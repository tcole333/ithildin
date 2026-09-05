#!/usr/bin/env python3
"""Query the Supreme Court of Georgia public docket.

The official portal exposes anonymous JSON search and case-detail routes for
cases docketed in the last five years. Search results are returned as one
complete array and paginated only in the browser, so this adapter provides a
snapshot-bound local cursor. Case detail includes filing/order, judgment, and
attorney metadata. It does not expose document files; the Court directs users
to request copies of public, unsealed documents from the Clerk's Office.

Examples:
    uv run python tools/query_georgia_supreme_docket.py search S26G \
        --field case-number --output /tmp/ga-supreme-cases.json
    uv run python tools/query_georgia_supreme_docket.py search Blackwell \
        --field attorney --json
    uv run python tools/query_georgia_supreme_docket.py search 2018CV02040 \
        --field lower-court-case-number --county Clayton --json
    uv run python tools/query_georgia_supreme_docket.py detail S26G0537 --json
    uv run python tools/query_georgia_supreme_docket.py documents S26G0537 --json
    uv run python tools/query_georgia_supreme_docket.py counties --json
    uv run python tools/query_georgia_supreme_docket.py manifest --json
    uv run python tools/query_georgia_supreme_docket.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

import requests

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_court_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-ga-supreme-court-public-docket"
COURT_ID = "us-ga-supreme-court"
STATE_CODE = "GA"
STATE_GEOID = "13"

BASE_URL = "https://pubdoc.gasupreme.gov"
PORTAL_URL = f"{BASE_URL}/ui/"
API_ROOT = f"{BASE_URL}/api"
SEARCH_URL = f"{API_ROOT}/public-docket/query"
ATTORNEY_SEARCH_URL = f"{API_ROOT}/public-docket/by-attorney"
CASE_DETAIL_ROOT = f"{API_ROOT}/public-docket/case"
SYSTEM_DATA_URL = f"{API_ROOT}/system-data/two-val-const"

COURT_SITE_URL = "https://www.gasupreme.us/"
DOCKET_PAGE_URL = "https://www.gasupreme.us/docket-search/"
CLERK_URL = "https://www.gasupreme.us/court-information/clerks-office/"
OPINIONS_2026_URL = "https://www.gasupreme.us/2026-opinions/"
GRANTED_2026_URL = "https://www.gasupreme.us/2026-granted/"
DENIED_2026_URL = "https://www.gasupreme.us/2026-denied/"
DISCRETIONARY_2026_URL = "https://www.gasupreme.us/2026-discretionary/"
INTERLOCUTORY_2026_URL = "https://www.gasupreme.us/2026-interlocutory/"
CALENDAR_URL = "https://www.gasupreme.us/calendar-list/"
CASE_ANNOUNCEMENTS_2026_URL = (
    "https://www.gasupreme.us/2026-case-announcements/"
)

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_LIMIT = 100
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF = 0.5
MAXIMUM_JSON_BYTES = 24 * 1024 * 1024
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

PROBE_CASE_NUMBER = "S26G0537"
CURSOR_RE = re.compile(
    r"^ga-supreme-docket:v1:query:(?P<query>[0-9a-f]{16}):"
    r"snapshot:(?P<snapshot>[0-9a-f]{16}):offset:(?P<offset>[0-9]+)$"
)
CASE_YEAR_RE = re.compile(r"^S(?P<year>[0-9]{2})[A-Z]", re.IGNORECASE)

SEARCH_FIELDS = (
    "case-number",
    "case-style",
    "party",
    "lower-court-case-number",
    "court-of-appeals-case-number",
    "attorney",
)
SEARCH_SENTINEL_FIELDS = frozenset(
    {
        "docketDate",
        "caseType",
        "caseStyle",
        "caseNumber",
        "caseStatus",
    }
)
DETAIL_SENTINEL_FIELDS = SEARCH_SENTINEL_FIELDS | frozenset(
    {
        "description",
        "filingsAndOrders",
        "judgments",
        "attorneys",
    }
)
SYSTEM_SENTINEL_FIELDS = frozenset(
    {"id", "text_val", "other_val", "grouping", "active"}
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Supreme Court of Georgia Public Docket",
    source_role=(
        "official_recent_supreme_court_case_docket_and_filing_metadata"
    ),
    base_url=PORTAL_URL,
    dataset_id="georgia-supreme-court-public-docket",
    metadata={
        "authority": "Supreme Court of Georgia",
        "authentication": "none",
        "coverage": "cases docketed in the last 5 years",
        "native_pagination": "none_complete_json_array",
        "browser_pagination": "client_side_20_rows",
        "search_fields": list(SEARCH_FIELDS),
        "detail_sections": [
            "case_header",
            "filings_and_orders",
            "judgments",
            "attorneys",
        ],
        "document_files_exposed": False,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Georgia",
    state_code=STATE_CODE,
    metadata={"court": "Supreme Court of Georgia"},
)

SOURCE_WARNINGS = (
    "The portal states that its scope is cases docketed in the last five years; "
    "an older case missing from this source is not an authoritative absence.",
    "The API returns one complete result array. Continuation cursors are "
    "adapter-local and bound to the observed result snapshot.",
    "Filing, order, and judgment rows are metadata only. The API does not "
    "publish document URLs; unsealed public copies are requested from the Clerk.",
)


class GeorgiaSupremeDocketSelectionError(RuntimeError):
    """A caller selector cannot be represented by the verified source."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="selection",
            retryable=False,
            details=self.details,
        )


@dataclass(frozen=True)
class ParsedRecords:
    records: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class ParsedDetail:
    record: Mapping[str, Any]
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class SearchBatch:
    records: tuple[Mapping[str, Any], ...]
    source_total_count: int
    next_cursor: str | None
    source_url: str
    schema_fingerprint: str
    source_snapshot_fingerprint: str
    query_filters: tuple[tuple[str, str], ...]
    requests_made: int


def _text(value: Any) -> str | None:
    if value is None:
        return None
    clean = " ".join(str(value).replace("\x00", "").split()).strip()
    return clean or None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {0, 1}:
        return bool(value)
    return None


def _response_header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return _text(value)
    return None


def _retry_after(response: Any) -> float | None:
    value = _response_header(response, "retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _checked_status(response: Any, *, url: str) -> None:
    status_code = int(getattr(response, "status_code", 0))
    response_text = str(getattr(response, "text", ""))
    if status_code == 429:
        raise RateLimitedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code in {401, 403}:
        raise RestrictedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code == 451:
        raise TermsBlockedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code in {404, 410}:
        raise SourceChangedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code < 200 or status_code >= 300:
        raise HTTPStatusError(
            status_code,
            url=url,
            response_text=response_text,
        )


def _schema_for(
    records: Sequence[Mapping[str, Any]],
    *,
    kind: str,
    sentinel_fields: Sequence[str],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "required_fields": sorted(sentinel_fields),
        "observed": inferred_schema(records),
    }


def parse_search_payload(
    payload: Any,
    *,
    source_url: str,
) -> ParsedRecords:
    """Validate the complete-array case-search response."""

    if not isinstance(payload, list):
        raise SourceSchemaError(
            "Georgia Supreme Court docket search response is not an array",
            url=source_url,
            details={"response_type": type(payload).__name__},
        )
    records: list[Mapping[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise SourceSchemaError(
                "Georgia Supreme Court docket search row is not an object",
                url=source_url,
                details={"index": index, "row_type": type(item).__name__},
            )
        missing = sorted(SEARCH_SENTINEL_FIELDS - set(item))
        if missing:
            raise SourceSchemaError(
                "Georgia Supreme Court docket search fields changed",
                url=source_url,
                details={"index": index, "missing_fields": missing},
            )
        if not _text(item.get("caseNumber")):
            raise SourceSchemaError(
                "Georgia Supreme Court docket search row has no case number",
                url=source_url,
                details={"index": index},
            )
        records.append(dict(item))
    schema = _schema_for(
        records,
        kind="georgia_supreme_docket_search",
        sentinel_fields=SEARCH_SENTINEL_FIELDS,
    )
    return ParsedRecords(
        records=tuple(records),
        source_url=source_url,
        schema_fingerprint=schema_fingerprint(schema),
    )


def parse_detail_payload(
    payload: Any,
    *,
    requested_case_number: str,
    source_url: str,
) -> ParsedDetail:
    """Validate one exact case-detail response."""

    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "Georgia Supreme Court case detail is not an object",
            url=source_url,
            details={"response_type": type(payload).__name__},
        )
    missing = sorted(DETAIL_SENTINEL_FIELDS - set(payload))
    if missing:
        raise SourceSchemaError(
            "Georgia Supreme Court case detail fields changed",
            url=source_url,
            details={"missing_fields": missing},
        )
    observed_case_number = _text(payload.get("caseNumber"))
    if (
        observed_case_number is None
        or observed_case_number.casefold()
        != requested_case_number.strip().casefold()
    ):
        raise SourceSchemaError(
            "Georgia Supreme Court detail returned a different case",
            url=source_url,
            details={
                "requested_case_number": requested_case_number,
                "observed_case_number": observed_case_number,
            },
        )
    for field_name in ("filingsAndOrders", "judgments", "attorneys"):
        values = payload.get(field_name)
        if not isinstance(values, list) or not all(
            isinstance(item, Mapping) for item in values
        ):
            raise SourceSchemaError(
                f"Georgia Supreme Court detail {field_name} is not an object array",
                url=source_url,
            )
    record = dict(payload)
    schema = _schema_for(
        [record],
        kind="georgia_supreme_docket_detail",
        sentinel_fields=DETAIL_SENTINEL_FIELDS,
    )
    return ParsedDetail(
        record=record,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint(schema),
    )


def parse_system_data(
    payload: Any,
    *,
    source_url: str,
) -> ParsedRecords:
    """Validate the portal lookup table used for counties and party roles."""

    if not isinstance(payload, list):
        raise SourceSchemaError(
            "Georgia Supreme Court system metadata is not an array",
            url=source_url,
        )
    records: list[Mapping[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise SourceSchemaError(
                "Georgia Supreme Court system metadata row is not an object",
                url=source_url,
                details={"index": index},
            )
        missing = sorted(SYSTEM_SENTINEL_FIELDS - set(item))
        if missing:
            raise SourceSchemaError(
                "Georgia Supreme Court system metadata fields changed",
                url=source_url,
                details={"index": index, "missing_fields": missing},
            )
        records.append(dict(item))
    schema = _schema_for(
        records,
        kind="georgia_supreme_docket_system_data",
        sentinel_fields=SYSTEM_SENTINEL_FIELDS,
    )
    return ParsedRecords(
        records=tuple(records),
        source_url=source_url,
        schema_fingerprint=schema_fingerprint(schema),
    )


def _search_words(value: str) -> tuple[str, ...]:
    """Mirror the portal's comma/whitespace tokenization."""

    return tuple(
        token
        for token in re.sub(r"\s+", " ", value.replace(",", " ")).split(" ")
        if token
    )


def build_search_parameters(
    field: str,
    query: str,
    *,
    county_id: str | int | None = None,
) -> tuple[tuple[str, str], ...]:
    """Translate a semantic field to the portal's verified query grammar."""

    clean_query = _text(query)
    if clean_query is None:
        raise GeorgiaSupremeDocketSelectionError(
            "query_required",
            "Georgia Supreme Court docket search query must not be blank",
        )
    if field not in SEARCH_FIELDS:
        raise GeorgiaSupremeDocketSelectionError(
            "unsupported_search_field",
            f"unsupported Georgia Supreme Court docket search field: {field}",
            details={"supported_fields": list(SEARCH_FIELDS)},
        )
    if field != "lower-court-case-number" and county_id is not None:
        raise GeorgiaSupremeDocketSelectionError(
            "county_not_used",
            "county applies only to lower-court-case-number search",
        )
    if field == "attorney":
        return (("lastName", clean_query),)
    if field == "case-number":
        filters = [f"CaseNumber STARTS_WITH {clean_query.upper()}"]
    elif field == "case-style":
        filters = [
            f"CaseStyle CONTAINS {word}" for word in _search_words(clean_query)
        ]
    elif field == "party":
        filters = [
            f"Party CONTAINS {word}" for word in _search_words(clean_query)
        ]
    elif field == "lower-court-case-number":
        if county_id is None or _text(county_id) is None:
            raise GeorgiaSupremeDocketSelectionError(
                "county_required",
                "lower-court case-number search also requires a county",
            )
        filters = [
            f"LowerCaseNumbers CONTAINS {clean_query}",
            f"TrialCourtCounty EQUALS {_text(county_id)}",
        ]
    else:
        filters = [f"AssociatedCase EQUALS {clean_query.upper()}"]
    return tuple(("queryFilter", value) for value in filters)


def _query_fingerprint(
    field: str,
    parameters: Sequence[tuple[str, str]],
) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "source_id": SOURCE_ID,
                "field": field,
                "parameters": [list(item) for item in parameters],
            }
        ).encode("utf-8")
    ).hexdigest()[:16]


def _snapshot_fingerprint(
    records: Sequence[Mapping[str, Any]],
) -> str:
    return hashlib.sha256(canonical_json(list(records)).encode("utf-8")).hexdigest()[
        :16
    ]


def _cursor(
    *,
    query_fingerprint: str,
    snapshot_fingerprint: str,
    offset: int,
) -> str:
    return (
        "ga-supreme-docket:v1:"
        f"query:{query_fingerprint}:snapshot:{snapshot_fingerprint}:"
        f"offset:{offset}"
    )


def _cursor_offset(
    cursor: str | None,
    *,
    query_fingerprint: str,
    snapshot_fingerprint: str,
    record_count: int,
) -> int:
    if cursor is None:
        return 0
    match = CURSOR_RE.fullmatch(cursor.strip())
    if match is None:
        raise GeorgiaSupremeDocketSelectionError(
            "invalid_cursor",
            "Georgia Supreme Court docket cursor is invalid",
        )
    if match.group("query") != query_fingerprint:
        raise GeorgiaSupremeDocketSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to a different Georgia Supreme Court docket search",
        )
    if match.group("snapshot") != snapshot_fingerprint:
        raise GeorgiaSupremeDocketSelectionError(
            "cursor_snapshot_changed",
            "Georgia Supreme Court search results changed since this cursor was issued",
            details={
                "cursor_snapshot": match.group("snapshot"),
                "observed_snapshot": snapshot_fingerprint,
            },
        )
    offset = int(match.group("offset"))
    if offset > record_count:
        raise GeorgiaSupremeDocketSelectionError(
            "cursor_out_of_range",
            "cursor points beyond the Georgia Supreme Court result array",
            details={"offset": offset, "record_count": record_count},
        )
    return offset


class GeorgiaSupremeDocketClient:
    """Paced, retrying client for the verified public JSON routes."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            backoff_initial=DEFAULT_RETRY_BACKOFF,
        )
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper
        self.request_count = 0
        self.headers = {
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request_json(
        self,
        url: str,
        *,
        parameters: Sequence[tuple[str, str]] = (),
        allow_not_found: bool = False,
    ) -> tuple[Any | None, str]:
        response: Any | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    "GET",
                    url,
                    params=list(parameters),
                    headers=self.headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        "Georgia Supreme Court docket request failed",
                        url=url,
                        details={"error": str(error), "attempts": attempt},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            source_url = str(getattr(response, "url", url))
            status_code = int(getattr(response, "status_code", 0))
            if allow_not_found and status_code == 404:
                return None, source_url
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(
                    self.retry_policy.delay(attempt, _retry_after(response))
                )
                continue
            _checked_status(response, url=source_url)
            content = getattr(response, "content", None)
            if content is None:
                content = str(getattr(response, "text", "")).encode("utf-8")
            if len(content) > MAXIMUM_JSON_BYTES:
                raise SourceSchemaError(
                    "Georgia Supreme Court docket response exceeded the JSON bound",
                    url=source_url,
                    details={
                        "response_bytes": len(content),
                        "maximum_bytes": MAXIMUM_JSON_BYTES,
                    },
                )
            try:
                return response.json(), source_url
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise SourceSchemaError(
                    "Georgia Supreme Court docket returned invalid JSON",
                    url=source_url,
                ) from error
        raise TransportError(
            "Georgia Supreme Court docket request produced no response",
            url=url,
        )

    def system_data(self) -> ParsedRecords:
        payload, source_url = self._request_json(SYSTEM_DATA_URL)
        return parse_system_data(payload, source_url=source_url)

    def counties(self) -> tuple[Mapping[str, Any], ...]:
        parsed = self.system_data()
        counties = [
            {
                "county_id": str(item["id"]),
                "name": _text(item["text_val"]),
                "county_code": _text(item["other_val"]),
                "active": _bool_or_none(item["active"]),
            }
            for item in parsed.records
            if item.get("grouping") == 1
        ]
        counties.sort(key=lambda item: (str(item["name"]), item["county_id"]))
        return tuple(counties)

    def party_type_lookup(self) -> tuple[dict[str, str], str]:
        parsed = self.system_data()
        lookup = {
            str(item["id"]): str(_text(item["text_val"]))
            for item in parsed.records
            if item.get("grouping") == 6 and _text(item.get("text_val"))
        }
        return lookup, parsed.source_url

    def resolve_county(self, name: str) -> tuple[str, str]:
        clean_name = _text(name)
        if clean_name is None:
            raise GeorgiaSupremeDocketSelectionError(
                "county_required",
                "county name must not be blank",
            )
        matches = [
            item
            for item in self.counties()
            if str(item["name"]).casefold() == clean_name.casefold()
        ]
        if len(matches) != 1:
            raise GeorgiaSupremeDocketSelectionError(
                "county_not_found",
                f"Georgia county was not found in the portal lookup: {clean_name}",
            )
        return str(matches[0]["county_id"]), SYSTEM_DATA_URL

    def search(
        self,
        field: str,
        query: str,
        *,
        county_id: str | int | None = None,
        limit: int | None = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> SearchBatch:
        if limit is not None and limit <= 0:
            raise GeorgiaSupremeDocketSelectionError(
                "invalid_limit",
                "search limit must be positive",
            )
        parameters = build_search_parameters(
            field,
            query,
            county_id=county_id,
        )
        url = ATTORNEY_SEARCH_URL if field == "attorney" else SEARCH_URL
        before_requests = self.request_count
        payload, source_url = self._request_json(
            url,
            parameters=parameters,
        )
        parsed = parse_search_payload(payload, source_url=source_url)
        query_fingerprint = _query_fingerprint(field, parameters)
        snapshot_fingerprint = _snapshot_fingerprint(parsed.records)
        offset = _cursor_offset(
            cursor,
            query_fingerprint=query_fingerprint,
            snapshot_fingerprint=snapshot_fingerprint,
            record_count=len(parsed.records),
        )
        end = len(parsed.records) if limit is None else min(
            len(parsed.records),
            offset + limit,
        )
        next_cursor = (
            _cursor(
                query_fingerprint=query_fingerprint,
                snapshot_fingerprint=snapshot_fingerprint,
                offset=end,
            )
            if end < len(parsed.records)
            else None
        )
        return SearchBatch(
            records=tuple(parsed.records[offset:end]),
            source_total_count=len(parsed.records),
            next_cursor=next_cursor,
            source_url=parsed.source_url,
            schema_fingerprint=parsed.schema_fingerprint,
            source_snapshot_fingerprint=snapshot_fingerprint,
            query_filters=parameters,
            requests_made=self.request_count - before_requests,
        )

    def detail(self, case_number: str) -> ParsedDetail | None:
        clean_case_number = _text(case_number)
        if clean_case_number is None:
            raise GeorgiaSupremeDocketSelectionError(
                "case_number_required",
                "Georgia Supreme Court case number must not be blank",
            )
        url = f"{CASE_DETAIL_ROOT}/{quote(clean_case_number.upper(), safe='')}"
        payload, source_url = self._request_json(
            url,
            allow_not_found=True,
        )
        if payload is None:
            return None
        return parse_detail_payload(
            payload,
            requested_case_number=clean_case_number,
            source_url=source_url,
        )


def split_lower_court_case_numbers(value: Any) -> list[str]:
    clean = _text(value)
    if clean is None:
        return []
    return [
        part
        for part in (_text(item) for item in re.split(r"[,;\n]+", clean))
        if part is not None
    ]


def _case_year(case_number: str) -> int | None:
    match = CASE_YEAR_RE.match(case_number)
    return 2000 + int(match.group("year")) if match else None


def adjacent_routes_for_case(case_number: str) -> list[dict[str, Any]]:
    year = _case_year(case_number)
    if year is None:
        return []
    return [
        {
            "source_role": "published_opinions_and_summaries",
            "url": f"https://www.gasupreme.us/{year}-opinions/",
            "lookup_key": case_number,
            "coverage_difference": (
                "full opinion PDFs for decided cases; not a complete docket"
            ),
        },
        {
            "source_role": "certiorari_granted",
            "url": f"https://www.gasupreme.us/{year}-granted/",
            "lookup_key": case_number,
            "coverage_difference": (
                "decision list and Court of Appeals case pivots; no filing history"
            ),
        },
        {
            "source_role": "certiorari_denied",
            "url": f"https://www.gasupreme.us/{year}-denied/",
            "lookup_key": case_number,
            "coverage_difference": (
                "decision list and Court of Appeals case pivots; no filing history"
            ),
        },
        {
            "source_role": "discretionary_applications_granted",
            "url": f"https://www.gasupreme.us/{year}-discretionary/",
            "lookup_key": case_number,
            "coverage_difference": "grant orders only; not all applications",
        },
        {
            "source_role": "interlocutory_applications_granted",
            "url": f"https://www.gasupreme.us/{year}-interlocutory/",
            "lookup_key": case_number,
            "coverage_difference": "grant orders only; not all applications",
        },
    ]


def document_request_handoff(case_number: str) -> dict[str, Any]:
    """Return the Court's public-document copy route without submitting it."""

    return {
        "case_number": case_number,
        "access_mode": "request_from_clerk",
        "availability_scope": "public documents not under seal",
        "document_urls_in_api": False,
        "request_submitted": False,
        "phone": "+1-404-656-3470",
        "phone_display": "(404) 656-3470",
        "fee_may_apply": True,
        "email_inquiries_accepted": False,
        "clerk_url": CLERK_URL,
        "docket_page_url": DOCKET_PAGE_URL,
        "request_prep": (
            "Use the case number plus filing type and filing date from the "
            "docket metadata to identify the requested item."
        ),
    }


def _normalize_filing(
    raw: Mapping[str, Any],
    *,
    case_number: str,
    sequence: int,
) -> dict[str, Any]:
    stable_payload = {
        "case_number": case_number,
        "filing_type": _text(raw.get("filingType")),
        "filed_at": _text(raw.get("filingDateTime")),
        "order_type": _text(raw.get("orderType") or raw.get("order")),
        "order_date": _text(raw.get("orderDate")),
        "docketed_in_error": _bool_or_none(raw.get("docketedInError")),
    }
    event_id = sha256_fingerprint(stable_payload)[:20]
    return {
        "event_id": f"ga-supreme-docket-event:{event_id}",
        "sequence": sequence,
        **stable_payload,
        "document_url": None,
        "document_access": "request_from_clerk",
        "raw_source": dict(raw),
    }


def _normalize_judgment(
    raw: Mapping[str, Any],
    *,
    sequence: int,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "judgment": _text(raw.get("judgment")),
        "judgment_line": _text(raw.get("judgmentLine")),
        "judgment_date": _text(raw.get("judgmentDate")),
        "raw_source": dict(raw),
    }


def _normalize_attorney(raw: Mapping[str, Any]) -> dict[str, Any]:
    name_parts = [
        _text(raw.get("firstName")),
        _text(raw.get("middleName")),
        _text(raw.get("lastName")),
        _text(raw.get("suffix")),
    ]
    return {
        "display_name": " ".join(part for part in name_parts if part),
        "first_name": _text(raw.get("firstName")),
        "middle_name": _text(raw.get("middleName")),
        "last_name": _text(raw.get("lastName")),
        "suffix": _text(raw.get("suffix")),
        "title": _text(raw.get("title")),
        "firm": _text(raw.get("firm")),
        "address": {
            "line_1": _text(raw.get("streetAddress1")),
            "line_2": _text(raw.get("streetAddress2")),
            "city": _text(raw.get("city")),
            "state": _text(raw.get("state")),
            "postal_code": _text(raw.get("zip")),
        },
        "phone": _text(raw.get("phone")),
        "party_type": _text(raw.get("partyType")),
        "raw_source": dict(raw),
    }


def normalize_search_record(
    raw: Mapping[str, Any],
    *,
    field: str,
    query: str,
    party_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    case_number = str(_text(raw.get("caseNumber")))
    attorney_match = None
    if field == "attorney":
        party_type_id = _text(raw.get("partyType"))
        attorney_match = {
            "first_name": _text(raw.get("firstName")),
            "last_name": _text(raw.get("lastName")),
            "party_type_native_id": party_type_id,
            "party_type": (
                party_types.get(party_type_id)
                if party_types is not None and party_type_id is not None
                else None
            ),
        }
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
            "case",
        ),
        "source_id": SOURCE_ID,
        "court": {
            "court_id": COURT_ID,
            "name": "Supreme Court of Georgia",
            "court_level": "supreme",
        },
        "record_kind": "supreme_court_case_index",
        "case_number": case_number,
        "case_style": _text(raw.get("caseStyle")),
        "case_status": _text(raw.get("caseStatus")),
        "case_type_code": _text(raw.get("caseType")),
        "docket_date": _text(raw.get("docketDate")),
        "lower_court_case_numbers": split_lower_court_case_numbers(
            raw.get("lowerCourtCaseNumbers")
        ),
        "attorney_search_match": attorney_match,
        "query_match": {"field": field, "query": query},
        "source_scope": {"docketed_within_last_years": 5},
        "detail_api_url": (
            f"{CASE_DETAIL_ROOT}/{quote(case_number, safe='')}"
        ),
        "portal_url": PORTAL_URL,
        "adjacent_official_routes": adjacent_routes_for_case(case_number),
        "raw_source": dict(raw),
    }


def normalize_detail_record(detail: ParsedDetail) -> dict[str, Any]:
    raw = detail.record
    case_number = str(_text(raw.get("caseNumber")))
    filings = [
        _normalize_filing(item, case_number=case_number, sequence=index)
        for index, item in enumerate(raw["filingsAndOrders"], start=1)
    ]
    judgments = [
        _normalize_judgment(item, sequence=index)
        for index, item in enumerate(raw["judgments"], start=1)
    ]
    attorneys = [_normalize_attorney(item) for item in raw["attorneys"]]
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
            "case_detail",
        ),
        "source_id": SOURCE_ID,
        "court": {
            "court_id": COURT_ID,
            "name": "Supreme Court of Georgia",
            "court_level": "supreme",
        },
        "record_kind": "supreme_court_case_detail",
        "case_number": case_number,
        "case_style": _text(raw.get("caseStyle")),
        "case_status": _text(raw.get("caseStatus")),
        "case_type_code": _text(raw.get("caseType")),
        "description": _text(raw.get("description")),
        "docket_date": _text(raw.get("docketDate")),
        "lower_court_case_numbers": split_lower_court_case_numbers(
            raw.get("lowerCourtCaseNumbers")
        ),
        "county": _text(raw.get("county")),
        "calendar": {
            "is_calendar_case": _bool_or_none(raw.get("calendarCase")),
            "calendar": _text(raw.get("docketCalendar")),
            "argument_date": _text(raw.get("argumentDate")),
            "argument_date_is_provisional": bool(raw.get("argumentDate")),
        },
        "docket_entries": filings,
        "judgments": judgments,
        "attorneys": attorneys,
        "document_inventory": {
            "state": "metadata_only",
            "public_document_urls": [],
            "filing_metadata_count": len(filings),
            "request_handoff": document_request_handoff(case_number),
        },
        "source_scope": {"docketed_within_last_years": 5},
        "source_url": detail.source_url,
        "source_schema_fingerprint": detail.schema_fingerprint,
        "adjacent_official_routes": adjacent_routes_for_case(case_number),
        "raw_source": dict(raw),
    }


def normalize_document_handoff(detail: ParsedDetail) -> dict[str, Any]:
    case = normalize_detail_record(detail)
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case["case_number"],
            "document_request_handoff",
        ),
        "source_id": SOURCE_ID,
        "record_kind": "document_request_handoff",
        "case_number": case["case_number"],
        "case_style": case["case_style"],
        "document_inventory_state": "metadata_only_no_public_file_urls",
        "filing_candidates": case["docket_entries"],
        "judgment_metadata": case["judgments"],
        "request_handoff": document_request_handoff(case["case_number"]),
        "source_url": detail.source_url,
    }


def source_manifest() -> dict[str, Any]:
    return {
        "canonical_ref": f"STATECOURT:{SOURCE_ID}/manifest",
        "source_id": SOURCE_ID,
        "record_kind": "source_manifest",
        "source": SOURCE_METADATA.to_dict(),
        "scope": {
            "case_window": "cases docketed in the last 5 years",
            "historical_completeness": False,
        },
        "verified_endpoints": {
            "case_search": SEARCH_URL,
            "attorney_search": ATTORNEY_SEARCH_URL,
            "case_detail_template": f"{CASE_DETAIL_ROOT}/{{case_number}}",
            "system_lookup": SYSTEM_DATA_URL,
        },
        "search_modes": {
            "case-number": "CaseNumber STARTS_WITH",
            "case-style": "one CaseStyle CONTAINS filter per token",
            "party": "one Party CONTAINS filter per token",
            "lower-court-case-number": (
                "LowerCaseNumbers CONTAINS plus TrialCourtCounty EQUALS"
            ),
            "court-of-appeals-case-number": "AssociatedCase EQUALS",
            "attorney": "separate by-attorney route using lastName",
        },
        "pagination": {
            "native_api": "none",
            "response_shape": "complete JSON array",
            "portal_table": "client-side paginator with 20 rows",
            "adapter": "snapshot-bound local offset cursor",
        },
        "detail_fields": [
            "case metadata",
            "lower-court case numbers",
            "calendar metadata",
            "filings and orders",
            "judgments",
            "attorney names and contact metadata",
        ],
        "document_access": {
            "api_file_urls": False,
            "handoff": document_request_handoff("{case_number}"),
        },
        "adjacent_official_sources": [
            {
                "name": "Supreme Court opinions and summaries",
                "url": OPINIONS_2026_URL,
                "url_pattern": "https://www.gasupreme.us/{year}-opinions/",
                "adds": "opinion PDFs, decision and argument dates",
                "gap": "decided opinion cases only",
            },
            {
                "name": "Certiorari granted and denied lists",
                "urls": [GRANTED_2026_URL, DENIED_2026_URL],
                "adds": "disposition dates and Court of Appeals case pivots",
                "gap": "not a filing-level docket",
            },
            {
                "name": "Discretionary applications granted",
                "url": DISCRETIONARY_2026_URL,
                "adds": "public grant-order PDFs",
                "gap": "grants only",
            },
            {
                "name": "Interlocutory applications granted",
                "url": INTERLOCUTORY_2026_URL,
                "adds": "public grant-order PDFs",
                "gap": "grants only",
            },
            {
                "name": "Oral argument calendar",
                "url": CALENDAR_URL,
                "adds": "argument schedule and related-case groupings",
                "gap": "calendared cases only",
            },
            {
                "name": "Case announcements",
                "url": CASE_ANNOUNCEMENTS_2026_URL,
                "adds": "official announcement documents",
                "gap": "announcement subset rather than complete docket",
            },
        ],
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters = {
            "field": args.field,
            "query": args.query,
            "county_id": args.county_id,
            "county": args.county,
        }
        requested_limit = None if args.all else args.limit
        cursor = args.cursor
    elif args.command in {"detail", "documents"}:
        parameters = {"case_number": args.case_number}
    elif args.command == "probe":
        parameters = {"case_number": args.case_number}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata={
                "source_scope": "cases docketed in the last 5 years",
            },
        ),
    )


def _search_result(
    args: argparse.Namespace,
    client: GeorgiaSupremeDocketClient,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.county is not None and args.county_id is not None:
        raise GeorgiaSupremeDocketSelectionError(
            "conflicting_county_selectors",
            "pass either --county or --county-id, not both",
        )
    county_id = args.county_id
    raw_refs: list[str] = []
    if args.county is not None:
        county_id, lookup_url = client.resolve_county(args.county)
        raw_refs.append(lookup_url)
    batch = client.search(
        args.field,
        args.query,
        county_id=county_id,
        limit=None if args.all else args.limit,
        cursor=args.cursor,
    )
    party_types: dict[str, str] | None = None
    if args.field == "attorney":
        party_types, lookup_url = client.party_type_lookup()
        raw_refs.append(lookup_url)
    records = [
        normalize_search_record(
            item,
            field=args.field,
            query=args.query,
            party_types=party_types,
        )
        for item in batch.records
    ]
    for record in records:
        record["retrieval"] = {
            "source_total_count": batch.source_total_count,
            "returned_count": len(records),
            "source_snapshot_fingerprint": (
                batch.source_snapshot_fingerprint
            ),
            "source_schema_fingerprint": batch.schema_fingerprint,
            "query_filters": [list(item) for item in batch.query_filters],
            "native_pagination": False,
        }
    raw_refs.append(batch.source_url)
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        raw_artifact_refs=tuple(dict.fromkeys(raw_refs)),
        warnings=SOURCE_WARNINGS,
    )


def _detail_result(
    client: GeorgiaSupremeDocketClient,
    query: PublicRecordsQuery,
    *,
    case_number: str,
) -> PublicRecordsResult:
    detail = client.detail(case_number)
    return PublicRecordsResult.success(
        query,
        [normalize_detail_record(detail)] if detail is not None else [],
        raw_artifact_refs=([detail.source_url] if detail is not None else []),
        warnings=SOURCE_WARNINGS,
    )


def _documents_result(
    client: GeorgiaSupremeDocketClient,
    query: PublicRecordsQuery,
    *,
    case_number: str,
) -> PublicRecordsResult:
    detail = client.detail(case_number)
    return PublicRecordsResult.success(
        query,
        [normalize_document_handoff(detail)] if detail is not None else [],
        raw_artifact_refs=(
            [detail.source_url, CLERK_URL] if detail is not None else []
        ),
        warnings=SOURCE_WARNINGS,
    )


def _counties_result(
    client: GeorgiaSupremeDocketClient,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    records = [
        {
            "canonical_ref": (
                f"STATECOURT:{SOURCE_ID}/county/{item['county_id']}"
            ),
            "source_id": SOURCE_ID,
            "record_kind": "county_lookup",
            **item,
        }
        for item in client.counties()
    ]
    return PublicRecordsResult.success(
        query,
        records,
        raw_artifact_refs=[SYSTEM_DATA_URL],
        warnings=SOURCE_WARNINGS,
    )


def _probe_result(
    client: GeorgiaSupremeDocketClient,
    query: PublicRecordsQuery,
    *,
    case_number: str,
) -> PublicRecordsResult:
    before_requests = client.request_count
    batch = client.search(
        "case-number",
        case_number,
        limit=25,
    )
    exact = [
        item
        for item in batch.records
        if str(item.get("caseNumber", "")).casefold()
        == case_number.casefold()
    ]
    if len(exact) != 1:
        raise SourceSchemaError(
            "Georgia Supreme Court probe did not return its exact case once",
            url=batch.source_url,
            details={
                "case_number": case_number,
                "exact_match_count": len(exact),
            },
        )
    detail = client.detail(case_number)
    if detail is None:
        raise SourceSchemaError(
            "Georgia Supreme Court probe case detail disappeared",
            url=f"{CASE_DETAIL_ROOT}/{case_number}",
        )
    normalized = normalize_detail_record(detail)
    requests_made = client.request_count - before_requests
    probe = {
        "canonical_ref": f"STATECOURT:{SOURCE_ID}/probe",
        "source_id": SOURCE_ID,
        "record_kind": "source_probe",
        "source_url": PORTAL_URL,
        "stable_contract": {
            "search_endpoint": SEARCH_URL,
            "detail_endpoint": f"{CASE_DETAIL_ROOT}/{{case_number}}",
            "search_response": "complete JSON array",
            "case_detail_sections": [
                "filingsAndOrders",
                "judgments",
                "attorneys",
            ],
            "document_access": "Clerk request handoff",
        },
        "rolling_observation": {
            "case_number": case_number,
            "case_style": normalized["case_style"],
            "case_status": normalized["case_status"],
            "filing_metadata_count": len(normalized["docket_entries"]),
            "judgment_count": len(normalized["judgments"]),
            "attorney_count": len(normalized["attorneys"]),
        },
        "schema_contract": {
            "search": batch.schema_fingerprint,
            "detail": detail.schema_fingerprint,
        },
        "requests_made": requests_made,
    }
    return PublicRecordsResult.success(
        query,
        [probe],
        raw_artifact_refs=[batch.source_url, detail.source_url],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: GeorgiaSupremeDocketClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one isolated public-docket operation."""

    query = build_query(args)
    source_client = client
    owns_client = False
    try:
        if args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [source_manifest()],
                warnings=SOURCE_WARNINGS,
            )
        else:
            if source_client is None:
                source_client = GeorgiaSupremeDocketClient(
                    timeout=args.timeout,
                    minimum_interval=args.minimum_interval,
                    retry_policy=RetryPolicy(
                        max_attempts=args.max_attempts,
                        backoff_initial=args.retry_backoff,
                    ),
                )
                owns_client = True
            if args.command == "search":
                result = _search_result(args, source_client, query)
            elif args.command == "detail":
                result = _detail_result(
                    source_client,
                    query,
                    case_number=args.case_number,
                )
            elif args.command == "documents":
                result = _documents_result(
                    source_client,
                    query,
                    case_number=args.case_number,
                )
            elif args.command == "counties":
                result = _counties_result(source_client, query)
            elif args.command == "probe":
                result = _probe_result(
                    source_client,
                    query,
                    case_number=args.case_number,
                )
            else:
                raise ValueError(
                    f"unsupported Georgia Supreme Court command: {args.command}"
                )
    except GeorgiaSupremeDocketSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client and source_client is not None:
            source_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Georgia Supreme Court docket {args.command}",
        result_count=(
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        ),
    ):
        return
    print(
        f"Georgia Supreme Court docket {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            "  "
            + str(
                record.get("case_number")
                or record.get("record_kind")
                or "record"
            )
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--retry-backoff",
        type=_nonnegative_float,
        default=DEFAULT_RETRY_BACKOFF,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the Supreme Court of Georgia public docket",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser(
        "manifest",
        help="Describe verified routes, scope, and adjacent official sources",
    )
    add_output_args(manifest)

    search = subparsers.add_parser(
        "search",
        help="Search recent Supreme Court dockets",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=SEARCH_FIELDS,
        default="case-number",
    )
    county_group = search.add_mutually_exclusive_group()
    county_group.add_argument(
        "--county",
        help="Georgia county name for lower-court case-number search",
    )
    county_group.add_argument(
        "--county-id",
        help="Native county ID from the counties command",
    )
    limit_group = search.add_mutually_exclusive_group()
    limit_group.add_argument(
        "--limit",
        type=_positive_int,
        default=DEFAULT_LIMIT,
        help="Maximum records returned from the complete source array",
    )
    limit_group.add_argument(
        "--all",
        action="store_true",
        help="Return the complete source array",
    )
    search.add_argument(
        "--cursor",
        help="Snapshot-bound continuation cursor from a prior matching search",
    )
    _add_runtime_and_output(search)

    detail = subparsers.add_parser(
        "detail",
        help="Read one exact recent case docket",
    )
    detail.add_argument("case_number")
    _add_runtime_and_output(detail)

    documents = subparsers.add_parser(
        "documents",
        help="List filing metadata and prepare the Clerk copy-request handoff",
    )
    documents.add_argument("case_number")
    _add_runtime_and_output(documents)

    counties = subparsers.add_parser(
        "counties",
        help="List native county selectors used by lower-court searches",
    )
    _add_runtime_and_output(counties)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded exact search-plus-detail source check",
    )
    probe.add_argument(
        "--case-number",
        default=PROBE_CASE_NUMBER,
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
