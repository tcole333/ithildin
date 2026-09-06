#!/usr/bin/env python3
"""Query the public Virgin Islands judiciary C-Track portal.

The adapter covers the anonymous C-Track JSON/PDF routes and the judiciary's
older numeric ``DisplayFile.aspx`` PDF route.  The two source systems retain
separate native identifier namespaces; a validated PDF SHA-256 is the only
cross-system content identity emitted by this tool.

Examples:
    uv run python tools/query_vicourts.py courts --json
    uv run python tools/query_vicourts.py search ST-19-PB-80 \
        --field number --match-mode exact --json
    uv run python tools/query_vicourts.py docket ST-19-PB-80 --output docket.json
    uv run python tools/query_vicourts.py document-search \
        --exact Epstein --limit 25 --json
    uv run python tools/query_vicourts.py legacy-file 16911884 opinion.pdf
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
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
    )
    from tools.public_records_http import (
        HTTPStatusError,
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
    )
    from public_records_http import (
        HTTPStatusError,
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


SOURCE_ID = "us-vi-c-track"
STATE_CODE = "VI"
STATE_GEOID = "78"
PORTAL_ROOT = "https://usvipublicportal.vicourts.org"
PORTAL_HOME = f"{PORTAL_ROOT}/portal/home"
API_ROOT = "https://usvipublicportal-api.vicourts.org"
COURTS_URL = f"{API_ROOT}/courts"
CASE_SEARCH_URL = f"{API_ROOT}/courts/cms/cases"
PARTY_SEARCH_URL = f"{API_ROOT}/courts/cms/parties"
DOCUMENT_SEARCH_URL = f"{API_ROOT}/courts/cms/docketentrydocuments"
DOCUMENT_ACCESS_URL = f"{API_ROOT}/courts/cms/docketentrydocumentsaccess"
PUBLICATION_SEARCH_URL = f"{API_ROOT}/courts/cms/publications"
INFO_URL = f"{API_ROOT}/manage/info"
LEGACY_FILE_URL = "https://www.vicourts.org/common/pages/DisplayFile.aspx"

QUERY_TYPES = {
    "starts": "10461",
    "exact": "10462",
    "contains": "10463",
    "match": "300054",
    "phonetic": "300055",
}
CASE_MATCH_MODES = frozenset({"starts", "exact", "contains"})
PARTY_MATCH_MODES = frozenset({"match", "phonetic"})
MAX_PAGE_SIZE = 500
SOURCE_RESULT_LIMIT = 10_000

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

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Virgin Islands Judiciary Public Portal",
    source_role="territorial_case_docket_and_document_portal",
    base_url=PORTAL_HOME,
    dataset_id="vicourts-ctrack-public",
    metadata={
        "authority": "Judicial Branch of the Virgin Islands",
        "coverage": "Supreme Court and Superior Court of the Virgin Islands",
        "state_code": STATE_CODE,
        "authentication": "none",
        "source_result_limit": SOURCE_RESULT_LIMIT,
    },
)


@dataclass(frozen=True)
class VICourt:
    """One live court-directory entry."""

    resource_uuid: str
    external_id: str
    display_name: str
    active: bool
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class VICourtsFetch:
    """One or more zero-based Spring pages plus source-bound metadata."""

    records: Sequence[Mapping[str, Any]]
    next_cursor: str | None
    schema: Mapping[str, Any]
    schema_fingerprint: str
    pages_fetched: int
    requests_made: int
    total_elements: int | None = None
    source_overflow: bool = False
    truncated_by_caller: bool = False
    warnings: Sequence[str] = ()


@dataclass(frozen=True)
class ValidatedPDF:
    """A PDF whose media type, signature, size, and digest were checked."""

    content: bytes
    media_type: str
    filename: str
    sha256: str
    source_url: str
    etag: str | None = None


class VICourtsSelectionError(ValueError):
    """A caller selector did not resolve to one source record."""

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
        raise ValueError(f"VI Courts {field_name} must not be blank")
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


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def _response_text(response: Any) -> str:
    value = getattr(response, "text", "")
    return value if isinstance(value, str) else str(value)


def _positive(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    prefix = "vicourts:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError("VI Courts cursor must have form vicourts:offset:N")
    return int(cursor[len(prefix) :])


def _embedded_records(payload: Any, *, url: str) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "VI Courts paginated response must be an object",
            url=url,
        )
    embedded = payload.get("_embedded")
    page = payload.get("page")
    if embedded is None and isinstance(page, Mapping):
        if _integer(page.get("totalElements")) == 0:
            return []
    if not isinstance(embedded, Mapping):
        raise SourceSchemaError(
            "VI Courts paginated response lacks _embedded",
            url=url,
        )
    records = embedded.get("results")
    if not isinstance(records, list) or any(
        not isinstance(record, Mapping) for record in records
    ):
        raise SourceSchemaError(
            "VI Courts response lacks an object results array",
            url=url,
        )
    return list(records)


def _page_metadata(payload: Mapping[str, Any], *, url: str) -> dict[str, int]:
    page = payload.get("page")
    if not isinstance(page, Mapping):
        raise SourceSchemaError(
            "VI Courts response lacks Spring page metadata",
            url=url,
        )
    result: dict[str, int] = {}
    for key in ("size", "totalElements", "totalPages", "number"):
        value = _integer(page.get(key))
        if value is None or value < 0:
            raise SourceSchemaError(
                f"VI Courts page metadata lacks numeric {key}",
                url=url,
            )
        result[key] = value
    return result


_LEGACY_CASE_PATTERN = re.compile(
    r"^(?P<venue>[A-Z]{2,4})-(?P<year>\d{2}|\d{4})-"
    r"(?P<kind>[A-Z0-9]{2,5})-(?P<sequence>\d{1,8})$",
    re.I,
)


def normalize_case_number(value: str) -> str:
    """Expand legacy two-digit years and left-pad VI case sequences."""

    raw = _required_text(value, "case number").upper()
    match = _LEGACY_CASE_PATTERN.fullmatch(raw)
    if match is None:
        return raw
    year_text = match.group("year")
    if len(year_text) == 2:
        year_number = int(year_text)
        year_text = str(1900 + year_number if year_number >= 70 else 2000 + year_number)
    sequence = match.group("sequence")
    sequence = sequence.zfill(5) if len(sequence) < 5 else sequence
    return (
        f"{match.group('venue').upper()}-{year_text}-"
        f"{match.group('kind').upper()}-{sequence}"
    )


def _validate_pdf(response: Any, *, url: str, fallback_name: str) -> ValidatedPDF:
    content = getattr(response, "content", None)
    if not isinstance(content, bytes):
        raise SourceSchemaError(
            "VI Courts PDF response did not expose binary content",
            url=url,
        )
    media_type = (
        _header(getattr(response, "headers", {}), "Content-Type") or ""
    ).split(";", 1)[0].strip().lower()
    if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
        raise SourceSchemaError(
            "VI Courts response was not a PDF",
            url=url,
            details={
                "content_type": media_type,
                "signature_hex": content[:8].hex(),
            },
        )
    filename = fallback_name
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
    return ValidatedPDF(
        content=content,
        media_type=media_type,
        filename=filename,
        sha256=hashlib.sha256(content).hexdigest(),
        source_url=url,
        etag=_header(getattr(response, "headers", {}), "ETag"),
    )


class VICourtsClient(_BaseJSONClient):
    """Transport-injectable client for verified VI C-Track routes."""

    def __init__(
        self,
        *args: Any,
        maximum_page_size: int = MAX_PAGE_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.maximum_page_size = min(
            _positive(maximum_page_size, "maximum_page_size") or MAX_PAGE_SIZE,
            MAX_PAGE_SIZE,
        )
        self._courts: tuple[VICourt, ...] | None = None

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
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
        """Fetch zero-based Spring pages, respecting the verified 500-row max."""

        size = self._bounded_page_size(page_size)
        requested_limit = _positive(requested_limit, "requested_limit")
        current_offset = _cursor_offset(cursor)
        records: list[Mapping[str, Any]] = []
        total_elements: int | None = None
        source_page_size = size
        pages_fetched = 0
        initial_requests = self.request_count

        while requested_limit is None or len(records) < requested_limit:
            page_number = current_offset // source_page_size
            payload = self._request_json(
                url,
                params={
                    **dict(params or {}),
                    "page": page_number,
                    "size": size,
                },
            )
            if not isinstance(payload, Mapping):
                raise SourceSchemaError(
                    "VI Courts page must be an object",
                    url=url,
                )
            page_records = _embedded_records(payload, url=url)
            metadata = _page_metadata(payload, url=url)
            pages_fetched += 1
            total_elements = metadata["totalElements"]
            reported_size = metadata["size"]
            if reported_size > 0 and reported_size != source_page_size:
                source_page_size = reported_size
                corrected_page = current_offset // source_page_size
                if corrected_page != page_number:
                    continue

            within_page = current_offset % source_page_size
            available = page_records[within_page:]
            remaining = (
                None
                if requested_limit is None
                else requested_limit - len(records)
            )
            selected = available if remaining is None else available[:remaining]
            records.extend(selected)
            current_offset += len(selected)

            if not selected or current_offset >= total_elements:
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
        source_overflow = (
            total_elements is not None
            and total_elements >= SOURCE_RESULT_LIMIT
        )
        warnings: list[str] = []
        if source_overflow:
            warnings.append(
                "source_overflow: C-Track reported the 10,000-result source "
                "ceiling; records beyond that ceiling require narrower criteria."
            )
        observed_schema = inferred_schema(records)
        return VICourtsFetch(
            records=tuple(records),
            next_cursor=(
                f"vicourts:offset:{current_offset}" if source_has_more else None
            ),
            schema=observed_schema,
            schema_fingerprint=schema_fingerprint(observed_schema),
            pages_fetched=pages_fetched,
            requests_made=self.request_count - initial_requests,
            total_elements=total_elements,
            source_overflow=source_overflow,
            truncated_by_caller=requested_limit is not None and source_has_more,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _court_from_record(record: Mapping[str, Any]) -> VICourt:
        return VICourt(
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

    def list_courts(
        self,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
        fetched = self._fetch_hal(
            COURTS_URL,
            params={"fields": "*,locations(*)"},
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
        )
        if cursor is None and fetched.next_cursor is None:
            self._courts = tuple(
                self._court_from_record(record) for record in fetched.records
            )
        return fetched

    def courts(self) -> tuple[VICourt, ...]:
        if self._courts is None:
            fetched = self.list_courts(page_size=MAX_PAGE_SIZE)
            self._courts = tuple(
                self._court_from_record(record) for record in fetched.records
            )
        return self._courts

    def resolve_court(self, selector: str) -> VICourt:
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
        matches = exact or partial
        if matches:
            raise VICourtsSelectionError(
                "ambiguous_court_selector",
                f"VI Courts selector {value!r} matches multiple courts",
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
        raise VICourtsSelectionError(
            "court_not_found",
            f"VI Courts selector {value!r} did not match the live directory",
            details={"selector": value},
        )

    def court_by_external_id(self, external_id: Any) -> VICourt:
        value = _required_text(external_id, "case courtID")
        matches = [
            court for court in self.courts() if court.external_id == value
        ]
        if len(matches) != 1:
            raise SourceSchemaError(
                f"VI Courts case references unknown courtID {value!r}",
                url=COURTS_URL,
            )
        return matches[0]

    def search_cases(
        self,
        query: str,
        *,
        field: str,
        match_mode: str,
        court: str | None = None,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
        if field not in {"number", "title"}:
            raise ValueError("case field must be number or title")
        if match_mode not in CASE_MATCH_MODES:
            raise ValueError("case match mode must be starts, exact, or contains")
        selector = _required_text(query, "case query")
        if field == "number":
            selector = normalize_case_number(selector)
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
        if court:
            params["caseHeader.courtID"] = self.resolve_court(
                court
            ).resource_uuid
        return self._fetch_hal(
            CASE_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
        )

    def search_parties(
        self,
        query: str,
        *,
        match_mode: str,
        court: str | None = None,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
        if match_mode not in PARTY_MATCH_MODES:
            raise ValueError("party match mode must be match or phonetic")
        params: dict[str, Any] = {
            "partyHeader.partyActorInstance.displayName": _required_text(
                query,
                "party query",
            ),
            "partyHeader.partyActorInstance.displayNameSearchType": (
                QUERY_TYPES[match_mode]
            ),
            "sort": "score,desc",
        }
        if court:
            params["caseHeader.courtID"] = self.resolve_court(
                court
            ).resource_uuid
        return self._fetch_hal(
            PARTY_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
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
                "VI Courts case detail must be an object",
                url=url,
            )
        return payload

    def docket_entries(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
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
        )

    def claims(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"cases/{quote(identifier, safe='')}/claims"
        )
        return self._fetch_hal(
            url,
            params={"sort": "claimHeader.sequenceNumber,asc"},
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
        )

    def case_documents(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        docket_entry_uuid: str | None = None,
        document_uuid: str | None = None,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        params: dict[str, Any] = {
            "caseHeader.courtID": court.resource_uuid,
            "caseHeader.caseInstanceUUID": identifier,
            "sort": "documentName,asc",
        }
        if docket_entry_uuid:
            params["docketEntryHeader.docketEntryUUID"] = docket_entry_uuid
        if document_uuid:
            params["documentLinkUUID"] = document_uuid
        return self._fetch_hal(
            DOCUMENT_ACCESS_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
        )

    def search_documents(
        self,
        *,
        exact: str | None = None,
        any_words: str | None = None,
        all_words: str | None = None,
        none_words: str | None = None,
        court: str | None = None,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
        params: dict[str, Any] = {"sort": "score,desc"}
        fields = {
            "thisExactPhrase": exact,
            "anyOfTheseWords": any_words,
            "allOfTheseWords": all_words,
            "noneOfTheseWords": none_words,
        }
        for key, value in fields.items():
            if _text(value):
                params[key] = _required_text(value, key)
        if len(params) == 1:
            raise ValueError(
                "document-search requires --exact, --any, --all, or --none"
            )
        if court:
            params["caseHeader.courtID"] = self.resolve_court(
                court
            ).resource_uuid
        return self._fetch_hal(
            DOCUMENT_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
        )

    def search_publications(
        self,
        *,
        query: str | None = None,
        publication_number: str | None = None,
        case_number: str | None = None,
        court: str | None = None,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> VICourtsFetch:
        params: dict[str, Any] = {"sort": "publicationDate,desc"}
        if query:
            params["publicationTitle"] = _required_text(
                query,
                "publication query",
            )
        if publication_number:
            params["publicationNumber"] = _required_text(
                publication_number,
                "publication number",
            )
        if case_number:
            params["caseNumber"] = normalize_case_number(case_number)
        if court:
            params["courtID"] = self.resolve_court(court).resource_uuid
        if len(params) == 1:
            raise ValueError("publications requires at least one criterion")
        return self._fetch_hal(
            PUBLICATION_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
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
                "VI Courts publication detail must be an object",
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
                        f"VI Courts PDF request failed after {attempt} "
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
                error_type = (
                    RateLimitedHTTPError
                    if status_code == 429
                    else HTTPStatusError
                )
                raise error_type(
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
            f"VI Courts PDF request failed: {last_error}",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )

    def download_document(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        document_uuid: str,
    ) -> ValidatedPDF:
        court = self.resolve_court(court_resource_uuid)
        case_identifier = _required_text(case_uuid, "case UUID")
        document_identifier = _required_text(document_uuid, "document UUID")
        access = self.case_documents(
            court.resource_uuid,
            case_identifier,
            document_uuid=document_identifier,
            page_size=100,
        )
        matches = [
            row
            for row in access.records
            if _text(row.get("documentLinkUUID")) == document_identifier
        ]
        if not matches:
            raise VICourtsSelectionError(
                "document_not_found",
                "VI C-Track did not list that document for the selected case",
                details={
                    "court_resource_uuid": court.resource_uuid,
                    "case_uuid": case_identifier,
                    "document_uuid": document_identifier,
                },
            )
        if len(matches) > 1:
            raise SourceSchemaError(
                "VI C-Track returned duplicate document identities",
                url=DOCUMENT_ACCESS_URL,
            )
        state_uuid = _text(matches[0].get("userDocumentState"))
        if state_uuid != DOCUMENT_STATE_VIEWABLE:
            state = DOCUMENT_STATES.get(state_uuid or "", "unknown")
            raise VICourtsSelectionError(
                "document_not_publicly_viewable",
                f"VI C-Track reports this document as {state}",
                details={
                    "document_uuid": document_identifier,
                    "source_state": state,
                    "source_state_uuid": state_uuid,
                },
                status=ResultStatus.RESTRICTED,
            )
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"case/{quote(case_identifier, safe='')}/docketentrydocuments/"
            f"{quote(document_identifier, safe='')}"
        )
        return _validate_pdf(
            self._request_binary(url),
            url=url,
            fallback_name=f"{document_identifier}.pdf",
        )

    def legacy_file(self, item_id: int) -> ValidatedPDF:
        if isinstance(item_id, bool) or item_id <= 0:
            raise ValueError("legacy itemId must be a positive integer")
        url = f"{LEGACY_FILE_URL}?itemId={item_id}"
        return _validate_pdf(
            self._request_binary(url),
            url=url,
            fallback_name=f"VICOURTS_ITEM_{item_id}.pdf",
        )

    def info(self) -> Mapping[str, Any]:
        payload = self._request_json(INFO_URL, params={})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "VI Courts manage/info response must be an object",
                url=INFO_URL,
            )
        return payload


def _court_payload(court: VICourt) -> dict[str, Any]:
    level = (
        "supreme"
        if "supreme" in court.display_name.casefold()
        else "superior"
        if "superior" in court.display_name.casefold()
        else None
    )
    return {
        "court_id": court.resource_uuid,
        "native_court_id": court.external_id,
        "name": court.display_name,
        "state_code": STATE_CODE,
        "court_level": level,
        "official_url": PORTAL_HOME,
    }


def _court_record(court: VICourt, *, schema: str) -> dict[str, Any]:
    payload = _court_payload(court)
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{court.resource_uuid}/court/"
            f"{court.external_id}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "court",
        "backend": "ctrack",
        "source_namespace_id": f"CTRACK_COURT:{court.resource_uuid}",
        "court_resource_uuid": court.resource_uuid,
        "native_court_id": court.external_id,
        "name": court.display_name,
        "state_code": STATE_CODE,
        "court_level": payload["court_level"],
        "active": court.active,
        "official_url": PORTAL_HOME,
        "schema_fingerprint": schema,
        "raw": dict(court.raw),
    }


def _party_record(row: Mapping[str, Any]) -> dict[str, Any]:
    header = row.get("partyHeader")
    if not isinstance(header, Mapping):
        raise ValueError("VI C-Track party result lacks partyHeader")
    actor = header.get("partyActorInstance")
    if not isinstance(actor, Mapping):
        raise ValueError("VI C-Track party result lacks party actor")
    name = _required_text(
        actor.get("displayName") or actor.get("sortName"),
        "party display name",
    )
    sequence = _integer(row.get("partyNumber"))
    source_identity = _text(header.get("casePartyUUID"))
    if sequence is None:
        stable = source_identity or "\x1f".join(
            (
                _text(header.get("partySubType"))
                or _text(header.get("partyType"))
                or "Party",
                name,
            )
        )
        sequence = int(hashlib.sha256(stable.encode()).hexdigest()[:8], 16) or 1
    return {
        "sequence_no": sequence,
        "role": _text(header.get("partySubType") or header.get("partyType"))
        or "Party",
        "raw_name": name,
        "normalized_name": _text(actor.get("sortName")),
        "source_internal_id": source_identity,
        "status": _text(header.get("partyStatus")),
        "access_state": (
            "restricted" if row.get("nonPublicFlag") else "public"
        ),
        "raw": dict(row),
    }


def _case_header(row: Mapping[str, Any]) -> Mapping[str, Any]:
    header = row.get("caseHeader")
    if isinstance(header, Mapping):
        return header
    if row.get("caseInstanceUUID") and row.get("caseNumber"):
        return row
    raise ValueError("VI C-Track case payload lacks caseHeader")


def _case_record(
    client: VICourtsClient,
    header: Mapping[str, Any],
    *,
    schema: str,
    parties: Sequence[Mapping[str, Any]] = (),
    docket_entries: Sequence[Mapping[str, Any]] = (),
    documents: Sequence[Mapping[str, Any]] = (),
    claims: Sequence[Mapping[str, Any]] = (),
    search_hit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    case_uuid = _required_text(
        header.get("caseInstanceUUID"),
        "case instance UUID",
    )
    raw_case_number = _required_text(header.get("caseNumber"), "case number")
    case_number = normalize_case_number(raw_case_number)
    court = client.court_by_external_id(header.get("courtID"))
    record: dict[str, Any] = {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court.resource_uuid,
            case_number,
            native_id=case_uuid,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "backend": "ctrack",
        "source_namespace_id": f"CTRACK_CASE:{case_uuid}",
        "court": _court_payload(court),
        "raw_case_number": case_number,
        "display_case_number": raw_case_number,
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
        "source_url": (
            f"{PORTAL_ROOT}/portal/court/{court.resource_uuid}/case/{case_uuid}"
        ),
        "parties": list(parties),
        "docket_entries": list(docket_entries),
        "documents": list(documents),
        "claims": list(claims),
        "schema_fingerprint": schema,
        "raw": dict(header),
    }
    if search_hit is not None:
        record["search_hit"] = dict(search_hit)
    return record


def _docket_record(row: Mapping[str, Any]) -> dict[str, Any]:
    header = row.get("docketEntryHeader")
    if not isinstance(header, Mapping):
        raise ValueError("VI C-Track docket result lacks docketEntryHeader")
    identifier = _required_text(
        header.get("docketEntryUUID"),
        "docket entry UUID",
    )
    count = _integer(header.get("documentCount")) or 0
    description = _text(
        header.get("docketEntryDescription")
        or header.get("docketEntryName")
        or header.get("docketEntrySubType")
        or header.get("docketEntryType")
    )
    return {
        "native_entry_id": identifier,
        "backend": "ctrack",
        "source_namespace_id": f"CTRACK_DOCKET:{identifier}",
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
        "document_available": count > 0,
        "document_count": count,
        "secured_document": bool(header.get("securedDocument")),
        "access_state": "public",
        "documents": [],
        "raw": dict(row),
    }


def _claim_record(row: Mapping[str, Any]) -> dict[str, Any]:
    header = row.get("claimHeader")
    if not isinstance(header, Mapping):
        header = row
    sequence = _integer(header.get("sequenceNumber"))
    identifier = _text(
        header.get("claimUUID")
        or header.get("claimInstanceUUID")
        or header.get("resourceID")
    )
    stable = identifier or str(sequence or _text(header.get("claimType")) or "claim")
    return {
        "backend": "ctrack",
        "source_namespace_id": f"CTRACK_CLAIM:{stable}",
        "claim_uuid": identifier,
        "sequence_no": sequence,
        "claim_type": _text(
            header.get("claimType")
            or header.get("claimTypeDescription")
        ),
        "claim_date": _date(
            header.get("claimDate") or header.get("filedDate")
        ),
        "limited_stub": True,
        "raw": dict(row),
    }


def _document_record(
    client: VICourtsClient,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    identifier = _required_text(
        row.get("documentLinkUUID"),
        "document link UUID",
    )
    docket_uuid = _text(row.get("docketEntryUUID"))
    docket_header = row.get("docketEntryHeader")
    if not isinstance(docket_header, Mapping):
        docket_header = {}
    if docket_uuid is None:
        docket_uuid = _text(docket_header.get("docketEntryUUID"))
    case_header = row.get("caseHeader")
    if not isinstance(case_header, Mapping):
        case_header = {}
    court: VICourt | None = None
    if case_header.get("courtID") is not None:
        court = client.court_by_external_id(case_header.get("courtID"))
    case_uuid = _text(case_header.get("caseInstanceUUID"))
    info = row.get("documentInfo")
    if not isinstance(info, Mapping):
        info = {}
    state_uuid = _text(row.get("userDocumentState"))
    state = DOCUMENT_STATES.get(state_uuid or "", "unknown")
    access_state = (
        "public" if state_uuid == DOCUMENT_STATE_VIEWABLE else "restricted"
    )
    source_url = None
    if court and case_uuid and access_state == "public":
        source_url = (
            f"{API_ROOT}/courts/{court.resource_uuid}/cms/case/{case_uuid}/"
            f"docketentrydocuments/{identifier}"
        )
    return {
        "native_document_id": identifier,
        "backend": "ctrack",
        "source_namespace_id": f"CTRACK_DOCUMENT:{identifier}",
        "document_link_uuid": identifier,
        "docket_entry_uuid": docket_uuid,
        "docket_entry_native_id": docket_uuid,
        "document_type": _text(
            row.get("documentName") or info.get("documentType")
        ),
        "filed_date": _date(docket_header.get("filedDate")),
        "source_url": source_url,
        "mime_type": _text(info.get("contentType")),
        "page_count": _integer(info.get("pageCount")),
        "file_size": _integer(info.get("fileSize")),
        "file_extension": _text(info.get("fileExtension")),
        "access_state": access_state,
        "native_access_state": state,
        "source_access_state": state,
        "source_access_state_uuid": state_uuid,
        "highlights": row.get("highlightsMap"),
        "raw": dict(row),
    }


def _publication_record(
    client: VICourtsClient,
    row: Mapping[str, Any],
    *,
    schema: str,
    publication_uuid: str | None = None,
    court_hint: VICourt | None = None,
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
    raw_items = row.get("publicationItems")
    items = []
    if isinstance(raw_items, list):
        items = [
            {
                "publication_item_uuid": _text(
                    item.get("publicationItemUUID")
                ),
                "case_instance_uuid": _text(item.get("caseInstanceUUID")),
                "case_number": (
                    normalize_case_number(str(item["caseNumber"]))
                    if item.get("caseNumber")
                    else None
                ),
                "title": _text(item.get("title")),
                "decision": _text(item.get("decision")),
                "raw": dict(item),
            }
            for item in raw_items
            if isinstance(item, Mapping)
        ]
    court_uuid = court.resource_uuid if court else "unknown-court"
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{court_uuid}/publication/{identifier}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "publication",
        "backend": "ctrack",
        "source_namespace_id": f"CTRACK_PUBLICATION:{identifier}",
        "publication_uuid": identifier,
        "court_resource_uuid": court.resource_uuid if court else None,
        "native_court_id": court.external_id if court else None,
        "court_name": court.display_name if court else None,
        "publication_number": _text(row.get("publicationNumber")),
        "name": _text(row.get("publicationName")),
        "title": _text(row.get("publicationTitle")),
        "note": _text(row.get("publicationNote")),
        "publication_date": _date(row.get("publicationDate")),
        "case_number": (
            normalize_case_number(str(row["caseNumber"]))
            if row.get("caseNumber")
            else None
        ),
        "publication_items": items,
        "schema_fingerprint": schema,
        "raw": dict(row),
    }


def _resolve_case(
    client: VICourtsClient,
    case_number: str,
    *,
    court: str | None,
    page_size: int,
) -> tuple[VICourt, Mapping[str, Any]] | None:
    selector = normalize_case_number(case_number)
    fetched = client.search_cases(
        selector,
        field="number",
        match_mode="exact",
        court=court,
        page_size=page_size,
    )
    unique: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in fetched.records:
        header = _case_header(row)
        if normalize_case_number(str(header.get("caseNumber") or "")) != selector:
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
        raise VICourtsSelectionError(
            "ambiguous_case_number",
            f"VI case number {selector!r} matched multiple courts",
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
                "hint": "Pass --court with a live external ID, resource UUID, "
                "or unique court name.",
            },
        )
    header = next(iter(unique.values()))
    return client.court_by_external_id(header.get("courtID")), header


def _save_validated_pdf(
    pdf: ValidatedPDF,
    destination_value: str | None,
    *,
    overwrite: bool,
) -> tuple[Path | None, list[str]]:
    if not destination_value:
        return None, []
    destination = Path(destination_value).expanduser()
    if destination.exists() and not overwrite:
        raise OSError(f"destination exists; pass --overwrite: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(pdf.content)
    resolved = destination.resolve()
    return resolved, [str(resolved)]


def _fetch_result(
    query: PublicRecordsQuery,
    fetched: VICourtsFetch,
    records: Sequence[Mapping[str, Any]],
    *,
    warnings: Sequence[str] = (),
) -> PublicRecordsResult:
    combined_warnings = tuple(
        dict.fromkeys((*warnings, *fetched.warnings))
    )
    if fetched.source_overflow:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="source_overflow",
                    message=(
                        "C-Track reported its 10,000-result ceiling; narrow the "
                        "query to enumerate records beyond the source window."
                    ),
                    category="source_pagination",
                    retryable=False,
                    details={
                        "reported_total_elements": fetched.total_elements,
                        "source_result_limit": SOURCE_RESULT_LIMIT,
                    },
                )
            ],
            records=records,
            next_cursor=fetched.next_cursor,
            warnings=combined_warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=fetched.next_cursor,
        warnings=combined_warnings,
    )


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in (
        "query",
        "field",
        "match_mode",
        "court",
        "case_number",
        "docket_entry_uuid",
        "case_uuid",
        "document_uuid",
        "publication_uuid",
        "publication_number",
        "exact",
        "any_words",
        "all_words",
        "none_words",
        "item_id",
        "page_size",
    ):
        if hasattr(args, name):
            value = getattr(args, name)
            if value is not None:
                values[name] = value
    return values


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="United States Virgin Islands",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _make_client(
    args: argparse.Namespace,
    access_decision: Mapping[str, Any],
) -> VICourtsClient:
    limits = access_decision.get("limits") or {}
    interval = max(
        float(getattr(args, "minimum_interval", 0.25)),
        float(limits.get("minimum_interval_seconds") or 0),
    )
    maximum_page_size = min(
        int(limits.get("maximum_page_size") or MAX_PAGE_SIZE),
        MAX_PAGE_SIZE,
    )
    return VICourtsClient(
        session=requests.Session(),
        timeout=float(getattr(args, "timeout", 30.0)),
        retry_policy=RetryPolicy(),
        minimum_interval=interval,
        maximum_page_size=maximum_page_size,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    disposition = _text(decision.get("automation_disposition"))
    status = {
        "human_required": ResultStatus.HUMAN_REQUIRED,
        "restricted": ResultStatus.RESTRICTED,
        "terms_blocked": ResultStatus.TERMS_BLOCKED,
    }.get(disposition or "", ResultStatus.UNAVAILABLE)
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code") or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "VI Courts acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=decision,
            )
        ],
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: VICourtsSelectionError,
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
    )


def _execute_command(
    args: argparse.Namespace,
    client: VICourtsClient,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    command = args.command
    limit = getattr(args, "limit", None)
    page_size = getattr(args, "page_size", 100)
    cursor = getattr(args, "cursor", None)
    court_selector = getattr(args, "court", None)

    if command == "courts":
        fetched = client.list_courts(
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
        )
        records = [
            _court_record(
                client._court_from_record(row),
                schema=fetched.schema_fingerprint,
            )
            for row in fetched.records
        ]
        return _fetch_result(query, fetched, records)

    if command == "search":
        field = getattr(args, "field", "number")
        match_mode = getattr(args, "match_mode", None)
        if field == "party":
            fetched = client.search_parties(
                getattr(args, "query"),
                match_mode=match_mode or "match",
                court=court_selector,
                requested_limit=limit,
                page_size=page_size,
                cursor=cursor,
            )
            records = []
            for row in fetched.records:
                header = _case_header(row)
                records.append(
                    _case_record(
                        client,
                        header,
                        schema=fetched.schema_fingerprint,
                        parties=[_party_record(row)],
                        search_hit=row,
                    )
                )
            return _fetch_result(query, fetched, records)
        fetched = client.search_cases(
            getattr(args, "query"),
            field=field,
            match_mode=match_mode or (
                "exact" if field == "number" else "contains"
            ),
            court=court_selector,
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
        )
        records = [
            _case_record(
                client,
                _case_header(row),
                schema=fetched.schema_fingerprint,
                search_hit=row,
            )
            for row in fetched.records
        ]
        return _fetch_result(query, fetched, records)

    if command in {"case", "docket", "claims", "documents"}:
        case_number = (
            getattr(args, "case_number", None)
            or getattr(args, "query", None)
        )
        resolved = _resolve_case(
            client,
            _required_text(case_number, "case number"),
            court=court_selector,
            page_size=page_size,
        )
        if resolved is None:
            return PublicRecordsResult.success(query, [])
        court, search_header = resolved
        case_uuid = _required_text(
            search_header.get("caseInstanceUUID"),
            "case instance UUID",
        )
        detail = client.get_case(court.resource_uuid, case_uuid)
        detail_header = _case_header(detail)
        detail_schema = schema_fingerprint(inferred_schema([detail]))
        docket_entries: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        warnings: list[str] = []
        next_cursor: str | None = None
        status = ResultStatus.OK

        if command == "docket":
            fetched = client.docket_entries(
                court.resource_uuid,
                case_uuid,
                requested_limit=limit,
                page_size=page_size,
                cursor=cursor,
            )
            docket_entries = [_docket_record(row) for row in fetched.records]
            result = _fetch_result(
                query,
                fetched,
                [
                    _case_record(
                        client,
                        detail_header,
                        schema=detail_schema,
                        docket_entries=docket_entries,
                    )
                ],
            )
            return result

        if command == "claims":
            fetched = client.claims(
                court.resource_uuid,
                case_uuid,
                requested_limit=limit,
                page_size=page_size,
                cursor=cursor,
            )
            claims = [_claim_record(row) for row in fetched.records]
            return _fetch_result(
                query,
                fetched,
                [
                    _case_record(
                        client,
                        detail_header,
                        schema=detail_schema,
                        claims=claims,
                    )
                ],
                warnings=(
                    "The C-Track claims route exposes limited claim-header stubs.",
                ),
            )

        if command == "documents":
            docket_uuid = _required_text(
                getattr(args, "docket_entry_uuid", None),
                "docket entry UUID",
            )
            docket_fetch = client.docket_entries(
                court.resource_uuid,
                case_uuid,
                page_size=page_size,
            )
            matching_rows = [
                row
                for row in docket_fetch.records
                if _text(
                    (
                        row.get("docketEntryHeader")
                        if isinstance(row.get("docketEntryHeader"), Mapping)
                        else {}
                    ).get("docketEntryUUID")
                )
                == docket_uuid
            ]
            if not matching_rows:
                raise VICourtsSelectionError(
                    "docket_entry_not_found",
                    "The docket entry UUID was not present on the selected case",
                    details={
                        "case_number": normalize_case_number(case_number),
                        "docket_entry_uuid": docket_uuid,
                    },
                )
            docket_entry = _docket_record(matching_rows[0])
            document_fetch = client.case_documents(
                court.resource_uuid,
                case_uuid,
                docket_entry_uuid=docket_uuid,
                requested_limit=limit,
                page_size=page_size,
                cursor=cursor,
            )
            docket_entry["documents"] = [
                _document_record(client, row)
                for row in document_fetch.records
            ]
            # The docket row remains authoritative even when the access route
            # returns zero document rows for a secured filing.
            return _fetch_result(
                query,
                document_fetch,
                [
                    _case_record(
                        client,
                        detail_header,
                        schema=detail_schema,
                        docket_entries=[docket_entry],
                    )
                ],
            )

        return PublicRecordsResult(
            query=query,
            status=status,
            records=[
                _case_record(
                    client,
                    detail_header,
                    schema=detail_schema,
                )
            ],
            next_cursor=next_cursor,
            warnings=warnings,
        )

    if command == "document-search":
        fetched = client.search_documents(
            exact=getattr(args, "exact", None),
            any_words=getattr(args, "any_words", None),
            all_words=getattr(args, "all_words", None),
            none_words=getattr(args, "none_words", None),
            court=court_selector,
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
        )
        records = []
        for row in fetched.records:
            header = _case_header(row)
            records.append(
                _case_record(
                    client,
                    header,
                    schema=fetched.schema_fingerprint,
                    documents=[_document_record(client, row)],
                    search_hit=row,
                )
            )
        return _fetch_result(query, fetched, records)

    if command == "download":
        court = client.resolve_court(
            _required_text(court_selector, "court selector")
        )
        case_uuid = _required_text(
            getattr(args, "case_uuid", None),
            "case UUID",
        )
        document_uuid = _required_text(
            getattr(args, "document_uuid", None),
            "document UUID",
        )
        pdf = client.download_document(
            court.resource_uuid,
            case_uuid,
            document_uuid,
        )
        destination, refs = _save_validated_pdf(
            pdf,
            getattr(args, "destination", None),
            overwrite=bool(getattr(args, "overwrite", False)),
        )
        return PublicRecordsResult.success(
            query,
            [
                {
                    "canonical_ref": f"CTRACK_DOCUMENT:{document_uuid}",
                    "source_id": SOURCE_ID,
                    "record_kind": "document_download",
                    "backend": "ctrack",
                    "source_namespace_id": f"CTRACK_DOCUMENT:{document_uuid}",
                    "court_resource_uuid": court.resource_uuid,
                    "case_instance_uuid": case_uuid,
                    "document_link_uuid": document_uuid,
                    "download_status": "saved" if destination else "verified",
                    "storage_path": str(destination) if destination else None,
                    "filename": pdf.filename,
                    "mime_type": pdf.media_type,
                    "size": len(pdf.content),
                    "sha256": pdf.sha256,
                    "cross_system_dedupe_sha256": pdf.sha256,
                    "etag": pdf.etag,
                    "source_url": pdf.source_url,
                }
            ],
            raw_artifact_refs=refs,
        )

    if command == "publications":
        fetched = client.search_publications(
            query=getattr(args, "query", None),
            publication_number=getattr(args, "publication_number", None),
            case_number=getattr(args, "case_number", None),
            court=court_selector,
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
        )
        return _fetch_result(
            query,
            fetched,
            [
                _publication_record(
                    client,
                    row,
                    schema=fetched.schema_fingerprint,
                )
                for row in fetched.records
            ],
        )

    if command == "publication":
        court = client.resolve_court(
            _required_text(court_selector, "court selector")
        )
        publication_uuid = _required_text(
            getattr(args, "publication_uuid", None),
            "publication UUID",
        )
        payload = client.get_publication(
            court.resource_uuid,
            publication_uuid,
        )
        schema = schema_fingerprint(inferred_schema([payload]))
        return PublicRecordsResult.success(
            query,
            [
                _publication_record(
                    client,
                    payload,
                    schema=schema,
                    publication_uuid=publication_uuid,
                    court_hint=court,
                )
            ],
        )

    if command == "legacy-file":
        item_id = int(getattr(args, "item_id"))
        pdf = client.legacy_file(item_id)
        destination, refs = _save_validated_pdf(
            pdf,
            getattr(args, "destination", None),
            overwrite=bool(getattr(args, "overwrite", False)),
        )
        return PublicRecordsResult.success(
            query,
            [
                {
                    "canonical_ref": f"VICOURTS_ITEM:{item_id}",
                    "source_id": SOURCE_ID,
                    "record_kind": "legacy_document_download",
                    "backend": "legacy_displayfile",
                    "source_namespace_id": f"VICOURTS_ITEM:{item_id}",
                    "legacy_item_id": item_id,
                    "download_status": "saved" if destination else "verified",
                    "storage_path": str(destination) if destination else None,
                    "filename": pdf.filename,
                    "mime_type": pdf.media_type,
                    "size": len(pdf.content),
                    "sha256": pdf.sha256,
                    "cross_system_dedupe_sha256": pdf.sha256,
                    "etag": pdf.etag,
                    "source_url": pdf.source_url,
                }
            ],
            raw_artifact_refs=refs,
        )

    if command == "probe":
        info = client.info()
        courts_fetch = client.list_courts(
            requested_limit=10,
            page_size=10,
        )
        case_fetch = client.search_cases(
            "ST-2019-PB-00080",
            field="number",
            match_mode="exact",
            requested_limit=1,
            page_size=1,
        )
        document_fetch = client.search_documents(
            exact="Epstein",
            requested_limit=1,
            page_size=1,
        )
        publication_fetch = client.search_publications(
            publication_number="PB-2026-00032",
            requested_limit=1,
            page_size=1,
        )
        legacy = client.legacy_file(16911884)
        constants = info.get("constants")
        if not isinstance(constants, Mapping):
            constants = {}
        record = {
            "canonical_ref": f"VICOURTS_PROBE:{API_ROOT}",
            "source_id": SOURCE_ID,
            "record_kind": "probe",
            "backend": "mixed_probe",
            "checks": {
                "manage_info": True,
                "reported_search_results_limit": _integer(
                    constants.get("SEARCH_RESULTS_LIMIT")
                ),
                "courts": len(courts_fetch.records),
                "case_sentinel": len(case_fetch.records),
                "document_sentinel": len(document_fetch.records),
                "publication_sentinel": len(publication_fetch.records),
                "legacy_item_16911884": {
                    "size": len(legacy.content),
                    "sha256": legacy.sha256,
                },
            },
        }
        return PublicRecordsResult.success(query, [record])

    raise ValueError(f"unsupported VI Courts command: {command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: VICourtsClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one command and return the canonical public-record envelope."""

    query = build_query(args)
    decision = (
        dict(access_decision)
        if access_decision is not None
        else {
            "allowed": True,
            "access_class": "B",
            "automation_disposition": "machine",
            "limits": {"maximum_page_size": MAX_PAGE_SIZE},
        }
    )
    if not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    owned_client = client is None
    source_client = client or _make_client(args, decision)
    try:
        result = _execute_command(args, source_client, query)
    except VICourtsSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
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
        )
    finally:
        if owned_client:
            closer = getattr(source_client, "close", None)
            if not callable(closer):
                closer = getattr(
                    getattr(source_client, "transport", None),
                    "close",
                    None,
                )
            if callable(closer):
                closer()

    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"VI Courts {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"VI Courts {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("raw_case_number")
            or record.get("publication_uuid")
            or record.get("document_link_uuid")
            or record.get("legacy_item_id")
            or record.get("court_resource_uuid")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    add_output_args(parser)


def _add_paging(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional caller-selected record ceiling",
    )
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--cursor")


def _add_query_runtime(parser: argparse.ArgumentParser) -> None:
    _add_paging(parser)
    _add_runtime(parser)


def _positive_item_id(value: str) -> int:
    try:
        item_id = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("itemId must be numeric") from error
    if item_id <= 0:
        raise argparse.ArgumentTypeError("itemId must be positive")
    return item_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query verified public Virgin Islands judiciary routes"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    courts = sub.add_parser("courts", help="List live C-Track courts")
    _add_query_runtime(courts)

    search = sub.add_parser(
        "search",
        help="Search case numbers, case titles, or parties",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=("number", "title", "party"),
        default="number",
    )
    search.add_argument(
        "--match-mode",
        choices=tuple(QUERY_TYPES),
        help=(
            "number/title: starts, exact, contains; "
            "party: match, phonetic"
        ),
    )
    search.add_argument(
        "--court",
        help="Live external court ID, resource UUID, or unique court name",
    )
    _add_query_runtime(search)

    case = sub.add_parser("case", help="Fetch one case detail")
    case.add_argument("case_number")
    case.add_argument("--court")
    _add_query_runtime(case)

    docket = sub.add_parser("docket", help="Fetch all or part of one docket")
    docket.add_argument("case_number")
    docket.add_argument("--court")
    _add_query_runtime(docket)

    claims = sub.add_parser("claims", help="Fetch limited C-Track claim stubs")
    claims.add_argument("case_number")
    claims.add_argument("--court")
    _add_query_runtime(claims)

    documents = sub.add_parser(
        "documents",
        help="Fetch access metadata for one docket entry",
    )
    documents.add_argument("case_number")
    documents.add_argument("docket_entry_uuid")
    documents.add_argument("--court")
    _add_query_runtime(documents)

    document_search = sub.add_parser(
        "document-search",
        help="Search C-Track OCR text",
    )
    document_search.add_argument("--exact")
    document_search.add_argument("--any", dest="any_words")
    document_search.add_argument("--all", dest="all_words")
    document_search.add_argument("--none", dest="none_words")
    document_search.add_argument("--court")
    _add_query_runtime(document_search)

    download = sub.add_parser(
        "download",
        help="Validate and optionally save one viewable C-Track PDF",
    )
    download.add_argument("court")
    download.add_argument("case_uuid")
    download.add_argument("document_uuid")
    download.add_argument("destination", nargs="?")
    download.add_argument("--overwrite", action="store_true")
    _add_runtime(download)

    publications = sub.add_parser(
        "publications",
        help="Search C-Track publications",
    )
    publications.add_argument("query", nargs="?")
    publications.add_argument("--publication-number")
    publications.add_argument("--case-number")
    publications.add_argument("--court")
    _add_query_runtime(publications)

    publication = sub.add_parser(
        "publication",
        help="Fetch one C-Track publication",
    )
    publication.add_argument("court")
    publication.add_argument("publication_uuid")
    _add_runtime(publication)

    legacy = sub.add_parser(
        "legacy-file",
        help="Validate and optionally save one numeric legacy PDF item",
    )
    legacy.add_argument("item_id", type=_positive_item_id)
    legacy.add_argument("destination", nargs="?")
    legacy.add_argument("--overwrite", action="store_true")
    _add_runtime(legacy)

    probe = sub.add_parser(
        "probe",
        help="Run bounded sentinels against each verified route family",
    )
    _add_runtime(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "timeout", 0) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    for name in ("limit", "page_size"):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.command == "document-search" and not any(
        _text(getattr(args, name, None))
        for name in ("exact", "any_words", "all_words", "none_words")
    ):
        parser.error(
            "document-search requires --exact, --any, --all, or --none"
        )
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
