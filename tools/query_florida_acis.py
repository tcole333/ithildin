#!/usr/bin/env python3
"""Query Florida's public Appellate Case Information System (ACIS).

ACIS is the shared public case-information system for the Supreme Court of
Florida and the six District Courts of Appeal.  The public portal is backed by
an anonymous JSON API that exposes court metadata, case and party indexes,
dockets, appellate calendar events and their case hearings, public-document
metadata, full-text document search, and publications.

Examples:
    uv run python tools/query_florida_acis.py courts
    uv run python tools/query_florida_acis.py party-search "EXAMPLE LLC"
    uv run python tools/query_florida_acis.py case-search SC2026-0899
    uv run python tools/query_florida_acis.py case SC2026-0899 \
        --court 68f021c4-6a44-4735-9a76-5360b2e8af13 --documents
    uv run python tools/query_florida_acis.py calendar \
        --after 2026-08-18 --before 2026-08-19 \
        --session-type "Oral Argument"
    uv run python tools/query_florida_acis.py document-search "motion"
    uv run python tools/query_florida_acis.py download \
        COURT_UUID CASE_UUID DOCUMENT_UUID document.pdf
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
        acquisition_result_status,
    )
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
    )
    from tools.public_records_http import (
        HTTPStatusError,
        PaginatedFetch,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
    )
    from tools.public_records_store import canonical_court_ref
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
        acquisition_result_status,
    )
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
    )
    from public_records_http import (
        HTTPStatusError,
        PaginatedFetch,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
    )
    from public_records_store import canonical_court_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-fl-acis"
STATE_GEOID = "12"
STATE_CODE = "FL"
PORTAL_ROOT = "https://acis.flcourts.gov/portal"
PORTAL_HOME = f"{PORTAL_ROOT}/home"
PORTAL_SEARCH = f"{PORTAL_ROOT}/search"
USER_GUIDE_URL = (
    "https://www.flcourts.gov/content/download/861390/file/"
    "ACIS-User-Guide.pdf"
)
API_ROOT = "https://acis-api.flcourts.gov"
COURTS_URL = f"{API_ROOT}/courts"
CASE_SEARCH_URL = f"{API_ROOT}/courts/cms/cases"
PARTY_SEARCH_URL = f"{API_ROOT}/courts/cms/parties"
DOCUMENT_SEARCH_URL = f"{API_ROOT}/courts/cms/docketentrydocuments"
DOCUMENT_ACCESS_URL = f"{API_ROOT}/courts/cms/docketentrydocumentsaccess"
PUBLICATION_SEARCH_URL = f"{API_ROOT}/courts/cms/publications"
EVENT_SEARCH_URL = f"{API_ROOT}/courts/cms/events"
SESSION_TYPES_URL = f"{API_ROOT}/cms/courtsessiontypes"

QUERY_TYPES = {
    "starts": "10461",
    "exact": "10462",
    "contains": "10463",
    "match": "300054",
    "phonetic": "300055",
}
CASE_QUERY_MODES = frozenset({"starts", "exact", "contains"})
PARTY_QUERY_MODES = frozenset({"match", "phonetic"})

DOCUMENT_STATE_VIEWABLE = "b64d1d1e-f926-4c87-ab6b-df5c96d3b186"
DOCUMENT_STATE_IN_CART = "e069220c-7377-4b6a-8664-15f29da6808a"
DOCUMENT_STATE_PURCHASABLE = "dc195201-c792-4883-ab2a-5730dc357ca2"
DOCUMENT_STATE_UNAVAILABLE = "ea5979e2-9949-4819-819b-72f9ef7f7106"
DOCUMENT_STATES = {
    DOCUMENT_STATE_VIEWABLE: "viewable",
    DOCUMENT_STATE_IN_CART: "in_cart",
    DOCUMENT_STATE_PURCHASABLE: "purchasable",
    DOCUMENT_STATE_UNAVAILABLE: "unavailable",
}
FLORIDA_PORTAL_TIMEZONE = ZoneInfo("America/New_York")
ACIS_MAX_PAGE_SIZE = 500

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Florida Appellate Case Information System",
    source_role="appellate_case_docket_calendar_and_document_portal",
    base_url=PORTAL_HOME,
    dataset_id="acis-public",
    metadata={
        "authority": "Florida State Courts System",
        "coverage": "Florida Supreme Court and six District Courts of Appeal",
        "state_code": STATE_CODE,
        "access_class": "B",
        "authentication": "none_for_public_search_and_public_documents",
        "operations": [
            "court_directory",
            "case_and_party_search",
            "case_docket_and_documents",
            "appellate_calendar_and_event_hearings",
            "publications",
        ],
    },
)

SOURCE_WARNINGS = (
    "ACIS covers Florida appellate courts; county trial-court records remain "
    "with the applicable clerks.",
    "Document availability reflects the access state returned by ACIS for "
    "the current public session.",
)


@dataclass(frozen=True)
class ACISCourt:
    """One court from the ACIS public directory."""

    resource_uuid: str
    external_id: str
    display_name: str
    active: bool
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class ACISDocumentDownload:
    """Validated public PDF returned by ACIS."""

    content: bytes
    media_type: str
    filename: str
    source_url: str
    etag: str | None = None


class ACISSelectionError(ValueError):
    """A selector could not be resolved to one source record."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})
        self.status = status


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise ValueError(f"ACIS {field_name} must not be blank")
    return normalized


def _integer(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> str | None:
    raw = _text(value)
    if raw is None:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", raw)
    return match.group(1) if match else raw


def _acis_datetime(value: str, *, end_of_day: bool) -> str:
    """Expand a calendar date to the offset datetime expected by ACIS."""
    raw = _required_text(value, "date filter")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    try:
        calendar_date = date.fromisoformat(raw)
    except ValueError as error:
        raise ACISSelectionError(
            "invalid_date_filter",
            f"Invalid ISO calendar date: {raw}",
            details={"value": raw},
        ) from error
    boundary = time(23, 59, 59, 999999) if end_of_day else time.min
    return datetime.combine(
        calendar_date,
        boundary,
        tzinfo=FLORIDA_PORTAL_TIMEZONE,
    ).isoformat(timespec="milliseconds")


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def _response_text(response: Any) -> str:
    value = getattr(response, "text", "")
    return value if isinstance(value, str) else str(value)


def _embedded_records(payload: Any, *, url: str) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "ACIS paginated response must be an object",
            url=url,
        )
    embedded = payload.get("_embedded")
    if embedded is None:
        page = payload.get("page")
        if (
            isinstance(page, Mapping)
            and _integer(page.get("totalElements")) == 0
        ):
            return []
    if not isinstance(embedded, Mapping):
        raise SourceSchemaError(
            "ACIS paginated response lacks _embedded",
            url=url,
        )
    records = embedded.get("results")
    if not isinstance(records, list) or any(
        not isinstance(record, Mapping) for record in records
    ):
        raise SourceSchemaError(
            "ACIS paginated response lacks an object results array",
            url=url,
        )
    return list(records)


def _page_metadata(payload: Mapping[str, Any], *, url: str) -> dict[str, int]:
    page = payload.get("page")
    if not isinstance(page, Mapping):
        raise SourceSchemaError(
            "ACIS paginated response lacks page metadata",
            url=url,
        )
    metadata: dict[str, int] = {}
    for key in ("size", "totalElements", "totalPages", "number"):
        value = _integer(page.get(key))
        if value is None or value < 0:
            raise SourceSchemaError(
                f"ACIS page metadata lacks numeric {key}",
                url=url,
            )
        metadata[key] = value
    return metadata


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    prefix = "acis:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError("ACIS cursor must have form acis:offset:N")
    return int(cursor[len(prefix) :])


def _positive(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


class FloridaACISClient(_BaseJSONClient):
    """Transport-injectable client for the public ACIS JSON and PDF routes."""

    def __init__(
        self,
        *args: Any,
        maximum_page_size: int = ACIS_MAX_PAGE_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.maximum_page_size = (
            _positive(maximum_page_size, "maximum_page_size")
            or ACIS_MAX_PAGE_SIZE
        )
        self._courts: tuple[ACISCourt, ...] | None = None
        self._session_types: tuple[Mapping[str, Any], ...] | None = None

    def _bounded_page_size(self, page_size: int) -> int:
        return min(
            _positive(page_size, "page_size") or self.maximum_page_size,
            self.maximum_page_size,
        )

    def _fetch_hal(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        requested_limit: int | None,
        page_size: int,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        page_size = _positive(page_size, "page_size") or 100
        requested_limit = _positive(requested_limit, "requested_limit")
        max_records = _positive(max_records, "max_records")
        start_offset = _cursor_offset(cursor)
        effective_limit = requested_limit
        truncated_by_cap = False
        warnings: list[str] = []
        if max_records is not None and (
            effective_limit is None or max_records < effective_limit
        ):
            effective_limit = max_records
            truncated_by_cap = True
            warnings.append(
                f"Result collection stopped at the caller-selected "
                f"--max-records value ({max_records})."
            )

        records: list[Mapping[str, Any]] = []
        current_offset = start_offset
        source_page_size = page_size
        total_elements: int | None = None
        pages_fetched = 0
        initial_request_count = self.request_count
        while effective_limit is None or len(records) < effective_limit:
            page_number = current_offset // source_page_size
            request_params = {
                **dict(params or {}),
                "page": page_number,
                "size": page_size,
            }
            payload = self._request_json(url, params=request_params)
            page_records = _embedded_records(payload, url=url)
            metadata = _page_metadata(payload, url=url)
            pages_fetched += 1
            total_elements = metadata["totalElements"]
            reported_page_size = metadata["size"]
            if reported_page_size > 0 and reported_page_size != source_page_size:
                source_page_size = reported_page_size
                corrected_page = current_offset // source_page_size
                if corrected_page != page_number:
                    continue
            within_page = current_offset % source_page_size

            available = page_records[within_page:]
            remaining = (
                None
                if effective_limit is None
                else effective_limit - len(records)
            )
            selected = available if remaining is None else available[:remaining]
            records.extend(selected)
            current_offset += len(selected)

            if not selected:
                break
            if current_offset >= total_elements:
                break
            if remaining is not None and len(selected) >= remaining:
                break
            if within_page + len(selected) < len(page_records):
                continue
            if len(page_records) < source_page_size:
                break

        source_has_more = (
            total_elements is not None and current_offset < total_elements
        )
        if truncated_by_cap and not source_has_more:
            truncated_by_cap = False
            warnings = []
        observed_schema = inferred_schema(records)
        return PaginatedFetch(
            records=tuple(records),
            next_cursor=(
                f"acis:offset:{current_offset}" if source_has_more else None
            ),
            schema=observed_schema,
            schema_fingerprint=schema_fingerprint(observed_schema),
            pages_fetched=pages_fetched,
            requests_made=self.request_count - initial_request_count,
            truncated_by_cap=truncated_by_cap and source_has_more,
            warnings=tuple(warnings),
        )

    def list_courts(self, *, page: int = 0, size: int = 100) -> PaginatedFetch:
        if isinstance(page, bool) or page < 0:
            raise ValueError("page must not be negative")
        size = _positive(size, "size") or 100
        fetched = self._fetch_hal(
            COURTS_URL,
            params={"fields": "*,locations(*)"},
            requested_limit=size,
            page_size=size,
            cursor=f"acis:offset:{page * size}",
        )
        if page == 0 and fetched.next_cursor is None:
            self._courts = tuple(
                self._court_from_record(record) for record in fetched.records
            )
        return fetched

    @staticmethod
    def _court_from_record(record: Mapping[str, Any]) -> ACISCourt:
        return ACISCourt(
            resource_uuid=_required_text(
                record.get("resourceID"),
                "court resourceID",
            ),
            external_id=_required_text(
                record.get("externalIdentifier"),
                "court externalIdentifier",
            ),
            display_name=_required_text(
                record.get("displayName"),
                "court displayName",
            ),
            active=bool(record.get("active", True)),
            raw=dict(record),
        )

    def courts(self) -> tuple[ACISCourt, ...]:
        if self._courts is None:
            fetched = self._fetch_hal(
                COURTS_URL,
                params={"fields": "*,locations(*)"},
                requested_limit=None,
                page_size=100,
            )
            self._courts = tuple(
                self._court_from_record(record) for record in fetched.records
            )
        return self._courts

    def resolve_court(self, selector: str) -> ACISCourt:
        value = _required_text(selector, "court selector")
        folded = value.casefold()
        exact = [
            court
            for court in self.courts()
            if value in {court.resource_uuid, court.external_id}
            or folded == court.display_name.casefold()
        ]
        if len(exact) == 1:
            return exact[0]
        partial = [
            court
            for court in self.courts()
            if folded in court.display_name.casefold()
        ]
        if len(partial) == 1:
            return partial[0]
        if len(exact) > 1 or len(partial) > 1:
            matches = exact or partial
            raise ACISSelectionError(
                "ambiguous_court_selector",
                f"ACIS court selector {value!r} matches multiple courts",
                details={
                    "matches": [
                        {
                            "resource_uuid": court.resource_uuid,
                            "external_id": court.external_id,
                            "display_name": court.display_name,
                        }
                        for court in matches
                    ]
                },
            )
        raise ACISSelectionError(
            "court_not_found",
            f"ACIS court selector {value!r} did not match the public directory",
            details={"selector": value},
        )

    def court_by_external_id(self, external_id: Any) -> ACISCourt:
        value = _required_text(external_id, "case courtID")
        matches = [
            court for court in self.courts() if court.external_id == value
        ]
        if len(matches) != 1:
            raise SourceSchemaError(
                f"ACIS case references unknown courtID {value!r}",
                url=COURTS_URL,
            )
        return matches[0]

    def search_cases(
        self,
        query: str,
        *,
        field: str = "auto",
        match_mode: str = "contains",
        court: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        case_type_id: str | None = None,
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        page_size = self._bounded_page_size(page_size)
        selector = _required_text(query, "case query")
        if match_mode not in CASE_QUERY_MODES:
            raise ValueError(
                "case match_mode must be starts, exact, or contains"
            )
        if field == "auto":
            field = (
                "number"
                if re.search(r"(?:SC|[1-6]D)?\d{4}-\d{4}$", selector, re.I)
                else "title"
            )
        if field not in {"number", "title"}:
            raise ValueError("case search field must be auto, number, or title")
        prefix = (
            "caseHeader.caseNumber"
            if field == "number"
            else "caseHeader.caseTitle"
        )
        params: dict[str, Any] = {
            prefix: selector,
            f"{prefix}SearchType": QUERY_TYPES[match_mode],
            "sort": "caseHeader.filedDate,desc",
        }
        if court is not None:
            params["caseHeader.courtID"] = self.resolve_court(
                court
            ).resource_uuid
        if filed_after:
            params["caseHeader.filedDateFrom"] = _acis_datetime(
                filed_after,
                end_of_day=False,
            )
        if filed_before:
            params["caseHeader.filedDateTo"] = _acis_datetime(
                filed_before,
                end_of_day=True,
            )
        if case_type_id:
            params["caseHeader.caseTypeID"] = case_type_id
        return self._fetch_hal(
            CASE_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def search_parties(
        self,
        party_name: str,
        *,
        match_mode: str = "match",
        court: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        case_type_id: str | None = None,
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        page_size = self._bounded_page_size(page_size)
        selector = _required_text(party_name, "party name")
        if match_mode not in PARTY_QUERY_MODES:
            raise ValueError("party match_mode must be match or phonetic")
        params: dict[str, Any] = {
            "partyHeader.partyActorInstance.displayName": selector,
            "partyHeader.partyActorInstance.displayNameSearchType": (
                QUERY_TYPES[match_mode]
            ),
            "sort": "score,desc",
        }
        if court is not None:
            params["caseHeader.courtID"] = self.resolve_court(
                court
            ).resource_uuid
        if filed_after:
            params["caseHeader.filedDateFrom"] = _acis_datetime(
                filed_after,
                end_of_day=False,
            )
        if filed_before:
            params["caseHeader.filedDateTo"] = _acis_datetime(
                filed_before,
                end_of_day=True,
            )
        if case_type_id:
            params["caseHeader.caseTypeID"] = case_type_id
        return self._fetch_hal(
            PARTY_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def get_case(
        self,
        court_resource_uuid: str,
        case_uuid: str,
    ) -> Mapping[str, Any]:
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"cases/{quote(identifier, safe='')}"
        )
        payload = self._request_json(url, params={})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "ACIS case detail must be an object",
                url=url,
            )
        return payload

    def case_parties(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        page_size = self._bounded_page_size(page_size)
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"cases/{quote(identifier, safe='')}/parties"
        )
        return self._fetch_hal(
            url,
            params={"sort": ["orderBy,asc", "partyNumber,asc"]},
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def docket_entries(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        page_size = self._bounded_page_size(page_size)
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"cases/{quote(identifier, safe='')}/docketentries"
        )
        return self._fetch_hal(
            url,
            params={"sort": "docketEntryHeader.filedDate,desc"},
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def case_documents(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        document_uuid: str | None = None,
        docket_entry_uuid: str | None = None,
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        page_size = self._bounded_page_size(page_size)
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        params: dict[str, Any] = {
            "caseHeader.courtID": court.resource_uuid,
            "caseHeader.caseInstanceUUID": identifier,
            "sort": "documentName,asc",
        }
        if document_uuid:
            params["documentLinkUUID"] = document_uuid
        if docket_entry_uuid:
            params["docketEntryHeader.docketEntryUUID"] = docket_entry_uuid
        return self._fetch_hal(
            DOCUMENT_ACCESS_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def search_documents(
        self,
        query: str,
        *,
        text_mode: str = "any",
        court: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        case_type_id: str | None = None,
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        page_size = self._bounded_page_size(page_size)
        selector = _required_text(query, "document query")
        text_fields = {
            "any": "anyOfTheseWords",
            "all": "allOfTheseWords",
            "exact": "thisExactPhrase",
            "none": "noneOfTheseWords",
        }
        if text_mode not in text_fields:
            raise ValueError(
                "document text_mode must be any, all, exact, or none"
            )
        params: dict[str, Any] = {
            text_fields[text_mode]: selector,
            "sort": "score,desc",
        }
        if court is not None:
            params["caseHeader.courtID"] = self.resolve_court(
                court
            ).resource_uuid
        if filed_after:
            params["docketEntryHeader.docketEntryFiledDateFrom"] = (
                _acis_datetime(filed_after, end_of_day=False)
            )
        if filed_before:
            params["docketEntryHeader.docketEntryFiledDateTo"] = (
                _acis_datetime(filed_before, end_of_day=True)
            )
        if case_type_id:
            params["caseHeader.caseTypeID"] = case_type_id
        return self._fetch_hal(
            DOCUMENT_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def search_publications(
        self,
        query: str | None,
        *,
        court: str | None = None,
        case_number: str | None = None,
        publication_number: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        page_size = self._bounded_page_size(page_size)
        params: dict[str, Any] = {"sort": "publicationDate,desc"}
        if query:
            params["publicationTitle"] = _required_text(
                query,
                "publication query",
            )
        if court is not None:
            params["courtID"] = self.resolve_court(court).resource_uuid
        if case_number:
            params["caseNumber"] = case_number
        if publication_number:
            params["publicationNumber"] = publication_number
        if filed_after:
            params["publicationDateFrom"] = _acis_datetime(
                filed_after,
                end_of_day=False,
            )
        if filed_before:
            params["publicationDateTo"] = _acis_datetime(
                filed_before,
                end_of_day=True,
            )
        if len(params) == 1:
            raise ValueError("publication search requires at least one criterion")
        return self._fetch_hal(
            PUBLICATION_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def session_types(self) -> tuple[Mapping[str, Any], ...]:
        """Return ACIS's public calendar-session taxonomy."""
        if self._session_types is None:
            payload = self._request_json(SESSION_TYPES_URL, params={})
            if not isinstance(payload, list) or any(
                not isinstance(row, Mapping) for row in payload
            ):
                raise SourceSchemaError(
                    "ACIS court-session types response must be an object array",
                    url=SESSION_TYPES_URL,
                )
            normalized = []
            for row in payload:
                _required_text(
                    row.get("courtSessionTypeID"),
                    "court session type ID",
                )
                _required_text(
                    row.get("courtSessionTypeName"),
                    "court session type name",
                )
                normalized.append(dict(row))
            self._session_types = tuple(normalized)
        return self._session_types

    def resolve_session_type(self, selector: str) -> Mapping[str, Any]:
        value = _required_text(selector, "court session type")
        folded = value.casefold()
        exact = [
            row
            for row in self.session_types()
            if value == str(row.get("courtSessionTypeID"))
            or folded
            == str(row.get("courtSessionTypeName") or "").casefold()
        ]
        if len(exact) == 1:
            return exact[0]
        partial = [
            row
            for row in self.session_types()
            if folded
            in str(row.get("courtSessionTypeName") or "").casefold()
        ]
        if len(partial) == 1:
            return partial[0]
        matches = exact or partial
        if matches:
            raise ACISSelectionError(
                "ambiguous_session_type",
                f"ACIS session type {value!r} matches multiple values",
                details={
                    "matches": [
                        {
                            "court_session_type_id": row.get(
                                "courtSessionTypeID"
                            ),
                            "name": row.get("courtSessionTypeName"),
                        }
                        for row in matches
                    ]
                },
            )
        raise ACISSelectionError(
            "session_type_not_found",
            f"ACIS session type {value!r} was not found",
            details={
                "selector": value,
                "available": [
                    row.get("courtSessionTypeName")
                    for row in self.session_types()
                ],
            },
        )

    def search_calendar_events(
        self,
        *,
        court: str | None = None,
        after: str | None = None,
        before: str | None = None,
        session_type: str | None = None,
        event_name: str | None = None,
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        """Search the statewide public appellate calendar-event index."""
        page_size = self._bounded_page_size(page_size)
        params: dict[str, Any] = {"sort": "startDate,asc"}
        if court is not None:
            params["courtID"] = self.resolve_court(court).resource_uuid
        if after:
            params["startDateFrom"] = _acis_datetime(
                after,
                end_of_day=False,
            )
        if before:
            params["startDateTo"] = _acis_datetime(
                before,
                end_of_day=True,
            )
        if session_type:
            session = self.resolve_session_type(session_type)
            params["courtSessionTypeID"] = _required_text(
                session.get("courtSessionTypeID"),
                "court session type ID",
            )
        if event_name:
            params["eventName"] = _required_text(
                event_name,
                "calendar event name",
            )
            params["eventNameSearchType"] = QUERY_TYPES["match"]
        return self._fetch_hal(
            EVENT_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def event_hearings(
        self,
        court_resource_uuid: str,
        event_uuid: str,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        """Fetch every published case hearing attached to one calendar event."""
        page_size = self._bounded_page_size(page_size)
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(event_uuid, "event UUID")
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"events/{quote(identifier, safe='')}/hearings"
        )
        return self._fetch_hal(
            url,
            params={"sort": "orderBy,asc"},
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )

    def get_publication(
        self,
        court_resource_uuid: str,
        publication_uuid: str,
    ) -> Mapping[str, Any]:
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(publication_uuid, "publication UUID")
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"publication/{quote(identifier, safe='')}"
        )
        payload = self._request_json(url, params={})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "ACIS publication detail must be an object",
                url=url,
            )
        return payload

    def _request_binary(self, url: str) -> Any:
        headers = {
            "Accept": "application/pdf",
            "User-Agent": self.user_agent,
        }
        transient_errors = (
            requests.RequestException,
            TimeoutError,
            ConnectionError,
        )
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.transport.request(
                    "GET",
                    url,
                    params={},
                    headers=headers,
                    timeout=self.timeout,
                )
            except transient_errors as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        f"ACIS document request failed after {attempt} "
                        f"attempts: {error}",
                        url=url,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(
                getattr(response, "status_code", getattr(response, "status", 0))
            )
            if status_code in self.retry_policy.retry_statuses:
                retry_after_raw = _header(
                    getattr(response, "headers", {}),
                    "Retry-After",
                )
                try:
                    retry_after = (
                        max(0.0, float(retry_after_raw))
                        if retry_after_raw is not None
                        else None
                    )
                except ValueError:
                    retry_after = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                if status_code == 429:
                    raise RateLimitedHTTPError(
                        status_code,
                        url=url,
                        response_text=_response_text(response),
                    )
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code == 451:
                raise TermsBlockedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code in {404, 410}:
                raise SourceChangedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            return response
        raise TransportError(
            f"ACIS document request failed: {last_error}",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )

    def download_document(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        document_uuid: str,
    ) -> ACISDocumentDownload:
        court = self.resolve_court(court_resource_uuid)
        case_identifier = _required_text(case_uuid, "case UUID")
        document_identifier = _required_text(document_uuid, "document UUID")
        metadata = self.case_documents(
            court.resource_uuid,
            case_identifier,
            document_uuid=document_identifier,
            requested_limit=None,
            page_size=100,
        )
        matches = [
            row
            for row in metadata.records
            if _text(row.get("documentLinkUUID")) == document_identifier
        ]
        if not matches:
            raise ACISSelectionError(
                "document_not_found",
                "ACIS did not list that document for the selected case",
                details={
                    "court_resource_uuid": court.resource_uuid,
                    "case_uuid": case_identifier,
                    "document_uuid": document_identifier,
                },
            )
        if len(matches) > 1:
            raise SourceSchemaError(
                "ACIS returned duplicate document identities",
                url=DOCUMENT_ACCESS_URL,
            )
        source_state_uuid = _text(matches[0].get("userDocumentState"))
        if source_state_uuid != DOCUMENT_STATE_VIEWABLE:
            source_state = DOCUMENT_STATES.get(
                source_state_uuid or "",
                "unknown",
            )
            raise ACISSelectionError(
                "document_not_publicly_viewable",
                f"ACIS reports this document as {source_state}",
                details={
                    "document_uuid": document_identifier,
                    "source_state": source_state,
                    "source_state_uuid": source_state_uuid,
                },
                status=ResultStatus.RESTRICTED,
            )

        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"case/{quote(case_identifier, safe='')}/docketentrydocuments/"
            f"{quote(document_identifier, safe='')}"
        )
        response = self._request_binary(url)
        content = getattr(response, "content", None)
        if not isinstance(content, bytes):
            raise SourceSchemaError(
                "ACIS document response did not expose binary content",
                url=url,
            )
        media_type = (
            _header(getattr(response, "headers", {}), "Content-Type") or ""
        ).split(";", 1)[0].strip().lower()
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise SourceSchemaError(
                "ACIS document response was not a PDF",
                url=url,
                details={
                    "content_type": media_type,
                    "signature_hex": content[:8].hex(),
                },
            )
        filename = f"{document_identifier}.pdf"
        disposition = _header(
            getattr(response, "headers", {}),
            "Content-Disposition",
        )
        if disposition:
            match = re.search(
                r"filename\*?=(?:UTF-8''|[\"']?)([^\"';]+)",
                disposition,
                re.I,
            )
            if match:
                filename = match.group(1).strip()
        return ACISDocumentDownload(
            content=content,
            media_type=media_type,
            filename=filename,
            source_url=url,
            etag=_header(getattr(response, "headers", {}), "ETag"),
        )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(
            getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
        ).expanduser(),
        config_path=Path(
            getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
        ).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _make_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> FloridaACISClient:
    limits = access_contract.get("limits") or {}
    interval = max(
        float(getattr(args, "minimum_interval", 0.25)),
        float(limits.get("minimum_interval_seconds") or 0),
    )
    maximum_page_size = int(
        limits.get("maximum_page_size") or ACIS_MAX_PAGE_SIZE
    )
    return FloridaACISClient(
        session=requests.Session(),
        timeout=float(getattr(args, "timeout", 30.0)),
        retry_policy=RetryPolicy(),
        minimum_interval=interval,
        maximum_page_size=maximum_page_size,
    )


def _court_record(court: ACISCourt, schema: str) -> dict[str, Any]:
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{court.resource_uuid}/court/"
            f"{court.external_id}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "court",
        "court_resource_uuid": court.resource_uuid,
        "native_court_id": court.external_id,
        "name": court.display_name,
        "state_code": STATE_CODE,
        "court_level": "appellate",
        "active": court.active,
        "official_url": PORTAL_HOME,
        "schema_fingerprint": schema,
        "raw": dict(court.raw),
    }


def _court_payload(court: ACISCourt) -> dict[str, Any]:
    return {
        "court_id": court.resource_uuid,
        "native_court_id": court.external_id,
        "name": court.display_name,
        "state_code": STATE_CODE,
        "court_level": "appellate",
        "official_url": PORTAL_HOME,
    }


def _case_url(court: ACISCourt, case_uuid: str) -> str:
    return (
        f"{PORTAL_ROOT}/court/{quote(court.resource_uuid, safe='')}/case/"
        f"{quote(case_uuid, safe='')}"
    )


def _case_record(
    client: FloridaACISClient,
    header: Mapping[str, Any],
    *,
    schema: str,
    parties: Sequence[Mapping[str, Any]] = (),
    docket_entries: Sequence[Mapping[str, Any]] = (),
    documents: Sequence[Mapping[str, Any]] = (),
    search_hit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    case_uuid = _required_text(
        header.get("caseInstanceUUID"),
        "case instance UUID",
    )
    case_number = _required_text(header.get("caseNumber"), "case number")
    court = client.court_by_external_id(header.get("courtID"))
    record = {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court.resource_uuid,
            case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": _court_payload(court),
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_uuid,
        "case_instance_uuid": case_uuid,
        "caption": _text(
            header.get("caseTitle") or header.get("caseCaption")
        ),
        "case_type": _text(
            header.get("caseClassification")
            or header.get("caseCategory")
            or header.get("caseClassGroupType")
        ),
        "filing_date": _date(header.get("filedDate")),
        "status": "closed" if header.get("closedFlag") else "open",
        "access_state": (
            "restricted" if header.get("nonPublicFlag") else "public"
        ),
        "certified_record": False,
        "source_url": _case_url(court, case_uuid),
        "originating_court_cases": list(
            header.get("originatingCourtCases") or []
        ),
        "parties": list(parties),
        "docket_entries": list(docket_entries),
        "documents": list(documents),
        "schema_fingerprint": schema,
        "raw": dict(header),
    }
    if search_hit is not None:
        record["search_hit"] = dict(search_hit)
    return record


def _attorneys(
    legal_representations: Any,
) -> list[dict[str, Any]]:
    if not isinstance(legal_representations, list):
        return []
    attorneys: list[dict[str, Any]] = []
    for representation in legal_representations:
        if not isinstance(representation, Mapping):
            continue
        party_header = (
            representation.get("attorneyPartyHeader")
            or representation.get("legalOrganizationPartyHeader")
        )
        if not isinstance(party_header, Mapping):
            continue
        actor = party_header.get("partyActorInstance")
        if not isinstance(actor, Mapping):
            continue
        name = _text(actor.get("displayName") or actor.get("sortName"))
        if name is None:
            continue
        attorneys.append(
            {
                "raw_name": name,
                "source_internal_id": _text(
                    party_header.get("casePartyUUID")
                ),
                "primary": bool(representation.get("primaryFlag")),
                "raw": dict(representation),
            }
        )
    return attorneys


def _party_record(
    row: Mapping[str, Any],
) -> dict[str, Any]:
    header = row.get("partyHeader")
    if not isinstance(header, Mapping):
        raise ValueError("ACIS party result lacks partyHeader")
    actor = header.get("partyActorInstance")
    if not isinstance(actor, Mapping):
        raise ValueError("ACIS party result lacks party actor")
    name = _required_text(
        actor.get("displayName") or actor.get("sortName"),
        "party display name",
    )
    source_sequence = _integer(row.get("partyNumber"))
    source_identity = _text(header.get("casePartyUUID"))
    if source_sequence is None:
        stable_identity = source_identity or "\x1f".join(
            (
                _text(header.get("partySubType"))
                or _text(header.get("partyType"))
                or "Party",
                name,
            )
        )
        source_sequence = (
            int(
                hashlib.sha256(stable_identity.encode("utf-8")).hexdigest()[
                    :8
                ],
                16,
            )
            or 1
        )
    return {
        "sequence_no": source_sequence,
        "sequence_source": (
            "partyNumber"
            if row.get("partyNumber") not in (None, "")
            else "stable_party_identity"
        ),
        "role": _text(
            header.get("partySubType") or header.get("partyType")
        )
        or "Party",
        "raw_name": name,
        "normalized_name": _text(actor.get("sortName")),
        "source_internal_id": source_identity,
        "status": _text(header.get("partyStatus")),
        "access_state": (
            "restricted" if row.get("nonPublicFlag") else "public"
        ),
        "attorneys": _attorneys(row.get("legalRepresentations")),
        "raw": dict(row),
    }


def _docket_record(row: Mapping[str, Any]) -> dict[str, Any]:
    header = row.get("docketEntryHeader")
    if not isinstance(header, Mapping):
        raise ValueError("ACIS docket result lacks docketEntryHeader")
    identifier = _required_text(
        header.get("docketEntryUUID"),
        "docket entry UUID",
    )
    document_count = _integer(header.get("documentCount")) or 0
    description = _text(
        header.get("docketEntryDescription")
        or header.get("docketEntryName")
        or header.get("docketEntrySubType")
        or header.get("docketEntryType")
    )
    return {
        "native_entry_id": identifier,
        "docket_entry_uuid": identifier,
        "event_code": _text(
            header.get("docketEntrySubTypeID")
            or header.get("docketEntryTypeID")
        ),
        "event_type": _text(header.get("docketEntryType")),
        "event_subtype": _text(header.get("docketEntrySubType")),
        "raw_text": description or "Docket entry",
        "filed_date": _date(header.get("filedDate")),
        "entered_date": _date(header.get("submittedDate")),
        "event_date": _date(header.get("filedDate")),
        "document_available": document_count > 0,
        "document_count": document_count,
        "secured_document": bool(header.get("securedDocument")),
        "access_state": "public",
        "raw": dict(row),
    }


def _document_state(row: Mapping[str, Any]) -> tuple[str, str, str | None]:
    state_uuid = _text(row.get("userDocumentState"))
    state = DOCUMENT_STATES.get(state_uuid or "", "unknown")
    access_state = (
        "public" if state_uuid == DOCUMENT_STATE_VIEWABLE else "restricted"
    )
    return access_state, state, state_uuid


def _document_record(
    client: FloridaACISClient,
    row: Mapping[str, Any],
    *,
    link_to_docket: bool,
) -> dict[str, Any]:
    identifier = _required_text(
        row.get("documentLinkUUID"),
        "document link UUID",
    )
    docket_uuid = _text(row.get("docketEntryUUID"))
    if docket_uuid is None:
        docket_header = row.get("docketEntryHeader")
        if isinstance(docket_header, Mapping):
            docket_uuid = _text(docket_header.get("docketEntryUUID"))
    case_header = row.get("caseHeader")
    if not isinstance(case_header, Mapping):
        case_header = {}
    court: ACISCourt | None = None
    if case_header.get("courtID") is not None:
        court = client.court_by_external_id(case_header.get("courtID"))
    case_uuid = _text(case_header.get("caseInstanceUUID"))
    info = row.get("documentInfo")
    if not isinstance(info, Mapping):
        info = {}
    access_state, source_state, source_state_uuid = _document_state(row)
    source_url = None
    if (
        court is not None
        and case_uuid
        and access_state == "public"
    ):
        source_url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"case/{quote(case_uuid, safe='')}/docketentrydocuments/"
            f"{quote(identifier, safe='')}"
        )
    record = {
        "native_document_id": identifier,
        "document_link_uuid": identifier,
        "docket_entry_uuid": docket_uuid,
        "document_type": _text(
            row.get("documentName") or info.get("documentType")
        ),
        "filed_date": _date(
            (
                row.get("docketEntryHeader")
                if isinstance(row.get("docketEntryHeader"), Mapping)
                else {}
            ).get("filedDate")
        ),
        "source_url": source_url,
        "mime_type": _text(info.get("contentType")),
        "page_count": _integer(info.get("pageCount")),
        "file_size": _integer(info.get("fileSize")),
        "file_extension": _text(info.get("fileExtension")),
        "access_state": access_state,
        "native_access_state": source_state,
        "source_access_state": source_state,
        "source_access_state_uuid": source_state_uuid,
        "highlights": row.get("highlightsMap"),
        "raw": dict(row),
    }
    if link_to_docket and docket_uuid:
        record["docket_entry_native_id"] = docket_uuid
    return record


def _attach_documents(
    docket_entries: list[dict[str, Any]],
    documents: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        str(entry["native_entry_id"]): entry for entry in docket_entries
    }
    unlinked: list[dict[str, Any]] = []
    for document in documents:
        docket_uuid = _text(document.get("docket_entry_uuid"))
        if docket_uuid and docket_uuid in by_id:
            by_id[docket_uuid].setdefault("documents", []).append(document)
        else:
            clean = dict(document)
            clean.pop("docket_entry_native_id", None)
            unlinked.append(clean)
    return unlinked


def _session_type_record(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = _required_text(
        row.get("courtSessionTypeID"),
        "court session type ID",
    )
    name = _required_text(
        row.get("courtSessionTypeName"),
        "court session type name",
    )
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/calendar-session-type/{identifier}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "court_calendar_session_type",
        "native_session_type_id": identifier,
        "name": name,
        "comment": _text(row.get("courtSessionTypeComment")),
        "source_url": f"{PORTAL_ROOT}/search/calendar",
        "raw": dict(row),
    }


def _calendar_hearing_record(
    court: ACISCourt,
    event_uuid: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    header = row.get("caseHeader")
    if not isinstance(header, Mapping):
        raise ValueError("ACIS calendar hearing lacks caseHeader")
    case_uuid = _required_text(
        header.get("caseInstanceUUID"),
        "calendar hearing case instance UUID",
    )
    case_number = _required_text(
        header.get("caseNumber"),
        "calendar hearing case number",
    )
    header_court_id = _required_text(
        header.get("courtID"),
        "calendar hearing court ID",
    )
    if header_court_id != court.external_id:
        raise ValueError(
            "ACIS calendar hearing court ID does not match its event court"
        )
    order = _integer(row.get("orderBy"))
    occurrence_key = f"{event_uuid}:{case_uuid}:{order or 0}"
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{court.resource_uuid}/event/"
            f"{event_uuid}/hearing/{quote(occurrence_key, safe='')}"
        ),
        "case_canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court.resource_uuid,
            case_number,
        ),
        "source_internal_id": case_uuid,
        "case_instance_uuid": case_uuid,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "caption": _text(
            header.get("caseTitle") or header.get("caseCaption")
        ),
        "event_date": _text(row.get("startDate")),
        "event_type": _text(row.get("hearingType")) or "court_hearing",
        "status": _text(row.get("hearingStatus")),
        "order": order,
        "panel_flag": bool(
            (
                row.get("event")
                if isinstance(row.get("event"), Mapping)
                else {}
            ).get("panelFlag")
        ),
        "source_url": _case_url(court, case_uuid),
        "raw": dict(row),
    }


def _calendar_event_record(
    client: FloridaACISClient | Any,
    row: Mapping[str, Any],
    *,
    schema: str,
    hearings: Sequence[Mapping[str, Any]] = (),
    hearing_detail_state: str,
) -> dict[str, Any]:
    identifier = _required_text(row.get("eventUUID"), "event UUID")
    court = client.court_by_external_id(row.get("courtID"))
    normalized_hearings = [
        _calendar_hearing_record(court, identifier, hearing)
        for hearing in hearings
    ]
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{court.resource_uuid}/event/{identifier}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "calendar_event",
        "native_event_id": identifier,
        "court": _court_payload(court),
        "event_name": _text(row.get("eventName")),
        "event_type": _text(row.get("courtSessionType"))
        or "court_session",
        "event_date": _text(row.get("startDate")),
        "location": _text(row.get("location")),
        "room": _text(row.get("room")),
        "panel_flag": bool(row.get("panelFlag")),
        "cases": normalized_hearings,
        "case_count": len(normalized_hearings),
        "hearing_detail_state": hearing_detail_state,
        "source_url": f"{PORTAL_ROOT}/search/calendar",
        "schema_fingerprint": schema,
        "raw": dict(row),
    }


def _publication_record(
    client: FloridaACISClient,
    row: Mapping[str, Any],
    *,
    schema: str,
    publication_uuid: str | None = None,
    court_hint: ACISCourt | None = None,
) -> dict[str, Any]:
    identifier = _required_text(
        publication_uuid
        or row.get("publicationUUID")
        or row.get("resourceID")
        or row.get("publicationID"),
        "publication UUID",
    )
    court_id = row.get("courtID")
    if court_id is None and isinstance(row.get("court"), Mapping):
        court_id = row["court"].get("externalIdentifier")
    court = court_hint
    if court is None and court_id is not None:
        court = client.court_by_external_id(court_id)
    court_uuid = court.resource_uuid if court else "unknown-court"
    raw_items = row.get("publicationItems")
    publication_items = []
    if isinstance(raw_items, list):
        publication_items = [
            {
                "publication_item_uuid": _text(
                    item.get("publicationItemUUID")
                ),
                "case_instance_uuid": _text(item.get("caseInstanceUUID")),
                "case_number": _text(item.get("caseNumber")),
                "title": _text(item.get("title")),
                "decision": _text(item.get("decision")),
                "group_name": _text(item.get("groupName")),
                "group_order": _integer(item.get("groupOrderBy")),
                "order": _integer(item.get("orderBy")),
                "raw": dict(item),
            }
            for item in raw_items
            if isinstance(item, Mapping)
        ]
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{court_uuid}/publication/{identifier}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "publication",
        "publication_uuid": identifier,
        "court_resource_uuid": court.resource_uuid if court else None,
        "native_court_id": court.external_id if court else None,
        "court_name": court.display_name if court else None,
        "publication_number": _text(row.get("publicationNumber")),
        "name": _text(row.get("publicationName")),
        "title": _text(row.get("publicationTitle")),
        "note": _text(row.get("publicationNote")),
        "publication_date": _date(row.get("publicationDate")),
        "case_number": _text(row.get("caseNumber")),
        "publication_items": publication_items,
        "source_url": (
            f"{PORTAL_ROOT}/court/{court.resource_uuid}/publication/{identifier}"
            if court
            else PORTAL_SEARCH
        ),
        "schema_fingerprint": schema,
        "raw": dict(row),
    }


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "court_resource_uuid": getattr(args, "court", None)
        or getattr(args, "court_resource_uuid", None),
        "cursor": getattr(args, "cursor", None),
    }
    if args.command == "calendar":
        parameters.update(
            after=getattr(args, "after", None),
            before=getattr(args, "before", None),
        )
    else:
        parameters.update(
            filed_after=getattr(args, "filed_after", None)
            or getattr(args, "after", None),
            filed_before=getattr(args, "filed_before", None)
            or getattr(args, "before", None),
            case_type=getattr(args, "case_type", None),
            case_type_id=getattr(args, "case_type_id", None),
        )
    for name in (
        "query",
        "party_name",
        "case_number",
        "case_uuid",
        "document_uuid",
        "publication_uuid",
        "publication_number",
        "search_scope",
        "match_mode",
        "field",
        "text_mode",
        "document_type",
        "session_type",
        "event_name",
        "events_only",
    ):
        if hasattr(args, name):
            parameters[name] = getattr(args, name)
    return parameters


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Florida appellate courts",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _access_failure(
    query: PublicRecordsQuery,
    error: (
        AcquisitionUnavailableError
        | CatalogError
        | OSError
        | ValueError
    ),
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        return PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code")
                        or "acquisition_route_unavailable"
                    ),
                    message=str(decision.get("reason") or error),
                    category="access",
                    retryable=False,
                    details=decision,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="acquisition_route_unavailable",
                message=str(error),
                category="access_control",
                retryable=False,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=decision,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: ACISSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="query_selection",
                retryable=False,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _paginated_result(
    query: PublicRecordsQuery,
    fetched: PaginatedFetch,
    records: Sequence[Mapping[str, Any]],
) -> PublicRecordsResult:
    if fetched.truncated_by_cap:
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=records,
            next_cursor=fetched.next_cursor,
            warnings=(*SOURCE_WARNINGS, *fetched.warnings),
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=fetched.next_cursor,
        warnings=(*SOURCE_WARNINGS, *fetched.warnings),
    )


def _source_case_type_id(args: argparse.Namespace) -> str | None:
    direct = _text(getattr(args, "case_type_id", None))
    generic = _text(getattr(args, "case_type", None))
    if direct and generic and direct != generic:
        raise ACISSelectionError(
            "conflicting_case_type_filters",
            "--case-type and --case-type-id identify different values",
            details={"case_type": generic, "case_type_id": direct},
        )
    value = direct or generic
    if value is None:
        return None
    if not value.isdigit():
        raise ACISSelectionError(
            "case_type_id_required",
            "ACIS case-type filtering requires the source-native numeric "
            "case type ID",
            details={
                "provided_case_type": value,
                "supported_parameter": "caseHeader.caseTypeID",
            },
        )
    return str(int(value))


def _resolve_case(
    client: FloridaACISClient,
    case_number: str,
    *,
    court: str | None,
    page_size: int,
    case_type_id: str | None = None,
) -> tuple[ACISCourt, Mapping[str, Any]] | None:
    selector = _required_text(case_number, "case number")
    fetched = client.search_cases(
        selector,
        field="number",
        match_mode="exact",
        court=court,
        case_type_id=case_type_id,
        requested_limit=None,
        page_size=page_size,
    )
    unique: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in fetched.records:
        header = row.get("caseHeader")
        if not isinstance(header, Mapping):
            raise ValueError("ACIS case search result lacks caseHeader")
        if str(header.get("caseNumber") or "").casefold() != selector.casefold():
            continue
        key = (
            _required_text(header.get("courtID"), "case courtID"),
            _required_text(
                header.get("caseInstanceUUID"),
                "case instance UUID",
            ),
        )
        unique[key] = header
    if not unique:
        return None
    if len(unique) > 1:
        raise ACISSelectionError(
            "ambiguous_case_number",
            f"ACIS case number {selector!r} matched multiple courts",
            details={
                "matches": [
                    {
                        "court_id": key[0],
                        "case_instance_uuid": key[1],
                        "case_number": header.get("caseNumber"),
                        "case_title": header.get("caseTitle"),
                    }
                    for key, header in unique.items()
                ],
                "hint": "Select a court resource UUID with --court.",
            },
        )
    (_, _), header = next(iter(unique.items()))
    return client.court_by_external_id(header.get("courtID")), header


def _detail_header(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    header = payload.get("caseHeader")
    if not isinstance(header, Mapping):
        raise ValueError("ACIS case detail lacks caseHeader")
    return header


def _execute_command(
    args: argparse.Namespace,
    client: FloridaACISClient,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    command = args.command
    limit = getattr(args, "limit", None)
    page_size = getattr(args, "page_size", 100)
    cursor = getattr(args, "cursor", None)
    max_records = getattr(args, "max_records", None)
    case_type_id = (
        None
        if command in {"calendar", "calendar-types"}
        else _source_case_type_id(args)
    )
    court_selector = getattr(args, "court", None)
    filed_after = getattr(args, "filed_after", None) or getattr(
        args,
        "after",
        None,
    )
    filed_before = getattr(args, "filed_before", None) or getattr(
        args,
        "before",
        None,
    )

    if command == "courts":
        fetched = client._fetch_hal(
            COURTS_URL,
            params={"fields": "*,locations(*)"},
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )
        records = [
            _court_record(
                client._court_from_record(row),
                fetched.schema_fingerprint,
            )
            for row in fetched.records
        ]
        return _paginated_result(query, fetched, records)

    if command == "calendar-types":
        return PublicRecordsResult.success(
            query,
            [
                _session_type_record(row)
                for row in client.session_types()
            ],
            warnings=SOURCE_WARNINGS,
        )

    if command == "calendar":
        fetched = client.search_calendar_events(
            court=court_selector,
            after=getattr(args, "after", None),
            before=getattr(args, "before", None),
            session_type=(
                getattr(args, "session_type", None)
                or getattr(args, "case_type", None)
            ),
            event_name=getattr(args, "event_name", None),
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )
        records = []
        events_only = bool(getattr(args, "events_only", False))
        for row in fetched.records:
            court = client.court_by_external_id(row.get("courtID"))
            hearings: Sequence[Mapping[str, Any]] = ()
            hearing_schema: str | None = None
            hearing_requests = 0
            if not events_only:
                hearing_page = client.event_hearings(
                    court.resource_uuid,
                    _required_text(row.get("eventUUID"), "event UUID"),
                    requested_limit=None,
                    page_size=page_size,
                )
                hearings = hearing_page.records
                hearing_schema = hearing_page.schema_fingerprint
                hearing_requests = hearing_page.requests_made
            record = _calendar_event_record(
                client,
                row,
                schema=fetched.schema_fingerprint,
                hearings=hearings,
                hearing_detail_state=(
                    "not_requested" if events_only else "complete"
                ),
            )
            record["hearing_schema_fingerprint"] = hearing_schema
            record["hearing_requests_made"] = hearing_requests
            records.append(record)
        return _paginated_result(query, fetched, records)

    if command in {"search", "party-search"} and (
        command == "party-search"
        or getattr(args, "search_scope", "party") == "party"
    ):
        party_name = (
            getattr(args, "party_name", None)
            or getattr(args, "query", None)
        )
        match_mode = getattr(args, "match_mode", "match")
        fetched = client.search_parties(
            party_name,
            match_mode=match_mode,
            court=court_selector,
            filed_after=filed_after,
            filed_before=filed_before,
            case_type_id=case_type_id,
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )
        records = []
        for row in fetched.records:
            header = row.get("caseHeader")
            if not isinstance(header, Mapping):
                raise ValueError("ACIS party search result lacks caseHeader")
            records.append(
                _case_record(
                    client,
                    header,
                    schema=fetched.schema_fingerprint,
                    parties=[_party_record(row)],
                    search_hit=row,
                )
            )
        return _paginated_result(query, fetched, records)

    if command in {"search", "case-search"}:
        selector = getattr(args, "query")
        match_mode = getattr(args, "match_mode", "contains")
        if match_mode in PARTY_QUERY_MODES:
            match_mode = "contains"
        fetched = client.search_cases(
            selector,
            field=getattr(args, "field", "auto"),
            match_mode=match_mode,
            court=court_selector,
            filed_after=filed_after,
            filed_before=filed_before,
            case_type_id=case_type_id,
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )
        records = []
        for row in fetched.records:
            header = row.get("caseHeader")
            if not isinstance(header, Mapping):
                raise ValueError("ACIS case search result lacks caseHeader")
            records.append(
                _case_record(
                    client,
                    header,
                    schema=fetched.schema_fingerprint,
                    search_hit=row,
                )
            )
        return _paginated_result(query, fetched, records)

    if command in {"case", "docket", "documents"}:
        resolved = _resolve_case(
            client,
            getattr(args, "query"),
            court=court_selector,
            page_size=page_size,
            case_type_id=case_type_id,
        )
        if resolved is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        court, search_header = resolved
        case_uuid = _required_text(
            search_header.get("caseInstanceUUID"),
            "case instance UUID",
        )
        detail = client.get_case(court.resource_uuid, case_uuid)
        header = _detail_header(detail)
        detail_schema = schema_fingerprint(inferred_schema([detail]))

        parties: list[dict[str, Any]] = []
        docket_entries: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        next_cursor: str | None = None
        warnings = list(SOURCE_WARNINGS)

        if command == "case":
            party_page = client.case_parties(
                court.resource_uuid,
                case_uuid,
                requested_limit=None,
                page_size=page_size,
            )
            parties = [
                _party_record(row) for row in party_page.records
            ]

        include_documents = command == "documents" or (
            command == "case" and bool(getattr(args, "documents", False))
        )
        if command == "docket" or include_documents:
            docket_page = client.docket_entries(
                court.resource_uuid,
                case_uuid,
                requested_limit=(
                    None if include_documents else limit
                ),
                page_size=page_size,
                cursor=None if include_documents else cursor,
                max_records=(
                    None if include_documents else max_records
                ),
            )
            docket_entries = [
                _docket_record(row) for row in docket_page.records
            ]
            if command == "docket":
                next_cursor = docket_page.next_cursor
                warnings.extend(docket_page.warnings)

        if include_documents:
            document_page = client.case_documents(
                court.resource_uuid,
                case_uuid,
                requested_limit=limit,
                page_size=page_size,
                cursor=cursor,
                max_records=max_records,
            )
            normalized_documents = [
                _document_record(client, row, link_to_docket=True)
                for row in document_page.records
            ]
            document_type = _text(
                getattr(args, "document_type", None)
            )
            if document_type:
                normalized_documents = [
                    document
                    for document in normalized_documents
                    if document_type.casefold()
                    in str(document.get("document_type") or "").casefold()
                ]
            documents = _attach_documents(
                docket_entries,
                normalized_documents,
            )
            next_cursor = document_page.next_cursor
            warnings.extend(document_page.warnings)

        record = _case_record(
            client,
            header,
            schema=detail_schema,
            parties=parties,
            docket_entries=docket_entries,
            documents=documents,
        )
        status = (
            ResultStatus.PARTIAL
            if max_records is not None and next_cursor is not None
            else ResultStatus.OK
        )
        return PublicRecordsResult(
            query=query,
            status=status,
            records=[record],
            next_cursor=next_cursor,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    if command == "document-search":
        fetched = client.search_documents(
            getattr(args, "query"),
            text_mode=getattr(args, "text_mode", "any"),
            court=court_selector,
            filed_after=filed_after,
            filed_before=filed_before,
            case_type_id=case_type_id,
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )
        records = []
        for row in fetched.records:
            header = row.get("caseHeader")
            if not isinstance(header, Mapping):
                raise ValueError("ACIS document result lacks caseHeader")
            document_row: Mapping[str, Any] = row
            document_uuid = _text(row.get("documentLinkUUID"))
            case_uuid = _text(header.get("caseInstanceUUID"))
            if document_uuid and case_uuid:
                result_court = client.court_by_external_id(
                    header.get("courtID")
                )
                access_page = client.case_documents(
                    result_court.resource_uuid,
                    case_uuid,
                    document_uuid=document_uuid,
                    requested_limit=None,
                    page_size=page_size,
                )
                access_match = next(
                    (
                        candidate
                        for candidate in access_page.records
                        if _text(candidate.get("documentLinkUUID"))
                        == document_uuid
                    ),
                    None,
                )
                if access_match is not None:
                    merged = dict(access_match)
                    for key in ("docketEntryHeader", "highlightsMap"):
                        if key in row and key not in merged:
                            merged[key] = row[key]
                    document_row = merged
            records.append(
                _case_record(
                    client,
                    header,
                    schema=fetched.schema_fingerprint,
                    documents=[
                        _document_record(
                            client,
                            document_row,
                            link_to_docket=False,
                        )
                    ],
                    search_hit=row,
                )
            )
        return _paginated_result(query, fetched, records)

    if command == "download":
        court_uuid = getattr(args, "court_resource_uuid", None) or court_selector
        case_uuid = getattr(args, "case_uuid", None)
        document_uuid = getattr(args, "document_uuid", None) or getattr(
            args,
            "query",
            None,
        )
        download = client.download_document(
            _required_text(court_uuid, "court resource UUID"),
            _required_text(case_uuid, "case UUID"),
            _required_text(document_uuid, "document UUID"),
        )
        destination_value = getattr(args, "destination", None)
        destination: Path | None = None
        if destination_value:
            destination = Path(destination_value).expanduser()
            if destination.exists() and not getattr(args, "overwrite", False):
                raise OSError(
                    f"destination exists; pass --overwrite: {destination}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(download.content)
        digest = hashlib.sha256(download.content).hexdigest()
        record = {
            "canonical_ref": (
                f"STATECOURT:{SOURCE_ID}/{court_uuid}/{case_uuid}/document/"
                f"{document_uuid}"
            ),
            "source_id": SOURCE_ID,
            "record_kind": "document_download",
            "court_resource_uuid": court_uuid,
            "case_instance_uuid": case_uuid,
            "document_link_uuid": document_uuid,
            "download_status": "saved" if destination else "verified",
            "storage_path": (
                str(destination.resolve()) if destination else None
            ),
            "filename": download.filename,
            "mime_type": download.media_type,
            "size": len(download.content),
            "sha256": digest,
            "etag": download.etag,
            "source_url": download.source_url,
        }
        refs = [str(destination.resolve())] if destination else []
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=refs,
            warnings=SOURCE_WARNINGS,
        )

    if command == "publications":
        fetched = client.search_publications(
            getattr(args, "query", None),
            court=court_selector,
            case_number=getattr(args, "case_number", None),
            publication_number=getattr(args, "publication_number", None),
            filed_after=filed_after,
            filed_before=filed_before,
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
            max_records=max_records,
        )
        records = [
            _publication_record(
                client,
                row,
                schema=fetched.schema_fingerprint,
            )
            for row in fetched.records
        ]
        return _paginated_result(query, fetched, records)

    if command == "publication":
        court_uuid = getattr(args, "court_resource_uuid", None) or court_selector
        publication_uuid = getattr(args, "publication_uuid", None)
        selected_court = client.resolve_court(
            _required_text(court_uuid, "court resource UUID")
        )
        payload = client.get_publication(
            selected_court.resource_uuid,
            _required_text(publication_uuid, "publication UUID"),
        )
        observed_schema = schema_fingerprint(inferred_schema([payload]))
        return PublicRecordsResult.success(
            query,
            [
                _publication_record(
                    client,
                    payload,
                    schema=observed_schema,
                    publication_uuid=publication_uuid,
                    court_hint=selected_court,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )

    raise ValueError(f"unsupported ACIS command: {command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: FloridaACISClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one ACIS operation and return the shared result envelope."""
    query = build_query(args)
    try:
        decision = (
            dict(access_decision)
            if access_decision is not None
            else _access_contract(args)
        )
    except (AcquisitionUnavailableError, CatalogError, OSError, ValueError) as error:
        result = _access_failure(query, error)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result
    if not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    source_client = client or _make_client(args, decision)
    try:
        result = _execute_command(args, source_client, query)
    except ACISSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
            warnings=SOURCE_WARNINGS,
        )
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="document_write_failed",
                    message=str(error),
                    category="local_io",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
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
        summary=f"Florida ACIS {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Florida ACIS {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("raw_case_number")
            or record.get("publication_uuid")
            or record.get("court_resource_uuid")
            or record.get("document_link_uuid")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_catalog_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source and acquisition catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and reviewed access decisions",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    add_output_args(parser)


def _add_paging(parser: argparse.ArgumentParser, *, default_limit: int = 50) -> None:
    parser.add_argument("--limit", type=int, default=default_limit)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--cursor")
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional caller-selected ceiling for this operation",
    )


def _add_search_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--court",
        help="Court resource UUID, numeric ACIS court ID, or court name",
    )
    parser.add_argument("--filed-after", help="Filed on/after ISO date")
    parser.add_argument("--filed-before", help="Filed on/before ISO date")
    parser.add_argument(
        "--case-type-id",
        help="Source-native numeric ACIS case type ID",
    )


def _add_search_shared(parser: argparse.ArgumentParser) -> None:
    _add_search_filters(parser)
    _add_paging(parser)
    _add_catalog_and_output(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the Florida Supreme Court and six District Courts of "
            "Appeal through the public ACIS backend"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    courts = sub.add_parser("courts", help="List the seven appellate courts")
    _add_paging(courts, default_limit=100)
    _add_catalog_and_output(courts)

    calendar_types = sub.add_parser(
        "calendar-types",
        help="List the public ACIS calendar-session taxonomy",
    )
    _add_catalog_and_output(calendar_types)

    calendar = sub.add_parser(
        "calendar",
        help="Search appellate calendar events and their case hearings",
    )
    calendar.add_argument(
        "--court",
        help="Court resource UUID, numeric ACIS court ID, or court name",
    )
    calendar.add_argument("--after", help="Event on/after ISO date")
    calendar.add_argument("--before", help="Event on/before ISO date")
    calendar.add_argument(
        "--session-type",
        help="Session-type ID or name, such as Oral Argument",
    )
    calendar.add_argument(
        "--event-name",
        help="Match text in the source calendar-event name",
    )
    calendar.add_argument(
        "--events-only",
        action="store_true",
        help="Return event rows without fetching their attached case hearings",
    )
    _add_paging(calendar, default_limit=50)
    _add_catalog_and_output(calendar)

    search = sub.add_parser(
        "search",
        help="Unified case or party search (party by default)",
    )
    search.add_argument("query")
    search.add_argument(
        "--search-scope",
        choices=("party", "case"),
        default="party",
    )
    search.add_argument(
        "--match-mode",
        choices=tuple(QUERY_TYPES),
        default="match",
    )
    search.add_argument(
        "--field",
        choices=("auto", "number", "title"),
        default="auto",
    )
    _add_search_shared(search)

    case_search = sub.add_parser(
        "case-search",
        help="Search the public case index",
    )
    case_search.add_argument("query")
    case_search.add_argument(
        "--field",
        choices=("auto", "number", "title"),
        default="auto",
    )
    case_search.add_argument(
        "--match-mode",
        choices=tuple(sorted(CASE_QUERY_MODES)),
        default="contains",
    )
    _add_search_shared(case_search)

    party_search = sub.add_parser(
        "party-search",
        help="Search the public party index",
    )
    party_search.add_argument("party_name")
    party_search.add_argument(
        "--match-mode",
        choices=tuple(sorted(PARTY_QUERY_MODES)),
        default="match",
    )
    _add_search_shared(party_search)

    case = sub.add_parser("case", help="Fetch case detail and parties")
    case.add_argument("query", metavar="CASE_NUMBER")
    case.add_argument(
        "--documents",
        action="store_true",
        help="Also retrieve docket and public-document metadata",
    )
    _add_search_shared(case)

    docket = sub.add_parser("docket", help="Fetch public docket entries")
    docket.add_argument("query", metavar="CASE_NUMBER")
    _add_search_shared(docket)

    documents = sub.add_parser(
        "documents",
        help="Fetch document metadata for a case",
    )
    documents.add_argument("query", metavar="CASE_NUMBER")
    documents.add_argument("--document-type")
    _add_search_shared(documents)

    document_search = sub.add_parser(
        "document-search",
        help="Search indexed document text",
    )
    document_search.add_argument("query")
    document_search.add_argument(
        "--text-mode",
        choices=("any", "all", "exact", "none"),
        default="any",
    )
    _add_search_shared(document_search)

    download = sub.add_parser(
        "download",
        help="Download a document ACIS marks viewable to the public",
    )
    download.add_argument("court_resource_uuid")
    download.add_argument("case_uuid")
    download.add_argument("document_uuid")
    download.add_argument("destination", nargs="?")
    download.add_argument("--overwrite", action="store_true")
    _add_catalog_and_output(download)

    publications = sub.add_parser(
        "publications",
        help="Search ACIS publications",
    )
    publications.add_argument("query", nargs="?")
    publications.add_argument("--case-number")
    publications.add_argument("--publication-number")
    _add_search_shared(publications)

    publication = sub.add_parser(
        "publication",
        help="Fetch one publication by court and publication UUID",
    )
    publication.add_argument("court_resource_uuid")
    publication.add_argument("publication_uuid")
    _add_catalog_and_output(publication)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "timeout", 0) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    for name in ("limit", "page_size", "max_records"):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    try:
        result = execute(args)
    except ValueError as error:
        parser.error(str(error))
        return
    _emit(result, args)


if __name__ == "__main__":
    main()
