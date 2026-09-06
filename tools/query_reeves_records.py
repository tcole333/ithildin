#!/usr/bin/env python3
"""Query Reeves County Clerk official property records and page images.

The County Clerk links to a GovOS/Kofile PublicSearch tenant. The public
application exposes an anonymous HTTP bootstrap, a versioned WebSocket search
and detail protocol, and session-signed page images.

Usage:
    uv run python tools/query_reeves_records.py search "THREE RIVERS"
    uv run python tools/query_reeves_records.py search 18-06481 --limit 10
    uv run python tools/query_reeves_records.py document 20798096
    uv run python tools/query_reeves_records.py page 20798096 1 /tmp/page.png
    uv run python tools/query_reeves_records.py probe
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, TypeVar
from urllib.parse import quote

try:
    from tools.kofile_publicsearch import (
        KofileAccessError,
        KofileBootstrap,
        KofileNotFoundError,
        KofilePageImage,
        KofilePublicSearchClient,
        KofilePublicSearchError,
        KofileRateLimitError,
        KofileSearchPage,
        KofileSourceChangedError,
    )
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
    from tools.public_records_http import inferred_schema, schema_fingerprint
    from tools.public_records_store import canonical_property_ref
except ImportError:
    from kofile_publicsearch import (
        KofileAccessError,
        KofileBootstrap,
        KofileNotFoundError,
        KofilePageImage,
        KofilePublicSearchClient,
        KofilePublicSearchError,
        KofileRateLimitError,
        KofileSearchPage,
        KofileSourceChangedError,
    )
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
    from public_records_http import inferred_schema, schema_fingerprint
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-tx-reeves-county-clerk-official-records"
COUNTY_GEOID = "48389"
STATE_CODE = "TX"
DEPARTMENT = "RP"
BASE_URL = "https://reeves.tx.publicsearch.us"
WEBSOCKET_URL = "wss://reeves.tx.publicsearch.us/ws"
RESULTS_URL = f"{BASE_URL}/results"
DETAIL_URL_TEMPLATE = f"{BASE_URL}/doc/{{doc_id}}?department={DEPARTMENT}"
OFFICIAL_LINKING_PAGE = (
    "https://www.reevescounty.org/departments/county-clerk"
)
PROBE_INSTRUMENT_NUMBER = "18-06481"
PROBE_DOCUMENT_ID = 20798096
RECORD_KIND_INSTRUMENT = "recorded_instrument"
CANONICAL_KIND_INSTRUMENT = "instrument"
RECORD_KIND_DOCUMENT_ARTIFACT = "document_artifact"
DEFAULT_SEARCH_PAGE_SIZE = 50
SEARCH_CURSOR_PREFIX = "kofile:v1:"


@dataclass(frozen=True)
class RecorderTenant:
    """County recorder configuration for the shared GovOS/Kofile protocol."""

    key: str
    source_id: str
    name: str
    authority: str
    jurisdiction_name: str
    county_geoid: str
    state_code: str
    department: str
    base_url: str
    official_linking_page: str
    coverage: str
    probe_instrument_number: str
    probe_document_id: int
    departments: tuple[str, ...] = ()
    probe_page_count: int | None = None
    probe_page_sha256: str | None = None

    @property
    def websocket_url(self) -> str:
        scheme = "wss" if self.base_url.startswith("https://") else "ws"
        host = self.base_url.split("://", 1)[-1].rstrip("/")
        return f"{scheme}://{host}/ws"

    @property
    def detail_url_template(self) -> str:
        return (
            f"{self.base_url.rstrip('/')}/doc/{{doc_id}}"
            f"?department={self.department}"
        )

    @property
    def supported_departments(self) -> tuple[str, ...]:
        return self.departments or (self.department,)

    @property
    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=(
                "recorder_instrument_index_detail_and_page_images"
            ),
            base_url=self.base_url,
            dataset_id=self.department,
            metadata={
                "authority": self.authority,
                "operator": "GovOS/Kofile",
                "platform_family": "kofile_neumo_publicsearch_ws",
                "coverage": self.coverage,
                "official_linking_page": self.official_linking_page,
                "tenant_key": self.key,
                "supported_departments": list(self.supported_departments),
            },
        )


REEVES_TENANT = RecorderTenant(
    key="tx-reeves",
    source_id=SOURCE_ID,
    name="Reeves County Clerk Official Records",
    authority="Reeves County Clerk",
    jurisdiction_name="Reeves County, Texas",
    county_geoid=COUNTY_GEOID,
    state_code=STATE_CODE,
    department=DEPARTMENT,
    base_url=BASE_URL,
    official_linking_page=OFFICIAL_LINKING_PAGE,
    coverage="Reeves County, Texas official property records",
    probe_instrument_number=PROBE_INSTRUMENT_NUMBER,
    probe_document_id=PROBE_DOCUMENT_ID,
    probe_page_count=36,
)

SOURCE_METADATA = REEVES_TENANT.source_metadata

SOURCE_WARNINGS = (
    "Recorder rows reflect the Clerk's index; the instrument image contains the complete filing.",
    "Downloaded portal page images are uncertified copies.",
    "Session-signed image URLs are refreshed when needed and omitted from normalized records.",
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_T = TypeVar("_T")


class ReevesSelectionError(ValueError):
    """A caller supplied an incomplete or invalid source selector."""

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


@dataclass(frozen=True)
class SearchCursorState:
    offset: int
    criteria_sha256: str
    source_total_count: int
    response_type: str


class ReevesRecordsClient:
    """Paced, retrying wrapper around the reusable PublicSearch client."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        minimum_interval: float = 0.25,
        max_attempts: int = 3,
        retry_backoff: float = 0.5,
        tenant: RecorderTenant = REEVES_TENANT,
        source_client: KofilePublicSearchClient | Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if minimum_interval < 0:
            raise ValueError("minimum_interval must not be negative")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if retry_backoff < 0:
            raise ValueError("retry_backoff must not be negative")
        self.tenant = tenant
        self.source_client = source_client or KofilePublicSearchClient(
            tenant.base_url,
            websocket_url=tenant.websocket_url,
            timeout=timeout,
        )
        self.minimum_interval = minimum_interval
        self.max_attempts = max_attempts
        self.retry_backoff = retry_backoff
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_started: float | None = None

    def _pace(self) -> None:
        now = self._monotonic()
        if self._last_started is not None:
            remaining = self.minimum_interval - (now - self._last_started)
            if remaining > 0:
                self._sleep(remaining)
                now = self._monotonic()
        self._last_started = now

    def _invoke(self, operation: Callable[[], _T]) -> _T:
        for attempt in range(1, self.max_attempts + 1):
            self._pace()
            try:
                return operation()
            except KofilePublicSearchError as error:
                if not error.retryable or attempt >= self.max_attempts:
                    raise
                self._sleep(self.retry_backoff * (2 ** (attempt - 1)))
        raise AssertionError("retry loop exhausted without returning or raising")

    def bootstrap(self, *, force: bool = False) -> KofileBootstrap:
        return self._invoke(
            lambda: self.source_client.bootstrap(force=force)
        )

    def search(self, **kwargs: Any) -> KofileSearchPage:
        return self._invoke(lambda: self.source_client.search(**kwargs))

    def fetch_document(self, doc_id: int) -> Mapping[str, Any]:
        return self._invoke(lambda: self.source_client.fetch_document(doc_id))

    def fetch_page_image(
        self,
        doc_id: int,
        page_number: int,
    ) -> KofilePageImage:
        return self._invoke(
            lambda: self.source_client.fetch_page_image(
                doc_id,
                page_number,
            )
        )

    @property
    def request_count(self) -> int:
        """Return actual HTTP and WebSocket exchanges made by the client."""

        return int(getattr(self.source_client, "request_count", 0))

    def close(self) -> None:
        self.source_client.close()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _plain_text(value: Any) -> str | None:
    raw = _text(value)
    if raw is None:
        return None
    return html.unescape(_HTML_TAG_RE.sub("", raw)).strip() or None


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Recorder record has invalid {field_name}")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Recorder record lacks numeric {field_name}"
        ) from error
    if result <= 0:
        raise ValueError(f"Recorder record has invalid {field_name}")
    return result


def _optional_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _source_date(
    value: Any,
    field_name: str,
) -> tuple[str | None, str | None]:
    raw = _text(value)
    if raw is None:
        return None, None
    for date_format in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return raw, datetime.strptime(raw, date_format).date().isoformat()
        except ValueError:
            continue
    raise ValueError(
        f"Recorder record has unparseable {field_name} {raw!r}"
    )


def _compact_date(value: str, field_name: str) -> str:
    raw = value.strip()
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as error:
        raise ReevesSelectionError(
            "invalid_date_filter",
            f"{field_name} must be an ISO calendar date",
            details={"field": field_name, "value": value},
        ) from error
    return parsed.strftime("%Y%m%d")


def _search_selection(
    args: argparse.Namespace,
) -> tuple[str | None, str | None]:
    query_text = _plain_text(getattr(args, "query", None))
    date_from = _text(getattr(args, "date_from", None))
    date_to = _text(getattr(args, "date_to", None))
    if bool(date_from) != bool(date_to):
        raise ReevesSelectionError(
            "incomplete_date_range",
            "--date-from and --date-to must be supplied together",
        )
    if query_text is None and date_from is None:
        raise ReevesSelectionError(
            "search_selector_required",
            "search requires text or a complete recorded-date range",
        )
    if date_from and query_text and not getattr(args, "ocr", False):
        raise ReevesSelectionError(
            "date_range_text_requires_ocr",
            "text with a recorded-date range requires --ocr",
        )
    date_range = None
    if date_from and date_to:
        compact_from = _compact_date(date_from, "--date-from")
        compact_to = _compact_date(date_to, "--date-to")
        if compact_from > compact_to:
            raise ReevesSelectionError(
                "invalid_date_range",
                "--date-from must not be later than --date-to",
            )
        date_range = f"{compact_from},{compact_to}"
    return query_text, date_range


def _search_criteria_sha256(
    *,
    tenant: RecorderTenant,
    search_text: str | None,
    search_ocr_text: bool,
    recorded_date_range: str | None,
    workspace_id: str | None,
) -> str:
    criteria = {
        "source_id": tenant.source_id,
        "department": tenant.department,
        "search_text": search_text,
        "search_ocr_text": search_ocr_text,
        "recorded_date_range": recorded_date_range,
        "workspace_id": workspace_id,
    }
    return hashlib.sha256(canonical_json(criteria).encode("utf-8")).hexdigest()


def _encode_search_cursor(state: SearchCursorState) -> str:
    payload = {
        "version": 1,
        "offset": state.offset,
        "criteria_sha256": state.criteria_sha256,
        "source_total_count": state.source_total_count,
        "response_type": state.response_type,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{SEARCH_CURSOR_PREFIX}{encoded}"


def _decode_search_cursor(value: str) -> SearchCursorState:
    if not value.startswith(SEARCH_CURSOR_PREFIX):
        raise ReevesSelectionError(
            "invalid_cursor",
            f"cursor must start with {SEARCH_CURSOR_PREFIX}",
        )
    token = value[len(SEARCH_CURSOR_PREFIX) :]
    try:
        decoded = base64.urlsafe_b64decode(
            token + "=" * (-len(token) % 4)
        ).decode("utf-8")
        payload = json.loads(decoded)
        if not isinstance(payload, Mapping):
            raise TypeError
        if payload.get("version") != 1:
            raise ValueError
        offset = int(payload["offset"])
        source_total_count = int(payload["source_total_count"])
        criteria_sha256 = str(payload["criteria_sha256"])
        response_type = str(payload["response_type"])
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReevesSelectionError(
            "invalid_cursor",
            "cursor is not a valid GovOS search continuation",
        ) from error
    if (
        offset < 0
        or source_total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", criteria_sha256)
        or not response_type
    ):
        raise ReevesSelectionError(
            "invalid_cursor",
            "cursor contains invalid GovOS continuation values",
        )
    return SearchCursorState(
        offset=offset,
        criteria_sha256=criteria_sha256,
        source_total_count=source_total_count,
        response_type=response_type,
    )


def _assert_cursor_snapshot(
    state: SearchCursorState,
    page: KofileSearchPage,
) -> None:
    if (
        page.total_count != state.source_total_count
        or page.response_type != state.response_type
    ):
        raise KofileSourceChangedError(
            "PublicSearch result population changed after the cursor was issued",
            code="search_cursor_snapshot_changed",
            retryable=False,
            details={
                "expected_total_count": state.source_total_count,
                "observed_total_count": page.total_count,
                "expected_response_type": state.response_type,
                "observed_response_type": page.response_type,
            },
        )


def _instrument_number(row: Mapping[str, Any]) -> str:
    for key in ("instrumentNumber", "documentNumber", "docNumber"):
        value = _plain_text(row.get(key))
        if value is not None:
            return value
    raise ValueError("Recorder record lacks instrument number")


def _normalized_native_role(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    aliases = {
        "securedparty": "secured_party",
        "secured_party": "secured_party",
        "financing_statement_debtor": "debtor",
        "financing_statement_secured_party": "secured_party",
    }
    return aliases.get(normalized, normalized or None)


def _parties(
    value: Any,
    *,
    department_code: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("Recorder record lacks a party list")
    parties: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Recorder record party must be an object")
        name = _plain_text(item.get("name"))
        if name is None:
            continue
        native_role = _text(item.get("type"))
        role_key = _normalized_native_role(native_role)
        party_type_code = _text(item.get("partyTypeCode"))
        is_direct = item.get("isDirect")
        if role_key and role_key not in {"direct", "indirect", "party"}:
            role = role_key
        elif department_code == "RP" and party_type_code == "D":
            role = "grantor"
        elif department_code == "RP" and party_type_code == "I":
            role = "grantee"
        elif department_code != "RP" and party_type_code == "D":
            role = "direct_party"
        elif department_code != "RP" and party_type_code == "I":
            role = "indirect_party"
        elif is_direct is True:
            role = "grantor" if department_code == "RP" else "direct_party"
        elif is_direct is False:
            role = "grantee" if department_code == "RP" else "indirect_party"
        else:
            role = role_key or party_type_code or "unknown"
        parties.append(
            {
                "name": name,
                "role": role,
                "native_role": native_role,
                "party_type_code": party_type_code,
                "is_direct": is_direct if isinstance(is_direct, bool) else None,
            }
        )
    parties.sort(
        key=lambda party: (
            str(party["role"]).casefold(),
            str(party["name"]).casefold(),
            str(party.get("party_type_code") or "").casefold(),
        )
    )
    for sequence_no, party in enumerate(parties, start=1):
        party["sequence_no"] = sequence_no
    return parties


def _department_code(
    row: Mapping[str, Any],
    *,
    tenant: RecorderTenant,
) -> str:
    native_department = _text(
        row.get("department", row.get("departmentCode"))
    )
    if native_department is None:
        return tenant.department
    if native_department != tenant.department:
        raise ValueError(
            "Recorder record department does not match the selected "
            f"department: expected {tenant.department}, observed "
            f"{native_department}"
        )
    return native_department


def _qualified_document_id(department_code: str, doc_id: int) -> str:
    return f"{department_code}:{doc_id}"


def _legal_descriptions(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    values = row.get("legals")
    descriptions: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, Mapping):
                continue
            description = _plain_text(
                item.get("description", item.get("lglDesc"))
            )
            if description is None:
                continue
            legal_type = _text(item.get("legalType"))
            identity = (description, legal_type)
            if identity in seen:
                continue
            seen.add(identity)
            descriptions.append(
                {
                    "description": description,
                    "native_type": legal_type,
                }
            )
    if descriptions:
        return descriptions
    fallback = row.get("legalDescription")
    if isinstance(fallback, list):
        for item in fallback:
            description = _plain_text(item)
            if description and (description, None) not in seen:
                seen.add((description, None))
                descriptions.append(
                    {"description": description, "native_type": None}
                )
    return descriptions


def _image_id(row: Mapping[str, Any]) -> int | None:
    direct = _optional_int(row.get("imageId"))
    if direct is not None:
        return direct
    images = row.get("images")
    if isinstance(images, list) and images and isinstance(images[0], Mapping):
        return _optional_int(images[0].get("id"))
    return None


def _sanitized_raw(row: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve native fields without persisting ephemeral signed URLs."""

    sanitized: dict[str, Any] = {}
    for key, value in row.items():
        if key == "urls":
            sanitized["signed_page_url_count"] = (
                len(value) if isinstance(value, list) else None
            )
            continue
        if key == "thumbnails":
            sanitized["signed_thumbnail_url_count"] = (
                len(value) if isinstance(value, list) else None
            )
            continue
        if key == "thumbnail":
            sanitized["signed_thumbnail_available"] = bool(value)
            continue
        sanitized[str(key)] = value
    return sanitized


def _document_artifact(
    *,
    doc_id: int,
    image_id: int | None,
    instrument_type: str | None,
    recorded_date: str | None,
    page_count: int | None,
    access_state: str,
    department_code: str,
    tenant: RecorderTenant = REEVES_TENANT,
) -> dict[str, Any]:
    qualified_doc_id = _qualified_document_id(department_code, doc_id)
    native_document_id = (
        f"{qualified_doc_id}:{image_id}"
        if image_id is not None
        else qualified_doc_id
    )
    return {
        "record_kind": RECORD_KIND_DOCUMENT_ARTIFACT,
        "native_document_id": native_document_id,
        "document_type": instrument_type or "recorded_instrument",
        "filed_date": recorded_date,
        "source_url": tenant.detail_url_template.format(doc_id=doc_id),
        "mime_type": "image/png",
        "page_count": page_count,
        "certification_status": "uncertified",
        "access_state": access_state,
        "source_locator": {
            "department_code": department_code,
            "doc_id": doc_id,
            "image_id": image_id,
        },
    }


def normalize_instrument(
    row: Mapping[str, Any],
    *,
    schema: str,
    search_metadata: Mapping[str, Any] | None = None,
    tenant: RecorderTenant = REEVES_TENANT,
) -> dict[str, Any]:
    """Normalize one Clerk index/detail row as a recorded instrument."""

    doc_id = _positive_int(row.get("id", row.get("docId")), "document ID")
    department_code = _department_code(row, tenant=tenant)
    qualified_document_id = _qualified_document_id(
        department_code,
        doc_id,
    )
    instrument_number = _instrument_number(row)
    rs_id = _text(row.get("rsId"))
    recorded_date_raw, recorded_date = _source_date(
        row.get("recordedDate"),
        "recorded date",
    )
    instrument_date_raw, instrument_date = _source_date(
        row.get("instrumentDate"),
        "instrument date",
    )
    instrument_type_raw = _plain_text(row.get("docType"))
    instrument_type_code = _plain_text(row.get("docTypeCode"))
    if instrument_type_code is None and instrument_type_raw is not None:
        instrument_type_code = instrument_type_raw
        instrument_type_label = None
    else:
        instrument_type_label = instrument_type_raw
    parties = _parties(
        row.get("parties"),
        department_code=department_code,
    )
    grantors = [
        party["name"] for party in parties if party["role"] == "grantor"
    ]
    grantees = [
        party["name"] for party in parties if party["role"] == "grantee"
    ]
    page_count = _optional_int(
        row.get("pageCount", row.get("totalPages"))
    )
    image_id = _image_id(row)
    access_state = "restricted" if row.get("isSecured") is True else "public"
    source_url = tenant.detail_url_template.format(
        doc_id=quote(str(doc_id), safe="")
    )
    record = {
        "canonical_ref": canonical_property_ref(
            tenant.source_id,
            tenant.county_geoid,
            CANONICAL_KIND_INSTRUMENT,
            qualified_document_id,
        ),
        "source_id": tenant.source_id,
        "record_kind": RECORD_KIND_INSTRUMENT,
        "source_representation": (
            "search_index" if search_metadata is not None else "document_detail"
        ),
        "native_document_id": qualified_document_id,
        "source_internal_id": qualified_document_id,
        "doc_id": doc_id,
        "department_code": department_code,
        "rs_id": rs_id,
        "instrument_number": instrument_number,
        "instrument_type": instrument_type_raw,
        "instrument_type_code": instrument_type_code,
        "instrument_type_label": instrument_type_label,
        "recording_date": recorded_date,
        "recording_date_raw": recorded_date_raw,
        "execution_date": instrument_date,
        "execution_date_raw": instrument_date_raw,
        "recorded_time_raw": _text(row.get("recordedTime")),
        "book": _plain_text(row.get("book")),
        "volume": _plain_text(row.get("volume")),
        "page": _plain_text(row.get("page")),
        "book_volume_page": _plain_text(row.get("bookVolumePage")),
        "parties": parties,
        "grantors": grantors,
        "grantees": grantees,
        "legal_descriptions": _legal_descriptions(row),
        "page_count": page_count,
        "image_id": image_id,
        "access_state": access_state,
        "native_access_state": (
            "isSecured:true" if access_state == "restricted" else "isSecured:false"
        ),
        "certified_record": False,
        "source_url": source_url,
        "official_linking_page": tenant.official_linking_page,
        "ocr_excerpt": _text(row.get("ocrText")),
        "documents": [
            _document_artifact(
                doc_id=doc_id,
                image_id=image_id,
                instrument_type=instrument_type_raw,
                recorded_date=recorded_date,
                page_count=page_count,
                access_state=access_state,
                department_code=department_code,
                tenant=tenant,
            )
        ],
        "source_versions": {
            "metadata_version": row.get("metadataVersion"),
            "document_version": row.get("docVersion", row.get("version")),
            "created_at": row.get("createdAt"),
            "updated_at": row.get("updatedAt"),
            "content_modified_at": row.get("contentModifiedAt"),
        },
        "schema_fingerprint": schema,
        "raw": _sanitized_raw(row),
    }
    if search_metadata is not None:
        record["search_metadata"] = dict(search_metadata)
    return record


def _make_client(
    args: argparse.Namespace,
    *,
    tenant: RecorderTenant = REEVES_TENANT,
) -> ReevesRecordsClient:
    return ReevesRecordsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=args.max_attempts,
        retry_backoff=args.retry_backoff,
        tenant=tenant,
    )


def build_query(
    args: argparse.Namespace,
    *,
    tenant: RecorderTenant = REEVES_TENANT,
) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {"department": tenant.department}
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters.update(
            query=getattr(args, "query", None),
            ocr=getattr(args, "ocr", False),
            date_from=getattr(args, "date_from", None),
            date_to=getattr(args, "date_to", None),
            offset=getattr(args, "offset", 0),
        )
        requested_limit = args.limit
        cursor = getattr(args, "cursor", None)
    elif args.command in {"document", "page"}:
        parameters["doc_id"] = args.doc_id
        if args.command == "page":
            parameters.update(
                page_number=args.page_number,
                destination=(
                    str(args.destination) if args.destination else None
                ),
            )
    elif args.command == "probe":
        parameters.update(
            probe_instrument_number=tenant.probe_instrument_number,
            probe_document_id=tenant.probe_document_id,
        )
        requested_limit = 1
    return PublicRecordsQuery(
        source=tenant.source_metadata,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=tenant.county_geoid,
            name=tenant.jurisdiction_name,
            state_code=tenant.state_code,
            county_fips=tenant.county_geoid,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: ReevesSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
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


def _source_failure(
    query: PublicRecordsQuery,
    error: KofilePublicSearchError,
) -> PublicRecordsResult:
    if isinstance(error, KofileAccessError):
        status = ResultStatus.RESTRICTED
        category = "access"
    elif isinstance(error, KofileRateLimitError):
        status = ResultStatus.RATE_LIMITED
        category = "rate_limit"
    elif isinstance(error, KofileSourceChangedError):
        status = ResultStatus.SOURCE_CHANGED
        category = "source_schema"
    else:
        status = ResultStatus.UNAVAILABLE
        category = "transport"
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _normalized_search_page(
    page: KofileSearchPage,
    *,
    tenant: RecorderTenant,
) -> list[dict[str, Any]]:
    observed_schema = schema_fingerprint(inferred_schema(page.records))
    search_metadata = {
        "source_total_count": page.total_count,
        "offset": page.offset,
        "limit": page.limit,
        "statistics": dict(page.statistics),
        "response_type": page.response_type,
    }
    return [
        normalize_instrument(
            row,
            schema=observed_schema,
            search_metadata=search_metadata,
            tenant=tenant,
        )
        for row in page.records
    ]


def _search_result(
    query: PublicRecordsQuery,
    page: KofileSearchPage,
    *,
    criteria_sha256: str,
    cursor_anchor: SearchCursorState | None = None,
    tenant: RecorderTenant = REEVES_TENANT,
) -> PublicRecordsResult:
    records = _normalized_search_page(page, tenant=tenant)
    next_cursor = (
        _encode_search_cursor(
            SearchCursorState(
                offset=page.next_offset,
                criteria_sha256=criteria_sha256,
                source_total_count=(
                    cursor_anchor.source_total_count
                    if cursor_anchor is not None
                    else page.total_count
                ),
                response_type=(
                    cursor_anchor.response_type
                    if cursor_anchor is not None
                    else page.response_type
                ),
            )
        )
        if page.next_offset is not None
        else None
    )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _exhaustive_search_result(
    query: PublicRecordsQuery,
    pages: Sequence[KofileSearchPage],
    *,
    tenant: RecorderTenant = REEVES_TENANT,
) -> PublicRecordsResult:
    records: list[dict[str, Any]] = []
    for page in pages:
        records.extend(_normalized_search_page(page, tenant=tenant))
    return PublicRecordsResult.success(
        query,
        records,
        warnings=SOURCE_WARNINGS,
    )


def _page_record(
    page: KofilePageImage,
    *,
    destination: Path | None,
    tenant: RecorderTenant = REEVES_TENANT,
) -> tuple[dict[str, Any], str | None]:
    observed_schema = schema_fingerprint(inferred_schema([page.document]))
    record = normalize_instrument(
        page.document,
        schema=observed_schema,
        tenant=tenant,
    )
    digest = hashlib.sha256(page.content).hexdigest()
    storage_path = str(destination.resolve()) if destination else None
    image_id = record.get("image_id")
    page_artifact = {
        "record_kind": RECORD_KIND_DOCUMENT_ARTIFACT,
        "native_document_id": (
            f"{record['native_document_id']}:{image_id}:"
            f"page:{page.page_number}"
        ),
        "document_type": "recorded_instrument_page",
        "filed_date": record.get("recording_date"),
        "source_url": record["source_url"],
        "source_locator": {
            "department_code": record["department_code"],
            "doc_id": record["doc_id"],
            "page_number": page.page_number,
        },
        "sha256": digest,
        "mime_type": page.media_type,
        "page_count": 1,
        "storage_path": storage_path,
        "ocr_status": "not_run",
        "certification_status": "uncertified",
        "access_state": "public",
    }
    record["documents"] = [page_artifact]
    record["page_download"] = {
        "page_number": page.page_number,
        "size": len(page.content),
        "sha256": digest,
        "mime_type": page.media_type,
        "etag": page.etag,
        "storage_path": storage_path,
        "signed_url_refreshed": True,
    }
    return record, storage_path


def _execute_command(
    args: argparse.Namespace,
    client: ReevesRecordsClient | Any,
    query: PublicRecordsQuery,
    *,
    tenant: RecorderTenant = REEVES_TENANT,
) -> PublicRecordsResult:
    if args.command == "search":
        search_text, date_range = _search_selection(args)
        criteria_sha256 = _search_criteria_sha256(
            tenant=tenant,
            search_text=search_text,
            search_ocr_text=args.ocr,
            recorded_date_range=date_range,
            workspace_id=args.workspace_id,
        )
        cursor_value = _text(getattr(args, "cursor", None))
        cursor_state = (
            _decode_search_cursor(cursor_value) if cursor_value else None
        )
        if cursor_state is not None and cursor_state.criteria_sha256 != criteria_sha256:
            raise ReevesSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to a different source or search selection",
            )
        if cursor_state is not None and args.offset != 0:
            raise ReevesSelectionError(
                "cursor_offset_conflict",
                "--cursor and a nonzero --offset cannot be combined",
            )
        initial_offset = cursor_state.offset if cursor_state is not None else args.offset
        search_kwargs = {
            "department": tenant.department,
            "search_value": search_text,
            "search_ocr_text": args.ocr,
            "recorded_date_range": date_range,
            "workspace_id": args.workspace_id,
        }
        if args.limit is not None:
            page = client.search(
                **search_kwargs,
                limit=args.limit,
                offset=initial_offset,
            )
            if page.offset != initial_offset:
                raise KofileSourceChangedError(
                    "PublicSearch returned a different offset than requested",
                    code="search_pagination_offset_changed",
                    retryable=False,
                    details={
                        "requested_offset": initial_offset,
                        "observed_offset": page.offset,
                    },
                )
            if cursor_state is not None:
                _assert_cursor_snapshot(cursor_state, page)
            return _search_result(
                query,
                page,
                criteria_sha256=criteria_sha256,
                cursor_anchor=cursor_state,
                tenant=tenant,
            )

        pages: list[KofileSearchPage] = []
        offset = initial_offset
        seen_offsets: set[int] = set()
        cursor_anchor = cursor_state
        while True:
            if offset in seen_offsets:
                raise KofileSourceChangedError(
                    "PublicSearch continuation repeated an offset",
                    code="search_pagination_stalled",
                    retryable=False,
                    details={"offset": offset},
                )
            seen_offsets.add(offset)
            page = client.search(
                **search_kwargs,
                limit=DEFAULT_SEARCH_PAGE_SIZE,
                offset=offset,
            )
            if page.offset != offset:
                raise KofileSourceChangedError(
                    "PublicSearch returned a different offset than requested",
                    code="search_pagination_offset_changed",
                    retryable=False,
                    details={
                        "requested_offset": offset,
                        "observed_offset": page.offset,
                    },
                )
            if cursor_anchor is None:
                cursor_anchor = SearchCursorState(
                    offset=offset,
                    criteria_sha256=criteria_sha256,
                    source_total_count=page.total_count,
                    response_type=page.response_type,
                )
            else:
                _assert_cursor_snapshot(cursor_anchor, page)
            pages.append(page)
            if page.next_offset is None:
                break
            if page.next_offset <= offset:
                raise KofileSourceChangedError(
                    "PublicSearch continuation did not advance",
                    code="search_pagination_stalled",
                    retryable=False,
                    details={
                        "offset": offset,
                        "next_offset": page.next_offset,
                    },
                )
            offset = page.next_offset
        return _exhaustive_search_result(query, pages, tenant=tenant)

    if args.command == "document":
        payload = client.fetch_document(args.doc_id)
        observed_schema = schema_fingerprint(inferred_schema([payload]))
        return PublicRecordsResult.success(
            query,
            [
                normalize_instrument(
                    payload,
                    schema=observed_schema,
                    tenant=tenant,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "page":
        page = client.fetch_page_image(args.doc_id, args.page_number)
        destination = (
            Path(args.destination).expanduser()
            if args.destination is not None
            else None
        )
        if destination is not None:
            if destination.exists() and not args.overwrite:
                raise OSError(
                    f"destination exists; pass --overwrite: {destination}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(page.content)
        record, storage_path = _page_record(
            page,
            destination=destination,
            tenant=tenant,
        )
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[storage_path] if storage_path else (),
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "probe":
        bootstrap = client.bootstrap()
        if bootstrap.tenant_id != tenant.county_geoid:
            raise KofileSourceChangedError(
                f"{tenant.name} returned a different tenant identity",
                code="tenant_identity_changed",
                retryable=False,
                details={
                    "expected_tenant_id": tenant.county_geoid,
                    "observed_tenant_id": bootstrap.tenant_id,
                },
            )
        missing_departments = sorted(
            set(tenant.supported_departments)
            - set(bootstrap.department_codes)
        )
        if missing_departments:
            raise KofileSourceChangedError(
                "PublicSearch tenant no longer exposes all configured "
                "departments",
                code="property_records_department_missing",
                retryable=False,
                details={
                    "expected_departments": list(
                        tenant.supported_departments
                    ),
                    "observed_departments": list(
                        bootstrap.department_codes
                    ),
                    "missing_departments": missing_departments,
                },
            )
        page = client.search(
            department=tenant.department,
            limit=1,
            offset=0,
            search_value=tenant.probe_instrument_number,
            workspace_id=f"ithildin-{tenant.key}-recorder-probe",
        )
        if len(page.records) != 1 or page.total_count != 1:
            raise KofileSourceChangedError(
                f"{tenant.name} probe instrument is no longer uniquely returned",
                code="probe_record_missing",
                retryable=False,
                details={
                    "instrument_number": tenant.probe_instrument_number,
                    "source_total_count": page.total_count,
                },
            )
        search_row = page.records[0]
        search_doc_id = _positive_int(
            search_row.get("id", search_row.get("docId")),
            "probe document ID",
        )
        if (
            search_doc_id != tenant.probe_document_id
            or _instrument_number(search_row)
            != tenant.probe_instrument_number
        ):
            raise KofileSourceChangedError(
                f"{tenant.name} probe search returned a different instrument",
                code="probe_identity_changed",
                retryable=False,
                details={
                    "expected_doc_id": tenant.probe_document_id,
                    "observed_doc_id": search_doc_id,
                    "observed_instrument_number": _instrument_number(search_row),
                },
            )
        payload = client.fetch_document(tenant.probe_document_id)
        observed_schema = schema_fingerprint(inferred_schema([payload]))
        record = normalize_instrument(
            payload,
            schema=observed_schema,
            tenant=tenant,
        )
        if (
            tenant.probe_page_count is not None
            and record.get("page_count") != tenant.probe_page_count
        ):
            raise KofileSourceChangedError(
                f"{tenant.name} probe page count changed",
                code="probe_page_count_changed",
                retryable=False,
                details={
                    "expected_page_count": tenant.probe_page_count,
                    "observed_page_count": record.get("page_count"),
                },
            )
        record["instrument_type_label"] = _plain_text(
            search_row.get("docType")
        )
        record["probe"] = {
            "tenant_id": bootstrap.tenant_id,
            "department_codes": list(bootstrap.department_codes),
            "department_date_ranges": dict(
                bootstrap.department_date_ranges
            ),
            "source_total_count": page.total_count,
            "search_response_type": page.response_type,
            "search_schema_fingerprint": schema_fingerprint(
                inferred_schema(page.records)
            ),
        }
        if tenant.probe_page_sha256 is not None:
            page_image = client.fetch_page_image(
                tenant.probe_document_id,
                1,
            )
            observed_digest = hashlib.sha256(page_image.content).hexdigest()
            if observed_digest != tenant.probe_page_sha256:
                raise KofileSourceChangedError(
                    f"{tenant.name} probe page digest changed",
                    code="probe_page_digest_changed",
                    retryable=False,
                    details={
                        "expected_sha256": tenant.probe_page_sha256,
                        "observed_sha256": observed_digest,
                    },
                )
            record["probe"]["page_1"] = {
                "sha256": observed_digest,
                "size": len(page_image.content),
                "media_type": page_image.media_type,
            }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )

    raise ValueError(f"unsupported recorder command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    client: ReevesRecordsClient | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
    tenant: RecorderTenant = REEVES_TENANT,
) -> PublicRecordsResult:
    """Execute one configured county-recorder operation."""

    del access_decision
    query = build_query(args, tenant=tenant)
    source_client = client or _make_client(args, tenant=tenant)
    owns_client = client is None
    try:
        result = _execute_command(
            args,
            source_client,
            query,
            tenant=tenant,
        )
    except ReevesSelectionError as error:
        result = _selection_failure(query, error)
    except KofileNotFoundError as error:
        if args.command == "probe":
            result = PublicRecordsResult.failure(
                query,
                ResultStatus.SOURCE_CHANGED,
                [
                    PublicRecordsError(
                        code="probe_record_missing",
                        message=str(error),
                        category="source_schema",
                        retryable=False,
                        details=error.details,
                    )
                ],
                warnings=SOURCE_WARNINGS,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
    except KofilePublicSearchError as error:
        result = _source_failure(query, error)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="page_write_failed",
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
    finally:
        if owns_client:
            source_client.close()

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
    log_search(canonical_json(query.to_dict()), tenant.source_id, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Reeves County records {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Reeves County records {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('instrument_number') or '?'} | "
            f"doc {record.get('doc_id') or '?'} | "
            f"{record.get('instrument_type_label') or record.get('instrument_type') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the official Reeves County Clerk property records"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser(
        "search",
        help="Search indexed fields, OCR, or a recorded-date range",
    )
    search.add_argument("query", nargs="?")
    search.add_argument(
        "--ocr",
        action="store_true",
        help="Search document OCR",
    )
    search.add_argument("--date-from", help="Recorded date on/after YYYY-MM-DD")
    search.add_argument("--date-to", help="Recorded date on/before YYYY-MM-DD")
    search.add_argument(
        "--limit",
        type=int,
        help=(
            "Return at most this many records and expose continuation; "
            "omit to follow all source pages"
        ),
    )
    search.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start at a caller-selected native offset",
    )
    search.add_argument(
        "--cursor",
        help="Resume a query-bound continuation returned by a prior search",
    )
    search.add_argument(
        "--workspace-id",
        help="Optional caller-stable source workspace identifier",
    )
    _add_runtime_and_output(search)

    document = sub.add_parser(
        "document",
        help="Fetch exact instrument detail by native document ID",
    )
    document.add_argument("doc_id", type=int)
    _add_runtime_and_output(document)

    page = sub.add_parser(
        "page",
        help="Fetch one caller-selected instrument page image",
    )
    page.add_argument("doc_id", type=int)
    page.add_argument("page_number", type=int)
    page.add_argument("destination", nargs="?")
    page.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(page)

    probe = sub.add_parser(
        "probe",
        help="Run a bounded tenant, search, and detail health check",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be positive")
    if args.retry_backoff < 0:
        parser.error("--retry-backoff must not be negative")
    if (
        getattr(args, "limit", None) is not None
        and args.limit <= 0
    ):
        parser.error("--limit must be positive")
    if getattr(args, "offset", 0) < 0:
        parser.error("--offset must not be negative")
    if getattr(args, "cursor", None) and getattr(args, "offset", 0):
        parser.error("--cursor and a nonzero --offset cannot be combined")
    if getattr(args, "doc_id", 1) <= 0:
        parser.error("doc_id must be positive")
    if getattr(args, "page_number", 1) <= 0:
        parser.error("page_number must be positive")
    try:
        result = execute(args)
    except ReevesSelectionError as error:
        parser.error(str(error))
        return 2
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
