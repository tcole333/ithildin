#!/usr/bin/env python3
"""Backfill DS09 text_cache (and optional entities) in lmsband_epstein_files.db."""

from __future__ import annotations

import argparse
import csv
import gc
import html
import os
import re
import resource
import signal
import sqlite3
import subprocess
import sys
import time
import zipfile
from collections import Counter
from email.utils import getaddresses
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import fitz  # PyMuPDF
import openpyxl


DEFAULT_DB = Path("datasets/lmsband_epstein_files.db")
DEFAULT_DATASET = 9
DEFAULT_MAX_MB = 64
DEFAULT_BATCH_SIZE = 250
DEFAULT_PROGRESS_EVERY = 250
HEADER_SCAN_CHARS = 12000
DEFAULT_EXTENSIONS = "pdf,doc,docx,xls,xlsx,csv,ppt,pptx"
MAX_TEXT_CHARS = 2_000_000  # 2M char cap per file
EXTRACT_TIMEOUT_SECS = 30  # per-file extraction timeout
RSS_WARN_MB = 4096  # log warning at this RSS
RSS_STOP_MB = 6144  # graceful stop at this RSS

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
HEADER_RE = re.compile(r"^(From|To|Cc|Bcc|Reply-To):\s*(.+)$", re.IGNORECASE | re.MULTILINE)
SPACE_RE = re.compile(r"\s+")
TAG_RE = re.compile(r"<[^>]+>")
BAD_NAME_TOKENS = {
    "",
    "n/a",
    "none",
    "subject",
    "from",
    "to",
    "cc",
    "bcc",
    "unknown",
    "undisclosed-recipients",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill DS09 text cache and lightweight entities."
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dataset", type=int, default=DEFAULT_DATASET)
    parser.add_argument(
        "--extensions",
        default=DEFAULT_EXTENSIONS,
        help=f"Comma-separated extensions to process (default: {DEFAULT_EXTENSIONS})",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max files to process (0 = all)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-file-size-mb", type=int, default=DEFAULT_MAX_MB)
    parser.add_argument(
        "--retry-empty",
        action="store_true",
        help="Also retry files with text_cache rows where char_count=0.",
    )
    parser.add_argument(
        "--entities",
        action="store_true",
        help="Extract lightweight contact entities (email/domain/header names).",
    )
    parser.add_argument(
        "--sync-fts",
        action="store_true",
        help="Incrementally add newly text-indexed rows to text_fts.",
    )
    parser.add_argument("--progress-every", type=int, default=DEFAULT_PROGRESS_EVERY)
    return parser.parse_args()


def _clean_space(text: str) -> str:
    return SPACE_RE.sub(" ", text).strip()


class _ExtractionTimeout(Exception):
    pass


def _alarm_handler(signum: int, frame: object) -> None:
    raise _ExtractionTimeout()


def _get_rss_mb() -> int:
    """Current RSS in MB (macOS ru_maxrss is bytes, Linux is KB)."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage // (1024 * 1024)
    return usage // 1024


def _extract_pdf(path: Path) -> tuple[str, str]:
    try:
        doc = fitz.open(path)
    except Exception:
        return "", "pymupdf_error"
    try:
        chunks: list[str] = []
        for page in doc:
            text = page.get_text("text")
            if text:
                chunks.append(text)
        return _clean_space("\n".join(chunks)), "pymupdf"
    finally:
        doc.close()


def _extract_csv(path: Path) -> tuple[str, str]:
    rows: list[str] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(" | ".join(str(v) for v in row if v is not None))
        return _clean_space("\n".join(rows)), "csv"
    except Exception:
        return "", "csv_error"


def _extract_textutil(path: Path) -> tuple[str, str]:
    cmd = ["/usr/bin/textutil", "-stdout", "-convert", "txt", str(path)]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
    except Exception:
        return "", "textutil_error"
    text = _clean_space(out.decode("utf-8", errors="replace"))
    if not text:
        return "", "textutil_empty"
    return text, "textutil"


def _extract_strings(path: Path) -> tuple[str, str]:
    cmd = ["/usr/bin/strings", "-n", "4", str(path)]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
    except Exception:
        return "", "strings_error"
    text = _clean_space(out.decode("utf-8", errors="replace"))
    if not text:
        return "", "strings_empty"
    return text, "strings"


def _extract_xml_text(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return ""
    parts: list[str] = []
    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1] == "t" and elem.text:
            parts.append(elem.text)
    return _clean_space(" ".join(parts))


def _extract_docx(path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as zf:
            data = zf.read("word/document.xml")
        return _extract_xml_text(data), "docx_xml"
    except Exception:
        return "", "docx_error"


def _extract_pptx(path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as zf:
            slide_names = sorted(
                n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")
            )
            parts: list[str] = []
            for name in slide_names:
                parts.append(_extract_xml_text(zf.read(name)))
        return _clean_space("\n".join(parts)), "pptx_xml"
    except Exception:
        return "", "pptx_error"


def _extract_xlsx(path: Path) -> tuple[str, str]:
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return "", "xlsx_error"
    try:
        lines: list[str] = []
        for sheet in wb.worksheets:
            lines.append(f"[sheet:{sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
                if vals:
                    lines.append(" | ".join(vals))
        return _clean_space("\n".join(lines)), "xlsx_openpyxl"
    finally:
        wb.close()


def _extract_html_payload(path: Path) -> tuple[str, str]:
    try:
        raw = path.read_text("utf-8", errors="replace")
    except Exception:
        return "", "html_read_error"
    lowered = raw.lower()
    text = _clean_space(html.unescape(TAG_RE.sub(" ", raw)))
    placeholder_markers = [
        "an official website of the united states government",
        "skip to main content",
        "an error occurred while processing your request",
        "errors.edgesuite.net",
    ]
    if any(marker in lowered for marker in placeholder_markers):
        return "", "html_placeholder"
    if text:
        return text, "html_payload"
    return "", "html_empty"


def _extract_text_inner(path: Path, ext: str, max_bytes: int) -> tuple[str, str]:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return "", "missing_file"

    if size == 0:
        return "", "zero_byte"
    if size > max_bytes:
        return "", "too_large"

    head = b""
    try:
        with path.open("rb") as f:
            head = f.read(4096)
    except Exception:
        return "", "read_error"

    head_l = head.lstrip().lower()
    if head_l.startswith(b"<!doctype html") or head_l.startswith(b"<html"):
        return _extract_html_payload(path)

    if ext == "pdf":
        return _extract_pdf(path)
    if ext == "csv":
        text, method = _extract_csv(path)
        if text:
            return text, method
        return _extract_textutil(path)
    if ext == "docx":
        text, method = _extract_docx(path)
        if text:
            return text, method
        text, method = _extract_textutil(path)
        if text:
            return text, f"docx_{method}"
        return "", "docx_error"
    if ext == "pptx":
        text, method = _extract_pptx(path)
        if text:
            return text, method
        text, method = _extract_textutil(path)
        if text:
            return text, f"pptx_{method}"
        return "", "pptx_error"
    if ext == "xlsx":
        text, method = _extract_xlsx(path)
        if text:
            return text, method
        text, method = _extract_textutil(path)
        if text:
            return text, f"xlsx_{method}"
        return "", "xlsx_error"
    if ext in {"doc", "ppt", "xls"}:
        text, method = _extract_textutil(path)
        if text:
            return text, f"{ext}_{method}"
        text, method = _extract_strings(path)
        if text:
            return text, f"{ext}_{method}"
        return "", f"{ext}_unreadable"
    return "", "unsupported_extension"


def extract_text(path: Path, ext: str, max_bytes: int) -> tuple[str, str]:
    """Extract text with per-file timeout and text length cap."""
    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(EXTRACT_TIMEOUT_SECS)
    try:
        text, method = _extract_text_inner(path, ext, max_bytes)
    except _ExtractionTimeout:
        return "", "timeout"
    except Exception:
        return "", "unexpected_error"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    # Cap text length to prevent memory blowup
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]

    return text, method


def _normalize_name(name: str) -> str:
    cleaned = _clean_space(
        name.replace("<", " ").replace(">", " ").replace('"', " ").replace("'", " ")
    )
    cleaned = cleaned.strip(" ,;:")
    if not cleaned:
        return ""
    low = cleaned.lower()
    if low in BAD_NAME_TOKENS:
        return ""
    if not re.search(r"[A-Za-z]", cleaned):
        return ""
    if len(cleaned) < 2 or len(cleaned) > 120:
        return ""
    return cleaned


def extract_entities(text: str) -> Counter[tuple[str, str, str]]:
    counts: Counter[tuple[str, str, str]] = Counter()

    for email in EMAIL_RE.findall(text):
        email_norm = email.lower()
        counts[(email_norm, "EMAIL", email_norm)] += 1
        domain = email_norm.split("@", 1)[-1]
        if domain and "." in domain:
            counts[(domain, "DOMAIN", domain)] += 1

    header_block = text[:HEADER_SCAN_CHARS]
    for _label, value in HEADER_RE.findall(header_block):
        for name, addr in getaddresses([value]):
            if addr:
                email_norm = addr.lower()
                counts[(email_norm, "EMAIL", email_norm)] += 1
                domain = email_norm.split("@", 1)[-1]
                if domain and "." in domain:
                    counts[(domain, "DOMAIN", domain)] += 1
            norm_name = _normalize_name(name)
            if norm_name:
                counts[(norm_name, "PERSON", norm_name.lower())] += 1

    return counts


def iter_candidates(
    con: sqlite3.Connection,
    dataset: int,
    retry_empty: bool,
    extensions: set[str],
) -> Iterable[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    ext_expr = "lower(substr(f.filename, instr(f.filename,'.')+1))"
    ext_placeholders = ",".join("?" for _ in sorted(extensions))
    ext_clause = f" AND {ext_expr} IN ({ext_placeholders})"
    ext_params = list(sorted(extensions))
    if retry_empty:
        sql = """
            SELECT f.id, f.filename, f.rel_path, f.file_size
            FROM files f
            LEFT JOIN text_cache tc ON tc.file_id = f.id
            WHERE f.dataset = ? AND (tc.file_id IS NULL OR tc.char_count = 0)
        ORDER BY f.id
        """
        sql = sql.replace("ORDER BY f.id", f"{ext_clause} ORDER BY f.id")
    else:
        sql = """
            SELECT f.id, f.filename, f.rel_path, f.file_size
            FROM files f
            LEFT JOIN text_cache tc ON tc.file_id = f.id
            WHERE f.dataset = ? AND tc.file_id IS NULL
            ORDER BY f.id
        """
        sql = sql.replace("ORDER BY f.id", f"{ext_clause} ORDER BY f.id")
    return cur.execute(sql, [dataset] + ext_params)


def sync_text_fts(con: sqlite3.Connection, dataset: int) -> int:
    cur = con.cursor()
    before = con.total_changes
    cur.execute(
        """
        INSERT INTO text_fts(rowid, filename, dataset, extracted_text)
        SELECT f.id, f.filename, f.dataset, tc.extracted_text
        FROM files f
        JOIN text_cache tc ON tc.file_id = f.id
        LEFT JOIN text_fts t ON t.rowid = f.id
        WHERE f.dataset = ? AND tc.char_count > 0 AND t.rowid IS NULL
        """,
        (dataset,),
    )
    con.commit()
    return con.total_changes - before


def main() -> int:
    args = parse_args()
    if not args.db_path.exists():
        raise SystemExit(f"DB not found: {args.db_path}")

    con = sqlite3.connect(args.db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    write_cur = con.cursor()

    extensions = {e.strip().lower() for e in args.extensions.split(",") if e.strip()}
    if not extensions:
        raise SystemExit("No extensions configured.")

    max_bytes = max(1, args.max_file_size_mb) * 1024 * 1024

    scanned = 0
    processed = 0
    with_text = 0
    empty_text = 0
    entity_rows = 0
    missing_paths = 0
    method_counts: Counter[str] = Counter()
    t_start = time.monotonic()
    mem_stopped = False

    text_rows: list[tuple[int, str, int, str]] = []
    file_updates: list[tuple[int, int, int]] = []
    entity_deletes: list[tuple[int]] = []
    entity_inserts: list[tuple[int, str, str, str, int]] = []

    def flush() -> None:
        if text_rows:
            write_cur.executemany(
                """
                INSERT INTO text_cache (file_id, extracted_text, char_count, method)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    extracted_text=excluded.extracted_text,
                    char_count=excluded.char_count,
                    method=excluded.method
                """,
                text_rows,
            )
        if file_updates:
            write_cur.executemany(
                """
                UPDATE files
                SET has_text = ?, needs_ocr = ?
                WHERE id = ?
                """,
                file_updates,
            )
        if entity_deletes:
            write_cur.executemany("DELETE FROM entities WHERE file_id = ?", entity_deletes)
        if entity_inserts:
            write_cur.executemany(
                """
                INSERT INTO entities (file_id, entity_text, entity_label, normalized, count)
                VALUES (?, ?, ?, ?, ?)
                """,
                entity_inserts,
            )
        con.commit()
        text_rows.clear()
        file_updates.clear()
        entity_deletes.clear()
        entity_inserts.clear()

    for row in iter_candidates(con, args.dataset, args.retry_empty, extensions):
        scanned += 1
        file_id = row["id"]
        rel_path = row["rel_path"]
        path = Path(rel_path)
        if not path.exists():
            missing_paths += 1
            method = "missing_file"
            text = ""
            char_count = 0
        else:
            ext = path.suffix.lower().lstrip(".")
            text, method = extract_text(path, ext, max_bytes=max_bytes)
            char_count = len(text)

        method_counts[method] += 1
        has_text = 1 if char_count > 0 else 0
        needs_ocr = 1 if method in {"zero_byte", "pymupdf_error"} else 0

        text_rows.append((file_id, text, char_count, method))
        file_updates.append((has_text, needs_ocr, file_id))
        processed += 1

        if char_count > 0:
            with_text += 1
            if args.entities:
                ents = extract_entities(text)
                entity_deletes.append((file_id,))
                for (entity_text, label, normalized), count in ents.items():
                    entity_inserts.append((file_id, entity_text, label, normalized, count))
                entity_rows += len(ents)
        else:
            empty_text += 1

        if len(text_rows) >= args.batch_size:
            flush()
            gc.collect()

            # Memory check
            rss = _get_rss_mb()
            if rss >= RSS_STOP_MB:
                print(
                    f"\n[STOP] RSS {rss:,} MB exceeds {RSS_STOP_MB} MB limit. "
                    f"Stopping after {processed:,} files. Re-run to continue.",
                    flush=True,
                )
                mem_stopped = True
                break
            if rss >= RSS_WARN_MB:
                print(f"  [WARN] RSS {rss:,} MB", flush=True)

            if args.progress_every and processed % args.progress_every == 0:
                elapsed = time.monotonic() - t_start
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = (scanned - processed) if args.limit == 0 else max(0, args.limit - processed)
                eta_secs = remaining / rate if rate > 0 else 0
                eta_h = eta_secs / 3600
                print(
                    f"processed={processed:,} with_text={with_text:,} empty={empty_text:,} "
                    f"entities={entity_rows:,} | "
                    f"{rate:.1f} files/s  RSS={rss:,}MB  "
                    f"elapsed={elapsed/60:.0f}m  ETA~{eta_h:.1f}h",
                    flush=True,
                )

        if args.limit and processed >= args.limit:
            break

    flush()
    gc.collect()

    fts_added = 0
    if args.sync_fts:
        fts_added = sync_text_fts(con, args.dataset)

    ds_files = con.execute("SELECT COUNT(*) FROM files WHERE dataset = ?", (args.dataset,)).fetchone()[0]
    ds_text = con.execute(
        """
        SELECT COUNT(*)
        FROM text_cache tc
        JOIN files f ON f.id = tc.file_id
        WHERE f.dataset = ? AND tc.char_count > 0
        """,
        (args.dataset,),
    ).fetchone()[0]
    ds_entities = con.execute(
        """
        SELECT COUNT(*)
        FROM entities e
        JOIN files f ON f.id = e.file_id
        WHERE f.dataset = ?
        """,
        (args.dataset,),
    ).fetchone()[0]

    total_elapsed = time.monotonic() - t_start
    status = "stopped (memory limit)" if mem_stopped else "complete"
    print(f"\nBackfill {status}")
    print(f"  elapsed: {total_elapsed/3600:.1f}h ({total_elapsed/60:.0f}m)")
    print(f"  scanned_candidates: {scanned:,}")
    print(f"  processed: {processed:,}")
    print(f"  with_text: {with_text:,}")
    print(f"  empty_text: {empty_text:,}")
    print(f"  missing_paths: {missing_paths:,}")
    print(f"  entity_rows_written: {entity_rows:,}")
    print(f"  fts_rows_added: {fts_added:,}")
    print(f"  final_rss_mb: {_get_rss_mb():,}")
    print(f"  dataset_{args.dataset}_files: {ds_files:,}")
    print(f"  dataset_{args.dataset}_text_rows_gt0: {ds_text:,}")
    print(f"  dataset_{args.dataset}_entity_rows: {ds_entities:,}")
    print("  methods:")
    for method, count in method_counts.most_common():
        print(f"    {method}: {count:,}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
