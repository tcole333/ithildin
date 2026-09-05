#!/usr/bin/env python3
"""Query official Oregon court document collections hosted by CONTENTdm.

The State of Oregon Law Library publishes several court-document collections
through one CONTENTdm API.  This adapter shares transport and pagination code
while retaining a separate source identity and collection alias for every
collection.

Examples:
    uv run python tools/query_oregon_court_documents.py sources --json
    uv run python tools/query_oregon_court_documents.py search A182332 \
        --source us-or-law-library-coa-opinions --field all --json
    uv run python tools/query_oregon_court_documents.py latest \
        --source us-or-law-library-supreme-opinions --limit 10 --json
    uv run python tools/query_oregon_court_documents.py item 42527 \
        --source us-or-law-library-coa-opinions --json
    uv run python tools/query_oregon_court_documents.py download 42527 \
        /tmp/A182332.pdf --source us-or-law-library-coa-opinions
    uv run python tools/query_oregon_court_documents.py probe --all --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, unquote, urlsplit

import requests

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import acquisition_result_status
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
        system_trust_session,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import acquisition_result_status
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
        system_trust_session,
    )


API_ORIGIN = "https://cdm17027.contentdm.oclc.org"
API_BASE_URL = f"{API_ORIGIN}/digital/api"
ADAPTER_FAMILY = "oregon_law_library_contentdm"
CATALOG_SOURCE_ID = "us-or-law-library-court-collections-catalog"
STATE_CODE = "OR"
STATE_GEOID = "41"
MULTNOMAH_COUNTY_FIPS = "41051"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_LIMIT = 100
NATIVE_PAGE_SIZE = 100
CURSOR_VERSION = 1
CURSOR_PREFIX = "or-contentdm:v1:"
FIELD_RE = re.compile(r"^[A-Za-z0-9_]+$")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

WARNINGS = (
    "Each CONTENTdm collection is retained as a distinct source component.",
    "These document collections complement, but do not replace, Oregon case "
    "indexes and registers of actions.",
)


@dataclass(frozen=True)
class CollectionSpec:
    """Verified source identity and collection-native field mapping."""

    source_id: str
    alias: str
    name: str
    source_role: str
    record_kind: str
    date_field: str
    sentinel_item_id: str
    sentinel_query: str
    normalized_fields: tuple[tuple[str, str], ...]
    locality: str | None = None
    county_fips: str | None = None

    @property
    def collection_url(self) -> str:
        return (
            f"{API_ORIGIN}/digital/collection/{self.alias}/search"
        )

    @property
    def search_sort(self) -> str:
        return "relevance"

    @property
    def latest_sort(self) -> str:
        return f"{self.date_field}:desc"


COLLECTIONS: dict[str, CollectionSpec] = {
    "us-or-law-library-supreme-opinions": CollectionSpec(
        source_id="us-or-law-library-supreme-opinions",
        alias="p17027coll3",
        name="Oregon Supreme Court Opinions",
        source_role="official_supreme_court_opinion_collection",
        record_kind="supreme_court_opinion",
        date_field="dated",
        sentinel_item_id="18161",
        sentinel_query="S072132",
        normalized_fields=(
            ("title", "title"),
            ("case_name", "subjec"),
            ("case_number", "relispt"),
            ("document_type", "type"),
            ("document_date", "dated"),
            ("parties", "subjec1"),
            ("author", "judge"),
            ("citation", "cita"),
            ("notes", "descri"),
        ),
    ),
    "us-or-law-library-coa-opinions": CollectionSpec(
        source_id="us-or-law-library-coa-opinions",
        alias="p17027coll5",
        name="Oregon Court of Appeals Opinions",
        source_role="official_court_of_appeals_opinion_collection",
        record_kind="court_of_appeals_opinion",
        date_field="dated",
        sentinel_item_id="42527",
        sentinel_query="A182332",
        normalized_fields=(
            ("title", "title"),
            ("case_name", "subjec"),
            ("case_number", "relispt"),
            ("document_type", "type"),
            ("document_date", "dated"),
            ("parties", "subjec1"),
            ("author", "judge"),
            ("citation", "identia"),
            ("notes", "descri"),
            ("additional_case_numbers", "relhapt"),
        ),
    ),
    "us-or-law-library-tax-court-decisions": CollectionSpec(
        source_id="us-or-law-library-tax-court-decisions",
        alias="p17027coll6",
        name="Oregon Tax Court Decisions",
        source_role="official_tax_court_decision_collection",
        record_kind="tax_court_decision",
        date_field="dated",
        sentinel_item_id="10610",
        sentinel_query="TC-MD 250612G",
        normalized_fields=(
            ("title", "title"),
            ("case_name", "subjec"),
            ("case_number", "relispt"),
            ("document_type", "type"),
            ("document_date", "dated"),
            ("parties", "subjec1"),
            ("author", "judge"),
            ("notes", "descri"),
            ("division", "divisi"),
        ),
    ),
    "us-or-law-library-supreme-briefs": CollectionSpec(
        source_id="us-or-law-library-supreme-briefs",
        alias="p17027coll7",
        name="Oregon Supreme Court Briefs",
        source_role="official_supreme_court_brief_collection",
        record_kind="supreme_court_brief",
        date_field="date",
        sentinel_item_id="29902",
        sentinel_query="S071535",
        normalized_fields=(
            ("title", "title"),
            ("case_name", "subjec"),
            ("case_number", "relispt"),
            ("document_type", "type"),
            ("document_date", "date"),
            ("citation", "cita"),
        ),
    ),
    "us-or-law-library-coa-briefs": CollectionSpec(
        source_id="us-or-law-library-coa-briefs",
        alias="p17027coll8",
        name="Oregon Court of Appeals Briefs",
        source_role="official_court_of_appeals_brief_collection",
        record_kind="court_of_appeals_brief",
        date_field="date",
        sentinel_item_id="124865",
        sentinel_query="A167583",
        normalized_fields=(
            ("title", "title"),
            ("case_name", "subjec"),
            ("case_number", "relispt"),
            ("document_type", "type"),
            ("document_date", "date"),
            ("citation", "cita"),
            ("additional_case_numbers", "relhapt"),
        ),
    ),
    "us-or-law-library-coa-orders-interest": CollectionSpec(
        source_id="us-or-law-library-coa-orders-interest",
        alias="p17027coll17",
        name="Oregon Court of Appeals Orders of Interest",
        source_role="official_court_of_appeals_orders_of_interest_collection",
        record_kind="court_of_appeals_order_of_interest",
        date_field="date",
        sentinel_item_id="25",
        sentinel_query="A185034",
        normalized_fields=(
            ("case_title", "title"),
            ("case_number", "identi"),
            ("case_classification", "subjec"),
            ("document_date", "date"),
            ("disposition", "descri"),
            ("order_type", "creato"),
            ("issued_by", "publis"),
            ("amount_awarded", "contri"),
        ),
    ),
    "us-or-law-library-multnomah-presiding-orders": CollectionSpec(
        source_id="us-or-law-library-multnomah-presiding-orders",
        alias="p17027coll15",
        name="Multnomah County Presiding Judge Orders",
        source_role="official_multnomah_county_presiding_judge_order_collection",
        record_kind="multnomah_presiding_judge_order",
        date_field="date",
        sentinel_item_id="758",
        sentinel_query="26PJO00003",
        normalized_fields=(
            ("order_number", "title"),
            ("county", "publis"),
            ("subject", "subjec"),
            ("description", "descri"),
            ("document_date", "date"),
            ("effective_date", "type"),
            ("related_order", "identi"),
            ("order_type", "source"),
            ("archival_status", "langua"),
        ),
        locality="Multnomah County",
        county_fips=MULTNOMAH_COUNTY_FIPS,
    ),
}


def _source_metadata(spec: CollectionSpec) -> SourceMetadata:
    return SourceMetadata(
        source_id=spec.source_id,
        name=spec.name,
        source_role=spec.source_role,
        base_url=spec.collection_url,
        dataset_id=spec.alias,
        metadata={
            "authority": "Oregon Judicial Department",
            "publisher": "State of Oregon Law Library",
            "operator": "OCLC CONTENTdm",
            "authentication": "none",
            "adapter_family": ADAPTER_FAMILY,
            "collection_alias": spec.alias,
            "native_pagination": "one_based_start_with_total_count",
            "native_page_size": NATIVE_PAGE_SIZE,
        },
    )


SOURCE_METADATA = {
    source_id: _source_metadata(spec)
    for source_id, spec in COLLECTIONS.items()
}
CATALOG_METADATA = SourceMetadata(
    source_id=CATALOG_SOURCE_ID,
    name="Oregon Law Library Court Collections Catalog",
    source_role="official_court_document_collection_catalog",
    base_url=API_BASE_URL,
    dataset_id="oregon-law-library-contentdm-collections",
    metadata={
        "authority": "Oregon Judicial Department",
        "publisher": "State of Oregon Law Library",
        "operator": "OCLC CONTENTdm",
        "authentication": "none",
        "adapter_family": ADAPTER_FAMILY,
        "components": list(COLLECTIONS),
    },
)


class OregonCourtDocumentsError(RuntimeError):
    """Transport, selection, schema, or pagination failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "source",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.retryable = retryable
        self.details = dict(details or {})


class OregonCourtDocumentsSelectionError(OregonCourtDocumentsError):
    """Caller input or a continuation cursor is invalid."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="query_selection",
            details=details,
        )


class OregonCourtDocumentsSourceChangedError(OregonCourtDocumentsError):
    """The live CONTENTdm response no longer matches the verified contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


class OregonCourtDocumentsPaginationError(OregonCourtDocumentsError):
    """Traversal stopped before the frozen result count was exhausted."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.PARTIAL,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status=status,
            category="source_pagination",
            details=details,
        )


@dataclass(frozen=True)
class SearchPage:
    """One verified native CONTENTdm search page."""

    records: tuple[Mapping[str, Any], ...]
    total_results: int
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class SearchBatch:
    """Count-bounded collection with an optional resumable continuation."""

    records: tuple[Mapping[str, Any], ...]
    snapshot_total: int
    pages_fetched: int
    next_cursor: str | None
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: OregonCourtDocumentsError | None = None


@dataclass(frozen=True)
class PDFArtifact:
    """Validated PDF bytes and their source identity."""

    content: bytes
    source_url: str
    media_type: str
    filename: str | None
    sha256: str
    source_id: str
    item_id: str


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _required_text(value: Any, field: str) -> str:
    normalized = _clean_text(value)
    if normalized is None:
        raise OregonCourtDocumentsSourceChangedError(
            "required_field_missing",
            f"Oregon CONTENTdm response lacks {field}",
            details={"field": field},
        )
    return normalized


def _positive_item_id(value: Any, field: str = "item ID") -> str:
    normalized = _required_text(value, field)
    if not normalized.isdigit() or int(normalized) <= 0:
        raise OregonCourtDocumentsSourceChangedError(
            "item_id_changed",
            f"Oregon CONTENTdm {field} is not a positive integer",
            details={"field": field, "value": normalized},
        )
    return normalized


def _required_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise OregonCourtDocumentsSourceChangedError(
            "integer_field_changed",
            f"Oregon CONTENTdm {field} is not an integer",
            details={"field": field, "value": value},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise OregonCourtDocumentsSourceChangedError(
            "integer_field_changed",
            f"Oregon CONTENTdm {field} is not an integer",
            details={"field": field, "value": value},
        ) from error
    if parsed < minimum:
        raise OregonCourtDocumentsSourceChangedError(
            "integer_field_out_of_range",
            f"Oregon CONTENTdm {field} is below {minimum}",
            details={"field": field, "value": parsed, "minimum": minimum},
        )
    return parsed


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OregonCourtDocumentsSourceChangedError(
            "mapping_field_changed",
            f"Oregon CONTENTdm {field} is not an object",
            details={"field": field, "type": type(value).__name__},
        )
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)):
        raise OregonCourtDocumentsSourceChangedError(
            "sequence_field_changed",
            f"Oregon CONTENTdm {field} is not a list",
            details={"field": field, "type": type(value).__name__},
        )
    return value


def _media_type(response: Any) -> str:
    value = str(
        getattr(response, "headers", {}).get(
            "Content-Type",
            getattr(response, "headers", {}).get("content-type", ""),
        )
    )
    return value.split(";", 1)[0].strip().lower()


def _response_url(response: Any, fallback: str) -> str:
    return str(getattr(response, "url", None) or fallback)


def _schema_fingerprint(payload: Mapping[str, Any]) -> str:
    return sha256_fingerprint(payload)


def _spec(source_id: str) -> CollectionSpec:
    try:
        return COLLECTIONS[source_id]
    except KeyError as error:
        raise OregonCourtDocumentsSelectionError(
            "source_unknown",
            f"unknown Oregon court document source: {source_id}",
            details={"source_id": source_id},
        ) from error


def _jurisdiction(spec: CollectionSpec | None = None) -> JurisdictionMetadata:
    if spec is not None and spec.county_fips:
        return JurisdictionMetadata(
            jurisdiction_id="us-or-multnomah",
            name="Multnomah County, Oregon",
            state_code=STATE_CODE,
            county_fips=spec.county_fips,
            locality=spec.locality,
        )
    return JurisdictionMetadata(
        jurisdiction_id=STATE_GEOID,
        name="Oregon",
        state_code=STATE_CODE,
    )


def _absolute_api_uri(value: Any, field: str) -> str:
    advertised = _required_text(value, field)
    parsed = urlsplit(advertised)
    expected_origin = urlsplit(API_ORIGIN)
    if parsed.scheme or parsed.netloc:
        if (
            parsed.scheme != expected_origin.scheme
            or parsed.netloc.lower() != expected_origin.netloc.lower()
        ):
            raise OregonCourtDocumentsSourceChangedError(
                "api_origin_changed",
                "Oregon CONTENTdm advertised a URI on another origin",
                details={"field": field, "advertised_uri": advertised},
            )

    path = parsed.path
    # CONTENTdm advertises downloadUri values beneath `/api`, while this
    # tenant exposes those same routes beneath its `/digital/api` context.
    if path == "/api" or path.startswith("/api/"):
        path = f"/digital{path}"
    elif path == "api" or path.startswith("api/"):
        path = f"/digital/{path}"
    if not path.startswith("/"):
        path = f"/{path}"

    normalized = f"{API_ORIGIN}{path}"
    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"
    return normalized


def _metadata_entries(
    value: Any,
    *,
    field_name: str,
    search_shape: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    by_key: dict[str, Any] = {}
    by_label: dict[str, Any] = {}

    for index, raw in enumerate(_sequence(value, field_name)):
        item = _mapping(raw, f"{field_name}[{index}]")
        key_name = "field" if search_shape else "key"
        key = _required_text(item.get(key_name), f"{field_name}[{index}].{key_name}")
        label = (
            key
            if search_shape
            else _clean_text(item.get("label")) or key
        )
        raw_value = item.get("value")
        normalized_value = (
            _clean_text(raw_value)
            if isinstance(raw_value, str)
            else raw_value
        )
        entry = {
            "field": key,
            "label": label,
            "value": normalized_value,
        }
        entries.append(entry)
        _add_metadata_value(by_key, key, normalized_value)
        _add_metadata_value(by_label, label, normalized_value)
    return entries, by_key, by_label


def _add_metadata_value(
    target: dict[str, Any],
    key: str,
    value: Any,
) -> None:
    if key not in target:
        target[key] = value
        return
    current = target[key]
    if not isinstance(current, list):
        target[key] = [current, value]
    else:
        current.append(value)


def _canonical_document_ref(spec: CollectionSpec, item_id: str) -> str:
    return f"ORCOURT-DOC:{spec.source_id}:{item_id}"


def _canonical_artifact_ref(spec: CollectionSpec, sha256: str) -> str:
    return f"ORCOURT-ARTIFACT:{spec.source_id}:{sha256}"


def _item_api_url(spec: CollectionSpec, item_id: str) -> str:
    return (
        f"{API_BASE_URL}/singleitem/collection/{spec.alias}/id/{item_id}"
    )


def _standard_download_url(spec: CollectionSpec, item_id: str) -> str:
    return (
        f"{API_BASE_URL}/collection/{spec.alias}/id/{item_id}/download"
    )


def _search_url(
    spec: CollectionSpec,
    *,
    query_text: str | None,
    field: str | None,
    sort: str,
    start: int,
    max_records: int,
) -> str:
    parts = [
        API_BASE_URL,
        "search",
        "collection",
        quote(spec.alias, safe=""),
    ]
    if query_text is not None:
        if field is None:
            raise ValueError("field is required for a source-native search")
        parts.extend(
            [
                "field",
                quote(field, safe=""),
                "searchterm",
                quote(query_text, safe=""),
            ]
        )
    parts.extend(
        ["maxRecords", str(max_records), "start", str(start)]
    )
    if sort != "relevance":
        sort_field, separator, direction = sort.partition(":")
        if not separator or direction not in {"asc", "desc"}:
            raise ValueError(f"invalid CONTENTdm sort: {sort}")
        parts.extend(
            [
                "order",
                quote(sort_field, safe=""),
                "ad",
                direction,
            ]
        )
    return "/".join(parts)


def _criteria_payload(
    spec: CollectionSpec,
    *,
    query_text: str | None,
    field: str | None,
    sort: str,
) -> dict[str, Any]:
    return {
        "source_id": spec.source_id,
        "collection_alias": spec.alias,
        "query": query_text,
        "field": field,
        "sort": sort,
    }


def _criteria_fingerprint(
    spec: CollectionSpec,
    *,
    query_text: str | None,
    field: str | None,
    sort: str,
) -> str:
    return hashlib.sha256(
        canonical_json(
            _criteria_payload(
                spec,
                query_text=query_text,
                field=field,
                sort=sort,
            )
        ).encode("utf-8")
    ).hexdigest()


def _encode_cursor(
    spec: CollectionSpec,
    *,
    query_text: str | None,
    field: str | None,
    sort: str,
    next_start: int,
    snapshot_total: int,
    anchor_item_id: str,
) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source_id": spec.source_id,
        "alias": spec.alias,
        "criteria": _criteria_fingerprint(
            spec,
            query_text=query_text,
            field=field,
            sort=sort,
        ),
        "next_start": next_start,
        "snapshot_total": snapshot_total,
        "anchor_item_id": anchor_item_id,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{encoded}"


def _decode_cursor(
    cursor: str | None,
    spec: CollectionSpec,
    *,
    query_text: str | None,
    field: str | None,
    sort: str,
) -> tuple[int, int | None, str | None]:
    if cursor is None:
        return 1, None, None
    if not cursor.startswith(CURSOR_PREFIX):
        raise OregonCourtDocumentsSelectionError(
            "invalid_cursor",
            "cursor must be an Oregon CONTENTdm continuation returned by a "
            "prior query",
        )
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OregonCourtDocumentsSelectionError(
            "invalid_cursor",
            "Oregon CONTENTdm cursor could not be decoded",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("v") != CURSOR_VERSION:
        raise OregonCourtDocumentsSelectionError(
            "invalid_cursor",
            "Oregon CONTENTdm cursor has an unsupported shape or version",
        )
    expected = _criteria_fingerprint(
        spec,
        query_text=query_text,
        field=field,
        sort=sort,
    )
    if (
        payload.get("source_id") != spec.source_id
        or payload.get("alias") != spec.alias
        or payload.get("criteria") != expected
    ):
        raise OregonCourtDocumentsSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to a different Oregon collection query",
            details={
                "cursor_source_id": payload.get("source_id"),
                "query_source_id": spec.source_id,
                "cursor_alias": payload.get("alias"),
                "query_alias": spec.alias,
            },
        )
    next_start = _cursor_int(payload.get("next_start"), "next_start", 1)
    snapshot_total = _cursor_int(
        payload.get("snapshot_total"),
        "snapshot_total",
        0,
    )
    anchor = _clean_text(payload.get("anchor_item_id"))
    if next_start > 1 and anchor is None:
        raise OregonCourtDocumentsSelectionError(
            "invalid_cursor",
            "Oregon CONTENTdm cursor lacks its overlap anchor",
        )
    return next_start, snapshot_total, anchor


def _cursor_int(value: Any, field: str, minimum: int) -> int:
    if isinstance(value, bool):
        raise OregonCourtDocumentsSelectionError(
            "invalid_cursor",
            f"Oregon CONTENTdm cursor {field} is invalid",
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise OregonCourtDocumentsSelectionError(
            "invalid_cursor",
            f"Oregon CONTENTdm cursor {field} is invalid",
        ) from error
    if parsed < minimum:
        raise OregonCourtDocumentsSelectionError(
            "invalid_cursor",
            f"Oregon CONTENTdm cursor {field} is below {minimum}",
        )
    return parsed


def _search_item(
    raw: Any,
    *,
    spec: CollectionSpec,
    total_results: int,
) -> dict[str, Any]:
    item = _mapping(raw, "search item")
    alias = _required_text(
        item.get("collectionAlias"),
        "search item.collectionAlias",
    )
    if alias != spec.alias:
        raise OregonCourtDocumentsSourceChangedError(
            "collection_identity_mismatch",
            "Oregon CONTENTdm search returned a record from another "
            "collection",
            details={"expected_alias": spec.alias, "observed_alias": alias},
        )
    item_id = _positive_item_id(item.get("itemId"), "search item.itemId")
    metadata, metadata_by_key, _metadata_by_label = _metadata_entries(
        item.get("metadataFields", []),
        field_name="search item.metadataFields",
        search_shape=True,
    )
    title = _clean_text(item.get("title")) or _clean_text(
        metadata_by_key.get("title")
    )
    return {
        "record_kind": spec.record_kind,
        "source_id": spec.source_id,
        "component_source_id": spec.source_id,
        "adapter_family": ADAPTER_FAMILY,
        "collection_alias": spec.alias,
        "collection_name": spec.name,
        "canonical_ref": _canonical_document_ref(spec, item_id),
        "item_id": item_id,
        "title": title,
        "source_url": _item_api_url(spec, item_id),
        "download_uri": _standard_download_url(spec, item_id),
        "thumbnail_uri": (
            _absolute_api_uri(
                item.get("thumbnailUri"),
                "search item.thumbnailUri",
            )
            if _clean_text(item.get("thumbnailUri"))
            else None
        ),
        "file_type": _clean_text(item.get("filetype")),
        "metadata_fields": metadata,
        "metadata_by_key": metadata_by_key,
        "source_total_results": total_results,
        "result_scope": "collection_search_index",
        "access_state": "public",
        "certified_record": False,
    }


def parse_search_page(
    payload: Any,
    *,
    spec: CollectionSpec,
    source_url: str,
) -> SearchPage:
    """Validate and normalize one CONTENTdm search response."""

    root = _mapping(payload, "search response")
    total = _required_int(
        root.get("totalResults"),
        "search response.totalResults",
        minimum=0,
    )
    raw_items = _sequence(root.get("items"), "search response.items")
    records = tuple(
        _search_item(item, spec=spec, total_results=total)
        for item in raw_items
    )
    if total == 0 and records:
        raise OregonCourtDocumentsSourceChangedError(
            "search_count_inconsistent",
            "Oregon CONTENTdm returned records with a zero result count",
            details={"record_count": len(records)},
        )
    schema = {
        "root_keys": sorted(str(key) for key in root),
        "item_keys": sorted(
            {
                str(key)
                for raw_item in raw_items
                for key in _mapping(raw_item, "search item")
            }
        ),
        "metadata_field_keys": sorted(
            {
                str(key)
                for raw_item in raw_items
                for raw_field in _sequence(
                    _mapping(raw_item, "search item").get(
                        "metadataFields",
                        [],
                    ),
                    "search item.metadataFields",
                )
                for key in _mapping(
                    raw_field,
                    "search item.metadataFields entry",
                )
            }
        ),
    }
    return SearchPage(
        records=records,
        total_results=total,
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(schema),
    )


def _compound_page_descriptors(
    payload: Mapping[str, Any],
    *,
    spec: CollectionSpec,
    item_id: str,
) -> list[dict[str, Any]]:
    object_info = payload.get("objectInfo")
    if object_info is None:
        return []
    info = _mapping(object_info, "item.objectInfo")
    if "page" not in info:
        if _clean_text(info.get("code")) == "-2":
            return []
        return []
    raw_pages = _sequence(info.get("page"), "item.objectInfo.page")
    pages: list[dict[str, Any]] = []
    for index, raw_page in enumerate(raw_pages, start=1):
        page = _mapping(raw_page, f"item.objectInfo.page[{index - 1}]")
        page_id = _positive_item_id(
            page.get("pageptr"),
            f"item.objectInfo.page[{index - 1}].pageptr",
        )
        pages.append(
            {
                "page_order": index,
                "page_id": page_id,
                "title": _clean_text(page.get("pagetitle")),
                "file_name": _clean_text(page.get("pagefile")),
                "source_url": _item_api_url(spec, page_id),
                "parent_item_id": item_id,
            }
        )
    return pages


def _normalized_source_fields(
    spec: CollectionSpec,
    metadata_by_key: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        normalized_name: metadata_by_key.get(native_key)
        for normalized_name, native_key in spec.normalized_fields
    }


def normalize_item(
    payload: Any,
    *,
    spec: CollectionSpec,
    item_id: str,
    source_url: str,
    compound_pages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize one item while preserving native metadata and full text."""

    root = _mapping(payload, "item response")
    metadata, metadata_by_key, metadata_by_label = _metadata_entries(
        root.get("fields"),
        field_name="item.fields",
    )
    download_uri = _absolute_api_uri(
        root.get("downloadUri"),
        "item.downloadUri",
    )
    expected_fragment = f"/collection/{spec.alias}/id/{item_id}/download"
    if expected_fragment not in urlsplit(download_uri).path:
        raise OregonCourtDocumentsSourceChangedError(
            "download_identity_mismatch",
            "Oregon CONTENTdm item advertised another download identity",
            details={
                "item_id": item_id,
                "collection_alias": spec.alias,
                "download_uri": download_uri,
            },
        )
    descriptors = _compound_page_descriptors(
        root,
        spec=spec,
        item_id=item_id,
    )
    pages = (
        [dict(page) for page in compound_pages]
        if compound_pages is not None
        else descriptors
    )
    page_texts = [
        str(page.get("full_text"))
        for page in pages
        if isinstance(page.get("full_text"), str)
        and str(page.get("full_text"))
    ]
    raw_text = root.get("text")
    item_text = raw_text if isinstance(raw_text, str) and raw_text else None
    full_text = "\n\n".join(page_texts) if page_texts else item_text
    full_text_sha256 = (
        hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        if full_text is not None
        else None
    )
    normalized_fields = _normalized_source_fields(spec, metadata_by_key)
    title = (
        _clean_text(normalized_fields.get("title"))
        or _clean_text(normalized_fields.get("case_title"))
        or _clean_text(normalized_fields.get("order_number"))
    )
    record = {
        "record_kind": spec.record_kind,
        "source_id": spec.source_id,
        "component_source_id": spec.source_id,
        "adapter_family": ADAPTER_FAMILY,
        "collection_alias": spec.alias,
        "collection_name": spec.name,
        "collection_role": spec.source_role,
        "canonical_ref": _canonical_document_ref(spec, item_id),
        "item_id": item_id,
        "title": title,
        "case_number": normalized_fields.get("case_number"),
        "document_date": normalized_fields.get("document_date"),
        "document_type": (
            normalized_fields.get("document_type")
            or normalized_fields.get("order_type")
        ),
        "normalized_metadata": normalized_fields,
        "metadata_fields": metadata,
        "metadata_by_key": metadata_by_key,
        "metadata_by_label": metadata_by_label,
        "source_url": source_url,
        "download_uri": download_uri,
        "filename": _clean_text(root.get("filename")),
        "content_type": _clean_text(root.get("contentType")),
        "has_print_pdf": bool(root.get("hasPrintPDF")),
        "is_compound": bool(descriptors),
        "compound_pages": pages,
        "page_count": len(descriptors),
        "full_text": full_text,
        "full_text_sha256": full_text_sha256,
        "full_text_character_count": (
            len(full_text) if full_text is not None else 0
        ),
        "thumbnail_uri": (
            _absolute_api_uri(
                root.get("thumbnailUri"),
                "item.thumbnailUri",
            )
            if _clean_text(root.get("thumbnailUri"))
            else None
        ),
        "access_state": "public",
        "certified_record": False,
        "schema_fingerprint": _schema_fingerprint(
            {
                "root_keys": sorted(str(key) for key in root),
                "field_keys": sorted(
                    {
                        str(key)
                        for raw_field in _sequence(
                            root.get("fields"),
                            "item.fields",
                        )
                        for key in _mapping(
                            raw_field,
                            "item.fields entry",
                        )
                    }
                ),
                "native_metadata_keys": sorted(metadata_by_key),
                "compound_page_keys": sorted(
                    {
                        str(key)
                        for page in descriptors
                        for key in page
                    }
                ),
            }
        ),
    }
    return record


def normalize_compound_page(
    payload: Any,
    *,
    spec: CollectionSpec,
    parent_item_id: str,
    descriptor: Mapping[str, Any],
    source_url: str,
) -> dict[str, Any]:
    """Normalize page-level metadata and OCR for a compound document."""

    root = _mapping(payload, "compound page response")
    observed_parent = _required_text(
        root.get("parentId"),
        "compound page.parentId",
    )
    if observed_parent != parent_item_id:
        raise OregonCourtDocumentsSourceChangedError(
            "compound_parent_mismatch",
            "Oregon CONTENTdm compound page belongs to another item",
            details={
                "expected_parent": parent_item_id,
                "observed_parent": observed_parent,
                "page_id": descriptor.get("page_id"),
            },
        )
    metadata, metadata_by_key, metadata_by_label = _metadata_entries(
        root.get("fields", []),
        field_name="compound page.fields",
    )
    raw_text = root.get("text")
    full_text = raw_text if isinstance(raw_text, str) and raw_text else None
    page_id = _positive_item_id(
        descriptor.get("page_id"),
        "compound page descriptor.page_id",
    )
    return {
        **dict(descriptor),
        "page_id": page_id,
        "source_url": source_url,
        "download_uri": (
            _absolute_api_uri(
                root.get("downloadUri"),
                "compound page.downloadUri",
            )
            if _clean_text(root.get("downloadUri"))
            else None
        ),
        "filename": _clean_text(root.get("filename"))
        or descriptor.get("file_name"),
        "content_type": _clean_text(root.get("contentType")),
        "metadata_fields": metadata,
        "metadata_by_key": metadata_by_key,
        "metadata_by_label": metadata_by_label,
        "full_text": full_text,
        "full_text_sha256": (
            hashlib.sha256(full_text.encode("utf-8")).hexdigest()
            if full_text is not None
            else None
        ),
        "full_text_character_count": (
            len(full_text) if full_text is not None else 0
        ),
    }


class OregonCourtDocumentsClient:
    """Retrying anonymous client for official Oregon CONTENTdm collections."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        sleeper: Any = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(self, url: str, *, accept: str) -> Any:
        headers = {
            "Accept": accept,
            "User-Agent": self.user_agent,
            "Referer": API_ORIGIN,
        }
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    "GET",
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise OregonCourtDocumentsError(
                    "transport_error",
                    "Oregon CONTENTdm request failed after "
                    f"{attempt} attempts: {error}",
                    category="transport",
                    retryable=True,
                    details={"attempts": attempt, "url": url},
                ) from error

            status_code = int(getattr(response, "status_code", 0))
            if status_code in self.retry_policy.retry_statuses:
                retry_after = _retry_after(response)
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                raise OregonCourtDocumentsError(
                    (
                        "rate_limited"
                        if status_code == 429
                        else "http_status_error"
                    ),
                    f"Oregon CONTENTdm returned HTTP {status_code}",
                    status=(
                        ResultStatus.RATE_LIMITED
                        if status_code == 429
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=(
                        "rate_limit"
                        if status_code == 429
                        else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code, "url": url},
                )
            if status_code in {401, 403}:
                raise OregonCourtDocumentsError(
                    "source_access_failed",
                    f"Oregon CONTENTdm returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code, "url": url},
                )
            if status_code in {404, 410}:
                raise OregonCourtDocumentsSourceChangedError(
                    "source_route_missing",
                    f"Oregon CONTENTdm route returned HTTP {status_code}",
                    details={"status_code": status_code, "url": url},
                )
            if status_code < 200 or status_code >= 300:
                raise OregonCourtDocumentsError(
                    "http_status_error",
                    f"Oregon CONTENTdm returned HTTP {status_code}",
                    category="transport",
                    details={"status_code": status_code, "url": url},
                )
            return response
        raise OregonCourtDocumentsError(
            "transport_error",
            f"Oregon CONTENTdm request failed: {last_error}",
            category="transport",
            retryable=True,
            details={"url": url},
        )

    def _json(self, url: str) -> tuple[Any, str]:
        response = self._request(url, accept="application/json")
        media_type = _media_type(response)
        if media_type and media_type != "application/json":
            raise OregonCourtDocumentsSourceChangedError(
                "json_media_type_changed",
                "Oregon CONTENTdm JSON route returned another media type",
                details={"content_type": media_type, "url": url},
            )
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise OregonCourtDocumentsSourceChangedError(
                "json_response_invalid",
                "Oregon CONTENTdm returned invalid JSON",
                details={"url": url},
            ) from error
        return payload, _response_url(response, url)

    def fetch_search_page(
        self,
        spec: CollectionSpec,
        *,
        query_text: str | None,
        field: str | None,
        sort: str,
        start: int,
        max_records: int = NATIVE_PAGE_SIZE,
    ) -> SearchPage:
        if start <= 0:
            raise ValueError("CONTENTdm start must be positive")
        if max_records <= 1:
            raise ValueError("CONTENTdm max_records must exceed one")
        url = _search_url(
            spec,
            query_text=query_text,
            field=field,
            sort=sort,
            start=start,
            max_records=max_records,
        )
        payload, source_url = self._json(url)
        return parse_search_page(
            payload,
            spec=spec,
            source_url=source_url,
        )

    def search(
        self,
        spec: CollectionSpec,
        *,
        query_text: str | None,
        field: str | None,
        sort: str,
        limit: int | None,
        cursor: str | None = None,
    ) -> SearchBatch:
        next_start, frozen_total, anchor = _decode_cursor(
            cursor,
            spec,
            query_text=query_text,
            field=field,
            sort=sort,
        )
        collected: list[Mapping[str, Any]] = []
        seen_ids: set[str] = set()
        page_signatures: set[tuple[str, ...]] = set()
        pages: list[SearchPage] = []
        incomplete_error: OregonCourtDocumentsError | None = None
        last_anchor = anchor

        while True:
            request_start = (
                max(1, next_start - 1) if last_anchor is not None else next_start
            )
            page = self.fetch_search_page(
                spec,
                query_text=query_text,
                field=field,
                sort=sort,
                start=request_start,
            )
            pages.append(page)
            if frozen_total is None:
                frozen_total = page.total_results
            elif page.total_results != frozen_total:
                incomplete_error = OregonCourtDocumentsPaginationError(
                    "source_count_drift",
                    "Oregon CONTENTdm result count changed during traversal; "
                    "the cursor retained its initial count",
                    details={
                        "snapshot_total": frozen_total,
                        "observed_total": page.total_results,
                        "request_start": request_start,
                    },
                )
                break

            page_ids = tuple(
                _positive_item_id(record.get("item_id"), "record.item_id")
                for record in page.records
            )
            if page_ids in page_signatures:
                incomplete_error = OregonCourtDocumentsPaginationError(
                    "repeated_page",
                    "Oregon CONTENTdm repeated a native result page",
                    details={
                        "request_start": request_start,
                        "item_ids": list(page_ids),
                    },
                )
                break
            page_signatures.add(page_ids)

            if frozen_total == 0:
                if page.records:
                    incomplete_error = OregonCourtDocumentsPaginationError(
                        "search_count_inconsistent",
                        "Oregon CONTENTdm returned records beyond its frozen "
                        "zero count",
                    )
                break
            if next_start > frozen_total:
                break
            if not page.records:
                incomplete_error = OregonCourtDocumentsPaginationError(
                    "empty_page_before_count",
                    "Oregon CONTENTdm returned an empty page before its frozen "
                    "result count was reached",
                    details={
                        "next_start": next_start,
                        "snapshot_total": frozen_total,
                    },
                )
                break

            candidates = list(page.records)
            if last_anchor is not None:
                observed_anchor = _positive_item_id(
                    candidates[0].get("item_id"),
                    "overlap item ID",
                )
                if observed_anchor != last_anchor:
                    incomplete_error = (
                        OregonCourtDocumentsPaginationError(
                            "cursor_anchor_changed",
                            "Oregon CONTENTdm results reordered at the "
                            "continuation boundary",
                            status=(
                                ResultStatus.PARTIAL
                                if collected
                                else ResultStatus.SOURCE_CHANGED
                            ),
                            details={
                                "expected_anchor": last_anchor,
                                "observed_anchor": observed_anchor,
                                "request_start": request_start,
                            },
                        )
                    )
                    break
                candidates = candidates[1:]

            if not candidates:
                incomplete_error = OregonCourtDocumentsPaginationError(
                    "pagination_stalled",
                    "Oregon CONTENTdm pagination made no progress before its "
                    "frozen count was reached",
                    details={
                        "next_start": next_start,
                        "snapshot_total": frozen_total,
                        "anchor_item_id": last_anchor,
                    },
                )
                break

            stop = False
            for record in candidates:
                item_id = _positive_item_id(
                    record.get("item_id"),
                    "record.item_id",
                )
                if item_id in seen_ids:
                    incomplete_error = OregonCourtDocumentsPaginationError(
                        "duplicate_item",
                        "Oregon CONTENTdm repeated an item during traversal",
                        details={
                            "item_id": item_id,
                            "request_start": request_start,
                        },
                    )
                    stop = True
                    break
                if next_start > frozen_total:
                    incomplete_error = OregonCourtDocumentsPaginationError(
                        "rows_beyond_frozen_count",
                        "Oregon CONTENTdm returned rows beyond its frozen "
                        "result count",
                        details={
                            "snapshot_total": frozen_total,
                            "next_start": next_start,
                            "item_id": item_id,
                        },
                    )
                    stop = True
                    break
                seen_ids.add(item_id)
                collected.append(record)
                last_anchor = item_id
                next_start += 1
                if limit is not None and len(collected) >= limit:
                    stop = True
                    break
            if stop:
                break
            if next_start > frozen_total:
                break

        assert frozen_total is not None
        next_cursor = None
        if next_start <= frozen_total and last_anchor is not None:
            next_cursor = _encode_cursor(
                spec,
                query_text=query_text,
                field=field,
                sort=sort,
                next_start=next_start,
                snapshot_total=frozen_total,
                anchor_item_id=last_anchor,
            )
        elif incomplete_error is not None and cursor is not None:
            next_cursor = cursor
        return SearchBatch(
            records=tuple(collected),
            snapshot_total=frozen_total,
            pages_fetched=len(pages),
            next_cursor=next_cursor,
            source_urls=tuple(page.source_url for page in pages),
            schema_fingerprints=tuple(
                page.schema_fingerprint for page in pages
            ),
            incomplete_error=incomplete_error,
        )

    def fetch_item(
        self,
        spec: CollectionSpec,
        item_id: str,
        *,
        include_compound_pages: bool = True,
    ) -> dict[str, Any]:
        item_id = _positive_item_id(item_id)
        requested_url = _item_api_url(spec, item_id)
        payload, source_url = self._json(requested_url)
        root = _mapping(payload, "item response")
        descriptors = _compound_page_descriptors(
            root,
            spec=spec,
            item_id=item_id,
        )
        pages: list[Mapping[str, Any]] | None = None
        if descriptors and include_compound_pages:
            pages = []
            for descriptor in descriptors:
                page_url = str(descriptor["source_url"])
                page_payload, resolved_page_url = self._json(page_url)
                pages.append(
                    normalize_compound_page(
                        page_payload,
                        spec=spec,
                        parent_item_id=item_id,
                        descriptor=descriptor,
                        source_url=resolved_page_url,
                    )
                )
        return normalize_item(
            root,
            spec=spec,
            item_id=item_id,
            source_url=source_url,
            compound_pages=pages,
        )

    def fetch_artifact(
        self,
        spec: CollectionSpec,
        item_id: str,
    ) -> PDFArtifact:
        item = self.fetch_item(
            spec,
            item_id,
            include_compound_pages=False,
        )
        source_url = _required_text(
            item.get("download_uri"),
            "item download URI",
        )
        response = self._request(source_url, accept="application/pdf")
        resolved_url = _response_url(response, source_url)
        media_type = _media_type(response)
        content = bytes(getattr(response, "content", b""))
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise OregonCourtDocumentsSourceChangedError(
                "download_not_pdf",
                "Oregon CONTENTdm download route did not return a PDF",
                details={
                    "content_type": media_type,
                    "magic_hex": content[:8].hex(),
                    "url": resolved_url,
                },
            )
        sha256 = hashlib.sha256(content).hexdigest()
        return PDFArtifact(
            content=content,
            source_url=resolved_url,
            media_type=media_type,
            filename=_download_filename(response, resolved_url),
            sha256=sha256,
            source_id=spec.source_id,
            item_id=_positive_item_id(item_id),
        )

    def probe(self, spec: CollectionSpec) -> dict[str, Any]:
        page = self.fetch_search_page(
            spec,
            query_text=spec.sentinel_query,
            field="all",
            sort=spec.search_sort,
            start=1,
        )
        sentinel = next(
            (
                record
                for record in page.records
                if record.get("item_id") == spec.sentinel_item_id
            ),
            None,
        )
        if sentinel is None:
            raise OregonCourtDocumentsSourceChangedError(
                "sentinel_missing",
                "Oregon CONTENTdm sentinel is missing from its exact "
                "collection search",
                details={
                    "source_id": spec.source_id,
                    "collection_alias": spec.alias,
                    "sentinel_query": spec.sentinel_query,
                    "sentinel_item_id": spec.sentinel_item_id,
                },
            )
        item = self.fetch_item(spec, spec.sentinel_item_id)
        return {
            "record_kind": "source_health_check",
            "source_id": spec.source_id,
            "component_source_id": spec.source_id,
            "adapter_family": ADAPTER_FAMILY,
            "canonical_ref": (
                f"ORCOURT-SOURCE:{spec.source_id}:probe:"
                f"{spec.sentinel_item_id}"
            ),
            "source_url": spec.collection_url,
            "status": "ok",
            "checked_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "collection_alias": spec.alias,
            "sentinel_query": spec.sentinel_query,
            "sentinel_item_id": spec.sentinel_item_id,
            "sentinel_total_results": page.total_results,
            "sentinel_canonical_ref": item["canonical_ref"],
            "metadata_field_count": len(item["metadata_fields"]),
            "full_text_character_count": item[
                "full_text_character_count"
            ],
            "is_compound": item["is_compound"],
            "page_count": item["page_count"],
            "download_uri": item["download_uri"],
            "search_schema_fingerprint": page.schema_fingerprint,
            "item_schema_fingerprint": item["schema_fingerprint"],
            "authentication": "none",
        }


def _retry_after(response: Any) -> float | None:
    raw = getattr(response, "headers", {}).get(
        "Retry-After",
        getattr(response, "headers", {}).get("retry-after"),
    )
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def _download_filename(response: Any, fallback_url: str) -> str | None:
    disposition = str(
        getattr(response, "headers", {}).get(
            "Content-Disposition",
            getattr(response, "headers", {}).get(
                "content-disposition",
                "",
            ),
        )
    )
    match = re.search(
        r"""filename\*?=(?:UTF-8''|")?([^";]+)""",
        disposition,
        flags=re.IGNORECASE,
    )
    if match:
        return unquote(match.group(1).strip())
    return Path(urlsplit(fallback_url).path).name or None


def _catalog_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for spec in COLLECTIONS.values():
        records.append(
            {
                "record_kind": "source_component",
                "source_id": spec.source_id,
                "component_source_id": spec.source_id,
                "adapter_family": ADAPTER_FAMILY,
                "canonical_ref": f"ORCOURT-SOURCE:{spec.source_id}",
                "name": spec.name,
                "source_role": spec.source_role,
                "collection_alias": spec.alias,
                "collection_url": spec.collection_url,
                "api_base_url": API_BASE_URL,
                "date_field": spec.date_field,
                "sentinel_item_id": spec.sentinel_item_id,
                "sentinel_query": spec.sentinel_query,
                "authentication": "none",
                "access_state": "public",
            }
        )
    return records


def _selected_spec(args: argparse.Namespace) -> CollectionSpec | None:
    source_id = getattr(args, "source", None)
    return _spec(source_id) if source_id else None


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    spec = _selected_spec(args)
    source = SOURCE_METADATA[spec.source_id] if spec else CATALOG_METADATA
    if args.command == "search":
        parameters: Mapping[str, Any] = _criteria_payload(
            spec,
            query_text=args.query_text,
            field=args.field,
            sort=spec.search_sort,
        )
    elif args.command == "latest":
        parameters = _criteria_payload(
            spec,
            query_text=None,
            field=None,
            sort=spec.latest_sort,
        )
    elif args.command == "item":
        parameters = {
            "source_id": spec.source_id,
            "collection_alias": spec.alias,
            "item_id": args.item_id,
            "include_compound_pages": True,
        }
    elif args.command == "download":
        parameters = {
            "source_id": spec.source_id,
            "collection_alias": spec.alias,
            "item_id": args.item_id,
            "destination": str(args.destination),
        }
    elif args.command == "probe":
        parameters = {
            "source_id": spec.source_id if spec else None,
            "all": spec is None,
        }
    else:
        parameters = {"components": list(COLLECTIONS)}
    return PublicRecordsQuery(
        source=source,
        jurisdiction=_jurisdiction(spec),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _minimum_interval(
    args: argparse.Namespace,
    catalog_decision: Mapping[str, Any] | None,
) -> float:
    selected = float(args.minimum_interval)
    if not catalog_decision:
        return selected
    limits = catalog_decision.get("limits")
    if not isinstance(limits, Mapping):
        return selected
    value = limits.get("minimum_interval_seconds")
    if value is None:
        return selected
    try:
        return max(selected, float(value))
    except (TypeError, ValueError):
        return selected


def _make_client(
    args: argparse.Namespace,
    catalog_decision: Mapping[str, Any] | None,
) -> OregonCourtDocumentsClient:
    return OregonCourtDocumentsClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=_minimum_interval(args, catalog_decision),
    )


def _public_error(
    error: OregonCourtDocumentsError,
) -> PublicRecordsError:
    return PublicRecordsError(
        code=error.code,
        message=str(error),
        category=error.category,
        retryable=error.retryable,
        details=error.details,
    )


def _batch_result(
    query: PublicRecordsQuery,
    batch: SearchBatch,
) -> PublicRecordsResult:
    if batch.incomplete_error is not None:
        status = batch.incomplete_error.status
        if batch.records and status != ResultStatus.PARTIAL:
            status = ResultStatus.PARTIAL
        return PublicRecordsResult.failure(
            query,
            status,
            [_public_error(batch.incomplete_error)],
            records=list(batch.records),
            next_cursor=batch.next_cursor,
            warnings=WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        list(batch.records),
        next_cursor=batch.next_cursor,
        warnings=WARNINGS,
    )


def _write_artifact(
    artifact: PDFArtifact,
    destination: Path,
    *,
    overwrite: bool,
) -> Path:
    if destination.exists() and not overwrite:
        raise OregonCourtDocumentsSelectionError(
            "destination_exists",
            f"destination exists; pass --overwrite: {destination}",
            details={"destination": str(destination)},
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(artifact.content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return destination.resolve()


def _execute_command(
    args: argparse.Namespace,
    client: OregonCourtDocumentsClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "sources":
        return PublicRecordsResult.success(
            query,
            _catalog_records(),
            warnings=WARNINGS,
        )

    spec = _selected_spec(args)
    if args.command == "search":
        batch = client.search(
            spec,
            query_text=args.query_text,
            field=args.field,
            sort=spec.search_sort,
            limit=args.limit,
            cursor=args.cursor,
        )
        return _batch_result(query, batch)

    if args.command == "latest":
        batch = client.search(
            spec,
            query_text=None,
            field=None,
            sort=spec.latest_sort,
            limit=args.limit,
            cursor=args.cursor,
        )
        return _batch_result(query, batch)

    if args.command == "item":
        record = client.fetch_item(spec, args.item_id)
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=WARNINGS,
        )

    if args.command == "download":
        artifact = client.fetch_artifact(spec, args.item_id)
        destination = _write_artifact(
            artifact,
            Path(args.destination),
            overwrite=args.overwrite,
        )
        receipt = {
            "record_kind": "court_document_pdf_artifact",
            "source_id": spec.source_id,
            "component_source_id": spec.source_id,
            "adapter_family": ADAPTER_FAMILY,
            "collection_alias": spec.alias,
            "canonical_ref": _canonical_artifact_ref(
                spec,
                artifact.sha256,
            ),
            "document_canonical_ref": _canonical_document_ref(
                spec,
                artifact.item_id,
            ),
            "item_id": artifact.item_id,
            "source_url": artifact.source_url,
            "artifact_path": str(destination),
            "filename": artifact.filename,
            "media_type": artifact.media_type,
            "byte_length": len(artifact.content),
            "sha256": artifact.sha256,
            "access_state": "public",
            "certified_record": False,
        }
        return PublicRecordsResult.success(
            query,
            [receipt],
            raw_artifact_refs=[str(destination)],
            warnings=WARNINGS,
        )

    if args.command == "probe":
        specs = [spec] if spec else list(COLLECTIONS.values())
        records: list[Mapping[str, Any]] = []
        errors: list[PublicRecordsError] = []
        failure_statuses: list[ResultStatus] = []
        for selected in specs:
            try:
                records.append(client.probe(selected))
            except OregonCourtDocumentsError as error:
                errors.append(_public_error(error))
                failure_statuses.append(error.status)
        if errors:
            if records:
                status = ResultStatus.PARTIAL
            elif len(set(failure_statuses)) == 1:
                status = failure_statuses[0]
            else:
                status = ResultStatus.UNAVAILABLE
            return PublicRecordsResult.failure(
                query,
                status,
                errors,
                records=records,
                warnings=WARNINGS,
            )
        return PublicRecordsResult.success(
            query,
            records,
            warnings=WARNINGS,
        )

    raise OregonCourtDocumentsSelectionError(
        "unsupported_command",
        f"unsupported Oregon court documents command: {args.command}",
    )


def _catalog_failure(
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
                details=dict(decision),
            )
        ],
        warnings=WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    catalog_decision: Mapping[str, Any] | None = None,
    access_decision: Mapping[str, Any] | None = None,
    client: OregonCourtDocumentsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source-scoped Oregon court document operation."""

    if catalog_decision is not None and access_decision is not None:
        raise ValueError(
            "pass catalog_decision or access_decision, not both"
        )
    decision = (
        catalog_decision
        if catalog_decision is not None
        else access_decision
    )
    query = build_query(args)
    selected = _selected_spec(args)
    expected_decision_source = (
        selected.source_id if selected is not None else query.source.source_id
    )
    if (
        decision is not None
        and decision.get("source_id") is not None
        and decision.get("source_id") != expected_decision_source
    ):
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_decision_source_mismatch",
                    message=(
                        "Catalog decision belongs to another source component"
                    ),
                    category="access",
                    retryable=False,
                    details={
                        "decision_source_id": decision.get("source_id"),
                        "query_source_id": expected_decision_source,
                    },
                )
            ],
            warnings=WARNINGS,
        )
        if log_results:
            _log(query, None)
        return result
    if decision is not None and not decision.get("allowed", False):
        result = _catalog_failure(query, decision)
        if log_results:
            _log(query, None)
        return result

    if args.command == "sources":
        result = _execute_command(args, client, query)
        if log_results:
            _log(query, len(result.records))
        return result

    source_client = client or _make_client(args, decision)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except OregonCourtDocumentsError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [_public_error(error)],
            warnings=WARNINGS,
        )
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_write_failed",
                    message=str(error),
                    category="local_io",
                    retryable=False,
                )
            ],
            warnings=WARNINGS,
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
            warnings=WARNINGS,
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


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            count,
        )
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Oregon court documents {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Oregon court documents {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        print(
            f"  {record.get('source_id') or '?'} | "
            f"{record.get('item_id') or '-'} | "
            f"{record.get('title') or record.get('name') or '?'}"
        )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_cli_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _item_id_arg(value: str) -> str:
    if not value.isdigit() or int(value) <= 0:
        raise argparse.ArgumentTypeError(
            "item ID must be a positive integer"
        )
    return value


def _field_arg(value: str) -> str:
    if not FIELD_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "field must be one CONTENTdm field nickname"
        )
    return value


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between source requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_cli_int,
        default=3,
        help="Maximum attempts for transient source failures",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Oregon Law Library CONTENTdm court collections"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    source_choices = tuple(COLLECTIONS)

    sources = subparsers.add_parser(
        "sources",
        help="List distinct court-document collection components",
    )
    _add_runtime_and_output(sources)

    search = subparsers.add_parser(
        "search",
        help="Search one source-native term in one collection field",
    )
    search.add_argument("query_text")
    search.add_argument(
        "--source",
        choices=source_choices,
        required=True,
    )
    search.add_argument(
        "--field",
        type=_field_arg,
        default="all",
        help="One CONTENTdm field nickname (default: all)",
    )
    search.add_argument(
        "--limit",
        type=_positive_cli_int,
        default=DEFAULT_LIMIT,
    )
    search.add_argument("--cursor")
    _add_runtime_and_output(search)

    latest = subparsers.add_parser(
        "latest",
        help="List a collection in descending source-native date order",
    )
    latest.add_argument(
        "--source",
        choices=source_choices,
        required=True,
    )
    latest.add_argument(
        "--limit",
        type=_positive_cli_int,
        default=DEFAULT_LIMIT,
    )
    latest.add_argument("--cursor")
    _add_runtime_and_output(latest)

    item = subparsers.add_parser(
        "item",
        help="Retrieve structured metadata, full text, and compound pages",
    )
    item.add_argument("item_id", type=_item_id_arg)
    item.add_argument(
        "--source",
        choices=source_choices,
        required=True,
    )
    _add_runtime_and_output(item)

    download = subparsers.add_parser(
        "download",
        help="Atomically download an exact collection item as a PDF",
    )
    download.add_argument("item_id", type=_item_id_arg)
    download.add_argument("destination", type=Path)
    download.add_argument(
        "--source",
        choices=source_choices,
        required=True,
    )
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify exact collection sentinels and response contracts",
    )
    selection = probe.add_mutually_exclusive_group()
    selection.add_argument("--source", choices=source_choices)
    selection.add_argument(
        "--all",
        action="store_true",
        help="Probe every configured collection (default)",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
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
