#!/usr/bin/env python3
"""
Ingest USPTO Patent Assignment bulk data into a local SQLite database.

Downloads annual XML backfiles and daily front files from the USPTO Open Data
Portal, parses PADX v0.3 XML, and loads into datasets/patent_assignments_bulk.db.

Data source: https://data.uspto.gov/bulkdata/datasets/pasyr (annual)
             https://data.uspto.gov/bulkdata/datasets/pasdl (daily)

Usage:
    uv run python scripts/ingest_patent_assignments.py --discover
    uv run python scripts/ingest_patent_assignments.py --year 2023
    uv run python scripts/ingest_patent_assignments.py --daily --days 7
    uv run python scripts/ingest_patent_assignments.py --stats
    uv run python scripts/ingest_patent_assignments.py --query "SECURITY" --country "RUSSIA"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("ERROR: requests not found. Run: uv add requests", file=sys.stderr)
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # Graceful fallback

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "datasets" / "patent_assignments_bulk.db"
DOWNLOAD_DIR = BASE_DIR / "datasets" / "patent_assignments"

# USPTO ODP Bulk Data API (discovered via network inspection of the Angular SPA)
ODP_SEARCH_API = "https://data.uspto.gov/api/v1/datasets/products/search"
ODP_PRODUCT_API = "https://data.uspto.gov/api/v1/datasets/products"
ODP_DOWNLOAD_BASE = "https://data.uspto.gov/bulkdata"

# Known annual file URL pattern (based on USPTO documentation)
# Annual files: pasyr product, named like ad{start}-{end}.zip
# Daily files: pasdl product, named like ad{YYYYMMDD}.zip
ANNUAL_PRODUCT = "pasyr"
DAILY_PRODUCT = "pasdl"

# User agent for downloads
USER_AGENT = "Ithildin-OSINT/1.0 (research; patent-assignment-bulk-ingest)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- Patent assignment records
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reel_no TEXT NOT NULL,
    frame_no TEXT NOT NULL,
    conveyance_text TEXT,
    date_recorded TEXT,
    correspondent_name TEXT,
    correspondent_address TEXT,
    source_file TEXT,
    ingested_at TEXT DEFAULT (datetime('now')),
    UNIQUE(reel_no, frame_no)
);

-- Assignors (who is transferring)
CREATE TABLE IF NOT EXISTS assignors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id),
    name TEXT NOT NULL,
    execution_date TEXT,
    UNIQUE(assignment_id, name)
);

-- Assignees (who is receiving)
CREATE TABLE IF NOT EXISTS assignees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id),
    name TEXT NOT NULL,
    city TEXT,
    state TEXT,
    country TEXT,
    postcode TEXT,
    UNIQUE(assignment_id, name)
);

-- Patent/application properties affected by the assignment
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id),
    patent_number TEXT,
    application_number TEXT,
    invention_title TEXT,
    filing_date TEXT,
    issue_date TEXT,
    UNIQUE(assignment_id, patent_number, application_number)
);

-- Track which files have been ingested
CREATE TABLE IF NOT EXISTS ingest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    file_hash TEXT,
    record_count INTEGER,
    error_count INTEGER DEFAULT 0,
    ingested_at TEXT DEFAULT (datetime('now')),
    duration_seconds REAL
);

-- Indexes for common search patterns
CREATE INDEX IF NOT EXISTS idx_assignees_name ON assignees(name);
CREATE INDEX IF NOT EXISTS idx_assignees_name_upper ON assignees(UPPER(name));
CREATE INDEX IF NOT EXISTS idx_assignees_country ON assignees(country);
CREATE INDEX IF NOT EXISTS idx_assignees_city ON assignees(city);
CREATE INDEX IF NOT EXISTS idx_assignees_state ON assignees(state);
CREATE INDEX IF NOT EXISTS idx_assignors_name ON assignors(name);
CREATE INDEX IF NOT EXISTS idx_assignors_name_upper ON assignors(UPPER(name));
CREATE INDEX IF NOT EXISTS idx_assignments_conveyance ON assignments(conveyance_text);
CREATE INDEX IF NOT EXISTS idx_assignments_date_recorded ON assignments(date_recorded);
CREATE INDEX IF NOT EXISTS idx_assignments_reel_frame ON assignments(reel_no, frame_no);
CREATE INDEX IF NOT EXISTS idx_properties_patent ON properties(patent_number);
CREATE INDEX IF NOT EXISTS idx_properties_app ON properties(application_number);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create or open the database and ensure schema exists."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def discover_files_via_api(product: str) -> list[dict]:
    """Discover available files via the ODP product API.

    The ODP API requires browser-like headers (Referer from data.uspto.gov)
    to pass the AWS WAF. The actual endpoint is:
      GET /ui/datasets/products/{product}?includeFiles=true&fileDataFromDate=...&fileDataToDate=...
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://data.uspto.gov/bulkdata/datasets/{product.lower()}",
    })

    url = (f"https://data.uspto.gov/ui/datasets/products/{product.lower()}"
           f"?includeFiles=true&fileDataFromDate=1980-01-01&fileDataToDate=2030-12-31")

    try:
        resp = session.get(url, timeout=60)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "json" in ct:
                data = resp.json()
                bag = data.get("bulkDataProductBag", [])
                if bag:
                    product_data = bag[0]
                    file_bag = product_data.get("productFileBag", {})
                    file_list = file_bag.get("fileDataBag", [])
                    log.info(f"Found {len(file_list)} files via ODP API "
                             f"({product_data.get('productTitleText', '')})")

                    files = []
                    for f in file_list:
                        files.append({
                            "filename": f["fileName"],
                            "url": f["fileDownloadURI"],
                            "size": f["fileSize"],
                            "from_date": f.get("fileDataFromDate", ""),
                            "to_date": f.get("fileDataToDate", ""),
                            "release_date": f.get("fileReleaseDate", ""),
                        })
                    return files
    except Exception as e:
        log.error(f"ODP API discovery failed: {e}")

    log.warning("ODP API not accessible. Using known URL patterns.")
    return []


def discover_files_via_playwright(product: str) -> list[dict]:
    """Use Playwright to load the ODP SPA and extract file download URLs."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("Playwright not installed. Cannot discover files via browser. "
                     "Install with: uv add playwright && uv run playwright install chromium")
        return []

    files = []
    url = f"https://data.uspto.gov/bulkdata/datasets/{product}"

    log.info(f"Launching browser to discover files at {url} ...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Intercept XHR/fetch requests to find the actual API calls
            api_responses = []

            def handle_response(response):
                if "api" in response.url and response.status == 200:
                    try:
                        body = response.json()
                        api_responses.append({"url": response.url, "data": body})
                    except Exception:
                        pass

            page.on("response", handle_response)
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for file table to render
            try:
                page.wait_for_selector("table", timeout=10000)
            except Exception:
                pass

            # Extract file links from the rendered page
            links = page.eval_on_selector_all(
                "a[href*='.zip'], a[download]",
                "els => els.map(e => ({href: e.href, text: e.textContent.trim()}))"
            )
            for link in links:
                files.append({
                    "filename": link.get("text", ""),
                    "url": link.get("href", ""),
                })

            # Also check captured API responses
            for resp in api_responses:
                log.info(f"Captured API call: {resp['url']}")
                data = resp["data"]
                if isinstance(data, dict) and "files" in data:
                    for f in data["files"]:
                        files.append(f)

            browser.close()

    except Exception as e:
        log.error(f"Playwright discovery failed: {e}")

    log.info(f"Discovered {len(files)} files via browser")
    return files


def generate_known_annual_urls() -> list[dict]:
    """Generate annual file URLs based on known naming conventions.

    The USPTO patent assignment annual XML files are NOT per-year.
    They are split into numbered parts covering the full date range:
    - Series 1: ad19800101-20241231-{01..22}.zip (22 files, ~82-130 MB each)
    - Series 2: ad19880101-20241231-{01..26}.zip (26 files, ~127-169 MB each)
    - Series 3: ad19880101-20251231-{01..26}.zip (26 files, ~122-169 MB each)

    Each part contains assignments from different reel number ranges
    across the full time period.
    """
    files = []
    base_url = "https://data.uspto.gov/ui/datasets/products/files/PASYR"

    # Series with known file counts (most recent backfile = 2025 series)
    series = [
        ("ad19880101-20251231", 26),  # Latest: 1988-2025, 26 parts
    ]

    for prefix, count in series:
        for i in range(1, count + 1):
            filename = f"{prefix}-{i:02d}.zip"
            url = f"{base_url}/{filename}"
            files.append({
                "filename": filename,
                "url": url,
                "part": i,
            })

    return files


def discover_daily_files_via_api(days: int = 30) -> list[dict]:
    """Discover daily files via the ODP product API."""
    today = datetime.now()
    from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    return discover_files_via_api_with_dates(DAILY_PRODUCT, from_date, to_date)


def discover_files_via_api_with_dates(product: str, from_date: str, to_date: str) -> list[dict]:
    """Discover files for a specific date range."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://data.uspto.gov/bulkdata/datasets/{product.lower()}",
    })

    url = (f"https://data.uspto.gov/ui/datasets/products/{product.lower()}"
           f"?includeFiles=true&fileDataFromDate={from_date}&fileDataToDate={to_date}")

    try:
        resp = session.get(url, timeout=60)
        if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
            data = resp.json()
            bag = data.get("bulkDataProductBag", [])
            if bag:
                file_list = bag[0].get("productFileBag", {}).get("fileDataBag", [])
                files = []
                for f in file_list:
                    files.append({
                        "filename": f["fileName"],
                        "url": f["fileDownloadURI"],
                        "size": f["fileSize"],
                        "from_date": f.get("fileDataFromDate", ""),
                        "to_date": f.get("fileDataToDate", ""),
                        "release_date": f.get("fileReleaseDate", ""),
                    })
                return files
    except Exception as e:
        log.error(f"Daily file discovery failed: {e}")

    return []


def generate_daily_urls(days: int = 7) -> list[dict]:
    """Generate daily file URLs for the last N days (fallback if API fails)."""
    files = []
    today = datetime.now()
    base_url = "https://data.uspto.gov/ui/datasets/products/files/PASDL"

    for i in range(days):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y%m%d")
        filename = f"ad{date_str}.zip"
        url = f"{base_url}/{filename}"
        files.append({
            "filename": filename,
            "url": url,
            "date": date_str,
        })

    return files


# ---------------------------------------------------------------------------
# Download with resume
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, session: Optional[requests.Session] = None,
                  max_retries: int = 3) -> bool:
    """Download a file with resume capability and progress display."""
    if session is None:
        session = requests.Session()
    # Must use browser-like headers to pass AWS WAF
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": "https://data.uspto.gov/bulkdata/datasets/pasyr",
    })

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Check if partially downloaded
    headers = {}
    existing_size = 0
    if dest.exists():
        existing_size = dest.stat().st_size
        headers["Range"] = f"bytes={existing_size}-"

    for attempt in range(max_retries):
        try:
            resp = session.get(url, headers=headers, stream=True, timeout=60)

            if resp.status_code == 416:
                # Range not satisfiable - file already complete
                log.info(f"Already downloaded: {dest.name}")
                return True

            if resp.status_code == 404:
                log.warning(f"File not found (404): {url}")
                return False

            if resp.status_code == 403:
                log.warning(f"Access denied (403): {url} — may need browser download")
                return False

            if resp.status_code not in (200, 206):
                log.warning(f"HTTP {resp.status_code} for {url}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return False

            # Check content type — if HTML, it's the SPA catch-all, not a real file
            ct = resp.headers.get("content-type", "")
            if "text/html" in ct:
                log.warning(f"Got HTML instead of ZIP for {url} — URL pattern incorrect or WAF blocked")
                return False

            total_size = int(resp.headers.get("content-length", 0))
            if resp.status_code == 206:
                total_size += existing_size

            mode = "ab" if resp.status_code == 206 else "wb"

            desc = dest.name
            if tqdm:
                progress = tqdm(
                    total=total_size,
                    initial=existing_size if resp.status_code == 206 else 0,
                    unit="B",
                    unit_scale=True,
                    desc=desc,
                )
            else:
                log.info(f"Downloading {desc} ({total_size / 1024 / 1024:.1f} MB)...")
                progress = None

            with open(dest, mode) as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    if progress:
                        progress.update(len(chunk))

            if progress:
                progress.close()

            log.info(f"Downloaded: {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
            return True

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            log.warning(f"Download error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return False


# ---------------------------------------------------------------------------
# XML parsing (PADX v0.3)
# ---------------------------------------------------------------------------

def safe_text(element, xpath: str, default: str = "") -> str:
    """Safely extract text from an XML element."""
    el = element.find(xpath)
    if el is not None and el.text:
        return el.text.strip()
    return default


def parse_patent_assignment(elem) -> Optional[dict]:
    """Parse a single <patent-assignment> element into a dict."""
    try:
        record = elem.find("assignment-record")
        if record is None:
            return None

        assignment = {
            "reel_no": safe_text(record, "reel-no"),
            "frame_no": safe_text(record, "frame-no"),
            "conveyance_text": safe_text(record, "conveyance-text"),
            "date_recorded": safe_text(record, "recorded-date/date"),
            "correspondent_name": safe_text(record, "correspondent/name"),
            "correspondent_address": "",
        }

        # Build correspondent address
        corr = record.find("correspondent")
        if corr is not None:
            addr_parts = []
            for tag in ["address-1", "address-2", "address-3", "address-4"]:
                val = safe_text(corr, tag)
                if val:
                    addr_parts.append(val)
            assignment["correspondent_address"] = "; ".join(addr_parts)

        if not assignment["reel_no"] or not assignment["frame_no"]:
            return None

        # Parse assignors
        assignors = []
        assignors_elem = elem.find("patent-assignors")
        if assignors_elem is not None:
            for assignor_elem in assignors_elem.findall("patent-assignor"):
                name = safe_text(assignor_elem, "name")
                if name:
                    assignors.append({
                        "name": name,
                        "execution_date": safe_text(assignor_elem, "execution-date/date"),
                    })

        # Parse assignees
        assignees = []
        assignees_elem = elem.find("patent-assignees")
        if assignees_elem is not None:
            for assignee_elem in assignees_elem.findall("patent-assignee"):
                name = safe_text(assignee_elem, "name")
                if name:
                    assignees.append({
                        "name": name,
                        "city": safe_text(assignee_elem, "city") or safe_text(assignee_elem, "address/city"),
                        "state": safe_text(assignee_elem, "state") or safe_text(assignee_elem, "address/state"),
                        "country": safe_text(assignee_elem, "country-name") or safe_text(assignee_elem, "address/country-name"),
                        "postcode": safe_text(assignee_elem, "postcode") or safe_text(assignee_elem, "address/postcode"),
                    })

        # Parse properties (patents/applications)
        properties = []
        props_elem = elem.find("patent-properties")
        if props_elem is not None:
            for prop_elem in props_elem.findall("patent-property"):
                doc_id = prop_elem.find("document-id")
                if doc_id is not None:
                    properties.append({
                        "patent_number": safe_text(doc_id, "doc-number"),
                        "application_number": safe_text(prop_elem, "application-number/doc-number")
                                              or safe_text(doc_id, "doc-number"),
                        "invention_title": safe_text(prop_elem, "invention-title"),
                        "filing_date": safe_text(doc_id, "date"),
                        "issue_date": "",
                    })

        assignment["assignors"] = assignors
        assignment["assignees"] = assignees
        assignment["properties"] = properties

        return assignment

    except Exception as e:
        log.debug(f"Error parsing assignment: {e}")
        return None


def iter_assignments_from_xml(xml_content: bytes):
    """Iterate over patent-assignment elements using incremental parsing."""
    # Use iterparse for memory efficiency on large XML files
    try:
        context = ET.iterparse(BytesIO(xml_content), events=("end",))
        for event, elem in context:
            if elem.tag == "patent-assignment":
                result = parse_patent_assignment(elem)
                if result:
                    yield result
                elem.clear()
    except ET.ParseError as e:
        log.error(f"XML parse error: {e}")
        # Try to recover by finding individual assignment blocks
        log.info("Attempting recovery parse...")
        text = xml_content.decode("utf-8", errors="replace")
        pattern = re.compile(
            r"<patent-assignment>.*?</patent-assignment>",
            re.DOTALL
        )
        for match in pattern.finditer(text):
            try:
                elem = ET.fromstring(match.group())
                result = parse_patent_assignment(elem)
                if result:
                    yield result
            except ET.ParseError:
                continue


# ---------------------------------------------------------------------------
# Database insertion
# ---------------------------------------------------------------------------

def insert_assignments(conn: sqlite3.Connection, assignments: list[dict],
                       source_file: str, batch_size: int = 5000) -> tuple[int, int]:
    """Insert parsed assignments into the database. Returns (inserted, errors)."""
    inserted = 0
    errors = 0
    cur = conn.cursor()

    batch = []

    for asn in assignments:
        batch.append(asn)

        if len(batch) >= batch_size:
            i, e = _flush_batch(cur, batch, source_file)
            inserted += i
            errors += e
            batch = []
            conn.commit()

    if batch:
        i, e = _flush_batch(cur, batch, source_file)
        inserted += i
        errors += e
        conn.commit()

    return inserted, errors


def _flush_batch(cur: sqlite3.Cursor, batch: list[dict], source_file: str) -> tuple[int, int]:
    """Flush a batch of assignments to the database."""
    inserted = 0
    errors = 0

    for asn in batch:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO assignments (reel_no, frame_no, conveyance_text,
                    date_recorded, correspondent_name, correspondent_address, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                asn["reel_no"], asn["frame_no"], asn["conveyance_text"],
                asn["date_recorded"], asn["correspondent_name"],
                asn["correspondent_address"], source_file,
            ))

            if cur.rowcount == 0:
                # Already exists (dedup via UNIQUE constraint)
                continue

            assignment_id = cur.lastrowid

            for assignor in asn.get("assignors", []):
                cur.execute("""
                    INSERT OR IGNORE INTO assignors (assignment_id, name, execution_date)
                    VALUES (?, ?, ?)
                """, (assignment_id, assignor["name"], assignor.get("execution_date", "")))

            for assignee in asn.get("assignees", []):
                cur.execute("""
                    INSERT OR IGNORE INTO assignees (assignment_id, name, city, state, country, postcode)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    assignment_id, assignee["name"],
                    assignee.get("city", ""), assignee.get("state", ""),
                    assignee.get("country", ""), assignee.get("postcode", ""),
                ))

            for prop in asn.get("properties", []):
                cur.execute("""
                    INSERT OR IGNORE INTO properties (assignment_id, patent_number,
                        application_number, invention_title, filing_date, issue_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    assignment_id, prop.get("patent_number", ""),
                    prop.get("application_number", ""),
                    prop.get("invention_title", ""),
                    prop.get("filing_date", ""), prop.get("issue_date", ""),
                ))

            inserted += 1

        except Exception as e:
            errors += 1
            log.debug(f"Insert error for reel {asn.get('reel_no')}/{asn.get('frame_no')}: {e}")

    return inserted, errors


# ---------------------------------------------------------------------------
# Ingest pipeline
# ---------------------------------------------------------------------------

def ingest_zip(conn: sqlite3.Connection, zip_path: Path,
               progress_bar: bool = True) -> tuple[int, int]:
    """Ingest a ZIP file containing PADX XML."""
    filename = zip_path.name

    # Check if already ingested
    cur = conn.cursor()
    cur.execute("SELECT record_count FROM ingest_log WHERE filename = ?", (filename,))
    existing = cur.fetchone()
    if existing:
        log.info(f"Already ingested: {filename} ({existing[0]} records)")
        return existing[0], 0

    log.info(f"Ingesting: {filename} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
    start_time = time.time()

    # Compute file hash for integrity tracking
    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    file_hash = sha256.hexdigest()

    total_inserted = 0
    total_errors = 0

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            xml_files = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not xml_files:
                log.warning(f"No XML files found in {filename}")
                return 0, 0

            for xml_name in xml_files:
                log.info(f"  Parsing: {xml_name}")
                xml_content = zf.read(xml_name)

                assignments = list(iter_assignments_from_xml(xml_content))
                log.info(f"  Parsed {len(assignments)} assignment records")

                if assignments:
                    inserted, errors = insert_assignments(conn, assignments, filename)
                    total_inserted += inserted
                    total_errors += errors
                    log.info(f"  Inserted: {inserted}, Errors: {errors}")

    except zipfile.BadZipFile:
        log.error(f"Corrupt ZIP file: {filename}")
        return 0, 1

    duration = time.time() - start_time

    # Log the ingest
    conn.execute("""
        INSERT OR REPLACE INTO ingest_log (filename, file_hash, record_count, error_count, duration_seconds)
        VALUES (?, ?, ?, ?, ?)
    """, (filename, file_hash, total_inserted, total_errors, duration))
    conn.commit()

    log.info(f"Completed: {filename} — {total_inserted} records in {duration:.1f}s")
    return total_inserted, total_errors


def ingest_from_url(conn: sqlite3.Connection, url: str, filename: str,
                    session: Optional[requests.Session] = None) -> tuple[int, int]:
    """Download and ingest a file from a URL."""
    dest = DOWNLOAD_DIR / filename

    if not dest.exists():
        success = download_file(url, dest, session)
        if not success:
            return 0, 0

    return ingest_zip(conn, dest)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def show_stats(conn: sqlite3.Connection):
    """Display database statistics."""
    cur = conn.cursor()

    print("\n=== USPTO Patent Assignment Database Statistics ===\n")

    cur.execute("SELECT COUNT(*) FROM assignments")
    print(f"Total assignments:  {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(*) FROM assignors")
    print(f"Total assignors:    {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(*) FROM assignees")
    print(f"Total assignees:    {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(*) FROM properties")
    print(f"Total properties:   {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(*) FROM ingest_log")
    print(f"Files ingested:     {cur.fetchone()[0]:,}")

    # Date range
    cur.execute("SELECT MIN(date_recorded), MAX(date_recorded) FROM assignments")
    min_date, max_date = cur.fetchone()
    print(f"Date range:         {min_date or 'N/A'} to {max_date or 'N/A'}")

    # Top conveyance types
    print("\n--- Top Conveyance Types ---")
    cur.execute("""
        SELECT conveyance_text, COUNT(*) as cnt
        FROM assignments
        GROUP BY conveyance_text
        ORDER BY cnt DESC
        LIMIT 15
    """)
    for row in cur.fetchall():
        print(f"  {row[1]:>8,}  {(row[0] or 'NULL')[:80]}")

    # Top assignee countries
    print("\n--- Top Assignee Countries ---")
    cur.execute("""
        SELECT country, COUNT(*) as cnt
        FROM assignees
        WHERE country != '' AND country IS NOT NULL
        GROUP BY country
        ORDER BY cnt DESC
        LIMIT 20
    """)
    for row in cur.fetchall():
        print(f"  {row[1]:>8,}  {row[0]}")

    # Ingested files
    print("\n--- Ingested Files ---")
    cur.execute("""
        SELECT filename, record_count, error_count,
               ROUND(duration_seconds, 1), ingested_at
        FROM ingest_log
        ORDER BY ingested_at DESC
        LIMIT 20
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:<40} {row[1]:>8,} records  {row[2]:>4} errors  {row[3]:>6}s  {row[4]}")

    # DB file size
    db_size = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\nDatabase size:      {db_size:.1f} MB")
    print()


def run_query(conn: sqlite3.Connection, conveyance: Optional[str] = None,
              assignee_name: Optional[str] = None, assignor_name: Optional[str] = None,
              country: Optional[str] = None, patent: Optional[str] = None,
              limit: int = 50):
    """Run investigative queries against the database."""
    cur = conn.cursor()

    conditions = []
    params = []

    base_query = """
        SELECT DISTINCT
            a.reel_no, a.frame_no, a.conveyance_text, a.date_recorded,
            GROUP_CONCAT(DISTINCT aor.name) as assignors,
            GROUP_CONCAT(DISTINCT aee.name) as assignees,
            GROUP_CONCAT(DISTINCT aee.country) as countries,
            GROUP_CONCAT(DISTINCT p.patent_number) as patents
        FROM assignments a
        LEFT JOIN assignors aor ON aor.assignment_id = a.id
        LEFT JOIN assignees aee ON aee.assignment_id = a.id
        LEFT JOIN properties p ON p.assignment_id = a.id
    """

    if conveyance:
        conditions.append("UPPER(a.conveyance_text) LIKE UPPER(?)")
        params.append(f"%{conveyance}%")

    if assignee_name:
        conditions.append("UPPER(aee.name) LIKE UPPER(?)")
        params.append(f"%{assignee_name}%")

    if assignor_name:
        conditions.append("UPPER(aor.name) LIKE UPPER(?)")
        params.append(f"%{assignor_name}%")

    if country:
        conditions.append("UPPER(aee.country) LIKE UPPER(?)")
        params.append(f"%{country}%")

    if patent:
        conditions.append("p.patent_number LIKE ?")
        params.append(f"%{patent}%")

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += " GROUP BY a.id ORDER BY a.date_recorded DESC"
    base_query += f" LIMIT {limit}"

    cur.execute(base_query, params)
    results = cur.fetchall()

    if not results:
        print("No results found.")
        return

    print(f"\n=== Query Results ({len(results)} rows) ===\n")
    for row in results:
        reel, frame, conveyance_text, date_recorded, assignors_str, assignees_str, countries, patents = row
        print(f"Reel/Frame: {reel}/{frame}  Date: {date_recorded}")
        print(f"  Conveyance: {(conveyance_text or 'N/A')[:100]}")
        print(f"  Assignor(s): {assignors_str or 'N/A'}")
        print(f"  Assignee(s): {assignees_str or 'N/A'}")
        print(f"  Country: {countries or 'N/A'}")
        print(f"  Patent(s): {(patents or 'N/A')[:80]}")
        print()


# ---------------------------------------------------------------------------
# URL probing
# ---------------------------------------------------------------------------

def probe_url_patterns(session: requests.Session) -> dict:
    """Try various URL patterns to find working download endpoints.

    Returns a dict with 'annual_base' and 'daily_base' URLs that work,
    or empty strings if none work.
    """
    log.info("Probing URL patterns for USPTO patent assignment data...")

    # Common patterns for the annual data
    annual_patterns = [
        "https://data.uspto.gov/bulkdata/PASYR",
        "https://data.uspto.gov/bulkdata/pasyr",
        "https://data.uspto.gov/bulkdata/datasets/pasyr/files",
        "https://bulkdata.uspto.gov/data/patent/assignment",
    ]

    daily_patterns = [
        "https://data.uspto.gov/bulkdata/PASDL",
        "https://data.uspto.gov/bulkdata/pasdl",
        "https://data.uspto.gov/bulkdata/datasets/pasdl/files",
    ]

    # For each pattern, try to download a known file
    test_daily_file = f"ad{(datetime.now() - timedelta(days=3)).strftime('%Y%m%d')}.zip"
    test_annual_file = "ad20230101-20231231.zip"

    results = {"annual_base": "", "daily_base": ""}

    for base in annual_patterns:
        test_url = f"{base}/{test_annual_file}"
        try:
            resp = session.head(test_url, timeout=15, allow_redirects=True)
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and "text/html" not in ct:
                log.info(f"  FOUND annual base: {base}")
                results["annual_base"] = base
                break
            else:
                log.debug(f"  Annual {base}: HTTP {resp.status_code}, CT={ct[:40]}")
        except Exception as e:
            log.debug(f"  Annual {base}: error {e}")

    for base in daily_patterns:
        test_url = f"{base}/{test_daily_file}"
        try:
            resp = session.head(test_url, timeout=15, allow_redirects=True)
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and "text/html" not in ct:
                log.info(f"  FOUND daily base: {base}")
                results["daily_base"] = base
                break
            else:
                log.debug(f"  Daily {base}: HTTP {resp.status_code}, CT={ct[:40]}")
        except Exception as e:
            log.debug(f"  Daily {base}: error {e}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="USPTO Patent Assignment Bulk Data Ingest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover available files (74 parts, ~10 GB total)
  uv run python scripts/ingest_patent_assignments.py --discover

  # Download and ingest one part (~140 MB)
  uv run python scripts/ingest_patent_assignments.py --part 1

  # Download and ingest several parts
  uv run python scripts/ingest_patent_assignments.py --part 1,2,3

  # Download and ingest ALL parts (~10 GB)
  uv run python scripts/ingest_patent_assignments.py --all

  # Ingest recent daily updates
  uv run python scripts/ingest_patent_assignments.py --daily --days 7

  # Ingest a local ZIP file
  uv run python scripts/ingest_patent_assignments.py --file datasets/patent_assignments/ad19880101-20251231-01.zip

  # Show database statistics
  uv run python scripts/ingest_patent_assignments.py --stats

  # Search for security interest assignments from Russian entities
  uv run python scripts/ingest_patent_assignments.py --query "SECURITY" --country "RUSSIA"

  # Search for foreclosures
  uv run python scripts/ingest_patent_assignments.py --query "FORECLOSURE"

  # Search by assignee name
  uv run python scripts/ingest_patent_assignments.py --assignee "APPLE INC"
        """
    )

    # Ingest modes
    ingest = parser.add_argument_group("Ingest")
    ingest.add_argument("--discover", action="store_true",
                        help="Discover available files via ODP API")
    ingest.add_argument("--part", type=str,
                        help="Download and ingest specific part number(s), e.g. '1' or '1,2,3'")
    ingest.add_argument("--daily", action="store_true",
                        help="Ingest daily update files")
    ingest.add_argument("--days", type=int, default=7,
                        help="Number of days of daily files to fetch (default: 7)")
    ingest.add_argument("--file", type=Path,
                        help="Ingest a specific local ZIP file")
    ingest.add_argument("--all", action="store_true",
                        help="Download and ingest ALL annual files (~10 GB, 74 parts)")

    # Query mode
    query = parser.add_argument_group("Query")
    query.add_argument("--stats", action="store_true",
                       help="Show database statistics")
    query.add_argument("--query", type=str,
                       help="Search conveyance text (e.g., SECURITY, FORECLOSURE)")
    query.add_argument("--assignee", type=str,
                       help="Search by assignee name")
    query.add_argument("--assignor", type=str,
                       help="Search by assignor name")
    query.add_argument("--country", type=str,
                       help="Filter by assignee country")
    query.add_argument("--patent", type=str,
                       help="Search by patent number")
    query.add_argument("--limit", type=int, default=50,
                       help="Max results for queries (default: 50)")

    # Options
    parser.add_argument("--db", type=Path, default=DB_PATH,
                        help=f"Database path (default: {DB_PATH})")
    parser.add_argument("--download-dir", type=Path, default=DOWNLOAD_DIR,
                        help=f"Download directory (default: {DOWNLOAD_DIR})")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Session for HTTP requests
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    # Handle discovery
    if args.discover:
        log.info("Discovering available patent assignment files via ODP API...")
        files = discover_files_via_api(ANNUAL_PRODUCT)
        if not files:
            log.info("API discovery failed. Generating known URL patterns...")
            files = generate_known_annual_urls()

        total_size = sum(f.get("size", 0) for f in files)
        print(f"\n=== Available Annual Files ({len(files)}, {total_size / 1024/1024/1024:.1f} GB) ===")
        for f in sorted(files, key=lambda x: x.get("filename", "")):
            name = f.get("filename", "")
            size_mb = f.get("size", 0) / 1024 / 1024
            print(f"  {name:<45} {size_mb:>7.1f} MB")

        daily = discover_daily_files_via_api(args.days)
        if not daily:
            daily = generate_daily_urls(args.days)
        print(f"\n=== Recent Daily Files ({len(daily)}) ===")
        for f in daily:
            name = f.get("filename", "")
            size_mb = f.get("size", 0) / 1024 / 1024
            print(f"  {name:<45} {size_mb:>7.1f} MB")

        return

    # Database operations
    conn = init_db(args.db)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    if args.query or args.assignee or args.assignor or args.country or args.patent:
        run_query(conn,
                  conveyance=args.query,
                  assignee_name=args.assignee,
                  assignor_name=args.assignor,
                  country=args.country,
                  patent=args.patent,
                  limit=args.limit)
        conn.close()
        return

    # Ingest from local file
    if args.file:
        if not args.file.exists():
            log.error(f"File not found: {args.file}")
            sys.exit(1)
        inserted, errors = ingest_zip(conn, args.file)
        print(f"Ingested {inserted:,} records ({errors} errors) from {args.file.name}")
        conn.close()
        return

    # Ingest specific part(s) or all
    if args.part or args.all:
        # Discover files via API
        files = discover_files_via_api(ANNUAL_PRODUCT)
        if not files:
            files = generate_known_annual_urls()

        if args.part:
            # Filter to specific part numbers
            parts = [int(p.strip()) for p in args.part.split(",")]
            files = [f for f in files if any(
                f["filename"].endswith(f"-{p:02d}.zip") for p in parts
            )]

        total_inserted = 0
        total_errors = 0

        for f in sorted(files, key=lambda x: x["filename"]):
            filename = f["filename"]
            url = f["url"]
            local_path = DOWNLOAD_DIR / filename

            if local_path.exists():
                log.info(f"Found local file: {local_path}")
                inserted, errors = ingest_zip(conn, local_path)
                total_inserted += inserted
                total_errors += errors
                continue

            log.info(f"Downloading: {filename} ({f.get('size', 0) / 1024/1024:.1f} MB)")
            if download_file(url, local_path, session):
                inserted, errors = ingest_zip(conn, local_path)
                total_inserted += inserted
                total_errors += errors
            else:
                log.warning(f"Failed to download {filename}")

        print(f"\nTotal: {total_inserted:,} records ({total_errors} errors)")
        conn.close()
        return

    # Ingest daily
    if args.daily:
        daily_files = discover_daily_files_via_api(args.days)
        if not daily_files:
            daily_files = generate_daily_urls(args.days)

        total_inserted = 0
        total_errors = 0

        for f in daily_files:
            filename = f["filename"]
            url = f["url"]
            local_path = DOWNLOAD_DIR / filename

            if local_path.exists():
                inserted, errors = ingest_zip(conn, local_path)
                total_inserted += inserted
                total_errors += errors
                continue

            if download_file(url, local_path, session):
                inserted, errors = ingest_zip(conn, local_path)
                total_inserted += inserted
                total_errors += errors

        print(f"\nTotal: {total_inserted:,} records ({total_errors} errors)")
        conn.close()
        return

    # No action specified
    parser.print_help()


if __name__ == "__main__":
    main()
