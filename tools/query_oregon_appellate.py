#!/usr/bin/env python3
"""Query Oregon's official Appellate Record Search public API.

The portal covers the Oregon Court of Appeals and Oregon Supreme Court.  Its
anonymous C-Track API exposes separate case, party, docket, calendar, party,
hearing, judgment, group, and document-access-metadata components.  This
adapter preserves those component boundaries and does not infer that public
document metadata means that the underlying file is retrievable.

Examples:
    uv run python tools/query_oregon_appellate.py courts --json
    uv run python tools/query_oregon_appellate.py search-case A182332 \
        --field number --match-mode exact --output /tmp/or-case.json
    uv run python tools/query_oregon_appellate.py search-party "State of Oregon"
    uv run python tools/query_oregon_appellate.py case A182332
    uv run python tools/query_oregon_appellate.py docket A182332
    uv run python tools/query_oregon_appellate.py parties A182332
    uv run python tools/query_oregon_appellate.py calendar --after 2026-01-01
    uv run python tools/query_oregon_appellate.py document-metadata A182332
    uv run python tools/query_oregon_appellate.py probe
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
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
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceSchemaError,
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
        sha256_fingerprint,
    )
    from public_records_http import (
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceSchemaError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-or-appellate-record-search"
STATE_CODE = "OR"
STATE_GEOID = "41"
PORTAL_ROOT = "https://trportal.courts.oregon.gov"
PORTAL_HOME = f"{PORTAL_ROOT}/portal/home"
PORTAL_SEARCH = f"{PORTAL_ROOT}/portal/search"
API_ROOT = "https://trportal-api.courts.oregon.gov"
INFO_URL = f"{API_ROOT}/manage/info"
COURTS_URL = f"{API_ROOT}/courts"
CASE_SEARCH_URL = f"{API_ROOT}/courts/cms/cases"
PARTY_SEARCH_URL = f"{API_ROOT}/courts/cms/parties"
EVENT_SEARCH_URL = f"{API_ROOT}/courts/cms/events"
DOCUMENT_ACCESS_URL = f"{API_ROOT}/courts/cms/docketentrydocumentsaccess"

COURT_OF_APPEALS_UUID = "3d764b2a-2faa-4613-aac6-7da3b06325f4"
SUPREME_COURT_UUID = "f28c1f7b-0af7-4462-b253-bd5371f86443"
COURT_OF_APPEALS_EXTERNAL_ID = "1"
SUPREME_COURT_EXTERNAL_ID = "2"

QUERY_TYPES = {
    "starts": "10461",
    "exact": "10462",
    "contains": "10463",
    "match": "300054",
    "phonetic": "300055",
}
CASE_MATCH_MODES = frozenset({"starts", "exact", "contains"})
PARTY_MATCH_MODES = frozenset({"match", "phonetic"})
MAX_PAGE_SIZE = 1_000
SOURCE_RESULT_LIMIT = 10_000
CURSOR_VERSION = 1
CURSOR_PREFIX = "orapp:v1:"

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
    name="Oregon Appellate Record Search",
    source_role="appellate_case_docket_calendar_and_document_metadata_portal",
    base_url=PORTAL_HOME,
    dataset_id="oregon-ctrack-appellate-public",
    metadata={
        "authority": "Oregon Judicial Department",
        "coverage": "Oregon Court of Appeals and Oregon Supreme Court",
        "state_code": STATE_CODE,
        "authentication": "none",
        "source_result_limit": SOURCE_RESULT_LIMIT,
        "courts": {
            COURT_OF_APPEALS_EXTERNAL_ID: COURT_OF_APPEALS_UUID,
            SUPREME_COURT_EXTERNAL_ID: SUPREME_COURT_UUID,
        },
    },
)

SOURCE_WARNINGS = (
    "This source covers Oregon appellate courts; circuit and tax court case "
    "records are separate source systems.",
    "Docket document counts, public metadata, and retrievable file state are "
    "reported as separate observations.",
)


@dataclass(frozen=True)
class OregonAppellateCourt:
    """One court in the live Oregon appellate directory."""

    resource_uuid: str
    external_id: str
    display_name: str
    active: bool
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class CursorState:
    """Opaque continuation state bound to one source query and boundary row."""

    query_fingerprint: str
    offset: int
    anchor: str
    total_elements: int


@dataclass(frozen=True)
class SpringFetch:
    """One result window plus explicit source and continuation metadata."""

    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    schema: Mapping[str, Any]
    schema_fingerprint: str
    pages_fetched: int
    requests_made: int
    total_elements: int
    total_pages: int
    page_size: int
    start_offset: int
    end_offset: int
    source_ceiling: bool
    complete: bool
    cursor_anchor_verified: bool
    count_changed_since_cursor: bool
    warnings: tuple[str, ...] = ()


class OregonAppellateSelectionError(ValueError):
    """A selector or continuation state cannot be used safely."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        category: str = "query",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=False,
            details=self.details,
        )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise ValueError(f"Oregon appellate {field_name} must not be blank")
    return normalized


def _integer(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _positive(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _date(value: Any) -> str | None:
    raw = _text(value)
    if raw is None:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", raw)
    return match.group(1) if match else raw


def _source_datetime(value: str | None, *, end_of_day: bool) -> str | None:
    raw = _text(value)
    if raw is None:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    try:
        calendar_date = date.fromisoformat(raw)
    except ValueError as error:
        raise OregonAppellateSelectionError(
            "invalid_date_filter",
            f"Invalid ISO calendar date: {raw}",
            category="query_selection",
            details={"value": raw},
        ) from error
    boundary = time(23, 59, 59, 999000) if end_of_day else time.min
    return datetime.combine(
        calendar_date,
        boundary,
        tzinfo=timezone.utc,
    ).isoformat(timespec="milliseconds")


def _embedded_records(payload: Any, *, url: str) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "Oregon appellate paginated response must be an object",
            url=url,
        )
    embedded = payload.get("_embedded")
    page = payload.get("page")
    if embedded is None and isinstance(page, Mapping):
        if _integer(page.get("totalElements")) == 0:
            return []
    if not isinstance(embedded, Mapping):
        raise SourceSchemaError(
            "Oregon appellate response lacks _embedded",
            url=url,
        )
    records = embedded.get("results")
    if not isinstance(records, list) or any(
        not isinstance(record, Mapping) for record in records
    ):
        raise SourceSchemaError(
            "Oregon appellate response lacks an object results array",
            url=url,
        )
    return list(records)


def _page_metadata(payload: Mapping[str, Any], *, url: str) -> dict[str, int]:
    page = payload.get("page")
    if not isinstance(page, Mapping):
        raise SourceSchemaError(
            "Oregon appellate response lacks Spring page metadata",
            url=url,
        )
    metadata: dict[str, int] = {}
    for key in ("size", "totalElements", "totalPages", "number"):
        value = _integer(page.get(key))
        if value is None or value < 0:
            raise SourceSchemaError(
                f"Oregon appellate page metadata lacks numeric {key}",
                url=url,
            )
        metadata[key] = value
    return metadata


def _query_cursor_fingerprint(
    url: str,
    params: Mapping[str, Any],
    anchor_kind: str,
) -> str:
    return sha256_fingerprint(
        {
            "cursor_version": CURSOR_VERSION,
            "source_id": SOURCE_ID,
            "url": url,
            "params": dict(params),
            "anchor_kind": anchor_kind,
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "q": state.query_fingerprint,
        "o": state.offset,
        "a": state.anchor,
        "n": state.total_elements,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return f"{CURSOR_PREFIX}{encoded.rstrip('=')}"


def _decode_cursor(
    cursor: str | None,
    *,
    expected_query_fingerprint: str,
) -> CursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise OregonAppellateSelectionError(
            "invalid_cursor",
            "cursor is not an Oregon appellate continuation",
            category="pagination",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(f"{token}{padding}").decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OregonAppellateSelectionError(
            "invalid_cursor",
            "Oregon appellate cursor payload is malformed",
            category="pagination",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("v") != CURSOR_VERSION:
        raise OregonAppellateSelectionError(
            "invalid_cursor",
            "Oregon appellate cursor version or payload is invalid",
            category="pagination",
        )
    if payload.get("q") != expected_query_fingerprint:
        raise OregonAppellateSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different Oregon appellate query parameters",
            category="pagination",
            details={
                "cursor_query_fingerprint": payload.get("q"),
                "search_query_fingerprint": expected_query_fingerprint,
            },
        )
    offset = payload.get("o")
    total = payload.get("n")
    anchor = payload.get("a")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset <= 0
        or isinstance(total, bool)
        or not isinstance(total, int)
        or total < 0
        or not isinstance(anchor, str)
        or not anchor
    ):
        raise OregonAppellateSelectionError(
            "invalid_cursor",
            "Oregon appellate cursor lacks a valid offset, anchor, or count",
            category="pagination",
        )
    return CursorState(
        query_fingerprint=str(payload["q"]),
        offset=offset,
        anchor=anchor,
        total_elements=total,
    )


def _case_header(row: Mapping[str, Any]) -> Mapping[str, Any]:
    header = row.get("caseHeader")
    if isinstance(header, Mapping):
        return header
    if row.get("caseInstanceUUID") and row.get("caseNumber"):
        return row
    raise ValueError("Oregon appellate case payload lacks caseHeader")


def _party_identity(row: Mapping[str, Any]) -> tuple[str, bool]:
    """Return the native case-party UUID or a stable search-hit identity."""

    header = row.get("partyHeader")
    if not isinstance(header, Mapping):
        raise ValueError("Oregon appellate party payload lacks partyHeader")
    native = _text(header.get("casePartyUUID"))
    if native:
        return native, False
    actor = header.get("partyActorInstance")
    if not isinstance(actor, Mapping):
        raise ValueError("Oregon appellate party payload lacks party actor")
    case_header = row.get("caseHeader")
    if not isinstance(case_header, Mapping):
        case_header = {}
    identity_payload = {
        "case_instance_uuid": _text(case_header.get("caseInstanceUUID")),
        "case_number": _text(case_header.get("caseNumber")),
        "role": _text(header.get("partySubType") or header.get("partyType")),
        "display_name": _text(
            actor.get("displayName") or actor.get("sortName")
        ),
        "order_by": _integer(row.get("orderBy")),
    }
    if not identity_payload["case_instance_uuid"] or not identity_payload[
        "display_name"
    ]:
        raise ValueError(
            "Oregon appellate party search hit lacks a stable case and name"
        )
    return f"derived:{sha256_fingerprint(identity_payload)}", True


def _anchor_value(row: Mapping[str, Any], anchor_kind: str) -> str:
    if anchor_kind == "court":
        return _required_text(row.get("resourceID"), "court resourceID")
    if anchor_kind == "case":
        return _required_text(
            _case_header(row).get("caseInstanceUUID"),
            "case instance UUID",
        )
    if anchor_kind == "party":
        party_id, _ = _party_identity(row)
        case_id = _text(_case_header(row).get("caseInstanceUUID")) or ""
        return f"{case_id}:{party_id}"
    if anchor_kind == "docket":
        header = row.get("docketEntryHeader")
        if not isinstance(header, Mapping):
            raise ValueError("Oregon appellate docket payload lacks header")
        return _required_text(
            header.get("docketEntryUUID"),
            "docket entry UUID",
        )
    if anchor_kind == "event":
        return _required_text(row.get("eventUUID"), "event UUID")
    if anchor_kind == "document":
        return _required_text(
            row.get("documentLinkUUID"),
            "document link UUID",
        )
    if anchor_kind == "hearing":
        return _required_text(
            row.get("hearingUUID")
            or row.get("eventUUID")
            or row.get("resourceID"),
            "hearing UUID",
        )
    if anchor_kind == "judgment":
        return _required_text(
            row.get("judgmentUUID")
            or row.get("judgmentInstanceUUID")
            or row.get("resourceID"),
            "judgment UUID",
        )
    raise ValueError(f"unsupported Oregon appellate anchor kind: {anchor_kind}")


class OregonAppellateClient(_BaseJSONClient):
    """Transport-injectable client for Oregon's verified C-Track routes."""

    def __init__(
        self,
        *args: Any,
        maximum_page_size: int = MAX_PAGE_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.maximum_page_size = min(
            _positive(maximum_page_size, "maximum_page_size")
            or MAX_PAGE_SIZE,
            MAX_PAGE_SIZE,
        )
        self._courts: tuple[OregonAppellateCourt, ...] | None = None

    def close(self) -> None:
        closer = getattr(self.transport, "close", None)
        if callable(closer):
            closer()

    def _bounded_page_size(self, value: int) -> int:
        return min(
            _positive(value, "page_size") or self.maximum_page_size,
            self.maximum_page_size,
        )

    def _request_page(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        offset: int,
        page_size: int,
    ) -> tuple[list[Mapping[str, Any]], dict[str, int], int]:
        """Fetch the Spring page containing one zero-based result offset."""

        source_size = page_size
        for _ in range(2):
            page_number = offset // source_size
            payload = self._request_json(
                url,
                params={
                    **dict(params),
                    "page": page_number,
                    "size": page_size,
                },
            )
            if not isinstance(payload, Mapping):
                raise SourceSchemaError(
                    "Oregon appellate Spring page must be an object",
                    url=url,
                )
            records = _embedded_records(payload, url=url)
            metadata = _page_metadata(payload, url=url)
            reported_size = metadata["size"]
            if reported_size <= 0 or reported_size == source_size:
                return records, metadata, offset % max(reported_size, 1)
            source_size = reported_size
        raise SourceSchemaError(
            "Oregon appellate source changed page size during one request",
            url=url,
        )

    def _fetch_hal(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        requested_limit: int | None,
        page_size: int,
        cursor: str | None = None,
        anchor_kind: str,
    ) -> SpringFetch:
        """Fetch zero-based pages with query-bound, boundary-anchored cursors."""

        size = self._bounded_page_size(page_size)
        requested_limit = _positive(requested_limit, "requested_limit")
        source_params = dict(params or {})
        query_fingerprint = _query_cursor_fingerprint(
            url,
            source_params,
            anchor_kind,
        )
        state = _decode_cursor(
            cursor,
            expected_query_fingerprint=query_fingerprint,
        )
        start_offset = state.offset if state else 0
        current_offset = start_offset
        records: list[Mapping[str, Any]] = []
        total_elements = 0
        total_pages = 0
        pages_fetched = 0
        initial_requests = self.request_count
        anchor_verified = False
        count_changed = False
        warnings: list[str] = []

        if state is not None:
            boundary_rows, boundary_meta, boundary_index = self._request_page(
                url,
                params=source_params,
                offset=state.offset - 1,
                page_size=size,
            )
            pages_fetched += 1
            if boundary_index >= len(boundary_rows):
                raise OregonAppellateSelectionError(
                    "cursor_snapshot_changed",
                    "continuation boundary no longer exists at its source offset",
                    category="pagination",
                    details={
                        "cursor_offset": state.offset,
                        "boundary_rows": len(boundary_rows),
                    },
                )
            observed_anchor = _anchor_value(
                boundary_rows[boundary_index],
                anchor_kind,
            )
            if observed_anchor != state.anchor:
                raise OregonAppellateSelectionError(
                    "cursor_snapshot_changed",
                    "Oregon appellate result ordering changed at the cursor boundary",
                    category="pagination",
                    details={
                        "cursor_offset": state.offset,
                        "expected_anchor": state.anchor,
                        "observed_anchor": observed_anchor,
                    },
                )
            anchor_verified = True
            total_elements = boundary_meta["totalElements"]
            total_pages = boundary_meta["totalPages"]
            count_changed = total_elements != state.total_elements
            if count_changed:
                warnings.append(
                    "The source result count changed after the cursor was issued; "
                    "the anchored boundary remained stable."
                )

        last_anchor: str | None = state.anchor if state else None
        while requested_limit is None or len(records) < requested_limit:
            if current_offset >= SOURCE_RESULT_LIMIT:
                break
            page_rows, metadata, within_page = self._request_page(
                url,
                params=source_params,
                offset=current_offset,
                page_size=size,
            )
            pages_fetched += 1
            total_elements = metadata["totalElements"]
            total_pages = metadata["totalPages"]
            if current_offset >= total_elements or within_page >= len(page_rows):
                break
            available = page_rows[within_page:]
            remaining = (
                None
                if requested_limit is None
                else requested_limit - len(records)
            )
            source_window = SOURCE_RESULT_LIMIT - current_offset
            take = min(len(available), source_window)
            if remaining is not None:
                take = min(take, remaining)
            selected = available[:take]
            if not selected:
                break
            records.extend(selected)
            current_offset += len(selected)
            last_anchor = _anchor_value(selected[-1], anchor_kind)
            if current_offset >= total_elements:
                break
            if remaining is not None and len(selected) >= remaining:
                break

        source_ceiling = total_elements >= SOURCE_RESULT_LIMIT
        has_more_in_window = current_offset < min(
            total_elements,
            SOURCE_RESULT_LIMIT,
        )
        next_cursor = None
        if has_more_in_window and last_anchor is not None:
            next_cursor = _encode_cursor(
                CursorState(
                    query_fingerprint=query_fingerprint,
                    offset=current_offset,
                    anchor=last_anchor,
                    total_elements=total_elements,
                )
            )
        if source_ceiling:
            warnings.append(
                "The source reported its 10,000-result search ceiling; narrower "
                "criteria are needed to determine or enumerate any records beyond "
                "the native window."
            )
        observed_schema = inferred_schema(records)
        return SpringFetch(
            records=tuple(records),
            next_cursor=next_cursor,
            schema=observed_schema,
            schema_fingerprint=schema_fingerprint(observed_schema),
            pages_fetched=pages_fetched,
            requests_made=self.request_count - initial_requests,
            total_elements=total_elements,
            total_pages=total_pages,
            page_size=size,
            start_offset=start_offset,
            end_offset=current_offset,
            source_ceiling=source_ceiling,
            complete=not source_ceiling and current_offset >= total_elements,
            cursor_anchor_verified=anchor_verified,
            count_changed_since_cursor=count_changed,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _court_from_record(
        record: Mapping[str, Any],
    ) -> OregonAppellateCourt:
        return OregonAppellateCourt(
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
        page_size: int = MAX_PAGE_SIZE,
        cursor: str | None = None,
    ) -> SpringFetch:
        fetched = self._fetch_hal(
            COURTS_URL,
            params={"fields": "*,locations(*)"},
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="court",
        )
        if cursor is None and fetched.next_cursor is None:
            self._courts = tuple(
                self._court_from_record(row) for row in fetched.records
            )
        return fetched

    def courts(self) -> tuple[OregonAppellateCourt, ...]:
        if self._courts is None:
            fetched = self.list_courts(page_size=MAX_PAGE_SIZE)
            self._courts = tuple(
                self._court_from_record(row) for row in fetched.records
            )
        return self._courts

    def resolve_court(self, selector: str) -> OregonAppellateCourt:
        value = _required_text(selector, "court selector")
        folded = value.casefold()
        aliases = {
            "coa": COURT_OF_APPEALS_UUID,
            "court of appeals": COURT_OF_APPEALS_UUID,
            "supreme": SUPREME_COURT_UUID,
            "supreme court": SUPREME_COURT_UUID,
        }
        alias_uuid = aliases.get(folded)
        exact = [
            court
            for court in self.courts()
            if value in {court.resource_uuid, court.external_id}
            or folded == court.display_name.casefold()
            or court.resource_uuid == alias_uuid
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
            raise OregonAppellateSelectionError(
                "ambiguous_court_selector",
                f"Oregon appellate court selector {value!r} is ambiguous",
                status=ResultStatus.UNAVAILABLE,
                category="query_selection",
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
        raise OregonAppellateSelectionError(
            "court_not_found",
            f"Oregon appellate court selector {value!r} was not found",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
            details={"selector": value},
        )

    def court_by_external_id(self, external_id: Any) -> OregonAppellateCourt:
        value = _required_text(external_id, "case courtID")
        matches = [
            court for court in self.courts() if court.external_id == value
        ]
        if len(matches) != 1:
            raise SourceSchemaError(
                f"Oregon appellate case references unknown courtID {value!r}",
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
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> SpringFetch:
        selector = _required_text(query, "case query")
        if match_mode not in CASE_MATCH_MODES:
            raise OregonAppellateSelectionError(
                "invalid_match_mode",
                "case match mode must be starts, exact, or contains",
                category="query_selection",
            )
        if field == "auto":
            field = (
                "number"
                if re.fullmatch(r"[AS]\d{5,8}", selector, re.I)
                else "title"
            )
        if field not in {"number", "title"}:
            raise OregonAppellateSelectionError(
                "invalid_case_field",
                "case field must be auto, number, or title",
                category="query_selection",
            )
        prefix = (
            "caseHeader.caseNumber"
            if field == "number"
            else "caseHeader.caseTitle"
        )
        params: dict[str, Any] = {
            prefix: selector.upper() if field == "number" else selector,
            f"{prefix}SearchType": QUERY_TYPES[match_mode],
            "sort": (
                "caseHeader.filedDate,desc",
                "caseHeader.caseInstanceUUID,asc",
            ),
        }
        if court:
            params["caseHeader.courtID"] = self.resolve_court(
                court
            ).resource_uuid
        after = _source_datetime(filed_after, end_of_day=False)
        before = _source_datetime(filed_before, end_of_day=True)
        if after:
            params["caseHeader.filedDateFrom"] = after
        if before:
            params["caseHeader.filedDateTo"] = before
        return self._fetch_hal(
            CASE_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="case",
        )

    def search_parties(
        self,
        query: str,
        *,
        match_mode: str = "match",
        court: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        requested_limit: int | None = 50,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> SpringFetch:
        if match_mode not in PARTY_MATCH_MODES:
            raise OregonAppellateSelectionError(
                "invalid_match_mode",
                "party match mode must be match or phonetic",
                category="query_selection",
            )
        params: dict[str, Any] = {
            "partyHeader.partyActorInstance.displayName": _required_text(
                query,
                "party query",
            ),
            "partyHeader.partyActorInstance.displayNameSearchType": (
                QUERY_TYPES[match_mode]
            ),
            "sort": (
                "score,desc",
                "caseHeader.caseInstanceUUID,asc",
                "partyHeader.casePartyUUID,asc",
            ),
        }
        if court:
            params["caseHeader.courtID"] = self.resolve_court(
                court
            ).resource_uuid
        after = _source_datetime(filed_after, end_of_day=False)
        before = _source_datetime(filed_before, end_of_day=True)
        if after:
            params["caseHeader.filedDateFrom"] = after
        if before:
            params["caseHeader.filedDateTo"] = before
        return self._fetch_hal(
            PARTY_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="party",
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
                "Oregon appellate case detail must be an object",
                url=url,
            )
        return payload

    def _case_component(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        component: str,
        *,
        requested_limit: int | None,
        page_size: int,
        cursor: str | None,
        anchor_kind: str,
        sort: Sequence[str] = (),
    ) -> SpringFetch:
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"cases/{quote(identifier, safe='')}/{component}"
        )
        params: dict[str, Any] = {}
        if sort:
            params["sort"] = tuple(sort)
        return self._fetch_hal(
            url,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind=anchor_kind,
        )

    def docket_entries(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> SpringFetch:
        return self._case_component(
            court_resource_uuid,
            case_uuid,
            "docketentries",
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="docket",
            sort=(
                "docketEntryHeader.filedDate,desc",
                "docketEntryHeader.docketEntryUUID,asc",
            ),
        )

    def case_parties(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> SpringFetch:
        return self._case_component(
            court_resource_uuid,
            case_uuid,
            "parties",
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="party",
            sort=("orderBy,asc", "partyHeader.casePartyUUID,asc"),
        )

    def case_hearings(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> SpringFetch:
        return self._case_component(
            court_resource_uuid,
            case_uuid,
            "hearings",
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="hearing",
            sort=("startDate,asc",),
        )

    def case_judgments(
        self,
        court_resource_uuid: str,
        case_uuid: str,
        *,
        requested_limit: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> SpringFetch:
        return self._case_component(
            court_resource_uuid,
            case_uuid,
            "judgments",
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="judgment",
        )

    def case_groups(
        self,
        court_resource_uuid: str,
        case_uuid: str,
    ) -> tuple[Mapping[str, Any], ...]:
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        url = (
            f"{API_ROOT}/courts/{quote(court.resource_uuid, safe='')}/cms/"
            f"cases/{quote(identifier, safe='')}/groups"
        )
        payload = self._request_json(url, params={})
        if not isinstance(payload, list) or any(
            not isinstance(row, Mapping) for row in payload
        ):
            raise SourceSchemaError(
                "Oregon appellate case groups response must be an object array",
                url=url,
            )
        return tuple(payload)

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
    ) -> SpringFetch:
        court = self.resolve_court(court_resource_uuid)
        identifier = _required_text(case_uuid, "case UUID")
        params: dict[str, Any] = {
            "caseHeader.courtID": court.resource_uuid,
            "caseHeader.caseInstanceUUID": identifier,
            "sort": ("documentName,asc", "documentLinkUUID,asc"),
        }
        if docket_entry_uuid:
            params["docketEntryHeader.docketEntryUUID"] = _required_text(
                docket_entry_uuid,
                "docket entry UUID",
            )
        if document_uuid:
            params["documentLinkUUID"] = _required_text(
                document_uuid,
                "document UUID",
            )
        return self._fetch_hal(
            DOCUMENT_ACCESS_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="document",
        )

    def search_events(
        self,
        *,
        court: str | None = None,
        after: str | None = None,
        before: str | None = None,
        requested_limit: int | None = 100,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> SpringFetch:
        params: dict[str, Any] = {
            "sort": ("startDate,asc", "eventUUID,asc"),
        }
        if court:
            params["courtID"] = self.resolve_court(court).resource_uuid
        start = _source_datetime(after, end_of_day=False)
        end = _source_datetime(before, end_of_day=True)
        if start:
            params["startDateFrom"] = start
        if end:
            params["startDateTo"] = end
        return self._fetch_hal(
            EVENT_SEARCH_URL,
            params=params,
            requested_limit=requested_limit,
            page_size=page_size,
            cursor=cursor,
            anchor_kind="event",
        )

    def info(self) -> Mapping[str, Any]:
        payload = self._request_json(INFO_URL, params={})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Oregon appellate manage/info response must be an object",
                url=INFO_URL,
            )
        return payload


def _court_level(court: OregonAppellateCourt) -> str:
    if court.external_id == SUPREME_COURT_EXTERNAL_ID:
        return "supreme"
    return "intermediate_appellate"


def _court_payload(court: OregonAppellateCourt) -> dict[str, Any]:
    return {
        "court_id": court.resource_uuid,
        "native_court_id": court.external_id,
        "name": court.display_name,
        "state_code": STATE_CODE,
        "court_level": _court_level(court),
        "official_url": PORTAL_HOME,
    }


def _fetch_metadata(fetched: SpringFetch) -> dict[str, Any]:
    if fetched.source_ceiling:
        completeness = "bounded_by_native_ceiling"
    elif fetched.complete:
        completeness = "complete"
    else:
        completeness = "continuation_available"
    return {
        "reported_total_elements": fetched.total_elements,
        "reported_total_pages": fetched.total_pages,
        "source_result_limit": SOURCE_RESULT_LIMIT,
        "source_ceiling_reached": fetched.source_ceiling,
        "returned_in_envelope": len(fetched.records),
        "start_offset": fetched.start_offset,
        "end_offset": fetched.end_offset,
        "page_size": fetched.page_size,
        "complete": fetched.complete,
        "completeness": completeness,
        "cursor_anchor_verified": fetched.cursor_anchor_verified,
        "count_changed_since_cursor": fetched.count_changed_since_cursor,
    }


def _court_record(
    court: OregonAppellateCourt,
    *,
    schema: str,
    retrieval: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{court.resource_uuid}/court/"
            f"{court.external_id}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "court",
        "backend": "oregon_ctrack",
        "source_namespace_id": f"OR_CTRACK_COURT:{court.resource_uuid}",
        "court_resource_uuid": court.resource_uuid,
        "native_court_id": court.external_id,
        "name": court.display_name,
        "state_code": STATE_CODE,
        "court_level": _court_level(court),
        "active": court.active,
        "official_url": PORTAL_HOME,
        "schema_fingerprint": schema,
        "retrieval": dict(retrieval),
        "raw": dict(court.raw),
    }


def _originating_relations(header: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_values = header.get("originatingCourtCases")
    if not isinstance(raw_values, list):
        return []
    relations: list[dict[str, Any]] = []
    for row in raw_values:
        if not isinstance(row, Mapping):
            continue
        case_number = _text(row.get("originatingCaseNumber"))
        if case_number is None:
            continue
        court_name = _text(row.get("originatingCourtName"))
        county = None
        if court_name:
            match = re.match(r"^(.+?) County Circuit Court$", court_name)
            if match:
                county = match.group(1)
        relations.append(
            {
                "relation_type": "originating_trial_case",
                "raw_case_number": case_number,
                "court_name": court_name,
                "county": county,
                "access_state": "public",
                "source_url": PORTAL_SEARCH,
                "raw": dict(row),
            }
        )
    return relations


def _case_record(
    client: OregonAppellateClient | Any,
    header: Mapping[str, Any],
    *,
    schema: str,
    parties: Sequence[Mapping[str, Any]] = (),
    docket_entries: Sequence[Mapping[str, Any]] = (),
    documents: Sequence[Mapping[str, Any]] = (),
    case_events: Sequence[Mapping[str, Any]] = (),
    judgments: Sequence[Mapping[str, Any]] = (),
    groups: Sequence[Mapping[str, Any]] = (),
    components: Mapping[str, Any] | None = None,
    search_hit: Mapping[str, Any] | None = None,
    retrieval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    case_uuid = _required_text(
        header.get("caseInstanceUUID"),
        "case instance UUID",
    )
    case_number = _required_text(header.get("caseNumber"), "case number").upper()
    court = client.court_by_external_id(header.get("courtID"))
    native_status = _text(header.get("caseStatus"))
    status = native_status or (
        "closed" if header.get("closedFlag") else "open"
    )
    record: dict[str, Any] = {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court.resource_uuid,
            case_number,
            native_id=case_uuid,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "backend": "oregon_ctrack",
        "source_namespace_id": f"OR_CTRACK_CASE:{case_uuid}",
        "court": _court_payload(court),
        "raw_case_number": case_number,
        "display_case_number": _text(header.get("caseNumber")),
        "source_internal_id": case_uuid,
        "case_instance_uuid": case_uuid,
        "caption": _text(
            header.get("caseCaption") or header.get("caseTitle")
        ),
        "case_title": _text(header.get("caseTitle")),
        "case_type": _text(
            header.get("caseClassification")
            or header.get("caseCategory")
            or header.get("caseClassGroupType")
        ),
        "case_classification_id": _text(
            header.get("caseClassificationID")
        ),
        "filing_date": _date(header.get("filedDate")),
        "status": status,
        "native_status": native_status,
        "closed_flag": bool(header.get("closedFlag")),
        "access_state": (
            "restricted" if header.get("nonPublicFlag") else "public"
        ),
        "certified_record": False,
        "source_url": (
            f"{PORTAL_ROOT}/portal/court/{court.resource_uuid}/case/{case_uuid}"
        ),
        "case_relations": _originating_relations(header),
        "parties": list(parties),
        "docket_entries": list(docket_entries),
        "documents": list(documents),
        "case_events": list(case_events),
        "judgments": list(judgments),
        "case_groups": list(groups),
        "components": dict(components or {}),
        "schema_fingerprint": schema,
        "raw": dict(header),
    }
    if search_hit is not None:
        record["search_hit"] = dict(search_hit)
    if retrieval is not None:
        record["retrieval"] = dict(retrieval)
    return record


def _attorney_record(row: Mapping[str, Any]) -> dict[str, Any] | None:
    header = row.get("attorneyPartyHeader")
    if not isinstance(header, Mapping):
        header = row.get("partyHeader")
    if not isinstance(header, Mapping):
        return None
    actor = header.get("partyActorInstance")
    if not isinstance(actor, Mapping):
        return None
    raw_name = _text(actor.get("displayName") or actor.get("sortName"))
    if raw_name is None:
        return None
    return {
        "raw_name": raw_name,
        "normalized_name": _text(actor.get("sortName")),
        "native_attorney_id": _text(header.get("casePartyUUID")),
        "bar_id": _text(header.get("barNumber")),
        "firm_name": _text(header.get("firmName")),
        "primary": bool(row.get("primaryFlag")),
        "raw": dict(row),
    }


def _party_record(row: Mapping[str, Any]) -> dict[str, Any]:
    header = row.get("partyHeader")
    if not isinstance(header, Mapping):
        raise ValueError("Oregon appellate party result lacks partyHeader")
    actor = header.get("partyActorInstance")
    if not isinstance(actor, Mapping):
        raise ValueError("Oregon appellate party result lacks party actor")
    name = _required_text(
        actor.get("displayName") or actor.get("sortName"),
        "party display name",
    )
    identity, identity_derived = _party_identity(row)
    sequence = _integer(row.get("partyNumber") or row.get("orderBy"))
    if sequence is None:
        sequence = int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16) or 1
    attorneys: list[dict[str, Any]] = []
    representations = row.get("legalRepresentations")
    if isinstance(representations, list):
        for representation in representations:
            if not isinstance(representation, Mapping):
                continue
            normalized = _attorney_record(representation)
            if normalized is not None:
                attorneys.append(normalized)
    return {
        "sequence_no": sequence,
        "role": _text(header.get("partySubType") or header.get("partyType"))
        or "Party",
        "raw_name": name,
        "normalized_name": _text(actor.get("sortName")),
        "source_internal_id": identity,
        "source_identity_derived": identity_derived,
        "status": _text(header.get("partyStatus")),
        "pro_se": bool(row.get("proSeFlag")),
        "access_state": (
            "restricted" if row.get("nonPublicFlag") else "public"
        ),
        "attorneys": attorneys,
        "raw": dict(row),
    }


def _docket_record(row: Mapping[str, Any]) -> dict[str, Any]:
    header = row.get("docketEntryHeader")
    if not isinstance(header, Mapping):
        raise ValueError("Oregon appellate docket result lacks docketEntryHeader")
    identifier = _required_text(
        header.get("docketEntryUUID"),
        "docket entry UUID",
    )
    count = _integer(header.get("documentCount")) or 0
    submitters: list[str] = []
    submitted_by = row.get("submittedBy")
    if isinstance(submitted_by, list):
        for submitter in submitted_by:
            if not isinstance(submitter, Mapping):
                continue
            actor = submitter.get("partyActorInstance")
            if isinstance(actor, Mapping):
                name = _text(actor.get("displayName") or actor.get("sortName"))
                if name:
                    submitters.append(name)
    description = _text(
        header.get("docketEntryDescription")
        or header.get("docketEntryName")
        or header.get("docketEntrySubType")
        or header.get("docketEntryType")
    )
    return {
        "native_entry_id": identifier,
        "backend": "oregon_ctrack",
        "source_namespace_id": f"OR_CTRACK_DOCKET:{identifier}",
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
        "filer_raw": "; ".join(submitters) or None,
        "document_available": None,
        "document_metadata_indicated": count > 0,
        "document_metadata_count": count,
        "secured_document": bool(header.get("securedDocument")),
        "official": bool(header.get("official")),
        "native_status": _text(header.get("docketEntryStatus")),
        "outcome_status": _text(header.get("outcomeStatus")),
        "access_state": (
            "restricted"
            if header.get("securedDocument")
            or header.get("compositeSecurity")
            else "public"
        ),
        "documents": [],
        "raw": dict(row),
    }


def _document_record(
    client: OregonAppellateClient | Any,
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
    court: OregonAppellateCourt | None = None
    if case_header.get("courtID") is not None:
        court = client.court_by_external_id(case_header.get("courtID"))
    case_uuid = _text(case_header.get("caseInstanceUUID"))
    info = row.get("documentInfo")
    if not isinstance(info, Mapping):
        info = {}
    state_uuid = _text(row.get("userDocumentState"))
    state = DOCUMENT_STATES.get(state_uuid or "", "unknown")
    file_retrievable = state_uuid == DOCUMENT_STATE_VIEWABLE
    file_url = None
    if court and case_uuid and file_retrievable:
        file_url = (
            f"{API_ROOT}/courts/{court.resource_uuid}/cms/case/{case_uuid}/"
            f"docketentrydocuments/{identifier}"
        )
    access_state = (
        "public"
        if file_retrievable
        else "restricted"
        if state in {"in_cart", "purchasable"}
        else "unknown"
    )
    return {
        "native_document_id": identifier,
        "backend": "oregon_ctrack",
        "source_namespace_id": f"OR_CTRACK_DOCUMENT:{identifier}",
        "document_link_uuid": identifier,
        "docket_entry_uuid": docket_uuid,
        "docket_entry_native_id": docket_uuid,
        "document_name": _text(row.get("documentName")),
        "document_type": _text(
            info.get("documentType") or row.get("documentName")
        ),
        "filed_date": _date(docket_header.get("filedDate")),
        "metadata_available": True,
        "metadata_source_url": DOCUMENT_ACCESS_URL,
        "file_availability": state,
        "file_retrievable": file_retrievable,
        "source_url": file_url,
        "mime_type": _text(info.get("contentType")),
        "page_count": _integer(info.get("pageCount")),
        "file_size": _integer(info.get("fileSize")),
        "file_extension": _text(info.get("fileExtension")),
        "access_state": access_state,
        "native_access_state": state,
        "source_access_state_uuid": state_uuid,
        "raw": dict(row),
    }


def _attach_documents(
    docket_entries: Sequence[dict[str, Any]],
    documents: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        _text(entry.get("native_entry_id")): entry
        for entry in docket_entries
    }
    unlinked: list[dict[str, Any]] = []
    for document in documents:
        entry_id = _text(document.get("docket_entry_native_id"))
        target = by_id.get(entry_id)
        if target is None:
            clean = dict(document)
            clean.pop("docket_entry_native_id", None)
            unlinked.append(clean)
            continue
        target.setdefault("documents", []).append(document)
    for entry in docket_entries:
        attached = entry.get("documents")
        if not isinstance(attached, list):
            attached = []
            entry["documents"] = attached
        entry["document_available"] = any(
            bool(document.get("file_retrievable"))
            for document in attached
            if isinstance(document, Mapping)
        )
        entry["document_file_state_evaluated"] = True
    return unlinked


def _hearing_record(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = _required_text(
        row.get("hearingUUID")
        or row.get("eventUUID")
        or row.get("resourceID"),
        "hearing UUID",
    )
    return {
        "native_event_id": identifier,
        "event_type": _text(
            row.get("hearingType")
            or row.get("courtSessionType")
            or row.get("eventName")
        )
        or "appellate_hearing",
        "event_date": _text(
            row.get("startDate")
            or row.get("hearingDate")
            or row.get("scheduledDate")
        ),
        "location": _text(row.get("location")),
        "room": _text(row.get("room")),
        "panel": row.get("panel"),
        "assertion_kind": "docket_metadata",
        "raw": dict(row),
    }


def _judgment_record(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = _required_text(
        row.get("judgmentUUID")
        or row.get("judgmentInstanceUUID")
        or row.get("resourceID"),
        "judgment UUID",
    )
    return {
        "native_judgment_id": identifier,
        "judgment_type": _text(
            row.get("judgmentType")
            or row.get("judgmentName")
            or row.get("type")
        ),
        "judgment_date": _date(
            row.get("judgmentDate")
            or row.get("filedDate")
            or row.get("entryDate")
        ),
        "status": _text(row.get("judgmentStatus") or row.get("status")),
        "raw": dict(row),
    }


def _group_record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "group_uuid": _text(
            row.get("groupUUID")
            or row.get("caseGroupUUID")
            or row.get("resourceID")
        ),
        "group_name": _text(row.get("groupName") or row.get("name")),
        "group_type": _text(row.get("groupType") or row.get("type")),
        "raw": dict(row),
    }


def _calendar_record(
    client: OregonAppellateClient | Any,
    row: Mapping[str, Any],
    *,
    schema: str,
    retrieval: Mapping[str, Any],
) -> dict[str, Any]:
    identifier = _required_text(row.get("eventUUID"), "event UUID")
    court = client.court_by_external_id(row.get("courtID"))
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{court.resource_uuid}/event/{identifier}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "calendar_event",
        "backend": "oregon_ctrack",
        "source_namespace_id": f"OR_CTRACK_EVENT:{identifier}",
        "native_event_id": identifier,
        "court": _court_payload(court),
        "event_name": _text(row.get("eventName")),
        "event_type": _text(row.get("courtSessionType")) or "court_session",
        "event_date": _text(row.get("startDate")),
        "location": _text(row.get("location")),
        "room": _text(row.get("room")),
        "panel_flag": bool(row.get("panelFlag")),
        "cases": (
            list(row["cases"]) if isinstance(row.get("cases"), list) else []
        ),
        "source_url": PORTAL_SEARCH,
        "schema_fingerprint": schema,
        "retrieval": dict(retrieval),
        "raw": dict(row),
    }


def _resolve_case(
    client: OregonAppellateClient | Any,
    case_number: str,
    *,
    court: str | None,
    page_size: int,
) -> tuple[OregonAppellateCourt, Mapping[str, Any]] | None:
    selector = _required_text(case_number, "case number").upper()
    fetched = client.search_cases(
        selector,
        field="number",
        match_mode="exact",
        court=court,
        requested_limit=None,
        page_size=page_size,
    )
    unique: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in fetched.records:
        header = _case_header(row)
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
        raise OregonAppellateSelectionError(
            "ambiguous_case_number",
            f"Oregon appellate case number {selector!r} matched multiple courts",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
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
                "hint": "Pass --court with a court UUID, external ID, or name.",
            },
        )
    header = next(iter(unique.values()))
    return client.court_by_external_id(header.get("courtID")), header


def _ceiling_error(
    fetched: SpringFetch,
    *,
    component: str | None = None,
) -> PublicRecordsError:
    details: dict[str, Any] = {
        "reported_total_elements": fetched.total_elements,
        "source_result_limit": SOURCE_RESULT_LIMIT,
    }
    if component:
        details["component"] = component
    return PublicRecordsError(
        code=(
            f"{component}_source_result_ceiling"
            if component
            else "source_result_ceiling"
        ),
        message=(
            "The source reported its 10,000-result search ceiling; narrower "
            "criteria are needed to assess records beyond that native window."
        ),
        category="source_pagination",
        retryable=False,
        details=details,
    )


def _fetch_result(
    query: PublicRecordsQuery,
    fetched: SpringFetch,
    records: Sequence[Mapping[str, Any]],
    *,
    warnings: Sequence[str] = (),
) -> PublicRecordsResult:
    combined = tuple(
        dict.fromkeys((*SOURCE_WARNINGS, *warnings, *fetched.warnings))
    )
    if fetched.source_ceiling:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [_ceiling_error(fetched)],
            records=records,
            next_cursor=fetched.next_cursor,
            warnings=combined,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=fetched.next_cursor,
        warnings=combined,
    )


def _component_http_error(
    component: str,
    error: PublicRecordsHTTPError,
) -> PublicRecordsError:
    source_error = error.to_contract_error()
    return PublicRecordsError(
        code=f"{component}_{source_error.code}",
        message=f"{component} component: {source_error.message}",
        category=source_error.category,
        retryable=source_error.retryable,
        details={"component": component, **dict(source_error.details)},
    )


def _component_normalization_error(
    component: str,
    error: Exception,
) -> PublicRecordsError:
    return PublicRecordsError(
        code=f"{component}_normalization_failed",
        message=f"{component} component: {error}",
        category="source_schema",
        retryable=False,
        details={"component": component},
    )


def _component_state(
    fetched: SpringFetch,
    *,
    returned: int,
) -> dict[str, Any]:
    metadata = _fetch_metadata(fetched)
    metadata.update(
        {
            "status": (
                "partial" if fetched.source_ceiling else "complete"
            ),
            "records_returned": returned,
        }
    )
    return metadata


def _failed_component(error: PublicRecordsError) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "complete": False,
        "records_returned": 0,
        "error": error.to_dict(),
    }


def _load_paginated_component(
    component: str,
    loader: Callable[[], SpringFetch],
    normalizer: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[PublicRecordsError]]:
    try:
        fetched = loader()
        values = [dict(normalizer(row)) for row in fetched.records]
    except PublicRecordsHTTPError as error:
        normalized_error = _component_http_error(component, error)
        return [], _failed_component(normalized_error), [normalized_error]
    except (OregonAppellateSelectionError, TypeError, ValueError) as error:
        normalized_error = _component_normalization_error(component, error)
        return [], _failed_component(normalized_error), [normalized_error]
    errors: list[PublicRecordsError] = []
    if fetched.source_ceiling:
        errors.append(_ceiling_error(fetched, component=component))
    return values, _component_state(
        fetched,
        returned=len(values),
    ), errors


def _load_groups_component(
    loader: Callable[[], Sequence[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[PublicRecordsError]]:
    try:
        values = [_group_record(row) for row in loader()]
    except PublicRecordsHTTPError as error:
        normalized_error = _component_http_error("groups", error)
        return [], _failed_component(normalized_error), [normalized_error]
    except (OregonAppellateSelectionError, TypeError, ValueError) as error:
        normalized_error = _component_normalization_error("groups", error)
        return [], _failed_component(normalized_error), [normalized_error]
    return (
        values,
        {
            "status": "complete",
            "complete": True,
            "records_returned": len(values),
            "pagination": "single_array_response",
        },
        [],
    )


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in (
        "query",
        "case_number",
        "field",
        "match_mode",
        "court",
        "filed_after",
        "filed_before",
        "after",
        "before",
        "docket_entry_uuid",
        "document_uuid",
        "page_size",
    ):
        value = getattr(args, name, None)
        if value is not None:
            values[name] = value
    return values


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Oregon appellate courts",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={
                "adapter_family": "ctrack",
                "pagination": "zero_based_spring_query_bound_anchored_cursor",
                "source_result_limit": SOURCE_RESULT_LIMIT,
            },
        ),
    )


def _decision_status(decision: Mapping[str, Any]) -> ResultStatus:
    disposition = _text(decision.get("automation_disposition"))
    return {
        "human_required": ResultStatus.HUMAN_REQUIRED,
        "restricted": ResultStatus.RESTRICTED,
        "terms_blocked": ResultStatus.TERMS_BLOCKED,
    }.get(disposition or "", ResultStatus.UNAVAILABLE)


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        _decision_status(decision),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Oregon appellate acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: OregonAppellateSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _make_client(
    args: argparse.Namespace,
    decision: Mapping[str, Any] | None,
) -> OregonAppellateClient:
    limits = decision.get("limits") if decision else {}
    if not isinstance(limits, Mapping):
        limits = {}
    interval = max(
        float(getattr(args, "minimum_interval", 0.25)),
        float(limits.get("minimum_interval_seconds") or 0),
    )
    maximum_page_size = min(
        int(limits.get("maximum_page_size") or MAX_PAGE_SIZE),
        MAX_PAGE_SIZE,
    )
    return OregonAppellateClient(
        session=requests.Session(),
        timeout=float(getattr(args, "timeout", 30.0)),
        retry_policy=RetryPolicy(
            max_attempts=int(getattr(args, "max_attempts", 3))
        ),
        minimum_interval=interval,
        maximum_page_size=maximum_page_size,
    )


def _case_detail(
    client: OregonAppellateClient | Any,
    case_number: str,
    *,
    court_selector: str | None,
    page_size: int,
) -> tuple[OregonAppellateCourt, str, Mapping[str, Any]] | None:
    resolved = _resolve_case(
        client,
        case_number,
        court=court_selector,
        page_size=page_size,
    )
    if resolved is None:
        return None
    court, search_header = resolved
    case_uuid = _required_text(
        search_header.get("caseInstanceUUID"),
        "case instance UUID",
    )
    detail = client.get_case(court.resource_uuid, case_uuid)
    return court, case_uuid, _case_header(detail)


def _execute_case_aggregate(
    args: argparse.Namespace,
    client: OregonAppellateClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    page_size = getattr(args, "page_size", 100)
    resolved = _case_detail(
        client,
        getattr(args, "case_number"),
        court_selector=getattr(args, "court", None),
        page_size=page_size,
    )
    if resolved is None:
        return PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    court, case_uuid, header = resolved
    components: dict[str, Any] = {
        "case_detail": {
            "status": "complete",
            "complete": True,
            "records_returned": 1,
        }
    }
    errors: list[PublicRecordsError] = []

    parties, components["parties"], party_errors = _load_paginated_component(
        "parties",
        lambda: client.case_parties(
            court.resource_uuid,
            case_uuid,
            requested_limit=None,
            page_size=page_size,
        ),
        _party_record,
    )
    errors.extend(party_errors)
    docket, components["docket"], docket_errors = _load_paginated_component(
        "docket",
        lambda: client.docket_entries(
            court.resource_uuid,
            case_uuid,
            requested_limit=None,
            page_size=page_size,
        ),
        _docket_record,
    )
    errors.extend(docket_errors)
    hearings, components["hearings"], hearing_errors = (
        _load_paginated_component(
            "hearings",
            lambda: client.case_hearings(
                court.resource_uuid,
                case_uuid,
                requested_limit=None,
                page_size=page_size,
            ),
            _hearing_record,
        )
    )
    errors.extend(hearing_errors)
    judgments, components["judgments"], judgment_errors = (
        _load_paginated_component(
            "judgments",
            lambda: client.case_judgments(
                court.resource_uuid,
                case_uuid,
                requested_limit=None,
                page_size=page_size,
            ),
            _judgment_record,
        )
    )
    errors.extend(judgment_errors)
    groups, components["groups"], group_errors = _load_groups_component(
        lambda: client.case_groups(court.resource_uuid, case_uuid)
    )
    errors.extend(group_errors)
    documents, components["documents"], document_errors = (
        _load_paginated_component(
            "documents",
            lambda: client.case_documents(
                court.resource_uuid,
                case_uuid,
                requested_limit=None,
                page_size=page_size,
            ),
            lambda row: _document_record(client, row),
        )
    )
    errors.extend(document_errors)
    unlinked_documents = _attach_documents(docket, documents)

    detail_schema = schema_fingerprint(inferred_schema([header]))
    record = _case_record(
        client,
        header,
        schema=detail_schema,
        parties=parties,
        docket_entries=docket,
        documents=unlinked_documents,
        case_events=hearings,
        judgments=judgments,
        groups=groups,
        components=components,
    )
    if errors:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            errors,
            records=[record],
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        [record],
        warnings=SOURCE_WARNINGS,
    )


def _execute_command(
    args: argparse.Namespace,
    client: OregonAppellateClient | Any,
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
        retrieval = _fetch_metadata(fetched)
        records = [
            _court_record(
                client._court_from_record(row),
                schema=fetched.schema_fingerprint,
                retrieval=retrieval,
            )
            for row in fetched.records
        ]
        return _fetch_result(query, fetched, records)

    if command == "search-case":
        fetched = client.search_cases(
            getattr(args, "query"),
            field=getattr(args, "field", "auto"),
            match_mode=getattr(args, "match_mode", "contains"),
            court=court_selector,
            filed_after=getattr(args, "filed_after", None),
            filed_before=getattr(args, "filed_before", None),
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
        )
        retrieval = _fetch_metadata(fetched)
        records = [
            _case_record(
                client,
                _case_header(row),
                schema=fetched.schema_fingerprint,
                search_hit=row,
                retrieval=retrieval,
            )
            for row in fetched.records
        ]
        return _fetch_result(query, fetched, records)

    if command == "search-party":
        fetched = client.search_parties(
            getattr(args, "query"),
            match_mode=getattr(args, "match_mode", "match"),
            court=court_selector,
            filed_after=getattr(args, "filed_after", None),
            filed_before=getattr(args, "filed_before", None),
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
        )
        retrieval = _fetch_metadata(fetched)
        records = [
            _case_record(
                client,
                _case_header(row),
                schema=fetched.schema_fingerprint,
                parties=[_party_record(row)],
                search_hit=row,
                retrieval=retrieval,
            )
            for row in fetched.records
        ]
        return _fetch_result(query, fetched, records)

    if command == "case":
        return _execute_case_aggregate(args, client, query)

    if command in {"docket", "parties"}:
        resolved = _case_detail(
            client,
            getattr(args, "case_number"),
            court_selector=court_selector,
            page_size=page_size,
        )
        if resolved is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        court, case_uuid, header = resolved
        if command == "docket":
            fetched = client.docket_entries(
                court.resource_uuid,
                case_uuid,
                requested_limit=limit,
                page_size=page_size,
                cursor=cursor,
            )
            docket = [_docket_record(row) for row in fetched.records]
            parties: list[dict[str, Any]] = []
        else:
            fetched = client.case_parties(
                court.resource_uuid,
                case_uuid,
                requested_limit=limit,
                page_size=page_size,
                cursor=cursor,
            )
            docket = []
            parties = [_party_record(row) for row in fetched.records]
        component_name = command
        components = {
            "case_detail": {
                "status": "complete",
                "complete": True,
                "records_returned": 1,
            },
            component_name: _component_state(
                fetched,
                returned=len(fetched.records),
            ),
        }
        record = _case_record(
            client,
            header,
            schema=schema_fingerprint(inferred_schema([header])),
            parties=parties,
            docket_entries=docket,
            components=components,
            retrieval=_fetch_metadata(fetched),
        )
        return _fetch_result(query, fetched, [record])

    if command == "calendar":
        fetched = client.search_events(
            court=court_selector,
            after=getattr(args, "after", None),
            before=getattr(args, "before", None),
            requested_limit=limit,
            page_size=page_size,
            cursor=cursor,
        )
        retrieval = _fetch_metadata(fetched)
        records = [
            _calendar_record(
                client,
                row,
                schema=fetched.schema_fingerprint,
                retrieval=retrieval,
            )
            for row in fetched.records
        ]
        return _fetch_result(query, fetched, records)

    if command == "document-metadata":
        resolved = _case_detail(
            client,
            getattr(args, "case_number"),
            court_selector=court_selector,
            page_size=page_size,
        )
        if resolved is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        court, case_uuid, header = resolved
        components: dict[str, Any] = {
            "case_detail": {
                "status": "complete",
                "complete": True,
                "records_returned": 1,
            }
        }
        errors: list[PublicRecordsError] = []
        docket, components["docket"], docket_errors = (
            _load_paginated_component(
                "docket",
                lambda: client.docket_entries(
                    court.resource_uuid,
                    case_uuid,
                    requested_limit=None,
                    page_size=page_size,
                ),
                _docket_record,
            )
        )
        errors.extend(docket_errors)
        try:
            fetched = client.case_documents(
                court.resource_uuid,
                case_uuid,
                docket_entry_uuid=getattr(
                    args,
                    "docket_entry_uuid",
                    None,
                ),
                document_uuid=getattr(args, "document_uuid", None),
                requested_limit=limit,
                page_size=page_size,
                cursor=cursor,
            )
            documents = [
                _document_record(client, row) for row in fetched.records
            ]
            components["documents"] = _component_state(
                fetched,
                returned=len(documents),
            )
            if fetched.source_ceiling:
                errors.append(_ceiling_error(fetched, component="documents"))
        except PublicRecordsHTTPError as error:
            component_error = _component_http_error("documents", error)
            errors.append(component_error)
            components["documents"] = _failed_component(component_error)
            fetched = None
            documents = []
        unlinked_documents = _attach_documents(docket, documents)
        record = _case_record(
            client,
            header,
            schema=schema_fingerprint(inferred_schema([header])),
            docket_entries=docket,
            documents=unlinked_documents,
            components=components,
            retrieval=(
                _fetch_metadata(fetched) if fetched is not None else None
            ),
        )
        if errors:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                errors,
                records=[record],
                next_cursor=fetched.next_cursor if fetched else None,
                warnings=tuple(
                    dict.fromkeys(
                        (
                            *SOURCE_WARNINGS,
                            *(fetched.warnings if fetched else ()),
                        )
                    )
                ),
            )
        assert fetched is not None
        return _fetch_result(query, fetched, [record])

    if command == "probe":
        errors: list[PublicRecordsError] = []
        checks: dict[str, Any] = {}

        def check(
            name: str,
            callback: Callable[[], Any],
            summarize: Callable[[Any], Any],
        ) -> Any | None:
            try:
                value = callback()
            except PublicRecordsHTTPError as error:
                normalized = _component_http_error(name, error)
                errors.append(normalized)
                checks[name] = {
                    "status": "unavailable",
                    "error": normalized.to_dict(),
                }
                return None
            except (OregonAppellateSelectionError, TypeError, ValueError) as error:
                normalized = _component_normalization_error(name, error)
                errors.append(normalized)
                checks[name] = {
                    "status": "unavailable",
                    "error": normalized.to_dict(),
                }
                return None
            checks[name] = {
                "status": "ok",
                "result": summarize(value),
            }
            return value

        info = check(
            "manage_info",
            client.info,
            lambda value: {
                "reported_search_results_limit": _integer(
                    (
                        value.get("constants")
                        if isinstance(value.get("constants"), Mapping)
                        else {}
                    ).get("SEARCH_RESULTS_LIMIT")
                )
            },
        )
        check(
            "courts",
            lambda: client.list_courts(requested_limit=2, page_size=2),
            lambda value: {
                "records": len(value.records),
                "total_elements": value.total_elements,
            },
        )
        case_fetch = check(
            "case_search",
            lambda: client.search_cases(
                "A182332",
                field="number",
                match_mode="exact",
                court=COURT_OF_APPEALS_UUID,
                requested_limit=1,
                page_size=1,
            ),
            lambda value: {
                "records": len(value.records),
                "total_elements": value.total_elements,
            },
        )
        court = None
        case_uuid = None
        if case_fetch is not None and case_fetch.records:
            sentinel_header = _case_header(case_fetch.records[0])
            court = client.court_by_external_id(sentinel_header.get("courtID"))
            case_uuid = _text(sentinel_header.get("caseInstanceUUID"))
        if court is not None and case_uuid is not None:
            check(
                "case_detail",
                lambda: client.get_case(court.resource_uuid, case_uuid),
                lambda value: {
                    "case_number": _case_header(value).get("caseNumber")
                },
            )
            for name, callback in (
                (
                    "docket",
                    lambda: client.docket_entries(
                        court.resource_uuid,
                        case_uuid,
                        requested_limit=1,
                        page_size=1,
                    ),
                ),
                (
                    "parties",
                    lambda: client.case_parties(
                        court.resource_uuid,
                        case_uuid,
                        requested_limit=1,
                        page_size=1,
                    ),
                ),
                (
                    "hearings",
                    lambda: client.case_hearings(
                        court.resource_uuid,
                        case_uuid,
                        requested_limit=1,
                        page_size=1,
                    ),
                ),
                (
                    "judgments",
                    lambda: client.case_judgments(
                        court.resource_uuid,
                        case_uuid,
                        requested_limit=1,
                        page_size=1,
                    ),
                ),
                (
                    "documents",
                    lambda: client.case_documents(
                        court.resource_uuid,
                        case_uuid,
                        requested_limit=1,
                        page_size=1,
                    ),
                ),
            ):
                check(
                    name,
                    callback,
                    lambda value: {
                        "records": len(value.records),
                        "total_elements": value.total_elements,
                    },
                )
            check(
                "groups",
                lambda: client.case_groups(court.resource_uuid, case_uuid),
                lambda value: {"records": len(value)},
            )
        check(
            "calendar",
            lambda: client.search_events(
                after="2026-01-01",
                requested_limit=1,
                page_size=1,
            ),
            lambda value: {
                "records": len(value.records),
                "total_elements": value.total_elements,
            },
        )
        record = {
            "canonical_ref": f"ORAPPELLATE_PROBE:{API_ROOT}",
            "source_id": SOURCE_ID,
            "record_kind": "probe",
            "backend": "oregon_ctrack",
            "checks": checks,
            "source_result_limit": (
                _integer(
                    (
                        info.get("constants")
                        if isinstance(info, Mapping)
                        and isinstance(info.get("constants"), Mapping)
                        else {}
                    ).get("SEARCH_RESULTS_LIMIT")
                )
                if info is not None
                else None
            ),
        }
        if errors:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                errors,
                records=[record],
                warnings=SOURCE_WARNINGS,
            )
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )

    raise OregonAppellateSelectionError(
        "unsupported_command",
        f"unsupported Oregon appellate command: {command}",
        category="query_selection",
    )


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    catalog_decision: Mapping[str, Any] | None = None,
    access_decision: Mapping[str, Any] | None = None,
    client: OregonAppellateClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one operation and return the shared public-record envelope."""

    if catalog_decision is not None and access_decision is not None:
        raise ValueError("pass catalog_decision or access_decision, not both")
    decision = (
        catalog_decision
        if catalog_decision is not None
        else access_decision
    )
    query = build_query(args)
    if (
        decision is not None
        and decision.get("source_id") is not None
        and decision.get("source_id") != SOURCE_ID
    ):
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_decision_source_mismatch",
                    message="Catalog decision belongs to another source",
                    category="access",
                    retryable=False,
                    details={
                        "decision_source_id": decision.get("source_id"),
                        "query_source_id": SOURCE_ID,
                    },
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
        if log_results:
            _log(query, None)
        return result
    if decision is not None and not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        if log_results:
            _log(query, None)
        return result

    source_client = client or _make_client(args, decision)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except OregonAppellateSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
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
    finally:
        if owns_client:
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
        _log(query, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Oregon appellate {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Oregon appellate {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("raw_case_number")
            or record.get("event_name")
            or record.get("name")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    parser.add_argument("--max-attempts", type=int, default=3)
    add_output_args(parser)


def _add_paging(
    parser: argparse.ArgumentParser,
    *,
    default_limit: int | None,
    default_page_size: int = 100,
) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        default=default_limit,
        help="Records to return in this envelope; use the cursor to continue",
    )
    parser.add_argument("--page-size", type=int, default=default_page_size)
    parser.add_argument("--cursor")


def _add_query_runtime(
    parser: argparse.ArgumentParser,
    *,
    default_limit: int | None,
    default_page_size: int = 100,
) -> None:
    _add_paging(
        parser,
        default_limit=default_limit,
        default_page_size=default_page_size,
    )
    _add_runtime(parser)


def _add_court_filter(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--court",
        help=(
            "Court UUID, external ID, unique name, 'coa', or 'supreme'"
        ),
    )


def _add_case_date_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--filed-after")
    parser.add_argument("--filed-before")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Oregon's official public appellate record API"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    courts = sub.add_parser("courts", help="List the live appellate courts")
    _add_query_runtime(
        courts,
        default_limit=None,
        default_page_size=MAX_PAGE_SIZE,
    )

    search_case = sub.add_parser(
        "search-case",
        help="Search appellate case numbers or titles",
    )
    search_case.add_argument("query")
    search_case.add_argument(
        "--field",
        choices=("auto", "number", "title"),
        default="auto",
    )
    search_case.add_argument(
        "--match-mode",
        choices=tuple(sorted(CASE_MATCH_MODES)),
        default="contains",
    )
    _add_court_filter(search_case)
    _add_case_date_filters(search_case)
    _add_query_runtime(search_case, default_limit=50)

    search_party = sub.add_parser(
        "search-party",
        help="Search party names across appellate cases",
    )
    search_party.add_argument("query")
    search_party.add_argument(
        "--match-mode",
        choices=tuple(sorted(PARTY_MATCH_MODES)),
        default="match",
    )
    _add_court_filter(search_party)
    _add_case_date_filters(search_party)
    _add_query_runtime(search_party, default_limit=50)

    case = sub.add_parser(
        "case",
        help=(
            "Fetch case detail plus independently reported optional components"
        ),
    )
    case.add_argument("case_number")
    _add_court_filter(case)
    case.add_argument("--page-size", type=int, default=100)
    _add_runtime(case)

    docket = sub.add_parser(
        "docket",
        help="Fetch one case and a resumable docket window",
    )
    docket.add_argument("case_number")
    _add_court_filter(docket)
    _add_query_runtime(docket, default_limit=100)

    parties = sub.add_parser(
        "parties",
        help="Fetch one case and a resumable party window",
    )
    parties.add_argument("case_number")
    _add_court_filter(parties)
    _add_query_runtime(parties, default_limit=100)

    calendar = sub.add_parser(
        "calendar",
        help="Search appellate sessions and calendar events",
    )
    _add_court_filter(calendar)
    calendar.add_argument("--after")
    calendar.add_argument("--before")
    _add_query_runtime(calendar, default_limit=100)

    documents = sub.add_parser(
        "document-metadata",
        help=(
            "Fetch public document metadata and separately reported file state"
        ),
    )
    documents.add_argument("case_number")
    _add_court_filter(documents)
    documents.add_argument("--docket-entry-uuid")
    documents.add_argument("--document-uuid")
    _add_query_runtime(documents, default_limit=100)

    probe = sub.add_parser(
        "probe",
        help="Run bounded sentinels for each verified API component",
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
    if getattr(args, "max_attempts", 0) <= 0:
        parser.error("--max-attempts must be positive")
    for name in ("limit", "page_size"):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
