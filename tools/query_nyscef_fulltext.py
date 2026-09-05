#!/usr/bin/env python3
"""Build and search a case-scoped full-text corpus of NYSCEF filings.

This adapter begins with a NYSCEF document-list manifest and PDF files already
acquired through the source route selected by the public-record catalog. It
normalizes document identity, extracts page text, optionally OCRs image-only
pages, and stores the result in a portable SQLite FTS5 index.

Examples:
    uv run python tools/query_nyscef_fulltext.py sources --output sources.json
    uv run python tools/query_nyscef_fulltext.py normalize documents.json
    uv run python tools/query_nyscef_fulltext.py extract filing.pdf \
        --case-number 156728/2019 --court "New York County Supreme Court" \
        --document-number 7 --output filing-text.json
    uv run python tools/query_nyscef_fulltext.py index documents.json \
        --pdf-dir ./filings --database ./nyscef-text.db --output index.json
    uv run python tools/query_nyscef_fulltext.py search ./nyscef-text.db \
        '"Example Holdings LLC"' --mode fts --mention-name "Example Holdings LLC"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from lead_tracker import log_search
    from output_util import add_output_args, write_output


SOURCE_ID = "us-ny-nyscef"
SOURCE_LABEL = "New York State Courts Electronic Filing (NYSCEF)"
CASE_SEARCH_URL = "https://iapps.courts.state.ny.us/nyscef/CaseSearch"
TERMS_URL = "https://iappscontent.courts.state.ny.us/NYSCEF/live/termsOfUse.htm"
FAQ_URL = "https://iappscontent.courts.state.ny.us/nyscef/live/faq.htm"
COURT_RECORDS_HELP_URL = (
    "https://www.nycourts.gov/help/representing-yourself-court/"
    "getting-court-records-case-information"
)

SCHEMA_VERSION = 1
PAGE_BREAK = "\n--- PAGE BREAK ---\n"
LOCAL_PATH_FIELDS = (
    "local_path",
    "file_path",
    "pdf_path",
    "downloaded_path",
    "output_file",
)

SOURCE_INVENTORY = {
    "source_id": SOURCE_ID,
    "name": SOURCE_LABEL,
    "authority": "New York State Unified Court System",
    "official_urls": {
        "case_search": CASE_SEARCH_URL,
        "faq": FAQ_URL,
        "terms": TERMS_URL,
        "court_records_help": COURT_RECORDS_HELP_URL,
    },
    "capabilities": [
        "case and party discovery",
        "case-scoped document manifests",
        "available filed-document PDFs",
    ],
    "adapter_scope": [
        "normalize a supplied NYSCEF document manifest",
        "extract and OCR supplied filing PDFs",
        "build a page-level local FTS5 index",
        "search filing bodies with exact case and document provenance",
        "flag whether a searched name is listed as a case party",
    ],
    "identity": {
        "case": ["court", "raw_case_number", "docket_id"],
        "document": [
            "case_identity",
            "document_number",
            "doc_index",
            "filed_date",
        ],
        "artifact": ["pdf_sha256"],
    },
    "complementary_sources": [
        {
            "source_id": "us-ny-court-pass",
            "name": "Court-PASS",
            "value": "Court of Appeals briefs, records, appendices, and decisions",
            "official_url": "https://courtpass.nycourts.gov/",
        },
        {
            "source_id": "us-ny-law-reporting-bureau",
            "name": "New York Law Reporting Bureau",
            "value": "official opinion bodies and filing references",
            "official_url": "https://www.nycourts.gov/reporter/",
        },
        {
            "source_id": "us-ny-webcivil-supreme",
            "name": "WebCivil Supreme",
            "value": "Supreme Court case, appearance, and calendar context",
            "official_url": "https://iapps.courts.state.ny.us/webcivil/FCASMain",
        },
        {
            "source_id": "us-ny-county-clerk-court-records",
            "name": "County clerk and court-record copy routes",
            "value": "official copies for records not available from a public portal",
            "official_url": COURT_RECORDS_HELP_URL,
        },
        {
            "source_id": "us-courtlistener-api",
            "name": "CourtListener",
            "value": "opinion, citation, docket, and selected document discovery",
            "official_url": "https://www.courtlistener.com/",
        },
        {
            "source_id": "us-ny-trellis",
            "name": "Trellis",
            "value": "commercial state-trial filing-body and docket search",
            "official_url": "https://trellis.law/",
        },
        {
            "source_id": "us-ny-courtlink",
            "name": "CourtLink",
            "value": "commercial state docket and document search",
            "official_url": "https://www.lexisnexis.com/en-us/products/courtlink.page",
        },
        {
            "source_id": "us-ny-elaw",
            "name": "eLaw",
            "value": "commercial New York docket monitoring and document access",
            "official_url": "https://www.elaw.com/",
        },
    ],
}


class FullTextError(RuntimeError):
    """Raised for a source artifact or local-index contract error."""


@dataclass(frozen=True)
class ExtractionResult:
    """Page-level text and extraction diagnostics for one PDF."""

    pages: list[str]
    page_methods: list[str]
    primary_method: str
    quality: dict[str, Any]
    ocr_attempted_pages: list[int]
    ocr_used_pages: list[int]
    ocr_errors: list[dict[str, Any]]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FullTextError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FullTextError(f"Invalid JSON in {path}: {exc}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()
    return cleaned or None


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if mapping.get(key) not in (None, ""):
            return mapping[key]
    return None


def _slug(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", (value or "").casefold()).strip("-")
    return normalized or "unknown"


def _case_number_key(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "").upper())


def _normalize_date_iso(value: str | None) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _party_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    direct = payload.get("party_names")
    if isinstance(direct, list):
        names.extend(_clean(value) for value in direct)

    for key in (
        "plaintiffs_petitioners",
        "defendants_respondents",
        "parties",
    ):
        group = payload.get(key)
        if not isinstance(group, list):
            continue
        for item in group:
            if isinstance(item, dict):
                names.append(_clean(_first(item, "name", "party_name", "label")))
            else:
                names.append(_clean(item))

    return sorted({name for name in names if name}, key=str.casefold)


def _case_identity(
    *,
    court: str | None,
    case_number: str | None,
    docket_id: str | None,
) -> str:
    case_key = _case_number_key(case_number)
    if case_key:
        return f"NYSCEF-CASE:{_slug(court)}:{case_key}"
    if docket_id:
        return f"NYSCEF-CASE:DOCKET:{docket_id}"
    raise FullTextError(
        "A NYSCEF document needs case_number + court, or a docket_id, "
        "to preserve case identity."
    )


def _document_identity(
    *,
    case_identity: str,
    document_number: str | None,
    doc_index: str | None,
    source_url: str | None,
) -> str:
    if document_number:
        return f"NYSCEF-DOC:{case_identity}:{document_number}"
    if doc_index:
        return f"NYSCEF-DOC:{case_identity}:INDEX:{doc_index}"
    if source_url:
        return (
            f"NYSCEF-DOC:{case_identity}:URL:"
            f"{hashlib.sha256(source_url.encode()).hexdigest()[:20]}"
        )
    raise FullTextError(
        "A NYSCEF document needs document_number, doc_index, or source_url "
        "to preserve document identity."
    )


def _document_url(record: dict[str, Any]) -> str | None:
    direct = _clean(
        _first(
            record,
            "document_url",
            "source_url",
            "url",
            "download_url",
        )
    )
    if direct:
        return direct
    doc_index = _clean(record.get("doc_index"))
    if doc_index:
        from urllib.parse import quote

        return (
            "https://iapps.courts.state.ny.us/nyscef/ViewDocument"
            f"?docIndex={quote(doc_index, safe='')}"
        )
    return None


def _normalize_record(
    raw: dict[str, Any],
    defaults: dict[str, Any],
    manifest_sha256: str,
) -> dict[str, Any]:
    merged = {**defaults, **raw}
    court = _clean(_first(merged, "court", "court_name"))
    county = _clean(_first(merged, "county", "county_name"))
    case_number = _clean(
        _first(merged, "case_number", "raw_case_number", "index_number")
    )
    docket_id = _clean(_first(merged, "docket_id", "source_docket_id"))
    document_number = _clean(
        _first(
            merged,
            "document_number",
            "document_no",
            "doc_number",
            "sequence_number",
        )
    )
    doc_index = _clean(
        _first(merged, "doc_index", "document_index", "source_document_id")
    )
    source_url = _document_url(merged)
    case_identity = _case_identity(
        court=court,
        case_number=case_number,
        docket_id=docket_id,
    )
    record_identity = _document_identity(
        case_identity=case_identity,
        document_number=document_number,
        doc_index=doc_index,
        source_url=source_url,
    )
    listed_parties = sorted(
        {
            *_party_names(defaults),
            *_party_names(raw),
        },
        key=str.casefold,
    )

    local_path = _clean(_first(merged, *LOCAL_PATH_FIELDS))
    return {
        "source_id": SOURCE_ID,
        "case_identity": case_identity,
        "record_identity": record_identity,
        "case_number": case_number,
        "docket_id": docket_id,
        "court": court,
        "county": county,
        "caption": _clean(
            _first(merged, "short_caption", "caption", "case_caption")
        ),
        "document_number": document_number,
        "doc_index": doc_index,
        "document_type": _clean(
            _first(merged, "document_type", "type", "title")
        ),
        "description": _clean(merged.get("description")),
        "filed_by": _clean(_first(merged, "filed_by", "filer")),
        "filed_date": _clean(_first(merged, "filed_date", "date_filed")),
        "filed_date_iso": _normalize_date_iso(
            _first(merged, "filed_date", "date_filed")
        ),
        "received_date": _clean(merged.get("received_date")),
        "status": _clean(merged.get("status")),
        "source_url": source_url,
        "confirmation_url": _clean(merged.get("confirmation_url")),
        "local_path": local_path,
        "listed_parties": listed_parties,
        "manifest_sha256": manifest_sha256,
        "raw_record": raw,
    }


def normalize_manifest(payload: Any) -> dict[str, Any]:
    """Normalize a query_nyscef document response or a compatible row list."""
    manifest_sha256 = _sha256_json(payload)
    if isinstance(payload, list):
        raw_documents = payload
        defaults: dict[str, Any] = {}
    elif isinstance(payload, dict):
        raw_documents = payload.get("documents")
        if raw_documents is None:
            raw_documents = payload.get("records")
        defaults = {
            key: value
            for key, value in payload.items()
            if key not in {"documents", "records"}
        }
    else:
        raise FullTextError("Manifest must be a JSON object or list.")

    if not isinstance(raw_documents, list):
        status = payload.get("status") if isinstance(payload, dict) else None
        if status == "human_required":
            raise FullTextError(
                "The supplied artifact is a search handoff, not a document "
                "manifest. Add the case document-list result after acquisition."
            )
        raise FullTextError("Manifest does not contain a documents or records list.")

    records = []
    failures = []
    for ordinal, raw in enumerate(raw_documents, start=1):
        if not isinstance(raw, dict):
            failures.append(
                {
                    "ordinal": ordinal,
                    "error": "document row is not an object",
                }
            )
            continue
        try:
            record = _normalize_record(raw, defaults, manifest_sha256)
            record["manifest_ordinal"] = ordinal
            records.append(record)
        except FullTextError as exc:
            failures.append({"ordinal": ordinal, "error": str(exc)})

    return {
        "source_id": SOURCE_ID,
        "manifest_sha256": manifest_sha256,
        "record_count": len(records),
        "failure_count": len(failures),
        "records": records,
        "failures": failures,
    }


def _load_file_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    payload = _load_json(path)
    if isinstance(payload, dict):
        if isinstance(payload.get("files"), dict):
            payload = payload["files"]
        return {
            str(key): str(value)
            for key, value in payload.items()
            if value not in (None, "")
        }
    if isinstance(payload, list):
        result = {}
        for row in payload:
            if not isinstance(row, dict):
                continue
            file_path = _first(row, *LOCAL_PATH_FIELDS)
            if not file_path:
                continue
            for key in (
                "record_identity",
                "doc_index",
                "document_number",
                "source_url",
            ):
                if row.get(key):
                    result[str(row[key])] = str(file_path)
        return result
    raise FullTextError("File map must be a JSON object or list.")


def _safe_doc_index(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def _mapped_path(record: dict[str, Any], file_map: dict[str, str]) -> str | None:
    for key in (
        record.get("record_identity"),
        record.get("doc_index"),
        record.get("document_number"),
        record.get("source_url"),
    ):
        if key and str(key) in file_map:
            return file_map[str(key)]
    return None


def resolve_pdf_path(
    record: dict[str, Any],
    *,
    manifest_dir: Path,
    pdf_dir: Path | None,
    file_map: dict[str, str],
) -> Path | None:
    """Resolve one manifest row to an unambiguous local PDF."""
    explicit = _mapped_path(record, file_map) or record.get("local_path")
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_absolute():
            bases = [manifest_dir]
            if pdf_dir:
                bases.insert(0, pdf_dir)
            found = [
                (base / candidate).resolve()
                for base in bases
                if (base / candidate).is_file()
            ]
            if len({str(item) for item in found}) == 1:
                return found[0]
            if len(found) > 1:
                raise FullTextError(
                    f"Ambiguous relative PDF path for {record['record_identity']}: "
                    f"{explicit}"
                )
            return None
        return candidate.resolve() if candidate.is_file() else None

    if not pdf_dir:
        return None

    stems: list[str] = []
    document_number = record.get("document_number")
    if document_number:
        stems.extend(
            [
                str(document_number),
                f"doc-{document_number}",
                f"document-{document_number}",
            ]
        )
    doc_index = record.get("doc_index")
    if doc_index:
        stems.append(_safe_doc_index(doc_index))
    source_url = record.get("source_url")
    if source_url:
        basename = unquote(Path(urlparse(source_url).path).name)
        if basename.casefold().endswith(".pdf"):
            stems.append(Path(basename).stem)

    found = []
    for stem in dict.fromkeys(stems):
        candidate = (pdf_dir / f"{stem}.pdf").resolve()
        if candidate.is_file():
            found.append(candidate)

    unique = {str(item): item for item in found}
    if len(unique) > 1:
        raise FullTextError(
            f"Multiple PDF candidates match {record['record_identity']}; "
            "provide --file-map."
        )
    return next(iter(unique.values()), None)


def _run_command(command: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise FullTextError(f"Required command is unavailable: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise FullTextError(f"Command timed out: {command[0]}") from exc


def _extract_pdftotext_pages(pdf_path: Path) -> list[str]:
    executable = shutil.which("pdftotext")
    if not executable:
        raise FullTextError("pdftotext is not installed or not on PATH.")
    completed = _run_command(
        [executable, "-layout", str(pdf_path.resolve()), "-"],
        timeout=300,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise FullTextError(
            f"pdftotext failed for {pdf_path.name}: "
            f"{detail or completed.returncode}"
        )
    raw = completed.stdout.decode("utf-8", errors="replace")
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages or [""]


def _text_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def extraction_quality(pages: list[str]) -> dict[str, Any]:
    chars_per_page = [_text_chars(page) for page in pages]
    page_count = len(pages)
    total_chars = sum(chars_per_page)
    substantive_pages = sum(chars >= 300 for chars in chars_per_page)
    low_text_pages = [
        number
        for number, chars in enumerate(chars_per_page, start=1)
        if chars < 80
    ]
    needs_ocr = (
        total_chars < 100
        or (
            page_count >= 3
            and (
                total_chars / page_count < 200
                or substantive_pages / page_count < 0.25
            )
        )
        or bool(low_text_pages)
    )
    return {
        "page_count": page_count,
        "text_chars": total_chars,
        "chars_per_page": chars_per_page,
        "substantive_pages": substantive_pages,
        "low_text_pages": low_text_pages,
        "needs_ocr": needs_ocr,
    }


def _ocr_dependencies() -> dict[str, str | None]:
    return {
        "pdftocairo": shutil.which("pdftocairo"),
        "tesseract": shutil.which("tesseract"),
    }


def _ocr_page(
    pdf_path: Path,
    page_number: int,
    *,
    dpi: int,
    language: str,
) -> str:
    dependencies = _ocr_dependencies()
    renderer = dependencies["pdftocairo"]
    tesseract = dependencies["tesseract"]
    missing = [name for name, value in dependencies.items() if not value]
    if missing:
        raise FullTextError(
            "OCR dependencies unavailable: " + ", ".join(sorted(missing))
        )

    with tempfile.TemporaryDirectory(prefix="nyscef-ocr-") as directory:
        prefix = Path(directory) / "page"
        rendered = _run_command(
            [
                str(renderer),
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-singlefile",
                "-png",
                "-r",
                str(dpi),
                str(pdf_path.resolve()),
                str(prefix),
            ],
            timeout=300,
        )
        if rendered.returncode != 0:
            detail = rendered.stderr.decode("utf-8", errors="replace").strip()
            raise FullTextError(
                f"pdftocairo failed on page {page_number}: "
                f"{detail or rendered.returncode}"
            )

        image_path = prefix.with_suffix(".png")
        if not image_path.is_file() or image_path.stat().st_size == 0:
            raise FullTextError(
                f"pdftocairo produced no image for page {page_number}."
            )
        recognized = _run_command(
            [
                str(tesseract),
                str(image_path),
                "stdout",
                "-l",
                language,
                "--dpi",
                str(dpi),
            ],
            timeout=300,
        )
        if recognized.returncode != 0:
            detail = recognized.stderr.decode("utf-8", errors="replace").strip()
            raise FullTextError(
                f"tesseract failed on page {page_number}: "
                f"{detail or recognized.returncode}"
            )
        return recognized.stdout.decode("utf-8", errors="replace")


def extract_pdf(
    pdf_path: str | Path,
    *,
    ocr_mode: str = "auto",
    ocr_language: str = "eng",
    ocr_dpi: int = 200,
) -> ExtractionResult:
    """Extract text and optionally OCR weak pages from one PDF."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FullTextError(f"PDF file not found: {pdf_path}")
    if path.suffix.casefold() != ".pdf":
        raise FullTextError(f"Expected a PDF file: {pdf_path}")

    pages = _extract_pdftotext_pages(path)
    methods = ["pdftotext-layout"] * len(pages)
    initial_quality = extraction_quality(pages)

    if ocr_mode == "always":
        candidate_pages = list(range(1, len(pages) + 1))
    elif ocr_mode == "auto" and initial_quality["needs_ocr"]:
        candidate_pages = initial_quality["low_text_pages"]
        if not candidate_pages:
            candidate_pages = list(range(1, len(pages) + 1))
    else:
        candidate_pages = []

    attempted = []
    used = []
    errors = []
    for page_number in candidate_pages:
        attempted.append(page_number)
        try:
            ocr_text = _ocr_page(
                path,
                page_number,
                dpi=ocr_dpi,
                language=ocr_language,
            )
        except FullTextError as exc:
            errors.append({"page_number": page_number, "error": str(exc)})
            continue

        existing = pages[page_number - 1]
        if ocr_mode == "always" or _text_chars(ocr_text) > _text_chars(existing):
            pages[page_number - 1] = ocr_text
            methods[page_number - 1] = "tesseract-ocr"
            used.append(page_number)

    quality = extraction_quality(pages)
    quality["initial_needs_ocr"] = initial_quality["needs_ocr"]
    quality["ocr_available"] = all(_ocr_dependencies().values())
    primary_method = (
        "pdftotext-layout+tesseract-ocr" if used else "pdftotext-layout"
    )
    return ExtractionResult(
        pages=pages,
        page_methods=methods,
        primary_method=primary_method,
        quality=quality,
        ocr_attempted_pages=attempted,
        ocr_used_pages=used,
        ocr_errors=errors,
    )


def _database_connection(path: str | Path) -> sqlite3.Connection:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS corpus_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            source_id TEXT NOT NULL,
            case_identity TEXT NOT NULL,
            record_identity TEXT NOT NULL,
            artifact_identity TEXT NOT NULL,
            case_number TEXT,
            docket_id TEXT,
            court TEXT,
            county TEXT,
            caption TEXT,
            document_number TEXT,
            doc_index TEXT,
            document_type TEXT,
            description TEXT,
            filed_by TEXT,
            filed_date TEXT,
            filed_date_iso TEXT,
            received_date TEXT,
            status TEXT,
            source_url TEXT,
            confirmation_url TEXT,
            local_path TEXT NOT NULL,
            pdf_sha256 TEXT NOT NULL,
            byte_size INTEGER NOT NULL,
            page_count INTEGER NOT NULL,
            extraction_method TEXT NOT NULL,
            text_chars INTEGER NOT NULL,
            needs_ocr INTEGER NOT NULL,
            ocr_attempted_pages_json TEXT NOT NULL,
            ocr_used_pages_json TEXT NOT NULL,
            ocr_errors_json TEXT NOT NULL,
            listed_parties_json TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            manifest_path TEXT,
            indexed_at TEXT NOT NULL,
            UNIQUE(record_identity, pdf_sha256)
        );

        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY,
            document_id INTEGER NOT NULL
                REFERENCES documents(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            text TEXT NOT NULL,
            extraction_method TEXT NOT NULL,
            text_chars INTEGER NOT NULL,
            UNIQUE(document_id, page_number)
        );

        CREATE INDEX IF NOT EXISTS documents_case_idx
            ON documents(case_identity);
        CREATE INDEX IF NOT EXISTS documents_case_number_idx
            ON documents(case_number);
        CREATE INDEX IF NOT EXISTS documents_filed_date_idx
            ON documents(filed_date_iso);
        CREATE INDEX IF NOT EXISTS pages_document_idx
            ON pages(document_id, page_number);

        CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
            text,
            content='pages',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        );

        CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO pages_fts(rowid, text) VALUES (new.id, new.text);
        END;
        CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
        END;
        CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
            INSERT INTO pages_fts(rowid, text) VALUES (new.id, new.text);
        END;
        """
    )
    connection.execute(
        """
        INSERT INTO corpus_metadata(key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(SCHEMA_VERSION),),
    )
    connection.execute(
        """
        INSERT INTO corpus_metadata(key, value)
        VALUES ('source_id', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (SOURCE_ID,),
    )
    connection.commit()
    return connection


def _store_document(
    connection: sqlite3.Connection,
    *,
    record: dict[str, Any],
    pdf_path: Path,
    extraction: ExtractionResult,
    manifest_path: str,
) -> tuple[int, bool]:
    sha256 = _sha256_file(pdf_path)
    existing = connection.execute(
        """
        SELECT id
        FROM documents
        WHERE record_identity = ? AND pdf_sha256 = ?
        """,
        (record["record_identity"], sha256),
    ).fetchone()
    if existing:
        return int(existing["id"]), False

    artifact_identity = f"NYSCEF-PDF:{sha256}"
    cursor = connection.execute(
        """
        INSERT INTO documents (
            source_id, case_identity, record_identity, artifact_identity,
            case_number, docket_id, court, county, caption,
            document_number, doc_index, document_type, description,
            filed_by, filed_date, filed_date_iso, received_date, status,
            source_url, confirmation_url, local_path, pdf_sha256, byte_size,
            page_count, extraction_method, text_chars, needs_ocr,
            ocr_attempted_pages_json, ocr_used_pages_json, ocr_errors_json,
            listed_parties_json, manifest_sha256, manifest_path, indexed_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            SOURCE_ID,
            record["case_identity"],
            record["record_identity"],
            artifact_identity,
            record.get("case_number"),
            record.get("docket_id"),
            record.get("court"),
            record.get("county"),
            record.get("caption"),
            record.get("document_number"),
            record.get("doc_index"),
            record.get("document_type"),
            record.get("description"),
            record.get("filed_by"),
            record.get("filed_date"),
            record.get("filed_date_iso"),
            record.get("received_date"),
            record.get("status"),
            record.get("source_url"),
            record.get("confirmation_url"),
            str(pdf_path.resolve()),
            sha256,
            pdf_path.stat().st_size,
            len(extraction.pages),
            extraction.primary_method,
            extraction.quality["text_chars"],
            int(extraction.quality["needs_ocr"]),
            json.dumps(extraction.ocr_attempted_pages),
            json.dumps(extraction.ocr_used_pages),
            json.dumps(extraction.ocr_errors),
            json.dumps(record.get("listed_parties", []), ensure_ascii=False),
            record["manifest_sha256"],
            str(Path(manifest_path).resolve()),
            _utc_now(),
        ),
    )
    document_id = int(cursor.lastrowid)
    connection.executemany(
        """
        INSERT INTO pages (
            document_id, page_number, text, extraction_method, text_chars
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                document_id,
                page_number,
                text,
                extraction.page_methods[page_number - 1],
                _text_chars(text),
            )
            for page_number, text in enumerate(extraction.pages, start=1)
        ],
    )
    return document_id, True


def _document_payload(
    record: dict[str, Any],
    pdf_path: Path,
    extraction: ExtractionResult,
) -> dict[str, Any]:
    sha256 = _sha256_file(pdf_path)
    return {
        "source_id": SOURCE_ID,
        "case_identity": record["case_identity"],
        "record_identity": record["record_identity"],
        "artifact_identity": f"NYSCEF-PDF:{sha256}",
        "case_number": record.get("case_number"),
        "docket_id": record.get("docket_id"),
        "court": record.get("court"),
        "county": record.get("county"),
        "caption": record.get("caption"),
        "document_number": record.get("document_number"),
        "doc_index": record.get("doc_index"),
        "document_type": record.get("document_type"),
        "filed_by": record.get("filed_by"),
        "filed_date": record.get("filed_date"),
        "filed_date_iso": record.get("filed_date_iso"),
        "source_url": record.get("source_url"),
        "local_path": str(pdf_path.resolve()),
        "pdf_sha256": sha256,
        "byte_size": pdf_path.stat().st_size,
        "page_count": len(extraction.pages),
        "extraction_method": extraction.primary_method,
        "quality": extraction.quality,
        "ocr_attempted_pages": extraction.ocr_attempted_pages,
        "ocr_used_pages": extraction.ocr_used_pages,
        "ocr_errors": extraction.ocr_errors,
        "listed_parties": record.get("listed_parties", []),
        "pages": [
            {
                "page_number": page_number,
                "text": text,
                "text_chars": _text_chars(text),
                "extraction_method": extraction.page_methods[page_number - 1],
                "evidence_reference": (
                    f"{record['record_identity']}:p{page_number}"
                ),
            }
            for page_number, text in enumerate(extraction.pages, start=1)
        ],
    }


def _record_from_extract_args(args: argparse.Namespace) -> dict[str, Any]:
    raw = {
        "case_number": args.case_number,
        "docket_id": args.docket_id,
        "court": args.court,
        "county": args.county,
        "short_caption": args.caption,
        "document_number": args.document_number,
        "doc_index": args.doc_index,
        "document_type": args.document_type,
        "filed_by": args.filed_by,
        "filed_date": args.filed_date,
        "document_url": args.source_url,
        "party_names": args.party_name or [],
        "local_path": str(Path(args.pdf).resolve()),
    }
    return _normalize_record(raw, {}, _sha256_json(raw))


def _fts_query(query: str, mode: str) -> str:
    if mode == "fts":
        return query
    if mode == "phrase":
        return f'"{query.replace(chr(34), chr(34) * 2)}"'
    tokens = re.findall(r"[\w'-]+", query, flags=re.UNICODE)
    if not tokens:
        raise FullTextError("Search query contains no searchable tokens.")
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def _mention_classification(
    mention_name: str | None,
    listed_parties_json: str,
) -> dict[str, Any] | None:
    if not mention_name:
        return None
    parties = json.loads(listed_parties_json or "[]")
    if not parties:
        return {
            "name": mention_name,
            "classification": "party_list_unavailable",
            "matched_party": None,
        }

    needle = re.sub(r"[^a-z0-9]+", " ", mention_name.casefold()).strip()
    for party in parties:
        normalized = re.sub(r"[^a-z0-9]+", " ", party.casefold()).strip()
        if needle == normalized or needle in normalized or normalized in needle:
            return {
                "name": mention_name,
                "classification": "listed_party",
                "matched_party": party,
            }
    return {
        "name": mention_name,
        "classification": "non_party_candidate",
        "matched_party": None,
    }


def search_index(
    database: str | Path,
    query: str,
    *,
    mode: str = "phrase",
    limit: int = 50,
    case_number: str | None = None,
    county: str | None = None,
    document_type: str | None = None,
    filed_by: str | None = None,
    filed_from: str | None = None,
    filed_to: str | None = None,
    mention_name: str | None = None,
) -> dict[str, Any]:
    path = Path(database)
    if not path.is_file():
        raise FullTextError(f"Index database not found: {database}")
    fts_query = _fts_query(query, mode)
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    clauses = ["pages_fts MATCH ?"]
    parameters: list[Any] = [fts_query]

    for expression, value in (
        ("d.case_number = ?", case_number),
        ("LOWER(d.county) = LOWER(?)", county),
        ("LOWER(d.document_type) LIKE LOWER(?)", f"%{document_type}%"
         if document_type else None),
        ("LOWER(d.filed_by) LIKE LOWER(?)", f"%{filed_by}%" if filed_by else None),
        ("d.filed_date_iso >= ?", filed_from),
        ("d.filed_date_iso <= ?", filed_to),
    ):
        if value:
            clauses.append(expression)
            parameters.append(value)

    parameters.append(max(1, limit))
    sql = f"""
        SELECT
            d.*,
            p.page_number,
            p.extraction_method AS page_extraction_method,
            snippet(pages_fts, 0, '[', ']', ' … ', 30) AS snippet,
            bm25(pages_fts) AS rank
        FROM pages_fts
        JOIN pages AS p ON p.id = pages_fts.rowid
        JOIN documents AS d ON d.id = p.document_id
        WHERE {' AND '.join(clauses)}
        ORDER BY rank, d.filed_date_iso, d.document_number, p.page_number
        LIMIT ?
    """
    try:
        rows = connection.execute(sql, parameters).fetchall()
    except sqlite3.OperationalError as exc:
        raise FullTextError(f"Invalid FTS query: {exc}") from exc
    finally:
        connection.close()

    results = []
    for row in rows:
        item = dict(row)
        item["needs_ocr"] = bool(item["needs_ocr"])
        item["listed_parties"] = json.loads(item.pop("listed_parties_json"))
        item["ocr_attempted_pages"] = json.loads(
            item.pop("ocr_attempted_pages_json")
        )
        item["ocr_used_pages"] = json.loads(item.pop("ocr_used_pages_json"))
        item["ocr_errors"] = json.loads(item.pop("ocr_errors_json"))
        item["evidence_reference"] = (
            f"{item['record_identity']}:p{item['page_number']}"
        )
        classification = _mention_classification(
            mention_name,
            json.dumps(item["listed_parties"]),
        )
        if classification:
            item["mention_check"] = classification
        results.append(item)

    return {
        "source_id": SOURCE_ID,
        "database": str(path.resolve()),
        "query": query,
        "fts_query": fts_query,
        "mode": mode,
        "result_count": len(results),
        "results": results,
    }


def cmd_sources(args: argparse.Namespace) -> None:
    result = {
        **SOURCE_INVENTORY,
        "generated_at": _utc_now(),
        "local_dependencies": {
            "pdftotext": shutil.which("pdftotext"),
            **_ocr_dependencies(),
            "sqlite_fts5": sqlite3.connect(":memory:")
            .execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')")
            .fetchone()[0]
            == 1,
        },
    }
    if write_output(result, args, summary="NYSCEF full-text source inventory"):
        return
    print(json.dumps(result, indent=2))


def cmd_probe(args: argparse.Namespace) -> None:
    dependencies = {
        "pdftotext": shutil.which("pdftotext"),
        **_ocr_dependencies(),
    }
    try:
        try:
            from tools.query_nyscef import _access_decision
        except ImportError:
            from query_nyscef import _access_decision

        decision = _access_decision(args.catalog_db)
    except Exception as exc:
        decision = {
            "allowed": None,
            "reason_code": "catalog_check_failed",
            "reason": str(exc),
        }

    result = {
        "source_id": SOURCE_ID,
        "checked_at": _utc_now(),
        "official_case_search": CASE_SEARCH_URL,
        "catalog_decision": decision,
        "local_processing": {
            "pdf_text_extraction_ready": bool(dependencies["pdftotext"]),
            "ocr_ready": bool(
                dependencies["pdftocairo"] and dependencies["tesseract"]
            ),
            "dependencies": dependencies,
            "sqlite_fts5": sqlite3.connect(":memory:")
            .execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')")
            .fetchone()[0]
            == 1,
        },
    }
    if write_output(result, args, summary="NYSCEF full-text processing probe"):
        return
    print(json.dumps(result, indent=2))


def cmd_normalize(args: argparse.Namespace) -> None:
    normalized = normalize_manifest(_load_json(args.manifest))
    normalized["manifest_path"] = str(Path(args.manifest).resolve())
    if write_output(
        normalized,
        args,
        summary=(
            f"NYSCEF manifest normalized "
            f"({normalized['record_count']} records)"
        ),
        result_count=normalized["record_count"],
    ):
        return
    print(json.dumps(normalized, indent=2))


def cmd_extract(args: argparse.Namespace) -> None:
    record = _record_from_extract_args(args)
    pdf_path = Path(args.pdf)
    extraction = extract_pdf(
        pdf_path,
        ocr_mode=args.ocr,
        ocr_language=args.ocr_language,
        ocr_dpi=args.ocr_dpi,
    )
    result = _document_payload(record, pdf_path, extraction)
    if args.text_output:
        text_path = Path(args.text_output)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(
            PAGE_BREAK.join(page.rstrip() for page in extraction.pages).rstrip()
            + "\n",
            encoding="utf-8",
        )
        result["text_output"] = str(text_path.resolve())

    if write_output(
        result,
        args,
        summary=(
            f"NYSCEF filing extracted "
            f"({result['page_count']} pages, {result['quality']['text_chars']} chars)"
        ),
        result_count=result["page_count"],
    ):
        return
    print(json.dumps(result, indent=2))


def cmd_index(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    normalized = normalize_manifest(_load_json(manifest_path))
    file_map = _load_file_map(args.file_map)
    pdf_dir = Path(args.pdf_dir).resolve() if args.pdf_dir else None
    connection = _database_connection(args.database)
    indexed = []
    already_indexed = []
    missing = []
    failures = list(normalized["failures"])

    try:
        for record in normalized["records"]:
            try:
                pdf_path = resolve_pdf_path(
                    record,
                    manifest_dir=manifest_path.resolve().parent,
                    pdf_dir=pdf_dir,
                    file_map=file_map,
                )
                if not pdf_path:
                    missing.append(
                        {
                            "record_identity": record["record_identity"],
                            "document_number": record.get("document_number"),
                            "doc_index": record.get("doc_index"),
                            "source_url": record.get("source_url"),
                        }
                    )
                    continue
                extraction = extract_pdf(
                    pdf_path,
                    ocr_mode=args.ocr,
                    ocr_language=args.ocr_language,
                    ocr_dpi=args.ocr_dpi,
                )
                document_id, created = _store_document(
                    connection,
                    record=record,
                    pdf_path=pdf_path,
                    extraction=extraction,
                    manifest_path=str(manifest_path),
                )
                target = {
                    "document_id": document_id,
                    "record_identity": record["record_identity"],
                    "local_path": str(pdf_path),
                    "page_count": len(extraction.pages),
                    "text_chars": extraction.quality["text_chars"],
                    "needs_ocr": extraction.quality["needs_ocr"],
                    "ocr_used_pages": extraction.ocr_used_pages,
                }
                (indexed if created else already_indexed).append(target)
            except Exception as exc:
                failures.append(
                    {
                        "record_identity": record.get("record_identity"),
                        "error": str(exc),
                    }
                )
        connection.commit()
    finally:
        connection.close()

    result = {
        "source_id": SOURCE_ID,
        "database": str(Path(args.database).resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": normalized["manifest_sha256"],
        "manifest_records": normalized["record_count"],
        "indexed_count": len(indexed),
        "already_indexed_count": len(already_indexed),
        "missing_count": len(missing),
        "failure_count": len(failures),
        "indexed": indexed,
        "already_indexed": already_indexed,
        "missing": missing,
        "failures": failures,
    }
    if args.require_all and (missing or failures):
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(
                json.dumps(result, indent=2),
                encoding="utf-8",
            )
        raise FullTextError(
            f"Index incomplete: {len(missing)} missing, "
            f"{len(failures)} failed."
        )

    if write_output(
        result,
        args,
        summary=(
            f"NYSCEF full-text index "
            f"({len(indexed)} new, {len(already_indexed)} existing, "
            f"{len(missing)} missing)"
        ),
        result_count=len(indexed) + len(already_indexed),
    ):
        return
    print(json.dumps(result, indent=2))


def cmd_search(args: argparse.Namespace) -> None:
    result = search_index(
        args.database,
        args.query,
        mode=args.mode,
        limit=args.limit,
        case_number=args.case_number,
        county=args.county,
        document_type=args.document_type,
        filed_by=args.filed_by,
        filed_from=args.filed_from,
        filed_to=args.filed_to,
        mention_name=args.mention_name,
    )
    log_search(args.query, "nyscef_fulltext", result["result_count"])
    if write_output(
        result,
        args,
        summary=(
            f"NYSCEF filing-body search '{args.query}' "
            f"({result['result_count']} hits)"
        ),
        result_count=result["result_count"],
    ):
        return
    print(json.dumps(result, indent=2))


def cmd_stats(args: argparse.Namespace) -> None:
    path = Path(args.database)
    if not path.is_file():
        raise FullTextError(f"Index database not found: {args.database}")
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        counts = dict(
            connection.execute(
                """
                SELECT
                    COUNT(*) AS documents,
                    COUNT(DISTINCT case_identity) AS cases,
                    COUNT(DISTINCT record_identity) AS document_records,
                    SUM(page_count) AS pages,
                    SUM(text_chars) AS text_chars,
                    SUM(needs_ocr) AS documents_needing_ocr
                FROM documents
                """
            ).fetchone()
        )
        by_court = [
            dict(row)
            for row in connection.execute(
                """
                SELECT court, county, COUNT(*) AS documents
                FROM documents
                GROUP BY court, county
                ORDER BY documents DESC, court, county
                """
            )
        ]
    finally:
        connection.close()
    result = {
        "source_id": SOURCE_ID,
        "database": str(path.resolve()),
        **counts,
        "by_court": by_court,
    }
    if write_output(result, args, summary="NYSCEF full-text index statistics"):
        return
    print(json.dumps(result, indent=2))


def _add_ocr_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ocr",
        choices=("auto", "never", "always"),
        default="auto",
        help="OCR weak pages automatically, never OCR, or OCR every page",
    )
    parser.add_argument(
        "--ocr-language",
        default="eng",
        help="Tesseract language code (default: eng)",
    )
    parser.add_argument(
        "--ocr-dpi",
        type=int,
        default=200,
        help="Rasterization resolution for OCR (default: 200)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract and search case-scoped NYSCEF filing bodies"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe the primary and complementary source routes",
    )
    add_output_args(sources)
    sources.set_defaults(func=cmd_sources)

    probe = subparsers.add_parser(
        "probe",
        help="Check the catalog route and local extraction dependencies",
    )
    probe.add_argument(
        "--catalog-db",
        help="Optional public-record catalog database path",
    )
    add_output_args(probe)
    probe.set_defaults(func=cmd_probe)

    normalize = subparsers.add_parser(
        "normalize",
        help="Normalize a supplied NYSCEF document manifest",
    )
    normalize.add_argument("manifest")
    add_output_args(normalize)
    normalize.set_defaults(func=cmd_normalize)

    extract = subparsers.add_parser(
        "extract",
        help="Extract and optionally OCR one supplied NYSCEF PDF",
    )
    extract.add_argument("pdf")
    extract.add_argument("--case-number")
    extract.add_argument("--docket-id")
    extract.add_argument("--court")
    extract.add_argument("--county")
    extract.add_argument("--caption")
    extract.add_argument("--document-number")
    extract.add_argument("--doc-index")
    extract.add_argument("--document-type")
    extract.add_argument("--filed-by")
    extract.add_argument("--filed-date")
    extract.add_argument("--source-url")
    extract.add_argument(
        "--party-name",
        action="append",
        help="Listed case party; repeat for multiple names",
    )
    extract.add_argument(
        "--text-output",
        help="Also write page-separated plain text",
    )
    _add_ocr_args(extract)
    add_output_args(extract)
    extract.set_defaults(func=cmd_extract)

    index = subparsers.add_parser(
        "index",
        help="Build or incrementally update a local filing-body index",
    )
    index.add_argument("manifest")
    index.add_argument("--database", required=True)
    index.add_argument(
        "--pdf-dir",
        help="Directory containing PDFs named by document number or file map",
    )
    index.add_argument(
        "--file-map",
        help="JSON mapping document identity/index/number/URL to a PDF path",
    )
    index.add_argument(
        "--require-all",
        action="store_true",
        help="Exit nonzero when any manifest document is missing or fails",
    )
    _add_ocr_args(index)
    add_output_args(index)
    index.set_defaults(func=cmd_index)

    search = subparsers.add_parser(
        "search",
        help="Search an existing NYSCEF filing-body index",
    )
    search.add_argument("database")
    search.add_argument("query")
    search.add_argument(
        "--mode",
        choices=("phrase", "all", "fts"),
        default="phrase",
        help="Exact phrase, all tokens, or raw SQLite FTS5 syntax",
    )
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--case-number")
    search.add_argument("--county")
    search.add_argument("--document-type")
    search.add_argument("--filed-by")
    search.add_argument("--filed-from", help="ISO date lower bound")
    search.add_argument("--filed-to", help="ISO date upper bound")
    search.add_argument(
        "--mention-name",
        help="Compare a matched name with the manifest's listed parties",
    )
    add_output_args(search)
    search.set_defaults(func=cmd_search)

    stats = subparsers.add_parser(
        "stats",
        help="Summarize a local NYSCEF filing-body index",
    )
    stats.add_argument("database")
    add_output_args(stats)
    stats.set_defaults(func=cmd_stats)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "catalog_db", None) is None and args.command == "probe":
        try:
            try:
                from tools.public_records_catalog import DEFAULT_DB_PATH
            except ImportError:
                from public_records_catalog import DEFAULT_DB_PATH

            args.catalog_db = DEFAULT_DB_PATH
        except ImportError:
            args.catalog_db = None
    try:
        args.func(args)
    except FullTextError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
