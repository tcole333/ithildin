#!/usr/bin/env python3
"""Normalize property-source envelopes into the property sidecar.

The adapter-neutral entry point dispatches canonical result envelopes from the
supported parcel and recorder adapters. It preserves the complete query
envelope and each normalized record as canonical JSON with SHA-256 hashes
before projecting stable fields into the shared property model.

Usage:
    uv run python tools/ingest_property_records.py ingest \
      --input /tmp/nc-parcels.json --output /tmp/ingest-summary.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools import (
        dc_property_projection,
        oregon_county_property_projection,
        query_govos_recorders,
        query_mason_county_tax_parcels,
        query_md_mdp_parcel_points,
        query_md_plats,
        query_montana_cadastral,
        query_nyc_pip,
        query_licking_foreclosure_archive,
        query_ohio_franklin_auditor_bulk,
        query_ohio_licking_property,
        query_ohio_pax_recorders,
        query_ohio_sheriff_sales,
        query_oregon_helion_recorder,
        query_orange_tax_collector,
        query_palm_beach_property_appraiser,
        query_palm_beach_tax_collector,
        query_palm_beach_tax_deeds,
        query_santa_fe_clerktrack,
        query_santa_fe_property,
        query_usvi_property_tax,
        query_usvi_recorder,
        query_washington_digital_archives_land,
        query_washington_taxsifter,
        washington_parcel_projection,
    )
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import canonical_json, sha256_fingerprint
    from tools.public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
except ImportError:
    import dc_property_projection
    import oregon_county_property_projection
    import query_govos_recorders
    import query_mason_county_tax_parcels
    import query_md_mdp_parcel_points
    import query_md_plats
    import query_montana_cadastral
    import query_nyc_pip
    import query_licking_foreclosure_archive
    import query_ohio_franklin_auditor_bulk
    import query_ohio_licking_property
    import query_ohio_pax_recorders
    import query_ohio_sheriff_sales
    import query_oregon_helion_recorder
    import query_orange_tax_collector
    import query_palm_beach_property_appraiser
    import query_palm_beach_tax_collector
    import query_palm_beach_tax_deeds
    import query_santa_fe_clerktrack
    import query_santa_fe_property
    import query_usvi_property_tax
    import query_usvi_recorder
    import query_washington_digital_archives_land
    import query_washington_taxsifter
    import washington_parcel_projection
    from output_util import add_output_args, write_output
    from public_records_contract import canonical_json, sha256_fingerprint
    from public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )


NC_ONEMAP_SOURCE_ID = "us-nc-onemap-parcels"
ARLINGTON_PROPERTY_SOURCE_ID = "us-va-arlington-property-map"
BEXAR_PROPERTY_SOURCE_ID = "us-tx-bexar-bcad-property"
DELAWARE_FIRSTMAP_SOURCE_ID = "us-de-firstmap-parcels"
DESCHUTES_PROPERTY_SOURCE_ID = "us-or-deschutes-county-taxlots"
DESCHUTES_CDD_WEBLINK_SOURCE_ID = "us-or-deschutes-cdd-weblink"
BENTON_TAXLOT_OWNER_SOURCE_ID = "us-or-benton-county-taxlot-owners"
BENTON_ASSESSMENT_BULK_SOURCE_ID = "us-or-benton-county-assessment-bulk"
BENTON_ASSESSMENT_MAP_SOURCE_ID = "us-or-benton-county-assessment-maps"
LINCOLN_PROPERTYWEB_SOURCE_ID = "us-or-lincoln-propertyweb"
LINCOLN_TAXLOT_WFS_SOURCE_ID = "us-or-lincoln-county-taxlots-wfs"
LINCOLN_HELION_RECORDER_SOURCE_ID = "us-or-lincoln-helion-recorder"
OREGON_COUNTY_PROPERTY_SOURCE_IDS = (
    oregon_county_property_projection.SUPPORTED_SOURCE_IDS
)
OREGON_COUNTY_ASSESSOR_SOURCE_IDS = (
    oregon_county_property_projection.ASSESSOR_SOURCE_IDS
)
WASHINGTON_PARCEL_SOURCE_IDS = washington_parcel_projection.SUPPORTED_SOURCE_IDS
WASHINGTON_PARCEL_REPRESENTATION_SOURCE_IDS = (
    washington_parcel_projection.PARCEL_SOURCE_IDS
)
WASHINGTON_LAND_RECORDS_SOURCE_ID = (
    query_washington_digital_archives_land.SOURCE_ID
)
MASON_COUNTY_TAX_PARCELS_SOURCE_ID = (
    query_mason_county_tax_parcels.SOURCE_ID
)
WASHINGTON_TAXSIFTER_SOURCE_IDS = frozenset(
    tenant.source_id for tenant in query_washington_taxsifter.TENANTS
)
DC_PROPERTY_SOURCE_IDS = dc_property_projection.SUPPORTED_SOURCE_IDS
DC_PROPERTY_ASSESSOR_SOURCE_IDS = dc_property_projection.ASSESSOR_SOURCE_IDS
JACKSON_ASSESSOR_SOURCE_ID = "us-or-jackson-county-assessor-taxlots"
DOUGLAS_ASSESSOR_SOURCE_ID = "us-or-douglas-county-assessor-parcels"
OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCE_IDS = frozenset(
    {JACKSON_ASSESSOR_SOURCE_ID, DOUGLAS_ASSESSOR_SOURCE_ID}
)
JACKSON_PROPERTY_EVENT_SOURCE_IDS = frozenset(
    {
        "us-or-jackson-county-building-permits",
        "us-or-jackson-county-land-use-permits",
        "us-or-jackson-county-code-compliance",
    }
)
JACKSON_ACCELA_DETAIL_SOURCE_IDS = frozenset(
    {
        "us-or-jackson-county-accela-building-details",
        "us-or-jackson-county-accela-planning-details",
    }
)
OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SCOPES = {
    "us-or-linn-county-assessor-taxlots": "41043",
    "us-or-josephine-county-assessor-taxlots": "41033",
    "us-or-klamath-county-assessor-taxlots": "41035",
}
OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SOURCE_IDS = frozenset(
    OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SCOPES
)
LANE_PARCELS_SOURCE_ID = "us-or-lane-county-assessor-parcels"
LANE_SALES_SOURCE_ID = "us-or-lane-county-recent-property-sales"
LANE_PROPERTY_ACCOUNT_SOURCE_ID = (
    "us-or-lane-property-account-information"
)
LANE_TAX_MAP_SOURCE_ID = "us-or-lane-tax-maps"
OREGON_LANE_PROPERTY_SOURCE_IDS = frozenset(
    {LANE_PROPERTY_ACCOUNT_SOURCE_ID, LANE_TAX_MAP_SOURCE_ID}
)
MARION_PARCELS_SOURCE_ID = "us-or-marion-county-assessor-parcels"
MARION_SALES_DOWNLOAD_SOURCE_ID = "us-or-marion-sales-data"
MARION_ASSESSMENT_DOWNLOAD_SOURCE_ID = (
    "us-or-marion-comprehensive-assessment-download"
)
OREGON_LANE_MARION_SOURCE_IDS = frozenset(
    {
        LANE_PARCELS_SOURCE_ID,
        LANE_SALES_SOURCE_ID,
        MARION_PARCELS_SOURCE_ID,
        MARION_SALES_DOWNLOAD_SOURCE_ID,
        MARION_ASSESSMENT_DOWNLOAD_SOURCE_ID,
    }
)
LANE_MARION_SALE_PLACEHOLDER_SOURCES = {
    LANE_PARCELS_SOURCE_ID: (
        LANE_SALES_SOURCE_ID,
        LANE_PROPERTY_ACCOUNT_SOURCE_ID,
        LANE_TAX_MAP_SOURCE_ID,
    ),
    MARION_PARCELS_SOURCE_ID: (MARION_SALES_DOWNLOAD_SOURCE_ID,),
    MARION_ASSESSMENT_DOWNLOAD_SOURCE_ID: (
        MARION_SALES_DOWNLOAD_SOURCE_ID,
    ),
}
DENVER_DELINQUENT_TAX_SOURCE_ID = "us-co-denver-delinquent-real-property-tax-list"
DENVER_PROPERTY_SOURCE_ID = "us-co-denver-parcels"
MIAMI_DADE_PROPERTY_SOURCE_ID = "us-fl-miami-dade-property-appraiser"
ORLEANS_PROPERTY_SOURCE_ID = "us-la-orleans-property-viewer"
OREGON_TAXLOT_SOURCE_IDS = frozenset(
    {
        "us-or-portland-regional-taxlots",
        "us-or-metro-rlis-public-taxlots",
        "us-or-owrd-public-tax-lots",
    }
)
OREGON_HELION_PROPERTY_SCOPES = {
    "us-or-umatilla-helion-property": (
        "41059",
        "Umatilla County, Oregon",
        "OR",
    ),
    "us-or-morrow-helion-property": (
        "41049",
        "Morrow County, Oregon",
        "OR",
    ),
    "us-or-polk-helion-property": (
        "41053",
        "Polk County, Oregon",
        "OR",
    ),
    "us-or-tillamook-helion-property": (
        "41057",
        "Tillamook County, Oregon",
        "OR",
    ),
    "us-or-columbia-helion-property": (
        "41009",
        "Columbia County, Oregon",
        "OR",
    ),
    "us-or-coos-helion-property": (
        "41011",
        "Coos County, Oregon",
        "OR",
    ),
    "us-or-benton-helion-property": (
        "41003",
        "Benton County, Oregon",
        "OR",
    ),
}
OREGON_HELION_PROPERTY_SOURCE_IDS = frozenset(OREGON_HELION_PROPERTY_SCOPES)
OREGON_TAX_FORECLOSURE_SCOPES = {
    "us-or-clackamas-tax-foreclosure-publications": (
        "41005",
        "Clackamas County, Oregon",
        "OR",
    ),
    "us-or-marion-tax-foreclosure-publications": (
        "41047",
        "Marion County, Oregon",
        "OR",
    ),
    "us-or-multnomah-tax-foreclosure-publications": (
        "41051",
        "Multnomah County, Oregon",
        "OR",
    ),
    "us-or-tillamook-tax-foreclosure-publications": (
        "41057",
        "Tillamook County, Oregon",
        "OR",
    ),
}
OREGON_TAX_FORECLOSURE_SOURCE_IDS = frozenset(OREGON_TAX_FORECLOSURE_SCOPES)
MIAMI_DADE_PUBLIC_RECORDER_SOURCE_ID = "us-fl-miami-dade-official-records-public"
MIAMI_DADE_CANONICAL_RECORDER_SOURCE_ID = "us-fl-miami-dade-official-records"
COOK_PROPERTY_SOURCE_ID = "us-il-cook-parcel-universe"
MD_PROPERTY_SOURCE_ID = "us-md-sdat-property-hidden"
MD_MDP_PARCEL_POINTS_SOURCE_ID = query_md_mdp_parcel_points.SOURCE_ID
MD_PLATS_SOURCE_ID = query_md_plats.SOURCE_ID
ACRIS_SOURCE_ID = "us-nyc-acris"
NYC_PIP_SOURCE_ID = query_nyc_pip.SOURCE_ID
REEVES_RECORDER_SOURCE_ID = "us-tx-reeves-county-clerk-official-records"
GOVOS_RECORDER_SCOPES = {
    tenant.source_id: (
        tenant.county_geoid,
        tenant.jurisdiction_name,
        tenant.state_code,
    )
    for tenant in query_govos_recorders.TENANTS
}
GOVOS_RECORDER_SOURCE_IDS = frozenset(GOVOS_RECORDER_SCOPES)
OREGON_HELION_RECORDER_SCOPES = {
    source_id: (
        tenant.county_fips,
        f"{tenant.county_name}, Oregon",
        "OR",
    )
    for source_id, tenant in (
        query_oregon_helion_recorder.TENANTS_BY_SOURCE.items()
    )
}
OREGON_HELION_RECORDER_SOURCE_IDS = frozenset(OREGON_HELION_RECORDER_SCOPES)
HARRIS_RECORDER_SOURCE_ID = "us-tx-harris-clerk-real-property"
SANTA_FE_CLERKTRACK_SOURCE_ID = query_santa_fe_clerktrack.SOURCE_ID
SANTA_FE_PROPERTY_SOURCE_ID = query_santa_fe_property.SOURCE_ID
USVI_PROPERTY_TAX_SOURCE_ID = query_usvi_property_tax.SOURCE_ID
USVI_RECORDER_SOURCE_ID = query_usvi_recorder.SOURCE_ID
HCAD_GIS_SOURCE_ID = "us-tx-harris-hcad-gis"
TXGIO_LAND_PARCELS_SOURCE_ID = "us-tx-txgio-land-parcels"
MONTANA_CADASTRAL_SOURCE_ID = query_montana_cadastral.SOURCE_ID
LOS_ANGELES_ASSESSOR_SOURCE_ID = "us-ca-los-angeles-county-assessor-parcels"
LOS_ANGELES_TTC_PAYMENT_SOURCE_ID = "us-ca-los-angeles-county-ttc-payment-history"
LOS_ANGELES_TTC_SALE_SOURCE_ID = "us-ca-los-angeles-county-ttc-tax-sale"
LOS_ANGELES_PROPERTY_SOURCE_IDS = frozenset(
    {
        LOS_ANGELES_ASSESSOR_SOURCE_ID,
        LOS_ANGELES_TTC_PAYMENT_SOURCE_ID,
        LOS_ANGELES_TTC_SALE_SOURCE_ID,
    }
)
PHILADELPHIA_OPA_SOURCE_ID = "us-pa-philadelphia-opa-properties"
PHILADELPHIA_HISTORY_SOURCE_ID = "us-pa-philadelphia-opa-assessment-history"
PHILADELPHIA_DOR_SOURCE_ID = "us-pa-philadelphia-dor-parcels"
PHILADELPHIA_PROPERTY_SOURCE_IDS = frozenset(
    {
        PHILADELPHIA_OPA_SOURCE_ID,
        PHILADELPHIA_HISTORY_SOURCE_ID,
        PHILADELPHIA_DOR_SOURCE_ID,
    }
)
WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID = "us-wi-statewide-parcels"
WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID = "us-wy-dor-statewide-parcels"
OHIO_STATEWIDE_PARCELS_SOURCE_ID = "us-oh-ogrip-statewide-parcels"
OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID = (
    query_ohio_franklin_auditor_bulk.SOURCE_ID
)
OHIO_FRANKLIN_SALES_GIS_SOURCE_ID = (
    "us-oh-franklin-county-auditor-sales-gis"
)
OHIO_LICKING_AUDITOR_GIS_SOURCE_ID = query_ohio_licking_property.SOURCE_ID
OHIO_DELAWARE_PAX_SOURCE_ID = query_ohio_pax_recorders.DELAWARE_SOURCE_ID
OHIO_LICKING_PAX_SOURCE_ID = query_ohio_pax_recorders.LICKING_SOURCE_ID
OHIO_LICKING_DETAIL_SOURCE_ID = (
    query_ohio_pax_recorders.LICKING_DETAIL_SOURCE_ID
)
OHIO_PAX_QUERY_SOURCE_IDS = frozenset(
    {
        OHIO_DELAWARE_PAX_SOURCE_ID,
        OHIO_LICKING_PAX_SOURCE_ID,
        OHIO_LICKING_DETAIL_SOURCE_ID,
    }
)
OHIO_PAX_RECORDER_SCOPES = {
    OHIO_DELAWARE_PAX_SOURCE_ID: (
        "39041",
        "Delaware County",
        "OH",
        OHIO_DELAWARE_PAX_SOURCE_ID,
    ),
    OHIO_LICKING_PAX_SOURCE_ID: (
        "39089",
        "Licking County",
        "OH",
        OHIO_LICKING_PAX_SOURCE_ID,
    ),
    OHIO_LICKING_DETAIL_SOURCE_ID: (
        "39089",
        "Licking County",
        "OH",
        OHIO_LICKING_PAX_SOURCE_ID,
    ),
}
OHIO_SHERIFF_REALAUCTION_SCOPES = {
    tenant.source_id: (
        tenant.county_geoid,
        tenant.county_name.split(",", 1)[0],
        "OH",
    )
    for tenant in query_ohio_sheriff_sales.TENANTS.values()
}
OHIO_SHERIFF_REALAUCTION_SOURCE_IDS = frozenset(
    OHIO_SHERIFF_REALAUCTION_SCOPES
)
OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID = (
    query_licking_foreclosure_archive.SOURCE_ID
)
OHIO_FORECLOSURE_EVENT_SOURCE_IDS = frozenset(
    {
        *OHIO_SHERIFF_REALAUCTION_SOURCE_IDS,
        OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID,
    }
)
MICHIGAN_PROPERTY_DIRECTORY_SOURCE_ID = "us-mi-dtmb-tax-parcel-directory"
MICHIGAN_EATON_PARCELS_SOURCE_ID = "us-mi-eaton-county-parcel-snapshot"
GEORGIA_PROPERTY_DIRECTORY_SOURCE_ID = "us-ga-dor-county-property-records-directory"
GEORGIA_GSCCCA_SOURCE_ID = "us-ga-gsccca-real-estate-index"
GEORGIA_PROPERTY_SOURCE_IDS = frozenset(
    {
        GEORGIA_PROPERTY_DIRECTORY_SOURCE_ID,
        GEORGIA_GSCCCA_SOURCE_ID,
    }
)
NEW_JERSEY_DCA_PROPERTY_SOURCE_ID = "us-nj-dca-property-registration"
NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID = "us-nj-njgin-parcels-modiv"
NEW_JERSEY_SR1A_SOURCE_ID = "us-nj-treasury-sr1a-sales"
NEW_YORK_SALESWEB_SOURCE_ID = "us-ny-orpts-sales-web"
NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID = "us-ny-statewide-parcels"
# Exact alternate-representation parcel anchors remain in their publishing
# lineage until the matching canonical parcel representation adopts the row.
STATEWIDE_PARCEL_SHELL_SOURCE_IDS = {
    MD_PROPERTY_SOURCE_ID: (
        MD_MDP_PARCEL_POINTS_SOURCE_ID,
    ),
    NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID: (
        NEW_JERSEY_SR1A_SOURCE_ID,
    ),
    NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID: (
        NEW_YORK_SALESWEB_SOURCE_ID,
    ),
}
VIRGINIA_BEACH_DELINQUENT_TAX_SOURCE_ID = (
    "us-va-virginia-beach-delinquent-real-estate-taxes"
)
VIRGINIA_VGIN_PARCELS_SOURCE_ID = "us-va-vgin-parcels"
PALM_BEACH_RECORDER_SOURCE_ID = "us-fl-palm-beach-official-records"
PALM_BEACH_PROPERTY_SOURCE_ID = "us-fl-palm-beach-property-appraiser"
ORANGE_TAX_SOURCE_ID = query_orange_tax_collector.SOURCE_ID
PALM_BEACH_TAX_SOURCE_ID = query_palm_beach_tax_collector.SOURCE_ID
PALM_BEACH_TAX_DEEDS_SOURCE_ID = query_palm_beach_tax_deeds.SOURCE_ID
PALM_BEACH_PARCEL_SHELL_SOURCE_IDS = (
    PALM_BEACH_TAX_SOURCE_ID,
    PALM_BEACH_TAX_DEEDS_SOURCE_ID,
    PALM_BEACH_RECORDER_SOURCE_ID,
)
PALM_BEACH_PARCEL_RESOLUTION_SOURCE_IDS = (
    PALM_BEACH_PROPERTY_SOURCE_ID,
    *PALM_BEACH_PARCEL_SHELL_SOURCE_IDS,
)
BROWARD_RECORDER_SOURCE_ID = "us-fl-broward-official-records"
STATEWIDE_PARCEL_SOURCE_IDS = frozenset(
    {
        WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID,
        NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID,
        NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID,
        VIRGINIA_VGIN_PARCELS_SOURCE_ID,
        OHIO_STATEWIDE_PARCELS_SOURCE_ID,
        WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID,
    }
)
STATEWIDE_PARCEL_STATE_FIPS = {
    WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID: "55",
    NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID: "34",
    NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID: "36",
    VIRGINIA_VGIN_PARCELS_SOURCE_ID: "51",
    OHIO_STATEWIDE_PARCELS_SOURCE_ID: "39",
    WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID: "56",
    MONTANA_CADASTRAL_SOURCE_ID: "30",
}
INGESTABLE_STATUSES = frozenset({"ok", "no_results", "partial"})
OBSERVABLE_STATUSES = frozenset(
    {
        *INGESTABLE_STATUSES,
        "unavailable",
        "restricted",
        "human_required",
        "rate_limited",
        "terms_blocked",
        "source_changed",
    }
)
PROJECTED_SOURCE_IDS = frozenset(
    {
        NC_ONEMAP_SOURCE_ID,
        ARLINGTON_PROPERTY_SOURCE_ID,
        BEXAR_PROPERTY_SOURCE_ID,
        DELAWARE_FIRSTMAP_SOURCE_ID,
        DESCHUTES_PROPERTY_SOURCE_ID,
        DESCHUTES_CDD_WEBLINK_SOURCE_ID,
        BENTON_TAXLOT_OWNER_SOURCE_ID,
        BENTON_ASSESSMENT_BULK_SOURCE_ID,
        BENTON_ASSESSMENT_MAP_SOURCE_ID,
        LINCOLN_PROPERTYWEB_SOURCE_ID,
        LINCOLN_TAXLOT_WFS_SOURCE_ID,
        *OREGON_COUNTY_PROPERTY_SOURCE_IDS,
        *WASHINGTON_PARCEL_SOURCE_IDS,
        WASHINGTON_LAND_RECORDS_SOURCE_ID,
        MASON_COUNTY_TAX_PARCELS_SOURCE_ID,
        *WASHINGTON_TAXSIFTER_SOURCE_IDS,
        *DC_PROPERTY_SOURCE_IDS,
        *OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCE_IDS,
        *JACKSON_PROPERTY_EVENT_SOURCE_IDS,
        *JACKSON_ACCELA_DETAIL_SOURCE_IDS,
        *OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SOURCE_IDS,
        *OREGON_LANE_MARION_SOURCE_IDS,
        *OREGON_LANE_PROPERTY_SOURCE_IDS,
        DENVER_DELINQUENT_TAX_SOURCE_ID,
        DENVER_PROPERTY_SOURCE_ID,
        MIAMI_DADE_PROPERTY_SOURCE_ID,
        ORLEANS_PROPERTY_SOURCE_ID,
        *OREGON_TAXLOT_SOURCE_IDS,
        *OREGON_HELION_PROPERTY_SOURCE_IDS,
        *OREGON_TAX_FORECLOSURE_SOURCE_IDS,
        MIAMI_DADE_PUBLIC_RECORDER_SOURCE_ID,
        MIAMI_DADE_CANONICAL_RECORDER_SOURCE_ID,
        COOK_PROPERTY_SOURCE_ID,
        MD_PROPERTY_SOURCE_ID,
        MD_MDP_PARCEL_POINTS_SOURCE_ID,
        MD_PLATS_SOURCE_ID,
        ACRIS_SOURCE_ID,
        NYC_PIP_SOURCE_ID,
        REEVES_RECORDER_SOURCE_ID,
        *GOVOS_RECORDER_SOURCE_IDS,
        *OREGON_HELION_RECORDER_SOURCE_IDS,
        HARRIS_RECORDER_SOURCE_ID,
        HCAD_GIS_SOURCE_ID,
        TXGIO_LAND_PARCELS_SOURCE_ID,
        MONTANA_CADASTRAL_SOURCE_ID,
        *LOS_ANGELES_PROPERTY_SOURCE_IDS,
        *PHILADELPHIA_PROPERTY_SOURCE_IDS,
        *STATEWIDE_PARCEL_SOURCE_IDS,
        OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
        OHIO_FRANKLIN_SALES_GIS_SOURCE_ID,
        OHIO_LICKING_AUDITOR_GIS_SOURCE_ID,
        *OHIO_PAX_QUERY_SOURCE_IDS,
        *OHIO_FORECLOSURE_EVENT_SOURCE_IDS,
        MICHIGAN_PROPERTY_DIRECTORY_SOURCE_ID,
        MICHIGAN_EATON_PARCELS_SOURCE_ID,
        *GEORGIA_PROPERTY_SOURCE_IDS,
        NEW_JERSEY_DCA_PROPERTY_SOURCE_ID,
        NEW_JERSEY_SR1A_SOURCE_ID,
        NEW_YORK_SALESWEB_SOURCE_ID,
        VIRGINIA_BEACH_DELINQUENT_TAX_SOURCE_ID,
        PALM_BEACH_RECORDER_SOURCE_ID,
        PALM_BEACH_PROPERTY_SOURCE_ID,
        ORANGE_TAX_SOURCE_ID,
        PALM_BEACH_TAX_SOURCE_ID,
        PALM_BEACH_TAX_DEEDS_SOURCE_ID,
        BROWARD_RECORDER_SOURCE_ID,
        SANTA_FE_CLERKTRACK_SOURCE_ID,
        SANTA_FE_PROPERTY_SOURCE_ID,
        USVI_PROPERTY_TAX_SOURCE_ID,
        USVI_RECORDER_SOURCE_ID,
    }
)

STATE_METADATA = {
    "06": ("California", "CA"),
    "08": ("Colorado", "CO"),
    "10": ("Delaware", "DE"),
    "11": ("District of Columbia", "DC"),
    "12": ("Florida", "FL"),
    "13": ("Georgia", "GA"),
    "17": ("Illinois", "IL"),
    "22": ("Louisiana", "LA"),
    "24": ("Maryland", "MD"),
    "26": ("Michigan", "MI"),
    "30": ("Montana", "MT"),
    "35": ("New Mexico", "NM"),
    "39": ("Ohio", "OH"),
    "36": ("New York", "NY"),
    "37": ("North Carolina", "NC"),
    "41": ("Oregon", "OR"),
    "42": ("Pennsylvania", "PA"),
    "48": ("Texas", "TX"),
    "51": ("Virginia", "VA"),
    "53": ("Washington", "WA"),
    "34": ("New Jersey", "NJ"),
    "55": ("Wisconsin", "WI"),
    "56": ("Wyoming", "WY"),
    "78": ("U.S. Virgin Islands", "VI"),
}

SOURCE_JURISDICTION_SCOPES = {
    NC_ONEMAP_SOURCE_ID: ("prefix", "37"),
    ARLINGTON_PROPERTY_SOURCE_ID: ("exact", "51013"),
    BEXAR_PROPERTY_SOURCE_ID: ("exact", "48029"),
    DELAWARE_FIRSTMAP_SOURCE_ID: ("prefix", "10"),
    DESCHUTES_PROPERTY_SOURCE_ID: ("exact", "41017"),
    DESCHUTES_CDD_WEBLINK_SOURCE_ID: ("exact", "41017"),
    BENTON_TAXLOT_OWNER_SOURCE_ID: ("exact", "41003"),
    LINCOLN_PROPERTYWEB_SOURCE_ID: ("exact", "41041"),
    LINCOLN_TAXLOT_WFS_SOURCE_ID: ("exact", "41041"),
    **{
        source_id: (
            "exact",
            oregon_county_property_projection.SOURCE_JURISDICTIONS[source_id][0],
        )
        for source_id in OREGON_COUNTY_ASSESSOR_SOURCE_IDS
    },
    **{
        source_id: ("prefix", "53")
        for source_id in WASHINGTON_PARCEL_REPRESENTATION_SOURCE_IDS
    },
    WASHINGTON_LAND_RECORDS_SOURCE_ID: ("prefix", "53"),
    MASON_COUNTY_TAX_PARCELS_SOURCE_ID: ("exact", "53045"),
    **{
        tenant.source_id: ("exact", tenant.county_geoid)
        for tenant in query_washington_taxsifter.TENANTS
    },
    **{source_id: ("exact", "11") for source_id in DC_PROPERTY_ASSESSOR_SOURCE_IDS},
    JACKSON_ASSESSOR_SOURCE_ID: ("exact", "41029"),
    DOUGLAS_ASSESSOR_SOURCE_ID: ("exact", "41019"),
    **{
        source_id: ("exact", "41029") for source_id in JACKSON_PROPERTY_EVENT_SOURCE_IDS
    },
    **{source_id: ("exact", "41029") for source_id in JACKSON_ACCELA_DETAIL_SOURCE_IDS},
    **{
        source_id: ("exact", geoid)
        for source_id, geoid in (OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SCOPES.items())
    },
    LANE_PARCELS_SOURCE_ID: ("exact", "41039"),
    LANE_SALES_SOURCE_ID: ("exact", "41039"),
    LANE_PROPERTY_ACCOUNT_SOURCE_ID: ("exact", "41039"),
    LANE_TAX_MAP_SOURCE_ID: ("exact", "41039"),
    MARION_PARCELS_SOURCE_ID: ("exact", "41047"),
    MARION_SALES_DOWNLOAD_SOURCE_ID: ("exact", "41047"),
    MARION_ASSESSMENT_DOWNLOAD_SOURCE_ID: ("exact", "41047"),
    DENVER_DELINQUENT_TAX_SOURCE_ID: ("exact", "08031"),
    DENVER_PROPERTY_SOURCE_ID: ("exact", "08031"),
    MIAMI_DADE_PROPERTY_SOURCE_ID: ("exact", "12086"),
    ORLEANS_PROPERTY_SOURCE_ID: ("exact", "22071"),
    **{source_id: ("prefix", "41") for source_id in OREGON_TAXLOT_SOURCE_IDS},
    **{
        source_id: ("exact", scope[0])
        for source_id, scope in OREGON_HELION_PROPERTY_SCOPES.items()
    },
    **{
        source_id: ("exact", scope[0])
        for source_id, scope in OREGON_TAX_FORECLOSURE_SCOPES.items()
    },
    **{source_id: ("exact", "06037") for source_id in LOS_ANGELES_PROPERTY_SOURCE_IDS},
    **{source_id: ("exact", "42101") for source_id in PHILADELPHIA_PROPERTY_SOURCE_IDS},
    WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID: ("prefix", "55"),
    NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID: ("prefix", "34"),
    NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID: ("prefix", "36"),
    VIRGINIA_BEACH_DELINQUENT_TAX_SOURCE_ID: ("exact", "51810"),
    VIRGINIA_VGIN_PARCELS_SOURCE_ID: ("prefix", "51"),
    OHIO_STATEWIDE_PARCELS_SOURCE_ID: ("prefix", "39"),
    OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID: ("exact", "39049"),
    WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID: ("prefix", "56"),
    **{
        source_id: ("exact", scope[0])
        for source_id, scope in OHIO_PAX_RECORDER_SCOPES.items()
    },
    **{
        source_id: ("exact", scope[0])
        for source_id, scope in OHIO_SHERIFF_REALAUCTION_SCOPES.items()
    },
    OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID: ("exact", "39089"),
    OHIO_LICKING_AUDITOR_GIS_SOURCE_ID: ("exact", "39089"),
    MICHIGAN_PROPERTY_DIRECTORY_SOURCE_ID: ("prefix", "26"),
    MICHIGAN_EATON_PARCELS_SOURCE_ID: ("exact", "26045"),
    GEORGIA_PROPERTY_DIRECTORY_SOURCE_ID: ("prefix", "13"),
    GEORGIA_GSCCCA_SOURCE_ID: ("exact", "13"),
    NEW_YORK_SALESWEB_SOURCE_ID: ("prefix", "36"),
    NEW_JERSEY_DCA_PROPERTY_SOURCE_ID: ("exact", "34"),
    NEW_JERSEY_SR1A_SOURCE_ID: ("prefix", "34"),
    MD_MDP_PARCEL_POINTS_SOURCE_ID: ("prefix", "24"),
    MD_PLATS_SOURCE_ID: ("prefix", "24"),
    PALM_BEACH_RECORDER_SOURCE_ID: ("exact", "12099"),
    PALM_BEACH_PROPERTY_SOURCE_ID: ("exact", "12099"),
    ORANGE_TAX_SOURCE_ID: ("exact", "12095"),
    PALM_BEACH_TAX_SOURCE_ID: ("exact", "12099"),
    PALM_BEACH_TAX_DEEDS_SOURCE_ID: ("exact", "12099"),
    BROWARD_RECORDER_SOURCE_ID: ("exact", "12011"),
    SANTA_FE_CLERKTRACK_SOURCE_ID: ("exact", "35049"),
    SANTA_FE_PROPERTY_SOURCE_ID: ("exact", "35049"),
    USVI_RECORDER_SOURCE_ID: ("exact", "78"),
    HCAD_GIS_SOURCE_ID: ("exact", "48201"),
    TXGIO_LAND_PARCELS_SOURCE_ID: ("prefix", "48"),
    MONTANA_CADASTRAL_SOURCE_ID: ("prefix", "30"),
}

COUNTY_RECORDER_SCOPES = {
    REEVES_RECORDER_SOURCE_ID: ("48389", "Reeves County", "TX"),
    **GOVOS_RECORDER_SCOPES,
    **OREGON_HELION_RECORDER_SCOPES,
    HARRIS_RECORDER_SOURCE_ID: (
        "48201",
        "Harris County, Texas",
        "TX",
    ),
    USVI_RECORDER_SOURCE_ID: (
        "78",
        "U.S. Virgin Islands",
        "VI",
    ),
}

DEFAULT_GEOMETRY_CRS_BY_SOURCE = {
    ARLINGTON_PROPERTY_SOURCE_ID: "EPSG:3857",
    BEXAR_PROPERTY_SOURCE_ID: "EPSG:4326",
    DENVER_PROPERTY_SOURCE_ID: "EPSG:2877",
    DESCHUTES_PROPERTY_SOURCE_ID: "EPSG:4326",
    PHILADELPHIA_OPA_SOURCE_ID: "EPSG:4326",
    PHILADELPHIA_DOR_SOURCE_ID: "EPSG:4326",
    NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID: "EPSG:4326",
    NYC_PIP_SOURCE_ID: "EPSG:4326",
    BENTON_TAXLOT_OWNER_SOURCE_ID: "EPSG:4326",
    LINCOLN_TAXLOT_WFS_SOURCE_ID: "urn:ogc:def:crs:OGC:1.3:CRS84",
    HCAD_GIS_SOURCE_ID: "EPSG:4326",
    MASON_COUNTY_TAX_PARCELS_SOURCE_ID: "EPSG:4326",
    PALM_BEACH_PROPERTY_SOURCE_ID: "EPSG:4326",
    MONTANA_CADASTRAL_SOURCE_ID: "EPSG:4326",
    MD_MDP_PARCEL_POINTS_SOURCE_ID: "EPSG:4326",
    SANTA_FE_PROPERTY_SOURCE_ID: "EPSG:4326",
    **{
        source_id: "EPSG:4326"
        for source_id in (
            oregon_county_property_projection.YAMHILL_TAXLOT_SOURCE_ID,
            oregon_county_property_projection.YAMHILL_RETIRED_TAXLOT_SOURCE_ID,
            oregon_county_property_projection.CLACKAMAS_CMAP_SOURCE_ID,
            oregon_county_property_projection.WASCO_TAXLOT_SOURCE_ID,
        )
    },
    JACKSON_ASSESSOR_SOURCE_ID: "EPSG:4326",
    DOUGLAS_ASSESSOR_SOURCE_ID: "EPSG:4326",
    **{
        source_id: "EPSG:4326"
        for source_id in OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SOURCE_IDS
    },
    LANE_PARCELS_SOURCE_ID: "EPSG:4326",
    LANE_SALES_SOURCE_ID: "EPSG:4326",
    MARION_PARCELS_SOURCE_ID: "EPSG:4326",
    MIAMI_DADE_PROPERTY_SOURCE_ID: "EPSG:4326",
    ORLEANS_PROPERTY_SOURCE_ID: "EPSG:4326",
    **{source_id: "EPSG:4326" for source_id in OREGON_TAXLOT_SOURCE_IDS},
    LOS_ANGELES_ASSESSOR_SOURCE_ID: "EPSG:4326",
    WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID: "EPSG:4326",
    NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID: "EPSG:4326",
    VIRGINIA_VGIN_PARCELS_SOURCE_ID: "EPSG:4326",
    OHIO_STATEWIDE_PARCELS_SOURCE_ID: "EPSG:4326",
    OHIO_LICKING_AUDITOR_GIS_SOURCE_ID: "EPSG:4326",
    WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID: "EPSG:4326",
}

ACRIS_BOROUGH_METADATA = {
    "1": ("36061", "New York County (Manhattan)"),
    "2": ("36005", "Bronx County"),
    "3": ("36047", "Kings County (Brooklyn)"),
    "4": ("36081", "Queens County"),
    "5": ("36085", "Richmond County"),
}

ACRIS_PARTY_ROLES = {
    "1": "grantor",
    "2": "grantee",
    "3": "other",
}


class PropertyIngestError(ValueError):
    """Raised when an input envelope cannot be normalized."""


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    return normalized or None


def _minor_units(value: Any) -> int | None:
    """Convert a source dollar value to integer cents without float rounding."""
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise PropertyIngestError(f"invalid monetary value: {value!r}") from error
    if not amount.is_finite():
        raise PropertyIngestError(f"non-finite monetary value: {value!r}")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _normalized_address(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.upper().split())


def _address_identity(
    *,
    raw_address: str | None,
    city: Any,
    state: Any,
    postal_code: Any,
    country: Any,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    return (
        _normalized_address(raw_address),
        _normalized_address(_text(city)),
        _normalized_address(_text(state)),
        _normalized_address(_text(postal_code)),
        _normalized_address(_text(country) or "US"),
    )


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PropertyIngestError(f"{field_name} must be an object")
    return dict(value)


def _source_id(envelope: Mapping[str, Any]) -> str:
    query = _mapping(envelope.get("query"), "query")
    source = _mapping(query.get("source"), "query.source")
    value = _text(source.get("source_id"))
    if not value:
        raise PropertyIngestError("query.source.source_id is required")
    return value


def _record_url(envelope: Mapping[str, Any]) -> str | None:
    query = envelope.get("query")
    if not isinstance(query, Mapping):
        return None
    source = query.get("source")
    if not isinstance(source, Mapping):
        return None
    return _text(source.get("base_url"))


def _roll_year(record: Mapping[str, Any]) -> str:
    value = _text(record.get("tax_year")) or _text(record.get("roll_year"))
    if value:
        return value[:4]
    raw = record.get("raw_attributes")
    if isinstance(raw, Mapping):
        value = _text(raw.get("prop_val_yr") or raw.get("reviseyear"))
        if value:
            return value[:4]
    revised = _text(record.get("source_revised_date"))
    if revised and len(revised) >= 4 and revised[:4].isdigit():
        return revised[:4]
    return ""


def _address_raw(address: Mapping[str, Any]) -> str | None:
    raw = _text(address.get("raw")) or _text(address.get("raw_address"))
    unit = _text(address.get("unit"))
    if raw and unit and unit.casefold() not in raw.casefold():
        return f"{raw} {unit}"
    return raw or unit


def _upsert_jurisdiction(db, record: Mapping[str, Any]) -> str:
    jurisdiction = _mapping(record.get("jurisdiction"), "record.jurisdiction")
    county_geoid = _text(jurisdiction.get("county_geoid"))
    # Shared JurisdictionMetadata serializes a county GEOID as county_fips.
    county_fips = _text(jurisdiction.get("county_fips"))
    if county_geoid and county_fips and county_geoid != county_fips:
        raise PropertyIngestError("record jurisdiction has conflicting county GEOIDs")
    geoid = county_geoid or county_fips or _text(jurisdiction.get("state_fips"))
    if not geoid:
        raise PropertyIngestError(
            "record jurisdiction requires a county or state GEOID"
        )
    if not geoid.isdigit() or len(geoid) not in {2, 5}:
        raise PropertyIngestError(f"invalid property jurisdiction GEOID: {geoid!r}")
    state_fips = geoid[:2]
    state_name, canonical_state_code = STATE_METADATA.get(
        state_fips,
        (
            _text(jurisdiction.get("state_code")) or state_fips,
            _text(jurisdiction.get("state_code")) or state_fips,
        ),
    )
    state_code = (_text(jurisdiction.get("state_code")) or canonical_state_code).upper()
    county_name = _text(jurisdiction.get("county_name") or jurisdiction.get("locality"))
    if county_name and not county_name.casefold().endswith(("county", "parish")):
        jurisdiction_suffix = "Parish" if state_fips == "22" else "County"
        county_name = f"{county_name} {jurisdiction_suffix}"
    name = county_name or state_name
    jurisdiction_type = "county" if len(geoid) == 5 else "state"
    parent = state_fips if len(geoid) == 5 else None
    if parent:
        db.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, state_code
            ) VALUES (?, ?, 'state', ?)
            ON CONFLICT(geoid) DO UPDATE SET
                name=excluded.name,
                jurisdiction_type=excluded.jurisdiction_type,
                state_code=excluded.state_code
            """,
            (parent, state_name, state_code),
        )
    db.execute(
        """
        INSERT INTO jurisdiction(
            geoid, name, jurisdiction_type, parent_geoid, state_code, county_code
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(geoid) DO UPDATE SET
            name=excluded.name,
            jurisdiction_type=excluded.jurisdiction_type,
            parent_geoid=excluded.parent_geoid,
            state_code=excluded.state_code,
            county_code=excluded.county_code
        """,
        (
            geoid,
            name,
            jurisdiction_type,
            parent,
            state_code,
            geoid[-3:] if parent else None,
        ),
    )
    return geoid


def _insert_observation(
    db,
    *,
    source_id: str,
    source_native_id: str | None,
    record_kind: str,
    query_fingerprint: str | None,
    source_url: str | None,
    retrieved_at: str,
    access_status: str,
    schema_fingerprint: str | None,
    raw: Mapping[str, Any],
    raw_artifact_path: str | None,
    warnings: list[str],
    raw_artifact_sha256: str | None = None,
) -> tuple[int, str]:
    raw_json = canonical_json(raw)
    raw_hash = sha256_fingerprint(raw)
    cursor = db.execute(
        """
        INSERT INTO source_observation(
            source_id, source_native_id, record_kind, query_fingerprint,
            source_url, retrieved_at, access_status, schema_fingerprint,
            raw_artifact_sha256, raw_artifact_path, raw_json, warning_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            source_native_id,
            record_kind,
            query_fingerprint,
            source_url,
            retrieved_at,
            access_status,
            schema_fingerprint,
            raw_artifact_sha256 or raw_hash,
            raw_artifact_path,
            raw_json,
            canonical_json(warnings),
        ),
    )
    return int(cursor.lastrowid), raw_hash


def _upsert_address(
    db,
    *,
    parcel_id: int,
    source_id: str,
    role: str,
    address: Mapping[str, Any],
    effective_from: str,
) -> bool:
    raw_address = _address_raw(address)
    if not raw_address:
        return False
    city = _text(address.get("city"))
    state = _text(address.get("state"))
    postal_code = _text(address.get("postal_code"))
    country = _text(address.get("country")) or "US"
    identity = _address_identity(
        raw_address=raw_address,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
    )
    open_rows = db.execute(
        """
        SELECT address_id, raw_address, city, state, postal_code, country
        FROM parcel_address
        WHERE parcel_id=? AND address_role=? AND source_id=?
          AND effective_to IS NULL
        ORDER BY address_id DESC
        """,
        (parcel_id, role, source_id),
    ).fetchall()
    for row in open_rows:
        row_identity = _address_identity(
            raw_address=row["raw_address"],
            city=row["city"],
            state=row["state"],
            postal_code=row["postal_code"],
            country=row["country"],
        )
        if row_identity != identity:
            continue
        db.execute(
            """
            UPDATE parcel_address SET
                raw_address=?,
                normalized_address=?,
                city=?,
                state=?,
                postal_code=?,
                country=?
            WHERE address_id=?
            """,
            (
                raw_address,
                identity[0],
                city,
                state,
                postal_code,
                country,
                int(row["address_id"]),
            ),
        )
        return False
    params = (
        parcel_id,
        role,
        raw_address,
        identity[0],
        city,
        state,
        postal_code,
        country,
        source_id,
        effective_from,
    )
    db.execute(
        """
        INSERT INTO parcel_address(
            parcel_id, address_role, raw_address, normalized_address,
            city, state, postal_code, country, source_id, effective_from
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        params,
    )
    return True


def _record_declares_complete_assessor_snapshot(
    record: Mapping[str, Any],
) -> bool:
    if (
        record.get("snapshot_complete") is True
        or record.get("enrichment_complete") is True
    ):
        return True
    record_view = (_text(record.get("record_view")) or "").casefold()
    if record_view in {"detail", "property_detail", "history", "full_detail"}:
        return True
    return any(
        field in record
        for field in (
            "assessment_history",
            "deed_history",
            "roll_history",
            "site_addresses",
        )
    )


def _newer_complete_assessor_observation_exists(
    db,
    *,
    existing_observation_id: int,
    retrieved_at: str,
    observation_id: int,
) -> bool:
    row = db.execute(
        """
        SELECT observation_id, retrieved_at, raw_json
        FROM source_observation
        WHERE observation_id=?
        """,
        (existing_observation_id,),
    ).fetchone()
    if row is None:
        return False
    existing_retrieved_at = _text(row["retrieved_at"])
    existing_is_newer = bool(
        existing_retrieved_at is not None
        and (
            existing_retrieved_at > retrieved_at
            or (
                existing_retrieved_at == retrieved_at
                and int(row["observation_id"]) > observation_id
            )
        )
    )
    if not existing_is_newer:
        return False
    try:
        candidate = json.loads(row["raw_json"])
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(candidate, Mapping) and (
        _record_declares_complete_assessor_snapshot(candidate)
    )


def _upsert_assessor_owner(
    db,
    *,
    parcel_id: int,
    source_id: str,
    raw_name: str,
    effective_from: str,
    confidence: str,
    observation_id: int,
    evidence_ref: str,
) -> int:
    normalized_name = " ".join(raw_name.upper().split())
    existing = db.execute(
        """
        SELECT ownership_assertion_id
        FROM ownership_assertion
        WHERE parcel_id=? AND source_id=?
          AND assertion_type='assessment_roll'
          AND normalized_owner_name=?
          AND effective_to IS NULL
        ORDER BY observation_id DESC, ownership_assertion_id DESC
        LIMIT 1
        """,
        (parcel_id, source_id, normalized_name),
    ).fetchone()
    if existing is not None:
        db.execute(
            """
            UPDATE ownership_assertion SET
                raw_owner_name=?,
                normalized_owner_name=?,
                confidence=?,
                observation_id=?,
                evidence_ref=?,
                source_quote=?
            WHERE ownership_assertion_id=?
            """,
            (
                raw_name,
                normalized_name,
                confidence,
                observation_id,
                evidence_ref,
                raw_name,
                int(existing["ownership_assertion_id"]),
            ),
        )
        return 1
    db.execute(
        """
        INSERT INTO ownership_assertion(
            parcel_id, source_id, assertion_type, raw_owner_name,
            normalized_owner_name, effective_from, effective_to,
            confidence, claim_type, observation_id, evidence_ref, source_quote
        ) VALUES (
            ?, ?, 'assessment_roll', ?, ?, ?, NULL,
            ?, 'direct_quote', ?, ?, ?
        )
        ON CONFLICT(
            parcel_id, source_id, assertion_type, raw_owner_name, effective_from
        ) DO UPDATE SET
            normalized_owner_name=excluded.normalized_owner_name,
            effective_to=NULL,
            confidence=excluded.confidence,
            observation_id=excluded.observation_id,
            evidence_ref=excluded.evidence_ref,
            source_quote=excluded.source_quote
        """,
        (
            parcel_id,
            source_id,
            raw_name,
            normalized_name,
            effective_from,
            confidence,
            observation_id,
            evidence_ref,
            raw_name,
        ),
    )
    return 1


def _reconcile_assessor_owners(
    db,
    *,
    parcel_id: int,
    source_id: str,
    current_owner_names: set[str],
    effective_to: str,
) -> int:
    rows = db.execute(
        """
        SELECT ownership_assertion_id, normalized_owner_name
        FROM ownership_assertion
        WHERE parcel_id=? AND source_id=?
          AND assertion_type='assessment_roll'
          AND effective_to IS NULL
        ORDER BY observation_id DESC, ownership_assertion_id DESC
        """,
        (parcel_id, source_id),
    ).fetchall()
    kept: set[str] = set()
    closed = 0
    for row in rows:
        identity = _text(row["normalized_owner_name"]) or ""
        if identity in current_owner_names and identity not in kept:
            kept.add(identity)
            continue
        cursor = db.execute(
            """
            UPDATE ownership_assertion
            SET effective_to=?
            WHERE ownership_assertion_id=? AND effective_to IS NULL
            """,
            (effective_to, int(row["ownership_assertion_id"])),
        )
        closed += max(cursor.rowcount, 0)
    return closed


def _reconcile_assessor_addresses(
    db,
    *,
    parcel_id: int,
    source_id: str,
    current_addresses: Mapping[
        str,
        set[tuple[str | None, str | None, str | None, str | None, str | None]],
    ],
    effective_to: str,
) -> int:
    rows = db.execute(
        """
        SELECT address_id, address_role, raw_address, city, state,
               postal_code, country
        FROM parcel_address
        WHERE parcel_id=? AND source_id=? AND effective_to IS NULL
          AND address_role IN ('situs', 'mailing')
        ORDER BY address_id DESC
        """,
        (parcel_id, source_id),
    ).fetchall()
    kept: set[
        tuple[
            str,
            tuple[str | None, str | None, str | None, str | None, str | None],
        ]
    ] = set()
    closed = 0
    for row in rows:
        role = str(row["address_role"])
        identity = _address_identity(
            raw_address=row["raw_address"],
            city=row["city"],
            state=row["state"],
            postal_code=row["postal_code"],
            country=row["country"],
        )
        role_identity = (role, identity)
        if identity in current_addresses.get(role, set()) and role_identity not in kept:
            kept.add(role_identity)
            continue
        cursor = db.execute(
            """
            UPDATE parcel_address
            SET effective_to=?
            WHERE address_id=? AND effective_to IS NULL
            """,
            (effective_to, int(row["address_id"])),
        )
        closed += max(cursor.rowcount, 0)
    return closed


def _record_source_url(
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
) -> str | None:
    direct_url = _text(record.get("source_url"))
    if direct_url:
        return direct_url
    links = record.get("source_links")
    if isinstance(links, Mapping):
        for key in ("real_property_search", "finder", "record", "document"):
            value = _text(links.get(key))
            if value:
                return value
    master = record.get("master")
    if isinstance(master, Mapping):
        value = _text(master.get("document_url"))
        if value:
            return value
    return _record_url(envelope)


def _observation_context(
    envelope: Mapping[str, Any],
) -> tuple[str | None, str, str, list[str]]:
    query = _mapping(envelope.get("query"), "query")
    retrieved_at = _text(envelope.get("retrieved_at"))
    if not retrieved_at:
        raise PropertyIngestError("retrieved_at is required")
    status = _text(envelope.get("status"))
    if status not in OBSERVABLE_STATUSES:
        raise PropertyIngestError(f"unsupported ingestion source status {status!r}")
    warnings = envelope.get("warnings", [])
    if not isinstance(warnings, list) or not all(
        isinstance(item, str) for item in warnings
    ):
        raise PropertyIngestError("warnings must be a list of strings")
    return _text(query.get("fingerprint")), retrieved_at, status, list(warnings)


def _record_schema_fingerprint(record: Mapping[str, Any]) -> str | None:
    return _text(
        record.get("source_response_schema_fingerprint")
        or record.get("response_schema_fingerprint")
        or record.get("schema_fingerprint")
        or record.get("adapter_schema_fingerprint")
    )


def _assert_record_source(
    record: Mapping[str, Any],
    source_id: str,
) -> None:
    record_source_id = _text(record.get("source_id"))
    if record_source_id and record_source_id != source_id:
        raise PropertyIngestError(
            f"record source_id {record_source_id} does not match envelope {source_id}"
        )


def _upsert_jurisdiction_values(
    db,
    *,
    geoid: str,
    name: str,
    state_code: str,
    jurisdiction_type: str,
    parent_geoid: str | None = None,
) -> str:
    if parent_geoid:
        state_name, canonical_state_code = STATE_METADATA.get(
            parent_geoid,
            (state_code, state_code),
        )
        db.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, state_code
            ) VALUES (?, ?, 'state', ?)
            ON CONFLICT(geoid) DO UPDATE SET
                name=excluded.name,
                jurisdiction_type=excluded.jurisdiction_type,
                state_code=excluded.state_code
            """,
            (parent_geoid, state_name, canonical_state_code),
        )
    db.execute(
        """
        INSERT INTO jurisdiction(
            geoid, name, jurisdiction_type, parent_geoid, state_code, county_code
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(geoid) DO UPDATE SET
            name=excluded.name,
            jurisdiction_type=excluded.jurisdiction_type,
            parent_geoid=excluded.parent_geoid,
            state_code=excluded.state_code,
            county_code=excluded.county_code
        """,
        (
            geoid,
            name,
            jurisdiction_type,
            parent_geoid,
            state_code,
            geoid[-3:] if parent_geoid and geoid.isdigit() else None,
        ),
    )
    return geoid


def _upsert_record_jurisdiction(
    db,
    record: Mapping[str, Any],
    *,
    fallback_geoid: str,
    fallback_name: str,
    fallback_state_code: str,
) -> str:
    jurisdiction = record.get("jurisdiction")
    if not isinstance(jurisdiction, Mapping):
        jurisdiction = {}
    geoid = _text(jurisdiction.get("county_geoid")) or fallback_geoid
    state_code = (_text(jurisdiction.get("state_code")) or fallback_state_code).upper()
    county_name = _text(jurisdiction.get("county_name"))
    if geoid.isdigit() and len(geoid) == 5:
        name = county_name or fallback_name
        parent_geoid = geoid[:2]
        jurisdiction_type = "county"
    else:
        name = county_name or fallback_name
        parent_geoid = None
        jurisdiction_type = "state" if geoid.isdigit() and len(geoid) == 2 else "region"
    return _upsert_jurisdiction_values(
        db,
        geoid=geoid,
        name=name,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        parent_geoid=parent_geoid,
    )


def _upsert_parcel_snapshot(
    db,
    *,
    source_id: str,
    jurisdiction_geoid: str,
    native_parcel_id: str,
    roll_year: str,
    effective_from: str | None,
    source_good_through: str | None,
    observation_id: int,
    record: Mapping[str, Any],
) -> int:
    db.execute(
        """
        INSERT INTO parcel_snapshot(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year,
            effective_from, source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_parcel_id, roll_year)
        DO UPDATE SET
            effective_from=excluded.effective_from,
            source_good_through=excluded.source_good_through,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            source_id,
            jurisdiction_geoid,
            native_parcel_id,
            roll_year,
            effective_from,
            source_good_through,
            observation_id,
            canonical_json(record),
        ),
    )
    row = db.execute(
        """
        SELECT parcel_id FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=?
        """,
        (source_id, jurisdiction_geoid, native_parcel_id, roll_year),
    ).fetchone()
    return int(row["parcel_id"])


def _upsert_alias(
    db,
    *,
    parcel_id: int,
    alias_type: str,
    alias_value: Any,
    source_id: str,
    effective_from: str,
) -> int:
    value = _text(alias_value)
    if not value:
        return 0
    cursor = db.execute(
        """
        INSERT OR IGNORE INTO parcel_alias(
            parcel_id, alias_type, alias_value, source_id, effective_from
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (parcel_id, alias_type, value, source_id, effective_from),
    )
    return max(cursor.rowcount, 0)


def _upsert_assessment_projection(
    db,
    *,
    parcel_id: int,
    source_id: str,
    tax_year: str,
    land_value: Any = None,
    improvement_value: Any = None,
    total_value: Any = None,
    market_value: Any = None,
    assessed_value: Any = None,
    exempt_value: Any = None,
    assessment_class: Any = None,
    source_good_through: str | None,
    observation_id: int,
    raw: Mapping[str, Any],
) -> int:
    db.execute(
        """
        INSERT INTO assessment(
            parcel_id, source_id, tax_year, land_value_minor,
            improvement_value_minor, total_value_minor, market_value_minor,
            assessed_value_minor, exempt_value_minor, currency, assessment_class,
            source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(parcel_id, source_id, tax_year) DO UPDATE SET
            land_value_minor=excluded.land_value_minor,
            improvement_value_minor=excluded.improvement_value_minor,
            total_value_minor=excluded.total_value_minor,
            market_value_minor=excluded.market_value_minor,
            assessed_value_minor=excluded.assessed_value_minor,
            exempt_value_minor=excluded.exempt_value_minor,
            assessment_class=excluded.assessment_class,
            source_good_through=excluded.source_good_through,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            parcel_id,
            source_id,
            tax_year,
            _minor_units(land_value),
            _minor_units(improvement_value),
            _minor_units(total_value),
            _minor_units(market_value),
            _minor_units(assessed_value),
            _minor_units(exempt_value),
            _text(assessment_class),
            source_good_through,
            observation_id,
            canonical_json(raw),
        ),
    )
    return 1


def _upsert_sale_projection(
    db,
    *,
    parcel_id: int,
    source_id: str,
    native_sale_id: str,
    sale_date: str | None,
    consideration: Any,
    derivation: str,
    observation_id: int,
    raw: Mapping[str, Any],
    instrument_id: int | None = None,
    execution_date: str | None = None,
    recording_date: str | None = None,
    qualification_code: str | None = None,
    match_sale_date: bool = True,
    source_version: str | None = None,
) -> int:
    sale_date_clause = "AND se.sale_date IS ?" if match_sale_date else ""
    params: tuple[Any, ...] = (
        (parcel_id, source_id, native_sale_id, sale_date, derivation)
        if match_sale_date
        else (parcel_id, source_id, native_sale_id, derivation)
    )
    existing = db.execute(
        f"""
        SELECT se.sale_event_id, se.observation_id, se.raw_json,
               so.retrieved_at AS observation_retrieved_at
        FROM sale_event se
        LEFT JOIN source_observation so
          ON so.observation_id=se.observation_id
        WHERE se.parcel_id=? AND se.source_id=? AND se.native_sale_id=?
          {sale_date_clause} AND se.derivation=?
        ORDER BY so.retrieved_at DESC, se.observation_id DESC,
                 se.sale_event_id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if existing:
        incoming_newer_by_source_version = False
        if source_version:
            try:
                existing_raw = json.loads(existing["raw_json"])
            except (TypeError, json.JSONDecodeError):
                existing_raw = None
            existing_source_version = (
                _franklin_auditor_bulk_release_boundary(existing_raw)
                if isinstance(existing_raw, Mapping)
                else None
            )
            if not existing_source_version and isinstance(existing_raw, Mapping):
                activity = existing_raw.get("activity")
                if isinstance(activity, Mapping):
                    existing_source_version = _franklin_sales_timestamp(
                        activity.get("last_update_iso")
                    )
            if existing_source_version and existing_source_version > source_version:
                return 0
            incoming_newer_by_source_version = bool(
                existing_source_version
                and existing_source_version < source_version
            )
        incoming = db.execute(
            """
            SELECT retrieved_at FROM source_observation WHERE observation_id=?
            """,
            (observation_id,),
        ).fetchone()
        existing_retrieved_at = _text(existing["observation_retrieved_at"])
        incoming_retrieved_at = (
            _text(incoming["retrieved_at"]) if incoming is not None else None
        )
        existing_observation_id = int(existing["observation_id"] or 0)
        if (
            not incoming_newer_by_source_version
            and existing_retrieved_at
            and incoming_retrieved_at
            and (
                existing_retrieved_at > incoming_retrieved_at
                or (
                    existing_retrieved_at == incoming_retrieved_at
                    and existing_observation_id > observation_id
                )
            )
        ):
            return 0
    values = (
        sale_date,
        execution_date,
        recording_date,
        _minor_units(consideration),
        qualification_code,
        instrument_id,
        observation_id,
        canonical_json(raw),
    )
    if existing:
        db.execute(
            """
            UPDATE sale_event SET
                sale_date=?,
                execution_date=?,
                recording_date=?,
                consideration_minor=?,
                currency='USD',
                qualification_code=?,
                instrument_id=?,
                observation_id=?,
                raw_json=?
            WHERE sale_event_id=?
            """,
            (*values, int(existing["sale_event_id"])),
        )
    else:
        db.execute(
            """
            INSERT INTO sale_event(
                parcel_id, source_id, native_sale_id, sale_date,
                execution_date, recording_date, consideration_minor, currency,
                qualification_code, derivation, instrument_id, observation_id,
                raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?, ?)
            """,
            (
                parcel_id,
                source_id,
                native_sale_id,
                sale_date,
                execution_date,
                recording_date,
                _minor_units(consideration),
                qualification_code,
                derivation,
                instrument_id,
                observation_id,
                canonical_json(raw),
            ),
        )
    return 1


def _upsert_point_geometry(
    db,
    *,
    parcel_id: int,
    source_id: str,
    longitude: Any,
    latitude: Any,
    snapshot_date: str,
    source_resolution: str = "source_centroid",
) -> int:
    if longitude in (None, "") or latitude in (None, ""):
        return 0
    point = {
        "type": "Point",
        "coordinates": [longitude, latitude],
    }
    db.execute(
        """
        INSERT INTO parcel_geometry(
            parcel_id, geometry_ref, geometry_format, crs,
            source_resolution, source_id, snapshot_date
        ) VALUES (?, ?, 'geojson_point', 'EPSG:4326', ?, ?, ?)
        ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
            geometry_ref=excluded.geometry_ref,
            geometry_format=excluded.geometry_format,
            crs=excluded.crs,
            source_resolution=excluded.source_resolution
        """,
        (
            parcel_id,
            f"source-observation-sha256:{sha256_fingerprint(point)}",
            source_resolution,
            source_id,
            snapshot_date,
        ),
    )
    return 1


def _ingest_assessor_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
    observation_kind: str = "parcel_snapshot",
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    canonical_kind = "account" if source_id == ORLEANS_PROPERTY_SOURCE_ID else "parcel"
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        raise PropertyIngestError("assessor record lacks native_parcel_id")
    geoid = _upsert_jurisdiction(db, record)
    scope = SOURCE_JURISDICTION_SCOPES.get(source_id)
    if scope:
        match_type, expected = scope
        valid = (
            geoid == expected if match_type == "exact" else geoid.startswith(expected)
        )
        if not valid:
            raise PropertyIngestError(
                f"{source_id} record has out-of-scope GEOID {geoid}"
            )

    query = _mapping(envelope.get("query"), "query")
    query_fingerprint = _text(query.get("fingerprint"))
    retrieved_at = _text(envelope.get("retrieved_at"))
    if not retrieved_at:
        raise PropertyIngestError("retrieved_at is required")
    status = _text(envelope.get("status")) or "ok"
    warnings = envelope.get("warnings", [])
    if not isinstance(warnings, list) or not all(
        isinstance(item, str) for item in warnings
    ):
        raise PropertyIngestError("warnings must be a list of strings")
    schema_fingerprint = _record_schema_fingerprint(record)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=(
            _text(record.get("source_occurrence_id")) or native_parcel_id
        ),
        record_kind=observation_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=schema_fingerprint,
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    snapshot_complete = _record_declares_complete_assessor_snapshot(record)
    roll_year = _roll_year(record)
    effective_from = (
        _text(record.get("source_revised_date") or record.get("source_last_updated"))
        or ""
    )
    snapshot_boundary = effective_from or retrieved_at
    raw_json = canonical_json(record)
    parcel_row = db.execute(
        """
        SELECT parcel_id, observation_id, raw_json FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=?
        """,
        (source_id, geoid, native_parcel_id, roll_year),
    ).fetchone()
    newer_complete_snapshot_exists = bool(
        snapshot_complete
        and parcel_row is not None
        and _newer_complete_assessor_observation_exists(
            db,
            existing_observation_id=int(parcel_row["observation_id"]),
            retrieved_at=retrieved_at,
            observation_id=observation_id,
        )
    )
    preserve_existing_snapshot = False
    if parcel_row is not None:
        try:
            existing_record = json.loads(parcel_row["raw_json"])
        except (TypeError, json.JSONDecodeError):
            existing_record = None
        existing_complete = isinstance(existing_record, Mapping) and (
            _record_declares_complete_assessor_snapshot(existing_record)
        )
        preserve_existing_snapshot = bool(
            (existing_complete and not snapshot_complete)
            or newer_complete_snapshot_exists
        )
    if parcel_row is None and not roll_year:
        parcel_row = db.execute(
            """
            SELECT parcel_id, observation_id, raw_json FROM parcel_snapshot
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_parcel_id=? AND roll_year<>''
            ORDER BY roll_year DESC, parcel_id DESC
            LIMIT 1
            """,
            (source_id, geoid, native_parcel_id),
        ).fetchone()
        preserve_existing_snapshot = parcel_row is not None
    placeholder = None
    adopted_placeholder_source_id = None
    sale_placeholder_sources = LANE_MARION_SALE_PLACEHOLDER_SOURCES.get(
        source_id,
        (),
    )
    if parcel_row is None and sale_placeholder_sources:
        source_placeholders = ", ".join(
            "?" for _ in sale_placeholder_sources
        )
        placeholder = db.execute(
            f"""
            SELECT p.parcel_id, p.source_id
            FROM parcel_snapshot p
            LEFT JOIN parcel_alias pa ON pa.parcel_id=p.parcel_id
            WHERE p.jurisdiction_geoid=?
              AND p.roll_year=''
              AND p.source_id IN ({source_placeholders})
              AND (
                p.native_parcel_id=?
                OR pa.alias_value=?
              )
            ORDER BY
                CASE WHEN p.native_parcel_id=? THEN 0 ELSE 1 END,
                p.parcel_id
            LIMIT 1
            """,
            (
                geoid,
                *sale_placeholder_sources,
                native_parcel_id,
                native_parcel_id,
                native_parcel_id,
            ),
        ).fetchone()
    statewide_shell_sources = STATEWIDE_PARCEL_SHELL_SOURCE_IDS.get(
        source_id,
        (),
    )
    shell_join_values = record.get("parcel_shell_join_ids", [])
    if not isinstance(shell_join_values, list):
        shell_join_values = []
    shell_join_ids = [native_parcel_id]
    for candidate in shell_join_values:
        candidate_text = _text(candidate)
        if candidate_text and candidate_text not in shell_join_ids:
            shell_join_ids.append(candidate_text)
    if parcel_row is None and placeholder is None and statewide_shell_sources:
        source_placeholders = ", ".join(
            "?" for _ in statewide_shell_sources
        )
        identifier_placeholders = ", ".join(
            "?" for _ in shell_join_ids
        )
        placeholder = db.execute(
            f"""
            SELECT p.parcel_id, p.source_id
            FROM parcel_snapshot p
            LEFT JOIN parcel_alias pa ON pa.parcel_id=p.parcel_id
            WHERE p.jurisdiction_geoid=?
              AND p.roll_year=''
              AND p.source_id IN ({source_placeholders})
              AND (
                p.native_parcel_id IN ({identifier_placeholders})
                OR pa.alias_value IN ({identifier_placeholders})
              )
            ORDER BY
                CASE WHEN p.native_parcel_id=? THEN 0 ELSE 1 END,
                p.parcel_id
            LIMIT 1
            """,
            (
                geoid,
                *statewide_shell_sources,
                *shell_join_ids,
                *shell_join_ids,
                native_parcel_id,
            ),
        ).fetchone()
    if parcel_row is None and placeholder is None:
        placeholder_source_ids = [
            source_id,
            MIAMI_DADE_PUBLIC_RECORDER_SOURCE_ID,
            MIAMI_DADE_CANONICAL_RECORDER_SOURCE_ID,
            LOS_ANGELES_TTC_PAYMENT_SOURCE_ID,
            LOS_ANGELES_TTC_SALE_SOURCE_ID,
            PHILADELPHIA_HISTORY_SOURCE_ID,
        ]
        if source_id == PALM_BEACH_PROPERTY_SOURCE_ID:
            placeholder_source_ids.extend(PALM_BEACH_PARCEL_SHELL_SOURCE_IDS)
        source_placeholders = ", ".join(
            "?" for _ in placeholder_source_ids
        )
        placeholder = db.execute(
            f"""
            SELECT parcel_id, source_id FROM parcel_snapshot
            WHERE jurisdiction_geoid=? AND native_parcel_id=? AND roll_year=''
              AND source_id IN ({source_placeholders})
            ORDER BY parcel_id
            LIMIT 1
            """,
            (geoid, native_parcel_id, *placeholder_source_ids),
        ).fetchone()
    if parcel_row is None and placeholder is not None:
        adopted_placeholder_source_id = _text(placeholder["source_id"])
        db.execute(
            """
            UPDATE parcel_snapshot SET
                source_id=?,
                native_parcel_id=?,
                roll_year=?,
                effective_from=?,
                source_good_through=?,
                observation_id=?,
                raw_json=?
            WHERE parcel_id=?
            """,
            (
                source_id,
                native_parcel_id,
                roll_year,
                effective_from or None,
                effective_from or None,
                observation_id,
                raw_json,
                int(placeholder["parcel_id"]),
            ),
        )
        parcel_row = placeholder
    if parcel_row is None:
        db.execute(
            """
            INSERT INTO parcel_snapshot(
                source_id, jurisdiction_geoid, native_parcel_id, roll_year,
                effective_from, source_good_through, observation_id, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                geoid,
                native_parcel_id,
                roll_year,
                effective_from or None,
                effective_from or None,
                observation_id,
                raw_json,
            ),
        )
        parcel_row = db.execute(
            """
            SELECT parcel_id FROM parcel_snapshot
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_parcel_id=? AND roll_year=?
            """,
            (source_id, geoid, native_parcel_id, roll_year),
        ).fetchone()
    elif not preserve_existing_snapshot:
        db.execute(
            """
            UPDATE parcel_snapshot SET
                effective_from=?,
                source_good_through=?,
                observation_id=?,
                raw_json=?
            WHERE parcel_id=?
            """,
            (
                effective_from or None,
                effective_from or None,
                observation_id,
                raw_json,
                int(parcel_row["parcel_id"]),
            ),
        )
    parcel_id = int(parcel_row["parcel_id"])
    project_mutable_assertions = not preserve_existing_snapshot
    mutable_effective_from = snapshot_boundary if snapshot_complete else effective_from

    aliases_inserted = 0
    for alias in record.get("alternate_parcel_ids", []):
        alias_text = _text(alias)
        if not alias_text or alias_text == native_parcel_id:
            continue
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO parcel_alias(
                parcel_id, alias_type, alias_value, source_id, effective_from
            ) VALUES (?, 'source_alternate', ?, ?, ?)
            """,
            (parcel_id, alias_text, source_id, effective_from),
        )
        aliases_inserted += max(cursor.rowcount, 0)

    addresses_inserted = 0
    current_addresses: dict[
        str,
        set[
            tuple[
                str | None,
                str | None,
                str | None,
                str | None,
                str | None,
            ]
        ],
    ] = {"situs": set(), "mailing": set()}
    for role, field in (("situs", "situs_address"), ("mailing", "mailing_address")):
        address = record.get(field)
        if isinstance(address, Mapping) and _address_raw(address):
            current_addresses[role].add(
                _address_identity(
                    raw_address=_address_raw(address),
                    city=address.get("city"),
                    state=address.get("state"),
                    postal_code=address.get("postal_code"),
                    country=address.get("country"),
                )
            )
        if (
            project_mutable_assertions
            and isinstance(address, Mapping)
            and _address_raw(address)
        ):
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role=role,
                    address=address,
                    effective_from=mutable_effective_from,
                )
            )

    assessment = record.get("assessment")
    assessment_history = record.get("assessment_history")
    if assessment_history is not None and not isinstance(assessment_history, list):
        raise PropertyIngestError("record.assessment_history must be a list")
    assessment_records = (
        assessment_history
        if isinstance(assessment_history, list) and assessment_history
        else ([assessment] if isinstance(assessment, Mapping) else [])
    )
    assessments_upserted = 0
    for index, assessment_value in enumerate(
        assessment_records if not newer_complete_snapshot_exists else []
    ):
        assessment_record = _mapping(
            assessment_value,
            f"record.assessment_history[{index}]",
        )
        if not any(
            assessment_record.get(field) not in (None, "")
            for field in (
                "land_value",
                "improvement_value",
                "parcel_value",
                "assessed_value",
            )
        ):
            continue
        assessment_year = (
            _text(assessment_record.get("tax_year") or assessment_record.get("year"))
            or roll_year
        )
        assessments_upserted += _upsert_assessment_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=assessment_year,
            land_value=assessment_record.get("land_value"),
            improvement_value=assessment_record.get("improvement_value"),
            total_value=assessment_record.get("parcel_value"),
            market_value=assessment_record.get("market_value"),
            assessed_value=assessment_record.get("assessed_value"),
            assessment_class=_text(assessment_record.get("assessment_class")),
            source_good_through=effective_from or None,
            observation_id=observation_id,
            raw=assessment_record,
        )

    owners_upserted = 0
    owners = record.get("owners", [])
    if not isinstance(owners, list):
        raise PropertyIngestError("record.owners must be a list")
    current_owner_names: set[str] = set()
    for owner in owners:
        owner = _mapping(owner, "record.owners[]")
        raw_name = _text(owner.get("raw_name"))
        if not raw_name:
            continue
        current_owner_names.add(" ".join(raw_name.upper().split()))
        if project_mutable_assertions:
            owner_effective_from = (
                _text(owner.get("effective_from")) or mutable_effective_from
            )
            owners_upserted += _upsert_assessor_owner(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                raw_name=raw_name,
                effective_from=owner_effective_from,
                confidence=_text(owner.get("confidence")) or "high",
                observation_id=observation_id,
                evidence_ref=canonical_property_ref(
                    source_id,
                    geoid,
                    canonical_kind,
                    native_parcel_id,
                ),
            )

    owners_closed = 0
    addresses_closed = 0
    if snapshot_complete and project_mutable_assertions:
        owners_closed = _reconcile_assessor_owners(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            current_owner_names=current_owner_names,
            effective_to=snapshot_boundary,
        )
        addresses_closed = _reconcile_assessor_addresses(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            current_addresses=current_addresses,
            effective_to=snapshot_boundary,
        )

    sale_history = record.get("sale_history")
    if sale_history is not None and not isinstance(sale_history, list):
        raise PropertyIngestError("record.sale_history must be a list")
    sales = (
        sale_history
        if isinstance(sale_history, list) and sale_history
        else (
            [record["last_sale"]]
            if isinstance(record.get("last_sale"), Mapping)
            else []
        )
    )
    sales_upserted = 0
    for index, sale_value in enumerate(
        sales if not newer_complete_snapshot_exists else []
    ):
        sale = _mapping(sale_value, f"record.sale_history[{index}]")
        sale_date = _text(sale.get("sale_date"))
        source_document_date = _text(sale.get("source_document_date"))
        native_sale_id = _text(sale.get("source_document_ref"))
        if sale_date or source_document_date or native_sale_id:
            native_sale_id = native_sale_id or (
                f"assessor:{record.get('object_id', native_parcel_id)}:"
                f"{sha256_fingerprint(sale)[:20]}"
            )
            sales_upserted += _upsert_sale_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                native_sale_id=native_sale_id,
                sale_date=sale_date,
                consideration=(
                    sale.get("consideration")
                    if sale.get("consideration") not in (None, "")
                    else sale.get("sale_price")
                ),
                derivation="assessment_roll",
                observation_id=observation_id,
                raw=sale,
                execution_date=_text(sale.get("execution_date")),
                recording_date=source_document_date,
                qualification_code=_text(
                    sale.get("qualification_code") or sale.get("qualified_flag")
                ),
            )

    geometry_upserted = 0
    geometry = record.get("geometry")
    if isinstance(geometry, Mapping) and not newer_complete_snapshot_exists:
        snapshot_date = effective_from
        db.execute(
            """
            INSERT INTO parcel_geometry(
                parcel_id, geometry_ref, geometry_format, crs,
                accuracy_disclaimer, source_id, snapshot_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
                geometry_ref=excluded.geometry_ref,
                geometry_format=excluded.geometry_format,
                crs=excluded.crs,
                accuracy_disclaimer=excluded.accuracy_disclaimer
            """,
            (
                parcel_id,
                f"source-observation:{observation_id}#/geometry",
                _text(record.get("geometry_format")) or "esri_json",
                _text(record.get("geometry_crs"))
                or DEFAULT_GEOMETRY_CRS_BY_SOURCE.get(
                    source_id,
                    "source_defined",
                ),
                _text(record.get("geometry_disclaimer")),
                source_id,
                snapshot_date,
            ),
        )
        geometry_upserted = 1

    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id, geoid, canonical_kind, native_parcel_id
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "addresses_closed": addresses_closed,
        "assessments_upserted": assessments_upserted,
        "owners_upserted": owners_upserted,
        "owners_closed": owners_closed,
        "sales_upserted": sales_upserted,
        "geometry_upserted": geometry_upserted,
        "parcel_shell_adopted": int(
            adopted_placeholder_source_id is not None
        ),
        "parcel_shell_source_id_adopted": adopted_placeholder_source_id,
    }


def _feature_occurrence_id(record: Mapping[str, Any]) -> str | None:
    direct = _text(record.get("feature_ref") or record.get("evidence_ref"))
    if direct:
        return direct
    occurrence = record.get("feature_occurrence")
    if not isinstance(occurrence, Mapping):
        return None
    for key in (
        "feature_ref",
        "object_id",
        "native_object_id",
        "dbf_record_index",
    ):
        value = _text(occurrence.get(key))
        if value:
            return value
    return None


def _parcel_identifier_aliases(
    record: Mapping[str, Any],
    native_parcel_id: str,
) -> list[str]:
    identifiers = record.get("parcel_identifiers")
    if not isinstance(identifiers, Mapping):
        return []
    return list(
        dict.fromkeys(
            value
            for raw_value in identifiers.values()
            if (value := _text(raw_value)) and value != native_parcel_id
        )
    )


def _preserve_unlinked_parcel_feature(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    preserved = dict(record)
    if not _text(preserved.get("native_id")):
        preserved["native_id"] = (
            _feature_occurrence_id(record)
            or _text(record.get("source_occurrence_id"))
        )
    if not _text(preserved.get("record_type")):
        preserved["record_type"] = (
            _text(record.get("record_kind"))
            or "parcel_feature_occurrence"
        )
    occurrence = record.get("feature_occurrence")
    if isinstance(occurrence, Mapping):
        for key in ("object_id", "native_object_id", "dbf_record_index"):
            if key in occurrence and occurrence.get(key) is not None:
                preserved["object_id"] = occurrence.get(key)
                break
    return _ingest_statewide_parcel_observation_only(
        db,
        envelope=envelope,
        record=preserved,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        reason="feature_occurrence_has_no_parcel_join_identifier",
    )


def _ingest_hcad_gis_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project a queryable HCAD feature without collapsing feature identity."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_kind")) != ("parcel_assessment_geometry_snapshot"):
        return {
            "projection_skipped": True,
            "reason": "hcad_gis_record_is_not_a_queryable_parcel_feature",
            "record_kind": _text(record.get("record_kind")),
        }
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        return _preserve_unlinked_parcel_feature(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
        )

    projected = dict(record)
    projected["source_occurrence_id"] = (
        _feature_occurrence_id(record) or native_parcel_id
    )
    identifiers = record.get("parcel_identifiers")
    identifiers = identifiers if isinstance(identifiers, Mapping) else {}
    projected["alternate_parcel_ids"] = list(
        dict.fromkeys(
            value
            for key in ("hcad_num", "cama_account", "lowest_parcel_id")
            if (value := _text(identifiers.get(key))) and value != native_parcel_id
        )
    )
    projected["snapshot_complete"] = True
    assessment = record.get("assessment")
    if isinstance(assessment, Mapping):
        normalized_assessment = dict(assessment)
        appraised_value = assessment.get("appraised_value")
        normalized_assessment["parcel_value"] = appraised_value
        normalized_assessment["assessed_value"] = appraised_value
        if normalized_assessment.get("improvement_value") is None:
            normalized_assessment["improvement_value"] = assessment.get(
                "building_value"
            )
        projected["assessment"] = normalized_assessment
        tax_year = _text(assessment.get("tax_year"))
        projected["tax_year"] = tax_year
        if tax_year:
            projected["source_last_updated"] = tax_year
    if isinstance(record.get("geometry"), Mapping):
        projected["geometry_format"] = "esri_json"
        projected["geometry_disclaimer"] = (
            "Source MapServer feature occurrence; HCAD_NUM is not unique "
            "within the layer."
        )
    return _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="parcel_assessment_geometry_snapshot",
    )


def _ingest_mason_county_tax_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project a Mason GIS feature without collapsing FID into parcel identity."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_kind")) != (
        "parcel_assessment_geometry_snapshot"
    ):
        return {
            "projection_skipped": True,
            "reason": "mason_gis_record_is_not_a_queryable_parcel_feature",
            "record_kind": _text(record.get("record_kind")),
        }

    occurrence = record.get("feature_occurrence")
    if not isinstance(occurrence, Mapping):
        raise PropertyIngestError(
            "Mason GIS record requires feature_occurrence"
        )
    if _text(occurrence.get("object_id_field")) != (
        query_mason_county_tax_parcels.OBJECT_ID_FIELD
    ):
        raise PropertyIngestError(
            "Mason GIS feature occurrence must identify the FID field"
        )
    raw_object_id = occurrence.get("object_id")
    if isinstance(raw_object_id, bool) or (
        isinstance(raw_object_id, float) and not raw_object_id.is_integer()
    ):
        raise PropertyIngestError(
            "Mason GIS feature occurrence FID must be a non-negative integer"
        )
    try:
        object_id = int(raw_object_id)
    except (TypeError, ValueError) as error:
        raise PropertyIngestError(
            "Mason GIS feature occurrence FID must be a non-negative integer"
        ) from error
    if object_id < 0:
        raise PropertyIngestError(
            "Mason GIS feature occurrence FID must be a non-negative integer"
        )
    expected_occurrence_id = f"FID:{object_id}"
    if _text(record.get("source_occurrence_id")) != expected_occurrence_id:
        raise PropertyIngestError(
            "Mason GIS source_occurrence_id does not match its FID"
        )
    feature_ref = _text(record.get("feature_ref"))
    expected_feature_ref = canonical_property_ref(
        source_id,
        query_mason_county_tax_parcels.COUNTY_GEOID,
        "parcel_feature",
        expected_occurrence_id,
    )
    if feature_ref != expected_feature_ref:
        raise PropertyIngestError(
            "Mason GIS feature_ref does not match its county-scoped FID"
        )

    native_parcel_id = _text(record.get("native_parcel_id"))
    join_key = record.get("parcel_join_key")
    if native_parcel_id:
        if not isinstance(join_key, Mapping):
            raise PropertyIngestError(
                "Mason GIS parcel projection requires parcel_join_key"
            )
        if (
            _text(join_key.get("county_geoid"))
            != query_mason_county_tax_parcels.COUNTY_GEOID
            or _text(join_key.get("value")) != native_parcel_id
            or _text(join_key.get("field"))
            not in {"pin", "terra_pin", "taxlot"}
            or _text(join_key.get("uniqueness_in_layer")) != "not_assumed"
        ):
            raise PropertyIngestError(
                "Mason GIS parcel join identity is inconsistent"
            )
    elif join_key not in (None, {}):
        raise PropertyIngestError(
            "Mason GIS feature without a parcel identifier cannot declare a join"
        )

    if not native_parcel_id:
        return _preserve_unlinked_parcel_feature(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
        )

    projected = dict(record)
    projected["source_occurrence_id"] = feature_ref
    identifiers = record.get("parcel_identifiers")
    identifiers = identifiers if isinstance(identifiers, Mapping) else {}
    projected["alternate_parcel_ids"] = list(
        dict.fromkeys(
            value
            for key in ("pin", "terra_pin", "taxlot")
            if (value := _text(identifiers.get(key)))
            and value != native_parcel_id
        )
    )
    projected["snapshot_complete"] = False
    assessment = record.get("assessment")
    if isinstance(assessment, Mapping):
        normalized_assessment = dict(assessment)
        if normalized_assessment.get("parcel_value") is None:
            normalized_assessment["parcel_value"] = assessment.get(
                "market_value"
            )
        projected["assessment"] = normalized_assessment
    if isinstance(record.get("geometry"), Mapping):
        projected["geometry_format"] = "esri_json"
        projected["geometry_crs"] = "EPSG:4326"
        projected["geometry_disclaimer"] = (
            "Mason County GIS feature occurrence transformed to EPSG:4326; "
            "not a surveyed legal boundary."
        )
    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="parcel_assessment_geometry_snapshot",
    )
    result["feature_occurrence_id"] = expected_occurrence_id
    result["parcel_join_uniqueness_assumed"] = False
    return result


def _ingest_palm_beach_property_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project a PBC GIS occurrence without collapsing repeated parcel numbers."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_kind")) != (
        "parcel_assessment_geometry_snapshot"
    ):
        return {
            "projection_skipped": True,
            "reason": "palm_beach_gis_record_is_not_a_queryable_parcel_feature",
            "record_kind": _text(record.get("record_kind")),
        }

    occurrence = record.get("feature_occurrence")
    if not isinstance(occurrence, Mapping):
        raise PropertyIngestError(
            "Palm Beach GIS record requires feature_occurrence"
        )
    if _text(occurrence.get("object_id_field")) != (
        query_palm_beach_property_appraiser.OBJECT_ID_FIELD
    ):
        raise PropertyIngestError(
            "Palm Beach GIS feature occurrence must identify OBJECTID"
        )
    raw_object_id = occurrence.get("object_id")
    if isinstance(raw_object_id, bool) or (
        isinstance(raw_object_id, float) and not raw_object_id.is_integer()
    ):
        raise PropertyIngestError(
            "Palm Beach GIS OBJECTID must be a non-negative integer"
        )
    try:
        object_id = int(raw_object_id)
    except (TypeError, ValueError) as error:
        raise PropertyIngestError(
            "Palm Beach GIS OBJECTID must be a non-negative integer"
        ) from error
    if object_id < 0:
        raise PropertyIngestError(
            "Palm Beach GIS OBJECTID must be a non-negative integer"
        )

    expected_occurrence_id = f"OBJECTID:{object_id}"
    if _text(record.get("source_occurrence_id")) != expected_occurrence_id:
        raise PropertyIngestError(
            "Palm Beach GIS source_occurrence_id does not match OBJECTID"
        )
    feature_ref = _text(record.get("feature_ref"))
    expected_feature_ref = canonical_property_ref(
        source_id,
        query_palm_beach_property_appraiser.COUNTY_GEOID,
        "parcel_feature",
        expected_occurrence_id,
    )
    if feature_ref != expected_feature_ref:
        raise PropertyIngestError(
            "Palm Beach GIS feature_ref does not match its county OBJECTID"
        )

    native_parcel_id = _text(record.get("native_parcel_id"))
    join_key = record.get("parcel_join_key")
    if native_parcel_id:
        if not isinstance(join_key, Mapping):
            raise PropertyIngestError(
                "Palm Beach GIS parcel projection requires parcel_join_key"
            )
        if (
            _text(join_key.get("county_geoid"))
            != query_palm_beach_property_appraiser.COUNTY_GEOID
            or _text(join_key.get("value")) != native_parcel_id
            or _text(join_key.get("field")) != "parcel_number"
            or _text(join_key.get("role"))
            != "candidate_exact_tax_account_join"
            or _text(join_key.get("uniqueness_in_layer")) != "not_assumed"
        ):
            raise PropertyIngestError(
                "Palm Beach GIS parcel join identity is inconsistent"
            )
    elif join_key not in (None, {}):
        raise PropertyIngestError(
            "Palm Beach feature without PARCEL_NUMBER cannot declare a join"
        )

    if not native_parcel_id:
        return _preserve_unlinked_parcel_feature(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
        )

    projected = dict(record)
    projected["source_occurrence_id"] = feature_ref
    projected["snapshot_complete"] = False
    projected["alternate_parcel_ids"] = []
    if isinstance(record.get("geometry"), Mapping):
        projected["geometry_format"] = "esri_json"
        projected["geometry_crs"] = "EPSG:4326"
        projected["geometry_disclaimer"] = (
            "Palm Beach County GIS feature occurrence transformed to "
            "EPSG:4326; not a surveyed legal boundary."
        )
    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="parcel_assessment_geometry_snapshot",
    )
    result["feature_occurrence_id"] = expected_occurrence_id
    result["parcel_join_uniqueness_assumed"] = False
    result["parid_projected_as_parcel_alias"] = False
    parcel_id = int(result["parcel_id"])
    reconciliation = _reconcile_palm_beach_parcel_shells(
        db,
        canonical_parcel_id=parcel_id,
        native_parcel_id=native_parcel_id,
    )
    initial_shell_source_id = _text(
        result.get("parcel_shell_source_id_adopted")
    )
    adopted_source_ids = list(
        reconciliation["parcel_shell_source_ids_repointed"]
    )
    parcel_shells_adopted = int(
        initial_shell_source_id in PALM_BEACH_PARCEL_SHELL_SOURCE_IDS
    )
    if parcel_shells_adopted:
        adopted_source_ids.append(initial_shell_source_id)
    parcel_shells_adopted += int(
        reconciliation["parcel_shells_repointed"]
    )
    adopted_source_ids = sorted(set(adopted_source_ids))
    result.update(reconciliation)
    result["parcel_shells_adopted"] = parcel_shells_adopted
    result["parcel_shell_source_ids_adopted"] = adopted_source_ids
    result["tax_deed_shell_links_adopted"] = sum(
        source_id == PALM_BEACH_TAX_DEEDS_SOURCE_ID
        for source_id in adopted_source_ids
    )
    return result


def _txgio_geometry_reference(
    db,
    *,
    record: Mapping[str, Any],
    projection: Mapping[str, Any],
    source_id: str,
) -> dict[str, Any]:
    available = record.get("geometry_available")
    if not isinstance(available, Mapping):
        return {"geometry_upserted": 0}
    artifact = record.get("artifact_snapshot")
    artifact = artifact if isinstance(artifact, Mapping) else {}
    shapefile = available.get("shapefile")
    shapefile = shapefile if isinstance(shapefile, Mapping) else {}
    artifact_sha256 = _text(artifact.get("sha256") or available.get("artifact_sha256"))
    shapefile_path = _text(
        shapefile.get("member_name")
        or shapefile.get("shp")
        or shapefile.get("path")
        or shapefile.get("stem")
    )
    row_index = available.get("dbf_record_index")
    if row_index is None:
        row_index = artifact.get("dbf_record_index")
    if not artifact_sha256 or not shapefile_path or row_index is None:
        return {"geometry_upserted": 0}

    geometry_ref = (
        f"artifact-sha256:{artifact_sha256}#{shapefile_path}:dbf-record={row_index}"
    )
    projection_wkt = _text(available.get("projection_wkt"))
    crs = (
        f"source-prj-wkt-sha256:{sha256_fingerprint(projection_wkt)}"
        if projection_wkt
        else None
    )
    assessment = record.get("assessment")
    tax_year = (
        _text(assessment.get("tax_year")) if isinstance(assessment, Mapping) else None
    )
    snapshot_date = _text(artifact.get("dbf_last_update")) or tax_year or ""
    db.execute(
        """
        INSERT INTO parcel_geometry(
            parcel_id, geometry_ref, geometry_format, crs,
            source_resolution, accuracy_disclaimer, source_id, snapshot_date
        ) VALUES (
            ?, ?, 'shapefile_record_reference', ?, 'source_polygon_reference',
            ?, ?, ?
        )
        ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
            geometry_ref=excluded.geometry_ref,
            geometry_format=excluded.geometry_format,
            crs=excluded.crs,
            source_resolution=excluded.source_resolution,
            accuracy_disclaimer=excluded.accuracy_disclaimer
        """,
        (
            int(projection["parcel_id"]),
            geometry_ref,
            crs,
            (
                "Coordinates are not decoded in the local archive scan; "
                "the reference identifies the aligned source polygon record."
            ),
            source_id,
            snapshot_date,
        ),
    )
    return {
        "geometry_upserted": 1,
        "geometry_reference": geometry_ref,
        "geometry_decoded": False,
    }


def _ingest_txgio_land_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one TxGIO DBF row and retain its aligned polygon reference."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_kind")) != ("parcel_assessment_geometry_snapshot"):
        return {
            "projection_skipped": True,
            "reason": "txgio_record_is_not_a_local_parcel_feature",
            "record_kind": _text(record.get("record_kind")),
        }
    artifact = record.get("artifact_snapshot")
    artifact = artifact if isinstance(artifact, Mapping) else {}
    available = record.get("geometry_available")
    available = available if isinstance(available, Mapping) else {}
    artifact_path = (
        raw_artifact_path
        or _text(artifact.get("path"))
        or _text(available.get("artifact_path"))
    )
    artifact_sha256 = (
        raw_artifact_sha256
        or _text(artifact.get("sha256"))
        or _text(available.get("artifact_sha256"))
    )
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        return _preserve_unlinked_parcel_feature(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=artifact_path,
            raw_artifact_sha256=artifact_sha256,
        )

    projected = dict(record)
    jurisdiction = record.get("jurisdiction")
    if isinstance(jurisdiction, Mapping):
        normalized_jurisdiction = dict(jurisdiction)
        normalized_jurisdiction["county_geoid"] = _text(
            jurisdiction.get("county_geoid")
        ) or _text(jurisdiction.get("county_fips"))
        projected["jurisdiction"] = normalized_jurisdiction
    projected["source_occurrence_id"] = (
        _feature_occurrence_id(record) or native_parcel_id
    )
    projected["alternate_parcel_ids"] = _parcel_identifier_aliases(
        record,
        native_parcel_id,
    )
    projected["snapshot_complete"] = True
    owners = record.get("owners")
    if isinstance(owners, list):
        projected["owners"] = [
            owner
            for owner in owners
            if isinstance(owner, Mapping)
            and _text(owner.get("role")) == "assessment_snapshot_owner_name"
        ]
    assessment = record.get("assessment")
    if isinstance(assessment, Mapping):
        normalized_assessment = dict(assessment)
        normalized_assessment["parcel_value"] = assessment.get("market_value")
        projected["assessment"] = normalized_assessment
        projected["tax_year"] = _text(assessment.get("tax_year"))
    source_updated = _text(artifact.get("dbf_last_update"))
    if source_updated:
        projected["source_last_updated"] = source_updated

    projection = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=artifact_path,
        raw_artifact_sha256=artifact_sha256,
        observation_kind="parcel_assessment_geometry_snapshot",
    )
    geometry = _txgio_geometry_reference(
        db,
        record=record,
        projection=projection,
        source_id=source_id,
    )
    return {**projection, **geometry}


def _montana_cadastral_observation_only(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
    reason: str,
) -> dict[str, Any]:
    """Preserve a Montana occurrence or bulk envelope without making a parcel."""

    preserved = dict(record)
    identity = record.get("identity")
    identity = identity if isinstance(identity, Mapping) else {}
    source_native_id = _text(
        record.get("source_record_id")
        or record.get("canonical_ref")
        or identity.get("global_id")
        or (
            f"OBJECTID-{identity.get('object_id')}"
            if identity.get("object_id") not in (None, "")
            else None
        )
        or record.get("record_type")
    )
    preserved["native_id"] = source_native_id or (
        f"record-sha256:{sha256_fingerprint(record)}"
    )
    jurisdiction = record.get("jurisdiction")
    if not isinstance(jurisdiction, Mapping):
        preserved["jurisdiction"] = {
            "state_code": "MT",
            "state_fips": "30",
        }
    return _ingest_statewide_parcel_observation_only(
        db,
        envelope=envelope,
        record=preserved,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        reason=reason,
    )


def _ingest_montana_cadastral_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project a live MSL feature while retaining source occurrence identity."""

    if _text(record.get("record_type")) != "parcel_feature_occurrence":
        return _montana_cadastral_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="montana_bulk_or_metadata_record_is_envelope_only",
        )
    _assert_record_source(record, source_id)
    identity = _mapping(record.get("identity"), "record.identity")
    native_parcel_id = _text(identity.get("parcel_id"))
    if not native_parcel_id:
        return _montana_cadastral_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="montana_feature_occurrence_has_no_parcelid_join",
        )

    jurisdiction = _mapping(record.get("jurisdiction"), "record.jurisdiction")
    county_geoid = _text(jurisdiction.get("county_geoid"))
    raw_prefix = jurisdiction.get("orion_county_prefix")
    try:
        orion_prefix = int(raw_prefix)
    except (TypeError, ValueError) as error:
        raise PropertyIngestError(
            "Montana parcel feature lacks a valid ORION county prefix"
        ) from error
    county = query_montana_cadastral.COUNTY_BY_PREFIX.get(orion_prefix)
    if county is None or county_geoid != county.geoid:
        raise PropertyIngestError(
            "Montana parcel feature county GEOID conflicts with the "
            "ORION-to-Census crosswalk"
        )

    source_occurrence_id = _text(
        record.get("source_record_id")
        or identity.get("global_id")
        or (
            f"OBJECTID-{identity.get('object_id')}"
            if identity.get("object_id") not in (None, "")
            else None
        )
    )
    if not source_occurrence_id:
        raise PropertyIngestError(
            "Montana parcel feature lacks GlobalID/OBJECTID occurrence identity"
        )

    site = record.get("site_address")
    site = site if isinstance(site, Mapping) else {}
    site_raw = ", ".join(
        value
        for value in (
            _text(site.get("line1")),
            _text(site.get("line2")),
            _text(site.get("city_state_zip")),
        )
        if value
    )
    owner = record.get("owner")
    owner = owner if isinstance(owner, Mapping) else {}
    address_lines = owner.get("address_lines")
    if not isinstance(address_lines, list):
        address_lines = []
    mailing_raw = ", ".join(
        value
        for value in (
            _text(owner.get("care_of")),
            *(_text(line) for line in address_lines),
            _text(owner.get("city")),
            " ".join(
                value
                for value in (
                    _text(owner.get("state")),
                    _text(owner.get("postal_code")),
                )
                if value
            )
            or None,
        )
        if value
    )
    owner_name = _text(owner.get("name"))

    source_assessment = record.get("assessment")
    source_assessment = (
        source_assessment if isinstance(source_assessment, Mapping) else {}
    )
    tax_year = _text(source_assessment.get("tax_year"))
    property_id = _text(identity.get("property_id"))
    assessment_code = _text(identity.get("assessment_code"))
    aliases = [
        value
        for value in (property_id, assessment_code)
        if value and value != native_parcel_id
    ]

    projected = {
        **dict(record),
        "native_parcel_id": native_parcel_id,
        "source_occurrence_id": source_occurrence_id,
        "alternate_parcel_ids": list(dict.fromkeys(aliases)),
        "tax_year": tax_year,
        "snapshot_complete": False,
        "snapshot_completeness": {
            "role": "selected_cama_and_parcel_geometry_observation",
            "feature_occurrence_identity": (
                "GlobalID" if _text(identity.get("global_id")) else "OBJECTID"
            ),
            "parcel_join_identity": "PARCELID",
            "owner_assertion": "assessment_roll_observation_not_title",
        },
        "situs_address": {
            "raw": site_raw or None,
            "country": "US",
        },
        "mailing_address": {
            "raw": mailing_raw or None,
            "city": _text(owner.get("city")),
            "state": _text(owner.get("state")),
            "postal_code": _text(owner.get("postal_code")),
            "country": "US",
        },
        "owners": (
            [
                {
                    "raw_name": owner_name,
                    "role": "assessment_roll_owner_observation",
                    "confidence": "high",
                }
            ]
            if owner_name
            else []
        ),
        "assessment": {
            **dict(source_assessment),
            "tax_year": tax_year,
            "land_value": source_assessment.get("land_value"),
            "improvement_value": source_assessment.get("building_value"),
            "parcel_value": source_assessment.get("total_value"),
            "market_value": source_assessment.get("total_value"),
            "assessment_class": _text(source_assessment.get("property_type")),
        },
    }
    geometry = record.get("geometry")
    if isinstance(geometry, Mapping):
        if _text(record.get("geometry_crs")) != "EPSG:4326":
            raise PropertyIngestError(
                "Montana live geometry must declare EPSG:4326"
            )
        projected["geometry_format"] = "esri_json"
        projected["geometry_disclaimer"] = (
            "State cadastral parcel geometry observation; recorded "
            "instruments and local survey records control legal interests."
        )

    projection = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="parcel_feature_occurrence",
    )
    _query_fingerprint, retrieved_at, _status, _warnings = _observation_context(
        envelope
    )
    typed_aliases = (
        ("montana_property_id", property_id),
        ("montana_assessment_code", assessment_code),
    )
    typed_aliases_inserted = 0
    for alias_type, alias_value in typed_aliases:
        if not alias_value or alias_value == native_parcel_id:
            continue
        typed_aliases_inserted += _upsert_alias(
            db,
            parcel_id=int(projection["parcel_id"]),
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=retrieved_at,
        )
    return {
        **projection,
        "source_occurrence_id": source_occurrence_id,
        "orion_county_prefix": orion_prefix,
        "county_geoid": county_geoid,
        "typed_aliases_inserted": typed_aliases_inserted,
    }


def _ingest_philadelphia_opa_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project a complete current OPA row onto the shared parcel model."""

    if _text(record.get("record_type")) != ("current_property_assessment_observation"):
        return {
            "projection_skipped": True,
            "reason": "opa_component_record_is_not_a_current_assessment",
            "record_type": _text(record.get("record_type")),
        }

    projected = dict(record)
    projected["snapshot_complete"] = True
    projected["alternate_parcel_ids"] = [
        value
        for value in (
            record.get("pin"),
            record.get("registry_number"),
        )
        if _text(value)
    ]

    mailing = record.get("mailing_address")
    if isinstance(mailing, Mapping):
        projected_mailing = dict(mailing)
        projected_mailing["raw"] = ", ".join(
            value
            for value in (
                _text(mailing.get("addressee_line")),
                _text(mailing.get("secondary_line")),
                _text(mailing.get("care_of")),
                _text(mailing.get("street")),
                _text(mailing.get("city_state_raw")),
                _text(mailing.get("postal_code")),
            )
            if value
        )
        projected_mailing["state"] = _text(mailing.get("source_state_code"))
        projected["mailing_address"] = projected_mailing

    assessment = record.get("assessment")
    if isinstance(assessment, Mapping):
        projected_assessment = dict(assessment)
        assessment_date = _text(assessment.get("assessment_date"))
        market_value = assessment.get("market_value")
        projected_assessment["tax_year"] = (
            assessment_date[:4]
            if assessment_date and len(assessment_date) >= 4
            else None
        )
        projected_assessment["parcel_value"] = market_value
        classification = record.get("classification")
        if isinstance(classification, Mapping):
            projected_assessment["assessment_class"] = _text(
                classification.get("category_code")
            )
        projected["assessment"] = projected_assessment
        projected["tax_year"] = projected_assessment.get("tax_year")
        projected["source_last_updated"] = assessment_date

    last_sale = record.get("last_sale")
    if isinstance(last_sale, Mapping):
        projected_sale = dict(last_sale)
        projected_sale["source_document_date"] = _text(last_sale.get("recording_date"))
        projected_sale["source_document_ref"] = _text(
            last_sale.get("registry_number") or last_sale.get("book_and_page_raw")
        )
        projected["last_sale"] = projected_sale

    if isinstance(record.get("geometry"), Mapping):
        projected["geometry_disclaimer"] = (
            "Source-published OPA property point; use the Department of "
            "Records parcel source for deed-description-derived boundaries."
        )

    return _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="current_property_assessment_observation",
    )


def _ingest_philadelphia_history_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Attach an annual OPA history row to the stable OPA parcel identity."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_type")) != ("annual_property_assessment_observation"):
        return {
            "projection_skipped": True,
            "reason": "history_component_record_is_not_an_annual_assessment",
            "record_type": _text(record.get("record_type")),
        }
    native_parcel_id = _text(record.get("native_parcel_id"))
    assessment_year = _text(record.get("assessment_year"))
    if not native_parcel_id or not assessment_year:
        raise PropertyIngestError(
            "Philadelphia assessment history requires parcel number and year"
        )

    geoid = _upsert_jurisdiction(db, record)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_native_id = _text(record.get("native_id")) or (
        f"{native_parcel_id}:{assessment_year}:"
        f"{_text(record.get('object_id')) or 'unknown'}"
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind="annual_property_assessment_observation",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_row = db.execute(
        """
        SELECT parcel_id
        FROM parcel_snapshot
        WHERE jurisdiction_geoid=? AND native_parcel_id=?
          AND source_id IN (?, ?)
        ORDER BY
          CASE WHEN source_id=? THEN 0 ELSE 1 END,
          roll_year DESC,
          parcel_id DESC
        LIMIT 1
        """,
        (
            geoid,
            native_parcel_id,
            PHILADELPHIA_OPA_SOURCE_ID,
            PHILADELPHIA_HISTORY_SOURCE_ID,
            PHILADELPHIA_OPA_SOURCE_ID,
        ),
    ).fetchone()
    if parcel_row is None:
        parcel_id = _upsert_parcel_snapshot(
            db,
            source_id=source_id,
            jurisdiction_geoid=geoid,
            native_parcel_id=native_parcel_id,
            roll_year="",
            effective_from=None,
            source_good_through=assessment_year,
            observation_id=observation_id,
            record=record,
        )
    else:
        parcel_id = int(parcel_row["parcel_id"])

    assessment = _mapping(record.get("assessment"), "record.assessment")
    assessments_upserted = _upsert_assessment_projection(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        tax_year=assessment_year,
        market_value=assessment.get("market_value"),
        source_good_through=assessment_year,
        observation_id=observation_id,
        raw=assessment,
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id,
            geoid,
            "parcel-assessment",
            source_native_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "assessments_upserted": assessments_upserted,
    }


def _philadelphia_dor_parcel_id(
    db,
    *,
    geoid: str,
    identifiers: list[str],
) -> int | None:
    """Resolve a DOR map/PIN identifier without creating a competing parcel."""

    if not identifiers:
        return None
    placeholders = ", ".join("?" for _ in identifiers)
    source_ids = (
        PHILADELPHIA_OPA_SOURCE_ID,
        PHILADELPHIA_HISTORY_SOURCE_ID,
    )
    parcel_row = db.execute(
        f"""
        SELECT parcel_id
        FROM parcel_snapshot
        WHERE jurisdiction_geoid=?
          AND source_id IN (?, ?)
          AND native_parcel_id IN ({placeholders})
        ORDER BY
          CASE WHEN source_id=? THEN 0 ELSE 1 END,
          roll_year DESC,
          parcel_id DESC
        LIMIT 1
        """,
        (geoid, *source_ids, *identifiers, PHILADELPHIA_OPA_SOURCE_ID),
    ).fetchone()
    if parcel_row is None:
        parcel_row = db.execute(
            f"""
            SELECT ps.parcel_id
            FROM parcel_alias AS pa
            JOIN parcel_snapshot AS ps ON ps.parcel_id=pa.parcel_id
            WHERE ps.jurisdiction_geoid=?
              AND ps.source_id IN (?, ?)
              AND pa.alias_value IN ({placeholders})
              AND pa.effective_to IS NULL
            ORDER BY
              CASE WHEN ps.source_id=? THEN 0 ELSE 1 END,
              ps.roll_year DESC,
              ps.parcel_id DESC
            LIMIT 1
            """,
            (geoid, *source_ids, *identifiers, PHILADELPHIA_OPA_SOURCE_ID),
        ).fetchone()
    return int(parcel_row["parcel_id"]) if parcel_row is not None else None


def _ingest_philadelphia_dor_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve a DOR map row and join its geometry to an OPA parcel."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_type")) != ("deed_description_parcel_map_observation"):
        return {
            "projection_skipped": True,
            "reason": "dor_component_record_is_not_a_parcel_map",
            "record_type": _text(record.get("record_type")),
        }
    source_native_id = _text(record.get("native_id")) or _text(record.get("object_id"))
    if not source_native_id:
        raise PropertyIngestError(
            "Philadelphia DOR parcel row requires a native identifier"
        )
    geoid = _upsert_jurisdiction(db, record)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind="deed_description_parcel_map_observation",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    identifiers = list(
        dict.fromkeys(
            value
            for value in (
                _text(record.get("map_registry_number")),
                _text(record.get("base_registry_number")),
                _text(record.get("pin")),
            )
            if value
        )
    )
    parcel_id = _philadelphia_dor_parcel_id(
        db,
        geoid=geoid,
        identifiers=identifiers,
    )
    if parcel_id is None:
        return {
            "projection": "observation_only",
            "projection_reason": "awaiting_opa_registry_or_pin_join",
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "source_native_id": source_native_id,
        }

    aliases_inserted = 0
    for alias_type, alias_value in (
        ("philadelphia_map_registry", record.get("map_registry_number")),
        ("philadelphia_base_registry", record.get("base_registry_number")),
        ("philadelphia_pin", record.get("pin")),
    ):
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=_text(record.get("origin_date")) or retrieved_at,
        )

    addresses_inserted = 0
    address = record.get("address")
    if isinstance(address, Mapping) and _text(address.get("standardized")):
        addresses_inserted = int(
            _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                role="situs",
                address={"raw": address.get("standardized")},
                effective_from=_text(record.get("origin_date")) or retrieved_at,
            )
        )

    geometry_upserted = 0
    if isinstance(record.get("geometry"), Mapping):
        db.execute(
            """
            INSERT INTO parcel_geometry(
                parcel_id, geometry_ref, geometry_format, crs,
                source_resolution, accuracy_disclaimer, source_id,
                snapshot_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
                geometry_ref=excluded.geometry_ref,
                geometry_format=excluded.geometry_format,
                crs=excluded.crs,
                source_resolution=excluded.source_resolution,
                accuracy_disclaimer=excluded.accuracy_disclaimer
            """,
            (
                parcel_id,
                f"source-observation:{observation_id}#/geometry",
                _text(record.get("geometry_format")) or "esri_json",
                _text(record.get("geometry_crs")) or "EPSG:4326",
                "source_parcel_polygon",
                (
                    "Department of Records parcel-map observation derived "
                    "from recorded deed descriptions; consult the recorded "
                    "instrument for controlling text."
                ),
                source_id,
                retrieved_at,
            ),
        )
        geometry_upserted = 1

    return {
        "parcel_id": parcel_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            geoid,
            "registry",
            source_native_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "geometry_upserted": geometry_upserted,
    }


def _ingest_oregon_county_observation_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
    source_native_id: str | None,
    observation_kind: str | None,
    reason: str | None,
) -> dict[str, Any]:
    """Store a county survey, geometry, or document-index observation."""

    _assert_record_source(record, source_id)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    geoid, county_name = oregon_county_property_projection.SOURCE_JURISDICTIONS[
        source_id
    ]
    _upsert_jurisdiction_values(
        db,
        geoid=geoid,
        name=f"{county_name} County",
        state_code="OR",
        jurisdiction_type="county",
        parent_geoid="41",
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=observation_kind
        or _text(record.get("record_kind"))
        or "source_row",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return {
        "projection": "observation_only",
        "projection_reason": reason,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": source_native_id,
        "record_kind": observation_kind,
    }


def _ingest_oregon_county_property_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Apply the explicit projection decision for one county adapter record."""

    decision = oregon_county_property_projection.project_record(
        record,
        source_id=source_id,
    )
    if decision.kind == "assessor":
        return _ingest_assessor_record(
            db,
            envelope=envelope,
            record=decision.record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            observation_kind=(
                _text(decision.record.get("record_kind")) or "parcel_snapshot"
            ),
        )
    if decision.kind == "property_event":
        parcel_alias_sources = (
            oregon_county_property_projection.PROPERTY_EVENT_PARCEL_ALIAS_SOURCE_IDS
        )
        parcel_alias_source_id = parcel_alias_sources.get(source_id)
        return _ingest_property_event_record(
            db,
            envelope=envelope,
            record=decision.record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            expected_geoid=(
                oregon_county_property_projection.SOURCE_JURISDICTIONS[source_id][0]
            ),
            parcel_alias_source_id=parcel_alias_source_id,
        )
    return _ingest_oregon_county_observation_record(
        db,
        envelope=envelope,
        record=decision.record,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        source_native_id=decision.source_native_id,
        observation_kind=decision.observation_kind,
        reason=decision.reason,
    )


def _ingest_washington_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project parcel rows and preserve companion/lineage rows as observations."""

    decision = washington_parcel_projection.project_record(
        record,
        source_id=source_id,
    )
    if decision.kind == "assessor":
        return _ingest_assessor_record(
            db,
            envelope=envelope,
            record=decision.record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            observation_kind="parcel_snapshot",
        )

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    county_geoid = _text(decision.record.get("county_geoid"))
    if county_geoid and county_geoid.isdigit() and len(county_geoid) == 5:
        county_name = _text(decision.record.get("county_name")) or county_geoid
        if not county_name.casefold().endswith("county"):
            county_name = f"{county_name} County"
        _upsert_jurisdiction_values(
            db,
            geoid=county_geoid,
            name=county_name,
            state_code="WA",
            jurisdiction_type="county",
            parent_geoid="53",
        )
    else:
        _upsert_jurisdiction_values(
            db,
            geoid="53",
            name="Washington",
            state_code="WA",
            jurisdiction_type="state",
        )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=decision.source_native_id,
        record_kind=decision.observation_kind or "source_row",
        query_fingerprint=query_fingerprint,
        source_url=(
            _record_source_url(envelope, decision.record)
            or washington_parcel_projection.SOURCE_URLS[source_id]
        ),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(decision.record),
        raw=decision.record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return {
        "projection": "observation_only",
        "projection_reason": decision.reason,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": decision.source_native_id,
        "record_kind": decision.observation_kind,
    }


def _dc_tax_events(
    db,
    *,
    record: Mapping[str, Any],
    source_id: str,
    parcel_id: int,
    observation_id: int,
) -> int:
    """Project the published ITSPE account snapshot into tax event rows."""

    if source_id != dc_property_projection.ITSPE_SOURCE_ID:
        return 0
    tax = record.get("tax")
    if not isinstance(tax, Mapping):
        return 0
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        raise PropertyIngestError("DC ITSPE tax projection requires an SSL")
    extract_date = _text(
        record.get("source_extract_date") or record.get("source_last_updated")
    )
    tax_year = _text(record.get("tax_year"))
    count = 0

    aggregate_fields = {
        "annual_tax": "account_annual_tax",
        "total_due": "account_total_due",
        "total_collected": "account_total_collected",
        "total_balance": "account_total_balance",
    }
    for source_field, event_type in aggregate_fields.items():
        value = tax.get(source_field)
        if value in (None, ""):
            continue
        count += _upsert_tax_account_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=tax_year,
            event_type=event_type,
            event_date=extract_date,
            amount=value,
            status="published_account_snapshot",
            native_event_id=f"{native_parcel_id}:account:{source_field}",
            observation_id=observation_id,
            raw={
                "scope": "account_snapshot",
                "source_field": source_field,
                "value": value,
                "source_extract_date": extract_date,
            },
        )

    installments = tax.get("installments")
    if isinstance(installments, list):
        for index, installment_value in enumerate(installments, start=1):
            if not isinstance(installment_value, Mapping):
                continue
            due_date = _text(installment_value.get("due_date_raw"))
            amount_due = installment_value.get("amount_due")
            if due_date is None and amount_due in (None, ""):
                continue
            count += _upsert_tax_account_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                tax_year=tax_year,
                event_type="installment_due",
                event_date=due_date,
                amount=amount_due,
                status="published_installment",
                native_event_id=(
                    f"{native_parcel_id}:installment:{index}:{due_date or ''}"
                ),
                observation_id=observation_id,
                raw=dict(installment_value),
            )

    period_fields = {
        "tax": "period_tax",
        "penalty": "period_penalty",
        "interest": "period_interest",
        "fee": "period_fee",
        "total_due": "period_total_due",
        "collected": "period_collected",
        "balance": "period_balance",
        "credits": "period_credits",
    }
    periods = tax.get("periods")
    if isinstance(periods, list):
        for index, period_value in enumerate(periods, start=1):
            if not isinstance(period_value, Mapping):
                continue
            prefix = _text(period_value.get("source_prefix")) or str(index)
            period_year = _text(period_value.get("year_label")) or tax_year
            period_status = (
                _text(period_value.get("tax_sale_flag")) or "published_period_snapshot"
            )
            for source_field, event_type in period_fields.items():
                value = period_value.get(source_field)
                if value in (None, ""):
                    continue
                count += _upsert_tax_account_projection(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    tax_year=period_year,
                    event_type=event_type,
                    event_date=extract_date,
                    amount=value,
                    status=period_status,
                    native_event_id=(f"{native_parcel_id}:{prefix}:{source_field}"),
                    observation_id=observation_id,
                    raw=dict(period_value),
                )
    last_payment_date = _text(tax.get("last_payment_date"))
    if last_payment_date:
        count += _upsert_tax_account_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=tax_year,
            event_type="last_payment_date",
            event_date=last_payment_date,
            amount=None,
            status="published_account_snapshot",
            native_event_id=f"{native_parcel_id}:last-payment",
            observation_id=observation_id,
            raw={
                "last_payment_date": last_payment_date,
                "source_extract_date": extract_date,
            },
        )
    return count


def _dc_sale_parcel(
    db,
    *,
    record: Mapping[str, Any],
    source_id: str,
    observation_id: int,
) -> int:
    """Resolve a CAMA SSL to an existing account/geometry parcel or placeholder."""

    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        raise PropertyIngestError("DC CAMA sale record requires an SSL")
    row = db.execute(
        """
        SELECT parcel_id
        FROM parcel_snapshot
        WHERE jurisdiction_geoid='11' AND native_parcel_id=?
        ORDER BY CASE source_id
            WHEN ? THEN 0
            WHEN ? THEN 1
            ELSE 2
        END, parcel_id
        LIMIT 1
        """,
        (
            native_parcel_id,
            dc_property_projection.ITSPE_SOURCE_ID,
            dc_property_projection.OWNER_POLYGON_SOURCE_ID,
        ),
    ).fetchone()
    if row is not None:
        return int(row["parcel_id"])
    return _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid="11",
        native_parcel_id=native_parcel_id,
        roll_year="",
        effective_from=_text(record.get("source_last_updated")),
        source_good_through=_text(record.get("source_last_updated")),
        observation_id=observation_id,
        record=record,
    )


def _ingest_dc_property_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Apply the component-specific DC property projection decision."""

    decision = dc_property_projection.project_record(
        record,
        source_id=source_id,
    )
    if decision.kind == "assessor":
        result = _ingest_assessor_record(
            db,
            envelope=envelope,
            record=decision.record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            observation_kind=(
                _text(decision.record.get("record_type")) or "parcel_snapshot"
            ),
        )
        result["tax_events_upserted"] = _dc_tax_events(
            db,
            record=decision.record,
            source_id=source_id,
            parcel_id=int(result["parcel_id"]),
            observation_id=int(result["observation_id"]),
        )
        return result

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    _upsert_jurisdiction_values(
        db,
        geoid="11",
        name="District of Columbia",
        state_code="DC",
        jurisdiction_type="state",
    )
    _assert_record_source(decision.record, source_id)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=decision.source_native_id,
        record_kind=decision.observation_kind or "source_row",
        query_fingerprint=query_fingerprint,
        source_url=(
            _record_source_url(envelope, decision.record)
            or dc_property_projection.SOURCE_URLS[source_id]
        ),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(decision.record),
        raw=decision.record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    if decision.kind == "sale":
        parcel_id = _dc_sale_parcel(
            db,
            record=decision.record,
            source_id=source_id,
            observation_id=observation_id,
        )
        sale = decision.record.get("sale")
        if not isinstance(sale, Mapping):
            raise PropertyIngestError("DC CAMA sale record lacks sale details")
        native_sale_id = _text(decision.record.get("native_id"))
        if not native_sale_id:
            raise PropertyIngestError("DC CAMA sale record lacks native_id")
        sales_upserted = _upsert_sale_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            native_sale_id=native_sale_id,
            sale_date=_text(sale.get("sale_date")),
            consideration=sale.get("consideration"),
            derivation="dc_cama_property_sales",
            observation_id=observation_id,
            raw=sale,
            qualification_code=_text(sale.get("qualified") or sale.get("sale_code")),
        )
        return {
            "parcel_id": parcel_id,
            "canonical_ref": canonical_property_ref(
                source_id,
                "11",
                "sale",
                native_sale_id,
            ),
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "sales_upserted": sales_upserted,
        }
    return {
        "projection": "observation_only",
        "projection_reason": decision.reason,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": decision.source_native_id,
        "record_kind": decision.observation_kind,
    }


def _normalized_map_taxlot(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    normalized = "".join(character for character in text.upper() if character.isalnum())
    return normalized or None


def _ingest_jackson_douglas_assessor_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project the two county field maps into the shared assessor tables."""

    projected = dict(record)
    assessment = record.get("assessment")
    classification = record.get("classification")
    if isinstance(assessment, Mapping):
        normalized_assessment = dict(assessment)
        normalized_assessment.update(
            {
                "land_value": assessment.get("market_land"),
                "improvement_value": assessment.get("market_improvements"),
                "parcel_value": assessment.get("market_total"),
                "market_value": assessment.get("market_total"),
                "assessed_value": (
                    assessment.get("assessed_total")
                    if assessment.get("assessed_total") not in (None, "")
                    else assessment.get("assessed_value")
                ),
                "assessment_class": (
                    classification.get("property_class")
                    if isinstance(classification, Mapping)
                    else None
                ),
            }
        )
        projected["assessment"] = normalized_assessment

    aliases = [
        value for value in projected.get("alternate_parcel_ids", []) if _text(value)
    ]
    for value in projected.get("assessment_account_ids", []):
        if _text(value) and _text(value) not in aliases:
            aliases.append(value)
    projected["alternate_parcel_ids"] = aliases

    sale_reference = record.get("published_instrument_and_sale_reference")
    if isinstance(sale_reference, Mapping) and any(
        sale_reference.get(key) not in (None, "")
        for key in ("instrument_number", "sale_date")
    ):
        projected["last_sale"] = {
            "source_document_ref": sale_reference.get("instrument_number"),
            "sale_date": sale_reference.get("sale_date"),
            "scope": sale_reference.get("scope"),
            "derivation": "assessor_current_parcel_reference",
        }

    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    parcel_id = int(result["parcel_id"])
    effective_from = (
        _text(record.get("source_revised_date") or record.get("source_last_updated"))
        or ""
    )
    typed_aliases: list[tuple[str, Any]] = [
        ("assessment_account", value)
        for value in record.get("assessment_account_ids", [])
    ]
    map_taxlot = record.get("map_taxlot")
    if isinstance(map_taxlot, Mapping):
        for key, alias_type in (
            ("combined", "map_taxlot_combined"),
            ("compact", "map_taxlot_compact"),
            ("map_number", "map_number"),
            ("alternate_map_number", "alternate_map_number"),
            ("taxlot", "taxlot"),
        ):
            value = map_taxlot.get(key)
            typed_aliases.append((alias_type, value))
            typed_aliases.append(
                ("map_taxlot_normalized", _normalized_map_taxlot(value))
            )
    elif source_id == DOUGLAS_ASSESSOR_SOURCE_ID:
        typed_aliases.append(
            ("map_taxlot_normalized", _normalized_map_taxlot(record.get("tax_id")))
        )

    typed_aliases_inserted = 0
    seen: set[tuple[str, str]] = set()
    for alias_type, value in typed_aliases:
        normalized_value = _text(value)
        if not normalized_value or (alias_type, normalized_value) in seen:
            continue
        seen.add((alias_type, normalized_value))
        typed_aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=normalized_value,
            source_id=source_id,
            effective_from=effective_from,
        )
    result["typed_aliases_inserted"] = typed_aliases_inserted
    return result


def _event_date(record: Mapping[str, Any], key: str) -> str | None:
    event_dates = record.get("event_dates")
    if not isinstance(event_dates, Mapping):
        return None
    value = event_dates.get(key)
    if not isinstance(value, Mapping):
        return None
    return _text(value.get("utc_date"))


def _ingest_property_event_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
    expected_geoid: str,
    parcel_alias_source_id: str | None,
) -> dict[str, Any]:
    """Project a local property event or document without title semantics."""

    _assert_record_source(record, source_id)
    native_event_id = _text(record.get("native_event_id"))
    source_record_id = _text(record.get("source_record_id") or record.get("object_id"))
    if not native_event_id or not source_record_id:
        raise PropertyIngestError(
            "property-event records require native_event_id and source_record_id"
        )
    geoid = _upsert_jurisdiction(db, record)
    if geoid != expected_geoid:
        raise PropertyIngestError(f"{source_id} record has out-of-scope GEOID {geoid}")

    query = _mapping(envelope.get("query"), "query")
    query_fingerprint = _text(query.get("fingerprint"))
    retrieved_at = _text(envelope.get("retrieved_at"))
    if not retrieved_at:
        raise PropertyIngestError("retrieved_at is required")
    status = _text(envelope.get("status")) or "ok"
    warnings = envelope.get("warnings", [])
    if not isinstance(warnings, list) or not all(
        isinstance(item, str) for item in warnings
    ):
        raise PropertyIngestError("warnings must be a list of strings")
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=f"{native_event_id}:{source_record_id}",
        record_kind=_text(record.get("record_kind")) or "property_event",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    address = record.get("address")
    address_raw = _text(address.get("raw")) if isinstance(address, Mapping) else None
    join_evidence = record.get("parcel_join_evidence")
    published_location = (
        join_evidence.get("published_location")
        if isinstance(join_evidence, Mapping)
        else None
    )
    map_taxlot_candidate = (
        _text(published_location.get("normalized_candidate"))
        if isinstance(published_location, Mapping)
        else None
    )
    permit = record.get("permit")
    estimated_cost = (
        permit.get("estimated_cost") if isinstance(permit, Mapping) else None
    )
    geometry = record.get("geometry")
    longitude = geometry.get("x") if isinstance(geometry, Mapping) else None
    latitude = geometry.get("y") if isinstance(geometry, Mapping) else None
    values = (
        _text(record.get("record_kind")) or "property_event",
        _text(record.get("event_type")),
        _text(record.get("description")),
        _text(record.get("status")),
        _text(record.get("status_category")),
        _text(record.get("event_date")),
        _text(record.get("normalized_case_number")),
        _event_date(record, "submitted"),
        _event_date(record, "approved"),
        _event_date(record, "last_update"),
        _minor_units(estimated_cost),
        address_raw,
        map_taxlot_candidate,
        float(longitude) if longitude not in (None, "") else None,
        float(latitude) if latitude not in (None, "") else None,
        _text(record.get("geometry_crs")),
        observation_id,
        canonical_json(record),
    )
    db.execute(
        """
        INSERT INTO property_event(
            source_id, jurisdiction_geoid, native_event_id, source_record_id,
            record_kind, event_type, description, status, status_category,
            event_date, normalized_case_number,
            submitted_date, approved_date, last_update_date,
            estimated_cost_minor, currency, address_raw, map_taxlot_candidate,
            longitude, latitude, geometry_crs, observation_id, raw_json
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD',
            ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(
            source_id, jurisdiction_geoid, native_event_id, source_record_id
        ) DO UPDATE SET
            record_kind=excluded.record_kind,
            event_type=excluded.event_type,
            description=excluded.description,
            status=excluded.status,
            status_category=excluded.status_category,
            event_date=excluded.event_date,
            normalized_case_number=excluded.normalized_case_number,
            submitted_date=excluded.submitted_date,
            approved_date=excluded.approved_date,
            last_update_date=excluded.last_update_date,
            estimated_cost_minor=excluded.estimated_cost_minor,
            address_raw=excluded.address_raw,
            map_taxlot_candidate=excluded.map_taxlot_candidate,
            longitude=excluded.longitude,
            latitude=excluded.latitude,
            geometry_crs=excluded.geometry_crs,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (source_id, geoid, native_event_id, source_record_id, *values),
    )
    event_row = db.execute(
        """
        SELECT event_id FROM property_event
        WHERE source_id=? AND jurisdiction_geoid=? AND native_event_id=?
          AND source_record_id=?
        """,
        (source_id, geoid, native_event_id, source_record_id),
    ).fetchone()
    event_id = int(event_row["event_id"])

    db.execute("DELETE FROM property_event_party WHERE event_id=?", (event_id,))
    parties_upserted = 0
    people = record.get("people", [])
    if not isinstance(people, list):
        raise PropertyIngestError("record.people must be a list")
    for sequence_no, value in enumerate(people, start=1):
        person = _mapping(value, "record.people[]")
        raw_name = _text(person.get("raw_name"))
        if not raw_name:
            continue
        db.execute(
            """
            INSERT INTO property_event_party(
                event_id, sequence_no, role, raw_name, normalized_name,
                assertion_type
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                sequence_no,
                _text(person.get("role")) or "published_party",
                raw_name,
                " ".join(raw_name.upper().split()),
                _text(person.get("assertion_type")),
            ),
        )
        parties_upserted += 1

    matching_parcels: list[int] = []
    if map_taxlot_candidate and parcel_alias_source_id:
        matching_parcels = sorted(
            {
                int(row["parcel_id"])
                for row in db.execute(
                    """
                    SELECT parcel_id
                    FROM parcel_snapshot
                    WHERE source_id=? AND native_parcel_id=?
                    UNION
                    SELECT parcel_id
                    FROM parcel_alias
                    WHERE source_id=?
                      AND (
                        (alias_type='map_taxlot_normalized' AND alias_value=?)
                        OR alias_value=?
                      )
                    """,
                    (
                        parcel_alias_source_id,
                        map_taxlot_candidate,
                        parcel_alias_source_id,
                        map_taxlot_candidate,
                        map_taxlot_candidate,
                    ),
                )
            }
        )
    parcel_id = matching_parcels[0] if len(matching_parcels) == 1 else None
    link_method = (
        "exact_published_map_taxlot_alias"
        if parcel_id is not None
        else "ambiguous_published_map_taxlot"
        if matching_parcels
        else "unresolved_published_map_taxlot"
    )
    db.execute(
        """
        INSERT INTO property_event_parcel_link(
            event_id, parcel_id, map_taxlot_candidate, link_method,
            link_confidence, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            parcel_id=excluded.parcel_id,
            map_taxlot_candidate=excluded.map_taxlot_candidate,
            link_method=excluded.link_method,
            link_confidence=excluded.link_confidence,
            evidence_json=excluded.evidence_json
        """,
        (
            event_id,
            parcel_id,
            map_taxlot_candidate,
            link_method,
            1.0 if parcel_id is not None else None,
            canonical_json(join_evidence or {}),
        ),
    )

    db.execute(
        "DELETE FROM property_event_representation WHERE event_id=?",
        (event_id,),
    )
    representations_upserted = 0
    representations = record.get("detail_representations", [])
    if not isinstance(representations, list):
        raise PropertyIngestError("record.detail_representations must be a list")
    for value in representations:
        representation = _mapping(value, "record.detail_representations[]")
        source_url = _text(representation.get("url"))
        if not source_url:
            continue
        db.execute(
            """
            INSERT INTO property_event_representation(
                event_id, representation_kind, source_url, relationship,
                source_state, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                _text(representation.get("kind")) or "linked_detail",
                source_url,
                _text(representation.get("relationship")),
                _text(representation.get("source_state")),
                canonical_json(representation),
            ),
        )
        representations_upserted += 1

    return {
        "event_id": event_id,
        "canonical_ref": canonical_property_ref(
            source_id,
            geoid,
            _text(record.get("record_kind")) or "property_event",
            f"{native_event_id}:{source_record_id}",
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "parties_upserted": parties_upserted,
        "parcel_id": parcel_id,
        "parcel_link_method": link_method,
        "representations_upserted": representations_upserted,
    }


def _normalized_foreclosure_case(value: Any) -> str | None:
    normalized = re.sub(r"[^A-Z0-9]", "", (_text(value) or "").upper())
    return normalized or None


def _normalized_foreclosure_parcel(value: Any) -> str | None:
    normalized = re.sub(r"[^A-Z0-9]", "", (_text(value) or "").upper())
    return normalized or None


def _foreclosure_event_scope(
    source_id: str,
) -> tuple[str, str, str]:
    if source_id == OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID:
        return "39089", "Licking County", "OH"
    try:
        return OHIO_SHERIFF_REALAUCTION_SCOPES[source_id]
    except KeyError as error:
        raise PropertyIngestError(
            f"unsupported Ohio foreclosure-event source: {source_id}"
        ) from error


def _preserve_ohio_foreclosure_metadata_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    query_fingerprint, retrieved_at, status, warnings = _observation_context(
        envelope
    )
    record_kind = _text(record.get("record_kind")) or "source_metadata"
    native_id = (
        _text(record.get("auction_date"))
        or _text(record.get("year"))
        or _text(record.get("canonical_ref"))
        or record_kind
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return {
        "projection_skipped": True,
        "reason": "foreclosure_source_metadata_observation",
        "record_kind": record_kind,
        "source_native_id": native_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "metadata_observation_inserted": True,
    }


def _ohio_foreclosure_projection_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    geoid, county_name, state_code = _foreclosure_event_scope(source_id)
    record_kind = _text(record.get("record_kind"))
    is_archive = (
        source_id == OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID
    )
    if is_archive:
        if record_kind != "sheriff_foreclosure_archive_record":
            raise PropertyIngestError(
                "Licking foreclosure archive detail has an unknown record kind"
            )
        native_event_id = _text(
            record.get("native_case_number") or record.get("case_number")
        )
        event_date = _text(record.get("sale_date"))
        status = _text(record.get("status") or record.get("status_raw"))
        event_type = "sheriff_foreclosure_archive_observation"
    else:
        if record_kind != "sheriff_sale_auction":
            raise PropertyIngestError(
                "Ohio RealAuction detail has an unknown record kind"
            )
        native_event_id = _text(record.get("native_auction_id"))
        event_date = _text(record.get("auction_date"))
        status = _text(
            record.get("auction_status")
            or record.get("source_status_message")
            or record.get("case_status")
        )
        event_type = "sheriff_sale_auction_observation"
    if not native_event_id or not event_date:
        raise PropertyIngestError(
            "Ohio foreclosure event requires its native identity and event date"
        )

    case_number = _text(record.get("case_number"))
    normalized_case = _normalized_foreclosure_case(case_number)
    raw_parcels = record.get("parcel_ids") or []
    if not isinstance(raw_parcels, list):
        raise PropertyIngestError(
            "Ohio foreclosure event parcel_ids must be a list"
        )
    published_parcels = [
        _text(value) for value in raw_parcels if _text(value)
    ]
    normalized_parcels = sorted(
        {
            normalized
            for value in raw_parcels
            if (normalized := _normalized_foreclosure_parcel(value))
        }
    )
    join_evidence = {
        "relationship": "same_event_candidate",
        "independent_corroboration": False,
        "normalized_case_number": normalized_case,
        "event_date": event_date,
        "published_parcel_ids": published_parcels,
        "normalized_parcel_ids": normalized_parcels,
        "match_requirement": (
            "exact normalized case, exact event date, and at least one exact "
            "overlapping normalized published parcel"
        ),
    }
    parcel_join_evidence: dict[str, Any] = {
        "published_parcel_ids": join_evidence["published_parcel_ids"],
        "normalized_candidates": normalized_parcels,
        "jurisdiction_geoid": geoid,
        "resolution_requirement": (
            "one published parcel and one exact OGRIP local-parcel match"
        ),
    }
    if len(published_parcels) == 1 and len(normalized_parcels) == 1:
        parcel_join_evidence["published_location"] = {
            "raw": join_evidence["published_parcel_ids"][0],
            "normalized_candidate": normalized_parcels[0],
        }

    people: list[dict[str, Any]] = []
    if is_archive:
        for role, value in (
            ("source_reported_deed_as", record.get("deed_as")),
            (
                "source_reported_purchaser_contact",
                record.get("purchaser_contact_name"),
            ),
        ):
            raw_name = _text(value)
            if raw_name:
                people.append(
                    {
                        "role": role,
                        "raw_name": raw_name,
                        "assertion_type": (
                            "auction_outcome_observation_not_ownership"
                        ),
                    }
                )

    address_parts = [
        _text(record.get("property_address")),
        _text(record.get("city")),
        state_code,
        _text(record.get("postal_code") or record.get("postal_code_raw")),
    ]
    address_raw = " ".join(part for part in address_parts if part)
    projection = {
        **dict(record),
        "source_id": source_id,
        "native_event_id": native_event_id,
        "source_record_id": native_event_id,
        "record_kind": record_kind,
        "event_type": event_type,
        "description": (
            f"Source-reported sheriff-sale event"
            f"{f' for case {case_number}' if case_number else ''}"
        ),
        "status": status,
        "status_category": "source_reported_auction_status",
        "event_date": event_date,
        "normalized_case_number": normalized_case,
        "jurisdiction": {
            "county_geoid": geoid,
            "county_name": county_name,
            "state_code": state_code,
        },
        "address": {"raw": address_raw or None},
        "people": people,
        "parcel_join_evidence": parcel_join_evidence,
        "same_event_join": join_evidence,
        "event_observation": {
            "event_date": event_date,
            "case_number": case_number,
            "parcel_ids": list(raw_parcels),
            "appraised_value_amount": record.get(
                "appraised_value_amount"
            ),
            "opening_bid_amount": record.get("opening_bid_amount"),
            "deposit_requirement_amount": record.get(
                "deposit_requirement_amount"
            ),
            "required_deposit_amount": record.get(
                "required_deposit_amount"
            ),
            "source_reported_bid_amount": record.get(
                "source_reported_bid_amount"
            ),
            "sold_amount": record.get("sold_amount"),
            "purchase_price_amount": record.get("purchase_price_amount"),
            "currency": "USD",
        },
        "detail_representations": [],
    }
    return projection


def _resolve_ohio_foreclosure_parcel_link(
    db,
    *,
    event_id: int,
    jurisdiction_geoid: str,
    published_parcels: Sequence[str],
) -> tuple[int | None, str]:
    normalized = sorted(
        {
            candidate
            for value in published_parcels
            if (candidate := _normalized_foreclosure_parcel(value))
        }
    )
    evidence = {
        "published_parcel_ids": list(published_parcels),
        "normalized_candidates": normalized,
        "jurisdiction_geoid": jurisdiction_geoid,
        "parcel_source_id": OHIO_STATEWIDE_PARCELS_SOURCE_ID,
    }
    parcel_id = None
    link_method = "unresolved_no_indexed_ogrip_alias_match"
    if len(published_parcels) == 1 and len(normalized) == 1:
        published = _text(published_parcels[0]) or ""
        county_local = f"{jurisdiction_geoid}|{published}"
        statewide_native = f"{jurisdiction_geoid}-{published}"
        rows = db.execute(
            """
            SELECT p.parcel_id
            FROM parcel_alias a
            JOIN parcel_snapshot p ON p.parcel_id=a.parcel_id
            WHERE a.source_id=? AND p.jurisdiction_geoid=?
              AND (
                  (
                      a.alias_type='local_parcel_id_normalized'
                      AND a.alias_value=?
                  )
                  OR (
                      a.alias_type='local_parcel_id'
                      AND a.alias_value=?
                  )
                  OR (
                      a.alias_type='county_local_parcel_id'
                      AND a.alias_value=?
                  )
              )
            UNION
            SELECT p.parcel_id
            FROM parcel_snapshot p
            WHERE p.source_id=? AND p.jurisdiction_geoid=?
              AND p.native_parcel_id IN (?, ?)
            """,
            (
                OHIO_STATEWIDE_PARCELS_SOURCE_ID,
                jurisdiction_geoid,
                normalized[0],
                published,
                county_local,
                OHIO_STATEWIDE_PARCELS_SOURCE_ID,
                jurisdiction_geoid,
                published,
                statewide_native,
            ),
        ).fetchall()
        matching = sorted({int(row["parcel_id"]) for row in rows})
        evidence["matching_parcel_ids"] = matching
        if len(matching) == 1:
            parcel_id = matching[0]
            link_method = "exact_ogrip_local_parcel_normalized"
        elif len(matching) > 1:
            link_method = "ambiguous_ogrip_local_parcel_normalized"
    elif len(published_parcels) > 1 or len(normalized) > 1:
        link_method = "multiple_published_parcels_unresolved"

    db.execute(
        """
        UPDATE property_event_parcel_link
        SET parcel_id=?, map_taxlot_candidate=?, link_method=?,
            link_confidence=?, evidence_json=?
        WHERE event_id=?
        """,
        (
            parcel_id,
            normalized[0] if len(normalized) == 1 else None,
            link_method,
            1.0 if parcel_id is not None else None,
            canonical_json(evidence),
            event_id,
        ),
    )
    return parcel_id, link_method


def _join_ohio_foreclosure_same_event(
    db,
    *,
    event_id: int,
    source_id: str,
    normalized_case_number: str | None,
    event_date: str,
    normalized_parcels: Sequence[str],
) -> tuple[str, list[int]]:
    licking_realauction_source = (
        query_ohio_sheriff_sales.TENANTS["licking"].source_id
    )
    paired_sources = {
        licking_realauction_source,
        OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID,
    }
    if source_id not in paired_sources:
        return "insufficient_exact_join_keys", []
    counterpart = (
        OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID
        if source_id == licking_realauction_source
        else licking_realauction_source
    )

    def clear_current_pair_relation() -> None:
        db.execute(
            """
            DELETE FROM property_event_relation
            WHERE relationship='same_event_candidate'
              AND (
                  (
                      event_id=?
                      AND related_event_id IN (
                          SELECT event_id FROM property_event
                          WHERE source_id=?
                      )
                  )
                  OR (
                      related_event_id=?
                      AND event_id IN (
                          SELECT event_id FROM property_event
                          WHERE source_id=?
                      )
                  )
              )
            """,
            (event_id, counterpart, event_id, counterpart),
        )

    if (
        not normalized_case_number
        or not event_date
        or not normalized_parcels
    ):
        clear_current_pair_relation()
        return "insufficient_exact_join_keys", []

    wanted_parcels = set(normalized_parcels)
    matches_by_event: dict[int, dict[str, Any]] = {}
    for row in db.execute(
        """
        SELECT e.event_id, e.native_event_id, k.normalized_parcel_id
        FROM property_event e
        JOIN property_event_parcel_join_key k
          ON k.event_id=e.event_id
        WHERE e.source_id=?
          AND e.jurisdiction_geoid='39089'
          AND e.normalized_case_number=?
          AND e.event_date=?
        """,
        (counterpart, normalized_case_number, event_date),
    ):
        normalized_parcel = str(row["normalized_parcel_id"])
        if normalized_parcel not in wanted_parcels:
            continue
        match = matches_by_event.setdefault(
            int(row["event_id"]),
            {
                "native_event_id": row["native_event_id"],
                "overlap": set(),
            },
        )
        match["overlap"].add(normalized_parcel)
    if not matches_by_event:
        clear_current_pair_relation()
        return "no_exact_cross_source_match", []

    current_event = db.execute(
        """
        SELECT native_event_id
        FROM property_event
        WHERE event_id=?
        """,
        (event_id,),
    ).fetchone()
    clear_current_pair_relation()
    relation_ids: list[int] = []
    involved_event_ids = {event_id}
    for related_event_id, matched in sorted(matches_by_event.items()):
        first_id, second_id = sorted((event_id, related_event_id))
        involved_event_ids.add(related_event_id)
        overlap = set(matched["overlap"])
        identities = {
            event_id: {
                "event_id": event_id,
                "source_id": source_id,
                "native_event_id": (
                    current_event["native_event_id"]
                    if current_event is not None
                    else None
                ),
            },
            related_event_id: {
                "event_id": related_event_id,
                "source_id": counterpart,
                "native_event_id": matched["native_event_id"],
            },
        }
        evidence = {
            "normalized_case_number": normalized_case_number,
            "event_date": event_date,
            "overlapping_parcels": sorted(overlap),
            "relationship": "same_event_candidate",
            "independent_corroboration": False,
            "left": identities[first_id],
            "right": identities[second_id],
        }
        db.execute(
            """
            INSERT INTO property_event_relation(
                event_id, related_event_id, relationship,
                independent_corroboration, normalized_case_number, event_date,
                overlapping_parcels_json, evidence_json
            ) VALUES (?, ?, 'same_event_candidate', 0, ?, ?, ?, ?)
            ON CONFLICT(event_id, related_event_id, relationship) DO UPDATE SET
                independent_corroboration=0,
                normalized_case_number=excluded.normalized_case_number,
                event_date=excluded.event_date,
                overlapping_parcels_json=excluded.overlapping_parcels_json,
                evidence_json=excluded.evidence_json
            """,
            (
                first_id,
                second_id,
                normalized_case_number,
                event_date,
                canonical_json(sorted(overlap)),
                canonical_json(evidence),
            ),
        )
        relation_row = db.execute(
            """
            SELECT relation_id FROM property_event_relation
            WHERE event_id=? AND related_event_id=?
              AND relationship='same_event_candidate'
            """,
            (first_id, second_id),
        ).fetchone()
        relation_ids.append(int(relation_row["relation_id"]))

    ambiguous = len(matches_by_event) > 1
    for involved_event_id in involved_event_ids:
        degree = db.execute(
            """
            SELECT COUNT(*) AS relation_count
            FROM property_event_relation r
            JOIN property_event left_event
              ON left_event.event_id=r.event_id
            JOIN property_event right_event
              ON right_event.event_id=r.related_event_id
            WHERE r.relationship='same_event_candidate'
              AND (r.event_id=? OR r.related_event_id=?)
              AND (
                  (
                      left_event.source_id=?
                      AND right_event.source_id=?
                  )
                  OR (
                      left_event.source_id=?
                      AND right_event.source_id=?
                  )
              )
            """,
            (
                involved_event_id,
                involved_event_id,
                source_id,
                counterpart,
                counterpart,
                source_id,
            ),
        ).fetchone()
        if int(degree["relation_count"]) > 1:
            ambiguous = True
            break
    return (
        "ambiguous_exact_cross_source_matches"
        if ambiguous
        else "exact_cross_source_match",
        sorted(relation_ids),
    )


def _ingest_ohio_foreclosure_event_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    detail_kinds = {
        "sheriff_sale_auction",
        "sheriff_foreclosure_archive_record",
    }
    if record_kind not in detail_kinds:
        return _preserve_ohio_foreclosure_metadata_record(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
        )

    projected = _ohio_foreclosure_projection_record(
        record,
        source_id=source_id,
    )
    geoid, _county_name, _state_code = _foreclosure_event_scope(source_id)
    result = _ingest_property_event_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        expected_geoid=geoid,
        parcel_alias_source_id=None,
    )
    join = _mapping(projected.get("same_event_join"), "same_event_join")
    normalized_parcels = [
        str(value)
        for value in (join.get("normalized_parcel_ids") or [])
        if value
    ]
    db.execute(
        "DELETE FROM property_event_parcel_join_key WHERE event_id=?",
        (int(result["event_id"]),),
    )
    for normalized_parcel in normalized_parcels:
        db.execute(
            """
            INSERT INTO property_event_parcel_join_key(
                event_id, normalized_parcel_id
            ) VALUES (?, ?)
            """,
            (int(result["event_id"]), normalized_parcel),
        )
    parcel_id, link_method = _resolve_ohio_foreclosure_parcel_link(
        db,
        event_id=int(result["event_id"]),
        jurisdiction_geoid=geoid,
        published_parcels=join.get("published_parcel_ids") or [],
    )
    relation_state, relation_ids = _join_ohio_foreclosure_same_event(
        db,
        event_id=int(result["event_id"]),
        source_id=source_id,
        normalized_case_number=_text(
            join.get("normalized_case_number")
        ),
        event_date=_text(join.get("event_date")) or "",
        normalized_parcels=normalized_parcels,
    )
    return {
        **result,
        "canonical_ref": _text(record.get("canonical_ref"))
        or result["canonical_ref"],
        "parcel_id": parcel_id,
        "parcel_link_method": link_method,
        "same_event_relation_state": relation_state,
        "same_event_relation_ids": relation_ids,
        "same_event_relation_id": (
            relation_ids[0] if len(relation_ids) == 1 else None
        ),
        "sales_upserted": 0,
        "ownership_assertions_upserted": 0,
        "recorded_instruments_upserted": 0,
        "title_transfer_assertions_upserted": 0,
    }


def _ingest_jackson_property_event_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one Jackson permit or compliance observation."""

    return _ingest_property_event_record(
        db,
        envelope=envelope,
        record=record,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        expected_geoid="41029",
        parcel_alias_source_id=JACKSON_ASSESSOR_SOURCE_ID,
    )


def _deschutes_cdd_document_projection(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Translate an index or metadata row into the shared event projection."""

    metadata_value = record.get("weblink_metadata")
    if not isinstance(metadata_value, Mapping):
        metadata_value = record.get("document_metadata")
    metadata = dict(metadata_value) if isinstance(metadata_value, Mapping) else {}
    document_id = _text(
        record.get("laserfiche_entry_id")
        or record.get("native_document_id")
        or metadata.get("laserfiche_entry_id")
        or metadata.get("native_document_id")
    )
    if not document_id:
        raise PropertyIngestError(
            "Deschutes CDD document record lacks a Laserfiche entry ID"
        )

    verified_link = record.get("verified_property_link")
    verified_link = dict(verified_link) if isinstance(verified_link, Mapping) else {}
    property_identifiers = record.get("property_identifiers")
    property_identifiers = (
        dict(property_identifiers) if isinstance(property_identifiers, Mapping) else {}
    )
    metadata_identifiers = metadata.get("property_identifiers")
    metadata_identifiers = (
        dict(metadata_identifiers) if isinstance(metadata_identifiers, Mapping) else {}
    )
    map_taxlot = _text(
        record.get("map_taxlot")
        or verified_link.get("map_taxlot")
        or metadata.get("map_taxlot")
        or property_identifiers.get("map_taxlot")
        or metadata_identifiers.get("map_taxlot")
    )
    account_id = _text(
        record.get("deschutes_dial_account_id")
        or verified_link.get("deschutes_dial_account_id")
        or property_identifiers.get("deschutes_dial_account_id")
        or metadata_identifiers.get("deschutes_dial_account_id")
    )
    account_index = record.get("account_index")
    account_index = dict(account_index) if isinstance(account_index, Mapping) else {}

    representations: list[dict[str, Any]] = []
    representation_candidates = (
        (
            "laserfiche_document_viewer",
            record.get("viewer_url")
            or metadata.get("viewer_url")
            or record.get("source_url")
            or metadata.get("source_url"),
            "source_document_view",
            record.get("retrieval_state") or metadata.get("retrieval_state"),
        ),
        (
            "laserfiche_document_metadata",
            record.get("metadata_endpoint") or metadata.get("metadata_endpoint"),
            "source_document_metadata",
            "metadata_available",
        ),
        (
            "electronic_file",
            record.get("electronic_file_url") or metadata.get("electronic_file_url"),
            "source_document_bytes",
            "download_available",
        ),
        (
            "generated_pdf_route",
            record.get("generated_pdf_route") or metadata.get("generated_pdf_route"),
            "source_document_bytes",
            "generation_available",
        ),
        (
            "dial_account_document_index",
            record.get("discovery_source_url"),
            "property_account_document_discovery",
            "index_available",
        ),
        (
            "retrieved_document_artifact",
            (
                record.get("source_url")
                if record.get("record_kind") == "laserfiche_document_artifact"
                else None
            ),
            "retrieved_source_document_bytes",
            record.get("retrieval_state"),
        ),
    )
    seen_representations: set[tuple[str, str]] = set()
    for kind, url, relationship, source_state in representation_candidates:
        source_url = _text(url)
        if not source_url or (kind, source_url) in seen_representations:
            continue
        seen_representations.add((kind, source_url))
        representations.append(
            {
                "kind": kind,
                "url": source_url,
                "relationship": relationship,
                "source_state": _text(source_state),
            }
        )

    created_at = _text(metadata.get("created_at") or record.get("created_at"))
    uploaded_at = _text(record.get("date_uploaded"))
    modified_at = _text(metadata.get("modified_at") or record.get("modified_at"))
    event_kind = (
        _text(metadata.get("record_kind"))
        if record.get("record_kind") == "laserfiche_document_artifact"
        else _text(record.get("record_kind"))
    ) or "development_document"
    return {
        **dict(record),
        "source_id": DESCHUTES_CDD_WEBLINK_SOURCE_ID,
        "source_url": (
            record.get("source_url")
            or metadata.get("source_url")
            or record.get("viewer_url")
            or metadata.get("viewer_url")
        ),
        "record_kind": event_kind,
        "native_event_id": document_id,
        "source_record_id": document_id,
        "event_type": (
            record.get("document_type")
            or metadata.get("document_category")
            or metadata.get("template_name")
            or "development_document"
        ),
        "description": (
            record.get("description")
            or metadata.get("description")
            or metadata.get("name")
            or record.get("name")
        ),
        "status": (
            record.get("retrieval_state")
            or metadata.get("retrieval_state")
            or "metadata_available"
        ),
        "status_category": "published_document",
        "address": {"raw": account_index.get("situs_address")},
        "people": [],
        "event_dates": {
            "submitted": {"utc_date": _date_prefix(uploaded_at or created_at)},
            "last_update": {"utc_date": _date_prefix(modified_at)},
        },
        "parcel_join_evidence": {
            "method": "published_dial_account_and_map_taxlot",
            "published_location": {
                "raw": map_taxlot,
                "normalized_candidate": _normalized_map_taxlot(map_taxlot),
            },
            "deschutes_dial_account_id": account_id,
            "laserfiche_entry_id": document_id,
        },
        "detail_representations": representations,
        "jurisdiction": {
            "country": "US",
            "state_code": "OR",
            "state_fips": "41",
            "county_name": "Deschutes County",
            "county_geoid": "41017",
        },
    }


def _upsert_deschutes_cdd_artifact(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve a retrieved Laserfiche representation as a document artifact."""

    document_id = _text(
        record.get("laserfiche_entry_id") or record.get("native_document_id")
    )
    if not document_id:
        raise PropertyIngestError("Deschutes CDD artifact lacks a Laserfiche entry ID")
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=DESCHUTES_CDD_WEBLINK_SOURCE_ID,
        source_native_id=document_id,
        record_kind="laserfiche_document_artifact",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    _upsert_jurisdiction_values(
        db,
        geoid="41017",
        name="Deschutes County, Oregon",
        state_code="OR",
        jurisdiction_type="county",
        parent_geoid="41",
    )
    digest = _text(record.get("sha256"))
    existing = db.execute(
        """
        SELECT artifact_id FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_document_id=?
          AND COALESCE(sha256, '')=COALESCE(?, '')
        """,
        (
            DESCHUTES_CDD_WEBLINK_SOURCE_ID,
            "41017",
            document_id,
            digest,
        ),
    ).fetchone()
    metadata = record.get("document_metadata")
    metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    raw_page_count = metadata.get("page_count")
    try:
        page_count = int(raw_page_count) if raw_page_count not in (None, "") else None
    except (TypeError, ValueError):
        page_count = None
    values = (
        digest,
        _text(record.get("media_type")),
        page_count,
        _text(record.get("local_path")),
        _text(record.get("source_url")),
        _text(record.get("retrieval_mode")) or "source_document_download",
        "official_county_document",
        "public",
        retrieved_at,
    )
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DESCHUTES_CDD_WEBLINK_SOURCE_ID,
                "41017",
                document_id,
                *values,
            ),
        )
        artifact_id = int(cursor.lastrowid)
    else:
        artifact_id = int(existing["artifact_id"])
        db.execute(
            """
            UPDATE document_artifact SET
                sha256=?, mime_type=?, page_count=?, storage_path=?,
                source_url=?, acquisition_method=?, rights_tier=?,
                access_state=?, acquired_at=?
            WHERE artifact_id=?
            """,
            (*values, artifact_id),
        )
    return {
        "artifact_id": artifact_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "native_document_id": document_id,
        "artifacts_upserted": 1,
    }


def _ingest_deschutes_cdd_document_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project account-linked CDD documents and retrieved representations."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    if record_kind not in {
        "development_document_reference",
        "laserfiche_development_document",
        "laserfiche_document_artifact",
    }:
        return {
            "projection_skipped": True,
            "reason": "record_kind_is_not_a_property_linked_document",
            "record_kind": record_kind,
        }

    projected = _deschutes_cdd_document_projection(record)
    event = _ingest_property_event_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        expected_geoid="41017",
        parcel_alias_source_id=DESCHUTES_PROPERTY_SOURCE_ID,
    )
    if record_kind != "laserfiche_document_artifact":
        return event
    artifact = _upsert_deschutes_cdd_artifact(
        db,
        envelope=envelope,
        record=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    return {**event, **artifact}


def _ingest_oregon_linn_josephine_klamath_assessor_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one county field map while preserving its complete native row."""

    projected = dict(record)
    native_id = _text(record.get("native_id"))
    if not native_id:
        raise PropertyIngestError(f"{source_id} record lacks native_id")
    projected["native_parcel_id"] = native_id
    projected["snapshot_complete"] = True

    county = _mapping(record.get("county"), "record.county")
    projected["jurisdiction"] = {
        "state_code": _text(county.get("state")) or "OR",
        "state_fips": "41",
        "county_name": _text(county.get("name")),
        "county_geoid": _text(county.get("geoid")),
    }
    provenance = record.get("provenance")
    if isinstance(provenance, Mapping):
        projected["source_url"] = provenance.get("layer_url")
        projected["response_schema_fingerprint"] = provenance.get("schema_fingerprint")

    alternate_ids: list[str] = []
    for value in [
        *record.get("assessment_account_ids", []),
        *record.get("map_taxlot_ids", []),
        *(
            record.get("native_identity", {}).values()
            if isinstance(record.get("native_identity"), Mapping)
            else []
        ),
    ]:
        normalized = _text(value)
        if normalized and normalized != native_id and normalized not in alternate_ids:
            alternate_ids.append(normalized)
    projected["alternate_parcel_ids"] = alternate_ids

    source_assessment = record.get("assessment")
    property_values = record.get("property")
    if isinstance(source_assessment, Mapping):
        classification = (
            property_values.get("classification")
            if isinstance(property_values, Mapping)
            else None
        )
        classification_value = None
        if isinstance(classification, Mapping):
            classification_value = next(
                (
                    f"{field_name}:{value}"
                    for field_name, value in classification.items()
                    if _text(value)
                ),
                None,
            )
        projected["assessment"] = {
            **dict(source_assessment),
            "land_value": source_assessment.get("market_or_appraised_land"),
            "improvement_value": source_assessment.get(
                "market_or_appraised_improvements"
            ),
            "parcel_value": source_assessment.get("market_or_appraised_total"),
            "market_value": source_assessment.get("market_or_appraised_total"),
            "assessed_value": source_assessment.get("assessed_value"),
            "assessment_class": classification_value,
        }

    sale = record.get("sale")
    if isinstance(sale, Mapping):
        sale_date = sale.get("date")
        normalized_sale_date = (
            sale_date.get("date_iso") if isinstance(sale_date, Mapping) else None
        )
        if any(
            value not in (None, "")
            for value in (
                normalized_sale_date,
                sale.get("price"),
                sale.get("instrument"),
            )
        ):
            projected["last_sale"] = {
                "sale_date": normalized_sale_date,
                "sale_price": sale.get("price"),
                "source_document_ref": sale.get("instrument"),
                "qualification_code": (sale.get("sale_type") or sale.get("deed_type")),
                "scope": sale.get("scope"),
            }

    update_evidence = record.get("update_evidence")
    if isinstance(update_evidence, Mapping):
        update_values = [
            _text(value.get("normalized"))
            for value in update_evidence.get("observations", [])
            if isinstance(value, Mapping) and _text(value.get("normalized"))
        ]
        if update_values:
            projected["source_last_updated"] = max(update_values)

    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    parcel_id = int(result["parcel_id"])
    effective_from = (
        _text(projected.get("source_last_updated"))
        or _text(envelope.get("retrieved_at"))
        or ""
    )
    typed_aliases = [
        *(
            ("assessment_account", value)
            for value in record.get("assessment_account_ids", [])
        ),
        *(("map_taxlot", value) for value in record.get("map_taxlot_ids", [])),
        *(
            (
                "map_taxlot_normalized",
                _normalized_map_taxlot(value),
            )
            for value in record.get("map_taxlot_ids", [])
        ),
    ]
    typed_aliases_inserted = 0
    seen: set[tuple[str, str]] = set()
    for alias_type, value in typed_aliases:
        alias_value = _text(value)
        if not alias_value or (alias_type, alias_value) in seen:
            continue
        seen.add((alias_type, alias_value))
        typed_aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=effective_from,
        )
    result["typed_aliases_inserted"] = typed_aliases_inserted
    return result


def _accela_labeled_values(record: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field_name in ("record_details", "additional_information"):
        raw_values = record.get(field_name, [])
        if isinstance(raw_values, list):
            for value in raw_values:
                if not isinstance(value, Mapping):
                    continue
                label = _text(value.get("label"))
                if label:
                    values[label.casefold()] = value.get("value")
    sections = record.get("application_information", [])
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            fields = section.get("fields", [])
            if not isinstance(fields, list):
                continue
            for value in fields:
                if not isinstance(value, Mapping):
                    continue
                label = _text(value.get("label"))
                if label:
                    values[label.casefold()] = value.get("value")
    return values


def _ingest_jackson_accela_detail_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project a fetched permit detail and retain each fetched representation."""

    record_kind = _text(record.get("record_kind"))
    if record_kind not in {
        "building_permit_detail",
        "land_use_permit_detail",
    }:
        return {
            "projection_skipped": True,
            "reason": "record_kind_is_not_a_permit_detail",
            "record_kind": record_kind,
        }

    projected = dict(record)
    native_event_id = _text(record.get("native_record_id"))
    record_key = record.get("record_key")
    source_record_id = (
        _text(record_key.get("compact")) if isinstance(record_key, Mapping) else None
    )
    if not native_event_id or not source_record_id:
        raise PropertyIngestError(
            "Jackson Accela detail requires native_record_id and compact CAP key"
        )
    projected["native_event_id"] = native_event_id
    projected["source_record_id"] = source_record_id
    projected["event_type"] = record.get("record_type")
    projected["description"] = record.get("project_description")
    projected["address"] = {"raw": record.get("work_location")}
    projected["jurisdiction"] = {
        "state_code": "OR",
        "state_fips": "41",
        "county_name": "Jackson County",
        "county_geoid": "41029",
    }

    source_urls = record.get("source_urls")
    if isinstance(source_urls, Mapping):
        projected["source_url"] = source_urls.get("record_detail")

    participants = record.get("participants")
    projected["people"] = [
        {
            "raw_name": value,
            "role": role,
            "assertion_type": "published_permit_participant",
        }
        for role, value in (
            participants.items() if isinstance(participants, Mapping) else []
        )
        if _text(value)
    ]

    parcels = record.get("parcels", [])
    primary_parcel = (
        parcels[0]
        if isinstance(parcels, list) and parcels and isinstance(parcels[0], Mapping)
        else {}
    )
    published_parcel = _text(primary_parcel.get("parcel_number"))
    projected["parcel_join_evidence"] = {
        "method": "published_accela_parcel_number_candidate",
        "published_location": {
            "raw": published_parcel,
            "normalized_candidate": _normalized_map_taxlot(published_parcel),
        },
        "source_record_id": source_record_id,
    }

    representation_rows: list[dict[str, Any]] = []
    representations = record.get("representations")
    if isinstance(representations, Mapping):
        for representation_kind, value in representations.items():
            if not isinstance(value, Mapping):
                continue
            source_url = _text(value.get("response_url") or value.get("request_url"))
            if not source_url:
                continue
            representation_rows.append(
                {
                    **dict(value),
                    "kind": _text(value.get("kind")) or str(representation_kind),
                    "url": source_url,
                    "relationship": "fetched_with_permit_detail",
                    "source_state": "fetched_representation",
                }
            )
    documents = record.get("documents", [])
    if isinstance(documents, list):
        for document in documents:
            if not isinstance(document, Mapping):
                continue
            source_url = _text(document.get("document_detail_url"))
            if source_url:
                representation_rows.append(
                    {
                        **dict(document),
                        "kind": "listed_document_detail",
                        "url": source_url,
                        "relationship": "listed_on_attachment_representation",
                        "source_state": "metadata_listed",
                    }
                )
    projected["detail_representations"] = representation_rows

    labeled_values = _accela_labeled_values(record)
    submitted = next(
        (
            labeled_values[label]
            for label in (
                "application date",
                "date received",
                "file date",
                "submitted date",
            )
            if _text(labeled_values.get(label))
        ),
        None,
    )
    approved = next(
        (
            labeled_values[label]
            for label in (
                "decision is final",
                "approval date",
                "issued date",
            )
            if _text(labeled_values.get(label))
        ),
        None,
    )
    projected["event_dates"] = {
        "submitted": {"utc_date": _date_prefix(submitted)},
        "approved": {"utc_date": _date_prefix(approved)},
    }
    estimated_cost = next(
        (
            labeled_values[label]
            for label in ("estimated cost", "job value", "valuation")
            if _text(labeled_values.get(label))
        ),
        None,
    )
    estimated_cost_text = _text(estimated_cost)
    if estimated_cost_text:
        negative = estimated_cost_text.startswith("(") and estimated_cost_text.endswith(
            ")"
        )
        estimated_cost_text = (
            estimated_cost_text.strip("()").replace("$", "").replace(",", "")
        )
        if negative:
            estimated_cost_text = f"-{estimated_cost_text}"
    projected["permit"] = {"estimated_cost": estimated_cost_text}

    result = _ingest_jackson_property_event_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    result["documents_listed"] = len(documents) if isinstance(documents, list) else 0
    result["fetched_representations_preserved"] = (
        len(representations) if isinstance(representations, Mapping) else 0
    )
    return result


def _ingest_oregon_helion_property_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one PSO account while retaining its full source observation."""

    projected = dict(record)

    for address_field in ("situs_address", "mailing_address"):
        address = projected.get(address_field)
        if isinstance(address, Mapping):
            normalized_address = dict(address)
            normalized_address.setdefault(
                "raw",
                _text(address.get("raw_address")),
            )
            projected[address_field] = normalized_address

    aliases = [
        value for value in projected.get("alternate_parcel_ids", []) if _text(value)
    ]
    for value in (
        projected.get("native_account_id"),
        (
            projected.get("tax_state", {}).get("tax_account_id")
            if isinstance(projected.get("tax_state"), Mapping)
            else None
        ),
    ):
        if _text(value) and _text(value) not in aliases:
            aliases.append(value)
    projected["alternate_parcel_ids"] = aliases

    assessment_class = None
    physical = projected.get("physical_characteristics")
    if isinstance(physical, Mapping):
        assessment_class = _text(physical.get("property_class"))

    def normalize_assessment(value: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(value)
        normalized["land_value"] = value.get("land_real_market_value")
        normalized["improvement_value"] = value.get("improvement_real_market_value")
        normalized["parcel_value"] = value.get("real_market_value")
        normalized["market_value"] = value.get("real_market_value")
        normalized["assessment_class"] = (
            value.get("assessment_class") or assessment_class
        )
        return normalized

    current = projected.get("assessment")
    normalized_current = (
        normalize_assessment(current) if isinstance(current, Mapping) else None
    )
    if normalized_current is not None:
        projected["assessment"] = normalized_current

    history = projected.get("assessment_history")
    if isinstance(history, list):
        normalized_history: list[dict[str, Any]] = []
        current_year = (
            _text(normalized_current.get("tax_year"))
            if normalized_current is not None
            else None
        )
        for value in history:
            if not isinstance(value, Mapping):
                continue
            normalized = normalize_assessment(value)
            if current_year and _text(normalized.get("tax_year")) == current_year:
                normalized = {
                    **normalized_current,
                    **{
                        key: item
                        for key, item in normalized.items()
                        if item not in (None, "")
                    },
                }
            normalized_history.append(normalized)
        projected["assessment_history"] = normalized_history

    sales = projected.get("sale_history")
    if isinstance(sales, list):
        projected["sale_history"] = [
            {
                **sale,
                "source_document_ref": (
                    sale.get("source_document_ref") or sale.get("document_id")
                ),
                "qualification_code": (
                    sale.get("qualification_code") or sale.get("condition_code")
                ),
            }
            for sale in sales
            if isinstance(sale, Mapping)
        ]

    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    result["tax_state_preserved"] = isinstance(
        projected.get("tax_state"),
        Mapping,
    )
    result["improvement_records_preserved"] = len(projected.get("improvements") or [])
    return result


def _ingest_benton_taxlot_owner_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one Benton owner-party row without changing its source grain."""

    if record.get("record_kind") != "taxlot_owner_party":
        raise PropertyIngestError(
            "Benton TaxlotOwners ingestion requires taxlot_owner_party records"
        )
    projected = dict(record)
    native_parcel_id = _text(
        record.get("map_taxlot")
        or record.get("account_number")
        or record.get("or_taxlot")
        or record.get("object_id")
    )
    if not native_parcel_id:
        raise PropertyIngestError(
            "Benton taxlot owner-party record lacks map taxlot, account, "
            "ORTaxlot, and object ID"
        )
    projected["native_parcel_id"] = native_parcel_id
    projected["jurisdiction"] = {
        "state_code": "OR",
        "state_fips": "41",
        "county_name": "Benton County",
        "county_geoid": "41003",
    }
    projected["alternate_parcel_ids"] = [
        value
        for value in (
            record.get("account_number"),
            record.get("map_taxlot"),
            record.get("or_taxlot"),
            record.get("map_number"),
        )
        if _text(value) and _text(value) != native_parcel_id
    ]
    owner = record.get("owner_party")
    projected["owners"] = (
        [dict(owner)]
        if isinstance(owner, Mapping) and _text(owner.get("raw_name"))
        else []
    )
    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="taxlot_owner_party",
    )

    parcel_id = int(result["parcel_id"])
    effective_from = _text(envelope.get("retrieved_at")) or ""
    typed_aliases = (
        ("account_number", record.get("account_number")),
        ("map_taxlot", record.get("map_taxlot")),
        ("or_taxlot", record.get("or_taxlot")),
        ("map_number", record.get("map_number")),
        ("arcgis_object_id", record.get("object_id")),
    )
    aliases_inserted = 0
    seen: set[tuple[str, str]] = set()
    for alias_type, raw_value in typed_aliases:
        value = _text(raw_value)
        if not value or (alias_type, value) in seen:
            continue
        seen.add((alias_type, value))
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=value,
            source_id=source_id,
            effective_from=effective_from,
        )
    result["typed_aliases_inserted"] = aliases_inserted
    result["source_record_kind"] = "taxlot_owner_party"
    return result


def _normalize_lincoln_instrument_number(value: Any) -> str | None:
    """Return the shared PropertyWeb/Helion instrument-number representation."""

    text = _text(value)
    if not text:
        return None
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) < 9 or len(digits) > 12 or digits[:2] not in {"19", "20"}:
        return text
    return f"{digits[:4]}-{digits[4:].zfill(6)}"


def _upsert_tax_account_projection(
    db,
    *,
    parcel_id: int,
    source_id: str,
    tax_year: Any,
    event_type: str,
    event_date: Any,
    amount: Any,
    status: Any,
    native_event_id: str,
    observation_id: int,
    raw: Mapping[str, Any],
) -> int:
    """Project one source-native tax event without changing its meaning."""

    normalized_date = _text(event_date) or ""
    db.execute(
        """
        INSERT INTO tax_account_event(
            parcel_id, source_id, tax_year, event_type, event_date,
            amount_minor, currency, status, native_event_id,
            observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(
            parcel_id, source_id, event_type, event_date, native_event_id
        ) DO UPDATE SET
            tax_year=excluded.tax_year,
            amount_minor=excluded.amount_minor,
            status=excluded.status,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            parcel_id,
            source_id,
            _text(tax_year),
            event_type,
            normalized_date,
            _minor_units(amount),
            _text(status),
            native_event_id,
            observation_id,
            canonical_json(raw),
        ),
    )
    return 1


def _link_lincoln_propertyweb_sale(
    db,
    *,
    parcel_id: int,
    instrument_number: Any,
) -> int:
    """Link an exact PropertyWeb sale reference to its Helion instrument."""

    normalized = _normalize_lincoln_instrument_number(instrument_number)
    if not normalized:
        return 0
    instrument = db.execute(
        """
        SELECT instrument_id, legal_description_raw
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid='41041'
          AND native_document_id=?
        """,
        (LINCOLN_HELION_RECORDER_SOURCE_ID, normalized),
    ).fetchone()
    if instrument is None:
        return 0
    instrument_id = int(instrument["instrument_id"])
    db.execute(
        """
        UPDATE sale_event
        SET instrument_id=?
        WHERE parcel_id=? AND source_id=? AND native_sale_id=?
        """,
        (
            instrument_id,
            parcel_id,
            LINCOLN_PROPERTYWEB_SOURCE_ID,
            normalized,
        ),
    )
    db.execute(
        """
        INSERT INTO instrument_parcel(
            instrument_id, parcel_id, link_method, link_confidence,
            legal_description_raw
        ) VALUES (?, ?, 'propertyweb_sale_instrument', 1.0, ?)
        ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
            link_method=excluded.link_method,
            link_confidence=excluded.link_confidence,
            legal_description_raw=COALESCE(
                excluded.legal_description_raw,
                instrument_parcel.legal_description_raw
            )
        """,
        (instrument_id, parcel_id, instrument["legal_description_raw"]),
    )
    return 1


def _link_lincoln_recorder_instrument_to_propertyweb(
    db,
    *,
    instrument_id: int,
    instrument_number: Any,
    legal_description_raw: Any,
) -> int:
    """Resolve earlier PropertyWeb sale rows when the recorder arrives later."""

    normalized = _normalize_lincoln_instrument_number(instrument_number)
    if not normalized:
        return 0
    rows = db.execute(
        """
        SELECT DISTINCT parcel_id
        FROM sale_event
        WHERE source_id=? AND native_sale_id=?
        """,
        (LINCOLN_PROPERTYWEB_SOURCE_ID, normalized),
    ).fetchall()
    for row in rows:
        parcel_id = int(row["parcel_id"])
        db.execute(
            """
            UPDATE sale_event
            SET instrument_id=?
            WHERE parcel_id=? AND source_id=? AND native_sale_id=?
            """,
            (
                instrument_id,
                parcel_id,
                LINCOLN_PROPERTYWEB_SOURCE_ID,
                normalized,
            ),
        )
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, 'propertyweb_sale_instrument', 1.0, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=COALESCE(
                    excluded.legal_description_raw,
                    instrument_parcel.legal_description_raw
                )
            """,
            (instrument_id, parcel_id, _text(legal_description_raw)),
        )
    return len(rows)


def _lincoln_propertyweb_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project Lincoln PropertyWeb search/detail rows at their native grain."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    if record_kind not in {
        "property_account_search_result",
        "property_account_detail",
    }:
        return {
            "projection_skipped": True,
            "reason": "non_account_propertyweb_record",
            "record_kind": record_kind,
        }
    property_quick_ref = _text(record.get("property_quick_ref"))
    if not property_quick_ref:
        raise PropertyIngestError(
            "Lincoln PropertyWeb account record lacks property_quick_ref"
        )

    projected = dict(record)
    projected["native_parcel_id"] = property_quick_ref
    projected["jurisdiction"] = {
        "state_code": "OR",
        "state_fips": "41",
        "county_name": "Lincoln County",
        "county_geoid": "41041",
    }
    projected["record_view"] = (
        "detail" if record_kind == "property_account_detail" else "search_result"
    )
    projected["snapshot_complete"] = record_kind == "property_account_detail"
    if _text(record.get("effective_date")):
        projected["source_last_updated"] = record.get("effective_date")

    alias_values = [
        record.get("party_quick_ref"),
        record.get("property_id"),
        record.get("property_owner_id"),
        record.get("party_id"),
        record.get("legacy_id"),
        record.get("property_number"),
        record.get("alternate_account_number"),
        record.get("custom_id"),
        record.get("map_number"),
        record.get("parcel_id"),
    ]
    projected["alternate_parcel_ids"] = [
        value
        for value in alias_values
        if _text(value) and _text(value) != property_quick_ref
    ]
    owner_name = _text(record.get("owner_name"))
    projected["owners"] = (
        [
            {
                "raw_name": owner_name,
                "role": "assessment_roll_owner",
                "confidence": "high",
            }
        ]
        if owner_name
        else []
    )
    situs = _text(record.get("situs_address"))
    mailing_lines = record.get("mailing_address_lines")
    mailing = (
        ", ".join(value for raw_value in mailing_lines if (value := _text(raw_value)))
        if isinstance(mailing_lines, list)
        else _text(record.get("owner_full_address"))
    )
    projected["situs_address"] = {"raw": situs} if situs else {}
    projected["mailing_address"] = {"raw": mailing} if mailing else {}

    value_history = record.get("value_history")
    if isinstance(value_history, list):
        projected["assessment_history"] = [
            {
                **dict(value),
                "land_value": value.get("land_value"),
                "improvement_value": value.get("improvement_value"),
                "parcel_value": value.get("real_market_value"),
                "market_value": value.get("real_market_value"),
                "assessed_value": value.get("assessed_value"),
            }
            for value in value_history
            if isinstance(value, Mapping)
        ]
    elif any(
        record.get(field) not in (None, "")
        for field in ("property_value", "market_value", "assessed_value")
    ):
        projected["assessment"] = {
            "tax_year": record.get("property_value_tax_year") or record.get("tax_year"),
            "parcel_value": record.get("property_value"),
            "market_value": record.get("market_value"),
            "assessed_value": record.get("assessed_value"),
            "assessment_class": record.get("property_class"),
        }

    sales = record.get("sales_history")
    sale_instruments: list[str] = []
    if isinstance(sales, list):
        projected_sales = []
        for raw_sale in sales:
            if not isinstance(raw_sale, Mapping):
                continue
            join_candidate = raw_sale.get("recorder_join_candidate")
            normalized_instrument = (
                _normalize_lincoln_instrument_number(
                    join_candidate.get("instrument_number")
                )
                if isinstance(join_candidate, Mapping)
                else _normalize_lincoln_instrument_number(
                    raw_sale.get("instrument_number")
                )
            )
            if normalized_instrument:
                sale_instruments.append(normalized_instrument)
            projected_sales.append(
                {
                    **dict(raw_sale),
                    "source_document_ref": normalized_instrument
                    or raw_sale.get("instrument_number"),
                    "consideration": raw_sale.get("sale_price"),
                }
            )
        projected["sale_history"] = projected_sales

    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind=record_kind,
    )
    parcel_id = int(result["parcel_id"])
    effective_from = (
        _text(record.get("effective_date")) or _text(envelope.get("retrieved_at")) or ""
    )
    typed_aliases: list[tuple[str, Any]] = [
        ("property_quick_ref", property_quick_ref),
        ("propertyweb_property_quick_ref", property_quick_ref),
        ("party_quick_ref", record.get("party_quick_ref")),
        ("property_id", record.get("property_id")),
        ("property_owner_id", record.get("property_owner_id")),
        ("party_id", record.get("party_id")),
        ("legacy_id", record.get("legacy_id")),
        ("property_number", record.get("property_number")),
        ("alternate_account_number", record.get("alternate_account_number")),
        ("custom_id", record.get("custom_id")),
        ("map_number", record.get("map_number")),
        ("lincoln_wfs_parcel_id", record.get("map_number")),
        ("parcel_id", record.get("parcel_id")),
    ]
    typed_aliases.extend(
        ("lincoln_recorder_instrument", value) for value in sale_instruments
    )
    aliases_inserted = 0
    seen_aliases: set[tuple[str, str]] = set()
    for alias_type, raw_value in typed_aliases:
        value = _text(raw_value)
        if not value or (alias_type, value) in seen_aliases:
            continue
        seen_aliases.add((alias_type, value))
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=value,
            source_id=source_id,
            effective_from=effective_from,
        )

    observation_id = int(result["observation_id"])
    tax_events_upserted = 0
    bills = record.get("bills")
    if isinstance(bills, list):
        for index, raw_bill in enumerate(bills):
            if not isinstance(raw_bill, Mapping):
                continue
            tax_year = _text(raw_bill.get("tax_year"))
            total_owed = raw_bill.get("total_owed")
            status = (
                "paid"
                if total_owed == 0 and _text(raw_bill.get("date_paid"))
                else "balance_due"
                if total_owed not in (None, "", 0)
                else "published"
            )
            tax_events_upserted += _upsert_tax_account_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                tax_year=tax_year,
                event_type="tax_bill",
                event_date=raw_bill.get("date_paid"),
                amount=raw_bill.get("total_billed"),
                status=status,
                native_event_id=f"bill:{tax_year or index}",
                observation_id=observation_id,
                raw=raw_bill,
            )
    payments = record.get("payment_history")
    if isinstance(payments, list):
        for index, raw_payment in enumerate(payments):
            if not isinstance(raw_payment, Mapping):
                continue
            native_payment_id = (
                _text(
                    raw_payment.get("transaction_id")
                    or raw_payment.get("receipt_number")
                )
                or f"payment:{index}:{sha256_fingerprint(raw_payment)[:16]}"
            )
            tax_events_upserted += _upsert_tax_account_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                tax_year=raw_payment.get("tax_year"),
                event_type="tax_payment",
                event_date=raw_payment.get("transaction_date"),
                amount=raw_payment.get("payment_amount"),
                status="paid",
                native_event_id=native_payment_id,
                observation_id=observation_id,
                raw=raw_payment,
            )
    due = record.get("tax_due_summary")
    if isinstance(due, Mapping) and due.get("total_due") not in (None, ""):
        due_date = _text(due.get("effective_date"))
        tax_events_upserted += _upsert_tax_account_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=record.get("tax_year"),
            event_type="tax_balance",
            event_date=due_date,
            amount=due.get("total_due"),
            status="balance_due" if due.get("total_due") else "paid",
            native_event_id=f"balance:{due_date or 'current'}",
            observation_id=observation_id,
            raw=due,
        )

    instrument_links_resolved = sum(
        _link_lincoln_propertyweb_sale(
            db,
            parcel_id=parcel_id,
            instrument_number=instrument,
        )
        for instrument in dict.fromkeys(sale_instruments)
    )
    result["typed_aliases_inserted"] = aliases_inserted
    result["tax_events_upserted"] = tax_events_upserted
    result["instrument_links_resolved"] = instrument_links_resolved
    result["document_representations_preserved"] = len(
        record.get("document_representations") or []
    )
    return result


def _lincoln_taxlot_wfs_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one WFS feature while retaining its feature-level identity."""

    _assert_record_source(record, source_id)
    if record.get("record_kind") != "taxlot_owner_geometry":
        return {
            "projection_skipped": True,
            "reason": "non_taxlot_wfs_record",
            "record_kind": _text(record.get("record_kind")),
        }
    native_identity = record.get("native_identity")
    if not isinstance(native_identity, Mapping):
        raise PropertyIngestError("Lincoln WFS record lacks native_identity")
    native_id = _text(
        record.get("native_id")
        or record.get("source_record_id")
        or native_identity.get("ogc_fid")
    )
    if not native_id:
        raise PropertyIngestError("Lincoln WFS record lacks its ogc_fid identity")

    projected = dict(record)
    projected["native_parcel_id"] = native_id
    projected["jurisdiction"] = {
        "state_code": "OR",
        "state_fips": "41",
        "county_name": "Lincoln County",
        "county_geoid": "41041",
    }
    projected["snapshot_complete"] = True
    projected["record_view"] = "full_detail"
    projected["alternate_parcel_ids"] = [
        value
        for value in (
            native_identity.get("propertyid"),
            native_identity.get("parcelid"),
            native_identity.get("imagekey"),
        )
        if _text(value) and _text(value) != native_id
    ]
    mailing = record.get("mailing_address")
    if isinstance(mailing, Mapping):
        projected["mailing_address"] = {
            **dict(mailing),
            "raw": mailing.get("formatted"),
        }
    situs = record.get("situs_address")
    if isinstance(situs, Mapping):
        projected["situs_address"] = {
            **dict(situs),
            "raw": situs.get("raw"),
        }
    if isinstance(record.get("geometry"), Mapping):
        projected["geometry_format"] = "geojson"
        projected["geometry_crs"] = record.get("geometry_crs")
        projected["geometry_disclaimer"] = (
            "County GIS taxlot geometry; source cadastral and survey records "
            "remain the boundary authority."
        )

    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="taxlot_owner_geometry",
    )
    parcel_id = int(result["parcel_id"])
    effective_from = _text(envelope.get("retrieved_at")) or ""
    typed_aliases = (
        ("wfs_ogc_fid", native_identity.get("ogc_fid")),
        ("property_account_id", native_identity.get("propertyid")),
        ("propertyweb_property_quick_ref", native_identity.get("propertyid")),
        ("map_number", native_identity.get("parcelid")),
        ("propertyweb_map_number", native_identity.get("parcelid")),
        ("image_key", native_identity.get("imagekey")),
    )
    aliases_inserted = 0
    seen_aliases: set[tuple[str, str]] = set()
    for alias_type, raw_value in typed_aliases:
        value = _text(raw_value)
        if not value or (alias_type, value) in seen_aliases:
            continue
        seen_aliases.add((alias_type, value))
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=value,
            source_id=source_id,
            effective_from=effective_from,
        )
    result["typed_aliases_inserted"] = aliases_inserted
    result["join_keys_preserved"] = {
        "propertyweb_property_quick_ref": _text(native_identity.get("propertyid")),
        "propertyweb_map_number": _text(native_identity.get("parcelid")),
    }
    return result


def _ingest_benton_artifact_metadata(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve one bulk release or assessment-map row as its own observation."""

    _assert_record_source(record, source_id)
    expected_kind = (
        "bulk_release"
        if source_id == BENTON_ASSESSMENT_BULK_SOURCE_ID
        else "assessment_map"
    )
    if record.get("record_kind") != expected_kind:
        raise PropertyIngestError(
            f"{source_id} ingestion requires {expected_kind} records"
        )
    if expected_kind == "bulk_release":
        manifest = _mapping(record.get("manifest"), "record.manifest")
        release = _mapping(manifest.get("release"), "record.manifest.release")
        native_id = _text(release.get("release_id"))
        source_url = _text(
            manifest.get("metadata", {}).get("source_directory")
            if isinstance(manifest.get("metadata"), Mapping)
            else None
        )
    else:
        native_id = _text(record.get("filename") or record.get("map_number"))
        source_url = _text(record.get("url"))
    if not native_id:
        raise PropertyIngestError(
            f"{expected_kind} record lacks a stable native identifier"
        )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_id,
        record_kind=expected_kind,
        query_fingerprint=query_fingerprint,
        source_url=source_url or _record_url(envelope),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return {
        "projection_skipped": True,
        "reason": "artifact_metadata_observation",
        "record_kind": expected_kind,
        "source_native_id": native_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "metadata_observation_inserted": True,
    }


def _lane_property_jurisdiction(db) -> str:
    return _upsert_jurisdiction_values(
        db,
        geoid="41039",
        name="Lane County, Oregon",
        state_code="OR",
        jurisdiction_type="county",
        parent_geoid="41",
    )


def _lane_property_source_occurrence_id(
    record: Mapping[str, Any],
) -> str:
    return (
        _text(record.get("source_record_id"))
        or _text(record.get("tax_map_document_id"))
        or _text(record.get("account_number"))
        or _text(record.get("canonical_ref"))
        or sha256_fingerprint(record)
    )


def _lane_property_observation(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> tuple[int, str, str, str, str]:
    _assert_record_source(record, source_id)
    _lane_property_jurisdiction(db)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(
        envelope
    )
    record_kind = _text(record.get("record_kind")) or "source_record"
    source_occurrence_id = _lane_property_source_occurrence_id(record)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_occurrence_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return (
        observation_id,
        record_hash,
        retrieved_at,
        record_kind,
        source_occurrence_id,
    )


def _lane_property_parcel(
    db,
    *,
    source_id: str,
    map_taxlot: str | None,
    account_number: str | None,
    observation_id: int,
    retrieved_at: str,
    record: Mapping[str, Any],
) -> tuple[int, str, bool]:
    """Reuse an exact Lane assessor/account/map locator before making a shell."""

    join_values = list(
        dict.fromkeys(
            value for value in (map_taxlot, account_number) if value
        )
    )
    if not join_values:
        raise PropertyIngestError(
            "Lane property record lacks an exact map-taxlot or account join"
        )
    placeholders = ", ".join("?" for _ in join_values)
    row = db.execute(
        f"""
        SELECT DISTINCT p.parcel_id, p.source_id
        FROM parcel_snapshot p
        LEFT JOIN parcel_alias pa ON pa.parcel_id=p.parcel_id
        WHERE p.jurisdiction_geoid='41039'
          AND p.source_id IN (?, ?, ?)
          AND (
            p.native_parcel_id IN ({placeholders})
            OR pa.alias_value IN ({placeholders})
          )
        ORDER BY CASE p.source_id
            WHEN ? THEN 0
            WHEN ? THEN 1
            ELSE 2
        END, p.parcel_id
        LIMIT 1
        """,
        (
            LANE_PARCELS_SOURCE_ID,
            LANE_PROPERTY_ACCOUNT_SOURCE_ID,
            LANE_TAX_MAP_SOURCE_ID,
            *join_values,
            *join_values,
            LANE_PARCELS_SOURCE_ID,
            LANE_PROPERTY_ACCOUNT_SOURCE_ID,
        ),
    ).fetchone()
    if row is not None:
        return int(row["parcel_id"]), str(row["source_id"]), False

    native_parcel_id = map_taxlot or account_number
    assert native_parcel_id is not None
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid="41039",
        native_parcel_id=native_parcel_id,
        roll_year="",
        effective_from=retrieved_at,
        source_good_through=None,
        observation_id=observation_id,
        record={
            **dict(record),
            "parcel_shell": {
                "state": "exact_lane_account_or_tax_map_join",
                "source_id": source_id,
                "map_taxlot": map_taxlot,
                "account_number": account_number,
                "candidate_canonical_source_id": LANE_PARCELS_SOURCE_ID,
            },
        },
    )
    return parcel_id, source_id, True


def _lane_property_aliases(
    db,
    *,
    parcel_id: int,
    source_id: str,
    map_taxlot: str | None,
    account_number: str | None,
    effective_from: str,
) -> int:
    aliases = _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="map_taxlot",
        alias_value=map_taxlot,
        source_id=source_id,
        effective_from=effective_from,
    )
    aliases += _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="assessment_account",
        alias_value=account_number,
        source_id=source_id,
        effective_from=effective_from,
    )
    return aliases


def _lane_account_label_projections(
    db,
    *,
    parcel_id: int,
    source_id: str,
    record: Mapping[str, Any],
    observation_id: int,
    retrieved_at: str,
) -> tuple[int, int]:
    default_evidence = _text(record.get("evidence_ref"))
    observations = record.get("search_index_observations")
    search_observations = (
        [value for value in observations if isinstance(value, Mapping)]
        if isinstance(observations, list)
        else [record]
    )
    owners_upserted = 0
    seen_owner_names: set[str] = set()
    for observation in search_observations:
        raw_name = _text(observation.get("owner_index_name"))
        if not raw_name or raw_name in seen_owner_names:
            continue
        seen_owner_names.add(raw_name)
        owners_upserted += _upsert_assessor_owner(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            raw_name=raw_name,
            effective_from=retrieved_at,
            confidence="confirmed",
            observation_id=observation_id,
            evidence_ref=(
                _text(observation.get("evidence_ref"))
                or default_evidence
                or ""
            ),
        )
    if not owners_upserted:
        owner_values = record.get("owner_index_names")
        if not isinstance(owner_values, list):
            owner_values = [record.get("owner_index_name")]
        for owner_value in owner_values:
            raw_name = _text(owner_value)
            if not raw_name or raw_name in seen_owner_names:
                continue
            seen_owner_names.add(raw_name)
            owners_upserted += _upsert_assessor_owner(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                raw_name=raw_name,
                effective_from=retrieved_at,
                confidence="confirmed",
                observation_id=observation_id,
                evidence_ref=default_evidence or "",
            )

    taxpayer_values = record.get("taxpayer_names")
    if not isinstance(taxpayer_values, list):
        taxpayer_values = [record.get("taxpayer_name")]
    taxpayers_upserted = 0
    seen_taxpayer_names: set[str] = set()
    for taxpayer_value in taxpayer_values:
        raw_name = _text(taxpayer_value)
        if not raw_name or raw_name in seen_taxpayer_names:
            continue
        seen_taxpayer_names.add(raw_name)
        taxpayers_upserted += _upsert_tax_account_owner(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            raw_name=raw_name,
            effective_from=retrieved_at,
            observation_id=observation_id,
            evidence_ref=default_evidence,
        )
    return owners_upserted, taxpayers_upserted


def _ingest_lane_property_account_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project account labels, values, and receipts without implying title."""

    (
        observation_id,
        record_hash,
        retrieved_at,
        record_kind,
        source_occurrence_id,
    ) = _lane_property_observation(
        db,
        envelope=envelope,
        record=record,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    if record_kind not in {
        "property_account_search_index",
        "property_account_detail",
    }:
        return {
            "projection_skipped": True,
            "reason": "lane_account_metadata_or_probe_observation",
            "record_kind": record_kind,
            "source_occurrence_id": source_occurrence_id,
            "observation_id": observation_id,
            "record_sha256": record_hash,
        }

    account_number = _text(record.get("account_number"))
    if not account_number:
        raise PropertyIngestError("Lane property-account record lacks account number")
    map_taxlot = _text(record.get("map_taxlot"))
    parcel_id, anchor_source_id, placeholder_created = _lane_property_parcel(
        db,
        source_id=source_id,
        map_taxlot=map_taxlot,
        account_number=account_number,
        observation_id=observation_id,
        retrieved_at=retrieved_at,
        record=record,
    )
    aliases_inserted = _lane_property_aliases(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        map_taxlot=map_taxlot,
        account_number=account_number,
        effective_from=retrieved_at,
    )
    owners_upserted, taxpayers_upserted = _lane_account_label_projections(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        record=record,
        observation_id=observation_id,
        retrieved_at=retrieved_at,
    )
    addresses_inserted = 0
    for role, value in (
        ("situs", record.get("situs_address")),
        ("mailing", record.get("mailing_address")),
    ):
        raw_address = _text(value)
        if raw_address:
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role=role,
                    address={"raw": raw_address},
                    effective_from=retrieved_at,
                )
            )

    assessments_upserted = 0
    valuation_history = record.get("valuation_history")
    if isinstance(valuation_history, list):
        for value in valuation_history:
            if not isinstance(value, Mapping):
                continue
            tax_year = _text(value.get("tax_year"))
            if not tax_year:
                continue
            assessments_upserted += _upsert_assessment_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                tax_year=tax_year,
                market_value=value.get("real_market_value"),
                assessed_value=value.get("assessed_value"),
                assessment_class=record.get("property_class"),
                source_good_through=None,
                observation_id=observation_id,
                raw={
                    **dict(value),
                    "maximum_assessed_value": value.get(
                        "maximum_assessed_value"
                    ),
                    "property_class": record.get("property_class"),
                    "property_class_description": record.get(
                        "property_class_description"
                    ),
                },
            )

    tax_events_upserted = 0
    recent_receipts = record.get("recent_receipts")
    if isinstance(recent_receipts, list):
        for index, value in enumerate(recent_receipts):
            if not isinstance(value, Mapping):
                continue
            native_event_id = sha256_fingerprint(
                {
                    "account_number": account_number,
                    "receipt_index": index,
                    "receipt": dict(value),
                }
            )
            tax_events_upserted += _upsert_tax_account_event(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                event_type="property_tax_receipt",
                tax_year="",
                event_date=_date_prefix(value.get("date_iso")),
                amount=value.get("amount_received"),
                status="source_observed_receipt",
                native_event_id=native_event_id,
                observation_id=observation_id,
                raw=value,
            )

    representations = record.get("related_representations")
    representation_count = (
        len([value for value in representations if isinstance(value, Mapping)])
        if isinstance(representations, list)
        else 0
    )
    return {
        "parcel_id": parcel_id,
        "parcel_anchor_source_id": anchor_source_id,
        "parcel_placeholder_created": int(placeholder_created),
        "canonical_ref": _text(record.get("canonical_ref")),
        "account_number": account_number,
        "map_taxlot": map_taxlot,
        "source_occurrence_id": source_occurrence_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "owners_upserted": owners_upserted,
        "taxpayers_upserted": taxpayers_upserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "tax_events_upserted": tax_events_upserted,
        "source_representations_preserved": representation_count,
        "recorded_instruments_upserted": 0,
        "recorded_title_conclusions_created": 0,
        "receipt_payers_projected_as_owners": 0,
    }


def _lane_tax_map_artifact(
    db,
    *,
    record: Mapping[str, Any],
    observation_id: int,
    retrieved_at: str,
) -> int:
    document_id = _text(record.get("tax_map_document_id"))
    if not document_id:
        raise PropertyIngestError("Lane tax-map document lacks document ID")
    sha256 = _text(record.get("sha256"))
    row = db.execute(
        """
        SELECT artifact_id FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid='41039'
          AND native_document_id=?
          AND COALESCE(sha256, '')=COALESCE(?, '')
        """,
        (LANE_TAX_MAP_SOURCE_ID, document_id, sha256),
    ).fetchone()
    values = (
        None,
        sha256,
        _text(record.get("media_type")) or "application/pdf",
        None,
        _text(record.get("local_path")),
        _text(record.get("source_url")),
        "direct_source_pdf_download",
        "official_assessment_tax_map",
        "public",
        retrieved_at,
    )
    if row is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, '41039', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (LANE_TAX_MAP_SOURCE_ID, document_id, *values),
        )
        return int(cursor.lastrowid)
    artifact_id = int(row["artifact_id"])
    db.execute(
        """
        UPDATE document_artifact SET
            instrument_id=?, sha256=?, mime_type=?, page_count=?,
            storage_path=?, source_url=?, acquisition_method=?,
            rights_tier=?, access_state=?, acquired_at=?
        WHERE artifact_id=?
        """,
        (*values, artifact_id),
    )
    return artifact_id


def _ingest_lane_tax_map_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve locator/document identity and project exact map-taxlot joins."""

    (
        observation_id,
        record_hash,
        retrieved_at,
        record_kind,
        source_occurrence_id,
    ) = _lane_property_observation(
        db,
        envelope=envelope,
        record=record,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    if record_kind == "tax_map_document":
        artifact_id = _lane_tax_map_artifact(
            db,
            record=record,
            observation_id=observation_id,
            retrieved_at=retrieved_at,
        )
        return {
            "artifact_id": artifact_id,
            "tax_map_document_id": _text(record.get("tax_map_document_id")),
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "locator_projected": False,
            "recorded_instruments_upserted": 0,
            "recorded_title_conclusions_created": 0,
        }
    if record_kind != "tax_map_locator":
        return {
            "projection_skipped": True,
            "reason": "lane_tax_map_metadata_or_probe_observation",
            "record_kind": record_kind,
            "source_occurrence_id": source_occurrence_id,
            "observation_id": observation_id,
            "record_sha256": record_hash,
        }

    map_taxlot = _text(record.get("map_taxlot"))
    if not map_taxlot:
        return {
            "projection_skipped": True,
            "reason": "lane_tax_map_locator_has_map_name_without_exact_map_taxlot",
            "record_kind": record_kind,
            "source_occurrence_id": source_occurrence_id,
            "tax_map_document_id": _text(record.get("tax_map_document_id")),
            "observation_id": observation_id,
            "record_sha256": record_hash,
        }
    parcel_id, anchor_source_id, placeholder_created = _lane_property_parcel(
        db,
        source_id=source_id,
        map_taxlot=map_taxlot,
        account_number=None,
        observation_id=observation_id,
        retrieved_at=retrieved_at,
        record=record,
    )
    aliases_inserted = _lane_property_aliases(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        map_taxlot=map_taxlot,
        account_number=None,
        effective_from=retrieved_at,
    )
    address = _text(record.get("address"))
    addresses_inserted = int(
        bool(
            address
            and _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                role="situs",
                address={
                    "raw": address,
                    "city": _text(record.get("city")),
                    "state": "OR",
                },
                effective_from=retrieved_at,
            )
        )
    )
    return {
        "parcel_id": parcel_id,
        "parcel_anchor_source_id": anchor_source_id,
        "parcel_placeholder_created": int(placeholder_created),
        "canonical_ref": _text(record.get("canonical_ref")),
        "map_taxlot": map_taxlot,
        "source_occurrence_id": source_occurrence_id,
        "tax_map_document_id": _text(record.get("tax_map_document_id")),
        "tax_map_document_ref": _text(record.get("tax_map_document_ref")),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "locator_identity_preserved": True,
        "document_identity_preserved": True,
        "ownership_assertions_created": 0,
        "recorded_instruments_upserted": 0,
        "recorded_title_conclusions_created": 0,
    }


def _ingest_lane_marion_assessor_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project Lane/Marion parcel fields without flattening source components."""

    projected = dict(record)
    if not _text(projected.get("source_last_updated")) and _text(
        projected.get("source_last_edited")
    ):
        projected["source_last_updated"] = projected["source_last_edited"]

    source_assessment = record.get("assessment")
    if isinstance(source_assessment, Mapping):
        projected["assessment"] = {
            **dict(source_assessment),
            "land_value": source_assessment.get("real_market_land"),
            "improvement_value": source_assessment.get("real_market_improvements"),
            "parcel_value": source_assessment.get("real_market_total"),
            "assessed_value": source_assessment.get("assessed_value"),
            "assessment_class": (
                record.get("physical_characteristics", {}).get("property_class")
                if isinstance(
                    record.get("physical_characteristics"),
                    Mapping,
                )
                else source_assessment.get("property_class")
            ),
        }
        if not projected["assessment"]["assessment_class"]:
            projected["assessment"]["assessment_class"] = (
                source_assessment.get("property_class")
            )

    latest_sale = record.get("latest_verified_sale_reference")
    if isinstance(latest_sale, Mapping):
        projected["last_sale"] = {
            **dict(latest_sale),
            "source_document_ref": latest_sale.get("instrument_number"),
            "source_document_date": latest_sale.get("recording_date"),
            "sale_date": latest_sale.get("recording_date"),
            "qualification_code": ("latest_transfer_coded_as_verified_sale"),
        }

    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    effective_from = (
        _text(projected.get("source_last_updated"))
        or _text(envelope.get("retrieved_at"))
        or ""
    )
    account_aliases = record.get("assessment_account_ids", [])
    if not isinstance(account_aliases, list):
        raise PropertyIngestError("record.assessment_account_ids must be a list")
    for account_id in account_aliases:
        result["aliases_inserted"] += _upsert_alias(
            db,
            parcel_id=int(result["parcel_id"]),
            alias_type="assessment_account",
            alias_value=account_id,
            source_id=source_id,
            effective_from=effective_from,
        )
    return result


def _ingest_lane_sale_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one Lane or Marion assessor-sale row through parcel join keys."""

    _assert_record_source(record, source_id)
    if source_id == MARION_SALES_DOWNLOAD_SOURCE_ID:
        parcel_source_ids = (
            MARION_PARCELS_SOURCE_ID,
            MARION_ASSESSMENT_DOWNLOAD_SOURCE_ID,
        )
        fallback_geoid = "41047"
        fallback_name = "Marion County, Oregon"
    elif source_id == LANE_SALES_SOURCE_ID:
        parcel_source_ids = (LANE_PARCELS_SOURCE_ID,)
        fallback_geoid = "41039"
        fallback_name = "Lane County, Oregon"
    else:
        raise PropertyIngestError(
            f"{source_id} is not a Lane or Marion assessor-sale source"
        )
    native_sale_id = _text(record.get("native_sale_id"))
    if not native_sale_id:
        raise PropertyIngestError("assessor sale record lacks native_sale_id")
    join_keys = _mapping(record.get("join_keys"), "record.join_keys")
    map_taxlot = _text(join_keys.get("map_taxlot"))
    account_id = _text(join_keys.get("assessment_account_id"))
    native_parcel_id = map_taxlot or account_id
    if not native_parcel_id:
        raise PropertyIngestError(
            "assessor sale record lacks a map-taxlot or assessment account"
        )

    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid=fallback_geoid,
        fallback_name=fallback_name,
        fallback_state_code="OR",
    )
    if geoid != fallback_geoid:
        raise PropertyIngestError(
            f"{source_id} record has out-of-scope GEOID {geoid}"
        )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=(
            _text(record.get("source_occurrence_id")) or native_sale_id
        ),
        record_kind=(
            _text(record.get("record_kind"))
            or "assessor_sale_observation"
        ),
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    sale = _mapping(record.get("sale"), "record.sale")
    instrument = _mapping(
        record.get("instrument_reference"),
        "record.instrument_reference",
    )
    sale_date = _text(sale.get("sale_date") or instrument.get("recording_date"))
    retrieval_snapshot = record.get("retrieval_snapshot")
    source_good_through = (
        _text(retrieval_snapshot.get("service_data_last_edit"))
        if isinstance(retrieval_snapshot, Mapping)
        else None
    )
    source_placeholders = ", ".join("?" for _ in parcel_source_ids)
    parcel_row = None
    if map_taxlot:
        parcel_row = db.execute(
            f"""
            SELECT p.parcel_id, p.source_id
            FROM parcel_snapshot p
            WHERE p.source_id IN ({source_placeholders})
              AND p.jurisdiction_geoid=?
              AND (
                p.native_parcel_id=?
                OR EXISTS(
                    SELECT 1
                    FROM parcel_alias pa
                    WHERE pa.parcel_id=p.parcel_id
                      AND pa.alias_value=?
                )
              )
            ORDER BY CASE WHEN p.roll_year='' THEN 1 ELSE 0 END,
                     p.roll_year DESC, p.parcel_id DESC
            LIMIT 1
            """,
            (
                *parcel_source_ids,
                geoid,
                map_taxlot,
                map_taxlot,
            ),
        ).fetchone()
    if parcel_row is None and account_id:
        parcel_row = db.execute(
            f"""
            SELECT p.parcel_id, p.source_id
            FROM parcel_snapshot p
            JOIN parcel_alias pa ON pa.parcel_id=p.parcel_id
            WHERE p.source_id IN ({source_placeholders})
              AND p.jurisdiction_geoid=?
              AND pa.alias_type='assessment_account'
              AND pa.alias_value=?
            ORDER BY CASE WHEN p.roll_year='' THEN 1 ELSE 0 END,
                     p.roll_year DESC, p.parcel_id DESC
            LIMIT 1
            """,
            (*parcel_source_ids, geoid, account_id),
        ).fetchone()
    sale_source_shell = None
    if parcel_row is None:
        sale_source_shell = db.execute(
            """
            SELECT p.parcel_id, p.source_id
            FROM parcel_snapshot p
            WHERE p.source_id=? AND p.jurisdiction_geoid=?
              AND (
                p.native_parcel_id=?
                OR EXISTS(
                    SELECT 1
                    FROM parcel_alias pa
                    WHERE pa.parcel_id=p.parcel_id
                      AND pa.alias_value IN (?, ?)
                )
              )
            ORDER BY p.parcel_id
            LIMIT 1
            """,
            (
                source_id,
                geoid,
                native_parcel_id,
                map_taxlot,
                account_id,
            ),
        ).fetchone()
    parcel_placeholder_created = (
        parcel_row is None and sale_source_shell is None
    )
    if parcel_row is None:
        if sale_source_shell is None:
            placeholder_record = {
                **dict(record),
                "parcel_shell": {
                    "state": "sale_source_anchor",
                    "source_id": source_id,
                    "candidate_related_source_ids": list(parcel_source_ids),
                    "join_keys": dict(join_keys),
                },
            }
            parcel_id = _upsert_parcel_snapshot(
                db,
                source_id=source_id,
                jurisdiction_geoid=geoid,
                native_parcel_id=native_parcel_id,
                roll_year="",
                effective_from=None,
                source_good_through=source_good_through,
                observation_id=observation_id,
                record=placeholder_record,
            )
        else:
            parcel_id = int(sale_source_shell["parcel_id"])
        parcel_anchor_source_id = source_id
    else:
        parcel_id = int(parcel_row["parcel_id"])
        parcel_anchor_source_id = str(parcel_row["source_id"])

    aliases_inserted = 0
    if account_id and (
        account_id != native_parcel_id or parcel_placeholder_created
    ):
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="assessment_account",
            alias_value=account_id,
            source_id=source_id,
            effective_from=sale_date or retrieved_at,
        )
    if map_taxlot and (
        map_taxlot != native_parcel_id or parcel_placeholder_created
    ):
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="map_taxlot",
            alias_value=map_taxlot,
            source_id=source_id,
            effective_from=sale_date or retrieved_at,
        )

    address = record.get("situs_address")
    addresses_inserted = int(
        isinstance(address, Mapping)
        and _upsert_address(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            role="situs",
            address=address,
            effective_from=sale_date or retrieved_at,
        )
    )
    sales_upserted = _upsert_sale_projection(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        native_sale_id=native_sale_id,
        sale_date=sale_date,
        consideration=sale.get("consideration"),
        derivation="assessor_sale_analysis",
        observation_id=observation_id,
        raw={
            "sale": sale,
            "instrument_reference": instrument,
            "transaction_parties": record.get("transaction_parties"),
            "coverage_period": record.get("coverage_period"),
            "join_keys": join_keys,
            "sale_identity": record.get("sale_identity"),
            "release_slot_identity": record.get(
                "release_slot_identity"
            ),
            "release_occurrence_identity": record.get(
                "release_occurrence_identity"
            ),
            "row_occurrence": record.get("row_occurrence"),
        },
        recording_date=_text(instrument.get("recording_date")),
        qualification_code=_text(
            sale.get("reject_code") or sale.get("condition_code")
        ),
    )

    geometry_upserted = 0
    geometry = record.get("geometry")
    if isinstance(geometry, Mapping):
        db.execute(
            """
            INSERT INTO parcel_geometry(
                parcel_id, geometry_ref, geometry_format, crs,
                accuracy_disclaimer, source_id, snapshot_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
                geometry_ref=excluded.geometry_ref,
                geometry_format=excluded.geometry_format,
                crs=excluded.crs,
                accuracy_disclaimer=excluded.accuracy_disclaimer
            """,
            (
                parcel_id,
                f"source-observation:{observation_id}#/geometry",
                _text(record.get("geometry_format")) or "esri_json",
                _text(record.get("geometry_crs")) or "EPSG:4326",
                _text(record.get("geometry_disclaimer")),
                source_id,
                source_good_through or sale_date or "",
            ),
        )
        geometry_upserted = 1

    return {
        "parcel_id": parcel_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            geoid,
            "sale_reference",
            native_sale_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": 0,
        "owners_upserted": 0,
        "sales_upserted": sales_upserted,
        "geometry_upserted": geometry_upserted,
        "parcel_placeholder_created": parcel_placeholder_created,
        "parcel_anchor_source_id": parcel_anchor_source_id,
        "candidate_parcel_source_ids": list(parcel_source_ids),
    }


def _ingest_firstmap_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        identity = record.get("identity")
        return {
            "projection_skipped": True,
            "reason": "noncanonical_source_feature",
            "identity_basis": (
                _text(identity.get("basis")) if isinstance(identity, Mapping) else None
            ),
            "source_feature_ids": list(record.get("source_feature_ids") or []),
        }

    projected = dict(record)
    dated_features: list[Mapping[str, Any]] = []
    polygon_features = record.get("polygon_features")
    centroid_features = record.get("centroid_features")
    for field_name, features in (
        ("polygon_features", polygon_features),
        ("centroid_features", centroid_features),
    ):
        if features is None:
            continue
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise PropertyIngestError(f"record.{field_name} must be a list")
        dated_features.extend(features)

    updated_values = sorted(
        {
            value
            for feature in dated_features
            if (value := _text(feature.get("source_updated_at")))
        }
    )
    if updated_values:
        projected["source_last_updated"] = updated_values[-1]

    geometry_features = [
        feature
        for feature in list(polygon_features or [])
        if isinstance(feature.get("geometry"), Mapping)
    ]
    if not geometry_features:
        geometry_features = [
            feature
            for feature in list(centroid_features or [])
            if isinstance(feature.get("geometry"), Mapping)
        ]
    if geometry_features:
        geometries = [dict(feature["geometry"]) for feature in geometry_features]
        projected["geometry"] = (
            geometries[0] if len(geometries) == 1 else {"geometries": geometries}
        )
        projected["geometry_format"] = (
            "esri_json" if len(geometries) == 1 else "esri_json_geometry_collection"
        )
        spatial_references = {
            int(feature["geometry_spatial_reference"])
            for feature in geometry_features
            if feature.get("geometry_spatial_reference") not in (None, "")
        }
        if len(spatial_references) == 1:
            projected["geometry_crs"] = f"EPSG:{next(iter(spatial_references))}"
        projected["geometry_disclaimer"] = (
            "FirstMap parcel geometry is mapping data and is not a surveyed "
            "legal boundary."
        )

    return _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )


def _upsert_tax_account_owner(
    db,
    *,
    parcel_id: int,
    source_id: str,
    raw_name: str,
    effective_from: str,
    observation_id: int,
    evidence_ref: str | None,
) -> int:
    normalized_name = " ".join(raw_name.upper().split())
    db.execute(
        """
        INSERT INTO ownership_assertion(
            parcel_id, source_id, assertion_type, raw_owner_name,
            normalized_owner_name, effective_from, confidence, claim_type,
            observation_id, evidence_ref, source_quote
        ) VALUES (?, ?, 'tax_account', ?, ?, ?, 'confirmed',
                  'direct_quote', ?, ?, ?)
        ON CONFLICT(
            parcel_id, source_id, assertion_type, raw_owner_name, effective_from
        ) DO UPDATE SET
            normalized_owner_name=excluded.normalized_owner_name,
            confidence=excluded.confidence,
            claim_type=excluded.claim_type,
            observation_id=excluded.observation_id,
            evidence_ref=excluded.evidence_ref,
            source_quote=excluded.source_quote
        """,
        (
            parcel_id,
            source_id,
            raw_name,
            normalized_name,
            effective_from,
            observation_id,
            evidence_ref,
            raw_name,
        ),
    )
    return 1


def _upsert_tax_account_event(
    db,
    *,
    parcel_id: int,
    source_id: str,
    event_type: str = "delinquency_publication",
    tax_year: str,
    event_date: str | None,
    amount: Any,
    status: str,
    native_event_id: str,
    observation_id: int,
    raw: Mapping[str, Any],
) -> int:
    existing = db.execute(
        """
        SELECT tax_event_id
        FROM tax_account_event
        WHERE parcel_id=? AND source_id=? AND event_type=?
          AND event_date IS ? AND native_event_id=?
        """,
        (
            parcel_id,
            source_id,
            event_type,
            event_date,
            native_event_id,
        ),
    ).fetchone()
    values = (
        tax_year,
        event_date,
        _minor_units(amount),
        status,
        observation_id,
        canonical_json(raw),
    )
    if existing is None:
        db.execute(
            """
            INSERT INTO tax_account_event(
                parcel_id, source_id, tax_year, event_type, event_date,
                amount_minor, currency, status, native_event_id,
                observation_id, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
            """,
            (
                parcel_id,
                source_id,
                tax_year,
                event_type,
                event_date,
                _minor_units(amount),
                status,
                native_event_id,
                observation_id,
                canonical_json(raw),
            ),
        )
    else:
        db.execute(
            """
            UPDATE tax_account_event SET
                tax_year=?,
                event_date=?,
                amount_minor=?,
                currency='USD',
                status=?,
                observation_id=?,
                raw_json=?
            WHERE tax_event_id=?
            """,
            (*values, int(existing["tax_event_id"])),
        )
    return 1


def _los_angeles_jurisdiction(db) -> str:
    return _upsert_jurisdiction_values(
        db,
        geoid="06037",
        name="Los Angeles County, California",
        state_code="CA",
        jurisdiction_type="county",
        parent_geoid="06",
    )


def _los_angeles_existing_or_placeholder_parcel(
    db,
    *,
    source_id: str,
    native_parcel_id: str,
    observation_id: int,
    record: Mapping[str, Any],
) -> int:
    """Resolve one AIN across the separately sourced LA property components."""

    row = db.execute(
        """
        SELECT parcel_id
        FROM parcel_snapshot
        WHERE jurisdiction_geoid='06037' AND native_parcel_id=?
          AND source_id IN (?, ?, ?)
        ORDER BY CASE source_id
            WHEN ? THEN 0
            WHEN ? THEN 1
            ELSE 2
        END, parcel_id
        LIMIT 1
        """,
        (
            native_parcel_id,
            LOS_ANGELES_ASSESSOR_SOURCE_ID,
            LOS_ANGELES_TTC_PAYMENT_SOURCE_ID,
            LOS_ANGELES_TTC_SALE_SOURCE_ID,
            LOS_ANGELES_ASSESSOR_SOURCE_ID,
            LOS_ANGELES_TTC_PAYMENT_SOURCE_ID,
        ),
    ).fetchone()
    if row is not None:
        return int(row["parcel_id"])
    return _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid="06037",
        native_parcel_id=native_parcel_id,
        roll_year="",
        effective_from=None,
        source_good_through=None,
        observation_id=observation_id,
        record=record,
    )


def _ingest_los_angeles_assessor_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project the exact Assessor AIN route without importing TTC facts."""

    if _text(record.get("record_kind")) != "parcel_route":
        return {
            "projection_skipped": True,
            "reason": "assessor_component_record_is_not_a_parcel_route",
            "record_kind": _text(record.get("record_kind")),
        }
    projected = dict(record)
    projected["jurisdiction"] = {
        "state_code": "CA",
        "state_fips": "06",
        "county_name": "Los Angeles County",
        "county_geoid": "06037",
    }
    native_ids = record.get("native_ids")
    if isinstance(native_ids, Mapping):
        projected["tax_year"] = native_ids.get("roll_year")
        apn = _text(native_ids.get("apn"))
        if apn and apn != _text(record.get("native_parcel_id")):
            projected["alternate_parcel_ids"] = [apn]
    address = record.get("situs_address")
    if isinstance(address, Mapping):
        projected_address = dict(address)
        city_state = _text(address.get("city_state"))
        if city_state and city_state.upper().endswith(" CA"):
            projected_address["city"] = city_state[:-3].strip()
            projected_address["state"] = "CA"
        projected["situs_address"] = projected_address
    centroid = record.get("centroid")
    if isinstance(centroid, Mapping) and all(
        centroid.get(field) not in (None, "") for field in ("longitude", "latitude")
    ):
        projected["geometry"] = {
            "type": "Point",
            "coordinates": [
                centroid.get("longitude"),
                centroid.get("latitude"),
            ],
        }
        projected["geometry_format"] = "geojson_point"
        projected["geometry_crs"] = "EPSG:4326"
        projected["geometry_disclaimer"] = "Source-published Assessor parcel centroid."
    return _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="parcel_route",
    )


def _ingest_los_angeles_payment_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one TTC payment row as an AIN-linked tax-account event."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_kind")) != "property_tax_payment":
        return {
            "projection_skipped": True,
            "reason": "payment_component_record_is_not_a_payment_row",
            "record_kind": _text(record.get("record_kind")),
        }
    ain = _text(record.get("native_parcel_id") or record.get("ain"))
    native_ids = record.get("native_ids")
    payment_id = (
        _text(native_ids.get("payment_id")) if isinstance(native_ids, Mapping) else None
    )
    tax_year = _text(record.get("tax_year"))
    if not ain or not payment_id or not tax_year:
        raise PropertyIngestError(
            "Los Angeles TTC payment row requires AIN, payment ID, and tax year"
        )
    _los_angeles_jurisdiction(db)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    native_event_id = f"{ain}:{payment_id}"
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_event_id,
        record_kind="property_tax_payment",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_id = _los_angeles_existing_or_placeholder_parcel(
        db,
        source_id=source_id,
        native_parcel_id=ain,
        observation_id=observation_id,
        record=record,
    )
    aliases_inserted = _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="formatted_ain",
        alias_value=record.get("formatted_ain"),
        source_id=source_id,
        effective_from=_text(record.get("effective_date")) or retrieved_at,
    )
    amounts = _mapping(record.get("amounts"), "record.amounts")
    tax_events_upserted = _upsert_tax_account_event(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        event_type="property_tax_payment",
        tax_year=tax_year,
        event_date=_text(record.get("effective_date")),
        amount=amounts.get("total_paid"),
        status=(_text(record.get("operation_state")) or "official_payment_row"),
        native_event_id=native_event_id,
        observation_id=observation_id,
        raw=record,
    )
    addresses_inserted = 0
    account_snapshot = record.get("account_snapshot")
    if isinstance(account_snapshot, Mapping):
        street = _text(account_snapshot.get("street_address"))
        if street:
            addresses_inserted = int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role="situs",
                    address={"raw": street},
                    effective_from=(
                        _text(record.get("effective_date")) or retrieved_at
                    ),
                )
            )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            "06037",
            "tax-payment",
            native_event_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "tax_events_upserted": tax_events_upserted,
    }


def _ingest_los_angeles_sale_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve TTC sale artifacts and project parcel-level result rows."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind")) or "source_row"
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    native_ids = record.get("native_ids")
    native_ids = dict(native_ids) if isinstance(native_ids, Mapping) else {}
    source_native_id = (
        _text(record.get("sale_id"))
        or _text(native_ids.get("sale_id"))
        or _text(record.get("canonical_ref"))
        or sha256_fingerprint(record)
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=(
            raw_artifact_sha256
            or _text(
                (
                    record.get("publication")
                    if isinstance(record.get("publication"), Mapping)
                    else {}
                ).get("artifact_sha256")
            )
        ),
        warnings=warnings,
    )
    if record_kind != "property_tax_sale_result":
        return {
            "projection": "observation_only",
            "canonical_ref": _text(record.get("canonical_ref")),
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "source_native_id": source_native_id,
            "record_kind": record_kind,
        }

    ain = _text(record.get("native_parcel_id") or record.get("ain"))
    sale_id = _text(record.get("sale_id") or native_ids.get("sale_id"))
    cycle = _text(record.get("auction_cycle"))
    if not ain or not sale_id or not cycle:
        raise PropertyIngestError(
            "Los Angeles TTC sale result requires AIN, sale ID, and cycle"
        )
    _los_angeles_jurisdiction(db)
    parcel_id = _los_angeles_existing_or_placeholder_parcel(
        db,
        source_id=source_id,
        native_parcel_id=ain,
        observation_id=observation_id,
        record=record,
    )
    aliases_inserted = _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="formatted_ain",
        alias_value=record.get("formatted_ain"),
        source_id=source_id,
        effective_from=_text(record.get("publication_date")) or retrieved_at,
    )
    amounts = _mapping(record.get("amounts"), "record.amounts")
    event_date = _text(record.get("publication_date"))
    tax_year = cycle[:4]
    tax_events_upserted = _upsert_tax_account_event(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        event_type="tax_sale_result",
        tax_year=tax_year,
        event_date=event_date,
        amount=amounts.get("purchase_price"),
        status=_text(record.get("status")) or "sold_as_published",
        native_event_id=sale_id,
        observation_id=observation_id,
        raw=record,
    )
    tax_events_upserted += _upsert_tax_account_event(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        event_type="tax_sale_excess_proceeds",
        tax_year=tax_year,
        event_date=event_date,
        amount=amounts.get("excess_proceeds"),
        status=_text(
            (
                record.get("excess_proceeds_state")
                if isinstance(record.get("excess_proceeds_state"), Mapping)
                else {}
            ).get("status")
        )
        or "as_published",
        native_event_id=f"{sale_id}:excess-proceeds",
        observation_id=observation_id,
        raw=record,
    )
    sales_upserted = _upsert_sale_projection(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        native_sale_id=sale_id,
        sale_date=None,
        consideration=amounts.get("purchase_price"),
        derivation="tax_sale_publication",
        observation_id=observation_id,
        raw=record,
        qualification_code=":".join(
            value
            for value in (
                cycle,
                _text(record.get("sale_phase")),
            )
            if value
        ),
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            "06037",
            "tax-sale-result",
            sale_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "tax_events_upserted": tax_events_upserted,
        "sales_upserted": sales_upserted,
    }


def _ingest_denver_delinquent_tax_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    native_parcel_id = _text(record.get("native_parcel_id"))
    tax_year = _text(record.get("tax_year"))
    if not native_parcel_id or not tax_year:
        raise PropertyIngestError(
            "Denver delinquent-tax record requires native_parcel_id and tax_year"
        )
    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="08031",
        fallback_name="City and County of Denver, Colorado",
        fallback_state_code="CO",
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    stable_account_key = (
        _text(record.get("stable_account_key")) or f"{tax_year}:{native_parcel_id}"
    )
    release_date = _text(record.get("release_date"))
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=stable_account_key,
        record_kind="property_tax_delinquency",
        query_fingerprint=query_fingerprint,
        source_url=(
            _text(record.get("artifact_url"))
            or _text(record.get("publication_page"))
            or _record_source_url(envelope, record)
        ),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=(
            raw_artifact_sha256 or _text(record.get("artifact_sha256"))
        ),
        warnings=warnings,
    )
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid=geoid,
        native_parcel_id=native_parcel_id,
        roll_year=tax_year,
        effective_from=release_date,
        source_good_through=release_date,
        observation_id=observation_id,
        record=record,
    )

    effective_from = release_date or tax_year
    aliases_inserted = _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="tax_account",
        alias_value=record.get("native_account_id"),
        source_id=source_id,
        effective_from=effective_from,
    )
    owners = record.get("owners", [])
    if not isinstance(owners, list):
        raise PropertyIngestError("record.owners must be a list")
    owners_upserted = 0
    evidence_ref = _text(record.get("evidence_ref"))
    for index, owner_value in enumerate(owners):
        owner = _mapping(owner_value, f"record.owners[{index}]")
        raw_name = _text(owner.get("raw_name"))
        if not raw_name:
            continue
        owners_upserted += _upsert_tax_account_owner(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            raw_name=raw_name,
            effective_from=effective_from,
            observation_id=observation_id,
            evidence_ref=evidence_ref,
        )

    addresses_inserted = 0
    address = record.get("situs_address")
    if isinstance(address, Mapping):
        addresses_inserted = int(
            _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                role="situs",
                address=address,
                effective_from=effective_from,
            )
        )

    valuation = record.get("valuation")
    assessments_upserted = 0
    if isinstance(valuation, Mapping) and valuation.get("parcel_valuation") not in (
        None,
        "",
    ):
        assessments_upserted = _upsert_assessment_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=tax_year,
            total_value=valuation.get("parcel_valuation"),
            assessment_class="delinquent_tax_publication_valuation",
            source_good_through=release_date,
            observation_id=observation_id,
            raw=valuation,
        )

    amounts = record.get("amounts")
    if not isinstance(amounts, Mapping):
        raise PropertyIngestError("record.amounts must be an object")
    tax_events_upserted = _upsert_tax_account_event(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        tax_year=tax_year,
        event_date=release_date,
        amount=amounts.get("total_due"),
        status=(_text(record.get("delinquency_status")) or "delinquent_as_published"),
        native_event_id=stable_account_key,
        observation_id=observation_id,
        raw={
            "amounts": dict(amounts),
            "tax_sale_indicator": record.get("tax_sale_indicator"),
            "partial_payment_indicator": record.get("partial_payment_indicator"),
            "release_scope_categories": record.get("release_scope_categories"),
        },
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id,
            geoid,
            "tax-delinquency",
            stable_account_key,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "owners_upserted": owners_upserted,
        "tax_events_upserted": tax_events_upserted,
    }


def _ingest_virginia_beach_delinquent_tax_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one current bill installment while joining parcels only by GPIN."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    if record_kind != "property_tax_delinquency":
        return {
            "projection_skipped": True,
            "reason": "record_is_not_a_tax_delinquency_installment",
            "record_kind": record_kind,
        }

    gpin = _text(record.get("native_parcel_id") or record.get("gpin"))
    bill_number = _text(
        record.get("bill_number") or record.get("native_account_id")
    )
    installment = _text(record.get("installment"))
    tax_year = _text(record.get("tax_year"))
    if not all((gpin, bill_number, installment, tax_year)):
        raise PropertyIngestError(
            "Virginia Beach delinquent-tax record requires GPIN, bill number, "
            "installment, and tax year"
        )
    occurrence_id = f"{bill_number}:{installment}:{gpin}:{tax_year}"
    native_event_id = _text(record.get("native_event_id"))
    if native_event_id != occurrence_id:
        raise PropertyIngestError(
            "Virginia Beach native_event_id must preserve the "
            "bill/installment/GPIN/tax-year occurrence key"
        )
    native_account_id = _text(record.get("native_account_id"))
    if native_account_id and native_account_id != bill_number:
        raise PropertyIngestError(
            "Virginia Beach native_account_id must match the published bill number"
        )

    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="51810",
        fallback_name="City of Virginia Beach, Virginia",
        fallback_state_code="VA",
    )
    if geoid != "51810":
        raise PropertyIngestError(
            f"{source_id} record has out-of-scope GEOID {geoid}"
        )

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_snapshot = record.get("source_snapshot")
    if not isinstance(source_snapshot, Mapping):
        source_snapshot = {}
    snapshot_date = _date_prefix(source_snapshot.get("data_last_edit_at"))
    effective_from = snapshot_date or _date_prefix(retrieved_at) or tax_year
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=occurrence_id,
        record_kind="property_tax_delinquency",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid=geoid,
        native_parcel_id=gpin,
        roll_year=tax_year,
        effective_from=effective_from,
        source_good_through=snapshot_date,
        observation_id=observation_id,
        record=record,
    )
    aliases_inserted = _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="tax_bill",
        alias_value=bill_number,
        source_id=source_id,
        effective_from=tax_year,
    )

    evidence_ref = _text(record.get("evidence_ref"))
    owner_observation = record.get("owner_observation")
    owners_upserted = 0
    if isinstance(owner_observation, Mapping):
        raw_owner_name = _text(owner_observation.get("raw_name"))
        if raw_owner_name:
            owners_upserted = _upsert_tax_account_owner(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                raw_name=raw_owner_name,
                effective_from=effective_from,
                observation_id=observation_id,
                evidence_ref=evidence_ref,
            )

    addresses_inserted = 0
    for role, address_value in (
        ("situs", record.get("situs_address")),
        ("mailing", record.get("mailing_address")),
    ):
        if isinstance(address_value, Mapping):
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role=role,
                    address=address_value,
                    effective_from=effective_from,
                )
            )

    amounts = record.get("amounts")
    if not isinstance(amounts, Mapping):
        raise PropertyIngestError("record.amounts must be an object")
    total_due = amounts.get("total_due")
    total_due_minor = amounts.get("total_due_minor")
    if total_due_minor is not None:
        if isinstance(total_due_minor, bool) or not isinstance(
            total_due_minor, int
        ):
            raise PropertyIngestError(
                "Virginia Beach total_due_minor must be an integer"
            )
        if total_due is not None and _minor_units(total_due) != total_due_minor:
            raise PropertyIngestError(
                "Virginia Beach total_due and total_due_minor disagree"
            )
        total_due = Decimal(total_due_minor) / Decimal(100)

    tax_events_upserted = _upsert_tax_account_event(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        event_type="delinquency_current_extract",
        tax_year=tax_year,
        event_date=None,
        amount=total_due,
        status=(
            _text(record.get("delinquency_status"))
            or "delinquent_in_current_daily_extract"
        ),
        native_event_id=occurrence_id,
        observation_id=observation_id,
        raw={
            "occurrence_identity": {
                "bill_number": bill_number,
                "installment": installment,
                "gpin": gpin,
                "tax_year": tax_year,
            },
            "parcel_join": {
                "gpin": gpin,
                "jurisdiction_geoid": geoid,
            },
            "amounts": dict(amounts),
            "district": record.get("district"),
            "legal_description_raw": record.get("legal_description_raw"),
            "source_snapshot": dict(source_snapshot),
        },
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            geoid,
            "tax-delinquency",
            occurrence_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "native_event_id": occurrence_id,
        "parcel_join_gpin": gpin,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "owners_upserted": owners_upserted,
        "tax_events_upserted": tax_events_upserted,
    }


def _oregon_tax_publication_snapshot(
    envelope: Mapping[str, Any],
) -> dict[str, Any]:
    query = envelope.get("query")
    if not isinstance(query, Mapping):
        return {}
    metadata = query.get("query")
    if not isinstance(metadata, Mapping):
        return {}
    parameters = metadata.get("parameters")
    if not isinstance(parameters, Mapping):
        return {}
    publication = parameters.get("publication")
    if not isinstance(publication, Mapping):
        return {}
    return dict(publication)


def _upsert_oregon_tax_publication_artifact(
    db,
    *,
    source_id: str,
    jurisdiction_geoid: str,
    publication: Mapping[str, Any],
    retrieved_at: str,
) -> dict[str, Any]:
    artifact_sha256 = _text(publication.get("artifact_sha256"))
    if not artifact_sha256:
        return {
            "artifact_id": None,
            "artifacts_upserted": 0,
            "representations_upserted": 0,
        }
    process_stage = _text(publication.get("process_stage")) or "publication"
    document_id = _text(publication.get("publication_document_id")) or (
        f"{source_id}:{process_stage}:{artifact_sha256[:20]}"
    )
    raw_page_count = publication.get("artifact_page_count")
    try:
        page_count = int(raw_page_count) if raw_page_count not in (None, "") else None
    except (TypeError, ValueError):
        page_count = None

    existing = db.execute(
        """
        SELECT artifact_id FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_document_id=? AND COALESCE(sha256, '')=?
        """,
        (
            source_id,
            jurisdiction_geoid,
            document_id,
            artifact_sha256,
        ),
    ).fetchone()
    values = (
        artifact_sha256,
        _text(publication.get("artifact_media_type")) or "application/pdf",
        page_count,
        _text(publication.get("artifact_path")),
        _text(publication.get("document_url")),
        "official_publication_inspection",
        "source_publication",
        "public",
        retrieved_at,
    )
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                jurisdiction_geoid,
                document_id,
                *values,
            ),
        )
        artifact_id = int(cursor.lastrowid)
    else:
        artifact_id = int(existing["artifact_id"])
        db.execute(
            """
            UPDATE document_artifact SET
                sha256=?, mime_type=?, page_count=?, storage_path=?,
                source_url=?, acquisition_method=?, rights_tier=?,
                access_state=?, acquired_at=?
            WHERE artifact_id=?
            """,
            (*values, artifact_id),
        )

    representations_upserted = 0
    representation = publication.get("text_representation")
    if isinstance(representation, Mapping):
        text_sha256 = _text(representation.get("text_sha256"))
        parent_sha256 = _text(representation.get("parent_artifact_sha256"))
        if parent_sha256 and parent_sha256 != artifact_sha256:
            raise PropertyIngestError(
                "publication text representation does not reference its "
                "official parent artifact"
            )
        method = _text(representation.get("method")) or "unspecified_text"
        if text_sha256:
            representation_type = (
                "embedded_pdf_text" if method == "embedded_pdf_text" else "derived_text"
            )
            representation_details = dict(representation)
            for field in (
                "text_state",
                "searchable_text_char_count",
                "page_searchable_char_counts",
            ):
                if publication.get(field) is not None:
                    representation_details[field] = publication[field]
            existing_representation = db.execute(
                """
                SELECT representation_id
                FROM evidence_representation
                WHERE artifact_id=? AND representation_type=?
                  AND COALESCE(content_hash, '')=?
                  AND COALESCE(model_or_parser, '')=?
                """,
                (
                    artifact_id,
                    representation_type,
                    text_sha256,
                    method,
                ),
            ).fetchone()
            if existing_representation is None:
                db.execute(
                    """
                    INSERT INTO evidence_representation(
                        artifact_id, representation_type, content_hash,
                        model_or_parser, structured_json, review_status
                    ) VALUES (?, ?, ?, ?, ?, 'unreviewed')
                    """,
                    (
                        artifact_id,
                        representation_type,
                        text_sha256,
                        method,
                        canonical_json(representation_details),
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE evidence_representation
                    SET structured_json=?
                    WHERE representation_id=?
                    """,
                    (
                        canonical_json(representation_details),
                        int(existing_representation["representation_id"]),
                    ),
                )
            representations_upserted = 1
    return {
        "artifact_id": artifact_id,
        "native_document_id": document_id,
        "artifact_sha256": artifact_sha256,
        "artifacts_upserted": 1,
        "representations_upserted": representations_upserted,
    }


def _ingest_oregon_tax_publication_envelope(
    db,
    *,
    envelope: Mapping[str, Any],
    source_id: str,
    retrieved_at: str,
) -> dict[str, Any] | None:
    publication = _oregon_tax_publication_snapshot(envelope)
    if not publication:
        return None
    if not _text(publication.get("artifact_sha256")):
        raw_refs = envelope.get("raw_artifact_refs")
        if isinstance(raw_refs, list) and raw_refs:
            publication["artifact_sha256"] = _text(raw_refs[0])
    geoid, jurisdiction_name, state_code = OREGON_TAX_FORECLOSURE_SCOPES[source_id]
    _upsert_jurisdiction_values(
        db,
        geoid=geoid,
        name=jurisdiction_name,
        state_code=state_code,
        jurisdiction_type="county",
        parent_geoid=geoid[:2],
    )
    return _upsert_oregon_tax_publication_artifact(
        db,
        source_id=source_id,
        jurisdiction_geoid=geoid,
        publication=publication,
        retrieved_at=retrieved_at,
    )


def _oregon_tax_publication_event_date(
    record: Mapping[str, Any],
    process_stage: str,
) -> str | None:
    fields_by_stage = {
        "foreclosure_list_published": (
            "advertising_date",
            "publication_date",
            "general_judgment_date",
        ),
        "statutory_redemption_notice": (
            "notice_date",
            "publication_date",
            "judgment_date",
        ),
        "end_of_redemption_notice": (
            "notice_date",
            "publication_date",
            "judgment_date",
        ),
        "tax_title_inventory": (
            "inventory_as_of_date",
            "property_received_date",
            "publication_date",
        ),
        "sale_authorization": ("publication_date",),
        "auction_offering": ("auction_date", "publication_date"),
        "auction_results": ("auction_date", "publication_date"),
        "judgment_in_progress": ("publication_date",),
    }
    for field in fields_by_stage.get(process_stage, ("publication_date",)):
        value = _date_prefix(record.get(field))
        if value:
            return value
    return None


def _oregon_tax_publication_amount(
    record: Mapping[str, Any],
    process_stage: str,
) -> Any:
    amounts = record.get("amounts")
    if isinstance(amounts, Mapping):
        if process_stage in {
            "statutory_redemption_notice",
            "end_of_redemption_notice",
        }:
            return amounts.get("total_due_as_published")
        if process_stage == "tax_title_inventory":
            return amounts.get("total_decree")
    if process_stage == "auction_offering":
        return record.get("minimum_bid")
    if process_stage == "auction_results":
        return record.get("final_bid")
    return None


def _ingest_oregon_tax_foreclosure_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    process_stage = _text(record.get("process_stage"))
    if not process_stage:
        raise PropertyIngestError(
            "Oregon tax-foreclosure publication record lacks process_stage"
        )
    identifier_fields = {
        "us-or-tillamook-tax-foreclosure-publications": (
            "property_map_id",
            "tax_account",
            "stable_property_key",
        ),
        "us-or-marion-tax-foreclosure-publications": (
            "map_tax_lot",
            "tax_account",
            "stable_property_key",
        ),
        "us-or-multnomah-tax-foreclosure-publications": (
            "real_property_id",
            "map_id",
            "stable_property_key",
        ),
        "us-or-clackamas-tax-foreclosure-publications": (
            "map_tax_lot",
            "stable_property_key",
        ),
    }
    native_parcel_id = next(
        (
            value
            for field in identifier_fields[source_id]
            if (value := _text(record.get(field)))
        ),
        None,
    )
    if not native_parcel_id:
        raise PropertyIngestError(
            f"{source_id} publication record lacks a stable property key"
        )

    expected_geoid, jurisdiction_name, state_code = OREGON_TAX_FORECLOSURE_SCOPES[
        source_id
    ]
    jurisdiction_geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid=expected_geoid,
        fallback_name=jurisdiction_name,
        fallback_state_code=state_code,
    )
    if jurisdiction_geoid != expected_geoid:
        raise PropertyIngestError(
            f"{source_id} publication record has out-of-scope GEOID "
            f"{jurisdiction_geoid}"
        )

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    publication_document_id = _text(record.get("publication_document_id"))
    stable_property_key = _text(record.get("stable_property_key")) or native_parcel_id
    native_event_id = ":".join(
        value
        for value in (
            publication_document_id or "",
            stable_property_key,
        )
        if value
    )
    event_date = _oregon_tax_publication_event_date(record, process_stage)
    publication_year = _text(
        record.get("foreclosure_tax_year") or record.get("publication_year")
    )
    if not publication_year and event_date:
        publication_year = event_date[:4]
    publication_year = (publication_year or "")[:4]
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_event_id,
        record_kind=(
            _text(record.get("record_kind")) or "property_tax_foreclosure_publication"
        ),
        query_fingerprint=query_fingerprint,
        source_url=(
            _text(record.get("document_url"))
            or _text(record.get("publication_page_url"))
            or _record_source_url(envelope, record)
        ),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=(
            _text(record.get("artifact_sha256")) or raw_artifact_sha256
        ),
        warnings=warnings,
    )
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid=jurisdiction_geoid,
        native_parcel_id=native_parcel_id,
        roll_year=publication_year,
        effective_from=event_date,
        source_good_through=(
            _date_prefix(record.get("inventory_as_of_date")) or event_date
        ),
        observation_id=observation_id,
        record=record,
    )
    effective_from = event_date or publication_year
    alias_fields = {
        "tax_account": record.get("tax_account"),
        "map_tax_lot": record.get("map_tax_lot"),
        "property_map_id": record.get("property_map_id"),
        "map_id": record.get("map_id"),
        "real_property_id": record.get("real_property_id"),
        "court_case_number": record.get("court_case_number"),
    }
    aliases_inserted = sum(
        _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=effective_from,
        )
        for alias_type, alias_value in alias_fields.items()
    )

    addresses_inserted = 0
    for role, field in (
        ("situs", "situs_address"),
        ("situs", "street_address"),
        ("mailing", "mailing_address"),
    ):
        address_value = record.get(field)
        if isinstance(address_value, Mapping):
            address = dict(address_value)
        elif _text(address_value):
            address = {"raw": _text(address_value)}
        else:
            continue
        addresses_inserted += int(
            _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                role=role,
                address=address,
                effective_from=effective_from,
            )
        )

    owner_values: list[str] = []
    for field in ("property_owner", "owner_as_shown_on_tax_roll"):
        value = _text(record.get(field))
        if value and value not in owner_values:
            owner_values.append(value)
    published_names = record.get("published_name_lines")
    if isinstance(published_names, list):
        for raw_name in published_names:
            value = _text(raw_name)
            if value and value not in owner_values:
                owner_values.append(value)
    elif (value := _text(record.get("published_name"))) and value not in owner_values:
        owner_values.append(value)
    evidence_ref = canonical_property_ref(
        source_id,
        jurisdiction_geoid,
        "tax-publication-event",
        native_event_id,
    )
    owners_upserted = sum(
        _upsert_tax_account_owner(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            raw_name=raw_name,
            effective_from=effective_from,
            observation_id=observation_id,
            evidence_ref=evidence_ref,
        )
        for raw_name in owner_values
    )
    event_status = (
        _text(record.get("inventory_status"))
        or _text(record.get("auction_result"))
        or _text(record.get("publication_status"))
        or "as_published"
    )
    tax_events_upserted = _upsert_tax_account_event(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        event_type=process_stage,
        tax_year=publication_year,
        event_date=event_date,
        amount=_oregon_tax_publication_amount(record, process_stage),
        status=event_status,
        native_event_id=native_event_id,
        observation_id=observation_id,
        raw=record,
    )
    artifact_projection = _upsert_oregon_tax_publication_artifact(
        db,
        source_id=source_id,
        jurisdiction_geoid=jurisdiction_geoid,
        publication=record,
        retrieved_at=retrieved_at,
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": evidence_ref,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "process_stage": process_stage,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "owners_upserted": owners_upserted,
        "tax_events_upserted": tax_events_upserted,
        **artifact_projection,
    }


def _ingest_cook_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    native_parcel_id = _text(record.get("native_parcel_id"))
    tax_year = _text(record.get("tax_year"))
    if not native_parcel_id or not tax_year:
        raise PropertyIngestError(
            "Cook County record requires native_parcel_id and tax_year"
        )
    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="17031",
        fallback_name="Cook County",
        fallback_state_code="IL",
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_native_id = _text(record.get("source_row_id")) or (
        f"{native_parcel_id}:{tax_year}"
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind="parcel_snapshot",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid=geoid,
        native_parcel_id=native_parcel_id,
        roll_year=tax_year,
        effective_from=None,
        source_good_through=None,
        observation_id=observation_id,
        record=record,
    )
    aliases_inserted = 0
    pin10 = _text(record.get("pin10"))
    if pin10 and pin10 != native_parcel_id:
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="pin10",
            alias_value=pin10,
            source_id=source_id,
            effective_from=tax_year,
        )

    assessments_upserted = _upsert_assessment_projection(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        tax_year=tax_year,
        assessment_class=record.get("property_class"),
        source_good_through=None,
        observation_id=observation_id,
        raw={
            "tax_year": tax_year,
            "property_class": record.get("property_class"),
            "assessor_geography": record.get("assessor_geography"),
        },
    )
    location = record.get("situs_location")
    geometry_upserted = 0
    if isinstance(location, Mapping):
        centroid = location.get("centroid")
        if isinstance(centroid, Mapping):
            geometry_upserted = _upsert_point_geometry(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                longitude=centroid.get("longitude"),
                latitude=centroid.get("latitude"),
                snapshot_date=tax_year,
            )
    owner_observation = record.get("owner_observation")
    owner_state = (
        _text(owner_observation.get("state"))
        if isinstance(owner_observation, Mapping)
        else None
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id, geoid, "parcel", native_parcel_id
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": 0,
        "assessments_upserted": assessments_upserted,
        "owners_upserted": 0,
        "owner_visibility_state": owner_state,
        "sales_upserted": 0,
        "geometry_upserted": geometry_upserted,
    }


def _maryland_sale_id(sale: Mapping[str, Any]) -> str:
    transfer_number = _text(sale.get("transfer_number"))
    if transfer_number:
        return f"transfer:{transfer_number}"
    deed = sale.get("deed_reference")
    if isinstance(deed, Mapping):
        liber = _text(deed.get("liber"))
        folio = _text(deed.get("folio"))
        if liber or folio:
            return f"deed:{liber or ''}:{folio or ''}"
    segment = _text(sale.get("segment")) or ""
    transfer_date = _text(sale.get("transfer_date")) or ""
    return f"segment:{segment}:{transfer_date}:{sha256_fingerprint(sale)[:16]}"


def _existing_maryland_parcel(
    db,
    *,
    jurisdiction_geoid: str,
    native_parcel_id: str,
):
    """Resolve an exact ACCTID, preferring the canonical SDAT representation."""

    return db.execute(
        """
        SELECT parcel_id, source_id, roll_year
        FROM parcel_snapshot
        WHERE jurisdiction_geoid=? AND native_parcel_id=?
          AND source_id IN (?, ?)
        ORDER BY
          CASE WHEN source_id=? THEN 0 ELSE 1 END,
          CASE WHEN roll_year='' THEN 1 ELSE 0 END,
          roll_year DESC,
          parcel_id DESC
        LIMIT 1
        """,
        (
            jurisdiction_geoid,
            native_parcel_id,
            MD_PROPERTY_SOURCE_ID,
            MD_MDP_PARCEL_POINTS_SOURCE_ID,
            MD_PROPERTY_SOURCE_ID,
        ),
    ).fetchone()


def _ingest_md_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        raise PropertyIngestError("Maryland record lacks native_parcel_id")
    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="24",
        fallback_name="Maryland",
        fallback_state_code="MD",
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_good_through = _text(record.get("source_record_updated"))
    assessment = record.get("assessment")
    tax_year = (
        _text(assessment.get("cycle_year")) if isinstance(assessment, Mapping) else None
    ) or ""
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_parcel_id,
        record_kind="parcel_snapshot",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    canonical_row = db.execute(
        """
        SELECT parcel_id
        FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=?
        """,
        (source_id, geoid, native_parcel_id, tax_year),
    ).fetchone()
    adopted_shell_source_id = None
    if canonical_row is not None:
        parcel_id = _upsert_parcel_snapshot(
            db,
            source_id=source_id,
            jurisdiction_geoid=geoid,
            native_parcel_id=native_parcel_id,
            roll_year=tax_year,
            effective_from=source_good_through,
            source_good_through=source_good_through,
            observation_id=observation_id,
            record=record,
        )
    else:
        shell_row = db.execute(
            """
            SELECT parcel_id, source_id
            FROM parcel_snapshot
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_parcel_id=? AND roll_year=''
            ORDER BY parcel_id
            LIMIT 1
            """,
            (
                MD_MDP_PARCEL_POINTS_SOURCE_ID,
                geoid,
                native_parcel_id,
            ),
        ).fetchone()
        if shell_row is None:
            parcel_id = _upsert_parcel_snapshot(
                db,
                source_id=source_id,
                jurisdiction_geoid=geoid,
                native_parcel_id=native_parcel_id,
                roll_year=tax_year,
                effective_from=source_good_through,
                source_good_through=source_good_through,
                observation_id=observation_id,
                record=record,
            )
        else:
            parcel_id = int(shell_row["parcel_id"])
            adopted_shell_source_id = _text(shell_row["source_id"])
            db.execute(
                """
                UPDATE parcel_snapshot SET
                    source_id=?,
                    roll_year=?,
                    effective_from=?,
                    source_good_through=?,
                    observation_id=?,
                    raw_json=?
                WHERE parcel_id=?
                """,
                (
                    source_id,
                    tax_year,
                    source_good_through,
                    source_good_through,
                    observation_id,
                    canonical_json(record),
                    parcel_id,
                ),
            )

    aliases_inserted = 0
    record_key = record.get("record_key")
    if isinstance(record_key, Mapping):
        account_number = _text(record_key.get("account_number"))
        if account_number and account_number != native_parcel_id:
            aliases_inserted += _upsert_alias(
                db,
                parcel_id=parcel_id,
                alias_type="account_number",
                alias_value=account_number,
                source_id=source_id,
                effective_from=source_good_through or tax_year,
            )

    addresses_inserted = 0
    situs_address = record.get("situs_address")
    if isinstance(situs_address, Mapping):
        addresses_inserted = int(
            _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                role="situs",
                address=situs_address,
                effective_from=source_good_through or tax_year,
            )
        )

    assessments_upserted = 0
    if isinstance(assessment, Mapping) and any(
        assessment.get(field) not in (None, "")
        for field in (
            "cycle_year",
            "current_land_value",
            "current_improvement_value",
            "current_total_assessment",
        )
    ):
        assessments_upserted = _upsert_assessment_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=tax_year,
            land_value=assessment.get("current_land_value"),
            improvement_value=assessment.get("current_improvement_value"),
            total_value=assessment.get("current_total_assessment"),
            assessed_value=assessment.get("current_total_assessment"),
            source_good_through=source_good_through,
            observation_id=observation_id,
            raw=assessment,
        )

    sales = record.get("sales_history", [])
    if not isinstance(sales, list):
        raise PropertyIngestError("record.sales_history must be a list")
    sales_upserted = 0
    for index, sale_value in enumerate(sales):
        sale = _mapping(sale_value, f"record.sales_history[{index}]")
        sales_upserted += _upsert_sale_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            native_sale_id=_maryland_sale_id(sale),
            sale_date=_text(sale.get("transfer_date")),
            consideration=sale.get("consideration"),
            derivation="assessment_sales_history",
            observation_id=observation_id,
            raw=sale,
        )

    location = record.get("location")
    geometry_upserted = 0
    if isinstance(location, Mapping):
        geometry_upserted = _upsert_point_geometry(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            longitude=location.get("longitude"),
            latitude=location.get("latitude"),
            snapshot_date=source_good_through or tax_year,
        )

    owner_visibility = record.get("owner_visibility")
    owner_state = (
        _text(owner_visibility.get("state"))
        if isinstance(owner_visibility, Mapping)
        else None
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id, geoid, "parcel", native_parcel_id
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "owners_upserted": 0,
        "owner_visibility_state": owner_state,
        "sales_upserted": sales_upserted,
        "geometry_upserted": geometry_upserted,
        "parcel_shell_adopted": int(adopted_shell_source_id is not None),
        "parcel_shell_source_id_adopted": adopted_shell_source_id,
    }


def _md_plats_identity(
    record: Mapping[str, Any],
) -> tuple[dict[str, str], str] | None:
    value = record.get("record_identity")
    if value is None:
        return None
    identity = _mapping(value, "record.record_identity")
    keys = (
        "county_code",
        "archive_qualifier",
        "archive_series",
        "archive_unit",
        "msa_accession",
    )
    normalized = {key: _text(identity.get(key)) for key in keys}
    if any(value is None for value in normalized.values()):
        raise PropertyIngestError(
            "Maryland Plats record identity is incomplete"
        )
    county_code = str(normalized["county_code"]).upper()
    qualifier = str(normalized["archive_qualifier"]).upper()
    series = str(normalized["archive_series"])
    unit = str(normalized["archive_unit"])
    accession = str(normalized["msa_accession"])
    if county_code not in query_md_plats.COUNTY_GEOIDS:
        raise PropertyIngestError(
            "Maryland Plats record uses an unknown county code"
        )
    if qualifier not in {"C", "S"}:
        raise PropertyIngestError(
            "Maryland Plats record uses an unknown archive qualifier"
        )
    expected_accession = f"MSA {qualifier}{series}-{unit}"
    if " ".join(accession.upper().split()) != expected_accession.upper():
        raise PropertyIngestError(
            "Maryland Plats accession conflicts with its archive identity"
        )
    stable_identity = {
        "county_code": county_code,
        "archive_qualifier": qualifier,
        "archive_series": series,
        "archive_unit": unit,
        "msa_accession": expected_accession,
    }
    return stable_identity, f"{county_code}:{qualifier}{series}-{unit}"


def _md_plats_record_url(
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
) -> str | None:
    direct = _text(record.get("source_url"))
    if direct:
        return direct
    provenance = record.get("provenance")
    if isinstance(provenance, Mapping):
        source_url = _text(provenance.get("source_url"))
        if source_url:
            return source_url
    return _record_url(envelope)


def _md_plats_jurisdiction(
    db,
    *,
    record: Mapping[str, Any],
    identity: Mapping[str, str] | None,
) -> str:
    county_code = identity.get("county_code") if identity else None
    if county_code is None:
        county_identity = record.get("county_identity")
        if isinstance(county_identity, Mapping):
            county_code = _text(
                county_identity.get("source_county_code")
            )
    if county_code is None:
        return _upsert_jurisdiction_values(
            db,
            geoid="24",
            name="Maryland",
            state_code="MD",
            jurisdiction_type="state",
        )
    code = county_code.upper()
    try:
        geoid, county_name = query_md_plats.COUNTY_GEOIDS[code]
    except KeyError as error:
        raise PropertyIngestError(
            "Maryland Plats record uses an unknown county code"
        ) from error
    return _upsert_jurisdiction_values(
        db,
        geoid=geoid,
        name=county_name,
        state_code="MD",
        jurisdiction_type=(
            "independent_city" if geoid == "24510" else "county"
        ),
        parent_geoid="24",
    )


def _upsert_md_plats_artifact(
    db,
    *,
    jurisdiction_geoid: str,
    native_document_id: str,
    sha256: str | None,
    mime_type: str | None,
    storage_path: str | None,
    source_url: str,
    acquisition_method: str,
    acquired_at: str | None,
    representation_type: str,
    structured: Mapping[str, Any],
) -> int:
    if sha256 is None:
        existing = db.execute(
            """
            SELECT artifact_id
            FROM document_artifact
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_document_id=? AND sha256 IS NULL
            ORDER BY artifact_id DESC
            LIMIT 1
            """,
            (
                MD_PLATS_SOURCE_ID,
                jurisdiction_geoid,
                native_document_id,
            ),
        ).fetchone()
    else:
        existing = db.execute(
            """
            SELECT artifact_id
            FROM document_artifact
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_document_id=? AND sha256=?
            ORDER BY artifact_id DESC
            LIMIT 1
            """,
            (
                MD_PLATS_SOURCE_ID,
                jurisdiction_geoid,
                native_document_id,
                sha256,
            ),
        ).fetchone()
    values = (
        sha256,
        mime_type,
        storage_path,
        source_url,
        acquisition_method,
        acquired_at,
    )
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, ?, ?, NULL, ?, ?, NULL, ?, ?, ?,
                      'official_archive_plat_representation',
                      'public', ?)
            """,
            (
                MD_PLATS_SOURCE_ID,
                jurisdiction_geoid,
                native_document_id,
                *values,
            ),
        )
        artifact_id = int(cursor.lastrowid)
    else:
        artifact_id = int(existing["artifact_id"])
        db.execute(
            """
            UPDATE document_artifact SET
                instrument_id=NULL,
                sha256=?,
                mime_type=?,
                page_count=NULL,
                storage_path=?,
                source_url=?,
                acquisition_method=?,
                rights_tier='official_archive_plat_representation',
                access_state='public',
                acquired_at=?
            WHERE artifact_id=?
            """,
            (*values, artifact_id),
        )
    db.execute(
        """
        DELETE FROM evidence_representation
        WHERE artifact_id=? AND representation_type=?
        """,
        (artifact_id, representation_type),
    )
    db.execute(
        """
        INSERT INTO evidence_representation(
            artifact_id, representation_type, content_hash,
            model_or_parser, model_or_parser_version,
            prompt_or_schema_version, extraction_confidence,
            page_locator, region_locator, source_quote,
            structured_json, review_status
        ) VALUES (?, ?, ?, 'query_md_plats', NULL, ?, NULL,
                  NULL, NULL, NULL, ?, 'unreviewed')
        """,
        (
            artifact_id,
            representation_type,
            sha256,
            query_md_plats.OUTPUT_SCHEMA_VERSION,
            canonical_json(structured),
        ),
    )
    return artifact_id


def _ingest_md_plats_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve plat identities and files without deriving title ownership."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind")) or "source_row"
    parsed_identity = _md_plats_identity(record)
    identity = parsed_identity[0] if parsed_identity else None
    native_plat_id = parsed_identity[1] if parsed_identity else None
    jurisdiction_geoid = _md_plats_jurisdiction(
        db,
        record=record,
        identity=identity,
    )
    occurrence = record.get("result_occurrence")
    occurrence_id = (
        _text(occurrence.get("occurrence_identity"))
        if isinstance(occurrence, Mapping)
        else None
    )
    if (
        record_kind == "recorded_plat_search_occurrence"
        and occurrence_id is None
    ):
        raise PropertyIngestError(
            "Maryland Plats search row lacks its query occurrence identity"
        )
    if record_kind in {
        "recorded_plat_search_occurrence",
        "recorded_plat_detail",
    } and native_plat_id is None:
        raise PropertyIngestError(
            "Maryland Plats record lacks its archive identity"
        )

    if record_kind == "recorded_plat_search_occurrence":
        source_native_id = occurrence_id
    elif record_kind == "recorded_plat_detail":
        source_native_id = native_plat_id
    elif record_kind == "plat_artifact_download":
        source_native_id = _text(
            record.get("source_artifact_locator_identity")
        )
    elif record_kind == "plat_county_route":
        county_identity = record.get("county_identity")
        source_native_id = (
            _text(county_identity.get("source_county_code"))
            if isinstance(county_identity, Mapping)
            else None
        )
    else:
        source_native_id = _text(record.get("canonical_ref"))
    source_native_id = source_native_id or sha256_fingerprint(record)

    query_fingerprint, retrieved_at, status, warnings = (
        _observation_context(envelope)
    )
    observation_sha256 = (
        _text(record.get("content_sha256"))
        if record_kind == "plat_artifact_download"
        else raw_artifact_sha256
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_md_plats_record_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=observation_sha256,
        warnings=warnings,
    )

    artifact_ids: list[int] = []
    metadata_only = False
    if record_kind == "recorded_plat_search_occurrence":
        representation = record.get("source_result_representation")
        if not isinstance(representation, Mapping):
            raise PropertyIngestError(
                "Maryland Plats search row lacks its result representation"
            )
        metadata_only = (
            _text(representation.get("image_availability"))
            == "metadata_only"
        )
    elif record_kind == "recorded_plat_detail":
        metadata_only = (
            _text(record.get("image_availability")) == "metadata_only"
        )
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, list):
            raise PropertyIngestError(
                "Maryland Plats detail artifacts must be a list"
            )
        for index, value in enumerate(artifacts):
            artifact = _mapping(
                value,
                f"record.artifacts[{index}]",
            )
            artifact_identity = _text(
                artifact.get("artifact_identity")
            )
            source_url = _text(artifact.get("source_url"))
            if not artifact_identity or not source_url:
                raise PropertyIngestError(
                    "Maryland Plats artifact lacks identity or source URL"
                )
            artifact_ids.append(
                _upsert_md_plats_artifact(
                    db,
                    jurisdiction_geoid=jurisdiction_geoid,
                    native_document_id=(
                        f"{native_plat_id}:{artifact_identity}"
                    ),
                    sha256=None,
                    mime_type=_text(artifact.get("media_type")),
                    storage_path=None,
                    source_url=source_url,
                    acquisition_method=(
                        "source_published_plat_representation"
                    ),
                    acquired_at=None,
                    representation_type="plat_artifact_metadata",
                    structured={
                        "record_identity": identity,
                        "artifact": dict(artifact),
                    },
                )
            )
    elif record_kind == "plat_artifact_download":
        locator_identity = _text(
            record.get("source_artifact_locator_identity")
        )
        source_url = _text(record.get("source_url"))
        content_sha256 = _text(record.get("content_sha256"))
        if not locator_identity or not source_url or not content_sha256:
            raise PropertyIngestError(
                "Maryland Plats download lacks locator, URL, or content hash"
            )
        artifact_ids.append(
            _upsert_md_plats_artifact(
                db,
                jurisdiction_geoid=jurisdiction_geoid,
                native_document_id=locator_identity,
                sha256=content_sha256,
                mime_type=_text(record.get("media_type")),
                storage_path=_text(record.get("local_path")),
                source_url=source_url,
                acquisition_method="direct_source_artifact_download",
                acquired_at=retrieved_at,
                representation_type="downloaded_plat_artifact",
                structured=dict(record),
            )
        )

    if record_kind not in {
        "recorded_plat_search_occurrence",
        "recorded_plat_detail",
        "plat_artifact_download",
    }:
        return {
            "projection_skipped": True,
            "reason": "maryland_plats_non_record_observation",
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "record_kind": record_kind,
        }
    return {
        "canonical_ref": _text(record.get("canonical_ref")),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "record_kind": record_kind,
        "native_plat_id": native_plat_id,
        "result_occurrence_id": occurrence_id,
        "metadata_only": metadata_only,
        "artifacts_upserted": len(artifact_ids),
        "artifact_ids": artifact_ids,
        "recorded_instruments_upserted": 0,
        "recorded_title_assertions_upserted": 0,
        "parcel_owner_assertions_upserted": 0,
        "parcel_links_upserted": 0,
    }


def _md_mdp_source_good_through(
    record: Mapping[str, Any],
    *,
    retrieved_at: str,
) -> str:
    freshness = record.get("freshness")
    if isinstance(freshness, Mapping):
        for key in (
            "sdat_linkage_date",
            "mdp_product_publication_date",
        ):
            observation = freshness.get(key)
            if isinstance(observation, Mapping):
                normalized = _text(
                    observation.get("normalized") or observation.get("raw")
                )
                if normalized:
                    return normalized
    return _date_prefix(retrieved_at) or retrieved_at


def _ingest_md_mdp_parcel_point_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one MDP point occurrence onto the exact shared SDAT ACCTID."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_kind")) != "parcel_assessment_point_snapshot":
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="mdp_row_is_not_a_parcel_assessment_point_snapshot",
        )
    if _text(record.get("record_identity_source_id")) != MD_PROPERTY_SOURCE_ID:
        raise PropertyIngestError(
            "Maryland Parcel Points record does not declare the SDAT "
            "ACCTID identity source"
        )
    native_parcel_id = _text(record.get("native_parcel_id"))
    source_occurrence_id = _text(record.get("source_occurrence_id"))
    if not native_parcel_id or not source_occurrence_id:
        raise PropertyIngestError(
            "Maryland Parcel Points record requires ACCTID and OBJECTID occurrence"
        )
    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="24",
        fallback_name="Maryland",
        fallback_state_code="MD",
    )
    if not geoid.startswith("24"):
        raise PropertyIngestError(
            f"Maryland Parcel Points record has out-of-scope GEOID {geoid}"
        )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_good_through = _md_mdp_source_good_through(
        record,
        retrieved_at=retrieved_at,
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_occurrence_id,
        record_kind="parcel_assessment_point_snapshot",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    parcel_row = _existing_maryland_parcel(
        db,
        jurisdiction_geoid=geoid,
        native_parcel_id=native_parcel_id,
    )
    placeholder_created = parcel_row is None
    if parcel_row is None:
        parcel_id = _upsert_parcel_snapshot(
            db,
            source_id=source_id,
            jurisdiction_geoid=geoid,
            native_parcel_id=native_parcel_id,
            roll_year="",
            effective_from=source_good_through,
            source_good_through=source_good_through,
            observation_id=observation_id,
            record=record,
        )
        parcel_anchor_source_id = source_id
    else:
        parcel_id = int(parcel_row["parcel_id"])
        parcel_anchor_source_id = _text(parcel_row["source_id"]) or source_id

    effective_from = source_good_through or retrieved_at
    published_identifiers = record.get("published_identifiers")
    if not isinstance(published_identifiers, Mapping):
        published_identifiers = {}
    aliases_inserted = 0
    for alias_type, field_name in (
        ("md_jurisdiction_code", "jurisdiction_code"),
        ("md_map", "map"),
        ("md_grid", "grid"),
        ("md_parcel", "parcel"),
        ("md_plat", "plat"),
    ):
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=published_identifiers.get(field_name),
            source_id=source_id,
            effective_from=effective_from,
        )

    addresses_inserted = 0
    for role, field_name in (
        ("situs", "situs_address"),
        ("mailing", "mailing_address"),
    ):
        address = record.get(field_name)
        if isinstance(address, Mapping):
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role=role,
                    address=address,
                    effective_from=effective_from,
                )
            )

    appraisal = record.get("appraisal")
    assessments_upserted = 0
    if isinstance(appraisal, Mapping) and any(
        appraisal.get(field_name) not in (None, "")
        for field_name in (
            "new_appraised_land_value",
            "new_appraised_improvement_value",
            "new_appraised_full_value",
        )
    ):
        assessments_upserted = _upsert_assessment_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year="",
            land_value=appraisal.get("new_appraised_land_value"),
            improvement_value=appraisal.get(
                "new_appraised_improvement_value"
            ),
            total_value=appraisal.get("new_appraised_full_value"),
            market_value=appraisal.get("new_appraised_full_value"),
            source_good_through=source_good_through,
            observation_id=observation_id,
            raw={
                "appraisal": dict(appraisal),
                "freshness": record.get("freshness"),
            },
        )

    transfer = record.get("transfer")
    sales_upserted = 0
    if isinstance(transfer, Mapping):
        deed_reference = transfer.get("grantor_deed_reference")
        deed_reference = (
            dict(deed_reference)
            if isinstance(deed_reference, Mapping)
            else {}
        )
        transfer_projection = {
            **dict(transfer),
            "segment": "mdp_parcel_points",
            "deed_reference": deed_reference,
        }
        if any(
            (
                _text(transfer.get("transfer_date")),
                transfer.get("consideration")
                if transfer.get("consideration") not in (None, "")
                else None,
                _text(transfer.get("conveyance_code")),
                _text(deed_reference.get("liber")),
                _text(deed_reference.get("folio")),
            )
        ):
            sales_upserted = _upsert_sale_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                native_sale_id=_maryland_sale_id(transfer_projection),
                sale_date=_text(transfer.get("transfer_date")),
                consideration=transfer.get("consideration"),
                derivation="mdp_parcel_points_transfer_reference",
                observation_id=observation_id,
                raw=transfer_projection,
            )

    geometry_upserted = 0
    geometry = record.get("geometry")
    if isinstance(geometry, Mapping):
        geometry_crs = _text(record.get("geometry_crs"))
        if geometry_crs != "EPSG:4326":
            raise PropertyIngestError(
                "Maryland Parcel Points geometry is not normalized to EPSG:4326"
            )
        geometry_upserted = _upsert_point_geometry(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            longitude=geometry.get("x"),
            latitude=geometry.get("y"),
            snapshot_date=source_good_through,
            source_resolution="published_parcel_point",
        )

    owner_visibility = record.get("owner_visibility")
    owner_state = (
        _text(owner_visibility.get("state"))
        if isinstance(owner_visibility, Mapping)
        else None
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            MD_PROPERTY_SOURCE_ID,
            geoid,
            "parcel",
            native_parcel_id,
        ),
        "representation_ref": _text(record.get("representation_ref")),
        "record_identity_source_id": MD_PROPERTY_SOURCE_ID,
        "source_occurrence_id": source_occurrence_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "parcel_placeholder_created": int(placeholder_created),
        "parcel_anchor_source_id": parcel_anchor_source_id,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "sales_upserted": sales_upserted,
        "geometry_upserted": geometry_upserted,
        "owners_upserted": 0,
        "owner_visibility_state": owner_state,
        "recorded_instruments_upserted": 0,
    }


def _date_prefix(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    for date_format in (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text[:10]


def _acris_query_jurisdiction(
    db,
    envelope: Mapping[str, Any],
) -> str:
    query = _mapping(envelope.get("query"), "query")
    jurisdiction = query.get("jurisdiction")
    if not isinstance(jurisdiction, Mapping):
        jurisdiction = {}
    geoid = _text(jurisdiction.get("jurisdiction_id")) or "nyc-acris"
    name = _text(jurisdiction.get("name")) or "New York City ACRIS coverage"
    state_code = _text(jurisdiction.get("state_code")) or "NY"
    parent_geoid = geoid[:2] if geoid.isdigit() and len(geoid) == 5 else None
    jurisdiction_type = "county" if parent_geoid else "region"
    return _upsert_jurisdiction_values(
        db,
        geoid=geoid,
        name=name,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        parent_geoid=parent_geoid,
    )


def _acris_party_address(party: Mapping[str, Any]) -> str | None:
    pieces = [
        _text(party.get(field))
        for field in (
            "address_1",
            "address_2",
            "city",
            "state",
            "zip",
            "country",
        )
    ]
    return ", ".join(piece for piece in pieces if piece) or None


def _acris_legal_parcel_id(legal: Mapping[str, Any]) -> str | None:
    borough = _text(legal.get("borough"))
    block = _text(legal.get("block"))
    lot = _text(legal.get("lot"))
    if not (borough and block and lot):
        return None
    return f"{borough}-{block}-{lot}"


def _ingest_acris_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    document_id = _text(record.get("document_id"))
    if not document_id:
        raise PropertyIngestError("ACRIS record lacks document_id")
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    jurisdiction_geoid = _acris_query_jurisdiction(db, envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=document_id,
        record_kind="recorded_instrument",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    master_value = record.get("master")
    master = dict(master_value) if isinstance(master_value, Mapping) else {}
    legals_value = record.get("legals", [])
    if not isinstance(legals_value, list):
        raise PropertyIngestError("record.legals must be a list")
    legals = [
        _mapping(value, f"record.legals[{index}]")
        for index, value in enumerate(legals_value)
    ]
    legal_description = canonical_json(legals) if legals else None
    consideration = master.get("document_amt")
    db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id,
            instrument_type, book, page, execution_date, recording_date,
            consideration_minor, currency, legal_description_raw, source_url,
            observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
        DO UPDATE SET
            instrument_type=excluded.instrument_type,
            book=excluded.book,
            page=excluded.page,
            execution_date=excluded.execution_date,
            recording_date=excluded.recording_date,
            consideration_minor=excluded.consideration_minor,
            legal_description_raw=excluded.legal_description_raw,
            source_url=excluded.source_url,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            source_id,
            jurisdiction_geoid,
            document_id,
            _text(record.get("document_type") or master.get("doc_type")),
            _text(master.get("reel_nbr")),
            _text(master.get("reel_pg")),
            _date_prefix(master.get("document_date")),
            _date_prefix(master.get("recorded_datetime")),
            _minor_units(consideration),
            legal_description,
            _record_source_url(envelope, record),
            observation_id,
            canonical_json(record),
        ),
    )
    instrument_row = db.execute(
        """
        SELECT instrument_id FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (source_id, jurisdiction_geoid, document_id),
    ).fetchone()
    instrument_id = int(instrument_row["instrument_id"])

    parties_value = record.get("parties", [])
    if not isinstance(parties_value, list):
        raise PropertyIngestError("record.parties must be a list")
    parties_upserted = 0
    for index, party_value in enumerate(parties_value, start=1):
        party = _mapping(party_value, f"record.parties[{index - 1}]")
        raw_name = _text(party.get("name"))
        if not raw_name:
            continue
        party_type = _text(party.get("party_type"))
        role = ACRIS_PARTY_ROLES.get(
            party_type or "",
            f"party_type_{party_type}" if party_type else "other",
        )
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET
                normalized_name=excluded.normalized_name,
                entity_kind=excluded.entity_kind,
                raw_address=excluded.raw_address
            """,
            (
                instrument_id,
                index,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
                _text(party.get("party_type_desc")),
                _acris_party_address(party),
            ),
        )
        parties_upserted += 1

    parcels_upserted = 0
    addresses_inserted = 0
    sales_upserted = 0
    parcel_ids: set[int] = set()
    effective_from = (
        _date_prefix(master.get("recorded_datetime"))
        or _date_prefix(master.get("document_date"))
        or ""
    )
    for legal in legals:
        native_parcel_id = _acris_legal_parcel_id(legal)
        if not native_parcel_id:
            continue
        borough = _text(legal.get("borough")) or ""
        legal_geoid, legal_name = ACRIS_BOROUGH_METADATA.get(
            borough,
            (jurisdiction_geoid, "New York City ACRIS coverage"),
        )
        _upsert_jurisdiction_values(
            db,
            geoid=legal_geoid,
            name=legal_name,
            state_code="NY",
            jurisdiction_type="county" if legal_geoid.isdigit() else "region",
            parent_geoid=(
                legal_geoid[:2]
                if legal_geoid.isdigit() and len(legal_geoid) == 5
                else None
            ),
        )
        parcel_id = _upsert_parcel_snapshot(
            db,
            source_id=source_id,
            jurisdiction_geoid=legal_geoid,
            native_parcel_id=native_parcel_id,
            roll_year="",
            effective_from=effective_from or None,
            source_good_through=None,
            observation_id=observation_id,
            record=legal,
        )
        parcel_ids.add(parcel_id)
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, 'source_index_bbl', 1.0, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=excluded.legal_description_raw
            """,
            (instrument_id, parcel_id, canonical_json(legal)),
        )
        street = " ".join(
            value
            for value in (
                _text(legal.get("street_number")),
                _text(legal.get("street_name")),
            )
            if value
        )
        if street:
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role="situs",
                    address={
                        "raw": street,
                        "unit": legal.get("unit"),
                        "city": "New York",
                        "state": "NY",
                        "postal_code": None,
                    },
                    effective_from=effective_from,
                )
            )
        parcels_upserted += 1

    instrument_type = _text(record.get("document_type") or master.get("doc_type"))
    if instrument_type in {"DEED", "DEEDO"}:
        for parcel_id in parcel_ids:
            sales_upserted += _upsert_sale_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                native_sale_id=document_id,
                sale_date=_date_prefix(master.get("document_date")),
                consideration=consideration,
                derivation="recorded_instrument",
                instrument_id=instrument_id,
                observation_id=observation_id,
                raw=master or record,
            )

    return {
        "instrument_id": instrument_id,
        "canonical_ref": canonical_property_ref(
            source_id, jurisdiction_geoid, "instrument", document_id
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "parties_upserted": parties_upserted,
        "parcels_upserted": parcels_upserted,
        "addresses_inserted": addresses_inserted,
        "sales_upserted": sales_upserted,
    }


NYC_PIP_COMPONENT_BY_RECORD_KIND = {
    spec.record_kind: component
    for component, spec in query_nyc_pip.LAYER_SPECS.items()
}
NYC_PIP_BUNDLE_RECORD_KIND = "nyc_dof_property_information_bundle"


def _nyc_pip_occurrence_rank(value: Any) -> tuple[int, int | str]:
    text = _text(value) or ""
    if text.isdigit():
        return (0, int(text))
    return (1, text)


def _nyc_pip_identity(
    record: Mapping[str, Any],
) -> tuple[str, dict[str, Any], str, str | None]:
    """Validate and return the durable BBL plus optional layer occurrence."""

    try:
        bbl = query_nyc_pip.normalize_bbl(
            record.get("bbl") or record.get("native_parcel_id")
        )
    except ValueError as error:
        raise PropertyIngestError(f"invalid NYC PIP BBL: {error}") from error
    parts = query_nyc_pip.bbl_parts(bbl)
    native_parcel_id = _text(record.get("native_parcel_id"))
    if native_parcel_id is not None and native_parcel_id != bbl:
        raise PropertyIngestError("NYC PIP native_parcel_id conflicts with BBL")

    jurisdiction = record.get("jurisdiction")
    if not isinstance(jurisdiction, Mapping):
        raise PropertyIngestError("NYC PIP record jurisdiction must be an object")
    if _text(jurisdiction.get("county_geoid")) != parts["county_geoid"]:
        raise PropertyIngestError("NYC PIP county GEOID conflicts with BBL")

    expected_parcel_ref = canonical_property_ref(
        NYC_PIP_SOURCE_ID,
        parts["county_geoid"],
        "parcel",
        bbl,
    )
    if _text(record.get("parcel_canonical_ref")) != expected_parcel_ref:
        raise PropertyIngestError("NYC PIP parcel canonical reference changed")

    record_kind = _text(record.get("record_kind")) or ""
    if record_kind == NYC_PIP_BUNDLE_RECORD_KIND:
        if _text(record.get("canonical_ref")) != expected_parcel_ref:
            raise PropertyIngestError("NYC PIP bundle canonical reference changed")
        return bbl, parts, "bundle", None

    component = NYC_PIP_COMPONENT_BY_RECORD_KIND.get(record_kind)
    if component is None:
        raise PropertyIngestError(f"unsupported NYC PIP record kind: {record_kind!r}")
    object_id = _text(record.get("native_feature_id"))
    if not object_id:
        raise PropertyIngestError(f"NYC PIP {component} occurrence lacks OBJECTID")
    expected_occurrence_id = f"{component}:{bbl}:{object_id}"
    expected_occurrence_ref = canonical_property_ref(
        NYC_PIP_SOURCE_ID,
        parts["county_geoid"],
        f"{component}_occurrence",
        expected_occurrence_id,
    )
    if _text(record.get("canonical_ref")) != expected_occurrence_ref:
        raise PropertyIngestError(
            f"NYC PIP {component} occurrence canonical reference changed"
        )
    identity = record.get("identity")
    occurrence = (
        identity.get("layer_occurrence")
        if isinstance(identity, Mapping)
        else None
    )
    if (
        not isinstance(occurrence, Mapping)
        or _text(occurrence.get("component")) != component
        or _text(occurrence.get("object_id")) != object_id
    ):
        raise PropertyIngestError(
            f"NYC PIP {component} layer occurrence identity changed"
        )
    return bbl, parts, component, object_id


def _upsert_nyc_pip_parcel(
    db,
    *,
    bbl: str,
    parts: Mapping[str, Any],
) -> int:
    """Project every component onto one order-independent BBL parcel shell."""

    projection = {
        "record_kind": "nyc_dof_pip_parcel_identity",
        "source_id": NYC_PIP_SOURCE_ID,
        "bbl": bbl,
        "borough_code": parts["borough_code"],
        "borough_name": parts["borough_name"],
        "block": parts["block"],
        "lot": parts["lot"],
        "county_geoid": parts["county_geoid"],
        "projection_policy": (
            "durable BBL identity only; layer occurrences remain source observations"
        ),
    }
    db.execute(
        """
        INSERT INTO parcel_snapshot(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year,
            effective_from, source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, '', NULL, NULL, NULL, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_parcel_id, roll_year)
        DO UPDATE SET
            effective_from=NULL,
            source_good_through=NULL,
            observation_id=NULL,
            raw_json=excluded.raw_json
        """,
        (
            NYC_PIP_SOURCE_ID,
            parts["county_geoid"],
            bbl,
            canonical_json(projection),
        ),
    )
    row = db.execute(
        """
        SELECT parcel_id FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=''
        """,
        (NYC_PIP_SOURCE_ID, parts["county_geoid"], bbl),
    ).fetchone()
    return int(row["parcel_id"])


def _nyc_pip_observation_rank(db, observation_id: int | None) -> tuple[int, int | str]:
    if observation_id is None:
        return (2, "")
    row = db.execute(
        "SELECT source_native_id FROM source_observation WHERE observation_id=?",
        (observation_id,),
    ).fetchone()
    native_id = _text(row["source_native_id"]) if row is not None else None
    return _nyc_pip_occurrence_rank((native_id or "").rsplit(":", 1)[-1])


def _upsert_nyc_pip_owner(
    db,
    *,
    parcel_id: int,
    raw_name: str,
    effective_from: str,
    observation_id: int,
    evidence_ref: str,
) -> int:
    normalized_name = " ".join(raw_name.upper().split())
    existing = db.execute(
        """
        SELECT ownership_assertion_id, observation_id
        FROM ownership_assertion
        WHERE parcel_id=? AND source_id=?
          AND assertion_type='assessment_roll'
          AND normalized_owner_name=? AND effective_from=?
        ORDER BY ownership_assertion_id
        LIMIT 1
        """,
        (parcel_id, NYC_PIP_SOURCE_ID, normalized_name, effective_from),
    ).fetchone()
    if existing is not None:
        if _nyc_pip_observation_rank(db, observation_id) < _nyc_pip_observation_rank(
            db, existing["observation_id"]
        ):
            db.execute(
                """
                UPDATE ownership_assertion SET
                    raw_owner_name=?, confidence='confirmed',
                    claim_type='direct_quote', observation_id=?,
                    evidence_ref=?, source_quote=?
                WHERE ownership_assertion_id=?
                """,
                (
                    raw_name,
                    observation_id,
                    evidence_ref,
                    raw_name,
                    int(existing["ownership_assertion_id"]),
                ),
            )
        return 0
    db.execute(
        """
        INSERT INTO ownership_assertion(
            parcel_id, source_id, assertion_type, raw_owner_name,
            normalized_owner_name, effective_from, effective_to,
            confidence, claim_type, observation_id, evidence_ref, source_quote
        ) VALUES (
            ?, ?, 'assessment_roll', ?, ?, ?, NULL,
            'confirmed', 'direct_quote', ?, ?, ?
        )
        """,
        (
            parcel_id,
            NYC_PIP_SOURCE_ID,
            raw_name,
            normalized_name,
            effective_from,
            observation_id,
            evidence_ref,
            raw_name,
        ),
    )
    return 1


def _upsert_nyc_pip_geometry(
    db,
    *,
    parcel_id: int,
    bbl: str,
    object_id: str,
    record: Mapping[str, Any],
) -> int:
    geometry = record.get("geometry")
    if not isinstance(geometry, Mapping):
        return 0
    existing = db.execute(
        """
        SELECT geometry_ref FROM parcel_geometry
        WHERE parcel_id=? AND source_id=? AND snapshot_date=''
        """,
        (parcel_id, NYC_PIP_SOURCE_ID),
    ).fetchone()
    if existing is not None:
        existing_id = str(existing["geometry_ref"]).split("#", 1)[0].rsplit(":", 1)[-1]
        if _nyc_pip_occurrence_rank(object_id) >= _nyc_pip_occurrence_rank(existing_id):
            return 0
    geometry_ref = (
        f"source-occurrence:{NYC_PIP_SOURCE_ID}:tax_lot:{bbl}:{object_id}#/geometry"
    )
    db.execute(
        """
        INSERT INTO parcel_geometry(
            parcel_id, geometry_ref, geometry_format, crs,
            source_resolution, accuracy_disclaimer, source_id, snapshot_date
        ) VALUES (?, ?, ?, ?, 'cadastral_tax_lot', ?, ?, '')
        ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
            geometry_ref=excluded.geometry_ref,
            geometry_format=excluded.geometry_format,
            crs=excluded.crs,
            source_resolution=excluded.source_resolution,
            accuracy_disclaimer=excluded.accuracy_disclaimer
        """,
        (
            parcel_id,
            geometry_ref,
            _text(record.get("geometry_format")) or "esri_json",
            _text(record.get("geometry_crs")) or "EPSG:4326",
            "NYC DOF cadastral tax-lot geometry; not a surveyed legal boundary",
            NYC_PIP_SOURCE_ID,
        ),
    )
    return 1


def _nyc_pip_assessment_rank(
    period: str,
    object_id: str,
) -> tuple[int, int | str, tuple[int, int | str]]:
    if period.isdigit():
        period_rank: tuple[int, int | str] = (0, -int(period))
    else:
        period_rank = (1, period)
    return (*period_rank, _nyc_pip_occurrence_rank(object_id))


def _upsert_nyc_pip_current_assessment(
    db,
    *,
    parcel_id: int,
    record: Mapping[str, Any],
    observation_id: int,
    object_id: str,
) -> int:
    assessment = record.get("assessment")
    identity = record.get("assessment_identity")
    if not isinstance(assessment, Mapping) or not isinstance(identity, Mapping):
        raise PropertyIngestError("NYC PIP assessment identity is incomplete")
    tax_year = _text(assessment.get("tax_year"))
    period = _text(assessment.get("period"))
    representation = _text(assessment.get("representation"))
    expected_key = f"US-NYC-DOF:ASSESSMENT:{record['bbl']}:{tax_year}:{period}"
    if (
        not tax_year
        or not period
        or representation != "current_assessment"
        or _text(record.get("same_assessment_key")) != expected_key
        or _text(identity.get("same_assessment_key")) != expected_key
    ):
        raise PropertyIngestError("NYC PIP current-assessment tuple changed")

    existing = db.execute(
        """
        SELECT raw_json FROM assessment
        WHERE parcel_id=? AND source_id=? AND tax_year=?
        """,
        (parcel_id, NYC_PIP_SOURCE_ID, tax_year),
    ).fetchone()
    if existing is not None:
        try:
            existing_raw = json.loads(existing["raw_json"])
        except (TypeError, json.JSONDecodeError):
            existing_raw = {}
        choice = existing_raw.get("projection_choice", {})
        existing_period = _text(choice.get("period")) or ""
        existing_object_id = _text(choice.get("object_id")) or ""
        if _nyc_pip_assessment_rank(
            period, object_id
        ) >= _nyc_pip_assessment_rank(existing_period, existing_object_id):
            return 0

    values = assessment.get("values")
    if not isinstance(values, Mapping):
        raise PropertyIngestError("NYC PIP assessment values must be an object")
    return _upsert_assessment_projection(
        db,
        parcel_id=parcel_id,
        source_id=NYC_PIP_SOURCE_ID,
        tax_year=tax_year,
        land_value=values.get("land_value"),
        improvement_value=values.get("improvement_value"),
        market_value=values.get("market_value"),
        assessed_value=values.get("taxable_assessed_value"),
        exempt_value=values.get("exemption_assessed_value"),
        assessment_class=assessment.get("tax_class"),
        source_good_through=None,
        observation_id=observation_id,
        raw={
            "projection_policy": (
                "current-assessment rows only; for a tax year choose the highest "
                "numeric period, then the lowest OBJECTID"
            ),
            "projection_choice": {
                "representation": representation,
                "tax_year": tax_year,
                "period": period,
                "object_id": object_id,
                "same_assessment_key": expected_key,
            },
            "assessment": dict(assessment),
        },
    )


def _validate_nyc_pip_exemption(record: Mapping[str, Any]) -> None:
    exemption = record.get("exemption")
    identity = record.get("exemption_identity")
    raw = record.get("raw_attributes")
    if (
        not isinstance(exemption, Mapping)
        or not isinstance(identity, Mapping)
        or not isinstance(raw, Mapping)
        or "PARID_ORG" not in raw
    ):
        raise PropertyIngestError("NYC PIP exemption tuple is incomplete")
    expected_tuple = {
        "bbl": record["bbl"],
        "original_parid": exemption.get("original_parid"),
        "tax_year": exemption.get("tax_year"),
        "exemption_code": exemption.get("code"),
        "exemption_type": exemption.get("type"),
        "sort_order": exemption.get("sort_order"),
    }
    if identity.get("published_tuple") != expected_tuple:
        raise PropertyIngestError("NYC PIP exemption published tuple changed")


def _ingest_nyc_pip_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve every PIP occurrence and project only deterministic parcel facts."""

    _assert_record_source(record, source_id)
    if source_id != NYC_PIP_SOURCE_ID:
        raise PropertyIngestError("NYC PIP mapper received a different source")
    bbl, parts, component, object_id = _nyc_pip_identity(record)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid=parts["county_geoid"],
        fallback_name=f"{parts['county_name']} County",
        fallback_state_code="NY",
    )
    if geoid != parts["county_geoid"]:
        raise PropertyIngestError("NYC PIP projected jurisdiction conflicts with BBL")
    source_native_id = (
        f"parcel:{bbl}"
        if component == "bundle"
        else f"{component}:{bbl}:{object_id}"
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=_text(record.get("record_kind")) or component,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=(
            _text(record.get("layer_schema_fingerprint"))
            or _record_schema_fingerprint(record)
        ),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_id = _upsert_nyc_pip_parcel(db, bbl=bbl, parts=parts)
    aliases_inserted = _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="bbl",
        alias_value=bbl,
        source_id=source_id,
        effective_from="",
    )

    owners_upserted = 0
    addresses_inserted = 0
    geometry_upserted = 0
    assessments_upserted = 0
    if component == "detail":
        context = record.get("assessment_context")
        context = dict(context) if isinstance(context, Mapping) else {}
        tax_year = _text(context.get("tax_year")) or ""
        period = _text(context.get("period")) or ""
        effective_from = f"tax-year:{tax_year};period:{period}"
        owners = record.get("owners")
        if not isinstance(owners, list):
            raise PropertyIngestError("NYC PIP owners must be a list")
        for owner_value in owners:
            owner = _mapping(owner_value, "record.owners[]")
            raw_name = _text(owner.get("raw_name"))
            if raw_name:
                owners_upserted += _upsert_nyc_pip_owner(
                    db,
                    parcel_id=parcel_id,
                    raw_name=raw_name,
                    effective_from=effective_from,
                    observation_id=observation_id,
                    evidence_ref=_text(record.get("canonical_ref")) or source_native_id,
                )
        address = record.get("situs_address")
        if isinstance(address, Mapping):
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role="situs",
                    address=address,
                    effective_from=effective_from,
                )
            )
    elif component == "tax_lot" and object_id is not None:
        geometry_upserted = _upsert_nyc_pip_geometry(
            db,
            parcel_id=parcel_id,
            bbl=bbl,
            object_id=object_id,
            record=record,
        )
    elif component == "current_assessment" and object_id is not None:
        assessments_upserted = _upsert_nyc_pip_current_assessment(
            db,
            parcel_id=parcel_id,
            record=record,
            observation_id=observation_id,
            object_id=object_id,
        )
    elif component == "assessment_history":
        assessment = record.get("assessment")
        if (
            not isinstance(assessment, Mapping)
            or assessment.get("representation") != "assessment_history"
        ):
            raise PropertyIngestError("NYC PIP assessment-history tuple changed")
    elif component == "exemptions":
        _validate_nyc_pip_exemption(record)

    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id, geoid, "parcel", bbl
        ),
        "source_occurrence_id": source_native_id,
        "component": component,
        "bbl": bbl,
        "native_feature_id": object_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "owners_upserted": owners_upserted,
        "geometry_upserted": geometry_upserted,
        "assessments_upserted": assessments_upserted,
        "assessment_history_preserved_raw": component == "assessment_history",
        "exemption_tuple_preserved_raw": component == "exemptions",
        "recorded_instruments_upserted": 0,
        "sales_upserted": 0,
        "title_assertions_upserted": 0,
        "document_artifacts_upserted": 0,
    }


def _miami_folio(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    digits = "".join(character for character in text if character.isdigit())
    if digits and len(digits) <= 13:
        return digits.zfill(13)
    return text


def _existing_parcel_id(
    db,
    *,
    jurisdiction_geoid: str,
    native_parcel_id: str,
) -> int | None:
    row = db.execute(
        """
        SELECT parcel_id
        FROM parcel_snapshot
        WHERE jurisdiction_geoid=? AND native_parcel_id=?
        ORDER BY
            CASE WHEN source_id=? THEN 0 ELSE 1 END,
            roll_year DESC,
            parcel_id DESC
        LIMIT 1
        """,
        (
            jurisdiction_geoid,
            native_parcel_id,
            MIAMI_DADE_PROPERTY_SOURCE_ID,
        ),
    ).fetchone()
    return int(row["parcel_id"]) if row else None


def _ingest_miami_recorder_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    document_id = _text(
        record.get("native_document_id")
        or record.get("clerk_file_number")
        or record.get("cfn")
    )
    if not document_id:
        return {
            "projection_skipped": True,
            "reason": "supplemental_recorder_record",
            "record_kind": _text(record.get("record_kind")),
        }
    jurisdiction_geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="12086",
        fallback_name="Miami-Dade County",
        fallback_state_code="FL",
    )
    if jurisdiction_geoid != "12086":
        raise PropertyIngestError(
            f"Miami-Dade recorder record has out-of-scope GEOID {jurisdiction_geoid}"
        )
    query_source = envelope.get("query", {}).get("source", {})
    query_source_metadata = (
        query_source.get("metadata", {}) if isinstance(query_source, Mapping) else {}
    )
    instrument_source_id = _text(
        record.get("record_identity_source_id")
        or (
            query_source_metadata.get("record_identity_source_id")
            if isinstance(query_source_metadata, Mapping)
            else None
        )
        or source_id
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=document_id,
        record_kind="recorded_instrument",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    execution_date = _date_prefix(record.get("execution_date"))
    recording_date = _date_prefix(record.get("recording_date"))
    consideration = record.get("consideration")
    db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id,
            instrument_type, book, page, execution_date, recording_date,
            consideration_minor, currency, legal_description_raw, source_url,
            observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
        DO UPDATE SET
            instrument_type=excluded.instrument_type,
            book=excluded.book,
            page=excluded.page,
            execution_date=excluded.execution_date,
            recording_date=excluded.recording_date,
            consideration_minor=excluded.consideration_minor,
            legal_description_raw=excluded.legal_description_raw,
            source_url=excluded.source_url,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            instrument_source_id,
            jurisdiction_geoid,
            document_id,
            _text(record.get("instrument_type")),
            _text(record.get("book")),
            _text(record.get("page")),
            execution_date,
            recording_date,
            _minor_units(consideration),
            _text(record.get("legal_description_raw")),
            _record_source_url(envelope, record),
            observation_id,
            canonical_json(record),
        ),
    )
    instrument_row = db.execute(
        """
        SELECT instrument_id FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (instrument_source_id, jurisdiction_geoid, document_id),
    ).fetchone()
    instrument_id = int(instrument_row["instrument_id"])

    parties = record.get("parties", [])
    if not isinstance(parties, list):
        raise PropertyIngestError("record.parties must be a list")
    parties_upserted = 0
    for index, party_value in enumerate(parties, start=1):
        party = _mapping(party_value, f"record.parties[{index - 1}]")
        raw_name = _text(party.get("name") or party.get("raw_name"))
        if not raw_name:
            continue
        sequence = party.get("sequence")
        try:
            sequence_no = int(sequence) if sequence not in (None, "") else index
        except (TypeError, ValueError):
            sequence_no = index
        role = _text(party.get("role")) or _text(party.get("raw_role_code")) or "other"
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET
                normalized_name=excluded.normalized_name,
                entity_kind=excluded.entity_kind,
                raw_address=excluded.raw_address
            """,
            (
                instrument_id,
                sequence_no,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
                _text(party.get("entity_kind")),
                _text(party.get("raw_address")),
            ),
        )
        parties_upserted += 1

    parcels = record.get("parcels", [])
    if not isinstance(parcels, list):
        raise PropertyIngestError("record.parcels must be a list")
    parcel_ids: set[int] = set()
    parcels_upserted = 0
    addresses_inserted = 0
    effective_from = recording_date or execution_date or ""
    for index, parcel_value in enumerate(parcels):
        parcel = _mapping(parcel_value, f"record.parcels[{index}]")
        native_parcel_id = _miami_folio(
            parcel.get("native_parcel_id") or parcel.get("folio")
        )
        if not native_parcel_id:
            continue
        parcel_id = _existing_parcel_id(
            db,
            jurisdiction_geoid=jurisdiction_geoid,
            native_parcel_id=native_parcel_id,
        )
        if parcel_id is None:
            parcel_id = _upsert_parcel_snapshot(
                db,
                source_id=instrument_source_id,
                jurisdiction_geoid=jurisdiction_geoid,
                native_parcel_id=native_parcel_id,
                roll_year="",
                effective_from=effective_from or None,
                source_good_through=None,
                observation_id=observation_id,
                record=parcel,
            )
        parcel_ids.add(parcel_id)
        legal_description = _text(
            parcel.get("legal_description_raw") or record.get("legal_description_raw")
        )
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=excluded.legal_description_raw
            """,
            (
                instrument_id,
                parcel_id,
                _text(parcel.get("link_method")) or "source_index_folio",
                float(parcel.get("link_confidence") or 1.0),
                legal_description,
            ),
        )
        address = parcel.get("address")
        if isinstance(address, Mapping):
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=instrument_source_id,
                    role="situs",
                    address=address,
                    effective_from=effective_from,
                )
            )
        parcels_upserted += 1

    sales_upserted = 0
    if record.get("is_conveyance") is True:
        for parcel_id in parcel_ids:
            sales_upserted += _upsert_sale_projection(
                db,
                parcel_id=parcel_id,
                source_id=instrument_source_id,
                native_sale_id=document_id,
                sale_date=execution_date or recording_date,
                consideration=consideration,
                derivation="recorded_instrument",
                instrument_id=instrument_id,
                observation_id=observation_id,
                raw=record,
                execution_date=execution_date,
                recording_date=recording_date,
            )

    return {
        "instrument_id": instrument_id,
        "canonical_ref": canonical_property_ref(
            instrument_source_id,
            jurisdiction_geoid,
            "instrument",
            document_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "parties_upserted": parties_upserted,
        "parcels_upserted": parcels_upserted,
        "addresses_inserted": addresses_inserted,
        "sales_upserted": sales_upserted,
    }


def _kofile_recorder_representation_rank(record: Mapping[str, Any]) -> int:
    """Rank an index occurrence below a document-detail representation."""

    representation = _text(record.get("source_representation"))
    if representation == "search_index":
        return 1
    if representation == "document_detail":
        return 2
    return 1 if isinstance(record.get("search_metadata"), Mapping) else 2


def _ingest_county_recorder_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    department_code = _text(record.get("department_code"))
    if department_code == "MAR":
        return {
            "projection_skipped": True,
            "reason": "non_property_recorder_department",
            "department_code": department_code,
            "record_kind": _text(record.get("record_kind")),
        }
    document_id = _text(
        record.get("native_document_id")
        or record.get("source_internal_id")
        or record.get("doc_id")
        or record.get("instrument_number")
    )
    if not document_id:
        raise PropertyIngestError(f"{source_id} recorder record lacks a document ID")
    try:
        expected_geoid, jurisdiction_name, state_code = COUNTY_RECORDER_SCOPES[
            source_id
        ]
    except KeyError as error:
        raise PropertyIngestError(
            f"unsupported county recorder source: {source_id}"
        ) from error
    jurisdiction_geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid=expected_geoid,
        fallback_name=jurisdiction_name,
        fallback_state_code=state_code,
    )
    if jurisdiction_geoid != expected_geoid:
        raise PropertyIngestError(
            f"{source_id} recorder record has out-of-scope GEOID {jurisdiction_geoid}"
        )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=document_id,
        record_kind="recorded_instrument",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    existing_instrument = db.execute(
        """
        SELECT ri.instrument_id, ri.instrument_type, ri.observation_id,
               ri.raw_json,
               so.retrieved_at AS observation_retrieved_at
        FROM recorded_instrument ri
        LEFT JOIN source_observation so
          ON so.observation_id=ri.observation_id
        WHERE ri.source_id=? AND ri.jurisdiction_geoid=?
          AND ri.native_document_id=?
        """,
        (source_id, jurisdiction_geoid, document_id),
    ).fetchone()
    current_retrieved_at = (
        _text(existing_instrument["observation_retrieved_at"])
        if existing_instrument is not None
        else None
    )
    preserve_reason = None
    existing_representation_rank = None
    incoming_representation_rank = None
    if (
        existing_instrument is not None
        and (
            source_id in GOVOS_RECORDER_SOURCE_IDS
            or source_id == REEVES_RECORDER_SOURCE_ID
        )
    ):
        try:
            existing_raw = json.loads(existing_instrument["raw_json"])
        except (TypeError, json.JSONDecodeError):
            existing_raw = {}
        if not isinstance(existing_raw, Mapping):
            existing_raw = {}
        existing_representation_rank = _kofile_recorder_representation_rank(
            existing_raw
        )
        incoming_representation_rank = _kofile_recorder_representation_rank(record)
        if incoming_representation_rank < existing_representation_rank:
            preserve_reason = (
                "less_complete_recorder_observation_preserved_without_mutation"
            )
    if (
        preserve_reason is None
        and current_retrieved_at
        and current_retrieved_at > retrieved_at
        and (
            incoming_representation_rank is None
            or existing_representation_rank is None
            or incoming_representation_rank <= existing_representation_rank
        )
    ):
        preserve_reason = "older_recorder_observation_preserved_without_mutation"
    if preserve_reason is not None:
        return {
            "projection_skipped": True,
            "reason": preserve_reason,
            "instrument_id": int(existing_instrument["instrument_id"]),
            "canonical_ref": canonical_property_ref(
                source_id,
                jurisdiction_geoid,
                "instrument",
                document_id,
            ),
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "current_observation_id": existing_instrument["observation_id"],
            "current_retrieved_at": current_retrieved_at,
            "incoming_retrieved_at": retrieved_at,
            "current_representation_rank": existing_representation_rank,
            "incoming_representation_rank": incoming_representation_rank,
            "parties_upserted": 0,
            "documents_upserted": 0,
            "parcels_upserted": 0,
            "addresses_inserted": 0,
            "sales_upserted": 0,
        }

    legal_values = record.get("legal_descriptions", [])
    if not isinstance(legal_values, list):
        raise PropertyIngestError("record.legal_descriptions must be a list")
    legal_descriptions = [
        _mapping(value, f"record.legal_descriptions[{index}]")
        for index, value in enumerate(legal_values)
    ]
    if not legal_descriptions:
        map_values = record.get("map_legal_fields", [])
        if not isinstance(map_values, list):
            raise PropertyIngestError("record.map_legal_fields must be a list")
        mapped_legal = {
            field: value
            for index, raw_value in enumerate(map_values)
            for item in [_mapping(raw_value, f"record.map_legal_fields[{index}]")]
            if (field := _text(item.get("field")))
            and (value := _text(item.get("value")))
        }
        if mapped_legal:
            legal_descriptions = [mapped_legal]
    book_parts: list[str] = []
    for raw_value in (record.get("book"), record.get("volume")):
        value = _text(raw_value)
        if value and value not in book_parts:
            book_parts.append(value)
    book = "/".join(book_parts) or None
    legal_description_raw = _text(record.get("legal_description_raw"))
    if legal_description_raw is None and legal_descriptions:
        legal_description_raw = canonical_json(legal_descriptions)
    instrument_type_label = _text(record.get("instrument_type_label"))
    instrument_type = (
        instrument_type_label
        or (
            _text(existing_instrument["instrument_type"])
            if existing_instrument is not None
            else None
        )
        or _text(record.get("instrument_type"))
        or _text(record.get("document_type"))
    )
    db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id,
            instrument_type, book, page, execution_date, recording_date,
            consideration_minor, currency, legal_description_raw, source_url,
            observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
        DO UPDATE SET
            instrument_type=COALESCE(
                excluded.instrument_type, recorded_instrument.instrument_type
            ),
            book=COALESCE(excluded.book, recorded_instrument.book),
            page=COALESCE(excluded.page, recorded_instrument.page),
            execution_date=COALESCE(
                excluded.execution_date, recorded_instrument.execution_date
            ),
            recording_date=COALESCE(
                excluded.recording_date, recorded_instrument.recording_date
            ),
            legal_description_raw=COALESCE(
                excluded.legal_description_raw,
                recorded_instrument.legal_description_raw
            ),
            source_url=COALESCE(excluded.source_url, recorded_instrument.source_url),
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            source_id,
            jurisdiction_geoid,
            document_id,
            instrument_type,
            book,
            _text(record.get("page")),
            _date_prefix(record.get("execution_date")),
            _date_prefix(
                record.get("recording_date") or record.get("recording_date_local_iso")
            ),
            _minor_units(record.get("consideration_amount")),
            legal_description_raw,
            _record_source_url(envelope, record),
            observation_id,
            canonical_json(record),
        ),
    )
    instrument_row = db.execute(
        """
        SELECT instrument_id FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (source_id, jurisdiction_geoid, document_id),
    ).fetchone()
    instrument_id = int(instrument_row["instrument_id"])

    parties = record.get("parties", [])
    if not isinstance(parties, list):
        raise PropertyIngestError("record.parties must be a list")
    parties_upserted = 0
    for index, party_value in enumerate(parties, start=1):
        party = _mapping(party_value, f"record.parties[{index - 1}]")
        raw_name = _text(party.get("name") or party.get("raw_name"))
        if not raw_name:
            continue
        raw_sequence = party.get("sequence_no", party.get("sequence"))
        try:
            sequence_no = int(raw_sequence) if raw_sequence not in (None, "") else index
        except (TypeError, ValueError):
            sequence_no = index
        role = (
            _text(party.get("role"))
            or _text(party.get("native_role"))
            or _text(party.get("party_type"))
            or "other"
        )
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET
                normalized_name=excluded.normalized_name,
                entity_kind=COALESCE(
                    excluded.entity_kind, instrument_party.entity_kind
                ),
                raw_address=COALESCE(
                    excluded.raw_address, instrument_party.raw_address
                )
            """,
            (
                instrument_id,
                sequence_no,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
                _text(party.get("entity_kind")),
                _text(party.get("raw_address")),
            ),
        )
        parties_upserted += 1

    documents_value = record.get("documents", [])
    if not isinstance(documents_value, list):
        raise PropertyIngestError("record.documents must be a list")
    documents = list(documents_value)
    if source_id in OREGON_HELION_RECORDER_SOURCE_IDS:
        for resource_kind, field_name, mime_type in (
            ("image", "document_image", "application/pdf"),
            ("text", "text_alternative", "text/plain"),
        ):
            resource_value = record.get(field_name)
            if not isinstance(resource_value, Mapping):
                continue
            source_url = _text(resource_value.get("url"))
            if not source_url:
                continue
            documents.append(
                {
                    "native_document_id": (f"{document_id}:{resource_kind}"),
                    "mime_type": mime_type,
                    "page_count": (
                        record.get("page_count") if resource_kind == "image" else None
                    ),
                    "source_url": source_url,
                    "access_state": "public",
                    "certification_status": "source_resource",
                }
            )
    documents_upserted = 0
    for index, document_value in enumerate(documents):
        document = _mapping(
            document_value,
            f"record.documents[{index}]",
        )
        native_document_id = _text(document.get("native_document_id"))
        if not native_document_id:
            continue
        digest = _text(document.get("sha256"))
        access_state = _text(document.get("access_state")) or "unknown"
        if access_state not in {
            "public",
            "restricted",
            "sealed",
            "expunged",
            "removed",
            "redacted",
            "unknown",
        }:
            access_state = "unknown"
        raw_page_count = document.get("page_count")
        try:
            page_count = (
                int(raw_page_count) if raw_page_count not in (None, "") else None
            )
        except (TypeError, ValueError):
            page_count = None
        existing = db.execute(
            """
            SELECT artifact_id FROM document_artifact
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_document_id=?
              AND COALESCE(sha256, '')=COALESCE(?, '')
            """,
            (
                source_id,
                jurisdiction_geoid,
                native_document_id,
                digest,
            ),
        ).fetchone()
        values = (
            instrument_id,
            digest,
            _text(document.get("mime_type")),
            page_count,
            _text(document.get("storage_path")),
            _text(document.get("source_url")),
            (
                "downloaded_page"
                if digest or document.get("storage_path")
                else "portal_metadata"
            ),
            _text(document.get("certification_status")) or "source_record",
            access_state,
            retrieved_at if digest or document.get("storage_path") else None,
        )
        if existing is None:
            db.execute(
                """
                INSERT INTO document_artifact(
                    source_id, jurisdiction_geoid, native_document_id,
                    instrument_id, sha256, mime_type, page_count, storage_path,
                    source_url, acquisition_method, rights_tier, access_state,
                    acquired_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    jurisdiction_geoid,
                    native_document_id,
                    *values,
                ),
            )
        else:
            db.execute(
                """
                UPDATE document_artifact
                SET instrument_id=?,
                    sha256=COALESCE(?, sha256),
                    mime_type=COALESCE(?, mime_type),
                    page_count=COALESCE(?, page_count),
                    storage_path=COALESCE(?, storage_path),
                    source_url=COALESCE(?, source_url),
                    acquisition_method=COALESCE(?, acquisition_method),
                    rights_tier=COALESCE(?, rights_tier),
                    access_state=COALESCE(?, access_state),
                    acquired_at=COALESCE(?, acquired_at)
                WHERE artifact_id=?
                """,
                (*values, int(existing["artifact_id"])),
            )
        documents_upserted += 1

    propertyweb_links_resolved = 0
    if source_id == LINCOLN_HELION_RECORDER_SOURCE_ID:
        propertyweb_links_resolved = _link_lincoln_recorder_instrument_to_propertyweb(
            db,
            instrument_id=instrument_id,
            instrument_number=document_id,
            legal_description_raw=legal_description_raw,
        )

    return {
        "instrument_id": instrument_id,
        "canonical_ref": canonical_property_ref(
            source_id,
            jurisdiction_geoid,
            "instrument",
            document_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "parties_upserted": parties_upserted,
        "documents_upserted": documents_upserted,
        "parcels_upserted": 0,
        "addresses_inserted": 0,
        "sales_upserted": 0,
        "propertyweb_links_resolved": propertyweb_links_resolved,
    }


def _ingest_santa_fe_clerktrack_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project ClerkTrack index/detail metadata without deriving current title."""

    _assert_record_source(record, source_id)
    if source_id != SANTA_FE_CLERKTRACK_SOURCE_ID:
        raise PropertyIngestError("Santa Fe ClerkTrack source ID changed")
    record_kind = _text(record.get("record_kind"))
    if record_kind not in {
        "recorded_instrument_index",
        "recorded_instrument_detail",
    }:
        raise PropertyIngestError(
            "Santa Fe ClerkTrack projection requires an index or detail record"
        )
    instrument_number = _text(
        record.get("native_instrument_id")
        or record.get("instrument_number")
    )
    if not instrument_number:
        raise PropertyIngestError(
            "Santa Fe ClerkTrack record lacks its instrument number"
        )
    if (
        _text(record.get("native_instrument_id")) != instrument_number
        or _text(record.get("instrument_number")) != instrument_number
    ):
        raise PropertyIngestError(
            "Santa Fe ClerkTrack native and displayed instrument identities differ"
        )
    expected_ref = canonical_property_ref(
        source_id,
        query_santa_fe_clerktrack.COUNTY_GEOID,
        "recorded_instrument",
        instrument_number,
    )
    if _text(record.get("canonical_ref")) != expected_ref:
        raise PropertyIngestError(
            "Santa Fe ClerkTrack canonical_ref does not preserve instrument identity"
        )

    jurisdiction_geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid=query_santa_fe_clerktrack.COUNTY_GEOID,
        fallback_name="Santa Fe County, New Mexico",
        fallback_state_code="NM",
    )
    if jurisdiction_geoid != query_santa_fe_clerktrack.COUNTY_GEOID:
        raise PropertyIngestError(
            "Santa Fe ClerkTrack record is outside county GEOID 35049"
        )

    query_fingerprint, retrieved_at, status, warnings = (
        _observation_context(envelope)
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=f"instrument:{instrument_number}",
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    if record_kind == "recorded_instrument_index":
        legal_payload = {
            "legal_description_raw": record.get(
                "legal_description_raw"
            ),
            "legal_information_raw": record.get(
                "legal_information_raw"
            ),
            "cross_source_join_keys": record.get(
                "cross_source_join_keys"
            ),
        }
    else:
        legal_payload = {
            "legal_information": record.get("legal_information") or [],
            "additional_descriptions": (
                record.get("additional_descriptions") or []
            ),
            "index_listing_displays": record.get(
                "index_listing_displays"
            ),
            "cross_source_join_keys": record.get(
                "cross_source_join_keys"
            ),
        }
    legal_description_raw = (
        canonical_json(legal_payload)
        if any(
            value not in (None, "", [], {})
            for value in legal_payload.values()
        )
        else None
    )

    existing = db.execute(
        """
        SELECT instrument_id, raw_json
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (source_id, jurisdiction_geoid, instrument_number),
    ).fetchone()
    existing_kind = None
    if existing is not None:
        try:
            existing_raw = json.loads(existing["raw_json"])
        except (TypeError, json.JSONDecodeError):
            existing_raw = None
        if isinstance(existing_raw, Mapping):
            existing_kind = _text(existing_raw.get("record_kind"))
    preserve_existing_detail = (
        record_kind == "recorded_instrument_index"
        and existing_kind == "recorded_instrument_detail"
    )
    if existing is None:
        db.execute(
            """
            INSERT INTO recorded_instrument(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_type, book, page, execution_date, recording_date,
                consideration_minor, currency, legal_description_raw,
                source_url, observation_id, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, 'USD', ?, ?, ?, ?)
            """,
            (
                source_id,
                jurisdiction_geoid,
                instrument_number,
                _text(record.get("document_type")),
                _text(record.get("book")),
                _text(record.get("page")),
                _date_prefix(record.get("recording_date")),
                legal_description_raw,
                _record_source_url(envelope, record),
                observation_id,
                canonical_json(record),
            ),
        )
        instrument_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    else:
        instrument_id = int(existing["instrument_id"])
        if not preserve_existing_detail:
            db.execute(
                """
                UPDATE recorded_instrument
                SET instrument_type=?, book=?, page=?, recording_date=?,
                    legal_description_raw=?, source_url=?, observation_id=?,
                    raw_json=?
                WHERE instrument_id=?
                """,
                (
                    _text(record.get("document_type")),
                    _text(record.get("book")),
                    _text(record.get("page")),
                    _date_prefix(record.get("recording_date")),
                    legal_description_raw,
                    _record_source_url(envelope, record),
                    observation_id,
                    canonical_json(record),
                    instrument_id,
                ),
            )

    party_rows: list[tuple[str, str]] = []
    if record_kind == "recorded_instrument_index":
        displays = _mapping(
            record.get("indexed_party_displays"),
            "record.indexed_party_displays",
        )
        for role, field in (
            ("grantor_display_snapshot", "grantors_raw"),
            ("grantee_display_snapshot", "grantees_raw"),
        ):
            raw_name = _text(displays.get(field))
            if raw_name:
                party_rows.append((role, raw_name))
    else:
        parties_value = record.get("parties") or []
        if not isinstance(parties_value, list):
            raise PropertyIngestError(
                "Santa Fe ClerkTrack detail parties must be a list"
            )
        for index, party_value in enumerate(parties_value):
            party = _mapping(
                party_value,
                f"record.parties[{index}]",
            )
            raw_name = _text(
                party.get("raw_name") or party.get("name")
            )
            role = _text(party.get("role"))
            if role not in {"grantor", "grantee"}:
                raise PropertyIngestError(
                    "Santa Fe ClerkTrack detail party role must preserve "
                    "the published grantor or grantee classification"
                )
            if raw_name and role:
                party_rows.append((role, raw_name))

    for sequence_no, (role, raw_name) in enumerate(
        party_rows,
        start=1,
    ):
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name,
                normalized_name, entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET normalized_name=excluded.normalized_name
            """,
            (
                instrument_id,
                sequence_no,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
            ),
        )

    return {
        "instrument_id": instrument_id,
        "canonical_ref": expected_ref,
        "native_instrument_id": instrument_number,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "recorded_instruments_upserted": int(
            not preserve_existing_detail
        ),
        "index_party_snapshots_upserted": (
            len(party_rows)
            if record_kind == "recorded_instrument_index"
            else 0
        ),
        "detail_parties_upserted": (
            len(party_rows)
            if record_kind == "recorded_instrument_detail"
            else 0
        ),
        "documents_upserted": 0,
        "parcels_upserted": 0,
        "ownership_assertions_upserted": 0,
        "title_assertions_upserted": 0,
        "cross_source_join_keys_preserved": bool(
            record.get("cross_source_join_keys")
        ),
    }


SANTA_FE_ASSESSMENT_PERIODS = {
    "current": "source-period:current",
    "prior": "source-period:prior",
}


def _santa_fe_is_active_open(record: Mapping[str, Any]) -> bool:
    return (
        (_text(record.get("account_status")) or "").upper() == "A"
        and _text(record.get("effective_to")) is None
    )


def _santa_fe_feature_sort_key(
    record: Mapping[str, Any],
) -> tuple[int, int | str]:
    feature_id = _text(record.get("native_feature_id")) or ""
    if feature_id.isdigit():
        return (0, int(feature_id))
    return (1, feature_id)


def _santa_fe_preferred_active_feature(
    records: Sequence[Mapping[str, Any]],
    *,
    native_parcel_id: str,
) -> str | None:
    """Select the newest active account version with a stable tie-breaker."""

    candidates = [
        record
        for record in records
        if _text(record.get("native_parcel_id")) == native_parcel_id
        and _santa_fe_is_active_open(record)
        and _text(record.get("native_feature_id"))
    ]
    if not candidates:
        return None
    latest_effective_from = max(
        _text(record.get("effective_from")) or ""
        for record in candidates
    )
    latest = [
        record
        for record in candidates
        if (_text(record.get("effective_from")) or "")
        == latest_effective_from
    ]
    preferred = min(latest, key=_santa_fe_feature_sort_key)
    return _text(preferred.get("native_feature_id"))


def _ingest_santa_fe_property_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve every Assessor feature and project only durable parcel rows."""

    _assert_record_source(record, source_id)
    if source_id != SANTA_FE_PROPERTY_SOURCE_ID:
        raise PropertyIngestError("Santa Fe property source ID changed")
    identity = _mapping(record.get("identity"), "record.identity")
    native_parcel_id = _text(record.get("native_parcel_id"))
    native_feature_id = _text(record.get("native_feature_id"))
    if not native_feature_id:
        raise PropertyIngestError(
            "Santa Fe Assessor feature lacks its ArcGIS OBJECTID"
        )
    durable_identity = native_parcel_id is not None
    if (
        identity.get("durable_parcel_identity") is not durable_identity
        or identity.get("projection_eligible_as_parcel")
        is not durable_identity
    ):
        raise PropertyIngestError(
            "Santa Fe record identity tier disagrees with its parcel key"
        )

    canonical_kind = "parcel" if durable_identity else "feature_occurrence"
    canonical_native_id = native_parcel_id or native_feature_id
    expected_ref = canonical_property_ref(
        source_id,
        query_santa_fe_property.COUNTY_GEOID,
        canonical_kind,
        canonical_native_id,
    )
    canonical_ref = _text(record.get("canonical_ref"))
    if canonical_ref != expected_ref:
        raise PropertyIngestError(
            "Santa Fe canonical_ref disagrees with its published identity"
        )
    expected_record_kind = (
        "parcel_account_observation"
        if durable_identity
        else "parcel_geometry_feature_occurrence"
    )
    record_kind = _text(record.get("record_kind"))
    if record_kind != expected_record_kind:
        raise PropertyIngestError(
            "Santa Fe record kind disagrees with its identity tier"
        )

    query_fingerprint, retrieved_at, status, warnings = (
        _observation_context(envelope)
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=f"feature:{native_feature_id}",
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    if not durable_identity:
        return {
            "projection_skipped": True,
            "reason": (
                "santa_fe_objectid_only_feature_has_no_durable_parcel_identity"
            ),
            "canonical_ref": canonical_ref,
            "native_feature_id": native_feature_id,
            "observation_id": observation_id,
            "record_sha256": record_hash,
        }

    if not _santa_fe_is_active_open(record):
        return {
            "projection_skipped": True,
            "reason": (
                "santa_fe_inactive_or_closed_feature_preserved_without_"
                "current_projection"
            ),
            "canonical_ref": canonical_ref,
            "native_parcel_id": native_parcel_id,
            "native_feature_id": native_feature_id,
            "observation_id": observation_id,
            "record_sha256": record_hash,
        }

    envelope_records_value = envelope.get("records")
    envelope_records = [
        value
        for value in (
            envelope_records_value
            if isinstance(envelope_records_value, list)
            else []
        )
        if isinstance(value, Mapping)
    ]
    preferred_feature_id = _santa_fe_preferred_active_feature(
        envelope_records,
        native_parcel_id=native_parcel_id,
    )
    if preferred_feature_id != native_feature_id:
        return {
            "projection_skipped": True,
            "reason": (
                "santa_fe_active_feature_is_not_preferred_account_version"
            ),
            "canonical_ref": canonical_ref,
            "native_parcel_id": native_parcel_id,
            "native_feature_id": native_feature_id,
            "preferred_native_feature_id": preferred_feature_id,
            "observation_id": observation_id,
            "record_sha256": record_hash,
        }

    geoid = _upsert_jurisdiction(db, record)
    if geoid != query_santa_fe_property.COUNTY_GEOID:
        raise PropertyIngestError(
            f"Santa Fe Assessor record has out-of-scope GEOID {geoid}"
        )
    effective_from = _text(record.get("effective_from"))
    effective_to = _text(record.get("effective_to"))
    existing = db.execute(
        """
        SELECT raw_json
        FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=''
        """,
        (source_id, geoid, native_parcel_id),
    ).fetchone()
    if existing is not None:
        try:
            existing_record = json.loads(existing["raw_json"])
        except (TypeError, json.JSONDecodeError):
            existing_record = None
        if isinstance(existing_record, Mapping):
            preferred_across_observations = (
                _santa_fe_preferred_active_feature(
                    [existing_record, record],
                    native_parcel_id=native_parcel_id,
                )
            )
            if preferred_across_observations != native_feature_id:
                return {
                    "projection_skipped": True,
                    "reason": (
                        "santa_fe_active_feature_is_older_than_projected_"
                        "account_version"
                    ),
                    "canonical_ref": canonical_ref,
                    "native_parcel_id": native_parcel_id,
                    "native_feature_id": native_feature_id,
                    "preferred_native_feature_id": (
                        preferred_across_observations
                    ),
                    "observation_id": observation_id,
                    "record_sha256": record_hash,
                }
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid=geoid,
        native_parcel_id=native_parcel_id,
        roll_year="",
        effective_from=effective_from,
        source_good_through=effective_to,
        observation_id=observation_id,
        record=record,
    )

    aliases_value = record.get("alternate_parcel_ids") or []
    if not isinstance(aliases_value, list):
        raise PropertyIngestError(
            "Santa Fe alternate_parcel_ids must be a list"
        )
    aliases_inserted = 0
    for alias in aliases_value:
        if _text(alias) == native_parcel_id:
            continue
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="assessor_alternate_parcel_id",
            alias_value=alias,
            source_id=source_id,
            effective_from=effective_from or retrieved_at,
        )

    addresses_inserted = 0
    current_addresses: dict[
        str,
        set[
            tuple[
                str | None,
                str | None,
                str | None,
                str | None,
                str | None,
            ]
        ],
    ] = {"situs": set(), "mailing": set()}
    for role, field in (
        ("situs", "situs_address"),
        ("mailing", "mailing_address"),
    ):
        address = record.get(field)
        if not isinstance(address, Mapping) or not _address_raw(address):
            continue
        current_addresses[role].add(
            _address_identity(
                raw_address=_address_raw(address),
                city=address.get("city"),
                state=address.get("state"),
                postal_code=address.get("postal_code"),
                country=address.get("country"),
            )
        )
        addresses_inserted += int(
            _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                role=role,
                address=address,
                effective_from=effective_from or retrieved_at,
            )
        )
    addresses_closed = _reconcile_assessor_addresses(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        current_addresses=current_addresses,
        effective_to=effective_from or retrieved_at,
    )

    owners = record.get("owners") or []
    if not isinstance(owners, list):
        raise PropertyIngestError("Santa Fe record.owners must be a list")
    owners_upserted = 0
    current_owner_names: set[str] = set()
    for owner_value in owners:
        owner = _mapping(owner_value, "record.owners[]")
        raw_name = _text(owner.get("raw_name"))
        if not raw_name:
            continue
        if owner.get("assertion_type") not in {
            None,
            "assessment_account_observation",
        }:
            raise PropertyIngestError(
                "Santa Fe owner row is not an assessment observation"
            )
        current_owner_names.add(" ".join(raw_name.upper().split()))
        owners_upserted += _upsert_assessor_owner(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            raw_name=raw_name,
            effective_from=effective_from or retrieved_at,
            confidence="high",
            observation_id=observation_id,
            evidence_ref=canonical_ref,
        )
    owners_closed = _reconcile_assessor_owners(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        current_owner_names=current_owner_names,
        effective_to=effective_from or retrieved_at,
    )

    assessment = record.get("assessment")
    if not isinstance(assessment, Mapping):
        assessment = {}
    classification = record.get("classification")
    classification = (
        dict(classification)
        if isinstance(classification, Mapping)
        else {}
    )
    assessments_upserted = 0
    assessment_periods: list[str] = []
    for period, period_key in SANTA_FE_ASSESSMENT_PERIODS.items():
        period_record = assessment.get(period)
        if not isinstance(period_record, Mapping):
            continue
        source_fields = period_record.get("source_fields")
        source_fields = (
            dict(source_fields)
            if isinstance(source_fields, Mapping)
            else {}
        )
        if not any(value is not None for value in source_fields.values()):
            continue
        assessments_upserted += _upsert_assessment_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=period_key,
            land_value=source_fields.get("assessed_land"),
            improvement_value=source_fields.get(
                "assessed_improvement"
            ),
            assessed_value=None,
            exempt_value=source_fields.get("exemption"),
            assessment_class=classification.get("property_class"),
            source_good_through=effective_to,
            observation_id=observation_id,
            raw={
                "source_period": period,
                "year_published": False,
                **dict(period_record),
            },
        )
        assessment_periods.append(period_key)

    geometry_upserted = 0
    geometry = record.get("geometry")
    if isinstance(geometry, Mapping):
        snapshot_date = _date_prefix(retrieved_at) or ""
        db.execute(
            """
            INSERT INTO parcel_geometry(
                parcel_id, geometry_ref, geometry_format, crs,
                accuracy_disclaimer, source_id, snapshot_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
                geometry_ref=excluded.geometry_ref,
                geometry_format=excluded.geometry_format,
                crs=excluded.crs,
                accuracy_disclaimer=excluded.accuracy_disclaimer
            """,
            (
                parcel_id,
                f"source-observation:{observation_id}#/geometry",
                _text(record.get("geometry_format")) or "esri_json",
                _text(record.get("geometry_crs")) or "EPSG:4326",
                (
                    "Santa Fe County Assessor cadastral mapping; "
                    "not a surveyed legal boundary"
                ),
                source_id,
                snapshot_date,
            ),
        )
        geometry_upserted = 1

    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_ref,
        "native_parcel_id": native_parcel_id,
        "native_feature_id": native_feature_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "addresses_closed": addresses_closed,
        "owners_upserted": owners_upserted,
        "owners_closed": owners_closed,
        "owner_assertion_basis": "assessment_roll_observation",
        "assessment_periods": assessment_periods,
        "assessment_years_invented": False,
        "assessments_upserted": assessments_upserted,
        "geometry_upserted": geometry_upserted,
        "legal_preserved_in_snapshot": isinstance(
            record.get("legal"),
            Mapping,
        ),
        "classification_preserved_in_snapshot": bool(classification),
        "recorder_hints_preserved_as_join_hints": isinstance(
            record.get("recorder_index_hints"),
            Mapping,
        ),
        "recorded_instruments_upserted": 0,
        "sales_upserted": 0,
        "title_assertions_upserted": 0,
    }


USVI_CAMA_ARTIFACT_KINDS = frozenset(
    {
        "property_record_card_print_view",
        "property_tax_bill_print_view",
        "property_tax_payment_receipt",
    }
)


def _usvi_cama_jurisdiction(db) -> str:
    return _upsert_jurisdiction_values(
        db,
        geoid="78",
        name="U.S. Virgin Islands",
        state_code="VI",
        jurisdiction_type="territory",
    )


def _usvi_cama_amount(value: Any) -> Decimal | None:
    text = _text(value)
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    normalized = re.sub(r"[^0-9.\-]", "", text)
    if not normalized or normalized in {"-", ".", "-."}:
        return None
    try:
        amount = Decimal(normalized)
    except InvalidOperation as error:
        raise PropertyIngestError(
            f"invalid USVI Capture CAMA amount: {value!r}"
        ) from error
    return -amount if negative else amount


def _usvi_cama_parcel_for_year(
    db,
    *,
    parcel_number: str,
    tax_year: str,
    observation_id: int,
    record: Mapping[str, Any],
) -> int:
    row = db.execute(
        """
        SELECT parcel_id
        FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid='78'
          AND native_parcel_id=? AND roll_year=?
        """,
        (USVI_PROPERTY_TAX_SOURCE_ID, parcel_number, tax_year),
    ).fetchone()
    if row is not None:
        return int(row["parcel_id"])
    return _upsert_parcel_snapshot(
        db,
        source_id=USVI_PROPERTY_TAX_SOURCE_ID,
        jurisdiction_geoid="78",
        native_parcel_id=parcel_number,
        roll_year=tax_year,
        effective_from=None,
        source_good_through=None,
        observation_id=observation_id,
        record=record,
    )


def _ingest_usvi_cama_artifact(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    query_fingerprint, retrieved_at, status, warnings = _observation_context(
        envelope
    )
    native_document_id = _text(
        record.get("native_document_id") or record.get("canonical_ref")
    )
    digest = _text(record.get("sha256")) or raw_artifact_sha256
    storage_path = raw_artifact_path or _text(record.get("destination"))
    if not native_document_id or not digest or not storage_path:
        raise PropertyIngestError(
            "USVI Capture CAMA artifact requires stable identity, SHA-256, "
            "and a retrieved storage path"
        )
    if raw_artifact_sha256 and digest != raw_artifact_sha256:
        raise PropertyIngestError(
            "USVI Capture CAMA artifact SHA-256 disagrees with the local file"
        )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_document_id,
        record_kind=_text(record.get("record_kind")) or "document_artifact",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=storage_path,
        raw_artifact_sha256=digest,
        warnings=warnings,
    )
    existing = db.execute(
        """
        SELECT artifact_id
        FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid='78'
          AND native_document_id=? AND sha256=?
        """,
        (source_id, native_document_id, digest),
    ).fetchone()
    values = (
        None,
        digest,
        _text(record.get("media_type")),
        None,
        storage_path,
        _text(record.get("source_url")),
        "direct_official_print_view_download",
        "official_public_assessment_tax_print_view",
        "public",
        retrieved_at,
    )
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, '78', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, native_document_id, *values),
        )
        artifact_id = int(cursor.lastrowid)
    else:
        artifact_id = int(existing["artifact_id"])
        db.execute(
            """
            UPDATE document_artifact SET
                instrument_id=?, sha256=?, mime_type=?, page_count=?,
                storage_path=?, source_url=?, acquisition_method=?,
                rights_tier=?, access_state=?, acquired_at=?
            WHERE artifact_id=?
            """,
            (*values, artifact_id),
        )
    return {
        "artifact_id": artifact_id,
        "canonical_ref": _text(record.get("canonical_ref")),
        "native_document_id": native_document_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "artifacts_upserted": 1,
        "recorded_instruments_upserted": 0,
        "ownership_assertions_upserted": 0,
    }


def _ingest_usvi_property_tax_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project tax-year CAMA observations without converting them to title."""

    _assert_record_source(record, source_id)
    _usvi_cama_jurisdiction(db)
    record_kind = _text(record.get("record_kind")) or "source_observation"
    if record_kind in USVI_CAMA_ARTIFACT_KINDS:
        return _ingest_usvi_cama_artifact(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
        )

    query_fingerprint, retrieved_at, status, warnings = _observation_context(
        envelope
    )
    parcel_number = _text(record.get("formatted_parcel_number"))
    tax_year = _text(record.get("tax_year"))
    if not parcel_number or not tax_year:
        source_native_id = (
            _text(record.get("canonical_ref"))
            or _text(record.get("source_id"))
            or sha256_fingerprint(record)
        )
        observation_id, record_hash = _insert_observation(
            db,
            source_id=source_id,
            source_native_id=source_native_id,
            record_kind=record_kind,
            query_fingerprint=query_fingerprint,
            source_url=_record_source_url(envelope, record),
            retrieved_at=retrieved_at,
            access_status=status,
            schema_fingerprint=_record_schema_fingerprint(record),
            raw=record,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            warnings=warnings,
        )
        return {
            "projection_skipped": True,
            "reason": "usvi_cama_source_metadata_without_parcel_tax_year",
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "record_kind": record_kind,
        }
    if not re.fullmatch(r"\d{4}", tax_year):
        raise PropertyIngestError(
            "USVI Capture CAMA tax year must be a four-digit source year"
        )

    observation_identity = record.get("observation_identity")
    expected_native_id = f"{parcel_number}|tax-year:{tax_year}"
    if isinstance(observation_identity, Mapping):
        identity_parcel = _text(
            observation_identity.get("formatted_parcel_number")
        )
        identity_year = _text(observation_identity.get("tax_year"))
        identity_native_id = _text(observation_identity.get("native_id"))
        if (
            identity_parcel != parcel_number
            or identity_year != tax_year
            or identity_native_id != expected_native_id
        ):
            raise PropertyIngestError(
                "USVI Capture CAMA observation identity disagrees with its "
                "formatted parcel number or tax year"
            )
    native_id = expected_native_id
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid="78",
        native_parcel_id=parcel_number,
        roll_year=tax_year,
        effective_from=None,
        source_good_through=None,
        observation_id=observation_id,
        record=record,
    )
    internal_parcel_id = _text(record.get("source_internal_parcel_id"))
    aliases_inserted = _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="capture_cama_tax_year_parcel_id",
        alias_value=internal_parcel_id,
        source_id=source_id,
        effective_from=tax_year,
    )

    current = record.get("current_published_observation")
    current = dict(current) if isinstance(current, Mapping) else {}
    addresses_inserted = 0
    for role, field in (
        ("situs", "property_address"),
        ("mailing", "mailing_address"),
    ):
        raw_address = _text(current.get(field))
        if raw_address:
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role=role,
                    address={"raw": raw_address},
                    effective_from=retrieved_at,
                )
            )

    owners_upserted = 0
    owner_name = _text(current.get("owner_name"))
    if owner_name:
        owners_upserted = _upsert_assessor_owner(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            raw_name=owner_name,
            effective_from=retrieved_at,
            confidence="high",
            observation_id=observation_id,
            evidence_ref=(
                _text(record.get("canonical_ref"))
                or canonical_property_ref(
                    source_id,
                    "78",
                    "parcel_assessment_tax_observation",
                    native_id,
                )
            ),
        )

    assessments_upserted = 0
    current_assessment_values = {
        "land_value": _usvi_cama_amount(current.get("land_value")),
        "improvement_value": _usvi_cama_amount(
            current.get("improvement_value")
        ),
        "total_value": _usvi_cama_amount(current.get("total_value")),
        "assessed_value": _usvi_cama_amount(current.get("assessed_value")),
        "exempt_value": _usvi_cama_amount(current.get("exemption")),
    }
    if any(value is not None for value in current_assessment_values.values()):
        assessments_upserted += _upsert_assessment_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=tax_year,
            assessment_class=current.get("property_class"),
            source_good_through=None,
            observation_id=observation_id,
            raw={"tax_year": tax_year, **current},
            **current_assessment_values,
        )

    tax_events_upserted = 0
    for event_type, field in (
        ("property_tax_current_year_due_snapshot", "current_year_due"),
        ("property_tax_total_due_snapshot", "total_due"),
    ):
        amount = _usvi_cama_amount(current.get(field))
        if amount is None:
            continue
        tax_events_upserted += _upsert_tax_account_event(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            event_type=event_type,
            tax_year=tax_year,
            event_date=_date_prefix(retrieved_at),
            amount=amount,
            status="source_observed_balance_snapshot",
            native_event_id=native_id,
            observation_id=observation_id,
            raw={"tax_year": tax_year, **current},
        )

    components = record.get("components")
    components = dict(components) if isinstance(components, Mapping) else {}
    valuation = components.get("valuation")
    valuation = dict(valuation) if isinstance(valuation, Mapping) else {}
    valuation_history = valuation.get("valuation_history")
    if not isinstance(valuation_history, list):
        valuation_history = []
    for value in valuation_history:
        row = _mapping(value, "record.components.valuation.valuation_history[]")
        fields = _mapping(row.get("published_fields"), "valuation.published_fields")
        row_year = _text(fields.get("Year"))
        if not row_year or not re.fullmatch(r"\d{4}", row_year):
            continue
        row_parcel_id = (
            parcel_id
            if row_year == tax_year
            else _usvi_cama_parcel_for_year(
                db,
                parcel_number=parcel_number,
                tax_year=row_year,
                observation_id=observation_id,
                record=row,
            )
        )
        assessments_upserted += _upsert_assessment_projection(
            db,
            parcel_id=row_parcel_id,
            source_id=source_id,
            tax_year=row_year,
            land_value=_usvi_cama_amount(fields.get("Land Value")),
            improvement_value=_usvi_cama_amount(fields.get("Imp Value")),
            total_value=_usvi_cama_amount(fields.get("Final Value")),
            assessed_value=(
                current_assessment_values["assessed_value"]
                if row_year == tax_year
                else None
            ),
            exempt_value=(
                current_assessment_values["exempt_value"]
                if row_year == tax_year
                else None
            ),
            assessment_class=(
                current.get("property_class") if row_year == tax_year else None
            ),
            source_good_through=None,
            observation_id=observation_id,
            raw=row,
        )

    statements = valuation.get("statements")
    if not isinstance(statements, list):
        statements = []
    for value in statements:
        row = _mapping(value, "record.components.valuation.statements[]")
        fields = _mapping(row.get("published_fields"), "statement.published_fields")
        identity = row.get("statement_identity")
        identity = dict(identity) if isinstance(identity, Mapping) else {}
        row_year = _text(identity.get("tax_year") or fields.get("Year"))
        statement_number = _text(
            identity.get("statement_number") or fields.get("Statement")
        )
        if not row_year or not statement_number:
            continue
        row_parcel_id = (
            parcel_id
            if row_year == tax_year
            else _usvi_cama_parcel_for_year(
                db,
                parcel_number=parcel_number,
                tax_year=row_year,
                observation_id=observation_id,
                record=row,
            )
        )
        balance = _usvi_cama_amount(fields.get("Balance"))
        tax_events_upserted += _upsert_tax_account_event(
            db,
            parcel_id=row_parcel_id,
            source_id=source_id,
            event_type="property_tax_statement",
            tax_year=row_year,
            event_date=_date_prefix(fields.get("Due Date")),
            amount=(
                balance
                if balance is not None
                else _usvi_cama_amount(fields.get("Total Due"))
            ),
            status=(
                "source_observed_paid"
                if balance == Decimal("0")
                else "source_observed_statement"
            ),
            native_event_id=statement_number,
            observation_id=observation_id,
            raw=row,
        )

    payments = valuation.get("payment_transactions")
    if not isinstance(payments, list):
        payments = []
    for value in payments:
        row = _mapping(
            value,
            "record.components.valuation.payment_transactions[]",
        )
        fields = _mapping(row.get("published_fields"), "payment.published_fields")
        identity = row.get("payment_identity")
        identity = dict(identity) if isinstance(identity, Mapping) else {}
        row_year = _text(
            identity.get("record_year") or fields.get("Record Year")
        )
        transaction_id = _text(
            identity.get("transaction_id") or fields.get("Transaction Id")
        )
        if not row_year or not transaction_id:
            continue
        row_parcel_id = (
            parcel_id
            if row_year == tax_year
            else _usvi_cama_parcel_for_year(
                db,
                parcel_number=parcel_number,
                tax_year=row_year,
                observation_id=observation_id,
                record=row,
            )
        )
        tax_events_upserted += _upsert_tax_account_event(
            db,
            parcel_id=row_parcel_id,
            source_id=source_id,
            event_type="property_tax_payment",
            tax_year=row_year,
            event_date=_date_prefix(fields.get("Pay Date")),
            amount=_usvi_cama_amount(fields.get("Amount")),
            status="source_observed_payment",
            native_event_id=transaction_id,
            observation_id=observation_id,
            raw=row,
        )

    return {
        "parcel_id": parcel_id,
        "canonical_ref": _text(record.get("canonical_ref")),
        "native_parcel_id": parcel_number,
        "tax_year": tax_year,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "tax_events_upserted": tax_events_upserted,
        "owners_upserted": owners_upserted,
        "owner_assertion_basis": "assessment_roll_tax_year_observation",
        "payer_names_projected_as_owners": False,
        "sales_upserted": 0,
        "recorded_instruments_upserted": 0,
        "title_assertions_upserted": 0,
    }


def _ingest_usvi_recorder_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one USVI index/detail row without deriving present ownership."""

    _assert_record_source(record, source_id)
    district = query_usvi_recorder.normalize_district(record.get("district"))
    inst_id = _text(record.get("native_inst_id"))
    instrument_number = _text(
        record.get("instrument_number") or record.get("document_number")
    )
    if district is None or inst_id is None or instrument_number is None:
        raise PropertyIngestError(
            "USVI recorder projection requires district, instId, and "
            "instrument number"
        )
    native_identity = query_usvi_recorder.native_instrument_identity(
        district,
        inst_id,
    )
    if _text(record.get("native_document_id")) != native_identity:
        raise PropertyIngestError(
            "USVI recorder native_document_id must be district:instId"
        )
    expected_ref = canonical_property_ref(
        source_id,
        query_usvi_recorder.TERRITORY_GEOID,
        "instrument",
        native_identity,
    )
    canonical_ref = _text(record.get("canonical_ref"))
    if canonical_ref != expected_ref:
        raise PropertyIngestError(
            "USVI recorder canonical_ref does not preserve district:instId identity"
        )

    locator = record.get("source_locator")
    if not isinstance(locator, Mapping):
        raise PropertyIngestError("USVI recorder record lacks its exact source locator")
    locator_district = query_usvi_recorder.normalize_district(
        locator.get("district")
    )
    if (
        locator_district != district
        or _text(locator.get("inst_id")) != inst_id
        or _text(locator.get("instrument_number")) != instrument_number
    ):
        raise PropertyIngestError(
            "USVI recorder source locator disagrees with emitted record identity"
        )

    projected = dict(record)
    projected["execution_date"] = (
        _text(record.get("execution_date"))
        or _text(record.get("instrument_date"))
    )
    if "legal_descriptions" not in projected:
        legal = record.get("legal")
        projected["legal_descriptions"] = (
            [dict(legal)]
            if isinstance(legal, Mapping)
            and any(_text(value) for value in legal.values())
            else []
        )

    documents = record.get("documents", [])
    if not isinstance(documents, list):
        raise PropertyIngestError("USVI recorder record.documents must be a list")
    normalized_documents: list[dict[str, Any]] = []
    for index, value in enumerate(documents):
        document = _mapping(value, f"record.documents[{index}]")
        artifact_id = _text(
            document.get("native_artifact_id")
            or document.get("native_document_id")
        )
        if not artifact_id:
            continue
        expected_prefix = f"{native_identity}:page:"
        if not artifact_id.startswith(expected_prefix):
            raise PropertyIngestError(
                "USVI recorder page artifact must be nested under district:instId"
            )
        if _text(document.get("representation_of")) != expected_ref:
            raise PropertyIngestError(
                "USVI recorder page artifact must represent its selected instrument"
            )
        normalized_documents.append(
            {
                **dict(document),
                "native_document_id": artifact_id,
                "storage_path": _text(
                    document.get("storage_path") or document.get("local_path")
                ),
                "page_count": 1,
                "access_state": "public",
                "certification_status": (
                    "official_host_reference_image_uncertified"
                ),
            }
        )
    projected["documents"] = normalized_documents

    result = _ingest_county_recorder_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
    )
    return {
        **result,
        "native_instrument_identity": native_identity,
        "instrument_number_lookup": instrument_number,
        "ownership_assertions_upserted": 0,
        "artifacts_upserted": result.get("documents_upserted", 0),
    }


def _ohio_pax_record_sources(
    record: Mapping[str, Any],
    query_source_id: str,
) -> tuple[str, str, str, str, str]:
    try:
        (
            jurisdiction_geoid,
            jurisdiction_name,
            state_code,
            expected_identity_source_id,
        ) = OHIO_PAX_RECORDER_SCOPES[query_source_id]
    except KeyError as error:
        raise PropertyIngestError(
            f"unsupported Ohio PAX recorder source: {query_source_id}"
        ) from error

    identity_source_id = (
        _text(record.get("record_identity_source_id"))
        or expected_identity_source_id
    )
    if identity_source_id != expected_identity_source_id:
        raise PropertyIngestError(
            "Ohio recorder record identity source does not match its county "
            f"component: {identity_source_id!r}"
        )
    representation_source_id = (
        _text(record.get("representation_source_id")) or query_source_id
    )
    allowed_representations = {expected_identity_source_id}
    if expected_identity_source_id == OHIO_LICKING_PAX_SOURCE_ID:
        allowed_representations.add(OHIO_LICKING_DETAIL_SOURCE_ID)
    if representation_source_id not in allowed_representations:
        raise PropertyIngestError(
            "Ohio recorder record has an unrelated representation source: "
            f"{representation_source_id!r}"
        )
    if (
        query_source_id == OHIO_LICKING_DETAIL_SOURCE_ID
        and representation_source_id != OHIO_LICKING_DETAIL_SOURCE_ID
    ):
        raise PropertyIngestError(
            "Licking exact-detail envelopes must retain the exact-detail "
            "representation source"
        )
    record_source_id = _text(record.get("source_id"))
    if record_source_id and record_source_id not in {
        identity_source_id,
        representation_source_id,
    }:
        raise PropertyIngestError(
            "Ohio recorder record source does not match its identity or "
            f"representation component: {record_source_id!r}"
        )
    if (
        representation_source_id == OHIO_LICKING_DETAIL_SOURCE_ID
        and record.get("independent_corroboration") is True
    ):
        raise PropertyIngestError(
            "Licking exact detail is an alternate representation of the PAX "
            "instrument identity, not independent corroboration"
        )
    return (
        identity_source_id,
        representation_source_id,
        jurisdiction_geoid,
        jurisdiction_name,
        state_code,
    )


def _ohio_pax_persistable_url(
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    representation_source_id: str,
) -> str | None:
    if representation_source_id == OHIO_DELAWARE_PAX_SOURCE_ID:
        return (
            _text(record.get("portal_url"))
            or query_ohio_pax_recorders.DELAWARE.pax_root
        )
    if representation_source_id == OHIO_LICKING_PAX_SOURCE_ID:
        return (
            _text(record.get("portal_url"))
            or query_ohio_pax_recorders.LICKING.pax_root
        )
    return _record_source_url(envelope, record)


def _ohio_pax_book_page(value: Any) -> tuple[str | None, str | None]:
    text = _text(value)
    if not text:
        return None, None
    if "/" not in text:
        return text, None
    book, page = text.split("/", 1)
    return _text(book), _text(page)


def _upsert_ohio_pax_document_artifact(
    db,
    *,
    representation_source_id: str,
    jurisdiction_geoid: str,
    identity_native_id: str,
    instrument_id: int,
    sha256: str | None,
    mime_type: str | None,
    page_count: int | None,
    storage_path: str | None,
    source_url: str | None,
    retrieved_at: str,
) -> int:
    native_document_id = f"{identity_native_id}:official-public-pdf"
    existing = None
    if sha256:
        existing = db.execute(
            """
            SELECT artifact_id
            FROM document_artifact
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_document_id=? AND sha256=?
            """,
            (
                representation_source_id,
                jurisdiction_geoid,
                native_document_id,
                sha256,
            ),
        ).fetchone()
        if existing is None:
            existing = db.execute(
                """
                SELECT artifact_id
                FROM document_artifact
                WHERE source_id=? AND jurisdiction_geoid=?
                  AND native_document_id=? AND sha256 IS NULL
                ORDER BY artifact_id
                LIMIT 1
                """,
                (
                    representation_source_id,
                    jurisdiction_geoid,
                    native_document_id,
                ),
            ).fetchone()
    else:
        existing = db.execute(
            """
            SELECT artifact_id
            FROM document_artifact
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_document_id=?
            ORDER BY CASE WHEN sha256 IS NULL THEN 0 ELSE 1 END, artifact_id
            LIMIT 1
            """,
            (
                representation_source_id,
                jurisdiction_geoid,
                native_document_id,
            ),
        ).fetchone()
    downloaded = bool(sha256 or storage_path)
    acquisition_method = (
        "official_public_pdf" if downloaded else "portal_metadata"
    )
    acquired_at = retrieved_at if downloaded else None
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'public', ?)
            """,
            (
                representation_source_id,
                jurisdiction_geoid,
                native_document_id,
                instrument_id,
                sha256,
                mime_type,
                page_count,
                storage_path,
                source_url,
                acquisition_method,
                "source_public_record",
                acquired_at,
            ),
        )
        return int(cursor.lastrowid)
    artifact_id = int(existing["artifact_id"])
    db.execute(
        """
        UPDATE document_artifact
        SET instrument_id=?,
            sha256=COALESCE(?, sha256),
            mime_type=COALESCE(?, mime_type),
            page_count=COALESCE(?, page_count),
            storage_path=COALESCE(?, storage_path),
            source_url=COALESCE(?, source_url),
            acquisition_method=?,
            rights_tier='source_public_record',
            access_state='public',
            acquired_at=COALESCE(?, acquired_at)
        WHERE artifact_id=?
        """,
        (
            instrument_id,
            sha256,
            mime_type,
            page_count,
            storage_path,
            source_url,
            acquisition_method,
            acquired_at,
            artifact_id,
        ),
    )
    return artifact_id


def _ingest_ohio_pax_recorder_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    (
        identity_source_id,
        representation_source_id,
        expected_geoid,
        jurisdiction_name,
        state_code,
    ) = _ohio_pax_record_sources(record, source_id)
    jurisdiction_geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid=expected_geoid,
        fallback_name=jurisdiction_name,
        fallback_state_code=state_code,
    )
    if jurisdiction_geoid != expected_geoid:
        raise PropertyIngestError(
            f"{source_id} Ohio recorder record has out-of-scope GEOID "
            f"{jurisdiction_geoid}"
        )

    record_kind = _text(record.get("record_kind"))
    if record_kind not in {
        "source_probe",
        "recorded_instrument_detail",
        "recorded_instrument_document",
    }:
        raise PropertyIngestError(
            f"unsupported Ohio recorder record kind: {record_kind!r}"
        )
    identity_native_id = (
        _text(record.get("instrument_reference_id"))
        if identity_source_id == OHIO_DELAWARE_PAX_SOURCE_ID
        else _text(record.get("instrument_number"))
    )
    if record_kind == "source_probe":
        identity_native_id = (
            identity_native_id
            or _text(record.get("sentinel_reference_id"))
            or _text(record.get("sentinel_instrument"))
            or _text(record.get("canonical_ref"))
            or "source-probe"
        )
    if not identity_native_id:
        identity_label = (
            "instrument_reference_id"
            if identity_source_id == OHIO_DELAWARE_PAX_SOURCE_ID
            else "instrument_number"
        )
        raise PropertyIngestError(
            f"Ohio recorder record lacks stable {identity_label}"
        )

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    persistable_url = _ohio_pax_persistable_url(
        envelope,
        record,
        representation_source_id,
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=representation_source_id,
        source_native_id=identity_native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=persistable_url,
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    common_result = {
        "record_identity_source_id": identity_source_id,
        "representation_source_id": representation_source_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "parcels_upserted": 0,
        "addresses_inserted": 0,
        "sales_upserted": 0,
        "ownership_assertions_upserted": 0,
    }
    if record_kind == "source_probe":
        return {
            **common_result,
            "projection_skipped": True,
            "reason": "access_and_contract_probe",
            "record_kind": record_kind,
        }

    if record_kind == "recorded_instrument_detail":
        book, page = _ohio_pax_book_page(record.get("book_page"))
        db.execute(
            """
            INSERT INTO recorded_instrument(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_type, book, page, execution_date, recording_date,
                consideration_minor, currency, legal_description_raw,
                source_url, observation_id, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, 'USD', ?, ?, ?, ?)
            ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
            DO UPDATE SET
                instrument_type=COALESCE(
                    excluded.instrument_type, recorded_instrument.instrument_type
                ),
                book=COALESCE(excluded.book, recorded_instrument.book),
                page=COALESCE(excluded.page, recorded_instrument.page),
                recording_date=COALESCE(
                    excluded.recording_date, recorded_instrument.recording_date
                ),
                consideration_minor=COALESCE(
                    excluded.consideration_minor,
                    recorded_instrument.consideration_minor
                ),
                legal_description_raw=COALESCE(
                    excluded.legal_description_raw,
                    recorded_instrument.legal_description_raw
                ),
                source_url=COALESCE(
                    excluded.source_url, recorded_instrument.source_url
                ),
                observation_id=excluded.observation_id,
                raw_json=excluded.raw_json
            """,
            (
                identity_source_id,
                jurisdiction_geoid,
                identity_native_id,
                _text(record.get("document_type")),
                book,
                page,
                _date_prefix(
                    record.get("recorded_date_iso")
                    or record.get("recorded_at_iso")
                ),
                _minor_units(record.get("consideration_amount")),
                _text(record.get("legal_description")),
                persistable_url,
                observation_id,
                canonical_json(record),
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO recorded_instrument(
                source_id, jurisdiction_geoid, native_document_id,
                source_url, observation_id, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
            DO UPDATE SET
                source_url=COALESCE(
                    recorded_instrument.source_url, excluded.source_url
                ),
                observation_id=COALESCE(
                    recorded_instrument.observation_id, excluded.observation_id
                )
            """,
            (
                identity_source_id,
                jurisdiction_geoid,
                identity_native_id,
                persistable_url,
                observation_id,
                canonical_json(record),
            ),
        )
    instrument_row = db.execute(
        """
        SELECT instrument_id
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (identity_source_id, jurisdiction_geoid, identity_native_id),
    ).fetchone()
    instrument_id = int(instrument_row["instrument_id"])

    parties_upserted = 0
    if record_kind == "recorded_instrument_detail":
        occurrences_value = record.get("party_occurrences")
        if occurrences_value is None:
            occurrences_value = [
                *[
                    {"role": "grantor", "display_name": value}
                    for value in record.get("grantors", [])
                ],
                *[
                    {"role": "grantee", "display_name": value}
                    for value in record.get("grantees", [])
                ],
            ]
        if not isinstance(occurrences_value, list):
            raise PropertyIngestError(
                "Ohio recorder party_occurrences must be a list"
            )
        for sequence_no, raw_occurrence in enumerate(
            occurrences_value,
            start=1,
        ):
            occurrence = _mapping(
                raw_occurrence,
                f"record.party_occurrences[{sequence_no - 1}]",
            )
            raw_name = _text(
                occurrence.get("display_name")
                or occurrence.get("name")
                or occurrence.get("raw_name")
            )
            if not raw_name:
                continue
            role = _text(occurrence.get("role")) or "other"
            db.execute(
                """
                INSERT INTO instrument_party(
                    instrument_id, sequence_no, role, raw_name,
                    normalized_name, entity_kind, raw_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instrument_id, sequence_no, role, raw_name)
                DO UPDATE SET
                    normalized_name=excluded.normalized_name,
                    entity_kind=COALESCE(
                        excluded.entity_kind, instrument_party.entity_kind
                    ),
                    raw_address=COALESCE(
                        excluded.raw_address, instrument_party.raw_address
                    )
                """,
                (
                    instrument_id,
                    sequence_no,
                    role,
                    raw_name,
                    " ".join(raw_name.upper().split()),
                    _text(occurrence.get("entity_kind")),
                    _text(occurrence.get("raw_address")),
                ),
            )
            parties_upserted += 1

    artifact_id = None
    page_count = None
    raw_page_count = record.get("page_count")
    try:
        page_count = (
            int(raw_page_count)
            if raw_page_count not in (None, "")
            else None
        )
    except (TypeError, ValueError):
        page_count = None
    artifact_available = record_kind == "recorded_instrument_document"
    artifact_media_type = _text(record.get("media_type"))
    artifact_source_url = persistable_url
    artifact_sha256 = _text(record.get("sha256"))
    artifact_storage_path = _text(record.get("local_path"))
    if record_kind == "recorded_instrument_detail":
        document = record.get("document")
        if isinstance(document, Mapping):
            artifact_available = document.get("available") is True
            artifact_media_type = _text(document.get("media_type"))
            artifact_source_url = (
                _text(document.get("source_url")) or artifact_source_url
            )
        document_access = record.get("document_access")
        if isinstance(document_access, Mapping):
            artifact_available = document_access.get("has_image") is True
            raw_access_pages = document_access.get("page_count")
            try:
                page_count = (
                    int(raw_access_pages)
                    if raw_access_pages not in (None, "")
                    else page_count
                )
            except (TypeError, ValueError):
                pass
            artifact_media_type = artifact_media_type or "application/pdf"
        artifact_source_url = _ohio_pax_persistable_url(
            envelope,
            {**record, "source_url": artifact_source_url},
            representation_source_id,
        )
    if artifact_available:
        artifact_id = _upsert_ohio_pax_document_artifact(
            db,
            representation_source_id=representation_source_id,
            jurisdiction_geoid=jurisdiction_geoid,
            identity_native_id=identity_native_id,
            instrument_id=instrument_id,
            sha256=artifact_sha256,
            mime_type=artifact_media_type or "application/pdf",
            page_count=page_count,
            storage_path=artifact_storage_path,
            source_url=artifact_source_url,
            retrieved_at=retrieved_at,
        )

    return {
        **common_result,
        "instrument_id": instrument_id,
        "canonical_ref": canonical_property_ref(
            identity_source_id,
            jurisdiction_geoid,
            "instrument",
            identity_native_id,
        ),
        "recorded_instruments_upserted": 1,
        "parties_upserted": parties_upserted,
        "documents_upserted": int(artifact_id is not None),
        "artifact_id": artifact_id,
    }


def _ingest_statewide_parcel_observation_only(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
    reason: str,
) -> dict[str, Any]:
    """Preserve a statewide source row that is not a canonical parcel."""

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    jurisdiction = record.get("jurisdiction")
    geoid = None
    county_name = None
    if isinstance(jurisdiction, Mapping):
        geoid = _text(
            jurisdiction.get("county_geoid") or jurisdiction.get("state_fips")
        )
        county_name = _text(jurisdiction.get("county_name"))
    if not geoid or not geoid.isdigit() or len(geoid) not in {2, 5}:
        try:
            geoid = STATEWIDE_PARCEL_STATE_FIPS[source_id]
        except KeyError as error:
            raise PropertyIngestError(
                f"statewide parcel source lacks a state scope: {source_id}"
            ) from error
    state_name, state_code = STATE_METADATA[geoid[:2]]
    if len(geoid) == 5:
        name = county_name or geoid
        if not name.casefold().endswith("county"):
            name = f"{name} County"
        _upsert_jurisdiction_values(
            db,
            geoid=geoid,
            name=name,
            state_code=state_code,
            jurisdiction_type="county",
            parent_geoid=geoid[:2],
        )
    else:
        _upsert_jurisdiction_values(
            db,
            geoid=geoid,
            name=state_name,
            state_code=state_code,
            jurisdiction_type="state",
        )
    source_native_id = _text(
        record.get("native_id")
        or record.get("native_parcel_id")
        or record.get("object_id")
        or record.get("route_id")
        or record.get("record_type")
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=_text(record.get("record_type")) or "source_row",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return {
        "projection_skipped": True,
        "reason": reason,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": source_native_id,
        "record_kind": _text(record.get("record_type")),
    }


def _ingest_michigan_property_directory_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Retain Michigan county routes as discovery metadata only."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind") or record.get("record_type"))
    if not record_kind:
        raise PropertyIngestError("Michigan property-directory row lacks record_kind")
    canonical_ref = _text(record.get("canonical_ref"))
    source_native_id = (
        canonical_ref
        or _text(record.get("alternative_id"))
        or _text(record.get("county_fips"))
        or _text(record.get("platform_family"))
    )
    if not source_native_id:
        raise PropertyIngestError(
            "Michigan property-directory row lacks a stable identity"
        )

    county_fips = _text(record.get("county_fips"))
    county_name = _text(record.get("county"))
    jurisdiction = record.get("jurisdiction")
    if isinstance(jurisdiction, Mapping):
        county_fips = county_fips or _text(jurisdiction.get("county_fips"))
        county_name = county_name or _text(jurisdiction.get("county"))
    if county_fips is not None and (
        not county_fips.isdigit()
        or len(county_fips) != 5
        or not county_fips.startswith("26")
    ):
        raise PropertyIngestError(
            "Michigan property-directory county_fips must be a Michigan GEOID"
        )

    _upsert_jurisdiction_values(
        db,
        geoid="26",
        name="Michigan",
        state_code="MI",
        jurisdiction_type="state",
    )
    if county_fips:
        normalized_county_name = county_name or county_fips
        if not normalized_county_name.casefold().endswith("county"):
            normalized_county_name = f"{normalized_county_name} County"
        _upsert_jurisdiction_values(
            db,
            geoid=county_fips,
            name=normalized_county_name,
            state_code="MI",
            jurisdiction_type="county",
            parent_geoid="26",
        )

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    provenance = record.get("provenance")
    schema_fingerprint = _record_schema_fingerprint(record)
    if schema_fingerprint is None and isinstance(provenance, Mapping):
        schema_fingerprint = _text(provenance.get("response_schema_fingerprint"))
    discovered_from = record.get("discovered_from")
    source_url = _text(record.get("source_url"))
    if source_url is None and isinstance(discovered_from, Mapping):
        source_url = _text(discovered_from.get("source_url"))
    source_url = source_url or _record_url(envelope)

    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=source_url,
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=schema_fingerprint,
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    capability_evidence = record.get("capability_evidence")
    destination_verified_roles: list[str] = []
    review_flags: list[str] = []
    if isinstance(capability_evidence, Mapping):
        verified = capability_evidence.get("destination_verified_roles")
        if isinstance(verified, (list, tuple)):
            destination_verified_roles = [str(value) for value in verified]
        flags = capability_evidence.get("review_flags")
        if isinstance(flags, (list, tuple)):
            review_flags = [str(value) for value in flags]
    destination_triage = record.get("destination_triage")
    if isinstance(destination_triage, Mapping):
        flags = destination_triage.get("review_flags")
        if isinstance(flags, (list, tuple)):
            review_flags = [str(value) for value in flags]

    return {
        "projection_skipped": True,
        "reason": "michigan_directory_metadata_has_no_property_event_semantics",
        "projection": "source_discovery_observation_only",
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": source_native_id,
        "record_kind": record_kind,
        "county_fips": county_fips,
        "publisher_declared_role": record.get("publisher_declared_role"),
        "destination_verified_roles": destination_verified_roles,
        "review_flags": review_flags,
        "created_property_records": 0,
        "created_ownership_or_title_assertions": 0,
    }


def _ingest_michigan_eaton_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project DBF parcel rows and retain other Eaton source records as metadata."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind") or record.get("record_type"))
    if record_kind == "parcel_assessment_snapshot":
        return _ingest_assessor_record(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            observation_kind=record_kind,
        )

    _upsert_jurisdiction_values(
        db,
        geoid="26",
        name="Michigan",
        state_code="MI",
        jurisdiction_type="state",
    )
    _upsert_jurisdiction_values(
        db,
        geoid="26045",
        name="Eaton County",
        state_code="MI",
        jurisdiction_type="county",
        parent_geoid="26",
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_native_id = _text(
        record.get("canonical_ref") or record.get("evidence_ref") or record_kind
    )
    if not source_native_id:
        raise PropertyIngestError("Eaton source metadata row lacks a stable identity")
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=record_kind or "source_metadata",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return {
        "projection_skipped": True,
        "reason": "eaton_non_parcel_source_metadata_observation",
        "projection": "source_snapshot_observation_only",
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": source_native_id,
        "record_kind": record_kind,
        "created_property_records": 0,
        "created_ownership_or_title_assertions": 0,
    }


def _ingest_georgia_property_source_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Retain Georgia routing and acquisition records without property projection."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind") or record.get("record_type"))
    if not record_kind:
        raise PropertyIngestError("Georgia property-source row lacks record_kind")

    county_geoid = _text(record.get("county_geoid"))
    county_name = _text(record.get("county_name"))
    if county_geoid is not None and (
        not county_geoid.isdigit()
        or len(county_geoid) != 5
        or not county_geoid.startswith("13")
    ):
        raise PropertyIngestError(
            "Georgia property-source county_geoid must be a Georgia county GEOID"
        )

    _upsert_jurisdiction_values(
        db,
        geoid="13",
        name="Georgia",
        state_code="GA",
        jurisdiction_type="state",
    )
    if county_geoid:
        normalized_county_name = county_name or county_geoid
        if not normalized_county_name.casefold().endswith("county"):
            normalized_county_name = f"{normalized_county_name} County"
        _upsert_jurisdiction_values(
            db,
            geoid=county_geoid,
            name=normalized_county_name,
            state_code="GA",
            jurisdiction_type="county",
            parent_geoid="13",
        )

    source_native_id = _text(
        record.get("canonical_ref")
        or record.get("evidence_ref")
        or county_geoid
        or record.get("platform_family")
    )
    if not source_native_id:
        source_native_id = f"{source_id}:{record_kind}:13"

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return {
        "projection_skipped": True,
        "reason": "georgia_source_routing_or_acquisition_metadata_only",
        "projection": "source_snapshot_observation_only",
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": source_native_id,
        "record_kind": record_kind,
        "county_geoid": county_geoid,
        "created_property_records": 0,
        "created_ownership_or_title_assertions": 0,
    }


def _licking_auditor_transfer_supports_sale_projection(
    transfer: Mapping[str, Any],
) -> bool:
    """Return whether an Auditor transfer has source-published sale support."""

    valid_sale = _text(transfer.get("valid_sale"))
    if valid_sale is not None:
        return valid_sale.casefold() in {"1", "true", "valid", "y", "yes"}
    amount = transfer.get("sale_amount")
    if amount in (None, "") or isinstance(amount, bool):
        return False
    try:
        return Decimal(str(amount).replace(",", "").replace("$", "")) > 0
    except InvalidOperation:
        return False


def _assert_observation_county_scope(
    record: Mapping[str, Any],
    *,
    source_id: str,
    expected_geoid: str,
) -> None:
    """Reject an observation-only record that publishes another county."""

    jurisdiction = record.get("jurisdiction")
    if not isinstance(jurisdiction, Mapping):
        return
    metadata = jurisdiction.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    published_geoids = {
        value
        for value in (
            _text(jurisdiction.get("county_geoid")),
            _text(metadata.get("county_geoid")),
            _text(jurisdiction.get("jurisdiction_id")),
        )
        if value
    }
    mismatches = sorted(
        value for value in published_geoids if value != expected_geoid
    )
    if mismatches:
        raise PropertyIngestError(
            f"{source_id} observation has out-of-scope county GEOID "
            f"{mismatches[0]}"
        )


def _ingest_ohio_licking_auditor_gis_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project Licking assessment rows while retaining every GIS occurrence."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    occurrence = (
        record.get("occurrence_identity")
        if isinstance(record.get("occurrence_identity"), Mapping)
        else {}
    )
    occurrence_id = _text(
        occurrence.get("native_id")
        or record.get("native_id")
        or record.get("source_record_id")
    )
    if (
        record_kind
        != "county_assessor_parcel_feature_occurrence"
        or not occurrence_id
    ):
        _assert_observation_county_scope(
            record,
            source_id=source_id,
            expected_geoid="39089",
        )
        preserved = dict(record)
        jurisdiction = (
            dict(preserved["jurisdiction"])
            if isinstance(preserved.get("jurisdiction"), Mapping)
            else {}
        )
        jurisdiction_metadata = (
            jurisdiction.get("metadata")
            if isinstance(jurisdiction.get("metadata"), Mapping)
            else {}
        )
        jurisdiction.update(
            {
                "state_code": _text(jurisdiction.get("state_code")) or "OH",
                "state_fips": (
                    _text(jurisdiction.get("state_fips"))
                    or _text(jurisdiction_metadata.get("state_fips"))
                    or "39"
                ),
                "county_name": (
                    _text(jurisdiction.get("county_name"))
                    or _text(jurisdiction_metadata.get("county_name"))
                    or "Licking County"
                ),
                "county_geoid": (
                    _text(jurisdiction.get("county_geoid"))
                    or _text(jurisdiction_metadata.get("county_geoid"))
                    or "39089"
                ),
            }
        )
        preserved["jurisdiction"] = jurisdiction
        preserved["record_type"] = (
            record_kind or "licking_auditor_source_contract"
        )
        preserved["native_id"] = (
            occurrence_id
            or _text(record.get("schema_fingerprint"))
            or _text(record.get("layer_url"))
            or _text(record.get("source_record_id"))
            or query_ohio_licking_property.SOURCE_ID
        )
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=preserved,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="licking_auditor_non_feature_source_observation",
        )

    parcel_number = _text(record.get("parcel_number"))
    if not parcel_number:
        _assert_observation_county_scope(
            record,
            source_id=source_id,
            expected_geoid="39089",
        )
        preserved = dict(record)
        preserved["record_type"] = record_kind
        preserved["native_id"] = occurrence_id
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=preserved,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="licking_gis_occurrence_has_no_usable_parcel_join",
        )

    projected = dict(record)
    projected.update(
        {
            "native_parcel_id": parcel_number,
            "source_occurrence_id": occurrence_id,
            "alternate_parcel_ids": [],
            "snapshot_complete": True,
            "snapshot_completeness": {
                "role": "county_assessor_joined_feature_snapshot",
                "occurrence_identity": occurrence.get("identity_basis"),
                "recorded_title": False,
            },
            "geometry_disclaimer": (
                "Licking County Auditor GIS mapping polygon; recorded "
                "instruments and survey records remain separate evidence."
            ),
        }
    )

    pid = _text(record.get("pid"))
    if pid and pid != parcel_number:
        projected["alternate_parcel_ids"] = [pid]

    situs = record.get("situs_address_observation")
    if isinstance(situs, Mapping):
        projected["situs_address"] = {
            **dict(situs),
            "state": "OH",
            "country": "US",
        }
    mailing = record.get("mailing_address_observation")
    if isinstance(mailing, Mapping):
        projected["mailing_address"] = {
            **dict(mailing),
            "raw": mailing.get("address"),
            "country": "US",
        }

    owner_name = _text(record.get("owner_name_observation"))
    projected["owners"] = (
        [{"raw_name": owner_name, "confidence": "high"}]
        if owner_name
        else []
    )
    values = record.get("assessment_value_observations")
    if isinstance(values, Mapping):
        projected["assessment"] = {
            "land_value": values.get("market_land"),
            "improvement_value": values.get("market_improvement"),
            "parcel_value": values.get("market_total"),
            "market_value": values.get("market_total"),
            "source_tax_values": dict(values),
        }

    transfers = record.get("recent_transfer_observations")
    if isinstance(transfers, list):
        projected["sale_history"] = [
            {
                "sale_date": transfer.get("date_iso"),
                "consideration": transfer.get("sale_amount"),
                "source_document_ref": transfer.get("instrument"),
                "qualification_code": transfer.get("valid_sale"),
                "source_role": "auditor_recent_transfer_observation",
                "source_transfer": dict(transfer),
            }
            for transfer in transfers
            if isinstance(transfer, Mapping)
            and _licking_auditor_transfer_supports_sale_projection(transfer)
            and any(
                transfer.get(field) not in (None, "")
                for field in ("date_iso", "instrument", "sale_amount")
            )
        ]

    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind=record_kind,
    )
    _query_fingerprint, retrieved_at, _status, _warnings = (
        _observation_context(envelope)
    )
    aliases_inserted = 0
    for alias_type, alias_value in (
        ("auditor_pid", pid),
        ("auditor_globalid", occurrence.get("global_id")),
        ("auditor_objectid", occurrence.get("object_id")),
    ):
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=int(result["parcel_id"]),
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=retrieved_at,
        )
    result["aliases_inserted"] = (
        int(result.get("aliases_inserted", 0)) + aliases_inserted
    )
    result["feature_occurrence_id"] = occurrence_id
    result["transfer_observations_retained"] = (
        len(transfers) if isinstance(transfers, list) else 0
    )
    result["created_title_assertions"] = 0
    return result


_OHIO_FRANKLIN_AUDITOR_BULK_ROW_KINDS = frozenset(
    f"{family.replace('-', '_')}_row_observation"
    for family in query_ohio_franklin_auditor_bulk.RECORD_FAMILY_CHOICES
)


def _franklin_auditor_bulk_artifact_sha256(
    record: Mapping[str, Any],
    fallback: str | None,
) -> str | None:
    direct = _text(record.get("artifact_sha256"))
    downloaded = None
    download = record.get("download")
    if isinstance(download, Mapping):
        downloaded = _text(download.get("sha256"))
    digests = {
        digest
        for digest in (direct, downloaded, fallback)
        if digest is not None
    }
    if len(digests) > 1:
        raise PropertyIngestError(
            "Franklin Auditor bulk record artifact SHA-256 does not match "
            "the supplied raw artifact"
        )
    return direct or downloaded or fallback


def _franklin_auditor_bulk_roll_year(
    record: Mapping[str, Any],
    parsed: Mapping[str, Any],
) -> str:
    tax_year = _text(parsed.get("tax_year"))
    if tax_year and re.fullmatch(r"\d{4}", tax_year[:4]):
        return tax_year[:4]
    for value in (
        record.get("release_date"),
        record.get("release_id"),
        record.get("path_period"),
    ):
        match = re.search(
            r"(?<!\d)((?:19|20)\d{2})(?!\d)",
            _text(value) or "",
        )
        if match:
            return match.group(1)
    return ""


def _franklin_auditor_bulk_release_boundary(
    record: Mapping[str, Any],
) -> str | None:
    release_date = _text(record.get("release_date"))
    if release_date and re.fullmatch(
        r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])",
        release_date,
    ):
        return release_date
    release_id = _text(record.get("release_id")) or ""
    exact_dates = re.findall(
        r"(?<!\d)((?:19|20)\d{2}-\d{2}-\d{2})(?!\d)",
        release_id,
    )
    if exact_dates:
        return exact_dates[-1]
    period = re.search(
        r"(?<!\d)((?:19|20)\d{2}-(?:0[1-9]|1[0-2]))(?!-\d)",
        release_id,
    )
    if period:
        return period.group(1)
    year = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", release_id)
    return year.group(1) if year else None


def _franklin_auditor_bulk_daily_sale(parsed: Mapping[str, Any]) -> bool:
    """Return true for a source-published non-exempt daily conveyance."""

    record_family = _text(parsed.get("record_family"))
    exempt = re.sub(
        r"[^a-z0-9]+",
        " ",
        (_text(parsed.get("is_exempt")) or "").casefold(),
    ).strip()
    if exempt in {"y", "yes", "true", "1", "exempt"}:
        return False
    return bool(
        record_family == "daily-conveyance"
        and exempt in {"n", "no", "false", "0", "non exempt"}
    )


def _franklin_auditor_bulk_sale_native_id(
    parsed: Mapping[str, Any],
    *,
    record_family: str,
    normalized_parcel_id: str,
) -> str:
    """Build a business sale identity independent of release row location."""

    owner_names = parsed.get("owner_names")
    if not isinstance(owner_names, list):
        owner_names = []
    prior_owner_names = parsed.get("prior_owner_names")
    if not isinstance(prior_owner_names, list):
        prior_owner_names = []

    if record_family == "sales":
        business_id = _text(parsed.get("instrument_number"))
        identity_role = "instrument"
    else:
        business_id = _text(parsed.get("conveyance_number"))
        identity_role = "conveyance"
    if business_id:
        normalized_business_id = re.sub(
            r"[^A-Za-z0-9]+", "", business_id
        ).upper()
        if normalized_business_id:
            return (
                f"{record_family}:{normalized_parcel_id}:"
                f"{identity_role}:{normalized_business_id}"
            )
    semantic_identity = {
        "record_family": record_family,
        "parcel_id": normalized_parcel_id,
        "sale_date": _text(parsed.get("event_date")),
        "instrument": _text(parsed.get("instrument")),
        "sale_type": _text(parsed.get("sale_type")),
        "consideration_minor": _minor_units(parsed.get("amount")),
        "owner_names": sorted(
            value.casefold()
            for value in (_text(item) for item in owner_names)
            if value
        ),
        "prior_owner_names": sorted(
            value.casefold()
            for value in (_text(item) for item in prior_owner_names)
            if value
        ),
    }
    return (
        f"{record_family}:{normalized_parcel_id}:semantic:"
        f"{sha256_fingerprint(semantic_identity)}"
    )


def _franklin_auditor_bulk_parcel(
    db,
    *,
    native_parcel_id: str,
    normalized_parcel_id: str,
    roll_year: str,
    observation_id: int,
    release_date: str | None,
    record: Mapping[str, Any],
    event_anchor: bool = False,
) -> tuple[int, int]:
    """Resolve a Franklin row to its source-owned deterministic parcel shell."""

    bulk_params: list[Any] = [
        OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
        native_parcel_id,
        normalized_parcel_id,
        native_parcel_id,
        normalized_parcel_id,
    ]
    year_sql = ""
    if event_anchor:
        year_sql = "AND p.roll_year=''"
    elif roll_year:
        year_sql = "AND p.roll_year=?"
        bulk_params.append(roll_year)
    bulk = db.execute(
        f"""
        SELECT p.parcel_id
        FROM parcel_snapshot p
        LEFT JOIN parcel_alias a ON a.parcel_id=p.parcel_id
        WHERE p.source_id=? AND p.jurisdiction_geoid='39049'
          AND (p.native_parcel_id IN (?, ?)
               OR a.alias_value IN (?, ?))
          {year_sql}
        ORDER BY p.roll_year DESC, p.parcel_id
        LIMIT 1
        """,
        bulk_params,
    ).fetchone()
    if bulk is not None:
        return int(bulk["parcel_id"]), 0

    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
        jurisdiction_geoid="39049",
        native_parcel_id=native_parcel_id,
        roll_year=roll_year,
        effective_from=release_date,
        source_good_through=release_date,
        observation_id=observation_id,
        record=record,
    )
    return parcel_id, 1


_FRANKLIN_SALES_GIS_FEATURE_KIND = (
    "county_auditor_sale_feature_occurrence"
)
_FRANKLIN_SALES_IDENTIFIER_SENTINELS = frozenset(
    {
        "-",
        "--",
        "0",
        "n/a",
        "na",
        "none",
        "not applicable",
        "not available",
        "null",
        "unknown",
    }
)


def _franklin_sales_usable_identifier(value: Any) -> str | None:
    """Return a source identifier only when it is usable as a join key."""

    identifier = _text(value)
    if not identifier:
        return None
    casefolded = identifier.casefold()
    compact = re.sub(r"[^a-z0-9]+", "", casefolded)
    if (
        casefolded in _FRANKLIN_SALES_IDENTIFIER_SENTINELS
        or compact
        in {"na", "none", "notapplicable", "notavailable", "null", "unknown"}
    ):
        return None
    alphanumeric = re.sub(r"[^A-Za-z0-9]+", "", identifier)
    if not alphanumeric or not alphanumeric.strip("0"):
        return None
    return identifier


def _franklin_sales_normalized_identifier(value: Any) -> str | None:
    identifier = _franklin_sales_usable_identifier(value)
    if not identifier:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]+", "", identifier).upper()
    return normalized or None


def _franklin_sales_parties(
    record: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    parties = record.get("parties")
    if not isinstance(parties, Mapping):
        return [], []

    def names(field: str) -> list[str]:
        values = parties.get(field)
        if values is None:
            return []
        if not isinstance(values, list):
            raise PropertyIngestError(
                f"Franklin Sales GIS parties.{field} must be a list"
            )
        return list(
            dict.fromkeys(
                name
                for name in (_text(value) for value in values)
                if name
            )
        )

    return names("grantor_names"), names("grantee_names")


def _franklin_sales_date(value: Any) -> str | None:
    date_value = _date_prefix(value)
    if not date_value or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        return None
    try:
        datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        return None
    return date_value


def _franklin_sales_timestamp(value: Any) -> str | None:
    timestamp = _text(value)
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.isoformat()
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _franklin_sales_positive_price(value: Any) -> tuple[Any, int | None]:
    if value in (None, "") or isinstance(value, bool):
        return value, None
    try:
        minor = _minor_units(value)
    except PropertyIngestError:
        return value, None
    if minor is None or minor <= 0:
        return value, None
    return value, minor


def _franklin_sales_business_identity(
    record: Mapping[str, Any],
    *,
    normalized_parcel_id: str,
) -> tuple[str | None, str | None]:
    """Separate a source occurrence from its defensible business sale key."""

    conveyance = _franklin_sales_normalized_identifier(
        record.get("conveyance_number")
    )
    if conveyance:
        return (
            f"parcel:{normalized_parcel_id}:conveyance:{conveyance}",
            "parcel_plus_conveyance_number",
        )

    sale = record.get("sale")
    if not isinstance(sale, Mapping):
        return None, None
    sale_date = _franklin_sales_date(sale.get("date_iso"))
    _price, price_minor = _franklin_sales_positive_price(sale.get("price"))
    instrument = _text(sale.get("instrument"))
    sale_type = _text(sale.get("sale_type"))
    grantors, grantees = _franklin_sales_parties(record)
    if not (
        sale_date
        and price_minor is not None
        and instrument
        and sale_type
        and grantors
        and grantees
    ):
        return None, None
    semantic_key = {
        "parcel_id": normalized_parcel_id,
        "sale_date": sale_date,
        "price_minor": price_minor,
        "instrument": instrument.casefold(),
        "sale_type": sale_type.casefold(),
        "grantors": sorted(name.casefold() for name in grantors),
        "grantees": sorted(name.casefold() for name in grantees),
    }
    return (
        f"parcel:{normalized_parcel_id}:semantic:"
        f"{sha256_fingerprint(semantic_key)}",
        "parcel_plus_dated_price_instrument_type_and_bilateral_parties",
    )


def _franklin_sales_occurrence_identity(
    record: Mapping[str, Any],
) -> str | None:
    occurrence = record.get("occurrence_identity")
    if not isinstance(occurrence, Mapping):
        occurrence = {}
    native_id = _text(occurrence.get("native_id") or record.get("native_id"))
    if native_id:
        return native_id
    object_id = _text(
        occurrence.get("object_id") or record.get("source_record_id")
    )
    if not object_id:
        return None
    service_item_id = _text(occurrence.get("service_item_id"))
    layer_id = _text(occurrence.get("layer_id"))
    if service_item_id and layer_id is not None:
        return f"{service_item_id}:{layer_id}:OBJECTID:{object_id}"
    return f"OBJECTID:{object_id}"


def _franklin_sales_wgs84_point(
    record: Mapping[str, Any],
) -> tuple[float | None, float | None]:
    geometry = record.get("geometry")
    if not isinstance(geometry, Mapping):
        return None, None
    geometry_crs = (_text(record.get("geometry_crs")) or "").upper()
    if geometry_crs not in {"EPSG:4326", "WGS84", "WGS 84"}:
        return None, None
    try:
        longitude = float(geometry.get("x"))
        latitude = float(geometry.get("y"))
    except (TypeError, ValueError):
        return None, None
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None, None
    return longitude, latitude


def _franklin_sales_parcel_anchor(
    db,
    *,
    native_parcel_id: str,
    normalized_parcel_id: str,
    observation_id: int,
    record: Mapping[str, Any],
) -> tuple[int, int]:
    """Resolve Sales GIS rows to the Auditor's stable cross-roll parcel shell."""

    parcel_id, created = _franklin_auditor_bulk_parcel(
        db,
        native_parcel_id=native_parcel_id,
        normalized_parcel_id=normalized_parcel_id,
        roll_year="",
        observation_id=observation_id,
        release_date=None,
        record=record,
        event_anchor=True,
    )
    # The cross-roll row is a deterministic authority-level join anchor, not a
    # preferred copy of either the bulk or GIS representation. All source facts
    # remain in their own observations and projection rows.
    anchor_record = {
        "record_kind": "franklin_auditor_cross_roll_parcel_anchor",
        "authority": "Franklin County Auditor",
        "jurisdiction_geoid": "39049",
        "normalized_parcel_id": normalized_parcel_id,
        "representation_source_ids": sorted(
            {
                OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
                OHIO_FRANKLIN_SALES_GIS_SOURCE_ID,
            }
        ),
        "recorded_title_evidence": False,
    }
    db.execute(
        """
        UPDATE parcel_snapshot
        SET effective_from=NULL, source_good_through=NULL,
            observation_id=NULL, raw_json=?
        WHERE parcel_id=?
        """,
        (canonical_json(anchor_record), parcel_id),
    )
    return parcel_id, created


def _upsert_franklin_sales_occurrence_event(
    db,
    *,
    record: Mapping[str, Any],
    occurrence_id: str,
    business_sale_id: str,
    normalized_parcel_id: str,
    parcel_id: int,
    observation_id: int,
) -> tuple[int, int]:
    sale = record.get("sale")
    if not isinstance(sale, Mapping):
        sale = {}
    activity = record.get("activity")
    if not isinstance(activity, Mapping):
        activity = {}
    address = record.get("situs_address_observation")
    address_raw = _address_raw(address) if isinstance(address, Mapping) else None
    longitude, latitude = _franklin_sales_wgs84_point(record)
    description_parts = [
        value
        for value in (
            _text(sale.get("instrument")),
            _text(sale.get("sale_type")),
        )
        if value
    ]
    existing = db.execute(
        """
        SELECT e.event_id, e.observation_id, e.raw_json,
               so.retrieved_at AS observation_retrieved_at
        FROM property_event e
        LEFT JOIN source_observation so
          ON so.observation_id=e.observation_id
        WHERE e.source_id=? AND e.jurisdiction_geoid='39049'
          AND e.native_event_id=? AND e.source_record_id=?
        """,
        (
            OHIO_FRANKLIN_SALES_GIS_SOURCE_ID,
            business_sale_id,
            occurrence_id,
        ),
    ).fetchone()
    if existing is not None:
        try:
            existing_raw = json.loads(existing["raw_json"])
        except (TypeError, json.JSONDecodeError):
            existing_raw = None
        existing_activity = (
            existing_raw.get("activity")
            if isinstance(existing_raw, Mapping)
            and isinstance(existing_raw.get("activity"), Mapping)
            else {}
        )
        existing_version = _franklin_sales_timestamp(
            existing_activity.get("last_update_iso")
        )
        incoming_version = _franklin_sales_timestamp(
            activity.get("last_update_iso")
        )
        existing_is_newer = bool(
            existing_version
            and (
                not incoming_version
                or existing_version > incoming_version
            )
        )
        if existing_version == incoming_version:
            incoming_observation = db.execute(
                "SELECT retrieved_at FROM source_observation WHERE observation_id=?",
                (observation_id,),
            ).fetchone()
            existing_retrieved_at = _text(
                existing["observation_retrieved_at"]
            )
            incoming_retrieved_at = (
                _text(incoming_observation["retrieved_at"])
                if incoming_observation is not None
                else None
            )
            existing_is_newer = bool(
                existing_retrieved_at
                and incoming_retrieved_at
                and (
                    existing_retrieved_at > incoming_retrieved_at
                    or (
                        existing_retrieved_at == incoming_retrieved_at
                        and int(existing["observation_id"] or 0) > observation_id
                    )
                )
            )
        if existing_is_newer:
            party_count = db.execute(
                "SELECT COUNT(*) FROM property_event_party WHERE event_id=?",
                (int(existing["event_id"]),),
            ).fetchone()[0]
            return int(existing["event_id"]), int(party_count)
    db.execute(
        """
        INSERT INTO property_event(
            source_id, jurisdiction_geoid, native_event_id, source_record_id,
            record_kind, event_type, description, status, status_category,
            event_date, last_update_date, address_raw, map_taxlot_candidate,
            longitude, latitude, geometry_crs, observation_id, raw_json
        ) VALUES (
            ?, '39049', ?, ?, ?, 'auditor_sale_feature_observation', ?, ?, NULL,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(
            source_id, jurisdiction_geoid, native_event_id, source_record_id
        ) DO UPDATE SET
            record_kind=excluded.record_kind,
            event_type=excluded.event_type,
            description=excluded.description,
            status=excluded.status,
            status_category=NULL,
            event_date=excluded.event_date,
            last_update_date=excluded.last_update_date,
            address_raw=excluded.address_raw,
            map_taxlot_candidate=excluded.map_taxlot_candidate,
            longitude=excluded.longitude,
            latitude=excluded.latitude,
            geometry_crs=excluded.geometry_crs,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            OHIO_FRANKLIN_SALES_GIS_SOURCE_ID,
            business_sale_id,
            occurrence_id,
            _FRANKLIN_SALES_GIS_FEATURE_KIND,
            " / ".join(description_parts) or None,
            _text(sale.get("valid_sale")),
            _franklin_sales_date(sale.get("date_iso")),
            _franklin_sales_timestamp(activity.get("last_update_iso")),
            address_raw,
            normalized_parcel_id,
            longitude,
            latitude,
            "EPSG:4326" if longitude is not None else None,
            observation_id,
            canonical_json(record),
        ),
    )
    event_row = db.execute(
        """
        SELECT event_id FROM property_event
        WHERE source_id=? AND jurisdiction_geoid='39049'
          AND native_event_id=? AND source_record_id=?
        """,
        (
            OHIO_FRANKLIN_SALES_GIS_SOURCE_ID,
            business_sale_id,
            occurrence_id,
        ),
    ).fetchone()
    event_id = int(event_row["event_id"])
    db.execute(
        "DELETE FROM property_event_parcel_join_key WHERE event_id=?",
        (event_id,),
    )
    db.execute(
        """
        INSERT INTO property_event_parcel_join_key(
            event_id, normalized_parcel_id
        ) VALUES (?, ?)
        """,
        (event_id, normalized_parcel_id),
    )
    db.execute(
        """
        INSERT INTO property_event_parcel_link(
            event_id, parcel_id, map_taxlot_candidate, link_method,
            link_confidence, evidence_json
        ) VALUES (?, ?, ?, 'exact_source_published_parcel_identifier', 1.0, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            parcel_id=excluded.parcel_id,
            map_taxlot_candidate=excluded.map_taxlot_candidate,
            link_method=excluded.link_method,
            link_confidence=excluded.link_confidence,
            evidence_json=excluded.evidence_json
        """,
        (
            event_id,
            parcel_id,
            normalized_parcel_id,
            canonical_json(
                {
                    "parcel_id": _text(record.get("parcel_id")),
                    "normalized_parcel_id": normalized_parcel_id,
                    "source_id": OHIO_FRANKLIN_SALES_GIS_SOURCE_ID,
                }
            ),
        ),
    )

    db.execute("DELETE FROM property_event_party WHERE event_id=?", (event_id,))
    grantors, grantees = _franklin_sales_parties(record)
    parties_upserted = 0
    for role, names in (("grantor", grantors), ("grantee", grantees)):
        for raw_name in names:
            parties_upserted += 1
            db.execute(
                """
                INSERT INTO property_event_party(
                    event_id, sequence_no, role, raw_name, normalized_name,
                    assertion_type
                ) VALUES (?, ?, ?, ?, ?, 'auditor_transaction_party_observation')
                """,
                (
                    event_id,
                    parties_upserted,
                    role,
                    raw_name,
                    " ".join(raw_name.upper().split()),
                ),
            )
    return event_id, parties_upserted


def _ingest_ohio_franklin_sales_gis_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve each Sales GIS feature and project conservative sale facts."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    occurrence_id = _franklin_sales_occurrence_identity(record)
    if record_kind != _FRANKLIN_SALES_GIS_FEATURE_KIND:
        _assert_observation_county_scope(
            record,
            source_id=source_id,
            expected_geoid="39049",
        )
        preserved = dict(record)
        jurisdiction = (
            dict(preserved["jurisdiction"])
            if isinstance(preserved.get("jurisdiction"), Mapping)
            else {}
        )
        jurisdiction.update(
            {
                "state_code": _text(jurisdiction.get("state_code")) or "OH",
                "state_fips": _text(jurisdiction.get("state_fips")) or "39",
                "county_name": (
                    _text(jurisdiction.get("county_name"))
                    or "Franklin County"
                ),
                "county_geoid": (
                    _text(jurisdiction.get("county_geoid")) or "39049"
                ),
            }
        )
        preserved["jurisdiction"] = jurisdiction
        preserved["record_type"] = record_kind or "franklin_sales_gis_source"
        preserved["native_id"] = (
            occurrence_id
            or _text(record.get("canonical_ref"))
            or _record_schema_fingerprint(record)
            or sha256_fingerprint(record)
        )
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=preserved,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="franklin_sales_gis_non_feature_source_observation",
        )

    _assert_observation_county_scope(
        record,
        source_id=source_id,
        expected_geoid="39049",
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_native_id = occurrence_id or sha256_fingerprint(record)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    base_result = {
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": source_native_id,
        "record_kind": record_kind,
        "independent_corroboration": False,
        "same_authority_lineage": "franklin_county_auditor_property_data",
        "recorded_instruments_upserted": 0,
        "created_title_assertions": 0,
    }
    if not occurrence_id:
        return {
            **base_result,
            "projection_skipped": True,
            "reason": "franklin_sales_gis_feature_has_no_occurrence_identity",
            "created_property_records": 0,
        }

    parcel_identity = record.get("parcel_identity")
    identity_parcel = (
        _franklin_sales_usable_identifier(parcel_identity.get("parcel_id"))
        if isinstance(parcel_identity, Mapping)
        else None
    )
    native_parcel_id = _franklin_sales_usable_identifier(record.get("parcel_id"))
    if native_parcel_id and identity_parcel and (
        _franklin_sales_normalized_identifier(native_parcel_id)
        != _franklin_sales_normalized_identifier(identity_parcel)
    ):
        raise PropertyIngestError(
            "Franklin Sales GIS parcel_identity does not match parcel_id"
        )
    native_parcel_id = native_parcel_id or identity_parcel
    normalized_parcel_id = _franklin_sales_normalized_identifier(native_parcel_id)
    if not native_parcel_id or not normalized_parcel_id:
        return {
            **base_result,
            "projection_skipped": True,
            "reason": "franklin_sales_gis_occurrence_has_no_usable_parcel_join",
            "created_property_records": 0,
        }

    sale_identity = record.get("sale_identity")
    if isinstance(sale_identity, Mapping):
        identity_conveyance = _franklin_sales_normalized_identifier(
            sale_identity.get("conveyance_number")
        )
        record_conveyance = _franklin_sales_normalized_identifier(
            record.get("conveyance_number")
        )
        identity_sale_parcel = _franklin_sales_normalized_identifier(
            sale_identity.get("parcel_id")
        )
        if identity_sale_parcel and identity_sale_parcel != normalized_parcel_id:
            raise PropertyIngestError(
                "Franklin Sales GIS sale_identity parcel does not match parcel_id"
            )
        if (
            identity_conveyance
            and record_conveyance
            and identity_conveyance != record_conveyance
        ):
            raise PropertyIngestError(
                "Franklin Sales GIS sale_identity conveyance does not match "
                "conveyance_number"
            )

    _upsert_jurisdiction_values(
        db,
        geoid="39049",
        name="Franklin County",
        state_code="OH",
        jurisdiction_type="county",
        parent_geoid="39",
    )
    parcel_id, parcels_created = _franklin_sales_parcel_anchor(
        db,
        native_parcel_id=native_parcel_id,
        normalized_parcel_id=normalized_parcel_id,
        observation_id=observation_id,
        record=record,
    )
    activity = record.get("activity")
    last_update_timestamp = (
        _franklin_sales_timestamp(activity.get("last_update_iso"))
        if isinstance(activity, Mapping)
        else None
    )
    last_update = (
        _franklin_sales_date(activity.get("last_update_iso"))
        if isinstance(activity, Mapping)
        else None
    )
    sale = record.get("sale")
    sale_date = (
        _franklin_sales_date(sale.get("date_iso"))
        if isinstance(sale, Mapping)
        else None
    )
    effective_from = last_update or sale_date or ""
    aliases_inserted = 0
    for alias_type, alias_value in (
        ("franklin_auditor_sales_gis_parcel_id", native_parcel_id),
        (
            "franklin_auditor_sales_gis_parcel_id_normalized",
            normalized_parcel_id,
        ),
        (
            "franklin_auditor_sales_gis_low_parcel_id",
            record.get("low_parcel_id"),
        ),
    ):
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=effective_from,
        )

    address = record.get("situs_address_observation")
    addresses_inserted = 0
    if isinstance(address, Mapping):
        addresses_inserted = int(
            _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                role="situs",
                address={**dict(address), "state": "OH", "country": "US"},
                effective_from=effective_from,
            )
        )
    longitude, latitude = _franklin_sales_wgs84_point(record)
    geometry_upserted = _upsert_point_geometry(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        longitude=longitude,
        latitude=latitude,
        snapshot_date=last_update_timestamp or sale_date or "",
        source_resolution="county_auditor_sale_location_point",
    )

    business_sale_id, business_identity_basis = (
        _franklin_sales_business_identity(
            record,
            normalized_parcel_id=normalized_parcel_id,
        )
    )
    event_id = None
    parties_upserted = 0
    if business_sale_id:
        event_id, parties_upserted = _upsert_franklin_sales_occurrence_event(
            db,
            record=record,
            occurrence_id=occurrence_id,
            business_sale_id=business_sale_id,
            normalized_parcel_id=normalized_parcel_id,
            parcel_id=parcel_id,
            observation_id=observation_id,
        )

    price = sale.get("price") if isinstance(sale, Mapping) else None
    _raw_price, price_minor = _franklin_sales_positive_price(price)
    sale_projection_eligible = bool(
        business_sale_id and sale_date and price_minor is not None
    )
    sales_upserted = 0
    if sale_projection_eligible and business_sale_id:
        sales_upserted = _upsert_sale_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            native_sale_id=business_sale_id,
            sale_date=sale_date,
            consideration=price,
            derivation="franklin_auditor_sales_gis_transaction",
            observation_id=observation_id,
            raw=record,
            qualification_code=_text(sale.get("valid_sale")),
            match_sale_date=False,
            source_version=last_update_timestamp,
        )

    improvements = record.get("improvements")
    structure_observation_projected = bool(
        isinstance(improvements, Mapping)
        and any(value not in (None, "") for value in improvements.values())
        and event_id is not None
    )
    return {
        **base_result,
        "parcel_id": parcel_id,
        "native_parcel_id": native_parcel_id,
        "normalized_parcel_id": normalized_parcel_id,
        "parcel_anchor_source_id": OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
        "parcels_created": parcels_created,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "geometry_upserted": geometry_upserted,
        "structure_observation_projected": structure_observation_projected,
        "event_id": event_id,
        "parties_upserted": parties_upserted,
        "business_sale_id": business_sale_id,
        "business_identity_basis": business_identity_basis,
        "sale_projection_eligible": sale_projection_eligible,
        "sales_upserted": sales_upserted,
        "source_valid_sale_qualification": (
            _text(sale.get("valid_sale"))
            if isinstance(sale, Mapping)
            else None
        ),
    }


def _ingest_ohio_franklin_auditor_bulk_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve bulk lineage and project only component-specific row facts."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind")) or "source_row"
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    native_id = _text(
        record.get("native_document_id")
        or record.get("native_occurrence")
        or record.get("canonical_ref")
        or record.get("release_id")
        or record.get("family")
    ) or sha256_fingerprint(record)
    artifact_sha256 = _franklin_auditor_bulk_artifact_sha256(
        record, raw_artifact_sha256
    )
    artifact_path = _text(record.get("artifact_path")) or raw_artifact_path
    source_url = _text(
        record.get("artifact_source_url")
        or record.get("artifact_url")
        or record.get("directory_url")
        or record.get("root_url")
        or record.get("official_data_landing")
    ) or _record_source_url(envelope, record)
    schema_fingerprint = _record_schema_fingerprint(record)
    if schema_fingerprint is None and isinstance(record.get("raw_headers"), list):
        schema_fingerprint = sha256_fingerprint(
            {
                "record_family": (
                    record.get("parsed_fields", {}).get("record_family")
                    if isinstance(record.get("parsed_fields"), Mapping)
                    else None
                ),
                "raw_headers": record["raw_headers"],
            }
        )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=source_url,
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=schema_fingerprint,
        raw=record,
        raw_artifact_path=artifact_path,
        raw_artifact_sha256=artifact_sha256,
        warnings=warnings,
    )
    base_result = {
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": native_id,
        "record_kind": record_kind,
        "release_id": _text(record.get("release_id")),
        "artifact_sha256": artifact_sha256,
        "independent_corroboration": False,
        "same_authority_lineage": _text(record.get("same_authority_lineage")),
        "recorded_instruments_upserted": 0,
        "created_title_assertions": 0,
    }
    if record_kind not in _OHIO_FRANKLIN_AUDITOR_BULK_ROW_KINDS:
        return {
            **base_result,
            "projection_skipped": True,
            "reason": "franklin_auditor_bulk_release_or_artifact_observation",
            "created_property_records": 0,
        }

    parsed = record.get("parsed_fields")
    if not isinstance(parsed, Mapping):
        raise PropertyIngestError(
            "Franklin Auditor bulk row lacks parsed_fields"
        )
    occurrence = _text(record.get("native_occurrence"))
    release_id = _text(record.get("release_id"))
    row_artifact_sha256 = _text(record.get("artifact_sha256"))
    if not occurrence or not release_id or not row_artifact_sha256:
        raise PropertyIngestError(
            "Franklin Auditor bulk rows require occurrence, release, and "
            "artifact SHA-256 provenance"
        )
    join_candidates = record.get("join_candidates")
    if isinstance(join_candidates, Mapping):
        county_geoid = _text(join_candidates.get("county_geoid"))
        if county_geoid and county_geoid != "39049":
            raise PropertyIngestError(
                "Franklin Auditor bulk row has an out-of-scope county join"
            )
    native_parcel_id = _text(parsed.get("parcel_id"))
    if not native_parcel_id:
        return {
            **base_result,
            "projection_skipped": True,
            "reason": "franklin_auditor_bulk_row_has_no_parcel_join",
            "created_property_records": 0,
        }
    normalized_parcel_id = (
        _text(
            join_candidates.get("normalized_parcel_id")
            if isinstance(join_candidates, Mapping)
            else None
        )
        or _normalized_foreclosure_parcel(native_parcel_id)
        or native_parcel_id
    )
    record_family = _text(parsed.get("record_family")) or record_kind.removesuffix(
        "_row_observation"
    ).replace("_", "-")
    _upsert_jurisdiction_values(
        db,
        geoid="39049",
        name="Franklin County",
        state_code="OH",
        jurisdiction_type="county",
        parent_geoid="39",
    )
    release_id = _text(record.get("release_id")) or ""
    release_boundary = _franklin_auditor_bulk_release_boundary(record)
    roll_year = _franklin_auditor_bulk_roll_year(record, parsed)
    parcel_roll_year = (
        "" if record_family in {"sales", "daily-conveyance"} else roll_year
    )
    parcel_id, parcels_created = _franklin_auditor_bulk_parcel(
        db,
        native_parcel_id=native_parcel_id,
        normalized_parcel_id=normalized_parcel_id,
        roll_year=parcel_roll_year,
        observation_id=observation_id,
        release_date=release_boundary,
        record=record,
        event_anchor=record_family in {"sales", "daily-conveyance"},
    )
    effective_from = release_boundary or ""
    aliases_inserted = 0
    for alias_type, alias_value in (
        ("franklin_auditor_bulk_parcel_id", native_parcel_id),
        (
            "franklin_auditor_bulk_parcel_id_normalized",
            normalized_parcel_id,
        ),
    ):
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=effective_from,
        )

    owners_upserted = 0
    tax_events_upserted = 0
    sales_upserted = 0
    if record_family == "parcel":
        owners = parsed.get("owner_names")
        if not isinstance(owners, list):
            owners = []
        for owner in dict.fromkeys(_text(value) for value in owners):
            if owner:
                owners_upserted += _upsert_assessor_owner(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    raw_name=owner,
                    effective_from=effective_from,
                    confidence="high",
                    observation_id=observation_id,
                    evidence_ref=(
                        _text(record.get("evidence_ref"))
                        or f"BULK:{source_id}/row/{native_id}"
                    ),
                )
    elif record_family == "payment" and any(
        parsed.get(field) not in (None, "")
        for field in ("event_date", "amount", "tax_year", "bill_type")
    ):
        tax_events_upserted = _upsert_tax_account_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=parsed.get("tax_year") or roll_year,
            event_type="tax_payment_observation",
            event_date=parsed.get("event_date"),
            amount=parsed.get("amount"),
            status=parsed.get("bill_type"),
            native_event_id=occurrence,
            observation_id=observation_id,
            raw=record,
        )
    sale_date = _text(parsed.get("event_date"))
    sale_amount_minor = _minor_units(parsed.get("amount"))
    sale_projection_eligible = bool(
        sale_date
        and sale_amount_minor is not None
        and sale_amount_minor > 0
        and (
            record_family == "sales"
            or (
                record_family == "daily-conveyance"
                and _franklin_auditor_bulk_daily_sale(parsed)
            )
        )
    )
    if sale_projection_eligible:
        normalized_sale_id = _franklin_auditor_bulk_sale_native_id(
            parsed,
            record_family=record_family,
            normalized_parcel_id=normalized_parcel_id,
        )
        sales_upserted = _upsert_sale_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            native_sale_id=normalized_sale_id,
            sale_date=sale_date,
            consideration=parsed.get("amount"),
            derivation=(
                "franklin_auditor_daily_conveyance"
                if record_family == "daily-conveyance"
                else "franklin_auditor_assessor_sale"
            ),
            observation_id=observation_id,
            raw=record,
            qualification_code=_text(
                parsed.get("sale_validity")
                if record_family == "sales"
                else parsed.get("is_exempt")
            ),
            match_sale_date=False,
            source_version=release_boundary,
        )
    else:
        normalized_sale_id = None

    return {
        **base_result,
        "parcel_id": parcel_id,
        "native_parcel_id": native_parcel_id,
        "record_family": record_family,
        "parcel_anchor_role": (
            "cross_release_sale_event"
            if record_family in {"sales", "daily-conveyance"}
            else "release_roll"
        ),
        "parcels_created": parcels_created,
        "aliases_inserted": aliases_inserted,
        "assessment_owners_upserted": owners_upserted,
        "tax_events_upserted": tax_events_upserted,
        "sales_upserted": sales_upserted,
        "sale_projection_eligible": sale_projection_eligible,
        "normalized_sale_id": normalized_sale_id,
        "source_sale_flags": (
            dict(parsed["source_sale_flags"])
            if isinstance(parsed.get("source_sale_flags"), Mapping)
            else None
        ),
    }


def _ingest_ohio_statewide_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project OGRIP parcel context without creating assessor or title claims."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    identifiers = (
        record.get("parcel_identifiers")
        if isinstance(record.get("parcel_identifiers"), Mapping)
        else {}
    )
    state_parcel_id = _text(identifiers.get("state_parcel_id"))
    if (
        record_kind != "standardized_county_parcel_observation"
        or not state_parcel_id
    ):
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="ohio_row_is_not_a_state_identified_parcel_observation",
        )

    local_parcel_id = _text(identifiers.get("local_parcel_id"))
    jurisdiction = (
        record.get("jurisdiction")
        if isinstance(record.get("jurisdiction"), Mapping)
        else {}
    )
    county_geoid = _text(jurisdiction.get("county_geoid"))
    county_local_id = _text(record.get("county_local_parcel_id")) or (
        f"{county_geoid}|{local_parcel_id}"
        if county_geoid and local_parcel_id
        else None
    )
    source_freshness = (
        record.get("source_freshness")
        if isinstance(record.get("source_freshness"), Mapping)
        else {}
    )
    source_last_updated = _text(source_freshness.get("current_to_iso"))
    global_id = _text(record.get("global_id"))
    object_id = _text(record.get("object_id"))

    projected = dict(record)
    projected.update(
        {
            "native_parcel_id": state_parcel_id,
            "alternate_parcel_ids": [],
            "source_occurrence_id": (
                global_id
                or (f"OBJECTID:{object_id}" if object_id is not None else None)
            ),
            "situs_address": {
                "raw": _text(record.get("situs_address_observation")),
                "country": "US",
            },
            "owners": [],
            "snapshot_complete": False,
            "snapshot_completeness": {
                "parcel_row": "county_standardized_statewide_observation",
                "reconciliation": "not_asserted",
            },
            "source_last_updated": source_last_updated,
            "response_schema_fingerprint": _text(
                record.get("source_response_schema_fingerprint")
            ),
            "geometry_disclaimer": (
                "OGRIP geometry is a county-contributed mapping polygon; "
                "local survey, assessor, and recorded-instrument sources "
                "provide separately attributable detail."
            ),
        }
    )
    mailing = record.get("mailing_address_observation")
    if isinstance(mailing, Mapping):
        projected["mailing_address"] = {
            **dict(mailing),
            "country": "US",
        }
    for field in (
        "assessment",
        "assessment_history",
        "last_sale",
        "sale_history",
        "tax_year",
    ):
        projected.pop(field, None)

    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="standardized_county_parcel_observation",
    )
    effective_from = source_last_updated or ""
    typed_aliases = (
        ("local_parcel_id", local_parcel_id),
        (
            "local_parcel_id_normalized",
            _normalized_foreclosure_parcel(local_parcel_id),
        ),
        ("county_local_parcel_id", county_local_id),
    )
    aliases_inserted = 0
    for alias_type, alias_value in typed_aliases:
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=int(result["parcel_id"]),
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=effective_from,
        )
    result["aliases_inserted"] += aliases_inserted
    result["land_observation_preserved"] = isinstance(
        record.get("land"),
        Mapping,
    )
    result["created_ownership_or_title_assertions"] = 0
    return result


def _ingest_wisconsin_statewide_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project parcel rows while retaining Wisconsin visibility semantics."""

    _assert_record_source(record, source_id)
    classification = record.get("source_record_classification")
    is_parcel = (
        _text(record.get("record_type")) == "statewide_annual_parcel_observation"
        and isinstance(classification, Mapping)
        and _text(classification.get("kind")) == "parcel_or_unclassified"
    )
    if not is_parcel:
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="wisconsin_row_is_not_a_canonical_parcel",
        )

    native_id = _text(record.get("native_id") or record.get("state_parcel_id"))
    if not native_id:
        raise PropertyIngestError("Wisconsin parcel record lacks native_id")
    projected = dict(record)
    projected["native_parcel_id"] = native_id
    projected["alternate_parcel_ids"] = [
        value
        for value in dict.fromkeys(
            _text(candidate)
            for candidate in (
                record.get("state_parcel_id"),
                record.get("native_parcel_id"),
                record.get("tax_parcel_id"),
            )
        )
        if value and value != native_id
    ]
    assessment = record.get("assessment_and_tax")
    if isinstance(assessment, Mapping):
        total_value = assessment.get("total_assessed_value")
        projected["tax_year"] = _text(assessment.get("tax_roll_year"))
        projected["assessment"] = {
            "tax_year": _text(assessment.get("tax_roll_year")),
            "land_value": assessment.get("land_value"),
            "improvement_value": assessment.get("improvement_value"),
            "parcel_value": total_value,
            "assessed_value": total_value,
            "market_value": assessment.get("estimated_fair_market_value"),
            "assessment_class": _text(
                (
                    record.get("property_classification")
                    if isinstance(
                        record.get("property_classification"),
                        Mapping,
                    )
                    else {}
                ).get("raw_property_class")
            ),
            "source_tax_values": dict(assessment),
        }
    mailing = record.get("owner_or_tax_bill_mailing_address")
    if isinstance(mailing, Mapping):
        projected["mailing_address"] = dict(mailing)
    source_dates = record.get("source_dates")
    if isinstance(source_dates, Mapping):
        projected["source_revised_date"] = _text(
            source_dates.get("contributor_load_date") or source_dates.get("parcel_date")
        )
    projected["snapshot_complete"] = False
    projected["snapshot_completeness"] = {
        "parcel_row": "current_annual_release_observation",
        "owner_visibility": (
            dict(record.get("owner_visibility"))
            if isinstance(record.get("owner_visibility"), Mapping)
            else None
        ),
        "reconciliation": "not_asserted_across_county_contributions",
    }
    projected["geometry_disclaimer"] = (
        "Statewide geometry is aggregated from county contributors; use the "
        "identified county source and recorded instruments for controlling detail."
    )
    return _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="statewide_annual_parcel_observation",
    )


WYOMING_DOR_ANNUAL_IDENTITY_BASES = frozenset(
    {
        "tax_year_jurisdiction_parcel_account",
        "tax_year_jurisdiction_parcel",
        "tax_year_jurisdiction_account",
    }
)


def _wyoming_dor_occurrence_context(
    db,
    record: Mapping[str, Any],
) -> tuple[int, str, str, str]:
    feature_id = _text(record.get("native_feature_id"))
    if not feature_id or not feature_id.isdigit():
        raise PropertyIngestError("Wyoming DOR occurrence lacks a numeric FID")
    fid = int(feature_id)
    county_geoid = _text(record.get("county_geoid"))
    if (
        not county_geoid
        or len(county_geoid) != 5
        or not county_geoid.isdigit()
        or not county_geoid.startswith("56")
    ):
        raise PropertyIngestError(
            "Wyoming DOR occurrence requires a Wyoming county GEOID"
        )
    county_name = _text(record.get("county_name")) or county_geoid
    if not county_name.casefold().endswith("county"):
        county_name = f"{county_name} County"
    _upsert_jurisdiction_values(
        db,
        geoid=county_geoid,
        name=county_name,
        state_code="WY",
        jurisdiction_type="county",
        parent_geoid="56",
    )
    tax_year = _text(record.get("tax_year"))
    if not tax_year or not re.fullmatch(r"[0-9]{4}", tax_year):
        raise PropertyIngestError("Wyoming DOR occurrence lacks a four-digit tax year")
    return fid, f"FID:{fid}", county_geoid, tax_year


def _insert_wyoming_dor_occurrence(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    occurrence_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> tuple[int, str]:
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    return _insert_observation(
        db,
        source_id=source_id,
        source_native_id=occurrence_id,
        record_kind=(
            _text(record.get("record_kind"))
            or "wy_dor_annual_parcel_feature_occurrence"
        ),
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )


def _wyoming_dor_representative_fid(raw_json: Any) -> int | None:
    try:
        value = json.loads(str(raw_json))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping):
        return None
    feature_id = _text(value.get("native_feature_id"))
    return int(feature_id) if feature_id and feature_id.isdigit() else None


def _upsert_wyoming_dor_geometry_representative(
    db,
    *,
    parcel_id: int,
    record: Mapping[str, Any],
    fid: int,
    tax_year: str,
    force: bool,
) -> int:
    geometry = record.get("geometry")
    if not isinstance(geometry, Mapping):
        return 0
    snapshot_date = f"{tax_year}-01-01"
    existing = db.execute(
        """
        SELECT geometry_ref FROM parcel_geometry
        WHERE parcel_id=? AND source_id=? AND snapshot_date=?
        """,
        (
            parcel_id,
            WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID,
            snapshot_date,
        ),
    ).fetchone()
    existing_fid = None
    if existing is not None:
        match = re.search(r":FID:([0-9]+)#/geometry$", str(existing["geometry_ref"]))
        if match:
            existing_fid = int(match.group(1))
    if not force and existing_fid is not None and existing_fid <= fid:
        return 0
    geometry_ref = (
        f"source-occurrence:{WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID}:"
        f"FID:{fid}#/geometry"
    )
    db.execute(
        """
        INSERT INTO parcel_geometry(
            parcel_id, geometry_ref, geometry_format, crs,
            source_resolution, accuracy_disclaimer, source_id, snapshot_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
            geometry_ref=excluded.geometry_ref,
            geometry_format=excluded.geometry_format,
            crs=excluded.crs,
            source_resolution=excluded.source_resolution,
            accuracy_disclaimer=excluded.accuracy_disclaimer
        """,
        (
            parcel_id,
            geometry_ref,
            _text(record.get("geometry_format")) or "esri_json",
            _text(record.get("geometry_crs")) or "EPSG:4326",
            f"annual_parcel_feature_occurrence:FID:{fid}",
            (
                "Wyoming DOR annual parcel geometry occurrence; every FID "
                "remains in source_observation and the lowest geometry-bearing "
                "FID is the normalized representative."
            ),
            WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID,
            snapshot_date,
        ),
    )
    return 1


def _upsert_wyoming_dor_aliases(
    db,
    *,
    parcel_id: int,
    record: Mapping[str, Any],
    annual_key: str,
    occurrence_id: str,
    tax_year: str,
) -> int:
    aliases = (
        ("wy_dor_annual_join_key", annual_key),
        ("wy_dor_parcel_number", record.get("parcel_number")),
        ("wy_dor_account_number", record.get("account_number")),
        ("wy_dor_fid_occurrence", occurrence_id),
        ("wy_dor_annual_canonical_ref", record.get("annual_parcel_canonical_ref")),
    )
    return sum(
        _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID,
            effective_from=f"{tax_year}-01-01",
        )
        for alias_type, alias_value in aliases
    )


def _ingest_wyoming_dor_statewide_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Retain every FID and project one deterministic annual parcel join."""

    _assert_record_source(record, source_id)
    fid, occurrence_id, county_geoid, tax_year = _wyoming_dor_occurrence_context(
        db, record
    )
    identity = record.get("identity")
    annual_identity = (
        identity.get("annual_parcel_join")
        if isinstance(identity, Mapping)
        and isinstance(identity.get("annual_parcel_join"), Mapping)
        else {}
    )
    identity_basis = _text(annual_identity.get("basis"))
    annual_key = _text(annual_identity.get("key"))
    eligible = (
        annual_identity.get("projection_eligible_as_annual_parcel") is True
        and identity_basis in WYOMING_DOR_ANNUAL_IDENTITY_BASES
        and annual_key is not None
    )
    if not eligible:
        observation_id, record_hash = _insert_wyoming_dor_occurrence(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            occurrence_id=occurrence_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
        )
        return {
            "projection_skipped": True,
            "reason": "wyoming_fid_occurrence_has_no_supported_annual_join",
            "projection": "raw_release_occurrence_only",
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "source_native_id": occurrence_id,
            "native_feature_id": str(fid),
            "identity_basis": identity_basis or "release_occurrence_only",
            "created_property_records": 0,
            "created_ownership_or_title_assertions": 0,
        }

    existing = db.execute(
        """
        SELECT parcel_id, raw_json FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=?
        """,
        (source_id, county_geoid, annual_key, tax_year),
    ).fetchone()
    previous_fid = (
        _wyoming_dor_representative_fid(existing["raw_json"])
        if existing is not None
        else None
    )
    is_annual_representative = previous_fid is None or fid <= previous_fid

    if not is_annual_representative:
        observation_id, record_hash = _insert_wyoming_dor_occurrence(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            occurrence_id=occurrence_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
        )
        parcel_id = int(existing["parcel_id"])
        aliases_inserted = _upsert_wyoming_dor_aliases(
            db,
            parcel_id=parcel_id,
            record=record,
            annual_key=annual_key,
            occurrence_id=occurrence_id,
            tax_year=tax_year,
        )
        geometry_upserted = _upsert_wyoming_dor_geometry_representative(
            db,
            parcel_id=parcel_id,
            record=record,
            fid=fid,
            tax_year=tax_year,
            force=False,
        )
        return {
            "parcel_id": parcel_id,
            "canonical_ref": record.get("annual_parcel_canonical_ref"),
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "native_feature_id": str(fid),
            "annual_representative_fid": previous_fid,
            "annual_projection_replaced": False,
            "aliases_inserted": aliases_inserted,
            "geometry_upserted": geometry_upserted,
            "created_ownership_or_title_assertions": 0,
        }

    if existing is not None and previous_fid is not None and fid < previous_fid:
        parcel_id = int(existing["parcel_id"])
        db.execute(
            "DELETE FROM ownership_assertion WHERE parcel_id=? AND source_id=?",
            (parcel_id, source_id),
        )
        db.execute(
            "DELETE FROM parcel_address WHERE parcel_id=? AND source_id=?",
            (parcel_id, source_id),
        )
        db.execute(
            "DELETE FROM assessment WHERE parcel_id=? AND source_id=?",
            (parcel_id, source_id),
        )

    projected = dict(record)
    projected.update(
        {
            "native_parcel_id": annual_key,
            "source_occurrence_id": occurrence_id,
            "jurisdiction": {
                "county_geoid": county_geoid,
                "county_name": record.get("county_name"),
                "state_fips": "56",
                "state_code": "WY",
            },
            "alternate_parcel_ids": [],
            "source_revised_date": f"{tax_year}-01-01",
            "snapshot_complete": False,
            "snapshot_completeness": {
                "annual_join": identity_basis,
                "representative_rule": "lowest_numeric_FID",
                "all_FID_occurrences_retained": True,
            },
            "geometry_disclaimer": (
                "Wyoming DOR annual parcel geometry occurrence; all FIDs "
                "remain separately attributable source observations."
            ),
        }
    )
    assessment = record.get("assessment")
    if isinstance(assessment, Mapping):
        projected["assessment"] = {
            "tax_year": tax_year,
            "market_value": assessment.get("actual_value"),
            "assessed_value": assessment.get("assessed_value"),
            "source_tax_values": dict(assessment),
        }
    for address_field in ("situs_address", "mailing_address"):
        address = projected.get(address_field)
        if isinstance(address, Mapping):
            projected[address_field] = {**dict(address), "country": "US"}
    for inferred_field in ("last_sale", "sale_history"):
        projected.pop(inferred_field, None)

    projection = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="wy_dor_annual_parcel_geometry_occurrence",
    )
    parcel_id = int(projection["parcel_id"])
    projection["aliases_inserted"] = int(projection["aliases_inserted"]) + (
        _upsert_wyoming_dor_aliases(
            db,
            parcel_id=parcel_id,
            record=record,
            annual_key=annual_key,
            occurrence_id=occurrence_id,
            tax_year=tax_year,
        )
    )
    if isinstance(record.get("geometry"), Mapping):
        projection["geometry_upserted"] = (
            _upsert_wyoming_dor_geometry_representative(
                db,
                parcel_id=parcel_id,
                record=record,
                fid=fid,
                tax_year=tax_year,
                force=True,
            )
        )
    projection.update(
        {
            "canonical_ref": record.get("annual_parcel_canonical_ref"),
            "native_feature_id": str(fid),
            "annual_representative_fid": fid,
            "annual_projection_replaced": (
                previous_fid is not None and fid < previous_fid
            ),
            "identity_basis": identity_basis,
            "created_ownership_or_title_assertions": 0,
        }
    )
    return projection


def _ingest_virginia_vgin_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project VGIN geometry while preserving statewide and local identities."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_type")) != "parcel_geometry":
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="vgin_row_is_not_a_parcel_geometry_observation",
        )

    identity = (
        record.get("identity") if isinstance(record.get("identity"), Mapping) else {}
    )
    vgin_qpid = _text(record.get("vgin_qpid") or identity.get("durable_source_key"))
    if not vgin_qpid:
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="vgin_parcel_lacks_durable_vgin_qpid",
        )

    jurisdiction = (
        record.get("jurisdiction")
        if isinstance(record.get("jurisdiction"), Mapping)
        else {}
    )
    locality_code = _text(jurisdiction.get("source_locality_code"))
    locality_name = _text(jurisdiction.get("locality_name"))
    projected_jurisdiction: dict[str, Any] = {
        "state_code": "VA",
        "state_fips": "51",
        "source_locality_code": locality_code,
        "locality_name": locality_name,
        "geography_type": _text(jurisdiction.get("geography_type")),
    }
    if (
        locality_code
        and locality_code.isdigit()
        and len(locality_code) == 5
        and locality_code.startswith("51")
    ):
        projected_jurisdiction["county_geoid"] = locality_code
        projected_jurisdiction["county_name"] = locality_name

    identifiers = (
        record.get("parcel_identifiers")
        if isinstance(record.get("parcel_identifiers"), Mapping)
        else {}
    )
    parcel_id_value = _text(identifiers.get("parcel_id"))
    ptm_id_value = _text(identifiers.get("parcel_tax_map_id"))
    source_dates = (
        record.get("source_dates")
        if isinstance(record.get("source_dates"), Mapping)
        else {}
    )
    last_update = _text(source_dates.get("last_update"))
    projected = {
        **dict(record),
        "native_parcel_id": vgin_qpid,
        "jurisdiction": projected_jurisdiction,
        "alternate_parcel_ids": [],
        "source_last_updated": last_update,
        "snapshot_complete": False,
        "snapshot_completeness": {
            "role": "statewide_parcel_geometry_and_local_identifier_observation",
            "owner_assessment_tax_fields": "not_published_by_vgin",
            "source_locality_code": locality_code,
            "locality_name": locality_name,
            "locality_last_update": last_update,
        },
        "geometry_disclaimer": (
            "VGIN parcel boundaries are cartographic and spatial-analysis "
            "representations, not legal descriptions or property surveys; "
            "consult the locality and recorded instruments for controlling detail."
        ),
    }
    projection = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="statewide_parcel_geometry_observation",
    )

    _query_fingerprint, retrieved_at, _status, _warnings = _observation_context(
        envelope
    )
    effective_from = last_update or retrieved_at
    object_id = record.get("object_id")
    typed_aliases = (
        ("vgin_objectid_locator", object_id),
        ("vgin_locality_code", locality_code),
        ("vgin_parcelid", parcel_id_value),
        ("vgin_ptm_id", ptm_id_value),
        (
            "vgin_fips_parcelid",
            (
                f"{locality_code}:{parcel_id_value}"
                if locality_code and parcel_id_value
                else None
            ),
        ),
        (
            "vgin_fips_ptm_id",
            (
                f"{locality_code}:{ptm_id_value}"
                if locality_code and ptm_id_value
                else None
            ),
        ),
    )
    aliases_inserted = 0
    for alias_type, alias_value in typed_aliases:
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=int(projection["parcel_id"]),
            alias_type=alias_type,
            alias_value=alias_value,
            source_id=source_id,
            effective_from=effective_from,
        )
    projection["aliases_inserted"] = (
        int(projection.get("aliases_inserted", 0)) + aliases_inserted
    )
    projection["vgin_qpid"] = vgin_qpid
    projection["object_id_locator"] = object_id
    projection["source_locality_code"] = locality_code
    return projection


def _ingest_new_jersey_statewide_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project NJGIN parcel/MOD-IV rows without inventing redacted owners."""

    if _text(record.get("record_type")) != "statewide_parcel_modiv_observation":
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="njgin_row_is_not_a_parcel_modiv_observation",
        )
    _assert_record_source(record, source_id)
    projected = dict(record)
    identifiers = (
        record.get("parcel_identifiers")
        if isinstance(record.get("parcel_identifiers"), Mapping)
        else {}
    )
    native_id = _text(record.get("native_parcel_id"))
    projected["alternate_parcel_ids"] = [
        value
        for value in dict.fromkeys(
            _text(candidate)
            for candidate in (
                identifiers.get("pams_pin"),
                identifiers.get("pin_nodup"),
                identifiers.get("gis_pin"),
                identifiers.get("parcel_guid"),
                identifiers.get("old_property_id"),
            )
        )
        if value and value != native_id
    ]
    projected["parcel_shell_join_ids"] = [
        value
        for value in (
            _text(identifiers.get("pams_pin")),
            _text(identifiers.get("pin_nodup")),
            _text(identifiers.get("gis_pin")),
        )
        if value
    ]
    assessment = record.get("assessment")
    classification = (
        record.get("classification")
        if isinstance(record.get("classification"), Mapping)
        else {}
    )
    if isinstance(assessment, Mapping):
        total_value = assessment.get("net_assessed_value")
        projected["assessment"] = {
            "land_value": assessment.get("land_value"),
            "improvement_value": assessment.get("improvement_value"),
            "parcel_value": total_value,
            "assessed_value": total_value,
            "assessment_class": _text(classification.get("property_class")),
            "source_tax_values": dict(assessment),
        }
    mailing = record.get("mailing_address")
    if isinstance(mailing, Mapping):
        mailing_address = dict(mailing)
        mailing_address["raw"] = ", ".join(
            value
            for value in (
                _text(mailing.get("street")),
                _text(mailing.get("city_state_raw")),
                _text(mailing.get("postal_code") or mailing.get("postal_code_raw")),
            )
            if value
        )
        projected["mailing_address"] = mailing_address
    owner_observation = record.get("owner_observation")
    owner_name = (
        _text(owner_observation.get("raw_name"))
        if isinstance(owner_observation, Mapping)
        else None
    )
    projected["owners"] = (
        [{"raw_name": owner_name, "confidence": "high"}] if owner_name else []
    )
    sale = record.get("last_sale_and_deed_reference")
    if isinstance(sale, Mapping):
        deed_book = _text(sale.get("deed_book"))
        deed_page = _text(sale.get("deed_page"))
        document_ref = (
            "/".join(value for value in (deed_book, deed_page) if value) or None
        )
        projected["last_sale"] = {
            "sale_date": _text(sale.get("deed_date")),
            "consideration": sale.get("sale_price"),
            "qualification_code": _text(sale.get("sale_code")),
            "source_document_ref": document_ref,
            "source_role": "assessment_roll_last_sale_observation",
        }
    source_dates = record.get("source_dates")
    if isinstance(source_dates, Mapping):
        projected["source_revised_date"] = _text(
            source_dates.get("parcel_last_update")
            or source_dates.get("parcel_publication_date")
        )
    projected["snapshot_complete"] = False
    projected["snapshot_completeness"] = {
        "parcel_modiv_join": (
            dict(record.get("modiv_join"))
            if isinstance(record.get("modiv_join"), Mapping)
            else None
        ),
        "owner_visibility": (
            dict(owner_observation) if isinstance(owner_observation, Mapping) else None
        ),
        "reconciliation": "not_asserted_for_redacted_or_unmatched_rows",
    }
    projected["geometry_disclaimer"] = (
        "NJGIN geometry is an approximate parcel representation; consult local "
        "assessment records and recorded instruments for controlling detail."
    )
    return _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="statewide_parcel_modiv_observation",
    )


def _ingest_new_york_statewide_parcel_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project NY's joined centroid, public-polygon, and state-owned rows."""

    _assert_record_source(record, source_id)
    record_type = _text(record.get("record_type"))
    parcel_record_types = {
        "statewide_annual_parcel_assessment_centroid",
        "statewide_annual_public_parcel_polygon",
        "state_owned_parcel_polygon",
    }
    if record_type not in parcel_record_types:
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="new_york_row_is_not_a_parcel_component_observation",
        )

    native_id = _text(record.get("native_id"))
    if not native_id:
        raise PropertyIngestError("New York parcel record lacks native_id")
    projected = dict(record)
    projected["native_parcel_id"] = native_id

    identifiers = (
        record.get("parcel_identifiers")
        if isinstance(record.get("parcel_identifiers"), Mapping)
        else {}
    )
    projected["alternate_parcel_ids"] = [
        value
        for value in dict.fromkeys(
            _text(identifiers.get(field_name))
            for field_name in (
                "swis_sbl_id",
                "swis_print_key_id",
                "municipal_parcel_id",
                "swis",
                "sbl",
                "print_key",
            )
        )
        if value and value != native_id
    ]
    projected["parcel_shell_join_ids"] = [
        value
        for value in (_text(identifiers.get("swis_print_key_id")),)
        if value
    ]

    assessment = record.get("assessment")
    if isinstance(assessment, Mapping):
        roll_year = _text(assessment.get("roll_year"))
        total_value = assessment.get("total_assessed_value")
        projected["tax_year"] = roll_year
        projected["assessment"] = {
            "tax_year": roll_year,
            "land_value": assessment.get("land_assessed_value"),
            "parcel_value": total_value,
            "assessed_value": total_value,
            "market_value": assessment.get("full_market_value"),
            "assessment_class": _text(assessment.get("property_class")),
            "source_tax_values": dict(assessment),
        }

    mailing_addresses = record.get("mailing_addresses")
    if isinstance(mailing_addresses, Mapping):
        primary = mailing_addresses.get("primary_owner")
        if isinstance(primary, Mapping):
            mailing = dict(primary)
            parts: list[str] = []
            for value in (
                primary.get("street"),
                primary.get("po_box"),
                primary.get("city"),
                primary.get("state"),
                primary.get("postal_code"),
            ):
                text = _text(value)
                if text and text not in parts:
                    parts.append(text)
            mailing["raw"] = ", ".join(parts)
            projected["mailing_address"] = mailing

    deed_reference = record.get("deed_reference")
    if isinstance(deed_reference, Mapping):
        book = _text(deed_reference.get("book"))
        page = _text(deed_reference.get("page"))
        document_ref = "/".join(value for value in (book, page) if value)
        if document_ref:
            projected["last_sale"] = {
                "source_document_ref": document_ref,
                "source_role": "annual_parcel_recent_sale_reference",
            }

    component = _text(record.get("component"))
    projected["snapshot_complete"] = component == "centroids"
    projected["snapshot_completeness"] = {
        "component": component,
        "component_role": _text(record.get("component_role")),
        "component_coverage": _text(record.get("component_coverage")),
        "join_keys": (
            list(record.get("cross_component_join_keys", []))
            if isinstance(record.get("cross_component_join_keys"), list)
            else []
        ),
        "assessment_snapshot_owner": component == "centroids",
    }
    if component == "centroids":
        projected.pop("geometry", None)
        projected.pop("geometry_format", None)
        projected.pop("geometry_crs", None)
        projected.pop("geometry_role", None)
    else:
        projected["geometry_disclaimer"] = (
            "County-contributed statewide parcel geometry is a mapping "
            "representation; consult the county source and recorded "
            "instruments for controlling boundary detail."
        )

    return _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind=record_type,
    )


def _existing_new_york_parcel(
    db,
    *,
    jurisdiction_geoid: str,
    native_parcel_id: str,
) -> int | None:
    row = db.execute(
        """
        SELECT p.parcel_id
        FROM parcel_snapshot p
        WHERE p.source_id IN (?, ?) AND p.jurisdiction_geoid=?
          AND (
            p.native_parcel_id=?
            OR EXISTS(
                SELECT 1
                FROM parcel_alias pa
                WHERE pa.parcel_id=p.parcel_id
                  AND pa.alias_value=?
            )
          )
        ORDER BY CASE WHEN p.source_id=? THEN 0 ELSE 1 END,
                 CASE WHEN p.roll_year='' THEN 1 ELSE 0 END,
                 p.roll_year DESC, p.parcel_id DESC
        LIMIT 1
        """,
        (
            NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID,
            NEW_YORK_SALESWEB_SOURCE_ID,
            jurisdiction_geoid,
            native_parcel_id,
            native_parcel_id,
            NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID,
        ),
    ).fetchone()
    return int(row["parcel_id"]) if row else None


def _new_york_salesweb_date(value: Any) -> str | None:
    if isinstance(value, Mapping):
        return _date_prefix(value.get("iso") or value.get("raw"))
    return _date_prefix(value)


def _ingest_new_york_salesweb_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one SalesWeb transfer without asserting present ownership."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_type")) != "property_sale":
        return {
            "projection_skipped": True,
            "reason": "salesweb_record_is_not_a_property_sale",
            "record_kind": _text(record.get("record_type")),
        }
    sale_record_id = _text(
        record.get("sale_record_id") or record.get("native_record_id")
    )
    if not sale_record_id:
        raise PropertyIngestError("New York SalesWeb record lacks sale_record_id")

    jurisdiction_geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="36",
        fallback_name="New York",
        fallback_state_code="NY",
    )
    if not jurisdiction_geoid.startswith("36"):
        raise PropertyIngestError(
            "New York SalesWeb record has out-of-scope jurisdiction "
            f"{jurisdiction_geoid}"
        )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_record = (
        dict(record["source_record"])
        if isinstance(record.get("source_record"), Mapping)
        else {}
    )
    source_url = _text(source_record.get("endpoint")) or _record_source_url(
        envelope,
        record,
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=sale_record_id,
        record_kind="property_sale",
        query_fingerprint=query_fingerprint,
        source_url=source_url,
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    transaction = _mapping(record.get("transaction"), "record.transaction")
    deed = _mapping(transaction.get("deed"), "record.transaction.deed")
    sale_date = _new_york_salesweb_date(transaction.get("sale_date"))
    execution_date = _new_york_salesweb_date(deed.get("deed_date"))
    consideration = transaction.get("sale_price_dollars")
    book = _text(deed.get("book"))
    page = _text(deed.get("page"))
    document_number = _text(deed.get("document_number"))
    source_processing = (
        dict(record["source_processing"])
        if isinstance(record.get("source_processing"), Mapping)
        else {}
    )
    source_good_through = _new_york_salesweb_date(
        source_processing.get("load_date") or source_processing.get("last_form_date")
    )

    db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id,
            instrument_type, book, page, execution_date, recording_date,
            consideration_minor, currency, legal_description_raw, source_url,
            observation_id, raw_json
        ) VALUES (?, ?, ?, 'rp5217_transfer_index_reference', ?, ?, ?, NULL,
                  ?, 'USD', NULL, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
        DO UPDATE SET
            instrument_type=excluded.instrument_type,
            book=excluded.book,
            page=excluded.page,
            execution_date=excluded.execution_date,
            consideration_minor=excluded.consideration_minor,
            source_url=excluded.source_url,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            source_id,
            jurisdiction_geoid,
            sale_record_id,
            book,
            page,
            execution_date,
            _minor_units(consideration),
            source_url,
            observation_id,
            canonical_json(record),
        ),
    )
    instrument_row = db.execute(
        """
        SELECT instrument_id
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (source_id, jurisdiction_geoid, sale_record_id),
    ).fetchone()
    instrument_id = int(instrument_row["instrument_id"])

    parties_value = _mapping(record.get("parties"), "record.parties")
    parties_upserted = 0
    for sequence_no, (source_role, role) in enumerate(
        (("seller", "grantor"), ("buyer", "grantee")),
        start=1,
    ):
        party = _mapping(
            parties_value.get(source_role),
            f"record.parties.{source_role}",
        )
        raw_name = _text(party.get("name"))
        if not raw_name:
            continue
        mailing = party.get("mailing_address")
        raw_address = None
        if isinstance(mailing, Mapping):
            raw_address = ", ".join(
                value
                for value in (
                    _text(mailing.get("street_number")),
                    _text(mailing.get("street")),
                    _text(mailing.get("city")),
                    _text(mailing.get("state")),
                    _text(mailing.get("postal_code")),
                )
                if value
            )
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET
                normalized_name=excluded.normalized_name,
                raw_address=excluded.raw_address
            """,
            (
                instrument_id,
                sequence_no,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
                raw_address,
            ),
        )
        parties_upserted += 1

    property_value = _mapping(record.get("property"), "record.property")
    identifiers = _mapping(
        property_value.get("parcel_identifiers"),
        "record.property.parcel_identifiers",
    )
    native_parcel_id = _text(identifiers.get("swis_print_key_id"))
    parcel_id = None
    placeholder_created = 0
    aliases_inserted = 0
    addresses_inserted = 0
    assessments_upserted = 0
    sales_upserted = 0
    if native_parcel_id:
        parcel_id = _existing_new_york_parcel(
            db,
            jurisdiction_geoid=jurisdiction_geoid,
            native_parcel_id=native_parcel_id,
        )
        if parcel_id is None:
            parcel_id = _upsert_parcel_snapshot(
                db,
                source_id=source_id,
                jurisdiction_geoid=jurisdiction_geoid,
                native_parcel_id=native_parcel_id,
                roll_year="",
                effective_from=sale_date or execution_date,
                source_good_through=source_good_through,
                observation_id=observation_id,
                record={
                    "source_id": source_id,
                    "native_parcel_id": native_parcel_id,
                    "parcel_identifiers": dict(identifiers),
                    "placeholder_state": (
                        "salesweb_join_pending_statewide_parcel_or_local_assessor"
                    ),
                    "source_sale_record_id": sale_record_id,
                },
            )
            placeholder_created = 1
        effective_from = sale_date or execution_date or retrieved_at
        for alias_type, value in (
            ("ny_swis_print_key_id", native_parcel_id),
            ("ny_salesweb_parcel_id", identifiers.get("salesweb_parcel_id")),
            ("ny_swis", identifiers.get("swis")),
            ("ny_print_key", identifiers.get("print_key")),
        ):
            alias = _text(value)
            if alias:
                aliases_inserted += _upsert_alias(
                    db,
                    parcel_id=parcel_id,
                    alias_type=alias_type,
                    alias_value=alias,
                    source_id=source_id,
                    effective_from=effective_from,
                )
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, 'exact_swis_print_key_id', 1.0, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=excluded.legal_description_raw
            """,
            (instrument_id, parcel_id, canonical_json(dict(identifiers))),
        )

        address = property_value.get("address")
        if isinstance(address, Mapping):
            street_line = " ".join(
                value
                for value in (
                    _text(address.get("street_number")),
                    _text(address.get("street")),
                )
                if value
            )
            raw_address = ", ".join(
                value
                for value in (
                    street_line or None,
                    _text(address.get("postal_code")),
                )
                if value
            )
            if raw_address:
                addresses_inserted += int(
                    _upsert_address(
                        db,
                        parcel_id=parcel_id,
                        source_id=source_id,
                        role="situs",
                        address={
                            **dict(address),
                            "raw": raw_address,
                        },
                        effective_from=effective_from,
                    )
                )

        roll_year = _text(property_value.get("roll_year"))
        assessed_values = (
            dict(property_value["assessed_value_dollars"])
            if isinstance(
                property_value.get("assessed_value_dollars"),
                Mapping,
            )
            else {}
        )
        property_class = (
            dict(property_value["property_class"])
            if isinstance(property_value.get("property_class"), Mapping)
            else {}
        )
        class_on_roll = (
            dict(property_class["on_last_roll"])
            if isinstance(property_class.get("on_last_roll"), Mapping)
            else {}
        )
        if roll_year and assessed_values.get("total") is not None:
            assessments_upserted += _upsert_assessment_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                tax_year=roll_year,
                total_value=assessed_values.get("total"),
                assessed_value=assessed_values.get("total"),
                assessment_class=_text(class_on_roll.get("code")),
                source_good_through=source_good_through,
                observation_id=observation_id,
                raw={
                    "assessment_at_transfer": assessed_values,
                    "property_class": property_class,
                    "roll_year": roll_year,
                },
            )
        sales_upserted += _upsert_sale_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            native_sale_id=sale_record_id,
            sale_date=sale_date,
            consideration=consideration,
            derivation="state_taxation_transfer_report_index",
            instrument_id=instrument_id,
            observation_id=observation_id,
            raw={
                "transaction": transaction,
                "property": property_value,
                "source_processing": source_processing,
            },
            execution_date=execution_date,
            qualification_code=_text(transaction.get("report_type_code")),
        )

    return {
        "instrument_id": instrument_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            jurisdiction_geoid,
            "property_sale",
            sale_record_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "sale_record_id": sale_record_id,
        "source_document_number": document_number,
        "parties_upserted": parties_upserted,
        "parcels_linked": int(parcel_id is not None),
        "parcel_id": parcel_id,
        "parcel_placeholder_created": placeholder_created,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "sales_upserted": sales_upserted,
        "ownership_assertions_upserted": 0,
    }


def _ingest_new_jersey_dca_property_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project a DCA building registration as a regulatory property record."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_type")) != "property_registration_building":
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="dca_row_is_not_a_property_registration_building",
        )

    building_registration = _text(record.get("building_registration_number"))
    property_registration = _text(record.get("property_registration_number"))
    if not (
        building_registration
        and building_registration.isdigit()
        and len(building_registration) == 13
    ):
        raise PropertyIngestError(
            "New Jersey DCA record requires a 13-digit building registration"
        )
    if not (
        property_registration
        and property_registration.isdigit()
        and len(property_registration) == 10
        and building_registration.startswith(property_registration)
    ):
        raise PropertyIngestError(
            "New Jersey DCA property registration must be the building "
            "registration's 10-digit prefix"
        )

    building_address = (
        dict(record["building_address"])
        if isinstance(record.get("building_address"), Mapping)
        else {}
    )
    coordinates = (
        dict(record["parcel_coordinates"])
        if isinstance(record.get("parcel_coordinates"), Mapping)
        else {}
    )
    address_raw = ", ".join(
        value
        for value in (
            _text(building_address.get("line1")),
            _text(coordinates.get("municipality")),
            "NJ",
            _text(building_address.get("postal_code")),
        )
        if value
    )
    block = _text(coordinates.get("block"))
    lot = _text(coordinates.get("lot"))
    municipality = _text(coordinates.get("municipality"))
    parcel_candidate = (
        _normalized_map_taxlot(
            "|".join(value for value in (municipality, block, lot) if value)
        )
        if block or lot
        else None
    )

    owner = (
        dict(record["registered_owner"])
        if isinstance(record.get("registered_owner"), Mapping)
        else {}
    )
    owner_name = _text(owner.get("name"))
    building_status = (
        dict(record["building_registration_status"])
        if isinstance(record.get("building_registration_status"), Mapping)
        else {}
    )
    property_status = (
        dict(record["property_registration_status"])
        if isinstance(record.get("property_registration_status"), Mapping)
        else {}
    )
    detail_url = _text(record.get("detail_url"))
    projection_record = {
        "canonical_ref": _text(record.get("canonical_ref")),
        "source_id": source_id,
        "record_kind": "property_registration_building",
        "native_event_id": property_registration,
        "source_record_id": building_registration,
        "event_type": "bhi_property_registration",
        "description": _text(
            record.get("building_name") or record.get("property_name")
        ),
        "status": _text(building_status.get("name")),
        "status_category": "regulatory_registration_status",
        "jurisdiction": {
            "state_fips": "34",
            "state_code": "NJ",
        },
        "address": {
            "raw": address_raw or None,
            "line1": _text(building_address.get("line1")),
            "city": municipality,
            "state": "NJ",
            "postal_code": _text(building_address.get("postal_code")),
            "aka": list(building_address.get("aka", [])),
        },
        "people": (
            [
                {
                    "raw_name": owner_name,
                    "role": "registered_owner",
                    "assertion_type": (
                        "dca_regulatory_registration_relationship_not_title"
                    ),
                }
            ]
            if owner_name
            else []
        ),
        "parcel_join_evidence": {
            "state": "candidate_only",
            "reason": (
                "DCA publishes municipality name/locator plus partial "
                "block/lot, not the NJ MOD-IV municipality code required for "
                "a deterministic statewide parcel join."
            ),
            "published_location": {
                "normalized_candidate": parcel_candidate,
                "county": _text(coordinates.get("county")),
                "county_fips": _text(coordinates.get("county_fips")),
                "municipality": municipality,
                "municipality_id": _text(coordinates.get("municipality_id")),
                "block": block,
                "lot": lot,
            },
        },
        "detail_representations": (
            [
                {
                    "kind": "dca_property_interest_detail",
                    "url": detail_url,
                    "relationship": "property_interest_locator",
                    "source_state": "anonymous_html",
                }
            ]
            if detail_url
            else []
        ),
        "registration": {
            "building_registration_number": building_registration,
            "property_registration_number": property_registration,
            "building_id": _text(record.get("building_id")),
            "property_interest_id": _text(record.get("property_interest_id")),
            "building_status": building_status,
            "property_status": property_status,
            "registered_owner_publication_state": _text(
                record.get("registered_owner_publication_state")
            ),
        },
        "source_record": dict(record),
    }
    projection = _ingest_property_event_record(
        db,
        envelope=envelope,
        record=projection_record,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        expected_geoid="34",
        parcel_alias_source_id=None,
    )
    projection["canonical_ref"] = _text(record.get("canonical_ref")) or (
        canonical_property_ref(
            source_id,
            "34",
            "building-registration",
            building_registration,
        )
    )
    projection["building_registration_number"] = building_registration
    projection["property_registration_number"] = property_registration
    projection["ownership_assertions_upserted"] = 0
    return projection


def _new_jersey_parcel_component(value: Any) -> str | None:
    """Normalize an SR1A block/lot component to the NJGIN PIN convention."""

    text = _text(value)
    if not text:
        return None
    compact = "".join(text.upper().split())
    numeric = compact.replace(".", "", 1)
    if numeric.isdigit():
        integer, dot, fraction = compact.partition(".")
        integer = integer.lstrip("0") or "0"
        fraction = fraction.rstrip("0")
        return integer + (f".{fraction}" if dot and fraction else "")
    return compact


def _new_jersey_sr1a_parcels(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return complete, deduplicated municipality/block/lot coordinates."""

    jurisdiction = _mapping(record.get("jurisdiction"), "record.jurisdiction")
    municipality = _text(jurisdiction.get("municipality_code"))
    property_value = _mapping(record.get("property"), "record.property")
    rows: list[dict[str, Any]] = []

    main = _mapping(property_value.get("parcel"), "record.property.parcel")
    main_block = _new_jersey_parcel_component(
        f"{_text(main.get('block')) or ''}{_text(main.get('block_suffix')) or ''}"
    )
    main_lot = _new_jersey_parcel_component(
        f"{_text(main.get('lot')) or ''}{_text(main.get('lot_suffix')) or ''}"
    )
    if municipality and main_block and main_lot:
        rows.append(
            {
                "parcel_role": "main",
                "municipality_code": municipality,
                "block": main_block,
                "lot": main_lot,
                "qualifier": None,
                "source_values": main,
                "assessed_value_dollars": _mapping(
                    property_value.get("main_assessed_value_dollars"),
                    "record.property.main_assessed_value_dollars",
                ),
            }
        )

    additional = property_value.get("additional_parcels", [])
    if not isinstance(additional, list):
        raise PropertyIngestError("record.property.additional_parcels must be a list")
    for index, value in enumerate(additional):
        parcel = _mapping(
            value,
            f"record.property.additional_parcels[{index}]",
        )
        block = _new_jersey_parcel_component(parcel.get("block"))
        lot = _new_jersey_parcel_component(parcel.get("lot"))
        if not (municipality and block and lot):
            continue
        rows.append(
            {
                "parcel_role": "additional",
                "slot": parcel.get("slot"),
                "municipality_code": municipality,
                "block": block,
                "lot": lot,
                "qualifier": _new_jersey_parcel_component(parcel.get("qualifier")),
                "source_values": parcel,
                "assessed_value_dollars": (
                    _mapping(
                        parcel.get("assessed_value_dollars"),
                        (
                            "record.property.additional_parcels"
                            f"[{index}].assessed_value_dollars"
                        ),
                    )
                    if isinstance(parcel.get("assessed_value_dollars"), Mapping)
                    else {}
                ),
            }
        )

    deduplicated: dict[str, dict[str, Any]] = {}
    for parcel in rows:
        parts = [
            parcel["municipality_code"],
            parcel["block"],
            parcel["lot"],
        ]
        if parcel.get("qualifier"):
            parts.append(parcel["qualifier"])
        native_parcel_id = "_".join(parts)
        parcel["native_parcel_id"] = native_parcel_id
        deduplicated.setdefault(native_parcel_id, parcel)
    return list(deduplicated.values())


def _new_jersey_sr1a_party_address(party: Mapping[str, Any]) -> str | None:
    address = party.get("mailing_address")
    if not isinstance(address, Mapping):
        return None
    return (
        ", ".join(
            value
            for value in (
                _text(address.get("street")),
                _text(address.get("city_state")),
                _text(address.get("postal_code")),
            )
            if value
        )
        or None
    )


def _existing_new_jersey_parcel(
    db,
    *,
    jurisdiction_geoid: str,
    native_parcel_id: str,
) -> int | None:
    row = db.execute(
        """
        SELECT p.parcel_id
        FROM parcel_snapshot p
        WHERE p.source_id IN (?, ?) AND p.jurisdiction_geoid=?
          AND (
            p.native_parcel_id=?
            OR EXISTS(
                SELECT 1
                FROM parcel_alias pa
                WHERE pa.parcel_id=p.parcel_id
                  AND pa.alias_value=?
            )
          )
        ORDER BY CASE WHEN p.source_id=? THEN 0 ELSE 1 END,
                 CASE WHEN p.roll_year='' THEN 1 ELSE 0 END,
                 p.roll_year DESC, p.parcel_id DESC
        LIMIT 1
        """,
        (
            NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID,
            NEW_JERSEY_SR1A_SOURCE_ID,
            jurisdiction_geoid,
            native_parcel_id,
            native_parcel_id,
            NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID,
        ),
    ).fetchone()
    return int(row["parcel_id"]) if row else None


def _ingest_new_jersey_sr1a_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project one SR1A sale without treating its parties as title assertions."""

    _assert_record_source(record, source_id)
    if _text(record.get("record_type")) != "property_sale":
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="sr1a_row_is_not_a_property_sale",
        )
    sale_record_id = _text(
        record.get("sale_record_id") or record.get("native_record_id")
    )
    source_occurrence_id = _text(
        record.get("source_occurrence_id") or record.get("native_record_id")
    )
    if not sale_record_id:
        raise PropertyIngestError("New Jersey SR1A record lacks sale_record_id")

    jurisdiction_geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="34",
        fallback_name="New Jersey",
        fallback_state_code="NJ",
    )
    if not jurisdiction_geoid.startswith("34"):
        raise PropertyIngestError(
            f"New Jersey SR1A record has out-of-scope jurisdiction {jurisdiction_geoid}"
        )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_record = (
        dict(record["source_record"])
        if isinstance(record.get("source_record"), Mapping)
        else {}
    )
    source_url = _text(source_record.get("archive_url")) or _record_source_url(
        envelope,
        record,
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_occurrence_id,
        record_kind="property_sale_release_occurrence",
        query_fingerprint=query_fingerprint,
        source_url=source_url,
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256
        or _text(source_record.get("archive_sha256")),
        warnings=warnings,
    )

    transaction = _mapping(record.get("transaction"), "record.transaction")
    deed = _mapping(record.get("deed"), "record.deed")
    property_value = _mapping(record.get("property"), "record.property")
    deed_date_value = deed.get("deed_date")
    recorded_date_value = deed.get("recorded_date")
    execution_date = _date_prefix(
        deed_date_value.get("iso")
        if isinstance(deed_date_value, Mapping)
        else deed_date_value
    )
    recording_date = _date_prefix(
        recorded_date_value.get("iso")
        if isinstance(recorded_date_value, Mapping)
        else recorded_date_value
    )
    consideration = transaction.get("verified_sale_price_dollars")
    if consideration is None:
        consideration = transaction.get("reported_sale_price_dollars")
    qualification_code = _text(transaction.get("qualification_codes"))
    legal_coordinates = _new_jersey_sr1a_parcels(record)
    db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id,
            instrument_type, book, page, execution_date, recording_date,
            consideration_minor, currency, legal_description_raw, source_url,
            observation_id, raw_json
        ) VALUES (?, ?, ?, 'sr1a_deed_index_reference', ?, ?, ?, ?, ?, 'USD',
                  ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
        DO UPDATE SET
            instrument_type=excluded.instrument_type,
            book=excluded.book,
            page=excluded.page,
            execution_date=excluded.execution_date,
            recording_date=excluded.recording_date,
            consideration_minor=excluded.consideration_minor,
            legal_description_raw=excluded.legal_description_raw,
            source_url=excluded.source_url,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            source_id,
            jurisdiction_geoid,
            sale_record_id,
            _text(deed.get("book")),
            _text(deed.get("page")),
            execution_date,
            recording_date,
            _minor_units(consideration),
            canonical_json(legal_coordinates),
            source_url,
            observation_id,
            canonical_json(record),
        ),
    )
    instrument_row = db.execute(
        """
        SELECT instrument_id
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (source_id, jurisdiction_geoid, sale_record_id),
    ).fetchone()
    instrument_id = int(instrument_row["instrument_id"])

    parties_value = _mapping(record.get("parties"), "record.parties")
    parties_upserted = 0
    for sequence_no, role in enumerate(("grantor", "grantee"), start=1):
        party = _mapping(
            parties_value.get(role),
            f"record.parties.{role}",
        )
        raw_name = _text(party.get("name"))
        if not raw_name:
            continue
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET
                normalized_name=excluded.normalized_name,
                raw_address=excluded.raw_address
            """,
            (
                instrument_id,
                sequence_no,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
                _new_jersey_sr1a_party_address(party),
            ),
        )
        parties_upserted += 1

    source_processing = (
        dict(record["source_processing"])
        if isinstance(record.get("source_processing"), Mapping)
        else {}
    )
    last_update_value = source_processing.get("last_update_date")
    field_date_value = source_processing.get("field_date")
    source_good_through = _date_prefix(
        (
            last_update_value.get("iso")
            if isinstance(last_update_value, Mapping)
            else last_update_value
        )
        or (
            field_date_value.get("iso")
            if isinstance(field_date_value, Mapping)
            else field_date_value
        )
    )
    assessment_year = _text(property_value.get("assessment_year"))
    effective_from = recording_date or execution_date or retrieved_at
    parcel_ids: set[int] = set()
    placeholders_created = 0
    aliases_inserted = 0
    addresses_inserted = 0
    assessments_upserted = 0
    sales_upserted = 0
    for parcel in legal_coordinates:
        native_parcel_id = str(parcel["native_parcel_id"])
        parcel_id = _existing_new_jersey_parcel(
            db,
            jurisdiction_geoid=jurisdiction_geoid,
            native_parcel_id=native_parcel_id,
        )
        if parcel_id is None:
            parcel_id = _upsert_parcel_snapshot(
                db,
                source_id=source_id,
                jurisdiction_geoid=jurisdiction_geoid,
                native_parcel_id=native_parcel_id,
                roll_year="",
                effective_from=execution_date or recording_date,
                source_good_through=source_good_through,
                observation_id=observation_id,
                record={
                    **parcel,
                    "source_id": source_id,
                    "placeholder_state": (
                        "sr1a_coordinate_pending_njgin_or_local_assessor"
                    ),
                    "source_sale_record_id": sale_record_id,
                },
            )
            placeholders_created += 1
        parcel_ids.add(parcel_id)
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="nj_municipality_block_lot",
            alias_value=native_parcel_id,
            source_id=source_id,
            effective_from=effective_from,
        )
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, 'exact_municipality_block_lot', 1.0, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=excluded.legal_description_raw
            """,
            (instrument_id, parcel_id, canonical_json(parcel)),
        )
        property_location = _text(property_value.get("location"))
        if property_location:
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role="situs",
                    address={"raw": property_location, "state": "NJ"},
                    effective_from=effective_from,
                )
            )
        assessed = (
            dict(parcel["assessed_value_dollars"])
            if isinstance(parcel.get("assessed_value_dollars"), Mapping)
            else {}
        )
        if assessment_year and assessed:
            assessments_upserted += _upsert_assessment_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                tax_year=assessment_year,
                land_value=assessed.get("land"),
                improvement_value=assessed.get("building"),
                total_value=assessed.get("total"),
                assessed_value=assessed.get("total"),
                assessment_class=(
                    property_value.get("property_class")
                    if parcel.get("parcel_role") == "main"
                    else None
                ),
                source_good_through=source_good_through,
                observation_id=observation_id,
                raw={
                    "parcel_role": parcel.get("parcel_role"),
                    "assessment_at_sale": assessed,
                    "assessment_year": assessment_year,
                },
            )
        sales_upserted += _upsert_sale_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            native_sale_id=sale_record_id,
            sale_date=execution_date or recording_date,
            consideration=consideration,
            derivation="state_taxation_sale_return_index",
            instrument_id=instrument_id,
            observation_id=observation_id,
            raw={
                "transaction": transaction,
                "deed": deed,
                "parcel": parcel,
                "release": record.get("release"),
                "source_occurrence_id": source_occurrence_id,
            },
            execution_date=execution_date,
            recording_date=recording_date,
            qualification_code=qualification_code,
        )

    return {
        "instrument_id": instrument_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            jurisdiction_geoid,
            "property_sale",
            sale_record_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "sale_record_id": sale_record_id,
        "source_occurrence_id": source_occurrence_id,
        "parties_upserted": parties_upserted,
        "parcels_linked": len(parcel_ids),
        "parcel_placeholders_created": placeholders_created,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "sales_upserted": sales_upserted,
        "ownership_assertions_upserted": 0,
    }


def _palm_beach_jurisdiction(db) -> str:
    return _upsert_jurisdiction_values(
        db,
        geoid="12099",
        name="Palm Beach County, Florida",
        state_code="FL",
        jurisdiction_type="county",
        parent_geoid="12",
    )


def _palm_beach_instrument_id(
    db,
    *,
    instrument_number: str,
    observation_id: int,
    record: Mapping[str, Any],
) -> int:
    """Return the official-instrument row without substituting a portal ID."""

    jurisdiction_geoid = _palm_beach_jurisdiction(db)
    db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id,
            instrument_type, book, page, execution_date, recording_date,
            consideration_minor, currency, legal_description_raw, source_url,
            observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
        DO UPDATE SET
            instrument_type=COALESCE(
                excluded.instrument_type, recorded_instrument.instrument_type
            ),
            book=COALESCE(excluded.book, recorded_instrument.book),
            page=COALESCE(excluded.page, recorded_instrument.page),
            recording_date=COALESCE(
                excluded.recording_date, recorded_instrument.recording_date
            ),
            consideration_minor=COALESCE(
                excluded.consideration_minor,
                recorded_instrument.consideration_minor
            ),
            legal_description_raw=COALESCE(
                excluded.legal_description_raw,
                recorded_instrument.legal_description_raw
            ),
            source_url=COALESCE(
                excluded.source_url, recorded_instrument.source_url
            ),
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            PALM_BEACH_RECORDER_SOURCE_ID,
            jurisdiction_geoid,
            instrument_number,
            _text(record.get("document_type")),
            _text(record.get("book")),
            _text(record.get("page")),
            _date_prefix(record.get("recording_date")),
            _minor_units(record.get("consideration")),
            (
                canonical_json(record.get("legal_descriptions"))
                if isinstance(record.get("legal_descriptions"), list)
                and record.get("legal_descriptions")
                else None
            ),
            _text(record.get("source_url")),
            observation_id,
            canonical_json(record),
        ),
    )
    row = db.execute(
        """
        SELECT instrument_id
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (
            PALM_BEACH_RECORDER_SOURCE_ID,
            jurisdiction_geoid,
            instrument_number,
        ),
    ).fetchone()
    return int(row["instrument_id"])


def _existing_palm_beach_parcel(
    db,
    *,
    native_parcel_id: str,
) -> int | None:
    source_placeholders = ", ".join(
        "?" for _ in PALM_BEACH_PARCEL_RESOLUTION_SOURCE_IDS
    )
    row = db.execute(
        f"""
        SELECT p.parcel_id
        FROM parcel_snapshot p
        WHERE p.source_id IN ({source_placeholders})
          AND p.jurisdiction_geoid='12099'
          AND (
            p.native_parcel_id=?
            OR EXISTS(
                SELECT 1
                FROM parcel_alias pa
                WHERE pa.parcel_id=p.parcel_id
                  AND pa.alias_value=?
            )
          )
        ORDER BY CASE WHEN p.source_id=? THEN 0 ELSE 1 END,
                 CASE WHEN p.roll_year='' THEN 1 ELSE 0 END,
                 p.roll_year DESC, p.parcel_id DESC
        LIMIT 1
        """,
        (
            *PALM_BEACH_PARCEL_RESOLUTION_SOURCE_IDS,
            native_parcel_id,
            native_parcel_id,
            PALM_BEACH_PROPERTY_SOURCE_ID,
        ),
    ).fetchone()
    return int(row["parcel_id"]) if row else None


def _merge_palm_beach_parcel_shell(
    db,
    *,
    canonical_parcel_id: int,
    shell_parcel_id: int,
) -> None:
    """Repoint an exact duplicate shell without changing child-source identity."""

    db.execute(
        """
        INSERT OR IGNORE INTO parcel_alias(
            parcel_id, alias_type, alias_value, source_id,
            effective_from, effective_to
        )
        SELECT ?, alias_type, alias_value, source_id,
               effective_from, effective_to
        FROM parcel_alias
        WHERE parcel_id=?
        """,
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        "DELETE FROM parcel_alias WHERE parcel_id=?",
        (shell_parcel_id,),
    )
    db.execute(
        "UPDATE parcel_address SET parcel_id=? WHERE parcel_id=?",
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO parcel_geometry(
            parcel_id, geometry_ref, geometry_format, crs,
            source_resolution, accuracy_disclaimer, source_id, snapshot_date
        )
        SELECT ?, geometry_ref, geometry_format, crs,
               source_resolution, accuracy_disclaimer, source_id, snapshot_date
        FROM parcel_geometry
        WHERE parcel_id=?
        """,
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        "DELETE FROM parcel_geometry WHERE parcel_id=?",
        (shell_parcel_id,),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO assessment(
            parcel_id, source_id, tax_year, land_value_minor,
            improvement_value_minor, total_value_minor, market_value_minor,
            assessed_value_minor, exempt_value_minor, currency,
            assessment_class, source_good_through, observation_id, raw_json
        )
        SELECT ?, source_id, tax_year, land_value_minor,
               improvement_value_minor, total_value_minor, market_value_minor,
               assessed_value_minor, exempt_value_minor, currency,
               assessment_class, source_good_through, observation_id, raw_json
        FROM assessment
        WHERE parcel_id=?
        """,
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        "DELETE FROM assessment WHERE parcel_id=?",
        (shell_parcel_id,),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO tax_account_event(
            parcel_id, source_id, tax_year, event_type, event_date,
            amount_minor, currency, status, native_event_id,
            observation_id, raw_json
        )
        SELECT ?, source_id, tax_year, event_type, event_date,
               amount_minor, currency, status, native_event_id,
               observation_id, raw_json
        FROM tax_account_event
        WHERE parcel_id=?
        """,
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        "DELETE FROM tax_account_event WHERE parcel_id=?",
        (shell_parcel_id,),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO sale_event(
            parcel_id, source_id, native_sale_id, sale_date,
            execution_date, recording_date, consideration_minor, currency,
            qualification_code, derivation, instrument_id,
            observation_id, raw_json
        )
        SELECT ?, source_id, native_sale_id, sale_date,
               execution_date, recording_date, consideration_minor, currency,
               qualification_code, derivation, instrument_id,
               observation_id, raw_json
        FROM sale_event
        WHERE parcel_id=?
        """,
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        "DELETE FROM sale_event WHERE parcel_id=?",
        (shell_parcel_id,),
    )
    db.execute(
        """
        UPDATE property_event_parcel_link SET
            parcel_id=?,
            link_method='exact_papa_pcn_after_cross_source_shell',
            link_confidence=1.0
        WHERE parcel_id=?
        """,
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO instrument_parcel(
            instrument_id, parcel_id, link_method, link_confidence,
            legal_description_raw
        )
        SELECT instrument_id, ?, link_method, link_confidence,
               legal_description_raw
        FROM instrument_parcel
        WHERE parcel_id=?
        """,
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        "DELETE FROM instrument_parcel WHERE parcel_id=?",
        (shell_parcel_id,),
    )

    lineage_rows = db.execute(
        """
        SELECT predecessor_parcel_id, successor_parcel_id, relationship,
               effective_date, source_id, evidence_ref
        FROM parcel_lineage
        WHERE predecessor_parcel_id=? OR successor_parcel_id=?
        """,
        (shell_parcel_id, shell_parcel_id),
    ).fetchall()
    db.execute(
        """
        DELETE FROM parcel_lineage
        WHERE predecessor_parcel_id=? OR successor_parcel_id=?
        """,
        (shell_parcel_id, shell_parcel_id),
    )
    for row in lineage_rows:
        predecessor = int(row["predecessor_parcel_id"])
        successor = int(row["successor_parcel_id"])
        if predecessor == shell_parcel_id:
            predecessor = canonical_parcel_id
        if successor == shell_parcel_id:
            successor = canonical_parcel_id
        if predecessor == successor:
            continue
        db.execute(
            """
            INSERT OR IGNORE INTO parcel_lineage(
                predecessor_parcel_id, successor_parcel_id, relationship,
                effective_date, source_id, evidence_ref
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                predecessor,
                successor,
                row["relationship"],
                row["effective_date"],
                row["source_id"],
                row["evidence_ref"],
            ),
        )

    db.execute(
        """
        INSERT OR IGNORE INTO ownership_assertion(
            parcel_id, source_id, assertion_type, raw_owner_name,
            normalized_owner_name, core_entity_id, effective_from,
            effective_to, confidence, claim_type, observation_id,
            evidence_ref, source_quote
        )
        SELECT ?, source_id, assertion_type, raw_owner_name,
               normalized_owner_name, core_entity_id, effective_from,
               effective_to, confidence, claim_type, observation_id,
               evidence_ref, source_quote
        FROM ownership_assertion
        WHERE parcel_id=?
        """,
        (canonical_parcel_id, shell_parcel_id),
    )
    db.execute(
        "DELETE FROM ownership_assertion WHERE parcel_id=?",
        (shell_parcel_id,),
    )
    db.execute(
        "DELETE FROM parcel_snapshot WHERE parcel_id=?",
        (shell_parcel_id,),
    )


def _reconcile_palm_beach_parcel_shells(
    db,
    *,
    canonical_parcel_id: int,
    native_parcel_id: str,
) -> dict[str, Any]:
    """Merge legacy or concurrent exact Palm Beach shells into PAPA."""

    source_placeholders = ", ".join(
        "?" for _ in PALM_BEACH_PARCEL_SHELL_SOURCE_IDS
    )
    shell_rows = db.execute(
        f"""
        SELECT DISTINCT p.parcel_id, p.source_id
        FROM parcel_snapshot p
        LEFT JOIN parcel_alias pa ON pa.parcel_id=p.parcel_id
        WHERE p.jurisdiction_geoid='12099'
          AND p.roll_year=''
          AND p.source_id IN ({source_placeholders})
          AND p.parcel_id<>?
          AND (
            p.native_parcel_id=?
            OR pa.alias_value=?
          )
        ORDER BY p.parcel_id
        """,
        (
            *PALM_BEACH_PARCEL_SHELL_SOURCE_IDS,
            canonical_parcel_id,
            native_parcel_id,
            native_parcel_id,
        ),
    ).fetchall()
    adopted_source_ids: list[str] = []
    for shell in shell_rows:
        shell_source_id = _text(shell["source_id"])
        if shell_source_id:
            adopted_source_ids.append(shell_source_id)
        _merge_palm_beach_parcel_shell(
            db,
            canonical_parcel_id=canonical_parcel_id,
            shell_parcel_id=int(shell["parcel_id"]),
        )
    return {
        "parcel_shells_repointed": len(shell_rows),
        "parcel_shell_source_ids_repointed": sorted(
            set(adopted_source_ids)
        ),
    }


ORANGE_TAX_PROJECTABLE_RECORD_KINDS = frozenset(
    {
        "property_tax_account_search_hit",
        "property_tax_bill_history",
        "property_tax_certificate_history",
        "property_tax_bill_detail",
        "historical_current_tax_roll_row",
        "historical_delinquent_tax_roll_row",
    }
)


def _orange_tax_jurisdiction(db) -> str:
    return _upsert_jurisdiction_values(
        db,
        geoid=query_orange_tax_collector.COUNTY_GEOID,
        name="Orange County, Florida",
        state_code="FL",
        jurisdiction_type="county",
        parent_geoid="12",
    )


def _orange_tax_source_url(
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
) -> str | None:
    for key in (
        "source_url",
        "source_document_url",
        "bill_url",
        "account_history_url",
        "portal_url",
    ):
        value = _text(record.get(key))
        if value:
            return value
    return _record_source_url(envelope, record)


def _orange_tax_row_occurrence(
    record: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    identity_contract = record.get("identity_contract")
    if not isinstance(identity_contract, Mapping):
        return None
    occurrence = identity_contract.get("row_occurrence")
    return occurrence if isinstance(occurrence, Mapping) else None


def _orange_tax_source_occurrence_id(record: Mapping[str, Any]) -> str:
    record_kind = _text(record.get("record_kind")) or "source_row"
    direct_fields = {
        "property_tax_account_search_hit": ("algolia_object_id",),
        "property_tax_bill_history": ("bill_uuid",),
        "property_tax_certificate_history": (
            "certificate_number",
            "bill_uuid",
        ),
        "property_tax_bill_detail": ("bill_uuid",),
    }
    values = [
        value
        for field in direct_fields.get(record_kind, ())
        if (value := _text(record.get(field)))
    ]
    if values:
        return ":".join(values)
    row_occurrence = _orange_tax_row_occurrence(record)
    if row_occurrence is not None:
        occurrence_id = _text(row_occurrence.get("occurrence_id"))
        if occurrence_id:
            return occurrence_id
    return (
        _text(record.get("canonical_ref"))
        or _text(record.get("release_id"))
        or sha256_fingerprint(record)
    )


def _orange_tax_exact_parcel_account(
    record: Mapping[str, Any],
) -> str | None:
    parcel_join = record.get("parcel_join")
    if not isinstance(parcel_join, Mapping):
        return None
    account = _text(parcel_join.get("normalized_15_digit_account"))
    if (
        parcel_join.get("exact") is not True
        or account is None
        or re.fullmatch(r"\d{15}", account) is None
    ):
        return None
    try:
        normalized = query_orange_tax_collector.normalize_account(account)
    except query_orange_tax_collector.OrangeTaxError:
        return None
    return normalized if normalized == account else None


def _orange_tax_decimal(
    value: Any,
    *,
    field: str = "decimal",
) -> Any:
    return value.get(field) if isinstance(value, Mapping) else None


def _orange_tax_date(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("iso")
    return _date_prefix(value)


def _orange_tax_parcel(
    db,
    *,
    native_parcel_id: str,
    observation_id: int,
    retrieved_at: str,
    record: Mapping[str, Any],
) -> int:
    publication_date = _date_prefix(record.get("publication_date"))
    return _upsert_parcel_snapshot(
        db,
        source_id=ORANGE_TAX_SOURCE_ID,
        jurisdiction_geoid=query_orange_tax_collector.COUNTY_GEOID,
        native_parcel_id=native_parcel_id,
        roll_year="",
        effective_from=retrieved_at,
        source_good_through=publication_date,
        observation_id=observation_id,
        record={
            **dict(record),
            "parcel_representation": "orange_tax_collector_account_shell",
        },
    )


def _orange_tax_aliases(
    db,
    *,
    parcel_id: int,
    native_parcel_id: str,
    record: Mapping[str, Any],
    effective_from: str,
) -> int:
    aliases_inserted = 0
    parcel_join = record.get("parcel_join")
    if isinstance(parcel_join, Mapping):
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="orange_tax_formatted_account",
            alias_value=parcel_join.get("formatted_account"),
            source_id=ORANGE_TAX_SOURCE_ID,
            effective_from=effective_from,
        )
    native_account_id = _text(
        record.get("native_account_id")
        or record.get("native_parcel_number")
    )
    if native_account_id and native_account_id != native_parcel_id:
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="orange_tax_published_account",
            alias_value=native_account_id,
            source_id=ORANGE_TAX_SOURCE_ID,
            effective_from=effective_from,
        )
    return aliases_inserted


def _orange_tax_owner_and_address_projections(
    db,
    *,
    parcel_id: int,
    observation_id: int,
    retrieved_at: str,
    record: Mapping[str, Any],
) -> tuple[int, int]:
    record_kind = _text(record.get("record_kind"))
    if record_kind not in {
        "property_tax_account_search_hit",
        "property_tax_bill_detail",
    }:
        return 0, 0

    owners = record.get("owners")
    owners_upserted = 0
    if isinstance(owners, list):
        for owner in owners:
            if not isinstance(owner, Mapping):
                continue
            raw_name = _text(owner.get("raw_name") or owner.get("name"))
            if not raw_name or set(raw_name) <= {"*"}:
                continue
            owners_upserted += _upsert_tax_account_owner(
                db,
                parcel_id=parcel_id,
                source_id=ORANGE_TAX_SOURCE_ID,
                raw_name=raw_name,
                effective_from=retrieved_at,
                observation_id=observation_id,
                evidence_ref=_text(record.get("canonical_ref")),
            )

    addresses: list[tuple[str, Mapping[str, Any]]] = []
    if record_kind == "property_tax_account_search_hit":
        for role, field in (
            ("situs", "situs_entities"),
            ("mailing", "billing_entities"),
        ):
            entities = record.get(field)
            if not isinstance(entities, list):
                continue
            for entity in entities:
                if not isinstance(entity, Mapping):
                    continue
                addresses.append(
                    (
                        role,
                        {
                            "raw": entity.get("address"),
                            "city": entity.get("city"),
                            "state": entity.get("state")
                            or entity.get("province"),
                            "postal_code": entity.get("zip"),
                            "country": entity.get("country"),
                        },
                    )
                )
    else:
        for role, field in (
            ("situs", "situs_address"),
            ("mailing", "mailing_address"),
        ):
            address = record.get(field)
            if isinstance(address, Mapping):
                addresses.append((role, address))

    addresses_inserted = sum(
        int(
            _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=ORANGE_TAX_SOURCE_ID,
                role=role,
                address=address,
                effective_from=retrieved_at,
            )
        )
        for role, address in addresses
    )
    return owners_upserted, addresses_inserted


def _orange_tax_event(
    db,
    *,
    parcel_id: int,
    observation_id: int,
    record: Mapping[str, Any],
    event_type: str,
    native_event_id: str,
    status: str,
    event_date: str | None = None,
    amount: Any = None,
    raw: Mapping[str, Any] | None = None,
) -> int:
    return _upsert_tax_account_event(
        db,
        parcel_id=parcel_id,
        source_id=ORANGE_TAX_SOURCE_ID,
        event_type=event_type,
        tax_year=_text(record.get("tax_year")) or "",
        event_date=event_date,
        amount=amount,
        status=status,
        native_event_id=native_event_id,
        observation_id=observation_id,
        raw=raw or record,
    )


def _orange_tax_event_projections(
    db,
    *,
    parcel_id: int,
    observation_id: int,
    record: Mapping[str, Any],
    row_occurrence_id: str,
) -> int:
    record_kind = _text(record.get("record_kind"))
    events_upserted = 0

    if record_kind == "property_tax_bill_history":
        bill_uuid = _text(record.get("bill_uuid")) or row_occurrence_id
        status = record.get("status")
        status_mapping = status if isinstance(status, Mapping) else {}
        events_upserted += _orange_tax_event(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            record=record,
            event_type="property_tax_bill_history",
            native_event_id=bill_uuid,
            amount=_orange_tax_decimal(record.get("balance_due")),
            status=(
                _text(status_mapping.get("raw"))
                or "source_observed_bill_history"
            ),
        )
        payment = record.get("payment")
        if isinstance(payment, Mapping):
            payment_date = _orange_tax_date(payment.get("date"))
            receipt_number = _text(payment.get("receipt_number"))
            payment_identity = (
                receipt_number
                or f"{bill_uuid}:payment:{payment_date or sha256_fingerprint(payment)}"
            )
            events_upserted += _orange_tax_event(
                db,
                parcel_id=parcel_id,
                observation_id=observation_id,
                record=record,
                event_type="property_tax_payment",
                native_event_id=payment_identity,
                event_date=payment_date,
                amount=status_mapping.get("amount_decimal"),
                status="source_observed_payment",
                raw={"record": dict(record), "payment": dict(payment)},
            )
        return events_upserted

    if record_kind == "property_tax_certificate_history":
        certificate_number = (
            _text(record.get("certificate_number")) or row_occurrence_id
        )
        return _orange_tax_event(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            record=record,
            event_type="tax_certificate_state",
            native_event_id=certificate_number,
            event_date=_orange_tax_date(record.get("status_date")),
            amount=_orange_tax_decimal(record.get("face_value")),
            status=(
                _text(record.get("certificate_status"))
                or "source_observed_certificate_state"
            ),
        )

    if record_kind == "property_tax_bill_detail":
        status = record.get("status")
        status_mapping = status if isinstance(status, Mapping) else {}
        return _orange_tax_event(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            record=record,
            event_type="property_tax_bill_detail",
            native_event_id=_text(record.get("bill_uuid")) or row_occurrence_id,
            amount=_orange_tax_decimal(record.get("amount_due")),
            status=(
                _text(status_mapping.get("raw"))
                or "source_observed_bill_detail"
            ),
        )

    if record_kind == "historical_current_tax_roll_row":
        tax = record.get("tax")
        tax_mapping = tax if isinstance(tax, Mapping) else {}
        events_upserted += _orange_tax_event(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            record=record,
            event_type="historical_current_tax_roll_row",
            native_event_id=row_occurrence_id,
            amount=_orange_tax_decimal(tax_mapping.get("balance_due")),
            status=(
                _text(record.get("status_code"))
                or "source_observed_historical_current_row"
            ),
        )
        payment = record.get("payment")
        payment_mapping = payment if isinstance(payment, Mapping) else {}
        payment_date = _orange_tax_date(payment_mapping.get("date"))
        validation_number = _text(
            payment_mapping.get("validation_number")
        )
        amount_paid = _orange_tax_decimal(tax_mapping.get("amount_paid"))
        if validation_number or payment_date or amount_paid is not None:
            events_upserted += _orange_tax_event(
                db,
                parcel_id=parcel_id,
                observation_id=observation_id,
                record=record,
                event_type="property_tax_payment",
                native_event_id=(
                    validation_number
                    or _text(record.get("tax_summary_id"))
                    or f"{row_occurrence_id}:payment"
                ),
                event_date=payment_date,
                amount=amount_paid,
                status="source_observed_payment",
                raw={
                    "record": dict(record),
                    "payment": dict(payment_mapping),
                },
            )
        return events_upserted

    if record_kind != "historical_delinquent_tax_roll_row":
        return 0

    tax = record.get("tax")
    tax_mapping = tax if isinstance(tax, Mapping) else {}
    events_upserted += _orange_tax_event(
        db,
        parcel_id=parcel_id,
        observation_id=observation_id,
        record=record,
        event_type="historical_delinquent_tax_roll_row",
        native_event_id=row_occurrence_id,
        amount=_orange_tax_decimal(tax_mapping.get("payoff_due")),
        status=(
            _text(record.get("status_code"))
            or "source_observed_historical_delinquent_row"
        ),
    )

    payment = record.get("payment")
    payment_mapping = payment if isinstance(payment, Mapping) else {}
    payment_date = (
        _orange_tax_date(payment_mapping.get("payment_date"))
        or _orange_tax_date(payment_mapping.get("payoff_date"))
    )
    validation_number = _text(payment_mapping.get("validation_number"))
    payment_code = _text(payment_mapping.get("payment_code"))
    if validation_number or payment_date or payment_code:
        events_upserted += _orange_tax_event(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            record=record,
            event_type="property_tax_payment",
            native_event_id=(
                validation_number
                or _text(record.get("tax_summary_id"))
                or f"{row_occurrence_id}:payment"
            ),
            event_date=payment_date,
            status=payment_code or "source_observed_payment",
            raw={"record": dict(record), "payment": dict(payment_mapping)},
        )

    certificate = record.get("certificate")
    certificate_mapping = (
        certificate if isinstance(certificate, Mapping) else {}
    )
    certificate_number = _text(certificate_mapping.get("number"))
    certificate_issue_date = _orange_tax_date(
        certificate_mapping.get("issue_date")
    )
    certificate_purchase_date = _orange_tax_date(
        certificate_mapping.get("purchase_date")
    )
    certificate_face_value = _orange_tax_decimal(
        certificate_mapping.get("face_value")
    )
    if any(
        value not in (None, "")
        for value in (
            certificate_number,
            certificate_mapping.get("year"),
            certificate_mapping.get("sequence"),
            certificate_face_value,
            certificate_issue_date,
            certificate_purchase_date,
            certificate_mapping.get("bidder_number"),
        )
    ):
        events_upserted += _orange_tax_event(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            record=record,
            event_type="tax_certificate_state",
            native_event_id=certificate_number
            or f"{row_occurrence_id}:certificate",
            event_date=certificate_issue_date or certificate_purchase_date,
            amount=certificate_face_value,
            status="source_observed_certificate_state",
            raw={
                "record": dict(record),
                "certificate": dict(certificate_mapping),
            },
        )

    tax_deed = record.get("tax_deed")
    tax_deed_mapping = tax_deed if isinstance(tax_deed, Mapping) else {}
    tax_deed_number = _text(tax_deed_mapping.get("number"))
    tax_deed_status = _text(
        tax_deed_mapping.get("status") or record.get("tax_deed_status")
    )
    tax_deed_application_date = _orange_tax_date(
        tax_deed_mapping.get("application_date")
    )
    tax_deed_redemption_date = _orange_tax_date(
        tax_deed_mapping.get("redemption_date")
    )
    if any(
        value not in (None, "")
        for value in (
            tax_deed_number,
            tax_deed_mapping.get("year"),
            tax_deed_mapping.get("sequence"),
            tax_deed_status,
            tax_deed_application_date,
            tax_deed_redemption_date,
        )
    ):
        tax_deed_identity = ":".join(
            value
            for value in (
                _text(tax_deed_mapping.get("year")),
                tax_deed_number,
                _text(tax_deed_mapping.get("sequence")),
            )
            if value
        )
        events_upserted += _orange_tax_event(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            record=record,
            event_type="tax_deed_state",
            native_event_id=tax_deed_identity
            or f"{row_occurrence_id}:tax-deed",
            event_date=(
                tax_deed_redemption_date
                or tax_deed_application_date
            ),
            status=tax_deed_status or "source_observed_tax_deed_state",
            raw={"record": dict(record), "tax_deed": dict(tax_deed_mapping)},
        )
    return events_upserted


def _orange_tax_assessment_projection(
    db,
    *,
    parcel_id: int,
    observation_id: int,
    record: Mapping[str, Any],
) -> tuple[int, list[str]]:
    if _text(record.get("record_kind")) not in {
        "historical_current_tax_roll_row",
        "historical_delinquent_tax_roll_row",
    }:
        return 0, []
    tax_year = _text(record.get("tax_year"))
    values = record.get("values")
    if not tax_year or not isinstance(values, Mapping):
        return 0, []
    explicit = {
        name: _orange_tax_decimal(values.get(name))
        for name in ("total", "exempt", "taxable")
    }
    projected_fields = [
        name for name, value in explicit.items() if value is not None
    ]
    if not projected_fields:
        return 0, []
    return (
        _upsert_assessment_projection(
            db,
            parcel_id=parcel_id,
            source_id=ORANGE_TAX_SOURCE_ID,
            tax_year=tax_year,
            total_value=explicit["total"],
            exempt_value=explicit["exempt"],
            assessment_class="orange_tax_collector_historical_roll_values",
            source_good_through=_date_prefix(record.get("publication_date")),
            observation_id=observation_id,
            raw={
                "record": dict(record),
                "projected_fields": projected_fields,
                "taxable_value_decimal": explicit["taxable"],
            },
        ),
        projected_fields,
    )


def _ingest_orange_tax_collector_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve every Orange row and project exact parcel-linked tax facts."""

    _assert_record_source(record, source_id)
    _orange_tax_jurisdiction(db)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(
        envelope
    )
    record_kind = (
        _text(record.get("record_kind"))
        or _text(record.get("record_type"))
        or "source_row"
    )
    source_occurrence_id = _orange_tax_source_occurrence_id(record)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_occurrence_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_orange_tax_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    if record_kind not in ORANGE_TAX_PROJECTABLE_RECORD_KINDS:
        return {
            "projection_skipped": True,
            "reason": "orange_tax_metadata_or_transport_observation",
            "record_kind": record_kind,
            "source_occurrence_id": source_occurrence_id,
            "observation_id": observation_id,
            "record_sha256": record_hash,
        }

    native_parcel_id = _orange_tax_exact_parcel_account(record)
    if native_parcel_id is None:
        return {
            "projection_skipped": True,
            "reason": "orange_tax_record_lacks_exact_15_digit_parcel_join",
            "record_kind": record_kind,
            "source_occurrence_id": source_occurrence_id,
            "observation_id": observation_id,
            "record_sha256": record_hash,
        }

    parcel_id = _orange_tax_parcel(
        db,
        native_parcel_id=native_parcel_id,
        observation_id=observation_id,
        retrieved_at=retrieved_at,
        record=record,
    )
    aliases_inserted = _orange_tax_aliases(
        db,
        parcel_id=parcel_id,
        native_parcel_id=native_parcel_id,
        record=record,
        effective_from=retrieved_at,
    )
    owners_upserted, addresses_inserted = (
        _orange_tax_owner_and_address_projections(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            retrieved_at=retrieved_at,
            record=record,
        )
    )
    tax_events_upserted = _orange_tax_event_projections(
        db,
        parcel_id=parcel_id,
        observation_id=observation_id,
        record=record,
        row_occurrence_id=source_occurrence_id,
    )
    assessments_upserted, assessment_value_fields = (
        _orange_tax_assessment_projection(
            db,
            parcel_id=parcel_id,
            observation_id=observation_id,
            record=record,
        )
    )
    return {
        "parcel_id": parcel_id,
        "parcel_anchor_source_id": ORANGE_TAX_SOURCE_ID,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            ORANGE_TAX_SOURCE_ID,
            query_orange_tax_collector.COUNTY_GEOID,
            record_kind,
            source_occurrence_id,
        ),
        "native_parcel_id": native_parcel_id,
        "source_occurrence_id": source_occurrence_id,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "owners_upserted": owners_upserted,
        "addresses_inserted": addresses_inserted,
        "tax_events_upserted": tax_events_upserted,
        "assessments_upserted": assessments_upserted,
        "assessment_value_fields": assessment_value_fields,
        "recorded_instruments_upserted": 0,
    }


def _palm_beach_tax_jurisdiction(db) -> str:
    return _upsert_jurisdiction_values(
        db,
        geoid=query_palm_beach_tax_collector.COUNTY_GEOID,
        name="Palm Beach County, Florida",
        state_code="FL",
        jurisdiction_type="county",
        parent_geoid="12",
    )


def _normalize_palm_beach_tax_pcn(value: Any) -> str:
    try:
        normalized = query_palm_beach_tax_collector.normalize_pcn(value)
    except query_palm_beach_tax_collector.PalmBeachTaxError as error:
        raise PropertyIngestError(str(error)) from error
    if normalized is None:
        raise PropertyIngestError("Palm Beach Tax Collector record lacks a PCN")
    return normalized


def _preserve_palm_beach_tax_observation(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
    reason: str,
) -> dict[str, Any]:
    """Preserve source metadata and search rows without inventing a parcel fact."""

    _assert_record_source(record, source_id)
    _palm_beach_tax_jurisdiction(db)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    record_kind = (
        _text(record.get("record_kind"))
        or _text(record.get("record_type"))
        or "source_row"
    )
    source_native_id = (
        _text(record.get("source_occurrence_id"))
        or _text(record.get("native_account_id"))
        or _text(record.get("native_parcel_id"))
        or _text(record.get("canonical_ref"))
        or sha256_fingerprint(record)
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    return {
        "projection_skipped": True,
        "reason": reason,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "source_native_id": source_native_id,
        "record_kind": record_kind,
    }


def _palm_beach_tax_parcel(
    db,
    *,
    native_parcel_id: str,
    observation_id: int,
    retrieved_at: str,
    record: Mapping[str, Any],
) -> tuple[int, bool]:
    """Reuse an exact Palm Beach parcel before creating a tax-source shell."""

    parcel_id = _existing_palm_beach_parcel(
        db,
        native_parcel_id=native_parcel_id,
    )
    if parcel_id is not None:
        return parcel_id, False
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=PALM_BEACH_TAX_SOURCE_ID,
        jurisdiction_geoid="12099",
        native_parcel_id=native_parcel_id,
        roll_year="",
        effective_from=retrieved_at,
        source_good_through=None,
        observation_id=observation_id,
        record={
            **dict(record),
            "placeholder_state": (
                "tax_account_pcn_pending_property_appraiser_roll"
            ),
        },
    )
    return parcel_id, True


def _palm_beach_tax_aliases(
    db,
    *,
    parcel_id: int,
    record: Mapping[str, Any],
    source_id: str,
    effective_from: str,
) -> int:
    aliases_inserted = _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="pbc_tax_account_alternate_key",
        alias_value=record.get("native_account_id"),
        source_id=source_id,
        effective_from=effective_from,
    )
    formatted_pcn = _text(record.get("formatted_pcn"))
    native_parcel_id = _text(record.get("native_parcel_id"))
    if formatted_pcn and formatted_pcn != native_parcel_id:
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="palm_beach_formatted_pcn",
            alias_value=formatted_pcn,
            source_id=source_id,
            effective_from=effective_from,
        )
    return aliases_inserted


def _ingest_palm_beach_tax_collector_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project exact tax-account snapshots, bill states, and payment events."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    projectable_kinds = {
        "property_tax_account_snapshot",
        "property_tax_bill_snapshot",
        "property_tax_payment",
    }
    if record_kind not in projectable_kinds:
        return _preserve_palm_beach_tax_observation(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="palm_beach_tax_source_metadata_or_discovery_row",
        )

    native_parcel_id = _normalize_palm_beach_tax_pcn(
        record.get("native_parcel_id")
    )
    native_account_id = _text(record.get("native_account_id"))
    if not native_account_id:
        raise PropertyIngestError(
            "Palm Beach Tax Collector projected record lacks AlternateKey"
        )
    source_occurrence_id = _text(record.get("source_occurrence_id"))
    if not source_occurrence_id:
        raise PropertyIngestError(
            "Palm Beach Tax Collector projected record lacks occurrence identity"
        )

    _palm_beach_tax_jurisdiction(db)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_occurrence_id,
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_id, placeholder_created = _palm_beach_tax_parcel(
        db,
        native_parcel_id=native_parcel_id,
        observation_id=observation_id,
        retrieved_at=retrieved_at,
        record=record,
    )
    aliases_inserted = _palm_beach_tax_aliases(
        db,
        parcel_id=parcel_id,
        record=record,
        source_id=source_id,
        effective_from=retrieved_at,
    )

    common_result = {
        "parcel_id": parcel_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            "12099",
            record_kind,
            source_occurrence_id,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "native_parcel_id": native_parcel_id,
        "native_account_id": native_account_id,
        "source_occurrence_id": source_occurrence_id,
        "parcel_placeholder_created": int(placeholder_created),
        "aliases_inserted": aliases_inserted,
    }

    if record_kind == "property_tax_account_snapshot":
        owners = record.get("owners", [])
        if not isinstance(owners, list):
            raise PropertyIngestError("Palm Beach tax account owners must be a list")
        owners_upserted = 0
        evidence_ref = _text(record.get("canonical_ref"))
        for index, owner_value in enumerate(owners):
            owner = _mapping(owner_value, f"record.owners[{index}]")
            raw_name = _text(owner.get("raw_name"))
            masked = owner.get("masked") is True or bool(
                raw_name and set(raw_name) <= {"*"}
            )
            if not raw_name or masked:
                continue
            owners_upserted += _upsert_tax_account_owner(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                raw_name=raw_name,
                effective_from=retrieved_at,
                observation_id=observation_id,
                evidence_ref=evidence_ref,
            )
        addresses_inserted = 0
        for role, address_value in (
            ("situs", record.get("property_address")),
            ("mailing", record.get("mailing_address")),
        ):
            if isinstance(address_value, Mapping):
                addresses_inserted += int(
                    _upsert_address(
                        db,
                        parcel_id=parcel_id,
                        source_id=source_id,
                        role=role,
                        address=address_value,
                        effective_from=retrieved_at,
                    )
                )
        tax_events_upserted = _upsert_tax_account_event(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            event_type="tax_account_snapshot",
            tax_year="",
            event_date=None,
            amount=None,
            status=(
                _text(record.get("account_status"))
                or "source_observed_account_snapshot"
            ),
            native_event_id=source_occurrence_id,
            observation_id=observation_id,
            raw=record,
        )
        return {
            **common_result,
            "owners_upserted": owners_upserted,
            "addresses_inserted": addresses_inserted,
            "tax_events_upserted": tax_events_upserted,
        }

    if record_kind == "property_tax_bill_snapshot":
        amounts = record.get("amounts")
        if not isinstance(amounts, Mapping):
            amounts = {}
        installment = _text(record.get("installment"))
        tax_events_upserted = _upsert_tax_account_event(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            event_type=(
                "property_tax_installment_snapshot"
                if installment
                else "property_tax_bill_snapshot"
            ),
            tax_year=_text(record.get("tax_year")) or "",
            event_date=None,
            amount=amounts.get("amount_due"),
            status=_text(record.get("status")) or "source_observed_bill_snapshot",
            native_event_id=source_occurrence_id,
            observation_id=observation_id,
            raw=record,
        )
        return {
            **common_result,
            "tax_events_upserted": tax_events_upserted,
            "bill_id": _text(record.get("bill_id")),
            "bill_number": _text(record.get("bill_number")),
            "installment": installment,
        }

    event_date = _date_prefix(record.get("effective_payment_date"))
    tax_events_upserted = _upsert_tax_account_event(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        event_type="property_tax_payment",
        tax_year=_text(record.get("tax_year")) or "",
        event_date=event_date,
        amount=record.get("receipt_amount"),
        status="source_observed_payment",
        native_event_id=source_occurrence_id,
        observation_id=observation_id,
        raw=record,
    )
    return {
        **common_result,
        "tax_events_upserted": tax_events_upserted,
        "effective_payment_date": event_date,
        "receipt_number": _text(record.get("receipt_number")),
        "payer_projected_as_owner": False,
    }


def _upsert_palm_beach_tax_deed_artifact(
    db,
    *,
    native_document_id: str,
    sha256: str,
    mime_type: str | None,
    storage_path: str | None,
    source_url: str | None,
    acquired_at: str,
) -> int:
    existing = db.execute(
        """
        SELECT artifact_id
        FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid='12099'
          AND native_document_id=?
          AND COALESCE(sha256, '')=COALESCE(?, '')
        """,
        (
            PALM_BEACH_TAX_DEEDS_SOURCE_ID,
            native_document_id,
            sha256,
        ),
    ).fetchone()
    values = (
        None,
        sha256,
        mime_type,
        None,
        storage_path,
        source_url,
        "direct_source_pdf_download",
        "official_public_record_uncertified",
        "public",
        acquired_at,
    )
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, '12099', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                PALM_BEACH_TAX_DEEDS_SOURCE_ID,
                native_document_id,
                *values,
            ),
        )
        return int(cursor.lastrowid)
    artifact_id = int(existing["artifact_id"])
    db.execute(
        """
        UPDATE document_artifact SET
            instrument_id=?, sha256=?, mime_type=?, page_count=?,
            storage_path=?, source_url=?, acquisition_method=?,
            rights_tier=?, access_state=?, acquired_at=?
        WHERE artifact_id=?
        """,
        (*values, artifact_id),
    )
    return artifact_id


def _ingest_palm_beach_tax_deed_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project tax-deed cases as events without creating title assertions."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    if record_kind == "tax_deed_document_artifact":
        _palm_beach_tax_jurisdiction(db)
        portal_row_id = _text(record.get("portal_row_id"))
        native_document_id = _text(record.get("native_document_id"))
        sha256 = _text(record.get("sha256"))
        if not portal_row_id or not portal_row_id.isdigit():
            raise PropertyIngestError(
                "Palm Beach tax-deed artifact lacks a numeric portal row ID"
            )
        if not native_document_id or not native_document_id.isdigit():
            raise PropertyIngestError(
                "Palm Beach tax-deed artifact lacks a numeric image ID"
            )
        if not sha256:
            raise PropertyIngestError(
                "Palm Beach tax-deed artifact lacks its PDF SHA-256"
            )
        (
            query_fingerprint,
            retrieved_at,
            status,
            warnings,
        ) = _observation_context(envelope)
        source_native_id = f"{portal_row_id}:document:{native_document_id}"
        observation_id, record_hash = _insert_observation(
            db,
            source_id=source_id,
            source_native_id=source_native_id,
            record_kind=record_kind,
            query_fingerprint=query_fingerprint,
            source_url=_record_source_url(envelope, record),
            retrieved_at=retrieved_at,
            access_status=status,
            schema_fingerprint=_record_schema_fingerprint(record),
            raw=record,
            raw_artifact_path=(
                _text(record.get("document_output")) or raw_artifact_path
            ),
            raw_artifact_sha256=sha256,
            warnings=warnings,
        )
        artifact_id = _upsert_palm_beach_tax_deed_artifact(
            db,
            native_document_id=native_document_id,
            sha256=sha256,
            mime_type=_text(record.get("media_type")) or "application/pdf",
            storage_path=_text(record.get("document_output")),
            source_url=_text(record.get("source_url")),
            acquired_at=retrieved_at,
        )
        return {
            "artifact_id": artifact_id,
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "portal_row_id": portal_row_id,
            "native_document_id": native_document_id,
            "document_occurrence_id": _text(
                record.get("document_occurrence_id")
            ),
            "parent_case_identity_preserved": True,
        }

    if record_kind != "tax_deed_case_occurrence":
        return _preserve_palm_beach_tax_observation(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="palm_beach_tax_deed_metadata_or_probe_row",
        )

    result = _ingest_property_event_record(
        db,
        envelope=envelope,
        record=record,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        expected_geoid="12099",
        parcel_alias_source_id=PALM_BEACH_PROPERTY_SOURCE_ID,
    )
    raw_pcn = _text(record.get("parcel_id"))
    normalized_pcn = query_palm_beach_tax_deeds.normalize_pcn(raw_pcn)
    published_normalized_pcn = _text(record.get("parcel_id_normalized"))
    if (
        published_normalized_pcn
        and normalized_pcn
        and published_normalized_pcn != normalized_pcn
    ):
        raise PropertyIngestError(
            "Palm Beach tax-deed PCN fields do not normalize to the same value"
        )
    normalized_pcn = normalized_pcn or published_normalized_pcn
    if not normalized_pcn:
        return {
            **result,
            "tax_events_upserted": 0,
            "aliases_inserted": 0,
            "parcel_placeholder_created": 0,
            "parcel_link_method": "unresolved_source_parcel_label",
        }

    parcel_id = result.get("parcel_id")
    placeholder_created = False
    if parcel_id is None:
        parcel_id = _existing_palm_beach_parcel(
            db,
            native_parcel_id=normalized_pcn,
        )
    if parcel_id is None:
        parcel_id = _upsert_parcel_snapshot(
            db,
            source_id=PALM_BEACH_TAX_DEEDS_SOURCE_ID,
            jurisdiction_geoid="12099",
            native_parcel_id=normalized_pcn,
            roll_year="",
            effective_from=_text(envelope.get("retrieved_at")),
            source_good_through=None,
            observation_id=int(result["observation_id"]),
            record={
                "source_id": source_id,
                "native_parcel_id": normalized_pcn,
                "source_parcel_id_raw": raw_pcn,
                "placeholder_state": (
                    "tax_deed_pcn_pending_property_appraiser_or_dor"
                ),
                "tax_deed_record": dict(record),
            },
        )
        placeholder_created = True

    join_evidence = record.get("parcel_join_evidence")
    db.execute(
        """
        UPDATE property_event_parcel_link SET
            parcel_id=?, map_taxlot_candidate=?,
            link_method='exact_source_pcn_candidate',
            link_confidence=1.0, evidence_json=?
        WHERE event_id=?
        """,
        (
            parcel_id,
            normalized_pcn,
            canonical_json(
                join_evidence
                if isinstance(join_evidence, Mapping)
                else {
                    "published_location": {
                        "raw": raw_pcn,
                        "normalized_candidate": normalized_pcn,
                    }
                }
            ),
            int(result["event_id"]),
        ),
    )
    aliases_inserted = _upsert_alias(
        db,
        parcel_id=int(parcel_id),
        alias_type="palm_beach_pcn",
        alias_value=raw_pcn,
        source_id=source_id,
        effective_from=_text(envelope.get("retrieved_at")),
    )
    tax_events_upserted = _upsert_tax_account_event(
        db,
        parcel_id=int(parcel_id),
        source_id=source_id,
        event_type="tax_deed_case_status",
        tax_year="",
        event_date=_date_prefix(record.get("auction_date")),
        amount=None,
        status=_text(record.get("status")) or "source_observed_tax_deed_case",
        native_event_id=_text(record.get("native_event_id")),
        observation_id=int(result["observation_id"]),
        raw=record,
    )
    return {
        **result,
        "parcel_id": int(parcel_id),
        "parcel_link_method": "exact_source_pcn_candidate",
        "parcel_placeholder_created": int(placeholder_created),
        "aliases_inserted": aliases_inserted,
        "tax_events_upserted": tax_events_upserted,
        "current_ownership_assertions_created": 0,
        "recorded_title_conclusions_created": 0,
    }


def _upsert_palm_beach_artifact(
    db,
    *,
    native_document_id: str,
    instrument_id: int,
    sha256: str | None,
    mime_type: str | None,
    page_count: int | None,
    storage_path: str | None,
    source_url: str | None,
    acquisition_method: str,
    access_state: str,
    acquired_at: str | None,
) -> int:
    existing = db.execute(
        """
        SELECT artifact_id
        FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid='12099'
          AND native_document_id=?
          AND COALESCE(sha256, '')=COALESCE(?, '')
        """,
        (PALM_BEACH_RECORDER_SOURCE_ID, native_document_id, sha256),
    ).fetchone()
    values = (
        instrument_id,
        sha256,
        mime_type,
        page_count,
        storage_path,
        source_url,
        acquisition_method,
        "official_public_record_uncertified",
        access_state,
        acquired_at,
    )
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, '12099', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                PALM_BEACH_RECORDER_SOURCE_ID,
                native_document_id,
                *values,
            ),
        )
        return int(cursor.lastrowid)
    artifact_id = int(existing["artifact_id"])
    db.execute(
        """
        UPDATE document_artifact SET
            instrument_id=?, sha256=?, mime_type=?, page_count=?,
            storage_path=?, source_url=?, acquisition_method=?,
            rights_tier=?, access_state=?, acquired_at=?
        WHERE artifact_id=?
        """,
        (*values, artifact_id),
    )
    return artifact_id


def _ingest_palm_beach_recorder_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project exact Clerk instruments and acquired image pages."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    if record_kind not in {
        "recorded_instrument",
        "document_image_artifact",
    }:
        return _ingest_statewide_parcel_observation_only(
            db,
            envelope=envelope,
            record=record,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            reason="palm_beach_non_instrument_record",
        )
    instrument_number = _text(record.get("instrument_number"))
    if not instrument_number:
        raise PropertyIngestError(
            "Palm Beach Official Records record lacks instrument_number"
        )
    if not instrument_number.isdigit():
        raise PropertyIngestError(
            "Palm Beach Official Records instrument_number must be numeric"
        )

    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    portal_document_id = _text(record.get("native_document_id"))
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=(
            instrument_number
            if record_kind == "recorded_instrument"
            else portal_document_id
        ),
        record_kind=record_kind,
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=(
            _text(record.get("sha256"))
            if record_kind == "document_image_artifact"
            else raw_artifact_sha256
        ),
        warnings=warnings,
    )
    existing_instrument = db.execute(
        """
        SELECT instrument_id
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid='12099'
          AND native_document_id=?
        """,
        (source_id, instrument_number),
    ).fetchone()
    if record_kind == "document_image_artifact" and existing_instrument:
        instrument_id = int(existing_instrument["instrument_id"])
    else:
        instrument_id = _palm_beach_instrument_id(
            db,
            instrument_number=instrument_number,
            observation_id=observation_id,
            record=record,
        )

    if record_kind == "document_image_artifact":
        if not portal_document_id:
            raise PropertyIngestError(
                "Palm Beach image artifact lacks native_document_id"
            )
        digest = _text(record.get("sha256"))
        if not digest:
            raise PropertyIngestError("Palm Beach image artifact lacks sha256")
        artifact_id = _upsert_palm_beach_artifact(
            db,
            native_document_id=portal_document_id,
            instrument_id=instrument_id,
            sha256=digest,
            mime_type=_text(record.get("media_type")),
            page_count=1,
            storage_path=_text(record.get("document_output")),
            source_url=_text(record.get("source_url")),
            acquisition_method="direct_source_image_download",
            access_state="public",
            acquired_at=retrieved_at,
        )
        return {
            "instrument_id": instrument_id,
            "artifact_id": artifact_id,
            "canonical_ref": _text(record.get("canonical_ref")),
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "official_instrument_number": instrument_number,
            "portal_page_id": portal_document_id,
            "artifacts_upserted": 1,
        }

    if not portal_document_id:
        raise PropertyIngestError(
            "Palm Beach instrument record lacks portal native_document_id"
        )
    parties = record.get("parties", [])
    if not isinstance(parties, list):
        raise PropertyIngestError("record.parties must be a list")
    parties_upserted = 0
    for sequence_no, value in enumerate(parties, start=1):
        party = _mapping(value, f"record.parties[{sequence_no - 1}]")
        raw_name = _text(party.get("name"))
        role = _text(party.get("role")) or "other"
        if not raw_name:
            continue
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET normalized_name=excluded.normalized_name
            """,
            (
                instrument_id,
                sequence_no,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
            ),
        )
        parties_upserted += 1

    legal_values = record.get("legal_descriptions", [])
    if not isinstance(legal_values, list):
        raise PropertyIngestError("record.legal_descriptions must be a list")
    legal_description_raw = canonical_json(legal_values) if legal_values else None
    normalized_values = record.get("parcel_ids_normalized", [])
    raw_values = record.get("parcel_ids", [])
    if not isinstance(normalized_values, list) or not isinstance(raw_values, list):
        raise PropertyIngestError(
            "Palm Beach parcel_ids and parcel_ids_normalized must be lists"
        )
    effective_from = _date_prefix(record.get("recording_date")) or retrieved_at
    parcel_ids: set[int] = set()
    placeholders_created = 0
    aliases_inserted = 0
    sales_upserted = 0
    for index, raw_normalized in enumerate(normalized_values):
        native_parcel_id = _text(raw_normalized)
        if not native_parcel_id:
            continue
        parcel_id = _existing_palm_beach_parcel(
            db,
            native_parcel_id=native_parcel_id,
        )
        if parcel_id is None:
            parcel_id = _upsert_parcel_snapshot(
                db,
                source_id=PALM_BEACH_RECORDER_SOURCE_ID,
                jurisdiction_geoid="12099",
                native_parcel_id=native_parcel_id,
                roll_year="",
                effective_from=None,
                source_good_through=None,
                observation_id=observation_id,
                record={
                    "native_parcel_id": native_parcel_id,
                    "placeholder_state": (
                        "recorder_pcn_pending_property_appraiser_or_dor_roll"
                    ),
                    "source_instrument_number": instrument_number,
                },
            )
            placeholders_created += 1
        parcel_ids.add(parcel_id)
        raw_parcel_id = _text(raw_values[index]) if index < len(raw_values) else None
        if raw_parcel_id:
            aliases_inserted += _upsert_alias(
                db,
                parcel_id=parcel_id,
                alias_type="palm_beach_pcn",
                alias_value=raw_parcel_id,
                source_id=source_id,
                effective_from=effective_from,
            )
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, 'exact_source_index_pcn', 1.0, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=excluded.legal_description_raw
            """,
            (instrument_id, parcel_id, legal_description_raw),
        )
        if (_text(record.get("document_type")) or "").upper() == "DEED":
            sales_upserted += _upsert_sale_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                native_sale_id=instrument_number,
                sale_date=_date_prefix(record.get("recording_date")),
                consideration=record.get("consideration"),
                derivation="recorded_instrument_index",
                instrument_id=instrument_id,
                observation_id=observation_id,
                raw=record,
                recording_date=_date_prefix(record.get("recording_date")),
            )

    image_access = record.get("image_access")
    artifacts_upserted = 0
    image_artifact_id = None
    if isinstance(image_access, Mapping):
        raw_page_count = image_access.get("online_page_count")
        try:
            page_count = (
                int(raw_page_count) if raw_page_count not in (None, "") else None
            )
        except (TypeError, ValueError):
            page_count = None
        available = _text(image_access.get("status")) == "available_online"
        image_artifact_id = _upsert_palm_beach_artifact(
            db,
            native_document_id=f"{portal_document_id}:online-image-set",
            instrument_id=instrument_id,
            sha256=None,
            mime_type=_text(image_access.get("media_type_observed")),
            page_count=page_count,
            storage_path=None,
            source_url=_text(image_access.get("endpoint")),
            acquisition_method="source_image_availability_metadata",
            access_state="public" if available else "unknown",
            acquired_at=None,
        )
        artifacts_upserted = 1

    return {
        "instrument_id": instrument_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            "12099",
            "instrument",
            instrument_number,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "official_instrument_number": instrument_number,
        "portal_document_id": portal_document_id,
        "parties_upserted": parties_upserted,
        "parcels_linked": len(parcel_ids),
        "parcel_placeholders_created": placeholders_created,
        "aliases_inserted": aliases_inserted,
        "sales_upserted": sales_upserted,
        "artifacts_upserted": artifacts_upserted,
        "image_artifact_id": image_artifact_id,
        "ownership_assertions_upserted": 0,
    }


def _upsert_broward_artifact(
    db,
    *,
    native_document_id: str,
    instrument_id: int,
    sha256: str | None,
    mime_type: str | None,
    page_count: int | None,
    storage_path: str | None,
    source_url: str | None,
    acquisition_method: str,
    rights_tier: str,
    access_state: str,
    acquired_at: str | None,
) -> int:
    if access_state not in {
        "public",
        "restricted",
        "sealed",
        "expunged",
        "removed",
        "redacted",
        "unknown",
    }:
        access_state = "unknown"
    existing = db.execute(
        """
        SELECT artifact_id
        FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid='12011'
          AND native_document_id=?
          AND COALESCE(sha256, '')=COALESCE(?, '')
        """,
        (BROWARD_RECORDER_SOURCE_ID, native_document_id, sha256),
    ).fetchone()
    values = (
        instrument_id,
        sha256,
        mime_type,
        page_count,
        storage_path,
        source_url,
        acquisition_method,
        rights_tier,
        access_state,
        acquired_at,
    )
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, '12011', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                BROWARD_RECORDER_SOURCE_ID,
                native_document_id,
                *values,
            ),
        )
        return int(cursor.lastrowid)
    artifact_id = int(existing["artifact_id"])
    db.execute(
        """
        UPDATE document_artifact SET
            instrument_id=?, sha256=?, mime_type=?, page_count=?,
            storage_path=?, source_url=?, acquisition_method=?,
            rights_tier=?, access_state=?, acquired_at=?
        WHERE artifact_id=?
        """,
        (*values, artifact_id),
    )
    return artifact_id


def _broward_instrument_id(
    db,
    *,
    instrument_number: str,
    observation_id: int,
    record: Mapping[str, Any],
    update_metadata: bool,
) -> int:
    existing = db.execute(
        """
        SELECT instrument_id
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid='12011'
          AND native_document_id=?
        """,
        (BROWARD_RECORDER_SOURCE_ID, instrument_number),
    ).fetchone()
    if existing is not None and not update_metadata:
        return int(existing["instrument_id"])

    legal_values = record.get("legal_descriptions", [])
    if not isinstance(legal_values, list):
        raise PropertyIngestError("Broward legal_descriptions must be a list")
    legal_description_raw = canonical_json(legal_values) if legal_values else None
    db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id,
            instrument_type, book, page, execution_date, recording_date,
            consideration_minor, currency, legal_description_raw, source_url,
            observation_id, raw_json
        ) VALUES (?, '12011', ?, ?, ?, ?, NULL, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
        DO UPDATE SET
            instrument_type=COALESCE(
                excluded.instrument_type, recorded_instrument.instrument_type
            ),
            book=COALESCE(excluded.book, recorded_instrument.book),
            page=COALESCE(excluded.page, recorded_instrument.page),
            recording_date=COALESCE(
                excluded.recording_date, recorded_instrument.recording_date
            ),
            consideration_minor=COALESCE(
                excluded.consideration_minor,
                recorded_instrument.consideration_minor
            ),
            legal_description_raw=COALESCE(
                excluded.legal_description_raw,
                recorded_instrument.legal_description_raw
            ),
            source_url=COALESCE(
                excluded.source_url, recorded_instrument.source_url
            ),
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            BROWARD_RECORDER_SOURCE_ID,
            instrument_number,
            _text(record.get("document_type"))
            or _text(record.get("document_type_code")),
            _text(record.get("book")),
            _text(record.get("page")),
            _date_prefix(record.get("recording_date")),
            _minor_units(record.get("consideration")),
            legal_description_raw,
            _record_source_url({}, record),
            observation_id,
            canonical_json(record),
        ),
    )
    row = db.execute(
        """
        SELECT instrument_id
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid='12011'
          AND native_document_id=?
        """,
        (BROWARD_RECORDER_SOURCE_ID, instrument_number),
    ).fetchone()
    return int(row["instrument_id"])


def _existing_broward_parcel(
    db,
    *,
    native_parcel_id: str,
) -> int | None:
    row = db.execute(
        """
        SELECT p.parcel_id
        FROM parcel_snapshot p
        WHERE p.jurisdiction_geoid='12011'
          AND (
            p.native_parcel_id=?
            OR EXISTS(
                SELECT 1
                FROM parcel_alias pa
                WHERE pa.parcel_id=p.parcel_id
                  AND pa.alias_value=?
            )
          )
        ORDER BY
            CASE WHEN p.roll_year='' THEN 1 ELSE 0 END,
            p.roll_year DESC,
            p.parcel_id DESC
        LIMIT 1
        """,
        (native_parcel_id, native_parcel_id),
    ).fetchone()
    return int(row["parcel_id"]) if row else None


def _broward_legal_for_parcel(
    legal_values: Sequence[Any],
    parcel_id: str,
) -> str | None:
    selected: list[Any] = []
    for value in legal_values:
        if isinstance(value, Mapping):
            linked_parcel = _text(value.get("parcel_id"))
            if linked_parcel and linked_parcel != parcel_id:
                continue
            selected.append(dict(value))
        elif _text(value):
            selected.append(_text(value))
    return canonical_json(selected) if selected else None


def _ingest_broward_recorder_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project Broward instrument-index rows and document artifacts."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    instrument_number = _text(
        record.get("instrument_number") or record.get("native_document_id")
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    observation_sha256 = (
        _text(record.get("sha256"))
        if record_kind == "recorded_document_artifact"
        else raw_artifact_sha256
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=(
            _text(record.get("evidence_ref"))
            or instrument_number
            or _text(record.get("native_document_id"))
        ),
        record_kind=record_kind or "source_row",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=observation_sha256,
        warnings=warnings,
    )
    if record_kind not in {
        "recorded_instrument",
        "recorded_document_artifact",
    }:
        return {
            "projection_skipped": True,
            "reason": "broward_non_instrument_record",
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "record_kind": record_kind,
        }
    if not instrument_number or not instrument_number.isdigit():
        raise PropertyIngestError(
            "Broward Official Records record lacks a numeric instrument number"
        )

    jurisdiction_geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="12011",
        fallback_name="Broward County, Florida",
        fallback_state_code="FL",
    )
    if jurisdiction_geoid != "12011":
        raise PropertyIngestError(
            "Broward Official Records record is outside GEOID 12011"
        )
    instrument_id = _broward_instrument_id(
        db,
        instrument_number=instrument_number,
        observation_id=observation_id,
        record=record,
        update_metadata=record_kind == "recorded_instrument",
    )

    if record_kind == "recorded_document_artifact":
        digest = _text(record.get("sha256"))
        if not digest:
            raise PropertyIngestError(
                "Broward downloaded document artifact lacks sha256"
            )
        artifact_id = _upsert_broward_artifact(
            db,
            native_document_id=_text(record.get("native_document_id"))
            or instrument_number,
            instrument_id=instrument_id,
            sha256=digest,
            mime_type=_text(record.get("mime_type")),
            page_count=(
                int(record["page_count"])
                if record.get("page_count") not in (None, "")
                else None
            ),
            storage_path=_text(record.get("storage_path")),
            source_url=_record_source_url(envelope, record),
            acquisition_method="browser_session_pdf_download",
            rights_tier=_text(record.get("certification_status"))
            or "official_public_record_uncertified",
            access_state="public",
            acquired_at=retrieved_at,
        )
        return {
            "instrument_id": instrument_id,
            "artifact_id": artifact_id,
            "canonical_ref": _text(record.get("canonical_ref")),
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "official_instrument_number": instrument_number,
            "artifacts_upserted": 1,
        }

    parties = record.get("parties", [])
    if not isinstance(parties, list):
        raise PropertyIngestError("Broward record.parties must be a list")
    parties_upserted = 0
    for index, party_value in enumerate(parties, start=1):
        party = _mapping(party_value, f"record.parties[{index - 1}]")
        raw_name = _text(party.get("name"))
        if not raw_name:
            continue
        raw_sequence = party.get("sequence")
        try:
            sequence_no = int(raw_sequence) if raw_sequence not in (None, "") else index
        except (TypeError, ValueError):
            sequence_no = index
        role = (
            _text(party.get("role"))
            or _text(party.get("native_role"))
            or "indexed_party"
        )
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET normalized_name=excluded.normalized_name
            """,
            (
                instrument_id,
                sequence_no,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
            ),
        )
        parties_upserted += 1

    legal_values = record.get("legal_descriptions", [])
    parcel_values = record.get("parcel_ids", [])
    if not isinstance(legal_values, list) or not isinstance(
        parcel_values,
        list,
    ):
        raise PropertyIngestError(
            "Broward legal_descriptions and parcel_ids must be lists"
        )
    linked_parcels: set[int] = set()
    parcel_stubs_created = 0
    effective_from = _date_prefix(record.get("recording_date"))
    for value in parcel_values:
        native_parcel_id = _text(value)
        if not native_parcel_id:
            continue
        parcel_id = _existing_broward_parcel(
            db,
            native_parcel_id=native_parcel_id,
        )
        if parcel_id is None:
            parcel_id = _upsert_parcel_snapshot(
                db,
                source_id=source_id,
                jurisdiction_geoid="12011",
                native_parcel_id=native_parcel_id,
                roll_year="",
                effective_from=effective_from,
                source_good_through=None,
                observation_id=observation_id,
                record={
                    "native_parcel_id": native_parcel_id,
                    "record_scope": "recorder_index_locator",
                },
            )
            parcel_stubs_created += 1
        linked_parcels.add(parcel_id)
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, 'exact_source_index_parcel_id', 1.0, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=excluded.legal_description_raw
            """,
            (
                instrument_id,
                parcel_id,
                _broward_legal_for_parcel(
                    legal_values,
                    native_parcel_id,
                ),
            ),
        )

    artifact_ids: list[int] = []
    image_access = record.get("image_access")
    if isinstance(image_access, Mapping):
        image_status = _text(image_access.get("status"))
        if image_status == "available_online":
            raw_page_count = image_access.get("page_count")
            try:
                page_count = (
                    int(raw_page_count) if raw_page_count not in (None, "") else None
                )
            except (TypeError, ValueError):
                page_count = None
            artifact_ids.append(
                _upsert_broward_artifact(
                    db,
                    native_document_id=f"{instrument_number}:online-pdf",
                    instrument_id=instrument_id,
                    sha256=None,
                    mime_type=_text(image_access.get("mime_type")) or "application/pdf",
                    page_count=page_count,
                    storage_path=None,
                    source_url=_text(record.get("detail_source_url"))
                    or _record_source_url(envelope, record),
                    acquisition_method=("browser_session_image_availability_metadata"),
                    rights_tier="official_public_record_uncertified",
                    access_state="public",
                    acquired_at=None,
                )
            )
        members = image_access.get("members", [])
        if isinstance(members, list):
            for index, member_value in enumerate(members):
                member = _mapping(
                    member_value,
                    f"record.image_access.members[{index}]",
                )
                native_artifact_id = _text(member.get("native_artifact_id"))
                if not native_artifact_id:
                    continue
                artifact_ids.append(
                    _upsert_broward_artifact(
                        db,
                        native_document_id=native_artifact_id,
                        instrument_id=instrument_id,
                        sha256=None,
                        mime_type=_text(member.get("mime_type")) or "image/tiff",
                        page_count=1,
                        storage_path=None,
                        source_url=_record_source_url(envelope, record),
                        acquisition_method=("official_daily_zip_member_metadata"),
                        rights_tier=("official_public_record_uncertified"),
                        access_state="public",
                        acquired_at=None,
                    )
                )

    return {
        "instrument_id": instrument_id,
        "canonical_ref": _text(record.get("canonical_ref"))
        or canonical_property_ref(
            source_id,
            "12011",
            "instrument",
            instrument_number,
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "official_instrument_number": instrument_number,
        "parties_upserted": parties_upserted,
        "parcels_linked": len(linked_parcels),
        "parcel_stubs_created": parcel_stubs_created,
        "addresses_inserted": 0,
        "sales_upserted": 0,
        "ownership_assertions_upserted": 0,
        "artifacts_upserted": len(artifact_ids),
        "artifact_ids": artifact_ids,
    }


WASHINGTON_LAND_PARCEL_LINK_METHODS = frozenset(
    {
        "exact_current_parcel_or_alias",
        "unique_punctuation_normalized_current_parcel_or_alias",
    }
)


def _washington_land_jurisdiction(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
) -> str:
    """Resolve one archive record to a single verified Washington county."""

    query = _mapping(envelope.get("query"), "query")
    query_jurisdiction = _mapping(
        query.get("jurisdiction"),
        "query.jurisdiction",
    )
    candidates: set[str] = set()
    envelope_geoid = _text(query_jurisdiction.get("jurisdiction_id"))
    if envelope_geoid and len(envelope_geoid) == 5:
        candidates.add(envelope_geoid)
    record_geoid = _text(record.get("county_geoid"))
    if record_geoid:
        candidates.add(record_geoid)
    provenance = record.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    title_id_value = record.get("title_id") or provenance.get("title_id")
    try:
        title_id = int(title_id_value) if title_id_value not in (None, "") else None
    except (TypeError, ValueError) as error:
        raise PropertyIngestError(
            "Washington land record title_id must be numeric"
        ) from error
    title = (
        query_washington_digital_archives_land.TITLES_BY_ID.get(title_id)
        if title_id is not None
        else None
    )
    if title is not None:
        candidates.add(title.county_geoid)
    if len(candidates) != 1:
        raise PropertyIngestError(
            "Washington land record must resolve to exactly one county GEOID"
        )
    jurisdiction_geoid = next(iter(candidates))
    if (
        not jurisdiction_geoid.isdigit()
        or len(jurisdiction_geoid) != 5
        or not jurisdiction_geoid.startswith("53")
    ):
        raise PropertyIngestError(
            "Washington land record county GEOID must be a five-digit 53 code"
        )
    title_by_geoid = next(
        (
            candidate
            for candidate in query_washington_digital_archives_land.TITLES
            if candidate.county_geoid == jurisdiction_geoid
        ),
        None,
    )
    county_name = (
        f"{title_by_geoid.county} County"
        if title_by_geoid is not None
        else _text(record.get("county"))
        or _text(query_jurisdiction.get("locality"))
        or f"Washington county {jurisdiction_geoid}"
    )
    observed_county = _text(record.get("county"))
    if title_by_geoid is not None and observed_county:
        normalized_observed = re.sub(
            r"\s+county$",
            "",
            observed_county.strip(),
            flags=re.I,
        ).casefold()
        if normalized_observed != title_by_geoid.county.casefold():
            raise PropertyIngestError(
                "Washington land record county name conflicts with its GEOID"
            )
    return _upsert_jurisdiction_values(
        db,
        geoid=jurisdiction_geoid,
        name=county_name,
        state_code="WA",
        jurisdiction_type="county",
        parent_geoid="53",
    )


def _washington_land_legal(
    record: Mapping[str, Any],
    *,
    detail: bool,
) -> tuple[dict[str, Any], str | None]:
    if detail:
        value = record.get("legal")
        if not isinstance(value, Mapping):
            raise PropertyIngestError(
                "Washington land detail record.legal must be an object"
            )
        legal = dict(value)
    else:
        legal_description = _text(record.get("legal_description"))
        legal = (
            {"legal_description": legal_description}
            if legal_description is not None
            else {}
        )
    return legal, canonical_json(legal) if legal else None


def _washington_land_instrument_id(
    db,
    *,
    jurisdiction_geoid: str,
    record_id: str,
    record: Mapping[str, Any],
    observation_id: int,
    legal_description_raw: str | None,
    detail: bool,
) -> int:
    values = (
        WASHINGTON_LAND_RECORDS_SOURCE_ID,
        jurisdiction_geoid,
        record_id,
        _text(record.get("document_type")),
        _date_prefix(record.get("recording_date")) if detail else None,
        legal_description_raw,
        _text(record.get("record_url")) or _record_source_url({}, record),
        observation_id,
        canonical_json(record),
    )
    if detail:
        db.execute(
            """
            INSERT INTO recorded_instrument(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_type, book, page, execution_date, recording_date,
                consideration_minor, currency, legal_description_raw,
                source_url, observation_id, raw_json
            ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, 'USD', ?, ?, ?, ?)
            ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
            DO UPDATE SET
                instrument_type=COALESCE(
                    excluded.instrument_type,
                    recorded_instrument.instrument_type
                ),
                recording_date=COALESCE(
                    excluded.recording_date,
                    recorded_instrument.recording_date
                ),
                legal_description_raw=COALESCE(
                    excluded.legal_description_raw,
                    recorded_instrument.legal_description_raw
                ),
                source_url=COALESCE(
                    excluded.source_url,
                    recorded_instrument.source_url
                ),
                observation_id=excluded.observation_id,
                raw_json=excluded.raw_json
            """,
            values,
        )
    else:
        db.execute(
            """
            INSERT INTO recorded_instrument(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_type, book, page, execution_date, recording_date,
                consideration_minor, currency, legal_description_raw,
                source_url, observation_id, raw_json
            ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, 'USD', ?, ?, ?, ?)
            ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
            DO UPDATE SET
                instrument_type=COALESCE(
                    recorded_instrument.instrument_type,
                    excluded.instrument_type
                ),
                legal_description_raw=COALESCE(
                    recorded_instrument.legal_description_raw,
                    excluded.legal_description_raw
                ),
                source_url=COALESCE(
                    recorded_instrument.source_url,
                    excluded.source_url
                )
            """,
            values,
        )
    row = db.execute(
        """
        SELECT instrument_id
        FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (
            WASHINGTON_LAND_RECORDS_SOURCE_ID,
            jurisdiction_geoid,
            record_id,
        ),
    ).fetchone()
    return int(row["instrument_id"])


def _washington_land_party_name(party: Mapping[str, Any]) -> str | None:
    first = _text(party.get("first_name"))
    middle = _text(party.get("middle_name"))
    last = _text(party.get("last_name"))
    given = " ".join(value for value in (first, middle) if value)
    if last and given:
        return f"{last}, {given}"
    return last or given


def _washington_land_parties(
    record: Mapping[str, Any],
) -> list[tuple[int, str, str]]:
    values = record.get("parties")
    if not isinstance(values, list):
        raise PropertyIngestError(
            "Washington land detail record.parties must be a list"
        )
    parties: list[tuple[int, str, str]] = []
    sequences: set[int] = set()
    for index, value in enumerate(values, start=1):
        party = _mapping(value, f"record.parties[{index - 1}]")
        raw_sequence = party.get("sequence_no")
        try:
            sequence_no = (
                int(raw_sequence) if raw_sequence not in (None, "") else index
            )
        except (TypeError, ValueError) as error:
            raise PropertyIngestError(
                "Washington land party sequence_no must be numeric"
            ) from error
        if sequence_no <= 0 or sequence_no in sequences:
            raise PropertyIngestError(
                "Washington land party sequence_no values must be unique and positive"
            )
        sequences.add(sequence_no)
        raw_name = _washington_land_party_name(party)
        if not raw_name:
            continue
        parties.append(
            (
                sequence_no,
                _text(party.get("party_type")) or "indexed_party",
                raw_name,
            )
        )
    return parties


def _washington_land_parcel_candidates(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    candidates: list[str] = []
    for raw_value in values:
        text = _text(raw_value)
        if not text:
            continue
        for candidate in re.split(r"[;|,\n]+", text):
            candidate = candidate.strip()
            if candidate and re.search(r"[A-Za-z0-9]", candidate):
                candidates.append(candidate)
    return list(dict.fromkeys(candidates))


def _washington_land_parcel_resolution(
    db,
    *,
    jurisdiction_geoid: str,
    candidate: str,
) -> tuple[tuple[int, str, float] | None, str]:
    rows = db.execute(
        """
        SELECT p.parcel_id, p.native_parcel_id AS identifier
        FROM parcel_snapshot p
        WHERE p.jurisdiction_geoid=? AND p.effective_to IS NULL
        UNION ALL
        SELECT p.parcel_id, a.alias_value AS identifier
        FROM parcel_snapshot p
        JOIN parcel_alias a ON a.parcel_id=p.parcel_id
        WHERE p.jurisdiction_geoid=?
          AND p.effective_to IS NULL
          AND a.effective_to IS NULL
        """,
        (jurisdiction_geoid, jurisdiction_geoid),
    ).fetchall()
    exact_ids = {
        int(row["parcel_id"])
        for row in rows
        if (_text(row["identifier"]) or "").casefold() == candidate.casefold()
    }
    if len(exact_ids) == 1:
        return (
            (
                next(iter(exact_ids)),
                "exact_current_parcel_or_alias",
                1.0,
            ),
            "exact",
        )
    if len(exact_ids) > 1:
        return None, "multiple_exact"
    normalized_candidate = re.sub(r"[^A-Za-z0-9]+", "", candidate).casefold()
    if not normalized_candidate:
        return None, "empty_normalized"
    normalized_ids = {
        int(row["parcel_id"])
        for row in rows
        if re.sub(
            r"[^A-Za-z0-9]+",
            "",
            _text(row["identifier"]) or "",
        ).casefold()
        == normalized_candidate
    }
    if len(normalized_ids) == 1:
        return (
            (
                next(iter(normalized_ids)),
                "unique_punctuation_normalized_current_parcel_or_alias",
                0.95,
            ),
            "unique_normalized",
        )
    if len(normalized_ids) > 1:
        return None, "multiple_normalized"
    return None, "no_match"


def _upsert_washington_land_artifact(
    db,
    *,
    jurisdiction_geoid: str,
    instrument_id: int,
    digital_object: Mapping[str, Any],
    record: Mapping[str, Any],
) -> int:
    object_id = _text(digital_object.get("native_digital_object_id"))
    if not object_id:
        raise PropertyIngestError(
            "Washington listed digital object lacks its native identifier"
        )
    existing = db.execute(
        """
        SELECT artifact_id
        FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_document_id=? AND sha256 IS NULL
          AND acquisition_method='site_recaptcha_queue_metadata'
        ORDER BY artifact_id DESC
        LIMIT 1
        """,
        (
            WASHINGTON_LAND_RECORDS_SOURCE_ID,
            jurisdiction_geoid,
            object_id,
        ),
    ).fetchone()
    object_format = (_text(digital_object.get("format")) or "").upper()
    mime_type = {
        "PDF": "application/pdf",
        "TIFF": "image/tiff",
        "TIF": "image/tiff",
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
    }.get(object_format)
    values = (
        instrument_id,
        mime_type,
        _text(record.get("record_url")) or _record_source_url({}, record),
    )
    if existing is None:
        cursor = db.execute(
            """
            INSERT INTO document_artifact(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_id, sha256, mime_type, page_count, storage_path,
                source_url, acquisition_method, rights_tier, access_state,
                acquired_at
            ) VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL, ?,
                      'site_recaptcha_queue_metadata',
                      'official_archive_image_uncertified', 'public', NULL)
            """,
            (
                WASHINGTON_LAND_RECORDS_SOURCE_ID,
                jurisdiction_geoid,
                object_id,
                *values,
            ),
        )
        return int(cursor.lastrowid)
    artifact_id = int(existing["artifact_id"])
    db.execute(
        """
        UPDATE document_artifact SET
            instrument_id=?, sha256=NULL, mime_type=?, page_count=NULL,
            storage_path=NULL, source_url=?,
            acquisition_method='site_recaptcha_queue_metadata',
            rights_tier='official_archive_image_uncertified',
            access_state='public', acquired_at=NULL
        WHERE artifact_id=?
        """,
        (*values, artifact_id),
    )
    return artifact_id


def _ingest_washington_land_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Preserve index occurrences and enrich one county-scoped instrument."""

    _assert_record_source(record, source_id)
    provenance = record.get("provenance")
    if isinstance(provenance, Mapping):
        provenance_source = _text(provenance.get("source_id"))
        if provenance_source and provenance_source != source_id:
            raise PropertyIngestError(
                "Washington land record provenance source does not match envelope"
            )
    record_kind = _text(record.get("record_kind"))
    is_search = record_kind == "recorded_land_search_result"
    is_detail = record_kind == "recorded_land_record"
    record_id = _text(record.get("native_record_id"))
    occurrence_id = _text(
        record.get("source_occurrence_id")
        or record.get("query_occurrence_id")
    )
    if is_search and not occurrence_id:
        raise PropertyIngestError(
            "Washington index row lacks its query-bound occurrence identifier"
        )
    source_native_id = occurrence_id if is_search else record_id
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    schema_fingerprint = _record_schema_fingerprint(record)
    if schema_fingerprint is None and isinstance(provenance, Mapping):
        schema_fingerprint = _text(provenance.get("schema_fingerprint"))
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind=record_kind or "source_row",
        query_fingerprint=query_fingerprint,
        source_url=_text(record.get("record_url"))
        or _record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=schema_fingerprint,
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    if not (is_search or is_detail):
        return {
            "projection_skipped": True,
            "reason": "washington_land_non_instrument_record",
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "record_kind": record_kind,
        }
    if not record_id or not re.fullmatch(r"[A-Fa-f0-9]{32}", record_id):
        raise PropertyIngestError(
            "Washington land record lacks its 32-hex archive record identifier"
        )
    record_id = record_id.upper()
    jurisdiction_geoid = _washington_land_jurisdiction(
        db,
        envelope=envelope,
        record=record,
    )
    legal, legal_description_raw = _washington_land_legal(
        record,
        detail=is_detail,
    )
    instrument_id = _washington_land_instrument_id(
        db,
        jurisdiction_geoid=jurisdiction_geoid,
        record_id=record_id,
        record=record,
        observation_id=observation_id,
        legal_description_raw=legal_description_raw,
        detail=is_detail,
    )
    canonical_ref = canonical_property_ref(
        source_id,
        jurisdiction_geoid,
        "instrument",
        record_id,
    )
    if is_search:
        return {
            "instrument_id": instrument_id,
            "canonical_ref": canonical_ref,
            "observation_id": observation_id,
            "record_sha256": record_hash,
            "source_occurrence_id": occurrence_id,
            "record_kind": record_kind,
            "parties_upserted": 0,
            "parcel_links_upserted": 0,
            "parcel_placeholders_created": 0,
            "ownership_assertions_upserted": 0,
            "artifacts_upserted": 0,
        }

    parties = _washington_land_parties(record)
    db.execute(
        "DELETE FROM instrument_party WHERE instrument_id=?",
        (instrument_id,),
    )
    for sequence_no, role, raw_name in parties:
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                instrument_id,
                sequence_no,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
            ),
        )

    placeholders = ",".join("?" for _ in WASHINGTON_LAND_PARCEL_LINK_METHODS)
    db.execute(
        f"""
        DELETE FROM instrument_parcel
        WHERE instrument_id=? AND link_method IN ({placeholders})
        """,
        (instrument_id, *sorted(WASHINGTON_LAND_PARCEL_LINK_METHODS)),
    )
    parcel_resolution_states: dict[str, str] = {}
    linked_parcels: set[int] = set()
    for candidate in _washington_land_parcel_candidates(legal.get("parcel")):
        resolution, state = _washington_land_parcel_resolution(
            db,
            jurisdiction_geoid=jurisdiction_geoid,
            candidate=candidate,
        )
        parcel_resolution_states[candidate] = state
        if resolution is None:
            continue
        parcel_id, link_method, confidence = resolution
        linked_parcels.add(parcel_id)
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=excluded.legal_description_raw
            """,
            (
                instrument_id,
                parcel_id,
                link_method,
                confidence,
                legal_description_raw,
            ),
        )

    digital_objects = record.get("digital_objects")
    if not isinstance(digital_objects, list):
        raise PropertyIngestError(
            "Washington land detail digital_objects must be a list"
        )
    listed_ids = {
        object_id
        for value in digital_objects
        if isinstance(value, Mapping)
        and (object_id := _text(value.get("native_digital_object_id")))
    }
    existing_metadata = db.execute(
        """
        SELECT artifact_id, native_document_id
        FROM document_artifact
        WHERE source_id=? AND jurisdiction_geoid=? AND instrument_id=?
          AND acquisition_method='site_recaptcha_queue_metadata'
        """,
        (
            WASHINGTON_LAND_RECORDS_SOURCE_ID,
            jurisdiction_geoid,
            instrument_id,
        ),
    ).fetchall()
    for existing in existing_metadata:
        if existing["native_document_id"] not in listed_ids:
            db.execute(
                "DELETE FROM document_artifact WHERE artifact_id=?",
                (int(existing["artifact_id"]),),
            )
    artifact_ids = [
        _upsert_washington_land_artifact(
            db,
            jurisdiction_geoid=jurisdiction_geoid,
            instrument_id=instrument_id,
            digital_object=_mapping(
                value,
                f"record.digital_objects[{index}]",
            ),
            record=record,
        )
        for index, value in enumerate(digital_objects)
    ]
    return {
        "instrument_id": instrument_id,
        "canonical_ref": canonical_ref,
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "record_kind": record_kind,
        "parties_upserted": len(parties),
        "parties_reconciled": True,
        "parcel_links_upserted": len(linked_parcels),
        "parcel_resolution_states": parcel_resolution_states,
        "parcel_placeholders_created": 0,
        "ownership_assertions_upserted": 0,
        "artifacts_upserted": len(artifact_ids),
        "artifact_ids": artifact_ids,
        "digital_object_delivery_state": _text(
            _mapping(
                record.get("document_delivery"),
                "record.document_delivery",
            ).get("state")
        ),
    }


def _taxsifter_tenant(source_id: str) -> Any:
    tenant = query_washington_taxsifter.TENANTS_BY_SOURCE.get(source_id)
    if tenant is None:
        raise PropertyIngestError(f"unknown Washington TaxSifter source {source_id}")
    return tenant


def _taxsifter_date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    for date_format in (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y",
        "%m/%d/%y",
    ):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _taxsifter_money_amount(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get("amount")
    if value in (None, ""):
        return None
    return value


def _taxsifter_row_money(
    row: Mapping[str, Any],
    *field_names: str,
) -> Any:
    for field_name in field_names:
        value = row.get(field_name)
        amount = _taxsifter_money_amount(value)
        if amount not in (None, ""):
            return amount
    return None


def _taxsifter_account_occurrence(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, str]:
    occurrence = _mapping(
        record.get("account_occurrence"),
        "record.account_occurrence",
    )
    occurrence_source = _text(occurrence.get("source_id"))
    key_id = _text(occurrence.get("key_id"))
    type_id = _text(occurrence.get("type_id"))
    native_id = _text(occurrence.get("native_id"))
    if occurrence_source != source_id:
        raise PropertyIngestError(
            "TaxSifter account occurrence source does not match its leaf source"
        )
    if not key_id or not type_id:
        raise PropertyIngestError(
            "TaxSifter account occurrence requires keyId and typeID"
        )
    expected_native_id = f"keyId={key_id};typeID={type_id}"
    if native_id != expected_native_id:
        raise PropertyIngestError(
            "TaxSifter account occurrence native_id does not match keyId/typeID"
        )
    return {
        "source_id": source_id,
        "key_id": key_id,
        "type_id": type_id,
        "native_id": expected_native_id,
    }


def _taxsifter_parcel_identity(
    record: Mapping[str, Any],
    *,
    source_id: str,
    require_join: bool,
) -> tuple[Any, str]:
    tenant = _taxsifter_tenant(source_id)
    county_geoid = _text(record.get("county_geoid"))
    if county_geoid != tenant.county_geoid:
        raise PropertyIngestError(
            f"{source_id} TaxSifter record has county GEOID {county_geoid!r}; "
            f"expected {tenant.county_geoid}"
        )
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        raise PropertyIngestError("TaxSifter record lacks its parcel number")
    parcel_join = record.get("parcel_join")
    if require_join or parcel_join is not None:
        join = _mapping(parcel_join, "record.parcel_join")
        if (
            _text(join.get("county_geoid")) != tenant.county_geoid
            or _text(join.get("parcel_number")) != native_parcel_id
        ):
            raise PropertyIngestError(
                "TaxSifter county/parcel join does not match the leaf record"
            )
    return tenant, native_parcel_id


def _taxsifter_representation_consistency(
    representation: Mapping[str, Any],
    *,
    source_id: str,
    county_geoid: str,
    native_parcel_id: str,
    account_occurrence: Mapping[str, str],
) -> None:
    if _text(representation.get("source_id")) != source_id:
        raise PropertyIngestError(
            "TaxSifter detail representation source differs from its bundle"
        )
    if _text(representation.get("county_geoid")) != county_geoid:
        raise PropertyIngestError(
            "TaxSifter detail representation county differs from its bundle"
        )
    if _text(representation.get("native_parcel_id")) != native_parcel_id:
        raise PropertyIngestError(
            "TaxSifter detail representation parcel differs from its bundle"
        )
    observed_occurrence = _taxsifter_account_occurrence(
        representation,
        source_id=source_id,
    )
    if observed_occurrence != dict(account_occurrence):
        raise PropertyIngestError(
            "TaxSifter detail representations identify different accounts"
        )
    _taxsifter_parcel_identity(
        representation,
        source_id=source_id,
        require_join=True,
    )


def _taxsifter_assessment_history(
    assessor: Mapping[str, Any],
) -> list[dict[str, Any]]:
    provenance = (
        dict(assessor["provenance"])
        if isinstance(assessor.get("provenance"), Mapping)
        else {}
    )
    data_current_as = _taxsifter_date(provenance.get("data_current_as"))
    records_by_year: dict[str, dict[str, Any]] = {}
    valuation_history = assessor.get("valuation_history")
    if isinstance(valuation_history, list):
        for value in valuation_history:
            if not isinstance(value, Mapping):
                continue
            year = _text(value.get("year") or value.get("tax_year"))
            if not year:
                continue
            records_by_year[year] = {
                "tax_year": year,
                "land_value": _taxsifter_row_money(
                    value,
                    "land_money",
                    "land_value_money",
                ),
                "improvement_value": _taxsifter_row_money(
                    value,
                    "impr_money",
                    "improvements_money",
                    "improvement_value_money",
                ),
                "parcel_value": _taxsifter_row_money(
                    value,
                    "total_money",
                    "market_value_money",
                ),
                "market_value": _taxsifter_row_money(
                    value,
                    "total_money",
                    "market_value_money",
                ),
                "taxable_value": _taxsifter_row_money(
                    value,
                    "taxable_money",
                    "taxable_value_money",
                ),
                "value_basis": "assessor_valuation_history_market_value",
                "effective_date": data_current_as,
                "source_row": dict(value),
            }

    market_value = assessor.get("market_value")
    if isinstance(market_value, Mapping):
        fields = market_value.get("fields")
        fields = fields if isinstance(fields, Mapping) else {}
        taxable_value = assessor.get("taxable_value")
        taxable_fields = (
            taxable_value.get("fields")
            if isinstance(taxable_value, Mapping)
            else {}
        )
        taxable_fields = taxable_fields if isinstance(taxable_fields, Mapping) else {}
        year = _text(
            market_value.get("tax_year")
            or provenance.get("roll_year")
        )
        if year:
            records_by_year[year] = {
                "tax_year": year,
                "land_value": _taxsifter_money_amount(fields.get("land")),
                "improvement_value": _taxsifter_money_amount(
                    fields.get("improvements") or fields.get("improvement")
                ),
                "parcel_value": _taxsifter_money_amount(fields.get("total")),
                "market_value": _taxsifter_money_amount(fields.get("total")),
                "taxable_value": _taxsifter_money_amount(
                    taxable_fields.get("total")
                ),
                "value_basis": "assessor_current_market_value",
                "taxable_value_basis": (
                    "assessor_taxable_value_preserved_separately"
                ),
                "effective_date": data_current_as,
                "market_value_source": dict(market_value),
                "taxable_value_source": (
                    dict(taxable_value)
                    if isinstance(taxable_value, Mapping)
                    else {}
                ),
            }
    return list(records_by_year.values())


def _taxsifter_assessor_owners(
    assessor: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_names: list[str] = []
    parcel = assessor.get("parcel")
    if isinstance(parcel, Mapping):
        owner_name = _text(parcel.get("owner_name"))
        if owner_name:
            raw_names.append(owner_name)
    ownership = assessor.get("ownership")
    if isinstance(ownership, list):
        for value in ownership:
            if not isinstance(value, Mapping):
                continue
            owner_name = _text(
                value.get("owner_s_name")
                or value.get("owner_name")
                or value.get("name")
            )
            if owner_name:
                raw_names.append(owner_name)
    return [
        {"raw_name": raw_name, "confidence": "high"}
        for raw_name in dict.fromkeys(raw_names)
    ]


def _taxsifter_projection_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
    assessor: Mapping[str, Any] | None,
    account_occurrence: Mapping[str, str] | None,
    complete: bool,
) -> dict[str, Any]:
    tenant, native_parcel_id = _taxsifter_parcel_identity(
        record,
        source_id=source_id,
        require_join=account_occurrence is not None,
    )
    source_record = assessor if assessor is not None else record
    provenance = (
        source_record.get("provenance")
        if isinstance(source_record.get("provenance"), Mapping)
        else {}
    )
    source_last_updated = _taxsifter_date(provenance.get("data_current_as"))
    roll_year = _text(provenance.get("roll_year"))
    projected: dict[str, Any] = {
        "source_id": source_id,
        "record_kind": record.get("record_kind"),
        "canonical_ref": record.get("canonical_ref"),
        "evidence_ref": record.get("evidence_ref"),
        "source_url": record.get("source_url"),
        "county_geoid": tenant.county_geoid,
        "native_parcel_id": native_parcel_id,
        "parcel_join": record.get("parcel_join"),
        "provenance": source_record.get("provenance"),
        "jurisdiction": {
            "state_code": "WA",
            "state_fips": "53",
            "county_name": tenant.county_name,
            "county_geoid": tenant.county_geoid,
        },
        "tax_year": roll_year,
        "source_last_updated": source_last_updated,
        "snapshot_complete": complete,
        "_taxsifter_source_record": dict(record),
    }
    if account_occurrence is not None:
        projected["source_occurrence_id"] = account_occurrence["native_id"]
        projected["account_occurrence"] = dict(account_occurrence)
        projected["taxsifter_account_occurrence"] = dict(account_occurrence)
    if assessor is None:
        projected["owners"] = []
        return projected

    parcel = assessor.get("parcel")
    parcel = parcel if isinstance(parcel, Mapping) else {}
    mailing = parcel.get("mailing_address")
    if isinstance(mailing, Mapping):
        projected["mailing_address"] = dict(mailing)
    situs = _text(parcel.get("situs_address"))
    if situs:
        projected["situs_address"] = {"raw": situs}
    map_number = _text(parcel.get("map_number"))
    if map_number and map_number != native_parcel_id:
        projected["alternate_parcel_ids"] = [map_number]
    projected["owners"] = _taxsifter_assessor_owners(assessor)
    projected["assessment_history"] = _taxsifter_assessment_history(assessor)
    projected["taxsifter_assessment_data"] = assessor.get("assessment_data")
    projected["taxsifter_appraisal_basis"] = {
        "lineage_id": query_washington_taxsifter.ASSESSOR_LINEAGE,
        "roll_year": roll_year,
        "data_current_as": source_last_updated,
    }
    return projected


def _taxsifter_account_alias(
    db,
    *,
    parcel_id: int,
    source_id: str,
    occurrence: Mapping[str, str],
    effective_from: str,
) -> int:
    return _upsert_alias(
        db,
        parcel_id=parcel_id,
        alias_type="taxsifter_account_occurrence",
        alias_value=occurrence["native_id"],
        source_id=source_id,
        effective_from=effective_from,
    )


def _taxsifter_sale_native_id(
    sale: Mapping[str, Any],
    identity: Mapping[str, Any] | None = None,
) -> str:
    native_id, computed_identity = query_washington_taxsifter._sale_identity(sale)
    if identity is not None:
        supplied_fingerprint = _text(identity.get("fingerprint"))
        if supplied_fingerprint != computed_identity["fingerprint"]:
            raise PropertyIngestError(
                "TaxSifter sale identity does not match its normalized fields"
            )
    return native_id


def _project_taxsifter_sale(
    db,
    *,
    parcel_id: int,
    source_id: str,
    sale: Mapping[str, Any],
    observation_id: int,
    derivation: str,
    identity: Mapping[str, Any] | None = None,
) -> int:
    price = _taxsifter_row_money(
        sale,
        "price_money",
        "sale_price_money",
        "consideration_money",
    )
    raw = {
        **dict(sale),
        "lineage_id": query_washington_taxsifter.ASSESSOR_LINEAGE,
        "derivation": derivation,
        "recording_join_state": "candidate_not_recorded_instrument_evidence",
    }
    return _upsert_sale_projection(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        native_sale_id=_taxsifter_sale_native_id(sale, identity),
        sale_date=_taxsifter_date(
            sale.get("sale_date_iso")
            or sale.get("sale_date")
            or sale.get("date")
        ),
        consideration=price,
        derivation=derivation,
        observation_id=observation_id,
        raw=raw,
        qualification_code=_text(
            sale.get("sale_type")
            or sale.get("qualification_code")
        ),
    )


def _taxsifter_event_native_id(
    row: Mapping[str, Any],
    *,
    prefix: str,
    candidates: Sequence[str],
) -> str:
    for field_name in candidates:
        value = _text(row.get(field_name))
        if value:
            return f"{prefix}:{value}"
    stable_row = {
        key: value
        for key, value in row.items()
        if key not in {"native_position", "links"}
    }
    return f"{prefix}:row-{sha256_fingerprint(stable_row)}"


def _project_taxsifter_treasurer(
    db,
    *,
    parcel_id: int,
    source_id: str,
    treasurer: Mapping[str, Any],
    observation_id: int,
    retrieved_at: str,
) -> tuple[int, int]:
    provenance = (
        treasurer.get("provenance")
        if isinstance(treasurer.get("provenance"), Mapping)
        else {}
    )
    tax_year = _text(treasurer.get("tax_year") or provenance.get("roll_year")) or ""
    effective_from = (
        _taxsifter_date(provenance.get("data_current_as")) or retrieved_at
    )
    evidence_ref = _text(treasurer.get("evidence_ref"))
    owner_names: list[str] = []
    events_upserted = 0
    event_specs = (
        (
            "current_tax_year",
            "tax_statement",
            ("statement_number", "statement"),
            (
                "total_tax_money",
                "net_tax_money",
                "gross_tax_money",
            ),
            None,
            "published_statement",
        ),
        (
            "balances_due",
            "tax_balance",
            ("statementid", "statement_id", "statement_number", "statement"),
            (
                "balance_s_due_money",
                "balance_due_money",
                "tax_amount_money",
            ),
            None,
            "balance_due",
        ),
        (
            "payment_receipts",
            "tax_payment_receipt",
            ("receipt_number",),
            (
                "total_paid_money",
                "taxes_fees_money",
            ),
            "receipt_date_iso",
            "paid",
        ),
    )
    for (
        field_name,
        event_type,
        id_fields,
        amount_fields,
        date_field,
        event_status,
    ) in event_specs:
        values = treasurer.get(field_name)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, Mapping):
                continue
            taxpayer = _text(value.get("taxpayer"))
            if taxpayer:
                owner_names.append(taxpayer)
            raw = {
                **dict(value),
                "lineage_id": query_washington_taxsifter.TREASURER_LINEAGE,
                "event_basis": field_name,
            }
            events_upserted += _upsert_tax_account_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                tax_year=tax_year,
                event_type=event_type,
                event_date=(
                    _taxsifter_date(value.get(date_field))
                    if date_field is not None
                    else None
                ),
                amount=_taxsifter_row_money(value, *amount_fields),
                status=_text(value.get("status")) or event_status,
                native_event_id=_taxsifter_event_native_id(
                    value,
                    prefix=event_type,
                    candidates=id_fields,
                ),
                observation_id=observation_id,
                raw=raw,
            )

    owners_upserted = 0
    for raw_name in dict.fromkeys(owner_names):
        owners_upserted += _upsert_tax_account_owner(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            raw_name=raw_name,
            effective_from=effective_from,
            observation_id=observation_id,
            evidence_ref=evidence_ref,
        )
    return events_upserted, owners_upserted


def _ingest_washington_taxsifter_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    """Project TaxSifter account, tax, value, and assessor-sale observations."""

    _assert_record_source(record, source_id)
    record_kind = _text(record.get("record_kind"))
    if record_kind == "property_search_result":
        occurrence = _taxsifter_account_occurrence(
            record,
            source_id=source_id,
        )
        projected = _taxsifter_projection_record(
            record,
            source_id=source_id,
            assessor=None,
            account_occurrence=occurrence,
            complete=False,
        )
        result = _ingest_assessor_record(
            db,
            envelope=envelope,
            record=projected,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            observation_kind="property_search_result",
        )
        result["account_occurrence_aliases_upserted"] = (
            _taxsifter_account_alias(
                db,
                parcel_id=int(result["parcel_id"]),
                source_id=source_id,
                occurrence=occurrence,
                effective_from=_text(envelope.get("retrieved_at")) or "",
            )
        )
        result["source_record_kind"] = record_kind
        return result

    if record_kind == "assessor_sale_search_result":
        native_parcel_value = _text(record.get("native_parcel_id"))
        if (
            not native_parcel_value
            or query_washington_taxsifter._slug(native_parcel_value)
            == "multiple_parcels_in_sale"
        ):
            return {
                "projection_skipped": True,
                "reason": "taxsifter_sale_has_no_single_parcel_join",
                "record_kind": record_kind,
            }
        _, native_parcel_id = _taxsifter_parcel_identity(
            record,
            source_id=source_id,
            require_join=False,
        )
        sale = _mapping(record.get("sale"), "record.sale")
        projected = _taxsifter_projection_record(
            record,
            source_id=source_id,
            assessor=None,
            account_occurrence=None,
            complete=False,
        )
        projected["source_occurrence_id"] = _taxsifter_sale_native_id(
            sale,
            (
                record.get("sale_identity")
                if isinstance(record.get("sale_identity"), Mapping)
                else None
            ),
        )
        result = _ingest_assessor_record(
            db,
            envelope=envelope,
            record=projected,
            source_id=source_id,
            raw_artifact_path=raw_artifact_path,
            raw_artifact_sha256=raw_artifact_sha256,
            observation_kind="assessor_sale_search_result",
        )
        result["sales_upserted"] = _project_taxsifter_sale(
            db,
            parcel_id=int(result["parcel_id"]),
            source_id=source_id,
            sale={**sale, "parcel_number": native_parcel_id},
            observation_id=int(result["observation_id"]),
            derivation="assessor_sales_search",
            identity=(
                record.get("sale_identity")
                if isinstance(record.get("sale_identity"), Mapping)
                else None
            ),
        )
        result["source_record_kind"] = record_kind
        return result

    if record_kind != "property_enrichment_bundle":
        return {
            "projection_skipped": True,
            "reason": "taxsifter_record_has_no_normalized_projection",
            "record_kind": record_kind,
        }

    tenant, native_parcel_id = _taxsifter_parcel_identity(
        record,
        source_id=source_id,
        require_join=True,
    )
    occurrence = _taxsifter_account_occurrence(
        record,
        source_id=source_id,
    )
    representations = _mapping(
        record.get("representations"),
        "record.representations",
    )
    assessor = _mapping(
        representations.get("assessor"),
        "record.representations.assessor",
    )
    _taxsifter_representation_consistency(
        assessor,
        source_id=source_id,
        county_geoid=tenant.county_geoid,
        native_parcel_id=native_parcel_id,
        account_occurrence=occurrence,
    )
    for representation_name in ("treasurer", "appraisal"):
        representation = representations.get(representation_name)
        if (
            isinstance(representation, Mapping)
            and _text(representation.get("source_id")) is not None
        ):
            _taxsifter_representation_consistency(
                representation,
                source_id=source_id,
                county_geoid=tenant.county_geoid,
                native_parcel_id=native_parcel_id,
                account_occurrence=occurrence,
            )

    projected = _taxsifter_projection_record(
        record,
        source_id=source_id,
        assessor=assessor,
        account_occurrence=occurrence,
        complete=True,
    )
    projected["taxsifter_representations"] = {
        key: value
        for key, value in representations.items()
        if key != "assessor"
    }
    result = _ingest_assessor_record(
        db,
        envelope=envelope,
        record=projected,
        source_id=source_id,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        observation_kind="property_enrichment_bundle",
    )
    parcel_id = int(result["parcel_id"])
    observation_id = int(result["observation_id"])
    retrieved_at = _text(envelope.get("retrieved_at")) or ""
    result["account_occurrence_aliases_upserted"] = _taxsifter_account_alias(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        occurrence=occurrence,
        effective_from=(
            _taxsifter_date(
                (
                    assessor.get("provenance")
                    if isinstance(assessor.get("provenance"), Mapping)
                    else {}
                ).get("data_current_as")
            )
            or retrieved_at
        ),
    )
    assessor_evidence_ref = _text(assessor.get("evidence_ref"))
    if assessor_evidence_ref:
        db.execute(
            """
            UPDATE ownership_assertion
            SET evidence_ref=?
            WHERE parcel_id=? AND source_id=?
              AND assertion_type='assessment_roll' AND observation_id=?
            """,
            (
                assessor_evidence_ref,
                parcel_id,
                source_id,
                observation_id,
            ),
        )

    sales_upserted = 0
    assessor_sales = assessor.get("sales_history")
    if isinstance(assessor_sales, list):
        for sale in assessor_sales:
            if isinstance(sale, Mapping):
                sales_upserted += _project_taxsifter_sale(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    sale=sale,
                    observation_id=observation_id,
                    derivation="assessor_sale_history",
                )
    sales_representation = representations.get("sales")
    if isinstance(sales_representation, Mapping):
        sales_results = sales_representation.get("results")
        if isinstance(sales_results, list):
            for value in sales_results:
                if not isinstance(value, Mapping):
                    continue
                sale = (
                    value.get("sale")
                    if isinstance(value.get("sale"), Mapping)
                    else value
                )
                sale_parcel = _text(sale.get("parcel_number"))
                if sale_parcel and sale_parcel != native_parcel_id:
                    raise PropertyIngestError(
                        "TaxSifter parcel-filtered sales representation returned "
                        "a different parcel"
                    )
                identity = (
                    value.get("sale_identity")
                    if isinstance(value.get("sale_identity"), Mapping)
                    else None
                )
                sales_upserted += _project_taxsifter_sale(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    sale=sale,
                    observation_id=observation_id,
                    derivation="assessor_sales_search",
                    identity=identity,
                )
    result["sales_upserted"] = sales_upserted

    treasurer = representations.get("treasurer")
    if (
        isinstance(treasurer, Mapping)
        and _text(treasurer.get("record_kind")) == "treasurer_tax_account"
    ):
        tax_events, tax_owners = _project_taxsifter_treasurer(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            treasurer=treasurer,
            observation_id=observation_id,
            retrieved_at=retrieved_at,
        )
    else:
        tax_events, tax_owners = 0, 0
    result["tax_events_upserted"] = tax_events
    result["tax_account_owners_upserted"] = tax_owners
    appraisal = representations.get("appraisal")
    result["appraisal_sections_preserved"] = (
        len(appraisal.get("sections") or [])
        if isinstance(appraisal, Mapping)
        else 0
    )
    result["source_record_kind"] = record_kind
    return result


PROPERTY_RECORD_MAPPERS = {
    NC_ONEMAP_SOURCE_ID: _ingest_assessor_record,
    ARLINGTON_PROPERTY_SOURCE_ID: _ingest_assessor_record,
    BEXAR_PROPERTY_SOURCE_ID: _ingest_assessor_record,
    DELAWARE_FIRSTMAP_SOURCE_ID: _ingest_firstmap_record,
    DESCHUTES_PROPERTY_SOURCE_ID: _ingest_assessor_record,
    DESCHUTES_CDD_WEBLINK_SOURCE_ID: _ingest_deschutes_cdd_document_record,
    BENTON_TAXLOT_OWNER_SOURCE_ID: _ingest_benton_taxlot_owner_record,
    BENTON_ASSESSMENT_BULK_SOURCE_ID: _ingest_benton_artifact_metadata,
    BENTON_ASSESSMENT_MAP_SOURCE_ID: _ingest_benton_artifact_metadata,
    LINCOLN_PROPERTYWEB_SOURCE_ID: _lincoln_propertyweb_record,
    LINCOLN_TAXLOT_WFS_SOURCE_ID: _lincoln_taxlot_wfs_record,
    **{
        source_id: _ingest_oregon_county_property_record
        for source_id in OREGON_COUNTY_PROPERTY_SOURCE_IDS
    },
    **{
        source_id: _ingest_washington_parcel_record
        for source_id in WASHINGTON_PARCEL_SOURCE_IDS
    },
    **{source_id: _ingest_dc_property_record for source_id in DC_PROPERTY_SOURCE_IDS},
    **{
        source_id: _ingest_jackson_douglas_assessor_record
        for source_id in OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCE_IDS
    },
    **{
        source_id: _ingest_jackson_property_event_record
        for source_id in JACKSON_PROPERTY_EVENT_SOURCE_IDS
    },
    **{
        source_id: _ingest_jackson_accela_detail_record
        for source_id in JACKSON_ACCELA_DETAIL_SOURCE_IDS
    },
    **{
        source_id: _ingest_oregon_linn_josephine_klamath_assessor_record
        for source_id in OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SOURCE_IDS
    },
    LANE_PARCELS_SOURCE_ID: _ingest_lane_marion_assessor_record,
    LANE_SALES_SOURCE_ID: _ingest_lane_sale_record,
    LANE_PROPERTY_ACCOUNT_SOURCE_ID: _ingest_lane_property_account_record,
    LANE_TAX_MAP_SOURCE_ID: _ingest_lane_tax_map_record,
    MARION_PARCELS_SOURCE_ID: _ingest_lane_marion_assessor_record,
    MARION_SALES_DOWNLOAD_SOURCE_ID: _ingest_lane_sale_record,
    MARION_ASSESSMENT_DOWNLOAD_SOURCE_ID: (
        _ingest_lane_marion_assessor_record
    ),
    DENVER_DELINQUENT_TAX_SOURCE_ID: _ingest_denver_delinquent_tax_record,
    DENVER_PROPERTY_SOURCE_ID: _ingest_assessor_record,
    MIAMI_DADE_PROPERTY_SOURCE_ID: _ingest_assessor_record,
    ORLEANS_PROPERTY_SOURCE_ID: _ingest_assessor_record,
    **{source_id: _ingest_assessor_record for source_id in OREGON_TAXLOT_SOURCE_IDS},
    **{
        source_id: _ingest_oregon_helion_property_record
        for source_id in OREGON_HELION_PROPERTY_SOURCE_IDS
    },
    **{
        source_id: _ingest_oregon_tax_foreclosure_record
        for source_id in OREGON_TAX_FORECLOSURE_SOURCE_IDS
    },
    LOS_ANGELES_ASSESSOR_SOURCE_ID: _ingest_los_angeles_assessor_record,
    LOS_ANGELES_TTC_PAYMENT_SOURCE_ID: _ingest_los_angeles_payment_record,
    LOS_ANGELES_TTC_SALE_SOURCE_ID: _ingest_los_angeles_sale_record,
    PHILADELPHIA_OPA_SOURCE_ID: _ingest_philadelphia_opa_record,
    PHILADELPHIA_HISTORY_SOURCE_ID: _ingest_philadelphia_history_record,
    PHILADELPHIA_DOR_SOURCE_ID: _ingest_philadelphia_dor_record,
    OHIO_STATEWIDE_PARCELS_SOURCE_ID: (
        _ingest_ohio_statewide_parcel_record
    ),
    OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID: (
        _ingest_ohio_franklin_auditor_bulk_record
    ),
    OHIO_FRANKLIN_SALES_GIS_SOURCE_ID: (
        _ingest_ohio_franklin_sales_gis_record
    ),
    OHIO_LICKING_AUDITOR_GIS_SOURCE_ID: (
        _ingest_ohio_licking_auditor_gis_record
    ),
    **{
        source_id: _ingest_ohio_pax_recorder_record
        for source_id in OHIO_PAX_QUERY_SOURCE_IDS
    },
    **{
        source_id: _ingest_ohio_foreclosure_event_record
        for source_id in OHIO_FORECLOSURE_EVENT_SOURCE_IDS
    },
    WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID: (_ingest_wisconsin_statewide_parcel_record),
    WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID: (
        _ingest_wyoming_dor_statewide_parcel_record
    ),
    MICHIGAN_PROPERTY_DIRECTORY_SOURCE_ID: (_ingest_michigan_property_directory_record),
    MICHIGAN_EATON_PARCELS_SOURCE_ID: (_ingest_michigan_eaton_parcel_record),
    **{
        source_id: _ingest_georgia_property_source_record
        for source_id in GEORGIA_PROPERTY_SOURCE_IDS
    },
    VIRGINIA_BEACH_DELINQUENT_TAX_SOURCE_ID: (
        _ingest_virginia_beach_delinquent_tax_record
    ),
    VIRGINIA_VGIN_PARCELS_SOURCE_ID: (_ingest_virginia_vgin_parcel_record),
    NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID: (
        _ingest_new_jersey_statewide_parcel_record
    ),
    NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID: (_ingest_new_york_statewide_parcel_record),
    NEW_YORK_SALESWEB_SOURCE_ID: _ingest_new_york_salesweb_record,
    NEW_JERSEY_DCA_PROPERTY_SOURCE_ID: (_ingest_new_jersey_dca_property_record),
    NEW_JERSEY_SR1A_SOURCE_ID: _ingest_new_jersey_sr1a_record,
    ORANGE_TAX_SOURCE_ID: _ingest_orange_tax_collector_record,
    PALM_BEACH_RECORDER_SOURCE_ID: _ingest_palm_beach_recorder_record,
    PALM_BEACH_PROPERTY_SOURCE_ID: _ingest_palm_beach_property_record,
    PALM_BEACH_TAX_SOURCE_ID: _ingest_palm_beach_tax_collector_record,
    PALM_BEACH_TAX_DEEDS_SOURCE_ID: _ingest_palm_beach_tax_deed_record,
    BROWARD_RECORDER_SOURCE_ID: _ingest_broward_recorder_record,
    WASHINGTON_LAND_RECORDS_SOURCE_ID: _ingest_washington_land_record,
    **{
        source_id: _ingest_washington_taxsifter_record
        for source_id in WASHINGTON_TAXSIFTER_SOURCE_IDS
    },
    MASON_COUNTY_TAX_PARCELS_SOURCE_ID: (
        _ingest_mason_county_tax_parcel_record
    ),
    HCAD_GIS_SOURCE_ID: _ingest_hcad_gis_record,
    TXGIO_LAND_PARCELS_SOURCE_ID: _ingest_txgio_land_parcel_record,
    MONTANA_CADASTRAL_SOURCE_ID: _ingest_montana_cadastral_record,
    COOK_PROPERTY_SOURCE_ID: _ingest_cook_record,
    MD_PROPERTY_SOURCE_ID: _ingest_md_record,
    MD_MDP_PARCEL_POINTS_SOURCE_ID: _ingest_md_mdp_parcel_point_record,
    MD_PLATS_SOURCE_ID: _ingest_md_plats_record,
    NYC_PIP_SOURCE_ID: _ingest_nyc_pip_record,
    ACRIS_SOURCE_ID: _ingest_acris_record,
    MIAMI_DADE_PUBLIC_RECORDER_SOURCE_ID: _ingest_miami_recorder_record,
    MIAMI_DADE_CANONICAL_RECORDER_SOURCE_ID: _ingest_miami_recorder_record,
    REEVES_RECORDER_SOURCE_ID: _ingest_county_recorder_record,
    **{
        source_id: _ingest_county_recorder_record
        for source_id in GOVOS_RECORDER_SOURCE_IDS
    },
    **{
        source_id: _ingest_county_recorder_record
        for source_id in OREGON_HELION_RECORDER_SOURCE_IDS
    },
    HARRIS_RECORDER_SOURCE_ID: _ingest_county_recorder_record,
    SANTA_FE_CLERKTRACK_SOURCE_ID: _ingest_santa_fe_clerktrack_record,
    SANTA_FE_PROPERTY_SOURCE_ID: _ingest_santa_fe_property_record,
    USVI_PROPERTY_TAX_SOURCE_ID: _ingest_usvi_property_tax_record,
    USVI_RECORDER_SOURCE_ID: _ingest_usvi_recorder_record,
}


def _artifact_details(
    raw_artifact_path: Path | str | None,
) -> tuple[str | None, str | None]:
    artifact_path = (
        str(Path(raw_artifact_path).resolve()) if raw_artifact_path else None
    )
    if not artifact_path:
        return None, None
    digest = hashlib.sha256()
    with Path(artifact_path).open("rb") as artifact:
        while chunk := artifact.read(1024 * 1024):
            digest.update(chunk)
    return artifact_path, digest.hexdigest()


def ingest_property_envelope(
    envelope: Mapping[str, Any],
    *,
    db_path: Path | str = DEFAULT_PROPERTY_DB,
    raw_artifact_path: Path | str | None = None,
) -> dict[str, Any]:
    """Preserve a canonical property envelope and project known record schemas."""
    envelope = _mapping(envelope, "envelope")
    source_id = _source_id(envelope)
    record_mapper = PROPERTY_RECORD_MAPPERS.get(source_id)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    records_value = envelope.get("records")
    if not isinstance(records_value, list):
        raise PropertyIngestError("records must be a list")
    records = [
        _mapping(record, f"records[{index}]")
        for index, record in enumerate(records_value)
    ]
    if status == "no_results" and records:
        raise PropertyIngestError("no_results envelope cannot contain records")

    artifact_path, artifact_sha256 = _artifact_details(raw_artifact_path)
    envelope_hash = sha256_fingerprint(envelope)
    envelope_projection: dict[str, Any] | None = None

    db = connect_property(db_path)
    try:
        with db:
            envelope_observation_id, _ = _insert_observation(
                db,
                source_id=source_id,
                source_native_id=None,
                record_kind="query_envelope",
                query_fingerprint=query_fingerprint,
                source_url=_record_url(envelope),
                retrieved_at=retrieved_at,
                access_status=status,
                schema_fingerprint=None,
                raw=envelope,
                raw_artifact_path=artifact_path,
                raw_artifact_sha256=artifact_sha256,
                warnings=warnings,
            )
            if source_id in OREGON_TAX_FORECLOSURE_SOURCE_IDS:
                envelope_projection = _ingest_oregon_tax_publication_envelope(
                    db,
                    envelope=envelope,
                    source_id=source_id,
                    retrieved_at=retrieved_at,
                )
            ingested = []
            projection_skips = []
            if status in INGESTABLE_STATUSES and record_mapper is not None:
                for index, record in enumerate(records):
                    projection = record_mapper(
                        db,
                        envelope=envelope,
                        record=record,
                        source_id=source_id,
                        raw_artifact_path=artifact_path,
                        raw_artifact_sha256=artifact_sha256,
                    )
                    if projection.get("projection_skipped") is True:
                        projection_skips.append(
                            {
                                "record_index": index,
                                **projection,
                            }
                        )
                    else:
                        ingested.append(projection)
    finally:
        db.close()

    return {
        "schema_version": "public-records-ingest/1.0",
        "status": "ok",
        "source_id": source_id,
        "source_status": status,
        "query_fingerprint": query_fingerprint,
        "envelope_sha256": envelope_hash,
        "raw_artifact_sha256": artifact_sha256 or envelope_hash,
        "envelope_observation_id": envelope_observation_id,
        "records_seen": len(records),
        "records_ingested": len(ingested),
        "records_preserved_without_projection": len(records) - len(ingested),
        "projection_skips": projection_skips,
        "projection_supported": record_mapper is not None,
        "envelope_projection": envelope_projection,
        "property_db": str(Path(db_path)),
        "records": ingested,
    }


def ingest_nc_envelope(
    envelope: Mapping[str, Any],
    *,
    db_path: Path | str = DEFAULT_PROPERTY_DB,
    raw_artifact_path: Path | str | None = None,
) -> dict[str, Any]:
    """Ingest one canonical NC OneMap result envelope transactionally."""
    envelope = _mapping(envelope, "envelope")
    source_id = _source_id(envelope)
    if source_id != NC_ONEMAP_SOURCE_ID:
        raise PropertyIngestError(
            f"nc-onemap ingestion requires source {NC_ONEMAP_SOURCE_ID}, got {source_id}"
        )
    status = _text(envelope.get("status"))
    if status not in INGESTABLE_STATUSES:
        raise PropertyIngestError(f"unsupported ingestion source status {status!r}")
    return ingest_property_envelope(
        envelope,
        db_path=db_path,
        raw_artifact_path=raw_artifact_path,
    )


def _read_json(path: str) -> tuple[dict[str, Any], str | None]:
    if path == "-":
        data = json.load(sys.stdin)
        return _mapping(data, "input"), None
    input_path = Path(path)
    with input_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return _mapping(data, "input"), str(input_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize property query envelopes")
    sub = parser.add_subparsers(dest="command", required=True)
    generic = sub.add_parser(
        "ingest",
        help="Dispatch a supported canonical property result envelope",
    )
    generic.add_argument(
        "--input",
        required=True,
        help="Envelope JSON path, or - for stdin",
    )
    generic.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    add_output_args(generic)
    nc = sub.add_parser("nc-onemap", help="Ingest an NC OneMap result envelope")
    nc.add_argument("--input", required=True, help="Envelope JSON path, or - for stdin")
    nc.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    add_output_args(nc)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    envelope, artifact_path = _read_json(args.input)
    if args.command == "nc-onemap":
        result = ingest_nc_envelope(
            envelope,
            db_path=args.property_db,
            raw_artifact_path=artifact_path,
        )
    else:
        result = ingest_property_envelope(
            envelope,
            db_path=args.property_db,
            raw_artifact_path=artifact_path,
        )
    if write_output(
        result,
        args,
        summary=f"normalized {result['source_id']} property records",
    ):
        return
    print(json.dumps(result, indent=2 if args.json_out else None, sort_keys=True))


if __name__ == "__main__":
    main()
