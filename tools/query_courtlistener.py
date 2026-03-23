#!/usr/bin/env python3
"""
CourtListener API wrapper for OSINT investigations.

Loads credentials from .env and provides investigation-friendly output.

Usage:
    python tools/query_courtlistener.py search "Jeffrey Epstein"
    python tools/query_courtlistener.py cases "Epstein" --court nysd
    python tools/query_courtlistener.py docket 16066603
    python tools/query_courtlistener.py party "Ghislaine Maxwell"
    python tools/query_courtlistener.py opinions "Epstein" --court ca2
    python tools/query_courtlistener.py judge "Preska"
    python tools/query_courtlistener.py disclosures --person-id 1234
"""

import argparse
import json
import os
import sys
from pathlib import Path

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


# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"'))

def _client():
    try:
        from tools.courtlistener_api_client import CourtListenerClient
    except ImportError:
        from courtlistener_api_client import CourtListenerClient

    token = os.environ.get("COURTLISTENER_TOKEN")
    if not token:
        print("ERROR: COURTLISTENER_TOKEN not set in .env", file=sys.stderr)
        sys.exit(1)
    return CourtListenerClient(token=token)


def cmd_search(args):
    """Generic search (defaults to RECAP/dockets)."""
    client = _client()
    results = client.search(
        args.query,
        search_type=args.type,
        court=args.court,
        max_results=args.limit,
    )

    _log(args.query, "courtlistener", len(results))

    if write_output(results, args, summary=f"CourtListener search '{args.query}'"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(results, indent=2, default=str))
        return

    print(f"Found {len(results)} results for '{args.query}' (type={args.type})")
    print()
    for r in results:
        court = r.get("court", r.get("court_id", "?"))
        case_name = r.get("caseName", r.get("case_name", "?"))
        date = r.get("dateFiled", r.get("date_filed", ""))
        url = r.get("docket_absolute_url", r.get("absolute_url", ""))
        print(f"  [{court}] {case_name}")
        if date:
            print(f"    Filed: {date}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        # Show snippet if available
        snippet = r.get("snippet", r.get("text", ""))
        if snippet:
            clean = snippet.replace("<mark>", "**").replace("</mark>", "**")
            print(f"    Snippet: {clean[:200]}")
        print()


def cmd_cases(args):
    """Search RECAP dockets specifically."""
    client = _client()
    results = client.search_cases(
        args.query,
        court=args.court,
        date_filed_after=args.after,
        date_filed_before=args.before,
        max_results=args.limit,
    )
    _log(args.query, "courtlistener", len(results))
    print(f"Found {len(results)} cases for '{args.query}'")
    print()
    for r in results:
        court = r.get("court", "?")
        case_name = r.get("caseName", "?")
        date = r.get("dateFiled", "")
        docket_num = r.get("docketNumber", "")
        nos = r.get("suitNature", "")
        url = r.get("docket_absolute_url", "")
        print(f"  [{court}] {case_name}")
        if docket_num:
            print(f"    Docket #: {docket_num}")
        if date:
            print(f"    Filed: {date}")
        if nos:
            print(f"    Nature of suit: {nos}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        print()


def cmd_docket(args):
    """Get docket details by ID."""
    client = _client()
    docket = client.get_docket(args.docket_id)

    if write_output(docket, args, summary=f"CourtListener docket #{args.docket_id}"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(docket, indent=2, default=str))
        return

    print(f"=== Docket #{args.docket_id} ===")
    print(f"Case: {docket.get('case_name', '?')}")
    print(f"Court: {docket.get('court', '?')}")
    print(f"Docket #: {docket.get('docket_number', '?')}")
    print(f"Filed: {docket.get('date_filed', '?')}")
    print(f"Terminated: {docket.get('date_terminated', 'ongoing')}")
    print(f"Nature of suit: {docket.get('nature_of_suit', '?')}")
    print(f"Cause: {docket.get('cause', '?')}")
    judges = docket.get("assigned_to_str", "") or docket.get("referred_to_str", "")
    if judges:
        print(f"Judge: {judges}")
    print(f"URL: https://www.courtlistener.com{docket.get('absolute_url', '')}")
    print()


def cmd_party(args):
    """Search parties across all cases."""
    client = _client()
    parties = client.search_party_by_name(args.name, max_results=args.limit)
    _log(args.name, "courtlistener", len(parties))
    print(f"Found {len(parties)} party records for '{args.name}'")
    print()
    for p in parties:
        name = p.get("name", "?")
        docket_url = p.get("docket", "")
        party_types = [pt.get("name", "?") for pt in p.get("party_types", [])]
        attorneys = p.get("attorneys", [])
        print(f"  {name} ({', '.join(party_types) if party_types else '?'})")
        if docket_url:
            print(f"    Docket: {docket_url}")
        if attorneys:
            for att in attorneys[:3]:
                att_name = att.get("name", "?")
                att_firm = att.get("firm_name", "")
                print(f"    Attorney: {att_name}" + (f" ({att_firm})" if att_firm else ""))
        print()


def cmd_opinions(args):
    """Search opinions."""
    client = _client()
    results = client.search(
        args.query,
        search_type="o",
        court=args.court,
        max_results=args.limit,
    )
    print(f"Found {len(results)} opinions for '{args.query}'")
    print()
    for r in results:
        case_name = r.get("caseName", "?")
        court = r.get("court", "?")
        date = r.get("dateFiled", "")
        cite = r.get("citation", [])
        url = r.get("absolute_url", "")
        print(f"  [{court}] {case_name}")
        if date:
            print(f"    Date: {date}")
        if cite:
            print(f"    Citations: {cite}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        snippet = r.get("snippet", "")
        if snippet:
            clean = snippet.replace("<mark>", "**").replace("</mark>", "**")
            print(f"    Snippet: {clean[:200]}")
        print()


def cmd_judge(args):
    """Search judges."""
    client = _client()
    judges = client.search_judges(name=args.name, max_results=args.limit)
    print(f"Found {len(judges)} judges matching '{args.name}'")
    for j in judges:
        name = j.get("name_full", "?")
        positions = j.get("positions", [])
        print(f"  {name} (ID: {j.get('id', '?')})")
        for pos in positions[:3]:
            court = pos.get("court", {}).get("short_name", "?")
            title = pos.get("position_type", "?")
            print(f"    {title} at {court}")
        print()


def cmd_disclosures(args):
    """Get financial disclosures for a judge."""
    client = _client()
    results = client.get_financial_disclosures(
        person_id=args.person_id,
        year=args.year,
        max_results=args.limit,
    )

    if write_output(results, args, summary=f"CourtListener disclosures"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(results, indent=2, default=str))
        return

    print(f"Found {len(results)} disclosure records")
    for d in results:
        year = d.get("year", "?")
        person = d.get("person", "?")
        print(f"  Year {year} — Person ID: {person}")
        if d.get("has_been_extracted"):
            print(f"    Extracted: Yes")
        print()


def cmd_opinion(args):
    """Fetch full opinion text by opinion ID or cluster ID."""
    client = _client()
    try:
        opinion = client.get_opinion(args.opinion_id)
    except Exception:
        # Try as cluster ID
        try:
            import requests
            token = os.environ.get("COURTLISTENER_TOKEN", "")
            headers = {"Authorization": f"Token {token}"} if token else {}
            r = requests.get(
                f"https://www.courtlistener.com/api/rest/v4/clusters/{args.opinion_id}/",
                headers=headers,
            )
            r.raise_for_status()
            cluster = r.json()
            # Get the first opinion from the cluster
            opinion_urls = cluster.get("sub_opinions", [])
            if opinion_urls:
                oid = opinion_urls[0].rstrip("/").split("/")[-1]
                opinion = client.get_opinion(int(oid))
            else:
                print("No opinions found in this cluster.", file=sys.stderr)
                return
        except Exception as e:
            print(f"ERROR: Could not fetch opinion: {e}", file=sys.stderr)
            return

    if write_output(opinion, args, summary=f"CourtListener opinion #{args.opinion_id}"):
        return

    # Extract text from available fields (priority order)
    text = ""
    for field in ["html_lawbox", "html_columbia", "html_with_citations", "html", "plain_text", "xml_harvard"]:
        content = opinion.get(field, "")
        if content and len(content) > 100:
            text = content
            print(f"─── Opinion (source: {field}, {len(text):,} chars) ───")
            break

    if not text:
        print("No opinion text available.", file=sys.stderr)
        return

    # Strip HTML if needed
    if text.startswith("<"):
        import re, html as html_mod
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<(?:br|p|div|tr|li|h[1-6])[^>]*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = html_mod.unescape(text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)

    lines = text.split("\n")
    for line in lines[:args.lines]:
        print(line)
    if len(lines) > args.lines:
        print(f"\n... ({len(lines) - args.lines} more lines)")

    _log(str(args.opinion_id), "courtlistener_opinion", 1)


def cmd_recap_search(args):
    """Search RECAP documents for a case. Uses the search API (type=rd)."""
    client = _client()
    results = client.search(
        args.query,
        search_type="rd",
        court=args.court,
        max_results=args.limit,
    )

    if write_output(results, args, summary=f"RECAP doc search '{args.query}': {len(results)} results"):
        return

    print(f"Found {len(results)} RECAP documents for '{args.query}'")
    print()
    for r in results:
        desc = r.get("short_description") or r.get("description") or "?"
        entry_num = r.get("entry_number", "?")
        date = r.get("entry_date_filed", "?")
        pages = r.get("page_count", "?")
        filepath = r.get("filepath_local", "")
        is_available = r.get("is_available", False)
        docket_url = r.get("docket_absolute_url", "")

        print(f"  [{entry_num}] {date} | {desc[:80]}")
        print(f"       Pages: {pages} | Available: {is_available}")
        if filepath:
            print(f"       Download: https://storage.courtlistener.com/{filepath}")
        if docket_url:
            print(f"       Docket: https://www.courtlistener.com{docket_url}")
        print()

    _log(args.query, "courtlistener_recap", len(results))


def cmd_download(args):
    """Download a RECAP document PDF from CourtListener storage."""
    import requests

    url = args.url
    if not url.startswith("http"):
        # Assume it's a filepath_local — prepend storage URL
        url = f"https://storage.courtlistener.com/{url}"

    print(f"Downloading: {url}", file=sys.stderr)
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        print(f"ERROR: HTTP {r.status_code}", file=sys.stderr)
        return

    outpath = args.output_file
    with open(outpath, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    size_kb = os.path.getsize(outpath) / 1024
    print(f"Downloaded {size_kb:.0f}KB to {outpath}")

    # If it's a PDF and the user wants text extraction, try pymupdf
    if outpath.endswith(".pdf") and args.extract_text:
        try:
            import fitz  # pymupdf
            doc = fitz.open(outpath)
            text_path = outpath.replace(".pdf", ".txt")
            with open(text_path, "w") as f:
                for page in doc:
                    f.write(page.get_text())
                    f.write("\n--- PAGE BREAK ---\n")
            print(f"Extracted text ({doc.page_count} pages) to {text_path}")
            doc.close()
        except ImportError:
            print("WARNING: pymupdf not installed, cannot extract text. Install with: uv add pymupdf", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="CourtListener API for OSINT investigation")
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p = sub.add_parser("search", help="Search (generic)")
    p.add_argument("query")
    p.add_argument("--type", default="r", help="o=opinions, r=recap/dockets, p=people")
    p.add_argument("--court", help="Court filter (e.g., nysd, ca2, scotus)")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # cases
    p = sub.add_parser("cases", help="Search RECAP dockets")
    p.add_argument("query")
    p.add_argument("--court")
    p.add_argument("--after", help="Filed after (YYYY-MM-DD)")
    p.add_argument("--before", help="Filed before (YYYY-MM-DD)")
    p.add_argument("--limit", type=int, default=20)

    # docket
    p = sub.add_parser("docket", help="Get docket by ID")
    p.add_argument("docket_id", type=int)
    add_output_args(p)

    # party
    p = sub.add_parser("party", help="Search parties")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=20)

    # opinions
    p = sub.add_parser("opinions", help="Search opinions")
    p.add_argument("query")
    p.add_argument("--court")
    p.add_argument("--limit", type=int, default=20)

    # judge
    p = sub.add_parser("judge", help="Search judges")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=10)

    # disclosures
    p = sub.add_parser("disclosures", help="Financial disclosures")
    p.add_argument("--person-id", type=int, help="Judge person ID")
    p.add_argument("--year", type=int)
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # opinion — full text by ID
    p = sub.add_parser("opinion", help="Fetch full opinion text by ID")
    p.add_argument("opinion_id", type=int, help="Opinion ID or cluster ID")
    p.add_argument("--lines", type=int, default=500, help="Max lines to show")
    add_output_args(p)

    # recap-search — find RECAP documents
    p = sub.add_parser("recap-search", help="Search RECAP documents (type=rd)")
    p.add_argument("query", help="Search query")
    p.add_argument("--court", help="Court filter")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # download — fetch RECAP PDF
    p = sub.add_parser("download", help="Download a RECAP document PDF")
    p.add_argument("url", help="Full URL or filepath_local from RECAP")
    p.add_argument("output_file", help="Local path to save the PDF")
    p.add_argument("--extract-text", action="store_true", help="Extract text from PDF via pymupdf")

    args = parser.parse_args()
    # Propagate json_out to all subcommands (fallback if not present)
    if not hasattr(args, "json_out"):
        args.json_out = False

    handlers = {
        "search": cmd_search,
        "cases": cmd_cases,
        "docket": cmd_docket,
        "party": cmd_party,
        "opinions": cmd_opinions,
        "judge": cmd_judge,
        "disclosures": cmd_disclosures,
        "opinion": cmd_opinion,
        "recap-search": cmd_recap_search,
        "download": cmd_download,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
