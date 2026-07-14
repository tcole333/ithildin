#!/usr/bin/env python3
"""
NYSCEF guest-search tool for New York State court e-filing records.

NYSCEF does not expose a public JSON API for guest search. The public portal is
server-rendered and fronted by Cloudflare, so this tool uses a Playwright-backed
browser helper to perform low-volume searches through the same guest workflow a
human uses.

Use for targeted court research, not bulk extraction. NYSCEF's public terms
state that data may not be mined and the site may not be accessed by a bot for
extracting data.

Usage:
    python tools/query_nyscef.py search "Jeffrey Epstein"
    python tools/query_nyscef.py search "Bennet Moskowitz" --attorney
    python tools/query_nyscef.py search "Golden Nugget Atlantic City LLC" --business --limit 10
    python tools/query_nyscef.py case 156728/2019
    python tools/query_nyscef.py new-cases --court "New York County Supreme Court" --date 2019-07-10
    python tools/query_nyscef.py detail AcfkebAfF6itr8YHo86mUQ==
    python tools/query_nyscef.py documents AcfkebAfF6itr8YHo86mUQ==
    python tools/query_nyscef.py download f0TLN3SKZ/mR_PLUS_Xfj5Dbefw== /tmp/petition.pdf
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from output_util import add_output_args, write_output

try:
    from tools.lead_tracker import log_search
except ImportError:
    try:
        from lead_tracker import log_search
    except ImportError:
        def log_search(*a, **kw):
            pass


HELPER_PATH = Path(__file__).parent / "_nyscef_browser_helper.js"
HARD_LIMIT = 50
BASE_URL = "https://iapps.courts.state.ny.us/nyscef"

_UNAVAILABLE_SEARCH_STATUSES = frozenset(
    {"blocked", "challenged", "error", "failed", "failure", "unavailable"}
)
_CHALLENGE_MESSAGE_MARKERS = (
    "to continue, please check the box below",
    "captcha",
    "verify you are human",
    "checking your browser",
    "enable javascript and cookies to continue",
    "cloudflare challenge",
)


def _run_helper(command, payload, timeout=180):
    """Run the NYSCEF browser helper through npx so Playwright is available."""
    if not HELPER_PATH.exists():
        print(f"ERROR: Browser helper not found at {HELPER_PATH}", file=sys.stderr)
        return None

    cmd = [
        "npx",
        "-y",
        "-p",
        "playwright",
        "node",
        str(HELPER_PATH),
        command,
        json.dumps(payload),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        print(
            "ERROR: npx not found. Install Node.js/npm so the NYSCEF browser helper can run.",
            file=sys.stderr,
        )
        return None
    except subprocess.TimeoutExpired:
        print("ERROR: NYSCEF browser helper timed out", file=sys.stderr)
        return None

    if result.stderr:
        for line in result.stderr.strip().splitlines():
            if line.strip():
                print(f"  {line}", file=sys.stderr)

    if result.returncode != 0:
        print(f"ERROR: Browser helper exited with code {result.returncode}", file=sys.stderr)
        return None

    if not result.stdout.strip():
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        print(f"ERROR: Invalid JSON from browser helper: {error}", file=sys.stderr)
        return None


def _normalize_limit(limit):
    """Clamp guest-search page traversal to a small number of records."""
    if limit is None:
        return 20
    if limit > HARD_LIMIT:
        print(
            f"  Limiting requested search to {HARD_LIMIT} records for low-volume use.",
            file=sys.stderr,
        )
        return HARD_LIMIT
    if limit < 1:
        return 1
    return limit


def _normalize_date(value):
    """Accept YYYY-MM-DD or MM/DD/YYYY and pass through unchanged otherwise."""
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    return raw


def _derive_person_fields(query):
    """Split a simple person name into first/middle/last fields."""
    parts = [part for part in query.strip().split() if part]
    if not parts:
        return {"first_name": "", "middle_name": "", "last_name": ""}
    if len(parts) == 1:
        return {"first_name": "", "middle_name": "", "last_name": parts[0]}
    if len(parts) == 2:
        return {"first_name": parts[0], "middle_name": "", "last_name": parts[1]}
    return {
        "first_name": parts[0],
        "middle_name": " ".join(parts[1:-1]),
        "last_name": parts[-1],
    }


def _filter_documents(documents, args):
    """Apply lightweight client-side filters to a parsed document list."""
    filtered = []
    for document in documents:
        if args.doc_type and args.doc_type.lower() not in (document.get("document_type") or "").lower():
            continue
        if args.filed_by and args.filed_by.lower() not in (document.get("filed_by") or "").lower():
            continue
        if args.motion and args.motion.lower() not in (document.get("motion_number") or "").lower():
            continue
        if args.doc_number and args.doc_number != str(document.get("document_number") or ""):
            continue
        if args.status and args.status.lower() not in (document.get("status") or "").lower():
            continue
        filtered.append(document)
    return filtered


def _normalize_search_response(data):
    """Mark NYSCEF anti-bot responses as unavailable, not empty searches."""
    if not isinstance(data, dict):
        return data

    status = str(data.get("status") or "").strip().lower()
    challenge_status = str(data.get("challenge_status") or "").strip().lower()
    message = " ".join(
        str(data.get(key) or "") for key in ("message", "error")
    ).lower()
    challenged = (
        status == "challenged"
        or challenge_status == "challenged"
        or any(marker in message for marker in _CHALLENGE_MESSAGE_MARKERS)
    )
    unavailable = (
        data.get("available") is False
        or data.get("source_available") is False
        or status in _UNAVAILABLE_SEARCH_STATUSES
        or bool(data.get("error"))
        or challenged
    )
    if not unavailable:
        return data

    normalized = dict(data)
    normalized["available"] = False
    normalized["source_available"] = False
    normalized["status"] = "unavailable"
    normalized.setdefault("criteria", [])
    normalized.setdefault("results", [])
    if challenged:
        normalized["challenge_status"] = "challenged"
        normalized.setdefault("reason", "captcha_or_anti_bot_challenge")
    return normalized


def _handle_unavailable_search(data, args, label):
    """Emit a structured unavailable response before result logging."""
    if not isinstance(data, dict) or data.get("available") is not False:
        return False

    detail = data.get("challenge_status") or data.get("status") or "unavailable"
    if write_output(data, args, summary=f"{label} ({detail})"):
        return True

    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, default=str))
        return True

    message = data.get("message") or data.get("error") or data.get("reason")
    suffix = f": {message}" if message else ""
    print(f"{label} unavailable ({detail}){suffix}", file=sys.stderr)
    return True


def _print_search_results(results, criteria):
    if criteria:
        print("Criteria:")
        for item in criteria:
            print(f"  {item}")
        print()

    print(f"Found {len(results)} results")
    print()
    for item in results:
        if not item.get("public_access", True):
            print("  [restricted]")
            print(f"    {item.get('access_message', 'Case not available online')}")
            print()
            continue

        print(f"  {item.get('case_number', '?')} | {item.get('caption', '?')}")
        if item.get("received_date"):
            print(f"    Received: {item['received_date']}")
        status_bits = [item.get("efiling_status"), item.get("case_status")]
        status_bits = [bit for bit in status_bits if bit]
        if status_bits:
            print(f"    Status: {' | '.join(status_bits)}")
        court_bits = [item.get("court"), item.get("case_type")]
        court_bits = [bit for bit in court_bits if bit]
        if court_bits:
            print(f"    {' | '.join(court_bits)}")
        if item.get("docket_id"):
            print(f"    Docket ID: {item['docket_id']}")
        if item.get("document_list_url"):
            print(f"    Documents: {item['document_list_url']}")
        print()


def cmd_search(args):
    payload = {
        "search_type": "attorney" if args.attorney else "party",
        "business_name": args.query if args.business else (args.business_name or ""),
        "first_name": args.first or "",
        "middle_name": args.middle or "",
        "last_name": args.last or "",
        "county": args.county,
        "case_type": args.case_type,
        "filed_from": _normalize_date(args.after),
        "filed_to": _normalize_date(args.before),
        "limit": _normalize_limit(args.limit),
    }

    if args.query and not args.business and not any([args.first, args.middle, args.last]):
        payload.update(_derive_person_fields(args.query))

    data = _run_helper("search-name", payload)
    if not data:
        print("Search failed")
        return

    data = _normalize_search_response(data)
    if _handle_unavailable_search(data, args, "NYSCEF search"):
        return

    results = data.get("results", [])
    log_search(args.query or args.business_name or "[manual]", "nyscef", len(results))

    summary = f"NYSCEF search ({len(results)} results)"
    if write_output(data, args, summary=summary):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, default=str))
        return

    _print_search_results(results, data.get("criteria", []))


def cmd_case(args):
    payload = {
        "query": args.query,
        "mode": args.mode,
        "county": args.county,
        "case_type": args.case_type,
        "filed_from": _normalize_date(args.after),
        "filed_to": _normalize_date(args.before),
        "limit": _normalize_limit(args.limit),
    }

    data = _run_helper("search-case", payload)
    if not data:
        print("Case search failed")
        return

    data = _normalize_search_response(data)
    if _handle_unavailable_search(data, args, "NYSCEF case search"):
        return

    results = data.get("results", [])
    log_search(args.query, "nyscef", len(results))

    if write_output(data, args, summary=f"NYSCEF case search '{args.query}' ({len(results)} results)"):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, default=str))
        return

    _print_search_results(results, data.get("criteria", []))


def cmd_new_cases(args):
    payload = {
        "court": args.court,
        "date": _normalize_date(args.date),
        "limit": _normalize_limit(args.limit),
    }

    data = _run_helper("new-cases", payload)
    if not data:
        print("New-case search failed")
        return

    data = _normalize_search_response(data)
    if _handle_unavailable_search(data, args, "NYSCEF new-cases search"):
        return

    results = data.get("results", [])
    log_search(f"{args.court}:{args.date}", "nyscef", len(results))

    if write_output(
        data,
        args,
        summary=f"NYSCEF new cases {args.court} on {args.date} ({len(results)} results)",
    ):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, default=str))
        return

    _print_search_results(results, data.get("criteria", []))


def cmd_detail(args):
    data = _run_helper("detail", {"docket_id": args.docket_id})
    if not data:
        print(f"Case detail lookup failed for {args.docket_id}")
        return

    if write_output(data, args, summary=f"NYSCEF case detail {args.docket_id}"):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"{data.get('case_number', '?')} | {data.get('court', '?')}")
    if data.get("short_caption"):
        print(f"  Short caption: {data['short_caption']}")
    if data.get("full_caption"):
        print(f"  Full caption: {data['full_caption']}")
    if data.get("case_type"):
        print(f"  Case type: {data['case_type']}")
    if data.get("case_status") or data.get("efiling_status"):
        print(
            f"  Status: {data.get('case_status', '?')} | eFiling: {data.get('efiling_status', '?')}"
        )
    if data.get("assigned_judge"):
        print(f"  Assigned judge: {data['assigned_judge']}")
    if data.get("docket_id"):
        print(f"  Docket ID: {data['docket_id']}")
    if data.get("document_list_url"):
        print(f"  Documents: {data['document_list_url']}")

    plaintiffs = data.get("plaintiffs_petitioners") or []
    if plaintiffs:
        print("\nPlaintiffs/Petitioners:")
        for party in plaintiffs:
            print(f"  {party.get('name', '?')}")
            reps = party.get("representatives") or []
            if reps:
                for rep in reps:
                    org = f" | {rep['organization']}" if rep.get("organization") else ""
                    when = f" on {rep['appeared_on']}" if rep.get("appeared_on") else ""
                    print(f"    {rep.get('name', '?')}{when}{org}")

    defendants = data.get("defendants_respondents") or []
    if defendants:
        print("\nDefendants/Respondents:")
        for party in defendants:
            print(f"  {party.get('name', '?')}")
            reps = party.get("representatives") or []
            if reps:
                for rep in reps:
                    org = f" | {rep['organization']}" if rep.get("organization") else ""
                    when = f" on {rep['appeared_on']}" if rep.get("appeared_on") else ""
                    print(f"    {rep.get('name', '?')}{when}{org}")


def cmd_documents(args):
    payload = {
        "docket_id": args.docket_id,
        "motion_only": args.motion_only,
    }

    data = _run_helper("documents", payload)
    if not data:
        print(f"Document list lookup failed for {args.docket_id}")
        return

    documents = _filter_documents(data.get("documents", []), args)
    if args.limit:
        documents = documents[: args.limit]
    data["documents"] = documents

    if write_output(
        data,
        args,
        summary=f"NYSCEF documents {args.docket_id} ({len(documents)} returned)",
    ):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"{data.get('case_number', '?')} | {data.get('short_caption', '?')}")
    if data.get("print_document_list_url"):
        print(f"  Printable PDF list: {data['print_document_list_url']}")
    if data.get("case_detail_url"):
        print(f"  Case detail: {data['case_detail_url']}")
    print()

    for document in documents:
        line = f"  #{document.get('document_number', '?')} | {document.get('document_type', '?')}"
        if document.get("motion_number"):
            line += f" | Motion #{document['motion_number']}"
        print(line)
        if document.get("description"):
            print(f"    {document['description']}")
        meta = []
        if document.get("filed_by"):
            meta.append(f"Filed by: {document['filed_by']}")
        if document.get("filed_date"):
            meta.append(f"Filed: {document['filed_date']}")
        if document.get("received_date"):
            meta.append(f"Received: {document['received_date']}")
        if document.get("status"):
            meta.append(f"Status: {document['status']}")
        if meta:
            print(f"    {' | '.join(meta)}")
        if document.get("doc_index"):
            print(f"    Doc index: {document['doc_index']}")
        if document.get("document_url"):
            print(f"    PDF: {document['document_url']}")
        print()


def cmd_download(args):
    payload = {
        "output_file": str(Path(args.output_file).expanduser().resolve()),
    }
    if args.target.startswith("http://") or args.target.startswith("https://"):
        payload["url"] = args.target
    else:
        payload["doc_index"] = args.target

    data = _run_helper("download", payload, timeout=240)
    if not data:
        print("Download failed")
        return

    if write_output(data, args, summary=f"NYSCEF download -> {data.get('output_file', args.output_file)}"):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"Saved PDF to {data.get('output_file')}")
    print(f"  Source: {data.get('source_url')}")
    print(f"  Size: {data.get('bytes')} bytes")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Search NYSCEF guest-accessible state court records via browser automation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search by party or attorney name")
    search_parser.add_argument("query", nargs="?", help="Name or business query")
    search_parser.add_argument("--attorney", action="store_true", help="Search attorney names instead of parties")
    search_parser.add_argument(
        "--business",
        action="store_true",
        help="Treat QUERY as a business/organization name",
    )
    search_parser.add_argument("--business-name", help="Explicit business/organization name")
    search_parser.add_argument("--first", help="Party first name")
    search_parser.add_argument("--middle", help="Party middle name")
    search_parser.add_argument("--last", help="Party last name")
    search_parser.add_argument("--county", help="County filter, e.g. 'New York'")
    search_parser.add_argument("--case-type", help="Case type filter (partial text accepted)")
    search_parser.add_argument("--after", help="Filed on/after date (YYYY-MM-DD or MM/DD/YYYY)")
    search_parser.add_argument("--before", help="Filed on/before date (YYYY-MM-DD or MM/DD/YYYY)")
    search_parser.add_argument("--limit", type=int, default=20)
    add_output_args(search_parser)
    search_parser.set_defaults(func=cmd_search)

    case_parser = subparsers.add_parser("case", help="Search by case identifier")
    case_parser.add_argument("query", help="Case number / identifier, e.g. 156728/2019")
    case_parser.add_argument(
        "--mode",
        choices=["index", "attorney_file", "third_party"],
        default="index",
        help="Identifier type",
    )
    case_parser.add_argument("--county", help="County filter, e.g. 'New York'")
    case_parser.add_argument("--case-type", help="Case type filter (partial text accepted)")
    case_parser.add_argument("--after", help="Filed on/after date (YYYY-MM-DD or MM/DD/YYYY)")
    case_parser.add_argument("--before", help="Filed on/before date (YYYY-MM-DD or MM/DD/YYYY)")
    case_parser.add_argument("--limit", type=int, default=20)
    add_output_args(case_parser)
    case_parser.set_defaults(func=cmd_case)

    new_cases_parser = subparsers.add_parser(
        "new-cases",
        help="List cases filed for a court on a specific date",
    )
    new_cases_parser.add_argument("--court", required=True, help="Court label, e.g. 'New York County Supreme Court'")
    new_cases_parser.add_argument("--date", required=True, help="Date (YYYY-MM-DD or MM/DD/YYYY)")
    new_cases_parser.add_argument("--limit", type=int, default=20)
    add_output_args(new_cases_parser)
    new_cases_parser.set_defaults(func=cmd_new_cases)

    detail_parser = subparsers.add_parser("detail", help="Get case detail by NYSCEF docket ID")
    detail_parser.add_argument("docket_id", help="Opaque docketId from search results")
    add_output_args(detail_parser)
    detail_parser.set_defaults(func=cmd_detail)

    documents_parser = subparsers.add_parser("documents", help="List case documents by docket ID")
    documents_parser.add_argument("docket_id", help="Opaque docketId from search results")
    documents_parser.add_argument("--doc-type", help="Filter document type by substring")
    documents_parser.add_argument("--filed-by", help="Filter filer name by substring")
    documents_parser.add_argument("--motion", help="Filter motion number, e.g. 002")
    documents_parser.add_argument("--doc-number", help="Filter a specific document number")
    documents_parser.add_argument("--status", help="Filter document status by substring")
    documents_parser.add_argument("--motion-only", action="store_true", help="Use the motion-folder view")
    documents_parser.add_argument("--limit", type=int, help="Limit returned documents after filtering")
    add_output_args(documents_parser)
    documents_parser.set_defaults(func=cmd_documents)

    download_parser = subparsers.add_parser(
        "download",
        help="Download a NYSCEF PDF by doc index or full NYSCEF PDF URL",
    )
    download_parser.add_argument("target", help="docIndex or full URL")
    download_parser.add_argument("output_file", help="Path to save the PDF")
    add_output_args(download_parser)
    download_parser.set_defaults(func=cmd_download)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
