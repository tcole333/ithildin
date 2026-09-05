#!/usr/bin/env python3
"""Format-aware metadata inventory for local Epstein artifacts.

The source files are opened read-only. Exact bytes are content-addressed in the
regenerable ``datasets/epstein_derived.db`` sidecar, while raw metadata values
are stored with an explicit provenance layer so release-processing timestamps
cannot silently become source-event dates.

Usage:
    uv run python tools/epstein_metadata.py pilot --output "$WORKDIR/pilot.json"
    uv run python tools/epstein_metadata.py scan PATH [PATH ...] \
      --collection local-import --output "$WORKDIR/scan.json"
    uv run python tools/epstein_metadata.py report --reference-date 2019-07-06 \
      --output "$WORKDIR/report.json"
    uv run python tools/epstein_metadata.py show EFTA01091533 --output "$WORKDIR/show.json"
    uv run python tools/epstein_metadata.py stats --output "$WORKDIR/stats.json"
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import re
import shutil
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from tools.epstein_derived import DERIVED_DB, get_db, init_schema, new_run
    from tools.output_util import add_output_args, write_output
except ImportError:
    from epstein_derived import DERIVED_DB, get_db, init_schema, new_run
    from output_util import add_output_args, write_output

try:
    from tools.lead_tracker import log_search
except ImportError:  # pragma: no cover - standalone invocation fallback
    log_search = None


OUTPUT_SCHEMA_VERSION = "epstein-artifact-metadata/1.0"
EXTRACTOR_VERSION = "1"
DEFAULT_MAX_EXTRACT_BYTES = 250 * 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024
CSV_FIELD_LIMIT = 10 * 1024 * 1024

CANONICAL_REF_RE = re.compile(
    r"(EFTA\d{8,}|HOUSE_OVERSIGHT_\d+|DOJ-OGR-\d+|SDNY_GM(?:_SUPP)?_\d+)",
    re.IGNORECASE,
)
TIMESTAMP_FIELD_RE = re.compile(
    r"(?:date|time|created|creation|modified|modify|change|received|sent)",
    re.IGNORECASE,
)
SENSITIVE_FIELD_RE = re.compile(
    r"(?:gps|latitude|longitude|location|x-originating-ip|originating_ip|bcc)",
    re.IGNORECASE,
)
HIGH_VALUE_FIELD_RE = re.compile(
    r"(?:author|creator|producer|lastmodifiedby|company|template|software|"
    r"camera|model|serial|device|cart|original|folder|path|message.?id|"
    r"x-mailer|originating|gps|latitude|longitude|creation|created|modified)",
    re.IGNORECASE,
)
SUPPORTED_EXTENSIONS = {
    ".csv",
    ".docx",
    ".eml",
    ".gif",
    ".jpeg",
    ".jpg",
    ".json",
    ".m4a",
    ".meta",
    ".mov",
    ".mp3",
    ".mp4",
    ".msg",
    ".pdf",
    ".png",
    ".pptx",
    ".rtf",
    ".tif",
    ".tiff",
    ".wav",
    ".webp",
    ".xlsx",
    ".zip",
}
MEDIA_EXTENSIONS = {
    ".gif",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".png",
    ".tif",
    ".tiff",
    ".wav",
    ".webp",
}
OFFICE_EXTENSIONS = {".docx", ".xlsx", ".pptx"}


@dataclass(frozen=True)
class Observation:
    namespace: str
    field_name: str
    raw_value: str
    normalized_value: str | None
    value_type: str
    provenance_layer: str
    extractor: str
    extractor_version: str = EXTRACTOR_VERSION


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _path_key(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def _canonical_ref(path: Path) -> str | None:
    match = CANONICAL_REF_RE.search(str(path))
    return match.group(1).upper() if match else None


def _normalize_timestamp(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if abs(number) > 10_000_000_000:
            number /= 1000
        try:
            return datetime.fromtimestamp(number, tz=UTC).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError):
            return None

    raw = str(value).strip()
    if not raw:
        return None
    if re.fullmatch(r"-?\d{9,13}(?:\.\d+)?", raw):
        return _normalize_timestamp(float(raw))

    pdf_match = re.fullmatch(
        r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?"
        r"(?:([Zz]|[+-])(\d{2})?'?(\d{2})?'?)?",
        raw,
    )
    if pdf_match:
        year, month, day, hour, minute, second, sign, tz_h, tz_m = pdf_match.groups()
        base = datetime(
            int(year),
            int(month or 1),
            int(day or 1),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
        )
        if sign and sign.upper() == "Z":
            return base.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
        if sign in {"+", "-"}:
            offset_minutes = int(tz_h or 0) * 60 + int(tz_m or 0)
            if sign == "-":
                offset_minutes *= -1
            from datetime import timedelta, timezone

            aware = base.replace(tzinfo=timezone(timedelta(minutes=offset_minutes)))
            return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return base.isoformat()

    iso_raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_raw)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return parsed.isoformat()
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.isoformat()
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _observation(
    namespace: str,
    field_name: str,
    value: Any,
    provenance_layer: str,
    extractor: str,
    *,
    value_type: str = "text",
    normalize_timestamp: bool | None = None,
) -> Observation | None:
    if value is None:
        return None
    raw = _json_text(value).strip()
    if not raw:
        return None
    if normalize_timestamp is None:
        normalize_timestamp = bool(TIMESTAMP_FIELD_RE.search(field_name))
    normalized = _normalize_timestamp(value) if normalize_timestamp else None
    return Observation(
        namespace=namespace,
        field_name=field_name,
        raw_value=raw,
        normalized_value=normalized,
        value_type=value_type,
        provenance_layer=provenance_layer,
        extractor=extractor,
    )


def _append_observation(
    observations: list[Observation],
    namespace: str,
    field_name: str,
    value: Any,
    provenance_layer: str,
    extractor: str,
    **kwargs: Any,
) -> None:
    item = _observation(
        namespace,
        field_name,
        value,
        provenance_layer,
        extractor,
        **kwargs,
    )
    if item is not None:
        observations.append(item)


def _run_command(command: list[str], timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _mime_type(path: Path) -> str:
    binary = shutil.which("file")
    if binary:
        result = _run_command([binary, "--brief", "--mime-type", str(path)], timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _extract_email(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    with path.open("rb") as handle:
        message = BytesParser(policy=policy.default).parse(handle)

    repeatable_headers = {
        "received",
        "authentication-results",
        "references",
    }
    selected_headers = {
        "bcc",
        "cc",
        "content-language",
        "content-type",
        "date",
        "from",
        "in-reply-to",
        "message-id",
        "mime-version",
        "received",
        "reply-to",
        "return-path",
        "sender",
        "subject",
        "thread-index",
        "thread-topic",
        "to",
        "user-agent",
        "x-apparently-to",
        "x-mailer",
        "x-originating-ip",
    }
    for header in selected_headers:
        values = message.get_all(header, [])
        if not values:
            continue
        if header not in repeatable_headers:
            values = values[:1]
        for value in values:
            _append_observation(
                observations,
                "email.header",
                header.lower(),
                str(value),
                "source_native",
                "stdlib-email",
            )

    attachment_count = 0
    for attachment_count, part in enumerate(message.iter_attachments(), start=1):
        prefix = f"attachment_{attachment_count}"
        _append_observation(
            observations,
            "email.attachment",
            f"{prefix}.filename",
            part.get_filename() or "",
            "source_native",
            "stdlib-email",
            normalize_timestamp=False,
        )
        _append_observation(
            observations,
            "email.attachment",
            f"{prefix}.content_type",
            part.get_content_type(),
            "source_native",
            "stdlib-email",
            normalize_timestamp=False,
        )
        _append_observation(
            observations,
            "email.attachment",
            f"{prefix}.content_id",
            part.get("Content-ID"),
            "source_native",
            "stdlib-email",
            normalize_timestamp=False,
        )
        payload = part.get_payload(decode=True)
        if payload is not None:
            _append_observation(
                observations,
                "email.attachment",
                f"{prefix}.byte_length",
                len(payload),
                "source_native",
                "stdlib-email",
                value_type="integer",
                normalize_timestamp=False,
            )
            _append_observation(
                observations,
                "email.attachment",
                f"{prefix}.sha256",
                hashlib.sha256(payload).hexdigest(),
                "source_native",
                "stdlib-email",
                normalize_timestamp=False,
            )
    _append_observation(
        observations,
        "email.structure",
        "attachment_count",
        attachment_count,
        "source_native",
        "stdlib-email",
        value_type="integer",
        normalize_timestamp=False,
    )

    sent = _normalize_timestamp(message.get("Date"))
    received_dates: list[str] = []
    for received in message.get_all("Received", []):
        if ";" not in str(received):
            continue
        normalized = _normalize_timestamp(str(received).rsplit(";", 1)[-1].strip())
        if normalized:
            received_dates.append(normalized)
    if received_dates:
        received_dates.sort()
        _append_observation(
            observations,
            "email.analysis",
            "received_min",
            received_dates[0],
            "source_native",
            "stdlib-email",
        )
        _append_observation(
            observations,
            "email.analysis",
            "received_max",
            received_dates[-1],
            "source_native",
            "stdlib-email",
        )
    if sent and received_dates:
        try:
            sent_dt = _parse_normalized_datetime(sent)
            recv_dt = _parse_normalized_datetime(received_dates[-1])
        except ValueError:
            sent_dt = recv_dt = None
        if sent_dt and recv_dt:
            delta = int((sent_dt - recv_dt).total_seconds())
            _append_observation(
                observations,
                "email.analysis",
                "sent_minus_last_received_seconds",
                delta,
                "source_native",
                "stdlib-email",
                value_type="integer",
                normalize_timestamp=False,
            )
    return observations


def _extract_mail_sidecar(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("mail sidecar must contain a JSON object")
    exact_companion = path.with_suffix("")
    _append_observation(
        observations,
        "mail_sidecar.inventory",
        "exact_eml_companion_present",
        exact_companion.is_file(),
        "acquisition",
        "filesystem-inventory",
        value_type="boolean",
        normalize_timestamp=False,
    )
    for key, value in sorted(data.items()):
        if key == "metadata":
            raw = _json_text(value)
            _append_observation(
                observations,
                "mail_sidecar",
                "metadata_payload_length",
                len(raw),
                "production_lineage",
                "json-sidecar",
                value_type="integer",
                normalize_timestamp=False,
            )
            _append_observation(
                observations,
                "mail_sidecar",
                "metadata_payload_sha256",
                _sha256_text(raw),
                "production_lineage",
                "json-sidecar",
                normalize_timestamp=False,
            )
            continue
        _append_observation(
            observations,
            "mail_sidecar",
            key,
            value,
            "production_lineage",
            "json-sidecar",
            value_type="json" if isinstance(value, (list, dict)) else "text",
            normalize_timestamp=key.lower() in {"date", "change_date"},
        )
    return observations


def _parse_colon_output(output: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            rows.append((key, value))
    return rows


def _qpdf_status(returncode: int, output: str) -> str:
    if returncode == 0:
        return "warning" if "WARNING" in output.upper() else "ok"
    if returncode == 3:
        return "warning"
    return "error"


def _xml_leaf_values(root: ET.Element) -> Iterable[tuple[str, str]]:
    for element in root.iter():
        text = (element.text or "").strip()
        if not text:
            continue
        tag = element.tag.rsplit("}", 1)[-1]
        yield tag, text


def _extract_pdf(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        result = _run_command([pdfinfo, "-isodates", str(path)])
        if result.returncode == 0:
            for key, value in _parse_colon_output(result.stdout):
                _append_observation(
                    observations,
                    "pdf.info",
                    key.lower().replace(" ", "_"),
                    value,
                    "release_container",
                    "pdfinfo",
                )
        else:
            _append_observation(
                observations,
                "pdf.validation",
                "pdfinfo_error",
                result.stderr.strip() or f"exit {result.returncode}",
                "release_container",
                "pdfinfo",
                normalize_timestamp=False,
            )

        meta = _run_command([pdfinfo, "-meta", str(path)])
        xmp = meta.stdout.strip()
        if meta.returncode == 0 and xmp.startswith("<"):
            try:
                root = ET.fromstring(xmp)
            except ET.ParseError:
                _append_observation(
                    observations,
                    "pdf.xmp",
                    "raw_sha256",
                    _sha256_text(xmp),
                    "release_container",
                    "pdfinfo",
                    normalize_timestamp=False,
                )
            else:
                for key, value in _xml_leaf_values(root):
                    _append_observation(
                        observations,
                        "pdf.xmp",
                        key,
                        value,
                        "release_container",
                        "pdfinfo",
                    )

    qpdf = shutil.which("qpdf")
    if qpdf:
        result = _run_command([qpdf, "--check", str(path)])
        combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
        status = _qpdf_status(result.returncode, combined)
        _append_observation(
            observations,
            "pdf.validation",
            "qpdf_status",
            status,
            "release_container",
            "qpdf",
            normalize_timestamp=False,
        )

    pdfdetach = shutil.which("pdfdetach")
    if pdfdetach:
        result = _run_command([pdfdetach, "-list", str(path)])
        if result.returncode == 0:
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            count = 0
            names: list[str] = []
            if lines:
                match = re.search(r"(\d+)\s+embedded files?", lines[0], re.IGNORECASE)
                if match:
                    count = int(match.group(1))
                for line in lines[1:]:
                    if ":" in line:
                        names.append(line.split(":", 1)[1].strip())
            _append_observation(
                observations,
                "pdf.embedded_files",
                "count",
                count,
                "release_container",
                "pdfdetach",
                value_type="integer",
                normalize_timestamp=False,
            )
            for name in names:
                _append_observation(
                    observations,
                    "pdf.embedded_files",
                    "filename",
                    name,
                    "release_container",
                    "pdfdetach",
                    normalize_timestamp=False,
                )
    return observations


def _extract_openxml(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    parts = {
        "docProps/core.xml": "office.core",
        "docProps/app.xml": "office.app",
        "docProps/custom.xml": "office.custom",
    }
    with zipfile.ZipFile(path) as archive:
        for member, namespace in parts.items():
            try:
                raw = archive.read(member)
            except KeyError:
                continue
            root = ET.fromstring(raw)
            for key, value in _xml_leaf_values(root):
                _append_observation(
                    observations,
                    namespace,
                    key,
                    value,
                    "source_native",
                    "openxml",
                )
    return observations


def _extract_zip(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        encrypted = sum(bool(item.flag_bits & 0x1) for item in infos)
        names = [item.filename for item in infos]
        dates = [
            datetime(*item.date_time).isoformat()
            for item in infos
            if item.date_time[0] >= 1980
        ]
        top_levels = sorted({name.split("/", 1)[0] for name in names if name})
        _append_observation(
            observations,
            "archive.structure",
            "member_count",
            len(infos),
            "container_embedded",
            "stdlib-zipfile",
            value_type="integer",
            normalize_timestamp=False,
        )
        _append_observation(
            observations,
            "archive.structure",
            "encrypted_member_count",
            encrypted,
            "container_embedded",
            "stdlib-zipfile",
            value_type="integer",
            normalize_timestamp=False,
        )
        _append_observation(
            observations,
            "archive.structure",
            "top_level_names",
            top_levels[:100],
            "container_embedded",
            "stdlib-zipfile",
            value_type="json",
            normalize_timestamp=False,
        )
        if dates:
            _append_observation(
                observations,
                "archive.structure",
                "earliest_member_date",
                min(dates),
                "container_embedded",
                "stdlib-zipfile",
            )
            _append_observation(
                observations,
                "archive.structure",
                "latest_member_date",
                max(dates),
                "container_embedded",
                "stdlib-zipfile",
            )
        special = [
            name
            for name in names
            if Path(name).name.lower()
            in {".ds_store", "thumbs.db", "desktop.ini", "zone.identifier"}
        ]
        if special:
            _append_observation(
                observations,
                "archive.structure",
                "special_members",
                special[:100],
                "container_embedded",
                "stdlib-zipfile",
                value_type="json",
                normalize_timestamp=False,
            )
    return observations


def _extract_rtf(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    text = path.read_text(encoding="latin-1", errors="replace")[:2_000_000]
    scalar_fields = {
        "author": r"\\author\s+([^{}\\]+)",
        "company": r"\\company\s+([^{}\\]+)",
        "operator": r"\\operator\s+([^{}\\]+)",
        "title": r"\\title\s+([^{}\\]+)",
        "subject": r"\\subject\s+([^{}\\]+)",
        "keywords": r"\\keywords\s+([^{}\\]+)",
    }
    for field, pattern in scalar_fields.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            _append_observation(
                observations,
                "rtf.info",
                field,
                match.group(1).strip(),
                "source_native",
                "rtf-info",
                normalize_timestamp=False,
            )
    for field, pattern in {
        "creation_date": r"\\creatim([^}]*)",
        "revision_date": r"\\revtim([^}]*)",
        "print_date": r"\\printim([^}]*)",
    }.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        values = dict(
            (key, int(value))
            for key, value in re.findall(r"\\(yr|mo|dy|hr|min|sec)(\d+)", match.group(1))
        )
        try:
            timestamp = datetime(
                values["yr"],
                values.get("mo", 1),
                values.get("dy", 1),
                values.get("hr", 0),
                values.get("min", 0),
                values.get("sec", 0),
            ).isoformat()
        except (KeyError, ValueError):
            continue
        _append_observation(
            observations,
            "rtf.info",
            field,
            timestamp,
            "source_native",
            "rtf-info",
        )
    return observations


def _extract_csv(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    csv.field_size_limit(CSV_FIELD_LIMIT)
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:100_000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(text.splitlines(), dialect)
    header = next(reader, [])
    rows_scanned = sum(1 for _index, _row in zip(range(10_000), reader))
    _append_observation(
        observations,
        "csv.structure",
        "header",
        header,
        "container_embedded",
        "stdlib-csv",
        value_type="json",
        normalize_timestamp=False,
    )
    _append_observation(
        observations,
        "csv.structure",
        "delimiter",
        dialect.delimiter,
        "container_embedded",
        "stdlib-csv",
        normalize_timestamp=False,
    )
    _append_observation(
        observations,
        "csv.structure",
        "rows_scanned",
        rows_scanned,
        "container_embedded",
        "stdlib-csv",
        value_type="integer",
        normalize_timestamp=False,
    )
    return observations


def _flatten_ffprobe(data: dict[str, Any]) -> Iterable[tuple[str, str, Any]]:
    format_data = data.get("format") or {}
    for key in (
        "format_name",
        "format_long_name",
        "duration",
        "size",
        "bit_rate",
        "probe_score",
    ):
        if key in format_data:
            yield "ffprobe.format", key, format_data[key]
    for key, value in sorted((format_data.get("tags") or {}).items()):
        yield "ffprobe.format.tags", key, value
    for index, stream in enumerate(data.get("streams") or []):
        namespace = f"ffprobe.stream.{index}"
        for key in (
            "codec_name",
            "codec_long_name",
            "codec_type",
            "profile",
            "width",
            "height",
            "pix_fmt",
            "sample_rate",
            "channels",
            "duration",
            "bit_rate",
        ):
            if key in stream:
                yield namespace, key, stream[key]
        for key, value in sorted((stream.get("tags") or {}).items()):
            yield f"{namespace}.tags", key, value


def _extract_media(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        result = _run_command(
            [
                ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ]
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            for namespace, key, value in _flatten_ffprobe(data):
                _append_observation(
                    observations,
                    namespace,
                    key,
                    value,
                    "container_embedded",
                    "ffprobe",
                )
    return observations


def _exiftool_layer(namespace: str) -> str:
    prefix = namespace.split(":", 1)[0].lower()
    if prefix in {"file", "system"}:
        return "acquisition"
    if prefix == "pdf":
        return "release_container"
    if prefix in {"exif", "iptc", "xmp", "composite", "maker"}:
        return "source_native"
    return "container_embedded"


def _extract_exiftool(path: Path) -> list[Observation]:
    binary = shutil.which("exiftool")
    if not binary:
        return []
    result = _run_command(
        [binary, "-json", "-G1", "-a", "-u", "-api", "LargeFileSupport=1", str(path)],
        timeout=90,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    payload = json.loads(result.stdout)
    if not payload or not isinstance(payload[0], dict):
        return []
    observations: list[Observation] = []
    skipped = {
        "SourceFile",
        "File:FileName",
        "File:Directory",
        "File:FilePermissions",
        "System:FilePermissions",
        "System:FileAccessDate",
        "System:FileModifyDate",
        "System:FileInodeChangeDate",
    }
    for key, value in sorted(payload[0].items()):
        if key in skipped:
            continue
        namespace, _, field = key.partition(":")
        _append_observation(
            observations,
            f"exiftool.{namespace.lower()}",
            field or namespace,
            value,
            _exiftool_layer(key),
            "exiftool",
            value_type="json" if isinstance(value, (list, dict)) else "text",
        )
    return observations


def extract_metadata(path: Path, *, max_extract_bytes: int) -> list[Observation]:
    stat = path.stat()
    observations: list[Observation] = []
    _append_observation(
        observations,
        "filesystem",
        "modified_time",
        datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat().replace("+00:00", "Z"),
        "acquisition",
        "stat",
    )
    _append_observation(
        observations,
        "filesystem",
        "change_time",
        datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat().replace("+00:00", "Z"),
        "acquisition",
        "stat",
    )
    _append_observation(
        observations,
        "filesystem",
        "filename",
        path.name,
        "acquisition",
        "stat",
        normalize_timestamp=False,
    )
    if stat.st_size > max_extract_bytes:
        _append_observation(
            observations,
            "scan",
            "content_extraction_skipped",
            f"file exceeds max_extract_bytes={max_extract_bytes}",
            "acquisition",
            "epstein_metadata",
            normalize_timestamp=False,
        )
        return observations

    suffix = path.suffix.lower()
    if suffix == ".eml":
        observations.extend(_extract_email(path))
    elif suffix == ".meta":
        observations.extend(_extract_mail_sidecar(path))
    elif suffix == ".pdf":
        observations.extend(_extract_pdf(path))
    elif suffix in OFFICE_EXTENSIONS:
        observations.extend(_extract_openxml(path))
        observations.extend(_extract_zip(path))
    elif suffix == ".zip":
        observations.extend(_extract_zip(path))
    elif suffix == ".rtf":
        observations.extend(_extract_rtf(path))
    elif suffix == ".csv":
        observations.extend(_extract_csv(path))
    elif suffix in MEDIA_EXTENSIONS:
        observations.extend(_extract_media(path))
    observations.extend(_extract_exiftool(path))
    return observations


def _parse_normalized_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _evidence_item_id(db: sqlite3.Connection, canonical_ref: str | None) -> int | None:
    if not canonical_ref:
        return None
    row = db.execute(
        "SELECT evidence_item_id FROM evidence_item WHERE canonical_ref=?",
        (canonical_ref,),
    ).fetchone()
    return int(row[0]) if row else None


def _store_file(
    db: sqlite3.Connection,
    path: Path,
    collection: str,
    run_id: int,
    *,
    max_extract_bytes: int,
) -> dict[str, Any]:
    stat = path.stat()
    sha256 = _sha256_file(path)
    suffix = path.suffix.lower()
    media_type = _mime_type(path)
    relative_path = _path_key(path)
    canonical_ref = _canonical_ref(path)
    evidence_id = _evidence_item_id(db, canonical_ref)

    db.execute(
        """
        INSERT INTO artifact_file(
            sha256, byte_length, media_type, file_extension,
            first_seen_run, last_seen_run
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(sha256) DO UPDATE SET
            byte_length=excluded.byte_length,
            media_type=excluded.media_type,
            file_extension=excluded.file_extension,
            last_seen_run=excluded.last_seen_run
        """,
        (sha256, stat.st_size, media_type, suffix or None, run_id, run_id),
    )
    artifact_id = int(
        db.execute("SELECT artifact_id FROM artifact_file WHERE sha256=?", (sha256,)).fetchone()[0]
    )
    db.execute(
        """
        INSERT INTO artifact_location(
            artifact_id, relative_path, collection_name, canonical_ref,
            evidence_item_id, filesystem_mtime_ns, filesystem_ctime_ns,
            first_seen_run, last_seen_run
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(relative_path) DO UPDATE SET
            artifact_id=excluded.artifact_id,
            collection_name=excluded.collection_name,
            canonical_ref=excluded.canonical_ref,
            evidence_item_id=excluded.evidence_item_id,
            filesystem_mtime_ns=excluded.filesystem_mtime_ns,
            filesystem_ctime_ns=excluded.filesystem_ctime_ns,
            last_seen_run=excluded.last_seen_run
        """,
        (
            artifact_id,
            relative_path,
            collection,
            canonical_ref,
            evidence_id,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
            run_id,
            run_id,
        ),
    )
    location_id = int(
        db.execute(
            "SELECT location_id FROM artifact_location WHERE relative_path=?",
            (relative_path,),
        ).fetchone()[0]
    )
    db.execute(
        "DELETE FROM artifact_metadata_observation WHERE location_id=?",
        (location_id,),
    )

    observations = extract_metadata(path, max_extract_bytes=max_extract_bytes)
    occurrence_counts: Counter[tuple[str, str]] = Counter()
    for observation in observations:
        key = (observation.namespace, observation.field_name)
        occurrence = occurrence_counts[key]
        occurrence_counts[key] += 1
        db.execute(
            """
            INSERT INTO artifact_metadata_observation(
                artifact_id, location_id, namespace, field_name, occurrence,
                raw_value, normalized_value, value_type, provenance_layer,
                extractor, extractor_version, first_seen_run, last_seen_run
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                location_id,
                observation.namespace,
                observation.field_name,
                occurrence,
                observation.raw_value,
                observation.normalized_value,
                observation.value_type,
                observation.provenance_layer,
                observation.extractor,
                observation.extractor_version,
                run_id,
                run_id,
            ),
        )
    return {
        "path": relative_path,
        "collection": collection,
        "canonical_ref": canonical_ref,
        "sha256": sha256,
        "byte_length": stat.st_size,
        "media_type": media_type,
        "observation_count": len(observations),
    }


def _supported_files(paths: Iterable[Path], extensions: set[str] | None) -> list[Path]:
    files: list[Path] = []
    allowed = extensions or SUPPORTED_EXTENSIONS
    for source in paths:
        if source.is_file():
            if source.suffix.lower() in allowed:
                files.append(source)
            continue
        if not source.exists():
            raise FileNotFoundError(source)
        files.extend(
            path
            for path in source.rglob("*")
            if path.is_file() and path.suffix.lower() in allowed
        )
    return sorted(set(files), key=lambda item: _path_key(item).lower())


def _even_sample(paths: list[Path], limit: int) -> list[Path]:
    if limit <= 0 or len(paths) <= limit:
        return paths
    return [paths[index * len(paths) // limit] for index in range(limit)]


def _pilot_files(max_files: int) -> list[tuple[Path, str]]:
    archive = PROJECT_ROOT / "datasets" / "epstein-archive" / "data"
    selected: list[tuple[Path, str]] = []

    def add(paths: Iterable[Path], collection: str) -> None:
        selected.extend((path, collection) for path in paths if path.is_file())

    barak_dir = archive / "emails" / "ehud_barak_emails"
    sidecars = _even_sample(sorted(barak_dir.glob("*.eml.meta")), 100)
    add(sidecars, "ehud_barak_mail_sidecars")
    add((Path(str(path)[:-5]) for path in sidecars), "ehud_barak_emails")
    barak_emails = sorted(barak_dir.glob("*.eml"))
    add(_even_sample(barak_emails, 25), "ehud_barak_emails")

    yahoo_dir = archive / "emails" / "jeeproject_yahoo"
    add(_even_sample(sorted(yahoo_dir.rglob("*.eml")), 50), "jeeproject_yahoo")

    add(sorted((archive / "originals").glob("*.pdf")), "epstein_archive_originals")
    add(sorted((archive / "text" / "lvoocaudiop1").glob("*.pdf")), "audio_transcript_pdfs")
    add(sorted((PROJECT_ROOT / "datasets").glob("EFTA*.pdf")), "local_efta_pdfs")

    estate = archive / "media" / "images" / "12.11.25 Estate Production"
    usvi = archive / "media" / "images" / "12.03.25 USVI Production"
    add(_even_sample(_supported_files([estate], MEDIA_EXTENSIONS), 80), "estate_production_media")
    add(_even_sample(_supported_files([usvi], MEDIA_EXTENSIONS), 40), "usvi_production_media")

    add(sorted((archive / "csv").rglob("*.csv")), "house_oversight_csv")
    add(sorted((archive / "text").rglob("*.rtf")), "epstein_archive_rtf")
    add(sorted(archive.rglob("*.docx")), "epstein_archive_office")
    add(sorted(archive.rglob("*.xlsx")), "epstein_archive_office")
    add(sorted(archive.rglob("*.pptx")), "epstein_archive_office")
    add(sorted(archive.rglob("*.zip")), "epstein_archive_archives")

    deduped: dict[str, tuple[Path, str]] = {}
    for path, collection in selected:
        deduped.setdefault(str(path.resolve()), (path, collection))
    rows = sorted(deduped.values(), key=lambda item: (item[1], _path_key(item[0]).lower()))
    return _even_sample_pairs(rows, max_files)


def _even_sample_pairs(
    rows: list[tuple[Path, str]], limit: int
) -> list[tuple[Path, str]]:
    if limit <= 0 or len(rows) <= limit:
        return rows
    grouped: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[1]].append(row)
    total = len(rows)
    allocations: dict[str, int] = {}
    for collection, items in grouped.items():
        allocations[collection] = max(1, round(limit * len(items) / total))
    while sum(allocations.values()) > limit:
        reducible = [key for key, value in allocations.items() if value > 1]
        if not reducible:
            break
        key = max(reducible, key=lambda item: allocations[item])
        allocations[key] -= 1
    while sum(allocations.values()) < limit:
        expandable = [
            key
            for key, value in allocations.items()
            if value < len(grouped[key])
        ]
        if not expandable:
            break
        key = max(expandable, key=lambda item: len(grouped[item]) - allocations[item])
        allocations[key] += 1
    sampled: list[tuple[Path, str]] = []
    for collection in sorted(grouped):
        items = grouped[collection]
        quota = min(allocations[collection], len(items))
        sampled.extend(items[index * len(items) // quota] for index in range(quota))
    return sampled[:limit]


def scan_files(
    db_path: Path,
    files: list[tuple[Path, str]],
    *,
    note: str,
    max_extract_bytes: int,
) -> dict[str, Any]:
    db = get_db(db_path)
    init_schema(db)
    run_id = int(
        new_run(
            db,
            "epstein_metadata",
            note=note,
            code_version=OUTPUT_SCHEMA_VERSION,
        )
    )
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for index, (path, collection) in enumerate(files, start=1):
        try:
            results.append(
                _store_file(
                    db,
                    path,
                    collection,
                    run_id,
                    max_extract_bytes=max_extract_bytes,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "path": _path_key(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        if index % 25 == 0:
            db.commit()
    db.execute(
        """
        UPDATE derivation_run
        SET completed_at=CURRENT_TIMESTAMP, record_count=?,
            note=COALESCE(note, '') || ?
        WHERE run_id=?
        """,
        (
            len(results),
            f"; errors={len(errors)}",
            run_id,
        ),
    )
    db.commit()
    db.close()
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "run_id": run_id,
        "scanned": len(results),
        "errors": errors,
        "capabilities": {
            binary: bool(shutil.which(binary))
            for binary in ("exiftool", "ffprobe", "file", "pdfdetach", "pdfinfo", "qpdf")
        },
        "collections": dict(Counter(item["collection"] for item in results)),
        "extensions": dict(Counter(Path(item["path"]).suffix.lower() for item in results)),
        "observations": sum(item["observation_count"] for item in results),
        "files": results,
    }


def _metadata_rows(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in db.execute(
            """
            SELECT m.*, l.relative_path, l.collection_name, l.canonical_ref,
                   a.sha256, a.media_type, a.file_extension
            FROM artifact_metadata_observation m
            JOIN artifact_location l ON l.location_id=m.location_id
            JOIN artifact_file a ON a.artifact_id=m.artifact_id
            """
        )
    ]


def _redact_value(field_name: str, raw_value: str, include_sensitive: bool) -> str:
    if include_sensitive or not SENSITIVE_FIELD_RE.search(field_name):
        return raw_value
    return "[withheld-sensitive-metadata]"


def build_stats(db_path: Path) -> dict[str, Any]:
    db = get_db(db_path)
    init_schema(db)
    result = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "artifacts": db.execute("SELECT COUNT(*) FROM artifact_file").fetchone()[0],
        "locations": db.execute("SELECT COUNT(*) FROM artifact_location").fetchone()[0],
        "observations": db.execute(
            "SELECT COUNT(*) FROM artifact_metadata_observation"
        ).fetchone()[0],
        "duplicate_artifacts": db.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT artifact_id FROM artifact_location
                GROUP BY artifact_id HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0],
        "by_collection": {
            row[0]: row[1]
            for row in db.execute(
                """
                SELECT collection_name, COUNT(*) FROM artifact_location
                GROUP BY collection_name ORDER BY COUNT(*) DESC, collection_name
                """
            )
        },
        "by_extension": {
            row[0] or "[none]": row[1]
            for row in db.execute(
                """
                SELECT file_extension, COUNT(*) FROM artifact_file
                GROUP BY file_extension ORDER BY COUNT(*) DESC, file_extension
                """
            )
        },
        "by_provenance_layer": {
            row[0]: row[1]
            for row in db.execute(
                """
                SELECT provenance_layer, COUNT(*) FROM artifact_metadata_observation
                GROUP BY provenance_layer ORDER BY COUNT(*) DESC, provenance_layer
                """
            )
        },
        "by_namespace": {
            row[0]: row[1]
            for row in db.execute(
                """
                SELECT namespace, COUNT(*) FROM artifact_metadata_observation
                GROUP BY namespace ORDER BY COUNT(*) DESC, namespace
                """
            )
        },
    }
    db.close()
    return result


def build_report(
    db_path: Path,
    *,
    reference_date: str,
    limit: int,
    cluster_min: int,
    include_sensitive: bool,
) -> dict[str, Any]:
    reference = datetime.fromisoformat(reference_date).replace(tzinfo=UTC)
    db = get_db(db_path)
    init_schema(db)
    rows = _metadata_rows(db)

    post_reference: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        normalized = row.get("normalized_value")
        if not normalized or not TIMESTAMP_FIELD_RE.search(row["field_name"]):
            continue
        try:
            value = _parse_normalized_datetime(normalized)
        except ValueError:
            continue
        if value <= reference:
            continue
        layer = row["provenance_layer"]
        if len(post_reference[layer]) >= limit:
            continue
        post_reference[layer].append(
            {
                "path": row["relative_path"],
                "canonical_ref": row["canonical_ref"],
                "namespace": row["namespace"],
                "field": row["field_name"],
                "raw_value": _redact_value(
                    row["field_name"], row["raw_value"] or "", include_sensitive
                ),
                "normalized_value": normalized,
            }
        )

    duplicate_groups = [
        {
            "sha256": row["sha256"],
            "location_count": row["location_count"],
            "paths": json.loads(row["paths"]),
        }
        for row in db.execute(
            """
            SELECT a.sha256, COUNT(*) AS location_count,
                   json_group_array(l.relative_path) AS paths
            FROM artifact_file a
            JOIN artifact_location l ON l.artifact_id=a.artifact_id
            GROUP BY a.artifact_id
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, a.sha256
            LIMIT ?
            """,
            (limit,),
        )
    ]

    cluster_counter: Counter[tuple[str, str, str]] = Counter()
    cluster_paths: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        value = row.get("normalized_value") or row.get("raw_value")
        if not value:
            continue
        field = row["field_name"]
        if not (TIMESTAMP_FIELD_RE.search(field) or HIGH_VALUE_FIELD_RE.search(field)):
            continue
        key = (row["namespace"], field, str(value))
        cluster_paths[key].add(row["relative_path"])
    for key, paths in cluster_paths.items():
        cluster_counter[key] = len(paths)
    clusters = []
    for (namespace, field, value), count in cluster_counter.most_common():
        if count < cluster_min or len(clusters) >= limit:
            continue
        clusters.append(
            {
                "namespace": namespace,
                "field": field,
                "value": _redact_value(field, value, include_sensitive),
                "location_count": count,
                "sample_paths": sorted(cluster_paths[(namespace, field, value)])[:5],
            }
        )

    high_value = []
    for row in rows:
        if len(high_value) >= limit:
            break
        if not HIGH_VALUE_FIELD_RE.search(row["field_name"]):
            continue
        high_value.append(
            {
                "path": row["relative_path"],
                "canonical_ref": row["canonical_ref"],
                "namespace": row["namespace"],
                "field": row["field_name"],
                "value": _redact_value(
                    row["field_name"], row["raw_value"] or "", include_sensitive
                ),
                "provenance_layer": row["provenance_layer"],
            }
        )

    sidecar_inventory = {
        row["raw_value"].lower(): row["location_count"]
        for row in db.execute(
            """
            SELECT m.raw_value, COUNT(DISTINCT m.location_id) AS location_count
            FROM artifact_metadata_observation m
            WHERE m.namespace='mail_sidecar.inventory'
              AND m.field_name='exact_eml_companion_present'
            GROUP BY m.raw_value
            """
        )
    }
    sidecar_gap_samples = [
        row["relative_path"]
        for row in db.execute(
            """
            SELECT l.relative_path
            FROM artifact_metadata_observation m
            JOIN artifact_location l ON l.location_id=m.location_id
            WHERE m.namespace='mail_sidecar.inventory'
              AND m.field_name='exact_eml_companion_present'
              AND lower(m.raw_value)='false'
            ORDER BY l.relative_path
            LIMIT ?
            """,
            (min(limit, 20),),
        )
    ]
    generic_only = [
        row["relative_path"]
        for row in db.execute(
            """
            SELECT l.relative_path
            FROM artifact_location l
            LEFT JOIN artifact_metadata_observation m ON m.location_id=l.location_id
            GROUP BY l.location_id
            HAVING SUM(
                CASE WHEN m.namespace NOT IN ('filesystem', 'scan') THEN 1 ELSE 0 END
            )=0
            ORDER BY l.relative_path
            LIMIT ?
            """,
            (min(limit, 20),),
        )
    ]

    fingerprint_rows = db.execute(
        """
        SELECT m.namespace, m.field_name, m.raw_value,
               COUNT(DISTINCT m.artifact_id) AS unique_artifact_count,
               COUNT(DISTINCT m.location_id) AS location_count,
               json_group_array(DISTINCT l.relative_path) AS paths
        FROM artifact_metadata_observation m
        JOIN artifact_location l ON l.location_id=m.location_id
        WHERE lower(m.field_name) IN (
            'author', 'creator', 'producer', 'company', 'application',
            'lastmodifiedby', 'x-mailer', 'path'
        )
          AND COALESCE(m.raw_value, '') <> ''
        GROUP BY m.namespace, m.field_name, m.raw_value
        ORDER BY location_count DESC, m.namespace, m.field_name, m.raw_value
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    fingerprints = [
        {
            "namespace": row["namespace"],
            "field": row["field_name"],
            "value": _redact_value(
                row["field_name"], row["raw_value"], include_sensitive
            ),
            "unique_artifact_count": row["unique_artifact_count"],
            "location_count": row["location_count"],
            "sample_paths": json.loads(row["paths"])[:5],
        }
        for row in fingerprint_rows
    ]

    result = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "reference_date": reference_date,
        "interpretation_warning": (
            "Dates are grouped by provenance layer. A post-reference release, "
            "container, production, or acquisition timestamp is not a source-event date."
        ),
        "stats": build_stats(db_path),
        "post_reference_dates": dict(post_reference),
        "duplicate_content": duplicate_groups,
        "repeated_metadata_clusters": clusters,
        "metadata_fingerprints": fingerprints,
        "coverage_gaps": {
            "mail_sidecars_scanned": sum(sidecar_inventory.values()),
            "mail_sidecars_without_exact_eml_companion": sidecar_inventory.get(
                "false", 0
            ),
            "mail_sidecars_without_exact_eml_companion_samples": sidecar_gap_samples,
            "generic_metadata_only_sample": generic_only,
            "exiftool_available": bool(shutil.which("exiftool")),
            "exiftool_note": (
                "ExifTool is optional but required for the broadest EXIF/IPTC/XMP and "
                "device-metadata coverage."
            ),
        },
        "high_value_observations": high_value,
    }
    db.close()
    _log_local_query(
        f"report reference_date={reference_date} cluster_min={cluster_min}",
        sum(len(items) for items in post_reference.values()) + len(duplicate_groups),
    )
    return result


def show_artifact(
    db_path: Path,
    selector: str,
    *,
    include_sensitive: bool,
) -> dict[str, Any] | None:
    db = get_db(db_path)
    init_schema(db)
    selector_upper = selector.upper()
    rows = db.execute(
        """
        SELECT l.*, a.sha256, a.byte_length, a.media_type, a.file_extension
        FROM artifact_location l
        JOIN artifact_file a ON a.artifact_id=l.artifact_id
        WHERE l.relative_path=? OR a.sha256=? OR l.canonical_ref=?
           OR a.sha256 LIKE ?
        ORDER BY l.relative_path
        """,
        (selector, selector.lower(), selector_upper, f"{selector.lower()}%"),
    ).fetchall()
    if not rows:
        db.close()
        _log_local_query(f"show {selector}", 0)
        return None
    locations = []
    for row in rows:
        item = dict(row)
        observations = []
        for observation in db.execute(
            """
            SELECT namespace, field_name, occurrence, raw_value, normalized_value,
                   value_type, provenance_layer, extractor, extractor_version
            FROM artifact_metadata_observation
            WHERE location_id=?
            ORDER BY namespace, field_name, occurrence
            """,
            (row["location_id"],),
        ):
            value = dict(observation)
            value["raw_value"] = _redact_value(
                value["field_name"], value["raw_value"] or "", include_sensitive
            )
            observations.append(value)
        item["observations"] = observations
        locations.append(item)
    db.close()
    _log_local_query(f"show {selector}", len(locations))
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "selector": selector,
        "locations": locations,
    }


def _log_local_query(query: str, result_count: int) -> None:
    if log_search is None:
        return
    try:
        log_search(query, "epstein_metadata", result_count)
    except (OSError, sqlite3.Error) as exc:
        print(f"warning: could not log metadata query: {exc}", file=sys.stderr)


def _extensions_arg(value: str | None) -> set[str] | None:
    if not value:
        return None
    result = set()
    for item in value.split(","):
        item = item.strip().lower()
        if not item:
            continue
        result.add(item if item.startswith(".") else f".{item}")
    return result


def _emit(data: Any, args: argparse.Namespace, summary: str, result_count: int) -> None:
    if write_output(data, args, summary=summary, result_count=result_count):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=DERIVED_DB,
        help=f"Derived sidecar path (default: {DERIVED_DB})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pilot = subparsers.add_parser("pilot", help="scan a deterministic stratified local sample")
    pilot.add_argument("--max-files", type=int, default=500)
    pilot.add_argument("--max-extract-bytes", type=int, default=DEFAULT_MAX_EXTRACT_BYTES)
    add_output_args(pilot)

    scan = subparsers.add_parser("scan", help="scan explicit local files or directories")
    scan.add_argument("paths", nargs="+", type=Path)
    scan.add_argument("--collection", default="manual_scan")
    scan.add_argument("--extensions", help="comma-separated extension allowlist")
    scan.add_argument("--limit", type=int)
    scan.add_argument("--max-extract-bytes", type=int, default=DEFAULT_MAX_EXTRACT_BYTES)
    add_output_args(scan)

    report = subparsers.add_parser("report", help="rank metadata anomalies and clusters")
    report.add_argument("--reference-date", default="2019-07-06")
    report.add_argument("--limit", type=int, default=100)
    report.add_argument("--cluster-min", type=int, default=3)
    report.add_argument("--include-sensitive", action="store_true")
    add_output_args(report)

    show = subparsers.add_parser("show", help="show one path, EFTA ref, or SHA-256")
    show.add_argument("selector")
    show.add_argument("--include-sensitive", action="store_true")
    add_output_args(show)

    stats = subparsers.add_parser("stats", help="metadata inventory counts")
    add_output_args(stats)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "pilot":
        if args.max_files <= 0:
            parser.error("--max-files must be positive")
        files = _pilot_files(args.max_files)
        result = scan_files(
            args.db,
            files,
            note=f"stratified local pilot; requested_max_files={args.max_files}",
            max_extract_bytes=args.max_extract_bytes,
        )
        _emit(result, args, "Epstein metadata pilot", result["scanned"])
    elif args.command == "scan":
        extensions = _extensions_arg(args.extensions)
        paths = _supported_files(args.paths, extensions)
        if args.limit is not None:
            if args.limit <= 0:
                parser.error("--limit must be positive")
            paths = _even_sample(paths, args.limit)
        files = [(path, args.collection) for path in paths]
        result = scan_files(
            args.db,
            files,
            note=f"manual scan collection={args.collection}",
            max_extract_bytes=args.max_extract_bytes,
        )
        _emit(result, args, f"Epstein metadata scan '{args.collection}'", result["scanned"])
    elif args.command == "report":
        result = build_report(
            args.db,
            reference_date=args.reference_date,
            limit=args.limit,
            cluster_min=args.cluster_min,
            include_sensitive=args.include_sensitive,
        )
        count = sum(len(items) for items in result["post_reference_dates"].values())
        count += len(result["duplicate_content"])
        _emit(result, args, "Epstein metadata anomaly report", count)
    elif args.command == "show":
        result = show_artifact(
            args.db,
            args.selector,
            include_sensitive=args.include_sensitive,
        )
        if result is None:
            print(f"No metadata artifact matched: {args.selector}", file=sys.stderr)
            raise SystemExit(1)
        _emit(result, args, f"Epstein metadata '{args.selector}'", len(result["locations"]))
    elif args.command == "stats":
        result = build_stats(args.db)
        _emit(result, args, "Epstein metadata stats", result["locations"])


if __name__ == "__main__":
    main()
