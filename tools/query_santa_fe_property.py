#!/usr/bin/env python3
"""Query Santa Fe County assessor parcel and assessment observations.

The county's Tax Parcel Viewer is an ArcGIS application backed by the public
``LAND/Accounts/MapServer/0`` layer.  This adapter queries that layer directly
and retains the source's account, owner, address, legal-description, valuation,
and recorder-join fields.

The source's 2,000-row ArcGIS transfer size is technical pagination, not a
published-data limit.  With no ``--limit`` or ``--max-records``, the adapter
continues until the source reports that the matching result set is exhausted.

Examples:
    uv run python tools/query_santa_fe_property.py owner "SANTA FE COUNTY" \
        --output /tmp/santa-fe-county.json
    uv run python tools/query_santa_fe_property.py address "18 DINKLE RD" \
        --json
    uv run python tools/query_santa_fe_property.py parcel 910002704 --json
    uv run python tools/query_santa_fe_property.py objectid 249 --geometry \
        --json
    uv run python tools/query_santa_fe_property.py probe --json
    uv run python tools/query_santa_fe_property.py routes --json
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


SOURCE_ID = "us-nm-santa-fe-assessor-accounts"
SOURCE = SOURCE_ID
COUNTY_GEOID = "35049"
STATE_CODE = "NM"
COUNTY_NAME = "Santa Fe County"
OBSERVED_AT = "2026-07-31"

OFFICIAL_ASSESSOR_URL = "https://www.santafecountynm.gov/assessor/"
TAX_PARCEL_VIEWER_URL = (
    "https://sfcomaps.santafecountynm.gov/mapsvc/apps/webappviewer/"
    "index.html?id=7ba6293895454413a140b25200f40fda"
)
PORTAL_URL = "https://sfcomaps.santafecountynm.gov/mapsvc"
APP_ITEM_ID = "7ba6293895454413a140b25200f40fda"
WEB_MAP_ITEM_ID = "f845a6fead3b464ca52880a0d618dc9f"
LAYER_URL = (
    "https://sfcomaps.santafecountynm.gov/restsvc/rest/services/"
    "LAND/Accounts/MapServer/0"
)
LAYER_NAME = "ACCOUNTS"
SOURCE_MAX_PAGE_SIZE = 2_000
GEOMETRY_CRS = "EPSG:2258"

PARCEL_DOWNLOAD_ITEM_ID = "98a3e4e30d7c4495a6d74499e6996a44"
PARCEL_DOWNLOAD_PUBLISHED_URL = (
    "https://sfcserver.co.santa-fe.nm.us/restsvc/rest/services/"
    "Hosted/ParcelDownload/FeatureServer"
)
PARCEL_DOWNLOAD_RESOLVED_URL = (
    "https://sfcomaps.santafecountynm.gov/restsvc/rest/services/"
    "Hosted/ParcelDownload/FeatureServer/0"
)
PARCEL_MAP_ITEM_ID = "d7a8094e799a416d8863ebe6be4e35e1"
PARCEL_MAP_URL = (
    "https://sfcomaps.santafecountynm.gov/restsvc/rest/services/"
    "LAND/Parcels/MapServer/0"
)
NOTICE_MANAGER_URL = (
    "https://assrdocs.santafecountynm.gov/AXPortal/login.aspx"
)
CLERK_RECORDS_PAGE = (
    "https://www.santafecountynm.gov/clerk/divisions/"
    "research-public-records-access"
)
CLERKTRACK_URL = (
    "https://clerktrackweb.santafecountynm.gov/CTWeb/login.aspx"
)
TREASURER_SEARCH_URL = (
    "https://paydici.com/santa-fe-treasurer-nm/search/"
    "property-tax-search-group"
)

PROBE_UPC = "1037057082517000000"
PROBE_PARCEL_NUMBER = "910002704"
PROBE_OWNER = "SANTA FE COUNTY"

REQUIRED_FIELDS = frozenset(
    {
        "OBJECTID",
        "UPC",
        "parcel_number",
        "eff_from_date",
        "eff_to_date",
        "active_status",
        "situs_line_1",
        "situs_city",
        "owner_name",
        "owner_line_1",
        "tca_number",
        "township",
        "section",
        "range",
        "legal_text",
        "property_class",
        "book_page",
        "acreage",
        "adeed",
        "adhst",
        "current_assessed_land",
        "current_assessed_imp",
        "prior_assessed_land",
        "prior_assessed_imp",
    }
)

MARKET_FIELDS = (
    "market_land_comm",
    "market_land_res",
    "market_land_ag",
    "market_land_dry",
    "market_land_grazing",
    "market_land_irrigated",
    "market_imp_comm",
    "market_imp_res",
    "market_imp_ag",
    "market_mnt",
    "market_new",
)

EXEMPTION_FIELDS = (
    "is_exempt_gov",
    "is_exempt_nongov",
    "is_exempt_state_assessed",
    "is_disabled_veteran",
    "is_head_of_family",
    "is_veteran_1",
    "is_veteran_2",
    "is_senior_freeze",
    "is_affordable_housing",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Santa Fe County Assessor Accounts",
    source_role="county_assessor_live_parcel_and_assessment_observations",
    base_url=LAYER_URL,
    dataset_id=f"{WEB_MAP_ITEM_ID}/LAND/Accounts/MapServer/0",
    metadata={
        "authority": "Office of the Santa Fe County Assessor",
        "official_assessor_url": OFFICIAL_ASSESSOR_URL,
        "tax_parcel_viewer_url": TAX_PARCEL_VIEWER_URL,
        "portal_url": PORTAL_URL,
        "app_item_id": APP_ITEM_ID,
        "web_map_item_id": WEB_MAP_ITEM_ID,
        "layer_name": LAYER_NAME,
        "native_max_record_count": SOURCE_MAX_PAGE_SIZE,
        "publication_grain": "live ArcGIS account-parcel feature occurrence",
        "observed_at": OBSERVED_AT,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=f"{COUNTY_NAME}, New Mexico",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality=COUNTY_NAME,
)

SOURCE_WARNINGS = (
    (
        "Owner names are Assessor account observations. Recorded instruments "
        "from the County Clerk are the independent title-event source."
    ),
    (
        "The Tax Parcel Viewer geometry is cadastral mapping and may differ "
        "from a surveyed legal boundary."
    ),
    (
        "ParcelDownload, the Parcels map layer, and Notice of Value PDFs are "
        "other Santa Fe County Assessor representations, not independent "
        "corroboration of the same account fields."
    ),
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "normalization_version": 1,
        "required_fields": sorted(REQUIRED_FIELDS),
        "market_fields": MARKET_FIELDS,
        "exemption_fields": EXEMPTION_FIELDS,
    }
)

SOURCE_ROUTES: tuple[dict[str, Any], ...] = (
    {
        "route_id": SOURCE_ID,
        "name": "Assessor Accounts live layer",
        "authority": "Office of the Santa Fe County Assessor",
        "record_class": "current parcel/account and assessment observation",
        "access": "verified_anonymous_arcgis_query",
        "url": LAYER_URL,
        "selectors": [
            "owner_name",
            "situs_address",
            "mailing_address",
            "UPC",
            "parcel_number",
            "OBJECTID",
        ],
        "source_published_grain": "live account-parcel feature occurrence",
        "technical_pagination": {
            "mechanism": "resultOffset/resultRecordCount",
            "native_max_page_size": SOURCE_MAX_PAGE_SIZE,
        },
        "relationship_to_primary": "primary",
        "independent_evidence": True,
        "observed_count": 90_695,
        "observed_count_note": (
            "Includes geometry occurrences without populated account fields."
        ),
    },
    {
        "route_id": "us-nm-santa-fe-assessor-parcel-download",
        "name": "Assessor ParcelDownload feature service",
        "authority": "Office of the Santa Fe County Assessor",
        "record_class": "published parcel snapshot",
        "access": "verified_anonymous_query_sync_extract",
        "portal_item_id": PARCEL_DOWNLOAD_ITEM_ID,
        "published_url": PARCEL_DOWNLOAD_PUBLISHED_URL,
        "resolved_url": PARCEL_DOWNLOAD_RESOLVED_URL,
        "resolution_evidence": (
            "The current host returns the published portal serviceItemId."
        ),
        "relationship_to_primary": "same_record_snapshot",
        "independent_evidence": False,
        "join_fields": ["UPC", "parcel_number", "GlobalID"],
        "observed_count": 81_841,
    },
    {
        "route_id": "us-nm-santa-fe-assessor-parcels-map",
        "name": "Assessor Parcels map layer",
        "authority": "Office of the Santa Fe County Assessor",
        "record_class": "parcel geometry and summarized account fields",
        "access": "verified_anonymous_arcgis_query",
        "portal_item_id": PARCEL_MAP_ITEM_ID,
        "url": PARCEL_MAP_URL,
        "relationship_to_primary": "same_record_alternate_layer",
        "independent_evidence": False,
        "join_fields": ["UPC", "Parcel_Number"],
    },
    {
        "route_id": "us-nm-santa-fe-assessor-notices",
        "name": "Assessor Notice of Values Document Manager",
        "authority": "Office of the Santa Fe County Assessor",
        "record_class": "annual notice of value index and PDF",
        "access": "verified_public_session",
        "url": NOTICE_MANAGER_URL,
        "selectors": ["property_id", "valuation_year", "notice_type"],
        "relationship_to_primary": "same_authority_field_matched_document",
        "independent_evidence": False,
        "join_fields": ["parcel_number/property_id"],
        "artifact": "one-page PDF notice",
    },
    {
        "route_id": "us-nm-santa-fe-clerktrack-index",
        "name": "County Clerk ClerkTrack recording index",
        "authority": "Office of the Santa Fe County Clerk",
        "record_class": "recorded instrument index",
        "access": "verified_county_published_guest_index_login",
        "official_access_page": CLERK_RECORDS_PAGE,
        "url": CLERKTRACK_URL,
        "selectors": [
            "party",
            "recording_date",
            "instrument_number",
            "book_page",
            "document_type",
            "legal_description",
        ],
        "technical_pagination": {
            "mechanism": "ASP.NET GridView page selector",
            "native_page_size": 25,
        },
        "relationship_to_primary": "independent_recorded_instrument",
        "independent_evidence": True,
        "join_fields": [
            "recording_num/instrument_number",
            "book_page",
            "owner/party",
            "legal_description",
        ],
    },
    {
        "route_id": "us-nm-santa-fe-treasurer-paydici",
        "name": "County Treasurer property-tax search",
        "authority": "Office of the Santa Fe County Treasurer",
        "record_class": "tax bill, balance, and payment observation",
        "access": "verified_interactive_search_with_recaptcha",
        "url": TREASURER_SEARCH_URL,
        "selectors": ["account_number", "name", "address"],
        "relationship_to_primary": "distinct_tax_record",
        "independent_evidence": True,
        "join_fields": ["parcel_number/account_number", "name", "address"],
    },
)


class SantaFeArcGISClient(ArcGISRESTClient):
    """ArcGIS client with an explicit layer-metadata preflight."""

    def metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Santa Fe ArcGIS layer metadata must be an object",
                url=self.layer_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "Santa Fe ArcGIS returned an error for layer metadata",
                url=self.layer_url,
                details={"response": payload["error"]},
            )
        return payload


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()
    return text or None


def _unique(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = _clean(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)
    return output


def _arcgis_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(
                value / 1_000,
                tz=timezone.utc,
            ).date().isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    text = _clean(value)
    if not text:
        return None
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = _clean(value)
    if not text:
        return None
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _address(attributes: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    lines = [
        _clean(attributes.get(f"{prefix}_line_1")),
        _clean(attributes.get(f"{prefix}_line_2")),
        _clean(attributes.get(f"{prefix}_line_3")),
    ]
    city = _clean(attributes.get(f"{prefix}_city"))
    state = _clean(attributes.get(f"{prefix}_state"))
    postal_code = _clean(attributes.get(f"{prefix}_zip"))
    country = _clean(attributes.get(f"{prefix}_country"))
    raw = ", ".join(
        item
        for item in (*lines, city, state, postal_code, country)
        if item
    )
    return {
        "raw": raw or None,
        "care_of": _clean(attributes.get(f"{prefix}_care_of")),
        "line1": lines[0],
        "line2": lines[1],
        "line3": lines[2],
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "country": country,
    }


def _recording_note(value: Any) -> dict[str, Any] | None:
    raw = _clean(value)
    if not raw:
        return None
    match = re.match(
        r"^(?P<number>\S+)\s+REC\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})$",
        raw,
        flags=re.IGNORECASE,
    )
    return {
        "raw": raw,
        "instrument_number": match.group("number") if match else None,
        "recording_date": (
            _arcgis_date(match.group("date")) if match else None
        ),
    }


def _book_page_refs(value: Any) -> list[dict[str, str]]:
    raw = _clean(value)
    if not raw:
        return []
    return [
        {"book": match.group(1), "page": match.group(2)}
        for match in re.finditer(r"\b(\d+)\s*/\s*(\d+)\b", raw)
    ]


def _sql_literal(value: str) -> str:
    normalized = _clean(value)
    if not normalized:
        raise ValueError("query value must not be blank")
    return normalized.replace("'", "''")


def _where(
    operation: str,
    selector: str | None,
    *,
    active_only: bool = False,
) -> str:
    if operation == "probe":
        where = f"UPC='{PROBE_UPC}'"
    else:
        value = _sql_literal(selector or "")
        upper = value.upper()
        if operation == "owner":
            where = f"UPPER(owner_name) LIKE '%{upper}%'"
        elif operation == "address":
            where = " OR ".join(
                f"UPPER({field}) LIKE '%{upper}%'"
                for field in (
                    "situs_line_1",
                    "situs_line_2",
                    "situs_line_3",
                )
            )
            where = f"({where})"
        elif operation == "mailing":
            where = " OR ".join(
                f"UPPER({field}) LIKE '%{upper}%'"
                for field in (
                    "owner_line_1",
                    "owner_line_2",
                    "owner_line_3",
                )
            )
            where = f"({where})"
        elif operation == "parcel":
            where = (
                f"UPC='{value}' OR parcel_number='{value}' "
                f"OR alt_id='{value}'"
            )
        elif operation == "objectid":
            if not value.isdigit():
                raise ValueError("objectid must be numeric")
            where = f"OBJECTID={int(value)}"
        else:
            raise ValueError(
                f"unsupported Santa Fe property operation: {operation}"
            )
    if active_only:
        return f"({where}) AND active_status='A'"
    return where


def validate_layer_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the source fields and paging features used by the adapter."""

    if _clean(metadata.get("name")) != LAYER_NAME:
        raise SourceSchemaError(
            "Santa Fe ArcGIS layer identity changed",
            url=LAYER_URL,
            details={"expected": LAYER_NAME, "observed": metadata.get("name")},
        )
    if _clean(metadata.get("geometryType")) != "esriGeometryPolygon":
        raise SourceSchemaError(
            "Santa Fe ArcGIS layer geometry type changed",
            url=LAYER_URL,
            details={"observed": metadata.get("geometryType")},
        )
    capabilities = {
        item.strip()
        for item in str(metadata.get("capabilities") or "").split(",")
        if item.strip()
    }
    if "Query" not in capabilities:
        raise SourceSchemaError(
            "Santa Fe ArcGIS layer no longer declares Query capability",
            url=LAYER_URL,
        )
    field_definitions = metadata.get("fields")
    if not isinstance(field_definitions, list) or any(
        not isinstance(field, Mapping) for field in field_definitions
    ):
        raise SourceSchemaError(
            "Santa Fe ArcGIS layer field declarations are malformed",
            url=LAYER_URL,
        )
    field_names = {
        str(field.get("name"))
        for field in field_definitions
        if field.get("name") is not None
    }
    missing = sorted(REQUIRED_FIELDS - field_names)
    if missing:
        raise SourceSchemaError(
            "Santa Fe ArcGIS layer is missing required fields",
            url=LAYER_URL,
            details={"missing_fields": missing},
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping) or not (
        advanced.get("supportsPagination") is True
        and advanced.get("supportsOrderBy") is True
    ):
        raise SourceSchemaError(
            "Santa Fe ArcGIS ordered pagination contract changed",
            url=LAYER_URL,
        )
    max_record_count = metadata.get("maxRecordCount")
    if (
        isinstance(max_record_count, bool)
        or not isinstance(max_record_count, int)
        or max_record_count <= 0
    ):
        raise SourceSchemaError(
            "Santa Fe ArcGIS metadata lacks a native page size",
            url=LAYER_URL,
        )
    schema = {
        "layer_name": LAYER_NAME,
        "geometry_type": metadata.get("geometryType"),
        "max_record_count": max_record_count,
        "capabilities": sorted(capabilities),
        "advanced_query_capabilities": {
            "supports_pagination": True,
            "supports_order_by": True,
        },
        "fields": [
            {
                "name": field.get("name"),
                "type": field.get("type"),
                "length": field.get("length"),
            }
            for field in field_definitions
        ],
    }
    return {
        "native_page_size": max_record_count,
        "schema": schema,
        "schema_fingerprint": sha256_fingerprint(schema),
    }


def _assessment_period(
    attributes: Mapping[str, Any],
    period: str,
) -> dict[str, Any]:
    return {
        "source_fields": {
            "assessed_land": _number(
                attributes.get(f"{period}_assessed_land")
            ),
            "assessed_improvement": _number(
                attributes.get(f"{period}_assessed_imp")
            ),
            "assessed_use": _number(
                attributes.get(f"{period}_assessed_use")
            ),
            "exemption": _number(
                attributes.get(f"{period}_exemption")
            ),
        },
        "market_components": {
            field: _number(attributes.get(f"{period}_{field}"))
            for field in MARKET_FIELDS
        },
        "currency": "USD",
    }


def normalize_feature(
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
    layer_schema_fingerprint: str,
) -> dict[str, Any]:
    """Normalize one live Assessor account-layer feature."""

    attribute_value = feature.get("attributes")
    if not isinstance(attribute_value, Mapping):
        raise ValueError(
            "Santa Fe ArcGIS feature attributes must be an object"
        )
    attributes = dict(attribute_value)
    upc = _clean(attributes.get("UPC"))
    parcel_number = _clean(attributes.get("parcel_number"))
    alt_id = _clean(attributes.get("alt_id"))
    object_id = attributes.get("OBJECTID")
    native_feature_id = _clean(object_id)
    native_parcel_id = upc or parcel_number
    native_id = native_parcel_id or native_feature_id
    if not native_id:
        raise ValueError(
            "Santa Fe ArcGIS feature lacks UPC, parcel number, and OBJECTID"
        )
    if upc:
        identity_basis = "upc"
    elif parcel_number:
        identity_basis = "parcel_number"
    else:
        identity_basis = "objectid"
    durable_parcel_identity = native_parcel_id is not None
    canonical_kind = (
        "parcel" if durable_parcel_identity else "feature_occurrence"
    )
    record_kind = (
        "parcel_account_observation"
        if durable_parcel_identity
        else "parcel_geometry_feature_occurrence"
    )
    owner_name = _clean(attributes.get("owner_name"))
    owners = (
        [
            {
                "raw_name": owner_name,
                "role": "assessor_owner",
                "assertion_type": "assessment_account_observation",
            }
        ]
        if owner_name
        else []
    )
    book_page_raw = _clean(attributes.get("book_page"))
    recording_number = _clean(attributes.get("recording_num"))
    assessor_deed = _recording_note(attributes.get("adeed"))
    assessor_history = _recording_note(attributes.get("adhst"))
    same_record_key = (
        f"US-NM-SANTA-FE:PARCEL:{native_parcel_id}"
        if durable_parcel_identity
        else f"US-NM-SANTA-FE:FEATURE:{native_feature_id}"
    )
    same_authority_representations = [
        representation
        for representation in (
            {
                "source_id": (
                    "us-nm-santa-fe-assessor-parcel-download"
                ),
                "join_value": upc,
                "relationship": "same_record_snapshot",
            },
            {
                "source_id": "us-nm-santa-fe-assessor-notices",
                "join_value": parcel_number,
                "relationship": "field_matched_notice_document",
            },
        )
        if representation["join_value"]
    ]

    record: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            canonical_kind,
            native_id,
        ),
        "same_record_key": same_record_key,
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "record_kind": record_kind,
        "record_scope": "county_assessor_live_layer",
        "source_url": LAYER_URL,
        "viewer_url": TAX_PARCEL_VIEWER_URL,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "identity": {
            "basis": identity_basis,
            "tier": (
                "durable_parcel_account"
                if durable_parcel_identity
                else "layer_feature_occurrence"
            ),
            "durable_parcel_identity": durable_parcel_identity,
            "projection_eligible_as_parcel": durable_parcel_identity,
        },
        "native_parcel_id": native_parcel_id,
        "native_feature_id": native_feature_id,
        "upc": upc,
        "parcel_number": parcel_number,
        "alternate_parcel_ids": _unique([parcel_number, alt_id]),
        "object_id": object_id,
        "account_status": _clean(attributes.get("active_status")),
        "effective_from": _arcgis_date(
            attributes.get("eff_from_date")
        ),
        "effective_to": _arcgis_date(attributes.get("eff_to_date")),
        "owners": owners,
        "situs_address": _address(attributes, "situs"),
        "mailing_address": _address(attributes, "owner"),
        "legal": {
            "description_raw": _clean(attributes.get("legal_text")),
            "acreage": _number(attributes.get("acreage")),
            "acreage_raw": _clean(attributes.get("acreage")),
            "township": _clean(attributes.get("township")),
            "range": _clean(attributes.get("range")),
            "section": _clean(attributes.get("section")),
            "quarter": _clean(attributes.get("quarter")),
            "subdivision_type": _clean(
                attributes.get("subdiv_type_description")
            ),
            "subdivision_name": _clean(attributes.get("subdiv_name")),
            "subdivision_phase": _clean(attributes.get("subdiv_phase")),
            "subdivision_block": _clean(attributes.get("subdiv_block")),
            "subdivision_lot": _clean(attributes.get("subdiv_lot")),
            "subdivision_number": _clean(attributes.get("subdiv_num")),
            "map_number": _clean(attributes.get("map_no")),
        },
        "classification": {
            "pact_code": _clean(attributes.get("pact_code")),
            "roll_code": _clean(attributes.get("roll_code")),
            "tax_district": _clean(attributes.get("tax_district")),
            "tca_number": _clean(attributes.get("tca_number")),
            "property_class": _clean(attributes.get("property_class")),
            "neighborhood_number": attributes.get("neighborhood_num"),
            "neighborhood_name": _clean(
                attributes.get("neighborhood_name")
            ),
        },
        "assessment": {
            "current": _assessment_period(attributes, "current"),
            "prior": _assessment_period(attributes, "prior"),
        },
        "exemption_indicators": {
            field: attributes.get(field) for field in EXEMPTION_FIELDS
        },
        "recorder_index_hints": {
            "target_source_id": "us-nm-santa-fe-clerktrack-index",
            "recording_number": recording_number,
            "book_page_raw": book_page_raw,
            "book_page_refs": _book_page_refs(book_page_raw),
            "assessor_deed_note": assessor_deed,
            "assessor_history_note": assessor_history,
            "relationship": "assessor_supplied_join_hint",
        },
        "same_authority_representations": (
            same_authority_representations
        ),
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "layer_schema_fingerprint": layer_schema_fingerprint,
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": attributes,
    }
    if "geometry" in feature:
        record["geometry"] = feature.get("geometry")
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = "EPSG:4326"
    return record


def build_query(
    operation: str,
    selector: str | None,
    *,
    limit: int | None,
    cursor: str | None,
    active_only: bool,
    return_geometry: bool,
    max_records: int | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "active_only": active_only,
                "return_geometry": return_geometry,
                "max_records": max_records,
                "source_published_grain": (
                    "live ArcGIS account-parcel feature occurrence"
                ),
            },
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _client(args: argparse.Namespace) -> SantaFeArcGISClient:
    return SantaFeArcGISClient(
        LAYER_URL,
        page_size=min(args.page_size, SOURCE_MAX_PAGE_SIZE),
        max_records=args.max_records,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
    )


def _invalid_query_result(
    args: argparse.Namespace,
    error: ValueError,
) -> PublicRecordsResult:
    query = build_query(
        args.command,
        getattr(args, "query", None),
        limit=getattr(args, "limit", None),
        cursor=getattr(args, "cursor", None),
        active_only=getattr(args, "active_only", False),
        return_geometry=getattr(args, "geometry", False),
        max_records=getattr(args, "max_records", None),
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


def _metadata_result(
    args: argparse.Namespace,
    *,
    client: SantaFeArcGISClient | Any | None = None,
) -> PublicRecordsResult:
    """Return the validated live-layer metadata in a canonical envelope."""

    query = build_query(
        "metadata",
        None,
        limit=None,
        cursor=None,
        active_only=False,
        return_geometry=False,
        max_records=None,
    )
    source_client = client or _client(args)
    try:
        validated = validate_layer_metadata(source_client.metadata())
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_metadata",
                    "dataset_id": SOURCE_METADATA.dataset_id,
                    "layer_url": LAYER_URL,
                    "layer_contract": validated["schema"],
                    "layer_schema_fingerprint": validated[
                        "schema_fingerprint"
                    ],
                    "native_page_size": validated[
                        "native_page_size"
                    ],
                    "route_map": route_map(),
                }
            ],
            warnings=SOURCE_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    _best_effort_log(query, result)
    return result


def _routes_result() -> PublicRecordsResult:
    """Return verified route and lineage relationships as one record."""

    query = build_query(
        "routes",
        None,
        limit=None,
        cursor=None,
        active_only=False,
        return_geometry=False,
        max_records=None,
    )
    return PublicRecordsResult.success(
        query,
        [route_map()],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: SantaFeArcGISClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute a live parcel-layer lookup."""

    operation = args.command
    if operation == "metadata":
        return _metadata_result(args, client=client)
    if operation == "routes":
        return _routes_result()
    selector = getattr(args, "query", None)
    limit = None if operation == "probe" else args.limit
    try:
        where = _where(
            operation,
            selector,
            active_only=args.active_only,
        )
    except ValueError as error:
        return _invalid_query_result(args, error)
    query = build_query(
        operation,
        selector,
        limit=limit,
        cursor=args.cursor,
        active_only=args.active_only,
        return_geometry=args.geometry,
        max_records=args.max_records,
    )
    source_client = client or _client(args)
    try:
        metadata = validate_layer_metadata(source_client.metadata())
        if hasattr(source_client, "page_size"):
            source_client.page_size = min(
                source_client.page_size,
                metadata["native_page_size"],
            )
        query_parameters: dict[str, Any] = {
            "orderByFields": "OBJECTID",
        }
        if args.geometry:
            query_parameters["outSR"] = 4326
        fetched = source_client.query(
            where=where,
            out_fields="*",
            parameters=query_parameters,
            requested_limit=limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        records = [
            normalize_feature(
                feature,
                response_schema_fingerprint=(
                    fetched.schema_fingerprint
                ),
                layer_schema_fingerprint=(
                    metadata["schema_fingerprint"]
                ),
            )
            for feature in fetched.records
        ]
        if operation == "probe":
            if (
                len(records) != 1
                or records[0]["upc"] != PROBE_UPC
                or records[0]["parcel_number"] != PROBE_PARCEL_NUMBER
            ):
                raise SourceSchemaError(
                    "Santa Fe parcel probe sentinel changed",
                    url=LAYER_URL,
                    details={
                        "expected_upc": PROBE_UPC,
                        "expected_parcel_number": PROBE_PARCEL_NUMBER,
                    },
                )
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

    _best_effort_log(query, result)
    return result


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
) -> None:
    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(
            canonical_json(query.to_dict()),
            SOURCE_ID,
            result_count,
        )
    except Exception as error:
        print(
            f"Warning: search log was not updated: {error}",
            file=sys.stderr,
        )


def route_map() -> dict[str, Any]:
    """Return the verified Santa Fe property-source relationship map."""

    return {
        "jurisdiction": {
            "county": COUNTY_NAME,
            "state": STATE_CODE,
            "county_geoid": COUNTY_GEOID,
        },
        "observed_at": OBSERVED_AT,
        "primary_adapter_source_id": SOURCE_ID,
        "routes": [dict(route) for route in SOURCE_ROUTES],
        "relationship_rule": (
            "Assessor layers, snapshots, and notices are alternate "
            "representations of Assessor records. Clerk instruments and "
            "Treasurer tax records are distinct record classes."
        ),
    }


def _emit_routes(args: argparse.Namespace) -> None:
    data = route_map()
    if write_output(
        data,
        args,
        summary="Santa Fe County property source routes",
        result_count=len(SOURCE_ROUTES),
    ):
        return
    print("Santa Fe County property source routes")
    for route in SOURCE_ROUTES:
        relationship = route["relationship_to_primary"]
        print(
            f"  {route['route_id']} | {route['access']} | {relationship}"
        )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=(
            f"Santa Fe County property {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    print(
        f"Santa Fe County property {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "source_metadata":
            print(
                f"  {record['dataset_id']} | "
                f"native page {record['native_page_size']} | "
                f"schema {record['layer_schema_fingerprint']}"
            )
            continue
        owners = ", ".join(
            owner["raw_name"] for owner in record["owners"]
        )
        display_id = (
            record["native_parcel_id"]
            or f"feature:{record['native_feature_id']}"
        )
        print(
            f"  {display_id} | "
            f"{record['situs_address']['raw'] or '?'} | "
            f"{owners or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional caller-selected result window",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation cursor from a previous result",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Select source rows whose active_status is A",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Return parcel geometry transformed to EPSG:4326",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=SOURCE_MAX_PAGE_SIZE,
        help="ArcGIS request page size, bounded by the source-native maximum",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional caller-selected ceiling across technical pages",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.0)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Santa Fe County Assessor parcel and assessment records"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("owner", "Search Assessor owner-name observations"),
        ("address", "Search situs-address observations"),
        ("mailing", "Search owner mailing-address observations"),
        ("parcel", "Look up a UPC, parcel number, or alternate ID"),
        ("objectid", "Look up one ArcGIS object ID"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_query_arguments(command_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Verify the layer contract with a county-owned parcel",
    )
    _add_query_arguments(probe_parser)

    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Validate and return the live ArcGIS layer contract",
    )
    _add_query_arguments(metadata_parser)

    routes_parser = subparsers.add_parser(
        "routes",
        help="Show verified Assessor, Clerk, and Treasurer route relationships",
    )
    add_output_args(routes_parser)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "routes":
        _emit_routes(args)
        return 0
    if (
        (args.limit is not None and args.limit <= 0)
        or args.page_size <= 0
        or args.timeout <= 0
        or args.minimum_interval < 0
        or (args.max_records is not None and args.max_records <= 0)
    ):
        parser.error(
            "limit is optional; page-size and timeout must be positive; "
            "minimum-interval must not be negative; max-records is optional"
        )
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
