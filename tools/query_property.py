#!/usr/bin/env python3
"""Unified property-record query router.

The router serves normalized local sidecar data by default and selects live
adapters through ``--source``. Source capabilities, access state, and reviewed
limits come from the central catalog.

Usage:
    uv run python tools/query_property.py sources --json
    uv run python tools/query_property.py owner "SMITH" --jurisdiction 37005
    uv run python tools/query_property.py parcel 3013467134 \
      --source us-nc-onemap-parcels --county-fips 005 --ingest
    uv run python tools/query_property.py address "7 TRAYMORE RD" \
      --source us-md-sdat-property-hidden --county-code 04
    uv run python tools/query_property.py parcel 1-1386-10 \
      --source us-nyc-acris
    uv run python tools/query_property.py chain 3013467134 --jurisdiction 37005
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from tools import (
        query_acris,
        query_arlington_property,
        query_bexar_property,
        query_broward_official_records,
        query_cook_property,
        query_dc_property,
        query_delaware_firstmap,
        query_deschutes_dial,
        query_deschutes_laserfiche,
        query_deschutes_property,
        query_denver_delinquent_tax,
        query_denver_foreclosures,
        query_denver_property,
        query_govos_recorders,
        query_georgia_property_sources,
        query_harris_foreclosures,
        query_harris_property,
        query_harris_recorder,
        query_hcad_gis,
        query_fl_dor_property,
        query_la_property,
        query_los_angeles_ttc,
        query_md_mdp_property_downloads,
        query_md_mdp_parcel_points,
        query_md_plats,
        query_md_property,
        query_mason_county_tax_parcels,
        query_michigan_eaton_parcels,
        query_michigan_property_directories,
        query_miami_dade_property,
        query_montana_cadastral,
        query_nc_property,
        query_new_jersey_dca_property,
        query_new_jersey_parcels,
        query_new_jersey_sr1a,
        query_nyc_pip,
        query_ny_salesweb,
        query_ny_statewide_parcels,
        query_licking_foreclosure_archive,
        query_ohio_franklin_auditor_bulk,
        query_ohio_franklin_sales_gis,
        query_ohio_licking_property,
        query_ohio_pax_recorders,
        query_ohio_sheriff_sales,
        query_ohio_statewide_parcels,
        query_oregon_benton_property,
        query_oregon_clackamas_property,
        query_oregon_helion_property,
        query_oregon_helion_recorder,
        query_oregon_jackson_accela,
        query_oregon_jackson_douglas_assessors,
        query_oregon_jackson_property_events,
        query_oregon_lane_marion_parcels,
        query_oregon_lane_property,
        query_oregon_lincoln_propertyweb,
        query_oregon_lincoln_taxlots,
        query_oregon_linn_josephine_klamath_assessors,
        query_oregon_marion_downloads,
        query_oregon_multnomah_sail,
        query_oregon_tax_foreclosures,
        query_oregon_taxlots,
        query_oregon_wasco_property,
        query_oregon_washington_case_permits,
        query_oregon_washington_property,
        query_oregon_yamhill_property,
        query_orange_tax_collector,
        query_orleans_property,
        query_palm_beach_official_records,
        query_palm_beach_property_appraiser,
        query_palm_beach_tax_collector,
        query_palm_beach_tax_deeds,
        query_philadelphia_property,
        query_reeves_records,
        query_santa_fe_clerktrack,
        query_santa_fe_property,
        query_txgio_land_parcels,
        query_usvi_property_tax,
        query_usvi_recorder,
        query_va_beach_delinquent_tax,
        query_virginia_parcels,
        query_washington_digital_archives_land,
        query_washington_parcels,
        query_washington_taxsifter,
        query_wisconsin_parcels,
        query_wy_dor_parcels,
    )
    from tools.ingest_property_records import ingest_property_envelope
    from tools.fl_dor_property_common import resolve_county as resolve_fl_county
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        CatalogError,
        PublicRecordsCatalog,
        acquisition_result_status,
    )
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
    from tools.public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
    from tools.seed_public_records_catalog import ensure_catalog_source
except ImportError:
    import query_acris
    import query_arlington_property
    import query_bexar_property
    import query_broward_official_records
    import query_cook_property
    import query_dc_property
    import query_delaware_firstmap
    import query_deschutes_dial
    import query_deschutes_laserfiche
    import query_deschutes_property
    import query_denver_delinquent_tax
    import query_denver_foreclosures
    import query_denver_property
    import query_govos_recorders
    import query_georgia_property_sources
    import query_harris_foreclosures
    import query_harris_property
    import query_harris_recorder
    import query_hcad_gis
    import query_fl_dor_property
    import query_la_property
    import query_los_angeles_ttc
    import query_md_mdp_property_downloads
    import query_md_mdp_parcel_points
    import query_md_plats
    import query_md_property
    import query_mason_county_tax_parcels
    import query_michigan_eaton_parcels
    import query_michigan_property_directories
    import query_miami_dade_property
    import query_montana_cadastral
    import query_nc_property
    import query_new_jersey_dca_property
    import query_new_jersey_parcels
    import query_new_jersey_sr1a
    import query_nyc_pip
    import query_ny_salesweb
    import query_ny_statewide_parcels
    import query_licking_foreclosure_archive
    import query_ohio_franklin_auditor_bulk
    import query_ohio_franklin_sales_gis
    import query_ohio_licking_property
    import query_ohio_pax_recorders
    import query_ohio_sheriff_sales
    import query_ohio_statewide_parcels
    import query_oregon_benton_property
    import query_oregon_clackamas_property
    import query_oregon_helion_property
    import query_oregon_helion_recorder
    import query_oregon_jackson_accela
    import query_oregon_jackson_douglas_assessors
    import query_oregon_jackson_property_events
    import query_oregon_lane_marion_parcels
    import query_oregon_lane_property
    import query_oregon_lincoln_propertyweb
    import query_oregon_lincoln_taxlots
    import query_oregon_linn_josephine_klamath_assessors
    import query_oregon_marion_downloads
    import query_oregon_multnomah_sail
    import query_oregon_tax_foreclosures
    import query_oregon_taxlots
    import query_oregon_wasco_property
    import query_oregon_washington_case_permits
    import query_oregon_washington_property
    import query_oregon_yamhill_property
    import query_orange_tax_collector
    import query_orleans_property
    import query_palm_beach_official_records
    import query_palm_beach_property_appraiser
    import query_palm_beach_tax_collector
    import query_palm_beach_tax_deeds
    import query_philadelphia_property
    import query_reeves_records
    import query_santa_fe_clerktrack
    import query_santa_fe_property
    import query_txgio_land_parcels
    import query_usvi_property_tax
    import query_usvi_recorder
    import query_va_beach_delinquent_tax
    import query_virginia_parcels
    import query_washington_digital_archives_land
    import query_washington_parcels
    import query_washington_taxsifter
    import query_wisconsin_parcels
    import query_wy_dor_parcels
    from ingest_property_records import ingest_property_envelope
    from fl_dor_property_common import resolve_county as resolve_fl_county
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        CatalogError,
        PublicRecordsCatalog,
        acquisition_result_status,
    )
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
    from public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
    from seed_public_records_catalog import ensure_catalog_source


LOCAL_SOURCE_ID = "local-property-records-sidecar"
CATALOG_SOURCE_ID = "local-public-records-catalog"
NC_SOURCE_ID = query_nc_property.SOURCE_ID
BEXAR_SOURCE_ID = query_bexar_property.SOURCE_ID
BROWARD_RECORDER_SOURCE_ID = query_broward_official_records.SOURCE_ID
DELAWARE_FIRSTMAP_SOURCE_ID = query_delaware_firstmap.SOURCE_ID
DESCHUTES_CDD_WEBLINK_SOURCE_ID = query_deschutes_laserfiche.SOURCE_ID
DESCHUTES_DIAL_SOURCE_ID = query_deschutes_dial.SOURCE_ID
DESCHUTES_PROPERTY_SOURCE_ID = query_deschutes_property.SOURCE_ID
DENVER_DELINQUENT_TAX_SOURCE_ID = query_denver_delinquent_tax.SOURCE_ID
DENVER_FORECLOSURE_SOURCE_ID = query_denver_foreclosures.SOURCE_ID
DENVER_PROPERTY_SOURCE_ID = query_denver_property.SOURCE_ID
COOK_SOURCE_ID = query_cook_property.SOURCE_ID
MD_SOURCE_ID = query_md_property.SOURCE_ID
MD_MDP_PROPERTY_DOWNLOAD_SOURCE_IDS = query_md_mdp_property_downloads.SOURCE_IDS
MD_MDP_PARCEL_POINTS_SOURCE_ID = query_md_mdp_parcel_points.SOURCE_ID
MD_PLATS_SOURCE_ID = query_md_plats.SOURCE_ID
MICHIGAN_PROPERTY_DIRECTORY_SOURCE_ID = query_michigan_property_directories.SOURCE_ID
MICHIGAN_EATON_PARCELS_SOURCE_ID = query_michigan_eaton_parcels.SOURCE_ID
GEORGIA_PROPERTY_DIRECTORY_SOURCE_ID = (
    query_georgia_property_sources.DIRECTORY_SOURCE_ID
)
GEORGIA_GSCCCA_SOURCE_ID = query_georgia_property_sources.GSCCCA_SOURCE_ID
MIAMI_DADE_PA_SOURCE_ID = query_miami_dade_property.SOURCE_ID
MIAMI_DADE_RECORDER_PUBLIC_SOURCE_ID = "us-fl-miami-dade-official-records-public"
MIAMI_DADE_RECORDER_SOURCE_ID = "us-fl-miami-dade-official-records"
EBR_SOURCE_ID = query_la_property.SOURCE_ID
ORLEANS_SOURCE_ID = query_orleans_property.SOURCE_ID
OREGON_TAXLOT_SOURCE_IDS = tuple(query_oregon_taxlots.SOURCES)
OREGON_PORTLAND_TAXLOT_SOURCE_ID = query_oregon_taxlots.PORTLAND_SOURCE_ID
OREGON_BENTON_TAXLOT_SOURCE_ID = query_oregon_benton_property.PARCEL_SOURCE_ID
OREGON_BENTON_BULK_SOURCE_ID = query_oregon_benton_property.BULK_SOURCE_ID
OREGON_BENTON_MAP_SOURCE_ID = query_oregon_benton_property.MAP_SOURCE_ID
OREGON_CLACKAMAS_SOURCE_IDS = query_oregon_clackamas_property.SOURCE_IDS
OREGON_LINCOLN_PROPERTYWEB_SOURCE_ID = query_oregon_lincoln_propertyweb.SOURCE_ID
OREGON_LINCOLN_TAXLOT_SOURCE_ID = query_oregon_lincoln_taxlots.SOURCE_ID
OREGON_HELION_PROPERTY_SOURCE_IDS = query_oregon_helion_property.SOURCE_IDS
OREGON_HELION_RECORDER_SOURCE_IDS = query_oregon_helion_recorder.SOURCE_IDS
OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCE_IDS = tuple(
    query_oregon_jackson_douglas_assessors.SOURCES
)
OREGON_JACKSON_PROPERTY_EVENT_SOURCE_IDS = tuple(
    query_oregon_jackson_property_events.SOURCES
)
OREGON_JACKSON_ACCELA_SOURCE_IDS = tuple(
    source.source_id for source in query_oregon_jackson_accela.SOURCES.values()
)
OREGON_LINN_JOSEPHINE_KLAMATH_SOURCE_IDS = tuple(
    query_oregon_linn_josephine_klamath_assessors.SOURCES
)
OREGON_LANE_MARION_SOURCE_IDS = tuple(query_oregon_lane_marion_parcels.SOURCES)
OREGON_LANE_PROPERTY_SOURCE_IDS = query_oregon_lane_property.SOURCE_IDS
OREGON_MARION_DOWNLOAD_SOURCE_IDS = query_oregon_marion_downloads.SOURCE_IDS
OREGON_MULTNOMAH_SAIL_SOURCE_IDS = query_oregon_multnomah_sail.SOURCE_IDS
OREGON_TAX_FORECLOSURE_SOURCE_IDS = tuple(query_oregon_tax_foreclosures.SOURCES)
OREGON_WASCO_SOURCE_IDS = query_oregon_wasco_property.SOURCE_IDS
OREGON_WASHINGTON_CASE_PERMIT_SOURCE_IDS = tuple(
    query_oregon_washington_case_permits.SOURCES
)
OREGON_WASHINGTON_SOURCE_IDS = tuple(query_oregon_washington_property.SOURCES)
OREGON_YAMHILL_SOURCE_IDS = query_oregon_yamhill_property.SOURCE_IDS
REEVES_SOURCE_ID = query_reeves_records.SOURCE_ID
GOVOS_RECORDER_SOURCE_IDS = query_govos_recorders.SOURCE_IDS
ACRIS_SOURCE_ID = query_acris.SOURCE_ID
ARLINGTON_PROPERTY_SOURCE_ID = query_arlington_property.SOURCE_ID
FL_SOURCE_ID = query_fl_dor_property.SOURCE_ID
MASSGIS_SOURCE_ID = "us-ma-massgis-parcels"
HARRIS_SOURCE_ID = query_harris_property.SOURCE_ID
HCAD_GIS_SOURCE_ID = query_hcad_gis.SOURCE_ID
HARRIS_FORECLOSURE_SOURCE_ID = query_harris_foreclosures.SOURCE_ID
HARRIS_RECORDER_SOURCE_ID = query_harris_recorder.SOURCE_ID
TEXAS_EPTS_SOURCE_ID = "us-tx-comptroller-epts"
TXGIO_LAND_PARCELS_SOURCE_ID = query_txgio_land_parcels.SOURCE_ID
SANTA_FE_PROPERTY_SOURCE_ID = query_santa_fe_property.SOURCE_ID
SANTA_FE_CLERKTRACK_SOURCE_ID = query_santa_fe_clerktrack.SOURCE_ID
USVI_PROPERTY_TAX_SOURCE_ID = query_usvi_property_tax.SOURCE_ID
USVI_RECORDER_SOURCE_ID = query_usvi_recorder.SOURCE_ID
MONTANA_CADASTRAL_SOURCE_ID = query_montana_cadastral.SOURCE_ID
VIRGINIA_BEACH_DELINQUENT_TAX_SOURCE_ID = (
    query_va_beach_delinquent_tax.SOURCE_ID
)
LOS_ANGELES_ASSESSOR_SOURCE_ID = query_los_angeles_ttc.ASSESSOR_SOURCE_ID
LOS_ANGELES_TTC_PAYMENT_SOURCE_ID = query_los_angeles_ttc.PAYMENT_SOURCE_ID
LOS_ANGELES_TTC_SALE_SOURCE_ID = query_los_angeles_ttc.SALE_SOURCE_ID
PHILADELPHIA_OPA_SOURCE_ID = query_philadelphia_property.SOURCE_ID
PHILADELPHIA_HISTORY_SOURCE_ID = query_philadelphia_property.HISTORY_SOURCE_ID
PHILADELPHIA_DOR_SOURCE_ID = query_philadelphia_property.DOR_SOURCE_ID
VIRGINIA_VGIN_PARCELS_SOURCE_ID = query_virginia_parcels.SOURCE_ID
WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID = query_wisconsin_parcels.SOURCE_ID
WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID = query_wy_dor_parcels.SOURCE_ID
NEW_JERSEY_DCA_PROPERTY_SOURCE_ID = query_new_jersey_dca_property.SOURCE_ID
NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID = query_new_jersey_parcels.SOURCE_ID
NEW_JERSEY_SR1A_SOURCE_ID = query_new_jersey_sr1a.SOURCE_ID
NYC_PIP_SOURCE_ID = query_nyc_pip.SOURCE_ID
NEW_YORK_SALESWEB_SOURCE_ID = query_ny_salesweb.SOURCE_ID
NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID = query_ny_statewide_parcels.SOURCE_ID
OHIO_PAX_RECORDER_SOURCE_IDS = query_ohio_pax_recorders.SOURCE_IDS
OHIO_SHERIFF_REALAUCTION_SOURCE_IDS = tuple(
    tenant.source_id for tenant in query_ohio_sheriff_sales.TENANTS.values()
)
OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID = (
    query_licking_foreclosure_archive.SOURCE_ID
)
OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID = (
    query_ohio_franklin_auditor_bulk.SOURCE_ID
)
OHIO_FRANKLIN_SALES_GIS_SOURCE_ID = query_ohio_franklin_sales_gis.SOURCE_ID
OHIO_LICKING_AUDITOR_GIS_SOURCE_ID = query_ohio_licking_property.SOURCE_ID
OHIO_LICKING_RECORDER_DETAIL_SOURCE_ID = (
    query_ohio_pax_recorders.LICKING_DETAIL_SOURCE_ID
)
OHIO_STATEWIDE_PARCELS_SOURCE_ID = query_ohio_statewide_parcels.SOURCE_ID
ORANGE_TAX_COLLECTOR_SOURCE_ID = query_orange_tax_collector.SOURCE_ID
PALM_BEACH_RECORDER_SOURCE_ID = query_palm_beach_official_records.SOURCE_ID
PALM_BEACH_PROPERTY_SOURCE_ID = query_palm_beach_property_appraiser.SOURCE_ID
PALM_BEACH_TAX_SOURCE_ID = query_palm_beach_tax_collector.SOURCE_ID
PALM_BEACH_TAX_DEEDS_SOURCE_ID = query_palm_beach_tax_deeds.SOURCE_ID
ACRIS_IMAGES_SOURCE_ID = "us-nyc-acris-images"
WASHINGTON_LAND_RECORDS_SOURCE_ID = (
    query_washington_digital_archives_land.SOURCE_ID
)
MASON_COUNTY_TAX_PARCELS_SOURCE_ID = (
    query_mason_county_tax_parcels.SOURCE_ID
)
WASHINGTON_PARCEL_LINEAGE_SOURCE_ID = query_washington_parcels.LINEAGE_ID
WASHINGTON_PARCEL_REPRESENTATION_SOURCE_IDS = tuple(
    representation.source_id
    for representation in query_washington_parcels.REPRESENTATIONS.values()
)
WASHINGTON_PARCEL_REPRESENTATIONS_BY_SOURCE = {
    representation.source_id: representation.key
    for representation in query_washington_parcels.REPRESENTATIONS.values()
}
WASHINGTON_PARCEL_FRESHNESS_SOURCE_ID = query_washington_parcels.FRESHNESS_SOURCE_ID
WASHINGTON_PARCEL_LAND_USE_SOURCE_ID = query_washington_parcels.LAND_USE_SOURCE_ID
WASHINGTON_PARCEL_SOURCE_IDS = (
    WASHINGTON_PARCEL_LINEAGE_SOURCE_ID,
    *WASHINGTON_PARCEL_REPRESENTATION_SOURCE_IDS,
    WASHINGTON_PARCEL_FRESHNESS_SOURCE_ID,
    WASHINGTON_PARCEL_LAND_USE_SOURCE_ID,
)
WASHINGTON_TAXSIFTER_UMBRELLA_SOURCE_ID = (
    query_washington_taxsifter.UMBRELLA_SOURCE_ID
)
WASHINGTON_TAXSIFTER_LEAF_SOURCE_IDS = tuple(
    tenant.source_id for tenant in query_washington_taxsifter.TENANTS
)
WASHINGTON_TAXSIFTER_SOURCE_IDS = (
    WASHINGTON_TAXSIFTER_UMBRELLA_SOURCE_ID,
    *WASHINGTON_TAXSIFTER_LEAF_SOURCE_IDS,
)
DC_PROPERTY_LINEAGE_SOURCE_ID = query_dc_property.LINEAGE_ID
DC_PROPERTY_COMPONENT_SOURCE_IDS = tuple(
    component.source_id for component in query_dc_property.COMPONENTS.values()
)
DC_PROPERTY_RECORDER_SOURCE_ID = query_dc_property.RECORDER_SOURCE_ID
DC_PROPERTY_SOURCE_IDS = (
    DC_PROPERTY_LINEAGE_SOURCE_ID,
    *DC_PROPERTY_COMPONENT_SOURCE_IDS,
    DC_PROPERTY_RECORDER_SOURCE_ID,
)

LOCAL_SOURCE = SourceMetadata(
    source_id=LOCAL_SOURCE_ID,
    name="Normalized property records sidecar",
    source_role="local_normalized_cache",
    metadata={
        "coverage_semantics": "cache_with_explicit_query_evidence",
        "assessor_ownership_caveat": (
            "Assessment-roll owners are source observations, not proof of title "
            "or beneficial ownership."
        ),
    },
)
CATALOG_SOURCE = SourceMetadata(
    source_id=CATALOG_SOURCE_ID,
    name="Public records source catalog",
    source_role="source_control_plane",
)


@dataclass(frozen=True)
class _LiveRoute:
    adapter: Any
    adapter_command: str
    translate: Callable[[argparse.Namespace, str], argparse.Namespace]


@dataclass(frozen=True)
class _ExecuteWithoutAccessDecision:
    """Adapt source modules whose direct execute surface needs only arguments."""

    adapter: Any

    def execute(
        self,
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> Any:
        del access_decision
        return self.adapter.execute(args)


@dataclass(frozen=True)
class _ExecuteWithAccessContract:
    """Pass the catalog decision to adapters that accept an access contract."""

    adapter: Any

    def execute(
        self,
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> Any:
        return self.adapter.execute(
            args,
            access_contract=access_decision,
        )


OREGON_JACKSON_ACCELA_ADAPTER = _ExecuteWithoutAccessDecision(
    query_oregon_jackson_accela
)
DESCHUTES_CDD_WEBLINK_ADAPTER = _ExecuteWithoutAccessDecision(
    query_deschutes_laserfiche
)
OREGON_BENTON_ADAPTER = _ExecuteWithoutAccessDecision(query_oregon_benton_property)
OREGON_WASCO_ADAPTER = _ExecuteWithoutAccessDecision(query_oregon_wasco_property)
OREGON_WASHINGTON_ADAPTER = _ExecuteWithoutAccessDecision(
    query_oregon_washington_property
)
OREGON_WASHINGTON_CASE_PERMIT_ADAPTER = _ExecuteWithoutAccessDecision(
    query_oregon_washington_case_permits
)
OREGON_LINCOLN_PROPERTYWEB_ADAPTER = _ExecuteWithoutAccessDecision(
    query_oregon_lincoln_propertyweb
)
OREGON_LINCOLN_TAXLOT_ADAPTER = _ExecuteWithoutAccessDecision(
    query_oregon_lincoln_taxlots
)
OREGON_LINN_JOSEPHINE_KLAMATH_ADAPTER = _ExecuteWithoutAccessDecision(
    query_oregon_linn_josephine_klamath_assessors
)
OREGON_LANE_PROPERTY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_oregon_lane_property
)
WASHINGTON_PARCEL_ADAPTER = _ExecuteWithoutAccessDecision(query_washington_parcels)
LOS_ANGELES_TTC_ADAPTER = _ExecuteWithoutAccessDecision(query_los_angeles_ttc)
PHILADELPHIA_PROPERTY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_philadelphia_property
)
VIRGINIA_VGIN_PARCELS_ADAPTER = _ExecuteWithoutAccessDecision(query_virginia_parcels)
WISCONSIN_STATEWIDE_PARCELS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_wisconsin_parcels
)
WYOMING_DOR_STATEWIDE_PARCELS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_wy_dor_parcels
)
MICHIGAN_PROPERTY_DIRECTORY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_michigan_property_directories
)
MICHIGAN_EATON_PARCELS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_michigan_eaton_parcels
)
MD_MDP_PARCEL_POINTS_ADAPTER = _ExecuteWithAccessContract(
    query_md_mdp_parcel_points
)
MD_PLATS_ADAPTER = _ExecuteWithoutAccessDecision(query_md_plats)
GEORGIA_PROPERTY_SOURCES_ADAPTER = _ExecuteWithoutAccessDecision(
    query_georgia_property_sources
)
FL_DOR_PROPERTY_ADAPTER = _ExecuteWithoutAccessDecision(query_fl_dor_property)
HARRIS_PROPERTY_ADAPTER = _ExecuteWithoutAccessDecision(query_harris_property)
HCAD_GIS_ADAPTER = _ExecuteWithAccessContract(query_hcad_gis)
TXGIO_LAND_PARCELS_ADAPTER = _ExecuteWithAccessContract(query_txgio_land_parcels)
MONTANA_CADASTRAL_ADAPTER = _ExecuteWithoutAccessDecision(
    query_montana_cadastral
)
NEW_JERSEY_DCA_PROPERTY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_new_jersey_dca_property
)
NYC_PIP_ADAPTER = _ExecuteWithoutAccessDecision(query_nyc_pip)
NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_new_jersey_parcels
)
NEW_JERSEY_SR1A_ADAPTER = _ExecuteWithoutAccessDecision(query_new_jersey_sr1a)
NEW_YORK_SALESWEB_ADAPTER = _ExecuteWithoutAccessDecision(query_ny_salesweb)
NEW_YORK_STATEWIDE_PARCELS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ny_statewide_parcels
)
OHIO_STATEWIDE_PARCELS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_statewide_parcels
)
OHIO_PAX_RECORDER_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_pax_recorders
)
OHIO_SHERIFF_REALAUCTION_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_sheriff_sales
)
OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER = _ExecuteWithoutAccessDecision(
    query_licking_foreclosure_archive
)
OHIO_LICKING_AUDITOR_GIS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_licking_property
)
OHIO_FRANKLIN_AUDITOR_BULK_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_franklin_auditor_bulk
)
OHIO_FRANKLIN_SALES_GIS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_franklin_sales_gis
)
ORANGE_TAX_COLLECTOR_ADAPTER = _ExecuteWithoutAccessDecision(
    query_orange_tax_collector
)
PALM_BEACH_RECORDER_ADAPTER = _ExecuteWithoutAccessDecision(
    query_palm_beach_official_records
)
PALM_BEACH_PROPERTY_ADAPTER = _ExecuteWithAccessContract(
    query_palm_beach_property_appraiser
)
PALM_BEACH_TAX_ADAPTER = _ExecuteWithAccessContract(
    query_palm_beach_tax_collector
)
PALM_BEACH_TAX_DEEDS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_palm_beach_tax_deeds
)
BROWARD_RECORDER_ADAPTER = _ExecuteWithoutAccessDecision(query_broward_official_records)
SANTA_FE_PROPERTY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_santa_fe_property
)
SANTA_FE_CLERKTRACK_ADAPTER = _ExecuteWithoutAccessDecision(
    query_santa_fe_clerktrack
)
USVI_PROPERTY_TAX_ADAPTER = _ExecuteWithoutAccessDecision(
    query_usvi_property_tax
)
USVI_RECORDER_ADAPTER = _ExecuteWithoutAccessDecision(query_usvi_recorder)
MASON_COUNTY_TAX_PARCELS_ADAPTER = _ExecuteWithAccessContract(
    query_mason_county_tax_parcels
)


@dataclass(frozen=True)
class _WashingtonLandRecordsAdapter:
    """Add shared county coverage and scope checks around the source adapter."""

    adapter: Any

    def execute(
        self,
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> PublicRecordsResult:
        del access_decision
        alternative = getattr(args, "shared_gap_alternative", None)
        if alternative is not None:
            record = alternative.to_record()
            complements = list(record.pop("complementary_sources", []))
            assessor_complements = [
                item
                for item in complements
                if str(item.get("kind") or "").startswith("assessor")
            ]
            other_complements = [
                item
                for item in complements
                if item not in assessor_complements
            ]
            query = PublicRecordsQuery(
                source=self.adapter._source_metadata(),
                jurisdiction=JurisdictionMetadata(
                    jurisdiction_id=alternative.county_geoid,
                    name=f"{alternative.county} County, Washington",
                    state_code="WA",
                    county_fips=alternative.county_geoid[-3:],
                    locality=f"{alternative.county} County",
                    metadata={"state_fips": "53"},
                ),
                query=QueryMetadata(
                    operation=getattr(args, "shared_operation", "search"),
                    parameters={
                        "county": alternative.key,
                        "selector": getattr(args, "shared_selector", None),
                    },
                ),
            )
            return PublicRecordsResult.failure(
                query,
                ResultStatus.UNAVAILABLE,
                [
                    PublicRecordsError(
                        code="county_not_in_digital_archives_land_series",
                        message=(
                            f"{alternative.county} County is not represented "
                            "in the verified Digital Archives land-record title "
                            "inventory; use its separately attributable "
                            "official recorder route"
                        ),
                        category="source_coverage",
                        retryable=False,
                        details={
                            "recorder_alternative": record,
                            "assessor_alternatives": assessor_complements,
                            "other_official_complements": other_complements,
                        },
                    )
                ],
            )

        result = self.adapter.execute(args)
        expected_geoid = getattr(args, "shared_expected_county_geoid", None)
        if expected_geoid is None or result.status not in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }:
            return result
        observed_geoid = result.query.jurisdiction.jurisdiction_id
        if observed_geoid == expected_geoid:
            return result
        return PublicRecordsResult.failure(
            PublicRecordsQuery(
                source=result.query.source,
                jurisdiction=getattr(args, "shared_expected_jurisdiction"),
                query=result.query.query,
            ),
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="record_outside_requested_county",
                    message=(
                        "The Digital Archives response resolved to a different "
                        "county than the shared query requested"
                    ),
                    category="source_scope",
                    retryable=False,
                    details={
                        "requested_county_geoid": expected_geoid,
                        "observed_county_geoid": observed_geoid,
                    },
                )
            ],
        )


WASHINGTON_LAND_RECORDS_ADAPTER = _WashingtonLandRecordsAdapter(
    query_washington_digital_archives_land
)


def _washington_taxsifter_alternatives(
    tenant: Any,
) -> list[dict[str, Any]]:
    """Return separately attributable official pivots for one county tenant."""

    alternatives: list[dict[str, Any]] = [
        {
            "kind": "statewide_current_parcel_representation",
            "source_id": query_washington_parcels.ECOLOGY_SOURCE_ID,
            "lineage_id": query_washington_parcels.LINEAGE_ID,
            "county_geoid": tenant.county_geoid,
            "operations": ["parcel", "address", "map"],
            "relationship": (
                "same_county_assessor_origin_not_independent_corroboration"
            ),
        },
        {
            "kind": "interactive_official_county_property_portal",
            "source_id": tenant.source_id,
            "url": tenant.portal_root,
            "county_geoid": tenant.county_geoid,
            "operations": ["parcel", "owner", "address", "tax"],
            "relationship": "alternate_access_path_to_same_county_source",
        },
    ]
    if tenant.digital_archives_title_id is not None:
        alternatives.append(
            {
                "kind": "washington_digital_archives_recorded_land_title",
                "source_id": WASHINGTON_LAND_RECORDS_SOURCE_ID,
                "lineage_id": query_washington_taxsifter.RECORDER_LINEAGE,
                "county_geoid": tenant.county_geoid,
                "title_id": tenant.digital_archives_title_id,
                "url": (
                    "https://digitalarchives.wa.gov/Collections/TitleInfo/"
                    f"{tenant.digital_archives_title_id}"
                ),
                "operations": ["owner", "instrument"],
                "relationship": "separate_county_auditor_instrument_index",
            }
        )
    if tenant.key == "mason":
        alternatives.extend(
            [
                {
                    "kind": "mason_county_tax_parcels_gis",
                    "name": "Mason County TaxParcels GIS",
                    "source_id": MASON_COUNTY_TAX_PARCELS_SOURCE_ID,
                    "lineage_id": query_washington_taxsifter.MAP_LINEAGE,
                    "county_geoid": tenant.county_geoid,
                    "url": query_mason_county_tax_parcels.LAYER_URL,
                    "operations": ["parcel", "owner", "address", "map"],
                    "record_grain": "parcel_assessment_geometry",
                    "relationship": (
                        "distinct_county_gis_assessment_representation"
                    ),
                },
                {
                    "kind": "mason_county_auditor_eagleweb",
                    "name": "Mason County Auditor EagleWeb",
                    "lineage_id": query_washington_taxsifter.RECORDER_LINEAGE,
                    "county_geoid": tenant.county_geoid,
                    "url": (
                        "https://recording.masoncountywa.gov/recorder/web/"
                    ),
                    "operations": [
                        "grantor",
                        "grantee",
                        "document",
                        "date",
                        "legal-description",
                    ],
                    "record_grain": "recorded_instrument_index",
                    "relationship": (
                        "current_county_auditor_index_same_recorder_lineage_"
                        "as_state_archive"
                    ),
                },
            ]
        )
    return alternatives


@dataclass(frozen=True)
class _WashingtonTaxSifterAdapter:
    """Preserve source failures while adding county-specific official pivots."""

    adapter: Any

    def execute(
        self,
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> PublicRecordsResult:
        del access_decision
        result = self.adapter.execute(args)
        if not isinstance(result, PublicRecordsResult):
            raise TypeError("shared TaxSifter routes require a result envelope")
        tenant = self.adapter.TENANTS_BY_SOURCE.get(getattr(args, "source", None))
        if tenant is None:
            return result

        updated_errors: list[PublicRecordsError] = []
        changed = False
        for error in result.errors:
            if error.code != "source_challenge_required":
                updated_errors.append(error)
                continue
            changed = True
            updated_errors.append(
                PublicRecordsError(
                    code=error.code,
                    message=error.message,
                    category=error.category,
                    retryable=error.retryable,
                    details={
                        **dict(error.details),
                        "county_geoid": tenant.county_geoid,
                        "official_alternatives": (
                            _washington_taxsifter_alternatives(tenant)
                        ),
                    },
                )
            )
        if not changed:
            return result
        return PublicRecordsResult(
            query=result.query,
            status=result.status,
            retrieved_at=result.retrieved_at,
            records=result.records,
            next_cursor=result.next_cursor,
            raw_artifact_refs=result.raw_artifact_refs,
            warnings=result.warnings,
            errors=updated_errors,
            schema_version=result.schema_version,
        )


WASHINGTON_TAXSIFTER_ADAPTER = _WashingtonTaxSifterAdapter(
    query_washington_taxsifter
)


class _ExplicitLimitAction(argparse.Action):
    """Store a result limit and remember that the caller selected it."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        del parser, option_string
        setattr(namespace, self.dest, values)
        setattr(namespace, "limit_explicit", True)


def _remote_common(
    args: argparse.Namespace,
    *,
    default_timeout: float = 30.0,
) -> dict[str, Any]:
    return {
        "limit": args.limit,
        "cursor": args.cursor,
        "page_size": args.page_size,
        "max_records": args.max_records,
        "timeout": (args.timeout if args.timeout is not None else default_timeout),
        "minimum_interval": args.minimum_interval,
        "catalog_db": args.catalog_db,
        "output": None,
        "json_out": False,
    }


def _nc_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    county_fips = args.county_fips
    if (
        county_fips is None
        and args.jurisdiction
        and re.fullmatch(r"37\d{3}", args.jurisdiction)
    ):
        county_fips = args.jurisdiction
    return argparse.Namespace(
        **_remote_common(args),
        command=adapter_command,
        query=args.query,
        county_fips=county_fips,
        geometry=args.geometry or args.command == "map",
    )


def _bexar_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    return argparse.Namespace(
        **_remote_common(args),
        command=adapter_command,
        query=args.query,
        geometry=args.geometry or args.command == "map",
        year=args.tax_year,
    )


def _denver_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    jurisdiction = str(args.jurisdiction or "").strip()
    if jurisdiction and jurisdiction not in {"08", "08031"}:
        raise ValueError(
            "Denver parcel queries use Colorado GEOID 08 or Denver GEOID 08031"
        )
    common = _remote_common(args)
    common["limit"] = args.limit if args.limit_explicit else None
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        geometry=args.geometry or args.command == "map",
    )


def _denver_delinquent_tax_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate common property selectors to the annual Treasury workbook."""

    jurisdiction = str(args.jurisdiction or "").strip()
    if jurisdiction and jurisdiction not in {"08", "08031"}:
        raise ValueError(
            "Denver delinquent-tax queries use Colorado GEOID 08 or Denver GEOID 08031"
        )
    caller_limit = args.limit if args.limit_explicit else None
    if args.max_records is not None:
        caller_limit = (
            min(caller_limit, args.max_records)
            if caller_limit is not None
            else args.max_records
        )
    values = {
        "command": adapter_command,
        "artifact": None,
        "query": None,
        "parcel": None,
        "owner": None,
        "address": None,
        "tax_year": args.tax_year,
        "tax_sale_only": False,
        "partially_paid_only": False,
        "max_records": caller_limit,
        "cursor": args.cursor,
        "timeout": args.timeout if args.timeout is not None else 60.0,
        "minimum_interval": args.minimum_interval,
        "retry_attempts": 3,
        "chunk_size": 1024 * 1024,
        "max_download_bytes": None,
        "max_archive_members": (
            query_denver_delinquent_tax.DEFAULT_MAX_ARCHIVE_MEMBERS
        ),
        "max_uncompressed_bytes": (
            query_denver_delinquent_tax.DEFAULT_MAX_UNCOMPRESSED_BYTES
        ),
        "max_member_uncompressed_bytes": (
            query_denver_delinquent_tax.DEFAULT_MAX_MEMBER_UNCOMPRESSED_BYTES
        ),
        "max_compression_ratio": (
            query_denver_delinquent_tax.DEFAULT_MAX_COMPRESSION_RATIO
        ),
        "catalog_db": args.catalog_db,
        "catalog_config": str(query_denver_delinquent_tax.DEFAULT_CATALOG_CONFIG_PATH),
        "output": None,
        "json_out": False,
    }
    if args.command == "owner":
        values["owner"] = args.query
    elif args.command == "address":
        values["address"] = args.query
    elif args.command in {"parcel", "account"}:
        values["parcel"] = args.query
    else:
        values["query"] = args.query
    return argparse.Namespace(**values)


def _denver_foreclosure_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate common property selectors to Public Trustee GTS."""

    jurisdiction = str(args.jurisdiction or "").strip()
    if jurisdiction and jurisdiction not in {"08", "08031"}:
        raise ValueError(
            "Denver Public Trustee queries use Colorado GEOID 08 or Denver GEOID 08031"
        )
    caller_limit = args.limit if args.limit_explicit else None
    if args.max_records is not None:
        caller_limit = (
            min(caller_limit, args.max_records)
            if caller_limit is not None
            else args.max_records
        )
    values = {
        "command": adapter_command,
        "foreclosure_number": None,
        "grantor": None,
        "owner": None,
        "zip_code": None,
        "street": None,
        "subdivision": None,
        "status": None,
        "ned_from": None,
        "ned_to": None,
        "sold_from": None,
        "sold_to": None,
        "sale_from": None,
        "sale_to": None,
        "expedited": None,
        "show_all": False,
        "limit": caller_limit,
        "cursor": args.cursor,
        "timeout": args.timeout if args.timeout is not None else 30.0,
        "minimum_interval": args.minimum_interval,
        "max_attempts": 3,
        "catalog_db": args.catalog_db,
        "catalog_config": str(query_denver_foreclosures.DEFAULT_CATALOG_CONFIG_PATH),
        "output": None,
        "json_out": False,
    }
    if args.command == "owner":
        values["owner"] = args.query
    elif args.command == "address":
        values["street"] = args.query
    else:
        values["foreclosure_number"] = args.query
    return argparse.Namespace(**values)


def _delaware_firstmap_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    jurisdiction = str(args.jurisdiction or "").strip()
    county_selector = str(args.county_fips or "").strip()
    selector = county_selector or jurisdiction
    county_by_code = {
        "001": "Kent",
        "10001": "Kent",
        "003": "New Castle",
        "10003": "New Castle",
        "005": "Sussex",
        "10005": "Sussex",
    }
    if jurisdiction and jurisdiction != "10" and jurisdiction not in county_by_code:
        raise ValueError(
            "Delaware FirstMap queries use Delaware GEOID 10 or a Delaware county GEOID"
        )
    county = (
        None
        if selector in {"", "10"}
        else county_by_code.get(
            selector,
            selector,
        )
    )
    caller_ceiling = (
        args.max_records
        if args.max_records is not None
        else (args.limit if args.limit_explicit else None)
    )
    return argparse.Namespace(
        command=adapter_command,
        pin=args.query,
        county=county,
        limit=args.limit,
        geometry=args.geometry or args.command == "map",
        out_sr=4326,
        page_size=args.page_size,
        max_records=caller_ceiling,
        timeout=args.timeout if args.timeout is not None else 30.0,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        catalog_db=args.catalog_db,
        output=None,
        json_out=False,
    )


def _arlington_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    jurisdiction = str(args.jurisdiction or "").strip()
    if jurisdiction and jurisdiction not in {"51", "51013"}:
        raise ValueError(
            "Arlington property queries use Virginia GEOID 51 or Arlington "
            "County GEOID 51013"
        )
    common = _remote_common(args)
    common["limit"] = args.limit if args.limit_explicit else None
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        geometry=args.geometry or args.command == "map",
    )


def _cook_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    common = _remote_common(args)
    common.pop("max_records")
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        tax_year=args.tax_year,
    )


def _md_county_code(args: argparse.Namespace) -> str | None:
    if args.county_fips:
        return args.county_fips
    jurisdiction = str(args.jurisdiction or "").strip()
    if not jurisdiction or jurisdiction == "24":
        return None
    for code, (geoid, _name) in query_md_property.COUNTY_GEOIDS.items():
        if jurisdiction == geoid:
            return code
    return jurisdiction


def _md_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    common = _remote_common(args)
    common.pop("max_records")
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        county_code=_md_county_code(args),
    )


def _md_plats_county_code(
    args: argparse.Namespace,
    *,
    required: bool,
) -> str | None:
    """Resolve shared Maryland geography to a PLATS.NET county code."""

    values = [
        str(value).strip()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    ]
    jurisdiction = str(args.jurisdiction or "").strip()
    if jurisdiction.upper() not in {"", "24", "MD", "US-MD"}:
        values.insert(0, jurisdiction)

    resolved: set[str] = set()
    for value in values:
        upper = value.upper()
        normalized = re.sub(
            r"[^a-z0-9]+",
            " ",
            value.casefold(),
        ).strip()
        normalized_without_county = re.sub(
            r"\s+(?:county|city)$",
            "",
            normalized,
        )
        match = next(
            (
                code
                for code, (geoid, name) in query_md_plats.COUNTY_GEOIDS.items()
                if upper in {code, geoid, geoid[-3:]}
                or normalized
                == re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()
                or normalized_without_county
                == re.sub(
                    r"\s+(?:county|city)$",
                    "",
                    re.sub(
                        r"[^a-z0-9]+",
                        " ",
                        name.casefold(),
                    ).strip(),
                )
            ),
            None,
        )
        if match is None:
            raise ValueError(
                "Maryland Plats county must be a PLATS.NET code, Maryland "
                "county-equivalent GEOID, FIPS suffix, or county name"
            )
        resolved.add(match)
    if len(resolved) > 1:
        raise ValueError(
            "Maryland Plats geography selectors refer to different counties"
        )
    if resolved:
        return next(iter(resolved))
    if required:
        raise ValueError(
            "Maryland Plats search and detail operations require a county"
        )
    return None


def _md_plats_source_date(args: argparse.Namespace) -> str | None:
    values = [
        str(value).strip()
        for value in (args.from_date, args.to_date)
        if value not in (None, "")
    ]
    if len(set(values)) > 1:
        raise ValueError(
            "PLATS.NET publishes an exact filing-date search, not a date range"
        )
    if not values:
        return None
    value = values[0].replace("-", "/")
    if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", value):
        raise ValueError("Maryland Plats dates must use YYYY-MM-DD")
    return value


def _md_plats_accession(
    value: str,
) -> tuple[str | None, str, str, str] | None:
    match = re.fullmatch(
        r"(?:(?P<county>[A-Za-z]{2}):)?\s*"
        r"(?:MSA\s+)?(?P<qualifier>[CS])\s*"
        r"(?P<series>\d+)\s*-\s*"
        r"(?P<unit>[A-Za-z0-9.-]+)",
        value.strip(),
        re.IGNORECASE,
    )
    if match is None:
        return None
    county = match.group("county")
    return (
        county.upper() if county else None,
        match.group("qualifier").upper(),
        match.group("series"),
        match.group("unit"),
    )


def _md_plats_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property operations to the verified WebForms archive."""

    if args.tax_year is not None:
        raise ValueError(
            "Maryland Plats uses its filing-date field rather than tax year"
        )
    if args.geometry:
        raise ValueError("Maryland Plats records do not publish parcel geometry")
    if args.artifact_path:
        raise ValueError(
            "Maryland Plats downloads one source-published URL at a time"
        )

    selector = str(args.query or "").strip()
    search_field = (
        str(args.search_field or "")
        .strip()
        .casefold()
        .replace("_", "-")
    )
    source_date = _md_plats_source_date(args)
    county = _md_plats_county_code(
        args,
        required=adapter_command in {
            "search",
            "subdivision",
            "survey",
        },
    )
    accession = _md_plats_accession(selector) if selector else None
    argv: list[str]
    supports_cursor = False

    if adapter_command == "counties":
        if selector or county or args.cursor or source_date:
            raise ValueError(
                "Maryland Plats discovery lists the statewide county routes"
            )
        argv = ["counties"]
    elif adapter_command == "probe":
        if selector or county or args.cursor or source_date:
            raise ValueError(
                "Maryland Plats probe uses its fixed verified sentinel"
            )
        argv = ["probe"]
    elif adapter_command == "download":
        if not selector or not args.destination:
            raise ValueError(
                "Maryland Plats download requires an artifact URL and "
                "--destination"
            )
        if county or args.cursor or source_date:
            raise ValueError(
                "Maryland Plats download is selected by its exact artifact URL"
            )
        argv = ["download", selector, args.destination]
    elif adapter_command == "instrument" and accession is not None:
        accession_county, qualifier, series, unit = accession
        if accession_county:
            if county and county != accession_county:
                raise ValueError(
                    "Maryland Plats accession and geography select different "
                    "counties"
                )
            county = accession_county
        if county is None:
            raise ValueError(
                "Maryland Plats exact accession lookup requires a county"
            )
        if args.cursor or source_date:
            raise ValueError(
                "Maryland Plats exact accession lookup does not use search "
                "continuation or filing-date filters"
            )
        argv = ["plat", county, qualifier, series, unit]
    else:
        if not selector and source_date is None:
            raise ValueError("Maryland Plats search requires a selector")
        if county is None:
            raise ValueError("Maryland Plats search requires a county")
        supports_cursor = True
        if source_date and (
            adapter_command == "instrument"
            or search_field
            in {
                "accession",
                "archive",
                "msa",
                "series",
                "book-page",
                "book/page",
                "reference",
                "plat",
                "plat-number",
                "box",
                "right-of-way",
                "right-of-way-plat",
                "row",
            }
        ):
            raise ValueError(
                "Maryland Plats filing-date filters use the advanced search "
                "fields"
            )
        book_page = re.fullmatch(
            r"\s*([^/]+?)\s*/\s*([^/]+?)\s*",
            selector,
        )
        if search_field in {"accession", "archive", "msa", "series"}:
            if accession is None:
                raise ValueError(
                    "Maryland Plats archive selectors use C1136-1, "
                    "S17-2, or COUNTY:C1136-1"
                )
            accession_county, qualifier, series, unit = accession
            if accession_county and accession_county != county:
                raise ValueError(
                    "Maryland Plats accession and geography select different "
                    "counties"
                )
            argv = [
                "search",
                county,
                "--mode",
                "series",
                "--qualifier",
                qualifier,
                "--series",
                series,
                "--unit",
                unit,
            ]
        elif search_field in {"book-page", "book/page", "reference"}:
            if book_page is None:
                raise ValueError(
                    "Maryland Plats book/page selectors use BOOK/PAGE"
                )
            argv = [
                "search",
                county,
                "--mode",
                "basic",
                "--book",
                book_page.group(1),
                "--page",
                book_page.group(2),
            ]
        elif search_field in {"plat", "plat-number", "box"} or (
            adapter_command == "instrument"
            and search_field in {"", "any"}
            and accession is None
        ):
            argv = [
                "search",
                county,
                "--mode",
                "basic",
                "--plat",
                selector,
            ]
        elif search_field in {
            "right-of-way",
            "right-of-way-plat",
            "row",
        }:
            argv = [
                "search",
                county,
                "--mode",
                "basic",
                "--right-of-way",
                selector,
            ]
        else:
            allowed = {
                "",
                "any",
                "description",
                "subdivision",
                "survey",
                "clerk",
                "clerk-initials",
                "date",
            }
            if search_field not in allowed:
                raise ValueError(
                    "Maryland Plats search fields are description, "
                    "subdivision, survey, date, clerk-initials, book-page, "
                    "plat, right-of-way, or archive accession"
                )
            argv = ["search", county, "--mode", "advanced"]
            if search_field == "date":
                date_value = selector.replace("-", "/")
                if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", date_value):
                    raise ValueError(
                        "Maryland Plats date selectors use YYYY-MM-DD"
                    )
                if source_date and source_date != date_value:
                    raise ValueError(
                        "Maryland Plats date selectors disagree"
                    )
                argv.extend(["--date", source_date or date_value])
                selector = ""
            elif source_date:
                argv.extend(["--date", source_date])
            if selector:
                if search_field in {"clerk", "clerk-initials"}:
                    argv.extend(["--clerk-initials", selector])
                else:
                    argv.extend(["--description", selector])
        argv.append("--include-no-images")
        if args.limit_explicit:
            argv.extend(["--limit", str(args.limit)])

    if args.cursor:
        if not supports_cursor:
            raise ValueError(
                f"Maryland Plats {args.command} does not use a continuation "
                "cursor"
            )
        argv.extend(["--cursor", args.cursor])
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_md_plats.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--max-attempts",
            "3",
        ]
    )
    try:
        return query_md_plats.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Maryland Plats selector for {adapter_command}"
        ) from error


def _md_mdp_county_code(args: argparse.Namespace) -> str | None:
    """Resolve shared Maryland geography selectors to SDAT county codes."""

    jurisdiction = str(args.jurisdiction or "").strip()
    county_values = [
        str(value).strip()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    ]
    if jurisdiction.upper() not in {"", "24", "MD", "US-MD"}:
        if not (
            len(jurisdiction) == 5
            and jurisdiction.isdigit()
            and jurisdiction.startswith("24")
        ):
            raise ValueError(
                "Maryland Parcel Points queries use Maryland GEOID 24 or a "
                "Maryland county-equivalent GEOID"
            )
        county_values.insert(0, jurisdiction)
    if not county_values:
        return None

    resolved_codes: set[str] = set()
    for value in county_values:
        normalized_name = re.sub(
            r"[^a-z0-9]+",
            " ",
            value.casefold().replace("county", ""),
        ).strip()
        matched_code = next(
            (
                code
                for code, (geoid, name) in (
                    query_md_mdp_parcel_points.COUNTY_GEOIDS.items()
                )
                if value in {code, geoid, geoid[-3:]}
                or normalized_name
                == re.sub(
                    r"[^a-z0-9]+",
                    " ",
                    name.casefold().replace("county", ""),
                ).strip()
            ),
            None,
        )
        if matched_code is None:
            raise ValueError(
                "Maryland Parcel Points county must be an SDAT code, "
                "Maryland GEOID, county FIPS suffix, or county name"
            )
        resolved_codes.add(matched_code)
    if len(resolved_codes) != 1:
        raise ValueError(
            "Maryland Parcel Points county selectors refer to different "
            "county equivalents"
        )
    return next(iter(resolved_codes))


def _md_mdp_selector_arguments(
    *,
    command: str,
    selector: str,
    requested_field: str,
) -> list[str]:
    """Translate one shared selector without collapsing ACCTID and PARCEL."""

    field = requested_field
    if field in {"", "auto", "any"}:
        account_candidate = "".join(
            character for character in selector if character.isalnum()
        )
        field = "account" if len(account_candidate) == 10 else "address"
    if field in {"account", "acctid", "parcel-account"}:
        return ["--account", selector] if command == "count" else [
            "account",
            selector,
        ]
    if field in {"parcel", "local-parcel", "parcel-coordinate"}:
        return ["--parcel", selector] if command == "count" else [
            "parcel",
            selector,
        ]
    if field in {"address", "situs"}:
        return (
            ["--address", selector]
            if command == "count"
            else ["address", selector]
        )
    if command != "count" and field in {"objectid", "object-id"}:
        return ["objectid", selector]
    filter_fields = {
        "map": "--map",
        "plat": "--plat",
        "grid": "--grid",
        "land-use": "--land-use",
        "zoning": "--zoning",
    }
    if field in filter_fields:
        prefix = [] if command == "count" else ["query"]
        return [*prefix, filter_fields[field], selector]
    raise ValueError(
        "Maryland Parcel Points --search-field must be account/ACCTID, "
        "parcel, address, OBJECTID, map, plat, grid, land-use, or zoning"
    )


def _md_mdp_parcel_points_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the official statewide point layer."""

    if args.artifact_path:
        raise ValueError(
            "Maryland Parcel Points uses the live ArcGIS layer; official "
            "download releases use the separate MDP bulk source family"
        )
    if args.tax_year is not None:
        raise ValueError(
            "Maryland Parcel Points publishes source freshness fields rather "
            "than a native assessment-year selector"
        )
    if args.from_date or args.to_date:
        raise ValueError(
            "Maryland Parcel Points does not publish a native date-range "
            "search for this operation"
        )

    selector = str(args.query or "").strip()
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    county_code = _md_mdp_county_code(args)
    record_commands = {
        "list",
        "query",
        "account",
        "parcel",
        "address",
        "objectid",
        "point",
        "bbox",
    }

    if adapter_command in {"metadata", "discovery", "probe"}:
        argv = [adapter_command]
    elif adapter_command == "search":
        if not selector:
            raise ValueError("Maryland Parcel Points search requires a selector")
        argv = _md_mdp_selector_arguments(
            command="search",
            selector=selector,
            requested_field=requested_field,
        )
    elif adapter_command in {"account", "address"}:
        argv = [adapter_command, selector]
    elif adapter_command == "map":
        argv = ["account", selector, "--geometry"]
    elif adapter_command == "count":
        argv = ["count"]
        if selector:
            argv.extend(
                _md_mdp_selector_arguments(
                    command="count",
                    selector=selector,
                    requested_field=requested_field,
                )
            )
    elif adapter_command in {"land-use", "survey"}:
        option = "--land-use" if adapter_command == "land-use" else "--plat"
        argv = ["query", option, selector]
    elif adapter_command == "point":
        values = [value.strip() for value in selector.split(",")]
        if len(values) != 2:
            raise ValueError(
                "Maryland Parcel Points point query must be longitude,latitude"
            )
        argv = ["point", *values]
    elif adapter_command == "bbox":
        values = [value.strip() for value in selector.split(",")]
        if len(values) != 4:
            raise ValueError(
                "Maryland Parcel Points bbox query must be "
                "west,south,east,north"
            )
        argv = ["bbox", *values]
    else:
        raise ValueError(
            f"Maryland Parcel Points does not translate {args.command}"
        )

    if county_code and argv[0] not in {"metadata", "discovery", "probe"}:
        argv.extend(["--county-code", county_code])
    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and argv[0] in record_commands:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor:
        if argv[0] not in record_commands:
            raise ValueError(
                f"Maryland Parcel Points {args.command} does not use a "
                "continuation cursor"
            )
        argv.extend(["--cursor", args.cursor])
    if (
        args.geometry
        and argv[0] in record_commands
        and "--geometry" not in argv
    ):
        argv.append("--geometry")
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_md_mdp_parcel_points.DEFAULT_TIMEOUT
            ),
            "--retry-attempts",
            str(query_md_mdp_parcel_points.DEFAULT_RETRY_ATTEMPTS),
        ]
    )
    argv.extend(["--minimum-interval", str(args.minimum_interval)])
    try:
        return query_md_mdp_parcel_points.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Maryland Parcel Points selector for {adapter_command}"
        ) from error


def _md_mdp_property_download_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared release selectors to the three MDP bulk families."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "24", "MD", "US-MD"}:
        if (
            len(jurisdiction) == 5
            and jurisdiction.isdigit()
            and jurisdiction.startswith("24")
        ):
            raise ValueError(
                "Maryland MDP bulk artifacts are statewide and do not apply "
                "a county filter"
            )
        raise ValueError(
            "Maryland MDP downloads use Maryland context 24/MD/US-MD"
        )
    if args.county_fips or args.county_selector:
        raise ValueError(
            "Maryland MDP bulk artifacts are statewide and do not apply a "
            "county filter"
        )
    if args.from_date or args.to_date:
        raise ValueError(
            "Maryland MDP bulk release selection does not use a date range; "
            "use --tax-year or --collection-id"
        )
    if args.search_field:
        raise ValueError(
            "Maryland MDP bulk routes expose release and artifact metadata, "
            "not row search fields"
        )
    if args.geometry:
        raise ValueError(
            "Maryland MDP bulk routes inventory artifacts; use the Parcel "
            "Points source for live point geometry"
        )

    source_id = args.source
    dataset_type = str(args.dataset_type or "").strip().casefold()
    component: str | None = None
    family_aliases = {
        query_md_mdp_property_downloads.PARCEL_SOURCE_ID: {
            "",
            "parcel",
            "parcels",
            "parcel-downloads",
        },
        query_md_mdp_property_downloads.CAMA_SOURCE_ID: {
            "",
            "cama",
            "statewide-cama",
        },
        query_md_mdp_property_downloads.SALES_SOURCE_ID: {
            "",
            "sales",
            "property-sales",
            "residential-sales",
        },
    }
    component_aliases = {
        "core": "core",
        "building": "building",
        "bldg": "building",
        "land": "land",
        "subareas": "subareas",
        "subarea": "subareas",
        "suba": "subareas",
        "bundle": "statewide_bundle",
        "statewide-bundle": "statewide_bundle",
        "statewide_bundle": "statewide_bundle",
    }
    if (
        source_id == query_md_mdp_property_downloads.CAMA_SOURCE_ID
        and dataset_type in component_aliases
    ):
        component = component_aliases[dataset_type]
    elif dataset_type not in family_aliases[source_id]:
        raise ValueError(
            f"{source_id} does not use --dataset-type {args.dataset_type}; "
            "select an exact schema workbook with --collection-id"
        )

    selector = str(args.query or "").strip()
    if selector.casefold() in {"", "*", "all"}:
        selector = ""
    release_selector = str(args.collection_id or "").strip()
    if selector:
        if release_selector and release_selector != selector:
            raise ValueError("Maryland MDP release selectors conflict")
        release_selector = selector
    release_selector = release_selector or None
    transfer_controls_selected = any(
        (
            not args.resume,
            args.expected_sha256 is not None,
            args.max_download_bytes is not None,
            args.chunk_size is not None,
        )
    )
    selected_limit = _selected_live_limit(args)

    if args.artifact_path:
        if args.command not in {"manifest", "discovery"}:
            raise ValueError(
                "Use shared manifest or discovery with --artifact-path to "
                "inspect a local Maryland MDP archive"
            )
        if (
            args.tax_year is not None
            or component is not None
            or args.cursor
            or selected_limit is not None
            or args.destination
            or args.range_bytes is not None
            or transfer_controls_selected
        ):
            raise ValueError(
                "Local Maryland MDP inspection uses the artifact filename "
                "and optional exact --collection-id"
            )
        argv = [
            "inspect",
            args.artifact_path,
            "--source",
            source_id,
        ]
        if release_selector:
            argv.extend(["--release", release_selector])
    elif adapter_command == "manifest":
        if args.destination:
            raise ValueError(
                "Maryland MDP release discovery does not use --destination"
            )
        if args.range_bytes is not None:
            raise ValueError(
                "Maryland MDP manifest does not use --range-bytes"
            )
        if transfer_controls_selected:
            raise ValueError(
                "Maryland MDP manifest does not use transfer controls"
            )
        argv = ["manifest", "--source", source_id]
        if release_selector:
            argv.extend(["--release", release_selector])
        if args.tax_year is not None:
            argv.extend(["--year", str(args.tax_year)])
        if component:
            argv.extend(["--component", component])
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif adapter_command == "probe":
        if args.cursor:
            raise ValueError(
                "Maryland MDP artifact probes do not use a continuation cursor"
            )
        if args.destination:
            raise ValueError(
                "Maryland MDP artifact probes do not use --destination"
            )
        if transfer_controls_selected:
            raise ValueError(
                "Maryland MDP artifact probes do not use transfer controls"
            )
        if selected_limit is not None:
            raise ValueError(
                "Maryland MDP artifact probes select one release and do not "
                "use row limits"
            )
        argv = ["probe", "--source", source_id]
        if release_selector:
            argv.extend(["--release", release_selector])
        if args.tax_year is not None:
            argv.extend(["--year", str(args.tax_year)])
        if component:
            argv.extend(["--component", component])
        if args.range_bytes is not None:
            argv.extend(["--sample-bytes", str(args.range_bytes)])
    elif adapter_command == "download":
        if args.cursor:
            raise ValueError(
                "Maryland MDP artifact transfers do not use a continuation "
                "cursor"
            )
        if args.range_bytes is not None:
            raise ValueError(
                "Maryland MDP artifact transfers do not use --range-bytes"
            )
        if selected_limit is not None:
            raise ValueError(
                "Maryland MDP artifact transfers select one release and do "
                "not use row limits"
            )
        native_command = "download" if args.destination else "prepare"
        argv = [native_command, "--source", source_id]
        if release_selector:
            argv.extend(["--release", release_selector])
        if args.tax_year is not None:
            argv.extend(["--year", str(args.tax_year)])
        if component:
            argv.extend(["--component", component])
        if native_command == "download":
            argv.extend(["--destination", args.destination])
            if not args.resume:
                argv.append("--no-resume")
            if args.expected_sha256:
                argv.extend(["--expected-sha256", args.expected_sha256])
            if args.max_download_bytes is not None:
                argv.extend(
                    [
                        "--max-download-bytes",
                        str(args.max_download_bytes),
                    ]
                )
        elif transfer_controls_selected:
            raise ValueError(
                "Transfer options require --destination; without it shared "
                "download returns a prepared transfer description"
            )
    else:
        raise ValueError(
            f"Maryland MDP downloads do not translate {args.command}"
        )

    if argv[0] != "inspect":
        argv.extend(
            [
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else query_md_mdp_property_downloads.DEFAULT_TIMEOUT
                ),
                "--retry-attempts",
                str(
                    query_md_mdp_property_downloads.DEFAULT_RETRY_ATTEMPTS
                ),
                "--minimum-interval",
                str(args.minimum_interval),
            ]
        )
        if args.chunk_size is not None:
            argv.extend(["--chunk-size", str(args.chunk_size)])
    try:
        return query_md_mdp_property_downloads.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Maryland MDP download selector for {adapter_command}"
        ) from error


def _miami_dade_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    return argparse.Namespace(
        **_remote_common(args),
        command=adapter_command,
        query=args.query,
        unit=None,
        geometry=args.geometry or args.command == "map",
    )


def _ebr_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    values = {
        **_remote_common(args),
        "command": adapter_command,
        "parish": query_la_property.DEFAULT_PARISH,
        "max_results": args.limit,
    }
    if adapter_command == "parcel":
        values["assessment_no"] = args.query
    else:
        values["query"] = args.query
    return argparse.Namespace(**values)


def _orleans_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    common = _remote_common(args, default_timeout=60.0)
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        geometry=args.geometry or args.command == "map",
        tax_year=args.tax_year,
    )


def _oregon_taxlots_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate unified selectors to one publisher-scoped Oregon layer."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if (
        jurisdiction
        and jurisdiction not in {"41", "OR"}
        and not re.fullmatch(
            r"41\d{3}",
            jurisdiction,
        )
    ):
        raise ValueError(
            "Oregon taxlot queries use Oregon GEOID 41, OR, or an Oregon "
            "county GEOID beginning with 41"
        )
    county = args.county_fips
    if county is None and jurisdiction and re.fullmatch(r"41\d{3}", jurisdiction):
        county = jurisdiction

    field_by_operation = {
        "search": "auto",
        "owner": "owner",
        "address": "address",
        "parcel": "parcel",
        "map": "parcel",
        "account": "account",
    }
    common = _remote_common(args)
    common["limit"] = args.limit
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        source=args.source,
        field=field_by_operation[args.command],
        county=county,
        geometry=args.geometry or args.command == "map",
        retry_attempts=3,
    )


def _oregon_benton_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property operations to one Benton component."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", "41003"}:
        raise ValueError(
            "Benton County property sources use Oregon GEOID 41, OR, or "
            "Benton County GEOID 41003"
        )

    common = _remote_common(args)
    common.update(
        retry_attempts=3,
        output=None,
        json_out=False,
    )
    if args.source == OREGON_BENTON_TAXLOT_SOURCE_ID:
        aliases = {
            "parcel": "map_taxlot",
            "taxlot": "map_taxlot",
            "map-taxlot": "map_taxlot",
            "ortaxlot": "or_taxlot",
            "or-taxlot": "or_taxlot",
            "map": "map_number",
            "map-number": "map_number",
        }
        selected_field = aliases.get(
            str(args.search_field or "").strip().casefold(),
            str(args.search_field or "").strip().casefold(),
        )
        if args.command == "search":
            field = selected_field or "auto"
        elif args.command in {"parcel", "map"}:
            field = selected_field or "map_taxlot"
            if field not in {
                "account",
                "map_taxlot",
                "or_taxlot",
                "map_number",
            }:
                raise ValueError(
                    "Benton parcel/map lookup supports account, map_taxlot, "
                    "or_taxlot, or map_number"
                )
        else:
            field = {
                "owner": "owner",
                "address": "address",
                "account": "account",
            }[args.command]
        return argparse.Namespace(
            **common,
            command=adapter_command,
            query=args.query,
            field=field,
            geometry=args.geometry or args.command == "map",
        )

    if args.source == OREGON_BENTON_BULK_SOURCE_ID:
        if adapter_command == "bulk-manifest":
            return argparse.Namespace(
                **common,
                command=adapter_command,
            )
        return argparse.Namespace(
            **common,
            command="artifact-probe",
            component="bulk",
            artifact=args.query,
            range_bytes=8,
        )

    if args.source == OREGON_BENTON_MAP_SOURCE_ID:
        if adapter_command == "maps":
            map_number = args.query.strip()
            return argparse.Namespace(
                **common,
                command="maps",
                map_number=None if map_number == "*" else map_number,
                match=(
                    args.search_field
                    if args.search_field in {"exact", "prefix", "contains"}
                    else "exact"
                ),
                map_kind="all",
                updated_after=None,
            )
        return argparse.Namespace(
            **common,
            command="artifact-probe",
            component="map",
            artifact=args.query,
            range_bytes=8,
        )

    raise ValueError(f"unknown Benton property component: {args.source}")


def _oregon_lincoln_propertyweb_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to Lincoln County PropertyWeb search."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", "41041"}:
        raise ValueError("Lincoln County PropertyWeb serves Oregon GEOID 41041")
    county = str(args.county_fips or "").strip()
    if county and county not in {"041", "41041"}:
        raise ValueError(
            "Lincoln County PropertyWeb uses county code 041 or GEOID 41041"
        )
    return argparse.Namespace(
        command=adapter_command,
        term=args.query,
        tax_year=args.tax_year,
        property_value_tax_year=args.tax_year,
        property_types=query_oregon_lincoln_propertyweb.DEFAULT_PROPERTY_TYPES,
        sort="property_id",
        sort_order="asc",
        limit=args.limit,
        cursor=args.cursor,
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_lincoln_propertyweb.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _validate_oregon_county_context(
    args: argparse.Namespace,
    *,
    county_geoid: str,
    county_name: str,
) -> None:
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", county_geoid}:
        raise ValueError(f"{county_name} source serves Oregon GEOID {county_geoid}")
    county = str(args.county_fips or "").strip()
    if county and county not in {county_geoid[-3:], county_geoid}:
        raise ValueError(
            f"{county_name} uses county code {county_geoid[-3:]} or "
            f"GEOID {county_geoid}"
        )


def _oregon_yamhill_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one Yamhill property component."""

    _validate_oregon_county_context(
        args,
        county_geoid=query_oregon_yamhill_property.COUNTY_GEOID,
        county_name="Yamhill County",
    )
    source_id = args.source
    requested_field = str(args.search_field or "").strip().casefold()
    if source_id == query_oregon_yamhill_property.ASCEND_SOURCE_ID:
        default_field = {
            "search": "auto",
            "address": "address",
            "account": "account",
            "parcel": "alternate",
        }[args.command]
    else:
        default_field = {
            "search": "auto",
            "owner": "owner",
            "address": "address",
            "account": "account",
            "parcel": "map_taxlot",
            "map": "map_taxlot",
            "event": "native_id",
            "instrument": "recording",
        }[args.command]
    return argparse.Namespace(
        command=adapter_command,
        source=source_id,
        query=args.query,
        field=requested_field or default_field,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        city="",
        state="",
        postal_code="",
        tax_year=args.tax_year,
        page_size=(
            args.page_size
            if args.page_size is not None
            else query_oregon_yamhill_property.DEFAULT_PAGE_SIZE
        ),
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_yamhill_property.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _oregon_clackamas_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to AscendWeb or the county CMap layer."""

    _validate_oregon_county_context(
        args,
        county_geoid=query_oregon_clackamas_property.COUNTY_GEOID,
        county_name="Clackamas County",
    )
    requested_field = str(args.search_field or "").strip().casefold()
    if args.source == query_oregon_clackamas_property.ASCEND_SOURCE_ID:
        default_field = {
            "search": "auto",
            "address": "address",
            "account": "account",
        }[args.command]
    else:
        default_field = {
            "search": "auto",
            "address": "address",
            "account": "account",
            "parcel": "map_taxlot",
            "map": "map_taxlot",
            "instrument": "recording",
        }[args.command]
    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        query=args.query,
        field=requested_field or default_field,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        city="",
        state="",
        postal_code="",
        tax_year=args.tax_year,
        page_size=(
            args.page_size
            if args.page_size is not None
            else query_oregon_clackamas_property.DEFAULT_PAGE_SIZE
        ),
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_clackamas_property.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _oregon_wasco_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to a Wasco account, taxlot, or survey layer."""

    _validate_oregon_county_context(
        args,
        county_geoid=query_oregon_wasco_property.COUNTY_GEOID,
        county_name="Wasco County",
    )
    requested_field = str(args.search_field or "").strip()
    if args.source == query_oregon_wasco_property.ASCEND_SOURCE_ID:
        default_field = {
            "search": "auto",
            "address": "address",
            "account": "account",
            "parcel": "alternate",
        }[args.command]
    elif args.source == query_oregon_wasco_property.TAXLOT_SOURCE_ID:
        default_field = {
            "search": "auto",
            "owner": "owner",
            "account": "account",
            "parcel": "taxlot",
            "map": "taxlot",
        }[args.command]
    else:
        default_field = "auto"
    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        value=args.query,
        account=args.query,
        field=requested_field or default_field,
        city=None,
        state=None,
        postal_code=None,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        tax_year=args.tax_year,
        page_size=(
            args.page_size
            if args.page_size is not None
            else query_oregon_wasco_property.DEFAULT_PAGE_SIZE
        ),
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_wasco_property.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _oregon_washington_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one Washington County component."""

    _validate_oregon_county_context(
        args,
        county_geoid=query_oregon_washington_property.COUNTY_GEOID,
        county_name="Washington County",
    )
    source_id = args.source
    requested_field = str(args.search_field or "").strip()
    common = {
        "timeout": (
            args.timeout
            if args.timeout is not None
            else query_oregon_washington_property.DEFAULT_TIMEOUT
        ),
        "minimum_interval": args.minimum_interval,
        "retry_attempts": 3,
        "output": None,
        "json_out": False,
    }
    if source_id == query_oregon_washington_property.SURVEY_API_SOURCE_ID:
        if adapter_command == "survey-detail":
            return argparse.Namespace(
                **common,
                command=adapter_command,
                kind="taxlot",
                uid=args.query,
            )
        kind = "plat" if args.command == "instrument" else "survey"
        default_field = "docnumber" if kind == "plat" else "surveynumber"
        return argparse.Namespace(
            **common,
            command=adapter_command,
            kind=kind,
            query=args.query,
            field=requested_field.casefold() or default_field,
            filter=[],
            limit=args.limit,
            cursor=args.cursor,
        )
    if source_id == query_oregon_washington_property.SURVEY_MAP_SOURCE_ID:
        layer = "survey-taxlots" if args.command in {"parcel", "map"} else "surveys"
        default_field = "TLID" if layer == "survey-taxlots" else "SurvNum"
        return argparse.Namespace(
            **common,
            command=adapter_command,
            layer=layer,
            query=args.query,
            field=requested_field or default_field,
            where=None,
            match="exact",
            limit=args.limit,
            cursor=args.cursor,
            geometry=args.geometry or args.command == "map",
            out_sr="4326",
        )
    if source_id == query_oregon_washington_property.TAXLOT_SOURCE_ID:
        return argparse.Namespace(
            **common,
            command=adapter_command,
            query=args.query,
            field=requested_field or "TLNO",
            where=None,
            match="exact",
            limit=args.limit,
            cursor=args.cursor,
            geometry=args.geometry or args.command == "map",
            out_sr="4326",
        )
    if source_id == query_oregon_washington_property.SITUS_SOURCE_ID:
        default_field = {
            "search": "FULLADDRESS",
            "address": "FULLADDRESS",
            "parcel": "TAXLOT",
            "map": "TAXLOT",
            "account": "ACCOUNT_ID",
        }[args.command]
        return argparse.Namespace(
            **common,
            command=adapter_command,
            query=args.query,
            field=requested_field or default_field,
            where=None,
            match=("contains" if args.command in {"search", "address"} else "exact"),
            limit=args.limit,
            cursor=args.cursor,
            geometry=args.geometry or args.command == "map",
            out_sr="4326",
        )
    if source_id == query_oregon_washington_property.INTERMAP_SOURCE_ID:
        return argparse.Namespace(
            **common,
            command=adapter_command,
            tlno=args.query,
            report="tax-map" if args.command == "map" else "parcel",
            include_raw_html=False,
            max_html_bytes=(query_oregon_washington_property.DEFAULT_MAX_HTML_BYTES),
        )
    if source_id == query_oregon_washington_property.TAX_SOURCE_ID:
        return argparse.Namespace(
            **common,
            command=adapter_command,
            account=args.query,
            include_raw_html=False,
            max_html_bytes=(query_oregon_washington_property.DEFAULT_MAX_HTML_BYTES),
        )
    raise ValueError(f"unknown Washington County property source: {source_id}")


def _oregon_washington_case_permit_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to a Washington County case/permit component."""

    adapter = query_oregon_washington_case_permits
    _validate_oregon_county_context(
        args,
        county_geoid=adapter.COUNTY_GEOID,
        county_name="Washington County",
    )
    source_id = args.source
    requested_field = str(args.search_field or "").strip().casefold()
    common = {
        "command": adapter_command,
        "timeout": (
            args.timeout if args.timeout is not None else adapter.DEFAULT_TIMEOUT
        ),
        "minimum_interval": args.minimum_interval,
        "retry_attempts": adapter.DEFAULT_RETRY_ATTEMPTS,
        "output": None,
        "json_out": False,
    }

    if source_id == adapter.CASEFILE_SOURCE_ID:
        if adapter_command == "case-detail":
            return argparse.Namespace(**common, casefile=args.query)
        kind = "taxlot" if args.command == "parcel" else requested_field or "casefile"
        if kind not in adapter.CASE_SEARCH_KINDS:
            supported = ", ".join(sorted(adapter.CASE_SEARCH_KINDS))
            raise ValueError(
                f"Washington County casefile search field must be one of: {supported}"
            )
        return argparse.Namespace(
            **common,
            kind=kind,
            query=args.query,
            filter=[],
            limit=args.limit,
            cursor=args.cursor,
        )

    if source_id == adapter.TAXLOT_ACTIVITY_SOURCE_ID:
        return argparse.Namespace(
            **common,
            taxlot=args.query,
            collection="all",
            limit=args.limit,
            cursor=args.cursor,
        )

    if source_id == adapter.BUILDING_SOURCE_ID:
        kind = {
            "parcel": "taxlot",
            "event": "permit",
            "address": "address",
        }.get(args.command, requested_field or "taxlot")
        if kind not in adapter.BUILDING_SEARCH_KINDS:
            supported = ", ".join(sorted(adapter.BUILDING_SEARCH_KINDS))
            raise ValueError(
                f"Washington County building search field must be one of: {supported}"
            )
        return argparse.Namespace(
            **common,
            kind=kind,
            query=args.query,
            filter=[],
            limit=args.limit,
            cursor=args.cursor,
        )

    if source_id == adapter.PERMIT_REPORT_SOURCE_ID:
        kind = requested_field
        if not kind:
            identifier = str(args.query or "").strip().upper()
            if identifier.startswith("P"):
                kind = "project"
            elif identifier.startswith(("L", "HR")):
                kind = "activity"
            elif identifier.isdigit():
                kind = "inspection"
            else:
                raise ValueError(
                    "Select a Washington County permit report type with "
                    "--search-field project|activity|people|inspection|review"
                )
        if kind not in adapter.REPORT_KINDS:
            supported = ", ".join(sorted(adapter.REPORT_KINDS))
            raise ValueError(
                f"Washington County permit report type must be one of: {supported}"
            )
        return argparse.Namespace(
            **common,
            kind=kind,
            identifier=args.query,
            limit=args.limit,
            cursor=args.cursor,
        )

    if source_id == adapter.ACCELA_SOURCE_ID:
        return argparse.Namespace(**common, casefile=args.query)

    if source_id == adapter.DOCUMENT_ROUTE_SOURCE_ID:
        return argparse.Namespace(**common, casefile=args.query)

    raise ValueError(f"unknown Washington County case/permit source: {source_id}")


def _oregon_multnomah_sail_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one Multnomah County SAIL component."""

    _validate_oregon_county_context(
        args,
        county_geoid=query_oregon_multnomah_sail.COUNTY_GEOID,
        county_name="Multnomah County",
    )
    requested_field = str(args.search_field or "").strip().casefold()
    if args.source == query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID:
        default_field = {
            "search": "auto",
            "owner": "owner",
            "address": "address",
            "account": "account",
            "parcel": "property-id",
            "map": "map-taxlot",
            "instrument": "instrument",
        }[args.command]
    else:
        default_field = "survey-id" if args.command == "instrument" else "auto"
    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        query=args.query,
        field=requested_field or default_field,
        match="auto",
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        page_size=(
            args.page_size
            if args.page_size is not None
            else query_oregon_multnomah_sail.DEFAULT_PAGE_SIZE
        ),
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_multnomah_sail.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        retry_attempts=query_oregon_multnomah_sail.DEFAULT_RETRY_ATTEMPTS,
        output=None,
        json_out=False,
    )


def _oregon_lincoln_taxlot_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to Lincoln County's taxlot-owner WFS."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", "41041"}:
        raise ValueError("Lincoln County taxlot WFS serves Oregon GEOID 41041")
    county = str(args.county_fips or "").strip()
    if county and county not in {"041", "41041"}:
        raise ValueError(
            "Lincoln County taxlot WFS uses county code 041 or GEOID 41041"
        )

    requested_field = str(args.search_field or "").strip().casefold()
    if (
        requested_field
        and requested_field not in query_oregon_lincoln_taxlots.SEARCH_FIELDS
    ):
        raise ValueError(
            "Lincoln County taxlot WFS fields are "
            + ", ".join(sorted(query_oregon_lincoln_taxlots.SEARCH_FIELDS))
        )
    field = (
        requested_field
        or {
            "search": "all",
            "owner": "owner",
            "address": "address",
            "parcel": "parcel",
            "map": "parcel",
            "account": "property",
        }[args.command]
    )
    return argparse.Namespace(
        command=adapter_command,
        query=args.query,
        field=field,
        match="auto",
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        page_size=(
            args.page_size
            if args.page_size is not None
            else query_oregon_lincoln_taxlots.DEFAULT_PAGE_SIZE
        ),
        max_response_bytes=(query_oregon_lincoln_taxlots.DEFAULT_MAX_RESPONSE_BYTES),
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_lincoln_taxlots.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _oregon_tax_foreclosure_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one county publication collection."""

    config = query_oregon_tax_foreclosures.SOURCES[args.source]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", config.county_geoid}:
        raise ValueError(
            f"{config.county_name} tax-foreclosure publications serve county "
            f"GEOID {config.county_geoid}"
        )
    county = str(args.county_fips or "").strip()
    if county and county not in {
        config.county_geoid,
        config.county_geoid[-3:],
    }:
        raise ValueError(
            f"{config.county_name} uses county code {config.county_geoid[-3:]} "
            f"or GEOID {config.county_geoid}"
        )
    supported_stages = query_oregon_tax_foreclosures.SOURCE_PROCESS_STAGES[args.source]
    if args.process_stage and args.process_stage not in supported_stages:
        raise ValueError(
            f"{config.county_name} publication routes expose process stages: "
            f"{', '.join(supported_stages)}"
        )

    criteria = {
        "query": None,
        "owner": None,
        "account": None,
        "map_tax_lot": None,
        "property_id": None,
        "address": None,
        "case": None,
    }
    if args.command == "search":
        criteria["query"] = args.query
    elif args.command == "owner":
        criteria["owner"] = args.query
    elif args.command == "address":
        criteria["address"] = args.query
    elif args.command == "account":
        criteria["account"] = args.query
    elif args.command == "parcel":
        field = (
            "property_id"
            if args.source == query_oregon_tax_foreclosures.MULTNOMAH_SOURCE_ID
            else "map_tax_lot"
        )
        criteria[field] = args.query
    else:
        raise ValueError(
            f"{config.county_name} does not translate unified operation {args.command}"
        )

    caller_ceiling = args.max_records
    if caller_ceiling is None and args.limit_explicit:
        caller_ceiling = args.limit
    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        artifact=None,
        process_stage=args.process_stage,
        document_url=None,
        publication_page_url=None,
        publication_label=None,
        text_artifact=None,
        text_method=None,
        **criteria,
        max_records=caller_ceiling,
        cursor=args.cursor,
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_tax_foreclosures.DEFAULT_TIMEOUT
        ),
        max_page_bytes=query_oregon_tax_foreclosures.DEFAULT_MAX_PAGE_BYTES,
        max_document_bytes=(query_oregon_tax_foreclosures.DEFAULT_MAX_DOCUMENT_BYTES),
        output=None,
        json_out=False,
    )


def _deschutes_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate unified selectors to the Deschutes assessor service."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"41", "OR", "41017"}:
        raise ValueError(
            "The Deschutes source accepts Oregon context (41/OR) and serves "
            "Deschutes County GEOID 41017"
        )
    county = str(args.county_fips or "").strip()
    if county and county not in {"017", "41017"}:
        raise ValueError("The Deschutes source uses county code 017 or GEOID 41017")
    field_by_operation = {
        "search": "auto",
        "owner": "owner",
        "address": "address",
        "parcel": "parcel",
        "map": "parcel",
        "account": "account",
    }
    common = _remote_common(args)
    common["limit"] = args.limit
    return argparse.Namespace(
        **common,
        command=adapter_command,
        query=args.query,
        field=field_by_operation[args.command],
        geometry=args.geometry or args.command == "map",
        retry_attempts=3,
    )


def _deschutes_dial_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate unified selectors to Deschutes DIAL search or account detail."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"41", "OR", "41017"}:
        raise ValueError(
            "The Deschutes DIAL source accepts Oregon context (41/OR) and "
            "serves Deschutes County GEOID 41017"
        )
    county = str(args.county_fips or "").strip()
    if county and county not in {"017", "41017"}:
        raise ValueError(
            "The Deschutes DIAL source uses county code 017 or GEOID 41017"
        )

    transport = {
        "timeout": (
            args.timeout
            if args.timeout is not None
            else query_deschutes_dial.DEFAULT_TIMEOUT
        ),
        "minimum_interval": args.minimum_interval,
        "retry_attempts": 3,
        "catalog_db": args.catalog_db,
        "output": None,
        "json_out": False,
    }
    if adapter_command == "account":
        return argparse.Namespace(
            **transport,
            command="account",
            selector=args.query,
            field="account" if args.command == "account" else "taxlot",
            components=query_deschutes_dial.DEFAULT_COMPONENTS,
        )

    field_by_operation = {
        "search": "general",
        "owner": "owner",
        "address": "situs",
        "subdivision": "subdivision",
        "mobile-park": "mobile-park",
    }
    return argparse.Namespace(
        **transport,
        command="search",
        query=args.query,
        field=field_by_operation[args.command],
        limit=args.limit,
        cursor=args.cursor,
    )


def _deschutes_cdd_weblink_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate an exact Deschutes account to its linked CDD documents."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"41", "OR", "41017"}:
        raise ValueError(
            "The Deschutes CDD WebLink source accepts Oregon context (41/OR) "
            "and serves Deschutes County GEOID 41017"
        )
    county = str(args.county_fips or "").strip()
    if county and county not in {"017", "41017"}:
        raise ValueError(
            "The Deschutes CDD WebLink source uses county code 017 or GEOID 41017"
        )
    return argparse.Namespace(
        command=adapter_command,
        account_id=args.query,
        limit=args.limit,
        cursor=args.cursor,
        hydrate=False,
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_deschutes_laserfiche.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        max_response_bytes=(query_deschutes_laserfiche.DEFAULT_MAX_RESPONSE_BYTES),
        output=None,
        json_out=False,
    )


def _oregon_helion_recorder_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate common owner and instrument selectors to one Helion tenant."""

    tenant = query_oregon_helion_recorder.TENANTS_BY_SOURCE[args.source]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    allowed_jurisdictions = {
        "",
        "41",
        "OR",
        tenant.county_fips,
    }
    if jurisdiction not in allowed_jurisdictions:
        raise ValueError(f"{tenant.name} serves county GEOID {tenant.county_fips}")
    county = str(args.county_fips or "").strip()
    if county and county not in {
        tenant.county_fips,
        tenant.county_fips[-3:],
    }:
        raise ValueError(
            f"{tenant.name} uses county code {tenant.county_fips[-3:]} "
            f"or GEOID {tenant.county_fips}"
        )

    selectors: dict[str, Any] = {
        "year": None,
        "document_from": None,
        "document_to": None,
        "recorded_from": None,
        "recorded_to": None,
        "historic_number": None,
        "document_type_key": None,
        "subtype_key": None,
        "last_name": None,
        "first_name": None,
        "middle_name": None,
        "suffix": None,
        "party_type": "all",
        "property_id": None,
        "subdivision": None,
        "legal_1": None,
        "legal_2": None,
        "township": None,
        "range": None,
        "section": None,
        "quarter_quarter": None,
        "taxlot": None,
        "legal_description": None,
        "comments": None,
        "view": "document",
        "sort": None,
        "direction": "ascending",
    }
    if args.command in {"search", "owner"}:
        selectors["last_name"] = args.query
        selectors["view"] = "party"
    elif args.command == "instrument":
        match = re.fullmatch(r"\s*(\d{4})\D+0*(\d+)\s*", args.query)
        if match:
            selectors["year"] = int(match.group(1))
            document_number = int(match.group(2))
            selectors["document_from"] = document_number
            selectors["document_to"] = document_number
        else:
            selectors["historic_number"] = args.query
    else:
        raise ValueError(
            f"{tenant.name} does not translate unified operation {args.command}"
        )

    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        **selectors,
        limit=_selected_live_limit(args),
        cursor=args.cursor,
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_helion_recorder.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        max_attempts=query_oregon_helion_recorder.DEFAULT_MAX_ATTEMPTS,
        retry_backoff=query_oregon_helion_recorder.DEFAULT_RETRY_BACKOFF,
        output=None,
        json_out=False,
    )


def _santa_fe_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the Santa Fe Assessor ArcGIS layer."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "35", "NM", "US-NM", "35049"}:
        raise ValueError(
            "The Santa Fe Assessor source serves county GEOID 35049"
        )
    county_values = {
        str(value).strip().casefold()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    }
    county_aliases = {
        "049",
        "35049",
        "santa fe",
        "santa fe county",
    }
    if not county_values.issubset(county_aliases):
        raise ValueError(
            "Santa Fe county selectors must identify county GEOID 35049"
        )

    if adapter_command == "discovery":
        selector = str(args.query or args.search_field or "routes")
        selector = selector.strip().casefold().replace("_", "-")
        if selector in {"", "routes", "alternatives", "sources"}:
            argv = ["routes"]
        elif selector in {"metadata", "layer", "schema"}:
            argv = ["metadata"]
        else:
            raise ValueError(
                "Santa Fe discovery selector must be routes or metadata"
            )
    elif adapter_command in {"metadata", "probe"}:
        argv = [adapter_command]
    else:
        selector = str(args.query or "").strip()
        command = adapter_command
        if args.command == "search":
            field = (
                str(args.search_field or "owner")
                .strip()
                .casefold()
                .replace("_", "-")
            )
            aliases = {
                "name": "owner",
                "owner-name": "owner",
                "situs": "address",
                "situs-address": "address",
                "mail": "mailing",
                "mailing-address": "mailing",
                "upc": "parcel",
                "parcel-number": "parcel",
                "alternate-id": "parcel",
                "object-id": "objectid",
            }
            command = aliases.get(field, field)
            if command not in {
                "owner",
                "address",
                "mailing",
                "parcel",
                "objectid",
            }:
                raise ValueError(
                    "Santa Fe --search-field must be owner, address, "
                    "mailing, parcel/UPC, or objectid"
                )
        elif args.command == "map":
            command = "objectid"
        argv = [command, selector]

    if argv[0] != "routes":
        selected_limit = _selected_live_limit(args)
        if argv[0] not in {"metadata", "probe"}:
            if selected_limit is not None:
                argv.extend(["--limit", str(selected_limit)])
            if args.cursor:
                argv.extend(["--cursor", args.cursor])
            if args.geometry or args.command == "map":
                argv.append("--geometry")
            if args.max_records is not None:
                argv.extend(["--max-records", str(args.max_records)])
        argv.extend(
            [
                "--page-size",
                str(args.page_size),
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else 30.0
                ),
                "--minimum-interval",
                str(args.minimum_interval),
            ]
        )

    try:
        return query_santa_fe_property.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Santa Fe property selector for {adapter_command}"
        ) from error


def _santa_fe_clerktrack_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the verified ClerkTrack guest index."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "35", "NM", "US-NM", "35049"}:
        raise ValueError(
            "The Santa Fe ClerkTrack source serves county GEOID 35049"
        )
    county_values = {
        str(value).strip().casefold()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    }
    if not county_values.issubset(
        {"049", "35049", "santa fe", "santa fe county"}
    ):
        raise ValueError(
            "Santa Fe county selectors must identify county GEOID 35049"
        )
    if args.geometry:
        raise ValueError("ClerkTrack index records do not publish parcel geometry")

    timeout = (
        args.timeout
        if args.timeout is not None
        else query_santa_fe_clerktrack.DEFAULT_TIMEOUT
    )
    runtime = [
        "--timeout",
        str(timeout),
        "--minimum-interval",
        str(args.minimum_interval),
        "--retry-attempts",
        str(query_santa_fe_clerktrack.DEFAULT_RETRY_ATTEMPTS),
    ]

    if adapter_command == "routes":
        selector = str(args.query or "routes").strip().casefold()
        if selector not in {"routes", "sources", "alternatives"}:
            raise ValueError(
                "Santa Fe ClerkTrack discovery currently exposes verified routes"
            )
        argv = ["routes"]
    elif adapter_command == "probe":
        argv = ["probe", *runtime]
    elif adapter_command == "detail":
        instrument_number = str(args.query or "").strip()
        if not instrument_number:
            raise ValueError(
                "Santa Fe ClerkTrack detail requires an instrument number"
            )
        argv = ["detail", instrument_number, *runtime]
    elif adapter_command == "search":
        selector = str(args.query or "").strip()
        field = (
            "name"
            if args.command == "owner"
            else str(args.search_field or "name")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        argv = ["search"]
        if field in {"", "any", "name", "party", "owner"}:
            argv.extend(["--name", selector])
        elif field in {"grantor", "grantee"}:
            argv.extend(
                ["--name", selector, "--party-role", field]
            )
        elif field in {
            "instrument",
            "instrument-number",
            "document-number",
        }:
            argv.extend(["--instrument", selector])
        elif field == "book":
            argv.extend(["--book", selector])
        elif field == "page":
            argv.extend(["--page", selector])
        elif field in {"book-page", "book/page"}:
            match = re.fullmatch(
                r"\s*([^/]+)\s*/\s*([^/]+)\s*",
                selector,
            )
            if match is None:
                raise ValueError(
                    "Santa Fe ClerkTrack book/page selectors use BOOK/PAGE"
                )
            argv.extend(
                [
                    "--book",
                    match.group(1),
                    "--page",
                    match.group(2),
                ]
            )
        elif field in {"document-type", "instrument-type", "type"}:
            argv.extend(["--document-type", selector])
        elif field in {"date", "recording-date", "recorded-date"}:
            if not args.from_date:
                argv.extend(["--from-date", selector])
            if not args.to_date:
                argv.extend(["--to-date", selector])
        else:
            field_options = {
                "legal": "--legal",
                "legal-description": "--legal",
                "subdivision": "--subdivision",
                "lot": "--lot",
                "block": "--block",
                "tract": "--tract",
                "section": "--section",
                "township": "--township",
                "range": "--range",
                "unit": "--unit",
                "additional-info": "--additional-info",
            }
            option = field_options.get(field)
            if option is None:
                raise ValueError(
                    "Santa Fe ClerkTrack --search-field must be party/name, "
                    "grantor, grantee, instrument, book, page, book-page, "
                    "recording-date, document-type, legal, subdivision, lot, "
                    "block, tract, section, township, range, unit, or "
                    "additional-info"
                )
            argv.extend([option, selector])

        if args.from_date:
            argv.extend(["--from-date", args.from_date])
        if args.to_date:
            argv.extend(["--to-date", args.to_date])
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
        argv.extend(runtime)
    else:
        raise ValueError(
            f"Santa Fe ClerkTrack does not translate {adapter_command}"
        )

    try:
        return query_santa_fe_clerktrack.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Santa Fe ClerkTrack selector for {adapter_command}"
        ) from error


NYC_PIP_COUNTY_GEOIDS = frozenset(
    borough["county_geoid"]
    for borough in query_nyc_pip.BOROUGHS.values()
)


def _nyc_pip_scope(args: argparse.Namespace) -> None:
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {
        "",
        "36",
        "NY",
        "US-NY",
        query_nyc_pip.NYC_GEOID,
        *NYC_PIP_COUNTY_GEOIDS,
    }:
        raise ValueError(
            "NYC PIP covers the five New York City borough county GEOIDs"
        )
    for value in (args.county_fips, args.county_selector):
        selector = str(value or "").strip()
        if not selector:
            continue
        normalized = re.sub(r"[^a-z0-9]", "", selector.casefold())
        if (
            selector not in NYC_PIP_COUNTY_GEOIDS
            and normalized not in query_nyc_pip.BOROUGH_ALIASES
        ):
            raise ValueError(
                "NYC PIP county selectors must identify one of the five boroughs"
            )


def _nyc_pip_parcel_command(selector: str) -> list[str]:
    try:
        return ["bbl", query_nyc_pip.normalize_bbl(selector)]
    except ValueError as bbl_error:
        match = re.fullmatch(
            r"\s*(.+?)\s*[-/:,]\s*(\d+)\s*[-/:,]\s*(\d+)\s*",
            selector,
        )
        if match is None:
            raise ValueError(
                "NYC PIP parcel selectors use a ten-digit BBL or "
                "BOROUGH/BLOCK/LOT"
            ) from bbl_error
        borough, block, lot = match.groups()
        query_nyc_pip.bbl_from_parts(borough, block, lot)
        return ["lot", borough, block, lot]


def _nyc_pip_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property operations to the verified PIP layers."""

    _nyc_pip_scope(args)
    selector = str(args.query or "").strip()
    runtime = [
        "--page-size",
        str(args.page_size),
        "--timeout",
        str(
            args.timeout
            if args.timeout is not None
            else query_nyc_pip.DEFAULT_TIMEOUT
        ),
        "--minimum-interval",
        str(args.minimum_interval),
    ]

    if adapter_command == "parcel":
        if not selector:
            raise ValueError("NYC PIP parcel lookup requires a BBL")
        argv = [*_nyc_pip_parcel_command(selector), *runtime]
    elif adapter_command in {
        "detail",
        "geometry",
        "current-assessment",
        "assessment-history",
        "exemptions",
    }:
        if not selector:
            raise ValueError(f"NYC PIP {adapter_command} requires a BBL")
        bbl = query_nyc_pip.normalize_bbl(selector)
        argv = [adapter_command, bbl]
        if args.limit_explicit:
            argv.extend(["--limit", str(args.limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
        if args.max_records is not None:
            argv.extend(["--max-records", str(args.max_records)])
        argv.extend(runtime)
    elif adapter_command in {"owner", "address"}:
        if not selector:
            raise ValueError(f"NYC PIP {adapter_command} search requires a value")
        match_mode = str(args.search_field or "contains").strip().casefold()
        if match_mode not in {"contains", "starts", "exact"}:
            raise ValueError(
                "NYC PIP owner/address --search-field selects contains, "
                "starts, or exact matching"
            )
        argv = [adapter_command, selector, "--match", match_mode]
        if args.limit_explicit:
            argv.extend(["--limit", str(args.limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
        if args.max_records is not None:
            argv.extend(["--max-records", str(args.max_records)])
        argv.extend(runtime)
    elif adapter_command == "discovery":
        mode = (selector or "layers").casefold()
        if mode not in {"layers", "metadata", "routes"}:
            raise ValueError(
                "NYC PIP discovery mode must be layers, metadata, or routes"
            )
        argv = ["discovery", mode]
        layer = str(args.search_field or "").strip().casefold()
        if layer:
            if layer not in query_nyc_pip.LAYER_SPECS:
                raise ValueError(
                    "NYC PIP discovery layer must be detail, tax_lot, "
                    "current_assessment, assessment_history, or exemptions"
                )
            argv.extend(["--layer", layer])
        argv.extend(runtime)
    elif adapter_command == "probe":
        argv = ["probe", *runtime]
    else:
        raise ValueError(f"NYC PIP does not translate {adapter_command}")

    try:
        return query_nyc_pip.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid NYC PIP selector for {adapter_command}"
        ) from error


def _usvi_recorder_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the territorial CountyFusion adapter."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "78", "VI"}:
        raise ValueError(
            "The U.S. Virgin Islands Recorder source serves territorial GEOID 78"
        )
    county = str(args.county_fips or "").strip().upper()
    if county not in {"", "78", "VI"}:
        raise ValueError(
            "The U.S. Virgin Islands Recorder source uses territorial GEOID 78"
        )

    timeout = (
        args.timeout
        if args.timeout is not None
        else query_usvi_recorder.TIMEOUT
    )
    runtime = [
        "--timeout",
        str(timeout),
        "--minimum-interval",
        str(args.minimum_interval),
    ]

    if adapter_command == "probe":
        argv = ["probe", *runtime]
    elif adapter_command in {"document", "page"}:
        instrument_number = str(args.query or "").strip()
        district = str(getattr(args, "district", None) or "").strip()
        inst_id = str(getattr(args, "inst_id", None) or "").strip()
        if not instrument_number or not district or not inst_id:
            raise ValueError(
                "Exact USVI instrument access requires the instrument number, "
                "--district, and --inst-id emitted by a search result"
            )
        argv = [
            adapter_command,
            instrument_number,
            "--district",
            district,
            "--inst-id",
            inst_id,
        ]
        if adapter_command == "page":
            page_number = getattr(args, "page_number", None)
            if page_number is None:
                raise ValueError(
                    "USVI page-image retrieval requires --page-number"
                )
            if not args.destination:
                raise ValueError(
                    "USVI page-image retrieval requires --destination"
                )
            argv.extend([str(page_number), args.destination])
            if getattr(args, "overwrite", False):
                argv.append("--overwrite")
        argv.extend(runtime)
    elif adapter_command == "search":
        selector = str(args.query or "").strip()
        search_field = str(args.search_field or "").strip().casefold()
        argv = ["search"]
        if search_field in {"", "any", "name", "party"}:
            argv.append(selector)
        elif search_field in {"grantor", "party-1"}:
            argv.extend([selector, "--party", "grantor"])
        elif search_field in {"grantee", "party-2"}:
            argv.extend([selector, "--party", "grantee"])
        elif search_field in {
            "document",
            "document-number",
            "instrument",
            "instrument-number",
        }:
            argv.extend(["--document-number", selector])
        elif search_field in {"book-page", "book/page"}:
            match = re.fullmatch(r"\s*([^/]+)\s*/\s*([^/]+)\s*", selector)
            if match is None:
                raise ValueError(
                    "USVI book/page selectors use BOOK/PAGE"
                )
            argv.extend(["--book", match.group(1), "--page", match.group(2)])
        elif search_field in {
            "parcel",
            "qtr-condo",
            "estate",
            "building",
            "unit",
            "plot",
            "land-comment",
        }:
            argv.extend([f"--{search_field}", selector])
        elif search_field in {"document-type", "instrument-type", "type"}:
            argv.extend(["--document-type", selector])
        elif search_field in {"date", "recording-date", "recorded-date"}:
            if not args.from_date and not args.to_date:
                argv.extend(["--date-from", selector, "--date-to", selector])
        else:
            raise ValueError(
                "USVI Recorder --search-field must be name, grantor, grantee, "
                "document-number, book-page, document-type, recording-date, "
                "parcel, qtr-condo, estate, building, unit, plot, or land-comment"
            )

        if getattr(args, "district", None):
            argv.extend(["--district", args.district])
        if args.from_date:
            argv.extend(["--date-from", args.from_date])
        if args.to_date:
            argv.extend(["--date-to", args.to_date])

        native_page_size = args.page_size
        if native_page_size == 1_000:
            native_page_size = 100
        if native_page_size not in query_usvi_recorder.NATIVE_PAGE_SIZES:
            allowed = ", ".join(
                str(value) for value in query_usvi_recorder.NATIVE_PAGE_SIZES
            )
            raise ValueError(
                f"USVI Recorder --page-size must be one of {allowed}"
            )
        argv.extend(["--page-size", str(native_page_size)])

        offset = 0
        if args.cursor:
            prefix = "usvi-recorder:offset:"
            if (
                not args.cursor.startswith(prefix)
                or not args.cursor[len(prefix) :].isdigit()
            ):
                raise ValueError(
                    "USVI Recorder cursor must have form "
                    "usvi-recorder:offset:N"
                )
            offset = int(args.cursor[len(prefix) :])
        argv.extend(["--offset", str(offset)])
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        argv.extend(runtime)
    else:
        raise ValueError(
            f"USVI Recorder does not translate {adapter_command}"
        )

    try:
        return query_usvi_recorder.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid USVI Recorder selector for {adapter_command}"
        ) from error


def _usvi_property_tax_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the territorial Capture CAMA adapter."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "78", "VI"}:
        raise ValueError(
            "The USVI Capture CAMA source serves territorial GEOID 78"
        )
    county = str(args.county_fips or "").strip().upper()
    if county not in {"", "78", "VI"}:
        raise ValueError(
            "The USVI Capture CAMA source uses territorial GEOID 78"
        )
    timeout = (
        args.timeout
        if args.timeout is not None
        else query_usvi_property_tax.DEFAULT_TIMEOUT
    )
    runtime = {
        "timeout": timeout,
        "minimum_interval": args.minimum_interval,
        "output": None,
        "json_out": False,
    }
    tax_year = str(args.tax_year) if args.tax_year is not None else None

    if adapter_command == "probe":
        return argparse.Namespace(command="probe", **runtime)
    if adapter_command == "parcel":
        return argparse.Namespace(
            command="parcel",
            parcel_number=args.query,
            tax_year=tax_year,
            **runtime,
        )
    if adapter_command == "artifact":
        kind = str(getattr(args, "artifact_kind", None) or "").strip()
        if kind not in {"bill", "receipt", "property-card"}:
            raise ValueError(
                "USVI Capture CAMA download requires --artifact-kind "
                "bill, receipt, or property-card"
            )
        if not args.destination:
            raise ValueError(
                "USVI Capture CAMA artifact retrieval requires --destination"
            )
        statement = getattr(args, "statement", None)
        transaction_id = getattr(args, "transaction_id", None)
        if kind == "bill" and not statement:
            raise ValueError(
                "USVI Capture CAMA bill retrieval requires --statement"
            )
        if kind == "receipt" and not transaction_id:
            raise ValueError(
                "USVI Capture CAMA receipt retrieval requires --transaction-id"
            )
        return argparse.Namespace(
            command="artifact",
            parcel_number=args.query,
            tax_year=tax_year,
            kind=kind,
            statement=statement,
            transaction_id=transaction_id,
            destination=Path(args.destination),
            overwrite=args.overwrite,
            **runtime,
        )
    if adapter_command != "search":
        raise ValueError(
            f"USVI Capture CAMA does not translate {adapter_command}"
        )

    if args.command == "owner":
        field = "owner"
    elif args.command == "address":
        field = "address"
    else:
        field = str(args.search_field or "owner").strip().casefold()
    field_aliases = {
        "name": "owner",
        "owner-name": "owner",
        "property-address": "address",
        "legal-description": "legal",
        "parcel-number": "parcel",
    }
    field = field_aliases.get(field, field)
    if field not in {"owner", "parcel", "address", "legal"}:
        raise ValueError(
            "USVI Capture CAMA --search-field must be owner, parcel, "
            "address, or legal"
        )
    return argparse.Namespace(
        command="search",
        field=field,
        term=args.query,
        tax_year=tax_year,
        limit=_selected_live_limit(args),
        cursor=args.cursor,
        **runtime,
    )


def _oregon_helion_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one county Property Search Online tenant."""

    tenant = query_oregon_helion_property.TENANTS_BY_SOURCE[args.source]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", tenant.county_fips}:
        raise ValueError(
            f"{tenant.county_name} Property Search Online serves county "
            f"GEOID {tenant.county_fips}"
        )
    county = str(args.county_fips or "").strip()
    if county and county not in {
        tenant.county_fips,
        tenant.county_fips[-3:],
    }:
        raise ValueError(
            f"{tenant.county_name} uses county code "
            f"{tenant.county_fips[-3:]} or GEOID {tenant.county_fips}"
        )

    runtime = {
        "source": args.source,
        "timeout": (
            args.timeout
            if args.timeout is not None
            else query_oregon_helion_property.DEFAULT_TIMEOUT
        ),
        "output": None,
        "json_out": False,
    }
    if adapter_command == "detail":
        return argparse.Namespace(
            command="detail",
            account=args.query,
            roll_type="R",
            **runtime,
        )

    field_by_operation = {
        "search": "name",
        "owner": "name",
        "address": "address",
        "parcel": "map",
    }
    return argparse.Namespace(
        command="search",
        query=args.query,
        field=field_by_operation[args.command],
        limit=args.limit,
        cursor=args.cursor,
        **runtime,
    )


def _oregon_lane_marion_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate unified selectors to one Lane or Marion ArcGIS component."""

    config = query_oregon_lane_marion_parcels.SOURCES[args.source]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", config.county_geoid}:
        raise ValueError(f"{config.name} serves county GEOID {config.county_geoid}")
    county = str(args.county_fips or "").strip()
    if county and county not in {
        config.county_geoid,
        config.county_geoid[-3:],
    }:
        raise ValueError(
            f"{config.name} uses county code {config.county_geoid[-3:]} "
            f"or GEOID {config.county_geoid}"
        )

    field_by_operation = {
        "search": "auto",
        "owner": "owner",
        "address": "address",
        "parcel": "parcel",
        "map": "parcel",
        "account": "account",
        "instrument": "instrument",
    }
    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        query=args.query,
        field=field_by_operation[args.command],
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        page_size=args.page_size,
        timeout=(args.timeout if args.timeout is not None else 30.0),
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _oregon_lane_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to Lane's account or tax-map component."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", "US-OR", "41039"}:
        raise ValueError(
            "Lane County property sources use Oregon context 41/OR/US-OR "
            "or county GEOID 41039"
        )
    county = str(
        getattr(args, "county_selector", None) or args.county_fips or ""
    ).strip().casefold()
    if county not in {
        "",
        "039",
        "39",
        "41039",
        "lane",
        "lane county",
    }:
        raise ValueError(
            "Lane County property sources cover Lane County (039/41039)"
        )

    source_id = args.source
    selector = str(args.query or "").strip()
    timeout = (
        args.timeout
        if args.timeout is not None
        else query_oregon_lane_property.DEFAULT_TIMEOUT
    )
    if adapter_command == "probe":
        argv = ["probe", "--source", source_id]
    elif adapter_command == "account":
        if source_id != query_oregon_lane_property.ACCOUNT_SOURCE_ID:
            raise ValueError("exact account detail belongs to the account source")
        if not selector:
            raise ValueError("Lane County account detail requires an account number")
        argv = ["account", selector]
    elif adapter_command == "download-tax-map":
        if source_id != query_oregon_lane_property.TAX_MAP_SOURCE_ID:
            raise ValueError("tax-map download belongs to the tax-map source")
        if not selector:
            raise ValueError("Lane County tax-map download requires a document ID")
        if not args.destination:
            raise ValueError("Lane County tax-map download requires --destination")
        argv = [
            "download-tax-map",
            selector,
            "--destination",
            args.destination,
        ]
    else:
        if not selector:
            raise ValueError("Lane County source search requires a selector")
        requested_field = (
            str(args.search_field or "")
            .strip()
            .casefold()
            .replace("-", "_")
        )
        if source_id == query_oregon_lane_property.ACCOUNT_SOURCE_ID:
            fields = {
                "owner": "name",
                "name": "name",
                "account": "account",
                "address": "address",
                "parcel": "map_taxlot",
                "map": "map_taxlot",
                "map_taxlot": "map_taxlot",
            }
            if args.command == "owner":
                field = "name"
            elif args.command == "address":
                field = "address"
            elif args.command in {"parcel", "map"}:
                field = "map_taxlot"
            elif requested_field:
                if requested_field not in fields:
                    raise ValueError(
                        "Lane account --search-field must be account, "
                        "map_taxlot, address, name, or owner"
                    )
                field = fields[requested_field]
            elif selector.isdigit():
                field = "account" if len(selector) == 7 else "map_taxlot"
            else:
                field = "name"
        else:
            fields = {
                "address": "address",
                "parcel": "map_lot",
                "map": "map_lot",
                "map_lot": "map_lot",
                "map_taxlot": "map_lot",
                "map_name": "map_name",
            }
            if args.command == "address":
                field = "address"
            elif args.command in {"parcel", "map"}:
                field = "map_lot"
            elif requested_field:
                if requested_field not in fields:
                    raise ValueError(
                        "Lane tax-map --search-field must be map_lot, "
                        "map_taxlot, map_name, or address"
                    )
                field = fields[requested_field]
            else:
                field = "map_lot" if selector.isdigit() else "address"
        argv = [
            "search",
            selector,
            "--source",
            source_id,
            "--field",
            field,
        ]
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])

    argv.extend(["--timeout", str(timeout)])
    try:
        return query_oregon_lane_property.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Lane County selector for {adapter_command}"
        ) from error


def _oregon_marion_download_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to Marion's official download families."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", "US-OR", "41047"}:
        raise ValueError(
            "Marion downloads use Oregon context 41/OR/US-OR or "
            "Marion County GEOID 41047"
        )
    county = str(
        getattr(args, "county_selector", None) or args.county_fips or ""
    ).strip().casefold()
    if county not in {"", "047", "47", "41047", "marion", "marion county"}:
        raise ValueError(
            "Marion downloads cover Marion County (047/41047)"
        )

    source_id = args.source
    dataset_aliases = {
        query_oregon_marion_downloads.SALES_SOURCE_ID: {
            "",
            "sales",
            "sale",
            "sales-data",
            "assessor-sales",
        },
        query_oregon_marion_downloads.ASSESSMENT_SOURCE_ID: {
            "",
            "assessment",
            "comprehensive",
            "comprehensive-assessment",
            "assessment-roll",
        },
    }
    dataset_type = str(args.dataset_type or "").strip().casefold()
    if dataset_type not in dataset_aliases[source_id]:
        raise ValueError(
            f"{source_id} does not use --dataset-type {args.dataset_type}"
        )

    selector = str(args.query or "").strip()
    selector_is_all = selector.casefold() in {"", "*", "all"}
    release_selector = str(args.collection_id or "").strip() or None
    if adapter_command != "search" and not selector_is_all:
        if release_selector and release_selector != selector:
            raise ValueError("Marion release selectors conflict")
        release_selector = selector

    if adapter_command == "search":
        if not selector:
            raise ValueError("Marion artifact search requires a selector")
        source_fields = (
            query_oregon_marion_downloads.SALES_SEARCH_FIELDS
            if source_id == query_oregon_marion_downloads.SALES_SOURCE_ID
            else query_oregon_marion_downloads.ASSESSMENT_SEARCH_FIELDS
        )
        field_by_operation = {
            "search": "any",
            "address": "address",
            "parcel": "parcel",
            "map": "parcel",
            "account": "account",
            "instrument": "instrument",
            "sale": "any",
        }
        field = str(args.search_field or "").strip().casefold()
        if not field:
            field = field_by_operation[args.command]
        if field not in source_fields:
            raise ValueError(
                "Marion artifact --search-field must be one of "
                + ", ".join(sorted(source_fields))
            )
        match = (
            "exact"
            if args.command in {"parcel", "map", "account", "instrument"}
            else "contains"
        )
        argv = [
            "search",
            selector,
            "--source",
            source_id,
            "--field",
            field,
            "--match",
            match,
        ]
        if args.artifact_path:
            argv.extend(["--artifact", args.artifact_path])
        if args.max_download_bytes is not None:
            argv.extend(
                ["--max-download-bytes", str(args.max_download_bytes)]
            )
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif adapter_command == "manifest":
        argv = ["manifest", "--source", source_id]
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif adapter_command in {"probe", "download"}:
        if args.cursor:
            raise ValueError(
                f"Marion {args.command} does not use a continuation cursor"
            )
        argv = [adapter_command, "--source", source_id]
        if adapter_command == "probe" and args.range_bytes is not None:
            argv.extend(["--sample-bytes", str(args.range_bytes)])
        if adapter_command == "download":
            if not args.destination:
                raise ValueError(
                    "Marion shared download requires --destination"
                )
            argv.extend(["--destination", args.destination])
            if not args.resume:
                argv.append("--no-resume")
            if args.expected_sha256:
                argv.extend(
                    ["--expected-sha256", args.expected_sha256]
                )
            if args.max_download_bytes is not None:
                argv.extend(
                    [
                        "--max-download-bytes",
                        str(args.max_download_bytes),
                    ]
                )
    else:
        raise ValueError(
            f"Marion downloads do not translate {args.command}"
        )

    if release_selector:
        argv.extend(["--release", release_selector])
    if args.tax_year is not None:
        argv.extend(["--year", str(args.tax_year)])
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_oregon_marion_downloads.DEFAULT_TIMEOUT
            ),
            "--retry-attempts",
            "3",
            "--minimum-interval",
            str(args.minimum_interval),
        ]
    )
    if args.chunk_size is not None:
        argv.extend(["--chunk-size", str(args.chunk_size)])
    try:
        return query_oregon_marion_downloads.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Marion download selector for {adapter_command}"
        ) from error


def _oregon_jackson_douglas_assessor_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one Jackson or Douglas assessor layer."""

    config = query_oregon_jackson_douglas_assessors.SOURCES[args.source]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", config.county_geoid}:
        raise ValueError(f"{config.name} serves county GEOID {config.county_geoid}")
    county = str(args.county_fips or "").strip()
    if county and county not in {config.county_geoid, config.county_geoid[-3:]}:
        raise ValueError(
            f"{config.name} uses county code {config.county_geoid[-3:]} "
            f"or GEOID {config.county_geoid}"
        )

    field_by_operation = {
        "search": "auto",
        "owner": "owner",
        "address": "address",
        "parcel": "parcel",
        "map": "parcel",
        "account": "account",
        "instrument": "instrument",
    }
    field = (
        str(args.search_field).strip()
        if args.command == "search" and args.search_field
        else field_by_operation[args.command]
    )
    if field != "auto" and field not in config.search_fields:
        supported = ", ".join(sorted(config.search_fields))
        raise ValueError(
            f"{config.name} does not publish the {field!r} search field; "
            f"available fields: {supported}"
        )
    caller_limit = args.limit
    if args.max_records is not None:
        caller_limit = min(caller_limit, args.max_records)
    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        query=args.query,
        field=field,
        limit=caller_limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        page_size=args.page_size,
        timeout=args.timeout if args.timeout is not None else 30.0,
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _oregon_jackson_property_event_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one Jackson County event component."""

    config = query_oregon_jackson_property_events.SOURCES[args.source]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", "41029"}:
        raise ValueError(f"{config.name} serves Jackson County GEOID 41029")
    county = str(args.county_fips or "").strip()
    if county and county not in {"029", "41029"}:
        raise ValueError(f"{config.name} uses county code 029 or GEOID 41029")

    field_by_operation = {
        "search": "auto",
        "owner": "person",
        "address": "address",
        "parcel": "map_taxlot",
        "map": "map_taxlot",
        "event": "native_id",
    }
    field = (
        str(args.search_field).strip()
        if args.command == "search" and args.search_field
        else field_by_operation[args.command]
    )
    if field != "auto" and field not in config.search_fields:
        supported = ", ".join(sorted(config.search_fields))
        raise ValueError(
            f"{config.name} does not publish the {field!r} search field; "
            f"available fields: {supported}"
        )
    caller_limit = args.limit
    if args.max_records is not None:
        caller_limit = min(caller_limit, args.max_records)
    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        query=args.query,
        field=field,
        limit=caller_limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        page_size=args.page_size,
        timeout=args.timeout if args.timeout is not None else 30.0,
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _oregon_linn_josephine_klamath_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one county-native assessor layer."""

    config = query_oregon_linn_josephine_klamath_assessors.SOURCES[args.source]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", config.county_geoid}:
        raise ValueError(f"{config.name} serves county GEOID {config.county_geoid}")
    county = str(args.county_fips or "").strip()
    if county and county not in {config.county_geoid, config.county_geoid[-3:]}:
        raise ValueError(
            f"{config.name} uses county code {config.county_geoid[-3:]} "
            f"or GEOID {config.county_geoid}"
        )

    field_by_operation = {
        "search": "auto",
        "owner": "owner",
        "address": "situs",
        "parcel": "parcel",
        "map": "parcel",
        "account": "account",
    }
    field = (
        str(args.search_field).strip()
        if args.command == "search" and args.search_field
        else field_by_operation[args.command]
    )
    if field != "auto" and field not in config.search_fields:
        supported = ", ".join(sorted(config.search_fields))
        raise ValueError(
            f"{config.name} does not publish the {field!r} search field; "
            f"available fields: {supported}"
        )
    caller_limit = args.limit
    if args.max_records is not None:
        caller_limit = min(caller_limit, args.max_records)
    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        query=args.query,
        field=field,
        limit=caller_limit,
        cursor=args.cursor,
        geometry=args.geometry or args.command == "map",
        page_size=args.page_size,
        timeout=args.timeout if args.timeout is not None else 30.0,
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _oregon_jackson_accela_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate an exact Jackson permit key to its Accela detail component."""

    source = next(
        source
        for source in query_oregon_jackson_accela.SOURCES.values()
        if source.source_id == args.source
    )
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "41", "OR", "41029"}:
        raise ValueError(f"{source.name} serves Jackson County GEOID 41029")
    county = str(args.county_fips or "").strip()
    if county and county not in {"029", "41029"}:
        raise ValueError(f"{source.name} uses county code 029 or GEOID 41029")
    return argparse.Namespace(
        command=adapter_command,
        module=source.key,
        cap_key=args.query,
        timeout=(
            args.timeout
            if args.timeout is not None
            else query_oregon_jackson_accela.DEFAULT_TIMEOUT
        ),
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
        output=None,
        json_out=False,
    )


def _reeves_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    return argparse.Namespace(
        command=adapter_command,
        query=args.query,
        ocr=False,
        date_from=None,
        date_to=None,
        limit=args.limit if args.limit_explicit else None,
        offset=0,
        cursor=args.cursor,
        workspace_id=None,
        timeout=args.timeout if args.timeout is not None else 30.0,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )


def _govos_recorder_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    tenant = query_govos_recorders.TENANTS_BY_SOURCE[args.source]
    state_fips = tenant.county_geoid[:2]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    accepted_jurisdictions = {
        "",
        state_fips,
        tenant.state_code.upper(),
        f"US-{tenant.state_code.upper()}",
        tenant.county_geoid,
    }
    if jurisdiction not in accepted_jurisdictions:
        raise ValueError(
            f"{tenant.name} serves county GEOID {tenant.county_geoid}"
        )

    county_label = tenant.jurisdiction_name.split(",", 1)[0]
    normalized_county_label = re.sub(
        r"[^a-z0-9]+", " ", county_label.casefold()
    ).strip()
    county_core = normalized_county_label
    if county_core.startswith("city and county of "):
        county_core = county_core.removeprefix("city and county of ").strip()
    county_core = county_core.removesuffix(" county").strip()
    accepted_counties = {
        tenant.county_geoid,
        tenant.county_geoid[-3:],
        normalized_county_label,
        county_core,
        f"{county_core} county",
        f"city and county of {county_core}",
    }
    for raw_county in (args.county_fips, args.county_selector):
        county = re.sub(
            r"[^a-z0-9]+", " ", str(raw_county or "").casefold()
        ).strip()
        if county and county not in accepted_counties:
            raise ValueError(
                f"{tenant.name} does not serve county selector "
                f"{raw_county!r}"
            )

    return argparse.Namespace(
        command=adapter_command,
        source=args.source,
        department=args.department,
        query=args.query,
        ocr=False,
        date_from=None,
        date_to=None,
        limit=args.limit if args.limit_explicit else None,
        offset=0,
        cursor=args.cursor,
        workspace_id=None,
        timeout=args.timeout if args.timeout is not None else 30.0,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )


def _normalized_digits(value: str) -> str:
    return str(int(value)) if value and int(value) else "0"


def _acris_bbl(
    args: argparse.Namespace,
) -> tuple[str | None, str | None, str | None, str | None]:
    selector = " ".join(args.query.split()).strip()
    for name in query_acris.KNOWN_PROPERTIES:
        if selector.casefold() in name.casefold():
            return None, None, None, selector

    parts = re.findall(r"\d+", selector)
    if len(parts) == 1 and len(parts[0]) == 10:
        digits = parts[0]
        return (
            digits[0],
            _normalized_digits(digits[1:6]),
            _normalized_digits(digits[6:]),
            None,
        )
    if len(parts) == 3:
        return (
            _normalized_digits(parts[0]),
            _normalized_digits(parts[1]),
            _normalized_digits(parts[2]),
            None,
        )
    if len(parts) == 2:
        borough_by_geoid = {
            geoid: borough
            for borough, (geoid, _name) in query_acris.BOROUGH_METADATA.items()
        }
        borough = borough_by_geoid.get(str(args.jurisdiction or ""))
        if borough:
            return (
                borough,
                _normalized_digits(parts[0]),
                _normalized_digits(parts[1]),
                None,
            )
    return None, None, None, None


def _acris_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    values = {
        **_remote_common(args),
        "command": adapter_command,
        "max_docs": 1 if adapter_command == "document" else args.limit,
    }
    if adapter_command == "party":
        values.update(query=args.query, exact=False)
    elif adapter_command == "document":
        values["document_id"] = args.query
    else:
        borough, block, lot, property_name = _acris_bbl(args)
        values.update(
            borough=borough,
            block=block,
            lot=lot,
            property_name=property_name,
        )
    return argparse.Namespace(**values)


def _harris_recorder_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate an exact unified instrument lookup to the Clerk index."""

    if args.jurisdiction and args.jurisdiction not in {"48", "48201"}:
        raise ValueError("Harris County Clerk records cover jurisdiction GEOID 48201")
    caller_limit = args.limit if getattr(args, "limit_explicit", False) else None
    if args.max_records is not None:
        caller_limit = (
            min(caller_limit, args.max_records)
            if caller_limit is not None
            else args.max_records
        )
    return argparse.Namespace(
        command=adapter_command,
        file_number=args.query,
        film_code=None,
        from_date=None,
        to_date=None,
        grantor=None,
        grantee=None,
        trustee=None,
        description=None,
        instrument_type=None,
        volume=None,
        page=None,
        section=None,
        lot=None,
        block=None,
        unit=None,
        abstract=None,
        outlot=None,
        tract=None,
        reserve=None,
        limit=caller_limit,
        timeout=args.timeout if args.timeout is not None else 30.0,
        minimum_interval=args.minimum_interval,
        catalog_db=args.catalog_db,
        output=None,
        json_out=False,
    )


def _harris_foreclosure_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate an exact foreclosure-notice lookup to the Clerk source."""

    if args.jurisdiction and args.jurisdiction not in {"48", "48201"}:
        raise ValueError("Harris County Clerk foreclosure notices cover GEOID 48201")
    caller_limit = args.limit if getattr(args, "limit_explicit", False) else None
    if args.max_records is not None:
        caller_limit = (
            min(caller_limit, args.max_records)
            if caller_limit is not None
            else args.max_records
        )
    return argparse.Namespace(
        command=adapter_command,
        document_id=args.query,
        file_date=None,
        sale_date=None,
        limit=caller_limit,
        timeout=args.timeout if args.timeout is not None else 30.0,
        minimum_interval=args.minimum_interval,
        catalog_db=args.catalog_db,
        output=None,
        json_out=False,
    )


def _washington_land_county_key(value: Any) -> str | None:
    """Resolve one shared county selector to an archive or gap key."""

    normalized = str(value or "").strip().casefold()
    if not normalized or normalized in {"53", "wa", "us-wa", "washington"}:
        return None
    if normalized.isdigit() and len(normalized) == 3:
        normalized = f"53{normalized}"
    normalized_name = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    normalized_name = re.sub(r"_county$", "", normalized_name)
    for candidate in (
        *query_washington_digital_archives_land.TITLES,
        *query_washington_digital_archives_land.RECORDER_ALTERNATIVES,
    ):
        aliases = {
            candidate.key.casefold(),
            candidate.county.casefold(),
            f"{candidate.county} county".casefold(),
            candidate.county_geoid,
            candidate.county_geoid[-3:],
        }
        normalized_aliases = {
            re.sub(r"[^a-z0-9]+", "_", alias).strip("_")
            for alias in aliases
        }
        normalized_aliases |= {
            re.sub(r"_county$", "", alias) for alias in normalized_aliases
        }
        if normalized in aliases or normalized_name in normalized_aliases:
            return candidate.key
    raise ValueError(f"unknown Washington county selector: {value}")


def _washington_land_county(
    args: argparse.Namespace,
) -> tuple[Any | None, Any | None]:
    """Resolve and cross-check the shared Washington county context."""

    jurisdiction = str(args.jurisdiction or "").strip()
    if jurisdiction and _washington_land_county_key(jurisdiction) is None and (
        jurisdiction.casefold() not in {"53", "wa", "us-wa", "washington"}
    ):
        raise ValueError(
            "Washington Digital Archives land records use state context "
            "53/WA or a Washington county GEOID"
        )
    keys = {
        key
        for key in (
            _washington_land_county_key(args.jurisdiction),
            _washington_land_county_key(args.county_fips),
            _washington_land_county_key(args.county_selector),
        )
        if key is not None
    }
    if len(keys) > 1:
        raise ValueError(
            "Washington Digital Archives county selectors identify "
            "different counties"
        )
    if not keys:
        return None, None
    key = next(iter(keys))
    title = query_washington_digital_archives_land.TITLES_BY_KEY.get(key)
    alternative = (
        query_washington_digital_archives_land.ALTERNATIVES_BY_KEY.get(key)
    )
    return title, alternative


def _washington_land_native_page_size(requested: int) -> int:
    """Translate the shared page size to one supported native size."""

    bounded = min(requested, max(
        query_washington_digital_archives_land.NATIVE_PAGE_SIZES
    ))
    return max(
        (
            size
            for size in query_washington_digital_archives_land.NATIVE_PAGE_SIZES
            if size <= bounded
        ),
        default=min(query_washington_digital_archives_land.NATIVE_PAGE_SIZES),
    )


def _washington_land_records_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared owner and exact-record selectors to the archive."""

    title, alternative = _washington_land_county(args)
    selector = str(args.query or "").strip()
    if alternative is not None:
        return argparse.Namespace(
            command="alternatives",
            county=alternative.key,
            shared_gap_alternative=alternative,
            shared_operation=args.command,
            shared_selector=selector,
        )

    adapter = query_washington_digital_archives_land
    argv: list[str]
    if adapter_command == "detail":
        if not re.fullmatch(r"[A-Fa-f0-9]{32}", selector):
            raise ValueError(
                "Washington Digital Archives instrument lookup requires the "
                "exact 32-hex archive record identifier"
            )
        argv = ["detail", selector]
    elif adapter_command == "search":
        if title is None:
            raise ValueError(
                "Washington Digital Archives owner search requires a covered "
                "county selector or county GEOID"
            )
        search_field = (
            str(args.search_field or "")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        if search_field not in {
            "",
            "any",
            "name",
            "owner",
            "party",
            "company",
            "last-name",
            "first-name",
            "grantor",
            "grantee",
        }:
            raise ValueError(
                "Washington Digital Archives owner search fields are name, "
                "company, last-name, first-name, grantor, or grantee"
            )
        argv = ["search", "--county", title.key]
        if search_field == "first-name":
            argv.extend(["--first-name", selector])
        else:
            argv.extend(["--last-name", selector])
        if search_field in {"grantor", "grantee"}:
            argv.extend(["--party-role", search_field])
        if args.tax_year is not None:
            argv.extend(
                [
                    "--start-year",
                    str(args.tax_year),
                    "--end-year",
                    str(args.tax_year),
                ]
            )
        selected_limit = min(
            value
            for value in (args.limit, args.max_records)
            if value is not None
        )
        argv.extend(
            [
                "--limit",
                str(selected_limit),
                "--page-size",
                str(_washington_land_native_page_size(args.page_size)),
            ]
        )
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    else:
        raise ValueError(
            f"Washington Digital Archives do not translate {adapter_command}"
        )

    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else adapter.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        translated = adapter.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Washington Digital Archives selector for {adapter_command}"
        ) from error
    translated.shared_expected_county_geoid = (
        title.county_geoid if title is not None else None
    )
    translated.shared_expected_jurisdiction = (
        title.jurisdiction if title is not None else None
    )
    return translated


def _washington_taxsifter_county_key(value: Any) -> str | None:
    """Resolve a shared Washington selector to a TaxSifter tenant key."""

    normalized = str(value or "").strip().casefold()
    if normalized in {
        "",
        "53",
        "wa",
        "us-wa",
        "washington",
        "washington state",
    }:
        return None
    if normalized.isdigit() and len(normalized) == 3:
        normalized = f"53{normalized}"
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    compact = re.sub(r"county$", "", compact)
    for tenant in query_washington_taxsifter.TENANTS:
        aliases = {
            tenant.key.casefold(),
            tenant.source_id.casefold(),
            tenant.county_name.casefold(),
            tenant.county_name.casefold().removesuffix(" county"),
            tenant.county_geoid,
            tenant.county_fips,
        }
        compact_aliases = {
            re.sub(r"county$", "", re.sub(r"[^a-z0-9]+", "", alias))
            for alias in aliases
        }
        if normalized in aliases or compact in compact_aliases:
            return tenant.key
    raise ValueError(f"unknown Washington TaxSifter county selector: {value}")


def _washington_taxsifter_tenant(args: argparse.Namespace) -> Any:
    """Resolve umbrella or leaf routing while enforcing county consistency."""

    selected_keys = {
        key
        for key in (
            _washington_taxsifter_county_key(args.jurisdiction),
            _washington_taxsifter_county_key(args.county_fips),
            _washington_taxsifter_county_key(args.county_selector),
        )
        if key is not None
    }
    if len(selected_keys) > 1:
        raise ValueError(
            "Washington TaxSifter county selectors identify different counties"
        )
    selected_key = next(iter(selected_keys), None)
    if args.source == WASHINGTON_TAXSIFTER_UMBRELLA_SOURCE_ID:
        if selected_key is None:
            raise ValueError(
                "the Washington TaxSifter family route requires a county "
                "name, FIPS suffix, or county GEOID"
            )
        return query_washington_taxsifter.TENANTS_BY_KEY[selected_key]

    tenant = query_washington_taxsifter.TENANTS_BY_SOURCE.get(args.source)
    if tenant is None:
        raise ValueError(f"unknown Washington TaxSifter source: {args.source}")
    if selected_key is not None and selected_key != tenant.key:
        raise ValueError(
            f"{args.source} serves {tenant.county_name} "
            f"({tenant.county_geoid}), not the requested county"
        )
    return tenant


def _washington_taxsifter_search_field(args: argparse.Namespace) -> None:
    """Reject field semantics the native general-query box cannot promise."""

    requested = (
        str(args.search_field or "")
        .strip()
        .casefold()
        .replace("_", "-")
    )
    allowed = {
        "search": {
            "",
            "auto",
            "any",
            "general",
            "owner",
            "name",
            "address",
            "situs",
            "mailing",
            "parcel",
            "account",
        },
        "owner": {"", "auto", "any", "general", "owner", "name"},
        "address": {
            "",
            "auto",
            "any",
            "general",
            "address",
            "situs",
            "mailing",
        },
        "parcel": {"", "auto", "parcel", "parcel-number", "account"},
        "account": {"", "auto", "parcel", "parcel-number", "account"},
        "sale": {"", "auto", "parcel", "parcel-number", "account"},
    }.get(args.command, {""})
    if requested not in allowed:
        raise ValueError(
            f"TaxSifter {args.command} cannot honor shared search field "
            f"{args.search_field!r}; the county portal exposes a general "
            "parcel/name/address query and exact parcel detail"
        )


def _washington_taxsifter_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one anonymous county TaxSifter tenant."""

    tenant = _washington_taxsifter_tenant(args)
    selector = str(args.query or "").strip()
    _washington_taxsifter_search_field(args)
    if args.geometry:
        raise ValueError(
            "TaxSifter publishes parcel-map pivots, not geometry; use a "
            "Washington current-parcels representation for shared geometry"
        )
    if args.tax_year is not None:
        raise ValueError(
            "TaxSifter detail reports the source's current roll and does not "
            "offer a tax-year selector"
        )
    if args.cursor and adapter_command != "search":
        raise ValueError(
            f"TaxSifter {args.command} does not publish a shared continuation"
        )

    argv: list[str]
    if adapter_command == "metadata":
        argv = ["metadata", "--source", tenant.source_id]
    elif adapter_command == "probe":
        argv = [
            "probe",
            "--source",
            tenant.source_id,
            "--operations",
            "search,assessor",
        ]
    elif adapter_command == "search":
        argv = ["search", selector, "--source", tenant.source_id]
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif adapter_command == "detail":
        argv = ["detail", "--source", tenant.source_id]
        if re.match(r"https?://", selector, flags=re.I):
            argv.extend(["--data-link", selector])
        else:
            argv.insert(1, selector)
        argv.extend(["--operations", "assessor,treasurer,appraisal"])
    elif adapter_command == "sales":
        argv = ["sales", "--source", tenant.source_id, "--parcel", selector]
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
    else:
        raise ValueError(f"TaxSifter does not translate {adapter_command}")

    if adapter_command in {"search", "detail", "sales", "probe"}:
        argv.extend(
            [
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else query_washington_taxsifter.DEFAULT_TIMEOUT
                ),
                "--minimum-interval",
                str(args.minimum_interval),
                "--retry-attempts",
                "3",
            ]
        )
    try:
        translated = query_washington_taxsifter.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Washington TaxSifter selector for {adapter_command}"
        ) from error
    translated.shared_operation = args.command
    translated.shared_source_id = args.source
    return translated


def _mason_county_tax_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared fields to Mason's non-pageable ArcGIS layer."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "53", "WA", "US-WA", "53045"}:
        raise ValueError(
            "Mason Tax Parcels queries use Washington context 53/WA/US-WA "
            "or Mason County GEOID 53045"
        )
    county_values = [
        str(value).strip().casefold()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    ]
    allowed_counties = {
        "45",
        "045",
        "53045",
        "mason",
        "mason county",
    }
    if any(value not in allowed_counties for value in county_values):
        raise ValueError(
            "Mason Tax Parcels queries use Mason County GEOID 53045"
        )
    if args.tax_year is not None:
        raise ValueError(
            "The Mason GIS layer publishes current assessment fields without "
            "a source tax-year selector"
        )
    if args.artifact_path:
        raise ValueError(
            "Mason Tax Parcels is queried through its live county ArcGIS "
            "layer, not a local --artifact-path"
        )

    selector = str(args.query or "").strip()
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    command = adapter_command
    argv: list[str]
    if command in {"metadata", "probe"}:
        argv = [command]
    elif command == "count":
        argv = ["count"]
        if selector.casefold() not in {"", "*", "all"}:
            field_map = {
                "": "any",
                "auto": "any",
                "any": "any",
                "parcel": "parcel",
                "pin": "parcel",
                "parcel-id": "parcel",
                "owner": "owner",
                "name": "owner",
                "address": "address",
                "situs": "address",
                "mailing": "address",
                "assessment": "assessment",
                "afn": "afn",
                "subdivision": "subdivision",
                "legal": "subdivision",
            }
            try:
                field = field_map[requested_field]
            except KeyError as error:
                raise ValueError(
                    "Mason count --search-field must be any, parcel, owner, "
                    "address, assessment, afn, or subdivision"
                ) from error
            argv.extend([selector, "--field", field])
    elif command in {"point", "bbox"}:
        coordinate_count = 2 if command == "point" else 4
        argv = [
            command,
            *_washington_parcel_coordinates(
                selector,
                count=coordinate_count,
                operation=command,
            ),
        ]
    elif command == "search":
        if selector.casefold() in {"*", "all"}:
            argv = ["list"]
        else:
            default_field = (
                "subdivision" if args.command == "subdivision" else "any"
            )
            field_map = {
                "": default_field,
                "auto": default_field,
                "any": "any",
                "parcel": "parcel",
                "pin": "parcel",
                "parcel-id": "parcel",
                "taxlot": "parcel",
                "terra-pin": "parcel",
                "owner": "owner",
                "name": "owner",
                "address": "address",
                "situs": "address",
                "mailing": "address",
                "assessment": "assessment",
                "afn": "afn",
                "subdivision": "subdivision",
                "legal": "subdivision",
            }
            try:
                field = field_map[requested_field]
            except KeyError as error:
                raise ValueError(
                    "Mason --search-field must be any, parcel, owner, "
                    "address, assessment, afn, or subdivision"
                ) from error
            argv = ["search", selector, "--field", field]
    elif command in {"owner", "address", "parcel"}:
        argv = [command, selector]
    else:
        raise ValueError(
            f"Mason Tax Parcels does not translate {args.command}"
        )

    selected_limit = _selected_live_limit(args)
    record_commands = {
        "list",
        "search",
        "owner",
        "address",
        "parcel",
        "point",
        "bbox",
    }
    parsed_command = argv[0]
    if selected_limit is not None and parsed_command in record_commands:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor:
        if parsed_command not in record_commands:
            raise ValueError(
                f"Mason Tax Parcels {args.command} does not use a continuation"
            )
        argv.extend(["--cursor", args.cursor])
    if (
        parsed_command in record_commands
        and (
            args.geometry
            or args.command == "map"
            or parsed_command in {"point", "bbox"}
        )
        and parsed_command not in {"point", "bbox"}
    ):
        argv.append("--geometry")
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_mason_county_tax_parcels.DEFAULT_TIMEOUT
            ),
            "--retry-attempts",
            str(query_mason_county_tax_parcels.DEFAULT_RETRY_ATTEMPTS),
        ]
    )
    if args.minimum_interval != 0.25:
        argv.extend(["--minimum-interval", str(args.minimum_interval)])
    try:
        return query_mason_county_tax_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Mason Tax Parcels selector for {adapter_command}"
        ) from error


def _palm_beach_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the anonymous county parcel GIS."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "12", "FL", "US-FL", "12099"}:
        raise ValueError(
            "Palm Beach parcel queries use Florida context 12/FL/US-FL or "
            "Palm Beach County GEOID 12099"
        )
    county_values = [
        str(value).strip().casefold()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    ]
    allowed_counties = {
        "99",
        "099",
        "12099",
        "palm beach",
        "palm beach county",
    }
    if any(value not in allowed_counties for value in county_values):
        raise ValueError(
            "Palm Beach parcel queries use county code 099 or GEOID 12099"
        )
    if args.tax_year is not None:
        raise ValueError(
            "The Palm Beach parcel layer publishes current assessment fields "
            "without a native tax-year selector"
        )
    if args.artifact_path:
        raise ValueError(
            "Palm Beach parcel search uses the live county GIS, not a local "
            "--artifact-path"
        )

    selector = str(args.query or "").strip()
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    command = adapter_command
    if command in {"metadata", "discovery", "probe"}:
        argv = [command]
    elif command == "count":
        argv = ["count"]
        if selector.casefold() not in {"", "*", "all"}:
            field_map = {
                "": "any",
                "auto": "any",
                "any": "any",
                "parcel": "parcel",
                "parcel-number": "parcel",
                "pcn": "parcel",
                "parid": "parid",
                "owner": "owner",
                "name": "owner",
                "address": "address",
                "situs": "address",
                "mailing": "address",
                "sale": "sale",
                "book-page": "sale",
                "legal": "legal",
                "property-use": "property-use",
                "subdivision": "subdivision",
            }
            try:
                field = field_map[requested_field]
            except KeyError as error:
                raise ValueError(
                    "Palm Beach count --search-field must be any, parcel, "
                    "parid, owner, address, sale, legal, property-use, or "
                    "subdivision"
                ) from error
            argv.extend([selector, "--field", field])
    elif command in {"point", "bbox"}:
        coordinate_count = 2 if command == "point" else 4
        argv = [
            command,
            *_washington_parcel_coordinates(
                selector,
                count=coordinate_count,
                operation=command,
            ),
        ]
    elif command == "search":
        if selector.casefold() in {"*", "all"}:
            argv = ["list"]
        else:
            default_field = (
                "subdivision" if args.command == "subdivision" else "any"
            )
            field_map = {
                "": default_field,
                "auto": default_field,
                "any": "any",
                "parcel": "parcel",
                "parcel-number": "parcel",
                "pcn": "parcel",
                "parid": "parid",
                "owner": "owner",
                "name": "owner",
                "address": "address",
                "situs": "address",
                "mailing": "address",
                "sale": "sale",
                "book-page": "sale",
                "legal": "legal",
                "property-use": "property-use",
                "subdivision": "subdivision",
            }
            try:
                field = field_map[requested_field]
            except KeyError as error:
                raise ValueError(
                    "Palm Beach --search-field must be any, parcel, parid, "
                    "owner, address, sale, legal, property-use, or subdivision"
                ) from error
            argv = ["search", selector, "--field", field]
    elif command in {"owner", "address", "parcel", "parid"}:
        argv = [command, selector]
    elif command == "sale":
        if requested_field in {"book-page", "book/page"}:
            field = "book-page"
        elif requested_field in {"sale-key", "salekey"}:
            field = "sale-key"
        elif requested_field in {"", "auto", "any", "sale"}:
            field = "any"
        else:
            raise ValueError(
                "Palm Beach sale --search-field must be any, sale-key, or "
                "book-page"
            )
        argv = ["sale", selector, "--field", field]
    else:
        raise ValueError(
            f"Palm Beach parcel details do not translate {args.command}"
        )

    selected_limit = _selected_live_limit(args)
    record_commands = {
        "list",
        "search",
        "owner",
        "address",
        "parcel",
        "parid",
        "sale",
        "point",
        "bbox",
    }
    parsed_command = argv[0]
    if selected_limit is not None and parsed_command in record_commands:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor:
        if parsed_command not in record_commands:
            raise ValueError(
                f"Palm Beach {args.command} does not use a continuation cursor"
            )
        argv.extend(["--cursor", args.cursor])
    if (
        parsed_command in record_commands
        and (
            args.geometry
            or args.command == "map"
            or parsed_command in {"point", "bbox"}
        )
        and parsed_command not in {"point", "bbox"}
    ):
        argv.append("--geometry")
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_palm_beach_property_appraiser.DEFAULT_TIMEOUT
            ),
            "--retry-attempts",
            str(
                query_palm_beach_property_appraiser.DEFAULT_RETRY_ATTEMPTS
            ),
        ]
    )
    if args.minimum_interval != 0.25:
        argv.extend(["--minimum-interval", str(args.minimum_interval)])
    try:
        return query_palm_beach_property_appraiser.build_parser().parse_args(
            argv
        )
    except SystemExit as error:
        raise ValueError(
            f"invalid Palm Beach parcel selector for {adapter_command}"
        ) from error


def _orange_tax_collector_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors without mixing current and 2020 records."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "12", "FL", "US-FL", "12095"}:
        raise ValueError(
            "Orange Tax Collector queries use Florida context 12/FL/US-FL "
            "or Orange County GEOID 12095"
        )
    county_values = [
        str(value).strip().casefold()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    ]
    if any(
        value
        not in {"95", "095", "12095", "orange", "orange county"}
        for value in county_values
    ):
        raise ValueError(
            "Orange Tax Collector queries use county code 095 or GEOID 12095"
        )
    if args.geometry or args.command == "map":
        raise ValueError(
            "Orange Tax Collector records do not publish parcel geometry"
        )
    unsupported_shared_selectors = {
        "--collection-id": args.collection_id,
        "--department": args.department,
        "--process-stage": args.process_stage,
        "--from-date": args.from_date,
        "--to-date": args.to_date,
    }
    selected_unsupported = [
        flag
        for flag, value in unsupported_shared_selectors.items()
        if value not in (None, "")
    ]
    if selected_unsupported:
        raise ValueError(
            "Orange Tax Collector does not use "
            + ", ".join(selected_unsupported)
        )

    selector = str(args.query or "").strip()
    selector_is_all = selector.casefold() in {"", "*", "all"}
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    dataset = str(args.dataset_type or "").strip().casefold()
    if dataset and dataset not in query_orange_tax_collector.BULK_PUBLICATIONS:
        raise ValueError(
            "Orange Tax Collector --dataset-type must be current or delinquent"
        )

    transport_argv = [
        "--timeout",
        str(
            args.timeout
            if args.timeout is not None
            else query_orange_tax_collector.DEFAULT_TIMEOUT
        ),
        "--retry-attempts",
        str(query_orange_tax_collector.DEFAULT_RETRY_ATTEMPTS),
        "--minimum-interval",
        str(args.minimum_interval),
    ]
    if args.chunk_size is not None:
        transport_argv.extend(["--chunk-size", str(args.chunk_size)])

    if adapter_command in {"search", "account"}:
        if not selector:
            raise ValueError(
                f"Orange Tax Collector {args.command} requires a selector"
            )
        if args.command in {"account", "parcel"}:
            try:
                query_orange_tax_collector.normalize_account(selector)
            except query_orange_tax_collector.OrangeTaxQueryError as error:
                raise ValueError(
                    "Shared Orange account/parcel lookup requires the exact "
                    "15-digit parcel account; TaxSys tokens remain a separate "
                    "direct-tool locator"
                ) from error
        if args.artifact_path:
            if not dataset:
                raise ValueError(
                    "Orange historical bulk search requires --dataset-type "
                    "current or delinquent"
                )
            argv = [
                *transport_argv,
                "bulk-search",
                dataset,
                args.artifact_path,
            ]
            if args.command == "owner":
                if requested_field not in {"", "auto", "any", "owner", "name"}:
                    raise ValueError(
                        "Orange historical owner search does not use "
                        f"--search-field {requested_field}"
                    )
                argv.extend(["--owner", selector])
            elif args.command == "address":
                if requested_field not in {
                    "",
                    "auto",
                    "any",
                    "address",
                    "mailing",
                }:
                    raise ValueError(
                        "Orange historical address search does not use "
                        f"--search-field {requested_field}"
                    )
                argv.extend(["--query", selector])
            elif args.command in {"account", "parcel"}:
                if requested_field not in {
                    "",
                    "auto",
                    "any",
                    "account",
                    "parcel",
                }:
                    raise ValueError(
                        "Orange historical parcel search does not use "
                        f"--search-field {requested_field}"
                    )
                argv.extend(["--account", selector])
            else:
                field_flags = {
                    "": "--query",
                    "auto": "--query",
                    "any": "--query",
                    "query": "--query",
                    "owner": "--owner",
                    "name": "--owner",
                    "account": "--account",
                    "parcel": "--account",
                    "certificate": "--certificate",
                    "tax-summary": "--tax-summary-id",
                    "tax-summary-id": "--tax-summary-id",
                    "status": "--status",
                    "address": "--query",
                    "mailing": "--query",
                }
                try:
                    selector_flag = field_flags[requested_field]
                except KeyError as error:
                    raise ValueError(
                        "Orange historical --search-field must be any, owner, "
                        "account/parcel, address, certificate, tax-summary-id, "
                        "or status"
                    ) from error
                argv.extend([selector_flag, selector])
            if args.tax_year is not None:
                argv.extend(["--tax-year", str(args.tax_year)])
            selected_limit = _selected_live_limit(args)
            if selected_limit is not None:
                argv.extend(["--limit", str(selected_limit)])
            if args.cursor:
                argv.extend(["--cursor", args.cursor])
        else:
            if dataset:
                raise ValueError(
                    "Orange --dataset-type selects a historical bulk snapshot "
                    "and requires --artifact-path"
                )
            if args.tax_year is not None:
                raise ValueError(
                    "The current Orange portal has no native tax-year filter; "
                    "use a local historical bulk snapshot when appropriate"
                )
            if adapter_command == "account":
                if requested_field not in {
                    "",
                    "auto",
                    "any",
                    "account",
                    "parcel",
                }:
                    raise ValueError(
                        "Orange account/parcel lookup does not use "
                        f"--search-field {requested_field}"
                    )
                if (
                    args.cursor
                    or args.limit_explicit
                    or args.max_records is not None
                ):
                    raise ValueError(
                        "Orange exact account lookup returns the account and "
                        "its bill history without a cursor or result limit"
                    )
                argv = [*transport_argv, "account", selector]
            else:
                fixed_field = {
                    "owner": {"", "auto", "any", "owner", "name"},
                    "address": {
                        "",
                        "auto",
                        "any",
                        "address",
                        "situs",
                        "mailing",
                    },
                    "search": {
                        "",
                        "auto",
                        "any",
                        "owner",
                        "name",
                        "address",
                        "situs",
                        "mailing",
                        "account",
                        "parcel",
                    },
                }[args.command]
                if requested_field not in fixed_field:
                    raise ValueError(
                        "Orange current portal uses one general index and does "
                        f"not support --search-field {requested_field}"
                    )
                argv = [*transport_argv, "search", selector]
                selected_limit = _selected_live_limit(args)
                if selected_limit is not None:
                    argv.extend(["--limit", str(selected_limit)])
                if args.cursor:
                    argv.extend(["--cursor", args.cursor])
    elif adapter_command == "sources":
        if (
            not selector_is_all
            or dataset
            or args.artifact_path
            or args.tax_year is not None
            or args.search_field
            or args.cursor
            or args.limit_explicit
            or args.max_records is not None
        ):
            raise ValueError(
                "Orange discovery returns the complete portal and historical "
                "bulk capability contract without record selectors"
            )
        argv = [*transport_argv, "sources"]
    elif adapter_command == "bulk-manifest":
        if (
            not selector_is_all
            or dataset
            or args.artifact_path
            or args.tax_year is not None
            or args.search_field
            or args.cursor
            or args.limit_explicit
            or args.max_records is not None
        ):
            raise ValueError(
                "Orange releases/manifest returns both fixed historical "
                "publication manifests without record selectors"
            )
        argv = [*transport_argv, "bulk-manifest"]
    elif adapter_command == "bulk-probe":
        if not selector_is_all:
            raise ValueError(
                "Orange bulk probe uses --dataset-type, not a record selector"
            )
        if not dataset:
            raise ValueError(
                "Orange bulk probe requires --dataset-type current or delinquent"
            )
        if (
            args.artifact_path
            or args.tax_year is not None
            or args.search_field
            or args.cursor
            or args.limit_explicit
            or args.max_records is not None
        ):
            raise ValueError(
                "Orange bulk probe observes the selected published artifact "
                "without local-path, record, cursor, or result-limit selectors"
            )
        argv = [*transport_argv, "bulk-probe", dataset]
        if args.range_bytes is not None:
            argv.extend(["--sample-bytes", str(args.range_bytes)])
    elif adapter_command == "bulk-download":
        if not selector_is_all:
            raise ValueError(
                "Orange bulk download uses --dataset-type and --destination"
            )
        if not dataset:
            raise ValueError(
                "Orange bulk download requires --dataset-type current or "
                "delinquent"
            )
        if not args.destination:
            raise ValueError(
                "Orange shared bulk download requires --destination"
            )
        if (
            args.artifact_path
            or args.tax_year is not None
            or args.search_field
            or args.cursor
            or args.limit_explicit
            or args.max_records is not None
        ):
            raise ValueError(
                "Orange bulk download does not use local-path, record, cursor, "
                "or result-limit selectors"
            )
        argv = [
            *transport_argv,
            "bulk-download",
            dataset,
            args.destination,
        ]
        if not args.resume:
            argv.append("--no-resume")
        if args.expected_sha256:
            argv.extend(["--expected-sha256", args.expected_sha256])
        if args.max_download_bytes is not None:
            argv.extend(
                ["--max-download-bytes", str(args.max_download_bytes)]
            )
    else:
        raise ValueError(
            f"Orange Tax Collector does not translate {args.command}"
        )

    try:
        return query_orange_tax_collector.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Orange Tax Collector selector for {adapter_command}"
        ) from error


def _palm_beach_tax_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the county's Aumentum tax modules."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "12", "FL", "US-FL", "12099"}:
        raise ValueError(
            "Palm Beach Tax Collector queries use Florida context 12/FL/US-FL "
            "or Palm Beach County GEOID 12099"
        )
    county_values = [
        str(value).strip().casefold()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    ]
    if any(
        value
        not in {"99", "099", "12099", "palm beach", "palm beach county"}
        for value in county_values
    ):
        raise ValueError(
            "Palm Beach Tax Collector queries use county code 099 or GEOID 12099"
        )
    if args.artifact_path:
        raise ValueError(
            "Palm Beach Tax Collector queries use the live public portal, not "
            "--artifact-path"
        )
    if args.geometry or args.command == "map":
        raise ValueError(
            "Palm Beach Tax Collector does not publish parcel geometry; use "
            "the Property Appraiser complement"
        )
    selector = str(args.query or "").strip()
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    command = adapter_command
    if command in {"discovery", "probe"}:
        argv = [command]
    elif command == "search":
        field_map = {
            "": "simple",
            "auto": "simple",
            "any": "simple",
            "simple": "simple",
            "owner": "owner",
            "name": "owner",
            "owners": "owners",
            "parcel": "parcel",
            "pcn": "pcn",
            "address": "address",
            "situs": "situs",
            "mailing": "postal",
            "postal": "postal",
            "paid-status": "paid-status",
            "delivery": "delivery",
        }
        try:
            field = field_map[requested_field]
        except KeyError as error:
            raise ValueError(
                "Palm Beach Tax Collector --search-field must be owner, "
                "parcel/PCN, address/situs, postal, paid-status, or delivery"
            ) from error
        argv = ["search", selector, "--field", field]
    elif command in {"owner", "address", "parcel", "account"}:
        argv = [command, selector]
    elif command == "bills":
        if requested_field in {
            "payment",
            "payments",
            "payment-history",
            "receipt",
        }:
            command = "payments"
        elif requested_field not in {
            "",
            "auto",
            "any",
            "bill",
            "bills",
            "installment",
            "tax-bill",
            "event",
        }:
            raise ValueError(
                "Palm Beach Tax Collector event --search-field must be bill, "
                "installment, payment-history, or receipt"
            )
        argv = [command, selector]
    else:
        raise ValueError(
            f"Palm Beach Tax Collector does not translate {args.command}"
        )

    if args.tax_year is not None:
        if argv[0] not in {"bills", "payments"}:
            raise ValueError(
                "Palm Beach Tax Collector --tax-year applies to bills or "
                "payment history"
            )
        argv.extend(["--tax-year", str(args.tax_year)])
    selected_limit = _selected_live_limit(args)
    paginated_commands = {"search", "owner", "address", "parcel", "payments"}
    if selected_limit is not None and argv[0] in paginated_commands:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor:
        if argv[0] not in paginated_commands:
            raise ValueError(
                f"Palm Beach Tax Collector {args.command} does not use a "
                "continuation cursor"
            )
        argv.extend(["--cursor", args.cursor])
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_palm_beach_tax_collector.DEFAULT_TIMEOUT
            ),
            "--retry-attempts",
            str(query_palm_beach_tax_collector.DEFAULT_RETRY_ATTEMPTS),
        ]
    )
    if args.minimum_interval != 0.25:
        argv.extend(["--minimum-interval", str(args.minimum_interval)])
    try:
        return query_palm_beach_tax_collector.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Palm Beach Tax Collector selector for {adapter_command}"
        ) from error


def _palm_beach_tax_deeds_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the Clerk's tax-deed portal."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "12", "FL", "US-FL", "12099"}:
        raise ValueError(
            "Palm Beach Tax Deeds queries use Florida context 12/FL/US-FL "
            "or Palm Beach County GEOID 12099"
        )
    county_values = [
        str(value).strip().casefold()
        for value in (args.county_fips, args.county_selector)
        if value not in (None, "")
    ]
    if any(
        value
        not in {"99", "099", "12099", "palm beach", "palm beach county"}
        for value in county_values
    ):
        raise ValueError(
            "Palm Beach Tax Deeds queries use county code 099 or GEOID 12099"
        )
    if args.artifact_path:
        raise ValueError(
            "Palm Beach Tax Deeds queries use the live Clerk portal, not "
            "--artifact-path"
        )
    if args.geometry or args.command == "map":
        raise ValueError(
            "Palm Beach Tax Deeds does not publish parcel geometry; use the "
            "Property Appraiser complement"
        )
    if args.tax_year is not None:
        raise ValueError(
            "Tax-deed searches expose certificate and auction dates, not a "
            "native tax-year selector"
        )

    selector = str(args.query or "").strip()
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    from_date = str(getattr(args, "from_date", None) or "").strip()
    to_date = str(getattr(args, "to_date", None) or "").strip()

    if adapter_command in {"discovery", "probe"}:
        argv = [adapter_command]
    elif adapter_command == "search":
        field_map = {
            "": "case",
            "auto": "case",
            "case": "case",
            "case-number": "case",
            "certificate": "certificate",
            "certificate-number": "certificate",
            "parcel": "parcel",
            "pcn": "parcel",
            "tax-collector": "tax-collector",
            "tax-collector-number": "tax-collector",
            "applicant": "applicant",
            "owner": "owner",
            "status": "status",
            "sale": "sale-date",
            "sale-date": "sale-date",
            "lands-available": "lands-available",
        }
        try:
            command = field_map[requested_field]
        except KeyError as error:
            raise ValueError(
                "Palm Beach Tax Deeds --search-field must be case, "
                "certificate, parcel/PCN, tax-collector, applicant, owner, "
                "status, sale-date, or lands-available"
            ) from error
        if command == "lands-available":
            argv = [command]
        elif command == "sale-date":
            sale_from = from_date or selector
            if not sale_from:
                raise ValueError(
                    "Palm Beach sale-date search requires a from date"
                )
            argv = [command, sale_from]
            if to_date:
                argv.extend(["--to-sale-date", to_date])
        elif command in {"applicant", "owner", "status"}:
            if not from_date or not to_date:
                raise ValueError(
                    f"Palm Beach Tax Deeds {command} search requires "
                    "--from-date and --to-date"
                )
            argv = [
                command,
                selector,
                "--from-date",
                from_date,
                "--to-date",
                to_date,
            ]
        else:
            argv = [command, selector]
    elif adapter_command == "owner":
        if not from_date or not to_date:
            raise ValueError(
                "Palm Beach Tax Deeds owner search requires --from-date and "
                "--to-date"
            )
        argv = [
            "owner",
            selector,
            "--from-date",
            from_date,
            "--to-date",
            to_date,
        ]
    elif adapter_command == "parcel":
        argv = ["parcel", selector]
    elif adapter_command == "sale-date":
        sale_from = from_date or selector
        if not sale_from:
            raise ValueError("Palm Beach tax-deed sale search requires a date")
        argv = ["sale-date", sale_from]
        if to_date:
            argv.extend(["--to-sale-date", to_date])
    elif adapter_command == "detail":
        if not selector.isdigit():
            raise ValueError(
                "Palm Beach tax-deed event lookup requires a numeric portal "
                "row ID"
            )
        argv = ["detail", selector]
    elif adapter_command == "document":
        match = re.fullmatch(r"(?P<row>\d+)\s*[:/]\s*(?P<image>\d+)", selector)
        if match is None:
            raise ValueError(
                "Palm Beach tax-deed download requires ROW_ID:IMAGE_ID or "
                "ROW_ID/IMAGE_ID"
            )
        if not args.destination:
            raise ValueError(
                "Palm Beach tax-deed document download requires --destination"
            )
        argv = [
            "document",
            match.group("row"),
            match.group("image"),
            "--document-output",
            args.destination,
        ]
    else:
        raise ValueError(
            f"Palm Beach Tax Deeds does not translate {args.command}"
        )

    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and argv[0] in {
        "certificate",
        "case",
        "parcel",
        "tax-collector",
        "applicant",
        "owner",
        "status",
        "sale-date",
        "lands-available",
    }:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor:
        if argv[0] not in {
            "certificate",
            "case",
            "parcel",
            "tax-collector",
            "applicant",
            "owner",
            "status",
            "sale-date",
            "lands-available",
        }:
            raise ValueError(
                f"Palm Beach Tax Deeds {args.command} does not use a "
                "continuation cursor"
            )
        argv.extend(["--cursor", args.cursor])
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_palm_beach_tax_deeds.DEFAULT_TIMEOUT
            ),
            "--retry-attempts",
            str(query_palm_beach_tax_deeds.DEFAULT_RETRY_ATTEMPTS),
        ]
    )
    try:
        return query_palm_beach_tax_deeds.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Palm Beach Tax Deeds selector for {adapter_command}"
        ) from error


def _washington_parcel_context(args: argparse.Namespace) -> str | None:
    """Resolve an optional Washington county selector from shared arguments."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "53", "WA"} and not (
        jurisdiction.isdigit()
        and len(jurisdiction) == 5
        and jurisdiction.startswith("53")
    ):
        raise ValueError(
            "Washington statewide parcels accept state context 53/WA or a "
            "Washington county GEOID"
        )
    county = str(args.county_fips or "").strip()
    if county:
        return county
    return jurisdiction if len(jurisdiction) == 5 else None


def _washington_parcel_coordinates(
    selector: str,
    *,
    count: int,
    operation: str,
) -> list[str]:
    values = [value for value in re.split(r"[\s,]+", selector.strip()) if value]
    if len(values) != count:
        expected = "longitude,latitude" if count == 2 else "west,south,east,north"
        raise ValueError(f"{operation} requires {expected}")
    try:
        [float(value) for value in values]
    except ValueError as error:
        raise ValueError(f"{operation} coordinates must be numeric") from error
    return values


def _washington_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one statewide parcel component."""

    adapter = query_washington_parcels
    county = _washington_parcel_context(args)
    source_id = args.source
    selector = str(args.query or "").strip()
    selector_is_all = selector.casefold() in {"*", "all"}
    requested_field = str(args.search_field or "").strip().casefold()
    argv: list[str] = [adapter_command]

    if source_id in WASHINGTON_PARCEL_REPRESENTATIONS_BY_SOURCE:
        representation = WASHINGTON_PARCEL_REPRESENTATIONS_BY_SOURCE[source_id]
        if adapter_command == "search":
            field = requested_field or {
                "address": "situs",
                "parcel": "parcel",
                "map": "parcel",
            }.get(args.command, "auto")
            argv.extend(
                [selector, "--field", field, "--representation", representation]
            )
            if county:
                argv.extend(["--county", county])
            argv.extend(["--limit", str(args.limit)])
            if args.cursor:
                argv.extend(["--cursor", args.cursor])
            if args.geometry or args.command == "map":
                argv.append("--geometry")
        elif adapter_command == "count":
            argv.extend(["--representation", representation])
            if county:
                argv.extend(["--county", county])
            if selector and not selector_is_all:
                field = requested_field or "parcel-id"
                option_by_field = {
                    "parcel": "--parcel-id",
                    "parcel-id": "--parcel-id",
                    "original-parcel-id": "--original-parcel-id",
                    "county": "--county",
                    "fips": "--fips",
                    "situs": "--situs",
                    "land-use": "--land-use",
                    "original-land-use": "--original-land-use",
                }
                try:
                    option = option_by_field[field]
                except KeyError as error:
                    raise ValueError(
                        "Washington parcel count search field must be one of "
                        + ", ".join(sorted(option_by_field))
                    ) from error
                argv.extend([option, selector])
        elif adapter_command in {"point", "bbox"}:
            coordinate_count = 2 if adapter_command == "point" else 4
            argv.extend(
                _washington_parcel_coordinates(
                    selector,
                    count=coordinate_count,
                    operation=adapter_command,
                )
            )
            argv.extend(["--representation", representation])
            if county:
                argv.extend(["--county", county])
            argv.extend(["--limit", str(args.limit)])
            if args.cursor:
                argv.extend(["--cursor", args.cursor])
            if args.geometry:
                argv.append("--geometry")
        elif adapter_command == "probe":
            operation = selector.casefold() or "sentinel"
            argv.extend(
                [
                    "--operation",
                    operation,
                    "--representation",
                    representation,
                ]
            )
        else:
            raise ValueError(
                f"{source_id} does not translate statewide parcel operation "
                f"{adapter_command}"
            )
    elif source_id == WASHINGTON_PARCEL_FRESHNESS_SOURCE_ID:
        if adapter_command != "county-freshness":
            raise ValueError("county freshness supports freshness/search")
        selected_county = county or (None if selector_is_all else selector)
        if selected_county:
            argv.extend(["--county", selected_county])
        argv.extend(["--limit", str(args.limit)])
    elif source_id == WASHINGTON_PARCEL_LAND_USE_SOURCE_ID:
        if adapter_command != "land-use-codes":
            raise ValueError("county land-use vocabulary supports land-use/search")
        if county:
            argv.extend(["--county", county])
        if selector and not selector_is_all:
            if requested_field == "county":
                argv.extend(["--county", selector])
            else:
                argv.extend(["--code", selector])
        argv.extend(["--limit", str(args.limit)])
    elif source_id == WASHINGTON_PARCEL_LINEAGE_SOURCE_ID:
        if adapter_command == "metadata":
            argv.extend(["--representation", "all"])
        elif adapter_command == "parity":
            if selector.casefold() in {
                "all",
                "wisaard",
                "include-wisaard",
                "true",
            }:
                argv.append("--include-wisaard")
        elif adapter_command == "probe":
            operation = selector.casefold() or "all"
            argv.extend(["--operation", operation, "--representation", "all"])
            if requested_field in {"wisaard", "all"}:
                argv.append("--include-wisaard")
        else:
            raise ValueError(
                "Washington parcel lineage supports search metadata, parity, and probe"
            )
    else:
        raise ValueError(f"unknown Washington statewide parcel source: {source_id}")

    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(args.timeout if args.timeout is not None else 30.0),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return adapter.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Washington parcel selector for {adapter_command}"
        ) from error


def _dc_property_context(args: argparse.Namespace) -> None:
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "11", "DC", "11001"}:
        raise ValueError(
            "District of Columbia property components use jurisdiction 11/DC"
        )


def _dc_property_component(source_id: str) -> Any:
    for component in query_dc_property.COMPONENTS.values():
        if component.source_id == source_id:
            return component
    raise ValueError(f"unknown District of Columbia property source: {source_id}")


def _dc_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property operations to one DCGIS component."""

    _dc_property_context(args)
    adapter = query_dc_property
    component = _dc_property_component(args.source)
    selector = str(args.query or "").strip()
    requested_field = str(args.search_field or "").strip().casefold()
    argv: list[str]

    if adapter_command in {"metadata", "count", "probe"}:
        argv = [adapter_command, component.key]
    elif adapter_command in {"point", "bbox"}:
        coordinate_count = 2 if adapter_command == "point" else 4
        argv = [
            adapter_command,
            *_washington_parcel_coordinates(
                selector,
                count=coordinate_count,
                operation=adapter_command,
            ),
        ]
    elif component.key == "assessment" and adapter_command == "assessment":
        field = requested_field or {
            "owner": "owner",
            "address": "address",
            "instrument": "instrument",
        }.get(args.command, "ssl")
        argv = ["assessment", selector, "--field", field]
    elif component.key == "geometry" and adapter_command == "geometry":
        field = requested_field or {
            "owner": "owner",
            "address": "address",
            "instrument": "instrument",
        }.get(args.command, "ssl")
        argv = ["geometry", selector, "--field", field]
    elif component.key == "sales" and adapter_command == "sales":
        argv = ["sales", selector]
    elif component.key == "surveys" and adapter_command == "surveys":
        field = requested_field or ("document" if args.command == "survey" else "ssl")
        argv = ["surveys", selector, "--field", field]
    else:
        raise ValueError(
            f"{component.source_id} does not translate shared operation {args.command}"
        )

    if adapter_command not in {"metadata", "count", "probe"}:
        argv.extend(["--limit", str(args.limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    if (
        component.has_geometry
        and adapter_command not in {"metadata", "count"}
        and (
            args.geometry
            or args.command == "map"
            or adapter_command in {"point", "bbox"}
        )
    ):
        argv.append("--geometry")
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(args.timeout if args.timeout is not None else 30.0),
            "--minimum-interval",
            str(args.minimum_interval),
            "--max-attempts",
            "3",
        ]
    )
    if args.max_records is not None:
        argv.extend(["--max-records", str(args.max_records)])
    try:
        return adapter.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid District of Columbia selector for {adapter_command}"
        ) from error


def _los_angeles_ttc_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property operations to one Los Angeles component."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "06", "CA", "06037"}:
        raise ValueError(
            "Los Angeles County property-tax sources serve county GEOID 06037"
        )
    county = str(args.county_fips or "").strip()
    if county and county not in {"037", "06037"}:
        raise ValueError(
            "Los Angeles County property-tax sources use county code 037 or GEOID 06037"
        )

    selector = str(args.query or "").strip()
    argv: list[str]
    if adapter_command == "route":
        argv = ["route", selector]
    elif adapter_command == "history":
        argv = ["history", selector]
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
        if args.limit_explicit:
            argv.extend(["--max-pages", str(args.limit)])
    elif adapter_command == "sale-results":
        argv = ["sale-results", selector]
        caller_limit = args.limit if args.limit_explicit else None
        if args.max_records is not None:
            caller_limit = (
                min(caller_limit, args.max_records)
                if caller_limit is not None
                else args.max_records
            )
        if caller_limit is not None:
            argv.extend(["--limit", str(caller_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif adapter_command == "auctions":
        argv = ["auctions"]
    elif adapter_command == "publications":
        argv = ["publications"]
        if selector.casefold() not in {"*", "all"}:
            if not re.fullmatch(r"\d{4}[A-Za-z]", selector):
                raise ValueError(
                    "Los Angeles tax-sale publication search uses an auction "
                    "cycle such as 2025B, or * for every indexed artifact"
                )
            argv.extend(["--cycle", selector.upper()])
        kind = str(args.process_stage or "").strip().casefold()
        kind_aliases = {
            "": "all",
            "all": "all",
            "sale-results": "sale_results_excess_proceeds",
            "sale_results": "sale_results_excess_proceeds",
            "sale_results_excess_proceeds": "sale_results_excess_proceeds",
            "sold-parcels": "sold_parcels",
            "sold_parcels": "sold_parcels",
        }
        if kind not in kind_aliases:
            raise ValueError(
                "Los Angeles TTC publication stages are all, sale-results, "
                "or sold-parcels"
            )
        argv.extend(["--kind", kind_aliases[kind]])
    elif adapter_command == "probe":
        argv = ["probe"]
    else:
        raise ValueError(f"Los Angeles County TTC does not translate {args.command}")

    argv.extend(
        [
            "--timeout",
            str(args.timeout if args.timeout is not None else 30.0),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_los_angeles_ttc.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Los Angeles County TTC selector for {adapter_command}"
        ) from error


def _philadelphia_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property operations to one Philadelphia component."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "42", "PA", "42101"}:
        raise ValueError("Philadelphia property sources serve county GEOID 42101")
    county = str(args.county_fips or "").strip().upper()
    if county not in {"", "101", "42101", "PHILADELPHIA"}:
        raise ValueError(
            "Philadelphia property sources use county code 101 or GEOID 42101"
        )

    selector = str(args.query or "").strip()
    command = adapter_command
    if command == "search":
        command = str(args.search_field or "owner").strip().casefold()
        if command not in {
            "owner",
            "address",
            "parcel",
            "registry",
            "pin",
            "objectid",
        }:
            raise ValueError(
                "Philadelphia OPA --search-field must be owner, address, "
                "parcel, registry, pin, or objectid"
            )

    argv: list[str]
    if command == "probe":
        argv = ["probe"]
    elif command == "history":
        argv = ["history", selector]
        if args.tax_year is not None:
            argv.extend(
                [
                    "--from-year",
                    str(args.tax_year),
                    "--to-year",
                    str(args.tax_year),
                ]
            )
    elif command == "parcel-shape":
        by = str(args.search_field or "").strip().casefold()
        if not by:
            by = {
                "address": "address",
                "instrument": "registry",
            }.get(args.command, "registry")
        if by not in {"registry", "pin", "address", "objectid"}:
            raise ValueError(
                "Philadelphia DOR --search-field must be registry, pin, "
                "address, or objectid"
            )
        argv = ["parcel-shape", selector, "--by", by]
    else:
        argv = [command, selector]

    caller_limits = [
        value
        for value in (
            args.limit if args.limit_explicit else None,
            args.max_records,
        )
        if value is not None
    ]
    if command != "probe" and caller_limits:
        argv.extend(["--limit", str(min(caller_limits))])
    if args.cursor:
        argv.extend(["--cursor", args.cursor])
    if command not in {"history"} and (args.geometry or args.command == "map"):
        argv.append("--geometry")
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_philadelphia_property.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_philadelphia_property.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Philadelphia property selector for {adapter_command}"
        ) from error


def _selected_live_limit(args: argparse.Namespace) -> int | None:
    limits = [
        value
        for value in (
            args.limit if args.limit_explicit else None,
            args.max_records,
        )
        if value is not None
    ]
    return min(limits) if limits else None


def _michigan_property_directory_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to Michigan's county source directory."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "26", "MI", "US-MI"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("26")
    ):
        raise ValueError(
            "Michigan property-directory queries accept state context "
            "26/MI/US-MI or a Michigan county GEOID"
        )
    county = str(args.county_fips or "").strip()
    if not county and len(jurisdiction) == 5 and jurisdiction.isdigit():
        county = jurisdiction
    if county.isdigit() and len(county) == 3:
        county = f"26{county}"
    if county and (
        not county.isdigit()
        or len(county) != 5
        or not county.startswith("26")
        or county not in query_michigan_property_directories.COUNTY_FIPS.values()
    ):
        normalized_county = re.sub(
            r"\s+COUNTY$",
            "",
            county,
            flags=re.IGNORECASE,
        ).strip()
        if normalized_county.casefold() not in {
            name.casefold() for name in query_michigan_property_directories.COUNTY_NAMES
        }:
            raise ValueError(f"unknown Michigan county selector {county!r}")
        county = normalized_county

    selector = str(args.query or "").strip()
    field = str(args.search_field or "").strip().casefold().replace("_", "-")
    command = adapter_command
    argv: list[str]

    if command == "probe":
        if county:
            raise ValueError(
                "Michigan property-directory probe validates statewide "
                "coverage and does not apply a county filter"
            )
        argv = ["probe"]
    elif command == "discovery":
        argv = ["discovery"]
        if field in {"", "any", "query", "text"}:
            if selector and selector.casefold() not in {"*", "all", "statewide"}:
                argv.extend(["--query", selector])
        elif field in {"county", "county-name", "county-fips", "fips"}:
            selected_county = selector or county
            if not selected_county:
                raise ValueError(
                    "Michigan directory county discovery requires a county selector"
                )
            if county and selector:
                normalized_selector = (
                    query_michigan_property_directories._normalize_county_selector(
                        selector
                    )
                )
                normalized_context = (
                    query_michigan_property_directories._normalize_county_selector(
                        county
                    )
                )
                if normalized_selector != normalized_context:
                    raise ValueError(
                        "Michigan directory county query conflicts with "
                        "--county-fips or --jurisdiction"
                    )
            argv.extend(["--county", selected_county])
            county = ""
        elif field in {"platform", "platform-family"}:
            if not selector:
                raise ValueError(
                    "Michigan directory platform discovery requires a platform"
                )
            argv.extend(["--platform", selector])
        else:
            raise ValueError(
                "Michigan directory discovery --search-field must be any, "
                "county, or platform"
            )
        if county:
            argv.extend(["--county", county])
    elif command == "search":
        if field in {"", "any", "query", "text"}:
            if selector.casefold() in {"*", "all", "statewide"}:
                argv = ["list"]
            elif selector:
                argv = ["search", selector]
            else:
                raise ValueError("Michigan directory search requires text or '*'")
        elif field in {"county", "county-name", "county-fips", "fips"}:
            selected_county = selector or county
            if not selected_county:
                raise ValueError(
                    "Michigan directory county search requires a county selector"
                )
            if county and selector:
                normalized_selector = (
                    query_michigan_property_directories._normalize_county_selector(
                        selector
                    )
                )
                normalized_context = (
                    query_michigan_property_directories._normalize_county_selector(
                        county
                    )
                )
                if normalized_selector != normalized_context:
                    raise ValueError(
                        "Michigan directory county query conflicts with "
                        "--county-fips or --jurisdiction"
                    )
            argv = ["list", "--county", selected_county]
            county = ""
        elif field in {"platform", "platform-family"}:
            if not selector:
                raise ValueError(
                    "Michigan directory platform search requires a platform"
                )
            argv = ["list", "--platform", selector]
        elif field in {"platforms", "platform-summary"}:
            argv = ["platforms"]
            if selector.casefold() not in {"", "*", "all", "statewide"}:
                argv.extend(["--platform", selector])
        elif field in {"discovery", "source-discovery", "candidate"}:
            argv = ["discovery"]
            if selector.casefold() not in {"", "*", "all", "statewide"}:
                argv.extend(["--query", selector])
        else:
            raise ValueError(
                "Michigan directory search --search-field must be any, "
                "county, platform, platforms, or discovery"
            )
        if county:
            argv.extend(["--county", county])
    else:
        raise ValueError(
            f"Michigan property directory does not translate {args.command}"
        )

    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and argv[0] in {
        "list",
        "search",
        "platforms",
        "discovery",
    }:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor and argv[0] in {
        "list",
        "search",
        "platforms",
        "discovery",
    }:
        argv.extend(["--cursor", args.cursor])
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_michigan_property_directories.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--max-attempts",
            "3",
        ]
    )
    try:
        return query_michigan_property_directories.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Michigan property-directory selector for {adapter_command}"
        ) from error


def _michigan_eaton_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the Eaton bulk snapshot adapter."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "26", "MI", "US-MI", "26045"}:
        raise ValueError(
            "Eaton parcel queries accept Michigan context 26/MI/US-MI "
            "or Eaton County GEOID 26045"
        )
    county = str(args.county_fips or "").strip()
    if county in {"045", "45"}:
        county = "26045"
    if county and county.casefold() not in {
        "26045",
        "eaton",
        "eaton county",
    }:
        raise ValueError("Eaton parcel queries use Eaton County GEOID 26045")

    if adapter_command in {"metadata", "probe"}:
        argv = [adapter_command]
        if adapter_command == "probe":
            argv.extend(["--sample-bytes", "64"])
        argv.extend(
            [
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else query_michigan_eaton_parcels.DEFAULT_TIMEOUT
                ),
                "--minimum-interval",
                str(args.minimum_interval),
                "--retry-attempts",
                "3",
            ]
        )
    elif adapter_command == "search":
        artifact = str(getattr(args, "artifact_path", "") or "").strip()
        if not artifact:
            raise ValueError(
                "Eaton snapshot search requires --artifact-path pointing "
                "to a downloaded TaxParcel.zip or TaxParcel.dbf"
            )
        selector = str(args.query or "").strip()
        if not selector:
            raise ValueError("Eaton snapshot search requires a selector")
        shared_field = {
            "owner": "owner",
            "address": "address",
            "parcel": "parcel",
            "account": "parcel",
            "map": "parcel",
        }.get(args.command, "any")
        selected_field = (
            str(args.search_field or "").strip().casefold().replace("_", "-")
        )
        if selected_field:
            if selected_field not in {
                "any",
                "parcel",
                "owner",
                "address",
                "bsa-url",
            }:
                raise ValueError(
                    "Eaton snapshot --search-field must be any, parcel, "
                    "owner, address, or bsa-url"
                )
            shared_field = selected_field
        match = "exact" if args.command in {"parcel", "account", "map"} else "contains"
        argv = [
            "search",
            artifact,
            selector,
            "--field",
            shared_field,
            "--match",
            match,
        ]
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    else:
        raise ValueError(f"Eaton parcel snapshot does not translate {args.command}")
    try:
        return query_michigan_eaton_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Eaton parcel selector for {adapter_command}"
        ) from error


def _fl_dor_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared bulk selectors to the Florida DOR release adapter."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "12", "FL", "US-FL"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("12")
    ):
        raise ValueError(
            "Florida DOR property releases use state context 12/FL/US-FL "
            "or a Florida county GEOID"
        )

    county_values = [
        value
        for value in (
            getattr(args, "county_selector", None),
            args.county_fips,
            jurisdiction if len(jurisdiction) == 5 else None,
        )
        if value not in (None, "")
    ]
    county: tuple[int, str, str] | None = None
    for value in county_values:
        try:
            resolved = resolve_fl_county(value)
        except ValueError as error:
            raise ValueError(str(error)) from error
        if county is not None and resolved[0] != county[0]:
            raise ValueError("Florida DOR county selectors conflict")
        county = resolved

    selector = str(args.query or "").strip()
    if selector.casefold() not in {"", "*", "all", "statewide"}:
        raise ValueError(
            "Florida DOR bulk operations use --dataset-type, --county, and "
            "--tax-year instead of a parcel or owner selector"
        )

    if adapter_command == "list":
        if county is not None:
            raise ValueError(
                "Florida DOR release-directory discovery is statewide; "
                "select a county with manifest, probe, or download"
            )
        argv = ["list"]
    elif adapter_command == "manifest":
        argv = ["manifest"]
    elif adapter_command in {"probe", "download"}:
        if not args.dataset_type:
            raise ValueError(f"Florida DOR {args.command} requires --dataset-type")
        if county is None:
            raise ValueError(f"Florida DOR {args.command} requires --county")
        argv = [adapter_command]
    else:
        raise ValueError(
            f"Florida DOR property releases do not translate {args.command}"
        )

    if args.dataset_type:
        argv.extend(["--type", args.dataset_type])
    if county is not None and adapter_command != "list":
        argv.extend(["--county", str(county[0])])
    if args.tax_year is not None:
        argv.extend(["--year", str(args.tax_year)])

    selected_limit = _selected_live_limit(args)
    if adapter_command in {"list", "manifest"}:
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif args.cursor:
        raise ValueError(
            f"Florida DOR {args.command} does not use a continuation cursor"
        )

    if adapter_command == "probe" and args.range_bytes is not None:
        argv.extend(["--range-bytes", str(args.range_bytes)])
    if adapter_command == "download":
        if not args.destination:
            raise ValueError("Florida DOR shared download requires --destination")
        argv.extend(["--destination", args.destination])
        if not args.resume:
            argv.append("--no-resume")
        if args.expected_sha256:
            argv.extend(["--expected-sha256", args.expected_sha256])
        if args.max_download_bytes is not None:
            argv.extend(["--max-download-bytes", str(args.max_download_bytes)])
        if args.chunk_size is not None:
            argv.extend(["--chunk-size", str(args.chunk_size)])

    argv.extend(
        [
            "--catalog-db",
            args.catalog_db,
            "--timeout",
            str(args.timeout if args.timeout is not None else 60.0),
            "--retry-attempts",
            "3",
            "--minimum-interval",
            str(args.minimum_interval),
        ]
    )
    try:
        return query_fl_dor_property.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Florida DOR bulk selector for {adapter_command}"
        ) from error


def _hcad_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared bulk selectors to the official HCAD release adapter."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "48", "TX", "US-TX", "48201"}:
        raise ValueError(
            "HCAD property releases use Texas context 48/TX/US-TX or "
            "Harris County GEOID 48201"
        )
    county = (
        str(getattr(args, "county_selector", None) or args.county_fips or "")
        .strip()
        .casefold()
    )
    if county not in {"", "201", "48201", "harris", "harris county"}:
        raise ValueError("HCAD property releases cover Harris County (201/48201)")

    group_aliases = {
        "": "real-property",
        "real": "real-property",
        "real-property": "real-property",
        "real_property": "real-property",
        "personal": "personal-property",
        "personal-property": "personal-property",
        "personal_property": "personal-property",
        "hearing": "hearings",
        "hearings": "hearings",
    }
    native_group = str(args.dataset_type or "").strip().casefold()
    try:
        group = group_aliases[native_group]
    except KeyError as error:
        raise ValueError(
            "HCAD --dataset-type must identify real-property, "
            "personal-property, or hearings"
        ) from error

    selector = str(args.query or "").strip()
    selector_is_all = selector.casefold() in {"", "*", "all"}
    if adapter_command == "list":
        if not selector_is_all:
            raise ValueError("HCAD release discovery does not use an artifact selector")
        argv = ["list"]
    elif adapter_command == "manifest":
        if args.tax_year is None:
            raise ValueError("HCAD manifest requires --tax-year")
        if not selector_is_all:
            raise ValueError(
                "HCAD manifest lists its complete artifact family; use the "
                "published artifact selector with probe or download"
            )
        argv = [
            "manifest",
            "--year",
            str(args.tax_year),
            "--group",
            group,
        ]
    elif adapter_command in {"probe", "download"}:
        if args.tax_year is None:
            raise ValueError(f"HCAD {args.command} requires --tax-year")
        if selector_is_all:
            raise ValueError(
                f"HCAD {args.command} requires a published artifact selector"
            )
        argv = [
            adapter_command,
            "--year",
            str(args.tax_year),
            "--group",
            group,
            "--artifact",
            selector,
        ]
    else:
        raise ValueError(f"HCAD property releases do not translate {args.command}")

    if args.cursor:
        raise ValueError(f"HCAD {args.command} does not use a continuation cursor")
    if adapter_command == "probe" and args.range_bytes is not None:
        argv.extend(["--range-bytes", str(args.range_bytes)])
    if adapter_command == "download":
        if not args.destination:
            raise ValueError("HCAD shared download requires --destination")
        argv.extend(["--destination", args.destination])
        if not args.resume:
            argv.append("--no-resume")
        if args.expected_sha256:
            argv.extend(["--expected-sha256", args.expected_sha256])
        if args.max_download_bytes is not None:
            argv.extend(["--max-download-bytes", str(args.max_download_bytes)])
        if args.chunk_size is not None:
            argv.extend(["--chunk-size", str(args.chunk_size)])

    argv.extend(
        [
            "--catalog-db",
            args.catalog_db,
            "--timeout",
            str(args.timeout if args.timeout is not None else 60.0),
            "--retry-attempts",
            "3",
            "--minimum-interval",
            str(args.minimum_interval),
        ]
    )
    try:
        return query_harris_property.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(f"invalid HCAD bulk selector for {adapter_command}") from error


def _hcad_gis_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to HCAD GIS bulk and MapServer routes."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "48", "TX", "US-TX", "48201"}:
        raise ValueError(
            "HCAD GIS uses Texas context 48/TX/US-TX or Harris County GEOID 48201"
        )
    county_values = [
        str(value).strip().casefold()
        for value in (args.county_selector, args.county_fips)
        if value not in (None, "")
    ]
    county_aliases = {"201", "48201", "harris", "harris county"}
    if any(value not in county_aliases for value in county_values):
        raise ValueError("HCAD GIS covers Harris County (201/48201)")

    dataset_type = str(args.dataset_type or "").strip().casefold()
    if dataset_type not in {
        "",
        "gis",
        "hcad-gis",
        "parcel",
        "parcels",
        "parcel-geometry",
        "parcel_geometry",
    }:
        raise ValueError("HCAD GIS --dataset-type must identify parcel GIS data")
    if getattr(args, "collection_id", None):
        raise ValueError("HCAD GIS releases use --tax-year for historical snapshots")
    if args.artifact_path:
        raise ValueError("HCAD GIS local archive inspection uses the direct adapter")

    if adapter_command in {"search", "account"}:
        if args.tax_year is not None:
            raise ValueError(
                "HCAD MapServer queries expose the current published "
                "assessment snapshot; --tax-year selects bulk releases"
            )
        selector = str(args.query or "").strip()
        if not selector:
            raise ValueError(f"HCAD GIS {args.command} requires a selector")
        if adapter_command == "account":
            argv = ["account", selector]
            if args.search_field not in {None, "", "any", "account", "parcel"}:
                raise ValueError(
                    f"HCAD GIS {args.command} does not use "
                    f"--search-field {args.search_field}"
                )
        else:
            requested_field = str(args.search_field or "").strip().casefold()
            fixed_field = {
                "owner": "owner",
                "address": "address",
            }.get(args.command)
            if fixed_field is None:
                field = requested_field or "any"
                if field not in query_hcad_gis.SEARCH_FIELDS:
                    raise ValueError(
                        "HCAD GIS --search-field must be any, owner, address, "
                        "legal, or account"
                    )
            else:
                if requested_field not in {"", "any", fixed_field}:
                    raise ValueError(
                        f"HCAD GIS {args.command} does not use "
                        f"--search-field {requested_field}"
                    )
                field = fixed_field
            argv = [
                "search",
                selector,
                "--field",
                field,
                "--match",
                "contains",
            ]

        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
        if args.geometry or args.command == "map":
            argv.append("--geometry")
        argv.extend(["--page-size", str(args.page_size)])
    else:
        selector = str(args.query or "").strip()
        selector_is_all = selector.casefold() in {"", "*", "all"}
        if args.cursor:
            raise ValueError(
                f"HCAD GIS {args.command} does not use a continuation cursor"
            )
        if args.limit_explicit or args.max_records is not None:
            raise ValueError(
                f"HCAD GIS {args.command} returns its complete source "
                "manifest and does not use a result limit"
            )
        if adapter_command == "releases":
            if not selector_is_all:
                raise ValueError(
                    "HCAD GIS release discovery does not use an artifact selector"
                )
            if args.tax_year is not None:
                raise ValueError(
                    "HCAD GIS release discovery lists current and historical "
                    "snapshots; select a year with manifest, probe, or "
                    "download"
                )
            argv = ["releases"]
        elif adapter_command in {"manifest", "probe", "download"}:
            argv = [adapter_command]
            if args.tax_year is not None:
                argv.extend(["--year", str(args.tax_year)])
            if not selector_is_all:
                argv.extend(["--artifact", selector])
        else:
            raise ValueError(
                f"HCAD GIS does not translate shared operation {args.command}"
            )
        if adapter_command == "probe" and args.range_bytes is not None:
            argv.extend(["--sample-bytes", str(args.range_bytes)])
        if adapter_command == "download":
            if not args.destination:
                raise ValueError("HCAD GIS shared download requires --destination")
            argv.extend(["--destination", args.destination])
            if not args.resume:
                argv.append("--no-resume")
            if args.expected_sha256:
                argv.extend(["--expected-sha256", args.expected_sha256])
            if args.max_download_bytes is not None:
                argv.extend(["--max-download-bytes", str(args.max_download_bytes)])
            if args.chunk_size is not None:
                argv.extend(["--chunk-size", str(args.chunk_size)])

    argv.extend(
        [
            "--catalog-db",
            args.catalog_db,
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_hcad_gis.DEFAULT_TIMEOUT
            ),
            "--retry-attempts",
            "3",
            "--minimum-interval",
            str(args.minimum_interval),
        ]
    )
    try:
        return query_hcad_gis.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(f"invalid HCAD GIS selector for {adapter_command}") from error


def _txgio_land_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to TxGIO bulk or local-archive operations."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "48", "TX", "US-TX"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("48")
    ):
        raise ValueError(
            "TxGIO land parcels use Texas context 48/TX/US-TX or a Texas county GEOID"
        )

    dataset_type = str(args.dataset_type or "").strip().casefold()
    if dataset_type not in {
        "",
        "land-parcels",
        "land_parcels",
        "parcel",
        "parcels",
    }:
        raise ValueError(
            "TxGIO --dataset-type must identify the land-parcels collection"
        )

    if adapter_command == "search":
        if not args.artifact_path:
            raise ValueError("TxGIO local archive search requires --artifact-path")
        if getattr(args, "collection_id", None):
            raise ValueError(
                "TxGIO --collection-id selects remote release artifacts, "
                "not a downloaded local archive"
            )
        if args.tax_year is not None:
            raise ValueError(
                "TxGIO local archive search does not use --tax-year; the "
                "source row retains its published TAX_YEAR"
            )
        if args.county_selector or args.county_fips:
            raise ValueError(
                "TxGIO local archive search takes its row scope from "
                "--artifact-path, not a separate --county selector"
            )

        requested_field = str(args.search_field or "").strip().casefold()
        fields = query_txgio_land_parcels.SEARCH_FIELDS
        fixed_field = {
            "owner": "owner",
            "address": "address",
            "parcel": "parcel",
            "map": "parcel",
        }.get(args.command)
        if fixed_field is None:
            field = requested_field or "any"
            if field not in fields:
                raise ValueError(
                    "TxGIO --search-field must be any, parcel, owner, address, or legal"
                )
        else:
            if requested_field not in {"", "any", fixed_field}:
                raise ValueError(
                    f"TxGIO {args.command} does not use "
                    f"--search-field {requested_field}"
                )
            field = fixed_field

        selector = str(args.query or "").strip()
        if not selector:
            raise ValueError(f"TxGIO {args.command} requires a selector")
        match = "exact" if args.command in {"parcel", "map"} else "contains"
        argv = [
            "search",
            args.artifact_path,
            selector,
            "--field",
            field,
            "--match",
            match,
        ]
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    else:
        selector = str(args.query or "").strip()
        selector_is_all = selector.casefold() in {"", "*", "all"}
        if args.tax_year is not None:
            raise ValueError(
                "TxGIO releases are selected by --collection-id, not --tax-year"
            )
        if args.cursor:
            raise ValueError(f"TxGIO {args.command} does not use a continuation cursor")
        if args.limit_explicit or args.max_records is not None:
            raise ValueError(
                f"TxGIO {args.command} returns its complete source manifest "
                "and does not use a result limit"
            )

        county_values = [
            str(value).strip()
            for value in (
                args.county_selector,
                args.county_fips,
                (
                    jurisdiction
                    if len(jurisdiction) == 5 and jurisdiction.isdigit()
                    else None
                ),
                selector if not selector_is_all else None,
            )
            if value not in (None, "")
        ]

        def county_key(value: str) -> str:
            key = re.sub(r"[^a-z0-9]", "", value.casefold())
            key = key.removesuffix("county")
            if key.isdigit() and len(key) == 3:
                return f"48{key}"
            return key

        county_keys = {county_key(value) for value in county_values}
        if len(county_keys) > 1:
            raise ValueError("TxGIO county selectors conflict")
        county = county_values[0] if county_values else None

        collection_id = str(getattr(args, "collection_id", None) or "").strip()
        if adapter_command == "releases":
            if county is not None:
                raise ValueError(
                    "TxGIO release discovery lists collections statewide; "
                    "select a county with manifest, probe, or download"
                )
            if collection_id:
                raise ValueError(
                    "TxGIO release discovery already lists historical "
                    "collection IDs; select one with manifest, probe, or "
                    "download"
                )
            argv = ["releases"]
        elif adapter_command == "manifest":
            argv = ["manifest"]
        elif adapter_command in {"probe", "download"}:
            if county is None:
                raise ValueError(
                    f"TxGIO {args.command} requires --county, a county "
                    "GEOID, or an explicit statewide selector such as "
                    "--county 48"
                )
            argv = [adapter_command]
        else:
            raise ValueError(f"TxGIO land parcels do not translate {args.command}")

        if collection_id:
            argv.extend(["--collection-id", collection_id])
        if county is not None:
            argv.extend(["--county", county])
        if adapter_command == "probe" and args.range_bytes is not None:
            argv.extend(["--sample-bytes", str(args.range_bytes)])
        if adapter_command == "download":
            if not args.destination:
                raise ValueError("TxGIO shared download requires --destination")
            argv.extend(["--destination", args.destination])
            if not args.resume:
                argv.append("--no-resume")
            if args.expected_sha256:
                argv.extend(["--expected-sha256", args.expected_sha256])
            if args.max_download_bytes is not None:
                argv.extend(["--max-download-bytes", str(args.max_download_bytes)])
            if args.chunk_size is not None:
                argv.extend(["--chunk-size", str(args.chunk_size)])

        argv.extend(
            [
                "--catalog-db",
                args.catalog_db,
                "--timeout",
                str(args.timeout if args.timeout is not None else 60.0),
                "--retry-attempts",
                "3",
                "--minimum-interval",
                str(args.minimum_interval),
            ]
        )

    try:
        return query_txgio_land_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid TxGIO land-parcel selector for {adapter_command}"
        ) from error


def _montana_cadastral_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors without conflating ORION and Census codes."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "30", "MT", "US-MT"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("30")
    ):
        raise ValueError(
            "Montana cadastral queries use Montana context 30/MT/US-MT "
            "or a Montana county GEOID"
        )
    if args.artifact_path:
        raise ValueError(
            "Montana cadastral live queries and bulk transfer use the "
            "published remote adapter, not --artifact-path"
        )
    if getattr(args, "collection_id", None):
        raise ValueError(
            "Montana rolling releases do not use --collection-id"
        )

    selector = str(args.query or "").strip()
    selector_is_all = selector.casefold() in {"", "*", "all"}
    bulk_commands = {"manifest", "probe", "download"}
    county_values = [
        str(value).strip()
        for value in (
            args.county_selector,
            args.county_fips,
            (
                jurisdiction
                if len(jurisdiction) == 5 and jurisdiction.isdigit()
                else None
            ),
            (
                selector
                if adapter_command in bulk_commands and not selector_is_all
                else None
            ),
        )
        if value not in (None, "")
    ]
    counties = []
    for value in county_values:
        try:
            county = query_montana_cadastral._county_from_selector(value)
        except query_montana_cadastral.MontanaCadastralError as error:
            raise ValueError(str(error)) from error
        if county is not None:
            counties.append(county)
    county_geoids = {county.geoid for county in counties}
    if len(county_geoids) > 1:
        raise ValueError("Montana county selectors conflict")
    county = counties[0] if counties else None

    dataset_type = str(args.dataset_type or "").strip().casefold()
    if dataset_type and dataset_type not in query_montana_cadastral.DATASET_TYPES:
        raise ValueError(
            "Montana --dataset-type must be parcel-shp, parcel-gdb, or orion"
        )

    live_commands = {
        "search",
        "owner",
        "address",
        "parcel",
        "account",
        "map",
        "point",
        "count",
    }
    connection_args = True
    if adapter_command in live_commands:
        if dataset_type:
            raise ValueError(
                "Montana --dataset-type selects bulk releases, not live queries"
            )
        if not selector:
            raise ValueError(f"Montana {args.command} requires a selector")

        requested_field = str(args.search_field or "").strip().casefold()
        fixed_field = {
            "owner": "owner",
            "address": "address",
            "parcel": "parcel",
            "account": "account",
            "map": "parcel",
        }.get(adapter_command)
        valid_fixed_fields = {"", "any", fixed_field}
        if fixed_field == "account":
            valid_fixed_fields.update(
                {"property", "property-id", "assessment-code"}
            )
        if (
            fixed_field is not None
            and requested_field not in valid_fixed_fields
        ):
            raise ValueError(
                f"Montana {args.command} does not use "
                f"--search-field {requested_field}"
            )
        if adapter_command == "point" and requested_field:
            raise ValueError("Montana point does not use --search-field")

        if adapter_command == "point":
            coordinates = [part.strip() for part in selector.split(",")]
            if len(coordinates) != 2:
                raise ValueError(
                    "Montana point requires a longitude,latitude selector"
                )
            try:
                longitude, latitude = map(float, coordinates)
            except ValueError as error:
                raise ValueError(
                    "Montana point requires numeric longitude and latitude"
                ) from error
            argv = ["point", str(longitude), str(latitude)]
        elif adapter_command == "count":
            field = requested_field or "any"
            filters = {
                "any": ("--query", selector),
                "owner": ("--owner", selector),
                "address": ("--address", selector),
                "parcel": ("--parcel-id", selector),
                "account": ("--property-id", selector),
                "property": ("--property-id", selector),
                "property-id": ("--property-id", selector),
                "assessment-code": ("--property-id", selector),
            }
            try:
                flag, value = filters[field]
            except KeyError as error:
                raise ValueError(
                    "Montana count --search-field must be any, owner, "
                    "address, parcel, account, property-id, or assessment-code"
                ) from error
            argv = ["count", flag, value]
            if args.cursor:
                raise ValueError("Montana count does not use a continuation cursor")
            if args.limit_explicit or args.max_records is not None:
                raise ValueError(
                    "Montana count returns one complete count and does not use "
                    "a result limit"
                )
        else:
            if adapter_command == "search":
                field = requested_field or "any"
                command_and_selector = {
                    "any": ("search", "--query"),
                    "owner": ("owner", None),
                    "address": ("address", None),
                    "parcel": ("parcel", None),
                    "account": ("search", "--property-id"),
                    "property": ("search", "--property-id"),
                    "property-id": ("search", "--property-id"),
                    "assessment-code": ("search", "--property-id"),
                }
                try:
                    native_command, selector_flag = command_and_selector[field]
                except KeyError as error:
                    raise ValueError(
                        "Montana search --search-field must be any, owner, "
                        "address, parcel, account, property-id, or "
                        "assessment-code"
                    ) from error
            elif adapter_command == "map":
                native_command, selector_flag = "parcel", None
            elif adapter_command == "account":
                native_command, selector_flag = "search", "--property-id"
            else:
                native_command, selector_flag = adapter_command, None
            argv = [native_command]
            if selector_flag is not None:
                argv.extend([selector_flag, selector])
            else:
                argv.append(selector)

        if county is not None:
            argv.extend(["--county", county.geoid])
        if args.tax_year is not None:
            argv.extend(["--tax-year", str(args.tax_year)])
        selected_limit = _selected_live_limit(args)
        if adapter_command not in {"count"} and selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if adapter_command not in {"count"} and args.cursor:
            argv.extend(["--cursor", args.cursor])
        if (
            adapter_command not in {"count"}
            and (args.geometry or adapter_command in {"map", "point"})
        ):
            argv.append("--geometry")
        if adapter_command not in {"count"}:
            argv.extend(["--page-size", str(args.page_size)])
    elif adapter_command == "discovery":
        if dataset_type or county is not None or args.tax_year is not None:
            raise ValueError(
                "Montana discovery does not use dataset, county, or tax-year selectors"
            )
        route_selector = selector.casefold()
        if route_selector in {"", "*", "all", "routes", "alternatives"}:
            argv = ["alternatives"]
            connection_args = False
        elif route_selector in {"counties", "coverage"}:
            argv = ["counties"]
        else:
            raise ValueError(
                "Montana discovery selector must be routes, alternatives, "
                "counties, or coverage"
            )
        if args.cursor or args.limit_explicit or args.max_records is not None:
            raise ValueError(
                "Montana discovery returns its complete route or county set"
            )
    elif adapter_command == "releases":
        if not selector_is_all:
            raise ValueError(
                "Montana release discovery does not use a county selector"
            )
        if dataset_type or county is not None or args.tax_year is not None:
            raise ValueError(
                "Montana releases lists all current parcel and ORION routes"
            )
        if args.cursor or args.limit_explicit or args.max_records is not None:
            raise ValueError(
                "Montana releases returns its complete discovered release set"
            )
        argv = ["releases"]
    elif adapter_command == "probe" and not dataset_type:
        if not selector_is_all:
            raise ValueError(
                "Montana live probe does not use a record selector"
            )
        if county is not None or args.tax_year is not None:
            raise ValueError(
                "Montana live probe uses the adapter's fixed statewide sentinel"
            )
        if args.cursor or args.limit_explicit or args.max_records is not None:
            raise ValueError(
                "Montana live probe is bounded internally and does not use "
                "shared cursor or limit selectors"
            )
        argv = ["probe"]
    elif adapter_command in {"manifest", "probe", "download"}:
        if not dataset_type:
            raise ValueError(
                f"Montana {args.command} bulk operation requires --dataset-type"
            )
        if args.tax_year is not None:
            raise ValueError(
                "Montana bulk release identity comes from the rolling artifact "
                "listing, not --tax-year"
            )
        if args.cursor or args.limit_explicit or args.max_records is not None:
            raise ValueError(
                f"Montana {args.command} bulk operation does not use a "
                "continuation cursor or result limit"
            )
        native_command = (
            "artifact-probe" if adapter_command == "probe" else adapter_command
        )
        argv = [native_command, "--dataset", dataset_type]
        if county is not None:
            argv.extend(["--county", county.geoid])
        if native_command == "artifact-probe" and args.range_bytes is not None:
            argv.extend(["--range-bytes", str(args.range_bytes)])
        if native_command == "download":
            if not args.destination:
                raise ValueError(
                    "Montana shared download requires --destination"
                )
            argv.extend(["--destination", args.destination])
            if not args.resume:
                argv.append("--no-resume")
            if args.expected_sha256:
                argv.extend(["--expected-sha256", args.expected_sha256])
            if args.max_download_bytes is not None:
                argv.extend(
                    ["--max-download-bytes", str(args.max_download_bytes)]
                )
            if args.chunk_size is not None:
                argv.extend(["--chunk-size", str(args.chunk_size)])
    else:
        raise ValueError(
            f"Montana cadastral does not translate shared operation {args.command}"
        )

    if connection_args:
        argv.extend(
            [
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else query_montana_cadastral.DEFAULT_TIMEOUT
                ),
                "--retry-attempts",
                "3",
                "--minimum-interval",
                str(args.minimum_interval),
            ]
        )
    try:
        return query_montana_cadastral.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Montana cadastral selector for {adapter_command}"
        ) from error


def _virginia_beach_delinquent_tax_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the current Treasurer installment table."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "51", "VA", "US-VA", "51810"}:
        raise ValueError(
            "Virginia Beach delinquent-tax queries use Virginia context "
            "51/VA/US-VA or Virginia Beach GEOID 51810"
        )
    county_values = [
        str(value).strip().casefold()
        for value in (args.county_selector, args.county_fips)
        if value not in (None, "")
    ]
    locality_aliases = {
        "810",
        "51810",
        "virginia beach",
        "virginia beach city",
        "city of virginia beach",
    }
    if any(value not in locality_aliases for value in county_values):
        raise ValueError(
            "Virginia Beach delinquent-tax queries cover GEOID 51810"
        )
    if args.geometry:
        raise ValueError(
            "The delinquent-tax table has no parcel geometry; use the "
            "official VGIN parcel complement for map records"
        )

    if adapter_command == "routes":
        try:
            return query_va_beach_delinquent_tax.build_parser().parse_args(
                ["routes"]
            )
        except SystemExit as error:
            raise ValueError(
                "invalid Virginia Beach related-route request"
            ) from error

    selector = str(args.query or "").strip()
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    command = adapter_command
    if args.command == "search":
        command_by_field = {
            "": "search",
            "any": "search",
            "query": "search",
            "text": "search",
            "owner": "owner",
            "address": "address",
            "parcel": "parcel",
            "gpin": "parcel",
            "bill": "bill",
            "tax-bill": "bill",
            "event": "bill",
        }
        try:
            command = command_by_field[requested_field]
        except KeyError as error:
            raise ValueError(
                "Virginia Beach --search-field must be any, owner, address, "
                "parcel/GPIN, or bill/event"
            ) from error
    elif requested_field:
        allowed_fields = {
            "owner": {"any", "owner"},
            "address": {"any", "address"},
            "parcel": {"any", "parcel", "gpin"},
            "bill": {"any", "bill", "tax-bill", "event"},
            "probe": {
                "owner",
                "address",
                "parcel",
                "gpin",
                "bill",
                "tax-bill",
                "event",
            },
        }.get(command, set())
        if requested_field not in allowed_fields:
            raise ValueError(
                f"Virginia Beach {args.command} does not use "
                f"--search-field {requested_field}"
            )

    if command == "probe":
        argv = ["probe"]
        if selector:
            option_by_field = {
                "owner": "--owner",
                "address": "--address",
                "parcel": "--gpin",
                "gpin": "--gpin",
                "bill": "--bill-number",
                "tax-bill": "--bill-number",
                "event": "--bill-number",
            }
            try:
                option = option_by_field[requested_field]
            except KeyError as error:
                raise ValueError(
                    "A filtered Virginia Beach probe pairs its selector with "
                    "--search-field owner, address, parcel/GPIN, or bill/event"
                ) from error
            argv.extend([option, selector])
    else:
        if not selector:
            raise ValueError(
                f"Virginia Beach {args.command} requires a non-empty selector"
            )
        argv = [command, selector]

    if args.tax_year is not None:
        argv.extend(["--tax-year", str(args.tax_year)])
    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and command != "probe":
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor:
        argv.extend(["--cursor", args.cursor])
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--catalog-db",
            args.catalog_db,
            "--catalog-config",
            str(
                query_va_beach_delinquent_tax.DEFAULT_CATALOG_CONFIG_PATH
            ),
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_va_beach_delinquent_tax.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
        ]
    )
    try:
        return query_va_beach_delinquent_tax.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Virginia Beach delinquent-tax selector for {command}"
        ) from error


def _georgia_property_source_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared discovery selectors to Georgia's statewide routes."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "13", "GA", "US-GA"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("13")
    ):
        raise ValueError(
            "Georgia property-source queries use state context "
            "13/GA/US-GA or a Georgia county GEOID"
        )

    county = str(args.county_fips or "").strip()
    if not county and len(jurisdiction) == 5 and jurisdiction.isdigit():
        county = jurisdiction
    if county:
        try:
            context_county = query_georgia_property_sources._county_name(county)
        except query_georgia_property_sources.GeorgiaPropertySourceError as error:
            raise ValueError(str(error)) from error
    else:
        context_county = None

    selector = str(args.query or "").strip()
    selector_key = selector.casefold()
    field = str(args.search_field or "").strip().casefold().replace("_", "-")
    argv: list[str]

    if adapter_command == "probe":
        argv = ["probe", "--source", args.source]
    elif args.source == GEORGIA_GSCCCA_SOURCE_ID:
        if adapter_command != "handoff":
            raise ValueError(f"Georgia GSCCCA does not translate {args.command}")
        if (
            county
            or field
            or selector_key
            not in {
                "",
                "*",
                "all",
                "statewide",
                "handoff",
                "account",
            }
        ):
            raise ValueError(
                "Georgia GSCCCA discovery returns the statewide acquisition "
                "handoff and does not apply record selectors"
            )
        if args.cursor:
            raise ValueError(
                "Georgia GSCCCA discovery does not use a continuation cursor"
            )
        argv = ["handoff"]
    elif adapter_command == "directory":
        if field in {"platforms", "platform-summary", "platform-summary-all"}:
            if county or selector_key not in {"", "*", "all", "statewide"}:
                raise ValueError(
                    "Georgia platform summary is statewide; use platform "
                    "search for one destination family"
                )
            if args.cursor:
                raise ValueError(
                    "Georgia platform summary does not use a continuation cursor"
                )
            argv = ["platforms"]
        else:
            argv = ["directory"]
            if field in {"", "any", "query", "text"}:
                argv.append(selector or "*")
                if context_county:
                    argv.extend(["--county", context_county])
            elif field in {"county", "county-name", "county-fips", "fips"}:
                selected_county = selector or context_county
                if not selected_county:
                    raise ValueError(
                        "Georgia directory county search requires a county selector"
                    )
                try:
                    selected_county = query_georgia_property_sources._county_name(
                        selected_county
                    )
                except (
                    query_georgia_property_sources.GeorgiaPropertySourceError
                ) as error:
                    raise ValueError(str(error)) from error
                if context_county and selected_county != context_county:
                    raise ValueError(
                        "Georgia directory county query conflicts with "
                        "--county-fips or --jurisdiction"
                    )
                argv.extend(["*", "--county", selected_county])
            elif field in {"platform", "platform-family"}:
                if not selector:
                    raise ValueError(
                        "Georgia directory platform search requires a platform"
                    )
                argv.extend(["*", "--platform", selector])
                if context_county:
                    argv.extend(["--county", context_county])
            else:
                raise ValueError(
                    "Georgia directory --search-field must be any, county, "
                    "platform, or platforms"
                )

            selected_limit = _selected_live_limit(args)
            if selected_limit is not None:
                argv.extend(["--limit", str(selected_limit)])
            if args.cursor:
                argv.extend(["--cursor", args.cursor])
    else:
        raise ValueError(f"Georgia property sources do not translate {args.command}")

    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_georgia_property_sources.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--max-attempts",
            "3",
        ]
    )
    try:
        return query_georgia_property_sources.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Georgia property-source selector for {adapter_command}"
        ) from error


def _virginia_vgin_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to VGIN parcel discovery and geometry."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    is_source_locality_code = (
        jurisdiction.isdigit()
        and len(jurisdiction) in {5, 7}
        and jurisdiction.startswith("51")
    )
    if jurisdiction not in {"", "51", "VA"} and not is_source_locality_code:
        raise ValueError(
            "VGIN parcels accept Virginia context 51/VA or a five- or "
            "seven-digit VGIN locality code beginning with 51"
        )
    locality_code = str(args.county_fips or "").strip()
    if not locality_code and is_source_locality_code:
        locality_code = jurisdiction
    if locality_code and not (
        locality_code.isdigit()
        and len(locality_code) in {5, 7, 8}
        and locality_code.startswith("51")
    ):
        raise ValueError(
            "VGIN --county-code must be a Virginia locality code beginning with 51"
        )

    selector = str(args.query or "").strip()
    requested_field = str(args.search_field or "").strip().casefold().replace("_", "-")
    command = adapter_command
    argv: list[str]

    parcel_field_aliases = {
        "": "auto",
        "any": "auto",
        "auto": "auto",
        "parcel": "auto",
        "parcel-id": "parcel-id",
        "parcelid": "parcel-id",
        "local-parcel-id": "parcel-id",
        "ptm": "ptm-id",
        "ptm-id": "ptm-id",
        "tax-map": "ptm-id",
        "tax-map-id": "ptm-id",
        "qpid": "vgin-qpid",
        "vgin-qpid": "vgin-qpid",
    }
    if command in {"parcel", "map"}:
        if requested_field == "objectid":
            command = "objectid"
            argv = [command, selector]
        else:
            try:
                parcel_field = parcel_field_aliases[requested_field]
            except KeyError as error:
                raise ValueError(
                    "VGIN parcel/map --search-field must be auto, parcel-id, "
                    "ptm-id, vgin-qpid, or objectid"
                ) from error
            command = "parcel"
            argv = [command, selector, "--field", parcel_field]
    elif command == "search":
        if requested_field in parcel_field_aliases:
            command = "parcel"
            argv = [
                command,
                selector,
                "--field",
                parcel_field_aliases[requested_field],
            ]
        elif requested_field == "objectid":
            command = "objectid"
            argv = [command, selector]
        elif requested_field in {"locality", "locality-name"}:
            argv = ["search", "--locality", selector]
        elif requested_field in {"fips", "locality-code", "county"}:
            if locality_code and locality_code != selector:
                raise ValueError(
                    "VGIN query locality code conflicts with jurisdiction context"
                )
            locality_code = selector
            argv = ["search"]
        elif requested_field in {"updated-after", "updated-before"}:
            argv = ["search", f"--{requested_field}", selector]
        else:
            raise ValueError(
                "VGIN search --search-field must be auto, parcel-id, ptm-id, "
                "vgin-qpid, objectid, locality, fips, updated-after, or "
                "updated-before"
            )
    elif command == "count":
        argv = ["count"]
        if selector.casefold() not in {"*", "all", "statewide"}:
            option_by_field = {
                "parcel-id": "--parcel-id",
                "parcelid": "--parcel-id",
                "local-parcel-id": "--parcel-id",
                "ptm": "--ptm-id",
                "ptm-id": "--ptm-id",
                "tax-map": "--ptm-id",
                "tax-map-id": "--ptm-id",
                "qpid": "--vgin-qpid",
                "vgin-qpid": "--vgin-qpid",
                "locality": "--locality",
                "locality-name": "--locality",
                "fips": "--fips",
                "locality-code": "--fips",
                "county": "--fips",
                "updated-after": "--updated-after",
                "updated-before": "--updated-before",
            }
            try:
                option = option_by_field[requested_field]
            except KeyError as error:
                raise ValueError(
                    "VGIN count requires '*', or --search-field parcel-id, "
                    "ptm-id, vgin-qpid, locality, fips, updated-after, or "
                    "updated-before"
                ) from error
            argv.extend([option, selector])
            if option == "--fips":
                locality_code = ""
    elif command in {"point", "bbox"}:
        coordinate_count = 2 if command == "point" else 4
        argv = [
            command,
            *_washington_parcel_coordinates(
                selector,
                count=coordinate_count,
                operation=command,
            ),
        ]
    elif command == "localities":
        argv = ["localities"]
    elif command == "probe":
        argv = ["probe"]
    else:
        raise ValueError(f"VGIN parcels do not translate {args.command}")

    if locality_code and command in {
        "parcel",
        "search",
        "count",
        "point",
        "bbox",
    }:
        argv.extend(["--fips", locality_code])
    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and command in {
        "parcel",
        "objectid",
        "search",
        "point",
        "bbox",
    }:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor and command in {
        "parcel",
        "objectid",
        "search",
        "point",
        "bbox",
    }:
        argv.extend(["--cursor", args.cursor])
    if command in {
        "parcel",
        "objectid",
        "search",
        "point",
        "bbox",
        "probe",
    } and (args.geometry or args.command == "map"):
        argv.append("--geometry")
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_virginia_parcels.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_virginia_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid VGIN parcel selector for {adapter_command}"
        ) from error


def _wisconsin_statewide_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to Wisconsin's statewide parcel layer."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "55", "WI"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("55")
    ):
        raise ValueError(
            "Wisconsin statewide parcels accept state context 55/WI or a "
            "Wisconsin county GEOID"
        )
    county = str(args.county_fips or "").strip()
    if not county and len(jurisdiction) == 5 and jurisdiction.isdigit():
        county = jurisdiction
    selector = str(args.query or "").strip()
    command = adapter_command
    if command == "search":
        command = str(args.search_field or "owner").strip().casefold()
        if command not in {"owner", "address", "mailing", "parcel"}:
            raise ValueError(
                "Wisconsin parcel --search-field must be owner, address, "
                "mailing, or parcel"
            )

    argv = [command]
    if command != "probe":
        argv.append(selector)
    if county:
        argv.extend(["--county", county])
    selected_limit = _selected_live_limit(args)
    if selected_limit is not None:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor:
        argv.extend(["--cursor", args.cursor])
    if args.geometry or args.command == "map":
        argv.append("--geometry")
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_wisconsin_parcels.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_wisconsin_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Wisconsin parcel selector for {adapter_command}"
        ) from error


def _wyoming_county_from_shared_args(args: argparse.Namespace) -> str | None:
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction in {"", "56", "WY", "US-WY"}:
        state_county = None
    elif len(jurisdiction) == 5 and jurisdiction.isdigit() and jurisdiction.startswith(
        "56"
    ):
        state_county = next(
            (
                value["name"]
                for value in query_wy_dor_parcels.COUNTIES.values()
                if value["fips"] == jurisdiction[-3:]
            ),
            None,
        )
        if state_county is None:
            raise ValueError("unknown Wyoming county GEOID")
    else:
        raise ValueError(
            "Wyoming DOR parcels accept state context 56/WY/US-WY or a "
            "Wyoming county GEOID"
        )

    county_selector = str(
        args.county_fips or args.county_selector or state_county or ""
    ).strip()
    if not county_selector:
        return None
    if county_selector.isdigit() and len(county_selector) in {3, 5}:
        suffix = county_selector[-3:]
        county_selector = next(
            (
                value["name"]
                for value in query_wy_dor_parcels.COUNTIES.values()
                if value["fips"] == suffix
            ),
            county_selector,
        )
    try:
        return query_wy_dor_parcels.normalize_jurisdiction(county_selector)
    except ValueError as error:
        raise ValueError("unknown Wyoming county selector") from error


def _wyoming_dor_statewide_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate every Wyoming annual-parcel selector without adding a cap."""

    county = _wyoming_county_from_shared_args(args)
    selector = str(args.query or "").strip()
    command = adapter_command
    if command == "search":
        command = str(args.search_field or "owner").strip().casefold().replace(
            "_", "-"
        )
        command = {"address": "situs", "objectid": "fid"}.get(command, command)
        if command not in {
            "owner",
            "parcel",
            "account",
            "county",
            "jurisdiction",
            "situs",
            "mailing",
            "legal",
            "fid",
            "geometry",
        }:
            raise ValueError(
                "Wyoming parcel --search-field must be owner, parcel, account, "
                "county, jurisdiction, situs, mailing, legal, fid, or geometry"
            )

    if command == "discovery":
        mode = selector.casefold() if selector else "source"
        argv = ["discovery", mode]
    elif command == "probe":
        argv = ["probe"]
    elif command == "point":
        coordinates = [value.strip() for value in selector.split(",")]
        if len(coordinates) != 2 or any(not value for value in coordinates):
            raise ValueError("Wyoming point selectors use longitude,latitude")
        argv = ["point", *coordinates]
    elif command == "bbox":
        coordinates = [value.strip() for value in selector.split(",")]
        if len(coordinates) != 4 or any(not value for value in coordinates):
            raise ValueError("Wyoming bbox selectors use west,south,east,north")
        argv = ["bbox", *coordinates]
    else:
        if not selector:
            raise ValueError(f"Wyoming {command} requires a selector")
        if command in {"county", "jurisdiction"} and selector.isdigit():
            suffix = selector[-3:]
            selector = next(
                (
                    value["name"]
                    for value in query_wy_dor_parcels.COUNTIES.values()
                    if value["fips"] == suffix
                ),
                selector,
            )
        argv = [command, selector]

    if command not in {"discovery", "probe"}:
        if county and command not in {"county", "jurisdiction"}:
            argv.extend(["--jurisdiction", county])
        if args.tax_year is not None:
            argv.extend(["--tax-year", str(args.tax_year)])
        if args.geometry or args.command == "map":
            argv.append("--geometry")
        if args.limit_explicit:
            argv.extend(["--limit", str(args.limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
        if args.max_records is not None:
            argv.extend(["--max-records", str(args.max_records)])
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_wy_dor_parcels.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
        ]
    )
    try:
        return query_wy_dor_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Wyoming DOR parcel selector for {adapter_command}"
        ) from error


def _ohio_pax_recorder_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to one verified Ohio recorder component."""

    try:
        tenant = query_ohio_pax_recorders.TENANTS_BY_QUERY_SOURCE[args.source]
    except KeyError as error:
        raise ValueError(f"unknown Ohio recorder component {args.source}") from error

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {
        "",
        "39",
        "OH",
        "US-OH",
        tenant.county_fips,
    }:
        raise ValueError(
            f"{tenant.county_name} recorder serves county GEOID "
            f"{tenant.county_fips}"
        )
    accepted_counties = {
        tenant.county_fips,
        tenant.county_fips[-3:],
        tenant.county_name.upper(),
        tenant.county_name.removesuffix(" County").upper(),
    }
    for raw_county in (args.county_fips, args.county_selector):
        county = str(raw_county or "").strip().upper()
        if county and county not in accepted_counties:
            raise ValueError(
                f"{tenant.county_name} recorder does not serve "
                f"county selector {raw_county!r}"
            )
    if args.geometry:
        raise ValueError(
            "Ohio recorder instruments do not publish parcel geometry"
        )

    selector = str(args.query or "").strip()
    source_args = ["--source", str(args.source)]
    argv: list[str]
    if adapter_command == "search":
        field = (
            str(args.search_field or "")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        argv = ["search", *source_args]
        if field in {"", "any", "name", "party"}:
            if selector not in {"*", "all"}:
                argv.extend(["--name", selector])
        elif field in {"grantor", "first-party"}:
            argv.extend(["--name", selector, "--party", "first"])
        elif field in {"grantee", "second-party"}:
            argv.extend(["--name", selector, "--party", "second"])
        elif field in {"instrument", "instrument-number"}:
            argv.extend(["--instrument", selector])
        elif field in {"book-page", "book/page"}:
            match = re.fullmatch(r"\s*([^/]+?)\s*/\s*([^/]+?)\s*", selector)
            if match is None:
                raise ValueError(
                    "Ohio recorder book/page selectors use BOOK/PAGE"
                )
            argv.extend(
                [
                    "--book",
                    match.group(1),
                    "--page",
                    match.group(2),
                ]
            )
        elif field in {"document-id", "document"}:
            argv.extend(["--document-id", selector])
        elif field in {"date", "recorded-date"}:
            if args.from_date or args.to_date:
                raise ValueError(
                    "Use either the exact recorded-date selector or "
                    "--from-date/--to-date"
                )
            argv.extend(
                [
                    "--recorded-from",
                    selector,
                    "--recorded-to",
                    selector,
                ]
            )
        else:
            raise ValueError(
                "Ohio recorder --search-field must be name, party, grantor, "
                "grantee, instrument, book-page, document-id, or recorded-date"
            )
        if args.from_date:
            argv.extend(["--recorded-from", args.from_date])
        if args.to_date:
            argv.extend(["--recorded-to", args.to_date])
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif adapter_command == "document-info":
        argv = ["document-info", *source_args, selector]
    elif adapter_command == "download":
        if not args.destination:
            raise ValueError(
                "Ohio recorder document download requires --destination"
            )
        argv = [
            "download",
            *source_args,
            selector,
            "--destination",
            args.destination,
        ]
    elif adapter_command == "probe":
        if selector and selector.casefold() not in {"*", "all"}:
            raise ValueError(
                "Ohio recorder probes use each component's fixed sentinel"
            )
        argv = ["probe", *source_args]
    else:
        raise ValueError(
            f"Ohio recorder components do not translate {args.command}"
        )

    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_ohio_pax_recorders.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_ohio_pax_recorders.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Ohio recorder selector for {adapter_command}"
        ) from error


def _validate_fixed_ohio_county(
    args: argparse.Namespace,
    *,
    county_geoid: str,
    county_name: str,
    source_label: str,
) -> None:
    """Keep a county-specific source inside its published jurisdiction."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", county_geoid}:
        raise ValueError(f"{source_label} serves county GEOID {county_geoid}")
    short_name = county_name.split(",", 1)[0]
    accepted_counties = {
        county_geoid,
        county_geoid[-3:],
        short_name.upper(),
        short_name.removesuffix(" County").upper(),
    }
    for raw_county in (args.county_fips, args.county_selector):
        county = str(raw_county or "").strip().upper()
        if county and county not in accepted_counties:
            raise ValueError(
                f"{source_label} does not serve county selector "
                f"{raw_county!r}"
            )
    if args.geometry:
        raise ValueError(f"{source_label} does not publish parcel geometry")


def _franklin_auditor_bulk_family(value: Any) -> str:
    normalized = str(value or "").strip().casefold().replace("_", "-")
    aliases = {
        "appraisal": "appraisal",
        "assessment": "appraisal",
        "assessment-roll": "appraisal",
        "tax": "tax-accounting",
        "tax-accounting": "tax-accounting",
        "payments": "tax-accounting",
        "daily-conveyance": "daily-conveyances",
        "daily-conveyances": "daily-conveyances",
        "conveyances": "daily-conveyances",
        "gis": "gis-shapefiles",
        "gis-shapefile": "gis-shapefiles",
        "gis-shapefiles": "gis-shapefiles",
        "parcel-csv": "parcel-csv",
        "parcels-csv": "parcel-csv",
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise ValueError(
            "Franklin Auditor bulk --dataset-type must select appraisal, "
            "tax-accounting, daily-conveyances, gis-shapefiles, or parcel-csv"
        ) from error


def _ohio_franklin_auditor_bulk_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared bulk and local-row selectors to the Auditor library."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", "39049"}:
        raise ValueError(
            "Franklin County Auditor bulk data serves county GEOID 39049"
        )
    accepted_counties = {
        "049",
        "39049",
        "franklin",
        "franklin county",
    }
    for raw_county in (args.county_fips, args.county_selector):
        county = re.sub(
            r"[^a-z0-9]+", " ", str(raw_county or "").casefold()
        ).strip()
        if county and county not in accepted_counties:
            raise ValueError(
                "Franklin County Auditor bulk data does not serve county "
                f"selector {raw_county!r}"
            )

    selector = str(args.query or "").strip()
    selector_is_all = selector.casefold() in {"", "*", "all", "current"}
    selected_limit = _selected_live_limit(args)
    argv: list[str]

    if adapter_command == "source":
        if selector.casefold() in {"families", "datasets", "dataset-families"}:
            argv = ["families"]
        elif selector_is_all or selector.casefold() in {"source", "contract"}:
            argv = ["source"]
        else:
            raise ValueError(
                "Franklin Auditor discovery accepts source or families"
            )
    elif adapter_command == "releases":
        family = _franklin_auditor_bulk_family(args.dataset_type)
        argv = ["releases", family]
        year = args.tax_year
        if selector and selector.casefold() not in {"current", "*", "all"}:
            if not re.fullmatch(r"\d{4}", selector):
                raise ValueError(
                    "Franklin Auditor releases select current, all, or a "
                    "four-digit year"
                )
            selector_year = int(selector)
            if year is not None and year != selector_year:
                raise ValueError("Franklin Auditor release years conflict")
            year = selector_year
        if selector.casefold() in {"*", "all"}:
            if year is not None:
                raise ValueError(
                    "Franklin Auditor all-release discovery does not combine "
                    "with a single year"
                )
            argv.append("--all-releases")
        elif year is not None:
            argv.extend(["--year", str(year)])
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif adapter_command == "artifacts":
        family = _franklin_auditor_bulk_family(args.dataset_type)
        release = str(args.collection_id or "").strip()
        if not selector_is_all:
            if release and release != selector:
                raise ValueError("Franklin Auditor release selectors conflict")
            release = selector
        argv = ["artifacts", family, "--release", release or "current"]
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    elif adapter_command == "probe":
        if args.cursor:
            raise ValueError("Franklin Auditor probes do not use a cursor")
        if args.dataset_type:
            family = _franklin_auditor_bulk_family(args.dataset_type)
            if selector_is_all:
                raise ValueError(
                    "Select an artifact filename or ID when probing one "
                    "Franklin Auditor dataset family"
                )
            argv = ["artifact-probe", family, selector]
            argv.extend(
                ["--release", str(args.collection_id or "current")]
            )
        else:
            if not selector_is_all and selector.casefold() not in {"source", "health"}:
                raise ValueError(
                    "Franklin Auditor source probes take no artifact selector"
                )
            argv = ["probe"]
        if args.range_bytes is not None:
            argv.extend(["--sample-bytes", str(args.range_bytes)])
    elif adapter_command == "download":
        family = _franklin_auditor_bulk_family(args.dataset_type)
        if selector_is_all:
            raise ValueError(
                "Franklin Auditor downloads require an artifact filename or ID"
            )
        if not args.destination:
            raise ValueError(
                "Franklin Auditor shared download requires --destination"
            )
        if args.cursor:
            raise ValueError("Franklin Auditor downloads do not use a cursor")
        argv = [
            "download",
            family,
            selector,
            "--release",
            str(args.collection_id or "current"),
            "--destination",
            args.destination,
        ]
        if args.overwrite:
            argv.append("--overwrite")
        if not args.resume:
            argv.append("--no-resume")
        if args.expected_sha256:
            argv.extend(["--expected-sha256", args.expected_sha256])
        if args.max_download_bytes is not None:
            argv.extend(
                ["--max-download-bytes", str(args.max_download_bytes)]
            )
    elif adapter_command == "rows":
        if not args.artifact_path:
            raise ValueError(
                "Franklin Auditor local row search requires --artifact-path"
            )
        if not args.collection_id:
            raise ValueError(
                "Franklin Auditor local row search requires --collection-id "
                "for the release identity"
            )
        record_family = (
            str(args.dataset_type or "").strip().casefold().replace("_", "-")
        )
        if record_family not in query_ohio_franklin_auditor_bulk.RECORD_FAMILY_CHOICES:
            raise ValueError(
                "Franklin Auditor local rows use --dataset-type parcel, value, "
                "payment, transfer, sales, or daily-conveyance"
            )
        argv = [
            "rows",
            args.artifact_path,
            "--record-family",
            record_family,
            "--release-id",
            args.collection_id,
        ]
        if args.artifact_source_url:
            argv.extend(["--source-url", args.artifact_source_url])
        release_dates = re.findall(
            r"(?<!\d)((?:19|20)\d{2}-\d{2}-\d{2})(?!\d)",
            args.collection_id,
        )
        if release_dates:
            argv.extend(["--release-date", release_dates[-1]])
        if args.command == "parcel":
            argv.extend(["--parcel", selector])
        elif selector and selector.casefold() not in {"*", "all"}:
            argv.extend(["--query", selector])
        if args.from_date:
            argv.extend(["--from-date", args.from_date])
        if args.to_date:
            argv.extend(["--to-date", args.to_date])
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    else:
        raise ValueError(
            f"Franklin Auditor bulk data does not translate {args.command}"
        )

    if argv[0] in {"releases", "artifacts", "artifact-probe", "download", "probe"}:
        argv.extend(
            [
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else query_ohio_franklin_auditor_bulk.DEFAULT_TIMEOUT
                ),
                "--minimum-interval",
                str(args.minimum_interval),
                "--retry-attempts",
                str(query_ohio_franklin_auditor_bulk.DEFAULT_RETRY_ATTEMPTS),
            ]
        )
        if args.chunk_size is not None:
            argv.extend(["--chunk-size", str(args.chunk_size)])
    try:
        return query_ohio_franklin_auditor_bulk.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Franklin Auditor bulk selector for {adapter_command}"
        ) from error


def _ohio_franklin_sales_gis_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to Franklin Auditor sale occurrences."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", "39049"}:
        raise ValueError(
            "Franklin County Auditor Sales GIS serves county GEOID 39049"
        )
    accepted_counties = {"049", "39049", "franklin", "franklin county"}
    for raw_county in (args.county_fips, args.county_selector):
        county = re.sub(
            r"[^a-z0-9]+", " ", str(raw_county or "").casefold()
        ).strip()
        if county and county not in accepted_counties:
            raise ValueError(
                "Franklin County Auditor Sales GIS does not serve county "
                f"selector {raw_county!r}"
            )

    selector = str(args.query or "").strip()
    selector_is_all = selector.casefold() in {"", "*", "all"}
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    command = adapter_command
    argv: list[str]

    if command == "source":
        if selector.casefold() in {"layers", "aliases", "layer-contract"}:
            argv = ["layers"]
        elif selector_is_all or selector.casefold() in {"source", "contract"}:
            argv = ["source"]
        else:
            raise ValueError(
                "Franklin Sales GIS discovery accepts source or layers"
            )
    elif command in {"schema", "count", "probe"}:
        if not selector_is_all and selector.casefold() not in {
            command,
            "health",
            "metadata",
        }:
            raise ValueError(
                f"Franklin Sales GIS {command} does not use a record selector"
            )
        if args.cursor:
            raise ValueError(f"Franklin Sales GIS {command} does not use a cursor")
        argv = [command]
    elif command == "search":
        implicit_field = "address" if args.command == "address" else ""
        field_aliases = {
            "": "all",
            "all": "all",
            "auto": "all",
            "party": "party",
            "grantor": "party",
            "grantee": "party",
            "parcel": "parcel",
            "parcel-id": "parcel",
            "conveyance": "conveyance",
            "conveyance-number": "conveyance",
            "instrument": "conveyance",
            "address": "address",
            "situs": "address",
            "fid": "object-id",
            "objectid": "object-id",
            "object-id": "object-id",
            "validity": "validity",
            "valid-sale": "validity",
            "date": "date-range",
            "sale-date": "date-range",
            "date-range": "date-range",
        }
        try:
            selected_field = field_aliases[requested_field or implicit_field]
        except KeyError as error:
            raise ValueError(
                "Franklin Sales GIS --search-field must be party, parcel, "
                "conveyance, address, fid, validity, or date"
            ) from error
        if selected_field == "validity":
            if not selector:
                raise ValueError("Franklin Sales GIS validity search needs a value")
            argv = ["validity", selector]
            command = "validity"
        elif selected_field == "date-range":
            command = "date-range"
            argv = ["date-range"]
        else:
            if not selector:
                raise ValueError("Franklin Sales GIS search needs a selector")
            argv = ["search", selector, "--field", selected_field]
    elif command in {"parcel", "conveyance", "party"}:
        if not selector:
            raise ValueError(f"Franklin Sales GIS {command} needs a selector")
        argv = [command, selector]
    elif command == "object-id":
        if not selector:
            raise ValueError("Franklin Sales GIS OBJECTID lookup needs a selector")
        argv = ["search", selector, "--field", "object-id"]
        command = "search"
    elif command == "date-range":
        argv = ["date-range"]
    else:
        raise ValueError(
            f"Franklin County Auditor Sales GIS does not translate {args.command}"
        )

    if command == "date-range":
        start = str(args.from_date or "").strip()
        end = str(args.to_date or "").strip()
        if not selector_is_all:
            try:
                exact_date = query_ohio_franklin_sales_gis._iso_date(selector)
            except argparse.ArgumentTypeError as error:
                raise ValueError(str(error)) from error
            exact = exact_date.isoformat()
            if start and start != exact or end and end != exact:
                raise ValueError(
                    "Franklin Sales GIS exact sale date conflicts with date bounds"
                )
            start = end = exact
        if not start and not end:
            raise ValueError(
                "Franklin Sales GIS date search needs --from-date, --to-date, "
                "or one exact YYYY-MM-DD selector"
            )
        if start:
            argv.extend(["--start", start])
        if end:
            argv.extend(["--end", end])

    if command not in {"source", "layers", "schema", "count", "probe"}:
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
        if args.geometry or args.command in {"map", "geometry"}:
            argv.append("--geometry")
    if command not in {"source", "layers"}:
        argv.extend(
            [
                "--page-size",
                str(args.page_size),
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else query_ohio_franklin_sales_gis.DEFAULT_TIMEOUT
                ),
                "--minimum-interval",
                str(args.minimum_interval),
                "--retry-attempts",
                "3",
            ]
        )
    try:
        return query_ohio_franklin_sales_gis.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Franklin Auditor Sales GIS selector for {adapter_command}"
        ) from error


def _one_ohio_auction_date(
    args: argparse.Namespace,
    *,
    selector_date: str | None = None,
) -> str:
    """Resolve one exact native auction date without widening the query."""

    bounds = [
        str(value).strip()
        for value in (args.from_date, args.to_date)
        if value not in (None, "")
    ]
    if len(set(bounds)) > 1:
        raise ValueError(
            "Ohio sheriff-sale listings require one exact auction date; "
            "--from-date and --to-date must match"
        )
    candidates = [
        value
        for value in (selector_date, bounds[0] if bounds else None)
        if value
    ]
    if not candidates:
        raise ValueError(
            "Ohio sheriff-sale listings require an exact auction date"
        )
    if len(set(candidates)) > 1:
        raise ValueError(
            "Ohio sheriff-sale date selectors refer to different dates"
        )
    try:
        return query_ohio_sheriff_sales._parse_iso_date(candidates[0])
    except argparse.ArgumentTypeError as error:
        raise ValueError(str(error)) from error


def _ohio_sheriff_realauction_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property operations to one official county tenant."""

    try:
        tenant = query_ohio_sheriff_sales.TENANTS_BY_SOURCE_ID[args.source]
    except KeyError as error:
        raise ValueError(
            f"unknown Ohio sheriff-sale component {args.source}"
        ) from error
    _validate_fixed_ohio_county(
        args,
        county_geoid=tenant.county_geoid,
        county_name=tenant.county_name,
        source_label=f"{tenant.county_name} sheriff-sale source",
    )

    selector = str(args.query or "").strip()
    if adapter_command == "source":
        if selector and selector.casefold() not in {"*", "all"}:
            raise ValueError("Ohio sheriff-sale discovery takes no selector")
        argv = ["source", tenant.slug]
    elif adapter_command == "calendar":
        month = selector
        if not month and args.from_date:
            month = _one_ohio_auction_date(args)[:7]
        try:
            month = query_ohio_sheriff_sales._parse_iso_month(month)
        except argparse.ArgumentTypeError as error:
            raise ValueError(
                "Ohio sheriff-sale freshness requires YYYY-MM or "
                "an exact --from-date"
            ) from error
        argv = ["calendar", tenant.slug, "--month", month]
    elif adapter_command == "probe":
        argv = ["probe", tenant.slug]
        if selector:
            argv.extend(
                ["--date", _one_ohio_auction_date(args, selector_date=selector)]
            )
        elif args.from_date or args.to_date:
            argv.extend(["--date", _one_ohio_auction_date(args)])
    elif adapter_command == "auctions":
        selector_date = selector if args.command == "sale" else None
        auction_date = _one_ohio_auction_date(
            args,
            selector_date=selector_date,
        )
        argv = ["auctions", tenant.slug, "--date", auction_date]
        if args.command == "event":
            argv.extend(["--auction-id", selector])
        elif args.command == "parcel":
            argv.extend(["--parcel", selector])
        elif args.command == "address":
            argv.extend(["--address", selector])
        elif args.command == "search":
            field = (
                str(args.search_field or "case")
                .strip()
                .casefold()
                .replace("_", "-")
            )
            option = {
                "case": "--case-number",
                "case-number": "--case-number",
                "parcel": "--parcel",
                "parcel-id": "--parcel",
                "address": "--address",
            }.get(field)
            if option is None:
                raise ValueError(
                    "Ohio sheriff-sale --search-field must be case, parcel, "
                    "or address"
                )
            argv.extend([option, selector])
        elif args.command != "sale":
            raise ValueError(
                f"Ohio sheriff-sale components do not translate {args.command}"
            )
        stage = str(args.process_stage or "").strip().casefold()
        if stage and stage not in {"*", "all"}:
            for value in stage.split(","):
                normalized = value.strip().replace("-", "_")
                if normalized not in query_ohio_sheriff_sales.AREA_CODES:
                    raise ValueError(
                        "Ohio sheriff-sale --process-stage must be running, "
                        "waiting, or closed_or_canceled"
                    )
                argv.extend(["--area", normalized])
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    else:
        raise ValueError(
            f"Ohio sheriff-sale components do not translate {args.command}"
        )

    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_ohio_sheriff_sales.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            str(query_ohio_sheriff_sales.DEFAULT_MAX_RETRIES),
        ]
    )
    try:
        return query_ohio_sheriff_sales.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Ohio sheriff-sale selector for {adapter_command}"
        ) from error


def _one_licking_archive_year(
    args: argparse.Namespace,
    *,
    selector_year: str | None = None,
) -> int:
    """Resolve the single full-year array selected by the caller."""

    years: list[int] = []
    if args.tax_year is not None:
        years.append(int(args.tax_year))
    if selector_year:
        try:
            years.append(int(selector_year))
        except ValueError as error:
            raise ValueError(
                "Licking foreclosure sale selectors use a four-digit year"
            ) from error
    for value in (args.from_date, args.to_date):
        if value:
            try:
                normalized = query_ohio_sheriff_sales._parse_iso_date(value)
            except argparse.ArgumentTypeError as error:
                raise ValueError(str(error)) from error
            years.append(int(normalized[:4]))
    if not years:
        raise ValueError(
            "Licking foreclosure archive searches require --tax-year or "
            "a date bound"
        )
    if len(set(years)) > 1:
        raise ValueError(
            "Licking foreclosure archive selectors must resolve to one year"
        )
    try:
        return query_licking_foreclosure_archive._year_value(str(years[0]))
    except argparse.ArgumentTypeError as error:
        raise ValueError(str(error)) from error


def _licking_foreclosure_archive_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property operations to the county JSON archive."""

    _validate_fixed_ohio_county(
        args,
        county_geoid=query_licking_foreclosure_archive.COUNTY_GEOID,
        county_name="Licking County, Ohio",
        source_label="Licking County sheriff foreclosure archive",
    )
    selector = str(args.query or "").strip()
    if adapter_command == "source":
        if selector and selector.casefold() not in {"*", "all"}:
            raise ValueError("Licking archive discovery takes no selector")
        argv = ["source"]
    elif adapter_command == "years":
        if selector and selector.casefold() not in {"*", "all"}:
            raise ValueError("Licking archive releases take no selector")
        argv = ["years"]
    elif adapter_command == "case":
        argv = ["case", "--case-number", selector]
    elif adapter_command == "probe":
        argv = ["probe"]
        if selector:
            argv.extend(["--case-number", selector])
    elif adapter_command == "year":
        year = _one_licking_archive_year(
            args,
            selector_year=selector if args.command == "sale" else None,
        )
        argv = ["year", "--year", str(year)]
        if args.command == "parcel":
            argv.extend(["--parcel", selector])
        elif args.command == "address":
            argv.extend(["--address", selector])
        elif args.command == "search":
            field = (
                str(args.search_field or "case")
                .strip()
                .casefold()
                .replace("_", "-")
            )
            option = {
                "case": "--case-number",
                "case-number": "--case-number",
                "parcel": "--parcel",
                "parcel-id": "--parcel",
                "address": "--address",
                "status": "--status",
                "sale-type": "--sale-type",
                "purchaser": "--purchaser",
            }.get(field)
            if option is None:
                raise ValueError(
                    "Licking archive --search-field must be case, parcel, "
                    "address, status, sale-type, or purchaser"
                )
            argv.extend([option, selector])
        elif args.command != "sale":
            raise ValueError(
                f"Licking foreclosure archive does not translate "
                f"{args.command}"
            )
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    else:
        raise ValueError(
            f"Licking foreclosure archive does not translate {args.command}"
        )

    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_licking_foreclosure_archive.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            str(query_licking_foreclosure_archive.DEFAULT_MAX_RETRIES),
        ]
    )
    try:
        return query_licking_foreclosure_archive.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Licking foreclosure archive selector for "
            f"{adapter_command}"
        ) from error


def _ohio_licking_auditor_gis_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the Licking Auditor parcel layer."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", "39089"}:
        raise ValueError(
            "Licking County Auditor GIS serves county GEOID 39089"
        )
    county = str(args.county_fips or args.county_selector or "").strip()
    normalized_county = re.sub(
        r"[^a-z0-9]+", " ", county.casefold()
    ).strip()
    if county and normalized_county not in {
        "089",
        "39089",
        "licking",
        "licking county",
    }:
        raise ValueError(
            "Licking County Auditor GIS accepts county 089, GEOID 39089, "
            "or Licking County"
        )

    selector = str(args.query or "").strip()
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    command = adapter_command
    argv: list[str]

    if command == "search":
        field_aliases = {
            "": "owner",
            "auto": "owner",
            "owner": "owner",
            "parcel": "parcel",
            "parcel-id": "parcel",
            "address": "situs",
            "situs": "situs",
            "mailing": "mailing",
            "mailing-address": "mailing",
            "fid": "occurrence",
            "objectid": "occurrence",
            "legal": "legal-description",
            "legal-description": "legal-description",
            "land-use": "land-use",
            "instrument": "instrument",
        }
        try:
            command = field_aliases[requested_field]
        except KeyError as error:
            raise ValueError(
                "Licking property --search-field must be owner, parcel, "
                "address, mailing, fid, legal, land-use, or instrument"
            ) from error

    if command in {"source", "metadata", "probe"}:
        argv = [command]
    elif command == "occurrence":
        if not selector.isdigit() or int(selector) <= 0:
            raise ValueError(
                "Licking feature occurrence lookup requires a positive OBJECTID"
            )
        argv = ["occurrence", selector]
    elif command in {"legal-description", "land-use", "instrument"}:
        if not selector:
            raise ValueError(f"Licking {command} search requires a selector")
        argv = ["attribute", command, selector]
    elif command in {"parcel", "owner", "situs", "mailing"}:
        if not selector:
            raise ValueError(f"Licking {command} search requires a selector")
        argv = [command, selector]
    else:
        raise ValueError(
            f"Licking County Auditor GIS does not translate {args.command}"
        )

    if command not in {"source", "metadata", "probe"}:
        selected_limit = _selected_live_limit(args)
        if selected_limit is not None:
            argv.extend(["--limit", str(selected_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
        if args.geometry or args.command in {"map", "geometry"}:
            argv.append("--geometry")
    if command != "source":
        argv.extend(
            [
                "--page-size",
                str(args.page_size),
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else query_ohio_licking_property.DEFAULT_TIMEOUT
                ),
                "--minimum-interval",
                str(args.minimum_interval),
                "--retry-attempts",
                "3",
            ]
        )
    try:
        return query_ohio_licking_property.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Licking Auditor GIS selector for {adapter_command}"
        ) from error


def _ohio_statewide_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to the OGRIP statewide parcel view."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    county_from_jurisdiction = ""
    if jurisdiction not in {"", "39", "OH", "US-OH"}:
        if (
            len(jurisdiction) == 5
            and jurisdiction.isdigit()
            and jurisdiction.startswith("39")
        ):
            county_from_jurisdiction = jurisdiction
        else:
            raise ValueError(
                "Ohio statewide parcels accept state context 39/OH/US-OH "
                "or an Ohio county GEOID"
            )

    raw_counties = [
        str(value).strip()
        for value in (
            county_from_jurisdiction,
            args.county_fips,
            args.county_selector,
        )
        if value not in (None, "")
    ]
    normalized_counties: list[tuple[str | None, str | None, str]] = []
    for raw_county in raw_counties:
        candidate = (
            f"39{raw_county}"
            if raw_county.isdigit() and len(raw_county) == 3
            else raw_county
        )
        county_name, county_geoid = (
            query_ohio_statewide_parcels._county_selection(candidate)
        )
        normalized_counties.append((county_name, county_geoid, candidate))
    county_keys = {
        geoid or str(name or raw).casefold()
        for name, geoid, raw in normalized_counties
    }
    if len(county_keys) > 1:
        raise ValueError(
            "Ohio county selectors conflict across --jurisdiction, "
            "--county-fips, and --county"
        )
    county = normalized_counties[0][2] if normalized_counties else ""

    selector = str(args.query or "").strip()
    requested_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    command = adapter_command
    argv: list[str]

    if command == "search":
        field_aliases = {
            "": "any",
            "auto": "any",
            "any": "any",
            "parcel": "parcel",
            "parcel-id": "parcel",
            "state-parcel-id": "parcel",
            "local-parcel-id": "parcel",
            "address": "address",
            "situs": "address",
            "situs-address": "address",
            "mailing": "mailing",
            "mailing-address": "mailing",
            "land-use": "land-use",
            "state-land-use": "land-use",
            "state-luc": "land-use",
        }
        try:
            field = field_aliases[requested_field]
        except KeyError as error:
            raise ValueError(
                "Ohio parcel --search-field must be any, parcel, address, "
                "mailing, or land-use"
            ) from error
        argv = ["search", selector, "--field", field]
    elif command == "land-use":
        if requested_field not in {"", "auto", "any", "land-use", "state-luc"}:
            raise ValueError(
                "Ohio land-use search does not use "
                f"--search-field {requested_field}"
            )
        argv = ["search", selector, "--field", "land-use"]
    elif command in {"address", "parcel"}:
        allowed_fields = {
            "address": {"", "auto", "any", "address", "situs", "situs-address"},
            "parcel": {
                "",
                "auto",
                "any",
                "parcel",
                "parcel-id",
                "state-parcel-id",
                "local-parcel-id",
            },
        }[command]
        if requested_field not in allowed_fields:
            raise ValueError(
                f"Ohio {command} lookup does not use "
                f"--search-field {requested_field}"
            )
        argv = [command, selector]
    elif command == "count":
        if selector.casefold() not in {"*", "all", "statewide", "ohio"}:
            if county:
                selected_name, selected_geoid = (
                    query_ohio_statewide_parcels._county_selection(selector)
                )
                context_name, context_geoid = (
                    query_ohio_statewide_parcels._county_selection(county)
                )
                if (
                    selected_geoid or str(selected_name).casefold()
                ) != (
                    context_geoid or str(context_name).casefold()
                ):
                    raise ValueError(
                        "Ohio count selector conflicts with the county context"
                    )
            else:
                county = selector
        argv = ["count"]
    elif command == "source":
        argv = ["source"]
    elif command == "metadata":
        argv = ["metadata"]
    elif command == "probe":
        argv = ["probe"]
    else:
        raise ValueError(
            f"Ohio statewide parcels do not translate {args.command}"
        )

    if county and command in {
        "search",
        "land-use",
        "address",
        "parcel",
        "count",
    }:
        argv.extend(["--county", county])

    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and command in {
        "search",
        "land-use",
        "address",
        "parcel",
    }:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor and command in {
        "search",
        "land-use",
        "address",
        "parcel",
    }:
        argv.extend(["--cursor", args.cursor])
    if command in {"search", "land-use", "address", "parcel"} and (
        args.geometry or args.command == "map"
    ):
        argv.append("--geometry")

    if command != "source":
        argv.extend(
            [
                "--page-size",
                str(args.page_size),
                "--timeout",
                str(
                    args.timeout
                    if args.timeout is not None
                    else query_ohio_statewide_parcels.DEFAULT_TIMEOUT
                ),
                "--minimum-interval",
                str(args.minimum_interval),
                "--retry-attempts",
                "3",
            ]
        )
    try:
        return query_ohio_statewide_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Ohio statewide parcel selector for {adapter_command}"
        ) from error


def _new_jersey_county_selector(args: argparse.Namespace) -> str | None:
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "34", "NJ", "US-NJ"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("34")
    ):
        raise ValueError(
            "New Jersey statewide parcels accept state context 34/NJ or a "
            "New Jersey county GEOID"
        )
    county = str(args.county_fips or "").strip()
    if not county and len(jurisdiction) == 5 and jurisdiction.isdigit():
        county = jurisdiction
    if county.isdigit() and len(county) == 3:
        county = f"34{county}"
    if county.isdigit() and len(county) == 5:
        matches = [
            code
            for code, (_name, geoid) in query_new_jersey_parcels.COUNTIES.items()
            if geoid == county
        ]
        if not matches:
            raise ValueError(f"unknown New Jersey county GEOID {county}")
        return matches[0]
    return county or None


def _new_jersey_dca_county_selector(
    args: argparse.Namespace,
    *,
    required: bool,
) -> str | None:
    """Resolve shared New Jersey geography to a current DCA county name."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "34", "NJ", "US-NJ"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("34")
    ):
        raise ValueError(
            "New Jersey DCA property registrations cover New Jersey "
            "(34/NJ/US-NJ) and its county GEOIDs"
        )

    county = str(args.county_fips or "").strip()
    if not county and len(jurisdiction) == 5 and jurisdiction.isdigit():
        county = jurisdiction
    if not county:
        if required:
            raise ValueError(
                "New Jersey DCA block/lot searches require --county-fips "
                "or a county GEOID in --jurisdiction"
            )
        return None

    if county.isdigit() and len(county) == 3:
        county = f"34{county}"
    if county.isdigit():
        if len(county) != 5 or not county.startswith("34"):
            raise ValueError(f"invalid New Jersey county GEOID {county}")
        matches = [
            name
            for name, county_geoid in (
                query_new_jersey_dca_property.COUNTY_FIPS_BY_NAME.items()
            )
            if county_geoid == county
        ]
        if not matches:
            raise ValueError(f"unknown New Jersey county GEOID {county}")
        return matches[0]

    normalized = re.sub(r"[^A-Z0-9]+", " ", county.upper()).strip()
    if normalized.endswith(" COUNTY"):
        normalized = normalized[: -len(" COUNTY")].strip()
    if normalized not in query_new_jersey_dca_property.COUNTY_FIPS_BY_NAME:
        raise ValueError(f"unknown New Jersey county {county!r}")
    return normalized


def _new_jersey_dca_property_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to one verified DCA search branch."""

    selector = str(args.query or "").strip()
    requested_field = str(args.search_field or "").strip().casefold()
    command = adapter_command
    argv: list[str]

    def require_statewide_scope(branch: str) -> None:
        county = _new_jersey_dca_county_selector(args, required=False)
        if county:
            raise ValueError(
                f"New Jersey DCA {branch} does not apply a county filter; "
                "use state scope or the source's supported county/block/lot "
                "branch"
            )

    if command == "probe":
        require_statewide_scope("probe")
        argv = ["probe"]
    else:
        field = requested_field
        if command == "search" and field in {"", "any", "auto"}:
            field = (
                "registration"
                if selector
                and all(
                    character.isdigit() or character == "-" for character in selector
                )
                else "address"
            )
        elif command == "registration":
            field = "registration"
        elif command == "address":
            field = "address"
        elif command == "parcel" and not field:
            field = "block-lot"

        if field in {
            "registration",
            "property-registration",
            "building-registration",
            "account",
        }:
            require_statewide_scope("registration search")
            argv = ["registration", selector]
        elif field in {"address", "street", "situs"}:
            require_statewide_scope("address search")
            argv = ["address", selector]
        elif field in {"municipality", "municipality-name"}:
            require_statewide_scope("municipality search")
            argv = ["search", "--municipality", selector]
        elif field in {"county", "county-name"}:
            county = _new_jersey_dca_county_selector(args, required=False)
            selector_args = argparse.Namespace(
                jurisdiction="",
                county_fips=selector,
            )
            selector_county = _new_jersey_dca_county_selector(
                selector_args,
                required=True,
            )
            if county and county != selector_county:
                raise ValueError(
                    "DCA county query conflicts with --county-fips or the "
                    "county GEOID in --jurisdiction"
                )
            argv = ["parcel", "--county", str(county or selector_county)]
        elif field in {"parcel", "block-lot", "block", "lot"}:
            county = _new_jersey_dca_county_selector(args, required=True)
            block: str | None = None
            lot: str | None = None
            if field == "block":
                block = selector
            elif field == "lot":
                lot = selector
            else:
                components = [
                    value.strip()
                    for value in re.split(r"[/|,:]+", selector)
                    if value.strip()
                ]
                if len(components) != 2:
                    raise ValueError("New Jersey DCA parcel selectors use BLOCK/LOT")
                block, lot = components
            argv = ["parcel", "--county", str(county)]
            if block:
                argv.extend(["--block", block])
            if lot:
                argv.extend(["--lot", lot])
        else:
            raise ValueError(
                "New Jersey DCA --search-field must be auto, registration, "
                "address, municipality, county, block-lot, block, or lot"
            )

    if args.limit_explicit and command != "probe":
        argv.extend(["--limit", str(args.limit)])
    if args.max_records is not None and command != "probe":
        argv.extend(["--max-records", str(args.max_records)])
    if args.cursor and command != "probe":
        argv.extend(["--cursor", args.cursor])
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_new_jersey_dca_property.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            str(query_new_jersey_dca_property.DEFAULT_RETRY_ATTEMPTS),
        ]
    )
    try:
        return query_new_jersey_dca_property.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid New Jersey DCA selector for {adapter_command}"
        ) from error


def _new_jersey_statewide_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to NJGIN's parcel/MOD-IV composite."""

    county = _new_jersey_county_selector(args)
    selector = str(args.query or "").strip()
    requested_field = str(args.search_field or "").strip().casefold()
    command = adapter_command
    if command == "search":
        field = requested_field or "address"
        if field in {"pin", "parcel", "parcel-id"}:
            command = "pin"
        elif field in {"address", "situs", "mailing"}:
            command = "address"
        else:
            raise ValueError("New Jersey parcel --search-field must be address or pin")

    if command in {"point", "bbox"}:
        coordinate_count = 2 if command == "point" else 4
        argv = [
            command,
            *_washington_parcel_coordinates(
                selector,
                count=coordinate_count,
                operation=command,
            ),
        ]
    elif command == "count":
        argv = ["count"]
        if selector.casefold() not in {"*", "all"}:
            option_by_field = {
                "address": "--address",
                "pin": "--pin",
                "parcel": "--pin",
                "parcel-id": "--pin",
                "municipality": "--municipality",
                "municipality-code": "--municipality-code",
                "block": "--block",
                "lot": "--lot",
                "property-class": "--property-class",
                "property-use": "--property-use",
                "deed-book": "--deed-book",
                "deed-page": "--deed-page",
            }
            if requested_field not in option_by_field:
                raise ValueError(
                    "New Jersey parcel count requires '*' or --search-field "
                    "address, pin, municipality, municipality-code, block, "
                    "lot, property-class, property-use, deed-book, or deed-page"
                )
            argv.extend([option_by_field[requested_field], selector])
    elif command == "probe":
        argv = ["probe"]
    elif command in {"address", "pin"}:
        argv = [command, selector]
    else:
        raise ValueError(
            f"New Jersey statewide parcels do not translate {args.command}"
        )

    if county and command not in {"pin", "probe"}:
        argv.extend(["--county", county])
    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and command not in {"count", "probe"}:
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor and command not in {"count", "probe"}:
        argv.extend(["--cursor", args.cursor])
    if command not in {"count", "probe"} and (args.geometry or args.command == "map"):
        argv.append("--geometry")
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_new_jersey_parcels.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_new_jersey_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid New Jersey parcel selector for {adapter_command}"
        ) from error


def _new_york_statewide_parcel_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to New York's three parcel components."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "36", "NY"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("36")
    ):
        raise ValueError(
            "New York statewide parcels accept state context 36/NY or a "
            "New York county GEOID"
        )
    county = str(args.county_fips or "").strip()
    if not county and len(jurisdiction) == 5:
        county = jurisdiction

    selector = str(args.query or "").strip()
    requested_field = str(args.search_field or "").strip().casefold()
    command = adapter_command
    if command == "search":
        field = requested_field or "any"
        command_by_field = {
            "any": "search",
            "search": "search",
            "owner": "owner",
            "name": "owner",
            "address": "address",
            "situs": "address",
            "mailing": "mailing",
            "parcel": "parcel",
            "pin": "parcel",
            "parcel-id": "parcel",
            "agency": "agency",
            "state-agency": "agency",
            "objectid": "objectid",
        }
        try:
            command = command_by_field[field]
        except KeyError as error:
            raise ValueError(
                "New York parcel --search-field must be any, owner, address, "
                "mailing, parcel, agency, or objectid"
            ) from error
    elif command == "address" and requested_field == "mailing":
        command = "mailing"

    collection = "centroids"
    if command == "agency":
        collection = "state-owned"
    elif args.command in {"map", "point"}:
        collection = "public-parcels"

    if command == "point":
        argv = [
            "point",
            *_washington_parcel_coordinates(
                selector,
                count=2,
                operation="point",
            ),
        ]
    elif command == "deed":
        parts = [
            value.strip() for value in re.split(r"[/|,:\s]+", selector) if value.strip()
        ]
        if len(parts) != 2 or any(not value.isdigit() for value in parts):
            raise ValueError("New York parcel instrument requires book/page")
        argv = ["deed", parts[0], parts[1]]
    elif command == "probe":
        argv = ["probe"]
    else:
        argv = [command, selector]

    argv.extend(["--collection", collection])
    if command == "parcel":
        argv.extend(["--id-type", "auto"])
    if county:
        argv.extend(["--county", county])
    if args.tax_year is not None:
        argv.extend(["--roll-year", str(args.tax_year)])
    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and command != "probe":
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor and command != "probe":
        argv.extend(["--cursor", args.cursor])
    if args.geometry or args.command in {"map", "point"}:
        argv.append("--geometry")
    argv.extend(
        [
            "--page-size",
            str(args.page_size),
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_ny_statewide_parcels.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_ny_statewide_parcels.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid New York parcel selector for {adapter_command}"
        ) from error


def _new_york_salesweb_county(args: argparse.Namespace) -> str | None:
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "36", "NY"} and not (
        len(jurisdiction) == 5
        and jurisdiction.isdigit()
        and jurisdiction.startswith("36")
    ):
        raise ValueError(
            "New York SalesWeb accepts state context 36/NY or a New York county GEOID"
        )
    county = str(args.county_fips or "").strip()
    if not county and len(jurisdiction) == 5:
        county = jurisdiction
    if county.isdigit() and len(county) == 3:
        county = f"36{county}"
    if county.isdigit() and len(county) == 5:
        matches = [
            name
            for name, geoid in query_ny_salesweb.COUNTY_GEOID_BY_NAME.items()
            if geoid == county
        ]
        if not matches:
            raise ValueError(f"unknown New York county GEOID {county}")
        return matches[0]
    return county or None


def _new_york_salesweb_address(selector: str) -> list[str]:
    match = re.match(r"^\s*([0-9A-Za-z-]+)\s+(.+?)\s*$", selector)
    if match is None:
        return ["--street", selector]
    return [
        "--address-number",
        match.group(1),
        "--street",
        match.group(2),
    ]


def _new_york_salesweb_book_page(selector: str) -> list[str]:
    parts = [
        value.strip() for value in re.split(r"[/|,:\s]+", selector) if value.strip()
    ]
    if len(parts) != 2:
        raise ValueError("New York SalesWeb instrument requires book/page")
    return ["--book", parts[0], "--page", parts[1]]


def _new_york_salesweb_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property selectors to ORPTS SalesWeb criteria."""

    selector = str(args.query or "").strip()
    requested_field = str(args.search_field or "").strip().casefold()
    county = _new_york_salesweb_county(args)
    command = adapter_command
    criteria: list[str] = []

    if command == "probe":
        argv = ["probe"]
    else:
        default_field = {
            "owner": "buyer",
            "address": "address",
            "parcel": "tax-map",
            "instrument": "book-page",
            "sale": "sale-id" if selector.isdigit() else "buyer",
            "search": "buyer",
        }.get(args.command, "buyer")
        field = requested_field or default_field
        if field in {"sale-id", "sale-transaction", "transaction"}:
            if not selector.isdigit():
                raise ValueError(
                    "New York SalesWeb sale transaction ID must be numeric"
                )
            argv = ["detail", selector]
            command = "detail"
        else:
            argv = ["search"]
            if field in {"buyer", "grantee"}:
                criteria.extend(["--buyer", selector])
            elif field in {"seller", "grantor"}:
                criteria.extend(["--seller", selector])
            elif field in {"address", "street", "situs"}:
                criteria.extend(_new_york_salesweb_address(selector))
            elif field in {"parcel", "parcel-id", "tax-map"}:
                criteria.extend(["--tax-map", selector])
            elif field in {"book-page", "deed", "instrument"}:
                criteria.extend(_new_york_salesweb_book_page(selector))
            else:
                raise ValueError(
                    "New York SalesWeb --search-field must be buyer, seller, "
                    "address, tax-map, book-page, or sale-id"
                )
            if county:
                criteria.extend(["--county", county])
            if args.tax_year is not None:
                criteria.extend(
                    [
                        "--sale-from",
                        f"{args.tax_year:04d}-01-01",
                        "--sale-to",
                        f"{args.tax_year:04d}-12-31",
                    ]
                )
            selected_limit = _selected_live_limit(args)
            if selected_limit is None:
                selected_limit = args.limit
            criteria.extend(["--limit", str(selected_limit)])
            if args.cursor:
                criteria.extend(["--cursor", args.cursor])
            criteria.extend(["--page-size", str(args.page_size)])
            argv.extend(criteria)

    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_ny_salesweb.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_ny_salesweb.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid New York SalesWeb selector for {adapter_command}"
        ) from error


def _new_jersey_sr1a_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared property selectors to the statewide SR1A releases."""

    county = _new_jersey_county_selector(args)
    selector = str(args.query or "").strip()
    requested_field = str(args.search_field or "").strip().casefold()
    allowed_fields = {
        "any",
        "grantor",
        "grantee",
        "party",
        "property-address",
        "deed",
        "block-lot",
    }
    if adapter_command == "probe":
        argv = ["probe"]
    else:
        field = {
            "party": "party",
            "property-address": "property-address",
            "deed": "deed",
            "block-lot": "block-lot",
        }.get(adapter_command, requested_field or "any")
        if field not in allowed_fields:
            raise ValueError(
                "New Jersey SR1A --search-field must be any, grantor, "
                "grantee, party, property-address, deed, or block-lot"
            )
        structured_filters: list[str] = []
        positional_query = selector
        if adapter_command == "deed":
            parts = [
                value.strip() for value in re.split(r"[/|]", selector) if value.strip()
            ]
            if len(parts) == 2:
                positional_query = ""
                structured_filters.extend(
                    ["--deed-book", parts[0], "--deed-page", parts[1]]
                )
        elif adapter_command == "block-lot":
            parts = [
                value.strip()
                for value in re.split(r"[/_:|]", selector)
                if value.strip()
            ]
            if len(parts) in {3, 4} and re.fullmatch(r"\d{4}", parts[0]):
                positional_query = parts[3] if len(parts) == 4 else ""
                structured_filters.extend(
                    [
                        "--municipality-code",
                        parts[0],
                        "--block",
                        parts[1],
                        "--lot",
                        parts[2],
                    ]
                )
        argv = ["search"]
        if positional_query:
            argv.append(positional_query)
        argv.extend(["--field", field, *structured_filters])

    if county and adapter_command != "probe":
        argv.extend(["--county", county])
    if args.tax_year is not None:
        argv.extend(["--year", str(args.tax_year)])
    selected_limit = _selected_live_limit(args)
    if selected_limit is not None and adapter_command != "probe":
        argv.extend(["--limit", str(selected_limit)])
    if args.cursor and adapter_command != "probe":
        argv.extend(["--cursor", args.cursor])
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_new_jersey_sr1a.DEFAULT_TIMEOUT
            ),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_new_jersey_sr1a.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid New Jersey SR1A selector for {adapter_command}"
        ) from error


def _palm_beach_recorder_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate only deterministic Clerk instrument and book/page routes."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "12", "FL", "12099"}:
        raise ValueError(
            "Palm Beach Official Records use Florida GEOID 12 or "
            "Palm Beach County GEOID 12099"
        )
    if adapter_command == "probe":
        argv = ["probe"]
    else:
        selector = str(args.query or "").strip()
        search_field = str(args.search_field or "").strip().casefold()
        if search_field not in {
            "",
            "any",
            "instrument",
            "instrument-number",
            "book-page",
        }:
            raise ValueError(
                "Palm Beach Official Records --search-field must be "
                "instrument-number or book-page"
            )
        book_page = re.fullmatch(r"(\d+)\s*/\s*(\d+)", selector)
        if search_field == "book-page" and book_page is None:
            raise ValueError("Palm Beach book/page selectors must use BOOK/PAGE")
        if book_page is not None:
            argv = ["book-page", book_page.group(1), book_page.group(2)]
        elif re.fullmatch(r"\d+", selector):
            argv = ["instrument", selector]
        else:
            raise ValueError(
                "Palm Beach Official Records shared queries require an exact "
                "numeric instrument number or BOOK/PAGE selector"
            )
    argv.extend(
        [
            "--timeout",
            str(
                args.timeout
                if args.timeout is not None
                else query_palm_beach_official_records.DEFAULT_TIMEOUT
            ),
            "--minimum-interval",
            str(args.minimum_interval),
        ]
    )
    try:
        return query_palm_beach_official_records.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Palm Beach Official Records selector for {adapter_command}"
        ) from error


def _broward_recorder_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to Broward's browser-session index."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    county = str(args.county_fips or "").strip().upper()
    if jurisdiction not in {"", "12", "FL", "12011"}:
        raise ValueError(
            "Broward Official Records use Florida GEOID 12 or "
            "Broward County GEOID 12011"
        )
    if county not in {"", "011", "12011", "BROWARD"}:
        raise ValueError("Broward Official Records use county code 011 or GEOID 12011")

    if adapter_command == "probe":
        argv = ["probe"]
    else:
        selector = str(args.query or "").strip()
        search_field = (
            str(args.search_field or "")
            .strip()
            .casefold()
            .replace(
                "_",
                "-",
            )
        )
        if adapter_command == "name":
            allowed = {"", "any", "name", "party", "grantor", "grantee"}
            if search_field not in allowed:
                raise ValueError(
                    "Broward party search --search-field must be name, party, "
                    "grantor, or grantee"
                )
            direction = (
                search_field if search_field in {"grantor", "grantee"} else "all"
            )
            argv = [
                "name",
                selector,
                "--direction",
                direction,
                "--max-pages",
                "10",
            ]
        elif adapter_command == "parcel":
            if search_field not in {
                "",
                "any",
                "parcel",
                "parcel-id",
                "pcn",
            }:
                raise ValueError(
                    "Broward parcel --search-field must be parcel, parcel-id, or pcn"
                )
            argv = ["parcel", selector, "--max-pages", "10"]
        elif adapter_command == "detail":
            if search_field not in {
                "",
                "any",
                "instrument",
                "instrument-number",
            }:
                raise ValueError(
                    "Broward instrument --search-field must be instrument or "
                    "instrument-number"
                )
            if not re.fullmatch(r"\d+", selector):
                raise ValueError(
                    "Broward instrument lookup requires a numeric instrument number"
                )
            argv = ["detail", selector]
        else:
            raise ValueError(
                f"Broward Official Records do not translate {adapter_command}"
            )

        selected_limit = _selected_live_limit(args)
        if selected_limit is not None and adapter_command in {"name", "parcel"}:
            argv.extend(["--limit", str(selected_limit)])

    argv.extend(
        [
            "--timeout",
            str(args.timeout if args.timeout is not None else 300),
        ]
    )
    try:
        return query_broward_official_records.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Broward Official Records selector for {adapter_command}"
        ) from error


LIVE_ROUTES: dict[str, dict[str, _LiveRoute]] = {
    LOS_ANGELES_ASSESSOR_SOURCE_ID: {
        operation: _LiveRoute(
            LOS_ANGELES_TTC_ADAPTER,
            "route",
            _los_angeles_ttc_args,
        )
        for operation in ("account", "parcel", "map")
    },
    LOS_ANGELES_TTC_PAYMENT_SOURCE_ID: {
        operation: _LiveRoute(
            LOS_ANGELES_TTC_ADAPTER,
            "history",
            _los_angeles_ttc_args,
        )
        for operation in ("account", "parcel")
    },
    LOS_ANGELES_TTC_SALE_SOURCE_ID: {
        "sale": _LiveRoute(
            LOS_ANGELES_TTC_ADAPTER,
            "sale-results",
            _los_angeles_ttc_args,
        ),
        "event": _LiveRoute(
            LOS_ANGELES_TTC_ADAPTER,
            "auctions",
            _los_angeles_ttc_args,
        ),
        "search": _LiveRoute(
            LOS_ANGELES_TTC_ADAPTER,
            "publications",
            _los_angeles_ttc_args,
        ),
        "probe": _LiveRoute(
            LOS_ANGELES_TTC_ADAPTER,
            "probe",
            _los_angeles_ttc_args,
        ),
    },
    PHILADELPHIA_OPA_SOURCE_ID: {
        "search": _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "search",
            _philadelphia_property_args,
        ),
        "owner": _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "owner",
            _philadelphia_property_args,
        ),
        "address": _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "address",
            _philadelphia_property_args,
        ),
        "account": _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "parcel",
            _philadelphia_property_args,
        ),
        "parcel": _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "parcel",
            _philadelphia_property_args,
        ),
        "instrument": _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "registry",
            _philadelphia_property_args,
        ),
        "map": _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "parcel",
            _philadelphia_property_args,
        ),
        "probe": _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "probe",
            _philadelphia_property_args,
        ),
    },
    PHILADELPHIA_HISTORY_SOURCE_ID: {
        operation: _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "history",
            _philadelphia_property_args,
        )
        for operation in ("search", "account", "parcel")
    },
    PHILADELPHIA_DOR_SOURCE_ID: {
        operation: _LiveRoute(
            PHILADELPHIA_PROPERTY_ADAPTER,
            "parcel-shape",
            _philadelphia_property_args,
        )
        for operation in (
            "search",
            "address",
            "parcel",
            "instrument",
            "map",
        )
    },
    MICHIGAN_PROPERTY_DIRECTORY_SOURCE_ID: {
        "search": _LiveRoute(
            MICHIGAN_PROPERTY_DIRECTORY_ADAPTER,
            "search",
            _michigan_property_directory_args,
        ),
        "discovery": _LiveRoute(
            MICHIGAN_PROPERTY_DIRECTORY_ADAPTER,
            "discovery",
            _michigan_property_directory_args,
        ),
        "probe": _LiveRoute(
            MICHIGAN_PROPERTY_DIRECTORY_ADAPTER,
            "probe",
            _michigan_property_directory_args,
        ),
    },
    MICHIGAN_EATON_PARCELS_SOURCE_ID: {
        operation: _LiveRoute(
            MICHIGAN_EATON_PARCELS_ADAPTER,
            "search",
            _michigan_eaton_parcel_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "account",
            "parcel",
            "map",
        )
    }
    | {
        "freshness": _LiveRoute(
            MICHIGAN_EATON_PARCELS_ADAPTER,
            "metadata",
            _michigan_eaton_parcel_args,
        ),
        "probe": _LiveRoute(
            MICHIGAN_EATON_PARCELS_ADAPTER,
            "probe",
            _michigan_eaton_parcel_args,
        ),
    },
    FL_SOURCE_ID: {
        "releases": _LiveRoute(
            FL_DOR_PROPERTY_ADAPTER,
            "list",
            _fl_dor_property_args,
        ),
        "manifest": _LiveRoute(
            FL_DOR_PROPERTY_ADAPTER,
            "manifest",
            _fl_dor_property_args,
        ),
        "download": _LiveRoute(
            FL_DOR_PROPERTY_ADAPTER,
            "download",
            _fl_dor_property_args,
        ),
        "discovery": _LiveRoute(
            FL_DOR_PROPERTY_ADAPTER,
            "list",
            _fl_dor_property_args,
        ),
        "probe": _LiveRoute(
            FL_DOR_PROPERTY_ADAPTER,
            "probe",
            _fl_dor_property_args,
        ),
    },
    HARRIS_SOURCE_ID: {
        "releases": _LiveRoute(
            HARRIS_PROPERTY_ADAPTER,
            "list",
            _hcad_property_args,
        ),
        "manifest": _LiveRoute(
            HARRIS_PROPERTY_ADAPTER,
            "manifest",
            _hcad_property_args,
        ),
        "download": _LiveRoute(
            HARRIS_PROPERTY_ADAPTER,
            "download",
            _hcad_property_args,
        ),
        "discovery": _LiveRoute(
            HARRIS_PROPERTY_ADAPTER,
            "list",
            _hcad_property_args,
        ),
        "probe": _LiveRoute(
            HARRIS_PROPERTY_ADAPTER,
            "probe",
            _hcad_property_args,
        ),
    },
    HCAD_GIS_SOURCE_ID: {
        "releases": _LiveRoute(
            HCAD_GIS_ADAPTER,
            "releases",
            _hcad_gis_args,
        ),
        "discovery": _LiveRoute(
            HCAD_GIS_ADAPTER,
            "releases",
            _hcad_gis_args,
        ),
        "manifest": _LiveRoute(
            HCAD_GIS_ADAPTER,
            "manifest",
            _hcad_gis_args,
        ),
        "probe": _LiveRoute(
            HCAD_GIS_ADAPTER,
            "probe",
            _hcad_gis_args,
        ),
        "download": _LiveRoute(
            HCAD_GIS_ADAPTER,
            "download",
            _hcad_gis_args,
        ),
        "search": _LiveRoute(
            HCAD_GIS_ADAPTER,
            "search",
            _hcad_gis_args,
        ),
        "owner": _LiveRoute(
            HCAD_GIS_ADAPTER,
            "search",
            _hcad_gis_args,
        ),
        "address": _LiveRoute(
            HCAD_GIS_ADAPTER,
            "search",
            _hcad_gis_args,
        ),
        **{
            operation: _LiveRoute(
                HCAD_GIS_ADAPTER,
                "account",
                _hcad_gis_args,
            )
            for operation in ("account", "parcel", "map")
        },
    },
    TXGIO_LAND_PARCELS_SOURCE_ID: {
        "releases": _LiveRoute(
            TXGIO_LAND_PARCELS_ADAPTER,
            "releases",
            _txgio_land_parcel_args,
        ),
        "discovery": _LiveRoute(
            TXGIO_LAND_PARCELS_ADAPTER,
            "releases",
            _txgio_land_parcel_args,
        ),
        "manifest": _LiveRoute(
            TXGIO_LAND_PARCELS_ADAPTER,
            "manifest",
            _txgio_land_parcel_args,
        ),
        "probe": _LiveRoute(
            TXGIO_LAND_PARCELS_ADAPTER,
            "probe",
            _txgio_land_parcel_args,
        ),
        "download": _LiveRoute(
            TXGIO_LAND_PARCELS_ADAPTER,
            "download",
            _txgio_land_parcel_args,
        ),
        **{
            operation: _LiveRoute(
                TXGIO_LAND_PARCELS_ADAPTER,
                "search",
                _txgio_land_parcel_args,
            )
            for operation in ("search", "owner", "address", "parcel", "map")
        },
    },
    MONTANA_CADASTRAL_SOURCE_ID: {
        operation: _LiveRoute(
            MONTANA_CADASTRAL_ADAPTER,
            operation,
            _montana_cadastral_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "parcel",
            "account",
            "map",
            "point",
            "count",
            "releases",
            "manifest",
            "download",
            "discovery",
            "probe",
        )
    },
    GEORGIA_PROPERTY_DIRECTORY_SOURCE_ID: {
        operation: _LiveRoute(
            GEORGIA_PROPERTY_SOURCES_ADAPTER,
            "directory",
            _georgia_property_source_args,
        )
        for operation in ("search", "discovery")
    }
    | {
        "probe": _LiveRoute(
            GEORGIA_PROPERTY_SOURCES_ADAPTER,
            "probe",
            _georgia_property_source_args,
        ),
    },
    GEORGIA_GSCCCA_SOURCE_ID: {
        "discovery": _LiveRoute(
            GEORGIA_PROPERTY_SOURCES_ADAPTER,
            "handoff",
            _georgia_property_source_args,
        ),
        "probe": _LiveRoute(
            GEORGIA_PROPERTY_SOURCES_ADAPTER,
            "probe",
            _georgia_property_source_args,
        ),
    },
    VIRGINIA_BEACH_DELINQUENT_TAX_SOURCE_ID: {
        "search": _LiveRoute(
            query_va_beach_delinquent_tax,
            "search",
            _virginia_beach_delinquent_tax_args,
        ),
        "owner": _LiveRoute(
            query_va_beach_delinquent_tax,
            "owner",
            _virginia_beach_delinquent_tax_args,
        ),
        "address": _LiveRoute(
            query_va_beach_delinquent_tax,
            "address",
            _virginia_beach_delinquent_tax_args,
        ),
        "parcel": _LiveRoute(
            query_va_beach_delinquent_tax,
            "parcel",
            _virginia_beach_delinquent_tax_args,
        ),
        "event": _LiveRoute(
            query_va_beach_delinquent_tax,
            "bill",
            _virginia_beach_delinquent_tax_args,
        ),
        "discovery": _LiveRoute(
            query_va_beach_delinquent_tax,
            "routes",
            _virginia_beach_delinquent_tax_args,
        ),
        "probe": _LiveRoute(
            query_va_beach_delinquent_tax,
            "probe",
            _virginia_beach_delinquent_tax_args,
        ),
    },
    VIRGINIA_VGIN_PARCELS_SOURCE_ID: {
        "search": _LiveRoute(
            VIRGINIA_VGIN_PARCELS_ADAPTER,
            "search",
            _virginia_vgin_parcel_args,
        ),
        "parcel": _LiveRoute(
            VIRGINIA_VGIN_PARCELS_ADAPTER,
            "parcel",
            _virginia_vgin_parcel_args,
        ),
        "map": _LiveRoute(
            VIRGINIA_VGIN_PARCELS_ADAPTER,
            "parcel",
            _virginia_vgin_parcel_args,
        ),
        "count": _LiveRoute(
            VIRGINIA_VGIN_PARCELS_ADAPTER,
            "count",
            _virginia_vgin_parcel_args,
        ),
        "point": _LiveRoute(
            VIRGINIA_VGIN_PARCELS_ADAPTER,
            "point",
            _virginia_vgin_parcel_args,
        ),
        "bbox": _LiveRoute(
            VIRGINIA_VGIN_PARCELS_ADAPTER,
            "bbox",
            _virginia_vgin_parcel_args,
        ),
        "freshness": _LiveRoute(
            VIRGINIA_VGIN_PARCELS_ADAPTER,
            "localities",
            _virginia_vgin_parcel_args,
        ),
        "probe": _LiveRoute(
            VIRGINIA_VGIN_PARCELS_ADAPTER,
            "probe",
            _virginia_vgin_parcel_args,
        ),
    },
    WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID: {
        "search": _LiveRoute(
            WISCONSIN_STATEWIDE_PARCELS_ADAPTER,
            "search",
            _wisconsin_statewide_parcel_args,
        ),
        "owner": _LiveRoute(
            WISCONSIN_STATEWIDE_PARCELS_ADAPTER,
            "owner",
            _wisconsin_statewide_parcel_args,
        ),
        "address": _LiveRoute(
            WISCONSIN_STATEWIDE_PARCELS_ADAPTER,
            "address",
            _wisconsin_statewide_parcel_args,
        ),
        "parcel": _LiveRoute(
            WISCONSIN_STATEWIDE_PARCELS_ADAPTER,
            "parcel",
            _wisconsin_statewide_parcel_args,
        ),
        "map": _LiveRoute(
            WISCONSIN_STATEWIDE_PARCELS_ADAPTER,
            "parcel",
            _wisconsin_statewide_parcel_args,
        ),
        "probe": _LiveRoute(
            WISCONSIN_STATEWIDE_PARCELS_ADAPTER,
            "probe",
            _wisconsin_statewide_parcel_args,
        ),
    },
    WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID: {
        operation: _LiveRoute(
            WYOMING_DOR_STATEWIDE_PARCELS_ADAPTER,
            adapter_command,
            _wyoming_dor_statewide_parcel_args,
        )
        for operation, adapter_command in {
            "search": "search",
            "owner": "owner",
            "parcel": "parcel",
            "account": "account",
            "county": "county",
            "jurisdiction": "jurisdiction",
            "address": "situs",
            "situs": "situs",
            "mailing": "mailing",
            "legal": "legal",
            "fid": "fid",
            "map": "parcel",
            "geometry": "geometry",
            "point": "point",
            "bbox": "bbox",
            "discovery": "discovery",
            "probe": "probe",
        }.items()
    },
    **{
        source_id: {
            "search": _LiveRoute(
                OHIO_SHERIFF_REALAUCTION_ADAPTER,
                "auctions",
                _ohio_sheriff_realauction_args,
            ),
            "address": _LiveRoute(
                OHIO_SHERIFF_REALAUCTION_ADAPTER,
                "auctions",
                _ohio_sheriff_realauction_args,
            ),
            "parcel": _LiveRoute(
                OHIO_SHERIFF_REALAUCTION_ADAPTER,
                "auctions",
                _ohio_sheriff_realauction_args,
            ),
            "sale": _LiveRoute(
                OHIO_SHERIFF_REALAUCTION_ADAPTER,
                "auctions",
                _ohio_sheriff_realauction_args,
            ),
            "event": _LiveRoute(
                OHIO_SHERIFF_REALAUCTION_ADAPTER,
                "auctions",
                _ohio_sheriff_realauction_args,
            ),
            "freshness": _LiveRoute(
                OHIO_SHERIFF_REALAUCTION_ADAPTER,
                "calendar",
                _ohio_sheriff_realauction_args,
            ),
            "discovery": _LiveRoute(
                OHIO_SHERIFF_REALAUCTION_ADAPTER,
                "source",
                _ohio_sheriff_realauction_args,
            ),
            "probe": _LiveRoute(
                OHIO_SHERIFF_REALAUCTION_ADAPTER,
                "probe",
                _ohio_sheriff_realauction_args,
            ),
        }
        for source_id in OHIO_SHERIFF_REALAUCTION_SOURCE_IDS
    },
    OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID: {
        "search": _LiveRoute(
            OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER,
            "year",
            _licking_foreclosure_archive_args,
        ),
        "address": _LiveRoute(
            OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER,
            "year",
            _licking_foreclosure_archive_args,
        ),
        "parcel": _LiveRoute(
            OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER,
            "year",
            _licking_foreclosure_archive_args,
        ),
        "sale": _LiveRoute(
            OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER,
            "year",
            _licking_foreclosure_archive_args,
        ),
        "event": _LiveRoute(
            OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER,
            "case",
            _licking_foreclosure_archive_args,
        ),
        "releases": _LiveRoute(
            OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER,
            "years",
            _licking_foreclosure_archive_args,
        ),
        "discovery": _LiveRoute(
            OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER,
            "source",
            _licking_foreclosure_archive_args,
        ),
        "probe": _LiveRoute(
            OHIO_LICKING_FORECLOSURE_ARCHIVE_ADAPTER,
            "probe",
            _licking_foreclosure_archive_args,
        ),
    },
    OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID: {
        "search": _LiveRoute(
            OHIO_FRANKLIN_AUDITOR_BULK_ADAPTER,
            "rows",
            _ohio_franklin_auditor_bulk_args,
        ),
        "parcel": _LiveRoute(
            OHIO_FRANKLIN_AUDITOR_BULK_ADAPTER,
            "rows",
            _ohio_franklin_auditor_bulk_args,
        ),
        "releases": _LiveRoute(
            OHIO_FRANKLIN_AUDITOR_BULK_ADAPTER,
            "releases",
            _ohio_franklin_auditor_bulk_args,
        ),
        "manifest": _LiveRoute(
            OHIO_FRANKLIN_AUDITOR_BULK_ADAPTER,
            "artifacts",
            _ohio_franklin_auditor_bulk_args,
        ),
        "download": _LiveRoute(
            OHIO_FRANKLIN_AUDITOR_BULK_ADAPTER,
            "download",
            _ohio_franklin_auditor_bulk_args,
        ),
        "discovery": _LiveRoute(
            OHIO_FRANKLIN_AUDITOR_BULK_ADAPTER,
            "source",
            _ohio_franklin_auditor_bulk_args,
        ),
        "probe": _LiveRoute(
            OHIO_FRANKLIN_AUDITOR_BULK_ADAPTER,
            "probe",
            _ohio_franklin_auditor_bulk_args,
        ),
    },
    OHIO_FRANKLIN_SALES_GIS_SOURCE_ID: {
        operation: _LiveRoute(
            OHIO_FRANKLIN_SALES_GIS_ADAPTER,
            adapter_command,
            _ohio_franklin_sales_gis_args,
        )
        for operation, adapter_command in {
            "search": "search",
            "owner": "party",
            "address": "search",
            "parcel": "parcel",
            "map": "parcel",
            "fid": "object-id",
            "geometry": "object-id",
            "sale": "date-range",
            "instrument": "conveyance",
            "count": "count",
            "freshness": "schema",
            "discovery": "source",
            "probe": "probe",
        }.items()
    },
    query_ohio_pax_recorders.DELAWARE_SOURCE_ID: {
        "search": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "search",
            _ohio_pax_recorder_args,
        ),
        "instrument": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "document-info",
            _ohio_pax_recorder_args,
        ),
        "download": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "download",
            _ohio_pax_recorder_args,
        ),
        "probe": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "probe",
            _ohio_pax_recorder_args,
        ),
    },
    query_ohio_pax_recorders.LICKING_SOURCE_ID: {
        "search": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "search",
            _ohio_pax_recorder_args,
        ),
        "probe": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "probe",
            _ohio_pax_recorder_args,
        ),
    },
    OHIO_LICKING_RECORDER_DETAIL_SOURCE_ID: {
        "instrument": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "document-info",
            _ohio_pax_recorder_args,
        ),
        "download": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "download",
            _ohio_pax_recorder_args,
        ),
        "probe": _LiveRoute(
            OHIO_PAX_RECORDER_ADAPTER,
            "probe",
            _ohio_pax_recorder_args,
        ),
    },
    OHIO_LICKING_AUDITOR_GIS_SOURCE_ID: {
        operation: _LiveRoute(
            OHIO_LICKING_AUDITOR_GIS_ADAPTER,
            adapter_command,
            _ohio_licking_auditor_gis_args,
        )
        for operation, adapter_command in {
            "search": "search",
            "owner": "owner",
            "address": "situs",
            "situs": "situs",
            "mailing": "mailing",
            "parcel": "parcel",
            "map": "parcel",
            "fid": "occurrence",
            "geometry": "occurrence",
            "legal": "legal-description",
            "land-use": "land-use",
            "instrument": "instrument",
            "freshness": "metadata",
            "discovery": "source",
            "probe": "probe",
        }.items()
    },
    OHIO_STATEWIDE_PARCELS_SOURCE_ID: {
        "search": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "search",
            _ohio_statewide_parcel_args,
        ),
        "address": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "address",
            _ohio_statewide_parcel_args,
        ),
        "parcel": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "parcel",
            _ohio_statewide_parcel_args,
        ),
        "map": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "parcel",
            _ohio_statewide_parcel_args,
        ),
        "land-use": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "land-use",
            _ohio_statewide_parcel_args,
        ),
        "count": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "count",
            _ohio_statewide_parcel_args,
        ),
        "freshness": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "metadata",
            _ohio_statewide_parcel_args,
        ),
        "discovery": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "source",
            _ohio_statewide_parcel_args,
        ),
        "probe": _LiveRoute(
            OHIO_STATEWIDE_PARCELS_ADAPTER,
            "probe",
            _ohio_statewide_parcel_args,
        ),
    },
    NEW_JERSEY_DCA_PROPERTY_SOURCE_ID: {
        "search": _LiveRoute(
            NEW_JERSEY_DCA_PROPERTY_ADAPTER,
            "search",
            _new_jersey_dca_property_args,
        ),
        "account": _LiveRoute(
            NEW_JERSEY_DCA_PROPERTY_ADAPTER,
            "registration",
            _new_jersey_dca_property_args,
        ),
        "address": _LiveRoute(
            NEW_JERSEY_DCA_PROPERTY_ADAPTER,
            "address",
            _new_jersey_dca_property_args,
        ),
        "parcel": _LiveRoute(
            NEW_JERSEY_DCA_PROPERTY_ADAPTER,
            "parcel",
            _new_jersey_dca_property_args,
        ),
        "probe": _LiveRoute(
            NEW_JERSEY_DCA_PROPERTY_ADAPTER,
            "probe",
            _new_jersey_dca_property_args,
        ),
    },
    NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID: {
        "search": _LiveRoute(
            NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER,
            "search",
            _new_jersey_statewide_parcel_args,
        ),
        "address": _LiveRoute(
            NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER,
            "address",
            _new_jersey_statewide_parcel_args,
        ),
        "parcel": _LiveRoute(
            NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER,
            "pin",
            _new_jersey_statewide_parcel_args,
        ),
        "map": _LiveRoute(
            NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER,
            "pin",
            _new_jersey_statewide_parcel_args,
        ),
        "count": _LiveRoute(
            NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER,
            "count",
            _new_jersey_statewide_parcel_args,
        ),
        "point": _LiveRoute(
            NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER,
            "point",
            _new_jersey_statewide_parcel_args,
        ),
        "bbox": _LiveRoute(
            NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER,
            "bbox",
            _new_jersey_statewide_parcel_args,
        ),
        "probe": _LiveRoute(
            NEW_JERSEY_STATEWIDE_PARCELS_ADAPTER,
            "probe",
            _new_jersey_statewide_parcel_args,
        ),
    },
    NEW_JERSEY_SR1A_SOURCE_ID: {
        "search": _LiveRoute(
            NEW_JERSEY_SR1A_ADAPTER,
            "search",
            _new_jersey_sr1a_args,
        ),
        "owner": _LiveRoute(
            NEW_JERSEY_SR1A_ADAPTER,
            "party",
            _new_jersey_sr1a_args,
        ),
        "address": _LiveRoute(
            NEW_JERSEY_SR1A_ADAPTER,
            "property-address",
            _new_jersey_sr1a_args,
        ),
        "parcel": _LiveRoute(
            NEW_JERSEY_SR1A_ADAPTER,
            "block-lot",
            _new_jersey_sr1a_args,
        ),
        "sale": _LiveRoute(
            NEW_JERSEY_SR1A_ADAPTER,
            "search",
            _new_jersey_sr1a_args,
        ),
        "instrument": _LiveRoute(
            NEW_JERSEY_SR1A_ADAPTER,
            "deed",
            _new_jersey_sr1a_args,
        ),
        "probe": _LiveRoute(
            NEW_JERSEY_SR1A_ADAPTER,
            "probe",
            _new_jersey_sr1a_args,
        ),
    },
    NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID: {
        "search": _LiveRoute(
            NEW_YORK_STATEWIDE_PARCELS_ADAPTER,
            "search",
            _new_york_statewide_parcel_args,
        ),
        "owner": _LiveRoute(
            NEW_YORK_STATEWIDE_PARCELS_ADAPTER,
            "owner",
            _new_york_statewide_parcel_args,
        ),
        "address": _LiveRoute(
            NEW_YORK_STATEWIDE_PARCELS_ADAPTER,
            "address",
            _new_york_statewide_parcel_args,
        ),
        "parcel": _LiveRoute(
            NEW_YORK_STATEWIDE_PARCELS_ADAPTER,
            "parcel",
            _new_york_statewide_parcel_args,
        ),
        "map": _LiveRoute(
            NEW_YORK_STATEWIDE_PARCELS_ADAPTER,
            "parcel",
            _new_york_statewide_parcel_args,
        ),
        "point": _LiveRoute(
            NEW_YORK_STATEWIDE_PARCELS_ADAPTER,
            "point",
            _new_york_statewide_parcel_args,
        ),
        "instrument": _LiveRoute(
            NEW_YORK_STATEWIDE_PARCELS_ADAPTER,
            "deed",
            _new_york_statewide_parcel_args,
        ),
        "probe": _LiveRoute(
            NEW_YORK_STATEWIDE_PARCELS_ADAPTER,
            "probe",
            _new_york_statewide_parcel_args,
        ),
    },
    NYC_PIP_SOURCE_ID: {
        "parcel": _LiveRoute(
            NYC_PIP_ADAPTER,
            "parcel",
            _nyc_pip_args,
        ),
        "owner": _LiveRoute(
            NYC_PIP_ADAPTER,
            "owner",
            _nyc_pip_args,
        ),
        "address": _LiveRoute(
            NYC_PIP_ADAPTER,
            "address",
            _nyc_pip_args,
        ),
        "detail": _LiveRoute(
            NYC_PIP_ADAPTER,
            "detail",
            _nyc_pip_args,
        ),
        "map": _LiveRoute(
            NYC_PIP_ADAPTER,
            "geometry",
            _nyc_pip_args,
        ),
        "assessment": _LiveRoute(
            NYC_PIP_ADAPTER,
            "current-assessment",
            _nyc_pip_args,
        ),
        "history": _LiveRoute(
            NYC_PIP_ADAPTER,
            "assessment-history",
            _nyc_pip_args,
        ),
        "exemptions": _LiveRoute(
            NYC_PIP_ADAPTER,
            "exemptions",
            _nyc_pip_args,
        ),
        "discovery": _LiveRoute(
            NYC_PIP_ADAPTER,
            "discovery",
            _nyc_pip_args,
        ),
        "probe": _LiveRoute(
            NYC_PIP_ADAPTER,
            "probe",
            _nyc_pip_args,
        ),
    },
    NEW_YORK_SALESWEB_SOURCE_ID: {
        operation: _LiveRoute(
            NEW_YORK_SALESWEB_ADAPTER,
            operation,
            _new_york_salesweb_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "parcel",
            "sale",
            "instrument",
            "probe",
        )
    },
    ORANGE_TAX_COLLECTOR_SOURCE_ID: {
        "search": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "search",
            _orange_tax_collector_args,
        ),
        "owner": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "search",
            _orange_tax_collector_args,
        ),
        "address": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "search",
            _orange_tax_collector_args,
        ),
        "account": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "account",
            _orange_tax_collector_args,
        ),
        "parcel": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "account",
            _orange_tax_collector_args,
        ),
        "discovery": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "sources",
            _orange_tax_collector_args,
        ),
        "releases": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "bulk-manifest",
            _orange_tax_collector_args,
        ),
        "manifest": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "bulk-manifest",
            _orange_tax_collector_args,
        ),
        "probe": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "bulk-probe",
            _orange_tax_collector_args,
        ),
        "download": _LiveRoute(
            ORANGE_TAX_COLLECTOR_ADAPTER,
            "bulk-download",
            _orange_tax_collector_args,
        ),
    },
    PALM_BEACH_PROPERTY_SOURCE_ID: {
        "search": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "search",
            _palm_beach_property_args,
        ),
        "owner": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "owner",
            _palm_beach_property_args,
        ),
        "address": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "address",
            _palm_beach_property_args,
        ),
        "subdivision": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "search",
            _palm_beach_property_args,
        ),
        "account": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "parcel",
            _palm_beach_property_args,
        ),
        "parcel": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "parcel",
            _palm_beach_property_args,
        ),
        "sale": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "sale",
            _palm_beach_property_args,
        ),
        "map": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "parcel",
            _palm_beach_property_args,
        ),
        "point": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "point",
            _palm_beach_property_args,
        ),
        "bbox": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "bbox",
            _palm_beach_property_args,
        ),
        "count": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "count",
            _palm_beach_property_args,
        ),
        "discovery": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "discovery",
            _palm_beach_property_args,
        ),
        "probe": _LiveRoute(
            PALM_BEACH_PROPERTY_ADAPTER,
            "probe",
            _palm_beach_property_args,
        ),
    },
    PALM_BEACH_TAX_SOURCE_ID: {
        "search": _LiveRoute(
            PALM_BEACH_TAX_ADAPTER,
            "search",
            _palm_beach_tax_args,
        ),
        "owner": _LiveRoute(
            PALM_BEACH_TAX_ADAPTER,
            "owner",
            _palm_beach_tax_args,
        ),
        "address": _LiveRoute(
            PALM_BEACH_TAX_ADAPTER,
            "address",
            _palm_beach_tax_args,
        ),
        "parcel": _LiveRoute(
            PALM_BEACH_TAX_ADAPTER,
            "parcel",
            _palm_beach_tax_args,
        ),
        "account": _LiveRoute(
            PALM_BEACH_TAX_ADAPTER,
            "account",
            _palm_beach_tax_args,
        ),
        "event": _LiveRoute(
            PALM_BEACH_TAX_ADAPTER,
            "bills",
            _palm_beach_tax_args,
        ),
        "discovery": _LiveRoute(
            PALM_BEACH_TAX_ADAPTER,
            "discovery",
            _palm_beach_tax_args,
        ),
        "probe": _LiveRoute(
            PALM_BEACH_TAX_ADAPTER,
            "probe",
            _palm_beach_tax_args,
        ),
    },
    PALM_BEACH_TAX_DEEDS_SOURCE_ID: {
        "search": _LiveRoute(
            PALM_BEACH_TAX_DEEDS_ADAPTER,
            "search",
            _palm_beach_tax_deeds_args,
        ),
        "owner": _LiveRoute(
            PALM_BEACH_TAX_DEEDS_ADAPTER,
            "owner",
            _palm_beach_tax_deeds_args,
        ),
        "parcel": _LiveRoute(
            PALM_BEACH_TAX_DEEDS_ADAPTER,
            "parcel",
            _palm_beach_tax_deeds_args,
        ),
        "sale": _LiveRoute(
            PALM_BEACH_TAX_DEEDS_ADAPTER,
            "sale-date",
            _palm_beach_tax_deeds_args,
        ),
        "event": _LiveRoute(
            PALM_BEACH_TAX_DEEDS_ADAPTER,
            "detail",
            _palm_beach_tax_deeds_args,
        ),
        "download": _LiveRoute(
            PALM_BEACH_TAX_DEEDS_ADAPTER,
            "document",
            _palm_beach_tax_deeds_args,
        ),
        "discovery": _LiveRoute(
            PALM_BEACH_TAX_DEEDS_ADAPTER,
            "discovery",
            _palm_beach_tax_deeds_args,
        ),
        "probe": _LiveRoute(
            PALM_BEACH_TAX_DEEDS_ADAPTER,
            "probe",
            _palm_beach_tax_deeds_args,
        ),
    },
    PALM_BEACH_RECORDER_SOURCE_ID: {
        "instrument": _LiveRoute(
            PALM_BEACH_RECORDER_ADAPTER,
            "instrument",
            _palm_beach_recorder_args,
        ),
        "probe": _LiveRoute(
            PALM_BEACH_RECORDER_ADAPTER,
            "probe",
            _palm_beach_recorder_args,
        ),
    },
    BROWARD_RECORDER_SOURCE_ID: {
        "search": _LiveRoute(
            BROWARD_RECORDER_ADAPTER,
            "name",
            _broward_recorder_args,
        ),
        "parcel": _LiveRoute(
            BROWARD_RECORDER_ADAPTER,
            "parcel",
            _broward_recorder_args,
        ),
        "instrument": _LiveRoute(
            BROWARD_RECORDER_ADAPTER,
            "detail",
            _broward_recorder_args,
        ),
        "probe": _LiveRoute(
            BROWARD_RECORDER_ADAPTER,
            "probe",
            _broward_recorder_args,
        ),
    },
    SANTA_FE_PROPERTY_SOURCE_ID: {
        "search": _LiveRoute(
            SANTA_FE_PROPERTY_ADAPTER,
            "owner",
            _santa_fe_property_args,
        ),
        "owner": _LiveRoute(
            SANTA_FE_PROPERTY_ADAPTER,
            "owner",
            _santa_fe_property_args,
        ),
        "address": _LiveRoute(
            SANTA_FE_PROPERTY_ADAPTER,
            "address",
            _santa_fe_property_args,
        ),
        "parcel": _LiveRoute(
            SANTA_FE_PROPERTY_ADAPTER,
            "parcel",
            _santa_fe_property_args,
        ),
        "map": _LiveRoute(
            SANTA_FE_PROPERTY_ADAPTER,
            "objectid",
            _santa_fe_property_args,
        ),
        "discovery": _LiveRoute(
            SANTA_FE_PROPERTY_ADAPTER,
            "discovery",
            _santa_fe_property_args,
        ),
        "freshness": _LiveRoute(
            SANTA_FE_PROPERTY_ADAPTER,
            "metadata",
            _santa_fe_property_args,
        ),
        "probe": _LiveRoute(
            SANTA_FE_PROPERTY_ADAPTER,
            "probe",
            _santa_fe_property_args,
        ),
    },
    SANTA_FE_CLERKTRACK_SOURCE_ID: {
        "search": _LiveRoute(
            SANTA_FE_CLERKTRACK_ADAPTER,
            "search",
            _santa_fe_clerktrack_args,
        ),
        "owner": _LiveRoute(
            SANTA_FE_CLERKTRACK_ADAPTER,
            "search",
            _santa_fe_clerktrack_args,
        ),
        "instrument": _LiveRoute(
            SANTA_FE_CLERKTRACK_ADAPTER,
            "detail",
            _santa_fe_clerktrack_args,
        ),
        "detail": _LiveRoute(
            SANTA_FE_CLERKTRACK_ADAPTER,
            "detail",
            _santa_fe_clerktrack_args,
        ),
        "discovery": _LiveRoute(
            SANTA_FE_CLERKTRACK_ADAPTER,
            "routes",
            _santa_fe_clerktrack_args,
        ),
        "probe": _LiveRoute(
            SANTA_FE_CLERKTRACK_ADAPTER,
            "probe",
            _santa_fe_clerktrack_args,
        ),
    },
    USVI_RECORDER_SOURCE_ID: {
        "search": _LiveRoute(
            USVI_RECORDER_ADAPTER,
            "search",
            _usvi_recorder_args,
        ),
        "owner": _LiveRoute(
            USVI_RECORDER_ADAPTER,
            "search",
            _usvi_recorder_args,
        ),
        "instrument": _LiveRoute(
            USVI_RECORDER_ADAPTER,
            "document",
            _usvi_recorder_args,
        ),
        "download": _LiveRoute(
            USVI_RECORDER_ADAPTER,
            "page",
            _usvi_recorder_args,
        ),
        "probe": _LiveRoute(
            USVI_RECORDER_ADAPTER,
            "probe",
            _usvi_recorder_args,
        ),
    },
    USVI_PROPERTY_TAX_SOURCE_ID: {
        "search": _LiveRoute(
            USVI_PROPERTY_TAX_ADAPTER,
            "search",
            _usvi_property_tax_args,
        ),
        "owner": _LiveRoute(
            USVI_PROPERTY_TAX_ADAPTER,
            "search",
            _usvi_property_tax_args,
        ),
        "address": _LiveRoute(
            USVI_PROPERTY_TAX_ADAPTER,
            "search",
            _usvi_property_tax_args,
        ),
        "parcel": _LiveRoute(
            USVI_PROPERTY_TAX_ADAPTER,
            "parcel",
            _usvi_property_tax_args,
        ),
        "download": _LiveRoute(
            USVI_PROPERTY_TAX_ADAPTER,
            "artifact",
            _usvi_property_tax_args,
        ),
        "probe": _LiveRoute(
            USVI_PROPERTY_TAX_ADAPTER,
            "probe",
            _usvi_property_tax_args,
        ),
    },
    MASON_COUNTY_TAX_PARCELS_SOURCE_ID: {
        "search": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "search",
            _mason_county_tax_parcel_args,
        ),
        "owner": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "owner",
            _mason_county_tax_parcel_args,
        ),
        "address": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "address",
            _mason_county_tax_parcel_args,
        ),
        "subdivision": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "search",
            _mason_county_tax_parcel_args,
        ),
        "parcel": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "parcel",
            _mason_county_tax_parcel_args,
        ),
        "map": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "parcel",
            _mason_county_tax_parcel_args,
        ),
        "point": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "point",
            _mason_county_tax_parcel_args,
        ),
        "bbox": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "bbox",
            _mason_county_tax_parcel_args,
        ),
        "count": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "count",
            _mason_county_tax_parcel_args,
        ),
        "discovery": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "metadata",
            _mason_county_tax_parcel_args,
        ),
        "probe": _LiveRoute(
            MASON_COUNTY_TAX_PARCELS_ADAPTER,
            "probe",
            _mason_county_tax_parcel_args,
        ),
    },
    WASHINGTON_LAND_RECORDS_SOURCE_ID: {
        "search": _LiveRoute(
            WASHINGTON_LAND_RECORDS_ADAPTER,
            "search",
            _washington_land_records_args,
        ),
        "owner": _LiveRoute(
            WASHINGTON_LAND_RECORDS_ADAPTER,
            "search",
            _washington_land_records_args,
        ),
        "instrument": _LiveRoute(
            WASHINGTON_LAND_RECORDS_ADAPTER,
            "detail",
            _washington_land_records_args,
        ),
    },
    **{
        source_id: {
            "search": _LiveRoute(
                WASHINGTON_TAXSIFTER_ADAPTER,
                "search",
                _washington_taxsifter_args,
            ),
            "owner": _LiveRoute(
                WASHINGTON_TAXSIFTER_ADAPTER,
                "search",
                _washington_taxsifter_args,
            ),
            "address": _LiveRoute(
                WASHINGTON_TAXSIFTER_ADAPTER,
                "search",
                _washington_taxsifter_args,
            ),
            "parcel": _LiveRoute(
                WASHINGTON_TAXSIFTER_ADAPTER,
                "detail",
                _washington_taxsifter_args,
            ),
            "account": _LiveRoute(
                WASHINGTON_TAXSIFTER_ADAPTER,
                "detail",
                _washington_taxsifter_args,
            ),
            "sale": _LiveRoute(
                WASHINGTON_TAXSIFTER_ADAPTER,
                "sales",
                _washington_taxsifter_args,
            ),
            "discovery": _LiveRoute(
                WASHINGTON_TAXSIFTER_ADAPTER,
                "metadata",
                _washington_taxsifter_args,
            ),
            "probe": _LiveRoute(
                WASHINGTON_TAXSIFTER_ADAPTER,
                "probe",
                _washington_taxsifter_args,
            ),
        }
        for source_id in WASHINGTON_TAXSIFTER_SOURCE_IDS
    },
    NC_SOURCE_ID: {
        "owner": _LiveRoute(query_nc_property, "owner", _nc_args),
        "address": _LiveRoute(query_nc_property, "address", _nc_args),
        "parcel": _LiveRoute(query_nc_property, "parcel", _nc_args),
        "map": _LiveRoute(query_nc_property, "parcel", _nc_args),
    },
    BEXAR_SOURCE_ID: {
        "owner": _LiveRoute(query_bexar_property, "owner", _bexar_args),
        "address": _LiveRoute(query_bexar_property, "address", _bexar_args),
        "parcel": _LiveRoute(query_bexar_property, "parcel", _bexar_args),
        "map": _LiveRoute(query_bexar_property, "parcel", _bexar_args),
    },
    DENVER_PROPERTY_SOURCE_ID: {
        "owner": _LiveRoute(
            query_denver_property,
            "owner",
            _denver_args,
        ),
        "address": _LiveRoute(
            query_denver_property,
            "address",
            _denver_args,
        ),
        "parcel": _LiveRoute(
            query_denver_property,
            "parcel",
            _denver_args,
        ),
        "map": _LiveRoute(
            query_denver_property,
            "parcel",
            _denver_args,
        ),
    },
    DENVER_DELINQUENT_TAX_SOURCE_ID: {
        operation: _LiveRoute(
            query_denver_delinquent_tax,
            "search",
            _denver_delinquent_tax_args,
        )
        for operation in ("search", "owner", "address", "parcel", "account")
    },
    DENVER_FORECLOSURE_SOURCE_ID: {
        operation: _LiveRoute(
            query_denver_foreclosures,
            "search",
            _denver_foreclosure_args,
        )
        for operation in ("search", "owner", "address")
    },
    DELAWARE_FIRSTMAP_SOURCE_ID: {
        "parcel": _LiveRoute(
            query_delaware_firstmap,
            "pin",
            _delaware_firstmap_args,
        ),
        "map": _LiveRoute(
            query_delaware_firstmap,
            "pin",
            _delaware_firstmap_args,
        ),
    },
    ARLINGTON_PROPERTY_SOURCE_ID: {
        "address": _LiveRoute(
            query_arlington_property,
            "address",
            _arlington_args,
        ),
        "parcel": _LiveRoute(
            query_arlington_property,
            "parcel",
            _arlington_args,
        ),
        "map": _LiveRoute(
            query_arlington_property,
            "parcel",
            _arlington_args,
        ),
    },
    COOK_SOURCE_ID: {
        "parcel": _LiveRoute(query_cook_property, "parcel", _cook_args),
    },
    MD_SOURCE_ID: {
        "address": _LiveRoute(query_md_property, "address", _md_args),
        "parcel": _LiveRoute(query_md_property, "parcel", _md_args),
    },
    MD_PLATS_SOURCE_ID: {
        "search": _LiveRoute(
            MD_PLATS_ADAPTER,
            "search",
            _md_plats_args,
        ),
        "subdivision": _LiveRoute(
            MD_PLATS_ADAPTER,
            "subdivision",
            _md_plats_args,
        ),
        "survey": _LiveRoute(
            MD_PLATS_ADAPTER,
            "survey",
            _md_plats_args,
        ),
        "instrument": _LiveRoute(
            MD_PLATS_ADAPTER,
            "instrument",
            _md_plats_args,
        ),
        "download": _LiveRoute(
            MD_PLATS_ADAPTER,
            "download",
            _md_plats_args,
        ),
        "discovery": _LiveRoute(
            MD_PLATS_ADAPTER,
            "counties",
            _md_plats_args,
        ),
        "probe": _LiveRoute(
            MD_PLATS_ADAPTER,
            "probe",
            _md_plats_args,
        ),
    },
    MD_MDP_PARCEL_POINTS_SOURCE_ID: {
        "search": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "search",
            _md_mdp_parcel_points_args,
        ),
        "address": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "address",
            _md_mdp_parcel_points_args,
        ),
        "account": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "account",
            _md_mdp_parcel_points_args,
        ),
        "parcel": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "account",
            _md_mdp_parcel_points_args,
        ),
        "map": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "map",
            _md_mdp_parcel_points_args,
        ),
        "point": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "point",
            _md_mdp_parcel_points_args,
        ),
        "bbox": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "bbox",
            _md_mdp_parcel_points_args,
        ),
        "count": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "count",
            _md_mdp_parcel_points_args,
        ),
        "land-use": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "land-use",
            _md_mdp_parcel_points_args,
        ),
        "survey": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "survey",
            _md_mdp_parcel_points_args,
        ),
        "freshness": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "metadata",
            _md_mdp_parcel_points_args,
        ),
        "discovery": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "discovery",
            _md_mdp_parcel_points_args,
        ),
        "probe": _LiveRoute(
            MD_MDP_PARCEL_POINTS_ADAPTER,
            "probe",
            _md_mdp_parcel_points_args,
        ),
    },
    **{
        source_id: {
            **{
                operation: _LiveRoute(
                    query_md_mdp_property_downloads,
                    "manifest",
                    _md_mdp_property_download_args,
                )
                for operation in (
                    "releases",
                    "manifest",
                    "discovery",
                )
            },
            "probe": _LiveRoute(
                query_md_mdp_property_downloads,
                "probe",
                _md_mdp_property_download_args,
            ),
            "download": _LiveRoute(
                query_md_mdp_property_downloads,
                "download",
                _md_mdp_property_download_args,
            ),
        }
        for source_id in MD_MDP_PROPERTY_DOWNLOAD_SOURCE_IDS
    },
    MIAMI_DADE_PA_SOURCE_ID: {
        "owner": _LiveRoute(
            query_miami_dade_property,
            "owner",
            _miami_dade_args,
        ),
        "address": _LiveRoute(
            query_miami_dade_property,
            "address",
            _miami_dade_args,
        ),
        "parcel": _LiveRoute(
            query_miami_dade_property,
            "folio",
            _miami_dade_args,
        ),
        "map": _LiveRoute(
            query_miami_dade_property,
            "folio",
            _miami_dade_args,
        ),
    },
    EBR_SOURCE_ID: {
        "owner": _LiveRoute(query_la_property, "owner", _ebr_args),
        "address": _LiveRoute(query_la_property, "address", _ebr_args),
        "parcel": _LiveRoute(query_la_property, "parcel", _ebr_args),
    },
    ORLEANS_SOURCE_ID: {
        "account": _LiveRoute(
            query_orleans_property,
            "account",
            _orleans_args,
        ),
        "owner": _LiveRoute(
            query_orleans_property,
            "owner",
            _orleans_args,
        ),
        "address": _LiveRoute(
            query_orleans_property,
            "address",
            _orleans_args,
        ),
        "parcel": _LiveRoute(
            query_orleans_property,
            "parcel",
            _orleans_args,
        ),
        "map": _LiveRoute(
            query_orleans_property,
            "parcel",
            _orleans_args,
        ),
        "search": _LiveRoute(
            query_orleans_property,
            "search",
            _orleans_args,
        ),
    },
    **{
        source_id: {
            operation: _LiveRoute(
                query_oregon_taxlots,
                ("parcel" if operation in {"parcel", "map"} else "search"),
                _oregon_taxlots_args,
            )
            for operation in (
                ("search", "address", "parcel", "map", "account", "owner")
                if source_id == OREGON_PORTLAND_TAXLOT_SOURCE_ID
                else ("search", "address", "parcel", "map", "account")
            )
        }
        for source_id in OREGON_TAXLOT_SOURCE_IDS
    },
    OREGON_BENTON_TAXLOT_SOURCE_ID: {
        "search": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "search",
            _oregon_benton_args,
        ),
        "owner": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "owner",
            _oregon_benton_args,
        ),
        "address": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "address",
            _oregon_benton_args,
        ),
        "account": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "account",
            _oregon_benton_args,
        ),
        "parcel": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "search",
            _oregon_benton_args,
        ),
        "map": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "search",
            _oregon_benton_args,
        ),
    },
    OREGON_BENTON_BULK_SOURCE_ID: {
        "search": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "bulk-manifest",
            _oregon_benton_args,
        ),
        "instrument": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "artifact-probe",
            _oregon_benton_args,
        ),
    },
    OREGON_BENTON_MAP_SOURCE_ID: {
        "search": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "maps",
            _oregon_benton_args,
        ),
        "parcel": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "maps",
            _oregon_benton_args,
        ),
        "instrument": _LiveRoute(
            OREGON_BENTON_ADAPTER,
            "artifact-probe",
            _oregon_benton_args,
        ),
    },
    query_oregon_yamhill_property.ASCEND_SOURCE_ID: {
        operation: _LiveRoute(
            query_oregon_yamhill_property,
            "detail" if operation == "account" else "search",
            _oregon_yamhill_args,
        )
        for operation in ("search", "address", "account", "parcel")
    },
    **{
        source_id: {
            operation: _LiveRoute(
                query_oregon_yamhill_property,
                "search",
                _oregon_yamhill_args,
            )
            for operation in (
                "search",
                "owner",
                "address",
                "account",
                "parcel",
                "map",
                "instrument",
            )
        }
        for source_id in (
            query_oregon_yamhill_property.TAXLOT_SOURCE_ID,
            query_oregon_yamhill_property.RETIRED_SOURCE_ID,
        )
    },
    query_oregon_yamhill_property.PERMIT_SOURCE_ID: {
        operation: _LiveRoute(
            query_oregon_yamhill_property,
            "search",
            _oregon_yamhill_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "account",
            "parcel",
            "map",
            "event",
        )
    },
    query_oregon_clackamas_property.ASCEND_SOURCE_ID: {
        operation: _LiveRoute(
            query_oregon_clackamas_property,
            "detail" if operation == "account" else "search",
            _oregon_clackamas_args,
        )
        for operation in ("search", "address", "account")
    },
    query_oregon_clackamas_property.CMAP_SOURCE_ID: {
        operation: _LiveRoute(
            query_oregon_clackamas_property,
            "search",
            _oregon_clackamas_args,
        )
        for operation in (
            "search",
            "address",
            "account",
            "parcel",
            "map",
            "instrument",
        )
    },
    query_oregon_wasco_property.ASCEND_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASCO_ADAPTER,
            "detail" if operation == "account" else "search",
            _oregon_wasco_args,
        )
        for operation in ("search", "address", "account", "parcel")
    },
    query_oregon_wasco_property.TAXLOT_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASCO_ADAPTER,
            "search",
            _oregon_wasco_args,
        )
        for operation in ("search", "owner", "account", "parcel", "map")
    },
    **{
        source_id: {
            operation: _LiveRoute(
                OREGON_WASCO_ADAPTER,
                "search",
                _oregon_wasco_args,
            )
            for operation in ("search", "instrument", "map")
        }
        for source_id in query_oregon_wasco_property.SURVEY_SOURCE_IDS
    },
    query_oregon_washington_property.SURVEY_API_SOURCE_ID: {
        "search": _LiveRoute(
            OREGON_WASHINGTON_ADAPTER,
            "survey-search",
            _oregon_washington_args,
        ),
        "parcel": _LiveRoute(
            OREGON_WASHINGTON_ADAPTER,
            "survey-detail",
            _oregon_washington_args,
        ),
        "instrument": _LiveRoute(
            OREGON_WASHINGTON_ADAPTER,
            "survey-search",
            _oregon_washington_args,
        ),
    },
    query_oregon_washington_property.SURVEY_MAP_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASHINGTON_ADAPTER,
            "arcgis",
            _oregon_washington_args,
        )
        for operation in ("search", "parcel", "map")
    },
    query_oregon_washington_property.TAXLOT_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASHINGTON_ADAPTER,
            "taxlots",
            _oregon_washington_args,
        )
        for operation in ("search", "parcel", "map")
    },
    query_oregon_washington_property.SITUS_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASHINGTON_ADAPTER,
            "situs",
            _oregon_washington_args,
        )
        for operation in ("search", "address", "parcel", "account", "map")
    },
    query_oregon_washington_property.INTERMAP_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASHINGTON_ADAPTER,
            "intermap",
            _oregon_washington_args,
        )
        for operation in ("parcel", "map")
    },
    query_oregon_washington_property.TAX_SOURCE_ID: {
        "account": _LiveRoute(
            OREGON_WASHINGTON_ADAPTER,
            "tax-account",
            _oregon_washington_args,
        ),
    },
    query_oregon_washington_case_permits.CASEFILE_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASHINGTON_CASE_PERMIT_ADAPTER,
            "case-detail" if operation == "event" else "case-search",
            _oregon_washington_case_permit_args,
        )
        for operation in ("search", "parcel", "event")
    },
    query_oregon_washington_case_permits.TAXLOT_ACTIVITY_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASHINGTON_CASE_PERMIT_ADAPTER,
            "taxlot-activity",
            _oregon_washington_case_permit_args,
        )
        for operation in ("search", "parcel")
    },
    query_oregon_washington_case_permits.BUILDING_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASHINGTON_CASE_PERMIT_ADAPTER,
            "building-search",
            _oregon_washington_case_permit_args,
        )
        for operation in ("search", "address", "parcel", "event")
    },
    query_oregon_washington_case_permits.PERMIT_REPORT_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_WASHINGTON_CASE_PERMIT_ADAPTER,
            "permit-report",
            _oregon_washington_case_permit_args,
        )
        for operation in ("search", "event")
    },
    query_oregon_washington_case_permits.ACCELA_SOURCE_ID: {
        "event": _LiveRoute(
            OREGON_WASHINGTON_CASE_PERMIT_ADAPTER,
            "accela-record",
            _oregon_washington_case_permit_args,
        ),
    },
    query_oregon_washington_case_permits.DOCUMENT_ROUTE_SOURCE_ID: {
        "event": _LiveRoute(
            OREGON_WASHINGTON_CASE_PERMIT_ADAPTER,
            "document-routes",
            _oregon_washington_case_permit_args,
        ),
    },
    query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID: {
        operation: _LiveRoute(
            query_oregon_multnomah_sail,
            "search",
            _oregon_multnomah_sail_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "account",
            "parcel",
            "map",
            "instrument",
        )
    },
    **{
        source_id: {
            operation: _LiveRoute(
                query_oregon_multnomah_sail,
                "search",
                _oregon_multnomah_sail_args,
            )
            for operation in ("search", "map", "instrument")
        }
        for source_id in query_oregon_multnomah_sail.IMAGE_SOURCE_IDS
    },
    OREGON_LINCOLN_PROPERTYWEB_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_LINCOLN_PROPERTYWEB_ADAPTER,
            "search",
            _oregon_lincoln_propertyweb_args,
        )
        for operation in ("search", "owner", "address", "parcel", "account")
    },
    OREGON_LINCOLN_TAXLOT_SOURCE_ID: {
        operation: _LiveRoute(
            OREGON_LINCOLN_TAXLOT_ADAPTER,
            "search",
            _oregon_lincoln_taxlot_args,
        )
        for operation in ("search", "owner", "address", "parcel", "map", "account")
    },
    **{
        source_id: {
            operation: _LiveRoute(
                query_oregon_tax_foreclosures,
                "search",
                _oregon_tax_foreclosure_args,
            )
            for operation in ("search", "owner", "address", "account", "parcel")
        }
        for source_id in OREGON_TAX_FORECLOSURE_SOURCE_IDS
    },
    DESCHUTES_PROPERTY_SOURCE_ID: {
        operation: _LiveRoute(
            query_deschutes_property,
            ("parcel" if operation in {"parcel", "map"} else "search"),
            _deschutes_property_args,
        )
        for operation in (
            "search",
            "address",
            "parcel",
            "map",
            "account",
            "owner",
        )
    },
    DESCHUTES_DIAL_SOURCE_ID: {
        "search": _LiveRoute(
            query_deschutes_dial,
            "search",
            _deschutes_dial_args,
        ),
        "owner": _LiveRoute(
            query_deschutes_dial,
            "search",
            _deschutes_dial_args,
        ),
        "address": _LiveRoute(
            query_deschutes_dial,
            "search",
            _deschutes_dial_args,
        ),
        "subdivision": _LiveRoute(
            query_deschutes_dial,
            "search",
            _deschutes_dial_args,
        ),
        "mobile-park": _LiveRoute(
            query_deschutes_dial,
            "search",
            _deschutes_dial_args,
        ),
        "account": _LiveRoute(
            query_deschutes_dial,
            "account",
            _deschutes_dial_args,
        ),
        "parcel": _LiveRoute(
            query_deschutes_dial,
            "account",
            _deschutes_dial_args,
        ),
    },
    DESCHUTES_CDD_WEBLINK_SOURCE_ID: {
        "account": _LiveRoute(
            DESCHUTES_CDD_WEBLINK_ADAPTER,
            "account",
            _deschutes_cdd_weblink_args,
        ),
    },
    **{
        source_id: {
            "search": _LiveRoute(
                query_oregon_helion_property,
                "search",
                _oregon_helion_property_args,
            ),
            "owner": _LiveRoute(
                query_oregon_helion_property,
                "search",
                _oregon_helion_property_args,
            ),
            "address": _LiveRoute(
                query_oregon_helion_property,
                "search",
                _oregon_helion_property_args,
            ),
            "parcel": _LiveRoute(
                query_oregon_helion_property,
                "search",
                _oregon_helion_property_args,
            ),
            "account": _LiveRoute(
                query_oregon_helion_property,
                "detail",
                _oregon_helion_property_args,
            ),
        }
        for source_id in OREGON_HELION_PROPERTY_SOURCE_IDS
    },
    **{
        source_id: {
            operation: _LiveRoute(
                query_oregon_helion_recorder,
                "search",
                _oregon_helion_recorder_args,
            )
            for operation in ("search", "owner", "instrument")
        }
        for source_id in OREGON_HELION_RECORDER_SOURCE_IDS
    },
    **{
        source_id: {
            operation: _LiveRoute(
                query_oregon_jackson_douglas_assessors,
                "search",
                _oregon_jackson_douglas_assessor_args,
            )
            for operation in (
                "search",
                "owner",
                "address",
                "parcel",
                "map",
                "account",
                *(
                    ("instrument",)
                    if source_id
                    == query_oregon_jackson_douglas_assessors.DOUGLAS_SOURCE_ID
                    else ()
                ),
            )
        }
        for source_id in OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCE_IDS
    },
    **{
        source_id: {
            operation: _LiveRoute(
                query_oregon_jackson_property_events,
                (
                    "record"
                    if operation == "event"
                    else "person"
                    if operation == "owner"
                    else "map-taxlot"
                    if operation in {"parcel", "map"}
                    else operation
                ),
                _oregon_jackson_property_event_args,
            )
            for operation in (
                "search",
                "owner",
                "address",
                "parcel",
                "map",
                "event",
            )
        }
        for source_id in OREGON_JACKSON_PROPERTY_EVENT_SOURCE_IDS
    },
    **{
        source_id: {
            operation: _LiveRoute(
                OREGON_LINN_JOSEPHINE_KLAMATH_ADAPTER,
                "search",
                _oregon_linn_josephine_klamath_args,
            )
            for operation in (
                "search",
                "owner",
                "address",
                "parcel",
                "map",
                "account",
            )
        }
        for source_id in OREGON_LINN_JOSEPHINE_KLAMATH_SOURCE_IDS
    },
    **{
        source_id: {
            "event": _LiveRoute(
                OREGON_JACKSON_ACCELA_ADAPTER,
                "record",
                _oregon_jackson_accela_args,
            )
        }
        for source_id in OREGON_JACKSON_ACCELA_SOURCE_IDS
    },
    query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID: {
        operation: _LiveRoute(
            query_oregon_lane_marion_parcels,
            "parcel" if operation in {"parcel", "map"} else "search",
            _oregon_lane_marion_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "parcel",
            "map",
            "account",
        )
    },
    query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID: {
        operation: _LiveRoute(
            query_oregon_lane_marion_parcels,
            "sale" if operation == "instrument" else "search",
            _oregon_lane_marion_args,
        )
        for operation in (
            "search",
            "address",
            "parcel",
            "map",
            "account",
            "instrument",
        )
    },
    query_oregon_lane_property.ACCOUNT_SOURCE_ID: {
        **{
            operation: _LiveRoute(
                OREGON_LANE_PROPERTY_ADAPTER,
                "search",
                _oregon_lane_property_args,
            )
            for operation in ("search", "owner", "address", "parcel", "map")
        },
        "account": _LiveRoute(
            OREGON_LANE_PROPERTY_ADAPTER,
            "account",
            _oregon_lane_property_args,
        ),
        "probe": _LiveRoute(
            OREGON_LANE_PROPERTY_ADAPTER,
            "probe",
            _oregon_lane_property_args,
        ),
    },
    query_oregon_lane_property.TAX_MAP_SOURCE_ID: {
        **{
            operation: _LiveRoute(
                OREGON_LANE_PROPERTY_ADAPTER,
                "search",
                _oregon_lane_property_args,
            )
            for operation in ("search", "address", "parcel", "map")
        },
        "download": _LiveRoute(
            OREGON_LANE_PROPERTY_ADAPTER,
            "download-tax-map",
            _oregon_lane_property_args,
        ),
        "probe": _LiveRoute(
            OREGON_LANE_PROPERTY_ADAPTER,
            "probe",
            _oregon_lane_property_args,
        ),
    },
    query_oregon_lane_marion_parcels.MARION_PARCELS_SOURCE_ID: {
        operation: _LiveRoute(
            query_oregon_lane_marion_parcels,
            "parcel" if operation in {"parcel", "map"} else "search",
            _oregon_lane_marion_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "parcel",
            "map",
            "account",
            "instrument",
        )
    },
    query_oregon_marion_downloads.SALES_SOURCE_ID: {
        **{
            operation: _LiveRoute(
                query_oregon_marion_downloads,
                "search",
                _oregon_marion_download_args,
            )
            for operation in (
                "search",
                "address",
                "parcel",
                "account",
                "instrument",
                "sale",
            )
        },
        **{
            operation: _LiveRoute(
                query_oregon_marion_downloads,
                (
                    "manifest"
                    if operation
                    in {"releases", "manifest", "discovery"}
                    else operation
                ),
                _oregon_marion_download_args,
            )
            for operation in (
                "releases",
                "manifest",
                "discovery",
                "probe",
                "download",
            )
        },
    },
    query_oregon_marion_downloads.ASSESSMENT_SOURCE_ID: {
        **{
            operation: _LiveRoute(
                query_oregon_marion_downloads,
                "search",
                _oregon_marion_download_args,
            )
            for operation in (
                "search",
                "address",
                "parcel",
                "account",
                "instrument",
            )
        },
        **{
            operation: _LiveRoute(
                query_oregon_marion_downloads,
                (
                    "manifest"
                    if operation
                    in {"releases", "manifest", "discovery"}
                    else operation
                ),
                _oregon_marion_download_args,
            )
            for operation in (
                "releases",
                "manifest",
                "discovery",
                "probe",
                "download",
            )
        },
    },
    REEVES_SOURCE_ID: {
        "search": _LiveRoute(
            query_reeves_records,
            "search",
            _reeves_args,
        ),
        "owner": _LiveRoute(
            query_reeves_records,
            "search",
            _reeves_args,
        ),
        "instrument": _LiveRoute(
            query_reeves_records,
            "search",
            _reeves_args,
        ),
    },
    **{
        source_id: {
            operation: _LiveRoute(
                query_govos_recorders,
                "search",
                _govos_recorder_args,
            )
            for operation in ("search", "owner", "instrument")
        }
        for source_id in GOVOS_RECORDER_SOURCE_IDS
    },
    ACRIS_SOURCE_ID: {
        "owner": _LiveRoute(query_acris, "party", _acris_args),
        "parcel": _LiveRoute(query_acris, "address", _acris_args),
        "instrument": _LiveRoute(query_acris, "document", _acris_args),
        "chain": _LiveRoute(query_acris, "history", _acris_args),
    },
    HARRIS_RECORDER_SOURCE_ID: {
        "instrument": _LiveRoute(
            query_harris_recorder,
            "search",
            _harris_recorder_args,
        ),
    },
    HARRIS_FORECLOSURE_SOURCE_ID: {
        "search": _LiveRoute(
            query_harris_foreclosures,
            "search",
            _harris_foreclosure_args,
        ),
    },
    **{
        source_id: {
            **{
                operation: _LiveRoute(
                    WASHINGTON_PARCEL_ADAPTER,
                    "search",
                    _washington_parcel_args,
                )
                for operation in ("search", "address", "parcel", "map")
            },
            **{
                operation: _LiveRoute(
                    WASHINGTON_PARCEL_ADAPTER,
                    operation,
                    _washington_parcel_args,
                )
                for operation in ("count", "point", "bbox", "probe")
            },
        }
        for source_id in WASHINGTON_PARCEL_REPRESENTATION_SOURCE_IDS
    },
    WASHINGTON_PARCEL_FRESHNESS_SOURCE_ID: {
        operation: _LiveRoute(
            WASHINGTON_PARCEL_ADAPTER,
            "county-freshness",
            _washington_parcel_args,
        )
        for operation in ("search", "freshness")
    },
    WASHINGTON_PARCEL_LAND_USE_SOURCE_ID: {
        operation: _LiveRoute(
            WASHINGTON_PARCEL_ADAPTER,
            "land-use-codes",
            _washington_parcel_args,
        )
        for operation in ("search", "land-use")
    },
    WASHINGTON_PARCEL_LINEAGE_SOURCE_ID: {
        "search": _LiveRoute(
            WASHINGTON_PARCEL_ADAPTER,
            "metadata",
            _washington_parcel_args,
        ),
        "parity": _LiveRoute(
            WASHINGTON_PARCEL_ADAPTER,
            "parity",
            _washington_parcel_args,
        ),
        "probe": _LiveRoute(
            WASHINGTON_PARCEL_ADAPTER,
            "probe",
            _washington_parcel_args,
        ),
    },
    query_dc_property.ITSPE_SOURCE_ID: {
        operation: _LiveRoute(
            query_dc_property,
            "assessment",
            _dc_property_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "account",
            "parcel",
            "instrument",
        )
    }
    | {
        operation: _LiveRoute(
            query_dc_property,
            operation,
            _dc_property_args,
        )
        for operation in ("count", "probe")
    },
    query_dc_property.OWNER_POLYGON_SOURCE_ID: {
        operation: _LiveRoute(
            query_dc_property,
            "geometry",
            _dc_property_args,
        )
        for operation in (
            "search",
            "owner",
            "address",
            "parcel",
            "instrument",
            "map",
        )
    }
    | {
        operation: _LiveRoute(
            query_dc_property,
            operation,
            _dc_property_args,
        )
        for operation in ("count", "point", "bbox", "probe")
    },
    query_dc_property.SALES_SOURCE_ID: {
        operation: _LiveRoute(
            query_dc_property,
            "sales",
            _dc_property_args,
        )
        for operation in ("search", "parcel", "sale", "event")
    }
    | {
        operation: _LiveRoute(
            query_dc_property,
            operation,
            _dc_property_args,
        )
        for operation in ("count", "probe")
    },
    query_dc_property.SURVEY_SOURCE_ID: {
        operation: _LiveRoute(
            query_dc_property,
            "surveys",
            _dc_property_args,
        )
        for operation in ("search", "parcel", "survey")
    }
    | {
        operation: _LiveRoute(
            query_dc_property,
            operation,
            _dc_property_args,
        )
        for operation in ("count", "probe")
    },
}

DIRECT_TOOL_GUIDANCE: dict[str, dict[str, Any]] = {
    LOS_ANGELES_ASSESSOR_SOURCE_ID: {
        "mode": "unified_exact_parcel_route",
        "direct_tool": ("uv run python tools/query_los_angeles_ttc.py route --help"),
        "native_key": "AIN",
        "official_complements": [
            LOS_ANGELES_TTC_PAYMENT_SOURCE_ID,
            LOS_ANGELES_TTC_SALE_SOURCE_ID,
            "us-ca-los-angeles-registrar-recorder-real-estate",
        ],
        "note": (
            "The shared parcel/account route verifies one exact AIN against "
            "the Assessor parcel layer. Payment, tax-sale, and recorded-title "
            "facts remain separately attributable sources joined by AIN or "
            "recorded instrument identifiers."
        ),
    },
    LOS_ANGELES_TTC_PAYMENT_SOURCE_ID: {
        "mode": "unified_exact_payment_history",
        "direct_tool": ("uv run python tools/query_los_angeles_ttc.py history --help"),
        "native_key": "AIN",
        "pagination": (
            "Omitted shared --limit follows every source-reported page; an "
            "explicit shared --limit is a native-page bound with a cursor."
        ),
        "official_complements": [
            {
                "name": "Annual Secured Property Tax Bill",
                "url": query_los_angeles_ttc.ANNUAL_BILL_URL,
                "adds": ["current_bill", "current_tax_information"],
            },
            {
                "name": "View or request a property tax bill",
                "url": query_los_angeles_ttc.TAX_BILL_URL,
                "adds": ["duplicate_bill", "bill_request"],
            },
            {
                "name": "Secured Property Tax Information Request",
                "url": query_los_angeles_ttc.MULTIPLE_PARCELS_URL,
                "adds": ["multi_parcel_tax_information"],
            },
        ],
        "note": (
            "Payment rows are official historical transactions. Current "
            "balance, bill, tax-default, and recorded-title questions use the "
            "listed official complements."
        ),
    },
    LOS_ANGELES_TTC_SALE_SOURCE_ID: {
        "mode": "unified_tax_sale_publications",
        "direct_tool": ("uv run python tools/query_los_angeles_ttc.py --help"),
        "native_keys": ["auction_cycle", "sale_phase", "item", "AIN"],
        "official_complements": [
            {
                "name": "Notice of Auction or Sale",
                "url": query_los_angeles_ttc.AUCTION_NOTICE_URL,
                "adds": [
                    "individual_tax_default_status",
                    "redemption_or_removal_information",
                ],
            },
            {
                "name": "Notice of Excess Proceeds",
                "url": query_los_angeles_ttc.EXCESS_PROCEEDS_URL,
                "adds": ["claim_instructions", "published_notices"],
            },
        ],
        "note": (
            "Unified event returns the current source-published auction "
            "schedule, search lists indexed publication artifacts by cycle, "
            "and sale extracts parcel, purchase-price, phase, and excess-"
            "proceeds rows from one official result PDF."
        ),
    },
    PHILADELPHIA_OPA_SOURCE_ID: {
        "mode": "unified_live_current_assessment",
        "direct_tool": ("uv run python tools/query_philadelphia_property.py --help"),
        "native_keys": [
            "parcel_number",
            "registry_number",
            "pin",
            "objectid",
        ],
        "direct_default": "all_matching_objectid_keyset_pages",
        "same_dataset_transports": [
            query_philadelphia_property.OPA_CURRENT_CSV_URL,
            query_philadelphia_property.OPA_CARTO_GEOJSON_URL,
        ],
        "official_complements": [
            PHILADELPHIA_HISTORY_SOURCE_ID,
            PHILADELPHIA_DOR_SOURCE_ID,
            query_philadelphia_property.ATLAS_SOURCE_ID,
            query_philadelphia_property.PHILADOX_SOURCE_ID,
            query_philadelphia_property.RECORDS_SOURCE_ID,
        ],
        "note": (
            "Current OPA rows include assessment-owner observations, situs "
            "and mailing fields, values, characteristics, last-sale and deed "
            "references, and optional point geometry. Omitted caller limits "
            "exhaust the count-checked keyset traversal. The nightly CSV and "
            "CARTO current table are alternate transports for the same OPA "
            "dataset, not independent corroboration."
        ),
    },
    PHILADELPHIA_HISTORY_SOURCE_ID: {
        "mode": "unified_live_assessment_history",
        "direct_tool": (
            "uv run python tools/query_philadelphia_property.py history --help"
        ),
        "native_key": "OPA parcel number",
        "direct_default": "all_annual_rows",
        "bulk_complement": (query_philadelphia_property.OPA_HISTORY_CSV_URL),
        "note": (
            "The history table preserves every source assessment-year label "
            "and remains separately attributable from the current OPA row "
            "while joining through parcel_number. --tax-year selects one "
            "source year; omitted limits traverse every matching row."
        ),
    },
    PHILADELPHIA_DOR_SOURCE_ID: {
        "mode": "unified_live_deed_description_geometry",
        "direct_tool": (
            "uv run python tools/query_philadelphia_property.py parcel-shape --help"
        ),
        "native_keys": ["mapreg", "basereg", "pin", "objectid"],
        "direct_default": "all_matching_objectid_keyset_pages",
        "note": (
            "The Department of Records polygon is a separate weekly map "
            "observation derived from recorded deed descriptions. It joins "
            "to OPA through registry_number/mapreg or PIN; Philadox and the "
            "Department of Records/City Archives routes provide the "
            "underlying and historical instruments."
        ),
    },
    MICHIGAN_PROPERTY_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_county_property_source_discovery",
        "direct_tool": (
            "uv run python tools/query_michigan_property_directories.py --help"
        ),
        "native_keys": [
            "Michigan county GEOID",
            "published county route URL",
            "platform family",
        ],
        "shared_selectors": {
            "search": ("text, county, platform, platform summary, or discovery"),
            "discovery": "text, county, or platform",
            "probe": "statewide 83-county directory contract",
        },
        "official_complements": (query_michigan_property_directories._alternatives()),
        "note": (
            "DTMB publishes county parcel-layer routes because its statewide "
            "parcel layer is not in the open-data portal. Directory-publisher "
            "role evidence remains separate from capabilities verified at "
            "each destination. Results are discovery metadata, not parcels, "
            "assessment rolls, tax ledgers, ownership assertions, or title "
            "records; destination mismatches such as the current Genesee "
            "Register of Deeds route remain explicit."
        ),
    },
    MICHIGAN_EATON_PARCELS_SOURCE_ID: {
        "mode": "unified_local_search_of_official_county_bulk_snapshot",
        "direct_tool": ("uv run python tools/query_michigan_eaton_parcels.py --help"),
        "native_keys": [
            "LPARCEL",
            "PARCELID",
            "LOWPARCELI",
            "DBF physical record index within an artifact digest",
        ],
        "shared_selectors": {
            "search": "any current DBF search field",
            "owner": "OWNERNME1 or OWNERNME2 snapshot value",
            "address": "SITEADDRES snapshot value",
            "account_or_parcel": "punctuation-insensitive exact parcel ID",
            "map": "parcel row plus bulk geometry artifact reference",
            "freshness": "live ArcGIS item metadata",
            "probe": "live item identity and bounded ZIP signature",
        },
        "bulk_workflow": {
            "download": (
                "uv run python tools/query_michigan_eaton_parcels.py download --help"
            ),
            "shared_artifact_selector": "--artifact-path FILE",
            "snapshot_join": "artifact SHA-256 plus DBF physical row index",
        },
        "official_complements": (query_michigan_eaton_parcels._alternative_records()),
        "note": (
            "Eaton County publishes a downloadable parcel shapefile snapshot. "
            "The ArcGIS description declares geometry, a parcel identifier, "
            "and a current-information URL; the adapter separately inspects "
            "the downloaded DBF and currently verifies situs, assessment-roll "
            "owner-name, assessed-value, taxable-value, classification, and "
            "BSA detail-link fields. Assessment year is left unset because "
            "the current DBF does not declare one. BSA remains the "
            "record-specific current-detail complement."
        ),
    },
    GEORGIA_PROPERTY_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_county_property_source_discovery",
        "direct_tool": ("uv run python tools/query_georgia_property_sources.py --help"),
        "native_keys": [
            "Georgia county GEOID",
            "published county route URL",
            "destination platform family",
        ],
        "shared_selectors": {
            "search": "text, county, platform, or platform summary",
            "discovery": "text, county, or platform",
            "probe": "statewide directory coverage and anomaly sentinel",
        },
        "official_complements": [GEORGIA_GSCCCA_SOURCE_ID],
        "note": (
            "The Georgia Department of Revenue directory is a statewide "
            "launchpad for county assessment and tax systems. Its rows are "
            "source-routing observations rather than parcels, assessment "
            "rolls, ownership assertions, or title records. Published "
            "missing counties and disagreements between a row's two links "
            "remain explicit."
        ),
    },
    GEORGIA_GSCCCA_SOURCE_ID: {
        "mode": "unified_verified_acquisition_handoff",
        "direct_tool": (
            "uv run python tools/query_georgia_property_sources.py handoff --help"
        ),
        "native_keys": [
            "statewide index identity",
            "official search route",
            "official login handoff",
        ],
        "shared_selectors": {
            "discovery": "statewide account and index-coverage handoff",
            "probe": "coverage, account, and login-route sentinel",
        },
        "official_complements": [GEORGIA_PROPERTY_DIRECTORY_SOURCE_ID],
        "note": (
            "GSCCCA provides the statewide deed, lien, and plat index. The "
            "shared route preserves verified coverage and the no-cost "
            "limited-use summary-search account path; it does not represent "
            "that handoff as a completed party or instrument search. County "
            "assessor systems and Superior Court clerk records provide "
            "separately attributable complements."
        ),
    },
    VIRGINIA_BEACH_DELINQUENT_TAX_SOURCE_ID: {
        "mode": "unified_live_current_tax_delinquency_installments",
        "direct_tool": (
            "uv run python tools/query_va_beach_delinquent_tax.py --help"
        ),
        "record_identity": [
            "bill_number",
            "installment",
            "GPIN",
            "tax_year",
        ],
        "parcel_join": "GPIN within Virginia Beach GEOID 51810",
        "shared_selectors": {
            "search": "any published installment field",
            "owner": "published primary-owner observation",
            "address": "situs or mailing-address observation",
            "parcel": "exact GPIN",
            "event": "exact tax bill number, returning its installment rows",
            "probe": "item identity, schema, count, and one bounded row",
            "discovery": "official complementary routes and join keys",
        },
        "direct_filters": [
            "tax year",
            "installment",
            "district",
            "minimum total due",
            "maximum total due",
        ],
        "official_complements": [
            dict(route)
            for route in query_va_beach_delinquent_tax.RELATED_ROUTES
            if route.get("source_id")
            != VIRGINIA_BEACH_DELINQUENT_TAX_SOURCE_ID
        ],
        "note": (
            "Each row is one current delinquent bill installment. The "
            "bill/installment/GPIN/tax-year occurrence key remains separate "
            "from the GPIN parcel join. Owner and mailing values are "
            "Treasurer tax-account observations; the assessor, detailed tax "
            "inquiry, Circuit Court land records, Virginia court indexes, "
            "and Treasurer sale notices add separately attributable detail."
        ),
    },
    VIRGINIA_VGIN_PARCELS_SOURCE_ID: {
        "mode": "unified_live_statewide_parcel_discovery_geometry",
        "direct_tool": ("uv run python tools/query_virginia_parcels.py --help"),
        "native_keys": [
            "VGIN_QPID",
            "OBJECTID",
            "FIPS plus PARCELID",
            "FIPS plus PTM_ID",
        ],
        "direct_default": "all_matching_objectid_keyset_pages",
        "official_complements": query_virginia_parcels._alternative_routes(),
        "note": (
            "The official ArcGIS item resolves the current VGIN service. "
            "VGIN_QPID is the durable statewide key and OBJECTID is a "
            "release-scoped transport locator. The layer supplies parcel "
            "geometry and locality identifiers rather than owner, assessment, "
            "tax, or recorded-instrument detail. Local update dates and "
            "county-equivalent coverage remain explicit; use locality "
            "assessment systems and Circuit Court land records for richer "
            "evidence."
        ),
    },
    WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID: {
        "mode": "unified_live_statewide_annual_parcels",
        "direct_tool": ("uv run python tools/query_wisconsin_parcels.py --help"),
        "native_keys": [
            "STATEID",
            "PARCELID",
            "TAXPARCELID",
            "OBJECTID",
        ],
        "direct_default": "all_matching_objectid_keyset_pages",
        "official_complements": query_wisconsin_parcels._alternatives(),
        "note": (
            "The annual statewide layer aggregates county submissions and "
            "keeps published, withheld, partially withheld, and absent owner "
            "states distinct. Known non-parcel map labels remain source "
            "observations rather than parcels. County systems add current "
            "local detail and recorded instruments; DOR RETR adds transfer "
            "returns. Same-release downloads are transport redundancy, not "
            "independent corroboration."
        ),
    },
    WYOMING_DOR_STATEWIDE_PARCELS_SOURCE_ID: {
        "mode": "unified_live_statewide_annual_tax_roll_and_parcel_occurrences",
        "direct_tool": "uv run python tools/query_wy_dor_parcels.py --help",
        "annual_identity_bases": [
            "tax year + jurisdiction + parcel + account",
            "tax year + jurisdiction + specific parcel",
            "tax year + jurisdiction + account",
        ],
        "occurrence_identity": "release-scoped FID",
        "direct_default": "all_matching_ordered_FID_offset_pages",
        "shared_selectors": {
            "owner": "annual tax-roll owner observation",
            "parcel": "parcel number",
            "account": "county property account number",
            "county": "county annual occurrence inventory",
            "jurisdiction": "county annual occurrence inventory",
            "address": "situs/location address",
            "situs": "situs/location address",
            "mailing": "owner mailing fields",
            "legal": "legal-description text",
            "fid": "one release feature occurrence",
            "map": "parcel-number lookup with WGS84 geometry",
            "geometry": "one FID's WGS84 geometry",
            "point": "WGS84 point intersection",
            "bbox": "WGS84 envelope intersection",
            "discovery": "root app, layer, county, identity, and route contracts",
            "probe": "fixed app/layer/exact-parcel sentinel",
        },
        "official_complements": query_wy_dor_parcels.source_routes(),
        "note": (
            "The DOR layer joins annual county tax-roll context to parcel "
            "geometry. A business-key tuple can repeat across several FIDs, "
            "so every feature occurrence remains evidence while eligible "
            "rows share one annual parcel join. Owner names are assessment-"
            "roll observations; county clerk instruments remain the title-"
            "event source. The DOR assessment download is the same-publisher "
            "annual lineage, not independent corroboration."
        ),
    },
    **{
        tenant.source_id: {
            "mode": "unified_live_county_sheriff_sale_events",
            "direct_tool": (
                "uv run python tools/query_ohio_sheriff_sales.py --help"
            ),
            "county_geoid": tenant.county_geoid,
            "native_identity": "county tenant plus RealAuction AID",
            "same_event_join": ["case_number", "parcel_ids", "auction_date"],
            "shared_selectors": {
                "search": (
                    "case, parcel, or address on one exact --from-date"
                ),
                "address": "address text on one exact --from-date",
                "parcel": "parcel text on one exact --from-date",
                "sale": "one exact auction date",
                "event": "exact AID on one exact --from-date",
                "freshness": "one YYYY-MM public auction calendar",
                "discovery": "tenant contract and official complements",
                "probe": "fixed county sentinel or caller-selected date",
            },
            "official_complements": [
                dict(value) for value in tenant.alternatives
            ],
            "note": (
                "A sheriff-sale row is a scheduled or completed auction "
                "observation, not proof of court confirmation, a recorded "
                "sheriff deed, or completed title transfer. Case, parcel, and "
                "date support cross-source matching but do not replace the "
                "tenant-scoped AID identity."
            ),
        }
        for tenant in query_ohio_sheriff_sales.TENANTS.values()
    },
    OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID: {
        "mode": "unified_live_county_foreclosure_archive",
        "direct_tool": (
            "uv run python tools/query_licking_foreclosure_archive.py --help"
        ),
        "county_geoid": query_licking_foreclosure_archive.COUNTY_GEOID,
        "native_identity": "Licking County archive case number",
        "same_event_join": ["case_number", "parcel_ids", "sale_date"],
        "independent_corroboration_from_realauction": False,
        "shared_selectors": {
            "search": (
                "case, parcel, address, status, sale type, or purchaser "
                "within one selected year"
            ),
            "address": "address text within one selected year",
            "parcel": "parcel text within one selected year",
            "sale": "one complete four-digit archive year",
            "event": "one exact archive case number",
            "releases": "complete official sale-year inventory",
            "discovery": "archive contract, fields, gaps, and complements",
            "probe": "fixed four-route archive sentinel",
        },
        "official_complements": (
            query_licking_foreclosure_archive._source_record()[
                "official_complements"
            ]
        ),
        "note": (
            "The archive preserves county-reported status, purchaser, deed-as, "
            "and price fields as auction outcome observations. They do not "
            "establish court confirmation, a recorded deed, current ownership, "
            "or title transfer. A case/parcel/date match to RealAuction is a "
            "same-event candidate, not independent corroboration."
        ),
    },
    OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID: {
        "mode": "unified_bulk_release_and_local_row_search",
        "direct_tool": (
            "uv run python tools/query_ohio_franklin_auditor_bulk.py --help"
        ),
        "county_geoid": query_ohio_franklin_auditor_bulk.COUNTY_GEOID,
        "families": list(query_ohio_franklin_auditor_bulk.FAMILY_CHOICES),
        "record_families": list(
            query_ohio_franklin_auditor_bulk.RECORD_FAMILY_CHOICES
        ),
        "shared_selectors": {
            "discovery": "source contract, or families as the selector",
            "releases": (
                "--dataset-type plus current, all, or a four-digit year"
            ),
            "manifest": (
                "--dataset-type plus a release in --collection-id or selector"
            ),
            "probe": (
                "source health, or one artifact selected with --dataset-type, "
                "--collection-id, and its filename or ID"
            ),
            "download": (
                "one artifact selected by dataset family and release, with "
                "--destination"
            ),
            "search": (
                "local artifact rows using --artifact-path, a row family in "
                "--dataset-type, and release identity in --collection-id"
            ),
            "parcel": "exact parcel join within one selected local artifact",
        },
        "native_operations": {
            "inspect-local": "header, worksheet, and ZIP-member inspection",
            "rows": (
                "archive-member and worksheet selection plus explicit release "
                "date and artifact source URL"
            ),
        },
        "identity": {
            "release": (
                "publisher family plus source release directory or filename date"
            ),
            "artifact": "official relative path",
            "artifact_version": (
                "source metadata plus computed SHA-256 after download"
            ),
            "row_occurrence": (
                "release, artifact SHA-256, archive member and worksheet when "
                "applicable, and physical row"
            ),
        },
        "official_complements": [
            {
                "source_id": "us-oh-franklin-county-auditor-property",
                "relationship": "same_authority_interactive_representation",
                "independent_corroboration": False,
            },
            {
                "source_id": OHIO_FRANKLIN_SALES_GIS_SOURCE_ID,
                "relationship": "same_authority_structured_sales_representation",
                "independent_corroboration": False,
            },
            {
                "source_id": OHIO_STATEWIDE_PARCELS_SOURCE_ID,
                "relationship": (
                    "statewide_county_contributed_parcel_representation"
                ),
                "independent_corroboration": False,
            },
            {
                "source_id": "us-oh-franklin-county-recorder-publicsearch",
                "relationship": "distinct_recorded_instrument_domain",
                "distinct_record_domain": True,
                "corroboration_requires_exact_record_match": True,
            },
        ],
        "note": (
            "Appraisal, tax-accounting, conveyance, parcel CSV, and GIS files "
            "remain separately attributable Auditor components. Overlapping "
            "rows from those files are same-authority representations, while "
            "Recorder instruments supply a distinct record domain."
        ),
    },
    OHIO_FRANKLIN_SALES_GIS_SOURCE_ID: {
        "mode": "unified_live_county_auditor_sale_occurrences",
        "direct_tool": (
            "uv run python tools/query_ohio_franklin_sales_gis.py --help"
        ),
        "county_geoid": query_ohio_franklin_sales_gis.COUNTY_GEOID,
        "native_keys": [
            "GlobalID feature occurrence",
            "service item, layer, and OBJECTID occurrence fallback",
            "ConveyanceNum plus PARCELID business event",
        ],
        "direct_default": "all_matching_OBJECTID_keyset_pages",
        "shared_selectors": {
            "search": (
                "all fields, or party, parcel, conveyance, address, fid, "
                "validity, or date through --search-field"
            ),
            "owner": "grantor/grantee transaction-party observations",
            "address": "site address, ZIP, and subdivision/condominium text",
            "parcel": "exact PARCELID",
            "map": "exact PARCELID with sale-location point",
            "fid": "exact OBJECTID feature occurrence",
            "geometry": "exact OBJECTID with sale-location point",
            "sale": (
                "inclusive --from-date/--to-date bounds or one exact date"
            ),
            "instrument": "exact Auditor ConveyanceNum",
            "count": "complete canonical layer count",
            "freshness": "live canonical layer schema and metadata",
            "discovery": "source contract, or layers as the selector",
            "probe": "ten-request schema, identity, coverage, and sentinel check",
        },
        "qualification": (
            "ValidSale remains the Auditor's raw qualification and does not "
            "erase a dated positive-price transaction observation"
        ),
        "official_complements": [
            {
                "source_id": OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
                "relationship": "same_authority_release_representation",
                "independent_corroboration": False,
            },
            {
                "source_id": "us-oh-franklin-county-auditor-property",
                "relationship": "same_authority_interactive_representation",
                "independent_corroboration": False,
            },
            {
                "source_id": OHIO_STATEWIDE_PARCELS_SOURCE_ID,
                "relationship": "county_origin_statewide_representation",
                "independent_corroboration": False,
            },
            {
                "source_id": "us-oh-franklin-county-recorder-publicsearch",
                "relationship": "distinct_recorded_instrument_domain",
                "distinct_record_domain": True,
                "corroboration_requires_exact_record_match": True,
            },
        ],
        "note": (
            "GlobalID identifies each published sale feature. ConveyanceNum "
            "plus PARCELID is the separate business event; grantor/grantee "
            "values are transaction parties rather than current-owner claims. "
            "Layers 1-4 are renderer aliases of canonical layer 0."
        ),
    },
    query_ohio_pax_recorders.DELAWARE_SOURCE_ID: {
        "mode": "unified_live_county_recorded_instruments",
        "direct_tool": (
            "uv run python tools/query_ohio_pax_recorders.py --help"
        ),
        "native_keys": [
            "InstrumentReferenceId",
            "instrument number",
            "book/page locator",
        ],
        "direct_default": "all_source_reported_instruments",
        "shared_selectors": {
            "search": (
                "party name, grantor, grantee, instrument number, "
                "book/page, document ID, or recording date"
            ),
            "instrument": (
                "exact instrument detail and public-image availability"
            ),
            "download": "exact official public PDF to --destination",
            "probe": (
                "guest bootstrap, exact reference, image metadata, and PDF"
            ),
        },
        "official_complements": [
            dict(value) for value in query_ohio_pax_recorders.DELAWARE.complements
        ],
        "note": (
            "Delaware PAX is anonymous after its public disclaimer. Native "
            "InstrumentReferenceId is the recorded-instrument identity; "
            "instrument number and book/page remain locators. Recorder parties "
            "and images are recorded-instrument evidence, not conclusions "
            "about current title or beneficial ownership."
        ),
    },
    query_ohio_pax_recorders.LICKING_SOURCE_ID: {
        "mode": "registered_account_discovery_route",
        "direct_tool": (
            "uv run python tools/query_ohio_pax_recorders.py --help"
        ),
        "native_keys": ["instrument number"],
        "shared_selectors": {
            "search": (
                "account-gated party, date, instrument, book/page, and "
                "document-ID discovery"
            ),
            "probe": "published PAX login requirement and component contract",
        },
        "official_complements": [
            dict(value) for value in query_ohio_pax_recorders.LICKING.complements
        ],
        "note": (
            "Licking PAX discovery requires an account. Known instruments use "
            "the county's separate anonymous exact-detail component, and the "
            "Records & Archives route covers historical deed and mortgage "
            "holdings. These are different access representations and roles, "
            "not duplicate corroboration."
        ),
    },
    OHIO_LICKING_RECORDER_DETAIL_SOURCE_ID: {
        "mode": "unified_live_exact_instrument_representation",
        "direct_tool": (
            "uv run python tools/query_ohio_pax_recorders.py --help"
        ),
        "native_keys": ["instrument number"],
        "record_identity_source_id": (
            query_ohio_pax_recorders.LICKING_SOURCE_ID
        ),
        "independent_corroboration": False,
        "shared_selectors": {
            "instrument": "exact known instrument number",
            "download": "exact official public PDF to --destination",
            "probe": "exact HTML fields and PDF representation",
        },
        "note": (
            "The anonymous Licking HTML/PDF route is an alternate "
            "representation of the same recorder instrument identity used by "
            "PAX. Ingestion deduplicates on the PAX identity source plus "
            "instrument number while retaining the representation provenance."
        ),
    },
    OHIO_LICKING_AUDITOR_GIS_SOURCE_ID: {
        "mode": "unified_live_county_assessor_parcels",
        "direct_tool": (
            "uv run python tools/query_ohio_licking_property.py --help"
        ),
        "county_geoid": query_ohio_licking_property.COUNTY_GEOID,
        "native_keys": [
            "GlobalID or OBJECTID feature occurrence",
            "Parcel business join candidate",
        ],
        "direct_default": "all_matching_objectid_keyset_pages",
        "shared_selectors": {
            "search": "assessment-owner by default, or an explicit field",
            "owner": "assessment-roll owner-name observation",
            "address": "published situs-address components",
            "situs": "published situs-address components",
            "mailing": "published owner-mailing-address components",
            "parcel": "exact Auditor parcel number",
            "map": "exact parcel with its county GIS polygon",
            "fid": "exact OBJECTID feature occurrence",
            "geometry": "exact OBJECTID with its county GIS polygon",
            "legal": "legal-description text",
            "land-use": "land-use label",
            "instrument": "Auditor-published instrument reference",
            "freshness": "live layer metadata and schema",
            "discovery": "source, identity, lineage, and field contract",
            "probe": "schema, counts, null-key state, and exact sentinel",
        },
        "official_complements": [
            {
                "source_id": "us-oh-licking-county-auditor-ontrac",
                "record_role": "same_authority_interactive_property_detail",
                "relationship": "same_authority_assessment_route",
                "independent_corroboration": False,
            },
            {
                "source_id": query_ohio_statewide_parcels.SOURCE_ID,
                "record_role": "statewide standardized parcel context",
                "relationship": "county_origin_statewide_representation",
                "independent_corroboration": False,
            },
            {
                "source_id": query_ohio_pax_recorders.LICKING_SOURCE_ID,
                "record_role": "recorder instrument discovery",
                "relationship": "distinct_recorded_instrument_domain",
                "distinct_record_domain": True,
                "corroboration_requires_exact_record_match": True,
            },
            {
                "source_id": OHIO_LICKING_RECORDER_DETAIL_SOURCE_ID,
                "record_role": "anonymous exact instrument detail and PDF",
                "relationship": "same_recorder_instrument_representation",
                "independent_corroboration": False,
            },
            {
                "source_id": "us-oh-licking-sheriff-realauction",
                "record_role": "sheriff sale auction events",
                "relationship": "distinct_foreclosure_event_domain",
                "distinct_record_domain": True,
                "corroboration_requires_exact_record_match": True,
            },
            {
                "source_id": OHIO_LICKING_FORECLOSURE_ARCHIVE_SOURCE_ID,
                "record_role": "foreclosure sale archive",
                "relationship": "distinct_foreclosure_event_domain",
                "distinct_record_domain": True,
                "corroboration_requires_exact_record_match": True,
            },
        ],
        "note": (
            "The layer publishes assessor owner, value, address, recent-"
            "transfer, building, and polygon observations. GlobalID or "
            "OBJECTID identifies the feature occurrence; Parcel is the "
            "business join. Recorder instruments remain the title source, "
            "and the county layer overlaps the Auditor-derived OGRIP view."
        ),
    },
    OHIO_STATEWIDE_PARCELS_SOURCE_ID: {
        "mode": "unified_live_statewide_standardized_parcels",
        "direct_tool": (
            "uv run python tools/query_ohio_statewide_parcels.py --help"
        ),
        "native_keys": [
            "StateParcelID",
            "County plus LocalParcelID",
            "GlobalID",
            "OBJECTID",
        ],
        "direct_default": "all_matching_objectid_keyset_pages",
        "shared_selectors": {
            "search": "parcel, address, mailing, or state land-use field",
            "address": "situs-address observation",
            "parcel": "state or local parcel identifier",
            "map": "parcel lookup with county-contributed polygon",
            "land-use": "state land-use code",
            "count": "statewide or county inventory",
            "freshness": "service metadata and schema observation",
            "discovery": "field-oriented county source graph",
            "probe": "schema, 88-county inventory, and target-county sentinels",
        },
        "official_complements": (
            query_ohio_statewide_parcels.SOURCE_GRAPH["counties"]
        ),
        "process_learnings": (
            query_ohio_statewide_parcels.SOURCE_GRAPH["process_learnings"]
        ),
        "note": (
            "OGRIP supplies standardized parcel identifiers, situs and mailing "
            "observations, state land-use codes, area, local CAMA routes, and "
            "county-contributed geometry. County assessor systems supply owner "
            "and value observations; county recorders supply instruments and "
            "document images. Service-edit metadata and row-level CurrentTo "
            "dates remain separate freshness signals."
        ),
    },
    NEW_JERSEY_DCA_PROPERTY_SOURCE_ID: {
        "mode": "unified_live_building_registration_index",
        "direct_tool": ("uv run python tools/query_new_jersey_dca_property.py --help"),
        "native_keys": [
            "13-digit building registration",
            "10-digit property registration",
            "building locator GUID",
            "property-interest locator GUID",
        ],
        "shared_selectors": {
            "account": "property or building registration",
            "address": "partial primary or AKA address",
            "parcel": "BLOCK/LOT plus a county selector",
            "search": (
                "auto, registration, address, municipality, county, "
                "block-lot, block, or lot"
            ),
        },
        "official_complements": (
            query_new_jersey_dca_property.alternative_route_records()
        ),
        "note": (
            "DCA rows describe regulatory building registrations. A "
            "registered-owner relationship is retained as agency-registration "
            "context, not deed title. NJGIN/MOD-IV supplies parcel and "
            "assessment context; SR1A and county clerk records supply transfer "
            "and recorded-instrument evidence; the official BHI Active "
            "Building report and OPRA routes add fields absent from the index."
        ),
    },
    NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID: {
        "mode": "unified_live_statewide_parcel_modiv_composite",
        "direct_tool": ("uv run python tools/query_new_jersey_parcels.py --help"),
        "native_keys": [
            "PAMS_PIN",
            "PIN_NODUP",
            "GIS_PIN",
            "municipality/block/lot/qualifier",
            "OBJECTID",
        ],
        "direct_default": "all_matching_objectid_keyset_pages",
        "official_complements": (query_new_jersey_parcels._alternative_routes()),
        "note": (
            "NJGIN joins parcel geometry to MOD-IV where a match exists and "
            "preserves parcel-only rows when it does not. Hosted owner names "
            "are source-redacted. Treasury MOD-IV and SR1A files, local "
            "assessors, county tax boards, and recorded instruments supply "
            "separately attributable assessment, transaction, title, and "
            "historical detail."
        ),
    },
    NEW_JERSEY_SR1A_SOURCE_ID: {
        "mode": "unified_live_statewide_sale_release",
        "direct_tool": ("uv run python tools/query_new_jersey_sr1a.py --help"),
        "native_search_fields": [
            "any",
            "grantor",
            "grantee",
            "party",
            "property-address",
            "deed",
            "block-lot",
        ],
        "record_identity": [
            "municipality_code",
            "serial_number",
            "deed_book",
            "deed_page",
            "recording_date",
        ],
        "release_occurrence_identity": [
            "release_id",
            "archive_sha256",
            "archive_member",
            "row_number",
            "record_sha256",
        ],
        "official_complements": query_new_jersey_sr1a._alternative_routes(),
        "note": (
            "SR1A contributes statewide grantor/grantee, price, transfer-fee, "
            "deed-reference, parcel-coordinate, and assessment-at-sale "
            "observations. Year-to-date and annual files are occurrences of "
            "one publisher record lineage. NJGIN supplies parcel geometry, "
            "county instruments supply document-level title evidence, and "
            "local assessment and Tax Court routes supply valuation context."
        ),
    },
    NEW_YORK_STATEWIDE_PARCELS_SOURCE_ID: {
        "mode": "unified_live_multi_component_statewide_parcels",
        "direct_tool": ("uv run python tools/query_ny_statewide_parcels.py --help"),
        "components": {
            "centroids": (
                "all-county assessment, owner, address, identifier, and centroid index"
            ),
            "public-parcels": ("public parcel polygons for participating counties"),
            "state-owned": ("statewide state-owned subset with agency attribution"),
        },
        "native_keys": [
            "SWIS_SBL_ID",
            "SWIS_PRINT_KEY_ID",
            "MUNI_PARCEL_ID",
            "SWIS",
            "SBL",
            "PRINT_KEY",
            "OBJECTID",
        ],
        "direct_default": "all_matching_objectid_keyset_pages",
        "official_complements": (query_ny_statewide_parcels.alternative_routes()),
        "note": (
            "The statewide centroid component covers all 62 counties. Public "
            "parcel polygons cover participating counties, and the separate "
            "state-owned component adds agency attribution. Exact SWIS-based "
            "keys join the components; county systems, ORPTS SalesWeb, ACRIS, "
            "and OGS land records add fresher local, transfer, instrument, "
            "and historical state-land detail."
        ),
    },
    NYC_PIP_SOURCE_ID: {
        "mode": "unified_live_nyc_dof_arcgis_layer_family",
        "direct_tool": "uv run python tools/query_nyc_pip.py --help",
        "durable_parcel_identity": "ten_digit_bbl",
        "occurrence_identity": "layer_key_plus_bbl_plus_objectid",
        "shared_selectors": {
            "parcel": "ten-digit BBL or BOROUGH/BLOCK/LOT",
            "owner": "DOF tax-roll owner observation",
            "address": "parcel-detail situs address",
            "detail": "parcel and building detail by BBL",
            "map": "tax-lot polygon by BBL",
            "assessment": "current PROPMAST assessment by BBL",
            "history": "PROPMAST_HIST rows by BBL",
            "exemptions": "EXDET rows by BBL",
            "discovery": "layer, metadata, and recording-route manifests",
            "probe": "fixed exact five-component sentinel",
        },
        "default_pagination": (
            "exhaust native ArcGIS pages unless the caller selects a window"
        ),
        "official_complements": query_nyc_pip.source_routes()[
            "recording_routes"
        ],
        "note": (
            "BBL joins five separately attributable layer grains. PIP's "
            "recent ACRIS display is the same recording lineage; complete "
            "ACRIS and Richmond Clerk results are field-matched recorder "
            "routes rather than duplicate corroboration of a displayed event."
        ),
    },
    NEW_YORK_SALESWEB_SOURCE_ID: {
        "mode": "unified_live_statewide_transfer_index",
        "direct_tool": ("uv run python tools/query_ny_salesweb.py --help"),
        "record_identity": "saleTranNmbr",
        "parcel_join": "swisCd + printKey -> SWIS_PRINT_KEY_ID",
        "native_search_fields": [
            "buyer",
            "seller",
            "address",
            "tax-map",
            "book-page",
            "sale-id",
        ],
        "direct_default": "100_matching_rows_or_explicit_all",
        "official_complements": query_ny_salesweb.alternative_routes(),
        "note": (
            "SalesWeb is a weekly updated rolling ten-year RP-5217 transfer "
            "index outside New York City. The sale transaction number remains "
            "separate from parcel identity; the published SWIS and print key "
            "join exactly to the statewide parcel index. ACRIS, Richmond and "
            "other county clerks, and the NYC Property Information Portal "
            "supply the city, older-transfer, instrument, and image routes."
        ),
    },
    PALM_BEACH_RECORDER_SOURCE_ID: {
        "mode": "unified_live_exact_record_and_image_metadata",
        "direct_tool": (
            "uv run python tools/query_palm_beach_official_records.py --help"
        ),
        "record_identity": "official_instrument_number",
        "portal_locator": "native_document_id",
        "unified_selector_forms": [
            "numeric instrument number",
            "BOOK/PAGE",
        ],
        "direct_only_operations": [
            "book-page",
            "image",
            "routes",
        ],
        "official_complements": (
            query_palm_beach_official_records.source_routes()["complementary_routes"]
        ),
        "note": (
            "The shared route resolves deterministic exact instrument or "
            "book/page selectors. Broad party, parcel, legal-description, "
            "case, and date discovery is a separate interactive portal "
            "operation with reCAPTCHA observed. The official instrument "
            "number is the durable record key; the Landmark document ID and "
            "page IDs remain portal locators. Clerk bulk/copy services, the "
            "property appraiser, Florida DOR roll, tax collector, tax-deed "
            "portal, and eCaseView provide separately attributable discovery "
            "and context."
        ),
    },
    BROWARD_RECORDER_SOURCE_ID: {
        "mode": "unified_browser_session_recorder_index",
        "direct_tool": ("uv run python tools/query_broward_official_records.py --help"),
        "record_identity": "instrument_number",
        "shared_selectors": {
            "search": "indexed party name; optional grantor/grantee direction",
            "parcel": "exact recorder-index parcel identifier",
            "instrument": "exact instrument detail and image-availability metadata",
            "probe": "portal routes, release state, and coverage statements",
        },
        "direct_only_operations": [
            "download",
            "bulk",
            "routes",
            "runtime-check",
        ],
        "browser_session": {
            "portal_state": "disclaimer, cookies, and server-side search state",
            "document_pdf": (
                "viewer and all-pages PDF URLs are issued within the detail session"
            ),
        },
        "official_complements": (
            query_broward_official_records.source_routes()["complementary_routes"]
        ),
        "note": (
            "Shared records are recorder-index observations keyed by instrument "
            "number. Party roles and parcel links remain source fields. Address "
            "lookup uses the Property Appraiser or Florida DOR roll; certified "
            "copies, older media, court dockets, taxes, and tax-deed files use "
            "the separately listed official routes."
        ),
    },
    SANTA_FE_PROPERTY_SOURCE_ID: {
        "mode": "unified_anonymous_county_assessor_arcgis",
        "direct_tool": (
            "uv run python tools/query_santa_fe_property.py --help"
        ),
        "record_identity": (
            "UPC, with parcel_number fallback for durable parcel accounts"
        ),
        "feature_occurrence_identity": (
            "OBJECTID only when no durable parcel key is published"
        ),
        "native_search_fields": [
            "owner",
            "address",
            "mailing",
            "parcel",
            "objectid",
        ],
        "default_pagination": (
            "exhaust source-reported ArcGIS pages unless the caller selects "
            "a result window"
        ),
        "shared_selectors": {
            "search": (
                "owner by default; --search-field also selects address, "
                "mailing, parcel/UPC, or objectid"
            ),
            "owner": "Assessor owner-name observation",
            "address": "published situs address",
            "parcel": "UPC, parcel number, or alternate ID",
            "map": "ArcGIS OBJECTID with geometry enabled",
            "discovery": "routes by default, or metadata",
            "freshness": "validated live-layer metadata",
            "probe": "exact county-owned UPC sentinel plus layer contract",
        },
        "official_complements": [
            {
                key: value
                for key, value in route.items()
                if key not in {"observed_count", "observed_count_note"}
            }
            for route in query_santa_fe_property.SOURCE_ROUTES
            if route["route_id"] != SANTA_FE_PROPERTY_SOURCE_ID
        ],
        "note": (
            "Owner fields are assessment-roll observations, not recorded "
            "title. OBJECTID-only geometry features remain source "
            "occurrences and do not become durable parcels. Current and "
            "prior valuation labels retain the source period names because "
            "the layer does not publish their years. Recorder numbers, "
            "book/page, ADEED, and ADHST remain join hints. ParcelDownload, "
            "Parcels, and Notice of Value are same-Assessor representations; "
            "ClerkTrack instruments and Treasurer tax records are distinct "
            "field-matched sources."
        ),
    },
    SANTA_FE_CLERKTRACK_SOURCE_ID: {
        "mode": "unified_public_clerktrack_recorded_instrument_index",
        "direct_tool": (
            "uv run python tools/query_santa_fe_clerktrack.py --help"
        ),
        "record_identity": "instrument_number",
        "native_page_size": (
            query_santa_fe_clerktrack.NATIVE_PAGE_SIZE_OBSERVED
        ),
        "default_pagination": (
            "exhaust every source-reported native page unless the caller "
            "selects a result window"
        ),
        "native_search_fields": [
            "party_name",
            "party_role",
            "recording_date",
            "instrument_number",
            "book",
            "page",
            "document_type",
            "legal_description",
            "subdivision",
            "lot",
            "block",
            "tract",
            "section",
            "township",
            "range",
            "unit",
            "additional_information",
        ],
        "shared_selectors": {
            "search": (
                "party name by default; --search-field selects every other "
                "verified ClerkTrack field"
            ),
            "owner": "indexed party-name discovery",
            "instrument": "fresh-session exact instrument detail",
            "detail": "fresh-session exact instrument detail",
            "discovery": "verified route and lineage map",
            "probe": (
                "fixed exact instrument with list/detail agreement and no "
                "image acquisition"
            ),
        },
        "official_complements": [
            dict(route)
            for route in query_santa_fe_clerktrack.SOURCE_ROUTES
            if route["route_id"] != SANTA_FE_CLERKTRACK_SOURCE_ID
        ],
        "note": (
            "Index party displays are source snapshots; exact detail exposes "
            "the individually published grantor and grantee roles. Index, "
            "detail, image purchase, copy request, and Index Books are the "
            "same Clerk office lineage. Assessor account fields are "
            "independent field-matched evidence, and Treasurer observations "
            "are a distinct tax-record complement. No image artifact is "
            "created from index or detail metadata."
        ),
    },
    USVI_RECORDER_SOURCE_ID: {
        "mode": "unified_anonymous_countyfusion_recorder",
        "direct_tool": "uv run python tools/query_usvi_recorder.py --help",
        "record_identity": "district_plus_inst_id",
        "lookup_keys": ["instrument_number", "book_page"],
        "native_search_fields": [
            "indexed_party_name",
            "grantor",
            "grantee",
            "recording_date",
            "document_type",
            "document_number",
            "book_page",
            "parcel",
            "qtr_condo",
            "estate",
            "building",
            "unit",
            "plot",
            "land_comment",
        ],
        "default_pagination": (
            "exhaust every source-reported native page before applying an "
            "explicit caller offset or result window"
        ),
        "shared_selectors": {
            "search": "native indexed name, date/type, number, book/page, or legal field",
            "owner": "indexed party-name discovery",
            "instrument": (
                "exact detail using instrument number plus emitted district and instId"
            ),
            "download": (
                "one explicitly selected PNG page using the same exact locators"
            ),
            "probe": "fixed exact-instrument detail sentinel without an image fetch",
        },
        "official_complements": [
            {
                "kind": "current_official_publicsearch_alternative",
                "url": query_usvi_recorder.CURRENT_PUBLICSEARCH_COMPLEMENT,
                "authority": "U.S. Virgin Islands Recorder of Deeds",
                "relationship": (
                    "modern access representation of the same recorder authority"
                ),
                "independent_evidence": False,
            },
            {
                "kind": "official_property_assessment_complement",
                "url": query_usvi_recorder.CAMA_COMPLEMENT,
                "relationship": (
                    "assessment and tax fields joined separately from recorded title"
                ),
            },
        ],
        "note": (
            "Instrument numbers and book/page values are lookup keys; district "
            "plus instId is the durable source identity. Indexed parties and "
            "legal text project as recorded-instrument metadata, not a current "
            "ownership assertion. Each PNG is a nested representation of the "
            "same instrument, and the modern PublicSearch portal is another "
            "official access route rather than independent corroboration."
        ),
    },
    USVI_PROPERTY_TAX_SOURCE_ID: {
        "mode": "unified_anonymous_capture_cama_assessment_and_tax",
        "direct_tool": (
            "uv run python tools/query_usvi_property_tax.py --help"
        ),
        "record_identity": "formatted_parcel_number_plus_tax_year",
        "source_internal_locator": (
            "ParcelId is a tax-year-specific detail locator"
        ),
        "native_search_fields": ["owner", "parcel", "address", "legal"],
        "native_page_sizes": list(query_usvi_property_tax.NATIVE_PAGE_SIZES),
        "default_pagination": (
            "exhaust every source-reported native page before applying an "
            "explicit caller result window"
        ),
        "shared_selectors": {
            "search": (
                "owner by default, or owner, parcel, address, or legal "
                "through --search-field"
            ),
            "owner": "assessment-roll owner-name observation",
            "address": "published property or mailing address search",
            "parcel": "exact formatted parcel plus optional tax year",
            "download": (
                "bill, receipt, or property-card printable HTML selected "
                "with --artifact-kind"
            ),
            "probe": (
                "fixed exact parcel-and-year contract without photographs, "
                "maps, property cards, bills, or receipts"
            ),
        },
        "identity_domains": {
            "assessment_observation": "formatted_parcel_number_plus_tax_year",
            "statement": (
                "formatted_parcel_number_plus_tax_year_plus_statement_number"
            ),
            "payment": (
                "formatted_parcel_number_plus_payment_transaction_id"
            ),
            "printable_artifact": (
                "nested_representation_of_statement_payment_or_card"
            ),
        },
        "official_complements": [
            {
                "source_id": USVI_RECORDER_SOURCE_ID,
                "kind": "official_recorded_instrument_complement",
                "url": query_usvi_recorder.OFFICIAL_LINKING_PAGE,
                "relationship": (
                    "separately attributable title, grantor, grantee, "
                    "recording-date, and legal-description evidence"
                ),
            },
            {
                "source_id": "us-vi-office-of-tax-collector",
                "kind": "official_tax_collector_service_complement",
                "url": (
                    "https://ltg.gov.vi/departments/office-of-tax-collector/"
                ),
                "relationship": (
                    "tax clearance, delinquency, payment-plan, and collection "
                    "services from the responsible office"
                ),
            },
            {
                "kind": "same_tenant_failover",
                "url": query_usvi_property_tax.FAILOVER_BASE_URL,
                "relationship": (
                    "alternate host for the same Capture CAMA tenant"
                ),
                "independent_evidence": False,
            },
        ],
        "note": (
            "Owner labels project only as dated assessment-roll assertions. "
            "Payer, value, balance, statement, payment, and sale labels remain "
            "assessment/tax observations and do not become current-title "
            "claims. Supported assessment, tax-event, address, and retrieved "
            "artifact fields are projected while the remaining publisher "
            "tables stay in the raw observation."
        ),
    },
    WASHINGTON_LAND_RECORDS_SOURCE_ID: {
        "mode": "unified_live_county_auditor_archive_index",
        "direct_tool": (
            "uv run python "
            "tools/query_washington_digital_archives_land.py --help"
        ),
        "record_identity": "archive_record_id_with_query_bound_index_occurrences",
        "shared_selectors": {
            "search": "indexed party name within one covered county title",
            "owner": "indexed party name within one covered county title",
            "instrument": "exact 32-hex archive record identifier",
        },
        "native_page_sizes": list(
            query_washington_digital_archives_land.NATIVE_PAGE_SIZES
        ),
        "official_recorder_alternatives": [
            {
                key: value
                for key, value in alternative.to_record().items()
                if key != "complementary_sources"
            }
            for alternative in (
                query_washington_digital_archives_land.RECORDER_ALTERNATIVES
            )
        ],
        "official_assessor_complements": [
            {
                "county_key": alternative.key,
                "county_geoid": alternative.county_geoid,
                **dict(complement),
            }
            for alternative in (
                query_washington_digital_archives_land.RECORDER_ALTERNATIVES
            )
            for complement in alternative.complementary_sources
            if str(complement.get("kind") or "").startswith("assessor")
        ],
        "note": (
            "Search results are county-auditor recorded-instrument index "
            "occurrences, not assessor ownership records. Exact detail adds "
            "the archived instrument metadata and listed digital-object state. "
            "Counties absent from record series 14 route to separately "
            "attributed county recorder paths; assessor parcel searches remain "
            "distinct join and discovery complements."
        ),
    },
    NC_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_nc_property.py --help",
    },
    BEXAR_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_bexar_property.py --help",
        "note": (
            "The direct adapter also exposes full-text search, rich property "
            "detail, roll history, appeals, improvements, and deed history."
        ),
    },
    DENVER_PROPERTY_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_denver_property.py --help"),
        "note": (
            "The direct adapter also exposes exact ArcGIS object lookup, "
            "assessment fields, physical characteristics, and reception "
            "numbers that join to the Denver recorder index."
        ),
    },
    DENVER_DELINQUENT_TAX_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_denver_delinquent_tax.py --help"),
        "note": (
            "Unified queries discover and stream the current official "
            "workbook. The direct adapter also lists, verifies, inspects, and "
            "downloads releases and exposes tax-sale and partial-payment "
            "indicators."
        ),
    },
    DENVER_FORECLOSURE_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_denver_foreclosures.py --help"),
        "note": (
            "Unified queries cover foreclosure number, current owner, and "
            "street address. The direct adapter also exposes every verified "
            "search filter, rich case details, document indexes, and "
            "session-bound document downloads."
        ),
    },
    DELAWARE_FIRSTMAP_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_delaware_firstmap.py --help"),
        "note": (
            "The statewide layer supplies parcel identifiers, polygons, "
            "centroids, and routing attributes. County systems remain the "
            "complement for owner, assessment, deed, permit, and history "
            "fields."
        ),
    },
    ARLINGTON_PROPERTY_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_arlington_property.py --help"),
        "note": (
            "The official layer exposes parcel identifiers, owner mailing "
            "addresses without owner names, classifications, zoning, legal "
            "descriptions, assessments, lot size, and geometry."
        ),
    },
    COOK_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_cook_property.py --help",
    },
    MD_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_md_property.py --help",
    },
    MD_PLATS_SOURCE_ID: {
        "mode": "unified_live_recorded_plat_archive",
        "direct_tool": "uv run python tools/query_md_plats.py --help",
        "native_keys": [
            "county_code",
            "archive_qualifier",
            "archive_series",
            "archive_unit",
        ],
        "search_occurrence_identity": [
            "search_criteria_fingerprint",
            "absolute_source_position",
            "representation_identity",
        ],
        "artifact_representations": [
            "compiled_pdf",
            "published_pdf",
            "direct_scan",
            "microfilm_scan",
            "other_scan",
        ],
        "pagination": (
            "Omitted shared --limit follows every source-reported native "
            "page. An explicit shared --limit returns a query-bound cursor."
        ),
        "official_complements": [
            "us-md-land-records",
            "us-md-mdp-parcel-points",
            "us-md-mdp-cama-downloads",
            "us-md-mdp-property-sales-downloads",
        ],
        "note": (
            "Search rows include metadata-only archive records. Plat "
            "references and the source's developer/owner display remain "
            "plat metadata; recorded-title and parcel-owner questions use "
            "their separately attributed complements."
        ),
    },
    MD_MDP_PARCEL_POINTS_SOURCE_ID: {
        "mode": "unified_live_statewide_point_representation",
        "direct_tool": (
            "uv run python tools/query_md_mdp_parcel_points.py --help"
        ),
        "record_identity": {
            "source_id": query_md_mdp_parcel_points.RECORD_IDENTITY_SOURCE_ID,
            "field": query_md_mdp_parcel_points.ACCOUNT_ID_FIELD,
            "relationship": "exact_cross_representation_parcel_account_join",
        },
        "feature_occurrence_identity": (
            query_md_mdp_parcel_points.OBJECT_ID_FIELD
        ),
        "native_search_fields": [
            "ACCTID",
            "local parcel coordinate",
            "address",
            "OBJECTID",
            "county",
            "map",
            "plat",
            "grid",
            "land-use",
            "zoning",
            "point",
            "bounding box",
        ],
        "note": (
            "This official MDP/SDAT representation adds point geometry, "
            "structure, land, zoning, appraisal, transfer-reference, and "
            "owner-mailing-address fields. It shares ACCTID identity with "
            "the hidden-owner Socrata representation but retains OBJECTID "
            "as its ArcGIS occurrence; it is not independent corroboration."
        ),
    },
    query_md_mdp_property_downloads.PARCEL_SOURCE_ID: {
        "mode": "unified_bulk_release_and_local_inventory",
        "direct_tool": (
            "uv run python "
            "tools/query_md_mdp_property_downloads.py --help"
        ),
        "native_keys": [
            "release_id",
            "Dropbox provider_link_id",
            "artifact_sha256",
            "archive member occurrence",
            "ACCTID",
        ],
        "record_identity": {
            "source_id": (
                query_md_mdp_property_downloads.SDAT_PROPERTY_IDENTITY_SOURCE_ID
            ),
            "field": "ACCTID",
            "relationship": "exact_cross_representation_parcel_account_join",
        },
        "shared_transfer_contract": {
            "download_without_destination": "prepared_transfer_description",
            "manifest_or_discovery_with_artifact_path": (
                "safe_local_archive_inventory"
            ),
        },
        "row_projection": False,
        "note": (
            "The official statewide parcel ZIP and schema workbook remain "
            "release artifacts until their geodatabase tables are decoded. "
            "Release, Dropbox link, artifact digest, and member occurrence "
            "identities remain separate; future parcel rows share ACCTID "
            "identity with the MDP/SDAT assessment representations."
        ),
    },
    query_md_mdp_property_downloads.CAMA_SOURCE_ID: {
        "mode": "unified_bulk_release_and_local_inventory",
        "direct_tool": (
            "uv run python "
            "tools/query_md_mdp_property_downloads.py --help"
        ),
        "native_keys": [
            "release_id and release_group_id",
            "Dropbox provider_link_id",
            "artifact_sha256",
            "archive member occurrence",
            "component row occurrence",
        ],
        "parcel_join": {
            "record_identity_source_id": (
                query_md_mdp_property_downloads.SDAT_PROPERTY_IDENTITY_SOURCE_ID
            ),
            "field": "ACCTID",
        },
        "component_join": {
            "field": "CAMALINK",
            "relationship": "building_to_subareas",
        },
        "shared_transfer_contract": {
            "download_without_destination": "prepared_transfer_description",
            "manifest_or_discovery_with_artifact_path": (
                "safe_local_archive_inventory"
            ),
        },
        "row_projection": False,
        "note": (
            "Core, Building, Land, Subareas, and statewide bundles retain "
            "their different row grains. ACCTID joins CAMA records to the "
            "parcel account, CAMALINK joins Building to Subareas, and row "
            "occurrences remain artifact/member/ordinal identities until "
            "the actual component schemas are decoded."
        ),
    },
    query_md_mdp_property_downloads.SALES_SOURCE_ID: {
        "mode": "unified_bulk_release_and_local_inventory",
        "direct_tool": (
            "uv run python "
            "tools/query_md_mdp_property_downloads.py --help"
        ),
        "native_keys": [
            "release_id",
            "Dropbox provider_link_id",
            "artifact_sha256",
            "archive member occurrence",
            "row occurrence",
        ],
        "parcel_join": "ACCTID",
        "candidate_transaction_dedup": [
            "ACCTID",
            "TRADATE",
            "CONSIDR1",
        ],
        "source_issued_transaction_id_verified": False,
        "monthly_release_rows_may_repeat": True,
        "shared_transfer_contract": {
            "download_without_destination": "prepared_transfer_description",
            "manifest_or_discovery_with_artifact_path": (
                "safe_local_archive_inventory"
            ),
        },
        "row_projection": False,
        "note": (
            "These are residential-sales analytic releases rather than "
            "complete deed history. The ACCTID/date/consideration tuple is "
            "only a candidate transaction deduplication key; release, "
            "artifact, member, and row occurrences remain separately "
            "attributable."
        ),
    },
    MIAMI_DADE_PA_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_miami_dade_property.py --help"),
        "note": (
            "The direct adapter also exposes rich detail, assessment and sale "
            "history, and exact parcel geometry."
        ),
    },
    MIAMI_DADE_RECORDER_PUBLIC_SOURCE_ID: {
        "mode": "direct_live_enrichment",
        "direct_tool": ("uv run python tools/query_miami_dade_recorder.py --help"),
        "note": (
            "Use issued public-result tokens or known record identifiers for "
            "party, financial, instrument, and document-image enrichment."
        ),
    },
    MIAMI_DADE_RECORDER_SOURCE_ID: {
        "mode": "credentialed_api_and_bulk_actions",
        "direct_tool": ("uv run python tools/query_miami_dade_recorder.py --help"),
        "note": (
            "The direct adapter exposes exact commercial CFN, book/page, and "
            "folio lookups; subscribed bulk feeds remain catalog-backed data "
            "product work."
        ),
    },
    EBR_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_la_property.py --help",
    },
    ORLEANS_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_orleans_property.py --help",
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": ("uv run python tools/query_oregon_taxlots.py --help"),
            "note": (
                "Select one publisher-scoped Oregon component. Portland "
                "publishes owner names; Metro and OWRD do not. Every result "
                "retains county and upstream source lineage."
            ),
        }
        for source_id in OREGON_TAXLOT_SOURCE_IDS
    },
    OREGON_BENTON_TAXLOT_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_oregon_benton_property.py --help"),
        "native_search_fields": [
            "owner",
            "address",
            "account",
            "map_taxlot",
            "or_taxlot",
            "map_number",
        ],
        "official_complements": [
            {
                "source_id": query_oregon_benton_property.HELION_SOURCE_ID,
                "role": "current_assessment_tax_and_payment_detail",
            },
            {
                "source_id": query_oregon_benton_property.ACCOUNT_API_SOURCE_ID,
                "role": "assessment_value_sales_and_improvement_history",
            },
            {
                "source_id": query_oregon_benton_property.BULK_SOURCE_ID,
                "role": "county_assessment_gis_snapshots",
            },
            {
                "source_id": query_oregon_benton_property.MAP_SOURCE_ID,
                "role": "assessment_map_pdfs",
            },
        ],
        "note": (
            "The live layer returns owner-party/account rows and optional "
            "WGS84 geometry. Unified parcel/map lookup defaults to MapTaxlot; "
            "--search-field selects account, ORTaxlot, or map number."
        ),
    },
    OREGON_BENTON_BULK_SOURCE_ID: {
        "mode": "unified_live_bulk",
        "direct_tool": ("uv run python tools/query_oregon_benton_property.py --help"),
        "artifact_names": list(query_oregon_benton_property.CURRENT_BULK_FILENAMES),
        "note": (
            "Unified search returns the current county release manifest; "
            "unified instrument probes one named ZIP and returns its current "
            "transfer and format state."
        ),
    },
    OREGON_BENTON_MAP_SOURCE_ID: {
        "mode": "unified_live_document_collection",
        "direct_tool": ("uv run python tools/query_oregon_benton_property.py --help"),
        "note": (
            "Unified search or parcel lists assessment-map PDFs by map number "
            "('*' lists the current directory); unified instrument probes one "
            "named map artifact."
        ),
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_yamhill_property.py --help"
            ),
            "official_complements": [
                item.get("source_id") or item.get("kind")
                for item in query_oregon_yamhill_property.COMPLEMENTARY_SOURCES[
                    source_id
                ]
            ],
            "note": (
                "Yamhill keeps AscendWeb account history, current and retired "
                "taxlots, annual assessment permits, and recorder pivots as "
                "separately attributable components joined by account, "
                "map-taxlot, and recording number."
            ),
        }
        for source_id in OREGON_YAMHILL_SOURCE_IDS
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_clackamas_property.py --help"
            ),
            "note": (
                "AscendWeb supplies account parties and rich tax history; CMap "
                "supplies geometry and selected assessment, building, and "
                "sale/deed fields. Owner-name behavior is retained per "
                "component."
            ),
        }
        for source_id in OREGON_CLACKAMAS_SOURCE_IDS
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_wasco_property.py --help"
            ),
            "note": (
                "Wasco exposes independent AscendWeb, taxlot, and SurveyorData "
                "components. Land-corner and survey-book layers also expose "
                "source-hosted scan attachments through the direct adapter."
            ),
        }
        for source_id in OREGON_WASCO_SOURCE_IDS
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_washington_property.py --help"
            ),
            "native_capabilities": (
                query_oregon_washington_property._capabilities(source_id)
            ),
            "native_joins": (query_oregon_washington_property._joins(source_id)),
            "official_complements": [
                dict(item) for item in query_oregon_washington_property.COMPLEMENTS
            ],
            "note": (
                "Washington County keeps Survey Explorer indexes and source "
                "documents, survey geometry, current taxlots, situs points, "
                "Intermap reports, and WashCoTax account/statement records as "
                "six attributable components. The direct adapter exposes the "
                "full Survey Explorer kind/layer matrix and document retrieval."
            ),
        }
        for source_id in OREGON_WASHINGTON_SOURCE_IDS
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_washington_case_permits.py --help"
            ),
            "native_capabilities": {
                query_oregon_washington_case_permits.CASEFILE_SOURCE_ID: [
                    "case-search",
                    "case-detail",
                    "case-review",
                    "case-decisions",
                    "case-staff",
                ],
                query_oregon_washington_case_permits.TAXLOT_ACTIVITY_SOURCE_ID: [
                    "taxlot-activity"
                ],
                query_oregon_washington_case_permits.BUILDING_SOURCE_ID: [
                    "building-search",
                    "building-types",
                ],
                query_oregon_washington_case_permits.PERMIT_REPORT_SOURCE_ID: [
                    "permit-report"
                ],
                query_oregon_washington_case_permits.ACCELA_SOURCE_ID: [
                    "accela-record",
                    "accela-document",
                    "accela-download",
                ],
                query_oregon_washington_case_permits.DOCUMENT_ROUTE_SOURCE_ID: [
                    "document-routes"
                ],
            }[source_id],
            "operation_access": dict(
                query_oregon_washington_case_permits.SOURCES[source_id].metadata.get(
                    "operations"
                )
                or query_oregon_washington_case_permits.SOURCES[source_id].metadata.get(
                    "operation_access"
                )
                or {"document_routes": "official publication and request routes"}
            ),
            "native_joins": [
                dict(edge)
                for edge in query_oregon_washington_case_permits.source_manifest()[
                    "join_graph"
                ]
                if source_id in {edge["from"], edge["to"]}
            ],
            "operation_triage": [
                dict(item)
                for item in query_oregon_washington_case_permits.source_manifest()[
                    "operation_triage"
                ]
            ],
            "official_complements": [
                {
                    "name": "Development applications in progress",
                    "url": (
                        query_oregon_washington_case_permits.DEVELOPMENT_PROGRESS_URL
                    ),
                },
                {
                    "name": "Frequently discussed development applications",
                    "url": (
                        query_oregon_washington_case_permits.FREQUENTLY_DISCUSSED_URL
                    ),
                },
                {
                    "name": "Notices of decision",
                    "url": query_oregon_washington_case_permits.DECISIONS_APP_URL,
                },
                {
                    "name": "Public hearings and agendas",
                    "url": (query_oregon_washington_case_permits.PUBLIC_HEARINGS_URL),
                },
                {
                    "name": "CivicWeb land-use meeting packets",
                    "url": (query_oregon_washington_case_permits.CIVICWEB_LAND_USE_URL),
                },
                {
                    "name": "Legacy Laserfiche casefile route",
                    "url": (query_oregon_washington_case_permits.LEGACY_LASERFICHE_URL),
                },
                {
                    "name": "Permit records and public request route",
                    "url": query_oregon_washington_case_permits.PERMIT_RECORDS_URL,
                },
            ],
            "note": (
                "Washington County planning and permit records remain six "
                "attributable components. Dated casefile and report rows can "
                "be stored as property events; vocabularies, route catalogs, "
                "document representations, and undated rows remain source "
                "observations. These sources describe planning and permit "
                "activity rather than court dockets."
            ),
        }
        for source_id in OREGON_WASHINGTON_CASE_PERMIT_SOURCE_IDS
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_multnomah_sail.py --help"
            ),
            "native_capabilities": [
                "search",
                "record",
                *(
                    ["image", "download"]
                    if query_oregon_multnomah_sail.COMPONENTS[source_id].image_capable
                    else []
                ),
            ],
            "native_search_fields": sorted(
                {
                    "object-id",
                    *query_oregon_multnomah_sail.COMPONENTS[source_id].search_fields,
                }
            ),
            "native_joins": (
                ["PROPID", "MAPTAXLOT", "ALTACCTNUM", "INST_NUM"]
                if source_id == query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID
                else ["OBJECTID", "SURVEYID"]
            ),
            "official_complements": [
                dict(item) for item in query_oregon_multnomah_sail.COMPLEMENTARY_SOURCES
            ],
            "note": (
                "Multnomah County SAIL keeps the current county tax-parcel "
                "layer and seven survey, plat, corner, road, and field-book "
                "collections separately attributable. The direct adapter also "
                "resolves each image-capable SURVEYID through the county viewer "
                "and can save the selected PDF representation."
            ),
        }
        for source_id in OREGON_MULTNOMAH_SAIL_SOURCE_IDS
    },
    OREGON_LINCOLN_PROPERTYWEB_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": (
            "uv run python tools/query_oregon_lincoln_propertyweb.py --help"
        ),
        "official_complements": [
            {
                "source_id": OREGON_LINCOLN_TAXLOT_SOURCE_ID,
                "role": "parcel_owner_geometry",
                "join_keys": ["property_quick_ref", "map_number"],
            },
            {
                "source_id": query_oregon_lincoln_propertyweb.RECORDER_SOURCE_ID,
                "role": "recorded_instrument_and_image",
                "join_keys": ["sale_instrument", "party_name", "sale_date"],
            },
        ],
        "note": (
            "Unified routes search the PropertyWeb JSON account index. The "
            "direct adapter also returns account detail, value and sale "
            "history, bills, payments, improvements, land, districts, "
            "exemptions, and session-linked PDF representations."
        ),
    },
    OREGON_LINCOLN_TAXLOT_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_oregon_lincoln_taxlots.py --help"),
        "native_search_fields": sorted(query_oregon_lincoln_taxlots.SEARCH_FIELDS),
        "official_complements": [
            {
                "source_id": OREGON_LINCOLN_PROPERTYWEB_SOURCE_ID,
                "role": "assessment_tax_sale_and_document_detail",
                "join_keys": ["propertyid", "parcelid"],
            },
            {
                "source_id": query_oregon_lincoln_taxlots.RECORDER_SOURCE_ID,
                "role": "recorded_instrument_and_image",
                "join_path": (
                    "propertyid -> PropertyWeb account -> sale instrument -> "
                    "recorder document number"
                ),
            },
            {
                "source_id": "us-or-owrd-public-tax-lots",
                "role": "statewide_taxlot_geometry",
                "join_keys": ["normalized_parcelid", "county_name"],
            },
            {
                "source_id": "us-or-ormap-cadastral-routing",
                "role": "official_assessor_map_routing",
                "join_keys": ["parcelid", "imagekey"],
            },
        ],
        "note": (
            "The county WFS supplies taxlot identifiers, owner and address "
            "fields, assessor-map links, and optional GeoJSON geometry. "
            "Results retain the declared source CRS, requested output CRS, "
            "and GeoJSON-reported CRS as separate lineage values."
        ),
    },
    **{
        source_id: {
            "mode": "unified_live_publication",
            "direct_tool": (
                "uv run python tools/query_oregon_tax_foreclosures.py --help"
            ),
            "publication_process_stages": list(
                query_oregon_tax_foreclosures.SOURCE_PROCESS_STAGES[source_id]
            ),
            "official_complements": [
                complement.to_dict() for complement in config.complementary_sources
            ],
            "artifact_workflow": (
                "The direct adapter discovers current and historical official "
                "routes, downloads a selected publication, inspects its PDF "
                "version, and can bind a supplied OCR or other text "
                "representation to that artifact."
            ),
            "note": (
                "Unified routes search the selected county publication and "
                "preserve the resolved legal-process stage, publication "
                "identity, artifact hash, and text-representation provenance. "
                "County parcel/tax systems and post-sale routes remain keyed "
                "official complements."
            ),
        }
        for source_id, config in query_oregon_tax_foreclosures.SOURCES.items()
    },
    DESCHUTES_PROPERTY_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_deschutes_property.py --help"),
        "note": (
            "The county service hydrates each taxlot through eight declared "
            "assessor relationships. Its sales table is joined separately by "
            "the published taxlot key. The direct adapter also exposes map, "
            "mailing-address, and sale-party search."
        ),
    },
    DESCHUTES_DIAL_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_deschutes_dial.py --help"),
        "note": (
            "DIAL is the official account-detail, tax, payment, report, permit, "
            "and development-record complement. It joins to the separate "
            "ArcGIS parcel source by account ID and map/taxlot; use the ArcGIS "
            "source for parcel geometry."
        ),
    },
    DESCHUTES_CDD_WEBLINK_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_deschutes_laserfiche.py --help"),
        "native_identity": "laserfiche_entry_id",
        "property_join_keys": ["deschutes_dial_account_id", "map_taxlot"],
        "note": (
            "The unified account route discovers CDD document IDs linked from "
            "one DIAL property account. Use the direct adapter for document and "
            "folder metadata or for electronic-file and generated-PDF "
            "retrieval; DIAL, the county taxlot service, Oregon ePermitting, "
            "and the county records-request channel remain distinct "
            "complements."
        ),
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_helion_property.py --help"
            ),
            "native_search_fields": list(tenant.search_options),
            "official_complements": [
                dict(complement) for complement in tenant.complements
            ],
            "note": (
                "Unified routes cover name, address, map-taxlot, and real-roll "
                "account detail for this county tenant. The direct adapter "
                "retains its complete native selector set, roll-type detail, "
                "continuation, tax balances, payoff schedule, assessments, "
                "sales, improvements, reports, and county-specific official "
                "complements."
            ),
        }
        for source_id, tenant in (
            query_oregon_helion_property.TENANTS_BY_SOURCE.items()
        )
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_helion_recorder.py --help"
            ),
            "selector_discovery": (
                "The direct adapter probe returns this tenant's current form "
                "fields and option vocabularies; search validates selectors "
                "against that rendered tenant form."
            ),
            "official_complements": [
                dict(complement) for complement in tenant.complement_observations
            ],
            "resource_observation": tenant.resource_observation,
            "note": (
                "Unified routes cover party-name and instrument-number "
                "discovery for the selected county tenant. The direct adapter "
                "also exposes the date, document-type, map, taxlot, "
                "subdivision, legal-description, and other selectors present "
                "in that tenant's form, plus title detail. Image, OCR-text, "
                "cart-copy, and certified-copy states are retained when the "
                "selected tenant publishes them; an absent state remains "
                "explicit rather than becoming a family-wide capability."
            ),
        }
        for source_id, tenant in (
            query_oregon_helion_recorder.TENANTS_BY_SOURCE.items()
        )
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_jackson_douglas_assessors.py --help"
            ),
            "native_search_fields": sorted(config.search_fields),
            "official_complements": list(
                query_oregon_jackson_douglas_assessors.COMPLEMENTARY_SOURCES[source_id]
            ),
            "note": (
                "Jackson and Douglas remain separate assessor components with "
                "their own identifiers, field maps, values, and geometry. "
                "Douglas also publishes a current-row instrument and sale-date "
                "reference; recorder and bulk products remain distinct sources."
            ),
        }
        for source_id, config in (
            query_oregon_jackson_douglas_assessors.SOURCES.items()
        )
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_jackson_property_events.py --help"
            ),
            "record_kind": config.record_kind,
            "native_search_fields": sorted(config.search_fields),
            "official_complements": list(
                query_oregon_jackson_property_events.COMPLEMENTARY_SOURCES[source_id]
            ),
            "note": (
                "Building permits, land-use permits, and code-compliance "
                "observations are separate event components. Their published "
                "address, map-taxlot candidate, people, point, and linked "
                "Accela detail are retained as event evidence."
            ),
        }
        for source_id, config in query_oregon_jackson_property_events.SOURCES.items()
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python "
                "tools/query_oregon_linn_josephine_klamath_assessors.py --help"
            ),
            "native_search_fields": sorted(config.search_fields),
            "official_complements": [
                dict(complement) for complement in config.complementary_sources
            ],
            "note": (
                "Linn, Josephine, and Klamath remain separate assessor "
                "components with county-native identifiers, schemas, value "
                "meanings, update observations, and official account, map, "
                "recorder, or request complements."
            ),
        }
        for source_id, config in (
            query_oregon_linn_josephine_klamath_assessors.SOURCES.items()
        )
    },
    **{
        source.source_id: {
            "mode": "unified_exact_record",
            "direct_tool": (
                "uv run python tools/query_oregon_jackson_accela.py --help"
            ),
            "arcgis_index_source_id": source.arcgis_source_id,
            "record_kind": source.record_kind,
            "note": (
                "The unified event route fetches an exact Accela CAP record "
                "and preserves its detail, attachment listing, processing, "
                "related-record, fee, and inspection representations. The "
                "direct adapter also exposes stable document-detail and listed "
                "binary-document commands."
            ),
        }
        for source in query_oregon_jackson_accela.SOURCES.values()
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_lane_marion_parcels.py --help"
            ),
            "note": (
                "Lane parcel and rolling recent-sale layers remain separate "
                "components joined by account and map-taxlot. Marion parcels "
                "include the latest verified-sale reference; the official "
                "annual sales downloads add the longer history."
            ),
        }
        for source_id in OREGON_LANE_MARION_SOURCE_IDS
    },
    query_oregon_lane_property.ACCOUNT_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": (
            "uv run python tools/query_oregon_lane_property.py --help"
        ),
        "native_search_fields": ["account", "map_taxlot", "address", "name"],
        "identity": {
            "account": "canonical property-account identity",
            "search_index_row": (
                "account plus the source-returned map-taxlot, taxpayer, "
                "owner-index, and situs labels"
            ),
        },
        "official_complements": [
            query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID,
            query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID,
            query_oregon_lane_property.TAX_MAP_SOURCE_ID,
            query_oregon_lane_property.LANE_RECORDER_SOURCE_ID,
            query_oregon_lane_property.LANE_RLID_SOURCE_ID,
        ],
        "note": (
            "The portal publishes account, taxpayer, owner-index, situs, "
            "mailing, receipt, and valuation representations. Taxpayer and "
            "owner-index labels remain distinct assessor or tax-account "
            "observations and are not recorded-title conclusions. Omitted "
            "limits return every row supplied by the selected native query."
        ),
    },
    query_oregon_lane_property.TAX_MAP_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": (
            "uv run python tools/query_oregon_lane_property.py --help"
        ),
        "native_search_fields": ["map_lot", "address", "map_name"],
        "identity": {
            "locator": "map-taxlot or map-name plus tax-map document ID",
            "document": "source-native tax-map document ID",
        },
        "official_complements": [
            query_oregon_lane_property.ACCOUNT_SOURCE_ID,
            query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID,
            query_oregon_lane_property.LANE_RECORDER_SOURCE_ID,
            {
                "url": query_oregon_lane_property.TAX_MAP_ORDER_URL,
                "relationship": (
                    "official full image set and periodic update subscription"
                ),
            },
        ],
        "note": (
            "The search row is a locator occurrence and the linked PDF has "
            "its own document identity; several locators can point to one "
            "map image. Tax maps provide assessment cartography, while the "
            "recorder remains the source for recorded title instruments."
        ),
    },
    query_oregon_marion_downloads.SALES_SOURCE_ID: {
        "mode": "unified_bulk_and_local_search",
        "direct_tool": (
            "uv run python tools/query_oregon_marion_downloads.py --help"
        ),
        "native_keys": [
            "release slot",
            "downloaded artifact digest",
            "archive member occurrence",
            "row occurrence",
            "native or semantic sale identity",
            "assessment account and map-taxlot joins",
        ],
        "official_complements": (
            query_oregon_marion_downloads.alternative_records()
        ),
        "note": (
            "The official page exposes the current weekly CSV and historical "
            "sales artifacts back to 1940. CSV schema generations are parsed "
            "positionally, including duplicate 2020 headers. Legacy XLS and "
            "XLSB artifacts remain discoverable, transferable, and locally "
            "inspectable even when row search is unavailable for that member. "
            "Assessor sale-party and deed-reference labels are not current "
            "ownership, title, or recorded-document verification."
        ),
    },
    query_oregon_marion_downloads.ASSESSMENT_SOURCE_ID: {
        "mode": "unified_bulk_and_local_search",
        "direct_tool": (
            "uv run python tools/query_oregon_marion_downloads.py --help"
        ),
        "native_keys": [
            "comprehensive-current release slot",
            "downloaded artifact digest",
            "ORCATS member occurrence",
            "row occurrence",
            "ACCOUNT_ID",
            "RDATE",
        ],
        "official_complements": (
            query_oregon_marion_downloads.alternative_records()
        ),
        "note": (
            "The comprehensive ZIP is a replaceable assessment snapshot whose "
            "RDATE field supplies its data vintage. Owner names and mailing "
            "addresses have been omitted since February 1, 2015. SALE_GRANTOR, "
            "SALE_GRANTEE, BOOKPG, and related values remain latest-sale "
            "labels and are not projected as ownership, title, or a verified "
            "recorded instrument."
        ),
    },
    REEVES_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_reeves_records.py --help",
        "note": (
            "Unified search covers indexed parties and instrument numbers; "
            "the direct adapter also retrieves exact detail and selected "
            "instrument page images by native document ID."
        ),
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": ("uv run python tools/query_govos_recorders.py --help"),
            "note": (
                "Unified search covers indexed parties and instrument "
                "numbers. The shared direct adapter also exposes each "
                "tenant's departments, OCR/date searches, exact detail, "
                "selected page images, and live sentinel."
            ),
        }
        for source_id in GOVOS_RECORDER_SOURCE_IDS
    },
    ACRIS_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_acris.py --help",
    },
    FL_SOURCE_ID: {
        "mode": "unified_bulk_release",
        "direct_tool": "uv run python tools/query_fl_dor_property.py --help",
        "native_keys": [
            "dataset type",
            "Florida DOR county number",
            "assessment year and submission stage",
            "artifact filename and SHA-256",
        ],
        "shared_selectors": {
            "releases": "dataset type and tax year",
            "manifest": "dataset type, county, and tax year",
            "probe": "exact dataset type, county, and optional tax year",
            "download": (
                "exact dataset type, county, optional tax year, and explicit "
                "destination"
            ),
        },
        "archive_ingest": (
            "uv run python tools/ingest_fl_dor_property.py ingest --help"
        ),
        "note": (
            "Shared operations expose release directories, artifact manifests, "
            "bounded probes, and resumable downloads. Those envelopes remain "
            "source snapshots until a downloaded NAL, SDF, or GIS-PIN archive "
            "is explicitly parsed by the streaming archive ingester."
        ),
    },
    MASSGIS_SOURCE_ID: {
        "mode": "bulk_manifest",
        "direct_tool": "uv run python tools/query_massgis_property.py --help",
        "note": "Use the bulk adapter for municipal manifests and downloads.",
    },
    HARRIS_SOURCE_ID: {
        "mode": "unified_bulk_release",
        "direct_tool": "uv run python tools/query_harris_property.py --help",
        "native_keys": [
            "HCAD tax year and certification state",
            "artifact family and filename",
            "account number",
            "artifact SHA-256, table, and row occurrence",
        ],
        "shared_selectors": {
            "releases": "all published HCAD tax years",
            "manifest": "tax year and optional artifact family",
            "probe": "tax year, artifact family, and published artifact selector",
            "download": (
                "tax year, artifact family, published artifact selector, and "
                "explicit destination"
            ),
        },
        "archive_ingest": ("uv run python tools/ingest_hcad_property.py ingest --help"),
        "note": (
            "Shared operations expose official release discovery, manifests, "
            "bounded probes, and resumable downloads. Downloaded CAMA ZIPs "
            "remain source snapshots until the streaming archive ingester "
            "validates member headers and projects selected rows."
        ),
    },
    HCAD_GIS_SOURCE_ID: {
        "mode": "unified_bulk_release_and_live_mapserver",
        "direct_tool": "uv run python tools/query_hcad_gis.py --help",
        "native_keys": [
            "bulk release date or historical October snapshot year",
            "artifact filename and SHA-256",
            "HCAD_NUM parcel join",
            "MapServer OBJECTID feature occurrence",
        ],
        "shared_selectors": {
            "releases": "current release and all published October snapshots",
            "manifest": "optional historical tax year and artifact selector",
            "probe": "optional historical tax year and one artifact",
            "download": (
                "optional historical tax year, one artifact, and explicit destination"
            ),
            "live_search": (
                "owner, address, legal text, or account with a "
                "snapshot-bounded OBJECTID cursor"
            ),
            "map": "exact HCAD account with WGS84 parcel geometry",
        },
        "official_complements": query_hcad_gis._alternatives(),
        "note": (
            "The bulk and MapServer representations have separate freshness. "
            "The current bulk manifest was updated in July 2026, while the "
            "live MapServer appraisal fields are predominantly tax year 2025. "
            "Bulk ZIP inspection fingerprints the current File Geodatabase; "
            "the separate public_records_filegdb.py interface can stream its "
            "native-FID features when GDAL OpenFileGDB is available. HCAD CAMA "
            "supplies the fresher assessment and ownership complement; TxGIO "
            "supplies a standardized county shapefile alternative."
        ),
    },
    TEXAS_EPTS_SOURCE_ID: {
        "mode": "request_handoff_and_local_artifact",
        "direct_tool": "uv run python tools/query_texas_epts.py --help",
        "native_keys": [
            "artifact SHA-256, member, and source row occurrence",
            "CAD_ID plus PROP_ID1_TX property candidate",
            "deed locator and transaction-group candidates",
        ],
        "operations": {
            "discover": "official source and acquisition contract",
            "schema": "September 2025 52-field layout and code sets",
            "request-plan": "reviewable CRRS/email handoff without submission",
            "inspect": "validate a caller-acquired artifact",
            "parse_search": "stream or search validated local row occurrences",
        },
        "note": (
            "The Comptroller describes a statewide EPTS compilation but no "
            "public statewide download was found. Use the direct tool to "
            "prepare the request handoff or process a delivered artifact. "
            "Deed fields remain county-clerk pivots rather than instrument "
            "copies or title assertions."
        ),
    },
    TXGIO_LAND_PARCELS_SOURCE_ID: {
        "mode": "unified_bulk_release_and_local_archive_scan",
        "direct_tool": ("uv run python tools/query_txgio_land_parcels.py --help"),
        "native_keys": [
            "collection ID and resource ID",
            "county FIPS plus PROP_ID or GEO_ID",
            "artifact SHA-256 plus DBF record index",
        ],
        "shared_selectors": {
            "releases": "all published TxGIO collection IDs",
            "manifest": (
                "optional historical collection ID and optional county or "
                "explicit statewide archive selector"
            ),
            "probe": (
                "one county or statewide archive, with an optional historical "
                "collection ID"
            ),
            "download": (
                "one county or statewide archive, optional historical "
                "collection ID, and explicit destination"
            ),
            "local_search": (
                "downloaded --artifact-path plus any, owner, address, legal, "
                "or exact parcel selector"
            ),
        },
        "official_complements": query_txgio_land_parcels._alternatives(),
        "note": (
            "Remote shared operations discover and acquire source archives. "
            "Search, owner, address, parcel, and map scan a caller-supplied "
            "downloaded archive; they are not an indexed statewide service. "
            "Parcel keys remain separate from feature occurrences. Map "
            "returns the record-aligned shapefile reference without decoding "
            "or projecting coordinates. The published MapServer remains a "
            "metadata and interactive-map complement."
        ),
    },
    MONTANA_CADASTRAL_SOURCE_ID: {
        "mode": "unified_live_and_bulk_cadastral",
        "direct_tool": (
            "uv run python tools/query_montana_cadastral.py --help"
        ),
        "native_keys": [
            "GlobalID or OBJECTID feature occurrence",
            "nullable PARCELID parcel join",
            "PropertyID and AssessmentCode account aliases",
            "ORION CountyPrefix mapped explicitly to Census county GEOID",
            "rolling artifact filename, listing marker, size, and SHA-256",
        ],
        "shared_selectors": {
            "live_search": (
                "any, owner, address, parcel, or account selector with an "
                "OBJECTID keyset cursor"
            ),
            "point": "WGS84 longitude,latitude intersection",
            "count": "one live selector and optional county/tax-year filters",
            "discovery": "official complements or live 56-county coverage",
            "releases": "all current parcel and ORION release routes",
            "manifest": (
                "exact parcel-shp, parcel-gdb, or orion dataset plus optional "
                "county"
            ),
            "probe": (
                "live bounded contract probe, or exact bulk dataset and "
                "optional county"
            ),
            "download": (
                "exact bulk dataset, optional county, and explicit destination"
            ),
        },
        "official_complements": query_montana_cadastral.alternative_routes(),
        "note": (
            "The live layer projects selected assessment-roll and parcel "
            "geometry observations. GlobalID/OBJECTID remain feature "
            "occurrence identity; nullable PARCELID alone joins a parcel. "
            "ORION COUNTYCD is not Census FIPS. Bulk release, manifest, probe, "
            "and download results remain source envelopes until a format-aware "
            "archive decoder is used."
        ),
    },
    HARRIS_RECORDER_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_harris_recorder.py --help",
        "note": (
            "Unified instrument lookup resolves an exact Clerk file number; "
            "the direct adapter also exposes grantor, grantee, date, type, "
            "and legal-description selectors plus the separate image and "
            "bulk-product routes."
        ),
    },
    HARRIS_FORECLOSURE_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_harris_foreclosures.py --help"),
        "note": (
            "Unified search resolves an exact FRCL notice ID. The direct "
            "adapter also supports filing-month and sale-month census "
            "searches and anonymous official PDF downloads. Notice records "
            "are event evidence, not recorder title evidence."
        ),
    },
    ORANGE_TAX_COLLECTOR_SOURCE_ID: {
        "mode": "unified_current_portal_and_local_historical_bulk",
        "direct_tool": (
            "uv run python tools/query_orange_tax_collector.py --help"
        ),
        "county_geoid": query_orange_tax_collector.COUNTY_GEOID,
        "publication_paths": {
            "current": {
                "portal": query_orange_tax_collector.GOVHUB_PORTAL_URL,
                "index": query_orange_tax_collector.ALGOLIA_INDEX,
                "account_history_root": (
                    query_orange_tax_collector.TAXSYS_ROOT
                ),
            },
            "historical_bulk": {
                "official_page": (
                    query_orange_tax_collector.OFFICIAL_TAX_ROLL_PAGE
                ),
                "datasets": ["current", "delinquent"],
                "publication_date": (
                    query_orange_tax_collector.PUBLICATION_DATE
                ),
                "publication_state": "fixed_historical_snapshot",
            },
        },
        "shared_selectors": {
            "search": (
                "current general portal search, or local historical search "
                "with --artifact-path and --dataset-type"
            ),
            "owner": (
                "current general portal search, or the historical roll's "
                "owner fields when a local artifact is selected"
            ),
            "address": (
                "current general portal search, or a cross-field historical "
                "artifact match"
            ),
            "account": (
                "exact current account plus bill/certificate history, or an "
                "exact historical parcel-account match"
            ),
            "parcel": "the same exact 15-digit account route as account",
            "discovery": "complete current and historical capability contract",
            "releases": "both fixed historical publication manifests",
            "manifest": "both fixed historical publication manifests",
            "probe": (
                "one selected historical data artifact via --dataset-type; "
                "the source monitor checks the live portal separately"
            ),
            "download": (
                "one selected historical data artifact via --dataset-type "
                "and --destination"
            ),
        },
        "native_identity": {
            "parcel_join": "exact normalized 15-digit Orange account",
            "portal_occurrence": "Algolia objectID",
            "account_locator": "TaxSys account token",
            "bill_occurrence": "bill UUID",
            "certificate_occurrence": "certificate number",
            "payment_occurrence": [
                "receipt number",
                "validation number",
            ],
            "bulk_row_occurrence": [
                "artifact SHA-256",
                "archive member path",
                "source row number",
            ],
            "tax_summary_id": "separate source identifier",
        },
        "direct_only_operations": [
            "history without the resolved account hit",
            "bill detail by bill UUID",
            "historical bulk inspect",
            "historical layout-document probe or download",
        ],
        "official_complements": [
            "us-fl-dor-property-roll",
            "us-fl-orange-official-records",
            "us-fl-orange-comptroller-tax-deed-sales",
        ],
        "note": (
            "The current GovHub/TaxSys route and the two artifacts labeled as "
            "of 02/17/20 are different publication states. Although the landing "
            "page labels the bulk downloads Daily, the adapter retains the "
            "identified files as fixed 2020 snapshots. Owner, payer, buyer, "
            "balance, bill, and certificate labels remain source observations; "
            "object IDs, tokens, bill UUIDs, certificates, receipts, "
            "TaxSummaryID values, and row occurrences do not collapse into the "
            "parcel join."
        ),
    },
    PALM_BEACH_PROPERTY_SOURCE_ID: {
        "mode": "unified_live_county_gis",
        "direct_tool": (
            "uv run python "
            "tools/query_palm_beach_property_appraiser.py --help"
        ),
        "county_geoid": query_palm_beach_property_appraiser.COUNTY_GEOID,
        "native_search_fields": [
            "any",
            "parcel",
            "parid",
            "owner",
            "address",
            "sale",
            "legal",
            "property-use",
            "subdivision",
        ],
        "native_identity": {
            "feature_occurrence": "OBJECTID",
            "candidate_exact_tax_account_join": "PARCEL_NUMBER",
            "separate_geometry_or_group_identifier": "PARID",
            "identifier_uniqueness_assumed": False,
        },
        "traversal": (
            "OBJECTID-ordered ArcGIS pagination within a maximum-matching-"
            "OBJECTID boundary; omitted limits exhaust the bounded population"
        ),
        "representations": [
            {
                "name": "PARCEL_DETAILS",
                "url": query_palm_beach_property_appraiser.LAYER_URL,
                "role": "primary_query_and_ingestion_representation",
            },
            {
                "name": "PAO.PARCEL_QSALES",
                "url": query_palm_beach_property_appraiser.QSALES_LAYER_URL,
                "role": "same_publisher_sale-age_thematic_representation",
                "independent_corroboration": False,
                "exact_row_or_objectid_parity_established": False,
            },
        ],
        "official_complements": [
            {
                "source_id": PALM_BEACH_RECORDER_SOURCE_ID,
                "adds": [
                    "recorded_instrument_index",
                    "exact_book_page_pivot",
                    "document_representation",
                ],
            },
            {
                "source_id": query_palm_beach_property_appraiser.FL_DOR_SOURCE_ID,
                "adds": ["statewide_property_roll_bulk"],
            },
            {
                "kind": "pbc_tax_deeds",
                "url": "https://taxdeed.mypalmbeachclerk.com/",
                "adds": ["tax_deed_case_and_event"],
                "join_evidence": (
                    "The official detail/PAPA link demonstrates dashed and "
                    "undashed forms of the same 17-digit parcel number."
                ),
            },
            {
                "kind": "pbc_property_appraiser_flat_files",
                "url": (
                    query_palm_beach_property_appraiser
                    .PROPERTY_APPRAISER_DATA_URL
                ),
                "adds": ["advertised CAMA, NAL, situs, owner, and vector files"],
                "operation_access": (
                    "The current cloud-drive invitation has consent language "
                    "inconsistent with general anonymous reuse and is not "
                    "accepted or automated."
                ),
            },
        ],
        "note": (
            "Owner and last-sale values are assessment-layer observations, "
            "not recorded-title conclusions. Book/page values are exact Clerk "
            "search pivots rather than instrument copies. CONFID_FLG and blank "
            "owner/address values remain publisher redaction state. The "
            "flat-file invitation discrepancy affects that transfer route, "
            "not the anonymous GIS source."
        ),
    },
    PALM_BEACH_TAX_SOURCE_ID: {
        "mode": "unified_live_county_tax_account",
        "direct_tool": (
            "uv run python tools/query_palm_beach_tax_collector.py --help"
        ),
        "county_geoid": query_palm_beach_tax_collector.COUNTY_GEOID,
        "native_search_fields": [
            "simple",
            "owner",
            "owners",
            "parcel",
            "situs",
            "postal",
            "paid-status",
            "delivery",
        ],
        "native_identity": {
            "parcel_join": "17-digit Property Control Number",
            "tax_account_locator": "AlternateKey",
            "bill_occurrence": [
                "bill_id",
                "bill_number",
                "installment",
                "tax_year",
            ],
            "payment_occurrence": [
                "receipt_number",
                "bill_number",
                "effective_payment_date",
                "source_row_digest",
            ],
        },
        "source_search_boundary": {
            "publisher_setting": "maximumRecords",
            "observed_value": 300,
            "equal_total_is_partial": True,
            "adapter_selected_cap": False,
        },
        "shared_selectors": {
            "search": "simple or source-qualified account discovery",
            "owner": "Owner-qualified account discovery",
            "address": "Situs-qualified account discovery",
            "parcel": "exact full PCN discovery",
            "account": "exact PCN with AlternateKey resolved when omitted",
            "event": (
                "bill/installment by default; payment-history or receipt via "
                "--search-field"
            ),
            "discovery": "settings, sync routing, and official complements",
            "probe": "stable settings/routing plus one rolling exact-PCN sample",
        },
        "direct_only_operations": [
            "settings",
            "sync-status",
            "refresh",
            "bills",
            "payments",
            "bill-detail",
        ],
        "official_complements": (
            query_palm_beach_tax_collector.source_routes()[
                "complementary_routes"
            ]
        ),
        "note": (
            "PCN joins the county property sources; AlternateKey, bill IDs, "
            "bill numbers, installments, receipts, and payment occurrences do "
            "not collapse into that join. Current amounts, status, source "
            "flags, and last-updated labels are retrieved-state observations. "
            "Payer names remain payer observations, and Tax Collector owner "
            "labels are not recorded-title conclusions."
        ),
    },
    PALM_BEACH_TAX_DEEDS_SOURCE_ID: {
        "mode": "unified_live_county_tax_deed_case",
        "direct_tool": (
            "uv run python tools/query_palm_beach_tax_deeds.py --help"
        ),
        "county_geoid": query_palm_beach_tax_deeds.COUNTY_GEOID,
        "native_search_fields": [
            "case",
            "certificate",
            "parcel",
            "tax-collector",
            "applicant",
            "owner",
            "status",
            "sale-date",
            "lands-available",
        ],
        "native_identity": {
            "case_occurrence_locator": "portal row ID",
            "case_number": "tax-deed case number",
            "certificate_number": "tax certificate number",
            "parcel_join": "reversible 17-digit Property Control Number",
            "auction_event": ["portal row ID", "auction date"],
            "document_occurrence": [
                "portal row ID",
                "document inventory sequence",
                "image ID when available",
            ],
        },
        "traversal": (
            "session-backed form POST followed by all source-reported jqGrid "
            "pages; continuations bind the criteria, schema, totals, native "
            "page size, and first-page occurrence snapshot"
        ),
        "shared_selectors": {
            "search": (
                "case by default, or another native selector through "
                "--search-field"
            ),
            "owner": (
                "source-reported owner labels with --from-date and --to-date"
            ),
            "parcel": "exact PCN case discovery",
            "sale": (
                "source-published auction date or range; query is the from "
                "date and --to-date is optional"
            ),
            "event": "exact portal row detail and document inventory",
            "download": (
                "validated case/document membership using ROW_ID:IMAGE_ID and "
                "--destination"
            ),
            "discovery": "live selectors, rolling sale dates, and complements",
            "probe": "stable portal contract plus separate rolling observations",
        },
        "direct_only_operations": ["routes"],
        "official_complements": query_palm_beach_tax_deeds.official_routes(),
        "note": (
            "Portal row IDs, case numbers, certificates, PCNs, auction events, "
            "and document occurrences remain distinct identities. Status is a "
            "mutable Clerk lifecycle observation. Applicant and owner labels "
            "remain source-reported roles rather than current-title "
            "conclusions. Public PDFs are uncertified; certified copies use "
            "the separate Clerk route."
        ),
    },
    MASON_COUNTY_TAX_PARCELS_SOURCE_ID: {
        "mode": "unified_live_county_gis",
        "direct_tool": (
            "uv run python tools/query_mason_county_tax_parcels.py --help"
        ),
        "county_geoid": query_mason_county_tax_parcels.COUNTY_GEOID,
        "native_search_fields": [
            "any",
            "parcel",
            "owner",
            "address",
            "assessment",
            "afn",
            "subdivision",
        ],
        "native_identity": {
            "feature_occurrence": "FID",
            "parcel_join_candidates": ["PIN", "TERRA_PIN", "Taxlot"],
            "parcel_join_uniqueness": "not_assumed",
        },
        "traversal": (
            "returnIdsOnly snapshot sorted by FID, then objectIds batches; "
            "the layer does not support offset pagination or orderBy"
        ),
        "official_complements": [
            {
                "source_id": "us-wa-mason-county-taxsifter",
                "adds": [
                    "interactive assessor account",
                    "treasurer detail when accessible",
                ],
                "relationship": "same_county_property_system_family",
            },
            {
                "source_id": WASHINGTON_LAND_RECORDS_SOURCE_ID,
                "title_id": 56,
                "adds": ["recorded_instrument_index", "indexed_parties"],
                "relationship": "independent_county_auditor_archive",
            },
            {
                "kind": "mason_county_auditor_eagleweb",
                "url": (
                    "https://recording.masoncountywa.gov/recorder/web/"
                ),
                "adds": ["current_recorder_instrument_index"],
                "relationship": "independent_county_auditor_index",
            },
        ],
        "note": (
            "This is the field-oriented county GIS substitute for the "
            "challenge-observed TaxSifter route. It publishes current "
            "assessor/GIS names, addresses, values, identifiers, and parcel "
            "geometry. It does not publish recorder instruments or treasury "
            "balance/payment history, and its name field is not a recorded-"
            "title conclusion."
        ),
    },
    **{
        representation.source_id: {
            "mode": "unified_live",
            "direct_tool": ("uv run python tools/query_washington_parcels.py --help"),
            "lineage_id": WASHINGTON_PARCEL_LINEAGE_SOURCE_ID,
            "representation": representation.key,
            "representation_role": representation.role,
            "native_search_fields": [
                "parcel",
                "parcel-id",
                "original-parcel-id",
                "county",
                "fips",
                "situs",
                "land-use",
                "original-land-use",
            ],
            "official_complements": [
                {
                    "kind": "county_assessor_detail",
                    "discovered_from": "DATA_LINK",
                    "adds": [
                        "owner_or_taxpayer",
                        "mailing_address",
                        "tax_and_exemption_detail",
                        "sales_or_permit_detail_when_published",
                    ],
                }
            ],
            "note": (
                "This is one representation of the normalized Washington "
                "state/county parcel lineage. Ecology is the normal default; "
                "DNR and WISAARD comparisons measure representation health "
                "rather than independent corroboration. Current owner-field "
                "state is detected from each live schema and county DATA_LINK "
                "routes are preserved for richer detail."
            ),
        }
        for representation in query_washington_parcels.REPRESENTATIONS.values()
    },
    WASHINGTON_PARCEL_FRESHNESS_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": (
            "uv run python tools/query_washington_parcels.py county-freshness --help"
        ),
        "lineage_id": WASHINGTON_PARCEL_LINEAGE_SOURCE_ID,
        "native_search_fields": ["county"],
        "note": (
            "The companion table preserves each county partition's published "
            "file date separately from parcel values and schema contracts."
        ),
    },
    WASHINGTON_PARCEL_LAND_USE_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": (
            "uv run python tools/query_washington_parcels.py land-use-codes --help"
        ),
        "lineage_id": WASHINGTON_PARCEL_LINEAGE_SOURCE_ID,
        "native_search_fields": ["county", "code"],
        "note": (
            "The county-specific original land-use vocabulary joins parcel "
            "rows on COUNTY_NM plus CODE and remains separately attributable."
        ),
    },
    WASHINGTON_PARCEL_LINEAGE_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_washington_parcels.py --help"),
        "representations": [
            {
                "source_id": representation.source_id,
                "key": representation.key,
                "role": representation.role,
            }
            for representation in query_washington_parcels.REPRESENTATIONS.values()
        ],
        "parity_interpretation": "mirror_health_not_corroboration",
        "note": (
            "Use search to inspect all representation metadata, parity to "
            "compare the stable sentinel, and probe for bounded contract "
            "checks. WISAARD is optional and may contain older same-lineage "
            "county partitions."
        ),
    },
    WASHINGTON_TAXSIFTER_UMBRELLA_SOURCE_ID: {
        "mode": "county_routed_source_family",
        "direct_tool": (
            "uv run python tools/query_washington_taxsifter.py sources --json"
        ),
        "county_sources": [
            {
                "county": tenant.key,
                "county_geoid": tenant.county_geoid,
                "source_id": tenant.source_id,
                "access_state": tenant.access_state,
            }
            for tenant in query_washington_taxsifter.TENANTS
        ],
        "native_search_semantics": (
            "one general parcel, owner-name, or address query box"
        ),
        "native_identity": (
            "leaf source_id plus keyId/typeID account occurrence; "
            "county GEOID plus parcel number is the cross-source parcel join"
        ),
        "sales_pagination": query_washington_taxsifter.SALES_PAGINATION_STATE,
        "lineages": {
            "assessor": query_washington_taxsifter.ASSESSOR_LINEAGE,
            "treasurer": query_washington_taxsifter.TREASURER_LINEAGE,
            "recorder": query_washington_taxsifter.RECORDER_LINEAGE,
            "map": query_washington_taxsifter.MAP_LINEAGE,
        },
        "note": (
            "Select a county for the family route. Parcel/account detail "
            "combines separately labeled assessor, treasurer, and appraisal "
            "representations. Assessor sale rows retain their current-response "
            "pagination observation and recorder identifiers remain candidate "
            "joins to a separately sourced instrument index."
        ),
    },
    **{
        tenant.source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_washington_taxsifter.py --help"
            ),
            "county": tenant.key,
            "county_geoid": tenant.county_geoid,
            "access_state": tenant.access_state,
            "native_search_semantics": (
                "one general parcel, owner-name, or address query box"
            ),
            "native_identity": {
                "account_occurrence": "source_id + keyId + typeID",
                "parcel_join": "county_geoid + parcel_number",
            },
            "sales_pagination": {
                "state": query_washington_taxsifter.SALES_PAGINATION_STATE,
                "note": query_washington_taxsifter.SALES_PAGINATION_NOTE,
            },
            "lineages": {
                "assessor": query_washington_taxsifter.ASSESSOR_LINEAGE,
                "treasurer": query_washington_taxsifter.TREASURER_LINEAGE,
                "recorder": query_washington_taxsifter.RECORDER_LINEAGE,
                "map": query_washington_taxsifter.MAP_LINEAGE,
            },
            "official_alternatives": (
                _washington_taxsifter_alternatives(tenant)
            ),
            "note": (
                "Owner and address routes use the county portal's native "
                "general query. Exact parcel/account detail returns source-"
                "labeled assessor, treasurer, and appraisal representations. "
                "Sales are assessor observations, not recorded instruments."
            ),
        }
        for tenant in query_washington_taxsifter.TENANTS
    },
    query_dc_property.ITSPE_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_dc_property.py assessment --help",
        "lineage_id": query_dc_property.LINEAGE_ID,
        "native_search_fields": ["ssl", "owner", "address", "instrument"],
        "official_complements": [
            {
                "source_id": query_dc_property.OWNER_POLYGON_SOURCE_ID,
                "adds": ["common_ownership_polygon_geometry"],
            },
            {
                "source_id": query_dc_property.RECORDER_SOURCE_ID,
                "adds": ["recorded_instrument_index", "document_images"],
                "join_field": "instrument_number",
            },
        ],
        "note": (
            "ITSPE is the full assessment and tax-account extract. Its "
            "instrument field is a join to the separately sourced Recorder "
            "index, not a substitute for that index."
        ),
    },
    query_dc_property.OWNER_POLYGON_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_dc_property.py geometry --help",
        "lineage_id": query_dc_property.LINEAGE_ID,
        "native_search_fields": [
            "ssl",
            "owner",
            "address",
            "instrument",
            "objectid",
        ],
        "note": (
            "The common-ownership layer supplies physical-land geometry and "
            "a daily ITSPE view. Its 137,400 polygons have different grain "
            "from the 221,400 ITSPE accounts, and overlapping values share "
            "the ITSPE lineage."
        ),
    },
    query_dc_property.SALES_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_dc_property.py sales --help",
        "lineage_id": query_dc_property.LINEAGE_ID,
        "native_search_fields": ["ssl"],
        "note": (
            "CAMA rows are assessor-system sale observations joined by SSL. "
            "They preserve sale qualification and price and do not replace "
            "the Recorder instrument index."
        ),
    },
    query_dc_property.SURVEY_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_dc_property.py surveys --help",
        "lineage_id": query_dc_property.LINEAGE_ID,
        "native_search_fields": ["ssl", "document", "type", "book"],
        "note": (
            "SurDocs provides survey and plat metadata plus official viewer "
            "links. It is a survey/plat complement, not the Recorder "
            "instrument index."
        ),
    },
    query_dc_property.LINEAGE_ID: {
        "mode": "catalog_lineage",
        "direct_tool": "uv run python tools/query_dc_property.py sources --json",
        "components": [
            {
                "source_id": component.source_id,
                "component": component.key,
                "role": component.role,
            }
            for component in query_dc_property.COMPONENTS.values()
        ],
        "join_key": "SSL",
        "account_polygon_cardinality": "not_assumed_one_to_one",
        "note": (
            "The lineage entry describes the four separately attributable "
            "DCGIS components and their SSL joins."
        ),
    },
    query_dc_property.RECORDER_SOURCE_ID: {
        "mode": "registered_source_route",
        "direct_tool": "https://washington.dc.publicsearch.us/",
        "authentication": "registered_user",
        "coverage_start": "August 1921",
        "note": (
            "The Recorder PublicSearch portal is the actual instrument index. "
            "Registration provides free search and image viewing; downloads "
            "are purchased separately. CAMA instrument joins and SurDocs "
            "survey records remain useful when this account route is not "
            "available."
        ),
    },
    ACRIS_IMAGES_SOURCE_ID: {
        "mode": "action_planning",
        "direct_tool": (
            "uv run python tools/public_records_actions.py plan "
            "us-nyc-acris-images --operation open_selected_image "
            "--selector DOCUMENT_ID"
        ),
        "note": (
            "Image viewing and copy-service work is represented through "
            "catalog-backed actions."
        ),
    },
}


def _source_guidance(source_id: str) -> dict[str, Any]:
    guidance = dict(
        DIRECT_TOOL_GUIDANCE.get(
            source_id,
            {
                "mode": "catalog_only",
            },
        )
    )
    guidance["unified_operations"] = sorted(LIVE_ROUTES.get(source_id, {}))
    return guidance


def _jurisdiction(value: str | None) -> JurisdictionMetadata:
    value = str(value or "").strip()
    state_code = None
    county_fips = None
    name = "Local normalized property records"
    if value:
        name = f"Property jurisdiction {value}"
        if value.startswith("37"):
            state_code = "NC"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("48"):
            state_code = "TX"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("12"):
            state_code = "FL"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("13"):
            state_code = "GA"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("22"):
            state_code = "LA"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("08"):
            state_code = "CO"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("11"):
            state_code = "DC"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("26"):
            state_code = "MI"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("30"):
            state_code = "MT"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("39"):
            state_code = "OH"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("41"):
            state_code = "OR"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("42"):
            state_code = "PA"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("51"):
            state_code = "VA"
            county_fips = value if len(value) == 5 else None
        elif value.startswith("53"):
            state_code = "WA"
            county_fips = value if len(value) == 5 else None
        elif value == "78":
            state_code = "VI"
    return JurisdictionMetadata(
        jurisdiction_id=value or "local",
        name=name,
        state_code=state_code,
        county_fips=county_fips,
    )


def _query(
    source: SourceMetadata,
    operation: str,
    selector: str | None,
    args: argparse.Namespace,
) -> PublicRecordsQuery:
    parameters = {
        "selector": selector,
        "source": getattr(args, "source", None),
        "jurisdiction": getattr(args, "jurisdiction", None),
        "tax_year": getattr(args, "tax_year", None),
        "department": getattr(args, "department", None),
        "process_stage": getattr(args, "process_stage", None),
        "search_field": getattr(args, "search_field", None),
    }
    return PublicRecordsQuery(
        source=source,
        jurisdiction=_jurisdiction(getattr(args, "jurisdiction", None)),
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    prefix = "sqlite:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError("local cursor must have form sqlite:offset:N")
    return int(cursor[len(prefix) :])


def _next_cursor(
    offset: int, limit: int, rows: list[sqlite3.Row]
) -> tuple[list[sqlite3.Row], str | None]:
    if len(rows) <= limit:
        return rows, None
    return rows[:limit], f"sqlite:offset:{offset + limit}"


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _json_value(raw: Any) -> Any:
    if raw in (None, ""):
        return None
    try:
        return json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return raw


def _parcel_record(row: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(row)
    source_id = str(row["source_id"])
    geoid = str(row["jurisdiction_geoid"])
    native_id = str(row["native_parcel_id"])
    return {
        "canonical_ref": canonical_property_ref(source_id, geoid, "parcel", native_id),
        "parcel_id": row["parcel_id"],
        "source_id": source_id,
        "jurisdiction_geoid": geoid,
        "jurisdiction_name": row.get("jurisdiction_name"),
        "native_parcel_id": native_id,
        "roll_year": row.get("roll_year") or None,
        "effective_from": row.get("effective_from"),
        "effective_to": row.get("effective_to"),
        "source_good_through": row.get("source_good_through"),
    }


def _local_owner(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions = [
        "(oa.raw_owner_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR oa.normalized_owner_name LIKE ? ESCAPE '\\' COLLATE NOCASE)"
    ]
    params: list[Any] = [_like(selector), _like(selector)]
    if args.jurisdiction:
        conditions.append("p.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    if args.tax_year is not None:
        conditions.append("p.roll_year=?")
        params.append(str(args.tax_year))
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT p.*, j.name AS jurisdiction_name,
               oa.ownership_assertion_id, oa.assertion_type,
               oa.raw_owner_name, oa.normalized_owner_name,
               oa.effective_from AS owner_effective_from,
               oa.effective_to AS owner_effective_to,
               oa.confidence, oa.claim_type, oa.evidence_ref, oa.source_quote
        FROM ownership_assertion oa
        JOIN parcel_snapshot p USING(parcel_id)
        JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
        WHERE {" AND ".join(conditions)}
        ORDER BY oa.raw_owner_name, p.jurisdiction_geoid,
                 p.native_parcel_id, oa.effective_from DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        record = _parcel_record(row)
        record["matched_owner"] = {
            "ownership_assertion_id": row["ownership_assertion_id"],
            "raw_name": row["raw_owner_name"],
            "normalized_name": row["normalized_owner_name"],
            "assertion_type": row["assertion_type"],
            "effective_from": row["owner_effective_from"] or None,
            "effective_to": row["owner_effective_to"],
            "confidence": row["confidence"],
            "claim_type": row["claim_type"],
            "evidence_ref": row["evidence_ref"],
            "source_quote": row["source_quote"],
        }
        records.append(record)
    return records, cursor


def _local_address(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions = [
        "(pa.raw_address LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR pa.normalized_address LIKE ? ESCAPE '\\' COLLATE NOCASE)"
    ]
    params: list[Any] = [_like(selector), _like(selector)]
    if args.jurisdiction:
        conditions.append("p.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    if args.tax_year is not None:
        conditions.append("p.roll_year=?")
        params.append(str(args.tax_year))
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT p.*, j.name AS jurisdiction_name,
               pa.address_id, pa.address_role, pa.raw_address,
               pa.normalized_address, pa.city, pa.state, pa.postal_code,
               pa.effective_from AS address_effective_from,
               pa.effective_to AS address_effective_to
        FROM parcel_address pa
        JOIN parcel_snapshot p USING(parcel_id)
        JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
        WHERE {" AND ".join(conditions)}
        ORDER BY pa.raw_address, p.jurisdiction_geoid, p.native_parcel_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        record = _parcel_record(row)
        record["matched_address"] = {
            "address_id": row["address_id"],
            "role": row["address_role"],
            "raw": row["raw_address"],
            "normalized": row["normalized_address"],
            "city": row["city"],
            "state": row["state"],
            "postal_code": row["postal_code"],
            "effective_from": row["address_effective_from"] or None,
            "effective_to": row["address_effective_to"],
        }
        records.append(record)
    return records, cursor


def _local_parcel(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions = [
        "(p.native_parcel_id=? OR EXISTS("
        "SELECT 1 FROM parcel_alias pa "
        "WHERE pa.parcel_id=p.parcel_id AND pa.alias_value=?))"
    ]
    params: list[Any] = [selector, selector]
    if args.jurisdiction:
        conditions.append("p.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    if args.tax_year is not None:
        conditions.append("p.roll_year=?")
        params.append(str(args.tax_year))
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT p.*, j.name AS jurisdiction_name
        FROM parcel_snapshot p
        JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
        WHERE {" AND ".join(conditions)}
        ORDER BY p.jurisdiction_geoid, p.native_parcel_id, p.roll_year DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        record = _parcel_record(row)
        record["aliases"] = [
            {
                "type": alias["alias_type"],
                "value": alias["alias_value"],
                "source_id": alias["source_id"],
                "effective_from": alias["effective_from"] or None,
                "effective_to": alias["effective_to"],
            }
            for alias in db.execute(
                """
                SELECT * FROM parcel_alias
                WHERE parcel_id=? ORDER BY alias_type, alias_value
                """,
                (row["parcel_id"],),
            )
        ]
        record["addresses"] = [
            {
                "role": address["address_role"],
                "raw": address["raw_address"],
                "normalized": address["normalized_address"],
                "city": address["city"],
                "state": address["state"],
                "postal_code": address["postal_code"],
            }
            for address in db.execute(
                """
                SELECT * FROM parcel_address
                WHERE parcel_id=? ORDER BY address_role, address_id
                """,
                (row["parcel_id"],),
            )
        ]
        record["tax_events"] = [
            {
                "tax_event_id": event["tax_event_id"],
                "source_id": event["source_id"],
                "tax_year": event["tax_year"],
                "event_type": event["event_type"],
                "event_date": event["event_date"],
                "amount_minor": event["amount_minor"],
                "currency": event["currency"],
                "status": event["status"],
                "native_event_id": event["native_event_id"],
                "raw": _json_value(event["raw_json"]),
            }
            for event in db.execute(
                """
                SELECT * FROM tax_account_event
                WHERE parcel_id=?
                ORDER BY event_date DESC, tax_event_id DESC
                """,
                (row["parcel_id"],),
            )
        ]
        records.append(record)
    return records, cursor


def _local_event(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    pattern = _like(selector)
    conditions = [
        "("
        "pe.native_event_id=? OR pe.source_record_id=? "
        "OR pe.event_type LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR pe.description LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR pe.status LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR pe.address_raw LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR pe.map_taxlot_candidate=? "
        "OR EXISTS(SELECT 1 FROM property_event_parcel_join_key pjk "
        "WHERE pjk.event_id=pe.event_id "
        "AND pjk.normalized_parcel_id=?) "
        "OR pe.normalized_case_number=? "
        "OR pe.event_date=? "
        "OR EXISTS(SELECT 1 FROM property_event_party pp "
        "WHERE pp.event_id=pe.event_id "
        "AND pp.raw_name LIKE ? ESCAPE '\\' COLLATE NOCASE)"
        ")"
    ]
    params: list[Any] = [
        selector,
        selector,
        pattern,
        pattern,
        pattern,
        pattern,
        re.sub(r"[^0-9A-Z]", "", selector.upper()),
        re.sub(r"[^0-9A-Z]", "", selector.upper()),
        re.sub(r"[^0-9A-Z]", "", selector.upper()),
        selector,
        pattern,
    ]
    if args.jurisdiction:
        conditions.append("pe.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT pe.*, j.name AS jurisdiction_name,
               pl.parcel_id, pl.link_method, pl.link_confidence,
               pl.evidence_json
        FROM property_event pe
        JOIN jurisdiction j ON j.geoid=pe.jurisdiction_geoid
        LEFT JOIN property_event_parcel_link pl ON pl.event_id=pe.event_id
        WHERE {" AND ".join(conditions)}
        ORDER BY COALESCE(
                     pe.last_update_date,
                     pe.approved_date,
                     pe.submitted_date,
                     pe.event_date
                 ) DESC,
                 pe.native_event_id,
                 pe.source_record_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records: list[dict[str, Any]] = []
    for row in rows:
        event_id = int(row["event_id"])
        raw_event = _json_value(row["raw_json"])
        source_canonical_ref = (
            str(raw_event.get("canonical_ref")).strip()
            if isinstance(raw_event, Mapping) and raw_event.get("canonical_ref")
            else None
        )
        record = {
            "canonical_ref": (
                source_canonical_ref
                or canonical_property_ref(
                    row["source_id"],
                    row["jurisdiction_geoid"],
                    row["record_kind"],
                    f"{row['native_event_id']}:{row['source_record_id']}",
                )
            ),
            "event_id": event_id,
            "source_id": row["source_id"],
            "jurisdiction_geoid": row["jurisdiction_geoid"],
            "jurisdiction_name": row["jurisdiction_name"],
            "record_kind": row["record_kind"],
            "native_event_id": row["native_event_id"],
            "source_record_id": row["source_record_id"],
            "event_type": row["event_type"],
            "description": row["description"],
            "status": row["status"],
            "status_category": row["status_category"],
            "event_date": row["event_date"],
            "normalized_case_number": row["normalized_case_number"],
            "event_dates": {
                "event": row["event_date"],
                "submitted": row["submitted_date"],
                "approved": row["approved_date"],
                "last_update": row["last_update_date"],
            },
            "estimated_cost_minor": row["estimated_cost_minor"],
            "currency": row["currency"],
            "address": row["address_raw"],
            "map_taxlot_candidate": row["map_taxlot_candidate"],
            "point": (
                {
                    "longitude": row["longitude"],
                    "latitude": row["latitude"],
                    "crs": row["geometry_crs"],
                    "source_role": "published_event_location",
                }
                if row["longitude"] is not None and row["latitude"] is not None
                else None
            ),
            "parcel_link": {
                "parcel_id": row["parcel_id"],
                "method": row["link_method"],
                "confidence": row["link_confidence"],
                "evidence": _json_value(row["evidence_json"]),
            },
            "parties": [
                {
                    "role": party["role"],
                    "raw_name": party["raw_name"],
                    "normalized_name": party["normalized_name"],
                    "assertion_type": party["assertion_type"],
                }
                for party in db.execute(
                    """
                    SELECT role, raw_name, normalized_name, assertion_type
                    FROM property_event_party
                    WHERE event_id=?
                    ORDER BY sequence_no, event_party_id
                    """,
                    (event_id,),
                )
            ],
            "representations": [
                {
                    "kind": representation["representation_kind"],
                    "url": representation["source_url"],
                    "relationship": representation["relationship"],
                    "source_state": representation["source_state"],
                }
                for representation in db.execute(
                    """
                    SELECT representation_kind, source_url, relationship,
                           source_state
                    FROM property_event_representation
                    WHERE event_id=?
                    ORDER BY representation_id
                    """,
                    (event_id,),
                )
            ],
            "relations": [
                {
                    "relationship": relation["relationship"],
                    "related_event_id": relation["related_event_id"],
                    "related_source_id": relation["related_source_id"],
                    "independent_corroboration": bool(
                        relation["independent_corroboration"]
                    ),
                    "normalized_case_number": relation[
                        "normalized_case_number"
                    ],
                    "event_date": relation["event_date"],
                    "overlapping_parcels": _json_value(
                        relation["overlapping_parcels_json"]
                    ),
                    "evidence": _json_value(relation["evidence_json"]),
                }
                for relation in db.execute(
                    """
                    SELECT r.relationship, r.independent_corroboration,
                           r.normalized_case_number, r.event_date,
                           r.overlapping_parcels_json, r.evidence_json,
                           CASE
                               WHEN r.event_id=? THEN r.related_event_id
                               ELSE r.event_id
                           END AS related_event_id,
                           CASE
                               WHEN r.event_id=? THEN right_event.source_id
                               ELSE left_event.source_id
                           END AS related_source_id
                    FROM property_event_relation r
                    JOIN property_event left_event
                      ON left_event.event_id=r.event_id
                    JOIN property_event right_event
                      ON right_event.event_id=r.related_event_id
                    WHERE r.event_id=? OR r.related_event_id=?
                    ORDER BY r.relation_id
                    """,
                    (event_id, event_id, event_id, event_id),
                )
            ],
            "raw": raw_event,
        }
        records.append(record)
    return records, cursor


def _local_instrument(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    pattern = _like(selector)
    conditions = [
        "(ri.native_document_id=? "
        "OR ri.legal_description_raw LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR EXISTS(SELECT 1 FROM instrument_party ip "
        "WHERE ip.instrument_id=ri.instrument_id "
        "AND (ip.raw_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR ip.normalized_name LIKE ? ESCAPE '\\' COLLATE NOCASE)))"
    ]
    params: list[Any] = [selector, pattern, pattern, pattern]
    if args.jurisdiction:
        conditions.append("ri.jurisdiction_geoid=?")
        params.append(args.jurisdiction)
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT ri.*, j.name AS jurisdiction_name
        FROM recorded_instrument ri
        JOIN jurisdiction j ON j.geoid=ri.jurisdiction_geoid
        WHERE {" AND ".join(conditions)}
        ORDER BY ri.recording_date DESC, ri.native_document_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        parties = [
            {
                "sequence": party["sequence_no"],
                "role": party["role"],
                "raw_name": party["raw_name"],
                "normalized_name": party["normalized_name"],
                "raw_address": party["raw_address"],
            }
            for party in db.execute(
                """
                SELECT * FROM instrument_party
                WHERE instrument_id=? ORDER BY sequence_no, instrument_party_id
                """,
                (row["instrument_id"],),
            )
        ]
        parcels = [
            {
                **_parcel_record(parcel),
                "link_method": parcel["link_method"],
                "link_confidence": parcel["link_confidence"],
            }
            for parcel in db.execute(
                """
                SELECT p.*, j.name AS jurisdiction_name,
                       ip.link_method, ip.link_confidence
                FROM instrument_parcel ip
                JOIN parcel_snapshot p USING(parcel_id)
                JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
                WHERE ip.instrument_id=?
                ORDER BY p.jurisdiction_geoid, p.native_parcel_id
                """,
                (row["instrument_id"],),
            )
        ]
        records.append(
            {
                "canonical_ref": canonical_property_ref(
                    row["source_id"],
                    row["jurisdiction_geoid"],
                    "instrument",
                    row["native_document_id"],
                ),
                "instrument_id": row["instrument_id"],
                "source_id": row["source_id"],
                "jurisdiction_geoid": row["jurisdiction_geoid"],
                "jurisdiction_name": row["jurisdiction_name"],
                "native_document_id": row["native_document_id"],
                "instrument_type": row["instrument_type"],
                "book": row["book"],
                "page": row["page"],
                "execution_date": row["execution_date"],
                "recording_date": row["recording_date"],
                "consideration_minor": row["consideration_minor"],
                "currency": row["currency"],
                "legal_description_raw": row["legal_description_raw"],
                "source_url": row["source_url"],
                "parties": parties,
                "parcels": parcels,
            }
        )
    return records, cursor


def _find_parcels(
    db,
    selector: str,
    jurisdiction: str | None,
    tax_year: int | None,
    limit: int,
) -> list[sqlite3.Row]:
    conditions = [
        "(p.native_parcel_id=? OR EXISTS("
        "SELECT 1 FROM parcel_alias pa "
        "WHERE pa.parcel_id=p.parcel_id AND pa.alias_value=?))"
    ]
    params: list[Any] = [selector, selector]
    if jurisdiction:
        conditions.append("p.jurisdiction_geoid=?")
        params.append(jurisdiction)
    if tax_year is not None:
        conditions.append("p.roll_year=?")
        params.append(str(tax_year))
    params.append(limit)
    return db.execute(
        f"""
        SELECT p.*, j.name AS jurisdiction_name
        FROM parcel_snapshot p
        JOIN jurisdiction j ON j.geoid=p.jurisdiction_geoid
        WHERE {" AND ".join(conditions)}
        ORDER BY p.roll_year DESC LIMIT ?
        """,
        params,
    ).fetchall()


def _local_chain(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], None]:
    records = []
    for parcel in _find_parcels(
        db,
        selector,
        args.jurisdiction,
        args.tax_year,
        args.limit,
    ):
        parcel_id = parcel["parcel_id"]
        owners = [
            dict(row)
            for row in db.execute(
                """
                SELECT ownership_assertion_id, assertion_type, raw_owner_name,
                       normalized_owner_name, effective_from, effective_to,
                       confidence, claim_type, evidence_ref, source_quote
                FROM ownership_assertion
                WHERE parcel_id=?
                ORDER BY effective_from, ownership_assertion_id
                """,
                (parcel_id,),
            )
        ]
        sales = [
            {
                **dict(row),
                "raw": _json_value(row["raw_json"]),
            }
            for row in db.execute(
                """
                SELECT sale_event_id, source_id, native_sale_id, sale_date,
                       execution_date, recording_date, consideration_minor,
                       currency, qualification_code, derivation, instrument_id,
                       raw_json
                FROM sale_event
                WHERE parcel_id=?
                ORDER BY COALESCE(recording_date, execution_date, sale_date),
                         sale_event_id
                """,
                (parcel_id,),
            )
        ]
        instruments = [
            {
                "canonical_ref": canonical_property_ref(
                    row["source_id"],
                    row["jurisdiction_geoid"],
                    "instrument",
                    row["native_document_id"],
                ),
                **dict(row),
            }
            for row in db.execute(
                """
                SELECT ri.instrument_id, ri.source_id, ri.jurisdiction_geoid,
                       ri.native_document_id, ri.instrument_type,
                       ri.execution_date, ri.recording_date,
                       ri.consideration_minor, ri.currency,
                       ip.link_method, ip.link_confidence
                FROM instrument_parcel ip
                JOIN recorded_instrument ri USING(instrument_id)
                WHERE ip.parcel_id=?
                ORDER BY COALESCE(ri.recording_date, ri.execution_date),
                         ri.instrument_id
                """,
                (parcel_id,),
            )
        ]
        lineage = [
            dict(row)
            for row in db.execute(
                """
                SELECT predecessor_parcel_id, successor_parcel_id,
                       relationship, effective_date, source_id, evidence_ref
                FROM parcel_lineage
                WHERE predecessor_parcel_id=? OR successor_parcel_id=?
                ORDER BY effective_date
                """,
                (parcel_id, parcel_id),
            )
        ]
        gap_flags = []
        if not instruments:
            gap_flags.append("no_recorded_instrument_coverage")
        if owners and all(
            owner["assertion_type"] == "assessment_roll" for owner in owners
        ):
            gap_flags.append("assessment_owner_observations_only")
        if any(sale["instrument_id"] is None for sale in sales):
            gap_flags.append("sale_without_instrument_link")
        record = _parcel_record(parcel)
        record.update(
            {
                "ownership_assertions": owners,
                "sale_events": sales,
                "recorded_instruments": instruments,
                "parcel_lineage": lineage,
                "chain_analysis": {
                    "claim_type": "synthesis",
                    "confidence_ceiling": "medium",
                    "gap_flags": gap_flags,
                    "complete_chain_claimed": False,
                },
            }
        )
        records.append(record)
    return records, None


def _local_map(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], None]:
    records = []
    for parcel in _find_parcels(
        db,
        selector,
        args.jurisdiction,
        args.tax_year,
        args.limit,
    ):
        for geometry in db.execute(
            """
            SELECT geometry_id, geometry_ref, geometry_format, crs,
                   source_resolution, accuracy_disclaimer, source_id,
                   snapshot_date
            FROM parcel_geometry
            WHERE parcel_id=?
            ORDER BY snapshot_date DESC, geometry_id DESC
            """,
            (parcel["parcel_id"],),
        ):
            record = _parcel_record(parcel)
            record["geometry"] = dict(geometry)
            record["geometry"]["surveyed_legal_boundary"] = False
            records.append(record)
    return records, None


LOCAL_HANDLERS: dict[
    str,
    Callable[
        [sqlite3.Connection, str, argparse.Namespace],
        tuple[list[dict[str, Any]], str | None],
    ],
] = {
    "search": _local_owner,
    "owner": _local_owner,
    "address": _local_address,
    "parcel": _local_parcel,
    "event": _local_event,
    "instrument": _local_instrument,
    "chain": _local_chain,
    "map": _local_map,
}


_PROPERTY_OPERATION_ALIASES = {
    "search": {"search", "owner", "party", "party_search"},
    "owner": {"owner", "party", "party_search"},
    "address": {"address", "address_search"},
    "account": {"account"},
    "parcel": {"parcel", "parcel_search"},
    "event": {"event", "record", "property_event"},
    "instrument": {"instrument", "document", "document_search"},
    "chain": {"chain", "history"},
    "map": {"map", "parcel"},
}
_SELECTOR_PARAMETER_KEYS = (
    "selector",
    "query",
    "assessment_no",
    "document_id",
    "parcel_id",
    "party_name",
    "owner",
    "address",
)


def _normalized_selector(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _property_query_evidence(
    observation: Mapping[str, Any],
    args: argparse.Namespace,
    selector: str,
) -> dict[str, Any] | None:
    observation = dict(observation)
    raw = _json_value(observation.get("raw_json"))
    if not isinstance(raw, Mapping):
        return None
    query = raw.get("query")
    if not isinstance(query, Mapping):
        return None
    source = query.get("source")
    jurisdiction = query.get("jurisdiction")
    metadata = query.get("query")
    if not all(
        isinstance(value, Mapping) for value in (source, jurisdiction, metadata)
    ):
        return None
    if source.get("source_id") != observation.get("source_id"):
        return None
    if query.get("fingerprint") != observation.get("query_fingerprint"):
        return None

    operation = str(metadata.get("operation") or "").strip().casefold()
    if operation not in _PROPERTY_OPERATION_ALIASES.get(args.command, {args.command}):
        return None
    parameters = metadata.get("parameters")
    if not isinstance(parameters, Mapping):
        return None
    selectors = {
        _normalized_selector(parameters.get(key))
        for key in _SELECTOR_PARAMETER_KEYS
        if parameters.get(key) not in (None, "")
    }
    if {
        "borough",
        "block",
        "lot",
    }.issubset(parameters) and all(
        parameters.get(key) not in (None, "") for key in ("borough", "block", "lot")
    ):
        selectors.add(
            _normalized_selector(
                f"{parameters['borough']}-{parameters['block']}-{parameters['lot']}"
            )
        )
    if _normalized_selector(selector) not in selectors:
        return None

    evidence_jurisdiction = str(jurisdiction.get("jurisdiction_id") or "").strip()
    requested_jurisdiction = str(args.jurisdiction or "").strip()
    if not requested_jurisdiction or evidence_jurisdiction != requested_jurisdiction:
        return None

    evidence_tax_year = next(
        (
            parameters.get(key)
            for key in ("tax_year", "roll_year", "assessment_year")
            if parameters.get(key) not in (None, "")
        ),
        None,
    )
    if args.tax_year is None:
        if evidence_tax_year is not None:
            return None
    elif str(evidence_tax_year or "") != str(args.tax_year):
        return None

    records = raw.get("records")
    complete_zero = (
        observation.get("access_status") == ResultStatus.NO_RESULTS.value
        and raw.get("status") == ResultStatus.NO_RESULTS.value
        and records == []
        and raw.get("next_cursor") is None
        and metadata.get("cursor") is None
        and bool(observation.get("retrieved_at"))
    )
    return {
        "source_id": observation["source_id"],
        "status": observation["access_status"],
        "retrieved_at": observation["retrieved_at"],
        "query_fingerprint": observation["query_fingerprint"],
        "jurisdiction": evidence_jurisdiction,
        "operation": operation,
        "tax_year": evidence_tax_year,
        "complete_zero": complete_zero,
    }


def _property_route_guidance(args: argparse.Namespace) -> dict[str, Any]:
    guidance: dict[str, Any] = {
        "discover": (
            "uv run python tools/query_property.py sources "
            "[--jurisdiction GEOID] --output FILE"
        ),
        "select_source": "--source SOURCE_ID",
        "catalog_sources": [],
    }
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        for source in catalog.list_sources(
            domain="property",
            jurisdiction=args.jurisdiction,
        ):
            source_id = source["source_id"]
            decision = catalog.machine_acquisition_decision(source_id)
            guidance["catalog_sources"].append(
                {
                    "source_id": source_id,
                    "official_url": source.get("official_url"),
                    "acquisition_status": acquisition_result_status(decision),
                    "query_guidance": _source_guidance(source_id),
                }
            )
    except (CatalogError, sqlite3.Error, ValueError) as error:
        guidance["catalog_error"] = str(error)
    return guidance


def _property_local_coverage(
    db: sqlite3.Connection,
    args: argparse.Namespace,
    selector: str,
) -> dict[str, Any]:
    row_counts = {
        "query_envelopes": int(
            db.execute(
                """
                SELECT COUNT(*) FROM source_observation
                WHERE record_kind='query_envelope'
                """
            ).fetchone()[0]
        ),
        "parcels": int(
            db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0]
        ),
        "instruments": int(
            db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0]
        ),
    }
    requested_jurisdiction = str(args.jurisdiction or "").strip()
    jurisdiction_counts = {"parcels": 0, "instruments": 0}
    source_ids: set[str] = set()
    if requested_jurisdiction:
        jurisdiction_counts = {
            "parcels": int(
                db.execute(
                    """
                    SELECT COUNT(*) FROM parcel_snapshot
                    WHERE jurisdiction_geoid=?
                    """,
                    (requested_jurisdiction,),
                ).fetchone()[0]
            ),
            "instruments": int(
                db.execute(
                    """
                    SELECT COUNT(*) FROM recorded_instrument
                    WHERE jurisdiction_geoid=?
                    """,
                    (requested_jurisdiction,),
                ).fetchone()[0]
            ),
        }
        source_ids.update(
            str(row[0])
            for row in db.execute(
                """
                SELECT DISTINCT source_id FROM parcel_snapshot
                WHERE jurisdiction_geoid=?
                UNION
                SELECT DISTINCT source_id FROM recorded_instrument
                WHERE jurisdiction_geoid=?
                """,
                (requested_jurisdiction, requested_jurisdiction),
            )
        )
    else:
        source_ids.update(
            str(row[0])
            for row in db.execute(
                """
                SELECT DISTINCT source_id FROM parcel_snapshot
                UNION
                SELECT DISTINCT source_id FROM recorded_instrument
                """
            )
        )

    matching_evidence: list[dict[str, Any]] = []
    observed_requested_scope = False
    observations = db.execute(
        """
        SELECT observation_id, source_id, query_fingerprint, retrieved_at,
               access_status, raw_json
        FROM source_observation
        WHERE record_kind='query_envelope'
        ORDER BY retrieved_at DESC, observation_id DESC
        """
    ).fetchall()
    for observation in observations:
        raw = _json_value(observation["raw_json"])
        if isinstance(raw, Mapping):
            raw_query = raw.get("query")
            raw_jurisdiction = (
                raw_query.get("jurisdiction")
                if isinstance(raw_query, Mapping)
                else None
            )
            observed_geoid = (
                str(raw_jurisdiction.get("jurisdiction_id") or "").strip()
                if isinstance(raw_jurisdiction, Mapping)
                else ""
            )
            if requested_jurisdiction and observed_geoid == requested_jurisdiction:
                observed_requested_scope = True
                source_ids.add(str(observation["source_id"]))
        evidence = _property_query_evidence(observation, args, selector)
        if evidence is not None:
            matching_evidence.append(evidence)

    latest_by_source: dict[str, dict[str, Any]] = {}
    for evidence in matching_evidence:
        latest_by_source.setdefault(evidence["source_id"], evidence)
    latest = list(latest_by_source.values())
    authoritative_zero = bool(latest) and all(
        evidence["complete_zero"] for evidence in latest
    )
    has_global_cache = any(row_counts.values())
    scope_covered = (
        has_global_cache
        if not requested_jurisdiction
        else observed_requested_scope or any(jurisdiction_counts.values())
    )
    return {
        "authoritative_zero": authoritative_zero,
        "requested_scope": {
            "operation": args.command,
            "selector": selector,
            "jurisdiction": requested_jurisdiction or None,
            "tax_year": args.tax_year,
        },
        "sidecar": {
            "row_counts": row_counts,
            "requested_jurisdiction_counts": jurisdiction_counts,
            "requested_scope_observed": observed_requested_scope,
            "scope_covered": scope_covered,
            "source_ids": sorted(source_ids),
        },
        "matching_query_evidence": latest,
    }


def _local_result(args: argparse.Namespace) -> PublicRecordsResult:
    selector = " ".join(args.query.split()).strip()
    query = _query(LOCAL_SOURCE, args.command, selector, args)
    try:
        db = connect_property(args.property_db)
        try:
            records, cursor = LOCAL_HANDLERS[args.command](db, selector, args)
            coverage = _property_local_coverage(db, args, selector)
        finally:
            db.close()
        if records:
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=cursor,
            )
        elif coverage["authoritative_zero"]:
            evidence = coverage["matching_query_evidence"]
            result = PublicRecordsResult.success(
                query,
                [],
                warnings=[
                    "Exact source-query zero preserved from "
                    + ", ".join(
                        f"{item['source_id']} at {item['retrieved_at']}"
                        for item in evidence
                    )
                ],
            )
        else:
            scope_covered = coverage["sidecar"]["scope_covered"]
            result = PublicRecordsResult.failure(
                query,
                (ResultStatus.PARTIAL if scope_covered else ResultStatus.UNAVAILABLE),
                [
                    PublicRecordsError(
                        code=(
                            "local_cache_miss"
                            if scope_covered
                            else "local_scope_not_covered"
                        ),
                        message=(
                            "no matching normalized record is cached, and no "
                            "exact source-query zero establishes an empty result"
                        ),
                        category="local_coverage",
                        retryable=False,
                        details={
                            "coverage": coverage,
                            "route_guidance": _property_route_guidance(args),
                        },
                    )
                ],
            )
    except (sqlite3.Error, TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="local_sidecar_query_failed",
                    message=str(error),
                    category="local_store",
                    retryable=False,
                )
            ],
        )
    count = (
        len(result.records)
        if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS}
        else None
    )
    log_search(canonical_json(query.to_dict()), LOCAL_SOURCE_ID, count)
    return result


def _catalog_source(detail: Mapping[str, Any]) -> SourceMetadata:
    source = detail["source"]
    roles = detail.get("roles") or ["public_record"]
    return SourceMetadata(
        source_id=source["source_id"],
        name=source["name"],
        source_role=",".join(roles),
        base_url=source.get("official_url"),
        metadata={
            "authority": source.get("authority"),
            "platform_family": source.get("platform_family"),
        },
    )


def _access_failure(
    args: argparse.Namespace,
    *,
    detail: Mapping[str, Any] | None,
    decision: Mapping[str, Any] | None,
    code: str,
    message: str,
    status: ResultStatus,
) -> PublicRecordsResult:
    source = (
        _catalog_source(detail)
        if detail is not None
        else SourceMetadata(
            source_id=args.source,
            name=args.source,
            source_role="unresolved_property_source",
        )
    )
    query = _query(source, args.command, args.query, args)
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=message,
                category="source_access",
                retryable=False,
                details={
                    "access_decision": decision or {},
                    "source_guidance": _source_guidance(args.source),
                },
            )
        ],
    )


def _live_result(
    args: argparse.Namespace,
) -> tuple[PublicRecordsResult, bool]:
    """Return ``(result, adapter_invoked)`` for one explicit external source."""
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        try:
            detail = catalog.show_source(args.source)
        except CatalogError:
            catalog = ensure_catalog_source(
                args.source,
                db_path=args.catalog_db,
            )
            detail = catalog.show_source(args.source)
    except (CatalogError, OSError, ValueError, sqlite3.Error) as error:
        return (
            _access_failure(
                args,
                detail=None,
                decision=None,
                code="source_not_registered",
                message=str(error),
                status=ResultStatus.UNAVAILABLE,
            ),
            False,
        )
    decision = catalog.machine_acquisition_decision(args.source)
    if not decision["allowed"]:
        status = ResultStatus(acquisition_result_status(decision))
        return (
            _access_failure(
                args,
                detail=detail,
                decision=decision,
                code=decision["reason_code"],
                message=decision["reason"],
                status=status,
            ),
            False,
        )

    source_routes = LIVE_ROUTES.get(args.source)
    if source_routes is None:
        guidance = _source_guidance(args.source)
        return (
            _access_failure(
                args,
                detail=detail,
                decision=decision,
                code="adapter_not_implemented",
                message=(
                    f"{args.source} has no unified direct-query adapter; "
                    f"use {guidance.get('direct_tool', 'the catalogued source route')}"
                ),
                status=ResultStatus.UNAVAILABLE,
            ),
            False,
        )
    route = source_routes.get(args.command)
    if route is None:
        return (
            _access_failure(
                args,
                detail=detail,
                decision=decision,
                code="capability_not_supported",
                message=(
                    f"{args.source} does not support unified operation "
                    f"{args.command}; supported operations: "
                    f"{', '.join(sorted(source_routes))}"
                ),
                status=ResultStatus.UNAVAILABLE,
            ),
            False,
        )

    adapter_args = route.translate(args, route.adapter_command)
    return (
        route.adapter.execute(
            adapter_args,
            access_decision=decision,
        ),
        True,
    )


def _sources_result(args: argparse.Namespace) -> PublicRecordsResult:
    query = PublicRecordsQuery(
        source=CATALOG_SOURCE,
        jurisdiction=_jurisdiction(args.jurisdiction),
        query=QueryMetadata(
            operation="sources",
            parameters={"domain": "property", "jurisdiction": args.jurisdiction},
        ),
    )
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        rows = catalog.list_sources(domain="property", jurisdiction=args.jurisdiction)
        records = []
        for row in rows:
            decision = catalog.machine_acquisition_decision(row["source_id"])
            detail = catalog.show_source(row["source_id"])
            records.append(
                {
                    **row,
                    "capabilities": [
                        capability["name"]
                        for capability in detail.get("capabilities", ())
                        if capability.get("supported", True)
                    ],
                    "machine_acquisition": decision,
                    "query_guidance": _source_guidance(row["source_id"]),
                }
            )
        return PublicRecordsResult.success(query, records)
    except (CatalogError, sqlite3.Error, ValueError) as error:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="catalog_query_failed",
                    message=str(error),
                    category="source_catalog",
                    retryable=False,
                )
            ],
        )


def _source_selection_result(
    args: argparse.Namespace,
    compatible_sources: list[str],
) -> PublicRecordsResult:
    """Return an explicit result when a non-local operation has several routes."""

    query = _query(CATALOG_SOURCE, args.command, args.query, args)
    ordered_sources = sorted(compatible_sources)
    result = PublicRecordsResult.failure(
        query,
        ResultStatus.HUMAN_REQUIRED,
        [
            PublicRecordsError(
                code="source_selection_required",
                message=(
                    f"{args.command} is available from multiple property sources; "
                    "select the source that matches the intended jurisdiction"
                ),
                category="source_routing",
                retryable=False,
                details={
                    "compatible_sources": [
                        {
                            "source_id": source_id,
                            "query_guidance": _source_guidance(source_id),
                        }
                        for source_id in ordered_sources
                    ],
                    "select_source": "--source SOURCE_ID",
                },
            )
        ],
    )
    log_search(canonical_json(query.to_dict()), CATALOG_SOURCE_ID, None)
    return result


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "sources":
        return _sources_result(args).to_dict()
    routed_args = args
    if args.source == "local" and args.command not in LOCAL_HANDLERS:
        compatible_sources = [
            source_id
            for source_id, routes in LIVE_ROUTES.items()
            if args.command in routes
        ]
        if len(compatible_sources) == 1:
            routed_args = argparse.Namespace(
                **{
                    **vars(args),
                    "source": compatible_sources[0],
                }
            )
        elif compatible_sources:
            if args.ingest:
                raise ValueError("--ingest requires an explicit live source")
            return _source_selection_result(args, compatible_sources).to_dict()
    if routed_args.source == "local":
        if args.ingest:
            raise ValueError("--ingest requires a live source")
        return _local_result(args).to_dict()

    result, adapter_invoked = _live_result(routed_args)
    if not adapter_invoked:
        log_search(
            canonical_json(result.query.to_dict()),
            routed_args.source,
            None,
        )
    payload = result.to_dict()
    if args.ingest:
        if not adapter_invoked:
            payload["ingest"] = {
                "status": "skipped",
                "reason": "no live adapter envelope was returned",
            }
        else:
            payload["ingest"] = ingest_property_envelope(
                payload,
                db_path=routed_args.property_db,
                raw_artifact_path=(
                    routed_args.destination
                    if (
                        routed_args.source
                        in {
                            USVI_PROPERTY_TAX_SOURCE_ID,
                            OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
                        }
                        and routed_args.command == "download"
                        and result.status == ResultStatus.OK
                        and bool(result.records)
                    )
                    else (
                        routed_args.artifact_path
                        if routed_args.source
                        in {
                            MICHIGAN_EATON_PARCELS_SOURCE_ID,
                            ORANGE_TAX_COLLECTOR_SOURCE_ID,
                            OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
                            *OREGON_MARION_DOWNLOAD_SOURCE_IDS,
                        }
                        else None
                    )
                ),
            )
    return payload


def _emit(payload: Mapping[str, Any], args: argparse.Namespace) -> None:
    if write_output(
        payload,
        args,
        summary=f"property {args.command} ({payload.get('status', 'unknown')})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    records = payload.get("records", [])
    print(f"Property {args.command}: {payload.get('status')} ({len(records)} records)")
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        label = (
            record.get("native_parcel_id")
            or record.get("native_document_id")
            or record.get("source_id")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


class _PropertyArgumentParser(argparse.ArgumentParser):
    """Normalize explicit coordinate options into the shared selector."""

    def parse_args(
        self,
        args: Any = None,
        namespace: argparse.Namespace | None = None,
    ) -> argparse.Namespace:
        parsed = super().parse_args(args, namespace)
        if getattr(parsed, "command", None) != "point":
            return parsed

        longitude = getattr(parsed, "longitude", None)
        latitude = getattr(parsed, "latitude", None)
        if (longitude is None) != (latitude is None):
            self.error("point requires both --longitude and --latitude")
        if longitude is not None:
            if parsed.query is not None:
                self.error(
                    "point accepts either a longitude,latitude selector or "
                    "--longitude/--latitude, not both"
                )
            parsed.query = f"{longitude:.15g},{latitude:.15g}"
        elif parsed.query is None:
            self.error(
                "point requires a longitude,latitude selector or both "
                "--longitude and --latitude"
            )
        return parsed


def _add_query_args(
    parser: argparse.ArgumentParser,
    *,
    query_optional: bool = False,
) -> None:
    parser.set_defaults(limit_explicit=False)
    parser.add_argument("query", nargs="?" if query_optional else None)
    parser.add_argument(
        "--source",
        default="local",
        help="Canonical catalog source ID, or local (default)",
    )
    parser.add_argument("--jurisdiction", help="State/county GEOID filter")
    parser.add_argument(
        "--county-code",
        "--county-fips",
        dest="county_fips",
        help="Optional source-specific county code, FIPS, or GEOID",
    )
    parser.add_argument(
        "--county",
        dest="county_selector",
        help="Optional county name, publisher code, FIPS suffix, or GEOID",
    )
    parser.add_argument(
        "--dataset-type",
        help="Optional source-native bulk dataset or artifact family",
    )
    parser.add_argument(
        "--collection-id",
        help="Optional source-native bulk collection or release identifier",
    )
    parser.add_argument(
        "--tax-year",
        type=int,
        help="Optional source tax or assessment year",
    )
    parser.add_argument(
        "--department",
        help="Optional source-native recorder department such as RP, MISC, or UCC",
    )
    parser.add_argument(
        "--district",
        help="Optional source-native recording district",
    )
    parser.add_argument(
        "--inst-id",
        help="Optional source-native instrument ID used with an exact locator",
    )
    parser.add_argument(
        "--page-number",
        type=int,
        help="Explicit source document page selected for retrieval",
    )
    parser.add_argument(
        "--process-stage",
        help="Optional source-specific publication or legal-process stage",
    )
    parser.add_argument(
        "--from-date",
        help="Optional source-native beginning date for a date-bounded search",
    )
    parser.add_argument(
        "--to-date",
        help="Optional source-native ending date for a date-bounded search",
    )
    parser.add_argument(
        "--search-field",
        help="Optional source-native search field exposed by the selected adapter",
    )
    parser.add_argument(
        "--artifact-path",
        help="Downloaded source artifact used by adapters with local snapshot search",
    )
    parser.add_argument(
        "--artifact-source-url",
        help=(
            "Original source URL for a caller-supplied local artifact when "
            "supported by the selected adapter"
        ),
    )
    parser.add_argument(
        "--destination",
        help="Explicit destination for a bulk artifact download",
    )
    parser.add_argument(
        "--artifact-kind",
        help="Source-native artifact kind selected for retrieval",
    )
    parser.add_argument(
        "--statement",
        help="Source-native property-tax statement number",
    )
    parser.add_argument(
        "--transaction-id",
        help="Source-native property-tax payment transaction identifier",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing explicitly selected destination when supported",
    )
    parser.add_argument(
        "--range-bytes",
        type=int,
        help="Caller-selected leading byte range for a bounded artifact probe",
    )
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument(
        "--resume",
        action="store_true",
        dest="resume",
        help="Resume a compatible partial bulk transfer",
    )
    resume_group.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="Start the bulk transfer without resuming a partial file",
    )
    parser.set_defaults(resume=True)
    parser.add_argument(
        "--expected-sha256",
        help="Expected artifact SHA-256 supplied by the caller",
    )
    parser.add_argument(
        "--max-download-bytes",
        type=int,
        help="Optional caller-selected maximum transfer size",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        help="Optional caller-selected bulk transfer chunk size",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        action=_ExplicitLimitAction,
    )
    parser.add_argument("--cursor", help="Continuation cursor")
    parser.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    parser.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Request source geometry where supported",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Normalize a live result when a sidecar ingester is available",
    )
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional user-selected record ceiling for live source queries",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Optional source request timeout in seconds",
    )
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = _PropertyArgumentParser(
        description="Query normalized and catalogued property record sources"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sources = sub.add_parser("sources", help="List catalogued property sources")
    sources.add_argument("--jurisdiction", help="State/county GEOID filter")
    sources.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    add_output_args(sources)

    for command, help_text in (
        ("search", "Search normalized owner observations by default"),
        ("owner", "Search normalized owner observations"),
        ("address", "Search normalized situs or mailing addresses"),
        ("subdivision", "Search source-native subdivision names"),
        ("mobile-park", "Search source-native mobile-home park names"),
        ("account", "Look up an exact source-native assessment account"),
        ("parcel", "Look up a native or alternate parcel identifier"),
        ("county", "Search one source-native county inventory"),
        ("jurisdiction", "Search one source-native jurisdiction inventory"),
        ("situs", "Search source-native situs addresses"),
        ("mailing", "Search source-native mailing addresses"),
        ("legal", "Search source-native legal descriptions"),
        ("fid", "Look up an exact source feature occurrence"),
        ("geometry", "Fetch geometry for an exact source occurrence"),
        ("sale", "Search source-native property sale observations"),
        ("survey", "Search source-native survey or plat records"),
        ("event", "Look up a permit, land-use, or code-compliance event"),
        ("instrument", "Search recorded instruments and instrument parties"),
        ("detail", "Fetch an exact source-native record detail"),
        ("assessment", "Fetch a current source-native assessment"),
        ("history", "Fetch source-native assessment history"),
        ("exemptions", "Fetch source-native property exemptions"),
        ("chain", "Build a gap-labeled chain-of-title view"),
        ("map", "Return source-provided parcel geometry references"),
        ("count", "Count rows matching a source-native selector"),
        ("point", "Search a source at longitude,latitude"),
        ("bbox", "Search a source at west,south,east,north"),
        ("freshness", "Inspect a source's partition freshness observations"),
        ("land-use", "Search a source's land-use vocabulary"),
        ("parity", "Compare same-lineage source representations"),
        ("releases", "List published bulk release directories"),
        ("manifest", "List bulk artifacts and their release metadata"),
        ("download", "Download one explicitly selected bulk artifact"),
        (
            "discovery",
            "Discover source routes and destination capabilities",
        ),
        ("probe", "Run a source's bounded contract probe"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        _add_query_args(
            command_parser,
            query_optional=command
            in {
                "point",
                "releases",
                "manifest",
                "download",
                "discovery",
                "freshness",
                "probe",
            },
        )
        if command == "point":
            command_parser.add_argument(
                "--longitude",
                type=float,
                help="WGS84 longitude; use with --latitude",
            )
            command_parser.add_argument(
                "--latitude",
                type=float,
                help="WGS84 latitude; use with --longitude",
            )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "page_size", 1) <= 0 or (
        getattr(args, "max_records", None) is not None and args.max_records <= 0
    ):
        parser.error("--page-size must be positive; --max-records is optional")
    if getattr(args, "tax_year", None) is not None and args.tax_year <= 0:
        parser.error("--tax-year must be positive")
    if (
        getattr(args, "page_number", None) is not None
        and args.page_number <= 0
    ):
        parser.error("--page-number must be positive")
    for field in ("range_bytes", "max_download_bytes", "chunk_size"):
        value = getattr(args, field, None)
        if value is not None and value <= 0:
            parser.error(f"--{field.replace('_', '-')} must be positive")
    if hasattr(args, "query") and args.query is not None and not args.query.strip():
        parser.error("query must not be blank")
    try:
        payload = execute(args)
    except ValueError as error:
        parser.error(str(error))
        return
    _emit(payload, args)


if __name__ == "__main__":
    main()
