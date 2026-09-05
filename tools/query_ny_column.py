#!/usr/bin/env python3
"""Search New York public notices published through Column.

Verified source contract (2026-07-29):

    Portal:
        https://newyork.column.us/
    Search:
        POST https://us-central1-enotice-production.cloudfunctions.net/
             api/search/public-notices

The source exposes one-indexed pages and reports at most 10,000 matching rows
for a search window. This adapter retrieves every source-reported page by
default. Date, county, and notice-type filters can partition searches that
reach the source's displayed 10,000-row ceiling.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output


SOURCE_ID = "us-ny-public-notices-column"
SOURCE = SOURCE_ID
PORTAL_URL = "https://newyork.column.us/"
SEARCH_ENDPOINT = (
    "https://us-central1-enotice-production.cloudfunctions.net/"
    "api/search/public-notices"
)
SOURCE_STATE = "New York"
SOURCE_DISPLAY_CEILING = 10_000
DEFAULT_PAGE_SIZE = 100
TIMEOUT = 30
MAX_RETRIES = 2
REQUEST_DELAY = 0.1
USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

SENTINEL_QUERY = "CARRINGTON MORTGAGE SERVICES"
SENTINEL_NOTICE_ID = "5r3wmbl7IAfYExOneLRQ-3"
SENTINEL_TEXT_MARKER = "Index #EFC-2025-0044"
SENTINEL_START_DATE = "2026-10-01"
SENTINEL_END_DATE = "2026-10-01"
SENTINEL_COUNTY = "Oswego"
SENTINEL_NOTICE_TYPE = "Foreclosure Sale"

_last_request_at = 0.0


class NyColumnError(RuntimeError):
    """New York Column request or response error."""


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": PORTAL_URL.rstrip("/"),
        "Referer": PORTAL_URL,
    })
    return session


def _positive(value: int, name: str) -> None:
    if value < 1:
        raise NyColumnError(f"{name} must be a positive integer")


def _parse_date(value: str | None, name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise NyColumnError(f"{name} must use YYYY-MM-DD format") from exc


def _timestamp_ms(value: date, *, end_of_day: bool = False) -> int:
    point = datetime.combine(value, datetime_time.min, tzinfo=timezone.utc)
    if end_of_day:
        point += timedelta(days=1)
        return int(point.timestamp() * 1000) - 1
    return int(point.timestamp() * 1000)


def _unique_values(values: list[str] | None, name: str) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = value.strip()
        if not item:
            raise NyColumnError(f"{name} values cannot be empty")
        if item not in seen:
            cleaned.append(item)
            seen.add(item)
    return cleaned


def _county_filter_values(counties: list[str] | None) -> list[str]:
    """Mirror the portal's exact and ``County``-suffixed matching variants."""
    expanded: list[str] = []
    seen: set[str] = set()
    for county in _unique_values(counties, "--county"):
        base = county.removesuffix(" County").strip()
        for value in (base, f"{base} County"):
            if value and value not in seen:
                expanded.append(value)
                seen.add(value)
    return expanded


def _build_filters(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    counties: list[str] | None = None,
    notice_types: list[str] | None = None,
    newspapers: list[str] | None = None,
    filers: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = _parse_date(start_date, "--start-date")
    end = _parse_date(end_date, "--end-date")
    if start and end and start > end:
        raise NyColumnError("--start-date cannot be after --end-date")

    all_filters: list[dict[str, Any]] = []
    date_filter: dict[str, int] = {}
    if start:
        date_filter["from"] = _timestamp_ms(start)
    if end:
        date_filter["to"] = _timestamp_ms(end, end_of_day=True)
    if date_filter:
        all_filters.append({"publishedtimestamp": date_filter})

    all_filters.append({"state": [SOURCE_STATE]})

    clean_notice_types = _unique_values(notice_types, "--notice-type")
    if clean_notice_types:
        all_filters.append({"noticetype": clean_notice_types})

    clean_newspapers = _unique_values(newspapers, "--newspaper")
    if clean_newspapers:
        all_filters.append({"newspapername": clean_newspapers})

    expanded_counties = _county_filter_values(counties)
    if expanded_counties:
        all_filters.append({"county": expanded_counties})

    clean_filers = _unique_values(filers, "--filer")
    if clean_filers:
        all_filters.append({"filer": clean_filers})

    partition = {
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
        "counties": _unique_values(counties, "--county"),
        "notice_types": clean_notice_types,
        "newspapers": clean_newspapers,
        "filers": clean_filers,
    }
    return all_filters, partition


def _request_body(
    query: str,
    all_filters: list[dict[str, Any]],
    *,
    page_size: int,
    current_page: int,
) -> dict[str, Any]:
    _positive(page_size, "--page-size")
    _positive(current_page, "current page")
    return {
        "search": query,
        "allFilters": all_filters,
        "noneFilters": [],
        "sort": [{"publishedtimestamp": "desc"}],
        "pageSize": page_size,
        "current": current_page,
        "isDemo": False,
    }


def _post_search(
    session: requests.Session,
    body: dict[str, Any],
) -> dict[str, Any]:
    global _last_request_at

    for attempt in range(MAX_RETRIES + 1):
        elapsed = time.monotonic() - _last_request_at
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        try:
            _last_request_at = time.monotonic()
            response = session.post(
                SEARCH_ENDPOINT,
                json=body,
                timeout=TIMEOUT,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            if attempt < MAX_RETRIES:
                time.sleep(0.5 * (2**attempt))
                continue
            raise NyColumnError(f"Column search request failed: {exc}") from exc

        if response.status_code == 429 or response.status_code >= 500:
            if attempt < MAX_RETRIES:
                time.sleep(0.5 * (2**attempt))
                continue
        if response.status_code != 200:
            raise NyColumnError(
                f"Column search returned HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise NyColumnError("Column search returned invalid JSON") from exc
        return _validate_response(payload)

    raise NyColumnError("Column search exhausted retries")


def _source_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise NyColumnError(f"Column response field {field!r} is not an integer")
    return value


def _validate_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise NyColumnError("Column search response is not an object")
    if payload.get("success") is not True:
        message = payload.get("message") or payload.get("error") or "unknown error"
        raise NyColumnError(f"Column search reported failure: {message}")
    results = payload.get("results")
    page = payload.get("page")
    if not isinstance(results, list) or not isinstance(page, dict):
        raise NyColumnError("Column response is missing results or page metadata")
    for field in ("current", "total_pages", "total_results", "size"):
        _source_int(page.get(field), f"page.{field}")
    if any(not isinstance(row, dict) for row in results):
        raise NyColumnError("Column response contains a non-object result")
    return payload


def _published_date(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    try:
        return datetime.fromtimestamp(
            timestamp_ms / 1000,
            tz=timezone.utc,
        ).date().isoformat()
    except (OverflowError, OSError, ValueError) as exc:
        raise NyColumnError(
            f"notice has invalid publishedtimestamp: {timestamp_ms}"
        ) from exc


def _notice_url(notice_id: str) -> str:
    return f"{PORTAL_URL}?activeNotice={quote(notice_id, safe='')}"


def _normalize_notice(row: dict[str, Any]) -> dict[str, Any]:
    notice_id = row.get("id")
    if not isinstance(notice_id, str) or not notice_id.strip():
        raise NyColumnError("Column notice is missing a string id")

    notice_text = row.get("text")
    if notice_text is not None and not isinstance(notice_text, str):
        raise NyColumnError(f"Column notice {notice_id} has non-string text")

    raw_timestamp = row.get("publishedtimestamp")
    if raw_timestamp is not None:
        timestamp_ms = _source_int(
            raw_timestamp,
            f"notice {notice_id}.publishedtimestamp",
        )
    else:
        timestamp_ms = None

    publication_name = row.get("newspapername")
    notice_type = row.get("noticetype")
    county = row.get("county")
    state = row.get("state")
    pdf_url = row.get("pdfurl") or None
    filer_id = row.get("filer") or None

    raw_metadata = {
        key: value
        for key, value in row.items()
        if key not in {
            "id",
            "text",
            "publishedtimestamp",
            "noticetype",
            "newspapername",
            "county",
            "state",
            "pdfurl",
            "filer",
        }
    }
    source_url = _notice_url(notice_id)
    return {
        "source": SOURCE,
        "notice_id": notice_id,
        "evidence_ref": f"NY_COLUMN:{notice_id}",
        "source_url": source_url,
        "notice_text": notice_text,
        "pdf_url": pdf_url,
        "filer_id": filer_id,
        "notice_type": notice_type or None,
        "publication_name": publication_name or None,
        "published_timestamp_ms": timestamp_ms,
        "published_date": _published_date(timestamp_ms),
        "county": county or None,
        "state": state or None,
        "publication_metadata": {
            "newspaper": publication_name or None,
            "published_timestamp_ms": timestamp_ms,
            "published_date": _published_date(timestamp_ms),
            "county": county or None,
            "state": state or None,
            "notice_type": notice_type or None,
        },
        "filer_metadata": {
            "source_filer_id": filer_id,
        },
        "discovery_provenance": {
            "platform": "Column",
            "portal_url": PORTAL_URL,
            "search_endpoint": SEARCH_ENDPOINT,
            "record_class": "newspaper_public_notice",
            "investigative_role": "discovery",
            "court_record_status": "not_court_filing",
        },
        "raw_metadata": raw_metadata,
    }


def parse_search_response(payload: Any) -> dict[str, Any]:
    validated = _validate_response(payload)
    return {
        "page": dict(validated["page"]),
        "results": [_normalize_notice(row) for row in validated["results"]],
    }


def search_notices(
    session: requests.Session,
    *,
    query: str,
    all_filters: list[dict[str, Any]],
    partition: dict[str, Any],
    page_size: int = DEFAULT_PAGE_SIZE,
    limit: int | None = None,
) -> dict[str, Any]:
    _positive(page_size, "--page-size")
    if limit is not None:
        _positive(limit, "--limit")

    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    pages_fetched: list[int] = []
    raw_rows_received = 0
    duplicate_rows = 0
    first_page_metadata: dict[str, Any] | None = None
    last_page_metadata: dict[str, Any] | None = None
    source_pages_exhausted = False
    user_limit_reached = False
    current_page = 1

    while True:
        body = _request_body(
            query,
            all_filters,
            page_size=page_size,
            current_page=current_page,
        )
        parsed = parse_search_response(_post_search(session, body))
        page_metadata = parsed["page"]
        if first_page_metadata is None:
            first_page_metadata = dict(page_metadata)
        last_page_metadata = dict(page_metadata)

        source_current = page_metadata["current"]
        if source_current != current_page:
            raise NyColumnError(
                "Column returned source page "
                f"{source_current} for requested page {current_page}"
            )
        pages_fetched.append(source_current)

        rows = parsed["results"]
        raw_rows_received += len(rows)
        for row in rows:
            notice_id = row["notice_id"]
            if notice_id in seen_ids:
                duplicate_rows += 1
                continue
            seen_ids.add(notice_id)
            results.append(row)
            if limit is not None and len(results) >= limit:
                user_limit_reached = True
                break

        total_pages = page_metadata["total_pages"]
        if source_current >= total_pages or total_pages == 0:
            source_pages_exhausted = True
            break
        if user_limit_reached:
            break
        if not rows:
            raise NyColumnError(
                "Column returned an empty page before its reported final page"
            )
        current_page += 1

    if first_page_metadata is None or last_page_metadata is None:
        raise NyColumnError("Column pagination produced no page metadata")

    source_total = first_page_metadata["total_results"]
    ceiling_reached = source_total >= SOURCE_DISPLAY_CEILING
    truncated_by_user_limit = user_limit_reached and not source_pages_exhausted
    return {
        "source": SOURCE,
        "source_url": PORTAL_URL,
        "search_endpoint": SEARCH_ENDPOINT,
        "query": query,
        "partition": partition,
        "source_request": {
            "search": query,
            "allFilters": all_filters,
            "noneFilters": [],
            "sort": [{"publishedtimestamp": "desc"}],
            "pageSize": page_size,
            "isDemo": False,
        },
        "coverage": {
            "source_reported_total_results": source_total,
            "source_display_ceiling": SOURCE_DISPLAY_CEILING,
            "source_display_ceiling_reached": ceiling_reached,
            "source_reported_total_kind": (
                "display_ceiling" if ceiling_reached else "exact_within_partition"
            ),
            "returned_unique_results": len(results),
            "raw_rows_received": raw_rows_received,
            "duplicate_rows_removed": duplicate_rows,
            "source_pages_exhausted": source_pages_exhausted,
            "user_limit": limit,
            "truncated_by_user_limit": truncated_by_user_limit,
        },
        "pagination": {
            "kind": "source_one_indexed_pages",
            "page_size": page_size,
            "source_reported_total_pages": first_page_metadata["total_pages"],
            "pages_fetched": pages_fetched,
            "first_page_metadata": first_page_metadata,
            "last_page_metadata": last_page_metadata,
            "returned_all_source_reported_pages": source_pages_exhausted,
        },
        "results": results,
    }


def _log(query: str, count: int) -> None:
    try:
        log_search(query, SOURCE, count)
    except Exception as exc:
        print(f"Warning: could not log search: {exc}", file=sys.stderr)


def _emit(payload: dict[str, Any], args: argparse.Namespace, summary: str) -> None:
    if write_output(payload, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return

    if "results" not in payload:
        print(f"{payload.get('status', SOURCE)}")
        return
    coverage = payload["coverage"]
    print(
        f"{len(payload['results'])} results; source reported "
        f"{coverage['source_reported_total_results']}"
    )
    if coverage["source_display_ceiling_reached"]:
        print(
            "Source display ceiling reached; partition by date, county, "
            "or notice type for narrower coverage."
        )
    for row in payload["results"]:
        print(
            f"- {row['published_date'] or 'unknown date'} | "
            f"{row['publication_name'] or 'unknown publication'} | "
            f"{row['notice_type'] or 'Public Notice'}"
        )
        print(f"  {row['source_url']}")


def cmd_search(args: argparse.Namespace) -> int:
    all_filters, partition = _build_filters(
        start_date=args.start_date,
        end_date=args.end_date,
        counties=args.county,
        notice_types=args.notice_type,
        newspapers=args.newspaper,
        filers=args.filer,
    )
    payload = search_notices(
        _session(),
        query=args.query,
        all_filters=all_filters,
        partition=partition,
        page_size=args.page_size,
        limit=args.limit,
    )
    log_query = json.dumps(
        {
            "query": args.query,
            "partition": partition,
        },
        sort_keys=True,
    )
    _log(log_query, len(payload["results"]))
    _emit(payload, args, f"New York Column public notices {args.query!r}")
    return 0


def run_sentinel(session: requests.Session | None = None) -> dict[str, Any]:
    session = session or _session()
    checks: list[dict[str, Any]] = []

    try:
        all_filters, partition = _build_filters(
            start_date=SENTINEL_START_DATE,
            end_date=SENTINEL_END_DATE,
            counties=[SENTINEL_COUNTY],
            notice_types=[SENTINEL_NOTICE_TYPE],
        )
        narrow_body = _request_body(
            SENTINEL_QUERY,
            all_filters,
            page_size=5,
            current_page=1,
        )
        narrow = parse_search_response(_post_search(session, narrow_body))
        sentinel = next(
            (
                row
                for row in narrow["results"]
                if row["notice_id"] == SENTINEL_NOTICE_ID
            ),
            None,
        )
        if sentinel is None:
            raise NyColumnError("known partition did not return the sentinel notice")
        if SENTINEL_TEXT_MARKER not in (sentinel["notice_text"] or ""):
            raise NyColumnError("sentinel notice text marker is missing")
        checks.append({
            "name": "partitioned_notice",
            "status": "ok",
            "notice_id": sentinel["notice_id"],
            "source_url": sentinel["source_url"],
            "published_date": sentinel["published_date"],
            "county": sentinel["county"],
            "notice_type": sentinel["notice_type"],
            "publication_name": sentinel["publication_name"],
            "partition": partition,
        })
    except NyColumnError as exc:
        checks.append({
            "name": "partitioned_notice",
            "status": "error",
            "error": str(exc),
        })

    try:
        broad_filters, _ = _build_filters()
        ceiling_body = _request_body(
            "",
            broad_filters,
            page_size=1,
            current_page=1,
        )
        broad = parse_search_response(_post_search(session, ceiling_body))
        reported_total = broad["page"]["total_results"]
        if reported_total != SOURCE_DISPLAY_CEILING:
            raise NyColumnError(
                "source display ceiling changed: "
                f"expected {SOURCE_DISPLAY_CEILING}, got {reported_total}"
            )
        checks.append({
            "name": "display_ceiling",
            "status": "ok",
            "source_reported_total_results": reported_total,
            "source_display_ceiling": SOURCE_DISPLAY_CEILING,
            "source_reported_total_pages": broad["page"]["total_pages"],
        })
    except NyColumnError as exc:
        checks.append({
            "name": "display_ceiling",
            "status": "error",
            "error": str(exc),
        })

    ok = all(check["status"] == "ok" for check in checks)
    return {
        "source": SOURCE,
        "status": "ok" if ok else "unavailable",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "exact_urls": {
            "portal": PORTAL_URL,
            "search_endpoint": SEARCH_ENDPOINT,
            "sentinel_notice": _notice_url(SENTINEL_NOTICE_ID),
        },
    }


def cmd_sentinel(args: argparse.Namespace) -> int:
    payload = run_sentinel()
    _emit(payload, args, "New York Column live sentinel")
    return 0 if payload["status"] == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search New York public notices published through Column"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search all source-reported pages in a notice partition",
    )
    search.add_argument(
        "query",
        nargs="?",
        default="",
        help="Full-text query; omit to browse a filtered partition",
    )
    search.add_argument("--start-date", help="Inclusive publication date YYYY-MM-DD")
    search.add_argument("--end-date", help="Inclusive publication date YYYY-MM-DD")
    search.add_argument(
        "--county",
        action="append",
        help="County facet; repeat for multiple values",
    )
    search.add_argument(
        "--notice-type",
        action="append",
        help="Notice-type facet; repeat for multiple values",
    )
    search.add_argument(
        "--newspaper",
        action="append",
        help="Publication facet; repeat for multiple values",
    )
    search.add_argument(
        "--filer",
        action="append",
        help="Source-native filer ID; repeat for multiple values",
    )
    search.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"Source request page size (default: {DEFAULT_PAGE_SIZE})",
    )
    search.add_argument(
        "--limit",
        type=int,
        help="Optional user-requested result limit; default retrieves all pages",
    )
    add_output_args(search)
    search.set_defaults(func=cmd_search)

    sentinel = subparsers.add_parser(
        "sentinel",
        help="Verify partition filters, record schema, and displayed ceiling",
    )
    add_output_args(sentinel)
    sentinel.set_defaults(func=cmd_sentinel)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except NyColumnError as exc:
        payload = {
            "status": "error",
            "source": SOURCE,
            "error": str(exc),
            "results": [],
        }
        if getattr(args, "output", None):
            write_output(payload, args, summary="New York Column request failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
