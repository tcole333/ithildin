#!/usr/bin/env python3
"""Query the current official VGIN statewide parcel layer.

The Virginia Geographic Information Network (VGIN) publishes a stable ArcGIS
item for the current statewide parcel release.  That item is the source
identity and links to the current FeatureServer; the service URL itself has
changed over time.  This adapter resolves the service link from the item,
validates the live layer contract, and uses ordered OBJECTID keyset traversal.

The current layer is deliberately lean: parcel geometry, locality identifiers,
local parcel identifiers, VGIN_QPID, and a locality-contributed update date. It
does not publish owner, assessment, tax, sale, deed, or lien fields. Use the
``alternatives`` command to route a parcel to richer local assessment and
Circuit Court land-record systems.

Omitting ``--limit`` traverses every native match. ``--page-size`` controls
transport batches and is bounded by the live service metadata.

Examples:
    uv run python tools/query_virginia_parcels.py parcel 740-783-1825 \
        --fips 51087 --geometry
    uv run python tools/query_virginia_parcels.py parcel 5108700000001 \
        --field vgin-qpid
    uv run python tools/query_virginia_parcels.py search \
        --locality "Henrico County" --updated-after 2026-01-01 --limit 20
    uv run python tools/query_virginia_parcels.py point -77.6104 37.7099
    uv run python tools/query_virginia_parcels.py localities
    uv run python tools/query_virginia_parcels.py identity-audit
    uv run python tools/query_virginia_parcels.py alternatives
    uv run python tools/query_virginia_parcels.py probe
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

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


SOURCE_ID = "us-va-vgin-parcels"
STATE_CODE = "VA"
STATE_FIPS = "51"

ITEM_ID = "29627d7c051a47dc8ce71b4484531ab3"
ITEM_API_URL = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}"
ITEM_PAGE_URL = f"https://www.arcgis.com/home/item.html?id={ITEM_ID}"
ITEM_DATA_URL = f"{ITEM_API_URL}/data"

DEFAULT_SERVICE_URL = (
    "https://vginmaps.vdem.virginia.gov/arcgis/rest/services/"
    "VA_Base_Layers/VA_Parcels/FeatureServer"
)
DEFAULT_LAYER_URL = f"{DEFAULT_SERVICE_URL}/0"
SHAPEFILE_URL = (
    "https://vginmaps.vdem.virginia.gov/download/BaseMapData/SHP/VirginiaParcel.shp.zip"
)
LOCAL_SCHEMA_TABLES_URL = (
    "https://vgin.vdem.virginia.gov/datasets/virginia-parcels-local-schema-tables/about"
)
VIRGINIA_TAX_LOCALITIES_URL = "https://www.tax.virginia.gov/localities"
SRA_INFO_URL = "https://www.courts.state.va.us/online/sra/home"
SRA_PORTAL_URL = "https://risweb.courts.state.va.us/"
CIRCUIT_DIRECTORY_URL = "https://www.courts.state.va.us/directories/rule115"
ARLINGTON_PROPERTY_URL = (
    "https://arlgis.arlingtonva.us/arcgis/rest/services/"
    "StaffMap/Property_Map_public/MapServer/3"
)
ARLINGTON_LAND_RECORDS_URL = "https://arlington.va.publicsearch.us/"

SOURCE_LAYER_NAME = "Virginia Parcels"
SOURCE_GEOMETRY_TYPE = "esriGeometryPolygon"
PROBE_VGIN_QPID = "5108700000001"
PROBE_LOCALITY_FIPS = "51087"

DEFAULT_PAGE_SIZE = 2_000
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = "vgin-parcels:v1:"
CURSOR_VERSION = 1

REQUIRED_FIELDS = (
    "OBJECTID",
    "VGIN_QPID",
    "FIPS",
    "LOCALITY",
    "PARCELID",
    "PTM_ID",
    "LASTUPDATE",
)
OPTIONAL_FIELDS = ("Shape__Area", "Shape__Length")

# Current Census county-equivalent GEOIDs: 95 counties and 38 independent
# cities. VGIN can additionally publish incorporated towns under seven-digit
# place codes, so those are reported separately rather than treated as extras.
EXPECTED_COUNTY_EQUIVALENT_GEOIDS = frozenset(
    """
    51001 51003 51005 51007 51009 51011 51013 51015 51017 51019
    51021 51023 51025 51027 51029 51031 51033 51035 51036 51037
    51041 51043 51045 51047 51049 51051 51053 51057 51059 51061
    51063 51065 51067 51069 51071 51073 51075 51077 51079 51081
    51083 51085 51087 51089 51091 51093 51095 51097 51099 51101
    51103 51105 51107 51109 51111 51113 51115 51117 51119 51121
    51125 51127 51131 51133 51135 51137 51139 51141 51143 51145
    51147 51149 51153 51155 51157 51159 51161 51163 51165 51167
    51169 51171 51173 51175 51177 51179 51181 51183 51185 51187
    51191 51193 51195 51197 51199 51510 51520 51530 51540 51550
    51570 51580 51590 51595 51600 51610 51620 51630 51640 51650
    51660 51670 51678 51680 51683 51685 51690 51700 51710 51720
    51730 51735 51740 51750 51760 51770 51775 51790 51800 51810
    51820 51830 51840
    """.split()
)

SOURCE_WARNINGS = (
    "VGIN publishes parcel geometry and locality/parcel identifiers, not "
    "owner, assessment, tax, sale, deed, lien, or recorded-instrument data.",
    "VGIN describes the polygons as cartographic and spatial-analysis data, "
    "not legal descriptions, property surveys, or edge-matched boundaries.",
    "Local governments contribute on different schedules. Preserve each "
    "record's FIPS, LOCALITY, and LASTUPDATE and check the relevant local "
    "assessment or land-record source when current detail matters.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Virginia Geographic Information Network Statewide Parcels",
    source_role="statewide_parcel_discovery_geometry_and_local_source_routing",
    base_url=ITEM_PAGE_URL,
    dataset_id=ITEM_ID,
    metadata={
        "authority": "Commonwealth of Virginia",
        "operator": "Virginia Geographic Information Network",
        "official_arcgis_item": ITEM_API_URL,
        "current_service_resolved_at_runtime": True,
        "coverage": "Virginia local-government parcel submissions",
        "geometry_role": "cartographic_and_spatial_analysis",
        "attribute_scope": "locality_identification_and_parcel_id",
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_FIPS,
    name="Virginia",
    state_code=STATE_CODE,
)


class VirginiaParcelError(RuntimeError):
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
class Selection:
    where: str
    spatial_parameters: Mapping[str, Any]
    coverage_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceSnapshot:
    schema_fingerprint: str
    data_fingerprint: str
    item_modified: int
    layer_url: str
    native_page_size: int
    metadata: Mapping[str, Any]
    item_metadata: Mapping[str, Any]
    dataset_statistics: Mapping[str, int | None]


@dataclass(frozen=True)
class CursorState:
    criteria_fingerprint: str
    last_object_id: int
    total_count: int
    schema_fingerprint: str
    data_fingerprint: str
    layer_url: str


@dataclass(frozen=True)
class TraversalBatch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    remaining_count: int
    pages_fetched: int
    snapshot: SourceSnapshot
    error: PublicRecordsError | None = None


class VirginiaParcelClient(ArcGISRESTClient):
    """Resolve the current VGIN item and query its parcel layer."""

    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
    ) -> None:
        super().__init__(
            DEFAULT_LAYER_URL,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )

    def fetch_snapshot(self) -> SourceSnapshot:
        item = self._request_json(ITEM_API_URL, params={"f": "json"})
        if not isinstance(item, Mapping) or "error" in item:
            raise SourceResponseError(
                "VGIN returned invalid ArcGIS item metadata",
                url=ITEM_API_URL,
                details={"response": item},
            )
        layer_url = _extract_layer_url(item)
        self.layer_url = layer_url
        layer = self._request_json(layer_url, params={"f": "json"})
        if not isinstance(layer, Mapping) or "error" in layer:
            raise SourceResponseError(
                "VGIN returned invalid parcel-layer metadata",
                url=layer_url,
                details={"response": layer},
            )
        statistics = self.fetch_dataset_statistics()
        return _compatible_snapshot(item, layer, layer_url, statistics)

    def fetch_dataset_statistics(self) -> dict[str, int | None]:
        out_statistics = [
            {
                "statisticType": "min",
                "onStatisticField": "OBJECTID",
                "outStatisticFieldName": "min_object_id",
            },
            {
                "statisticType": "max",
                "onStatisticField": "OBJECTID",
                "outStatisticFieldName": "max_object_id",
            },
            {
                "statisticType": "count",
                "onStatisticField": "OBJECTID",
                "outStatisticFieldName": "row_count",
            },
            {
                "statisticType": "min",
                "onStatisticField": "LASTUPDATE",
                "outStatisticFieldName": "earliest_update",
            },
            {
                "statisticType": "max",
                "onStatisticField": "LASTUPDATE",
                "outStatisticFieldName": "latest_update",
            },
        ]
        payload = self._request_json(
            self.query_url,
            params={
                "where": "1=1",
                "outStatistics": canonical_json(out_statistics),
                "returnGeometry": "false",
                "f": "json",
            },
        )
        attributes = _single_attributes(
            payload,
            url=self.query_url,
            description="VGIN dataset-statistics response",
        )
        result: dict[str, int | None] = {}
        for field_name in (
            "min_object_id",
            "max_object_id",
            "row_count",
            "earliest_update",
            "latest_update",
        ):
            value = attributes.get(field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise SourceSchemaError(
                    "VGIN returned a non-integer dataset statistic",
                    url=self.query_url,
                    details={field_name: value},
                )
            result[field_name] = value
        row_count = result["row_count"]
        if row_count is None or row_count < 0:
            raise SourceSchemaError(
                "VGIN dataset statistics lack a valid row count",
                url=self.query_url,
                details={"row_count": row_count},
            )
        return result

    def fetch_count(
        self,
        where: str,
        spatial_parameters: Mapping[str, Any] | None = None,
    ) -> int:
        payload = self._request_json(
            self.query_url,
            params={
                **dict(spatial_parameters or {}),
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "VGIN returned an invalid count response",
                url=self.query_url,
                details={"response": payload},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "VGIN count is not a non-negative integer",
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
        spatial_parameters: Mapping[str, Any] | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        params: dict[str, Any] = {
            **dict(spatial_parameters or {}),
            "where": where,
            "outFields": "*",
            "returnGeometry": str(return_geometry).lower(),
            "orderByFields": "OBJECTID ASC",
            "resultRecordCount": record_count,
            "f": "json",
        }
        if return_geometry:
            params["outSR"] = 4326
        payload = self._request_json(self.query_url, params=params)
        return _feature_tuple(
            payload,
            url=self.query_url,
            description="VGIN feature response",
        )

    def fetch_locality_statistics(
        self,
        *,
        page_size: int,
    ) -> tuple[Mapping[str, Any], ...]:
        out_statistics = [
            {
                "statisticType": "count",
                "onStatisticField": "OBJECTID",
                "outStatisticFieldName": "parcel_count",
            },
            {
                "statisticType": "min",
                "onStatisticField": "LASTUPDATE",
                "outStatisticFieldName": "earliest_update",
            },
            {
                "statisticType": "max",
                "onStatisticField": "LASTUPDATE",
                "outStatisticFieldName": "latest_update",
            },
        ]
        records: list[Mapping[str, Any]] = []
        offset = 0
        seen_pages: set[str] = set()
        while True:
            payload = self._request_json(
                self.query_url,
                params={
                    "where": "1=1",
                    "outStatistics": canonical_json(out_statistics),
                    "groupByFieldsForStatistics": "FIPS,LOCALITY",
                    "orderByFields": "FIPS ASC,LOCALITY ASC",
                    "returnGeometry": "false",
                    "resultOffset": offset,
                    "resultRecordCount": page_size,
                    "f": "json",
                },
            )
            features = _feature_tuple(
                payload,
                url=self.query_url,
                description="VGIN locality-statistics response",
            )
            fingerprint = sha256_fingerprint(features)
            if features and fingerprint in seen_pages:
                raise SourceSchemaError(
                    "VGIN locality-statistics pagination repeated a page",
                    url=self.query_url,
                    details={"result_offset": offset},
                )
            seen_pages.add(fingerprint)
            for feature in features:
                attributes = feature.get("attributes")
                if not isinstance(attributes, Mapping):
                    raise SourceSchemaError(
                        "VGIN locality statistic lacks attributes",
                        url=self.query_url,
                    )
                records.append(dict(attributes))
            exceeded = (
                payload.get("exceededTransferLimit")
                if isinstance(payload, Mapping)
                else None
            )
            if exceeded is not True and len(features) < page_size:
                break
            if not features:
                raise SourceSchemaError(
                    "VGIN reported more locality groups without returning rows",
                    url=self.query_url,
                    details={"result_offset": offset},
                )
            offset += len(features)
        return tuple(records)

    def fetch_identity_audit(self) -> dict[str, Any]:
        null_qpid_count = self.fetch_count("VGIN_QPID IS NULL")
        blank_parcel_id_count = self.fetch_count("PARCELID IS NULL OR PARCELID = ''")
        payload = self._request_json(
            self.query_url,
            params={
                "where": "1=1",
                "outStatistics": canonical_json(
                    [
                        {
                            "statisticType": "count",
                            "onStatisticField": "OBJECTID",
                            "outStatisticFieldName": "record_count",
                        }
                    ]
                ),
                "groupByFieldsForStatistics": "VGIN_QPID",
                "havingClause": "COUNT(OBJECTID) > 1",
                "orderByFields": "record_count DESC",
                "resultRecordCount": 10,
                "returnGeometry": "false",
                "f": "json",
            },
        )
        duplicate_features = _feature_tuple(
            payload,
            url=self.query_url,
            description="VGIN duplicate-identifier audit response",
        )
        duplicate_examples = []
        for feature in duplicate_features:
            attributes = feature.get("attributes")
            if not isinstance(attributes, Mapping):
                raise SourceSchemaError(
                    "VGIN duplicate audit row lacks attributes",
                    url=self.query_url,
                )
            duplicate_examples.append(
                {
                    "vgin_qpid": _qpid_text(attributes.get("VGIN_QPID")),
                    "record_count": attributes.get("record_count"),
                }
            )
        return {
            "vgin_qpid_null_count": null_qpid_count,
            "vgin_qpid_duplicate_group_examples": duplicate_examples,
            "vgin_qpid_unique_and_complete_in_observed_release": (
                null_qpid_count == 0 and not duplicate_examples
            ),
            "blank_or_null_parcel_id_count": blank_parcel_id_count,
        }


def _feature_tuple(
    payload: Any,
    *,
    url: str,
    description: str,
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, Mapping) or "error" in payload:
        raise SourceResponseError(
            f"{description} was invalid",
            url=url,
            details={"response": payload},
        )
    features = payload.get("features")
    if not isinstance(features, list) or any(
        not isinstance(feature, Mapping) for feature in features
    ):
        raise SourceSchemaError(
            f"{description} lacks a valid features array",
            url=url,
        )
    return tuple(features)


def _single_attributes(
    payload: Any,
    *,
    url: str,
    description: str,
) -> Mapping[str, Any]:
    features = _feature_tuple(payload, url=url, description=description)
    if len(features) != 1:
        raise SourceSchemaError(
            f"{description} did not contain exactly one row",
            url=url,
            details={"row_count": len(features)},
        )
    attributes = features[0].get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            f"{description} row lacks attributes",
            url=url,
        )
    return attributes


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any, field_name: str = "selector") -> str:
    text = _clean_text(value)
    if not text:
        raise VirginiaParcelError(
            "blank_selector",
            f"{field_name} must not be blank",
            details={"field": field_name},
        )
    return text.replace("'", "''")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _source_code(value: Any) -> str:
    text = _clean_text(value)
    if text is None or not re.fullmatch(r"\d{5,8}", text):
        raise VirginiaParcelError(
            "invalid_locality_code",
            "FIPS/locality code must contain 5 to 8 digits",
            details={"value": text},
        )
    return text


def _qpid_selector(value: Any) -> str:
    text = _clean_text(value)
    if text is None or not text.isdigit() or int(text) <= 0:
        raise VirginiaParcelError(
            "invalid_vgin_qpid",
            "VGIN_QPID must be a positive integer",
        )
    parsed = int(text)
    if parsed > 9_007_199_254_740_991:
        raise VirginiaParcelError(
            "invalid_vgin_qpid",
            "VGIN_QPID exceeds ArcGIS exact-integer range",
        )
    return str(parsed)


def _date_epoch_ms(value: str, field_name: str) -> int:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise VirginiaParcelError(
            "invalid_date",
            f"{field_name} must use YYYY-MM-DD",
            details={"field": field_name, "value": value},
        ) from error
    return int(
        datetime(
            parsed.year,
            parsed.month,
            parsed.day,
            tzinfo=timezone.utc,
        ).timestamp()
        * 1000
    )


def _qpid_text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer():
            return str(int(value))
        return format(value, ".15g")
    text = _clean_text(value)
    if text and re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _epoch_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(
                    value / 1000,
                    tz=timezone.utc,
                )
                .date()
                .isoformat()
            )
        except (OSError, OverflowError, ValueError):
            return None
    return None


def _extract_layer_url(item: Mapping[str, Any]) -> str:
    description = item.get("description")
    if not isinstance(description, str):
        raise SourceSchemaError(
            "VGIN ArcGIS item lacks its published REST endpoint",
            url=ITEM_API_URL,
        )
    decoded = html.unescape(description)
    candidates = re.findall(
        r"https://[^\"'<>\s]+?/FeatureServer(?:/0)?",
        decoded,
        flags=re.IGNORECASE,
    )
    normalized: list[str] = []
    for candidate in candidates:
        candidate = candidate.rstrip("/")
        if not candidate.lower().endswith("/featureserver/0"):
            candidate = f"{candidate}/0"
        parsed = urlparse(candidate)
        hostname = (parsed.hostname or "").lower()
        if not (
            hostname == "virginia.gov"
            or hostname.endswith(".virginia.gov")
            or hostname == "arcgis.com"
            or hostname.endswith(".arcgis.com")
        ):
            continue
        if candidate not in normalized:
            normalized.append(candidate)
    preferred = [
        value
        for value in normalized
        if "/VA_Base_Layers/VA_Parcels/FeatureServer/0" in value
    ]
    if len(preferred) == 1:
        return preferred[0]
    if len(normalized) == 1:
        return normalized[0]
    raise SourceSchemaError(
        "VGIN ArcGIS item does not identify one current parcel FeatureServer",
        url=ITEM_API_URL,
        details={"candidate_layer_urls": normalized},
    )


def _compatible_snapshot(
    item: Mapping[str, Any],
    layer: Mapping[str, Any],
    layer_url: str,
    dataset_statistics: Mapping[str, int | None],
) -> SourceSnapshot:
    item_identity = {
        "id": item.get("id"),
        "type": item.get("type"),
        "owner": item.get("owner"),
        "access": item.get("access"),
    }
    expected_item = {
        "id": ITEM_ID,
        "type": "File Geodatabase",
        "owner": "VGIN",
        "access": "public",
    }
    if item_identity != expected_item:
        raise SourceSchemaError(
            "VGIN ArcGIS item identity changed",
            url=ITEM_API_URL,
            details={"expected": expected_item, "observed": item_identity},
        )
    layer_identity = {
        "name": layer.get("name"),
        "id": layer.get("id"),
        "object_id_field": layer.get("objectIdField"),
        "geometry_type": layer.get("geometryType"),
    }
    expected_layer = {
        "name": SOURCE_LAYER_NAME,
        "id": 0,
        "object_id_field": "OBJECTID",
        "geometry_type": SOURCE_GEOMETRY_TYPE,
    }
    if layer_identity != expected_layer:
        raise SourceSchemaError(
            "VGIN parcel-layer identity changed",
            url=layer_url,
            details={"expected": expected_layer, "observed": layer_identity},
        )
    if "Query" not in str(layer.get("capabilities", "")).split(","):
        raise SourceSchemaError(
            "VGIN parcel layer no longer declares query capability",
            url=layer_url,
        )
    advanced = layer.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping) or not (
        advanced.get("supportsOrderBy") is True
        and advanced.get("supportsStatistics") is True
    ):
        raise SourceSchemaError(
            "VGIN parcel layer lacks ordered/statistical query support",
            url=layer_url,
        )
    fields = layer.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "VGIN parcel metadata lacks field declarations",
            url=layer_url,
        )
    definitions = {
        str(field.get("name")): {
            "name": field.get("name"),
            "type": field.get("type"),
            "length": field.get("length"),
            "nullable": field.get("nullable"),
        }
        for field in fields
        if isinstance(field.get("name"), str)
    }
    missing = sorted(set(REQUIRED_FIELDS) - set(definitions))
    if missing:
        raise SourceSchemaError(
            "VGIN parcel layer is missing required fields",
            url=layer_url,
            details={"missing_fields": missing},
        )
    native_page_size = layer.get("maxRecordCount")
    if (
        isinstance(native_page_size, bool)
        or not isinstance(native_page_size, int)
        or native_page_size <= 0
    ):
        raise SourceSchemaError(
            "VGIN parcel layer lacks a usable maxRecordCount",
            url=layer_url,
            details={"maxRecordCount": native_page_size},
        )
    item_modified = item.get("modified")
    if (
        isinstance(item_modified, bool)
        or not isinstance(item_modified, int)
        or item_modified <= 0
    ):
        raise SourceSchemaError(
            "VGIN ArcGIS item lacks a valid modified marker",
            url=ITEM_API_URL,
            details={"modified": item_modified},
        )
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "item_identity": item_identity,
            "layer_identity": layer_identity,
            "field_definitions": definitions,
        }
    )
    data_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "item_modified": item_modified,
            "resolved_layer_url": layer_url,
            "dataset_statistics": dict(dataset_statistics),
        }
    )
    return SourceSnapshot(
        schema_fingerprint=schema_fingerprint,
        data_fingerprint=data_fingerprint,
        item_modified=item_modified,
        layer_url=layer_url,
        native_page_size=native_page_size,
        metadata=dict(layer),
        item_metadata=dict(item),
        dataset_statistics=dict(dataset_statistics),
    )


def _optional_locality_clauses(args: argparse.Namespace) -> list[str]:
    clauses: list[str] = []
    if getattr(args, "fips", None):
        clauses.append(f"FIPS='{_source_code(args.fips)}'")
    if getattr(args, "locality", None):
        locality = _sql_text(args.locality, "locality")
        clauses.append(f"LOCALITY='{locality}'")
    return clauses


def _search_clauses(args: argparse.Namespace) -> list[str]:
    clauses = _optional_locality_clauses(args)
    if getattr(args, "parcel_id", None):
        value = _sql_text(args.parcel_id, "parcel_id")
        clauses.append(f"PARCELID='{value}'")
    if getattr(args, "ptm_id", None):
        value = _sql_text(args.ptm_id, "ptm_id")
        clauses.append(f"PTM_ID='{value}'")
    if getattr(args, "vgin_qpid", None):
        value = _qpid_selector(args.vgin_qpid)
        clauses.append(f"VGIN_QPID={value}")
    if getattr(args, "updated_after", None):
        value = _date_epoch_ms(args.updated_after, "updated_after")
        clauses.append(f"LASTUPDATE >= {value}")
    if getattr(args, "updated_before", None):
        value = _date_epoch_ms(args.updated_before, "updated_before")
        clauses.append(f"LASTUPDATE < {value}")
    return clauses


def _parcel_clause(identifier: str, field: str) -> str:
    if field == "vgin-qpid":
        return f"VGIN_QPID={_qpid_selector(identifier)}"
    value = _sql_text(identifier, "parcel identifier")
    if field == "parcel-id":
        return f"PARCELID='{value}'"
    if field == "ptm-id":
        return f"PTM_ID='{value}'"
    clauses = [f"PARCELID='{value}'", f"PTM_ID='{value}'"]
    cleaned = _clean_text(identifier)
    if cleaned and cleaned.isdigit():
        try:
            clauses.append(f"VGIN_QPID={_qpid_selector(cleaned)}")
        except VirginiaParcelError:
            pass
    return "(" + " OR ".join(clauses) + ")"


def _selection_from_args(args: argparse.Namespace) -> Selection:
    operation = args.command
    if operation == "probe":
        return Selection(
            where=(f"VGIN_QPID={PROBE_VGIN_QPID} AND FIPS='{PROBE_LOCALITY_FIPS}'"),
            spatial_parameters={},
        )
    if operation == "parcel":
        clauses = [
            _parcel_clause(args.identifier, args.field),
            *_optional_locality_clauses(args),
        ]
        return Selection(
            where=" AND ".join(f"({clause})" for clause in clauses),
            spatial_parameters={},
        )
    if operation == "objectid":
        return Selection(
            where=f"OBJECTID={args.object_id}",
            spatial_parameters={},
        )
    if operation in {"search", "count"}:
        clauses = _search_clauses(args)
        if operation == "search" and not clauses and not getattr(args, "all", False):
            raise VirginiaParcelError(
                "missing_search_selector",
                "search needs at least one selector or --all",
            )
        return Selection(
            where=" AND ".join(f"({clause})" for clause in clauses) or "1=1",
            spatial_parameters={},
        )
    if operation in {"point", "bbox"}:
        clauses = _optional_locality_clauses(args)
        if operation == "point":
            if not (-180 <= args.longitude <= 180):
                raise VirginiaParcelError(
                    "invalid_longitude",
                    "longitude must be between -180 and 180",
                )
            if not (-90 <= args.latitude <= 90):
                raise VirginiaParcelError(
                    "invalid_latitude",
                    "latitude must be between -90 and 90",
                )
            geometry = f"{args.longitude},{args.latitude}"
            geometry_type = "esriGeometryPoint"
        else:
            if args.xmin >= args.xmax or args.ymin >= args.ymax:
                raise VirginiaParcelError(
                    "invalid_bbox",
                    "bbox minimums must be smaller than maximums",
                )
            geometry = ",".join(
                str(value) for value in (args.xmin, args.ymin, args.xmax, args.ymax)
            )
            geometry_type = "esriGeometryEnvelope"
        return Selection(
            where=" AND ".join(f"({clause})" for clause in clauses) or "1=1",
            spatial_parameters={
                "geometry": geometry,
                "geometryType": geometry_type,
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
            },
        )
    raise VirginiaParcelError(
        "unsupported_operation",
        f"unsupported Virginia parcel operation: {operation}",
    )


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.command
    parameters: dict[str, Any] = {}
    if operation == "parcel":
        parameters.update(
            {
                "identifier": args.identifier,
                "field": args.field,
                "fips": args.fips,
                "locality": args.locality,
                "return_geometry": bool(args.geometry),
            }
        )
    elif operation == "objectid":
        parameters.update(
            {
                "object_id": args.object_id,
                "return_geometry": bool(args.geometry),
            }
        )
    elif operation in {"search", "count"}:
        for name in (
            "fips",
            "locality",
            "parcel_id",
            "ptm_id",
            "vgin_qpid",
            "updated_after",
            "updated_before",
            "all",
        ):
            parameters[name] = getattr(args, name, None)
        if operation == "search":
            parameters["return_geometry"] = bool(args.geometry)
    elif operation == "point":
        parameters = {
            "longitude": args.longitude,
            "latitude": args.latitude,
            "fips": args.fips,
            "locality": args.locality,
            "return_geometry": bool(args.geometry),
        }
    elif operation == "bbox":
        parameters = {
            "xmin": args.xmin,
            "ymin": args.ymin,
            "xmax": args.xmax,
            "ymax": args.ymax,
            "fips": args.fips,
            "locality": args.locality,
            "return_geometry": bool(args.geometry),
        }
    elif operation == "probe":
        parameters = {
            "vgin_qpid": PROBE_VGIN_QPID,
            "fips": PROBE_LOCALITY_FIPS,
            "return_geometry": bool(args.geometry),
        }
    return parameters


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    requested_limit = None
    if args.command in {
        "parcel",
        "objectid",
        "search",
        "point",
        "bbox",
        "probe",
    }:
        requested_limit = 1 if args.command == "probe" else getattr(args, "limit", None)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
        ),
    )


def _criteria_fingerprint(
    selection: Selection,
    *,
    operation: str,
    return_geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "operation": operation,
            "where": selection.where,
            "spatial_parameters": dict(selection.spatial_parameters),
            "return_geometry": return_geometry,
            "ordering": "OBJECTID ASC",
            "fields": "*",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "last_oid": state.last_object_id,
        "total": state.total_count,
        "schema": state.schema_fingerprint,
        "data": state.data_fingerprint,
        "layer_url": state.layer_url,
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
        raise VirginiaParcelError(
            "invalid_cursor",
            "cursor does not belong to the VGIN parcel adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
        state = CursorState(
            criteria_fingerprint=str(payload["criteria"]),
            last_object_id=int(payload["last_oid"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
            data_fingerprint=str(payload["data"]),
            layer_url=str(payload["layer_url"]),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise VirginiaParcelError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if (
        payload.get("v") != CURSOR_VERSION
        or state.last_object_id < 0
        or state.total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.data_fingerprint)
        or not state.layer_url.startswith("https://")
    ):
        raise VirginiaParcelError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _validate_cursor(
    state: CursorState | None,
    *,
    criteria: str,
    snapshot: SourceSnapshot,
) -> None:
    if state is None:
        return
    if state.criteria_fingerprint != criteria:
        raise VirginiaParcelError(
            "cursor_query_mismatch",
            "cursor belongs to different query criteria",
        )
    if state.schema_fingerprint != snapshot.schema_fingerprint:
        raise VirginiaParcelError(
            "cursor_schema_changed",
            "VGIN schema changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    if state.layer_url != snapshot.layer_url:
        raise VirginiaParcelError(
            "cursor_service_changed",
            "the official VGIN item now links to a different parcel service; "
            "restart the query for one source snapshot",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_layer_url": state.layer_url,
                "current_layer_url": snapshot.layer_url,
            },
        )
    if state.data_fingerprint != snapshot.data_fingerprint:
        raise VirginiaParcelError(
            "cursor_snapshot_changed",
            "VGIN refreshed the parcel release after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_data_fingerprint": state.data_fingerprint,
                "current_data_fingerprint": snapshot.data_fingerprint,
            },
        )


def _object_id(feature: Mapping[str, Any]) -> int:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "VGIN feature lacks an attributes object",
            url="arcgis://feature",
        )
    value = attributes.get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceSchemaError(
            "VGIN feature lacks a valid OBJECTID",
            url="arcgis://feature",
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


def _snapshots_match(left: SourceSnapshot, right: SourceSnapshot) -> bool:
    return (
        left.schema_fingerprint == right.schema_fingerprint
        and left.data_fingerprint == right.data_fingerprint
        and left.layer_url == right.layer_url
    )


def _traverse(
    client: Any,
    *,
    operation: str,
    selection: Selection,
    limit: int | None,
    cursor: str | None,
    return_geometry: bool,
) -> TraversalBatch:
    start_snapshot = client.fetch_snapshot()
    criteria = _criteria_fingerprint(
        selection,
        operation=operation,
        return_geometry=return_geometry,
    )
    state = _decode_cursor(cursor)
    _validate_cursor(state, criteria=criteria, snapshot=start_snapshot)
    total_count = client.fetch_count(
        selection.where,
        selection.spatial_parameters,
    )
    if state is not None and state.total_count != total_count:
        raise VirginiaParcelError(
            "cursor_count_changed",
            "the matching VGIN count changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_total_count": state.total_count,
                "current_total_count": total_count,
            },
        )
    last_object_id = state.last_object_id if state is not None else None
    remaining_where = _keyset_where(selection.where, last_object_id)
    remaining_count = (
        total_count
        if last_object_id is None
        else client.fetch_count(
            remaining_where,
            selection.spatial_parameters,
        )
    )
    target = remaining_count if limit is None else min(limit, remaining_count)
    page_size = min(int(client.page_size), start_snapshot.native_page_size)
    collected: list[Mapping[str, Any]] = []
    pages_fetched = 0
    traversal_error: PublicRecordsError | None = None

    while len(collected) < target:
        requested = min(page_size, target - len(collected))
        page = client.fetch_page(
            where=_keyset_where(selection.where, last_object_id),
            record_count=requested,
            return_geometry=return_geometry,
            spatial_parameters=selection.spatial_parameters,
        )
        pages_fetched += 1
        if not page:
            traversal_error = _partial_error(
                "arcgis_traversal_ended_early",
                "VGIN traversal ended before its reported count",
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
                "VGIN returned more features than requested",
                details={"requested": requested, "returned": len(page)},
            )
            page = page[:requested]
        for feature in page:
            current_object_id = _object_id(feature)
            if last_object_id is not None and current_object_id <= last_object_id:
                traversal_error = _partial_error(
                    "arcgis_keyset_not_monotonic",
                    "VGIN repeated or reordered a keyset feature",
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
                "VGIN returned a short page before its reported count",
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
            "VGIN traversal did not return its reported target count",
            details={"target": target, "retrieved": len(collected)},
        )

    try:
        end_snapshot = client.fetch_snapshot()
        end_count = client.fetch_count(
            selection.where,
            selection.spatial_parameters,
        )
    except PublicRecordsHTTPError as error:
        if not collected:
            raise
        end_snapshot = start_snapshot
        end_count = total_count
        traversal_error = error.to_contract_error()

    if traversal_error is None and (
        not _snapshots_match(start_snapshot, end_snapshot) or end_count != total_count
    ):
        traversal_error = _partial_error(
            "source_changed_during_traversal",
            "VGIN parcel data changed during traversal",
            details={
                "start_count": total_count,
                "end_count": end_count,
                "start_data_fingerprint": start_snapshot.data_fingerprint,
                "end_data_fingerprint": end_snapshot.data_fingerprint,
                "start_layer_url": start_snapshot.layer_url,
                "end_layer_url": end_snapshot.layer_url,
            },
        )

    next_cursor = None
    if traversal_error is None and remaining_count > len(collected) and collected:
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria,
                last_object_id=_object_id(collected[-1]),
                total_count=total_count,
                schema_fingerprint=start_snapshot.schema_fingerprint,
                data_fingerprint=start_snapshot.data_fingerprint,
                layer_url=start_snapshot.layer_url,
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


def _source_snapshot_record(batch: TraversalBatch) -> dict[str, Any]:
    snapshot = batch.snapshot
    return {
        "reported_total_matches": batch.total_count,
        "reported_remaining_matches_at_start": batch.remaining_count,
        "pages_fetched": batch.pages_fetched,
        "schema_fingerprint": snapshot.schema_fingerprint,
        "data_fingerprint": snapshot.data_fingerprint,
        "arcgis_item_modified_epoch_ms": snapshot.item_modified,
        "resolved_layer_url": snapshot.layer_url,
        "native_page_size": snapshot.native_page_size,
        "dataset_statistics": dict(snapshot.dataset_statistics),
    }


def _geography_type(fips: str | None, locality: str | None) -> str:
    if fips and len(fips) == 7:
        return "incorporated_town_place"
    if locality:
        lowered = locality.casefold()
        if lowered.endswith(" county"):
            return "county"
        if lowered.endswith(" city"):
            return "independent_city"
        if lowered.endswith(" town"):
            return "incorporated_town"
    if fips and len(fips) == 5:
        return "county_equivalent"
    return "source_locality"


def _record_routes(
    *,
    fips: str | None,
    locality: str | None,
    parcel_id: str | None,
    ptm_id: str | None,
) -> dict[str, Any]:
    routing_keys = {
        "source_locality_code": fips,
        "locality_name": locality,
        "parcel_id": parcel_id,
        "parcel_tax_map_id": ptm_id,
    }
    return {
        "local_assessment_and_tax": {
            "route_id": "local-assessor-commissioner-gis-or-treasurer",
            "directory_url": VIRGINIA_TAX_LOCALITIES_URL,
            "routing_keys": routing_keys,
            "adds": (
                "owner publication, situs and mailing address, assessed "
                "values, property characteristics, exemptions, tax status, "
                "and locality-specific sale history where published"
            ),
        },
        "recorded_land_instruments": {
            "source_id": "us-va-secure-remote-access-land-records",
            "url": SRA_INFO_URL,
            "portal_url": SRA_PORTAL_URL,
            "court_directory_url": CIRCUIT_DIRECTORY_URL,
            "routing_keys": routing_keys,
            "adds": (
                "deeds, deeds of trust, releases, judgments, wills, financing "
                "statements, party indexes, instrument identifiers, and images "
                "for participating Circuit Court clerks"
            ),
        },
    }


def _normalize_feature(
    feature: Mapping[str, Any],
    batch: TraversalBatch,
    *,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise SourceSchemaError(
            "VGIN feature lacks attributes",
            url=batch.snapshot.layer_url,
        )
    attributes = dict(attributes_value)
    object_id = _object_id(feature)
    qpid = _qpid_text(attributes.get("VGIN_QPID"))
    fips = _clean_text(attributes.get("FIPS"))
    locality = _clean_text(attributes.get("LOCALITY"))
    parcel_id = _clean_text(attributes.get("PARCELID"))
    ptm_id = _clean_text(attributes.get("PTM_ID"))
    native_id = qpid or f"OBJECTID:{object_id}"
    jurisdiction_geoid = fips or STATE_FIPS
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        jurisdiction_geoid,
        "parcel",
        native_id,
    )
    identity_basis = (
        "vgin_qpid" if qpid is not None else "object_id_fallback_missing_vgin_qpid"
    )
    result = {
        "source_id": SOURCE_ID,
        "record_type": "parcel_geometry",
        "source_record_id": (
            f"VGIN_QPID:{qpid}" if qpid is not None else f"OBJECTID:{object_id}"
        ),
        "canonical_ref": canonical_ref,
        "object_id": object_id,
        "vgin_qpid": qpid,
        "identity": {
            "basis": identity_basis,
            "durable_source_key": qpid,
            "transport_locator": object_id,
            "local_join_fields": {
                "fips": fips,
                "parcel_id": parcel_id,
                "parcel_tax_map_id": ptm_id,
            },
        },
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "source_locality_code": fips,
            "locality_name": locality,
            "geography_type": _geography_type(fips, locality),
        },
        "parcel_identifiers": {
            "parcel_id": parcel_id,
            "parcel_tax_map_id": ptm_id,
            "join_candidates": [
                {
                    "field": field_name,
                    "value": value,
                    "source_locality_code": fips,
                }
                for field_name, value in (
                    ("PARCELID", parcel_id),
                    ("PTM_ID", ptm_id),
                )
                if value is not None
            ],
        },
        "source_dates": {
            "last_update": _epoch_date(attributes.get("LASTUPDATE")),
            "last_update_epoch_ms": attributes.get("LASTUPDATE"),
            "meaning": "locality-contributed parcel geography update",
        },
        "measurements": {
            "source_shape_area": attributes.get("Shape__Area"),
            "source_shape_length": attributes.get("Shape__Length"),
            "source_crs": "layer_native_web_mercator",
        },
        "coverage_role": "parcel_discovery_geometry_and_local_source_routing",
        "related_routes": _record_routes(
            fips=fips,
            locality=locality,
            parcel_id=parcel_id,
            ptm_id=ptm_id,
        ),
        "source_snapshot": _source_snapshot_record(batch),
        "raw_attributes": attributes,
    }
    if geometry_requested and "geometry" in feature:
        result.update(
            {
                "geometry": feature.get("geometry"),
                "geometry_format": "esri_json",
                "geometry_crs": "EPSG:4326",
                "geometry_role": "cartographic_parcel_polygon",
            }
        )
    return result


def _alternative_routes() -> list[dict[str, Any]]:
    return [
        {
            "source_id": SOURCE_ID,
            "route_id": "official-current-feature-service",
            "name": "VGIN current statewide parcel FeatureServer",
            "url": ITEM_PAGE_URL,
            "resolved_from": ITEM_ID,
            "access": "anonymous ArcGIS REST",
            "adds": "bounded query, spatial lookup, parcel IDs, and geometry",
            "relationship_to_primary": "primary live query route",
        },
        {
            "source_id": SOURCE_ID,
            "route_id": "official-bulk-downloads",
            "name": "VGIN File Geodatabase and shapefile downloads",
            "url": ITEM_DATA_URL,
            "shapefile_url": SHAPEFILE_URL,
            "local_schema_tables_url": LOCAL_SCHEMA_TABLES_URL,
            "access": "anonymous bulk download",
            "adds": (
                "reproducible statewide snapshot and locality schema tables "
                "for high-volume joins"
            ),
            "relationship_to_primary": "bulk representation of the VGIN lineage",
        },
        {
            "route_id": "local-assessor-commissioner-gis-or-treasurer",
            "name": "Virginia locality assessment, GIS, and real-estate tax systems",
            "url": VIRGINIA_TAX_LOCALITIES_URL,
            "authority": (
                "county or city assessor, Commissioner of the Revenue, "
                "Treasurer, or local GIS office"
            ),
            "routing_keys": ["FIPS", "LOCALITY", "PARCELID", "PTM_ID"],
            "access": "locality-specific public portal, download, or office",
            "adds": (
                "owner publication, addresses, assessment and tax history, "
                "property characteristics, exemptions, and local sale fields"
            ),
            "relationship_to_primary": (
                "richer local administrative record joined through VGIN "
                "locality and parcel identifiers"
            ),
        },
        {
            "source_id": "us-va-secure-remote-access-land-records",
            "route_id": "circuit-court-land-records",
            "name": "Virginia Secure Remote Access to Land Records",
            "url": SRA_INFO_URL,
            "portal_url": SRA_PORTAL_URL,
            "court_directory_url": CIRCUIT_DIRECTORY_URL,
            "authority": (
                "Supreme Court of Virginia and participating Circuit Court Clerks"
            ),
            "routing_keys": [
                "LOCALITY",
                "PARCELID or PTM_ID",
                "party",
                "instrument number",
                "book and page",
            ],
            "access": (
                "free index where enabled; clerk registration and local fees "
                "for participating image access"
            ),
            "adds": (
                "deeds, deeds of trust, releases, judgments, wills, financing "
                "statements, instrument metadata, party indexes, and images"
            ),
            "relationship_to_primary": "document-level title and lien evidence",
        },
        {
            "source_id": "us-va-arlington-property-map",
            "route_id": "arlington-rich-assessment-example",
            "name": "Arlington County Property Map",
            "url": ARLINGTON_PROPERTY_URL,
            "jurisdiction_geoid": "51013",
            "routing_keys": ["FIPS=51013", "PARCELID", "PTM_ID"],
            "access": "anonymous ArcGIS query",
            "adds": (
                "RPC, owner-mailing address without name, assessed values, "
                "classification, zoning, legal description, lot size, and "
                "exemptions"
            ),
            "relationship_to_primary": (
                "implemented richer locality layer for Arlington parcels"
            ),
        },
        {
            "source_id": "us-va-arlington-land-records-publicsearch",
            "route_id": "arlington-recorded-instruments-example",
            "name": "Arlington Circuit Court Land Records PublicSearch",
            "url": ARLINGTON_LAND_RECORDS_URL,
            "jurisdiction_geoid": "51013",
            "routing_keys": [
                "parcel identifier",
                "party",
                "instrument number",
                "book and page",
            ],
            "access": "registered index; source-advertised image fees",
            "adds": (
                "deed, judgment, financing-statement, and wills indexes plus "
                "recorded document images"
            ),
            "relationship_to_primary": (
                "recorded-instrument complement for Arlington parcels"
            ),
        },
    ]


def alternative_routes() -> list[dict[str, Any]]:
    """Return the official bulk, local-administration, and title complements."""

    return _alternative_routes()


def _metadata_record(snapshot: SourceSnapshot) -> dict[str, Any]:
    layer = snapshot.metadata
    fields = layer.get("fields")
    return {
        "source_id": SOURCE_ID,
        "record_type": "source_contract",
        "official_arcgis_item_id": ITEM_ID,
        "official_arcgis_item_url": ITEM_PAGE_URL,
        "resolved_layer_url": snapshot.layer_url,
        "resolution_method": "FeatureServer link in official item description",
        "layer_name": layer.get("name"),
        "geometry_type": layer.get("geometryType"),
        "object_id_field": layer.get("objectIdField"),
        "native_page_size": snapshot.native_page_size,
        "supported_query_formats": layer.get("supportedQueryFormats"),
        "field_count": len(fields) if isinstance(fields, list) else None,
        "required_fields": list(REQUIRED_FIELDS),
        "optional_fields_present": [
            field_name
            for field_name in OPTIONAL_FIELDS
            if any(
                isinstance(field, Mapping) and field.get("name") == field_name
                for field in (fields or [])
            )
        ],
        "schema_fingerprint": snapshot.schema_fingerprint,
        "data_fingerprint": snapshot.data_fingerprint,
        "arcgis_item_modified_epoch_ms": snapshot.item_modified,
        "dataset_statistics": dict(snapshot.dataset_statistics),
        "identity_contract": {
            "durable_source_key": "VGIN_QPID",
            "transport_locator": "OBJECTID",
            "local_join_fields": ["FIPS", "PARCELID", "PTM_ID"],
        },
        "attribute_scope": (
            "parcel geometry, VGIN/local parcel identifiers, locality, "
            "and locality-contributed update date"
        ),
        "bulk_routes": {
            "file_geodatabase": ITEM_DATA_URL,
            "shapefile": SHAPEFILE_URL,
            "local_schema_tables": LOCAL_SCHEMA_TABLES_URL,
        },
    }


def _locality_coverage_record(
    rows: Sequence[Mapping[str, Any]],
    snapshot: SourceSnapshot,
) -> dict[str, Any]:
    localities: list[dict[str, Any]] = []
    observed_county_equivalents: set[str] = set()
    observed_town_codes: set[str] = set()
    grouped_total = 0
    for row in rows:
        fips = _clean_text(row.get("FIPS"))
        locality = _clean_text(row.get("LOCALITY"))
        count = row.get("parcel_count")
        earliest = row.get("earliest_update")
        latest = row.get("latest_update")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "VGIN locality statistics contain an invalid parcel count",
                url=snapshot.layer_url,
                details={"row": dict(row)},
            )
        for field_name, value in (
            ("earliest_update", earliest),
            ("latest_update", latest),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise SourceSchemaError(
                    "VGIN locality statistics contain an invalid date",
                    url=snapshot.layer_url,
                    details={"field": field_name, "value": value},
                )
        grouped_total += count
        if fips in EXPECTED_COUNTY_EQUIVALENT_GEOIDS:
            observed_county_equivalents.add(fips)
        elif fips and len(fips) == 7:
            observed_town_codes.add(fips)
        localities.append(
            {
                "source_locality_code": fips,
                "locality_name": locality,
                "geography_type": _geography_type(fips, locality),
                "parcel_count": count,
                "earliest_update": _epoch_date(earliest),
                "earliest_update_epoch_ms": earliest,
                "latest_update": _epoch_date(latest),
                "latest_update_epoch_ms": latest,
            }
        )
    expected_total = snapshot.dataset_statistics.get("row_count")
    if grouped_total != expected_total:
        raise SourceSchemaError(
            "VGIN locality groups do not reconcile to the statewide count",
            url=snapshot.layer_url,
            details={
                "grouped_total": grouped_total,
                "statewide_row_count": expected_total,
            },
        )
    localities.sort(
        key=lambda record: (
            record["source_locality_code"] or "",
            record["locality_name"] or "",
        )
    )
    latest_rows = [
        record for record in localities if record["latest_update_epoch_ms"] is not None
    ]
    oldest_latest = (
        min(
            latest_rows,
            key=lambda record: record["latest_update_epoch_ms"],
        )
        if latest_rows
        else None
    )
    newest_latest = (
        max(
            latest_rows,
            key=lambda record: record["latest_update_epoch_ms"],
        )
        if latest_rows
        else None
    )
    return {
        "source_id": SOURCE_ID,
        "record_type": "locality_coverage",
        "statewide_parcel_count": grouped_total,
        "source_locality_group_count": len(localities),
        "expected_current_county_equivalent_count": len(
            EXPECTED_COUNTY_EQUIVALENT_GEOIDS
        ),
        "observed_county_equivalent_count": len(observed_county_equivalents),
        "missing_county_equivalent_geoids": sorted(
            EXPECTED_COUNTY_EQUIVALENT_GEOIDS - observed_county_equivalents
        ),
        "incorporated_town_code_count": len(observed_town_codes),
        "incorporated_town_codes": sorted(observed_town_codes),
        "oldest_locality_latest_update": oldest_latest,
        "newest_locality_latest_update": newest_latest,
        "localities": localities,
        "source_snapshot": {
            "resolved_layer_url": snapshot.layer_url,
            "schema_fingerprint": snapshot.schema_fingerprint,
            "data_fingerprint": snapshot.data_fingerprint,
            "arcgis_item_modified_epoch_ms": snapshot.item_modified,
        },
    }


def _result_from_batch(
    query: PublicRecordsQuery,
    batch: TraversalBatch,
    records: Sequence[Mapping[str, Any]],
    warnings: Sequence[str],
) -> PublicRecordsResult:
    if batch.error is not None:
        status = ResultStatus.PARTIAL if records else ResultStatus.SOURCE_CHANGED
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


def _client_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "page_size": getattr(args, "page_size", DEFAULT_PAGE_SIZE),
        "timeout": getattr(args, "timeout", DEFAULT_TIMEOUT),
        "minimum_interval": getattr(
            args,
            "minimum_interval",
            DEFAULT_MINIMUM_INTERVAL,
        ),
        "retry_attempts": getattr(args, "retry_attempts", 3),
    }


def _stable_snapshot_operation(
    client: Any,
    operation: Any,
) -> tuple[SourceSnapshot, Any]:
    start = client.fetch_snapshot()
    value = operation(start)
    end = client.fetch_snapshot()
    if not _snapshots_match(start, end):
        raise VirginiaParcelError(
            "source_changed_during_operation",
            "VGIN parcel data changed during the operation",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "start_data_fingerprint": start.data_fingerprint,
                "end_data_fingerprint": end.data_fingerprint,
                "start_layer_url": start.layer_url,
                "end_layer_url": end.layer_url,
            },
        )
    return start, value


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    source_client = client
    try:
        if args.command == "alternatives":
            result = PublicRecordsResult.success(query, alternative_routes())
        else:
            source_client = source_client or VirginiaParcelClient(**_client_args(args))
            if args.command == "metadata":
                snapshot = source_client.fetch_snapshot()
                result = PublicRecordsResult.success(
                    query,
                    [_metadata_record(snapshot)],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "identity-audit":
                snapshot, audit = _stable_snapshot_operation(
                    source_client,
                    lambda _snapshot: source_client.fetch_identity_audit(),
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "record_type": "identity_audit",
                            **audit,
                            "identity_contract": {
                                "durable_source_key": "VGIN_QPID",
                                "transport_locator": "OBJECTID",
                                "local_join_fields": [
                                    "FIPS",
                                    "PARCELID",
                                    "PTM_ID",
                                ],
                            },
                            "source_snapshot": {
                                "resolved_layer_url": snapshot.layer_url,
                                "schema_fingerprint": (snapshot.schema_fingerprint),
                                "data_fingerprint": snapshot.data_fingerprint,
                            },
                        }
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "localities":
                snapshot, rows = _stable_snapshot_operation(
                    source_client,
                    lambda current: source_client.fetch_locality_statistics(
                        page_size=min(
                            int(source_client.page_size),
                            current.native_page_size,
                        )
                    ),
                )
                result = PublicRecordsResult.success(
                    query,
                    [_locality_coverage_record(rows, snapshot)],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "count":
                selection = _selection_from_args(args)
                snapshot, count = _stable_snapshot_operation(
                    source_client,
                    lambda _snapshot: source_client.fetch_count(
                        selection.where,
                        selection.spatial_parameters,
                    ),
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "record_type": "source_count",
                            "count": count,
                            "where": selection.where,
                            "spatial_parameters": dict(selection.spatial_parameters),
                            "resolved_layer_url": snapshot.layer_url,
                            "schema_fingerprint": (snapshot.schema_fingerprint),
                            "data_fingerprint": snapshot.data_fingerprint,
                        }
                    ],
                    warnings=(*SOURCE_WARNINGS, *selection.coverage_notes),
                )
            else:
                selection = _selection_from_args(args)
                limit = 1 if args.command == "probe" else args.limit
                batch = _traverse(
                    source_client,
                    operation=args.command,
                    selection=selection,
                    limit=limit,
                    cursor=getattr(args, "cursor", None),
                    return_geometry=bool(args.geometry),
                )
                records = [
                    _normalize_feature(
                        feature,
                        batch,
                        geometry_requested=bool(args.geometry),
                    )
                    for feature in batch.records
                ]
                result = _result_from_batch(
                    query,
                    batch,
                    records,
                    (*SOURCE_WARNINGS, *selection.coverage_notes),
                )
    except VirginiaParcelError as error:
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
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
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
        summary=f"Virginia VGIN parcels {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Virginia VGIN parcels {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command == "alternatives":
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "metadata":
            print(f"  {record['layer_name']} | {record['resolved_layer_url']}")
        elif args.command == "localities":
            print(
                f"  {record['source_locality_group_count']} locality groups | "
                f"{record['statewide_parcel_count']} parcels"
            )
        elif args.command == "identity-audit":
            print(
                "  VGIN_QPID complete/unique: "
                f"{record['vgin_qpid_unique_and_complete_in_observed_release']}"
            )
        elif args.command == "count":
            print(f"  {record['count']} | {record['where']}")
        else:
            print(
                f"  {record['vgin_qpid'] or record['source_record_id']} | "
                f"{record['parcel_identifiers']['parcel_id'] or '?'} | "
                f"{record['jurisdiction']['locality_name'] or '?'}"
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
        type=_positive_int,
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
        help="Return source parcel geometry in EPSG:4326",
    )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="Transport batch size, bounded by live source metadata",
    )
    parser.add_argument(
        "--timeout",
        type=_nonnegative_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=_positive_int, default=3)
    add_output_args(parser)


def _add_metadata_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
    )
    parser.add_argument(
        "--timeout",
        type=_nonnegative_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=_positive_int, default=3)
    add_output_args(parser)


def _add_locality_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fips", help="Exact VGIN locality/FIPS code")
    parser.add_argument("--locality", help="Exact VGIN LOCALITY name")


def _add_search_args(
    parser: argparse.ArgumentParser,
    *,
    allow_all: bool,
) -> None:
    _add_locality_args(parser)
    parser.add_argument("--parcel-id", help="Exact PARCELID")
    parser.add_argument("--ptm-id", help="Exact PTM_ID")
    parser.add_argument("--vgin-qpid", help="Exact statewide VGIN_QPID")
    parser.add_argument(
        "--updated-after",
        help="LASTUPDATE on or after YYYY-MM-DD",
    )
    parser.add_argument(
        "--updated-before",
        help="LASTUPDATE before YYYY-MM-DD",
    )
    if allow_all:
        parser.add_argument(
            "--all",
            action="store_true",
            help="Select the statewide layer when no narrower selector is set",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Query VGIN statewide parcel discovery, identifiers, and geometry")
    )
    subparsers = parser.add_subparsers(dest="command")

    parcel = subparsers.add_parser(
        "parcel",
        help="Search an exact VGIN or local parcel identifier",
    )
    parcel.add_argument("identifier")
    parcel.add_argument(
        "--field",
        choices=("auto", "parcel-id", "ptm-id", "vgin-qpid"),
        default="auto",
    )
    _add_locality_args(parcel)
    _add_network_args(parcel)

    objectid = subparsers.add_parser(
        "objectid",
        help="Fetch one ArcGIS OBJECTID transport locator",
    )
    objectid.add_argument("object_id", type=_positive_int)
    _add_network_args(objectid)

    search = subparsers.add_parser(
        "search",
        help="Combine locality, parcel-ID, and update-date selectors",
    )
    _add_search_args(search, allow_all=True)
    _add_network_args(search)

    count = subparsers.add_parser(
        "count",
        help="Count a selected source population",
    )
    _add_search_args(count, allow_all=False)
    _add_metadata_network_args(count)

    point = subparsers.add_parser(
        "point",
        help="Find parcels intersecting a WGS84 point",
    )
    point.add_argument("longitude", type=float)
    point.add_argument("latitude", type=float)
    _add_locality_args(point)
    _add_network_args(point, geometry_default=True)

    bbox = subparsers.add_parser(
        "bbox",
        help="Find parcels intersecting a WGS84 bounding box",
    )
    bbox.add_argument("xmin", type=float)
    bbox.add_argument("ymin", type=float)
    bbox.add_argument("xmax", type=float)
    bbox.add_argument("ymax", type=float)
    _add_locality_args(bbox)
    _add_network_args(bbox, geometry_default=True)

    metadata = subparsers.add_parser(
        "metadata",
        help="Resolve and validate the current official source contract",
    )
    _add_metadata_network_args(metadata)

    localities = subparsers.add_parser(
        "localities",
        help="Report locality coverage, counts, and update dates",
    )
    _add_metadata_network_args(localities)

    identity_audit = subparsers.add_parser(
        "identity-audit",
        help="Audit VGIN_QPID completeness and duplicate groups",
    )
    _add_metadata_network_args(identity_audit)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="List bulk, local assessment, and recorded-instrument routes",
    )
    add_output_args(alternatives)

    probe = subparsers.add_parser(
        "probe",
        help="Run one exact live VGIN parcel sentinel",
    )
    _add_network_args(probe, geometry_default=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
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
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
