#!/usr/bin/env python3
"""Query Wisconsin's official statewide parcel-map service.

The State Cartographer's Office and Wisconsin Land Information Program publish
one stable ArcGIS service directory for the current annual parcel release. The
layer aggregates county and municipal GIS/tax-roll observations. It also
contains source-labelled rights-of-way, hydrography, gaps, and other non-parcel
polygons.

Searches use ordered OBJECTID keyset traversal and compare source counts,
compatible schema, release identity, and the ArcGIS data-edit marker before and
after collection. Omitting ``--limit`` retrieves every native match;
``--page-size`` only controls transport batches.

Examples:
    uv run python tools/query_wisconsin_parcels.py owner "EPSTEIN"
    uv run python tools/query_wisconsin_parcels.py address "MAIN ST" \
        --county Dane
    uv run python tools/query_wisconsin_parcels.py parcel "008015540000" \
        --county 001
    uv run python tools/query_wisconsin_parcels.py mailing "CHICAGO IL"
    uv run python tools/query_wisconsin_parcels.py coverage --json
    uv run python tools/query_wisconsin_parcels.py alternatives --json
    uv run python tools/query_wisconsin_parcels.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
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


SOURCE_ID = "us-wi-statewide-parcels"
STATE_CODE = "WI"
STATE_FIPS = "55"
LAYER_URL = (
    "https://services3.arcgis.com/n6uYoouQZW75n5WI/arcgis/rest/services/"
    "Wisconsin_Statewide_Parcels_DB/FeatureServer/0"
)
DATA_PAGE_URL = "https://www.sco.wisc.edu/parcels/data/"
COUNTY_DOWNLOAD_URL = "https://www.sco.wisc.edu/parcels/data-county/"
PARCEL_OVERVIEW_URL = "https://www.sco.wisc.edu/data/parcels/"
WEB_APP_URL = "https://maps.sco.wisc.edu/Parcels/"
GEODATA_URL = "https://geodata.wisc.edu/"
COUNTY_CONTACTS_URL = "https://doa.wi.gov/DIR/County_Contacts.pdf"
PARCEL_FORMATS_URL = "https://www.revenue.wi.gov/pages/ust/parcels.aspx"
RETR_HOME_URL = "https://www.revenue.wi.gov/Pages/RETr/Home.aspx"
RETR_SEARCH_URL = "https://tap.revenue.wi.gov/RETRSearch"
RETR_HISTORY_URL = "https://tap.revenue.wi.gov/RETRHistoric"
SCHEMA_URL = (
    "https://www.sco.wisc.edu/parcels/data/assets/V12/"
    "V12_Wisconsin_Statewide_Parcels_Schema_Documentation.pdf"
)
CHANGE_LOG_URL = (
    "https://www.sco.wisc.edu/parcels/data/assets/"
    "Wisconsin_Statewide_Parcels_Change_Log.pdf"
)
STATEWIDE_COMPRESSED_URL = (
    "https://web.s3.wisc.edu/parcels/v12_parcels/"
    "V12.0.0_Wisconsin_Parcels_2026_10.3_Compressed.zip"
)
STATEWIDE_UNCOMPRESSED_URL = (
    "https://web.s3.wisc.edu/parcels/v12_parcels/"
    "V12.0.0_Wisconsin_Parcels_2026_10.3_Uncompressed.zip"
)

DEFAULT_PAGE_SIZE = 2_000
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = "wi-parcels:v1:"
CURSOR_VERSION = 1
RELEASE_NAME_PATTERN = re.compile(
    r"^V(?P<version>[0-9]+)00_WisconsinParcels_(?P<year>[0-9]{4})$"
)

REQUIRED_FIELDS = (
    "OBJECTID",
    "STATEID",
    "PARCELID",
    "TAXPARCELID",
    "PARCELDATE",
    "TAXROLLYEAR",
    "OWNERNME1",
    "OWNERNME2",
    "PSTLADRESS",
    "SITEADRESS",
    "ADDNUMPREFIX",
    "ADDNUM",
    "ADDNUMSUFFIX",
    "PREFIX",
    "STREETNAME",
    "STREETTYPE",
    "SUFFIX",
    "LANDMARKNAME",
    "UNITTYPE",
    "UNITID",
    "PLACENAME",
    "ZIPCODE",
    "ZIP4",
    "STATE",
    "SCHOOLDIST",
    "SCHOOLDISTNO",
    "CNTASSDVALUE",
    "LNDVALUE",
    "IMPVALUE",
    "MFLVALUE",
    "ESTFMKVALUE",
    "NETPRPTA",
    "GRSPRPTA",
    "PROPCLASS",
    "AUXCLASS",
    "ASSDACRES",
    "DEEDACRES",
    "GISACRES",
    "CONAME",
    "LOADDATE",
    "PARCELFIPS",
    "PARCELSRC",
    "LONGITUDE",
    "LATITUDE",
    "SITEADRESS_STAND",
    "Shape__Area",
    "Shape__Length",
)

# The source documentation says its list is not exhaustive. These exact values
# are useful positive signals; other records remain parcel_or_unclassified.
KNOWN_NON_PARCEL_LABELS = frozenset(
    {
        "BALSAM LAKE",
        "GAP",
        "HYDRO",
        "LAKE",
        "MUD LAKE",
        "OVERLAP",
        "RAIL",
        "ROAD.RESERVATION",
        "ROW",
        "WATER",
    }
)
OWNER_WITHHELD_MARKER = "NOT AVAILABLE"

PROPERTY_CLASS_DESCRIPTIONS = {
    "1": "residential",
    "2": "commercial",
    "3": "manufacturing",
    "4": "agricultural",
    "5": "undeveloped",
    "5M": "agricultural_forest",
    "6": "productive_forest_land",
    "7": "other",
}

SOURCE_WARNINGS = (
    "Owner, assessment, and tax fields are county-contributed annual "
    "observations; use the county property system or recorded instrument when "
    "more current or instrument-level detail matters.",
    "Parcel polygons are aggregated GIS representations. The source documents "
    "known jurisdiction-boundary gaps and overlaps and is not a land survey.",
    "Field population varies by contributor. Source nulls and numeric zeroes "
    "are preserved as distinct values.",
    "The observed V12 documentation identifies partial digital-map gaps in "
    "Buffalo and Burnett counties.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Wisconsin Statewide Parcel Map",
    source_role="statewide_annual_county_contributed_parcel_assessment_map",
    base_url=LAYER_URL,
    dataset_id="Wisconsin_Statewide_Parcels_DB/FeatureServer/0",
    metadata={
        "authority": (
            "Wisconsin State Cartographer's Office and Wisconsin Land "
            "Information Program"
        ),
        "coverage": "Wisconsin statewide, aggregated from county submissions",
        "update_frequency": "annual",
        "stable_service_directory": True,
        "data_page": DATA_PAGE_URL,
        "overview": PARCEL_OVERVIEW_URL,
        "observed_v12_schema": SCHEMA_URL,
        "change_log": CHANGE_LOG_URL,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_FIPS,
    name="Wisconsin",
    state_code=STATE_CODE,
)


class WisconsinParcelError(RuntimeError):
    """Selection or continuation error with result-envelope semantics."""

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
    criteria_fingerprint: str
    last_object_id: int
    total_count: int
    schema_fingerprint: str
    dataset_release: str
    dataset_version: int | None


@dataclass(frozen=True)
class SourceSnapshot:
    schema_fingerprint: str
    dataset_release: str
    release_version: int
    release_year: int
    dataset_version: int | None
    page_size: int
    service_item_id: str | None


@dataclass(frozen=True)
class TraversalBatch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    remaining_count: int
    pages_fetched: int
    snapshot: SourceSnapshot
    error: PublicRecordsError | None = None


class WisconsinParcelClient(ArcGISRESTClient):
    """Metadata, count, grouped-statistic, and keyset access."""

    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
    ) -> None:
        super().__init__(
            LAYER_URL,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Wisconsin ArcGIS returned invalid layer metadata",
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
                "Wisconsin ArcGIS returned an invalid count response",
                url=self.query_url,
                details={"response": payload},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Wisconsin ArcGIS count is not a non-negative integer",
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
        parameters: dict[str, Any] = {
            "where": where,
            "outFields": "*",
            "returnGeometry": str(return_geometry).lower(),
            "orderByFields": "OBJECTID ASC",
            "resultRecordCount": record_count,
            "f": "json",
        }
        if return_geometry:
            parameters["outSR"] = 4326
        payload = self._request_json(self.query_url, params=parameters)
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Wisconsin ArcGIS returned an invalid feature response",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "Wisconsin ArcGIS response lacks a valid features array",
                url=self.query_url,
            )
        return tuple(features)

    def fetch_grouped_counts(
        self,
        where: str,
    ) -> tuple[Mapping[str, Any], ...]:
        statistics = [
            {
                "statisticType": "count",
                "onStatisticField": "OBJECTID",
                "outStatisticFieldName": "record_count",
            }
        ]
        payload = self._request_json(
            self.query_url,
            params={
                "where": where,
                "outStatistics": canonical_json(statistics),
                "groupByFieldsForStatistics": "PARCELSRC,PARCELFIPS",
                "orderByFields": "PARCELFIPS ASC",
                "returnGeometry": "false",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Wisconsin ArcGIS returned invalid grouped statistics",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list):
            raise SourceSchemaError(
                "Wisconsin grouped-statistics response lacks features",
                url=self.query_url,
            )
        rows: list[Mapping[str, Any]] = []
        for feature in features:
            if not isinstance(feature, Mapping):
                raise SourceSchemaError(
                    "Wisconsin grouped-statistics feature is malformed",
                    url=self.query_url,
                )
            attributes = feature.get("attributes")
            if not isinstance(attributes, Mapping):
                raise SourceSchemaError(
                    "Wisconsin grouped-statistics row lacks attributes",
                    url=self.query_url,
                )
            rows.append(attributes)
        return tuple(rows)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        raise WisconsinParcelError(
            "blank_query",
            "query value must not be blank",
        )
    return text.replace("'", "''")


def _county_where(county: str | None) -> str | None:
    if county is None:
        return None
    value = _sql_text(county)
    digits = "".join(character for character in value if character.isdigit())
    if value.replace("-", "").isdigit():
        if len(digits) == 5 and digits.startswith(STATE_FIPS):
            digits = digits[2:]
        if len(digits) != 3:
            raise WisconsinParcelError(
                "invalid_county_fips",
                "Wisconsin county FIPS must be three digits or a 55xxx GEOID",
            )
        return f"PARCELFIPS='{digits}'"
    upper = value.upper()
    return (
        f"(UPPER(PARCELSRC)='{upper}' OR UPPER(CONAME)='{upper}')"
    )


def _where(
    operation: str,
    selector: str | None,
    county: str | None,
) -> str:
    if operation == "probe":
        expression = "OBJECTID > 0"
    else:
        value = _sql_text(selector)
        upper = value.upper()
        if operation == "owner":
            expression = (
                f"(UPPER(OWNERNME1) LIKE '%{upper}%' OR "
                f"UPPER(OWNERNME2) LIKE '%{upper}%')"
            )
        elif operation == "address":
            expression = (
                f"(UPPER(SITEADRESS) LIKE '%{upper}%' OR "
                f"UPPER(SITEADRESS_STAND) LIKE '%{upper}%')"
            )
        elif operation == "mailing":
            expression = f"UPPER(PSTLADRESS) LIKE '%{upper}%'"
        elif operation == "parcel":
            expression = (
                f"(UPPER(STATEID)='{upper}' OR "
                f"UPPER(PARCELID)='{upper}' OR "
                f"UPPER(TAXPARCELID)='{upper}')"
            )
        elif operation == "objectid":
            if not value.isdigit():
                raise WisconsinParcelError(
                    "invalid_object_id",
                    "objectid must be numeric",
                )
            expression = f"OBJECTID={int(value)}"
        else:
            raise WisconsinParcelError(
                "unsupported_operation",
                f"unsupported Wisconsin parcel operation: {operation}",
            )
    county_expression = _county_where(county)
    if county_expression:
        return f"({expression}) AND {county_expression}"
    return expression


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    operation = args.command
    selector = getattr(args, "query", None)
    parameters: dict[str, Any] = {
        "selector": selector,
        "county": getattr(args, "county", None),
    }
    if operation not in {"alternatives", "coverage"}:
        parameters["return_geometry"] = bool(
            getattr(args, "geometry", False)
        )
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=(
                1
                if operation == "probe"
                else getattr(args, "limit", None)
            ),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _compatible_snapshot(metadata: Mapping[str, Any]) -> SourceSnapshot:
    name = metadata.get("name")
    release_match = (
        RELEASE_NAME_PATTERN.fullmatch(name) if isinstance(name, str) else None
    )
    if release_match is None:
        raise SourceSchemaError(
            "Wisconsin ArcGIS layer name no longer identifies an annual release",
            url=LAYER_URL,
            details={"observed_name": name},
        )
    identity = {
        "id": metadata.get("id"),
        "object_id_field": metadata.get("objectIdField"),
        "geometry_type": metadata.get("geometryType"),
    }
    expected_identity = {
        "id": 0,
        "object_id_field": "OBJECTID",
        "geometry_type": "esriGeometryPolygon",
    }
    if identity != expected_identity:
        raise SourceSchemaError(
            "Wisconsin ArcGIS layer identity changed",
            url=LAYER_URL,
            details={
                "expected": expected_identity,
                "observed": identity,
            },
        )
    capabilities = metadata.get("advancedQueryCapabilities")
    if not isinstance(capabilities, Mapping) or (
        capabilities.get("supportsOrderBy") is not True
    ):
        raise SourceSchemaError(
            "Wisconsin ArcGIS layer no longer declares ordered queries",
            url=LAYER_URL,
        )
    if metadata.get("supportsStatistics") is not True:
        raise SourceSchemaError(
            "Wisconsin ArcGIS layer no longer declares statistics support",
            url=LAYER_URL,
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "Wisconsin ArcGIS metadata lacks field declarations",
            url=LAYER_URL,
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
    missing = sorted(set(REQUIRED_FIELDS) - set(definitions))
    if missing:
        raise SourceSchemaError(
            "Wisconsin ArcGIS layer is missing required fields",
            url=LAYER_URL,
            details={"missing_fields": missing},
        )
    native_maximum = metadata.get("maxRecordCount")
    if (
        isinstance(native_maximum, bool)
        or not isinstance(native_maximum, int)
        or native_maximum <= 0
    ):
        raise SourceSchemaError(
            "Wisconsin ArcGIS metadata lacks a usable maxRecordCount",
            url=LAYER_URL,
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
    service_item_id = metadata.get("serviceItemId")
    if not isinstance(service_item_id, str):
        service_item_id = None
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "identity": identity,
            "required_fields": {
                field_name: definitions[field_name]
                for field_name in REQUIRED_FIELDS
            },
        }
    )
    return SourceSnapshot(
        schema_fingerprint=schema_fingerprint,
        dataset_release=name,
        release_version=int(release_match.group("version")),
        release_year=int(release_match.group("year")),
        dataset_version=dataset_version,
        page_size=native_maximum,
        service_item_id=service_item_id,
    )


def _criteria_fingerprint(
    *,
    operation: str,
    where: str,
    return_geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "operation": operation,
            "where": where,
            "return_geometry": return_geometry,
            "ordering": "OBJECTID ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "last_oid": state.last_object_id,
        "total": state.total_count,
        "schema": state.schema_fingerprint,
        "release": state.dataset_release,
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
        raise WisconsinParcelError(
            "invalid_cursor",
            "cursor does not belong to the Wisconsin parcel adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(token + padding).decode("utf-8")
        )
        state = CursorState(
            criteria_fingerprint=str(payload["criteria"]),
            last_object_id=int(payload["last_oid"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
            dataset_release=str(payload["release"]),
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
        raise WisconsinParcelError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if (
        payload.get("v") != CURSOR_VERSION
        or state.last_object_id < 0
        or state.total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
        or RELEASE_NAME_PATTERN.fullmatch(state.dataset_release) is None
    ):
        raise WisconsinParcelError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _object_id(feature: Mapping[str, Any]) -> int:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "Wisconsin ArcGIS feature lacks an attributes object",
            url=LAYER_URL,
        )
    value = attributes.get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceSchemaError(
            "Wisconsin ArcGIS feature lacks a valid OBJECTID",
            url=LAYER_URL,
            details={"OBJECTID": value},
        )
    return value


def _keyset_where(where: str, last_object_id: int | None) -> str:
    if last_object_id is None:
        return where
    return f"({where}) AND OBJECTID > {last_object_id}"


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
    criteria: str,
    snapshot: SourceSnapshot,
) -> None:
    if state is None:
        return
    if state.criteria_fingerprint != criteria:
        raise WisconsinParcelError(
            "cursor_query_mismatch",
            "cursor belongs to different query criteria",
        )
    if state.schema_fingerprint != snapshot.schema_fingerprint:
        raise WisconsinParcelError(
            "cursor_schema_changed",
            "source schema changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    if state.dataset_release != snapshot.dataset_release:
        raise WisconsinParcelError(
            "cursor_release_changed",
            "the annual parcel release changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_release": state.dataset_release,
                "current_release": snapshot.dataset_release,
            },
        )
    if (
        state.dataset_version is not None
        and snapshot.dataset_version is not None
        and state.dataset_version != snapshot.dataset_version
    ):
        raise WisconsinParcelError(
            "cursor_snapshot_changed",
            "source data changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_dataset_version": state.dataset_version,
                "current_dataset_version": snapshot.dataset_version,
            },
        )


def _traverse(
    client: Any,
    *,
    operation: str,
    where: str,
    limit: int | None,
    cursor: str | None,
    return_geometry: bool,
) -> TraversalBatch:
    start_snapshot = _compatible_snapshot(client.fetch_metadata())
    criteria = _criteria_fingerprint(
        operation=operation,
        where=where,
        return_geometry=return_geometry,
    )
    cursor_state = _decode_cursor(cursor)
    _validate_cursor(
        cursor_state,
        criteria=criteria,
        snapshot=start_snapshot,
    )
    total_count = client.fetch_count(where)
    if cursor_state is not None and cursor_state.total_count != total_count:
        raise WisconsinParcelError(
            "cursor_count_changed",
            "matching source count changed after the cursor was issued",
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
                "ArcGIS returned more features than requested",
                details={
                    "requested": requested,
                    "returned": len(page),
                },
            )
            page = page[:requested]
        for feature in page:
            current_object_id = _object_id(feature)
            if (
                last_object_id is not None
                and current_object_id <= last_object_id
            ):
                traversal_error = _partial_error(
                    "arcgis_keyset_not_monotonic",
                    "ArcGIS repeated or reordered a keyset feature",
                    details={
                        "previous_object_id": last_object_id,
                        "object_id": current_object_id,
                    },
                )
                break
            collected.append(feature)
            last_object_id = current_object_id
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
        end_snapshot = _compatible_snapshot(client.fetch_metadata())
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
        or end_snapshot.dataset_release != start_snapshot.dataset_release
        or end_snapshot.dataset_version != start_snapshot.dataset_version
        or end_count != total_count
    ):
        traversal_error = _partial_error(
            "source_changed_during_traversal",
            "Wisconsin parcel data changed during traversal",
            details={
                "start_count": total_count,
                "end_count": end_count,
                "start_release": start_snapshot.dataset_release,
                "end_release": end_snapshot.dataset_release,
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
                criteria_fingerprint=criteria,
                last_object_id=_object_id(collected[-1]),
                total_count=total_count,
                schema_fingerprint=start_snapshot.schema_fingerprint,
                dataset_release=start_snapshot.dataset_release,
                dataset_version=start_snapshot.dataset_version,
            )
        )
    return TraversalBatch(
        records=tuple(collected),
        next_cursor=next_cursor,
        total_count=total_count,
        remaining_count=remaining_count,
        pages_fetched=pages_fetched,
        snapshot=start_snapshot,
        error=traversal_error,
    )


def _source_date(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    for date_format in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _source_snapshot(batch: TraversalBatch) -> dict[str, Any]:
    snapshot = batch.snapshot
    return {
        "dataset_release": snapshot.dataset_release,
        "release_version": snapshot.release_version,
        "release_year": snapshot.release_year,
        "data_last_edit_epoch_ms": snapshot.dataset_version,
        "service_item_id": snapshot.service_item_id,
        "reported_total_matches": batch.total_count,
        "reported_remaining_matches_at_start": batch.remaining_count,
        "pages_fetched": batch.pages_fetched,
        "compatible_schema_fingerprint": snapshot.schema_fingerprint,
    }


def _owner_observation(
    attributes: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    owners: list[dict[str, Any]] = []
    withheld_fields: list[str] = []
    for field_name, role in (
        ("OWNERNME1", "primary_assessor_owner"),
        ("OWNERNME2", "secondary_assessor_owner"),
    ):
        name = _clean_text(attributes.get(field_name))
        if name and name.upper() == OWNER_WITHHELD_MARKER:
            withheld_fields.append(field_name)
        elif name:
            owners.append(
                {
                    "raw_name": name,
                    "role": role,
                    "assertion_type": "county_tax_roll_observation",
                    "source_field": field_name,
                }
            )
    if withheld_fields and owners:
        state = "partially_withheld_by_source"
    elif withheld_fields:
        state = "withheld_by_source"
    elif owners:
        state = "published"
    else:
        state = "not_present_in_dataset"
    visibility: dict[str, Any] = {"state": state}
    if withheld_fields:
        visibility.update(
            {
                "source_marker": OWNER_WITHHELD_MARKER,
                "withheld_fields": withheld_fields,
            }
        )
    return owners, visibility


def _record_classification(parcel_id: str | None) -> dict[str, Any]:
    label = parcel_id.upper() if parcel_id else None
    if label in KNOWN_NON_PARCEL_LABELS:
        return {
            "kind": "non_parcel_feature",
            "source_label": parcel_id,
            "basis": "exact_source_label",
            "label_inventory_is_exhaustive": False,
        }
    return {
        "kind": "parcel_or_unclassified",
        "source_label": None,
        "basis": "no_known_exact_non_parcel_label",
        "label_inventory_is_exhaustive": False,
    }


def _class_codes(value: Any) -> list[str]:
    text = _clean_text(value)
    if text is None:
        return []
    return re.findall(r"[A-Z0-9]+", text.upper())


def _normalize_feature(
    feature: Mapping[str, Any],
    batch: TraversalBatch,
    *,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise SourceSchemaError(
            "Wisconsin parcel feature lacks attributes",
            url=LAYER_URL,
        )
    attributes = dict(attributes_value)
    object_id = _object_id(feature)
    state_id = _clean_text(attributes.get("STATEID"))
    parcel_id = _clean_text(attributes.get("PARCELID"))
    tax_parcel_id = _clean_text(attributes.get("TAXPARCELID"))
    parcel_fips = _clean_text(attributes.get("PARCELFIPS"))
    contributor = _clean_text(attributes.get("PARCELSRC"))
    county_name = _clean_text(attributes.get("CONAME"))
    county_geoid = (
        f"{STATE_FIPS}{parcel_fips}"
        if parcel_fips is not None
        and re.fullmatch(r"[0-9]{3}", parcel_fips)
        and parcel_fips != "999"
        else STATE_FIPS
    )
    record_classification = _record_classification(parcel_id)
    native_id = (
        state_id
        or (
            f"{parcel_fips}{parcel_id}"
            if parcel_fips and parcel_id
            else None
        )
        or str(object_id)
    )
    if record_classification["kind"] == "non_parcel_feature":
        native_id = f"{native_id}:{object_id}"
    owners, owner_visibility = _owner_observation(attributes)
    property_codes = _class_codes(attributes.get("PROPCLASS"))
    auxiliary_codes = _class_codes(attributes.get("AUXCLASS"))

    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            county_geoid,
            (
                "parcel"
                if record_classification["kind"]
                == "parcel_or_unclassified"
                else "mapped-feature"
            ),
            native_id,
        ),
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "record_type": (
            "statewide_annual_parcel_observation"
            if record_classification["kind"]
            == "parcel_or_unclassified"
            else "statewide_annual_non_parcel_map_observation"
        ),
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": county_name,
            "county_geoid": county_geoid,
            "contributing_source": contributor,
            "contributing_source_fips": parcel_fips,
        },
        "native_id": native_id,
        "state_parcel_id": state_id,
        "native_parcel_id": parcel_id,
        "tax_parcel_id": tax_parcel_id,
        "object_id": object_id,
        "source_record_classification": record_classification,
        "owners": owners,
        "owner_visibility": owner_visibility,
        "situs_address": {
            "raw": _clean_text(attributes.get("SITEADRESS")),
            "standardized": _clean_text(
                attributes.get("SITEADRESS_STAND")
            ),
            "number_prefix": _clean_text(
                attributes.get("ADDNUMPREFIX")
            ),
            "number": _clean_text(attributes.get("ADDNUM")),
            "number_suffix": _clean_text(
                attributes.get("ADDNUMSUFFIX")
            ),
            "street_prefix": _clean_text(attributes.get("PREFIX")),
            "street_name": _clean_text(attributes.get("STREETNAME")),
            "street_type": _clean_text(attributes.get("STREETTYPE")),
            "street_suffix": _clean_text(attributes.get("SUFFIX")),
            "landmark": _clean_text(attributes.get("LANDMARKNAME")),
            "unit_type": _clean_text(attributes.get("UNITTYPE")),
            "unit_id": _clean_text(attributes.get("UNITID")),
            "place_name": _clean_text(attributes.get("PLACENAME")),
            "postal_code": _clean_text(attributes.get("ZIPCODE")),
            "postal_code_plus_4": _clean_text(
                attributes.get("ZIP4")
            ),
            "state": _clean_text(attributes.get("STATE")) or STATE_CODE,
        },
        "owner_or_tax_bill_mailing_address": {
            "raw": _clean_text(attributes.get("PSTLADRESS")),
            "may_be_outside_wisconsin": True,
        },
        "assessment_and_tax": {
            "tax_roll_year": _clean_text(
                attributes.get("TAXROLLYEAR")
            ),
            "total_assessed_value": attributes.get("CNTASSDVALUE"),
            "land_value": attributes.get("LNDVALUE"),
            "improvement_value": attributes.get("IMPVALUE"),
            "managed_forest_value": attributes.get("MFLVALUE"),
            "estimated_fair_market_value": attributes.get(
                "ESTFMKVALUE"
            ),
            "net_property_tax": attributes.get("NETPRPTA"),
            "gross_property_tax": attributes.get("GRSPRPTA"),
            "currency": "USD",
        },
        "property_classification": {
            "raw_property_class": _clean_text(
                attributes.get("PROPCLASS")
            ),
            "property_class_codes": property_codes,
            "property_class_descriptions": [
                PROPERTY_CLASS_DESCRIPTIONS[code]
                for code in property_codes
                if code in PROPERTY_CLASS_DESCRIPTIONS
            ],
            "raw_auxiliary_class": _clean_text(
                attributes.get("AUXCLASS")
            ),
            "auxiliary_class_codes": auxiliary_codes,
            "has_tax_exempt_class": any(
                code in {"X1", "X2", "X3", "X4"}
                for code in auxiliary_codes
            ),
            "has_forest_program_class": any(
                re.fullmatch(r"W[1-9]", code)
                for code in auxiliary_codes
            ),
            "assessed_with_other": any(
                code in {"AW", "AWO"} for code in auxiliary_codes
            ),
        },
        "acreage": {
            "assessed": attributes.get("ASSDACRES"),
            "deeded": attributes.get("DEEDACRES"),
            "gis": attributes.get("GISACRES"),
        },
        "school_district": {
            "name": _clean_text(attributes.get("SCHOOLDIST")),
            "number": _clean_text(attributes.get("SCHOOLDISTNO")),
        },
        "source_dates": {
            "parcel_date_raw": _clean_text(
                attributes.get("PARCELDATE")
            ),
            "parcel_date": _source_date(attributes.get("PARCELDATE")),
            "contributor_load_date_raw": _clean_text(
                attributes.get("LOADDATE")
            ),
            "contributor_load_date": _source_date(
                attributes.get("LOADDATE")
            ),
        },
        "source_centroid": {
            "longitude": attributes.get("LONGITUDE"),
            "latitude": attributes.get("LATITUDE"),
            "crs": "EPSG:4326",
        },
        "source_shape_metrics": {
            "area": attributes.get("Shape__Area"),
            "length": attributes.get("Shape__Length"),
            "native_units": "source_spatial_reference",
        },
        "related_official_routes": {
            "county_property_and_recording_contacts": COUNTY_CONTACTS_URL,
            "county_bulk_downloads": COUNTY_DOWNLOAD_URL,
            "parcel_number_formats": PARCEL_FORMATS_URL,
            "real_estate_transfer_return_search": RETR_SEARCH_URL,
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
                "geometry_role": "aggregated_county_gis_parcel_polygon",
            }
        )
    return result


def _group_map(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], int]:
    result: dict[tuple[str, str], int] = {}
    for row in rows:
        source = _clean_text(row.get("PARCELSRC"))
        parcel_fips = _clean_text(row.get("PARCELFIPS"))
        count = row.get("record_count")
        if (
            source is None
            or parcel_fips is None
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            raise SourceSchemaError(
                "Wisconsin grouped-statistics row is invalid",
                url=LAYER_URL,
                details={"row": dict(row)},
            )
        key = (source, parcel_fips)
        if key in result:
            raise SourceSchemaError(
                "Wisconsin grouped-statistics repeated a contributor",
                url=LAYER_URL,
                details={"contributor": key},
            )
        result[key] = count
    return result


def _known_non_parcel_where() -> str:
    labels = ",".join(
        f"'{label.replace(chr(39), chr(39) * 2)}'"
        for label in sorted(KNOWN_NON_PARCEL_LABELS)
    )
    return f"UPPER(PARCELID) IN ({labels})"


def _coverage(client: Any) -> Mapping[str, Any]:
    start_snapshot = _compatible_snapshot(client.fetch_metadata())
    start_count = client.fetch_count("1=1")
    totals = _group_map(client.fetch_grouped_counts("1=1"))
    marker_present = _group_map(
        client.fetch_grouped_counts(
            "OWNERNME1='NOT AVAILABLE' OR "
            "OWNERNME2='NOT AVAILABLE'"
        )
    )
    partially_withheld = _group_map(
        client.fetch_grouped_counts(
            "(OWNERNME1='NOT AVAILABLE' AND OWNERNME2 IS NOT NULL "
            "AND OWNERNME2<>'NOT AVAILABLE') OR "
            "(OWNERNME2='NOT AVAILABLE' AND OWNERNME1 IS NOT NULL "
            "AND OWNERNME1<>'NOT AVAILABLE')"
        )
    )
    absent = _group_map(
        client.fetch_grouped_counts(
            "OWNERNME1 IS NULL AND OWNERNME2 IS NULL"
        )
    )
    known_non_parcel = _group_map(
        client.fetch_grouped_counts(_known_non_parcel_where())
    )
    end_snapshot = _compatible_snapshot(client.fetch_metadata())
    end_count = client.fetch_count("1=1")
    grouped_total = sum(totals.values())
    if grouped_total != start_count:
        raise SourceSchemaError(
            "Wisconsin grouped contributor counts do not equal total count",
            url=LAYER_URL,
            details={
                "reported_count": start_count,
                "grouped_total": grouped_total,
            },
        )
    if (
        end_count != start_count
        or end_snapshot.schema_fingerprint
        != start_snapshot.schema_fingerprint
        or end_snapshot.dataset_release != start_snapshot.dataset_release
        or end_snapshot.dataset_version != start_snapshot.dataset_version
    ):
        raise WisconsinParcelError(
            "source_changed_during_coverage",
            "Wisconsin parcel data changed during the coverage query",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "start_count": start_count,
                "end_count": end_count,
                "start_release": start_snapshot.dataset_release,
                "end_release": end_snapshot.dataset_release,
            },
        )

    contributors = []
    for source, parcel_fips in sorted(
        totals, key=lambda key: (key[1], key[0])
    ):
        total = totals[(source, parcel_fips)]
        marker_count = marker_present.get((source, parcel_fips), 0)
        partially_withheld_count = partially_withheld.get(
            (source, parcel_fips), 0
        )
        withheld_count = marker_count - partially_withheld_count
        absent_count = absent.get((source, parcel_fips), 0)
        published_count = total - marker_count - absent_count
        if published_count < 0 or withheld_count < 0:
            raise SourceSchemaError(
                "Wisconsin owner-visibility counts exceed contributor total",
                url=LAYER_URL,
                details={
                    "source": source,
                    "parcel_fips": parcel_fips,
                    "total": total,
                    "marker_present": marker_count,
                    "withheld": withheld_count,
                    "partially_withheld": partially_withheld_count,
                    "absent": absent_count,
                },
            )
        contributors.append(
            {
                "contributing_source": source,
                "contributing_source_fips": parcel_fips,
                "county_geoid": (
                    f"{STATE_FIPS}{parcel_fips}"
                    if parcel_fips != "999"
                    else None
                ),
                "record_count": total,
                "owner_visibility": {
                    "published": published_count,
                    "withheld_by_source": withheld_count,
                    "partially_withheld_by_source": (
                        partially_withheld_count
                    ),
                    "not_present_in_dataset": absent_count,
                },
                "known_non_parcel_label_count": known_non_parcel.get(
                    (source, parcel_fips), 0
                ),
            }
        )
    special_sources = [
        row
        for row in contributors
        if row["contributing_source_fips"] == "999"
    ]
    county_contributors = [
        row
        for row in contributors
        if row["contributing_source_fips"] != "999"
    ]
    return {
        "source_id": SOURCE_ID,
        "record_type": "statewide_parcel_coverage_summary",
        "dataset_release": start_snapshot.dataset_release,
        "release_version": start_snapshot.release_version,
        "release_year": start_snapshot.release_year,
        "data_last_edit_epoch_ms": start_snapshot.dataset_version,
        "compatible_schema_fingerprint": (
            start_snapshot.schema_fingerprint
        ),
        "statewide_record_count": start_count,
        "county_contributor_count": len(county_contributors),
        "special_source_count": len(special_sources),
        "owner_visibility": {
            "published": (
                start_count
                - sum(marker_present.values())
                - sum(absent.values())
            ),
            "withheld_by_source": (
                sum(marker_present.values())
                - sum(partially_withheld.values())
            ),
            "partially_withheld_by_source": sum(
                partially_withheld.values()
            ),
            "not_present_in_dataset": sum(absent.values()),
        },
        "known_non_parcel_label_count": sum(known_non_parcel.values()),
        "known_non_parcel_labels": sorted(KNOWN_NON_PARCEL_LABELS),
        "non_parcel_label_inventory_is_exhaustive": False,
        "contributors": contributors,
    }


def _alternatives() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "us-wi-statewide-parcels-bulk",
            "route_id": "current-statewide-release-downloads",
            "name": "Current statewide parcel release downloads",
            "url": DATA_PAGE_URL,
            "authority": (
                "Wisconsin State Cartographer's Office and Wisconsin Land "
                "Information Program"
            ),
            "access": "anonymous bulk download",
            "use": (
                "current compressed and uncompressed full-release snapshots "
                "and recovery from API degradation"
            ),
            "relationship_to_primary": (
                "same annual statewide release; transport redundancy"
            ),
        },
        {
            "source_id": "us-wi-statewide-parcels-bulk",
            "route_id": "observed-v12-compressed-gdb",
            "name": "Observed V12 compressed file geodatabase snapshot",
            "url": STATEWIDE_COMPRESSED_URL,
            "authority": (
                "Wisconsin State Cartographer's Office and Wisconsin Land "
                "Information Program"
            ),
            "access": "anonymous bulk download",
            "use": "reproducible V12 snapshot and full-release ingestion",
            "relationship_to_primary": (
                "version-pinned copy of the observed annual release"
            ),
        },
        {
            "source_id": "us-wi-statewide-parcels-bulk",
            "route_id": "observed-v12-uncompressed-gdb",
            "name": "Observed V12 uncompressed file geodatabase snapshot",
            "url": STATEWIDE_UNCOMPRESSED_URL,
            "authority": (
                "Wisconsin State Cartographer's Office and Wisconsin Land "
                "Information Program"
            ),
            "access": "anonymous bulk download",
            "use": "open-source GIS ingestion of the reproducible V12 snapshot",
            "relationship_to_primary": (
                "version-pinned copy of the observed annual release"
            ),
        },
        {
            "source_id": "us-wi-statewide-parcels-bulk",
            "route_id": "county-gdb-and-shapefile-downloads",
            "name": "Current parcel data by county",
            "url": COUNTY_DOWNLOAD_URL,
            "authority": (
                "Wisconsin State Cartographer's Office and Wisconsin Land "
                "Information Program"
            ),
            "access": "anonymous county GDB and shapefile downloads",
            "use": "partitioned bulk ingestion and county-specific recovery",
            "relationship_to_primary": (
                "county partitions of the same annual release"
            ),
        },
        {
            "source_id": "us-wi-statewide-parcels-bulk",
            "route_id": "historic-statewide-and-county-releases",
            "name": "Historic V1-V11 statewide and county parcel releases",
            "url": DATA_PAGE_URL,
            "authority": (
                "Wisconsin State Cartographer's Office and Wisconsin Land "
                "Information Program"
            ),
            "access": "anonymous annual GDB and county downloads",
            "use": "temporal comparison and reproducible historical snapshots",
            "relationship_to_primary": "earlier annual releases",
        },
        {
            "source_id": "us-wi-geodata",
            "route_id": "geodata-wisconsin",
            "name": "GeoData@Wisconsin",
            "url": GEODATA_URL,
            "authority": "University of Wisconsin–Madison",
            "access": "public geospatial discovery and download portal",
            "use": (
                "alternate county dataset discovery and complementary GIS "
                "layers"
            ),
            "relationship_to_primary": (
                "alternate official distribution and complementary layers"
            ),
        },
        {
            "source_id": "us-wi-county-land-record-directory",
            "route_id": "county-land-record-systems",
            "name": "County GIS, real-property-lister, and Register of Deeds",
            "url": COUNTY_CONTACTS_URL,
            "authority": "Wisconsin Department of Administration",
            "access": "official directory of 72 county public systems",
            "use": (
                "more current local detail, tax bills, and recorded "
                "instrument searches"
            ),
            "relationship_to_primary": (
                "upstream local systems and instrument-level complements"
            ),
        },
        {
            "source_id": "us-wi-dor-retr",
            "route_id": "dor-retr-property-search",
            "name": "Wisconsin DOR Real Estate Transfer Return search",
            "url": RETR_SEARCH_URL,
            "authority": "Wisconsin Department of Revenue",
            "access": "public browser application; cookies required",
            "landing_page": RETR_HOME_URL,
            "use": (
                "property transfer, grantor/grantee, consideration, and "
                "recording context"
            ),
            "relationship_to_primary": (
                "complementary official transfer-return records"
            ),
        },
        {
            "source_id": "us-wi-dor-retr-historical",
            "route_id": "dor-retr-historical-downloads",
            "name": "Wisconsin DOR historical RETR downloads",
            "url": RETR_HISTORY_URL,
            "authority": "Wisconsin Department of Revenue",
            "access": "public browser application; cookies required",
            "use": "bulk historical real-estate transfer analysis",
            "relationship_to_primary": (
                "complementary official transfer-return history"
            ),
        },
        {
            "source_id": "us-wi-dor-parcel-number-formats",
            "route_id": "dor-parcel-number-formats",
            "name": "Wisconsin municipality parcel-number formats",
            "url": PARCEL_FORMATS_URL,
            "authority": "Wisconsin Department of Revenue",
            "access": "anonymous reference page",
            "use": (
                "translate contributor-specific PARCELID/TAXPARCELID formats "
                "for local and RETR searches"
            ),
            "relationship_to_primary": "official identifier crosswalk guide",
        },
        {
            "source_id": "us-wi-statewide-parcel-map",
            "route_id": "statewide-parcel-web-app",
            "name": "Wisconsin Statewide Parcel Map web application",
            "url": WEB_APP_URL,
            "authority": "Wisconsin State Cartographer's Office",
            "access": "public interactive map",
            "use": "human-readable map verification and spatial exploration",
            "relationship_to_primary": (
                "official presentation of the current parcel release"
            ),
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
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
) -> PublicRecordsResult:
    query = build_query(args)
    operation = args.command
    try:
        if operation == "alternatives":
            result = PublicRecordsResult.success(query, _alternatives())
        elif operation == "coverage":
            source_client = client or WisconsinParcelClient(
                **_client_args(args)
            )
            result = PublicRecordsResult.success(
                query,
                [_coverage(source_client)],
                warnings=SOURCE_WARNINGS,
            )
        else:
            where = _where(
                operation,
                None if operation == "probe" else args.query,
                getattr(args, "county", None),
            )
            source_client = client or WisconsinParcelClient(
                **_client_args(args)
            )
            batch = _traverse(
                source_client,
                operation=operation,
                where=where,
                limit=1 if operation == "probe" else args.limit,
                cursor=args.cursor,
                return_geometry=args.geometry,
            )
            records = [
                _normalize_feature(
                    feature,
                    batch,
                    geometry_requested=args.geometry,
                )
                for feature in batch.records
            ]
            result = _result_from_batch(query, batch, records)
    except WisconsinParcelError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
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
            f"Wisconsin statewide parcels {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Wisconsin statewide parcels {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command == "alternatives":
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "coverage":
            print(
                f"  {record['dataset_release']} | "
                f"{record['statewide_record_count']} records | "
                f"{record['county_contributor_count']} counties"
            )
        else:
            owners = ", ".join(
                owner["raw_name"] for owner in record["owners"]
            )
            print(
                f"  {record['state_parcel_id'] or '?'} | "
                f"{record['situs_address']['raw'] or '?'} | "
                f"{owners or record['owner_visibility']['state']}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--county",
        help="Optional contributor county name, 3-digit FIPS, or 5-digit GEOID",
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
        "--geometry",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Return source polygon geometry in EPSG:4326",
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


def _add_coverage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Client transport setting; grouped coverage is server-side",
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
            "Query Wisconsin's official statewide annual parcel-map service"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("owner", "Search county-contributed owner observations"),
        ("address", "Search physical-address observations"),
        ("mailing", "Search owner/tax-bill mailing-address observations"),
        ("parcel", "Look up STATEID, PARCELID, or TAXPARCELID"),
        ("objectid", "Look up an ArcGIS OBJECTID"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_network_args(command_parser)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the current service with its first ordered record",
    )
    _add_network_args(probe)

    coverage = subparsers.add_parser(
        "coverage",
        help="Return exact grouped contributor and visibility counts",
    )
    _add_coverage_args(coverage)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="List official bulk, historical, local, and transfer routes",
    )
    add_output_args(alternatives)
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
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
