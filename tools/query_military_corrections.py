#!/usr/bin/env python3
"""
Military corrections boards (BCMR/BCNR/AFBCMR/CGBCMR) decision-search tool.

Crawls the Department of Defense Boards of Review Reading Room, hosted by the
Air Force at boards.law.af.mil, which mirrors decisional documents for all four
service correction boards (October 1998 - present, plus AF history back to 1984).

Index structure:
    https://boards.law.af.mil/index.htm
        AFboards.htm  -> AF_BCMR.htm    -> AF_BCMR_CY{YEAR}.htm   -> AF/BCMR/CY{YEAR}/*.pdf
        ARMYboards.htm -> ARMY_BCMR.htm  -> ARMY_BCMR_CY{YEAR}.htm -> ARMY/BCMR/CY{YEAR}/*.pdf
        NAVYboards.htm -> NAVY_BCNR.htm  -> NAVY_BCNR_CY{YEAR}.htm -> NAVY/BCNR/CY{YEAR}/*.pdf
        CGboards.htm  -> CG_BCMR.htm    -> CG_BCMR_{Category}.htm -> CG/BCMR/{Category}/*.pdf

Coast Guard decisions are organized by topic (e.g., "Officer Promotion and
DOR") rather than calendar year. The other three services use CY{YEAR} folders.

Petitioner counsel is sometimes named on the face of the redacted PDF and
sometimes redacted entirely. Counsel never appears in the index metadata, so a
full-text scan over downloaded PDFs is the only way to identify Parlatore Law
Group / Tim Parlatore / etc. as petitioner counsel.

Subcommands:
    crawl-index   - Refresh local index of available decisions (no PDFs)
    download      - Download decision PDFs for a service/year range
    index-text    - Extract text from cached PDFs into local SQLite
    attorney NAME - Find decisions where NAME appears as counsel
    keyword TERM  - Free-text search over indexed decisions
    decision SVC DOCKET - Show one decision's metadata + text excerpt
    stats         - Show cache state

Cache: .cache/military_corrections.db (SQLite, WAL)
PDFs:  .cache/military_corrections/{service}/{year_or_cat}/{docket}.pdf

Usage examples:
    uv run python tools/query_military_corrections.py crawl-index --service all --output /tmp/mc-index.json
    uv run python tools/query_military_corrections.py download --service afbcmr --year-from 2022 --year-to 2024
    uv run python tools/query_military_corrections.py index-text --service all
    uv run python tools/query_military_corrections.py attorney "Parlatore" --output /tmp/parlatore.json
    uv run python tools/query_military_corrections.py keyword "promotion list" --output /tmp/promo.json
    uv run python tools/query_military_corrections.py decision afbcmr BC-2023-00003
"""

import argparse
import html
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache"
DB_PATH = CACHE_DIR / "military_corrections.db"
PDF_DIR = CACHE_DIR / "military_corrections"

BASE_URL = "https://boards.law.af.mil/"
USER_AGENT = "Mozilla/5.0 (compatible; ithildin-osint-research/1.0)"
DEFAULT_DELAY = 2.0  # seconds between requests = 0.5 req/sec
HTTP_TIMEOUT = 60

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

try:
    from tools.lead_tracker import log_search
except Exception:  # pragma: no cover
    def log_search(*_args, **_kwargs):
        pass


# ----- Service definitions -----------------------------------------------------

# id -> (display_label, board_index_page, organization_kind, year_range_or_categories)
# organization_kind: "year" => calendar-year folders; "category" => topic folders (CG)
SERVICES = {
    "afbcmr": {
        "label": "Air Force Board for Correction of Military Records",
        "board_page": "AF_BCMR.htm",
        "kind": "year",
        "default_years": (1984, 2025),
        "pdf_prefix": "AF/BCMR/",
        "docket_re": re.compile(r"(BC-?\d{4}-?\d{4,6})", re.I),
    },
    "abcmr": {
        "label": "Army Board for Correction of Military Records",
        "board_page": "ARMY_BCMR.htm",
        "kind": "year",
        "default_years": (1997, 2025),
        "pdf_prefix": "ARMY/BCMR/",
        "docket_re": re.compile(r"(AR\d{10,})", re.I),
    },
    "bcnr": {
        "label": "Board for Correction of Naval Records (Navy/Marines)",
        "board_page": "NAVY_BCNR.htm",
        "kind": "year",
        "default_years": (1998, 2025),
        "pdf_prefix": "NAVY/BCNR/",
        "docket_re": re.compile(r"(NR\d{10,})", re.I),
    },
    "cgbcmr": {
        "label": "Coast Guard Board for Correction of Military Records",
        "board_page": "CG_BCMR.htm",
        "kind": "category",
        "default_years": None,
        "pdf_prefix": "CG/BCMR/",
        # CG dockets vary widely (e.g. "13-97", "1997-025", "2024-003"); pull the leading
        # token from the filename and let the catch-all match it.
        "docket_re": re.compile(r"^([\w\-]+)", re.I),
    },
}

ALL_SERVICE_IDS = list(SERVICES.keys())


# ----- HTTP fetcher ------------------------------------------------------------

class Fetcher:
    """Polite HTTP fetcher with rate limiting."""

    def __init__(self, delay=DEFAULT_DELAY):
        self.delay = delay
        self._last = 0.0

    def _sleep(self):
        elapsed = time.time() - self._last
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last = time.time()

    def fetch(self, url, binary=False):
        self._sleep()
        req = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                data = resp.read()
        except HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} for {url}") from e
        except URLError as e:
            raise RuntimeError(f"URL error for {url}: {e}") from e
        if binary:
            return data
        # Reading Room pages are static ASCII/Windows-1252 HTML; latin-1 decode never fails.
        return data.decode("latin-1", errors="replace")


# ----- HTML parsing ------------------------------------------------------------

_LINK_RE = re.compile(r'href="([^"]+)"', re.I)


def extract_hrefs(html_text):
    """Return all hrefs in the HTML document, decoded."""
    return [html.unescape(m) for m in _LINK_RE.findall(html_text)]


def filter_links(hrefs, suffix):
    """Return hrefs ending with the given suffix (case-insensitive)."""
    return [h for h in hrefs if h.lower().endswith(suffix.lower())]


# ----- Database ----------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service         TEXT    NOT NULL,
    bucket          TEXT    NOT NULL,           -- year ("CY2023") or category ("Officer Promotion and DOR")
    docket          TEXT    NOT NULL,
    pdf_url         TEXT    NOT NULL,
    pdf_filename    TEXT    NOT NULL,
    local_path      TEXT,
    downloaded_at   TEXT,
    indexed_at      TEXT,
    text_chars      INTEGER,
    page_count      INTEGER,
    UNIQUE(service, pdf_url)
);

CREATE INDEX IF NOT EXISTS idx_decisions_service ON decisions(service);
CREATE INDEX IF NOT EXISTS idx_decisions_bucket  ON decisions(service, bucket);
CREATE INDEX IF NOT EXISTS idx_decisions_docket  ON decisions(docket);

CREATE TABLE IF NOT EXISTS decision_text (
    decision_id INTEGER PRIMARY KEY,
    text        TEXT NOT NULL,
    FOREIGN KEY(decision_id) REFERENCES decisions(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS decision_text_fts USING fts5(
    text,
    content='decision_text',
    content_rowid='decision_id',
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS crawl_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    service     TEXT NOT NULL,
    bucket      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    pdf_count   INTEGER NOT NULL
);
"""


def db_connect():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def db_reset():
    if DB_PATH.exists():
        DB_PATH.unlink()


# ----- crawl-index -------------------------------------------------------------

def list_buckets(fetcher, service_id):
    """Return list of (bucket_label, bucket_url) for a service.

    For year-based services this is calendar years; for CG it is topic categories.
    """
    svc = SERVICES[service_id]
    page = fetcher.fetch(urljoin(BASE_URL, svc["board_page"]))
    hrefs = extract_hrefs(page)

    if svc["kind"] == "year":
        prefix = svc["board_page"].replace(".htm", "_CY")
        buckets = []
        for h in hrefs:
            if h.startswith(prefix) and h.endswith(".htm"):
                year_str = h[len(prefix):-4]
                buckets.append((f"CY{year_str}", h))
        return sorted(set(buckets))

    # CG: category folders
    page_prefix = svc["board_page"].replace(".htm", "_")
    buckets = []
    for h in hrefs:
        if h.startswith(page_prefix) and h.endswith(".htm"):
            cat = unquote(h[len(page_prefix):-4])
            buckets.append((cat, h))
    return sorted(set(buckets))


def list_pdfs_in_bucket(fetcher, bucket_url):
    """Return list of (pdf_url, pdf_filename) for a single bucket index page."""
    page = fetcher.fetch(urljoin(BASE_URL, bucket_url))
    pdfs = filter_links(extract_hrefs(page), ".pdf")
    out = []
    seen = set()
    for href in pdfs:
        href_clean = href.split("#", 1)[0]
        if href_clean in seen:
            continue
        seen.add(href_clean)
        full = urljoin(BASE_URL, href_clean)
        filename = unquote(href_clean.rsplit("/", 1)[-1])
        out.append((full, filename))
    return out


def docket_from_filename(service_id, filename):
    """Best-effort extraction of a docket identifier from the PDF filename."""
    svc = SERVICES[service_id]
    m = svc["docket_re"].search(filename)
    if m:
        return m.group(1).strip("_- ").upper()
    # Last-ditch fallback
    return filename.rsplit(".", 1)[0].strip()


def cmd_crawl_index(args):
    """Refresh the local index of available decisions (no PDF download)."""
    services = _resolve_services(args.service)
    year_filter = _resolve_year_filter(args)
    fetcher = Fetcher(delay=args.delay)
    conn = db_connect()
    rows_added = 0
    rows_updated = 0
    summary = []

    for svc_id in services:
        svc = SERVICES[svc_id]
        try:
            buckets = list_buckets(fetcher, svc_id)
        except RuntimeError as e:
            print(f"WARNING: {svc_id} board page unreachable: {e}", file=sys.stderr)
            summary.append({"service": svc_id, "error": str(e)})
            continue

        if svc["kind"] == "year" and year_filter:
            yfrom, yto = year_filter
            buckets = [(b, u) for (b, u) in buckets
                       if b.startswith("CY") and yfrom <= int(b[2:]) <= yto]

        if args.limit_buckets:
            buckets = buckets[: args.limit_buckets]

        svc_pdf_total = 0
        for bucket_label, bucket_url in buckets:
            try:
                pdfs = list_pdfs_in_bucket(fetcher, bucket_url)
            except RuntimeError as e:
                print(f"WARNING: {svc_id}/{bucket_label} unreachable: {e}", file=sys.stderr)
                continue
            for pdf_url, pdf_filename in pdfs:
                docket = docket_from_filename(svc_id, pdf_filename)
                cur = conn.execute(
                    "SELECT id FROM decisions WHERE service=? AND pdf_url=?",
                    (svc_id, pdf_url),
                )
                existing = cur.fetchone()
                if existing:
                    rows_updated += 1
                    conn.execute(
                        "UPDATE decisions SET bucket=?, docket=?, pdf_filename=? WHERE id=?",
                        (bucket_label, docket, pdf_filename, existing[0]),
                    )
                else:
                    rows_added += 1
                    conn.execute(
                        "INSERT INTO decisions(service, bucket, docket, pdf_url, pdf_filename) "
                        "VALUES(?,?,?,?,?)",
                        (svc_id, bucket_label, docket, pdf_url, pdf_filename),
                    )
            conn.execute(
                "INSERT INTO crawl_log(service, bucket, fetched_at, pdf_count) VALUES(?,?,datetime('now'),?)",
                (svc_id, bucket_label, len(pdfs)),
            )
            svc_pdf_total += len(pdfs)
            conn.commit()
            print(f"  [{svc_id}] {bucket_label}: {len(pdfs)} PDFs", file=sys.stderr)

        summary.append({
            "service": svc_id,
            "label": svc["label"],
            "buckets": len(buckets),
            "pdfs": svc_pdf_total,
        })

    log_search(f"crawl-index service={args.service}", "military_corrections", rows_added)
    result = {
        "summary": summary,
        "rows_added": rows_added,
        "rows_updated": rows_updated,
        "db": str(DB_PATH),
    }
    if write_output(result, args, summary=f"crawl-index added={rows_added} updated={rows_updated}"):
        return
    print(json.dumps(result, indent=2))


# ----- download ---------------------------------------------------------------

def safe_local_path(service_id, bucket, filename):
    safe_bucket = re.sub(r"[^\w\-]+", "_", bucket).strip("_") or "misc"
    safe_filename = re.sub(r"[^\w\-.]+", "_", filename)
    return PDF_DIR / service_id / safe_bucket / safe_filename


def cmd_download(args):
    """Download decision PDFs for a service/year range."""
    services = _resolve_services(args.service)
    year_filter = _resolve_year_filter(args)
    fetcher = Fetcher(delay=args.delay)
    conn = db_connect()

    where = ["service IN (" + ",".join("?" for _ in services) + ")"]
    params = list(services)
    if year_filter:
        yfrom, yto = year_filter
        ranges = [f"CY{y}" for y in range(yfrom, yto + 1)]
        where.append("(bucket IN (" + ",".join("?" for _ in ranges) + ") OR bucket NOT LIKE 'CY%')")
        params.extend(ranges)
    if args.bucket:
        where.append("bucket = ?")
        params.append(args.bucket)
    if not args.redownload:
        where.append("(local_path IS NULL OR downloaded_at IS NULL)")

    sql = f"SELECT id, service, bucket, pdf_url, pdf_filename FROM decisions WHERE {' AND '.join(where)}"
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("No decisions match the selection (run crawl-index first).", file=sys.stderr)
        if write_output({"downloaded": 0, "errors": 0, "rows": []}, args, summary="download no-op"):
            return
        return

    downloaded = 0
    errors = 0
    error_records = []
    for row_id, svc_id, bucket, pdf_url, pdf_filename in rows:
        local = safe_local_path(svc_id, bucket, pdf_filename)
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = fetcher.fetch(pdf_url, binary=True)
        except RuntimeError as e:
            errors += 1
            error_records.append({"docket": pdf_filename, "error": str(e)})
            print(f"  ERROR {svc_id}/{bucket}/{pdf_filename}: {e}", file=sys.stderr)
            continue
        if not data.startswith(b"%PDF"):
            errors += 1
            error_records.append({"docket": pdf_filename, "error": "not a PDF"})
            continue
        local.write_bytes(data)
        conn.execute(
            "UPDATE decisions SET local_path=?, downloaded_at=datetime('now') WHERE id=?",
            (str(local), row_id),
        )
        downloaded += 1
        if downloaded % 25 == 0:
            conn.commit()
            print(f"  downloaded {downloaded}/{len(rows)}", file=sys.stderr)
    conn.commit()

    log_search(f"download service={args.service}", "military_corrections", downloaded)
    result = {
        "requested": len(rows),
        "downloaded": downloaded,
        "errors": errors,
        "error_records": error_records[:25],
    }
    if write_output(result, args, summary=f"downloaded {downloaded}/{len(rows)}"):
        return
    print(json.dumps(result, indent=2))


# ----- index-text -------------------------------------------------------------

def extract_pdf_text(path):
    """Extract text from a PDF using pymupdf. Returns (text, page_count)."""
    import fitz  # pymupdf
    doc = fitz.open(str(path))
    try:
        chunks = []
        for page in doc:
            chunks.append(page.get_text())
        return "\n".join(chunks), doc.page_count
    finally:
        doc.close()


def cmd_index_text(args):
    """Extract text from cached PDFs into local SQLite."""
    services = _resolve_services(args.service)
    conn = db_connect()
    where = ["service IN (" + ",".join("?" for _ in services) + ")", "local_path IS NOT NULL"]
    params = list(services)
    if not args.reindex:
        where.append("indexed_at IS NULL")
    sql = f"SELECT id, service, bucket, docket, local_path FROM decisions WHERE {' AND '.join(where)}"
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    rows = conn.execute(sql, params).fetchall()

    if not rows:
        print("Nothing to index. Run download first.", file=sys.stderr)
        if write_output({"indexed": 0, "errors": 0}, args, summary="index-text no-op"):
            return
        return

    indexed = 0
    errors = 0
    error_records = []
    for row_id, svc_id, bucket, docket, local_path in rows:
        path = Path(local_path)
        if not path.exists():
            errors += 1
            error_records.append({"docket": docket, "error": "missing PDF on disk"})
            continue
        try:
            text, page_count = extract_pdf_text(path)
        except Exception as e:
            errors += 1
            error_records.append({"docket": docket, "error": f"PDF parse failed: {e}"})
            continue

        text = text or ""
        conn.execute("DELETE FROM decision_text WHERE decision_id=?", (row_id,))
        conn.execute("DELETE FROM decision_text_fts WHERE rowid=?", (row_id,))
        conn.execute("INSERT INTO decision_text(decision_id, text) VALUES(?,?)", (row_id, text))
        conn.execute("INSERT INTO decision_text_fts(rowid, text) VALUES(?,?)", (row_id, text))
        conn.execute(
            "UPDATE decisions SET indexed_at=datetime('now'), text_chars=?, page_count=? WHERE id=?",
            (len(text), page_count, row_id),
        )
        indexed += 1
        if indexed % 50 == 0:
            conn.commit()
            print(f"  indexed {indexed}/{len(rows)}", file=sys.stderr)
    conn.commit()

    result = {"indexed": indexed, "errors": errors, "error_records": error_records[:25]}
    if write_output(result, args, summary=f"indexed {indexed} PDFs"):
        return
    print(json.dumps(result, indent=2))


# ----- search helpers ---------------------------------------------------------

def excerpt_around(text, needle, radius=180):
    """Return up to ~3 case-insensitive excerpts surrounding `needle`."""
    if not text:
        return []
    out = []
    pat = re.compile(re.escape(needle), re.I)
    for m in pat.finditer(text):
        start = max(0, m.start() - radius)
        end = min(len(text), m.end() + radius)
        snippet = text[start:end].replace("\n", " ")
        snippet = re.sub(r"\s+", " ", snippet).strip()
        out.append(snippet)
        if len(out) >= 3:
            break
    return out


def search_term(conn, term, services=None, limit=50):
    """Search via FTS5 first; fall back to LIKE. Returns list of dict rows."""
    services = services or ALL_SERVICE_IDS
    placeholders = ",".join("?" for _ in services)

    # FTS5 phrase search (escape internal quotes)
    fts_query = '"' + term.replace('"', '""') + '"'
    try:
        rows = conn.execute(
            f"""
            SELECT d.id, d.service, d.bucket, d.docket, d.pdf_url, d.pdf_filename,
                   d.local_path, d.downloaded_at, d.indexed_at, d.page_count,
                   t.text
              FROM decision_text_fts f
              JOIN decisions      d ON d.id = f.rowid
              JOIN decision_text  t ON t.decision_id = d.id
             WHERE decision_text_fts MATCH ?
               AND d.service IN ({placeholders})
             LIMIT ?
            """,
            (fts_query, *services, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []

    if not rows:
        rows = conn.execute(
            f"""
            SELECT d.id, d.service, d.bucket, d.docket, d.pdf_url, d.pdf_filename,
                   d.local_path, d.downloaded_at, d.indexed_at, d.page_count,
                   t.text
              FROM decisions      d
              JOIN decision_text  t ON t.decision_id = d.id
             WHERE t.text LIKE ?
               AND d.service IN ({placeholders})
             LIMIT ?
            """,
            (f"%{term}%", *services, limit),
        ).fetchall()

    out = []
    for r in rows:
        (row_id, svc_id, bucket, docket, pdf_url, pdf_filename,
         local_path, downloaded_at, indexed_at, page_count, text) = r
        out.append({
            "id": row_id,
            "service": svc_id,
            "service_label": SERVICES[svc_id]["label"],
            "bucket": bucket,
            "docket": docket,
            "pdf_url": pdf_url,
            "pdf_filename": pdf_filename,
            "local_path": local_path,
            "downloaded_at": downloaded_at,
            "indexed_at": indexed_at,
            "page_count": page_count,
            "excerpts": excerpt_around(text, term),
        })
    return out


# ----- attorney / keyword / decision -----------------------------------------

def cmd_attorney(args):
    """Find decisions where NAME appears as petitioner counsel."""
    services = _resolve_services(args.service)
    conn = db_connect()
    name = args.name.strip()
    matches = search_term(conn, name, services=services, limit=args.limit)
    log_search(f"attorney {name}", "military_corrections", len(matches))

    note = None
    have_text = conn.execute("SELECT COUNT(*) FROM decision_text").fetchone()[0]
    if have_text == 0:
        note = ("No decisions have been text-indexed yet. Run "
                "`download` then `index-text` to populate the cache before searching.")

    result = {"query": name, "match_count": len(matches), "matches": matches}
    if note:
        result["note"] = note
    if write_output(result, args, summary=f"attorney '{name}': {len(matches)} matches"):
        return
    print(json.dumps(result, indent=2))


def cmd_keyword(args):
    """Free-text search over indexed decisions."""
    services = _resolve_services(args.service)
    conn = db_connect()
    term = args.term.strip()
    matches = search_term(conn, term, services=services, limit=args.limit)
    log_search(f"keyword {term}", "military_corrections", len(matches))

    note = None
    have_text = conn.execute("SELECT COUNT(*) FROM decision_text").fetchone()[0]
    if have_text == 0:
        note = ("No decisions have been text-indexed yet. Run "
                "`download` then `index-text` to populate the cache before searching.")

    result = {"query": term, "match_count": len(matches), "matches": matches}
    if note:
        result["note"] = note
    if write_output(result, args, summary=f"keyword '{term}': {len(matches)} matches"):
        return
    print(json.dumps(result, indent=2))


def cmd_decision(args):
    """Show one decision's metadata + text excerpt."""
    conn = db_connect()
    row = conn.execute(
        """
        SELECT d.id, d.service, d.bucket, d.docket, d.pdf_url, d.pdf_filename,
               d.local_path, d.downloaded_at, d.indexed_at, d.page_count, d.text_chars,
               t.text
          FROM decisions d
          LEFT JOIN decision_text t ON t.decision_id = d.id
         WHERE d.service = ? AND (d.docket = ? OR d.pdf_filename LIKE ?)
         LIMIT 1
        """,
        (args.service, args.docket.upper(), f"%{args.docket}%"),
    ).fetchone()
    if not row:
        print(f"Decision {args.service}/{args.docket} not found in cache.", file=sys.stderr)
        if write_output({"found": False}, args, summary="decision not found"):
            return
        return
    (row_id, svc_id, bucket, docket, pdf_url, pdf_filename,
     local_path, downloaded_at, indexed_at, page_count, text_chars, text) = row
    excerpt = (text or "")[: args.excerpt_chars] if text else None
    result = {
        "found": True,
        "service": svc_id,
        "service_label": SERVICES[svc_id]["label"],
        "bucket": bucket,
        "docket": docket,
        "pdf_url": pdf_url,
        "pdf_filename": pdf_filename,
        "local_path": local_path,
        "downloaded_at": downloaded_at,
        "indexed_at": indexed_at,
        "page_count": page_count,
        "text_chars": text_chars,
        "excerpt": excerpt,
    }
    if write_output(result, args, summary=f"decision {svc_id}/{docket}"):
        return
    print(json.dumps(result, indent=2))


# ----- stats ------------------------------------------------------------------

def cmd_stats(args):
    """Show cache state."""
    conn = db_connect()
    services = []
    for svc_id, svc in SERVICES.items():
        row = conn.execute(
            """
            SELECT COUNT(*),
                   SUM(CASE WHEN local_path IS NOT NULL THEN 1 ELSE 0 END),
                   SUM(CASE WHEN indexed_at  IS NOT NULL THEN 1 ELSE 0 END),
                   COUNT(DISTINCT bucket)
              FROM decisions WHERE service=?
            """,
            (svc_id,),
        ).fetchone()
        total, downloaded, indexed, buckets = row
        services.append({
            "service": svc_id,
            "label": svc["label"],
            "indexed_decisions": total or 0,
            "downloaded": downloaded or 0,
            "text_indexed": indexed or 0,
            "buckets": buckets or 0,
        })
    totals = {
        "total": sum(s["indexed_decisions"] for s in services),
        "downloaded": sum(s["downloaded"] for s in services),
        "text_indexed": sum(s["text_indexed"] for s in services),
    }
    result = {"db": str(DB_PATH), "totals": totals, "services": services}
    if write_output(result, args, summary=f"stats total={totals['total']} downloaded={totals['downloaded']} indexed={totals['text_indexed']}"):
        return
    print(json.dumps(result, indent=2))


# ----- shared helpers ---------------------------------------------------------

def _resolve_services(arg):
    if arg in (None, "all"):
        return list(ALL_SERVICE_IDS)
    if arg not in SERVICES:
        print(f"ERROR: unknown service '{arg}'. Choose: {', '.join(['all', *ALL_SERVICE_IDS])}",
              file=sys.stderr)
        sys.exit(2)
    return [arg]


def _resolve_year_filter(args):
    yfrom = getattr(args, "year_from", None)
    yto = getattr(args, "year_to", None)
    if yfrom is None and yto is None:
        return None
    if yfrom is None:
        yfrom = 1984
    if yto is None:
        yto = 2025
    return int(yfrom), int(yto)


# ----- argparse ---------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="query_military_corrections.py",
        description="Search decisional documents from BCMR/BCNR/AFBCMR/CGBCMR Reading Rooms.",
    )
    p.add_argument("--reset-cache", action="store_true",
                   help="Delete the local SQLite cache before running the subcommand.")
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                   help="Seconds between HTTP requests (default 2.0 = 0.5 req/sec).")
    sub = p.add_subparsers(dest="cmd", required=True)

    # crawl-index
    pc = sub.add_parser("crawl-index", help="Refresh local index of available decisions")
    pc.add_argument("--service", default="all",
                    help="afbcmr | abcmr | bcnr | cgbcmr | all (default: all)")
    pc.add_argument("--year-from", type=int)
    pc.add_argument("--year-to", type=int)
    pc.add_argument("--limit-buckets", type=int,
                    help="Cap per-service buckets crawled (useful for sampling)")
    add_output_args(pc)
    pc.set_defaults(func=cmd_crawl_index)

    # download
    pd = sub.add_parser("download", help="Download decision PDFs")
    pd.add_argument("--service", default="all")
    pd.add_argument("--year-from", type=int)
    pd.add_argument("--year-to", type=int)
    pd.add_argument("--bucket", help="Single bucket label, e.g. CY2023 or 'Officer Promotion and DOR'")
    pd.add_argument("--limit", type=int, help="Cap number of PDFs to download in this run")
    pd.add_argument("--redownload", action="store_true",
                    help="Re-fetch PDFs even if already cached")
    add_output_args(pd)
    pd.set_defaults(func=cmd_download)

    # index-text
    pi = sub.add_parser("index-text", help="Extract text from cached PDFs into SQLite")
    pi.add_argument("--service", default="all")
    pi.add_argument("--limit", type=int, help="Cap number of PDFs to (re)index")
    pi.add_argument("--reindex", action="store_true",
                    help="Re-extract text even if already indexed")
    add_output_args(pi)
    pi.set_defaults(func=cmd_index_text)

    # attorney
    pa = sub.add_parser("attorney", help="Find decisions where NAME appears as counsel")
    pa.add_argument("name")
    pa.add_argument("--service", default="all")
    pa.add_argument("--limit", type=int, default=100)
    add_output_args(pa)
    pa.set_defaults(func=cmd_attorney)

    # keyword
    pk = sub.add_parser("keyword", help="Free-text search over indexed decisions")
    pk.add_argument("term")
    pk.add_argument("--service", default="all")
    pk.add_argument("--limit", type=int, default=100)
    add_output_args(pk)
    pk.set_defaults(func=cmd_keyword)

    # decision
    pdsh = sub.add_parser("decision", help="Show one decision's metadata + text excerpt")
    pdsh.add_argument("service", choices=ALL_SERVICE_IDS)
    pdsh.add_argument("docket")
    pdsh.add_argument("--excerpt-chars", type=int, default=4000)
    add_output_args(pdsh)
    pdsh.set_defaults(func=cmd_decision)

    # stats
    ps = sub.add_parser("stats", help="Show cache state")
    add_output_args(ps)
    ps.set_defaults(func=cmd_stats)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.reset_cache:
        db_reset()
    args.func(args)


if __name__ == "__main__":
    main()
