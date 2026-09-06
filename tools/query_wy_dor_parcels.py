#!/usr/bin/env python3
"""Query the Wyoming Department of Revenue annual statewide parcel layer.

The current official hosted layer contains annual county tax-roll context and
parcel polygons.  A tax-year/jurisdiction/parcel/account tuple joins repeated
geometry components for one annual parcel observation; ``FID`` identifies each
published feature occurrence.  Omitting caller limits exhausts the layer's
ordered native ArcGIS pages.

Examples:
    uv run python tools/query_wy_dor_parcels.py owner "STATE OF WYOMING"
    uv run python tools/query_wy_dor_parcels.py parcel 49720332401200 \
        --jurisdiction Campbell
    uv run python tools/query_wy_dor_parcels.py account R0059774
    uv run python tools/query_wy_dor_parcels.py county Campbell
    uv run python tools/query_wy_dor_parcels.py situs "KETTLESON XING"
    uv run python tools/query_wy_dor_parcels.py mailing "BISHOP BLVD"
    uv run python tools/query_wy_dor_parcels.py legal "LEGACY RIDGE"
    uv run python tools/query_wy_dor_parcels.py fid 30558
    uv run python tools/query_wy_dor_parcels.py geometry 30558
    uv run python tools/query_wy_dor_parcels.py point -105.5013 44.2526
    uv run python tools/query_wy_dor_parcels.py bbox -105.51 44.24 -105.49 44.27
    uv run python tools/query_wy_dor_parcels.py discovery metadata --json
    uv run python tools/query_wy_dor_parcels.py probe --json
"""

from __future__ import annotations

import argparse
import re
import sys
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
        SourceResponseError,
        SourceSchemaError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-wy-dor-statewide-parcels"
SOURCE_NAME = "Wyoming DOR Statewide Parcels"
STATE_CODE = "WY"
STATE_FIPS = "56"
RELEASE_YEAR = "2026"
OBSERVED_AT = "2026-07-31"

ITEM_ID = "9ab04f655f5b4e398d9f2f070d2d29bb"
ITEM_URL = f"https://www.arcgis.com/home/item.html?id={ITEM_ID}"
ITEM_METADATA_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{ITEM_ID}"
)
ROOT_APP_ITEM_ID = "4bb9a66f7287402b8f650aa9f21d3fa5"
ROOT_APP_URL = (
    "https://wyo-prop-div.maps.arcgis.com/apps/webappviewer/index.html?id="
    f"{ROOT_APP_ITEM_ID}"
)
ROOT_APP_METADATA_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{ROOT_APP_ITEM_ID}"
)
ROOT_APP_DATA_URL = f"{ROOT_APP_METADATA_URL}/data"
ROOT_APP_DATA_TITLE = "Wyoming Statewide Parcel and Tax District Viewer"
ROOT_APP_DATA_SUBTITLE = "Current as of January 1, 2026"
LAYER_URL = (
    "https://services3.arcgis.com/r0iJ85SKZ4zAzz3P/arcgis/rest/services/"
    "Wyoming_Parcels_for_2026/FeatureServer/0"
)
DOR_MAPS_URL = "https://wyo-prop-div.wyo.gov/tax-districts/maps-gis-data"
DOR_DOWNLOAD_URL = "https://wyo-prop-div.wyo.gov/assessment-data-download"
COUNTY_DIRECTORY_URL = "https://ets.wyo.gov/gis-office/georesources"

DEFAULT_PAGE_SIZE = 2_000
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.0

PROBE_TAX_YEAR = "2026"
PROBE_JURISDICTION = "CAMPBELL"
PROBE_PARCEL = "49720332401200"
PROBE_ACCOUNT = "R0059774"
PROBE_SITUS = "16 KETTLESON XING"

REQUIRED_FIELDS = (
    "FID",
    "ID",
    "taxyear",
    "parcelnb",
    "accountno",
    "jurisdicti",
    "ownername1",
    "ownername2",
    "mailaddres",
    "mailcity",
    "mailstate",
    "mailzipcod",
    "locationad",
    "legal",
    "actualvalu",
    "assessedva",
    "landgrossa",
    "landgrosss",
    "DEFAULTTAX",
    "Shape__Area",
    "Shape__Length",
)

COUNTIES: Mapping[str, Mapping[str, Any]] = {
    "ALBANY": {"name": "Albany", "fips": "001", "count": 18_273},
    "BIGHORN": {"name": "Big Horn", "fips": "003", "count": 8_451},
    "CAMPBELL": {"name": "Campbell", "fips": "005", "count": 20_302},
    "CARBON": {"name": "Carbon", "fips": "007", "count": 12_507},
    "CONVERSE": {"name": "Converse", "fips": "009", "count": 9_705},
    "CROOK": {"name": "Crook", "fips": "011", "count": 6_839},
    "FREMONT": {"name": "Fremont", "fips": "013", "count": 21_913},
    "GOSHEN": {"name": "Goshen", "fips": "015", "count": 8_534},
    "HOTSPRINGS": {
        "name": "Hot Springs",
        "fips": "017",
        "count": 6_844,
    },
    "JOHNSON": {"name": "Johnson", "fips": "019", "count": 7_799},
    "LARAMIE": {"name": "Laramie", "fips": "021", "count": 46_853},
    "LINCOLN": {"name": "Lincoln", "fips": "023", "count": 30_689},
    "NATRONA": {"name": "Natrona", "fips": "025", "count": 42_787},
    "NIOBRARA": {"name": "Niobrara", "fips": "027", "count": 3_806},
    "PARK": {"name": "Park", "fips": "029", "count": 19_437},
    "PLATTE": {"name": "Platte", "fips": "031", "count": 15_512},
    "SHERIDAN": {"name": "Sheridan", "fips": "033", "count": 18_982},
    "SUBLETTE": {"name": "Sublette", "fips": "035", "count": 8_681},
    "SWEETWATER": {
        "name": "Sweetwater",
        "fips": "037",
        "count": 27_394,
    },
    "TETON": {"name": "Teton", "fips": "039", "count": 12_503},
    "UINTA": {"name": "Uinta", "fips": "041", "count": 14_853},
    "WASHAKIE": {"name": "Washakie", "fips": "043", "count": 5_144},
    "WESTON": {"name": "Weston", "fips": "045", "count": 5_858},
}

COUNTY_ALIASES = {
    re.sub(r"[^A-Z0-9]", "", value["name"].upper()): key
    for key, value in COUNTIES.items()
}
COUNTY_ALIASES.update(
    {
        re.sub(r"[^A-Z0-9]", "", f"{value['name']} County".upper()): key
        for key, value in COUNTIES.items()
    }
)
COUNTY_ALIASES.update({key: key for key in COUNTIES})

NON_SPECIFIC_PARCEL_IDENTIFIERS = frozenset(
    {
        "BLM",
        "NO PIN",
        "ROW",
        "STATE",
        "UNKNOWN",
        "UNASSIGNED",
        "N/A",
    }
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role="annual_statewide_county_tax_roll_and_parcel_geometry",
    base_url=LAYER_URL,
    dataset_id=f"{ITEM_ID}/0",
    metadata={
        "authority": "Wyoming Department of Revenue, Property Tax Division",
        "publisher_account": "dave.chapman@wyo.gov",
        "release_year": RELEASE_YEAR,
        "coverage": "all 23 Wyoming counties",
        "official_maps_page": DOR_MAPS_URL,
        "observed_at": OBSERVED_AT,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_FIPS,
    name="Wyoming",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    (
        "Owner names are annual county tax-roll observations assembled by "
        "the Wyoming Department of Revenue; recorded instruments provide "
        "title-event evidence."
    ),
    (
        "One annual parcel/account tuple can have multiple FID geometry "
        "occurrences. Each feature is retained while the annual tuple is "
        "exposed as their shared join."
    ),
    (
        "A surname owner match is an unresolved candidate until parcel, "
        "address, jurisdiction, or recorded-instrument context resolves it."
    ),
)

IDENTITY_AUDIT = {
    "observed_at": OBSERVED_AT,
    "total_rows": 373_666,
    "tax_year_counts": {"2026": 373_666},
    "jurisdiction_count": 23,
    "database_non_null_counts": {
        "taxyear": 373_666,
        "jurisdicti": 373_666,
        "parcelnb": 373_666,
        "accountno": 373_666,
    },
    "blank_string_counts": {
        "parcelnb_single_space": 1_214,
        "accountno_single_space": 40_487,
        "both_single_space": 1_214,
    },
    "largest_blank_tuple_occurrence_count": 1_049,
    "largest_usable_tuple_occurrence_count": 84,
    "largest_usable_tuple": {
        "taxyear": "2026",
        "jurisdicti": "LINCOLN",
        "parcelnb": "37181840001700",
        "accountno": "R0015471",
    },
    "normalized_identity_basis_counts": {
        "tax_year_jurisdiction_parcel_account": 333_179,
        "tax_year_jurisdiction_parcel": 37_474,
        "tax_year_jurisdiction_account": 0,
        "release_occurrence_only": 3_013,
    },
    "occurrence_only_breakdown": {
        "blank_parcel_and_account": 1_214,
        "non_specific_parcel_without_account": 1_799,
    },
    "interpretation": (
        "annual tuple is a parcel/account join; FID is the published "
        "geometry occurrence"
    ),
}

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "item_id": ITEM_ID,
        "layer_name": "Wyoming_Parcels_for_2026",
        "release_year": RELEASE_YEAR,
        "required_fields": REQUIRED_FIELDS,
        "identity_version": 1,
    }
)


class WyomingDORClient(ArcGISRESTClient):
    """ArcGIS query client with layer metadata access."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(LAYER_URL, **kwargs)

    def metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Wyoming DOR layer metadata must be an object",
                url=self.layer_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "Wyoming DOR returned a layer metadata error",
                url=self.layer_url,
                details={"response": payload["error"]},
            )
        return payload

    def app_item(self) -> Mapping[str, Any]:
        return self._public_item_json(ROOT_APP_METADATA_URL)

    def app_data(self) -> Mapping[str, Any]:
        return self._public_item_json(ROOT_APP_DATA_URL)

    def count(self) -> int:
        payload = self._request_json(
            f"{self.layer_url}/query",
            params={"f": "json", "where": "1=1", "returnCountOnly": "true"},
        )
        count = payload.get("count") if isinstance(payload, Mapping) else None
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Wyoming DOR statewide count response changed",
                url=f"{self.layer_url}/query",
                details={"response": payload},
            )
        return count

    def _public_item_json(self, url: str) -> Mapping[str, Any]:
        payload = self._request_json(url, params={"f": "json"})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Wyoming DOR application metadata must be an object",
                url=url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "Wyoming DOR returned an application metadata error",
                url=url,
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
        return int(value) if float(value).is_integer() else value
    text = _clean(value)
    if text is None:
        return None
    cleaned = re.sub(r"[$,%\s]", "", text)
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


def normalize_jurisdiction(value: Any) -> str:
    """Return the exact jurisdiction token published by the annual layer."""

    text = _clean(value)
    if text is None:
        raise ValueError("jurisdiction must not be blank")
    key = re.sub(r"[^A-Z0-9]", "", text.upper())
    jurisdiction = COUNTY_ALIASES.get(key)
    if jurisdiction is None:
        raise ValueError("jurisdiction must be one of Wyoming's 23 counties")
    return jurisdiction


def _postal_code(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}"
    return text


def _non_specific_parcel(parcel_number: str | None) -> bool:
    if parcel_number is None:
        return False
    upper = parcel_number.upper()
    if upper in NON_SPECIFIC_PARCEL_IDENTIFIERS:
        return True
    digits = re.sub(r"[^0-9]", "", upper)
    return bool(digits) and len(set(digits)) == 1 and len(digits) >= 8


def validate_layer_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the current annual item, schema, geometry, and paging."""

    observed_identity = {
        "id": metadata.get("id"),
        "name": _clean(metadata.get("name")),
        "type": _clean(metadata.get("type")),
        "service_item_id": _clean(metadata.get("serviceItemId")),
        "object_id_field": _clean(metadata.get("objectIdField")),
        "geometry_type": _clean(metadata.get("geometryType")),
    }
    expected_identity = {
        "id": 0,
        "name": "Wyoming_Parcels_for_2026",
        "type": "Feature Layer",
        "service_item_id": ITEM_ID,
        "object_id_field": "FID",
        "geometry_type": "esriGeometryPolygon",
    }
    if observed_identity != expected_identity:
        raise SourceSchemaError(
            "Wyoming DOR annual layer identity changed",
            url=LAYER_URL,
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
            "Wyoming DOR layer no longer declares Query",
            url=LAYER_URL,
        )

    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping) or any(
        advanced.get(key) is not True
        for key in ("supportsPagination", "supportsOrderBy")
    ):
        raise SourceSchemaError(
            "Wyoming DOR ordered pagination contract changed",
            url=LAYER_URL,
        )

    page_size = metadata.get("maxRecordCount")
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or page_size <= 0
    ):
        raise SourceSchemaError(
            "Wyoming DOR layer lacks a native page size",
            url=LAYER_URL,
        )

    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "Wyoming DOR layer has malformed field declarations",
            url=LAYER_URL,
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
    missing = sorted(set(REQUIRED_FIELDS) - set(definitions))
    if missing:
        raise SourceSchemaError(
            "Wyoming DOR annual layer is missing required fields",
            url=LAYER_URL,
            details={"missing_fields": missing},
        )

    schema = {
        "identity": observed_identity,
        "capabilities": sorted(capabilities),
        "supports_pagination": True,
        "supports_order_by": True,
        "native_page_size": page_size,
        "required_fields": {
            name: definitions[name] for name in REQUIRED_FIELDS
        },
    }
    editing_info = metadata.get("editingInfo")
    if not isinstance(editing_info, Mapping):
        editing_info = {}
    return {
        "native_page_size": page_size,
        "schema": schema,
        "schema_fingerprint": sha256_fingerprint(schema),
        "source_version": {
            "data_last_edit": _arcgis_date(
                editing_info.get("dataLastEditDate")
            ),
            "schema_last_edit": _arcgis_date(
                editing_info.get("schemaLastEditDate")
            ),
        },
    }


def _query_widgets(value: Any) -> list[Mapping[str, Any]]:
    widgets: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        if _clean(value.get("uri")) == "widgets/Query/Widget":
            widgets.append(value)
        for child in value.values():
            widgets.extend(_query_widgets(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            widgets.extend(_query_widgets(child))
    return widgets


def validate_app_agreement(
    item_metadata: Mapping[str, Any],
    app_data: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify the stable DOR application root and its current parcel route."""

    app_identity = {
        "id": _clean(item_metadata.get("id")),
        "type": _clean(item_metadata.get("type")),
        "owner": _clean(item_metadata.get("owner")),
        "access": _clean(item_metadata.get("access")),
    }
    expected_identity = {
        "id": ROOT_APP_ITEM_ID,
        "type": "Web Mapping Application",
        "owner": "dave.chapman@wyo.gov",
        "access": "public",
    }
    if app_identity != expected_identity:
        raise SourceSchemaError(
            "Wyoming DOR application identity changed",
            url=ROOT_APP_METADATA_URL,
            details={"expected": expected_identity, "observed": app_identity},
        )

    app_item_id = _clean(app_data.get("appItemId"))
    title = _clean(app_data.get("title"))
    subtitle = _clean(app_data.get("subtitle"))
    subtitle_match = re.fullmatch(
        r"Current as of [A-Za-z]+ [0-9]{1,2}, ([0-9]{4})",
        subtitle or "",
    )
    if (
        app_item_id != ROOT_APP_ITEM_ID
        or title != ROOT_APP_DATA_TITLE
        or subtitle_match is None
    ):
        raise SourceSchemaError(
            "Wyoming DOR application data contract changed",
            url=ROOT_APP_DATA_URL,
            details={
                "expected": {
                    "app_item_id": ROOT_APP_ITEM_ID,
                    "title": ROOT_APP_DATA_TITLE,
                    "subtitle_format": "Current as of Month D, YYYY",
                },
                "observed": {
                    "app_item_id": app_item_id,
                    "title": title,
                    "subtitle": subtitle,
                },
            },
        )

    parcel_queries: list[dict[str, Any]] = []
    for widget in _query_widgets(app_data):
        config = widget.get("config")
        if not isinstance(config, Mapping):
            continue
        queries = config.get("queries")
        if not isinstance(queries, (list, tuple)):
            continue
        for query in queries:
            if not isinstance(query, Mapping):
                continue
            if _clean(query.get("url")) != LAYER_URL:
                continue
            fields: list[str] = []
            filter_value = query.get("filter")
            parts = (
                filter_value.get("parts")
                if isinstance(filter_value, Mapping)
                else None
            )
            if isinstance(parts, (list, tuple)):
                for part in parts:
                    field_value = (
                        part.get("fieldObj")
                        if isinstance(part, Mapping)
                        else None
                    )
                    field_name = (
                        _clean(field_value.get("name"))
                        if isinstance(field_value, Mapping)
                        else None
                    )
                    if field_name:
                        fields.append(field_name)
            parcel_queries.append(
                {
                    "widget_id": _clean(widget.get("id")),
                    "widget_label": _clean(widget.get("label")),
                    "query_name": _clean(query.get("name")),
                    "url": LAYER_URL,
                    "fields": sorted(set(fields)),
                }
            )
    observed_query_fields = {
        field
        for query in parcel_queries
        for field in query.get("fields", ())
    }
    required_query_fields = {"accountno", "parcelnb"}
    if not parcel_queries or not required_query_fields <= observed_query_fields:
        raise SourceSchemaError(
            "Wyoming DOR query widget no longer points to or agrees with the "
            "current parcel layer",
            url=ROOT_APP_DATA_URL,
            details={
                "expected_layer_url": LAYER_URL,
                "required_query_fields": sorted(required_query_fields),
                "observed_query_fields": sorted(observed_query_fields),
            },
        )
    return {
        "app_identity": app_identity,
        "app_data": {
            "app_item_id": app_item_id,
            "title": title,
            "subtitle": subtitle,
            "release_year": subtitle_match.group(1),
            "web_map_item_id": _clean(
                app_data.get("map", {}).get("itemId")
                if isinstance(app_data.get("map"), Mapping)
                else None
            ),
        },
        "parcel_query_routes": sorted(
            parcel_queries,
            key=lambda row: (
                str(row.get("query_name") or ""),
                tuple(row.get("fields") or ()),
            ),
        ),
        "implemented_layer_url": LAYER_URL,
    }


def _annual_identity(
    attributes: Mapping[str, Any],
) -> dict[str, Any]:
    tax_year = _clean(attributes.get("taxyear"))
    raw_jurisdiction = _clean(attributes.get("jurisdicti"))
    jurisdiction = (
        normalize_jurisdiction(raw_jurisdiction)
        if raw_jurisdiction is not None
        else None
    )
    parcel_number = _clean(attributes.get("parcelnb"))
    account_number = _clean(attributes.get("accountno"))
    parcel_is_non_specific = _non_specific_parcel(parcel_number)

    basis: str | None = None
    if tax_year and jurisdiction and account_number:
        basis = (
            "tax_year_jurisdiction_parcel_account"
            if parcel_number and not parcel_is_non_specific
            else "tax_year_jurisdiction_account"
        )
    elif (
        tax_year
        and jurisdiction
        and parcel_number
        and not parcel_is_non_specific
    ):
        basis = "tax_year_jurisdiction_parcel"

    components = {
        "tax_year": tax_year,
        "jurisdiction": jurisdiction,
        "parcel_number": parcel_number,
        "account_number": account_number,
    }
    if basis is None:
        if parcel_is_non_specific:
            reason = "non_specific_parcel_identifier_without_account"
        elif parcel_number is None and account_number is None:
            reason = "blank_parcel_and_account"
        else:
            reason = "incomplete_annual_identity"
        return {
            "basis": None,
            "components": components,
            "key": None,
            "fingerprint": None,
            "projection_eligible_as_annual_parcel": False,
            "reason": reason,
            "parcel_identifier_quality": (
                "non_specific_label"
                if parcel_is_non_specific
                else "missing" if parcel_number is None else "published"
            ),
        }

    key_payload = {
        "tax_year": tax_year,
        "jurisdiction": jurisdiction,
        "parcel_number": (
            parcel_number if not parcel_is_non_specific else None
        ),
        "account_number": account_number,
    }
    fingerprint = sha256_fingerprint(key_payload)
    key = f"US-WY-DOR:ANNUAL:{tax_year}:{jurisdiction}:{fingerprint[:24]}"
    return {
        "basis": basis,
        "components": components,
        "key": key,
        "fingerprint": fingerprint,
        "projection_eligible_as_annual_parcel": True,
        "durable_within_annual_release": True,
        "parcel_identifier_quality": (
            "non_specific_label"
            if parcel_is_non_specific
            else "published"
        ),
        "duplicate_geometry_occurrences_possible": True,
    }


def normalize_feature(
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
    layer_schema_fingerprint: str,
    source_version: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize one FID occurrence without collapsing annual joins."""

    raw_attributes = feature.get("attributes")
    if not isinstance(raw_attributes, Mapping):
        raise ValueError("Wyoming parcel feature attributes must be an object")
    attributes = dict(raw_attributes)
    fid = _number(attributes.get("FID"))
    if not isinstance(fid, int) or fid < 0:
        raise ValueError("Wyoming parcel feature lacks a valid FID")

    annual_identity = _annual_identity(attributes)
    components = annual_identity["components"]
    jurisdiction = components["jurisdiction"]
    county = COUNTIES.get(str(jurisdiction), {})
    county_fips = county.get("fips")
    county_geoid = f"{STATE_FIPS}{county_fips}" if county_fips else STATE_FIPS
    occurrence_ref = canonical_property_ref(
        SOURCE_ID,
        county_geoid,
        "release_occurrence",
        str(fid),
    )
    annual_ref: str | None = None
    if annual_identity["key"] is not None:
        annual_ref = canonical_property_ref(
            SOURCE_ID,
            county_geoid,
            "annual_parcel",
            (
                f"{components['tax_year']}:"
                f"{jurisdiction}:"
                f"{annual_identity['fingerprint'][:24]}"
            ),
        )

    owners = []
    for position, field_name in enumerate(("ownername1", "ownername2"), start=1):
        owner = _clean(attributes.get(field_name))
        if owner and all(item["raw_name"] != owner for item in owners):
            owners.append(
                {
                    "raw_name": owner,
                    "role": (
                        "primary_annual_tax_roll_owner"
                        if position == 1
                        else "secondary_annual_tax_roll_owner"
                    ),
                    "assertion_type": "annual_tax_roll_observation",
                    "title_assertion": False,
                }
            )

    mailing_parts = [
        _clean(attributes.get("mailaddres")),
        _clean(attributes.get("mailcity")),
        _clean(attributes.get("mailstate")),
        _postal_code(attributes.get("mailzipcod")),
    ]
    mailing_raw = ", ".join(part for part in mailing_parts if part)
    record = {
        "canonical_ref": occurrence_ref,
        "annual_parcel_canonical_ref": annual_ref,
        "same_record_key": annual_identity["key"] or f"US-WY-DOR:FID:{fid}",
        "same_annual_record_key": annual_identity["key"],
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "source_url": LAYER_URL,
        "viewer_url": DOR_MAPS_URL,
        "record_kind": (
            "wy_dor_annual_parcel_geometry_occurrence"
            if annual_ref
            else "wy_dor_unresolved_geometry_occurrence"
        ),
        "record_scope": "wyoming_dor_annual_statewide_parcels",
        "tax_year": components["tax_year"],
        "jurisdiction_code": jurisdiction,
        "county_name": county.get("name"),
        "county_fips": county_fips,
        "county_geoid": county_geoid if county_fips else None,
        "parcel_number": components["parcel_number"],
        "account_number": components["account_number"],
        "native_parcel_id": components["parcel_number"],
        "native_account_id": components["account_number"],
        "native_feature_id": str(fid),
        "source_row_id": _number(attributes.get("ID")),
        "identity": {
            "annual_parcel_join": annual_identity,
            "release_occurrence": {
                "basis": "arcgis_fid",
                "fid": fid,
                "canonical_ref": occurrence_ref,
                "durable_across_annual_releases": False,
            },
        },
        "owners": owners,
        "situs_address": {
            "raw": _clean(attributes.get("locationad")),
            "state": STATE_CODE,
        },
        "mailing_address": {
            "raw": mailing_raw or None,
            "line1": mailing_parts[0],
            "city": mailing_parts[1],
            "state": mailing_parts[2],
            "postal_code": mailing_parts[3],
        },
        "legal_description": _clean(attributes.get("legal")),
        "assessment": {
            "tax_year": components["tax_year"],
            "actual_value": _number(attributes.get("actualvalu")),
            "assessed_value": _number(attributes.get("assessedva")),
            "currency": "USD",
            "default_tax_district": _clean(attributes.get("DEFAULTTAX")),
            "assertion_type": "annual_tax_roll_observation",
        },
        "land": {
            "gross_acres": _number(attributes.get("landgrossa")),
            "gross_square_feet": _number(attributes.get("landgrosss")),
            "source_shape_area_square_meters": _number(
                attributes.get("Shape__Area")
            ),
            "source_shape_length_meters": _number(
                attributes.get("Shape__Length")
            ),
        },
        "source_snapshot": {
            "item_id": ITEM_ID,
            "release_year": RELEASE_YEAR,
            **dict(source_version),
        },
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "layer_schema_fingerprint": layer_schema_fingerprint,
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": attributes,
    }
    if "geometry" in feature:
        record["geometry"] = feature.get("geometry")
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = "EPSG:4326"
        record["geometry_role"] = "annual_parcel_feature_occurrence"
    return record


def _match_clause(field: str, value: Any, match: str) -> str:
    text = _sql_literal(value).upper()
    if match == "exact":
        return f"UPPER({field})='{text}'"
    if match == "starts":
        return f"UPPER({field}) LIKE '{text}%'"
    if match == "contains":
        return f"UPPER({field}) LIKE '%{text}%'"
    raise ValueError(f"unsupported match mode: {match}")


def _or_match(fields: Sequence[str], value: Any, match: str) -> str:
    return "(" + " OR ".join(
        _match_clause(field, value, match) for field in fields
    ) + ")"


def _fid_clause(value: Any) -> str:
    text = _clean(value)
    if text is None or not text.isdigit():
        raise ValueError("FID must be a nonnegative integer")
    return f"FID={int(text)}"


def _tax_year_clause(value: Any) -> str:
    text = _clean(value)
    if text is None or not re.fullmatch(r"[0-9]{4}", text):
        raise ValueError("tax year must contain four digits")
    return f"taxyear='{text}'"


def _where(
    operation: str,
    *,
    selector: Any = None,
    match: str = "contains",
    jurisdiction: Any = None,
    tax_year: Any = None,
) -> str:
    if operation == "owner":
        base = _or_match(("ownername1", "ownername2"), selector, match)
    elif operation == "parcel":
        base = _match_clause("parcelnb", selector, match)
    elif operation == "account":
        base = _match_clause("accountno", selector, match)
    elif operation in {"county", "jurisdiction"}:
        county = normalize_jurisdiction(selector)
        base = f"jurisdicti='{county}'"
    elif operation == "situs":
        base = _match_clause("locationad", selector, match)
    elif operation == "mailing":
        base = _or_match(
            ("mailaddres", "mailcity", "mailstate", "mailzipcod"),
            selector,
            match,
        )
    elif operation == "legal":
        base = _match_clause("legal", selector, match)
    elif operation in {"fid", "geometry"}:
        base = _fid_clause(selector)
    elif operation in {"point", "bbox"}:
        base = "1=1"
    elif operation == "probe":
        base = " AND ".join(
            (
                f"taxyear='{PROBE_TAX_YEAR}'",
                f"jurisdicti='{PROBE_JURISDICTION}'",
                f"parcelnb='{PROBE_PARCEL}'",
                f"accountno='{PROBE_ACCOUNT}'",
            )
        )
    else:
        raise ValueError(f"unsupported Wyoming parcel operation: {operation}")

    filters = [base]
    if jurisdiction is not None and operation not in {"county", "jurisdiction"}:
        county = normalize_jurisdiction(jurisdiction)
        filters.append(f"jurisdicti='{county}'")
    if tax_year is not None and operation != "probe":
        filters.append(_tax_year_clause(tax_year))
    return " AND ".join(
        f"({item})" if " OR " in item else item for item in filters
    )


def _coordinate(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be numeric") from error
    return number


def _spatial_parameters(
    operation: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if operation == "point":
        longitude = _coordinate(args.longitude, "longitude")
        latitude = _coordinate(args.latitude, "latitude")
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("point coordinates must be valid WGS84 longitude/latitude")
        return {
            "geometry": f"{longitude},{latitude}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        }
    if operation == "bbox":
        xmin = _coordinate(args.xmin, "xmin")
        ymin = _coordinate(args.ymin, "ymin")
        xmax = _coordinate(args.xmax, "xmax")
        ymax = _coordinate(args.ymax, "ymax")
        if not -180 <= xmin <= 180 or not -180 <= xmax <= 180:
            raise ValueError("bbox longitudes must be valid WGS84 values")
        if not -90 <= ymin <= 90 or not -90 <= ymax <= 90:
            raise ValueError("bbox latitudes must be valid WGS84 values")
        if xmin >= xmax or ymin >= ymax:
            raise ValueError("bbox minima must be smaller than maxima")
        return {
            "geometry": f"{xmin},{ymin},{xmax},{ymax}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        }
    return {}


def build_query(
    operation: str,
    *,
    selector: Any,
    parameters: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters={"selector": selector, **dict(parameters)},
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def source_routes() -> dict[str, Any]:
    """Return the annual publisher lineage and county evidence routes."""

    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_route_map",
        "observed_at": OBSERVED_AT,
        "primary": {
            "root_app_item_id": ROOT_APP_ITEM_ID,
            "root_app_url": ROOT_APP_URL,
            "item_id": ITEM_ID,
            "item_url": ITEM_URL,
            "layer_url": LAYER_URL,
            "record_class": "annual_statewide_tax_roll_and_parcel_geometry",
        },
        "same_publisher_lineage": [
            {
                "name": "ArcGIS hosted-item export",
                "url": ITEM_URL,
                "relationship": "same_annual_feature_service_release",
                "formats": (
                    "CSV",
                    "Shapefile",
                    "GeoPackage",
                    "File Geodatabase",
                    "GeoJSON",
                    "Parquet",
                ),
            },
            {
                "name": "Wyoming DOR Assessment Data Download",
                "url": DOR_DOWNLOAD_URL,
                "relationship": "same_authority_annual_assessment_lineage",
            },
        ],
        "county_route_directory": {
            "name": "Wyoming ETS county GIS and mapping sites",
            "url": COUNTY_DIRECTORY_URL,
            "coverage": tuple(value["name"] for value in COUNTIES.values()),
        },
        "field_matched_county_complements": [
            {
                "role": "county_assessor",
                "record_class": "current_local_assessment_and_property_account",
                "join_fields": ("jurisdiction", "parcel_number", "account_number"),
            },
            {
                "role": "county_treasurer",
                "record_class": "property_tax_bill_balance_and_payment",
                "join_fields": ("jurisdiction", "parcel_number", "account_number"),
            },
            {
                "role": "county_clerk",
                "record_class": "recorded_instrument_index_and_document",
                "join_fields": (
                    "owner_candidate",
                    "parcel_number",
                    "account_number",
                    "situs_address",
                    "legal_description",
                ),
            },
        ],
    }


def _new_client(args: argparse.Namespace) -> WyomingDORClient:
    return WyomingDORClient(
        page_size=getattr(args, "page_size", DEFAULT_PAGE_SIZE),
        max_records=getattr(args, "max_records", None),
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        minimum_interval=getattr(
            args,
            "minimum_interval",
            DEFAULT_MINIMUM_INTERVAL,
        ),
    )


def _client(
    args: argparse.Namespace,
    client: Any | None,
) -> Any:
    return client if client is not None else _new_client(args)


def _discovery_result(
    args: argparse.Namespace,
    *,
    client: Any | None,
) -> PublicRecordsResult:
    mode = args.mode
    query = build_query(
        "discovery",
        selector=mode,
        parameters={"mode": mode},
        limit=None,
        cursor=None,
    )
    if mode == "source":
        record = {
            "source_id": SOURCE_ID,
            "record_kind": "source_manifest",
            "authority": "Wyoming Department of Revenue, Property Tax Division",
            "release_year": RELEASE_YEAR,
            "root_app_item_id": ROOT_APP_ITEM_ID,
            "root_app_url": ROOT_APP_URL,
            "root_app_metadata_url": ROOT_APP_METADATA_URL,
            "root_app_data_url": ROOT_APP_DATA_URL,
            "item_id": ITEM_ID,
            "item_url": ITEM_URL,
            "item_metadata_url": ITEM_METADATA_URL,
            "layer_url": LAYER_URL,
            "layer_name": "Wyoming_Parcels_for_2026",
            "object_id_field": "FID",
            "geometry_type": "esriGeometryPolygon",
            "required_fields": REQUIRED_FIELDS,
        }
        return PublicRecordsResult.success(query, [record], warnings=SOURCE_WARNINGS)
    if mode == "counties":
        records = [
            {
                "source_id": SOURCE_ID,
                "record_kind": "annual_jurisdiction_coverage",
                "tax_year": RELEASE_YEAR,
                "jurisdiction_code": code,
                "county_name": value["name"],
                "county_fips": value["fips"],
                "county_geoid": f"{STATE_FIPS}{value['fips']}",
                "observed_feature_occurrences": value["count"],
                "observed_at": OBSERVED_AT,
            }
            for code, value in COUNTIES.items()
        ]
        return PublicRecordsResult.success(query, records, warnings=SOURCE_WARNINGS)
    if mode == "identity":
        return PublicRecordsResult.success(
            query,
            [
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "annual_identity_audit",
                    **IDENTITY_AUDIT,
                }
            ],
            warnings=SOURCE_WARNINGS,
        )
    if mode == "routes":
        return PublicRecordsResult.success(
            query,
            [source_routes()],
            warnings=SOURCE_WARNINGS,
        )

    source_client = _client(args, client)
    try:
        if mode == "agreement":
            agreement = validate_app_agreement(
                source_client.app_item(),
                source_client.app_data(),
            )
            return PublicRecordsResult.success(
                query,
                [
                    {
                        "source_id": SOURCE_ID,
                        "record_kind": "root_application_layer_agreement",
                        **agreement,
                    }
                ],
                warnings=SOURCE_WARNINGS,
            )
        validated = validate_layer_metadata(source_client.metadata())
    except PublicRecordsHTTPError as error:
        return failure_result(query, error, warnings=SOURCE_WARNINGS)
    record = {
        "source_id": SOURCE_ID,
        "record_kind": "source_layer_metadata",
        "item_id": ITEM_ID,
        "layer_url": LAYER_URL,
        "native_page_size": validated["native_page_size"],
        "layer_schema": validated["schema"],
        "layer_schema_fingerprint": validated["schema_fingerprint"],
        "source_version": validated["source_version"],
    }
    return PublicRecordsResult.success(query, [record], warnings=SOURCE_WARNINGS)


def _verify_probe(records: Sequence[Mapping[str, Any]]) -> None:
    if len(records) != 1:
        raise SourceSchemaError(
            "Wyoming DOR probe expected one exact annual parcel occurrence",
            url=LAYER_URL,
            details={"observed_count": len(records)},
        )
    record = records[0]
    geometry = record.get("geometry")
    rings = geometry.get("rings") if isinstance(geometry, Mapping) else None
    if (
        record.get("tax_year") != PROBE_TAX_YEAR
        or record.get("jurisdiction_code") != PROBE_JURISDICTION
        or record.get("parcel_number") != PROBE_PARCEL
        or record.get("account_number") != PROBE_ACCOUNT
        or record.get("situs_address", {}).get("raw") != PROBE_SITUS
        or not isinstance(rings, (list, tuple))
        or not rings
    ):
        raise SourceSchemaError(
            "Wyoming DOR exact annual parcel sentinel changed",
            url=LAYER_URL,
            details={
                "tax_year": PROBE_TAX_YEAR,
                "jurisdiction": PROBE_JURISDICTION,
                "parcel_number": PROBE_PARCEL,
                "account_number": PROBE_ACCOUNT,
                "situs": PROBE_SITUS,
            },
        )


def _invalid_query_result(
    operation: str,
    selector: Any,
    error: ValueError,
) -> PublicRecordsResult:
    query = build_query(
        operation,
        selector=selector,
        parameters={},
        limit=None,
        cursor=None,
    )
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


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one standalone Wyoming annual-parcel operation."""

    operation = args.command
    if operation == "discovery":
        result = _discovery_result(args, client=client)
        if log_results:
            _best_effort_log(result)
        return result

    selector: Any = getattr(args, "query", None)
    try:
        where = _where(
            operation,
            selector=selector,
            match=getattr(args, "match", "contains"),
            jurisdiction=getattr(args, "jurisdiction", None),
            tax_year=getattr(args, "tax_year", None),
        )
        spatial = _spatial_parameters(operation, args)
    except ValueError as error:
        result = _invalid_query_result(operation, selector, error)
        if log_results:
            _best_effort_log(result)
        return result

    if operation == "point":
        selector = {
            "longitude": float(args.longitude),
            "latitude": float(args.latitude),
        }
    elif operation == "bbox":
        selector = {
            "xmin": float(args.xmin),
            "ymin": float(args.ymin),
            "xmax": float(args.xmax),
            "ymax": float(args.ymax),
        }
    elif operation == "probe":
        selector = {
            "tax_year": PROBE_TAX_YEAR,
            "jurisdiction": PROBE_JURISDICTION,
            "parcel_number": PROBE_PARCEL,
            "account_number": PROBE_ACCOUNT,
        }

    requested_limit = (
        None if operation == "probe" else getattr(args, "limit", None)
    )
    cursor = None if operation == "probe" else getattr(args, "cursor", None)
    max_records = (
        None if operation == "probe" else getattr(args, "max_records", None)
    )
    return_geometry = (
        operation in {"geometry", "probe"}
        or bool(getattr(args, "geometry", False))
    )
    query_parameters = {
        "match": getattr(args, "match", None),
        "jurisdiction": getattr(args, "jurisdiction", None),
        "tax_year": getattr(args, "tax_year", None),
        "return_geometry": return_geometry,
        "max_records": max_records,
        "ordered_by": "FID ASC",
        "spatial": spatial or None,
        "bounded_exact_sentinel": operation == "probe",
    }
    query = build_query(
        operation,
        selector=selector,
        parameters=query_parameters,
        limit=requested_limit,
        cursor=cursor,
    )
    source_client = _client(args, client)
    app_agreement: dict[str, Any] | None = None
    statewide_occurrence_count: int | None = None
    try:
        if operation == "probe":
            app_agreement = validate_app_agreement(
                source_client.app_item(),
                source_client.app_data(),
            )
            statewide_occurrence_count = source_client.count()
        validated = validate_layer_metadata(source_client.metadata())
        if hasattr(source_client, "page_size"):
            source_client.page_size = min(
                int(source_client.page_size),
                validated["native_page_size"],
            )
        parameters = {
            "orderByFields": "FID ASC",
            **spatial,
        }
        if return_geometry:
            parameters["outSR"] = 4326
        fetched = source_client.query(
            where=where,
            out_fields="*",
            parameters=parameters,
            requested_limit=requested_limit,
            max_records=max_records,
            cursor=cursor,
            return_geometry=return_geometry,
        )
        records = [
            normalize_feature(
                feature,
                response_schema_fingerprint=fetched.schema_fingerprint,
                layer_schema_fingerprint=validated["schema_fingerprint"],
                source_version=validated["source_version"],
            )
            for feature in fetched.records
        ]
        if operation == "owner":
            for record in records:
                record["query_match"] = {
                    "domain": "annual_tax_roll_owner",
                    "selector": getattr(args, "query", None),
                    "match_mode": getattr(args, "match", "contains"),
                    "resolution_status": "unresolved_candidate",
                }
        if operation == "probe":
            _verify_probe(records)
            records[0]["source_probe"] = {
                "root_application_agreement": app_agreement,
                "layer_validation": validated,
                "statewide_occurrence_count": statewide_occurrence_count,
            }
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
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
    else:
        warnings = (*SOURCE_WARNINGS, *fetched.warnings)
        if fetched.truncated_by_cap:
            result = PublicRecordsResult(
                query=query,
                status=ResultStatus.PARTIAL,
                records=records,
                next_cursor=fetched.next_cursor,
                warnings=warnings,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=fetched.next_cursor,
                warnings=warnings,
            )

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
        log_search(canonical_json(result.query.to_dict()), SOURCE_ID, result_count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    if write_output(
        result.to_dict(),
        args,
        summary=(
            f"Wyoming DOR parcels {args.command} ({result.status.value})"
        ),
    ):
        return
    print(
        f"Wyoming DOR parcels {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('native_feature_id') or '-'} | "
            f"{record.get('jurisdiction_code') or '-'} | "
            f"{record.get('parcel_number') or '-'} | "
            f"{record.get('account_number') or '-'} | "
            f"{record.get('situs_address', {}).get('raw') or ''}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


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


def _tax_year(value: str) -> str:
    if not re.fullmatch(r"[0-9]{4}", value):
        raise argparse.ArgumentTypeError("must contain four digits")
    return value


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="ArcGIS transport page size, bounded by the live layer maximum",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
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
    parser.add_argument("--cursor", help="ArcGIS continuation cursor")
    parser.add_argument(
        "--max-records",
        type=_positive_int,
        help="Optional caller-selected ceiling across technical pages",
    )
    _add_transport_args(parser)


def _add_search_context(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--jurisdiction",
        "--county",
        dest="jurisdiction",
        help="Optional Wyoming county/jurisdiction filter",
    )
    parser.add_argument("--tax-year", type=_tax_year)
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Include WGS84 parcel feature geometry",
    )


def _add_search_parser(
    subparsers: Any,
    command: str,
    help_text: str,
    *,
    default_match: str,
    include_context: bool = True,
) -> None:
    parser = subparsers.add_parser(command, help=help_text)
    parser.add_argument("query")
    parser.add_argument(
        "--match",
        choices=("contains", "starts", "exact"),
        default=default_match,
    )
    if include_context:
        _add_search_context(parser)
    else:
        parser.add_argument("--tax-year", type=_tax_year)
        parser.add_argument("--geometry", action="store_true")
    _add_window_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the Wyoming Department of Revenue annual statewide "
            "parcel layer"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_search_parser(
        subparsers,
        "owner",
        "Search annual tax-roll owner observations",
        default_match="contains",
    )
    _add_search_parser(
        subparsers,
        "parcel",
        "Search parcel numbers",
        default_match="exact",
    )
    _add_search_parser(
        subparsers,
        "account",
        "Search county property account numbers",
        default_match="exact",
    )
    _add_search_parser(
        subparsers,
        "situs",
        "Search situs/location address",
        default_match="contains",
    )
    _add_search_parser(
        subparsers,
        "mailing",
        "Search owner mailing fields",
        default_match="contains",
    )
    _add_search_parser(
        subparsers,
        "legal",
        "Search legal descriptions",
        default_match="contains",
    )
    for command in ("county", "jurisdiction"):
        _add_search_parser(
            subparsers,
            command,
            "Fetch one county/jurisdiction annual occurrence inventory",
            default_match="exact",
            include_context=False,
        )

    fid_parser = subparsers.add_parser("fid", help="Fetch one release FID")
    fid_parser.add_argument("query")
    _add_search_context(fid_parser)
    _add_window_args(fid_parser)

    geometry_parser = subparsers.add_parser(
        "geometry",
        help="Fetch WGS84 geometry for one release FID",
    )
    geometry_parser.add_argument("query")
    geometry_parser.add_argument("--tax-year", type=_tax_year)
    geometry_parser.add_argument("--jurisdiction", "--county", dest="jurisdiction")
    _add_window_args(geometry_parser)

    point_parser = subparsers.add_parser(
        "point",
        help="Find parcel occurrences intersecting a WGS84 point",
    )
    point_parser.add_argument("longitude")
    point_parser.add_argument("latitude")
    _add_search_context(point_parser)
    _add_window_args(point_parser)

    bbox_parser = subparsers.add_parser(
        "bbox",
        help="Find parcel occurrences intersecting a WGS84 bounding box",
    )
    bbox_parser.add_argument("xmin")
    bbox_parser.add_argument("ymin")
    bbox_parser.add_argument("xmax")
    bbox_parser.add_argument("ymax")
    _add_search_context(bbox_parser)
    _add_window_args(bbox_parser)

    discovery_parser = subparsers.add_parser(
        "discovery",
        help="Show source, counties, identity audit, routes, or live metadata",
    )
    discovery_parser.add_argument(
        "mode",
        choices=(
            "source",
            "counties",
            "identity",
            "routes",
            "agreement",
            "metadata",
        ),
    )
    _add_transport_args(discovery_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Run the exact government-owned annual parcel sentinel",
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
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
