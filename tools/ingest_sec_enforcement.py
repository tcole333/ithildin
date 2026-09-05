#!/usr/bin/env python3
"""Ingest SEC enforcement actions (litigation releases, admin proceedings, AAERs).

Scrapes SEC enforcement index pages, parses defendant/respondent names, fetches
the full text of each release, and stores everything in
datasets/sec_enforcement.db for cross-referencing against investigation entities
and corporate registry officers.

`ingest` records only what the index pages expose (respondent, release number,
date, URL). `fetch-bodies` retrieves the release text itself from the official
URL already stored on each row; it is a separate, resumable pass because the
bodies are PDF orders and HTML pages rather than index metadata.

Release text is stored verbatim. Allegation, charge, settlement, and conviction
language is never normalized or reworded: an SEC release proves what the
Commission alleged, ordered, or settled, not that the described conduct occurred.

Usage:
    python tools/ingest_sec_enforcement.py ingest                          # All sources, all pages
    python tools/ingest_sec_enforcement.py ingest --source litigation       # One source type
    python tools/ingest_sec_enforcement.py ingest --pages 3                 # First 3 pages only
    python tools/ingest_sec_enforcement.py ingest --incremental             # Stop at existing entries
    python tools/ingest_sec_enforcement.py fetch-bodies                     # Backfill all missing bodies
    python tools/ingest_sec_enforcement.py fetch-bodies --start 2021-01-01 --end 2025-12-31
    python tools/ingest_sec_enforcement.py fetch-bodies --retry-failed      # Re-attempt failed/empty rows
    python tools/ingest_sec_enforcement.py stats                            # Summary counts
    python tools/ingest_sec_enforcement.py reparse                          # Re-run defendant parsing
"""

import argparse
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from tools.government_release_corpus import (
        decode_html,
        extract_balanced_div,
        strip_html,
    )
    from tools.output_util import add_output_args, write_output
except ImportError:
    from government_release_corpus import (
        decode_html,
        extract_balanced_div,
        strip_html,
    )
    from output_util import add_output_args, write_output

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent.parent / "datasets" / "sec_enforcement.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enforcement_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_number TEXT NOT NULL,
    source_type TEXT NOT NULL,
    date_published TEXT NOT NULL,
    datetime_published TEXT,
    respondent_text TEXT NOT NULL,
    release_url TEXT,
    file_number TEXT,
    see_also_text TEXT,
    see_also_url TEXT,
    body_text TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(release_number, source_type)
);

-- Parties named in an action's respondent field. `role` distinguishes actual
-- defendants from non-parties the field also carries (currently the presiding
-- administrative law judge); defendant-semantics queries must filter on it.
CREATE TABLE IF NOT EXISTS enforcement_defendants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id INTEGER NOT NULL REFERENCES enforcement_actions(id),
    name_raw TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    defendant_type TEXT,
    is_et_al INTEGER DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'defendant'
        CHECK (role IN ('defendant', 'presiding_alj')),
    UNIQUE(action_id, name_normalized)
);

CREATE TABLE IF NOT EXISTS enforcement_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    defendant_id INTEGER NOT NULL
        REFERENCES enforcement_defendants(id) ON DELETE CASCADE,
    match_source TEXT NOT NULL,
    match_source_id INTEGER,
    match_name TEXT NOT NULL,
    match_type TEXT NOT NULL,
    match_score REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(defendant_id, match_source, match_source_id)
);

CREATE TABLE IF NOT EXISTS enforcement_ingest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    pages_scraped INTEGER NOT NULL,
    actions_found INTEGER NOT NULL,
    actions_new INTEGER NOT NULL,
    defendants_parsed INTEGER NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ea_source ON enforcement_actions(source_type);
CREATE INDEX IF NOT EXISTS idx_ea_date ON enforcement_actions(date_published);
CREATE INDEX IF NOT EXISTS idx_ed_action ON enforcement_defendants(action_id);
CREATE INDEX IF NOT EXISTS idx_ed_name ON enforcement_defendants(name_normalized);
CREATE INDEX IF NOT EXISTS idx_em_defendant ON enforcement_matches(defendant_id);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS enforcement_actions_fts USING fts5(
    respondent_text, release_number, body_text,
    content=enforcement_actions, content_rowid=id,
    tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS enforcement_defendants_fts USING fts5(
    name_raw, name_normalized,
    content=enforcement_defendants, content_rowid=id,
    tokenize='porter unicode61'
);
"""

# FTS sync triggers
FTS_TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS ea_ai AFTER INSERT ON enforcement_actions BEGIN
    INSERT INTO enforcement_actions_fts(rowid, respondent_text, release_number, body_text)
    VALUES (new.id, new.respondent_text, new.release_number, new.body_text);
END;

CREATE TRIGGER IF NOT EXISTS ea_ad AFTER DELETE ON enforcement_actions BEGIN
    INSERT INTO enforcement_actions_fts(enforcement_actions_fts, rowid, respondent_text, release_number, body_text)
    VALUES ('delete', old.id, old.respondent_text, old.release_number, old.body_text);
END;

CREATE TRIGGER IF NOT EXISTS ea_au AFTER UPDATE ON enforcement_actions BEGIN
    INSERT INTO enforcement_actions_fts(enforcement_actions_fts, rowid, respondent_text, release_number, body_text)
    VALUES ('delete', old.id, old.respondent_text, old.release_number, old.body_text);
    INSERT INTO enforcement_actions_fts(rowid, respondent_text, release_number, body_text)
    VALUES (new.id, new.respondent_text, new.release_number, new.body_text);
END;

CREATE TRIGGER IF NOT EXISTS ed_ai AFTER INSERT ON enforcement_defendants BEGIN
    INSERT INTO enforcement_defendants_fts(rowid, name_raw, name_normalized)
    VALUES (new.id, new.name_raw, new.name_normalized);
END;

CREATE TRIGGER IF NOT EXISTS ed_ad AFTER DELETE ON enforcement_defendants BEGIN
    INSERT INTO enforcement_defendants_fts(enforcement_defendants_fts, rowid, name_raw, name_normalized)
    VALUES ('delete', old.id, old.name_raw, old.name_normalized);
END;

CREATE TRIGGER IF NOT EXISTS ed_au AFTER UPDATE ON enforcement_defendants BEGIN
    INSERT INTO enforcement_defendants_fts(enforcement_defendants_fts, rowid, name_raw, name_normalized)
    VALUES ('delete', old.id, old.name_raw, old.name_normalized);
    INSERT INTO enforcement_defendants_fts(rowid, name_raw, name_normalized)
    VALUES (new.id, new.name_raw, new.name_normalized);
END;
"""


# Body-retrieval provenance, added after the original index-only schema shipped.
BODY_COLUMNS = {
    "body_fetch_status": "TEXT",
    "body_fetch_error": "TEXT",
    "body_fetched_at": "TIMESTAMP",
    "body_source_url": "TEXT",
    "body_extraction_method": "TEXT",
}


# Party role, added after the original schema stored every name in the
# respondent field as a defendant. See parse_defendants.
DEFENDANT_COLUMNS = {
    "role": (
        "TEXT NOT NULL DEFAULT 'defendant' "
        "CHECK (role IN ('defendant', 'presiding_alj'))"
    ),
}


def _ensure_column(db, table, name, ddl):
    cols = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    if name not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _ensure_matches_cascade(db):
    """Rebuild enforcement_matches so its defendant FK cascades on delete.

    `reparse` clears enforcement_defendants wholesale. The original FK had no
    ON DELETE CASCADE, so reparse would abort with an IntegrityError as soon as
    any match rows existed. Matches are derived from defendant rows, so they are
    correctly discarded when those rows are rebuilt.
    """
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='enforcement_matches'"
    ).fetchone()
    if not row or not row[0] or "ON DELETE CASCADE" in row[0].upper():
        return

    db.commit()  # PRAGMA foreign_keys is a no-op inside a transaction
    db.execute("PRAGMA foreign_keys=OFF")
    try:
        db.executescript(
            """
            CREATE TABLE enforcement_matches_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                defendant_id INTEGER NOT NULL
                    REFERENCES enforcement_defendants(id) ON DELETE CASCADE,
                match_source TEXT NOT NULL,
                match_source_id INTEGER,
                match_name TEXT NOT NULL,
                match_type TEXT NOT NULL,
                match_score REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(defendant_id, match_source, match_source_id)
            );
            INSERT INTO enforcement_matches_new
                SELECT id, defendant_id, match_source, match_source_id,
                       match_name, match_type, match_score, created_at
                FROM enforcement_matches;
            DROP TABLE enforcement_matches;
            ALTER TABLE enforcement_matches_new RENAME TO enforcement_matches;
            CREATE INDEX IF NOT EXISTS idx_em_defendant
                ON enforcement_matches(defendant_id);
            """
        )
        db.commit()
    finally:
        db.execute("PRAGMA foreign_keys=ON")


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA_SQL)
    for name, ddl in BODY_COLUMNS.items():
        _ensure_column(db, "enforcement_actions", name, ddl)
    for name, ddl in DEFENDANT_COLUMNS.items():
        _ensure_column(db, "enforcement_defendants", name, ddl)
    _ensure_matches_cascade(db)
    # FTS tables and triggers (separate because CREATE VIRTUAL TABLE can't be in executescript with IF NOT EXISTS sometimes)
    for stmt in FTS_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                db.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Already exists
    for stmt in FTS_TRIGGERS_SQL.strip().split("END;"):
        stmt = stmt.strip()
        if stmt:
            try:
                db.execute(stmt + "END;")
            except sqlite3.OperationalError:
                pass  # Already exists
    db.commit()
    return db


# ---------------------------------------------------------------------------
# SEC HTTP client
# ---------------------------------------------------------------------------

USER_AGENT = "OSINT-Research osint-research@proton.me"
MIN_INTERVAL = 0.11  # 10 req/sec max
_last_request = 0.0
_request_lock = threading.Lock()

BASE_URL = "https://www.sec.gov"


def _throttle():
    """Reserve the next request slot, keeping the process under SEC's 10 req/s.

    The slot is claimed before the request is issued so concurrent body fetches
    cannot all read the same timestamp and burst past the ceiling.
    """
    global _last_request
    with _request_lock:
        wait = MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()

SOURCE_URLS = {
    "litigation": f"{BASE_URL}/enforcement-litigation/litigation-releases",
    "admin": f"{BASE_URL}/enforcement-litigation/administrative-proceedings",
    "aaer": f"{BASE_URL}/enforcement-litigation/accounting-auditing-enforcement-releases",
}


def _request(url):
    """Rate-limited GET returning HTML string, or None on error."""
    _throttle()
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        if e.code == 403:
            print("ERROR: 403 Forbidden — SEC requires User-Agent", file=sys.stderr)
        elif e.code == 429:
            print("  Rate limited — backing off 30s", file=sys.stderr)
            time.sleep(30)
            return _request(url)  # Retry once
        elif e.code == 404:
            return None
        else:
            print(f"ERROR: HTTP {e.code} from {url}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"ERROR: Cannot reach SEC: {e.reason}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

ROW_RE = re.compile(r'<tr class="pr-list-page-row">(.*?)</tr>', re.DOTALL)
DATE_RE = re.compile(r'<time datetime="([^"]+)"[^>]*>([^<]+)</time>')
RESP_RE = re.compile(r"class='release-view__respondents'>(.*?)</div>", re.DOTALL)
RESP_LINK_RE = re.compile(r"<a\s+href='([^']+)'[^>]*>([^<]+)</a>")
REL_NO_RE = re.compile(
    r"subfield_release_number.*?subfield_value\">([^<]+)", re.DOTALL
)
FILE_NO_RE = re.compile(
    r"subfield_file_number.*?subfield_value\">([^<]+)", re.DOTALL
)
SEE_ALSO_RE = re.compile(
    r'subfield_see_also.*?<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', re.DOTALL
)


def parse_page(html, source_type):
    """Parse one SEC enforcement index page. Returns list of action dicts."""
    actions = []
    for row_html in ROW_RE.findall(html):
        action = {"source_type": source_type}

        # Date
        date_m = DATE_RE.search(row_html)
        if date_m:
            action["datetime_published"] = date_m.group(1)
            # Extract ISO date from datetime
            action["date_published"] = date_m.group(1)[:10]
        else:
            continue  # Skip rows without dates

        # Respondent text and URL
        resp_m = RESP_RE.search(row_html)
        if resp_m:
            link_m = RESP_LINK_RE.search(resp_m.group(1))
            if link_m:
                href = link_m.group(1)
                if not href.startswith("http"):
                    href = BASE_URL + href
                action["release_url"] = href
                action["respondent_text"] = _clean_html(link_m.group(2))
            else:
                # Text without link
                action["respondent_text"] = _clean_html(resp_m.group(1))
        else:
            continue  # Skip rows without respondent info

        # Release number
        rel_m = REL_NO_RE.search(row_html)
        if rel_m:
            action["release_number"] = rel_m.group(1).strip()
        else:
            continue  # Skip rows without release number

        # File number (optional)
        file_m = FILE_NO_RE.search(row_html)
        if file_m:
            action["file_number"] = file_m.group(1).strip()

        # See-also (optional)
        see_m = SEE_ALSO_RE.search(row_html)
        if see_m:
            href = see_m.group(1)
            if not href.startswith("http"):
                href = BASE_URL + href
            action["see_also_url"] = href
            action["see_also_text"] = _clean_html(see_m.group(2))

        actions.append(action)
    return actions


def _clean_html(text):
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Release body retrieval
# ---------------------------------------------------------------------------

# Bodies live behind the release_url already stored by `ingest`, in three
# verified shapes: PDF orders (/files/litigation/admin/<year>/<release>.pdf),
# plain-text legacy releases (.txt), and HTML pages.
#
# Two modern-site templates need a fallback, and they need *different* ones:
#   * /administrative-proceedings/ and /opinions-adjudicatory-orders/ pages are
#     stubs carrying only the respondent name; the ordered text exists solely in
#     the order PDF under /files/litigation/admin/<year>/.
#   * some /litigation-releases/ pages publish a header-only body (release number
#     and date, no narrative); the legacy static release still has the full text
#     under /files/litigation/litreleases/<year>/.
# Both are keyed on the page's own URL slug rather than the row's release number:
# composite releases share one page and only the slug resolves.
ADMIN_PAGE_MARKERS = ("/administrative-proceedings/", "/opinions-adjudicatory-orders/")
LITIGATION_PAGE_MARKER = "/litigation-releases/"
ADMIN_PDF_TEMPLATE = f"{BASE_URL}/files/litigation/admin/{{year}}/{{slug}}.pdf"
LEGACY_LITRELEASE_TEMPLATE = (
    f"{BASE_URL}/files/litigation/litreleases/{{year}}/{{slug}}.htm"
)

# Path conventions also differ by era: from roughly 2005 the static files sit in
# a per-year directory, before that they are year-less .htm/.txt. Both are tried,
# newest convention first, and only for pages whose own body came up short.
ADMIN_BODY_TEMPLATES = (
    ADMIN_PDF_TEMPLATE,
    f"{BASE_URL}/files/litigation/admin/{{slug}}.htm",
    f"{BASE_URL}/files/litigation/admin/{{slug}}.txt",
)
LITIGATION_BODY_TEMPLATES = (
    LEGACY_LITRELEASE_TEMPLATE,
    f"{BASE_URL}/files/litigation/litreleases/{{slug}}.htm",
    f"{BASE_URL}/files/litigation/litreleases/{{slug}}.txt",
)

# A real release body always clears this; anything shorter is site chrome or an
# image-only scan, and is recorded as a miss rather than stored as a body.
BODY_MIN_CHARS = 200

# Whole-line site navigation removed from HTML extractions. Matched only against
# a complete stripped line, so release wording is never touched.
BOILERPLATE_LINES = frozenset(
    {
        "home",
        "previous page",
        "|",
        "menu",
        "return to top",
        "sec homepage",
        "skip to search field",
        "skip to main content",
        "stay connected. sign up for email updates.",
        "email updates",
        "an official website of the united states government",
        "here's how you know",
        "here’s how you know",
    }
)

BODY_RETRY_STATUSES = ("failed", "empty")


class BodyUnavailable(RuntimeError):
    """The official source was reached but carries no retrievable body text.

    Distinct from transport failures: retrying will not help until the SEC
    publishes text, or until an OCR pass is added for image-only scans.
    """


def _drop_boilerplate(text):
    """Remove whole-line site navigation, leaving all release wording intact."""
    kept = [
        line
        for line in text.splitlines()
        if line.strip().lower() not in BOILERPLATE_LINES
    ]
    return "\n".join(kept).strip()


def _fetch_raw(url, timeout=45, retries=3):
    """Rate-limited GET returning (content_type, raw_bytes).

    Raises HTTPError/URLError so the caller can record why a body is missing.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    attempt = 0
    while True:
        _throttle()
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as resp:
                return resp.headers.get("Content-Type", ""), resp.read()
        except HTTPError as exc:
            if attempt >= retries or exc.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = float(retry_after) if retry_after else 2**attempt
            except (TypeError, ValueError):
                delay = 2**attempt
        except URLError:
            if attempt >= retries:
                raise
            delay = 2**attempt
        time.sleep(min(max(delay, 0.5), 30.0))
        attempt += 1


def _extract_pdf_text(raw):
    """Extract text from a PDF payload. Returns (text, method)."""
    handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        handle.write(raw)
        handle.close()
        # Canonical path: macOS /tmp is a symlink and some extractors fail through it.
        pdf_path = Path(handle.name).resolve()

        try:
            import pymupdf
        except ImportError:
            try:
                import fitz as pymupdf
            except ImportError:
                pymupdf = None
        if pymupdf is not None:
            try:
                doc = pymupdf.open(str(pdf_path))
                try:
                    pages = [page.get_text() for page in doc]
                finally:
                    doc.close()
                text = "\n".join(pages).strip()
                if text:
                    return text, "pymupdf"
            except Exception:  # noqa: BLE001 - fall through to Poppler
                pass

        executable = shutil.which("pdftotext")
        if not executable:
            raise RuntimeError(
                "no PDF text extractor available (pymupdf missing, pdftotext not on PATH)"
            )
        completed = subprocess.run(
            [executable, "-layout", str(pdf_path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"exit status {completed.returncode}"
            raise RuntimeError(f"pdftotext failed: {detail}")
        return completed.stdout.strip(), "pdftotext"
    finally:
        Path(handle.name).unlink(missing_ok=True)


def extract_html_body(page_text):
    """Extract the release body from an SEC HTML page. Returns (body, method)."""
    container = extract_balanced_div(page_text, "field--name-body")
    if container is not None:
        return _drop_boilerplate(strip_html(container)), "html:field-body"

    legacy = re.search(
        r"<!--\s*BEGIN TEXT\s*-->(.*?)<!--\s*END TEXT\s*-->", page_text, re.S | re.I
    )
    if legacy:
        return _drop_boilerplate(strip_html(legacy.group(1))), "html:text-markers"

    return _drop_boilerplate(strip_html(page_text)), "html:full-page"


def _slug_and_year(release_url, date_published):
    """Return (slug, year) usable in a derived path, or (None, None)."""
    slug = release_url.rstrip("/").rsplit("/", 1)[-1].lower()
    year = (date_published or "")[:4]
    if not slug or "." in slug or not year.isdigit():
        return None, None
    return slug, year


def derive_order_pdf_url(release_url, date_published):
    """Return the order-PDF URL for a modern admin/adjudicatory stub, or None.

    The PDF is filed under the stub page's own URL slug, not under the row's
    release number: composite releases (e.g. AAER-4403 and 34-97381) share one
    page, and only the slug resolves. Only these families live under
    /files/litigation/admin/ — applying the convention to a litigation release
    produces a path that cannot exist.
    """
    if not any(marker in release_url for marker in ADMIN_PAGE_MARKERS):
        return None
    slug, year = _slug_and_year(release_url, date_published)
    if not slug:
        return None
    return ADMIN_PDF_TEMPLATE.format(year=year, slug=slug)


def derive_legacy_litrelease_url(release_url, date_published):
    """Return the legacy static litigation-release URL, or None.

    The modern slug carries a hyphen (`lr-23328`); the static file does not
    (`lr23328.htm`).
    """
    if LITIGATION_PAGE_MARKER not in release_url:
        return None
    slug, year = _slug_and_year(release_url, date_published)
    if not slug:
        return None
    return LEGACY_LITRELEASE_TEMPLATE.format(year=year, slug=slug.replace("-", ""))


def derived_body_urls(release_url, date_published):
    """Official fallback locations, in order, when a page has no usable body.

    Conventions differ by URL family and by era, so the ladder is per-family:
    cross-applying one family's path to the other yields a URL that cannot exist.
    """
    slug, year = _slug_and_year(release_url, date_published)
    if not slug:
        return []
    if any(marker in release_url for marker in ADMIN_PAGE_MARKERS):
        templates, key = ADMIN_BODY_TEMPLATES, slug
    elif LITIGATION_PAGE_MARKER in release_url:
        # The modern slug carries a hyphen (`lr-23328`), the static file does not.
        templates, key = LITIGATION_BODY_TEMPLATES, slug.replace("-", "")
    else:
        return []
    return [template.format(year=year, slug=key) for template in templates]


def resolve_body(release_url, date_published, timeout=45):
    """Fetch and extract one release body verbatim.

    Returns (body_text, extraction_method, source_url). Raises RuntimeError when
    the official source carries no retrievable body text.
    """
    content_type, raw = _fetch_raw(release_url, timeout=timeout)
    is_pdf = raw[:5] == b"%PDF-" or "application/pdf" in content_type.lower()

    if is_pdf:
        text, method = _extract_pdf_text(raw)
        if len(text) < BODY_MIN_CHARS:
            raise BodyUnavailable(
                f"PDF yielded {len(text)} chars (under {BODY_MIN_CHARS}); "
                "likely an image-only scan needing OCR"
            )
        return text, f"pdf:{method}", release_url

    page = decode_html(raw)
    if "text/plain" in content_type.lower() or not re.search(
        r"<html|<!doctype", page[:400], re.I
    ):
        text = _drop_boilerplate(page)
        if len(text) < BODY_MIN_CHARS:
            raise BodyUnavailable(f"plain-text body yielded {len(text)} chars")
        return text, "text:verbatim", release_url

    body, method = extract_html_body(page)
    if method != "html:full-page" and len(body) >= BODY_MIN_CHARS:
        return body, method, release_url

    # Either no body container at all (a stub page), or one that is present but
    # holds only the release header. Both need the derived fallbacks, which
    # differ by URL family — see the template comments above.
    tried = []
    for candidate in derived_body_urls(release_url, date_published):
        tried.append(candidate)
        try:
            cand_type, cand_raw = _fetch_raw(candidate, timeout=timeout)
        except (HTTPError, URLError):
            continue
        if cand_raw[:5] == b"%PDF-" or "application/pdf" in cand_type.lower():
            text, pdf_method = _extract_pdf_text(cand_raw)
            if len(text) >= BODY_MIN_CHARS:
                return text, f"pdf:{pdf_method}", candidate
            continue
        cand_body, cand_method = extract_html_body(decode_html(cand_raw))
        if len(cand_body) >= BODY_MIN_CHARS:
            return cand_body, cand_method, candidate

    if len(body) >= BODY_MIN_CHARS:
        return body, method, release_url
    detail = f"; derived fallbacks exhausted ({', '.join(tried)})" if tried else ""
    raise BodyUnavailable(
        f"official source published {len(body)} chars of body text "
        f"via {method}{detail}"
    )


def fetch_bodies(
    db,
    source=None,
    start=None,
    end=None,
    limit=None,
    workers=4,
    retry_failed=False,
    timeout=45,
):
    """Backfill release bodies for rows that have none. Resumable.

    Rows sharing a release_url are one document announced under several release
    numbers; each URL is fetched once and written to every row that cites it.
    """
    statuses = ["pending"] + (list(BODY_RETRY_STATUSES) if retry_failed else [])
    conditions = [
        "release_url IS NOT NULL",
        "release_url <> ''",
        "COALESCE(body_fetch_status, 'pending') IN (%s)"
        % ",".join("?" for _ in statuses),
        "(body_text IS NULL OR TRIM(body_text) = '')",
    ]
    params = list(statuses)
    if source:
        conditions.append("source_type = ?")
        params.append(source)
    if start:
        conditions.append("date_published >= ?")
        params.append(start)
    if end:
        conditions.append("date_published <= ?")
        params.append(end)

    rows = db.execute(
        f"""SELECT id, release_number, source_type, date_published, release_url
            FROM enforcement_actions
            WHERE {" AND ".join(conditions)}
            ORDER BY date_published DESC, id""",
        params,
    ).fetchall()

    # Group rows by the document they cite so each URL is fetched once.
    by_url = {}
    for row in rows:
        by_url.setdefault(row["release_url"], []).append(row)
    urls = list(by_url)
    if limit:
        urls = urls[:limit]

    print(
        f"Fetching bodies for {sum(len(by_url[u]) for u in urls):,} rows "
        f"across {len(urls):,} distinct documents ({workers} workers)"
    )

    def fetch_one(url):
        """Return (url, status, body, method, source_url, error) for one document."""
        group = by_url[url]
        try:
            body, method, source_url = resolve_body(
                url, group[0]["date_published"], timeout=timeout
            )
            return url, "complete", body, method, source_url, None
        except BodyUnavailable as exc:
            # Source reached, no text to store. Retrying will not help.
            return url, "empty", None, None, None, f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001 - recorded per row, never fatal
            return url, "failed", None, None, None, f"{type(exc).__name__}: {exc}"

    completed = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for index in range(0, len(urls), workers * 4):
            batch = urls[index : index + workers * 4]
            results = executor.map(fetch_one, batch)
            for url, status, body, method, source_url, error in results:
                ids = [row["id"] for row in by_url[url]]
                if status != "complete":
                    failed += len(ids)
                    db.executemany(
                        """UPDATE enforcement_actions
                           SET body_fetch_status = ?, body_fetch_error = ?,
                               body_fetched_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        [(status, error[:1000], row_id) for row_id in ids],
                    )
                    continue
                completed += len(ids)
                db.executemany(
                    """UPDATE enforcement_actions
                       SET body_text = ?, body_fetch_status = 'complete',
                           body_fetch_error = NULL, body_fetched_at = CURRENT_TIMESTAMP,
                           body_source_url = ?, body_extraction_method = ?
                       WHERE id = ?""",
                    [(body, source_url, method, row_id) for row_id in ids],
                )
            db.commit()
            print(
                f"  {min(index + len(batch), len(urls)):,}/{len(urls):,} documents "
                f"— {completed:,} rows stored, {failed:,} rows unresolved"
            )
    db.commit()
    return completed, failed


# ---------------------------------------------------------------------------
# Defendant name parsing
# ---------------------------------------------------------------------------

# Entity indicators — terms that signal a corporate/organizational name
ENTITY_SUFFIX_RE = re.compile(
    r"\b(LLC|L\.L\.C\.|Inc|Corp|Corporation|Ltd|LLP|L\.L\.P\.|L\.P\.|LP|Co\.|"
    r"Company|Group|Holdings|Ventures|Partners|Capital|Management|"
    r"Financial|Services|Fund|Trust|Foundation|Association|"
    r"Aktiengesellschaft|Pty|N\.?V\.?|B\.?V\.?|S\.?A\.?|GmbH|PLC|"
    r"Advisors|Advisers|Investments|Securities|Technologies|"
    r"International|Enterprises|Industries|Solutions|Network|"
    r"d/b/a|n/k/a)\b",
    re.IGNORECASE,
)

_PERSON_SUFFIX_ALT = r"Jr|Sr|II|III|IV|Esq|CPA|MD|Ph\.?D|CFP|CFA"

# Person suffixes that follow a comma (don't split on these commas). Tolerates
# repeated dots so residue from an adjacent strip can't break the rejoin, and
# stacked suffixes such as "III Esq.".
PERSON_SUFFIX_RE = re.compile(
    rf"^\s*(?:{_PERSON_SUFFIX_ALT})\.*(?:\s+(?:{_PERSON_SUFFIX_ALT})\.*)*\s*$",
    re.IGNORECASE,
)

# A suffix leading into a d/b/a clause, e.g. "Jr. d/b/a Race Cycler". The comma
# before it belongs to the person's name; the trade name is split off later.
PERSON_SUFFIX_DBA_RE = re.compile(
    rf"^\s*(?:{_PERSON_SUFFIX_ALT})\.*\s+(?:d/?b/?a|dba)\b", re.IGNORECASE
)

# Procedural role labels. SEC's respondent field mixes party-status words in with
# the party names themselves; a role label is never a party. This vocabulary is
# taken from the delimited tokens actually present in the corpus.
_ROLE_NOUN = r"""
    (?:no\s+)?                                  # "No Respondents"
    (?:(?:relief|chief)[\s\-]+)*                # "Relief Defendant", "Chief ALJ"
    (?:
        defendants? | respondents? | appellants? | petitioners?
      | movants? | intervenors? | applicants? | claimants?
      | administrative\s+law\s+judges?
    )
    (?:[\s\-]+(?:appellants?|petitioners?|respondents?|defendants?))?  # Defendant-Appellant
    (?:\s+solely\s+for\s+purposes\s+of\s+equitable\s+relief)?
"""
_ROLE_FLAGS = re.IGNORECASE | re.VERBOSE

# A candidate that is nothing but a role label — the final guard, which catches
# variants the text-level strips below miss (e.g. a label isolated by an " and "
# split later in parsing).
ROLE_LABEL_ONLY_RE = re.compile(
    rf"^\s*(?:(?:and|as)\s+)*{_ROLE_NOUN}\s*[.,;]?\s*$", _ROLE_FLAGS
)

# Role labels stripped from respondent text before splitting. Each requires an
# unambiguous boundary (parentheses, "as", or a delimiter) so a real name that
# merely contains a role word is left alone.
ROLE_STRIP_PATTERNS = [
    re.compile(rf"\s*\(\s*{_ROLE_NOUN}\s*\)", _ROLE_FLAGS),
    re.compile(rf",?\s*\b(?:and\s+)?as\s+{_ROLE_NOUN}\b", _ROLE_FLAGS),
    re.compile(rf"(?<=[,;])\s*(?:and\s+)?{_ROLE_NOUN}\s*(?=[,;]|$)", _ROLE_FLAGS),
    re.compile(rf"^\s*{_ROLE_NOUN}\s*(?=[,;])", _ROLE_FLAGS),
]

# Noise to strip from respondent text
NOISE_PATTERNS = [
    # The trailing dot must be consumed too, else "Jr., et al." leaves "Jr.."
    # and the person-suffix rejoin fails.
    re.compile(r",?\s*\bet\.?\s*al\b\.?", re.IGNORECASE),
    # Role label prefixing the names it applies to, e.g.
    # "Relief Defendants Tatiana Vorobieva and Anjali Walter".
    re.compile(r"\b(?:Relief\s+)?Defendants?\s+(?=[A-Z])", re.IGNORECASE),
    re.compile(r",?\s*and\s+\d+\s+other\s+related\s+entit\w+", re.IGNORECASE),
    re.compile(r"\s*f/k/a\s+[^,;]+", re.IGNORECASE),
]

# SEC administrative law judges appearing in this corpus, mapped to canonical
# spelling. The respondent field usually appends the presiding judge to the last
# party name with no separator ("...Anne P. Hovis James T. Kelly, Administrative
# Law Judge"), so the split point is only recoverable by matching a known name.
# This is a closed historical set: it resolves every ALJ mention in the corpus.
# "Brenda P. Murrary" is SEC's own misspelling of Brenda P. Murray.
ALJ_ROSTER = {
    "Brenda P. Murray": "Brenda P. Murray",
    "Brenda P. Murrary": "Brenda P. Murray",
    "Burton S. Kolko": "Burton S. Kolko",
    "Cameron Elliot": "Cameron Elliot",
    "Carol Fox Foelak": "Carol Fox Foelak",
    "G. Marvin Bober": "G. Marvin Bober",
    "Glenn Robert Lawrence": "Glenn Robert Lawrence",
    "H. Peter Young": "H. Peter Young",
    "Herbert Grossman": "Herbert Grossman",
    "James T. Kelly": "James T. Kelly",
    "Lillian A. McEwen": "Lillian A. McEwen",
    "Robert G. Mahony": "Robert G. Mahony",
    "William J. Cowan": "William J. Cowan",
}

ALJ_LABEL_RE = re.compile(
    r"[,;]?\s*(?:Chief\s+)?Administrative\s+Law\s+Judges?\b\.?\s*$", re.IGNORECASE
)

# Lowercase particles in person names (don't count against capitalization check)
NAME_PARTICLES = {"de", "van", "von", "al", "el", "bin", "la", "di", "del", "le", "da"}


def _alj_roster_by_length():
    """Roster spellings, longest first, so no name shadows a longer one."""
    return sorted(ALJ_ROSTER, key=len, reverse=True)


def _extract_presiding_alj(text):
    """Peel a trailing "<Judge>, Administrative Law Judge" off respondent text.

    Returns (remaining_text, canonical_judge_name_or_None). When the judge is not
    on the roster the label is still removed, but no judge is recorded and the
    text is left intact: with an unknown name there is no way to tell where the
    last party name ends, and under-claiming beats misattributing.
    """
    match = ALJ_LABEL_RE.search(text)
    if not match:
        return text, None

    head = text[: match.start()].strip()
    for variant in _alj_roster_by_length():
        if head == variant:
            return "", ALJ_ROSTER[variant]
        if head.endswith(variant) and head[-len(variant) - 1] in " ,;":
            remaining = head[: -len(variant)].strip().rstrip(",;").strip()
            return remaining, ALJ_ROSTER[variant]
    return head, None


def _tidy_delimiters(text):
    """Clean up punctuation left behind by noise and role-label stripping."""
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s*([,;])\s*(?=[,;])", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip().strip(",;").strip()


def parse_defendants(raw_text):
    """Parse the parties named in SEC enforcement respondent text.

    Returns list of dicts with: name_raw, name_normalized, defendant_type, role,
    is_et_al. `role` is 'defendant', or 'presiding_alj' for the administrative law
    judge the respondent field sometimes appends to the last party name — a judge
    is not a party to the action they heard, so callers reporting defendants must
    filter on role.

    Procedural role labels ("Relief Defendant", "Respondents") name no party and
    are dropped rather than stored.
    """
    if not raw_text or not raw_text.strip():
        return []

    text = raw_text.strip()
    is_et_al = bool(re.search(r"\bet\.?\s*al\.?\b", text, re.IGNORECASE))

    # Peel the presiding judge off first: the role label that identifies them is
    # itself stripped as noise below.
    text, alj_name = _extract_presiding_alj(text)

    # Text that is nothing but a role label names no party at all. Checked before
    # the strips below, which would otherwise leave a fragment of it behind.
    if ROLE_LABEL_ONLY_RE.match(text):
        return _finalize([], alj_name, is_et_al)

    # Strip noise
    for pat in ROLE_STRIP_PATTERNS + NOISE_PATTERNS:
        text = pat.sub("", text)
    text = _tidy_delimiters(text)

    if not text:
        return _finalize([], alj_name, is_et_al)

    # Step 1: Split on semicolons (unambiguous separator)
    parts = [p.strip() for p in text.split(";") if p.strip()]

    # Step 2: For each part, split on " and " with entity-awareness
    defendants = []
    for part in parts:
        sub_names = _split_on_and(part)
        defendants.extend(sub_names)

    # Step 3: For each candidate, further split on commas with heuristics
    final = []
    for name in defendants:
        split_names = _split_on_commas(name)
        final.extend(split_names)

    # Step 4: Classify and normalize each. d/b/a trade names are queued as
    # further candidates rather than appended to the list being iterated.
    names = []
    queue = deque(final)
    while queue:
        name = queue.popleft().strip().rstrip(",").strip()
        # Strip leading "and "
        if name.lower().startswith("and "):
            name = name[4:].strip()
        # Handle "dba" / "d/b/a" prefix — split into separate entity
        dba_m = re.match(r"^(.*?)\s*(?:d/?b/?a|dba)\s+(.+)$", name, re.IGNORECASE)
        if dba_m and dba_m.group(1).strip():
            # Keep the primary name, queue the d/b/a name as a separate entry
            name = dba_m.group(1).strip()
            dba_name = dba_m.group(2).strip()
            if dba_name and len(dba_name) >= 2:
                queue.append(dba_name)
        elif dba_m:
            name = dba_m.group(2).strip()
        if not name or len(name) < 2:
            continue
        # Strip parenthetical role labels, e.g. "Jane Roe (Relief Defendant)".
        # Left attached they corrupt name_normalized and split one party across
        # two repeat-offender rows.
        for pat in ROLE_STRIP_PATTERNS:
            name = pat.sub("", name)
        name = _tidy_delimiters(name)
        if not name or len(name) < 2:
            continue
        # Drop anything that is only a role label, or only a person suffix that
        # had no name to re-attach to (SEC text such as "Manderfeld and Esq.")
        if ROLE_LABEL_ONLY_RE.match(name) or PERSON_SUFFIX_RE.match(name):
            continue
        # Skip parenthetical state labels that leaked through
        if re.match(r"^\(?\w+\)?\s*$", name) and len(name) < 15:
            continue
        names.append(name)

    return _finalize(names, alj_name, is_et_al)


def _finalize(defendant_names, alj_name, is_et_al):
    """Classify, normalize and role-tag parsed names, dropping duplicates."""
    results = []
    seen = set()
    for name, role in [(n, "defendant") for n in defendant_names] + (
        [(alj_name, "presiding_alj")] if alj_name else []
    ):
        dtype = _classify_type(name)
        norm = _normalize(name, dtype)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        results.append(
            {
                "name_raw": name,
                "name_normalized": norm,
                "defendant_type": dtype,
                "role": role,
                # "et al." covers the parties, never the presiding judge.
                "is_et_al": is_et_al and role == "defendant",
            }
        )
    return results


def _split_on_and(text):
    """Split text on ' and ' but not when inside an entity name.

    E.g. 'Goldman, Sachs & Co. and Fabrice Tourre' -> ['Goldman, Sachs & Co.', 'Fabrice Tourre']
    But 'Landes and Compagnie Trust' stays together (entity indicators present).
    """
    # Handle ' and ' splits
    parts = re.split(r"\s+and\s+", text)
    if len(parts) <= 1:
        return [text]

    # Try to reaggregate if a split broke an entity name
    results = []
    i = 0
    while i < len(parts):
        current = parts[i].strip()
        # If next part starts with entity-ish words and current has no entity suffix,
        # they might belong together. But default is to split.
        # Heuristic: if current ends with an entity indicator (Co., Inc, etc.) or
        # next starts looking like a person name (capitalized first + last), split.
        if i + 1 < len(parts):
            next_part = parts[i + 1].strip()
            # If current looks incomplete (ends with comma or entity-like word without suffix)
            # and next part continues the entity name, re-join
            if _looks_like_entity_continuation(current, next_part):
                current = current + " and " + next_part
                i += 1
        results.append(current)
        i += 1
    return results


def _looks_like_entity_continuation(before, after):
    """Check if 'after' is a continuation of an entity name started by 'before'.

    E.g. 'Landes' + 'Compagnie Trust Prive KB' -> True (entity indicators in after)
    But 'Goldman, Sachs & Co.' + 'Fabrice Tourre' -> False (after looks like person)
    """
    # If 'after' has entity indicators, it's likely a standalone entity
    if ENTITY_SUFFIX_RE.search(after):
        return False
    # If 'before' ends with entity suffix, it's complete
    if ENTITY_SUFFIX_RE.search(before.split(",")[-1]):
        return False
    # If 'after' looks like a person name (2-4 words, first word capitalized)
    words = after.split()
    if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if len(w) > 1):
        return False
    # Default: if unsure, don't re-join (prefer splitting)
    return False


def _split_on_commas(text):
    """Split on commas, but preserve entity names with commas (e.g. 'Goldman, Sachs & Co.').

    Strategy: split on commas, then re-attach tokens that are entity suffixes,
    person suffixes, or continuations of entity names.
    """
    tokens = text.split(",")
    if len(tokens) <= 1:
        return [text]

    results = []
    i = 0
    while i < len(tokens):
        current = tokens[i].strip()
        if not current:
            i += 1
            continue

        # Look ahead: if next token is a person suffix (Jr., CPA), attach it
        while i + 1 < len(tokens):
            next_tok = tokens[i + 1].strip()
            if PERSON_SUFFIX_RE.match(next_tok) or PERSON_SUFFIX_DBA_RE.match(next_tok):
                current = current + ", " + next_tok
                i += 1
            elif _is_entity_suffix_token(next_tok):
                # E.g. "Power Up Lending Group" + "Ltd." or "Integrity Financial AZ" + "LLC"
                current = current + ", " + next_tok
                i += 1
            elif _is_state_label(next_tok):
                # E.g. "Trade with Ayasa, LLC (Texas)"
                current = current + ", " + next_tok
                i += 1
            else:
                break

        # Strip leading "and " from names
        if current.lower().startswith("and "):
            current = current[4:].strip()

        if current:
            results.append(current)
        i += 1

    return results


def _is_entity_suffix_token(token):
    """Check if a token is purely an entity suffix (e.g. 'LLC', 'Inc.', 'Ltd.')."""
    clean = token.strip().rstrip(".").strip().lower()
    suffixes = {
        "llc", "inc", "corp", "ltd", "lp", "llp", "co", "plc", "sa", "ag",
        "gmbh", "nv", "bv", "l.l.c", "l.l.p", "l.p",
    }
    return clean in suffixes


def _is_state_label(token):
    """Check if token is a parenthetical state label like '(Texas)' or '(Wyoming)'."""
    return bool(re.match(r"^\([A-Z][a-z]+\)$", token.strip()))


def _classify_type(name):
    """Classify a defendant name as 'person', 'entity', or 'unknown'."""
    if ENTITY_SUFFIX_RE.search(name):
        return "entity"
    # Check for common entity patterns without formal suffixes
    lower = name.lower()
    for indicator in ["bank", "credit union", "exchange"]:
        if indicator in lower:
            return "entity"
    # Person heuristic: 2-5 words where non-particle words are capitalized
    words = [w for w in name.split() if w and not w.startswith("(")]
    if 2 <= len(words) <= 5:
        alpha_words = [w for w in words if w[0].isalpha()]
        if alpha_words and all(
            w[0].isupper()
            or w.lower() in NAME_PARTICLES
            or _is_camelcase_name(w)  # e.g. deMora, deLuca
            for w in alpha_words
        ):
            return "person"
    return "unknown"


def _is_camelcase_name(word):
    """Check if word is a camelCase name part (e.g. deMora, deLuca, McBride)."""
    return bool(re.match(r"^[a-z]{1,3}[A-Z]", word))


def _normalize(name, dtype):
    """Normalize a defendant name using entity_resolution functions if available."""
    try:
        from tools.entity_resolution import normalize_entity_name, normalize_person_name
    except ImportError:
        try:
            from entity_resolution import normalize_entity_name, normalize_person_name
        except ImportError:
            # Fallback: basic normalization
            return re.sub(r"\s+", " ", name.strip().lower())

    if dtype == "entity":
        return normalize_entity_name(name)
    elif dtype == "person":
        return normalize_person_name(name)
    else:
        # Try person normalization (strips more noise)
        return normalize_person_name(name)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def ingest_source(db, source_type, max_pages=None, incremental=False):
    """Scrape one SEC enforcement source type. Returns (actions_found, actions_new, defendants)."""
    base_url = SOURCE_URLS[source_type]
    page = 0
    total_found = 0
    total_new = 0
    total_defendants = 0

    while True:
        if max_pages is not None and page >= max_pages:
            break

        url = f"{base_url}?page={page}"
        html = _request(url)
        if html is None:
            break

        actions = parse_page(html, source_type)
        if not actions:
            break

        page_new = 0
        page_defendants = 0
        for action in actions:
            # Handle composite release numbers (e.g. "34-105022, AAER-4588")
            release_numbers = [
                rn.strip()
                for rn in action["release_number"].split(",")
                if rn.strip()
            ]

            for rn in release_numbers:
                # Determine source_type from release number prefix
                st = _source_type_from_release(rn, source_type)

                try:
                    db.execute(
                        """INSERT INTO enforcement_actions
                           (release_number, source_type, date_published, datetime_published,
                            respondent_text, release_url, file_number, see_also_text, see_also_url)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            rn,
                            st,
                            action["date_published"],
                            action.get("datetime_published"),
                            action["respondent_text"],
                            action.get("release_url"),
                            action.get("file_number"),
                            action.get("see_also_text"),
                            action.get("see_also_url"),
                        ),
                    )
                    action_id = db.execute(
                        "SELECT last_insert_rowid()"
                    ).fetchone()[0]
                    page_new += 1

                    # Parse and insert defendants
                    defs = parse_defendants(action["respondent_text"])
                    for d in defs:
                        try:
                            db.execute(
                                """INSERT INTO enforcement_defendants
                                   (action_id, name_raw, name_normalized,
                                    defendant_type, is_et_al, role)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (
                                    action_id,
                                    d["name_raw"],
                                    d["name_normalized"],
                                    d["defendant_type"],
                                    1 if d["is_et_al"] else 0,
                                    d["role"],
                                ),
                            )
                            page_defendants += 1
                        except sqlite3.IntegrityError:
                            pass  # Duplicate defendant for this action

                except sqlite3.IntegrityError:
                    pass  # Duplicate release_number + source_type

        db.commit()
        total_found += len(actions)
        total_new += page_new
        total_defendants += page_defendants

        print(
            f"  {source_type} page {page}: {len(actions)} actions "
            f"({page_new} new, {page_defendants} defendants)"
        )

        # Incremental mode: stop if entire page already existed
        if incremental and page_new == 0:
            print(f"  {source_type}: all entries on page {page} already exist, stopping")
            break

        page += 1

    return total_found, total_new, total_defendants


def _source_type_from_release(release_number, default_type):
    """Infer source_type from release number prefix."""
    rn = release_number.strip().upper()
    if rn.startswith("LR-"):
        return "litigation"
    elif rn.startswith("AAER-"):
        return "aaer"
    elif rn.startswith("IA-") or rn.startswith("34-") or rn.startswith("33-"):
        return "admin"
    return default_type


# ---------------------------------------------------------------------------
# Reparse
# ---------------------------------------------------------------------------


def reparse_defendants(db):
    """Re-run defendant parsing on all stored respondent_text."""
    # Matches point at defendant rows by id, so they cannot outlive a rebuild.
    # Report the loss rather than dropping it silently.
    dropped_matches = db.execute("SELECT COUNT(*) FROM enforcement_matches").fetchone()[0]
    if dropped_matches:
        print(
            f"Dropping {dropped_matches} enforcement_matches rows "
            "(cascaded from rebuilt defendants) — re-run cross-ref afterwards"
        )

    # Clear existing defendants
    db.execute("DELETE FROM enforcement_defendants")
    # Rebuild FTS
    db.execute(
        "INSERT INTO enforcement_defendants_fts(enforcement_defendants_fts) VALUES('rebuild')"
    )
    db.commit()

    rows = db.execute(
        "SELECT id, respondent_text FROM enforcement_actions ORDER BY id"
    ).fetchall()

    total = 0
    by_role = Counter()
    for row in rows:
        defs = parse_defendants(row["respondent_text"])
        for d in defs:
            try:
                db.execute(
                    """INSERT INTO enforcement_defendants
                       (action_id, name_raw, name_normalized,
                        defendant_type, is_et_al, role)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        row["id"],
                        d["name_raw"],
                        d["name_normalized"],
                        d["defendant_type"],
                        1 if d["is_et_al"] else 0,
                        d["role"],
                    ),
                )
                total += 1
                by_role[d["role"]] += 1
            except sqlite3.IntegrityError:
                pass

    db.commit()
    breakdown = ", ".join(f"{n} {role}" for role, n in sorted(by_role.items()))
    print(f"Reparsed {len(rows)} actions → {total} parties ({breakdown})")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def show_stats(db, args):
    """Show summary statistics."""
    results = {}

    # Action counts by source
    rows = db.execute(
        """SELECT source_type, COUNT(*) as cnt
           FROM enforcement_actions GROUP BY source_type ORDER BY source_type"""
    ).fetchall()
    results["actions_by_source"] = {r["source_type"]: r["cnt"] for r in rows}
    results["total_actions"] = sum(r["cnt"] for r in rows)

    # Defendant counts by type
    rows = db.execute(
        """SELECT defendant_type, COUNT(*) as cnt
           FROM enforcement_defendants GROUP BY defendant_type ORDER BY cnt DESC"""
    ).fetchall()
    results["defendants_by_type"] = {r["defendant_type"]: r["cnt"] for r in rows}
    results["total_defendants"] = sum(r["cnt"] for r in rows)

    # Date range
    row = db.execute(
        "SELECT MIN(date_published) as earliest, MAX(date_published) as latest FROM enforcement_actions"
    ).fetchone()
    results["date_range"] = {"earliest": row["earliest"], "latest": row["latest"]}

    # Actions by year (top 10)
    rows = db.execute(
        """SELECT SUBSTR(date_published, 1, 4) as year, COUNT(*) as cnt
           FROM enforcement_actions GROUP BY year ORDER BY year DESC LIMIT 10"""
    ).fetchall()
    results["actions_by_year"] = {r["year"]: r["cnt"] for r in rows}

    # Repeat offenders
    row = db.execute(
        """SELECT COUNT(*) as cnt FROM (
            SELECT name_normalized FROM enforcement_defendants
            GROUP BY name_normalized HAVING COUNT(DISTINCT action_id) >= 2
        )"""
    ).fetchone()
    results["repeat_offenders"] = row["cnt"]

    # Et al actions
    row = db.execute(
        "SELECT COUNT(DISTINCT action_id) as cnt FROM enforcement_defendants WHERE is_et_al = 1"
    ).fetchone()
    results["et_al_actions"] = row["cnt"]

    # Body coverage — surfaced so a silently empty text layer cannot recur
    row = db.execute(
        """SELECT COUNT(*) AS total,
                  SUM(TRIM(COALESCE(body_text, '')) <> '') AS with_body
           FROM enforcement_actions"""
    ).fetchone()
    rows = db.execute(
        """SELECT COALESCE(body_fetch_status, 'pending') AS status, COUNT(*) AS cnt
           FROM enforcement_actions GROUP BY status ORDER BY cnt DESC"""
    ).fetchall()
    results["body_coverage"] = {
        "rows_with_body": row["with_body"] or 0,
        "rows_total": row["total"] or 0,
        "pct": round(100.0 * (row["with_body"] or 0) / (row["total"] or 1), 1),
        "by_status": {r["status"]: r["cnt"] for r in rows},
    }

    # Ingest log (last 5)
    rows = db.execute(
        "SELECT * FROM enforcement_ingest_log ORDER BY id DESC LIMIT 5"
    ).fetchall()
    results["recent_ingests"] = [dict(r) for r in rows]

    if write_output(results, args, summary="SEC enforcement stats"):
        return

    print(f"SEC Enforcement Database: {DB_PATH}")
    print(f"  Total actions:     {results['total_actions']:,}")
    for src, cnt in sorted(results["actions_by_source"].items()):
        print(f"    {src:12s} {cnt:,}")
    print(f"  Total defendants:  {results['total_defendants']:,}")
    for dtype, cnt in sorted(results["defendants_by_type"].items(), key=lambda x: -x[1]):
        print(f"    {dtype or 'null':12s} {cnt:,}")
    coverage = results["body_coverage"]
    print(
        f"  Bodies fetched:    {coverage['rows_with_body']:,}/{coverage['rows_total']:,} "
        f"({coverage['pct']}%)"
    )
    for status, cnt in coverage["by_status"].items():
        print(f"    {status:12s} {cnt:,}")
    print(f"  Date range:        {results['date_range']['earliest']} to {results['date_range']['latest']}")
    print(f"  Repeat offenders:  {results['repeat_offenders']:,} (appeared in 2+ actions)")
    print(f"  Et al. actions:    {results['et_al_actions']:,}")
    print("\n  Actions by year (recent):")
    for year, cnt in sorted(results["actions_by_year"].items(), reverse=True):
        print(f"    {year}: {cnt:,}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_ingest(args):
    db = get_db()
    sources = [args.source] if args.source else ["litigation", "admin", "aaer"]

    for source_type in sources:
        print(f"Ingesting {source_type} releases...")
        found, new, defs = ingest_source(
            db,
            source_type,
            max_pages=args.pages,
            incremental=args.incremental,
        )
        # Log the ingest
        db.execute(
            """INSERT INTO enforcement_ingest_log
               (source_type, pages_scraped, actions_found, actions_new, defendants_parsed)
               VALUES (?, ?, ?, ?, ?)""",
            (source_type, args.pages or -1, found, new, defs),
        )
        db.commit()
        print(f"  {source_type} done: {found} found, {new} new actions, {defs} defendants\n")

    db.close()


def cmd_fetch_bodies(args):
    db = get_db()
    completed, failed = fetch_bodies(
        db,
        source=args.source,
        start=args.start,
        end=args.end,
        limit=args.limit,
        workers=args.workers,
        retry_failed=args.retry_failed,
        timeout=args.timeout,
    )
    print(f"\nBody fetch done: {completed:,} rows stored, {failed:,} rows unresolved")
    db.close()


def cmd_stats(args):
    db = get_db()
    show_stats(db, args)
    db.close()


def cmd_reparse(args):
    db = get_db()
    reparse_defendants(db)
    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Ingest SEC enforcement actions"
    )
    sub = parser.add_subparsers(dest="command")

    # ingest
    p_ingest = sub.add_parser("ingest", help="Scrape SEC enforcement pages")
    p_ingest.add_argument(
        "--source",
        choices=["litigation", "admin", "aaer"],
        help="Source type (default: all)",
    )
    p_ingest.add_argument(
        "--pages", type=int, help="Max pages per source (default: all)"
    )
    p_ingest.add_argument(
        "--incremental",
        action="store_true",
        help="Stop when hitting existing entries",
    )

    # fetch-bodies
    p_bodies = sub.add_parser(
        "fetch-bodies",
        help="Fetch full release text for rows that have none (resumable)",
    )
    p_bodies.add_argument(
        "--source",
        choices=["litigation", "admin", "aaer"],
        help="Source type (default: all)",
    )
    p_bodies.add_argument("--start", help="Earliest date_published (YYYY-MM-DD)")
    p_bodies.add_argument("--end", help="Latest date_published (YYYY-MM-DD)")
    p_bodies.add_argument(
        "--limit", type=int, help="Max distinct documents to fetch this run"
    )
    p_bodies.add_argument(
        "--workers", type=int, default=4, help="Concurrent fetches (default: 4)"
    )
    p_bodies.add_argument(
        "--retry-failed",
        action="store_true",
        help="Also re-attempt rows previously marked failed or empty",
    )
    p_bodies.add_argument(
        "--timeout", type=int, default=45, help="Per-request timeout seconds"
    )

    # stats
    p_stats = sub.add_parser("stats", help="Show database statistics")
    add_output_args(p_stats)

    # reparse
    sub.add_parser("reparse", help="Re-run defendant name parsing")

    args = parser.parse_args()
    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "fetch-bodies":
        cmd_fetch_bodies(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "reparse":
        cmd_reparse(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
