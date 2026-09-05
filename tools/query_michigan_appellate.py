#!/usr/bin/env python3
"""Query Michigan's official appellate cases, opinions, and orders portal.

The Michigan Judiciary publishes three independently paginated result sets
behind its Cases, Opinions & Orders page.  This adapter keeps those roles
distinct, preserves the source record, and exposes the appellate docket,
lower-court label, attorney P-number, case route, and document URL needed for
cross-source joins.

Examples:
    uv run python tools/query_michigan_appellate.py search Epstein \
        --result-type cases --limit 50 --output /tmp/mi-cases.json
    uv run python tools/query_michigan_appellate.py search insurance \
        --result-type opinions --resource opinion --limit 100 \
        --output /tmp/mi-opinions.json
    uv run python tools/query_michigan_appellate.py search \
        --result-type cases --party-name "Jordan Epstein" \
        --output /tmp/mi-party-cases.json
    uv run python tools/query_michigan_appellate.py overview Epstein --json
    uv run python tools/query_michigan_appellate.py routes --json
    uv run python tools/query_michigan_appellate.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urljoin, urlparse

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
        MinimumIntervalRateLimiter,
        RetryPolicy,
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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-mi-appellate-case-opinion-order-search"
STATE_CODE = "MI"
STATE_GEOID = "26"

BASE_URL = "https://www.courts.michigan.gov"
SEARCH_PAGE_URL = f"{BASE_URL}/case-search/"
PAGE_MODEL_URL = SEARCH_PAGE_URL
API_ROOT = f"{BASE_URL}/api/CaseSearch"
SEARCH_ENDPOINTS = {
    "cases": f"{API_ROOT}/SearchCaseDetails",
    "opinions": f"{API_ROOT}/SearchCaseOpinions",
    "orders": f"{API_ROOT}/SearchCaseOrders",
}
OVERVIEW_URL = f"{API_ROOT}/SearchCaseSearchContent"

MICOURT_SEARCH_URL = "https://micourt.courts.michigan.gov/case-search/court-selection"
MICOURT_DEVELOPER_URL = (
    "https://developer.micourt.courts.michigan.gov/docs/case-search-api-reference-v4"
)
BUSINESS_COURT_URL = f"{BASE_URL}/business-court-search/"
TRIAL_COURT_DIRECTORY_URL = f"{BASE_URL}/courts/trial-courts/"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_PAGE_SIZE = 100
DEFAULT_LIMIT = 100
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_JSON_BYTES = 24 * 1024 * 1024
DEFAULT_MAX_PDF_BYTES = 256 * 1024 * 1024
DEFAULT_USER_AGENT = "IthildinOSINT/1.0 Michigan official appellate records client"

PROBE_QUERY = "insurance"
PROBE_DOCUMENT_URL = (
    f"{BASE_URL}/49d5f5/siteassets/case-documents/uploads/"
    "coa/public/orders/2022/360440_6_01.pdf"
)

CURSOR_RE = re.compile(
    r"^mi-appellate:v1:(?P<kind>cases|opinions|orders):"
    r"page:(?P<page>\d+):offset:(?P<offset>\d+):"
    r"query:(?P<fingerprint>[0-9a-f]{16})$"
)
CASE_ROUTE_RE = re.compile(
    r"/c/courts/(?P<court>coa|msc|coc)/case/(?P<case_id>[^/?#]+)",
    re.IGNORECASE,
)

COURTS = {
    "coa": {
        "court_id": "us-mi-court-of-appeals",
        "native_court_id": "coa",
        "name": "Michigan Court of Appeals",
        "court_level": "appellate",
    },
    "msc": {
        "court_id": "us-mi-supreme-court",
        "native_court_id": "msc",
        "name": "Michigan Supreme Court",
        "court_level": "supreme",
    },
    "coc": {
        "court_id": "us-mi-court-of-claims",
        "native_court_id": "coc",
        "name": "Michigan Court of Claims",
        "court_level": "trial_specialty",
    },
}
UNKNOWN_COURT = {
    "court_id": "us-mi-appellate-courts",
    "native_court_id": "unknown",
    "name": "Michigan appellate courts",
    "court_level": "appellate",
}

RESULT_KINDS = {
    "cases": "appellate_case_index",
    "opinions": "appellate_opinion",
    "orders": "appellate_order",
}

ADVANCED_PARAMETERS = {
    "appellate_court": "aAppellateCourt",
    "attorney_name": "aAttorneyName",
    "bar_number": "aBarNumber",
    "case_id": "aCaseId",
    "case_type": "aCaseType",
    "lower_court": "aLowerCourt",
    "open_status": "aOpenStatus",
    "party_name": "aPartyName",
    "author_name": "aAuthorName",
    "panel_member": "aPanelMember",
}
FACET_PARAMETERS = {
    "courts": "court",
    "court_types": "courtType",
    "judges": "judge",
    "filing_dates": "filingDate",
    "resources": "resource",
    "release_dates": "releaseDate",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Michigan Judiciary Cases, Opinions & Orders",
    source_role="official_statewide_appellate_case_opinion_and_order_search",
    base_url=SEARCH_PAGE_URL,
    dataset_id="michigan-judiciary-case-search",
    metadata={
        "authority": "Michigan Judiciary",
        "state_code": STATE_CODE,
        "authentication": "none",
        "result_types": list(SEARCH_ENDPOINTS),
        "native_pagination": "one_based_page",
        "page_size_options": [10, 25, 50, 100],
        "stable_join_keys": [
            "appellate_case_number",
            "coa_case_number",
            "msc_case_number",
            "court_of_claims_case_number",
            "lower_court",
            "attorney_p_number",
            "native_document_id",
        ],
        "complements": [
            "MiCOURT participating trial-court case search",
            "Michigan Business Court Search",
            "Michigan trial-court clerks",
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Michigan",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "This portal is the statewide appellate index; use the originating court "
    "and lower-court case number to pivot into trial-court records.",
    "Case search rows may summarize parties; the official case route and "
    "document PDFs remain separately linked.",
)


class MichiganAppellateError(RuntimeError):
    """Source error carrying public-record result semantics."""

    code = "michigan_appellate_error"
    status = ResultStatus.UNAVAILABLE
    category = "source"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        details = dict(self.details)
        if self.url:
            details["url"] = self.url
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=details,
        )


class MichiganSelectionError(MichiganAppellateError):
    code = "invalid_selection"
    category = "query"


class MichiganTransportError(MichiganAppellateError):
    code = "transport_error"
    category = "transport"
    retryable = True


class MichiganRateLimitedError(MichiganAppellateError):
    code = "rate_limited"
    status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True


class MichiganRestrictedError(MichiganAppellateError):
    code = "access_restricted"
    status = ResultStatus.RESTRICTED
    category = "access"


class MichiganHTTPError(MichiganAppellateError):
    code = "http_status"
    category = "http"


class MichiganSourceChangedError(MichiganAppellateError):
    code = "source_changed"
    status = ResultStatus.SOURCE_CHANGED
    category = "source_schema"


@dataclass(frozen=True)
class MichiganSearchPage:
    result_type: str
    records: tuple[Mapping[str, Any], ...]
    current_page: int
    page_size: int
    result_count: int
    total_pages: int
    total_results: int
    selected_sort_option: str | None
    sort_by_options: tuple[str, ...]
    facets: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str

    @property
    def next_page(self) -> int | None:
        if self.current_page < self.total_pages:
            return self.current_page + 1
        return None


@dataclass(frozen=True)
class MichiganSearchCollection:
    records: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    total_results: int
    next_page: int | None
    next_offset: int
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: MichiganAppellateError | None = None


@dataclass(frozen=True)
class MichiganDocument:
    source_url: str
    content: bytes
    media_type: str
    filename: str
    sha256: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise MichiganSourceChangedError(f"{field_name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise MichiganSourceChangedError(f"{field_name} must be an integer") from error


def _date(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", normalized)
    return match.group(1) if match else normalized


def _absolute_url(value: Any) -> str | None:
    normalized = _text(value)
    return urljoin(BASE_URL, normalized) if normalized else None


def _unique_text(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _text(value)
        if normalized is None or normalized in seen or normalized == "0":
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _official_url(value: str) -> str:
    absolute = urljoin(BASE_URL, value)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.hostname != "www.courts.michigan.gov":
        raise MichiganSelectionError(
            "document URL must be on the official Michigan Judiciary host",
            details={"document_url": value},
        )
    return absolute


def _court_for_item(item: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    case_url = _text(item.get("caseUrl")) or ""
    route = CASE_ROUTE_RE.search(case_url)
    if route:
        code = route.group("court").lower()
        return code, COURTS[code]
    if item.get("isSupremeCourtCase") or item.get("isSupremeCourtDocument"):
        return "msc", COURTS["msc"]
    if item.get("isCourtOfClaimsCase") or item.get("isCourtOfClaimsDocument"):
        return "coc", COURTS["coc"]
    if item.get("isCourtOfAppealsCase") or item.get("isCourtOfAppealsDocument"):
        return "coa", COURTS["coa"]
    return "unknown", UNKNOWN_COURT


def _case_numbers(item: Mapping[str, Any]) -> dict[str, str | None]:
    coa = _text(item.get("courtOfAppealsCaseNumber") or item.get("coaCaseId"))
    msc = _text(item.get("supremeCourtCaseNumber") or item.get("mscCaseId"))
    coc = _text(item.get("courtOfClaimsCaseNumber") or item.get("cocCaseId"))
    if msc == "0":
        msc = None
    route = CASE_ROUTE_RE.search(_text(item.get("caseUrl")) or "")
    route_id = unquote(route.group("case_id")) if route else None
    route_code = route.group("court").lower() if route else None
    if route_code == "coa" and coa is None:
        coa = route_id
    elif route_code == "msc" and msc is None:
        msc = route_id
    elif route_code == "coc" and coc is None:
        coc = route_id
    return {"coa": coa, "msc": msc, "coc": coc}


def _primary_case_number(
    item: Mapping[str, Any],
    court_code: str,
) -> tuple[str, bool]:
    numbers = _case_numbers(item)
    native = numbers.get(court_code)
    if native:
        return native, True
    candidates = _unique_text([numbers["coa"], numbers["msc"], numbers["coc"]])
    if candidates:
        return candidates[0], True
    title = _text(item.get("title")) or ""
    title_match = re.search(r"\b(?:COA|MSC|COC)\s+(\d{4,})\b", title)
    if title_match:
        return title_match.group(1), True
    fallback = sha256_fingerprint(dict(item))[:16]
    return f"unresolved-{fallback}", False


def _native_document_id(document_url: str | None) -> str | None:
    if not document_url:
        return None
    filename = Path(unquote(urlparse(document_url).path)).name
    return filename or sha256_fingerprint(document_url)[:16]


def _document_type(result_type: str, court_code: str) -> str | None:
    if result_type == "cases":
        return None
    court_prefix = {
        "coa": "court_of_appeals",
        "msc": "supreme_court",
        "coc": "court_of_claims",
    }.get(court_code, "appellate")
    singular = result_type.removesuffix("s")
    return f"{court_prefix}_{singular}"


def _attorneys(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    attorneys: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        appoint = raw.get("appointType")
        if not isinstance(appoint, Mapping):
            appoint = {}
        p_number = _text(raw.get("pNumber"))
        attorneys.append(
            {
                "name": _text(raw.get("name")),
                "p_number": p_number,
                "bar_number": f"P{p_number}" if p_number else None,
                "appointment_code": _text(appoint.get("abbreviation")),
                "appointment_description": _text(appoint.get("description")),
            }
        )
    return attorneys


def normalize_item(
    item: Mapping[str, Any],
    *,
    result_type: str,
    source_url: str,
    source_schema_fingerprint: str,
    retrieval: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize one official result while retaining its source representation."""

    if result_type not in RESULT_KINDS:
        raise MichiganSelectionError(
            f"unknown result type: {result_type}",
            details={"supported": sorted(RESULT_KINDS)},
        )
    if not isinstance(item, Mapping):
        raise MichiganSourceChangedError("search item must be an object")
    missing = sorted(
        key
        for key in ("title", "caseUrl", "documentUrl", "filingDate")
        if key not in item
    )
    if missing:
        raise MichiganSourceChangedError(
            "search item is missing expected fields",
            url=source_url,
            details={"missing_fields": missing},
        )

    court_code, court = _court_for_item(item)
    case_number, case_number_resolved = _primary_case_number(item, court_code)
    numbers = _case_numbers(item)
    document_url = _absolute_url(item.get("documentUrl"))
    case_url = _absolute_url(item.get("caseUrl"))
    native_document_id = _native_document_id(document_url)
    native_id = native_document_id or case_number
    record_kind = RESULT_KINDS[result_type]
    lower_courts = _unique_text(
        item.get("courts") if isinstance(item.get("courts"), list) else []
    )
    attorneys = _attorneys(item.get("attorneys"))

    party_fields = {
        "coa": _text(item.get("courtOfAppealsParties")),
        "msc": _text(item.get("supremeCourtParties")),
        "coc": _text(item.get("courtOfClaimsParties")),
    }
    party_summary = party_fields.get(court_code) or next(
        (value for value in party_fields.values() if value),
        None,
    )
    statuses = {
        "court_of_appeals": _text(item.get("courtOfAppealsCaseStatus")),
        "supreme_court": _text(item.get("supremeCourtCaseStatus")),
        "court_of_claims": _text(item.get("courtOfClaimsCaseStatus")),
    }
    status_key = {
        "coa": "court_of_appeals",
        "msc": "supreme_court",
        "coc": "court_of_claims",
    }.get(court_code)
    case_status = statuses.get(status_key) if status_key else None
    if case_status is None:
        case_status = next(
            (value for value in statuses.values() if value),
            None,
        )

    join_keys: dict[str, Any] = {
        "appellate_case_number": case_number,
        "coa_case_number": numbers["coa"],
        "msc_case_number": numbers["msc"],
        "court_of_claims_case_number": numbers["coc"],
        "lower_courts": lower_courts,
        "attorney_p_numbers": [
            value["p_number"] for value in attorneys if value["p_number"]
        ],
        "native_document_id": native_document_id,
    }
    record = {
        "source_id": SOURCE_ID,
        "record_kind": record_kind,
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            str(court["court_id"]),
            case_number,
            record_kind,
            native_id,
        ),
        "court": {
            **court,
            "state_code": STATE_CODE,
            "official_url": case_url or SEARCH_PAGE_URL,
            "identity_basis": (
                "case_url_route"
                if CASE_ROUTE_RE.search(_text(item.get("caseUrl")) or "")
                else "source_flags"
            ),
        },
        "raw_case_number": case_number if case_number_resolved else None,
        "normalized_case_number": case_number if case_number_resolved else None,
        "case_number_resolved": case_number_resolved,
        "case_number_variants": _unique_text(
            [case_number, numbers["coa"], numbers["msc"], numbers["coc"]]
        ),
        "caption": _text(item.get("title")),
        "party_summary": party_summary,
        "attorneys": attorneys,
        "lower_courts": lower_courts,
        "case_status": case_status,
        "case_statuses": statuses,
        "filing_or_release_date": _date(item.get("filingDate")),
        "filing_or_release_datetime_raw": _text(item.get("filingDate")),
        "decision": _text(item.get("decision")),
        "is_published": item.get("isPublished"),
        "is_final_opinion": item.get("isFinalOpinion"),
        "has_opinions": bool(item.get("hasOpinions")),
        "has_orders": bool(item.get("hasOrders")),
        "case_url": case_url,
        "document": (
            {
                "document_type": _document_type(result_type, court_code),
                "native_document_id": native_document_id,
                "native_document_id_type": "source_filename",
                "source_url": document_url,
                "mime_type": "application/pdf",
                "file_retrievable": True,
            }
            if document_url
            else None
        ),
        "join_keys": join_keys,
        "source_url": source_url,
        "schema_fingerprint": source_schema_fingerprint,
        "retrieval": dict(retrieval),
        "raw_source_record": dict(item),
    }
    return record


def parse_search_payload(
    payload: Mapping[str, Any],
    *,
    result_type: str,
    requested_page: int,
    source_url: str,
) -> MichiganSearchPage:
    """Validate and parse one native Michigan search page."""

    if not isinstance(payload, Mapping):
        raise MichiganSourceChangedError(
            "search response must be a JSON object",
            url=source_url,
        )
    required = {
        "currentPage",
        "facets",
        "pageSize",
        "resultCount",
        "searchItems",
        "selectedSortOption",
        "sortByOptions",
        "totalPages",
        "totalResults",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise MichiganSourceChangedError(
            "search response is missing expected fields",
            url=source_url,
            details={"missing_fields": missing},
        )
    items = payload.get("searchItems")
    facets = payload.get("facets")
    sort_options = payload.get("sortByOptions")
    if not isinstance(items, list) or any(
        not isinstance(value, Mapping) for value in items
    ):
        raise MichiganSourceChangedError(
            "searchItems must be an array of objects",
            url=source_url,
        )
    if not isinstance(facets, list) or any(
        not isinstance(value, Mapping) for value in facets
    ):
        raise MichiganSourceChangedError(
            "facets must be an array of objects",
            url=source_url,
        )
    if not isinstance(sort_options, list) or any(
        not isinstance(value, str) for value in sort_options
    ):
        raise MichiganSourceChangedError(
            "sortByOptions must be an array of strings",
            url=source_url,
        )

    current_page = _integer(payload.get("currentPage"), "currentPage")
    page_size = _integer(payload.get("pageSize"), "pageSize")
    result_count = _integer(payload.get("resultCount"), "resultCount")
    total_pages = _integer(payload.get("totalPages"), "totalPages")
    total_results = _integer(payload.get("totalResults"), "totalResults")
    if current_page != requested_page:
        raise MichiganSourceChangedError(
            "source returned a different page than requested",
            url=source_url,
            details={
                "requested_page": requested_page,
                "returned_page": current_page,
            },
        )
    if current_page <= 0 or page_size <= 0:
        raise MichiganSourceChangedError(
            "currentPage and pageSize must be positive",
            url=source_url,
        )
    if min(result_count, total_pages, total_results) < 0:
        raise MichiganSourceChangedError(
            "pagination values must not be negative",
            url=source_url,
        )
    if result_count != len(items):
        raise MichiganSourceChangedError(
            "resultCount does not match searchItems length",
            url=source_url,
            details={
                "result_count": result_count,
                "search_items": len(items),
            },
        )
    schema = {
        "envelope_fields": sorted(payload.keys()),
        "item_schema": (
            inferred_schema([dict(value) for value in items])
            if items
            else {"kind": "empty_search_items"}
        ),
    }
    return MichiganSearchPage(
        result_type=result_type,
        records=tuple(dict(value) for value in items),
        current_page=current_page,
        page_size=page_size,
        result_count=result_count,
        total_pages=total_pages,
        total_results=total_results,
        selected_sort_option=_text(payload.get("selectedSortOption")),
        sort_by_options=tuple(sort_options),
        facets=tuple(dict(value) for value in facets),
        source_url=source_url,
        schema_fingerprint=schema_fingerprint(schema),
    )


def parse_overview_payload(
    payload: Mapping[str, Any],
    *,
    source_url: str,
) -> dict[str, MichiganSearchPage]:
    """Parse the official cross-category preview response."""

    if not isinstance(payload, Mapping):
        raise MichiganSourceChangedError(
            "overview response must be a JSON object",
            url=source_url,
        )
    keys = {
        "cases": "caseDetailResults",
        "opinions": "opinionResults",
        "orders": "orderResults",
    }
    missing = sorted(value for value in keys.values() if value not in payload)
    if missing:
        raise MichiganSourceChangedError(
            "overview response is missing result groups",
            url=source_url,
            details={"missing_fields": missing},
        )
    pages: dict[str, MichiganSearchPage] = {}
    for result_type, key in keys.items():
        value = payload.get(key)
        if not isinstance(value, Mapping):
            raise MichiganSourceChangedError(
                f"{key} must be an object",
                url=source_url,
            )
        requested_page = _integer(value.get("currentPage"), f"{key}.currentPage")
        pages[result_type] = parse_search_payload(
            value,
            result_type=result_type,
            requested_page=requested_page,
            source_url=source_url,
        )
    return pages


def _query_fingerprint(
    result_type: str,
    query_text: str,
    sort_order: str,
    page_size: int,
    filters: Mapping[str, str],
) -> str:
    return sha256_fingerprint(
        {
            "result_type": result_type,
            "query_text": query_text,
            "sort_order": sort_order,
            "page_size": page_size,
            "filters": dict(sorted(filters.items())),
        }
    )[:16]


def make_cursor(
    *,
    result_type: str,
    page: int,
    offset: int,
    query_fingerprint: str,
) -> str:
    return (
        f"mi-appellate:v1:{result_type}:page:{page}:offset:{offset}:"
        f"query:{query_fingerprint}"
    )


def parse_cursor(
    value: str,
    *,
    result_type: str,
    query_fingerprint: str,
) -> tuple[int, int]:
    match = CURSOR_RE.fullmatch(value)
    if not match:
        raise MichiganSelectionError(
            "cursor is not a Michigan appellate cursor",
            details={"cursor": value},
        )
    if match.group("kind") != result_type:
        raise MichiganSelectionError(
            "cursor result type does not match this query",
            details={
                "cursor_result_type": match.group("kind"),
                "query_result_type": result_type,
            },
        )
    if match.group("fingerprint") != query_fingerprint:
        raise MichiganSelectionError(
            "cursor belongs to a different query",
        )
    page = int(match.group("page"))
    offset = int(match.group("offset"))
    if page <= 0 or offset < 0:
        raise MichiganSelectionError("cursor page or offset is invalid")
    return page, offset


def parse_parameter_pairs(values: Sequence[str] | None) -> dict[str, str]:
    """Parse repeatable KEY=VALUE passthrough parameters."""

    parsed: dict[str, list[str]] = {}
    for raw in values or ():
        if "=" not in raw:
            raise MichiganSelectionError(
                "native parameters must use KEY=VALUE",
                details={"parameter": raw},
            )
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise MichiganSelectionError(
                "native parameter key and value must be non-empty",
                details={"parameter": raw},
            )
        parsed.setdefault(key, []).append(value)
    return {key: ",".join(items) for key, items in parsed.items()}


def _facet_summaries(
    facets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for facet in facets:
        values = facet.get("facets")
        selected = facet.get("selectedFacets")
        summaries.append(
            {
                "name": _text(facet.get("name")),
                "query_string_key": _text(facet.get("queryStringKey")),
                "value_count": len(values) if isinstance(values, list) else 0,
                "selected_values": (
                    list(selected) if isinstance(selected, list) else []
                ),
            }
        )
    return summaries


def parameters_from_args(args: argparse.Namespace) -> dict[str, str]:
    """Build native facet and advanced-search parameters."""

    parameters = parse_parameter_pairs(getattr(args, "native_parameters", None))
    for attribute, native_name in ADVANCED_PARAMETERS.items():
        value = getattr(args, attribute, None)
        if isinstance(value, bool):
            if value:
                parameters[native_name] = "true"
            continue
        normalized = _text(value)
        if normalized is not None:
            parameters[native_name] = normalized
    for attribute, native_name in FACET_PARAMETERS.items():
        values = getattr(args, attribute, None)
        if not values:
            continue
        parameters[native_name] = ",".join(
            normalized for value in values if (normalized := _text(value)) is not None
        )
    return parameters


class MichiganAppellateClient:
    """Bounded client for the public Michigan court search endpoints."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        max_json_bytes: int = DEFAULT_MAX_JSON_BYTES,
        max_pdf_bytes: int = DEFAULT_MAX_PDF_BYTES,
        sleeper: Any = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            backoff_initial=0.5,
        )
        self.max_json_bytes = max_json_bytes
        self.max_pdf_bytes = max_pdf_bytes
        self.sleeper = sleeper
        self.request_count = 0
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": DEFAULT_USER_AGENT,
            }
        )

    def close(self) -> None:
        self.session.close()

    def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        accept: str = "application/json",
    ) -> Any:
        last_error: MichiganAppellateError | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.get(
                    url,
                    params=dict(params or {}),
                    headers={"Accept": accept},
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = MichiganTransportError(
                    f"request failed: {error}",
                    url=url,
                )
            else:
                status_code = int(response.status_code)
                effective_url = str(getattr(response, "url", url) or url)
                if 200 <= status_code < 300:
                    return response
                details = {
                    "status_code": status_code,
                    "response_text": str(getattr(response, "text", ""))[:500],
                }
                if status_code == 429:
                    last_error = MichiganRateLimitedError(
                        "Michigan court source rate limited the request",
                        url=effective_url,
                        details=details,
                    )
                elif status_code in {401, 403}:
                    last_error = MichiganRestrictedError(
                        "Michigan court source denied the request",
                        url=effective_url,
                        details=details,
                    )
                elif status_code == 404:
                    last_error = MichiganSourceChangedError(
                        "Michigan court endpoint was not found",
                        url=effective_url,
                        details=details,
                    )
                elif status_code >= 500:
                    last_error = MichiganTransportError(
                        f"Michigan court source returned HTTP {status_code}",
                        url=effective_url,
                        details=details,
                    )
                else:
                    last_error = MichiganHTTPError(
                        f"Michigan court source returned HTTP {status_code}",
                        url=effective_url,
                        details=details,
                    )
            assert last_error is not None
            retryable_status = (
                isinstance(last_error, MichiganRateLimitedError)
                or last_error.details.get("status_code")
                in self.retry_policy.retry_statuses
            )
            if (
                not (last_error.retryable or retryable_status)
                or attempt >= self.retry_policy.max_attempts
            ):
                raise last_error
            self.sleeper(self.retry_policy.delay(attempt))
        assert last_error is not None
        raise last_error

    def _json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[Mapping[str, Any], str]:
        response = self._request(url, params=params)
        content = bytes(getattr(response, "content", b"") or b"")
        if content and len(content) > self.max_json_bytes:
            raise MichiganSourceChangedError(
                "Michigan court JSON response exceeded the configured bound",
                url=str(getattr(response, "url", url) or url),
                details={"response_bytes": len(content)},
            )
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise MichiganSourceChangedError(
                "Michigan court endpoint did not return JSON",
                url=str(getattr(response, "url", url) or url),
                details={
                    "content_type": _text(
                        getattr(response, "headers", {}).get("Content-Type")
                    )
                },
            ) from error
        if not isinstance(payload, Mapping):
            raise MichiganSourceChangedError(
                "Michigan court JSON response must be an object",
                url=str(getattr(response, "url", url) or url),
            )
        return payload, str(getattr(response, "url", url) or url)

    def fetch_page(
        self,
        *,
        result_type: str,
        query_text: str,
        sort_order: str,
        page: int,
        page_size: int,
        filters: Mapping[str, str],
    ) -> MichiganSearchPage:
        endpoint = SEARCH_ENDPOINTS.get(result_type)
        if endpoint is None:
            raise MichiganSelectionError(
                f"unknown result type: {result_type}",
                details={"supported": sorted(SEARCH_ENDPOINTS)},
            )
        params = {
            **dict(filters),
            "searchQuery": query_text,
            "sortOrder": sort_order,
            "page": page,
            "pageSize": page_size,
        }
        payload, source_url = self._json(endpoint, params=params)
        return parse_search_payload(
            payload,
            result_type=result_type,
            requested_page=page,
            source_url=source_url,
        )

    def search(
        self,
        *,
        result_type: str,
        query_text: str,
        sort_order: str,
        page_size: int,
        start_page: int,
        start_offset: int,
        limit: int,
        filters: Mapping[str, str],
    ) -> MichiganSearchCollection:
        records: list[Mapping[str, Any]] = []
        source_urls: list[str] = []
        fingerprints: list[str] = []
        page_number = start_page
        offset = start_offset
        pages_fetched = 0
        total_results = 0
        incomplete_error: MichiganAppellateError | None = None
        next_page: int | None = None
        next_offset = 0

        while len(records) < limit:
            try:
                page = self.fetch_page(
                    result_type=result_type,
                    query_text=query_text,
                    sort_order=sort_order,
                    page=page_number,
                    page_size=page_size,
                    filters=filters,
                )
            except MichiganAppellateError as error:
                if not records:
                    raise
                incomplete_error = error
                next_page = page_number
                next_offset = offset
                break
            pages_fetched += 1
            total_results = page.total_results
            source_urls.append(page.source_url)
            fingerprints.append(page.schema_fingerprint)
            if offset > len(page.records):
                raise MichiganSelectionError(
                    "cursor offset exceeds the source page",
                    details={
                        "offset": offset,
                        "page_records": len(page.records),
                    },
                )
            retrieval = {
                "native_page": page.current_page,
                "native_page_size": page.page_size,
                "native_result_count": page.result_count,
                "native_total_pages": page.total_pages,
                "native_total_results": page.total_results,
                "selected_sort_option": page.selected_sort_option,
                "sort_by_options": list(page.sort_by_options),
                "facets": _facet_summaries(page.facets),
            }
            remaining = limit - len(records)
            source_slice = page.records[offset : offset + remaining]
            records.extend(
                normalize_item(
                    value,
                    result_type=result_type,
                    source_url=page.source_url,
                    source_schema_fingerprint=page.schema_fingerprint,
                    retrieval=retrieval,
                )
                for value in source_slice
            )
            consumed = offset + len(source_slice)
            if consumed < len(page.records):
                next_page = page_number
                next_offset = consumed
                break
            if page.next_page is None:
                next_page = None
                next_offset = 0
                break
            page_number = page.next_page
            offset = 0
            next_page = page_number
            next_offset = 0

        return MichiganSearchCollection(
            records=tuple(records),
            pages_fetched=pages_fetched,
            total_results=total_results,
            next_page=next_page,
            next_offset=next_offset,
            source_urls=tuple(source_urls),
            schema_fingerprints=tuple(fingerprints),
            incomplete_error=incomplete_error,
        )

    def overview(self, query_text: str) -> dict[str, MichiganSearchPage]:
        payload, source_url = self._json(
            OVERVIEW_URL,
            params={"searchQuery": query_text},
        )
        return parse_overview_payload(payload, source_url=source_url)

    def page_model(self) -> Mapping[str, Any]:
        payload, _ = self._json(PAGE_MODEL_URL)
        return payload

    def download(self, value: str) -> MichiganDocument:
        url = _official_url(value)
        response = self._request(url, accept="application/pdf")
        effective_url = _official_url(str(getattr(response, "url", url) or url))
        content = bytes(getattr(response, "content", b"") or b"")
        if len(content) > self.max_pdf_bytes:
            raise MichiganSourceChangedError(
                "Michigan court PDF exceeded the configured bound",
                url=effective_url,
                details={"response_bytes": len(content)},
            )
        if not content.startswith(b"%PDF-"):
            raise MichiganSourceChangedError(
                "Michigan court document response is not a PDF",
                url=effective_url,
                details={
                    "content_type": _text(
                        getattr(response, "headers", {}).get("Content-Type")
                    )
                },
            )
        filename = Path(unquote(urlparse(effective_url).path)).name
        return MichiganDocument(
            source_url=effective_url,
            content=content,
            media_type="application/pdf",
            filename=filename,
            sha256=hashlib.sha256(content).hexdigest(),
        )


def _routes() -> list[dict[str, Any]]:
    return [
        {
            "route_id": "michigan_appellate_portal",
            "source_name": "Michigan Judiciary Cases, Opinions & Orders",
            "source_url": SEARCH_PAGE_URL,
            "role": "appellate_case_index_opinions_and_orders",
            "access_method": "anonymous_json_api",
            "join_keys": [
                "appellate_case_number",
                "lower_court",
                "attorney_p_number",
                "native_document_id",
            ],
        },
        {
            "route_id": "micourt_trial_case_search",
            "source_name": "MiCOURT Case Search",
            "source_url": MICOURT_SEARCH_URL,
            "role": "participating_trial_court_case_index",
            "access_method": "public_web_portal",
            "join_keys": [
                "lower_court",
                "lower_court_case_number",
                "party_name",
            ],
        },
        {
            "route_id": "micourt_developer_api",
            "source_name": "MiCOURT Developer Case Search API",
            "source_url": MICOURT_DEVELOPER_URL,
            "role": "structured_participating_trial_court_case_data",
            "access_method": "subscription_api",
            "join_keys": [
                "court_key",
                "lower_court_case_number",
                "participant_name",
            ],
        },
        {
            "route_id": "michigan_business_court",
            "source_name": "Michigan Business Court Search",
            "source_url": BUSINESS_COURT_URL,
            "role": "specialized_trial_court_opinions",
            "access_method": "public_web_search",
            "join_keys": [
                "lower_court_case_number",
                "lower_court",
                "party_name",
                "judge",
            ],
        },
        {
            "route_id": "michigan_trial_court_directory",
            "source_name": "Michigan Trial Court Directory",
            "source_url": TRIAL_COURT_DIRECTORY_URL,
            "role": "official_clerk_and_record_request_routing",
            "access_method": "court_directory",
            "join_keys": ["lower_court", "lower_court_case_number"],
        },
    ]


def related_source_routes() -> list[dict[str, Any]]:
    """Return independently attributable routes that complement this index."""

    return [dict(record) for record in _routes()]


def build_query(
    args: argparse.Namespace,
    *,
    filters: Mapping[str, str] | None = None,
) -> PublicRecordsQuery:
    command = str(args.command)
    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    cursor = getattr(args, "cursor", None)
    if command == "search":
        parameters = {
            "query_text": getattr(args, "query_text", "") or "",
            "result_type": args.result_type,
            "sort_order": args.sort_order,
            "page": args.page,
            "page_size": args.page_size,
            "native_filters": dict(filters or {}),
        }
        requested_limit = args.limit
    elif command == "overview":
        parameters = {"query_text": args.query_text}
    elif command == "download":
        parameters = {
            "document_url": args.document_url,
            "destination": str(args.destination),
        }
    elif command == "probe":
        parameters = {"query_text": args.query_text}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: MichiganAppellateError,
    *,
    records: Sequence[Mapping[str, Any]] = (),
    next_cursor: str | None = None,
) -> PublicRecordsResult:
    status = ResultStatus.PARTIAL if records else error.status
    return PublicRecordsResult.failure(
        query,
        status,
        [error.to_contract_error()],
        records=records,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _execute_search(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: MichiganAppellateClient | Any,
    filters: Mapping[str, str],
) -> PublicRecordsResult:
    selection_fingerprint = _query_fingerprint(
        args.result_type,
        args.query_text or "",
        args.sort_order,
        args.page_size,
        filters,
    )
    start_page = args.page
    start_offset = 0
    if args.cursor:
        start_page, start_offset = parse_cursor(
            args.cursor,
            result_type=args.result_type,
            query_fingerprint=selection_fingerprint,
        )
    collection = client.search(
        result_type=args.result_type,
        query_text=args.query_text or "",
        sort_order=args.sort_order,
        page_size=args.page_size,
        start_page=start_page,
        start_offset=start_offset,
        limit=args.limit,
        filters=filters,
    )
    next_cursor = (
        make_cursor(
            result_type=args.result_type,
            page=collection.next_page,
            offset=collection.next_offset,
            query_fingerprint=selection_fingerprint,
        )
        if collection.next_page is not None
        else None
    )
    if collection.incomplete_error is not None:
        return _failure(
            query,
            collection.incomplete_error,
            records=collection.records,
            next_cursor=next_cursor,
        )
    return PublicRecordsResult.success(
        query,
        collection.records,
        next_cursor=next_cursor,
        raw_artifact_refs=collection.source_urls,
        warnings=SOURCE_WARNINGS,
    )


def _execute_overview(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: MichiganAppellateClient | Any,
) -> PublicRecordsResult:
    pages = client.overview(args.query_text)
    records: list[Mapping[str, Any]] = []
    refs: list[str] = []
    for result_type, page in pages.items():
        refs.append(page.source_url)
        retrieval = {
            "overview_preview": True,
            "native_page": page.current_page,
            "native_page_size": page.page_size,
            "native_total_pages": page.total_pages,
            "native_total_results": page.total_results,
        }
        records.extend(
            normalize_item(
                value,
                result_type=result_type,
                source_url=page.source_url,
                source_schema_fingerprint=page.schema_fingerprint,
                retrieval=retrieval,
            )
            for value in page.records
        )
    return PublicRecordsResult.success(
        query,
        records,
        raw_artifact_refs=tuple(dict.fromkeys(refs)),
        warnings=(
            *SOURCE_WARNINGS,
            "Overview returns the portal preview; use search with a result "
            "type to traverse that category.",
        ),
    )


def _execute_download(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: MichiganAppellateClient | Any,
) -> PublicRecordsResult:
    document = client.download(args.document_url)
    destination = Path(args.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(document.content)
    record = {
        "source_id": SOURCE_ID,
        "record_kind": "downloaded_appellate_document",
        "source_url": document.source_url,
        "local_path": str(destination.resolve()),
        "filename": document.filename,
        "media_type": document.media_type,
        "content_length": len(document.content),
        "sha256": document.sha256,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[document.source_url, str(destination.resolve())],
        warnings=SOURCE_WARNINGS,
    )


def _execute_probe(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: MichiganAppellateClient | Any,
) -> PublicRecordsResult:
    checks: dict[str, Any] = {}
    refs: list[str] = [PAGE_MODEL_URL]
    page_model = client.page_model()
    page_sizes = page_model.get("pageSizeOptions")
    if not isinstance(page_sizes, list) or any(
        isinstance(value, bool) or not isinstance(value, int) for value in page_sizes
    ):
        raise MichiganSourceChangedError(
            "case-search page model lacks numeric pageSizeOptions",
            url=PAGE_MODEL_URL,
        )
    checks["page_size_options"] = page_sizes
    checks["appellate_court_options"] = page_model.get("appellateCourtOptions")
    checks["lower_court_option_count"] = len(page_model.get("lowerCourtOptions") or [])
    for result_type in SEARCH_ENDPOINTS:
        page = client.fetch_page(
            result_type=result_type,
            query_text=args.query_text,
            sort_order="Newest",
            page=1,
            page_size=1,
            filters={},
        )
        checks[result_type] = {
            "result_count": page.result_count,
            "total_results": page.total_results,
            "total_pages": page.total_pages,
            "schema_fingerprint": page.schema_fingerprint,
        }
        refs.append(page.source_url)
    document = client.download(PROBE_DOCUMENT_URL)
    checks["document"] = {
        "source_url": document.source_url,
        "media_type": document.media_type,
        "content_length": len(document.content),
        "sha256": document.sha256,
    }
    refs.append(document.source_url)
    record = {
        "source_id": SOURCE_ID,
        "record_kind": "source_probe",
        "checks": checks,
        "source_url": SEARCH_PAGE_URL,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=tuple(dict.fromkeys(refs)),
        warnings=SOURCE_WARNINGS,
    )


def _best_effort_log(query: PublicRecordsQuery, result: PublicRecordsResult) -> None:
    try:
        log_search(
            canonical_json(query.to_dict()),
            SOURCE_ID,
            len(result.records),
        )
    except Exception:
        pass


def execute(
    args: argparse.Namespace,
    *,
    client: MichiganAppellateClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Michigan appellate source operation."""

    filters: dict[str, str] = {}
    try:
        if args.command == "search":
            filters = parameters_from_args(args)
        query = build_query(args, filters=filters)
    except MichiganAppellateError as error:
        raw_arguments = {
            key: (
                str(value)
                if isinstance(value, Path)
                else [str(item) if isinstance(item, Path) else item for item in value]
                if isinstance(value, list)
                else value
            )
            for key, value in vars(args).items()
        }
        query = PublicRecordsQuery(
            source=SOURCE_METADATA,
            jurisdiction=JURISDICTION,
            query=QueryMetadata(
                operation=str(args.command),
                parameters={"raw_arguments": raw_arguments},
            ),
        )
        return _failure(query, error)

    if args.command == "routes":
        result = PublicRecordsResult.success(
            query,
            _routes(),
            warnings=SOURCE_WARNINGS,
        )
        if log_results:
            _best_effort_log(query, result)
        return result

    source_client = client or MichiganAppellateClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=0.5,
        ),
    )
    owns_client = client is None
    try:
        if args.command == "search":
            result = _execute_search(args, query, source_client, filters)
        elif args.command == "overview":
            result = _execute_overview(args, query, source_client)
        elif args.command == "download":
            result = _execute_download(args, query, source_client)
        elif args.command == "probe":
            result = _execute_probe(args, query, source_client)
        else:
            raise MichiganSelectionError(f"unsupported command: {args.command}")
    except MichiganAppellateError as error:
        result = _failure(query, error)
    except (TypeError, ValueError, KeyError) as error:
        result = _failure(
            query,
            MichiganSourceChangedError(
                f"Michigan result normalization failed: {error}"
            ),
        )
    finally:
        if owns_client:
            source_client.close()
    if log_results:
        _best_effort_log(query, result)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Michigan appellate {args.command} "
            f"({result.status.value}, {len(result.records)} records)"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Michigan appellate {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") in RESULT_KINDS.values():
            print(
                f"  {record.get('raw_case_number') or '?'} | "
                f"{record.get('record_kind')} | "
                f"{record.get('caption') or '?'}"
            )
        elif record.get("record_kind") == "source_probe":
            print("  official cases, opinions, orders, and PDF checks passed")
        else:
            print(f"  {record.get('route_id') or record.get('filename') or '?'}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Query Michigan's official appellate cases, opinions, and orders")
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser(
        "search",
        help="Search and paginate one official result category",
    )
    search.add_argument("query_text", nargs="?", default="")
    search.add_argument(
        "--result-type",
        choices=tuple(SEARCH_ENDPOINTS),
        default="cases",
    )
    search.add_argument(
        "--sort",
        dest="sort_order",
        default="Relevance",
        help="Native sort label, such as Relevance, Newest, Oldest, A-Z, or Z-A",
    )
    search.add_argument("--page", type=_positive_int, default=1)
    search.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
    )
    search.add_argument("--limit", type=_positive_int, default=DEFAULT_LIMIT)
    search.add_argument("--cursor")

    search.add_argument("--appellate-court")
    search.add_argument("--attorney-name")
    search.add_argument("--bar-number")
    search.add_argument("--case-id")
    search.add_argument("--case-type")
    search.add_argument("--lower-court")
    search.add_argument("--open-only", dest="open_status", action="store_true")
    search.add_argument("--party-name")
    search.add_argument("--author", dest="author_name")
    search.add_argument("--panel-member")

    search.add_argument("--court", dest="courts", action="append")
    search.add_argument("--court-type", dest="court_types", action="append")
    search.add_argument("--judge", dest="judges", action="append")
    search.add_argument("--filing-date", dest="filing_dates", action="append")
    search.add_argument("--resource", dest="resources", action="append")
    search.add_argument("--release-date", dest="release_dates", action="append")
    search.add_argument(
        "--native-param",
        dest="native_parameters",
        action="append",
        metavar="KEY=VALUE",
        help="Pass through an additional source-supported query parameter",
    )
    _add_runtime(search)

    overview = sub.add_parser(
        "overview",
        help="Return the portal's cross-category preview",
    )
    overview.add_argument("query_text")
    _add_runtime(overview)

    download = sub.add_parser(
        "download",
        help="Download and validate an official opinion or order PDF",
    )
    download.add_argument("document_url")
    download.add_argument("destination", type=Path)
    _add_runtime(download)

    routes = sub.add_parser(
        "routes",
        help="Show complementary official sources and their join keys",
    )
    add_output_args(routes)

    probe = sub.add_parser(
        "probe",
        help="Verify result APIs, page-model options, and a document PDF",
    )
    probe.add_argument("--query", dest="query_text", default=PROBE_QUERY)
    _add_runtime(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "timeout", DEFAULT_TIMEOUT) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", DEFAULT_MINIMUM_INTERVAL) < 0:
        parser.error("--minimum-interval must not be negative")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
