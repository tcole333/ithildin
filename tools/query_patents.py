#!/usr/bin/env python3
"""
USPTO patent search and ownership tracing for OSINT investigations.

Searches patents via the USPTO Open Data Portal (ODP) API at api.uspto.gov.
Traces ownership chains via the ODP assignment endpoint. Caches results in a
local SQLite database for portfolio analysis.

USPTO ODP API: 60 req/min (peak), 120 req/min (off-peak 10pm-5am EST).
API key required: register at https://data.uspto.gov/myodp (requires ID.me).
Auth header: X-API-KEY.

Usage:
    python tools/query_patents.py search "machine learning financial fraud"
    python tools/query_patents.py inventor "Tim Draper"
    python tools/query_patents.py assignee "Apollo Global"
    python tools/query_patents.py patent 11234567
    python tools/query_patents.py assignments 11234567
    python tools/query_patents.py portfolio "L Brands"
    python tools/query_patents.py citations 11234567
    python tools/query_patents.py enrich --dry-run
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

# ─── Constants ────────────────────────────────────────────────────────────────

# USPTO Open Data Portal — replaced PatentsView (migrated March 20 2026)
ODP_BASE = "https://api.uspto.gov/api/v1"
ODP_PATENT_APPS = f"{ODP_BASE}/patent/applications"

DB_PATH = Path(__file__).parent.parent / "datasets" / "patents.db"
INVESTIGATION_DB = Path(__file__).parent.parent / "investigation.db"

USER_AGENT = "OSINT-Research osint-research@proton.me"
CACHE_MAX_AGE_DAYS = 30

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"'))

# ─── Rate Limiting ────────────────────────────────────────────────────────────

_last_request = 0.0
MIN_INTERVAL = 1.0  # 60 req/min peak


# ─── Errors ───────────────────────────────────────────────────────────────────

class PatentSourceUnavailable(RuntimeError):
    """Raised when USPTO ODP could not answer a request."""


# ─── Logging ──────────────────────────────────────────────────────────────────

def _log(query, source, count):
    """Log search to prevent redundant queries."""
    try:
        from tools.lead_tracker import log_search
        log_search(query, source, count)
    except Exception:
        pass


# ─── API Helpers ──────────────────────────────────────────────────────────────

def _get_api_key():
    """Get USPTO ODP API key from environment."""
    key = os.environ.get("USPTO_API_KEY") or os.environ.get("PATENTSVIEW_API_KEY")
    if not key:
        print("ERROR: USPTO_API_KEY not set in .env", file=sys.stderr)
        print("  Register at https://data.uspto.gov/myodp (requires ID.me)", file=sys.stderr)
        sys.exit(1)
    return key


def _api_request(url, params=None, body=None, method=None):
    """Make a rate-limited request to USPTO ODP. Returns parsed JSON."""
    global _last_request

    api_key = _get_api_key()

    if params and not body:
        url += "?" + urlencode(params, doseq=True)

    headers = {
        "X-API-KEY": api_key,
        "User-Agent": USER_AGENT,
        "accept": "application/json",
    }

    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
        if method is None:
            method = "POST"

    elapsed = time.time() - _last_request
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)

    req = Request(url, headers=headers, data=data, method=method or "GET")
    retries = 0
    while retries < 3:
        try:
            _last_request = time.time()
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code == 429:
                retries += 1
                wait = 2 ** retries
                print(f"  Rate limited (429), waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code == 404:
                return None
            body_text = e.read().decode()[:500]
            raise PatentSourceUnavailable(
                f"HTTP {e.code} from USPTO ODP: {body_text}"
            ) from e
        except URLError as e:
            raise PatentSourceUnavailable(
                f"cannot reach USPTO ODP: {e.reason}"
            ) from e
        except TimeoutError as e:
            raise PatentSourceUnavailable("USPTO ODP request timed out") from e

    raise PatentSourceUnavailable("USPTO ODP exhausted rate-limit retries")


# ─── ODP Search Helpers ───────────────────────────────────────────────────────

def _search_patents(q, limit=25, offset=0, filters=None, sort=None, fields=None):
    """Search patent applications via ODP POST endpoint.

    Args:
        q: Lucene-style query string (e.g., 'inventorNameText:Jobs')
        limit: max results per page
        offset: pagination offset
        filters: list of {"name": field, "value": [vals]} dicts
        sort: list of {"field": name, "order": "asc"|"desc"} dicts
        fields: list of field names to return
    """
    body = {
        "q": q,
        "pagination": {"offset": offset, "limit": limit},
    }
    if filters:
        body["filters"] = filters
    if sort:
        body["sort"] = sort
    if fields:
        body["fields"] = fields

    return _api_request(f"{ODP_PATENT_APPS}/search", body=body)


def _lucene_phrase(value):
    """Quote a user value as one Lucene phrase."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _normalized_person_name(value):
    """Normalize a person name while preserving exact token identity.

    USPTO sometimes stores names as ``Last, First``. Reordering that explicit
    form lets it match the CLI's ``First Last`` convention without turning a
    full-name lookup into token co-occurrence.
    """
    value = value.strip()
    if "," in value:
        last, remainder = value.split(",", 1)
        value = f"{remainder} {last}"
    return tuple(re.findall(r"[^\W_]+", value.casefold()))


def _exact_inventor_match(info, requested_name):
    """Return whether a patent has a name-scoped match for the request."""
    requested = _normalized_person_name(requested_name)
    if not requested:
        return False
    candidates = [
        _normalized_person_name(inventor.get("name", ""))
        for inventor in info.get("inventors", [])
    ]
    if len(requested) == 1:
        return any(requested[0] in candidate for candidate in candidates)
    return any(candidate == requested for candidate in candidates)


def _get_patent_detail(app_number):
    """Get full file wrapper for an application number."""
    return _api_request(f"{ODP_PATENT_APPS}/{app_number}")


def _get_patent_metadata(app_number):
    """Get metadata for an application number."""
    return _api_request(f"{ODP_PATENT_APPS}/{app_number}/meta-data")


def _get_patent_assignments(app_number):
    """Get assignment records for an application number."""
    return _api_request(f"{ODP_PATENT_APPS}/{app_number}/assignment")


def _get_patent_continuity(app_number):
    """Get continuity (parent/child relationships) for an application."""
    return _api_request(f"{ODP_PATENT_APPS}/{app_number}/continuity")


# ─── Patent Number Resolution ────────────────────────────────────────────────

def _normalize_patent_number(raw):
    """Normalize patent number to digits only.

    Handles: 11234567, 11,234,567, US11234567B2, US-11234567-B2, D123456, RE12345
    """
    s = raw.strip().upper().replace(",", "")

    # Strip US prefix and kind code
    s = re.sub(r'^US[-\s]*', '', s)
    s = re.sub(r'[-\s]*[A-Z]\d*$', '', s)

    # Design, reissue, plant patents: keep prefix
    m = re.match(r'^(D|RE|PP)(\d+)$', s)
    if m:
        prefix, num = m.groups()
        return f"{prefix}{num}"

    # Utility patents: just digits
    return re.sub(r'[^0-9]', '', s)


def _resolve_patent_to_app_number(patent_number):
    """Resolve a patent grant number to its application number via ODP search.

    Returns (app_number, metadata_dict) or (None, None) if not found.
    """
    sanitized = re.sub(r'[^0-9]', '', patent_number)

    resp = _search_patents(
        q=f"applicationMetaData.patentNumber:{sanitized}",
        limit=5,
        filters=[
            {"name": "applicationMetaData.applicationTypeLabelName", "value": ["Utility"]},
            {"name": "applicationMetaData.publicationCategoryBag", "value": ["Granted/Issued"]},
        ],
        sort=[{"field": "applicationMetaData.filingDate", "order": "desc"}],
        fields=["applicationNumberText", "applicationMetaData"],
    )

    if not resp:
        return None, None

    bag = resp.get("patentFileWrapperDataBag", [])
    if not bag:
        # Try without utility filter (design, plant patents)
        resp = _search_patents(
            q=f"applicationMetaData.patentNumber:{sanitized}",
            limit=5,
            filters=[
                {"name": "applicationMetaData.publicationCategoryBag", "value": ["Granted/Issued"]},
            ],
            fields=["applicationNumberText", "applicationMetaData"],
        )
        if not resp:
            return None, None
        bag = resp.get("patentFileWrapperDataBag", [])
        if not bag:
            return None, None

    entry = bag[0]
    app_num = entry.get("applicationNumberText")
    meta = entry.get("applicationMetaData", {})
    return app_num, meta


# ─── Database ─────────────────────────────────────────────────────────────────

def _init_db():
    """Initialize the patents cache database. Returns connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")

    db.executescript("""
        CREATE TABLE IF NOT EXISTS patents (
            patent_number TEXT PRIMARY KEY,
            app_number TEXT,
            patent_type TEXT,
            title TEXT,
            abstract TEXT,
            filing_date TEXT,
            grant_date TEXT,
            num_claims INTEGER,
            cpc_codes TEXT,
            status TEXT,
            raw_json TEXT,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inventors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patent_number TEXT,
            name TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            UNIQUE(patent_number, name)
        );

        CREATE TABLE IF NOT EXISTS assignees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patent_number TEXT,
            name TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            UNIQUE(patent_number, name)
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_number TEXT,
            patent_number TEXT,
            reel_number TEXT,
            frame_number TEXT,
            assignor_name TEXT,
            assignee_name TEXT,
            execution_date TEXT,
            recorded_date TEXT,
            conveyance_type TEXT,
            correspondent_name TEXT,
            raw_json TEXT,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(app_number, reel_number, frame_number, assignor_name)
        );

        CREATE TABLE IF NOT EXISTS citations (
            citing_patent TEXT NOT NULL,
            cited_patent TEXT NOT NULL,
            citation_category TEXT,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (citing_patent, cited_patent)
        );

        CREATE INDEX IF NOT EXISTS idx_patents_filing_date ON patents(filing_date);
        CREATE INDEX IF NOT EXISTS idx_patents_app_number ON patents(app_number);
        CREATE INDEX IF NOT EXISTS idx_inventors_name ON inventors(name);
        CREATE INDEX IF NOT EXISTS idx_inventors_patent ON inventors(patent_number);
        CREATE INDEX IF NOT EXISTS idx_assignees_name ON assignees(name);
        CREATE INDEX IF NOT EXISTS idx_assignees_patent ON assignees(patent_number);
        CREATE INDEX IF NOT EXISTS idx_assignments_patent ON assignments(patent_number);
        CREATE INDEX IF NOT EXISTS idx_assignments_app ON assignments(app_number);
        CREATE INDEX IF NOT EXISTS idx_assignments_assignor ON assignments(assignor_name);
        CREATE INDEX IF NOT EXISTS idx_assignments_assignee ON assignments(assignee_name);
    """)
    return db


def _is_cache_fresh(cached_at_str, max_age_days=None):
    """Check if a cached record is still fresh."""
    if not cached_at_str:
        return False
    max_age = max_age_days or CACHE_MAX_AGE_DAYS
    try:
        cached_at = datetime.fromisoformat(str(cached_at_str))
        return (datetime.now() - cached_at) < timedelta(days=max_age)
    except (ValueError, TypeError):
        return False


# ─── Response Parsing ─────────────────────────────────────────────────────────

def _extract_patent_info(entry):
    """Extract normalized patent info from an ODP patentFileWrapperDataBag entry.

    ODP nests most data inside applicationMetaData:
      - inventorBag, applicantBag, cpcClassificationBag are in meta
      - assignmentBag is at the top-level entry
      - patentNumber, grantDate, inventionTitle are in meta
    """
    meta = entry.get("applicationMetaData", {})
    app_num = entry.get("applicationNumberText", "")

    # Inventors — inside applicationMetaData
    inventors = []
    for inv in meta.get("inventorBag", []):
        name = inv.get("inventorNameText", "")
        if not name:
            first = inv.get("firstName", "")
            last = inv.get("lastName", "")
            name = f"{first} {last}".strip()
        # Address from first correspondenceAddressBag entry
        city = state = country = ""
        addrs = inv.get("correspondenceAddressBag", [])
        if addrs and isinstance(addrs[0], dict):
            addr = addrs[0]
            city = addr.get("cityName", "")
            state = addr.get("geographicRegionName", addr.get("geographicRegionCode", ""))
            country = addr.get("countryCode", "")
        if name:
            inventors.append({"name": name, "city": city, "state": state, "country": country})

    # Applicants/assignees — inside applicationMetaData
    assignees = []
    for asg in meta.get("applicantBag", []):
        name = asg.get("applicantNameText", asg.get("nameText", ""))
        city = state = country = ""
        addrs = asg.get("correspondenceAddressBag", [])
        if addrs and isinstance(addrs[0], dict):
            addr = addrs[0]
            city = addr.get("cityName", "")
            state = addr.get("geographicRegionName", "")
            country = addr.get("countryCode", "")
        if name:
            assignees.append({"name": name, "city": city, "state": state, "country": country})

    # CPC codes — inside applicationMetaData as plain strings
    cpc_codes = []
    for code in meta.get("cpcClassificationBag", []):
        if isinstance(code, str):
            cpc_codes.append(code.strip())
        elif isinstance(code, dict):
            c = code.get("cpcClassificationText", code.get("classificationText", ""))
            if c:
                cpc_codes.append(c.strip())

    patent_number = str(meta.get("patentNumber", ""))
    title = meta.get("inventionTitle", meta.get("inventionTitleText", ""))
    abstract = entry.get("abstractText", meta.get("abstractText", ""))

    return {
        "patent_number": patent_number,
        "app_number": app_num,
        "title": title,
        "abstract": abstract,
        "type": meta.get("applicationTypeLabelName", ""),
        "filing_date": meta.get("filingDate", ""),
        "grant_date": str(meta.get("grantDate", meta.get("patentGrantDate", ""))),
        "status": meta.get("applicationStatusDescriptionText", ""),
        "num_claims": meta.get("claimNumber", None),
        "cpc_codes": cpc_codes,
        "inventors": inventors,
        "assignees": assignees,
    }


def _cache_patent_info(db, info):
    """Cache extracted patent info to local DB."""
    pn = info.get("patent_number", "")
    if not pn:
        return

    db.execute("""
        INSERT OR REPLACE INTO patents
        (patent_number, app_number, patent_type, title, abstract, filing_date,
         grant_date, num_claims, cpc_codes, status, raw_json, cached_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        pn, info.get("app_number"), info.get("type"), info.get("title"),
        info.get("abstract"), info.get("filing_date"), info.get("grant_date"),
        info.get("num_claims"), json.dumps(info.get("cpc_codes", [])),
        info.get("status"), json.dumps(info, default=str),
    ))

    for inv in info.get("inventors", []):
        if inv.get("name"):
            db.execute("""
                INSERT OR IGNORE INTO inventors (patent_number, name, city, state, country)
                VALUES (?, ?, ?, ?, ?)
            """, (pn, inv["name"], inv.get("city"), inv.get("state"), inv.get("country")))

    for asg in info.get("assignees", []):
        if asg.get("name"):
            db.execute("""
                INSERT OR IGNORE INTO assignees (patent_number, name, city, state, country)
                VALUES (?, ?, ?, ?, ?)
            """, (pn, asg["name"], asg.get("city"), asg.get("state"), asg.get("country")))

    db.commit()


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_search(args):
    """Full-text patent search via ODP."""
    q_parts = [args.query]
    if getattr(args, "type", None):
        q_parts.append(f"AND applicationMetaData.applicationTypeLabelName:{args.type}")

    q = " ".join(q_parts)

    filters = []
    range_filters = []
    if getattr(args, "start", None) or getattr(args, "end", None):
        start = getattr(args, "start", None) or "2001-01-01"
        end = getattr(args, "end", None) or "2099-12-31"
        range_filters.append({
            "name": "applicationMetaData.filingDate",
            "from": start,
            "to": end,
        })

    body = {
        "q": q,
        "pagination": {"offset": 0, "limit": args.limit},
        "sort": [{"field": "applicationMetaData.filingDate", "order": "desc"}],
    }
    if filters:
        body["filters"] = filters
    if range_filters:
        body["rangeFilters"] = range_filters

    resp = _api_request(f"{ODP_PATENT_APPS}/search", body=body)
    if not resp:
        print("  No results or API error.", file=sys.stderr)
        return

    bag = resp.get("patentFileWrapperDataBag", [])
    total = resp.get("count", len(bag))

    db = _init_db()
    results = []
    for entry in bag:
        info = _extract_patent_info(entry)
        _cache_patent_info(db, info)
        results.append(info)
    db.close()

    _log(args.query, "patents", total)

    result = {
        "query": args.query,
        "total": total,
        "returned": len(results),
        "patents": [{
            "patent_number": p["patent_number"],
            "app_number": p["app_number"],
            "title": p["title"],
            "date": p["filing_date"],
            "type": p["type"],
            "status": p["status"],
            "assignees": [a["name"] for a in p.get("assignees", [])],
            "inventors": [i["name"] for i in p.get("inventors", [])],
        } for p in results],
    }

    summary = f"patent search '{args.query}': {total} total, {len(results)} returned"
    if write_output(result, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2, default=str))
        return

    _print_search(result)


def _print_search(result):
    """Pretty-print search results."""
    print(f"\n  Patent Search: \"{result['query']}\"")
    print(f"  {result['total']} total results, showing {result['returned']}")
    print("  " + "-" * 68)

    for i, p in enumerate(result["patents"], 1):
        title = (p.get("title") or "")[:75]
        assignees = ", ".join(p.get("assignees", [])[:2]) or "N/A"
        inventors = ", ".join(p.get("inventors", [])[:2]) or "N/A"
        pn = p.get("patent_number") or p.get("app_number", "N/A")
        print(f"  {i:3}. {pn}  ({p.get('date', 'N/A')})")
        print(f"       {title}")
        print(f"       Assignee: {assignees}")
        print(f"       Inventor: {inventors}")
        print()


def cmd_inventor(args):
    """Find patents by inventor name."""
    q = f"inventorNameText:{_lucene_phrase(args.name)}"

    resp = _search_patents(q, limit=args.limit,
                           sort=[{"field": "applicationMetaData.filingDate", "order": "desc"}])
    if not resp:
        print(f"  No results for inventor: {args.name}", file=sys.stderr)
        return

    bag = resp.get("patentFileWrapperDataBag", [])
    api_total = resp.get("count", len(bag))

    db = _init_db()
    results = []
    for entry in bag:
        info = _extract_patent_info(entry)
        if not _exact_inventor_match(info, args.name):
            continue
        _cache_patent_info(db, info)
        results.append(info)
    db.close()

    matched = len(results)
    _log(f"inventor:{args.name}", "patents", matched)

    result = {
        "query": args.name,
        "query_type": "inventor",
        "match_semantics": (
            "exact_normalized_inventor_name"
            if len(_normalized_person_name(args.name)) > 1
            else "exact_inventor_name_token"
        ),
        "total": matched,
        "returned": matched,
        "api_candidate_total": api_total,
        "api_candidates_screened": len(bag),
        "patents": [{
            "patent_number": p["patent_number"],
            "app_number": p["app_number"],
            "title": p["title"],
            "date": p["filing_date"],
            "type": p["type"],
            "assignees": [a["name"] for a in p.get("assignees", [])],
            "inventors": [i["name"] for i in p.get("inventors", [])],
        } for p in results],
    }

    summary = (
        f"inventor '{args.name}': {matched} name-scoped matches "
        f"from {len(bag)} screened candidates"
    )
    if write_output(result, args, summary=summary, result_count=matched):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2, default=str))
        return

    print(f"\n  Patents by Inventor: \"{args.name}\"")
    print(
        f"  {matched} name-scoped matches; screened {len(bag)} "
        f"of {api_total} API candidates"
    )
    print("  " + "-" * 68)
    for i, p in enumerate(result["patents"], 1):
        title = (p.get("title") or "")[:75]
        assignees = ", ".join(p.get("assignees", [])[:2]) or "N/A"
        print(f"  {i:3}. {p.get('patent_number') or p.get('app_number', 'N/A')}  ({p.get('date', 'N/A')})")
        print(f"       {title}")
        print(f"       Assignee: {assignees}")
        print()


def cmd_assignee(args):
    """Find patents by assignee/company name.

    ODP doesn't have a dedicated assignee field — we search by the company name
    in the general query and filter for granted patents.
    """
    q = f"\"{args.name}\""

    resp = _search_patents(
        q, limit=args.limit,
        filters=[
            {"name": "applicationMetaData.publicationCategoryBag", "value": ["Granted/Issued"]},
        ],
        sort=[{"field": "applicationMetaData.filingDate", "order": "desc"}],
    )
    if not resp:
        print(f"  No results for assignee: {args.name}", file=sys.stderr)
        return

    bag = resp.get("patentFileWrapperDataBag", [])
    total = resp.get("count", len(bag))

    db = _init_db()
    results = []
    unique_inventors = set()
    by_year = {}

    for entry in bag:
        info = _extract_patent_info(entry)
        _cache_patent_info(db, info)
        results.append(info)
        year = (info.get("filing_date") or "")[:4] or "Unknown"
        by_year[year] = by_year.get(year, 0) + 1
        for inv in info.get("inventors", []):
            if inv.get("name"):
                unique_inventors.add(inv["name"])
    db.close()

    _log(f"assignee:{args.name}", "patents", total)

    result = {
        "query": args.name,
        "query_type": "assignee",
        "total": total,
        "returned": len(results),
        "unique_inventors": len(unique_inventors),
        "by_year": dict(sorted(by_year.items())),
        "patents": [{
            "patent_number": p["patent_number"],
            "app_number": p["app_number"],
            "title": p["title"],
            "date": p["filing_date"],
            "type": p["type"],
            "inventors": [i["name"] for i in p.get("inventors", [])],
            "cpc_codes": p.get("cpc_codes", []),
        } for p in results],
    }

    summary = f"assignee '{args.name}': {total} patents, {len(unique_inventors)} inventors"
    if write_output(result, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2, default=str))
        return

    print(f"\n  Patents Assigned to: \"{args.name}\"")
    print(f"  {total} total, {len(unique_inventors)} unique inventors")
    if by_year:
        years = sorted(by_year.keys())
        print(f"  Filing range: {years[0]} - {years[-1]}")
    print("  " + "-" * 68)
    for i, p in enumerate(result["patents"], 1):
        title = (p.get("title") or "")[:75]
        inventors = ", ".join(p.get("inventors", [])[:2]) or "N/A"
        pn = p.get("patent_number") or p.get("app_number", "N/A")
        print(f"  {i:3}. {pn}  ({p.get('date', 'N/A')})")
        print(f"       {title}")
        print(f"       Inventors: {inventors}")
        print()


def cmd_patent(args):
    """Get detail for a specific patent number."""
    pn = _normalize_patent_number(args.number)

    # Check cache
    if not getattr(args, "force_refresh", False):
        db = _init_db()
        row = db.execute("SELECT * FROM patents WHERE patent_number = ?", (pn,)).fetchone()
        if row and _is_cache_fresh(row["cached_at"]):
            result = {
                "patent_number": row["patent_number"],
                "app_number": row["app_number"],
                "title": row["title"],
                "abstract": row["abstract"],
                "type": row["patent_type"],
                "filing_date": row["filing_date"],
                "grant_date": row["grant_date"],
                "status": row["status"],
                "num_claims": row["num_claims"],
                "cpc_codes": json.loads(row["cpc_codes"]) if row["cpc_codes"] else [],
                "inventors": [
                    {"name": r["name"], "city": r["city"], "state": r["state"], "country": r["country"]}
                    for r in db.execute("SELECT * FROM inventors WHERE patent_number=?", (pn,))
                ],
                "assignees": [
                    {"name": r["name"], "city": r["city"], "state": r["state"], "country": r["country"]}
                    for r in db.execute("SELECT * FROM assignees WHERE patent_number=?", (pn,))
                ],
            }
            summary = f"patent {pn} (cached)"
            if write_output(result, args, summary=summary):
                db.close()
                return
            if getattr(args, "json_out", False):
                print(json.dumps(result, indent=2, default=str))
                db.close()
                return
            _print_patent_detail(result)
            db.close()
            return
        db.close()

    # Resolve patent number to application number
    app_num, meta = _resolve_patent_to_app_number(pn)
    if not app_num:
        print(f"  No patent found for number: {pn}", file=sys.stderr)
        sys.exit(1)

    # Get full detail — _get_patent_detail returns {"patentFileWrapperDataBag": [...]}
    detail = _get_patent_detail(app_num)
    detail_bag = (detail or {}).get("patentFileWrapperDataBag", [])

    if detail_bag:
        info = _extract_patent_info(detail_bag[0])
        if not info["patent_number"]:
            info["patent_number"] = pn
        db = _init_db()
        _cache_patent_info(db, info)
        db.close()
        result = info
    else:
        # Fall back to metadata from the search/resolution step
        result = _extract_patent_info({"applicationMetaData": meta, "applicationNumberText": app_num})
        if not result["patent_number"]:
            result["patent_number"] = pn

    summary = f"patent {pn}: {result.get('title', '')[:60]}"
    if write_output(result, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2, default=str))
        return

    _print_patent_detail(result)


def _print_patent_detail(result):
    """Pretty-print a single patent's details."""
    pn = result.get("patent_number") or result.get("app_number", "N/A")
    print(f"\n  Patent: {pn}")
    print("  " + "=" * 68)
    print(f"  Title:       {result.get('title', 'N/A')}")
    print(f"  Type:        {result.get('type', 'N/A')}")
    print(f"  Filed:       {result.get('filing_date', 'N/A')}")
    print(f"  Granted:     {result.get('grant_date', 'N/A')}")
    print(f"  Status:      {result.get('status', 'N/A')}")
    if result.get("app_number"):
        print(f"  App Number:  {result['app_number']}")
    if result.get("num_claims"):
        print(f"  Claims:      {result['num_claims']}")
    if result.get("cpc_codes"):
        print(f"  CPC Codes:   {', '.join(result['cpc_codes'][:10])}")

    if result.get("assignees"):
        print("\n  Assignees:")
        for a in result["assignees"]:
            loc = ", ".join(filter(None, [a.get("city"), a.get("state"), a.get("country")])) or ""
            print(f"    - {a['name']}" + (f"  ({loc})" if loc else ""))

    if result.get("inventors"):
        print("\n  Inventors:")
        for inv in result["inventors"]:
            loc = ", ".join(filter(None, [inv.get("city"), inv.get("state"), inv.get("country")])) or ""
            print(f"    - {inv['name']}" + (f"  ({loc})" if loc else ""))

    if result.get("abstract"):
        abstract = result["abstract"][:500]
        print("\n  Abstract:")
        words = abstract.split()
        line = "    "
        for w in words:
            if len(line) + len(w) + 1 > 78:
                print(line)
                line = "    " + w
            else:
                line += " " + w if line.strip() else "    " + w
        if line.strip():
            print(line)
    print()


# ─── Assignment / Ownership Tracing ──────────────────────────────────────────

def cmd_assignments(args):
    """Trace ownership chain for a patent via ODP Assignment endpoint."""
    pn = _normalize_patent_number(args.number)

    # Check cache
    db = _init_db()
    if not getattr(args, "force_refresh", False):
        cached = db.execute(
            "SELECT * FROM assignments WHERE patent_number = ? ORDER BY recorded_date",
            (pn,)
        ).fetchall()
        if cached and all(_is_cache_fresh(r["cached_at"]) for r in cached):
            result = _format_assignments(pn, cached, args)
            summary = f"assignments for {pn}: {len(cached)} transfers (cached)"
            if write_output(result, args, summary=summary):
                db.close()
                return
            if getattr(args, "json_out", False):
                print(json.dumps(result, indent=2, default=str))
                db.close()
                return
            _print_assignments(result)
            db.close()
            return

    # Resolve to app number
    app_num, _ = _resolve_patent_to_app_number(pn)
    if not app_num:
        print(f"  Cannot resolve patent {pn} to application number.", file=sys.stderr)
        db.close()
        return

    # Fetch assignments
    resp = _get_patent_assignments(app_num)
    if not resp:
        print(f"  No assignment records found for patent: {pn} (app: {app_num})", file=sys.stderr)
        db.close()
        return

    # Unwrap: /assignment endpoint returns {patentFileWrapperDataBag: [{assignmentBag: [...]}]}
    wrapper_bag = resp.get("patentFileWrapperDataBag", [])
    if wrapper_bag and isinstance(wrapper_bag[0], dict):
        assignment_data = wrapper_bag[0]
    else:
        assignment_data = resp
    records = _parse_and_store_assignments(db, pn, app_num, assignment_data)

    db.commit()
    _log(f"assignments:{pn}", "patents", len(records))

    result = _format_assignments(pn, records, args)
    summary = f"assignments for {pn}: {len(records)} transfers"
    if write_output(result, args, summary=summary):
        db.close()
        return
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2, default=str))
        db.close()
        return
    _print_assignments(result)
    db.close()


def _format_assignments(patent_number, records, args=None):
    """Format assignment records into a result dict."""
    since = getattr(args, "since", None) if args else None

    transfers = []
    for r in records:
        if isinstance(r, sqlite3.Row):
            r = dict(r)
        exec_date = r.get("execution_date", "")
        if since and exec_date and exec_date < since:
            continue
        reel = r.get("reel_number", "")
        frame = r.get("frame_number", "")
        reel_frame = f"{reel}/{frame}" if reel and frame else ""
        transfers.append({
            "assignor": r.get("assignor_name", ""),
            "assignee": r.get("assignee_name", ""),
            "execution_date": exec_date,
            "recorded_date": r.get("recorded_date", ""),
            "conveyance_type": r.get("conveyance_type", ""),
            "reel_frame": reel_frame,
            "correspondent": r.get("correspondent_name", ""),
        })

    transfers.sort(key=lambda t: t.get("execution_date", "") or "9999")

    security_interests = [
        t for t in transfers
        if "SECURITY" in (t.get("conveyance_type") or "").upper()
    ]

    return {
        "patent_number": patent_number,
        "total_transfers": len(transfers),
        "security_interests": len(security_interests),
        "transfers": transfers,
    }


def _print_assignments(result):
    """Pretty-print ownership chain."""
    pn = result["patent_number"]
    transfers = result["transfers"]

    print(f"\n  OWNERSHIP CHAIN for {pn}")
    print("  " + "-" * 68)

    if not transfers:
        print("  No assignment records found.")
        print()
        return

    for t in transfers:
        date = t.get("execution_date", "N/A")
        assignor = t.get("assignor", "Unknown")
        assignee = t.get("assignee", "Unknown")
        conv = t.get("conveyance_type", "")
        reel = t.get("reel_frame", "")

        flag = ""
        if "SECURITY" in (conv or "").upper():
            flag = "  ** SECURITY INTEREST **"

        print(f"  {date}  {assignor} -> {assignee}{flag}")
        if conv:
            print(f"            Type: {conv[:80]}")
        if reel:
            print(f"            Reel/Frame: {reel}")
        print()

    print(f"  Summary: {result['total_transfers']} transfers")
    if result["security_interests"]:
        print(f"  !! {result['security_interests']} SECURITY INTEREST(s) detected (patent used as collateral)")
    print()


# ─── Portfolio ────────────────────────────────────────────────────────────────

def cmd_portfolio(args):
    """Full patent portfolio for a company."""
    all_patents = []
    offset = 0
    per_page = min(25, args.limit)

    while len(all_patents) < args.limit:
        resp = _search_patents(
            q=f"\"{args.name}\"",
            limit=per_page, offset=offset,
            filters=[
                {"name": "applicationMetaData.publicationCategoryBag", "value": ["Granted/Issued"]},
            ],
            sort=[{"field": "applicationMetaData.filingDate", "order": "desc"}],
        )
        if not resp:
            break

        bag = resp.get("patentFileWrapperDataBag", [])
        total = resp.get("count", 0)
        if not bag:
            break

        for entry in bag:
            all_patents.append(_extract_patent_info(entry))

        if len(all_patents) >= total or len(all_patents) >= args.limit:
            break
        offset += per_page

    # Cache
    db = _init_db()
    for info in all_patents:
        _cache_patent_info(db, info)

    _log(f"portfolio:{args.name}", "patents", len(all_patents))

    # Build summary
    by_year = {}
    unique_inventors = set()
    cpc_counts = {}

    for p in all_patents:
        year = (p.get("filing_date") or "")[:4] or "Unknown"
        by_year[year] = by_year.get(year, 0) + 1
        for inv in p.get("inventors", []):
            if inv.get("name"):
                unique_inventors.add(inv["name"])
        for code in p.get("cpc_codes", []):
            if code:
                cpc_counts[code] = cpc_counts.get(code, 0) + 1

    # Optionally trace assignments
    assignment_summary = None
    patent_numbers_with_apps = [
        (p["patent_number"], p["app_number"])
        for p in all_patents
        if p.get("app_number")
    ]

    if not getattr(args, "skip_assignments", False) and len(patent_numbers_with_apps) <= 50:
        acquired = divested = security = 0
        print(f"  Tracing assignments for {len(patent_numbers_with_apps)} patents...", file=sys.stderr)
        for i, (pn, app_num) in enumerate(patent_numbers_with_apps):
            if i % 10 == 0 and i > 0:
                print(f"    ...{i}/{len(patent_numbers_with_apps)}", file=sys.stderr)

            cached = db.execute(
                "SELECT * FROM assignments WHERE app_number = ?", (app_num,)
            ).fetchall()
            if not cached or not all(_is_cache_fresh(r["cached_at"]) for r in cached):
                resp = _get_patent_assignments(app_num)
                if resp:
                    wb = resp.get("patentFileWrapperDataBag", [])
                    ad = wb[0] if wb and isinstance(wb[0], dict) else resp
                    _parse_and_store_assignments(db, pn, app_num, ad)
                    cached = db.execute(
                        "SELECT * FROM assignments WHERE app_number = ?", (app_num,)
                    ).fetchall()

            for r in cached:
                conv = (r["conveyance_type"] or "").upper()
                if "SECURITY" in conv:
                    security += 1
                elif args.name.upper() in (r["assignee_name"] or "").upper():
                    acquired += 1
                elif args.name.upper() in (r["assignor_name"] or "").upper():
                    divested += 1

        assignment_summary = {
            "acquired_via_transfer": acquired,
            "divested": divested,
            "security_interests": security,
        }

    db.close()

    top_cpc = sorted(cpc_counts.items(), key=lambda x: -x[1])[:10]

    result = {
        "company": args.name,
        "total_patents": len(all_patents),
        "unique_inventors": len(unique_inventors),
        "by_year": dict(sorted(by_year.items())),
        "top_cpc_codes": [{"code": c, "count": n} for c, n in top_cpc],
        "assignment_summary": assignment_summary,
        "patents": [{
            "patent_number": p.get("patent_number"),
            "app_number": p.get("app_number"),
            "title": p.get("title"),
            "date": p.get("filing_date"),
        } for p in all_patents],
    }

    summary = f"portfolio '{args.name}': {len(all_patents)} patents, {len(unique_inventors)} inventors"
    if write_output(result, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2, default=str))
        return

    _print_portfolio(result)


def _parse_and_store_assignments(db, patent_number, app_number, resp):
    """Parse assignment records from ODP response, store in DB, return list of dicts.

    ODP assignment record structure (confirmed from live API):
      record.reelNumber (int), record.frameNumber (int)
      record.conveyanceText, record.assignmentRecordedDate
      record.assignorBag[].assignorName, record.assignorBag[].executionDate
      record.assigneeBag[].assigneeNameText, record.assigneeBag[].assigneeAddress
      record.correspondenceAddress (object, not a name string)
    """
    assignment_bag = resp.get("assignmentBag", resp.get("patentAssignmentBag", []))
    if isinstance(assignment_bag, dict):
        assignment_bag = [assignment_bag]

    records = []
    for record in assignment_bag:
        if not isinstance(record, dict):
            continue
        reel = str(record.get("reelNumber", ""))
        frame = str(record.get("frameNumber", ""))
        conveyance = record.get("conveyanceText", "")
        rec_date = str(record.get("assignmentRecordedDate",
                                  record.get("recordedDate", "")))

        # Correspondent from correspondenceAddress object
        corr_addr = record.get("correspondenceAddress", {})
        correspondent = ""
        if isinstance(corr_addr, dict):
            correspondent = corr_addr.get("nameLineOneText",
                           corr_addr.get("correspondentName", ""))

        assignor_bag = record.get("assignorBag", [])
        assignee_bag = record.get("assigneeBag", [])
        if isinstance(assignor_bag, dict):
            assignor_bag = [assignor_bag]
        if isinstance(assignee_bag, dict):
            assignee_bag = [assignee_bag]

        for assignor in assignor_bag:
            if isinstance(assignor, str):
                assignor_name = assignor
                exec_date = ""
            else:
                assignor_name = assignor.get("assignorName", assignor.get("name", "Unknown"))
                exec_date = str(assignor.get("executionDate", ""))

            for assignee in assignee_bag:
                if isinstance(assignee, str):
                    assignee_name = assignee
                else:
                    assignee_name = (assignee.get("assigneeNameText", "") or
                                     assignee.get("assigneeName", "") or
                                     assignee.get("name", "Unknown"))

                rec = {
                    "reel_number": reel,
                    "frame_number": frame,
                    "patent_number": patent_number,
                    "app_number": app_number,
                    "assignor_name": assignor_name,
                    "assignee_name": assignee_name,
                    "execution_date": exec_date,
                    "recorded_date": rec_date,
                    "conveyance_type": conveyance,
                    "correspondent_name": correspondent,
                }
                records.append(rec)

                db.execute("""
                    INSERT OR REPLACE INTO assignments
                    (app_number, patent_number, reel_number, frame_number,
                     assignor_name, assignee_name, execution_date, recorded_date,
                     conveyance_type, correspondent_name, raw_json, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    app_number, patent_number, reel, frame,
                    assignor_name, assignee_name, exec_date, rec_date,
                    conveyance, correspondent,
                    json.dumps(record, default=str),
                ))
    db.commit()
    return records


def _print_portfolio(result):
    """Pretty-print portfolio summary."""
    print(f"\n  Patent Portfolio: \"{result['company']}\"")
    print("  " + "=" * 68)
    print(f"  Total patents:     {result['total_patents']}")
    print(f"  Unique inventors:  {result['unique_inventors']}")

    if result.get("by_year"):
        years = sorted(result["by_year"].keys())
        print(f"  Date range:        {years[0]} - {years[-1]}")
        print("\n  Patents by year:")
        for y in years:
            count = result["by_year"][y]
            bar = "#" * min(count, 40)
            print(f"    {y}: {bar} {count}")

    if result.get("top_cpc_codes"):
        print("\n  Top technology areas (CPC):")
        for entry in result["top_cpc_codes"][:8]:
            print(f"    {entry['code']}: {entry['count']} patents")

    if result.get("assignment_summary"):
        a = result["assignment_summary"]
        print("\n  Ownership activity:")
        print(f"    Acquired via transfer: {a['acquired_via_transfer']}")
        print(f"    Divested:              {a['divested']}")
        if a["security_interests"]:
            print(f"    !! Security interests:  {a['security_interests']} (used as collateral)")

    print("\n  Recent patents:")
    sorted_patents = sorted(result.get("patents", []),
                            key=lambda p: p.get("date") or "", reverse=True)
    for p in sorted_patents[:10]:
        title = (p.get("title") or "")[:65]
        pn = p.get("patent_number") or p.get("app_number", "N/A")
        print(f"    {pn}  ({p.get('date', 'N/A')})  {title}")
    print()


# ─── Citations ────────────────────────────────────────────────────────────────

def cmd_citations(args):
    """Citation network for a patent.

    ODP doesn't expose citation data directly in the same way PatentsView did.
    We fetch the continuity data (parent/child relationships) and any citation
    info available in the file wrapper.
    """
    pn = _normalize_patent_number(args.number)

    # Resolve to app number
    app_num, _ = _resolve_patent_to_app_number(pn)
    if not app_num:
        print(f"  Cannot resolve patent {pn} to application number.", file=sys.stderr)
        sys.exit(1)

    # Get continuity (parent/child patent relationships)
    continuity = _get_patent_continuity(app_num)

    parents = []
    children = []
    if continuity:
        for p in continuity.get("parentBag", continuity.get("parentContinuityBag", [])):
            if isinstance(p, dict):
                parents.append({
                    "app_number": p.get("applicationNumberText", p.get("parentApplicationNumberText", "")),
                    "patent_number": p.get("patentNumber", ""),
                    "filing_date": p.get("filingDate", ""),
                    "relationship": p.get("continuityType", p.get("claimText", "")),
                })
        for c in continuity.get("childBag", continuity.get("childContinuityBag", [])):
            if isinstance(c, dict):
                children.append({
                    "app_number": c.get("applicationNumberText", c.get("childApplicationNumberText", "")),
                    "patent_number": c.get("patentNumber", ""),
                    "filing_date": c.get("filingDate", ""),
                    "relationship": c.get("continuityType", c.get("claimText", "")),
                })

    _log(f"citations:{pn}", "patents", len(parents) + len(children))

    result = {
        "patent_number": pn,
        "app_number": app_num,
        "parent_applications": len(parents),
        "child_applications": len(children),
        "parents": parents,
        "children": children,
        "note": "ODP provides continuity (parent/child) data. For prior-art citations, use bulk PatentsView data.",
    }

    summary = f"continuity for {pn}: {len(parents)} parents, {len(children)} children"
    if write_output(result, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2, default=str))
        return

    print(f"\n  Patent Continuity for {pn} (app: {app_num})")
    print("  " + "-" * 68)

    if parents:
        print(f"\n  Parent Applications ({len(parents)}):")
        for p in parents:
            pn_str = p.get("patent_number") or p.get("app_number", "N/A")
            rel = p.get("relationship", "")
            print(f"    {pn_str}  ({p.get('filing_date', 'N/A')})  {rel}")

    if children:
        print(f"\n  Child Applications ({len(children)}):")
        for c in children:
            pn_str = c.get("patent_number") or c.get("app_number", "N/A")
            rel = c.get("relationship", "")
            print(f"    {pn_str}  ({c.get('filing_date', 'N/A')})  {rel}")

    if not parents and not children:
        print("  No continuity records found.")

    print()


# ─── Enrich ───────────────────────────────────────────────────────────────────

def cmd_enrich(args):
    """Match investigation entities against patent data."""
    dry_run = getattr(args, "dry_run", False)
    threshold = getattr(args, "threshold", 85)

    if not INVESTIGATION_DB.exists():
        print("ERROR: investigation.db not found", file=sys.stderr)
        sys.exit(1)

    inv_db = sqlite3.connect(str(INVESTIGATION_DB))
    inv_db.row_factory = sqlite3.Row

    entities = inv_db.execute(
        "SELECT id, name, entity_type, jurisdiction, status, notes, address FROM entities ORDER BY name"
    ).fetchall()

    if not entities:
        print("  No entities in investigation.db")
        inv_db.close()
        return

    try:
        from rapidfuzz import fuzz
    except ImportError:
        print("WARNING: rapidfuzz not installed, using basic matching", file=sys.stderr)
        fuzz = None

    try:
        from tools.entity_resolution import normalize_entity_name
    except ImportError:
        try:
            from entity_resolution import normalize_entity_name
        except ImportError:
            def normalize_entity_name(n):
                return re.sub(r'\b(inc|llc|ltd|corp|co|lp|plc)\b\.?', '', n.lower()).strip()

    results = {
        "total_entities": len(entities),
        "matched": 0,
        "matches": [],
        "no_match": [],
        "errors": 0,
        "threshold": threshold,
    }

    patents_db = _init_db()

    for ent in entities:
        ent_id = ent["id"]
        ent_name = ent["name"]
        ent_type = ent["entity_type"] or ""
        norm = normalize_entity_name(ent_name)

        if not norm or len(norm) < 3:
            continue

        try:
            if ent_type.lower() in ("person", "individual"):
                q = f"inventorNameText:{ent_name}"
                search_type = "inventor"
            else:
                q = f"\"{ent_name}\""
                search_type = "assignee"

            print(f"  Searching {search_type}: {ent_name}...", file=sys.stderr)

            resp = _search_patents(q, limit=10)
            if not resp:
                results["no_match"].append(ent_name)
                continue

            bag = resp.get("patentFileWrapperDataBag", [])
            total = resp.get("count", 0)

            if not bag:
                results["no_match"].append(ent_name)
                continue

            # Parse and cache
            patent_infos = []
            for entry in bag:
                info = _extract_patent_info(entry)
                _cache_patent_info(patents_db, info)
                patent_infos.append(info)

            # Fuzzy match check
            best_score = 0
            if search_type == "assignee":
                for info in patent_infos:
                    for a in info.get("assignees", []):
                        match_name = a.get("name", "")
                        if not match_name:
                            continue
                        if fuzz:
                            score = fuzz.token_sort_ratio(norm, normalize_entity_name(match_name))
                        else:
                            score = 100 if norm in normalize_entity_name(match_name) else 50
                        best_score = max(best_score, score)
            else:
                for info in patent_infos:
                    for inv in info.get("inventors", []):
                        inv_name = inv.get("name", "")
                        if fuzz:
                            score = fuzz.token_sort_ratio(ent_name.lower(), inv_name.lower())
                        else:
                            score = 100 if ent_name.lower() in inv_name.lower() else 50
                        best_score = max(best_score, score)

            if best_score < threshold:
                results["no_match"].append(ent_name)
                continue

            dates = [p.get("filing_date", "") for p in patent_infos if p.get("filing_date")]
            cpc_set = set()
            for p in patent_infos:
                for code in p.get("cpc_codes", []):
                    if code:
                        cpc_set.add(code)

            confidence = "high" if best_score >= 95 else "review"

            match_info = {
                "entity_id": ent_id,
                "entity_name": ent_name,
                "entity_type": ent_type,
                "match_type": search_type,
                "match_score": best_score,
                "patent_count": total,
                "date_range": f"{min(dates)[:4]}-{max(dates)[:4]}" if dates else "N/A",
                "top_cpc": sorted(cpc_set)[:5],
                "confidence": confidence,
            }
            results["matches"].append(match_info)
            results["matched"] += 1

            if not dry_run and confidence == "high":
                patent_note = f"[Patents] {total} patents ({match_info['date_range']})"
                if cpc_set:
                    patent_note += f" CPC: {', '.join(sorted(cpc_set)[:3])}"
                existing_notes = ent["notes"] or ""
                if "[Patents]" not in existing_notes:
                    new_notes = (existing_notes + "\n" + patent_note).strip()
                    inv_db.execute("UPDATE entities SET notes=? WHERE id=?", (new_notes, ent_id))

        except Exception as e:
            print(f"  ERROR for {ent_name}: {e}", file=sys.stderr)
            results["errors"] += 1

    if not dry_run:
        inv_db.commit()
    inv_db.close()
    patents_db.close()

    summary = f"patent enrich: {results['matched']}/{results['total_entities']} matched"
    if write_output(results, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(results, indent=2, default=str))
        return

    _print_enrich(results)


def _print_enrich(data):
    """Pretty-print enrichment results."""
    high = [m for m in data["matches"] if m.get("confidence") == "high"]
    review = [m for m in data["matches"] if m.get("confidence") != "high"]

    print(f"\n  Patent Entity Enrichment (threshold={data.get('threshold', 85)})")
    print("  " + "=" * 68)
    print(f"  Entities searched:  {data['total_entities']}")
    print(f"  Matched:            {data['matched']}")
    print(f"  No match:           {len(data['no_match'])}")
    print(f"  Errors:             {data['errors']}")

    if high:
        print(f"\n  === High Confidence Matches ({len(high)}) ===")
        for m in high:
            print(f"    {m['entity_name']} ({m['entity_type']})")
            print(f"      {m['patent_count']} patents, {m['date_range']}, "
                  f"score={m['match_score']}, type={m['match_type']}")
            if m.get("top_cpc"):
                print(f"      CPC: {', '.join(m['top_cpc'])}")
            print()

    if review:
        print(f"\n  === Needs Review ({len(review)}) ===")
        for m in review:
            print(f"    {m['entity_name']} - score={m['match_score']}, "
                  f"{m['patent_count']} patents")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="USPTO patent search and ownership tracing for OSINT investigation"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p = sub.add_parser("search", help="Full-text patent search")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", type=int, default=25, help="Max results (default 25)")
    p.add_argument("--start", help="Filing date start (YYYY-MM-DD)")
    p.add_argument("--end", help="Filing date end (YYYY-MM-DD)")
    p.add_argument("--type", choices=["Utility", "Design", "Plant", "Reissue"],
                   help="Patent type filter")
    p.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    add_output_args(p)

    # inventor
    p = sub.add_parser("inventor", help="Find patents by inventor name")
    p.add_argument("name", help="Inventor name (e.g., 'Tim Draper')")
    p.add_argument("--limit", type=int, default=50, help="Max results (default 50)")
    p.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    add_output_args(p)

    # assignee
    p = sub.add_parser("assignee", help="Find patents by assignee/company")
    p.add_argument("name", help="Company or assignee name")
    p.add_argument("--limit", type=int, default=50, help="Max results (default 50)")
    p.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    add_output_args(p)

    # patent
    p = sub.add_parser("patent", help="Get detail for a specific patent")
    p.add_argument("number", help="Patent number (e.g., 11234567, US-11234567-B2)")
    p.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    add_output_args(p)

    # assignments
    p = sub.add_parser("assignments", help="Trace ownership chain for a patent")
    p.add_argument("number", help="Patent number")
    p.add_argument("--since", help="Only show assignments after date (YYYY-MM-DD)")
    p.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    add_output_args(p)

    # portfolio
    p = sub.add_parser("portfolio", help="Full patent portfolio for a company")
    p.add_argument("name", help="Company name")
    p.add_argument("--limit", type=int, default=200, help="Max patents (default 200)")
    p.add_argument("--skip-assignments", action="store_true",
                   help="Skip ownership tracing (faster)")
    p.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    add_output_args(p)

    # citations
    p = sub.add_parser("citations", help="Patent continuity (parent/child relationships)")
    p.add_argument("number", help="Patent number")
    p.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    add_output_args(p)

    # enrich
    p = sub.add_parser("enrich", help="Match investigation entities against patent data")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview matches without updating entities")
    p.add_argument("--threshold", type=int, default=85,
                   help="Fuzzy match threshold (default 85)")
    add_output_args(p)

    args = parser.parse_args()

    handlers = {
        "search": cmd_search,
        "inventor": cmd_inventor,
        "assignee": cmd_assignee,
        "patent": cmd_patent,
        "assignments": cmd_assignments,
        "portfolio": cmd_portfolio,
        "citations": cmd_citations,
        "enrich": cmd_enrich,
    }
    try:
        handlers[args.command](args)
    except PatentSourceUnavailable as exc:
        result = {
            "status": "unavailable",
            "source": "uspto_odp",
            "command": args.command,
            "query": getattr(args, "query", getattr(args, "name", None)),
            "error": str(exc),
            "results": [],
        }
        write_output(result, args, summary=f"USPTO ODP {args.command}")
        print(f"ERROR: USPTO ODP unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
