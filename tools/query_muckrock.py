#!/usr/bin/env python3
"""Authenticated MuckRock API v2 client for OSINT investigations.

Searches FOIA requests, retrieves request communications and released-file
metadata, downloads released documents, lists project requests, and searches
agencies through MuckRock's official ``python-muckrock`` wrapper. It can also
build and search a resumable local SQLite/FTS5 index of the public corpus.

Authentication uses a normal MuckRock account. The wrapper exchanges the
credentials for short-lived Squarelet access/refresh tokens and refreshes them
automatically.

Required environment variables (a repo-local ``.env`` is also supported):
    MUCKROCK_USERNAME
    MUCKROCK_PASSWORD

Usage:
    uv run python tools/query_muckrock.py project
    uv run python tools/query_muckrock.py project 507
    uv run python tools/query_muckrock.py request 78799
    uv run python tools/query_muckrock.py download 78799 --dir datasets/muckrock
    uv run python tools/query_muckrock.py search "Jeffrey Epstein" --limit 25
    uv run python tools/query_muckrock.py agencies "Federal Bureau"
    uv run python tools/query_muckrock.py crawl-index --max-pages 1
    uv run python tools/query_muckrock.py unlinked-files "GEO Group"
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from muckrock import MuckRock
from squarelet.exceptions import (
    CredentialsFailedError,
    DoesNotExistError,
    SquareletError,
)

try:
    from tools.env_loader import load_env_file
    from tools.lead_tracker import log_search
    from tools.muckrock_index import (
        COLLECTIONS as INDEX_COLLECTIONS,
        DEFAULT_INDEX_DB,
        crawl_index,
        index_stats,
        search_index,
    )
    from tools.output_util import add_output_args, write_output
except ImportError:
    from env_loader import load_env_file
    from lead_tracker import log_search
    from muckrock_index import (
        COLLECTIONS as INDEX_COLLECTIONS,
        DEFAULT_INDEX_DB,
        crawl_index,
        index_stats,
        search_index,
    )
    from output_util import add_output_args, write_output

load_env_file()

DEFAULT_PROJECT_ID = 507
DEFAULT_DOWNLOAD_DIR = "datasets/muckrock"
MUCKROCK_WEB_BASE = "https://www.muckrock.com"
DOWNLOAD_USER_AGENT = "OSINT-Research/1.0"
API_RETRY_ATTEMPTS = 3
API_RETRY_BACKOFF_SECONDS = 1.0
TRANSIENT_API_STATUS_CODES = {500, 502, 503, 504}


class MuckRockConfigurationError(RuntimeError):
    """Raised when local MuckRock configuration is missing or invalid."""


# ---------------------------------------------------------------------------
# Client and object helpers
# ---------------------------------------------------------------------------


def _create_client() -> MuckRock:
    """Create an authenticated official API-v2 client."""
    username = os.environ.get("MUCKROCK_USERNAME", "").strip()
    password = os.environ.get("MUCKROCK_PASSWORD", "")

    missing = [
        name
        for name, value in (
            ("MUCKROCK_USERNAME", username),
            ("MUCKROCK_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        joined = " and ".join(missing)
        raise MuckRockConfigurationError(
            f"{joined} not set. Add your MuckRock account credentials to the "
            "repo-local .env file or export them in the shell."
        )

    return MuckRock(username=username, password=password)


def _retry_api_call(operation, description):
    """Run one API-v2 operation with bounded transient-server retries."""
    for attempt in range(API_RETRY_ATTEMPTS):
        try:
            return operation()
        except SquareletError as exc:
            status_code = getattr(exc, "status_code", None)
            is_retryable = status_code in TRANSIENT_API_STATUS_CODES
            if not is_retryable or attempt + 1 == API_RETRY_ATTEMPTS:
                raise
            wait = API_RETRY_BACKOFF_SECONDS * (2**attempt)
            print(
                f"  MuckRock {description} returned HTTP {status_code}; "
                f"retrying in {wait:g}s...",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise AssertionError("unreachable")


def _retrieve_request(client: MuckRock, request_id):
    """Retrieve one FOIA request with transient-server retry handling."""
    return _retry_api_call(
        lambda: client.requests.retrieve(request_id),
        f"request {request_id}",
    )


def _configured_project_id() -> int:
    """Return the configured default project ID."""
    raw = os.environ.get("MUCKROCK_PROJECT_ID", str(DEFAULT_PROJECT_ID)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise MuckRockConfigurationError(
            f"MUCKROCK_PROJECT_ID must be an integer, got {raw!r}."
        ) from exc


def _get(obj, name, default=None):
    """Read a field from an API object or plain dictionary."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _first(obj, *names, default=None):
    """Return the first present, non-None object field."""
    for name in names:
        value = _get(obj, name)
        if value is not None:
            return value
    return default


def _object_id(value):
    """Normalize an ID that may be scalar, dictionary, or API object."""
    if value is None or isinstance(value, (int, str)):
        return value
    return _get(value, "id", value)


def _display_party(value) -> str:
    """Render a communication participant represented by ID or object."""
    if value is None:
        return ""
    if isinstance(value, (int, str)):
        return str(value)
    return str(_first(value, "name", "username", "id", default=""))


def _limited(results, limit: int):
    """Yield at most ``limit`` objects from a paginated API result."""
    for index, result in enumerate(results):
        if index >= limit:
            break
        yield result


def _total_count(results, returned: int) -> int:
    """Read the API's total result count with a safe local fallback."""
    count = getattr(results, "count", None)
    return returned if count is None else int(count)


def _positive_int(value: str) -> int:
    """Argparse type for strictly positive limits."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _nonnegative_int(value: str) -> int:
    """Argparse type for counts where zero means unlimited."""
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("cannot be negative")
    return parsed


def _nonnegative_float(value: str) -> float:
    """Argparse type for nonnegative crawl delays."""
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("cannot be negative")
    return parsed


_agency_cache: dict[int | str, str] = {}


def _agency_name(client: MuckRock, agency) -> str:
    """Resolve a request agency ID to a human-readable name."""
    if agency is None:
        return "Unknown Agency"

    direct_name = _get(agency, "name")
    if direct_name:
        return str(direct_name)

    agency_id = _object_id(agency)
    if agency_id in _agency_cache:
        return _agency_cache[agency_id]

    try:
        resolved = client.agencies.retrieve(agency_id)
        name = str(_get(resolved, "name", f"Agency #{agency_id}"))
    except DoesNotExistError:
        name = f"Agency #{agency_id}"

    _agency_cache[agency_id] = name
    return name


def _request_file_count(foia) -> int:
    """Count request files from communication file references."""
    count = 0
    communications = _retry_api_call(
        lambda: list(foia.get_communications()),
        f"communications for request {_get(foia, 'id', '?')}",
    )
    for communication in communications:
        file_refs = _get(communication, "files")
        if isinstance(file_refs, (list, tuple, set)):
            count += len(file_refs)
        else:
            count += len(_communication_files(communication))
    return count


def _request_summary(client: MuckRock, foia, *, include_file_count: bool) -> dict:
    """Normalize request fields shared by project and search output."""
    agency = _get(foia, "agency")
    summary = {
        "id": _get(foia, "id"),
        "title": _get(foia, "title", "Untitled"),
        "status": _get(foia, "status", "unknown"),
        "agency": _agency_name(client, agency),
        "agency_id": _object_id(agency),
        "date_submitted": str(_get(foia, "datetime_submitted", "") or ""),
        "tracking_id": _get(foia, "tracking_id", "") or "",
        "slug": _get(foia, "slug", "") or "",
        "file_count": None,
    }
    if include_file_count:
        summary["file_count"] = _request_file_count(foia)
    return summary


def _communication_files(communication) -> list:
    """Retrieve file objects for a communication, avoiding known-empty calls."""
    file_refs = _get(communication, "files")
    if isinstance(file_refs, (list, tuple, set)) and not file_refs:
        return []
    return _retry_api_call(
        lambda: list(communication.get_files()),
        f"files for communication {_get(communication, 'id', '?')}",
    )


def _file_record(file_obj, communication_date: str) -> dict:
    """Normalize a MuckRock file object."""
    return {
        "id": _get(file_obj, "id"),
        "title": _get(file_obj, "title", "") or "",
        "url": _get(file_obj, "ffile", "") or "",
        "pages": _get(file_obj, "pages"),
        "datetime": str(_get(file_obj, "datetime", "") or ""),
        "source": _get(file_obj, "source", "") or "",
        "description": _get(file_obj, "description", "") or "",
        "doc_id": _get(file_obj, "doc_id"),
        "comm_date": communication_date,
    }


def _request_detail(client: MuckRock, foia) -> tuple[dict, list[dict]]:
    """Build full request output and return its flattened file records."""
    communications = []
    all_files = []

    request_id = _get(foia, "id", "?")
    communication_objects = _retry_api_call(
        lambda: list(foia.get_communications()),
        f"communications for request {request_id}",
    )
    for communication in communication_objects:
        communication_date = str(_get(communication, "datetime", "") or "")
        files = [
            _file_record(file_obj, communication_date)
            for file_obj in _communication_files(communication)
        ]
        all_files.extend(files)
        communications.append(
            {
                "id": _get(communication, "id"),
                "date": communication_date,
                "from_who": _display_party(
                    _first(communication, "from_who", "from_user")
                ),
                "to_who": _display_party(
                    _first(communication, "to_who", "to_user")
                ),
                "subject": _get(communication, "subject", "") or "",
                "body": _get(communication, "communication", "") or "",
                "response": bool(_get(communication, "response", False)),
                "status": _get(communication, "status", "") or "",
                "file_count": len(files),
                "files": files,
            }
        )

    agency = _get(foia, "agency")
    request_id = _get(foia, "id")
    output = {
        "id": request_id,
        "title": _get(foia, "title", "Untitled"),
        "status": _get(foia, "status", "unknown"),
        "agency": _agency_name(client, agency),
        "agency_id": _object_id(agency),
        "date_submitted": str(_get(foia, "datetime_submitted", "") or ""),
        "date_done": str(_get(foia, "datetime_done", "") or ""),
        "tracking_id": _get(foia, "tracking_id", "") or "",
        "slug": _get(foia, "slug", "") or "",
        "requested_docs": _get(foia, "requested_docs", "") or "",
        "url": f"{MUCKROCK_WEB_BASE}/foi/request/{request_id}/",
        "total_files": len(all_files),
        "total_pages": sum(_get(file_obj, "pages", 0) or 0 for file_obj in all_files),
        "communications": communications,
    }
    return output, all_files


def _record_search(query: str, result_count: int) -> None:
    """Log successful MuckRock searches without obscuring local DB failures."""
    try:
        log_search(query, "muckrock", result_count)
    except Exception as exc:  # local logging must not invalidate remote results
        print(f"WARNING: Could not log MuckRock search: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------


def _download_file(url: str, dest_path: Path) -> bool:
    """Download a released file URL returned by API v2."""
    absolute_url = urljoin(MUCKROCK_WEB_BASE, url)
    req = Request(absolute_url, headers={"User-Agent": DOWNLOAD_USER_AGENT})
    try:
        with urlopen(req, timeout=120) as response:
            data = response.read()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(data)
        print(f"  Downloaded {dest_path.name} ({len(data) / 1024:.1f} KB)")
        return True
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"  ERROR downloading {absolute_url}: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Status display helpers
# ---------------------------------------------------------------------------


FOIA_STATUS_LABELS = {
    "submitted": "Processing",
    "ack": "Awaiting Acknowledgement",
    "processed": "Awaiting Response",
    "appealing": "Awaiting Appeal",
    "fix": "Fix Required",
    "payment": "Payment Required",
    "rejected": "Rejected",
    "no_docs": "No Responsive Documents",
    "done": "Completed",
    "partial": "Partially Completed",
    "abandoned": "Withdrawn",
    "lawsuit": "In Litigation",
    "consolidated": "Consolidated",
}


def _status_label(status) -> str:
    """Return a human-readable MuckRock request status."""
    return FOIA_STATUS_LABELS.get(status, status or "Unknown")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_project(client: MuckRock, args) -> int:
    """List FOIA requests associated with a MuckRock project."""
    project_id = args.project_id
    print(f"Fetching project {project_id}...", file=sys.stderr)
    project = client.projects.retrieve(project_id)

    request_refs = _get(project, "requests", []) or []
    requests = []
    for index, request_ref in enumerate(request_refs, 1):
        request_id = _object_id(request_ref)
        print(
            f"  Fetching request {request_id} ({index}/{len(request_refs)})...",
            file=sys.stderr,
        )
        foia = _retrieve_request(client, request_id)
        requests.append(_request_summary(client, foia, include_file_count=True))

    title = _get(project, "title", f"Project {project_id}")
    output_data = {
        "project_id": project_id,
        "project_title": title,
        "request_count": len(requests),
        "requests": requests,
    }

    if write_output(
        output_data,
        args,
        summary=f"MuckRock project {project_id} '{title}'",
    ):
        return 0
    if getattr(args, "json_out", False):
        print(json.dumps(output_data, indent=2, default=str))
        return 0

    print(f"\n{'=' * 70}")
    print(f"MuckRock Project: {title} (ID {project_id})")
    print(f"FOIA Requests: {len(requests)}")
    print(f"{'=' * 70}\n")

    for request in requests:
        status = _status_label(request["status"])
        files = f"{request['file_count']} files"
        date = request["date_submitted"][:10] or "no date"
        print(f"  [{request['id']}] {request['title']}")
        print(
            f"    Status: {status}  |  Agency: {request['agency']}  |  "
            f"{files}  |  {date}"
        )
        if request["tracking_id"]:
            print(f"    Tracking: {request['tracking_id']}")
        print()
    return 0


def cmd_request(client: MuckRock, args) -> int:
    """Show detail for a single FOIA request."""
    request_id = args.request_id
    print(f"Fetching FOIA request {request_id}...", file=sys.stderr)
    foia = _retrieve_request(client, request_id)
    output_data, _files = _request_detail(client, foia)

    if write_output(output_data, args, summary=f"MuckRock FOIA #{request_id}"):
        return 0
    if getattr(args, "json_out", False):
        print(json.dumps(output_data, indent=2, default=str))
        return 0

    status = _status_label(output_data["status"])
    print(f"\n{'=' * 70}")
    print(f"FOIA Request #{output_data['id']}: {output_data['title']}")
    print(f"{'=' * 70}")
    print(f"  Status:    {status}")
    print(f"  Agency:    {output_data['agency']}")
    submitted = output_data["date_submitted"][:10] or "N/A"
    print(f"  Submitted: {submitted}")
    if output_data["date_done"]:
        print(f"  Completed: {output_data['date_done'][:10]}")
    if output_data["tracking_id"]:
        print(f"  Tracking:  {output_data['tracking_id']}")
    print(
        f"  Files:     {output_data['total_files']} "
        f"({output_data['total_pages']} pages)"
    )
    print()

    for index, communication in enumerate(output_data["communications"], 1):
        date = communication["date"][:10] or "no date"
        direction = "RESPONSE" if communication["response"] else "SENT"
        from_part = (
            f" from {communication['from_who']}" if communication["from_who"] else ""
        )
        to_part = f" to {communication['to_who']}" if communication["to_who"] else ""
        print(
            f"  --- Communication {index} [{direction}] "
            f"{date}{from_part}{to_part} ---"
        )
        if communication["subject"]:
            print(f"  Subject: {communication['subject']}")
        for file_obj in communication["files"]:
            pages = f" ({file_obj['pages']} pages)" if file_obj["pages"] else ""
            print(f"    FILE: {file_obj['title'] or 'Untitled'}{pages}")
            if file_obj["url"]:
                print(f"          {file_obj['url']}")
        print()
    return 0


def cmd_download(client: MuckRock, args) -> int:
    """Download all released files attached to a FOIA request."""
    request_id = args.request_id
    base_dir = Path(args.dir) if args.dir else Path(DEFAULT_DOWNLOAD_DIR)
    dest_dir = base_dir / str(request_id)

    print(f"Fetching FOIA request {request_id}...", file=sys.stderr)
    foia = _retrieve_request(client, request_id)
    output_data, files = _request_detail(client, foia)

    if not files:
        print(f"No files found for FOIA request {request_id}")
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"FOIA #{request_id}: {output_data['title']}")
    print(f"  {len(files)} files to download -> {dest_dir}\n")

    downloaded = 0
    skipped = 0
    failed = 0

    for file_obj in files:
        url = file_obj["url"]
        if not url:
            print(f"  SKIP: No URL for file {file_obj['id']}", file=sys.stderr)
            failed += 1
            continue

        url_filename = Path(urlparse(url).path).name
        if not url_filename:
            safe_title = "".join(
                character if character.isalnum() or character in "-_." else "_"
                for character in file_obj["title"]
            )
            url_filename = f"{file_obj['id']}_{safe_title or 'file'}.pdf"

        dest_path = dest_dir / url_filename
        if dest_path.exists():
            skipped += 1
            continue

        if _download_file(url, dest_path):
            downloaded += 1
        else:
            failed += 1

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped (exist), {failed} failed")
    print(f"Files in: {dest_dir}")
    return 1 if failed else 0


def cmd_search(client: MuckRock, args) -> int:
    """Search FOIA requests using API v2 full-text search."""
    query = args.query
    api_results = client.requests.list(
        search=query,
        page_size=min(100, args.limit),
    )
    requests = list(_limited(api_results, args.limit))
    output_results = [
        _request_summary(client, request, include_file_count=False)
        for request in requests
    ]
    total = _total_count(api_results, len(output_results))

    output_data = {
        "query": query,
        "total": total,
        "showing": len(output_results),
        "results": output_results,
    }
    _record_search(query, len(output_results))

    if write_output(output_data, args, summary=f"MuckRock search '{query}'"):
        return 0
    if getattr(args, "json_out", False):
        print(json.dumps(output_data, indent=2, default=str))
        return 0

    print(f"\nMuckRock FOIA search: '{query}'")
    print(f"Found {total} results (showing {len(output_results)})\n")

    for request in output_results:
        status = _status_label(request["status"])
        date = request["date_submitted"][:10] or "no date"
        print(f"  [{request['id']}] {request['title']}")
        print(
            f"    Status: {status}  |  Agency: {request['agency']}  |  "
            f"file count not expanded  |  {date}"
        )
        print()
    return 0


def cmd_agencies(client: MuckRock, args) -> int:
    """Search MuckRock agencies by partial name through API v2."""
    query = args.query
    api_results = client.agencies.list(
        name=query,
        page_size=min(100, args.limit),
    )
    agencies = list(_limited(api_results, args.limit))
    total = _total_count(api_results, len(agencies))

    output_results = []
    for agency in agencies:
        jurisdiction = _get(agency, "jurisdiction")
        jurisdiction_id = _object_id(jurisdiction)
        if isinstance(jurisdiction, dict) or _get(jurisdiction, "name"):
            jurisdiction_name = str(_get(jurisdiction, "name", ""))
        else:
            jurisdiction_name = ""

        output_results.append(
            {
                "id": _get(agency, "id"),
                "name": _get(agency, "name", "Unknown"),
                "slug": _get(agency, "slug", "") or "",
                "status": _get(agency, "status", "") or "",
                "jurisdiction": jurisdiction_name,
                "jurisdiction_id": jurisdiction_id,
                "average_response_time": _get(agency, "average_response_time"),
                "success_rate": _get(agency, "success_rate"),
                "number_requests": _get(agency, "number_requests"),
                "number_requests_completed": _get(
                    agency, "number_requests_done"
                ),
            }
        )

    output_data = {
        "query": query,
        "total": total,
        "showing": len(output_results),
        "results": output_results,
    }
    _record_search(f"agency:{query}", len(output_results))

    if write_output(output_data, args, summary=f"MuckRock agencies '{query}'"):
        return 0
    if getattr(args, "json_out", False):
        print(json.dumps(output_data, indent=2, default=str))
        return 0

    print(f"\nMuckRock Agency search: '{query}'")
    print(f"Found {total} agencies (showing {len(output_results)})\n")

    for agency in output_results:
        print(f"  [{agency['id']}] {agency['name']}")
        jurisdiction = agency["jurisdiction"] or (
            f"Jurisdiction #{agency['jurisdiction_id']}"
            if agency["jurisdiction_id"] is not None
            else "N/A"
        )
        print(f"    Jurisdiction: {jurisdiction}")

        stats = []
        if agency["number_requests"] is not None:
            done = agency["number_requests_completed"]
            done_text = f" ({done} completed)" if done is not None else ""
            stats.append(f"{agency['number_requests']} requests{done_text}")
        if agency["average_response_time"] is not None:
            stats.append(f"avg {agency['average_response_time']} days")
        if agency["success_rate"] is not None:
            try:
                success_rate = float(agency["success_rate"])
                if success_rate > 100:
                    success_rate /= 100
                stats.append(f"{success_rate:.1f}% success")
            except (TypeError, ValueError):
                stats.append(f"{agency['success_rate']} success")
        if stats:
            print(f"    Stats: {' | '.join(stats)}")
        print()
    return 0


def _index_progress(
    collection: str, page: int, row_count: int, total: int | None
) -> None:
    """Print one concise crawl checkpoint after it is committed."""
    total_text = f"/{total}" if total is not None else ""
    print(
        f"  [{collection}] page {page}: {row_count} rows "
        f"(API total {total_text.lstrip('/') or 'unknown'})",
        file=sys.stderr,
        flush=True,
    )


def cmd_crawl_index(client: MuckRock, args) -> int:
    """Crawl public MuckRock collections into the resumable local index."""
    result = crawl_index(
        client,
        db_path=args.db,
        collections=args.collections,
        max_pages=args.max_pages,
        delay=args.delay,
        restart=args.restart,
        progress=_index_progress,
    )
    query = "crawl-index " + ",".join(args.collections)
    _record_search(query, result["rows_upserted"])
    if write_output(result, args, summary=f"MuckRock {query}"):
        return 0
    print(json.dumps(result, indent=2, default=str))
    return 0


def _local_index_search(args, *, force_unlinked: bool = False) -> int:
    without_documentcloud = force_unlinked or args.without_documentcloud
    response_only = (
        not args.include_outbound if force_unlinked else args.responses_only
    )
    results = search_index(
        db_path=args.db,
        query=args.query,
        without_documentcloud=without_documentcloud,
        response_only=response_only,
        agency_id=args.agency_id,
        limit=args.limit,
    )
    output_data = {
        "query": args.query or "",
        "db": str(args.db),
        "without_documentcloud": without_documentcloud,
        "documentcloud_filter_note": (
            "Blank MuckRock doc_id means no direct DocumentCloud linkage; it does "
            "not rule out a separately uploaded duplicate."
        ),
        "responses_only": response_only,
        "showing": len(results),
        "results": results,
    }
    qualifiers = []
    if without_documentcloud:
        qualifiers.append("documentcloud-unlinked")
    if response_only:
        qualifiers.append("responses-only")
    log_query = f"index:{args.query or '*'}"
    if qualifiers:
        log_query += " " + ",".join(qualifiers)
    _record_search(log_query, len(results))

    if write_output(
        output_data,
        args,
        summary=f"MuckRock local index search '{args.query or '*'}'",
    ):
        return 0
    if getattr(args, "json_out", False):
        print(json.dumps(output_data, indent=2, default=str))
        return 0

    label = "DocumentCloud-unlinked response files" if force_unlinked else "files"
    print(f"\nMuckRock local index: {label}")
    print(f"Query: {args.query or '(all indexed records)'}")
    print(f"Showing {len(results)} results\n")
    for result in results:
        pages = f" ({result['pages']} pages)" if result["pages"] else ""
        print(f"  [file {result['file_id']}] {result['file_title'] or 'Untitled'}{pages}")
        request_title = result["request_title"] or "Unknown request"
        agency = result["agency_name"] or (
            f"Agency #{result['agency_id']}"
            if result["agency_id"] is not None
            else "Unknown agency"
        )
        print(f"    Request #{result['request_id']}: {request_title}")
        print(f"    Agency: {agency}")
        if result["communication_subject"]:
            print(f"    Communication: {result['communication_subject']}")
        if result["communication_excerpt"]:
            print(f"    Context: {result['communication_excerpt']}")
        print(f"    File: {result['file_url']}")
        print(f"    Request: {result['request_url']}")
        print()
    return 0


def cmd_index_search(args) -> int:
    """Search the local index across request, communication, and file text."""
    return _local_index_search(args)


def cmd_unlinked_files(args) -> int:
    """Find response files with no direct DocumentCloud linkage."""
    return _local_index_search(args, force_unlinked=True)


def cmd_index_stats(args) -> int:
    """Show local index counts, linkage coverage, and resumable cursors."""
    result = index_stats(args.db)
    if write_output(result, args, summary="MuckRock local index stats"):
        return 0
    print(json.dumps(result, indent=2, default=str))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Authenticated MuckRock API v2 tool for OSINT investigations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Requires MUCKROCK_USERNAME and MUCKROCK_PASSWORD.

Examples:
  %(prog)s project
  %(prog)s project 507
  %(prog)s request 78799
  %(prog)s download 78799 --dir datasets/muckrock
  %(prog)s search "Jeffrey Epstein" --limit 25
  %(prog)s agencies "Federal Bureau"
  %(prog)s crawl-index --max-pages 1
  %(prog)s crawl-index --output /tmp/muckrock-crawl.json
  %(prog)s index-search "GEO Group" --without-documentcloud
  %(prog)s unlinked-files "private prison" --limit 50
  %(prog)s index-stats
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    project = subparsers.add_parser("project", help="List FOIA requests in a project")
    project.add_argument(
        "project_id",
        nargs="?",
        type=int,
        help=(
            f"Project ID (default: MUCKROCK_PROJECT_ID or {DEFAULT_PROJECT_ID})"
        ),
    )
    add_output_args(project)

    request = subparsers.add_parser("request", help="Show detail for a FOIA request")
    request.add_argument("request_id", type=int, help="FOIA request ID")
    add_output_args(request)

    download = subparsers.add_parser(
        "download", help="Download released files from a FOIA request"
    )
    download.add_argument("request_id", type=int, help="FOIA request ID")
    download.add_argument(
        "--dir",
        help=f"Download directory (default: {DEFAULT_DOWNLOAD_DIR})",
    )

    search = subparsers.add_parser("search", help="Full-text search FOIA requests")
    search.add_argument("query", help="Text to search for")
    search.add_argument(
        "--limit",
        type=_positive_int,
        default=100,
        help="Maximum results (default: 100)",
    )
    add_output_args(search)

    agencies = subparsers.add_parser("agencies", help="Search agencies")
    agencies.add_argument("query", help="Partial agency name")
    agencies.add_argument(
        "--limit",
        type=_positive_int,
        default=50,
        help="Maximum results (default: 50)",
    )
    add_output_args(agencies)

    crawl = subparsers.add_parser(
        "crawl-index",
        help="Crawl public API collections into a resumable local SQLite index",
    )
    crawl.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_INDEX_DB,
        help=f"Index database (default: {DEFAULT_INDEX_DB})",
    )
    crawl.add_argument(
        "--collections",
        nargs="+",
        choices=INDEX_COLLECTIONS,
        default=list(INDEX_COLLECTIONS),
        help="Collections to crawl (default: all)",
    )
    crawl.add_argument(
        "--max-pages",
        type=_nonnegative_int,
        default=0,
        help="Maximum pages per collection this run; 0 is unlimited",
    )
    crawl.add_argument(
        "--delay",
        type=_nonnegative_float,
        default=1.0,
        help="Minimum seconds between aggregate API requests (default: 1.0)",
    )
    crawl.add_argument(
        "--restart",
        action="store_true",
        help="Restart selected completed/in-progress collection cursors at page 1",
    )
    add_output_args(crawl)

    index_search = subparsers.add_parser(
        "index-search",
        help="Search local request, communication, and file metadata",
    )
    index_search.add_argument(
        "query",
        nargs="?",
        help="Terms to match; omit to browse indexed files",
    )
    index_search.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_INDEX_DB,
        help=f"Index database (default: {DEFAULT_INDEX_DB})",
    )
    index_search.add_argument(
        "--without-documentcloud",
        action="store_true",
        help="Only files whose MuckRock API record has no DocumentCloud doc_id",
    )
    index_search.add_argument(
        "--responses-only",
        action="store_true",
        help="Only files attached to incoming agency responses",
    )
    index_search.add_argument("--agency-id", type=int)
    index_search.add_argument("--limit", type=_positive_int, default=100)
    add_output_args(index_search)

    unlinked = subparsers.add_parser(
        "unlinked-files",
        help="Find agency-response files with no direct DocumentCloud linkage",
    )
    unlinked.add_argument(
        "query",
        nargs="?",
        help="Terms to match; omit to browse all indexed unlinked response files",
    )
    unlinked.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_INDEX_DB,
        help=f"Index database (default: {DEFAULT_INDEX_DB})",
    )
    unlinked.add_argument(
        "--include-outbound",
        action="store_true",
        help="Also include requester uploads and other outbound attachments",
    )
    unlinked.add_argument("--agency-id", type=int)
    unlinked.add_argument("--limit", type=_positive_int, default=100)
    unlinked.set_defaults(without_documentcloud=True, responses_only=True)
    add_output_args(unlinked)

    stats = subparsers.add_parser(
        "index-stats", help="Show local index and DocumentCloud-linkage coverage"
    )
    stats.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_INDEX_DB,
        help=f"Index database (default: {DEFAULT_INDEX_DB})",
    )
    add_output_args(stats)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        local_handlers = {
            "index-search": cmd_index_search,
            "unlinked-files": cmd_unlinked_files,
            "index-stats": cmd_index_stats,
        }
        if args.command in local_handlers:
            return local_handlers[args.command](args)

        if args.command == "project" and args.project_id is None:
            args.project_id = _configured_project_id()
        client = _create_client()
        handlers = {
            "project": cmd_project,
            "request": cmd_request,
            "download": cmd_download,
            "search": cmd_search,
            "agencies": cmd_agencies,
            "crawl-index": cmd_crawl_index,
        }
        return handlers[args.command](client, args)
    except MuckRockConfigurationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
    except CredentialsFailedError as exc:
        print(f"ERROR: MuckRock authentication failed: {exc}", file=sys.stderr)
    except DoesNotExistError as exc:
        print(f"ERROR: MuckRock resource not found: {exc}", file=sys.stderr)
    except SquareletError as exc:
        print(f"ERROR: MuckRock API request failed: {exc}", file=sys.stderr)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: Unexpected MuckRock API response: {exc}", file=sys.stderr)
    except (FileNotFoundError, sqlite3.Error) as exc:
        print(f"ERROR: MuckRock local index failed: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
