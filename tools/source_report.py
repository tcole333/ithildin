#!/usr/bin/env python3
"""
Data source coverage report for the Epstein OSINT investigation.

Lists all available data sources, record counts, and status.

Usage:
    python tools/source_report.py
    python tools/source_report.py --json
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def check_sqlite(path, count_query):
    """Check if a SQLite DB exists and get record count."""
    if not path.exists():
        return {"status": "missing", "path": str(path), "records": 0}
    try:
        db = sqlite3.connect(str(path))
        count = db.execute(count_query).fetchone()[0]
        db.close()
        size_mb = path.stat().st_size / (1024 * 1024)
        return {"status": "available", "path": str(path), "records": count, "size_mb": round(size_mb, 1)}
    except Exception as e:
        return {"status": "error", "path": str(path), "error": str(e)}


def check_parquet(path):
    """Check if a parquet file exists and get row count."""
    if not path.exists():
        return {"status": "missing", "path": str(path), "records": 0}
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        size_mb = path.stat().st_size / (1024 * 1024)
        return {"status": "available", "path": str(path), "records": len(df), "size_mb": round(size_mb, 1)}
    except Exception as e:
        return {"status": "error", "path": str(path), "error": str(e)}


def check_directory(path):
    """Check if a directory exists and count files."""
    if not path.exists():
        return {"status": "missing", "path": str(path), "records": 0}
    try:
        count = sum(1 for _ in path.rglob("*") if _.is_file())
        size_mb = sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / (1024 * 1024)
        return {"status": "available", "path": str(path), "records": count, "size_mb": round(size_mb, 1)}
    except Exception as e:
        return {"status": "error", "path": str(path), "error": str(e)}


def check_neo4j():
    """Check if ICIJ Neo4j is running."""
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=icij-offshore-leaks", "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            return {"status": "running", "bolt": "bolt://localhost:7689", "info": result.stdout.strip()}
        return {"status": "stopped", "start_cmd": "./scripts/start_icij_db.sh"}
    except Exception:
        return {"status": "unknown", "start_cmd": "./scripts/start_icij_db.sh"}


def check_api(name, test_url=None):
    """Check if an API is reachable."""
    if not test_url:
        return {"status": "configured"}
    try:
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError, URLError
        # SEC EDGAR requires User-Agent header
        headers = {"User-Agent": "OSINT-Research osint-research@proton.me"}
        # DugganUSA requires Bearer token auth
        if "dugganusa.com" in test_url:
            from tools.duggan_search import _get_api_key
            api_key = _get_api_key()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                return {"status": "error:no_api_key", "error": "DUGGANUSA_API_KEY not set in .env"}
        req = Request(test_url, headers=headers)
        with urlopen(req, timeout=5) as resp:
            return {"status": "available" if resp.status == 200 else f"error:{resp.status}"}
    except HTTPError as e:
        return {"status": f"error:{e.code}", "error": str(e)}
    except (URLError, Exception) as e:
        return {"status": "unreachable", "error": str(e)}


def generate_report():
    """Generate full source coverage report."""
    sources = {}

    # Local SQLite databases
    sources["DOJ Vol 11"] = {
        "description": "331K OCR'd pages from DOJ Volume 11 release",
        "query_tool": "tools/query_doj.py",
        **check_sqlite(
            Path("/Users/travcole/projects/epstein-docs/output/documents.db"),
            "SELECT COUNT(*) FROM documents"
        ),
    }

    sources["LMSBAND"] = {
        "description": "60K files, 851K entities, 110K co-occurrences",
        "query_tool": "tools/query_lmsband.py",
        **check_sqlite(
            PROJECT_ROOT / "datasets" / "lmsband_epstein_files.db",
            "SELECT COUNT(*) FROM files"
        ),
    }

    sources["Unified DB"] = {
        "description": "Consolidated emails, docs, entities, triples",
        "query_tool": "tools/query_unified.py",
        **check_sqlite(
            PROJECT_ROOT / "datasets" / "unified_epstein.db",
            "SELECT COUNT(*) FROM emails"
        ),
    }

    sources["Doc-Explorer"] = {
        "description": "25K docs, 107K triples, 27K entities (RDF format)",
        "query_tool": "sqlite3 (direct)",
        **check_sqlite(
            PROJECT_ROOT / "datasets" / "Epstein-doc-explorer" / "document_analysis.db",
            "SELECT COUNT(*) FROM rdf_triples"
        ),
    }

    sources["Investigation DB"] = {
        "description": "Leads, findings, connections, search log, sessions",
        "query_tool": "tools/lead_tracker.py / tools/findings_tracker.py",
        **check_sqlite(
            PROJECT_ROOT / "investigation.db",
            "SELECT COUNT(*) FROM leads"
        ),
    }

    # Parquet files
    sources["HF Emails Parquet"] = {
        "description": "4,272 House Oversight emails",
        "query_tool": "pandas read_parquet()",
        **check_parquet(PROJECT_ROOT / "datasets" / "epstein-emails-hf" / "emails.parquet"),
    }

    sources["FBI Files Parquet"] = {
        "description": "8,150 FBI docs (Textract OCR)",
        "query_tool": "pandas read_parquet()",
        **check_parquet(PROJECT_ROOT / "datasets" / "svetfm_fbi_files.parquet"),
    }

    sources["Email Threads Parquet"] = {
        "description": "5,082 email threads",
        "query_tool": "pandas read_parquet()",
        **check_parquet(PROJECT_ROOT / "datasets" / "notesbymuneeb_epstein_email_threads.parquet"),
    }

    # File directories
    sources["DDoSecrets EML"] = {
        "description": "13K+ raw .eml files from jeeproject yahoo",
        "query_tool": "tools/search_emails.py",
        **check_directory(PROJECT_ROOT / "datasets" / "epstein-archive" / "data" / "emails" / "jeeproject_yahoo"),
    }

    sources["Barak Emails"] = {
        "description": "1,411 Ehud Barak email files (.html + .meta)",
        "query_tool": "tools/search_emails.py",
        **check_directory(PROJECT_ROOT / "datasets" / "epstein-archive" / "data" / "emails" / "ehud_barak_emails"),
    }

    # Neo4j
    sources["ICIJ Offshore Leaks"] = {
        "description": "~800K offshore entities (Neo4j)",
        "query_tool": "tools/query_icij.py",
        **check_neo4j(),
    }

    # Corporate Registry
    sources["Corporate Registry"] = {
        "description": "FL, NY, NM, PA corps, officers, filings (unified schema)",
        "query_tool": "tools/query_registry.py",
        **check_sqlite(
            PROJECT_ROOT / "registry.db",
            "SELECT COUNT(*) FROM registry_entities"
        ),
    }

    # Investigations DB (ingested PDFs)
    sources["Investigations DB"] = {
        "description": "Ingested investigation reports (PDF → FTS5)",
        "query_tool": "tools/query_investigations.py",
        **check_sqlite(
            PROJECT_ROOT / "datasets" / "investigations.db",
            "SELECT COUNT(*) FROM documents"
        ),
    }

    # FAA Registry
    sources["FAA Registry"] = {
        "description": "US aircraft registration (owner names, N-numbers, addresses)",
        "query_tool": "tools/ingest_faa.py",
        **check_sqlite(
            PROJECT_ROOT / "datasets" / "faa_registry.db",
            "SELECT COUNT(*) FROM aircraft"
        ),
    }

    # APIs
    sources["DugganUSA API"] = {
        "description": "329K+ docs across all 12 DOJ datasets",
        "query_tool": "tools/duggan_search.py",
        **check_api("DugganUSA", "https://analytics.dugganusa.com/api/v1/search?q=test&indexes=epstein_files&limit=1"),
    }

    sources["LittleSis API"] = {
        "description": "Power network relationships (500+ Epstein connections pre-mapped)",
        "query_tool": "tools/query_littlesis.py",
        **check_api("LittleSis", "https://littlesis.org/api/entities/36043"),
    }

    sources["SEC EDGAR EFTS"] = {
        "description": "Full-text search across all SEC filings (1,237 Epstein hits)",
        "query_tool": "tools/query_edgar.py",
        **check_api("EDGAR", "https://efts.sec.gov/LATEST/search-index?q=test&size=1"),
    }

    # NYC ACRIS Property Records
    sources["NYC ACRIS"] = {
        "description": "NYC property transactions (deeds, mortgages, liens) via SODA API",
        "query_tool": "tools/query_acris.py",
        **check_api("ACRIS"),  # SODA API is slow to respond — skip live check
    }

    # FEC Campaign Finance
    sources["FEC Campaign Finance"] = {
        "description": "Political donations (Schedule A contributions)",
        "query_tool": "tools/query_fec.py",
        **check_api("FEC", "https://api.open.fec.gov/v1/?api_key=DEMO_KEY"),
    }

    # Federal Lobbying (LDA)
    sources["Federal Lobbying (LDA)"] = {
        "description": "1.9M+ lobbying filings, registrants, clients",
        "query_tool": "tools/query_lobbying.py",
        **check_api("LDA", "https://lda.senate.gov/api/v1/filings/?page_size=1"),
    }

    # FARA Foreign Agents
    fara_info = check_sqlite(
        PROJECT_ROOT / "investigation.db",
        "SELECT COUNT(*) FROM fara_registrants"
    )
    if fara_info.get("status") == "error":
        fara_info = {"status": "not_ingested", "records": 0}
        fara_info["start_cmd"] = "python tools/query_fara.py download && python tools/query_fara.py ingest"
    sources["FARA Foreign Agents"] = {
        "description": "7K registrants, 17K foreign principals, 151K documents",
        "query_tool": "tools/query_fara.py",
        **fara_info,
    }

    return sources


def main():
    parser = argparse.ArgumentParser(description="Epstein OSINT data source report")
    parser.add_argument("-j", "--json", action="store_true")
    args = parser.parse_args()

    sources = generate_report()

    if args.json:
        print(json.dumps(sources, indent=2))
        return

    print("\n" + "=" * 80)
    print("EPSTEIN OSINT DATA SOURCE REPORT")
    print("=" * 80)

    available = 0
    total = len(sources)

    for name, info in sources.items():
        status = info.get("status", "?")
        icon = {"available": "[OK]", "running": "[OK]", "configured": "[OK]",
                "missing": "[--]", "stopped": "[!!]", "error": "[!!]", "unknown": "[??]"}.get(status, "[??]")

        records = info.get("records", "")
        records_str = f" ({records:,} records)" if isinstance(records, int) and records > 0 else ""
        size = info.get("size_mb", "")
        size_str = f" [{size} MB]" if size else ""

        print(f"\n{icon} {name}{records_str}{size_str}")
        print(f"     {info['description']}")
        print(f"     Tool: {info.get('query_tool', '?')}")
        if info.get("start_cmd"):
            print(f"     Start: {info['start_cmd']}")
        if info.get("error"):
            print(f"     Error: {info['error']}")

        if status in ("available", "running", "configured"):
            available += 1

    print(f"\n{'='*80}")
    print(f"Sources available: {available}/{total}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
