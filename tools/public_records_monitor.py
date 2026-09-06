#!/usr/bin/env python3
"""Catalog-backed source sentinel and drift monitor for public records.

The monitor has no scheduler or independent access policy. ``run`` accepts
explicit source IDs, reads each current acquisition decision from
``PublicRecordsCatalog``, invokes only a visible registered probe handler, and
appends observations to the catalog's immutable probe history.

Usage:
    uv run python tools/public_records_monitor.py plan
    uv run python tools/public_records_monitor.py run us-nc-onemap-parcels
    uv run python tools/public_records_monitor.py history us-nc-onemap-parcels
    uv run python tools/public_records_monitor.py diff us-nc-onemap-parcels
    uv run python tools/public_records_monitor.py record SOURCE_ID --status ok ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import urlopen

try:
    from tools import query_broward_official_records
    from tools import query_california_court_directory
    from tools import query_california_opinions
    from tools import query_census_acs
    from tools import query_connecticut_civil_family
    from tools import query_dc_appellate_cases
    from tools import query_dc_court_directory_data
    from tools import query_doj_court_records
    from tools import query_edva_bankruptcy
    from tools import query_fl_dor_property
    from tools import query_florida_court_directory_data
    from tools import query_florida_ninth_opinions
    from tools import query_harris_property
    from tools import query_hcad_gis
    from tools import query_osceola_courts
    from tools import query_georgia_court_access
    from tools import query_georgia_court_data
    from tools import query_georgia_court_directory
    from tools import query_georgia_supreme_docket
    from tools import query_georgia_supreme_publications
    from tools import query_georgia_property_sources
    from tools import query_los_angeles_name_index
    from tools import query_md_mdp_property_downloads
    from tools import query_md_mdp_parcel_points
    from tools import query_md_plats
    from tools import query_md_estate_search
    from tools import query_md_estate_notices_claims
    from tools import query_md_business_opinions
    from tools import query_md_judgment_liens
    from tools import query_md_opinions
    from tools import query_md_public_cases
    from tools import query_mason_county_tax_parcels
    from tools import query_michigan_appellate
    from tools import query_michigan_business_court
    from tools import query_michigan_property_directories
    from tools import query_montana_cadastral
    from tools import query_new_mexico_case_lookup
    from tools import query_new_jersey_dca_property
    from tools import query_new_jersey_parcels
    from tools import query_new_jersey_sr1a
    from tools import query_new_jersey_tax_court
    from tools import query_new_jersey_tax_court_opinions
    from tools import query_ny_attorneys
    from tools import query_ny_salesweb
    from tools import query_ny_statewide_parcels
    from tools import query_nyc_pip
    from tools import query_licking_foreclosure_archive
    from tools import query_ohio_franklin_auditor_bulk
    from tools import query_ohio_franklin_sales_gis
    from tools import query_ohio_delaware_common_pleas
    from tools import query_ohio_franklin_courts
    from tools import query_ohio_franklin_municipal
    from tools import query_ohio_licking_common_pleas
    from tools import query_ohio_franklin_probate
    from tools import query_ohio_pax_recorders
    from tools import query_ohio_reporter_decisions
    from tools import query_ohio_sheriff_sales
    from tools import query_ohio_licking_property
    from tools import query_ohio_statewide_parcels
    from tools import query_ohio_supreme_court
    from tools import query_orange_county_court
    from tools import query_orange_tax_collector
    from tools import query_oregon_lane_property
    from tools import query_palm_beach_official_records
    from tools import query_palm_beach_property_appraiser
    from tools import query_palm_beach_tax_collector
    from tools import query_palm_beach_tax_deeds
    from tools import query_philadelphia_property
    from tools import query_qld_ecourts
    from tools import query_riverside_court
    from tools import query_san_diego_court_index
    from tools import query_santa_clara_court_records
    from tools import query_santa_fe_clerktrack
    from tools import query_santa_fe_property
    from tools import query_texas_supreme_publications
    from tools import query_txgio_land_parcels
    from tools import query_usvi_property_tax
    from tools import query_usvi_recorder
    from tools import query_va_beach_delinquent_tax
    from tools import query_va_general_district
    from tools import query_virginia_parcels
    from tools import query_wisconsin_court_directory
    from tools import query_wisconsin_opinions
    from tools import query_wisconsin_wscca
    from tools.output_util import add_output_args, write_output
    from tools.kofile_publicsearch import (
        KofileAccessError,
        KofileNotFoundError,
        KofilePublicSearchClient,
        KofilePublicSearchError,
        KofileRateLimitError,
        KofileSourceChangedError,
    )
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkSourceError,
        BulkTransferClient,
    )
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH,
        PROBE_STATUSES,
        CatalogError,
        PublicRecordsCatalog,
        acquisition_result_status,
    )
    from tools.public_records_contract import (
        PublicRecordsResult,
        ResultStatus,
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        _BaseJSONClient,
        inferred_schema,
        system_trust_session,
    )
    from tools.query_massgis_property import (
        MANIFEST_FIELDS as MASSGIS_MANIFEST_FIELDS,
        MANIFEST_LAYER_URL as MASSGIS_MANIFEST_LAYER_URL,
    )
    from tools.query_bexar_property import (
        OUT_FIELDS as BEXAR_PROPERTY_FIELDS,
        TABLE_ORDER_BY as BEXAR_PROPERTY_ORDER,
        TABLE_URL as BEXAR_PROPERTY_TABLE_URL,
    )
    from tools.query_denver_property import (
        LAYER_URL as DENVER_PROPERTY_LAYER_URL,
        OUT_FIELDS as DENVER_PROPERTY_FIELDS,
        PROBE_SCHEDULE_NUMBER as DENVER_PROPERTY_PROBE_SCHEDULE,
    )
    from tools.query_deschutes_property import (
        SERVICE_URL as DESCHUTES_PROPERTY_SERVICE_URL,
        SOURCE_ID as DESCHUTES_PROPERTY_SOURCE_ID,
        execute as execute_deschutes_property,
    )
    from tools.query_deschutes_dial import (
        BASE_URL as DESCHUTES_DIAL_BASE_URL,
        DEFAULT_COMPONENTS as DESCHUTES_DIAL_COMPONENTS,
        SOURCE_ID as DESCHUTES_DIAL_SOURCE_ID,
        execute as execute_deschutes_dial,
    )
    from tools.query_deschutes_laserfiche import (
        BASE_URL as DESCHUTES_CDD_WEBLINK_BASE_URL,
        DEFAULT_MAX_DOCUMENT_BYTES as DESCHUTES_CDD_MAX_DOCUMENT_BYTES,
        DEFAULT_MAX_RESPONSE_BYTES as DESCHUTES_CDD_MAX_RESPONSE_BYTES,
        DEFAULT_POLL_ATTEMPTS as DESCHUTES_CDD_POLL_ATTEMPTS,
        DEFAULT_POLL_INTERVAL as DESCHUTES_CDD_POLL_INTERVAL,
        SOURCE_ID as DESCHUTES_CDD_WEBLINK_SOURCE_ID,
        execute as execute_deschutes_cdd_weblink,
    )
    from tools.query_denver_delinquent_tax import (
        DEFAULT_MAX_ARCHIVE_MEMBERS as DENVER_TAX_MAX_ARCHIVE_MEMBERS,
        DEFAULT_MAX_COMPRESSION_RATIO as DENVER_TAX_MAX_COMPRESSION_RATIO,
        DEFAULT_MAX_MEMBER_UNCOMPRESSED_BYTES as DENVER_TAX_MAX_MEMBER_BYTES,
        DEFAULT_MAX_UNCOMPRESSED_BYTES as DENVER_TAX_MAX_UNCOMPRESSED_BYTES,
        DEFAULT_SAMPLE_BYTES as DENVER_TAX_SAMPLE_BYTES,
        PUBLICATION_PAGE as DENVER_TAX_PUBLICATION_PAGE,
        execute as execute_denver_delinquent_tax,
    )
    from tools.query_denver_foreclosures import (
        DEFAULT_PROBE_FORECLOSURE as DENVER_FORECLOSURE_PROBE_ID,
        SEARCH_URL as DENVER_FORECLOSURE_SEARCH_URL,
        execute as execute_denver_foreclosures,
    )
    from tools.query_denver_county_court import (
        DOCKET_URL as DENVER_COUNTY_COURT_DOCKET_URL,
        execute as execute_denver_county_court,
    )
    from tools.query_colorado_judicial import (
        DOCKET_URL as COLORADO_JUDICIAL_DOCKET_URL,
        execute as execute_colorado_judicial,
    )
    from tools.query_colorado_court_data import (
        ANNUAL_REPORTS_URL as COLORADO_COURT_DATA_URL,
        ColoradoCourtDataClient,
        execute as execute_colorado_court_data,
    )
    from tools.query_colorado_opinions import (
        CASE_LAW_BASE_URL as COLORADO_OPINIONS_ARCHIVE_URL,
        JUDICIAL_BASE_URL as COLORADO_OPINIONS_RELEASE_URL,
        execute as execute_colorado_opinions,
    )
    from tools.query_dc_opinions import (
        EXPECTED_HEADERS as DC_OPINIONS_EXPECTED_HEADERS,
        INDEX_URL as DC_OPINIONS_URL,
        NATIVE_ORDERS as DC_OPINIONS_NATIVE_ORDERS,
        NATIVE_TYPES as DC_OPINIONS_NATIVE_TYPES,
        PROBE_APPEAL_NUMBER as DC_OPINIONS_PROBE_APPEAL_NUMBER,
        ROWS_PER_PAGE as DC_OPINIONS_ROWS_PER_PAGE,
        SOURCE_ID as DC_OPINIONS_SOURCE_ID,
        SOURCE_METADATA as DC_OPINIONS_SOURCE_METADATA,
        execute as execute_dc_opinions,
    )
    from tools.query_dc_superior_calendar import (
        APPEALS_SOURCE_ID as DC_APPEALS_CALENDAR_SOURCE_ID,
        APPEALS_URL as DC_APPEALS_CALENDAR_URL,
        CRIMINAL_SOURCE_ID as DC_CRIMINAL_CALENDAR_SOURCE_ID,
        CRIMINAL_URL as DC_CRIMINAL_CALENDAR_URL,
        SOURCE_METADATA_BY_ID as DC_CALENDAR_SOURCE_METADATA,
        SOURCE_WARNINGS as DC_CALENDAR_SOURCE_WARNINGS,
        TAX_SOURCE_ID as DC_TAX_CALENDAR_SOURCE_ID,
        TAX_URL as DC_TAX_CALENDAR_URL,
        TODAY_SOURCE_ID as DC_TODAY_CALENDAR_SOURCE_ID,
        TODAY_URL as DC_TODAY_CALENDAR_URL,
        execute as execute_dc_superior_calendar,
    )
    from tools.query_fresno_superior_court import (
        CALENDAR_INDEX_URL as FRESNO_CALENDAR_URL,
        CALENDAR_SOURCE_ID as FRESNO_CALENDAR_SOURCE_ID,
        FAMILY_SOURCE_ID as FRESNO_FAMILY_SOURCE_ID,
        PORTAL_SOURCE_ID as FRESNO_PORTAL_SOURCE_ID,
        PORTAL_URL as FRESNO_PORTAL_URL,
        PROBATE_NOTES_URL as FRESNO_PROBATE_URL,
        PROBATE_SOURCE_ID as FRESNO_PROBATE_SOURCE_ID,
        RULINGS_INDEX_URL as FRESNO_RULINGS_URL,
        RULINGS_SOURCE_ID as FRESNO_RULINGS_SOURCE_ID,
        SOURCE_METADATA as FRESNO_SOURCE_METADATA,
        SOURCE_WARNINGS as FRESNO_SOURCE_WARNINGS,
        execute as execute_fresno_superior_court,
    )
    from tools.query_delaware_firstmap import (
        SERVICE_URL as DELAWARE_FIRSTMAP_SERVICE_URL,
        execute as execute_delaware_firstmap,
    )
    from tools.query_arlington_property import (
        LAYER_URL as ARLINGTON_PROPERTY_LAYER_URL,
        execute as execute_arlington_property,
    )
    from tools.query_bexar_courts import (
        BASE_URL as BEXAR_HISTORICAL_BASE_URL,
        DEPARTMENT as BEXAR_HISTORICAL_DEPARTMENT,
        PROBE_DATE_FROM as BEXAR_HISTORICAL_PROBE_DATE_FROM,
        PROBE_DATE_TO as BEXAR_HISTORICAL_PROBE_DATE_TO,
        WEBSOCKET_URL as BEXAR_HISTORICAL_WEBSOCKET_URL,
    )
    from tools.query_nc_property import (
        LAYER_URL as NC_ONEMAP_LAYER_URL,
        OUT_FIELDS as NC_ONEMAP_FIELDS,
    )
    from tools.query_orleans_property import (
        LAYER_URL as ORLEANS_PROPERTY_LAYER_URL,
        LOCATOR_URL as ORLEANS_PROPERTY_LOCATOR_URL,
        PROBE_GEOPIN as ORLEANS_PROPERTY_PROBE_GEOPIN,
    )
    from tools.query_oregon_appellate import (
        API_ROOT as OREGON_APPELLATE_API_ROOT,
        SOURCE_ID as OREGON_APPELLATE_SOURCE_ID,
        execute as execute_oregon_appellate,
    )
    from tools.query_oregon_appellate_calendars import (
        COURT_OF_APPEALS as OREGON_COA_CALENDAR,
        SUPREME_COURT as OREGON_SUPREME_CALENDAR,
        execute as execute_oregon_appellate_calendars,
    )
    from tools.query_oregon_court_calendar import (
        LANDING_URL as OREGON_COURT_CALENDAR_URL,
        SOURCE_ID as OREGON_COURT_CALENDAR_SOURCE_ID,
        execute as execute_oregon_court_calendar,
    )
    from tools.query_oregon_court_documents import (
        COLLECTIONS as OREGON_COURT_DOCUMENT_COLLECTIONS,
        execute as execute_oregon_court_documents,
    )
    from tools.query_oregon_court_directories import (
        LISTS_URL as OREGON_COURT_DIRECTORY_LISTS_URL,
        SOURCES_BY_ID as OREGON_COURT_DIRECTORY_SOURCES,
        execute as execute_oregon_court_directories,
    )
    from tools.query_oregon_ojcin_products import (
        ADAPTER_SCHEMA_FINGERPRINT as OREGON_OJCIN_SCHEMA_FINGERPRINT,
        ENDPOINTS as OREGON_OJCIN_ENDPOINTS,
        OJCIN_URL as OREGON_OJCIN_URL,
        PRODUCTS as OREGON_OJCIN_PRODUCTS,
        SOURCE_ID as OREGON_OJCIN_SOURCE_ID,
        OfficialEndpointClient as OregonOJCINEndpointClient,
        probe_all as run_oregon_ojcin_endpoint_probe,
    )
    from tools.query_oregon_smart_search import (
        FORM_ACTION_URL as OREGON_SMART_SEARCH_FORM_ACTION_URL,
        ROLLING_OPTION_FIELDS as OREGON_SMART_SEARCH_ROLLING_OPTION_FIELDS,
        SOURCE_ID as OREGON_SMART_SEARCH_SOURCE_ID,
        SOURCE_URL as OREGON_SMART_SEARCH_URL,
        execute as execute_oregon_smart_search,
    )
    from tools.query_oregon_taxlots import (
        SOURCES as OREGON_TAXLOT_SOURCES,
        execute as execute_oregon_taxlots,
    )
    from tools import query_dc_property
    from tools import query_los_angeles_ttc
    from tools import query_oregon_benton_property
    from tools import query_oregon_clackamas_property
    from tools import query_oregon_lincoln_propertyweb
    from tools import query_oregon_lincoln_taxlots
    from tools import query_oregon_marion_downloads
    from tools import query_oregon_multnomah_sail
    from tools import query_oregon_wasco_property
    from tools import query_oregon_washington_case_permits
    from tools import query_oregon_washington_property
    from tools import query_washington_courts
    from tools import query_washington_digital_archives_land
    from tools import query_washington_parcels
    from tools import query_washington_taxsifter
    from tools import query_wisconsin_parcels
    from tools import query_wy_dor_parcels
    from tools import query_oregon_yamhill_property
    from tools.query_oregon_helion_property import (
        PLATFORM_FAMILY as OREGON_HELION_PROPERTY_PLATFORM,
        TENANTS_BY_SOURCE as OREGON_HELION_PROPERTY_TENANTS,
        execute as execute_oregon_helion_property,
    )
    from tools.query_oregon_jackson_accela import (
        SOURCES as OREGON_JACKSON_ACCELA_SOURCES,
        execute as execute_oregon_jackson_accela,
    )
    from tools.query_oregon_jackson_douglas_assessors import (
        SOURCES as OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCES,
        execute as execute_oregon_jackson_douglas_assessors,
    )
    from tools.query_oregon_jackson_property_events import (
        SOURCES as OREGON_JACKSON_PROPERTY_EVENT_SOURCES,
        execute as execute_oregon_jackson_property_events,
    )
    from tools.query_oregon_helion_recorder import (
        TENANTS_BY_SOURCE as OREGON_HELION_RECORDER_TENANTS,
        execute as execute_oregon_helion_recorder,
    )
    from tools.query_oregon_linn_josephine_klamath_assessors import (
        SOURCES as OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SOURCES,
        execute as execute_oregon_linn_josephine_klamath_assessors,
    )
    from tools.query_oregon_lane_marion_parcels import (
        SOURCES as OREGON_LANE_MARION_PROPERTY_SOURCES,
        execute as execute_oregon_lane_marion_property,
    )
    from tools.query_eugene_municipal_court import (
        OREGON_TENANTS as OREGON_TYLER_MUNICIPAL_TENANTS,
        execute as execute_eugene_municipal_court,
    )
    from tools.query_oregon_tax_foreclosures import (
        DEFAULT_MAX_DOCUMENT_BYTES as OREGON_TAX_FORECLOSURE_MAX_DOCUMENT_BYTES,
        SOURCES as OREGON_TAX_FORECLOSURE_SOURCES,
        SOURCE_PROCESS_STAGES as OREGON_TAX_FORECLOSURE_PROCESS_STAGES,
        discover_source as discover_oregon_tax_foreclosure_source,
        fetch_bytes as fetch_oregon_tax_foreclosure_bytes,
    )
    from tools.query_vicourts import (
        CASE_SEARCH_URL as VICOURTS_CASE_SEARCH_URL,
        DOCUMENT_SEARCH_URL as VICOURTS_DOCUMENT_SEARCH_URL,
        INFO_URL as VICOURTS_INFO_URL,
        LEGACY_FILE_URL as VICOURTS_LEGACY_FILE_URL,
        PUBLICATION_SEARCH_URL as VICOURTS_PUBLICATION_SEARCH_URL,
        VICourtsClient,
        normalize_case_number as normalize_vicourts_case_number,
    )
    from tools.query_miami_dade_property import (
        PARCEL_LAYER_URL as MIAMI_DADE_PARCEL_LAYER_URL,
        PARCEL_ORDER_BY as MIAMI_DADE_PARCEL_ORDER,
        PARCEL_OUT_FIELDS as MIAMI_DADE_PARCEL_FIELDS,
        PROXY_URL as MIAMI_DADE_PA_PROXY_URL,
        MiamiDadePAClient,
    )
    from tools.query_miami_dade_recorder import (
        PUBLIC_DOCUMENT_TYPES_API as MIAMI_DADE_DOCUMENT_TYPES_URL,
        MiamiDadeRecorderClient,
    )
    from tools.query_orange_county_courts import (
        CALENDAR_URL as ORANGE_CALENDAR_URL,
        OrangeCountyCourtsClient,
    )
    from tools.query_los_angeles_court import (
        CASE_SEARCH_URL as LOS_ANGELES_CIVIL_CASE_SEARCH_URL,
        PROBE_CASE_NUMBER as LOS_ANGELES_CIVIL_PROBE_CASE_NUMBER,
        SOURCE_ID as LOS_ANGELES_CIVIL_SOURCE_ID,
        SOURCE_METADATA as LOS_ANGELES_CIVIL_SOURCE_METADATA,
        SOURCE_WARNINGS as LOS_ANGELES_CIVIL_SOURCE_WARNINGS,
        TENTATIVE_INDEX_URL as LOS_ANGELES_CIVIL_TENTATIVE_INDEX_URL,
        LosAngelesCourtClient,
    )
    from tools.query_los_angeles_probate import (
        CASE_SEARCH_URL as LOS_ANGELES_PROBATE_CASE_SEARCH_URL,
        PROBE_CASE_NUMBER as LOS_ANGELES_PROBATE_PROBE_CASE_NUMBER,
        LosAngelesProbateClient,
    )
    from tools.query_ny_law_reports import (
        BASE_URL as NY_LAW_REPORTS_BASE_URL,
        run_sentinel as run_ny_law_reports_sentinel,
    )
    from tools.query_ny_column import (
        PORTAL_URL as NY_COLUMN_PORTAL_URL,
        run_sentinel as run_ny_column_sentinel,
    )
    from tools.query_pa_ujs import (
        CASE_SEARCH_URL as PA_UJS_CASE_SEARCH_URL,
        execute as execute_pa_ujs,
    )
    from tools.query_pa_opinions import (
        API_URL as PA_OPINIONS_API_URL,
        execute as execute_pa_opinions,
    )
    from tools.query_delaware_courts import (
        OFFICIAL_CIVIL_SEARCH_URL as DELAWARE_COURTCONNECT_URL,
        execute as execute_delaware_courts,
    )
    from tools.query_delaware_opinions import (
        INDEX_URL as DELAWARE_OPINIONS_URL,
        execute as execute_delaware_opinions,
    )
    from tools.query_harris_recorder import (
        SEARCH_URL as HARRIS_RECORDER_SEARCH_URL,
        HarrisRecorderClient,
        run_sentinel as run_harris_recorder_sentinel,
    )
    from tools.query_harris_foreclosures import (
        SEARCH_URL as HARRIS_FORECLOSURE_SEARCH_URL,
        HarrisForeclosureClient,
        run_sentinel as run_harris_foreclosure_sentinel,
    )
    from tools.query_harris_court_bulk import (
        CATALOG_URL as HARRIS_COURT_BULK_CATALOG_URL,
        DEFAULT_SAMPLE_BYTES as HARRIS_COURT_BULK_SAMPLE_BYTES,
        JURISDICTION as HARRIS_COURT_BULK_JURISDICTION,
        SENTINEL_FILENAME as HARRIS_COURT_BULK_SENTINEL_FILENAME,
        SENTINEL_LOCATOR as HARRIS_COURT_BULK_SENTINEL_LOCATOR,
        SENTINEL_PUBLISHED_DATE as HARRIS_COURT_BULK_SENTINEL_PUBLISHED_DATE,
        SOURCE_ID as HARRIS_COURT_BULK_SOURCE_ID,
        SOURCE_METADATA as HARRIS_COURT_BULK_SOURCE_METADATA,
        DatasetArtifact as HarrisCourtBulkDatasetArtifact,
        HarrisCourtBulkClient,
        run_sentinel as run_harris_court_bulk_sentinel,
    )
    from tools.query_palm_beach_courts import (
        BASE_URL as PALM_BEACH_ECASEVIEW_URL,
        run_browser_helper as run_palm_beach_browser_helper,
    )
    from tools.query_pima_courts import (
        BASE_URL as PIMA_PUBLICDOCS_URL,
        PimaCourtClient,
    )
    from tools.query_san_mateo_midx import (
        LANDING_URL as SAN_MATEO_MIDX_URL,
        MIDXClient,
    )
    from tools.query_tax_court import (
        API_ROOT as TAX_COURT_API_ROOT,
        TaxCourtClient,
    )
    from tools.query_reeves_records import (
        BASE_URL as REEVES_RECORDS_BASE_URL,
        DEPARTMENT as REEVES_RECORDS_DEPARTMENT,
        PROBE_DOCUMENT_ID as REEVES_RECORDS_PROBE_DOCUMENT_ID,
        PROBE_INSTRUMENT_NUMBER as REEVES_RECORDS_PROBE_INSTRUMENT_NUMBER,
        ReevesRecordsClient,
        WEBSOCKET_URL as REEVES_RECORDS_WEBSOCKET_URL,
        normalize_instrument as normalize_kofile_instrument,
    )
    from tools.query_govos_recorders import (
        TENANTS_BY_SOURCE as GOVOS_RECORDER_TENANTS,
    )
    from tools.query_rrc_bulk import (
        SHARE_URLS as TEXAS_RRC_SHARE_URLS,
        SOURCE_CONTRACTS as TEXAS_RRC_SOURCE_CONTRACTS,
        RRCGoDriveClient,
        preferred_release as preferred_texas_rrc_release,
    )
    from tools.query_texas_appellate import (
        SEARCH_URL as TEXAS_TAMES_SEARCH_URL,
        TexasTAMESClient,
        normalize_case as normalize_texas_tames_case,
    )
except ImportError:
    import query_broward_official_records
    import query_california_court_directory
    import query_california_opinions
    import query_census_acs
    import query_dc_appellate_cases
    import query_connecticut_civil_family
    import query_dc_court_directory_data
    import query_doj_court_records
    import query_edva_bankruptcy
    import query_fl_dor_property
    import query_florida_court_directory_data
    import query_florida_ninth_opinions
    import query_harris_property
    import query_hcad_gis
    import query_osceola_courts
    import query_georgia_court_access
    import query_georgia_court_data
    import query_georgia_court_directory
    import query_georgia_supreme_docket
    import query_georgia_supreme_publications
    import query_georgia_property_sources
    import query_los_angeles_name_index
    import query_md_mdp_property_downloads
    import query_md_mdp_parcel_points
    import query_md_plats
    import query_md_estate_search
    import query_md_estate_notices_claims
    import query_md_business_opinions
    import query_md_judgment_liens
    import query_md_opinions
    import query_md_public_cases
    import query_mason_county_tax_parcels
    import query_michigan_appellate
    import query_michigan_business_court
    import query_michigan_property_directories
    import query_montana_cadastral
    import query_new_mexico_case_lookup
    import query_new_jersey_dca_property
    import query_new_jersey_parcels
    import query_new_jersey_sr1a
    import query_new_jersey_tax_court
    import query_new_jersey_tax_court_opinions
    import query_ny_attorneys
    import query_ny_salesweb
    import query_ny_statewide_parcels
    import query_nyc_pip
    import query_licking_foreclosure_archive
    import query_ohio_franklin_auditor_bulk
    import query_ohio_franklin_sales_gis
    import query_ohio_delaware_common_pleas
    import query_ohio_franklin_courts
    import query_ohio_franklin_municipal
    import query_ohio_licking_common_pleas
    import query_ohio_franklin_probate
    import query_ohio_pax_recorders
    import query_ohio_reporter_decisions
    import query_ohio_sheriff_sales
    import query_ohio_licking_property
    import query_ohio_statewide_parcels
    import query_ohio_supreme_court
    import query_orange_county_court
    import query_orange_tax_collector
    import query_oregon_lane_property
    import query_palm_beach_official_records
    import query_palm_beach_property_appraiser
    import query_palm_beach_tax_collector
    import query_palm_beach_tax_deeds
    import query_philadelphia_property
    import query_qld_ecourts
    import query_riverside_court
    import query_san_diego_court_index
    import query_santa_clara_court_records
    import query_santa_fe_clerktrack
    import query_santa_fe_property
    import query_texas_supreme_publications
    import query_txgio_land_parcels
    import query_usvi_property_tax
    import query_usvi_recorder
    import query_va_beach_delinquent_tax
    import query_va_general_district
    import query_virginia_parcels
    import query_wisconsin_court_directory
    from kofile_publicsearch import (
        KofileAccessError,
        KofileNotFoundError,
        KofilePublicSearchClient,
        KofilePublicSearchError,
        KofileRateLimitError,
        KofileSourceChangedError,
    )
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        BulkArtifact,
        BulkSourceError,
        BulkTransferClient,
    )
    from public_records_catalog import (
        DEFAULT_DB_PATH,
        PROBE_STATUSES,
        CatalogError,
        PublicRecordsCatalog,
        acquisition_result_status,
    )
    from public_records_contract import (
        PublicRecordsResult,
        ResultStatus,
        sha256_fingerprint,
    )
    from public_records_http import (
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        _BaseJSONClient,
        inferred_schema,
        system_trust_session,
    )
    from query_massgis_property import (
        MANIFEST_FIELDS as MASSGIS_MANIFEST_FIELDS,
        MANIFEST_LAYER_URL as MASSGIS_MANIFEST_LAYER_URL,
    )
    from query_bexar_property import (
        OUT_FIELDS as BEXAR_PROPERTY_FIELDS,
        TABLE_ORDER_BY as BEXAR_PROPERTY_ORDER,
        TABLE_URL as BEXAR_PROPERTY_TABLE_URL,
    )
    from query_denver_property import (
        LAYER_URL as DENVER_PROPERTY_LAYER_URL,
        OUT_FIELDS as DENVER_PROPERTY_FIELDS,
        PROBE_SCHEDULE_NUMBER as DENVER_PROPERTY_PROBE_SCHEDULE,
    )
    from query_deschutes_property import (
        SERVICE_URL as DESCHUTES_PROPERTY_SERVICE_URL,
        SOURCE_ID as DESCHUTES_PROPERTY_SOURCE_ID,
        execute as execute_deschutes_property,
    )
    from query_deschutes_dial import (
        BASE_URL as DESCHUTES_DIAL_BASE_URL,
        DEFAULT_COMPONENTS as DESCHUTES_DIAL_COMPONENTS,
        SOURCE_ID as DESCHUTES_DIAL_SOURCE_ID,
        execute as execute_deschutes_dial,
    )
    from query_deschutes_laserfiche import (
        BASE_URL as DESCHUTES_CDD_WEBLINK_BASE_URL,
        DEFAULT_MAX_DOCUMENT_BYTES as DESCHUTES_CDD_MAX_DOCUMENT_BYTES,
        DEFAULT_MAX_RESPONSE_BYTES as DESCHUTES_CDD_MAX_RESPONSE_BYTES,
        DEFAULT_POLL_ATTEMPTS as DESCHUTES_CDD_POLL_ATTEMPTS,
        DEFAULT_POLL_INTERVAL as DESCHUTES_CDD_POLL_INTERVAL,
        SOURCE_ID as DESCHUTES_CDD_WEBLINK_SOURCE_ID,
        execute as execute_deschutes_cdd_weblink,
    )
    from query_denver_delinquent_tax import (
        DEFAULT_MAX_ARCHIVE_MEMBERS as DENVER_TAX_MAX_ARCHIVE_MEMBERS,
        DEFAULT_MAX_COMPRESSION_RATIO as DENVER_TAX_MAX_COMPRESSION_RATIO,
        DEFAULT_MAX_MEMBER_UNCOMPRESSED_BYTES as DENVER_TAX_MAX_MEMBER_BYTES,
        DEFAULT_MAX_UNCOMPRESSED_BYTES as DENVER_TAX_MAX_UNCOMPRESSED_BYTES,
        DEFAULT_SAMPLE_BYTES as DENVER_TAX_SAMPLE_BYTES,
        PUBLICATION_PAGE as DENVER_TAX_PUBLICATION_PAGE,
        execute as execute_denver_delinquent_tax,
    )
    from query_denver_foreclosures import (
        DEFAULT_PROBE_FORECLOSURE as DENVER_FORECLOSURE_PROBE_ID,
        SEARCH_URL as DENVER_FORECLOSURE_SEARCH_URL,
        execute as execute_denver_foreclosures,
    )
    from query_denver_county_court import (
        DOCKET_URL as DENVER_COUNTY_COURT_DOCKET_URL,
        execute as execute_denver_county_court,
    )
    from query_colorado_judicial import (
        DOCKET_URL as COLORADO_JUDICIAL_DOCKET_URL,
        execute as execute_colorado_judicial,
    )
    from query_colorado_court_data import (
        ANNUAL_REPORTS_URL as COLORADO_COURT_DATA_URL,
        ColoradoCourtDataClient,
        execute as execute_colorado_court_data,
    )
    from query_colorado_opinions import (
        CASE_LAW_BASE_URL as COLORADO_OPINIONS_ARCHIVE_URL,
        JUDICIAL_BASE_URL as COLORADO_OPINIONS_RELEASE_URL,
        execute as execute_colorado_opinions,
    )
    from query_dc_opinions import (
        EXPECTED_HEADERS as DC_OPINIONS_EXPECTED_HEADERS,
        INDEX_URL as DC_OPINIONS_URL,
        NATIVE_ORDERS as DC_OPINIONS_NATIVE_ORDERS,
        NATIVE_TYPES as DC_OPINIONS_NATIVE_TYPES,
        PROBE_APPEAL_NUMBER as DC_OPINIONS_PROBE_APPEAL_NUMBER,
        ROWS_PER_PAGE as DC_OPINIONS_ROWS_PER_PAGE,
        SOURCE_ID as DC_OPINIONS_SOURCE_ID,
        SOURCE_METADATA as DC_OPINIONS_SOURCE_METADATA,
        execute as execute_dc_opinions,
    )
    from query_dc_superior_calendar import (
        APPEALS_SOURCE_ID as DC_APPEALS_CALENDAR_SOURCE_ID,
        APPEALS_URL as DC_APPEALS_CALENDAR_URL,
        CRIMINAL_SOURCE_ID as DC_CRIMINAL_CALENDAR_SOURCE_ID,
        CRIMINAL_URL as DC_CRIMINAL_CALENDAR_URL,
        SOURCE_METADATA_BY_ID as DC_CALENDAR_SOURCE_METADATA,
        SOURCE_WARNINGS as DC_CALENDAR_SOURCE_WARNINGS,
        TAX_SOURCE_ID as DC_TAX_CALENDAR_SOURCE_ID,
        TAX_URL as DC_TAX_CALENDAR_URL,
        TODAY_SOURCE_ID as DC_TODAY_CALENDAR_SOURCE_ID,
        TODAY_URL as DC_TODAY_CALENDAR_URL,
        execute as execute_dc_superior_calendar,
    )
    from query_fresno_superior_court import (
        CALENDAR_INDEX_URL as FRESNO_CALENDAR_URL,
        CALENDAR_SOURCE_ID as FRESNO_CALENDAR_SOURCE_ID,
        FAMILY_SOURCE_ID as FRESNO_FAMILY_SOURCE_ID,
        PORTAL_SOURCE_ID as FRESNO_PORTAL_SOURCE_ID,
        PORTAL_URL as FRESNO_PORTAL_URL,
        PROBATE_NOTES_URL as FRESNO_PROBATE_URL,
        PROBATE_SOURCE_ID as FRESNO_PROBATE_SOURCE_ID,
        RULINGS_INDEX_URL as FRESNO_RULINGS_URL,
        RULINGS_SOURCE_ID as FRESNO_RULINGS_SOURCE_ID,
        SOURCE_METADATA as FRESNO_SOURCE_METADATA,
        SOURCE_WARNINGS as FRESNO_SOURCE_WARNINGS,
        execute as execute_fresno_superior_court,
    )
    from query_delaware_firstmap import (
        SERVICE_URL as DELAWARE_FIRSTMAP_SERVICE_URL,
        execute as execute_delaware_firstmap,
    )
    from query_arlington_property import (
        LAYER_URL as ARLINGTON_PROPERTY_LAYER_URL,
        execute as execute_arlington_property,
    )
    from query_bexar_courts import (
        BASE_URL as BEXAR_HISTORICAL_BASE_URL,
        DEPARTMENT as BEXAR_HISTORICAL_DEPARTMENT,
        PROBE_DATE_FROM as BEXAR_HISTORICAL_PROBE_DATE_FROM,
        PROBE_DATE_TO as BEXAR_HISTORICAL_PROBE_DATE_TO,
        WEBSOCKET_URL as BEXAR_HISTORICAL_WEBSOCKET_URL,
    )
    from query_nc_property import (
        LAYER_URL as NC_ONEMAP_LAYER_URL,
        OUT_FIELDS as NC_ONEMAP_FIELDS,
    )
    from query_orleans_property import (
        LAYER_URL as ORLEANS_PROPERTY_LAYER_URL,
        LOCATOR_URL as ORLEANS_PROPERTY_LOCATOR_URL,
        PROBE_GEOPIN as ORLEANS_PROPERTY_PROBE_GEOPIN,
    )
    from query_oregon_appellate import (
        API_ROOT as OREGON_APPELLATE_API_ROOT,
        SOURCE_ID as OREGON_APPELLATE_SOURCE_ID,
        execute as execute_oregon_appellate,
    )
    from query_oregon_appellate_calendars import (
        COURT_OF_APPEALS as OREGON_COA_CALENDAR,
        SUPREME_COURT as OREGON_SUPREME_CALENDAR,
        execute as execute_oregon_appellate_calendars,
    )
    from query_oregon_court_calendar import (
        LANDING_URL as OREGON_COURT_CALENDAR_URL,
        SOURCE_ID as OREGON_COURT_CALENDAR_SOURCE_ID,
        execute as execute_oregon_court_calendar,
    )
    from query_oregon_court_documents import (
        COLLECTIONS as OREGON_COURT_DOCUMENT_COLLECTIONS,
        execute as execute_oregon_court_documents,
    )
    from query_oregon_court_directories import (
        LISTS_URL as OREGON_COURT_DIRECTORY_LISTS_URL,
        SOURCES_BY_ID as OREGON_COURT_DIRECTORY_SOURCES,
        execute as execute_oregon_court_directories,
    )
    from query_oregon_ojcin_products import (
        ADAPTER_SCHEMA_FINGERPRINT as OREGON_OJCIN_SCHEMA_FINGERPRINT,
        ENDPOINTS as OREGON_OJCIN_ENDPOINTS,
        OJCIN_URL as OREGON_OJCIN_URL,
        PRODUCTS as OREGON_OJCIN_PRODUCTS,
        SOURCE_ID as OREGON_OJCIN_SOURCE_ID,
        OfficialEndpointClient as OregonOJCINEndpointClient,
        probe_all as run_oregon_ojcin_endpoint_probe,
    )
    from query_oregon_smart_search import (
        FORM_ACTION_URL as OREGON_SMART_SEARCH_FORM_ACTION_URL,
        ROLLING_OPTION_FIELDS as OREGON_SMART_SEARCH_ROLLING_OPTION_FIELDS,
        SOURCE_ID as OREGON_SMART_SEARCH_SOURCE_ID,
        SOURCE_URL as OREGON_SMART_SEARCH_URL,
        execute as execute_oregon_smart_search,
    )
    from query_oregon_taxlots import (
        SOURCES as OREGON_TAXLOT_SOURCES,
        execute as execute_oregon_taxlots,
    )
    import query_dc_property
    import query_los_angeles_ttc
    import query_oregon_benton_property
    import query_oregon_clackamas_property
    import query_oregon_lincoln_propertyweb
    import query_oregon_lincoln_taxlots
    import query_oregon_marion_downloads
    import query_oregon_multnomah_sail
    import query_oregon_wasco_property
    import query_oregon_washington_case_permits
    import query_oregon_washington_property
    import query_washington_courts
    import query_washington_digital_archives_land
    import query_washington_parcels
    import query_washington_taxsifter
    import query_wisconsin_parcels
    import query_wy_dor_parcels
    import query_wisconsin_opinions
    import query_wisconsin_wscca
    import query_oregon_yamhill_property
    from query_oregon_helion_property import (
        PLATFORM_FAMILY as OREGON_HELION_PROPERTY_PLATFORM,
        TENANTS_BY_SOURCE as OREGON_HELION_PROPERTY_TENANTS,
        execute as execute_oregon_helion_property,
    )
    from query_oregon_jackson_accela import (
        SOURCES as OREGON_JACKSON_ACCELA_SOURCES,
        execute as execute_oregon_jackson_accela,
    )
    from query_oregon_jackson_douglas_assessors import (
        SOURCES as OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCES,
        execute as execute_oregon_jackson_douglas_assessors,
    )
    from query_oregon_jackson_property_events import (
        SOURCES as OREGON_JACKSON_PROPERTY_EVENT_SOURCES,
        execute as execute_oregon_jackson_property_events,
    )
    from query_oregon_helion_recorder import (
        TENANTS_BY_SOURCE as OREGON_HELION_RECORDER_TENANTS,
        execute as execute_oregon_helion_recorder,
    )
    from query_oregon_linn_josephine_klamath_assessors import (
        SOURCES as OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SOURCES,
        execute as execute_oregon_linn_josephine_klamath_assessors,
    )
    from query_oregon_lane_marion_parcels import (
        SOURCES as OREGON_LANE_MARION_PROPERTY_SOURCES,
        execute as execute_oregon_lane_marion_property,
    )
    from query_eugene_municipal_court import (
        OREGON_TENANTS as OREGON_TYLER_MUNICIPAL_TENANTS,
        execute as execute_eugene_municipal_court,
    )
    from query_oregon_tax_foreclosures import (
        DEFAULT_MAX_DOCUMENT_BYTES as OREGON_TAX_FORECLOSURE_MAX_DOCUMENT_BYTES,
        SOURCES as OREGON_TAX_FORECLOSURE_SOURCES,
        SOURCE_PROCESS_STAGES as OREGON_TAX_FORECLOSURE_PROCESS_STAGES,
        discover_source as discover_oregon_tax_foreclosure_source,
        fetch_bytes as fetch_oregon_tax_foreclosure_bytes,
    )
    from query_vicourts import (
        CASE_SEARCH_URL as VICOURTS_CASE_SEARCH_URL,
        DOCUMENT_SEARCH_URL as VICOURTS_DOCUMENT_SEARCH_URL,
        INFO_URL as VICOURTS_INFO_URL,
        LEGACY_FILE_URL as VICOURTS_LEGACY_FILE_URL,
        PUBLICATION_SEARCH_URL as VICOURTS_PUBLICATION_SEARCH_URL,
        VICourtsClient,
        normalize_case_number as normalize_vicourts_case_number,
    )
    from query_miami_dade_property import (
        PARCEL_LAYER_URL as MIAMI_DADE_PARCEL_LAYER_URL,
        PARCEL_ORDER_BY as MIAMI_DADE_PARCEL_ORDER,
        PARCEL_OUT_FIELDS as MIAMI_DADE_PARCEL_FIELDS,
        PROXY_URL as MIAMI_DADE_PA_PROXY_URL,
        MiamiDadePAClient,
    )
    from query_miami_dade_recorder import (
        PUBLIC_DOCUMENT_TYPES_API as MIAMI_DADE_DOCUMENT_TYPES_URL,
        MiamiDadeRecorderClient,
    )
    from query_orange_county_courts import (
        CALENDAR_URL as ORANGE_CALENDAR_URL,
        OrangeCountyCourtsClient,
    )
    from query_los_angeles_court import (
        CASE_SEARCH_URL as LOS_ANGELES_CIVIL_CASE_SEARCH_URL,
        PROBE_CASE_NUMBER as LOS_ANGELES_CIVIL_PROBE_CASE_NUMBER,
        SOURCE_ID as LOS_ANGELES_CIVIL_SOURCE_ID,
        SOURCE_METADATA as LOS_ANGELES_CIVIL_SOURCE_METADATA,
        SOURCE_WARNINGS as LOS_ANGELES_CIVIL_SOURCE_WARNINGS,
        TENTATIVE_INDEX_URL as LOS_ANGELES_CIVIL_TENTATIVE_INDEX_URL,
        LosAngelesCourtClient,
    )
    from query_los_angeles_probate import (
        CASE_SEARCH_URL as LOS_ANGELES_PROBATE_CASE_SEARCH_URL,
        PROBE_CASE_NUMBER as LOS_ANGELES_PROBATE_PROBE_CASE_NUMBER,
        LosAngelesProbateClient,
    )
    from query_ny_law_reports import (
        BASE_URL as NY_LAW_REPORTS_BASE_URL,
        run_sentinel as run_ny_law_reports_sentinel,
    )
    from query_ny_column import (
        PORTAL_URL as NY_COLUMN_PORTAL_URL,
        run_sentinel as run_ny_column_sentinel,
    )
    from query_pa_ujs import (
        CASE_SEARCH_URL as PA_UJS_CASE_SEARCH_URL,
        execute as execute_pa_ujs,
    )
    from query_pa_opinions import (
        API_URL as PA_OPINIONS_API_URL,
        execute as execute_pa_opinions,
    )
    from query_delaware_courts import (
        OFFICIAL_CIVIL_SEARCH_URL as DELAWARE_COURTCONNECT_URL,
        execute as execute_delaware_courts,
    )
    from query_delaware_opinions import (
        INDEX_URL as DELAWARE_OPINIONS_URL,
        execute as execute_delaware_opinions,
    )
    from query_harris_recorder import (
        SEARCH_URL as HARRIS_RECORDER_SEARCH_URL,
        HarrisRecorderClient,
        run_sentinel as run_harris_recorder_sentinel,
    )
    from query_harris_foreclosures import (
        SEARCH_URL as HARRIS_FORECLOSURE_SEARCH_URL,
        HarrisForeclosureClient,
        run_sentinel as run_harris_foreclosure_sentinel,
    )
    from query_harris_court_bulk import (
        CATALOG_URL as HARRIS_COURT_BULK_CATALOG_URL,
        DEFAULT_SAMPLE_BYTES as HARRIS_COURT_BULK_SAMPLE_BYTES,
        JURISDICTION as HARRIS_COURT_BULK_JURISDICTION,
        SENTINEL_FILENAME as HARRIS_COURT_BULK_SENTINEL_FILENAME,
        SENTINEL_LOCATOR as HARRIS_COURT_BULK_SENTINEL_LOCATOR,
        SENTINEL_PUBLISHED_DATE as HARRIS_COURT_BULK_SENTINEL_PUBLISHED_DATE,
        SOURCE_ID as HARRIS_COURT_BULK_SOURCE_ID,
        SOURCE_METADATA as HARRIS_COURT_BULK_SOURCE_METADATA,
        DatasetArtifact as HarrisCourtBulkDatasetArtifact,
        HarrisCourtBulkClient,
        run_sentinel as run_harris_court_bulk_sentinel,
    )
    from query_palm_beach_courts import (
        BASE_URL as PALM_BEACH_ECASEVIEW_URL,
        run_browser_helper as run_palm_beach_browser_helper,
    )
    from query_pima_courts import (
        BASE_URL as PIMA_PUBLICDOCS_URL,
        PimaCourtClient,
    )
    from query_san_mateo_midx import (
        LANDING_URL as SAN_MATEO_MIDX_URL,
        MIDXClient,
    )
    from query_tax_court import (
        API_ROOT as TAX_COURT_API_ROOT,
        TaxCourtClient,
    )
    from query_reeves_records import (
        BASE_URL as REEVES_RECORDS_BASE_URL,
        DEPARTMENT as REEVES_RECORDS_DEPARTMENT,
        PROBE_DOCUMENT_ID as REEVES_RECORDS_PROBE_DOCUMENT_ID,
        PROBE_INSTRUMENT_NUMBER as REEVES_RECORDS_PROBE_INSTRUMENT_NUMBER,
        ReevesRecordsClient,
        WEBSOCKET_URL as REEVES_RECORDS_WEBSOCKET_URL,
        normalize_instrument as normalize_kofile_instrument,
    )
    from query_govos_recorders import (
        TENANTS_BY_SOURCE as GOVOS_RECORDER_TENANTS,
    )
    from query_rrc_bulk import (
        SHARE_URLS as TEXAS_RRC_SHARE_URLS,
        SOURCE_CONTRACTS as TEXAS_RRC_SOURCE_CONTRACTS,
        RRCGoDriveClient,
        preferred_release as preferred_texas_rrc_release,
    )
    from query_texas_appellate import (
        SEARCH_URL as TEXAS_TAMES_SEARCH_URL,
        TexasTAMESClient,
        normalize_case as normalize_texas_tames_case,
    )

FLORIDA_ACIS_API_ROOT = "https://acis-api.flcourts.gov"
FLORIDA_ACIS_COURTS_URL = f"{FLORIDA_ACIS_API_ROOT}/courts"
FLORIDA_ACIS_SESSION_TYPES_URL = f"{FLORIDA_ACIS_API_ROOT}/cms/courtsessiontypes"
FLORIDA_ACIS_EVENT_SEARCH_URL = f"{FLORIDA_ACIS_API_ROOT}/courts/cms/events"
FLORIDA_ACIS_CALENDAR_URL = "https://acis.flcourts.gov/portal/search/calendar"
try:
    try:
        from tools.query_florida_acis import (
            COURTS_URL as FLORIDA_ACIS_COURTS_URL,
            EVENT_SEARCH_URL as FLORIDA_ACIS_EVENT_SEARCH_URL,
            SESSION_TYPES_URL as FLORIDA_ACIS_SESSION_TYPES_URL,
            FloridaACISClient,
        )
    except ImportError:
        from query_florida_acis import (
            COURTS_URL as FLORIDA_ACIS_COURTS_URL,
            EVENT_SEARCH_URL as FLORIDA_ACIS_EVENT_SEARCH_URL,
            SESSION_TYPES_URL as FLORIDA_ACIS_SESSION_TYPES_URL,
            FloridaACISClient,
        )
except ImportError:  # pragma: no cover - adapter can be installed independently
    FloridaACISClient = None

FLORIDA_ACIS_CALENDAR_PROBE_COURT_UUID = "8f454fb9-4c7f-43df-856b-ab373e71c27f"
FLORIDA_ACIS_CALENDAR_PROBE_COURT_ID = "3"
FLORIDA_ACIS_CALENDAR_PROBE_DATE = "2026-08-19"
FLORIDA_ACIS_CALENDAR_PROBE_SESSION_TYPE_ID = "1000003"
FLORIDA_ACIS_CALENDAR_PROBE_SESSION_TYPE_NAME = "Oral Argument"
FLORIDA_ACIS_CALENDAR_PROBE_EVENT_QUERY = "Khouzam"
FLORIDA_ACIS_CALENDAR_PROBE_EVENT_UUID = "39a9537b-2a08-4c3b-a78b-bb6acaaeb537"


MONITOR_ACTOR = "public_records_monitor"
OREGON_APPELLATE_CALENDAR_SOURCES = {
    source.source_id: source
    for source in (OREGON_COA_CALENDAR, OREGON_SUPREME_CALENDAR)
}
OREGON_TYLER_MUNICIPAL_TENANTS_BY_SOURCE = {
    tenant.source_id: tenant for tenant in OREGON_TYLER_MUNICIPAL_TENANTS.values()
}
ORLEANS_PROPERTY_QUERY_URL = f"{ORLEANS_PROPERTY_LAYER_URL}/query"
ORLEANS_PROPERTY_LOCATOR_CANDIDATES_URL = (
    f"{ORLEANS_PROPERTY_LOCATOR_URL}/findAddressCandidates"
)
ORLEANS_PROPERTY_DEPLOYED_VIEWER_LAYER_URL = (
    "https://gis.nola.gov/arcgis/rest/services/dev/property3/MapServer/15"
)
ORLEANS_PROPERTY_CANONICAL_VIEWER_LAYER_URL = (
    "https://gis.nola.gov/arcgis/rest/services/apps/property3/MapServer/15"
)
ORLEANS_PROPERTY_PROBE_TAX_BILL_ID = "104103301"
ORANGE_TAX_COLLECTOR_SENTINEL_ACCOUNT = "012027000000001"
VICOURTS_PROBE_CASE_NUMBER = "ST-2019-PB-00080"
VICOURTS_PROBE_PUBLICATION_NUMBER = "PB-2026-00032"
VICOURTS_PROBE_LEGACY_ITEM_ID = 16911884
TEXAS_TAMES_PROBE_CASE_NUMBER = "03-25-00287-CV"
TEXAS_TAMES_PROBE_COURT_CODE = "coa03"
TEXAS_TAMES_PROBE_DOCUMENT_ID = "bc16a831-998e-449f-9d28-84b61486178b"
TEXAS_RRC_SOURCE_KEYS = {
    contract["source_id"]: source_key
    for source_key, contract in TEXAS_RRC_SOURCE_CONTRACTS.items()
}
OHIO_REALAUCTION_SHARED_OPERATIONS = (
    "address",
    "discovery",
    "event",
    "freshness",
    "parcel",
    "probe",
    "sale",
    "search",
)
LICKING_FORECLOSURE_ARCHIVE_SHARED_OPERATIONS = (
    "address",
    "discovery",
    "event",
    "parcel",
    "probe",
    "releases",
    "sale",
    "search",
)


@dataclass(frozen=True)
class ProbeContext:
    """Runtime values visible to every registered handler."""

    source_id: str
    catalog_decision: Mapping[str, Any]
    timeout: float
    max_attempts: int
    sample_bytes: int | None


@dataclass(frozen=True)
class ProbeObservation:
    """Normalized probe data accepted by the catalog."""

    status: str
    endpoint: str | None = None
    http_status: int | None = None
    latency_ms: float | None = None
    schema_sha256: str | None = None
    artifact_sha256: str | None = None
    result_count: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in PROBE_STATUSES:
            raise ValueError(f"unsupported probe status: {self.status}")
        if self.status == "error" and not self.error:
            raise ValueError("error observations require an error message")
        if self.status == ResultStatus.NO_RESULTS.value and self.error:
            raise ValueError("no_results observations cannot contain an error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "endpoint": self.endpoint,
            "http_status": self.http_status,
            "latency_ms": self.latency_ms,
            "schema_sha256": self.schema_sha256,
            "artifact_sha256": self.artifact_sha256,
            "result_count": self.result_count,
            "details": dict(self.details),
            "error": self.error,
        }


def _json_ready(value: Any) -> Any:
    """Convert immutable adapter containers to ordinary JSON containers."""

    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


ProbeHandler = Callable[[ProbeContext], ProbeObservation]


@dataclass(frozen=True)
class ProbeHandlerSpec:
    """Visible registration for one low-cost source sentinel."""

    source_id: str
    capability: str
    endpoint: str
    observation: str
    expected_requests: int
    sentinel_record_count: int
    sample_bytes: int | None
    handler: ProbeHandler

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "capability": self.capability,
            "endpoint": self.endpoint,
            "observation": self.observation,
            "expected_requests": self.expected_requests,
            "sentinel_record_count": self.sentinel_record_count,
            "sample_bytes": self.sample_bytes,
        }


def _catalog_interval(decision: Mapping[str, Any]) -> float:
    limits = decision.get("limits") or {}
    return float(limits.get("minimum_interval_seconds") or 0)


def probe_nc_onemap(context: ProbeContext) -> ProbeObservation:
    """Fetch one NC OneMap feature and its declared ArcGIS schema."""
    started = time.perf_counter()
    client = ArcGISRESTClient(
        NC_ONEMAP_LAYER_URL,
        page_size=1,
        max_records=1,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    fetched = client.query(
        where="1=1",
        out_fields=NC_ONEMAP_FIELDS,
        requested_limit=1,
        max_records=1,
        return_geometry=False,
    )
    status = ResultStatus.OK.value if fetched.records else ResultStatus.NO_RESULTS.value
    return ProbeObservation(
        status=status,
        endpoint=client.query_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=fetched.schema_fingerprint,
        result_count=len(fetched.records),
        details={
            "sentinel_query": "1=1",
            "requested_fields": list(NC_ONEMAP_FIELDS),
            "pages_fetched": fetched.pages_fetched,
            "requests_made": fetched.requests_made,
            "next_cursor": fetched.next_cursor,
            "warnings": list(fetched.warnings),
        },
    )


def _arcgis_object(payload: Any, description: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"Orleans {description} response is not an object")
    if "error" in payload:
        raise ValueError(
            f"Orleans {description} returned an ArcGIS error: {payload['error']!r}"
        )
    return payload


def _arcgis_features(
    payload: Any,
    description: str,
) -> list[Mapping[str, Any]]:
    response = _arcgis_object(payload, description)
    features = response.get("features")
    if not isinstance(features, list) or any(
        not isinstance(feature, Mapping) for feature in features
    ):
        raise ValueError(f"Orleans {description} response lacks a features array")
    return list(features)


def _arcgis_fields(
    payload: Mapping[str, Any],
    description: str,
) -> list[dict[str, Any]]:
    fields = payload.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field_definition, Mapping) for field_definition in fields
    ):
        raise ValueError(f"Orleans {description} response lacks field definitions")
    return [dict(field_definition) for field_definition in fields]


def _epoch_millis_iso(value: Any, description: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"Orleans {description} is not an epoch-millisecond value")
    try:
        milliseconds = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Orleans {description} is not an epoch-millisecond value"
        ) from error
    if milliseconds <= 0:
        raise ValueError(f"Orleans {description} must be positive")
    return (
        datetime.fromtimestamp(milliseconds / 1_000, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def probe_orleans_property(context: ProbeContext) -> ProbeObservation:
    """Probe the rich parcel layer, locator, and deployed viewer layer."""
    started = time.perf_counter()
    client = _BaseJSONClient(
        session=system_trust_session(),
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )

    sentinel_payload = _arcgis_object(
        client._request_json(
            ORLEANS_PROPERTY_QUERY_URL,
            params={
                "where": (f"PARCELID='{ORLEANS_PROPERTY_PROBE_GEOPIN}'"),
                "outFields": (
                    "OBJECTID,PARCELID,PARID,TAXBILLID,SITEADDRESS,LASTUPDATE"
                ),
                "orderByFields": "OBJECTID ASC",
                "returnGeometry": "false",
                "resultRecordCount": 1,
                "f": "json",
            },
        ),
        "rich-layer sentinel",
    )
    sentinel_features = _arcgis_features(
        sentinel_payload,
        "rich-layer sentinel",
    )
    if len(sentinel_features) != 1:
        raise ValueError(
            "Orleans rich-layer sentinel expected exactly one bounded "
            f"feature, received {len(sentinel_features)}"
        )
    sentinel_attributes = sentinel_features[0].get("attributes")
    if not isinstance(sentinel_attributes, Mapping):
        raise ValueError("Orleans rich-layer sentinel feature lacks attributes")
    if str(sentinel_attributes.get("PARCELID") or "") != (
        ORLEANS_PROPERTY_PROBE_GEOPIN
    ):
        raise ValueError("Orleans rich-layer sentinel returned the wrong GeoPIN")
    sentinel_fields = _arcgis_fields(
        sentinel_payload,
        "rich-layer sentinel",
    )
    sentinel_field_names = {
        str(field_definition.get("name") or "") for field_definition in sentinel_fields
    }
    expected_sentinel_fields = {
        "OBJECTID",
        "PARCELID",
        "PARID",
        "TAXBILLID",
        "SITEADDRESS",
        "LASTUPDATE",
    }
    if not expected_sentinel_fields.issubset(sentinel_field_names):
        missing = sorted(expected_sentinel_fields - sentinel_field_names)
        raise ValueError(
            "Orleans rich-layer sentinel schema is missing: " + ", ".join(missing)
        )

    statistic_name = "max_lastupdate"
    freshness_payload = _arcgis_object(
        client._request_json(
            ORLEANS_PROPERTY_QUERY_URL,
            params={
                "where": "1=1",
                "outStatistics": json.dumps(
                    [
                        {
                            "statisticType": "max",
                            "onStatisticField": "LASTUPDATE",
                            "outStatisticFieldName": statistic_name,
                        }
                    ],
                    separators=(",", ":"),
                ),
                "returnGeometry": "false",
                "f": "json",
            },
        ),
        "freshness statistic",
    )
    freshness_features = _arcgis_features(
        freshness_payload,
        "freshness statistic",
    )
    if len(freshness_features) != 1:
        raise ValueError("Orleans freshness statistic expected one aggregate feature")
    freshness_attributes = freshness_features[0].get("attributes")
    if not isinstance(freshness_attributes, Mapping):
        raise ValueError("Orleans freshness statistic feature lacks attributes")
    freshness_value = next(
        (
            value
            for key, value in freshness_attributes.items()
            if str(key).casefold() == statistic_name
        ),
        None,
    )
    freshness_iso = _epoch_millis_iso(
        freshness_value,
        "maximum LASTUPDATE",
    )

    locator_payload = _arcgis_object(
        client._request_json(
            ORLEANS_PROPERTY_LOCATOR_CANDIDATES_URL,
            params={
                "SingleLine": ORLEANS_PROPERTY_PROBE_TAX_BILL_ID,
                "outSR": 102100,
                "outFields": "Address,User_fld,Loc_name,Match_addr",
                "maxLocations": 1,
                "f": "json",
            },
        ),
        "locator sentinel",
    )
    candidates = locator_payload.get("candidates")
    if not isinstance(candidates, list) or any(
        not isinstance(candidate, Mapping) for candidate in candidates
    ):
        raise ValueError("Orleans locator sentinel response lacks a candidates array")
    if len(candidates) != 1:
        raise ValueError(
            "Orleans locator sentinel expected exactly one bounded "
            f"candidate, received {len(candidates)}"
        )
    candidate = candidates[0]
    candidate_attributes = candidate.get("attributes")
    if not isinstance(candidate_attributes, Mapping):
        raise ValueError("Orleans locator sentinel candidate lacks attributes")
    if str(candidate.get("address") or "") != (ORLEANS_PROPERTY_PROBE_TAX_BILL_ID):
        raise ValueError("Orleans locator sentinel returned the wrong Tax Bill ID")
    if candidate_attributes.get("Loc_name") != "ParcelTaxbillL":
        raise ValueError(
            "Orleans locator sentinel no longer resolves through ParcelTaxbillL"
        )

    viewer_payload = _arcgis_object(
        client._request_json(
            ORLEANS_PROPERTY_DEPLOYED_VIEWER_LAYER_URL,
            params={"f": "json"},
        ),
        "deployed viewer layer",
    )
    viewer_fields = _arcgis_fields(
        viewer_payload,
        "deployed viewer layer",
    )
    viewer_field_names = {
        str(field_definition.get("name") or "") for field_definition in viewer_fields
    }
    expected_viewer_fields = {"PARCELID", "PARID", "TAXBILLID"}
    if not expected_viewer_fields.issubset(viewer_field_names):
        missing = sorted(expected_viewer_fields - viewer_field_names)
        raise ValueError(
            "Orleans deployed viewer-layer schema is missing: " + ", ".join(missing)
        )
    viewer_capabilities = {
        value.strip()
        for value in str(viewer_payload.get("capabilities") or "").split(",")
        if value.strip()
    }
    if (
        viewer_payload.get("id") != 15
        or viewer_payload.get("name") != "Property Information [Parcels]"
        or viewer_payload.get("geometryType") != "esriGeometryPolygon"
        or "Query" not in viewer_capabilities
    ):
        raise ValueError(
            "Orleans deployed viewer layer no longer matches the "
            "Property Viewer parcel contract"
        )

    schema_payload = {
        "rich_layer_query_fields": sentinel_fields,
        "locator_candidate": inferred_schema([dict(candidate)]),
        "deployed_viewer_layer": {
            "id": viewer_payload.get("id"),
            "name": viewer_payload.get("name"),
            "geometry_type": viewer_payload.get("geometryType"),
            "fields": viewer_fields,
        },
    }
    artifact_payload = {
        "sentinel": {
            key: sentinel_attributes.get(key)
            for key in (
                "OBJECTID",
                "PARCELID",
                "PARID",
                "TAXBILLID",
                "SITEADDRESS",
            )
        },
        "maximum_lastupdate": freshness_value,
        "locator": {
            "address": candidate.get("address"),
            "score": candidate.get("score"),
            "attributes": {
                key: candidate_attributes.get(key)
                for key in (
                    "Loc_name",
                    "Match_addr",
                    "User_fld",
                )
            },
        },
        "deployed_viewer": {
            "id": viewer_payload.get("id"),
            "name": viewer_payload.get("name"),
            "capabilities": sorted(viewer_capabilities),
        },
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=ORLEANS_PROPERTY_QUERY_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_payload),
        artifact_sha256=sha256_fingerprint(artifact_payload),
        result_count=len(sentinel_features),
        details={
            "sentinel_geopin": ORLEANS_PROPERTY_PROBE_GEOPIN,
            "sentinel_tax_bill_id": sentinel_attributes.get("TAXBILLID"),
            "sentinel_parid": sentinel_attributes.get("PARID"),
            "sentinel_source_last_updated": _epoch_millis_iso(
                sentinel_attributes.get("LASTUPDATE"),
                "sentinel LASTUPDATE",
            ),
            "maximum_source_last_updated": freshness_iso,
            "freshness_statistic": "max(LASTUPDATE)",
            "locator_query": ORLEANS_PROPERTY_PROBE_TAX_BILL_ID,
            "locator_role": candidate_attributes.get("Loc_name"),
            "locator_score": candidate.get("score"),
            "locator_endpoint": ORLEANS_PROPERTY_LOCATOR_CANDIDATES_URL,
            "deployed_viewer_layer": (ORLEANS_PROPERTY_DEPLOYED_VIEWER_LAYER_URL),
            "canonical_viewer_layer_mirror": (
                ORLEANS_PROPERTY_CANONICAL_VIEWER_LAYER_URL
            ),
            "viewer_layer_id": viewer_payload.get("id"),
            "viewer_layer_name": viewer_payload.get("name"),
            "viewer_field_count": len(viewer_fields),
            "requests_made": client.request_count,
        },
    )


def probe_bexar_property(context: ProbeContext) -> ProbeObservation:
    """Fetch one deterministically ordered BCAD property-summary record."""
    started = time.perf_counter()
    client = ArcGISRESTClient(
        BEXAR_PROPERTY_TABLE_URL,
        page_size=1,
        max_records=1,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    fetched = client.query(
        where="1=1",
        out_fields=BEXAR_PROPERTY_FIELDS,
        parameters={"orderByFields": BEXAR_PROPERTY_ORDER},
        requested_limit=1,
        max_records=1,
        return_geometry=False,
    )
    status = ResultStatus.OK.value if fetched.records else ResultStatus.NO_RESULTS.value
    return ProbeObservation(
        status=status,
        endpoint=client.query_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=fetched.schema_fingerprint,
        result_count=len(fetched.records),
        details={
            "sentinel_query": "1=1",
            "order_by": BEXAR_PROPERTY_ORDER,
            "requested_fields": list(BEXAR_PROPERTY_FIELDS),
            "pages_fetched": fetched.pages_fetched,
            "requests_made": fetched.requests_made,
            "next_cursor": fetched.next_cursor,
            "warnings": list(fetched.warnings),
        },
    )


def probe_denver_property(context: ProbeContext) -> ProbeObservation:
    """Fetch the known Denver schedule-number sentinel and declared schema."""
    started = time.perf_counter()
    client = ArcGISRESTClient(
        DENVER_PROPERTY_LAYER_URL,
        page_size=1,
        max_records=1,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    fetched = client.query(
        where=f"SCHEDNUM='{DENVER_PROPERTY_PROBE_SCHEDULE}'",
        out_fields=DENVER_PROPERTY_FIELDS,
        parameters={"orderByFields": "OBJECTID"},
        requested_limit=1,
        max_records=1,
        return_geometry=False,
    )
    artifact_sha256 = None
    if fetched.records:
        attributes = fetched.records[0].get("attributes")
        if not isinstance(attributes, Mapping):
            raise ValueError("Denver parcel sentinel lacks an attributes object")
        if str(attributes.get("SCHEDNUM") or "").strip() != (
            DENVER_PROPERTY_PROBE_SCHEDULE
        ):
            raise ValueError(
                "Denver parcel sentinel returned a different schedule number"
            )
        artifact_sha256 = sha256_fingerprint(
            {
                key: attributes.get(key)
                for key in (
                    "OBJECTID",
                    "SCHEDNUM",
                    "PARCELNUM",
                    "SYSTEM_START_DATE",
                    "RECEPTION_NUM",
                )
            }
        )
    status = ResultStatus.OK.value if fetched.records else ResultStatus.NO_RESULTS.value
    return ProbeObservation(
        status=status,
        endpoint=client.query_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=fetched.schema_fingerprint,
        artifact_sha256=artifact_sha256,
        result_count=len(fetched.records),
        details={
            "sentinel_schedule_number": DENVER_PROPERTY_PROBE_SCHEDULE,
            "requested_fields": list(DENVER_PROPERTY_FIELDS),
            "pages_fetched": fetched.pages_fetched,
            "requests_made": fetched.requests_made,
            "next_cursor": fetched.next_cursor,
            "warnings": list(fetched.warnings),
        },
    )


def probe_denver_foreclosures(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify GTS search, paging, detail sections, and document index."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        foreclosure_number=DENVER_FORECLOSURE_PROBE_ID,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_denver_foreclosures(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=DENVER_FORECLOSURE_SEARCH_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if record.get("record_kind") != "source_health_check":
        raise ValueError("Denver Public Trustee probe did not return a health record")
    schema_fingerprint = record.get("schema_fingerprint")
    artifact = {
        "foreclosure_number": record.get("foreclosure_number"),
        "detail_sections": record.get("detail_sections"),
        "document_count": record.get("document_count"),
    }
    return replace(
        observation,
        schema_sha256=(
            str(schema_fingerprint) if schema_fingerprint else observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(artifact),
        details={
            **dict(observation.details),
            "foreclosure_number": record.get("foreclosure_number"),
            "status_option_count": record.get("status_option_count"),
            "source_reported_total_results": record.get(
                "source_reported_total_results"
            ),
            "native_page_size": record.get("native_page_size"),
            "detail_sections": record.get("detail_sections"),
            "document_count": record.get("document_count"),
            "persistent_session_required": record.get("persistent_session_required"),
        },
    )


def probe_denver_delinquent_tax(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the current official XLSX release and workbook schema."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        sample_bytes=context.sample_bytes or DENVER_TAX_SAMPLE_BYTES,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        chunk_size=1024 * 1024,
        max_download_bytes=None,
        max_archive_members=DENVER_TAX_MAX_ARCHIVE_MEMBERS,
        max_uncompressed_bytes=DENVER_TAX_MAX_UNCOMPRESSED_BYTES,
        max_member_uncompressed_bytes=DENVER_TAX_MAX_MEMBER_BYTES,
        max_compression_ratio=DENVER_TAX_MAX_COMPRESSION_RATIO,
        output=None,
        json_out=False,
    )
    result = execute_denver_delinquent_tax(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=DENVER_TAX_PUBLICATION_PAGE,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if record.get("record_kind") != "source_health_check":
        raise ValueError("Denver delinquent-tax probe did not return a health record")
    inspection = dict(record.get("workbook_inspection") or {})
    release = dict(record.get("release") or {})
    receipt = dict(record.get("artifact_receipt") or {})
    schema_fingerprint = inspection.get("schema_fingerprint")
    artifact_sha256 = (
        inspection.get("artifact_sha256")
        or receipt.get("sha256")
        or observation.artifact_sha256
    )
    return replace(
        observation,
        schema_sha256=(
            str(schema_fingerprint) if schema_fingerprint else observation.schema_sha256
        ),
        artifact_sha256=(str(artifact_sha256) if artifact_sha256 else None),
        result_count=inspection.get("data_row_count"),
        details={
            **dict(observation.details),
            "tax_year": release.get("tax_year"),
            "release_date": release.get("release_date"),
            "artifact_url": release.get("artifact_url"),
            "artifact_size": inspection.get("artifact_size"),
            "data_row_count": inspection.get("data_row_count"),
            "rows_by_tax_year": inspection.get("rows_by_tax_year"),
            "worksheet": inspection.get("worksheet"),
            "archive_member_count": (
                dict(inspection.get("archive") or {}).get("member_count")
            ),
        },
    )


def probe_colorado_judicial(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the statewide docket directory, rows, paging, and export."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        courthouse=None,
        specific_date=None,
        date_range=None,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_colorado_judicial(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=COLORADO_JUDICIAL_DOCKET_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if record.get("record_kind") != "source_health_check":
        raise ValueError("Colorado Judicial probe did not return a health record")
    schema_fingerprint = record.get("schema_fingerprint")
    directory_fingerprint = record.get("directory_fingerprint")
    return replace(
        observation,
        schema_sha256=(
            str(schema_fingerprint) if schema_fingerprint else observation.schema_sha256
        ),
        artifact_sha256=(
            str(directory_fingerprint)
            if directory_fingerprint
            else observation.artifact_sha256
        ),
        result_count=record.get("parsed_row_count"),
        details={
            **dict(observation.details),
            "directory_counts": record.get("directory_counts"),
            "result_state": record.get("result_state"),
            "source_total_count": record.get("source_total_count"),
            "parsed_row_count": record.get("parsed_row_count"),
            "native_pagination": record.get("native_pagination"),
            "export_link_advertised": record.get("export_link_advertised"),
            "export_status": record.get("export_status"),
        },
    )


def probe_colorado_court_data(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify report discovery, one request form, and the eviction dashboard."""

    started = time.perf_counter()
    client = ColoradoCourtDataClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(0, context.max_attempts - 1),
    )
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        output=None,
        json_out=False,
    )
    try:
        result = execute_colorado_court_data(
            args,
            access_decision=context.catalog_decision,
            client=client,
            log_results=False,
        )
    finally:
        close = getattr(client.session, "close", None)
        if callable(close):
            close()
    observation = _adapter_result_observation(
        result,
        endpoint=COLORADO_COURT_DATA_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if record.get("record_kind") != "source_health_check":
        raise ValueError("Colorado court-data probe did not return a health record")
    schema_fingerprint = record.get("schema_fingerprint")
    catalog_identity = record.get("artifact_identity")
    return replace(
        observation,
        schema_sha256=(
            str(schema_fingerprint) if schema_fingerprint else observation.schema_sha256
        ),
        artifact_sha256=(
            str(catalog_identity) if catalog_identity else observation.artifact_sha256
        ),
        result_count=record.get("result_count"),
        details={
            **dict(observation.details),
            "component_counts": record.get("component_counts"),
            "source_pages": record.get("source_pages"),
            "sentinels": record.get("sentinels"),
        },
    )


def _probe_colorado_opinions_component(
    context: ProbeContext,
    *,
    component: str,
    endpoint: str,
) -> ProbeObservation:
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        component=component,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_colorado_opinions(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if record.get("record_kind") != "source_health_check":
        raise ValueError("Colorado opinions probe did not return a health-check record")
    if record.get("source_id") != context.source_id:
        raise ValueError("Colorado opinions health check returned another source")
    raw_components = record.get("component_sources")
    if (
        not isinstance(raw_components, Sequence)
        or isinstance(raw_components, (str, bytes))
        or len(raw_components) != 1
        or not isinstance(raw_components[0], Mapping)
    ):
        raise ValueError(
            "Colorado opinions component probe did not return one component"
        )
    component_record = dict(raw_components[0])
    if component_record.get("source_id") != context.source_id:
        raise ValueError("Colorado opinions component probe returned another source")
    if component == "archive":
        schema_payload = {
            key: component_record.get(key)
            for key in (
                "search_schema_fingerprint",
                "count_schema_fingerprint",
                "metadata_schema_fingerprint",
            )
        }
        artifact_payload = {
            key: component_record.get(key)
            for key in (
                "sentinel_document_id",
                "sentinel_result_count",
                "full_text_sha256",
                "pdf_byte_length",
                "pdf_media_type",
            )
        }
    else:
        schema_payload = {
            key: component_record.get(key)
            for key in (
                "supreme_schema_fingerprint",
                "appeals_schema_fingerprint",
            )
        }
        artifact_payload = {
            key: component_record.get(key)
            for key in (
                "supreme_current_page_records",
                "appeals_current_page_packets",
                "appeals_records_are_opinions",
            )
        }
    return replace(
        observation,
        schema_sha256=str(
            record.get("schema_fingerprint") or sha256_fingerprint(schema_payload)
        ),
        artifact_sha256=str(
            record.get("artifact_identity") or sha256_fingerprint(artifact_payload)
        ),
        result_count=record.get("result_count"),
        details={
            **dict(observation.details),
            "probe_component": component,
            "component_source": component_record,
            "source_roles_kept_distinct": record.get("source_roles_kept_distinct"),
            "native_pagination": record.get("native_pagination"),
        },
    )


def probe_colorado_opinions_archive(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify historical search, full text, and the sentinel opinion PDF."""

    return _probe_colorado_opinions_component(
        context,
        component="archive",
        endpoint=COLORADO_OPINIONS_ARCHIVE_URL,
    )


def probe_colorado_opinion_releases(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify current Supreme opinion and Court of Appeals release surfaces."""

    return _probe_colorado_opinions_component(
        context,
        component="releases",
        endpoint=COLORADO_OPINIONS_RELEASE_URL,
    )


def probe_dc_opinions(context: ProbeContext) -> ProbeObservation:
    """Verify the current D.C. appellate index and one opinion PDF."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    result = execute_dc_opinions(
        args,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=DC_OPINIONS_URL,
        started=started,
    )
    if not result.records:
        return observation

    record = result.records[0]
    if record.get("source_id") != DC_OPINIONS_SOURCE_ID:
        raise ValueError("D.C. opinions probe returned another source")
    probe = record.get("probe")
    probe_values = dict(probe) if isinstance(probe, Mapping) else {}
    provenance = record.get("provenance")
    provenance_values = dict(provenance) if isinstance(provenance, Mapping) else {}
    stable_contract = {
        "source": DC_OPINIONS_SOURCE_METADATA.to_dict(),
        "index_url": DC_OPINIONS_URL,
        "expected_headers": list(DC_OPINIONS_EXPECTED_HEADERS),
        "native_page_size": DC_OPINIONS_ROWS_PER_PAGE,
        "native_pagination": "zero_based_page",
        "native_types": dict(DC_OPINIONS_NATIVE_TYPES),
        "native_orders": dict(DC_OPINIONS_NATIVE_ORDERS),
        "publication_semantics": {
            "opinions": "court_hosted_pdf_when_linked",
            "mojs": "index_metadata_without_court_published_full_text",
        },
    }
    schema_contract = {
        "response_schema_fingerprint": provenance_values.get(
            "response_schema_fingerprint"
        ),
        "record_schema": inferred_schema([dict(record)]),
    }
    artifact_identity = {
        "probe_appeal_number": DC_OPINIONS_PROBE_APPEAL_NUMBER,
        "native_entry_id": record.get("native_entry_id"),
        "raw_case_number": record.get("raw_case_number"),
        "publication_kind": record.get("publication_kind"),
        "pdf_url": record.get("pdf_url"),
        "pdf_sha256": probe_values.get("pdf_sha256"),
        "pdf_media_type": probe_values.get("pdf_media_type"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "page_total_items": probe_values.get("page_total_items"),
                "page_total_pages": probe_values.get("page_total_pages"),
                "pdf_size_bytes": probe_values.get("pdf_size_bytes"),
            },
        },
    )


DC_CALENDAR_PROBE_ENDPOINTS = {
    DC_TODAY_CALENDAR_SOURCE_ID: DC_TODAY_CALENDAR_URL,
    DC_CRIMINAL_CALENDAR_SOURCE_ID: DC_CRIMINAL_CALENDAR_URL,
    DC_TAX_CALENDAR_SOURCE_ID: DC_TAX_CALENDAR_URL,
    DC_APPEALS_CALENDAR_SOURCE_ID: DC_APPEALS_CALENDAR_URL,
}


def probe_dc_calendar_component(context: ProbeContext) -> ProbeObservation:
    """Verify one D.C. calendar representation with its native operation."""

    started = time.perf_counter()
    common = {
        "timeout": context.timeout,
        "minimum_interval": _catalog_interval(context.catalog_decision),
        "retry_attempts": context.max_attempts,
        "output": None,
        "json_out": False,
    }
    if context.source_id == DC_TODAY_CALENDAR_SOURCE_ID:
        args = argparse.Namespace(command="probe", **common)
        operation = "bounded_source_family_probe"
    elif context.source_id == DC_CRIMINAL_CALENDAR_SOURCE_ID:
        args = argparse.Namespace(
            command="filters",
            calendar="criminal",
            **common,
        )
        operation = "criminal_filter_taxonomy"
    elif context.source_id == DC_TAX_CALENDAR_SOURCE_ID:
        args = argparse.Namespace(command="artifacts", family="tax", **common)
        operation = "tax_artifact_index"
    elif context.source_id == DC_APPEALS_CALENDAR_SOURCE_ID:
        args = argparse.Namespace(command="appeals", year=None, **common)
        operation = "appeals_artifact_index"
    else:
        raise ValueError(f"unsupported D.C. calendar source: {context.source_id}")

    endpoint = DC_CALENDAR_PROBE_ENDPOINTS[context.source_id]
    result = execute_dc_superior_calendar(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if not records:
        return observation
    if any(record.get("source_id") != context.source_id for record in records):
        raise ValueError("D.C. calendar probe returned another source")

    stable_contract = {
        "source": DC_CALENDAR_SOURCE_METADATA[context.source_id].to_dict(),
        "endpoint": endpoint,
        "probe_operation": operation,
        "record_kinds": sorted(
            {
                str(record.get("record_kind"))
                for record in records
                if record.get("record_kind")
            }
        ),
        "coverage_semantics": list(DC_CALENDAR_SOURCE_WARNINGS),
    }
    schema_contract = {"record_schema": inferred_schema(records)}
    operation_shapes = []
    for record in records:
        operations = record.get("operations")
        if isinstance(operations, Mapping):
            operation_shapes.append(
                {
                    str(name): sorted(dict(value))
                    for name, value in operations.items()
                    if isinstance(value, Mapping)
                }
            )
    artifact_identity = {
        "source_id": context.source_id,
        "endpoint": endpoint,
        "probe_operation": operation,
        "record_kinds": stable_contract["record_kinds"],
        "operation_shapes": operation_shapes,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "result_count": len(records),
                "records": [
                    {
                        "artifact_type": record.get("artifact_type"),
                        "calendar_year": record.get("calendar_year"),
                        "calendar_month": record.get("calendar_month"),
                        "document_url": record.get("document_url"),
                        "operations": record.get("operations"),
                    }
                    for record in records
                ],
            },
        },
    )


DC_DIRECTORY_DATA_MONITOR_SOURCE_IDS = {
    query_dc_court_directory_data.SUPERIOR_DIRECTORY_SOURCE_ID,
    query_dc_court_directory_data.APPEALS_DIRECTORY_SOURCE_ID,
    query_dc_court_directory_data.REPORTS_SOURCE_ID,
}


def probe_dc_court_directory_data_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one directly published D.C. directory or report catalog."""

    adapter = query_dc_court_directory_data
    if context.source_id not in DC_DIRECTORY_DATA_MONITOR_SOURCE_IDS:
        raise ValueError(
            "D.C. directory/data monitor supports the two judicial "
            "directories and the reports publication catalog"
        )

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--component",
            context.source_id,
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    component = adapter.COMPONENTS[context.source_id]
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=component.base_url,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("D.C. directory/data probe expected one health record")

    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_health_check"
        or record.get("source_id") != context.source_id
        or record.get("status") != "ok"
    ):
        raise ValueError("D.C. directory/data probe contract changed")

    if context.source_id in {
        adapter.SUPERIOR_DIRECTORY_SOURCE_ID,
        adapter.APPEALS_DIRECTORY_SOURCE_ID,
    }:
        expected_roles = (
            {"chief", "associate", "magistrate", "senior"}
            if context.source_id == adapter.SUPERIOR_DIRECTORY_SOURCE_ID
            else {"chief", "associate", "senior"}
        )
        role_counts_value = record.get("role_counts")
        if not isinstance(role_counts_value, Mapping):
            raise ValueError("D.C. directory role counts are missing")
        role_counts = {str(role): count for role, count in role_counts_value.items()}
        record_count = record.get("record_count")
        leadership_count = record.get("leadership_count")
        location_count = record.get("location_count")
        if (
            set(role_counts) != expected_roles
            or any(
                type(count) is not int or count < 1 for count in role_counts.values()
            )
            or type(record_count) is not int
            or record_count != sum(role_counts.values())
            or type(leadership_count) is not int
            or leadership_count < 1
            or type(location_count) is not int
            or location_count < 1
        ):
            raise ValueError("D.C. judicial-directory probe shape changed")
        probe_fields = {
            "canonical_ref",
            "leadership_count",
            "location_count",
            "record_count",
            "record_kind",
            "role_counts",
            "source_id",
            "status",
        }
        normalized_record_kinds = [
            "court_directory_judge",
            "court_directory_contact",
        ]
        if context.source_id == adapter.SUPERIOR_DIRECTORY_SOURCE_ID:
            normalized_record_kinds.append("court_assignment_publication")
        identity_contract = {
            "person": [
                "court_id",
                "judicial_role",
                "native_person_id",
                "profile_url",
            ],
            "shared_ingest_semantics": "snapshot_only",
        }
        stable_shape = {"expected_roles": sorted(expected_roles)}
        rolling_observation = {
            "record_count": record_count,
            "role_counts": role_counts,
            "leadership_count": leadership_count,
            "location_count": location_count,
        }
    else:
        section_counts_value = record.get("section_counts")
        if not isinstance(section_counts_value, Mapping):
            raise ValueError("D.C. reports section counts are missing")
        section_counts = {
            str(section): count for section, count in section_counts_value.items()
        }
        required_sections = {
            "annual-reports",
            "family-court-annual-reports",
        }
        publication_count = record.get("publication_count")
        observation_count = record.get("catalog_observation_count")
        if (
            not required_sections.issubset(section_counts)
            or any(
                type(count) is not int or count < 1 for count in section_counts.values()
            )
            or type(publication_count) is not int
            or publication_count != sum(section_counts.values())
            or type(observation_count) is not int
            or not 0 <= observation_count <= publication_count
        ):
            raise ValueError("D.C. reports publication-catalog probe shape changed")
        probe_fields = {
            "canonical_ref",
            "catalog_observation_count",
            "publication_count",
            "record_kind",
            "section_counts",
            "source_id",
            "status",
        }
        normalized_record_kinds = [
            "court_report_catalog_occurrence",
            "court_publication_pdf_artifact",
        ]
        identity_contract = {
            "publication_occurrence": [
                "catalog_section",
                "catalog_ordinal",
                "native_document_id",
            ],
            "artifact_locator": ["artifact_url"],
            "same_url_occurrences_preserved": True,
        }
        stable_shape = {
            "required_sections": sorted(required_sections),
        }
        rolling_observation = {
            "publication_count": publication_count,
            "section_counts": section_counts,
            "catalog_observation_count": observation_count,
        }

    if set(record) != probe_fields:
        raise ValueError("D.C. directory/data probe fields changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA[context.source_id].to_dict(),
        "jurisdiction": {
            "jurisdiction_id": adapter.STATE_GEOID,
            "name": "District of Columbia",
            "state_code": adapter.STATE_CODE,
        },
        "component": {
            "source_role": component.source_role,
            "base_url": component.base_url,
            "access_state": component.access_state,
            "operations": list(component.operations),
            "relationship": component.relationship,
            "coverage": component.coverage,
        },
        "publisher_and_transport": {
            "authority": "District of Columbia Courts",
            "publisher": "District of Columbia Courts",
            "retrieval_transport": "direct official HTTPS",
            "publisher_transport_distinct": False,
            "counts_as_independent_corroboration": False,
        },
        "official_alternatives": [
            {
                "source_id": source_id,
                "source_role": alternative.source_role,
                "base_url": alternative.base_url,
                "relationship": alternative.relationship,
            }
            for source_id, alternative in adapter.COMPONENTS.items()
            if source_id != context.source_id
        ],
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "probe_record_kind": "source_health_check",
        "probe_fields": sorted(probe_fields),
        "normalized_record_kinds": normalized_record_kinds,
        "identity_contract": identity_contract,
    }
    artifact_identity = {
        "source_id": context.source_id,
        "official_url": component.base_url,
        **stable_shape,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


FRESNO_PROBE_ENDPOINTS = {
    FRESNO_FAMILY_SOURCE_ID: FRESNO_PORTAL_URL,
    FRESNO_PORTAL_SOURCE_ID: FRESNO_PORTAL_URL,
    FRESNO_CALENDAR_SOURCE_ID: FRESNO_CALENDAR_URL,
    FRESNO_RULINGS_SOURCE_ID: FRESNO_RULINGS_URL,
    FRESNO_PROBATE_SOURCE_ID: FRESNO_PROBATE_URL,
}


def probe_fresno_court_component(context: ProbeContext) -> ProbeObservation:
    """Verify one Fresno source using its own anonymous representation."""

    started = time.perf_counter()
    common = {
        "timeout": context.timeout,
        "minimum_interval": _catalog_interval(context.catalog_decision),
        "max_attempts": context.max_attempts,
        "retry_backoff": 0.5,
        "output": None,
        "json_out": False,
    }
    if context.source_id == FRESNO_FAMILY_SOURCE_ID:
        args = argparse.Namespace(command="probe", **common)
        operation = "family_probe"
    elif context.source_id == FRESNO_PORTAL_SOURCE_ID:
        args = argparse.Namespace(command="portal", **common)
        operation = "portal_observation"
    elif context.source_id == FRESNO_CALENDAR_SOURCE_ID:
        args = argparse.Namespace(command="calendar-index", **common)
        operation = "calendar_artifact_index"
    elif context.source_id == FRESNO_RULINGS_SOURCE_ID:
        args = argparse.Namespace(command="rulings-index", **common)
        operation = "rulings_artifact_index"
    elif context.source_id == FRESNO_PROBATE_SOURCE_ID:
        args = argparse.Namespace(
            command="probate-notes",
            case_number="19CEPR00967",
            hearing_date=None,
            **common,
        )
        operation = "probate_note_sentinel"
    else:
        raise ValueError(f"unsupported Fresno source: {context.source_id}")

    endpoint = FRESNO_PROBE_ENDPOINTS[context.source_id]
    result = execute_fresno_superior_court(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if not records:
        return observation
    if any(record.get("source_id") != context.source_id for record in records):
        raise ValueError("Fresno component probe returned another source")

    stable_contract = {
        "source": FRESNO_SOURCE_METADATA[context.source_id].to_dict(),
        "endpoint": endpoint,
        "probe_operation": operation,
        "record_kinds": sorted(
            {
                str(record.get("record_kind"))
                for record in records
                if record.get("record_kind")
            }
        ),
        "coverage_semantics": list(FRESNO_SOURCE_WARNINGS),
    }
    schema_contract = {"record_schema": inferred_schema(records)}
    artifact_identity = {
        "source_id": context.source_id,
        "endpoint": endpoint,
        "probe_operation": operation,
        "record_kinds": stable_contract["record_kinds"],
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "result_count": len(records),
                "records": [
                    {
                        "publication_date": record.get("publication_date"),
                        "department": record.get("department"),
                        "case_number": record.get("case_number"),
                        "hearing_date": record.get("hearing_date"),
                        "source_url": record.get("source_url"),
                        "portal": record.get("portal"),
                        "calendar": record.get("calendar"),
                        "tentative_rulings": record.get("tentative_rulings"),
                        "probate_examiner_notes": record.get("probate_examiner_notes"),
                    }
                    for record in records
                ],
            },
        },
    )


ORANGE_COURT_PROBE_ENDPOINTS = {
    query_orange_county_court.SOURCE_FAMILY_ID: (
        query_orange_county_court.ONLINE_SERVICES_URL
    ),
    query_orange_county_court.CALENDAR_SOURCE_ID: (
        query_orange_county_court.CALENDAR_URL
    ),
    **{
        source_id: query_orange_county_court.RULING_DIRECTORY_URLS[division]
        for division, source_id in (query_orange_county_court.RULING_SOURCE_IDS.items())
    },
}


def probe_orange_county_court_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify one Orange County court representation and its stable shape."""

    started = time.perf_counter()
    common = {
        "timeout": context.timeout,
        "minimum_interval": _catalog_interval(context.catalog_decision),
        "retry_attempts": context.max_attempts,
        "output": None,
        "json_out": False,
    }
    if context.source_id == query_orange_county_court.SOURCE_FAMILY_ID:
        args = argparse.Namespace(command="probe", **common)
        source = query_orange_county_court._family_source()
        operation = "family_probe"
        record_kind = "source_probe"
        coverage_semantics = [
            *query_orange_county_court.CALENDAR_WARNINGS,
            *query_orange_county_court.RULING_WARNINGS,
        ]
    elif context.source_id == query_orange_county_court.CALENDAR_SOURCE_ID:
        args = argparse.Namespace(
            command="calendar",
            category="civil",
            case_id=None,
            case_year=None,
            title=None,
            location=None,
            department=None,
            date_from=None,
            date_to=None,
            hearing_time=None,
            limit=1,
            cursor=None,
            **common,
        )
        source = query_orange_county_court.CALENDAR_SOURCE
        operation = "one_row_calendar_probe"
        record_kind = "court_hearing"
        coverage_semantics = list(query_orange_county_court.CALENDAR_WARNINGS)
    else:
        division = next(
            (
                division
                for division, source_id in (
                    query_orange_county_court.RULING_SOURCE_IDS.items()
                )
                if source_id == context.source_id
            ),
            None,
        )
        if division is None:
            raise ValueError(
                f"unsupported Orange County court source: {context.source_id}"
            )
        args = argparse.Namespace(
            command="ruling-index",
            division=division,
            department=None,
            **common,
        )
        source = query_orange_county_court._ruling_source(division)
        operation = f"{division}_ruling_directory"
        record_kind = "tentative_ruling_artifact_index"
        coverage_semantics = list(query_orange_county_court.RULING_WARNINGS)

    endpoint = ORANGE_COURT_PROBE_ENDPOINTS[context.source_id]
    result = query_orange_county_court.execute(
        args,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if any(record.get("source_id") != context.source_id for record in records):
        raise ValueError("Orange County component probe returned another source")

    stable_contract = {
        "source": source.to_dict(),
        "endpoint": endpoint,
        "probe_operation": operation,
        "record_kind": record_kind,
        "coverage_semantics": coverage_semantics,
    }
    schema_contract = {
        "record_kind": record_kind,
        "required_common_fields": [
            "canonical_ref",
            "source_id",
            "record_kind",
            "retrieved_at",
        ],
        "observed_schema": inferred_schema(records) if records else None,
    }
    artifact_identity = {
        "source_id": context.source_id,
        "endpoint": endpoint,
        "probe_operation": operation,
    }
    rolling_observation = {
        "result_count": len(records),
        "records": [
            {
                "canonical_ref": record.get("canonical_ref"),
                "department": record.get("department"),
                "artifact_url": record.get("artifact_url"),
                "case_number": (
                    record.get("case", {}).get("case_number")
                    if isinstance(record.get("case"), Mapping)
                    else None
                ),
                "hearing": record.get("hearing"),
                "calendar": record.get("calendar"),
                "tentative_rulings": record.get("tentative_rulings"),
            }
            for record in records
        ],
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(
            {
                key: value
                for key, value in schema_contract.items()
                if key != "observed_schema"
            }
        ),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


RIVERSIDE_COURT_PROBE_ENDPOINTS = {
    query_riverside_court.CALENDAR_SOURCE_ID: (query_riverside_court.CALENDAR_URL),
    query_riverside_court.RULING_SOURCE_ID: (query_riverside_court.RULING_INDEX_URL),
}


def probe_riverside_court_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify one Riverside calendar or ruling-directory representation."""

    started = time.perf_counter()
    network_args = [
        "--timeout",
        str(context.timeout),
        "--minimum-interval",
        str(_catalog_interval(context.catalog_decision)),
        "--retry-attempts",
        str(context.max_attempts),
    ]
    if context.source_id == query_riverside_court.CALENDAR_SOURCE_ID:
        argv = [
            "calendar",
            "--courthouse",
            "Historic Court House",
            "--department",
            "8",
            "--area-of-law",
            "probate",
            "--limit",
            "1",
            *network_args,
        ]
        source = query_riverside_court.CALENDAR_SOURCE
        operation = "department_8_probate_window_sentinel"
        record_kind = "court_calendar_event"
        required_fields = sorted(query_riverside_court.CALENDAR_REQUIRED_KEYS)
        identity_fields = (
            "case_number",
            "hearing.date_time",
            "department",
            "canonical_ref",
        )
        coverage_semantics = list(query_riverside_court.CALENDAR_WARNINGS)
    elif context.source_id == query_riverside_court.RULING_SOURCE_ID:
        argv = ["ruling-index", *network_args]
        source = query_riverside_court.RULING_SOURCE
        operation = "complete_current_department_directory"
        record_kind = "tentative_ruling_artifact_index"
        required_fields = [
            "artifact_url",
            "canonical_ref",
            "department",
            "directory_state",
            "record_kind",
            "retrieved_at",
            "source_id",
        ]
        identity_fields = (
            "artifact_url",
            "department",
            "canonical_ref",
        )
        coverage_semantics = list(query_riverside_court.RULING_WARNINGS)
    else:
        raise ValueError(f"unsupported Riverside court source: {context.source_id}")

    args = query_riverside_court.build_parser().parse_args(argv)
    result = query_riverside_court.execute(args, log_results=False)
    endpoint = RIVERSIDE_COURT_PROBE_ENDPOINTS[context.source_id]
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if any(record.get("source_id") != context.source_id for record in records):
        raise ValueError("Riverside component probe returned another source")

    stable_contract = {
        "source": source.to_dict(),
        "endpoint": endpoint,
        "probe_operation": operation,
        "record_kind": record_kind,
        "required_source_fields": required_fields,
        "record_identity_fields": list(identity_fields),
        "coverage_semantics": coverage_semantics,
    }
    schema_contract = {
        "record_kind": record_kind,
        "required_source_fields": required_fields,
        "record_identity_fields": list(identity_fields),
        "observed_schema": inferred_schema(records) if records else None,
    }
    artifact_identity = {
        "source_id": context.source_id,
        "endpoint": endpoint,
        "probe_operation": operation,
    }
    rolling_observation = {
        "result_count": len(records),
        "query_metadata": dict(result.query.query.metadata),
        "records": [
            {
                "canonical_ref": record.get("canonical_ref"),
                "case_number": record.get("case_number"),
                "department": record.get("department"),
                "hearing": record.get("hearing"),
                "artifact_url": record.get("artifact_url"),
                "artifact_path_month": record.get("artifact_path_month"),
                "artifact_filename_date_candidates": record.get(
                    "artifact_filename_date_candidates"
                ),
            }
            for record in records
        ],
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(
            {
                key: value
                for key, value in schema_contract.items()
                if key != "observed_schema"
            }
        ),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_qld_ecourts(context: ProbeContext) -> ProbeObservation:
    """Verify the exact-file Queensland eCourts detail contract."""

    adapter = query_qld_ecourts
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        output=None,
        json_out=False,
    )
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.DETAIL_URL,
        started=started,
    )
    if not result.records:
        return observation

    record = dict(result.records[0])
    if record.get("record_type") != "court_case" or record.get(
        "evidence_ref"
    ) != adapter.qld_evidence_ref(
        adapter.PROBE_COURT,
        adapter.PROBE_LOCATION,
        adapter.PROBE_FILE_NUMBER,
    ):
        raise ValueError(
            "Queensland eCourts probe returned another file or record type"
        )

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "endpoints": {
            "search": adapter.SEARCH_URL,
            "results": adapter.RESULTS_URL,
            "detail": adapter.DETAIL_URL,
            "official_guide": adapter.OFFICIAL_GUIDE_URL,
        },
        "courts": dict(adapter.COURTS),
        "court_ids": dict(adapter.COURT_IDS),
        "originating_registries": dict(adapter.LOCATIONS),
        "form_fields": dict(adapter.FORM_FIELDS),
        "table_headers": {
            "search_parties": list(adapter.SEARCH_PARTY_HEADERS),
            "detail_parties": list(adapter.DETAIL_PARTY_HEADERS),
            "events": list(adapter.EVENT_HEADERS),
            "documents": list(adapter.DOCUMENT_HEADERS),
        },
        "native_page_size": adapter.NATIVE_PAGE_SIZE,
        "native_result_ceiling": adapter.NATIVE_RESULT_CEILING,
        "ceiling_partition_order": [
            "court",
            "originating_registry",
            "category",
            "party_role",
        ],
        "case_identity_fields": [
            "court_code",
            "originating_location_code",
            "file_number",
        ],
        "document_delivery": "official_copy_request_route",
        "complementary_sources": [
            {
                "source_id": route["source_id"],
                "role": route["role"],
                "url": route["url"],
            }
            for route in adapter.COMPLEMENTARY_OFFICIAL_ROUTES
        ],
    }
    schema_contract = {
        "detail_schema_fingerprint": record.get("schema_fingerprint"),
        "record_schema": inferred_schema([record]),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "probe_file_number": adapter.PROBE_FILE_NUMBER,
        "probe_court": adapter.PROBE_COURT,
        "probe_originating_registry": adapter.PROBE_LOCATION,
        "canonical_ref": record.get("canonical_ref"),
        "evidence_ref": record.get("evidence_ref"),
    }
    rolling_observation = {
        "case_name": record.get("case_name"),
        "date_filed_iso": record.get("date_filed_iso"),
        "current_location_code": record.get("current_location_code"),
        "party_count": len(record.get("parties") or []),
        "event_count": len(record.get("events") or []),
        "document_count": len(record.get("documents") or []),
        "related_file_count": len(record.get("related_files") or []),
        "status_notices": list(record.get("status_notices") or []),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_dc_appellate_cases(context: ProbeContext) -> ProbeObservation:
    """Probe C-Track case, docket-document resolver, and a filing PDF."""

    adapter = query_dc_appellate_cases
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.CASE_SEARCH_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    probe = dict(record["probe"]) if isinstance(record.get("probe"), Mapping) else {}
    if (
        record.get("record_kind") != "case"
        or record.get("appellate_case_number") != adapter.PROBE_CASE_NUMBER
        or record.get("source_internal_id") != adapter.PROBE_CASE_INTERNAL_ID
        or not isinstance(probe.get("resolved_document"), Mapping)
    ):
        raise ValueError("D.C. C-Track probe sentinel contract changed")

    manifest = adapter.source_manifest()
    resolved_document = dict(probe["resolved_document"])
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "operations": manifest["operations"],
        "native_page_size": adapter.NATIVE_PAGE_SIZE,
        "case_identity_fields": [
            "appellate_case_number",
            "source_internal_id",
        ],
        "originating_pivot_field": "originating_case_number",
        "child_identity_fields": {
            "party": "native_party_id",
            "docket_event": "native_event_id",
            "document": "native_document_id",
        },
        "complementary_sources": [
            {
                "source_id": route.get("source_id"),
                "relationship": route.get("relationship"),
                "join_keys": route.get("join_keys"),
                "operation_state": route.get("operation_state"),
            }
            for route in manifest["related_source_routes"]
        ],
    }
    schema_contract = {
        "case_required_fields": [
            "appellate_case_number",
            "source_internal_id",
            "caption",
            "classification",
            "parties",
            "docket_events",
        ],
        "resolved_document_required_fields": [
            "native_document_id",
            "source_event_id",
            "download_url",
            "mime_type",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel_case_number": adapter.PROBE_CASE_NUMBER,
        "sentinel_case_internal_id": adapter.PROBE_CASE_INTERNAL_ID,
        "sentinel_originating_case_number": (adapter.PROBE_ORIGINATING_CASE_NUMBER),
        "resolved_document_id": resolved_document.get("native_document_id"),
        "resolved_document_url": resolved_document.get("source_url"),
    }
    rolling_observation = {
        "party_count": len(record.get("parties") or []),
        "docket_event_count": len(record.get("docket_events") or []),
        "linked_document_count": len(record.get("documents") or []),
        "document_sha256": probe.get("document_sha256"),
        "document_size_bytes": probe.get("document_size_bytes"),
        "document_media_type": probe.get("document_media_type"),
        "component_access_outcomes": probe.get("component_access_outcomes"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_maryland_public_cases(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the rolling report directory, latest PDF, and coordinate parser."""

    adapter = query_md_public_cases
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    latest = (
        dict(record["latest_report"])
        if isinstance(record.get("latest_report"), Mapping)
        else {}
    )
    parsed = (
        dict(latest["parsed_report"])
        if isinstance(latest.get("parsed_report"), Mapping)
        else {}
    )
    if (
        record.get("record_kind") != "source_probe"
        or set(record.get("operation_states") or {})
        != {
            "landing_page",
            "report_directory",
            "pdf_download",
            "coordinate_text_parse",
        }
        or not parsed.get("case_count")
    ):
        raise ValueError("Maryland MDEC public-cases probe contract changed")

    manifest = adapter._source_manifest()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "operations": manifest["operations"],
        "coverage": manifest["coverage"],
        "directory_url": adapter.VERIFIED_DIRECTORY_URL,
        "filename_pattern": adapter.REPORT_FILENAME_RE.pattern,
        "report_name": "CBS721 - Cases Filed Report",
        "record_identity_fields": ["court_name", "case_number"],
        "party_join_fields": ["published_name", "published_address"],
        "complementary_sources": [
            {
                "source_id": route.get("source_id"),
                "role": route.get("role"),
                "join_keys": route.get("join_keys"),
                "operation_state": route.get("operation_state"),
            }
            for route in manifest["related_source_routes"]
        ],
    }
    schema_contract = {
        "case_record_fields": [
            "court_id",
            "court_name",
            "case_number",
            "case_caption",
            "case_type",
            "filing_date",
            "parties",
            "charges",
        ],
        "report_metadata_fields": sorted(parsed),
        "operation_states": sorted(record["operation_states"]),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "directory_url": adapter.VERIFIED_DIRECTORY_URL,
        "report_filename_pattern": adapter.REPORT_FILENAME_RE.pattern,
        "report_name": "CBS721 - Cases Filed Report",
    }
    rolling_observation = {
        "available_report_dates": list(record.get("available_report_dates") or []),
        "latest_report_date": latest.get("report_date"),
        "latest_report_sha256": latest.get("sha256"),
        "latest_report_size_bytes": latest.get("size_bytes"),
        "latest_case_count": parsed.get("case_count"),
        "latest_page_count": parsed.get("page_count"),
        "latest_courts": parsed.get("courts"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=int(parsed["case_count"]),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_maryland_estates(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe statewide estate search, exact detail, docket, and refresh state."""

    adapter = query_md_estate_search
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.SEARCH_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    operation_states = dict(record.get("operation_states") or {})
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or set(operation_states)
        != {
            "agreement_navigation",
            "search_form",
            "estate_number_search",
            "dynamic_native_pagination",
            "estate_detail",
            "docket_history",
        }
        or record.get("sentinel_estate_number") != adapter.PROBE_ESTATE_NUMBER
        or record.get("sentinel_county") != adapter.PROBE_COUNTY
        or record.get("sentinel_docket_event_count", 0) < 1
    ):
        raise ValueError("Maryland estate-search probe contract changed")

    primary = adapter.source_records()[0]
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "coverage": primary["coverage"],
        "bounds": primary["bounds"],
        "identity": primary["identity"],
        "expected_result_headers": list(adapter.EXPECTED_RESULT_HEADERS),
        "expected_docket_headers": list(adapter.EXPECTED_DOCKET_HEADERS),
        "form_field_ids": dict(adapter.FORM_IDS),
        "estate_type_codes": dict(adapter.ESTATE_TYPES),
        "status_codes": dict(adapter.STATUS_CODES),
        "complementary_sources": [
            {
                "source_id": route.get("source_id"),
                "record_role": route.get("record_role"),
                "join_keys": route.get("join_keys"),
            }
            for route in adapter.RELATED_ROUTES
            if route.get("source_id") != adapter.SOURCE_ID
        ],
    }
    schema_contract = {
        "result_schema_fingerprint": record.get("result_schema_fingerprint"),
        "detail_schema_fingerprint": record.get("detail_schema_fingerprint"),
        "operation_state_keys": sorted(operation_states),
        "result_record_kinds": [
            "estate_case_index",
            "estate_case_detail",
            "estate_docket_event",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel_record_id": record.get("sentinel_record_id"),
        "sentinel_estate_number": adapter.PROBE_ESTATE_NUMBER,
        "sentinel_county": adapter.PROBE_COUNTY,
        "detail_url": (
            f"{adapter.DETAIL_URL}?src=row&RecordId={record.get('sentinel_record_id')}"
        ),
    }
    rolling_observation = {
        "source_latest_data_raw": record.get("source_latest_data_raw"),
        "source_latest_data_at": record.get("source_latest_data_at"),
        "application_instance": record.get("application_instance"),
        "search_result_count": record.get("search_result_count"),
        "sentinel_docket_event_count": record.get("sentinel_docket_event_count"),
        "operation_states": operation_states,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_maryland_estate_notices(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe full notice text, native identity, filters, and dynamic paging."""

    adapter = query_md_estate_notices_claims
    args = adapter.build_parser().parse_args(
        [
            "probe-notices",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.NOTICE_SEARCH_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    operation_states = dict(record.get("operation_states") or {})
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.NOTICE_SOURCE_ID
        or set(operation_states)
        != {
            "default_rolling_search",
            "full_notice_text",
            "native_notice_identity",
            "dynamic_native_pagination",
            "county_publication_death_party_filters",
        }
        or not str(record.get("sample_notice_id") or "").isdigit()
    ):
        raise ValueError("Maryland estate-notice probe contract changed")

    manifest = adapter.source_records()[0]
    stable_contract = {
        "source": adapter.NOTICE_SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "coverage": manifest["coverage"],
        "bounds": manifest["bounds"],
        "identity": manifest["identity"],
        "form_field_ids": dict(adapter.NOTICE_EXPECTED_FORM_IDS),
        "native_page_size": adapter.NATIVE_PAGE_SIZE,
        "complementary_sources": manifest["complementary_source_ids"],
    }
    schema_contract = {
        "result_schema_fingerprint": record.get(
            "result_schema_fingerprint"
        ),
        "operation_state_keys": sorted(operation_states),
        "record_kind": "estate_legal_notice",
        "full_body_representations": ["full_notice_text", "full_notice_html"],
    }
    artifact_identity = {
        "source_id": adapter.NOTICE_SOURCE_ID,
        "search_url": adapter.NOTICE_SEARCH_URL,
        "native_identity": ["notice_id"],
    }
    rolling_observation = {
        "search_result_count": record.get("search_result_count"),
        "current_page_count": record.get("current_page_count"),
        "sample_notice_id": record.get("sample_notice_id"),
        "sample_notice_title": record.get("sample_notice_title"),
        "observed_notice_titles": record.get("observed_notice_titles"),
        "effective_parameters": record.get("effective_parameters"),
        "source_result_marker": record.get("source_result_marker"),
        "operation_states": operation_states,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_maryland_estate_claims(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe claim roles, exact detail, dynamic paging, and freshness."""

    adapter = query_md_estate_notices_claims
    args = adapter.build_parser().parse_args(
        [
            "probe-claims",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.CLAIM_SEARCH_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    operation_states = dict(record.get("operation_states") or {})
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.CLAIM_SOURCE_ID
        or set(operation_states)
        != {
            "claimant_and_decedent_roles",
            "person_and_corporation_fields",
            "claim_detail",
            "dynamic_native_pagination",
            "linked_and_migrated_filters",
        }
        or not str(record.get("sample_record_id") or "").isdigit()
        or not record.get("source_latest_data_at")
    ):
        raise ValueError("Maryland estate-claim probe contract changed")

    manifest = adapter.source_records()[1]
    stable_contract = {
        "source": adapter.CLAIM_SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "coverage": manifest["coverage"],
        "bounds": manifest["bounds"],
        "identity": manifest["identity"],
        "result_headers": list(adapter.CLAIM_RESULT_HEADERS),
        "form_field_ids": dict(adapter.CLAIM_EXPECTED_FORM_IDS),
        "native_page_size": adapter.NATIVE_PAGE_SIZE,
        "complementary_sources": manifest["complementary_source_ids"],
    }
    schema_contract = {
        "result_schema_fingerprint": record.get(
            "result_schema_fingerprint"
        ),
        "detail_schema_fingerprint": record.get(
            "detail_schema_fingerprint"
        ),
        "operation_state_keys": sorted(operation_states),
        "record_kind": "estate_claim_index_entry",
    }
    artifact_identity = {
        "source_id": adapter.CLAIM_SOURCE_ID,
        "search_url": adapter.CLAIM_SEARCH_URL,
        "detail_url": adapter.CLAIM_DETAIL_URL,
        "native_identity": ["source_partition", "RecordId"],
    }
    rolling_observation = {
        "search_result_count": record.get("search_result_count"),
        "sample_record_id": record.get("sample_record_id"),
        "sample_source_partition": record.get("sample_source_partition"),
        "sample_claim_type": record.get("sample_claim_type"),
        "sample_claim_status": record.get("sample_claim_status"),
        "source_latest_data_raw": record.get("source_latest_data_raw"),
        "source_latest_data_at": record.get("source_latest_data_at"),
        "application_instance": record.get("application_instance"),
        "source_result_marker": record.get("source_result_marker"),
        "operation_states": operation_states,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_maryland_judgment_liens(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe both JSF search modes, native paging, and a detail case."""

    adapter = query_md_judgment_liens
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.SEARCH_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("detail_sentinel_event_count", 0) < 1
    ):
        raise ValueError("Maryland judgment/liens probe contract changed")

    primary = next(
        value
        for value in adapter.source_records()
        if value.get("source_id") == adapter.SOURCE_ID
    )
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "coverage": primary["coverage"],
        "bounds": primary["bounds"],
        "identity": primary["identity"],
        "expected_result_headers": list(adapter.EXPECTED_RESULT_HEADERS),
        "form_modes": ["person", "company"],
        "complementary_sources": [
            {
                "source_id": route.get("source_id"),
                "record_role": route.get("record_role"),
                "join_keys": route.get("join_keys"),
                "access_observation": route.get("access_observation"),
            }
            for route in adapter.related_source_routes()
        ],
    }
    schema_contract = {
        "person_form_schema_fingerprint": record.get("person_form_schema_fingerprint"),
        "company_form_schema_fingerprint": record.get(
            "company_form_schema_fingerprint"
        ),
        "operation_state_keys": sorted(record.get("operation_states") or {}),
        "result_record_kinds": [
            "judgment_lien_index_event",
            "judgment_lien_detail_event",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "detail_sentinel_case_number": adapter.PROBE_CASE_NUMBER,
        "detail_url": (
            f"{adapter.DETAIL_URL}?selectedCaseId={adapter.PROBE_CASE_NUMBER}"
        ),
    }
    rolling_observation = {
        "search_sentinel_total": record.get("search_sentinel_total"),
        "search_sentinel_pages": record.get("search_sentinel_pages"),
        "detail_sentinel_event_count": record.get("detail_sentinel_event_count"),
        "operation_states": record.get("operation_states"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=int(record["detail_sentinel_event_count"]),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_michigan_appellate(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe all three appellate result APIs, page options, and one PDF."""

    adapter = query_michigan_appellate
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--query",
            adapter.PROBE_QUERY,
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.SEARCH_PAGE_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    checks = dict(record["checks"]) if isinstance(record.get("checks"), Mapping) else {}
    result_checks = {
        result_type: checks.get(result_type) for result_type in adapter.SEARCH_ENDPOINTS
    }
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or list(checks.get("page_size_options") or ()) != [10, 25, 50, 100]
        or any(not isinstance(value, Mapping) for value in result_checks.values())
        or not isinstance(checks.get("document"), Mapping)
    ):
        raise ValueError("Michigan appellate probe contract changed")

    document = dict(checks["document"])
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "endpoints": {
            "page_model": adapter.PAGE_MODEL_URL,
            **dict(adapter.SEARCH_ENDPOINTS),
            "overview": adapter.OVERVIEW_URL,
        },
        "result_categories": dict(adapter.RESULT_KINDS),
        "courts": {
            code: {
                key: value
                for key, value in court.items()
                if key
                in {
                    "court_id",
                    "native_court_id",
                    "name",
                    "court_level",
                }
            }
            for code, court in adapter.COURTS.items()
        },
        "page_size_options": checks["page_size_options"],
        "advanced_parameters": dict(adapter.ADVANCED_PARAMETERS),
        "facet_parameters": dict(adapter.FACET_PARAMETERS),
        "case_identity_precedence": [
            "case_url_route",
            "source_case_flags",
            "case_number_fields",
            "title_case_number",
        ],
        "join_keys": list(adapter.SOURCE_METADATA.metadata["stable_join_keys"]),
        "complementary_sources": [
            {
                "route_id": route["route_id"],
                "role": route["role"],
                "access_method": route["access_method"],
                "join_keys": route["join_keys"],
            }
            for route in adapter.related_source_routes()
            if route["route_id"] != "michigan_appellate_portal"
        ],
    }
    schema_contract = {
        "result_schema_fingerprints": {
            result_type: dict(value).get("schema_fingerprint")
            for result_type, value in result_checks.items()
            if isinstance(value, Mapping)
        },
        "normalized_record_kinds": list(adapter.RESULT_KINDS.values()),
        "normalized_identity_fields": [
            "court",
            "raw_case_number",
            "case_number_resolved",
            "canonical_ref",
        ],
        "document_fields": [
            "native_document_id",
            "document_type",
            "source_url",
            "mime_type",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel_document_url": adapter.PROBE_DOCUMENT_URL,
        "media_type": document.get("media_type"),
    }
    rolling_observation = {
        "query": adapter.PROBE_QUERY,
        "category_totals": {
            result_type: {
                "result_count": dict(value).get("result_count"),
                "total_results": dict(value).get("total_results"),
                "total_pages": dict(value).get("total_pages"),
            }
            for result_type, value in result_checks.items()
            if isinstance(value, Mapping)
        },
        "appellate_court_options": checks.get("appellate_court_options"),
        "lower_court_option_count": checks.get("lower_court_option_count"),
        "document_sha256": document.get("sha256"),
        "document_size_bytes": document.get("content_length"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_michigan_business_court(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one native page, a true zero, both facets, and one PDF."""

    adapter = query_michigan_business_court
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError(
            "Michigan Business Court monitor received an unknown source"
        )
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.SEARCH_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "Michigan Business Court probe expected one contract record"
        )

    record = dict(result.records[0])
    search_value = record.get("search_contract")
    zero_value = record.get("zero_result_contract")
    document_value = record.get("document_contract")
    if (
        record.get("record_kind") != "business_court_source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or not isinstance(search_value, Mapping)
        or not isinstance(zero_value, Mapping)
        or not isinstance(document_value, Mapping)
    ):
        raise ValueError("Michigan Business Court probe contract changed")
    search_contract = dict(search_value)
    zero_contract = dict(zero_value)
    document_contract = dict(document_value)

    search_counts = {
        field: search_contract.get(field)
        for field in (
            "native_page_size",
            "result_count",
            "total_pages",
            "total_results",
        )
    }
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in search_counts.values()
    ):
        raise ValueError("Michigan Business Court native counts changed")
    if (
        search_counts["native_page_size"] != adapter.NATIVE_PAGE_SIZE
        or search_counts["result_count"] < 1
        or search_counts["result_count"] > adapter.NATIVE_PAGE_SIZE
        or search_counts["total_pages"] < 1
        or search_counts["total_results"] < search_counts["result_count"]
        or search_contract.get("continuation_basis")
        != "currentPage_less_than_totalPages"
        or list(search_contract.get("sort_by_options") or ())
        != list(adapter.SORT_ORDERS)
    ):
        raise ValueError(
            "Michigan Business Court pagination contract changed"
        )
    facets = search_contract.get("facets")
    facet_keys = {
        facet.get("query_string_key")
        for facet in facets
        if isinstance(facet, Mapping)
    } if isinstance(facets, Sequence) and not isinstance(
        facets,
        (str, bytes, bytearray),
    ) else set()
    if not {
        adapter.BUSINESS_CATEGORY_QUERY_KEY,
        adapter.COURT_QUERY_KEY,
    } <= facet_keys:
        raise ValueError("Michigan Business Court facets changed")

    for count_field in ("result_count", "total_results", "total_pages"):
        value = zero_contract.get(count_field)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            raise ValueError(
                "Michigan Business Court zero-result contract changed"
            )
    document_size = document_contract.get("content_length")
    document_sha256 = document_contract.get("sha256")
    if (
        document_contract.get("media_type") != "application/pdf"
        or isinstance(document_size, bool)
        or not isinstance(document_size, int)
        or document_size < 1
        or not isinstance(document_sha256, str)
        or len(document_sha256) != 64
        or not str(document_contract.get("signature_hex") or "").startswith(
            "25504446"
        )
    ):
        raise ValueError("Michigan Business Court PDF contract changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "search_endpoint": adapter.SEARCH_URL,
        "native_page_size": adapter.NATIVE_PAGE_SIZE,
        "pagination": {
            "page_origin": 1,
            "continuation_basis": "currentPage_less_than_totalPages",
            "omitted_limit": "traverse_totalPages",
            "cursor_binding": "source_query_selection_fingerprint",
        },
        "sort_orders": list(adapter.SORT_ORDERS),
        "facet_query_keys": [
            adapter.BUSINESS_CATEGORY_QUERY_KEY,
            adapter.COURT_QUERY_KEY,
        ],
        "identity": {
            "document": [
                "official_pdf_url_with_query",
                "filename",
            ],
            "search_occurrence": [
                "selection_fingerprint",
                "native_page",
                "native_row",
                "document_url",
            ],
            "case_number": "source_label_candidates_without_canonical_resolution",
            "court_locators_are_assignments": False,
        },
        "optional_legacy_fields": sorted(adapter.OPTIONAL_ITEM_FIELDS),
        "document_contract": {
            "media_type": "application/pdf",
            "signature": "%PDF-",
        },
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "probe_record_kind": "business_court_source_probe",
        "search_contract_fields": [
            "native_page_size",
            "result_count",
            "total_pages",
            "total_results",
            "source_has_more_results",
            "continuation_basis",
            "sort_by_options",
            "facets",
            "schema_fingerprint",
        ],
        "zero_result_fields": [
            "query",
            "result_count",
            "total_results",
            "total_pages",
            "schema_fingerprint",
        ],
        "document_fields": [
            "source_url",
            "filename",
            "media_type",
            "content_length",
            "sha256",
            "signature_hex",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "landing_url": adapter.LANDING_URL,
        "search_endpoint": adapter.SEARCH_URL,
        "document_host": "www.courts.michigan.gov",
        "document_media_type": "application/pdf",
    }
    rolling_observation = {
        "native_page_size": search_counts["native_page_size"],
        "result_count": search_counts["result_count"],
        "total_pages": search_counts["total_pages"],
        "total_results": search_counts["total_results"],
        "source_has_more_results": search_contract.get(
            "source_has_more_results"
        ),
        "facets": facets,
        "search_schema_fingerprint": search_contract.get(
            "schema_fingerprint"
        ),
        "zero_schema_fingerprint": zero_contract.get(
            "schema_fingerprint"
        ),
        "document_url": document_contract.get("source_url"),
        "document_filename": document_contract.get("filename"),
        "document_size_bytes": document_size,
        "document_sha256": document_sha256,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "requests_made": 3,
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_maryland_opinions(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe both Maryland publication indexes and one official PDF."""

    adapter = query_md_opinions
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.REPORTED_INDEX_URL,
        started=started,
    )
    if not result.records:
        return observation

    record = dict(result.records[0])
    reported_schema = record.get("reported_schema_fingerprint")
    unreported_schema = record.get("unreported_schema_fingerprint")
    pdf_url = record.get("pdf_url")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or not isinstance(record.get("reported_year_count"), int)
        or int(record["reported_year_count"]) < 1
        or not isinstance(record.get("unreported_month_count"), int)
        or int(record["unreported_month_count"]) < 1
        or not isinstance(reported_schema, str)
        or len(reported_schema) != 64
        or not isinstance(unreported_schema, str)
        or len(unreported_schema) != 64
        or not isinstance(pdf_url, str)
        or record.get("pdf_media_type") != "application/pdf"
        or not isinstance(record.get("pdf_size_bytes"), int)
        or int(record["pdf_size_bytes"]) < 5
    ):
        raise ValueError("Maryland appellate-opinion probe contract changed")
    adapter._official_pdf_url(pdf_url)

    manifest = adapter._source_manifest()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "endpoints": {
            "reported_landing": adapter.REPORTED_INDEX_URL,
            "reported_results": adapter.REPORTED_RESULTS_URL,
            "unreported_directory": adapter.UNREPORTED_INDEX_URL,
            "unreported_month_prefix": adapter.UNREPORTED_MONTH_PREFIX,
        },
        "coverage": manifest["coverage"],
        "identity": manifest["identity"],
        "courts": {
            court_key: {
                key: value
                for key, value in court.items()
                if key
                in {
                    "court_id",
                    "current_name",
                    "former_name",
                    "native",
                }
            }
            for court_key, court in adapter.COURTS.items()
        },
        "reported_native_orders": dict(adapter.REPORTED_ORDERS),
        "reported_expected_headers": list(adapter.REPORTED_HEADERS),
        "unreported_expected_headers": list(adapter.UNREPORTED_HEADERS),
        "related_source_routes": manifest["related_source_routes"],
    }
    schema_contract = {
        "reported_schema_fingerprint": reported_schema,
        "unreported_schema_fingerprint": unreported_schema,
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "record_kind": "appellate_disposition",
        "publication_states": ["reported", "unreported"],
        "reported_completeness_marker": "sequential_source_line_number",
        "unreported_completeness_marker": "complete_month_table",
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "reported_document_identity": "court/year/pdf_filename",
        "unreported_document_identity": (
            "source_pdf_filename_or_metadata_court_case_filing_date"
        ),
        "official_pdf_hosts": ["mdcourts.gov", "www.mdcourts.gov"],
    }
    rolling_observation = {
        "reported_year_count": record["reported_year_count"],
        "reported_sample_count": record.get("reported_sample_count"),
        "unreported_month_count": record["unreported_month_count"],
        "unreported_sample_month": record.get("unreported_sample_month"),
        "unreported_sample_count": record.get("unreported_sample_count"),
        "pdf_url": pdf_url,
        "pdf_sha256": record.get("pdf_sha256"),
        "pdf_size_bytes": record["pdf_size_bytes"],
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_maryland_business_opinions(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Maryland's selective trial-publication archive and one PDF."""

    adapter = query_md_business_opinions
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.CURRENT_URL,
        started=started,
    )
    if not result.records:
        return observation

    record = dict(result.records[0])
    archive_years = record.get("archive_years")
    current_schema = record.get("current_schema_fingerprint")
    archive_schema = record.get("archive_schema_fingerprint")
    pdf_url = record.get("pdf_url")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or not isinstance(archive_years, (list, tuple))
        or list(archive_years) != [2008, 2007, 2006, 2005, 2004, 2003]
        or not isinstance(record.get("current_publication_count"), int)
        or int(record["current_publication_count"]) < 1
        or record.get("archive_sample_year") != 2003
        or not isinstance(record.get("archive_sample_count"), int)
        or int(record["archive_sample_count"]) < 1
        or not isinstance(current_schema, str)
        or len(current_schema) != 64
        or not isinstance(archive_schema, str)
        or len(archive_schema) != 64
        or not isinstance(pdf_url, str)
        or record.get("pdf_media_type") != "application/pdf"
        or not isinstance(record.get("pdf_size_bytes"), int)
        or int(record["pdf_size_bytes"]) < 5
    ):
        raise ValueError(
            "Maryland Business and Technology opinion probe contract changed"
        )
    adapter._official_attachment_url(pdf_url)

    manifest = adapter._source_manifest()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "endpoints": {
            "current_index": adapter.CURRENT_URL,
            "archive_directory": adapter.ARCHIVE_INDEX_URL,
            "annual_archive_pattern": (f"{adapter.ARCHIVE_INDEX_URL}<YYYY>"),
        },
        "coverage": manifest["coverage"],
        "identity": manifest["identity"],
        "archive_years": list(archive_years),
        "expected_headers": list(adapter.EXPECTED_HEADERS),
        "document_types": list(adapter._DOCUMENT_TYPES),
        "related_source_routes": manifest["related_source_routes"],
    }
    schema_contract = {
        "current_schema_fingerprint": current_schema,
        "archive_schema_fingerprint": archive_schema,
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "record_kind": "published_trial_court_opinion",
        "publication_identity_field": "publication_designation",
        "case_identity_field": "case_number_when_source_supplied",
        "date_precision_field": "date_precision",
        "source_state_fields": [
            "source_omissions",
            "source_link_anomalies",
            "publication_designation_at_source",
        ],
        "document_identity_field": "exact_source_url",
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "document_identity": "exact_source_listed_attachment_url",
        "official_document_hosts": ["mdcourts.gov", "www.mdcourts.gov"],
        "verified_formats": ["pdf", "doc", "wpd"],
    }
    rolling_observation = {
        "current_publication_count": record["current_publication_count"],
        "archive_sample_count": record["archive_sample_count"],
        "current_rows_with_source_omissions": record.get(
            "current_rows_with_source_omissions"
        ),
        "current_rows_with_source_link_anomalies": record.get(
            "current_rows_with_source_link_anomalies"
        ),
        "pdf_url": pdf_url,
        "pdf_sha256": record.get("pdf_sha256"),
        "pdf_size_bytes": record["pdf_size_bytes"],
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_new_jersey_dca_property(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify DCA building identity while keeping mutable property data rolling."""

    adapter = query_new_jersey_dca_property
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.ODATA_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "New Jersey DCA probe expected one exact building registration"
        )

    record = dict(result.records[0])
    coordinates_value = record.get("parcel_coordinates")
    match_context_value = record.get("source_match_context")
    raw_source_value = record.get("raw_source")
    coordinates = (
        dict(coordinates_value) if isinstance(coordinates_value, Mapping) else {}
    )
    match_context = (
        dict(match_context_value) if isinstance(match_context_value, Mapping) else {}
    )
    raw_source = dict(raw_source_value) if isinstance(raw_source_value, Mapping) else {}
    response_field_fingerprint = record.get("response_field_fingerprint")
    if (
        record.get("record_type") != "property_registration_building"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("building_registration_number")
        != adapter.PROBE_BUILDING_REGISTRATION
        or record.get("property_registration_number")
        != adapter.PROBE_PROPERTY_REGISTRATION
        or record.get("adapter_schema_fingerprint")
        != adapter.ADAPTER_SCHEMA_FINGERPRINT
        or not isinstance(response_field_fingerprint, str)
        or len(response_field_fingerprint) != 64
        or not adapter.REQUIRED_ODATA_FIELDS.issubset(raw_source)
    ):
        raise ValueError("New Jersey DCA building probe contract changed")

    alternative_routes = adapter.alternative_route_records()
    routes_by_id = {
        str(route.get("source_id")): dict(route)
        for route in alternative_routes
        if isinstance(route, Mapping)
    }
    expected_routes = {
        "us-nj-dca-bhi-active-buildings-opra",
        "us-nj-njgin-parcels-modiv",
        "us-nj-treasury-sr1a-sales",
        "us-nj-county-clerks-registers",
        "us-nj-local-assessors-tax-boards",
        "us-nj-opra-property-records",
    }
    if set(routes_by_id) != expected_routes or any(
        not route.get("gap_relative_to_dca") or not route.get("join_fields")
        for route in routes_by_id.values()
    ):
        raise ValueError("New Jersey DCA alternative-route contract changed")

    manifest = adapter.source_manifest_record()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "endpoints": {
            "search_page": adapter.SEARCH_PAGE_URL,
            "odata_buildings": adapter.ODATA_URL,
            "property_detail_template": adapter.DETAIL_URL_TEMPLATE,
        },
        "record_identity": manifest["record_identity"],
        "operation_access": manifest["operation_access"],
        "pagination": manifest["pagination"],
        "source_semantics": manifest["source_semantics"],
        "alternative_routes": [
            {
                "source_id": source_id,
                "url": route.get("url"),
                "official_landing_url": route.get("official_landing_url"),
                "join_fields": route.get("join_fields"),
                "adds": route.get("adds"),
                "coverage": route.get("coverage"),
                "gap_relative_to_dca": route.get("gap_relative_to_dca"),
            }
            for source_id, route in sorted(routes_by_id.items())
        ],
    }
    schema_contract = {
        "record_type": "property_registration_building",
        "adapter_schema_fingerprint": adapter.ADAPTER_SCHEMA_FINGERPRINT,
        "required_source_fields": sorted(adapter.REQUIRED_ODATA_FIELDS),
        "identity_fields": [
            "building_registration_number",
            "property_registration_number",
        ],
        "locator_fields": ["building_id", "property_interest_id"],
        "registered_owner_semantics": (
            "DCA regulatory-registration relationship, not deed title"
        ),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel_building_registration": adapter.PROBE_BUILDING_REGISTRATION,
        "sentinel_property_registration": adapter.PROBE_PROPERTY_REGISTRATION,
        "identity_grain": "13_digit_building_registration",
    }
    rolling_observation = {
        "canonical_ref": record.get("canonical_ref"),
        "building_id": record.get("building_id"),
        "property_interest_id": record.get("property_interest_id"),
        "building_address": record.get("building_address"),
        "parcel_coordinates": coordinates,
        "building_registration_status": record.get("building_registration_status"),
        "property_registration_status": record.get("property_registration_status"),
        "registered_owner_publication_state": record.get(
            "registered_owner_publication_state"
        ),
        "source_match_context": match_context,
        "response_field_fingerprint": response_field_fingerprint,
    }
    return replace(
        observation,
        schema_sha256=response_field_fingerprint,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def probe_virginia_general_district(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the court-component contract without hashing session/build churn."""

    adapter = query_va_general_district
    sentinel_code = "013"
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--court",
            sentinel_code,
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Virginia GDC probe expected one source-contract record")

    record = dict(result.records[0])
    selected_value = record.get("selected_court")
    selected = dict(selected_value) if isinstance(selected_value, Mapping) else {}
    route_labels_value = record.get("selected_court_route_labels")
    route_hrefs_value = record.get("selected_court_route_hrefs")
    hearing_types_value = record.get("source_native_hearing_types")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("status") != "ok"
        or record.get("verification_required") is not False
        or record.get("civil_case_form_present") is not True
        or record.get("traffic_criminal_case_form_present") is not True
        or not isinstance(record.get("court_component_count"), int)
        or int(record["court_component_count"]) < 1
        or selected.get("court_source_code") != sentinel_code
        or selected.get("court_id") != f"va-gdc-{sentinel_code}"
        or selected.get("court_source_code_semantics")
        != "source-published application court-component identifier"
        or not isinstance(route_labels_value, (list, tuple))
        or not isinstance(route_hrefs_value, (list, tuple))
        or len(route_labels_value) != len(route_hrefs_value)
        or not isinstance(hearing_types_value, (list, tuple))
    ):
        raise ValueError("Virginia GDC source probe contract changed")

    expected_route_labels = {
        f"{division} {role}"
        for division in ("Civil", "Traffic/Criminal")
        for role in (
            "Name Search",
            "Case Number Search",
            "Hearing Date Search",
            "Service/Process Search",
        )
    }
    route_labels = [str(value) for value in route_labels_value]
    route_hrefs = [str(value) for value in route_hrefs_value]
    if set(route_labels) != expected_route_labels:
        raise ValueError("Virginia GDC selected-court route set changed")
    route_contract = [
        {
            "label": label,
            "relative_endpoint": href.split("?", 1)[0],
            "division_code": ("T" if label.startswith("Traffic/Criminal ") else "V"),
        }
        for label, href in sorted(
            zip(route_labels, route_hrefs, strict=True),
            key=lambda item: item[0],
        )
    ]
    for route in route_contract:
        division_marker = f"searchDivision={route['division_code']}"
        href = route_hrefs[route_labels.index(str(route["label"]))]
        if division_marker not in href:
            raise ValueError(
                "Virginia GDC route no longer retains its division selector"
            )

    hearing_types = [
        {
            "code": str(value.get("code") or ""),
            "source_label": str(value.get("source_label") or ""),
        }
        for value in hearing_types_value
        if isinstance(value, Mapping)
    ]
    expected_hearing_codes = {code for code, _label in adapter.HEARING_TYPES if code}
    if (
        len(hearing_types) != len(hearing_types_value)
        or {value["code"] for value in hearing_types} != expected_hearing_codes
    ):
        raise ValueError("Virginia GDC hearing-type option contract changed")

    route_manifest = adapter._route_record()
    alternative_routes = [
        {
            "source_id": route["source_id"],
            "name": route["name"],
            "url": route["url"],
            "additional_url": route.get("additional_url"),
            "adds": route["adds"],
            "does_not_replace": route["does_not_replace"],
            "equivalent": route["equivalent"],
        }
        for route in adapter.COMPLEMENTARY_SOURCES
    ]
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "endpoints": {
            "landing": adapter.LANDING_URL,
            "name_search": adapter.NAME_SEARCH_URL,
            "hearing_and_service_search": adapter.CASE_SEARCH_URL,
            "exact_case_number_search": adapter.CASE_NUMBER_SEARCH_URL,
            "help": adapter.HELP_URL,
        },
        "court_components": {
            "source_published_count": record["court_component_count"],
            "identity_fields": ["court_source_code", "court_id"],
            "source_code_semantics": (
                "application court-component identifier, not geographic FIPS"
            ),
            "sentinel": {
                "court_source_code": sentinel_code,
                "court_id": f"va-gdc-{sentinel_code}",
                "court_name": selected.get("court_name"),
            },
        },
        "division_roles": route_manifest["source_native_divisions"],
        "selected_court_routes": route_contract,
        "source_native_hearing_types": hearing_types,
        "pagination": {
            "native_page_size": adapter.NATIVE_PAGE_SIZE,
            "reported_total": None,
            "exhaustion_signal": "Next control absent on final native page",
            "continuation": (
                "criteria-bound replay cursor with page schema and boundary anchor"
            ),
        },
        "alternative_routes": alternative_routes,
    }
    schema_contract = {
        "operations": [
            "courts",
            "name",
            "case",
            "hearing",
            "service",
            "probe",
            "routes",
        ],
        "case_identity_fields": ["source_id", "court_id", "raw_case_number"],
        "record_kinds": [
            "court_component",
            "case_search_hit",
            "case",
            "source_probe",
            "source_route_manifest",
        ],
        "division_codes": {"V": "civil", "T": "traffic_criminal"},
        "query_roles": [
            "name",
            "exact_case_number",
            "hearing_date",
            "service_process_name",
        ],
        "section_publication_states": [
            "published",
            "published_empty",
            "not_present",
        ],
        "date_of_birth_publication_states": [
            "year_redacted",
            "published",
            "not_published",
        ],
        "document_access": {
            "filing_index_present": False,
            "filing_images_present": False,
            "official_copy_route": "individual_court_clerk",
        },
    }
    rolling_observation = {
        "application_build": record.get("application_build"),
        "request_count": record.get("request_count"),
        "terms_state": record.get("terms_state"),
        "source_url": record.get("source_url"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=int(record["court_component_count"]),
        details={
            **dict(observation.details),
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": {
                "source_id": adapter.SOURCE_ID,
                "court_identity": (
                    "source-published court component plus raw case number"
                ),
                "sentinel_court_id": f"va-gdc-{sentinel_code}",
            },
            "rolling_observation": rolling_observation,
        },
    )


def probe_michigan_property_directory(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Michigan's statewide county-route directory contract."""

    adapter = query_michigan_property_directories
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.DIRECTORY_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "Michigan property-directory probe expected one contract record"
        )

    record = dict(result.records[0])
    platform_counts = record.get("platform_counts")
    review_flag_counts = record.get("review_flag_counts")
    sentinels = record.get("sentinels")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("county_count") != len(adapter.COUNTY_NAMES)
        or record.get("county_fips_count") != len(adapter.COUNTY_FIPS)
        or not isinstance(platform_counts, Mapping)
        or not isinstance(review_flag_counts, Mapping)
        or not isinstance(sentinels, Mapping)
        or set(sentinels)
        != {"Alcona", "Arenac", "Genesee", "Oakland", "Wayne", "Wexford"}
        or not isinstance(record.get("schema_fingerprint"), str)
        or len(str(record["schema_fingerprint"])) != 64
        or not isinstance(record.get("snapshot_fingerprint"), str)
        or len(str(record["snapshot_fingerprint"])) != 64
    ):
        raise ValueError("Michigan property-directory probe contract changed")
    for county, sentinel in sentinels.items():
        if (
            not isinstance(sentinel, Mapping)
            or sentinel.get("county_fips") != adapter.COUNTY_FIPS[county]
            or not isinstance(sentinel.get("official_url"), str)
            or not isinstance(sentinel.get("platform_family"), str)
            or not isinstance(sentinel.get("route_signals"), (list, tuple))
        ):
            raise ValueError("Michigan property-directory sentinel contract changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": {
            "jurisdiction_id": adapter.STATE_GEOID,
            "name": "Michigan",
            "state_code": adapter.STATE_CODE,
        },
        "directory_role": {
            "publisher_declared_role": "county_tax_parcel_layer_routes",
            "publisher_statement": adapter.DECLARED_ROLE_QUOTE,
            "statewide_query_service": False,
            "destination_capabilities_verified_by_directory": False,
        },
        "county_identity": {
            "expected_count": len(adapter.COUNTY_FIPS),
            "county_geoids": sorted(adapter.COUNTY_FIPS.values()),
        },
        "official_alternatives": [
            {
                "source_id": alternative["alternative_id"],
                "roles": list(alternative["roles"]),
                "official_url": alternative["official_url"],
                "authority": alternative["authority"],
                "coverage": alternative["coverage"],
                "not_equivalent_to": list(alternative.get("not_equivalent_to", ())),
            }
            for alternative in adapter._alternatives()
        ],
    }
    schema_contract = {
        "probe_record_kind": "source_probe",
        "directory_record_kind": "county_tax_parcel_route",
        "identity_fields": ["source_id", "county_fips"],
        "route_component_fields": [
            "published_label",
            "published_links",
            "published_unique_urls",
            "url",
            "canonical_url_without_fragment",
            "host",
            "platform_family",
        ],
        "evidence_layers": [
            "publisher_declared_role",
            "destination_triage",
            "role_separation",
        ],
        "shared_ingest_semantics": "snapshot_only",
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "directory_url": adapter.DIRECTORY_URL,
        "publisher_statement": adapter.DECLARED_ROLE_QUOTE,
        "county_geoids": sorted(adapter.COUNTY_FIPS.values()),
    }
    rolling_observation = {
        "source_url": record.get("source_url"),
        "platform_counts": _json_ready(platform_counts),
        "review_flag_counts": _json_ready(review_flag_counts),
        "partial_coverage_count": record.get("partial_coverage_count"),
        "schema_fingerprint": record.get("schema_fingerprint"),
        "snapshot_fingerprint": record.get("snapshot_fingerprint"),
        "sentinels": _json_ready(sentinels),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=int(record["county_count"]),
        details={
            **dict(observation.details),
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_broward_official_records(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Broward's public portal while hashing its durable route contract."""

    adapter = query_broward_official_records
    routes = adapter.source_routes()
    portal = dict(routes["official_record_portal"])
    daily = dict(routes["official_daily_release"])
    complements = {
        str(item["kind"]): dict(item) for item in routes["complementary_routes"]
    }
    required_complements = {
        "online_certified_copy_order",
        "search_copy_and_archive_service",
    }
    if not required_complements.issubset(complements):
        raise ValueError("Broward copy and archive route contract changed")

    route_contract = {
        "portal_search": {
            "url": portal["url"],
            "search_paths": dict(adapter.PORTAL_SEARCH_PATHS),
            "coverage_statements": dict(portal["coverage_statements"]),
            "public_image_route": portal["public_image_route"],
        },
        "certified_copy": {
            "url": complements["online_certified_copy_order"]["url"],
            "relationship": complements["online_certified_copy_order"]["relationship"],
        },
        "daily_bulk": {
            "url": daily["url"],
            "rolling_availability": daily["rolling_availability"],
            "files": dict(daily["files"]),
            "join_key": daily["join_key"],
        },
        "older_record_service": {
            "url": complements["search_copy_and_archive_service"]["url"],
            "relationship": complements["search_copy_and_archive_service"][
                "relationship"
            ],
        },
    }
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "record_identity": "instrument_number",
        "routes": route_contract,
    }
    schema_contract = {
        "record_kind": "source_probe",
        "record_fields": [
            "coverage_statements",
            "ok",
            "record_kind",
            "release",
            "schema_fingerprint",
            "search_routes",
            "source_id",
            "source_url",
            "title",
        ],
        "search_route_fields": ["href", "text"],
        "route_count": len(adapter.PORTAL_SEARCH_PATHS),
        "identity": "instrument_number",
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "portal_url": adapter.SEARCH_URL,
        "route_contract": route_contract,
    }
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.SEARCH_URL,
        started=started,
    )
    if not result.records:
        return replace(
            observation,
            schema_sha256=sha256_fingerprint(schema_contract),
            artifact_sha256=sha256_fingerprint(artifact_identity),
            details={
                **dict(observation.details),
                "stable_contract": stable_contract,
                "schema_contract": schema_contract,
                "artifact_identity": artifact_identity,
                "rolling_observation": {
                    "status": result.status.value,
                    "errors": [
                        error.to_dict()
                        if hasattr(error, "to_dict")
                        else {"message": str(error)}
                        for error in result.errors
                    ],
                },
            },
        )
    if len(result.records) != 1:
        raise ValueError("Broward Official Records probe expected one record")
    record = dict(result.records[0])
    raw_search_routes = record.get("search_routes")
    coverage_statements = record.get("coverage_statements")
    release = record.get("release")
    if (
        record.get("source_id") != adapter.SOURCE_ID
        or record.get("record_kind") != "source_probe"
        or not isinstance(raw_search_routes, Sequence)
        or isinstance(raw_search_routes, (str, bytes))
        or any(not isinstance(route, Mapping) for route in raw_search_routes)
        or not isinstance(coverage_statements, Sequence)
        or isinstance(coverage_statements, (str, bytes))
        or not isinstance(release, Mapping)
    ):
        raise ValueError("Broward Official Records probe contract changed")

    search_routes = [dict(route) for route in raw_search_routes]
    hrefs = [str(route.get("href") or "") for route in search_routes]
    missing_paths = [
        path
        for path in adapter.PORTAL_SEARCH_PATHS.values()
        if not any(href.rstrip("/").endswith(path) for href in hrefs)
    ]
    coverage_text = " ".join(str(item) for item in coverage_statements)
    coverage_markers = (
        "All plats and maps",
        "Other Official Records",
        "Documents recorded from 3/9/1972",
        "Documents recorded prior to 3/9/1972",
    )
    if missing_paths or any(marker not in coverage_text for marker in coverage_markers):
        raise ValueError("Broward Official Records search routes or coverage changed")

    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(search_routes),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "source_url": record.get("source_url"),
                "title": record.get("title"),
                "release": _json_ready(release),
                "search_routes": _json_ready(search_routes),
                "coverage_statements": list(coverage_statements),
                "source_schema_fingerprint": record.get("schema_fingerprint"),
            },
        },
    )


OSCEOLA_BENCHMARK_PROBE_CASE_NUMBER = "2023 CF 001540"
OSCEOLA_BENCHMARK_PROBE_DOCKET_ID = "56773534"


def probe_osceola_benchmark(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the Benchmark search, case, docket, and page-metadata contract."""

    adapter = query_osceola_courts
    if context.source_id != adapter.PORTAL_SOURCE_ID:
        raise ValueError("Osceola Benchmark monitor received an unknown source")

    client = adapter.PioneerBenchmarkClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    started = time.perf_counter()
    try:
        form = client.bootstrap()
        search_page = client.search(
            OSCEOLA_BENCHMARK_PROBE_CASE_NUMBER,
            native_mode="CaseNumber",
            offset=0,
            limit=1,
        )
        bundle = client.fetch_case(OSCEOLA_BENCHMARK_PROBE_CASE_NUMBER)
        documents = client.document_metadata_from_bundle(
            bundle,
            OSCEOLA_BENCHMARK_PROBE_DOCKET_ID,
        )
        requests_made = int(getattr(client, "request_count", 12))
    finally:
        client.close()

    search_records = [
        dict(hit.record) for hit in search_page.hits if isinstance(hit.record, Mapping)
    ]
    case_record = dict(bundle.record)
    docket_value = case_record.get("docket_entries")
    if not isinstance(docket_value, Sequence) or isinstance(
        docket_value,
        (str, bytes),
    ):
        raise ValueError("Osceola Benchmark docket collection changed")
    docket_records = [
        dict(record) for record in docket_value if isinstance(record, Mapping)
    ]
    document_records = [
        dict(record) for record in documents if isinstance(record, Mapping)
    ]
    exact_hits = [
        record
        for record in search_records
        if record.get("raw_case_number") == OSCEOLA_BENCHMARK_PROBE_CASE_NUMBER
    ]
    docket_ids = {
        str(record.get("native_entry_id"))
        for record in docket_records
        if record.get("native_entry_id") is not None
    }
    if (
        not exact_hits
        or case_record.get("source_id") != adapter.PORTAL_SOURCE_ID
        or case_record.get("record_kind") != "case"
        or case_record.get("raw_case_number") != OSCEOLA_BENCHMARK_PROBE_CASE_NUMBER
        or case_record.get("source_internal_id") is None
        or OSCEOLA_BENCHMARK_PROBE_DOCKET_ID not in docket_ids
        or not document_records
        or any(
            record.get("source_id") != adapter.PORTAL_SOURCE_ID
            or record.get("record_kind") != "document_page_metadata"
            or str(record.get("native_entry_id")) != OSCEOLA_BENCHMARK_PROBE_DOCKET_ID
            for record in document_records
        )
    ):
        raise ValueError("Osceola Benchmark sentinel contract changed")

    stable_contract = {
        "source": adapter.PORTAL_SOURCE.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "platform_family": adapter.PLATFORM_FAMILY,
        "shared_operations": [
            "case",
            "discovery",
            "docket",
            "documents",
            "probe",
            "search",
        ],
        "native_search_modes": sorted(adapter.NATIVE_SEARCH_MODES),
        "identity": {
            "case": [
                "canonical_ref",
                "source_internal_id",
                "raw_case_number",
            ],
            "docket": ["canonical_ref", "native_entry_id"],
            "document_page": [
                "canonical_ref",
                "native_entry_id",
                "native_document_id",
            ],
            "session_locator_fields_persisted": [],
        },
        "document_scope": "public_page_metadata_and_access_state",
        "certified_copy_route_separate": True,
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "bootstrap": {
            "fields": [
                "action_url",
                "hidden_fields",
                "native_search_modes",
                "platform_version",
                "source_document_sha256",
                "source_url",
            ],
            "verification_token_present": True,
        },
        "search": inferred_schema(search_records),
        "case": inferred_schema([case_record]),
        "docket": inferred_schema(docket_records),
        "document_page_metadata": inferred_schema(document_records),
    }
    artifact_identity = {
        "source_id": adapter.PORTAL_SOURCE_ID,
        "search_landing_url": adapter.SEARCH_LANDING_URL,
        "case_search_url": adapter.CASE_SEARCH_URL,
        "result_data_url": adapter.RESULT_DATA_URL,
        "sentinel_case_number": OSCEOLA_BENCHMARK_PROBE_CASE_NUMBER,
        "sentinel_docket_id": OSCEOLA_BENCHMARK_PROBE_DOCKET_ID,
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.SEARCH_LANDING_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "requests_made": requests_made,
            "stable_contract": stable_contract,
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": stable_schema_sha256,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "platform_version": form.platform_version,
                "bootstrap_document_sha256": form.source_document_sha256,
                "search_source_row_count": search_page.source_row_count,
                "search_total_reported": search_page.total_reported,
                "search_document_sha256": search_page.source_document_sha256,
                "case_source_internal_id": case_record.get("source_internal_id"),
                "case_bundle_sha256": bundle.source_document_sha256,
                "docket_entry_count": len(docket_records),
                "document_page_count": len(document_records),
                "document_metadata_sha256": sorted(
                    {
                        str(record["source_document_sha256"])
                        for record in document_records
                        if record.get("source_document_sha256")
                    }
                ),
            },
        },
    )


def probe_osceola_report(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify one rolling Osceola Clerk report route by HEAD metadata."""

    adapter = query_osceola_courts
    report_kinds = {
        adapter.CALENDAR_SOURCE_ID: "calendar",
        adapter.FORECLOSURE_SOURCE_ID: "foreclosure",
    }
    kind = report_kinds.get(context.source_id)
    if kind is None:
        raise ValueError("Osceola report monitor received an unknown source")

    client = adapter.PioneerBenchmarkClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    started = time.perf_counter()
    try:
        artifact = client.report_head(kind)
        requests_made = int(getattr(client, "request_count", 1))
    finally:
        client.close()

    report_record = adapter._report_record(kind)
    expected_url = (
        adapter.CALENDAR_URL if kind == "calendar" else adapter.FORECLOSURE_URL
    )
    if (
        artifact.source_url != expected_url
        or artifact.media_type not in {"application/pdf", "application/octet-stream"}
        or report_record.get("source_id") != context.source_id
        or report_record.get("artifact_url") != expected_url
        or report_record.get("projection", {}).get("projectable_as_case_record")
        is not False
    ):
        raise ValueError("Osceola rolling report identity changed")

    stable_contract = {
        "source": adapter.SOURCE_BY_ID[context.source_id].to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "shared_operations": ["discovery", "probe"],
        "record_kind": report_record["record_kind"],
        "record_grain": "rolling_official_pdf_snapshot",
        "projection": "source_snapshot_only",
        "artifact_url": expected_url,
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "head_probe": {
            "accepted_media_types": [
                "application/octet-stream",
                "application/pdf",
            ],
            "rolling_headers": [
                "content-length",
                "etag",
                "last-modified",
            ],
        },
    }
    artifact_identity = {
        "source_id": context.source_id,
        "canonical_ref": report_record["canonical_ref"],
        "artifact_url": expected_url,
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=expected_url,
        http_status=artifact.status_code,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "requests_made": requests_made,
            "stable_contract": stable_contract,
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": stable_schema_sha256,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "media_type": artifact.media_type,
                "content_length": artifact.headers.get("content-length"),
                "last_modified": artifact.headers.get("last-modified"),
                "etag": artifact.headers.get("etag"),
            },
        },
    )


def probe_florida_ninth_opinions(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the Ninth Circuit opinion index and one official PDF."""

    adapter = query_florida_ninth_opinions
    client = adapter.FloridaNinthOpinionsClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    started = time.perf_counter()
    try:
        index_artifact = client.index(None, page=0)
        parsed = adapter.parse_index_page(
            index_artifact,
            requested_page=0,
        )
        if not parsed.records:
            raise ValueError(
                "Ninth Circuit appellate-opinion archive returned no first-page records"
            )
        first_record = dict(parsed.records[0])
        document_url = str(first_record.get("document_url") or "")
        document = client.document(document_url)
    finally:
        client.close()

    expected_identifier = hashlib.sha256(document_url.encode()).hexdigest()[:24]
    if (
        first_record.get("source_id") != adapter.SOURCE_ID
        or first_record.get("record_kind") != "circuit_appellate_opinion_index"
        or first_record.get("native_document_id") != expected_identifier
    ):
        raise ValueError("Ninth Circuit appellate-opinion record identity changed")

    court = first_record.get("court")
    projection = first_record.get("projection")
    if not isinstance(court, Mapping) or not isinstance(projection, Mapping):
        raise ValueError("Ninth Circuit appellate-opinion nested record shape changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "court_id": adapter.COURT_ID,
        "county_geoids": list(adapter.COUNTY_GEOIDS),
        "record_kind": "circuit_appellate_opinion_index",
        "identity": {
            "native_document_id": "sha256(document_url)[:24]",
            "stable_keys": ["native_document_id", "document_url"],
        },
        "scope": {
            "publication_types": [
                "circuit_appellate_opinion",
                "certiorari_opinion",
                "writ_opinion",
            ],
            "general_trial_order_feed": False,
            "complete_trial_docket": False,
        },
        "complementary_sources": list(adapter.COMPLEMENTARY_SOURCES),
    }
    schema_contract = {
        "index_record_fields": sorted(first_record),
        "court_fields": sorted(court),
        "projection_fields": sorted(projection),
        "document": {
            "media_type": "application/pdf",
            "signature": "%PDF-",
        },
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "index_url": adapter.INDEX_URL,
        "pdf_route": {
            "host": "ninthcircuit.org",
            "path_prefix": "/sites/default/files/",
        },
        "record_identity": "sha256(document_url)[:24]",
    }
    rolling_observation = {
        "first_page_record_count": len(parsed.records),
        "last_page_index": parsed.last_page_index,
        "source_url": parsed.source_url,
        "source_document_sha256": parsed.source_document_sha256,
        "first_document_url": document.source_url,
        "first_document_bytes": len(document.content),
        "first_document_sha256": document.sha256,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.INDEX_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=len(parsed.records),
        details={
            "requests_made": 2,
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


FLORIDA_COURT_DIRECTORY_DATA_MONITOR_SOURCE_IDS = set(
    query_florida_court_directory_data.COMPONENTS
)


def probe_florida_court_directory_data_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Florida directory, request, or statistics snapshot."""

    adapter = query_florida_court_directory_data
    if context.source_id not in FLORIDA_COURT_DIRECTORY_DATA_MONITOR_SOURCE_IDS:
        raise ValueError(
            "Florida court directory/data monitor received an unknown component"
        )

    client = adapter.FloridaCourtsClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    started = time.perf_counter()
    try:
        if context.source_id == adapter.LOCATION_SOURCE_ID:
            artifact = client.locations()
            records = list(adapter.parse_location_directory(artifact))
        elif context.source_id == adapter.VIRTUAL_SOURCE_ID:
            artifact = client.virtual()
            records = list(adapter.parse_virtual_directory(artifact))
        elif context.source_id == adapter.PUBLIC_RECORDS_SOURCE_ID:
            artifact = client.page(adapter.PUBLIC_RECORDS_URL)
            records = [adapter.parse_data_request_program(artifact)]
        else:
            artifact = client.page(adapter.STATISTICS_CATALOG_URL)
            records = list(adapter.parse_statistics_catalog(artifact))
    finally:
        client.close()

    component = adapter.COMPONENTS[context.source_id]
    stable_contract = {
        "source": adapter.SOURCE_METADATA[context.source_id].to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "component": {
            "source_id": component.source_id,
            "source_role": component.source_role,
            "operations": list(component.operations),
            "relationship": component.relationship,
        },
        "publisher_and_transport": {
            "authority": adapter.AUTHORITY,
            "publisher": adapter.AUTHORITY,
            "retrieval_transport": "direct official HTTPS",
            "publisher_transport_distinct": False,
            "counts_as_independent_corroboration": False,
        },
        "snapshot_semantics": {
            "shared_ingest": "snapshot_only",
            "case_projection": False,
        },
    }
    artifact_identity = {
        "source_id": context.source_id,
        "endpoint": component.base_url,
        "adapter_family": adapter.ADAPTER_FAMILY,
        "operations": list(component.operations),
    }

    if context.source_id == adapter.LOCATION_SOURCE_ID:
        allowed_kinds = {
            "county_courthouse_location",
            "district_court_of_appeal_location",
            "state_supreme_court_location",
        }
        if not records or any(
            record.get("source_id") != context.source_id
            or record.get("record_kind") not in allowed_kinds
            or record.get("projection", {}).get("projectable_as_case") is not False
            for record in records
        ):
            raise ValueError("Florida court-location record contract changed")
        county_records = [
            record
            for record in records
            if record["record_kind"] == "county_courthouse_location"
        ]
        published_counties = {str(record["county"]) for record in county_records}
        omitted_counties = [
            {
                "county": county,
                "county_geoid": geoid,
            }
            for county, geoid in adapter.COUNTY_GEOID_BY_NAME.items()
            if county not in published_counties
        ]
        region_mismatches = [
            {
                "county": record.get("county"),
                "map_category": record["appellate_map_category"].get("identifier"),
                "published_region": (record.get("published_region") or {}).get(
                    "identifier"
                ),
            }
            for record in records
            if record.get("published_region_matches_map_category") is False
        ]
        schema_contract = {
            "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
            "record_kinds": sorted(allowed_kinds),
            "identity_fields": ["source_id", "native_record_id"],
            "county_identity_field": "county_geoid",
            "publisher_category_field": "appellate_map_category",
            "publisher_embedded_region_field": "published_region",
            "publisher_embedded_region_is_normalized_geography": False,
            "published_omissions_are_observations": True,
        }
        rolling_observation = {
            "source_url": artifact.source_url,
            "source_document_sha256": artifact.sha256,
            "record_count": len(records),
            "county_courthouse_count": len(county_records),
            "district_court_of_appeal_count": sum(
                record["record_kind"] == "district_court_of_appeal_location"
                for record in records
            ),
            "supreme_court_count": sum(
                record["record_kind"] == "state_supreme_court_location"
                for record in records
            ),
            "published_county_omissions": omitted_counties,
            "published_region_mismatches": region_mismatches,
            "published_values_normalized_or_corrected": False,
        }
    elif context.source_id == adapter.VIRTUAL_SOURCE_ID:
        if not records or any(
            record.get("source_id") != context.source_id
            or record.get("record_kind") != "virtual_courtroom_directory_entry"
            or record.get("projection", {}).get("projectable_as_case") is not False
            for record in records
        ):
            raise ValueError(
                "Florida Virtual Courtroom Directory record contract changed"
            )
        schema_contract = {
            "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
            "record_kind": "virtual_courtroom_directory_entry",
            "identity_fields": ["source_id", "native_record_id"],
            "mutable_snapshot_fields": [
                "judge_or_hearing_officer",
                "counties",
                "stream",
            ],
            "complete_judicial_roster": False,
        }
        rolling_observation = {
            "source_url": artifact.source_url,
            "source_document_sha256": artifact.sha256,
            "record_count": len(records),
            "named_judicial_officer_count": sum(
                bool(record.get("judge_or_hearing_officer")) for record in records
            ),
            "live_count": sum(
                bool((record.get("stream") or {}).get("live")) for record in records
            ),
            "published_counties": sorted(
                {
                    str(county)
                    for record in records
                    for county in record.get("counties", ())
                }
            ),
        }
    elif context.source_id == adapter.PUBLIC_RECORDS_SOURCE_ID:
        record = records[0] if len(records) == 1 else {}
        if (
            record.get("source_id") != context.source_id
            or record.get("record_kind") != "public_records_request_program"
            or record.get("request_scope") != "records_held_by_osca"
            or record.get("projection", {}).get("projectable_as_case") is not False
        ):
            raise ValueError("OSCA public-records request contract changed")
        schema_contract = {
            "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
            "record_kind": "public_records_request_program",
            "identity_fields": ["source_id", "canonical_ref"],
            "request_scope": "records_held_by_osca",
            "local_court_records_in_scope": False,
            "direct_case_level_bulk_feed": False,
        }
        rolling_observation = {
            "source_url": artifact.source_url,
            "source_document_sha256": artifact.sha256,
            "request_methods": _json_ready(record.get("request_methods")),
            "fee_estimate_notice_published": record.get(
                "fee_estimate_notice_published"
            ),
        }
    else:
        if not records or any(
            record.get("source_id") != context.source_id
            or record.get("record_kind") != "trial_court_statistical_publication"
            or record.get("projection", {}).get("projectable_as_case") is not False
            or not record.get("artifact_url")
            for record in records
        ):
            raise ValueError("Florida trial-court statistics catalog contract changed")
        section_counts: dict[str, int] = {}
        for record in records:
            section = str(record.get("catalog_section") or "unsectioned")
            section_counts[section] = section_counts.get(section, 0) + 1
        schema_contract = {
            "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
            "record_kind": "trial_court_statistical_publication",
            "occurrence_identity_fields": [
                "fiscal_year",
                "catalog_section",
                "native_document_id",
            ],
            "artifact_locator_field": "artifact_url",
            "case_level_bulk_feed": False,
            "exact_pdf_download": {
                "adapter_command": "download",
                "shared_router_operation": None,
                "validation": ["media_type", "byte_length", "sha256"],
            },
        }
        rolling_observation = {
            "source_url": artifact.source_url,
            "source_document_sha256": artifact.sha256,
            "publication_count": len(records),
            "fiscal_years": sorted({str(record["fiscal_year"]) for record in records}),
            "section_counts": dict(sorted(section_counts.items())),
            "first_artifact": {
                key: records[0].get(key)
                for key in (
                    "native_document_id",
                    "fiscal_year",
                    "catalog_section",
                    "title",
                    "artifact_url",
                )
            },
        }

    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=component.base_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        http_status=artifact.status_code,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(records),
        details={
            "requests_made": 1,
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_georgia_property_source(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Georgia's county-property directory or statewide land index."""

    adapter = query_georgia_property_sources
    if context.source_id not in adapter.SOURCE_METADATA_BY_ID:
        raise ValueError("Georgia property monitor received an unknown source")

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--source",
            context.source_id,
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    endpoint = (
        adapter.DIRECTORY_URL
        if context.source_id == adapter.DIRECTORY_SOURCE_ID
        else adapter.GSCCCA_INFORMATION_URL
    )
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Georgia property probe expected one contract record")

    record = dict(result.records[0])
    stable_schema_sha256 = record.get("stable_schema_sha256")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
        or record.get("status") != "ok"
        or not isinstance(stable_schema_sha256, str)
        or len(stable_schema_sha256) != 64
    ):
        raise ValueError("Georgia property probe contract changed")

    stable_contract: dict[str, Any] = {
        "source": adapter.SOURCE_METADATA_BY_ID[context.source_id].to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "adapter_family": "georgia_property_sources",
        "shared_ingest_semantics": "snapshot_only",
        "property_projection": False,
    }

    if context.source_id == adapter.DIRECTORY_SOURCE_ID:
        platform_counts = record.get("platform_counts")
        missing_counties = record.get("missing_counties")
        unexpected_counties = record.get("unexpected_counties")
        route_disagreements = record.get("route_disagreements")
        row_count = record.get("row_count")
        expected_county_count = record.get("expected_county_count")
        if (
            isinstance(row_count, bool)
            or not isinstance(row_count, int)
            or row_count < 1
            or expected_county_count != len(adapter.COUNTY_NAMES)
            or not isinstance(platform_counts, Mapping)
            or any(
                isinstance(count, bool) or not isinstance(count, int) or count < 0
                for count in platform_counts.values()
            )
            or sum(platform_counts.values()) != row_count
            or not isinstance(missing_counties, Sequence)
            or isinstance(missing_counties, (str, bytes))
            or not isinstance(unexpected_counties, Sequence)
            or isinstance(unexpected_counties, (str, bytes))
            or not isinstance(route_disagreements, Sequence)
            or isinstance(route_disagreements, (str, bytes))
        ):
            raise ValueError("Georgia DOR property-directory probe contract changed")
        stable_contract.update(
            {
                "scope": "official county assessor and tax-system routes",
                "expected_counties": len(adapter.COUNTY_NAMES),
                "county_geoids": sorted(adapter.COUNTY_GEOIDS.values()),
                "identity": {
                    "record_kind": "county_property_source_route",
                    "stable_keys": [
                        "source_id",
                        "county_geoid",
                        "published_primary_url",
                    ],
                },
                "published_routes": [
                    "published_primary_url",
                    "published_description_url",
                ],
                "complementary_sources": [
                    adapter.GSCCCA_SOURCE_ID,
                ],
            }
        )
        schema_contract = {
            "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
            "probe_fields": sorted(record),
            "route_record_fields": [
                "canonical_ref",
                "county_geoid",
                "county_name",
                "destination_host",
                "directory_ordinal",
                "evidence_ref",
                "platform_family",
                "projection",
                "published_description_url",
                "published_primary_url",
                "record_kind",
                "route_target_disagreement",
                "source_document_sha256",
                "source_id",
                "source_url",
                "state_code",
            ],
            "route_stable_schema_sha256": stable_schema_sha256,
        }
        artifact_identity = {
            "source_id": adapter.DIRECTORY_SOURCE_ID,
            "directory_url": adapter.DIRECTORY_URL,
            "county_geoids": sorted(adapter.COUNTY_GEOIDS.values()),
            "stable_keys": [
                "county_geoid",
                "published_primary_url",
            ],
            "platform_families": [
                "county_hosted",
                "qpublic_legacy",
                "qpublic_schneider",
            ],
        }
        rolling_observation = {
            "row_count": row_count,
            "expected_county_count": expected_county_count,
            "missing_counties": list(missing_counties),
            "unexpected_counties": list(unexpected_counties),
            "route_disagreements": list(route_disagreements),
            "platform_counts": _json_ready(platform_counts),
            "source_url": record.get("source_url"),
            "source_document_sha256": record.get("source_document_sha256"),
        }
        requests_made = 1
        result_count = row_count
    else:
        coverage = record.get("coverage")
        access = record.get("access")
        component_sha256 = record.get("component_sha256")
        if (
            not isinstance(coverage, Mapping)
            or coverage.get("geography") != "all Georgia counties"
            or coverage.get("deed_index_since_at_least") != "1999-01-01"
            or coverage.get("historical_data") != "continually_added"
            or not isinstance(
                coverage.get("search_dimensions"),
                Sequence,
            )
            or isinstance(
                coverage.get("search_dimensions"),
                (str, bytes),
            )
            or not isinstance(coverage.get("summary_fields"), Sequence)
            or isinstance(
                coverage.get("summary_fields"),
                (str, bytes),
            )
            or not isinstance(access, Mapping)
            or access.get("search_requires_account") is not True
            or access.get("limited_use_account_cost") != "no_cost"
            or access.get("limited_use_recurring_fee") is not False
            or access.get("limited_use_summary_index_access") is not True
            or access.get("limited_use_document_images") is not False
            or access.get("registration_url") != adapter.GSCCCA_REGISTRATION_URL
            or access.get("search_url") != adapter.GSCCCA_SEARCH_URL
            or not isinstance(component_sha256, Mapping)
            or set(component_sha256) != {"information", "limited_use", "login_gate"}
            or any(
                not isinstance(digest, str) or len(digest) != 64
                for digest in component_sha256.values()
            )
        ):
            raise ValueError("Georgia GSCCCA handoff probe contract changed")
        stable_contract.update(
            {
                "scope": ("statewide deed, lien, and plat index acquisition handoff"),
                "identity": {
                    "record_kind": "property_index_acquisition_handoff",
                    "stable_keys": ["canonical_ref"],
                    "canonical_ref": ("GA-GSCCCA-REAL-ESTATE-INDEX:13/handoff"),
                },
                "coverage": _json_ready(coverage),
                "access": _json_ready(access),
                "complementary_sources": [
                    adapter.DIRECTORY_SOURCE_ID,
                    "county Superior Court clerks",
                ],
            }
        )
        schema_contract = {
            "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
            "probe_fields": sorted(record),
            "handoff_record_kind": "property_index_acquisition_handoff",
            "handoff_identity": ["canonical_ref"],
            "coverage_fields": sorted(coverage),
            "access_fields": sorted(access),
            "handoff_stable_schema_sha256": stable_schema_sha256,
        }
        artifact_identity = {
            "source_id": adapter.GSCCCA_SOURCE_ID,
            "canonical_ref": ("GA-GSCCCA-REAL-ESTATE-INDEX:13/handoff"),
            "information_url": adapter.GSCCCA_INFORMATION_URL,
            "search_url": adapter.GSCCCA_SEARCH_URL,
            "login_gate_url": adapter.GSCCCA_LOGIN_GATE_URL,
            "limited_use_url": adapter.GSCCCA_LIMITED_USE_URL,
            "registration_url": adapter.GSCCCA_REGISTRATION_URL,
        }
        rolling_observation = {
            "component_sha256": _json_ready(component_sha256),
        }
        requests_made = 3
        result_count = 1

    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=result_count,
        details={
            **dict(observation.details),
            "requests_made": requests_made,
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_georgia_court_personnel_directory(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Georgia AOC's current court-personnel directory snapshot."""

    adapter = query_georgia_court_directory
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Georgia court-personnel monitor received an unknown source")

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Georgia court-personnel probe expected one contract record")

    record = dict(result.records[0])
    stable_probe_contract = _json_ready(record.get("stable_contract"))
    schema_contract = _json_ready(record.get("schema_contract"))
    rolling_observation = _json_ready(record.get("rolling_observation"))
    requests_made = record.get("requests_made")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("snapshot_only") is not True
        or not isinstance(stable_probe_contract, Mapping)
        or stable_probe_contract.get("application_id") != adapter.APP_ID
        or stable_probe_contract.get("search_view")
        != {
            "scene_id": adapter.SEARCH_SCENE,
            "view_id": adapter.SEARCH_VIEW,
        }
        or stable_probe_contract.get("detail_view")
        != {
            "scene_id": adapter.DETAIL_SCENE,
            "view_id": adapter.DETAIL_VIEW,
        }
        or stable_probe_contract.get("filter")
        != list(adapter.build_filters({"directory_section": "Superior Court Clerks"}))
        or stable_probe_contract.get("identity") != "exact native record ID"
        or not isinstance(schema_contract, Mapping)
        or not isinstance(schema_contract.get("search"), Sequence)
        or isinstance(schema_contract.get("search"), (str, bytes))
        or not schema_contract.get("search")
        or any(
            not isinstance(digest, str) or len(digest) != 64
            for digest in schema_contract["search"]
        )
        or not isinstance(schema_contract.get("detail"), str)
        or len(schema_contract["detail"]) != 64
        or not isinstance(rolling_observation, Mapping)
        or isinstance(
            rolling_observation.get("matching_total_records"),
            bool,
        )
        or not isinstance(
            rolling_observation.get("matching_total_records"),
            int,
        )
        or rolling_observation["matching_total_records"] < 1
        or not isinstance(
            rolling_observation.get("sample_record_id"),
            str,
        )
        or not rolling_observation["sample_record_id"]
        or not isinstance(
            rolling_observation.get("sample_directory_sections"),
            Sequence,
        )
        or isinstance(
            rolling_observation.get("sample_directory_sections"),
            (str, bytes),
        )
        or "Superior Court Clerks"
        not in rolling_observation["sample_directory_sections"]
        or requests_made != 2
    ):
        raise ValueError("Georgia court-personnel probe contract changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "probe": _json_ready(stable_probe_contract),
        "snapshot_semantics": {
            "snapshot_only": True,
            "historical_roster": False,
            "case_projection": False,
        },
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "landing_url": adapter.LANDING_URL,
        "application_id": stable_probe_contract["application_id"],
        "search_view": _json_ready(stable_probe_contract["search_view"]),
        "detail_view": _json_ready(stable_probe_contract["detail_view"]),
        "record_identity": stable_probe_contract["identity"],
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(_json_ready(schema_contract)),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=rolling_observation["matching_total_records"],
        details={
            **dict(observation.details),
            "requests_made": requests_made,
            "stable_contract": stable_contract,
            "schema_contract": _json_ready(schema_contract),
            "artifact_identity": artifact_identity,
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def probe_georgia_court_access_directory(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Georgia AOC court-provider directory snapshot."""

    adapter = query_georgia_court_access
    if context.source_id not in adapter.SOURCE_IDS:
        raise ValueError("Georgia court-access monitor received an unknown source")

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--source",
            context.source_id,
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    source = adapter.SOURCE_METADATA_BY_ID[context.source_id]
    observation = _adapter_result_observation(
        result,
        endpoint=str(source.base_url),
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Georgia court-access probe expected one contract record")

    record = dict(result.records[0])
    stable_contract = _json_ready(record.get("stable_contract"))
    schema_contract = _json_ready(record.get("schema_contract"))
    rolling_observation = _json_ready(record.get("rolling_observation"))
    stable_schema_sha256 = record.get("stable_schema_sha256")
    source_snapshot_sha256 = record.get("source_snapshot_sha256")
    requests_made = record.get("requests_made")
    expected_requests = 2 if context.source_id == adapter.EACCESS_SOURCE_ID else 1
    expected_record_kind = (
        "case_access_acquisition_handoff"
        if context.source_id == adapter.EACCESS_SOURCE_ID
        else "efile_provider_directory_entry"
    )
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
        or record.get("status") != "ok"
        or record.get("snapshot_only") is not True
        or not isinstance(stable_contract, Mapping)
        or stable_contract.get("source") != source.to_dict()
        or stable_contract.get("jurisdiction") != adapter.JURISDICTION.to_dict()
        or stable_contract.get("record_kind") != expected_record_kind
        or stable_contract.get("stable_identity") != ["canonical_ref"]
        or stable_contract.get("snapshot_semantics")
        != {
            "snapshot_only": True,
            "case_projection": False,
            "filing_projection": False,
        }
        or not isinstance(schema_contract, Mapping)
        or schema_contract.get("stable_identity") != ["canonical_ref"]
        or schema_contract.get("snapshot_only") is not True
        or schema_contract.get("case_projection") is not False
        or schema_contract.get("filing_projection") is not False
        or not isinstance(stable_schema_sha256, str)
        or len(stable_schema_sha256) != 64
        or sha256_fingerprint(schema_contract) != stable_schema_sha256
        or not isinstance(source_snapshot_sha256, str)
        or len(source_snapshot_sha256) != 64
        or not isinstance(rolling_observation, Mapping)
        or isinstance(rolling_observation.get("record_count"), bool)
        or not isinstance(rolling_observation.get("record_count"), int)
        or rolling_observation["record_count"] < 1
        or rolling_observation.get("missing_superior_counties") != []
        or rolling_observation.get("unexpected_superior_counties") != []
        or requests_made != expected_requests
    ):
        raise ValueError("Georgia court-access probe contract changed")

    if context.source_id == adapter.EACCESS_SOURCE_ID:
        if (
            stable_contract.get("access")
            != {
                "account_required": True,
                "directory_handoff": True,
                "case_search_completed": False,
            }
            or stable_contract.get("provider_selection_page")
            != {
                "published_url": adapter.EACCESS_VENDOR_PUBLISHED_URL,
                "canonical_url": adapter.EACCESS_VENDOR_URL,
            }
            or set(
                rolling_observation.get(
                    "published_route_kind_counts",
                    {},
                )
            )
            - {"direct_provider", "provider_selection_page"}
            or set(
                rolling_observation.get(
                    "provider_candidate_counts",
                    {},
                )
            )
            != {"peachcourt", "researchga"}
        ):
            raise ValueError("Georgia e-access provider-directory contract changed")
        provider_ids = ["peachcourt", "researchga"]
        artifact_urls = [
            adapter.EACCESS_URL,
            adapter.EACCESS_VENDOR_PUBLISHED_URL,
            adapter.EACCESS_VENDOR_URL,
        ]
    else:
        provider_state_counts = rolling_observation.get(
            "provider_state_counts",
            {},
        )
        allowed_states = {"mandatory", "available", "not_listed"}
        if (
            stable_contract.get("filing")
            != {
                "account_required_to_initiate": True,
                "filing_initiated": False,
                "case_evidence": False,
            }
            or stable_contract.get("blank_cell_semantics") != "not_listed"
            or set(provider_state_counts)
            != {
                "odyssey_efilega",
                "peachcourt",
                "greenfiling_infotrack",
            }
            or any(
                set(states) - allowed_states
                for states in provider_state_counts.values()
                if isinstance(states, Mapping)
            )
            or any(
                not isinstance(states, Mapping)
                for states in provider_state_counts.values()
            )
            or rolling_observation.get("unexpected_published_states") != []
            or rolling_observation.get("published_provider_dates_present") is not False
        ):
            raise ValueError("Georgia e-file provider-directory contract changed")
        provider_ids = [
            "greenfiling_infotrack",
            "odyssey_efilega",
            "peachcourt",
        ]
        artifact_urls = [adapter.EFILE_URL]

    artifact_identity = {
        "source_id": context.source_id,
        "source_url": source.base_url,
        "artifact_urls": artifact_urls,
        "court_identity": {
            "fields": ["county_geoid", "court_class"],
            "format": "GA-COURT:<county_geoid>:<court_class>",
        },
        "provider_ids": provider_ids,
    }
    rolling = {
        **dict(rolling_observation),
        "source_snapshot_sha256": source_snapshot_sha256,
    }
    return replace(
        observation,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=rolling_observation["record_count"],
        details={
            **dict(observation.details),
            "requests_made": requests_made,
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling,
        },
    )


def probe_georgia_court_data_source(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Georgia AOC aggregate court-data source."""

    adapter = query_georgia_court_data
    if context.source_id not in adapter.SOURCE_BY_ID:
        raise ValueError("Georgia court-data monitor received an unknown source")

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--source",
            context.source_id,
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.DATA_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Georgia court-data probe expected one contract record")

    record = dict(result.records[0])
    stable_schema_sha256 = record.get("stable_schema_sha256")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
        or record.get("status") != "ok"
        or not isinstance(stable_schema_sha256, str)
        or len(stable_schema_sha256) != 64
    ):
        raise ValueError("Georgia court-data probe contract changed")

    stable_contract: dict[str, Any] = {
        "source": adapter.SOURCE_BY_ID[context.source_id].to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "adapter_family": "georgia_court_data",
        "aggregate_scope": {
            "individual_case_records": False,
            "shared_ingest": "source_snapshot_only",
            "case_projection": False,
        },
    }

    if context.source_id == adapter.DASHBOARD_SOURCE_ID:
        court_classes = record.get("court_classes")
        dashboard_count = record.get("dashboard_count")
        source_document_sha256 = record.get("source_document_sha256")
        dashboard_user_guide_url = record.get("dashboard_user_guide_url")
        export_request_url = record.get("export_request_url")
        if (
            dashboard_count != len(adapter.COURT_CLASSES)
            or not isinstance(court_classes, Sequence)
            or isinstance(court_classes, (str, bytes))
            or list(court_classes) != list(adapter.COURT_CLASSES)
            or record.get("individual_case_records") is not False
            or not isinstance(source_document_sha256, str)
            or len(source_document_sha256) != 64
            or not isinstance(dashboard_user_guide_url, str)
            or not dashboard_user_guide_url.startswith(
                "https://research.georgiacourts.gov/"
            )
            or export_request_url != adapter.EXPORT_REQUEST_URL
        ):
            raise ValueError("Georgia AOC dashboard probe contract changed")
        stable_contract.update(
            {
                "record_grain": "aggregate self-reported case counts",
                "court_classes": list(adapter.COURT_CLASSES),
                "identity": {
                    "record_kind": "aggregate_caseload_dashboard",
                    "stable_keys": ["canonical_ref"],
                    "canonical_reference_pattern": (
                        "GA-AOC-CASELOAD-DASHBOARD:<COURT_CLASS>"
                    ),
                },
                "published_routes": {
                    "catalog": adapter.DATA_URL,
                    "export_request": adapter.EXPORT_REQUEST_URL,
                },
                "complementary_sources": [
                    adapter.WORKLOAD_SOURCE_ID,
                    query_georgia_court_directory.SOURCE_ID,
                ],
            }
        )
        schema_contract = {
            "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
            "probe_fields": sorted(record),
            "dashboard_record_fields": [
                "canonical_ref",
                "court_class",
                "dashboard_title",
                "dashboard_url",
                "data_scope",
                "export_request_url",
                "platform_family",
                "projection",
                "record_kind",
                "source_document_sha256",
                "source_id",
                "source_url",
            ],
            "dashboard_stable_schema_sha256": stable_schema_sha256,
        }
        artifact_identity = {
            "source_id": adapter.DASHBOARD_SOURCE_ID,
            "catalog_url": adapter.DATA_URL,
            "export_request_url": adapter.EXPORT_REQUEST_URL,
            "court_classes": list(adapter.COURT_CLASSES),
            "canonical_reference_pattern": ("GA-AOC-CASELOAD-DASHBOARD:<COURT_CLASS>"),
        }
        rolling_observation = {
            "dashboard_count": dashboard_count,
            "dashboard_user_guide_url": dashboard_user_guide_url,
            "source_document_sha256": source_document_sha256,
        }
        requests_made = 1
        result_count = dashboard_count
    else:
        publication_count = record.get("publication_count")
        publication_years = record.get("publication_years")
        latest_publication_year = record.get("latest_publication_year")
        latest_artifact_url = record.get("latest_artifact_url")
        latest_artifact_sha256 = record.get("latest_artifact_sha256")
        latest_artifact_byte_length = record.get("latest_artifact_byte_length")
        source_document_sha256 = record.get("source_document_sha256")
        if (
            isinstance(publication_count, bool)
            or not isinstance(publication_count, int)
            or publication_count < 1
            or not isinstance(publication_years, Sequence)
            or isinstance(publication_years, (str, bytes))
            or len(publication_years) != publication_count
            or any(
                isinstance(year, bool) or not isinstance(year, int)
                for year in publication_years
            )
            or not adapter.BASELINE_WORKLOAD_YEARS.issubset(set(publication_years))
            or latest_publication_year != max(publication_years)
            or not isinstance(latest_artifact_url, str)
            or not latest_artifact_url.startswith("https://research.georgiacourts.gov/")
            or not latest_artifact_url.casefold().endswith(".pdf")
            or not isinstance(latest_artifact_sha256, str)
            or len(latest_artifact_sha256) != 64
            or isinstance(latest_artifact_byte_length, bool)
            or not isinstance(latest_artifact_byte_length, int)
            or latest_artifact_byte_length < 1
            or not isinstance(source_document_sha256, str)
            or len(source_document_sha256) != 64
        ):
            raise ValueError("Georgia Superior Court workload probe contract changed")
        stable_contract.update(
            {
                "record_grain": (
                    "annual aggregate circuit and statewide workload publication"
                ),
                "baseline_years": sorted(adapter.BASELINE_WORKLOAD_YEARS),
                "identity": {
                    "record_kinds": [
                        "annual_superior_court_workload_assessment",
                        "annual_superior_court_workload_pdf",
                    ],
                    "stable_keys": ["canonical_ref"],
                    "canonical_reference_pattern": (
                        "GA-AOC-SUPERIOR-WORKLOAD-ASSESSMENT:<YEAR>"
                    ),
                },
                "document_validation": [
                    "media_type",
                    "pdf_signature",
                    "byte_length",
                    "sha256",
                ],
                "complementary_sources": [
                    adapter.DASHBOARD_SOURCE_ID,
                    query_georgia_court_directory.SOURCE_ID,
                ],
            }
        )
        schema_contract = {
            "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
            "probe_fields": sorted(record),
            "publication_record_fields": [
                "canonical_ref",
                "data_scope",
                "pdf_url",
                "projection",
                "publication_year",
                "published_update_note",
                "record_kind",
                "source_document_sha256",
                "source_id",
                "source_url",
                "title",
            ],
            "pdf_additional_fields": [
                "artifact_byte_length",
                "artifact_media_type",
                "artifact_sha256",
                "artifact_url",
            ],
            "workload_stable_schema_sha256": stable_schema_sha256,
        }
        artifact_identity = {
            "source_id": adapter.WORKLOAD_SOURCE_ID,
            "catalog_url": adapter.DATA_URL,
            "official_document_host": "research.georgiacourts.gov",
            "canonical_reference_pattern": (
                "GA-AOC-SUPERIOR-WORKLOAD-ASSESSMENT:<YEAR>"
            ),
            "document_validation": [
                "media_type",
                "pdf_signature",
                "byte_length",
                "sha256",
            ],
        }
        rolling_observation = {
            "publication_count": publication_count,
            "publication_years": list(publication_years),
            "latest_publication_year": latest_publication_year,
            "latest_artifact_url": latest_artifact_url,
            "latest_artifact_sha256": latest_artifact_sha256,
            "latest_artifact_byte_length": (latest_artifact_byte_length),
            "source_document_sha256": source_document_sha256,
        }
        requests_made = 2
        result_count = publication_count

    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=result_count,
        details={
            **dict(observation.details),
            "requests_made": requests_made,
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_georgia_supreme_docket(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the official recent Georgia Supreme Court docket."""

    adapter = query_georgia_supreme_docket
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Georgia Supreme Court monitor received an unknown source")

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--case-number",
            adapter.PROBE_CASE_NUMBER,
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.PORTAL_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Georgia Supreme Court probe expected one contract record")

    record = dict(result.records[0])
    probe_contract = _json_ready(record.get("stable_contract"))
    schema_contract = _json_ready(record.get("schema_contract"))
    rolling_observation = _json_ready(record.get("rolling_observation"))
    expected_probe_contract = {
        "search_endpoint": adapter.SEARCH_URL,
        "detail_endpoint": f"{adapter.CASE_DETAIL_ROOT}/{{case_number}}",
        "search_response": "complete JSON array",
        "case_detail_sections": [
            "filingsAndOrders",
            "judgments",
            "attorneys",
        ],
        "document_access": "Clerk request handoff",
    }
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("source_url") != adapter.PORTAL_URL
        or probe_contract != expected_probe_contract
        or not isinstance(schema_contract, Mapping)
        or set(schema_contract) != {"search", "detail"}
        or any(
            not isinstance(digest, str) or len(digest) != 64
            for digest in schema_contract.values()
        )
        or not isinstance(rolling_observation, Mapping)
        or rolling_observation.get("case_number") != adapter.PROBE_CASE_NUMBER
        or not isinstance(
            rolling_observation.get("case_style"),
            str,
        )
        or not rolling_observation["case_style"]
        or any(
            isinstance(rolling_observation.get(field), bool)
            or not isinstance(rolling_observation.get(field), int)
            or rolling_observation[field] < 0
            for field in (
                "filing_metadata_count",
                "judgment_count",
                "attorney_count",
            )
        )
        or record.get("requests_made") != 2
    ):
        raise ValueError("Georgia Supreme Court probe contract changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "probe": probe_contract,
        "scope": {
            "court_id": adapter.COURT_ID,
            "case_window": "cases docketed in the last 5 years",
            "case_identity": ["court_id", "case_number"],
            "event_identity": "event_id",
            "public_document_urls": False,
        },
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "portal_url": adapter.PORTAL_URL,
        "search_endpoint": adapter.SEARCH_URL,
        "attorney_search_endpoint": adapter.ATTORNEY_SEARCH_URL,
        "detail_endpoint": f"{adapter.CASE_DETAIL_ROOT}/{{case_number}}",
        "system_lookup_endpoint": adapter.SYSTEM_DATA_URL,
        "court_id": adapter.COURT_ID,
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return replace(
        observation,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "requests_made": 2,
            "stable_contract": stable_contract,
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": stable_schema_sha256,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_edva_bankruptcy(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe bounded read-only EDVA bankruptcy archive contracts."""

    adapter = query_edva_bankruptcy
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("EDVA bankruptcy monitor received an unknown source")

    args = adapter.build_parser().parse_args(["probe"])
    client = adapter.EDVABankruptcyClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    started = time.perf_counter()
    try:
        result = adapter.execute(
            args,
            client=client,
            log_results=False,
        )
    finally:
        client.close()
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.RECAP_COVERAGE_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("EDVA bankruptcy probe expected one contract record")

    record = dict(result.records[0])
    probe_scope = _json_ready(record.get("probe_scope"))
    sentinel_observations = _json_ready(
        record.get("sentinel_observations")
    )
    post_fields = _json_ready(record.get("recap_fetch_post_fields"))
    expected_scope = {
        "bounded": True,
        "docket_entry_pages_per_target": 1,
        "coverage_inference": False,
    }
    expected_post_fields = {
        "request_type",
        "court",
        "docket",
        "docket_number",
        "pacer_case_id",
        "pacer_username",
        "pacer_password",
        "recap_document",
    }
    expected_sentinels = {
        (
            int(sentinel["courtlistener_docket_id"]),
            str(sentinel["docket_number"]),
            str(sentinel["pacer_case_id"]),
        )
        for sentinel in adapter.SENTINELS
    }
    observed_sentinels: set[tuple[int, str, str]] = set()
    if isinstance(sentinel_observations, list):
        for sentinel in sentinel_observations:
            if not isinstance(sentinel, Mapping):
                continue
            docket_id = sentinel.get("courtlistener_docket_id")
            docket_number = sentinel.get("docket_number")
            pacer_case_id = sentinel.get("pacer_case_id")
            if (
                isinstance(docket_id, int)
                and isinstance(docket_number, str)
                and isinstance(pacer_case_id, str)
            ):
                observed_sentinels.add(
                    (docket_id, docket_number, pacer_case_id)
                )
    if (
        record.get("record_kind") != "source_probe"
        or probe_scope != expected_scope
        or not isinstance(sentinel_observations, list)
        or len(sentinel_observations) != len(adapter.SENTINELS)
        or observed_sentinels != expected_sentinels
        or any(
            not isinstance(sentinel, Mapping)
            or isinstance(sentinel.get("first_page_entry_count"), bool)
            or not isinstance(sentinel.get("first_page_entry_count"), int)
            or sentinel["first_page_entry_count"] < 0
            or not isinstance(sentinel.get("first_page_has_next"), bool)
            or sentinel.get("matches_sentinel") is not True
            for sentinel in sentinel_observations
        )
        or not isinstance(post_fields, list)
        or not expected_post_fields.issubset(
            {str(field_name) for field_name in post_fields}
        )
        or record.get("recap_fetch_contract_present") is not True
        or record.get("healthy") is not True
    ):
        raise ValueError("EDVA bankruptcy probe contract changed")

    source_inventory = adapter.source_inventory()
    routes = source_inventory.get("routes")
    if not isinstance(routes, list) or any(
        not isinstance(route, Mapping) for route in routes
    ):
        raise ValueError("EDVA bankruptcy source inventory changed")
    route_roles = {
        str(route["route_id"]): str(route["role"])
        for route in routes
        if route.get("route_id") and route.get("role")
    }
    required_route_ids = {
        "courtlistener_recap",
        "courtlistener_recap_fetch",
        "pacer_case_locator",
        "edva_cm_ecf",
        "recap_pray_and_pay",
        "edva_clerk_copy_request",
        "edva_public_access_terminal",
        "federal_records_archive",
    }
    if set(route_roles) != required_route_ids:
        raise ValueError("EDVA bankruptcy source-route inventory changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "shared_read_operations": {
            "case": "exact_edva_bankruptcy_docket_number",
            "docket": "positive_courtlistener_docket_id",
            "documents": (
                "positive_courtlistener_docket_id_with_nested_recap_metadata"
            ),
            "discovery": "role_specific_source_inventory",
            "probe": "bounded_read_only_contract_check",
        },
        "monitor_excluded_operations": [
            "fetch-docket",
            "fetch-document",
            "fetch-status",
            "pray",
            "document_retrieval",
        ],
        "coverage_semantics": {
            "recap_is_archive_not_official_docket": True,
            "blocked_or_empty_archive_is_official_absence": False,
            "blocked_or_empty_archive_is_case_sealing": False,
            "document_states": ["available", "metadata_only"],
        },
        "source_route_roles": route_roles,
        "probe_request_contract": {
            "sentinel_dockets": len(adapter.SENTINELS),
            "docket_entry_pages_per_target": 1,
            "requests_made": 5,
            "network_methods": ["GET", "OPTIONS"],
            "post_requests": 0,
            "document_retrieval_requests": 0,
        },
    }
    sentinel_fields = sorted(
        {
            str(field_name)
            for sentinel in sentinel_observations
            if isinstance(sentinel, Mapping)
            for field_name in sentinel
        }
    )
    schema_contract = {
        "probe_fields": sorted(record),
        "probe_scope_fields": sorted(probe_scope),
        "sentinel_observation_fields": sentinel_fields,
        "source_inventory_fields": sorted(source_inventory),
        "source_route_fields": sorted(
            {
                str(field_name)
                for route in routes
                for field_name in route
            }
        ),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "court_id": adapter.COURT_ID,
        "courtlistener_court_id": adapter.COURTLISTENER_COURT_ID,
        "dockets_endpoint": adapter.DOCKETS_URL,
        "docket_entries_endpoint": adapter.DOCKET_ENTRIES_URL,
        "recap_fetch_contract_endpoint": adapter.RECAP_FETCH_URL,
        "official_ecf": adapter.EDVA_ECF_URL,
        "official_pacer_information": adapter.EDVA_PACER_INFO_URL,
        "clerk_copy_request": adapter.EDVA_COPY_REQUEST_URL,
        "archive_forms": adapter.EDVA_FORMS_URL,
        "sentinel_docket_ids": sorted(
            int(sentinel["courtlistener_docket_id"])
            for sentinel in adapter.SENTINELS
        ),
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    rolling_observation = {
        "sentinel_observations": sentinel_observations,
        "recap_fetch_contract_present": record.get(
            "recap_fetch_contract_present"
        ),
        "healthy": record.get("healthy"),
    }
    return replace(
        observation,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(sentinel_observations),
        details={
            **dict(observation.details),
            "requests_made": 5,
            "stable_contract": stable_contract,
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": stable_schema_sha256,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


GEORGIA_SUPREME_PUBLICATION_MONITOR_SOURCE_IDS = frozenset(
    query_georgia_supreme_publications.SOURCE_METADATA
)


def probe_georgia_supreme_publication(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one current Georgia Supreme decision-publication component."""

    adapter = query_georgia_supreme_publications
    source_id = context.source_id
    if source_id not in GEORGIA_SUPREME_PUBLICATION_MONITOR_SOURCE_IDS:
        raise ValueError(
            "Georgia Supreme publication monitor received an unknown source"
        )

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--source",
            source_id,
            "--year",
            str(adapter.VERIFIED_THROUGH_YEAR),
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    source_url = adapter.SOURCE_METADATA[source_id].base_url
    observation = _adapter_result_observation(
        result,
        endpoint=source_url,
        started=started,
    )
    if not result.records:
        return observation

    expected_components = {
        adapter.OPINION_SOURCE_ID: {"opinions_and_summaries"},
        adapter.CERT_GRANT_SOURCE_ID: {"certiorari_grants"},
        adapter.CERT_DENIAL_SOURCE_ID: {"certiorari_denials"},
        adapter.APPLICATION_GRANT_SOURCE_ID: {
            "discretionary_application_grants",
            "interlocutory_application_grants",
        },
    }[source_id]
    expected_request_count = 2 * len(expected_components)
    records: dict[str, dict[str, Any]] = {}
    for raw_record in result.records:
        if not isinstance(raw_record, Mapping):
            raise ValueError("Georgia Supreme publication probe returned a non-object")
        record = dict(raw_record)
        component = record.get("publication_component")
        if (
            record.get("record_kind") != "source_probe"
            or record.get("source_id") != source_id
            or record.get("status") != "ok"
            or not isinstance(component, str)
            or component not in expected_components
            or component in records
            or record.get("publication_year") != adapter.VERIFIED_THROUGH_YEAR
        ):
            raise ValueError("Georgia Supreme publication probe contract changed")
        for count_field in ("record_count", "document_record_count"):
            value = record.get(count_field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("Georgia Supreme publication probe count changed")
        if record["record_count"] < 1:
            raise ValueError("Georgia Supreme publication probe returned no records")
        for digest_field in (
            "source_document_sha256",
            "schema_fingerprint",
            "snapshot_fingerprint",
        ):
            value = record.get(digest_field)
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError(
                    "Georgia Supreme publication probe fingerprint changed"
                )
        document_probe = record.get("document_probe")
        if not isinstance(document_probe, Mapping):
            raise ValueError(
                "Georgia Supreme publication representative PDF disappeared"
            )
        if (
            document_probe.get("mime_type")
            not in {
                None,
                "application/pdf",
            }
            or not isinstance(document_probe.get("document_url"), str)
            or not document_probe["document_url"]
            or isinstance(document_probe.get("byte_count"), bool)
            or not isinstance(document_probe.get("byte_count"), int)
            or document_probe["byte_count"] < 1
            or not isinstance(document_probe.get("sha256"), str)
            or len(document_probe["sha256"]) != 64
            or record.get("requests_made") != 2
        ):
            raise ValueError("Georgia Supreme publication PDF probe contract changed")
        records[component] = record
    if set(records) != expected_components:
        raise ValueError("Georgia Supreme publication component probe set changed")

    manifest = adapter._source_inventory_record(source_id)
    stable_contract = {
        "source": adapter.SOURCE_METADATA[source_id].to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "court_id": adapter.COURT_ID,
        "schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "verified_coverage": manifest["verified_coverage"],
        "annual_routes": manifest["annual_routes"],
        "publication_types": manifest["publication_types"],
        "document_contract": manifest["document_contract"],
        "opinion_version_notice": manifest["opinion_version_notice"],
        "separate_attribution": manifest["separate_attribution"],
        "identity": {
            "publication": [
                "component_source_id",
                "publication_type",
                "publication_year",
                "publication_date",
                "case_numbers",
                "document_url",
                "published_title",
            ],
            "case_join": ["court_id", "case_number"],
            "document": ["native_document_id", "source_url"],
            "multi_case_publications_preserved": True,
            "court_of_appeals_crosswalk_attribution_preserved": True,
        },
        "scope": {
            "complete_appellate_docket": False,
            "comprehensive_historical_opinion_archive": False,
            "website_copies_equal_final_official_reports_text": False,
        },
        "complements": manifest["complements"],
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "probe_record_fields": [
            "document_probe",
            "document_record_count",
            "page_updated_at",
            "publication_component",
            "publication_year",
            "record_count",
            "record_kind",
            "requests_made",
            "schema_fingerprint",
            "snapshot_fingerprint",
            "source_document_sha256",
            "source_id",
            "source_url",
            "status",
        ],
        "publication_components": sorted(expected_components),
        "publication_record_kinds": {
            adapter.OPINION_SOURCE_ID: [
                "noteworthy_opinion_summary_packet",
                "supreme_court_opinion_publication",
            ],
            adapter.CERT_GRANT_SOURCE_ID: [
                "supreme_court_certiorari_grant_publication",
            ],
            adapter.CERT_DENIAL_SOURCE_ID: [
                "supreme_court_certiorari_denial_list_entry",
            ],
            adapter.APPLICATION_GRANT_SOURCE_ID: [
                "supreme_court_application_grant_order",
            ],
        }[source_id],
        "document_probe": {
            "media_type": "application/pdf",
            "signature": "%PDF-",
            "identity_fields": ["document_url", "sha256"],
        },
    }
    monitor_page_urls = {
        component: (
            adapter._page_url(
                source_id,
                adapter.VERIFIED_THROUGH_YEAR,
                application_type=(
                    "discretionary"
                    if component == "discretionary_application_grants"
                    else "interlocutory"
                    if component == "interlocutory_application_grants"
                    else None
                ),
            )
        )
        for component in sorted(expected_components)
    }
    artifact_identity = {
        "source_id": source_id,
        "monitor_year": adapter.VERIFIED_THROUGH_YEAR,
        "annual_page_urls": monitor_page_urls,
        "document_route": {
            "host": "www.gasupreme.us",
            "path": "/wp-content/uploads/{year}/{month}/{filename.pdf}",
        },
    }
    rolling_components = {
        component: {
            key: _json_ready(record.get(key))
            for key in (
                "record_count",
                "document_record_count",
                "source_url",
                "source_document_sha256",
                "schema_fingerprint",
                "snapshot_fingerprint",
                "page_updated_at",
                "document_probe",
            )
        }
        for component, record in sorted(records.items())
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return replace(
        observation,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=sum(record["record_count"] for record in records.values()),
        details={
            **dict(observation.details),
            "requests_made": expected_request_count,
            "stable_contract": stable_contract,
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": stable_schema_sha256,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "components": rolling_components,
            },
        },
    )


def probe_california_opinions(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe both rolling California appellate-opinion collections."""

    adapter = query_california_opinions
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("California opinions monitor received an unknown source")

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.OPINIONS_HOME_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("California opinions probe expected one contract record")

    record = dict(result.records[0])
    operations_value = record.get("operations")
    feed_totals_value = record.get("feed_totals")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("status") != "ok"
        or not isinstance(operations_value, Mapping)
        or not isinstance(feed_totals_value, Mapping)
        or not isinstance(
            record.get("stable_contract_fingerprint"),
            str,
        )
        or len(str(record["stable_contract_fingerprint"])) != 64
        or not isinstance(record.get("live_state_fingerprint"), str)
        or len(str(record["live_state_fingerprint"])) != 64
    ):
        raise ValueError("California opinions probe contract changed")

    operations = {
        str(name): dict(value)
        for name, value in operations_value.items()
        if isinstance(value, Mapping)
    }
    expected_operation_names = {
        f"{collection}_{component}"
        for collection in adapter.COLLECTIONS
        for component in ("listing", "detail")
    }
    if set(operations) != expected_operation_names:
        raise ValueError("California opinions listing/detail probe set changed")

    listing_schema_fingerprints: dict[str, str] = {}
    observed_taxonomies: dict[str, dict[str, str]] = {}
    rolling_collections: dict[str, Any] = {}
    for collection, collection_config in adapter.COLLECTIONS.items():
        listing = operations[f"{collection}_listing"]
        detail = operations[f"{collection}_detail"]
        taxonomy_value = listing.get("source_taxonomy")
        if not isinstance(taxonomy_value, Mapping):
            raise ValueError("California opinions listing taxonomy changed")
        taxonomy = {
            str(native_id): str(name) for native_id, name in taxonomy_value.items()
        }
        expected_taxonomy = {
            native_id: str(spec["name"])
            for native_id, spec in adapter.COURTS.items()
            if collection in spec["collections"]
        }
        if (
            not taxonomy
            or not set(taxonomy) <= set(expected_taxonomy)
            or any(
                expected_taxonomy[native_id] != name
                for native_id, name in taxonomy.items()
            )
        ):
            raise ValueError("California opinions court taxonomy changed")

        total_count = listing.get("total_count")
        total_pages = listing.get("total_pages")
        visible_count = listing.get("visible_count")
        schema_fingerprint = listing.get("schema_fingerprint")
        page_fingerprint = listing.get("page_fingerprint")
        source_document_sha256 = listing.get("source_document_sha256")
        formats_value = detail.get("formats")
        formats = (
            sorted(str(value) for value in formats_value)
            if isinstance(formats_value, Sequence)
            and not isinstance(formats_value, (str, bytes))
            else []
        )
        if (
            listing.get("state") != "available"
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in (
                    total_count,
                    total_pages,
                    visible_count,
                )
            )
            or not isinstance(schema_fingerprint, str)
            or len(schema_fingerprint) != 64
            or not isinstance(page_fingerprint, str)
            or len(page_fingerprint) != 64
            or not isinstance(source_document_sha256, str)
            or len(source_document_sha256) != 64
            or detail.get("state") != "available"
            or detail.get("publication_status")
            != collection_config["publication_status"]
            or "pdf" not in formats
            or not set(formats) <= {"docx", "pdf"}
            or not isinstance(detail.get("case_number"), str)
            or not detail["case_number"]
            or not isinstance(
                detail.get("source_document_sha256"),
                str,
            )
            or len(str(detail["source_document_sha256"])) != 64
        ):
            raise ValueError("California opinions listing/detail contract changed")
        if feed_totals_value.get(collection) != total_count:
            raise ValueError("California opinions feed total disagrees with listing")

        listing_schema_fingerprints[collection] = schema_fingerprint
        observed_taxonomies[collection] = taxonomy
        rolling_collections[collection] = {
            "total_count": total_count,
            "total_pages": total_pages,
            "visible_count": visible_count,
            "page_fingerprint": page_fingerprint,
            "source_document_sha256": source_document_sha256,
            "source_url": listing.get("source_url"),
            "sample_case_number": detail.get("case_number"),
            "sample_formats": formats,
            "sample_detail_url": detail.get("source_url"),
            "sample_detail_sha256": detail.get("source_document_sha256"),
        }

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "collections": {
            collection: {
                "url": config["url"],
                "publication_status": config["publication_status"],
                "current_window_days": config["window_days"],
                "document_version": config["document_version"],
                "citation_status": config["citation_status"],
                "pdf_path_prefix": config["pdf_path_prefix"],
                "court_taxonomy": {
                    native_id: {
                        "name": spec["name"],
                        "court_id": spec["court_id"],
                    }
                    for native_id, spec in adapter.COURTS.items()
                    if collection in spec["collections"]
                },
            }
            for collection, config in adapter.COLLECTIONS.items()
        },
        "identity": {
            "opinion": [
                "court_id",
                "base_appellate_case_number",
                "opinion_filing_date",
            ],
            "source_visible_opinion_identifier_preserved": True,
            "modified_identifier_crosswalk": (
                "opinion_identifier_to_base_appellate_case_number"
            ),
            "document": ["official_document_path", "format"],
        },
        "scope": {
            "complete_appellate_docket": False,
            "complete_case_index": False,
            "corrected_official_reports_text_included": False,
        },
        "complementary_routes": [
            {
                "url": adapter.APPELLATE_CASE_INFORMATION_URL,
                "role": "older_opinion_and_appellate_case_lookup",
            },
            {
                "url": adapter.OFFICIAL_REPORTS_SEARCH_URL,
                "role": "corrected_and_historical_citable_text",
            },
        ],
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "listing_schema_fingerprints": listing_schema_fingerprints,
        "listing_record_kind": "appellate_opinion_index_entry",
        "detail_record_kind": "appellate_opinion_detail",
        "supported_detail_formats": ["docx", "pdf"],
        "native_page_sizes": list(adapter.PAGE_SIZE_CHOICES),
        "modified_opinion_fields": [
            "appellate_case_number",
            "opinion_identifier",
            "opinion_identifier_suffix",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "opinions_home": adapter.OPINIONS_HOME_URL,
        "collection_urls": {
            collection: config["url"]
            for collection, config in adapter.COLLECTIONS.items()
        },
        "document_path_prefixes": {
            collection: config["pdf_path_prefix"]
            for collection, config in adapter.COLLECTIONS.items()
        },
        "detail_path": (
            "/opinion/{published|unpublished}/{decision_date}/{opinion_identifier}"
        ),
        "document_formats": ["pdf", "docx"],
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return replace(
        observation,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "requests_made": 4,
            "stable_contract": stable_contract,
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": stable_schema_sha256,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "collections": rolling_collections,
                "observed_taxonomies": observed_taxonomies,
                "adapter_stable_contract_fingerprint": record[
                    "stable_contract_fingerprint"
                ],
                "live_state_fingerprint": record["live_state_fingerprint"],
            },
        },
    )


def probe_california_court_directory(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the complete California county-court directory contract."""

    adapter = query_california_court_directory
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.DIRECTORY_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "California court-directory probe expected one contract record"
        )
    record = dict(result.records[0])
    sentinels = record.get("sentinels")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("county_count") != len(adapter.COUNTY_FIPS)
        or set(record.get("appellate_districts") or ()) != set(range(1, 7))
        or not isinstance(record.get("schema_fingerprint"), str)
        or len(str(record["schema_fingerprint"])) != 64
        or not isinstance(record.get("snapshot_fingerprint"), str)
        or len(str(record["snapshot_fingerprint"])) != 64
        or not isinstance(sentinels, Mapping)
        or set(sentinels) != {"Los Angeles", "San Mateo"}
    ):
        raise ValueError("California court-directory probe contract changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "county_count": len(adapter.COUNTY_FIPS),
        "county_geoids": sorted(adapter.COUNTY_FIPS.values()),
        "route_fields": [name for name, _index in adapter.ROUTE_FIELDS],
        "appellate_districts": list(range(1, 7)),
        "sentinel_identity": {
            county: adapter.COUNTY_FIPS[county]
            for county in ("Los Angeles", "San Mateo")
        },
    }
    schema_contract = {
        "record_kinds": [
            "superior_court_directory_entry",
            "source_discovery_candidate",
            "source_probe",
        ],
        "directory_headers": list(adapter.EXPECTED_HEADERS),
        "directory_identity": ["source_id", "county_fips", "court_id"],
        "published_routes_preserved": True,
        "shared_ingest_semantics": "snapshot_only",
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "directory_url": adapter.DIRECTORY_URL,
        "county_geoids": sorted(adapter.COUNTY_FIPS.values()),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=int(record["county_count"]),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "source_url": record.get("source_url"),
                "schema_fingerprint": record["schema_fingerprint"],
                "snapshot_fingerprint": record["snapshot_fingerprint"],
                "sentinels": _json_ready(sentinels),
            },
        },
    )


def probe_santa_clara_tentative_rulings(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the open department directory and one current ruling PDF."""

    adapter = query_santa_clara_court_records
    client = adapter.SantaClaraCourtClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    started = time.perf_counter()
    try:
        directory = client.departments()
        department = adapter._department(directory, 1)
        ruling_index = client.ruling_artifacts(department)
        if not ruling_index.artifacts:
            raise ValueError(
                "Santa Clara Department 1 no longer publishes a ruling PDF"
            )
        pdf = client.pdf(str(ruling_index.artifacts[0]["source_url"]))
    finally:
        client.close()

    observed_departments = sorted(
        int(record["department"]) for record in directory.records
    )
    if (
        set(observed_departments) != set(adapter.EXPECTED_DEPARTMENTS)
        or len(directory.schema_fingerprint) != 64
        or ruling_index.department != 1
        or len(ruling_index.schema_fingerprint) != 64
        or pdf.media_type != "application/pdf"
        or len(pdf.sha256) != 64
        or not pdf.content.startswith(b"%PDF-")
    ):
        raise ValueError("Santa Clara tentative-ruling probe contract changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA[adapter.TENTATIVE_SOURCE_ID].to_dict(),
        "court_id": adapter.COURT_ID,
        "department_count": len(adapter.EXPECTED_DEPARTMENTS),
        "departments": sorted(adapter.EXPECTED_DEPARTMENTS),
        "department_headers": list(adapter.DEPARTMENT_HEADERS),
        "document_host": "santaclara.courts.ca.gov",
        "document_path_family": "/system/files/tentative-ruling/",
        "publication_state": "current_until_replaced",
    }
    schema_contract = {
        "record_kinds": [
            "tentative_ruling_department",
            "document_artifact",
        ],
        "department_identity": ["source_id", "department"],
        "document_identity": ["source_id", "department", "source_url"],
        "case_projection": False,
        "shared_ingest_semantics": "snapshot_only",
    }
    artifact_identity = {
        "source_id": adapter.TENTATIVE_SOURCE_ID,
        "directory_url": adapter.TENTATIVE_URL,
        "document_path_family": "/system/files/tentative-ruling/",
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.TENTATIVE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(directory.records),
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "department_schema_fingerprint": directory.schema_fingerprint,
                "department_1_artifact_count": len(ruling_index.artifacts),
                "ruling_schema_fingerprint": ruling_index.schema_fingerprint,
                "sample_pdf": {
                    "source_url": pdf.source_url,
                    "sha256": pdf.sha256,
                    "size_bytes": len(pdf.content),
                },
            },
        },
    )


def probe_san_diego_new_filings(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the static five-court-day filing publication family."""

    adapter = query_san_diego_court_index
    client = adapter.NewFilingsClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=_catalog_interval(context.catalog_decision),
    )
    started = time.perf_counter()
    try:
        pages = client.probe()
        request_count = client.request_count
    finally:
        client.close()
    if set(pages) != set(adapter.NEW_FILING_TYPE_CODES):
        raise ValueError("San Diego new-filing case-type routes changed")

    rolling: dict[str, Any] = {}
    result_count = 0
    for case_type in adapter.NEW_FILING_TYPE_CODES:
        page = pages[case_type]
        if (
            page.case_type != case_type
            or not page.partition
            or not isinstance(page.partition_urls, tuple)
            or len(page.schema_fingerprint) != 64
        ):
            raise ValueError("San Diego new-filing page contract changed")
        result_count += len(page.cases)
        rolling[case_type] = {
            "partition": page.partition,
            "last_updated": page.last_updated,
            "case_count": len(page.cases),
            "party_count": len(page.parties),
            "partition_count": len(page.partition_urls),
            "schema_fingerprint": page.schema_fingerprint,
            "source_url": page.source_url,
        }

    official_alternatives = [
        {
            "route_id": route["route_id"],
            "url": route["url"],
            "scope": route["scope"],
        }
        for route in adapter._alternatives()
        if route["official"]
    ]
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "case_types": list(adapter.NEW_FILING_TYPE_CODES),
        "landing_url": adapter.NEW_FILINGS_LANDING_URL,
        "retention_window": "five_court_days",
        "native_partition_traversal": "alphabet_links_from_each_page",
        "official_alternatives": official_alternatives,
    }
    schema_contract = {
        "record_kind": "case",
        "case_identity": ["source_id", "court_id", "raw_case_number"],
        "new_filing_case_fields": [
            "case_number",
            "filing_date",
            "case_type",
            "category",
            "location",
        ],
        "new_filing_party_fields": ["name", "party_type", "case_number"],
        "docket_projection": False,
        "document_projection": False,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "landing_url": adapter.NEW_FILINGS_LANDING_URL,
        "case_type_codes": dict(adapter.NEW_FILING_TYPE_CODES),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.NEW_FILINGS_LANDING_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=result_count,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "request_count": request_count,
                "case_types": rolling,
            },
        },
    )


def probe_wisconsin_court_directory(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe all Wisconsin directory components as one source family."""

    adapter = query_wisconsin_court_directory
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.DIRECTORIES_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Wisconsin court-directory probe expected one contract record")

    record = dict(result.records[0])
    components = record.get("components")
    county_coverage = record.get("county_coverage")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("snapshot_only") is not True
        or record.get("component_count") != len(adapter.COMPONENTS)
        or not isinstance(record.get("record_count"), int)
        or not isinstance(components, Mapping)
        or set(components) != set(adapter.COMPONENTS)
        or not isinstance(county_coverage, Mapping)
        or county_coverage.get("expected_count") != len(adapter.COUNTY_FIPS)
        or set(county_coverage.get("county_geoids") or ())
        != set(adapter.COUNTY_FIPS.values())
    ):
        raise ValueError("Wisconsin court-directory probe contract changed")

    rolling_components: dict[str, Any] = {}
    for component in adapter.COMPONENTS:
        component_record = components[component]
        if (
            not isinstance(component_record, Mapping)
            or component_record.get("status") != "ok"
            or not isinstance(component_record.get("record_count"), int)
            or not isinstance(component_record.get("coverage"), Mapping)
            or not isinstance(component_record.get("schema_fingerprint"), str)
            or len(str(component_record["schema_fingerprint"])) != 64
            or not isinstance(component_record.get("snapshot_fingerprint"), str)
            or len(str(component_record["snapshot_fingerprint"])) != 64
            or not isinstance(component_record.get("source_url"), str)
        ):
            raise ValueError("Wisconsin court-directory component contract changed")
        rolling_components[component] = {
            "record_count": component_record["record_count"],
            "coverage": _json_ready(component_record["coverage"]),
            "schema_fingerprint": component_record["schema_fingerprint"],
            "snapshot_fingerprint": component_record["snapshot_fingerprint"],
            "source_url": component_record["source_url"],
        }

    route_records = adapter.source_routes()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": {
            "jurisdiction_id": adapter.STATE_GEOID,
            "name": "Wisconsin",
            "state_code": adapter.STATE_CODE,
        },
        "components": [
            {
                "component": component,
                "record_kind": adapter.COMPONENT_DEFINITIONS[component]["record_kind"],
                "name": adapter.COMPONENT_DEFINITIONS[component]["name"],
                "url": adapter.COMPONENT_DEFINITIONS[component]["url"],
                "function": adapter.COMPONENT_DEFINITIONS[component]["function"],
            }
            for component in adapter.COMPONENTS
        ],
        "county_identity": {
            "expected_count": len(adapter.COUNTY_FIPS),
            "county_geoids": sorted(adapter.COUNTY_FIPS.values()),
        },
        "complementary_routes": [
            {
                "route_id": route["route_id"],
                "route_kind": route["route_kind"],
                "related_source_id": route.get("related_source_id"),
                "official_url": route["official_url"],
                "function": route["function"],
            }
            for route in route_records
            if route["route_kind"] != "parsed_html_directory_component"
        ],
    }
    schema_contract = {
        "probe_record_kind": "source_probe",
        "normalized_record_kinds": [
            adapter.COMPONENT_DEFINITIONS[component]["record_kind"]
            for component in adapter.COMPONENTS
        ],
        "identity_contract": {
            "county_components": ["directory_component", "county_geoid"],
            "administrative_district": [
                "directory_component",
                "district_number",
            ],
            "appellate_and_state_offices": [
                "directory_component",
                "canonical_ref",
            ],
            "source_component_identity_preserved": True,
            "shared_ingest_semantics": "snapshot_only",
        },
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "directory_index_url": adapter.DIRECTORIES_URL,
        "component_urls": {
            component: adapter.COMPONENT_DEFINITIONS[component]["url"]
            for component in adapter.COMPONENTS
        },
        "county_geoids": sorted(adapter.COUNTY_FIPS.values()),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=int(record["record_count"]),
        details={
            **dict(observation.details),
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "record_count": record["record_count"],
                "components": rolling_components,
                "county_coverage": _json_ready(county_coverage),
            },
        },
    )


def probe_washington_court_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one directly integrated Washington court component."""

    adapter = query_washington_courts
    supported = {
        adapter.DIRECTORY_SOURCE_ID,
        adapter.OPINIONS_SOURCE_ID,
    }
    if context.source_id not in supported:
        raise ValueError(
            "Washington court monitor supports only the directory and "
            "appellate-opinion components"
        )

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--component",
            context.source_id,
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    component = adapter.COMPONENTS[context.source_id]
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=component.base_url,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Washington court component probe expected one health record")

    record = dict(result.records[0])
    operations_value = record.get("operations")
    evidence_value = record.get("evidence")
    if (
        record.get("record_kind") != "source_health_check"
        or record.get("source_id") != context.source_id
        or record.get("component_source_id") != context.source_id
        or record.get("adapter_family") != adapter.ADAPTER_FAMILY
        or record.get("status") != "ok"
        or not isinstance(operations_value, Mapping)
        or not isinstance(evidence_value, Mapping)
    ):
        raise ValueError("Washington court component probe contract changed")

    operations = {str(key): str(value) for key, value in operations_value.items()}
    evidence = dict(evidence_value)
    if context.source_id == adapter.DIRECTORY_SOURCE_ID:
        expected_operation_keys = {
            "county_index",
            "organization_detail",
            "pdf",
            "person_search",
        }
        expected_evidence_keys = {
            "county_count",
            "sentinel_org_heading",
            "pdf_bytes",
            "pdf_sha256",
            "pdf_matches_observed_sentinel",
        }
        if (
            set(operations) != expected_operation_keys
            or set(evidence) != expected_evidence_keys
            or not isinstance(evidence.get("county_count"), int)
            or int(evidence["county_count"]) < 1
            or not isinstance(evidence.get("sentinel_org_heading"), str)
            or not evidence["sentinel_org_heading"].strip()
        ):
            raise ValueError("Washington court-directory probe shape changed")
        normalized_record_kinds = [
            "court_directory_county",
            "court_directory_person",
            "court_directory_organization",
            "court_directory_pdf_artifact",
        ]
        identity_contract = {
            "county": ["county_name", "organization_ids"],
            "person": ["person_id", "organization_id"],
            "organization": ["organization_id"],
            "snapshot": ["sha256"],
            "shared_ingest_semantics": "snapshot_only",
        }
        artifact_identity = {
            "source_id": context.source_id,
            "sentinel_organization_id": adapter.KNOWN_DIRECTORY_ORG_ID,
            "sentinel_organization_url": (
                f"{adapter.DIRECTORY_HOME_URL}orgs/"
                f"{adapter.KNOWN_DIRECTORY_ORG_ID}.html"
            ),
            "county_index_url": adapter.DIRECTORY_COUNTY_URL,
            "directory_pdf_url": adapter.DIRECTORY_PDF_URL,
        }
        alternative_ids = (
            adapter.CASE_DISCOVERY_SOURCE_ID,
            adapter.CURRENT_ROUTES_SOURCE_ID,
            adapter.JISLINK_SOURCE_ID,
            adapter.DATA_PRODUCTS_SOURCE_ID,
            adapter.DIGITAL_ARCHIVES_SOURCE_ID,
        )
    else:
        expected_operation_keys = {
            "rss",
            "information_sheet",
            "pdf",
            "by_year_enumeration",
            "general_search",
        }
        expected_evidence_keys = {
            "feed_item_count",
            "sentinel_case_number",
            "pdf_bytes",
            "pdf_sha256",
            "pdf_matches_observed_sentinel",
        }
        if (
            set(operations) != expected_operation_keys
            or set(evidence) != expected_evidence_keys
            or not isinstance(evidence.get("feed_item_count"), int)
            or int(evidence["feed_item_count"]) < 0
            or evidence.get("sentinel_case_number") != adapter.KNOWN_OPINION_CASE
        ):
            raise ValueError("Washington appellate-opinion probe shape changed")
        normalized_record_kinds = [
            "appellate_opinion",
            "appellate_opinion_information",
            "appellate_opinion_pdf_artifact",
        ]
        identity_contract = {
            "publication_occurrence": [
                "opinion_filename",
                "source_occurrence",
            ],
            "case": ["court", "case_number"],
            "document": ["official_pdf_path", "sha256"],
            "multi_docket_policy": "one case projection per published docket",
        }
        artifact_identity = {
            "source_id": context.source_id,
            "sentinel_case_number": adapter.KNOWN_OPINION_CASE,
            "sentinel_opinion_filename": adapter.KNOWN_OPINION_FILENAME,
            "information_sheet_url": (
                f"{adapter.OPINIONS_INDEX_URL}?"
                "fa=opinions.showOpinion&filename="
                f"{adapter.KNOWN_OPINION_FILENAME}"
            ),
            "official_pdf_url": (f"{adapter.OPINIONS_PDF_BASE}883666.pdf"),
        }
        alternative_ids = (
            adapter.APPELLATE_DOCUMENTS_SOURCE_ID,
            adapter.APPELLATE_COMPLEMENTS_SOURCE_ID,
            adapter.CASE_DISCOVERY_SOURCE_ID,
            adapter.CURRENT_ROUTES_SOURCE_ID,
            adapter.JISLINK_SOURCE_ID,
            adapter.DIGITAL_ARCHIVES_SOURCE_ID,
        )

    pdf_bytes = evidence.get("pdf_bytes")
    pdf_sha256 = evidence.get("pdf_sha256")
    if (
        not isinstance(pdf_bytes, int)
        or pdf_bytes < 5
        or not isinstance(pdf_sha256, str)
        or len(pdf_sha256) != 64
        or not isinstance(
            evidence.get("pdf_matches_observed_sentinel"),
            bool,
        )
    ):
        raise ValueError("Washington court PDF probe evidence changed")

    required_operations = expected_operation_keys - {"general_search"}
    unavailable_operations = sorted(
        operation
        for operation in required_operations
        if operations.get(operation) != "ok"
    )
    probe_status = observation.status
    probe_error = observation.error
    if unavailable_operations:
        probe_status = ResultStatus.PARTIAL.value
        probe_error = "Washington court component operations unavailable: " + ", ".join(
            unavailable_operations
        )

    stable_contract = {
        "source": adapter.SOURCE_METADATA[context.source_id].to_dict(),
        "jurisdiction": {
            "jurisdiction_id": adapter.STATE_GEOID,
            "name": "Washington",
            "state_code": adapter.STATE_CODE,
        },
        "component": {
            "source_role": component.source_role,
            "base_url": component.base_url,
            "access_state": component.access_state,
            "operations": list(component.operations),
            "relationship": component.relationship,
            "coverage": component.coverage,
        },
        "publisher_and_transport": {
            "authority": "Washington State Judiciary",
            "publisher": ("Washington State Administrative Office of the Courts"),
            "retrieval_transport": "direct official HTTPS",
            "publisher_transport_distinct": False,
            "counts_as_independent_corroboration": False,
        },
        "official_alternatives": [
            {
                "source_id": source_id,
                "source_role": adapter.COMPONENTS[source_id].source_role,
                "base_url": adapter.COMPONENTS[source_id].base_url,
                "access_state": adapter.COMPONENTS[source_id].access_state,
                "relationship": adapter.COMPONENTS[source_id].relationship,
            }
            for source_id in alternative_ids
        ],
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "probe_record_kind": "source_health_check",
        "probe_operation_keys": sorted(expected_operation_keys),
        "probe_evidence_keys": sorted(expected_evidence_keys),
        "normalized_record_kinds": normalized_record_kinds,
        "identity_contract": identity_contract,
    }
    return replace(
        observation,
        status=probe_status,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "checked_at": record.get("checked_at"),
                "operations": operations,
                "evidence": _json_ready(evidence),
            },
        },
        error=probe_error,
    )


def probe_new_jersey_tax_court(
    context: ProbeContext,
) -> ProbeObservation:
    """Traverse both current reports while keeping release churn out of hashes."""

    adapter = query_new_jersey_tax_court
    args = adapter.build_parser().parse_args(
        [
            "validate",
            "--dataset",
            "both",
            "--timeout",
            str(context.timeout),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.S3_LIST_URL,
        started=started,
    )
    if not result.records:
        return observation

    records_by_dataset: dict[str, dict[str, Any]] = {}
    for value in result.records:
        record = dict(value)
        dataset = record.get("dataset")
        workbook = record.get("workbook")
        artifact = record.get("artifact")
        validation = record.get("validation")
        if (
            record.get("record_type") != "workbook_validation"
            or not isinstance(dataset, Mapping)
            or not isinstance(workbook, Mapping)
            or not isinstance(artifact, Mapping)
            or not isinstance(validation, Mapping)
        ):
            raise ValueError("New Jersey Tax Court validation record shape changed")
        dataset_id = dataset.get("id")
        spec = adapter.DATASET_SPECS.get(dataset_id)
        raw_headers = workbook.get("raw_headers")
        if (
            spec is None
            or dataset_id in records_by_dataset
            or tuple(raw_headers or ()) not in spec.accepted_headers
            or list(workbook.get("semantic_headers") or [])
            != list(adapter.SEMANTIC_HEADERS)
            or workbook.get("sheet_name") != spec.sheet_name
            or artifact.get("s3_key") != spec.xlsx_key
            or validation.get("complete_workbook_traversal") is not True
            or not isinstance(validation.get("records_traversed"), int)
            or validation["records_traversed"] <= 0
            or validation["records_traversed"] != workbook.get("record_count")
        ):
            raise ValueError(
                "New Jersey Tax Court workbook validation contract changed"
            )
        records_by_dataset[str(dataset_id)] = record
    if set(records_by_dataset) != set(adapter.DATASET_SPECS):
        raise ValueError(
            "New Jersey Tax Court probe did not return both current reports"
        )

    manifest = adapter.source_manifest_record()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "endpoints": {
            "landing": adapter.LANDING_URL,
            "object_manifest": adapter.S3_LIST_URL,
            "artifact_root": adapter.S3_BASE_URL,
        },
        "datasets": manifest["datasets"],
        "operations": manifest["operations"],
        "access_state": manifest["access_state"],
        "join_guidance": manifest["join_guidance"],
        "complementary_routes": manifest["complementary_routes"],
    }
    schema_contract = {
        "record_type": "tax_court_property_case_parcel_row",
        "validation_record_type": "workbook_validation",
        "semantic_headers": list(adapter.SEMANTIC_HEADERS),
        "accepted_raw_headers": {
            dataset_id: [list(headers) for headers in spec.accepted_headers]
            for dataset_id, spec in adapter.DATASET_SPECS.items()
        },
        "accepted_header_aliases": {
            "open": {"Year": "county"},
        },
        "case_fields": [
            "docket_number_raw",
            "docket_number",
            "filing_year",
            "title",
            "entered_date",
        ],
        "property_fields": [
            "county_name",
            "county_fips",
            "block",
            "lot",
            "unit",
            "assessment_year_raw",
            "assessment_year",
        ],
        "source_record_identity_fields": [
            "artifact_sha256",
            "worksheet_member",
            "row_number",
            "row_sha256",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "court_id": adapter.COURT_ID,
        "case_identity": "docket_number_raw",
        "occurrence_identity": [
            "artifact_sha256",
            "worksheet_member",
            "row_number",
            "row_sha256",
        ],
        "current_artifact_keys": sorted(
            spec.xlsx_key for spec in adapter.DATASET_SPECS.values()
        ),
    }
    rolling_observation = {
        dataset_id: {
            "artifact": record["artifact"],
            "raw_headers": record["workbook"]["raw_headers"],
            "header_aliases": record["workbook"]["header_aliases"],
            "validation": record["validation"],
        }
        for dataset_id, record in sorted(records_by_dataset.items())
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(records_by_dataset),
        details={
            **dict(observation.details),
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def probe_new_jersey_tax_court_opinions(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe each publisher/transport operation without hashing index churn."""

    adapter = query_new_jersey_tax_court_opinions
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.PUBLISHED_INDEX_URL,
        started=started,
    )
    if not result.records:
        return observation

    record = dict(result.records[0])
    operations_value = record.get("operations")
    if (
        record.get("record_type") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("publisher_transport_separated") is not True
        or not isinstance(operations_value, Mapping)
    ):
        raise ValueError("New Jersey Tax Court opinion probe contract changed")
    operations = {
        str(key): dict(value)
        for key, value in operations_value.items()
        if isinstance(value, Mapping)
    }
    expected_operations = {
        "published_index_direct",
        "published_index_reader",
        "unpublished_index_direct",
        "unpublished_index_reader",
        "sample_document_direct",
        "sample_document_reader",
    }
    if set(operations) != expected_operations:
        raise ValueError("New Jersey Tax Court opinion probe operation set changed")

    index_contracts: dict[str, dict[str, Any]] = {}
    index_available: dict[str, bool] = {}
    rolling_counts: dict[str, dict[str, Any]] = {}
    for collection in ("published", "unpublished"):
        available: list[dict[str, Any]] = []
        for transport in ("direct", "reader"):
            operation = operations[f"{collection}_index_{transport}"]
            if operation.get("state") != "available":
                continue
            source_url = operation.get("source_url")
            schema_fingerprint = operation.get("schema_fingerprint")
            if (
                source_url != adapter.COLLECTIONS[collection]["url"]
                or not isinstance(schema_fingerprint, str)
                or len(schema_fingerprint) != 64
                or not isinstance(operation.get("visible_count"), int)
                or not isinstance(operation.get("total_count"), int)
                or not isinstance(operation.get("total_pages"), int)
            ):
                raise ValueError(
                    "New Jersey Tax Court opinion index probe shape changed"
                )
            available.append(operation)
        index_available[collection] = bool(available)
        if not available:
            continue
        schema_fingerprints = {
            str(operation["schema_fingerprint"]) for operation in available
        }
        if len(schema_fingerprints) != 1:
            raise ValueError(
                "New Jersey Tax Court opinion transports disagree on index schema"
            )
        selected = available[0]
        index_contracts[collection] = {
            "schema_fingerprint": next(iter(schema_fingerprints)),
            "record_type": "tax_court_opinion_index_entry",
            "publication_status": collection,
        }
        rolling_counts[collection] = {
            "total_count": selected["total_count"],
            "total_pages": selected["total_pages"],
            "visible_count": selected["visible_count"],
        }

    document_available = False
    for transport in ("direct", "reader"):
        operation = operations[f"sample_document_{transport}"]
        if operation.get("state") != "available":
            continue
        source_url = operation.get("source_url")
        if not isinstance(source_url, str):
            raise ValueError(
                "New Jersey Tax Court opinion document probe lacks its source URL"
            )
        adapter._official_document_url(source_url)
        if operation.get("source_media_type") != "application/pdf":
            raise ValueError(
                "New Jersey Tax Court opinion document source media type changed"
            )
        document_available = True

    manifest = adapter.source_manifest_record()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "collections": manifest["collections"],
        "identity": manifest["identity"],
        "pagination": manifest["pagination"],
        "operations": manifest["operations"],
        "transport_roles": {
            "publisher": {
                "authority": "New Jersey Judiciary",
                "index_urls": {
                    key: value["url"] for key, value in adapter.COLLECTIONS.items()
                },
                "document_host": "www.njcourts.gov",
            },
            "reader_relay": {
                "base_url": adapter.READER_BASE_URL,
                "role": "retrieval_and_text_extraction_transport",
                "publisher": False,
                "counts_as_independent_corroboration": False,
                "document_result": "extracted_text_not_original_pdf_bytes",
            },
        },
        "alternative_routes": [
            {key: value for key, value in route.items() if key != "operation_state"}
            for route in manifest["alternative_routes"]
        ],
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "index_contracts": index_contracts,
        "identity_layers": [
            "index_occurrence",
            "official_document",
            "normalized_case_docket",
        ],
        "document_record_type": "tax_court_opinion_document",
        "reader_hash_scope": "reader_extracted_text",
        "direct_hash_scope": "original_pdf_bytes",
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "court_id": adapter.COURT_ID,
        "occurrence_identity": (
            "collection_visible_fields_native_node_and_duplicate_ordinal"
        ),
        "document_identity": "exact_official_new_jersey_courts_url_path",
        "case_identity": "each_normalized_source_visible_docket_number",
        "retrieval_transport_is_not_document_identity": True,
    }
    rolling_observation = {
        "operations": operations,
        "collection_counts": rolling_counts,
        "usable_index_transport": record.get("usable_index_transport"),
        "index_available": index_available,
        "document_available": document_available,
    }

    probe_status = observation.status
    probe_error = observation.error
    if not all(index_available.values()):
        probe_status = ResultStatus.UNAVAILABLE.value
        probe_error = "No tested transport returned both official opinion indexes"
    elif not document_available:
        probe_status = ResultStatus.PARTIAL.value
        probe_error = (
            "Opinion indexes are available but no tested document transport succeeded"
        )

    return replace(
        observation,
        status=probe_status,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": _json_ready(rolling_observation),
        },
        error=probe_error,
    )


def probe_wisconsin_wscca(context: ProbeContext) -> ProbeObservation:
    """Probe one exact appellate case while separating contract from activity."""

    adapter = query_wisconsin_wscca
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--case-number",
            "2025AP000699",
            "--timeout",
            str(context.timeout),
            "--attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.BASE_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_probe"
        or record.get("canonical_case_number") != "2025AP000699"
    ):
        raise ValueError("WSCCA probe returned another case or record kind")

    routes = adapter.source_routes()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "court_ids": [
            adapter.SUPREME_COURT_ID,
            adapter.COURT_OF_APPEALS_ID,
            adapter.APPELLATE_COURTS_ID,
        ],
        "case_identity_field": "raw_case_number",
        "child_identity_fields": {
            "docket_entry": "native_entry_id",
            "document": "native_document_id",
        },
        "component_access": {
            "case_search_and_detail": (
                "browser_public_use_acknowledgment_and_source_validation"
            ),
            "case_rss": "direct_http",
        },
        "complementary_sources": [
            {
                "source_id": route.get("source_id"),
                "operations": route.get("operations"),
                "source_url": route.get("source_url"),
            }
            for route in routes
            if route.get("source_id") != adapter.SOURCE_ID
        ],
        "coverage_semantics": list(adapter.SOURCE_WARNINGS),
    }
    schema_contract = {
        "probe_record_kind": "source_probe",
        "required_probe_fields": [
            "canonical_case_number",
            "case_found",
            "document_count",
            "past_event_count",
            "validation",
        ],
        "normalized_case_record_kinds": [
            "case",
            "docket_entry",
            "document",
            "document_artifact",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel_case_number": "2025AP000699",
        "case_url": f"{adapter.BASE_URL}/case/2025AP000699",
        "case_rss_url": f"{adapter.BASE_URL}/rss/case/2025AP000699",
    }
    rolling_observation = {
        "case_found": record.get("case_found"),
        "past_event_count": record.get("past_event_count"),
        "document_count": record.get("document_count"),
        "validation": record.get("validation"),
        "runtime": record.get("runtime"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1 if record.get("case_found") else 0,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_wisconsin_opinions(context: ProbeContext) -> ProbeObservation:
    """Probe publication indexes, full text, feeds, and an immutable PDF."""

    adapter = query_wisconsin_opinions
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--component",
            "all",
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.OPINIONS_HOME_URL,
        started=started,
    )
    if not result.records:
        return observation
    records = [dict(record) for record in result.records]
    if any(record.get("source_id") != adapter.SOURCE_ID for record in records):
        raise ValueError("Wisconsin opinions probe returned another source")
    by_component = {
        str(record.get("probe_component")): record
        for record in records
        if record.get("probe_component")
    }
    expected_components = {
        "supreme_metadata_index",
        "appeals_metadata_index",
        "supreme_full_text",
        "supreme_rss",
        "appeals_rss",
        "official_pdf",
    }
    if set(by_component) != expected_components:
        raise ValueError(
            "Wisconsin opinions probe component inventory changed; "
            f"observed={sorted(by_component)}"
        )

    routes = adapter.source_routes()
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "metadata_collections": {
            key: {
                "court_id": config.court_id,
                "record_kind": config.record_kind,
                "document_type": config.document_type,
                "expected_headers": list(config.expected_headers),
            }
            for key, config in adapter.COLLECTIONS.items()
        },
        "full_text_collections": {
            key: {
                "court_id": config.court_id,
                "native_collection": config.native_collection,
                "native_filter": config.native_filter,
            }
            for key, config in adapter.FULLTEXT_COLLECTIONS.items()
        },
        "feed_urls": dict(adapter.FEED_URLS),
        "metadata_paging": "one_based_page",
        "full_text_page_size": adapter.FULLTEXT_PAGE_SIZE,
        "join_keys": [
            "normalized_appellate_case_number",
            "native_document_id",
            "public_domain_citation",
        ],
        "complementary_sources": [
            {
                "source_id": route.get("source_id"),
                "relationship": route.get("relationship"),
                "join_keys": route.get("join_keys"),
                "source_url": route.get("source_url"),
            }
            for route in routes
            if route.get("source_id") != adapter.SOURCE_ID
        ],
    }
    schema_contract = {
        component: inferred_schema([record])
        for component, record in sorted(by_component.items())
    }
    supreme = by_component["supreme_metadata_index"]
    appeals = by_component["appeals_metadata_index"]
    pdf = by_component["official_pdf"]
    artifact_identity = {
        "supreme_case_number": supreme.get("normalized_appellate_case_number"),
        "supreme_document_id": (
            dict(supreme.get("document") or {}).get("native_document_id")
        ),
        "appeals_case_number": appeals.get("normalized_appellate_case_number"),
        "appeals_document_id": (
            dict(appeals.get("document") or {}).get("native_document_id")
        ),
        "pdf_document_id": pdf.get("native_document_id"),
        "pdf_document_id_type": pdf.get("native_document_id_type"),
        "pdf_sha256": pdf.get("sha256"),
    }
    rolling_observation = {
        "keyword_total_items": by_component["supreme_full_text"].get(
            "probe_total_items"
        ),
        "feeds": {
            court: {
                "record_count": by_component[f"{court}_rss"].get("record_count"),
                "newest_record": by_component[f"{court}_rss"].get("newest_record"),
            }
            for court in ("supreme", "appeals")
        },
        "pdf_size_bytes": pdf.get("size_bytes"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(records),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


PHILADELPHIA_PROPERTY_PROBE_ENDPOINTS = {
    query_philadelphia_property.SOURCE_ID: (query_philadelphia_property.OPA_LAYER_URL),
    query_philadelphia_property.HISTORY_SOURCE_ID: (
        query_philadelphia_property.CARTO_SQL_URL
    ),
    query_philadelphia_property.DOR_SOURCE_ID: (
        query_philadelphia_property.DOR_LAYER_URL
    ),
}


def probe_philadelphia_property_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify each Philadelphia property component with its native sentinel."""

    started = time.perf_counter()
    network_args = [
        "--timeout",
        str(context.timeout),
        "--minimum-interval",
        str(_catalog_interval(context.catalog_decision)),
        "--retry-attempts",
        str(context.max_attempts),
    ]
    if context.source_id == query_philadelphia_property.SOURCE_ID:
        argv = ["probe", *network_args]
        source = query_philadelphia_property.SOURCE_METADATA
        operation = "opa_current_parcel_sentinel"
        required_fields = query_philadelphia_property.CURRENT_REQUIRED_FIELDS
        identity_fields = ("native_parcel_id", "pin", "registry_number")
    elif context.source_id == query_philadelphia_property.HISTORY_SOURCE_ID:
        argv = [
            "history",
            query_philadelphia_property.PROBE_PARCEL_NUMBER,
            "--limit",
            "1",
            *network_args,
        ]
        source = query_philadelphia_property.HISTORY_SOURCE_METADATA
        operation = "opa_history_parcel_sentinel"
        required_fields = query_philadelphia_property.HISTORY_REQUIRED_FIELDS
        identity_fields = (
            "native_parcel_id",
            "assessment_year",
            "object_id",
        )
    elif context.source_id == query_philadelphia_property.DOR_SOURCE_ID:
        argv = [
            "parcel-shape",
            query_philadelphia_property.PROBE_REGISTRY_NUMBER,
            "--by",
            "registry",
            "--limit",
            "1",
            *network_args,
        ]
        source = query_philadelphia_property.DOR_SOURCE_METADATA
        operation = "dor_registry_polygon_sentinel"
        required_fields = query_philadelphia_property.DOR_REQUIRED_FIELDS
        identity_fields = (
            "map_registry_number",
            "base_registry_number",
            "pin",
        )
    else:
        raise ValueError(
            f"unsupported Philadelphia property source: {context.source_id}"
        )

    args = query_philadelphia_property.build_parser().parse_args(argv)
    result = query_philadelphia_property.execute(args, log_results=False)
    endpoint = PHILADELPHIA_PROPERTY_PROBE_ENDPOINTS[context.source_id]
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if any(record.get("source_id") != context.source_id for record in records):
        raise ValueError("Philadelphia property probe returned another source")

    stable_contract = {
        "source": source.to_dict(),
        "endpoint": endpoint,
        "probe_operation": operation,
        "required_source_fields": list(required_fields),
        "record_identity_fields": list(identity_fields),
        "transport_semantics": (
            "OPA ArcGIS and CARTO/bulk representations of the same OPA "
            "dataset are transport redundancy, not corroboration."
        ),
    }
    schema_contract = {
        "required_source_fields": list(required_fields),
        "record_type": records[0].get("record_type") if records else None,
    }
    artifact_identity = {
        "source_id": context.source_id,
        "probe_operation": operation,
        "sentinel": (
            {field: records[0].get(field) for field in identity_fields}
            if records
            else None
        ),
    }
    rolling_observation = {
        "result_count": len(records),
        "source_snapshots": [
            record.get("source_snapshot")
            for record in records
            if isinstance(record.get("source_snapshot"), Mapping)
        ],
        "observed_schema": inferred_schema(records) if records else None,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_statewide_parcel_source(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify one bounded statewide parcel contract and separate rolling data."""

    if context.source_id == query_wisconsin_parcels.SOURCE_ID:
        adapter = query_wisconsin_parcels
        endpoint = adapter.LAYER_URL
        stable_contract = {
            "source": adapter.SOURCE_METADATA.to_dict(),
            "endpoint": endpoint,
            "required_fields": list(adapter.REQUIRED_FIELDS),
            "release_name_pattern": adapter.RELEASE_NAME_PATTERN.pattern,
            "native_page_size": adapter.DEFAULT_PAGE_SIZE,
            "traversal": "ordered_OBJECTID_keyset_with_count_check",
            "record_identity_fields": [
                "county_geoid",
                "STATEID_or_county_PARCELID",
            ],
            "owner_visibility_states": [
                "published",
                "partially_withheld_by_source",
                "withheld_by_source",
                "not_present_in_dataset",
            ],
            "non_parcel_classification": "known_exact_source_labels",
            "complementary_routes": [
                {
                    "route_id": route.get("route_id"),
                    "url": route.get("url"),
                    "relationship_to_primary": route.get("relationship_to_primary"),
                }
                for route in adapter._alternatives()
            ],
        }
        artifact_identity = {
            "source_id": context.source_id,
            "endpoint": endpoint,
            "sentinel": "first_ordered_OBJECTID_in_current_release",
        }
        expected_record_type = "statewide_annual_parcel_observation"
    elif context.source_id == query_new_jersey_parcels.SOURCE_ID:
        adapter = query_new_jersey_parcels
        endpoint = adapter.ITEM_API_URL
        stable_contract = {
            "source": adapter.SOURCE_METADATA.to_dict(),
            "item_api": adapter.ITEM_API_URL,
            "default_layer": adapter.DEFAULT_LAYER_URL,
            "required_fields": list(adapter.REQUIRED_FIELDS),
            "layer_name": adapter.SOURCE_LAYER_NAME,
            "geometry_type": adapter.SOURCE_GEOMETRY_TYPE,
            "native_page_size": adapter.DEFAULT_PAGE_SIZE,
            "traversal": "ordered_OBJECTID_keyset_with_count_check",
            "record_identity_fields": [
                "county_geoid",
                "PAMS_PIN_or_PIN_NODUP_or_PCL_GUID",
            ],
            "modiv_join": "partial",
            "owner_name_visibility": "redacted_by_source",
            "complementary_sources": [
                {
                    "source_id": route.get("source_id"),
                    "url": route.get("url"),
                    "relationship_to_primary": route.get("relationship_to_primary"),
                }
                for route in adapter._alternative_routes()
            ],
        }
        artifact_identity = {
            "source_id": context.source_id,
            "item_id": adapter.ITEM_ID,
            "sentinel_pin": adapter.PROBE_PIN,
        }
        expected_record_type = "statewide_parcel_modiv_observation"
    else:
        raise ValueError(f"unsupported statewide parcel source: {context.source_id}")

    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args)
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if not records:
        return observation
    record = records[0]
    if (
        record.get("source_id") != context.source_id
        or record.get("record_type") != expected_record_type
    ):
        raise ValueError("statewide parcel probe returned another record type")
    if (
        context.source_id == query_new_jersey_parcels.SOURCE_ID
        and record.get("native_parcel_id") != query_new_jersey_parcels.PROBE_PIN
    ):
        raise ValueError("NJGIN parcel probe returned another parcel")

    snapshot = (
        dict(record["source_snapshot"])
        if isinstance(record.get("source_snapshot"), Mapping)
        else {}
    )
    compatible_schema = snapshot.get("compatible_schema_fingerprint")
    schema_contract = {
        "source_id": context.source_id,
        "required_fields": stable_contract["required_fields"],
        "record_type": expected_record_type,
        "compatible_schema_fingerprint": compatible_schema,
    }
    rolling_observation = {
        "result_count": len(records),
        "canonical_ref": record.get("canonical_ref"),
        "native_parcel_id": record.get("native_parcel_id"),
        "object_id": record.get("object_id"),
        "source_snapshot": snapshot,
        "owner_visibility": (
            record.get("owner_visibility") or record.get("owner_observation")
        ),
        "modiv_join": record.get("modiv_join"),
        "situs_address": record.get("situs_address"),
    }
    return replace(
        observation,
        schema_sha256=(
            str(compatible_schema)
            if isinstance(compatible_schema, str) and len(compatible_schema) == 64
            else sha256_fingerprint(schema_contract)
        ),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(records),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_ohio_licking_auditor_gis(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the Licking Auditor layer, identity state, and exact sentinel."""

    adapter = query_ohio_licking_property
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Licking Auditor GIS monitor received another source")
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LAYER_URL,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if not records:
        return observation
    if len(records) != 1 or records[0].get("source_id") != adapter.SOURCE_ID:
        raise ValueError("Licking Auditor GIS probe returned another source")
    record = records[0]
    if (
        record.get("probe_request_count")
        != adapter.PROBE_EXPECTED_REQUESTS
    ):
        raise ValueError("Licking Auditor GIS probe request contract changed")
    sentinel = record.get("sentinel_occurrence_identity")
    if not isinstance(sentinel, Mapping) or not sentinel.get("native_id"):
        raise ValueError("Licking Auditor GIS sentinel identity is missing")
    if record.get("sentinel_parcel") != adapter.SENTINEL_PARCEL:
        raise ValueError("Licking Auditor GIS parcel sentinel changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "service_item_id": adapter.ITEM_ID,
        "layer_url": adapter.LAYER_URL,
        "layer_name": adapter.MANIFEST.expected_layer_name,
        "required_fields": list(adapter.FIELDS),
        "record_kind": adapter.MANIFEST.record_kind,
        "identity": {
            "occurrence": "GlobalID then OBJECTID",
            "parcel_join": "Parcel when usable",
            "null_parcel_occurrences": "retained without parcel projection",
        },
        "shared_operations": [
            "address",
            "discovery",
            "fid",
            "freshness",
            "geometry",
            "instrument",
            "land-use",
            "legal",
            "mailing",
            "map",
            "owner",
            "parcel",
            "probe",
            "search",
            "situs",
        ],
        "lineage": {
            "ontrac": "same_authority_assessment_route",
            "ogrip": "county_origin_statewide_representation",
            "recorder": "different_official_record_domain",
        },
    }
    schema_fingerprint = record.get("schema_fingerprint")
    schema_contract = {
        "required_fields": list(adapter.FIELDS),
        "record_kind": adapter.MANIFEST.record_kind,
        "schema_fingerprint": schema_fingerprint,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "service_item_id": adapter.ITEM_ID,
        "layer_id": adapter.MANIFEST.layer_id,
        "layer_url": adapter.LAYER_URL,
    }
    rolling_observation = {
        "record_count": record.get("record_count"),
        "null_parcel_occurrence_count": record.get(
            "null_parcel_occurrence_count"
        ),
        "maximum_page_size": record.get("maximum_page_size"),
        "sentinel_parcel": record.get("sentinel_parcel"),
        "sentinel_occurrence_identity": dict(sentinel),
        "warnings": list(result.warnings),
    }
    return replace(
        observation,
        schema_sha256=(
            str(schema_fingerprint)
            if isinstance(schema_fingerprint, str)
            and len(schema_fingerprint) == 64
            else sha256_fingerprint(schema_contract)
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_ohio_franklin_auditor_sales_gis(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify Franklin's canonical Auditor sale layer and rolling coverage."""

    adapter = query_ohio_franklin_sales_gis
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Franklin Auditor Sales GIS monitor received another source")
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LAYER_URL,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if not records:
        return observation
    if len(records) != 1 or records[0].get("source_id") != adapter.SOURCE_ID:
        raise ValueError("Franklin Auditor Sales GIS probe returned another source")
    record = records[0]
    if record.get("probe_request_count") != adapter.PROBE_EXPECTED_REQUESTS:
        raise ValueError("Franklin Auditor Sales GIS probe request contract changed")
    if record.get("layer_id") != 0:
        raise ValueError("Franklin Auditor Sales GIS canonical layer changed")
    sentinel = record.get("sentinel_occurrence_identity")
    if not isinstance(sentinel, Mapping) or not sentinel.get("native_id"):
        raise ValueError("Franklin Auditor Sales GIS sentinel identity is missing")
    identity_audit = record.get("identity_audit")
    if not isinstance(identity_audit, Mapping):
        raise ValueError("Franklin Auditor Sales GIS identity audit is missing")
    total_count = record.get("record_count")
    null_global_ids = identity_audit.get("null_global_id_occurrences")
    distinct_global_ids = identity_audit.get("distinct_global_id_occurrences")
    if (
        not isinstance(total_count, int)
        or not isinstance(null_global_ids, int)
        or not isinstance(distinct_global_ids, int)
        or distinct_global_ids != total_count - null_global_ids
    ):
        raise ValueError(
            "Franklin Auditor Sales GIS GlobalID occurrence identity is not unique"
        )
    rolling_coverage = record.get("rolling_coverage")
    if not isinstance(rolling_coverage, Mapping):
        raise ValueError("Franklin Auditor Sales GIS coverage statistics are missing")

    shared_operations = [
        "address",
        "count",
        "discovery",
        "fid",
        "freshness",
        "geometry",
        "instrument",
        "map",
        "owner",
        "parcel",
        "probe",
        "sale",
        "search",
    ]
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "service_item_id": record.get("service_item_id"),
        "canonical_layer": {
            "id": 0,
            "name": "Sales Details",
            "url": adapter.LAYER_URL,
        },
        "required_fields": list(adapter.FIELDS),
        "identity": {
            "occurrence": (
                "GlobalID then service item, layer, and OBJECTID fallback"
            ),
            "global_id_invariant": (
                "distinct non-null GlobalID count equals total minus null count"
            ),
            "business_event": "ConveyanceNum plus PARCELID",
            "parcel_join": "PARCELID when usable",
        },
        "paging": {
            "order": "OBJECTID ASC",
            "omitted_limit": "exhaustive",
            "bounded_cursor": (
                "query, schema, snapshot count and OBJECTID boundary, and anchor"
            ),
        },
        "renderer_alias_layers": [1, 2, 3, 4],
        "shared_operations": shared_operations,
        "lineage": {
            "auditor_bulk": "same_authority_representation",
            "auditor_property": "same_authority_representation",
            "ogrip": "county_origin_statewide_representation",
            "recorder": "distinct_official_record_domain",
        },
    }
    schema_fingerprint = record.get("schema_fingerprint")
    schema_contract = {
        "required_fields": list(adapter.FIELDS),
        "schema_fingerprint": schema_fingerprint,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "service_item_id": record.get("service_item_id"),
        "layer_id": record.get("layer_id"),
        "layer_url": adapter.LAYER_URL,
    }
    rolling_observation = {
        "record_count": record.get("record_count"),
        "maximum_page_size": record.get("maximum_page_size"),
        "identity_audit": dict(identity_audit),
        "coverage": dict(rolling_coverage),
        "sentinel_occurrence_identity": dict(sentinel),
        "warnings": list(result.warnings),
    }
    return replace(
        observation,
        schema_sha256=(
            str(schema_fingerprint)
            if isinstance(schema_fingerprint, str)
            and len(schema_fingerprint) == 64
            else sha256_fingerprint(schema_contract)
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_ohio_statewide_parcels(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify OGRIP schema, statewide coverage, and county sentinels."""

    adapter = query_ohio_statewide_parcels
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Ohio parcel monitor received an unknown source")
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LAYER_URL,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if not records:
        return observation
    if len(records) != 1 or records[0].get("source_id") != adapter.SOURCE_ID:
        raise ValueError("Ohio parcel probe returned another source contract")
    record = records[0]
    if (
        record.get("county_count") != 88
        or record.get("expected_statewide_county_count") != 88
    ):
        raise ValueError("Ohio parcel probe no longer reports all 88 counties")

    target_rows = record.get("target_counties")
    if not isinstance(target_rows, Sequence) or isinstance(
        target_rows,
        (str, bytes),
    ):
        raise ValueError("Ohio parcel probe lacks target-county observations")
    targets = {
        str(row.get("county_geoid")): dict(row)
        for row in target_rows
        if isinstance(row, Mapping) and row.get("county_geoid")
    }
    if set(targets) != set(adapter.TARGET_COUNTIES):
        raise ValueError("Ohio parcel target-county coverage changed")
    for geoid, expected in adapter.TARGET_COUNTIES.items():
        row = targets[geoid]
        if row.get("sample_state_parcel_id") != expected["sample_state_parcel_id"]:
            raise ValueError(f"Ohio parcel sentinel changed for {geoid}")

    shared_operations = [
        "address",
        "count",
        "discovery",
        "freshness",
        "land-use",
        "map",
        "parcel",
        "probe",
        "search",
    ]
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "item_id": adapter.ITEM_ID,
        "item_url": adapter.ITEM_URL,
        "layer_url": adapter.LAYER_URL,
        "layer_name": adapter.MANIFEST.expected_layer_name,
        "required_fields": list(adapter.FIELDS),
        "record_kind": adapter.MANIFEST.record_kind,
        "record_identity": {
            "parcel": "StateParcelID",
            "county_join": "County plus LocalParcelID",
            "source_occurrence": "GlobalID then OBJECTID",
        },
        "county_contract": {
            "expected_count": 88,
            "target_geoids": sorted(adapter.TARGET_COUNTIES),
        },
        "field_presence": {
            "published": [
                "parcel identifiers",
                "situs and mailing observations",
                "state land-use code",
                "land area",
                "local CAMA route",
                "parcel polygon",
            ],
            "absent": [
                "owner name",
                "assessed value",
                "recorder instrument",
                "tax balance",
            ],
        },
        "shared_operations": shared_operations,
        "complement_roles": [
            "county assessment and parcel detail",
            "county recorder instruments and images",
            "county tax account",
            "foreclosure sale",
            "court filing",
        ],
    }
    schema_fingerprint = record.get("schema_fingerprint")
    schema_contract = {
        "required_fields": list(adapter.FIELDS),
        "record_kind": adapter.MANIFEST.record_kind,
        "schema_fingerprint": schema_fingerprint,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "item_id": adapter.ITEM_ID,
        "layer_id": adapter.MANIFEST.layer_id,
        "layer_url": adapter.LAYER_URL,
    }
    rolling_observation = {
        "county_count": record.get("county_count"),
        "maximum_page_size": record.get("maximum_page_size"),
        "target_counties": [targets[geoid] for geoid in sorted(targets)],
        "warnings": list(result.warnings),
    }
    return replace(
        observation,
        schema_sha256=(
            str(schema_fingerprint)
            if isinstance(schema_fingerprint, str)
            and len(schema_fingerprint) == 64
            else sha256_fingerprint(schema_contract)
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_wyoming_dor_statewide_parcels(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the DOR app-to-layer contract and one exact annual occurrence."""

    adapter = query_wy_dor_parcels
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Wyoming parcel monitor received an unknown source")
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.ROOT_APP_URL,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if not records:
        return observation
    if len(records) != 1 or records[0].get("source_id") != adapter.SOURCE_ID:
        raise ValueError("Wyoming parcel probe returned another source")
    record = records[0]
    probe = record.get("source_probe")
    if not isinstance(probe, Mapping):
        raise ValueError("Wyoming parcel probe lacks its source contract")
    agreement = probe.get("root_application_agreement")
    layer_validation = probe.get("layer_validation")
    if not isinstance(agreement, Mapping) or not isinstance(
        layer_validation, Mapping
    ):
        raise ValueError("Wyoming parcel probe lacks app/layer agreement")
    app_data = agreement.get("app_data")
    app_identity = agreement.get("app_identity")
    parcel_routes = agreement.get("parcel_query_routes")
    if not isinstance(app_data, Mapping) or not isinstance(
        app_identity, Mapping
    ):
        raise ValueError("Wyoming parcel probe has malformed app identity")
    if not isinstance(parcel_routes, Sequence) or isinstance(
        parcel_routes, (str, bytes)
    ):
        raise ValueError("Wyoming parcel probe has malformed app query routes")
    layer_schema = layer_validation.get("schema")
    if not isinstance(layer_schema, Mapping):
        raise ValueError("Wyoming parcel probe has malformed layer schema")

    app_contract = {
        "root_item_id": adapter.ROOT_APP_ITEM_ID,
        "root_item_type": app_identity.get("type"),
        "publisher_account": app_identity.get("owner"),
        "public_access": app_identity.get("access"),
        "application_title": app_data.get("title"),
        "parcel_query_fields": sorted(
            {
                str(field)
                for route in parcel_routes
                if isinstance(route, Mapping)
                for field in (route.get("fields") or [])
            }
        ),
        "parcel_query_route_count": len(
            [
                route
                for route in parcel_routes
                if isinstance(route, Mapping)
            ]
        ),
    }
    layer_contract = {
        "hosted_item_id": adapter.ITEM_ID,
        "layer_id": 0,
        "layer_url": adapter.LAYER_URL,
        "layer_type": layer_schema.get("identity", {}).get("type")
        if isinstance(layer_schema.get("identity"), Mapping)
        else None,
        "object_id_field": "FID",
        "geometry_type": "esriGeometryPolygon",
    }
    schema_contract = {
        "required_fields": layer_schema.get("required_fields"),
        "record_kind": "wy_dor_annual_parcel_geometry_occurrence",
    }
    identity_contract = {
        "annual_business_key_bases": [
            "tax_year_jurisdiction_parcel_account",
            "tax_year_jurisdiction_parcel",
            "tax_year_jurisdiction_account",
        ],
        "release_occurrence": "FID",
        "occurrence_only_when_no_supported_annual_join": True,
        "owner_assertion": "annual_tax_roll_observation",
        "title_or_sale_inference": False,
    }
    paging_contract = {
        "ordering": "FID ASC",
        "supports_pagination": layer_schema.get("supports_pagination"),
        "supports_order_by": layer_schema.get("supports_order_by"),
        "native_page_size": layer_validation.get("native_page_size"),
        "omitted_limit": "all_matching_native_pages",
    }
    stable_fingerprints = {
        "app": sha256_fingerprint(app_contract),
        "layer": sha256_fingerprint(layer_contract),
        "schema": sha256_fingerprint(schema_contract),
        "identity": sha256_fingerprint(identity_contract),
        "paging": sha256_fingerprint(paging_contract),
    }
    rolling_observation = {
        "release_year": record.get("tax_year"),
        "app_subtitle": app_data.get("subtitle"),
        "current_layer_url": agreement.get("implemented_layer_url"),
        "statewide_occurrence_count": probe.get("statewide_occurrence_count"),
        "sentinel_fid": record.get("native_feature_id"),
        "sentinel_owner_names": [
            owner.get("raw_name")
            for owner in record.get("owners", [])
            if isinstance(owner, Mapping) and owner.get("raw_name")
        ],
        "sentinel_assessment": record.get("assessment"),
        "source_row_id": record.get("source_row_id"),
        "source_version": record.get("source_snapshot"),
    }
    return replace(
        observation,
        schema_sha256=stable_fingerprints["schema"],
        artifact_sha256=sha256_fingerprint(stable_fingerprints),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": {
                "app": app_contract,
                "layer": layer_contract,
                "schema": schema_contract,
                "identity": identity_contract,
                "paging": paging_contract,
            },
            "stable_fingerprints": stable_fingerprints,
            "rolling_observation": rolling_observation,
        },
    )


def _probe_ohio_sheriff_realauction_component_open(
    context: ProbeContext,
    *,
    client: Any | None = None,
) -> ProbeObservation:
    """Probe a fixed five-request RealAuction tenant contract."""

    adapter = query_ohio_sheriff_sales
    try:
        tenant = adapter.TENANTS_BY_SOURCE_ID[context.source_id]
    except KeyError as error:
        raise ValueError(
            "Ohio RealAuction monitor received an unknown tenant"
        ) from error
    source_client = client or adapter.OhioRealAuctionClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(0, context.max_attempts - 1),
    )
    started = time.perf_counter()
    sentinel_date = adapter.PROBE_SENTINEL_DATES[tenant.slug]
    sentinel_month = sentinel_date[:7]

    source_client.bootstrap(tenant)
    calendar = source_client.calendar(tenant, sentinel_month)
    calendar_record = next(
        (
            record
            for record in calendar
            if record.get("auction_date") == sentinel_date
        ),
        None,
    )
    if calendar_record is None:
        raise ValueError("RealAuction sentinel disappeared from its calendar")
    preview = source_client._request(
        tenant,
        {
            "zaction": "AUCTION",
            "Zmethod": "PREVIEW",
            "AUCTIONDATE": adapter._date_source_value(sentinel_date),
        },
    )
    preview_soup = adapter.BeautifulSoup(preview.text, "html.parser")
    if (
        preview_soup.select_one(".AuctionNav_Main") is None
        or preview_soup.select_one("#BID_WINDOW_CONTAINER") is None
    ):
        raise ValueError("RealAuction preview contract changed")
    listing_page = source_client._load_page(
        tenant,
        auction_date=sentinel_date,
        area="C",
        page=1,
    )
    if not listing_page.records:
        raise ValueError("RealAuction closed-area sentinel page is empty")
    updates, page_counts = source_client._update(
        tenant,
        listing_page.auction_ids,
    )
    sampled_records = adapter._overlay_updates(
        listing_page.records,
        updates,
    )

    source_contract = adapter._source_record(tenant)
    source_metadata = adapter._source_metadata(tenant).to_dict()
    source_metadata_details = dict(source_metadata.get("metadata") or {})
    source_metadata_details.pop("observed_at", None)
    source_metadata["metadata"] = source_metadata_details
    stable_access = dict(source_contract["access"])
    stable_access.pop("observation", None)
    native_pagination = source_contract["native_pagination"]
    stable_contract = {
        "source": source_metadata,
        "jurisdiction": adapter._jurisdiction(tenant).to_dict(),
        "component": "official_county_realauction_public_listing",
        "tenant": {
            "slug": tenant.slug,
            "host": tenant.base_url,
            "index_url": tenant.index_url,
            "official_info_url": tenant.official_info_url,
            "sale_schedule": source_contract["sale_schedule"],
        },
        "route_templates": source_contract["endpoints"],
        "access_contract": stable_access,
        "native_identity": source_contract["native_identity"],
        "native_pagination": {
            "areas": native_pagination["areas"],
            "page_size": native_pagination["page_size"],
            "page_selector": native_pagination["page_selector"],
            "page_counts": native_pagination["page_counts"],
            "continuation_consistency": native_pagination[
                "continuation_consistency"
            ],
        },
        "public_fields": source_contract["public_fields"],
        "public_field_gaps": source_contract["public_field_gaps"],
        "listing_token_replacements": list(
            adapter._LISTING_TOKEN_REPLACEMENTS
        ),
        "shared_operations": list(
            OHIO_REALAUCTION_SHARED_OPERATIONS
        ),
        "official_alternatives_and_complements": (
            source_contract["official_alternatives_and_complements"]
        ),
        "same_event_join": {
            "keys": ["case_number", "parcel_ids", "auction_date"],
            "identity_preserved": "tenant_and_aid",
            "independent_corroboration": False,
        },
    }
    schema_contract = {
        "record_kind": "sheriff_sale_auction",
        "required_listing_labels": list(adapter.EXPECTED_LISTING_LABELS),
        "listing_schema_fingerprint": adapter.LISTING_SCHEMA_FINGERPRINT,
        "listing_tokens": [
            token for token, _replacement in adapter._LISTING_TOKEN_REPLACEMENTS
        ],
        "status_item_fields": [
            "AID",
            "A",
            "B",
            "P",
            "C",
            "D",
            "SL",
            "ST",
            "SBH",
            "SP",
        ],
        "status_container_fields": [
            "ADATA",
            "AITEM",
            "WM",
            "CM",
            "RA",
            "RR",
            "RW",
            "RC",
        ],
    }
    statuses: dict[str, int] = {}
    for record in sampled_records:
        status = str(record.get("auction_status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    rolling_observation = {
        "sentinel_month": sentinel_month,
        "sentinel_date": sentinel_date,
        "calendar_active_count": calendar_record.get("active_count"),
        "calendar_scheduled_count": calendar_record.get("scheduled_count"),
        "sampled_aids": list(listing_page.auction_ids),
        "sampled_aid_membership_sha256": sha256_fingerprint(
            list(listing_page.auction_ids)
        ),
        "sampled_count": len(sampled_records),
        "source_page_counts": page_counts,
        "status_counts": statuses,
        "amount_observations": [
            {
                "aid": record.get("native_auction_id"),
                "appraised_value_amount": record.get(
                    "appraised_value_amount"
                ),
                "opening_bid_amount": record.get("opening_bid_amount"),
                "deposit_requirement_amount": record.get(
                    "deposit_requirement_amount"
                ),
                "source_reported_bid_amount": record.get(
                    "source_reported_bid_amount"
                ),
                "sold_amount": record.get("sold_amount"),
            }
            for record in sampled_records
        ],
        "final_urls": {
            "calendar": calendar_record.get("source_url"),
            "preview": preview.url,
            "listing": sampled_records[0].get("source_url"),
        },
        "preview_headers": dict(preview.headers),
        "review_observation": {
            "observed_at": source_contract.get("observed_at"),
            "verification": source_contract.get("verification"),
            "access_observation": source_contract["access"].get(
                "observation"
            ),
        },
        "requests_made": getattr(source_client, "request_count", None),
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=tenant.base_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=schema_sha256,
        artifact_sha256=stable_contract_sha256,
        result_count=1,
        details={
            "stable_contract": _json_ready(stable_contract),
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": schema_sha256,
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def probe_ohio_sheriff_realauction_component(
    context: ProbeContext,
    *,
    client: Any | None = None,
) -> ProbeObservation:
    """Run and close one exact-budget RealAuction component probe."""

    adapter = query_ohio_sheriff_sales
    source_client = client or adapter.OhioRealAuctionClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(0, context.max_attempts - 1),
    )
    try:
        observation = _probe_ohio_sheriff_realauction_component_open(
            context,
            client=source_client,
        )
        requests_made = int(getattr(source_client, "request_count", -1))
        if requests_made != 5:
            raise ValueError(
                "Ohio RealAuction component probe request count changed: "
                f"expected 5, observed {requests_made}"
            )
        return observation
    finally:
        close = getattr(source_client, "close", None)
        if callable(close):
            close()


def _probe_licking_foreclosure_archive_open(
    context: ProbeContext,
    *,
    client: Any | None = None,
) -> ProbeObservation:
    """Probe the archive's four fixed JSON representations."""

    adapter = query_licking_foreclosure_archive
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError(
            "Licking foreclosure monitor received an unknown component"
        )
    source_client = client or adapter.LickingForeclosureArchiveClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(0, context.max_attempts - 1),
    )
    started = time.perf_counter()
    inventory = source_client.years()
    full_year = source_client.year(
        adapter.PROBE_YEAR,
        current_archive_year=inventory.current_archive_year,
    )
    rolling = source_client.current(
        current_archive_year=inventory.current_archive_year,
    )
    detail = source_client.case(
        adapter.PROBE_CASE_NUMBER,
        current_archive_year=inventory.current_archive_year,
    )
    if adapter.PROBE_YEAR not in inventory.years:
        raise ValueError("Licking archive probe year disappeared")
    if len(detail) != 1:
        raise ValueError("Licking archive exact-case sentinel changed")
    if not any(
        record.get("case_number") == adapter.PROBE_CASE_NUMBER
        for record in full_year
    ):
        raise ValueError("Licking archive sentinel is absent from its year")

    source_contract = adapter._source_record()
    source_metadata = adapter._source_metadata().to_dict()
    source_metadata_details = dict(source_metadata.get("metadata") or {})
    source_metadata_details.pop("observed_at", None)
    source_metadata["metadata"] = source_metadata_details
    stable_native_identity = {
        "key": source_contract["native_identity"]["key"],
    }
    stable_contract = {
        "source": source_metadata,
        "jurisdiction": adapter._jurisdiction().to_dict(),
        "component": "official_county_foreclosure_archive_json",
        "host": adapter.EXPECTED_HOST,
        "route_templates": source_contract["endpoints"],
        "access_contract": source_contract["access"],
        "native_identity": stable_native_identity,
        "temporal_views": source_contract["temporal_views"],
        "public_fields": source_contract["public_fields"],
        "public_field_gaps": source_contract["public_field_gaps"],
        "null_not_found_behavior": "HTTP 200 JSON null",
        "shared_operations": list(
            LICKING_FORECLOSURE_ARCHIVE_SHARED_OPERATIONS
        ),
        "official_complements": source_contract["official_complements"],
        "realauction_same_event_join": {
            "keys": ["case_number", "parcel_ids", "sale_date"],
            "archive_identity": "case_number",
            "realauction_identity": "tenant_and_aid",
            "relationship": "same_event_candidate",
            "independent_corroboration": False,
        },
    }
    schema_contract = {
        "record_kind": "sheriff_foreclosure_archive_record",
        "required_fields": list(adapter.EXPECTED_FIELDS),
        "schema_fingerprint": adapter.SCHEMA_FINGERPRINT,
        "year_inventory": "nonempty_unique_descending_integer_array",
        "full_year": "complete_json_array_without_server_pagination",
        "exact_case": "object_or_null",
    }
    status_counts: dict[str, int] = {}
    for record in rolling:
        status = str(record.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    rolling_observation = {
        "inventory_years": list(inventory.years),
        "inventory_first_year": min(inventory.years),
        "inventory_latest_year": max(inventory.years),
        "inventory_year_count": len(inventory.years),
        "probe_year": adapter.PROBE_YEAR,
        "probe_year_record_count": len(full_year),
        "probe_year_case_membership_sha256": sha256_fingerprint(
            [record.get("case_number") for record in full_year]
        ),
        "rolling_current_record_count": len(rolling),
        "rolling_status_counts": status_counts,
        "rolling_amount_observations": [
            {
                "case_number": record.get("case_number"),
                "appraised_value_amount": record.get(
                    "appraised_value_amount"
                ),
                "required_deposit_amount": record.get(
                    "required_deposit_amount"
                ),
                "purchase_price_amount": record.get(
                    "purchase_price_amount"
                ),
            }
            for record in rolling
        ],
        "sentinel": {
            "case_number": detail[0].get("case_number"),
            "status": detail[0].get("status"),
            "sale_date": detail[0].get("sale_date"),
            "appraised_value_amount": detail[0].get(
                "appraised_value_amount"
            ),
            "required_deposit_amount": detail[0].get(
                "required_deposit_amount"
            ),
            "purchase_price_amount": detail[0].get(
                "purchase_price_amount"
            ),
        },
        "final_urls": {
            "year_inventory": inventory.source_url,
            "full_year": full_year[0].get("source_url") if full_year else None,
            "rolling_current": (
                rolling[0].get("source_url") if rolling else None
            ),
            "exact_case": detail[0].get("source_url"),
        },
        "review_observation": {
            "observed_at": source_contract.get("observed_at"),
            "native_identity": source_contract.get("native_identity"),
            "inventory_observation": source_contract.get(
                "inventory_observation"
            ),
            "observed_field_notes": source_contract.get(
                "observed_field_notes"
            ),
        },
        "requests_made": getattr(source_client, "request_count", None),
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.BASE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=schema_sha256,
        artifact_sha256=stable_contract_sha256,
        result_count=1,
        details={
            "stable_contract": _json_ready(stable_contract),
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": schema_sha256,
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def probe_licking_foreclosure_archive(
    context: ProbeContext,
    *,
    client: Any | None = None,
) -> ProbeObservation:
    """Run and close the archive's exact four-request probe."""

    adapter = query_licking_foreclosure_archive
    source_client = client or adapter.LickingForeclosureArchiveClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(0, context.max_attempts - 1),
    )
    try:
        observation = _probe_licking_foreclosure_archive_open(
            context,
            client=source_client,
        )
        requests_made = int(getattr(source_client, "request_count", -1))
        if requests_made != 4:
            raise ValueError(
                "Licking foreclosure archive probe request count changed: "
                f"expected 4, observed {requests_made}"
            )
        return observation
    finally:
        close = getattr(source_client, "close", None)
        if callable(close):
            close()


def probe_ohio_pax_recorder_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Ohio recorder component without conflating access routes."""

    adapter = query_ohio_pax_recorders
    if context.source_id not in adapter.QUERY_SOURCE_IDS:
        raise ValueError("Ohio recorder monitor received an unknown component")
    tenant = adapter.TENANTS_BY_QUERY_SOURCE[context.source_id]
    sample_bytes = context.sample_bytes or 4096
    client = adapter.OhioPAXClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        rate_limiter=adapter.MinimumIntervalRateLimiter(
            _catalog_interval(context.catalog_decision)
        ),
    )
    started = time.perf_counter()
    try:
        if context.source_id == adapter.LICKING_SOURCE_ID:
            access = client.entry_access(tenant)
            if access.get("login_required") is not True:
                raise ValueError(
                    "Licking PAX discovery access no longer reports login required"
                )
            stable_contract = {
                "source": adapter.source_metadata(context.source_id).to_dict(),
                "jurisdiction": tenant.jurisdiction.to_dict(),
                "component": "pax_account_discovery_entry",
                "entry_url": tenant.pax_root,
                "record_identity_source_id": adapter.LICKING_SOURCE_ID,
                "exact_representation_source_id": (
                    adapter.LICKING_DETAIL_SOURCE_ID
                ),
                "discovery_access": "account_required",
                "official_alternatives": [
                    dict(value) for value in tenant.complements
                ],
            }
            schema_contract = {
                "entry_fields": sorted(access),
                "required_fields": [
                    "disclaimer_present",
                    "form_action",
                    "hidden_fields",
                    "login_required",
                    "registration_enabled",
                    "version",
                ],
                "record_identity": "instrument_number",
            }
            artifact_identity = {
                "source_id": context.source_id,
                "entry_url": tenant.pax_root,
                "component": "pax_account_discovery_entry",
            }
            rolling_observation = {
                "login_required": access.get("login_required"),
                "registration_enabled": access.get("registration_enabled"),
                "disclaimer_present": access.get("disclaimer_present"),
                "pax_version": access.get("version"),
            }
            expected_requests = 1
        elif context.source_id == adapter.LICKING_DETAIL_SOURCE_ID:
            instrument = adapter.LICKING_DOCUMENT_SENTINEL
            record = client.licking_exact(tenant, instrument)
            if (
                record is None
                or record.get("instrument_number") != instrument
                or record.get("record_identity_source_id")
                != adapter.LICKING_SOURCE_ID
                or record.get("representation_source_id")
                != adapter.LICKING_DETAIL_SOURCE_ID
            ):
                raise ValueError(
                    "Licking exact-detail sentinel identity contract changed"
                )
            sample = client.document_sample(
                tenant,
                instrument,
                sample_bytes=sample_bytes,
            )
            stable_contract = {
                "source": adapter.source_metadata(context.source_id).to_dict(),
                "jurisdiction": tenant.jurisdiction.to_dict(),
                "component": "anonymous_exact_instrument_detail_and_pdf",
                "detail_url_template": tenant.exact_detail_url_template,
                "document_url_template": tenant.exact_document_url_template,
                "record_identity_source_id": adapter.LICKING_SOURCE_ID,
                "representation_source_id": adapter.LICKING_DETAIL_SOURCE_ID,
                "independent_corroboration": False,
                "stable_key": "instrument_number",
            }
            schema_contract = {
                "detail_schema_fingerprint": record.get(
                    "source_response_schema_fingerprint"
                ),
                "record_kind": "recorded_instrument_detail",
                "representation_kind": "county_exact_instrument_html",
                "identity_fields": ["instrument_number"],
                "document_validation": [
                    "PDF signature",
                    "declared media type",
                    "declared response length",
                ],
            }
            artifact_identity = {
                "source_id": context.source_id,
                "record_identity_source_id": adapter.LICKING_SOURCE_ID,
                "sentinel_instrument": instrument,
                "document_route": tenant.exact_document_url_template,
            }
            rolling_observation = {
                "sentinel_instrument": record.get("instrument_number"),
                "recorded_date_iso": record.get("recorded_date_iso"),
                "document_type": record.get("document_type"),
                "page_count": record.get("page_count"),
                "sample_size_bytes": len(sample.content),
                "sample_sha256": hashlib.sha256(sample.content).hexdigest(),
                "sample_headers": {
                    key: sample.headers.get(key)
                    for key in (
                        "content-type",
                        "content-length",
                        "content-range",
                        "etag",
                        "last-modified",
                    )
                    if sample.headers.get(key) is not None
                },
            }
            expected_requests = 2
        else:
            config = client.bootstrap(tenant)
            selectors = adapter.normalize_selectors(
                {"instrument": tenant.sentinel_instrument}
            )
            batch = client.search_detail(
                tenant,
                selectors,
                config,
                first_record=1,
                last_record=config.rows_per_page,
            )
            matches = [
                dict(record)
                for record in batch.records
                if record.get("instrument_number")
                == tenant.sentinel_instrument
            ]
            if len(matches) != 1:
                raise ValueError(
                    "Delaware PAX exact sentinel did not resolve uniquely"
                )
            record = matches[0]
            reference_id = str(record.get("instrument_reference_id") or "")
            if not reference_id:
                raise ValueError(
                    "Delaware PAX sentinel lacks InstrumentReferenceId"
                )
            image = client.image_detail(
                tenant,
                config,
                reference_id=reference_id,
                instrument=tenant.sentinel_instrument,
            )
            if image.get("has_image") is not True:
                raise ValueError(
                    "Delaware PAX sentinel no longer exposes a public image"
                )
            sample = client.document_sample(
                tenant,
                tenant.sentinel_instrument,
                sample_bytes=sample_bytes,
                config=config,
                reference_id=reference_id,
            )
            stable_contract = {
                "source": adapter.source_metadata(context.source_id).to_dict(),
                "jurisdiction": tenant.jurisdiction.to_dict(),
                "component": "anonymous_pax_discovery_detail_and_pdf",
                "endpoints": {
                    "entry": tenant.pax_root,
                    "detail": f"{tenant.pax_root}api/SearchDetail",
                    "image_detail": f"{tenant.pax_root}api/ImageDetail/",
                    "image": f"{tenant.pax_root}api/Image/",
                },
                "record_identity_source_id": adapter.DELAWARE_SOURCE_ID,
                "stable_key": "InstrumentReferenceId",
                "pagination": {
                    "native_page_size_source": "RowsPerPage",
                    "boundaries": ["FirstRecordNum", "LastRecordNum"],
                },
            }
            schema_contract = {
                "detail_schema_fingerprint": record.get(
                    "source_response_schema_fingerprint"
                ),
                "image_schema_fingerprint": image.get(
                    "source_response_schema_fingerprint"
                ),
                "record_kind": "recorded_instrument_detail",
                "identity_fields": [
                    "instrument_reference_id",
                    "instrument_number",
                ],
                "document_validation": [
                    "PDF signature",
                    "declared media type",
                    "declared response length",
                ],
            }
            artifact_identity = {
                "source_id": context.source_id,
                "sentinel_instrument": tenant.sentinel_instrument,
                "sentinel_reference_id": reference_id,
                "document_route": f"{tenant.pax_root}api/Image/",
            }
            rolling_observation = {
                "pax_version": config.version,
                "data_current_through": config.data_current_through,
                "native_rows_per_page": config.rows_per_page,
                "is_guest": config.is_guest,
                "sentinel_instrument": record.get("instrument_number"),
                "sentinel_reference_id": reference_id,
                "document_page_count": image.get("page_count"),
                "sample_size_bytes": len(sample.content),
                "sample_sha256": hashlib.sha256(sample.content).hexdigest(),
                "sample_headers": {
                    key: sample.headers.get(key)
                    for key in (
                        "content-type",
                        "content-length",
                        "content-range",
                        "etag",
                        "last-modified",
                    )
                    if sample.headers.get(key) is not None
                },
            }
            expected_requests = 5

        requests_made = int(client.request_count)
        if requests_made != expected_requests:
            raise ValueError(
                "Ohio recorder component probe request count changed: "
                f"expected {expected_requests}, observed {requests_made}"
            )
        rolling_observation["requests_made"] = requests_made
        return ProbeObservation(
            status=ResultStatus.OK.value,
            endpoint=(
                tenant.exact_detail_url_template
                if context.source_id == adapter.LICKING_DETAIL_SOURCE_ID
                else tenant.pax_root
            ),
            latency_ms=(time.perf_counter() - started) * 1000,
            schema_sha256=sha256_fingerprint(schema_contract),
            artifact_sha256=sha256_fingerprint(stable_contract),
            result_count=1,
            details={
                "stable_contract": _json_ready(stable_contract),
                "schema_contract": schema_contract,
                "artifact_identity": artifact_identity,
                "rolling_observation": rolling_observation,
            },
        )
    finally:
        client.close()


def probe_virginia_statewide_parcels(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify VGIN item resolution, parcel identity, and locality coverage."""

    adapter = query_virginia_parcels
    network_args = [
        "--timeout",
        str(context.timeout),
        "--minimum-interval",
        str(_catalog_interval(context.catalog_decision)),
        "--retry-attempts",
        str(context.max_attempts),
    ]
    started = time.perf_counter()
    results: dict[str, Any] = {}
    for command in ("metadata", "probe", "localities"):
        args = adapter.build_parser().parse_args([command, *network_args])
        result = adapter.execute(args, log_results=False)
        results[command] = result
        if result.status is not ResultStatus.OK:
            observation = _adapter_result_observation(
                result,
                endpoint=adapter.ITEM_API_URL,
                started=started,
            )
            return replace(
                observation,
                details={
                    **dict(observation.details),
                    "failed_operation": command,
                },
            )

    metadata_rows = list(results["metadata"].records)
    parcel_rows = list(results["probe"].records)
    coverage_rows = list(results["localities"].records)
    if not (
        len(metadata_rows) == 1 and len(parcel_rows) == 1 and len(coverage_rows) == 1
    ):
        raise ValueError("VGIN monitor expected one record from each sentinel")

    metadata = dict(metadata_rows[0])
    parcel = dict(parcel_rows[0])
    coverage = dict(coverage_rows[0])
    identity_contract = (
        dict(metadata["identity_contract"])
        if isinstance(metadata.get("identity_contract"), Mapping)
        else {}
    )
    parcel_snapshot = (
        dict(parcel["source_snapshot"])
        if isinstance(parcel.get("source_snapshot"), Mapping)
        else {}
    )
    coverage_snapshot = (
        dict(coverage["source_snapshot"])
        if isinstance(coverage.get("source_snapshot"), Mapping)
        else {}
    )
    schema_fingerprint = metadata.get("schema_fingerprint")
    resolved_layer_url = metadata.get("resolved_layer_url")
    data_fingerprint = metadata.get("data_fingerprint")
    statewide_count = coverage.get("statewide_parcel_count")
    locality_group_count = coverage.get("source_locality_group_count")
    locality_rows = coverage.get("localities")
    contract_checks = {
        "metadata_source": metadata.get("source_id") == adapter.SOURCE_ID,
        "metadata_record_type": metadata.get("record_type") == "source_contract",
        "official_item": metadata.get("official_arcgis_item_id") == adapter.ITEM_ID,
        "required_fields": list(metadata.get("required_fields") or ())
        == list(adapter.REQUIRED_FIELDS),
        "durable_identity": identity_contract.get("durable_source_key") == "VGIN_QPID",
        "transport_identity": identity_contract.get("transport_locator") == "OBJECTID",
        "local_join_fields": list(identity_contract.get("local_join_fields") or ())
        == ["FIPS", "PARCELID", "PTM_ID"],
        "schema_fingerprint": isinstance(schema_fingerprint, str)
        and len(schema_fingerprint) == 64,
        "resolved_layer": isinstance(resolved_layer_url, str)
        and resolved_layer_url.endswith("/FeatureServer/0"),
        "parcel_source": parcel.get("source_id") == adapter.SOURCE_ID,
        "parcel_record_type": parcel.get("record_type") == "parcel_geometry",
        "parcel_sentinel": parcel.get("vgin_qpid") == adapter.PROBE_VGIN_QPID,
        "coverage_source": coverage.get("source_id") == adapter.SOURCE_ID,
        "coverage_record_type": coverage.get("record_type") == "locality_coverage",
        "statewide_count": isinstance(statewide_count, int) and statewide_count > 0,
        "locality_group_count": isinstance(locality_group_count, int)
        and locality_group_count > 0,
        "locality_rows": isinstance(locality_rows, Sequence)
        and not isinstance(locality_rows, (str, bytes)),
        "locality_row_count": (
            isinstance(locality_rows, Sequence)
            and not isinstance(locality_rows, (str, bytes))
            and isinstance(locality_group_count, int)
            and len(locality_rows) == locality_group_count
        ),
    }
    failed_checks = [name for name, passed in contract_checks.items() if not passed]
    if failed_checks:
        raise ValueError(
            "VGIN source, schema, identity, or coverage contract changed: "
            + ", ".join(failed_checks)
        )

    snapshot_keys = (
        "resolved_layer_url",
        "schema_fingerprint",
        "data_fingerprint",
        "arcgis_item_modified_epoch_ms",
    )
    metadata_snapshot = {
        "resolved_layer_url": resolved_layer_url,
        "schema_fingerprint": schema_fingerprint,
        "data_fingerprint": data_fingerprint,
        "arcgis_item_modified_epoch_ms": metadata.get("arcgis_item_modified_epoch_ms"),
    }
    if any(
        parcel_snapshot.get(key) != metadata_snapshot.get(key)
        or coverage_snapshot.get(key) != metadata_snapshot.get(key)
        for key in snapshot_keys
    ):
        raise ValueError("VGIN source changed between monitor operations")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "official_item": {
            "item_id": adapter.ITEM_ID,
            "item_api_url": adapter.ITEM_API_URL,
            "item_page_url": adapter.ITEM_PAGE_URL,
            "resolution": "current FeatureServer resolved from official item",
        },
        "required_fields": list(adapter.REQUIRED_FIELDS),
        "optional_fields": list(adapter.OPTIONAL_FIELDS),
        "identity": {
            "durable_source_key": "VGIN_QPID",
            "transport_locator": "OBJECTID",
            "local_join_fields": ["FIPS", "PARCELID", "PTM_ID"],
        },
        "normalized_record_types": [
            "source_contract",
            "parcel_geometry",
            "locality_coverage",
        ],
        "coverage_roles": [
            "parcel_discovery",
            "parcel_geometry",
            "local_source_routing",
            "locality_freshness",
        ],
        "complementary_routes": [
            {
                key: route.get(key)
                for key in (
                    "source_id",
                    "route_id",
                    "name",
                    "url",
                    "routing_keys",
                    "adds",
                    "relationship_to_primary",
                )
                if route.get(key) is not None
            }
            for route in adapter.alternative_routes()
        ],
    }
    schema_contract = {
        "required_fields": list(adapter.REQUIRED_FIELDS),
        "schema_fingerprint": schema_fingerprint,
        "geometry_type": metadata.get("geometry_type"),
        "object_id_field": metadata.get("object_id_field"),
        "normalized_record_types": stable_contract["normalized_record_types"],
        "identity": stable_contract["identity"],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "official_item_id": adapter.ITEM_ID,
        "durable_source_key": "VGIN_QPID",
        "transport_locator": "OBJECTID",
    }
    rolling_observation = {
        "resolved_layer_url": resolved_layer_url,
        "data_fingerprint": data_fingerprint,
        "arcgis_item_modified_epoch_ms": metadata.get("arcgis_item_modified_epoch_ms"),
        "dataset_statistics": metadata.get("dataset_statistics"),
        "sentinel": {
            "vgin_qpid": parcel.get("vgin_qpid"),
            "object_id": parcel.get("object_id"),
            "locality": parcel.get("jurisdiction"),
            "last_update": parcel.get("source_dates"),
        },
        "coverage": {
            "statewide_parcel_count": coverage.get("statewide_parcel_count"),
            "source_locality_group_count": coverage.get("source_locality_group_count"),
            "observed_county_equivalent_count": coverage.get(
                "observed_county_equivalent_count"
            ),
            "missing_county_equivalent_geoids": coverage.get(
                "missing_county_equivalent_geoids"
            ),
            "incorporated_town_code_count": coverage.get(
                "incorporated_town_code_count"
            ),
            "oldest_locality_latest_update": coverage.get(
                "oldest_locality_latest_update"
            ),
            "newest_locality_latest_update": coverage.get(
                "newest_locality_latest_update"
            ),
        },
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.ITEM_API_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=3,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "warnings": {
                command: list(result.warnings) for command, result in results.items()
            },
        },
    )


def probe_virginia_beach_delinquent_tax(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the daily tax table without hashing its rolling membership."""

    adapter = query_va_beach_delinquent_tax
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--page-size",
            "1",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(
        args,
        access_decision=context.catalog_decision,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.ITEM_API_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Virginia Beach tax probe expected one installment row")

    record = dict(result.records[0])
    source_snapshot = (
        dict(record["source_snapshot"])
        if isinstance(record.get("source_snapshot"), Mapping)
        else {}
    )
    amounts = (
        dict(record["amounts"])
        if isinstance(record.get("amounts"), Mapping)
        else {}
    )
    owner_observation = (
        dict(record["owner_observation"])
        if isinstance(record.get("owner_observation"), Mapping)
        else {}
    )
    gpin = record.get("gpin")
    bill_number = record.get("bill_number")
    installment = record.get("installment")
    tax_year = record.get("tax_year")
    expected_native_event_id = f"{bill_number}:{installment}:{gpin}:{tax_year}"
    minor_fields = (
        "tax_due_minor",
        "penalty_due_minor",
        "interest_due_minor",
        "fee_due_minor",
        "total_due_minor",
    )
    contract_checks = {
        "source_id": record.get("source_id") == adapter.SOURCE_ID,
        "record_kind": record.get("record_kind") == "property_tax_delinquency",
        "record_scope": (
            record.get("record_scope")
            == "delinquent_real_estate_tax_installment"
        ),
        "native_event_identity": (
            record.get("native_event_id") == expected_native_event_id
            and record.get("native_document_id") == expected_native_event_id
        ),
        "parcel_join": (
            isinstance(gpin, str)
            and bool(gpin)
            and record.get("native_parcel_id") == gpin
        ),
        "bill_join": (
            isinstance(bill_number, str)
            and bool(bill_number)
            and record.get("native_account_id") == bill_number
        ),
        "installment": isinstance(installment, str) and bool(installment),
        "tax_year": isinstance(tax_year, int),
        "stable_keys": list(record.get("stable_key_fields") or ())
        == ["bill_number", "installment", "gpin", "tax_year"],
        "adapter_schema": (
            record.get("adapter_schema_fingerprint")
            == adapter.ADAPTER_SCHEMA_FINGERPRINT
        ),
        "response_schema": (
            isinstance(record.get("response_schema_fingerprint"), str)
            and len(record["response_schema_fingerprint"]) == 64
        ),
        "snapshot": (
            isinstance(source_snapshot.get("data_last_edit_epoch_ms"), int)
            and isinstance(source_snapshot.get("data_last_edit_at"), str)
            and source_snapshot.get("update_frequency") == "daily"
        ),
        "no_invented_onset": (
            "event_date" not in record
            and "delinquency_onset_date" not in record
        ),
        "minor_unit_amounts": all(
            isinstance(amounts.get(field_name), int)
            and not isinstance(amounts.get(field_name), bool)
            for field_name in minor_fields
        ),
        "component_reconciliation": (
            amounts.get("component_difference_minor") == 0
            and amounts.get("component_total_minor")
            == amounts.get("total_due_minor")
        ),
        "currency": amounts.get("currency") == "USD",
        "primary_owner_scope": (
            owner_observation.get("role") == "published_primary_owner"
            and owner_observation.get("additional_owners_may_be_omitted") is True
        ),
    }
    failed_checks = [name for name, passed in contract_checks.items() if not passed]
    if failed_checks:
        raise ValueError(
            "Virginia Beach tax source, identity, money, or snapshot contract "
            "changed: " + ", ".join(failed_checks)
        )

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "official_item": {
            "item_id": adapter.ARCGIS_ITEM_ID,
            "organization_id": adapter.ARCGIS_ORG_ID,
            "layer_id": adapter.LAYER_ID,
            "item_api_url": adapter.ITEM_API_URL,
            "open_data_url": adapter.OPEN_DATA_URL,
            "feature_service_url": adapter.FEATURE_SERVICE_URL,
            "layer_url": adapter.LAYER_URL,
        },
        "required_fields": list(adapter.OUT_FIELDS),
        "identity": {
            "occurrence_fields": [
                "Bill_Number",
                "Installment",
                "GPIN",
                "Tax_Year",
            ],
            "parcel_join_fields": ["GPIN", "jurisdiction_geoid"],
            "transport_locator": "OBJECTID",
        },
        "normalized_record_kind": "property_tax_delinquency",
        "money": {
            "currency": "USD",
            "minor_unit": "cent",
            "component_fields": [
                "tax_due_minor",
                "penalty_due_minor",
                "interest_due_minor",
                "fee_due_minor",
            ],
            "total_field": "total_due_minor",
            "component_reconciliation": True,
        },
        "snapshot_semantics": {
            "publication": "current_daily_extract",
            "membership_and_balances_mutable": True,
            "source_snapshot_is_not_delinquency_onset": True,
            "event_date_invented": False,
            "owner_scope": "published_primary_owner",
        },
        "complementary_routes": [
            {
                key: route.get(key)
                for key in (
                    "role",
                    "source_id",
                    "url",
                    "access",
                    "join_keys",
                    "information",
                )
                if route.get(key) is not None
            }
            for route in adapter.RELATED_ROUTES
        ],
    }
    schema_contract = {
        "adapter_schema_fingerprint": adapter.ADAPTER_SCHEMA_FINGERPRINT,
        "response_schema_fingerprint": record["response_schema_fingerprint"],
        "required_fields": list(adapter.OUT_FIELDS),
        "record_kind": "property_tax_delinquency",
        "identity": stable_contract["identity"],
        "money": stable_contract["money"],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "arcgis_item_id": adapter.ARCGIS_ITEM_ID,
        "arcgis_organization_id": adapter.ARCGIS_ORG_ID,
        "layer_id": adapter.LAYER_ID,
        "feature_service_url": adapter.FEATURE_SERVICE_URL,
    }
    rolling_observation = {
        "source_snapshot": source_snapshot,
        "sentinel": {
            "canonical_ref": record.get("canonical_ref"),
            "native_object_id": record.get("native_object_id"),
            "native_event_id": record.get("native_event_id"),
            "gpin": gpin,
            "bill_number": bill_number,
            "installment": installment,
            "tax_year": tax_year,
            "total_due_minor": amounts.get("total_due_minor"),
        },
        "warnings": list(result.warnings),
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return replace(
        observation,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "stable_contract_sha256": stable_contract_sha256,
            "stable_schema_sha256": stable_schema_sha256,
            "rolling_observation": rolling_observation,
        },
    )


def probe_new_york_statewide_parcels(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify all NY parcel components and the public-polygon footprint."""

    adapter = query_ny_statewide_parcels
    args = adapter.build_parser().parse_args(
        [
            "coverage",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    component_rows = list(record.get("component_counts") or ())
    component_by_key = {
        str(row.get("component")): dict(row)
        for row in component_rows
        if isinstance(row, Mapping)
    }
    expected_components = set(adapter.COMPONENTS)
    public_coverage = (
        dict(record["public_polygon_county_coverage"])
        if isinstance(
            record.get("public_polygon_county_coverage"),
            Mapping,
        )
        else {}
    )
    join_keys = list(record.get("cross_component_join_keys") or ())
    if (
        record.get("source_id") != adapter.SOURCE_ID
        or set(component_by_key) != expected_components
        or join_keys != ["SWIS_SBL_ID", "SWIS_PRINT_KEY_ID", "MUNI_PARCEL_ID"]
        or not isinstance(public_coverage.get("county_count"), int)
        or int(public_coverage["county_count"]) <= 0
    ):
        raise ValueError("New York statewide parcel coverage contract changed")

    stable_contract = {
        "source": adapter.source_metadata().to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "components": {
            key: {
                "layer_id": component.layer_id,
                "layer_name": component.layer_name,
                "geometry_type": component.geometry_type,
                "source_role": component.source_role,
                "record_type": component.record_type,
                "required_fields": list(component.required_fields),
            }
            for key, component in adapter.COMPONENTS.items()
        },
        "public_footprint": {
            "layer_id": adapter.FOOTPRINT_COMPONENT.layer_id,
            "layer_name": adapter.FOOTPRINT_COMPONENT.layer_name,
            "required_fields": list(adapter.FOOTPRINT_COMPONENT.required_fields),
        },
        "traversal": "ordered_OBJECTID_keyset_with_count_and_snapshot_checks",
        "cross_component_join_keys": join_keys,
        "complementary_routes": [
            {
                "route_id": route.get("route_id"),
                "url": route.get("url"),
                "relationship_to_primary": route.get("relationship_to_primary"),
            }
            for route in adapter.alternative_routes()
        ],
    }
    schema_contract = {
        "component_schema_fingerprints": {
            key: component_by_key[key].get("schema_fingerprint")
            for key in sorted(component_by_key)
        },
        "component_geometry_types": {
            key: component_by_key[key].get("geometry_type")
            for key in sorted(component_by_key)
        },
        "normalized_record_types": {
            key: adapter.COMPONENTS[key].record_type
            for key in sorted(adapter.COMPONENTS)
        },
        "join_keys": join_keys,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "components": {
            key: {
                "layer_url": component.layer_url,
                "layer_id": component.layer_id,
            }
            for key, component in adapter.COMPONENTS.items()
        },
        "public_footprint_layer_url": adapter.FOOTPRINT_COMPONENT.layer_url,
    }
    rolling_observation = {
        "components": {
            key: {
                field_name: component_by_key[key].get(field_name)
                for field_name in (
                    "record_count",
                    "dataset_title",
                    "assessment_year",
                    "publication_date",
                    "native_max_record_count",
                )
            }
            for key in sorted(component_by_key)
        },
        "public_polygon_county_count": public_coverage.get("county_count"),
        "public_polygon_counties": [
            dict(county)
            for county in list(public_coverage.get("counties") or ())
            if isinstance(county, Mapping)
        ],
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_new_york_salesweb(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify SalesWeb references, a bounded search, and exact sale detail."""

    adapter = query_ny_salesweb
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    references = (
        dict(record["reference_tables"])
        if isinstance(record.get("reference_tables"), Mapping)
        else {}
    )
    bounded_search = (
        dict(record["bounded_search"])
        if isinstance(record.get("bounded_search"), Mapping)
        else {}
    )
    detail = dict(record["detail"]) if isinstance(record.get("detail"), Mapping) else {}
    counts = (
        dict(references["counts"])
        if isinstance(references.get("counts"), Mapping)
        else {}
    )
    if (
        record.get("source_id") != adapter.SOURCE_ID
        or record.get("record_type") != "source_probe"
        or any(
            not isinstance(counts.get(table_name), int) or int(counts[table_name]) <= 0
            for table_name in ("muniRef", "schlRef", "propRef")
        )
        or detail.get("sale_transaction_identity_present") is not True
        or detail.get("swis_print_key_join_present") is not True
    ):
        raise ValueError("New York SalesWeb probe contract changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "application_url": adapter.APP_URL,
        "api_root": adapter.API_ROOT,
        "api_actions": {
            "references": adapter.REFERENCE_ACTION,
            "search": adapter.SEARCH_ACTION,
            "detail": adapter.DETAIL_ACTION,
            "export": adapter.EXPORT_ACTION,
        },
        "required_search_fields": sorted(adapter.SEARCH_REQUIRED_FIELDS),
        "required_detail_fields": sorted(adapter.DETAIL_REQUIRED_FIELDS),
        "required_reference_fields": {
            key: sorted(value)
            for key, value in adapter.REFERENCE_REQUIRED_FIELDS.items()
        },
        "record_identity": "saleTranNmbr",
        "parcel_join": "swisCd + printKey -> SWIS_PRINT_KEY_ID",
        "pagination": "criteria_schema_count_bound_offset_cursor",
        "complementary_routes": [
            {
                "route_id": route.get("route_id"),
                "url": route.get("url"),
                "record_role": route.get("record_role"),
                "join_keys": route.get("join_keys"),
            }
            for route in adapter.alternative_routes()
        ],
    }
    schema_contract = {
        "reference_schema_fingerprint": references.get("schema_fingerprint"),
        "search_schema_fingerprint": bounded_search.get("schema_fingerprint"),
        "detail_schema_fingerprint": detail.get("schema_fingerprint"),
        "normalized_identity_fields": [
            "sale_record_id",
            "native_record_id",
            "property.parcel_identifiers.swis_print_key_id",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "api_root": adapter.API_ROOT,
        "reference_action": adapter.REFERENCE_ACTION,
        "search_action": adapter.SEARCH_ACTION,
        "detail_action": adapter.DETAIL_ACTION,
        "sale_identity_field": "saleTranNmbr",
    }
    rolling_observation = {
        "reference_counts": counts,
        "bounded_search_total": bounded_search.get("reported_total_matches"),
        "sentinel_sale_transaction_number": detail.get(
            "native_sale_transaction_number"
        ),
        "requests_made": record.get("requests_made"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_new_jersey_sr1a(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify SR1A release discovery, ZIP transport, and fixed-width contract."""

    adapter = query_new_jersey_sr1a
    started = time.perf_counter()
    snapshot = adapter.fetch_release_manifest(
        timeout=context.timeout,
        retry_attempts=context.max_attempts,
    )
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--range-bytes",
            str(context.sample_bytes or 64),
            "--timeout",
            str(context.timeout),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    result = adapter.execute(
        args,
        manifest_snapshot=snapshot,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    manifest = (
        dict(record["manifest"]) if isinstance(record.get("manifest"), Mapping) else {}
    )
    artifact_probe = (
        dict(record["probe"]) if isinstance(record.get("probe"), Mapping) else {}
    )
    if manifest.get("source_id") != adapter.SOURCE_ID:
        raise ValueError("New Jersey SR1A probe returned another source")
    if artifact_probe.get("format_hint") != "zip":
        raise ValueError("New Jersey SR1A probe no longer identifies a ZIP")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "listing_url": adapter.LANDING_URL,
        "layout_url": adapter.LAYOUT_URL,
        "release_patterns": [
            adapter._YTD_RE.pattern,
            adapter._ANNUAL_RE.pattern,
        ],
        "schema": adapter.DECLARED_SCHEMA,
        "record_identity_fields": [
            "municipality_code",
            "serial_number",
            "deed_book",
            "deed_page",
            "date_recorded",
        ],
        "release_occurrence_fields": [
            "release_id",
            "archive_sha256",
            "archive_member",
            "row_number",
            "record_sha256",
        ],
        "traversal": "complete_fixed_width_archive_scan_with_artifact_bound_cursor",
        "complementary_sources": [
            {
                "source_id": route.get("source_id"),
                "url": route.get("url"),
                "relationship_to_sr1a": route.get("relationship_to_sr1a"),
            }
            for route in adapter._alternative_routes()
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "dataset_id": adapter.SOURCE_METADATA.dataset_id,
        "selection": "newest_currently_published_release",
        "expected_format": "zip_with_one_fixed_width_text_member",
    }
    rolling_observation = {
        "release_set_fingerprint": snapshot.fingerprint,
        "releases": [
            {
                "release_id": release.release_id,
                "year": release.year,
                "series": release.series,
                "url": release.url,
            }
            for release in snapshot.releases
        ],
        "probed_release_id": record.get("release_id"),
        "probed_release_url": record.get("url"),
        "probe": artifact_probe,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(
            {
                "declared_schema": adapter.DECLARED_SCHEMA,
                "record_identity_fields": stable_contract["record_identity_fields"],
            }
        ),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_palm_beach_official_records(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe deterministic Clerk routes without hashing rolling image state."""

    adapter = query_palm_beach_official_records
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.HOME_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = dict(result.records[0])
    if (
        record.get("source_id") != adapter.SOURCE_ID
        or record.get("record_kind") != "source_health_check"
    ):
        raise ValueError(
            "Palm Beach Official Records probe returned another record type"
        )
    sentinel = (
        dict(record["sentinel"]) if isinstance(record.get("sentinel"), Mapping) else {}
    )
    expected_sentinel = {
        "instrument_number": adapter.SENTINEL_INSTRUMENT,
        "document_id": adapter.SENTINEL_DOCUMENT_ID,
        "book": str(adapter.SENTINEL_BOOK),
        "page": str(adapter.SENTINEL_PAGE),
        "document_type": adapter.SENTINEL_DOC_TYPE,
    }
    if any(sentinel.get(field) != value for field, value in expected_sentinel.items()):
        raise ValueError("Palm Beach Official Records probe returned another sentinel")
    routes = adapter.source_routes()
    complements = [
        {
            "source_id": route.get("source_id"),
            "kind": route.get("kind"),
            "url": route.get("url"),
            "relationship": route.get("relationship"),
            "join_keys": route.get("join_keys"),
        }
        for route in routes["complementary_routes"]
    ]
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "county_geoid": adapter.COUNTY_GEOID,
        "platform_family": "landmark_web_official_records",
        "record_identity_field": "instrument_number",
        "portal_locator_field": "native_document_id",
        "exact_routes": {
            "instrument_number": adapter.DIRECT_CFN_URL,
            "book_page": adapter.DIRECT_BOOK_PAGE_URL,
            "document_information": adapter.DOCUMENT_INFORMATION_URL,
            "document_details": adapter.DOCUMENT_DETAILS_URL,
            "image": adapter.IMAGE_URL,
        },
        "broad_discovery": {
            "mode": "interactive_portal",
            "observed_challenge": "recaptcha",
        },
        "normalized_record_fields": [
            "instrument_number",
            "native_document_id",
            "book",
            "page",
            "recording_date",
            "document_type",
            "consideration",
            "parties",
            "parcel_ids",
            "parcel_ids_normalized",
            "legal_descriptions",
            "image_access",
        ],
        "complementary_sources": complements,
    }
    schema_contract = {
        "record_kind": "recorded_instrument",
        "required_identity_fields": [
            "instrument_number",
            "native_document_id",
        ],
        "normalized_record_fields": stable_contract["normalized_record_fields"],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel": expected_sentinel,
        "image_selector": {
            "portal_document_id": adapter.SENTINEL_DOCUMENT_ID,
            "page_number": 1,
        },
    }
    rolling_observation = {
        "sentinel": sentinel,
        "broad_search_captcha_required": record.get("broad_search_captcha_required"),
        "request_count": record.get("request_count"),
        "observed_routes": record.get("routes"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_denver_county_court(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the live courtroom options and daily-docket table contract."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        courtroom=None,
        court_date=None,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_denver_county_court(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=DENVER_COUNTY_COURT_DOCKET_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if record.get("record_kind") != "source_health_check":
        raise ValueError("Denver County Court probe did not return a health record")
    schema_fingerprint = record.get("schema_fingerprint")
    request_parameters = {
        key: value
        for key, value in dict(record.get("request_parameters") or {}).items()
        if key != "token"
    }
    artifact = {
        "courtrooms": record.get("courtrooms"),
        "table_columns": record.get("table_columns"),
        "captcha_enabled": record.get("captcha_enabled"),
    }
    return replace(
        observation,
        schema_sha256=(
            str(schema_fingerprint) if schema_fingerprint else observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(artifact),
        details={
            **dict(observation.details),
            "courtroom_count": record.get("courtroom_count"),
            "parsed_row_count": record.get("parsed_row_count"),
            "captcha_enabled": record.get("captcha_enabled"),
            "request_parameters": request_parameters,
            "table_columns": record.get("table_columns"),
        },
    )


def probe_delaware_firstmap(context: ProbeContext) -> ProbeObservation:
    """Verify the known FirstMap parcel across polygon and centroid layers."""
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        county=None,
        geometry=False,
        out_sr=4326,
        page_size=2_000,
        max_records=None,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_delaware_firstmap(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=DELAWARE_FIRSTMAP_SERVICE_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    probe = record.get("probe")
    if not isinstance(probe, Mapping):
        raise ValueError("FirstMap probe result lacks sentinel metadata")
    schema_fingerprints = probe.get("schema_fingerprints")
    if not isinstance(schema_fingerprints, Mapping):
        raise ValueError("FirstMap probe result lacks layer schema fingerprints")
    artifact = {
        "canonical_ref": record.get("canonical_ref"),
        "source_feature_ids": record.get("source_feature_ids"),
        "sentinel": probe.get("sentinel"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(dict(schema_fingerprints)),
        artifact_sha256=sha256_fingerprint(artifact),
        details={
            **dict(observation.details),
            "sentinel": probe.get("sentinel"),
            "polygon_feature_count": probe.get("polygon_feature_count"),
            "centroid_feature_count": probe.get("centroid_feature_count"),
            "layer_schema_fingerprints": dict(schema_fingerprints),
        },
    )


def probe_arlington_property(context: ProbeContext) -> ProbeObservation:
    """Verify the known Arlington RPC against the rich property-map layer."""
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        query=None,
        limit=None,
        cursor=None,
        geometry=False,
        page_size=2_000,
        max_records=None,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        output=None,
        json_out=False,
    )
    result = execute_arlington_property(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=ARLINGTON_PROPERTY_LAYER_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    response_schema = record.get("response_schema_fingerprint")
    artifact = {
        "canonical_ref": record.get("canonical_ref"),
        "rpc_number": record.get("rpc_number"),
        "parcel_id": record.get("parcel_id"),
        "object_id": record.get("object_id"),
        "source_last_updated": record.get("source_last_updated"),
    }
    return replace(
        observation,
        schema_sha256=(
            str(response_schema) if response_schema else observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(artifact),
        details={
            **dict(observation.details),
            "rpc_number": record.get("rpc_number"),
            "parcel_id": record.get("parcel_id"),
            "object_id": record.get("object_id"),
            "source_last_updated": record.get("source_last_updated"),
        },
    )


def probe_bexar_historical_courts(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Kofile tenant bootstrap, bounded search, and exact detail."""
    started = time.perf_counter()
    client = KofilePublicSearchClient(
        BEXAR_HISTORICAL_BASE_URL,
        websocket_url=BEXAR_HISTORICAL_WEBSOCKET_URL,
        timeout=context.timeout,
    )
    try:
        bootstrap = client.bootstrap()
        if BEXAR_HISTORICAL_DEPARTMENT not in bootstrap.department_codes:
            raise ValueError(
                "Bexar historical tenant no longer exposes department "
                f"{BEXAR_HISTORICAL_DEPARTMENT}"
            )
        date_range = (
            BEXAR_HISTORICAL_PROBE_DATE_FROM.replace("-", "")
            + ","
            + BEXAR_HISTORICAL_PROBE_DATE_TO.replace("-", "")
        )
        page = client.search(
            department=BEXAR_HISTORICAL_DEPARTMENT,
            limit=1,
            offset=0,
            recorded_date_range=date_range,
            workspace_id="ithildin-bexar-historical-monitor",
        )
        if len(page.records) != 1:
            raise ValueError(
                "Bexar historical bounded search expected one record, "
                f"received {len(page.records)}"
            )
        search_record = page.records[0]
        raw_doc_id = search_record.get(
            "id",
            search_record.get("docId"),
        )
        try:
            doc_id = int(raw_doc_id)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Bexar historical search sentinel lacks a numeric doc_id"
            ) from error
        detail = client.fetch_document(doc_id)
        schema_payload = {
            "bootstrap": {
                "state": inferred_schema([dict(bootstrap.state)]),
                "department_date_ranges": inferred_schema(
                    [dict(bootstrap.department_date_ranges)]
                ),
            },
            "search": inferred_schema(page.records),
            "detail": inferred_schema([dict(detail)]),
        }
        artifact_payload = {
            "tenant_id": bootstrap.tenant_id,
            "department": BEXAR_HISTORICAL_DEPARTMENT,
            "department_date_range": bootstrap.department_date_ranges.get(
                BEXAR_HISTORICAL_DEPARTMENT
            ),
            "probe_range": date_range,
            "probe_range_total": page.total_count,
            "doc_id": doc_id,
            "rs_id": detail.get("rsId"),
            "case_number": detail.get("docNumber"),
            "recorded_date": detail.get("recordedDate"),
            "metadata_version": detail.get("metadataVersion"),
            "document_version": detail.get(
                "docVersion",
                detail.get("version"),
            ),
        }
        return ProbeObservation(
            status=ResultStatus.OK.value,
            endpoint=BEXAR_HISTORICAL_WEBSOCKET_URL,
            latency_ms=(time.perf_counter() - started) * 1000,
            schema_sha256=sha256_fingerprint(schema_payload),
            artifact_sha256=sha256_fingerprint(artifact_payload),
            result_count=1,
            details={
                **artifact_payload,
                "search_response_type": page.response_type,
                "search_offset": page.offset,
                "search_limit": page.limit,
                "requests_made": 3,
            },
        )
    finally:
        client.close()


def probe_texas_tames(context: ProbeContext) -> ProbeObservation:
    """Probe the statewide search form, one exact case, and one public PDF."""

    started = time.perf_counter()
    client = TexasTAMESClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
    )
    try:
        search_probe = client.probe()
        page = client.case(
            TEXAS_TAMES_PROBE_CASE_NUMBER,
            court_code=TEXAS_TAMES_PROBE_COURT_CODE,
        )
        if page is None:
            raise ValueError("Texas TAMES exact-case sentinel no longer resolves")
        documents = [
            document
            for entry in page.docket_entries
            for document in entry.get("documents", ())
            if document.get("native_document_id") == TEXAS_TAMES_PROBE_DOCUMENT_ID
        ]
        if len(documents) != 1:
            raise ValueError(
                "Texas TAMES exact-case sentinel document is missing or ambiguous"
            )
        document = documents[0]
        downloaded = client.download(
            str(document["source_url"]),
            TEXAS_TAMES_PROBE_DOCUMENT_ID,
        )
        normalized = normalize_texas_tames_case(page)
        document_sha256 = hashlib.sha256(downloaded.content).hexdigest()
        schema_payload = {
            "search_form": search_probe["schema_fingerprint"],
            "case_detail": page.schema_fingerprint,
            "normalized_case": inferred_schema([normalized]),
            "document": {
                "media_type": downloaded.media_type,
                "filename_present": downloaded.filename is not None,
            },
        }
        artifact_payload = {
            "case_number": page.case_number,
            "court_code": page.court_code,
            "native_document_id": TEXAS_TAMES_PROBE_DOCUMENT_ID,
            "document_sha256": document_sha256,
            "document_bytes": len(downloaded.content),
            "docket_entry_count": len(page.docket_entries),
            "party_count": len(page.parties),
            "calendar_event_count": len(page.calendar_events),
            "court_count": len(search_probe["court_labels"]),
            "county_option_count": search_probe["county_option_count"],
            "trial_court_option_count": (search_probe["trial_court_option_count"]),
        }
        return ProbeObservation(
            status=ResultStatus.OK.value,
            endpoint=TEXAS_TAMES_SEARCH_URL,
            latency_ms=(time.perf_counter() - started) * 1000,
            schema_sha256=sha256_fingerprint(schema_payload),
            artifact_sha256=document_sha256,
            result_count=1,
            details={
                **artifact_payload,
                "document_media_type": downloaded.media_type,
                "requests_made": 3,
                "refresh": "nightly",
            },
        )
    finally:
        client.close()


def probe_reeves_records(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the Reeves recorder tenant, sentinel search, and exact detail."""
    started = time.perf_counter()
    client = KofilePublicSearchClient(
        REEVES_RECORDS_BASE_URL,
        websocket_url=REEVES_RECORDS_WEBSOCKET_URL,
        timeout=context.timeout,
    )
    try:
        bootstrap = client.bootstrap()
        if REEVES_RECORDS_DEPARTMENT not in bootstrap.department_codes:
            raise ValueError(
                "Reeves recorder tenant no longer exposes department "
                f"{REEVES_RECORDS_DEPARTMENT}"
            )
        page = client.search(
            department=REEVES_RECORDS_DEPARTMENT,
            limit=1,
            offset=0,
            search_value=REEVES_RECORDS_PROBE_INSTRUMENT_NUMBER,
            workspace_id="ithildin-reeves-recorder-monitor",
        )
        if len(page.records) != 1:
            raise ValueError(
                "Reeves recorder sentinel expected one record, "
                f"received {len(page.records)}"
            )
        search_record = page.records[0]
        raw_doc_id = search_record.get(
            "id",
            search_record.get("docId"),
        )
        try:
            doc_id = int(raw_doc_id)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Reeves recorder sentinel lacks a numeric doc_id"
            ) from error
        if doc_id != REEVES_RECORDS_PROBE_DOCUMENT_ID:
            raise ValueError(
                f"Reeves recorder sentinel returned an unexpected doc_id {doc_id}"
            )
        detail = client.fetch_document(doc_id)
        schema_payload = {
            "bootstrap": {
                "state": inferred_schema([dict(bootstrap.state)]),
                "department_date_ranges": inferred_schema(
                    [dict(bootstrap.department_date_ranges)]
                ),
            },
            "search": inferred_schema(page.records),
            "detail": inferred_schema([dict(detail)]),
        }
        artifact_payload = {
            "tenant_id": bootstrap.tenant_id,
            "department": REEVES_RECORDS_DEPARTMENT,
            "department_date_range": bootstrap.department_date_ranges.get(
                REEVES_RECORDS_DEPARTMENT
            ),
            "doc_id": doc_id,
            "rs_id": detail.get("rsId"),
            "instrument_number": detail.get(
                "instrumentNumber",
                detail.get("docNumber"),
            ),
            "recorded_date": detail.get("recordedDate"),
            "metadata_version": detail.get("metadataVersion"),
            "document_version": detail.get(
                "docVersion",
                detail.get("version"),
            ),
        }
        return ProbeObservation(
            status=ResultStatus.OK.value,
            endpoint=REEVES_RECORDS_WEBSOCKET_URL,
            latency_ms=(time.perf_counter() - started) * 1000,
            schema_sha256=sha256_fingerprint(schema_payload),
            artifact_sha256=sha256_fingerprint(artifact_payload),
            result_count=1,
            details={
                **artifact_payload,
                "search_response_type": page.response_type,
                "source_total_count": page.total_count,
                "search_offset": page.offset,
                "search_limit": page.limit,
                "requests_made": 3,
            },
        )
    finally:
        client.close()


GOVOS_RECORDER_EXPECTED_REQUESTS = 6


def probe_govos_recorder(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one configured county-recorder tenant through the shared protocol."""

    tenant = GOVOS_RECORDER_TENANTS.get(context.source_id)
    if tenant is None:
        raise ValueError(f"no GovOS recorder tenant configured for {context.source_id}")
    started = time.perf_counter()
    client = ReevesRecordsClient(
        timeout=context.timeout,
        max_attempts=context.max_attempts,
        tenant=tenant,
    )
    try:
        bootstrap = client.bootstrap()
        if bootstrap.tenant_id != tenant.county_geoid:
            raise KofileSourceChangedError(
                f"{tenant.name} returned a different tenant identity",
                code="tenant_identity_changed",
                retryable=False,
                details={
                    "expected_tenant_id": tenant.county_geoid,
                    "observed_tenant_id": bootstrap.tenant_id,
                },
            )
        missing_departments = sorted(
            set(tenant.supported_departments) - set(bootstrap.department_codes)
        )
        if missing_departments:
            raise KofileSourceChangedError(
                f"{tenant.name} no longer exposes all configured departments",
                code="property_records_department_missing",
                retryable=False,
                details={
                    "expected_departments": list(tenant.supported_departments),
                    "observed_departments": list(bootstrap.department_codes),
                    "missing_departments": missing_departments,
                },
            )
        page = client.search(
            department=tenant.department,
            limit=1,
            offset=0,
            search_value=tenant.probe_instrument_number,
            workspace_id=f"ithildin-{tenant.key}-recorder-monitor",
        )
        if len(page.records) != 1 or page.total_count != 1:
            raise KofileSourceChangedError(
                f"{tenant.name} sentinel expected one record, "
                f"received {len(page.records)} of {page.total_count}",
                code="probe_record_missing",
                retryable=False,
                details={
                    "returned_records": len(page.records),
                    "source_total_count": page.total_count,
                },
            )
        search_record = page.records[0]
        raw_doc_id = search_record.get(
            "id",
            search_record.get("docId"),
        )
        try:
            doc_id = int(raw_doc_id)
        except (TypeError, ValueError) as error:
            raise KofileSourceChangedError(
                f"{tenant.name} sentinel lacks a numeric doc_id",
                code="probe_identity_changed",
                retryable=False,
            ) from error
        if doc_id != tenant.probe_document_id:
            raise KofileSourceChangedError(
                f"{tenant.name} sentinel returned unexpected doc_id {doc_id}",
                code="probe_identity_changed",
                retryable=False,
                details={
                    "expected_doc_id": tenant.probe_document_id,
                    "observed_doc_id": doc_id,
                },
            )
        detail = client.fetch_document(doc_id)
        normalized = normalize_kofile_instrument(
            detail,
            schema=sha256_fingerprint(inferred_schema([dict(detail)])),
            tenant=tenant,
        )
        if normalized["instrument_number"] != tenant.probe_instrument_number:
            raise KofileSourceChangedError(
                f"{tenant.name} sentinel instrument number changed",
                code="probe_identity_changed",
                retryable=False,
            )
        if (
            tenant.probe_page_count is not None
            and normalized["page_count"] != tenant.probe_page_count
        ):
            raise KofileSourceChangedError(
                f"{tenant.name} sentinel page count changed",
                code="probe_page_count_changed",
                retryable=False,
            )
        page_image = client.fetch_page_image(doc_id, 1)
        page_sha256 = hashlib.sha256(page_image.content).hexdigest()
        if (
            tenant.probe_page_sha256 is not None
            and page_sha256 != tenant.probe_page_sha256
        ):
            raise KofileSourceChangedError(
                f"{tenant.name} sentinel page digest changed",
                code="probe_page_digest_changed",
                retryable=False,
            )
        requests_made = int(getattr(client, "request_count", -1))
        if requests_made != GOVOS_RECORDER_EXPECTED_REQUESTS:
            raise KofileSourceChangedError(
                f"{tenant.name} probe transport count changed",
                code="probe_request_contract_changed",
                retryable=False,
                details={
                    "expected_requests": GOVOS_RECORDER_EXPECTED_REQUESTS,
                    "observed_requests": requests_made,
                },
            )
        schema_payload = {
            "bootstrap": {
                "state": inferred_schema([dict(bootstrap.state)]),
                "department_date_ranges": inferred_schema(
                    [dict(bootstrap.department_date_ranges)]
                ),
            },
            "search": inferred_schema(page.records),
            "detail": inferred_schema([dict(detail)]),
            "page_media_type": page_image.media_type,
        }
        artifact_payload = {
            "tenant_id": bootstrap.tenant_id,
            "department": tenant.department,
            "department_codes": list(bootstrap.department_codes),
            "department_date_range": bootstrap.department_date_ranges.get(
                tenant.department
            ),
            "doc_id": doc_id,
            "instrument_number": normalized["instrument_number"],
            "recorded_date": normalized["recording_date"],
            "page_count": normalized["page_count"],
            "page_1_sha256": page_sha256,
            "page_1_size": len(page_image.content),
            "page_1_media_type": page_image.media_type,
        }
        return ProbeObservation(
            status=ResultStatus.OK.value,
            endpoint=tenant.websocket_url,
            latency_ms=(time.perf_counter() - started) * 1000,
            schema_sha256=sha256_fingerprint(schema_payload),
            artifact_sha256=page_sha256,
            result_count=1,
            details={
                **artifact_payload,
                "search_response_type": page.response_type,
                "source_total_count": page.total_count,
                "search_offset": page.offset,
                "search_limit": page.limit,
                "requests_made": requests_made,
            },
        )
    finally:
        client.close()


def probe_texas_supreme_publications(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe stable release-page structure and separate rolling artifact hashes."""

    adapter = query_texas_supreme_publications
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError(
            "Texas Supreme publications monitor received an unknown source"
        )
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--max-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "Texas Supreme publications probe expected one contract record"
        )
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("status") != "ok"
        or record.get("requests_made") != 4
        or record.get("probe_year") != adapter.PROBE_YEAR
        or record.get("probe_release_date") != adapter.PROBE_RELEASE_DATE
    ):
        raise ValueError(
            "Texas Supreme publications probe identity contract changed"
        )
    stable_contract = _json_ready(record.get("stable_contract"))
    schema_fingerprints = _json_ready(record.get("schema_fingerprints"))
    rolling_observation = _json_ready(record.get("rolling_observation"))
    if not isinstance(stable_contract, Mapping):
        raise ValueError(
            "Texas Supreme publications stable contract is missing"
        )
    if (
        not isinstance(schema_fingerprints, Mapping)
        or set(schema_fingerprints) != {"annual_index", "release_page"}
        or not all(
            isinstance(value, str) and len(value) == 64
            for value in schema_fingerprints.values()
        )
    ):
        raise ValueError(
            "Texas Supreme publications schema fingerprints changed"
        )
    if (
        not isinstance(rolling_observation, Mapping)
        or not all(
            isinstance(rolling_observation.get(field), str)
            and len(str(rolling_observation[field])) == 64
            for field in (
                "landing_sha256",
                "annual_index_sha256",
                "release_page_sha256",
                "print_order_pdf_sha256",
            )
        )
        or not isinstance(
            rolling_observation.get("print_order_pdf_bytes"),
            int,
        )
        or rolling_observation["print_order_pdf_bytes"] <= 0
    ):
        raise ValueError(
            "Texas Supreme publications rolling artifact observation changed"
        )
    stable_schema = {
        "record_fields": sorted(record),
        "schema_fingerprint_fields": sorted(schema_fingerprints),
        "rolling_observation_fields": sorted(rolling_observation),
        "release_record_identity": [
            "release_date",
            "raw_case_number",
            "release_occurrence",
        ],
        "document_identity": ["native_document_id", "source_url"],
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(stable_schema)
    return replace(
        observation,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(
            {
                "probe_year": adapter.PROBE_YEAR,
                "probe_release_date": adapter.PROBE_RELEASE_DATE,
                "release_selector": "#oReportDiv",
                "print_order_document_type": "print_order_release",
            }
        ),
        result_count=1,
        details={
            **dict(observation.details),
            "requests_made": 4,
            "stable_contract": dict(stable_contract),
            "stable_contract_sha256": stable_contract_sha256,
            "stable_schema": stable_schema,
            "stable_schema_sha256": stable_schema_sha256,
            "source_schema_fingerprints": dict(schema_fingerprints),
            "rolling_observation": dict(rolling_observation),
            "release_case_count": record.get("release_case_count"),
            "annual_release_count": record.get("annual_release_count"),
            "landing_record_kinds": record.get("landing_record_kinds"),
        },
    )


def probe_texas_rrc_release(
    context: ProbeContext,
) -> ProbeObservation:
    """Fingerprint one official RRC bulk-share listing and preferred release."""

    source_key = TEXAS_RRC_SOURCE_KEYS.get(context.source_id)
    if source_key is None:
        raise ValueError(f"no Texas RRC bulk source key for {context.source_id}")
    started = time.perf_counter()
    session = system_trust_session()
    client = RRCGoDriveClient(
        timeout=context.timeout,
        session=session,
    )
    try:
        entries, _view_state = client.list(source_key)
    finally:
        session.close()
    selected = preferred_texas_rrc_release(source_key, entries)
    contract = TEXAS_RRC_SOURCE_CONTRACTS[source_key]
    schema_payload = {
        "entry_fields": sorted(selected.to_dict()),
        "source_id": contract["source_id"],
        "filename_pattern": contract.get(
            "filename_pattern",
            contract.get("filename_patterns"),
        ),
        "release_kind": contract["release_kind"],
    }
    artifact_payload = {
        "filename": selected.filename,
        "modified_at": selected.modified_at,
        "modified_display": selected.modified_display,
        "size_display": selected.size_display,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=TEXAS_RRC_SHARE_URLS[source_key],
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_payload),
        artifact_sha256=sha256_fingerprint(artifact_payload),
        result_count=len(entries),
        details={
            "source_key": source_key,
            "preferred_release": artifact_payload,
            "listed_release_count": len(entries),
            "requests_made": 1,
            "download_performed": False,
        },
    )


def probe_orange_hearing_calendar(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the official current/future hearing form and result table."""
    started = time.perf_counter()
    client = OrangeCountyCourtsClient(timeout=context.timeout)
    try:
        page = client.probe()
    finally:
        client.close()
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=ORANGE_CALENDAR_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=page.schema_fingerprint,
        result_count=len(page.rows),
        details={
            "source_total_hearings": page.total_count,
            "table_columns": list(page.columns),
            "request_parameters": dict(page.request_parameters or {}),
            "client_side_pagination": True,
            "past_hearings_available": False,
        },
    )


def probe_los_angeles_civil(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the civil Case Summary and tentative-ruling contracts."""

    started = time.perf_counter()
    client = LosAngelesCourtClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    try:
        snapshot = client.probe()
    finally:
        client.close()
    case_summary = snapshot.case_summary
    if (
        case_summary.case_number.casefold()
        != LOS_ANGELES_CIVIL_PROBE_CASE_NUMBER.casefold()
    ):
        raise ValueError(
            "Los Angeles civil sentinel returned an unexpected case number"
        )

    stable_contract = {
        "source": LOS_ANGELES_CIVIL_SOURCE_METADATA.to_dict(),
        "case_search_endpoint": LOS_ANGELES_CIVIL_CASE_SEARCH_URL,
        "tentative_index_endpoint": LOS_ANGELES_CIVIL_TENTATIVE_INDEX_URL,
        "probe_case_number": LOS_ANGELES_CIVIL_PROBE_CASE_NUMBER,
        "representations": [
            "civil_case_summary",
            "civil_tentative_rulings",
        ],
        "coverage_semantics": list(LOS_ANGELES_CIVIL_SOURCE_WARNINGS),
    }
    schema_contract = {
        "case_search": snapshot.case_search.schema_fingerprint,
        "case_summary": case_summary.schema_fingerprint,
        "tentative_index": snapshot.tentative_index.schema_fingerprint,
        "tentative_result": (
            snapshot.tentative_result.schema_fingerprint
            if snapshot.tentative_result
            else None
        ),
    }
    artifact_identity = {
        "source_id": LOS_ANGELES_CIVIL_SOURCE_ID,
        "probe_case_number": LOS_ANGELES_CIVIL_PROBE_CASE_NUMBER,
        "case_search_endpoint": LOS_ANGELES_CIVIL_CASE_SEARCH_URL,
        "tentative_index_endpoint": LOS_ANGELES_CIVIL_TENTATIVE_INDEX_URL,
    }
    rolling_observation = {
        "case_summary_counts": {
            "future_hearings": len(case_summary.future_hearings),
            "parties": len(case_summary.parties),
            "documents": len(case_summary.documents),
            "past_proceedings": len(case_summary.past_proceedings),
            "register_actions": len(case_summary.register_actions),
        },
        "case_summary_response_sha256": case_summary.response_sha256,
        "tentative_selection_count": len(snapshot.tentative_index.selections),
        "tentative_probe_selection": (
            snapshot.tentative_selection.to_dict()
            if snapshot.tentative_selection
            else None
        ),
        "tentative_ruling_count": (
            len(snapshot.tentative_result.rulings) if snapshot.tentative_result else 0
        ),
        "tentative_result_response_sha256": (
            snapshot.tentative_result.response_sha256
            if snapshot.tentative_result
            else None
        ),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=LOS_ANGELES_CIVIL_CASE_SEARCH_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "requests_made": 4,
        },
    )


def probe_los_angeles_name_index(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the paid name-index discovery and recovery contracts."""

    adapter = query_los_angeles_name_index
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        retry_backoff=0.25,
        output=None,
        json_out=False,
    )
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.CIVIL_INDEX_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
    ):
        raise ValueError(
            "Los Angeles name-index probe returned another source or record kind"
        )

    landing = dict(record.get("landing") or {})
    fees = dict(record.get("fees") or {})
    search_form = dict(record.get("search_form") or {})
    guest = dict(record.get("guest") or {})
    services = [
        {
            "name": service.get("name"),
            "url": service.get("url"),
        }
        for service in guest.get("services") or []
        if isinstance(service, Mapping)
    ]
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "endpoints": {
            "civil_index": adapter.CIVIL_INDEX_URL,
            "search": adapter.SEARCH_URL,
            "guest_information": adapter.GUEST_INFORMATION_URL,
            "fee_information": adapter.FEE_INFORMATION_URL,
            "faq": adapter.FAQ_URL,
        },
        "result_fields": list(landing.get("result_fields") or []),
        "search_form": {
            key: search_form.get(key)
            for key in (
                "method",
                "action_url",
                "field_names",
                "remark_max_length",
            )
        },
        "receipt_field_names": list(guest.get("receipt_field_names") or []),
        "guest_services": services,
        "access": dict(record.get("access") or {}),
    }
    schema_contract = {
        "record_schema": inferred_schema([record]),
        "search_form_schema": search_form.get("schema_fingerprint"),
        "guest_schema": guest.get("schema_fingerprint"),
        "stable_contract_schema": inferred_schema([stable_contract]),
    }
    rolling_observation = {
        "coverage": list(landing.get("coverage") or []),
        "updated_daily": landing.get("updated_daily"),
        "archive_url": landing.get("archive_url"),
        "name_search_fees": list(fees.get("name_search_fees") or []),
        "result_availability_statement": guest.get("result_availability_statement"),
        "faq_redo_statement": guest.get("faq_redo_statement"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
            "requests_made": 6,
        },
    )


def probe_los_angeles_assessor_ain(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the exact-AIN Assessor routing representation."""

    adapter = query_los_angeles_ttc
    started = time.perf_counter()
    client = adapter.LosAngelesTTCClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    try:
        attributes = client.assessor_exact(adapter.PROBE_AIN)
    finally:
        client.close()
    if attributes is None:
        raise ValueError("Los Angeles Assessor sentinel AIN returned no parcel")
    if adapter.normalize_ain(str(attributes.get("AIN") or "")) != adapter.PROBE_AIN:
        raise ValueError("Los Angeles Assessor sentinel returned another AIN")

    stable_contract = {
        "source": adapter.ASSESSOR_METADATA.to_dict(),
        "endpoint": adapter.ASSESSOR_QUERY_URL,
        "native_key": "AIN",
        "join_source_ids": [
            adapter.PAYMENT_SOURCE_ID,
            adapter.SALE_SOURCE_ID,
        ],
        "representation": "exact_assessor_parcel_route",
    }
    schema_contract = inferred_schema([dict(attributes)])
    rolling_observation = {
        "sentinel_ain": adapter.PROBE_AIN,
        "object_id": attributes.get("OBJECTID"),
        "roll_year": attributes.get("Roll_Year"),
        "apn": attributes.get("APN"),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.ASSESSOR_QUERY_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
            "requests_made": 1,
        },
    )


def probe_los_angeles_ttc_payment(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify TTC bootstrap, positive-page, and structured empty contracts."""

    adapter = query_los_angeles_ttc
    started = time.perf_counter()
    client = adapter.LosAngelesTTCClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    try:
        bootstrap = client.payment_bootstrap()
        positive = client.payment_page(
            adapter.PROBE_AIN,
            1,
            bootstrap=bootstrap,
        )
        negative = client.payment_page(
            adapter.INVALID_PROBE_AIN,
            1,
            bootstrap=bootstrap,
        )
    finally:
        client.close()
    if positive.no_result or not positive.rows or not negative.no_result:
        raise ValueError("Los Angeles TTC payment sentinel contract changed")

    stable_contract = {
        "source": adapter.PAYMENT_METADATA.to_dict(),
        "landing_endpoint": adapter.PAYMENT_HISTORY_URL,
        "operation_endpoint": adapter.PAYMENT_AJAX_URL,
        "operation_action": adapter.PAYMENT_ACTION,
        "native_key": "AIN",
        "native_pagination": ["page", "totalPages", "totalRecords"],
        "positive_sentinel": adapter.PROBE_AIN,
        "negative_sentinel": adapter.INVALID_PROBE_AIN,
    }
    schema_contract = {
        "bootstrap": bootstrap.schema_fingerprint,
        "payment_page": positive.schema_fingerprint,
        "no_result": negative.schema_fingerprint,
    }
    rolling_observation = {
        "page_one_row_count": len(positive.rows),
        "source_total_records": positive.meta.get("totalRecords"),
        "source_total_pages": positive.meta.get("totalPages"),
        "source_last_updated": positive.meta.get("lastUpdated"),
        "negative_native_state": _json_ready(negative.native_state or {}),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.PAYMENT_HISTORY_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
            "requests_made": 3,
        },
    )


def probe_los_angeles_ttc_sale(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify TTC schedules, artifact index, and a current result PDF."""

    adapter = query_los_angeles_ttc
    started = time.perf_counter()
    client = adapter.LosAngelesTTCClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    try:
        schedules = adapter.parse_auction_schedule_html(
            client.html(adapter.AUCTION_SCHEDULE_URL)
        )
        publications = adapter.parse_publications_html(
            client.html(adapter.AUCTION_CONTACT_URL)
        )
        candidates = [
            artifact
            for artifact in publications
            if artifact.kind == "sale_results_excess_proceeds"
        ]
        if not candidates:
            raise ValueError("Los Angeles TTC published no sale-result artifact")
        latest = max(candidates, key=lambda artifact: artifact.cycle)
        artifact = client.bytes(
            latest.url,
            max_bytes=adapter.DEFAULT_MAX_DOCUMENT_BYTES,
        )
    finally:
        client.close()
    artifact_sha256 = hashlib.sha256(artifact.content).hexdigest()
    sale_rows: list[dict[str, Any]] = []
    extraction_state = "official_pdf_available"
    sale_windows: Mapping[str, Any] = {}
    try:
        parsed_rows, parsed_windows = adapter.parse_sale_results_text(
            adapter.extract_pdf_text(artifact),
            expected_cycle=latest.cycle,
        )
        sale_rows = [
            {
                "ain": row.ain,
                "item": row.item,
                "purchase_price": row.purchase_price,
                "excess_proceeds": row.excess_proceeds,
                "phase": row.phase,
            }
            for row in parsed_rows
        ]
        sale_windows = parsed_windows
        extraction_state = "official_pdf_parsed"
    except adapter.DocumentExtractionUnavailable:
        extraction_state = "official_pdf_available_extractor_missing"

    stable_contract = {
        "source": adapter.SALE_METADATA.to_dict(),
        "schedule_endpoint": adapter.AUCTION_SCHEDULE_URL,
        "publication_index_endpoint": adapter.AUCTION_CONTACT_URL,
        "tax_default_status_endpoint": adapter.AUCTION_NOTICE_URL,
        "excess_proceeds_endpoint": adapter.EXCESS_PROCEEDS_URL,
        "publication_kinds": [
            "sale_results_excess_proceeds",
            "sold_parcels",
        ],
        "native_keys": ["auction_cycle", "sale_phase", "item", "AIN"],
    }
    schema_contract = {
        "auction_schedule": inferred_schema(schedules),
        "publication_index": inferred_schema(
            [publication.to_record() for publication in publications]
        ),
        "sale_result_rows": (
            inferred_schema(sale_rows)
            if sale_rows
            else {
                "expected_fields": [
                    "ain",
                    "item",
                    "purchase_price",
                    "excess_proceeds",
                    "phase",
                ]
            }
        ),
    }
    rolling_observation = {
        "auction_entry_count": len(schedules),
        "auction_cycles": sorted(
            {
                str(record.get("auction_cycle"))
                for record in schedules
                if record.get("auction_cycle")
            }
        ),
        "publication_artifact_count": len(publications),
        "latest_sale_result_cycle": latest.cycle,
        "latest_sale_result_url": latest.url,
        "latest_sale_result_sha256": artifact_sha256,
        "latest_sale_result_size": len(artifact.content),
        "extraction_state": extraction_state,
        "sale_result_row_count": len(sale_rows) if sale_rows else None,
        "sale_windows": _json_ready(sale_windows),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.AUCTION_SCHEDULE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
            "requests_made": 3,
        },
    )


def probe_los_angeles_probate(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the public case, notes-form, and calendar sentinel contracts."""

    started = time.perf_counter()
    client = LosAngelesProbateClient(timeout=context.timeout)
    try:
        snapshot = client.probe()
    finally:
        client.close()
    case_summary = snapshot.case_summary
    if (
        case_summary.case_number.casefold()
        != LOS_ANGELES_PROBATE_PROBE_CASE_NUMBER.casefold()
    ):
        raise ValueError(
            "Los Angeles probate sentinel returned an unexpected case number"
        )
    counts = {
        "future_hearings": len(case_summary.future_hearings),
        "parties": len(case_summary.parties),
        "documents": len(case_summary.documents),
        "past_proceedings": len(case_summary.past_proceedings),
        "register_actions": len(case_summary.register_actions),
    }
    schema = {
        "case_search": snapshot.case_search.schema_fingerprint,
        "case_summary": case_summary.schema_fingerprint,
        "notes_search": snapshot.notes_search.schema_fingerprint,
        "calendar": snapshot.calendar.schema_fingerprint,
    }
    artifact = {
        "case_number": case_summary.case_number,
        "caption": case_summary.case_title,
        "filing_date": case_summary.filing_date,
        "status": case_summary.status,
        "counts": counts,
        "courthouse_options": dict(snapshot.case_search.courthouse_options),
        "calendar_message": snapshot.calendar.message,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=LOS_ANGELES_PROBATE_CASE_SEARCH_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema),
        artifact_sha256=sha256_fingerprint(artifact),
        result_count=1,
        details={
            **artifact,
            "schema_components": schema,
            "requests_made": 5,
        },
    )


def probe_palm_beach_courts(context: ProbeContext) -> ProbeObservation:
    """Verify the public eCaseView guest search controls in one browser session."""
    started = time.perf_counter()
    payload = run_palm_beach_browser_helper(["probe"], context.timeout)
    if not payload.get("ok"):
        raise ValueError("Palm Beach eCaseView probe did not report success")
    case_controls = int(payload.get("case_search_box_count") or 0)
    party_controls = int(payload.get("party_search_box_count") or 0)
    if case_controls < 1 or party_controls < 1:
        raise ValueError("Palm Beach eCaseView guest search controls are incomplete")
    schema = {
        "fields": sorted(payload),
        "case_search_box_count": case_controls,
        "party_search_box_count": party_controls,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=PALM_BEACH_ECASEVIEW_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema),
        result_count=1,
        details={
            "source_url": payload.get("source_url"),
            "title": payload.get("title"),
            "case_search_box_count": case_controls,
            "party_search_box_count": party_controls,
            "browser_session": "headed_guest",
        },
    )


def probe_pima_courts(context: ProbeContext) -> ProbeObservation:
    """Verify the Pima PublicDocs frame and ASP.NET search contract."""
    started = time.perf_counter()
    client = PimaCourtClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=0,
    )
    try:
        form = client.bootstrap()
        request_count = client.request_count
    finally:
        client.close()
    contract = {
        "search_url": form.search_url,
        "hidden_fields": sorted(form.hidden_fields),
        "session_bound_navigation": True,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=PIMA_PUBLICDOCS_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(contract),
        result_count=1,
        details={
            **contract,
            "request_count": request_count,
        },
    )


def probe_franklin_cio(context: ProbeContext) -> ProbeObservation:
    """Verify Franklin CIO with one fixed exact-case continuation sample."""

    adapter = query_ohio_franklin_courts
    started = time.perf_counter()
    client = adapter.FranklinCourtClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=_catalog_interval(context.catalog_decision),
        request_budget=5,
    )
    try:
        snapshot = client.probe_contract(adapter.PROBE_CASE_NUMBER)
    finally:
        client.close()
    if snapshot.request_count != 5:
        raise ValueError(
            "Franklin CIO sentinel did not honor its five-request contract"
        )

    record = dict(snapshot.record)
    parties = [
        dict(value)
        for value in record.get("parties", ())
        if isinstance(value, Mapping)
    ]
    schedule = [
        dict(value)
        for value in record.get("case_schedule", ())
        if isinstance(value, Mapping)
    ]
    docket_entries = [
        dict(value)
        for value in record.get("docket_entries", ())
        if isinstance(value, Mapping)
    ]
    documents = [
        dict(value)
        for value in record.get("documents", ())
        if isinstance(value, Mapping)
    ]

    def field_union(rows: Sequence[Mapping[str, Any]]) -> list[str]:
        return sorted(
            {
                str(key)
                for row in rows
                for key in row
            }
        )

    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "platform_family": adapter.PLATFORM_FAMILY,
        "official_origin": {
            "scheme": urlsplit(adapter.BASE_URL).scheme,
            "host": adapter.OFFICIAL_HOST,
        },
        "routes": {
            "landing": urlsplit(adapter.BASE_URL).path,
            "disclaimer_acceptance": snapshot.disclaimer_path,
            "party_name_search": urlsplit(adapter.NAME_SEARCH_URL).path,
            "exact_case": urlsplit(adapter.CASE_SEARCH_URL).path,
            "docket_continuation": urlsplit(adapter.DOCKET_URL).path,
            "public_document": urlsplit(adapter.DOCUMENT_URL).path,
        },
        "request_contract": [
            {"method": "GET", "role": "landing", "payload_fields": []},
            {
                "method": snapshot.disclaimer_method,
                "role": "disclaimer_acceptance",
                "payload_fields": list(snapshot.disclaimer_field_names),
            },
            {
                "method": "POST",
                "role": "party_name_search",
                "payload_fields": list(snapshot.party_search_field_names),
            },
            {
                "method": "POST",
                "role": "exact_case",
                "payload_fields": list(snapshot.case_search_field_names),
            },
            {
                "method": "POST",
                "role": "first_docket_continuation",
                "payload_fields": list(snapshot.docket_request_field_names),
            },
        ],
        "sentinel": {
            "normalized_case_number": adapter.parse_case_number(
                adapter.PROBE_CASE_NUMBER
            ).normalized,
            "party_case_number": snapshot.party_sentinel_case_number,
            "party_matching_count": snapshot.party_matching_count,
            "party_coverage_complete": snapshot.party_coverage_complete,
            "known_continuation_required": True,
        },
        "pagination": {
            "party_index": {
                "mechanism": "ordered_lower_bound_window",
                "native_cursor": None,
                "completion_evidence": "later_lexical_spillover",
                "adaptive_partitions": ["filed_date", "court_category"],
            },
            "docket": {
                "mechanism": "next_key_post",
                "direction_field": "docketdir",
                "forward_direction_value": "3",
                "normal_case_operation": "until_empty_next_key",
                "monitor_sample": "first_known_continuation_only",
            },
        },
        "identity": {
            "case": ["source_id", "court_id", "normalized_case_number"],
            "docket": [
                "case_number",
                "displayed_fields",
                "detail_fields",
                "duplicate_occurrence",
            ],
            "document": [
                "case_number",
                "fiche",
                "frame",
                "pages_raw",
                "docket_entry_fallback",
            ],
            "transport_locator_fields_persisted": [],
        },
        "document_validation": {
            "official_host": adapter.OFFICIAL_HOST,
            "media_type": "application/pdf",
            "signature_prefix": "%PDF-",
        },
    }
    schema_contract = {
        "disclaimer_form_fields": list(
            snapshot.disclaimer_field_names
        ),
        "party_search_request_fields": list(
            snapshot.party_search_field_names
        ),
        "party_search_result_fields": list(
            snapshot.party_result_field_names
        ),
        "case_search_request_fields": list(
            snapshot.case_search_field_names
        ),
        "docket_request_fields": list(
            snapshot.docket_request_field_names
        ),
        "docket_response_fields": list(
            snapshot.docket_response_field_names
        ),
        "case_record_fields": sorted(str(key) for key in record),
        "party_fields": field_union(parties),
        "case_schedule_fields": field_union(schedule),
        "docket_entry_fields": field_union(docket_entries),
        "document_fields": field_union(documents),
    }
    filed_dates = sorted(
        {
            str(entry["filed_date"])
            for entry in docket_entries
            if entry.get("filed_date")
        }
    )
    rolling_observation = {
        "request_count": snapshot.request_count,
        "party_sentinel_case_number": snapshot.party_sentinel_case_number,
        "party_matching_count": snapshot.party_matching_count,
        "party_coverage_complete": snapshot.party_coverage_complete,
        "case_status": record.get("status"),
        "judge": record.get("judge"),
        "initial_docket_entry_count": sum(
            1
            for entry in docket_entries
            if entry.get("source_page_no") == 1
        ),
        "continuation_docket_entry_count": sum(
            1
            for entry in docket_entries
            if entry.get("source_page_no") == 2
        ),
        "case_schedule_count": len(schedule),
        "document_count": len(documents),
        "first_docket_date": filed_dates[0] if filed_dates else None,
        "last_docket_date": filed_dates[-1] if filed_dates else None,
        "continuation_next_key_present": (
            snapshot.continuation_next_key_present
        ),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.BASE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_franklin_municipal(context: ProbeContext) -> ProbeObservation:
    """Verify the fixed FCMC search, case-detail, and summary contract."""

    adapter = query_ohio_franklin_municipal
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = adapter.execute(args, record_search=False)
    if result.status not in {ResultStatus.OK, ResultStatus.NO_RESULTS}:
        raise ValueError(
            "Franklin Municipal fixed probe did not return a usable result"
        )
    if len(result.records) != 1:
        raise ValueError("Franklin Municipal probe expected one health record")
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("request_count") != adapter.PROBE_REQUEST_COUNT
    ):
        raise ValueError("Franklin Municipal probe identity or budget changed")
    if record.get("summary_is_filed_document") is not False:
        raise ValueError(
            "Franklin Municipal summary/document distinction changed"
        )

    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "court_id": adapter.COURT_ID,
        "platform_family": adapter.PLATFORM_FAMILY,
        "official_origin": adapter.OFFICIAL_HOST,
        "routes": {
            "search": urlsplit(adapter.SEARCH_URL).path,
            "search_results": urlsplit(adapter.SEARCH_RESULTS_URL).path,
            "case_view": urlsplit(adapter.CASE_VIEW_URL).path,
            "case_summary": urlsplit(adapter.CASE_PDF_URL).path,
        },
        "request_sequence": [
            "search_form",
            "person_search",
            "exact_case_search",
            "case_detail",
            "generated_case_summary",
        ],
        "search_boundary": {
            "native_result_limit": adapter.NATIVE_RESULT_LIMIT,
            "native_pagination": "none",
            "next_cursor": None,
        },
        "identity": {
            "case": ["court_id", "normalized_case_number"],
            "search_occurrence": ["query_fingerprint", "response_ordinal"],
            "transport_handle_persisted": False,
        },
        "document_states": {
            "generated_case_summary_is_filed_document": False,
            "individual_filing_links": "not_published_in_verified_case_view",
        },
    }
    schema_contract = {
        "search_field_names": record.get("search_field_names"),
        "sentinel_sections": record.get("sentinel_sections"),
        "summary_media_type": record.get("summary_media_type"),
        "probe_record_fields": sorted(record),
    }
    rolling_observation = {
        "request_count": record.get("request_count"),
        "person_search_occurrences": record.get("person_search_occurrences"),
        "person_search_truncated": record.get("person_search_truncated"),
        "sentinel_case_number": record.get("sentinel_case_number"),
        "sentinel_party_occurrences": record.get("sentinel_party_occurrences"),
        "sentinel_docket_entries": record.get("sentinel_docket_entries"),
        "summary_sha256": record.get("summary_sha256"),
        "rate_limit_headers": record.get("rate_limit_headers"),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.SEARCH_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_delaware_ohio_common_pleas(
    context: ProbeContext,
) -> ProbeObservation:
    """Inspect the rendered CourtView contract or its visible challenge state."""

    adapter = query_ohio_delaware_common_pleas
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        input=None,
        browser_timeout=max(context.timeout, adapter.DEFAULT_BROWSER_TIMEOUT),
        output=None,
        json_out=False,
    )
    result = adapter.execute(args)
    if result.status is ResultStatus.HUMAN_REQUIRED:
        return ProbeObservation(
            status=ResultStatus.HUMAN_REQUIRED.value,
            endpoint=adapter.HOME_URL,
            latency_ms=(time.perf_counter() - started) * 1000,
            result_count=0,
            details={
                "browser_helper_invocations": 1,
                "access_state": "visible_session_challenge",
                "errors": [error.to_dict() for error in result.errors],
            },
            error=(result.errors[0].message if result.errors else None),
        )
    if result.status not in {ResultStatus.OK, ResultStatus.NO_RESULTS}:
        raise ValueError("Delaware CourtView probe did not return a usable result")
    if len(result.records) != 1:
        raise ValueError("Delaware CourtView probe expected one contract record")
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
    ):
        raise ValueError("Delaware CourtView probe identity changed")
    contract = record.get("contract")
    if not isinstance(contract, Mapping):
        raise ValueError("Delaware CourtView probe contract is missing")
    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "court_id": adapter.COURT_ID,
        "platform_family": adapter.ADAPTER_FAMILY,
        "official_host": urlsplit(adapter.HOME_URL).hostname,
        "rendered_contract": dict(contract),
        "identity": {
            "case": "displayed_case_number_within_court",
            "search_occurrence": "query_fingerprint_plus_occurrence_ordinal",
            "document": "case_plus_docket_occurrence_fields",
            "wicket_actions_persisted": False,
        },
        "paging": {
            "native_page_sizes": [25, 50, 75, 100],
            "default": "exhaustive",
            "shared_cursor": "query_bound_offset_replay",
        },
    }
    rolling_observation = {
        **dict(record.get("rolling_observations") or {}),
        "native_page_size": record.get("native_page_size"),
        "access_state": record.get("access_state"),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.HOME_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=(
            str(record.get("schema_fingerprint"))
            if record.get("schema_fingerprint")
            else sha256_fingerprint(contract)
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "browser_helper_invocations": 1,
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_licking_common_pleas(context: ProbeContext) -> ProbeObservation:
    """Verify the county landing and anonymous re:SearchOH configuration."""

    adapter = query_ohio_licking_common_pleas
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        input=None,
        timeout=context.timeout,
        output=None,
        json_out=False,
    )
    result = adapter.execute(args)
    if result.status is ResultStatus.HUMAN_REQUIRED:
        return ProbeObservation(
            status=ResultStatus.HUMAN_REQUIRED.value,
            endpoint=adapter.PORTAL_URL,
            latency_ms=(time.perf_counter() - started) * 1000,
            result_count=0,
            details={
                "access_state": "interactive_verification_required",
                "errors": [error.to_dict() for error in result.errors],
            },
            error=(result.errors[0].message if result.errors else None),
        )
    if result.status not in {ResultStatus.OK, ResultStatus.NO_RESULTS}:
        raise ValueError("Licking Common Pleas probe did not return a usable result")
    if len(result.records) != 1:
        raise ValueError("Licking Common Pleas probe expected one contract record")
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("request_count") != adapter.PROBE_REQUEST_COUNT
    ):
        raise ValueError("Licking Common Pleas probe identity or budget changed")
    contract = record.get("contract")
    if not isinstance(contract, Mapping):
        raise ValueError("Licking Common Pleas probe contract is missing")
    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "court_id": adapter.COURT_ID,
        "platform_family": adapter.ADAPTER_FAMILY,
        "official_landing_host": urlsplit(adapter.OFFICIAL_LANDING_URL).hostname,
        "portal_host": urlsplit(adapter.PORTAL_URL).hostname,
        "anonymous_contract": dict(contract),
        "targeted_search_access": record.get("targeted_search_access_state"),
        "max_export_is_search_page_ceiling": False,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.OFFICIAL_LANDING_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=(
            str(record.get("schema_fingerprint"))
            if record.get("schema_fingerprint")
            else sha256_fingerprint(contract)
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "rolling_observation": dict(
                record.get("rolling_observations") or {}
            ),
            "request_count": record.get("request_count"),
        },
    )


def probe_franklin_probate(context: ProbeContext) -> ProbeObservation:
    """Verify the Franklin Probate landing and exact-case record family."""

    adapter = query_ohio_franklin_probate
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Franklin Probate monitor source ID changed")
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    started = time.perf_counter()
    result = adapter.execute(args)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    records = [dict(record) for record in result.records]
    if len(records) != 1:
        raise ValueError("Franklin Probate probe expected one health record")
    record = records[0]
    expected_routes = [
        "official_landing",
        "exact_case_number",
        "case_type_detail",
        "docket",
        "fiduciaries",
        "fiduciary_detail",
        "attorney_detail",
    ]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("status") != "available"
        or record.get("sentinel_case_number") != adapter.PROBE_CASE_NUMBER
    ):
        raise ValueError("Franklin Probate sentinel identity changed")
    if list(record.get("routes_exercised") or ()) != expected_routes:
        raise ValueError("Franklin Probate probe route contract changed")
    if record.get("request_count") != 7:
        raise ValueError(
            "Franklin Probate sentinel did not honor its seven-request contract"
        )

    source_contract = adapter._source_record()
    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "court_id": adapter.COURT_ID,
        "platform_family": adapter.SOURCE_METADATA.metadata["platform_family"],
        "official_origins": {
            "landing": urlsplit(adapter.LANDING_URL).netloc,
            "netdata": urlsplit(adapter.NETDATA_BASE_URL).netloc,
        },
        "routes": source_contract["routes"],
        "case_types": {
            code: {
                "source_value": details["source_value"],
                "label": details["label"],
            }
            for code, details in adapter.CASE_TYPES.items()
        },
        "paging": source_contract["paging"],
        "selector_grammar": source_contract["selector_grammar"],
        "identity": {
            "case": ["court_id", "case_number", "case_suffix"],
            "docket": [
                "case_number_plus_suffix",
                "logical_source_position",
                "physical_source_rows_sha256",
            ],
            "fiduciary": [
                "case_number_plus_suffix",
                "fiduciary_number",
            ],
            "attorney": ["attorney_number"],
        },
        "shared_operations": [
            "search",
            "case",
            "docket",
            "discovery",
            "probe",
        ],
        "certified_records_url": adapter.CERTIFIED_RECORDS_URL,
        "public_document_index_verified": False,
    }
    schema_contract = {
        "index_header_prefixes": {
            "case": ["Case Number", "Case Name", "Type", "SubType"],
            "attorney": ["Attorney Name", "Attorney Number"],
            "fiduciary": ["Case Number", "Fiduciary", "Type", "Subtype"],
        },
        "docket_headers": list(adapter.DOCKET_HEADERS),
        "fiduciary_headers": list(adapter.FIDUCIARY_HEADERS),
        "probe_record_fields": sorted(record),
        "record_kinds": [
            "probate_case_index",
            "probate_case",
            "probate_docket_entry",
            "probate_docket_summary",
            "probate_fiduciary",
            "probate_fiduciary_detail",
            "probate_attorney_index",
            "probate_attorney_detail",
            "probate_attorney_profile",
        ],
        "docket_row_grouping": (
            "logical entry with every contributing physical row preserved"
        ),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "court_id": adapter.COURT_ID,
        "sentinel_case_number": adapter.PROBE_CASE_NUMBER,
        "route_contract": stable_contract["routes"],
        "selector_grammar": stable_contract["selector_grammar"],
    }
    rolling_observation = {
        "sentinel_case_name": record.get("sentinel_case_name"),
        "sentinel_status_code": record.get("sentinel_status_code"),
        "sentinel_docket_records": record.get("sentinel_docket_records"),
        "sentinel_fiduciaries": record.get("sentinel_fiduciaries"),
        "sentinel_fiduciary_number": record.get("sentinel_fiduciary_number"),
        "sentinel_attorney_number": record.get("sentinel_attorney_number"),
        "landing_search_methods": record.get("landing_search_methods"),
        "request_count": record.get("request_count"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_ohio_supreme_court(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the five-request eCMS contract without downloading a PDF."""

    adapter = query_ohio_supreme_court
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Ohio Supreme Court monitor source ID changed")
    started = time.perf_counter()
    client = adapter.OhioSupremeCourtClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(context.max_attempts - 1, 0),
        request_budget=5,
    )
    search_parameters = {
        "paramCaseYear": "",
        "paramCaseNumber": "",
        "paramCaseCaption": adapter.PROBE_CASE_CAPTION,
        "paramPriorCaseNumber": "",
        "paramCaseType": "",
        "paramCaseFiledFrom": "",
        "paramCaseFiledTo": "",
        "paramPriorCaseJuris": "",
        "paramPartyFirstName": "",
        "paramPartyLastName": "",
        "paramPartyEntity": "",
        "paramAttyFirstName": "",
        "paramAttyLastName": "",
    }
    try:
        search_records = client.search(search_parameters)
        case_record = client.case(adapter.PROBE_CASE_NUMBER)
        recent_records = client.recent(1)
        request_count = client.request_count
    finally:
        client.close()
    if request_count != 5:
        raise ValueError(
            "Ohio Supreme Court eCMS sentinel did not honor its "
            "five-request contract"
        )
    if not any(
        record.get("case_number") == adapter.PROBE_CASE_NUMBER
        for record in search_records
    ):
        raise ValueError(
            "Ohio Supreme Court eCMS search sentinel no longer resolves "
            "the exact historical case"
        )
    if case_record.get("case_number") != adapter.PROBE_CASE_NUMBER:
        raise ValueError(
            "Ohio Supreme Court eCMS exact-case sentinel identity changed"
        )

    def field_union(rows: Sequence[Mapping[str, Any]]) -> list[str]:
        return sorted(
            {
                str(field)
                for row in rows
                for field in row
            }
        )

    parties = [
        dict(value)
        for value in case_record.get("parties", ())
        if isinstance(value, Mapping)
    ]
    attorneys = [
        dict(attorney)
        for party in parties
        for attorney in party.get("attorneys", ())
        if isinstance(attorney, Mapping)
    ]
    docket_entries = [
        dict(value)
        for value in case_record.get("docket_entries", ())
        if isinstance(value, Mapping)
    ]
    decisions = [
        dict(value)
        for value in case_record.get("decisions", ())
        if isinstance(value, Mapping)
    ]
    documents = [
        dict(value)
        for value in case_record.get("documents", ())
        if isinstance(value, Mapping)
    ]
    case_issues = [
        dict(value)
        for value in case_record.get("case_issues", ())
        if isinstance(value, Mapping)
    ]
    prior_jurisdiction = case_record.get("prior_jurisdiction")
    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "platform_family": adapter.PLATFORM_FAMILY,
        "official_origin": {
            "scheme": urlsplit(adapter.BASE_URL).scheme,
            "host": adapter.EXPECTED_HOST,
        },
        "routes": {
            "landing": urlsplit(adapter.BASE_URL).path,
            "structured": urlsplit(adapter.AJAX_URL).path,
            "public_document": urlsplit(adapter.PDF_VIEWER_URL).path,
        },
        "actions": {
            "search": "CaseSearch",
            "case": "GetCaseDetails",
            "recent": "GetRecentFilings",
        },
        "request_contract": [
            {"method": "GET", "role": "ecms_landing"},
            {"method": "GET", "role": "application_bundle_request_token"},
            {
                "method": "POST",
                "role": "stable_caption_search",
                "action": "CaseSearch",
            },
            {
                "method": "POST",
                "role": "exact_known_case",
                "action": "GetCaseDetails",
            },
            {
                "method": "POST",
                "role": "rolling_recent_filings",
                "action": "GetRecentFilings",
            },
        ],
        "sentinel": {
            "caption": adapter.PROBE_CASE_CAPTION,
            "case_number": adapter.PROBE_CASE_NUMBER,
            "recent_days": 1,
        },
        "identity": {
            "case": "CaseInfo.CaseNumber",
            "source_internal_case_locator": (
                "CaseInfo.ID retained as metadata only"
            ),
            "search_row_id": "not a case identity",
            "docket_entry": "DocketItems.ID",
            "document": "case_number + section + DocumentName",
            "recent_docket_identity": (
                "unresolved until exact case supplies DocketItems.ID"
            ),
        },
        "source_response": {
            "native_pagination": "none",
            "browser_pagination": "local",
            "observed_search_boundary": (
                adapter.OBSERVED_SEARCH_BOUNDARY
            ),
            "refinement_response": adapter.SOURCE_REFINEMENT_RESPONSE,
        },
        "document_validation": {
            "final_https_host": adapter.EXPECTED_HOST,
            "media_type": "application/pdf",
            "signature_prefix": "%PDF-",
            "monitor_downloads_pdf": False,
        },
    }
    schema_contract = {
        "search_parameter_fields": sorted(search_parameters),
        "search_record_fields": field_union(search_records),
        "case_record_fields": sorted(str(key) for key in case_record),
        "party_fields": field_union(parties),
        "attorney_fields": field_union(attorneys),
        "docket_entry_fields": field_union(docket_entries),
        "decision_fields": field_union(decisions),
        "document_fields": field_union(documents),
        "case_issue_fields": field_union(case_issues),
        "prior_jurisdiction_fields": (
            sorted(str(key) for key in prior_jurisdiction)
            if isinstance(prior_jurisdiction, Mapping)
            else []
        ),
        "recent_record_fields": field_union(recent_records),
    }
    rolling_observation = {
        "request_count": request_count,
        "caption_search_record_count": len(search_records),
        "sentinel_case_status": case_record.get("status"),
        "sentinel_docket_entry_count": len(docket_entries),
        "sentinel_decision_count": len(decisions),
        "sentinel_document_count": len(documents),
        "sentinel_party_count": len(parties),
        "sentinel_attorney_appearance_count": len(attorneys),
        "recent_one_day_record_count": len(recent_records),
        "recent_filings": [
            {
                "case_number": record.get("case_number"),
                "date_filed": record.get("date_filed"),
                "document_name": record.get("document_name"),
            }
            for record in recent_records
        ],
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.BASE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_ohio_reporter_decisions(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify a fixed three-request Reporter contract without fetching a PDF."""

    adapter = query_ohio_reporter_decisions
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Ohio Reporter monitor source ID changed")
    started = time.perf_counter()
    client = adapter.OhioReporterClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(context.max_attempts - 1, 0),
        request_budget=3,
    )
    try:
        landing = client.landing()
        exact = client.publication(adapter.PROBE_WEBCITE)
        request_count = client.request_count
    finally:
        client.close()
    if request_count != 3:
        raise ValueError(
            "Ohio Reporter sentinel did not honor its three-request contract"
        )
    if exact.incomplete_error is not None:
        raise exact.incomplete_error
    if len(exact.records) != 1:
        raise ValueError(
            "Ohio Reporter historical publication sentinel is unavailable"
        )
    publication = dict(exact.records[0])
    if publication.get("webcite") != adapter.PROBE_WEBCITE:
        raise ValueError("Ohio Reporter publication sentinel identity changed")

    stable_contract = {
        "source": adapter._source_metadata().to_dict(),
        "jurisdiction": adapter._jurisdiction().to_dict(),
        "platform_family": adapter.PLATFORM_FAMILY,
        "official_origin": {
            "scheme": urlsplit(adapter.BASE_URL).scheme,
            "host": adapter.EXPECTED_HOST,
        },
        "routes": {
            "search": urlsplit(adapter.BASE_URL).path,
            "help": urlsplit(adapter.HELP_URL).path,
            "publication_pdf_prefix": adapter.EXPECTED_PDF_PREFIX,
        },
        "request_contract": [
            {"method": "GET", "role": "webforms_landing"},
            {"method": "GET", "role": "exact_webcite_form_state"},
            {"method": "POST", "role": "exact_webcite_publication"},
        ],
        "identity": {
            "publication": "WebCite",
            "case": "optional deciding-court case-number join",
            "document": "WebCite official PDF representation",
            "deciding_source": "official PDF path source code",
        },
        "pagination": {
            "mechanism": "ASP.NET GridView postback",
            "native_page_size": adapter.NATIVE_PAGE_SIZE,
            "normal_query_behavior": (
                "exhaust native pages before an explicit caller window"
            ),
            "full_text_result_boundary": (
                adapter.FULL_TEXT_RESULT_BOUNDARY
            ),
        },
        "representation_relationship": (
            "Reporter, eCMS, Journal, and district copies can represent the "
            "same judicial act and are not independent corroboration merely "
            "because their access routes differ"
        ),
        "document_validation": {
            "final_https_host": adapter.EXPECTED_HOST,
            "media_type": "application/pdf",
            "signature_prefix": "%PDF-",
            "monitor_downloads_pdf": False,
        },
    }
    schema_contract = {
        "expected_headers": list(adapter._EXPECTED_HEADERS),
        "form_fields": dict(adapter._FORM_FIELDS),
        "select_fields": sorted(adapter._SELECT_FIELDS),
        "text_fields": sorted(adapter._TEXT_FIELDS),
        "court_sources": adapter.QUERY_SOURCES,
        "landing_schema_fingerprint": landing.schema_fingerprint,
        "publication_record_fields": sorted(publication),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel_webcite": publication["webcite"],
        "publication_ref": publication.get("canonical_ref"),
        "native_document_id": publication.get("native_document_id"),
        "deciding_source_code": publication.get(
            "source_native_court_code"
        ),
    }
    year_values = [
        int(value)
        for value in landing.options[adapter._FORM_FIELDS["year_from"]]
        if str(value).isdigit()
    ]
    rolling_observation = {
        "request_count": request_count,
        "landing_result_count": landing.total_rows,
        "observed_year_vocabulary": {
            "minimum": min(year_values) if year_values else None,
            "maximum": max(year_values) if year_values else None,
        },
        "landing_selected_source": landing.selected_labels.get(
            adapter._FORM_FIELDS["court"]
        ),
        "sentinel": {
            "webcite": publication.get("webcite"),
            "caption": publication.get("caption"),
            "case_number": publication.get("case_number"),
            "decided_date": publication.get("decided_date"),
            "posted_date": publication.get("posted_date"),
        },
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.BASE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": _json_ready(schema_contract),
            "artifact_identity": _json_ready(artifact_identity),
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def probe_connecticut_civil_family(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the fixed five-request Civil/Family portal lifecycle."""

    adapter = query_connecticut_civil_family
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Connecticut Civil/Family monitor source ID changed")
    started = time.perf_counter()
    client = adapter.ConnecticutCivilFamilyClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=max(context.max_attempts, 1),
        request_budget=adapter.PROBE_EXPECTED_REQUESTS,
    )
    request_count = 0
    try:
        form, page = client.search_parties(
            last_name=adapter.SENTINEL_LAST_NAME,
            match="exact",
        )
        bundle = client.fetch_case_bundle(adapter.SENTINEL_DOCKET)
        request_count = client.request_count
    finally:
        client.close()
    if request_count != adapter.PROBE_EXPECTED_REQUESTS:
        raise ValueError(
            "Connecticut Civil/Family sentinel did not honor its "
            "five-request contract"
        )
    if bundle.child_errors:
        raise ValueError(
            "Connecticut Civil/Family sentinel child route was unavailable"
        )
    if not page.source_slice_unresolved:
        raise ValueError(
            "Connecticut party sentinel no longer has the verified 50-row "
            "no-pager display semantics"
        )
    sentinel_hits = [
        row
        for row in page.rows
        if row.get("docket") == adapter.SENTINEL_DOCKET
        and row.get("publisher_party_number")
        == adapter.SENTINEL_PARTY_NUMBER
    ]
    if len(sentinel_hits) != 1:
        raise ValueError("Connecticut party-search sentinel identity changed")
    normalized_hits = [
        adapter._normalize_party_occurrence(row, page=page, form=form)
        for row in page.rows
    ]
    if any(
        record.get("identity_resolution", {}).get("status")
        != "unresolved_same_name_candidate"
        for record in normalized_hits
    ):
        raise ValueError(
            "Connecticut party search no longer preserves unresolved identity"
        )

    case = dict(bundle.record)
    if case.get("docket") != adapter.SENTINEL_DOCKET:
        raise ValueError("Connecticut exact-docket sentinel identity changed")
    for child_name in (
        "parties",
        "docket_entries",
        "scheduled_events",
        "history",
        "notices",
    ):
        if not isinstance(case.get(child_name), list):
            raise ValueError(
                f"Connecticut sentinel {child_name} child contract changed"
            )
    documents = [
        dict(value)
        for value in case.get("filing_documents", ())
        if isinstance(value, Mapping)
    ]
    document_matches = [
        value
        for value in documents
        if value.get("publisher_document_number")
        == adapter.SENTINEL_DOCUMENT_NUMBER
    ]
    if len(document_matches) != 1:
        raise ValueError("Connecticut DocumentNo metadata sentinel changed")

    route_result = adapter.source_routes()
    routes = {
        str(value["route_id"]): dict(value)
        for value in route_result.records
        if isinstance(value, Mapping) and value.get("route_id")
    }
    expected_routes = {
        "party_search",
        "case_detail",
        "filing_document",
        "civil_family_bulk",
        "clerk_offices",
    }
    if not expected_routes.issubset(routes):
        raise ValueError("Connecticut official route registry changed")
    bulk = routes["civil_family_bulk"]
    expected_bulk_fields = {
        "basic case information",
        "important case dates",
        "party and appearance information",
        "motions and pleadings",
        "companion cases",
    }
    if (
        set(bulk.get("published_fields", ())) != expected_bulk_fields
        or bulk.get("electronic_documents_included") is not False
    ):
        raise ValueError("Connecticut official bulk complement contract changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "official_routes": [routes[route_id] for route_id in sorted(routes)],
        "request_contract": [
            {"method": "GET", "role": "party_search_form"},
            {"method": "POST", "role": "party_search_results"},
            {"method": "GET", "role": "exact_docket_detail"},
            {"method": "GET", "role": "case_transfer_history"},
            {"method": "GET", "role": "case_notices"},
        ],
        "document_probe": {
            "metadata_checked": True,
            "pdf_downloaded": False,
        },
        "transport": {
            "dependency": "curl-cffi>=0.13.0",
            "scope": "connecticut_source_local_injectable_session",
        },
        "same_publisher_complements": {
            "paid_bulk": {
                "url": adapter.BULK_DESCRIPTION_URL,
                "coverage": sorted(expected_bulk_fields),
                "electronic_documents_included": False,
            },
            "clerk_offices": {
                "url": adapter.CLERK_DIRECTORY_URL,
                "access": "human_request_or_copy_assistance",
            },
        },
    }
    schema_contract = {
        "party_result_headers": list(adapter.PARTY_RESULT_HEADERS),
        "party_grid_id": adapter.PARTY_GRID_ID,
        "case_child_grid_ids": {
            "parties": adapter.CASE_PARTIES_GRID_SUFFIX,
            "docket_entries": adapter.CASE_DOCUMENTS_GRID_SUFFIX,
            "scheduled_events": adapter.CASE_EVENTS_GRID_SUFFIX,
            "history": adapter.HISTORY_GRID_ID,
            "notices": adapter.NOTICES_GRID_ID,
        },
        "search_form_schema_fingerprint": form.schema_fingerprint,
        "party_results_schema_fingerprint": page.schema_fingerprint,
        "case_schema_fingerprint": case.get("schema_fingerprint"),
        "case_record_fields": sorted(case),
    }
    identity_contract = {
        "source_id": adapter.SOURCE_ID,
        "case": {
            "publisher_docket": adapter.SENTINEL_DOCKET,
            "canonical_ref": case.get("canonical_ref"),
        },
        "party": {
            "publisher_party_number": adapter.SENTINEL_PARTY_NUMBER,
            "identity_resolution": "unresolved_same_name_candidate",
        },
        "filing": {
            "publisher_document_number": adapter.SENTINEL_DOCUMENT_NUMBER,
            "canonical_ref": document_matches[0].get("canonical_ref"),
        },
        "child_identity_rules": {
            "party": "publisher_party_number_within_docket",
            "filing": "DocumentNo_within_docket",
            "scheduled_event": "publisher_event_number_within_docket",
            "notice": "publisher_eNID_within_docket",
            "transfer": "complete_published_transfer_tuple_hash",
            "idless_docket_entry": "complete_published_entry_tuple_hash",
            "appearance": (
                "complete_published_appearance_tuple_hash_plus_identical_"
                "tuple_ordinal"
            ),
        },
    }
    completeness_contract = {
        "party_search": {
            "displayed_start": 1,
            "displayed_end": adapter.SOURCE_DISPLAY_SLICE_SIZE,
            "source_reported_count": adapter.SOURCE_DISPLAY_SLICE_SIZE,
            "has_pager": False,
            "result_status": ResultStatus.PARTIAL.value,
            "error_code": "source_display_slice",
            "publisher_continuation_beyond_display": False,
            "adapter_cursor_scope": (
                "query_and_snapshot_bound_window_within_reacquired_display"
            ),
        },
        "exact_case_children_retrieved": [
            "parties",
            "docket_entries",
            "scheduled_events",
            "history",
            "notices",
        ],
        "document_metadata_without_download": True,
    }
    rolling_observation = {
        "request_count": request_count,
        "party_displayed_rows": len(page.rows),
        "sentinel_caption": case.get("caption"),
        "sentinel_case_type_code": case.get("case_type_code"),
        "sentinel_file_date": case.get("file_date"),
        "information_updated_as_of": case.get("information_updated_as_of"),
        "party_count": len(case["parties"]),
        "docket_entry_count": len(case["docket_entries"]),
        "scheduled_event_count": len(case["scheduled_events"]),
        "history_count": len(case["history"]),
        "notice_count": len(case["notices"]),
        "document_metadata_count": len(documents),
    }
    stable_hash = sha256_fingerprint(stable_contract)
    identity_hash = sha256_fingerprint(identity_contract)
    completeness_hash = sha256_fingerprint(completeness_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.BASE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=stable_hash,
        result_count=1,
        details={
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": _json_ready(schema_contract),
            "identity_contract": _json_ready(identity_contract),
            "completeness_contract": _json_ready(completeness_contract),
            "contract_hashes": {
                "stable": stable_hash,
                "identity": identity_hash,
                "completeness": completeness_hash,
            },
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def probe_new_mexico_case_lookup(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify one exact historical case through the four-request lifecycle."""

    adapter = query_new_mexico_case_lookup
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("New Mexico Case Lookup monitor source ID changed")
    started = time.perf_counter()
    client = adapter.NewMexicoCaseLookupClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(context.max_attempts - 1, 0),
        request_budget=adapter.PROBE_EXPECTED_REQUESTS,
    )
    request_count = 0
    try:
        exact = client.exact_case(adapter.PROBE_CASE_NUMBER)
        request_count = client.request_count
    finally:
        client.close()
    if request_count != adapter.PROBE_EXPECTED_REQUESTS:
        raise ValueError(
            "New Mexico Case Lookup sentinel did not honor its four-request "
            "contract"
        )
    if exact.record is None:
        raise ValueError(
            "New Mexico Case Lookup historical case sentinel is unavailable"
        )
    case = dict(exact.record)
    if case.get("case_number") != adapter.PROBE_CASE_NUMBER:
        raise ValueError(
            "New Mexico Case Lookup sentinel case identity changed"
        )

    parties = [
        dict(value)
        for value in case.get("parties", ())
        if isinstance(value, Mapping)
    ]
    attorneys = [
        dict(value)
        for party in parties
        for value in party.get("attorneys", ())
        if isinstance(value, Mapping)
    ]
    register = [
        dict(value)
        for value in case.get("register_of_actions", ())
        if isinstance(value, Mapping)
    ]
    judge_history = [
        dict(value)
        for value in case.get("judge_assignment_history", ())
        if isinstance(value, Mapping)
    ]
    complaints = [
        dict(value)
        for value in case.get("complaint_records", ())
        if isinstance(value, Mapping)
    ]
    causes = [
        dict(value)
        for value in case.get("cause_records", ())
        if isinstance(value, Mapping)
    ]
    detail_sections = [
        dict(value)
        for value in case.get("case_detail_sections", ())
        if isinstance(value, Mapping)
    ]

    def fields(values: Sequence[Mapping[str, Any]]) -> list[str]:
        return sorted(
            {
                str(key)
                for value in values
                for key in value
            }
        )

    stable_contract = {
        "source": adapter._source_metadata().to_dict(),
        "jurisdiction": adapter._jurisdiction().to_dict(),
        "platform_family": adapter.PLATFORM_FAMILY,
        "official_origins": {
            "case_lookup": {
                "scheme": urlsplit(adapter.BASE_URL).scheme,
                "host": adapter.EXPECTED_HOST,
                "path": adapter.EXPECTED_PATH,
            },
            "information": {
                "host": urlsplit(adapter.INFO_URL).hostname,
                "path": urlsplit(adapter.INFO_URL).path,
            },
            "research_nm": {
                "host": urlsplit(adapter.RESEARCH_NM_URL).hostname,
                "path": urlsplit(adapter.RESEARCH_NM_URL).path,
            },
            "public_records_request": {
                "host": urlsplit(adapter.IPRA_URL).hostname,
                "path": urlsplit(adapter.IPRA_URL).path,
            },
        },
        "request_contract": [
            {"method": "GET", "role": "disclaimer"},
            {"method": "POST", "role": "disclaimer_acceptance"},
            {"method": "GET", "role": "case_number_search_form"},
            {"method": "POST", "role": "caller_selected_exact_case"},
        ],
        "source_acquisition_grain": (
            "one_individual_electronic_case_record"
        ),
        "verified_operations": {
            "party_discovery": "first source-native result page",
            "exact_case": "one caller-selected full case number",
        },
        "identity": {
            "case": "published full case number plus court",
            "party": (
                "published role code, role, party number, and name plus "
                "duplicate ordinal among identical tuples"
            ),
            "complaint_and_cause": (
                "published group fields plus duplicate ordinal among "
                "identical tuples"
            ),
            "register_entry": (
                "published row fields plus duplicate ordinal among "
                "identical tuples"
            ),
            "judge_history": (
                "published assignment tuple plus duplicate ordinal among "
                "identical tuples"
            ),
            "ephemeral_tapestry_locator_persisted": False,
        },
        "documents": {
            "case_lookup_documents_available": False,
            "registered_complement": adapter.RESEARCH_NM_URL,
            "public_records_complement": adapter.IPRA_URL,
        },
    }
    schema_contract = {
        "disclaimer_form": adapter.DISCLAIMER_FORM_ID,
        "name_search_form": adapter.NAME_SEARCH_FORM_ID,
        "case_number_search_form": adapter.CASE_NUMBER_SEARCH_FORM_ID,
        "name_search_fields": list(adapter.NAME_SEARCH_FIELDS),
        "case_number_search_fields": list(
            adapter.CASE_NUMBER_SEARCH_FIELDS
        ),
        "party_search_headers": list(adapter.SEARCH_HEADERS),
        "case_summary_headers": list(adapter.CASE_SUMMARY_HEADERS),
        "party_headers": list(adapter.PARTY_HEADERS),
        "register_headers": list(adapter.REGISTER_HEADERS),
        "judge_history_headers": list(adapter.JUDGE_HISTORY_HEADERS),
        "case_record_fields": sorted(case),
        "party_fields": fields(parties),
        "attorney_fields": fields(attorneys),
        "complaint_fields": fields(complaints),
        "cause_fields": fields(causes),
        "register_entry_fields": fields(register),
        "judge_history_fields": fields(judge_history),
        "detail_section_titles": sorted(
            str(section.get("title"))
            for section in detail_sections
            if section.get("title") is not None
        ),
        "live_schema_fingerprint": exact.schema_fingerprint,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel_case_number": case["case_number"],
        "case_ref": case.get("canonical_ref"),
        "court_id": (
            case.get("court", {}).get("court_id")
            if isinstance(case.get("court"), Mapping)
            else None
        ),
    }
    rolling_observation = {
        "request_count": request_count,
        "sentinel_caption": case.get("caption"),
        "sentinel_current_judge": case.get("current_judge"),
        "sentinel_party_count": len(parties),
        "sentinel_attorney_appearance_count": len(attorneys),
        "sentinel_complaint_count": len(complaints),
        "sentinel_cause_count": len(causes),
        "sentinel_register_entry_count": len(register),
        "sentinel_judge_history_count": len(judge_history),
        "latest_register_date": (
            register[0].get("event_date") if register else None
        ),
        "documents_available": case.get("documents_available"),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.BASE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": _json_ready(schema_contract),
            "artifact_identity": _json_ready(artifact_identity),
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def probe_san_mateo_midx(context: ProbeContext) -> ProbeObservation:
    """Verify the official MIDX case sentinel through its browser form."""
    started = time.perf_counter()
    client = MIDXClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=_catalog_interval(context.catalog_decision),
    )
    try:
        result = client.probe()
    finally:
        client.close()
    status = ResultStatus.OK.value if result.rows else ResultStatus.NO_RESULTS.value
    return ProbeObservation(
        status=status,
        endpoint=SAN_MATEO_MIDX_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=result.schema_fingerprint,
        result_count=len(result.rows),
        details={
            "total_reported": result.total_reported,
            "source_total_pages": result.source_total_pages,
            "pages_fetched": result.pages_fetched,
            "current_as_of": result.current_as_of,
            "source_url": result.source_url,
            "transport": "anonymous_browser_form",
        },
    )


def probe_tax_court_dawson(context: ProbeContext) -> ProbeObservation:
    """Verify DAWSON health plus one stable public case-search contract."""
    started = time.perf_counter()
    client = TaxCourtClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=_catalog_interval(context.catalog_decision),
    )
    try:
        health_result = client.health()
        case_result = client.search_cases("Hagee")
    finally:
        close = getattr(client.session, "close", None)
        if callable(close):
            close()
    resource = health_result.get("resource")
    if not isinstance(resource, Mapping):
        raise ValueError("Tax Court health response lacks a resource object")
    health_metadata = health_result.get("metadata")
    if not isinstance(health_metadata, Mapping):
        raise ValueError("Tax Court health response lacks metadata")
    health_schema = health_metadata.get("schema_fingerprint")
    if not isinstance(health_schema, str):
        raise ValueError("Tax Court health response lacks a schema fingerprint")
    records = case_result.get("records")
    case_metadata = case_result.get("metadata")
    if (
        not isinstance(records, Sequence)
        or isinstance(records, (str, bytes))
        or any(not isinstance(record, Mapping) for record in records)
        or not isinstance(case_metadata, Mapping)
    ):
        raise ValueError("Tax Court case sentinel lacks records or metadata")
    case_schema = case_metadata.get("schema_fingerprint")
    if not isinstance(case_schema, str):
        raise ValueError("Tax Court case sentinel lacks a schema fingerprint")
    dockets = sorted(
        str(record.get("docketNumberWithSuffix"))
        for record in records
        if record.get("docketNumberWithSuffix")
    )
    expected_dockets = {"455-22S", "9072-14S"}
    if not expected_dockets.issubset(dockets):
        raise ValueError("Tax Court case sentinel no longer returns both known dockets")
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=f"{TAX_COURT_API_ROOT}/public-api/health",
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(
            {
                "health": health_schema,
                "case_search": case_schema,
            }
        ),
        result_count=len(records),
        details={
            "health": dict(resource),
            "contracts": dict(health_metadata.get("contracts") or {}),
            "sentinel_petitioner": "Hagee",
            "sentinel_dockets": dockets,
            "requests_made": (
                int(health_metadata.get("requests_made") or 0)
                + int(case_metadata.get("requests_made") or 0)
            ),
        },
    )


def probe_ny_law_reports(context: ProbeContext) -> ProbeObservation:
    """Verify both Law Reporting Bureau collections and an exact opinion."""
    del context
    started = time.perf_counter()
    payload = run_ny_law_reports_sentinel()
    checks = payload.get("checks")
    exact_urls = payload.get("exact_urls")
    if (
        not isinstance(checks, Sequence)
        or isinstance(checks, (str, bytes))
        or any(not isinstance(check, Mapping) for check in checks)
    ):
        raise ValueError("NY Law Reports sentinel lacks check objects")
    if not isinstance(exact_urls, Mapping):
        raise ValueError("NY Law Reports sentinel lacks exact URLs")
    status = (
        ResultStatus.OK.value
        if payload.get("status") == "ok"
        else ResultStatus.UNAVAILABLE.value
    )
    schema = {
        "checks": [
            {
                "name": check.get("name"),
                "fields": sorted(check),
            }
            for check in checks
        ]
    }
    return ProbeObservation(
        status=status,
        endpoint=f"{NY_LAW_REPORTS_BASE_URL}/reporter/",
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema),
        artifact_sha256=sha256_fingerprint(dict(exact_urls)),
        result_count=len(checks),
        details={
            "checks": [dict(check) for check in checks],
            "exact_urls": dict(exact_urls),
        },
    )


def probe_ny_column(context: ProbeContext) -> ProbeObservation:
    """Verify one exact public notice plus the displayed-result ceiling."""
    del context
    started = time.perf_counter()
    payload = run_ny_column_sentinel()
    checks = payload.get("checks")
    exact_urls = payload.get("exact_urls")
    if (
        not isinstance(checks, Sequence)
        or isinstance(checks, (str, bytes))
        or any(not isinstance(check, Mapping) for check in checks)
    ):
        raise ValueError("NY Column sentinel lacks check objects")
    if not isinstance(exact_urls, Mapping):
        raise ValueError("NY Column sentinel lacks exact URLs")
    status = (
        ResultStatus.OK.value
        if payload.get("status") == "ok"
        else ResultStatus.UNAVAILABLE.value
    )
    schema = {
        "checks": [
            {
                "name": check.get("name"),
                "fields": sorted(check),
            }
            for check in checks
        ]
    }
    return ProbeObservation(
        status=status,
        endpoint=NY_COLUMN_PORTAL_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema),
        artifact_sha256=sha256_fingerprint(dict(exact_urls)),
        result_count=len(checks),
        details={
            "checks": [dict(check) for check in checks],
            "exact_urls": dict(exact_urls),
        },
    )


def _adapter_result_observation(
    result: Any,
    *,
    endpoint: str,
    started: float,
) -> ProbeObservation:
    records = list(result.records)
    identities = [
        {
            "canonical_ref": record.get("canonical_ref"),
            "source_url": record.get("source_url"),
            "record_kind": record.get("record_kind"),
        }
        for record in records
        if isinstance(record, Mapping)
    ]
    errors = [
        error.to_dict() if hasattr(error, "to_dict") else {"message": str(error)}
        for error in result.errors
    ]
    return ProbeObservation(
        status=result.status.value,
        endpoint=endpoint,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(inferred_schema(records)),
        artifact_sha256=(sha256_fingerprint(identities) if identities else None),
        result_count=len(records),
        details={
            "records": identities,
            "warnings": list(result.warnings),
            "errors": errors,
        },
        error=(
            "; ".join(error.get("message", "") for error in errors).strip("; ") or None
            if result.status
            not in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        ),
    )


def probe_ny_oca_attorney_registrations(
    context: ProbeContext,
) -> ProbeObservation:
    """Run the standalone OCA metadata/count/exact-registration probe."""

    adapter = query_ny_attorneys
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError(
            "New York attorney-registration monitor received an unknown source"
        )
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.QUERY_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "New York attorney-registration probe expected one contract record"
        )

    record = dict(result.records[0])
    declared_fields = _json_ready(record.get("declared_fields"))
    sentinel = _json_ready(record.get("sentinel"))
    request_breakdown = _json_ready(record.get("request_breakdown"))
    declared_schema = record.get("declared_schema_fingerprint")
    rows_updated_at = record.get("rows_updated_at_epoch")
    total_rows = record.get("total_registration_rows")
    requests_made = record.get("requests_made")
    sentinel_snapshot = (
        sentinel.get("source_snapshot")
        if isinstance(sentinel, Mapping)
        else None
    )
    sentinel_native_ids = (
        sentinel.get("native_ids")
        if isinstance(sentinel, Mapping)
        else None
    )
    response_schema = (
        sentinel_snapshot.get("response_schema_fingerprint")
        if isinstance(sentinel_snapshot, Mapping)
        else None
    )
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("dataset_id") != adapter.DATASET_ID
        or declared_fields != list(adapter.EXPECTED_FIELDS)
        or record.get("declared_field_count") != len(adapter.EXPECTED_FIELDS)
        or not isinstance(declared_schema, str)
        or len(declared_schema) != 64
        or isinstance(rows_updated_at, bool)
        or not isinstance(rows_updated_at, int)
        or rows_updated_at < 1
        or not isinstance(record.get("rows_updated_at"), str)
        or not record["rows_updated_at"]
        or isinstance(total_rows, bool)
        or not isinstance(total_rows, int)
        or total_rows < 1
        or not isinstance(sentinel, Mapping)
        or sentinel.get("record_kind") != "attorney_registration"
        or sentinel.get("source_id") != adapter.SOURCE_ID
        or sentinel.get("dataset_id") != adapter.DATASET_ID
        or not isinstance(sentinel_native_ids, Mapping)
        or sentinel_native_ids.get("registration_number")
        != adapter.PROBE_REGISTRATION_NUMBER
        or not isinstance(sentinel_snapshot, Mapping)
        or sentinel_snapshot.get("rows_updated_at_epoch")
        != rows_updated_at
        or sentinel_snapshot.get("declared_schema_fingerprint")
        != declared_schema
        or not isinstance(response_schema, str)
        or len(response_schema) != 64
        or not isinstance(request_breakdown, Mapping)
        or request_breakdown
        != {
            "initial_metadata": 1,
            "matching_count": 1,
            "sentinel_query": 1,
            "final_metadata": 1,
            "total_count": 1,
        }
        or requests_made != sum(request_breakdown.values())
        or requests_made != 5
    ):
        raise ValueError(
            "New York attorney-registration probe contract changed"
        )

    complementary_route_identity = {
        "interactive_directory": adapter.INTERACTIVE_DIRECTORY_URL,
        "written_request_data": adapter.PUBLIC_ACCESS_RULE_URL,
        "public_discipline_sources": [
            adapter.AD1_REGISTRATION_URL,
            adapter.AD2_ATTORNEY_MATTERS_URL,
            adapter.AD3_DISCIPLINE_URL,
            adapter.AD4_DISCIPLINE_URL,
            adapter.AD4_DECISIONS_URL,
        ],
        "nyscef_case_filings": adapter.NYSCEF_URL,
    }
    stable_contract = {
        "dataset_identity": {
            "source_id": adapter.SOURCE_ID,
            "dataset_id": adapter.DATASET_ID,
            "dataset_url": adapter.DATASET_URL,
            "query_url": adapter.QUERY_URL,
            "metadata_url": adapter.METADATA_URL,
            "posting_frequency": "quarterly",
        },
        "registration_identity": {
            "field": "registration_number",
            "record_kind": "attorney_registration",
            "sentinel_registration_number": (
                adapter.PROBE_REGISTRATION_NUMBER
            ),
            "organization_name_semantics": "whole publisher field",
            "case_projection": False,
        },
        "declared_fields": list(adapter.EXPECTED_FIELDS),
        "declared_schema": declared_schema,
        "response_schema": response_schema,
        "cursor_contract": {
            "version": adapter.CURSOR_VERSION,
            "prefix": adapter.CURSOR_PREFIX,
            "ordering": adapter.ORDERING,
            "bound_fields": [
                "criteria",
                "schema",
                "rows_updated_at",
                "total",
                "offset",
            ],
            "checksum": "sha256 fingerprint prefix",
        },
        "complementary_route_identity": complementary_route_identity,
    }
    schema_contract = {
        "declared_fields": list(adapter.EXPECTED_FIELDS),
        "declared_schema_fingerprint": declared_schema,
        "sentinel_response_schema_fingerprint": response_schema,
        "probe_record_fields": sorted(record),
        "normalized_record_fields": sorted(sentinel),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "dataset_id": adapter.DATASET_ID,
        "sentinel_registration_number": adapter.PROBE_REGISTRATION_NUMBER,
        "query_url": adapter.QUERY_URL,
        "metadata_url": adapter.METADATA_URL,
    }
    rolling_observation = {
        "total_registration_rows": total_rows,
        "rows_updated_at_epoch": rows_updated_at,
        "rows_updated_at": record["rows_updated_at"],
        "sentinel_record_contents": sentinel,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=total_rows,
        details={
            **dict(observation.details),
            "requests_made": requests_made,
            "request_breakdown": request_breakdown,
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_doj_epstein_court_records(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe DOJ's release index, one case page, and five PDF bytes."""

    adapter = query_doj_court_records
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError(
            "DOJ Epstein court-record monitor received an unknown source"
        )
    client = adapter.DOJCourtRecordsClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    args = adapter.build_parser().parse_args(["probe"])
    started = time.perf_counter()
    try:
        result = adapter.execute(
            args,
            client=client,
            pdf_probe=lambda url: adapter.probe_pdf_magic(
                url,
                timeout=context.timeout,
            ),
            log_results=False,
        )
    finally:
        client.close()
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.INDEX_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "DOJ Epstein court-record probe expected one contract record"
        )

    record = dict(result.records[0])
    probe_scope = _json_ready(record.get("probe_scope"))
    pdf_magic = _json_ready(record.get("pdf_magic"))
    request_breakdown = _json_ready(record.get("request_breakdown"))
    case_count = record.get("case_count_on_index")
    document_count = record.get("sentinel_first_page_document_count")
    expected_scope = {
        "bounded": True,
        "index_pages": 1,
        "case_pages": 1,
        "pdf_bytes": 5,
        "coverage_inference": False,
    }
    expected_request_breakdown = {
        "release_index": 1,
        "sentinel_case_page": 1,
        "sentinel_pdf_range": 1,
    }
    if (
        record.get("record_kind") != "doj_court_records_probe"
        or probe_scope != expected_scope
        or isinstance(case_count, bool)
        or not isinstance(case_count, int)
        or case_count < 1
        or record.get("sentinel_case_present") is not True
        or isinstance(document_count, bool)
        or not isinstance(document_count, int)
        or document_count < 1
        or record.get("sentinel_document_present") is not True
        or not isinstance(
            record.get("sentinel_has_native_next_page"),
            bool,
        )
        or not isinstance(pdf_magic, Mapping)
        or pdf_magic.get("source_url") != adapter.SENTINEL_PDF_URL
        or pdf_magic.get("magic") != "%PDF-"
        or pdf_magic.get("bytes_read") != 5
        or request_breakdown != expected_request_breakdown
        or record.get("requests_made") != sum(
            expected_request_breakdown.values()
        )
        or record.get("healthy") is not True
    ):
        raise ValueError(
            "DOJ Epstein court-record probe contract changed"
        )

    routes = adapter.source_alternatives()
    if any(not isinstance(route, Mapping) for route in routes):
        raise ValueError(
            "DOJ Epstein court-record route inventory changed"
        )
    route_roles = {
        str(route["route_id"]): str(route["role"])
        for route in routes
        if route.get("route_id") and route.get("role")
    }
    required_route_ids = {
        "doj_current_case_listing",
        "pacer_cm_ecf",
        "courtlistener_recap",
        "court_clerk",
        "local_efta_corpus",
    }
    if set(route_roles) != required_route_ids:
        raise ValueError(
            "DOJ Epstein court-record route inventory changed"
        )

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "record_grain": [
            "doj_court_case_listing",
            "doj_released_court_document",
        ],
        "identity": {
            "case_group": "canonical DOJ case-page URL",
            "document": (
                "EFTA identifier when published; canonical case slug and "
                "filename otherwise"
            ),
            "official_document_url_preserved": True,
        },
        "shared_operations": {
            "search": "current case-group title or docket text",
            "documents": "exact canonical DOJ case-page URL",
            "discovery": "separately attributable source routes",
            "probe": "bounded release-contract check",
            "case": None,
            "docket": None,
            "normalized_case_ingestion": False,
        },
        "publication_semantics": {
            "publisher": "United States Department of Justice",
            "release_corpus_is_complete_underlying_docket": False,
            "empty_release_is_no_underlying_court_record": False,
            "duplicate_copy_is_independent_corroboration": False,
        },
        "source_route_roles": route_roles,
        "cursor_contract": {
            "version": adapter.CURSOR_VERSION,
            "prefix": adapter.CURSOR_PREFIX,
            "bound_fields": [
                "canonical case URL",
                "page URL",
                "page fingerprint",
                "offset",
                "checksum",
            ],
        },
        "probe_request_contract": {
            "requests_made": 3,
            "network_methods": ["GET"],
            "index_pages": 1,
            "case_pages": 1,
            "pdf_bytes_read": 5,
            "post_requests": 0,
            "request_breakdown": expected_request_breakdown,
        },
    }
    schema_contract = {
        "probe_record_fields": sorted(record),
        "probe_scope_fields": sorted(probe_scope),
        "pdf_probe_fields": sorted(pdf_magic),
        "case_group_fields": [
            "canonical_ref",
            "case_page_url",
            "case_title",
            "coverage_role",
            "docket_number",
            "index_url",
            "publisher",
            "record_kind",
        ],
        "released_document_fields": [
            "canonical_ref",
            "case_page_url",
            "case_title",
            "coverage_role",
            "docket_number",
            "efta_id",
            "filename",
            "indexed_source_url",
            "listing_page_url",
            "native_page",
            "publisher",
            "record_kind",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "index_url": adapter.INDEX_URL,
        "case_path_prefix": adapter.CASE_PATH_PREFIX,
        "current_pdf_path_prefix": adapter.CURRENT_PDF_PATH_PREFIX,
        "sentinel_case_url": adapter.SENTINEL_CASE_URL,
        "sentinel_efta_id": adapter.SENTINEL_EFTA,
        "sentinel_pdf_url": adapter.SENTINEL_PDF_URL,
    }
    rolling_observation = {
        "case_count_on_index": case_count,
        "sentinel_first_page_document_count": document_count,
        "sentinel_has_native_next_page": record[
            "sentinel_has_native_next_page"
        ],
        "sentinel_pdf_response": pdf_magic,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=case_count,
        details={
            **dict(observation.details),
            "requests_made": 3,
            "request_breakdown": request_breakdown,
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_census_acs(context: ProbeContext) -> ProbeObservation:
    """Probe ACS metadata and one county observation through an available backend."""

    adapter = query_census_acs
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--year",
            str(adapter.DEFAULT_YEAR),
            "--timeout",
            str(context.timeout),
            "--max-attempts",
            str(context.max_attempts),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    endpoint = f"{adapter.OFFICIAL_API_ROOT}/{adapter.DEFAULT_YEAR}/acs/acs5.html"
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    if not result.records:
        return observation

    record = dict(result.records[0])
    operation_states = record.get("operation_states")
    expected_state_keys = {
        "official_dataset_metadata",
        "official_variable_metadata",
        "official_data_query",
        "keyless_census_reporter_fallback",
        "official_bulk_summary_files",
    }

    def valid_fingerprint(value: Any) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    population = record.get("sentinel_population")
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("status") != "ok"
        or record.get("backend") not in {"census_api", "census_reporter"}
        or record.get("release_id") != f"acs{adapter.DEFAULT_YEAR}_5yr"
        or record.get("period") != f"{adapter.DEFAULT_YEAR - 4}-{adapter.DEFAULT_YEAR}"
        or record.get("sentinel_full_geoid") != "05000US24005"
        or not isinstance(record.get("sentinel_name"), str)
        or not record["sentinel_name"].strip()
        or isinstance(population, bool)
        or not isinstance(population, (int, float))
        or population <= 0
        or not isinstance(operation_states, Mapping)
        or not expected_state_keys.issubset(operation_states)
        or any(
            not isinstance(operation_states[key], str) for key in expected_state_keys
        )
        or operation_states["official_dataset_metadata"] != "available"
        or operation_states["official_variable_metadata"] != "available"
        or not valid_fingerprint(record.get("response_schema_fingerprint"))
        or not valid_fingerprint(record.get("data_fingerprint"))
    ):
        raise ValueError("Census ACS probe contract changed")

    manifest = adapter.source_records(adapter.DEFAULT_YEAR)[0]
    routes = adapter.related_source_routes(adapter.DEFAULT_YEAR)
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "endpoints": {
            "dataset_metadata": endpoint,
            "variable_metadata": (
                f"{adapter.OFFICIAL_API_ROOT}/{adapter.DEFAULT_YEAR}/"
                "acs/acs5/groups/<GROUP>.html"
            ),
            "official_data_api": (
                f"{adapter.OFFICIAL_API_ROOT}/{adapter.DEFAULT_YEAR}/acs/acs5"
            ),
        },
        "geographies": dict(adapter.SUMLEVELS),
        "profiles": {
            name: list(metric_keys) for name, metric_keys in adapter.PROFILES.items()
        },
        "metrics": [
            {
                "key": metric.key,
                "estimate_variable": metric.estimate_variable,
                "margin_variable": metric.margin_variable,
                "unit": metric.unit,
            }
            for metric in adapter.KNOWN_METRICS
        ],
        "identity": manifest["identity"],
        "acquisition_routes": [
            {
                key: route.get(key)
                for key in (
                    "source_id",
                    "record_role",
                    "join_keys",
                )
            }
            for route in routes
        ],
        "operation_state_keys": sorted(operation_states),
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "probe_record_kind": "source_probe",
        "observation_record_kind": "acs_geography_observation",
        "upstream_schema_observation": {
            "attribution_fields": [
                "backend",
                "response_schema_fingerprint",
            ],
            "location": "rolling_observation",
        },
        "observation_structure": {
            "geography": [
                "full_geoid",
                "summary_level",
                "state_fips",
                "county_fips",
                "tract_geoid",
                "block_group_geoid",
                "place_geoid",
                "zcta",
            ],
            "metric": [
                "estimate",
                "margin_of_error",
                "estimate_annotation",
                "margin_annotation",
            ],
            "derived_values": ["point_estimate_rate"],
        },
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "sentinel_full_geoid": "05000US24005",
        "canonical_reference_pattern": ("USCENSUS:ACS5:<vintage>:<full_geoid>"),
        "observation_identity": manifest["identity"]["observation"],
        "backend_attribution": [
            "census_api",
            "census_reporter",
        ],
        "same_release_mirror_identity_source": adapter.SOURCE_ID,
    }
    rolling_observation = {
        "release_id": record["release_id"],
        "period": record["period"],
        "dataset_identifier": record.get("dataset_identifier"),
        "dataset_modified": record.get("dataset_modified"),
        "response_schema_fingerprint": record["response_schema_fingerprint"],
        "sentinel_name": record["sentinel_name"],
        "sentinel_population": population,
        "data_fingerprint": record["data_fingerprint"],
        "backend": record["backend"],
        "credential_present": record.get("credential_present"),
        "operation_states": dict(operation_states),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_pa_ujs(context: ProbeContext) -> ProbeObservation:
    """Verify known Common Pleas and appellate docket/report rows."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="sentinel",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_pa_ujs(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    return _adapter_result_observation(
        result,
        endpoint=PA_UJS_CASE_SEARCH_URL,
        started=started,
    )


def probe_pa_opinions(context: ProbeContext) -> ProbeObservation:
    """Verify one official appellate posting and its public PDF."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="sentinel",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_pa_opinions(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    return _adapter_result_observation(
        result,
        endpoint=PA_OPINIONS_API_URL,
        started=started,
    )


def probe_delaware_courtconnect(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the JP full-docket and Chancery-stub sentinels."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_delaware_courts(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    return _adapter_result_observation(
        result,
        endpoint=DELAWARE_COURTCONNECT_URL,
        started=started,
    )


def probe_delaware_opinions(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify one official archive row and its direct public PDF."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_delaware_opinions(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    return _adapter_result_observation(
        result,
        endpoint=DELAWARE_OPINIONS_URL,
        started=started,
    )


def probe_harris_recorder(context: ProbeContext) -> ProbeObservation:
    """Verify the index, registered-image boundary, and bulk product page."""

    started = time.perf_counter()
    client = HarrisRecorderClient(
        timeout=context.timeout,
        request_delay=max(
            0.2,
            _catalog_interval(context.catalog_decision),
        ),
        max_retries=max(0, context.max_attempts - 1),
    )
    try:
        payload = run_harris_recorder_sentinel(client)
    finally:
        close = getattr(client.session, "close", None)
        if callable(close):
            close()
    checks = payload.get("checks")
    exact_urls = payload.get("exact_urls")
    if (
        not isinstance(checks, Sequence)
        or isinstance(checks, (str, bytes))
        or any(not isinstance(check, Mapping) for check in checks)
    ):
        raise ValueError("Harris recorder sentinel lacks check objects")
    if not isinstance(exact_urls, Mapping):
        raise ValueError("Harris recorder sentinel lacks exact URLs")
    status = (
        ResultStatus.OK.value
        if payload.get("status") == "ok"
        else ResultStatus.UNAVAILABLE.value
    )
    return ProbeObservation(
        status=status,
        endpoint=HARRIS_RECORDER_SEARCH_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(
            [
                {
                    "name": check.get("name"),
                    "fields": sorted(check),
                }
                for check in checks
            ]
        ),
        artifact_sha256=sha256_fingerprint(dict(exact_urls)),
        result_count=len(checks),
        details={
            "checks": [dict(check) for check in checks],
            "exact_urls": dict(exact_urls),
        },
    )


def probe_harris_foreclosures(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify one foreclosure notice and its anonymous official PDF."""

    started = time.perf_counter()
    client = HarrisForeclosureClient(
        timeout=context.timeout,
        minimum_interval=max(
            0.2,
            _catalog_interval(context.catalog_decision),
        ),
        max_retries=max(0, context.max_attempts - 1),
    )
    try:
        payload = run_harris_foreclosure_sentinel(client)
    finally:
        close = getattr(client.session, "close", None)
        if callable(close):
            close()
    checks = payload.get("checks")
    exact_urls = payload.get("exact_urls")
    if (
        not isinstance(checks, Sequence)
        or isinstance(checks, (str, bytes))
        or any(not isinstance(check, Mapping) for check in checks)
    ):
        raise ValueError("Harris foreclosure sentinel lacks check objects")
    if not isinstance(exact_urls, Mapping):
        raise ValueError("Harris foreclosure sentinel lacks exact URLs")
    status = (
        ResultStatus.OK.value
        if payload.get("status") == "ok"
        else ResultStatus.UNAVAILABLE.value
    )
    return ProbeObservation(
        status=status,
        endpoint=HARRIS_FORECLOSURE_SEARCH_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(
            [
                {
                    "name": check.get("name"),
                    "fields": sorted(check),
                }
                for check in checks
            ]
        ),
        artifact_sha256=sha256_fingerprint(
            {
                "exact_urls": dict(exact_urls),
                "pdf_sha256": next(
                    (
                        check.get("sha256")
                        for check in checks
                        if check.get("name") == "anonymous_notice_pdf"
                    ),
                    None,
                ),
            }
        ),
        result_count=len(checks),
        details={
            "checks": [dict(check) for check in checks],
            "exact_urls": dict(exact_urls),
        },
    )


def probe_harris_court_bulk(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the catalog contract and a stable schema-workbook artifact."""

    started = time.perf_counter()
    client = HarrisCourtBulkClient(
        timeout=context.timeout,
        minimum_interval=max(
            0.2,
            _catalog_interval(context.catalog_decision),
        ),
        max_retries=max(0, context.max_attempts - 1),
    )
    try:
        payload = run_harris_court_bulk_sentinel(client)
    finally:
        close = getattr(client.session, "close", None)
        if callable(close):
            close()
    sentinel = payload.get("sentinel")
    catalog = payload.get("catalog")
    if (
        payload.get("status") != "ok"
        or not isinstance(
            sentinel,
            Mapping,
        )
        or not isinstance(catalog, Mapping)
    ):
        raise ValueError("Harris court bulk sentinel is incomplete")
    sentinel_record = dict(sentinel)
    catalog_record = dict(catalog)
    artifact_record = HarrisCourtBulkDatasetArtifact(
        index=0,
        section="Civil",
        published_date=HARRIS_COURT_BULK_SENTINEL_PUBLISHED_DATE,
        filename=HARRIS_COURT_BULK_SENTINEL_FILENAME,
        native_locator=HARRIS_COURT_BULK_SENTINEL_LOCATOR,
    ).to_record()
    stable_contract = {
        "source": HARRIS_COURT_BULK_SOURCE_METADATA.to_dict(),
        "jurisdiction": HARRIS_COURT_BULK_JURISDICTION.to_dict(),
        "catalog_transport": {
            "method": "GET_then_POST",
            "pagination": "unpaginated",
            "selection": "exact_live_catalog_member",
            "hidden_locator_field": "hiddenDownloadFile",
        },
        "shared_operations": [
            "discovery",
            "documents",
            "download",
            "probe",
        ],
        "implemented_ingest_families": [
            "Civil/activity",
            "Civil/case_summary",
            "Civil/party",
            "Criminal/dispositions",
            "Criminal/filings",
        ],
        "artifact_scope": ("bulk_extract_metadata_not_individual_filing_documents"),
    }
    schema_contract = {
        "catalog_artifact": inferred_schema([artifact_record]),
        "sentinel_fields": sorted(sentinel_record),
        "catalog_summary_fields": sorted(catalog_record),
        "row_occurrence_identity_fields": [
            "artifact_id",
            "source_row_number",
            "row_sha256",
        ],
        "generic_projection_kinds": [
            "case",
            "party",
            "attorney",
            "representation",
            "docket_entry",
            "case_event",
        ],
        "document_projection": False,
    }
    artifact_identity = {
        "source_id": HARRIS_COURT_BULK_SOURCE_ID,
        "catalog_url": HARRIS_COURT_BULK_CATALOG_URL,
        "record_kind": "bulk_dataset_artifact",
        "sentinel_native_locator": HARRIS_COURT_BULK_SENTINEL_LOCATOR,
        "sentinel_filename": HARRIS_COURT_BULK_SENTINEL_FILENAME,
        "sentinel_published_date": HARRIS_COURT_BULK_SENTINEL_PUBLISHED_DATE,
        "sentinel_format": "xlsx",
    }
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=HARRIS_COURT_BULK_CATALOG_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": stable_schema_sha256,
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "catalog_url": payload.get("catalog_url"),
                "sentinel": sentinel_record,
                "catalog": catalog_record,
            },
            "requests_made": 2,
        },
    )


def _vicourts_page_records(page: Any, description: str) -> list[Mapping[str, Any]]:
    records = getattr(page, "records", None)
    if not isinstance(records, Sequence) or isinstance(
        records,
        (str, bytes),
    ):
        raise ValueError(f"VI Courts {description} lacks a records sequence")
    if any(not isinstance(record, Mapping) for record in records):
        raise ValueError(f"VI Courts {description} returned a non-object record")
    return list(records)


def probe_vicourts(context: ProbeContext) -> ProbeObservation:
    """Probe C-Track discovery/search families and one legacy PDF sentinel."""
    started = time.perf_counter()
    client = VICourtsClient(
        session=system_trust_session(),
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    try:
        info = client.info()
        courts_page = client.list_courts(page_size=500)
        case_page = client.search_cases(
            VICOURTS_PROBE_CASE_NUMBER,
            field="number",
            match_mode="exact",
            requested_limit=1,
            page_size=1,
        )
        document_page = client.search_documents(
            exact="Epstein",
            requested_limit=1,
            page_size=1,
        )
        publication_page = client.search_publications(
            publication_number=VICOURTS_PROBE_PUBLICATION_NUMBER,
            requested_limit=1,
            page_size=1,
        )
        legacy = client.legacy_file(VICOURTS_PROBE_LEGACY_ITEM_ID)

        if not isinstance(info, Mapping):
            raise ValueError("VI Courts manage/info did not return an object")
        court_records = _vicourts_page_records(
            courts_page,
            "court directory",
        )
        if not court_records:
            raise ValueError("VI Courts court directory returned no courts")
        court_resource_ids = [
            str(record.get("resourceID") or "").strip() for record in court_records
        ]
        court_external_ids = [
            str(record.get("externalIdentifier") or "").strip()
            for record in court_records
        ]
        if (
            any(not value for value in court_resource_ids)
            or any(not value for value in court_external_ids)
            or len(set(court_resource_ids)) != len(court_resource_ids)
            or len(set(court_external_ids)) != len(court_external_ids)
        ):
            raise ValueError(
                "VI Courts directory has missing or duplicate court identities"
            )

        case_records = _vicourts_page_records(case_page, "case sentinel")
        if len(case_records) != 1:
            raise ValueError(
                "VI Courts exact case sentinel expected one record, "
                f"received {len(case_records)}"
            )
        case_header = case_records[0].get("caseHeader")
        if not isinstance(case_header, Mapping):
            raise ValueError("VI Courts case sentinel lacks caseHeader")
        observed_case_number = normalize_vicourts_case_number(
            str(case_header.get("caseNumber") or "")
        )
        if observed_case_number != VICOURTS_PROBE_CASE_NUMBER:
            raise ValueError("VI Courts case sentinel returned the wrong case number")

        document_records = _vicourts_page_records(
            document_page,
            "document-search sentinel",
        )
        publication_records = _vicourts_page_records(
            publication_page,
            "publication sentinel",
        )
        if not document_records:
            raise ValueError("VI Courts document-search sentinel returned no records")
        if not publication_records:
            raise ValueError("VI Courts publication sentinel returned no records")

        constants = info.get("constants")
        constants = constants if isinstance(constants, Mapping) else {}
        schema_payload = {
            "manage_info": inferred_schema([dict(info)]),
            "courts": getattr(courts_page, "schema", None),
            "cases": getattr(case_page, "schema", None),
            "documents": getattr(document_page, "schema", None),
            "publications": getattr(publication_page, "schema", None),
            "legacy_pdf": {
                "media_type": legacy.media_type,
                "signature": legacy.content[:5].decode(
                    "ascii",
                    errors="replace",
                ),
            },
        }
        artifact_payload = {
            "version": info.get("version"),
            "search_results_limit": constants.get("SEARCH_RESULTS_LIMIT"),
            "court_resource_ids": court_resource_ids,
            "case_number": observed_case_number,
            "case_instance_uuid": case_header.get("caseInstanceUUID"),
            "document_link_uuid": document_records[0].get("documentLinkUUID"),
            "publication_uuid": publication_records[0].get(
                "publicationUUID",
                publication_records[0].get("resourceID"),
            ),
            "legacy_item_id": VICOURTS_PROBE_LEGACY_ITEM_ID,
            "legacy_sha256": legacy.sha256,
        }
        return ProbeObservation(
            status=ResultStatus.OK.value,
            endpoint=VICOURTS_INFO_URL,
            latency_ms=(time.perf_counter() - started) * 1000,
            schema_sha256=sha256_fingerprint(schema_payload),
            artifact_sha256=sha256_fingerprint(artifact_payload),
            result_count=1,
            details={
                **artifact_payload,
                "court_count": len(court_records),
                "case_search_endpoint": VICOURTS_CASE_SEARCH_URL,
                "document_search_endpoint": VICOURTS_DOCUMENT_SEARCH_URL,
                "publication_search_endpoint": (VICOURTS_PUBLICATION_SEARCH_URL),
                "legacy_file_endpoint": VICOURTS_LEGACY_FILE_URL,
                "requests_made": client.request_count,
            },
        )
    finally:
        closer = getattr(client, "close", None)
        if not callable(closer):
            closer = getattr(
                getattr(client, "transport", None),
                "close",
                None,
            )
        if callable(closer):
            closer()


def probe_miami_dade_property(context: ProbeContext) -> ProbeObservation:
    """Fetch one known PA detail record and its matching parcel feature."""
    started = time.perf_counter()
    retry_policy = RetryPolicy(max_attempts=context.max_attempts)
    minimum_interval = _catalog_interval(context.catalog_decision)
    folio = "0101000000020"
    detail_client = MiamiDadePAClient(
        session=system_trust_session(),
        timeout=context.timeout,
        minimum_interval=minimum_interval,
        retry_policy=retry_policy,
    )
    detail = detail_client.detail(folio)
    geometry_client = ArcGISRESTClient(
        MIAMI_DADE_PARCEL_LAYER_URL,
        page_size=1,
        max_records=1,
        session=system_trust_session(),
        timeout=context.timeout,
        minimum_interval=minimum_interval,
        retry_policy=retry_policy,
    )
    fetched = geometry_client.query(
        where=f"FOLIO = '{folio}'",
        out_fields=MIAMI_DADE_PARCEL_FIELDS,
        parameters={
            "orderByFields": MIAMI_DADE_PARCEL_ORDER,
            "outSR": 4326,
        },
        requested_limit=1,
        max_records=1,
        return_geometry=False,
    )
    detail_count = int(detail is not None)
    geometry_count = len(fetched.records)
    if detail_count and geometry_count:
        status = ResultStatus.OK.value
    elif detail_count or geometry_count:
        status = ResultStatus.PARTIAL.value
    else:
        status = ResultStatus.NO_RESULTS.value
    combined_schema = {
        "property_detail": (
            inferred_schema([dict(detail)]) if detail is not None else None
        ),
        "parcel_geometry": fetched.schema_fingerprint,
    }
    return ProbeObservation(
        status=status,
        endpoint=MIAMI_DADE_PA_PROXY_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(combined_schema),
        result_count=detail_count,
        details={
            "sentinel_folio": folio,
            "detail_present": bool(detail_count),
            "geometry_feature_count": geometry_count,
            "geometry_endpoint": geometry_client.query_url,
            "requested_geometry_fields": list(MIAMI_DADE_PARCEL_FIELDS),
            "order_by": MIAMI_DADE_PARCEL_ORDER,
            "requests_made": detail_client.request_count + fetched.requests_made,
            "warnings": list(fetched.warnings),
        },
    )


def probe_miami_dade_recorder_public(
    context: ProbeContext,
) -> ProbeObservation:
    """Fetch the Clerk's public Official Records document-type vocabulary."""
    started = time.perf_counter()
    client = MiamiDadeRecorderClient(
        session=system_trust_session(),
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    labels = list(client.document_types())
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=MIAMI_DADE_DOCUMENT_TYPES_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint({"container": "array", "item_type": "string"}),
        artifact_sha256=sha256_fingerprint(labels),
        result_count=len(labels),
        details={
            "vocabulary": "official_records_document_types",
            "requests_made": client.request_count,
        },
    )


def probe_florida_acis(context: ProbeContext) -> ProbeObservation:
    """Verify ACIS court identity, calendar taxonomy, event, and hearings."""
    started = time.perf_counter()
    if FloridaACISClient is None:
        raise RuntimeError("Florida ACIS adapter is unavailable")
    client = FloridaACISClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )

    courts = tuple(client.courts())
    if len(courts) != 7:
        raise ValueError(
            "Florida ACIS court-directory sentinel expected 7 courts, "
            f"received {len(courts)}"
        )
    resource_ids = {court.resource_uuid.strip() for court in courts}
    external_ids = {court.external_id.strip() for court in courts}
    if (
        "" in resource_ids
        or "" in external_ids
        or len(resource_ids) != 7
        or len(external_ids) != 7
    ):
        raise ValueError(
            "Florida ACIS court-directory sentinel contains missing or "
            "duplicate court identities"
        )

    probe_courts = [
        court
        for court in courts
        if court.resource_uuid == FLORIDA_ACIS_CALENDAR_PROBE_COURT_UUID
        and court.external_id == FLORIDA_ACIS_CALENDAR_PROBE_COURT_ID
    ]
    if len(probe_courts) != 1:
        raise ValueError(
            "Florida ACIS calendar probe court is absent from the directory"
        )
    probe_court = probe_courts[0]

    session_types = [dict(row) for row in client.session_types()]
    probe_session_types = [
        row
        for row in session_types
        if str(row.get("courtSessionTypeID") or "").strip()
        == FLORIDA_ACIS_CALENDAR_PROBE_SESSION_TYPE_ID
        and str(row.get("courtSessionTypeName") or "").strip()
        == FLORIDA_ACIS_CALENDAR_PROBE_SESSION_TYPE_NAME
    ]
    if len(probe_session_types) != 1:
        raise ValueError("Florida ACIS Oral Argument calendar-session type changed")

    event_page = client.search_calendar_events(
        court=probe_court.resource_uuid,
        after=FLORIDA_ACIS_CALENDAR_PROBE_DATE,
        before=FLORIDA_ACIS_CALENDAR_PROBE_DATE,
        session_type=FLORIDA_ACIS_CALENDAR_PROBE_SESSION_TYPE_ID,
        event_name=FLORIDA_ACIS_CALENDAR_PROBE_EVENT_QUERY,
        requested_limit=1,
        page_size=25,
    )
    events = [dict(row) for row in event_page.records]
    if len(events) != 1:
        raise ValueError(
            "Florida ACIS calendar sentinel expected one matching event, "
            f"received {len(events)}"
        )
    event = events[0]
    if (
        str(event.get("eventUUID") or "").strip()
        != FLORIDA_ACIS_CALENDAR_PROBE_EVENT_UUID
        or str(event.get("courtID") or "").strip()
        != FLORIDA_ACIS_CALENDAR_PROBE_COURT_ID
        or not str(event.get("startDate") or "").startswith(
            FLORIDA_ACIS_CALENDAR_PROBE_DATE
        )
        or str(event.get("courtSessionType") or "").strip()
        != FLORIDA_ACIS_CALENDAR_PROBE_SESSION_TYPE_NAME
    ):
        raise ValueError("Florida ACIS calendar sentinel identity changed")

    hearing_page = client.event_hearings(
        probe_court.resource_uuid,
        FLORIDA_ACIS_CALENDAR_PROBE_EVENT_UUID,
        requested_limit=None,
        page_size=25,
    )
    hearings = [dict(row) for row in hearing_page.records]
    if not hearings:
        raise ValueError(
            "Florida ACIS calendar sentinel returned no attached case hearings"
        )
    hearing_summaries = []
    for hearing in hearings:
        case_header = hearing.get("caseHeader")
        if not isinstance(case_header, Mapping):
            raise ValueError("Florida ACIS calendar hearing lacks caseHeader")
        case_uuid = str(case_header.get("caseInstanceUUID") or "").strip()
        case_number = str(case_header.get("caseNumber") or "").strip()
        court_id = str(case_header.get("courtID") or "").strip()
        if (
            not case_uuid
            or not case_number
            or court_id != FLORIDA_ACIS_CALENDAR_PROBE_COURT_ID
        ):
            raise ValueError("Florida ACIS calendar hearing identity is incomplete")
        hearing_summaries.append(
            {
                "case_instance_uuid": case_uuid,
                "case_number": case_number,
                "caption": case_header.get("caseTitle")
                or case_header.get("caseCaption"),
                "start_date": hearing.get("startDate"),
                "hearing_type": hearing.get("hearingType"),
                "hearing_status": hearing.get("hearingStatus"),
                "order": hearing.get("orderBy"),
            }
        )

    stable_contract = {
        "source_id": "us-fl-acis",
        "calendar_capability": (
            "appellate_calendar_events_with_case_hearing_hydration"
        ),
        "endpoints": {
            "portal": FLORIDA_ACIS_CALENDAR_URL,
            "courts": FLORIDA_ACIS_COURTS_URL,
            "session_types": FLORIDA_ACIS_SESSION_TYPES_URL,
            "events": FLORIDA_ACIS_EVENT_SEARCH_URL,
            "event_hearings_template": (
                f"{FLORIDA_ACIS_API_ROOT}/courts/{{court_resource_uuid}}/"
                "cms/events/{event_uuid}/hearings"
            ),
        },
        "event_identity_fields": ["court_resource_uuid", "event_uuid"],
        "hearing_occurrence_identity_fields": [
            "event_uuid",
            "case_instance_uuid",
            "order",
        ],
        "native_filters": [
            "court",
            "event_date_range",
            "calendar_session_type",
            "event_name",
        ],
    }
    schema_contract = {
        "court_directory": inferred_schema([dict(court.raw) for court in courts]),
        "calendar_session_types": inferred_schema(session_types),
        "calendar_events": event_page.schema_fingerprint,
        "event_case_hearings": hearing_page.schema_fingerprint,
    }
    artifact_identity = {
        "source_id": "us-fl-acis",
        "contract": stable_contract,
        "court_resource_ids": sorted(resource_ids),
        "session_type_id": FLORIDA_ACIS_CALENDAR_PROBE_SESSION_TYPE_ID,
        "court_resource_uuid": probe_court.resource_uuid,
        "calendar_date": FLORIDA_ACIS_CALENDAR_PROBE_DATE,
        "event_uuid": FLORIDA_ACIS_CALENDAR_PROBE_EVENT_UUID,
    }
    rolling_observation = {
        "court_names": [court.display_name for court in courts],
        "calendar_session_type_count": len(session_types),
        "calendar_session_types": [
            {
                "id": row.get("courtSessionTypeID"),
                "name": row.get("courtSessionTypeName"),
            }
            for row in session_types
        ],
        "event": {
            "event_name": event.get("eventName"),
            "event_type": event.get("courtSessionType"),
            "event_date": event.get("startDate"),
            "location": event.get("location"),
            "room": event.get("room"),
            "panel_flag": event.get("panelFlag"),
        },
        "case_count": len(hearings),
        "case_hearings": hearing_summaries,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=FLORIDA_ACIS_CALENDAR_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "directory": "florida_appellate_courts",
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "requests_made": client.request_count,
        },
    )


def _fl_dor_release_sort_key(
    release: Mapping[str, Any],
) -> tuple[int, int]:
    return (
        int(release["assessment_year"]),
        1 if release.get("submission_code") == "F" else 0,
    )


def _fl_dor_manifest_snapshot(
    context: ProbeContext,
) -> dict[str, Any]:
    """Fetch current NAL, SDF, and GIS-PIN manifests plus one artifact probe."""

    adapter = query_fl_dor_property
    directory_requests = 0
    bulk_requests = 0

    def directory_opener(*args: Any, **kwargs: Any) -> Any:
        nonlocal directory_requests
        directory_requests += 1
        return adapter.urlopen(*args, **kwargs)

    directory = adapter.FloridaDORDirectoryClient(
        timeout=context.timeout,
        max_attempts=context.max_attempts,
        minimum_interval=_catalog_interval(context.catalog_decision),
        opener=directory_opener,
    )
    releases: dict[str, Mapping[str, Any]] = {}
    records_by_type: dict[str, list[dict[str, Any]]] = {}

    for dataset_type in ("nal", "sdf"):
        candidates = adapter._release_directories(directory, dataset_type)
        if not candidates:
            raise ValueError(
                f"Florida DOR {dataset_type.upper()} release directory is empty"
            )
        release = max(candidates, key=_fl_dor_release_sort_key)
        files = directory.list_files(str(release["server_relative_path"]))
        if not files:
            raise ValueError(f"Florida DOR {release['release_id']} has no artifacts")
        releases[dataset_type] = release
        records_by_type[dataset_type] = [
            adapter._manifest_record(release=release, file_row=file_row)
            for file_row in files
        ]

    year_rows = [
        row
        for row in directory.list_folders(adapter.MAP_DATA_ROOT)
        if adapter.RELEASE_FOLDER_RE.fullmatch(str(row.get("Name") or ""))
    ]
    year_rows.sort(
        key=lambda row: (
            int(str(row["Name"])[:4]),
            1 if str(row["Name"])[-1:] == "F" else 0,
        ),
        reverse=True,
    )
    gis_release: Mapping[str, Any] | None = None
    gis_files: list[dict[str, Any]] | None = None
    for year_row in year_rows:
        release_name = str(year_row["Name"])
        subfolder_name = f"{release_name} PIN"
        subfolders = directory.list_folders(str(year_row["ServerRelativeUrl"]))
        subfolder = next(
            (row for row in subfolders if str(row.get("Name")) == subfolder_name),
            None,
        )
        if subfolder is None:
            continue
        normalized = adapter._normalize_release_folder(
            dataset_type="gis-pin",
            row={
                **dict(year_row),
                "ServerRelativeUrl": subfolder["ServerRelativeUrl"],
                "TimeLastModified": subfolder.get("TimeLastModified"),
            },
            item_count=int(subfolder.get("ItemCount") or 0),
        )
        if normalized is None:
            raise ValueError(
                "Florida DOR GIS-PIN release folder no longer matches "
                "the year/stage contract"
            )
        files = directory.list_files(str(normalized["server_relative_path"]))
        if files:
            gis_release = normalized
            gis_files = files
            break
    if gis_release is None or gis_files is None:
        raise ValueError("Florida DOR GIS-PIN release directory is empty")
    releases["gis-pin"] = gis_release
    records_by_type["gis-pin"] = [
        adapter._manifest_record(release=gis_release, file_row=file_row)
        for file_row in gis_files
    ]

    component_snapshots: dict[str, dict[str, Any]] = {}
    expected_county_numbers = set(adapter.COUNTY_BY_NUMBER)
    for dataset_type in ("nal", "sdf", "gis-pin"):
        records = records_by_type[dataset_type]
        base_records = [
            record for record in records if record.get("artifact_role") == dataset_type
        ]
        observed_county_numbers = {
            int(record["county_dor_number"]) for record in base_records
        }
        sentinel_matches = [
            record for record in base_records if int(record["county_dor_number"]) == 12
        ]
        if len(sentinel_matches) != 1:
            raise ValueError(
                f"Florida DOR {dataset_type} current release does not have "
                "one Baker County sentinel artifact"
            )
        sentinel = dict(sentinel_matches[0])
        manifest = sentinel.get("manifest")
        if not isinstance(manifest, Mapping):
            raise ValueError(f"Florida DOR {dataset_type} sentinel lacks a manifest")
        if manifest.get("schema") != adapter._schema(dataset_type):
            raise ValueError(f"Florida DOR {dataset_type} manifest schema changed")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != 1:
            raise ValueError(
                f"Florida DOR {dataset_type} sentinel artifact shape changed"
            )
        release = releases[dataset_type]
        component_snapshots[dataset_type] = {
            "release_id": release.get("release_id"),
            "assessment_year": release.get("assessment_year"),
            "submission_stage": release.get("submission_stage"),
            "submission_code": release.get("submission_code"),
            "release_last_modified": release.get("last_modified"),
            "directory_artifact_count": release.get("artifact_count"),
            "manifest_record_count": len(records),
            "base_artifact_count": len(base_records),
            "observed_county_count": len(observed_county_numbers),
            "missing_county_dor_numbers": sorted(
                expected_county_numbers - observed_county_numbers
            ),
            "extra_county_dor_numbers": sorted(
                observed_county_numbers - expected_county_numbers
            ),
            "release_fingerprint": release.get("release_fingerprint"),
            "sentinel": {
                "canonical_ref": sentinel.get("canonical_ref"),
                "county_name": sentinel.get("county_name"),
                "county_dor_number": sentinel.get("county_dor_number"),
                "artifact": dict(artifacts[0]),
            },
        }

    _record, nal_artifact = adapter._select_exact_artifact(
        records_by_type["nal"],
        dataset_type="nal",
        county=(12, adapter.COUNTY_BY_NUMBER[12]),
    )

    def bulk_opener(*args: Any, **kwargs: Any) -> Any:
        nonlocal bulk_requests
        bulk_requests += 1
        return adapter.urlopen(*args, **kwargs)

    artifact_probe = BulkTransferClient(
        timeout=context.timeout,
        max_attempts=context.max_attempts,
        opener=bulk_opener,
    ).probe(
        nal_artifact,
        sample_bytes=context.sample_bytes or 4096,
    )
    return {
        "components": component_snapshots,
        "artifact_probe": artifact_probe.to_dict(),
        "requests_made": directory_requests + bulk_requests,
        "directory_requests": directory_requests,
        "artifact_probe_requests": bulk_requests,
    }


def probe_fl_dor_property(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify current statewide DOR release manifests and one ZIP sentinel."""

    adapter = query_fl_dor_property
    started = time.perf_counter()
    snapshot = _fl_dor_manifest_snapshot(context)
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "dataset_types": ["nal", "sdf", "gis-pin", "gis-par"],
        "monitored_dataset_types": ["nal", "sdf", "gis-pin"],
        "county_count": len(adapter.COUNTIES),
        "county_number_crosswalk": [
            {"county_dor_number": number, "county_name": name}
            for number, name in adapter.COUNTIES
        ],
        "directory_roots": {
            "tax_roll": adapter.TAX_ROLL_ROOT,
            "map_data": adapter.MAP_DATA_ROOT,
        },
        "source_omissions": dict(adapter.SOURCE_OMISSIONS),
        "shared_operations": [
            "discovery",
            "download",
            "manifest",
            "probe",
            "releases",
        ],
    }
    schema_contract = {
        "release_folder_pattern": (adapter.RELEASE_FOLDER_RE.pattern),
        "release_identity_fields": [
            "dataset_type",
            "assessment_year",
            "submission_stage",
            "county_dor_number",
            "artifact_role",
        ],
        "manifest_fields": [
            "canonical_ref",
            "county_name",
            "county_dor_number",
            "assessment_year",
            "dataset_type",
            "submission_stage",
            "artifact_role",
            "manifest",
        ],
        "dataset_schemas": {
            dataset_type: adapter._schema(dataset_type)
            for dataset_type in ("nal", "sdf", "gis-pin")
        },
        "named_projection_columns": {
            "nal": sorted(adapter.NAL_REQUIRED_PUBLIC_COLUMNS),
            "sdf": sorted(adapter.SDF_REQUIRED_PUBLIC_COLUMNS),
            "gis-pin": ["PARCELNO"],
        },
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "record_kind": "county_bulk_release_manifest",
        "monitored_dataset_types": ["nal", "sdf", "gis-pin"],
        "sentinel_county_dor_number": 12,
        "sentinel_county_name": adapter.COUNTY_BY_NUMBER[12],
    }
    probe = dict(snapshot["artifact_probe"])
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.SOURCE_PAGE,
        http_status=int(probe["http_status"]),
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=3,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "stable_contract_sha256": stable_contract_sha256,
            "stable_schema_sha256": stable_schema_sha256,
            "rolling_observation": {
                "components": snapshot["components"],
                "nal_artifact_probe": probe,
            },
            "requests_made": snapshot["requests_made"],
            "directory_requests": snapshot["directory_requests"],
            "artifact_probe_requests": snapshot["artifact_probe_requests"],
        },
    )


def _counted_bulk_probe(
    artifact: BulkArtifact,
    context: ProbeContext,
    *,
    user_agent: str = "Ithildin-Public-Records/1.0",
) -> tuple[dict[str, Any], int]:
    """Probe one bulk artifact and report the transport requests actually made."""

    requests_made = 0

    def opener(*args: Any, **kwargs: Any) -> Any:
        nonlocal requests_made
        requests_made += 1
        return urlopen(*args, **kwargs)

    probe = BulkTransferClient(
        timeout=context.timeout,
        max_attempts=context.max_attempts,
        user_agent=user_agent,
        opener=opener,
    ).probe(
        artifact,
        sample_bytes=context.sample_bytes or 4096,
    )
    return probe.to_dict(), requests_made


OHIO_FRANKLIN_AUDITOR_BULK_EXPECTED_REQUESTS = 9


def probe_ohio_franklin_auditor_bulk(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify the Auditor directory contract and one current workbook sample."""

    adapter = query_ohio_franklin_auditor_bulk
    started = time.perf_counter()
    client = adapter.FranklinDirectoryClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    root = client.listing(adapter.DIRECTORY_ROOT)
    required_roots = {
        "Daily_Conveyances",
        "GIS_Shapefiles",
        "Outside_User_Files",
        "Parcel_CSV",
    }
    observed_roots = {
        entry.name for entry in root.entries if entry.is_directory
    }
    if not required_roots.issubset(observed_roots):
        raise ValueError(
            "Franklin Auditor root listing lost required data families: "
            f"{sorted(required_roots - observed_roots)}"
        )

    current_releases = {
        family: adapter.discover_releases(client, family)[0]
        for family in adapter.FAMILY_CHOICES
    }
    daily_artifacts = adapter.artifacts_for_release(
        client, current_releases["daily-conveyances"]
    )
    if len(daily_artifacts) != 1:
        raise ValueError(
            "Franklin Auditor current daily release no longer resolves to one "
            "workbook"
        )
    sentinel = daily_artifacts[0]
    artifact_probe, bulk_requests = _counted_bulk_probe(
        adapter._bulk_artifact(sentinel),
        context,
    )
    adapter.validate_artifact_probe(sentinel, artifact_probe)

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "official_data_landing": adapter.DATA_LANDING_URL,
        "directory_root": adapter.DIRECTORY_ROOT,
        "required_roots": sorted(required_roots),
        "families": {
            key: adapter.FAMILY_CONTRACTS[key].to_record()
            for key in adapter.FAMILY_CHOICES
        },
        "identity_contract": {
            "release": (
                "family plus source-published release directory or filename date"
            ),
            "artifact": "official relative path",
            "artifact_version": (
                "directory size and modified time, validators when present, "
                "and computed SHA-256 after download"
            ),
            "row_occurrence": (
                "release, artifact SHA-256, archive member and worksheet when "
                "applicable, and physical row"
            ),
            "parcel_join": "Franklin County GEOID plus source parcel identifier",
        },
        "shared_operations": [
            "discovery",
            "download",
            "manifest",
            "parcel",
            "probe",
            "releases",
            "search",
        ],
    }
    schema_contract = {
        "outside_release_pattern": adapter._OUTSIDE_RELEASE_RE.pattern,
        "daily_filename_pattern": adapter._DAILY_RE.pattern,
        "gis_filename_pattern": adapter._GIS_PREFIX_RE.pattern,
        "record_families": list(adapter.RECORD_FAMILY_CHOICES),
        "parcel_header_aliases": sorted(adapter._PARCEL_HEADERS),
        "date_header_aliases": sorted(adapter._DATE_HEADERS),
        "price_header_aliases": sorted(adapter._PRICE_HEADERS),
        "row_provenance_fields": [
            "release_id",
            "release_date",
            "artifact_sha256",
            "archive_member",
            "worksheet",
            "source_row_number",
            "raw_headers",
            "raw_values",
            "source_fields",
        ],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "family": "daily-conveyances",
        "selection": "current source-published daily workbook",
        "format": "xlsx",
        "identity": "official relative path within the selected release",
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    requests_made = client.request_count + bulk_requests
    if requests_made != OHIO_FRANKLIN_AUDITOR_BULK_EXPECTED_REQUESTS:
        raise ValueError(
            "Franklin Auditor bulk probe request count changed: "
            f"expected {OHIO_FRANKLIN_AUDITOR_BULK_EXPECTED_REQUESTS}, "
            f"observed {requests_made}"
        )
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.DIRECTORY_ROOT,
        http_status=int(artifact_probe["http_status"]),
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "stable_contract_sha256": stable_contract_sha256,
            "stable_schema_sha256": stable_schema_sha256,
            "rolling_observation": {
                "root_listing": root.to_dict(),
                "observed_root_names": sorted(observed_roots),
                "current_releases": {
                    family: release.to_record()
                    for family, release in current_releases.items()
                },
                "sampled_artifact": sentinel,
                "artifact_probe": artifact_probe,
            },
            "requests_made": requests_made,
            "directory_requests": client.request_count,
            "artifact_probe_requests": bulk_requests,
        },
    )


def _hcad_property_manifest_snapshot(
    context: ProbeContext,
) -> dict[str, Any]:
    """Fetch the current real-property CAMA manifest and one ZIP sentinel."""

    adapter = query_harris_property
    client = adapter.HCADManifestClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=_catalog_interval(context.catalog_decision),
    )
    years = client.list_tax_years()
    if not years:
        raise ValueError("HCAD CAMA tax-year manifest is empty")
    current_year = max(int(row["tax_year"]) for row in years)
    certification = client.certification(current_year)
    artifacts = client.downloads(current_year, "real-property")
    expected_filenames = {
        "Real_acct_owner.zip",
        "Real_acct_ownership_history.zip",
        "Real_building_land.zip",
        "Real_jur_exempt.zip",
        "Code_description_real.zip",
    }
    observed_filenames = {str(row["filename"]) for row in artifacts}
    if observed_filenames != expected_filenames:
        raise ValueError(
            "HCAD CAMA real-property artifact set changed: "
            f"{sorted(observed_filenames)}"
        )
    sentinel = next(
        row for row in artifacts if row["filename"] == "Real_acct_owner.zip"
    )
    artifact_probe, bulk_requests = _counted_bulk_probe(
        BulkArtifact(
            artifact_id=str(sentinel["filename"]),
            url=str(sentinel["url"]),
            filename=str(sentinel["filename"]),
            media_type="application/zip",
            archive_format="zip",
        ),
        context,
    )
    return {
        "available_tax_year_count": len(years),
        "available_tax_years": sorted(
            (int(row["tax_year"]) for row in years),
            reverse=True,
        ),
        "current_tax_year": current_year,
        "certification": certification,
        "real_property_artifact_count": len(artifacts),
        "real_property_artifact_filenames": sorted(observed_filenames),
        "sentinel_artifact": {
            "filename": sentinel["filename"],
            "label": sentinel["label"],
            "description": sentinel["description"],
            "probe": artifact_probe,
        },
        "requests_made": client.request_count + bulk_requests,
        "manifest_requests": client.request_count,
        "artifact_probe_requests": bulk_requests,
    }


def probe_hcad_property(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify HCAD's current CAMA release contract and one owner ZIP."""

    adapter = query_harris_property
    started = time.perf_counter()
    snapshot = _hcad_property_manifest_snapshot(context)
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "manifest_endpoints": {
            "tax_years": adapter.TAX_YEARS_ENDPOINT,
            "certification": adapter.CERTIFICATION_ENDPOINT,
            "downloads": adapter.DOWNLOADS_ENDPOINT,
        },
        "release_groups": dict(adapter.GROUPS),
        "selected_group": "real-property",
        "shared_operations": [
            "discovery",
            "download",
            "manifest",
            "probe",
            "releases",
        ],
        "record_boundaries": {
            "native_account_key": "acct",
            "ownership_history_occurrence": (
                "physical row position retained separately from account identity"
            ),
            "deed_fields": (
                "appraisal observations and county-clerk pivots, not controlling "
                "title instruments"
            ),
        },
    }
    schema_contract = {
        "endpoint_schema": adapter.ENDPOINT_SCHEMA,
        "endpoint_schema_sha256": adapter.ENDPOINT_SCHEMA_FINGERPRINT,
        "declared_data_model": adapter.DECLARED_DATA_MODEL,
        "codebook_url": adapter.CODEBOOK_URL,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "record_kind": "hcad_cama_real_property_release",
        "tax_year_selection": "latest_available",
        "group": "real-property",
        "expected_artifact_filenames": [
            "Code_description_real.zip",
            "Real_acct_owner.zip",
            "Real_acct_ownership_history.zip",
            "Real_building_land.zip",
            "Real_jur_exempt.zip",
        ],
        "sentinel_filename": "Real_acct_owner.zip",
    }
    probe = snapshot["sentinel_artifact"]["probe"]
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.SOURCE_PAGE,
        http_status=int(probe["http_status"]),
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "stable_contract_sha256": stable_contract_sha256,
            "stable_schema_sha256": stable_schema_sha256,
            "rolling_observation": snapshot,
            "requests_made": snapshot["requests_made"],
            "manifest_requests": snapshot["manifest_requests"],
            "artifact_probe_requests": snapshot["artifact_probe_requests"],
        },
    )


def _hcad_gis_snapshot(
    context: ProbeContext,
) -> dict[str, Any]:
    """Fetch the HCAD GIS manifests, MapServer schema, and bounded sentinels."""

    adapter = query_hcad_gis
    manifest_client = adapter.HCADGISManifestClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=_catalog_interval(context.catalog_decision),
    )
    releases, artifacts_by_release = adapter.release_inventory(manifest_client)
    current = next(
        (
            release
            for release in releases
            if release["release_kind"] == "rolling_snapshot"
        ),
        None,
    )
    if current is None:
        raise ValueError("HCAD GIS current release is missing")
    current_artifacts = artifacts_by_release[str(current["release_id"])]
    parcel_matches = [
        artifact
        for artifact in current_artifacts
        if str(artifact["filename"]).casefold() == "parcels.zip"
    ]
    if len(parcel_matches) != 1:
        raise ValueError("HCAD GIS current release lacks one Parcels.zip")
    parcel = parcel_matches[0]
    artifact_probe, bulk_requests = _counted_bulk_probe(
        BulkArtifact(
            artifact_id=str(parcel["artifact_id"]),
            url=str(parcel["url"]),
            filename=str(parcel["filename"]),
            media_type="application/zip",
            archive_format="zip",
        ),
        context,
    )

    map_client = adapter.arcgis_keyset.BoundedArcGISClient(
        adapter.MAP_MANIFEST,
        page_size=1,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    try:
        metadata = map_client.fetch_metadata()
        map_schema_sha256, map_max_record_count = (
            adapter.arcgis_keyset.metadata_contract(
                adapter.MAP_MANIFEST,
                metadata,
            )
        )
        map_total_count = map_client.fetch_count("1=1")
        tax_year_payload = map_client._request_json(
            adapter.MAP_MANIFEST.query_url,
            params={
                "where": "1=1",
                "outFields": "tax_year",
                "returnDistinctValues": "true",
                "returnGeometry": "false",
                "orderByFields": "tax_year ASC",
                "f": "json",
            },
        )
        tax_year_features = tax_year_payload.get("features")
        if not isinstance(tax_year_features, list) or any(
            not isinstance(feature, Mapping) for feature in tax_year_features
        ):
            raise ValueError("HCAD GIS MapServer distinct tax-year response changed")
        map_tax_years = sorted(
            {
                adapter.arcgis_keyset.feature_attributes(feature).get("tax_year")
                for feature in tax_year_features
            },
            key=lambda value: (value is None, str(value)),
        )
        sentinel_features = map_client.fetch_page(
            where="OBJECTID = 1",
            record_count=1,
            return_geometry=False,
        )
        if len(sentinel_features) != 1:
            raise ValueError("HCAD GIS MapServer OBJECTID=1 sentinel is missing")
        map_sentinel = dict(
            adapter.arcgis_keyset.feature_attributes(sentinel_features[0])
        )
    finally:
        map_client.close()

    historical_years = sorted(
        (
            int(release["snapshot_year"])
            for release in releases
            if release["release_kind"] == "historical_snapshot"
        ),
        reverse=True,
    )
    return {
        "bulk": {
            "release_id": current["release_id"],
            "last_updated": current["effective_at"],
            "component_artifact_count": current["component_artifact_count"],
            "combined_bundle_count": current["combined_bundle_count"],
            "artifact_count": current["artifact_count"],
            "artifact_filenames": sorted(
                str(artifact["filename"]) for artifact in current_artifacts
            ),
            "historical_snapshot_years": historical_years,
            "parcels_artifact_probe": artifact_probe,
        },
        "mapserver": {
            "layer_url": adapter.MAPSERVER_LAYER_URL,
            "schema_sha256": map_schema_sha256,
            "max_record_count": map_max_record_count,
            "total_feature_count": map_total_count,
            "tax_year_values": map_tax_years,
            "sentinel": {
                key: map_sentinel.get(key)
                for key in (
                    "OBJECTID",
                    "HCAD_NUM",
                    "acct_num",
                    "tax_year",
                    "GlobalID",
                )
            },
        },
        "requests_made": manifest_client.request_count + bulk_requests + 4,
        "manifest_requests": manifest_client.request_count,
        "artifact_probe_requests": bulk_requests,
        "mapserver_requests": 4,
    }


def probe_hcad_gis(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify distinct HCAD bulk and MapServer representation contracts."""

    adapter = query_hcad_gis
    started = time.perf_counter()
    snapshot = _hcad_gis_snapshot(context)
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "bulk_endpoints": {
            "last_update": adapter.LAST_UPDATE_ENDPOINT,
            "current_components": adapter.FILES_ENDPOINT,
            "current_bundle": adapter.PUBLIC_ENDPOINT,
            "historical_parcels": adapter.PRIOR_YEAR_ENDPOINT,
        },
        "mapserver_layer": adapter.MAPSERVER_LAYER_URL,
        "shared_operations": [
            "account",
            "address",
            "discovery",
            "download",
            "manifest",
            "map",
            "owner",
            "parcel",
            "probe",
            "releases",
            "search",
        ],
        "representation_boundaries": {
            "bulk": (
                "HCAD current and historical ZIP publications; current "
                "Parcels.zip representation is inspected, not locally decoded"
            ),
            "mapserver": (
                "official Harris County-hosted representation of HCAD data, "
                "not independent corroboration"
            ),
            "freshness": (
                "bulk publication date and MapServer tax_year are separate observations"
            ),
        },
    }
    schema_contract = {
        "bulk_endpoint_schema": adapter.ENDPOINT_SCHEMA,
        "bulk_endpoint_schema_sha256": (adapter.ENDPOINT_SCHEMA_FINGERPRINT),
        "bulk_schema_reference": adapter.SCHEMA_URL,
        "bulk_projection": {
            "epsg": 2278,
            "wkid": 102740,
            "parcel_join_field": "HCAD_NUM",
        },
        "map_manifest": adapter.MAP_MANIFEST.contract_record(),
        "map_schema_sha256": snapshot["mapserver"]["schema_sha256"],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "bulk_record_kind": "hcad_gis_release_artifact",
        "bulk_current_selector": "Parcels.zip",
        "historical_filename_pattern": adapter.PRIOR_FILENAME_RE.pattern,
        "parcel_join_field": "HCAD_NUM",
        "map_feature_occurrence_field": "OBJECTID",
        "map_record_identity": (
            "HCAD_NUM identifies the parcel account while OBJECTID retains "
            "feature occurrence; HCAD_NUM is not assumed unique"
        ),
    }
    probe = snapshot["bulk"]["parcels_artifact_probe"]
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.SOURCE_PAGE,
        http_status=int(probe["http_status"]),
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "stable_contract_sha256": stable_contract_sha256,
            "stable_schema_sha256": stable_schema_sha256,
            "rolling_observation": {
                "bulk": snapshot["bulk"],
                "mapserver": {
                    key: value
                    for key, value in snapshot["mapserver"].items()
                    if key != "schema_sha256"
                },
            },
            "requests_made": snapshot["requests_made"],
            "manifest_requests": snapshot["manifest_requests"],
            "artifact_probe_requests": snapshot["artifact_probe_requests"],
            "mapserver_requests": snapshot["mapserver_requests"],
        },
    )


def _txgio_land_parcels_snapshot(
    context: ProbeContext,
) -> dict[str, Any]:
    """Fetch the current TxGIO collection, resources, and one small ZIP."""

    adapter = query_txgio_land_parcels
    client = adapter.TxGIODataHubClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=_catalog_interval(context.catalog_decision),
    )
    releases = client.releases()
    if not releases:
        raise ValueError("TxGIO land-parcel collection inventory is empty")
    current = releases[0]
    resources = client.resources(str(current["collection_id"]))
    county_resources = [
        resource for resource in resources if resource["scope"] == "county"
    ]
    statewide_resources = [
        resource for resource in resources if resource["scope"] == "state"
    ]
    if not county_resources or len(statewide_resources) != 1:
        raise ValueError(
            "TxGIO current release must contain county archives and one "
            "statewide aggregate"
        )
    observed_counties = {
        adapter._county_key(str(resource["county_name"]))
        for resource in county_resources
    }
    missing_counties = [] if "donley" in observed_counties else ["Donley"]
    sentinel = min(
        county_resources,
        key=lambda resource: (
            int(resource["expected_size"]),
            str(resource["jurisdiction_fips"]),
        ),
    )
    artifact_probe, bulk_requests = _counted_bulk_probe(
        BulkArtifact(
            artifact_id=str(sentinel["resource_id"]),
            url=str(sentinel["url"]),
            filename=str(sentinel["filename"]),
            media_type="application/zip",
            archive_format="zip",
            expected_size=int(sentinel["expected_size"]),
        ),
        context,
        user_agent=adapter.DOWNLOAD_USER_AGENT,
    )
    return {
        "release_count": len(releases),
        "collection": {
            key: current.get(key)
            for key in (
                "collection_id",
                "acquisition_date",
                "publication_date",
                "availability",
                "file_type",
                "spatial_reference",
                "license_name",
                "license_abbreviation",
                "county_count_declared",
            )
        },
        "resource_count": len(resources),
        "county_artifact_count": len(county_resources),
        "statewide_artifact_count": len(statewide_resources),
        "missing_counties": missing_counties,
        "sentinel": {
            key: sentinel.get(key)
            for key in (
                "resource_id",
                "filename",
                "expected_size",
                "scope",
                "jurisdiction_fips",
                "county_fips",
                "county_name",
            )
        }
        | {"probe": artifact_probe},
        "statewide_aggregate": {
            key: statewide_resources[0].get(key)
            for key in (
                "resource_id",
                "filename",
                "expected_size",
                "scope",
                "jurisdiction_fips",
            )
        },
        "requests_made": client.request_count + bulk_requests,
        "manifest_requests": client.request_count,
        "artifact_probe_requests": bulk_requests,
    }


def probe_txgio_land_parcels(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify TxGIO's current mixed-scope release and one county ZIP."""

    adapter = query_txgio_land_parcels
    started = time.perf_counter()
    snapshot = _txgio_land_parcels_snapshot(context)
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "endpoints": {
            "collections": adapter.COLLECTIONS_ENDPOINT,
            "resources": adapter.RESOURCES_ENDPOINT,
            "schema": adapter.SCHEMA_URL,
            "mapserver": adapter.CURRENT_MAPSERVER_URL,
            "appraisal_directory": adapter.APPRAISAL_DIRECTORY_URL,
        },
        "download_user_agent": adapter.DOWNLOAD_USER_AGENT,
        "download_user_agent_source": (adapter.OFFICIAL_DOWNLOADER_SOURCE),
        "coverage_expectation": {
            "texas_county_count": 254,
            "known_current_gap_checked": "Donley",
            "resource_scopes": ["county", "state"],
        },
        "shared_operations": [
            "address",
            "discovery",
            "download",
            "manifest",
            "map",
            "owner",
            "parcel",
            "probe",
            "releases",
            "search",
        ],
        "representation_boundaries": {
            "query": (
                "search, owner, address, and parcel scan an explicitly "
                "downloaded local county archive"
            ),
            "map": (
                "returns the aligned shapefile reference and projection, "
                "not decoded feature geometry"
            ),
            "mapserver": (
                "interactive representation of this dataset, not independent "
                "corroboration"
            ),
        },
    }
    schema_contract = {
        "declared_schema": adapter.DECLARED_SCHEMA,
        "logical_to_physical_candidates": {
            key: list(value) for key, value in adapter.PUBLISHED_FIELDS.items()
        },
        "resource_filename_pattern": adapter.RESOURCE_FILENAME_RE.pattern,
        "published_logical_field_count": len(adapter.PUBLISHED_FIELDS),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "record_kind": "txgio_county_land_parcel_archive",
        "collection_identity_field": "collection_id",
        "resource_identity_field": "resource_id",
        "scope_identity_field": "jurisdiction_fips",
        "archive_scopes": ["county", "state"],
        "sentinel_selection": (
            "smallest current county artifact, then jurisdiction FIPS"
        ),
        "feature_identity": (
            "FIPS plus PROP_ID/GEO_ID with DBF row position retained as a "
            "separate feature occurrence"
        ),
    }
    probe = snapshot["sentinel"]["probe"]
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.LANDING_URL,
        http_status=int(probe["http_status"]),
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "stable_contract_sha256": stable_contract_sha256,
            "stable_schema_sha256": stable_schema_sha256,
            "rolling_observation": snapshot,
            "requests_made": snapshot["requests_made"],
            "manifest_requests": snapshot["manifest_requests"],
            "artifact_probe_requests": snapshot["artifact_probe_requests"],
        },
    )


def _montana_cadastral_snapshot(
    context: ProbeContext,
) -> dict[str, Any]:
    """Fetch one live parcel, all county groups, and current bulk aliases."""

    adapter = query_montana_cadastral
    interval = _catalog_interval(context.catalog_decision)
    client = adapter.MontanaCadastralClient(
        page_size=1,
        timeout=context.timeout,
        minimum_interval=interval,
        retry_attempts=context.max_attempts,
    )
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--page-size",
            "1",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(interval),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    result = adapter.execute(args, client=client, log_results=False)
    if result.status is not ResultStatus.OK:
        errors = [error.to_dict() for error in result.errors]
        raise ValueError(
            "Montana cadastral live probe failed: "
            + json.dumps(errors, sort_keys=True)
        )
    if len(result.records) != 1:
        raise ValueError("Montana cadastral probe expected one parcel feature")
    live_probe_requests = client.request_count

    county_rows = [dict(row) for row in client.fetch_county_statistics()]
    county_group_requests = client.request_count - live_probe_requests
    release_discovery = adapter.discover_releases(client)
    directory_requests = (
        client.request_count - live_probe_requests - county_group_requests
    )
    return {
        "record": dict(result.records[0]),
        "warnings": list(result.warnings),
        "county_rows": county_rows,
        "release_discovery": release_discovery,
        "requests_made": client.request_count,
        "live_probe_requests": live_probe_requests,
        "county_group_requests": county_group_requests,
        "directory_requests": directory_requests,
    }


def probe_montana_cadastral(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify Montana's live layer, county crosswalk, and bulk inventory."""

    adapter = query_montana_cadastral
    started = time.perf_counter()
    observation = _montana_cadastral_snapshot(context)
    record = observation["record"]
    identity = (
        dict(record["identity"])
        if isinstance(record.get("identity"), Mapping)
        else {}
    )
    jurisdiction = (
        dict(record["jurisdiction"])
        if isinstance(record.get("jurisdiction"), Mapping)
        else {}
    )
    source_snapshot = (
        dict(record["source_snapshot"])
        if isinstance(record.get("source_snapshot"), Mapping)
        else {}
    )
    total_features = source_snapshot.get("total_features")
    features_with_parcel_id = source_snapshot.get("features_with_parcel_id")
    features_without_parcel_id = source_snapshot.get(
        "features_without_parcel_id"
    )
    prefix = jurisdiction.get("orion_county_prefix")
    sentinel_county = (
        adapter.COUNTY_BY_PREFIX.get(prefix)
        if isinstance(prefix, int) and not isinstance(prefix, bool)
        else None
    )
    contract_checks = {
        "source_id": record.get("source_id") == adapter.SOURCE_ID,
        "record_type": record.get("record_type") == "parcel_feature_occurrence",
        "source_occurrence": (
            identity.get("occurrence_key") in {"GlobalID", "OBJECTID"}
            and isinstance(record.get("source_record_id"), str)
            and bool(record.get("source_record_id"))
        ),
        "object_id": (
            isinstance(identity.get("object_id"), int)
            and not isinstance(identity.get("object_id"), bool)
        ),
        "parcel_join": (
            identity.get("parcel_join_key") == "PARCELID"
            and identity.get("parcel_join_key_present") is True
            and isinstance(identity.get("parcel_id"), str)
            and bool(identity.get("parcel_id"))
        ),
        "county_crosswalk": (
            sentinel_county is not None
            and jurisdiction.get("county_geoid") == sentinel_county.geoid
            and jurisdiction.get("county_name") == sentinel_county.name
        ),
        "geometry": isinstance(record.get("geometry"), Mapping),
        "schema_fingerprint": (
            isinstance(source_snapshot.get("schema_fingerprint"), str)
            and len(source_snapshot["schema_fingerprint"]) == 64
        ),
        "data_fingerprint": (
            isinstance(source_snapshot.get("data_fingerprint"), str)
            and len(source_snapshot["data_fingerprint"]) == 64
        ),
        "parcel_id_counts": (
            isinstance(total_features, int)
            and not isinstance(total_features, bool)
            and total_features > 0
            and isinstance(features_with_parcel_id, int)
            and not isinstance(features_with_parcel_id, bool)
            and isinstance(features_without_parcel_id, int)
            and not isinstance(features_without_parcel_id, bool)
            and features_with_parcel_id + features_without_parcel_id
            == total_features
        ),
    }

    county_rows = observation["county_rows"]
    observed_prefixes: set[int] = set()
    observed_geoids: set[str] = set()
    county_feature_total = 0
    county_coverage: list[dict[str, Any]] = []
    for row in county_rows:
        row_prefix = row.get("COUNTYCD")
        feature_count = row.get("feature_count")
        county = (
            adapter.COUNTY_BY_PREFIX.get(row_prefix)
            if isinstance(row_prefix, int) and not isinstance(row_prefix, bool)
            else None
        )
        if (
            county is None
            or isinstance(feature_count, bool)
            or not isinstance(feature_count, int)
            or feature_count < 0
        ):
            raise ValueError("Montana cadastral county coverage row changed")
        if (
            row.get("CountyName") != county.name
            or row.get("CountyAbbr") != county.abbreviation
        ):
            raise ValueError(
                "Montana cadastral county group conflicts with the "
                "ORION-to-Census crosswalk"
            )
        observed_prefixes.add(county.prefix)
        observed_geoids.add(county.geoid)
        county_feature_total += feature_count
        county_coverage.append(
            {
                "orion_county_prefix": county.prefix,
                "county_geoid": county.geoid,
                "county_name": county.name,
                "feature_count": feature_count,
            }
        )
    contract_checks["all_56_county_prefixes"] = (
        observed_prefixes == set(adapter.COUNTY_BY_PREFIX)
    )
    contract_checks["all_56_county_geoids"] = (
        observed_geoids == set(adapter.COUNTY_BY_GEOID)
    )
    contract_checks["county_counts_reconcile"] = (
        isinstance(total_features, int)
        and county_feature_total == total_features
    )

    releases = observation["release_discovery"]
    contract_checks.update(
        {
            "parcel_county_directories": (
                releases.get("parcel_county_directory_count") == 56
            ),
            "orion_county_archives": (
                releases.get("orion_county_archive_count") == 56
            ),
            "parcel_directory_coverage": not (
                releases.get("missing_parcel_county_directories")
                or releases.get("unexpected_parcel_county_directories")
            ),
            "orion_archive_coverage": not releases.get(
                "missing_orion_county_prefixes"
            ),
            "release_fingerprint": (
                isinstance(releases.get("release_discovery_fingerprint"), str)
                and len(releases["release_discovery_fingerprint"]) == 64
            ),
        }
    )
    failed_checks = [name for name, passed in contract_checks.items() if not passed]
    if failed_checks:
        raise ValueError(
            "Montana cadastral source, identity, county, or release contract "
            "changed: " + ", ".join(failed_checks)
        )

    county_crosswalk = [
        {
            "orion_county_prefix": county.prefix,
            "county_name": county.name,
            "county_abbreviation": county.abbreviation,
            "parcel_directory": county.directory,
            "census_county_geoid": county.geoid,
        }
        for county in adapter.COUNTIES
    ]
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "live_layer": {
            "dataset_id": adapter.SOURCE_METADATA.dataset_id,
            "service_url": adapter.SERVICE_URL,
            "layer_url": adapter.LAYER_URL,
            "query_url": adapter.QUERY_URL,
            "layer_id": 1,
        },
        "bulk_endpoints": {
            "root": adapter.BULK_ROOT,
            "parcel_archives": adapter.PARCEL_ROOT,
            "orion_archives": adapter.ORION_ROOT,
        },
        "identity": {
            "source_occurrence_keys": ["GlobalID", "OBJECTID"],
            "transport_cursor_key": "OBJECTID",
            "nullable_parcel_join_key": "PARCELID",
            "property_attribute_keys": ["PropertyID", "AssessmentCode"],
            "county_crosswalk": county_crosswalk,
            "orion_prefix_is_census_fips": False,
        },
        "shared_operations": [
            "account",
            "address",
            "count",
            "discovery",
            "download",
            "manifest",
            "map",
            "owner",
            "parcel",
            "point",
            "probe",
            "releases",
            "search",
        ],
        "publication_semantics": {
            "record_grain": "parcel_feature_occurrence",
            "owner_assertion": "assessment_roll",
            "assessment_owner_is_recorded_title": False,
            "recorded_instruments_source": "county_clerk_or_recorder",
            "bulk_aliases_are_rolling": True,
        },
        "official_complements": adapter.alternative_routes(),
    }
    schema_contract = {
        "live_schema_fingerprint": source_snapshot["schema_fingerprint"],
        "required_fields": list(adapter.REQUIRED_FIELDS),
        "query_fields": list(adapter.QUERY_FIELDS),
        "normalized_record_types": [
            "parcel_feature_occurrence",
            "county_coverage",
            "bulk_release_discovery",
            "bulk_dataset_manifest",
        ],
        "identity": stable_contract["identity"],
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "dataset_id": adapter.SOURCE_METADATA.dataset_id,
        "live_layer_id": 1,
        "live_layer_url": adapter.LAYER_URL,
        "parcel_bulk_root": adapter.PARCEL_ROOT,
        "orion_bulk_root": adapter.ORION_ROOT,
    }
    rolling_observation = {
        "source_snapshot": source_snapshot,
        "sentinel": {
            "canonical_ref": record.get("canonical_ref"),
            "source_record_id": record.get("source_record_id"),
            "object_id": identity.get("object_id"),
            "parcel_id": identity.get("parcel_id"),
            "county_geoid": jurisdiction.get("county_geoid"),
            "orion_county_prefix": prefix,
        },
        "county_coverage": county_coverage,
        "county_feature_total": county_feature_total,
        "release_discovery": releases,
        "warnings": observation["warnings"],
    }
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.LAYER_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "stable_contract_sha256": stable_contract_sha256,
            "stable_schema_sha256": stable_schema_sha256,
            "rolling_observation": rolling_observation,
            "requests_made": observation["requests_made"],
            "live_probe_requests": observation["live_probe_requests"],
            "county_group_requests": observation["county_group_requests"],
            "directory_requests": observation["directory_requests"],
        },
    )


def probe_massgis(context: ProbeContext) -> ProbeObservation:
    """Fetch Gosnold's official manifest row and a bounded archive signature."""
    started = time.perf_counter()
    manifest_client = ArcGISRESTClient(
        MASSGIS_MANIFEST_LAYER_URL,
        page_size=1,
        max_records=1,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    fetched = manifest_client.query(
        where="TOWN = 'GOSNOLD'",
        out_fields=MASSGIS_MANIFEST_FIELDS,
        requested_limit=1,
        max_records=1,
        return_geometry=False,
    )
    if not fetched.records:
        return ProbeObservation(
            status=ResultStatus.NO_RESULTS.value,
            endpoint=manifest_client.query_url,
            latency_ms=(time.perf_counter() - started) * 1000,
            schema_sha256=fetched.schema_fingerprint,
            result_count=0,
            details={
                "sentinel_query": "TOWN = 'GOSNOLD'",
                "pages_fetched": fetched.pages_fetched,
                "requests_made": fetched.requests_made,
            },
        )

    attributes = fetched.records[0].get("attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError("MassGIS sentinel manifest feature lacks attributes")
    artifact_url = attributes.get("SHAPE_LINK")
    if not isinstance(artifact_url, str) or not artifact_url.strip():
        raise ValueError("MassGIS sentinel manifest lacks SHAPE_LINK")
    artifact = BulkArtifact.from_url(
        "shapefile",
        artifact_url.strip(),
        archive_format="zip",
    )
    sample_bytes = context.sample_bytes or 0
    artifact_probe = BulkTransferClient(
        timeout=context.timeout,
        max_attempts=context.max_attempts,
    ).probe(artifact, sample_bytes=sample_bytes)
    artifact_basis = {
        "url": artifact.url,
        "etag": artifact_probe.etag,
        "last_modified": artifact_probe.last_modified,
        "content_length": artifact_probe.content_length,
    }
    artifact_sha256 = artifact_probe.source_sha256 or sha256_fingerprint(artifact_basis)
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=artifact.url,
        http_status=artifact_probe.http_status,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=fetched.schema_fingerprint,
        artifact_sha256=artifact_sha256,
        result_count=1,
        details={
            "manifest_endpoint": manifest_client.query_url,
            "sentinel_query": "TOWN = 'GOSNOLD'",
            "municipality": attributes.get("TOWN"),
            "town_id": attributes.get("TOWN_ID"),
            "assessor_fiscal_year": attributes.get("FY"),
            "artifact_url": artifact.url,
            "artifact_sha256_basis": (
                "source_sha256"
                if artifact_probe.source_sha256
                else "artifact_metadata_fingerprint"
            ),
            "content_length": artifact_probe.content_length,
            "etag": artifact_probe.etag,
            "last_modified": artifact_probe.last_modified,
            "accept_ranges": artifact_probe.accept_ranges,
            "sample_size": artifact_probe.sample_size,
            "sample_sha256": artifact_probe.sample_sha256,
            "signature_hex": artifact_probe.signature_hex,
            "format_hint": artifact_probe.format_hint,
        },
    )


def probe_oregon_taxlot_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one publisher-scoped Oregon taxlot layer."""

    config = OREGON_TAXLOT_SOURCES[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        source=context.source_id,
        all_sources=False,
        page_size=min(1_000, config.max_page_size),
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_oregon_taxlots(
        args,
        access_decision=context.catalog_decision,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=config.layer_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon taxlot probe returned another component or record kind"
        )
    sentinel = dict(record.get("sentinel") or {})
    artifact = {
        "canonical_ref": sentinel.get("canonical_ref"),
        "native_parcel_id": sentinel.get("native_parcel_id"),
        "component_total_count": record.get("component_total_count"),
        "sentinel_count": record.get("sentinel_count"),
    }
    return replace(
        observation,
        schema_sha256=str(
            record.get("schema_fingerprint") or observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(artifact),
        result_count=record.get("component_total_count"),
        details={
            **dict(observation.details),
            **artifact,
            "layer_name": record.get("layer_name"),
            "max_record_count": record.get("max_record_count"),
            "upstream_source": sentinel.get("upstream_source"),
        },
    )


def probe_oregon_lane_marion_property_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Lane or Marion publisher-scoped ArcGIS component."""

    config = OREGON_LANE_MARION_PROPERTY_SOURCES[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        source=context.source_id,
        all_sources=False,
        page_size=min(1_000, config.max_page_size),
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_oregon_lane_marion_property(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=config.layer_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Lane/Marion property probe returned another component or record kind"
        )

    sentinel = dict(record.get("sentinel") or {})
    stable_artifact = {
        "source_id": context.source_id,
        "record_kind": config.record_kind,
        "layer_name": record.get("layer_name"),
        "service_item_id": (record.get("service_item_id") or config.service_item_id),
        "source_crs": record.get("source_crs"),
        "sentinel_strategy": record.get("sentinel_strategy"),
    }
    return replace(
        observation,
        schema_sha256=str(
            record.get("schema_fingerprint") or observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(stable_artifact),
        result_count=record.get("component_total_count"),
        details={
            **dict(observation.details),
            **stable_artifact,
            "max_record_count": record.get("max_record_count"),
            "component_scope": record.get("component_scope"),
            "sentinel_count": record.get("sentinel_count"),
            "sentinel": sentinel,
            "service_data_last_edit": record.get("service_data_last_edit"),
            "cadence_fact": record.get("cadence_fact"),
            "complementary_sources": record.get("complementary_sources"),
        },
    )


def probe_oregon_lane_property_source(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Lane account/tax-map contract through its direct adapter."""

    adapter = query_oregon_lane_property
    if context.source_id not in adapter.SOURCE_IDS:
        raise ValueError(
            "Lane County property monitor received an unknown source"
        )
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--source",
            context.source_id,
            "--timeout",
            str(context.timeout),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args, log_results=False)
    endpoint = (
        adapter.ACCOUNT_ROOT_URL
        if context.source_id == adapter.ACCOUNT_SOURCE_ID
        else adapter.TAX_MAP_SEARCH_URL
    )
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError("Lane County property probe expected one contract record")
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError("Lane County property probe identity contract changed")

    if context.source_id == adapter.ACCOUNT_SOURCE_ID:
        required_truths = {
            "anonymous_json_search_verified": True,
            "anonymous_session_detail_verified": True,
        }
        if any(record.get(key) is not value for key, value in required_truths.items()):
            raise ValueError("Lane property-account probe contract changed")
        stable_contract = {
            "source_id": context.source_id,
            "record_kind": "source_probe",
            "sentinel_account": record.get("sentinel_account"),
            "sentinel_map_taxlot": record.get("sentinel_map_taxlot"),
            "representations": [
                "anonymous_json_search_index",
                "anonymous_cookie_session_account_detail",
                "recent_receipts",
                "valuation_history",
                "related_official_links",
            ],
            "label_roles": ["taxpayer", "owner_index"],
        }
        rolling_observation = {
            "receipt_count": record.get("receipt_count"),
            "valuation_year_count": record.get("valuation_year_count"),
        }
    else:
        required_truths = {
            "anonymous_webforms_search_verified": True,
            "official_pdf_verified": True,
        }
        if any(record.get(key) is not value for key, value in required_truths.items()):
            raise ValueError("Lane tax-map probe contract changed")
        document_sha256 = record.get("document_sha256")
        if not isinstance(document_sha256, str) or len(document_sha256) != 64:
            raise ValueError("Lane tax-map probe did not hash the PDF bytes")
        stable_contract = {
            "source_id": context.source_id,
            "record_kind": "source_probe",
            "sentinel_map_taxlot": record.get("sentinel_map_taxlot"),
            "sentinel_map_name": record.get("sentinel_map_name"),
            "sentinel_document_id": record.get("sentinel_document_id"),
            "representations": [
                "webforms_locator",
                "official_pdf_document",
            ],
            "identity_roles": ["locator_occurrence", "document"],
        }
        rolling_observation = {
            "document_size_bytes": record.get("document_size_bytes"),
            "document_sha256": document_sha256,
        }

    schema_contract = {
        "record_fields": sorted(record),
        "source_response_schema_fingerprint": record.get(
            "source_response_schema_fingerprint"
        ),
        "required_truth_fields": sorted(required_truths),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_oregon_marion_download(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Marion's live manifest and one bounded current artifact sample."""

    if context.source_id not in query_oregon_marion_downloads.SOURCE_IDS:
        raise ValueError(
            "Marion download monitor received an unknown source"
        )
    started = time.perf_counter()
    argv = [
        "probe",
        "--source",
        context.source_id,
        "--sample-bytes",
        str(
            context.sample_bytes
            if context.sample_bytes is not None
            else 64
        ),
        "--timeout",
        str(context.timeout),
        "--retry-attempts",
        str(context.max_attempts),
        "--minimum-interval",
        str(_catalog_interval(context.catalog_decision)),
    ]
    args = query_oregon_marion_downloads.build_parser().parse_args(argv)
    result = query_oregon_marion_downloads.execute(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=query_oregon_marion_downloads.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Marion download probe returned another source or record kind"
        )
    manifest = dict(record.get("manifest") or {})
    capability = dict(record.get("capability") or {})
    probe = dict(record.get("artifact_probe") or {})
    validator = dict(
        record.get("validator_occurrence_identity") or {}
    )
    stable_contract = {
        "source_id": context.source_id,
        "manifest_schema_version": (
            query_oregon_marion_downloads.MANIFEST_SCHEMA_VERSION
        ),
        "probe_schema_version": (
            query_oregon_marion_downloads.PROBE_SCHEMA_VERSION
        ),
        "schema_profile": record.get("schema_profile"),
        "format": record.get("format"),
        "capability": capability,
        "manifest_schema": manifest.get("schema"),
        "identity_contract": (
            (manifest.get("metadata") or {}).get(
                "download_occurrence_identity"
            )
            if isinstance(manifest.get("metadata"), Mapping)
            else None
        ),
    }
    occurrence_id = validator.get("validator_occurrence_id")
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(stable_contract),
        artifact_sha256=(
            str(occurrence_id)
            if occurrence_id
            else sha256_fingerprint(
                {
                    "artifact_url": probe.get("url"),
                    "etag": probe.get("etag"),
                    "last_modified": probe.get("last_modified"),
                    "content_length": probe.get("content_length"),
                }
            )
        ),
        result_count=1,
        details={
            **dict(observation.details),
            "release_id": record.get("release_id"),
            "release_slot_identity": record.get(
                "release_slot_identity"
            ),
            "release_set_fingerprint": (
                (manifest.get("metadata") or {}).get(
                    "release_set_fingerprint"
                )
                if isinstance(manifest.get("metadata"), Mapping)
                else None
            ),
            "schema_profile": record.get("schema_profile"),
            "format": record.get("format"),
            "capability": capability,
            "validator_occurrence_identity": validator,
            "artifact_probe": probe,
        },
    )


def probe_deschutes_property(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Deschutes service inventory, relationships, and one parcel."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        page_size=1_000,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_deschutes_property(
        args,
        access_decision=context.catalog_decision,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=DESCHUTES_PROPERTY_SERVICE_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Deschutes property probe returned another source or record kind"
        )
    sentinel = dict(record.get("sentinel") or {})
    component_counts = dict(record.get("component_counts") or {})
    artifact = {
        "service_item_id": record.get("service_item_id"),
        "component_counts": component_counts,
        "declared_relationship_count": len(record.get("declared_relationships") or []),
        "keyed_complement_count": len(record.get("keyed_complements") or []),
        "sales_relationship_status": record.get("sales_relationship_status"),
        "sentinel_taxlot": sentinel.get("native_parcel_id"),
        "sentinel_accounts": sentinel.get("assessment_account_ids"),
        "sentinel_last_sale": sentinel.get("last_sale"),
    }
    return replace(
        observation,
        schema_sha256=str(
            sentinel.get("response_schema_fingerprint") or observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(artifact),
        result_count=component_counts.get("taxlot"),
        details={
            **dict(observation.details),
            **artifact,
        },
    )


def probe_deschutes_dial(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe DIAL account components, taxlot resolution, and one report PDF."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_deschutes_dial(
        args,
        access_decision=context.catalog_decision,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=DESCHUTES_DIAL_BASE_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError("Deschutes DIAL probe returned another source or record kind")

    components = {
        str(key): dict(value)
        for key, value in dict(record.get("components") or {}).items()
    }
    expected_components = set(DESCHUTES_DIAL_COMPONENTS)
    if set(components) != expected_components:
        missing = sorted(expected_components - set(components))
        unexpected = sorted(set(components) - expected_components)
        raise ValueError(
            "Deschutes DIAL probe component inventory changed; "
            f"missing={missing}, unexpected={unexpected}"
        )
    component_status = {key: value.get("status") for key, value in components.items()}
    component_schema = {
        key: value.get("schema_fingerprint") for key, value in components.items()
    }
    search = dict(record.get("search") or {})
    sentinel = dict(record.get("sentinel") or {})
    pdf_probe = dict(record.get("pdf_probe") or {})
    linked_sources = dict(record.get("linked_source_observations") or {})
    artifact = {
        "native_account_id": sentinel.get("native_account_id"),
        "native_parcel_id": sentinel.get("native_parcel_id"),
        "component_status": component_status,
        "pdf_document_kind": pdf_probe.get("document_kind"),
        "pdf_signature_verified": pdf_probe.get("signature_verified"),
        "pdf_media_type": pdf_probe.get("media_type"),
        "linked_source_observations": linked_sources,
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(
            {
                "search": search.get("schema_fingerprint"),
                "components": component_schema,
            }
        ),
        artifact_sha256=sha256_fingerprint(artifact),
        result_count=sum(status == "ok" for status in component_status.values()),
        details={
            **dict(observation.details),
            **artifact,
            "search_field": search.get("field"),
            "search_resolution": search.get("resolution"),
            "pdf_size_bytes": pdf_probe.get("size_bytes"),
            "arcgis_complement_source_id": DESCHUTES_PROPERTY_SOURCE_ID,
            "join_keys": ["native_account_id", "native_parcel_id"],
        },
    )


def probe_deschutes_cdd_weblink(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe account discovery and both Laserfiche document storage modes."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        with_download=False,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        max_response_bytes=DESCHUTES_CDD_MAX_RESPONSE_BYTES,
        max_bytes=DESCHUTES_CDD_MAX_DOCUMENT_BYTES,
        poll_attempts=DESCHUTES_CDD_POLL_ATTEMPTS,
        poll_interval=DESCHUTES_CDD_POLL_INTERVAL,
        output=None,
        json_out=False,
    )
    result = execute_deschutes_cdd_weblink(args, log_results=False)
    observation = _adapter_result_observation(
        result,
        endpoint=DESCHUTES_CDD_WEBLINK_BASE_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Deschutes CDD WebLink probe returned another source or record kind"
        )

    account = dict(record.get("account_discovery") or {})
    electronic = dict(record.get("electronic_document") or {})
    imaged = dict(record.get("imaged_document") or {})
    folder = dict(record.get("parent_folder") or {})
    viewer = dict(record.get("viewer_access") or {})
    if not electronic.get("laserfiche_entry_id") or not imaged.get(
        "laserfiche_entry_id"
    ):
        raise ValueError("Deschutes CDD WebLink probe lacks document sentinels")
    if record.get("downloads"):
        raise ValueError(
            "Deschutes CDD WebLink routine monitor unexpectedly downloaded documents"
        )
    artifact = {
        "account_id": account.get("account_id"),
        "map_taxlot": account.get("map_taxlot"),
        "unique_document_count": account.get("unique_document_count"),
        "electronic_document_id": electronic.get("laserfiche_entry_id"),
        "electronic_retrieval_mode": electronic.get("retrieval_mode"),
        "imaged_document_id": imaged.get("laserfiche_entry_id"),
        "imaged_retrieval_mode": imaged.get("retrieval_mode"),
        "imaged_page_count": imaged.get("page_count"),
        "parent_folder_id": folder.get("laserfiche_folder_id"),
        "parent_folder_path": folder.get("laserfiche_path"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(
            {
                "account_index": account.get("schema_fingerprint"),
                "viewer": viewer.get("schema_fingerprint"),
                "record_schema": observation.schema_sha256,
            }
        ),
        artifact_sha256=sha256_fingerprint(artifact),
        result_count=account.get("unique_document_count"),
        details={
            **dict(observation.details),
            **artifact,
            "viewer_access": viewer,
            "routine_downloads": 0,
            "complement_source_ids": [
                DESCHUTES_DIAL_SOURCE_ID,
                DESCHUTES_PROPERTY_SOURCE_ID,
            ],
        },
    )


def probe_oregon_court_document_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one official Oregon Law Library collection independently."""

    collection = OREGON_COURT_DOCUMENT_COLLECTIONS[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        source=context.source_id,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_oregon_court_documents(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=collection.collection_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_health_check"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon court-document probe returned another component or record kind"
        )
    schema = {
        "search": record.get("search_schema_fingerprint"),
        "item": record.get("item_schema_fingerprint"),
    }
    artifact = {
        "collection_alias": record.get("collection_alias"),
        "sentinel_item_id": record.get("sentinel_item_id"),
        "sentinel_canonical_ref": record.get("sentinel_canonical_ref"),
        "sentinel_total_results": record.get("sentinel_total_results"),
        "full_text_character_count": record.get("full_text_character_count"),
        "page_count": record.get("page_count"),
        "download_uri": record.get("download_uri"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema),
        artifact_sha256=sha256_fingerprint(artifact),
        result_count=record.get("sentinel_total_results"),
        details={
            **dict(observation.details),
            **artifact,
            "metadata_field_count": record.get("metadata_field_count"),
            "is_compound": record.get("is_compound"),
        },
    )


def probe_oregon_appellate(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe independently reported Oregon appellate API components."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_oregon_appellate(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=OREGON_APPELLATE_API_ROOT,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon appellate probe returned another source or record kind"
        )
    checks = dict(record.get("checks") or {})
    component_status = {
        name: value.get("status")
        for name, value in checks.items()
        if isinstance(value, Mapping)
    }
    case_detail = checks.get("case_detail")
    case_detail_result = (
        case_detail.get("result") if isinstance(case_detail, Mapping) else None
    )
    artifact = {
        "source_result_limit": record.get("source_result_limit"),
        "component_status": component_status,
        "sentinel_case_number": (
            case_detail_result.get("case_number")
            if isinstance(case_detail_result, Mapping)
            else None
        ),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(
            {
                name: inferred_schema([value])
                for name, value in checks.items()
                if isinstance(value, Mapping)
            }
        ),
        artifact_sha256=sha256_fingerprint(artifact),
        result_count=sum(status == "ok" for status in component_status.values()),
        details={
            **dict(observation.details),
            **artifact,
            "component_count": len(component_status),
        },
    )


def probe_oregon_appellate_calendar_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one appellate calendar without hashing routine list growth."""

    spec = OREGON_APPELLATE_CALENDAR_SOURCES[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        court=spec.key,
        timeout=context.timeout,
        max_attempts=context.max_attempts,
        minimum_interval=_catalog_interval(context.catalog_decision),
        output=None,
        json_out=False,
    )
    result = execute_oregon_appellate_calendars(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=spec.page_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon appellate-calendar probe returned another source or record kind"
        )

    checks = dict(record.get("checks") or {})
    legacy = dict(record.get("legacy_entrypoint") or {})
    page_contract = dict(record.get("page_contract") or {})
    view_contract = dict(record.get("view_contract") or {})
    list_contract = dict(record.get("list_contract") or {})
    component_status = dict(checks.get("component_status") or {})
    stable_artifact = {
        "source_id": spec.source_id,
        "court_id": spec.court_id,
        "legacy_url": spec.legacy_url,
        "legacy_migrated_to_error_path": legacy.get("migrated_to_error_path"),
        "current_page_url": spec.page_url,
        "page_list_title": page_contract.get("list_title"),
        "list_id": list_contract.get("list_id"),
        "list_path": list_contract.get("server_relative_url"),
        "view_name": spec.view_name,
        "view_row_limit": view_contract.get("row_limit"),
        "view_current_only": spec.view_current_only,
    }
    schema_fingerprints = dict(record.get("schema_fingerprints") or {})
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_fingerprints),
        artifact_sha256=sha256_fingerprint(stable_artifact),
        result_count=checks.get("list_item_count"),
        details={
            **dict(observation.details),
            **stable_artifact,
            "component_status": component_status,
            "declared_list_item_count": checks.get("declared_list_item_count"),
            "fetched_list_item_count": checks.get("list_item_count"),
            "source_pages_fetched": checks.get("source_pages_fetched"),
            "official_view_eligible_item_count": checks.get(
                "official_view_eligible_item_count"
            ),
            "official_view_may_truncate": checks.get("official_view_may_truncate"),
            "attachment_item_count": checks.get("attachment_item_count"),
            "attachment_document_count": checks.get("attachment_document_count"),
            "oldest_event_date": checks.get("oldest_event_date"),
            "newest_event_date": checks.get("newest_event_date"),
        },
    )


def probe_oregon_tax_foreclosure_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one county publication ecosystem without freezing current content."""

    config = OREGON_TAX_FORECLOSURE_SOURCES[context.source_id]
    started = time.perf_counter()
    discovery = discover_oregon_tax_foreclosure_source(
        config,
        timeout=context.timeout,
    )
    routes = [dict(route) for route in discovery.get("publication_routes", ())]
    landing_observations = [
        dict(observation)
        for observation in discovery.get("landing_page_observations", ())
    ]
    linked_routes = [route for route in routes if route.get("document_url")]
    if not linked_routes:
        raise ValueError(
            f"{config.county_name} discovery returned no linked publication artifact"
        )
    selected_route = linked_routes[0]
    artifact_payload = fetch_oregon_tax_foreclosure_bytes(
        str(selected_route["document_url"]),
        context.timeout,
        OREGON_TAX_FORECLOSURE_MAX_DOCUMENT_BYTES,
    )
    if not artifact_payload.startswith(b"%PDF-"):
        raise ValueError(
            f"{config.county_name} current publication is not a PDF artifact"
        )

    stable_contract = {
        "source_id": config.source_id,
        "county_geoid": config.county_geoid,
        "publisher": config.publisher,
        "landing_pages": [
            {"url": page.url, "role": page.role} for page in config.landing_pages
        ],
        "stable_join_keys": list(config.stable_join_keys),
        "supported_process_stages": list(
            OREGON_TAX_FORECLOSURE_PROCESS_STAGES[context.source_id]
        ),
        "complementary_sources": [
            item.to_dict() for item in config.complementary_sources
        ],
    }
    artifact_contract = {
        "media_type": "application/pdf",
        "version_identity": "artifact_sha256_after_download",
        "text_representation_parent_key": "parent_artifact_sha256",
        "publication_document_identity": "discovery_document_id",
    }
    current_artifact = {
        "publication_document_id": selected_route.get("document_id"),
        "process_stage": selected_route.get("process_stage"),
        "publication_label": selected_route.get("publication_label"),
        "document_url": selected_route.get("document_url"),
        "sha256": hashlib.sha256(artifact_payload).hexdigest(),
        "size_bytes": len(artifact_payload),
        "pdf_signature_verified": True,
    }
    rolling_observation = {
        "landing_pages": landing_observations,
        "route_count": len(routes),
        "observed_process_stages": sorted(
            {
                str(route["process_stage"])
                for route in routes
                if route.get("process_stage")
            }
        ),
        "publication_routes": routes,
        "current_artifact": current_artifact,
    }
    schema_payload = {
        "landing_page_observations": inferred_schema(landing_observations),
        "publication_routes": inferred_schema(routes),
        "current_artifact": inferred_schema([current_artifact]),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=config.primary_page,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_payload),
        artifact_sha256=sha256_fingerprint(
            {
                "stable_contract": stable_contract,
                "artifact_contract": artifact_contract,
            }
        ),
        result_count=len(routes),
        details={
            "stable_contract": stable_contract,
            "artifact_contract": artifact_contract,
            "rolling_observation": rolling_observation,
            "requests_made": len(config.landing_pages) + 1,
        },
    )


def probe_oregon_helion_recorder_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one county Helion form and its tenant-specific vocabulary."""

    tenant = OREGON_HELION_RECORDER_TENANTS[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        source=tenant.source_id,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    result = execute_oregon_helion_recorder(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=tenant.search_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon Helion recorder probe returned another source or record kind"
        )
    stable_artifact = {
        "county_fips": record.get("county_fips"),
        "search_action": record.get("search_action"),
        "search_method": record.get("search_method"),
        "form_fields": record.get("form_fields"),
        "select_options": record.get("select_options"),
    }
    return replace(
        observation,
        schema_sha256=str(
            record.get("source_schema_fingerprint") or observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(stable_artifact),
        result_count=len(record.get("form_fields") or []),
        details={
            **dict(observation.details),
            **stable_artifact,
            "county_name": record.get("county_name"),
            "indexed_through_raw": record.get("indexed_through_raw"),
        },
    )


def probe_oregon_helion_property_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one county PSO form while separating contract and runtime facts."""

    tenant = OREGON_HELION_PROPERTY_TENANTS[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        source=tenant.source_id,
        timeout=context.timeout,
        output=None,
        json_out=False,
    )
    result = execute_oregon_helion_property(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=tenant.portal_root,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon Helion property probe returned another source or record kind"
        )

    live_probe = dict(record.get("live_probe") or {})
    observed_options = [
        {
            "value": option.get("value"),
            "label": option.get("label"),
        }
        for option in live_probe.get("search_options") or []
        if isinstance(option, Mapping)
    ]
    stable_contract = {
        "source_id": context.source_id,
        "county_fips": tenant.county_fips,
        "platform_family": OREGON_HELION_PROPERTY_PLATFORM,
        "portal_root": tenant.portal_root,
        "page_title": live_probe.get("title"),
        "access_outcome": live_probe.get("access_outcome"),
        "search_options": observed_options,
        "configured_native_search_options": dict(tenant.search_options),
    }
    volatile_observation = {
        "footer": live_probe.get("footer"),
        "transport_events": list(live_probe.get("transport_events") or []),
        "runtime": dict(live_probe.get("runtime") or {}),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(inferred_schema([live_probe])),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=len(observed_options),
        details={
            **dict(observation.details),
            "county_name": tenant.county_name,
            "stable_contract": stable_contract,
            "volatile_observation": volatile_observation,
            "observed_access": record.get("observed_access"),
            "official_complements": [
                dict(complement) for complement in tenant.complements
            ],
        },
    )


def probe_oregon_county_assessor_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Oregon county assessor layer with stable/rolling separation."""

    is_jackson_douglas = context.source_id in OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCES
    configs = (
        OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCES
        if is_jackson_douglas
        else OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SOURCES
    )
    config = configs[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        source=context.source_id,
        all_sources=False,
        page_size=config.max_page_size,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    if is_jackson_douglas:
        result = execute_oregon_jackson_douglas_assessors(
            args,
            access_decision=context.catalog_decision,
            log_results=False,
        )
    else:
        result = execute_oregon_linn_josephine_klamath_assessors(
            args,
            log_results=False,
        )
    observation = _adapter_result_observation(
        result,
        endpoint=config.layer_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon county assessor probe returned another source or record kind"
        )

    complements = (
        list(config.complementary_sources)
        if hasattr(config, "complementary_sources")
        else list(record.get("complementary_sources") or [])
    )
    stable_contract = {
        "source_id": context.source_id,
        "county_geoid": config.county_geoid,
        "service_url": config.service_url,
        "service_item_id": config.service_item_id,
        "layer_url": config.layer_url,
        "layer_id": config.layer_id,
        "expected_layer_name": config.expected_layer_name,
        "source_crs": (
            config.source_crs if hasattr(config, "source_crs") else config.original_crs
        ),
        "native_id_fields": list(config.native_id_fields),
        "search_fields": sorted(config.search_fields),
        "required_fields": list(config.required_fields),
        "complementary_sources": _json_ready(complements),
    }
    representative = record.get("representative_row")
    representative_identity = (
        {
            key: representative.get(key)
            for key in (
                "canonical_ref",
                "native_id",
                "native_parcel_id",
                "object_id",
            )
        }
        if isinstance(representative, Mapping)
        else None
    )
    rolling_observation = {
        "component_total_count": record.get("component_total_count"),
        "count_baseline": _json_ready(record.get("count_baseline") or {}),
        "sentinel_count": record.get("sentinel_count"),
        "representative_identity": representative_identity,
        "update_metadata": _json_ready(record.get("update_metadata") or {}),
        "item_identity": _json_ready(record.get("item_identity") or {}),
    }
    return replace(
        observation,
        schema_sha256=str(
            record.get("schema_fingerprint") or observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=record.get("sentinel_count"),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_oregon_benton_property_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Benton API/directory component under its own source ID."""

    component_by_source = {
        query_oregon_benton_property.PARCEL_SOURCE_ID: "parcel",
        query_oregon_benton_property.BULK_SOURCE_ID: "bulk",
        query_oregon_benton_property.MAP_SOURCE_ID: "maps",
    }
    endpoint_by_source = {
        query_oregon_benton_property.PARCEL_SOURCE_ID: (
            query_oregon_benton_property.PARCEL_LAYER_URL
        ),
        query_oregon_benton_property.BULK_SOURCE_ID: (
            query_oregon_benton_property.ASSESSMENT_DIRECTORY_URL
        ),
        query_oregon_benton_property.MAP_SOURCE_ID: (
            query_oregon_benton_property.ASSESSMENT_MAP_DIRECTORY_URL
        ),
    }
    component = component_by_source[context.source_id]
    endpoint = endpoint_by_source[context.source_id]
    started = time.perf_counter()
    args = query_oregon_benton_property.build_parser().parse_args(
        [
            "probe",
            "--component",
            component,
            "--range-bytes",
            str(context.sample_bytes or 8),
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    result = query_oregon_benton_property.execute(
        args,
        log_results=False,
    )
    if not isinstance(result, PublicRecordsResult):
        raise ValueError("Benton component probe did not return a result envelope")
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError("Benton property probe returned another source or record kind")

    if component == "parcel":
        stable_contract = {
            "source_id": context.source_id,
            "layer_identity": _json_ready(record.get("layer_identity") or {}),
            "jurisdiction_identity": _json_ready(
                record.get("jurisdiction_identity") or {}
            ),
            "schema_baseline": _json_ready(record.get("schema_baseline") or {}),
        }
        rolling_observation = {
            "component_total_count": record.get("component_total_count"),
            "count_baseline": _json_ready(record.get("count_baseline") or {}),
            "sentinel_count": record.get("sentinel_count"),
            "representative_identity": {
                key: record.get("representative_row", {}).get(key)
                for key in (
                    "canonical_ref",
                    "object_id",
                    "account_number",
                    "map_taxlot",
                    "or_taxlot",
                    "map_number",
                )
            },
            "update_evidence": _json_ready(record.get("update_evidence") or {}),
        }
        schema_sha256 = (
            str(record.get("schema_fingerprint") or observation.schema_sha256 or "")
            or None
        )
        result_count = record.get("sentinel_count")
    elif component == "bulk":
        release = record.get("release")
        manifest = release.get("manifest") if isinstance(release, Mapping) else {}
        artifacts = manifest.get("artifacts") if isinstance(manifest, Mapping) else []
        stable_contract = {
            "source_id": context.source_id,
            "directory_identity": _json_ready(record.get("directory_identity") or {}),
            "dataset_id": (
                manifest.get("dataset_id") if isinstance(manifest, Mapping) else None
            ),
            "schema": _json_ready(
                manifest.get("schema", {}) if isinstance(manifest, Mapping) else {}
            ),
            "artifacts": [
                {
                    key: artifact.get(key)
                    for key in (
                        "artifact_id",
                        "filename",
                        "media_type",
                        "archive_format",
                    )
                }
                for artifact in artifacts or []
                if isinstance(artifact, Mapping)
            ],
        }
        rolling_observation = {
            "directory_entry_count": record.get("directory_entry_count"),
            "listing_fingerprint": record.get("listing_fingerprint"),
            "release_id": (
                manifest.get("release", {}).get("release_id")
                if isinstance(manifest, Mapping)
                and isinstance(manifest.get("release"), Mapping)
                else None
            ),
            "artifact_probes": _json_ready(record.get("artifact_probes") or []),
        }
        schema_sha256 = sha256_fingerprint(stable_contract["schema"])
        result_count = len(stable_contract["artifacts"])
    else:
        stable_contract = {
            "source_id": context.source_id,
            "directory_identity": _json_ready(record.get("directory_identity") or {}),
            "record_kind": "assessment_map",
            "artifact_media_type": "application/pdf",
            "map_kinds": [
                "assessment_map",
                "map_index",
                "dlc_index",
                "dated_archive",
            ],
        }
        rolling_observation = {
            "pdf_count": record.get("pdf_count"),
            "listing_fingerprint": record.get("listing_fingerprint"),
            "latest_directory_entry": _json_ready(
                record.get("latest_directory_entry") or {}
            ),
            "representative_map": _json_ready(record.get("representative_map") or {}),
            "artifact_probe": _json_ready(record.get("artifact_probe") or {}),
        }
        schema_sha256 = sha256_fingerprint(stable_contract)
        result_count = record.get("pdf_count")

    return replace(
        observation,
        schema_sha256=schema_sha256,
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=result_count,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
        },
    )


def _oregon_county_component_module(source_id: str) -> Any:
    if source_id in query_oregon_yamhill_property.SOURCE_IDS:
        return query_oregon_yamhill_property
    if source_id in query_oregon_clackamas_property.SOURCE_IDS:
        return query_oregon_clackamas_property
    if source_id in query_oregon_wasco_property.SOURCE_IDS:
        return query_oregon_wasco_property
    raise ValueError(f"unknown Oregon county property component: {source_id}")


def _oregon_county_stable_contract(module: Any, source_id: str) -> dict[str, Any]:
    source = module.SOURCE_METADATA[source_id].to_dict()
    metadata = dict(source.get("metadata") or {})
    native = metadata.get("native_contract")
    if isinstance(native, Mapping):
        native = dict(native)
        native.pop("observed_count", None)
        metadata["native_contract"] = native

    if module is query_oregon_yamhill_property:
        if source_id == module.ASCEND_SOURCE_ID:
            native = module.YAMHILL_ASCEND_MANIFEST.contract_record()
        else:
            config = module.ARCGIS_SOURCES[source_id]
            native = {
                "source_id": config.source_id,
                "layer_url": config.layer_url,
                "layer_id": config.layer_id,
                "service_item_id": config.service_item_id,
                "expected_layer_name": config.expected_layer_name,
                "object_id_field": config.object_id_field,
                "required_fields": list(config.required_fields),
                "source_crs": config.source_crs,
                "publication_year": config.publication_year,
            }
    elif module is query_oregon_clackamas_property:
        manifest = (
            module.CLACKAMAS_ASCEND_MANIFEST
            if source_id == module.ASCEND_SOURCE_ID
            else module.CLACKAMAS_CMAP_MANIFEST
        )
        native = manifest.contract_record()
        native.pop("observed_count", None)
    else:
        native = metadata.get("native_contract")

    return {
        "source_id": source_id,
        "county_geoid": module.COUNTY_GEOID,
        "base_url": source.get("base_url"),
        "dataset_id": source.get("dataset_id"),
        "source_role": source.get("source_role"),
        "native_contract": native,
    }


def probe_oregon_county_property_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Yamhill, Clackamas, or Wasco component contract."""

    module = _oregon_county_component_module(context.source_id)
    started = time.perf_counter()
    args = module.build_parser().parse_args(
        [
            "probe",
            "--source",
            context.source_id,
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    if module is query_oregon_wasco_property:
        result = module.execute(args, log_results=False)
    else:
        result = module.execute(
            args,
            access_decision=context.catalog_decision,
            log_results=False,
        )
    if not isinstance(result, PublicRecordsResult):
        raise ValueError("Oregon county component probe returned no result envelope")
    endpoint = module.SOURCE_METADATA[context.source_id].base_url or str(
        module.SOURCE_METADATA[context.source_id].metadata.get("publisher") or ""
    )
    observation = _adapter_result_observation(
        result,
        endpoint=endpoint,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError("Oregon county component probe returned another source")

    stable_contract = _oregon_county_stable_contract(module, context.source_id)
    schema_contract = {
        key: record.get(key)
        for key in (
            "platform_version",
            "home_schema_fingerprint",
            "schema_fingerprint",
            "layer_name",
            "layer_id",
            "service_item_id",
            "max_record_count",
        )
        if record.get(key) is not None
    }
    rolling_observation = {
        key: value
        for key, value in record.items()
        if key
        not in {
            "record_kind",
            "source_id",
            "native_contract",
            "schema_fingerprint",
            "home_schema_fingerprint",
        }
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(
            schema_contract or stable_contract["native_contract"] or stable_contract
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": _json_ready(rolling_observation),
        },
    )


def _washington_property_stable_contract(source_id: str) -> dict[str, Any]:
    adapter = query_oregon_washington_property
    source = adapter.SOURCES[source_id].to_dict()
    contract: dict[str, Any] = {
        "source_id": source_id,
        "county_geoid": adapter.COUNTY_GEOID,
        "base_url": source.get("base_url"),
        "dataset_id": source.get("dataset_id"),
        "source_role": source.get("source_role"),
        "capabilities": adapter._capabilities(source_id),
        "joins": adapter._joins(source_id),
    }
    if source_id == adapter.SURVEY_API_SOURCE_ID:
        contract["survey_kinds"] = {
            key: {
                "searchby": kind.searchby,
                "allowed_fields": list(kind.allowed_fields),
                "sort_fields": list(kind.sort_fields),
                "native_id_fields": list(kind.native_id_fields),
            }
            for key, kind in adapter.SURVEY_KINDS.items()
        }
    elif source_id == adapter.SURVEY_MAP_SOURCE_ID:
        contract["arcgis_layers"] = {
            key: {
                "layer_url": layer.layer_url,
                "sort_fields": list(layer.sort_fields),
                "native_id_fields": list(layer.native_id_fields),
                "join_fields": list(layer.join_fields),
                "source_wkid": layer.source_wkid,
            }
            for key, layer in adapter.ARCGIS_LAYERS.items()
            if layer.source_id == source_id
        }
    elif source_id in {
        adapter.TAXLOT_SOURCE_ID,
        adapter.SITUS_SOURCE_ID,
    }:
        layer_key = "taxlots" if source_id == adapter.TAXLOT_SOURCE_ID else "situs"
        layer = adapter.ARCGIS_LAYERS[layer_key]
        contract["arcgis_layer"] = {
            "layer_key": layer.key,
            "layer_url": layer.layer_url,
            "sort_fields": list(layer.sort_fields),
            "native_id_fields": list(layer.native_id_fields),
            "join_fields": list(layer.join_fields),
            "source_wkid": layer.source_wkid,
        }
    elif source_id == adapter.INTERMAP_SOURCE_ID:
        contract["report_routes"] = dict(adapter.INTERMAP_REPORT_IDS)
    elif source_id == adapter.TAX_SOURCE_ID:
        contract["routes"] = {
            "detail": adapter.TAX_DETAIL_ROUTE,
            "statement_generator": adapter.TAX_STATEMENT_GENERATOR_URL,
            "generated_document_base": adapter.TAX_GENERATED_DOCUMENT_BASE,
        }
    return contract


def _washington_arcgis_schema(metadata: Mapping[str, Any]) -> dict[str, Any]:
    fields = metadata.get("fields")
    return {
        "service_item_id": metadata.get("serviceItemId"),
        "layer_id": metadata.get("id"),
        "name": metadata.get("name"),
        "geometry_type": metadata.get("geometryType"),
        "object_id_field": (
            metadata.get("objectIdField") or metadata.get("objectIdFieldName")
        ),
        "fields": [
            {
                "name": field.get("name"),
                "type": field.get("type"),
            }
            for field in fields
            if isinstance(field, Mapping)
        ]
        if isinstance(fields, list)
        else [],
    }


def _run_washington_property_component_probe(
    context: ProbeContext,
) -> dict[str, Any]:
    adapter = query_oregon_washington_property
    interval = _catalog_interval(context.catalog_decision)
    with adapter.WashingtonClient(
        timeout=context.timeout,
        minimum_interval=interval,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    ) as client:
        if context.source_id == adapter.SURVEY_API_SOURCE_ID:
            envelope, artifact = client.survey_search(
                adapter.SURVEY_KINDS["survey"],
                {"surveynumber": adapter.PROBE_SURVEY},
            )
            rows = envelope.get("data")
            row_list = (
                rows
                if isinstance(rows, list)
                else [rows]
                if isinstance(rows, Mapping)
                else []
            )
            first = row_list[0] if row_list else {}
            return {
                "endpoint": artifact.source_url,
                "schema_contract": {
                    "envelope_keys": sorted(str(key) for key in envelope),
                    "record_fields": (
                        sorted(str(key) for key in first)
                        if isinstance(first, Mapping)
                        else []
                    ),
                },
                "rolling_observation": {
                    "total": envelope.get("total"),
                    "sentinel": adapter.PROBE_SURVEY,
                },
                "result_count": len(row_list),
            }

        arcgis_selection = {
            adapter.SURVEY_MAP_SOURCE_ID: (
                "survey-taxlots",
                "TLID",
                adapter.PROBE_TAXLOT,
            ),
            adapter.TAXLOT_SOURCE_ID: (
                "taxlots",
                "TLNO",
                adapter.PROBE_TAXLOT,
            ),
            adapter.SITUS_SOURCE_ID: (
                "situs",
                "TAXLOT",
                adapter.PROBE_TAXLOT,
            ),
        }
        if context.source_id in arcgis_selection:
            layer_key, field, value = arcgis_selection[context.source_id]
            layer = adapter.ARCGIS_LAYERS[layer_key]
            metadata = client.layer_metadata(layer)
            payload, artifact = client.arcgis_query(
                layer,
                {
                    "where": f"{field} = {adapter._sql_string(value)}",
                    "outFields": "*",
                    "returnGeometry": "false",
                    "resultRecordCount": 2,
                },
            )
            features = payload.get("features")
            return {
                "endpoint": artifact.source_url,
                "schema_contract": _washington_arcgis_schema(metadata),
                "rolling_observation": {
                    "matches": (len(features) if isinstance(features, list) else 0),
                    "sentinel": value,
                },
                "result_count": (len(features) if isinstance(features, list) else 0),
            }

        if context.source_id == adapter.INTERMAP_SOURCE_ID:
            endpoint = adapter.intermap_url(
                adapter.PROBE_TAXLOT,
                "assessment",
            )
            html, artifact = client.text(
                endpoint,
                maximum_bytes=adapter.DEFAULT_MAX_HTML_BYTES,
            )
            representation = adapter.parse_html_representation(
                html,
                source_url=artifact.source_url,
            )
            return {
                "endpoint": artifact.source_url,
                "schema_contract": {
                    "title": representation.get("title"),
                    "headings": representation.get("headings"),
                    "field_labels": [
                        pair.get("label")
                        for pair in representation.get("field_pairs", [])
                        if isinstance(pair, Mapping)
                    ],
                },
                "rolling_observation": {
                    "contains_account": adapter.PROBE_ACCOUNT in html,
                    "sentinel": adapter.PROBE_TAXLOT,
                },
                "result_count": 1,
            }

        if context.source_id == adapter.TAX_SOURCE_ID:
            endpoint = (
                f"{adapter.TAX_BASE_URL}"
                f"{adapter.TAX_DETAIL_ROUTE.format(account=adapter.PROBE_ACCOUNT)}"
            )
            html, artifact = client.text(
                endpoint,
                maximum_bytes=adapter.DEFAULT_MAX_HTML_BYTES,
            )
            record = adapter.parse_tax_account(
                html,
                source_url=artifact.source_url,
                requested_account=adapter.PROBE_ACCOUNT,
            )
            representation = record.get("native_representation") or {}
            return {
                "endpoint": artifact.source_url,
                "schema_contract": {
                    "record_fields": sorted(str(key) for key in record),
                    "field_labels": [
                        pair.get("label")
                        for pair in representation.get("field_pairs", [])
                        if isinstance(pair, Mapping)
                    ],
                },
                "rolling_observation": {
                    "account": record.get("native_ids", {}).get("PropertyQuickRefID"),
                    "statement_years": [
                        item.get("tax_year")
                        for item in record.get("tax_statements", [])[:5]
                        if isinstance(item, Mapping)
                    ],
                },
                "result_count": 1,
            }
    raise ValueError(
        f"unknown Washington County property component: {context.source_id}"
    )


def probe_oregon_washington_property_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Washington County component without rerunning the family."""

    started = time.perf_counter()
    stable_contract = _washington_property_stable_contract(context.source_id)
    runtime = _run_washington_property_component_probe(context)
    result_count = int(runtime.get("result_count") or 0)
    return ProbeObservation(
        status=(
            ResultStatus.OK.value if result_count else ResultStatus.NO_RESULTS.value
        ),
        endpoint=str(runtime.get("endpoint") or "") or None,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(
            runtime.get("schema_contract") or stable_contract
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=result_count,
        details={
            "stable_contract": stable_contract,
            "schema_contract": _json_ready(runtime.get("schema_contract") or {}),
            "rolling_observation": _json_ready(
                runtime.get("rolling_observation") or {}
            ),
        },
    )


def _washington_digital_archives_land_stable_contract() -> dict[str, Any]:
    """Return the archive contract without rolling counts or coverage years."""

    adapter = query_washington_digital_archives_land
    title_contracts = [
        {
            "county_key": title.key,
            "county": title.county,
            "county_geoid": title.county_geoid,
            "title_id": title.title_id,
        }
        for title in adapter.TITLES
    ]
    archive_gap_contracts = [
        {
            "county_key": alternative.key,
            "county": alternative.county,
            "county_geoid": alternative.county_geoid,
        }
        for alternative in adapter.RECORDER_ALTERNATIVES
    ]
    assessor_complements = [
        {
            "county_key": alternative.key,
            "county_geoid": alternative.county_geoid,
            "kind": complement.get("kind"),
            "relationship": complement.get("relationship"),
        }
        for alternative in adapter.RECORDER_ALTERNATIVES
        for complement in alternative.complementary_sources
        if str(complement.get("kind") or "").startswith("assessor")
    ]
    return {
        "source_id": adapter.SOURCE_ID,
        "authority": (
            "Washington Secretary of State, Washington State Archives"
        ),
        "base_url": adapter.BASE_URL,
        "record_series": {
            "id": adapter.RECORD_SERIES_ID,
            "name": adapter.RECORD_SERIES_NAME,
            "evidence_lineage": adapter.EVIDENCE_LINEAGE,
        },
        "coverage": {
            "statewide": False,
            "covered_title_count": len(title_contracts),
            "titles": title_contracts,
            "archive_gap_count": len(archive_gap_contracts),
            "archive_gaps": archive_gap_contracts,
            "rolling_title_observation_fields": [
                "title",
                "coverage_label",
                "record_count",
                "image_availability",
            ],
        },
        "operations": {
            "inventory": {
                "method": "GET",
                "path": adapter.TITLE_LIST_PATH,
                "access": "anonymous",
            },
            "title": {
                "method": "GET",
                "path": adapter.TITLE_PATH,
                "access": "anonymous",
            },
            "search": {
                "start_method": "POST",
                "start_path": adapter.SEARCH_PATH,
                "results_method": "GET",
                "results_path": adapter.RESULTS_PATH,
                "access": "anonymous_session",
                "native_page_sizes": list(adapter.NATIVE_PAGE_SIZES),
            },
            "detail": {
                "method": "GET",
                "path": adapter.DETAIL_PATH,
                "access": "anonymous",
            },
        },
        "identity": {
            "title": ["record_series_id", "title_id"],
            "recorded_instrument": [
                "record_series_id",
                "title_id",
                "native_record_id",
            ],
            "indexed_party_group": "source_published_party_tuple_hash",
            "search_occurrence": (
                "query_bound_native_result_ordinal_plus_indexed_party_key"
            ),
            "digital_object": "native_digital_object_id",
            "search_rows_can_repeat_record_id": True,
            "source_published_party_names_preserved_intact": True,
        },
        "image_delivery": {
            "listed_object_state": "metadata_only_until_bytes_acquired",
            "queue_path": adapter.DIGITAL_OBJECT_QUEUE_PATH,
            "queue_state": "site_recaptcha_queue",
            "captcha_action": "generateDocument",
            "included_in_monitor": False,
            "direct_download_url": None,
            "page_count_before_acquisition": None,
            "rights_tier": "official_archive_image_uncertified",
        },
        "lineages": {
            "archive_index": adapter.EVIDENCE_LINEAGE,
            "archive_gap_recorders": (
                "separate_county_auditor_recorded_instrument_lineages"
            ),
            "assessor_complements": assessor_complements,
            "statewide_parcels": {
                "lineage_id": query_washington_parcels.LINEAGE_ID,
                "relationship": (
                    "separate_current_parcel_assessment_and_geometry_lineage"
                ),
            },
        },
    }


def _washington_digital_archives_land_artifact_identity() -> dict[str, Any]:
    """Return the fixed identities exercised by the bounded monitor."""

    adapter = query_washington_digital_archives_land
    sentinel = adapter.TITLES_BY_KEY["adams"]
    return {
        "source_id": adapter.SOURCE_ID,
        "record_series_id": adapter.RECORD_SERIES_ID,
        "covered_title_ids": sorted(title.title_id for title in adapter.TITLES),
        "archive_gap_geoids": sorted(
            alternative.county_geoid
            for alternative in adapter.RECORDER_ALTERNATIVES
        ),
        "sentinel": {
            "county_key": sentinel.key,
            "county_geoid": sentinel.county_geoid,
            "title_id": sentinel.title_id,
            "record_id": sentinel.sentinel_record_id,
        },
    }


def _washington_digital_archives_land_snapshot(
    context: ProbeContext,
) -> dict[str, Any]:
    """Fetch bounded anonymous inventory/title/search/detail observations."""

    adapter = query_washington_digital_archives_land
    title_config = adapter.TITLES_BY_KEY["adams"]
    client = adapter.DigitalArchivesClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )

    inventory = client.fetch_title_list()
    title_detail = client.fetch_title(title_config.title_id)
    search_payload = adapter.build_search_payload(
        title_config,
        search_type="DetailedSearch",
        last_name=title_config.sentinel_last_name,
        first_name=title_config.sentinel_first_name,
        start_year=title_config.sentinel_year,
        end_year=title_config.sentinel_year,
    )
    search_handle = client.start_search(search_payload)
    search_page = client.fetch_results(
        search_handle.search_id,
        page=1,
        page_size=adapter.DEFAULT_PAGE_SIZE,
    )
    detail = client.fetch_detail(str(title_config.sentinel_record_id))

    expected_title_ids = {title.title_id for title in adapter.TITLES}
    discovered_title_ids = {
        int(record["title_id"])
        for record in inventory
        if isinstance(record.get("title_id"), int)
        and not isinstance(record.get("title_id"), bool)
    }
    sentinel_present = any(
        record.get("native_record_id") == title_config.sentinel_record_id
        for record in search_page.records
    )

    digital_objects = []
    for source_object in detail.get("digital_objects") or []:
        if not isinstance(source_object, Mapping):
            continue
        digital_objects.append(
            {
                **dict(source_object),
                "metadata_only": True,
                "acquired_at": None,
                "sha256": None,
                "storage_path": None,
                "page_count": None,
                "rights_tier": "official_archive_image_uncertified",
            }
        )

    inventory_fields = sorted(
        {
            str(field_name)
            for record in inventory
            for field_name in record
        }
    )
    search_record_fields = sorted(
        {
            str(field_name)
            for record in search_page.records
            for field_name in record
        }
    )
    party_fields = sorted(
        {
            str(field_name)
            for party in detail.get("parties") or []
            if isinstance(party, Mapping)
            for field_name in party
        }
    )
    source_digital_object_fields = sorted(
        {
            str(field_name)
            for source_object in detail.get("digital_objects") or []
            if isinstance(source_object, Mapping)
            for field_name in source_object
        }
    )
    schema_contract = {
        "inventory_record_fields": inventory_fields,
        "title_schema_fingerprint": (
            (title_detail.get("provenance") or {}).get("schema_fingerprint")
        ),
        "title_record_fields": sorted(str(key) for key in title_detail),
        "search_schema_fingerprint": search_page.schema_fingerprint,
        "search_record_fields": search_record_fields,
        "detail_schema_fingerprint": (
            (detail.get("provenance") or {}).get("schema_fingerprint")
        ),
        "detail_record_fields": sorted(str(key) for key in detail),
        "party_fields": party_fields,
        "legal_fields": sorted(
            str(key) for key in (detail.get("legal") or {})
        ),
        "digital_object_fields": source_digital_object_fields,
    }
    return {
        "schema_contract": schema_contract,
        "rolling_observation": {
            "inventory": {
                "discovered_title_count": len(inventory),
                "discovered_title_ids": sorted(discovered_title_ids),
                "missing_verified_title_ids": sorted(
                    expected_title_ids - discovered_title_ids
                ),
                "new_title_ids": sorted(
                    discovered_title_ids - expected_title_ids
                ),
                "titles": [
                    {
                        "title_id": record.get("title_id"),
                        "title": record.get("title"),
                        "county_key": record.get("county_key"),
                        "label_matches_inventory": record.get(
                            "label_matches_inventory"
                        ),
                    }
                    for record in inventory
                ],
            },
            "title": {
                "title_id": title_detail.get("title_id"),
                "title": title_detail.get("title"),
                "coverage_label": title_config.coverage_label,
                "record_count": title_detail.get("record_count"),
                "image_availability": title_detail.get("image_availability"),
                "document_types_text": title_detail.get(
                    "document_types_text"
                ),
            },
            "search": {
                "total_count": search_page.total_count,
                "page_count": search_page.page_count,
                "page_size": search_page.page_size,
                "returned_count": len(search_page.records),
                "sentinel_present": sentinel_present,
                "records": _json_ready(search_page.records),
            },
            "detail": {
                "native_record_id": detail.get("native_record_id"),
                "title_id": detail.get("title_id"),
                "county_geoid": detail.get("county_geoid"),
                "reference_number": detail.get("reference_number"),
                "recording_date": detail.get("recording_date"),
                "document_type": detail.get("document_type"),
                "parties": _json_ready(detail.get("parties") or []),
                "legal": _json_ready(detail.get("legal") or {}),
                "digital_objects": digital_objects,
                "document_delivery": _json_ready(
                    detail.get("document_delivery") or {}
                ),
            },
            "image_generation_invoked": False,
        },
        "requests_made": 5,
    }


def probe_washington_digital_archives_land(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe anonymous archive operations without invoking document generation."""

    adapter = query_washington_digital_archives_land
    started = time.perf_counter()
    stable_contract = _washington_digital_archives_land_stable_contract()
    artifact_identity = _washington_digital_archives_land_artifact_identity()
    snapshot = _washington_digital_archives_land_snapshot(context)
    schema_contract = _json_ready(snapshot["schema_contract"])
    rolling_observation = _json_ready(snapshot["rolling_observation"])
    inventory_observation = rolling_observation["inventory"]
    search_observation = rolling_observation["search"]
    detail_observation = rolling_observation["detail"]
    complete = (
        not inventory_observation["missing_verified_title_ids"]
        and not inventory_observation["new_title_ids"]
        and search_observation["sentinel_present"] is True
        and detail_observation["native_record_id"]
        == artifact_identity["sentinel"]["record_id"]
        and detail_observation["title_id"]
        == artifact_identity["sentinel"]["title_id"]
    )
    stable_contract_sha256 = sha256_fingerprint(stable_contract)
    stable_schema_sha256 = sha256_fingerprint(schema_contract)
    return ProbeObservation(
        status=(
            ResultStatus.OK.value
            if complete
            else ResultStatus.PARTIAL.value
        ),
        endpoint=f"{adapter.BASE_URL}{adapter.TITLE_LIST_PATH}",
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=stable_schema_sha256,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=inventory_observation["discovered_title_count"],
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": stable_contract_sha256,
            "schema_contract": schema_contract,
            "stable_schema_sha256": stable_schema_sha256,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "requests_made": snapshot["requests_made"],
        },
    )


def _washington_taxsifter_selected_tenants(
    source_id: str,
) -> tuple[Any, ...]:
    """Resolve one leaf monitor or the complete county-family monitor."""

    adapter = query_washington_taxsifter
    if source_id == adapter.UMBRELLA_SOURCE_ID:
        return tuple(adapter.TENANTS)
    tenant = adapter.TENANTS_BY_SOURCE.get(source_id)
    if tenant is None:
        raise ValueError(f"unknown Washington TaxSifter source: {source_id}")
    return (tenant,)


def _washington_taxsifter_official_complements(
    tenant: Any,
) -> list[dict[str, Any]]:
    """Describe separately attributable fields without collapsing lineages."""

    adapter = query_washington_taxsifter
    complements: list[dict[str, Any]] = [
        {
            "kind": "washington_current_parcels_ecology",
            "source_id": query_washington_parcels.ECOLOGY_SOURCE_ID,
            "lineage_id": query_washington_parcels.LINEAGE_ID,
            "roles": ["parcel", "assessment", "situs", "geometry"],
            "relationship": (
                "same_county_assessor_origin_not_independent_corroboration"
            ),
        }
    ]
    if tenant.digital_archives_title_id is not None:
        complements.append(
            {
                "kind": "washington_digital_archives_recorded_land_title",
                "source_id": query_washington_digital_archives_land.SOURCE_ID,
                "lineage_id": adapter.RECORDER_LINEAGE,
                "title_id": tenant.digital_archives_title_id,
                "roles": ["recorded_instrument_index", "indexed_parties"],
                "relationship": "county_auditor_recorded_instrument_lineage",
            }
        )
    if tenant.key == "mason":
        complements.extend(
            [
                {
                    "kind": "mason_county_tax_parcels_gis",
                    "url": (
                        "https://gis.masoncountywa.gov/arcgis/rest/services/"
                        "MasonCoSite/TaxParcels/MapServer/0"
                    ),
                    "lineage_id": adapter.MAP_LINEAGE,
                    "roles": [
                        "parcel",
                        "assessment",
                        "owner",
                        "situs",
                        "legal",
                        "geometry",
                    ],
                    "relationship": (
                        "distinct_county_gis_assessment_representation"
                    ),
                },
                {
                    "kind": "mason_county_auditor_eagleweb",
                    "url": (
                        "https://recording.masoncountywa.gov/recorder/web/"
                    ),
                    "lineage_id": adapter.RECORDER_LINEAGE,
                    "roles": [
                        "grantor_grantee",
                        "recorded_instrument",
                        "recording_date",
                        "legal_description",
                    ],
                    "relationship": "current_county_auditor_instrument_index",
                },
            ]
        )
    return complements


def _washington_taxsifter_tenant_stable_contract(
    tenant: Any,
) -> dict[str, Any]:
    """Return one county contract without current counts or property values."""

    adapter = query_washington_taxsifter
    operation_states = dict(tenant.source.metadata["operation_states"])
    return {
        "source_id": tenant.source_id,
        "umbrella_source_id": adapter.UMBRELLA_SOURCE_ID,
        "county": tenant.key,
        "county_name": tenant.county_name,
        "county_geoid": tenant.county_geoid,
        "authority": tenant.authority,
        "portal_root": tenant.portal_root,
        "search_path": tenant.search_path,
        "official_root_aliases": list(tenant.observed_hosts),
        "official_data_link": tenant.observed_data_link,
        "deployment_variant": tenant.deployment_variant,
        "catalog_baseline_access_state": tenant.access_state,
        "catalog_baseline_operation_states": operation_states,
        "operations": {
            operation.value: {
                **dict(adapter.OPERATION_LINEAGES[operation]),
                "route": {
                    adapter.Operation.SEARCH: tenant.search_path,
                    adapter.Operation.ASSESSOR: (
                        "Assessor.aspx?keyId={key_id}&"
                        "parcelNumber={parcel}&typeID={type_id}"
                    ),
                    adapter.Operation.TREASURER: (
                        "Treasurer.aspx?keyId={key_id}&"
                        "parcelNumber={parcel}&typeID={type_id}"
                    ),
                    adapter.Operation.APPRAISAL: (
                        "AppraisalDetails.aspx?keyId={key_id}&"
                        "parcelNumber={parcel}&typeID={type_id}"
                    ),
                    adapter.Operation.SALES: (
                        "SalesSearch/SalesSearch.aspx (ASP.NET postback)"
                    ),
                }[operation],
            }
            for operation in adapter.Operation
        },
        "ordinary_session_flow": (
            "target GET -> Disclaimer.aspx -> replay hidden fields with "
            "btnAgree -> retry target in the same session"
        ),
        "response_states": [state.value for state in adapter.ResponseState],
        "identity": {
            "account_occurrence": ["source_id", "key_id", "type_id"],
            "parcel_join": ["county_geoid", "parcel_number"],
            "sale_occurrence": [
                "parcel_number",
                "sale_date_iso",
                "sale_document",
                "excise_number",
            ],
        },
        "sales_pagination": {
            "state": adapter.SALES_PAGINATION_STATE,
            "continuation_verified": False,
            "published_count_and_returned_count_are_distinct": True,
        },
        "lineages": {
            "assessor": adapter.ASSESSOR_LINEAGE,
            "treasurer": adapter.TREASURER_LINEAGE,
            "recorder": adapter.RECORDER_LINEAGE,
            "map": adapter.MAP_LINEAGE,
        },
        "official_complements": _washington_taxsifter_official_complements(
            tenant
        ),
        "notes": list(tenant.notes),
    }


def _washington_taxsifter_stable_contract(
    source_id: str,
) -> dict[str, Any]:
    adapter = query_washington_taxsifter
    selected = _washington_taxsifter_selected_tenants(source_id)
    return {
        "source_id": source_id,
        "platform_family": adapter.PLATFORM_FAMILY,
        "adapter_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "probe_schema_version": adapter.PROBE_SCHEMA_VERSION,
        "tenant_count": len(selected),
        "family_tenant_count": len(adapter.TENANTS),
        "live_verified_tenant_count": len(adapter.VERIFIED_TENANT_KEYS),
        "tenants": [
            _washington_taxsifter_tenant_stable_contract(tenant)
            for tenant in selected
        ],
        "interpretation": {
            "operation_state_scope": "tenant_and_operation",
            "no_results_meaning": "accessible_authoritative_empty_response",
            "assessor_views_are_independent_corroboration": False,
            "assessor_sales_are_recorded_instruments": False,
            "recorder_and_treasurer_lineages_are_interchangeable": False,
        },
    }


def _washington_taxsifter_schema_contract(
    source_id: str,
) -> dict[str, Any]:
    """Return stable probe shapes while values and counts remain rolling."""

    adapter = query_washington_taxsifter
    selected = _washington_taxsifter_selected_tenants(source_id)
    return {
        "probe_schema_version": adapter.PROBE_SCHEMA_VERSION,
        "tenant_source_ids": [tenant.source_id for tenant in selected],
        "operation_observation_fields": {
            "search": [
                "response_state",
                "source_urls",
                "total_count",
                "parcel_number",
            ],
            "assessor": [
                "response_state",
                "source_url",
                "parcel_number",
                "published_operation_links",
                "sale_count",
                "permit_count",
                "valuation_count",
                "data_current_as",
                "roll_year",
            ],
            "treasurer": [
                "response_state",
                "source_url",
                "parcel_number",
                "data_current_as",
                "roll_year",
                "current_tax_rows",
                "balance_rows",
                "receipt_rows",
            ],
            "appraisal": [
                "response_state",
                "source_url",
                "parcel_number",
                "data_current_as",
                "roll_year",
                "section_count",
            ],
            "sales": [
                "response_state",
                "source_url",
                "result_count",
                "negotiated_fields",
                "native_pagination",
                "data_current_as",
                "roll_year",
            ],
        },
        "operation_state_fields": [
            "status",
            "response_state",
            "accessible",
            "observation",
        ],
    }


def _washington_taxsifter_artifact_identity(
    source_id: str,
) -> dict[str, Any]:
    selected = _washington_taxsifter_selected_tenants(source_id)
    return {
        "source_id": source_id,
        "sentinels": [
            {
                "source_id": tenant.source_id,
                "county_geoid": tenant.county_geoid,
                "sentinel_query": tenant.sentinel_query,
            }
            for tenant in selected
        ],
    }


def _washington_taxsifter_operation_states(
    _tenant: Any,
    payload: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Normalize current probe outcomes without treating emptiness as failure."""

    adapter = query_washington_taxsifter
    records = payload.get("records")
    if isinstance(records, list) and records:
        raw_observations = records[0].get("operation_observations") or {}
        normalized: dict[str, dict[str, Any]] = {}
        for operation in adapter.Operation:
            observation = raw_observations.get(operation.value)
            if not isinstance(observation, Mapping):
                normalized[operation.value] = {
                    "status": "not_observed",
                    "response_state": None,
                    "accessible": None,
                    "observation": None,
                }
                continue
            response_state = observation.get("response_state")
            capability_state = observation.get("capability_state")
            if response_state == adapter.ResponseState.LIVE.value:
                status = ResultStatus.OK.value
                accessible: bool | None = True
            elif response_state == adapter.ResponseState.NO_RESULT.value:
                status = ResultStatus.NO_RESULTS.value
                accessible = True
            elif capability_state == "link_not_published":
                status = "not_published_for_sentinel"
                accessible = None
            else:
                status = str(response_state or capability_state or "not_observed")
                accessible = None
            normalized[operation.value] = {
                "status": status,
                "response_state": response_state,
                "accessible": accessible,
                "observation": _json_ready(observation),
            }
        return normalized

    status = str(payload.get("status") or ResultStatus.UNAVAILABLE.value)
    errors = payload.get("errors")
    first_error = (
        errors[0]
        if isinstance(errors, list)
        and errors
        and isinstance(errors[0], Mapping)
        else {}
    )
    error_details = first_error.get("details")
    if not isinstance(error_details, Mapping):
        error_details = {}
    response_state = error_details.get("response_state")
    normalized = {}
    for operation in adapter.Operation:
        if operation == adapter.Operation.SEARCH:
            normalized[operation.value] = {
                "status": status,
                "response_state": response_state,
                "accessible": False,
                "observation": {
                    "error_code": first_error.get("code"),
                    "error_category": first_error.get("category"),
                    "error_details": _json_ready(error_details),
                },
            }
        else:
            normalized[operation.value] = {
                "status": "not_probed_after_search_failure",
                "response_state": None,
                "accessible": None,
                "observation": {"upstream_status": status},
            }
    return normalized


def _washington_taxsifter_tenant_snapshot(
    context: ProbeContext,
    tenant: Any,
) -> dict[str, Any]:
    """Run all five operations for one tenant through its real session flow."""

    adapter = query_washington_taxsifter
    client = adapter.TaxSifterClient(
        tenant,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    args = argparse.Namespace(
        command="probe",
        county=tenant.key,
        source=None,
        operations="all",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    result = adapter._probe_result(
        args,
        tenant,
        client=client,
        log_results=False,
    )
    payload = result.to_dict()
    errors = payload.get("errors")
    first_error = (
        errors[0]
        if isinstance(errors, list)
        and errors
        and isinstance(errors[0], Mapping)
        else None
    )
    return {
        "source_id": tenant.source_id,
        "county": tenant.key,
        "county_geoid": tenant.county_geoid,
        "status": str(payload["status"]),
        "endpoint": tenant.portal_root,
        "operation_states": _washington_taxsifter_operation_states(
            tenant,
            payload,
        ),
        "request_count": client.request_count,
        "warnings": list(payload.get("warnings") or []),
        "error": (
            str(first_error.get("message") or first_error.get("code"))
            if first_error
            else None
        ),
    }


def _washington_taxsifter_aggregate_status(
    snapshots: Sequence[Mapping[str, Any]],
) -> str:
    statuses = {str(snapshot["status"]) for snapshot in snapshots}
    successful = {
        ResultStatus.OK.value,
        ResultStatus.NO_RESULTS.value,
    }
    if statuses <= successful:
        return ResultStatus.OK.value
    if statuses & successful:
        return ResultStatus.PARTIAL.value
    if len(statuses) == 1:
        return next(iter(statuses))
    return ResultStatus.UNAVAILABLE.value


def probe_washington_taxsifter(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one TaxSifter leaf or the complete tenant-by-operation matrix."""

    started = time.perf_counter()
    selected = _washington_taxsifter_selected_tenants(context.source_id)
    stable_contract = _washington_taxsifter_stable_contract(context.source_id)
    schema_contract = _washington_taxsifter_schema_contract(context.source_id)
    artifact_identity = _washington_taxsifter_artifact_identity(
        context.source_id
    )
    snapshots = [
        _washington_taxsifter_tenant_snapshot(context, tenant)
        for tenant in selected
    ]
    status = _washington_taxsifter_aggregate_status(snapshots)
    accessible_operations = sum(
        1
        for snapshot in snapshots
        for state in snapshot["operation_states"].values()
        if state["accessible"] is True
    )
    requests_made = sum(
        int(snapshot.get("request_count") or 0)
        for snapshot in snapshots
    )
    error = None
    if status not in {
        ResultStatus.OK.value,
        ResultStatus.NO_RESULTS.value,
        ResultStatus.PARTIAL.value,
    }:
        error = "; ".join(
            str(snapshot["error"])
            for snapshot in snapshots
            if snapshot.get("error")
        ) or f"Washington TaxSifter probe returned {status}"
    return ProbeObservation(
        status=status,
        endpoint=(
            query_washington_parcels.ECOLOGY_LAYER_URL
            if context.source_id
            == query_washington_taxsifter.UMBRELLA_SOURCE_ID
            else selected[0].portal_root
        ),
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=accessible_operations,
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": sha256_fingerprint(stable_contract),
            "schema_contract": schema_contract,
            "stable_schema_sha256": sha256_fingerprint(schema_contract),
            "artifact_identity": artifact_identity,
            "rolling_observation": {
                "tenant_operation_states": snapshots,
                "accessible_operation_count": accessible_operations,
            },
            "requests_made": requests_made,
        },
        error=error,
    )


def probe_mason_county_tax_parcels(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe Mason's non-pageable GIS layer and separate rolling row values."""

    adapter = query_mason_county_tax_parcels
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Mason Tax Parcels monitor received another source")
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "layer_url": adapter.LAYER_URL,
        "query_url": adapter.QUERY_URL,
        "required_fields": list(adapter.REQUIRED_FIELDS),
        "feature_occurrence_identity": [adapter.OBJECT_ID_FIELD],
        "candidate_parcel_join_fields": list(adapter.PARCEL_FIELDS),
        "candidate_parcel_join_uniqueness_assumed": False,
        "traversal": {
            "id_snapshot": "returnIdsOnly",
            "stable_order": "client_sorted_FID_ascending",
            "feature_fetch": "objectIds_batches",
            "offset_pagination_used": False,
            "server_order_by_used": False,
        },
        "source_scope": {
            "current_assessor_gis_fields": True,
            "recorder_instruments": False,
            "treasury_balances_or_payment_history": False,
            "recorded_title_conclusion": False,
            "surveyed_legal_boundary": False,
        },
    }
    started = time.perf_counter()
    client = adapter.MasonCountyTaxParcelsClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    batch = adapter.fetch_feature_batch(
        client,
        operation="probe",
        spec=adapter.QuerySpec(
            where="1=1",
            geometry_parameters={},
            return_geometry=False,
        ),
        limit=1,
        cursor=None,
    )
    record = adapter._probe_record(batch)
    if record.get("source_id") != adapter.SOURCE_ID:
        raise ValueError("Mason Tax Parcels probe returned another source")
    if record.get("requests_made") != batch.requests_made:
        raise ValueError("Mason Tax Parcels request accounting changed")

    schema_contract = {
        "schema_fingerprint": batch.contract.schema_fingerprint,
        "field_names": list(batch.contract.field_names),
        "object_id_field": batch.contract.object_id_field,
        "geometry_type": batch.contract.geometry_type,
        "spatial_reference": dict(batch.contract.spatial_reference),
        "max_record_count": batch.contract.max_record_count,
        "supports_pagination": batch.contract.supports_pagination,
        "supports_order_by": batch.contract.supports_order_by,
        "supports_statistics": batch.contract.supports_statistics,
        "supports_advanced_queries": (
            batch.contract.supports_advanced_queries
        ),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "layer_url": adapter.LAYER_URL,
        "object_id_field": adapter.OBJECT_ID_FIELD,
        "record_grain": "current_assessor_gis_feature",
    }
    rolling_observation = {
        "feature_count": record.get("feature_count"),
        "id_snapshot_fingerprint": record.get(
            "id_snapshot_fingerprint"
        ),
        "smallest_object_id": record.get("smallest_object_id"),
        "sample": record.get("sample"),
    }
    return ProbeObservation(
        status=(
            ResultStatus.OK.value
            if batch.matching_object_ids
            else ResultStatus.NO_RESULTS.value
        ),
        endpoint=adapter.LAYER_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=batch.contract.schema_fingerprint,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(batch.matching_object_ids),
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": sha256_fingerprint(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "requests_made": batch.requests_made,
        },
    )


def probe_maryland_mdp_parcel_points(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the statewide point layer while isolating rolling population."""

    adapter = query_md_mdp_parcel_points
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Maryland Parcel Points monitor received another source")
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "layer_url": adapter.LAYER_URL,
        "query_url": adapter.QUERY_URL,
        "required_fields": list(adapter.REQUIRED_FIELDS),
        "feature_occurrence_identity": adapter.OBJECT_ID_FIELD,
        "cross_representation_record_identity": {
            "source_id": adapter.RECORD_IDENTITY_SOURCE_ID,
            "field": adapter.ACCOUNT_ID_FIELD,
            "relationship": "exact_cross_representation_parcel_account_join",
        },
        "traversal": {
            "stable_order": "OBJECTID_ascending",
            "snapshot_boundary": "maximum_matching_OBJECTID",
            "pagination": "resultOffset_with_live_maxRecordCount",
            "caller_limit_required": False,
        },
        "source_scope": {
            "current_owner_name_published": False,
            "owner_mailing_address_is_ownership_assertion": False,
            "parcel_point_is_surveyed_boundary": False,
            "recorded_instrument_copy": False,
        },
    }
    started = time.perf_counter()
    client = adapter.MarylandParcelPointsClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    metadata = client.fetch_metadata()
    contract = adapter.metadata_contract(metadata)
    record = adapter._probe_record(client, metadata, contract)
    if record.get("source_id") != adapter.SOURCE_ID:
        raise ValueError("Maryland Parcel Points probe returned another source")

    schema_contract = {
        "schema_fingerprint": contract.schema_fingerprint,
        "field_names": list(contract.field_names),
        "object_id_field": contract.object_id_field,
        "geometry_type": contract.geometry_type,
        "spatial_reference": dict(contract.spatial_reference),
        "max_record_count": contract.max_record_count,
        "supports_pagination": True,
        "supports_order_by": True,
        "supports_statistics": True,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "record_identity_source_id": adapter.RECORD_IDENTITY_SOURCE_ID,
        "layer_url": adapter.LAYER_URL,
        "feature_occurrence_field": adapter.OBJECT_ID_FIELD,
        "record_identity_field": adapter.ACCOUNT_ID_FIELD,
    }
    rolling_observation = dict(record.get("rolling_observations") or {})
    feature_count = rolling_observation.get("feature_count")
    return ProbeObservation(
        status=(
            ResultStatus.OK.value
            if isinstance(feature_count, int) and feature_count > 0
            else ResultStatus.NO_RESULTS.value
        ),
        endpoint=adapter.LAYER_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=contract.schema_fingerprint,
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1 if rolling_observation.get("sample") else 0,
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": sha256_fingerprint(stable_contract),
            "schema_contract": schema_contract,
            "stable_schema_sha256": sha256_fingerprint(schema_contract),
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "requests_made": getattr(client, "request_count", None),
        },
    )


def probe_maryland_plats(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe county, source-total, paging, and exact-unit plat contracts."""

    adapter = query_md_plats
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Maryland Plats monitor received another source")
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "adapter_family": "maryland_plats",
        "form_family": "ASP.NET WebForms",
        "county_routes": [
            {
                "county_code": code,
                "county_geoid": geoid,
                "county_name": name,
            }
            for code, (geoid, name) in adapter.COUNTY_GEOIDS.items()
        ],
        "search_modes": ["basic", "advanced", "series"],
        "sort_values": dict(adapter.SORT_VALUES),
        "result_headers": list(adapter.RESULT_HEADERS),
        "record_identity": [
            "county_code",
            "archive_qualifier",
            "archive_series",
            "archive_unit",
        ],
        "result_occurrence": [
            "selection_fingerprint",
            "absolute_position",
            "representation_identity",
        ],
        "pagination": {
            "source_total_authority": True,
            "native_page_capacity_observed": 300,
            "next_postback_control": "ctl00$body$imgButtonNext",
            "complete_by_default": True,
            "cursor_only_for_explicit_caller_limit": True,
        },
        "metadata_only_rows": {
            "toggle_control": "ctl00$body$ckhide",
            "retained": True,
        },
        "exact_unit_without_search_session": True,
        "artifact_formats": ["application/pdf", "image/tiff", "image/jpeg"],
        "complementary_source_ids": [
            item["source_id"] for item in adapter.COMPLEMENTARY_SOURCES
        ],
    }
    started = time.perf_counter()
    client = adapter.MarylandPlatsClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    try:
        counties = client.counties()
        observed_counties = [
            (county.code, county.name) for county in counties
        ]
        expected_counties = [
            (code, name)
            for code, (_geoid, name) in adapter.COUNTY_GEOIDS.items()
        ]
        if observed_counties != expected_counties:
            raise ValueError(
                "Maryland Plats county selector contract changed"
            )
        selection = adapter.SearchSelection(
            county_code="MO",
            mode="advanced",
            description="Estate",
            include_no_images=True,
        )
        search = client.search(selection, limit=1)
        if len(search.records) != 1:
            raise ValueError(
                "Maryland Plats bounded monitor search returned no sample"
            )
        detail = client.fetch_plat("MO", "C", "1136", "1")
        expected_identity = {
            "county_code": "MO",
            "archive_qualifier": "C",
            "archive_series": "1136",
            "archive_unit": "1",
            "msa_accession": "MSA C1136-1",
        }
        if detail.get("record_identity") != expected_identity:
            raise ValueError(
                "Maryland Plats exact-unit sentinel identity changed"
            )
    finally:
        client.close()

    sample = dict(search.records[0])
    representation = dict(
        sample.get("source_result_representation") or {}
    )
    occurrence = dict(sample.get("result_occurrence") or {})
    detail_artifacts = [
        dict(artifact)
        for artifact in detail.get("artifacts", ())
        if isinstance(artifact, Mapping)
    ]
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "form_contract_fingerprint": search.form_contract_fingerprint,
        "result_schema_fingerprints": sorted(
            search.result_schema_fingerprints
        ),
        "search_record_fields": sorted(sample),
        "detail_record_fields": sorted(detail),
        "artifact_fields": sorted(
            {
                str(key)
                for artifact in detail_artifacts
                for key in artifact
            }
        ),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "exact_unit": expected_identity,
        "published_representations": [
            {
                "artifact_role": artifact.get("artifact_role"),
                "ordinal_within_role": artifact.get(
                    "ordinal_within_role"
                ),
                "file_format": artifact.get("file_format"),
            }
            for artifact in detail_artifacts
        ],
    }
    rolling_observation = {
        "search_description": "Estate",
        "source_image_result_count": search.source_image_result_count,
        "source_total_result_count": search.source_total_result_count,
        "source_total_pages": search.source_total_pages,
        "native_pages_fetched": search.pages_fetched,
        "continuation_cursor_returned": search.next_cursor is not None,
        "sample_record_identity": sample.get("record_identity"),
        "sample_result_occurrence": occurrence,
        "sample_image_availability": representation.get(
            "image_availability"
        ),
        "exact_unit_image_availability": detail.get(
            "image_availability"
        ),
        "exact_unit_artifact_count": len(detail_artifacts),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.INDEX_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": sha256_fingerprint(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "requests_made": 2 + search.requests_made,
        },
    )


def probe_maryland_mdp_property_download(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one current data artifact from an MDP bulk source family."""

    adapter = query_md_mdp_property_downloads
    if context.source_id not in adapter.SOURCE_IDS:
        raise ValueError(
            "Maryland MDP download monitor received an unknown source"
        )
    argv = [
        "probe",
        "--source",
        context.source_id,
        "--sample-bytes",
        str(
            context.sample_bytes
            if context.sample_bytes is not None
            else 64
        ),
        "--timeout",
        str(context.timeout),
        "--retry-attempts",
        str(context.max_attempts),
        "--minimum-interval",
        str(_catalog_interval(context.catalog_decision)),
    ]
    args = adapter.build_parser().parse_args(argv)
    started = time.perf_counter()
    result = adapter.execute(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.LANDING_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "Maryland MDP download probe expected one artifact record"
        )
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
        or record.get("schema_reference") is not False
    ):
        raise ValueError(
            "Maryland MDP download probe selected another source, record "
            "kind, or a schema-preview artifact"
        )

    manifest = dict(record.get("manifest") or {})
    manifest_metadata = (
        dict(manifest.get("metadata") or {})
        if isinstance(manifest.get("metadata"), Mapping)
        else {}
    )
    capability = dict(record.get("capability") or {})
    identity_contract = dict(record.get("identity_contract") or {})
    probe = dict(record.get("artifact_probe") or {})
    validator = dict(
        record.get("validator_occurrence_identity") or {}
    )
    stable_contract = {
        "source": adapter._source_metadata(context.source_id).to_dict(),
        "manifest_schema_version": adapter.MANIFEST_SCHEMA_VERSION,
        "probe_schema_version": adapter.PROBE_SCHEMA_VERSION,
        "record_kind": "source_probe",
        "schema_profile": record.get("schema_profile"),
        "format": record.get("format"),
        "schema_reference": False,
        "capability": capability,
        "manifest_schema": manifest.get("schema"),
        "identity_contract": identity_contract,
    }
    occurrence_id = validator.get("validator_occurrence_id")
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(stable_contract),
        artifact_sha256=(
            str(occurrence_id)
            if occurrence_id
            else sha256_fingerprint(
                {
                    "provider_link_id": (
                        (record.get("provider_link") or {}).get(
                            "provider_link_id"
                        )
                        if isinstance(
                            record.get("provider_link"),
                            Mapping,
                        )
                        else None
                    ),
                    "etag": probe.get("etag"),
                    "last_modified": probe.get("last_modified"),
                    "content_length": probe.get("content_length"),
                    "sample_sha256": probe.get("sample_sha256"),
                }
            )
        ),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "stable_contract_sha256": sha256_fingerprint(
                stable_contract
            ),
            "release_id": record.get("release_id"),
            "release_group_id": record.get("release_group_id"),
            "release_set_fingerprint": manifest_metadata.get(
                "release_set_fingerprint"
            ),
            "selected_data_artifact": True,
            "schema_reference": False,
            "provider_link": record.get("provider_link"),
            "validator_occurrence_identity": validator,
            "artifact_probe": probe,
        },
    )


def probe_palm_beach_property_appraiser(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe both PBC GIS representations while isolating rolling values."""

    adapter = query_palm_beach_property_appraiser
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Palm Beach parcel monitor received another source")
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "primary_layer_url": adapter.LAYER_URL,
        "qsales_layer_url": adapter.QSALES_LAYER_URL,
        "required_fields": list(adapter.REQUIRED_FIELDS),
        "feature_occurrence_identity": [adapter.OBJECT_ID_FIELD],
        "candidate_exact_tax_account_join": "PARCEL_NUMBER",
        "candidate_parcel_join_uniqueness_assumed": False,
        "published_geometry_or_group_identifier": "PARID",
        "parid_uniqueness_assumed": False,
        "traversal": {
            "stable_order": "OBJECTID_ascending",
            "snapshot_boundary": "maximum_matching_OBJECTID",
            "pagination": "resultOffset_with_live_maxRecordCount",
            "caller_limit_required": False,
        },
        "representations": {
            "PARCEL_DETAILS": {
                "role": "primary_query_and_ingestion_representation",
                "independent_corroboration": False,
            },
            "PAO.PARCEL_QSALES": {
                "role": "same_publisher_sale_age_thematic_representation",
                "independent_corroboration": False,
                "exact_row_or_objectid_parity_established": False,
            },
        },
        "source_scope": {
            "assessment_owner_observation": True,
            "assessor_last_sale_observation": True,
            "recorder_instrument_copy": False,
            "recorded_title_conclusion": False,
            "publisher_redaction_state_preserved": True,
            "surveyed_legal_boundary": False,
        },
    }
    started = time.perf_counter()
    client = adapter.PalmBeachPropertyClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    metadata = client.fetch_metadata()
    primary_contract = adapter.metadata_contract(metadata)
    qsales_metadata = client.fetch_metadata(adapter.QSALES_LAYER_URL)
    qsales_contract = adapter.metadata_contract(
        qsales_metadata,
        layer_url=adapter.QSALES_LAYER_URL,
        expected_name=adapter.QSALES_LAYER_NAME,
    )
    primary_count = client.fetch_count("1=1")
    qsales_count = client.fetch_count(
        "1=1",
        query_url=adapter.QSALES_QUERY_URL,
    )
    parcel_number_count = client.fetch_distinct_count("PARCEL_NUMBER")
    parid_count = client.fetch_distinct_count("PARID")
    null_parid_count = client.fetch_count("PARID IS NULL")
    sample_batch = adapter.fetch_feature_batch(
        client,
        operation="probe",
        spec=adapter.QuerySpec(
            where="1=1",
            geometry_parameters={},
            return_geometry=False,
        ),
        limit=1,
        cursor=None,
    )
    sample = None
    if sample_batch.features:
        sample_attributes = dict(
            adapter._attributes(sample_batch.features[0])
        )
        sample = {
            "object_id": adapter._feature_object_id(
                sample_batch.features[0]
            ),
            "parcel_number": sample_attributes.get("PARCEL_NUMBER"),
            "parid": sample_attributes.get("PARID"),
            "confidential_flag": sample_attributes.get("CONFID_FLG"),
        }
    schema_contract = {
        "primary": primary_contract.to_dict(),
        "qsales": qsales_contract.to_dict(),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "primary_layer_url": adapter.LAYER_URL,
        "qsales_layer_url": adapter.QSALES_LAYER_URL,
        "record_grain": "published_parcel_detail_feature_occurrence",
    }
    rolling_observation = {
        "primary_feature_count": primary_count,
        "distinct_parcel_number_count": parcel_number_count,
        "distinct_parid_count": parid_count,
        "null_parid_count": null_parid_count,
        "qsales_feature_count": qsales_count,
        "primary_and_qsales_counts_equal": primary_count == qsales_count,
        "sample": sample,
    }
    return ProbeObservation(
        status=(
            ResultStatus.OK.value
            if primary_count
            else ResultStatus.NO_RESULTS.value
        ),
        endpoint=adapter.LAYER_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=primary_count,
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": sha256_fingerprint(stable_contract),
            "schema_contract": schema_contract,
            "stable_schema_sha256": sha256_fingerprint(schema_contract),
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "requests_made": client.request_count,
        },
    )


def probe_orange_tax_collector(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe current account routes without treating 2020 ZIPs as current."""

    adapter = query_orange_tax_collector
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError(
            "Orange Tax Collector monitor received another source"
        )
    started = time.perf_counter()
    client = adapter.OrangeTaxPortalClient(
        timeout=context.timeout,
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        minimum_interval=_catalog_interval(context.catalog_decision),
    )

    _landing_url, landing_html = client.bulk_landing_html()
    landing_observation = adapter.parse_bulk_landing_page(landing_html)
    bulk_artifact_probes: dict[str, dict[str, Any]] = {}
    bulk_probe_requests = 0
    for dataset, publication in adapter.BULK_PUBLICATIONS.items():
        probe, requests_made = _counted_bulk_probe(
            publication.artifact("data"),
            context,
            user_agent=adapter.USER_AGENT,
        )
        bulk_probe_requests += requests_made
        if (
            probe.get("signature_hex") is None
            or not str(probe["signature_hex"]).startswith("504b")
        ):
            raise adapter.OrangeTaxSourceChanged(
                "Orange historical data artifact no longer has a ZIP signature",
                details={"dataset": dataset, "probe": probe},
            )
        bulk_artifact_probes[dataset] = probe
    portal_result = client.search(
        ORANGE_TAX_COLLECTOR_SENTINEL_ACCOUNT,
        limit=adapter.ALGOLIA_HITS_PER_PAGE,
    )
    exact_hits = [
        record
        for record in portal_result.records
        if (
            record.get("parcel_join") or {}
        ).get("normalized_15_digit_account")
        == ORANGE_TAX_COLLECTOR_SENTINEL_ACCOUNT
    ]
    if len(exact_hits) > 1:
        raise adapter.OrangeTaxSourceChanged(
            "Orange monitor sentinel resolved to duplicate exact accounts",
            details={
                "sentinel_account": ORANGE_TAX_COLLECTOR_SENTINEL_ACCOUNT,
                "exact_hit_count": len(exact_hits),
            },
        )

    exact_hit = exact_hits[0] if exact_hits else None
    history_url = None
    history_records: list[dict[str, Any]] = []
    if exact_hit is not None:
        account_token = str(exact_hit["taxsys_account_token"])
        history_url, history_html = client.history_html(account_token)
        history_records = adapter.parse_bill_history_html(
            history_html,
            account_token=account_token,
            parcel_account=ORANGE_TAX_COLLECTOR_SENTINEL_ACCOUNT,
            source_url=history_url,
        )

    bulk_contracts = {
        dataset: {
            "dataset": publication.dataset,
            "release_id": publication.release_id,
            "publication_date": adapter.PUBLICATION_DATE,
            "publication_state": "fixed_historical_snapshot",
            "data_url": publication.data_url,
            "layout_url": publication.layout_url,
            "member_name": publication.member_name,
            "schema_fingerprint": publication.schema_fingerprint,
        }
        for dataset, publication in adapter.BULK_PUBLICATIONS.items()
    }
    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "platform_family": "govhub_algolia_taxsys",
        "current_portal": {
            "portal_url": adapter.GOVHUB_PORTAL_URL,
            "algolia_url": adapter.ALGOLIA_URL,
            "algolia_application_id": adapter.ALGOLIA_APPLICATION_ID,
            "algolia_index": adapter.ALGOLIA_INDEX,
            "hits_per_page": adapter.ALGOLIA_HITS_PER_PAGE,
            "taxsys_direct_root": adapter.TAXSYS_ROOT,
            "taxsys_embedded_lineage": adapter.EMBEDDED_TAXSYS_ROOT,
            "history_route": (
                "{taxsys_direct_root}/property-tax/{account_token}/"
                "load-bill-history"
            ),
            "bill_route": (
                "{taxsys_direct_root}/property-tax/{account_token}/bills/"
                "{bill_uuid}"
            ),
        },
        "historical_bulk": {
            "official_page": adapter.OFFICIAL_TAX_ROLL_PAGE,
            "publications": bulk_contracts,
            "landing_label": "Daily",
            "adapter_publication_state": "fixed_historical_snapshot",
        },
        "identity": {
            "parcel_join": "exact_normalized_15_digit_account",
            "portal_occurrence": "algolia_object_id",
            "account_locator": "taxsys_account_token",
            "bill_occurrence": "bill_uuid",
            "certificate_occurrence": "certificate_number",
            "receipt_occurrence": "receipt_number",
            "tax_summary_id": "separate_source_identifier",
            "bulk_row_occurrence": [
                "artifact_sha256",
                "archive_member_path",
                "source_row_number",
            ],
        },
    }
    schema_contract = {
        "output_schema_version": adapter.OUTPUT_SCHEMA_VERSION,
        "portal_response_contract_fingerprints": sorted(
            set(portal_result.response_contract_fingerprints)
        ),
        "historical_bulk_schema_fingerprints": {
            dataset: publication.schema_fingerprint
            for dataset, publication in adapter.BULK_PUBLICATIONS.items()
        },
        "landing_artifact_filenames": sorted(
            Path(publication.data_url).name
            for publication in adapter.BULK_PUBLICATIONS.values()
        )
        + sorted(
            Path(publication.layout_url).name
            for publication in adapter.BULK_PUBLICATIONS.values()
        ),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "current_portal": {
            "index": adapter.ALGOLIA_INDEX,
            "taxsys_root": adapter.TAXSYS_ROOT,
        },
        "historical_release_ids": sorted(
            publication.release_id
            for publication in adapter.BULK_PUBLICATIONS.values()
        ),
    }
    artifact_content_basis = {
        dataset: {
            "url": probe.get("url"),
            "content_length": probe.get("content_length"),
            "sample_size": probe.get("sample_size"),
            "sample_sha256": probe.get("sample_sha256"),
            "signature_hex": probe.get("signature_hex"),
        }
        for dataset, probe in bulk_artifact_probes.items()
    }
    artifact_transport_observations = {
        dataset: {
            "url": probe.get("url"),
            "http_status": probe.get("http_status"),
            "etag": probe.get("etag"),
            "last_modified": probe.get("last_modified"),
            "source_sha256": probe.get("source_sha256"),
            "accept_ranges": probe.get("accept_ranges"),
        }
        for dataset, probe in bulk_artifact_probes.items()
    }
    historical_artifact_observations = {
        "landing": landing_observation,
        "fixed_snapshots": {
            dataset: {
                "publication_date": adapter.PUBLICATION_DATE,
                "publication_state": "fixed_historical_snapshot",
                "data": {
                    "url": publication.data_url,
                    "observed_sha256": publication.observed_data_sha256,
                    "observed_size": publication.observed_data_size,
                    "observed_row_count": (
                        publication.observed_data_row_count
                    ),
                    "bounded_probe": bulk_artifact_probes[dataset],
                    "content_length_matches_observed": (
                        bulk_artifact_probes[dataset].get("content_length")
                        == publication.observed_data_size
                    ),
                },
                "layout": {
                    "url": publication.layout_url,
                    "observed_sha256": publication.observed_layout_sha256,
                    "observed_size": publication.observed_layout_size,
                },
            }
            for dataset, publication in adapter.BULK_PUBLICATIONS.items()
        },
        "full_bulk_artifacts_downloaded": 0,
        "bulk_artifact_sample_bytes_read": sum(
            int(probe.get("sample_size") or 0)
            for probe in bulk_artifact_probes.values()
        ),
    }
    rolling_observation = {
        "sentinel_account": ORANGE_TAX_COLLECTOR_SENTINEL_ACCOUNT,
        "portal_total_hits": portal_result.total_hits,
        "portal_pages_fetched": portal_result.pages_fetched,
        "exact_account_hit": exact_hit,
        "history_url": history_url,
        "history_record_count": len(history_records),
        "history_record_schema": (
            inferred_schema(history_records) if history_records else None
        ),
        "history_records": history_records,
    }
    return ProbeObservation(
        status=(
            ResultStatus.OK.value
            if exact_hit is not None
            else ResultStatus.NO_RESULTS.value
        ),
        endpoint=adapter.ALGOLIA_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_content_basis),
        result_count=len(exact_hits),
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": sha256_fingerprint(stable_contract),
            "schema_contract": schema_contract,
            "stable_schema_sha256": sha256_fingerprint(schema_contract),
            "artifact_identity": artifact_identity,
            "artifact_content_basis": artifact_content_basis,
            "artifact_transport_observations": (
                artifact_transport_observations
            ),
            "rolling_observation": rolling_observation,
            "historical_artifact_observations": (
                historical_artifact_observations
            ),
            "requests_made": client.request_count + bulk_probe_requests,
            "portal_requests": client.request_count,
            "bulk_probe_requests": bulk_probe_requests,
        },
    )


def probe_palm_beach_tax_collector(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe stable Aumentum routing separately from one rolling account row."""

    adapter = query_palm_beach_tax_collector
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError(
            "Palm Beach Tax Collector monitor received another source"
        )
    started = time.perf_counter()
    client = adapter.PalmBeachTaxClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    settings_payload = client.fetch_search_settings()
    settings = adapter.parse_search_settings(settings_payload)
    sync_payload = client.fetch_sync_status()
    sync_contract = adapter._sync_status_record(sync_payload)
    search_payload = client.fetch_search_page(adapter.SENTINEL_PCN, 1)
    rows, source_reported_total = adapter.parse_search_page(search_payload)
    sample = None
    if rows:
        sample = adapter.normalize_search_result(
            rows[0],
            criteria=adapter.SENTINEL_PCN,
            native_page=1,
            native_row=1,
            settings=settings,
            source_reported_total=source_reported_total,
        )

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "platform_family": "aumentum_publicaccessnow_dnn_property_tax",
        "endpoints": {
            "official_guidance": adapter.OFFICIAL_GUIDANCE_URL,
            "portal": adapter.SEARCH_PAGE_URL,
            "quick_search_settings": adapter.QUICK_SETTINGS_URL,
            "quick_search_data": adapter.QUICK_SEARCH_URL,
            "account_summary": adapter.ACCOUNT_SUMMARY_URL,
            "bills": adapter.BILLS_URL,
            "payment_history_settings": adapter.PAYMENT_SETTINGS_URL,
            "payment_history_data": adapter.PAYMENT_DATA_URL,
            "bill_detail": adapter.BILL_DETAIL_URL,
            "account_refresh": adapter.REFRESH_URL,
            "account_refresh_contract": adapter.SYNC_STATUS_URL,
        },
        "quick_search": {
            **settings.stable_contract(),
            "module_id": adapter.QUICK_SEARCH_MODULE_ID,
            "tab_id": adapter.QUICK_SEARCH_TAB_ID,
            "reported_total_equal_to_maximum_is_partial": True,
            "maximum_is_adapter_selected_cap": False,
        },
        "account_modules": {
            "summary": list(adapter.ACCOUNT_MODULE_IDS),
            "bills": adapter.BILLS_MODULE_ID,
            "payment_history": adapter.PAYMENT_HISTORY_MODULE_ID,
        },
        "account_refresh": {
            "module_id": sync_contract.get("module_id"),
            "tab_id": sync_contract.get("tab_id"),
            "active": sync_contract.get("active"),
            "navigate_to_url": sync_contract.get("navigate_to_url"),
            "refresh_selector": sync_contract.get("refresh_selector"),
            "settings_and_routing_metadata": True,
            "per_account_completion_poll": False,
        },
        "identity": {
            "parcel_join": "reversible_17_digit_pcn",
            "account_locator": "AlternateKey",
            "bill_id_bill_number_installment_receipt_and_payment": (
                "separate_source_identities"
            ),
        },
    }
    schema_contract = {
        "quick_search_settings": adapter._response_schema(
            settings_payload
        ),
        "account_refresh_contract": adapter._response_schema(sync_payload),
        "quick_search_page": adapter._response_schema(search_payload),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "portal_root": adapter.PORTAL_ROOT,
        "data_source": settings.data_source,
        "selected_view": settings.selected_view,
        "modules": {
            "quick_search": adapter.QUICK_SEARCH_MODULE_ID,
            "account_summary": list(adapter.ACCOUNT_MODULE_IDS),
            "bills": adapter.BILLS_MODULE_ID,
            "payment_history": adapter.PAYMENT_HISTORY_MODULE_ID,
            "account_refresh": adapter.REFRESH_MODULE_ID,
        },
    }
    rolling_observation = {
        "sentinel_pcn": adapter.SENTINEL_PCN,
        "source_reported_total": source_reported_total,
        "sample": sample,
    }
    return ProbeObservation(
        status=(
            ResultStatus.OK.value
            if rows
            else ResultStatus.NO_RESULTS.value
        ),
        endpoint=adapter.QUICK_SETTINGS_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=len(rows),
        details={
            "stable_contract": stable_contract,
            "stable_contract_sha256": sha256_fingerprint(stable_contract),
            "schema_contract": schema_contract,
            "stable_schema_sha256": sha256_fingerprint(schema_contract),
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
            "requests_made": client.request_count,
        },
    )


def probe_palm_beach_tax_deeds(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the Clerk contract while isolating rolling case/source state."""

    adapter = query_palm_beach_tax_deeds
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError(
            "Palm Beach Tax Deeds monitor received another source"
        )
    args = adapter.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    started = time.perf_counter()
    result = adapter.execute(args)
    observation = _adapter_result_observation(
        result,
        endpoint=adapter.HOME_URL,
        started=started,
    )
    if not result.records:
        return observation
    if len(result.records) != 1:
        raise ValueError(
            "Palm Beach Tax Deeds probe expected one health record"
        )
    record = dict(result.records[0])
    if (
        record.get("record_kind") != "source_health_check"
        or record.get("source_id") != adapter.SOURCE_ID
        or record.get("status") != "ok"
    ):
        raise ValueError("Palm Beach Tax Deeds probe contract changed")
    stable_contract = record.get("stable_contract")
    rolling_observation = record.get("rolling_observation")
    artifact_identity = record.get("artifact_identity")
    if (
        not isinstance(stable_contract, Mapping)
        or not isinstance(rolling_observation, Mapping)
        or not isinstance(artifact_identity, Mapping)
    ):
        raise ValueError(
            "Palm Beach Tax Deeds probe sections are missing"
        )
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(stable_contract),
        artifact_sha256=sha256_fingerprint(artifact_identity),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": dict(stable_contract),
            "stable_contract_sha256": sha256_fingerprint(stable_contract),
            "artifact_identity": dict(artifact_identity),
            "rolling_observation": dict(rolling_observation),
            "requests_made": record.get("request_count"),
        },
    )


def _washington_parcel_representation_for_source(
    source_id: str,
) -> Any:
    for representation in query_washington_parcels.REPRESENTATIONS.values():
        if representation.source_id == source_id:
            return representation
    raise ValueError(f"unknown Washington parcel representation: {source_id}")


def _washington_parcel_client(
    context: ProbeContext,
    layer_url: str,
    *,
    maximum_page_size: int,
) -> Any:
    return query_washington_parcels.WashingtonArcGISClient(
        layer_url,
        page_size=min(2_000, maximum_page_size),
        max_page_size=maximum_page_size,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )


def _washington_parcel_stable_contract(source_id: str) -> dict[str, Any]:
    adapter = query_washington_parcels
    if source_id in {
        representation.source_id for representation in adapter.REPRESENTATIONS.values()
    }:
        representation = _washington_parcel_representation_for_source(source_id)
        return {
            "source": representation.source_metadata().to_dict(),
            "lineage_id": adapter.LINEAGE_ID,
            "lineage_relationship": "same_normalized_state_county_dataset",
            "representation": representation.key,
            "representation_role": representation.role,
            "required_fields": [
                *adapter.COMMON_REQUIRED_FIELDS,
                *(["ORIG_LANDUSE_CD"] if representation.has_original_land_use else []),
            ],
            "county_selector_style": representation.county_value_style,
            "county_detail_link_field": "DATA_LINK",
            "mirror_comparison_is_corroboration": False,
        }
    if source_id == adapter.FRESHNESS_SOURCE_ID:
        return {
            "source": adapter.FRESHNESS_METADATA.to_dict(),
            "lineage_id": adapter.LINEAGE_ID,
            "join_key": ["COUNTY_NM"],
            "required_fields": ["OBJECTID", "COUNTY_NM", "FILE_DATE"],
            "expected_counties": 39,
        }
    if source_id == adapter.LAND_USE_SOURCE_ID:
        return {
            "source": adapter.LAND_USE_METADATA.to_dict(),
            "lineage_id": adapter.LINEAGE_ID,
            "join_key": ["COUNTY_NM", "CODE"],
            "required_fields": [
                "OBJECTID",
                "COUNTY_NM",
                "CODE",
                "CODE_DESC",
            ],
        }
    if source_id == adapter.LINEAGE_ID:
        return {
            "source": adapter.LINEAGE_METADATA.to_dict(),
            "lineage_id": adapter.LINEAGE_ID,
            "parity_interpretation": "mirror_health_not_corroboration",
            "representations": [
                {
                    "source_id": representation.source_id,
                    "representation": representation.key,
                    "role": representation.role,
                    "layer_url": representation.layer_url,
                    "relationship": "same_normalized_state_county_dataset",
                }
                for representation in adapter.REPRESENTATIONS.values()
            ],
        }
    raise ValueError(f"unknown Washington parcel source: {source_id}")


def probe_washington_parcel_representation(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one parcel representation's schema, total, and exact sentinel."""

    adapter = query_washington_parcels
    representation = _washington_parcel_representation_for_source(context.source_id)
    stable_contract = _washington_parcel_stable_contract(context.source_id)
    started = time.perf_counter()
    client = _washington_parcel_client(
        context,
        representation.layer_url,
        maximum_page_size=representation.max_page_size,
    )
    metadata = client.fetch_metadata()
    schema_contract = adapter._metadata_contract(representation, metadata)
    total_count = client.fetch_count("1=1")
    sentinel_where = f"PARCEL_ID_NR='{adapter.SENTINEL_PARCEL_ID}'"
    sentinel_count = client.fetch_count(sentinel_where)
    rows = client.fetch_page(
        where=sentinel_where,
        offset=0,
        record_count=1,
        return_geometry=False,
    )
    if sentinel_count != 1 or len(rows) != 1:
        raise ValueError(
            f"{representation.key} parcel sentinel is missing or non-unique"
        )
    attributes = dict(adapter._feature_attributes(rows[0]))
    current_row = {
        field_name: attributes.get(field_name)
        for field_name in (
            "OBJECTID",
            "FIPS_NR",
            "COUNTY_NM",
            "PARCEL_ID_NR",
            "ORIG_PARCEL_ID",
            "SITUS_ADDRESS",
            "SUB_ADDRESS",
            "SITUS_CITY_NM",
            "SITUS_ZIP_NR",
            "LANDUSE_CD",
            "ORIG_LANDUSE_CD",
            "VALUE_LAND",
            "VALUE_BLDG",
            "FILE_DATE",
            "DATA_LINK",
        )
        if field_name in attributes
    }
    current_row["owner_related_values"] = {
        field_name: attributes.get(field_name)
        for field_name in schema_contract["owner_fields_detected"]
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=representation.layer_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=str(schema_contract["schema_fingerprint"]),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=total_count,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": {
                "total_count": total_count,
                "sentinel_count": sentinel_count,
                "sentinel": current_row,
            },
            "requests_made": client.request_count,
        },
    )


def probe_washington_parcel_companion(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one companion table's schema, current count, and one row."""

    adapter = query_washington_parcels
    stable_contract = _washington_parcel_stable_contract(context.source_id)
    if context.source_id == adapter.FRESHNESS_SOURCE_ID:
        layer_url = adapter.FRESHNESS_TABLE_URL
    elif context.source_id == adapter.LAND_USE_SOURCE_ID:
        layer_url = adapter.LAND_USE_TABLE_URL
    else:
        raise ValueError(f"unknown Washington parcel companion: {context.source_id}")
    started = time.perf_counter()
    client = _washington_parcel_client(
        context,
        layer_url,
        maximum_page_size=2_000,
    )
    metadata = client.fetch_metadata()
    fields = adapter._field_definitions(metadata)
    field_names = {str(field.get("name") or "") for field in fields}
    missing = sorted(set(stable_contract["required_fields"]) - field_names)
    if missing:
        raise ValueError(f"{context.source_id} companion table is missing {missing}")
    schema_sha256 = adapter.schema_fingerprint(adapter.arcgis_declared_schema(fields))
    total_count = client.fetch_count("1=1")
    rows = (
        client.fetch_page(
            where="1=1",
            offset=0,
            record_count=1,
            return_geometry=False,
        )
        if total_count
        else ()
    )
    sample = dict(adapter._feature_attributes(rows[0])) if rows else None
    return ProbeObservation(
        status=(
            ResultStatus.OK.value if total_count else ResultStatus.NO_RESULTS.value
        ),
        endpoint=layer_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=schema_sha256,
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=total_count,
        details={
            "stable_contract": stable_contract,
            "schema_contract": {
                "field_names": sorted(field_names),
                "geometry_type": metadata.get("geometryType"),
                "max_record_count": metadata.get("maxRecordCount"),
            },
            "rolling_observation": {
                "total_count": total_count,
                "sample": sample,
                "expected_count_met": (
                    total_count == 39
                    if context.source_id == adapter.FRESHNESS_SOURCE_ID
                    else None
                ),
            },
            "requests_made": client.request_count,
        },
    )


def probe_washington_parcel_lineage(
    context: ProbeContext,
) -> ProbeObservation:
    """Compare all three representations without treating mirrors as corroboration."""

    adapter = query_washington_parcels
    stable_contract = _washington_parcel_stable_contract(context.source_id)
    started = time.perf_counter()
    args = argparse.Namespace(
        page_size=2_000,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    clients = adapter._client_map(args)
    record = adapter._parity_record(clients, include_wisaard=True)
    schema_contract = {
        key: value.get("schema_fingerprint")
        for key, value in record["representations"].items()
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.ECOLOGY_LAYER_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=len(record["representations"]),
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": record,
            "requests_made": sum(client.request_count for client in clients.values()),
        },
    )


def _dc_property_component_for_source(source_id: str) -> Any:
    for component in query_dc_property.COMPONENTS.values():
        if component.source_id == source_id:
            return component
    raise ValueError(f"unknown District of Columbia property source: {source_id}")


def _dc_property_client(
    context: ProbeContext,
    component: Any,
) -> Any:
    return query_dc_property.DCArcGISClient(
        component.layer_url,
        page_size=1,
        max_records=1,
        timeout=context.timeout,
        minimum_interval=max(
            0.2,
            _catalog_interval(context.catalog_decision),
        ),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )


def _dc_property_stable_contract(source_id: str) -> dict[str, Any]:
    adapter = query_dc_property
    if source_id == adapter.LINEAGE_ID:
        return {
            "source_id": adapter.LINEAGE_ID,
            "jurisdiction_geoid": adapter.JURISDICTION_GEOID,
            "join_key": "SSL",
            "account_polygon_cardinality": "not_assumed_one_to_one",
            "components": [
                {
                    "source": component.source_metadata().to_dict(),
                    "component": component.key,
                    "layer_id": component.layer_id,
                    "record_kind": component.record_kind,
                    "stable_keys": list(component.stable_keys),
                }
                for component in adapter.COMPONENTS.values()
            ],
            "recorder_complement": {
                "source_id": adapter.RECORDER_SOURCE_ID,
                "url": "https://washington.dc.publicsearch.us/",
                "role": "recorded_instrument_index",
            },
        }
    component = _dc_property_component_for_source(source_id)
    relationship = component.source_metadata().metadata.get("lineage_relationship")
    return {
        "source": component.source_metadata().to_dict(),
        "lineage_id": adapter.LINEAGE_ID,
        "component": component.key,
        "layer_id": component.layer_id,
        "record_kind": component.record_kind,
        "stable_keys": list(component.stable_keys),
        "requested_fields": list(adapter.OUT_FIELDS_BY_COMPONENT[component.key]),
        "lineage_relationship": relationship,
        "account_polygon_cardinality": (
            "not_assumed_one_to_one"
            if component.key in {"assessment", "geometry"}
            else None
        ),
        "recorder_complement_source_id": adapter.RECORDER_SOURCE_ID,
    }


def probe_dc_property_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one DCGIS component's schema, count, and exact sentinel."""

    adapter = query_dc_property
    component = _dc_property_component_for_source(context.source_id)
    stable_contract = _dc_property_stable_contract(context.source_id)
    started = time.perf_counter()
    client = _dc_property_client(context, component)
    metadata = adapter._metadata_record(component, client.fetch_metadata())
    total_count = client.fetch_count()
    where = (
        f"DOCGUID='{adapter.PROBE_SURVEY_GUID}'"
        if component.key == "surveys"
        else f"SSL='{adapter.PROBE_SSL}'"
    )
    fetched = client.query(
        where=where,
        out_fields=adapter.OUT_FIELDS_BY_COMPONENT[component.key],
        parameters={
            "orderByFields": (
                "SALE_DATE DESC,OBJECTID ASC"
                if component.key == "sales"
                else "OBJECTID ASC"
            )
        },
        requested_limit=1,
        max_records=1,
        return_geometry=component.has_geometry,
    )
    if len(fetched.records) != 1:
        raise ValueError(f"{component.key} sentinel is missing or non-unique")
    sentinel = adapter._normalize_feature(
        component,
        fetched.records[0],
        response_schema_fingerprint=fetched.schema_fingerprint,
        geometry_crs=adapter.DEFAULT_OUTPUT_CRS,
    )
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=component.layer_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=str(metadata["schema_fingerprint"]),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=total_count,
        details={
            "stable_contract": stable_contract,
            "schema_contract": {
                "field_names": list(metadata["field_names"]),
                "geometry_type": metadata.get("geometry_type"),
                "max_record_count": metadata.get("max_record_count"),
                "advanced_query_capabilities": metadata.get(
                    "advanced_query_capabilities"
                ),
            },
            "rolling_observation": {
                "total_count": total_count,
                "sentinel": sentinel,
            },
            "requests_made": client.request_count,
        },
    )


def probe_dc_property_lineage(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe all four SSL-linked components while retaining their identities."""

    adapter = query_dc_property
    stable_contract = _dc_property_stable_contract(adapter.LINEAGE_ID)
    started = time.perf_counter()
    component_observations: dict[str, ProbeObservation] = {}
    for component in adapter.COMPONENTS.values():
        component_observations[component.key] = probe_dc_property_component(
            replace(context, source_id=component.source_id)
        )
    schema_contract = {
        key: observation.schema_sha256
        for key, observation in component_observations.items()
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.SERVICE_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=len(component_observations),
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": {
                key: observation.details.get("rolling_observation")
                for key, observation in component_observations.items()
            },
            "requests_made": sum(
                int(observation.details.get("requests_made") or 0)
                for observation in component_observations.values()
            ),
        },
    )


def _washington_case_permit_stable_contract(
    source_id: str,
) -> dict[str, Any]:
    adapter = query_oregon_washington_case_permits
    manifest = adapter.source_manifest()
    return {
        "source": adapter.SOURCES[source_id].to_dict(),
        "join_graph": [
            dict(edge)
            for edge in manifest["join_graph"]
            if source_id in {edge["from"], edge["to"]}
        ],
        "operation_triage": [dict(item) for item in manifest["operation_triage"]],
    }


def _washington_case_permit_probe_commands(
    source_id: str,
) -> list[tuple[str, list[str], bool]]:
    adapter = query_oregon_washington_case_permits
    commands = {
        adapter.CASEFILE_SOURCE_ID: [
            ("exact_casefile", ["case-detail", adapter.PROBE_CASEFILE], True),
            (
                "applications_under_review",
                ["case-review", "--limit", "1"],
                True,
            ),
            (
                "recent_decisions",
                ["case-decisions", "--limit", "1"],
                True,
            ),
            (
                "staff_vocabulary",
                ["case-staff", "--limit", "1"],
                True,
            ),
        ],
        adapter.TAXLOT_ACTIVITY_SOURCE_ID: [
            (
                "taxlot_project_activity",
                [
                    "taxlot-activity",
                    adapter.PROBE_TAXLOT,
                    "--collection",
                    "all",
                    "--limit",
                    "1",
                ],
                True,
            )
        ],
        adapter.BUILDING_SOURCE_ID: [
            (
                "building_taxlot",
                [
                    "building-search",
                    "taxlot",
                    adapter.PROBE_TAXLOT,
                    "--limit",
                    "1",
                ],
                True,
            ),
            (
                "building_types",
                ["building-types", "--limit", "1"],
                True,
            ),
        ],
        adapter.PERMIT_REPORT_SOURCE_ID: [
            (
                f"{kind}_report",
                ["permit-report", kind, identifier, "--limit", "1"],
                True,
            )
            for kind, identifier in (
                ("project", adapter.PROBE_PROJECT),
                ("activity", adapter.PROBE_ACTIVITY),
                ("people", adapter.PROBE_ACTIVITY),
                ("inspection", adapter.PROBE_PERMIT),
                ("review", adapter.PROBE_PERMIT),
            )
        ],
        adapter.ACCELA_SOURCE_ID: [
            (
                "record_and_attachments",
                ["accela-record", adapter.PROBE_CASEFILE],
                True,
            )
        ],
        adapter.DOCUMENT_ROUTE_SOURCE_ID: [
            (
                "document_routes",
                ["document-routes", adapter.PROBE_CASEFILE],
                False,
            )
        ],
    }
    try:
        return commands[source_id]
    except KeyError as error:
        raise ValueError(
            f"unknown Washington County case/permit component: {source_id}"
        ) from error


def probe_oregon_washington_case_permit_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one case/permit component and separate contract from current rows."""

    adapter = query_oregon_washington_case_permits
    started = time.perf_counter()
    stable_contract = _washington_case_permit_stable_contract(context.source_id)
    schema_contract: dict[str, Any] = {}
    operations: list[dict[str, Any]] = []
    statuses: list[str] = []
    result_count = 0

    for operation, command, uses_network in _washington_case_permit_probe_commands(
        context.source_id
    ):
        values = list(command)
        if uses_network:
            values.extend(
                [
                    "--timeout",
                    str(context.timeout),
                    "--minimum-interval",
                    str(_catalog_interval(context.catalog_decision)),
                    "--retry-attempts",
                    str(context.max_attempts),
                ]
            )
        args = adapter.build_parser().parse_args(values)
        result = adapter.execute(args, log_results=False)
        if not isinstance(result, PublicRecordsResult):
            raise ValueError("Washington County case/permit probe returned no envelope")
        records = [dict(record) for record in result.records]
        statuses.append(result.status.value)
        result_count += len(records)
        schema_contract[operation] = {
            "schema_fingerprints": sorted(
                {
                    str(record["schema_fingerprint"])
                    for record in records
                    if record.get("schema_fingerprint")
                }
            ),
            "record_kinds": sorted(
                {
                    str(record["record_kind"])
                    for record in records
                    if record.get("record_kind")
                }
            ),
            "record_fields": sorted({str(key) for record in records for key in record}),
        }
        operations.append(
            {
                "operation": operation,
                "status": result.status.value,
                "result_count": len(records),
                "native_sentinels": [
                    record.get("native_record_id") or record.get("canonical_ref")
                    for record in records[:3]
                ],
                "warnings": list(result.warnings),
                "errors": [
                    error.to_dict()
                    if hasattr(error, "to_dict")
                    else {"message": str(error)}
                    for error in result.errors
                ],
            }
        )

    successful = {
        ResultStatus.OK.value,
        ResultStatus.NO_RESULTS.value,
    }
    failures = [status for status in statuses if status not in successful]
    successes = [status for status in statuses if status in successful]
    if failures and successes or ResultStatus.PARTIAL.value in statuses:
        status = ResultStatus.PARTIAL.value
    elif failures:
        status = failures[0] if len(set(failures)) == 1 else ResultStatus.PARTIAL.value
    elif result_count:
        status = ResultStatus.OK.value
    else:
        status = ResultStatus.NO_RESULTS.value

    error_messages = [
        str(error.get("message") or "")
        for operation in operations
        for error in operation["errors"]
        if error.get("message")
    ]
    return ProbeObservation(
        status=status,
        endpoint=adapter.SOURCES[context.source_id].base_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=result_count,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": {"operations": operations},
        },
        error=(
            "; ".join(error_messages)
            if status
            not in {
                ResultStatus.OK.value,
                ResultStatus.NO_RESULTS.value,
                ResultStatus.PARTIAL.value,
            }
            and error_messages
            else None
        ),
    )


def _multnomah_sail_stable_contract(source_id: str) -> dict[str, Any]:
    adapter = query_oregon_multnomah_sail
    component = adapter.COMPONENTS[source_id]
    source = adapter.SOURCE_METADATA[source_id].to_dict()
    layer_contract = component.manifest.contract_record()
    layer_contract.pop("observed_count", None)
    return {
        "source_id": source_id,
        "county_geoid": adapter.COUNTY_GEOID,
        "base_url": source.get("base_url"),
        "dataset_id": source.get("dataset_id"),
        "source_role": source.get("source_role"),
        "experience": {
            "item_id": adapter.EXPERIENCE_ID,
            "url": adapter.EXPERIENCE_URL,
            "configuration_url": adapter.EXPERIENCE_DATA_URL,
        },
        "layer_contract": layer_contract,
        "record_kind": component.record_kind,
        "search_fields": {
            key: list(fields) for key, fields in component.search_fields.items()
        },
        "image_viewer_template": (
            adapter.IMAGE_VIEWER_TEMPLATE if component.image_capable else None
        ),
        "official_complements": [
            {
                key: value
                for key, value in complement.items()
                if key in {"source_id", "name", "url", "relationship", "join_fields"}
            }
            for complement in adapter.COMPLEMENTARY_SOURCES
        ],
    }


def probe_oregon_multnomah_sail_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one SAIL layer and keep rolling counts outside contract hashes."""

    adapter = query_oregon_multnomah_sail
    started = time.perf_counter()
    command = [
        "probe",
        "--source",
        context.source_id,
        "--timeout",
        str(context.timeout),
        "--minimum-interval",
        str(_catalog_interval(context.catalog_decision)),
        "--retry-attempts",
        str(context.max_attempts),
    ]
    if context.source_id != adapter.SURVEY_SOURCE_ID:
        command.append("--no-resolve-image")
    args = adapter.build_parser().parse_args(command)
    result = adapter.execute(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    if not isinstance(result, PublicRecordsResult):
        raise ValueError("Multnomah SAIL component probe returned no envelope")
    component = adapter.COMPONENTS[context.source_id]
    observation = _adapter_result_observation(
        result,
        endpoint=component.layer_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError("Multnomah SAIL component probe returned another source")

    stable_contract = _multnomah_sail_stable_contract(context.source_id)
    schema_contract = {
        key: record.get(key)
        for key in (
            "schema_fingerprint",
            "layer_name",
            "layer_id",
            "service_item_id",
            "geometry_type",
            "native_crs",
            "max_record_count",
            "ordering",
            "complete_sort_tuple",
        )
    }
    rolling_observation = {
        "component_total_count": record.get("component_total_count"),
        "observed_count_reference": record.get("observed_count_reference"),
        "sentinel": _json_ready(record.get("sentinel") or {}),
        "image_resolution": _json_ready(record.get("image_resolution") or {}),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_oregon_lincoln_propertyweb(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe PropertyWeb while separating its contract from account state."""

    started = time.perf_counter()
    args = query_oregon_lincoln_propertyweb.build_parser().parse_args(
        [
            "probe",
            "--timeout",
            str(context.timeout),
            "--minimum-interval",
            str(_catalog_interval(context.catalog_decision)),
            "--retry-attempts",
            str(context.max_attempts),
        ]
    )
    result = query_oregon_lincoln_propertyweb.execute(
        args,
        log_results=False,
    )
    if not isinstance(result, PublicRecordsResult):
        raise ValueError("Lincoln PropertyWeb probe did not return a result envelope")
    observation = _adapter_result_observation(
        result,
        endpoint=query_oregon_lincoln_propertyweb.HOME_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != query_oregon_lincoln_propertyweb.SOURCE_ID
    ):
        raise ValueError("Lincoln PropertyWeb probe returned another source")

    home = dict(record.get("home") or {})
    search = dict(record.get("search") or {})
    detail = dict(record.get("detail") or {})
    stable_contract = {
        "source_id": query_oregon_lincoln_propertyweb.SOURCE_ID,
        "county_geoid": query_oregon_lincoln_propertyweb.COUNTY_GEOID,
        "platform_family": "tyler_propertyweb_dnn",
        "home_url": query_oregon_lincoln_propertyweb.HOME_URL,
        "search_url": query_oregon_lincoln_propertyweb.SEARCH_URL,
        "detail_route": query_oregon_lincoln_propertyweb.DETAIL_ROUTE,
        "document_generators": dict(
            query_oregon_lincoln_propertyweb.DOCUMENT_GENERATORS
        ),
        "complement_source_ids": [
            query_oregon_lincoln_propertyweb.TAXLOT_WFS_SOURCE_ID,
            query_oregon_lincoln_propertyweb.RECORDER_SOURCE_ID,
        ],
    }
    rolling_observation = {
        "tax_year": home.get("tax_year"),
        "search_record_count": search.get("record_count"),
        "search_snapshot_fingerprint": search.get("snapshot_fingerprint"),
        "detail_identity": {
            key: detail.get(key)
            for key in (
                "property_quick_ref",
                "party_quick_ref",
                "property_id",
                "property_owner_id",
                "party_id",
                "map_number",
            )
        },
        "document": _json_ready(record.get("document")),
    }
    schema_contract = {
        "home": home.get("schema_fingerprint"),
        "search": search.get("schema_fingerprint"),
        "detail": detail.get("response_schema_fingerprint"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
            "schema_contract": schema_contract,
        },
    )


def probe_oregon_lincoln_taxlots(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the county WFS with stable protocol and rolling count separation."""

    started = time.perf_counter()
    args = query_oregon_lincoln_taxlots.QueryOptions(
        command="probe",
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
    )
    result = query_oregon_lincoln_taxlots.execute(
        args,
        log_results=False,
    )
    if not isinstance(result, PublicRecordsResult):
        raise ValueError("Lincoln taxlot WFS probe did not return a result envelope")
    observation = _adapter_result_observation(
        result,
        endpoint=query_oregon_lincoln_taxlots.MAPSERVER_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != query_oregon_lincoln_taxlots.SOURCE_ID
    ):
        raise ValueError("Lincoln taxlot WFS probe returned another source")

    representative = dict(record.get("representative_row") or {})
    native_identity = dict(representative.get("native_identity") or {})
    schema_baseline = dict(record.get("schema_baseline") or {})
    stable_contract = {
        "source_id": query_oregon_lincoln_taxlots.SOURCE_ID,
        "service_identity": _json_ready(record.get("service_identity") or {}),
        "jurisdiction_evidence": _json_ready(record.get("jurisdiction_evidence") or {}),
        "protocol_contract": _json_ready(record.get("protocol_contract") or {}),
        "crs_lineage": _json_ready(record.get("crs_lineage") or {}),
        "declared_schema": _json_ready(record.get("declared_schema") or {}),
        "complement_source_ids": [
            item.get("source_id")
            for item in record.get("complementary_sources") or []
            if isinstance(item, Mapping) and item.get("source_id")
        ],
    }
    rolling_observation = {
        "count_baseline": _json_ready(record.get("count_baseline") or {}),
        "sentinel_count": record.get("sentinel_count"),
        "representative_identity": {
            key: native_identity.get(key)
            for key in ("propertyid", "parcelid", "ogc_fid", "imagekey")
        },
    }
    return replace(
        observation,
        schema_sha256=str(
            schema_baseline.get("observed_fingerprint")
            or observation.schema_sha256
            or sha256_fingerprint(stable_contract["declared_schema"])
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=record.get("sentinel_count"),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_oregon_jackson_property_event_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Jackson event layer without hashing the rolling event window."""

    config = OREGON_JACKSON_PROPERTY_EVENT_SOURCES[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        source=context.source_id,
        all_sources=False,
        page_size=2,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    result = execute_oregon_jackson_property_events(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=config.layer_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Jackson property-event probe returned another source or record kind"
        )
    stable_contract = {
        "source_id": context.source_id,
        "layer_url": config.layer_url,
        "layer_id": config.layer_id,
        "service_item_id": config.service_item_id,
        "expected_layer_name": config.expected_layer_name,
        "record_kind": config.record_kind,
        "native_id_field": config.native_id_field,
        "required_fields": list(config.required_fields),
        "search_fields": sorted(config.search_fields),
        "source_time_zone": config.source_time_zone,
        "source_time_respects_daylight_saving": (
            config.source_time_respects_daylight_saving
        ),
        "complementary_sources": _json_ready(record.get("complementary_sources") or []),
    }
    rolling_observation = {
        "component_total_count": record.get("component_total_count"),
        "first_ordered_observation": _json_ready(
            record.get("first_ordered_observation") or {}
        ),
        "last_ordered_observation": _json_ready(
            record.get("last_ordered_observation") or {}
        ),
        "source_time_reference": _json_ready(record.get("source_time_reference") or {}),
    }
    return replace(
        observation,
        schema_sha256=str(
            record.get("schema_fingerprint") or observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=record.get("component_total_count"),
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_oregon_jackson_accela_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one verified Accela detail module and its attachment listing."""

    source = next(
        source
        for source in OREGON_JACKSON_ACCELA_SOURCES.values()
        if source.source_id == context.source_id
    )
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        module=source.key,
        all_sources=False,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        output=None,
        json_out=False,
    )
    packet = execute_oregon_jackson_accela(args, log_results=False)
    components = packet.get("components") if isinstance(packet, Mapping) else None
    if not isinstance(components, list) or len(components) != 1:
        raise ValueError("Jackson Accela probe did not return one component")
    component = components[0]
    if not isinstance(component, Mapping):
        raise ValueError("Jackson Accela probe component is not an object")
    records = component.get("records")
    if not isinstance(records, list):
        raise ValueError("Jackson Accela probe component lacks records")
    record = records[0] if records else None
    if record is not None and (
        not isinstance(record, Mapping)
        or record.get("source_id") != context.source_id
        or record.get("record_kind") != "source_probe"
    ):
        raise ValueError("Jackson Accela probe returned another source or record kind")

    stable_contract = {
        "source_id": context.source_id,
        "module": source.module,
        "record_kind": source.record_kind,
        "arcgis_complement": {
            "source_id": source.arcgis_source_id,
            "url": source.arcgis_url,
        },
    }
    rolling_observation = (
        {
            "native_record_id": record.get("native_record_id"),
            "record_status": record.get("record_status"),
            "document_count": record.get("document_count"),
            "record_detail_representation": _json_ready(
                record.get("record_detail_representation") or {}
            ),
            "attachment_list_representation": _json_ready(
                record.get("attachment_list_representation") or {}
            ),
        }
        if isinstance(record, Mapping)
        else {}
    )
    status = str(component.get("status") or packet.get("status") or "unavailable")
    errors = component.get("errors")
    return ProbeObservation(
        status=status,
        endpoint=source.source_metadata().base_url or source.arcgis_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=(
            str(record.get("schema_fingerprint"))
            if isinstance(record, Mapping) and record.get("schema_fingerprint")
            else None
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=len(records),
        details={
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
            "warnings": _json_ready(component.get("warnings") or []),
            "errors": _json_ready(errors or []),
        },
        error=(
            "; ".join(
                str(value.get("message") or "")
                for value in (errors or [])
                if isinstance(value, Mapping)
            ).strip("; ")
            or None
        ),
    )


def probe_eugene_municipal_court_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one Tyler tenant with stable contract and rolling access separated."""

    tenant = OREGON_TYLER_MUNICIPAL_TENANTS_BY_SOURCE[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        tenant=tenant.key,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        retry_backoff=0.25,
        output=None,
        json_out=False,
    )
    result = execute_eugene_municipal_court(args)
    observation = _adapter_result_observation(
        result,
        endpoint=tenant.base_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Tyler municipal-court probe returned another source or record kind"
        )
    stable_contract = {
        "source_id": context.source_id,
        "court": _json_ready(record.get("court") or {}),
        "platform_family": record.get("platform_family"),
        "tenant_key": record.get("tenant_key"),
        "tenant_slug": record.get("tenant_slug"),
        "case_search_url": record.get("case_search_url"),
        "case_search_method": record.get("case_search_method"),
        "available_search_options": _json_ready(
            record.get("available_search_options") or []
        ),
        "dockets_url": record.get("dockets_url"),
        "configured_direct_verification": _json_ready(
            record.get("configured_direct_verification") or {}
        ),
        "official_referrer_chain": _json_ready(
            record.get("official_referrer_chain") or []
        ),
        "request_complement": _json_ready(record.get("request_complement") or {}),
    }
    rolling_observation = {
        "upcoming_docket_count": record.get("upcoming_docket_count"),
        "component_access": _json_ready(record.get("component_access") or {}),
        "case_form_snapshot": _json_ready(record.get("case_form_snapshot") or {}),
        "docket_snapshot": _json_ready(record.get("docket_snapshot") or {}),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(record.get("schema_fingerprints") or {}),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_oregon_court_directory_component(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe one official Oregon directory list and default view."""

    source = OREGON_COURT_DIRECTORY_SOURCES[context.source_id]
    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        source=source.source_id,
        view=None,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        retry_backoff=0.25,
        output=None,
        json_out=False,
    )
    result = execute_oregon_court_directories(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=source.page_url,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon court-directory probe returned another source or record kind"
        )

    checks = dict(record.get("checks") or {})
    list_contract = dict(record.get("list") or {})
    view_contract = dict(record.get("view") or {})
    live_views = [
        {
            "view_id": value.get("view_id"),
            "display_name": value.get("display_name"),
            "url": value.get("url"),
        }
        for value in record.get("live_views") or []
        if isinstance(value, Mapping)
    ]
    stable_artifact = {
        "source_id": source.source_id,
        "list_name": source.list_name,
        "list_id": list_contract.get("source_list_id"),
        "list_title": list_contract.get("source_title"),
        "default_view_id": view_contract.get("view_id"),
        "default_view_name": view_contract.get("live_display_name"),
        "live_views": live_views,
        "anonymous_page_bootstrap": checks.get("anonymous_page_bootstrap"),
        "cookie_bound_soap_request": checks.get("cookie_bound_soap_request"),
        "soap_action_header_required": checks.get("soap_action_header_required"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(
            {
                "list": list_contract.get("schema_fingerprint"),
                "view": view_contract.get("schema_fingerprint"),
                "rowset": record.get("rowset_schema_fingerprint"),
            }
        ),
        artifact_sha256=sha256_fingerprint(stable_artifact),
        result_count=checks.get("parsed_item_count"),
        details={
            **dict(observation.details),
            **stable_artifact,
            "reported_item_count": checks.get("reported_item_count"),
            "parsed_item_count": checks.get("parsed_item_count"),
            "complete_response": checks.get("complete_response"),
            "live_view_count": checks.get("live_view_count"),
            "configured_view_count": checks.get("configured_view_count"),
            "unconfigured_live_view_count": checks.get("unconfigured_live_view_count"),
            "list_reported_item_count": list_contract.get("source_reported_item_count"),
            "declared_field_count": list_contract.get("declared_field_count"),
        },
    )


def probe_oregon_court_calendar(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the Oregon calendar handshake, directories, and bounded result."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        location="Deschutes",
        timeout=context.timeout,
        output=None,
        json_out=False,
    )
    result = execute_oregon_court_calendar(
        args,
        access_decision=context.catalog_decision,
        log_results=False,
    )
    observation = _adapter_result_observation(
        result,
        endpoint=OREGON_COURT_CALENDAR_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon court-calendar probe returned another source or record kind"
        )
    checks = dict(record.get("checks") or {})
    schema_fingerprints = dict(record.get("schema_fingerprints") or {})
    stable_artifact = {
        "location": (record.get("location") or {}).get("name"),
        "documented_result_ceiling": checks.get("documented_result_ceiling"),
        "maximum_forward_date_window_days": checks.get(
            "maximum_forward_date_window_days"
        ),
        "forward_only": checks.get("forward_only"),
    }
    live_observation = {
        "location_directory_count": checks.get("location_directory_count"),
        "judicial_officer_count": checks.get("judicial_officer_count"),
        "reported_result_count": checks.get("reported_result_count"),
        "parsed_result_count": checks.get("parsed_result_count"),
        "live_observed_returned_rows": checks.get("live_observed_returned_rows"),
        "native_truncation_detected": checks.get("native_truncation_detected"),
        "source_alerts": checks.get("source_alerts"),
    }
    return replace(
        observation,
        schema_sha256=sha256_fingerprint(schema_fingerprints),
        artifact_sha256=sha256_fingerprint(stable_artifact),
        result_count=checks.get("parsed_result_count"),
        details={
            **dict(observation.details),
            **stable_artifact,
            **live_observation,
        },
    )


def probe_oregon_smart_search(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the rendered Smart Search form without hashing roster churn."""

    started = time.perf_counter()
    args = argparse.Namespace(
        command="probe",
        input=None,
        browser_timeout=context.timeout,
        output=None,
        json_out=False,
    )
    result = execute_oregon_smart_search(args)
    observation = _adapter_result_observation(
        result,
        endpoint=OREGON_SMART_SEARCH_URL,
        started=started,
    )
    if not result.records:
        return observation
    record = result.records[0]
    if (
        record.get("record_kind") != "court_search_source_probe"
        or record.get("source_id") != context.source_id
    ):
        raise ValueError(
            "Oregon Smart Search probe returned another source or record kind"
        )

    form = dict(record.get("form") or {})
    captcha = dict(record.get("captcha") or {})
    option_sets = {
        str(name): dict(option_set)
        for name, option_set in dict(record.get("option_sets") or {}).items()
        if isinstance(option_set, Mapping)
    }
    stable_option_sets = {
        name: {
            "count": option_set.get("count"),
            "first": _json_ready(option_set.get("first") or []),
            "last": _json_ready(option_set.get("last") or []),
            "values_fingerprint": option_set.get("values_fingerprint"),
        }
        for name, option_set in sorted(option_sets.items())
        if name not in OREGON_SMART_SEARCH_ROLLING_OPTION_FIELDS
    }
    stable_contract = {
        "source_id": OREGON_SMART_SEARCH_SOURCE_ID,
        "source_url": OREGON_SMART_SEARCH_URL,
        "form": {
            "action": form.get("action") or OREGON_SMART_SEARCH_FORM_ACTION_URL,
            "method": form.get("method"),
            "stable_controls": _json_ready(form.get("stable_controls") or []),
        },
        "settings": _json_ready(record.get("settings") or {}),
        "captcha": {
            key: captcha.get(key)
            for key in ("enabled", "disabled_for_authenticated", "provider")
        },
        "option_sets": stable_option_sets,
    }
    rolling_observations = dict(record.get("rolling_observations") or {})
    rolling_observation = {
        "final_url": record.get("final_url"),
        "http_status": record.get("http_status"),
        "title": record.get("title"),
        "rendered_named_control_count": form.get("rendered_named_control_count"),
        "captcha_frame_count": captcha.get("frame_count"),
        "officer_option_counts": _json_ready(
            rolling_observations.get("option_counts") or {}
        ),
        "runtime": _json_ready(record.get("runtime") or {}),
    }
    return replace(
        observation,
        http_status=record.get("http_status"),
        schema_sha256=str(
            record.get("schema_fingerprint") or observation.schema_sha256
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            **dict(observation.details),
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_oregon_ojcin_public_directory(
    context: ProbeContext,
) -> ProbeObservation:
    """Probe the OJCIN public product directory and its official routes."""

    started = time.perf_counter()
    client = OregonOJCINEndpointClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_retries=max(0, context.max_attempts - 1),
    )
    try:
        packet = run_oregon_ojcin_endpoint_probe(client)
    finally:
        close = getattr(client.session, "close", None)
        if callable(close):
            close()

    if packet.get("adapter_source_id") != context.source_id:
        raise ValueError("OJCIN public-directory probe returned another source")
    raw_probes = packet.get("probes")
    if not isinstance(raw_probes, list) or any(
        not isinstance(probe, Mapping) for probe in raw_probes
    ):
        raise ValueError("OJCIN public-directory probe lacks endpoint observations")

    product_contracts = [
        {
            "source_id": product.source_id,
            "name": product.name,
            "source_role": product.source_role,
            "system": product.system,
            "acquisition_mode": product.acquisition_mode,
            "acquisition_url": product.acquisition_url,
            "contents": list(product.contents),
            "delivery_schema_status": product.delivery_schema_status,
        }
        for product in (
            OREGON_OJCIN_PRODUCTS[source_id]
            for source_id in sorted(OREGON_OJCIN_PRODUCTS)
        )
    ]
    endpoint_contracts = [
        {
            "endpoint_id": endpoint.endpoint_id,
            "url": endpoint.url,
            "role": endpoint.role,
            "source_ids": list(endpoint.source_ids),
            "media_kind": endpoint.media_kind,
            "marker": endpoint.marker,
        }
        for endpoint in OREGON_OJCIN_ENDPOINTS
    ]
    stable_contract = {
        "source_id": OREGON_OJCIN_SOURCE_ID,
        "schema_fingerprint": OREGON_OJCIN_SCHEMA_FINGERPRINT,
        "product_contracts": product_contracts,
        "endpoint_contracts": endpoint_contracts,
    }
    rolling_observation = {
        "probe_status": packet.get("status"),
        "endpoint_count": packet.get("endpoint_count"),
        "ok_count": packet.get("ok_count"),
        "endpoints": [
            {
                key: probe.get(key)
                for key in (
                    "endpoint_id",
                    "final_url",
                    "status",
                    "http_status",
                    "content_type",
                    "content_length",
                    "etag",
                    "last_modified",
                    "representation_ok",
                    "error",
                )
            }
            for probe in raw_probes
        ],
    }
    packet_status = packet.get("status")
    if packet_status == "ok":
        status = ResultStatus.OK.value
    elif packet_status == "partial":
        status = ResultStatus.PARTIAL.value
    else:
        raise ValueError(f"unsupported OJCIN probe status: {packet_status}")
    return ProbeObservation(
        status=status,
        endpoint=OREGON_OJCIN_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=str(
            packet.get("adapter_schema_fingerprint") or OREGON_OJCIN_SCHEMA_FINGERPRINT
        ),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=packet.get("ok_count"),
        details={
            "stable_contract": stable_contract,
            "rolling_observation": rolling_observation,
        },
    )


def probe_nyc_pip(
    context: ProbeContext,
    *,
    clients: Mapping[str, Any] | None = None,
) -> ProbeObservation:
    """Validate five PIP layer contracts and one exact BBL in ten requests."""

    adapter = query_nyc_pip
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("NYC PIP monitor source ID changed")
    expected_requests = len(adapter.BUNDLE_LAYER_KEYS) * 2
    started = time.perf_counter()
    component_records: dict[str, list[dict[str, Any]]] = {}
    validated_layers: dict[str, dict[str, Any]] = {}
    request_counts: dict[str, int] = {}

    for component in adapter.BUNDLE_LAYER_KEYS:
        spec = adapter.LAYER_SPECS[component]
        client = (
            clients[component]
            if clients is not None and component in clients
            else adapter.PIPArcGISClient(
                spec,
                page_size=adapter.DEFAULT_PAGE_SIZE,
                timeout=context.timeout,
                minimum_interval=_catalog_interval(context.catalog_decision),
                retry_policy=RetryPolicy(max_attempts=1),
            )
        )
        start_count = int(getattr(client, "request_count", 0))
        validated = adapter.validate_layer_metadata(client.metadata(), spec)
        native_page_size = int(validated["native_page_size"])
        if hasattr(client, "page_size"):
            client.page_size = native_page_size
        fetched = client.query(
            where=adapter._exact_bbl_where(spec, adapter.PROBE_BBL),
            out_fields="*",
            parameters={
                "orderByFields": spec.order_by,
                **({"outSR": 4326} if component == "tax_lot" else {}),
            },
            requested_limit=native_page_size,
            max_records=native_page_size,
            cursor=None,
            return_geometry=component == "tax_lot",
        )
        observed_requests = int(
            getattr(client, "request_count", start_count + 2)
        ) - start_count
        if observed_requests != 2 or fetched.requests_made != 1:
            raise ValueError(
                f"NYC PIP {component} monitor request contract changed"
            )
        if fetched.next_cursor is not None or fetched.truncated_by_cap:
            raise ValueError(
                f"NYC PIP {component} exact sentinel exceeds one native page"
            )
        records = [
            adapter.normalize_feature(
                feature,
                spec,
                response_schema_fingerprint=fetched.schema_fingerprint,
                layer_schema_fingerprint=validated["schema_fingerprint"],
            )
            for feature in fetched.records
        ]
        if component == "exemptions":
            adapter._annotate_exemption_duplicate_ordinals(
                records,
                complete_exact_bbl_result=True,
            )
        component_records[component] = records
        validated_layers[component] = validated
        request_counts[component] = observed_requests

    adapter._verify_probe(component_records)
    requests_made = sum(request_counts.values())
    if requests_made != expected_requests:
        raise ValueError("NYC PIP monitor did not honor its ten-request contract")

    routes_contract = adapter.source_routes()
    layer_contract = {
        component: {
            "url": spec.url,
            "layer_id": spec.layer_id,
            "name": spec.expected_name,
            "type": spec.expected_type,
            "identity_field": spec.identity_field,
            "occurrence_field": "OBJECTID",
            "record_kind": spec.record_kind,
        }
        for component, spec in adapter.LAYER_SPECS.items()
    }
    identity_contract = {
        "source_id": adapter.SOURCE_ID,
        "dataset_id": adapter.SOURCE_METADATA.dataset_id,
        "sentinel": {
            "bbl": adapter.PROBE_BBL,
            "house_number": adapter.PROBE_HOUSE_NUMBER,
            "street": adapter.PROBE_STREET,
            "county_geoid": adapter.bbl_parts(adapter.PROBE_BBL)["county_geoid"],
        },
        "parcel_identity": "ten_digit_bbl",
        "layer_occurrence_identity": "component_plus_bbl_plus_OBJECTID",
        "assessment_identity": "PARID_plus_TAXYR_plus_PERIOD",
        "assessment_representations": [
            "current_assessment",
            "assessment_history",
        ],
        "exemption_identity": (
            "PARID_plus_PARID_ORG_plus_TAXYR_plus_F_EXCODE_plus_"
            "F_EXEMPT_TYPE_plus_SORT_ORDER; OBJECTID retained per occurrence"
        ),
        "recording_lineage": {
            "pip_acris_display": "same_acris_record_representation",
            "four_borough_full_instruments": "us-nyc-acris",
            "richmond_full_instruments": (
                "us-ny-richmond-county-clerk-land-documents"
            ),
        },
    }
    paging_contract = {
        component: {
            "native_page_size": validated_layers[component]["native_page_size"],
            "order_by": adapter.LAYER_SPECS[component].order_by,
            "supports_pagination": True,
            "supports_order_by": True,
            "omitted_caller_window": "exhaust_source_reported_pages",
            "monitor_window": "one_source_native_page",
        }
        for component in adapter.BUNDLE_LAYER_KEYS
    }
    stable_contract_hashes = {
        "routes_sha256": sha256_fingerprint(routes_contract),
        "layers_sha256": sha256_fingerprint(layer_contract),
        "identity_sha256": sha256_fingerprint(identity_contract),
        "paging_sha256": sha256_fingerprint(paging_contract),
    }
    schema_contract = {
        component: validated_layers[component]["schema"]
        for component in adapter.BUNDLE_LAYER_KEYS
    }

    detail_records = component_records["detail"]
    assessment_records = [
        *component_records["current_assessment"],
        *component_records["assessment_history"],
    ]
    exemption_records = component_records["exemptions"]
    rolling_observation = {
        "owners": sorted(
            {
                str(owner.get("raw_name"))
                for record in detail_records
                for owner in record.get("owners", ())
                if isinstance(owner, Mapping) and owner.get("raw_name")
            }
        ),
        "values": [
            {
                "component": (record.get("assessment") or {}).get(
                    "representation"
                ),
                "values": _json_ready(
                    (record.get("assessment") or {}).get("values") or {}
                ),
            }
            for record in assessment_records
        ]
        + [
            {
                "component": "exemptions",
                "values": {
                    key: (record.get("exemption") or {}).get(key)
                    for key in (
                        "taxable_assessed_value",
                        "exempt_assessed_value",
                        "taxable_bill_assessed_value",
                    )
                },
            }
            for record in exemption_records
        ],
        "years": sorted(
            {
                str(year)
                for record in [*assessment_records, *exemption_records]
                for year in [
                    (
                        record.get("assessment")
                        or record.get("exemption")
                        or {}
                    ).get("tax_year")
                ]
                if year is not None
            }
        ),
        "counts": {
            component: len(component_records[component])
            for component in adapter.BUNDLE_LAYER_KEYS
        },
        "object_ids": {
            component: [
                record.get("native_feature_id")
                for record in component_records[component]
            ]
            for component in adapter.BUNDLE_LAYER_KEYS
        },
    }
    rolling_hashes = {
        "owners_sha256": sha256_fingerprint(rolling_observation["owners"]),
        "values_sha256": sha256_fingerprint(rolling_observation["values"]),
        "years_sha256": sha256_fingerprint(rolling_observation["years"]),
        "counts_sha256": sha256_fingerprint(rolling_observation["counts"]),
        "object_ids_sha256": sha256_fingerprint(
            rolling_observation["object_ids"]
        ),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.PIP_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract_hashes),
        result_count=sum(rolling_observation["counts"].values()),
        details={
            "stable_contract_hashes": stable_contract_hashes,
            "routes_contract": _json_ready(routes_contract),
            "layer_contract": layer_contract,
            "identity_contract": identity_contract,
            "paging_contract": paging_contract,
            "schema_contract": schema_contract,
            "rolling_hashes": rolling_hashes,
            "rolling_observation": rolling_observation,
            "requests_made": requests_made,
            "request_counts": request_counts,
        },
    )


def probe_santa_fe_clerktrack(
    context: ProbeContext,
) -> ProbeObservation:
    """Verify one exact ClerkTrack index/detail pair without fetching an image."""

    adapter = query_santa_fe_clerktrack
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Santa Fe ClerkTrack monitor source ID changed")
    expected_requests = 5
    started = time.perf_counter()
    client = adapter.ClerkTrackClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_attempts=context.max_attempts,
        request_budget=expected_requests,
    )
    try:
        listing, detail, search_form = client.detail(
            adapter.PROBE_INSTRUMENT
        )
        request_count = client.request_count
        results_schema_fingerprint = (
            client.last_results_schema_fingerprint
        )
    finally:
        client.close()
    if request_count != expected_requests:
        raise ValueError(
            "Santa Fe ClerkTrack sentinel did not honor its five-request contract"
        )

    listing_identity = {
        "instrument_number": listing.instrument_number,
        "book": listing.book,
        "page": listing.page,
        "recording_date": listing.recording_date,
        "document_type": listing.document_type,
    }
    detail_identity = {
        "instrument_number": detail.instrument_number,
        "book": detail.book,
        "page": detail.page,
        "recording_date": detail.recording_date,
        "document_type": detail.document_type,
    }
    if listing_identity != detail_identity:
        raise ValueError(
            "Santa Fe ClerkTrack sentinel list/detail identities disagree"
        )
    expected_identity = {
        "instrument_number": adapter.PROBE_INSTRUMENT,
        "book": adapter.PROBE_BOOK,
        "page": adapter.PROBE_PAGE,
        "recording_date": adapter.PROBE_RECORDING_DATE,
        "document_type": adapter.PROBE_DOCUMENT_TYPE,
    }
    if detail_identity != expected_identity:
        raise ValueError(
            "Santa Fe ClerkTrack exact sentinel identity changed"
        )

    routes = [_json_ready(route) for route in adapter.SOURCE_ROUTES]
    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "jurisdiction_geoid": adapter.COUNTY_GEOID,
        "dataset_id": adapter.SOURCE_METADATA.dataset_id,
        "routes": routes,
        "forms": {
            "login": {
                "url": adapter.LOGIN_URL,
                "guest_identity": adapter.PUBLIC_INDEX_USERNAME,
                "required_state_fields": sorted(
                    adapter.REQUIRED_WEBFORMS_FIELDS
                ),
                "required_controls": [
                    "txtUser",
                    "txtPwd",
                    "btnLogin",
                ],
            },
            "search": {
                "url": adapter.SEARCH_URL,
                "required_state_fields": sorted(
                    adapter.REQUIRED_WEBFORMS_FIELDS
                ),
                "required_controls": sorted(
                    adapter.SEARCH_CONTROL_NAMES
                ),
                "schema_fingerprint": (
                    search_form.schema_fingerprint
                ),
            },
            "results": {
                "url": adapter.RESULTS_URL,
                "headers": list(adapter.RESULT_HEADERS),
                "schema_fingerprint": (
                    results_schema_fingerprint
                ),
            },
            "detail": {
                "url": adapter.DETAIL_URL,
                "field_labels": list(adapter.DETAIL_FIELD_LABELS),
                "schema_fingerprint": detail.schema_fingerprint,
            },
        },
        "identity": {
            "primary_stable_key": "instrument_number",
            "sentinel": expected_identity,
            "opaque_detail_selector_persisted": False,
        },
        "paging": {
            "mechanism": "WebForms native page selector",
            "native_page_size": adapter.NATIVE_PAGE_SIZE_OBSERVED,
            "order_by": adapter.EXPECTED_SORT_EXPRESSION,
            "omitted_caller_window": "exhaust_source_reported_pages",
            "continuation_prefix": adapter.CURSOR_PREFIX,
            "continuation_snapshot_fields": [
                "total_records",
                "page_count",
                "first_page_identity_fingerprint",
                "index_through_date",
                "results_schema_fingerprint",
            ],
        },
        "reacquisition": {
            "steps": [
                "new_index_guest_session",
                "exact_instrument_search",
                "require_one_exact_listing",
                "use_current_session_selector",
                "verify_visible_list_detail_identity",
            ],
            "verified_fields": sorted(expected_identity),
            "persisted_selector": False,
        },
        "lineage": {
            "same_clerk_non_independent": [
                "us-nm-santa-fe-clerktrack-detail",
                "us-nm-santa-fe-clerktrack-public-images",
                "us-nm-santa-fe-clerktrack-index-books",
                "us-nm-santa-fe-clerk-copy-request",
            ],
            "independent_assessor_field_match": (
                adapter.ASSESSOR_LAYER_SOURCE_ID
            ),
            "distinct_treasurer_tax_record": (
                adapter.TREASURER_ROUTE_ID
            ),
        },
        "monitor": {
            "request_budget": expected_requests,
            "image_fetched": False,
            "copy_purchased": False,
        },
    }
    schema_contract = {
        "search_form_schema_fingerprint": (
            search_form.schema_fingerprint
        ),
        "document_types_fingerprint": (
            search_form.document_types_fingerprint
        ),
        "results_schema_fingerprint": (
            results_schema_fingerprint
        ),
        "detail_schema_fingerprint": detail.schema_fingerprint,
        "result_headers": list(adapter.RESULT_HEADERS),
        "detail_fields": list(adapter.DETAIL_FIELD_LABELS),
    }
    rolling_observation = {
        "index_through_date": search_form.index_through_date,
        "document_type_count": len(search_form.document_types),
        "grantor_count": len(detail.grantors),
        "grantee_count": len(detail.grantees),
        "legal_information_count": len(detail.legal_information),
        "description_count": len(detail.descriptions),
        "submitter": detail.submitter,
        "address": detail.address,
        "location": detail.location,
        "requests_made": request_count,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.LOGIN_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": expected_identity,
            "rolling_observation": rolling_observation,
            "list_detail_agreement": True,
        },
    )


def probe_santa_fe_property(context: ProbeContext) -> ProbeObservation:
    """Validate ArcGIS metadata and one exact county-owned parcel."""

    adapter = query_santa_fe_property
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("Santa Fe Assessor monitor source ID changed")
    expected_requests = 2
    started = time.perf_counter()
    client = adapter.SantaFeArcGISClient(
        adapter.LAYER_URL,
        page_size=1,
        max_records=1,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    metadata = adapter.validate_layer_metadata(client.metadata())
    fetched = client.query(
        where=f"UPC='{adapter.PROBE_UPC}'",
        out_fields="*",
        parameters={"orderByFields": "OBJECTID"},
        requested_limit=1,
        max_records=1,
        return_geometry=False,
    )
    request_count = client.request_count
    if request_count != expected_requests:
        raise ValueError(
            "Santa Fe Assessor sentinel did not honor its two-request contract"
        )
    if len(fetched.records) != 1:
        raise ValueError(
            "Santa Fe Assessor exact sentinel no longer returns one feature"
        )
    record = adapter.normalize_feature(
        fetched.records[0],
        response_schema_fingerprint=fetched.schema_fingerprint,
        layer_schema_fingerprint=metadata["schema_fingerprint"],
    )
    if (
        record.get("source_id") != adapter.SOURCE_ID
        or record.get("upc") != adapter.PROBE_UPC
        or record.get("parcel_number") != adapter.PROBE_PARCEL_NUMBER
        or record.get("identity", {}).get("durable_parcel_identity")
        is not True
    ):
        raise ValueError(
            "Santa Fe Assessor county-owned sentinel identity changed"
        )

    stable_routes = [
        {
            key: _json_ready(value)
            for key, value in route.items()
            if key not in {"observed_count", "observed_count_note"}
        }
        for route in adapter.SOURCE_ROUTES
    ]
    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "jurisdiction_geoid": adapter.COUNTY_GEOID,
        "dataset_id": adapter.SOURCE_METADATA.dataset_id,
        "routes": stable_routes,
        "identity": {
            "durable_preference": ["UPC", "parcel_number"],
            "alternate_parcel_locator": "alt_id",
            "feature_occurrence": "OBJECTID",
            "objectid_only_projectable_as_parcel": False,
            "same_record_key": (
                "US-NM-SANTA-FE:PARCEL:{UPC_or_parcel_number}"
            ),
        },
        "paging": {
            "mechanism": "resultOffset/resultRecordCount",
            "order_by": "OBJECTID",
            "native_page_size": metadata["native_page_size"],
            "caller_window": "optional",
            "omitted_caller_window": "exhaust_source_reported_pages",
        },
        "lineage": {
            "same_assessor_non_independent": [
                "us-nm-santa-fe-assessor-parcel-download",
                "us-nm-santa-fe-assessor-parcels-map",
                "us-nm-santa-fe-assessor-notices",
            ],
            "independent_recorded_instrument": (
                "us-nm-santa-fe-clerktrack-index"
            ),
            "distinct_tax_record": (
                "us-nm-santa-fe-treasurer-paydici"
            ),
            "assessor_recorder_fields_are_join_hints": True,
        },
        "shared_operations": [
            "search",
            "owner",
            "address",
            "parcel",
            "map",
            "discovery",
            "freshness",
            "probe",
        ],
        "monitor": {
            "request_budget": expected_requests,
            "metadata_requests": 1,
            "exact_sentinel_requests": 1,
            "geometry_fetched": False,
            "document_artifacts_fetched": False,
        },
    }
    schema_contract = {
        "layer_contract": metadata["schema"],
        "required_fields": sorted(adapter.REQUIRED_FIELDS),
        "market_fields": list(adapter.MARKET_FIELDS),
        "exemption_fields": list(adapter.EXEMPTION_FIELDS),
        "normalized_record_fields": sorted(record),
        "identity_fields": sorted(record.get("identity") or {}),
        "assessment_periods": sorted(record.get("assessment") or {}),
    }
    current = (record.get("assessment") or {}).get("current") or {}
    route_counts = {
        route["route_id"]: route.get("observed_count")
        for route in adapter.SOURCE_ROUTES
        if route.get("observed_count") is not None
    }
    rolling_observation = {
        "owner_names": [
            owner.get("raw_name")
            for owner in record.get("owners") or []
            if isinstance(owner, Mapping)
        ],
        "account_status": record.get("account_status"),
        "current_assessment_source_fields": current.get(
            "source_fields"
        ),
        "route_observed_counts": route_counts,
        "sentinel_result_count": len(fetched.records),
        "requests_made": request_count,
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "upc": adapter.PROBE_UPC,
        "parcel_number": adapter.PROBE_PARCEL_NUMBER,
        "canonical_ref": record.get("canonical_ref"),
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.LAYER_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": stable_contract,
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_usvi_property_tax(context: ProbeContext) -> ProbeObservation:
    """Verify one parcel-year CAMA contract without printable artifacts."""

    adapter = query_usvi_property_tax
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("USVI Capture CAMA monitor source ID changed")
    expected_requests = 5
    started = time.perf_counter()
    client = adapter.CaptureCAMAClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
        request_budget=expected_requests,
    )
    try:
        record = adapter.fetch_parcel_detail(
            client,
            parcel_number=adapter.PROBE_PARCEL_NUMBER,
            tax_year=adapter.PROBE_TAX_YEAR,
            component_names=("valuation",),
        )
        request_count = client.request_count
    finally:
        client.close()
    if request_count != expected_requests:
        raise ValueError(
            "USVI Capture CAMA sentinel did not honor its five-request contract"
        )
    if (
        record.get("source_id") != adapter.SOURCE_ID
        or record.get("formatted_parcel_number")
        != adapter.PROBE_PARCEL_NUMBER
        or str(record.get("tax_year")) != adapter.PROBE_TAX_YEAR
    ):
        raise ValueError("USVI Capture CAMA parcel-year sentinel identity changed")

    stable_contract = {
        "source_id": adapter.SOURCE_ID,
        "jurisdiction_id": adapter.JURISDICTION_ID,
        "platform_family": adapter.PLATFORM_FAMILY,
        "routes": {
            "search": adapter.SEARCH_URL,
            "parcel_detail": adapter.INFO_URL,
            "component_root": adapter.BASE_URL,
            "print_view": (
                adapter.BASE_URL + "CZ_ReceiptPrint.aspx"
            ),
        },
        "search_fields": ["owner", "parcel", "address", "legal"],
        "native_page_sizes": list(adapter.NATIVE_PAGE_SIZES),
        "paging": {
            "control": "GridView1",
            "next_argument": "Page$Next",
            "caller_window": "after_native_page_exhaustion",
        },
        "identity": {
            "assessment_observation": (
                "formatted_parcel_number_plus_tax_year"
            ),
            "source_internal_parcel_id": (
                "tax_year_specific_detail_locator"
            ),
            "statement": (
                "formatted_parcel_number_plus_tax_year_plus_statement_number"
            ),
            "payment": (
                "formatted_parcel_number_plus_payment_transaction_id"
            ),
            "printable_artifact": (
                "nested_statement_payment_or_property_card_representation"
            ),
        },
        "monitor": {
            "request_budget": expected_requests,
            "components_fetched": ["valuation"],
            "large_artifacts_fetched": False,
        },
        "same_tenant_failover": {
            "url": adapter.FAILOVER_BASE_URL,
            "independent_evidence": False,
        },
        "official_complements": {
            "recorder": (
                "us-vi-recorder-of-deeds-countyfusion"
            ),
            "tax_collector": (
                "https://ltg.gov.vi/departments/office-of-tax-collector/"
            ),
        },
    }
    current = record.get("current_published_observation")
    current = dict(current) if isinstance(current, Mapping) else {}
    components = record.get("components")
    components = dict(components) if isinstance(components, Mapping) else {}
    valuation = components.get("valuation")
    valuation = dict(valuation) if isinstance(valuation, Mapping) else {}
    schema_contract = {
        "record_fields": sorted(record),
        "current_observation_fields": sorted(current),
        "valuation_component_fields": sorted(valuation),
        "statement_fields": sorted(
            {
                key
                for statement in valuation.get("statements", [])
                if isinstance(statement, Mapping)
                for key in statement
            }
        ),
        "statement_published_fields": sorted(
            {
                str(key)
                for statement in valuation.get("statements", [])
                if isinstance(statement, Mapping)
                for published in [statement.get("published_fields")]
                if isinstance(published, Mapping)
                for key in published
            }
        ),
        "valuation_history_fields": sorted(
            {
                key
                for value in valuation.get("valuation_history", [])
                if isinstance(value, Mapping)
                for key in value
            }
        ),
        "valuation_history_published_fields": sorted(
            {
                str(key)
                for value in valuation.get("valuation_history", [])
                if isinstance(value, Mapping)
                for published in [value.get("published_fields")]
                if isinstance(published, Mapping)
                for key in published
            }
        ),
        "payment_fields": sorted(
            {
                key
                for payment in valuation.get("payment_transactions", [])
                if isinstance(payment, Mapping)
                for key in payment
            }
        ),
        "payment_published_fields": sorted(
            {
                str(key)
                for payment in valuation.get("payment_transactions", [])
                if isinstance(payment, Mapping)
                for published in [payment.get("published_fields")]
                if isinstance(published, Mapping)
                for key in published
            }
        ),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "formatted_parcel_number": adapter.PROBE_PARCEL_NUMBER,
        "tax_year": adapter.PROBE_TAX_YEAR,
        "canonical_ref": record.get("canonical_ref"),
    }
    rolling_observation = {
        "source_internal_parcel_id": record.get(
            "source_internal_parcel_id"
        ),
        "owner_name": current.get("owner_name"),
        "land_value": current.get("land_value"),
        "improvement_value": current.get("improvement_value"),
        "assessed_value": current.get("assessed_value"),
        "total_due": current.get("total_due"),
        "statement_count": len(valuation.get("statements") or []),
        "valuation_history_count": len(
            valuation.get("valuation_history") or []
        ),
        "payment_count": len(
            valuation.get("payment_transactions") or []
        ),
        "requests_made": request_count,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.SEARCH_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


def probe_usvi_recorder(context: ProbeContext) -> ProbeObservation:
    """Verify one exact CountyFusion instrument in a fixed no-image budget."""

    adapter = query_usvi_recorder
    if context.source_id != adapter.SOURCE_ID:
        raise ValueError("USVI Recorder monitor source ID changed")
    expected_requests = 12
    started = time.perf_counter()
    client = adapter.USVIRecorderClient(
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        max_attempts=context.max_attempts,
        retry_backoff=adapter.RETRY_BACKOFF,
        request_budget=expected_requests,
    )
    try:
        record = client.select_exact(
            district=adapter.PROBE_DISTRICT,
            inst_id=adapter.PROBE_INST_ID,
            instrument_number=adapter.PROBE_INSTRUMENT_NUMBER,
        )
        request_count = client.request_count
    finally:
        client.close()
    if request_count != expected_requests:
        raise ValueError(
            "USVI Recorder sentinel did not honor its 12-request no-image contract"
        )
    expected_identity = adapter.native_instrument_identity(
        adapter.PROBE_DISTRICT,
        adapter.PROBE_INST_ID,
    )
    if (
        record.get("source_id") != adapter.SOURCE_ID
        or record.get("native_document_id") != expected_identity
        or record.get("instrument_number") != adapter.PROBE_INSTRUMENT_NUMBER
        or record.get("district") != adapter.PROBE_DISTRICT
    ):
        raise ValueError("USVI Recorder exact instrument sentinel identity changed")

    stable_contract = {
        "source": adapter.SOURCE_METADATA.to_dict(),
        "jurisdiction": adapter.JURISDICTION.to_dict(),
        "official_linking_page": adapter.OFFICIAL_LINKING_PAGE,
        "routes": {
            "guest_login": adapter.LOGIN_DISPLAY_URL,
            "search": adapter.SEARCH_EXECUTE_URL,
            "detail": adapter.DISPLAY_DOCUMENT_URL,
            "page_state": adapter.IMAGE_PAGE_STATE_URL,
            "page_image": adapter.IMAGE_PNG_URL,
        },
        "identity": {
            "instrument": "district_plus_inst_id",
            "instrument_number": "lookup_and_join_key",
            "book_page": "lookup_and_join_key",
            "page_image": "nested_instrument_representation",
        },
        "pagination": "exhaust_source_pages_before_explicit_caller_window",
        "monitor": {
            "request_budget": expected_requests,
            "image_fetched": False,
        },
        "current_publicsearch_alternative": {
            "url": adapter.CURRENT_PUBLICSEARCH_COMPLEMENT,
            "relationship": "same_recorder_authority_alternate_access_route",
            "independent_evidence": False,
        },
    }
    schema_contract = {
        "record_fields": sorted(record),
        "party_fields": sorted(
            {
                key
                for party in record.get("parties", [])
                if isinstance(party, Mapping)
                for key in party
            }
        ),
        "legal_description_fields": sorted(
            {
                key
                for legal in record.get("legal_descriptions", [])
                if isinstance(legal, Mapping)
                for key in legal
            }
        ),
        "associated_document_fields": sorted(
            {
                key
                for document in record.get("associated_documents", [])
                if isinstance(document, Mapping)
                for key in document
            }
        ),
    }
    artifact_identity = {
        "source_id": adapter.SOURCE_ID,
        "district": adapter.PROBE_DISTRICT,
        "inst_id": adapter.PROBE_INST_ID,
        "instrument_number": adapter.PROBE_INSTRUMENT_NUMBER,
        "canonical_ref": record.get("canonical_ref"),
    }
    rolling_observation = {
        "instrument_type": record.get("instrument_type"),
        "recording_date": record.get("recording_date"),
        "detail_page_count": record.get("detail_page_count"),
        "party_count": len(record.get("parties") or []),
        "legal_description_count": len(record.get("legal_descriptions") or []),
        "associated_document_count": len(record.get("associated_documents") or []),
        "requests_made": request_count,
    }
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=adapter.LOGIN_DISPLAY_URL,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=sha256_fingerprint(schema_contract),
        artifact_sha256=sha256_fingerprint(stable_contract),
        result_count=1,
        details={
            "stable_contract": _json_ready(stable_contract),
            "schema_contract": schema_contract,
            "artifact_identity": artifact_identity,
            "rolling_observation": rolling_observation,
        },
    )


# Central, inspectable registry. Adding a source requires an explicit entry here.
HANDLER_REGISTRY: dict[str, ProbeHandlerSpec] = {
    query_nyc_pip.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_nyc_pip.SOURCE_ID,
        capability="probe_source",
        endpoint=query_nyc_pip.PIP_URL,
        observation=(
            "Five layer metadata contracts plus one exact BBL page per layer, "
            "with stable route, layer, identity, and paging hashes separated "
            "from rolling owners, values, years, counts, and OBJECTIDs"
        ),
        expected_requests=10,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_nyc_pip,
    ),
    query_santa_fe_clerktrack.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_santa_fe_clerktrack.SOURCE_ID,
        capability="probe_source",
        endpoint=query_santa_fe_clerktrack.LOGIN_URL,
        observation=(
            "Exact five-request no-image instrument sentinel with dynamic "
            "list/detail agreement and stable route, form, identity, paging, "
            "reacquisition, and lineage contracts"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_santa_fe_clerktrack,
    ),
    query_santa_fe_property.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_santa_fe_property.SOURCE_ID,
        capability="probe_source",
        endpoint=query_santa_fe_property.LAYER_URL,
        observation=(
            "Validated live-layer metadata plus one exact county-owned UPC "
            "sentinel, with stable routing, identity, paging, and lineage "
            "separated from rolling owner, value, and count fields"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_santa_fe_property,
    ),
    query_usvi_property_tax.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_usvi_property_tax.SOURCE_ID,
        capability="probe_source",
        endpoint=query_usvi_property_tax.SEARCH_URL,
        observation=(
            "Exact formatted-parcel plus tax-year identity, paging and "
            "component-route contract, and valuation/statement/payment "
            "schemas within a fixed no-artifact request budget"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_usvi_property_tax,
    ),
    query_usvi_recorder.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_usvi_recorder.SOURCE_ID,
        capability="probe_source",
        endpoint=query_usvi_recorder.LOGIN_DISPLAY_URL,
        observation=(
            "Exact district-plus-instId instrument identity, detail schema, "
            "native paging contract, and official complement relationships "
            "within a fixed no-image request budget"
        ),
        expected_requests=12,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_usvi_recorder,
    ),
    query_census_acs.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_census_acs.SOURCE_ID,
        capability="probe_source",
        endpoint=(
            f"{query_census_acs.OFFICIAL_API_ROOT}/"
            f"{query_census_acs.DEFAULT_YEAR}/acs/acs5.html"
        ),
        observation=(
            "Official ACS dataset and variable metadata plus one Baltimore "
            "County observation through the selected backend, with release, "
            "schema, operation states, and same-release attribution retained"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_census_acs,
    ),
    DESCHUTES_CDD_WEBLINK_SOURCE_ID: ProbeHandlerSpec(
        source_id=DESCHUTES_CDD_WEBLINK_SOURCE_ID,
        capability="probe_source",
        endpoint=DESCHUTES_CDD_WEBLINK_BASE_URL,
        observation=(
            "One DIAL account index, recent electronic and historical imaged "
            "document metadata, viewer capabilities, and parent-folder metadata"
        ),
        expected_requests=query_ohio_licking_common_pleas.PROBE_REQUEST_COUNT,
        sentinel_record_count=2,
        sample_bytes=None,
        handler=probe_deschutes_cdd_weblink,
    ),
    DESCHUTES_DIAL_SOURCE_ID: ProbeHandlerSpec(
        source_id=DESCHUTES_DIAL_SOURCE_ID,
        capability="probe_source",
        endpoint=DESCHUTES_DIAL_BASE_URL,
        observation=(
            "Exact taxlot-to-account resolution, all account component "
            "schemas, linked-system states, and one ownership PDF"
        ),
        expected_requests=15,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_deschutes_dial,
    ),
    DESCHUTES_PROPERTY_SOURCE_ID: ProbeHandlerSpec(
        source_id=DESCHUTES_PROPERTY_SOURCE_ID,
        capability="probe_source",
        endpoint=DESCHUTES_PROPERTY_SERVICE_URL,
        observation=(
            "Service inventory, component counts, declared relationships, "
            "keyed sales complement, and one hydrated taxlot"
        ),
        expected_requests=54,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_deschutes_property,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=config.layer_url,
            observation=(
                "Publisher-scoped ArcGIS schema, total count, and one exact "
                "taxlot sentinel"
            ),
            expected_requests=4,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_taxlot_component,
        )
        for source_id, config in OREGON_TAXLOT_SOURCES.items()
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=config.layer_url,
            observation=(
                "Component-scoped ArcGIS schema, total count, exact "
                "sentinel, freshness, join keys, and complement routes"
            ),
            expected_requests=(3 if config.record_kind == "sale_reference" else 4),
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_lane_marion_property_component,
        )
        for source_id, config in (OREGON_LANE_MARION_PROPERTY_SOURCES.items())
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=(
                query_oregon_lane_property.ACCOUNT_ROOT_URL
                if source_id == query_oregon_lane_property.ACCOUNT_SOURCE_ID
                else query_oregon_lane_property.TAX_MAP_SEARCH_URL
            ),
            observation=(
                "Anonymous JSON search and cookie-session account detail"
                if source_id
                == query_oregon_lane_property.ACCOUNT_SOURCE_ID
                else (
                    "Fresh WebForms locator search and the linked official "
                    "tax-map PDF bytes"
                )
            ),
            expected_requests=3,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_lane_property_source,
        )
        for source_id in query_oregon_lane_property.SOURCE_IDS
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=query_oregon_marion_downloads.LANDING_URL,
            observation=(
                "Complete official release manifest plus validator metadata "
                "and one bounded sample from the selected current artifact"
            ),
            expected_requests=3,
            sentinel_record_count=1,
            sample_bytes=64,
            handler=probe_oregon_marion_download,
        )
        for source_id in query_oregon_marion_downloads.SOURCE_IDS
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=collection.collection_url,
            observation=(
                "Collection-scoped search schema, exact item metadata, full "
                "text state, and document route"
            ),
            expected_requests=2,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_court_document_component,
        )
        for source_id, collection in (OREGON_COURT_DOCUMENT_COLLECTIONS.items())
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=OREGON_COURT_DIRECTORY_LISTS_URL,
            observation=(
                "Anonymous page bootstrap, cookie-bound SharePoint SOAP "
                "list/view schemas, live view inventory, and complete "
                "default-view rowset"
            ),
            expected_requests=5,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_court_directory_component,
        )
        for source_id, source in OREGON_COURT_DIRECTORY_SOURCES.items()
    },
    OREGON_APPELLATE_SOURCE_ID: ProbeHandlerSpec(
        source_id=OREGON_APPELLATE_SOURCE_ID,
        capability="probe_source",
        endpoint=OREGON_APPELLATE_API_ROOT,
        observation=(
            "Court roster, exact case, docket, party, hearing, judgment, "
            "group, document-metadata, and calendar component health"
        ),
        expected_requests=11,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_oregon_appellate,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=spec.page_url,
            observation=(
                "Legacy-entrypoint migration, current official page, "
                "SharePoint list/view contract, complete continuation "
                "traversal, and published attachment counts"
            ),
            expected_requests=9 if spec is OREGON_COA_CALENDAR else 7,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_appellate_calendar_component,
        )
        for source_id, spec in OREGON_APPELLATE_CALENDAR_SOURCES.items()
    },
    OREGON_COURT_CALENDAR_SOURCE_ID: ProbeHandlerSpec(
        source_id=OREGON_COURT_CALENDAR_SOURCE_ID,
        capability="probe_source",
        endpoint=OREGON_COURT_CALENDAR_URL,
        observation=(
            "Anonymous session handshake, location and judicial-officer "
            "directories, bounded Deschutes calendar result, and source "
            "truncation signals"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_oregon_court_calendar,
    ),
    OREGON_SMART_SEARCH_SOURCE_ID: ProbeHandlerSpec(
        source_id=OREGON_SMART_SEARCH_SOURCE_ID,
        capability="probe_source",
        endpoint=OREGON_SMART_SEARCH_URL,
        observation=(
            "Rendered Smart Search form and stable selector contract, with "
            "judicial-officer counts and browser runtime reported separately"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_oregon_smart_search,
    ),
    OREGON_OJCIN_SOURCE_ID: ProbeHandlerSpec(
        source_id=OREGON_OJCIN_SOURCE_ID,
        capability="probe_source",
        endpoint=OREGON_OJCIN_URL,
        observation=(
            "OJCIN public product and official endpoint contract, with live "
            "HTTP status and headers reported separately"
        ),
        expected_requests=len(OREGON_OJCIN_ENDPOINTS),
        sentinel_record_count=len(OREGON_OJCIN_ENDPOINTS),
        sample_bytes=None,
        handler=probe_oregon_ojcin_public_directory,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=config.primary_page,
            observation=(
                "County publication-route schema and one current PDF version, "
                "with rolling page, route, and artifact values reported "
                "separately from the stable source contract"
            ),
            expected_requests=len(config.landing_pages) + 1,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_tax_foreclosure_component,
        )
        for source_id, config in OREGON_TAX_FORECLOSURE_SOURCES.items()
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=tenant.search_url,
            observation=(
                "County-native Helion advanced-search form, selector "
                "vocabulary, and index-freshness statement"
            ),
            expected_requests=3,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_helion_recorder_component,
        )
        for source_id, tenant in OREGON_HELION_RECORDER_TENANTS.items()
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=tenant.portal_root,
            observation=(
                "Rendered county PSO form title and native selector contract, "
                "with browser runtime and transport events reported separately"
            ),
            expected_requests=1,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_helion_property_component,
        )
        for source_id, tenant in OREGON_HELION_PROPERTY_TENANTS.items()
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=config.layer_url,
            observation=(
                "County assessor service, layer, schema, and complement "
                "contract with counts, sentinel row, and update observations "
                "reported separately"
            ),
            expected_requests=5,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_county_assessor_component,
        )
        for source_id, config in (OREGON_JACKSON_DOUGLAS_ASSESSOR_SOURCES.items())
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=config.layer_url,
            observation=(
                "County-native assessor service, layer, schema, and complement "
                "contract with counts, sentinel row, and native update "
                "observations reported separately"
            ),
            expected_requests=6 if config.update_order_field else 5,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_county_assessor_component,
        )
        for source_id, config in (
            OREGON_LINN_JOSEPHINE_KLAMATH_ASSESSOR_SOURCES.items()
        )
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=config.layer_url,
            observation=(
                "Jackson event-layer identity and schema with total count and "
                "first/last ordered observations reported separately"
            ),
            expected_requests=4,
            sentinel_record_count=2,
            sample_bytes=None,
            handler=probe_oregon_jackson_property_event_component,
        )
        for source_id, config in OREGON_JACKSON_PROPERTY_EVENT_SOURCES.items()
    },
    **{
        source.source_id: ProbeHandlerSpec(
            source_id=source.source_id,
            capability="probe_source",
            endpoint=source.source_metadata().base_url or source.arcgis_url,
            observation=(
                "Verified Accela detail-module and ArcGIS complement contract "
                "with one record and attachment-list representation"
            ),
            expected_requests=2,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_jackson_accela_component,
        )
        for source in OREGON_JACKSON_ACCELA_SOURCES.values()
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=tenant.base_url,
            observation=(
                f"{tenant.court_name} Tyler tenant contract with directly "
                "observed case and docket access states reported separately"
            ),
            expected_requests=2,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_eugene_municipal_court_component,
        )
        for source_id, tenant in (OREGON_TYLER_MUNICIPAL_TENANTS_BY_SOURCE.items())
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=(
                query_oregon_benton_property.PARCEL_LAYER_URL
                if source_id == query_oregon_benton_property.PARCEL_SOURCE_ID
                else (
                    query_oregon_benton_property.ASSESSMENT_DIRECTORY_URL
                    if source_id == query_oregon_benton_property.BULK_SOURCE_ID
                    else query_oregon_benton_property.ASSESSMENT_MAP_DIRECTORY_URL
                )
            ),
            observation=(
                "Benton County component identity and schema with rolling "
                "counts, listings, releases, or artifact observations "
                "reported separately"
            ),
            expected_requests=(
                6
                if source_id == query_oregon_benton_property.PARCEL_SOURCE_ID
                else (
                    4 if source_id == query_oregon_benton_property.BULK_SOURCE_ID else 2
                )
            ),
            sentinel_record_count=1,
            sample_bytes=(
                None
                if source_id == query_oregon_benton_property.PARCEL_SOURCE_ID
                else 8
            ),
            handler=probe_oregon_benton_property_component,
        )
        for source_id in (
            query_oregon_benton_property.PARCEL_SOURCE_ID,
            query_oregon_benton_property.BULK_SOURCE_ID,
            query_oregon_benton_property.MAP_SOURCE_ID,
        )
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=(
                _oregon_county_component_module(source_id)
                .SOURCE_METADATA[source_id]
                .base_url
                or ""
            ),
            observation=(
                "County component identity and schema, with current counts, "
                "versions, and sentinel state reported separately"
            ),
            expected_requests=3,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_county_property_component,
        )
        for source_id in (
            *query_oregon_yamhill_property.SOURCE_IDS,
            *query_oregon_clackamas_property.SOURCE_IDS,
            *query_oregon_wasco_property.SOURCE_IDS,
        )
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=(
                query_oregon_washington_property.SOURCES[source_id].base_url or ""
            ),
            observation=(
                "Washington County component identity and schema, with "
                "sentinel matches and current statement years reported "
                "separately"
            ),
            expected_requests=(
                2
                if source_id
                in {
                    query_oregon_washington_property.SURVEY_MAP_SOURCE_ID,
                    query_oregon_washington_property.TAXLOT_SOURCE_ID,
                    query_oregon_washington_property.SITUS_SOURCE_ID,
                }
                else 1
            ),
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_washington_property_component,
        )
        for source_id in query_oregon_washington_property.SOURCES
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=(query_dc_court_directory_data.COMPONENTS[source_id].base_url),
            observation=(
                "Complete judicial-role traversal and current court-contact "
                "shape, with personnel counts reported separately"
                if source_id != query_dc_court_directory_data.REPORTS_SOURCE_ID
                else "Official report-catalog occurrence and section contract, "
                "with publication and anomaly counts reported separately"
            ),
            expected_requests=expected_requests,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_dc_court_directory_data_component,
        )
        for source_id, expected_requests in {
            query_dc_court_directory_data.SUPERIOR_DIRECTORY_SOURCE_ID: 6,
            query_dc_court_directory_data.APPEALS_DIRECTORY_SOURCE_ID: 2,
            query_dc_court_directory_data.REPORTS_SOURCE_ID: 1,
        }.items()
    },
    query_broward_official_records.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_broward_official_records.SOURCE_ID,
        capability="probe_source",
        endpoint=query_broward_official_records.SEARCH_URL,
        observation=(
            "Browser-rendered public search family and coverage statements, "
            "with session PDF, certified-copy, ten-day bulk, and older-record "
            "routes retained as distinct stable components"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_broward_official_records,
    ),
    query_osceola_courts.PORTAL_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_osceola_courts.PORTAL_SOURCE_ID,
        capability="probe_source",
        endpoint=query_osceola_courts.SEARCH_LANDING_URL,
        observation=(
            "One exact case through Benchmark bootstrap, search, case, docket, "
            "and public document-page metadata contracts"
        ),
        expected_requests=12,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_osceola_benchmark,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=(
                query_osceola_courts.CALENDAR_URL
                if source_id == query_osceola_courts.CALENDAR_SOURCE_ID
                else query_osceola_courts.FORECLOSURE_URL
            ),
            observation=(
                "Rolling official PDF route identity and current HEAD metadata"
            ),
            expected_requests=1,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_osceola_report,
        )
        for source_id in (
            query_osceola_courts.CALENDAR_SOURCE_ID,
            query_osceola_courts.FORECLOSURE_SOURCE_ID,
        )
    },
    query_florida_ninth_opinions.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_florida_ninth_opinions.SOURCE_ID,
        capability="probe_source",
        endpoint=query_florida_ninth_opinions.INDEX_URL,
        observation=(
            "First archive page, source-visible pagination, stable opinion "
            "identity, and one validated official PDF"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_florida_ninth_opinions,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=(
                query_florida_court_directory_data.COMPONENTS[source_id].base_url
            ),
            observation={
                query_florida_court_directory_data.LOCATION_SOURCE_ID: (
                    "Current court-location snapshot, publisher omissions, "
                    "and differing map-category and embedded-region values"
                ),
                query_florida_court_directory_data.VIRTUAL_SOURCE_ID: (
                    "Current virtual-courtroom snapshot, partial personnel "
                    "labels, county participation, and live state"
                ),
                query_florida_court_directory_data.PUBLIC_RECORDS_SOURCE_ID: (
                    "Current OSCA-held-record request scope, published "
                    "contact methods, and fee-estimate notice"
                ),
                query_florida_court_directory_data.STATISTICS_SOURCE_ID: (
                    "Aggregate statistical publication occurrences, fiscal "
                    "years, sections, and exact direct-adapter PDF semantics"
                ),
            }[source_id],
            expected_requests=1,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_florida_court_directory_data_component,
        )
        for source_id in FLORIDA_COURT_DIRECTORY_DATA_MONITOR_SOURCE_IDS
    },
    query_georgia_property_sources.DIRECTORY_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_georgia_property_sources.DIRECTORY_SOURCE_ID,
        capability="probe_source",
        endpoint=query_georgia_property_sources.DIRECTORY_URL,
        observation=(
            "County-route membership, published route disagreements, "
            "destination-platform families, and source snapshot"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_georgia_property_source,
    ),
    query_georgia_property_sources.GSCCCA_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_georgia_property_sources.GSCCCA_SOURCE_ID,
        capability="probe_source",
        endpoint=query_georgia_property_sources.GSCCCA_INFORMATION_URL,
        observation=(
            "Statewide index coverage, free limited-use account facts, "
            "and official acquisition routes"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_georgia_property_source,
    ),
    query_georgia_court_directory.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_georgia_court_directory.SOURCE_ID,
        capability="probe_source",
        endpoint=query_georgia_court_directory.LANDING_URL,
        observation=(
            "Published search/detail view contract, current Superior Court "
            "Clerks match count, and one exact personnel detail"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_georgia_court_personnel_directory,
    ),
    query_georgia_court_access.EACCESS_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_georgia_court_access.EACCESS_SOURCE_ID,
        capability="probe_source",
        endpoint=query_georgia_court_access.EACCESS_URL,
        observation=(
            "Current court-to-case-access provider handoffs, account state, "
            "published HTTP routes, provider-selection copy, and county scope"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_georgia_court_access_directory,
    ),
    query_georgia_court_access.EFILE_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_georgia_court_access.EFILE_SOURCE_ID,
        capability="probe_source",
        endpoint=query_georgia_court_access.EFILE_URL,
        observation=(
            "Current court-to-filing-provider states, source-published HTTP "
            "routes, blank-cell non-listings, and county scope"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_georgia_court_access_directory,
    ),
    query_georgia_court_data.DASHBOARD_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_georgia_court_data.DASHBOARD_SOURCE_ID,
        capability="probe_source",
        endpoint=query_georgia_court_data.DATA_URL,
        observation=(
            "Six self-reported aggregate caseload dashboard classes, "
            "published guide, export route, and catalog snapshot"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_georgia_court_data_source,
    ),
    query_georgia_court_data.WORKLOAD_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_georgia_court_data.WORKLOAD_SOURCE_ID,
        capability="probe_source",
        endpoint=query_georgia_court_data.DATA_URL,
        observation=(
            "Annual aggregate workload publication set and one validated "
            "latest official PDF"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_georgia_court_data_source,
    ),
    query_georgia_supreme_docket.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_georgia_supreme_docket.SOURCE_ID,
        capability="probe_source",
        endpoint=query_georgia_supreme_docket.PORTAL_URL,
        observation=(
            "Stable anonymous search/detail contracts and schema hashes, "
            "plus rolling exact-case filing, judgment, and attorney counts"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_georgia_supreme_docket,
    ),
    query_doj_court_records.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_doj_court_records.SOURCE_ID,
        capability="probe_source",
        endpoint=query_doj_court_records.INDEX_URL,
        observation=(
            "Current DOJ case-group index, one sentinel case page, five PDF "
            "signature bytes, and distinct DOJ, PACER, RECAP, clerk, archive, "
            "and local-corpus roles"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=5,
        handler=probe_doj_epstein_court_records,
    ),
    query_edva_bankruptcy.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_edva_bankruptcy.SOURCE_ID,
        capability="probe_source",
        endpoint=query_edva_bankruptcy.RECAP_COVERAGE_URL,
        observation=(
            "Two known CourtListener docket identities, one RECAP entry page "
            "per docket, the read-only fetch OPTIONS contract, and distinct "
            "archive, PACER/ECF, clerk, public-terminal, and archive routes"
        ),
        expected_requests=5,
        sentinel_record_count=2,
        sample_bytes=None,
        handler=probe_edva_bankruptcy,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=source.base_url,
            observation=(
                "Stable annual decision-publication, identity, and schema "
                "contract with current index and representative PDF hashes "
                "reported as rolling observations"
            ),
            expected_requests=(
                4
                if source_id
                == query_georgia_supreme_publications.APPLICATION_GRANT_SOURCE_ID
                else 2
            ),
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_georgia_supreme_publication,
        )
        for source_id, source in (
            query_georgia_supreme_publications.SOURCE_METADATA.items()
        )
    },
    query_california_opinions.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_california_opinions.SOURCE_ID,
        capability="probe_source",
        endpoint=query_california_opinions.OPINIONS_HOME_URL,
        observation=(
            "Stable current-feed listing/detail schemas and route identity, "
            "with rolling publication counts, pages, sample cases, and "
            "artifact hashes reported separately"
        ),
        expected_requests=query_ohio_licking_property.PROBE_EXPECTED_REQUESTS,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_california_opinions,
    ),
    query_california_court_directory.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_california_court_directory.SOURCE_ID,
        capability="probe_source",
        endpoint=query_california_court_directory.DIRECTORY_URL,
        observation=(
            "Complete 58-county directory contract, route fields, appellate "
            "districts, and rolling published destinations"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_california_court_directory,
    ),
    query_santa_clara_court_records.TENTATIVE_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_santa_clara_court_records.TENTATIVE_SOURCE_ID,
        capability="probe_source",
        endpoint=query_santa_clara_court_records.TENTATIVE_URL,
        observation=(
            "Current department directory, Department 1 ruling index, and "
            "one validated official PDF"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_santa_clara_tentative_rulings,
    ),
    query_san_diego_court_index.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_san_diego_court_index.SOURCE_ID,
        capability="probe_source",
        endpoint=query_san_diego_court_index.NEW_FILINGS_LANDING_URL,
        observation=(
            "Static five-court-day filing landing and one native partition "
            "for each of five case types"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_san_diego_new_filings,
    ),
    query_wisconsin_court_directory.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_wisconsin_court_directory.SOURCE_ID,
        capability="probe_source",
        endpoint=query_wisconsin_court_directory.DIRECTORIES_URL,
        observation=(
            "All six official court-directory components, statewide county "
            "coverage, component schemas and snapshots, and complementary "
            "case, publication, municipal, employee, and juror routes"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_wisconsin_court_directory,
    ),
    query_washington_courts.DIRECTORY_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_washington_courts.DIRECTORY_SOURCE_ID,
        capability="probe_source",
        endpoint=query_washington_courts.DIRECTORY_HOME_URL,
        observation=(
            "Official county index, organization sentinel, directory PDF, "
            "and current operation states"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_washington_court_component,
    ),
    query_washington_courts.OPINIONS_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_washington_courts.OPINIONS_SOURCE_ID,
        capability="probe_source",
        endpoint=query_washington_courts.OPINIONS_HOME_URL,
        observation=(
            "Official appellate RSS, exact opinion information sheet, PDF "
            "artifact, and current operation states"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_washington_court_component,
    ),
    query_washington_digital_archives_land.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_washington_digital_archives_land.SOURCE_ID,
        capability="probe_source",
        endpoint=(
            f"{query_washington_digital_archives_land.BASE_URL}"
            f"{query_washington_digital_archives_land.TITLE_LIST_PATH}"
        ),
        observation=(
            "Bounded anonymous title inventory, one title contract, one "
            "sentinel search page, and one record detail; document generation "
            "remains a separate uninvoked reCAPTCHA queue"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_washington_digital_archives_land,
    ),
    query_mason_county_tax_parcels.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_mason_county_tax_parcels.SOURCE_ID,
        capability="probe_source",
        endpoint=query_mason_county_tax_parcels.LAYER_URL,
        observation=(
            "Declared layer schema and non-pageable support flags, complete "
            "FID snapshot, and the smallest current feature as a rolling sample"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_mason_county_tax_parcels,
    ),
    query_md_mdp_parcel_points.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_mdp_parcel_points.SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_mdp_parcel_points.LAYER_URL,
        observation=(
            "Declared ArcGIS schema, ACCTID/OBJECTID identity roles, bounded "
            "population count and maximum OBJECTID, and one rolling point "
            "feature sample"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_maryland_mdp_parcel_points,
    ),
    query_md_plats.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_plats.SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_plats.INDEX_URL,
        observation=(
            "All 24 county routes, one bounded metadata-inclusive search "
            "with source totals and native paging state, and one exact "
            "session-independent plat unit with published representation "
            "metadata"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_maryland_plats,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=query_md_mdp_property_downloads.LANDING_URL,
            observation=(
                "Official release manifest, selected non-schema data "
                "artifact, provider-link identity, transport validators, "
                "and one bounded ZIP-container sample"
            ),
            expected_requests=3,
            sentinel_record_count=1,
            sample_bytes=64,
            handler=probe_maryland_mdp_property_download,
        )
        for source_id in query_md_mdp_property_downloads.SOURCE_IDS
    },
    query_palm_beach_property_appraiser.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_palm_beach_property_appraiser.SOURCE_ID,
        capability="probe_source",
        endpoint=query_palm_beach_property_appraiser.LAYER_URL,
        observation=(
            "PARCEL_DETAILS and same-publisher QSALES schema contracts, "
            "rolling counts and identifier cardinalities, and one bounded "
            "OBJECTID occurrence sample"
        ),
        expected_requests=11,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_palm_beach_property_appraiser,
    ),
    query_orange_tax_collector.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_orange_tax_collector.SOURCE_ID,
        capability="probe_source",
        endpoint=query_orange_tax_collector.ALGOLIA_URL,
        observation=(
            "Current Algolia account and direct TaxSys history sentinel, "
            "official historical landing links, and fixed 2020 artifact "
            "observations with stable, rolling, and historical state separated"
        ),
        expected_requests=7,
        sentinel_record_count=1,
        sample_bytes=64,
        handler=probe_orange_tax_collector,
    ),
    query_palm_beach_tax_collector.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_palm_beach_tax_collector.SOURCE_ID,
        capability="probe_source",
        endpoint=query_palm_beach_tax_collector.QUICK_SETTINGS_URL,
        observation=(
            "QuickSearch settings, account-refresh routing, and one exact-PCN "
            "rolling search sample with stable and rolling state separated"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_palm_beach_tax_collector,
    ),
    query_palm_beach_tax_deeds.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_palm_beach_tax_deeds.SOURCE_ID,
        capability="probe_source",
        endpoint=query_palm_beach_tax_deeds.HOME_URL,
        observation=(
            "Native search/grid and identity contract, rolling sale-date and "
            "Lands Available state, exact case sentinel, document inventory, "
            "and one validated public PDF"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_palm_beach_tax_deeds,
    ),
    query_washington_taxsifter.UMBRELLA_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_washington_taxsifter.UMBRELLA_SOURCE_ID,
        capability="probe_source_family",
        endpoint=query_washington_parcels.ECOLOGY_LAYER_URL,
        observation=(
            "All eleven county tenants across search, assessor, treasurer, "
            "appraisal, and sales, with current state retained per tenant and "
            "operation; ordinary disclaimer transitions remain session flow"
        ),
        expected_requests=66,
        sentinel_record_count=11,
        sample_bytes=None,
        handler=probe_washington_taxsifter,
    ),
    **{
        tenant.source_id: ProbeHandlerSpec(
            source_id=tenant.source_id,
            capability="probe_source",
            endpoint=tenant.portal_root,
            observation=(
                "County-specific search, assessor, treasurer, appraisal, and "
                "sales states, including authoritative empty results, ordinary "
                "disclaimer transitions, and operation-scoped challenges"
            ),
            expected_requests=6,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_washington_taxsifter,
        )
        for tenant in query_washington_taxsifter.TENANTS
    },
    **{
        representation.source_id: ProbeHandlerSpec(
            source_id=representation.source_id,
            capability="probe_source",
            endpoint=representation.layer_url,
            observation=(
                "One representation schema, current total count, and exact "
                "parcel sentinel; current values remain rolling observations"
            ),
            expected_requests=4,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_washington_parcel_representation,
        )
        for representation in query_washington_parcels.REPRESENTATIONS.values()
    },
    query_washington_parcels.FRESHNESS_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_washington_parcels.FRESHNESS_SOURCE_ID,
        capability="probe_source",
        endpoint=query_washington_parcels.FRESHNESS_TABLE_URL,
        observation=(
            "County freshness table schema, current row count, and one "
            "bounded rolling sample"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_washington_parcel_companion,
    ),
    query_washington_parcels.LAND_USE_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_washington_parcels.LAND_USE_SOURCE_ID,
        capability="probe_source",
        endpoint=query_washington_parcels.LAND_USE_TABLE_URL,
        observation=(
            "County land-use vocabulary schema, current row count, and one "
            "bounded rolling sample"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_washington_parcel_companion,
    ),
    query_washington_parcels.LINEAGE_ID: ProbeHandlerSpec(
        source_id=query_washington_parcels.LINEAGE_ID,
        capability="probe_source",
        endpoint=query_washington_parcels.ECOLOGY_LAYER_URL,
        observation=(
            "Ecology, DNR, and optional WISAARD sentinel parity as rolling "
            "same-lineage mirror health rather than corroboration"
        ),
        expected_requests=15,
        sentinel_record_count=3,
        sample_bytes=None,
        handler=probe_washington_parcel_lineage,
    ),
    **{
        component.source_id: ProbeHandlerSpec(
            source_id=component.source_id,
            capability="probe_source",
            endpoint=component.layer_url,
            observation=(
                "One DCGIS component schema, current row count, and exact "
                "SSL or document sentinel; current values remain rolling "
                "observations"
            ),
            expected_requests=3,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_dc_property_component,
        )
        for component in query_dc_property.COMPONENTS.values()
    },
    query_dc_property.LINEAGE_ID: ProbeHandlerSpec(
        source_id=query_dc_property.LINEAGE_ID,
        capability="probe_source",
        endpoint=query_dc_property.SERVICE_URL,
        observation=(
            "All four separately attributable DCGIS component contracts and "
            "their SSL join lineage"
        ),
        expected_requests=12,
        sentinel_record_count=4,
        sample_bytes=None,
        handler=probe_dc_property_lineage,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=(
                query_oregon_washington_case_permits.SOURCES[source_id].base_url or ""
            ),
            observation=(
                "Washington County case, permit, report, or document-route "
                "contract with current counts and native sentinels reported "
                "separately"
            ),
            expected_requests={
                query_oregon_washington_case_permits.CASEFILE_SOURCE_ID: 4,
                query_oregon_washington_case_permits.TAXLOT_ACTIVITY_SOURCE_ID: 1,
                query_oregon_washington_case_permits.BUILDING_SOURCE_ID: 2,
                query_oregon_washington_case_permits.PERMIT_REPORT_SOURCE_ID: 5,
                query_oregon_washington_case_permits.ACCELA_SOURCE_ID: 3,
                query_oregon_washington_case_permits.DOCUMENT_ROUTE_SOURCE_ID: 0,
            }[source_id],
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_washington_case_permit_component,
        )
        for source_id in query_oregon_washington_case_permits.SOURCES
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=component.layer_url,
            observation=(
                "Multnomah County SAIL component schema and exact sentinel, "
                "with current counts and survey image resolution reported "
                "separately"
            ),
            expected_requests=(
                4 if source_id == query_oregon_multnomah_sail.SURVEY_SOURCE_ID else 3
            ),
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_oregon_multnomah_sail_component,
        )
        for source_id, component in query_oregon_multnomah_sail.COMPONENTS.items()
    },
    query_oregon_lincoln_propertyweb.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_oregon_lincoln_propertyweb.SOURCE_ID,
        capability="probe_source",
        endpoint=query_oregon_lincoln_propertyweb.HOME_URL,
        observation=(
            "PropertyWeb Home, JSON search, and account-detail contracts, "
            "with current tax year, result count, and sentinel account state "
            "reported separately"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_oregon_lincoln_propertyweb,
    ),
    query_oregon_lincoln_taxlots.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_oregon_lincoln_taxlots.SOURCE_ID,
        capability="probe_source",
        endpoint=query_oregon_lincoln_taxlots.MAPSERVER_URL,
        observation=(
            "WFS 2.0 identity, schema, paging, sorting, and CRS contract, "
            "with current feature count and exact sentinel state reported "
            "separately"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_oregon_lincoln_taxlots,
    ),
    "us-fl-acis": ProbeHandlerSpec(
        source_id="us-fl-acis",
        capability="probe_source",
        endpoint=FLORIDA_ACIS_CALENDAR_URL,
        observation=(
            "Seven-court identity, calendar-session taxonomy, and one exact-date "
            "calendar event with its attached case hearings"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_florida_acis,
    ),
    "us-fl-miami-dade-official-records-public": ProbeHandlerSpec(
        source_id="us-fl-miami-dade-official-records-public",
        capability="list_document_types",
        endpoint=MIAMI_DADE_DOCUMENT_TYPES_URL,
        observation="Public Official Records document-type vocabulary",
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_miami_dade_recorder_public,
    ),
    "us-fl-miami-dade-property-appraiser": ProbeHandlerSpec(
        source_id="us-fl-miami-dade-property-appraiser",
        capability="fetch_parcel",
        endpoint=MIAMI_DADE_PA_PROXY_URL,
        observation=("One known folio detail lookup and matching parcel-layer query"),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_miami_dade_property,
    ),
    "us-tx-bexar-bcad-property": ProbeHandlerSpec(
        source_id="us-tx-bexar-bcad-property",
        capability="fetch_parcel",
        endpoint=BEXAR_PROPERTY_TABLE_URL,
        observation=(
            "One 1=1 property-summary query ordered by the stable property ID"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_bexar_property,
    ),
    "us-co-denver-parcels": ProbeHandlerSpec(
        source_id="us-co-denver-parcels",
        capability="probe_source",
        endpoint=DENVER_PROPERTY_LAYER_URL,
        observation=(
            "One exact schedule-number parcel with its declared ArcGIS schema"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_denver_property,
    ),
    "us-co-denver-public-trustee-gts": ProbeHandlerSpec(
        source_id="us-co-denver-public-trustee-gts",
        capability="probe_source",
        endpoint=DENVER_FORECLOSURE_SEARCH_URL,
        observation=(
            "GTS search schema, native page, one stable foreclosure detail, "
            "and its public document index"
        ),
        expected_requests=16,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_denver_foreclosures,
    ),
    "us-co-denver-delinquent-real-property-tax-list": ProbeHandlerSpec(
        source_id="us-co-denver-delinquent-real-property-tax-list",
        capability="probe_source",
        endpoint=DENVER_TAX_PUBLICATION_PAGE,
        observation=(
            "Current official XLSX release, transfer evidence, and complete "
            "workbook schema/count inspection"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=DENVER_TAX_SAMPLE_BYTES,
        handler=probe_denver_delinquent_tax,
    ),
    "us-co-appellate-case-law-search": ProbeHandlerSpec(
        source_id="us-co-appellate-case-law-search",
        capability="probe_source",
        endpoint=COLORADO_OPINIONS_ARCHIVE_URL,
        observation=(
            "Historical search and count contracts, one full-text opinion, "
            "and its generated PDF"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_colorado_opinions_archive,
    ),
    "us-co-judicial-appellate-opinion-releases": ProbeHandlerSpec(
        source_id="us-co-judicial-appellate-opinion-releases",
        capability="probe_source",
        endpoint=COLORADO_OPINIONS_RELEASE_URL,
        observation=(
            "Current Supreme opinion records and Court of Appeals release "
            "packets with their source roles kept distinct"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_colorado_opinion_releases,
    ),
    DC_OPINIONS_SOURCE_ID: ProbeHandlerSpec(
        source_id=DC_OPINIONS_SOURCE_ID,
        capability="probe_source",
        endpoint=DC_OPINIONS_URL,
        observation=(
            "Current redesigned opinion/MOJ index and one official opinion "
            "PDF, preserving publication type and full-text state"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_dc_opinions,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=endpoint,
            observation=(
                "Source-native D.C. court calendar representation, schema, "
                "and separately attributable hearing or artifact record shape"
            ),
            expected_requests=(5 if source_id == DC_TODAY_CALENDAR_SOURCE_ID else 1),
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_dc_calendar_component,
        )
        for source_id, endpoint in DC_CALENDAR_PROBE_ENDPOINTS.items()
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=endpoint,
            observation=(
                "Fresno source-native portal, calendar index, tentative-"
                "ruling index, probate sentinel, or combined family contract"
            ),
            expected_requests={
                FRESNO_FAMILY_SOURCE_ID: 8,
                FRESNO_PORTAL_SOURCE_ID: 2,
                FRESNO_CALENDAR_SOURCE_ID: 1,
                FRESNO_RULINGS_SOURCE_ID: 1,
                FRESNO_PROBATE_SOURCE_ID: 2,
            }[source_id],
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_fresno_court_component,
        )
        for source_id, endpoint in FRESNO_PROBE_ENDPOINTS.items()
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=endpoint,
            observation=(
                "Orange County source-native calendar form, current "
                "tentative-ruling directory, or combined family contract"
            ),
            expected_requests=(
                5
                if source_id == query_orange_county_court.SOURCE_FAMILY_ID
                else (
                    2
                    if source_id == query_orange_county_court.CALENDAR_SOURCE_ID
                    else 1
                )
            ),
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_orange_county_court_component,
        )
        for source_id, endpoint in ORANGE_COURT_PROBE_ENDPOINTS.items()
    },
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=endpoint,
            observation=(
                "Riverside source-native current hearing window or complete "
                "tentative-ruling department directory"
            ),
            expected_requests=(
                2 if source_id == query_riverside_court.CALENDAR_SOURCE_ID else 1
            ),
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_riverside_court_component,
        )
        for source_id, endpoint in (RIVERSIDE_COURT_PROBE_ENDPOINTS.items())
    },
    query_qld_ecourts.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_qld_ecourts.SOURCE_ID,
        capability="probe_source",
        endpoint=query_qld_ecourts.DETAIL_URL,
        observation=(
            "Known registry-disambiguated civil file, detail-table schema, "
            "native ceiling contract, and complementary record routes"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_qld_ecourts,
    ),
    query_dc_appellate_cases.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_dc_appellate_cases.SOURCE_ID,
        capability="probe_source",
        endpoint=query_dc_appellate_cases.CASE_SEARCH_URL,
        observation=(
            "Exact appellate case and originating-matter identities, party "
            "and docket schemas, document resolution, filing PDF identity, "
            "and complementary source graph"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_dc_appellate_cases,
    ),
    query_md_public_cases.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_public_cases.SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_public_cases.LANDING_URL,
        observation=(
            "Rolling report discovery, latest PDF artifact, coordinate-aware "
            "case parsing, court coverage, and complementary source graph"
        ),
        expected_requests=3,
        sentinel_record_count=None,
        sample_bytes=None,
        handler=probe_maryland_public_cases,
    ),
    query_md_estate_search.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_estate_search.SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_estate_search.SEARCH_URL,
        observation=(
            "WebForms selectors and refresh marker, county-scoped estate "
            "identity, exact detail parties, docket events, native paging, "
            "and complementary estate/property routes"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_maryland_estates,
    ),
    query_md_estate_notices_claims.NOTICE_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_estate_notices_claims.NOTICE_SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_estate_notices_claims.NOTICE_SEARCH_URL,
        observation=(
            "WebForms filters, full source notice HTML/text, native notice "
            "identity, current result marker, variants, and dynamic paging"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_maryland_estate_notices,
    ),
    query_md_estate_notices_claims.CLAIM_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_estate_notices_claims.CLAIM_SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_estate_notices_claims.CLAIM_SEARCH_URL,
        observation=(
            "Claimant/decedent roles, person/corporation fields, dynamic "
            "paging, exact claim detail, status, flags, and freshness marker"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_maryland_estate_claims,
    ),
    query_md_judgment_liens.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_judgment_liens.SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_judgment_liens.SEARCH_URL,
        observation=(
            "Person/company JSF form schemas, stateful search and pagination, "
            "source-result boundary, exact detail events, and complement graph"
        ),
        expected_requests=7,
        sentinel_record_count=2,
        sample_bytes=None,
        handler=probe_maryland_judgment_liens,
    ),
    query_md_opinions.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_opinions.SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_opinions.REPORTED_INDEX_URL,
        observation=(
            "Reported filing-year and unreported monthly index schemas, "
            "coverage routes, document/case identities, one official PDF, "
            "and separately attributable case-detail complements"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_maryland_opinions,
    ),
    query_md_business_opinions.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_md_business_opinions.SOURCE_ID,
        capability="probe_source",
        endpoint=query_md_business_opinions.CURRENT_URL,
        observation=(
            "Current and closed annual trial-publication table schemas, "
            "publication/case/document identities, exact source omissions and "
            "link anomalies, one official PDF, and separately attributable "
            "case-detail complements"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_maryland_business_opinions,
    ),
    query_michigan_appellate.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_michigan_appellate.SOURCE_ID,
        capability="probe_source",
        endpoint=query_michigan_appellate.SEARCH_PAGE_URL,
        observation=(
            "Page-model options, separately paginated case, opinion, and "
            "order APIs, court/case identity contract, one official PDF, "
            "and complementary trial-record routes"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_michigan_appellate,
    ),
    query_michigan_business_court.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_michigan_business_court.SOURCE_ID,
        capability="probe_source",
        endpoint=query_michigan_business_court.SEARCH_URL,
        observation=(
            "Fixed native page size, total-page continuation, exact facet "
            "values, true-zero response, document/row/case-candidate identity "
            "layers, legacy omissions, and one official PDF"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_michigan_business_court,
    ),
    query_wisconsin_wscca.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_wisconsin_wscca.SOURCE_ID,
        capability="probe_source",
        endpoint=query_wisconsin_wscca.BASE_URL,
        observation=(
            "Exact appellate case identity, public-session validation state, "
            "docket/document counts, per-case RSS route, and complementary "
            "source contract"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_wisconsin_wscca,
    ),
    query_wisconsin_opinions.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_wisconsin_opinions.SOURCE_ID,
        capability="probe_source",
        endpoint=query_wisconsin_opinions.OPINIONS_HOME_URL,
        observation=(
            "Supreme and appellate metadata indexes, full-text search, both "
            "release feeds, official PDF identity, and complement contract"
        ),
        expected_requests=6,
        sentinel_record_count=6,
        sample_bytes=None,
        handler=probe_wisconsin_opinions,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=endpoint,
            observation=(
                "Philadelphia source-native current assessment, annual "
                "history, or deed-description parcel-map sentinel"
            ),
            expected_requests=4,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_philadelphia_property_component,
        )
        for source_id, endpoint in (PHILADELPHIA_PROPERTY_PROBE_ENDPOINTS.items())
    },
    query_wisconsin_parcels.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_wisconsin_parcels.SOURCE_ID,
        capability="probe_source",
        endpoint=query_wisconsin_parcels.LAYER_URL,
        observation=(
            "First ordered row in the current annual release, required "
            "schema, owner-visibility states, and complementary route contract"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_statewide_parcel_source,
    ),
    query_wy_dor_parcels.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_wy_dor_parcels.SOURCE_ID,
        capability="probe_source",
        endpoint=query_wy_dor_parcels.ROOT_APP_URL,
        observation=(
            "Official application item/data agreement, current parcel layer, "
            "schema and paging contracts, statewide count, and one exact "
            "annual parcel occurrence"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_wyoming_dor_statewide_parcels,
    ),
    query_ohio_licking_property.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_licking_property.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_licking_property.LAYER_URL,
        observation=(
            "Official layer schema and identity, complete and null-parcel "
            "occurrence counts, and one exact parcel sentinel"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_ohio_licking_auditor_gis,
    ),
    query_ohio_franklin_sales_gis.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_franklin_sales_gis.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_franklin_sales_gis.LAYER_URL,
        observation=(
            "Stable canonical sale-layer schema, occurrence and business-event "
            "identity, ordered paging, renderer-alias, shared-routing, and "
            "lineage contracts with rolling counts, sale/update ranges, join-"
            "field states, and an exact occurrence reported separately"
        ),
        expected_requests=query_ohio_franklin_sales_gis.PROBE_EXPECTED_REQUESTS,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_ohio_franklin_auditor_sales_gis,
    ),
    query_ohio_statewide_parcels.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_statewide_parcels.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_statewide_parcels.LAYER_URL,
        observation=(
            "Official item and layer identity, required schema, 88-county "
            "inventory, three exact county parcel sentinels, field-presence "
            "contract, and complementary county source roles"
        ),
        expected_requests=8,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_ohio_statewide_parcels,
    ),
    **{
        tenant.source_id: ProbeHandlerSpec(
            source_id=tenant.source_id,
            capability="probe_source",
            endpoint=tenant.base_url,
            observation=(
                "Fixed five-request public calendar, preview, one closed-area "
                "listing page, status update, stable tenant contract, and "
                "separate rolling schedule/status/count/amount observations"
            ),
            expected_requests=5,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_ohio_sheriff_realauction_component,
        )
        for tenant in query_ohio_sheriff_sales.TENANTS.values()
    },
    query_licking_foreclosure_archive.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_licking_foreclosure_archive.SOURCE_ID,
        capability="probe_source",
        endpoint=query_licking_foreclosure_archive.BASE_URL,
        observation=(
            "Fixed four-request year inventory, full-year array, rolling "
            "current subset, exact case, stable archive contract, and "
            "separate rolling schedule/status/count/amount observations"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_licking_foreclosure_archive,
    ),
    query_ohio_pax_recorders.DELAWARE_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_pax_recorders.DELAWARE_SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_pax_recorders.DELAWARE.pax_root,
        observation=(
            "Anonymous disclaimer bootstrap, exact instrument detail, stable "
            "InstrumentReferenceId, image metadata, and a bounded official "
            "PDF sample"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=4096,
        handler=probe_ohio_pax_recorder_component,
    ),
    query_ohio_pax_recorders.LICKING_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_pax_recorders.LICKING_SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_pax_recorders.LICKING.pax_root,
        observation=(
            "PAX entry contract and current account-required discovery state, "
            "with the anonymous exact-instrument and archival alternatives "
            "kept as separate source components"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_ohio_pax_recorder_component,
    ),
    query_ohio_pax_recorders.LICKING_DETAIL_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_pax_recorders.LICKING_DETAIL_SOURCE_ID,
        capability="probe_source",
        endpoint=(
            query_ohio_pax_recorders.LICKING.exact_detail_url_template or ""
        ),
        observation=(
            "Anonymous exact-instrument detail and a bounded official PDF "
            "sample, attributed as an alternate representation of the Licking "
            "PAX instrument identity"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=4096,
        handler=probe_ohio_pax_recorder_component,
    ),
    query_new_jersey_dca_property.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_new_jersey_dca_property.SOURCE_ID,
        capability="probe_source",
        endpoint=query_new_jersey_dca_property.ODATA_URL,
        observation=(
            "Exact 13-digit DCA building-registration sentinel and 10-digit "
            "property relationship; live source fields; operation access; "
            "keyset continuation; regulatory-owner semantics; and six "
            "complementary property routes"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_new_jersey_dca_property,
    ),
    query_michigan_property_directories.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_michigan_property_directories.SOURCE_ID,
        capability="probe_source",
        endpoint=query_michigan_property_directories.DIRECTORY_URL,
        observation=(
            "All 83 county route identities, platform-family and review-flag "
            "distribution, publisher-declared parcel role, destination "
            "signals, and complementary official property routes"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_michigan_property_directory,
    ),
    query_new_jersey_parcels.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_new_jersey_parcels.SOURCE_ID,
        capability="probe_source",
        endpoint=query_new_jersey_parcels.ITEM_API_URL,
        observation=(
            "Exact NJGIN parcel sentinel, resolved item/layer schema, partial "
            "MOD-IV join state, and complementary source contract"
        ),
        expected_requests=7,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_statewide_parcel_source,
    ),
    query_virginia_parcels.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_virginia_parcels.SOURCE_ID,
        capability="probe_source",
        endpoint=query_virginia_parcels.ITEM_API_URL,
        observation=(
            "Official item resolution, required layer schema, exact VGIN_QPID "
            "sentinel, durable and transport identities, statewide count, "
            "locality coverage and freshness, missing county equivalents, "
            "incorporated-town groups, and complementary property routes"
        ),
        expected_requests=18,
        sentinel_record_count=3,
        sample_bytes=None,
        handler=probe_virginia_statewide_parcels,
    ),
    query_va_beach_delinquent_tax.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_va_beach_delinquent_tax.SOURCE_ID,
        capability="probe_source",
        endpoint=query_va_beach_delinquent_tax.ITEM_API_URL,
        observation=(
            "Official item and table identity, required schema, one current "
            "delinquent-tax installment, occurrence and parcel-join keys, "
            "exact cents, daily-snapshot semantics, and complementary routes"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_virginia_beach_delinquent_tax,
    ),
    query_va_general_district.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_va_general_district.SOURCE_ID,
        capability="probe_source",
        endpoint=query_va_general_district.LANDING_URL,
        observation=(
            "All source-published court components; the Arlington component "
            "sentinel; civil and traffic/criminal name, case-number, hearing, "
            "and service/process routes; hearing-type options; native paging; "
            "case identity and publication-state contracts; and complementary "
            "official court, clerk, opinion, and land-record routes"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_virginia_general_district,
    ),
    query_ny_statewide_parcels.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ny_statewide_parcels.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ny_statewide_parcels.LANDING_URL,
        observation=(
            "All-county centroid index, participating-county public polygons, "
            "state-owned parcel subset, exact component join keys, current "
            "counts/releases, public-polygon footprint, and complementary routes"
        ),
        expected_requests=24,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_new_york_statewide_parcels,
    ),
    query_ny_salesweb.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ny_salesweb.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ny_salesweb.LANDING_URL,
        observation=(
            "Live municipality, school, class, and condition references; "
            "one bounded transfer search; exact sale detail; transaction "
            "identity; and the SWIS_PRINT_KEY_ID parcel join"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_new_york_salesweb,
    ),
    query_new_jersey_sr1a.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_new_jersey_sr1a.SOURCE_ID,
        capability="probe_source",
        endpoint=query_new_jersey_sr1a.LANDING_URL,
        observation=(
            "Official release set, newest ZIP transport, fixed-width schema, "
            "stable sale identity, and complementary source contract"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=64,
        handler=probe_new_jersey_sr1a,
    ),
    query_new_jersey_tax_court.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_new_jersey_tax_court.SOURCE_ID,
        capability="probe_source",
        endpoint=query_new_jersey_tax_court.S3_LIST_URL,
        observation=(
            "Anonymous current-report manifest; complete docketed and open XLSX "
            "traversal; accepted header aliases; docket and source-occurrence "
            "identities; duplicate/multi-property rows; and complementary "
            "historical judgment, case-jacket, opinion, parcel, and sale routes"
        ),
        expected_requests=OHIO_FRANKLIN_AUDITOR_BULK_EXPECTED_REQUESTS,
        sentinel_record_count=2,
        sample_bytes=16,
        handler=probe_new_jersey_tax_court,
    ),
    query_new_jersey_tax_court_opinions.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_new_jersey_tax_court_opinions.SOURCE_ID,
        capability="probe_source",
        endpoint=query_new_jersey_tax_court_opinions.PUBLISHED_INDEX_URL,
        observation=(
            "Published and unpublished official opinion-index schemas and "
            "rolling counts; direct publisher and Reader relay operation "
            "states; occurrence, document, and case identities; one document "
            "transport; and seven complementary routes"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_new_jersey_tax_court_opinions,
    ),
    query_palm_beach_official_records.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_palm_beach_official_records.SOURCE_ID,
        capability="probe_source",
        endpoint=query_palm_beach_official_records.HOME_URL,
        observation=(
            "Exact official instrument, portal locator, normalized detail "
            "schema, public image state, broad-search challenge, and "
            "complementary source contract"
        ),
        expected_requests=9,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_palm_beach_official_records,
    ),
    "us-co-judicial-data-reports": ProbeHandlerSpec(
        source_id="us-co-judicial-data-reports",
        capability="probe_source",
        endpoint=COLORADO_COURT_DATA_URL,
        observation=(
            "Complete official report and request-workflow catalog, the "
            "Addendum A PDF, and the public eviction-dashboard shell"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_colorado_court_data,
    ),
    "us-co-judicial-docket-search": ProbeHandlerSpec(
        source_id="us-co-judicial-docket-search",
        capability="probe_source",
        endpoint=COLORADO_JUDICIAL_DOCKET_URL,
        observation=(
            "Statewide docket directory, one current search, native paging, "
            "and export availability"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_colorado_judicial,
    ),
    "us-co-denver-county-court-public-docket": ProbeHandlerSpec(
        source_id="us-co-denver-county-court-public-docket",
        capability="probe_source",
        endpoint=DENVER_COUNTY_COURT_DOCKET_URL,
        observation=("Courtroom vocabulary and one daily-docket result-table contract"),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_denver_county_court,
    ),
    "us-de-firstmap-parcels": ProbeHandlerSpec(
        source_id="us-de-firstmap-parcels",
        capability="probe_source",
        endpoint=DELAWARE_FIRSTMAP_SERVICE_URL,
        observation=(
            "One exact PIN joined across the parcel-polygon and centroid layers"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_delaware_firstmap,
    ),
    "us-va-arlington-property-map": ProbeHandlerSpec(
        source_id="us-va-arlington-property-map",
        capability="probe_source",
        endpoint=ARLINGTON_PROPERTY_LAYER_URL,
        observation=("One exact RPC from the rich county property-map layer"),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_arlington_property,
    ),
    "us-tx-bexar-district-historical-cases": ProbeHandlerSpec(
        source_id="us-tx-bexar-district-historical-cases",
        capability="probe_source",
        endpoint=BEXAR_HISTORICAL_WEBSOCKET_URL,
        observation=(
            "Anonymous tenant bootstrap, one 1919 search row, and its exact "
            "case-file detail"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_bexar_historical_courts,
    ),
    "us-tx-harris-clerk-real-property": ProbeHandlerSpec(
        source_id="us-tx-harris-clerk-real-property",
        capability="probe_source",
        endpoint=HARRIS_RECORDER_SEARCH_URL,
        observation=(
            "Exact anonymous instrument-index row, registered-image access "
            "boundary, and official bulk-product markers"
        ),
        expected_requests=5,
        sentinel_record_count=3,
        sample_bytes=None,
        handler=probe_harris_recorder,
    ),
    "us-tx-harris-clerk-foreclosures": ProbeHandlerSpec(
        source_id="us-tx-harris-clerk-foreclosures",
        capability="probe_source",
        endpoint=HARRIS_FORECLOSURE_SEARCH_URL,
        observation=(
            "Exact anonymous foreclosure-notice row and its official public PDF"
        ),
        expected_requests=3,
        sentinel_record_count=2,
        sample_bytes=None,
        handler=probe_harris_foreclosures,
    ),
    "us-tx-harris-district-clerk-public-datasets": ProbeHandlerSpec(
        source_id="us-tx-harris-district-clerk-public-datasets",
        capability="probe_source",
        endpoint=HARRIS_COURT_BULK_CATALOG_URL,
        observation=(
            "Stable artifact, row-identity, and parser contracts plus a "
            "complete rolling catalog and 4 KiB field-code sample"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=HARRIS_COURT_BULK_SAMPLE_BYTES,
        handler=probe_harris_court_bulk,
    ),
    "us-tx-appellate-tames": ProbeHandlerSpec(
        source_id="us-tx-appellate-tames",
        capability="probe_source",
        endpoint=TEXAS_TAMES_SEARCH_URL,
        observation=(
            "Statewide search-form vocabulary, exact appellate case, and "
            "one stable public PDF"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_texas_tames,
    ),
    query_texas_supreme_publications.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_texas_supreme_publications.SOURCE_ID,
        capability="probe_source",
        endpoint=query_texas_supreme_publications.LANDING_URL,
        observation=(
            "Stable annual-index, release-row, document-type, identity, and "
            "complement contracts, with landing, annual, release, and PDF "
            "hashes reported as rolling observations"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_texas_supreme_publications,
    ),
    "us-pa-ujs-public-dockets": ProbeHandlerSpec(
        source_id="us-pa-ujs-public-dockets",
        capability="probe_source",
        endpoint=PA_UJS_CASE_SEARCH_URL,
        observation=(
            "Known Common Pleas and appellate dockets with official report links"
        ),
        expected_requests=4,
        sentinel_record_count=2,
        sample_bytes=None,
        handler=probe_pa_ujs,
    ),
    "us-pa-appellate-opinions-postings": ProbeHandlerSpec(
        source_id="us-pa-appellate-opinions-postings",
        capability="probe_source",
        endpoint=PA_OPINIONS_API_URL,
        observation=("Exact Supreme Court docket posting and its official public PDF"),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_pa_opinions,
    ),
    "us-de-courtconnect": ProbeHandlerSpec(
        source_id="us-de-courtconnect",
        capability="probe_source",
        endpoint=DELAWARE_COURTCONNECT_URL,
        observation=(
            "Known Justice of the Peace full docket and Court of Chancery "
            "stub through the public disclaimer flow"
        ),
        expected_requests=4,
        sentinel_record_count=2,
        sample_bytes=None,
        handler=probe_delaware_courtconnect,
    ),
    "us-de-opinions-orders": ProbeHandlerSpec(
        source_id="us-de-opinions-orders",
        capability="probe_source",
        endpoint=DELAWARE_OPINIONS_URL,
        observation=("Exact opinion/order archive row and its official public PDF"),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_delaware_opinions,
    ),
    "us-tx-reeves-county-clerk-official-records": ProbeHandlerSpec(
        source_id="us-tx-reeves-county-clerk-official-records",
        capability="probe_source",
        endpoint=REEVES_RECORDS_WEBSOCKET_URL,
        observation=(
            "Anonymous tenant bootstrap, exact recorded-instrument search, "
            "and its detail record"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_reeves_records,
    ),
    **{
        source_id: ProbeHandlerSpec(
            source_id=source_id,
            capability="probe_source",
            endpoint=tenant.websocket_url,
            observation=(
                "Anonymous tenant bootstrap, exact instrument search, "
                "detail record, and stable first-page image"
            ),
            expected_requests=6,
            sentinel_record_count=1,
            sample_bytes=None,
            handler=probe_govos_recorder,
        )
        for source_id, tenant in GOVOS_RECORDER_TENANTS.items()
    },
    "us-tx-rrc-p4-bulk": ProbeHandlerSpec(
        source_id="us-tx-rrc-p4-bulk",
        capability="probe_source",
        endpoint=TEXAS_RRC_SHARE_URLS["p4"],
        observation="Official P-4 bulk-share listing and preferred release",
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_texas_rrc_release,
    ),
    "us-tx-rrc-p5-bulk": ProbeHandlerSpec(
        source_id="us-tx-rrc-p5-bulk",
        capability="probe_source",
        endpoint=TEXAS_RRC_SHARE_URLS["p5"],
        observation="Official P-5 bulk-share listing and preferred release",
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_texas_rrc_release,
    ),
    "us-tx-rrc-wellbore-bulk": ProbeHandlerSpec(
        source_id="us-tx-rrc-wellbore-bulk",
        capability="probe_source",
        endpoint=TEXAS_RRC_SHARE_URLS["wellbore"],
        observation=(
            "Official Wellbore bulk-share archive and preferred dated release"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_texas_rrc_release,
    ),
    "us-fl-orange-county-hearing-calendar": ProbeHandlerSpec(
        source_id="us-fl-orange-county-hearing-calendar",
        capability="probe_source",
        endpoint=ORANGE_CALENDAR_URL,
        observation=(
            "Tokenized hearing-calendar form and complete current-day "
            "seven-column result table"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_orange_hearing_calendar,
    ),
    query_los_angeles_ttc.ASSESSOR_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_los_angeles_ttc.ASSESSOR_SOURCE_ID,
        capability="probe_source",
        endpoint=query_los_angeles_ttc.ASSESSOR_QUERY_URL,
        observation=(
            "One exact AIN against the official Assessor parcel-routing layer"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_los_angeles_assessor_ain,
    ),
    query_los_angeles_ttc.PAYMENT_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_los_angeles_ttc.PAYMENT_SOURCE_ID,
        capability="probe_source",
        endpoint=query_los_angeles_ttc.PAYMENT_HISTORY_URL,
        observation=(
            "Same-session TTC bootstrap plus positive and structured-empty "
            "payment-history pages"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_los_angeles_ttc_payment,
    ),
    query_los_angeles_ttc.SALE_SOURCE_ID: ProbeHandlerSpec(
        source_id=query_los_angeles_ttc.SALE_SOURCE_ID,
        capability="probe_source",
        endpoint=query_los_angeles_ttc.AUCTION_SCHEDULE_URL,
        observation=(
            "Current auction schedule, publication index, and one official "
            "sale-result PDF representation"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_los_angeles_ttc_sale,
    ),
    LOS_ANGELES_CIVIL_SOURCE_ID: ProbeHandlerSpec(
        source_id=LOS_ANGELES_CIVIL_SOURCE_ID,
        capability="probe_source",
        endpoint=LOS_ANGELES_CIVIL_CASE_SEARCH_URL,
        observation=(
            "Exact civil Case Summary plus the current tentative-ruling "
            "selection and full-text contracts"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_los_angeles_civil,
    ),
    query_los_angeles_name_index.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_los_angeles_name_index.SOURCE_ID,
        capability="probe_source",
        endpoint=query_los_angeles_name_index.CIVIL_INDEX_URL,
        observation=(
            "Coverage, fees, name-search form, guest receipt recovery, and "
            "result-field contracts"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_los_angeles_name_index,
    ),
    "us-ca-los-angeles-superior-probate": ProbeHandlerSpec(
        source_id="us-ca-los-angeles-superior-probate",
        capability="probe_source",
        endpoint=LOS_ANGELES_PROBATE_CASE_SEARCH_URL,
        observation=(
            "Known closed probate case across the tokenized Case Summary "
            "contract, Probate Notes form, and direct Case Calendar"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_los_angeles_probate,
    ),
    "us-ca-san-mateo-midx": ProbeHandlerSpec(
        source_id="us-ca-san-mateo-midx",
        capability="probe_source",
        endpoint=SAN_MATEO_MIDX_URL,
        observation=("Known case through the anonymous tokenized MIDX browser form"),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_san_mateo_midx,
    ),
    "us-ny-law-reporting-bureau": ProbeHandlerSpec(
        source_id="us-ny-law-reporting-bureau",
        capability="probe_source",
        endpoint=f"{NY_LAW_REPORTS_BASE_URL}/reporter/",
        observation=(
            "Both official decision collections, their current and archive "
            "indexes, and one exact full-text opinion"
        ),
        expected_requests=7,
        sentinel_record_count=7,
        sample_bytes=None,
        handler=probe_ny_law_reports,
    ),
    "us-ny-public-notices-column": ProbeHandlerSpec(
        source_id="us-ny-public-notices-column",
        capability="probe_source",
        endpoint=NY_COLUMN_PORTAL_URL,
        observation=(
            "One exact partitioned notice plus the source's displayed "
            "10,000-result ceiling"
        ),
        expected_requests=2,
        sentinel_record_count=2,
        sample_bytes=None,
        handler=probe_ny_column,
    ),
    query_ny_attorneys.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ny_attorneys.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ny_attorneys.QUERY_URL,
        observation=(
            "Official dataset metadata, statewide and sentinel counts, one "
            "exact registration, and final metadata, with current totals, "
            "freshness, and record contents reported separately"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_ny_oca_attorney_registrations,
    ),
    "us-fl-palm-beach-ecaseview": ProbeHandlerSpec(
        source_id="us-fl-palm-beach-ecaseview",
        capability="probe_source",
        endpoint=PALM_BEACH_ECASEVIEW_URL,
        observation=(
            "One headed public guest session with visible case-number and "
            "party/company search controls"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_palm_beach_courts,
    ),
    "us-az-pima-superior-agave": ProbeHandlerSpec(
        source_id="us-az-pima-superior-agave",
        capability="probe_source",
        endpoint=PIMA_PUBLICDOCS_URL,
        observation=(
            "PublicDocs landing frame and stable ASP.NET search-form contract"
        ),
        expected_requests=2,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_pima_courts,
    ),
    query_ohio_franklin_courts.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_franklin_courts.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_franklin_courts.BASE_URL,
        observation=(
            "Fixed five-request disclaimer, party-index, exact-case, "
            "initial-docket, and first-continuation contract"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_franklin_cio,
    ),
    query_ohio_franklin_municipal.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_franklin_municipal.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_franklin_municipal.SEARCH_URL,
        observation=(
            "Fixed five-request search form, person index, exact case, "
            "case detail, and generated-summary contract"
        ),
        expected_requests=query_ohio_franklin_municipal.PROBE_REQUEST_COUNT,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_franklin_municipal,
    ),
    query_ohio_delaware_common_pleas.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_delaware_common_pleas.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_delaware_common_pleas.HOME_URL,
        observation=(
            "One headed helper invocation reporting either the rendered "
            "CourtView search contract or its visible challenge state"
        ),
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_delaware_ohio_common_pleas,
    ),
    query_ohio_licking_common_pleas.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_licking_common_pleas.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_licking_common_pleas.OFFICIAL_LANDING_URL,
        observation=(
            "Fixed six-request county landing, Tyler shell, and anonymous "
            "re:SearchOH application, claims, subscription, and county contract"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_licking_common_pleas,
    ),
    query_ohio_franklin_probate.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_franklin_probate.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_franklin_probate.LANDING_URL,
        observation=(
            "Fixed seven-request landing, exact-case, docket, fiduciary, "
            "and person-detail contract"
        ),
        expected_requests=7,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_franklin_probate,
    ),
    query_ohio_franklin_auditor_bulk.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_franklin_auditor_bulk.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_franklin_auditor_bulk.DIRECTORY_ROOT,
        observation=(
            "Required Auditor directories, all five current release families, "
            "and one bounded daily-workbook sample"
        ),
        expected_requests=9,
        sentinel_record_count=1,
        sample_bytes=64,
        handler=probe_ohio_franklin_auditor_bulk,
    ),
    query_ohio_reporter_decisions.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_reporter_decisions.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_reporter_decisions.BASE_URL,
        observation=(
            "Fixed three-request Reporter landing and exact-WebCite contract "
            "without downloading the publication PDF"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_ohio_reporter_decisions,
    ),
    query_connecticut_civil_family.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_connecticut_civil_family.SOURCE_ID,
        capability="probe_source",
        endpoint=query_connecticut_civil_family.BASE_URL,
        observation=(
            "Fixed five-request party display, exact docket, transfer-history, "
            "notice, and no-download DocumentNo metadata contract"
        ),
        expected_requests=(
            query_connecticut_civil_family.PROBE_EXPECTED_REQUESTS
        ),
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_connecticut_civil_family,
    ),
    query_new_mexico_case_lookup.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_new_mexico_case_lookup.SOURCE_ID,
        capability="probe_source",
        endpoint=query_new_mexico_case_lookup.BASE_URL,
        observation=(
            "Fixed four-request disclaimer, acceptance, case-number form, "
            "and caller-selected exact historical-case contract"
        ),
        expected_requests=query_new_mexico_case_lookup.PROBE_EXPECTED_REQUESTS,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_new_mexico_case_lookup,
    ),
    query_ohio_supreme_court.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_ohio_supreme_court.SOURCE_ID,
        capability="probe_source",
        endpoint=query_ohio_supreme_court.BASE_URL,
        observation=(
            "Fixed five-request eCMS landing, application token, caption "
            "search, exact-case, and rolling recent-filings contract"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_ohio_supreme_court,
    ),
    "us-tax-court-dawson": ProbeHandlerSpec(
        source_id="us-tax-court-dawson",
        capability="probe_source",
        endpoint=f"{TAX_COURT_API_ROOT}/public-api/health",
        observation=(
            "Official DAWSON public API health and stable two-docket "
            "petitioner-search sentinel"
        ),
        expected_requests=2,
        sentinel_record_count=2,
        sample_bytes=None,
        handler=probe_tax_court_dawson,
    ),
    "us-vi-c-track": ProbeHandlerSpec(
        source_id="us-vi-c-track",
        capability="probe_source",
        endpoint=VICOURTS_INFO_URL,
        observation=(
            "C-Track info and directory, exact probate case, OCR document "
            "and publication sentinels, plus one validated legacy PDF"
        ),
        expected_requests=6,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_vicourts,
    ),
    "us-nc-onemap-parcels": ProbeHandlerSpec(
        source_id="us-nc-onemap-parcels",
        capability="fetch_parcel",
        endpoint=NC_ONEMAP_LAYER_URL,
        observation="One 1=1 feature query with declared fields and no geometry",
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_nc_onemap,
    ),
    "us-la-orleans-property-viewer": ProbeHandlerSpec(
        source_id="us-la-orleans-property-viewer",
        capability="fetch_account",
        endpoint=ORLEANS_PROPERTY_QUERY_URL,
        observation=(
            "One stable GeoPIN row, max LASTUPDATE, locator result, and "
            "deployed Property Viewer parcel-layer schema"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_orleans_property,
    ),
    query_fl_dor_property.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_fl_dor_property.SOURCE_ID,
        capability="probe_source",
        endpoint=query_fl_dor_property.SOURCE_PAGE,
        observation=(
            "Current NAL, SDF, and GIS-PIN directory and manifest contracts, "
            "67-county coverage observations, and one Baker NAL ZIP sentinel"
        ),
        expected_requests=9,
        sentinel_record_count=3,
        sample_bytes=4096,
        handler=probe_fl_dor_property,
    ),
    query_harris_property.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_harris_property.SOURCE_ID,
        capability="probe_source",
        endpoint=query_harris_property.SOURCE_PAGE,
        observation=(
            "Current HCAD CAMA tax year and certification, exact five-file "
            "real-property manifest, and one Real_acct_owner.zip sentinel"
        ),
        expected_requests=5,
        sentinel_record_count=1,
        sample_bytes=4096,
        handler=probe_hcad_property,
    ),
    query_hcad_gis.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_hcad_gis.SOURCE_ID,
        capability="probe_source",
        endpoint=query_hcad_gis.SOURCE_PAGE,
        observation=(
            "Current and historical HCAD GIS manifests, one Parcels.zip "
            "sentinel, and the distinct county MapServer schema, count, "
            "tax-year values, and feature sentinel"
        ),
        expected_requests=10,
        sentinel_record_count=1,
        sample_bytes=4096,
        handler=probe_hcad_gis,
    ),
    query_txgio_land_parcels.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_txgio_land_parcels.SOURCE_ID,
        capability="probe_source",
        endpoint=query_txgio_land_parcels.LANDING_URL,
        observation=(
            "Current TxGIO collection and mixed county/state resource "
            "inventory plus one smallest-county ZIP sentinel"
        ),
        expected_requests=4,
        sentinel_record_count=1,
        sample_bytes=4096,
        handler=probe_txgio_land_parcels,
    ),
    query_montana_cadastral.SOURCE_ID: ProbeHandlerSpec(
        source_id=query_montana_cadastral.SOURCE_ID,
        capability="probe_source",
        endpoint=query_montana_cadastral.LAYER_URL,
        observation=(
            "One geometry-bearing parcel feature, the live schema and nullable "
            "PARCELID counts, all 56 ORION-to-Census county groups, and the "
            "current 56-county parcel and ORION bulk inventories"
        ),
        expected_requests=15,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_montana_cadastral,
    ),
    "us-ma-massgis-parcels": ProbeHandlerSpec(
        source_id="us-ma-massgis-parcels",
        capability="probe",
        endpoint=MASSGIS_MANIFEST_LAYER_URL,
        observation=("One Gosnold manifest row, artifact HEAD, and leading byte range"),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=4096,
        handler=probe_massgis,
    ),
}


def registered_handlers(
    handlers: Mapping[str, ProbeHandlerSpec] | None = None,
) -> list[dict[str, Any]]:
    """Return the complete visible handler registry."""
    active = handlers if handlers is not None else HANDLER_REGISTRY
    return [active[source_id].to_dict() for source_id in sorted(active)]


def compare_probes(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare status and schema/artifact fingerprints between two probes."""
    if previous is None:
        return {
            "baseline": True,
            "drift_detected": False,
            "previous_probe_id": None,
            "current_probe_id": current.get("probe_id"),
            "changes": {},
        }
    fields = ("status", "schema_sha256", "artifact_sha256")
    changes = {
        field_name: {
            "previous": previous.get(field_name),
            "current": current.get(field_name),
            "changed": previous.get(field_name) != current.get(field_name),
        }
        for field_name in fields
    }
    return {
        "baseline": False,
        "drift_detected": any(change["changed"] for change in changes.values()),
        "previous_probe_id": previous.get("probe_id"),
        "current_probe_id": current.get("probe_id"),
        "changes": changes,
    }


def _decision_status(decision: Mapping[str, Any]) -> str:
    return acquisition_result_status(decision)


def _exception_observation(
    error: BaseException,
    *,
    endpoint: str,
    latency_ms: float,
) -> ProbeObservation:
    if isinstance(error, PublicRecordsHTTPError):
        return ProbeObservation(
            status=error.result_status.value,
            endpoint=endpoint,
            latency_ms=latency_ms,
            details={"error": error.to_contract_error().to_dict()},
            error=str(error),
        )
    if isinstance(error, BulkSourceError):
        return ProbeObservation(
            status=error.result_status.value,
            endpoint=endpoint,
            latency_ms=latency_ms,
            details={"error": error.to_contract_error().to_dict()},
            error=str(error),
        )
    if isinstance(error, query_orange_tax_collector.OrangeTaxError):
        return ProbeObservation(
            status=error.status.value,
            endpoint=endpoint,
            latency_ms=latency_ms,
            details={"error": error.to_contract_error().to_dict()},
            error=str(error),
        )
    if isinstance(error, KofilePublicSearchError):
        if isinstance(error, KofileAccessError):
            status = ResultStatus.RESTRICTED
        elif isinstance(error, KofileRateLimitError):
            status = ResultStatus.RATE_LIMITED
        elif isinstance(
            error,
            (KofileSourceChangedError, KofileNotFoundError),
        ):
            status = ResultStatus.SOURCE_CHANGED
        else:
            status = ResultStatus.UNAVAILABLE
        return ProbeObservation(
            status=status.value,
            endpoint=endpoint,
            latency_ms=latency_ms,
            details={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "category": (
                        "access"
                        if status == ResultStatus.RESTRICTED
                        else (
                            "rate_limit"
                            if status == ResultStatus.RATE_LIMITED
                            else (
                                "source_schema"
                                if status == ResultStatus.SOURCE_CHANGED
                                else "transport"
                            )
                        )
                    ),
                    "retryable": error.retryable,
                    "details": error.details,
                }
            },
            error=str(error),
        )
    return ProbeObservation(
        status=ResultStatus.UNAVAILABLE.value,
        endpoint=endpoint,
        latency_ms=latency_ms,
        details={"exception_type": type(error).__name__},
        error=str(error) or type(error).__name__,
    )


def _record_observation(
    catalog: PublicRecordsCatalog,
    source_id: str,
    observation: ProbeObservation,
    *,
    probed_by: str,
    probed_at: str | None,
    probe_kind: str,
    capability: str | None,
    details: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous_rows = catalog.probe_history(source_id)
    previous = previous_rows[0] if previous_rows else None
    recorded = catalog.record_probe(
        source_id,
        status=observation.status,
        probed_by=probed_by,
        probed_at=probed_at,
        probe_kind=probe_kind,
        capability=capability,
        endpoint=observation.endpoint,
        http_status=observation.http_status,
        latency_ms=observation.latency_ms,
        schema_sha256=observation.schema_sha256,
        artifact_sha256=observation.artifact_sha256,
        result_count=observation.result_count,
        details=_json_ready(details),
        error=observation.error,
    )
    current_rows = catalog.probe_history(
        source_id,
        probe_ids=[recorded["probe_id"]],
    )
    current = current_rows[0]
    return current, compare_probes(previous, current)


def plan_sources(
    catalog: PublicRecordsCatalog,
    source_ids: Sequence[str] | None = None,
    *,
    handlers: Mapping[str, ProbeHandlerSpec] | None = None,
) -> dict[str, Any]:
    """Describe catalog decisions and registered handlers without probing."""
    active_handlers = handlers if handlers is not None else HANDLER_REGISTRY
    selected_ids = (
        list(source_ids)
        if source_ids
        else [row["source_id"] for row in catalog.list_sources()]
    )
    sources: list[dict[str, Any]] = []
    for source_id in selected_ids:
        try:
            decision = catalog.machine_acquisition_decision(source_id)
            handler = active_handlers.get(source_id)
            if decision["allowed"] and handler is not None:
                mode = "registered_probe"
            elif decision["allowed"]:
                mode = "no_registered_handler"
            else:
                mode = "catalog_decision"
            sources.append(
                {
                    "source_id": source_id,
                    "mode": mode,
                    "catalog_decision": decision,
                    "handler": handler.to_dict() if handler else None,
                }
            )
        except CatalogError as error:
            sources.append(
                {
                    "source_id": source_id,
                    "mode": "catalog_error",
                    "catalog_decision": None,
                    "handler": None,
                    "error": str(error),
                }
            )
    return {
        "command": "plan",
        "handler_registry": registered_handlers(active_handlers),
        "sources": sources,
    }


def run_sources(
    catalog: PublicRecordsCatalog,
    source_ids: Sequence[str],
    *,
    probed_by: str = MONITOR_ACTOR,
    probed_at: str | None = None,
    timeout: float = 30.0,
    max_attempts: int = 3,
    handlers: Mapping[str, ProbeHandlerSpec] | None = None,
) -> dict[str, Any]:
    """Run and record probes only for the explicitly supplied source IDs."""
    if not source_ids:
        raise ValueError("run requires at least one explicit source ID")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    active_handlers = handlers if handlers is not None else HANDLER_REGISTRY
    results: list[dict[str, Any]] = []

    for source_id in source_ids:
        try:
            decision = catalog.machine_acquisition_decision(source_id)
        except CatalogError as error:
            results.append(
                {
                    "source_id": source_id,
                    "catalog_decision": None,
                    "handler": None,
                    "dispatched": False,
                    "recorded": False,
                    "status": "error",
                    "error": str(error),
                }
            )
            continue

        handler_spec = active_handlers.get(source_id)
        if not decision["allowed"]:
            observation = ProbeObservation(
                status=_decision_status(decision),
                endpoint=catalog.show_source(source_id)["source"]["official_url"],
                details={"catalog_decision": decision},
                error=str(decision["reason"]),
            )
            current, drift = _record_observation(
                catalog,
                source_id,
                observation,
                probed_by=probed_by,
                probed_at=probed_at,
                probe_kind="sentinel",
                capability=handler_spec.capability if handler_spec else None,
                details={
                    **observation.details,
                    "handler": handler_spec.to_dict() if handler_spec else None,
                    "dispatched": False,
                },
            )
            results.append(
                {
                    "source_id": source_id,
                    "catalog_decision": decision,
                    "handler": handler_spec.to_dict() if handler_spec else None,
                    "dispatched": False,
                    "recorded": True,
                    "probe": current,
                    "drift": drift,
                }
            )
            continue

        if handler_spec is None:
            results.append(
                {
                    "source_id": source_id,
                    "catalog_decision": decision,
                    "handler": None,
                    "dispatched": False,
                    "recorded": False,
                    "status": "error",
                    "error": "No registered low-cost probe handler for this source",
                }
            )
            continue

        context = ProbeContext(
            source_id=source_id,
            catalog_decision=decision,
            timeout=timeout,
            max_attempts=max_attempts,
            sample_bytes=handler_spec.sample_bytes,
        )
        started = time.perf_counter()
        try:
            observation = handler_spec.handler(context)
            if observation.latency_ms is None:
                observation = replace(
                    observation,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
        except Exception as error:
            observation = _exception_observation(
                error,
                endpoint=handler_spec.endpoint,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        details = {
            **observation.details,
            "catalog_decision": decision,
            "handler": handler_spec.to_dict(),
            "dispatched": True,
        }
        current, drift = _record_observation(
            catalog,
            source_id,
            observation,
            probed_by=probed_by,
            probed_at=probed_at,
            probe_kind="sentinel",
            capability=handler_spec.capability,
            details=details,
        )
        results.append(
            {
                "source_id": source_id,
                "catalog_decision": decision,
                "handler": handler_spec.to_dict(),
                "dispatched": True,
                "recorded": True,
                "probe": current,
                "drift": drift,
            }
        )

    return {
        "command": "run",
        "requested_source_ids": list(source_ids),
        "handler_registry": registered_handlers(active_handlers),
        "results": results,
    }


def record_observation(
    catalog: PublicRecordsCatalog,
    source_id: str,
    observation: ProbeObservation,
    *,
    probed_by: str,
    probed_at: str | None = None,
    probe_kind: str = "sentinel",
    capability: str | None = None,
) -> dict[str, Any]:
    """Append an explicitly supplied observation and show resulting drift."""
    decision = catalog.machine_acquisition_decision(source_id)
    current, drift = _record_observation(
        catalog,
        source_id,
        observation,
        probed_by=probed_by,
        probed_at=probed_at,
        probe_kind=probe_kind,
        capability=capability,
        details=observation.details,
    )
    return {
        "command": "record",
        "source_id": source_id,
        "catalog_decision": decision,
        "probe": current,
        "drift": drift,
    }


def history(
    catalog: PublicRecordsCatalog,
    source_id: str,
) -> dict[str, Any]:
    """Return the full immutable probe history for a source."""
    return {
        "command": "history",
        "source_id": source_id,
        "catalog_decision": catalog.machine_acquisition_decision(source_id),
        "probes": catalog.probe_history(source_id),
    }


def diff_history(
    catalog: PublicRecordsCatalog,
    source_id: str,
    *,
    from_probe_id: int | None = None,
    to_probe_id: int | None = None,
) -> dict[str, Any]:
    """Compare two exact probes, or the newest two when IDs are omitted."""
    if (from_probe_id is None) != (to_probe_id is None):
        raise ValueError("from_probe_id and to_probe_id must be supplied together")
    if from_probe_id is None:
        probes = catalog.probe_history(source_id)
        current = probes[0] if probes else None
        previous = probes[1] if len(probes) > 1 else None
    else:
        probes = catalog.probe_history(
            source_id,
            probe_ids=[from_probe_id, to_probe_id],
        )
        by_id = {probe["probe_id"]: probe for probe in probes}
        missing = [
            probe_id
            for probe_id in (from_probe_id, to_probe_id)
            if probe_id not in by_id
        ]
        if missing:
            raise CatalogError(
                f"probe IDs do not belong to {source_id}: "
                + ", ".join(str(probe_id) for probe_id in missing)
            )
        previous = by_id[from_probe_id]
        current = by_id[to_probe_id]
    if current is None:
        comparison = None
    else:
        comparison = compare_probes(previous, current)
    return {
        "command": "diff",
        "source_id": source_id,
        "catalog_decision": catalog.machine_acquisition_decision(source_id),
        "comparison": comparison,
    }


def _parse_details(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    if value.startswith("@"):
        raw = Path(value[1:]).read_text(encoding="utf-8")
    else:
        raw = value
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("details must be a JSON object")
    return data


def _add_output(parser: argparse.ArgumentParser) -> None:
    add_output_args(parser)


def _add_subcommand_db(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default=argparse.SUPPRESS,
        help="Public-records catalog database (also accepted before the command)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan, run, record, and compare public-record source probes"
    )
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Show catalog decisions and probe handlers")
    plan.add_argument("source_ids", nargs="*")
    _add_subcommand_db(plan)
    _add_output(plan)

    run = sub.add_parser("run", help="Run explicitly named source probes")
    run.add_argument("source_ids", nargs="+")
    _add_subcommand_db(run)
    run.add_argument("--probed-by", default=MONITOR_ACTOR)
    run.add_argument("--probed-at")
    run.add_argument("--timeout", type=float, default=30.0)
    run.add_argument("--max-attempts", type=int, default=3)
    _add_output(run)

    record = sub.add_parser("record", help="Append an explicit probe observation")
    record.add_argument("source_id")
    _add_subcommand_db(record)
    record.add_argument("--status", required=True, choices=sorted(PROBE_STATUSES))
    record.add_argument("--probed-by", required=True)
    record.add_argument("--probed-at")
    record.add_argument("--kind", default="sentinel")
    record.add_argument("--capability")
    record.add_argument("--endpoint")
    record.add_argument("--http-status", type=int)
    record.add_argument("--latency-ms", type=float)
    record.add_argument("--schema-sha256")
    record.add_argument("--artifact-sha256")
    record.add_argument("--result-count", type=int)
    record.add_argument("--details", help="JSON object or @file")
    record.add_argument("--error")
    _add_output(record)

    diff = sub.add_parser("diff", help="Compare schema, artifact, and status")
    diff.add_argument("source_id")
    _add_subcommand_db(diff)
    diff.add_argument("--from-probe-id", type=int)
    diff.add_argument("--to-probe-id", type=int)
    _add_output(diff)

    history_parser = sub.add_parser(
        "history",
        help="Return the complete immutable probe history",
    )
    history_parser.add_argument("source_id")
    _add_subcommand_db(history_parser)
    _add_output(history_parser)
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    catalog = PublicRecordsCatalog(args.db)
    if args.command == "plan":
        return plan_sources(catalog, args.source_ids)
    if args.command == "run":
        return run_sources(
            catalog,
            args.source_ids,
            probed_by=args.probed_by,
            probed_at=args.probed_at,
            timeout=args.timeout,
            max_attempts=args.max_attempts,
        )
    if args.command == "record":
        return record_observation(
            catalog,
            args.source_id,
            ProbeObservation(
                status=args.status,
                endpoint=args.endpoint,
                http_status=args.http_status,
                latency_ms=args.latency_ms,
                schema_sha256=args.schema_sha256,
                artifact_sha256=args.artifact_sha256,
                result_count=args.result_count,
                details=_parse_details(args.details),
                error=args.error,
            ),
            probed_by=args.probed_by,
            probed_at=args.probed_at,
            probe_kind=args.kind,
            capability=args.capability,
        )
    if args.command == "diff":
        return diff_history(
            catalog,
            args.source_id,
            from_probe_id=args.from_probe_id,
            to_probe_id=args.to_probe_id,
        )
    if args.command == "history":
        return history(catalog, args.source_id)
    raise ValueError(f"unsupported command: {args.command}")


def _emit(data: Mapping[str, Any], args: argparse.Namespace) -> None:
    if write_output(
        data,
        args,
        summary=f"Public-record monitor {args.command}",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    if args.command == "run":
        print(f"Processed {len(data['results'])} explicitly requested sources")
        for result in data["results"]:
            status = (
                result.get("probe", {}).get("status")
                or result.get("status")
                or "unknown"
            )
            print(
                f"  {result['source_id']}: {status} "
                f"(dispatched={result['dispatched']}, recorded={result['recorded']})"
            )
    elif args.command == "plan":
        print(f"Planned {len(data['sources'])} catalog sources")
        for source in data["sources"]:
            print(f"  {source['source_id']}: {source['mode']}")
    elif args.command == "history":
        print(f"{data['source_id']}: {len(data['probes'])} probes")
    elif args.command == "diff":
        comparison = data["comparison"]
        if comparison is None:
            print(f"{data['source_id']}: no probes")
        else:
            print(f"{data['source_id']}: drift_detected={comparison['drift_detected']}")
    else:
        print(f"Recorded probe #{data['probe']['probe_id']} for {data['source_id']}")


def _run_exit_code(data: Mapping[str, Any]) -> int:
    """Return a scheduler-friendly exit code for an explicit probe run."""

    healthy_statuses = {
        ResultStatus.OK.value,
        ResultStatus.NO_RESULTS.value,
    }
    for result in data.get("results", ()):
        probe = result.get("probe")
        status = (
            probe.get("status") if isinstance(probe, Mapping) else result.get("status")
        )
        if not result.get("recorded") or status not in healthy_statuses:
            return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if getattr(args, "timeout", 1) <= 0:
            parser.error("--timeout must be positive")
        if getattr(args, "max_attempts", 1) <= 0:
            parser.error("--max-attempts must be positive")
        data = execute(args)
        _emit(data, args)
        return _run_exit_code(data) if args.command == "run" else 0
    except (CatalogError, OSError, ValueError, json.JSONDecodeError) as error:
        if getattr(args, "json_out", False):
            print(
                json.dumps(
                    {
                        "command": args.command,
                        "status": "error",
                        "error": str(error),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
