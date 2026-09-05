#!/usr/bin/env python3
"""Query NYC Department of Finance Property Information Portal layers.

The Property Information Portal (PIP) is backed by a related family of public
NYC Department of Finance ArcGIS layers.  This adapter preserves the durable
ten-digit borough-block-lot identifier (BBL) separately from each layer's
``OBJECTID`` occurrence and from annual assessment child identities.

Omitting ``--limit`` and ``--max-records`` exhausts the native ArcGIS result
pages for owner, address, and component searches.  Exact BBL bundles and the
sentinel probe query every matching row in each component.

Examples:
    uv run python tools/query_nyc_pip.py bbl 1013860010 --json
    uv run python tools/query_nyc_pip.py lot Manhattan 1386 10 --json
    uv run python tools/query_nyc_pip.py owner "BOLT 1 L.P." --json
    uv run python tools/query_nyc_pip.py address "9 E 71st St" --json
    uv run python tools/query_nyc_pip.py detail 1013860010 --json
    uv run python tools/query_nyc_pip.py geometry 1013860010 --json
    uv run python tools/query_nyc_pip.py current-assessment 1013860010 --json
    uv run python tools/query_nyc_pip.py assessment-history 1013860010 --json
    uv run python tools/query_nyc_pip.py exemptions 1013860010 --json
    uv run python tools/query_nyc_pip.py discovery metadata --json
    uv run python tools/query_nyc_pip.py probe --json
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

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
        PaginatedFetch,
        PublicRecordsHTTPError,
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
        PaginatedFetch,
        PublicRecordsHTTPError,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-nyc-property-information-portal"
SOURCE_NAME = "NYC Property Information Portal"
STATE_CODE = "NY"
NYC_GEOID = "3651000"
OBSERVED_AT = "2026-07-31"

PIP_URL = "https://propertyinformationportal.nyc.gov/"
DOF_LINKER_URL = (
    "https://home4.nyc.gov/site/finance/property/"
    "property-digital-tax-map.page"
)
ACRIS_URL = "https://www.nyc.gov/site/finance/property/acris.page"
RICHMOND_CLERK_URL = (
    "https://richmondcountyclerk.com/Search/SearchIndex"
)
ARCGIS_ROOT = (
    "https://services6.arcgis.com/yG5s3afENB5iO9fj/ArcGIS/rest/services"
)

DEFAULT_PAGE_SIZE = 1_000
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.0

PROBE_BBL = "1013860010"
PROBE_HOUSE_NUMBER = "9"
PROBE_STREET = "EAST 71 STREET"

BOROUGHS: Mapping[str, Mapping[str, str]] = {
    "1": {
        "name": "Manhattan",
        "county_name": "New York",
        "county_geoid": "36061",
    },
    "2": {
        "name": "Bronx",
        "county_name": "Bronx",
        "county_geoid": "36005",
    },
    "3": {
        "name": "Brooklyn",
        "county_name": "Kings",
        "county_geoid": "36047",
    },
    "4": {
        "name": "Queens",
        "county_name": "Queens",
        "county_geoid": "36081",
    },
    "5": {
        "name": "Staten Island",
        "county_name": "Richmond",
        "county_geoid": "36085",
    },
}

BOROUGH_ALIASES = {
    "1": "1",
    "manhattan": "1",
    "newyork": "1",
    "newyorkcounty": "1",
    "2": "2",
    "bronx": "2",
    "bronxcounty": "2",
    "3": "3",
    "brooklyn": "3",
    "kings": "3",
    "kingscounty": "3",
    "4": "4",
    "queens": "4",
    "queenscounty": "4",
    "5": "5",
    "statenisland": "5",
    "richmond": "5",
    "richmondcounty": "5",
}

DETAIL_FIELDS = (
    "OBJECTID",
    "JUR",
    "PARID",
    "BORO",
    "BLOCK",
    "LOT",
    "PERIOD",
    "TAXYR",
    "CAMAB_YR",
    "NOV_YR",
    "RECTYPE",
    "BLDG_CLASS",
    "TAX_CLASS",
    "HOUSENUM",
    "STREET_NAME",
    "ZIP_CODE",
    "OWNER",
    "BLD_FRT",
    "BLD_DEP",
    "BLD_STORY",
    "YRBUILT",
    "GROSS_SQFT",
    "ZONING",
    "LOT_FRT",
    "LOT_DEP",
    "LAND_AREA",
    "UNITNO",
    "BUILDING_NAME",
    "COMMUNITY_NBHD",
    "RESIDENTIAL_SQFT",
    "COMMERCIAL_SQFT",
    "TOTAL_UNITS",
    "COMMERCIAL_UNITS",
    "RESIDENTIAL_UNITS",
    "CITYNAME",
    "EXTERIOR_CONDITION",
    "STYLE",
    "CONSTRUCTION_TYPE",
    "EXTERIOR_WALL",
    "PROXIMITY",
    "BASEMENT_TYPE",
    "BLDG_CLASS_DESC",
    "NUM_BLDGS",
)

TAX_LOT_FIELDS = (
    "OBJECTID",
    "BORO",
    "BLOCK",
    "LOT",
    "BBL",
    "CONDO_FLAG",
    "REUC_FLAG",
    "AIR_LOT_FLAG",
    "SUB_LOT_FLAG",
    "EASEMENT_FLAG",
    "LOT_NOTE",
    "EFFECTIVE_TAX_YEAR",
    "BILL_BBL_FLAG",
    "NYCMAP_BLDG_FLAG",
    "CREATED_DATE",
    "LAST_EDITED_DATE",
    "Shape__Area",
    "Shape__Length",
)

CURRENT_ASSESSMENT_FIELDS = (
    "OBJECTID",
    "PARID",
    "TAXYR",
    "PERIOD",
    "PERIOD_LABEL",
    "FISCAL_YEAR",
    "MARKET_VALUE",
    "TAXABLE_AV",
    "TAXABLE_BILL_AV",
    "AV_EXEMPTIONS",
    "LAND_VALUE",
    "IMPROVEMENT_VALUE",
    "TOTAL_VALUE_CHANGE",
    "TAXABLE_BILL_AV_CHANGE",
)

ASSESSMENT_HISTORY_FIELDS = (
    "OBJECTID",
    "PARID",
    "TAXYR",
    "PERIOD",
    "FISCAL_YEAR",
    "MARKET_VALUE",
    "TAXABLE_AV",
    "TAXABLE_BILL_AV",
    "AV_EXEMPTIONS",
    "LAND_VALUE",
    "IMPROVEMENT_VALUE",
    "TOTAL_VALUE_CHANGE",
    "TAXABLE_BILL_AV_CHANGE",
    "BLDG_CLASS",
    "TAX_CLASS",
)

EXEMPTION_FIELDS = (
    "OBJECTID",
    "PARID_ORG",
    "PARID",
    "TAXYR",
    "F_TAXYR",
    "F_TAXABLE_AV",
    "F_EXEMPT_AV",
    "F_EXCODE",
    "F_EXEMPT_TYPE",
    "F_TAXABLE_BILL_AV",
    "SORT_ORDER",
)


@dataclass(frozen=True)
class LayerSpec:
    """Stable source-local contract for one PIP ArcGIS layer."""

    key: str
    url: str
    layer_id: int
    expected_name: str
    expected_type: str
    identity_field: str
    record_kind: str
    required_fields: tuple[str, ...]
    order_by: str
    geometry_type: str | None = None


LAYER_SPECS: Mapping[str, LayerSpec] = {
    "detail": LayerSpec(
        key="detail",
        url=(
            f"{ARCGIS_ROOT}/DTM_ETL_DAILY_view/"
            "FeatureServer/18"
        ),
        layer_id=18,
        expected_name="PTS_DESC_DAILY",
        expected_type="Table",
        identity_field="PARID",
        record_kind="nyc_dof_parcel_detail_observation",
        required_fields=DETAIL_FIELDS,
        order_by="OBJECTID ASC",
    ),
    "tax_lot": LayerSpec(
        key="tax_lot",
        url=(
            f"{ARCGIS_ROOT}/DTM_ETL_DAILY_view/"
            "FeatureServer/0"
        ),
        layer_id=0,
        expected_name="TAX_LOT_POLYGON",
        expected_type="Feature Layer",
        identity_field="BBL",
        record_kind="nyc_dof_tax_lot_geometry_observation",
        required_fields=TAX_LOT_FIELDS,
        order_by="OBJECTID ASC",
        geometry_type="esriGeometryPolygon",
    ),
    "current_assessment": LayerSpec(
        key="current_assessment",
        url=f"{ARCGIS_ROOT}/PROPMAST__VIEW/FeatureServer/0",
        layer_id=0,
        expected_name="PROPMAST",
        expected_type="Table",
        identity_field="PARID",
        record_kind="nyc_dof_current_assessment_observation",
        required_fields=CURRENT_ASSESSMENT_FIELDS,
        order_by="OBJECTID ASC",
    ),
    "assessment_history": LayerSpec(
        key="assessment_history",
        url=(
            f"{ARCGIS_ROOT}/PROPMAST_HIST_VIEW/"
            "FeatureServer/0"
        ),
        layer_id=0,
        expected_name="PROPMAST_HIST",
        expected_type="Table",
        identity_field="PARID",
        record_kind="nyc_dof_historical_assessment_observation",
        required_fields=ASSESSMENT_HISTORY_FIELDS,
        order_by="TAXYR DESC, PERIOD DESC, OBJECTID ASC",
    ),
    "exemptions": LayerSpec(
        key="exemptions",
        url=f"{ARCGIS_ROOT}/EXDET_PIP_VIEW/FeatureServer/0",
        layer_id=0,
        expected_name="EXDET_PIP",
        expected_type="Table",
        identity_field="PARID",
        record_kind="nyc_dof_exemption_observation",
        required_fields=EXEMPTION_FIELDS,
        order_by=(
            "TAXYR DESC, PARID_ORG ASC, F_EXCODE ASC, "
            "F_EXEMPT_TYPE ASC, SORT_ORDER ASC, OBJECTID ASC"
        ),
    ),
}

BUNDLE_LAYER_KEYS = (
    "detail",
    "tax_lot",
    "current_assessment",
    "assessment_history",
    "exemptions",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role=(
        "five_borough_parcel_tax_lot_assessment_and_exemption_context"
    ),
    base_url=PIP_URL,
    dataset_id="NYC-DOF-PIP-ArcGIS-layer-family",
    metadata={
        "authority": "New York City Department of Finance",
        "platform_family": "arcgis_feature_service_family",
        "coverage": "five New York City boroughs",
        "official_linker_url": DOF_LINKER_URL,
        "observed_at": OBSERVED_AT,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=NYC_GEOID,
    name="New York City",
    state_code=STATE_CODE,
    locality="New York City",
)

SOURCE_WARNINGS = (
    (
        "PIP owner names are Department of Finance tax-roll observations. "
        "Recorded instruments are the title-event source."
    ),
    (
        "PIP recent-recording displays represent ACRIS records and do not "
        "provide independent corroboration of those same instruments."
    ),
    (
        "Tax-lot polygons are cadastral map geometry rather than surveyed "
        "legal boundaries."
    ),
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "normalization_version": 1,
        "layers": {
            key: {
                "name": spec.expected_name,
                "type": spec.expected_type,
                "identity_field": spec.identity_field,
                "required_fields": spec.required_fields,
            }
            for key, spec in LAYER_SPECS.items()
        },
    }
)


class PIPArcGISClient(ArcGISRESTClient):
    """ArcGIS client with source-local layer metadata access."""

    def __init__(self, spec: LayerSpec, **kwargs: Any) -> None:
        self.spec = spec
        super().__init__(spec.url, **kwargs)

    def metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "PIP ArcGIS layer metadata must be an object",
                url=self.layer_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "PIP ArcGIS returned a layer metadata error",
                url=self.layer_url,
                details={"response": payload["error"]},
            )
        return payload


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()
    return text or None


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = _clean(value)
    if not text:
        return None
    cleaned = re.sub(r"[$,%\s]", "", text)
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _arcgis_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(
                value / 1_000,
                tz=timezone.utc,
            ).isoformat().replace("+00:00", "Z")
        except (OSError, OverflowError, ValueError):
            return None
    return _clean(value)


def _sql_literal(value: Any, field_name: str = "query") -> str:
    text = _clean(value)
    if text is None:
        raise ValueError(f"{field_name} must not be blank")
    return text.replace("'", "''")


def normalize_bbl(value: Any) -> str:
    """Return one canonical ten-digit NYC borough-block-lot identifier."""

    text = _clean(value)
    if text is None or not re.fullmatch(r"[0-9\s-]+", text):
        raise ValueError("BBL must contain ten digits")
    digits = re.sub(r"[\s-]", "", text)
    if len(digits) != 10 or not digits.isdigit():
        raise ValueError("BBL must contain ten digits")
    if digits[0] not in BOROUGHS:
        raise ValueError("BBL borough digit must be 1 through 5")
    block = int(digits[1:6])
    lot = int(digits[6:10])
    if block <= 0 or lot <= 0:
        raise ValueError("BBL block and lot must be positive")
    return digits


def _borough_code(value: Any) -> str:
    text = _clean(value)
    if text is None:
        raise ValueError("borough must not be blank")
    key = re.sub(r"[^a-z0-9]", "", text.casefold())
    code = BOROUGH_ALIASES.get(key)
    if code is None:
        raise ValueError(
            "borough must be 1-5 or a New York City borough name"
        )
    return code


def bbl_from_parts(borough: Any, block: Any, lot: Any) -> str:
    """Build a canonical BBL from separate borough, block, and lot values."""

    code = _borough_code(borough)
    try:
        block_number = int(str(block))
        lot_number = int(str(lot))
    except ValueError as error:
        raise ValueError("block and lot must be integers") from error
    if not 1 <= block_number <= 99_999:
        raise ValueError("block must be between 1 and 99999")
    if not 1 <= lot_number <= 9_999:
        raise ValueError("lot must be between 1 and 9999")
    return f"{code}{block_number:05d}{lot_number:04d}"


def bbl_parts(bbl: str) -> dict[str, Any]:
    """Return normalized borough, block, lot, and county attributes."""

    normalized = normalize_bbl(bbl)
    borough = BOROUGHS[normalized[0]]
    return {
        "bbl": normalized,
        "borough_code": normalized[0],
        "borough_name": borough["name"],
        "block": int(normalized[1:6]),
        "block_padded": normalized[1:6],
        "lot": int(normalized[6:10]),
        "lot_padded": normalized[6:10],
        "county_name": borough["county_name"],
        "county_geoid": borough["county_geoid"],
    }


def _bbl_from_attributes(
    attributes: Mapping[str, Any],
    spec: LayerSpec,
) -> str:
    raw_bbl = attributes.get(spec.identity_field)
    bbl = normalize_bbl(raw_bbl)
    parts = bbl_parts(bbl)
    borough = _clean(attributes.get("BORO"))
    block = _clean(attributes.get("BLOCK"))
    lot = _clean(attributes.get("LOT"))
    if borough is not None and borough != parts["borough_code"]:
        raise ValueError(
            f"{spec.key} borough field conflicts with BBL {bbl}"
        )
    if block is not None and int(block) != parts["block"]:
        raise ValueError(f"{spec.key} block field conflicts with BBL {bbl}")
    if lot is not None and int(lot) != parts["lot"]:
        raise ValueError(f"{spec.key} lot field conflicts with BBL {bbl}")
    return bbl


def validate_layer_metadata(
    metadata: Mapping[str, Any],
    spec: LayerSpec,
) -> dict[str, Any]:
    """Validate the identity, fields, and paging contract of one PIP layer."""

    observed_identity = {
        "id": metadata.get("id"),
        "name": _clean(metadata.get("name")),
        "type": _clean(metadata.get("type")),
        "object_id_field": _clean(metadata.get("objectIdField")),
        "geometry_type": _clean(metadata.get("geometryType")),
    }
    expected_identity = {
        "id": spec.layer_id,
        "name": spec.expected_name,
        "type": spec.expected_type,
        "object_id_field": "OBJECTID",
        "geometry_type": spec.geometry_type,
    }
    if observed_identity != expected_identity:
        raise SourceSchemaError(
            f"PIP {spec.key} layer identity changed",
            url=spec.url,
            details={
                "expected": expected_identity,
                "observed": observed_identity,
            },
        )

    capabilities = {
        item.strip()
        for item in str(metadata.get("capabilities") or "").split(",")
        if item.strip()
    }
    if "Query" not in capabilities:
        raise SourceSchemaError(
            f"PIP {spec.key} layer no longer declares Query",
            url=spec.url,
        )

    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            f"PIP {spec.key} layer has malformed field declarations",
            url=spec.url,
        )
    definitions = {
        str(field.get("name")): {
            key: field.get(key)
            for key in ("name", "type", "length", "nullable")
            if key in field
        }
        for field in fields
        if isinstance(field.get("name"), str)
    }
    missing = sorted(set(spec.required_fields) - set(definitions))
    if missing:
        raise SourceSchemaError(
            f"PIP {spec.key} layer is missing required fields",
            url=spec.url,
            details={"missing_fields": missing},
        )

    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping) or any(
        advanced.get(key) is not True
        for key in ("supportsPagination", "supportsOrderBy")
    ):
        raise SourceSchemaError(
            f"PIP {spec.key} ordered pagination contract changed",
            url=spec.url,
        )

    page_size = metadata.get("maxRecordCount")
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or page_size <= 0
    ):
        raise SourceSchemaError(
            f"PIP {spec.key} layer lacks a native page size",
            url=spec.url,
        )

    schema = {
        "layer_key": spec.key,
        "identity": observed_identity,
        "capabilities": sorted(capabilities),
        "supports_pagination": True,
        "supports_order_by": True,
        "native_page_size": page_size,
        "required_fields": {
            name: definitions[name] for name in spec.required_fields
        },
    }
    return {
        "native_page_size": page_size,
        "schema": schema,
        "schema_fingerprint": sha256_fingerprint(schema),
    }


def _feature_attributes(
    feature: Mapping[str, Any],
    spec: LayerSpec,
) -> dict[str, Any]:
    value = feature.get("attributes")
    if not isinstance(value, Mapping):
        raise ValueError(
            f"PIP {spec.key} feature attributes must be an object"
        )
    return dict(value)


def _base_record(
    *,
    bbl: str,
    spec: LayerSpec,
    attributes: Mapping[str, Any],
    response_schema_fingerprint: str,
    layer_schema_fingerprint: str,
) -> dict[str, Any]:
    parts = bbl_parts(bbl)
    object_id = _clean(attributes.get("OBJECTID"))
    if object_id is None:
        raise ValueError(f"PIP {spec.key} row lacks OBJECTID")
    parcel_ref = canonical_property_ref(
        SOURCE_ID,
        parts["county_geoid"],
        "parcel",
        bbl,
    )
    occurrence_native_id = f"{spec.key}:{bbl}:{object_id}"
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            parts["county_geoid"],
            f"{spec.key}_occurrence",
            occurrence_native_id,
        ),
        "parcel_canonical_ref": parcel_ref,
        "same_record_key": f"US-NYC:BBL:{bbl}",
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "source_url": spec.url,
        "viewer_url": PIP_URL,
        "record_kind": spec.record_kind,
        "record_scope": "nyc_dof_property_information_portal",
        "jurisdiction": {
            "state_code": STATE_CODE,
            "city": "New York City",
            "borough_code": parts["borough_code"],
            "borough_name": parts["borough_name"],
            "county_name": parts["county_name"],
            "county_geoid": parts["county_geoid"],
        },
        "bbl": bbl,
        "borough": parts["borough_code"],
        "block": parts["block"],
        "lot": parts["lot"],
        "native_parcel_id": bbl,
        "native_feature_id": object_id,
        "identity": {
            "parcel": {
                "basis": "nyc_bbl",
                "value": bbl,
                "durable": True,
                "projection_eligible_as_parcel": True,
            },
            "layer_occurrence": {
                "component": spec.key,
                "object_id": object_id,
                "durable": False,
            },
        },
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "layer_schema_fingerprint": layer_schema_fingerprint,
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": dict(attributes),
    }


def _normalize_detail(
    feature: Mapping[str, Any],
    spec: LayerSpec,
    response_schema_fingerprint: str,
    layer_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes = _feature_attributes(feature, spec)
    bbl = _bbl_from_attributes(attributes, spec)
    record = _base_record(
        bbl=bbl,
        spec=spec,
        attributes=attributes,
        response_schema_fingerprint=response_schema_fingerprint,
        layer_schema_fingerprint=layer_schema_fingerprint,
    )
    owner = _clean(attributes.get("OWNER"))
    house_number = _clean(attributes.get("HOUSENUM"))
    street = _clean(attributes.get("STREET_NAME"))
    city = _clean(attributes.get("CITYNAME"))
    postal_code = _clean(attributes.get("ZIP_CODE"))
    street_line = " ".join(
        value for value in (house_number, street) if value
    )
    raw_address = ", ".join(
        value
        for value in (
            street_line or None,
            city,
            STATE_CODE,
            postal_code,
        )
        if value
    )
    record.update(
        {
            "owners": (
                [
                    {
                        "raw_name": owner,
                        "role": "dof_tax_roll_owner",
                        "assertion_type": "assessment_roll_observation",
                        "title_assertion": False,
                    }
                ]
                if owner
                else []
            ),
            "situs_address": {
                "raw": raw_address or None,
                "house_number": house_number,
                "street": street,
                "city": city,
                "state": STATE_CODE,
                "postal_code": postal_code,
                "unit": _clean(attributes.get("UNITNO")),
            },
            "assessment_context": {
                "tax_year": attributes.get("TAXYR"),
                "period": _clean(attributes.get("PERIOD")),
                "cama_year": attributes.get("CAMAB_YR"),
                "notice_of_value_year": attributes.get("NOV_YR"),
                "tax_class": _clean(attributes.get("TAX_CLASS")),
            },
            "building": {
                "building_class": _clean(
                    attributes.get("BLDG_CLASS")
                ),
                "building_class_description": _clean(
                    attributes.get("BLDG_CLASS_DESC")
                ),
                "building_name": _clean(
                    attributes.get("BUILDING_NAME")
                ),
                "year_built": _number(attributes.get("YRBUILT")),
                "stories": _number(attributes.get("BLD_STORY")),
                "gross_square_feet": _number(
                    attributes.get("GROSS_SQFT")
                ),
                "residential_square_feet": _number(
                    attributes.get("RESIDENTIAL_SQFT")
                ),
                "commercial_square_feet": _number(
                    attributes.get("COMMERCIAL_SQFT")
                ),
                "number_of_buildings": _number(
                    attributes.get("NUM_BLDGS")
                ),
                "total_units": _number(
                    attributes.get("TOTAL_UNITS")
                ),
                "residential_units": _number(
                    attributes.get("RESIDENTIAL_UNITS")
                ),
                "commercial_units": _number(
                    attributes.get("COMMERCIAL_UNITS")
                ),
                "frontage": _number(attributes.get("BLD_FRT")),
                "depth": _number(attributes.get("BLD_DEP")),
                "style": _clean(attributes.get("STYLE")),
                "construction_type": _clean(
                    attributes.get("CONSTRUCTION_TYPE")
                ),
                "exterior_wall": _clean(
                    attributes.get("EXTERIOR_WALL")
                ),
                "exterior_condition": _clean(
                    attributes.get("EXTERIOR_CONDITION")
                ),
                "basement_type": _clean(
                    attributes.get("BASEMENT_TYPE")
                ),
                "proximity": _clean(attributes.get("PROXIMITY")),
            },
            "land": {
                "area_square_feet": _number(
                    attributes.get("LAND_AREA")
                ),
                "frontage": _number(attributes.get("LOT_FRT")),
                "depth": _number(attributes.get("LOT_DEP")),
                "zoning": _clean(attributes.get("ZONING")),
                "community_neighborhood": _clean(
                    attributes.get("COMMUNITY_NBHD")
                ),
            },
            "recording_lineage": {
                "recent_recording_display_included": False,
                "complete_instrument_source_ids": (
                    "us-nyc-acris",
                    "us-ny-richmond-county-clerk-land-documents",
                ),
                "pip_acris_relationship": (
                    "same_acris_record_representation"
                ),
            },
        }
    )
    return record


def _normalize_tax_lot(
    feature: Mapping[str, Any],
    spec: LayerSpec,
    response_schema_fingerprint: str,
    layer_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes = _feature_attributes(feature, spec)
    bbl = _bbl_from_attributes(attributes, spec)
    record = _base_record(
        bbl=bbl,
        spec=spec,
        attributes=attributes,
        response_schema_fingerprint=response_schema_fingerprint,
        layer_schema_fingerprint=layer_schema_fingerprint,
    )
    record.update(
        {
            "tax_lot": {
                "condo_flag": _clean(attributes.get("CONDO_FLAG")),
                "reuc_flag": _clean(attributes.get("REUC_FLAG")),
                "air_lot_flag": _clean(
                    attributes.get("AIR_LOT_FLAG")
                ),
                "sub_lot_flag": _clean(
                    attributes.get("SUB_LOT_FLAG")
                ),
                "easement_flag": _clean(
                    attributes.get("EASEMENT_FLAG")
                ),
                "lot_note": _clean(attributes.get("LOT_NOTE")),
                "effective_tax_year": _clean(
                    attributes.get("EFFECTIVE_TAX_YEAR")
                ),
                "bill_bbl_flag": attributes.get("BILL_BBL_FLAG"),
                "nycmap_building_flag": attributes.get(
                    "NYCMAP_BLDG_FLAG"
                ),
                "shape_area": _number(
                    attributes.get("Shape__Area")
                ),
                "shape_length": _number(
                    attributes.get("Shape__Length")
                ),
                "created_at": _arcgis_date(
                    attributes.get("CREATED_DATE")
                ),
                "last_edited_at": _arcgis_date(
                    attributes.get("LAST_EDITED_DATE")
                ),
            }
        }
    )
    if "geometry" in feature:
        record["geometry"] = feature.get("geometry")
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = "EPSG:4326"
        record["geometry_role"] = "cadastral_tax_lot"
    return record


def _normalize_assessment(
    feature: Mapping[str, Any],
    spec: LayerSpec,
    response_schema_fingerprint: str,
    layer_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes = _feature_attributes(feature, spec)
    bbl = _bbl_from_attributes(attributes, spec)
    record = _base_record(
        bbl=bbl,
        spec=spec,
        attributes=attributes,
        response_schema_fingerprint=response_schema_fingerprint,
        layer_schema_fingerprint=layer_schema_fingerprint,
    )
    tax_year = _number(attributes.get("TAXYR"))
    period = _clean(attributes.get("PERIOD"))
    if not isinstance(tax_year, int) or period is None:
        raise ValueError(
            f"PIP {spec.key} row lacks tax-year/period identity"
        )
    assessment_key = (
        f"US-NYC-DOF:ASSESSMENT:{bbl}:{tax_year}:{period}"
    )
    record.update(
        {
            "assessment_identity": {
                "basis": "bbl_tax_year_period",
                "bbl": bbl,
                "tax_year": tax_year,
                "period": period,
                "same_assessment_key": assessment_key,
                "key_role": "cross_representation_join",
                "observed_unique_within_component": True,
                "uniqueness_observed_at": OBSERVED_AT,
                "occurrence_key": record["canonical_ref"],
                "representation_component": spec.key,
            },
            "same_assessment_key": assessment_key,
            "assessment": {
                "tax_year": tax_year,
                "period": period,
                "period_label": _clean(
                    attributes.get("PERIOD_LABEL")
                ),
                "fiscal_year": _clean(
                    attributes.get("FISCAL_YEAR")
                ),
                "representation": spec.key,
                "values": {
                    "market_value": _number(
                        attributes.get("MARKET_VALUE")
                    ),
                    "taxable_assessed_value": _number(
                        attributes.get("TAXABLE_AV")
                    ),
                    "taxable_bill_assessed_value": _number(
                        attributes.get("TAXABLE_BILL_AV")
                    ),
                    "exemption_assessed_value": _number(
                        attributes.get("AV_EXEMPTIONS")
                    ),
                    "land_value": _number(
                        attributes.get("LAND_VALUE")
                    ),
                    "improvement_value": _number(
                        attributes.get("IMPROVEMENT_VALUE")
                    ),
                    "currency": "USD",
                },
                "changes_percent": {
                    "total_value": _number(
                        attributes.get("TOTAL_VALUE_CHANGE")
                    ),
                    "taxable_bill_assessed_value": _number(
                        attributes.get(
                            "TAXABLE_BILL_AV_CHANGE"
                        )
                    ),
                },
                "building_class": _clean(
                    attributes.get("BLDG_CLASS")
                ),
                "tax_class": _clean(
                    attributes.get("TAX_CLASS")
                ),
                "source_fields": {
                    field: _clean(attributes.get(field))
                    for field in (
                        "MARKET_VALUE",
                        "TAXABLE_AV",
                        "TAXABLE_BILL_AV",
                        "AV_EXEMPTIONS",
                        "LAND_VALUE",
                        "IMPROVEMENT_VALUE",
                        "TOTAL_VALUE_CHANGE",
                        "TAXABLE_BILL_AV_CHANGE",
                    )
                },
            },
        }
    )
    return record


def _normalize_exemption(
    feature: Mapping[str, Any],
    spec: LayerSpec,
    response_schema_fingerprint: str,
    layer_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes = _feature_attributes(feature, spec)
    bbl = _bbl_from_attributes(attributes, spec)
    record = _base_record(
        bbl=bbl,
        spec=spec,
        attributes=attributes,
        response_schema_fingerprint=response_schema_fingerprint,
        layer_schema_fingerprint=layer_schema_fingerprint,
    )
    tax_year = _number(attributes.get("TAXYR"))
    exemption_code = _clean(attributes.get("F_EXCODE"))
    exemption_type = _clean(attributes.get("F_EXEMPT_TYPE"))
    sort_order = _number(attributes.get("SORT_ORDER"))
    original_parid = _clean(attributes.get("PARID_ORG"))
    published_tuple = {
        "bbl": bbl,
        "original_parid": original_parid,
        "tax_year": tax_year,
        "exemption_code": exemption_code,
        "exemption_type": exemption_type,
        "sort_order": sort_order,
    }
    tuple_fingerprint = sha256_fingerprint(published_tuple)
    tuple_key = (
        "US-NYC-DOF:EXEMPTION-TUPLE:"
        f"{tuple_fingerprint[:24]}"
    )
    occurrence_key = (
        "US-NYC-DOF:EXEMPTION-OCCURRENCE:"
        f"{record['native_feature_id']}"
    )
    record.update(
        {
            "same_exemption_tuple_key": tuple_key,
            "exemption_identity": {
                "basis": "arcgis_layer_occurrence",
                "key": occurrence_key,
                "occurrence_key": occurrence_key,
                "published_tuple_key": tuple_key,
                "published_tuple": published_tuple,
                "published_tuple_observed_unique": True,
                "uniqueness_observed_at": OBSERVED_AT,
                "object_id": record["native_feature_id"],
                "durable": False,
            },
            "exemption": {
                "tax_year": tax_year,
                "formatted_tax_year": _clean(
                    attributes.get("F_TAXYR")
                ),
                "code": exemption_code,
                "type": exemption_type,
                "sort_order": sort_order,
                "taxable_assessed_value": _number(
                    attributes.get("F_TAXABLE_AV")
                ),
                "exempt_assessed_value": _number(
                    attributes.get("F_EXEMPT_AV")
                ),
                "taxable_bill_assessed_value": _number(
                    attributes.get("F_TAXABLE_BILL_AV")
                ),
                "currency": "USD",
                "original_parid": original_parid,
            },
        }
    )
    return record


def _annotate_exemption_duplicate_ordinals(
    records: Sequence[dict[str, Any]],
    *,
    complete_exact_bbl_result: bool,
) -> None:
    """Label duplicates without replacing their OBJECTID occurrences."""

    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        tuple_key = record.get("same_exemption_tuple_key")
        if isinstance(tuple_key, str):
            groups.setdefault(tuple_key, []).append(record)

    for tuple_key, group in groups.items():
        if len(group) < 2:
            continue
        ordered = sorted(
            group,
            key=lambda record: (
                (
                    0,
                    int(record["native_feature_id"]),
                )
                if str(record.get("native_feature_id", "")).isdigit()
                else (
                    1,
                    str(record.get("native_feature_id", "")),
                )
            ),
        )
        for ordinal, record in enumerate(ordered, start=1):
            identity = record["exemption_identity"]
            identity["published_tuple_observed_unique"] = False
            identity["duplicate_ordinal"] = ordinal
            identity["duplicate_count_in_response"] = len(group)
            identity["duplicate_ordinal_scope"] = (
                "complete_exact_bbl_result"
                if complete_exact_bbl_result
                else "returned_window"
            )
            if complete_exact_bbl_result:
                identity["published_tuple_occurrence_key"] = (
                    f"{tuple_key}:DUPLICATE:{ordinal}"
                )


Normalizer = Callable[
    [Mapping[str, Any], LayerSpec, str, str],
    dict[str, Any],
]

NORMALIZERS: Mapping[str, Normalizer] = {
    "detail": _normalize_detail,
    "tax_lot": _normalize_tax_lot,
    "current_assessment": _normalize_assessment,
    "assessment_history": _normalize_assessment,
    "exemptions": _normalize_exemption,
}


def normalize_feature(
    feature: Mapping[str, Any],
    spec: LayerSpec,
    *,
    response_schema_fingerprint: str,
    layer_schema_fingerprint: str,
) -> dict[str, Any]:
    """Normalize one layer occurrence using its source-local record grain."""

    return NORMALIZERS[spec.key](
        feature,
        spec,
        response_schema_fingerprint,
        layer_schema_fingerprint,
    )


def _match_clause(field: str, value: str, match: str) -> str:
    upper = _sql_literal(value).upper()
    if match == "exact":
        return f"UPPER({field})='{upper}'"
    if match == "starts":
        return f"UPPER({field}) LIKE '{upper}%'"
    if match == "contains":
        return f"UPPER({field}) LIKE '%{upper}%'"
    raise ValueError(f"unsupported match mode: {match}")


ADDRESS_TOKEN_MAP = {
    "E": "EAST",
    "W": "WEST",
    "N": "NORTH",
    "S": "SOUTH",
    "ST": "STREET",
    "STR": "STREET",
    "AVE": "AVENUE",
    "AV": "AVENUE",
    "BLVD": "BOULEVARD",
    "RD": "ROAD",
    "DR": "DRIVE",
    "LN": "LANE",
    "PL": "PLACE",
    "PKWY": "PARKWAY",
    "TER": "TERRACE",
}

ADDRESS_IGNORED_TOKENS = {
    "NEW",
    "YORK",
    "NY",
    "NYC",
}


def _address_where(value: Any) -> str:
    text = _sql_literal(value, "address").upper()
    normalized = re.sub(r"(\d+)(ST|ND|RD|TH)\b", r"\1", text)
    tokens = re.findall(r"[A-Z0-9-]+", normalized)
    if not tokens:
        raise ValueError("address must contain searchable text")

    house_number: str | None = None
    if re.fullmatch(r"\d+[A-Z]?(?:-\d+[A-Z]?)?", tokens[0]):
        house_number = tokens.pop(0)

    street_tokens: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if re.fullmatch(r"\d{5}(?:-\d{4})?", token):
            continue
        mapped = ADDRESS_TOKEN_MAP.get(token, token)
        if mapped in ADDRESS_IGNORED_TOKENS or mapped in seen:
            continue
        seen.add(mapped)
        street_tokens.append(mapped)

    clauses: list[str] = []
    if house_number:
        house = house_number.replace("'", "''")
        clauses.append(
            "("
            f"UPPER(HOUSENUM)='{house}' OR "
            f"UPPER(HOUSENUM) LIKE '{house}-%'"
            ")"
        )
    clauses.extend(
        f"UPPER(STREET_NAME) LIKE '%{token.replace(chr(39), chr(39) * 2)}%'"
        for token in street_tokens
    )
    if not clauses:
        raise ValueError("address must contain a house or street selector")
    return " AND ".join(f"({clause})" for clause in clauses)


def _exact_bbl_where(spec: LayerSpec, bbl: str) -> str:
    field = spec.identity_field
    return f"{field}='{normalize_bbl(bbl)}'"


SINGLE_LAYER_OPERATIONS: Mapping[str, str] = {
    "owner": "detail",
    "address": "detail",
    "detail": "detail",
    "geometry": "tax_lot",
    "current-assessment": "current_assessment",
    "assessment-history": "assessment_history",
    "exemptions": "exemptions",
}


def _where(
    operation: str,
    *,
    selector: str,
    spec: LayerSpec,
    match: str = "contains",
) -> str:
    if operation == "owner":
        return _match_clause("OWNER", selector, match)
    if operation == "address":
        return _address_where(selector)
    return _exact_bbl_where(spec, selector)


def build_query(
    operation: str,
    *,
    selector: str | None,
    parameters: Mapping[str, Any] | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    query_parameters = {
        "selector": selector,
        **dict(parameters or {}),
    }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=query_parameters,
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _new_client(
    spec: LayerSpec,
    args: argparse.Namespace,
) -> PIPArcGISClient:
    return PIPArcGISClient(
        spec,
        page_size=getattr(args, "page_size", DEFAULT_PAGE_SIZE),
        max_records=getattr(args, "max_records", None),
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        minimum_interval=getattr(
            args,
            "minimum_interval",
            DEFAULT_MINIMUM_INTERVAL,
        ),
    )


def _client_for(
    spec: LayerSpec,
    args: argparse.Namespace,
    clients: Mapping[str, Any] | None,
) -> Any:
    if clients is not None and spec.key in clients:
        return clients[spec.key]
    return _new_client(spec, args)


def _fetch_component(
    *,
    spec: LayerSpec,
    where: str,
    args: argparse.Namespace,
    clients: Mapping[str, Any] | None,
    limit: int | None,
    cursor: str | None,
    max_records: int | None,
) -> tuple[list[dict[str, Any]], PaginatedFetch, dict[str, Any]]:
    client = _client_for(spec, args, clients)
    validated = validate_layer_metadata(client.metadata(), spec)
    if hasattr(client, "page_size"):
        client.page_size = min(
            int(client.page_size),
            validated["native_page_size"],
        )
    return_geometry = spec.key == "tax_lot"
    parameters: dict[str, Any] = {
        "orderByFields": spec.order_by,
    }
    if return_geometry:
        parameters["outSR"] = 4326
    fetched = client.query(
        where=where,
        out_fields="*",
        parameters=parameters,
        requested_limit=limit,
        max_records=max_records,
        cursor=cursor,
        return_geometry=return_geometry,
    )
    records = [
        normalize_feature(
            feature,
            spec,
            response_schema_fingerprint=fetched.schema_fingerprint,
            layer_schema_fingerprint=validated[
                "schema_fingerprint"
            ],
        )
        for feature in fetched.records
    ]
    if spec.key == "exemptions":
        _annotate_exemption_duplicate_ordinals(
            records,
            complete_exact_bbl_result=(
                cursor is None
                and fetched.next_cursor is None
                and not fetched.truncated_by_cap
            ),
        )
    return records, fetched, validated


def _invalid_query_result(
    operation: str,
    selector: str | None,
    error: ValueError,
) -> PublicRecordsResult:
    query = build_query(operation, selector=selector)
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="invalid_query",
                message=str(error),
                category="query",
                retryable=False,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _single_layer_result(
    args: argparse.Namespace,
    *,
    operation: str,
    selector: str,
    clients: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    spec = LAYER_SPECS[SINGLE_LAYER_OPERATIONS[operation]]
    limit = getattr(args, "limit", None)
    cursor = getattr(args, "cursor", None)
    max_records = getattr(args, "max_records", None)
    match = getattr(args, "match", "contains")
    query = build_query(
        operation,
        selector=selector,
        parameters={
            "layer": spec.key,
            "match": match if operation in {"owner", "address"} else None,
            "return_geometry": spec.key == "tax_lot",
            "max_records": max_records,
        },
        limit=limit,
        cursor=cursor,
    )
    where = _where(
        operation,
        selector=selector,
        spec=spec,
        match=match,
    )
    try:
        records, fetched, _validated = _fetch_component(
            spec=spec,
            where=where,
            args=args,
            clients=clients,
            limit=limit,
            cursor=cursor,
            max_records=max_records,
        )
        warnings = (*SOURCE_WARNINGS, *fetched.warnings)
        if fetched.truncated_by_cap:
            return PublicRecordsResult(
                query=query,
                status=ResultStatus.PARTIAL,
                records=records,
                next_cursor=fetched.next_cursor,
                warnings=warnings,
            )
        return PublicRecordsResult.success(
            query,
            records,
            next_cursor=fetched.next_cursor,
            warnings=warnings,
        )
    except PublicRecordsHTTPError as error:
        return failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
        return PublicRecordsResult.failure(
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


def _bundle_anchor(
    bbl: str,
    *,
    component_records: Mapping[str, Sequence[Mapping[str, Any]]],
    component_metadata: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    parts = bbl_parts(bbl)
    parcel_ref = canonical_property_ref(
        SOURCE_ID,
        parts["county_geoid"],
        "parcel",
        bbl,
    )
    return {
        "canonical_ref": parcel_ref,
        "parcel_canonical_ref": parcel_ref,
        "same_record_key": f"US-NYC:BBL:{bbl}",
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "record_kind": "nyc_dof_property_information_bundle",
        "record_scope": "nyc_dof_property_information_portal",
        "viewer_url": PIP_URL,
        "bbl": bbl,
        "borough": parts["borough_code"],
        "block": parts["block"],
        "lot": parts["lot"],
        "jurisdiction": {
            "state_code": STATE_CODE,
            "city": "New York City",
            "borough_name": parts["borough_name"],
            "county_name": parts["county_name"],
            "county_geoid": parts["county_geoid"],
        },
        "identity": {
            "basis": "nyc_bbl",
            "value": bbl,
            "durable": True,
            "projection_eligible_as_parcel": True,
        },
        "component_counts": {
            key: len(component_records.get(key, ()))
            for key in BUNDLE_LAYER_KEYS
        },
        "component_layer_schema_fingerprints": {
            key: component_metadata[key]["schema_fingerprint"]
            for key in component_metadata
        },
        "recording_routes": {
            "four_borough_complete_instruments": {
                "source_id": "us-nyc-acris",
                "url": ACRIS_URL,
            },
            "staten_island_complete_instruments": {
                "source_id": (
                    "us-ny-richmond-county-clerk-land-documents"
                ),
                "url": RICHMOND_CLERK_URL,
            },
            "pip_recent_acris_display_relationship": (
                "same_acris_record_representation"
            ),
        },
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
    }


def _verify_probe(
    component_records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    detail = component_records["detail"]
    tax_lot = component_records["tax_lot"]
    current = component_records["current_assessment"]
    history = component_records["assessment_history"]
    if len(detail) != 1:
        raise SourceSchemaError(
            "PIP probe expected one parcel-detail occurrence",
            url=LAYER_SPECS["detail"].url,
            details={"observed_count": len(detail)},
        )
    if len(tax_lot) != 1:
        raise SourceSchemaError(
            "PIP probe expected one tax-lot geometry occurrence",
            url=LAYER_SPECS["tax_lot"].url,
            details={"observed_count": len(tax_lot)},
        )
    if not current:
        raise SourceSchemaError(
            "PIP probe current-assessment sentinel disappeared",
            url=LAYER_SPECS["current_assessment"].url,
        )
    if not history:
        raise SourceSchemaError(
            "PIP probe assessment-history sentinel disappeared",
            url=LAYER_SPECS["assessment_history"].url,
        )
    detail_record = detail[0]
    address = detail_record.get("situs_address")
    geometry = tax_lot[0].get("geometry")
    rings = (
        geometry.get("rings")
        if isinstance(geometry, Mapping)
        else None
    )
    if (
        detail_record.get("bbl") != PROBE_BBL
        or not isinstance(address, Mapping)
        or address.get("house_number") != PROBE_HOUSE_NUMBER
        or address.get("street") != PROBE_STREET
        or tax_lot[0].get("bbl") != PROBE_BBL
        or not isinstance(rings, (list, tuple))
        or not rings
    ):
        raise SourceSchemaError(
            "PIP exact parcel sentinel identity changed",
            url=PIP_URL,
            details={
                "expected_bbl": PROBE_BBL,
                "expected_house_number": PROBE_HOUSE_NUMBER,
                "expected_street": PROBE_STREET,
            },
        )


def _bundle_result(
    args: argparse.Namespace,
    *,
    operation: str,
    bbl: str,
    clients: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    query = build_query(
        operation,
        selector=bbl,
        parameters={
            "bounded_exact_bbl": True,
            "layers": BUNDLE_LAYER_KEYS,
            "return_tax_lot_geometry": True,
        },
    )
    component_records: dict[str, list[dict[str, Any]]] = {}
    component_metadata: dict[str, dict[str, Any]] = {}
    component_fetches: dict[str, PaginatedFetch] = {}
    errors: list[PublicRecordsError] = []
    for key in BUNDLE_LAYER_KEYS:
        spec = LAYER_SPECS[key]
        try:
            records, fetched, metadata = _fetch_component(
                spec=spec,
                where=_exact_bbl_where(spec, bbl),
                args=args,
                clients=clients,
                limit=None,
                cursor=None,
                max_records=None,
            )
            component_records[key] = records
            component_metadata[key] = metadata
            component_fetches[key] = fetched
        except PublicRecordsHTTPError as error:
            errors.append(error.to_contract_error())
        except (TypeError, ValueError) as error:
            errors.append(
                PublicRecordsError(
                    code="normalization_failed",
                    message=f"{key}: {error}",
                    category="source_schema",
                    retryable=False,
                )
            )

    flattened = [
        record
        for key in BUNDLE_LAYER_KEYS
        for record in component_records.get(key, ())
    ]
    if errors:
        if flattened:
            anchor = _bundle_anchor(
                bbl,
                component_records=component_records,
                component_metadata=component_metadata,
            )
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                errors,
                records=[anchor, *flattened],
                warnings=SOURCE_WARNINGS,
            )
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            errors,
            warnings=SOURCE_WARNINGS,
        )
    if not flattened:
        return PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    if operation == "probe":
        try:
            _verify_probe(component_records)
        except PublicRecordsHTTPError as error:
            return failure_result(query, error, warnings=SOURCE_WARNINGS)

    anchor = _bundle_anchor(
        bbl,
        component_records=component_records,
        component_metadata=component_metadata,
    )
    anchor["component_fetches"] = {
        key: {
            "pages_fetched": fetched.pages_fetched,
            "requests_made": fetched.requests_made,
            "response_schema_fingerprint": (
                fetched.schema_fingerprint
            ),
        }
        for key, fetched in component_fetches.items()
    }
    return PublicRecordsResult.success(
        query,
        [anchor, *flattened],
        warnings=SOURCE_WARNINGS,
    )


def source_routes() -> dict[str, Any]:
    """Return the layer family and field-matched recording routes."""

    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_route_map",
        "observed_at": OBSERVED_AT,
        "official_portal": PIP_URL,
        "official_linker": DOF_LINKER_URL,
        "layers": [
            {
                "layer_key": spec.key,
                "url": spec.url,
                "layer_id": spec.layer_id,
                "expected_name": spec.expected_name,
                "record_kind": spec.record_kind,
                "durable_join_field": spec.identity_field,
                "occurrence_field": "OBJECTID",
                "order_by": spec.order_by,
            }
            for spec in LAYER_SPECS.values()
        ],
        "recording_routes": [
            {
                "source_id": "us-nyc-acris",
                "url": ACRIS_URL,
                "coverage": (
                    "Manhattan, Bronx, Brooklyn, and Queens"
                ),
                "record_class": "complete_recorded_instrument",
                "relationship_to_pip_recent_display": (
                    "same_acris_record_representation"
                ),
            },
            {
                "source_id": (
                    "us-ny-richmond-county-clerk-land-documents"
                ),
                "url": RICHMOND_CLERK_URL,
                "coverage": "Staten Island",
                "record_class": "complete_recorded_instrument",
                "relationship_to_pip": (
                    "field_matched_official_recorder"
                ),
            },
        ],
    }


def _discovery_result(
    args: argparse.Namespace,
    *,
    clients: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    mode = args.mode
    selected_key = getattr(args, "layer", None)
    query = build_query(
        "discovery",
        selector=mode,
        parameters={"mode": mode, "layer": selected_key},
    )
    if mode == "routes":
        return PublicRecordsResult.success(
            query,
            [source_routes()],
            warnings=SOURCE_WARNINGS,
        )
    if mode == "layers":
        records = [
            {
                "source_id": SOURCE_ID,
                "record_kind": "source_layer_manifest",
                "layer_key": spec.key,
                "url": spec.url,
                "expected_name": spec.expected_name,
                "expected_type": spec.expected_type,
                "identity_field": spec.identity_field,
                "occurrence_field": "OBJECTID",
                "normalized_record_kind": spec.record_kind,
                "required_fields": spec.required_fields,
                "order_by": spec.order_by,
            }
            for spec in LAYER_SPECS.values()
            if selected_key is None or spec.key == selected_key
        ]
        return PublicRecordsResult.success(
            query,
            records,
            warnings=SOURCE_WARNINGS,
        )

    records: list[dict[str, Any]] = []
    errors: list[PublicRecordsError] = []
    for spec in LAYER_SPECS.values():
        if selected_key is not None and spec.key != selected_key:
            continue
        client = _client_for(spec, args, clients)
        try:
            validated = validate_layer_metadata(
                client.metadata(),
                spec,
            )
            records.append(
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_layer_metadata",
                    "layer_key": spec.key,
                    "url": spec.url,
                    "native_page_size": validated[
                        "native_page_size"
                    ],
                    "layer_schema": validated["schema"],
                    "layer_schema_fingerprint": validated[
                        "schema_fingerprint"
                    ],
                }
            )
        except PublicRecordsHTTPError as error:
            errors.append(error.to_contract_error())
    if errors and records:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            errors,
            records=records,
            warnings=SOURCE_WARNINGS,
        )
    if errors:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            errors,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    clients: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one standalone PIP lookup or discovery operation."""

    operation = args.command
    selector: str | None = None
    try:
        if operation == "discovery":
            result = _discovery_result(args, clients=clients)
        elif operation == "probe":
            selector = PROBE_BBL
            result = _bundle_result(
                args,
                operation=operation,
                bbl=PROBE_BBL,
                clients=clients,
            )
        elif operation == "bbl":
            selector = normalize_bbl(args.query)
            result = _bundle_result(
                args,
                operation=operation,
                bbl=selector,
                clients=clients,
            )
        elif operation == "lot":
            selector = bbl_from_parts(
                args.borough,
                args.block,
                args.lot,
            )
            result = _bundle_result(
                args,
                operation=operation,
                bbl=selector,
                clients=clients,
            )
        elif operation in SINGLE_LAYER_OPERATIONS:
            selector = (
                args.query
                if operation in {"owner", "address"}
                else normalize_bbl(args.query)
            )
            result = _single_layer_result(
                args,
                operation=operation,
                selector=selector,
                clients=clients,
            )
        else:
            raise ValueError(f"unsupported PIP operation: {operation}")
    except ValueError as error:
        result = _invalid_query_result(operation, selector, error)

    if log_results:
        _best_effort_log(result)
    return result


def _best_effort_log(result: PublicRecordsResult) -> None:
    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(
            canonical_json(result.query.to_dict()),
            SOURCE_ID,
            result_count,
        )
    except Exception as error:
        print(
            f"Warning: search log was not updated: {error}",
            file=sys.stderr,
        )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    if write_output(
        result.to_dict(),
        args,
        summary=(
            f"NYC PIP {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    print(
        f"NYC PIP {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        bbl = record.get("bbl")
        kind = record.get("record_kind")
        address = record.get("situs_address")
        display_address = (
            address.get("raw")
            if isinstance(address, Mapping)
            else None
        )
        print(
            f"  {bbl or record.get('layer_key') or '-'} | "
            f"{kind or '-'} | {display_address or ''}"
        )
    for error in result.errors:
        print(
            f"ERROR [{error.code}]: {error.message}",
            file=sys.stderr,
        )


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _nonnegative_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be numeric") from error
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="ArcGIS transport page size, bounded by each live layer maximum",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    add_output_args(parser)


def _add_window_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-selected result window",
    )
    parser.add_argument(
        "--cursor",
        help="ArcGIS continuation cursor from a previous result",
    )
    parser.add_argument(
        "--max-records",
        type=_positive_int,
        help="Optional caller-selected ceiling across technical pages",
    )
    _add_transport_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query NYC Department of Finance Property Information "
            "Portal records"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bbl_parser = subparsers.add_parser(
        "bbl",
        help="Fetch the complete PIP component bundle for one BBL",
    )
    bbl_parser.add_argument("query")
    _add_transport_args(bbl_parser)

    lot_parser = subparsers.add_parser(
        "lot",
        help="Fetch a bundle by borough, block, and lot",
    )
    lot_parser.add_argument("borough")
    lot_parser.add_argument("block")
    lot_parser.add_argument("lot")
    _add_transport_args(lot_parser)

    for command, help_text in (
        ("detail", "Fetch parcel and building detail by BBL"),
        ("geometry", "Fetch tax-lot geometry by BBL"),
        (
            "current-assessment",
            "Fetch current published assessment rows by BBL",
        ),
        (
            "assessment-history",
            "Fetch historical assessment rows by BBL",
        ),
        ("exemptions", "Fetch exemption rows by BBL"),
    ):
        command_parser = subparsers.add_parser(
            command,
            help=help_text,
        )
        command_parser.add_argument("query")
        _add_window_args(command_parser)

    for command, help_text in (
        ("owner", "Search Department of Finance owner observations"),
        ("address", "Search parcel-detail address observations"),
    ):
        command_parser = subparsers.add_parser(
            command,
            help=help_text,
        )
        command_parser.add_argument("query")
        command_parser.add_argument(
            "--match",
            choices=("contains", "starts", "exact"),
            default="contains",
        )
        _add_window_args(command_parser)

    discovery_parser = subparsers.add_parser(
        "discovery",
        help="Show layer manifests, live metadata, or source routes",
    )
    discovery_parser.add_argument(
        "mode",
        choices=("layers", "metadata", "routes"),
    )
    discovery_parser.add_argument(
        "--layer",
        choices=tuple(LAYER_SPECS),
    )
    _add_transport_args(discovery_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Run the exact known-BBL contract sentinel",
    )
    _add_transport_args(probe_parser)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("timeout must be positive")
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
