#!/usr/bin/env python3
"""Evidence-safe triage and recovery helpers for public Epstein artifacts.

The tool separates a valid outer container from a damaged embedded payload,
keeps a public-recovery denylist, and refuses to write a decoded InfoPath
attachment unless its Base64, header, declared size, and filename all validate.

Usage:
    uv run python tools/epstein_recovery.py ledger --actionable \
      --output "$WORKDIR/recovery-ledger.json"
    uv run python tools/epstein_recovery.py inspect INPUT --efta-id EFTA00147557 \
      --expected-sha256 HASH --output "$WORKDIR/inspect.json"
    uv run python tools/epstein_recovery.py extract-text INPUT --pages 3-29 \
      --start-marker "<my:field11>" --end-marker "my:fieldll>" \
      --candidate-output "$WORKDIR/attachment.b64.txt" \
      --output "$WORKDIR/text-audit.json"
    uv run python tools/epstein_recovery.py ocr-pages INPUT --pages 4-28 \
      --ocr-dir "$WORKDIR/ocr" --psm 6 --psm 11 \
      --output "$WORKDIR/ocr-manifest.json"
    uv run python tools/epstein_recovery.py decode-infopath CANDIDATE \
      --artifact-dir "$WORKDIR/artifacts" --write-artifact \
      --output "$WORKDIR/decode.json"
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import mimetypes
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = (
    PROJECT_ROOT / "investigations" / "epstein" / "recovery" / "ledger.json"
)
BASE64_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)
INFOPATH_SIGNATURE = b"\xc7IFA"
MAX_INPUT_BYTES = 500 * 1024 * 1024
MAX_DECODED_BYTES = 100 * 1024 * 1024
EFTA_RE = re.compile(r"\bEFTA\d{8,}\b", re.IGNORECASE)

sys.path.insert(0, str(PROJECT_ROOT))
try:
    from tools.output_util import add_output_args, write_output
except ImportError:  # pragma: no cover - standalone invocation
    from output_util import add_output_args, write_output


class RecoveryError(ValueError):
    """Raised when evidence-safe validation fails."""


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_command(
    command: list[str],
    *,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RecoveryError(
            f"command timed out after {timeout}s: {command[0]}"
        ) from error


def require_binary(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RecoveryError(f"required binary is unavailable: {name}")
    return resolved


def parse_pages(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", value.strip())
    if not match:
        raise argparse.ArgumentTypeError("pages must be N or START-END")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError("pages must be positive and ordered")
    return start, end


def read_bounded(path: Path, limit: int = MAX_INPUT_BYTES) -> bytes:
    size = path.stat().st_size
    if size > limit:
        raise RecoveryError(f"input exceeds safety limit ({size:,} > {limit:,})")
    return path.read_bytes()


def file_type(path: Path) -> str:
    binary = shutil.which("file")
    if binary:
        result = run_command([binary, "--brief", "--mime-type", str(path)], timeout=20)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def parse_pdfinfo(stdout: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_line in stdout.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        normalized = key.strip().casefold().replace(" ", "_")
        clean = value.strip()
        if normalized in {"pages", "file_size"}:
            try:
                result[normalized] = int(clean.split()[0])
                continue
            except (ValueError, IndexError):
                pass
        result[normalized] = clean
    return result


def inspect_artifact(
    path: Path,
    *,
    efta_id: str | None = None,
    expected_sha256: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise RecoveryError(f"input file does not exist: {path}")
    size = path.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise RecoveryError(
            f"input exceeds the {MAX_INPUT_BYTES:,}-byte inspection limit"
        )
    digest = sha256_file(path)
    prefix = path.read_bytes()[:16]
    with path.open("rb") as handle:
        handle.seek(max(size - 65536, 0))
        tail = handle.read()
    is_pdf = prefix.startswith(b"%PDF-")
    result: dict[str, Any] = {
        "schema_version": "epstein-recovery-inspect/1.0",
        "inspected_at_utc": utc_now(),
        "efta_id": efta_id,
        "source_url": source_url,
        "path": str(path.resolve()),
        "bytes": size,
        "sha256": digest,
        "expected_sha256": expected_sha256,
        "hash_matches_expected": (
            digest.casefold() == expected_sha256.casefold()
            if expected_sha256
            else None
        ),
        "mime_type": file_type(path),
        "prefix_hex": prefix.hex(),
        "pdf_byte_structure": {
            "header": is_pdf,
            "eof_marker_in_tail": b"%%EOF" in tail,
            "startxref_in_tail": b"startxref" in tail,
            "xref_or_xref_stream_hint": (
                b"\nxref" in tail or b"/Type/XRef" in tail.replace(b" ", b"")
            ),
        },
    }
    if expected_sha256 and not result["hash_matches_expected"]:
        result["status"] = "hash_mismatch"
        return result
    if not is_pdf:
        result["status"] = "not_pdf"
        return result

    qpdf = shutil.which("qpdf")
    if qpdf:
        check = run_command([qpdf, "--check", str(path)], timeout=180)
        result["qpdf"] = {
            "returncode": check.returncode,
            "stdout": check.stdout.strip(),
            "stderr": check.stderr.strip(),
            "clean": check.returncode == 0,
        }
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        info = run_command([pdfinfo, str(path)], timeout=120)
        result["pdfinfo"] = {
            "returncode": info.returncode,
            "fields": parse_pdfinfo(info.stdout),
            "stderr": info.stderr.strip(),
        }
    byte_structure = result["pdf_byte_structure"]
    qpdf_clean = result.get("qpdf", {}).get("clean")
    result["status"] = (
        "valid_outer_pdf"
        if qpdf_clean is True
        else (
            "pdf_container_plausible"
            if byte_structure["header"]
            and byte_structure["eof_marker_in_tail"]
            and byte_structure["startxref_in_tail"]
            else "pdf_container_suspect"
        )
    )
    return result


def extract_between(text: str, start_marker: str | None, end_marker: str | None) -> str:
    start = 0
    if start_marker:
        index = text.find(start_marker)
        if index < 0:
            raise RecoveryError(f"start marker not found: {start_marker!r}")
        start = index + len(start_marker)
    end = len(text)
    if end_marker:
        index = text.find(end_marker, start)
        if index < 0:
            raise RecoveryError(f"end marker not found: {end_marker!r}")
        end = index
    return text[start:end]


def line_base64_score(line: str) -> float:
    compact = "".join(character for character in line if not character.isspace())
    if not compact:
        return 0.0
    acceptable = sum(
        character in BASE64_ALPHABET or character == "-" for character in compact
    )
    return acceptable / len(compact)


def audit_base64_ocr(
    text: str,
    *,
    expected_width: int = 76,
    minimum_line_chars: int = 20,
) -> tuple[dict[str, Any], str]:
    candidate_parts: list[str] = []
    line_records: list[dict[str, Any]] = []
    invalid_glyphs: Counter[str] = Counter()
    removed_footers = 0
    continuation_hyphens = 0

    for number, raw_line in enumerate(text.splitlines(), 1):
        line = EFTA_RE.sub("", raw_line).strip()
        if line != raw_line.strip():
            removed_footers += 1
        if len(line) < minimum_line_chars or line_base64_score(line) < 0.80:
            continue
        had_continuation = line.endswith("-")
        if had_continuation:
            line = line[:-1]
            continuation_hyphens += 1
        compact = "".join(character for character in line if not character.isspace())
        normalized_chars: list[str] = []
        line_invalid: list[dict[str, Any]] = []
        for offset, character in enumerate(compact):
            if character in BASE64_ALPHABET:
                normalized_chars.append(character)
            else:
                normalized_chars.append("?")
                invalid_glyphs[character] += 1
                line_invalid.append({"offset": offset, "glyph": character})
        normalized = "".join(normalized_chars)
        candidate_parts.append(normalized)
        line_records.append(
            {
                "source_line": number,
                "observed_length": len(normalized),
                "expected_width": expected_width,
                "length_delta": len(normalized) - expected_width,
                "continuation_hyphen_removed": had_continuation,
                "invalid_glyphs": line_invalid,
            }
        )

    candidate = "".join(candidate_parts)
    strict = bool(candidate) and set(candidate) <= BASE64_ALPHABET
    padding_shape_valid = (
        strict
        and len(candidate) % 4 == 0
        and re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", candidate) is not None
    )
    audit = {
        "candidate_length": len(candidate),
        "candidate_length_mod_4": len(candidate) % 4,
        "strict_base64_alphabet": strict,
        "padding_shape_valid": padding_shape_valid,
        "expected_line_width": expected_width,
        "candidate_lines": len(line_records),
        "line_length_histogram": dict(
            sorted(Counter(row["observed_length"] for row in line_records).items())
        ),
        "lines_with_length_errors": sum(
            row["length_delta"] != 0 for row in line_records
        ),
        "continuation_hyphens_removed": continuation_hyphens,
        "bates_footers_removed": removed_footers,
        "invalid_glyph_count": sum(invalid_glyphs.values()),
        "invalid_glyph_histogram": dict(invalid_glyphs.most_common()),
        "lines": line_records,
        "interpretation": (
            "A '?' marks an unrecognized OCR glyph. Valid-looking substitutions "
            "remain uncorrected and require independent OCR consensus."
        ),
    }
    return audit, candidate


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def extract_pdf_text(
    path: Path,
    pages: tuple[int, int],
    destination: Path,
) -> dict[str, Any]:
    pdftotext = require_binary("pdftotext")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".txt", dir=destination.parent
    )
    os.close(descriptor)
    temp_path = Path(temporary)
    try:
        result = run_command(
            [
                pdftotext,
                "-f",
                str(pages[0]),
                "-l",
                str(pages[1]),
                "-layout",
                str(path),
                str(temp_path),
            ],
            timeout=300,
        )
        if result.returncode != 0:
            raise RecoveryError(
                f"pdftotext failed ({result.returncode}): {result.stderr.strip()}"
            )
        os.replace(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)
    return {
        "path": str(destination.resolve()),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "pages": {"start": pages[0], "end": pages[1]},
    }


def parse_infopath_attachment(encoded_text: str) -> dict[str, Any]:
    compact = "".join(character for character in encoded_text if not character.isspace())
    invalid = sorted(set(compact) - BASE64_ALPHABET)
    if invalid:
        raise RecoveryError(f"candidate contains non-Base64 glyphs: {invalid!r}")
    if len(compact) % 4:
        raise RecoveryError(
            f"candidate length is not divisible by four: {len(compact):,}"
        )
    if len(compact) > (MAX_DECODED_BYTES * 4 // 3) + 8:
        raise RecoveryError("candidate exceeds decoded-size safety limit")
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error) as error:
        raise RecoveryError(f"strict Base64 decode failed: {error}") from error
    if len(decoded) < 24:
        raise RecoveryError("decoded candidate is shorter than an InfoPath header")

    signature = decoded[:4]
    header_size, version, reserved, file_size, name_chars = struct.unpack(
        "<IIIII", decoded[4:24]
    )
    if signature != INFOPATH_SIGNATURE:
        raise RecoveryError(
            f"InfoPath signature mismatch: {signature.hex()} != "
            f"{INFOPATH_SIGNATURE.hex()}"
        )
    if header_size != 0x14 or version != 1 or reserved != 0:
        raise RecoveryError(
            "InfoPath fixed header mismatch "
            f"(size={header_size}, version={version}, reserved={reserved})"
        )
    if name_chars < 1 or name_chars > 4096:
        raise RecoveryError(f"implausible InfoPath filename length: {name_chars}")
    name_bytes_length = name_chars * 2
    body_offset = 24 + name_bytes_length
    if body_offset > len(decoded):
        raise RecoveryError("InfoPath filename extends beyond decoded bytes")
    name_bytes = decoded[24:body_offset]
    if not name_bytes.endswith(b"\x00\x00"):
        raise RecoveryError("InfoPath filename is missing its UTF-16 terminator")
    try:
        filename = name_bytes[:-2].decode("utf-16le")
    except UnicodeDecodeError as error:
        raise RecoveryError("InfoPath filename is not valid UTF-16LE") from error
    body = decoded[body_offset:]
    if file_size != len(body):
        raise RecoveryError(
            f"InfoPath size mismatch: header declares {file_size:,}, "
            f"decoded body has {len(body):,}"
        )
    if file_size > MAX_DECODED_BYTES:
        raise RecoveryError("InfoPath body exceeds decoded-size safety limit")
    return {
        "base64_length": len(compact),
        "decoded_length": len(decoded),
        "signature_hex": signature.hex(),
        "header_size": header_size,
        "version": version,
        "reserved": reserved,
        "declared_file_size": file_size,
        "filename_chars_including_terminator": name_chars,
        "original_filename": filename,
        "body_offset": body_offset,
        "body": body,
    }


def safe_artifact_name(filename: str, digest: str) -> str:
    basename = Path(filename.replace("\\", "/")).name
    suffix = Path(basename).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
        suffix = ".bin"
    return f"recovered-{digest[:16]}{suffix}"


def validate_recovered_body(body: bytes, filename: str) -> dict[str, Any]:
    suffix = Path(filename).suffix.casefold()
    validation: dict[str, Any] = {
        "prefix_hex": body[:16].hex(),
        "suffix": suffix,
        "format_valid": False,
    }
    if suffix == ".pdf":
        validation["expected_format"] = "pdf"
        validation["pdf_header"] = body.startswith(b"%PDF-")
        if not validation["pdf_header"]:
            validation["failure"] = "filename declares PDF but body lacks %PDF- header"
            return validation
        qpdf = shutil.which("qpdf")
        if not qpdf:
            validation["failure"] = "qpdf is required for recovered PDF validation"
            return validation
        descriptor, temporary = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(body)
            check = run_command(
                [qpdf, "--check", str(Path(temporary).resolve())],
                timeout=120,
            )
            validation["qpdf"] = {
                "returncode": check.returncode,
                "stdout": check.stdout.strip(),
                "stderr": check.stderr.strip(),
            }
            qpdf_output = f"{check.stdout}\n{check.stderr}"
            if check.returncode == 0:
                qpdf_status = (
                    "warning"
                    if "WARNING" in qpdf_output.upper()
                    else "ok"
                )
            elif check.returncode == 3:
                # qpdf documents exit 3 as warning-only: processing succeeded.
                qpdf_status = "warning"
            else:
                qpdf_status = "error"
            validation["qpdf"]["status"] = qpdf_status
            validation["format_valid"] = qpdf_status in {"ok", "warning"}
            if qpdf_status == "warning":
                validation["warning"] = (
                    "qpdf completed with warnings; see recorded diagnostics"
                )
            if not validation["format_valid"]:
                validation["failure"] = "qpdf structural validation failed"
        finally:
            Path(temporary).unlink(missing_ok=True)
        return validation
    if suffix == ".xml":
        validation["expected_format"] = "xml"
        try:
            ET.fromstring(body)
            validation["xml_well_formed"] = True
            validation["format_valid"] = True
        except ET.ParseError as error:
            validation["xml_well_formed"] = False
            validation["xml_error"] = str(error)
            validation["failure"] = "XML parser rejected recovered body"
        return validation

    signatures: dict[str, tuple[bytes, ...]] = {
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".gif": (b"GIF87a", b"GIF89a"),
        ".rtf": (b"{\\rtf",),
        ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        ".ppt": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    }
    if suffix in signatures:
        validation["expected_format"] = suffix.removeprefix(".")
        validation["format_valid"] = body.startswith(signatures[suffix])
        if not validation["format_valid"]:
            validation["failure"] = (
                f"filename declares {suffix} but body signature does not match"
            )
        return validation
    if suffix in {".docx", ".xlsx", ".pptx", ".zip"}:
        validation["expected_format"] = suffix.removeprefix(".")
        descriptor, temporary = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(body)
            try:
                with zipfile.ZipFile(temporary) as archive:
                    bad_member = archive.testzip()
                    names = set(archive.namelist())
                validation["zip_bad_member"] = bad_member
                validation["zip_content_types_present"] = (
                    "[Content_Types].xml" in names
                )
                validation["format_valid"] = bad_member is None and (
                    suffix == ".zip" or validation["zip_content_types_present"]
                )
            except zipfile.BadZipFile as error:
                validation["zip_error"] = str(error)
            if not validation["format_valid"]:
                validation["failure"] = "ZIP/OOXML structural validation failed"
        finally:
            Path(temporary).unlink(missing_ok=True)
        return validation
    if suffix in {".txt", ".csv"}:
        validation["expected_format"] = suffix.removeprefix(".")
        try:
            body.decode("utf-8")
            validation["utf8"] = True
            validation["format_valid"] = True
        except UnicodeDecodeError as error:
            validation["utf8"] = False
            validation["failure"] = f"text body is not UTF-8: {error}"
        return validation

    validation["failure"] = (
        f"unsupported recovered attachment suffix {suffix or '<none>'}; "
        "no artifact was written"
    )
    return validation


def load_ledger(path: Path = DEFAULT_LEDGER) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RecoveryError(f"cannot load recovery ledger {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise RecoveryError("recovery ledger must contain a records list")
    return data


def command_ledger(args: argparse.Namespace) -> dict[str, Any]:
    ledger = load_ledger(Path(args.ledger))
    records = ledger["records"]
    if args.status:
        records = [record for record in records if record.get("status") in args.status]
    if args.actionable:
        records = [
            record
            for record in records
            if record.get("queue_decision") in {"active", "narrow_follow_up", "queued"}
        ]
    return {
        "schema_version": ledger.get("schema_version"),
        "as_of_utc": ledger.get("as_of_utc"),
        "records": records,
        "count": len(records),
    }


def command_extract_text(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input)
    text_path = Path(args.text_output)
    extraction = extract_pdf_text(source, args.pages, text_path)
    text = text_path.read_text(encoding="utf-8", errors="replace")
    selected = extract_between(text, args.start_marker, args.end_marker)
    audit, candidate = audit_base64_ocr(
        selected,
        expected_width=args.expected_width,
        minimum_line_chars=args.minimum_line_chars,
    )
    candidate_path = Path(args.candidate_output)
    atomic_write_text(candidate_path, candidate + "\n")
    return {
        "schema_version": "epstein-recovery-text-audit/1.0",
        "created_at_utc": utc_now(),
        "source": {
            "path": str(source.resolve()),
            "sha256": sha256_file(source),
        },
        "text_extraction": extraction,
        "selection": {
            "start_marker": args.start_marker,
            "end_marker": args.end_marker,
            "selected_characters": len(selected),
        },
        "base64_ocr_audit": audit,
        "candidate": {
            "path": str(candidate_path.resolve()),
            "sha256": sha256_file(candidate_path),
        },
    }


def command_ocr_pages(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input)
    pdftocairo = require_binary("pdftocairo")
    tesseract = require_binary("tesseract")
    ocr_dir = Path(args.ocr_dir)
    ocr_dir.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, Any]] = []
    whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=-"

    for page in range(args.pages[0], args.pages[1] + 1):
        image_prefix = ocr_dir / f"page-{page:04d}"
        render = run_command(
            [
                pdftocairo,
                "-f",
                str(page),
                "-l",
                str(page),
                "-singlefile",
                "-png",
                "-r",
                str(args.dpi),
                str(source),
                str(image_prefix),
            ],
            timeout=300,
        )
        if render.returncode != 0:
            raise RecoveryError(
                f"pdftocairo failed on page {page}: {render.stderr.strip()}"
            )
        image_path = image_prefix.with_suffix(".png")
        observations: list[dict[str, Any]] = []
        for psm in args.psm:
            ocr = run_command(
                [
                    tesseract,
                    str(image_path.resolve()),
                    "stdout",
                    "--psm",
                    str(psm),
                    "-l",
                    "eng",
                    "-c",
                    f"tessedit_char_whitelist={whitelist}",
                ],
                timeout=300,
            )
            if ocr.returncode != 0:
                raise RecoveryError(
                    f"tesseract failed on page {page}, psm {psm}: "
                    f"{ocr.stderr.strip()}"
                )
            text_path = ocr_dir / f"page-{page:04d}-psm-{psm}.txt"
            atomic_write_text(text_path, ocr.stdout)
            audit, _candidate = audit_base64_ocr(
                ocr.stdout,
                expected_width=args.expected_width,
                minimum_line_chars=args.minimum_line_chars,
            )
            observations.append(
                {
                    "psm": psm,
                    "text_path": str(text_path.resolve()),
                    "text_sha256": sha256_file(text_path),
                    "audit": {
                        key: value
                        for key, value in audit.items()
                        if key != "lines"
                    },
                }
            )
        pages.append(
            {
                "page": page,
                "image_path": str(image_path.resolve()),
                "image_sha256": sha256_file(image_path),
                "observations": observations,
            }
        )
        if not args.keep_images:
            image_path.unlink(missing_ok=True)
            pages[-1]["image_path"] = None
    return {
        "schema_version": "epstein-recovery-ocr/1.0",
        "created_at_utc": utc_now(),
        "source": {
            "path": str(source.resolve()),
            "sha256": sha256_file(source),
        },
        "settings": {
            "pages": {"start": args.pages[0], "end": args.pages[1]},
            "dpi": args.dpi,
            "psm": args.psm,
            "expected_width": args.expected_width,
            "images_retained": args.keep_images,
        },
        "pages": pages,
    }


def command_decode_infopath(args: argparse.Namespace) -> dict[str, Any]:
    candidate_path = Path(args.candidate)
    parsed = parse_infopath_attachment(
        candidate_path.read_text(encoding="ascii", errors="strict")
    )
    body = parsed.pop("body")
    digest = sha256_bytes(body)
    validation = validate_recovered_body(
        body, str(parsed["original_filename"])
    )
    result: dict[str, Any] = {
        "schema_version": "epstein-recovery-infopath/1.0",
        "validated_at_utc": utc_now(),
        "status": (
            "validated_recovery"
            if validation["format_valid"]
            else "invalid_body_format"
        ),
        "candidate": {
            "path": str(candidate_path.resolve()),
            "sha256": sha256_file(candidate_path),
        },
        "infopath": parsed,
        "artifact": {
            "sha256": digest,
            "bytes": len(body),
            "mime_type": None,
            "path": None,
            "written": False,
        },
        "validation": validation,
    }
    if args.write_artifact:
        if not validation["format_valid"]:
            raise RecoveryError(
                "decoded InfoPath wrapper is exact, but recovered body failed "
                f"filename/format validation: {validation.get('failure')}"
            )
        artifact_dir = Path(args.artifact_dir)
        artifact_name = safe_artifact_name(
            str(parsed["original_filename"]), digest
        )
        artifact_path = artifact_dir / artifact_name
        atomic_write_bytes(artifact_path, body)
        result["artifact"].update(
            {
                "path": str(artifact_path.resolve()),
                "mime_type": file_type(artifact_path),
                "written": True,
            }
        )
        provenance_path = artifact_dir / f"{artifact_name}.provenance.json"
        provenance = {
            **result,
            "provenance": {
                "source_ref": args.source_ref,
                "method": "strict InfoPath Base64/header/size validation",
                "no_synthetic_bytes": True,
            },
        }
        atomic_write_text(
            provenance_path,
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        )
        result["artifact"]["provenance_path"] = str(provenance_path.resolve())
    return result


def emit(data: dict[str, Any], args: argparse.Namespace, summary: str) -> None:
    result_count = data.get("count", 1)
    if write_output(data, args, summary=summary, result_count=result_count):
        return
    print(json.dumps(data, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evidence-safe Epstein artifact recovery helpers"
    )
    subparsers = parser.add_subparsers(dest="command")

    ledger = subparsers.add_parser("ledger", help="Show the recovery denylist/queue")
    ledger.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ledger.add_argument("--status", action="append")
    ledger.add_argument("--actionable", action="store_true")
    add_output_args(ledger)

    inspect = subparsers.add_parser(
        "inspect", help="Hash and structurally inspect one source artifact"
    )
    inspect.add_argument("input")
    inspect.add_argument("--efta-id")
    inspect.add_argument("--source-url")
    inspect.add_argument("--expected-sha256")
    add_output_args(inspect)

    extract = subparsers.add_parser(
        "extract-text",
        help="Extract PDF text and create an auditable OCR Base64 candidate",
    )
    extract.add_argument("input")
    extract.add_argument("--pages", type=parse_pages, required=True)
    extract.add_argument("--text-output", required=True)
    extract.add_argument("--candidate-output", required=True)
    extract.add_argument("--start-marker")
    extract.add_argument("--end-marker")
    extract.add_argument("--expected-width", type=int, default=76)
    extract.add_argument("--minimum-line-chars", type=int, default=20)
    add_output_args(extract)

    ocr = subparsers.add_parser(
        "ocr-pages", help="Render selected pages and run repeatable OCR passes"
    )
    ocr.add_argument("input")
    ocr.add_argument("--pages", type=parse_pages, required=True)
    ocr.add_argument("--ocr-dir", required=True)
    ocr.add_argument("--dpi", type=int, default=300)
    ocr.add_argument("--psm", type=int, action="append", default=[])
    ocr.add_argument("--expected-width", type=int, default=76)
    ocr.add_argument("--minimum-line-chars", type=int, default=20)
    ocr.add_argument("--keep-images", action="store_true")
    add_output_args(ocr)

    decode = subparsers.add_parser(
        "decode-infopath",
        help="Strictly decode a validated InfoPath attachment candidate",
    )
    decode.add_argument("candidate")
    decode.add_argument("--artifact-dir", required=True)
    decode.add_argument("--write-artifact", action="store_true")
    decode.add_argument("--source-ref")
    add_output_args(decode)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        raise SystemExit(1)
    if args.command == "ocr-pages" and not args.psm:
        args.psm = [6, 11]
    try:
        if args.command == "ledger":
            emit(command_ledger(args), args, "Epstein recovery ledger")
        elif args.command == "inspect":
            emit(
                inspect_artifact(
                    Path(args.input),
                    efta_id=args.efta_id,
                    expected_sha256=args.expected_sha256,
                    source_url=args.source_url,
                ),
                args,
                f"inspect {args.efta_id or Path(args.input).name}",
            )
        elif args.command == "extract-text":
            emit(command_extract_text(args), args, "OCR Base64 text audit")
        elif args.command == "ocr-pages":
            emit(command_ocr_pages(args), args, "page-selective OCR")
        elif args.command == "decode-infopath":
            emit(command_decode_infopath(args), args, "InfoPath decode")
        else:  # pragma: no cover - argparse controls choices
            raise RecoveryError(f"unknown command: {args.command}")
    except (OSError, RecoveryError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
