#!/usr/bin/env python3
"""Query Philadelphia property, assessment-history, and parcel-map records.

The Office of Property Assessment (OPA) publishes current property records
through an anonymous ArcGIS FeatureServer and a CARTO mirror.  The same CARTO
account publishes annual assessment history.  The Department of Records (DOR)
publishes a separate polygon layer derived from recorded deed descriptions.

Current-record searches use OPA ArcGIS because it exposes a documented schema,
ordered queries, point geometry, and a source edit marker.  Assessment history
uses the official ``assessments`` CARTO table.  DOR parcel polygons remain a
separate observation joined by OPA ``registry_number``/DOR ``mapreg`` or PIN.

Omitting ``--limit`` traverses every native match.  ``--page-size`` controls
transport batches only; it is not a collection ceiling.

Examples:
    uv run python tools/query_philadelphia_property.py owner "EPSTEIN"
    uv run python tools/query_philadelphia_property.py address "MARKET ST"
    uv run python tools/query_philadelphia_property.py parcel 341086700
    uv run python tools/query_philadelphia_property.py history 341086700
    uv run python tools/query_philadelphia_property.py parcel-shape \
        062N200131 --by registry
    uv run python tools/query_philadelphia_property.py alternatives --json
    uv run python tools/query_philadelphia_property.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

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
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
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
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


FAMILY_SOURCE_ID = "us-pa-philadelphia-property-data"
SOURCE_ID = "us-pa-philadelphia-opa-properties"
HISTORY_SOURCE_ID = "us-pa-philadelphia-opa-assessment-history"
DOR_SOURCE_ID = "us-pa-philadelphia-dor-parcels"
OPA_BULK_SOURCE_ID = "us-pa-philadelphia-opa-current-bulk"
OPA_CARTO_SOURCE_ID = "us-pa-philadelphia-opa-carto-mirror"
HISTORY_BULK_SOURCE_ID = "us-pa-philadelphia-opa-history-bulk"
ATLAS_SOURCE_ID = "us-pa-philadelphia-atlas"
PHILADOX_SOURCE_ID = "us-pa-philadelphia-philadox"
RECORDS_SOURCE_ID = "us-pa-philadelphia-records-and-archives"
PROPERTY_APP_SOURCE_ID = "us-pa-philadelphia-property-application"
COUNTY_GEOID = "42101"
STATE_CODE = "PA"
LOCALITY = "Philadelphia"

ARCGIS_ORG_ID = "fLeGjb7u4uXqeF9q"
OPA_ITEM_ID = "286094c5c9034a38b826afed954da6f3"
OPA_LAYER_URL = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/"
    "OPA_PROPERTIES_PUBLIC/FeatureServer/0"
)
DOR_ITEM_ID = "1c57dd1b3ff84449a4b0e3fb29d3cafd"
DOR_LAYER_URL = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/"
    "DOR_Parcel/FeatureServer/0"
)
CARTO_SQL_URL = "https://phl.carto.com/api/v2/sql"
ASSESSMENT_TABLE = "assessments"
OPEN_DATA_PAGE = (
    "https://opendataphilly.org/datasets/"
    "philadelphia-properties-and-assessment-history/"
)
DOR_OPEN_DATA_PAGE = (
    "https://opendataphilly.org/datasets/"
    "department-of-records-property-parcels/"
)
PROPERTY_APP_URL = "https://property.phila.gov/"
ATLAS_URL = "https://atlas.phila.gov/"
PHILADOX_URL = "https://epayss.phila-records.com/"
DEED_HELP_URL = (
    "https://www.phila.gov/services/property-lots-housing/"
    "get-a-copy-of-a-deed-or-other-recorded-document/"
)
OPA_CURRENT_CSV_URL = (
    "https://opendata-downloads.s3.amazonaws.com/"
    "opa_properties_public.csv"
)
OPA_HISTORY_CSV_URL = (
    "https://opendata-downloads.s3.amazonaws.com/assessments.csv"
)
OPA_CARTO_GEOJSON_URL = (
    "https://phl.carto.com/api/v2/sql?"
    "filename=opa_properties_public&format=geojson&"
    "q=SELECT%20*%20FROM%20opa_properties_public"
)

PROBE_PARCEL_NUMBER = "341086700"
PROBE_REGISTRY_NUMBER = "062N200131"
PROBE_PIN = "1001666377"
DEFAULT_PAGE_SIZE = 2_000
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = "phila-property:v1:"
CURSOR_VERSION = 1

CURRENT_REQUIRED_FIELDS = (
    "assessment_date",
    "book_and_page",
    "location",
    "mailing_address_1",
    "mailing_city_state",
    "mailing_street",
    "mailing_zip",
    "market_value",
    "owner_1",
    "owner_2",
    "parcel_number",
    "recording_date",
    "registry_number",
    "sale_date",
    "sale_price",
    "taxable_building",
    "taxable_land",
    "total_area",
    "total_livable_area",
    "year_built",
    "zip_code",
    "zoning",
    "pin",
    "objectid",
)

DOR_REQUIRED_FIELDS = (
    "basereg",
    "mapreg",
    "parcel",
    "recmap",
    "inactdate",
    "orig_date",
    "status",
    "addr_source",
    "addr_std",
    "pin",
    "muniment_type",
    "muniment_id",
    "objectid",
    "Shape__Area",
    "Shape__Length",
)

HISTORY_REQUIRED_FIELDS = (
    "parcel_number",
    "year",
    "market_value",
    "taxable_land",
    "taxable_building",
    "exempt_land",
    "exempt_building",
    "objectid",
)

CURRENT_WARNINGS = (
    "OPA owner fields are assessment-roll observations, not a substitute for "
    "the underlying recorded deed.",
    "OPA sale and recording fields are index attributes; use their deed "
    "references with Philadox or the Department of Records when the instrument "
    "itself matters.",
    "OPA geometry is a property point. Use the DOR parcel route for the "
    "separate deed-description-derived polygon.",
)

HISTORY_WARNINGS = (
    "Assessment-history rows and current OPA records come from the same office "
    "and are not independent corroboration.",
    "The published year is retained as the source's assessment-year label; "
    "the table can include a forthcoming tax year.",
)

DOR_WARNINGS = (
    "DOR polygons are map observations derived from recorded deed "
    "descriptions; use the recorded instrument for the controlling text.",
    "Inactive and remainder parcels can be historically useful, so source "
    "status fields are retained without recoding them.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Philadelphia OPA Properties",
    source_role="county_property_assessment_owner_sale_index",
    base_url=OPA_LAYER_URL,
    dataset_id=f"{OPA_ITEM_ID}/0",
    metadata={
        "authority": "City of Philadelphia Office of Property Assessment",
        "coverage": "All properties in Philadelphia",
        "update_frequency": "nightly",
        "arcgis_org_id": ARCGIS_ORG_ID,
        "arcgis_item_id": OPA_ITEM_ID,
        "layer_id": 0,
        "carto_mirror_table": "opa_properties_public",
        "open_data_page": OPEN_DATA_PAGE,
    },
)

HISTORY_SOURCE_METADATA = SourceMetadata(
    source_id=HISTORY_SOURCE_ID,
    name="Philadelphia OPA Property Assessment History",
    source_role="county_property_assessment_history",
    base_url=CARTO_SQL_URL,
    dataset_id=ASSESSMENT_TABLE,
    metadata={
        "authority": "City of Philadelphia Office of Property Assessment",
        "coverage": "Annual assessment history for Philadelphia properties",
        "update_frequency": "nightly",
        "open_data_page": OPEN_DATA_PAGE,
    },
)

DOR_SOURCE_METADATA = SourceMetadata(
    source_id=DOR_SOURCE_ID,
    name="Philadelphia Department of Records Property Parcels",
    source_role="county_deed_description_parcel_geometry",
    base_url=DOR_LAYER_URL,
    dataset_id=f"{DOR_ITEM_ID}/0",
    metadata={
        "authority": "City of Philadelphia Department of Records",
        "coverage": "Philadelphia real-estate parcel boundaries",
        "update_frequency": "weekly",
        "arcgis_org_id": ARCGIS_ORG_ID,
        "arcgis_item_id": DOR_ITEM_ID,
        "layer_id": 0,
        "open_data_page": DOR_OPEN_DATA_PAGE,
    },
)

FAMILY_SOURCE_METADATA = SourceMetadata(
    source_id=FAMILY_SOURCE_ID,
    name="Philadelphia Property Record Source Family",
    source_role="county_property_source_family",
    base_url=OPEN_DATA_PAGE,
    metadata={
        "authority": "City of Philadelphia",
        "current_source_id": SOURCE_ID,
        "history_source_id": HISTORY_SOURCE_ID,
        "parcel_geometry_source_id": DOR_SOURCE_ID,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Philadelphia County, Pennsylvania",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality=LOCALITY,
)


@dataclass(frozen=True)
class ArcGISManifest:
    route: str
    source_id: str
    layer_url: str
    item_id: str
    layer_name: str
    geometry_type: str
    required_fields: tuple[str, ...]


OPA_MANIFEST = ArcGISManifest(
    route="opa_current",
    source_id=SOURCE_ID,
    layer_url=OPA_LAYER_URL,
    item_id=OPA_ITEM_ID,
    layer_name="OPA_PROPERTIES_PUBLIC",
    geometry_type="esriGeometryPoint",
    required_fields=CURRENT_REQUIRED_FIELDS,
)

DOR_MANIFEST = ArcGISManifest(
    route="dor_parcel",
    source_id=DOR_SOURCE_ID,
    layer_url=DOR_LAYER_URL,
    item_id=DOR_ITEM_ID,
    layer_name="DOR_Parcel",
    geometry_type="esriGeometryPolygon",
    required_fields=DOR_REQUIRED_FIELDS,
)


class PhiladelphiaPropertyError(RuntimeError):
    """A selection or continuation error with result-envelope semantics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "query_selection",
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


@dataclass(frozen=True)
class CursorState:
    route: str
    criteria_fingerprint: str
    last_object_id: int
    total_count: int
    schema_fingerprint: str
    dataset_version: int | None


@dataclass(frozen=True)
class SourceSnapshot:
    schema_fingerprint: str
    dataset_version: int | None
    page_size: int
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class TraversalBatch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    remaining_count: int
    pages_fetched: int
    schema_fingerprint: str
    dataset_version: int | None
    error: PublicRecordsError | None = None


class PhiladelphiaArcGISClient(ArcGISRESTClient):
    """Metadata, count, and ordered-keyset access to one Philadelphia layer."""

    def __init__(
        self,
        manifest: ArcGISManifest,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
    ) -> None:
        super().__init__(
            manifest.layer_url,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )
        self.manifest = manifest

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Philadelphia ArcGIS returned invalid layer metadata",
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
                "Philadelphia ArcGIS returned an invalid count response",
                url=self.query_url,
                details={"response": payload},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Philadelphia ArcGIS count is not a non-negative integer",
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
    ) -> tuple[Mapping[str, Any], ...]:
        params: dict[str, Any] = {
            "where": where,
            "outFields": "*",
            "returnGeometry": str(return_geometry).lower(),
            "orderByFields": "objectid ASC",
            "resultRecordCount": record_count,
            "f": "json",
        }
        if return_geometry:
            params["outSR"] = 4326
        payload = self._request_json(self.query_url, params=params)
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Philadelphia ArcGIS returned an invalid feature response",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "Philadelphia ArcGIS response lacks a valid features array",
                url=self.query_url,
            )
        return tuple(features)


class PhiladelphiaCartoClient(ArcGISRESTClient):
    """Small retrying facade over Philadelphia's public CARTO SQL endpoint."""

    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
    ) -> None:
        super().__init__(
            CARTO_SQL_URL,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )

    def _sql(self, statement: str) -> Mapping[str, Any]:
        payload = self._request_json(CARTO_SQL_URL, params={"q": statement})
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Philadelphia CARTO returned an invalid SQL response",
                url=CARTO_SQL_URL,
                details={"response": payload},
            )
        return payload

    def fetch_schema(self) -> Mapping[str, Any]:
        payload = self._sql(f"SELECT * FROM {ASSESSMENT_TABLE} LIMIT 0")
        fields = payload.get("fields")
        if not isinstance(fields, Mapping) or any(
            not isinstance(name, str) or not isinstance(definition, Mapping)
            for name, definition in fields.items()
        ):
            raise SourceSchemaError(
                "Philadelphia CARTO schema response lacks field declarations",
                url=CARTO_SQL_URL,
            )
        return fields

    def fetch_count(self, where: str) -> int:
        payload = self._sql(
            f"SELECT count(*) AS count FROM {ASSESSMENT_TABLE} WHERE {where}"
        )
        rows = payload.get("rows")
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], Mapping)
        ):
            raise SourceSchemaError(
                "Philadelphia CARTO count response is malformed",
                url=CARTO_SQL_URL,
            )
        count = rows[0].get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Philadelphia CARTO count is not a non-negative integer",
                url=CARTO_SQL_URL,
                details={"count": count},
            )
        return count

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
    ) -> tuple[Mapping[str, Any], ...]:
        fields = ", ".join(HISTORY_REQUIRED_FIELDS)
        statement = (
            f"SELECT {fields} FROM {ASSESSMENT_TABLE} "
            f"WHERE {where} ORDER BY objectid ASC LIMIT {record_count}"
        )
        payload = self._sql(statement)
        rows = payload.get("rows")
        if not isinstance(rows, list) or any(
            not isinstance(row, Mapping) for row in rows
        ):
            raise SourceSchemaError(
                "Philadelphia CARTO response lacks a valid rows array",
                url=CARTO_SQL_URL,
            )
        return tuple(rows)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        raise PhiladelphiaPropertyError(
            "blank_query",
            "query value must not be blank",
        )
    return text.replace("'", "''")


def _numeric_selector(value: Any, field_name: str) -> int:
    text = _clean_text(value)
    if not text or not text.isdigit():
        raise PhiladelphiaPropertyError(
            "invalid_numeric_selector",
            f"{field_name} must be numeric",
            details={"field": field_name},
        )
    return int(text)


def _where_current(operation: str, selector: str | None) -> str:
    if operation == "probe":
        return f"parcel_number='{PROBE_PARCEL_NUMBER}'"
    value = _sql_text(selector)
    if operation == "owner":
        return (
            f"(owner_1 LIKE '%{value}%' OR owner_2 LIKE '%{value}%')"
        )
    if operation == "address":
        return f"location LIKE '%{value}%'"
    if operation == "parcel":
        return f"parcel_number='{value}'"
    if operation == "registry":
        return f"registry_number='{value}'"
    if operation == "pin":
        return f"pin={_numeric_selector(value, 'pin')}"
    if operation == "objectid":
        return f"objectid={_numeric_selector(value, 'objectid')}"
    raise PhiladelphiaPropertyError(
        "unsupported_operation",
        f"unsupported OPA operation: {operation}",
    )


def _where_history(
    selector: str | None,
    *,
    from_year: int | None,
    to_year: int | None,
) -> str:
    value = _sql_text(selector)
    clauses = [f"parcel_number='{value}'"]
    if from_year is not None:
        clauses.append(f"year >= '{from_year}'")
    if to_year is not None:
        clauses.append(f"year <= '{to_year}'")
    return " AND ".join(clauses)


def _where_dor(selector: str | None, by: str) -> str:
    value = _sql_text(selector)
    if by == "registry":
        return f"(mapreg='{value}' OR basereg='{value}')"
    if by == "pin":
        return f"pin={_numeric_selector(value, 'pin')}"
    if by == "address":
        return (
            f"(addr_std LIKE '%{value}%' OR addr_source LIKE '%{value}%')"
        )
    if by == "objectid":
        return f"objectid={_numeric_selector(value, 'objectid')}"
    raise PhiladelphiaPropertyError(
        "unsupported_dor_selector",
        f"unsupported DOR selector: {by}",
    )


def _source_for_operation(operation: str) -> SourceMetadata:
    if operation == "alternatives":
        return FAMILY_SOURCE_METADATA
    if operation == "history":
        return HISTORY_SOURCE_METADATA
    if operation == "parcel-shape":
        return DOR_SOURCE_METADATA
    return SOURCE_METADATA


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    operation = args.command
    selector = (
        PROBE_PARCEL_NUMBER
        if operation == "probe"
        else getattr(args, "query", None)
    )
    parameters: dict[str, Any] = {"selector": selector}
    if operation == "history":
        parameters.update(
            {
                "from_year": getattr(args, "from_year", None),
                "to_year": getattr(args, "to_year", None),
            }
        )
    if operation == "parcel-shape":
        parameters["by"] = getattr(args, "by", "registry")
    if operation not in {"history", "alternatives"}:
        parameters["return_geometry"] = bool(
            getattr(args, "geometry", False)
        )
    requested_limit = (
        1 if operation == "probe" else getattr(args, "limit", None)
    )
    return PublicRecordsQuery(
        source=_source_for_operation(operation),
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
        ),
    )


def _compatible_arcgis_snapshot(
    manifest: ArcGISManifest,
    metadata: Mapping[str, Any],
) -> SourceSnapshot:
    identity = {
        "name": metadata.get("name"),
        "id": metadata.get("id"),
        "service_item_id": metadata.get("serviceItemId"),
        "object_id_field": metadata.get("objectIdField"),
        "geometry_type": metadata.get("geometryType"),
    }
    expected_identity = {
        "name": manifest.layer_name,
        "id": 0,
        "service_item_id": manifest.item_id,
        "object_id_field": "objectid",
        "geometry_type": manifest.geometry_type,
    }
    if identity != expected_identity:
        raise SourceSchemaError(
            "Philadelphia ArcGIS layer identity changed",
            url=manifest.layer_url,
            details={
                "expected": expected_identity,
                "observed": identity,
            },
        )
    capabilities = metadata.get("advancedQueryCapabilities")
    if not isinstance(capabilities, Mapping) or not (
        capabilities.get("supportsOrderBy") is True
        and capabilities.get("supportsPagination") is True
    ):
        raise SourceSchemaError(
            "Philadelphia ArcGIS layer no longer declares ordered queries",
            url=manifest.layer_url,
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "Philadelphia ArcGIS metadata lacks field declarations",
            url=manifest.layer_url,
        )
    definitions = {
        str(field.get("name")): {
            "name": field.get("name"),
            "type": field.get("type"),
            "length": field.get("length"),
        }
        for field in fields
        if isinstance(field.get("name"), str)
    }
    missing = sorted(set(manifest.required_fields) - set(definitions))
    if missing:
        raise SourceSchemaError(
            "Philadelphia ArcGIS layer is missing required fields",
            url=manifest.layer_url,
            details={"missing_fields": missing},
        )
    native_maximum = metadata.get("maxRecordCount")
    if (
        isinstance(native_maximum, bool)
        or not isinstance(native_maximum, int)
        or native_maximum <= 0
    ):
        raise SourceSchemaError(
            "Philadelphia ArcGIS metadata lacks a usable maxRecordCount",
            url=manifest.layer_url,
            details={"maxRecordCount": native_maximum},
        )
    editing_info = metadata.get("editingInfo")
    dataset_version = (
        editing_info.get("dataLastEditDate")
        if isinstance(editing_info, Mapping)
        else None
    )
    if isinstance(dataset_version, bool) or not isinstance(
        dataset_version, (int, type(None))
    ):
        dataset_version = None
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": manifest.source_id,
            "identity": identity,
            "required_fields": {
                name: definitions[name]
                for name in manifest.required_fields
            },
        }
    )
    return SourceSnapshot(
        schema_fingerprint=schema_fingerprint,
        dataset_version=dataset_version,
        page_size=native_maximum,
        metadata=dict(metadata),
    )


def _compatible_history_snapshot(
    client: Any,
) -> SourceSnapshot:
    fields = client.fetch_schema()
    missing = sorted(set(HISTORY_REQUIRED_FIELDS) - set(fields))
    if missing:
        raise SourceSchemaError(
            "Philadelphia assessment-history table is missing required fields",
            url=CARTO_SQL_URL,
            details={"missing_fields": missing},
        )
    compatible_fields = {
        name: dict(fields[name]) for name in HISTORY_REQUIRED_FIELDS
    }
    return SourceSnapshot(
        schema_fingerprint=sha256_fingerprint(
            {
                "source_id": HISTORY_SOURCE_ID,
                "table": ASSESSMENT_TABLE,
                "required_fields": compatible_fields,
            }
        ),
        dataset_version=None,
        page_size=int(client.page_size),
        metadata={"fields": compatible_fields},
    )


def _criteria_fingerprint(
    *,
    route: str,
    operation: str,
    where: str,
    return_geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "route": route,
            "operation": operation,
            "where": where,
            "return_geometry": return_geometry,
            "ordering": "objectid ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "route": state.route,
        "criteria": state.criteria_fingerprint,
        "last_oid": state.last_object_id,
        "total": state.total_count,
        "schema": state.schema_fingerprint,
        "dataset_version": state.dataset_version,
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
        raise PhiladelphiaPropertyError(
            "invalid_cursor",
            "cursor does not belong to the Philadelphia property adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(token + padding).decode("utf-8")
        )
        state = CursorState(
            route=str(payload["route"]),
            criteria_fingerprint=str(payload["criteria"]),
            last_object_id=int(payload["last_oid"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
            dataset_version=(
                None
                if payload.get("dataset_version") is None
                else int(payload["dataset_version"])
            ),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise PhiladelphiaPropertyError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if (
        payload.get("v") != CURSOR_VERSION
        or state.last_object_id < 0
        or state.total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise PhiladelphiaPropertyError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _object_id_from_feature(feature: Mapping[str, Any]) -> int:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "Philadelphia ArcGIS feature lacks an attributes object",
            url="arcgis://feature",
        )
    value = attributes.get("objectid")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceSchemaError(
            "Philadelphia ArcGIS feature lacks a valid objectid",
            url="arcgis://feature",
            details={"objectid": value},
        )
    return value


def _object_id_from_history(row: Mapping[str, Any]) -> int:
    value = row.get("objectid")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceSchemaError(
            "Philadelphia assessment row lacks a valid objectid",
            url=CARTO_SQL_URL,
            details={"objectid": value},
        )
    return value


def _keyset_where(where: str, last_object_id: int | None) -> str:
    if last_object_id is None:
        return where
    return f"({where}) AND objectid > {last_object_id}"


def _partial_error(
    code: str,
    message: str,
    *,
    details: Mapping[str, Any],
) -> PublicRecordsError:
    return PublicRecordsError(
        code=code,
        message=message,
        category="source_schema",
        retryable=False,
        details=details,
    )


def _validate_cursor(
    state: CursorState | None,
    *,
    route: str,
    criteria: str,
    snapshot: SourceSnapshot,
) -> None:
    if state is None:
        return
    if state.route != route or state.criteria_fingerprint != criteria:
        raise PhiladelphiaPropertyError(
            "cursor_query_mismatch",
            "cursor belongs to different query criteria",
        )
    if state.schema_fingerprint != snapshot.schema_fingerprint:
        raise PhiladelphiaPropertyError(
            "cursor_schema_changed",
            "source schema changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    if (
        state.dataset_version is not None
        and snapshot.dataset_version is not None
        and state.dataset_version != snapshot.dataset_version
    ):
        raise PhiladelphiaPropertyError(
            "cursor_snapshot_changed",
            "source data refreshed after the cursor was issued; restart the "
            "query for a complete snapshot",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_dataset_version": state.dataset_version,
                "current_dataset_version": snapshot.dataset_version,
            },
        )


def _traverse_arcgis(
    client: Any,
    manifest: ArcGISManifest,
    *,
    operation: str,
    where: str,
    limit: int | None,
    cursor: str | None,
    return_geometry: bool,
) -> TraversalBatch:
    start_snapshot = _compatible_arcgis_snapshot(
        manifest, client.fetch_metadata()
    )
    criteria = _criteria_fingerprint(
        route=manifest.route,
        operation=operation,
        where=where,
        return_geometry=return_geometry,
    )
    cursor_state = _decode_cursor(cursor)
    _validate_cursor(
        cursor_state,
        route=manifest.route,
        criteria=criteria,
        snapshot=start_snapshot,
    )
    total_count = client.fetch_count(where)
    if cursor_state is not None and cursor_state.total_count != total_count:
        raise PhiladelphiaPropertyError(
            "cursor_count_changed",
            "matching source count changed after the cursor was issued; "
            "restart the query for a complete snapshot",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_total_count": cursor_state.total_count,
                "current_total_count": total_count,
            },
        )
    last_object_id = (
        cursor_state.last_object_id if cursor_state is not None else None
    )
    remaining_where = _keyset_where(where, last_object_id)
    remaining_count = (
        total_count
        if last_object_id is None
        else client.fetch_count(remaining_where)
    )
    target = (
        remaining_count if limit is None else min(limit, remaining_count)
    )
    page_size = min(int(client.page_size), start_snapshot.page_size)
    collected: list[Mapping[str, Any]] = []
    pages_fetched = 0
    traversal_error: PublicRecordsError | None = None

    while len(collected) < target:
        requested = min(page_size, target - len(collected))
        page = client.fetch_page(
            where=_keyset_where(where, last_object_id),
            record_count=requested,
            return_geometry=return_geometry,
        )
        pages_fetched += 1
        if not page:
            traversal_error = _partial_error(
                "arcgis_traversal_ended_early",
                "ArcGIS traversal ended before its reported count",
                details={
                    "target": target,
                    "retrieved": len(collected),
                    "remaining_count": remaining_count,
                },
            )
            break
        if len(page) > requested:
            traversal_error = _partial_error(
                "arcgis_page_exceeded_request",
                "ArcGIS returned more features than the requested page size",
                details={
                    "requested": requested,
                    "returned": len(page),
                },
            )
            page = page[:requested]
        for feature in page:
            object_id = _object_id_from_feature(feature)
            if (
                last_object_id is not None
                and object_id <= last_object_id
            ):
                traversal_error = _partial_error(
                    "arcgis_keyset_not_monotonic",
                    "ArcGIS repeated or reordered a keyset feature",
                    details={
                        "previous_object_id": last_object_id,
                        "object_id": object_id,
                    },
                )
                break
            collected.append(feature)
            last_object_id = object_id
        if traversal_error is not None:
            break
        if len(page) < requested and len(collected) < target:
            traversal_error = _partial_error(
                "arcgis_short_page_before_count",
                "ArcGIS returned a short page before its reported count",
                details={
                    "target": target,
                    "retrieved": len(collected),
                    "page_size": len(page),
                },
            )
            break

    if traversal_error is None and len(collected) != target:
        traversal_error = _partial_error(
            "arcgis_count_mismatch",
            "ArcGIS traversal did not return its reported target count",
            details={"target": target, "retrieved": len(collected)},
        )

    try:
        end_snapshot = _compatible_arcgis_snapshot(
            manifest, client.fetch_metadata()
        )
        end_count = client.fetch_count(where)
    except PublicRecordsHTTPError as error:
        if not collected:
            raise
        end_snapshot = start_snapshot
        end_count = total_count
        traversal_error = error.to_contract_error()

    if traversal_error is None and (
        end_snapshot.schema_fingerprint
        != start_snapshot.schema_fingerprint
        or end_snapshot.dataset_version != start_snapshot.dataset_version
        or end_count != total_count
    ):
        traversal_error = _partial_error(
            "source_changed_during_traversal",
            "Philadelphia ArcGIS data changed during traversal",
            details={
                "start_count": total_count,
                "end_count": end_count,
                "start_dataset_version": start_snapshot.dataset_version,
                "end_dataset_version": end_snapshot.dataset_version,
            },
        )

    next_cursor = None
    if (
        traversal_error is None
        and remaining_count > len(collected)
        and collected
    ):
        next_cursor = _encode_cursor(
            CursorState(
                route=manifest.route,
                criteria_fingerprint=criteria,
                last_object_id=_object_id_from_feature(collected[-1]),
                total_count=total_count,
                schema_fingerprint=start_snapshot.schema_fingerprint,
                dataset_version=start_snapshot.dataset_version,
            )
        )
    return TraversalBatch(
        records=tuple(collected),
        next_cursor=next_cursor,
        total_count=total_count,
        remaining_count=remaining_count,
        pages_fetched=pages_fetched,
        schema_fingerprint=start_snapshot.schema_fingerprint,
        dataset_version=start_snapshot.dataset_version,
        error=traversal_error,
    )


def _traverse_history(
    client: Any,
    *,
    where: str,
    limit: int | None,
    cursor: str | None,
) -> TraversalBatch:
    start_snapshot = _compatible_history_snapshot(client)
    criteria = _criteria_fingerprint(
        route="opa_history",
        operation="history",
        where=where,
        return_geometry=False,
    )
    cursor_state = _decode_cursor(cursor)
    _validate_cursor(
        cursor_state,
        route="opa_history",
        criteria=criteria,
        snapshot=start_snapshot,
    )
    total_count = client.fetch_count(where)
    if cursor_state is not None and cursor_state.total_count != total_count:
        raise PhiladelphiaPropertyError(
            "cursor_count_changed",
            "matching assessment-history count changed after the cursor was "
            "issued; restart the query for a complete snapshot",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_total_count": cursor_state.total_count,
                "current_total_count": total_count,
            },
        )
    last_object_id = (
        cursor_state.last_object_id if cursor_state is not None else None
    )
    remaining_where = _keyset_where(where, last_object_id)
    remaining_count = (
        total_count
        if last_object_id is None
        else client.fetch_count(remaining_where)
    )
    target = (
        remaining_count if limit is None else min(limit, remaining_count)
    )
    collected: list[Mapping[str, Any]] = []
    pages_fetched = 0
    traversal_error: PublicRecordsError | None = None

    while len(collected) < target:
        requested = min(int(client.page_size), target - len(collected))
        page = client.fetch_page(
            where=_keyset_where(where, last_object_id),
            record_count=requested,
        )
        pages_fetched += 1
        if not page:
            traversal_error = _partial_error(
                "carto_traversal_ended_early",
                "CARTO traversal ended before its reported count",
                details={
                    "target": target,
                    "retrieved": len(collected),
                    "remaining_count": remaining_count,
                },
            )
            break
        if len(page) > requested:
            traversal_error = _partial_error(
                "carto_page_exceeded_request",
                "CARTO returned more rows than the requested page size",
                details={
                    "requested": requested,
                    "returned": len(page),
                },
            )
            page = page[:requested]
        for row in page:
            object_id = _object_id_from_history(row)
            if (
                last_object_id is not None
                and object_id <= last_object_id
            ):
                traversal_error = _partial_error(
                    "carto_keyset_not_monotonic",
                    "CARTO repeated or reordered an assessment row",
                    details={
                        "previous_object_id": last_object_id,
                        "object_id": object_id,
                    },
                )
                break
            collected.append(row)
            last_object_id = object_id
        if traversal_error is not None:
            break
        if len(page) < requested and len(collected) < target:
            traversal_error = _partial_error(
                "carto_short_page_before_count",
                "CARTO returned a short page before its reported count",
                details={
                    "target": target,
                    "retrieved": len(collected),
                    "page_size": len(page),
                },
            )
            break

    if traversal_error is None and len(collected) != target:
        traversal_error = _partial_error(
            "carto_count_mismatch",
            "CARTO traversal did not return its reported target count",
            details={"target": target, "retrieved": len(collected)},
        )

    try:
        end_snapshot = _compatible_history_snapshot(client)
        end_count = client.fetch_count(where)
    except PublicRecordsHTTPError as error:
        if not collected:
            raise
        end_snapshot = start_snapshot
        end_count = total_count
        traversal_error = error.to_contract_error()

    if traversal_error is None and (
        end_snapshot.schema_fingerprint
        != start_snapshot.schema_fingerprint
        or end_count != total_count
    ):
        traversal_error = _partial_error(
            "source_changed_during_traversal",
            "Philadelphia assessment history changed during traversal",
            details={
                "start_count": total_count,
                "end_count": end_count,
            },
        )

    next_cursor = None
    if (
        traversal_error is None
        and remaining_count > len(collected)
        and collected
    ):
        next_cursor = _encode_cursor(
            CursorState(
                route="opa_history",
                criteria_fingerprint=criteria,
                last_object_id=_object_id_from_history(collected[-1]),
                total_count=total_count,
                schema_fingerprint=start_snapshot.schema_fingerprint,
                dataset_version=None,
            )
        )
    return TraversalBatch(
        records=tuple(collected),
        next_cursor=next_cursor,
        total_count=total_count,
        remaining_count=remaining_count,
        pages_fetched=pages_fetched,
        schema_fingerprint=start_snapshot.schema_fingerprint,
        dataset_version=None,
        error=traversal_error,
    )


def _epoch_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(
                value / 1000, tz=timezone.utc
            ).date().isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    text = _clean_text(value)
    if not text:
        return None
    if "T" in text:
        return text.split("T", 1)[0]
    return text


def _source_snapshot(
    batch: TraversalBatch,
) -> dict[str, Any]:
    return {
        "reported_total_matches": batch.total_count,
        "reported_remaining_matches_at_start": batch.remaining_count,
        "pages_fetched": batch.pages_fetched,
        "compatible_schema_fingerprint": batch.schema_fingerprint,
        "data_last_edit_epoch_ms": batch.dataset_version,
    }


def _normalize_current(
    feature: Mapping[str, Any],
    batch: TraversalBatch,
    *,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise SourceSchemaError(
            "Philadelphia OPA feature lacks attributes",
            url=OPA_LAYER_URL,
        )
    attributes = dict(attributes_value)
    object_id = _object_id_from_feature(feature)
    parcel_number = _clean_text(attributes.get("parcel_number"))
    native_id = parcel_number or str(object_id)
    pin = _clean_text(attributes.get("pin"))
    registry_number = _clean_text(attributes.get("registry_number"))
    owners = []
    for field, role in (
        ("owner_1", "primary_assessor_owner"),
        ("owner_2", "secondary_assessor_owner"),
    ):
        name = _clean_text(attributes.get(field))
        if name:
            owners.append(
                {
                    "raw_name": name,
                    "role": role,
                    "assertion_type": "assessment_roll",
                    "source_field": field,
                }
            )
    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            native_id,
        ),
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "record_type": "current_property_assessment_observation",
        "jurisdiction": {
            "state_code": STATE_CODE,
            "county_name": "Philadelphia",
            "county_geoid": COUNTY_GEOID,
            "locality": LOCALITY,
        },
        "native_parcel_id": parcel_number,
        "object_id": object_id,
        "pin": pin,
        "registry_number": registry_number,
        "owners": owners,
        "situs_address": {
            "raw": _clean_text(attributes.get("location")),
            "house_number": _clean_text(attributes.get("house_number")),
            "street_direction": _clean_text(
                attributes.get("street_direction")
            ),
            "street_name": _clean_text(attributes.get("street_name")),
            "street_designation": _clean_text(
                attributes.get("street_designation")
            ),
            "unit": _clean_text(attributes.get("unit")),
            "postal_code": _clean_text(attributes.get("zip_code")),
            "state": STATE_CODE,
        },
        "mailing_address": {
            "addressee_line": _clean_text(
                attributes.get("mailing_address_1")
            ),
            "secondary_line": _clean_text(
                attributes.get("mailing_address_2")
            ),
            "care_of": _clean_text(attributes.get("mailing_care_of")),
            "street": _clean_text(attributes.get("mailing_street")),
            "city_state_raw": _clean_text(
                attributes.get("mailing_city_state")
            ),
            "postal_code": _clean_text(attributes.get("mailing_zip")),
            "source_state_code": _clean_text(
                attributes.get("state_code")
            ),
        },
        "assessment": {
            "assessment_date": _epoch_date(
                attributes.get("assessment_date")
            ),
            "market_value": attributes.get("market_value"),
            "market_value_date": _epoch_date(
                attributes.get("market_value_date")
            ),
            "taxable_land": attributes.get("taxable_land"),
            "taxable_building": attributes.get("taxable_building"),
            "exempt_land": attributes.get("exempt_land"),
            "exempt_building": attributes.get("exempt_building"),
            "homestead_exemption": attributes.get(
                "homestead_exemption"
            ),
            "currency": "USD",
        },
        "classification": {
            "category_code": _clean_text(
                attributes.get("category_code")
            ),
            "category_description": _clean_text(
                attributes.get("category_code_description")
            ),
            "building_code": _clean_text(
                attributes.get("building_code")
            ),
            "building_description": _clean_text(
                attributes.get("building_code_description")
            ),
            "building_code_new": _clean_text(
                attributes.get("building_code_new")
            ),
            "building_description_new": _clean_text(
                attributes.get("building_code_description_new")
            ),
            "zoning": _clean_text(attributes.get("zoning")),
        },
        "physical_characteristics": {
            "year_built": _clean_text(attributes.get("year_built")),
            "year_built_estimate": _clean_text(
                attributes.get("year_built_estimate")
            ),
            "total_area": attributes.get("total_area"),
            "total_livable_area": attributes.get(
                "total_livable_area"
            ),
            "frontage": attributes.get("frontage"),
            "depth": attributes.get("depth"),
            "stories": attributes.get("number_stories"),
            "bedrooms": attributes.get("number_of_bedrooms"),
            "bathrooms": attributes.get("number_of_bathrooms"),
            "rooms": attributes.get("number_of_rooms"),
            "exterior_condition": _clean_text(
                attributes.get("exterior_condition")
            ),
            "interior_condition": _clean_text(
                attributes.get("interior_condition")
            ),
        },
        "last_sale": {
            "sale_date": _epoch_date(attributes.get("sale_date")),
            "consideration": attributes.get("sale_price"),
            "currency": "USD",
            "recording_date": _epoch_date(
                attributes.get("recording_date")
            ),
            "book_and_page_raw": _clean_text(
                attributes.get("book_and_page")
            ),
            "registry_number": registry_number,
        },
        "related_routes": {
            "assessment_history": {
                "source_id": HISTORY_SOURCE_ID,
                "join_field": "parcel_number",
                "join_value": parcel_number,
            },
            "dor_parcel_geometry": {
                "source_id": DOR_SOURCE_ID,
                "join_fields": {
                    "registry_number_to_mapreg": registry_number,
                    "pin_to_pin": pin,
                },
            },
            "recorded_instrument_search": {
                "name": "Philadox",
                "url": PHILADOX_URL,
                "book_and_page_raw": _clean_text(
                    attributes.get("book_and_page")
                ),
            },
        },
        "source_snapshot": _source_snapshot(batch),
        "raw_attributes": attributes,
    }
    if geometry_requested and "geometry" in feature:
        result.update(
            {
                "geometry": feature.get("geometry"),
                "geometry_format": "esri_json",
                "geometry_crs": "EPSG:4326",
                "geometry_role": "opa_property_point",
            }
        )
    return result


def _normalize_history(
    row: Mapping[str, Any],
    batch: TraversalBatch,
) -> dict[str, Any]:
    object_id = _object_id_from_history(row)
    parcel_number = _clean_text(row.get("parcel_number"))
    native_id = parcel_number or str(object_id)
    year = _clean_text(row.get("year"))
    return {
        "canonical_ref": canonical_property_ref(
            HISTORY_SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            native_id,
        ),
        "source_id": HISTORY_SOURCE_ID,
        "dataset_id": ASSESSMENT_TABLE,
        "record_type": "annual_property_assessment_observation",
        "jurisdiction": {
            "state_code": STATE_CODE,
            "county_name": "Philadelphia",
            "county_geoid": COUNTY_GEOID,
            "locality": LOCALITY,
        },
        "native_id": f"{native_id}:{year or 'unknown'}:{object_id}",
        "native_parcel_id": parcel_number,
        "object_id": object_id,
        "assessment_year": year,
        "assessment": {
            "market_value": row.get("market_value"),
            "taxable_land": row.get("taxable_land"),
            "taxable_building": row.get("taxable_building"),
            "exempt_land": row.get("exempt_land"),
            "exempt_building": row.get("exempt_building"),
            "currency": "USD",
        },
        "related_current_source": {
            "source_id": SOURCE_ID,
            "join_field": "parcel_number",
            "join_value": parcel_number,
        },
        "source_snapshot": _source_snapshot(batch),
        "raw_row": dict(row),
    }


def _normalize_dor(
    feature: Mapping[str, Any],
    batch: TraversalBatch,
    *,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise SourceSchemaError(
            "Philadelphia DOR feature lacks attributes",
            url=DOR_LAYER_URL,
        )
    attributes = dict(attributes_value)
    object_id = _object_id_from_feature(feature)
    map_registry = _clean_text(attributes.get("mapreg"))
    base_registry = _clean_text(attributes.get("basereg"))
    pin = _clean_text(attributes.get("pin"))
    native_id = map_registry or base_registry or pin or str(object_id)
    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            DOR_SOURCE_ID,
            COUNTY_GEOID,
            "registry",
            native_id,
        ),
        "source_id": DOR_SOURCE_ID,
        "dataset_id": DOR_SOURCE_METADATA.dataset_id,
        "record_type": "deed_description_parcel_map_observation",
        "jurisdiction": {
            "state_code": STATE_CODE,
            "county_name": "Philadelphia",
            "county_geoid": COUNTY_GEOID,
            "locality": LOCALITY,
        },
        "native_id": native_id,
        "object_id": object_id,
        "map_registry_number": map_registry,
        "base_registry_number": base_registry,
        "registry_map": _clean_text(attributes.get("recmap")),
        "registry_parcel_component": _clean_text(
            attributes.get("parcel")
        ),
        "pin": pin,
        "address": {
            "source": _clean_text(attributes.get("addr_source")),
            "standardized": _clean_text(attributes.get("addr_std")),
        },
        "source_status": attributes.get("status"),
        "origin_date": _epoch_date(attributes.get("orig_date")),
        "inactive_date": _epoch_date(attributes.get("inactdate")),
        "muniment": {
            "type": _clean_text(attributes.get("muniment_type")),
            "id": _clean_text(attributes.get("muniment_id")),
        },
        "review_status": {
            "dor": _clean_text(attributes.get("dor_review")),
            "opa": _clean_text(attributes.get("opa_review")),
            "pwd": _clean_text(attributes.get("pwd_review")),
        },
        "related_opa_source": {
            "source_id": SOURCE_ID,
            "join_fields": {
                "mapreg_to_registry_number": map_registry,
                "pin_to_pin": pin,
            },
        },
        "source_shape_area": attributes.get("Shape__Area"),
        "source_shape_length": attributes.get("Shape__Length"),
        "source_snapshot": _source_snapshot(batch),
        "raw_attributes": attributes,
    }
    if geometry_requested and "geometry" in feature:
        result.update(
            {
                "geometry": feature.get("geometry"),
                "geometry_format": "esri_json",
                "geometry_crs": "EPSG:4326",
                "geometry_role": "dor_deed_description_parcel_polygon",
            }
        )
    return result


def _alternatives() -> list[dict[str, Any]]:
    return [
        {
            "source_id": OPA_BULK_SOURCE_ID,
            "route_id": "opa-nightly-current-csv",
            "name": "OPA current properties nightly CSV",
            "url": OPA_CURRENT_CSV_URL,
            "authority": "City of Philadelphia Office of Property Assessment",
            "access": "anonymous bulk download",
            "use": "full refreshes and recovery when query APIs are degraded",
            "relationship_to_primary": "same OPA dataset; transport redundancy",
        },
        {
            "source_id": OPA_CARTO_SOURCE_ID,
            "route_id": "opa-carto-current-mirror",
            "name": "OPA current properties CARTO mirror",
            "url": OPA_CARTO_GEOJSON_URL,
            "authority": "City of Philadelphia Office of Property Assessment",
            "access": "anonymous SQL API and GeoJSON",
            "use": "alternate current-record query and export transport",
            "relationship_to_primary": "same OPA dataset; not corroboration",
        },
        {
            "source_id": HISTORY_BULK_SOURCE_ID,
            "route_id": "opa-nightly-history-csv",
            "name": "OPA assessment-history nightly CSV",
            "url": OPA_HISTORY_CSV_URL,
            "authority": "City of Philadelphia Office of Property Assessment",
            "access": "anonymous bulk download",
            "use": "large historical backfills and reproducible snapshots",
            "relationship_to_primary": "bulk form of the CARTO history table",
        },
        {
            "source_id": DOR_SOURCE_ID,
            "route_id": "dor-parcel-polygons",
            "name": "Department of Records property parcels",
            "url": DOR_LAYER_URL,
            "authority": "City of Philadelphia Department of Records",
            "access": "anonymous ArcGIS API and weekly bulk exports",
            "use": "deed-description-derived polygon and registry/PIN joins",
            "relationship_to_primary": "complementary official dataset",
        },
        {
            "source_id": ATLAS_SOURCE_ID,
            "route_id": "atlas",
            "name": "Philadelphia Atlas",
            "url": ATLAS_URL,
            "authority": "City of Philadelphia",
            "access": "interactive public application",
            "use": (
                "property context including deeds, permits, licenses, "
                "violations, and zoning"
            ),
            "relationship_to_primary": "cross-department context",
        },
        {
            "source_id": PHILADOX_SOURCE_ID,
            "route_id": "philadox",
            "name": "Philadox recorded document search",
            "url": PHILADOX_URL,
            "authority": "City of Philadelphia Department of Records",
            "access": (
                "online search and watermarked views; printing and indexed "
                "exports use a subscription"
            ),
            "coverage": "recorded property documents from 1974 to present",
            "use": "inspect the deed, mortgage, release, or easement itself",
            "relationship_to_primary": "underlying recorded instruments",
        },
        {
            "source_id": RECORDS_SOURCE_ID,
            "route_id": "department-of-records-and-city-archives",
            "name": "Recorded-document copy and City Archives route",
            "url": DEED_HELP_URL,
            "authority": "City of Philadelphia Department of Records",
            "access": "online, in person, or mail",
            "coverage": (
                "recorded documents from the late 17th century to present; "
                "pre-1973 property records may route through City Archives"
            ),
            "use": "older deeds and official document copies",
            "relationship_to_primary": "historical and instrument-level route",
        },
        {
            "source_id": PROPERTY_APP_SOURCE_ID,
            "route_id": "property-application",
            "name": "OPA Property application",
            "url": PROPERTY_APP_URL,
            "authority": "City of Philadelphia Office of Property Assessment",
            "access": "interactive public application",
            "use": "human-readable current property detail and verification",
            "relationship_to_primary": "official presentation of OPA data",
        },
    ]


def _client_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "page_size": args.page_size,
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "retry_attempts": args.retry_attempts,
    }


def _result_from_batch(
    query: PublicRecordsQuery,
    batch: TraversalBatch,
    records: Sequence[Mapping[str, Any]],
    warnings: Sequence[str],
) -> PublicRecordsResult:
    if batch.error is not None:
        status = (
            ResultStatus.PARTIAL
            if records
            else ResultStatus.SOURCE_CHANGED
        )
        return PublicRecordsResult.failure(
            query,
            status,
            [batch.error],
            records=records,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=warnings,
    )


def execute(
    args: argparse.Namespace,
    *,
    opa_client: Any | None = None,
    history_client: Any | None = None,
    dor_client: Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    operation = args.command
    try:
        if operation == "alternatives":
            result = PublicRecordsResult.success(
                query,
                _alternatives(),
            )
        elif operation == "history":
            where = _where_history(
                args.query,
                from_year=args.from_year,
                to_year=args.to_year,
            )
            source_client = history_client or PhiladelphiaCartoClient(
                **_client_args(args)
            )
            batch = _traverse_history(
                source_client,
                where=where,
                limit=args.limit,
                cursor=args.cursor,
            )
            records = [
                _normalize_history(row, batch) for row in batch.records
            ]
            result = _result_from_batch(
                query, batch, records, HISTORY_WARNINGS
            )
        elif operation == "parcel-shape":
            where = _where_dor(args.query, args.by)
            source_client = dor_client or PhiladelphiaArcGISClient(
                DOR_MANIFEST,
                **_client_args(args),
            )
            batch = _traverse_arcgis(
                source_client,
                DOR_MANIFEST,
                operation=operation,
                where=where,
                limit=args.limit,
                cursor=args.cursor,
                return_geometry=args.geometry,
            )
            records = [
                _normalize_dor(
                    feature,
                    batch,
                    geometry_requested=args.geometry,
                )
                for feature in batch.records
            ]
            result = _result_from_batch(
                query, batch, records, DOR_WARNINGS
            )
        else:
            where = _where_current(
                operation,
                None if operation == "probe" else args.query,
            )
            source_client = opa_client or PhiladelphiaArcGISClient(
                OPA_MANIFEST,
                **_client_args(args),
            )
            batch = _traverse_arcgis(
                source_client,
                OPA_MANIFEST,
                operation=operation,
                where=where,
                limit=1 if operation == "probe" else args.limit,
                cursor=args.cursor,
                return_geometry=args.geometry,
            )
            records = [
                _normalize_current(
                    feature,
                    batch,
                    geometry_requested=args.geometry,
                )
                for feature in batch.records
            ]
            result = _result_from_batch(
                query, batch, records, CURRENT_WARNINGS
            )
    except PhiladelphiaPropertyError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
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

    result_count = (
        len(result.records)
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else None
    )
    if log_results:
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            result_count,
        )
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Philadelphia property {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Philadelphia property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command == "alternatives":
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "history":
            print(
                f"  {record['native_parcel_id']} | "
                f"{record['assessment_year']} | "
                f"{record['assessment']['market_value']}"
            )
        elif args.command == "parcel-shape":
            print(
                f"  {record['map_registry_number'] or '?'} | "
                f"{record['address']['standardized'] or '?'}"
            )
        else:
            owners = ", ".join(
                owner["raw_name"] for owner in record["owners"]
            )
            print(
                f"  {record['native_parcel_id'] or '?'} | "
                f"{record['situs_address']['raw'] or '?'} | "
                f"{owners or '?'}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_network_args(
    parser: argparse.ArgumentParser,
    *,
    geometry_default: bool = False,
) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional result bound; omitted traverses every native match",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation cursor returned by a prior bounded query",
    )
    parser.add_argument(
        "--geometry",
        action=argparse.BooleanOptionalAction,
        default=geometry_default,
        help="Return source geometry in EPSG:4326",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Transport batch size, bounded by source metadata",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def _add_history_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--from-year",
        type=int,
        help="Include source assessment-year labels at or after this year",
    )
    parser.add_argument(
        "--to-year",
        type=int,
        help="Include source assessment-year labels at or before this year",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional result bound; omitted traverses every native match",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation cursor returned by a prior bounded query",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="CARTO transport batch size; not a collection ceiling",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Philadelphia OPA property, assessment-history, "
            "and DOR parcel-map records"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("owner", "Search OPA assessor-owner observations"),
        ("address", "Search OPA situs-address observations"),
        ("parcel", "Look up an OPA parcel number"),
        ("registry", "Look up an OPA registry number"),
        ("pin", "Look up an OPA PIN"),
        ("objectid", "Look up an OPA ArcGIS object ID"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_network_args(command_parser)

    history = subparsers.add_parser(
        "history",
        help="Fetch OPA annual assessment history for a parcel",
    )
    history.add_argument("query", help="OPA parcel number")
    _add_history_args(history)

    parcel_shape = subparsers.add_parser(
        "parcel-shape",
        help="Search DOR deed-description-derived parcel polygons",
    )
    parcel_shape.add_argument("query")
    parcel_shape.add_argument(
        "--by",
        choices=("registry", "pin", "address", "objectid"),
        default="registry",
    )
    _add_network_args(parcel_shape, geometry_default=True)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="List complementary official property-record routes",
    )
    add_output_args(alternatives)

    probe = subparsers.add_parser(
        "probe",
        help="Query one stable OPA parcel sentinel",
    )
    _add_network_args(probe)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    for field_name in ("limit", "page_size", "timeout", "retry_attempts"):
        value = getattr(args, field_name, None)
        if value is not None and value <= 0:
            parser.error(f"{field_name.replace('_', '-')} must be positive")
    minimum_interval = getattr(args, "minimum_interval", None)
    if minimum_interval is not None and minimum_interval < 0:
        parser.error("minimum-interval must not be negative")
    if (
        args.command == "history"
        and args.from_year is not None
        and args.to_year is not None
        and args.from_year > args.to_year
    ):
        parser.error("from-year must not be after to-year")
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
