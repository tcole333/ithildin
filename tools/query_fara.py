#!/usr/bin/env python3
"""
FARA (Foreign Agents Registration Act) bulk data tool.

Downloads daily CSV exports from efile.fara.gov and loads into
investigation.db for local FTS5 search. Covers registrants,
foreign principals, short form registrants, and document URLs.

Bulk data: https://efile.fara.gov/ords/fara/f?p=API:BULKDATA:0
Format: CSV (ISO-8859-1 encoded), updated daily, distributed as ZIP.
Rate limit: 5 requests per 10 seconds.

NETWORK NOTES (Apr 2026):
  efile.fara.gov actively TCP-RSTs requests that look programmatic.
  The download path now sends a browser User-Agent AND a Referer header
  pointing at the bulk-data landing page; with retry-on-reset/backoff
  this bypasses the block. If `download` ever fails after 6 attempts
  per file, fetch the ZIPs manually from the URL above and drop them
  into datasets/fara/ named registrants.csv.zip, foreign_principals.csv.zip,
  short_forms.csv.zip, documents.csv.zip — `ingest` will pick them up.

Usage:
    python tools/query_fara.py download          # Fetch CSV exports
    python tools/query_fara.py ingest            # Parse into investigation.db
    python tools/query_fara.py search "Epstein"
    python tools/query_fara.py search "International Peace"
    python tools/query_fara.py country "Norway"
    python tools/query_fara.py country "Israel"
    python tools/query_fara.py detail 1234       # Registration number
"""

import argparse
import csv
import io
import json
import sqlite3
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output


def _log(query, source, count):
    """Log search to prevent redundant queries."""
    try:
        from tools.lead_tracker import log_search
        log_search(query, source, count)
    except Exception:
        pass


PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "datasets" / "fara"
DB_PATH = PROJECT_ROOT / "investigation.db"

BULK_BASE = "https://efile.fara.gov/bulk/zip"

BULK_FILES = {
    "registrants": f"{BULK_BASE}/FARA_All_Registrants.csv.zip",
    "foreign_principals": f"{BULK_BASE}/FARA_All_ForeignPrincipals.csv.zip",
    "short_forms": f"{BULK_BASE}/FARA_All_ShortForms.csv.zip",
    "documents": f"{BULK_BASE}/FARA_All_RegistrantDocs.csv.zip",
}

STALE_AFTER_DAYS = 7


def _utc_now():
    """Return the current UTC time (a seam for deterministic freshness tests)."""
    return datetime.now(timezone.utc)


def _bulk_file_freshness(dataset_name):
    """Describe the age of a downloaded bulk file without claiming source recency.

    FARA does not embed a dataset version in the local tables.  The ZIP mtime is
    therefore the best available provenance for an existing cache: downloads
    performed by this tool create/replace the file at download time, while
    manually copied files are accurately labeled as filesystem modification
    times rather than DOJ publication dates.
    """
    source_path = DATA_DIR / f"{dataset_name}.csv.zip"
    metadata = {
        "source_file": str(source_path),
        "source_file_modified_at": None,
        "age_days": None,
        "stale_after_days": STALE_AFTER_DAYS,
        "stale": None,
    }
    try:
        modified_at = datetime.fromtimestamp(
            source_path.stat().st_mtime, tz=timezone.utc
        )
    except OSError:
        return metadata

    age_seconds = max(0.0, (_utc_now() - modified_at).total_seconds())
    age_days = age_seconds / 86400
    metadata.update(
        {
            "source_file_modified_at": modified_at.isoformat(),
            "age_days": round(age_days, 1),
            "stale": age_days > STALE_AFTER_DAYS,
        }
    )
    return metadata


def _active_status_freshness_warning(registrant, freshness):
    """Warn when a local Active label is stale or has unknown provenance."""
    if not registrant or str(registrant["status"]).lower() != "active":
        return None

    if freshness["stale"] is True:
        return (
            "Local FARA status is Active, but the registrants bulk cache is "
            f"{freshness['age_days']:.1f} days old "
            f"(stale after {freshness['stale_after_days']} days). "
            "Run `uv run python tools/query_fara.py download` and "
            "`uv run python tools/query_fara.py ingest` before relying on this status."
        )
    if freshness["stale"] is None:
        return (
            "Local FARA status is Active, but cache freshness is unknown because "
            "registrants.csv.zip is unavailable. Refresh and ingest the FARA bulk "
            "files before relying on this status."
        )
    return None


def _download_file(url, dest_path, max_retries=6):
    """Download a file with retry-on-reset.

    efile.fara.gov actively resets TCP connections from clients that look
    programmatic. Empirically (Apr 2026), the bulk endpoint accepts the
    request only when (a) a browser-like User-Agent is sent AND (b) a
    Referer header pointing at the bulk-data landing page is present.
    Even then, the server intermittently returns ConnectionResetError,
    so we retry with exponential backoff.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://efile.fara.gov/ords/fara/f?p=API:BULKDATA:0",
    }
    last_err = None
    for attempt in range(1, max_retries + 1):
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=90) as resp:
                data = resp.read()
                if len(data) < 100:
                    raise URLError(f"response too small ({len(data)} bytes)")
                dest_path.write_bytes(data)
                size_kb = len(data) / 1024
                print(f"  Downloaded {dest_path.name} ({size_kb:.0f} KB) on attempt {attempt}")
                return True
        except (HTTPError, URLError, ConnectionResetError, OSError) as e:
            last_err = e
            wait = min(2 ** attempt, 30)
            print(f"  Attempt {attempt}/{max_retries} failed for {dest_path.name}: {e}; sleeping {wait}s")
            time.sleep(wait)
    print(
        f"  ERROR downloading {url} after {max_retries} attempts: {last_err}\n"
        f"  efile.fara.gov is rate-limiting/blocking. Last error: {last_err}\n"
        f"  Try again later, or download manually via a browser from\n"
        f"  https://efile.fara.gov/ords/fara/f?p=API:BULKDATA:0 and place the\n"
        f"  ZIP in {dest_path.parent}/",
        file=sys.stderr,
    )
    return False


def _get_db():
    """Get connection to investigation.db."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def _create_tables(db):
    """Create FARA tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS fara_registrants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_number TEXT,
            registrant_name TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            country TEXT,
            registration_date TEXT,
            termination_date TEXT,
            status TEXT,
            raw_data TEXT
        );

        CREATE TABLE IF NOT EXISTS fara_foreign_principals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_number TEXT,
            registrant_name TEXT,
            foreign_principal TEXT,
            foreign_principal_country TEXT,
            date TEXT,
            registrant_date TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            raw_data TEXT
        );

        CREATE TABLE IF NOT EXISTS fara_short_forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_number TEXT,
            registrant_name TEXT,
            short_form_name TEXT,
            short_form_date TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            raw_data TEXT
        );

        CREATE TABLE IF NOT EXISTS fara_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_number TEXT,
            registrant_name TEXT,
            document_type TEXT,
            stamp_date TEXT,
            document_url TEXT,
            raw_data TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_fara_reg_number ON fara_registrants(registration_number);
        CREATE INDEX IF NOT EXISTS idx_fara_fp_reg ON fara_foreign_principals(registration_number);
        CREATE INDEX IF NOT EXISTS idx_fara_fp_country ON fara_foreign_principals(foreign_principal_country);
        CREATE INDEX IF NOT EXISTS idx_fara_sf_reg ON fara_short_forms(registration_number);
        CREATE INDEX IF NOT EXISTS idx_fara_doc_reg ON fara_documents(registration_number);
    """)

    # FTS5 indexes
    try:
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fara_registrants_fts
            USING fts5(registrant_name, address, city, state, content=fara_registrants, content_rowid=id)
        """)
    except sqlite3.OperationalError:
        pass

    try:
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fara_principals_fts
            USING fts5(foreign_principal, foreign_principal_country, registrant_name,
                       content=fara_foreign_principals, content_rowid=id)
        """)
    except sqlite3.OperationalError:
        pass

    db.commit()


def _rebuild_fts(db):
    """Rebuild FTS indexes."""
    try:
        db.execute("INSERT INTO fara_registrants_fts(fara_registrants_fts) VALUES('rebuild')")
        db.execute("INSERT INTO fara_principals_fts(fara_principals_fts) VALUES('rebuild')")
        db.commit()
    except sqlite3.OperationalError as e:
        print(f"  FTS rebuild warning: {e}", file=sys.stderr)


def _read_csv_from_zip(zip_path):
    """Read CSV from a ZIP file, handling ISO-8859-1 encoding."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            print(f"  No CSV found in {zip_path.name}", file=sys.stderr)
            return []

        with zf.open(csv_names[0]) as f:
            text = f.read().decode("iso-8859-1")
            reader = csv.DictReader(io.StringIO(text))
            return list(reader)


def cmd_download(args):
    """Download FARA bulk CSV exports."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading FARA bulk data files...")
    failed = []
    for name, url in BULK_FILES.items():
        dest = DATA_DIR / f"{name}.csv.zip"
        if not _download_file(url, dest):
            failed.append(name)
        time.sleep(5)  # Rate limit: 5 req/10s + extra slack to avoid TCP RST
    if failed:
        print(
            f"\nWARNING: {len(failed)} file(s) failed to download: {', '.join(failed)}\n"
            f"Re-run `download` later, or fetch the ZIPs manually and drop them in {DATA_DIR}.",
            file=sys.stderr,
        )

    print(f"\nFiles saved to {DATA_DIR}")


def cmd_ingest(args):
    """Parse downloaded CSVs into investigation.db."""
    db = _get_db()
    _create_tables(db)

    # Clear existing data for fresh ingest
    for table in ["fara_registrants", "fara_foreign_principals", "fara_short_forms", "fara_documents"]:
        db.execute(f"DELETE FROM {table}")
    db.commit()

    # Ingest registrants
    # Fields: Registration Number, Registration Date, Termination Date, Name, Business Name,
    #         Address 1, Address 2, City, State, Zip
    reg_path = DATA_DIR / "registrants.csv.zip"
    if reg_path.exists():
        rows = _read_csv_from_zip(reg_path)
        count = 0
        for r in rows:
            reg_num = r.get("Registration Number", "").strip()
            name = r.get("Name", "").strip()
            if not reg_num and not name:
                continue
            biz_name = r.get("Business Name", "").strip()
            full_name = f"{name} ({biz_name})" if biz_name else name
            term_date = r.get("Termination Date", "").strip()
            status = "Terminated" if term_date else "Active"
            db.execute("""
                INSERT INTO fara_registrants
                (registration_number, registrant_name, address, city, state, zip, country,
                 registration_date, termination_date, status, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                reg_num, full_name,
                r.get("Address 1", "").strip(),
                r.get("City", "").strip(),
                r.get("State", "").strip(),
                r.get("Zip", "").strip(),
                "",  # No country field in registrants CSV
                r.get("Registration Date", "").strip(),
                term_date or None,
                status,
                json.dumps(r),
            ])
            count += 1
        print(f"  Ingested {count} registrants")
    else:
        print(f"  Registrants file not found: {reg_path}")

    # Ingest foreign principals
    # Fields: Foreign Principal Termination Date, Foreign Principal,
    #         Foreign Principal Registration Date, Country/Location Represented,
    #         Registration Number, Registrant Date, Registrant Name,
    #         Address 1, Address 2, City, State, Zip
    fp_path = DATA_DIR / "foreign_principals.csv.zip"
    if fp_path.exists():
        rows = _read_csv_from_zip(fp_path)
        count = 0
        for r in rows:
            fp_name = r.get("Foreign Principal", "").strip()
            reg_num = r.get("Registration Number", "").strip()
            if not fp_name and not reg_num:
                continue
            db.execute("""
                INSERT INTO fara_foreign_principals
                (registration_number, registrant_name, foreign_principal, foreign_principal_country,
                 date, registrant_date, address, city, state, country, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                reg_num,
                r.get("Registrant Name", "").strip(),
                fp_name,
                r.get("Country/Location Represented", "").strip(),
                r.get("Foreign Principal Registration Date", "").strip(),
                r.get("Registrant Date", "").strip(),
                r.get("Address 1", "").strip(),
                r.get("City", "").strip(),
                r.get("State", "").strip(),
                "",  # Country of registrant address not in CSV
                json.dumps(r),
            ])
            count += 1
        print(f"  Ingested {count} foreign principals")
    else:
        print(f"  Foreign principals file not found: {fp_path}")

    # Ingest short forms
    # Fields: Short Form Termination Date, Short Form Date, Short Form Last Name,
    #         Short Form First Name, Registration Number, Registration Date,
    #         Registrant Name, Address 1, Address 2, City, State, Zip
    sf_path = DATA_DIR / "short_forms.csv.zip"
    if sf_path.exists():
        rows = _read_csv_from_zip(sf_path)
        count = 0
        for r in rows:
            reg_num = r.get("Registration Number", "").strip()
            last_name = r.get("Short Form Last Name", "").strip()
            first_name = r.get("Short Form First Name", "").strip()
            sf_name = f"{last_name}, {first_name}" if first_name else last_name
            if not reg_num and not sf_name:
                continue
            db.execute("""
                INSERT INTO fara_short_forms
                (registration_number, registrant_name, short_form_name, short_form_date,
                 address, city, state, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                reg_num,
                r.get("Registrant Name", "").strip(),
                sf_name,
                r.get("Short Form Date", "").strip(),
                r.get("Address 1", "").strip(),
                r.get("City", "").strip(),
                r.get("State", "").strip(),
                json.dumps(r),
            ])
            count += 1
        print(f"  Ingested {count} short form registrants")
    else:
        print(f"  Short forms file not found: {sf_path}")

    # Ingest documents
    # Fields: Date Stamped, Registrant Name, Registration Number,
    #         Document Type, Short Form Name, Foreign Principal Name,
    #         Foreign Principal Country, URL
    doc_path = DATA_DIR / "documents.csv.zip"
    if doc_path.exists():
        rows = _read_csv_from_zip(doc_path)
        count = 0
        for r in rows:
            reg_num = r.get("Registration Number", "").strip()
            if not reg_num:
                continue
            db.execute("""
                INSERT INTO fara_documents
                (registration_number, registrant_name, document_type, stamp_date, document_url, raw_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                reg_num,
                r.get("Registrant Name", "").strip(),
                r.get("Document Type", "").strip(),
                r.get("Date Stamped", "").strip(),
                r.get("URL", "").strip(),
                json.dumps(r),
            ])
            count += 1
        print(f"  Ingested {count} documents")
    else:
        print(f"  Documents file not found: {doc_path}")

    db.commit()
    _rebuild_fts(db)
    print("\nFARA ingest complete.")


def cmd_search(args):
    """Search FARA registrants and foreign principals by name."""
    db = _get_db()

    # Check if tables exist
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fara_%'").fetchall()]
    if not tables:
        print("FARA tables not found. Run: python tools/query_fara.py download && python tools/query_fara.py ingest")
        return

    query = args.query.strip()
    if not query:
        print("Please provide a search term.")
        return

    # If --output, collect all results, write, and return
    if getattr(args, "output", None) or getattr(args, "json_out", False):
        all_data = {"registrants": [], "foreign_principals": []}
        try:
            regs = db.execute("""
                SELECT r.* FROM fara_registrants r
                JOIN fara_registrants_fts f ON r.id = f.rowid
                WHERE fara_registrants_fts MATCH ?
                ORDER BY r.registration_date DESC LIMIT ?
            """, [query, args.limit]).fetchall()
        except sqlite3.OperationalError:
            regs = db.execute("""
                SELECT * FROM fara_registrants
                WHERE registrant_name LIKE ? OR address LIKE ?
                ORDER BY registration_date DESC LIMIT ?
            """, [f"%{query}%", f"%{query}%", args.limit]).fetchall()
        all_data["registrants"] = [dict(r) for r in regs]

        try:
            fps = db.execute("""
                SELECT fp.* FROM fara_foreign_principals fp
                JOIN fara_principals_fts f ON fp.id = f.rowid
                WHERE fara_principals_fts MATCH ?
                ORDER BY fp.date DESC LIMIT ?
            """, [query, args.limit]).fetchall()
        except sqlite3.OperationalError:
            fps = db.execute("""
                SELECT * FROM fara_foreign_principals
                WHERE foreign_principal LIKE ? OR registrant_name LIKE ?
                ORDER BY date DESC LIMIT ?
            """, [f"%{query}%", f"%{query}%", args.limit]).fetchall()
        all_data["foreign_principals"] = [dict(r) for r in fps]
        _log(query, "fara", len(regs) + len(fps))

        if write_output(all_data, args, summary=f"FARA search '{query}'"):
            return
        if args.json_out:
            print(json.dumps(all_data, indent=2, default=str))
            return

    # Search registrants
    print(f"=== FARA Registrants matching '{query}' ===")
    try:
        results = db.execute("""
            SELECT r.* FROM fara_registrants r
            JOIN fara_registrants_fts f ON r.id = f.rowid
            WHERE fara_registrants_fts MATCH ?
            ORDER BY r.registration_date DESC
            LIMIT ?
        """, [query, args.limit]).fetchall()
    except sqlite3.OperationalError:
        # Fall back to LIKE search
        results = db.execute("""
            SELECT * FROM fara_registrants
            WHERE registrant_name LIKE ? OR address LIKE ?
            ORDER BY registration_date DESC
            LIMIT ?
        """, [f"%{query}%", f"%{query}%", args.limit]).fetchall()

    print(f"Found {len(results)} registrants")
    for r in results:
        status = r["status"] or "?"
        print(f"\n  [{status}] {r['registrant_name']}")
        print(f"    Registration #: {r['registration_number']}")
        if r["address"]:
            print(f"    Address: {r['address']}, {r['city']}, {r['state']} {r['zip']}")
        if r["registration_date"]:
            print(f"    Registered: {r['registration_date']}")
        if r["termination_date"]:
            print(f"    Terminated: {r['termination_date']}")

    # Search foreign principals
    print(f"\n=== Foreign Principals matching '{query}' ===")
    try:
        fp_results = db.execute("""
            SELECT fp.* FROM fara_foreign_principals fp
            JOIN fara_principals_fts f ON fp.id = f.rowid
            WHERE fara_principals_fts MATCH ?
            ORDER BY fp.date DESC
            LIMIT ?
        """, [query, args.limit]).fetchall()
    except sqlite3.OperationalError:
        fp_results = db.execute("""
            SELECT * FROM fara_foreign_principals
            WHERE foreign_principal LIKE ? OR registrant_name LIKE ?
            ORDER BY date DESC
            LIMIT ?
        """, [f"%{query}%", f"%{query}%", args.limit]).fetchall()

    _log(query, "fara", len(results) + len(fp_results))
    print(f"Found {len(fp_results)} foreign principals")
    for fp in fp_results:
        print(f"\n  {fp['foreign_principal']} ({fp['foreign_principal_country']})")
        print(f"    Registrant: {fp['registrant_name']} (#{fp['registration_number']})")
        if fp["date"]:
            print(f"    Date: {fp['date']}")


def cmd_country(args):
    """Search FARA foreign principals by country, optionally filtered by year."""
    db = _get_db()

    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fara_%'").fetchall()]
    if not tables:
        print("FARA tables not found. Run download + ingest first.")
        return

    where = ["upper(foreign_principal_country) LIKE upper(?)"]
    params = [f"%{args.country}%"]
    year = getattr(args, "year", None)
    if year:
        # FARA dates are stored as MM/DD/YYYY strings; match either the
        # foreign-principal date or the registrant date.
        where.append("(substr(date, -4) = ? OR substr(registrant_date, -4) = ?)")
        params.extend([str(year), str(year)])
    params.append(args.limit)
    sql = f"""
        SELECT * FROM fara_foreign_principals
        WHERE {" AND ".join(where)}
        ORDER BY date DESC
        LIMIT ?
    """
    results = db.execute(sql, params).fetchall()

    if write_output([dict(r) for r in results], args, summary=f"FARA country '{args.country}'"):
        return
    if args.json_out:
        print(json.dumps([dict(r) for r in results], indent=2, default=str))
        return

    print(f"Found {len(results)} foreign principals for country '{args.country}'")
    for fp in results:
        print(f"\n  {fp['foreign_principal']} ({fp['foreign_principal_country']})")
        print(f"    Registrant: {fp['registrant_name']} (#{fp['registration_number']})")
        if fp["date"]:
            print(f"    Date: {fp['date']}")
        if fp["address"]:
            print(f"    Address: {fp['address']}, {fp['city']}, {fp['state']}")


def cmd_detail(args):
    """Get all records for a specific FARA registration number."""
    db = _get_db()

    reg_num = args.registration_number

    # Registrant info
    reg = db.execute(
        "SELECT * FROM fara_registrants WHERE registration_number = ?", [reg_num]
    ).fetchone()

    # Foreign principals
    fps = db.execute(
        "SELECT * FROM fara_foreign_principals WHERE registration_number = ? ORDER BY date", [reg_num]
    ).fetchall()

    # Short forms
    sfs = db.execute(
        "SELECT * FROM fara_short_forms WHERE registration_number = ? ORDER BY short_form_date", [reg_num]
    ).fetchall()

    # Documents
    docs = db.execute(
        "SELECT * FROM fara_documents WHERE registration_number = ? ORDER BY stamp_date DESC", [reg_num]
    ).fetchall()

    registrant_freshness = _bulk_file_freshness("registrants")
    freshness_warning = _active_status_freshness_warning(
        reg, registrant_freshness
    )

    # Prepare output data
    output_data = {
        "registrant": dict(reg) if reg else None,
        "foreign_principals": [dict(fp) for fp in fps],
        "short_forms": [dict(sf) for sf in sfs],
        "documents": [dict(d) for d in docs],
        "dataset_freshness": {
            "registrants": registrant_freshness,
        },
        "warnings": [freshness_warning] if freshness_warning else [],
    }

    if freshness_warning:
        print(f"WARNING: {freshness_warning}", file=sys.stderr)

    # Handle output mode
    if getattr(args, "output", None) or getattr(args, "json_out", False):
        if write_output(output_data, args, summary=f"FARA detail #{reg_num}"):
            return
        if args.json_out:
            print(json.dumps(output_data, indent=2, default=str))
            return

    # Print human-readable format
    if reg:
        print(f"=== Registrant #{reg_num} ===")
        print(f"  Name: {reg['registrant_name']}")
        print(f"  Status: {reg['status']}")
        if registrant_freshness["source_file_modified_at"]:
            print(
                "  Registrants cache: "
                f"{registrant_freshness['source_file_modified_at']} "
                f"({registrant_freshness['age_days']:.1f} days old)"
            )
        else:
            print("  Registrants cache: freshness unknown")
        if reg["address"]:
            print(f"  Address: {reg['address']}, {reg['city']}, {reg['state']} {reg['zip']}")
        if reg["registration_date"]:
            print(f"  Registered: {reg['registration_date']}")
        if reg["termination_date"]:
            print(f"  Terminated: {reg['termination_date']}")
    else:
        print(f"Registration #{reg_num} not found in registrants table")

    if fps:
        print(f"\n=== Foreign Principals ({len(fps)}) ===")
        for fp in fps:
            print(f"  {fp['foreign_principal']} ({fp['foreign_principal_country']})")
            if fp["date"]:
                print(f"    Date: {fp['date']}")

    if sfs:
        print(f"\n=== Short Form Registrants ({len(sfs)}) ===")
        for sf in sfs:
            print(f"  {sf['short_form_name']}")
            if sf["short_form_date"]:
                print(f"    Date: {sf['short_form_date']}")

    if docs:
        shown = min(20, len(docs))
        print(f"\n=== Documents (showing {shown} of {len(docs)}) ===")
        for d in docs[:20]:
            print(f"  [{d['document_type']}] {d['stamp_date']}")
            if d["document_url"]:
                print(f"    URL: {d['document_url']}")


def cmd_stats(args):
    """Show FARA data statistics."""
    db = _get_db()

    tables = {
        "fara_registrants": "Registrants",
        "fara_foreign_principals": "Foreign Principals",
        "fara_short_forms": "Short Form Registrants",
        "fara_documents": "Documents",
    }

    print("=== FARA Data Statistics ===")
    for table, label in tables.items():
        try:
            count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {label}: {count:,}")
        except sqlite3.OperationalError:
            print(f"  {label}: (table not found — run download + ingest)")

    # Country breakdown (top 20)
    try:
        countries = db.execute("""
            SELECT foreign_principal_country, COUNT(*) as cnt
            FROM fara_foreign_principals
            WHERE foreign_principal_country IS NOT NULL AND foreign_principal_country != ''
            GROUP BY foreign_principal_country
            ORDER BY cnt DESC
            LIMIT 20
        """).fetchall()

        if countries:
            print("\n=== Top Countries ===")
            for c in countries:
                print(f"  {c['foreign_principal_country']}: {c['cnt']}")
    except sqlite3.OperationalError:
        pass


def main():
    parser = argparse.ArgumentParser(description="FARA foreign agent registration data")
    sub = parser.add_subparsers(dest="command", required=True)

    # download
    sub.add_parser("download", help="Download FARA bulk CSV exports")

    # ingest
    sub.add_parser("ingest", help="Parse downloaded CSVs into investigation.db")

    # search
    p = sub.add_parser("search", help="Search registrants and foreign principals")
    p.add_argument("query", help="Search term")
    p.add_argument("--limit", type=int, default=20, help="Max results per category")
    add_output_args(p)

    # country
    p = sub.add_parser("country", help="Search foreign principals by country")
    p.add_argument("country", help="Country name")
    p.add_argument("--year", type=int, help="Filter by year (matches date or registrant_date YYYY)")
    p.add_argument("--limit", type=int, default=50, help="Max results")
    add_output_args(p)

    # detail
    p = sub.add_parser("detail", help="Get all records for a registration number")
    p.add_argument("registration_number", help="FARA registration number")
    add_output_args(p)

    # stats
    sub.add_parser("stats", help="Show FARA data statistics")

    args = parser.parse_args()
    if not hasattr(args, "json_out"):
        args.json_out = False

    handlers = {
        "download": cmd_download,
        "ingest": cmd_ingest,
        "search": cmd_search,
        "country": cmd_country,
        "detail": cmd_detail,
        "stats": cmd_stats,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
