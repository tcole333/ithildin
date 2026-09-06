#!/usr/bin/env python3
"""Query Jackson County, Oregon permit and code-compliance property events.

Jackson County publishes building permits, land-use permits, and code
compliance cases as three official ArcGIS layers.  A native permit can appear
under more than one layer OBJECTID, so this adapter keeps the native event
identity and the published observation identity.

Usage:
    uv run python tools/query_oregon_jackson_property_events.py sources
    uv run python tools/query_oregon_jackson_property_events.py search solar \
        --source us-or-jackson-county-building-permits --field description
    uv run python tools/query_oregon_jackson_property_events.py record \
        439-BLD2025-00123 --source us-or-jackson-county-building-permits
    uv run python tools/query_oregon_jackson_property_events.py map-taxlot \
        37-2W-23DA-2200 --source us-or-jackson-county-building-permits
    uv run python tools/query_oregon_jackson_property_events.py probe --all
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args
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
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args
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
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_GEOID = "41029"
COUNTY_NAME = "Jackson County, Oregon"
PUBLISHER = "Jackson County GIS and Development Services"

BUILDING_SOURCE_ID = "us-or-jackson-county-building-permits"
LAND_USE_SOURCE_ID = "us-or-jackson-county-land-use-permits"
CODE_SOURCE_ID = "us-or-jackson-county-code-compliance"
SOURCE_IDS = (BUILDING_SOURCE_ID, LAND_USE_SOURCE_ID, CODE_SOURCE_ID)

OUTPUT_SCHEMA_VERSION = "oregon-jackson-property-events/1.0"
PROBE_SCHEMA_VERSION = "oregon-jackson-property-events-probe/1.0"
CURSOR_PREFIX = "oregon-jackson-property-events:v1:"
CURSOR_VERSION = 1


@dataclass(frozen=True)
class SearchColumn:
    """One source column and the matching behavior used for it."""

    name: str
    contains: bool = False


@dataclass(frozen=True)
class SourceConfig:
    """Verified ArcGIS component contract."""

    source_id: str
    name: str
    layer_url: str
    layer_id: int
    service_item_id: str
    expected_layer_name: str
    source_role: str
    record_kind: str
    native_id_field: str
    required_fields: tuple[str, ...]
    search_fields: Mapping[str, tuple[SearchColumn, ...]]
    source_time_zone: str
    source_time_respects_daylight_saving: bool
    description_fact: str
    warnings: tuple[str, ...]

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=self.source_role,
            base_url=self.layer_url,
            dataset_id=self.service_item_id,
            metadata={
                "publisher": PUBLISHER,
                "county_name": COUNTY_NAME,
                "county_geoid": COUNTY_GEOID,
                "layer_id": self.layer_id,
                "layer_name": self.expected_layer_name,
                "record_kind": self.record_kind,
                "source_time_reference": {
                    "time_zone": self.source_time_zone,
                    "respects_daylight_saving": (
                        self.source_time_respects_daylight_saving
                    ),
                },
                "description_fact": self.description_fact,
            },
        )


PERMIT_FIELDS = (
    "OBJECTID",
    "PERMITID",
    "CASEKEY",
    "PERMITDESC",
    "ESTCOST",
    "SUBMITDT",
    "APPROVEDT",
    "APPLICANT",
    "CONTRACTOR",
    "FULLADDR",
    "LOCDESC",
    "PERMITTYPE",
    "PERMITSTAT",
    "LASTUPDATE",
    "LASTEDITOR",
    "PERID1",
    "PERID2",
    "PERID3",
    "JURISDICTION",
    "LINK",
    "STATUSCAT",
)

CODE_FIELDS = (
    "OBJECTID",
    "VIOLATIONID",
    "FULLADDR",
    "LOCDESC",
    "VIOLATETYPE",
    "VIOLATEDESC",
    "CODE",
    "VISABLE",
    "SUBMITDT",
    "NAME",
    "STATUS",
    "LASTUPDATE",
    "LASTEDITOR",
    "JURISDICTION",
    "PERID1",
    "PERID2",
    "PERID3",
    "LINK",
)

PERMIT_SEARCH_FIELDS = {
    "native_id": (SearchColumn("PERMITID"),),
    "case": (
        SearchColumn("CASEKEY"),
        SearchColumn("PERID1"),
        SearchColumn("PERID2"),
        SearchColumn("PERID3"),
    ),
    "address": (
        SearchColumn("FULLADDR", contains=True),
        SearchColumn("LOCDESC", contains=True),
    ),
    "person": (
        SearchColumn("APPLICANT", contains=True),
        SearchColumn("CONTRACTOR", contains=True),
    ),
    "map_taxlot": (SearchColumn("LOCDESC"),),
    "status": (
        SearchColumn("PERMITSTAT", contains=True),
        SearchColumn("STATUSCAT", contains=True),
    ),
    "type": (SearchColumn("PERMITTYPE", contains=True),),
    "description": (SearchColumn("PERMITDESC", contains=True),),
}

CODE_SEARCH_FIELDS = {
    "native_id": (SearchColumn("VIOLATIONID"),),
    "case": (
        SearchColumn("PERID1"),
        SearchColumn("PERID2"),
        SearchColumn("PERID3"),
    ),
    "address": (
        SearchColumn("FULLADDR", contains=True),
        SearchColumn("LOCDESC", contains=True),
    ),
    "person": (SearchColumn("NAME", contains=True),),
    "map_taxlot": (SearchColumn("LOCDESC"),),
    "status": (SearchColumn("STATUS", contains=True),),
    "type": (
        SearchColumn("VIOLATETYPE", contains=True),
        SearchColumn("CODE", contains=True),
    ),
    "description": (SearchColumn("VIOLATEDESC", contains=True),),
}

BUILDING = SourceConfig(
    source_id=BUILDING_SOURCE_ID,
    name="Jackson County Building Permits",
    layer_url=(
        "https://jcportal.jacksoncountyor.gov/server/rest/services/"
        "Property/Permits_Building/FeatureServer/1"
    ),
    layer_id=1,
    service_item_id="c27c3173486c4353b4256d07379f569a",
    expected_layer_name="Permits - Building",
    source_role="county_building_permit_property_events",
    record_kind="building_permit_observation",
    native_id_field="PERMITID",
    required_fields=PERMIT_FIELDS,
    search_fields=PERMIT_SEARCH_FIELDS,
    source_time_zone="Pacific Standard Time",
    source_time_respects_daylight_saving=False,
    description_fact=(
        "The layer describes building-permit points created at taxlot "
        "centroids and updated weekly."
    ),
    warnings=(
        "A native permit can have multiple OBJECTID observations; each row "
        "retains its published taxlot-centroid context.",
        "The Accela URL is retained as a separate detail representation.",
    ),
)

LAND_USE = SourceConfig(
    source_id=LAND_USE_SOURCE_ID,
    name="Jackson County Land-Use Permits",
    layer_url=(
        "https://jcportal.jacksoncountyor.gov/server/rest/services/"
        "Property/Permits_LandUse/FeatureServer/0"
    ),
    layer_id=0,
    service_item_id="e64370c726f2460c8711a19522ffcb44",
    expected_layer_name="Permits - Land-Use",
    source_role="county_land_use_permit_property_events",
    record_kind="land_use_permit_observation",
    native_id_field="PERMITID",
    required_fields=PERMIT_FIELDS,
    search_fields=PERMIT_SEARCH_FIELDS,
    source_time_zone="Pacific Standard Time",
    source_time_respects_daylight_saving=False,
    description_fact=(
        "The layer describes planning-permit points from 1980 to present, "
        "created at taxlot centroids and updated weekly."
    ),
    warnings=(
        "A native permit can have multiple OBJECTID observations; each row "
        "retains its published taxlot-centroid context.",
        "The Accela URL is retained as a separate detail representation.",
    ),
)

CODE_COMPLIANCE = SourceConfig(
    source_id=CODE_SOURCE_ID,
    name="Jackson County Code Compliance Cases",
    layer_url=(
        "https://jcportal.jacksoncountyor.gov/server/rest/services/"
        "Property/Permits_CodeCompliance/FeatureServer/2"
    ),
    layer_id=2,
    service_item_id="0fcc9165da494f1d848bb34d082d29b1",
    expected_layer_name="Permits-CodeCompliance",
    source_role="county_code_compliance_property_events",
    record_kind="code_compliance_observation",
    native_id_field="VIOLATIONID",
    required_fields=CODE_FIELDS,
    search_fields=CODE_SEARCH_FIELDS,
    source_time_zone="UTC",
    source_time_respects_daylight_saving=False,
    description_fact=(
        "The layer describes code-compliance points created at taxlot "
        "centroids and updated weekly by SQL query."
    ),
    warnings=(
        "Owner, status, code, and description fields reflect the published "
        "layer observation and may be blank on individual cases.",
        "The Accela URL is retained as a separate detail representation.",
    ),
)

SOURCES = {
    config.source_id: config
    for config in (BUILDING, LAND_USE, CODE_COMPLIANCE)
}

COMPLEMENTARY_SOURCES: dict[str, tuple[dict[str, Any], ...]] = {
    source_id: (
        {
            "kind": "jackson_county_taxlots",
            "name": "Jackson County Taxlots",
            "url": (
                "https://jcportal.jacksoncountyor.gov/server/rest/services/"
                "Property/Taxlots/FeatureServer/2"
            ),
            "relationship": "parcel_identity_owner_value_and_polygon_context",
            "join_evidence": ("published location text", "address", "geometry"),
        },
        {
            "kind": "jackson_county_interactive_map",
            "name": "Jackson County Interactive Map permit views",
            "url": "https://jacksoncountyor.gov/departments/gis/interactive-maps",
            "relationship": "official_map_and_multi_permit_property_context",
            "join_evidence": ("map-taxlot", "site address"),
        },
        {
            "kind": "accela_record_detail",
            "name": "Accela record detail",
            "url_from_field": "LINK",
            "relationship": "record_detail_and_document_representation",
            "join_evidence": (
                "PERID1/PERID2/PERID3",
                "native permit or violation ID",
            ),
            "observed_access": (
                "anonymous_record_detail_verified_2026-07-29"
                if source_id != CODE_SOURCE_ID
                else "linked_av_route_redirected_to_host_signon_2026-07-29"
            ),
            "observed_additional_depth": (
                (
                    "record status",
                    "work location",
                    "applicant and owner",
                    "parcel number",
                    "processing status",
                    "related records",
                    "documents",
                    "inspections",
                    "fees",
                    "conditions",
                )
                if source_id == BUILDING_SOURCE_ID
                else (
                    "record status",
                    "project description",
                    "parcel number",
                    "assessor account",
                    "property attributes",
                    "zoning",
                    "processing status",
                    "related records",
                )
                if source_id == LAND_USE_SOURCE_ID
                else (
                    "structured ArcGIS case fields remain public",
                    "county public-records request remains available",
                )
            ),
        },
        {
            "kind": "jackson_county_public_records_request",
            "name": "Jackson County public records request",
            "url": (
                "https://jacksoncountyor.gov/Document%20Center/Departments/"
                "Counsel/Public%20Records%20Request.pdf"
            ),
            "relationship": "copy_or_data_request_complement",
            "join_evidence": ("native permit or violation ID", "address"),
        },
    )
    for source_id in SOURCE_IDS
}


class SourceSelectionError(ValueError):
    """A source, field, or cursor selection error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
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
class CursorState:
    source_id: str
    criteria_fingerprint: str
    last_object_id: int
    total_count: int
    schema_fingerprint: str


@dataclass(frozen=True)
class EventBatch:
    features: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    schema_fingerprint: str
    metadata: Mapping[str, Any]
    pages_fetched: int
    count_changed_since_cursor: bool
    last_object_id: int | None


class JacksonPropertyEventClient(ArcGISRESTClient):
    """Metadata/count/keyset-page facade over the shared ArcGIS transport."""

    def __init__(
        self,
        config: SourceConfig,
        *,
        page_size: int,
        timeout: float,
        minimum_interval: float,
        retry_attempts: int,
    ) -> None:
        super().__init__(
            config.layer_url,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )
        self.config = config

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned invalid layer metadata",
                url=self.layer_url,
                details={"response": payload},
            )
        return payload

    def fetch_count(self, where: str) -> int:
        payload = self._request_json(
            self.query_url,
            params={
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned an invalid count response",
                url=self.query_url,
                details={"response": payload},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "ArcGIS count response lacks a non-negative integer",
                url=self.query_url,
                details={"count": count},
            )
        return count

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        descending: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        params: dict[str, Any] = {
            "where": where,
            "outFields": "*",
            "returnGeometry": str(return_geometry).lower(),
            "orderByFields": (
                f"OBJECTID {'DESC' if descending else 'ASC'}"
            ),
            "resultRecordCount": record_count,
            "f": "json",
        }
        if return_geometry:
            params["outSR"] = 4326
        payload = self._request_json(self.query_url, params=params)
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned an invalid feature response",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "ArcGIS feature response lacks a valid features array",
                url=self.query_url,
            )
        return tuple(features)


def _source(source_id: str) -> SourceConfig:
    try:
        return SOURCES[source_id]
    except KeyError as error:
        raise SourceSelectionError(
            "unknown_source",
            f"unknown Jackson County property-event source: {source_id}",
            details={"known_sources": sorted(SOURCES)},
        ) from error


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        raise SourceSelectionError("blank_query", "search value must not be blank")
    return text.replace("'", "''")


def _attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "ArcGIS feature lacks an attributes object",
            url="arcgis://feature",
            details={"feature_keys": sorted(str(key) for key in feature)},
        )
    return attributes


def _object_id(feature: Mapping[str, Any]) -> int:
    value = _attributes(feature).get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceSchemaError(
            "ArcGIS feature lacks an integer OBJECTID",
            url="arcgis://feature",
            details={"value": value},
        )
    return value


def _epoch_observation(
    value: Any,
    config: SourceConfig,
) -> dict[str, Any] | None:
    if value is None:
        return None
    observation: dict[str, Any] = {
        "raw": value,
        "source_time_reference": {
            "time_zone": config.source_time_zone,
            "respects_daylight_saving": (
                config.source_time_respects_daylight_saving
            ),
        },
    }
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return observation
        observation["utc_datetime"] = (
            parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
        )
        observation["utc_date"] = parsed.date().isoformat()
    return observation


def _person(name: Any, role: str) -> dict[str, Any] | None:
    cleaned = _clean_text(name)
    if not cleaned:
        return None
    return {
        "raw_name": cleaned,
        "role": role,
        "assertion_type": "published_property_event",
    }


def _candidate_map_taxlot(value: Any) -> dict[str, Any] | None:
    raw = _clean_text(value)
    if not raw:
        return None
    normalized = re.sub(r"[^0-9A-Z]", "", raw.upper())
    return {
        "raw": raw,
        "normalized_candidate": normalized or None,
        "source_field": "LOCDESC",
        "basis": "published_taxlot_centroid_location",
    }


def _where(
    config: SourceConfig,
    *,
    operation: str,
    selector: str,
    search_field: str,
) -> str:
    if operation == "record":
        groups = ("native_id",)
    elif operation == "address":
        groups = ("address",)
    elif operation == "person":
        groups = ("person",)
    elif operation == "map-taxlot":
        groups = ("map_taxlot",)
    elif search_field == "auto":
        groups = tuple(config.search_fields)
    elif search_field in config.search_fields:
        groups = (search_field,)
    else:
        raise SourceSelectionError(
            "unsupported_search_field",
            f"{config.source_id} does not publish a searchable {search_field} field",
            details={"supported_fields": sorted(config.search_fields)},
        )

    value = _sql_text(selector)
    clauses: list[str] = []
    for group in groups:
        columns = config.search_fields.get(group)
        if not columns:
            continue
        for column in columns:
            if column.contains:
                clauses.append(
                    f"UPPER({column.name}) LIKE '%{value.upper()}%'"
                )
            else:
                clauses.append(f"UPPER({column.name}) = '{value.upper()}'")
    if not clauses:
        raise SourceSelectionError(
            "operation_not_supported",
            f"{config.source_id} does not support {operation}",
        )
    return clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"


def _jurisdiction() -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=COUNTY_GEOID,
        name=COUNTY_NAME,
        state_code=STATE_CODE,
        county_fips=COUNTY_GEOID,
        metadata={"state_fips": STATE_FIPS, "publisher": PUBLISHER},
    )


def _build_query(
    config: SourceConfig,
    *,
    operation: str,
    selector: str,
    search_field: str,
    limit: int,
    cursor: str | None,
    geometry: bool,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=config.source_metadata(),
        jurisdiction=_jurisdiction(),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "field": search_field,
                "geometry": geometry,
                "component": config.record_kind,
            },
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "pagination": "query_bound_object_id_keyset",
                "access_decision": dict(access_decision or {}),
            },
        ),
    )


def _metadata_contract(
    config: SourceConfig,
    metadata: Mapping[str, Any],
) -> tuple[str, int]:
    if metadata.get("name") != config.expected_layer_name:
        raise SourceSchemaError(
            "ArcGIS layer name changed",
            url=config.layer_url,
            details={
                "expected": config.expected_layer_name,
                "observed": metadata.get("name"),
            },
        )
    if metadata.get("serviceItemId") != config.service_item_id:
        raise SourceSchemaError(
            "ArcGIS service item identity changed",
            url=config.layer_url,
            details={
                "expected": config.service_item_id,
                "observed": metadata.get("serviceItemId"),
            },
        )
    if metadata.get("id") != config.layer_id:
        raise SourceSchemaError(
            "ArcGIS layer identity changed",
            url=config.layer_url,
            details={
                "expected": config.layer_id,
                "observed": metadata.get("id"),
            },
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "ArcGIS metadata lacks valid field declarations",
            url=config.layer_url,
        )
    declared_names = {
        str(field.get("name"))
        for field in fields
        if field.get("name") is not None
    }
    missing = sorted(set(config.required_fields) - declared_names)
    if missing:
        raise SourceSchemaError(
            "ArcGIS layer is missing required fields",
            url=config.layer_url,
            details={"missing_fields": missing},
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if (
        not isinstance(advanced, Mapping)
        or not advanced.get("supportsOrderBy")
    ):
        raise SourceSchemaError(
            "ArcGIS layer no longer declares ordered queries",
            url=config.layer_url,
        )
    maximum = metadata.get("maxRecordCount")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise SourceSchemaError(
            "ArcGIS metadata lacks a positive maxRecordCount",
            url=config.layer_url,
            details={"maxRecordCount": maximum},
        )
    return schema_fingerprint(arcgis_declared_schema(fields)), maximum


def _criteria_fingerprint(
    config: SourceConfig,
    *,
    operation: str,
    where: str,
    geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": config.source_id,
            "operation": operation,
            "where": where,
            "geometry": geometry,
            "ordering": "OBJECTID ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source": state.source_id,
        "criteria": state.criteria_fingerprint,
        "last_oid": state.last_object_id,
        "total": state.total_count,
        "schema": state.schema_fingerprint,
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(cursor: str | None) -> CursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor does not belong to the Jackson property-event adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(token + padding).decode("utf-8")
        )
        state = CursorState(
            source_id=str(payload["source"]),
            criteria_fingerprint=str(payload["criteria"]),
            last_object_id=int(payload["last_oid"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if (
        payload.get("v") != CURSOR_VERSION
        or state.last_object_id < 0
        or state.total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _keyset_where(where: str, last_object_id: int | None) -> str:
    if last_object_id is None:
        return where
    return f"({where}) AND OBJECTID > {last_object_id}"


def _fetch_batch(
    client: Any,
    config: SourceConfig,
    *,
    operation: str,
    where: str,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
) -> EventBatch:
    metadata = client.fetch_metadata()
    current_schema, server_page_size = _metadata_contract(config, metadata)
    criteria = _criteria_fingerprint(
        config,
        operation=operation,
        where=where,
        geometry=return_geometry,
    )
    cursor_state = _decode_cursor(cursor)
    if cursor_state is not None:
        if (
            cursor_state.source_id != config.source_id
            or cursor_state.criteria_fingerprint != criteria
        ):
            raise SourceSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to different source or query criteria",
            )
        if cursor_state.schema_fingerprint != current_schema:
            raise SourceSelectionError(
                "cursor_schema_changed",
                "source schema changed after the cursor was issued",
                status=ResultStatus.SOURCE_CHANGED,
            )

    total_count = client.fetch_count(where)
    count_changed = (
        cursor_state is not None
        and cursor_state.total_count != total_count
    )
    last_oid = cursor_state.last_object_id if cursor_state else None
    collected: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    pages_fetched = 0
    target = limit + 1
    page_size = min(int(client.page_size), server_page_size)

    while len(collected) < target:
        requested = min(page_size, target - len(collected))
        page = client.fetch_page(
            where=_keyset_where(where, last_oid),
            record_count=requested,
            return_geometry=return_geometry,
        )
        pages_fetched += 1
        if not page:
            break
        for feature in page:
            oid = _object_id(feature)
            if oid in seen or (last_oid is not None and oid <= last_oid):
                raise SourceSchemaError(
                    "ArcGIS keyset query repeated or reordered a feature",
                    url=config.layer_url,
                    details={
                        "object_id": oid,
                        "previous_object_id": last_oid,
                    },
                )
            seen.add(oid)
            last_oid = oid
            collected.append(feature)
        if len(page) < requested:
            break

    has_more = len(collected) > limit
    returned = collected[:limit]
    returned_last_oid = _object_id(returned[-1]) if returned else None
    next_cursor = None
    if has_more and returned_last_oid is not None:
        next_cursor = _encode_cursor(
            CursorState(
                source_id=config.source_id,
                criteria_fingerprint=criteria,
                last_object_id=returned_last_oid,
                total_count=total_count,
                schema_fingerprint=current_schema,
            )
        )
    return EventBatch(
        features=tuple(returned),
        next_cursor=next_cursor,
        total_count=total_count,
        schema_fingerprint=current_schema,
        metadata=dict(metadata),
        pages_fetched=pages_fetched,
        count_changed_since_cursor=count_changed,
        last_object_id=returned_last_oid,
    )


def _normalize_feature(
    config: SourceConfig,
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = _attributes(feature)
    object_id = _object_id(feature)
    native_id = _clean_text(attributes.get(config.native_id_field))
    native_id_basis = "published_native_id"
    if not native_id:
        native_id = str(object_id)
        native_id_basis = "source_object_id_fallback"

    people: list[dict[str, Any]] = []
    if config.source_id == CODE_SOURCE_ID:
        person = _person(attributes.get("NAME"), "published_owner")
        if person:
            people.append(person)
    else:
        for field, role in (
            ("APPLICANT", "applicant"),
            ("CONTRACTOR", "contractor"),
        ):
            person = _person(attributes.get(field), role)
            if person:
                people.append(person)

    detail_url = _clean_text(attributes.get("LINK"))
    record = {
        "canonical_ref": canonical_property_ref(
            config.source_id,
            COUNTY_GEOID,
            config.record_kind,
            f"{native_id}:{object_id}",
        ),
        "source_id": config.source_id,
        "source_url": config.layer_url,
        "record_kind": config.record_kind,
        "snapshot_complete": False,
        "native_event_id": native_id,
        "native_event_id_basis": native_id_basis,
        "source_record_id": str(object_id),
        "object_id": object_id,
        "observation_identity": {
            "native_event_id": native_id,
            "arcgis_object_id": object_id,
            "basis": "native_event_at_published_taxlot_centroid",
        },
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": "Jackson County",
            "county_geoid": COUNTY_GEOID,
            "published_jurisdiction": _clean_text(
                attributes.get("JURISDICTION")
            ),
        },
        "event_type": (
            _clean_text(attributes.get("VIOLATETYPE"))
            if config.source_id == CODE_SOURCE_ID
            else _clean_text(attributes.get("PERMITTYPE"))
        ),
        "description": (
            _clean_text(attributes.get("VIOLATEDESC"))
            if config.source_id == CODE_SOURCE_ID
            else _clean_text(attributes.get("PERMITDESC"))
        ),
        "status": (
            _clean_text(attributes.get("STATUS"))
            if config.source_id == CODE_SOURCE_ID
            else _clean_text(attributes.get("PERMITSTAT"))
        ),
        "status_category": (
            None
            if config.source_id == CODE_SOURCE_ID
            else _clean_text(attributes.get("STATUSCAT"))
        ),
        "people": people,
        "address": {
            "raw": _clean_text(attributes.get("FULLADDR")),
            "country": "US",
        },
        "parcel_join_evidence": {
            "published_location": _candidate_map_taxlot(
                attributes.get("LOCDESC")
            ),
            "published_address": _clean_text(attributes.get("FULLADDR")),
            "geometry_available": isinstance(feature.get("geometry"), Mapping),
        },
        "event_dates": {
            "submitted": _epoch_observation(
                attributes.get("SUBMITDT"), config
            ),
            "approved": _epoch_observation(
                attributes.get("APPROVEDT"), config
            ),
            "last_update": _epoch_observation(
                attributes.get("LASTUPDATE"), config
            ),
        },
        "accela_identifiers": {
            "perid1": _clean_text(attributes.get("PERID1")),
            "perid2": _clean_text(attributes.get("PERID2")),
            "perid3": _clean_text(attributes.get("PERID3")),
            "case_key": _clean_text(attributes.get("CASEKEY")),
        },
        "detail_representations": (
            [
                {
                    "kind": "accela_record_detail",
                    "url": detail_url,
                    "relationship": "linked_detail_representation",
                }
            ]
            if detail_url
            else []
        ),
        "source_lineage": {
            "publisher": PUBLISHER,
            "service_item_id": config.service_item_id,
            "layer_id": config.layer_id,
            "layer_name": config.expected_layer_name,
            "layer_url": config.layer_url,
            "description_fact": config.description_fact,
            "source_crs": "EPSG:6827",
        },
        "response_schema_fingerprint": response_schema_fingerprint,
        "adapter_schema_fingerprint": sha256_fingerprint(
            {
                "normalization_version": 1,
                "source_id": config.source_id,
                "record_kind": config.record_kind,
                "native_id_field": config.native_id_field,
                "required_fields": list(config.required_fields),
            }
        ),
        "raw_attributes": dict(attributes),
    }
    if config.source_id == CODE_SOURCE_ID:
        record["code_compliance"] = {
            "municipal_code": _clean_text(attributes.get("CODE")),
            "visible_raw": _clean_text(attributes.get("VISABLE")),
        }
    else:
        record["permit"] = {
            "estimated_cost": attributes.get("ESTCOST"),
            "currency": "USD",
        }
    if geometry_requested and isinstance(feature.get("geometry"), Mapping):
        record["geometry"] = dict(feature["geometry"])
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = "EPSG:4326"
        record["geometry_lineage"] = {
            "source_crs": "EPSG:6827",
            "requested_output_crs": "EPSG:4326",
            "transformation": "ArcGIS outSR=4326",
        }
    return record


def _client(
    args: argparse.Namespace,
    config: SourceConfig,
) -> JacksonPropertyEventClient:
    return JacksonPropertyEventClient(
        config,
        page_size=args.page_size,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _best_effort_log(
    query: PublicRecordsQuery,
    source_id: str,
    result: PublicRecordsResult,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), source_id, count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _records_result(
    query: PublicRecordsQuery,
    config: SourceConfig,
    batch: EventBatch,
    *,
    geometry_requested: bool,
) -> PublicRecordsResult:
    records = [
        _normalize_feature(
            config,
            feature,
            response_schema_fingerprint=batch.schema_fingerprint,
            geometry_requested=geometry_requested,
        )
        for feature in batch.features
    ]
    retrieval_snapshot = {
        "total_matching_records": batch.total_count,
        "window_returned_records": len(records),
        "continuation_available": batch.next_cursor is not None,
        "pages_fetched": batch.pages_fetched,
        "last_object_id": batch.last_object_id,
        "schema_fingerprint": batch.schema_fingerprint,
        "count_changed_since_cursor": batch.count_changed_since_cursor,
    }
    for record in records:
        record["retrieval_snapshot"] = retrieval_snapshot
    warnings = list(config.warnings)
    if batch.count_changed_since_cursor:
        warnings.append(
            "The matching count changed since the prior cursor; OBJECTID "
            "keyset continuation remained query-bound."
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=warnings,
    )


def _execute_records(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    config = _source(args.source)
    operation = args.command
    search_field = (
        "native_id"
        if operation == "record"
        else "address"
        if operation == "address"
        else "person"
        if operation == "person"
        else "map_taxlot"
        if operation == "map-taxlot"
        else args.field
    )
    query = _build_query(
        config,
        operation=operation,
        selector=args.query,
        search_field=search_field,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry,
        access_decision=access_decision,
    )
    try:
        where = _where(
            config,
            operation=operation,
            selector=args.query,
            search_field=search_field,
        )
        batch = _fetch_batch(
            client or _client(args, config),
            config,
            operation=operation,
            where=where,
            limit=args.limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        result = _records_result(
            query,
            config,
            batch,
            geometry_requested=args.geometry,
        )
    except SourceSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=config.warnings,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=config.warnings)
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
            warnings=config.warnings,
        )
    if log_results:
        _best_effort_log(query, config.source_id, result)
    return result


def _execute_probe(
    args: argparse.Namespace,
    config: SourceConfig,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _build_query(
        config,
        operation="probe",
        selector="1=1",
        search_field="source_contract",
        limit=2,
        cursor=None,
        geometry=False,
        access_decision=access_decision,
    )
    try:
        active_client = client or _client(args, config)
        metadata = active_client.fetch_metadata()
        schema_value, maximum = _metadata_contract(config, metadata)
        total_count = active_client.fetch_count("1=1")
        first_page = active_client.fetch_page(
            where="1=1",
            record_count=1,
            return_geometry=False,
        )
        last_page = active_client.fetch_page(
            where="1=1",
            record_count=1,
            return_geometry=False,
            descending=True,
        )
        first_record = (
            _normalize_feature(
                config,
                first_page[0],
                response_schema_fingerprint=schema_value,
                geometry_requested=False,
            )
            if first_page
            else None
        )
        last_record = (
            _normalize_feature(
                config,
                last_page[0],
                response_schema_fingerprint=schema_value,
                geometry_requested=False,
            )
            if last_page
            else None
        )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": config.source_id,
                    "component_total_count": total_count,
                    "schema_fingerprint": schema_value,
                    "layer_name": metadata.get("name"),
                    "layer_id": metadata.get("id"),
                    "service_item_id": metadata.get("serviceItemId"),
                    "max_record_count": maximum,
                    "source_crs": "EPSG:6827",
                    "geometry_type": metadata.get("geometryType"),
                    "description": metadata.get("description"),
                    "source_time_reference": metadata.get(
                        "dateFieldsTimeReference"
                    ),
                    "first_ordered_observation": first_record,
                    "last_ordered_observation": last_record,
                    "complementary_sources": list(
                        COMPLEMENTARY_SOURCES[config.source_id]
                    ),
                }
            ],
            warnings=config.warnings,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=config.warnings)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="probe_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=config.warnings,
        )
    if log_results:
        _best_effort_log(query, config.source_id, result)
    return result


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "platform_family": "jackson_county_arcgis_property_events",
        "sources": [
            {
                **config.source_metadata().to_dict(),
                "required_fields": list(config.required_fields),
                "search_fields": sorted(config.search_fields),
                "warnings": list(config.warnings),
                "complementary_sources": list(
                    COMPLEMENTARY_SOURCES[config.source_id]
                ),
            }
            for config in SOURCES.values()
        ],
        "process_learnings": [
            {
                "scope": "component_identity",
                "learning": (
                    "Building, land-use, and code-compliance layers remain "
                    "separate sources even though they share a county server."
                ),
            },
            {
                "scope": "event_and_observation_identity",
                "learning": (
                    "Native permit identity and ArcGIS OBJECTID observation "
                    "identity are both needed because one permit can be "
                    "published under multiple layer observations."
                ),
            },
            {
                "scope": "detail_depth",
                "learning": (
                    "Structured ArcGIS index rows, Accela detail pages, parcel "
                    "polygons, interactive maps, and copy requests are "
                    "complementary representations joined by explicit fields."
                ),
            },
        ],
    }


def _all_probe_payload(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> dict[str, Any]:
    components = [
        _execute_probe(
            args,
            config,
            access_decision=access_decision,
            log_results=log_results,
        ).to_dict()
        for config in SOURCES.values()
    ]
    successful = sum(
        component["status"] in {"ok", "no_results"}
        for component in components
    )
    status = (
        "ok"
        if successful == len(components)
        else "partial"
        if successful
        else "unavailable"
    )
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": status,
        "components": components,
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute source listing, query, or bounded probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "probe":
        if args.all_sources:
            return _all_probe_payload(
                args,
                access_decision=access_decision,
                log_results=log_results,
            )
        return _execute_probe(
            args,
            _source(args.source),
            client=client,
            access_decision=access_decision,
            log_results=log_results,
        )
    return _execute_records(
        args,
        client=client,
        access_decision=access_decision,
        log_results=log_results,
    )


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _payload(
    value: PublicRecordsResult | Mapping[str, Any],
) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    if args.output:
        destination = Path(args.output).expanduser()
        _atomic_json_write(destination, payload)
        records = payload.get("records")
        count = (
            len(records)
            if isinstance(records, list)
            else len(payload.get("components", payload.get("sources", [])))
        )
        print(
            f"{count} results (Jackson property events {args.command}) "
            f"saved to {destination}"
        )
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command == "sources":
        print(f"Jackson County property-event sources: {len(payload['sources'])}")
        for source in payload["sources"]:
            print(
                f"  {source['source_id']} | "
                f"{source['metadata']['record_kind']} | "
                f"{', '.join(source['search_fields'])}"
            )
        return
    if args.command == "probe" and args.all_sources:
        print(f"Jackson County property-event probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | "
                f"{component['status']}"
            )
        return
    records = payload.get("records", [])
    print(
        f"Jackson property events {args.command}: "
        f"{payload.get('status')} ({len(records)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        print(
            f"  {record.get('native_event_id')} | "
            f"OBJECTID {record.get('object_id')} | "
            f"{record.get('source_id')}"
        )
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def _add_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        required=True,
        choices=sorted(SOURCES),
        help="Exact component-scoped source ID",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--cursor",
        help="Query-bound continuation cursor returned by an earlier result",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Request source points transformed to WGS84",
    )
    _add_transport_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Jackson County ArcGIS permit and "
            "code-compliance property events"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser("sources", help="List components and complements")
    add_output_args(sources)

    search = sub.add_parser("search", help="Search one selected component")
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=(
            "auto",
            "native_id",
            "case",
            "address",
            "person",
            "map_taxlot",
            "status",
            "type",
            "description",
        ),
        default="auto",
    )
    _add_query_arguments(search)

    for command, help_text in (
        ("record", "Look up an exact native permit or violation ID"),
        ("address", "Search published address and location fields"),
        ("person", "Search applicant, contractor, or published owner"),
        ("map-taxlot", "Look up an exact published taxlot location"),
    ):
        query_parser = sub.add_parser(command, help=help_text)
        query_parser.add_argument("query")
        query_parser.set_defaults(field=command.replace("-", "_"))
        _add_query_arguments(query_parser)

    probe = sub.add_parser("probe", help="Run bounded component health probes")
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source", choices=sorted(SOURCES))
    selection.add_argument(
        "--all",
        action="store_true",
        dest="all_sources",
        help="Probe every configured component",
    )
    probe.set_defaults(all_sources=False)
    _add_transport_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for field_name in ("page_size", "retry_attempts"):
        if getattr(args, field_name, 1) <= 0:
            parser.error(f"--{field_name.replace('_', '-')} must be positive")
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if hasattr(args, "query") and not args.query.strip():
        parser.error("query must not be blank")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
