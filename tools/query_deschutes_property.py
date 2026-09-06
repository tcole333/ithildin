#!/usr/bin/env python3
"""Query Deschutes County's relationship-aware assessor taxlot service.

The county publishes one taxlot polygon layer and nine related tables in a
single ArcGIS FeatureServer. Eight table joins are declared ArcGIS
relationships. The sales table is deliberately represented separately because
it shares the official service and Taxlot key but is not a declared
relationship.

Usage:
    uv run python tools/query_deschutes_property.py sources
    uv run python tools/query_deschutes_property.py search "VACH" --field owner
    uv run python tools/query_deschutes_property.py parcel 141031B000700 --geometry
    uv run python tools/query_deschutes_property.py probe
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
from typing import Any, Mapping, Sequence

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args
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


SOURCE_ID = "us-or-deschutes-county-taxlots"
SOURCE_NAME = "Deschutes County Taxlots FeatureServer"
PUBLISHER = "Deschutes County Assessor's Office"
SERVICE_URL = (
    "https://services1.arcgis.com/znO8Hz1SuVVohYhZ/arcgis/rest/services/"
    "Taxlots/FeatureServer"
)
SERVICE_ITEM_ID = "901cdd4a5ca24cc3b72cc8e3e0f11f02"
TAXLOT_LAYER_ID = 0
TAXLOT_LAYER_URL = f"{SERVICE_URL}/{TAXLOT_LAYER_ID}"
COUNTY_GEOID = "41017"
STATE_FIPS = "41"
STATE_CODE = "OR"
COUNTY_NAME = "Deschutes County, Oregon"
PROBE_TAXLOT = "141031B000700"
MAX_SERVER_PAGE_SIZE = 2_000
CURSOR_PREFIX = "deschutes-property:v1:"
CURSOR_VERSION = 1
OUTPUT_SCHEMA_VERSION = "deschutes-property-sources/1.0"
PROBE_SCHEMA_VERSION = "deschutes-property-probe/1.0"
SEARCH_FIELDS = (
    "auto",
    "parcel",
    "map",
    "account",
    "address",
    "mailing",
    "owner",
    "sale-party",
)
WARNINGS = (
    "Owner names are current assessor-table observations with their source-native "
    "name and ownership fields preserved.",
    "Sales are a Taxlot-keyed table in the same official service, not one of the "
    "eight declared ArcGIS relationships.",
)


@dataclass(frozen=True)
class TableConfig:
    """Verified schema and relationship contract for one service component."""

    key: str
    table_id: int
    name: str
    join_field: str
    required_fields: tuple[str, ...]
    relationship_id: int | None
    relationship_name: str | None
    cardinality: str | None
    declared_relationship: bool

    @property
    def url(self) -> str:
        return f"{SERVICE_URL}/{self.table_id}"

    @property
    def provenance_kind(self) -> str:
        if self.declared_relationship:
            return "declared_arcgis_relationship"
        return "same_service_taxlot_key_complement"


TAXLOT_FIELDS = (
    "OBJECTID",
    "TAXLOT",
    "TOWNSHIP",
    "RANGE",
    "SECTION",
    "QUARTER",
    "SIXTEENTH",
    "PARCEL",
    "MAPSUP",
    "MAPNUMBER",
    "DIAL",
    "Shape__Area",
    "Shape__Length",
)

TABLES: dict[str, TableConfig] = {
    "account": TableConfig(
        key="account",
        table_id=1,
        name="GIS_ASSESSOR_ACCOUNT",
        join_field="TaxLot",
        required_fields=(
            "OBJECTID",
            "TaxLot",
            "Address",
            "House_Number",
            "Direction",
            "Street_Name",
            "Street_Type",
            "Unit_Number",
            "City",
            "State",
            "Zip",
            "Subdiv_Code",
            "Subdivision",
            "Block",
            "Lot",
            "MA",
            "SA",
            "Percent_Good",
            "LegalLot",
            "UGB",
            "FirePatrol",
            "NH",
        ),
        relationship_id=7,
        relationship_name="General Information for",
        cardinality="esriRelCardinalityOneToOne",
        declared_relationship=True,
    ),
    "dead_numbers": TableConfig(
        key="dead_numbers",
        table_id=2,
        name="GIS_DEADNUMBERS",
        join_field="taxlot",
        required_fields=("OBJECTID", "taxlot", "year", "account_id"),
        relationship_id=0,
        relationship_name="Contains Serial Numbers",
        cardinality="esriRelCardinalityOneToMany",
        declared_relationship=True,
    ),
    "improvements": TableConfig(
        key="improvements",
        table_id=3,
        name="GIS_IMPROVEMENTS",
        join_field="Taxlot",
        required_fields=(
            "OBJECTID",
            "Taxlot",
            "Land_Size_Acres",
            "Year_Appr",
            "Property_Class",
            "impr_ID_1",
            "Stat_Class_1",
            "Stat_Class_Desc_1",
            "Total_Sqft_1",
            "Year_Built_1",
            "Garage_Sqft_1",
            "impr_ID_2",
            "Stat_Class_2",
            "Stat_Class_Desc_2",
            "Total_Sqft_2",
            "Year_Built_2",
            "Garage_Sqft_2",
            "Outcode_1_1",
            "Outcode_1_1_Description",
            "Outcode_1_2",
            "Outcode_1_2_Description",
            "Outcode_1_3",
            "Outcode_1_3_Description",
            "Outcode_2_1",
            "Outcode_2_1_Description",
            "Outcode_2_2",
            "Outcode_2_2_Description",
            "Outcode_2_3",
            "Outcode_2_3_Description",
            "Bedrooms",
            "Bathrooms",
        ),
        relationship_id=6,
        relationship_name="Has Improvement",
        cardinality="esriRelCardinalityOneToOne",
        declared_relationship=True,
    ),
    "mailing": TableConfig(
        key="mailing",
        table_id=4,
        name="GIS_MAILING",
        join_field="MAP_TAXLOT",
        required_fields=(
            "OBJECTID",
            "MAP_TAXLOT",
            "ACCOUNT_ID",
            "OWNER",
            "AGENT",
            "IN_CARE_OF",
            "M_ADDRESS",
            "M_CITYSTZIP",
            "M_CITY",
            "M_STATE",
            "M_ZIP",
        ),
        relationship_id=4,
        relationship_name="Has Mailing Address of",
        cardinality="esriRelCardinalityOneToOne",
        declared_relationship=True,
    ),
    "owners": TableConfig(
        key="owners",
        table_id=5,
        name="GIS_OWNERS",
        join_field="MAP_TAXLOT",
        required_fields=(
            "OBJECTID",
            "MAP_TAXLOT",
            "NAME_TYPE",
            "NAME",
            "OWNERSHIP_TYPE",
            "S_I_TYPE",
            "S_I_NUMBER",
        ),
        relationship_id=3,
        relationship_name="Is Owned by",
        cardinality="esriRelCardinalityOneToMany",
        declared_relationship=True,
    ),
    "property_classes": TableConfig(
        key="property_classes",
        table_id=6,
        name="GIS_PCSTAT",
        join_field="TAXLOT",
        required_fields=(
            "OBJECTID",
            "UniqueID",
            "TAXLOT",
            "PROPERTY_CLASS",
            "STAT_CLASS",
            "STAT_CLASS_DESC",
            "YEAR_BUILT",
            "TOTAL_SQFT",
            "RMV_IMPR",
        ),
        relationship_id=2,
        relationship_name="Has Stat Class or Property Class of",
        cardinality="esriRelCardinalityOneToMany",
        declared_relationship=True,
    ),
    "roll_values": TableConfig(
        key="roll_values",
        table_id=7,
        name="GIS_ROLLVALUES",
        join_field="Taxlot",
        required_fields=(
            "OBJECTID",
            "Taxlot",
            "RMV_Land",
            "RMV_Impr",
            "RMV_Total",
            "AV_Total",
        ),
        relationship_id=5,
        relationship_name="Has Roll Values of",
        cardinality="esriRelCardinalityOneToOne",
        declared_relationship=True,
    ),
    "sales": TableConfig(
        key="sales",
        table_id=8,
        name="GIS_SALES",
        join_field="Taxlot",
        required_fields=(
            "OBJECTID",
            "Taxlot",
            "Book_Page_1",
            "Reject_Code_1",
            "Reject_Description_1",
            "Total_Sales_Price_1",
            "Sales_Date_1",
            "Seller_1",
            "Buyer_1",
            "Book_Page_2",
            "Reject_Code_2",
            "Reject_Description_2",
            "Total_Sales_Price_2",
            "Sales_Date_2",
            "Seller_2",
            "Buyer_2",
        ),
        relationship_id=None,
        relationship_name=None,
        cardinality=None,
        declared_relationship=False,
    ),
    "serial_crossrefs": TableConfig(
        key="serial_crossrefs",
        table_id=9,
        name="GIS_SERIALXREF",
        join_field="taxlot",
        required_fields=(
            "OBJECTID",
            "taxlot",
            "account_id",
            "account_status",
        ),
        relationship_id=1,
        relationship_name="Contains Serial Numbers",
        cardinality="esriRelCardinalityOneToMany",
        declared_relationship=True,
    ),
}

DECLARED_RELATIONSHIPS = tuple(
    table for table in TABLES.values() if table.declared_relationship
)
KEYED_COMPLEMENTS = tuple(
    table for table in TABLES.values() if not table.declared_relationship
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "taxlot_fields": TAXLOT_FIELDS,
        "tables": [
            {
                "key": table.key,
                "table_id": table.table_id,
                "name": table.name,
                "join_field": table.join_field,
                "required_fields": table.required_fields,
                "relationship_id": table.relationship_id,
                "relationship_name": table.relationship_name,
                "cardinality": table.cardinality,
                "declared_relationship": table.declared_relationship,
            }
            for table in TABLES.values()
        ],
    }
)


class DeschutesSelectionError(ValueError):
    """A caller selection or continuation does not match the source contract."""

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


@dataclass(frozen=True)
class CursorState:
    """Opaque query-bound continuation over distinct taxlot identifiers."""

    mode: str
    query_fingerprint: str
    offset: int
    anchor: str
    total_count: int
    schema_fingerprint: str
    snapshot_fingerprint: str | None = None


@dataclass(frozen=True)
class TaxlotBatch:
    """One deterministic page of distinct taxlot identifiers."""

    taxlots: tuple[str, ...]
    next_cursor: str | None
    total_count: int
    schema_fingerprint: str
    errors: tuple[PublicRecordsError, ...] = ()


@dataclass(frozen=True)
class FetchedTable:
    """Complete table rows and source-completeness diagnostics."""

    features: tuple[Mapping[str, Any], ...]
    total_count: int
    schema_fingerprint: str
    errors: tuple[PublicRecordsError, ...] = ()


@dataclass(frozen=True)
class HydrationBundle:
    """Base features plus all relationship-preserving related components."""

    base_by_taxlot: Mapping[str, Mapping[str, Any]]
    components: Mapping[str, Mapping[str, tuple[Mapping[str, Any], ...]]]
    schema_fingerprints: Mapping[str, str]
    source_last_updated: str | None
    errors: tuple[PublicRecordsError, ...] = ()


class DeschutesArcGISClient(ArcGISRESTClient):
    """ArcGIS client exposing service metadata and explicit count/page queries."""

    def __init__(
        self,
        *,
        page_size: int = 1_000,
        timeout: float = 30.0,
        minimum_interval: float = 0.25,
        retry_attempts: int = 3,
        transport: Any = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "page_size": min(page_size, MAX_SERVER_PAGE_SIZE),
            "timeout": timeout,
            "minimum_interval": minimum_interval,
            "retry_policy": RetryPolicy(max_attempts=retry_attempts),
        }
        if transport is not None:
            kwargs["transport"] = transport
        super().__init__(TAXLOT_LAYER_URL, **kwargs)
        self._metadata_cache: dict[int, Mapping[str, Any]] = {}
        self._service_metadata: Mapping[str, Any] | None = None

    @staticmethod
    def _mapping_payload(
        payload: Any,
        *,
        url: str,
        operation: str,
    ) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                f"ArcGIS {operation} response must be a JSON object",
                url=url,
                details={"response_type": type(payload).__name__},
            )
        if "error" in payload:
            raise SourceResponseError(
                f"ArcGIS returned an error during {operation}",
                url=url,
                details={"response": payload.get("error")},
            )
        return payload

    def fetch_service_metadata(self) -> Mapping[str, Any]:
        if self._service_metadata is None:
            payload = self._request_json(SERVICE_URL, params={"f": "json"})
            self._service_metadata = self._mapping_payload(
                payload,
                url=SERVICE_URL,
                operation="service metadata",
            )
        return self._service_metadata

    def fetch_metadata(self, table_id: int) -> Mapping[str, Any]:
        if table_id not in self._metadata_cache:
            url = f"{SERVICE_URL}/{table_id}"
            payload = self._request_json(url, params={"f": "json"})
            self._metadata_cache[table_id] = self._mapping_payload(
                payload,
                url=url,
                operation="layer metadata",
            )
        return self._metadata_cache[table_id]

    def fetch_count(
        self,
        table_id: int,
        where: str,
        *,
        distinct_field: str | None = None,
    ) -> int:
        url = f"{SERVICE_URL}/{table_id}/query"
        params: dict[str, Any] = {
            "where": where,
            "returnCountOnly": "true",
            "f": "json",
        }
        if distinct_field:
            params.update(
                {
                    "outFields": distinct_field,
                    "returnDistinctValues": "true",
                }
            )
        payload = self._request_json(url, params=params)
        data = self._mapping_payload(
            payload,
            url=url,
            operation="count query",
        )
        count = data.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "ArcGIS count response lacks a non-negative integer count",
                url=url,
                details={"count": count, "table_id": table_id},
            )
        return count

    def fetch_page(
        self,
        table_id: int,
        *,
        where: str,
        offset: int,
        record_count: int,
        out_fields: str = "*",
        return_geometry: bool = False,
        distinct_field: str | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        url = f"{SERVICE_URL}/{table_id}/query"
        params: dict[str, Any] = {
            "where": where,
            "outFields": distinct_field or out_fields,
            "orderByFields": (
                f"{distinct_field} ASC" if distinct_field else "OBJECTID ASC"
            ),
            "resultOffset": offset,
            "resultRecordCount": record_count,
            "returnGeometry": "true" if return_geometry else "false",
            "f": "json",
        }
        if return_geometry:
            params["outSR"] = 4326
        if distinct_field:
            params["returnDistinctValues"] = "true"
        payload = self._request_json(url, params=params)
        data = self._mapping_payload(
            payload,
            url=url,
            operation="record query",
        )
        features = data.get("features")
        if not isinstance(features, list):
            raise SourceSchemaError(
                "ArcGIS record response lacks a features array",
                url=url,
                details={"table_id": table_id},
            )
        if any(not isinstance(feature, Mapping) for feature in features):
            raise SourceSchemaError(
                "ArcGIS features array contains a non-object record",
                url=url,
                details={"table_id": table_id},
            )
        return tuple(features)


def _source_metadata() -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_ID,
        name=SOURCE_NAME,
        source_role="county_assessment_relationship_graph",
        base_url=SERVICE_URL,
        dataset_id=SERVICE_ITEM_ID,
        metadata={
            "publisher": PUBLISHER,
            "primary_layer_id": TAXLOT_LAYER_ID,
            "declared_relationship_count": len(DECLARED_RELATIONSHIPS),
            "keyed_complement_count": len(KEYED_COMPLEMENTS),
            "relationship_model": "taxlot_origin_with_related_tables",
        },
    )


def _jurisdiction() -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=COUNTY_GEOID,
        name=COUNTY_NAME,
        state_code=STATE_CODE,
        county_fips=COUNTY_GEOID,
        metadata={
            "state_fips": STATE_FIPS,
            "county_fips_suffix": COUNTY_GEOID[-3:],
        },
    )


def _build_query(
    *,
    operation: str,
    selector: str | None,
    search_field: str | None,
    limit: int | None,
    cursor: str | None,
    geometry: bool,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {
        "selector": selector,
        "search_field": search_field,
        "return_geometry": geometry,
        "related_components": list(TABLES),
    }
    return PublicRecordsQuery(
        source=_source_metadata(),
        jurisdiction=_jurisdiction(),
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "pagination": "count_driven_distinct_taxlot_order",
                "cursor_anchor": "source_native_taxlot",
                "relationship_hydration": "count_driven_component_tables",
                "access_decision": dict(access_decision or {}),
            },
        ),
    )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _arcgis_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                .date()
                .isoformat()
            )
        except (OverflowError, OSError, ValueError):
            return None
    text = _clean_text(value)
    if not text:
        return None
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _arcgis_timestamp(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return (
            datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        return None


def _attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError("ArcGIS feature lacks an attributes object")
    return attributes


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _normalize_taxlot(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        raise ValueError("source record lacks a taxlot identifier")
    return text.upper()


def _account_selector(value: str) -> str:
    text = value.strip()
    if not re.fullmatch(r"\d+(?:\.0+)?", text):
        raise DeschutesSelectionError(
            "invalid_account_selector",
            "account search requires a numeric source account identifier",
            status=ResultStatus.SOURCE_CHANGED,
            details={"selector": value},
        )
    return str(int(float(text)))


def _auto_field(selector: str) -> str:
    if re.match(r"^\d+\s", selector.strip()):
        return "address"
    candidate = "".join(selector.strip().upper().split())
    if re.fullmatch(r"\d{1,10}", candidate):
        return "account"
    if re.fullmatch(r"[0-9A-Z]{11,20}", candidate):
        return "parcel"
    return "owner"


@dataclass(frozen=True)
class SearchPlan:
    """Source-native index table and distinct parcel key for a search."""

    field: str
    table_id: int
    distinct_field: str
    where: str


def _search_plan(operation: str, selector: str, search_field: str) -> SearchPlan:
    field = _auto_field(selector) if search_field == "auto" else search_field
    escaped = _sql_literal(selector.strip().upper())
    if operation == "parcel":
        exact = _sql_literal("".join(selector.strip().upper().split()))
        return SearchPlan(
            field="parcel",
            table_id=TAXLOT_LAYER_ID,
            distinct_field="TAXLOT",
            where=(
                f"TAXLOT = '{exact}' OR MAPNUMBER = '{exact}' "
                f"OR PARCEL = '{exact}'"
            ),
        )
    if field == "parcel":
        return SearchPlan(
            field=field,
            table_id=TAXLOT_LAYER_ID,
            distinct_field="TAXLOT",
            where=(
                f"UPPER(TAXLOT) LIKE '%{escaped}%' "
                f"OR UPPER(PARCEL) LIKE '%{escaped}%'"
            ),
        )
    if field == "map":
        return SearchPlan(
            field=field,
            table_id=TAXLOT_LAYER_ID,
            distinct_field="TAXLOT",
            where=f"UPPER(MAPNUMBER) LIKE '%{escaped}%'",
        )
    if field == "owner":
        return SearchPlan(
            field=field,
            table_id=TABLES["owners"].table_id,
            distinct_field=TABLES["owners"].join_field,
            where=f"UPPER(NAME) LIKE '%{escaped}%'",
        )
    if field == "address":
        return SearchPlan(
            field=field,
            table_id=TABLES["account"].table_id,
            distinct_field=TABLES["account"].join_field,
            where=(
                f"UPPER(Address) LIKE '%{escaped}%' "
                f"OR UPPER(Street_Name) LIKE '%{escaped}%'"
            ),
        )
    if field == "mailing":
        return SearchPlan(
            field=field,
            table_id=TABLES["mailing"].table_id,
            distinct_field=TABLES["mailing"].join_field,
            where=(
                f"UPPER(M_ADDRESS) LIKE '%{escaped}%' "
                f"OR UPPER(M_CITYSTZIP) LIKE '%{escaped}%'"
            ),
        )
    if field == "sale-party":
        return SearchPlan(
            field=field,
            table_id=TABLES["sales"].table_id,
            distinct_field=TABLES["sales"].join_field,
            where=(
                f"UPPER(Seller_1) LIKE '%{escaped}%' "
                f"OR UPPER(Buyer_1) LIKE '%{escaped}%' "
                f"OR UPPER(Seller_2) LIKE '%{escaped}%' "
                f"OR UPPER(Buyer_2) LIKE '%{escaped}%'"
            ),
        )
    if field == "account":
        account_id = _account_selector(selector)
        return SearchPlan(
            field=field,
            table_id=-1,
            distinct_field="taxlot",
            where=f"account_id = {account_id}",
        )
    raise DeschutesSelectionError(
        "invalid_search_field",
        f"unsupported Deschutes property search field {field!r}",
        details={"search_field": field},
    )


def _required_fields(table_id: int) -> tuple[str, ...]:
    if table_id == TAXLOT_LAYER_ID:
        return TAXLOT_FIELDS
    for table in TABLES.values():
        if table.table_id == table_id:
            return table.required_fields
    raise ValueError(f"unknown Deschutes table id {table_id}")


def _expected_name(table_id: int) -> str:
    if table_id == TAXLOT_LAYER_ID:
        return "Taxlot"
    for table in TABLES.values():
        if table.table_id == table_id:
            return table.name
    raise ValueError(f"unknown Deschutes table id {table_id}")


def _validate_relationship_contracts(metadata: Mapping[str, Any]) -> None:
    relationships = metadata.get("relationships")
    if not isinstance(relationships, list):
        raise SourceSchemaError(
            "Taxlot metadata lacks declared relationships",
            url=TAXLOT_LAYER_URL,
        )
    observed: dict[int, Mapping[str, Any]] = {}
    for relationship in relationships:
        if not isinstance(relationship, Mapping):
            continue
        relationship_id = relationship.get("id")
        if isinstance(relationship_id, int):
            observed[relationship_id] = relationship
    for table in DECLARED_RELATIONSHIPS:
        relationship = observed.get(table.relationship_id)
        expected = {
            "name": table.relationship_name,
            "relatedTableId": table.table_id,
            "cardinality": table.cardinality,
            "role": "esriRelRoleOrigin",
            "keyField": "TAXLOT",
        }
        if relationship is None or any(
            relationship.get(key) != value for key, value in expected.items()
        ):
            raise SourceSchemaError(
                "Taxlot relationship contract changed",
                url=TAXLOT_LAYER_URL,
                details={
                    "relationship_id": table.relationship_id,
                    "expected": expected,
                    "observed": dict(relationship or {}),
                },
            )
    sales_relationships = [
        relationship
        for relationship in relationships
        if isinstance(relationship, Mapping)
        and relationship.get("relatedTableId") == TABLES["sales"].table_id
    ]
    if sales_relationships:
        raise SourceSchemaError(
            "Sales table relationship status changed",
            url=TAXLOT_LAYER_URL,
            details={"observed": sales_relationships},
        )


def _metadata_schema(
    client: Any,
    table_id: int,
) -> tuple[str, int, str | None]:
    metadata = client.fetch_metadata(table_id)
    if metadata.get("id") != table_id or metadata.get("name") != _expected_name(
        table_id
    ):
        raise SourceSchemaError(
            "ArcGIS table identity changed",
            url=f"{SERVICE_URL}/{table_id}",
            details={
                "expected_id": table_id,
                "expected_name": _expected_name(table_id),
                "observed_id": metadata.get("id"),
                "observed_name": metadata.get("name"),
            },
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list):
        raise SourceSchemaError(
            "ArcGIS metadata lacks a fields array",
            url=f"{SERVICE_URL}/{table_id}",
        )
    field_names = {
        field.get("name")
        for field in fields
        if isinstance(field, Mapping) and isinstance(field.get("name"), str)
    }
    missing = sorted(set(_required_fields(table_id)) - field_names)
    if missing:
        raise SourceSchemaError(
            "ArcGIS component is missing required fields",
            url=f"{SERVICE_URL}/{table_id}",
            details={"table_id": table_id, "missing_fields": missing},
        )
    if metadata.get("objectIdField") != "OBJECTID":
        raise SourceSchemaError(
            "ArcGIS component OBJECTID contract changed",
            url=f"{SERVICE_URL}/{table_id}",
            details={"objectIdField": metadata.get("objectIdField")},
        )
    if table_id == TAXLOT_LAYER_ID:
        _validate_relationship_contracts(metadata)
    maximum = metadata.get("maxRecordCount")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        maximum = MAX_SERVER_PAGE_SIZE
    schema = arcgis_declared_schema(fields)
    updated = None
    editing_info = metadata.get("editingInfo")
    if isinstance(editing_info, Mapping):
        updated = _arcgis_timestamp(editing_info.get("dataLastEditDate"))
    return schema_fingerprint(schema), min(maximum, MAX_SERVER_PAGE_SIZE), updated


def _criteria_fingerprint(
    *,
    mode: str,
    table_id: int,
    distinct_field: str,
    where: str,
    geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "mode": mode,
            "table_id": table_id,
            "distinct_field": distinct_field,
            "where": where,
            "geometry": geometry,
            "components": list(TABLES),
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "m": state.mode,
        "q": state.query_fingerprint,
        "o": state.offset,
        "a": state.anchor,
        "n": state.total_count,
        "s": state.schema_fingerprint,
        "d": state.snapshot_fingerprint,
    }
    token = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + token.rstrip("=")


def _decode_cursor(
    cursor: str | None,
    *,
    expected_query_fingerprint: str,
    expected_mode: str,
) -> CursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise DeschutesSelectionError(
            "invalid_cursor",
            "cursor must be a Deschutes property continuation returned by this tool",
            details={"cursor": cursor},
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        values = json.loads(
            base64.urlsafe_b64decode(token + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DeschutesSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(values, Mapping) or values.get("v") != CURSOR_VERSION:
        raise DeschutesSelectionError(
            "invalid_cursor",
            "cursor version or payload is invalid",
        )
    if values.get("q") != expected_query_fingerprint:
        raise DeschutesSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different Deschutes property search parameters",
            details={
                "cursor_query_fingerprint": values.get("q"),
                "expected_query_fingerprint": expected_query_fingerprint,
            },
        )
    if values.get("m") != expected_mode:
        raise DeschutesSelectionError(
            "cursor_mode_mismatch",
            "cursor belongs to a different Deschutes pagination mode",
            details={
                "cursor_mode": values.get("m"),
                "expected_mode": expected_mode,
            },
        )
    offset = values.get("o")
    total_count = values.get("n")
    anchor = values.get("a")
    schema_value = values.get("s")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset <= 0
        or isinstance(total_count, bool)
        or not isinstance(total_count, int)
        or total_count < 0
        or not isinstance(anchor, str)
        or not anchor
        or not isinstance(schema_value, str)
        or not schema_value
    ):
        raise DeschutesSelectionError(
            "invalid_cursor",
            "cursor offset, anchor, count, or schema is invalid",
        )
    snapshot = values.get("d")
    if snapshot is not None and not isinstance(snapshot, str):
        raise DeschutesSelectionError(
            "invalid_cursor",
            "cursor snapshot fingerprint is invalid",
        )
    return CursorState(
        mode=expected_mode,
        query_fingerprint=expected_query_fingerprint,
        offset=offset,
        anchor=anchor,
        total_count=total_count,
        schema_fingerprint=schema_value,
        snapshot_fingerprint=snapshot,
    )


def _pagination_error(
    code: str,
    message: str,
    **details: Any,
) -> PublicRecordsError:
    return PublicRecordsError(
        code=code,
        message=message,
        category="pagination",
        retryable=False,
        details=details,
    )


def _distinct_taxlot(
    feature: Mapping[str, Any],
    field: str,
) -> str:
    return _normalize_taxlot(_attributes(feature).get(field))


def _fetch_distinct_slice(
    client: Any,
    plan: SearchPlan,
    *,
    limit: int,
    cursor: str | None,
    geometry: bool,
) -> TaxlotBatch:
    mode = f"table:{plan.table_id}:{plan.distinct_field}"
    criteria = _criteria_fingerprint(
        mode=mode,
        table_id=plan.table_id,
        distinct_field=plan.distinct_field,
        where=plan.where,
        geometry=geometry,
    )
    cursor_state = _decode_cursor(
        cursor,
        expected_query_fingerprint=criteria,
        expected_mode=mode,
    )
    current_schema, server_page_size, _updated = _metadata_schema(
        client, plan.table_id
    )
    if (
        cursor_state is not None
        and cursor_state.schema_fingerprint != current_schema
    ):
        raise DeschutesSelectionError(
            "cursor_schema_mismatch",
            "ArcGIS index schema changed since the continuation was issued",
            details={
                "cursor_schema_fingerprint": cursor_state.schema_fingerprint,
                "current_schema_fingerprint": current_schema,
            },
        )
    start_count = client.fetch_count(
        plan.table_id,
        plan.where,
        distinct_field=plan.distinct_field,
    )
    offset = cursor_state.offset if cursor_state else 0
    if offset > start_count:
        raise DeschutesSelectionError(
            "cursor_out_of_range",
            "cursor offset exceeds the current distinct taxlot count",
            details={"cursor_offset": offset, "source_count": start_count},
        )
    errors: list[PublicRecordsError] = []
    previous_taxlot: str | None = None
    safe_to_resume = True
    if cursor_state is not None:
        boundary = client.fetch_page(
            plan.table_id,
            where=plan.where,
            offset=offset - 1,
            record_count=1,
            distinct_field=plan.distinct_field,
        )
        if len(boundary) != 1:
            raise DeschutesSelectionError(
                "cursor_snapshot_changed",
                "continuation boundary no longer exists at the cursor offset",
                details={"cursor_offset": offset, "boundary_rows": len(boundary)},
            )
        observed_anchor = _distinct_taxlot(boundary[0], plan.distinct_field)
        if observed_anchor != cursor_state.anchor:
            raise DeschutesSelectionError(
                "cursor_snapshot_changed",
                "distinct taxlot ordering changed at the continuation boundary",
                details={
                    "expected_anchor": cursor_state.anchor,
                    "observed_anchor": observed_anchor,
                    "cursor_offset": offset,
                },
            )
        previous_taxlot = observed_anchor
        if cursor_state.total_count != start_count:
            errors.append(
                _pagination_error(
                    "count_changed_since_cursor",
                    "Distinct taxlot count changed since the cursor was issued",
                    cursor_count=cursor_state.total_count,
                    current_count=start_count,
                )
            )
            safe_to_resume = False
    page_size = min(
        int(getattr(client, "page_size", server_page_size)),
        server_page_size,
    )
    collected: list[str] = []
    seen: set[str] = set()
    while offset < start_count and len(collected) < limit:
        requested = min(page_size, limit - len(collected))
        try:
            page = client.fetch_page(
                plan.table_id,
                where=plan.where,
                offset=offset,
                record_count=requested,
                distinct_field=plan.distinct_field,
            )
        except PublicRecordsHTTPError as error:
            if not collected:
                raise
            errors.append(error.to_contract_error())
            safe_to_resume = False
            break
        if not page:
            errors.append(
                _pagination_error(
                    "pagination_no_progress",
                    "ArcGIS returned no distinct taxlots before its count was reached",
                    offset=offset,
                    snapshot_count=start_count,
                )
            )
            safe_to_resume = False
            break
        if len(page) > requested:
            errors.append(
                _pagination_error(
                    "pagination_page_oversized",
                    "ArcGIS returned more distinct taxlots than requested",
                    requested=requested,
                    returned=len(page),
                    offset=offset,
                )
            )
            safe_to_resume = False
            break
        page_valid = True
        for feature in page:
            taxlot = _distinct_taxlot(feature, plan.distinct_field)
            if (
                taxlot in seen
                or (previous_taxlot is not None and taxlot <= previous_taxlot)
            ):
                errors.append(
                    _pagination_error(
                        "pagination_repeat_or_reorder",
                        "ArcGIS repeated or reordered a distinct taxlot",
                        taxlot=taxlot,
                        previous_taxlot=previous_taxlot,
                        offset=offset,
                    )
                )
                safe_to_resume = False
                page_valid = False
                break
            seen.add(taxlot)
            previous_taxlot = taxlot
            collected.append(taxlot)
        if not page_valid:
            break
        offset += len(page)
    try:
        end_count = client.fetch_count(
            plan.table_id,
            plan.where,
            distinct_field=plan.distinct_field,
        )
    except PublicRecordsHTTPError as error:
        if not collected:
            raise
        errors.append(error.to_contract_error())
        safe_to_resume = False
        end_count = start_count
    if end_count != start_count:
        errors.append(
            _pagination_error(
                "count_changed_during_traversal",
                "Distinct taxlot count changed during pagination",
                initial_count=start_count,
                final_count=end_count,
            )
        )
        safe_to_resume = False
    next_cursor = None
    if (
        safe_to_resume
        and collected
        and len(collected) >= limit
        and offset < end_count
        and previous_taxlot is not None
    ):
        next_cursor = _encode_cursor(
            CursorState(
                mode=mode,
                query_fingerprint=criteria,
                offset=offset,
                anchor=previous_taxlot,
                total_count=end_count,
                schema_fingerprint=current_schema,
            )
        )
    return TaxlotBatch(
        taxlots=tuple(collected),
        next_cursor=next_cursor,
        total_count=end_count,
        schema_fingerprint=current_schema,
        errors=tuple(errors),
    )


def _feature_oid(feature: Mapping[str, Any]) -> int:
    value = _attributes(feature).get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SourceSchemaError(
            "ArcGIS feature lacks a numeric OBJECTID",
            url=SERVICE_URL,
            details={"object_id": value},
        )
    integer = int(value)
    if integer < 0 or integer != value:
        raise SourceSchemaError(
            "ArcGIS feature OBJECTID is not a non-negative integer",
            url=SERVICE_URL,
            details={"object_id": value},
        )
    return integer


def _fetch_complete(
    client: Any,
    table_id: int,
    *,
    where: str,
    return_geometry: bool = False,
) -> FetchedTable:
    current_schema, server_page_size, _updated = _metadata_schema(client, table_id)
    start_count = client.fetch_count(table_id, where)
    page_size = min(
        int(getattr(client, "page_size", server_page_size)),
        server_page_size,
    )
    offset = 0
    previous_oid: int | None = None
    seen: set[int] = set()
    collected: list[Mapping[str, Any]] = []
    errors: list[PublicRecordsError] = []
    while offset < start_count:
        requested = min(page_size, start_count - offset)
        try:
            page = client.fetch_page(
                table_id,
                where=where,
                offset=offset,
                record_count=requested,
                return_geometry=return_geometry,
            )
        except PublicRecordsHTTPError as error:
            if not collected:
                raise
            errors.append(error.to_contract_error())
            break
        if not page:
            errors.append(
                _pagination_error(
                    "component_pagination_no_progress",
                    "ArcGIS returned no component rows before its count was reached",
                    table_id=table_id,
                    offset=offset,
                    snapshot_count=start_count,
                )
            )
            break
        valid_page = True
        for feature in page:
            oid = _feature_oid(feature)
            if oid in seen or (previous_oid is not None and oid <= previous_oid):
                errors.append(
                    _pagination_error(
                        "component_repeat_or_reorder",
                        "ArcGIS repeated or reordered a component row",
                        table_id=table_id,
                        object_id=oid,
                        previous_object_id=previous_oid,
                    )
                )
                valid_page = False
                break
            seen.add(oid)
            previous_oid = oid
            collected.append(feature)
        if not valid_page:
            break
        offset += len(page)
    try:
        end_count = client.fetch_count(table_id, where)
    except PublicRecordsHTTPError as error:
        if not collected:
            raise
        errors.append(error.to_contract_error())
        end_count = start_count
    if end_count != start_count:
        errors.append(
            _pagination_error(
                "component_count_changed",
                "ArcGIS component count changed during relationship hydration",
                table_id=table_id,
                initial_count=start_count,
                final_count=end_count,
            )
        )
    if len(collected) != start_count and not errors:
        errors.append(
            _pagination_error(
                "component_count_mismatch",
                "ArcGIS component traversal did not return its reported count",
                table_id=table_id,
                reported_count=start_count,
                returned_count=len(collected),
            )
        )
    return FetchedTable(
        features=tuple(collected),
        total_count=end_count,
        schema_fingerprint=current_schema,
        errors=tuple(errors),
    )


def _fetch_all_distinct(
    client: Any,
    plan: SearchPlan,
) -> tuple[tuple[str, ...], str, tuple[PublicRecordsError, ...]]:
    current_schema, server_page_size, _updated = _metadata_schema(
        client, plan.table_id
    )
    start_count = client.fetch_count(
        plan.table_id,
        plan.where,
        distinct_field=plan.distinct_field,
    )
    page_size = min(
        int(getattr(client, "page_size", server_page_size)),
        server_page_size,
    )
    offset = 0
    previous: str | None = None
    collected: list[str] = []
    errors: list[PublicRecordsError] = []
    while offset < start_count:
        requested = min(page_size, start_count - offset)
        try:
            page = client.fetch_page(
                plan.table_id,
                where=plan.where,
                offset=offset,
                record_count=requested,
                distinct_field=plan.distinct_field,
            )
        except PublicRecordsHTTPError as error:
            if not collected:
                raise
            errors.append(error.to_contract_error())
            break
        if not page:
            errors.append(
                _pagination_error(
                    "composite_pagination_no_progress",
                    "Account index returned no taxlots before its count was reached",
                    table_id=plan.table_id,
                    offset=offset,
                    snapshot_count=start_count,
                )
            )
            break
        valid = True
        for feature in page:
            taxlot = _distinct_taxlot(feature, plan.distinct_field)
            if previous is not None and taxlot <= previous:
                errors.append(
                    _pagination_error(
                        "composite_repeat_or_reorder",
                        "Account index repeated or reordered a taxlot",
                        table_id=plan.table_id,
                        taxlot=taxlot,
                        previous_taxlot=previous,
                    )
                )
                valid = False
                break
            collected.append(taxlot)
            previous = taxlot
        if not valid:
            break
        offset += len(page)
    end_count = client.fetch_count(
        plan.table_id,
        plan.where,
        distinct_field=plan.distinct_field,
    )
    if end_count != start_count:
        errors.append(
            _pagination_error(
                "composite_count_changed",
                "Account index count changed during pagination",
                table_id=plan.table_id,
                initial_count=start_count,
                final_count=end_count,
            )
        )
    return tuple(collected), current_schema, tuple(errors)


def _fetch_account_slice(
    client: Any,
    selector: str,
    *,
    limit: int,
    cursor: str | None,
    geometry: bool,
) -> TaxlotBatch:
    account_id = _account_selector(selector)
    plans = (
        SearchPlan(
            field="account",
            table_id=TABLES["serial_crossrefs"].table_id,
            distinct_field=TABLES["serial_crossrefs"].join_field,
            where=f"account_id = {account_id}",
        ),
        SearchPlan(
            field="account",
            table_id=TABLES["dead_numbers"].table_id,
            distinct_field=TABLES["dead_numbers"].join_field,
            where=f"account_id = {account_id}",
        ),
    )
    mode = "account-union:active-and-retired"
    criteria = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "mode": mode,
            "account_id": account_id,
            "geometry": geometry,
            "components": [
                {
                    "table_id": plan.table_id,
                    "field": plan.distinct_field,
                    "where": plan.where,
                }
                for plan in plans
            ],
        }
    )
    active, active_schema, active_errors = _fetch_all_distinct(client, plans[0])
    retired, retired_schema, retired_errors = _fetch_all_distinct(client, plans[1])
    taxlots = tuple(sorted(set(active) | set(retired)))
    combined_schema = sha256_fingerprint(
        {
            "active": active_schema,
            "retired": retired_schema,
        }
    )
    snapshot = sha256_fingerprint(
        {
            "active": active,
            "retired": retired,
            "union": taxlots,
        }
    )
    cursor_state = _decode_cursor(
        cursor,
        expected_query_fingerprint=criteria,
        expected_mode=mode,
    )
    offset = cursor_state.offset if cursor_state else 0
    if cursor_state is not None:
        if cursor_state.schema_fingerprint != combined_schema:
            raise DeschutesSelectionError(
                "cursor_schema_mismatch",
                "Account index schema changed since the continuation was issued",
            )
        if (
            cursor_state.total_count != len(taxlots)
            or cursor_state.snapshot_fingerprint != snapshot
            or offset > len(taxlots)
            or taxlots[offset - 1] != cursor_state.anchor
        ):
            raise DeschutesSelectionError(
                "cursor_snapshot_changed",
                "Active or retired account matches changed since continuation",
                details={
                    "cursor_count": cursor_state.total_count,
                    "current_count": len(taxlots),
                    "cursor_offset": offset,
                },
            )
    selected = taxlots[offset : offset + limit]
    next_offset = offset + len(selected)
    next_cursor = None
    if selected and next_offset < len(taxlots):
        next_cursor = _encode_cursor(
            CursorState(
                mode=mode,
                query_fingerprint=criteria,
                offset=next_offset,
                anchor=selected[-1],
                total_count=len(taxlots),
                schema_fingerprint=combined_schema,
                snapshot_fingerprint=snapshot,
            )
        )
    return TaxlotBatch(
        taxlots=selected,
        next_cursor=next_cursor,
        total_count=len(taxlots),
        schema_fingerprint=combined_schema,
        errors=active_errors + retired_errors,
    )


def _taxlot_where(field: str, taxlots: Sequence[str]) -> str:
    values = ", ".join(f"'{_sql_literal(value)}'" for value in taxlots)
    return f"{field} IN ({values})"


def _chunks(values: Sequence[str], size: int = 100) -> Sequence[Sequence[str]]:
    return tuple(values[index : index + size] for index in range(0, len(values), size))


def _table_updated_at(client: Any, table_id: int) -> str | None:
    metadata = client.fetch_metadata(table_id)
    editing = metadata.get("editingInfo")
    if not isinstance(editing, Mapping):
        return None
    return _arcgis_timestamp(editing.get("dataLastEditDate"))


def _hydrate(
    client: Any,
    taxlots: Sequence[str],
    *,
    geometry: bool,
) -> HydrationBundle:
    if not taxlots:
        return HydrationBundle({}, {}, {}, None)
    selected = tuple(dict.fromkeys(taxlots))
    selected_set = set(selected)
    errors: list[PublicRecordsError] = []
    schemas: dict[str, str] = {}
    updated_values: list[str] = []

    base_features: list[Mapping[str, Any]] = []
    for chunk in _chunks(selected):
        fetched = _fetch_complete(
            client,
            TAXLOT_LAYER_ID,
            where=_taxlot_where("TAXLOT", chunk),
            return_geometry=geometry,
        )
        base_features.extend(fetched.features)
        errors.extend(fetched.errors)
        schemas["taxlot"] = fetched.schema_fingerprint
    base_by_taxlot: dict[str, Mapping[str, Any]] = {}
    for feature in base_features:
        taxlot = _normalize_taxlot(_attributes(feature).get("TAXLOT"))
        if taxlot not in selected_set:
            errors.append(
                PublicRecordsError(
                    code="base_join_outside_selection",
                    message="Taxlot query returned a parcel outside the selected keys",
                    category="source_schema",
                    details={"taxlot": taxlot},
                )
            )
            continue
        if taxlot in base_by_taxlot:
            errors.append(
                PublicRecordsError(
                    code="duplicate_taxlot_polygon",
                    message="Taxlot layer returned more than one feature for a taxlot key",
                    category="source_schema",
                    details={"taxlot": taxlot},
                )
            )
            continue
        base_by_taxlot[taxlot] = feature
    for taxlot in selected:
        if taxlot not in base_by_taxlot:
            errors.append(
                PublicRecordsError(
                    code="taxlot_polygon_missing",
                    message="A search index taxlot has no matching polygon feature",
                    category="source_schema",
                    details={"taxlot": taxlot},
                )
            )
    base_updated = _table_updated_at(client, TAXLOT_LAYER_ID)
    if base_updated:
        updated_values.append(base_updated)

    components: dict[str, dict[str, tuple[Mapping[str, Any], ...]]] = {}
    for table in TABLES.values():
        component_features: list[Mapping[str, Any]] = []
        component_errors: list[PublicRecordsError] = []
        component_schema: str | None = None
        try:
            for chunk in _chunks(selected):
                fetched = _fetch_complete(
                    client,
                    table.table_id,
                    where=_taxlot_where(table.join_field, chunk),
                )
                component_features.extend(fetched.features)
                component_errors.extend(fetched.errors)
                component_schema = fetched.schema_fingerprint
            updated = _table_updated_at(client, table.table_id)
            if updated:
                updated_values.append(updated)
        except PublicRecordsHTTPError as error:
            component_errors.append(error.to_contract_error())
        if component_schema:
            schemas[table.key] = component_schema
        errors.extend(component_errors)
        grouped: dict[str, list[Mapping[str, Any]]] = {
            taxlot: [] for taxlot in selected
        }
        for feature in component_features:
            try:
                taxlot = _normalize_taxlot(
                    _attributes(feature).get(table.join_field)
                )
            except ValueError as error:
                errors.append(
                    PublicRecordsError(
                        code="component_join_key_missing",
                        message=str(error),
                        category="source_schema",
                        details={"component": table.key},
                    )
                )
                continue
            if taxlot not in selected_set:
                errors.append(
                    PublicRecordsError(
                        code="component_join_outside_selection",
                        message="Related table returned a taxlot outside the selected keys",
                        category="source_schema",
                        details={"component": table.key, "taxlot": taxlot},
                    )
                )
                continue
            grouped[taxlot].append(feature)
        frozen_grouped: dict[str, tuple[Mapping[str, Any], ...]] = {}
        for taxlot, rows in grouped.items():
            ordered = tuple(sorted(rows, key=_feature_oid))
            frozen_grouped[taxlot] = ordered
            if (
                table.cardinality == "esriRelCardinalityOneToOne"
                and len(ordered) > 1
            ):
                errors.append(
                    PublicRecordsError(
                        code="declared_cardinality_exceeded",
                        message="Related table exceeds its declared one-to-one cardinality",
                        category="source_schema",
                        details={
                            "component": table.key,
                            "taxlot": taxlot,
                            "record_count": len(ordered),
                            "relationship_id": table.relationship_id,
                        },
                    )
                )
        components[table.key] = frozen_grouped
    return HydrationBundle(
        base_by_taxlot=base_by_taxlot,
        components=components,
        schema_fingerprints=schemas,
        source_last_updated=max(updated_values) if updated_values else None,
        errors=tuple(errors),
    )


def _relationship_contract(table: TableConfig) -> dict[str, Any]:
    return {
        "component": table.key,
        "table_id": table.table_id,
        "table_name": table.name,
        "provenance_kind": table.provenance_kind,
        "declared_relationship": table.declared_relationship,
        "relationship_id": table.relationship_id,
        "relationship_name": table.relationship_name,
        "declared_cardinality": table.cardinality,
        "origin_layer_id": TAXLOT_LAYER_ID,
        "origin_key": "TAXLOT",
        "destination_key": table.join_field,
    }


def _component_projection(
    table: TableConfig,
    features: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    contract = _relationship_contract(table)
    contract.update(
        {
            "record_count": len(features),
            "records": [dict(_attributes(feature)) for feature in features],
        }
    )
    return contract


def _address(
    attributes: Mapping[str, Any] | None,
    *,
    mailing: bool,
) -> dict[str, Any] | None:
    if not attributes:
        return None
    if mailing:
        raw = _clean_text(attributes.get("M_ADDRESS"))
        city = _clean_text(attributes.get("M_CITY"))
        state = _clean_text(attributes.get("M_STATE"))
        postal = _clean_text(attributes.get("M_ZIP"))
        if not any((raw, city, state, postal)):
            return None
        return {
            "raw": raw,
            "raw_address": raw,
            "city": city,
            "state": state,
            "postal_code": postal,
            "country": "US",
            "city_state_zip_raw": _clean_text(attributes.get("M_CITYSTZIP")),
            "in_care_of": _clean_text(attributes.get("IN_CARE_OF")),
            "agent": _clean_text(attributes.get("AGENT")),
            "account_id": _clean_text(attributes.get("ACCOUNT_ID")),
        }
    raw = _clean_text(attributes.get("Address"))
    city = _clean_text(attributes.get("City"))
    state = _clean_text(attributes.get("State"))
    postal = _clean_text(attributes.get("Zip"))
    if not any((raw, city, state, postal)):
        return None
    return {
        "raw": raw,
        "raw_address": raw,
        "house_number": _clean_text(attributes.get("House_Number")),
        "direction": _clean_text(attributes.get("Direction")),
        "street_name": _clean_text(attributes.get("Street_Name")),
        "street_type": _clean_text(attributes.get("Street_Type")),
        "unit_number": _clean_text(attributes.get("Unit_Number")),
        "city": city,
        "state": state,
        "postal_code": postal,
        "country": "US",
    }


def _owners(features: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for feature in features:
        attributes = _attributes(feature)
        raw_name = _clean_text(attributes.get("NAME"))
        if not raw_name:
            continue
        values.append(
            {
                "raw_name": raw_name,
                "role": "assessor_owner",
                "assertion_type": "assessment_roll",
                "confidence": "high",
                "name_type": _clean_text(attributes.get("NAME_TYPE")),
                "ownership_type": _clean_text(attributes.get("OWNERSHIP_TYPE")),
                "source_interest_type": _clean_text(attributes.get("S_I_TYPE")),
                "source_interest_number": _clean_text(
                    attributes.get("S_I_NUMBER")
                ),
            }
        )
    return values


def _assessment(
    roll_features: Sequence[Mapping[str, Any]],
    improvement_features: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    if not roll_features:
        return None
    values = _attributes(roll_features[0])
    improvements = _attributes(improvement_features[0]) if improvement_features else {}
    return {
        "land_value": _number(values.get("RMV_Land")),
        "improvement_value": _number(values.get("RMV_Impr")),
        "parcel_value": _number(values.get("RMV_Total")),
        "assessed_value": _number(values.get("AV_Total")),
        "assessment_class": _clean_text(improvements.get("Property_Class")),
        "currency": "USD",
        "roll_period": "current_published_roll",
    }


def _improvement_slots(
    improvement_features: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for feature in improvement_features:
        attributes = _attributes(feature)
        for index in (1, 2):
            improvement_id = _number(attributes.get(f"impr_ID_{index}"))
            if improvement_id is None and not any(
                _clean_text(attributes.get(f"{field}_{index}"))
                for field in (
                    "Stat_Class",
                    "Stat_Class_Desc",
                    "Year_Built",
                )
            ):
                continue
            slots.append(
                {
                    "slot": index,
                    "improvement_id": improvement_id,
                    "stat_class": _clean_text(
                        attributes.get(f"Stat_Class_{index}")
                    ),
                    "description": _clean_text(
                        attributes.get(f"Stat_Class_Desc_{index}")
                    ),
                    "total_square_feet": _number(
                        attributes.get(f"Total_Sqft_{index}")
                    ),
                    "year_built": _clean_text(
                        attributes.get(f"Year_Built_{index}")
                    ),
                    "garage_square_feet": _number(
                        attributes.get(f"Garage_Sqft_{index}")
                    ),
                    "outcodes": [
                        {
                            "code": _clean_text(
                                attributes.get(f"Outcode_{index}_{outcode}")
                            ),
                            "description": _clean_text(
                                attributes.get(
                                    f"Outcode_{index}_{outcode}_Description"
                                )
                            ),
                        }
                        for outcode in (1, 2, 3)
                        if _clean_text(
                            attributes.get(f"Outcode_{index}_{outcode}")
                        )
                        or _clean_text(
                            attributes.get(
                                f"Outcode_{index}_{outcode}_Description"
                            )
                        )
                    ],
                }
            )
    return slots


def _property_classes(
    features: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "unique_id": _clean_text(attributes.get("UniqueID")),
            "property_class": _clean_text(attributes.get("PROPERTY_CLASS")),
            "stat_class": _clean_text(attributes.get("STAT_CLASS")),
            "description": _clean_text(attributes.get("STAT_CLASS_DESC")),
            "year_built": _clean_text(attributes.get("YEAR_BUILT")),
            "total_square_feet": _number(attributes.get("TOTAL_SQFT")),
            "real_market_improvement_value": _number(
                attributes.get("RMV_IMPR")
            ),
        }
        for attributes in (_attributes(feature) for feature in features)
    ]


def _sales(features: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for feature in features:
        attributes = _attributes(feature)
        for slot in (1, 2):
            document_ref = _clean_text(attributes.get(f"Book_Page_{slot}"))
            sale_date = _arcgis_date(attributes.get(f"Sales_Date_{slot}"))
            seller = _clean_text(attributes.get(f"Seller_{slot}"))
            buyer = _clean_text(attributes.get(f"Buyer_{slot}"))
            price = _number(attributes.get(f"Total_Sales_Price_{slot}"))
            reject_code = _clean_text(attributes.get(f"Reject_Code_{slot}"))
            reject_description = _clean_text(
                attributes.get(f"Reject_Description_{slot}")
            )
            if not any(
                (
                    document_ref,
                    sale_date,
                    seller,
                    buyer,
                    reject_code,
                    reject_description,
                )
            ) and price in (None, 0):
                continue
            values.append(
                {
                    "source_document_ref": document_ref,
                    "sale_date": sale_date,
                    "consideration": price,
                    "currency": "USD",
                    "seller": seller,
                    "buyer": buyer,
                    "qualification_code": reject_code,
                    "qualification_description": reject_description,
                    "source_slot": slot,
                    "source_table": TABLES["sales"].name,
                    "join_provenance": "same_service_taxlot_key_complement",
                    "declared_arcgis_relationship": False,
                }
            )
    return sorted(
        values,
        key=lambda value: (
            value.get("sale_date") or "",
            value.get("source_document_ref") or "",
        ),
        reverse=True,
    )


def _active_accounts(
    features: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "account_id": _number(attributes.get("account_id")),
            "account_status": _clean_text(attributes.get("account_status")),
        }
        for attributes in (_attributes(feature) for feature in features)
    ]


def _retired_accounts(
    features: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "account_id": _number(attributes.get("account_id")),
            "year": _number(attributes.get("year")),
        }
        for attributes in (_attributes(feature) for feature in features)
    ]


def _normalize_record(
    taxlot: str,
    bundle: HydrationBundle,
    *,
    geometry_requested: bool,
) -> dict[str, Any]:
    feature = bundle.base_by_taxlot[taxlot]
    attributes = _attributes(feature)
    component_features = {
        key: bundle.components.get(key, {}).get(taxlot, ())
        for key in TABLES
    }
    component_records = {
        key: _component_projection(TABLES[key], features)
        for key, features in component_features.items()
    }
    account_features = component_features["account"]
    mailing_features = component_features["mailing"]
    improvement_features = component_features["improvements"]
    roll_features = component_features["roll_values"]
    sales = _sales(component_features["sales"])
    active_accounts = _active_accounts(component_features["serial_crossrefs"])
    retired_accounts = _retired_accounts(component_features["dead_numbers"])
    account_ids = [
        str(account["account_id"])
        for account in active_accounts
        if account.get("account_id") is not None
    ]
    record: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": TAXLOT_LAYER_URL,
        "record_view": "full_detail",
        "snapshot_complete": not bundle.errors,
        "native_parcel_id": taxlot,
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            taxlot,
        ),
        "object_id": _feature_oid(feature),
        "alternate_parcel_ids": [
            value
            for value in (
                _clean_text(attributes.get("MAPNUMBER")),
                _clean_text(attributes.get("PARCEL")),
            )
            if value and value != taxlot
        ],
        "assessment_account_ids": account_ids,
        "jurisdiction": {
            "country": "US",
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": "Deschutes",
            "county_geoid": COUNTY_GEOID,
            "county_fips": COUNTY_GEOID,
        },
        "taxlot_components": {
            "township": _clean_text(attributes.get("TOWNSHIP")),
            "range": _clean_text(attributes.get("RANGE")),
            "section": _clean_text(attributes.get("SECTION")),
            "quarter": _clean_text(attributes.get("QUARTER")),
            "sixteenth": _clean_text(attributes.get("SIXTEENTH")),
            "parcel": _clean_text(attributes.get("PARCEL")),
            "map_supplement": _clean_text(attributes.get("MAPSUP")),
            "map_number": _clean_text(attributes.get("MAPNUMBER")),
        },
        "situs_address": _address(
            _attributes(account_features[0]) if account_features else None,
            mailing=False,
        ),
        "mailing_address": _address(
            _attributes(mailing_features[0]) if mailing_features else None,
            mailing=True,
        ),
        "owners": _owners(component_features["owners"]),
        "assessment": _assessment(roll_features, improvement_features),
        "active_account_crossrefs": active_accounts,
        "retired_account_history": retired_accounts,
        "improvements": _improvement_slots(improvement_features),
        "property_class_observations": _property_classes(
            component_features["property_classes"]
        ),
        "sale_history": sales,
        "last_sale": sales[0] if sales else None,
        "physical_characteristics": (
            {
                "land_size_acres": _number(
                    _attributes(improvement_features[0]).get("Land_Size_Acres")
                ),
                "year_appraised": _clean_text(
                    _attributes(improvement_features[0]).get("Year_Appr")
                ),
                "property_class": _clean_text(
                    _attributes(improvement_features[0]).get("Property_Class")
                ),
                "bedrooms": _number(
                    _attributes(improvement_features[0]).get("Bedrooms")
                ),
                "bathrooms": _number(
                    _attributes(improvement_features[0]).get("Bathrooms")
                ),
            }
            if improvement_features
            else None
        ),
        "related_components": component_records,
        "relationship_contracts": [
            _relationship_contract(table) for table in DECLARED_RELATIONSHIPS
        ],
        "keyed_complements": [
            _relationship_contract(table) for table in KEYED_COMPLEMENTS
        ],
        "source_lineage": {
            "publisher": PUBLISHER,
            "service_item_id": SERVICE_ITEM_ID,
            "primary_layer_id": TAXLOT_LAYER_ID,
            "primary_key": "TAXLOT",
            "declared_relationship_count": len(DECLARED_RELATIONSHIPS),
            "sales_relationship_status": "same_service_taxlot_key_complement",
            "sales_declared_arcgis_relationship": False,
        },
        "source_links": {
            "feature_service": SERVICE_URL,
            "parcel_detail": _clean_text(attributes.get("DIAL")),
        },
        "source_last_updated": bundle.source_last_updated,
        "raw_attributes": dict(attributes),
        "response_schema_fingerprint": sha256_fingerprint(
            bundle.schema_fingerprints
        ),
        "component_schema_fingerprints": dict(bundle.schema_fingerprints),
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
    }
    if geometry_requested and isinstance(feature.get("geometry"), Mapping):
        record.update(
            {
                "geometry": dict(feature["geometry"]),
                "geometry_format": "esri_json",
                "geometry_crs": "EPSG:4326",
                "geometry_source_crs": "EPSG:3857",
            }
        )
    return record


def _client(
    args: argparse.Namespace,
    access_decision: Mapping[str, Any] | None,
) -> DeschutesArcGISClient:
    limits = (
        access_decision.get("limits") or {}
        if access_decision is not None
        else {}
    )
    page_size = min(args.page_size, MAX_SERVER_PAGE_SIZE)
    reviewed_page_size = limits.get("maximum_page_size")
    if reviewed_page_size is not None:
        page_size = min(page_size, int(reviewed_page_size))
    reviewed_interval = float(limits.get("minimum_interval_seconds") or 0)
    return DeschutesArcGISClient(
        page_size=page_size,
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
        retry_attempts=args.retry_attempts,
    )


def _access_failure(
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


def _enforce_access_decision(
    query: PublicRecordsQuery,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult | None:
    if access_decision is None:
        return None
    decision_source = access_decision.get("source_id")
    if decision_source is not None and decision_source != SOURCE_ID:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_decision_source_mismatch",
                    message="Catalog decision belongs to another source component",
                    category="access",
                    details={
                        "decision_source_id": decision_source,
                        "query_source_id": SOURCE_ID,
                    },
                )
            ],
            warnings=WARNINGS,
        )
    if not access_decision.get("allowed", False):
        return _access_failure(query, access_decision)
    return None


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception:
        pass


def _result_from_batch(
    query: PublicRecordsQuery,
    batch: TaxlotBatch,
    bundle: HydrationBundle,
    *,
    geometry: bool,
) -> PublicRecordsResult:
    records: list[dict[str, Any]] = []
    errors = [*batch.errors, *bundle.errors]
    for taxlot in batch.taxlots:
        if taxlot not in bundle.base_by_taxlot:
            continue
        try:
            records.append(
                _normalize_record(
                    taxlot,
                    bundle,
                    geometry_requested=geometry,
                )
            )
        except (TypeError, ValueError) as error:
            errors.append(
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    details={"taxlot": taxlot},
                )
            )
    if errors:
        status = ResultStatus.PARTIAL if records else ResultStatus.SOURCE_CHANGED
        return PublicRecordsResult.failure(
            query,
            status,
            errors,
            records=records,
            next_cursor=batch.next_cursor if records else None,
            warnings=WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=WARNINGS,
    )


def _execute_records(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    field = (
        "parcel"
        if args.command == "parcel"
        else (_auto_field(args.query) if args.field == "auto" else args.field)
    )
    query = _build_query(
        operation=args.command,
        selector=args.query,
        search_field=field,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry,
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(query, access_decision)
    if access_failure is not None:
        _best_effort_log(query, access_failure)
        return access_failure
    try:
        active_client = client or _client(args, access_decision)
        plan = _search_plan(args.command, args.query, field)
        if plan.field == "account":
            batch = _fetch_account_slice(
                active_client,
                args.query,
                limit=args.limit,
                cursor=args.cursor,
                geometry=args.geometry,
            )
        else:
            batch = _fetch_distinct_slice(
                active_client,
                plan,
                limit=args.limit,
                cursor=args.cursor,
                geometry=args.geometry,
            )
        bundle = _hydrate(
            active_client,
            batch.taxlots,
            geometry=args.geometry,
        )
        result = _result_from_batch(
            query,
            batch,
            bundle,
            geometry=args.geometry,
        )
    except DeschutesSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=WARNINGS)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                )
            ],
            warnings=WARNINGS,
        )
    _best_effort_log(query, result)
    return result


def _validate_service_metadata(metadata: Mapping[str, Any]) -> None:
    if metadata.get("serviceItemId") != SERVICE_ITEM_ID:
        raise SourceSchemaError(
            "Deschutes FeatureServer item identity changed",
            url=SERVICE_URL,
            details={
                "expected": SERVICE_ITEM_ID,
                "observed": metadata.get("serviceItemId"),
            },
        )
    layer_ids = {
        layer.get("id")
        for layer in metadata.get("layers", [])
        if isinstance(layer, Mapping)
    }
    table_ids = {
        table.get("id")
        for table in metadata.get("tables", [])
        if isinstance(table, Mapping)
    }
    if layer_ids != {TAXLOT_LAYER_ID} or table_ids != {
        table.table_id for table in TABLES.values()
    }:
        raise SourceSchemaError(
            "Deschutes FeatureServer component inventory changed",
            url=SERVICE_URL,
            details={
                "observed_layer_ids": sorted(layer_ids),
                "observed_table_ids": sorted(table_ids),
            },
        )


def _execute_probe(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    query = _build_query(
        operation="probe",
        selector=PROBE_TAXLOT,
        search_field="parcel",
        limit=1,
        cursor=None,
        geometry=False,
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(query, access_decision)
    if access_failure is not None:
        _best_effort_log(query, access_failure)
        return access_failure
    try:
        active_client = client or _client(args, access_decision)
        service_metadata = active_client.fetch_service_metadata()
        _validate_service_metadata(service_metadata)
        component_counts = {
            "taxlot": active_client.fetch_count(TAXLOT_LAYER_ID, "1=1")
        }
        for table in TABLES.values():
            component_counts[table.key] = active_client.fetch_count(
                table.table_id,
                "1=1",
            )
        plan = _search_plan("parcel", PROBE_TAXLOT, "parcel")
        batch = _fetch_distinct_slice(
            active_client,
            plan,
            limit=1,
            cursor=None,
            geometry=False,
        )
        if batch.taxlots != (PROBE_TAXLOT,):
            raise SourceSchemaError(
                "Deschutes sentinel taxlot did not resolve exactly once",
                url=TAXLOT_LAYER_URL,
                details={"taxlots": list(batch.taxlots)},
            )
        bundle = _hydrate(active_client, batch.taxlots, geometry=False)
        normalized = _normalize_record(
            PROBE_TAXLOT,
            bundle,
            geometry_requested=False,
        )
        errors = [*batch.errors, *bundle.errors]
        probe_record = {
            "record_kind": "source_probe",
            "source_id": SOURCE_ID,
            "schema_version": PROBE_SCHEMA_VERSION,
            "service_item_id": SERVICE_ITEM_ID,
            "service_description": service_metadata.get("serviceDescription"),
            "component_counts": component_counts,
            "declared_relationships": [
                _relationship_contract(table)
                for table in DECLARED_RELATIONSHIPS
            ],
            "keyed_complements": [
                _relationship_contract(table) for table in KEYED_COMPLEMENTS
            ],
            "sales_relationship_status": {
                "component": "sales",
                "declared_arcgis_relationship": False,
                "provenance_kind": "same_service_taxlot_key_complement",
                "join": "Taxlot -> TAXLOT",
            },
            "sentinel": normalized,
        }
        if errors:
            result = PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                errors,
                records=[probe_record],
                warnings=WARNINGS,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                [probe_record],
                warnings=WARNINGS,
            )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=WARNINGS)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="probe_validation_failed",
                    message=str(error),
                    category="source_schema",
                )
            ],
            warnings=WARNINGS,
        )
    _best_effort_log(query, result)
    return result


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "name": SOURCE_NAME,
        "publisher": PUBLISHER,
        "service_url": SERVICE_URL,
        "service_item_id": SERVICE_ITEM_ID,
        "jurisdiction": _jurisdiction().to_dict(),
        "search_fields": list(SEARCH_FIELDS),
        "probe_taxlot": PROBE_TAXLOT,
        "primary_layer": {
            "table_id": TAXLOT_LAYER_ID,
            "name": "Taxlot",
            "url": TAXLOT_LAYER_URL,
            "primary_key": "TAXLOT",
            "geometry_type": "esriGeometryPolygon",
        },
        "declared_relationships": [
            _relationship_contract(table) for table in DECLARED_RELATIONSHIPS
        ],
        "keyed_complements": [
            _relationship_contract(table) for table in KEYED_COMPLEMENTS
        ],
        "pagination": {
            "search_index": "distinct_taxlot_count_and_taxlot_order",
            "hydration": "component_count_and_objectid_order",
            "maximum_server_page_size": MAX_SERVER_PAGE_SIZE,
            "cursor": "query_bound_with_anchor_count_and_schema",
        },
        "warnings": list(WARNINGS),
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute a local source listing, property search, parcel lookup, or probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "probe":
        return _execute_probe(
            args,
            client=client,
            access_decision=access_decision,
        )
    return _execute_records(
        args,
        client=client,
        access_decision=access_decision,
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
    output = getattr(args, "output", None)
    if output:
        destination = Path(output).expanduser()
        _atomic_json_write(destination, payload)
        records = payload.get("records")
        count = len(records) if isinstance(records, list) else 1
        print(
            f"{count} results (Deschutes property {args.command}) "
            f"saved to {destination}"
        )
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command == "sources":
        print(f"{SOURCE_NAME}: {len(TABLES)} related table components")
        print(
            f"  declared relationships: {len(DECLARED_RELATIONSHIPS)}; "
            f"keyed complements: {len(KEYED_COMPLEMENTS)}"
        )
        return
    records = payload.get("records", [])
    print(
        f"Deschutes property {args.command}: {payload.get('status')} "
        f"({len(records)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        if record.get("record_kind") == "source_probe":
            print(
                f"  sentinel {record.get('sentinel', {}).get('native_parcel_id')} "
                f"| {len(record.get('declared_relationships', []))} relationships"
            )
        else:
            print(
                f"  {record.get('native_parcel_id')} | "
                f"{len(record.get('owners', []))} owner rows"
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


def _add_record_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--cursor",
        help="Query-bound continuation cursor returned by an earlier result",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Include taxlot geometry transformed to WGS84",
    )
    _add_transport_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query official Deschutes County relationship-aware taxlots"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Describe the verified layer, relationships, and keyed complement",
    )
    add_output_args(sources)

    search = sub.add_parser(
        "search",
        help="Search an official Deschutes assessor index and hydrate taxlots",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=SEARCH_FIELDS,
        default="auto",
        help="Source-native index family; auto resolves from selector shape",
    )
    _add_record_arguments(search)

    parcel = sub.add_parser(
        "parcel",
        help="Fetch an exact taxlot, map number, or parcel component",
    )
    parcel.add_argument("query")
    parcel.set_defaults(field="parcel")
    _add_record_arguments(parcel)

    probe = sub.add_parser(
        "probe",
        help="Verify service inventory, counts, relationships, and a live sentinel",
    )
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
