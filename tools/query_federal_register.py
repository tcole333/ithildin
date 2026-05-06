#!/usr/bin/env python3
"""
Federal Register API wrapper for OSINT investigations.

Free, public API documented at https://www.federalregister.gov/developers/documentation/api/v1.
No authentication required. Covers all Federal Register documents from 1994 onward
(rules, proposed rules, notices, presidential documents — proclamations, executive
orders, memoranda, determinations).

Useful for:
    - Officer appointments and military commissions/promotion lists published as
      presidential documents or DoD/military department notices
    - Civil service / SES nominations published in the Federal Register
    - Tracking executive orders, proclamations, memoranda by date/topic
    - Verifying claims that show up in news reporting against the primary source

Rate limit: ~1 req/sec (self-imposed; the API does not document a hard limit).

Usage:
    # Full-text search
    python tools/query_federal_register.py search "Navy Reserve commission" \
        --start-date 2025-01-01 --end-date 2025-06-30 --output /tmp/fr.json

    # Term search (matches the 'term' condition — phrase/keyword across documents)
    python tools/query_federal_register.py term "Parlatore" --limit 50 --output /tmp/fr.json

    # Documents from a specific agency (slug — see --list-agencies)
    python tools/query_federal_register.py agency navy-department \
        --start-date 2025-01-01 --output /tmp/fr.json

    # Presidential documents only (proclamations, EOs, memoranda, determinations)
    python tools/query_federal_register.py presidential \
        --start-date 2025-03-01 --end-date 2025-04-15 --output /tmp/fr.json
    python tools/query_federal_register.py presidential --type executive_order \
        --start-date 2025-01-20

    # Fetch a specific document's full record + raw text URL
    python tools/query_federal_register.py document 2025-06461

    # List agency slugs (one-time discovery)
    python tools/query_federal_register.py list-agencies | grep -i navy
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output


def _log(query, source, count):
    """Log search to investigation.db search_log (best-effort)."""
    try:
        from tools.lead_tracker import log_search
        log_search(query, source, count)
    except Exception:
        pass


# ─── Constants ───────────────────────────────────────────────────────────────

BASE_URL = "https://www.federalregister.gov/api/v1"
USER_AGENT = "OSINT-Research osint-research@proton.me"
MIN_INTERVAL = 1.0  # 1 req/sec
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 1000  # API caps at 1000

PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DB_PATH = PROJECT_ROOT / "datasets" / "fr_cache.db"
CACHE_TTL = 60 * 60 * 24 * 7  # 7 days

# Presidential document subtypes accepted by the API.
PRESIDENTIAL_TYPES = ["determination", "executive_order", "memorandum",
                      "notice", "proclamation", "other"]

# Federal Register document `type` codes.
DOCUMENT_TYPES = ["RULE", "PRORULE", "NOTICE", "PRESDOCU"]

_last_request = 0.0


# ─── Cache ───────────────────────────────────────────────────────────────────

def _cache_db():
    """Get (and lazily initialize) the local response cache."""
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(CACHE_DB_PATH))
    db.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            payload TEXT NOT NULL,
            fetched_at INTEGER NOT NULL
        )
    """)
    db.commit()
    return db


def _cache_get(key):
    """Return cached JSON payload if not expired."""
    if os.environ.get("FR_NO_CACHE"):
        return None
    try:
        db = _cache_db()
        row = db.execute(
            "SELECT payload, fetched_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        db.close()
        if not row:
            return None
        payload, fetched_at = row
        if time.time() - fetched_at > CACHE_TTL:
            return None
        return json.loads(payload)
    except Exception:
        return None


def _cache_put(key, url, payload):
    try:
        db = _cache_db()
        db.execute(
            "INSERT OR REPLACE INTO cache (key, url, payload, fetched_at) VALUES (?, ?, ?, ?)",
            (key, url, json.dumps(payload), int(time.time())),
        )
        db.commit()
        db.close()
    except Exception:
        pass


# ─── HTTP ────────────────────────────────────────────────────────────────────

def _request(path, params=None, raw=False):
    """Rate-limited GET against the Federal Register API.

    Args:
        path: Path beneath BASE_URL (starts with '/').
        params: Optional dict of query params (use [] notation as keys).
        raw: If True, return raw bytes (e.g., for full-text downloads).

    Returns parsed JSON dict, raw bytes, or None on error.
    """
    global _last_request

    if path.startswith("http://") or path.startswith("https://"):
        url = path
    else:
        url = f"{BASE_URL}{path}"

    if params:
        # urlencode with doseq handles list values (for [] params).
        url = url + ("&" if "?" in url else "?") + urlencode(params, doseq=True)

    cache_key = hashlib.sha256(url.encode()).hexdigest()
    if not raw:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    elapsed = time.time() - _last_request
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json" if not raw else "*/*",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            _last_request = time.time()
            data = resp.read()
            if raw:
                return data
            payload = json.loads(data.decode())
            _cache_put(cache_key, url, payload)
            return payload
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        if e.code == 404:
            print(f"ERROR: 404 Not Found — {url}", file=sys.stderr)
        elif e.code == 429:
            print("ERROR: 429 rate limit — back off and retry", file=sys.stderr)
        else:
            print(f"ERROR: HTTP {e.code} from Federal Register: {body}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"ERROR: Cannot reach Federal Register: {e.reason}", file=sys.stderr)
        return None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_conditions(args):
    """Build the conditions[*] params dict from parsed args.

    Returns a list of (key, value) tuples (so list-valued conditions repeat).
    """
    pairs = []
    if getattr(args, "term", None):
        pairs.append(("conditions[term]", args.term))
    if getattr(args, "start_date", None):
        pairs.append(("conditions[publication_date][gte]", args.start_date))
    if getattr(args, "end_date", None):
        pairs.append(("conditions[publication_date][lte]", args.end_date))
    if getattr(args, "agency", None):
        # agency arg may be a single slug or a list.
        agencies = args.agency if isinstance(args.agency, list) else [args.agency]
        for a in agencies:
            pairs.append(("conditions[agencies][]", a))
    if getattr(args, "doc_type", None):
        types = args.doc_type if isinstance(args.doc_type, list) else [args.doc_type]
        for t in types:
            pairs.append(("conditions[type][]", t))
    if getattr(args, "presidential_type", None):
        # presidential_document_type accepts a single value
        pairs.append(("conditions[presidential_document_type][]", args.presidential_type))
    return pairs


def _flatten_article(item):
    """Reduce a Federal Register article record to the most useful fields."""
    agencies = item.get("agencies") or []
    return {
        "document_number": item.get("document_number"),
        "title": item.get("title"),
        "type": item.get("type"),
        "subtype": item.get("subtype"),
        "publication_date": item.get("publication_date"),
        "abstract": item.get("abstract"),
        "agencies": [
            {"name": a.get("name"), "slug": a.get("slug"), "id": a.get("id")}
            for a in agencies
        ],
        "html_url": item.get("html_url"),
        "pdf_url": item.get("pdf_url"),
        "raw_text_url": item.get("raw_text_url"),
        "full_text_xml_url": item.get("full_text_xml_url"),
        "presidential_document_number": item.get("presidential_document_number"),
        "executive_order_number": item.get("executive_order_number"),
        "proclamation_number": item.get("proclamation_number"),
        "citation": item.get("citation"),
        "excerpts": item.get("excerpts"),
    }


def _print_article(i, art):
    title = art.get("title") or "(untitled)"
    pub = art.get("publication_date") or "?"
    typ = art.get("type") or art.get("subtype") or "?"
    docnum = art.get("document_number") or "?"
    agencies = art.get("agencies") or []
    agency_names = ", ".join(a.get("name", "") for a in agencies if a.get("name"))
    print(f"  [{i}] {pub} | {typ} | {docnum}")
    print(f"      {title}")
    if agency_names:
        print(f"      Agencies: {agency_names}")
    if art.get("html_url"):
        print(f"      {art['html_url']}")


def _paginate_articles(initial_params, max_results):
    """Pull articles from the /documents endpoint, following next_page_url.

    Stops once we hit max_results or run out of pages. Always returns a list of
    raw API article records (not flattened).
    """
    per_page = min(MAX_PER_PAGE, max_results) if max_results else DEFAULT_PER_PAGE
    params = list(initial_params)
    params.append(("per_page", per_page))
    params.append(("order", "newest"))
    # Restrict response fields to keep payloads small.
    fields = [
        "document_number", "title", "type", "subtype", "publication_date",
        "abstract", "agencies", "html_url", "pdf_url", "raw_text_url",
        "full_text_xml_url", "presidential_document_number",
        "executive_order_number", "proclamation_number", "citation", "excerpts",
    ]
    for f in fields:
        params.append(("fields[]", f))

    results = []
    next_path = "/documents"
    next_params = params
    total = None
    pages_walked = 0
    while next_path and (max_results is None or len(results) < max_results):
        data = _request(next_path, next_params)
        if not data:
            break
        if total is None:
            total = data.get("count", 0)
        page_results = data.get("results") or []
        results.extend(page_results)
        pages_walked += 1
        if max_results and len(results) >= max_results:
            break
        # next_page_url is a fully-qualified URL we can fetch directly
        nxt = data.get("next_page_url")
        if not nxt:
            break
        next_path = nxt
        next_params = None  # already encoded in next_page_url
        # Hard ceiling: walk at most 50 pages to avoid runaway loops
        if pages_walked >= 50:
            break

    if max_results:
        results = results[:max_results]
    return results, (total if total is not None else len(results))


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_search(args):
    """Full-text search."""
    if not args.query:
        print("ERROR: search requires a query string", file=sys.stderr)
        sys.exit(2)
    args.term = args.query  # `conditions[term]` is FR's full-text search
    pairs = _build_conditions(args)
    results, total = _paginate_articles(pairs, args.limit)
    flat = [_flatten_article(r) for r in results]

    output = {
        "query": args.query,
        "filters": {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "agency": args.agency,
            "doc_type": args.doc_type,
            "presidential_type": args.presidential_type,
        },
        "count": total,
        "results": flat,
    }

    _log(f"fr_search:{args.query}", "federal_register", total)

    if write_output(output, args, summary=f"Federal Register search '{args.query}' ({total} hits)"):
        return
    if args.json_out:
        print(json.dumps(output, indent=2, default=str))
        return

    print(f"Federal Register: '{args.query}' — {total:,} total (showing {len(flat)})")
    print()
    for i, art in enumerate(flat, 1):
        _print_article(i, art)
        print()


def cmd_term(args):
    """Search documents by named term (alias for search, but explicit)."""
    if not args.query:
        print("ERROR: term requires a search term", file=sys.stderr)
        sys.exit(2)
    args.term = args.query
    pairs = _build_conditions(args)
    results, total = _paginate_articles(pairs, args.limit)
    flat = [_flatten_article(r) for r in results]

    output = {
        "query": args.query,
        "term": args.query,
        "filters": {
            "start_date": args.start_date,
            "end_date": args.end_date,
        },
        "count": total,
        "results": flat,
    }

    _log(f"fr_term:{args.query}", "federal_register", total)

    if write_output(output, args, summary=f"Federal Register term '{args.query}' ({total} hits)"):
        return
    if args.json_out:
        print(json.dumps(output, indent=2, default=str))
        return

    print(f"Federal Register term: '{args.query}' — {total:,} total (showing {len(flat)})")
    print()
    for i, art in enumerate(flat, 1):
        _print_article(i, art)
        print()


def cmd_agency(args):
    """List documents from a specific agency."""
    if not args.agency_slug:
        print("ERROR: agency requires a slug (see list-agencies)", file=sys.stderr)
        sys.exit(2)
    args.agency = args.agency_slug
    args.term = args.query if getattr(args, "query", None) else None
    pairs = _build_conditions(args)
    results, total = _paginate_articles(pairs, args.limit)
    flat = [_flatten_article(r) for r in results]

    output = {
        "query": args.query or "",
        "agency": args.agency_slug,
        "filters": {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "doc_type": args.doc_type,
        },
        "count": total,
        "results": flat,
    }

    _log(f"fr_agency:{args.agency_slug}", "federal_register", total)

    if write_output(output, args, summary=f"Federal Register agency {args.agency_slug} ({total} hits)"):
        return
    if args.json_out:
        print(json.dumps(output, indent=2, default=str))
        return

    print(f"Federal Register agency: {args.agency_slug} — {total:,} total (showing {len(flat)})")
    print()
    for i, art in enumerate(flat, 1):
        _print_article(i, art)
        print()


def cmd_presidential(args):
    """Search presidential documents (proclamations, EOs, memoranda)."""
    args.term = args.query if getattr(args, "query", None) else None
    args.doc_type = ["PRESDOCU"]
    pairs = _build_conditions(args)
    results, total = _paginate_articles(pairs, args.limit)
    flat = [_flatten_article(r) for r in results]

    output = {
        "query": args.query or "",
        "presidential_type": args.presidential_type,
        "filters": {
            "start_date": args.start_date,
            "end_date": args.end_date,
        },
        "count": total,
        "results": flat,
    }

    _log(f"fr_presidential:{args.presidential_type or 'all'}",
         "federal_register", total)

    if write_output(output, args, summary=f"Federal Register presidential {args.presidential_type or 'all'} ({total} hits)"):
        return
    if args.json_out:
        print(json.dumps(output, indent=2, default=str))
        return

    label = args.presidential_type or "all presidential"
    print(f"Federal Register presidential: {label} — {total:,} total (showing {len(flat)})")
    print()
    for i, art in enumerate(flat, 1):
        _print_article(i, art)
        print()


def cmd_document(args):
    """Fetch a specific document by document_number."""
    if not args.document_number:
        print("ERROR: document requires a document_number", file=sys.stderr)
        sys.exit(2)

    data = _request(f"/documents/{args.document_number}")
    if not data:
        print(f"ERROR: no document found for {args.document_number}", file=sys.stderr)
        sys.exit(1)

    full_text = None
    if args.full_text:
        # Prefer the plain-text URL (already paginated as a single doc).
        text_url = data.get("raw_text_url")
        if text_url:
            blob = _request(text_url, raw=True)
            if blob:
                try:
                    full_text = blob.decode("utf-8", errors="replace")
                except Exception:
                    full_text = None

    output = {
        "document_number": args.document_number,
        "metadata": data,
    }
    if full_text is not None:
        output["full_text"] = full_text

    _log(f"fr_document:{args.document_number}", "federal_register", 1)

    if write_output(output, args, summary=f"Federal Register doc {args.document_number}"):
        return
    if args.json_out:
        print(json.dumps(output, indent=2, default=str))
        return

    title = data.get("title", "?")
    pub = data.get("publication_date", "?")
    typ = data.get("type", "?")
    citation = data.get("citation", "")
    print(f"=== {title} ===")
    print(f"  Document: {args.document_number}")
    print(f"  Type: {typ} | Published: {pub}" + (f" | Cite: {citation}" if citation else ""))
    if data.get("html_url"):
        print(f"  HTML:   {data['html_url']}")
    if data.get("pdf_url"):
        print(f"  PDF:    {data['pdf_url']}")
    if data.get("raw_text_url"):
        print(f"  Text:   {data['raw_text_url']}")
    if data.get("agencies"):
        names = ", ".join(a.get("name", "") for a in data["agencies"])
        print(f"  Agencies: {names}")
    if data.get("abstract"):
        print()
        print(f"  Abstract: {data['abstract']}")
    if full_text:
        print()
        print("─── Full text (first 80 lines) ───")
        for line in full_text.splitlines()[:80]:
            print(line)


def cmd_list_agencies(args):
    """List all known Federal Register agency slugs."""
    data = _request("/agencies", {"per_page": 1000})
    if not data:
        print("ERROR: could not load agency list", file=sys.stderr)
        sys.exit(1)
    # /agencies returns a flat list, not a paginated wrapper.
    agencies = data if isinstance(data, list) else data.get("results", [])
    rows = [
        {"slug": a.get("slug"), "id": a.get("id"), "name": a.get("name")}
        for a in agencies
    ]
    rows.sort(key=lambda r: r["slug"] or "")

    output = {"count": len(rows), "results": rows}
    if write_output(output, args, summary=f"Federal Register agencies ({len(rows)})"):
        return
    if args.json_out:
        print(json.dumps(output, indent=2, default=str))
        return
    for r in rows:
        print(f"  {r['slug']:<60} {r['name']}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Federal Register API search (no auth required).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # search — full-text
    p = sub.add_parser("search", help="Full-text search")
    p.add_argument("query", help="Full-text search query")
    p.add_argument("--start-date", help="Earliest publication_date (YYYY-MM-DD)")
    p.add_argument("--end-date", help="Latest publication_date (YYYY-MM-DD)")
    p.add_argument("--agency", action="append",
                   help="Agency slug (repeatable). See list-agencies.")
    p.add_argument("--doc-type", action="append",
                   choices=DOCUMENT_TYPES,
                   help=f"Document type (repeatable): {','.join(DOCUMENT_TYPES)}")
    p.add_argument("--presidential-type", choices=PRESIDENTIAL_TYPES,
                   help=f"Presidential document subtype: {','.join(PRESIDENTIAL_TYPES)}")
    p.add_argument("--limit", type=int, default=DEFAULT_PER_PAGE,
                   help="Max results to return (default 20)")
    add_output_args(p)

    # term — search by named term
    p = sub.add_parser("term", help="Search by term/keyword across documents")
    p.add_argument("query", help="Term (often a person/organization name)")
    p.add_argument("--start-date", help="Earliest publication_date (YYYY-MM-DD)")
    p.add_argument("--end-date", help="Latest publication_date (YYYY-MM-DD)")
    p.add_argument("--limit", type=int, default=DEFAULT_PER_PAGE)
    add_output_args(p)

    # agency — documents from one or more agencies
    p = sub.add_parser("agency", help="Documents from a specific agency")
    p.add_argument("agency_slug", help="Agency slug (e.g., navy-department)")
    p.add_argument("query", nargs="?", help="Optional term filter")
    p.add_argument("--start-date", help="Earliest publication_date (YYYY-MM-DD)")
    p.add_argument("--end-date", help="Latest publication_date (YYYY-MM-DD)")
    p.add_argument("--doc-type", action="append", choices=DOCUMENT_TYPES,
                   help="Filter by document type (repeatable)")
    p.add_argument("--limit", type=int, default=DEFAULT_PER_PAGE)
    add_output_args(p)

    # presidential — presidential documents only
    p = sub.add_parser("presidential", help="Presidential documents only")
    p.add_argument("query", nargs="?", help="Optional term filter")
    p.add_argument("--type", dest="presidential_type", choices=PRESIDENTIAL_TYPES,
                   help="Subtype (executive_order, proclamation, memorandum, ...)")
    p.add_argument("--start-date", help="Earliest publication_date (YYYY-MM-DD)")
    p.add_argument("--end-date", help="Latest publication_date (YYYY-MM-DD)")
    p.add_argument("--limit", type=int, default=DEFAULT_PER_PAGE)
    add_output_args(p)

    # document — fetch by document_number
    p = sub.add_parser("document", help="Fetch a single document by document_number")
    p.add_argument("document_number", help="Federal Register document number")
    p.add_argument("--full-text", action="store_true",
                   help="Also fetch the plain-text body (raw_text_url)")
    add_output_args(p)

    # list-agencies — discover slugs
    p = sub.add_parser("list-agencies", help="List all agency slugs")
    add_output_args(p)

    args = parser.parse_args()
    # Make sure write_output always has the attrs it expects.
    if not hasattr(args, "json_out"):
        args.json_out = False
    if not hasattr(args, "output"):
        args.output = None

    handlers = {
        "search": cmd_search,
        "term": cmd_term,
        "agency": cmd_agency,
        "presidential": cmd_presidential,
        "document": cmd_document,
        "list-agencies": cmd_list_agencies,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
