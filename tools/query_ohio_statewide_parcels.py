#!/usr/bin/env python3
"""Query Ohio's official OGRIP statewide parcel public view.

The Ohio Geographically Referenced Information Program (OGRIP) publishes one
standardized ArcGIS polygon layer assembled from county-maintained parcel data.
The public view is useful as a statewide parcel-ID, address, land-use, mailing-
address, geometry, and local-CAMA routing index.  Recorder instruments, title
evidence, tax balances, foreclosure dockets, owner names, and assessed values
remain separate source families.

Omitting ``--limit`` traverses every native match.  An explicit limit returns a
query- and schema-bound continuation cursor.

Examples:
    uv run python tools/query_ohio_statewide_parcels.py source --json
    uv run python tools/query_ohio_statewide_parcels.py counties --json
    uv run python tools/query_ohio_statewide_parcels.py count --county 39049
    uv run python tools/query_ohio_statewide_parcels.py parcel \
        39049-010-042534 --geometry
    uv run python tools/query_ohio_statewide_parcels.py address DODRIDGE \
        --county Franklin
    uv run python tools/query_ohio_statewide_parcels.py probe --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

try:
    from tools import oregon_arcgis_keyset as arcgis_shared
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
    from tools.public_records_http import (
        PublicRecordsHTTPError,
        SourceSchemaError,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    import oregon_arcgis_keyset as arcgis_shared
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
    from public_records_http import (
        PublicRecordsHTTPError,
        SourceSchemaError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-oh-ogrip-statewide-parcels"
STATE_CODE = "OH"
STATE_FIPS = "39"
STATE_NAME = "Ohio"
ITEM_ID = "26ab5fad8d5d4258a7492a14de83bc0e"
ITEM_URL = f"https://www.arcgis.com/home/item.html?id={ITEM_ID}&sublayer=0"
LAYER_URL = (
    "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
    "OhioStatewidePacels_full_view/FeatureServer/0"
)
DEFAULT_PAGE_SIZE = 1_000
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1

FIELDS = (
    "OBJECTID",
    "County",
    "LocalParcelID",
    "StateParcelID",
    "StateLUC",
    "SitusAddressAll",
    "MailAddressAll",
    "MailNumber",
    "MailStreetPrefix",
    "MailStreetName",
    "MailStreetSuffix",
    "MailUnitNumber",
    "MailCity",
    "MailZip",
    "MailState",
    "LandArea",
    "LandArea_PY",
    "CurrentTo",
    "CAMADataSite",
    "GlobalID",
    "Shape__Area",
    "Shape__Length",
)

MANIFEST = arcgis_shared.ArcGISLayerManifest(
    source_id=SOURCE_ID,
    name="Ohio Statewide Parcels Public View",
    layer_url=LAYER_URL,
    layer_id=0,
    service_item_id=ITEM_ID,
    expected_layer_name="Parcels",
    object_id_field="OBJECTID",
    required_fields=FIELDS,
    source_crs_wkids=(102723, 3735),
    record_kind="standardized_county_parcel_observation",
    publisher="Ohio Geographically Referenced Information Program",
    observed_count=None,
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Ohio Statewide Parcels Public View",
    source_role=(
        "official_statewide_standardized_county_parcel_geometry_address_"
        "land_use_and_local_cama_index"
    ),
    base_url=LAYER_URL,
    dataset_id=ITEM_ID,
    metadata={
        "publisher": "Ohio Geographically Referenced Information Program",
        "platform_family": "arcgis_feature_service",
        "coverage": "all_88_ohio_counties",
        "native_crs": "EPSG:3735 (native WKID 102723)",
        "output_geometry_crs": "EPSG:4326",
        "owner_name_field": None,
        "assessment_value_fields": [],
        "recorder_instrument_fields": [],
        "tax_balance_fields": [],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_FIPS,
    name=STATE_NAME,
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS},
)

TARGET_COUNTIES: Mapping[str, Mapping[str, Any]] = {
    "39049": {
        "name": "Franklin",
        "observed_count": 454_405,
        "observed_at": "2026-07-30",
        "sample_state_parcel_id": "39049-010-042534",
        "sample_local_parcel_id": "010-042534",
    },
    "39089": {
        "name": "Licking",
        "observed_count": 95_308,
        "observed_at": "2026-07-30",
        "sample_state_parcel_id": "39089-00100000601000",
        "sample_local_parcel_id": "00100000601000",
    },
    "39041": {
        "name": "Delaware",
        "observed_count": 95_456,
        "observed_at": "2026-07-30",
        "sample_state_parcel_id": "39041-10010001001000",
        "sample_local_parcel_id": "10010001001000",
    },
}
TARGET_NAME_TO_GEOID = {
    str(record["name"]).casefold(): geoid
    for geoid, record in TARGET_COUNTIES.items()
}

SOURCE_WARNINGS = (
    "OGRIP is a standardized statewide parcel observation assembled from "
    "county-maintained data; the linked county system may contain newer changes.",
    "The public layer exposes parcel IDs, address observations, land use, land "
    "area, geometry, and a local CAMA link, but no owner-name, assessed-value, "
    "recorder-instrument, or tax-balance fields.",
    "CurrentTo is a row-level upstream date. ArcGIS service-edit dates describe "
    "the published representation and are a separate freshness signal.",
    "Parcel polygons are mapping geometry rather than surveyed legal boundaries.",
)


SOURCE_GRAPH: Mapping[str, Any] = {
    "graph_schema_version": "ohio-property-source-graph/1.0",
    "observed_at": "2026-07-31",
    "statewide_component": {
        "source_id": SOURCE_ID,
        "url": LAYER_URL,
        "item_url": ITEM_URL,
        "publisher": "Ohio Geographically Referenced Information Program",
        "access": "anonymous_arcgis_feature_service",
        "access_observed_at": "2026-07-30",
        "coverage": "all_88_ohio_counties",
        "field_domains": [
            "parcel_identifier",
            "situs_address_observation",
            "mailing_address_observation",
            "state_land_use_code",
            "land_area",
            "parcel_polygon",
            "local_cama_route",
        ],
        "fields_not_present": [
            "owner_name",
            "assessed_value",
            "recorder_instrument",
            "tax_balance",
            "foreclosure_case",
        ],
        "indexed_selector_observations": [
            "County",
            "LocalParcelID",
            "CAMADataSite",
            "StateLUC",
        ],
        "unindexed_selector_observations": ["StateParcelID"],
    },
    "counties": [
        {
            "county_geoid": "39049",
            "county_name": "Franklin",
            "ogrip_inventory_observation": {
                "record_count": 454_405,
                "observed_at": "2026-07-30",
            },
            "assessment_and_parcel": [
                {
                    "source_id": "us-oh-franklin-county-auditor-bulk",
                    "name": "Franklin County Auditor Bulk Data Library",
                    "url": "https://auditor.franklincountyohio.gov/Auditor/FTP",
                    "directory_url": "https://apps.franklincountyauditor.com/",
                    "access": "anonymous_bulk_directories",
                    "observed_status": "available",
                    "observed_at": "2026-07-31",
                    "platform_family": "anonymous_iis_directory_bulk_library",
                    "field_domains": [
                        "assessment_and_appraisal_releases",
                        "tax_accounting_and_payments",
                        "daily_conveyances",
                        "assessor_sales",
                        "parcel_csv",
                        "parcel_geometry_and_gis",
                    ],
                },
                {
                    "source_id": "us-oh-franklin-county-auditor-sales-gis",
                    "name": "Franklin County Auditor Sales Information GIS",
                    "url": (
                        "https://gis.franklincountyohio.gov/hosting/rest/"
                        "services/RealEstate/Sales_Information/FeatureServer/0"
                    ),
                    "access": "anonymous_arcgis_feature_service",
                    "observed_status": "available_source_managed_snapshot",
                    "observed_at": "2026-07-31",
                    "integration_status": "implemented",
                    "canonical_layer": 0,
                    "renderer_alias_layers": [1, 2, 3, 4],
                    "field_domains": [
                        "sale_date_and_price",
                        "grantor_and_grantee",
                        "conveyance_and_instrument_reference",
                        "sale_qualification",
                        "parcel_and_situs",
                        "point_geometry",
                    ],
                },
                {
                    "name": "Franklin County Auditor IASWorld",
                    "url": "https://property.franklincountyauditor.com/",
                    "access": "anonymous",
                    "observed_status": "available",
                    "observed_at": "2026-07-30",
                    "field_domains": [
                        "assessment_owner_observation",
                        "parcel",
                        "valuation",
                        "transfer_observation",
                    ],
                },
                {
                    "name": "OGRIP statewide parcel public view",
                    "url": LAYER_URL,
                    "access": "anonymous",
                    "observed_status": "available",
                    "observed_at": "2026-07-30",
                    "relationship": "statewide_standardized_index_and_geometry",
                },
            ],
            "recorder_and_title": [
                {
                    "name": "Franklin County Recorder GovOS PublicSearch",
                    "url": "https://franklin.oh.publicsearch.us/",
                    "official_info_url": (
                        "https://www.franklincountyohio.gov/Agency-Directory/"
                        "Recorder/Real-Estate/Public-Records-Search"
                    ),
                    "access": "anonymous",
                    "observed_status": "available",
                    "observed_at": "2026-07-30",
                    "platform_family": "govos_publicsearch",
                    "field_domains": [
                        "instrument",
                        "grantor",
                        "grantee",
                        "document_type",
                        "recording_date",
                        "document_image",
                    ],
                }
            ],
            "tax_and_foreclosure": [
                {
                    "name": "Franklin County Treasurer Property Search",
                    "url": "https://treapropsearch.franklincountyohio.gov/",
                    "access": "anonymous",
                    "observed_at": "2026-07-30",
                    "field_domains": [
                        "tax_balance",
                        "tax_history",
                        "assessed_value",
                        "market_value",
                    ],
                },
                {
                    "name": "Franklin County Sheriff SaleAuction",
                    "url": "https://franklin.sheriffsaleauction.ohio.gov/",
                    "access": "anonymous_viewing",
                    "observed_at": "2026-07-30",
                    "platform_family": "realauction_sheriff_sale",
                    "field_domains": ["scheduled_foreclosure_sale"],
                },
            ],
        },
        {
            "county_geoid": "39089",
            "county_name": "Licking",
            "ogrip_inventory_observation": {
                "record_count": 95_308,
                "observed_at": "2026-07-30",
            },
            "assessment_and_parcel": [
                {
                    "source_id": "us-oh-licking-county-auditor-gis",
                    "name": "Licking County Auditor Parcel Search GIS",
                    "url": (
                        "https://gis.lickingcounty.gov/server/rest/services/"
                        "Auditor/ParcelsSearch/MapServer/0"
                    ),
                    "access": "anonymous_arcgis_map_service",
                    "observed_status": "available",
                    "observed_at": "2026-07-31",
                    "platform_family": "arcgis_mapserver_feature_layer",
                    "feature_occurrence_identity": (
                        "GlobalID_with_OBJECTID_locator_and_fallback"
                    ),
                    "parcel_business_join": "Parcel_when_nonblank",
                    "field_domains": [
                        "assessment_owner_observation",
                        "parcel_identifier",
                        "situs_address_observation",
                        "mailing_address_observation",
                        "valuation",
                        "building_attributes",
                        "recent_transfer_observations",
                        "parcel_polygon",
                    ],
                },
                {
                    "name": "Licking County Auditor OnTrac",
                    "url": "https://ontrac.lickingcounty.gov/",
                    "official_info_url": (
                        "https://lickingcounty.gov/depts/auditor/"
                    ),
                    "access": "http_403_observed",
                    "observed_status": "not_automatable_in_live_probe",
                    "observed_at": "2026-07-30",
                    "field_domains": [
                        "assessment_owner_observation",
                        "parcel",
                        "valuation",
                        "tax_property_detail",
                    ],
                    "field_matched_alternatives": [
                        {
                            "source_id": "us-oh-licking-county-auditor-gis",
                            "fields": [
                                "assessment_owner_observation",
                                "parcel_identifier",
                                "situs_address_observation",
                                "mailing_address_observation",
                                "valuation",
                                "building_attributes",
                                "recent_transfer_observations",
                                "parcel_polygon",
                            ],
                        },
                        {
                            "source_id": SOURCE_ID,
                            "fields": [
                                "parcel_identifier",
                                "situs_address_observation",
                                "mailing_address_observation",
                                "land_use",
                                "land_area",
                                "parcel_polygon",
                            ],
                        }
                    ],
                }
            ],
            "recorder_and_title": [
                {
                    "name": "Licking County Recorder PAX",
                    "url": (
                        "https://apps.lickingcounty.gov/recorder/paxworld/"
                    ),
                    "access": "account_required_for_discovery",
                    "observed_status": "available_with_login",
                    "observed_at": "2026-07-30",
                    "platform_family": "dts_paxworld",
                    "field_domains": [
                        "instrument",
                        "grantor",
                        "grantee",
                        "legal_description",
                        "document_image",
                    ],
                },
                {
                    "name": "Licking Recorder exact-instrument detail",
                    "url_template": (
                        "https://apps.lickingcounty.gov/recorder/"
                        "record-search/?instrument={instrument}"
                    ),
                    "access": "anonymous_exact_instrument",
                    "observed_status": "available",
                    "observed_at": "2026-07-30",
                },
                {
                    "name": "Licking County Archives recorder collections",
                    "url": (
                        "https://lickingcounty.gov/depts/records_n_archives/"
                        "list_of_record_collections_by_department/recorder.htm"
                    ),
                    "access": "request_and_archive",
                    "observed_at": "2026-07-30",
                    "field_domains": [
                        "historic_deeds_1803_1918",
                        "historic_mortgages_1851_1941",
                    ],
                },
            ],
            "tax_and_foreclosure": [
                {
                    "name": "Licking County Sheriff Foreclosures",
                    "url": (
                        "https://apps.lickingcounty.gov/sheriff/foreclosures/"
                    ),
                    "access": "anonymous",
                    "observed_status": "available",
                    "observed_at": "2026-07-30",
                    "field_domains": [
                        "foreclosure_case_number",
                        "parcel",
                        "address",
                        "appraised_amount",
                        "sale_status",
                    ],
                },
                {
                    "name": "Licking County Sheriff SaleAuction",
                    "url": "https://licking.sheriffsaleauction.ohio.gov/",
                    "access": "anonymous_viewing",
                    "observed_at": "2026-07-30",
                    "platform_family": "realauction_sheriff_sale",
                    "field_domains": ["scheduled_foreclosure_sale"],
                },
            ],
        },
        {
            "county_geoid": "39041",
            "county_name": "Delaware",
            "ogrip_inventory_observation": {
                "record_count": 95_456,
                "observed_at": "2026-07-30",
            },
            "assessment_and_parcel": [
                {
                    "name": "Delaware County Manatron Property Search",
                    "url": "https://delaware-auditor-ohio.manatron.com/",
                    "official_info_url": (
                        "https://auditor.co.delaware.oh.us/"
                        "real-estate-data-property-search/"
                    ),
                    "access": "anonymous",
                    "observed_status": "available",
                    "observed_at": "2026-07-30",
                    "platform_family": "manatron",
                    "field_domains": [
                        "assessment_owner_observation",
                        "parcel",
                        "valuation",
                        "tax_levy_distribution",
                    ],
                },
                {
                    "name": "Delaware County Auditor GIS",
                    "url": "https://auditor.delco-gis.org/",
                    "access": "anonymous",
                    "observed_status": "available_with_maintenance_notice",
                    "observed_at": "2026-07-30",
                    "field_domains": ["parcel_map", "parcel_route"],
                },
            ],
            "recorder_and_title": [
                {
                    "name": "Delaware County Recorder PAX",
                    "url": "https://delaware.dts-central-oh.com/PaxWorld/",
                    "official_info_url": (
                        "https://recorder.co.delaware.oh.us/"
                        "records-search-page/"
                    ),
                    "access": "anonymous_after_disclaimer",
                    "observed_status": "available",
                    "observed_at": "2026-07-30",
                    "platform_family": "dts_paxworld",
                    "field_domains": [
                        "instrument",
                        "grantor",
                        "grantee",
                        "book_page",
                        "document_image",
                    ],
                }
            ],
            "tax_and_foreclosure": [
                {
                    "name": "Delaware County Treasurer Property Lookup",
                    "url": "https://co.delaware.oh.us/pnp/searchprod.asp",
                    "access": "anonymous",
                    "observed_at": "2026-07-30",
                    "field_domains": ["tax_property_lookup"],
                },
                {
                    "name": "Delaware County Sheriff SaleAuction",
                    "url": "https://delaware.sheriffsaleauction.ohio.gov/",
                    "official_info_url": (
                        "https://sheriff.co.delaware.oh.us/sheriff-sales/"
                    ),
                    "access": "anonymous_viewing",
                    "observed_at": "2026-07-30",
                    "platform_family": "realauction_sheriff_sale",
                    "field_domains": [
                        "scheduled_foreclosure_sale",
                        "scheduled_tax_sale",
                    ],
                },
            ],
        },
    ],
    "field_relationships": [
        {
            "from": "ogrip_assessment_parcel_observation",
            "to": "county_recorder_instrument",
            "join": "parcel_identifier_or_legal_description_then_verify_instrument",
            "relationship": "complementary_evidence_domains",
        },
        {
            "from": "county_tax_property_record",
            "to": "foreclosure_sale",
            "join": "parcel_identifier_and_case_number",
            "relationship": "tax_and_enforcement_sequence",
        },
        {
            "from": "foreclosure_sale",
            "to": "court_filing",
            "join": "case_number",
            "relationship": "sale_listing_to_case_docket",
        },
    ],
    "process_learnings": [
        {
            "learning": "probe_full_application_path",
            "evidence": (
                "The Delaware DTS host root returned 403 while /PaxWorld/ "
                "returned the anonymous application."
            ),
        },
        {
            "learning": "choose_alternatives_by_field_domain",
            "evidence": (
                "The anonymous Licking Auditor GIS route supplies owner, "
                "parcel, address, value, building, transfer, and polygon "
                "fields when OnTrac is blocked; OGRIP adds the standardized "
                "statewide parcel representation."
            ),
        },
        {
            "learning": "separate_representation_and_row_freshness",
            "evidence": (
                "The ArcGIS item can be recently edited while CurrentTo retains "
                "an older county-export date."
            ),
        },
        {
            "learning": "prefer_indexed_join_selectors",
            "evidence": (
                "County plus LocalParcelID returned an exact polygon promptly; "
                "StateParcelID alone was not indexed and timed out in a probe."
            ),
        },
        {
            "learning": "keep_property_record_roles_distinct",
            "evidence": (
                "Assessment owner observations, recorder instruments, tax "
                "accounts, foreclosure listings, and court dockets answer "
                "different questions and join through explicit identifiers."
            ),
        },
    ],
}


class OhioParcelSelectionError(ValueError):
    """Structured query-selection failure."""

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

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="query_selection",
            retryable=False,
            details=self.details,
        )


class OhioParcelClient(arcgis_shared.BoundedArcGISClient):
    """OGRIP binding with a bounded distinct-county inventory request."""

    def fetch_distinct_counties(self) -> tuple[str, ...]:
        payload = self._request_json(
            self.manifest.query_url,
            params={
                "where": "County IS NOT NULL",
                "outFields": "County",
                "returnDistinctValues": "true",
                "returnGeometry": "false",
                "orderByFields": "County ASC",
                "f": "json",
            },
            maximum_bytes=2_000_000,
        )
        features = payload.get("features")
        if not isinstance(features, list):
            raise SourceSchemaError(
                "OGRIP distinct-county response lacks a features array",
                url=self.manifest.query_url,
            )
        counties: set[str] = set()
        for feature in features:
            if not isinstance(feature, Mapping):
                raise SourceSchemaError(
                    "OGRIP distinct-county response contains a malformed feature",
                    url=self.manifest.query_url,
                )
            county = _clean_text(
                arcgis_shared.feature_attributes(feature).get("County")
            )
            if county is not None:
                counties.add(county)
        if not counties:
            raise SourceSchemaError(
                "OGRIP distinct-county response is empty",
                url=self.manifest.query_url,
            )
        return tuple(sorted(counties))


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _sql_text(value: Any, field_name: str = "query") -> str:
    text = _clean_text(value)
    if text is None:
        raise OhioParcelSelectionError(
            "blank_query",
            f"{field_name} must not be blank",
        )
    return text.replace("'", "''")


def _county_selection(value: str | None) -> tuple[str | None, str | None]:
    text = _clean_text(value)
    if text is None:
        return None, None
    normalized = re.sub(
        r"\s+(county(?:,\s*ohio)?|ohio)$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if re.fullmatch(r"39[0-9]{3}", normalized):
        target = TARGET_COUNTIES.get(normalized)
        return (
            str(target["name"]) if target is not None else None,
            normalized,
        )
    target_geoid = TARGET_NAME_TO_GEOID.get(normalized.casefold())
    if target_geoid is not None:
        return str(TARGET_COUNTIES[target_geoid]["name"]), target_geoid
    return normalized.title(), None


def _target_for_state_parcel(
    value: str,
) -> tuple[str | None, str | None, str | None]:
    match = re.fullmatch(r"(39[0-9]{3})-(.+)", value)
    if match is None:
        return None, None, None
    geoid, local_id = match.groups()
    target = TARGET_COUNTIES.get(geoid)
    return geoid, str(target["name"]) if target else None, local_id


def _county_clause(args: argparse.Namespace) -> tuple[str | None, str | None]:
    county_name, county_geoid = _county_selection(getattr(args, "county", None))
    if county_name is None and county_geoid is not None:
        return f"StateParcelID LIKE '{county_geoid}-%'", county_geoid
    if county_name is None:
        return None, None
    return f"County='{_sql_text(county_name, 'county')}'", county_geoid


def _selector_clause(
    operation: str,
    args: argparse.Namespace,
) -> tuple[str, str | None]:
    if operation == "list":
        return "1=1", None
    if operation == "objectid":
        return f"OBJECTID={int(args.query)}", None
    if operation == "parcel":
        value = _sql_text(args.query, "parcel identifier")
        geoid, county_name, local_id = _target_for_state_parcel(value)
        requested_name, requested_geoid = _county_selection(
            getattr(args, "county", None)
        )
        if geoid is not None and requested_geoid not in {None, geoid}:
            raise OhioParcelSelectionError(
                "county_parcel_conflict",
                "parcel GEOID conflicts with the selected county",
                details={
                    "parcel_geoid": geoid,
                    "selected_county_geoid": requested_geoid,
                },
            )
        if geoid is not None and local_id is not None:
            clauses = [
                f"LocalParcelID='{_sql_text(local_id, 'local parcel identifier')}'",
                f"StateParcelID='{value}'",
            ]
            if county_name is not None:
                clauses.insert(0, f"County='{_sql_text(county_name, 'county')}'")
            elif requested_name is not None:
                clauses.insert(
                    0,
                    f"County='{_sql_text(requested_name, 'county')}'",
                )
            return " AND ".join(clauses), geoid
        return f"LocalParcelID='{value}'", requested_geoid
    value = _sql_text(args.query).upper()
    if operation == "address":
        return f"UPPER(SitusAddressAll) LIKE '%{value}%'", None
    if operation == "search":
        field = args.field
        fields_by_selector = {
            "parcel": ("LocalParcelID", "StateParcelID"),
            "address": ("SitusAddressAll",),
            "mailing": ("MailAddressAll",),
            "land-use": ("StateLUC",),
            "any": (
                "LocalParcelID",
                "StateParcelID",
                "SitusAddressAll",
                "MailAddressAll",
                "StateLUC",
            ),
        }
        fields = fields_by_selector[field]
        return (
            "("
            + " OR ".join(
                f"UPPER({field_name}) LIKE '%{value}%'"
                for field_name in fields
            )
            + ")"
        ), None
    raise OhioParcelSelectionError(
        "unsupported_operation",
        f"unsupported OGRIP parcel operation: {operation}",
    )


def _where(operation: str, args: argparse.Namespace) -> str:
    selector, embedded_geoid = _selector_clause(operation, args)
    county_clause, selected_geoid = _county_clause(args)
    if (
        embedded_geoid is not None
        and selected_geoid is not None
        and embedded_geoid != selected_geoid
    ):
        raise OhioParcelSelectionError(
            "county_parcel_conflict",
            "parcel GEOID conflicts with the selected county",
        )
    clauses = [selector]
    if county_clause and county_clause not in selector:
        clauses.append(county_clause)
    return " AND ".join(f"({clause})" for clause in clauses)


def _epoch_millis_iso(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return (
            datetime.fromtimestamp(value / 1_000, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        return None


def _county_geoid(
    county_name: str | None,
    state_parcel_id: str | None,
) -> str:
    if state_parcel_id is not None:
        match = re.match(r"^(39[0-9]{3})-", state_parcel_id)
        if match:
            return match.group(1)
    if county_name is not None:
        return TARGET_NAME_TO_GEOID.get(county_name.casefold(), STATE_FIPS)
    return STATE_FIPS


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = dict(arcgis_shared.feature_attributes(feature))
    object_id = attributes.get("OBJECTID")
    if isinstance(object_id, bool) or not isinstance(object_id, int):
        raise SourceSchemaError(
            "OGRIP parcel feature lacks integer OBJECTID",
            url=LAYER_URL,
            details={"OBJECTID": object_id},
        )
    county_name = _clean_text(attributes.get("County"))
    local_parcel_id = _clean_text(attributes.get("LocalParcelID"))
    state_parcel_id = _clean_text(attributes.get("StateParcelID"))
    global_id = _clean_text(attributes.get("GlobalID"))
    county_geoid = _county_geoid(county_name, state_parcel_id)
    native_id = state_parcel_id or global_id or str(object_id)
    county_local_parcel_id = (
        f"{county_geoid}|{local_parcel_id}"
        if county_geoid and local_parcel_id
        else None
    )
    current_to_raw = attributes.get("CurrentTo")
    mailing_address_raw = _clean_text(attributes.get("MailAddressAll"))
    geometry = feature.get("geometry") if geometry_requested else None

    result: dict[str, Any] = {
        "record_kind": "standardized_county_parcel_observation",
        "source_id": SOURCE_ID,
        "dataset_id": ITEM_ID,
        "source_record_id": str(object_id),
        "native_id": native_id,
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            county_geoid,
            "parcel" if state_parcel_id else "feature_occurrence",
            native_id,
        ),
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": county_name,
            "county_geoid": county_geoid,
        },
        "object_id": object_id,
        "global_id": global_id,
        "state_parcel_id": state_parcel_id,
        "local_parcel_id": local_parcel_id,
        "county_local_parcel_id": county_local_parcel_id,
        "parcel_identifiers": {
            "state_parcel_id": state_parcel_id,
            "local_parcel_id": local_parcel_id,
        },
        "cross_source_join_keys": [
            {"field": "StateParcelID", "value": state_parcel_id},
            {
                "field": "County+LocalParcelID",
                "value": (
                    f"{county_name}|{local_parcel_id}"
                    if county_name and local_parcel_id
                    else None
                ),
            },
            {
                "field": "county_geoid+LocalParcelID",
                "value": county_local_parcel_id,
            },
        ],
        "situs_address_observation": _clean_text(
            attributes.get("SitusAddressAll")
        ),
        "owner_name_observation": None,
        "assessment_value_observations": None,
        "mailing_address_observation": {
            "raw": mailing_address_raw,
            "number": _clean_text(attributes.get("MailNumber")),
            "street_prefix": _clean_text(attributes.get("MailStreetPrefix")),
            "street_name": _clean_text(attributes.get("MailStreetName")),
            "street_suffix": _clean_text(attributes.get("MailStreetSuffix")),
            "unit": _clean_text(attributes.get("MailUnitNumber")),
            "city": _clean_text(attributes.get("MailCity")),
            "state": _clean_text(attributes.get("MailState")),
            "postal_code": _clean_text(attributes.get("MailZip")),
        },
        "land": {
            "state_land_use_code": _clean_text(attributes.get("StateLUC")),
            "area": attributes.get("LandArea"),
            "prior_year_area": attributes.get("LandArea_PY"),
            "source_units": "source_native_unspecified",
        },
        "source_freshness": {
            "current_to_raw": current_to_raw,
            "current_to_iso": _epoch_millis_iso(current_to_raw),
            "signal_scope": "county_export_row",
        },
        "local_cama_url": _clean_text(attributes.get("CAMADataSite")),
        "field_presence": {
            "owner_name": False,
            "assessment_value": False,
            "recorder_instrument": False,
            "tax_balance": False,
            "mailing_address_observation": {
                "schema_available": True,
                "row_has_value": mailing_address_raw is not None,
            },
        },
        "shape_metrics_native": {
            "area": attributes.get("Shape__Area"),
            "length": attributes.get("Shape__Length"),
        },
        "source_layer_url": LAYER_URL,
        "source_record_selector": {
            "field": "OBJECTID",
            "value": object_id,
        },
        "source_response_schema_fingerprint": schema_fingerprint,
        "raw_attributes": attributes,
    }
    if geometry_requested and geometry is not None:
        result.update(
            {
                "geometry": geometry,
                "geometry_format": "esri_json",
                "geometry_crs": "EPSG:4326",
                "geometry_role": "county_contributed_parcel_mapping_polygon",
            }
        )
    return result


def _source_record() -> dict[str, Any]:
    return {
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "native_manifest": MANIFEST.contract_record(),
        "warnings": list(SOURCE_WARNINGS),
        "source_graph": SOURCE_GRAPH,
    }


def _metadata_record(
    metadata: Mapping[str, Any],
    schema_fingerprint: str,
    maximum_page_size: int,
) -> dict[str, Any]:
    indexes = metadata.get("indexes")
    declared_indexes = []
    if isinstance(indexes, list):
        for index in indexes:
            if isinstance(index, Mapping):
                declared_indexes.append(
                    {
                        "name": index.get("name"),
                        "fields": index.get("fields"),
                        "is_unique": index.get("isUnique"),
                    }
                )
    editing_info = metadata.get("editingInfo")
    return {
        "source_id": SOURCE_ID,
        "layer_url": LAYER_URL,
        "layer_name": metadata.get("name"),
        "layer_id": metadata.get("id"),
        "service_item_id": metadata.get("serviceItemId"),
        "geometry_type": metadata.get("geometryType"),
        "native_spatial_reference": metadata.get("spatialReference"),
        "schema_fingerprint": schema_fingerprint,
        "maximum_page_size": maximum_page_size,
        "declared_indexes": declared_indexes,
        "service_editing_info": (
            dict(editing_info) if isinstance(editing_info, Mapping) else None
        ),
        "required_fields": list(FIELDS),
    }


def _snapshot(batch: arcgis_shared.ArcGISBatch) -> dict[str, Any]:
    return {
        "total_matching_records_at_retrieval": batch.total_count,
        "records_inside_cursor_boundary": batch.bounded_count,
        "boundary_object_id": batch.boundary_object_id,
        "last_object_id": batch.last_object_id,
        "window_returned_records": len(batch.features),
        "continuation_available": batch.next_cursor is not None,
        "pages_fetched": batch.pages_fetched,
        "schema_fingerprint": batch.schema_fingerprint,
        "count_changed_inside_boundary_since_cursor": (
            batch.count_changed_since_cursor
        ),
    }


def _build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for key in ("query", "field", "county", "geometry"):
        if hasattr(args, key):
            parameters[key] = getattr(args, key)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={
                "adapter": "tools/query_ohio_statewide_parcels.py",
                "pagination": "schema_and_object_id_boundary_bound_keyset",
            },
        ),
    )


def _client_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "page_size": args.page_size,
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "retry_attempts": args.retry_attempts,
    }


def _new_client(args: argparse.Namespace) -> OhioParcelClient:
    return OhioParcelClient(MANIFEST, **_client_args(args))


def _selection_failure(
    query: PublicRecordsQuery,
    error: OhioParcelSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _schema_failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.SOURCE_CHANGED,
        [
            PublicRecordsError(
                code="normalization_or_cursor_failed",
                message=str(error),
                category="source_schema",
                retryable=False,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


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
        log_search(canonical_json(query.to_dict()), query.source.source_id, count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute a static graph, live inventory, record query, or probe."""

    query = _build_query(args)
    owned_client = client is None and args.command != "source"
    active_client = client
    try:
        if args.command == "source":
            result = PublicRecordsResult.success(query, [_source_record()])
        else:
            active_client = active_client or _new_client(args)
            if args.command == "metadata":
                metadata = active_client.fetch_metadata()
                schema_fingerprint, maximum = arcgis_shared.metadata_contract(
                    MANIFEST,
                    metadata,
                )
                result = PublicRecordsResult.success(
                    query,
                    [_metadata_record(metadata, schema_fingerprint, maximum)],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "counties":
                metadata = active_client.fetch_metadata()
                arcgis_shared.metadata_contract(MANIFEST, metadata)
                counties = active_client.fetch_distinct_counties()
                target_names = {
                    str(record["name"]) for record in TARGET_COUNTIES.values()
                }
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "county_name": county,
                            "target_county": county in target_names,
                            "county_geoid": TARGET_NAME_TO_GEOID.get(
                                county.casefold()
                            ),
                        }
                        for county in counties
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "count":
                metadata = active_client.fetch_metadata()
                schema_fingerprint, _ = arcgis_shared.metadata_contract(
                    MANIFEST,
                    metadata,
                )
                county_clause, county_geoid = _county_clause(args)
                where = county_clause or "1=1"
                count = active_client.fetch_count(where)
                county_name, _ = _county_selection(args.county)
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "county_name": county_name,
                            "county_geoid": county_geoid,
                            "where": where,
                            "record_count": count,
                            "schema_fingerprint": schema_fingerprint,
                        }
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                metadata = active_client.fetch_metadata()
                schema_fingerprint, maximum = arcgis_shared.metadata_contract(
                    MANIFEST,
                    metadata,
                )
                counties = active_client.fetch_distinct_counties()
                target_probe = []
                for geoid, target in TARGET_COUNTIES.items():
                    county_name = str(target["name"])
                    where = f"County='{_sql_text(county_name, 'county')}'"
                    count = active_client.fetch_count(where)
                    sample_where = (
                        f"{where} AND "
                        "LocalParcelID="
                        f"'{_sql_text(target['sample_local_parcel_id'], 'parcel')}' "
                        "AND StateParcelID="
                        f"'{_sql_text(target['sample_state_parcel_id'], 'parcel')}'"
                    )
                    sample = active_client.fetch_page(
                        where=sample_where,
                        record_count=1,
                        return_geometry=False,
                    )
                    normalized_sample = (
                        _normalize_feature(
                            sample[0],
                            schema_fingerprint=schema_fingerprint,
                            geometry_requested=False,
                        )
                        if sample
                        else None
                    )
                    target_probe.append(
                        {
                            "county_geoid": geoid,
                            "county_name": county_name,
                            "record_count": count,
                            "prior_observed_count": target["observed_count"],
                            "prior_observed_at": target["observed_at"],
                            "sample_state_parcel_id": (
                                normalized_sample["parcel_identifiers"][
                                    "state_parcel_id"
                                ]
                                if normalized_sample
                                else None
                            ),
                            "sample_current_to_iso": (
                                normalized_sample["source_freshness"][
                                    "current_to_iso"
                                ]
                                if normalized_sample
                                else None
                            ),
                        }
                    )
                missing_targets = sorted(
                    str(target["name"])
                    for target in TARGET_COUNTIES.values()
                    if str(target["name"]) not in counties
                )
                if missing_targets:
                    raise SourceSchemaError(
                        "OGRIP county inventory is missing target counties",
                        url=LAYER_URL,
                        details={"missing_target_counties": missing_targets},
                    )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "county_count": len(counties),
                            "expected_statewide_county_count": 88,
                            "maximum_page_size": maximum,
                            "schema_fingerprint": schema_fingerprint,
                            "target_counties": target_probe,
                        }
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                where = _where(args.command, args)
                batch = arcgis_shared.fetch_batch(
                    active_client,
                    MANIFEST,
                    adapter_slug="statewide-parcels",
                    operation=args.command,
                    where=where,
                    limit=(
                        args.limit if args.limit is not None else sys.maxsize
                    ),
                    cursor=args.cursor,
                    return_geometry=args.geometry,
                    cursor_namespace="ohio",
                )
                records = [
                    _normalize_feature(
                        feature,
                        schema_fingerprint=batch.schema_fingerprint,
                        geometry_requested=args.geometry,
                    )
                    for feature in batch.features
                ]
                snapshot = _snapshot(batch)
                for record in records:
                    record["retrieval_snapshot"] = snapshot
                warnings = list(SOURCE_WARNINGS)
                if batch.count_changed_since_cursor:
                    warnings.append(
                        "The record count inside the original object-ID boundary "
                        "changed while that boundary remained in force."
                    )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=batch.next_cursor,
                    warnings=warnings,
                )
    except OhioParcelSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
        result = _schema_failure(query, error)
    finally:
        if owned_client and active_client is not None:
            active_client.close()
    if log_results:
        _best_effort_log(query, result)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Ohio statewide parcels {args.command} ({result.status.value})",
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Ohio statewide parcels {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command == "counties":
            print(
                f"  {record['county_name']} | "
                f"{record.get('county_geoid') or 'unmapped'}"
            )
        elif args.command in {"source", "metadata", "count", "probe"}:
            print(f"  {record.get('source_id', SOURCE_ID)}")
        else:
            identifiers = record.get("parcel_identifiers", {})
            print(
                f"  {identifiers.get('state_parcel_id') or record['object_id']} | "
                f"{record.get('situs_address_observation') or '?'}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="Transport batch size, bounded by live layer metadata",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=3,
    )
    add_output_args(parser)


def _add_county_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--county",
        help="Ohio county name or five-digit GEOID",
    )


def _add_record_args(parser: argparse.ArgumentParser) -> None:
    _add_county_arg(parser)
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller bound; omitted traverses every native match",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation from the same query, county, and geometry selection",
    )
    parser.add_argument(
        "--geometry",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include source geometry transformed to EPSG:4326",
    )
    _add_transport_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Ohio's official OGRIP statewide parcel public view"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show the field-oriented source graph and live manifest",
    )
    add_output_args(source)

    metadata = subparsers.add_parser(
        "metadata",
        help="Validate and report the live ArcGIS layer contract",
    )
    _add_transport_args(metadata)

    counties = subparsers.add_parser(
        "counties",
        help="List counties declared by the live statewide layer",
    )
    _add_transport_args(counties)

    count = subparsers.add_parser(
        "count",
        help="Count statewide or county parcel observations",
    )
    _add_county_arg(count)
    _add_transport_args(count)

    listing = subparsers.add_parser(
        "list",
        help="Traverse statewide or county parcel observations",
    )
    _add_record_args(listing)

    parcel = subparsers.add_parser(
        "parcel",
        help="Look up an exact state or local parcel identifier",
    )
    parcel.add_argument("query")
    _add_record_args(parcel)

    address = subparsers.add_parser(
        "address",
        help="Search situs-address observations",
    )
    address.add_argument("query")
    _add_record_args(address)

    search = subparsers.add_parser(
        "search",
        help="Search selected public-view fields",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=("any", "parcel", "address", "mailing", "land-use"),
        default="any",
    )
    _add_record_args(search)

    objectid = subparsers.add_parser(
        "objectid",
        help="Look up a layer-native OBJECTID",
    )
    objectid.add_argument("query", type=_positive_int)
    _add_record_args(objectid)

    probe = subparsers.add_parser(
        "probe",
        help="Validate schema, statewide county inventory, and target counts",
    )
    _add_transport_args(probe)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
