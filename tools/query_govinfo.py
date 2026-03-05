#!/usr/bin/env python3
"""
GovInfo (GPO) congressional hearings, committee reports, GAO reports, and CRS reports.

Covers CHRG (hearings, 1997+), CRPT (committee reports), GAOREPORTS, and CRS collections.
Free API via api.data.gov key. Rate limit: ~1,000/hour.

Usage:
    python tools/query_govinfo.py search "Deutsche Bank" --collection CHRG
    python tools/query_govinfo.py search "shell companies" --collection GAOREPORTS --limit 10
    python tools/query_govinfo.py search "beneficial ownership" --collection CRS
    python tools/query_govinfo.py document CHRG-116shrg12345
    python tools/query_govinfo.py hearing CHRG-116shrg12345
    python tools/query_govinfo.py ingest CHRG-116shrg12345
    python tools/query_govinfo.py ingest-search "Epstein" --collection CHRG --limit 5
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from tools.output_util import add_output_args, write_output
    from tools.lead_tracker import log_search
except ImportError:
    from output_util import add_output_args, write_output
    from lead_tracker import log_search

BASE_URL = "https://api.govinfo.gov"
RATE_LIMIT = 0.5  # seconds between requests
COLLECTIONS = ["CHRG", "CRPT", "GAOREPORTS", "CRS"]

PROJECT_ROOT = Path(__file__).parent.parent


def _get_api_key():
    """Get GovInfo API key from environment."""
    key = os.environ.get("GOVINFO_API_KEY")
    if not key:
        # Try loading from .env
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("GOVINFO_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return key


def _request(endpoint, params=None):
    """Make authenticated request to GovInfo API."""
    api_key = _get_api_key()
    if not api_key:
        print("ERROR: GOVINFO_API_KEY not set. Get a free key at https://api.data.gov/signup/", file=sys.stderr)
        sys.exit(1)

    if params is None:
        params = {}
    params["api_key"] = api_key

    url = f"{BASE_URL}{endpoint}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"

    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "OSINT-Research/1.0",
    })

    time.sleep(RATE_LIMIT)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if e.code == 429:
            print("ERROR: Rate limit exceeded. Wait and retry.", file=sys.stderr)
        else:
            print(f"ERROR: HTTP {e.code}: {body[:200]}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"ERROR: {e.reason}", file=sys.stderr)
        return None


def _flatten_result(item):
    """Flatten a GovInfo search result into a clean dict."""
    return {
        "packageId": item.get("packageId"),
        "title": item.get("title"),
        "congress": item.get("congress"),
        "session": item.get("session"),
        "dateIssued": item.get("dateIssued"),
        "collectionCode": item.get("collectionCode"),
        "category": item.get("category"),
        "branch": item.get("branch"),
        "governmentAuthor1": item.get("governmentAuthor1"),
        "governmentAuthor2": item.get("governmentAuthor2"),
        "suDocClassNumber": item.get("suDocClassNumber"),
        "pages": item.get("pages"),
        "lastModified": item.get("lastModified"),
    }


def _print_result(r):
    """Pretty-print a single search result."""
    pkg = r.get("packageId", "?")
    title = r.get("title", "")
    date = r.get("dateIssued", "?")
    coll = r.get("collectionCode", "?")
    congress = r.get("congress", "")
    author = r.get("governmentAuthor1", "")
    pages = r.get("pages")

    print(f"\n  [{pkg}]")
    print(f"  {title}")
    parts = [f"Date: {date}", f"Collection: {coll}"]
    if congress:
        parts.append(f"Congress: {congress}")
    if author:
        parts.append(f"Author: {author}")
    if pages:
        parts.append(f"Pages: {pages}")
    print(f"  {' | '.join(parts)}")


def cmd_search(args):
    """Full-text search across GovInfo collections."""
    params = {
        "query": args.query,
        "pageSize": min(args.limit, 100),
        "offsetMark": "*",
    }
    if args.collection:
        params["collection"] = args.collection

    data = _request("/search", params)
    if not data:
        print("No results or API error.")
        return

    results = [_flatten_result(r) for r in data.get("results", [])]
    total = data.get("count", len(results))
    output = {"total": total, "query": args.query, "results": results}

    collection_label = args.collection or "all"
    log_search(f"govinfo_{collection_label.lower()}", args.query, total)

    if not write_output(output, args, summary=f"GovInfo search '{args.query}' ({collection_label})"):
        print(f"GovInfo: {total} results for '{args.query}' in {collection_label}")
        for r in results:
            _print_result(r)


def cmd_document(args):
    """Fetch full document metadata by package ID."""
    data = _request(f"/packages/{args.package_id}/summary")
    if not data:
        print(f"No document found for {args.package_id}")
        sys.exit(1)

    log_search("govinfo_document", f"doc:{args.package_id}", 1)

    if not write_output(data, args, summary=f"GovInfo document {args.package_id}"):
        title = data.get("title", "?")
        date = data.get("dateIssued", "?")
        coll = data.get("collectionCode", "?")
        congress = data.get("congress", "")

        print(f"\n  Package: {args.package_id}")
        print(f"  Title: {title}")
        print(f"  Date: {date} | Collection: {coll}")
        if congress:
            print(f"  Congress: {congress}")

        # Show download links
        download = data.get("download", {})
        if download:
            print(f"\n  Downloads:")
            for fmt, url in download.items():
                print(f"    {fmt}: {url}")

        # Show related
        related = data.get("related", {})
        if related:
            print(f"\n  Related:")
            for rel_type, url in related.items():
                print(f"    {rel_type}: {url}")


def cmd_hearing(args):
    """Fetch hearing details including committee, witnesses, and links."""
    # Get summary first
    data = _request(f"/packages/{args.package_id}/summary")
    if not data:
        print(f"No hearing found for {args.package_id}")
        sys.exit(1)

    # Get granules (individual testimony, sections)
    granules = _request(f"/packages/{args.package_id}/granules", {"pageSize": 100})
    if granules:
        data["granules"] = granules.get("granules", [])

    log_search("govinfo_hearing", f"hearing:{args.package_id}", 1)

    if not write_output(data, args, summary=f"GovInfo hearing {args.package_id}"):
        title = data.get("title", "?")
        date = data.get("dateIssued", "?")
        committee = data.get("committees", [])

        print(f"\n  Hearing: {args.package_id}")
        print(f"  Title: {title}")
        print(f"  Date: {date}")
        if committee:
            for c in committee:
                name = c.get("committeeName") or c.get("authorityId", "?")
                print(f"  Committee: {name}")

        members = data.get("members", [])
        if members:
            print(f"\n  Members/Witnesses ({len(members)}):")
            for m in members[:20]:
                print(f"    - {m.get('memberName', '?')}")

        grans = data.get("granules", [])
        if grans:
            print(f"\n  Granules ({len(grans)} sections):")
            for g in grans[:10]:
                print(f"    [{g.get('granuleId', '?')}] {g.get('title', '?')}")


def cmd_ingest(args):
    """Download PDF and ingest via ingest_pdf.py pipeline."""
    # Get document summary to find PDF URL
    data = _request(f"/packages/{args.package_id}/summary")
    if not data:
        print(f"No document found for {args.package_id}")
        sys.exit(1)

    download = data.get("download", {})
    pdf_url = download.get("pdfLink") or download.get("txtLink")
    if not pdf_url:
        # Try constructing PDF URL from package ID
        pdf_url = f"https://www.govinfo.gov/content/pkg/{args.package_id}/pdf/{args.package_id}.pdf"

    title = data.get("title", args.package_id)
    date = data.get("dateIssued", "")
    year = date[:4] if date else None
    collection = data.get("collectionCode", "CHRG")

    # Download PDF to temp location
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    print(f"Downloading {args.package_id}...")
    try:
        req = Request(pdf_url, headers={"User-Agent": "OSINT-Research/1.0"})
        with urlopen(req, timeout=120) as resp:
            with open(tmp_path, "wb") as f:
                f.write(resp.read())
    except (HTTPError, URLError) as e:
        print(f"ERROR: Failed to download PDF: {e}", file=sys.stderr)
        sys.exit(1)

    # Map collection to category
    category_map = {
        "CHRG": "congressional",
        "CRPT": "congressional",
        "GAOREPORTS": "government_report",
        "CRS": "government_report",
    }
    category = category_map.get(collection, "congressional")

    # Ingest via ingest_pdf.py
    ingest_cmd = [
        sys.executable, str(PROJECT_ROOT / "tools" / "ingest_pdf.py"),
        "ingest", tmp_path,
        "--title", title[:200],
        "--source", f"GovInfo:{args.package_id}",
        "--category", category,
    ]
    if year:
        ingest_cmd.extend(["--year", year])

    result = subprocess.run(ingest_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)

    # Clean up
    Path(tmp_path).unlink(missing_ok=True)

    log_search("govinfo_ingest", f"ingest:{args.package_id}", 1)


def cmd_ingest_search(args):
    """Search and bulk ingest matching documents."""
    params = {
        "query": args.query,
        "pageSize": min(args.limit, 100),
        "offsetMark": "*",
    }
    if args.collection:
        params["collection"] = args.collection

    data = _request("/search", params)
    if not data:
        print("No results or API error.")
        return

    results = data.get("results", [])
    total = data.get("count", len(results))
    print(f"Found {total} results for '{args.query}'. Ingesting {len(results)}...")

    ingested = 0
    for r in results:
        pkg_id = r.get("packageId")
        if not pkg_id:
            continue

        print(f"\n--- Ingesting {pkg_id} ---")

        # Create a namespace for the ingest args
        ingest_args = argparse.Namespace(package_id=pkg_id)
        try:
            cmd_ingest(ingest_args)
            ingested += 1
        except SystemExit:
            print(f"  Skipped {pkg_id} (download/ingest failed)")
            continue

    collection_label = args.collection or "all"
    log_search(f"govinfo_{collection_label.lower()}", f"ingest-search:{args.query}", total)
    print(f"\nIngested {ingested}/{len(results)} documents.")


def main():
    parser = argparse.ArgumentParser(
        description="GovInfo congressional hearings, reports, GAO, and CRS",
        epilog="Auth: GOVINFO_API_KEY (free at https://api.data.gov/signup/). Rate: ~1,000/hour.",
    )
    sub = parser.add_subparsers(dest="command")

    # search
    p_search = sub.add_parser("search", help="Full-text search across GovInfo collections")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--collection", choices=COLLECTIONS, help="Limit to collection (CHRG, CRPT, GAOREPORTS, CRS)")
    p_search.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    add_output_args(p_search)

    # document
    p_doc = sub.add_parser("document", help="Fetch document metadata by package ID")
    p_doc.add_argument("package_id", help="GovInfo package ID (e.g., CHRG-116shrg12345)")
    add_output_args(p_doc)

    # hearing
    p_hearing = sub.add_parser("hearing", help="Fetch hearing details (committee, witnesses, sections)")
    p_hearing.add_argument("package_id", help="Hearing package ID")
    add_output_args(p_hearing)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Download PDF and ingest via ingest_pdf.py")
    p_ingest.add_argument("package_id", help="Package ID to download and ingest")

    # ingest-search
    p_isearch = sub.add_parser("ingest-search", help="Search and bulk ingest matching documents")
    p_isearch.add_argument("query", help="Search query")
    p_isearch.add_argument("--collection", choices=COLLECTIONS, help="Limit to collection")
    p_isearch.add_argument("--limit", type=int, default=10, help="Max documents to ingest (default: 10)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "search": cmd_search,
        "document": cmd_document,
        "hearing": cmd_hearing,
        "ingest": cmd_ingest,
        "ingest-search": cmd_ingest_search,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
