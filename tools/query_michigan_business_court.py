#!/usr/bin/env python3
"""Query Michigan's official Business Court document collection.

The Michigan Judiciary publishes an anonymous JSON search endpoint with a
fixed native page size and official PDF links. This adapter traverses the
source using ``totalPages`` because the response's ``hasMoreResults`` flag is
not a reliable continuation signal.

Examples:
    uv run python tools/query_michigan_business_court.py categories --json
    uv run python tools/query_michigan_business_court.py sources --json
    uv run python tools/query_michigan_business_court.py search "real estate" \
        --business-court "Real Estate" --limit 40 --output /tmp/mi-business.json
    uv run python tools/query_michigan_business_court.py download \
        "https://www.courts.michigan.gov/.../opinion.pdf" /tmp/opinion.pdf
    uv run python tools/query_michigan_business_court.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
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


SOURCE_ID = "us-mi-business-court-search"
STATE_CODE = "MI"
STATE_GEOID = "26"
COLLECTION_COURT_ID = "us-mi-business-court-document-collection"

BASE_URL = "https://www.courts.michigan.gov"
LANDING_URL = f"{BASE_URL}/business-court-search/"
SEARCH_URL = (
    f"{BASE_URL}/api/BusinessCourtSearch/SearchBusinessCourtDocuments"
)

NATIVE_PAGE_SIZE = 8
SORT_ORDERS = ("Relevance", "A-Z", "Z-A", "Newest", "Oldest")
OUTPUT_SCHEMA_VERSION = "michigan-business-court/1.0"
CURSOR_PREFIX = "mi-business-court:v1:"
CURSOR_VERSION = 1

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_USER_AGENT = (
    "IthildinOSINT/1.0 Michigan official Business Court records client"
)
PROBE_ZERO_QUERY = "zzzznotlikely2026"

BUSINESS_CATEGORY_QUERY_KEY = "businessCourt"
COURT_QUERY_KEY = "court"
REQUIRED_RESPONSE_FIELDS = frozenset(
    {
        "currentPage",
        "facets",
        "hasMoreResults",
        "pageSize",
        "resultCount",
        "searchItems",
        "selectedSortOption",
        "sortByOptions",
        "totalPages",
        "totalResults",
    }
)
REQUIRED_ITEM_FIELDS = frozenset(
    {
        "businessCategoriesUnparsed",
        "businessCategories",
        "tags",
        "title",
        "url",
    }
)
OPTIONAL_ITEM_FIELDS = frozenset(
    {
        "pleadingOrderDate",
        "caseName",
        "caseNumber",
    }
)
CASE_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:\d{2,4}-)?[A-Za-z0-9]{2,10}(?:-[A-Za-z0-9]{1,8})+"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)
FILENAME_COURT_CODE_RE = re.compile(
    r"^(?P<code>c\d{2,3})(?:[-_])",
    re.IGNORECASE,
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Michigan Business Court Search",
    source_role="official_business_court_document_search_and_pdf_collection",
    base_url=LANDING_URL,
    dataset_id="michigan-business-court-documents",
    metadata={
        "authority": "Michigan Judiciary",
        "authentication": "none",
        "search_endpoint": SEARCH_URL,
        "native_page_size": NATIVE_PAGE_SIZE,
        "sort_orders": list(SORT_ORDERS),
        "native_pagination": "one_based_page_using_totalPages",
        "facet_parameters": [
            BUSINESS_CATEGORY_QUERY_KEY,
            COURT_QUERY_KEY,
        ],
        "document_format": "PDF",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Michigan",
    state_code=STATE_CODE,
)
SOURCE_WARNINGS = (
    (
        "The collection publishes selected Business Court documents and is not "
        "a complete trial-court case index."
    ),
    (
        "A case-number label is retained as a source candidate; the PDF, search "
        "row occurrence, and selected query context have separate identities."
    ),
    (
        "A selected court facet or filename court-code candidate is locator "
        "context, not an independently verified court assignment."
    ),
)


class MichiganBusinessCourtError(RuntimeError):
    """Source error carrying public-record result semantics."""

    code = "michigan_business_court_error"
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


class MichiganBusinessCourtSelectionError(MichiganBusinessCourtError):
    code = "invalid_selection"
    category = "query"


class MichiganBusinessCourtTransportError(MichiganBusinessCourtError):
    code = "transport_error"
    category = "transport"
    retryable = True


class MichiganBusinessCourtRateLimited(MichiganBusinessCourtError):
    code = "rate_limited"
    status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True


class MichiganBusinessCourtRestricted(MichiganBusinessCourtError):
    code = "access_restricted"
    status = ResultStatus.RESTRICTED
    category = "access"


class MichiganBusinessCourtHTTPError(MichiganBusinessCourtError):
    code = "http_status"
    category = "http"


class MichiganBusinessCourtSourceChanged(MichiganBusinessCourtError):
    code = "source_changed"
    status = ResultStatus.SOURCE_CHANGED
    category = "source_schema"


@dataclass(frozen=True)
class BusinessCourtFacet:
    name: str | None
    query_string_key: str
    values: tuple[Any, ...]
    selected_values: tuple[Any, ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class BusinessCourtPage:
    records: tuple[Mapping[str, Any], ...]
    current_page: int
    page_size: int
    result_count: int
    total_pages: int
    total_results: int
    has_more_results: bool
    selected_sort_option: str | None
    sort_by_options: tuple[str, ...]
    facets: tuple[BusinessCourtFacet, ...]
    source_url: str
    schema_fingerprint: str

    @property
    def next_page(self) -> int | None:
        if self.current_page < self.total_pages:
            return self.current_page + 1
        return None


@dataclass(frozen=True)
class BusinessCourtCollection:
    records: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    total_results: int
    total_pages: int
    next_page: int | None
    next_offset: int
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: MichiganBusinessCourtError | None = None


@dataclass(frozen=True)
class BusinessCourtDocument:
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
        raise MichiganBusinessCourtSourceChanged(
            f"{field_name} must be an integer"
        )
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise MichiganBusinessCourtSourceChanged(
            f"{field_name} must be an integer"
        ) from error


def _date(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    leading_iso = re.match(r"^(\d{4}-\d{2}-\d{2})", normalized)
    if leading_iso:
        return leading_iso.group(1)
    for date_format in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _official_pdf_url(
    value: Any,
    *,
    caller_selected: bool = False,
) -> str:
    raw_url = _text(value)
    error_type = (
        MichiganBusinessCourtSelectionError
        if caller_selected
        else MichiganBusinessCourtSourceChanged
    )
    if raw_url is None:
        raise error_type(
            "Business Court search item lacks a document URL"
        )
    url = urljoin(BASE_URL, raw_url)
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.courts.michigan.gov"
        or not unquote(parsed.path).casefold().endswith(".pdf")
    ):
        raise error_type(
            "document URL must be an official Michigan Judiciary PDF",
            details={"document_url": url},
        )
    # A query string can select the publisher's resource and remains part of
    # document identity. A fragment is client-side navigation and is removed
    # from the retrieval URL; the untouched source value remains in raw JSON.
    return parsed._replace(fragment="").geturl()


def _document_identity(document_url: str) -> tuple[str, str]:
    filename = Path(unquote(urlparse(document_url).path)).name
    url_digest = hashlib.sha256(document_url.encode("utf-8")).hexdigest()[:16]
    return f"{url_digest}:{filename}", filename


def _case_number_candidates(value: Any) -> list[str]:
    raw = _text(value)
    if raw is None:
        return []
    components = [
        component
        for component in (
            _text(part)
            for part in re.split(
                r"\s+(?:and|&|/)\s+|\s*;\s*",
                raw,
                flags=re.IGNORECASE,
            )
        )
        if component
    ]
    if len(components) > 1:
        return components
    candidates: list[str] = []
    for match in CASE_NUMBER_RE.finditer(raw):
        candidate = _text(match.group(0))
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates or [raw]


def _filename_court_code_candidate(filename: str) -> str | None:
    match = FILENAME_COURT_CODE_RE.match(filename)
    return match.group("code").lower() if match else None


def _parse_facets(
    value: Any,
    *,
    source_url: str,
) -> tuple[BusinessCourtFacet, ...]:
    if not isinstance(value, list):
        raise MichiganBusinessCourtSourceChanged(
            "facets must be an array",
            url=source_url,
        )
    parsed: list[BusinessCourtFacet] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise MichiganBusinessCourtSourceChanged(
                "each facet must be an object",
                url=source_url,
                details={"facet_index": index},
            )
        missing = sorted(
            {
                "name",
                "queryStringKey",
                "facets",
                "selectedFacets",
            }
            - raw.keys()
        )
        if missing:
            raise MichiganBusinessCourtSourceChanged(
                "facet is missing expected fields",
                url=source_url,
                details={"facet_index": index, "missing_fields": missing},
            )
        query_string_key = _text(raw.get("queryStringKey"))
        facets = raw.get("facets")
        selected = raw.get("selectedFacets")
        if query_string_key is None:
            raise MichiganBusinessCourtSourceChanged(
                "facet queryStringKey must be non-empty",
                url=source_url,
                details={"facet_index": index},
            )
        if not isinstance(facets, list) or not isinstance(selected, list):
            raise MichiganBusinessCourtSourceChanged(
                "facet values and selectedFacets must be arrays",
                url=source_url,
                details={"facet_index": index},
            )
        parsed.append(
            BusinessCourtFacet(
                name=_text(raw.get("name")),
                query_string_key=query_string_key,
                values=tuple(facets),
                selected_values=tuple(selected),
                raw=dict(raw),
            )
        )
    return tuple(parsed)


def parse_search_payload(
    payload: Mapping[str, Any],
    *,
    requested_page: int,
    source_url: str,
) -> BusinessCourtPage:
    """Validate and preserve one native Business Court search page."""

    if not isinstance(payload, Mapping):
        raise MichiganBusinessCourtSourceChanged(
            "search response must be a JSON object",
            url=source_url,
        )
    missing = sorted(REQUIRED_RESPONSE_FIELDS - payload.keys())
    if missing:
        raise MichiganBusinessCourtSourceChanged(
            "search response is missing expected fields",
            url=source_url,
            details={"missing_fields": missing},
        )
    items = payload.get("searchItems")
    sort_options = payload.get("sortByOptions")
    if not isinstance(items, list) or any(
        not isinstance(item, Mapping) for item in items
    ):
        raise MichiganBusinessCourtSourceChanged(
            "searchItems must be an array of objects",
            url=source_url,
        )
    if not isinstance(sort_options, list) or any(
        not isinstance(value, str) for value in sort_options
    ):
        raise MichiganBusinessCourtSourceChanged(
            "sortByOptions must be an array of strings",
            url=source_url,
        )
    for index, item in enumerate(items):
        item_missing = sorted(REQUIRED_ITEM_FIELDS - item.keys())
        if item_missing:
            raise MichiganBusinessCourtSourceChanged(
                "search item is missing expected fields",
                url=source_url,
                details={
                    "item_index": index,
                    "missing_fields": item_missing,
                },
            )
        categories = item.get("businessCategories")
        tags = item.get("tags")
        if not isinstance(categories, list) or not isinstance(tags, list):
            raise MichiganBusinessCourtSourceChanged(
                "businessCategories and tags must be arrays",
                url=source_url,
                details={"item_index": index},
            )
        _official_pdf_url(item.get("url"))

    current_page = _integer(payload.get("currentPage"), "currentPage")
    page_size = _integer(payload.get("pageSize"), "pageSize")
    result_count = _integer(payload.get("resultCount"), "resultCount")
    total_pages = _integer(payload.get("totalPages"), "totalPages")
    total_results = _integer(payload.get("totalResults"), "totalResults")
    has_more_results = payload.get("hasMoreResults")
    if not isinstance(has_more_results, bool):
        raise MichiganBusinessCourtSourceChanged(
            "hasMoreResults must be a boolean",
            url=source_url,
        )
    if current_page != requested_page:
        raise MichiganBusinessCourtSourceChanged(
            "source returned a different page than requested",
            url=source_url,
            details={
                "requested_page": requested_page,
                "returned_page": current_page,
            },
        )
    if current_page <= 0:
        raise MichiganBusinessCourtSourceChanged(
            "currentPage must be positive",
            url=source_url,
        )
    if page_size != NATIVE_PAGE_SIZE:
        raise MichiganBusinessCourtSourceChanged(
            "Business Court native page size changed",
            url=source_url,
            details={
                "expected_page_size": NATIVE_PAGE_SIZE,
                "observed_page_size": page_size,
            },
        )
    if min(result_count, total_pages, total_results) < 0:
        raise MichiganBusinessCourtSourceChanged(
            "pagination values must not be negative",
            url=source_url,
        )
    if result_count != len(items):
        raise MichiganBusinessCourtSourceChanged(
            "resultCount does not match searchItems length",
            url=source_url,
            details={
                "result_count": result_count,
                "search_items": len(items),
            },
        )
    if result_count > page_size:
        raise MichiganBusinessCourtSourceChanged(
            "resultCount exceeds the native page size",
            url=source_url,
            details={
                "result_count": result_count,
                "page_size": page_size,
            },
        )

    facets = _parse_facets(payload.get("facets"), source_url=source_url)
    response_schema = {
        "envelope_fields": sorted(payload),
        "item_schema": (
            inferred_schema([dict(item) for item in items])
            if items
            else {"kind": "empty_search_items"}
        ),
        "facet_query_keys": [
            facet.query_string_key for facet in facets
        ],
    }
    return BusinessCourtPage(
        records=tuple(dict(item) for item in items),
        current_page=current_page,
        page_size=page_size,
        result_count=result_count,
        total_pages=total_pages,
        total_results=total_results,
        has_more_results=has_more_results,
        selected_sort_option=_text(payload.get("selectedSortOption")),
        sort_by_options=tuple(sort_options),
        facets=facets,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint(response_schema),
    )


def _facet_value_label(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key in ("name", "label", "value"):
            raw_label = value.get(key)
            if raw_label is not None:
                label = str(raw_label).replace("\xa0", " ").strip()
                if label:
                    return label
        return None
    if value is None:
        return None
    label = str(value).replace("\xa0", " ").strip()
    return label or None


def _facet_by_key(
    facets: Sequence[BusinessCourtFacet],
    query_string_key: str,
) -> BusinessCourtFacet:
    matches = [
        facet
        for facet in facets
        if facet.query_string_key.casefold() == query_string_key.casefold()
    ]
    if len(matches) != 1:
        raise MichiganBusinessCourtSourceChanged(
            "Business Court response did not expose one expected facet",
            details={
                "query_string_key": query_string_key,
                "observed_query_keys": [
                    facet.query_string_key for facet in facets
                ],
            },
        )
    return matches[0]


def _selection_fingerprint(
    *,
    query_text: str,
    sort_order: str,
    business_courts: Sequence[str],
    courts: Sequence[str],
    audience: str | None,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "query_text": query_text,
            "sort_order": sort_order,
            "business_courts": list(business_courts),
            "courts": list(courts),
            "audience": audience,
            "native_page_size": NATIVE_PAGE_SIZE,
        }
    )


def make_cursor(
    *,
    page: int,
    offset: int,
    selection_fingerprint: str,
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "source_id": SOURCE_ID,
        "page": page,
        "offset": offset,
        "selection_fingerprint": selection_fingerprint,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def parse_cursor(
    value: str,
    *,
    selection_fingerprint: str,
) -> tuple[int, int]:
    if not value.startswith(CURSOR_PREFIX):
        raise MichiganBusinessCourtSelectionError(
            "cursor is not a Michigan Business Court cursor"
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        decoded = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        ).decode("utf-8")
        payload = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MichiganBusinessCourtSelectionError(
            "cursor payload is invalid"
        ) from error
    if not isinstance(payload, Mapping):
        raise MichiganBusinessCourtSelectionError(
            "cursor payload must be an object"
        )
    if (
        payload.get("version") != CURSOR_VERSION
        or payload.get("source_id") != SOURCE_ID
    ):
        raise MichiganBusinessCourtSelectionError(
            "cursor source or version does not match"
        )
    if payload.get("selection_fingerprint") != selection_fingerprint:
        raise MichiganBusinessCourtSelectionError(
            "cursor belongs to a different query"
        )
    try:
        page = int(payload.get("page"))
        offset = int(payload.get("offset"))
    except (TypeError, ValueError) as error:
        raise MichiganBusinessCourtSelectionError(
            "cursor page or offset is not an integer"
        ) from error
    if isinstance(payload.get("page"), bool) or isinstance(
        payload.get("offset"),
        bool,
    ):
        raise MichiganBusinessCourtSelectionError(
            "cursor page or offset is not an integer"
        )
    if page <= 0 or offset < 0:
        raise MichiganBusinessCourtSelectionError(
            "cursor page or offset is invalid"
        )
    return page, offset


def _facet_summaries(
    facets: Sequence[BusinessCourtFacet],
) -> list[dict[str, Any]]:
    return [
        {
            "name": facet.name,
            "query_string_key": facet.query_string_key,
            "values": list(facet.values),
            "selected_values": list(facet.selected_values),
        }
        for facet in facets
    ]


def normalize_search_item(
    item: Mapping[str, Any],
    *,
    source_url: str,
    source_schema_fingerprint: str,
    native_page: int,
    native_row: int,
    page: BusinessCourtPage,
    query_context: Mapping[str, Any],
    selection_fingerprint: str,
) -> dict[str, Any]:
    """Normalize one row while keeping its identities and context distinct."""

    missing = sorted(REQUIRED_ITEM_FIELDS - item.keys())
    if missing:
        raise MichiganBusinessCourtSourceChanged(
            "search item is missing expected fields",
            url=source_url,
            details={"missing_fields": missing},
        )
    document_url = _official_pdf_url(item.get("url"))
    native_document_id, filename = _document_identity(document_url)
    occurrence_basis = {
        "selection_fingerprint": selection_fingerprint,
        "native_page": native_page,
        "native_row": native_row,
        "document_url": document_url,
    }
    source_occurrence_id = sha256_fingerprint(occurrence_basis)
    raw_case_number = _text(item.get("caseNumber"))
    case_candidates = _case_number_candidates(raw_case_number)
    selected_courts = [
        value
        for value in query_context.get("courts", [])
        if isinstance(value, str) and value
    ]
    court_locator_candidates: list[dict[str, Any]] = []
    if len(selected_courts) == 1:
        court_locator_candidates.append(
            {
                "value": selected_courts[0],
                "basis": "selected_single_court_facet",
                "authoritative_assignment": False,
            }
        )
    filename_code = _filename_court_code_candidate(filename)
    if filename_code:
        court_locator_candidates.append(
            {
                "value": filename_code,
                "basis": "filename_court_code_candidate",
                "authoritative_assignment": False,
            }
        )
    categories = item.get("businessCategories")
    tags = item.get("tags")
    if not isinstance(categories, list) or not isinstance(tags, list):
        raise MichiganBusinessCourtSourceChanged(
            "businessCategories and tags must be arrays",
            url=source_url,
        )
    record_kind = "business_court_document_search_occurrence"
    return {
        "source_id": SOURCE_ID,
        "record_kind": record_kind,
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COLLECTION_COURT_ID,
            f"document:{native_document_id}",
            record_kind,
            source_occurrence_id,
        ),
        "source_occurrence_id": source_occurrence_id,
        "occurrence_identity": occurrence_basis,
        "document": {
            "native_document_id": native_document_id,
            "native_document_id_type": "official_pdf_url_and_filename",
            "filename": filename,
            "source_url": document_url,
            "mime_type": "application/pdf",
        },
        "title": _text(item.get("title")),
        "pleading_or_order_date": _date(item.get("pleadingOrderDate")),
        "pleading_or_order_date_raw": _text(
            item.get("pleadingOrderDate")
        ),
        "case_name_observation": _text(item.get("caseName")),
        "case_number_observation": (
            {
                "raw": raw_case_number,
                "candidates": case_candidates,
                "candidate_basis": "source_caseNumber_label",
                "canonical_case_number": None,
            }
            if raw_case_number
            else None
        ),
        "business_categories_unparsed": _text(
            item.get("businessCategoriesUnparsed")
        ),
        "business_categories": list(categories),
        "tags": list(tags),
        "selected_query_context": dict(query_context),
        "court_locator_candidates": court_locator_candidates,
        "source_row": {
            "native_page": native_page,
            "native_row": native_row,
            "native_page_size": page.page_size,
            "native_result_count": page.result_count,
            "native_total_pages": page.total_pages,
            "native_total_results": page.total_results,
            "source_has_more_results": page.has_more_results,
            "continuation_basis": "currentPage_less_than_totalPages",
        },
        "retrieval": {
            "selected_sort_option": page.selected_sort_option,
            "sort_by_options": list(page.sort_by_options),
            "facets": _facet_summaries(page.facets),
            "response_schema_fingerprint": source_schema_fingerprint,
        },
        "source_url": source_url,
        "raw_source_record": dict(item),
    }


class MichiganBusinessCourtClient:
    """Client for the anonymous official search endpoint and PDF artifacts."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            backoff_initial=0.5,
        )
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
        last_error: MichiganBusinessCourtError | None = None
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
                last_error = MichiganBusinessCourtTransportError(
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
                    "response_text": str(
                        getattr(response, "text", "")
                    )[:500],
                }
                if status_code == 429:
                    last_error = MichiganBusinessCourtRateLimited(
                        "Michigan Business Court source rate limited the request",
                        url=effective_url,
                        details=details,
                    )
                elif status_code in {401, 403}:
                    last_error = MichiganBusinessCourtRestricted(
                        "Michigan Business Court source denied the request",
                        url=effective_url,
                        details=details,
                    )
                elif status_code == 404:
                    last_error = MichiganBusinessCourtSourceChanged(
                        "Michigan Business Court endpoint was not found",
                        url=effective_url,
                        details=details,
                    )
                elif status_code >= 500:
                    last_error = MichiganBusinessCourtTransportError(
                        f"Michigan Business Court source returned HTTP {status_code}",
                        url=effective_url,
                        details=details,
                    )
                else:
                    last_error = MichiganBusinessCourtHTTPError(
                        f"Michigan Business Court source returned HTTP {status_code}",
                        url=effective_url,
                        details=details,
                    )
            assert last_error is not None
            retryable_status = (
                isinstance(last_error, MichiganBusinessCourtRateLimited)
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
        effective_url = str(getattr(response, "url", url) or url)
        content = bytes(getattr(response, "content", b"") or b"")
        content_type = _text(
            getattr(response, "headers", {}).get("Content-Type")
        )
        if content_type is not None and "json" not in content_type.casefold():
            raise MichiganBusinessCourtSourceChanged(
                "Business Court endpoint did not identify a JSON response",
                url=effective_url,
                details={"content_type": content_type},
            )
        if content and not content.lstrip().startswith(b"{"):
            raise MichiganBusinessCourtSourceChanged(
                "Business Court response lacks a JSON object signature",
                url=effective_url,
                details={"content_type": content_type},
            )
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise MichiganBusinessCourtSourceChanged(
                "Business Court endpoint did not return valid JSON",
                url=effective_url,
                details={"content_type": content_type},
            ) from error
        if not isinstance(payload, Mapping):
            raise MichiganBusinessCourtSourceChanged(
                "Business Court JSON response must be an object",
                url=effective_url,
            )
        return payload, effective_url

    @staticmethod
    def _search_params(
        *,
        query_text: str,
        page: int,
        sort_order: str,
        business_courts: Sequence[str],
        courts: Sequence[str],
        audience: str | None,
    ) -> dict[str, Any]:
        if sort_order not in SORT_ORDERS:
            raise MichiganBusinessCourtSelectionError(
                "unsupported Business Court sort order",
                details={"sort_order": sort_order, "supported": SORT_ORDERS},
            )
        if page <= 0:
            raise MichiganBusinessCourtSelectionError(
                "page must be positive"
            )
        params: dict[str, Any] = {
            "searchQuery": query_text,
            "page": page,
            "sortOrder": sort_order,
        }
        if business_courts:
            params[BUSINESS_CATEGORY_QUERY_KEY] = ",".join(business_courts)
        if courts:
            params[COURT_QUERY_KEY] = ",".join(courts)
        if audience:
            params["audience"] = audience
        return params

    def fetch_page(
        self,
        *,
        query_text: str,
        page: int,
        sort_order: str,
        business_courts: Sequence[str] = (),
        courts: Sequence[str] = (),
        audience: str | None = None,
    ) -> BusinessCourtPage:
        params = self._search_params(
            query_text=query_text,
            page=page,
            sort_order=sort_order,
            business_courts=business_courts,
            courts=courts,
            audience=audience,
        )
        payload, source_url = self._json(SEARCH_URL, params=params)
        parsed = parse_search_payload(
            payload,
            requested_page=page,
            source_url=source_url,
        )
        if (
            parsed.selected_sort_option is not None
            and parsed.selected_sort_option != sort_order
        ):
            raise MichiganBusinessCourtSourceChanged(
                "source selected a different sort order than requested",
                url=source_url,
                details={
                    "requested_sort_order": sort_order,
                    "selected_sort_option": parsed.selected_sort_option,
                },
            )
        return parsed

    def search(
        self,
        *,
        query_text: str,
        sort_order: str,
        business_courts: Sequence[str],
        courts: Sequence[str],
        audience: str | None,
        start_page: int,
        start_offset: int,
        limit: int | None,
        selection_fingerprint: str,
    ) -> BusinessCourtCollection:
        records: list[Mapping[str, Any]] = []
        source_urls: list[str] = []
        fingerprints: list[str] = []
        page_number = start_page
        offset = start_offset
        pages_fetched = 0
        total_results = 0
        total_pages = 0
        next_page: int | None = None
        next_offset = 0
        incomplete_error: MichiganBusinessCourtError | None = None
        query_context = {
            "query_text": query_text,
            "sort_order": sort_order,
            "business_courts": list(business_courts),
            "courts": list(courts),
            "audience": audience,
        }

        while limit is None or len(records) < limit:
            try:
                page = self.fetch_page(
                    query_text=query_text,
                    page=page_number,
                    sort_order=sort_order,
                    business_courts=business_courts,
                    courts=courts,
                    audience=audience,
                )
            except MichiganBusinessCourtError as error:
                if not records:
                    raise
                incomplete_error = error
                next_page = page_number
                next_offset = offset
                break
            pages_fetched += 1
            total_results = page.total_results
            total_pages = page.total_pages
            source_urls.append(page.source_url)
            fingerprints.append(page.schema_fingerprint)
            if offset > len(page.records):
                raise MichiganBusinessCourtSelectionError(
                    "cursor offset exceeds the source page",
                    details={
                        "offset": offset,
                        "page_records": len(page.records),
                    },
                )
            remaining = (
                None if limit is None else limit - len(records)
            )
            source_slice = (
                page.records[offset:]
                if remaining is None
                else page.records[offset : offset + remaining]
            )
            records.extend(
                normalize_search_item(
                    item,
                    source_url=page.source_url,
                    source_schema_fingerprint=page.schema_fingerprint,
                    native_page=page.current_page,
                    native_row=index + 1,
                    page=page,
                    query_context=query_context,
                    selection_fingerprint=selection_fingerprint,
                )
                for index, item in enumerate(
                    source_slice,
                    start=offset,
                )
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

        return BusinessCourtCollection(
            records=tuple(records),
            pages_fetched=pages_fetched,
            total_results=total_results,
            total_pages=total_pages,
            next_page=next_page,
            next_offset=next_offset,
            source_urls=tuple(source_urls),
            schema_fingerprints=tuple(fingerprints),
            incomplete_error=incomplete_error,
        )

    def download(
        self,
        value: str,
        *,
        max_bytes: int | None = None,
    ) -> BusinessCourtDocument:
        url = _official_pdf_url(value, caller_selected=True)
        response = self._request(url, accept="application/pdf")
        effective_url = _official_pdf_url(
            str(getattr(response, "url", url) or url)
        )
        content = bytes(getattr(response, "content", b"") or b"")
        content_type = _text(
            getattr(response, "headers", {}).get("Content-Type")
        )
        if max_bytes is not None and len(content) > max_bytes:
            raise MichiganBusinessCourtSelectionError(
                "download exceeds the caller-selected byte limit",
                url=effective_url,
                details={
                    "content_length": len(content),
                    "max_bytes": max_bytes,
                },
            )
        if (
            content_type is None
            or "application/pdf" not in content_type.casefold()
            or not content.startswith(b"%PDF-")
        ):
            raise MichiganBusinessCourtSourceChanged(
                "Business Court document response is not a PDF",
                url=effective_url,
                details={
                    "content_type": content_type,
                    "signature_hex": content[:8].hex(),
                },
            )
        native_document_id, filename = _document_identity(effective_url)
        del native_document_id
        return BusinessCourtDocument(
            source_url=effective_url,
            content=content,
            media_type="application/pdf",
            filename=filename,
            sha256=hashlib.sha256(content).hexdigest(),
        )


def _facet_records(
    page: BusinessCourtPage,
    *,
    query_string_key: str,
    record_kind: str,
) -> list[dict[str, Any]]:
    facet = _facet_by_key(page.facets, query_string_key)
    records: list[dict[str, Any]] = []
    for index, value in enumerate(facet.values):
        label = _facet_value_label(value)
        occurrence_basis = {
            "query_string_key": facet.query_string_key,
            "value_index": index,
            "raw_value": value,
        }
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": record_kind,
                "source_occurrence_id": sha256_fingerprint(
                    occurrence_basis
                ),
                "facet_name": facet.name,
                "query_string_key": facet.query_string_key,
                "value_index": index,
                "label": label,
                "selected": value in facet.selected_values,
                "raw_facet_value": value,
                "source_total_results": page.total_results,
                "source_total_pages": page.total_pages,
                "source_url": page.source_url,
                "response_schema_fingerprint": page.schema_fingerprint,
            }
        )
    return records


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    command = str(args.command)
    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    cursor = getattr(args, "cursor", None)
    if command == "search":
        parameters = {
            "query_text": args.query_text,
            "sort_order": args.sort_order,
            "business_courts": list(args.business_courts or []),
            "courts": list(args.courts or []),
            "audience": args.audience,
            "start_page": args.page,
            "native_page_size": NATIVE_PAGE_SIZE,
        }
        requested_limit = args.limit
    elif command in {"categories", "sources"}:
        parameters = {"audience": args.audience}
    elif command == "download":
        parameters = {
            "document_url": args.document_url,
            "destination": str(args.destination),
            "expected_sha256": args.expected_sha256,
            "max_bytes": args.max_bytes,
        }
    elif command == "probe":
        parameters = {"zero_query": args.zero_query}
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
    error: MichiganBusinessCourtError,
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
    client: MichiganBusinessCourtClient | Any,
) -> PublicRecordsResult:
    business_courts = tuple(args.business_courts or ())
    courts = tuple(args.courts or ())
    fingerprint = _selection_fingerprint(
        query_text=args.query_text,
        sort_order=args.sort_order,
        business_courts=business_courts,
        courts=courts,
        audience=args.audience,
    )
    start_page = args.page
    start_offset = 0
    if args.cursor:
        start_page, start_offset = parse_cursor(
            args.cursor,
            selection_fingerprint=fingerprint,
        )
    collection = client.search(
        query_text=args.query_text,
        sort_order=args.sort_order,
        business_courts=business_courts,
        courts=courts,
        audience=args.audience,
        start_page=start_page,
        start_offset=start_offset,
        limit=args.limit,
        selection_fingerprint=fingerprint,
    )
    next_cursor = (
        make_cursor(
            page=collection.next_page,
            offset=collection.next_offset,
            selection_fingerprint=fingerprint,
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


def _execute_facet_command(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: MichiganBusinessCourtClient | Any,
) -> PublicRecordsResult:
    page = client.fetch_page(
        query_text="",
        page=1,
        sort_order="Relevance",
        audience=args.audience,
    )
    if args.command == "categories":
        query_string_key = BUSINESS_CATEGORY_QUERY_KEY
        record_kind = "business_court_category_facet"
    else:
        query_string_key = COURT_QUERY_KEY
        record_kind = "business_court_source_facet"
    records = _facet_records(
        page,
        query_string_key=query_string_key,
        record_kind=record_kind,
    )
    return PublicRecordsResult.success(
        query,
        records,
        raw_artifact_refs=[page.source_url],
        warnings=SOURCE_WARNINGS,
    )


def _execute_download(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: MichiganBusinessCourtClient | Any,
) -> PublicRecordsResult:
    document = client.download(
        args.document_url,
        max_bytes=args.max_bytes,
    )
    if (
        args.expected_sha256
        and document.sha256.casefold() != args.expected_sha256.casefold()
    ):
        raise MichiganBusinessCourtSelectionError(
            "download SHA-256 does not match the caller-supplied digest",
            url=document.source_url,
            details={
                "expected_sha256": args.expected_sha256.casefold(),
                "observed_sha256": document.sha256,
            },
        )
    destination = Path(args.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(document.content)
    native_document_id, _filename = _document_identity(document.source_url)
    record = {
        "source_id": SOURCE_ID,
        "record_kind": "downloaded_business_court_document",
        "native_document_id": native_document_id,
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
        raw_artifact_refs=[
            document.source_url,
            str(destination.resolve()),
        ],
        warnings=SOURCE_WARNINGS,
    )


def _execute_probe(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: MichiganBusinessCourtClient | Any,
) -> PublicRecordsResult:
    page = client.fetch_page(
        query_text="",
        page=1,
        sort_order="Oldest",
    )
    zero_page = client.fetch_page(
        query_text=args.zero_query,
        page=1,
        sort_order="Relevance",
    )
    if zero_page.result_count != 0 or zero_page.total_results != 0:
        raise MichiganBusinessCourtSourceChanged(
            "Business Court zero-result sentinel unexpectedly matched records",
            url=zero_page.source_url,
            details={
                "query": args.zero_query,
                "result_count": zero_page.result_count,
                "total_results": zero_page.total_results,
            },
        )
    if not page.records:
        raise MichiganBusinessCourtSourceChanged(
            "Business Court full-corpus probe returned no documents",
            url=page.source_url,
        )
    document = client.download(str(page.records[0]["url"]))
    category_facet = _facet_by_key(
        page.facets,
        BUSINESS_CATEGORY_QUERY_KEY,
    )
    court_facet = _facet_by_key(page.facets, COURT_QUERY_KEY)
    record = {
        "source_id": SOURCE_ID,
        "record_kind": "business_court_source_probe",
        "search_contract": {
            "source_url": page.source_url,
            "native_page_size": page.page_size,
            "total_results": page.total_results,
            "total_pages": page.total_pages,
            "result_count": page.result_count,
            "source_has_more_results": page.has_more_results,
            "continuation_basis": "currentPage_less_than_totalPages",
            "sort_by_options": list(page.sort_by_options),
            "category_facet_count": len(category_facet.values),
            "court_facet_count": len(court_facet.values),
            "facets": _facet_summaries(page.facets),
            "schema_fingerprint": page.schema_fingerprint,
        },
        "zero_result_contract": {
            "query": args.zero_query,
            "result_count": zero_page.result_count,
            "total_results": zero_page.total_results,
            "total_pages": zero_page.total_pages,
            "schema_fingerprint": zero_page.schema_fingerprint,
        },
        "document_contract": {
            "source_url": document.source_url,
            "filename": document.filename,
            "media_type": document.media_type,
            "content_length": len(document.content),
            "sha256": document.sha256,
            "signature_hex": document.content[:8].hex(),
        },
        "source_url": LANDING_URL,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[
            page.source_url,
            zero_page.source_url,
            document.source_url,
        ],
        warnings=SOURCE_WARNINGS,
    )


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
) -> None:
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
    client: MichiganBusinessCourtClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Michigan Business Court source operation."""

    try:
        query = build_query(args)
    except (TypeError, ValueError) as error:
        query = PublicRecordsQuery(
            source=SOURCE_METADATA,
            jurisdiction=JURISDICTION,
            query=QueryMetadata(
                operation=str(args.command),
                parameters={"raw_arguments": dict(vars(args))},
            ),
        )
        return _failure(
            query,
            MichiganBusinessCourtSelectionError(str(error)),
        )

    source_client = client or MichiganBusinessCourtClient(
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
            result = _execute_search(args, query, source_client)
        elif args.command in {"categories", "sources"}:
            result = _execute_facet_command(args, query, source_client)
        elif args.command == "download":
            result = _execute_download(args, query, source_client)
        elif args.command == "probe":
            result = _execute_probe(args, query, source_client)
        else:
            raise MichiganBusinessCourtSelectionError(
                f"unsupported command: {args.command}"
            )
    except MichiganBusinessCourtError as error:
        result = _failure(query, error)
    except (TypeError, ValueError, KeyError) as error:
        result = _failure(
            query,
            MichiganBusinessCourtSourceChanged(
                f"Michigan Business Court normalization failed: {error}"
            ),
        )
    finally:
        if owns_client:
            source_client.close()
    if log_results:
        _best_effort_log(query, result)
    return result


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Michigan Business Court {args.command} "
            f"({result.status.value}, {len(result.records)} records)"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Michigan Business Court {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("title")
            or record.get("label")
            or record.get("filename")
            or record.get("record_kind")
        )
        print(f"  {label}")
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


def _sha256(value: str) -> str:
    normalized = value.casefold()
    if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
        raise argparse.ArgumentTypeError(
            "must be a 64-character hexadecimal SHA-256"
        )
    return normalized


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
        description=(
            "Query Michigan's official Business Court document collection"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser(
        "search",
        help="Search and traverse official Business Court documents",
    )
    search.add_argument("query_text", nargs="?", default="")
    search.add_argument(
        "--sort",
        dest="sort_order",
        choices=SORT_ORDERS,
        default="Relevance",
    )
    search.add_argument(
        "--business-court",
        dest="business_courts",
        action="append",
        help="Repeat to OR multiple native business-category facets",
    )
    search.add_argument(
        "--court",
        dest="courts",
        action="append",
        help="Repeat to OR multiple native court facets",
    )
    search.add_argument("--audience")
    search.add_argument("--page", type=_positive_int, default=1)
    search.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-selected result count",
    )
    search.add_argument("--cursor")
    _add_runtime(search)

    for command, help_text in (
        ("categories", "List native Business Court category facets"),
        ("sources", "List native lower-court source facets"),
    ):
        facet_parser = sub.add_parser(command, help=help_text)
        facet_parser.add_argument("--audience")
        _add_runtime(facet_parser)

    download = sub.add_parser(
        "download",
        help="Download and validate an official Business Court PDF",
    )
    download.add_argument("document_url")
    download.add_argument("destination", type=Path)
    download.add_argument("--expected-sha256", type=_sha256)
    download.add_argument(
        "--max-bytes",
        type=_positive_int,
        help="Optional caller-selected download byte limit",
    )
    _add_runtime(download)

    probe = sub.add_parser(
        "probe",
        help="Verify search, facet, zero-result, and PDF contracts",
    )
    probe.add_argument("--zero-query", default=PROBE_ZERO_QUERY)
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
