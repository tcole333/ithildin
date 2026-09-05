#!/usr/bin/env python3
"""Unified state and local court-record query router.

Normalized sidecar data is queried locally by default. Selecting an external
source reports the latest catalogued access decision before any adapter is
considered. Public query results use each record's current access state;
restriction history remains in the sidecar audit tables.

Usage:
    uv run python tools/query_state_courts.py sources --json
    uv run python tools/query_state_courts.py search "ACME LLC"
    uv run python tools/query_state_courts.py case 156728/2019 \
      --source us-ny-nyscef --court-id ny-supreme
    uv run python tools/query_state_courts.py docket 2025CV000001 \
      --court-id wi-dane-circuit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from tools import (
        query_bexar_courts,
        query_california_court_directory,
        query_california_opinions,
        query_colorado_court_data,
        query_colorado_judicial,
        query_colorado_opinions,
        query_connecticut_civil_family,
        query_dc_appellate_cases,
        query_dc_court_directory_data,
        query_dc_opinions,
        query_dc_superior_calendar,
        query_delaware_courts,
        query_delaware_opinions,
        query_denver_county_court,
        query_doj_court_records,
        query_edva_bankruptcy,
        query_eugene_municipal_court,
        query_florida_acis,
        query_florida_court_directory_data,
        query_florida_ninth_opinions,
        query_georgia_court_access,
        query_fresno_superior_court,
        query_georgia_court_data,
        query_georgia_court_directory,
        query_georgia_supreme_docket,
        query_georgia_supreme_publications,
        query_harris_court_bulk,
        query_los_angeles_court,
        query_los_angeles_name_index,
        query_los_angeles_probate,
        query_md_estate_notices_claims,
        query_md_estate_search,
        query_md_business_opinions,
        query_md_judgment_liens,
        query_md_opinions,
        query_md_public_cases,
        query_michigan_appellate,
        query_michigan_business_court,
        query_new_mexico_case_lookup,
        query_new_jersey_tax_court,
        query_new_jersey_tax_court_opinions,
        query_ny_attorneys,
        query_ohio_delaware_common_pleas,
        query_ohio_franklin_courts,
        query_ohio_franklin_municipal,
        query_ohio_licking_common_pleas,
        query_ohio_franklin_probate,
        query_ohio_reporter_decisions,
        query_ohio_supreme_court,
        query_orange_county_court,
        query_oregon_appellate,
        query_oregon_appellate_calendars,
        query_oregon_court_calendar,
        query_oregon_court_documents,
        query_oregon_ojcin_products,
        query_oregon_smart_search,
        query_osceola_courts,
        query_palm_beach_courts,
        query_pima_courts,
        query_pa_opinions,
        query_pa_ujs,
        query_qld_ecourts,
        query_riverside_court,
        query_san_diego_court_index,
        query_san_mateo_midx,
        query_santa_clara_court_records,
        query_texas_appellate,
        query_texas_supreme_publications,
        query_va_general_district,
        query_vicourts,
        query_washington_courts,
        query_wisconsin_court_directory,
        query_wisconsin_opinions,
        query_wisconsin_wscca,
    )
    from tools.ingest_state_court_records import (
        ingest_court_data_delivery_receipt,
        ingest_envelope,
    )
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
        DEFAULT_COURT_DB,
        canonical_court_ref,
        connect_courts,
    )
    from tools.seed_public_records_catalog import ensure_catalog_source
except ImportError:
    import query_bexar_courts
    import query_california_court_directory
    import query_california_opinions
    import query_colorado_court_data
    import query_colorado_judicial
    import query_colorado_opinions
    import query_connecticut_civil_family
    import query_dc_appellate_cases
    import query_dc_court_directory_data
    import query_dc_opinions
    import query_dc_superior_calendar
    import query_delaware_courts
    import query_delaware_opinions
    import query_denver_county_court
    import query_doj_court_records
    import query_edva_bankruptcy
    import query_eugene_municipal_court
    import query_florida_acis
    import query_florida_court_directory_data
    import query_florida_ninth_opinions
    import query_georgia_court_access
    import query_fresno_superior_court
    import query_georgia_court_data
    import query_georgia_court_directory
    import query_georgia_supreme_docket
    import query_georgia_supreme_publications
    import query_harris_court_bulk
    import query_los_angeles_court
    import query_los_angeles_name_index
    import query_los_angeles_probate
    import query_md_estate_notices_claims
    import query_md_estate_search
    import query_md_business_opinions
    import query_md_judgment_liens
    import query_md_opinions
    import query_md_public_cases
    import query_michigan_appellate
    import query_michigan_business_court
    import query_new_mexico_case_lookup
    import query_new_jersey_tax_court
    import query_new_jersey_tax_court_opinions
    import query_ny_attorneys
    import query_ohio_delaware_common_pleas
    import query_ohio_franklin_courts
    import query_ohio_franklin_municipal
    import query_ohio_licking_common_pleas
    import query_ohio_franklin_probate
    import query_ohio_reporter_decisions
    import query_ohio_supreme_court
    import query_orange_county_court
    import query_oregon_appellate
    import query_oregon_appellate_calendars
    import query_oregon_court_calendar
    import query_oregon_court_documents
    import query_oregon_ojcin_products
    import query_oregon_smart_search
    import query_osceola_courts
    import query_palm_beach_courts
    import query_pima_courts
    import query_pa_opinions
    import query_pa_ujs
    import query_qld_ecourts
    import query_riverside_court
    import query_san_diego_court_index
    import query_san_mateo_midx
    import query_santa_clara_court_records
    import query_texas_appellate
    import query_texas_supreme_publications
    import query_va_general_district
    import query_vicourts
    import query_washington_courts
    import query_wisconsin_court_directory
    import query_wisconsin_opinions
    import query_wisconsin_wscca
    from ingest_state_court_records import (
        ingest_court_data_delivery_receipt,
        ingest_envelope,
    )
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
        DEFAULT_COURT_DB,
        canonical_court_ref,
        connect_courts,
    )
    from seed_public_records_catalog import ensure_catalog_source


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_SOURCE_ID = "local-state-court-records-sidecar"
CATALOG_SOURCE_ID = "local-public-records-catalog"
ACIS_SOURCE_ID = query_florida_acis.SOURCE_ID
FLORIDA_COURT_LOCATION_DIRECTORY_SOURCE_ID = (
    query_florida_court_directory_data.LOCATION_SOURCE_ID
)
FLORIDA_VIRTUAL_COURTROOM_DIRECTORY_SOURCE_ID = (
    query_florida_court_directory_data.VIRTUAL_SOURCE_ID
)
FLORIDA_OSCA_PUBLIC_RECORDS_SOURCE_ID = (
    query_florida_court_directory_data.PUBLIC_RECORDS_SOURCE_ID
)
FLORIDA_TRIAL_COURT_STATISTICS_SOURCE_ID = (
    query_florida_court_directory_data.STATISTICS_SOURCE_ID
)
FLORIDA_COURT_DIRECTORY_DATA_SOURCE_IDS = (
    FLORIDA_COURT_LOCATION_DIRECTORY_SOURCE_ID,
    FLORIDA_VIRTUAL_COURTROOM_DIRECTORY_SOURCE_ID,
    FLORIDA_OSCA_PUBLIC_RECORDS_SOURCE_ID,
    FLORIDA_TRIAL_COURT_STATISTICS_SOURCE_ID,
)
FLORIDA_NINTH_OPINIONS_SOURCE_ID = (
    query_florida_ninth_opinions.SOURCE_ID
)
BEXAR_HISTORICAL_SOURCE_ID = query_bexar_courts.SOURCE_ID
COLORADO_COURT_DATA_SOURCE_ID = query_colorado_court_data.SOURCE_ID
COLORADO_JUDICIAL_SOURCE_ID = query_colorado_judicial.SOURCE_ID
COLORADO_OPINIONS_SOURCE_ID = query_colorado_opinions.SOURCE_ID
COLORADO_OPINION_RELEASES_SOURCE_ID = query_colorado_opinions.RELEASE_SOURCE_ID
DC_OPINIONS_SOURCE_ID = query_dc_opinions.SOURCE_ID
DC_TODAY_CALENDAR_SOURCE_ID = query_dc_superior_calendar.TODAY_SOURCE_ID
DC_CRIMINAL_CALENDAR_SOURCE_ID = query_dc_superior_calendar.CRIMINAL_SOURCE_ID
DC_TAX_CALENDAR_SOURCE_ID = query_dc_superior_calendar.TAX_SOURCE_ID
DC_APPEALS_CALENDAR_SOURCE_ID = query_dc_superior_calendar.APPEALS_SOURCE_ID
DC_CALENDAR_SOURCE_IDS = (
    DC_TODAY_CALENDAR_SOURCE_ID,
    DC_CRIMINAL_CALENDAR_SOURCE_ID,
    DC_TAX_CALENDAR_SOURCE_ID,
    DC_APPEALS_CALENDAR_SOURCE_ID,
)
DELAWARE_COURTCONNECT_SOURCE_ID = query_delaware_courts.SOURCE_ID
DELAWARE_OPINIONS_SOURCE_ID = query_delaware_opinions.SOURCE_ID
DENVER_COUNTY_DOCKET_SOURCE_ID = query_denver_county_court.SOURCE_ID
DOJ_COURT_RECORDS_SOURCE_ID = query_doj_court_records.SOURCE_ID
DC_APPELLATE_CASES_SOURCE_ID = query_dc_appellate_cases.SOURCE_ID
DC_SUPERIOR_DIRECTORY_SOURCE_ID = (
    query_dc_court_directory_data.SUPERIOR_DIRECTORY_SOURCE_ID
)
DC_APPEALS_DIRECTORY_SOURCE_ID = (
    query_dc_court_directory_data.APPEALS_DIRECTORY_SOURCE_ID
)
DC_DIRECTORY_SOURCE_IDS = (
    DC_SUPERIOR_DIRECTORY_SOURCE_ID,
    DC_APPEALS_DIRECTORY_SOURCE_ID,
)
EDVA_BANKRUPTCY_SOURCE_ID = query_edva_bankruptcy.SOURCE_ID
EUGENE_MUNICIPAL_SOURCE_ID = query_eugene_municipal_court.SOURCE_ID
FRESNO_FAMILY_SOURCE_ID = query_fresno_superior_court.FAMILY_SOURCE_ID
FRESNO_PORTAL_SOURCE_ID = query_fresno_superior_court.PORTAL_SOURCE_ID
FRESNO_CALENDAR_SOURCE_ID = query_fresno_superior_court.CALENDAR_SOURCE_ID
FRESNO_RULINGS_SOURCE_ID = query_fresno_superior_court.RULINGS_SOURCE_ID
FRESNO_PROBATE_SOURCE_ID = query_fresno_superior_court.PROBATE_SOURCE_ID
FRESNO_INDEX_SOURCE_ID = query_fresno_superior_court.INDEX_SOURCE_ID
FRESNO_RECORDS_SOURCE_ID = query_fresno_superior_court.RECORDS_SOURCE_ID
FRESNO_SOURCE_IDS = (
    FRESNO_FAMILY_SOURCE_ID,
    FRESNO_PORTAL_SOURCE_ID,
    FRESNO_CALENDAR_SOURCE_ID,
    FRESNO_RULINGS_SOURCE_ID,
    FRESNO_PROBATE_SOURCE_ID,
    FRESNO_INDEX_SOURCE_ID,
    FRESNO_RECORDS_SOURCE_ID,
)
GEORGIA_COURT_DIRECTORY_SOURCE_ID = query_georgia_court_directory.SOURCE_ID
GEORGIA_EACCESS_DIRECTORY_SOURCE_ID = (
    query_georgia_court_access.EACCESS_SOURCE_ID
)
GEORGIA_EFILE_DIRECTORY_SOURCE_ID = (
    query_georgia_court_access.EFILE_SOURCE_ID
)
GEORGIA_COURT_ACCESS_SOURCE_IDS = (
    GEORGIA_EACCESS_DIRECTORY_SOURCE_ID,
    GEORGIA_EFILE_DIRECTORY_SOURCE_ID,
)
GEORGIA_CASELOAD_DASHBOARD_SOURCE_ID = (
    query_georgia_court_data.DASHBOARD_SOURCE_ID
)
GEORGIA_WORKLOAD_ASSESSMENT_SOURCE_ID = (
    query_georgia_court_data.WORKLOAD_SOURCE_ID
)
GEORGIA_SUPREME_DOCKET_SOURCE_ID = query_georgia_supreme_docket.SOURCE_ID
GEORGIA_SUPREME_PUBLICATION_SOURCE_IDS = tuple(
    query_georgia_supreme_publications.SOURCE_METADATA
)
OREGON_TYLER_TENANTS_BY_SOURCE = {
    tenant.source_id: tenant
    for tenant in query_eugene_municipal_court.OREGON_TENANTS.values()
}
OREGON_TYLER_MUNICIPAL_SOURCE_IDS = tuple(OREGON_TYLER_TENANTS_BY_SOURCE)
HARRIS_COURT_BULK_SOURCE_ID = query_harris_court_bulk.SOURCE_ID
LOS_ANGELES_CIVIL_SOURCE_ID = query_los_angeles_court.SOURCE_ID
LOS_ANGELES_NAME_INDEX_SOURCE_ID = query_los_angeles_name_index.SOURCE_ID
LOS_ANGELES_PROBATE_SOURCE_ID = query_los_angeles_probate.SOURCE_ID
MARYLAND_ESTATE_SOURCE_ID = query_md_estate_search.SOURCE_ID
MARYLAND_ESTATE_NOTICE_SOURCE_ID = (
    query_md_estate_notices_claims.NOTICE_SOURCE_ID
)
MARYLAND_ESTATE_CLAIM_SOURCE_ID = (
    query_md_estate_notices_claims.CLAIM_SOURCE_ID
)
MARYLAND_BUSINESS_OPINIONS_SOURCE_ID = query_md_business_opinions.SOURCE_ID
MARYLAND_JUDGMENT_LIENS_SOURCE_ID = query_md_judgment_liens.SOURCE_ID
MARYLAND_OPINIONS_SOURCE_ID = query_md_opinions.SOURCE_ID
MARYLAND_PUBLIC_CASES_SOURCE_ID = query_md_public_cases.SOURCE_ID
MICHIGAN_APPELLATE_SOURCE_ID = query_michigan_appellate.SOURCE_ID
MICHIGAN_BUSINESS_COURT_SOURCE_ID = query_michigan_business_court.SOURCE_ID
CONNECTICUT_CIVIL_FAMILY_SOURCE_ID = query_connecticut_civil_family.SOURCE_ID
NEW_MEXICO_CASE_LOOKUP_SOURCE_ID = query_new_mexico_case_lookup.SOURCE_ID
NEW_JERSEY_TAX_COURT_SOURCE_ID = query_new_jersey_tax_court.SOURCE_ID
NEW_JERSEY_TAX_COURT_OPINIONS_SOURCE_ID = (
    query_new_jersey_tax_court_opinions.SOURCE_ID
)
ORANGE_CALENDAR_SOURCE_ID = query_orange_county_court.CALENDAR_SOURCE_ID
ORANGE_RULING_SOURCE_IDS = dict(query_orange_county_court.RULING_SOURCE_IDS)
RIVERSIDE_CALENDAR_SOURCE_ID = query_riverside_court.CALENDAR_SOURCE_ID
RIVERSIDE_RULING_SOURCE_ID = query_riverside_court.RULING_SOURCE_ID
ORANGE_RULING_DIVISIONS_BY_SOURCE = {
    source_id: division for division, source_id in ORANGE_RULING_SOURCE_IDS.items()
}
OREGON_COURT_DOCUMENT_SOURCE_IDS = tuple(query_oregon_court_documents.COLLECTIONS)
OREGON_APPELLATE_SOURCE_ID = query_oregon_appellate.SOURCE_ID
OREGON_APPELLATE_CALENDAR_SOURCE_IDS = query_oregon_appellate_calendars.SOURCE_IDS
OREGON_COURT_CALENDAR_SOURCE_ID = query_oregon_court_calendar.SOURCE_ID
OREGON_SMART_SEARCH_SOURCE_ID = query_oregon_smart_search.SOURCE_ID
OREGON_OJCIN_PRODUCT_DIRECTORY_SOURCE_ID = query_oregon_ojcin_products.SOURCE_ID
OREGON_OJCIN_PRODUCT_SOURCE_IDS = tuple(query_oregon_ojcin_products.PRODUCTS)
OSCEOLA_BENCHMARK_SOURCE_ID = query_osceola_courts.PORTAL_SOURCE_ID
OSCEOLA_CALENDAR_SOURCE_ID = query_osceola_courts.CALENDAR_SOURCE_ID
OSCEOLA_FORECLOSURE_SOURCE_ID = query_osceola_courts.FORECLOSURE_SOURCE_ID
OSCEOLA_REPORT_SOURCE_IDS = (
    OSCEOLA_CALENDAR_SOURCE_ID,
    OSCEOLA_FORECLOSURE_SOURCE_ID,
)
PALM_BEACH_SOURCE_ID = query_palm_beach_courts.SOURCE_ID
PIMA_SOURCE_ID = query_pima_courts.SOURCE_ID
FRANKLIN_CIO_SOURCE_ID = query_ohio_franklin_courts.SOURCE_ID
FRANKLIN_MUNICIPAL_SOURCE_ID = query_ohio_franklin_municipal.SOURCE_ID
FRANKLIN_PROBATE_SOURCE_ID = query_ohio_franklin_probate.SOURCE_ID
DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID = (
    query_ohio_delaware_common_pleas.SOURCE_ID
)
LICKING_COMMON_PLEAS_SOURCE_ID = query_ohio_licking_common_pleas.SOURCE_ID
OHIO_REPORTER_DECISIONS_SOURCE_ID = query_ohio_reporter_decisions.SOURCE_ID
OHIO_SUPREME_COURT_SOURCE_ID = query_ohio_supreme_court.SOURCE_ID
PA_UJS_SOURCE_ID = query_pa_ujs.SOURCE_ID
PA_OPINIONS_SOURCE_ID = query_pa_opinions.SOURCE_ID
QLD_ECOURTS_SOURCE_ID = query_qld_ecourts.SOURCE_ID
SAN_MATEO_MIDX_SOURCE_ID = query_san_mateo_midx.SOURCE_ID
CALIFORNIA_COURT_DIRECTORY_SOURCE_ID = query_california_court_directory.SOURCE_ID
CALIFORNIA_OPINIONS_SOURCE_ID = query_california_opinions.SOURCE_ID
SAN_DIEGO_COURT_INDEX_SOURCE_ID = query_san_diego_court_index.SOURCE_ID
SANTA_CLARA_FAMILY_SOURCE_ID = query_santa_clara_court_records.FAMILY_SOURCE_ID
SANTA_CLARA_TENTATIVE_SOURCE_ID = (
    query_santa_clara_court_records.TENTATIVE_SOURCE_ID
)
SANTA_CLARA_CIVIL_PRODUCT_SOURCE_ID = (
    query_santa_clara_court_records.CIVIL_INDEX_SOURCE_ID
)
SANTA_CLARA_CRIMINAL_PRODUCT_SOURCE_ID = (
    query_santa_clara_court_records.CRIMINAL_INDEX_SOURCE_ID
)
SANTA_CLARA_PORTAL_SOURCE_ID = query_santa_clara_court_records.PORTAL_SOURCE_ID
SANTA_CLARA_SOURCE_IDS = (
    SANTA_CLARA_FAMILY_SOURCE_ID,
    SANTA_CLARA_TENTATIVE_SOURCE_ID,
    SANTA_CLARA_CIVIL_PRODUCT_SOURCE_ID,
    SANTA_CLARA_CRIMINAL_PRODUCT_SOURCE_ID,
    SANTA_CLARA_PORTAL_SOURCE_ID,
)
NY_LAW_REPORTS_SOURCE_ID = "us-ny-law-reporting-bureau"
NY_COLUMN_SOURCE_ID = "us-ny-public-notices-column"
NY_ATTORNEY_REGISTRATION_SOURCE_ID = query_ny_attorneys.SOURCE_ID
NYSCEF_SOURCE_ID = "us-ny-nyscef"
TAX_COURT_SOURCE_ID = "us-tax-court-dawson"
TEXAS_TAMES_SOURCE_ID = query_texas_appellate.SOURCE_ID
TEXAS_SUPREME_PUBLICATIONS_SOURCE_ID = (
    query_texas_supreme_publications.SOURCE_ID
)
VA_GENERAL_DISTRICT_SOURCE_ID = query_va_general_district.SOURCE_ID
VICOURTS_SOURCE_ID = query_vicourts.SOURCE_ID
WASHINGTON_COURT_DIRECTORY_SOURCE_ID = (
    query_washington_courts.DIRECTORY_SOURCE_ID
)
WASHINGTON_APPELLATE_OPINIONS_SOURCE_ID = (
    query_washington_courts.OPINIONS_SOURCE_ID
)
WISCONSIN_COURT_DIRECTORY_SOURCE_ID = query_wisconsin_court_directory.SOURCE_ID
WISCONSIN_OPINIONS_SOURCE_ID = query_wisconsin_opinions.SOURCE_ID
WISCONSIN_WSCCA_SOURCE_ID = query_wisconsin_wscca.SOURCE_ID
PUBLIC_STATE = "public"
HEARING_EVENT_ALIASES = ("future_hearing", "hearing")
OREGON_STATEWIDE_CALENDAR_COURT_ID = "or-statewide-circuit-tax-calendar"

LOCAL_SOURCE = SourceMetadata(
    source_id=LOCAL_SOURCE_ID,
    name="Normalized state and local court records sidecar",
    source_role="local_normalized_cache",
    metadata={
        "serves_current_access_state": PUBLIC_STATE,
        "coverage_semantics": "cache_with_explicit_query_evidence",
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
class _DOJCourtReleaseAdapter:
    """Apply shared transport settings without changing release-corpus semantics."""

    adapter: Any

    def execute(
        self,
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> PublicRecordsResult:
        del access_decision
        if args.command == "sources":
            return self.adapter.execute(args)
        client = self.adapter.DOJCourtRecordsClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
        )
        try:
            if args.command == "probe":
                return self.adapter.execute(
                    args,
                    client=client,
                    pdf_probe=lambda url: self.adapter.probe_pdf_magic(
                        url,
                        timeout=args.timeout,
                    ),
                )
            return self.adapter.execute(args, client=client)
        finally:
            client.close()


@dataclass(frozen=True)
class _NYAttorneyRegistrationAdapter:
    """Keep source discovery inside the shared result envelope."""

    adapter: Any

    def execute(
        self,
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> PublicRecordsResult:
        result = self.adapter.execute(args)
        if isinstance(result, PublicRecordsResult):
            return result
        if args.command != "sources" or not isinstance(result, Mapping):
            raise TypeError(
                "New York attorney adapter returned an invalid result"
            )
        query = PublicRecordsQuery(
            source=self.adapter.SOURCE_METADATA,
            jurisdiction=self.adapter.JURISDICTION,
            query=QueryMetadata(
                operation="discovery",
                parameters={"dataset_id": self.adapter.DATASET_ID},
                metadata={
                    "access_decision": dict(access_decision or {}),
                },
            ),
        )
        record = {
            **dict(result),
            "record_kind": "source_manifest",
            "source_id": self.adapter.SOURCE_ID,
            "dataset_id": self.adapter.DATASET_ID,
            "projection": {
                "projectable_as_case_record": False,
                "scope": "attorney_registration_source_manifest",
            },
        }
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[
                self.adapter.DATASET_URL,
                self.adapter.METADATA_URL,
            ],
            warnings=self.adapter.WARNINGS,
        )


@dataclass(frozen=True)
class _OsceolaReportAdapter:
    """Return a source-specific snapshot from the shared family probe."""

    adapter: Any

    def execute(
        self,
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> PublicRecordsResult:
        del access_decision
        result = self.adapter.execute(args)
        if args.command != "probe" or result.status not in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
        }:
            return result
        report_kind = (
            "calendar"
            if args.source == OSCEOLA_CALENDAR_SOURCE_ID
            else "foreclosure"
        )
        records: list[dict[str, Any]] = []
        for record in result.records:
            report_routes = record.get("report_routes")
            if not isinstance(report_routes, Mapping):
                continue
            report = report_routes.get(report_kind)
            if not isinstance(report, Mapping):
                continue
            records.append(
                {
                    "canonical_ref": (
                        "OSCEOLA-COURT-HEARING-CALENDAR:CURRENT"
                        if report_kind == "calendar"
                        else "OSCEOLA-MORTGAGE-FORECLOSURE-SCHEDULE:CURRENT"
                    ),
                    "source_id": args.source,
                    "record_kind": "rolling_report_probe",
                    "status": "ok",
                    "report_kind": report_kind,
                    "artifact_url": report.get("url"),
                    "media_type": report.get("media_type"),
                    "content_length": report.get("content_length"),
                    "last_modified": report.get("last_modified"),
                    "etag": report.get("etag"),
                    "projection": {
                        "projectable_as_case_record": False,
                        "scope": "current_report_metadata_snapshot",
                    },
                }
            )
        return PublicRecordsResult.success(
            result.query,
            records,
            retrieved_at=result.retrieved_at,
            raw_artifact_refs=result.raw_artifact_refs,
            warnings=result.warnings,
        )


@dataclass(frozen=True)
class _FloridaCourtDirectoryDataAdapter:
    """Apply shared keyword and explicit-limit semantics to snapshot results."""

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
            raise TypeError(
                "Florida court directory/data adapter returned an invalid result"
            )
        records = list(result.records)
        if args.command == "data-request":
            selector = str(getattr(args, "query", "") or "").strip()
            if selector.casefold() not in {"", "*", "all"}:
                needle = selector.casefold()
                records = [
                    record
                    for record in records
                    if needle in canonical_json(record).casefold()
                ]
        limit = getattr(args, "limit", None)
        if limit is not None:
            records = records[: int(limit)]
        if records == list(result.records):
            return result
        if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS}:
            return PublicRecordsResult.success(
                result.query,
                records,
                retrieved_at=result.retrieved_at,
                next_cursor=result.next_cursor,
                raw_artifact_refs=result.raw_artifact_refs,
                warnings=result.warnings,
            )
        return PublicRecordsResult(
            query=result.query,
            status=result.status,
            retrieved_at=result.retrieved_at,
            records=records,
            next_cursor=result.next_cursor,
            raw_artifact_refs=result.raw_artifact_refs,
            warnings=result.warnings,
            errors=result.errors,
            schema_version=result.schema_version,
        )


@dataclass(frozen=True)
class _HarrisBulkUnifiedAdapter:
    """Expose exact bulk-artifact operations without inventing case search."""

    adapter: Any

    def execute(
        self,
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> PublicRecordsResult:
        result = self.adapter.execute(
            args,
            access_decision=access_decision,
        )
        if args.command != "list" or result.status not in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
        }:
            return result
        records = list(result.records)
        text_filter = str(getattr(args, "text_filter", "") or "").casefold()
        if text_filter:
            records = [
                record
                for record in records
                if text_filter
                in " ".join(
                    str(record.get(field) or "")
                    for field in (
                        "filename",
                        "native_locator",
                        "dataset_family",
                        "cadence",
                    )
                ).casefold()
            ]
        published_after = getattr(args, "published_after", None)
        published_before = getattr(args, "published_before", None)
        if published_after:
            records = [
                record
                for record in records
                if str(record.get("published_date") or "") >= published_after
            ]
        if published_before:
            records = [
                record
                for record in records
                if str(record.get("published_date") or "") <= published_before
            ]
        result_limit = getattr(args, "result_limit", None)
        if result_limit is not None:
            records = records[: int(result_limit)]
        shared_filter_selected = any(
            (
                text_filter,
                published_after,
                published_before,
                result_limit is not None,
            )
        )
        if records == list(result.records) and not shared_filter_selected:
            return result
        parameters = dict(result.query.query.parameters)
        parameters.update(
            {
                key: value
                for key, value in {
                    "text_filter": text_filter or None,
                    "published_after": published_after,
                    "published_before": published_before,
                }.items()
                if value is not None
            }
        )
        query = PublicRecordsQuery(
            source=result.query.source,
            jurisdiction=result.query.jurisdiction,
            query=QueryMetadata(
                operation=result.query.query.operation,
                parameters=parameters,
                requested_limit=result_limit,
                cursor=result.query.query.cursor,
                metadata=dict(result.query.query.metadata),
            ),
        )
        return PublicRecordsResult.success(
            query,
            records,
            retrieved_at=result.retrieved_at,
            raw_artifact_refs=result.raw_artifact_refs,
            warnings=result.warnings,
        )


DC_OPINIONS_ADAPTER = _ExecuteWithoutAccessDecision(query_dc_opinions)
DC_APPELLATE_CASES_ADAPTER = _ExecuteWithoutAccessDecision(query_dc_appellate_cases)
DC_COURT_DIRECTORY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_dc_court_directory_data
)
DC_CALENDAR_ADAPTER = _ExecuteWithoutAccessDecision(query_dc_superior_calendar)
DOJ_COURT_RECORDS_ADAPTER = _DOJCourtReleaseAdapter(
    query_doj_court_records
)
EDVA_BANKRUPTCY_ADAPTER = _ExecuteWithoutAccessDecision(query_edva_bankruptcy)
EUGENE_ADAPTER = _ExecuteWithoutAccessDecision(query_eugene_municipal_court)
FRESNO_ADAPTER = _ExecuteWithoutAccessDecision(query_fresno_superior_court)
GEORGIA_COURT_DIRECTORY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_georgia_court_directory
)
GEORGIA_COURT_ACCESS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_georgia_court_access
)
GEORGIA_SUPREME_DOCKET_ADAPTER = _ExecuteWithoutAccessDecision(
    query_georgia_supreme_docket
)
GEORGIA_SUPREME_PUBLICATIONS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_georgia_supreme_publications
)
CALIFORNIA_COURT_DIRECTORY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_california_court_directory
)
CALIFORNIA_OPINIONS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_california_opinions
)
FLORIDA_COURT_DIRECTORY_DATA_ADAPTER = _FloridaCourtDirectoryDataAdapter(
    query_florida_court_directory_data
)
SANTA_CLARA_ADAPTER = _ExecuteWithoutAccessDecision(
    query_santa_clara_court_records
)
LOS_ANGELES_CIVIL_ADAPTER = _ExecuteWithoutAccessDecision(query_los_angeles_court)
ORANGE_COURT_ADAPTER = _ExecuteWithoutAccessDecision(query_orange_county_court)
RIVERSIDE_COURT_ADAPTER = _ExecuteWithoutAccessDecision(query_riverside_court)
QLD_ECOURTS_ADAPTER = _ExecuteWithoutAccessDecision(query_qld_ecourts)
WISCONSIN_COURT_DIRECTORY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_wisconsin_court_directory
)
WISCONSIN_OPINIONS_ADAPTER = _ExecuteWithoutAccessDecision(query_wisconsin_opinions)
WISCONSIN_WSCCA_ADAPTER = _ExecuteWithoutAccessDecision(query_wisconsin_wscca)
MARYLAND_PUBLIC_CASES_ADAPTER = _ExecuteWithoutAccessDecision(query_md_public_cases)
MARYLAND_ESTATE_SUPPLEMENTS_ADAPTER = query_md_estate_notices_claims
MARYLAND_BUSINESS_OPINIONS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_md_business_opinions
)
MARYLAND_JUDGMENT_LIENS_ADAPTER = _ExecuteWithoutAccessDecision(query_md_judgment_liens)
MARYLAND_OPINIONS_ADAPTER = _ExecuteWithoutAccessDecision(query_md_opinions)
MICHIGAN_APPELLATE_ADAPTER = _ExecuteWithoutAccessDecision(query_michigan_appellate)
MICHIGAN_BUSINESS_COURT_ADAPTER = _ExecuteWithoutAccessDecision(
    query_michigan_business_court
)
CONNECTICUT_CIVIL_FAMILY_ADAPTER = _ExecuteWithoutAccessDecision(
    query_connecticut_civil_family
)
NEW_MEXICO_CASE_LOOKUP_ADAPTER = _ExecuteWithoutAccessDecision(
    query_new_mexico_case_lookup
)
TEXAS_SUPREME_PUBLICATIONS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_texas_supreme_publications
)
NEW_JERSEY_TAX_COURT_ADAPTER = _ExecuteWithoutAccessDecision(query_new_jersey_tax_court)
NEW_JERSEY_TAX_COURT_OPINIONS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_new_jersey_tax_court_opinions
)
NY_ATTORNEY_REGISTRATION_ADAPTER = _NYAttorneyRegistrationAdapter(
    query_ny_attorneys
)
VA_GENERAL_DISTRICT_ADAPTER = _ExecuteWithoutAccessDecision(query_va_general_district)
WASHINGTON_COURTS_ADAPTER = _ExecuteWithoutAccessDecision(query_washington_courts)
OREGON_TYLER_ADAPTER = EUGENE_ADAPTER
OREGON_SMART_SEARCH_ADAPTER = _ExecuteWithoutAccessDecision(query_oregon_smart_search)
OSCEOLA_BENCHMARK_ADAPTER = _ExecuteWithoutAccessDecision(query_osceola_courts)
OSCEOLA_REPORT_ADAPTER = _OsceolaReportAdapter(query_osceola_courts)
FRANKLIN_CIO_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_franklin_courts
)
FRANKLIN_MUNICIPAL_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_franklin_municipal
)
FRANKLIN_PROBATE_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_franklin_probate
)
DELAWARE_OHIO_COMMON_PLEAS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_delaware_common_pleas
)
LICKING_COMMON_PLEAS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_licking_common_pleas
)
OHIO_REPORTER_DECISIONS_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_reporter_decisions
)
OHIO_SUPREME_COURT_ADAPTER = _ExecuteWithoutAccessDecision(
    query_ohio_supreme_court
)
HARRIS_COURT_BULK_ADAPTER = _HarrisBulkUnifiedAdapter(
    query_harris_court_bulk
)


class _MarylandEstateUnifiedAdapter:
    """Resolve a public estate number to its RowNet detail when requested."""

    @staticmethod
    def execute(
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> PublicRecordsResult:
        if args.command != "resolve-estate":
            return query_md_estate_search.execute(
                args,
                access_decision=access_decision,
            )

        search_values = vars(args).copy()
        search_values.update(
            command="estate",
            all_results=True,
            limit=query_md_estate_search.DEFAULT_LIMIT,
            cursor=None,
        )
        search_result = query_md_estate_search.execute(
            argparse.Namespace(**search_values),
            access_decision=access_decision,
        )
        if search_result.status not in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
        }:
            return search_result
        if not search_result.records:
            return search_result
        if len(search_result.records) != 1:
            return PublicRecordsResult.failure(
                search_result.query,
                ResultStatus.PARTIAL,
                [
                    PublicRecordsError(
                        code="estate_number_requires_county",
                        message=(
                            "The estate number matched more than one Maryland "
                            "jurisdiction; select --county or --court-id to "
                            "retrieve one case and its docket."
                        ),
                        category="selection",
                        retryable=False,
                        details={
                            "candidate_count": len(search_result.records),
                            "candidates": [
                                {
                                    "county": record.get("county"),
                                    "estate_number": record.get("estate_number"),
                                    "record_id": record.get("record_id"),
                                }
                                for record in search_result.records
                            ],
                        },
                    )
                ],
                records=search_result.records,
                retrieved_at=search_result.retrieved_at,
                raw_artifact_refs=search_result.raw_artifact_refs,
                warnings=search_result.warnings,
            )

        record_id = str(search_result.records[0]["record_id"])
        detail_values = vars(args).copy()
        detail_values.update(command="detail", record_id=record_id)
        detail_result = query_md_estate_search.execute(
            argparse.Namespace(**detail_values),
            access_decision=access_decision,
        )
        if detail_result.status not in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
        }:
            return detail_result
        return PublicRecordsResult(
            query=search_result.query,
            status=detail_result.status,
            retrieved_at=detail_result.retrieved_at,
            records=detail_result.records,
            raw_artifact_refs=tuple(
                dict.fromkeys(
                    (
                        *search_result.raw_artifact_refs,
                        *detail_result.raw_artifact_refs,
                    )
                )
            ),
            warnings=tuple(
                dict.fromkeys((*search_result.warnings, *detail_result.warnings))
            ),
            errors=detail_result.errors,
        )


MARYLAND_ESTATE_ADAPTER = _MarylandEstateUnifiedAdapter()


class _OJCINProductDirectoryAdapter:
    """Expose product records and acquisition handoffs as non-case records."""

    @staticmethod
    def execute(
        args: argparse.Namespace,
        *,
        access_decision: Mapping[str, Any] | None = None,
    ) -> PublicRecordsResult:
        query = PublicRecordsQuery(
            source=query_oregon_ojcin_products.SOURCE_METADATA,
            jurisdiction=query_oregon_ojcin_products.JURISDICTION,
            query=QueryMetadata(
                operation=args.command,
                parameters={
                    "product_id": args.product_id,
                    "query": args.query,
                },
                metadata={"access_decision": dict(access_decision or {})},
            ),
        )
        if args.command == "products":
            records = query_oregon_ojcin_products.product_records(args.product_id)
        elif args.command == "handoff":
            handoff = query_oregon_ojcin_products.handoff_record(args.product_id)
            records = [
                {
                    "canonical_ref": (f"OR-OJCIN-HANDOFF:{args.product_id}"),
                    "source_id": args.product_id,
                    "record_kind": "court_data_acquisition_handoff",
                    **handoff,
                }
            ]
        else:
            raise ValueError(f"unsupported OJCIN directory command {args.command}")
        return PublicRecordsResult.success(query, records)


OREGON_OJCIN_PRODUCT_DIRECTORY_ADAPTER = _OJCINProductDirectoryAdapter()


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


class _ExplicitMinimumIntervalAction(argparse.Action):
    """Store pacing and remember that the caller selected it."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        del parser, option_string
        setattr(namespace, self.dest, values)
        setattr(namespace, "minimum_interval_explicit", True)


def _acis_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the stable router surface to the source adapter namespace."""
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        court=args.court_id,
        filed_after=args.after,
        filed_before=args.before,
        documents=False,
        output=None,
        json_out=False,
    )
    if adapter_command == "search":
        values.update(search_scope="party", match_mode="match")
    elif adapter_command == "calendar":
        hearing_date = getattr(args, "hearing_date", None)
        if hearing_date and any(
            value and value != hearing_date
            for value in (args.after, args.before)
        ):
            raise ValueError(
                "Florida ACIS calendar --hearing-date, --after, and "
                "--before must agree when combined"
            )
        values.update(
            after=hearing_date or args.after,
            before=hearing_date or args.before,
            session_type=args.case_type,
            event_name=(
                None
                if str(args.query or "").strip() in {"", "*"}
                else args.query
            ),
            events_only=False,
        )
    elif adapter_command == "download":
        values.update(
            court_resource_uuid=args.court_id,
            document_uuid=args.query,
        )
    return argparse.Namespace(**values)


def _florida_ninth_opinions_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared keyword search to the official opinion archive."""
    return argparse.Namespace(
        command=adapter_command,
        query=args.query,
        limit=_caller_limit(args) or args.limit,
        cursor=args.cursor,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=query_florida_ninth_opinions.DEFAULT_MAX_ATTEMPTS,
        output=None,
        json_out=False,
        quiet=False,
    )


def _resolve_florida_county(value: str) -> str:
    """Resolve a county name or GEOID without changing the published record."""

    selector = str(value).strip()
    normalized = selector.upper()
    if normalized.startswith("US-GEOID-"):
        normalized = normalized.removeprefix("US-GEOID-")
    county_by_geoid = {
        geoid: county
        for county, geoid in (
            query_florida_court_directory_data.COUNTY_GEOID_BY_NAME.items()
        )
    }
    if normalized in county_by_geoid:
        return county_by_geoid[normalized]
    name_selector = re.sub(
        r"\s+county$",
        "",
        selector,
        flags=re.IGNORECASE,
    ).strip()
    for county in query_florida_court_directory_data.COUNTY_GEOID_BY_NAME:
        if name_selector.casefold() == county.casefold():
            return county
    raise ValueError(
        "Florida directory county selectors must be a Florida county name "
        "or county GEOID"
    )


def _florida_county_context(
    args: argparse.Namespace,
    *,
    allow_county: bool,
) -> str | None:
    selectors: list[str] = []
    jurisdiction = str(args.jurisdiction or "").strip()
    normalized_jurisdiction = jurisdiction.upper()
    if normalized_jurisdiction.startswith("US-GEOID-"):
        normalized_jurisdiction = normalized_jurisdiction.removeprefix(
            "US-GEOID-"
        )
    if normalized_jurisdiction not in {"", "FL", "12", "US-FL"}:
        selectors.append(jurisdiction)
    if args.county:
        selectors.append(str(args.county))
    if selectors and not allow_county:
        raise ValueError("This Florida statewide publication is not county-filtered")
    counties = {_resolve_florida_county(value) for value in selectors}
    if len(counties) > 1:
        raise ValueError(
            "Florida county and jurisdiction selectors identify different counties"
        )
    return next(iter(counties), None)


def _reject_florida_snapshot_case_selectors(
    args: argparse.Namespace,
    *,
    allow_first_name: bool = False,
    allow_live_filter: bool = False,
) -> None:
    if any((args.after, args.before, args.case_type, args.court_id, args.cursor)):
        raise ValueError(
            "Florida directory and publication snapshots do not expose case, "
            "filing-date, court-ID, or continuation selectors"
        )
    if any(
        (
            args.courthouse,
            args.date_of_birth,
            args.drivers_license,
            args.plate_state,
            args.violation_number,
            args.partial,
            args.phonetic,
        )
    ):
        raise ValueError(
            "Florida directory and publication search uses its text and "
            "source-native catalog selectors"
        )
    if args.first_name and not allow_first_name:
        raise ValueError("--first-name is available only for virtual judge lookup")
    if args.exclude_inactive and not allow_live_filter:
        raise ValueError(
            "--exclude-inactive is available only for live virtual courtrooms"
        )


def _florida_location_directory_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared search to the official court-location snapshot."""

    if adapter_command != "locations":
        raise ValueError(f"unsupported Florida location operation {adapter_command}")
    _reject_florida_snapshot_case_selectors(args)
    county = _florida_county_context(args, allow_county=True)
    selector = str(args.query or "").strip()
    if selector.casefold() in {"", "*", "all", "directory"}:
        selector = ""
    if county and selector and selector.casefold() not in county.casefold():
        raise ValueError(
            "Use either a county selector or a different directory text query"
        )
    selected_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    kind_by_field = {
        "": None,
        "all": None,
        "directory": None,
        "county": "county",
        "courthouse": "county",
        "dca": "dca",
        "appellate": "dca",
    }
    district = (
        selected_field
        if selected_field
        in query_florida_court_directory_data.EXPECTED_DISTRICTS
        else None
    )
    if selected_field not in kind_by_field and district is None:
        raise ValueError(
            "Florida location --search-field must be directory, county, "
            "courthouse, dca, appellate, or 1dca through 6dca"
        )
    return argparse.Namespace(
        command="locations",
        query=county or selector or None,
        district=district,
        kind=kind_by_field.get(selected_field),
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=query_florida_court_directory_data.DEFAULT_MAX_ATTEMPTS,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )


def _florida_virtual_directory_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared search to Florida's Virtual Courtroom Directory."""

    if adapter_command != "virtual":
        raise ValueError(f"unsupported Florida virtual operation {adapter_command}")
    _reject_florida_snapshot_case_selectors(
        args,
        allow_first_name=True,
        allow_live_filter=True,
    )
    context_county = _florida_county_context(args, allow_county=True)
    selector = str(args.query or "").strip()
    if selector.casefold() in {"", "*", "all", "directory"}:
        selector = ""
    selected_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    if selected_field not in {
        "",
        "all",
        "directory",
        "text",
        "county",
        "judge",
        "judicial-officer",
        "live",
    }:
        raise ValueError(
            "Florida virtual-directory --search-field must be directory, "
            "text, county, judge, judicial-officer, or live"
        )
    county = context_county
    judge = None
    query_text = selector or None
    if selected_field == "county":
        selected_county = _resolve_florida_county(selector)
        if context_county and context_county != selected_county:
            raise ValueError(
                "Florida virtual-directory selectors identify different counties"
            )
        county = selected_county
        query_text = None
    elif selected_field in {"judge", "judicial-officer"}:
        if context_county:
            raise ValueError(
                "The source accepts either its county or judge endpoint selector"
            )
        judge = " ".join(
            value
            for value in (str(args.first_name or "").strip(), selector)
            if value
        )
        if not judge:
            raise ValueError("Florida virtual judge lookup requires a name")
        query_text = None
    elif args.first_name:
        query_text = " ".join(
            value
            for value in (str(args.first_name).strip(), selector)
            if value
        )
    return argparse.Namespace(
        command="virtual",
        county=f"{county} County" if county else None,
        judge=judge,
        query=query_text,
        live_only=bool(args.exclude_inactive or selected_field == "live"),
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=query_florida_court_directory_data.DEFAULT_MAX_ATTEMPTS,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )


def _florida_osca_request_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared search to the current OSCA request-route snapshot."""

    if adapter_command != "data-request":
        raise ValueError(f"unsupported Florida request operation {adapter_command}")
    _reject_florida_snapshot_case_selectors(args)
    _florida_county_context(args, allow_county=False)
    selected_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    if selected_field not in {"", "all", "request", "program", "contact"}:
        raise ValueError(
            "OSCA request --search-field must be request, program, or contact"
        )
    return argparse.Namespace(
        command="data-request",
        query=str(args.query or "").strip() or None,
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=query_florida_court_directory_data.DEFAULT_MAX_ATTEMPTS,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )


def _florida_statistics_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared search to the trial-court publication catalog."""

    if adapter_command != "statistics":
        raise ValueError(f"unsupported Florida statistics operation {adapter_command}")
    _reject_florida_snapshot_case_selectors(args)
    _florida_county_context(args, allow_county=False)
    selector = str(args.query or "").strip()
    if selector.casefold() in {"", "*", "all", "catalog"}:
        selector = ""
    selected_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    if selected_field not in {"", "all", "catalog", "text", "fiscal-year", "section"}:
        raise ValueError(
            "Florida statistics --search-field must be catalog, text, "
            "fiscal-year, or section"
        )
    return argparse.Namespace(
        command="statistics",
        fiscal_year=selector if selected_field == "fiscal-year" else None,
        section=selector if selected_field == "section" else None,
        query=(
            selector
            if selected_field not in {"fiscal-year", "section"} and selector
            else None
        ),
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=query_florida_court_directory_data.DEFAULT_MAX_ATTEMPTS,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )


def _oregon_appellate_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the unified court surface to Oregon's appellate API."""
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        court=args.court_id,
        output=None,
        json_out=False,
        max_attempts=3,
    )
    if adapter_command == "search-party":
        values.update(
            query=args.query,
            match_mode="match",
            filed_after=args.after,
            filed_before=args.before,
        )
    elif adapter_command in {
        "case",
        "docket",
        "parties",
        "document-metadata",
    }:
        values.update(case_number=args.query)
    elif adapter_command == "calendar":
        values.update(after=args.after, before=args.before)
    return argparse.Namespace(**values)


def _oregon_court_calendar_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate a location/date calendar query to Oregon PublicAccess."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    valid_county_geoids = set(query_oregon_court_calendar.COUNTY_GEOIDS.values())
    if (
        jurisdiction
        and jurisdiction not in {"41", "OR"}
        and jurisdiction not in valid_county_geoids
    ):
        raise ValueError(
            "The Oregon calendar accepts Oregon context (41/OR) or an "
            "Oregon county GEOID"
        )

    hearing_date = getattr(args, "hearing_date", None)
    if hearing_date and any(
        value and value != hearing_date for value in (args.after, args.before)
    ):
        raise ValueError(
            "Oregon calendar --hearing-date, --after, and --before must "
            "agree when combined"
        )
    date_after = hearing_date or args.after
    date_before = hearing_date or args.before

    categories = None
    if args.case_type:
        category = str(args.case_type).casefold()
        if category not in query_oregon_court_calendar.CATEGORY_CODES:
            supported = ", ".join(sorted(query_oregon_court_calendar.CATEGORY_CODES))
            raise ValueError(f"Oregon calendar --case-type must be one of {supported}")
        categories = [category]

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        location=args.query,
        date_after=date_after,
        date_before=date_before,
        categories=categories,
        case_number=None,
        party_first_name=None,
        party_last_name=None,
        party_middle_name=None,
        business_name=None,
        attorney_first_name=None,
        attorney_last_name=None,
        attorney_middle_name=None,
        attorney_bar_number=None,
        judicial_officer=None,
        exact_name=False,
        soundex=True,
        limit=_caller_limit(args),
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _oregon_appellate_calendar_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the unified calendar surface to one appellate list."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"41", "OR"}:
        raise ValueError("Oregon appellate calendars accept Oregon context (41 or OR)")

    source_to_spec = {
        spec.source_id: spec
        for spec in (
            query_oregon_appellate_calendars.COURT_OF_APPEALS,
            query_oregon_appellate_calendars.SUPREME_COURT,
        )
    }
    spec = source_to_spec[args.source]
    if args.court_id and args.court_id not in {
        spec.court_id,
        spec.native_court_id,
    }:
        raise ValueError(f"{spec.name} uses court ID {spec.court_id}")

    hearing_date = getattr(args, "hearing_date", None)
    if hearing_date and any(
        value and value != hearing_date for value in (args.after, args.before)
    ):
        raise ValueError(
            "Oregon appellate calendar --hearing-date, --after, and "
            "--before must agree when combined"
        )

    event_types = None
    if args.case_type:
        event_type = str(args.case_type).casefold().replace("_", "-")
        if event_type not in {"oral-argument", "submission"}:
            raise ValueError(
                "Oregon appellate calendar --case-type selects "
                "oral-argument or submission"
            )
        event_types = [event_type]

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        court=spec.key,
        date_after=hearing_date or args.after,
        date_before=hearing_date or args.before,
        current=False,
        case_number=None,
        query_text=args.query,
        event_types=event_types,
        limit=_caller_limit(args),
        output=None,
        json_out=False,
        max_attempts=3,
    )
    return argparse.Namespace(**values)


def _eugene_municipal_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the shared surface to one verified Oregon Tyler tenant."""

    tenant = OREGON_TYLER_TENANTS_BY_SOURCE[args.source]
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    accepted_jurisdictions = {
        "",
        "41",
        "OR",
        str(tenant.jurisdiction_id).upper(),
    }
    if tenant.county_fips:
        accepted_jurisdictions.add(str(tenant.county_fips).upper())
    if jurisdiction not in accepted_jurisdictions:
        raise ValueError(
            f"{tenant.court_name} uses jurisdiction {tenant.jurisdiction_id}"
        )
    if args.court_id and args.court_id != tenant.court_id:
        raise ValueError(f"{tenant.court_name} uses court ID {tenant.court_id}")

    runtime = {
        "tenant": tenant.key,
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "max_attempts": 3,
        "retry_backoff": 0.25,
        "output": None,
        "json_out": False,
    }
    caller_limit = _caller_limit(args) or args.limit
    if adapter_command == "search":
        search_field = str(args.search_field or "last_name").strip().lower()
        aliases = {
            "name": "last_name",
            "last-name": "last_name",
            "citation_number": "citation",
            "docket": "docket_number",
            "police_case": "police_case_number",
            "case_number": "police_case_number",
            "vehicle_plate": "plate",
        }
        search_field = aliases.get(search_field, search_field)
        selectors = {
            "last_name": None,
            "citation": None,
            "docket_number": None,
            "police_case_number": None,
            "plate": None,
            "vin": None,
        }
        if search_field not in selectors:
            raise ValueError(
                "Tyler tenant --search-field must be last_name, citation, "
                "docket_number, police_case_number, plate, or vin"
            )
        native_selector = {
            "last_name": "Name",
            "citation": "CitationNumber",
            "docket_number": "DocketNumber",
            "police_case_number": "CaseNumber",
            "plate": "VehiclePlate",
            "vin": "VIN",
        }[search_field]
        if (
            tenant.case_access_state == "public"
            and tenant.verified_selectors
            and native_selector not in tenant.verified_selectors
        ):
            available = ", ".join(tenant.verified_selectors)
            raise ValueError(
                f"{tenant.court_name} currently exposes {available}; "
                f"{native_selector} was not present in its verified form"
            )
        selectors[search_field] = args.query
        return argparse.Namespace(
            command="search",
            **selectors,
            first_name=args.first_name,
            date_of_birth=args.date_of_birth,
            drivers_license=args.drivers_license,
            soundex=args.phonetic,
            partial=args.partial,
            plate_state=args.plate_state,
            limit=caller_limit,
            cursor=args.cursor,
            **runtime,
        )
    if adapter_command == "dockets":
        return argparse.Namespace(
            command="dockets",
            date_from=args.after,
            date_to=args.before,
            limit=caller_limit,
            cursor=args.cursor,
            **runtime,
        )
    if adapter_command == "docket":
        parts = [value.strip() for value in args.query.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                "Tyler docket selectors use NATIVE_DATE|CALENDAR_CODE|ROOM_CODE"
            )
        return argparse.Namespace(
            command="docket",
            native_date=parts[0],
            calendar_code=parts[1],
            room_code=parts[2],
            limit=caller_limit,
            cursor=args.cursor,
            **runtime,
        )
    if adapter_command == "case":
        violation_number = args.violation_number
        citation_number = args.query
        if violation_number is None:
            if "-" not in citation_number:
                raise ValueError(
                    "Tyler case lookup needs CITATION-VIOLATION or --violation-number"
                )
            citation_number, violation_number = citation_number.rsplit("-", 1)
        return argparse.Namespace(
            command="case",
            citation_number=citation_number,
            violation_number=violation_number,
            **runtime,
        )
    raise ValueError(f"unsupported Tyler tenant operation {adapter_command}")


def _oregon_smart_search_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Prepare a Smart Search browser handoff without claiming case rows."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if (
        jurisdiction
        and jurisdiction not in {"41", "OR"}
        and not re.fullmatch(r"41\d{3}", jurisdiction)
    ):
        raise ValueError("Oregon Smart Search accepts Oregon or Oregon county context")
    search_by = (
        "BusinessName"
        if args.entity_kind == "organization"
        else str(args.search_field or "SmartSearch")
    )
    return argparse.Namespace(
        command=adapter_command,
        query_text=args.query,
        search_by=search_by,
        location=args.courthouse or "All Locations",
        last_name=(args.query if search_by == "LastName" else None),
        first_name=args.first_name,
        middle_name=None,
        suffix=None,
        phone_number=None,
        fbi_number=None,
        so_number=None,
        booking_number=None,
        case_type=args.case_type or "All Case Types",
        case_status=None,
        file_date_start=args.after,
        file_date_end=args.before,
        judicial_officer=None,
        judgment_type=None,
        judgment_date_from=None,
        judgment_date_to=None,
        warrant_type=None,
        warrant_status=None,
        warrant_date_issued_from=None,
        warrant_date_issued_to=None,
        search_cases=True,
        search_judgments=True,
        search_warrants=True,
        party_name=args.entity_kind == "person",
        nickname=False,
        business_name=args.entity_kind == "organization",
        soundex=args.phonetic,
        browser_timeout=args.timeout,
        output=None,
        json_out=False,
    )


def _oregon_ojcin_product_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    product_id = args.product_id
    if adapter_command == "handoff":
        product_id = product_id or args.query
    if (
        product_id is not None
        and product_id not in query_oregon_ojcin_products.PRODUCTS
    ):
        raise ValueError(f"unknown Oregon court-data product: {product_id}")
    return argparse.Namespace(
        command=adapter_command,
        query=args.query,
        product_id=product_id,
    )


def _kofile_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    prefix = "kofile:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError("Bexar cursor must have form kofile:offset:N")
    return int(cursor[len(prefix) :])


def _bexar_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the unified court surface to the historical Kofile adapter."""
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
    )
    if adapter_command == "search":
        has_after = bool(args.after)
        has_before = bool(args.before)
        if has_after != has_before:
            raise ValueError(
                "Bexar historical date filtering requires both --after and --before"
            )
        values.update(
            query=args.query,
            ocr=has_after,
            date_from=args.after,
            date_to=args.before,
            limit=(
                min(args.limit, args.max_records)
                if args.max_records is not None
                else args.limit
            ),
            offset=_kofile_offset(args.cursor),
            workspace_id=None,
        )
    elif adapter_command == "case":
        try:
            values["doc_id"] = int(args.query)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Bexar historical case selection requires a numeric DOC_ID"
            ) from error
        if values["doc_id"] <= 0:
            raise ValueError(
                "Bexar historical case selection requires a positive DOC_ID"
            )
    elif adapter_command == "page":
        try:
            values["doc_id"] = int(args.query)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Bexar historical page retrieval requires a numeric DOC_ID"
            ) from error
        if values["doc_id"] <= 0:
            raise ValueError(
                "Bexar historical page retrieval requires a positive DOC_ID"
            )
        if args.page_number is None:
            raise ValueError("Bexar historical page retrieval requires --page-number")
        if args.page_number <= 0:
            raise ValueError("--page-number must be positive")
    return argparse.Namespace(**values)


def _vicourts_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the unified court surface to the VI C-Track adapter."""
    if args.after or args.before or args.case_type:
        raise ValueError(
            "VI C-Track does not represent the unified --after, --before, "
            "or --case-type filters; use a supported selector"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        court=args.court_id,
        limit=(
            min(args.limit, args.max_records)
            if args.max_records is not None
            else args.limit
        ),
        output=None,
        json_out=False,
    )
    if adapter_command == "search":
        values.update(field="party", match_mode="match")
    elif adapter_command in {"case", "docket", "claims", "documents"}:
        values["case_number"] = args.query
        if adapter_command == "documents":
            docket_uuid = getattr(args, "docket_entry_uuid", None)
            if not docket_uuid:
                raise ValueError("VI document listing requires --docket-entry-uuid")
            values["docket_entry_uuid"] = docket_uuid
    elif adapter_command == "download":
        if not args.court_id:
            raise ValueError("VI document download requires --court-id")
        if not args.case_uuid:
            raise ValueError("VI document download requires --case-uuid")
        values.update(
            case_uuid=args.case_uuid,
            document_uuid=args.query,
        )
    return argparse.Namespace(**values)


def _pima_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the unified court surface to the Pima Agave adapter."""
    if args.after or args.before or args.case_type:
        raise ValueError(
            "Pima Agave does not expose the unified --after, --before, or "
            "--case-type filters; use its supported name or case selector"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        max_attempts=3,
    )
    if adapter_command == "search":
        values.update(
            last_name=args.query,
            first_name=None,
            limit=(
                min(args.limit, args.max_records)
                if args.max_records is not None
                else args.limit
            ),
        )
    elif adapter_command == "case":
        values.update(
            case_number=args.query,
            last_name=None,
            first_name=None,
        )
    elif adapter_command == "document":
        if not args.case_number:
            raise ValueError("Pima document download requires --case-number")
        if not args.destination:
            raise ValueError("Pima document download requires --destination")
        values.update(
            case_number=args.case_number,
            entry_id=args.query,
            destination=args.destination,
            last_name=None,
            first_name=None,
        )
    return argparse.Namespace(**values)


def _franklin_cio_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate party-index and exact-case operations to Franklin CIO."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", "39049"}:
        raise ValueError(
            "Franklin CIO serves Franklin County, Ohio (GEOID 39049)"
        )
    if args.court_id and args.court_id != query_ohio_franklin_courts.COURT_ID:
        raise ValueError(
            "Franklin CIO uses court ID "
            f"{query_ohio_franklin_courts.COURT_ID}"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        max_attempts=3,
    )
    if adapter_command == "name":
        if getattr(args, "document_type", None):
            raise ValueError(
                "Franklin CIO party search does not apply --document-type"
            )
        search_field = (
            str(args.search_field or "").strip().casefold().replace("_", "-")
        )
        if search_field not in {
            "",
            "auto",
            "name",
            "party",
            "party-name",
            "person",
            "organization",
            "last-name",
        }:
            raise ValueError(
                "Franklin CIO --search-field must identify its party-name index"
            )
        if args.cursor:
            raise ValueError(
                "Franklin CIO party results do not publish a continuation cursor"
            )
        court_category = str(
            getattr(args, "court_category", None)
            or args.courthouse
            or "all"
        ).strip().casefold()
        court_aliases = {
            "": "all",
            "all": "all",
            "appeal": "appeals",
            "appeals": "appeals",
            "civil": "civil",
            "criminal": "criminal",
            "domestic": "domestic",
            "domestic-relations": "domestic",
        }
        try:
            court_category = court_aliases[court_category]
        except KeyError as error:
            raise ValueError(
                "Franklin CIO court category must be all, appeals, civil, "
                "criminal, or domestic"
            ) from error
        caller_limit = _caller_limit(args)
        native_row_count = query_ohio_franklin_courts.DEFAULT_NATIVE_ROW_COUNT
        if caller_limit is not None:
            native_row_count = next(
                (
                    value
                    for value in query_ohio_franklin_courts.NATIVE_ROW_COUNTS
                    if value >= caller_limit
                ),
                query_ohio_franklin_courts.NATIVE_ROW_COUNTS[-1],
            )
        middle_name = str(getattr(args, "middle_name", None) or "").strip()
        values.update(
            last_name=str(args.query).strip(),
            first_name=(str(args.first_name).strip() if args.first_name else None),
            middle_initial=middle_name[:1] or None,
            court=court_category,
            filed_from=args.after,
            filed_to=args.before,
            native_row_count=native_row_count,
            exhaustive=bool(args.after and args.before),
            shared_requested_limit=caller_limit,
        )
    elif adapter_command == "case":
        unsupported_filters = [
            name
            for name, value in (
                ("--after", args.after),
                ("--before", args.before),
                ("--case-type", args.case_type),
                ("--document-type", getattr(args, "document_type", None)),
            )
            if value
        ]
        if unsupported_filters:
            raise ValueError(
                "Franklin CIO exact-case retrieval does not apply "
                + ", ".join(unsupported_filters)
            )
        values["case_number"] = args.query
    elif adapter_command == "document":
        if not args.case_number:
            raise ValueError(
                "Franklin CIO document download requires --case-number"
            )
        if not args.destination:
            raise ValueError(
                "Franklin CIO document download requires --destination"
            )
        values.update(
            case_number=args.case_number,
            document_id=args.query,
            destination=args.destination,
            overwrite=bool(args.overwrite),
        )
    elif adapter_command == "probe":
        values["case_number"] = query_ohio_franklin_courts.PROBE_CASE_NUMBER
    return argparse.Namespace(**values)


def _franklin_municipal_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared discovery and case operations to FCMC Clerk search."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", "39049"}:
        raise ValueError(
            "Franklin Municipal Court serves Franklin County, Ohio (GEOID 39049)"
        )
    if (
        args.court_id
        and args.court_id != query_ohio_franklin_municipal.COURT_ID
    ):
        raise ValueError(
            "Franklin Municipal Court uses court ID "
            f"{query_ohio_franklin_municipal.COURT_ID}"
        )

    command = adapter_command
    selector = str(args.query or "").strip()
    if command == "search":
        field = (
            str(args.search_field or "").strip().casefold().replace("_", "-")
        )
        aliases = {
            "": "person",
            "auto": "person",
            "name": "person",
            "party": "person",
            "person": "person",
            "company": "company",
            "organization": "company",
            "case": "case-search",
            "case-number": "case-search",
            "ticket": "ticket",
            "ticket-number": "ticket",
        }
        try:
            command = aliases[field]
        except KeyError as error:
            raise ValueError(
                "Franklin Municipal --search-field must be person, company, "
                "case-number, or ticket"
            ) from error
        if field in {"", "auto", "name", "party"} and args.entity_kind == "organization":
            command = "company"
        if args.cursor:
            raise ValueError(
                "Franklin Municipal search has no source continuation cursor"
            )
        if args.after or args.before:
            raise ValueError(
                "Franklin Municipal search exposes case year rather than a "
                "filed-date range; use --case-year"
            )

    values = vars(args).copy()
    values.update(
        command=command,
        output=None,
        json_out=False,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=3,
    )
    if command == "person":
        first_name = str(args.first_name or "").strip()
        if not first_name and "," in selector:
            selector, first_name = (
                part.strip() for part in selector.split(",", 1)
            )
        if not first_name:
            raise ValueError(
                "Franklin Municipal person search requires --first-name or "
                "a 'LAST, FIRST' selector"
            )
        values.update(last_name=selector, first_name=first_name)
    elif command == "company":
        values["company_name"] = selector
    elif command == "case-search":
        values["case_number"] = selector
    elif command == "ticket":
        values["ticket_number"] = selector
    elif command == "case":
        values["case_number"] = selector
    elif command == "summary-pdf":
        document_selector = selector.casefold().replace("_", "-")
        if document_selector not in {
            "case-summary",
            "generated-case-summary",
            "summary",
        }:
            raise ValueError(
                "Franklin Municipal download selector must identify the "
                "generated case summary"
            )
        if not args.case_number:
            raise ValueError(
                "Franklin Municipal case-summary download requires --case-number"
            )
        if not args.destination:
            raise ValueError(
                "Franklin Municipal case-summary download requires --destination"
            )
        values.update(
            case_number=args.case_number,
            destination=args.destination,
        )

    if command in {"person", "company", "case-search", "ticket"}:
        values.update(
            middle_name=getattr(args, "middle_name", None),
            date_of_birth=args.date_of_birth,
            party_type=getattr(args, "party_type", None),
            case_type=args.case_type,
            year=getattr(args, "case_year", None),
            status=getattr(args, "case_status", None),
            shared_requested_limit=_caller_limit(args),
        )
    return argparse.Namespace(**values)


def _delaware_ohio_common_pleas_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to the headed Delaware CourtView helper."""

    adapter = query_ohio_delaware_common_pleas
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", adapter.COUNTY_FIPS}:
        raise ValueError(
            "Delaware County CourtView serves Ohio county GEOID "
            f"{adapter.COUNTY_FIPS}"
        )
    if args.court_id and args.court_id != adapter.COURT_ID:
        raise ValueError(
            f"Delaware County CourtView uses court ID {adapter.COURT_ID}"
        )

    command = adapter_command
    selector = str(args.query or "").strip()
    if command == "search":
        field = (
            str(args.search_field or "").strip().casefold().replace("_", "-")
        )
        if field in {"company", "organization"} or (
            field in {"", "auto", "name", "party", "party-name"}
            and args.entity_kind == "organization"
        ):
            command = "search-company"
        elif field in {
            "",
            "auto",
            "name",
            "party",
            "party-name",
            "person",
            "last-name",
        }:
            command = "search-party"
        else:
            raise ValueError(
                "Delaware CourtView --search-field must identify a person "
                "or company party search"
            )

    values = vars(args).copy()
    values.update(
        command=command,
        output=None,
        json_out=False,
        input=None,
        browser_timeout=max(float(args.timeout), adapter.DEFAULT_BROWSER_TIMEOUT),
    )
    if command in {"search-party", "search-company"}:
        values.update(
            case_type=[args.case_type] if args.case_type else [],
            case_status=(
                [args.case_status]
                if getattr(args, "case_status", None)
                else []
            ),
            party_type=(
                [args.party_type]
                if getattr(args, "party_type", None)
                else []
            ),
            filed_from=(adapter._date_arg(args.after) if args.after else None),
            filed_to=(adapter._date_arg(args.before) if args.before else None),
            limit=_caller_limit(args),
            cursor=args.cursor,
        )
        if command == "search-party":
            dob = (
                adapter._date_arg(args.date_of_birth)
                if args.date_of_birth
                else None
            )
            values.update(
                last_name=selector,
                first_name=args.first_name,
                middle_name=getattr(args, "middle_name", None),
                suffix=getattr(args, "name_suffix", None),
                dob_from=dob,
                dob_to=dob,
                dod_from=None,
                dod_to=None,
            )
        else:
            values["company_name"] = selector
    elif command in {"case", "docket", "documents"}:
        values["case_number"] = selector
    elif command == "document":
        if not args.case_number:
            raise ValueError(
                "Delaware CourtView document download requires --case-number"
            )
        if not args.destination:
            raise ValueError(
                "Delaware CourtView document download requires --destination"
            )
        values.update(
            case_number=args.case_number,
            document_id=selector,
            document_output=Path(args.destination),
        )
    return argparse.Namespace(**values)


def _licking_common_pleas_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate verified Licking source discovery and anonymous probing."""

    adapter = query_ohio_licking_common_pleas
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", adapter.COUNTY_FIPS}:
        raise ValueError(
            "Licking Common Pleas serves Ohio county GEOID "
            f"{adapter.COUNTY_FIPS}"
        )
    if args.court_id and args.court_id != adapter.COURT_ID:
        raise ValueError(
            f"Licking Common Pleas uses court ID {adapter.COURT_ID}"
        )
    return argparse.Namespace(
        command=adapter_command,
        input=None,
        timeout=args.timeout,
        output=None,
        json_out=False,
    )


def _franklin_probate_case_selector(value: str) -> tuple[str, str]:
    match = re.fullmatch(
        r"\s*(\d{1,6})(?:[\s/-]+([A-Za-z0-9]{1,2}))?\s*",
        value,
    )
    if match is None:
        raise ValueError(
            "Franklin Probate case selectors use a numeric case number and "
            "an optional one- or two-character suffix"
        )
    return match.group(1), (match.group(2) or "").upper()


def _franklin_probate_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared discovery and exact-case operations to NetData."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "39", "OH", "US-OH", "39049"}:
        raise ValueError(
            "Franklin Probate Court serves Franklin County GEOID 39049"
        )
    if args.court_id and args.court_id != query_ohio_franklin_probate.COURT_ID:
        raise ValueError(
            "Franklin Probate Court uses court ID "
            f"{query_ohio_franklin_probate.COURT_ID}"
        )

    selector = str(args.query or "").strip()
    command = adapter_command
    if command == "search":
        selected_field = (
            str(args.search_field or "").strip().casefold().replace("_", "-")
        )
        if args.case_type and selected_field in {"", "auto", "name"}:
            selected_field = "type"
        field_aliases = {
            "": "name",
            "auto": "name",
            "name": "name",
            "case-name": "name",
            "case": "number",
            "case-number": "number",
            "number": "number",
            "attorney": "attorney",
            "fiduciary": "fiduciary",
            "opened": "opened",
            "date-opened": "opened",
            "type": "type",
            "case-type": "type",
        }
        try:
            command = field_aliases[selected_field]
        except KeyError as error:
            raise ValueError(
                "Franklin Probate --search-field must be name, case-number, "
                "attorney, fiduciary, opened, or case-type"
            ) from error

    if command in {"source", "probe"}:
        argv = [command]
    elif command in {"case", "docket", "number"}:
        case_number, suffix = _franklin_probate_case_selector(selector)
        argv = [command, case_number]
        if suffix:
            argv.extend(["--suffix", suffix])
    elif command in {"name", "attorney", "fiduciary"}:
        if args.after or args.before or args.case_type:
            raise ValueError(
                f"Franklin Probate {command} index does not apply date or "
                "case-type filters"
            )
        if not selector:
            raise ValueError(f"Franklin Probate {command} search requires a term")
        argv = [command, selector]
    elif command == "opened":
        dates = {
            str(value).strip()
            for value in (selector, args.after, args.before)
            if value not in (None, "", "*")
        }
        if len(dates) != 1:
            raise ValueError(
                "Franklin Probate opened-date search uses one exact date"
            )
        argv = ["opened", next(iter(dates))]
    elif command == "type":
        if args.after or args.before:
            raise ValueError(
                "Franklin Probate case-type index does not apply date filters"
            )
        case_type = str(args.case_type or selector).strip().upper()
        argv = ["type", case_type]
    else:
        raise ValueError(
            f"Franklin Probate does not translate shared {args.command}"
        )

    if command in query_ohio_franklin_probate.INDEX_ROUTES:
        caller_limit = _caller_limit(args)
        if caller_limit is not None:
            argv.extend(["--limit", str(caller_limit)])
        if args.cursor:
            argv.extend(["--cursor", args.cursor])
    argv.extend(
        [
            "--timeout",
            str(args.timeout),
            "--minimum-interval",
            str(args.minimum_interval),
            "--retry-attempts",
            "3",
        ]
    )
    try:
        return query_ohio_franklin_probate.build_parser().parse_args(argv)
    except SystemExit as error:
        raise ValueError(
            f"invalid Franklin Probate selector for {adapter_command}"
        ) from error


def _ohio_supreme_iso_date(value: str | None, option: str) -> str:
    """Translate a shared ISO date to the eCMS search form's date format."""

    if value is None:
        return ""
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"{option} must use YYYY-MM-DD") from error
    return parsed.strftime("%m-%d-%Y")


def _ohio_supreme_court_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared appellate operations to the verified eCMS adapter."""

    if args.case_type:
        raise ValueError(
            "Ohio Supreme Court eCMS does not expose the shared --case-type "
            "filter"
        )
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        retry_attempts=query_ohio_supreme_court.DEFAULT_MAX_RETRIES,
    )
    if adapter_command == "search":
        filed_from = _ohio_supreme_iso_date(args.after, "--after")
        filed_to = _ohio_supreme_iso_date(args.before, "--before")
        if filed_from and filed_to:
            lower = date.fromisoformat(str(args.after))
            upper = date.fromisoformat(str(args.before))
            if lower > upper:
                raise ValueError("--after must not be later than --before")

        selected = (
            str(args.search_field or "caption")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        fields = {
            "caption": "caption",
            "case": "case_number",
            "case-number": "case_number",
            "prior-case": "prior_case_number",
            "prior-case-number": "prior_case_number",
            "party-first-name": "party_first_name",
            "party-last-name": "party_last_name",
            "party-entity": "party_entity",
            "attorney-first-name": "attorney_first_name",
            "attorney-last-name": "attorney_last_name",
        }
        destination = fields.get(selected)
        if destination is None:
            raise ValueError(
                "Ohio Supreme Court eCMS --search-field must identify "
                "caption, case-number, prior-case-number, party-first-name, "
                "party-last-name, party-entity, attorney-first-name, or "
                "attorney-last-name"
            )
        caller_limit = (
            args.limit
            if getattr(args, "limit_explicit", False)
            else None
        )
        if args.max_records is not None:
            caller_limit = (
                min(caller_limit, args.max_records)
                if caller_limit is not None
                else args.max_records
            )
        values.update(
            case_number=None,
            caption=None,
            prior_case_number=None,
            party_first_name=None,
            party_last_name=None,
            party_entity=None,
            attorney_first_name=None,
            attorney_last_name=None,
            filed_from=filed_from,
            filed_to=filed_to,
            limit=caller_limit,
        )
        values[destination] = args.query
    elif adapter_command == "case":
        unsupported = [
            option
            for option, value in (
                ("--after", args.after),
                ("--before", args.before),
                ("--search-field", args.search_field),
                ("--document-type", getattr(args, "document_type", None)),
            )
            if value
        ]
        if unsupported:
            raise ValueError(
                "Ohio Supreme Court eCMS exact-case retrieval does not apply "
                + ", ".join(unsupported)
            )
        values.update(case_number=args.query)
    elif adapter_command == "document":
        if not args.case_number:
            raise ValueError(
                "Ohio Supreme Court eCMS download requires --case-number"
            )
        if not args.destination:
            raise ValueError(
                "Ohio Supreme Court eCMS download requires --destination"
            )
        section = getattr(args, "document_section", None)
        if section is None:
            raise ValueError(
                "Ohio Supreme Court eCMS download requires "
                "--document-section DocketItems or DecisionItems"
            )
        if args.after or args.before or args.search_field:
            raise ValueError(
                "Ohio Supreme Court eCMS document download does not apply "
                "--after, --before, or --search-field"
            )
        values.update(
            case_number=args.case_number,
            document_name=args.query,
            destination=Path(args.destination),
            section=section,
            overwrite=bool(args.overwrite),
        )
    return argparse.Namespace(**values)


def _ohio_reporter_decisions_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared publication operations to the Reporter adapter."""

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        retry_attempts=query_ohio_reporter_decisions.DEFAULT_MAX_RETRIES,
    )
    if adapter_command == "search":
        unsupported = [
            option
            for option, value in (
                ("--after", args.after),
                ("--before", args.before),
                ("--case-type", args.case_type),
                ("--document-type", getattr(args, "document_type", None)),
            )
            if value
        ]
        if unsupported:
            raise ValueError(
                "Ohio Reporter publication search does not apply "
                + ", ".join(unsupported)
            )

        court_slug = "all"
        if args.court_id:
            court_slugs = {
                details["court_id"]: details["slug"]
                for details in query_ohio_reporter_decisions.QUERY_SOURCES.values()
            }
            court_slug = court_slugs.get(args.court_id, "")
            if not court_slug:
                raise ValueError(
                    "Ohio Reporter --court-id must identify one of its "
                    "published deciding-source IDs"
                )

        selected = (
            str(args.search_field or "full-text")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        fields = {
            "full-text": "text",
            "text": "text",
            "query": "text",
            "case": "case_number",
            "case-number": "case_number",
            "author": "author",
            "topics": "topics",
            "issues": "topics",
            "topics-and-issues": "topics",
            "citation": "citation",
            "print-citation": "citation",
        }
        destination = fields.get(selected)
        if destination is None:
            raise ValueError(
                "Ohio Reporter --search-field must identify full-text, "
                "case-number, author, topics, or citation"
            )

        caller_limit = (
            args.limit if getattr(args, "limit_explicit", False) else None
        )
        if args.max_records is not None:
            caller_limit = (
                min(caller_limit, args.max_records)
                if caller_limit is not None
                else args.max_records
            )
        values.update(
            text=None,
            source=court_slug,
            year=None,
            year_from=None,
            year_to=None,
            county=args.county,
            case_number=None,
            author=None,
            topics=None,
            citation=None,
            limit=caller_limit,
            cursor=args.cursor,
        )
        values[destination] = args.query
    elif adapter_command in {"publication", "document"}:
        unsupported = [
            option
            for option, value in (
                ("--after", args.after),
                ("--before", args.before),
                ("--case-type", args.case_type),
                ("--search-field", args.search_field),
                ("--court-id", args.court_id),
                ("--county", args.county),
                ("--document-type", getattr(args, "document_type", None)),
            )
            if value
        ]
        if unsupported:
            raise ValueError(
                "Ohio Reporter exact publication retrieval does not apply "
                + ", ".join(unsupported)
            )
        values["webcite"] = args.query
        if adapter_command == "document":
            if not args.destination:
                raise ValueError(
                    "Ohio Reporter publication download requires --destination"
                )
            values.update(
                destination=Path(args.destination),
                overwrite=bool(args.overwrite),
            )
    return argparse.Namespace(**values)


def _new_mexico_case_lookup_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors without creating a result-following loop."""

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        retry_attempts=query_new_mexico_case_lookup.DEFAULT_MAX_RETRIES,
    )
    if adapter_command == "search":
        unsupported = [
            option
            for option, value in (
                ("--after", args.after),
                ("--before", args.before),
                ("--case-type", args.case_type),
                ("--court-id", args.court_id),
                ("--county", args.county),
                ("--trial-court", args.trial_court),
                ("--plate-state", args.plate_state),
                ("--partial", args.partial),
                ("--phonetic", args.phonetic),
            )
            if value
        ]
        selected_field = (
            str(args.search_field or "party")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        if selected_field not in {"party", "party-name", "name"}:
            unsupported.append("--search-field")
        if unsupported:
            raise ValueError(
                "New Mexico Case Lookup party search does not apply "
                + ", ".join(unsupported)
            )
        party_name = " ".join(
            part
            for part in (
                str(args.query or "").strip(),
                str(args.first_name or "").strip(),
            )
            if part
        )
        caller_limit = _caller_limit(args)
        requested_page_size = (
            caller_limit
            if caller_limit is not None
            else query_new_mexico_case_lookup.DEFAULT_NATIVE_PAGE_SIZE
        )
        native_page_size = next(
            (
                size
                for size in query_new_mexico_case_lookup.NATIVE_PAGE_SIZES
                if size >= requested_page_size
            ),
            query_new_mexico_case_lookup.NATIVE_PAGE_SIZES[-1],
        )
        values.update(
            party_name=party_name,
            date_of_birth=args.date_of_birth,
            birth_year=None,
            drivers_license=args.drivers_license,
            drivers_license_state=None,
            native_page_size=native_page_size,
            limit=caller_limit,
        )
    elif adapter_command == "case":
        unsupported = [
            option
            for option, value in (
                ("--after", args.after),
                ("--before", args.before),
                ("--case-type", args.case_type),
                ("--court-id", args.court_id),
                ("--county", args.county),
                ("--trial-court", args.trial_court),
                ("--search-field", args.search_field),
                ("--first-name", args.first_name),
                ("--date-of-birth", args.date_of_birth),
                ("--drivers-license", args.drivers_license),
            )
            if value
        ]
        if unsupported:
            raise ValueError(
                "New Mexico Case Lookup exact-case retrieval does not apply "
                + ", ".join(unsupported)
            )
        values.update(case_number=args.query, limit=None)
    return argparse.Namespace(**values)


def _connecticut_civil_family_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to verified Connecticut portal routes."""

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        retry_attempts=query_connecticut_civil_family.DEFAULT_RETRY_ATTEMPTS,
    )
    unsupported = [
        option
        for option, value in (
            ("--after", args.after),
            ("--before", args.before),
            ("--court-id", args.court_id),
            ("--county", args.county),
            ("--trial-court", args.trial_court),
            ("--date-of-birth", args.date_of_birth),
            ("--drivers-license", args.drivers_license),
            ("--plate-state", args.plate_state),
        )
        if value
    ]
    if adapter_command == "search":
        selected_field = (
            str(args.search_field or "party-name")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        if selected_field not in {"party", "party-name", "name"}:
            unsupported.append("--search-field")
        if args.partial and args.phonetic:
            raise ValueError(
                "Connecticut party search accepts one name-match mode"
            )
        if unsupported:
            raise ValueError(
                "Connecticut Civil/Family party search does not apply "
                + ", ".join(unsupported)
            )
        values.update(
            last_name=args.query,
            first_name=args.first_name,
            match=(
                "soundex"
                if args.phonetic
                else "contains"
                if args.partial
                else "exact"
            ),
            location=args.courthouse or "ALL",
            category="ALL",
            case_type=args.case_type or "All",
            sort="party_name",
            limit=_caller_limit(args),
            cursor=args.cursor,
        )
    elif adapter_command == "case":
        for option, value in (
            ("--search-field", args.search_field),
            ("--first-name", args.first_name),
            ("--courthouse", args.courthouse),
            ("--partial", args.partial),
            ("--phonetic", args.phonetic),
            ("--cursor", args.cursor),
        ):
            if value:
                unsupported.append(option)
        if unsupported:
            raise ValueError(
                "Connecticut exact-docket retrieval does not apply "
                + ", ".join(unsupported)
            )
        values["docket"] = args.query
    elif adapter_command == "document":
        if unsupported:
            raise ValueError(
                "Connecticut filing download does not apply "
                + ", ".join(unsupported)
            )
        if not args.destination:
            raise ValueError(
                "Connecticut filing download requires --destination"
            )
        values.update(
            document_number=args.query,
            docket=args.case_number or None,
            pdf_output=Path(args.destination),
        )
    return argparse.Namespace(**values)


def _palm_beach_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the unified court surface to Palm Beach eCaseView."""
    if args.after or args.before or args.case_type:
        raise ValueError(
            "Palm Beach eCaseView does not expose the unified --after, "
            "--before, or --case-type filters; use its supported party or "
            "full-case-number selector"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
    )
    effective_limit = (
        min(args.limit, args.max_records)
        if args.max_records is not None
        else args.limit
    )
    if adapter_command == "search":
        values.update(
            query=args.query,
            search_scope="party",
            match_mode="exact",
            first_name=None,
            limit=effective_limit,
            cursor=args.cursor,
        )
    elif adapter_command in {"case", "docket", "documents"}:
        values["case_number"] = args.query
        if adapter_command in {"docket", "documents"}:
            values.update(
                limit=effective_limit,
                cursor=args.cursor,
            )
    elif adapter_command == "download":
        if not args.case_number:
            raise ValueError("Palm Beach document download requires --case-number")
        if not args.destination:
            raise ValueError("Palm Beach document download requires --destination")
        values.update(
            case_number=args.case_number,
            din=args.query,
            destination=Path(args.destination),
        )
    return argparse.Namespace(**values)


def _los_angeles_probate_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    prefix = "la-probate:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError(
            "Los Angeles probate cursor must have form la-probate:offset:N"
        )
    return int(cursor[len(prefix) :])


def _los_angeles_probate_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate exact case-scoped router operations to the probate adapter."""

    values = vars(args).copy()
    caller_limit = args.limit if getattr(args, "limit_explicit", False) else None
    if args.max_records is not None:
        caller_limit = (
            min(caller_limit, args.max_records)
            if caller_limit is not None
            else args.max_records
        )
    values.update(
        command=adapter_command,
        case_number=args.query,
        courthouse=getattr(args, "courthouse", None),
        limit=caller_limit,
        offset=_los_angeles_probate_offset(args.cursor),
        view=getattr(args, "view", "all"),
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _los_angeles_civil_offset(
    cursor: str | None,
    *,
    prefix: str,
) -> int:
    if cursor is None:
        return 0
    marker = f"{prefix}:"
    if not cursor.startswith(marker) or not cursor[len(marker) :].isdigit():
        raise ValueError(f"Los Angeles civil cursor must have form {prefix}:N")
    return int(cursor[len(marker) :])


def _los_angeles_civil_exact_date(
    args: argparse.Namespace,
) -> str | None:
    selected = [
        value
        for value in (
            getattr(args, "hearing_date", None),
            args.after,
            args.before,
        )
        if value
    ]
    if len(set(selected)) > 1:
        raise ValueError(
            "Los Angeles ruling date selectors must identify one exact date"
        )
    if not selected:
        return None
    return (
        query_los_angeles_court.datetime.strptime(
            selected[0],
            "%Y-%m-%d",
        )
        .date()
        .isoformat()
    )


def _los_angeles_civil_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared exact-case and current-ruling operations."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "06",
        "CA",
        query_los_angeles_court.COUNTY_GEOID,
    }:
        raise ValueError(
            "Los Angeles Superior Court civil records cover county GEOID "
            f"{query_los_angeles_court.COUNTY_GEOID}"
        )
    if args.court_id and args.court_id != query_los_angeles_court.COURT_ID:
        raise ValueError(
            f"Los Angeles civil records use court ID {query_los_angeles_court.COURT_ID}"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        max_attempts=3,
        retry_backoff=0.5,
    )
    caller_limit = args.limit if args.limit_explicit else None
    if args.max_records is not None:
        caller_limit = (
            min(caller_limit, args.max_records)
            if caller_limit is not None
            else args.max_records
        )

    if adapter_command == "case":
        values.update(
            case_number=" ".join(args.query.split()).strip(),
            courthouse=args.courthouse,
            limit=caller_limit,
            offset=_los_angeles_civil_offset(
                args.cursor,
                prefix="la-civil-case-entry",
            ),
        )
        return argparse.Namespace(**values)

    if adapter_command == "rulings":
        selection = " ".join(args.query.split()).strip()
        exact_date = _los_angeles_civil_exact_date(args)
        selection_offset = _los_angeles_civil_offset(
            args.cursor,
            prefix="la-tentative-selection",
        )
        if selection.casefold() != "all":
            if selection_offset:
                raise ValueError(
                    "Los Angeles exact ruling selections do not use a cursor"
                )
            if exact_date is not None:
                source_date = query_los_angeles_court.datetime.strptime(
                    exact_date,
                    "%Y-%m-%d",
                ).strftime("%m/%d/%Y")
                if source_date not in selection:
                    raise ValueError(
                        "Los Angeles ruling selection and exact date disagree"
                    )
            caller_limit = None
        elif exact_date is not None:
            raise ValueError(
                "Date-filtered Los Angeles rulings require one exact current "
                "selection; list selections with the direct adapter first"
            )
        values.update(
            selection=selection,
            max_selections=caller_limit,
            selection_offset=selection_offset,
        )
        return argparse.Namespace(**values)

    raise ValueError(f"unsupported Los Angeles civil command: {adapter_command}")


def _texas_tames_court_code(court_id: str | None) -> str | None:
    if not court_id:
        return None
    prefix = "tx-appellate-"
    value = court_id[len(prefix) :] if court_id.startswith(prefix) else court_id
    return query_texas_appellate.normalize_court_code(value)


def _texas_tames_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the shared court surface to Texas TAMES selectors."""

    values = vars(args).copy()
    court_code = _texas_tames_court_code(args.court_id)
    caller_limit = args.limit
    if args.max_records is not None:
        caller_limit = min(caller_limit, args.max_records)
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
    )
    if adapter_command == "search":
        values.update(
            query=args.query,
            scope=args.search_scope or "style",
            style_other=args.style_other,
            case_type=args.case_type or "both",
            exclude_inactive=args.exclude_inactive,
            date_from=args.after,
            date_to=args.before,
            courts=[court_code] if court_code else None,
            originating_coa=args.originating_coa,
            county=args.county,
            trial_court=args.trial_court,
            limit=caller_limit,
            cursor=args.cursor,
        )
    elif adapter_command in {"case", "docket", "documents"}:
        values.update(
            case_number=args.query,
            court_code=court_code,
        )
    elif adapter_command == "download":
        if not args.case_number:
            raise ValueError("Texas TAMES document download requires --case-number")
        if not args.destination:
            raise ValueError("Texas TAMES document download requires --destination")
        values.update(
            case_number=args.case_number,
            document_id=args.query,
            destination=Path(args.destination),
            court_code=court_code,
        )
    return argparse.Namespace(**values)


def _texas_supreme_publications_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to the official Supreme release pages."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "48", "TX", "US-TX"}:
        raise ValueError(
            "Texas Supreme Court publications have statewide Texas scope"
        )
    if args.court_id and (
        str(args.court_id).strip().casefold()
        != query_texas_supreme_publications.COURT_ID.casefold()
    ):
        raise ValueError(
            "Texas Supreme publications --court-id must identify "
            f"{query_texas_supreme_publications.COURT_ID}"
        )

    runtime = {
        "timeout": args.timeout,
        "minimum_interval": max(
            args.minimum_interval,
            query_texas_supreme_publications.DEFAULT_MINIMUM_INTERVAL,
        ),
        "max_attempts": query_texas_supreme_publications.DEFAULT_MAX_ATTEMPTS,
        "output": None,
        "json_out": False,
    }
    selector = " ".join(str(args.query or "").split()).strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "source",
    }
    caller_limit = _caller_limit(args)

    if adapter_command == "download":
        if not args.destination:
            raise ValueError(
                "Texas Supreme publication download requires "
                "--destination"
            )
        return argparse.Namespace(
            command="download",
            document_url=selector,
            destination=Path(args.destination),
            overwrite=args.overwrite,
            **runtime,
        )

    if adapter_command == "discovery":
        discovery_selector = selector.casefold()
        if discovery_selector in {"years", "archives", "historical"}:
            return argparse.Namespace(command="years", **runtime)
        if discovery_selector not in {
            "",
            "*",
            "all",
            "manifest",
            "routes",
            "source",
            "sources",
        }:
            raise ValueError(
                "Texas Supreme publication discovery accepts source or years"
            )
        return argparse.Namespace(command="source", **runtime)

    if adapter_command == "probe":
        if not selector_is_all and selector.casefold() != "probe":
            raise ValueError(
                "Texas Supreme publication probe does not take a selector"
            )
        return argparse.Namespace(command="probe", **runtime)

    if adapter_command == "release":
        return argparse.Namespace(
            command="release",
            release_date=selector,
            **runtime,
        )

    if adapter_command != "search":
        raise ValueError(
            f"unsupported Texas Supreme publication operation {adapter_command}"
        )
    if not args.after and not args.before:
        raise ValueError(
            "Texas Supreme publication search requires --after or --before "
            "to select annual release pages"
        )

    exact_case = args.command in {"case", "documents"}
    case_number = selector if exact_case else None
    document_types: list[str] = []
    if args.command == "documents" and getattr(args, "document_type", None):
        document_types.append(str(args.document_type))
    case_type = str(args.case_type or "").strip().casefold().replace("-", "_")
    if case_type not in {"", "all", "appellate", "supreme", "civil"}:
        document_types.append(case_type)
    return argparse.Namespace(
        command="search",
        query="*" if exact_case else selector,
        case_number=case_number,
        document_type=document_types or None,
        year=None,
        date_from=args.after,
        date_to=args.before,
        limit=caller_limit,
        cursor=args.cursor,
        **runtime,
    )


def _san_mateo_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    prefix = "midx:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError("San Mateo MIDX cursor must have form midx:offset:N")
    return int(cursor[len(prefix) :])


def _san_mateo_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate exact case, business, and person selectors to MIDX."""

    if args.case_type:
        raise ValueError("San Mateo MIDX does not publish case type in index results")
    if args.after or args.before:
        raise ValueError(
            "Use query_san_mateo_midx.py for its native five-day filing-date selector"
        )
    if args.court_id and args.court_id != query_san_mateo_midx.COURT_ID:
        raise ValueError(f"San Mateo MIDX covers only {query_san_mateo_midx.COURT_ID}")

    caller_limit = args.limit if getattr(args, "limit_explicit", False) else None
    if args.max_records is not None:
        caller_limit = (
            min(caller_limit, args.max_records)
            if caller_limit is not None
            else args.max_records
        )
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        max_attempts=3,
        limit=caller_limit,
        offset=_san_mateo_offset(args.cursor),
        case_number=None,
        first_name=None,
        last_name=None,
        business_name=None,
        filed_from=None,
        filed_to=None,
    )
    if adapter_command == "search":
        if args.first_name:
            values.update(
                first_name=args.first_name,
                last_name=args.query,
            )
        else:
            values["business_name"] = args.query
    elif adapter_command == "case":
        values["case_number"] = args.query
    return argparse.Namespace(**values)


def _caller_limit(args: argparse.Namespace) -> int | None:
    value = args.limit if getattr(args, "limit_explicit", False) else None
    if args.max_records is not None:
        value = min(value, args.max_records) if value is not None else args.max_records
    return value


def _denver_county_docket_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    match = re.fullmatch(r"denver-county-docket:offset:(\d+)", cursor)
    if match is None:
        raise ValueError(
            "Denver County Court cursor must use denver-county-docket:offset:N"
        )
    return int(match.group(1))


def _denver_county_docket_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate one courtroom/date calendar request to the daily docket."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "08",
        "CO",
        "08031",
    }:
        raise ValueError("Denver County Court covers Denver County GEOID 08031")
    if args.court_id and args.court_id != query_denver_county_court.COURT_ID:
        raise ValueError(
            f"Denver County Court uses court ID {query_denver_county_court.COURT_ID}"
        )
    hearing_date = getattr(args, "hearing_date", None)
    if not hearing_date:
        raise ValueError("Denver County Court calendar requires --hearing-date")
    if any(value and value != hearing_date for value in (args.after, args.before)):
        raise ValueError(
            "Denver County Court accepts one exact hearing date; "
            "--hearing-date, --after, and --before must agree when combined"
        )
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        courtroom=args.query,
        court_date=hearing_date,
        limit=_caller_limit(args),
        offset=_denver_county_docket_offset(args.cursor),
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _colorado_judicial_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the common name search into Colorado's docket filters."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "08",
        "CO",
    }:
        raise ValueError("Colorado Judicial docket search covers state GEOID 08")
    if args.search_scope not in {None, "party", "attorney"}:
        raise ValueError(
            "Colorado Judicial name search supports party or attorney scope"
        )
    date_range = None
    specific_date = None
    if args.after or args.before:
        if not args.after or not args.before or args.after != args.before:
            raise ValueError(
                "Colorado Judicial can represent --after and --before only "
                "when both select the same hearing date"
            )
        date_range = "specific_date"
        specific_date = args.after
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        judicial_district=None,
        county=args.county,
        courthouse=args.courthouse,
        court_type=None,
        division=None,
        date_range=date_range,
        specific_date=specific_date,
        case_year=None,
        case_class=args.case_type,
        case_sequence=None,
        party_first_name=None,
        party_last_name=None,
        business_name=None,
        attorney_bar_number=None,
        attorney_first_name=None,
        attorney_last_name=None,
        limit=_caller_limit(args),
        max_attempts=3,
        output=None,
        json_out=False,
    )
    if args.search_scope == "attorney":
        values.update(
            attorney_first_name=args.first_name,
            attorney_last_name=args.query,
        )
    elif args.entity_kind == "organization":
        values["business_name"] = args.query
    else:
        values.update(
            party_first_name=args.first_name,
            party_last_name=args.query,
        )
    return argparse.Namespace(**values)


def _pa_ujs_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate exact cases and party/organization searches to PA UJS."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "42",
        "PA",
    }:
        raise ValueError("Pennsylvania UJS covers state GEOID 42")
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        max_attempts=3,
        limit=_caller_limit(args),
    )
    if adapter_command == "search":
        entity_kind = getattr(args, "entity_kind", "person")
        if entity_kind == "organization":
            values.update(
                command="organization",
                organization_name=args.query,
                county=args.county,
                filed_after=args.after,
                filed_before=args.before,
                docket_type=None,
                case_category=args.case_type,
                case_status=None,
            )
        else:
            values.update(
                command="person",
                last_name=args.query,
                first_name=args.first_name,
                date_of_birth=None,
                county=args.county,
                filed_after=args.after,
                filed_before=args.before,
                docket_type=None,
                case_status=None,
            )
    elif adapter_command == "case":
        values["docket_number"] = args.query
    elif adapter_command == "report":
        if not args.case_number:
            raise ValueError("Pennsylvania UJS report download requires --case-number")
        if not args.destination:
            raise ValueError("Pennsylvania UJS report download requires --destination")
        report_kinds = {
            "docket_sheet": "docket_sheet",
            "court_summary": "court_summary",
        }
        kind = report_kinds.get(args.query.casefold())
        if kind is None:
            raise ValueError(
                "Pennsylvania UJS document ID must be docket_sheet or court_summary"
            )
        values.update(
            docket_number=args.case_number,
            destination=Path(args.destination),
            kind=kind,
        )
    return argparse.Namespace(**values)


def _courtconnect_page(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    match = re.search(r"(?:PageNo=|:page:)(\d+)(?:\D|$)", cursor)
    if match is None:
        raise ValueError(
            "Delaware CourtConnect cursor must contain PageNo=N or :page:N"
        )
    page = int(match.group(1))
    if page <= 0:
        raise ValueError("Delaware CourtConnect page must be positive")
    return page


def _delaware_courtconnect_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate party and exact-case operations to CourtConnect."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "10",
        "DE",
    }:
        raise ValueError("Delaware CourtConnect covers state GEOID 10")
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        max_attempts=3,
        limit=_caller_limit(args),
    )
    if adapter_command == "cases":
        first_name = (
            None
            if getattr(args, "entity_kind", "person") == "organization"
            else args.first_name
        )
        values.update(
            last_name_or_company=args.query,
            first_name=first_name,
            middle_name=None,
            partial=getattr(args, "partial", False),
            phonetic=getattr(args, "phonetic", False),
            filed_after=args.after,
            filed_before=args.before,
            case_type=args.case_type or "ALL",
            page=_courtconnect_page(args.cursor),
        )
    elif adapter_command == "case":
        values.update(
            case_id=args.query,
            docket_after=args.after,
            docket_before=args.before,
        )
    return argparse.Namespace(**values)


def _dc_opinions_page(cursor: str | None) -> int:
    if cursor is None:
        return 0
    match = re.fullmatch(r"page:(\d+)", cursor)
    if match is None:
        raise ValueError("D.C. opinions cursor must use page:N")
    return int(match.group(1))


def _dc_opinions_type(args: argparse.Namespace) -> str:
    aliases = {
        "all": "all",
        "opinion": "opinions",
        "opinions": "opinions",
        "published_opinion": "opinions",
        "appellate_opinion": "opinions",
        "moj": "mojs",
        "mojs": "mojs",
        "memorandum": "mojs",
        "memorandums": "mojs",
        "memorandum_opinion_and_judgment": "mojs",
        "memorandum_opinion_and_judgment_index": "mojs",
    }
    requested = [
        value
        for value in (
            getattr(args, "case_type", None),
            (
                getattr(args, "document_type", None)
                if args.command == "documents"
                else None
            ),
        )
        if value
    ]
    normalized = {aliases.get(str(value).strip().casefold()) for value in requested}
    if None in normalized:
        raise ValueError("D.C. opinions type must be all, opinions, or mojs")
    if len(normalized) > 1:
        raise ValueError("D.C. opinions --case-type and --document-type disagree")
    return next(iter(normalized), "all")


def _dc_opinions_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared court operations to the official D.C. index."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "11",
        "DC",
        "11001",
    }:
        raise ValueError("D.C. Court of Appeals opinions cover jurisdiction 11/DC")
    if args.court_id and args.court_id != query_dc_opinions.COURT_ID:
        raise ValueError(f"D.C. opinions use court ID {query_dc_opinions.COURT_ID}")

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        max_attempts=3,
        retry_backoff=0.5,
    )
    if adapter_command == "download":
        if not args.destination:
            raise ValueError("D.C. opinion download requires --destination")
        values.update(
            url=args.query,
            destination=Path(args.destination),
        )
        return argparse.Namespace(**values)

    if bool(args.after) != bool(args.before):
        raise ValueError(
            "D.C. opinions date filtering requires both --after and --before"
        )
    exact_date = (
        args.after if args.after is not None and args.after == args.before else None
    )
    values.update(
        query=args.query,
        type=_dc_opinions_type(args),
        date=exact_date,
        date_from=None if exact_date else args.after,
        date_to=None if exact_date else args.before,
        page=_dc_opinions_page(args.cursor),
        all_pages=False,
        order="date",
        sort="desc",
    )
    return argparse.Namespace(**values)


def _dc_calendar_current_date() -> str:
    return (
        query_dc_superior_calendar.datetime.now(query_dc_superior_calendar.DC_TIMEZONE)
        .date()
        .isoformat()
    )


def _validate_dc_current_calendar_date(args: argparse.Namespace) -> None:
    """Accept date selectors only when they describe the current-day feeds."""

    current_date = _dc_calendar_current_date()
    selected = [
        value
        for value in (
            getattr(args, "hearing_date", None),
            args.after,
            args.before,
        )
        if value
    ]
    if any(value != current_date for value in selected):
        raise ValueError(
            "D.C. Superior Court hearing feeds publish the current day; "
            f"date selectors must be {current_date}"
        )


def _dc_calendar_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to one D.C. calendar representation."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "11",
        "DC",
        "11001",
    }:
        raise ValueError("D.C. court calendars cover jurisdiction 11/DC")

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        retry_attempts=3,
    )

    if args.source in {
        DC_TODAY_CALENDAR_SOURCE_ID,
        DC_CRIMINAL_CALENDAR_SOURCE_ID,
    }:
        if args.court_id and args.court_id != query_dc_superior_calendar.COURT_ID:
            raise ValueError(
                "D.C. Superior Court calendars use court ID "
                f"{query_dc_superior_calendar.COURT_ID}"
            )
        if args.case_type:
            raise ValueError(
                "D.C. calendar case-type taxonomy is source-published output, "
                "not a supported input filter"
            )
        _validate_dc_current_calendar_date(args)

        is_today = args.source == DC_TODAY_CALENDAR_SOURCE_ID
        supported_fields = (
            {"party", "case_number", "judge", "courtroom"}
            if is_today
            else {
                "defendant",
                "event",
                "charge",
                "time",
                "attorney",
                "case_number",
                "judge",
                "courtroom",
            }
        )
        default_field = (
            ("party" if is_today else "defendant")
            if args.command == "search"
            else "case_number"
        )
        selected_field = (
            str(args.search_field).strip().casefold().replace("-", "_")
            if args.search_field
            else default_field
        )
        if selected_field not in supported_fields:
            raise ValueError(
                "D.C. calendar --search-field must be one of "
                + ", ".join(sorted(supported_fields))
            )

        selector = " ".join(args.query.split()).strip()
        if args.command == "calendar" and selector.casefold() in {
            "*",
            "all",
            "today",
        }:
            selector = ""
        filters = {
            field: None
            for field in (
                "party",
                "defendant",
                "event",
                "charge",
                "time",
                "attorney",
                "case_number",
                "judge",
                "courtroom",
            )
        }
        filters[selected_field] = selector or None
        if args.courthouse:
            if filters["courtroom"] and filters["courtroom"] != args.courthouse:
                raise ValueError(
                    "D.C. calendar positional courtroom and --courthouse "
                    "selectors disagree"
                )
            filters["courtroom"] = args.courthouse
        values.update(
            **filters,
            page=None,
            cursor=args.cursor,
            max_pages=1,
            order=None,
            sort=None,
        )
        return argparse.Namespace(**values)

    if args.source == DC_TAX_CALENDAR_SOURCE_ID:
        values.update(family="tax")
        return argparse.Namespace(**values)

    if args.source == DC_APPEALS_CALENDAR_SOURCE_ID:
        selected_year: int | None = None
        selector = " ".join(args.query.split()).strip()
        if re.fullmatch(r"\d{4}", selector):
            selected_year = int(selector)
        elif selector.casefold() not in {"*", "all", "appeals", "calendar", "current"}:
            raise ValueError(
                "D.C. Court of Appeals calendar selector must be a four-digit "
                "year or all"
            )
        date_values = [
            value
            for value in (
                getattr(args, "hearing_date", None),
                args.after,
                args.before,
            )
            if value
        ]
        date_years = {int(value[:4]) for value in date_values}
        if len(date_years) > 1:
            raise ValueError(
                "D.C. Court of Appeals date selectors must fall in one year"
            )
        if date_years:
            date_year = next(iter(date_years))
            if selected_year is not None and selected_year != date_year:
                raise ValueError(
                    "D.C. Court of Appeals year and date selectors disagree"
                )
            selected_year = date_year
        values.update(year=selected_year)
        return argparse.Namespace(**values)

    raise ValueError(f"unsupported D.C. calendar source: {args.source}")


def _fresno_exact_date(args: argparse.Namespace) -> str | None:
    selected = [
        value
        for value in (
            getattr(args, "hearing_date", None),
            args.after,
            args.before,
        )
        if value
    ]
    if len(set(selected)) > 1:
        raise ValueError("Fresno source date selectors must identify one exact date")
    if not selected:
        return None
    return query_fresno_superior_court._validate_iso_date(selected[0])


def _fresno_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to one Fresno court publication."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "06",
        "CA",
        query_fresno_superior_court.COUNTY_FIPS,
    }:
        raise ValueError(
            "Fresno Superior Court covers California county GEOID "
            f"{query_fresno_superior_court.COUNTY_FIPS}"
        )
    if args.court_id and args.court_id != query_fresno_superior_court.COURT_ID:
        raise ValueError(
            f"Fresno sources use court ID {query_fresno_superior_court.COURT_ID}"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        max_attempts=3,
        retry_backoff=0.5,
    )
    exact_date = _fresno_exact_date(args)

    if args.source == FRESNO_CALENDAR_SOURCE_ID:
        selector = " ".join(args.query.split()).strip()
        selector_date = (
            query_fresno_superior_court._validate_iso_date(selector)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", selector)
            else None
        )
        if selector_date is None and selector.casefold() not in {
            "*",
            "all",
            "calendar",
            "latest",
        }:
            raise ValueError(
                "Fresno daily-calendar selector must be an ISO date or latest"
            )
        if (
            selector_date is not None
            and exact_date is not None
            and selector_date != exact_date
        ):
            raise ValueError(
                "Fresno daily-calendar positional and date selectors disagree"
            )
        values.update(url=None, date=selector_date or exact_date)
        return argparse.Namespace(**values)

    if args.source == FRESNO_RULINGS_SOURCE_ID:
        selector = " ".join(args.query.split()).strip()
        selector_date = (
            query_fresno_superior_court._validate_iso_date(selector)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", selector)
            else None
        )
        department_text = args.courthouse
        if selector_date is None and selector.casefold() not in {
            "*",
            "all",
            "latest",
            "rulings",
        }:
            department_text = selector
        department_match = (
            re.fullmatch(
                r"(?:department|dept|d)?\s*(\d+)",
                str(department_text).strip(),
                re.I,
            )
            if department_text
            else None
        )
        if department_match is None:
            raise ValueError(
                "Fresno tentative-ruling calendar requires a department "
                "number as its selector or --courthouse"
            )
        if (
            selector_date is not None
            and exact_date is not None
            and selector_date != exact_date
        ):
            raise ValueError(
                "Fresno tentative-ruling positional and date selectors disagree"
            )
        values.update(
            url=None,
            department=int(department_match.group(1)),
            date=selector_date or exact_date,
        )
        return argparse.Namespace(**values)

    if args.source == FRESNO_PROBATE_SOURCE_ID:
        if getattr(args, "view", "all") != "all":
            raise ValueError(
                "Fresno Probate Examiner Notes return the complete case note "
                "set rather than future/past views"
            )
        hearing_date = (
            query_fresno_superior_court.datetime.strptime(
                exact_date,
                "%Y-%m-%d",
            ).strftime("%m/%d/%Y")
            if exact_date
            else None
        )
        values.update(
            case_number=" ".join(args.query.split()).strip(),
            hearing_date=hearing_date,
        )
        return argparse.Namespace(**values)

    raise ValueError(f"unsupported Fresno source: {args.source}")


def _orange_calendar_category(args: argparse.Namespace) -> str:
    value = str(args.case_type or "").strip().casefold().replace("_", "-")
    aliases = {
        "family-law": "family",
        "smallclaims": "small-claims",
        "small claims": "small-claims",
    }
    value = aliases.get(value, value)
    if value not in query_orange_county_court.CATEGORY_CODES:
        choices = ", ".join(query_orange_county_court.CATEGORY_CODES)
        raise ValueError(
            f"Orange County calendar queries require --case-type with one of: {choices}"
        )
    return value


def _orange_court_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to one Orange County court component."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "06",
        "CA",
        query_orange_county_court.COUNTY_FIPS,
    }:
        raise ValueError(
            "Orange County Superior Court covers California county GEOID "
            f"{query_orange_county_court.COUNTY_FIPS}"
        )
    if args.court_id and args.court_id != query_orange_county_court.COURT_ID:
        raise ValueError(
            f"Orange County sources use court ID {query_orange_county_court.COURT_ID}"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        retry_attempts=3,
    )

    if args.source == ORANGE_CALENDAR_SOURCE_ID:
        hearing_date = getattr(args, "hearing_date", None)
        if hearing_date and any(
            value and value != hearing_date for value in (args.after, args.before)
        ):
            raise ValueError(
                "Orange County exact hearing date and range selectors disagree"
            )
        selector = " ".join(args.query.split()).strip()
        wildcard = selector.casefold() in {"*", "all", "calendar", "latest"}
        search_field = str(args.search_field or "").strip().casefold()
        if search_field:
            search_field = search_field.replace("_", "-")
        if not search_field:
            search_field = {
                "search": "title",
                "case": "case-id",
                "calendar": "case-id",
            }[args.command]
        supported_fields = {
            "all",
            "case-id",
            "title",
            "location",
            "department",
            "hearing-time",
        }
        if search_field not in supported_fields:
            raise ValueError(
                "Orange County calendar --search-field must be one of: "
                + ", ".join(sorted(supported_fields))
            )
        selectors: dict[str, str | None] = {
            "case_id": None,
            "title": None,
            "location": args.courthouse,
            "department": None,
            "hearing_time": None,
        }
        if not wildcard and search_field != "all":
            selectors[search_field.replace("-", "_")] = selector

        requested_limits = [
            value
            for value in (
                args.limit if getattr(args, "limit_explicit", False) else None,
                args.max_records,
            )
            if value is not None
        ]
        values.update(
            category=_orange_calendar_category(args),
            case_year=None,
            date_from=hearing_date or args.after,
            date_to=hearing_date or args.before,
            limit=min(requested_limits) if requested_limits else None,
            cursor=args.cursor,
            **selectors,
        )
        return argparse.Namespace(**values)

    division = ORANGE_RULING_DIVISIONS_BY_SOURCE.get(args.source)
    if division:
        selector = " ".join(args.query.split()).strip()
        wildcard = selector.casefold() in {
            "*",
            "all",
            "latest",
            "rulings",
        }
        if adapter_command == "ruling-index":
            values.update(
                division=division,
                department=None if wildcard else selector,
            )
            return argparse.Namespace(**values)
        if wildcard:
            raise ValueError(
                "Orange County ruling document lookup requires a department "
                "selector; use calendar with all to list current artifacts"
            )
        values.update(
            division=division,
            department=selector,
            download=None,
            no_text=False,
        )
        return argparse.Namespace(**values)

    raise ValueError(f"unsupported Orange County source: {args.source}")


def _riverside_court_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared calendar and ruling operations to Riverside."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "06",
        "CA",
        query_riverside_court.COUNTY_FIPS,
    }:
        raise ValueError(
            "Riverside Superior Court covers California county GEOID "
            f"{query_riverside_court.COUNTY_FIPS}"
        )
    if args.court_id and args.court_id != query_riverside_court.COURT_ID:
        raise ValueError(
            f"Riverside sources use court ID {query_riverside_court.COURT_ID}"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        retry_attempts=3,
    )
    selector = " ".join(args.query.split()).strip()
    wildcard = selector.casefold() in {
        "*",
        "all",
        "calendar",
        "latest",
        "rulings",
    }

    if args.source == RIVERSIDE_CALENDAR_SOURCE_ID:
        hearing_date = getattr(args, "hearing_date", None)
        if hearing_date and any(
            value and value != hearing_date for value in (args.after, args.before)
        ):
            raise ValueError(
                "Riverside exact hearing date and range selectors disagree"
            )
        search_field = (
            str(args.search_field or "department").strip().casefold().replace("_", "-")
        )
        if search_field not in {
            "all",
            "department",
            "courthouse",
            "area-of-law",
        }:
            raise ValueError(
                "Riverside calendar --search-field must be all, department, "
                "courthouse, or area-of-law"
            )
        courthouse = args.courthouse
        department = None
        area_of_law = str(args.case_type).strip().casefold() if args.case_type else None
        if not wildcard and search_field != "all":
            if search_field == "department":
                department = selector
            elif search_field == "courthouse":
                courthouse = selector
            else:
                area_of_law = selector.casefold()
        if area_of_law and area_of_law not in {
            "civil",
            "criminal",
            "probate",
            "traffic",
        }:
            raise ValueError(
                "Riverside calendar area of law must be civil, criminal, "
                "probate, or traffic"
            )
        requested_limits = [
            value
            for value in (
                args.limit if getattr(args, "limit_explicit", False) else None,
                args.max_records,
            )
            if value is not None
        ]
        values.update(
            courthouse=courthouse,
            department=department,
            area_of_law=area_of_law,
            start_date=hearing_date or args.after,
            end_date=hearing_date or args.before,
            limit=min(requested_limits) if requested_limits else None,
            cursor=args.cursor,
        )
        return argparse.Namespace(**values)

    if args.source == RIVERSIDE_RULING_SOURCE_ID:
        if any((args.after, args.before, getattr(args, "hearing_date", None))):
            raise ValueError(
                "Riverside's ruling directory does not publish a reliable "
                "date filter; inspect each artifact's path and extracted "
                "hearing date"
            )
        if adapter_command == "ruling-index":
            values.update(department=None if wildcard else selector)
            return argparse.Namespace(**values)
        if wildcard:
            raise ValueError(
                "Riverside ruling document lookup requires a department; "
                "use calendar with all to list directory artifacts"
            )
        values.update(
            department=selector,
            download=(
                Path(args.destination) if getattr(args, "destination", None) else None
            ),
            no_text=False,
        )
        return argparse.Namespace(**values)

    raise ValueError(f"unsupported Riverside source: {args.source}")


def _qld_ecourts_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared civil case operations to Queensland eCourts."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "AU",
        "AUS",
        "QLD",
        "AU-QLD",
        "AUS-QLD",
    }:
        raise ValueError("Queensland eCourts covers Queensland, Australia")
    if args.after or args.before:
        raise ValueError(
            "Queensland eCourts exposes listing and party-entry date "
            "selectors rather than the unified filing-date range; use the "
            "direct adapter for those source-native dates"
        )
    if args.cursor:
        raise ValueError(
            "Queensland eCourts traverses its native pages within one request; "
            "it does not use a unified continuation cursor"
        )

    court_code = None
    if args.court_id:
        court_code = next(
            (
                code
                for code, court_id in query_qld_ecourts.COURT_IDS.items()
                if court_id == args.court_id
            ),
            None,
        )
        if court_code is None:
            raise ValueError(
                "Queensland eCourts court ID must be qld-supreme-court or "
                "qld-district-court"
            )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        output=None,
        json_out=False,
        court=court_code,
        location=args.courthouse,
    )
    if adapter_command == "case":
        values["file_number"] = " ".join(args.query.split()).strip()
        return argparse.Namespace(**values)

    if adapter_command != "search":
        raise ValueError(f"unsupported Queensland eCourts command: {adapter_command}")

    search_field = (
        str(args.search_field or "party-name").strip().casefold().replace("_", "-")
    )
    selectors = {
        "file_number": None,
        "party_name": None,
        "given_names": None,
        "second_party_name": None,
        "second_given_names": None,
    }
    if search_field in {"party", "party-name", "last-company-name"}:
        selectors["party_name"] = args.query
        selectors["given_names"] = args.first_name
    elif search_field in {"file", "file-number", "case-number"}:
        selectors["file_number"] = args.query
    elif search_field in {"second-party", "second-party-name"}:
        selectors["second_party_name"] = args.query
        selectors["second_given_names"] = args.first_name
    else:
        raise ValueError(
            "Queensland eCourts --search-field must be party-name, "
            "second-party-name, or file-number"
        )

    caller_limit = args.limit if getattr(args, "limit_explicit", False) else None
    if args.max_records is not None:
        caller_limit = (
            min(caller_limit, args.max_records)
            if caller_limit is not None
            else args.max_records
        )
    values.update(
        **selectors,
        current_location=None,
        category=args.case_type,
        party_role=None,
        party_date_from=None,
        second_party_role=None,
        listing_from=None,
        listing_to=None,
        include_details=False,
        limit=caller_limit,
    )
    return argparse.Namespace(**values)


def _wisconsin_court_directory_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared text search to Wisconsin's directory family."""

    if adapter_command != "search":
        raise ValueError(
            f"unsupported Wisconsin court-directory operation {adapter_command}"
        )
    jurisdiction = str(args.jurisdiction or "").strip()
    normalized_jurisdiction = jurisdiction.upper()
    if normalized_jurisdiction.startswith("US-GEOID-"):
        normalized_jurisdiction = normalized_jurisdiction.removeprefix(
            "US-GEOID-"
        )

    county_selectors: list[str] = []
    if normalized_jurisdiction not in {"", "WI", "55", "US-WI"}:
        if normalized_jurisdiction not in (
            query_wisconsin_court_directory.COUNTY_BY_GEOID
        ):
            raise ValueError(
                "Wisconsin court-directory jurisdiction must be Wisconsin "
                "or a Wisconsin county GEOID"
            )
        county_selectors.append(normalized_jurisdiction)
    if args.county:
        county_selectors.append(str(args.county))
    if args.court_id:
        county_selectors.append(str(args.court_id))

    resolved_counties = {
        query_wisconsin_court_directory.resolve_county_selector(value)
        for value in county_selectors
    }
    if len(resolved_counties) > 1:
        raise ValueError(
            "Wisconsin court-directory jurisdiction, county, and court ID "
            "selectors identify different counties"
        )
    county = next(iter(resolved_counties), None)

    selected = (
        str(args.search_field or "")
        .strip()
        .casefold()
        .replace("_", "-")
    )
    component_aliases = {
        "": None,
        "any": None,
        "all": None,
        "directory": None,
        "court": query_wisconsin_court_directory.CIRCUIT_COMPONENT,
        "circuit": query_wisconsin_court_directory.CIRCUIT_COMPONENT,
        "circuit-court": query_wisconsin_court_directory.CIRCUIT_COMPONENT,
        "office": query_wisconsin_court_directory.CIRCUIT_COMPONENT,
        "clerk": query_wisconsin_court_directory.CLERK_COMPONENT,
        "clerks": query_wisconsin_court_directory.CLERK_COMPONENT,
        "judge": query_wisconsin_court_directory.JUDGE_COMPONENT,
        "judges": query_wisconsin_court_directory.JUDGE_COMPONENT,
        "district": query_wisconsin_court_directory.DISTRICT_COMPONENT,
        "administrative-district": (
            query_wisconsin_court_directory.DISTRICT_COMPONENT
        ),
        "appellate": query_wisconsin_court_directory.APPEALS_COMPONENT,
        "court-of-appeals": query_wisconsin_court_directory.APPEALS_COMPONENT,
        "supreme": query_wisconsin_court_directory.STATE_OFFICE_COMPONENT,
        "state-office": query_wisconsin_court_directory.STATE_OFFICE_COMPONENT,
    }
    if selected not in component_aliases:
        raise ValueError(
            "Wisconsin court-directory --search-field must be directory, "
            "court, clerk, judge, district, appellate, supreme, or state-office"
        )
    component = component_aliases[selected]
    if any((args.after, args.before, args.case_type, args.cursor)):
        raise ValueError(
            "Wisconsin court-directory snapshots do not expose case, date, "
            "or continuation selectors"
        )
    if any(
        (
            args.first_name,
            args.courthouse,
            args.partial,
            args.phonetic,
            args.exclude_inactive,
        )
    ):
        raise ValueError(
            "Wisconsin court-directory shared search uses its text query, "
            "optional component, and optional county selector"
        )

    values = vars(args).copy()
    values.update(
        command="search",
        query=args.query,
        components=[component] if component else [],
        county=county,
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=max(
            args.minimum_interval,
            query_wisconsin_court_directory.DEFAULT_MINIMUM_INTERVAL,
        ),
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _georgia_court_directory_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared directory operations to Georgia's published views."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "13", "GA", "US-GA"}:
        if (
            len(jurisdiction) == 5
            and jurisdiction.isdigit()
            and jurisdiction.startswith("13")
        ):
            raise ValueError(
                "Georgia court-directory county GEOIDs do not identify the "
                "source's native county-name filter; use --county"
            )
        raise ValueError(
            "Georgia court-directory jurisdiction must be Georgia "
            "(13, GA, or US-GA)"
        )
    if args.court_id:
        raise ValueError(
            "Georgia court-directory records do not expose canonical court IDs"
        )
    if args.after or args.before or args.case_type:
        raise ValueError(
            "Georgia court-directory snapshots do not expose case type or "
            "filing-date fields"
        )
    unsupported_name_modes = (
        args.entity_kind != "person"
        or args.partial
        or args.phonetic
        or args.exclude_inactive
        or bool(args.date_of_birth)
        or bool(args.drivers_license)
        or bool(args.plate_state)
        or bool(args.violation_number)
        or bool(args.search_scope)
        or bool(args.style_other)
        or bool(args.originating_coa)
        or bool(args.trial_court)
        or bool(args.courthouse)
    )
    if unsupported_name_modes:
        raise ValueError(
            "Georgia court-directory lookups use the published personnel "
            "name and directory fields"
        )

    selector = str(getattr(args, "query", "") or "").strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "directory",
        "statewide",
    }
    search_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    runtime = {
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "max_attempts": 3,
        "retry_backoff": 0.5,
        "output": None,
        "json_out": False,
    }

    if adapter_command == "manifest":
        if not selector_is_all:
            raise ValueError(
                "Georgia court-directory discovery returns the source manifest; "
                "use shared search for personnel selectors"
            )
        if search_field not in {"", "directory", "manifest", "source"}:
            raise ValueError(
                "Georgia court-directory discovery --search-field must be "
                "directory, manifest, or source"
            )
        if (
            args.cursor
            or args.first_name
            or args.county
            or args.max_records is not None
            or args.limit_explicit
        ):
            raise ValueError(
                "Georgia court-directory discovery does not apply record "
                "filters, result bounds, or continuation cursors"
            )
        return argparse.Namespace(
            command="manifest",
            output=None,
            json_out=False,
        )

    if adapter_command == "probe":
        if not selector_is_all:
            raise ValueError(
                "Georgia court-directory probe is a bounded source contract "
                "check and does not apply a record selector"
            )
        if (
            search_field
            or args.cursor
            or args.first_name
            or args.county
            or args.max_records is not None
            or args.limit_explicit
        ):
            raise ValueError(
                "Georgia court-directory probe does not apply search filters "
                "or result-page controls"
            )
        return argparse.Namespace(command="probe", **runtime)

    if adapter_command == "detail":
        if selector_is_all:
            raise ValueError(
                "Georgia court-directory detail requires one native record ID"
            )
        if search_field not in {"", "id", "record-id", "detail"}:
            raise ValueError(
                "Georgia court-directory detail --search-field must identify "
                "a record ID"
            )
        if (
            args.cursor
            or args.first_name
            or args.county
            or args.max_records is not None
            or args.limit_explicit
        ):
            raise ValueError(
                "Georgia court-directory detail uses only the exact native "
                "record ID"
            )
        return argparse.Namespace(
            command="detail",
            record_id=selector,
            **runtime,
        )

    if adapter_command != "search":
        raise ValueError(
            f"unsupported Georgia court-directory operation {adapter_command}"
        )

    filters: dict[str, str | None] = {
        "first": None,
        "middle": None,
        "last": None,
        "city": None,
        "county": str(args.county or "").strip() or None,
        "circuit": None,
        "court_class": None,
        "directory_section": None,
    }
    if search_field in {"", "person", "name", "last", "last-name"}:
        if not selector_is_all:
            filters["last"] = selector
        if args.first_name:
            filters["first"] = str(args.first_name).strip()
    elif search_field in {"first", "first-name"}:
        if selector_is_all:
            raise ValueError(
                "Georgia court-directory first-name search needs a selector"
            )
        if args.first_name and (
            str(args.first_name).strip().casefold() != selector.casefold()
        ):
            raise ValueError(
                "Georgia court-directory first-name selectors conflict"
            )
        filters["first"] = selector
    elif search_field in {"middle", "middle-name"}:
        if selector_is_all:
            raise ValueError(
                "Georgia court-directory middle-name search needs a selector"
            )
        filters["middle"] = selector
    elif search_field == "city":
        if selector_is_all:
            raise ValueError(
                "Georgia court-directory city search needs a selector"
            )
        filters["city"] = selector
    elif search_field in {"county", "county-name"}:
        selected_county = None if selector_is_all else selector
        context_county = filters["county"]
        if selected_county and context_county and (
            selected_county.casefold() != context_county.casefold()
        ):
            raise ValueError(
                "Georgia court-directory county selectors conflict"
            )
        filters["county"] = selected_county or context_county
        if not filters["county"]:
            raise ValueError(
                "Georgia court-directory county search needs a selector"
            )
    elif search_field == "circuit":
        if selector_is_all:
            raise ValueError(
                "Georgia court-directory circuit search needs a selector"
            )
        filters["circuit"] = selector
    elif search_field in {"court-class", "class"}:
        if selector_is_all:
            raise ValueError(
                "Georgia court-directory court-class search needs a selector"
            )
        filters["court_class"] = selector
    elif search_field in {"directory-section", "section"}:
        if selector_is_all:
            raise ValueError(
                "Georgia court-directory section search needs a selector"
            )
        filters["directory_section"] = selector
    elif search_field in {"directory", "all"}:
        if not selector_is_all:
            raise ValueError(
                "Georgia court-directory full listing uses '*' or 'all'"
            )
    else:
        raise ValueError(
            "Georgia court-directory --search-field must be person, first, "
            "middle, last, city, county, circuit, court-class, "
            "directory-section, or directory"
        )

    selected_limit = _caller_limit(args)
    return argparse.Namespace(
        command="search",
        **filters,
        limit=(
            selected_limit
            if selected_limit is not None
            else query_georgia_court_directory.DEFAULT_LIMIT
        ),
        all=False,
        page_size=args.page_size,
        cursor=args.cursor,
        details=False,
        **runtime,
    )


def _georgia_court_access_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to Georgia's court-provider directories."""

    source_id = str(args.source)
    if source_id not in GEORGIA_COURT_ACCESS_SOURCE_IDS:
        raise ValueError(
            f"unsupported Georgia court-access source {source_id}"
        )
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "13", "GA", "US-GA"}:
        if (
            len(jurisdiction) == 5
            and jurisdiction.isdigit()
            and jurisdiction.startswith("13")
        ):
            raise ValueError(
                "Georgia court-access county GEOIDs do not identify the "
                "directory's native county-name filter; use --county"
            )
        raise ValueError(
            "Georgia court-access jurisdiction must be Georgia "
            "(13, GA, or US-GA)"
        )

    unsupported_selectors = (
        bool(args.court_id)
        or bool(args.courthouse)
        or bool(args.case_type)
        or bool(args.after)
        or bool(args.before)
        or bool(args.first_name)
        or args.entity_kind != "person"
        or args.partial
        or args.phonetic
        or args.exclude_inactive
        or bool(args.date_of_birth)
        or bool(args.drivers_license)
        or bool(args.plate_state)
        or bool(args.violation_number)
        or bool(args.search_scope)
        or bool(args.style_other)
        or bool(args.originating_coa)
        or bool(args.trial_court)
    )
    if unsupported_selectors:
        raise ValueError(
            "Georgia court-access routes expose current court, county, "
            "provider, and published-state directory fields"
        )

    selector = str(getattr(args, "query", "") or "").strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "directory",
        "statewide",
        "providers",
    }
    search_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    bounds_selected = (
        args.cursor is not None
        or args.max_records is not None
        or args.limit_explicit
    )
    runtime = {
        "source": source_id,
        "timeout": args.timeout,
        "minimum_interval": max(
            args.minimum_interval,
            query_georgia_court_access.DEFAULT_MINIMUM_INTERVAL,
        ),
        "max_attempts": query_georgia_court_access.DEFAULT_MAX_ATTEMPTS,
        "retry_backoff": 0.5,
        "output": None,
        "json_out": False,
    }

    if adapter_command in {"providers", "probe"}:
        if not selector_is_all:
            raise ValueError(
                f"Georgia court-access {adapter_command} returns a bounded "
                "source-wide snapshot and does not apply a record selector"
            )
        if search_field not in {
            "",
            "directory",
            "providers",
            "source",
            "probe",
        }:
            raise ValueError(
                "Georgia court-access discovery/probe --search-field must be "
                "directory, providers, source, or probe"
            )
        if args.county or bounds_selected:
            raise ValueError(
                "Georgia court-access discovery/probe does not apply county "
                "filters, result bounds, or continuation cursors"
            )
        return argparse.Namespace(command=adapter_command, **runtime)

    if adapter_command != "search":
        raise ValueError(
            f"unsupported Georgia court-access operation {adapter_command}"
        )

    county = str(args.county or "").strip() or None
    court_class: str | None = None
    provider: str | None = None
    published_state: str | None = None
    query_text = "*" if selector_is_all else selector

    if search_field in {"", "any", "text", "court", "directory"}:
        pass
    elif search_field in {"county", "county-name"}:
        selected_county = None if selector_is_all else selector
        if (
            selected_county
            and county
            and selected_county.casefold() != county.casefold()
        ):
            raise ValueError(
                "Georgia court-access county selectors conflict"
            )
        county = selected_county or county
        if not county:
            raise ValueError(
                "Georgia court-access county search needs a selector"
            )
        query_text = "*"
    elif search_field in {"court-class", "class"}:
        court_class = selector.casefold()
        if court_class not in {"state", "superior"}:
            raise ValueError(
                "Georgia court-access court class must be state or superior"
            )
        query_text = "*"
    elif search_field == "provider":
        provider_aliases = {
            "peachcourt": "peachcourt",
            "peach-court": "peachcourt",
            "researchga": "researchga",
            "odyssey_efilega": "odyssey_efilega",
            "odyssey-efilega": "odyssey_efilega",
            "odyssey-efile-ga": "odyssey_efilega",
            "greenfiling_infotrack": "greenfiling_infotrack",
            "greenfiling-infotrack": "greenfiling_infotrack",
            "greenfiling/infotrack": "greenfiling_infotrack",
        }
        provider = provider_aliases.get(selector.casefold())
        source_providers = {
            GEORGIA_EACCESS_DIRECTORY_SOURCE_ID: {
                "peachcourt",
                "researchga",
            },
            GEORGIA_EFILE_DIRECTORY_SOURCE_ID: {
                "odyssey_efilega",
                "peachcourt",
                "greenfiling_infotrack",
            },
        }[source_id]
        if provider not in source_providers:
            raise ValueError(
                "Georgia court-access provider is not published for the "
                "selected directory source"
            )
        query_text = "*"
    elif search_field in {"published-state", "state"}:
        published_state = selector.casefold().replace("-", "_")
        source_states = {
            GEORGIA_EACCESS_DIRECTORY_SOURCE_ID: {"account_required"},
            GEORGIA_EFILE_DIRECTORY_SOURCE_ID: {
                "mandatory",
                "available",
                "not_listed",
            },
        }[source_id]
        if published_state not in source_states:
            raise ValueError(
                "Georgia court-access published state is not used by the "
                "selected directory source"
            )
        query_text = "*"
    else:
        raise ValueError(
            "Georgia court-access --search-field must be text, court, county, "
            "court-class, provider, published-state, or directory"
        )

    selected_limit = _caller_limit(args)
    return argparse.Namespace(
        command="search",
        query_text=query_text,
        county=county,
        court_class=court_class,
        provider=provider,
        published_state=published_state,
        limit=(
            selected_limit
            if selected_limit is not None
            else query_georgia_court_access.DEFAULT_LIMIT
        ),
        all=False,
        cursor=args.cursor,
        **runtime,
    )


def _georgia_court_data_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to Georgia's aggregate court publications."""

    source_id = str(args.source)
    if source_id not in {
        GEORGIA_CASELOAD_DASHBOARD_SOURCE_ID,
        GEORGIA_WORKLOAD_ASSESSMENT_SOURCE_ID,
    }:
        raise ValueError(f"unsupported Georgia court-data source {source_id}")
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "13", "GA", "US-GA"}:
        raise ValueError(
            "Georgia aggregate court-data jurisdiction must be Georgia "
            "(13, GA, or US-GA)"
        )
    unsupported_selectors = (
        bool(args.court_id)
        or bool(args.county)
        or bool(args.courthouse)
        or bool(args.case_type)
        or bool(args.after)
        or bool(args.before)
        or bool(args.first_name)
        or args.entity_kind != "person"
        or args.partial
        or args.phonetic
        or args.exclude_inactive
        or bool(args.date_of_birth)
        or bool(args.drivers_license)
        or bool(args.plate_state)
        or bool(args.violation_number)
        or bool(args.search_scope)
        or bool(args.style_other)
        or bool(args.originating_coa)
        or bool(args.trial_court)
    )
    if unsupported_selectors:
        raise ValueError(
            "Georgia aggregate court-data routes expose publication, court-"
            "class, and exact-year selectors rather than case, party, county, "
            "or courthouse fields"
        )

    selector = str(getattr(args, "query", "") or "").strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "publications",
        "statewide",
    }
    search_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    bounds_selected = (
        args.cursor is not None
        or args.max_records is not None
        or args.limit_explicit
    )
    runtime = {
        "source": source_id,
        "timeout": args.timeout,
        "minimum_interval": max(
            args.minimum_interval,
            query_georgia_court_data.DEFAULT_MINIMUM_INTERVAL,
        ),
        "max_attempts": query_georgia_court_data.DEFAULT_MAX_ATTEMPTS,
        "output": None,
        "json_out": False,
    }

    if adapter_command == "handoff":
        if source_id != GEORGIA_CASELOAD_DASHBOARD_SOURCE_ID:
            raise ValueError(
                "Georgia dashboard-export handoff belongs to the dashboard "
                "source"
            )
        if not selector_is_all:
            raise ValueError(
                "Georgia dashboard discovery returns the official export "
                "handoff and does not apply a record selector"
            )
        if search_field not in {"", "export", "handoff"} or bounds_selected:
            raise ValueError(
                "Georgia dashboard discovery does not apply result paging or "
                "dashboard filters"
            )
        return argparse.Namespace(command="handoff", **runtime)

    if adapter_command == "probe":
        if not selector_is_all:
            raise ValueError(
                "Georgia aggregate court-data probe is a bounded source "
                "sentinel and does not apply a record selector"
            )
        if search_field or bounds_selected:
            raise ValueError(
                "Georgia aggregate court-data probe does not apply search or "
                "result-page controls"
            )
        return argparse.Namespace(command="probe", **runtime)

    selected_limit = _caller_limit(args)
    limit = (
        selected_limit
        if selected_limit is not None
        else query_georgia_court_data.DEFAULT_LIMIT
    )
    if adapter_command == "dashboards":
        if source_id != GEORGIA_CASELOAD_DASHBOARD_SOURCE_ID:
            raise ValueError(
                "Georgia caseload dashboards belong to the dashboard source"
            )
        if search_field not in {
            "",
            "any",
            "dashboard",
            "court-class",
            "title",
        }:
            raise ValueError(
                "Georgia dashboard --search-field must be dashboard, "
                "court-class, title, or any"
            )
        return argparse.Namespace(
            command="dashboards",
            query="*" if selector_is_all else selector,
            limit=limit,
            cursor=args.cursor,
            **runtime,
        )

    if source_id != GEORGIA_WORKLOAD_ASSESSMENT_SOURCE_ID:
        raise ValueError(
            "Georgia workload publications belong to the workload source"
        )
    if search_field not in {
        "",
        "year",
        "publication",
        "publication-year",
        "workload",
    }:
        raise ValueError(
            "Georgia workload --search-field must be year, publication, "
            "publication-year, or workload"
        )
    year: int | None = None
    if not selector_is_all:
        if re.fullmatch(r"20\d{2}", selector) is None:
            raise ValueError(
                "Georgia workload selectors must be a four-digit publication "
                "year or '*'"
            )
        year = int(selector)

    if adapter_command == "workloads":
        document_type = str(
            getattr(args, "document_type", "") or ""
        ).strip().casefold()
        if document_type not in {
            "",
            "pdf",
            "publication",
            "workload",
            "workload-assessment",
        }:
            raise ValueError(
                "Georgia workload --document-type must be PDF, publication, "
                "workload, or workload-assessment"
            )
        return argparse.Namespace(
            command="workloads",
            year=year,
            limit=limit,
            cursor=args.cursor,
            **runtime,
        )

    if adapter_command == "document":
        if year is None:
            raise ValueError(
                "Georgia workload detail requires one exact publication year"
            )
        if bounds_selected:
            raise ValueError(
                "Georgia workload detail uses one exact year and does not "
                "apply result paging"
            )
        return argparse.Namespace(
            command="document",
            year=year,
            artifact_output=None,
            **runtime,
        )

    raise ValueError(
        f"unsupported Georgia aggregate court-data operation {adapter_command}"
    )


def _georgia_supreme_docket_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared appellate operations to Georgia's public docket."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "13", "GA", "US-GA"}:
        if (
            len(jurisdiction) == 5
            and jurisdiction.isdigit()
            and jurisdiction.startswith("13")
        ):
            raise ValueError(
                "Georgia Supreme Court lower-court searches use the portal's "
                "published county names; pass --county"
            )
        raise ValueError(
            "Georgia Supreme Court docket jurisdiction must be Georgia "
            "(13, GA, or US-GA)"
        )
    if args.court_id and (
        str(args.court_id).strip().casefold()
        != query_georgia_supreme_docket.COURT_ID.casefold()
    ):
        raise ValueError(
            "Georgia Supreme Court docket --court-id must identify "
            f"{query_georgia_supreme_docket.COURT_ID}"
        )
    if any(
        (
            args.after,
            args.before,
            args.case_type,
            args.courthouse,
            args.first_name,
            args.partial,
            args.phonetic,
            args.exclude_inactive,
            args.date_of_birth,
            args.drivers_license,
            args.plate_state,
            args.violation_number,
            args.search_scope,
            args.style_other,
            args.originating_coa,
            args.trial_court,
        )
    ):
        raise ValueError(
            "Georgia Supreme Court public-docket routes expose case, party, "
            "attorney, lower-court-number, and county selectors"
        )

    selector = " ".join(str(args.query or "").split()).strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "source",
    }
    search_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    bounds_selected = (
        args.cursor is not None
        or args.max_records is not None
        or args.limit_explicit
    )
    runtime = {
        "timeout": args.timeout,
        "minimum_interval": max(
            args.minimum_interval,
            query_georgia_supreme_docket.DEFAULT_MINIMUM_INTERVAL,
        ),
        "max_attempts": query_georgia_supreme_docket.DEFAULT_MAX_ATTEMPTS,
        "retry_backoff": query_georgia_supreme_docket.DEFAULT_RETRY_BACKOFF,
        "output": None,
        "json_out": False,
    }

    if adapter_command == "discovery":
        if bounds_selected or args.county:
            raise ValueError(
                "Georgia Supreme Court discovery does not apply result bounds, "
                "continuation cursors, or county filters"
            )
        wants_manifest = (
            selector.casefold() in {"manifest", "routes"}
            or search_field in {"manifest", "routes", "source"}
        )
        if not wants_manifest and (
            not selector_is_all
            and selector.casefold()
            not in {"counties", "county", "county-selectors", "selectors"}
        ):
            raise ValueError(
                "Georgia Supreme Court discovery accepts counties or manifest"
            )
        if search_field not in {
            "",
            "county",
            "counties",
            "selectors",
            "manifest",
            "routes",
            "source",
        }:
            raise ValueError(
                "Georgia Supreme Court discovery --search-field accepts "
                "counties or manifest"
            )
        return argparse.Namespace(
            command="manifest" if wants_manifest else "counties",
            **runtime,
        )

    if adapter_command == "probe":
        if bounds_selected or args.county:
            raise ValueError(
                "Georgia Supreme Court probe does not apply result bounds, "
                "continuation cursors, or county filters"
            )
        if search_field not in {"", "case", "case-number", "probe"}:
            raise ValueError(
                "Georgia Supreme Court probe --search-field must identify a "
                "case number"
            )
        case_number = (
            query_georgia_supreme_docket.PROBE_CASE_NUMBER
            if selector_is_all or selector.casefold() == "probe"
            else selector
        )
        return argparse.Namespace(
            command="probe",
            case_number=case_number,
            **runtime,
        )

    if adapter_command in {"detail", "documents"}:
        if selector_is_all:
            raise ValueError(
                "Georgia Supreme Court exact-case operations require one case "
                "number"
            )
        if search_field not in {"", "case", "case-number", "docket"}:
            raise ValueError(
                "Georgia Supreme Court exact-case --search-field must identify "
                "a case number"
            )
        if bounds_selected or args.county:
            raise ValueError(
                "Georgia Supreme Court exact-case operations use only the case "
                "number"
            )
        if adapter_command == "documents":
            document_type = str(
                getattr(args, "document_type", "") or ""
            ).strip().casefold().replace("_", "-")
            if document_type not in {
                "",
                "metadata",
                "filing",
                "filing-metadata",
                "clerk-request",
            }:
                raise ValueError(
                    "Georgia Supreme Court document handoff returns filing "
                    "metadata for Clerk copy requests"
                )
            if getattr(args, "docket_entry_uuid", None):
                raise ValueError(
                    "Georgia Supreme Court filing metadata has no native "
                    "document or docket-entry identifier"
                )
        return argparse.Namespace(
            command=adapter_command,
            case_number=selector,
            **runtime,
        )

    if adapter_command != "search":
        raise ValueError(
            f"unsupported Georgia Supreme Court operation {adapter_command}"
        )
    if selector_is_all:
        raise ValueError(
            "Georgia Supreme Court docket search requires a source-native "
            "case, party, attorney, or related-case selector"
        )

    aliases = {
        "case": "case-number",
        "case-number": "case-number",
        "docket": "case-number",
        "caption": "case-style",
        "case-style": "case-style",
        "style": "case-style",
        "name": "party",
        "party": "party",
        "person": "party",
        "organization": "party",
        "lower-case": "lower-court-case-number",
        "lower-court": "lower-court-case-number",
        "lower-court-case-number": "lower-court-case-number",
        "coa": "court-of-appeals-case-number",
        "court-of-appeals": "court-of-appeals-case-number",
        "court-of-appeals-case-number": "court-of-appeals-case-number",
        "attorney": "attorney",
        "counsel": "attorney",
    }
    if search_field:
        field = aliases.get(search_field)
        if field is None:
            raise ValueError(
                "Georgia Supreme Court --search-field must be case-number, "
                "case-style, party, lower-court-case-number, "
                "court-of-appeals-case-number, or attorney"
            )
    else:
        field = (
            "case-number"
            if re.fullmatch(r"S\d{2}[A-Z]\d+", selector, re.IGNORECASE)
            else "party"
        )
    county = str(args.county or "").strip() or None
    if county and field != "lower-court-case-number":
        raise ValueError(
            "Georgia Supreme Court --county applies to lower-court-case-number "
            "search"
        )
    selected_limit = _caller_limit(args)
    return argparse.Namespace(
        command="search",
        query=selector,
        field=field,
        county=county,
        county_id=None,
        limit=(
            selected_limit
            if selected_limit is not None
            else query_georgia_supreme_docket.DEFAULT_LIMIT
        ),
        all=False,
        cursor=args.cursor,
        **runtime,
    )


def _georgia_supreme_publications_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to Georgia's decision publications."""

    source_id = str(args.source)
    if source_id not in GEORGIA_SUPREME_PUBLICATION_SOURCE_IDS:
        raise ValueError(
            f"unsupported Georgia Supreme Court publication source {source_id}"
        )
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "13", "GA", "US-GA"}:
        raise ValueError(
            "Georgia Supreme Court publications have statewide Georgia scope"
        )
    if args.court_id and (
        str(args.court_id).strip().casefold()
        != query_georgia_supreme_publications.COURT_ID.casefold()
    ):
        raise ValueError(
            "Georgia Supreme Court publications --court-id must identify "
            f"{query_georgia_supreme_publications.COURT_ID}"
        )
    if any(
        (
            args.county,
            args.courthouse,
            args.first_name,
            args.date_of_birth,
            args.drivers_license,
            args.plate_state,
            args.violation_number,
            args.partial,
            args.phonetic,
            args.exclude_inactive,
            args.search_scope,
            args.style_other,
            args.originating_coa,
            args.trial_court,
        )
    ):
        raise ValueError(
            "Georgia Supreme Court publication indexes expose publication, "
            "date, title, and appellate-case selectors"
        )

    selector = " ".join(str(args.query or "").split()).strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "source",
    }
    bounds_selected = (
        args.cursor is not None
        or args.max_records is not None
        or args.limit_explicit
    )
    runtime = {
        "timeout": args.timeout,
        "minimum_interval": max(
            args.minimum_interval,
            query_georgia_supreme_publications.DEFAULT_MINIMUM_INTERVAL,
        ),
        "max_attempts": (
            query_georgia_supreme_publications.DEFAULT_MAX_ATTEMPTS
        ),
        "output": None,
        "json_out": False,
    }

    if adapter_command == "download":
        if not args.destination:
            raise ValueError(
                "Georgia Supreme Court publication download requires the "
                "exact official PDF URL and --destination"
            )
        if getattr(args, "case_number", None):
            raise ValueError(
                "Georgia Supreme Court publication download uses the exact "
                "official PDF URL; it does not derive one from a case number"
            )
        if any((args.after, args.before, bounds_selected)):
            raise ValueError(
                "Georgia Supreme Court publication download accepts one "
                "exact PDF URL and destination"
            )
        return argparse.Namespace(
            command="download",
            source=source_id,
            document_url=selector,
            destination=args.destination,
            overwrite=args.overwrite,
            **runtime,
        )

    if adapter_command == "discovery":
        if any(
            (
                args.after,
                args.before,
                args.case_type,
                bounds_selected,
            )
        ):
            raise ValueError(
                "Georgia Supreme Court publication discovery returns the "
                "selected component manifest"
            )
        if selector.casefold() not in {
            "",
            "*",
            "all",
            "manifest",
            "routes",
            "source",
            "sources",
        }:
            raise ValueError(
                "Georgia Supreme Court publication discovery accepts manifest"
            )
        return argparse.Namespace(
            command="manifest",
            source=source_id,
            **runtime,
        )

    if adapter_command == "probe":
        if (
            (not selector_is_all and selector.casefold() != "probe")
            or any(
                (
                    args.after,
                    args.before,
                    args.case_type,
                    bounds_selected,
                )
            )
        ):
            raise ValueError(
                "Georgia Supreme Court publication probe checks the current "
                "bounded annual component"
            )
        return argparse.Namespace(
            command="probe",
            source=source_id,
            year=None,
            application_type="both",
            **runtime,
        )

    if adapter_command != "search":
        raise ValueError(
            "unsupported Georgia Supreme Court publication operation "
            f"{adapter_command}"
        )

    date_from = date_to = None
    if args.after:
        try:
            date_from = date.fromisoformat(str(args.after))
        except ValueError as error:
            raise ValueError("--after must use YYYY-MM-DD") from error
    if args.before:
        try:
            date_to = date.fromisoformat(str(args.before))
        except ValueError as error:
            raise ValueError("--before must use YYYY-MM-DD") from error
    if date_from and date_to and date_from > date_to:
        raise ValueError("--after must not be later than --before")

    coverage_years = tuple(
        int(value)
        for value in (
            query_georgia_supreme_publications.SOURCE_METADATA[
                source_id
            ].metadata["coverage_years"]
        )
    )
    years: list[int] | None = None
    if date_from or date_to:
        first_year = date_from.year if date_from else coverage_years[0]
        last_year = date_to.year if date_to else coverage_years[-1]
        years = [
            year
            for year in coverage_years
            if first_year <= year <= last_year
        ]
        if not years:
            raise ValueError(
                "publication date range does not overlap verified annual "
                "coverage for the selected component"
            )

    selected_type = (
        str(args.case_type or "")
        .strip()
        .casefold()
        .replace("-", "_")
    )
    document_type = (
        str(getattr(args, "document_type", "") or "")
        .strip()
        .casefold()
        .replace("-", "_")
    )
    type_aliases = {
        "grant": "certiorari_grant",
        "grant_order": "certiorari_grant",
        "certiorari_grant_order": "certiorari_grant",
        "denial": "certiorari_denial",
        "denial_list": "certiorari_denial",
        "denial_related_publication": "certiorari_denial",
        "summary": "noteworthy_summary",
        "summary_packet": "noteworthy_summary",
        "supreme_court_opinion": "opinion",
        "discretionary": "discretionary_application_grant",
        "discretionary_application_grant_order": (
            "discretionary_application_grant"
        ),
        "interlocutory": "interlocutory_application_grant",
        "interlocutory_application_grant_order": (
            "interlocutory_application_grant"
        ),
    }
    requested_types = []
    for value in (selected_type, document_type):
        if value in {
            "",
            "all",
            "appellate",
            "both",
            "pdf",
            "publication",
            "publication_document",
        }:
            continue
        requested_types.append(type_aliases.get(value, value))
    if len(set(requested_types)) > 1:
        raise ValueError(
            "--case-type and --document-type select different publication "
            "components"
        )
    requested_type = requested_types[0] if requested_types else None
    allowed_types = {
        query_georgia_supreme_publications.OPINION_SOURCE_ID: {
            "opinion",
            "noteworthy_summary",
        },
        query_georgia_supreme_publications.CERT_GRANT_SOURCE_ID: {
            "certiorari_grant",
        },
        query_georgia_supreme_publications.CERT_DENIAL_SOURCE_ID: {
            "certiorari_denial",
        },
        query_georgia_supreme_publications.APPLICATION_GRANT_SOURCE_ID: {
            "discretionary_application_grant",
            "interlocutory_application_grant",
        },
    }[source_id]
    if requested_type and requested_type not in allowed_types:
        raise ValueError(
            "publication type does not belong to the selected Georgia "
            "Supreme Court component"
        )
    publication_types = [requested_type] if requested_type else None
    application_type = "both"
    if requested_type == "discretionary_application_grant":
        application_type = "discretionary"
    elif requested_type == "interlocutory_application_grant":
        application_type = "interlocutory"

    search_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    case_fields = {
        "case",
        "case-number",
        "docket",
        "court-of-appeals-case-number",
        "publication-id",
    }
    text_fields = {
        "",
        "any",
        "caption",
        "name",
        "publication",
        "text",
        "title",
    }
    exact_case_operation = args.command in {"case", "documents"}
    if exact_case_operation:
        if selector_is_all:
            raise ValueError(
                "Georgia Supreme Court publication case and documents "
                "operations require one exact appellate case number"
            )
        if search_field and search_field not in case_fields:
            raise ValueError(
                "Georgia Supreme Court publication exact-case operations use "
                "an appellate case number"
            )
        field = "case-number"
    elif search_field in case_fields:
        if selector_is_all:
            raise ValueError(
                "Georgia Supreme Court publication case-number search "
                "requires a case number"
            )
        field = "case-number"
    elif search_field in text_fields:
        field = "text"
    else:
        raise ValueError(
            "Georgia Supreme Court publication --search-field identifies a "
            "case number, title, caption, or publication text"
        )
    if (
        not exact_case_operation
        and not search_field
        and re.fullmatch(r"[SA]\d{2}[A-Z]\d{4}", selector, re.IGNORECASE)
    ):
        field = "case-number"

    selected_limit = _caller_limit(args)
    return argparse.Namespace(
        command="search",
        source=source_id,
        query="*" if field == "case-number" else selector,
        year=years,
        application_type=application_type,
        publication_type=publication_types,
        case_number=selector if field == "case-number" else None,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
        limit=(
            selected_limit
            if selected_limit is not None
            else query_georgia_supreme_publications.DEFAULT_LIMIT
        ),
        cursor=args.cursor,
        **runtime,
    )


def _wisconsin_wscca_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate the shared case surface to WSCCA's appellate operations."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "WI",
        "55",
        "US-WI",
    }:
        raise ValueError("WSCCA covers Wisconsin appellate courts")
    allowed_courts = {
        query_wisconsin_wscca.SUPREME_COURT_ID,
        query_wisconsin_wscca.COURT_OF_APPEALS_ID,
        query_wisconsin_wscca.APPELLATE_COURTS_ID,
    }
    if args.court_id and args.court_id not in allowed_courts:
        raise ValueError(
            "WSCCA court ID must identify the Wisconsin Supreme Court, "
            "Court of Appeals, or combined appellate courts"
        )
    if args.after or args.before or args.case_type:
        raise ValueError(
            "WSCCA's shared route does not expose filing-date or case-type "
            "filters; use the direct adapter for its published selectors"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        attempts=2,
        minimum_interval=args.minimum_interval,
        output=None,
        json_out=False,
    )
    if adapter_command == "search":
        search_field = (
            str(
                args.search_field
                or ("business" if args.entity_kind == "organization" else "party")
            )
            .strip()
            .casefold()
            .replace("_", "-")
        )
        scope_aliases = {
            "party": "party",
            "person": "party",
            "business": "business",
            "organization": "business",
            "case": "case-number",
            "case-number": "case-number",
        }
        if search_field not in scope_aliases:
            raise ValueError(
                "WSCCA --search-field must be party, business, or case-number"
            )
        values.update(
            query=args.query,
            scope=scope_aliases[search_field],
            middle_name=None,
            county=args.county,
            similar_names=args.partial,
            exclude_missing_middle=False,
            limit=_caller_limit(args),
            cursor=args.cursor,
        )
    elif adapter_command in {"case", "docket", "documents"}:
        values.update(
            case_number=args.query,
            limit=(
                _caller_limit(args)
                if adapter_command in {"docket", "documents"}
                else None
            ),
            cursor=(
                args.cursor if adapter_command in {"docket", "documents"} else None
            ),
        )
    elif adapter_command == "download":
        if not args.case_number:
            raise ValueError("WSCCA download requires --case-number")
        if not args.destination:
            raise ValueError("WSCCA download requires --destination")
        values.update(
            case_number=args.case_number,
            document_id=args.query,
            document_output=args.destination,
        )
    else:
        raise ValueError(f"unsupported WSCCA command: {adapter_command}")
    return argparse.Namespace(**values)


def _wisconsin_opinion_collection(args: argparse.Namespace) -> str:
    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": (
            "supreme-opinions"
            if args.court_id == query_wisconsin_opinions.SUPREME_COURT_ID
            else "appeals-opinions"
        ),
        "opinion": "appeals-opinions",
        "opinions": "appeals-opinions",
        "appeals-opinions": "appeals-opinions",
        "supreme-opinions": "supreme-opinions",
        "supreme-orders": "supreme-orders",
        "appeals-summary": "appeals-summary",
        "summary-dispositions": "appeals-summary",
    }
    collection = aliases.get(selected)
    if collection is None:
        raise ValueError(
            "Wisconsin opinions --search-field must be appeals-opinions, "
            "supreme-opinions, supreme-orders, appeals-summary, or keyword"
        )
    config = query_wisconsin_opinions.COLLECTIONS[collection]
    if args.court_id and args.court_id != config.court_id:
        raise ValueError(f"{collection} uses court ID {config.court_id}")
    return collection


def _wisconsin_opinion_page(
    cursor: str | None,
    *,
    collection: str,
) -> int:
    if cursor is None:
        return 1
    prefix = f"metadata:{collection}:page:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError(f"Wisconsin opinion cursor must use {prefix}N")
    return int(cursor[len(prefix) :])


def _wisconsin_opinions_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared searches to the official Wisconsin publication indexes."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "WI",
        "55",
        "US-WI",
    }:
        raise ValueError("Wisconsin appellate opinions cover Wisconsin")
    if args.case_type:
        raise ValueError(
            "Select the Wisconsin publication collection with --search-field"
        )

    values = vars(args).copy()
    values.update(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    if adapter_command == "download":
        if not args.destination:
            raise ValueError("Wisconsin opinion download requires --destination")
        values.update(
            command="download",
            url=args.query,
            destination=Path(args.destination),
        )
        return argparse.Namespace(**values)

    search_field = str(args.search_field or "").strip().casefold().replace("_", "-")
    if search_field in {"keyword", "full-text", "fulltext"}:
        allowed_court_ids = {
            query_wisconsin_opinions.SUPREME_COURT_ID,
            query_wisconsin_opinions.APPEALS_COURT_ID,
        }
        if args.court_id and args.court_id not in allowed_court_ids:
            raise ValueError(
                "Wisconsin full-text search uses the Wisconsin Supreme Court "
                "or Court of Appeals court ID"
            )
        court = (
            "supreme"
            if args.court_id == query_wisconsin_opinions.SUPREME_COURT_ID
            else "appeals"
        )
        if args.cursor:
            prefix = f"fulltext:{court}:offset:"
            if (
                not args.cursor.startswith(prefix)
                or not args.cursor[len(prefix) :].isdigit()
            ):
                raise ValueError(f"Wisconsin full-text cursor must use {prefix}N")
            offset = int(args.cursor[len(prefix) :])
            if offset % query_wisconsin_opinions.FULLTEXT_PAGE_SIZE:
                raise ValueError(
                    "Wisconsin full-text cursor offset must align to the "
                    "native page size"
                )
            page = (offset // query_wisconsin_opinions.FULLTEXT_PAGE_SIZE) + 1
        else:
            page = 1
        values.update(
            command="keyword",
            query=args.query,
            court=court,
            exact=False,
            page=page,
            all_pages=False,
            max_pages=None,
        )
        return argparse.Namespace(**values)

    collection = _wisconsin_opinion_collection(args)
    selector = re.sub(r"\s+", "", args.query).upper()
    case_number = (
        selector if re.match(r"^\d{4}AP\d+", selector, flags=re.IGNORECASE) else None
    )
    values.update(
        command="search",
        collection=collection,
        case_number=case_number,
        party=None if case_number else args.query,
        date_from=args.after,
        date_to=args.before,
        final_publication_from=None,
        final_publication_to=None,
        judge=None,
        county=args.county,
        district=None,
        disposition=None,
        citation_type="none",
        citation_page=None,
        citation_volume=None,
        public_domain_citation=None,
        sort=None,
        page=_wisconsin_opinion_page(
            args.cursor,
            collection=collection,
        ),
        all_pages=False,
        max_pages=None,
    )
    return argparse.Namespace(**values)


def _dc_participant_selector(
    query: str,
    *,
    first_name: str | None,
    entity_kind: str,
) -> tuple[str, str | None, str | None]:
    """Map the shared name selector to C-Track participant fields."""

    normalized = re.sub(r"\s+", " ", query).strip()
    if first_name:
        return normalized, first_name.strip() or None, None
    if entity_kind == "organization":
        return normalized, None, None
    if "," in normalized:
        last, remainder = normalized.split(",", 1)
        given = remainder.strip().split()
        return (
            last.strip(),
            given[0] if given else None,
            " ".join(given[1:]) or None,
        )
    tokens = normalized.split()
    if len(tokens) < 2:
        return normalized, None, None
    return tokens[-1], tokens[0], " ".join(tokens[1:-1]) or None


def _dc_court_directory_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared person search to one official D.C. judge directory."""

    if adapter_command != "directory":
        raise ValueError(
            f"unsupported D.C. court-directory operation {adapter_command}"
        )
    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "DC",
        "11",
        "US-DC",
    }:
        raise ValueError("D.C. court directories cover the District of Columbia")
    court_by_source = {
        DC_SUPERIOR_DIRECTORY_SOURCE_ID: (
            "superior",
            query_dc_court_directory_data.SUPERIOR_COURT_ID,
        ),
        DC_APPEALS_DIRECTORY_SOURCE_ID: (
            "appeals",
            query_dc_court_directory_data.APPEALS_COURT_ID,
        ),
    }
    court, expected_court_id = court_by_source[args.source]
    if args.court_id and args.court_id != expected_court_id:
        raise ValueError(
            f"{args.source} uses court ID {expected_court_id}"
        )
    if args.entity_kind != "person":
        raise ValueError("D.C. judge-directory search represents people")
    if any(
        (
            args.case_type,
            args.after,
            args.before,
            args.cursor,
            args.county,
            args.courthouse,
        )
    ):
        raise ValueError(
            "D.C. judge-directory search accepts a person, court, role, "
            "and result limit"
        )
    if args.phonetic:
        raise ValueError(
            "D.C. judge directories do not publish a phonetic-name mode"
        )

    selected = (
        str(args.search_field or "")
        .strip()
        .casefold()
        .replace("_", "-")
    )
    role_aliases = {
        "": "all",
        "directory": "all",
        "person": "all",
        "name": "all",
        "judge": "all",
        "chief": "chief",
        "chief-judge": "chief",
        "associate": "associate",
        "associate-judge": "associate",
        "magistrate": "magistrate",
        "magistrate-judge": "magistrate",
        "senior": "senior",
        "senior-judge": "senior",
    }
    role = role_aliases.get(selected)
    if role is None:
        raise ValueError(
            "D.C. judge-directory --search-field must be directory, person, "
            "name, judge, chief, associate, magistrate, or senior"
        )
    query_parts = [
        str(value).strip()
        for value in (args.first_name, args.query)
        if str(value or "").strip()
    ]
    query_text = " ".join(query_parts)
    if query_text.casefold() in {"*", "all"}:
        query_text = ""
    values = vars(args).copy()
    values.update(
        command="directory",
        court=court,
        role=role,
        query=query_text or None,
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=max(
            args.minimum_interval,
            query_dc_court_directory_data.DEFAULT_MINIMUM_INTERVAL,
        ),
        max_attempts=3,
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _dc_appellate_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate common court operations to D.C. appellate C-Track."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "DC",
        "11",
        "US-DC",
    }:
        raise ValueError("D.C. appellate case search covers the District of Columbia")
    if args.court_id and args.court_id != query_dc_appellate_cases.COURT_ID:
        raise ValueError(
            "D.C. appellate case search uses court ID "
            f"{query_dc_appellate_cases.COURT_ID}"
        )
    if args.case_type:
        raise ValueError(
            "D.C. C-Track does not expose case-type filtering on this search form"
        )

    shared_command = args.command
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    if adapter_command == "download":
        if not args.destination:
            raise ValueError("D.C. appellate download requires --destination")
        values.update(
            url=args.query,
            destination=Path(args.destination),
        )
        return argparse.Namespace(**values)

    if shared_command in {"case", "docket", "documents"}:
        values.update(
            command="case",
            case_number=args.query,
            source_internal_id=None,
            resolve_documents=shared_command in {"case", "documents"},
        )
        return argparse.Namespace(**values)

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": "",
        "participant": "participant",
        "party": "participant",
        "name": "participant",
        "caption": "caption",
        "case-number": "appellate-case-number",
        "appellate-case-number": "appellate-case-number",
        "originating-case-number": "originating-case-number",
        "trial-case-number": "originating-case-number",
    }
    search_field = aliases.get(selected)
    if search_field is None:
        raise ValueError(
            "D.C. appellate --search-field must be participant, caption, "
            "appellate-case-number, or originating-case-number"
        )
    if not search_field:
        if re.fullmatch(
            r"\d{2,4}-[A-Z0-9]{1,8}-\d+",
            args.query.strip(),
            flags=re.IGNORECASE,
        ):
            search_field = "appellate-case-number"
        else:
            search_field = "participant"

    if search_field == "participant":
        if args.after or args.before:
            raise ValueError(
                "D.C. participant search does not expose a filed-date filter; "
                "use caption or case-number search for source-native date filtering"
            )
        last_name, first_name, middle_name = _dc_participant_selector(
            args.query,
            first_name=args.first_name,
            entity_kind=args.entity_kind,
        )
        values.update(
            command="participant",
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            order_by="FileDt",
            order_direction="desc",
            start_row=None,
            cursor=args.cursor,
            all_pages=False,
        )
        return argparse.Namespace(**values)

    values.update(
        command="search",
        appellate_case_number=(
            args.query if search_field == "appellate-case-number" else None
        ),
        caption=args.query if search_field == "caption" else None,
        originating_case_number=(
            args.query if search_field == "originating-case-number" else None
        ),
        date_from=args.after,
        date_to=args.before,
        open_only=False,
        all_records=False,
        order_by="CsNumber",
        order_direction="desc",
        start_row=None,
        cursor=args.cursor,
        all_pages=False,
    )
    return argparse.Namespace(**values)


def _maryland_public_cases_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate common searches to Maryland's rolling cases-filed reports."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "MD",
        "24",
        "US-MD",
    }:
        raise ValueError("Maryland public-case reports cover Maryland")
    shared_command = args.command
    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": "name",
        "query": "query",
        "all": "query",
        "case-number": "case_number",
        "name": "name",
        "party": "name",
        "address": "address",
        "court": "court",
        "case-type": "case_type",
        "charge": "charge",
    }
    filter_name = aliases.get(selected)
    if filter_name is None:
        raise ValueError(
            "Maryland reports --search-field must be query, case-number, "
            "name, address, court, case-type, or charge"
        )

    filters: dict[str, Any] = {
        "query": None,
        "case_number": None,
        "name": None,
        "address": None,
        "court": None,
        "case_type": args.case_type,
        "charge": None,
        "filing_date": None,
        "filing_date_from": args.after,
        "filing_date_to": args.before,
    }
    if shared_command == "case":
        filters["case_number"] = args.query
    else:
        filters[filter_name] = args.query
    if args.county:
        filters["court"] = args.county
    elif args.court_id:
        filters["court"] = str(args.court_id).removeprefix("us-md-").replace("-", " ")

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        report_date=[],
        all_current=True,
        all_results=False,
        cursor=args.cursor,
        limit=_caller_limit(args) or args.limit,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
        **filters,
    )
    return argparse.Namespace(**values)


MARYLAND_ESTATE_COUNTIES_BY_GEOID = {
    "24001": "Allegany County",
    "24003": "Anne Arundel County",
    "24005": "Baltimore County",
    "24009": "Calvert County",
    "24011": "Caroline County",
    "24013": "Carroll County",
    "24015": "Cecil County",
    "24017": "Charles County",
    "24019": "Dorchester County",
    "24021": "Frederick County",
    "24023": "Garrett County",
    "24025": "Harford County",
    "24027": "Howard County",
    "24029": "Kent County",
    "24031": "Montgomery County",
    "24033": "Prince George's County",
    "24035": "Queen Anne's County",
    "24037": "St. Mary's County",
    "24039": "Somerset County",
    "24041": "Talbot County",
    "24043": "Washington County",
    "24045": "Wicomico County",
    "24047": "Worcester County",
    "24510": "Baltimore City",
}
MARYLAND_ESTATE_COUNTIES_BY_COURT = {
    query_md_estate_search._county_court_id(county): county
    for county in MARYLAND_ESTATE_COUNTIES_BY_GEOID.values()
}


def _maryland_estate_county(args: argparse.Namespace) -> str | None:
    if args.county:
        return str(args.county)
    if args.court_id:
        court_id = str(args.court_id).strip().upper()
        county = MARYLAND_ESTATE_COUNTIES_BY_COURT.get(court_id)
        if county is None:
            raise ValueError(
                "Maryland estate --court-id must identify one Register of "
                "Wills jurisdiction"
            )
        return county
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if not jurisdiction or jurisdiction in {"MD", "24", "US-MD"}:
        return None
    county = MARYLAND_ESTATE_COUNTIES_BY_GEOID.get(jurisdiction)
    if county is None:
        raise ValueError(
            "Maryland estate search covers Maryland state or county GEOIDs"
        )
    return county


def _maryland_estate_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared case/name selectors to the statewide estate index."""

    county = _maryland_estate_county(args)
    filing_date = (
        args.after if args.after and args.before and args.after == args.before else None
    )
    estate_type = args.case_type
    if str(estate_type or "").strip().casefold() in {
        "estate",
        "estate case",
        "probate",
        "probate estate",
    }:
        estate_type = None

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        county=county,
        status=None,
        estate_type=estate_type,
        filed_from=None if filing_date else args.after,
        filed_to=None if filing_date else args.before,
        filing_date=filing_date,
        cursor=args.cursor,
        limit=_caller_limit(args),
        all_results=False,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        catalog_config=str(query_md_estate_search.DEFAULT_CATALOG_CONFIG_PATH),
        output=None,
        json_out=False,
    )

    if args.command in {"case", "docket"}:
        values.update(
            command="resolve-estate",
            estate_number=args.query,
            last_name=None,
            first_name=None,
            middle_name=None,
            exact_last_name=False,
        )
        return argparse.Namespace(**values)

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": "decedent",
        "name": "decedent",
        "party": "decedent",
        "decedent": "decedent",
        "representative": "representative",
        "personal-representative": "representative",
        "executor": "representative",
        "estate": "estate",
        "estate-number": "estate",
        "case-number": "estate",
    }
    operation = aliases.get(selected)
    if operation is None:
        raise ValueError(
            "Maryland estate --search-field must be decedent, "
            "representative, or estate-number"
        )
    if operation == "estate":
        values.update(
            command="estate",
            estate_number=args.query,
            last_name=None,
            first_name=None,
            middle_name=None,
            exact_last_name=False,
        )
        return argparse.Namespace(**values)

    last_name, first_name, middle_name = _dc_participant_selector(
        args.query,
        first_name=args.first_name,
        entity_kind=args.entity_kind,
    )
    values.update(
        command=operation,
        estate_number=None,
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        exact_last_name=False,
    )
    return argparse.Namespace(**values)


def _maryland_estate_notice_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared name and date selectors to legal-notice occurrences."""

    county = _maryland_estate_county(args)
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        county=county,
        published_from=args.after,
        published_to=args.before,
        death_date=None,
        party_type="decedent",
        last_name=None,
        first_name=None,
        middle_name=None,
        sort=None,
        cursor=args.cursor,
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        catalog_config=str(
            query_md_estate_notices_claims.DEFAULT_CATALOG_CONFIG_PATH
        ),
        output=None,
        json_out=False,
    )
    if adapter_command == "probe-notices":
        return argparse.Namespace(**values)
    if args.case_type:
        raise ValueError(
            "Maryland estate legal notices do not expose a notice-type "
            "search field; filter returned source titles when needed"
        )
    if args.phonetic:
        raise ValueError(
            "Maryland estate legal notices do not expose phonetic name search"
        )

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": "decedent",
        "name": "decedent",
        "party": "decedent",
        "decedent": "decedent",
        "representative": "representative",
        "personal-representative": "representative",
        "executor": "representative",
    }
    party_type = aliases.get(selected)
    if party_type is None:
        raise ValueError(
            "Maryland estate-notice --search-field must be decedent or "
            "representative"
        )
    last_name, first_name, middle_name = _dc_participant_selector(
        args.query,
        first_name=args.first_name,
        entity_kind=args.entity_kind,
    )
    values.update(
        party_type=party_type,
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
    )
    return argparse.Namespace(**values)


def _maryland_estate_claim_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared selectors to filed-claim occurrences and details."""

    county = _maryland_estate_county(args)
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        role="decedent",
        last_name=None,
        exact_last_name=False,
        first_name=None,
        middle_name=None,
        surname=None,
        corporation=None,
        estate_number=None,
        filed_date=None,
        county=county,
        claim_type=args.case_type,
        claim_status=None,
        linked_to_estate=None,
        migrated_to_estate=None,
        cursor=args.cursor,
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        catalog_config=str(
            query_md_estate_notices_claims.DEFAULT_CATALOG_CONFIG_PATH
        ),
        output=None,
        json_out=False,
    )
    if adapter_command == "probe-claims":
        return argparse.Namespace(**values)
    if adapter_command == "claim-detail":
        selector = " ".join(args.query.split()).strip()
        match = re.fullmatch(
            r"(?:(?P<partition>[A-Za-z0-9_-]+):)?"
            r"(?P<record_id>\d+)",
            selector,
        )
        if match is None:
            raise ValueError(
                "Maryland claim detail expects RecordId or "
                "source-partition:RecordId"
            )
        values.update(
            record_id=match.group("record_id"),
            source_partition=match.group("partition") or "row",
        )
        return argparse.Namespace(**values)

    if args.phonetic:
        raise ValueError(
            "Maryland estate claims do not expose phonetic name search"
        )
    if args.after or args.before:
        if not args.after or not args.before or args.after != args.before:
            raise ValueError(
                "Maryland estate claims expose an exact filed-date field; "
                "use equal --after and --before dates"
            )
        values["filed_date"] = args.after

    if args.command == "claims":
        values["estate_number"] = args.query
        return argparse.Namespace(**values)

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    if not selected:
        selected = (
            "corporation"
            if args.entity_kind == "organization"
            else "decedent"
        )
    aliases = {
        "name": "decedent",
        "party": "decedent",
        "decedent": "decedent",
        "claimant": "claimant",
        "filed-by": "claimant",
        "creditor": "claimant",
        "corporation": "corporation",
        "organization": "corporation",
        "company": "corporation",
        "estate": "estate-number",
        "estate-number": "estate-number",
        "case-number": "estate-number",
        "claim-type": "claim-type",
        "type": "claim-type",
        "claim-status": "claim-status",
        "status": "claim-status",
    }
    operation = aliases.get(selected)
    if operation is None:
        raise ValueError(
            "Maryland estate-claim --search-field must be decedent, "
            "claimant, corporation, estate-number, claim-type, or claim-status"
        )
    if operation == "estate-number":
        values["estate_number"] = args.query
        return argparse.Namespace(**values)
    if operation == "claim-type":
        values["claim_type"] = args.query
        return argparse.Namespace(**values)
    if operation == "claim-status":
        values["claim_status"] = args.query
        return argparse.Namespace(**values)
    if operation == "corporation":
        values.update(
            role="claimant",
            corporation=" ".join(args.query.split()).strip(),
        )
        return argparse.Namespace(**values)

    last_name, first_name, middle_name = _dc_participant_selector(
        args.query,
        first_name=args.first_name,
        entity_kind=args.entity_kind,
    )
    values.update(
        role=operation,
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
    )
    return argparse.Namespace(**values)


def _maryland_judgment_liens_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate common case and name searches to the judgment/lien index."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "MD",
        "24",
        "US-MD",
    }:
        raise ValueError("Maryland judgment and lien search covers Maryland")
    if args.case_type:
        raise ValueError(
            "Maryland judgment and lien search does not expose case-type filtering"
        )

    shared_command = args.command
    values = vars(args).copy()
    values.update(
        command=adapter_command,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    if shared_command in {"case", "docket", "claims"}:
        values.update(command="detail", case_number=args.query)
        return argparse.Namespace(**values)

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    if selected not in {"", "name", "person", "company", "organization"}:
        raise ValueError(
            "Maryland judgment/liens --search-field must be person or company"
        )
    company_mode = selected in {"company", "organization"} or (
        not selected and args.entity_kind == "organization"
    )
    county = args.county
    if county is None and args.court_id:
        county = str(args.court_id).removeprefix("us-md-").replace("-", " ")
    filing_date = (
        args.after if args.after and args.before and args.after == args.before else None
    )
    filed_from = None if filing_date else args.after
    filed_to = None if filing_date else args.before
    common = {
        "county": county,
        "filed_from": filed_from,
        "filed_to": filed_to,
        "filing_date": filing_date,
        "cursor": args.cursor,
        "limit": _caller_limit(args) or args.limit,
        "all_results": False,
    }
    if company_mode:
        values.update(
            command="company",
            company_name=args.query,
            **common,
        )
        return argparse.Namespace(**values)

    last_name, first_name, middle_name = _dc_participant_selector(
        args.query,
        first_name=args.first_name,
        entity_kind="person",
    )
    values.update(
        command="person",
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        exact_last_name=False,
        **common,
    )
    return argparse.Namespace(**values)


def _maryland_opinions_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared document searches to Maryland's two opinion indexes."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "MD",
        "24",
        "US-MD",
    }:
        raise ValueError("Maryland appellate opinions cover Maryland")

    court_by_id = {
        spec["court_id"]: court_key
        for court_key, spec in query_md_opinions.COURTS.items()
    }
    court = "both"
    if args.court_id:
        court = court_by_id.get(str(args.court_id), "")
        if not court:
            raise ValueError(
                "Maryland opinions --court-id must be md-supreme-court or "
                "md-appellate-court"
            )

    values = vars(args).copy()
    values.update(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    if adapter_command == "download":
        if not args.destination:
            raise ValueError("Maryland opinion download requires --destination")
        values.update(
            command="download",
            url=args.query,
            destination=Path(args.destination),
        )
        return argparse.Namespace(**values)

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": "reported",
        "reported": "reported",
        "reported-opinion": "reported",
        "reported-opinions": "reported",
        "published": "reported",
        "unreported": "unreported",
        "unreported-opinion": "unreported",
        "unreported-opinions": "unreported",
    }
    collection = aliases.get(selected)
    if collection is None:
        raise ValueError(
            "Maryland opinions --search-field must be reported or unreported"
        )

    if collection == "reported":
        if args.after or args.before:
            raise ValueError(
                "The reported collection exposes complete filing-year indexes; "
                "use the direct adapter to select a filing year"
            )
        values.update(
            command="reported",
            court=court,
            year="all",
            order="case" if args.command in {"case", "documents"} else "date",
            query=args.query,
            match_mode=(
                "case_number" if args.command in {"case", "documents"} else "text"
            ),
            limit=_caller_limit(args),
            cursor=args.cursor,
        )
        return argparse.Namespace(**values)

    values.update(
        command="unreported",
        month=None,
        year=None,
        all_months=False,
        date_from=args.after,
        date_to=args.before,
        court=court,
        query=args.query,
        match_mode=("case_number" if args.command in {"case", "documents"} else "text"),
        limit=_caller_limit(args),
        cursor=args.cursor,
    )
    return argparse.Namespace(**values)


def _maryland_business_opinions_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared searches to Maryland's selective trial-opinion archive."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if (
        jurisdiction
        and jurisdiction not in {"MD", "24", "US-MD"}
        and not re.fullmatch(
            r"24\d{3}",
            jurisdiction,
        )
    ):
        raise ValueError("Maryland Business and Technology opinions cover Maryland")

    county = args.county
    if args.court_id:
        court_id = str(args.court_id)
        if not court_id.startswith("md-circuit-"):
            raise ValueError(
                "Maryland Business and Technology opinions use md-circuit-* court IDs"
            )
        court_county = court_id.removeprefix("md-circuit-").replace("-", " ")
        if county is None:
            county = court_county

    values = vars(args).copy()
    values.update(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    if adapter_command == "download":
        if not args.destination:
            raise ValueError(
                "Maryland Business and Technology document download requires "
                "--destination"
            )
        values.update(
            command="download",
            url=args.query,
            destination=Path(args.destination),
        )
        return argparse.Namespace(**values)

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": "query",
        "query": "query",
        "text": "query",
        "caption": "query",
        "party": "query",
        "name": "query",
        "case": "case-number",
        "case-number": "case-number",
        "judge": "judge",
        "county": "county",
        "opinion": "opinion",
        "order": "order",
        "synopsis": "synopsis",
    }
    search_field = aliases.get(selected)
    if search_field is None:
        raise ValueError(
            "Maryland Business and Technology --search-field must be query, "
            "case-number, judge, county, opinion, order, or synopsis"
        )

    raw_document_type = getattr(args, "document_type", None)
    document_type = (
        str(raw_document_type).strip().casefold() if raw_document_type else None
    )
    if document_type not in {None, "opinion", "order", "synopsis"}:
        raise ValueError(
            "Maryland Business and Technology --document-type must be "
            "opinion, order, or synopsis"
        )
    query_text: str | None = args.query
    case_number: str | None = None
    judge: str | None = None
    if args.command in {"case", "documents"}:
        case_number = args.query
        query_text = None
    elif search_field == "case-number":
        case_number = args.query
        query_text = None
    elif search_field == "judge":
        judge = args.query
        query_text = None
    elif search_field == "county":
        county = args.query
        query_text = None
    elif search_field in {"opinion", "order", "synopsis"}:
        document_type = search_field

    values.update(
        command="search",
        year=None,
        all_pages=True,
        query=query_text,
        case_number=case_number,
        county=county,
        judge=judge,
        document_type=document_type,
        filed_from=args.after,
        filed_to=args.before,
        limit=_caller_limit(args),
        cursor=args.cursor,
    )
    return argparse.Namespace(**values)


def _new_jersey_tax_court_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared searches to the current Tax Court property reports."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if (
        jurisdiction
        and jurisdiction not in {"NJ", "34", "US-NJ"}
        and not re.fullmatch(
            r"34\d{3}",
            jurisdiction,
        )
    ):
        raise ValueError("New Jersey Tax Court property reports cover New Jersey")
    if args.court_id and str(args.court_id) != query_new_jersey_tax_court.COURT_ID:
        raise ValueError("New Jersey Tax Court uses court ID nj-tax-court")

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": "any",
        "any": "any",
        "query": "any",
        "text": "any",
        "name": "case-title",
        "party": "case-title",
        "caption": "case-title",
        "title": "case-title",
        "case-title": "case-title",
        "docket": "docket",
        "case": "docket",
        "case-number": "docket",
        "parcel": "parcel",
        "block-lot": "parcel",
        "county": "county",
    }
    field = aliases.get(selected)
    if field is None:
        raise ValueError(
            "New Jersey Tax Court --search-field must be any, case-title, "
            "docket, parcel, or county"
        )

    query_text: str | None = args.query
    docket: str | None = None
    if args.command == "case":
        query_text = None
        docket = args.query
        field = "docket"

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        query=query_text,
        field=field,
        dataset="both",
        docket=docket,
        county=args.county,
        block=None,
        lot=None,
        unit=None,
        assessment_year=None,
        entered_from=args.after,
        entered_to=args.before,
        include_raw_row=False,
        limit=_caller_limit(args),
        cursor=args.cursor,
        cache_dir=query_new_jersey_tax_court.DEFAULT_CACHE_DIR,
        max_download_bytes=None,
        timeout=args.timeout,
        retry_attempts=3,
        chunk_size=query_new_jersey_tax_court.DEFAULT_CHUNK_SIZE,
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _new_jersey_tax_court_opinions_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared searches to the two official Tax Court opinion indexes."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if (
        jurisdiction
        and jurisdiction not in {"NJ", "34", "US-NJ"}
        and not re.fullmatch(r"34\d{3}", jurisdiction)
    ):
        raise ValueError("New Jersey Tax Court opinions cover New Jersey")
    if (
        args.court_id
        and str(args.court_id) != query_new_jersey_tax_court_opinions.COURT_ID
    ):
        raise ValueError("New Jersey Tax Court opinions use court ID nj-tax-court")

    if adapter_command == "document":
        values = vars(args).copy()
        values.update(
            command="document",
            url=args.query,
            transport="auto",
            metadata_only=False,
            save=Path(args.destination) if args.destination else None,
            timeout=args.timeout,
            minimum_interval=max(
                args.minimum_interval,
                query_new_jersey_tax_court_opinions.DEFAULT_MINIMUM_INTERVAL,
            ),
            max_attempts=3,
            retry_backoff=0.5,
            output=None,
            json_out=False,
        )
        return argparse.Namespace(**values)

    selected = str(args.search_field or "").strip().casefold().replace("_", "-")
    aliases = {
        "": "query",
        "any": "query",
        "query": "query",
        "text": "query",
        "name": "query",
        "party": "query",
        "caption": "query",
        "title": "query",
        "case-title": "query",
        "docket": "docket",
        "case": "docket",
        "case-number": "docket",
        "published": "published",
        "unpublished": "unpublished",
    }
    field = aliases.get(selected)
    if field is None:
        raise ValueError(
            "New Jersey Tax Court opinions --search-field must be query, "
            "docket, published, or unpublished"
        )

    collection_selections: list[str] = []
    if field in {"published", "unpublished"}:
        collection_selections.append(field)
        field = "query"
    for value in (
        getattr(args, "case_type", None),
        getattr(args, "document_type", None),
    ):
        normalized = str(value or "").strip().casefold().replace("_", "-")
        if normalized in {"", "opinion", "opinions", "tax-court-opinion"}:
            continue
        if normalized in {"published", "published-opinion"}:
            collection_selections.append("published")
        elif normalized in {"unpublished", "unpublished-opinion"}:
            collection_selections.append("unpublished")
        else:
            raise ValueError(
                "New Jersey Tax Court opinion type must be opinion, "
                "published, or unpublished"
            )
    if len(set(collection_selections)) > 1:
        raise ValueError("New Jersey Tax Court opinion collection selectors disagree")
    collection = collection_selections[0] if collection_selections else "both"

    query_text: str | None = args.query
    docket: str | None = None
    if args.command in {"case", "documents"} or field == "docket":
        query_text = None
        docket = args.query

    caller_limit = _caller_limit(args)
    values = vars(args).copy()
    values.update(
        command="search",
        query=query_text,
        collection=collection,
        docket=docket,
        after=args.after,
        before=args.before,
        transport="auto",
        limit=caller_limit,
        all_pages=caller_limit is None,
        cursor=args.cursor,
        timeout=args.timeout,
        minimum_interval=max(
            args.minimum_interval,
            query_new_jersey_tax_court_opinions.DEFAULT_MINIMUM_INTERVAL,
        ),
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _washington_statewide_jurisdiction(args: argparse.Namespace) -> None:
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"WA", "53", "US-WA"}:
        raise ValueError(
            "Washington appellate opinions and the AOC court directory use "
            "statewide Washington scope"
        )


def _washington_opinion_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared searches to Washington's official opinion surfaces."""

    _washington_statewide_jurisdiction(args)
    if args.court_id:
        raise ValueError(
            "Washington's combined opinion index does not expose a shared "
            "court-ID filter"
        )
    if args.courthouse or args.county:
        raise ValueError(
            "Washington appellate opinions do not expose courthouse or county "
            "selectors"
        )
    if args.after or args.before:
        raise ValueError(
            "Washington's opinion index does not expose exact date-range "
            "filtering through the shared route"
        )
    if args.cursor:
        raise ValueError("Washington's opinion index does not expose a cursor")
    if args.first_name:
        raise ValueError(
            "Washington appellate opinion search does not expose a first-name "
            "selector"
        )

    for label, selected in (
        ("--case-type", args.case_type),
        ("--document-type", getattr(args, "document_type", None)),
    ):
        normalized = str(selected or "").strip().casefold().replace("_", "-")
        if normalized not in {"", "opinion", "opinions", "appellate-opinion"}:
            raise ValueError(f"Washington appellate {label} must be opinion")

    values = vars(args).copy()
    if adapter_command == "opinion-download":
        if not args.destination:
            raise ValueError("Washington opinion download requires --destination")
        values.update(
            command="opinion-download",
            identifier=args.query,
            destination=Path(args.destination),
            overwrite=args.overwrite,
        )
    elif adapter_command == "opinion-detail":
        values.update(
            command="opinion-detail",
            identifier=args.query,
        )
    else:
        selected = (
            str(args.search_field or "")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        if selected not in {
            "",
            "any",
            "query",
            "text",
            "name",
            "party",
            "caption",
            "title",
            "case-title",
        }:
            raise ValueError(
                "Washington appellate opinion --search-field must be query, "
                "caption, title, name, or party"
            )
        query_text = (
            None
            if str(args.query).strip().casefold() in {"*", "all"}
            else args.query
        )
        values.update(
            command="opinions-list",
            scope="all",
            year=None,
            court_level=None,
            publication_status=None,
            query=query_text,
            limit=_caller_limit(args),
        )
    values.update(
        timeout=args.timeout,
        minimum_interval=max(
            args.minimum_interval,
            query_washington_courts.DEFAULT_MINIMUM_INTERVAL,
        ),
        max_attempts=3,
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _washington_directory_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate a last-name lookup to the official AOC personnel directory."""

    _washington_statewide_jurisdiction(args)
    if adapter_command != "directory-search":
        raise ValueError(
            f"unsupported Washington court-directory operation {adapter_command}"
        )
    selected = (
        str(args.search_field or "")
        .strip()
        .casefold()
        .replace("_", "-")
    )
    if selected not in {
        "",
        "directory",
        "person",
        "personnel",
        "name",
        "judge",
        "staff",
    }:
        raise ValueError(
            "Washington court-directory --search-field must be directory, "
            "person, name, judge, or staff"
        )
    if args.entity_kind != "person":
        raise ValueError(
            "Washington court-directory shared search currently represents "
            "personnel name results"
        )
    if any(
        (
            args.court_id,
            args.courthouse,
            args.county,
            args.case_type,
            args.after,
            args.before,
            args.cursor,
        )
    ):
        raise ValueError(
            "Washington court-directory personnel search accepts a last name "
            "and optional first initial, without case, court, date, or cursor "
            "filters"
        )
    if args.partial or args.phonetic or args.exclude_inactive:
        raise ValueError(
            "Washington court-directory search does not expose the selected "
            "name-matching option"
        )
    initial = str(args.first_name or "").strip().upper() or None
    if initial is not None and re.fullmatch(r"[A-Z]", initial) is None:
        raise ValueError(
            "Washington court-directory --first-name accepts one source-native "
            "first initial"
        )
    last_name = str(args.query).strip()
    if last_name.casefold() in {"*", "all"}:
        raise ValueError(
            "Washington court-directory search requires a last-name selector"
        )
    values = vars(args).copy()
    values.update(
        command="directory-search",
        last_name=last_name,
        initial=initial,
        limit=_caller_limit(args),
        timeout=args.timeout,
        minimum_interval=max(
            args.minimum_interval,
            query_washington_courts.DEFAULT_MINIMUM_INTERVAL,
        ),
        max_attempts=3,
        output=None,
        json_out=False,
    )
    return argparse.Namespace(**values)


def _va_general_district_court_selector(args: argparse.Namespace) -> str:
    """Return one source-native court component without treating it as FIPS."""

    court_id = str(args.court_id or "").strip()
    courthouse = str(args.courthouse or "").strip()
    if court_id and courthouse:
        raise ValueError(
            "Virginia General District Court accepts either --court-id or "
            "--courthouse for one court component, not both"
        )
    if court_id:
        match = re.fullmatch(r"va-gdc-(\d{3})", court_id, flags=re.IGNORECASE)
        if match is None:
            raise ValueError(
                "Virginia General District Court --court-id must have the "
                "canonical form va-gdc-NNN"
            )
        return match.group(1)
    if courthouse:
        return courthouse
    raise ValueError(
        "Virginia General District Court requires --court-id va-gdc-NNN or "
        "--courthouse with a source-published court code or name"
    )


def _va_general_district_division(args: argparse.Namespace) -> str:
    selected = str(args.case_type or "civil").strip().casefold().replace("_", "-")
    aliases = {
        "v": "civil",
        "civil": "civil",
        "t": "traffic-criminal",
        "traffic": "traffic-criminal",
        "criminal": "traffic-criminal",
        "traffic-criminal": "traffic-criminal",
    }
    division = aliases.get(selected)
    if division is None:
        raise ValueError(
            "Virginia General District Court --case-type selects the source "
            "division and must be civil or traffic-criminal"
        )
    return division


def _va_general_district_hearing_date(args: argparse.Namespace) -> str:
    """Resolve the shared calendar selectors to one source-native exact date."""

    explicit = str(getattr(args, "hearing_date", None) or "").strip()
    query_value = str(args.query or "").strip()
    direct = explicit or (query_value if query_value not in {"*", "all"} else "")
    lower = str(args.after or "").strip()
    upper = str(args.before or "").strip()
    if not direct:
        if not lower or not upper:
            raise ValueError(
                "Virginia General District Court hearing search requires an "
                "exact date as the query, --hearing-date, or equal --after "
                "and --before values"
            )
        direct = lower
    normalized = query_va_general_district._source_date(direct)
    for label, value in (("--after", lower), ("--before", upper)):
        if value and query_va_general_district._source_date(value) != normalized:
            raise ValueError(
                "Virginia General District Court hearing search accepts one "
                f"exact date; {label} does not match it"
            )
    if explicit and query_value not in {"", "*", "all"}:
        if query_va_general_district._source_date(query_value) != normalized:
            raise ValueError(
                "Virginia General District Court calendar query and "
                "--hearing-date must select the same exact date"
            )
    return normalized


def _va_general_district_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to Virginia's court-component application."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"VA", "51", "US-VA"}:
        raise ValueError(
            "Virginia General District Court jurisdiction is statewide Virginia; "
            "select its application court component separately"
        )
    court = _va_general_district_court_selector(args)
    division = _va_general_district_division(args)
    command = adapter_command
    if args.command == "search":
        selected = str(args.search_field or "").strip().casefold().replace("_", "-")
        aliases = {
            "": "name",
            "any": "name",
            "query": "name",
            "text": "name",
            "name": "name",
            "party": "name",
            "business": "name",
            "case": "case",
            "case-number": "case",
            "docket": "case",
            "hearing": "hearing",
            "hearing-date": "hearing",
            "calendar": "hearing",
            "service": "service",
            "service-process": "service",
            "process": "service",
            "person-served": "service",
        }
        command = aliases.get(selected, "")
        if not command:
            raise ValueError(
                "Virginia General District Court --search-field must be name, "
                "case-number, hearing-date, or service-process"
            )

    if command != "hearing" and (args.after or args.before):
        raise ValueError(
            "Virginia General District Court shared date selectors map only "
            "to its exact hearing-date operation"
        )

    values = vars(args).copy()
    values.update(
        command=command,
        court=court,
        division=division,
        output=None,
        json_out=False,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
    )
    if command == "name":
        values.update(
            last_name_or_business=args.query,
            first_name=args.first_name,
            middle_name=None,
            suffix=None,
            status=("current" if args.exclude_inactive else "all"),
            limit=_caller_limit(args),
            cursor=args.cursor,
            max_pages=None,
        )
    elif command == "case":
        values.update(case_number=args.query)
    elif command == "hearing":
        values.update(
            hearing_date=_va_general_district_hearing_date(args),
            hearing_time=None,
            courtroom=None,
            hearing_type=None,
            limit=_caller_limit(args),
            cursor=args.cursor,
            max_pages=None,
        )
    elif command == "service":
        values.update(
            last_name=args.query,
            first_name=args.first_name,
            middle_name=None,
            suffix=None,
            limit=_caller_limit(args),
            cursor=args.cursor,
            max_pages=None,
        )
    return argparse.Namespace(**values)


def _edva_bankruptcy_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate exact EDVA bankruptcy reads to the RECAP adapter."""

    court_id = str(args.court_id or "").strip().casefold()
    allowed_court_ids = {
        query_edva_bankruptcy.COURT_ID.casefold(),
        query_edva_bankruptcy.COURTLISTENER_COURT_ID.casefold(),
    }
    if court_id and court_id not in allowed_court_ids:
        raise ValueError(
            "E.D. Virginia bankruptcy --court-id must identify "
            f"{query_edva_bankruptcy.COURT_ID} or "
            f"{query_edva_bankruptcy.COURTLISTENER_COURT_ID}"
        )

    runtime = {
        "command": adapter_command,
        "output": None,
        "json_out": False,
    }
    if adapter_command == "case":
        return argparse.Namespace(
            docket_number=args.query,
            entry_limit=_caller_limit(args),
            cursor=args.cursor,
            **runtime,
        )
    if adapter_command == "entries":
        try:
            docket_id = int(str(args.query).strip())
        except ValueError as error:
            raise ValueError(
                "EDVA bankruptcy docket and documents selectors use a "
                "CourtListener numeric docket ID"
            ) from error
        if docket_id <= 0:
            raise ValueError(
                "EDVA bankruptcy CourtListener docket ID must be positive"
            )
        return argparse.Namespace(
            docket_id=docket_id,
            limit=_caller_limit(args),
            cursor=args.cursor,
            **runtime,
        )
    if adapter_command in {"sources", "probe"}:
        return argparse.Namespace(**runtime)
    raise ValueError(
        f"unsupported EDVA bankruptcy operation {adapter_command}"
    )


def _doj_court_records_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared reads without treating DOJ release groups as dockets."""

    if args.jurisdiction:
        raise ValueError(
            "DOJ Epstein Court Records spans multiple underlying courts and "
            "does not expose a jurisdiction filter"
        )
    if any(
        (
            args.court_id,
            args.courthouse,
            args.case_type,
            args.after,
            args.before,
            args.style_other,
            args.originating_coa,
            args.county,
            args.trial_court,
            args.first_name,
            args.date_of_birth,
            args.drivers_license,
            args.plate_state,
            args.violation_number,
            args.search_scope,
            args.search_field,
            args.partial,
            args.phonetic,
            args.exclude_inactive,
            args.entity_kind != "person",
        )
    ):
        raise ValueError(
            "DOJ Epstein Court Records exposes release-corpus case-title or "
            "docket text search and exact DOJ case-page document listing, "
            "not source-native court, party, date, or status filters"
        )
    if args.ingest:
        raise ValueError(
            "DOJ release-corpus rows are not normalized as complete court "
            "cases; use the direct corpus or document-ingestion workflow"
        )

    selector = " ".join(str(args.query or "").split()).strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "source",
        "sources",
    }
    bounded = (
        args.cursor is not None
        or args.max_records is not None
        or args.limit_explicit
    )
    runtime = {
        "command": adapter_command,
        "timeout": args.timeout,
        "minimum_interval": (
            args.minimum_interval
            if getattr(args, "minimum_interval_explicit", False)
            else query_doj_court_records.DEFAULT_MINIMUM_INTERVAL
        ),
        "output": None,
        "json_out": False,
    }

    if adapter_command == "index":
        if args.cursor is not None:
            raise ValueError(
                "DOJ release index is a single current page and does not "
                "emit a continuation cursor"
            )
        return argparse.Namespace(
            query=None if selector_is_all else selector,
            limit=_caller_limit(args),
            **runtime,
        )
    if adapter_command == "case":
        if selector_is_all:
            raise ValueError(
                "DOJ document listing requires an exact DOJ court-record "
                "case-page URL"
            )
        return argparse.Namespace(
            case_url=query_doj_court_records._canonical_case_url(selector),
            limit=_caller_limit(args),
            cursor=args.cursor,
            **runtime,
        )
    if adapter_command in {"sources", "probe"}:
        allowed = (
            {"", "*", "all", "source", "sources", "routes", "coverage"}
            if adapter_command == "sources"
            else {"", "*", "all", "probe"}
        )
        if selector.casefold() not in allowed or bounded:
            raise ValueError(
                "DOJ release-corpus discovery and probe expose source "
                "coverage without row filters or continuation controls"
            )
        return argparse.Namespace(**runtime)
    raise ValueError(
        f"unsupported DOJ court-record release operation {adapter_command}"
    )


def _michigan_appellate_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared case/name operations to Michigan's appellate API."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "MI",
        "26",
        "US-MI",
    }:
        raise ValueError("Michigan appellate search covers Michigan")

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        max_json_bytes=query_michigan_appellate.DEFAULT_MAX_JSON_BYTES,
        max_pdf_bytes=query_michigan_appellate.DEFAULT_MAX_PDF_BYTES,
        output=None,
        json_out=False,
    )
    if adapter_command == "download":
        if not args.destination:
            raise ValueError("Michigan appellate download requires --destination")
        values.update(
            document_url=args.query,
            destination=Path(args.destination),
        )
        return argparse.Namespace(**values)

    if args.after or args.before:
        raise ValueError(
            "Michigan's shared appellate route does not map ISO ranges to "
            "the portal's source-native filing/release facet labels; use the "
            "direct adapter when selecting those facets"
        )

    court_labels = {
        "us-mi-court-of-appeals": "Court Of Appeals",
        "us-mi-supreme-court": "Supreme Court",
        "us-mi-court-of-claims": "Court Of Claims",
    }
    appellate_court = None
    if args.court_id:
        appellate_court = court_labels.get(str(args.court_id))
        if appellate_court is None:
            raise ValueError(
                "Michigan appellate --court-id must be "
                "us-mi-court-of-appeals, us-mi-supreme-court, or "
                "us-mi-court-of-claims"
            )

    selected_type = str(args.case_type or "cases").strip().casefold()
    result_type_aliases = {
        "case": "cases",
        "cases": "cases",
        "opinion": "opinions",
        "opinions": "opinions",
        "order": "orders",
        "orders": "orders",
    }
    result_type = result_type_aliases.get(selected_type)
    if result_type is None:
        raise ValueError(
            "Michigan appellate --case-type must be cases, opinions, or orders"
        )

    selected_field = str(args.search_field or "").strip().casefold().replace("_", "-")
    field_aliases = {
        "": "party",
        "name": "party",
        "party": "party",
        "participant": "party",
        "keyword": "keyword",
        "query": "keyword",
        "case-number": "case-number",
        "appellate-case-number": "case-number",
        "attorney": "attorney",
        "bar-number": "bar-number",
        "lower-court": "lower-court",
        "author": "author",
        "panel-member": "panel-member",
    }
    field = field_aliases.get(selected_field)
    if field is None:
        raise ValueError(
            "Michigan appellate --search-field must be party, keyword, "
            "case-number, attorney, bar-number, lower-court, author, or "
            "panel-member"
        )
    if args.command == "case":
        field = "case-number"
        result_type = "cases"

    query_text = args.query if field == "keyword" else ""
    name_value = (
        " ".join(part for part in (args.first_name, args.query) if part)
        if field in {"party", "attorney"}
        else args.query
    )
    values.update(
        command="search",
        query_text=query_text,
        result_type=result_type,
        sort_order="Relevance",
        page=1,
        page_size=args.page_size or query_michigan_appellate.DEFAULT_PAGE_SIZE,
        limit=(
            _caller_limit(args) or args.limit or query_michigan_appellate.DEFAULT_LIMIT
        ),
        cursor=args.cursor,
        appellate_court=appellate_court,
        attorney_name=name_value if field == "attorney" else None,
        bar_number=args.query if field == "bar-number" else None,
        case_id=args.query if field == "case-number" else None,
        case_type=None,
        lower_court=args.query if field == "lower-court" else None,
        open_status=bool(args.exclude_inactive),
        party_name=name_value if field == "party" else None,
        author_name=args.query if field == "author" else None,
        panel_member=args.query if field == "panel-member" else None,
        courts=[args.county] if args.county else None,
        court_types=None,
        judges=None,
        filing_dates=None,
        resources=None,
        release_dates=None,
        native_parameters=None,
    )
    return argparse.Namespace(**values)


def _michigan_business_court_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate represented shared operations to the Business Court corpus."""

    if args.jurisdiction and str(args.jurisdiction).upper() not in {
        "MI",
        "26",
        "US-MI",
    }:
        raise ValueError("Michigan Business Court search covers Michigan")
    if args.court_id and str(args.court_id) != (
        query_michigan_business_court.COLLECTION_COURT_ID
    ):
        raise ValueError(
            "Michigan Business Court --court-id identifies the statewide "
            "document collection; use the direct adapter's --court option "
            "for an exact source-published court facet"
        )

    values = vars(args).copy()
    values.update(
        command=adapter_command,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=query_michigan_business_court.DEFAULT_MAX_ATTEMPTS,
        output=None,
        json_out=False,
    )
    if adapter_command == "search":
        if args.after or args.before:
            raise ValueError(
                "Michigan Business Court search has no native date-range "
                "selector; filter retained pleading/order dates after "
                "exhaustive retrieval"
            )
        if args.county:
            raise ValueError(
                "Michigan Business Court --county does not identify an exact "
                "native court facet; list and select the exact facet with the "
                "direct adapter"
            )
        selected_field = (
            str(args.search_field or "")
            .strip()
            .casefold()
            .replace("_", "-")
        )
        if selected_field not in {"", "all", "full-text", "keyword", "text"}:
            raise ValueError(
                "Michigan Business Court exposes one full-text query rather "
                "than field-specific shared search"
            )
        values.update(
            query_text=args.query,
            sort_order="Relevance",
            business_courts=([args.case_type] if args.case_type else None),
            courts=None,
            audience=None,
            page=1,
            limit=_caller_limit(args),
            cursor=args.cursor,
        )
        return argparse.Namespace(**values)

    selector = str(args.query or "").strip().casefold()
    if adapter_command == "sources":
        if selector not in {"", "*", "all", "court", "courts", "source", "sources"}:
            raise ValueError(
                "Michigan Business Court discovery lists the source's exact "
                "court facets"
            )
        values["audience"] = None
        return argparse.Namespace(**values)
    if adapter_command == "probe":
        if selector not in {"", "*", "all", "probe"}:
            raise ValueError(
                "Michigan Business Court probe uses the verified full-corpus "
                "and zero-result sentinels"
            )
        values["zero_query"] = query_michigan_business_court.PROBE_ZERO_QUERY
        return argparse.Namespace(**values)
    if adapter_command == "download":
        if not args.destination:
            raise ValueError("Michigan Business Court download requires --destination")
        destination = Path(args.destination)
        if destination.exists() and not args.overwrite:
            raise ValueError(
                "Michigan Business Court destination exists; pass --overwrite "
                "to replace it"
            )
        values.update(
            document_url=args.query,
            destination=destination,
            expected_sha256=None,
            max_bytes=None,
        )
        return argparse.Namespace(**values)
    raise ValueError(
        f"unsupported Michigan Business Court operation {adapter_command}"
    )


def _california_directory_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared text search to the official 58-county directory."""

    if adapter_command != "search":
        raise ValueError(
            f"unsupported California court-directory operation {adapter_command}"
        )
    county_by_geoid = {
        geoid: county
        for county, geoid in query_california_court_directory.COUNTY_FIPS.items()
    }
    county_by_court = {
        f"ca-{county.casefold().replace(' ', '-')}-superior": county
        for county in query_california_court_directory.COUNTY_FIPS
    }
    county = str(args.county or "").strip() or None
    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"CA", "06", "US-CA"}:
        jurisdiction_county = county_by_geoid.get(jurisdiction)
        if jurisdiction_county is None:
            raise ValueError(
                "California court-directory jurisdiction must be California "
                "or a California county GEOID"
            )
        if county and county.casefold() != jurisdiction_county.casefold():
            raise ValueError(
                "California court-directory county and jurisdiction selectors "
                "identify different counties"
            )
        county = jurisdiction_county
    if args.court_id:
        court_county = county_by_court.get(str(args.court_id).strip().casefold())
        if court_county is None:
            raise ValueError(
                "California court-directory --court-id must identify one "
                "county superior court published by the directory"
            )
        if county and county.casefold() != court_county.casefold():
            raise ValueError(
                "California court-directory court and county selectors "
                "identify different counties"
            )
        county = court_county
    if args.after or args.before or args.case_type:
        raise ValueError(
            "California court-directory snapshots do not expose case, date, "
            "or case-type fields"
        )

    selector = str(args.query).strip()
    list_all = selector.casefold() in {"*", "all", "directory"}
    return argparse.Namespace(
        command="list" if list_all else "search",
        query=None if list_all else selector,
        county=county,
        appellate_district=None,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=3,
        retry_backoff=0.5,
        output=None,
        json_out=False,
    )


def _california_opinion_collection(args: argparse.Namespace) -> str:
    """Resolve the shared publication selector without changing case identity."""

    aliases = {
        "all": "both",
        "appellate": "both",
        "appellate-opinion": "both",
        "both": "both",
        "document": "both",
        "documents": "both",
        "metadata": "both",
        "opinion": "both",
        "opinions": "both",
        "pdf": "both",
        "published": "published",
        "published-opinion": "published",
        "citable": "published",
        "slip-opinion": "published",
        "unpublished": "unpublished",
        "unpublished-opinion": "unpublished",
        "non-citable": "unpublished",
    }
    selected: list[tuple[str, str]] = []
    for label, value in (
        ("--case-type", getattr(args, "case_type", None)),
        (
            "--document-type",
            (
                getattr(args, "document_type", None)
                if args.command == "documents"
                else None
            ),
        ),
    ):
        normalized = str(value or "").strip().casefold().replace("_", "-")
        if not normalized:
            continue
        collection = aliases.get(normalized)
        if collection is None:
            raise ValueError(
                f"California opinions {label} must identify published, "
                "unpublished, both, opinion, or PDF metadata"
            )
        selected.append((label, collection))
    specific = {collection for _label, collection in selected if collection != "both"}
    if len(specific) > 1:
        raise ValueError(
            "California opinions --case-type and --document-type identify "
            "different publication collections"
        )
    return next(iter(specific), "both")


def _california_opinions_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to the current official opinion feeds."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "06", "CA", "US-CA"}:
        raise ValueError(
            "California opinion feeds have statewide California scope"
        )
    if args.court_id and str(args.court_id) not in {
        str(spec["court_id"]) for spec in query_california_opinions.COURTS.values()
    }:
        raise ValueError(
            "California opinions --court-id must identify a court in the "
            "adapter manifest"
        )

    unrelated = any(
        (
            args.county,
            args.courthouse,
            args.first_name,
            args.date_of_birth,
            args.drivers_license,
            args.plate_state,
            args.violation_number,
            args.partial,
            args.phonetic,
            args.exclude_inactive,
            args.search_scope,
            args.style_other,
            args.originating_coa,
            args.trial_court,
        )
    )
    if unrelated:
        raise ValueError(
            "California opinion feeds expose collection, court, case-number, "
            "title, and source-native paging selectors"
        )

    runtime = {
        "timeout": args.timeout,
        "minimum_interval": max(
            args.minimum_interval,
            query_california_opinions.DEFAULT_MINIMUM_INTERVAL,
        ),
        "max_attempts": query_california_opinions.DEFAULT_MAX_ATTEMPTS,
        "retry_backoff": 0.5,
        "output": None,
        "json_out": False,
    }
    selector = " ".join(str(args.query or "").split()).strip()
    selector_is_all = selector.casefold() in {"", "*", "all", "source"}
    bounds_selected = (
        args.cursor is not None
        or args.max_records is not None
        or args.limit_explicit
    )

    if adapter_command == "download":
        if not args.destination:
            raise ValueError(
                "California opinion download requires an exact official "
                "document URL and --destination"
            )
        if getattr(args, "case_number", None):
            raise ValueError(
                "California opinion download uses the exact document URL; it "
                "does not derive a path from --case-number"
            )
        return argparse.Namespace(
            command="download",
            url=selector,
            destination=Path(args.destination),
            overwrite=args.overwrite,
            **runtime,
        )

    if adapter_command == "discovery":
        if bounds_selected or args.after or args.before or args.court_id or args.case_type:
            raise ValueError(
                "California opinion discovery returns the source manifest or "
                "official complementary routes without result filters"
            )
        selected = selector.casefold().replace("_", "-")
        if selected in {"", "*", "all", "manifest", "routes", "source"}:
            command = "manifest"
        elif selected in {
            "alternative",
            "alternatives",
            "complement",
            "complements",
            "official-reports",
        }:
            command = "alternatives"
        else:
            raise ValueError(
                "California opinion discovery accepts manifest or alternatives"
            )
        return argparse.Namespace(command=command, **runtime)

    if adapter_command == "probe":
        if (
            not selector_is_all
            and selector.casefold() != "probe"
        ) or bounds_selected or args.after or args.before or args.court_id or args.case_type:
            raise ValueError(
                "California opinion probe is a bounded source-contract check"
            )
        return argparse.Namespace(command="probe", **runtime)

    if adapter_command != "search":
        raise ValueError(
            f"unsupported California opinion operation {adapter_command}"
        )
    if args.after or args.before:
        raise ValueError(
            "California's current opinion feeds do not expose native date-range "
            "filters"
        )
    if args.page_size not in query_california_opinions.PAGE_SIZE_CHOICES:
        choices = ", ".join(
            str(value) for value in query_california_opinions.PAGE_SIZE_CHOICES
        )
        raise ValueError(
            f"California opinion --page-size must be one of {choices}"
        )

    exact_case_operation = args.command in {"case", "documents"}
    search_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    case_fields = {
        "case",
        "case-number",
        "docket",
        "opinion-identifier",
    }
    title_fields = {
        "any",
        "caption",
        "case-title",
        "name",
        "party",
        "query",
        "text",
        "title",
    }
    if exact_case_operation:
        if selector_is_all:
            raise ValueError(
                "California opinion case and document operations require one "
                "exact appellate case number or opinion identifier"
            )
        if search_field and search_field not in case_fields:
            raise ValueError(
                "California opinion exact-case operations use case-number or "
                "opinion-identifier search"
            )
        field = "case-number"
    elif search_field in case_fields:
        if selector_is_all:
            raise ValueError(
                "California opinion case-number search requires a case number"
            )
        field = "case-number"
    elif search_field in title_fields:
        field = "title"
    elif search_field:
        raise ValueError(
            "California opinions --search-field must identify case-number or title"
        )
    elif selector_is_all:
        field = "all"
    elif re.fullmatch(r"[A-Za-z]\d{5,7}[A-Za-z]{0,3}", selector):
        field = "case-number"
    else:
        field = "title"

    selected_limit = _caller_limit(args)
    return argparse.Namespace(
        command="search",
        collection=_california_opinion_collection(args),
        court=args.court_id,
        case_number=selector if field == "case-number" else None,
        title=selector if field == "title" else None,
        page=0,
        page_size=args.page_size,
        limit=(
            selected_limit
            if selected_limit is not None
            else query_california_opinions.DEFAULT_LIMIT
        ),
        cursor=args.cursor,
        **runtime,
    )


def _harris_court_bulk_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared operations to exact Harris bulk artifacts."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "48", "48201", "TX", "US-TX"}:
        raise ValueError(
            "Harris District Clerk public datasets cover Harris County, Texas"
        )
    selector = str(args.query or "").strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "catalog",
        "source",
    }
    runtime = {
        "timeout": args.timeout,
        "minimum_interval": max(
            args.minimum_interval,
            query_harris_court_bulk.REQUEST_DELAY,
        ),
        "catalog_db": args.catalog_db,
        "catalog_config": str(
            query_harris_court_bulk.DEFAULT_CATALOG_CONFIG_PATH
        ),
        "output": None,
        "json_out": False,
    }

    if adapter_command == "list":
        section = None
        family = str(args.case_type or "").strip() or None
        text_filter = None
        search_field = str(args.search_field or "").strip().casefold()
        if not selector_is_all:
            if search_field == "section" or (
                not search_field
                and selector.casefold() in {"civil", "criminal"}
            ):
                section = selector.title()
            elif search_field == "family":
                family = selector
            else:
                text_filter = selector
        published_after = None
        published_before = None
        if args.after:
            try:
                published_after = date.fromisoformat(str(args.after)).isoformat()
            except ValueError as error:
                raise ValueError("--after must use YYYY-MM-DD") from error
        if args.before:
            try:
                published_before = date.fromisoformat(str(args.before)).isoformat()
            except ValueError as error:
                raise ValueError("--before must use YYYY-MM-DD") from error
        if (
            published_after
            and published_before
            and published_after > published_before
        ):
            raise ValueError("--after must not be later than --before")
        return argparse.Namespace(
            command="list",
            section=section,
            family=family,
            text_filter=text_filter,
            published_after=published_after,
            published_before=published_before,
            result_limit=_caller_limit(args),
            **runtime,
        )

    if adapter_command == "inspect":
        if selector_is_all:
            raise ValueError(
                "Harris bulk artifact inspection requires one exact live "
                "catalog locator, artifact ID, or unambiguous filename"
            )
        return argparse.Namespace(
            command="inspect",
            artifact=selector,
            sample_bytes=query_harris_court_bulk.DEFAULT_SAMPLE_BYTES,
            **runtime,
        )

    if adapter_command == "sentinel":
        return argparse.Namespace(command="sentinel", **runtime)

    if adapter_command == "download":
        if selector_is_all:
            raise ValueError(
                "Harris bulk download requires one exact live catalog locator, "
                "artifact ID, or unambiguous filename"
            )
        if not args.destination:
            raise ValueError("Harris bulk download requires --destination")
        return argparse.Namespace(
            command="download",
            artifact=selector,
            destination=Path(args.destination),
            overwrite=args.overwrite,
            **runtime,
        )

    raise ValueError(f"unsupported Harris bulk operation {adapter_command}")


def _osceola_benchmark_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared case operations to Osceola's Benchmark portal."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {"", "12", "12097", "FL", "US-FL"}:
        raise ValueError(
            "Osceola Benchmark accepts Florida or Osceola County jurisdiction "
            "context"
        )
    if args.county and str(args.county).strip().casefold() not in {
        "osceola",
        "osceola county",
        "12097",
    }:
        raise ValueError("Osceola Benchmark covers Osceola County")
    valid_courts = {
        "fl-09-osceola",
        "fl-09-osceola-circuit",
        "fl-09-osceola-county",
    }
    if args.court_id and str(args.court_id).strip().casefold() not in valid_courts:
        raise ValueError(
            "Osceola Benchmark --court-id must identify an Osceola circuit "
            "or county court"
        )
    if args.after or args.before or args.case_type or args.courthouse:
        raise ValueError(
            "Osceola Benchmark does not publish shared date-range, case-type, "
            "or courthouse filters"
        )

    runtime = {
        "timeout": args.timeout,
        "minimum_interval": max(
            args.minimum_interval,
            query_osceola_courts.DEFAULT_MINIMUM_INTERVAL,
        ),
        "max_attempts": query_osceola_courts.DEFAULT_MAX_ATTEMPTS,
        "output": None,
        "json_out": False,
    }
    selector = " ".join(str(args.query or "").split()).strip()

    if adapter_command == "manifest":
        return argparse.Namespace(
            command="manifest",
            source=args.source,
            **runtime,
        )
    if adapter_command == "probe":
        return argparse.Namespace(
            command="probe",
            source=args.source,
            **runtime,
        )
    if adapter_command in {"case", "docket"}:
        return argparse.Namespace(
            command=adapter_command,
            case_number=selector,
            source=query_osceola_courts.PORTAL_SOURCE_ID,
            **runtime,
        )
    if adapter_command == "document-metadata":
        docket_id = str(args.docket_entry_uuid or "").strip()
        if not docket_id:
            raise ValueError(
                "Osceola document metadata requires --docket-entry-uuid with "
                "the stable Benchmark docket ID"
            )
        return argparse.Namespace(
            command="document-metadata",
            case_number=selector,
            docket_id=docket_id,
            source=query_osceola_courts.PORTAL_SOURCE_ID,
            **runtime,
        )
    if adapter_command != "search":
        raise ValueError(
            f"unsupported Osceola Benchmark operation {adapter_command}"
        )

    field = (
        str(args.search_field or "name")
        .strip()
        .casefold()
        .replace("_", "-")
    )
    field_aliases = {
        "arresting-case": "arresting-case-number",
        "arresting-case-number": "arresting-case-number",
        "agency-case-number": "arresting-case-number",
        "case": "case-number",
        "case-number": "case-number",
        "citation": "citation-number",
        "citation-number": "citation-number",
        "name": "name",
        "organization": "name",
        "party": "name",
        "person": "name",
    }
    search_mode = field_aliases.get(field)
    if args.search_field is None and re.fullmatch(
        r"\d{4}\s+[A-Za-z]{2}\s+\d+",
        selector,
    ):
        search_mode = "case-number"
    if search_mode is None:
        raise ValueError(
            "Osceola Benchmark --search-field must identify name, case "
            "number, citation number, or arresting case number"
        )
    if args.partial or args.phonetic:
        raise ValueError(
            "Osceola Benchmark does not publish partial or phonetic mode "
            "selectors"
        )
    selected_limit = args.limit
    if args.max_records is not None:
        selected_limit = min(selected_limit, args.max_records)
    return argparse.Namespace(
        command="search",
        query=selector,
        search_mode=search_mode,
        limit=selected_limit,
        cursor=args.cursor,
        source=query_osceola_courts.PORTAL_SOURCE_ID,
        **runtime,
    )


def _santa_clara_tentative_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate current tentative-ruling directory and artifact operations."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"CA", "06", "06085", "US-CA"}:
        raise ValueError(
            "Santa Clara tentative rulings accept California or Santa Clara "
            "County jurisdiction context"
        )
    if args.court_id and (
        str(args.court_id).strip().casefold()
        != query_santa_clara_court_records.COURT_ID.casefold()
    ):
        raise ValueError(
            "Santa Clara tentative-ruling --court-id must identify the "
            "Santa Clara Superior Court"
        )
    if args.after or args.before or args.case_type:
        raise ValueError(
            "The current tentative-ruling publication does not expose a "
            "historical date range or case-type selector"
        )

    runtime = {
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "max_attempts": 3,
        "retry_backoff": 0.5,
        "output": None,
        "json_out": False,
    }
    if adapter_command == "download":
        if not args.destination:
            raise ValueError(
                "Santa Clara tentative-ruling download requires --destination"
            )
        return argparse.Namespace(
            command="download",
            url=args.query,
            destination=Path(args.destination),
            **runtime,
        )
    if adapter_command != "rulings":
        raise ValueError(
            f"unsupported Santa Clara tentative-ruling operation {adapter_command}"
        )

    selector = str(args.query).strip()
    if selector.casefold() in {"*", "all", "departments", "directory"}:
        if args.command == "documents":
            raise ValueError(
                "Santa Clara tentative-ruling documents require a department "
                "number"
            )
        return argparse.Namespace(command="departments", **runtime)
    if not selector.isdigit():
        raise ValueError(
            "Santa Clara tentative-ruling selection must be a department "
            "number or all"
        )
    return argparse.Namespace(
        command="rulings",
        department=int(selector),
        **runtime,
    )


def _san_diego_index_offset(
    cursor: str | None,
    *,
    operation: str,
) -> int:
    if cursor is None:
        return 0
    prefix = f"sd-index:{operation}-row-offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError(
            f"San Diego {operation} cursor must have form {prefix}N"
        )
    return int(cursor[len(prefix) :])


def _san_diego_court_index_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate party and exact-case lookups to the Court Index."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction and jurisdiction not in {"CA", "06", "06073", "US-CA"}:
        raise ValueError(
            "San Diego Court Index accepts California or San Diego County "
            "jurisdiction context"
        )
    if args.court_id and (
        str(args.court_id).strip().casefold()
        != query_san_diego_court_index.COURT_ID.casefold()
    ):
        raise ValueError(
            "San Diego Court Index --court-id must identify the San Diego "
            "Superior Court"
        )
    if args.after or args.before:
        raise ValueError(
            "San Diego shared Court Index routes do not convert ISO date "
            "ranges to the source's filing-year selector"
        )
    site = str(args.courthouse or "all").strip().casefold().replace("_", "-")
    if site not in query_san_diego_court_index.SITE_VALUES:
        raise ValueError(
            "San Diego --courthouse must be all, east-county, kearny-mesa, "
            "north-county, ramona, san-diego, or south-county"
        )
    runtime = {
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "max_attempts": 3,
        "output": None,
        "json_out": False,
    }
    if adapter_command == "case-search":
        case_type = str(args.case_type or "all").strip().casefold().replace("_", "-")
        if case_type not in query_san_diego_court_index.CASE_SEARCH_TYPE_VALUES:
            raise ValueError(
                "San Diego exact-case --case-type must be all, civil, "
                "criminal, domestic, mental-health, or probate"
            )
        return argparse.Namespace(
            command="case-search",
            case_number=args.query,
            case_type=case_type,
            site=site,
            limit=_caller_limit(args),
            offset=_san_diego_index_offset(args.cursor, operation="case"),
            **runtime,
        )
    if adapter_command != "party-search":
        raise ValueError(
            f"unsupported San Diego Court Index operation {adapter_command}"
        )

    search_field = (
        str(args.search_field or "party")
        .strip()
        .casefold()
        .replace("_", "-")
    )
    if search_field not in {
        "party",
        "name",
        "person",
        "organization",
        "business",
    }:
        raise ValueError(
            "San Diego Court Index shared search supports party or business names"
        )
    case_type = str(args.case_type or "").strip().casefold().replace("_", "-")
    if case_type not in query_san_diego_court_index.CASE_TYPE_VALUES:
        raise ValueError(
            "San Diego party search requires --case-type civil, criminal, "
            "domestic, mental-health, or probate"
        )
    return argparse.Namespace(
        command="party-search",
        case_type=case_type,
        site=site,
        party_type="all",
        begin_year=1974,
        end_year=date.today().year,
        last_name=args.query,
        first_name=args.first_name,
        date_of_birth=args.date_of_birth,
        limit=_caller_limit(args),
        offset=_san_diego_index_offset(args.cursor, operation="party"),
        **runtime,
    )


def _ny_attorney_registration_args(
    args: argparse.Namespace,
    adapter_command: str,
) -> argparse.Namespace:
    """Translate shared lookups to OCA's public registration snapshot."""

    jurisdiction = str(args.jurisdiction or "").strip().upper()
    if jurisdiction not in {
        "",
        "36",
        "NY",
        "US-NY",
        "US-GEOID-36",
        "NEW YORK",
        "NEW YORK STATE",
    }:
        raise ValueError(
            "New York attorney registrations have statewide New York "
            "jurisdiction (36, NY, or US-NY)"
        )
    if any(
        (
            args.court_id,
            args.courthouse,
            args.case_type,
            args.after,
            args.before,
            args.style_other,
            args.originating_coa,
            args.trial_court,
        )
    ):
        raise ValueError(
            "New York attorney registrations do not expose case, filing-date, "
            "courthouse, or court selectors"
        )
    if any(
        (
            args.date_of_birth,
            args.drivers_license,
            args.plate_state,
            args.violation_number,
            args.search_scope,
            args.phonetic,
        )
    ):
        raise ValueError(
            "New York attorney registrations do not publish the selected "
            "source-native identity field"
        )

    selector = " ".join(str(args.query or "").split()).strip()
    selector_is_all = selector.casefold() in {
        "",
        "*",
        "all",
        "source",
        "sources",
    }
    search_field = (
        str(args.search_field or "").strip().casefold().replace("_", "-")
    )
    bounded = (
        args.cursor is not None
        or args.max_records is not None
        or args.limit_explicit
    )
    runtime = {
        "page_size": args.page_size,
        "timeout": args.timeout,
        "minimum_interval": args.minimum_interval,
        "retry_attempts": query_ny_attorneys.DEFAULT_RETRY_ATTEMPTS,
        "output": None,
        "json_out": False,
    }

    if adapter_command == "sources":
        if selector.casefold() not in {
            "",
            "*",
            "all",
            "source",
            "sources",
            "manifest",
            "routes",
            "alternatives",
            "coverage",
        }:
            raise ValueError(
                "New York attorney discovery returns the source manifest and "
                "its complementary official routes"
            )
        if search_field not in {
            "",
            "source",
            "manifest",
            "routes",
            "alternatives",
            "coverage",
        }:
            raise ValueError(
                "New York attorney discovery --search-field must identify "
                "the source manifest or complementary routes"
            )
        if (
            bounded
            or args.first_name
            or args.county
            or args.entity_kind != "person"
            or args.partial
            or args.exclude_inactive
        ):
            raise ValueError(
                "New York attorney discovery returns source coverage and "
                "routes rather than filtered registration rows"
            )
        return argparse.Namespace(command="sources", output=None, json_out=False)

    if adapter_command == "probe":
        if (
            not selector_is_all
            and selector.casefold() != "probe"
        ) or search_field not in {"", "probe", "source"}:
            raise ValueError(
                "New York attorney probe is a bounded source-contract check"
            )
        if (
            bounded
            or args.first_name
            or args.county
            or args.entity_kind != "person"
            or args.partial
            or args.exclude_inactive
        ):
            raise ValueError(
                "New York attorney probe does not apply registration search "
                "filters or continuation controls"
            )
        return argparse.Namespace(command="probe", **runtime)

    if adapter_command == "registration":
        if search_field not in {
            "",
            "detail",
            "id",
            "registration",
            "registration-number",
            "bar-number",
        }:
            raise ValueError(
                "New York attorney detail uses an exact OCA registration "
                "number"
            )
        if (
            bounded
            or args.first_name
            or args.county
            or args.entity_kind != "person"
            or args.partial
            or args.exclude_inactive
        ):
            raise ValueError(
                "New York attorney detail uses only the exact registration "
                "number"
            )
        return argparse.Namespace(
            command="registration",
            registration_number=query_ny_attorneys._registration_number(
                selector
            ),
            **runtime,
        )

    if adapter_command != "search":
        raise ValueError(
            f"unsupported New York attorney operation {adapter_command}"
        )

    field_aliases = {
        "attorney": "name",
        "attorney-name": "name",
        "person": "name",
        "name": "name",
        "first": "first-name",
        "first-name": "first-name",
        "middle": "middle-name",
        "middle-name": "middle-name",
        "last": "last-name",
        "last-name": "last-name",
        "organization": "company",
        "organisation": "company",
        "business": "company",
        "company": "company",
        "employer": "company",
        "firm": "company",
        "city": "city",
        "state": "state",
        "zip": "zip",
        "zip-code": "zip",
        "postal-code": "zip",
        "country": "country",
        "county": "county",
        "law-school": "law-school",
        "status": "status",
    }
    if search_field:
        field = field_aliases.get(search_field)
        if field is None:
            if search_field in {
                "bar-number",
                "registration",
                "registration-number",
            }:
                raise ValueError(
                    "Use shared detail for an exact OCA registration number"
                )
            raise ValueError(
                "New York attorney --search-field must identify a name, "
                "organization, office location, law school, or status"
            )
    else:
        field = (
            "company"
            if args.entity_kind == "organization"
            else "last-name"
            if args.first_name
            else "name"
        )
    if args.entity_kind == "organization" and field != "company":
        raise ValueError(
            "New York attorney organization search uses the company field"
        )

    first = " ".join(str(args.first_name or "").split()).strip() or None
    if first:
        if field == "name":
            field = "last-name"
        elif field != "last-name":
            raise ValueError(
                "New York attorney --first-name accompanies a last-name "
                "search"
            )

    county = " ".join(str(args.county or "").split()).strip() or None
    if field == "county" and county and not selector_is_all:
        if county.casefold() != selector.casefold():
            raise ValueError(
                "New York attorney county selectors identify different "
                "values"
            )
        county = None

    return argparse.Namespace(
        command="search",
        query=None if selector_is_all else selector,
        field=field,
        match="contains",
        first=first,
        middle=None,
        last=None,
        company=None,
        city=None,
        state=None,
        postal_code=None,
        country=None,
        county=county,
        law_school=None,
        status=(
            "Currently registered"
            if args.exclude_inactive
            else None
        ),
        year_admitted=None,
        department=None,
        limit=_caller_limit(args),
        cursor=args.cursor,
        **runtime,
    )


LIVE_ROUTES: dict[str, dict[str, _LiveRoute]] = {
    ACIS_SOURCE_ID: {
        command: _LiveRoute(query_florida_acis, command, _acis_args)
        for command in (
            "search",
            "case",
            "docket",
            "calendar",
            "documents",
            "download",
        )
    },
    FLORIDA_NINTH_OPINIONS_SOURCE_ID: {
        "search": _LiveRoute(
            query_florida_ninth_opinions,
            "search",
            _florida_ninth_opinions_args,
        )
    },
    FLORIDA_COURT_LOCATION_DIRECTORY_SOURCE_ID: {
        "search": _LiveRoute(
            FLORIDA_COURT_DIRECTORY_DATA_ADAPTER,
            "locations",
            _florida_location_directory_args,
        )
    },
    FLORIDA_VIRTUAL_COURTROOM_DIRECTORY_SOURCE_ID: {
        "search": _LiveRoute(
            FLORIDA_COURT_DIRECTORY_DATA_ADAPTER,
            "virtual",
            _florida_virtual_directory_args,
        )
    },
    FLORIDA_OSCA_PUBLIC_RECORDS_SOURCE_ID: {
        "search": _LiveRoute(
            FLORIDA_COURT_DIRECTORY_DATA_ADAPTER,
            "data-request",
            _florida_osca_request_args,
        )
    },
    FLORIDA_TRIAL_COURT_STATISTICS_SOURCE_ID: {
        "search": _LiveRoute(
            FLORIDA_COURT_DIRECTORY_DATA_ADAPTER,
            "statistics",
            _florida_statistics_args,
        )
    },
    HARRIS_COURT_BULK_SOURCE_ID: {
        "discovery": _LiveRoute(
            HARRIS_COURT_BULK_ADAPTER,
            "list",
            _harris_court_bulk_args,
        ),
        "documents": _LiveRoute(
            HARRIS_COURT_BULK_ADAPTER,
            "inspect",
            _harris_court_bulk_args,
        ),
        "probe": _LiveRoute(
            HARRIS_COURT_BULK_ADAPTER,
            "sentinel",
            _harris_court_bulk_args,
        ),
        "download": _LiveRoute(
            HARRIS_COURT_BULK_ADAPTER,
            "download",
            _harris_court_bulk_args,
        ),
    },
    OSCEOLA_BENCHMARK_SOURCE_ID: {
        "search": _LiveRoute(
            OSCEOLA_BENCHMARK_ADAPTER,
            "search",
            _osceola_benchmark_args,
        ),
        "case": _LiveRoute(
            OSCEOLA_BENCHMARK_ADAPTER,
            "case",
            _osceola_benchmark_args,
        ),
        "docket": _LiveRoute(
            OSCEOLA_BENCHMARK_ADAPTER,
            "docket",
            _osceola_benchmark_args,
        ),
        "documents": _LiveRoute(
            OSCEOLA_BENCHMARK_ADAPTER,
            "document-metadata",
            _osceola_benchmark_args,
        ),
        "discovery": _LiveRoute(
            OSCEOLA_BENCHMARK_ADAPTER,
            "manifest",
            _osceola_benchmark_args,
        ),
        "probe": _LiveRoute(
            OSCEOLA_BENCHMARK_ADAPTER,
            "probe",
            _osceola_benchmark_args,
        ),
    },
    **{
        source_id: {
            "discovery": _LiveRoute(
                OSCEOLA_REPORT_ADAPTER,
                "manifest",
                _osceola_benchmark_args,
            ),
            "probe": _LiveRoute(
                OSCEOLA_REPORT_ADAPTER,
                "probe",
                _osceola_benchmark_args,
            ),
        }
        for source_id in OSCEOLA_REPORT_SOURCE_IDS
    },
    DC_APPELLATE_CASES_SOURCE_ID: {
        operation: _LiveRoute(
            DC_APPELLATE_CASES_ADAPTER,
            "case" if operation in {"case", "docket", "documents"} else operation,
            _dc_appellate_args,
        )
        for operation in ("search", "case", "docket", "documents", "download")
    },
    **{
        source_id: {
            "search": _LiveRoute(
                DC_COURT_DIRECTORY_ADAPTER,
                "directory",
                _dc_court_directory_args,
            )
        }
        for source_id in DC_DIRECTORY_SOURCE_IDS
    },
    DC_OPINIONS_SOURCE_ID: {
        operation: _LiveRoute(
            DC_OPINIONS_ADAPTER,
            "list",
            _dc_opinions_args,
        )
        for operation in ("search", "case", "documents")
    }
    | {
        "download": _LiveRoute(
            DC_OPINIONS_ADAPTER,
            "download",
            _dc_opinions_args,
        )
    },
    DC_TODAY_CALENDAR_SOURCE_ID: {
        operation: _LiveRoute(
            DC_CALENDAR_ADAPTER,
            "search",
            _dc_calendar_args,
        )
        for operation in ("search", "case", "calendar")
    },
    DC_CRIMINAL_CALENDAR_SOURCE_ID: {
        operation: _LiveRoute(
            DC_CALENDAR_ADAPTER,
            "criminal",
            _dc_calendar_args,
        )
        for operation in ("search", "case", "calendar")
    },
    DC_TAX_CALENDAR_SOURCE_ID: {
        "calendar": _LiveRoute(
            DC_CALENDAR_ADAPTER,
            "artifacts",
            _dc_calendar_args,
        )
    },
    DC_APPEALS_CALENDAR_SOURCE_ID: {
        "calendar": _LiveRoute(
            DC_CALENDAR_ADAPTER,
            "appeals",
            _dc_calendar_args,
        )
    },
    CALIFORNIA_COURT_DIRECTORY_SOURCE_ID: {
        "search": _LiveRoute(
            CALIFORNIA_COURT_DIRECTORY_ADAPTER,
            "search",
            _california_directory_args,
        )
    },
    CALIFORNIA_OPINIONS_SOURCE_ID: {
        operation: _LiveRoute(
            CALIFORNIA_OPINIONS_ADAPTER,
            (
                "discovery"
                if operation == "discovery"
                else "probe"
                if operation == "probe"
                else "download"
                if operation == "download"
                else "search"
            ),
            _california_opinions_args,
        )
        for operation in (
            "search",
            "case",
            "documents",
            "discovery",
            "probe",
            "download",
        )
    },
    GEORGIA_COURT_DIRECTORY_SOURCE_ID: {
        "search": _LiveRoute(
            GEORGIA_COURT_DIRECTORY_ADAPTER,
            "search",
            _georgia_court_directory_args,
        ),
        "discovery": _LiveRoute(
            GEORGIA_COURT_DIRECTORY_ADAPTER,
            "manifest",
            _georgia_court_directory_args,
        ),
        "probe": _LiveRoute(
            GEORGIA_COURT_DIRECTORY_ADAPTER,
            "probe",
            _georgia_court_directory_args,
        ),
        "detail": _LiveRoute(
            GEORGIA_COURT_DIRECTORY_ADAPTER,
            "detail",
            _georgia_court_directory_args,
        ),
    },
    **{
        source_id: {
            "search": _LiveRoute(
                GEORGIA_COURT_ACCESS_ADAPTER,
                "search",
                _georgia_court_access_args,
            ),
            "discovery": _LiveRoute(
                GEORGIA_COURT_ACCESS_ADAPTER,
                "providers",
                _georgia_court_access_args,
            ),
            "probe": _LiveRoute(
                GEORGIA_COURT_ACCESS_ADAPTER,
                "probe",
                _georgia_court_access_args,
            ),
        }
        for source_id in GEORGIA_COURT_ACCESS_SOURCE_IDS
    },
    GEORGIA_CASELOAD_DASHBOARD_SOURCE_ID: {
        "search": _LiveRoute(
            query_georgia_court_data,
            "dashboards",
            _georgia_court_data_args,
        ),
        "discovery": _LiveRoute(
            query_georgia_court_data,
            "handoff",
            _georgia_court_data_args,
        ),
        "probe": _LiveRoute(
            query_georgia_court_data,
            "probe",
            _georgia_court_data_args,
        ),
    },
    GEORGIA_WORKLOAD_ASSESSMENT_SOURCE_ID: {
        "search": _LiveRoute(
            query_georgia_court_data,
            "workloads",
            _georgia_court_data_args,
        ),
        "documents": _LiveRoute(
            query_georgia_court_data,
            "workloads",
            _georgia_court_data_args,
        ),
        "detail": _LiveRoute(
            query_georgia_court_data,
            "document",
            _georgia_court_data_args,
        ),
        "probe": _LiveRoute(
            query_georgia_court_data,
            "probe",
            _georgia_court_data_args,
        ),
    },
    GEORGIA_SUPREME_DOCKET_SOURCE_ID: {
        "search": _LiveRoute(
            GEORGIA_SUPREME_DOCKET_ADAPTER,
            "search",
            _georgia_supreme_docket_args,
        ),
        "case": _LiveRoute(
            GEORGIA_SUPREME_DOCKET_ADAPTER,
            "detail",
            _georgia_supreme_docket_args,
        ),
        "docket": _LiveRoute(
            GEORGIA_SUPREME_DOCKET_ADAPTER,
            "detail",
            _georgia_supreme_docket_args,
        ),
        "documents": _LiveRoute(
            GEORGIA_SUPREME_DOCKET_ADAPTER,
            "documents",
            _georgia_supreme_docket_args,
        ),
        "discovery": _LiveRoute(
            GEORGIA_SUPREME_DOCKET_ADAPTER,
            "discovery",
            _georgia_supreme_docket_args,
        ),
        "probe": _LiveRoute(
            GEORGIA_SUPREME_DOCKET_ADAPTER,
            "probe",
            _georgia_supreme_docket_args,
        ),
    },
    **{
        source_id: {
            operation: _LiveRoute(
                GEORGIA_SUPREME_PUBLICATIONS_ADAPTER,
                (
                    "discovery"
                    if operation == "discovery"
                    else "probe"
                    if operation == "probe"
                    else "download"
                    if operation == "download"
                    else "search"
                ),
                _georgia_supreme_publications_args,
            )
            for operation in (
                "search",
                "case",
                "documents",
                "discovery",
                "probe",
                "download",
            )
        }
        for source_id in GEORGIA_SUPREME_PUBLICATION_SOURCE_IDS
    },
    SANTA_CLARA_TENTATIVE_SOURCE_ID: {
        "search": _LiveRoute(
            SANTA_CLARA_ADAPTER,
            "rulings",
            _santa_clara_tentative_args,
        ),
        "calendar": _LiveRoute(
            SANTA_CLARA_ADAPTER,
            "rulings",
            _santa_clara_tentative_args,
        ),
        "documents": _LiveRoute(
            SANTA_CLARA_ADAPTER,
            "rulings",
            _santa_clara_tentative_args,
        ),
        "download": _LiveRoute(
            SANTA_CLARA_ADAPTER,
            "download",
            _santa_clara_tentative_args,
        ),
    },
    SAN_DIEGO_COURT_INDEX_SOURCE_ID: {
        "search": _LiveRoute(
            query_san_diego_court_index,
            "party-search",
            _san_diego_court_index_args,
        ),
        "case": _LiveRoute(
            query_san_diego_court_index,
            "case-search",
            _san_diego_court_index_args,
        ),
    },
    FRESNO_CALENDAR_SOURCE_ID: {
        "calendar": _LiveRoute(
            FRESNO_ADAPTER,
            "calendar",
            _fresno_args,
        )
    },
    FRESNO_RULINGS_SOURCE_ID: {
        "calendar": _LiveRoute(
            FRESNO_ADAPTER,
            "rulings",
            _fresno_args,
        )
    },
    FRESNO_PROBATE_SOURCE_ID: {
        "notes": _LiveRoute(
            FRESNO_ADAPTER,
            "probate-notes",
            _fresno_args,
        )
    },
    ORANGE_CALENDAR_SOURCE_ID: {
        operation: _LiveRoute(
            ORANGE_COURT_ADAPTER,
            "calendar",
            _orange_court_args,
        )
        for operation in ("search", "case", "calendar")
    },
    **{
        source_id: {
            "search": _LiveRoute(
                ORANGE_COURT_ADAPTER,
                "ruling-index",
                _orange_court_args,
            ),
            "calendar": _LiveRoute(
                ORANGE_COURT_ADAPTER,
                "ruling-index",
                _orange_court_args,
            ),
            "documents": _LiveRoute(
                ORANGE_COURT_ADAPTER,
                "ruling",
                _orange_court_args,
            ),
        }
        for source_id in ORANGE_RULING_DIVISIONS_BY_SOURCE
    },
    RIVERSIDE_CALENDAR_SOURCE_ID: {
        "calendar": _LiveRoute(
            RIVERSIDE_COURT_ADAPTER,
            "calendar",
            _riverside_court_args,
        )
    },
    RIVERSIDE_RULING_SOURCE_ID: {
        "search": _LiveRoute(
            RIVERSIDE_COURT_ADAPTER,
            "ruling-index",
            _riverside_court_args,
        ),
        "calendar": _LiveRoute(
            RIVERSIDE_COURT_ADAPTER,
            "ruling-index",
            _riverside_court_args,
        ),
        "documents": _LiveRoute(
            RIVERSIDE_COURT_ADAPTER,
            "ruling",
            _riverside_court_args,
        ),
    },
    QLD_ECOURTS_SOURCE_ID: {
        "search": _LiveRoute(
            QLD_ECOURTS_ADAPTER,
            "search",
            _qld_ecourts_args,
        ),
        **{
            operation: _LiveRoute(
                QLD_ECOURTS_ADAPTER,
                "case",
                _qld_ecourts_args,
            )
            for operation in ("case", "docket", "documents")
        },
    },
    WISCONSIN_COURT_DIRECTORY_SOURCE_ID: {
        "search": _LiveRoute(
            WISCONSIN_COURT_DIRECTORY_ADAPTER,
            "search",
            _wisconsin_court_directory_args,
        )
    },
    WISCONSIN_WSCCA_SOURCE_ID: {
        command: _LiveRoute(
            WISCONSIN_WSCCA_ADAPTER,
            command,
            _wisconsin_wscca_args,
        )
        for command in ("search", "case", "docket", "documents", "download")
    },
    WISCONSIN_OPINIONS_SOURCE_ID: {
        operation: _LiveRoute(
            WISCONSIN_OPINIONS_ADAPTER,
            "search",
            _wisconsin_opinions_args,
        )
        for operation in ("search", "case", "documents")
    }
    | {
        "download": _LiveRoute(
            WISCONSIN_OPINIONS_ADAPTER,
            "download",
            _wisconsin_opinions_args,
        )
    },
    MARYLAND_PUBLIC_CASES_SOURCE_ID: {
        operation: _LiveRoute(
            MARYLAND_PUBLIC_CASES_ADAPTER,
            "search",
            _maryland_public_cases_args,
        )
        for operation in ("search", "case")
    },
    MARYLAND_ESTATE_SOURCE_ID: {
        operation: _LiveRoute(
            MARYLAND_ESTATE_ADAPTER,
            ("resolve-estate" if operation in {"case", "docket"} else "decedent"),
            _maryland_estate_args,
        )
        for operation in ("search", "case", "docket")
    },
    MARYLAND_ESTATE_NOTICE_SOURCE_ID: {
        "search": _LiveRoute(
            MARYLAND_ESTATE_SUPPLEMENTS_ADAPTER,
            "notices",
            _maryland_estate_notice_args,
        ),
        "probe": _LiveRoute(
            MARYLAND_ESTATE_SUPPLEMENTS_ADAPTER,
            "probe-notices",
            _maryland_estate_notice_args,
        ),
    },
    MARYLAND_ESTATE_CLAIM_SOURCE_ID: {
        "search": _LiveRoute(
            MARYLAND_ESTATE_SUPPLEMENTS_ADAPTER,
            "claims",
            _maryland_estate_claim_args,
        ),
        "claims": _LiveRoute(
            MARYLAND_ESTATE_SUPPLEMENTS_ADAPTER,
            "claims",
            _maryland_estate_claim_args,
        ),
        "detail": _LiveRoute(
            MARYLAND_ESTATE_SUPPLEMENTS_ADAPTER,
            "claim-detail",
            _maryland_estate_claim_args,
        ),
        "probe": _LiveRoute(
            MARYLAND_ESTATE_SUPPLEMENTS_ADAPTER,
            "probe-claims",
            _maryland_estate_claim_args,
        ),
    },
    MARYLAND_JUDGMENT_LIENS_SOURCE_ID: {
        operation: _LiveRoute(
            MARYLAND_JUDGMENT_LIENS_ADAPTER,
            ("detail" if operation in {"case", "docket", "claims"} else "person"),
            _maryland_judgment_liens_args,
        )
        for operation in ("search", "case", "docket", "claims")
    },
    MARYLAND_OPINIONS_SOURCE_ID: {
        operation: _LiveRoute(
            MARYLAND_OPINIONS_ADAPTER,
            "reported",
            _maryland_opinions_args,
        )
        for operation in ("search", "case", "documents")
    }
    | {
        "download": _LiveRoute(
            MARYLAND_OPINIONS_ADAPTER,
            "download",
            _maryland_opinions_args,
        )
    },
    MARYLAND_BUSINESS_OPINIONS_SOURCE_ID: {
        operation: _LiveRoute(
            MARYLAND_BUSINESS_OPINIONS_ADAPTER,
            "search",
            _maryland_business_opinions_args,
        )
        for operation in ("search", "case", "documents")
    }
    | {
        "download": _LiveRoute(
            MARYLAND_BUSINESS_OPINIONS_ADAPTER,
            "download",
            _maryland_business_opinions_args,
        )
    },
    NEW_JERSEY_TAX_COURT_SOURCE_ID: {
        operation: _LiveRoute(
            NEW_JERSEY_TAX_COURT_ADAPTER,
            "search",
            _new_jersey_tax_court_args,
        )
        for operation in ("search", "case")
    },
    NEW_JERSEY_TAX_COURT_OPINIONS_SOURCE_ID: {
        operation: _LiveRoute(
            NEW_JERSEY_TAX_COURT_OPINIONS_ADAPTER,
            "search",
            _new_jersey_tax_court_opinions_args,
        )
        for operation in ("search", "case", "documents")
    }
    | {
        "download": _LiveRoute(
            NEW_JERSEY_TAX_COURT_OPINIONS_ADAPTER,
            "document",
            _new_jersey_tax_court_opinions_args,
        )
    },
    NY_ATTORNEY_REGISTRATION_SOURCE_ID: {
        "search": _LiveRoute(
            NY_ATTORNEY_REGISTRATION_ADAPTER,
            "search",
            _ny_attorney_registration_args,
        ),
        "detail": _LiveRoute(
            NY_ATTORNEY_REGISTRATION_ADAPTER,
            "registration",
            _ny_attorney_registration_args,
        ),
        "discovery": _LiveRoute(
            NY_ATTORNEY_REGISTRATION_ADAPTER,
            "sources",
            _ny_attorney_registration_args,
        ),
        "probe": _LiveRoute(
            NY_ATTORNEY_REGISTRATION_ADAPTER,
            "probe",
            _ny_attorney_registration_args,
        ),
    },
    WASHINGTON_APPELLATE_OPINIONS_SOURCE_ID: {
        "search": _LiveRoute(
            WASHINGTON_COURTS_ADAPTER,
            "opinions-list",
            _washington_opinion_args,
        ),
        "case": _LiveRoute(
            WASHINGTON_COURTS_ADAPTER,
            "opinion-detail",
            _washington_opinion_args,
        ),
        "documents": _LiveRoute(
            WASHINGTON_COURTS_ADAPTER,
            "opinion-detail",
            _washington_opinion_args,
        ),
        "download": _LiveRoute(
            WASHINGTON_COURTS_ADAPTER,
            "opinion-download",
            _washington_opinion_args,
        ),
    },
    WASHINGTON_COURT_DIRECTORY_SOURCE_ID: {
        "search": _LiveRoute(
            WASHINGTON_COURTS_ADAPTER,
            "directory-search",
            _washington_directory_args,
        )
    },
    VA_GENERAL_DISTRICT_SOURCE_ID: {
        "search": _LiveRoute(
            VA_GENERAL_DISTRICT_ADAPTER,
            "name",
            _va_general_district_args,
        ),
        "case": _LiveRoute(
            VA_GENERAL_DISTRICT_ADAPTER,
            "case",
            _va_general_district_args,
        ),
        "calendar": _LiveRoute(
            VA_GENERAL_DISTRICT_ADAPTER,
            "hearing",
            _va_general_district_args,
        ),
    },
    DOJ_COURT_RECORDS_SOURCE_ID: {
        "search": _LiveRoute(
            DOJ_COURT_RECORDS_ADAPTER,
            "index",
            _doj_court_records_args,
        ),
        "documents": _LiveRoute(
            DOJ_COURT_RECORDS_ADAPTER,
            "case",
            _doj_court_records_args,
        ),
        "discovery": _LiveRoute(
            DOJ_COURT_RECORDS_ADAPTER,
            "sources",
            _doj_court_records_args,
        ),
        "probe": _LiveRoute(
            DOJ_COURT_RECORDS_ADAPTER,
            "probe",
            _doj_court_records_args,
        ),
    },
    EDVA_BANKRUPTCY_SOURCE_ID: {
        "case": _LiveRoute(
            EDVA_BANKRUPTCY_ADAPTER,
            "case",
            _edva_bankruptcy_args,
        ),
        "docket": _LiveRoute(
            EDVA_BANKRUPTCY_ADAPTER,
            "entries",
            _edva_bankruptcy_args,
        ),
        "documents": _LiveRoute(
            EDVA_BANKRUPTCY_ADAPTER,
            "entries",
            _edva_bankruptcy_args,
        ),
        "discovery": _LiveRoute(
            EDVA_BANKRUPTCY_ADAPTER,
            "sources",
            _edva_bankruptcy_args,
        ),
        "probe": _LiveRoute(
            EDVA_BANKRUPTCY_ADAPTER,
            "probe",
            _edva_bankruptcy_args,
        ),
    },
    MICHIGAN_APPELLATE_SOURCE_ID: {
        "search": _LiveRoute(
            MICHIGAN_APPELLATE_ADAPTER,
            "search",
            _michigan_appellate_args,
        ),
        "case": _LiveRoute(
            MICHIGAN_APPELLATE_ADAPTER,
            "search",
            _michigan_appellate_args,
        ),
        "download": _LiveRoute(
            MICHIGAN_APPELLATE_ADAPTER,
            "download",
            _michigan_appellate_args,
        ),
    },
    MICHIGAN_BUSINESS_COURT_SOURCE_ID: {
        "search": _LiveRoute(
            MICHIGAN_BUSINESS_COURT_ADAPTER,
            "search",
            _michigan_business_court_args,
        ),
        "discovery": _LiveRoute(
            MICHIGAN_BUSINESS_COURT_ADAPTER,
            "sources",
            _michigan_business_court_args,
        ),
        "probe": _LiveRoute(
            MICHIGAN_BUSINESS_COURT_ADAPTER,
            "probe",
            _michigan_business_court_args,
        ),
        "download": _LiveRoute(
            MICHIGAN_BUSINESS_COURT_ADAPTER,
            "download",
            _michigan_business_court_args,
        ),
    },
    CONNECTICUT_CIVIL_FAMILY_SOURCE_ID: {
        "search": _LiveRoute(
            CONNECTICUT_CIVIL_FAMILY_ADAPTER,
            "search",
            _connecticut_civil_family_args,
        ),
        **{
            operation: _LiveRoute(
                CONNECTICUT_CIVIL_FAMILY_ADAPTER,
                "case",
                _connecticut_civil_family_args,
            )
            for operation in ("case", "docket", "documents")
        },
        "download": _LiveRoute(
            CONNECTICUT_CIVIL_FAMILY_ADAPTER,
            "document",
            _connecticut_civil_family_args,
        ),
        "discovery": _LiveRoute(
            CONNECTICUT_CIVIL_FAMILY_ADAPTER,
            "routes",
            _connecticut_civil_family_args,
        ),
        "probe": _LiveRoute(
            CONNECTICUT_CIVIL_FAMILY_ADAPTER,
            "probe",
            _connecticut_civil_family_args,
        ),
    },
    NEW_MEXICO_CASE_LOOKUP_SOURCE_ID: {
        "search": _LiveRoute(
            NEW_MEXICO_CASE_LOOKUP_ADAPTER,
            "search",
            _new_mexico_case_lookup_args,
        ),
        **{
            operation: _LiveRoute(
                NEW_MEXICO_CASE_LOOKUP_ADAPTER,
                "case",
                _new_mexico_case_lookup_args,
            )
            for operation in ("case", "docket", "claims")
        },
        "discovery": _LiveRoute(
            NEW_MEXICO_CASE_LOOKUP_ADAPTER,
            "source",
            _new_mexico_case_lookup_args,
        ),
        "probe": _LiveRoute(
            NEW_MEXICO_CASE_LOOKUP_ADAPTER,
            "probe",
            _new_mexico_case_lookup_args,
        ),
    },
    OREGON_APPELLATE_SOURCE_ID: {
        "search": _LiveRoute(
            query_oregon_appellate,
            "search-party",
            _oregon_appellate_args,
        ),
        "case": _LiveRoute(
            query_oregon_appellate,
            "case",
            _oregon_appellate_args,
        ),
        "docket": _LiveRoute(
            query_oregon_appellate,
            "docket",
            _oregon_appellate_args,
        ),
        "calendar": _LiveRoute(
            query_oregon_appellate,
            "calendar",
            _oregon_appellate_args,
        ),
        "documents": _LiveRoute(
            query_oregon_appellate,
            "document-metadata",
            _oregon_appellate_args,
        ),
    },
    OREGON_COURT_CALENDAR_SOURCE_ID: {
        "calendar": _LiveRoute(
            query_oregon_court_calendar,
            "search",
            _oregon_court_calendar_args,
        ),
    },
    **{
        source_id: {
            "search": _LiveRoute(
                OREGON_TYLER_ADAPTER,
                "search",
                _eugene_municipal_args,
            ),
            "case": _LiveRoute(
                OREGON_TYLER_ADAPTER,
                "case",
                _eugene_municipal_args,
            ),
            "docket": _LiveRoute(
                OREGON_TYLER_ADAPTER,
                "docket",
                _eugene_municipal_args,
            ),
            "calendar": _LiveRoute(
                OREGON_TYLER_ADAPTER,
                "dockets",
                _eugene_municipal_args,
            ),
        }
        for source_id in OREGON_TYLER_MUNICIPAL_SOURCE_IDS
    },
    OREGON_SMART_SEARCH_SOURCE_ID: {
        "search": _LiveRoute(
            OREGON_SMART_SEARCH_ADAPTER,
            "prepare",
            _oregon_smart_search_args,
        ),
    },
    OREGON_OJCIN_PRODUCT_DIRECTORY_SOURCE_ID: {
        "products": _LiveRoute(
            OREGON_OJCIN_PRODUCT_DIRECTORY_ADAPTER,
            "products",
            _oregon_ojcin_product_args,
        ),
        "handoff": _LiveRoute(
            OREGON_OJCIN_PRODUCT_DIRECTORY_ADAPTER,
            "handoff",
            _oregon_ojcin_product_args,
        ),
    },
    **{
        source_id: {
            "calendar": _LiveRoute(
                query_oregon_appellate_calendars,
                "search",
                _oregon_appellate_calendar_args,
            ),
        }
        for source_id in OREGON_APPELLATE_CALENDAR_SOURCE_IDS
    },
    BEXAR_HISTORICAL_SOURCE_ID: {
        "search": _LiveRoute(
            query_bexar_courts,
            "search",
            _bexar_args,
        ),
        "case": _LiveRoute(
            query_bexar_courts,
            "case",
            _bexar_args,
        ),
        "documents": _LiveRoute(
            query_bexar_courts,
            "case",
            _bexar_args,
        ),
        "download": _LiveRoute(
            query_bexar_courts,
            "page",
            _bexar_args,
        ),
    },
    PA_UJS_SOURCE_ID: {
        "search": _LiveRoute(
            query_pa_ujs,
            "search",
            _pa_ujs_args,
        ),
        "case": _LiveRoute(
            query_pa_ujs,
            "case",
            _pa_ujs_args,
        ),
        "docket": _LiveRoute(
            query_pa_ujs,
            "case",
            _pa_ujs_args,
        ),
        "documents": _LiveRoute(
            query_pa_ujs,
            "case",
            _pa_ujs_args,
        ),
        "download": _LiveRoute(
            query_pa_ujs,
            "report",
            _pa_ujs_args,
        ),
    },
    DELAWARE_COURTCONNECT_SOURCE_ID: {
        "search": _LiveRoute(
            query_delaware_courts,
            "cases",
            _delaware_courtconnect_args,
        ),
        "case": _LiveRoute(
            query_delaware_courts,
            "case",
            _delaware_courtconnect_args,
        ),
        "docket": _LiveRoute(
            query_delaware_courts,
            "case",
            _delaware_courtconnect_args,
        ),
        "documents": _LiveRoute(
            query_delaware_courts,
            "case",
            _delaware_courtconnect_args,
        ),
    },
    DENVER_COUNTY_DOCKET_SOURCE_ID: {
        "calendar": _LiveRoute(
            query_denver_county_court,
            "calendar",
            _denver_county_docket_args,
        ),
    },
    COLORADO_JUDICIAL_SOURCE_ID: {
        "search": _LiveRoute(
            query_colorado_judicial,
            "search",
            _colorado_judicial_args,
        ),
    },
    LOS_ANGELES_CIVIL_SOURCE_ID: {
        "case": _LiveRoute(
            LOS_ANGELES_CIVIL_ADAPTER,
            "case",
            _los_angeles_civil_args,
        ),
        "docket": _LiveRoute(
            LOS_ANGELES_CIVIL_ADAPTER,
            "case",
            _los_angeles_civil_args,
        ),
        "documents": _LiveRoute(
            LOS_ANGELES_CIVIL_ADAPTER,
            "case",
            _los_angeles_civil_args,
        ),
        "calendar": _LiveRoute(
            LOS_ANGELES_CIVIL_ADAPTER,
            "rulings",
            _los_angeles_civil_args,
        ),
    },
    LOS_ANGELES_PROBATE_SOURCE_ID: {
        "case": _LiveRoute(
            query_los_angeles_probate,
            "case",
            _los_angeles_probate_args,
        ),
        "docket": _LiveRoute(
            query_los_angeles_probate,
            "case",
            _los_angeles_probate_args,
        ),
        "documents": _LiveRoute(
            query_los_angeles_probate,
            "case",
            _los_angeles_probate_args,
        ),
        "notes": _LiveRoute(
            query_los_angeles_probate,
            "notes",
            _los_angeles_probate_args,
        ),
        "calendar": _LiveRoute(
            query_los_angeles_probate,
            "calendar",
            _los_angeles_probate_args,
        ),
    },
    PIMA_SOURCE_ID: {
        "search": _LiveRoute(
            query_pima_courts,
            "search",
            _pima_args,
        ),
        "case": _LiveRoute(
            query_pima_courts,
            "case",
            _pima_args,
        ),
        "docket": _LiveRoute(
            query_pima_courts,
            "case",
            _pima_args,
        ),
        "documents": _LiveRoute(
            query_pima_courts,
            "case",
            _pima_args,
        ),
        "download": _LiveRoute(
            query_pima_courts,
            "document",
            _pima_args,
        ),
    },
    FRANKLIN_CIO_SOURCE_ID: {
        "search": _LiveRoute(
            FRANKLIN_CIO_ADAPTER,
            "name",
            _franklin_cio_args,
        ),
        "case": _LiveRoute(
            FRANKLIN_CIO_ADAPTER,
            "case",
            _franklin_cio_args,
        ),
        "docket": _LiveRoute(
            FRANKLIN_CIO_ADAPTER,
            "case",
            _franklin_cio_args,
        ),
        "documents": _LiveRoute(
            FRANKLIN_CIO_ADAPTER,
            "case",
            _franklin_cio_args,
        ),
        "download": _LiveRoute(
            FRANKLIN_CIO_ADAPTER,
            "document",
            _franklin_cio_args,
        ),
        "discovery": _LiveRoute(
            FRANKLIN_CIO_ADAPTER,
            "source",
            _franklin_cio_args,
        ),
        "probe": _LiveRoute(
            FRANKLIN_CIO_ADAPTER,
            "probe",
            _franklin_cio_args,
        ),
    },
    FRANKLIN_MUNICIPAL_SOURCE_ID: {
        "search": _LiveRoute(
            FRANKLIN_MUNICIPAL_ADAPTER,
            "search",
            _franklin_municipal_args,
        ),
        "case": _LiveRoute(
            FRANKLIN_MUNICIPAL_ADAPTER,
            "case",
            _franklin_municipal_args,
        ),
        "docket": _LiveRoute(
            FRANKLIN_MUNICIPAL_ADAPTER,
            "case",
            _franklin_municipal_args,
        ),
        "documents": _LiveRoute(
            FRANKLIN_MUNICIPAL_ADAPTER,
            "case",
            _franklin_municipal_args,
        ),
        "download": _LiveRoute(
            FRANKLIN_MUNICIPAL_ADAPTER,
            "summary-pdf",
            _franklin_municipal_args,
        ),
        "discovery": _LiveRoute(
            FRANKLIN_MUNICIPAL_ADAPTER,
            "source",
            _franklin_municipal_args,
        ),
        "probe": _LiveRoute(
            FRANKLIN_MUNICIPAL_ADAPTER,
            "probe",
            _franklin_municipal_args,
        ),
    },
    DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID: {
        "search": _LiveRoute(
            DELAWARE_OHIO_COMMON_PLEAS_ADAPTER,
            "search",
            _delaware_ohio_common_pleas_args,
        ),
        "case": _LiveRoute(
            DELAWARE_OHIO_COMMON_PLEAS_ADAPTER,
            "case",
            _delaware_ohio_common_pleas_args,
        ),
        "docket": _LiveRoute(
            DELAWARE_OHIO_COMMON_PLEAS_ADAPTER,
            "docket",
            _delaware_ohio_common_pleas_args,
        ),
        "documents": _LiveRoute(
            DELAWARE_OHIO_COMMON_PLEAS_ADAPTER,
            "documents",
            _delaware_ohio_common_pleas_args,
        ),
        "download": _LiveRoute(
            DELAWARE_OHIO_COMMON_PLEAS_ADAPTER,
            "document",
            _delaware_ohio_common_pleas_args,
        ),
        "discovery": _LiveRoute(
            DELAWARE_OHIO_COMMON_PLEAS_ADAPTER,
            "source",
            _delaware_ohio_common_pleas_args,
        ),
        "probe": _LiveRoute(
            DELAWARE_OHIO_COMMON_PLEAS_ADAPTER,
            "probe",
            _delaware_ohio_common_pleas_args,
        ),
    },
    LICKING_COMMON_PLEAS_SOURCE_ID: {
        "discovery": _LiveRoute(
            LICKING_COMMON_PLEAS_ADAPTER,
            "source",
            _licking_common_pleas_args,
        ),
        "probe": _LiveRoute(
            LICKING_COMMON_PLEAS_ADAPTER,
            "probe",
            _licking_common_pleas_args,
        ),
    },
    FRANKLIN_PROBATE_SOURCE_ID: {
        "search": _LiveRoute(
            FRANKLIN_PROBATE_ADAPTER,
            "search",
            _franklin_probate_args,
        ),
        "case": _LiveRoute(
            FRANKLIN_PROBATE_ADAPTER,
            "case",
            _franklin_probate_args,
        ),
        "docket": _LiveRoute(
            FRANKLIN_PROBATE_ADAPTER,
            "docket",
            _franklin_probate_args,
        ),
        "discovery": _LiveRoute(
            FRANKLIN_PROBATE_ADAPTER,
            "source",
            _franklin_probate_args,
        ),
        "probe": _LiveRoute(
            FRANKLIN_PROBATE_ADAPTER,
            "probe",
            _franklin_probate_args,
        ),
    },
    OHIO_REPORTER_DECISIONS_SOURCE_ID: {
        "search": _LiveRoute(
            OHIO_REPORTER_DECISIONS_ADAPTER,
            "search",
            _ohio_reporter_decisions_args,
        ),
        "detail": _LiveRoute(
            OHIO_REPORTER_DECISIONS_ADAPTER,
            "publication",
            _ohio_reporter_decisions_args,
        ),
        "download": _LiveRoute(
            OHIO_REPORTER_DECISIONS_ADAPTER,
            "document",
            _ohio_reporter_decisions_args,
        ),
    },
    OHIO_SUPREME_COURT_SOURCE_ID: {
        "search": _LiveRoute(
            OHIO_SUPREME_COURT_ADAPTER,
            "search",
            _ohio_supreme_court_args,
        ),
        **{
            operation: _LiveRoute(
                OHIO_SUPREME_COURT_ADAPTER,
                "case",
                _ohio_supreme_court_args,
            )
            for operation in ("case", "docket", "documents")
        },
        "download": _LiveRoute(
            OHIO_SUPREME_COURT_ADAPTER,
            "document",
            _ohio_supreme_court_args,
        ),
    },
    SAN_MATEO_MIDX_SOURCE_ID: {
        "search": _LiveRoute(
            query_san_mateo_midx,
            "search",
            _san_mateo_args,
        ),
        "case": _LiveRoute(
            query_san_mateo_midx,
            "case",
            _san_mateo_args,
        ),
    },
    PALM_BEACH_SOURCE_ID: {
        command: _LiveRoute(
            query_palm_beach_courts,
            command,
            _palm_beach_args,
        )
        for command in (
            "search",
            "case",
            "docket",
            "documents",
            "download",
        )
    },
    TEXAS_TAMES_SOURCE_ID: {
        command: _LiveRoute(
            query_texas_appellate,
            command,
            _texas_tames_args,
        )
        for command in (
            "search",
            "case",
            "docket",
            "documents",
            "download",
        )
    },
    TEXAS_SUPREME_PUBLICATIONS_SOURCE_ID: {
        operation: _LiveRoute(
            TEXAS_SUPREME_PUBLICATIONS_ADAPTER,
            (
                "discovery"
                if operation == "discovery"
                else "probe"
                if operation == "probe"
                else "release"
                if operation == "detail"
                else "download"
                if operation == "download"
                else "search"
            ),
            _texas_supreme_publications_args,
        )
        for operation in (
            "search",
            "case",
            "documents",
            "detail",
            "discovery",
            "probe",
            "download",
        )
    },
    VICOURTS_SOURCE_ID: {
        command: _LiveRoute(query_vicourts, command, _vicourts_args)
        for command in (
            "search",
            "case",
            "docket",
            "claims",
            "documents",
            "download",
        )
    },
}

DIRECT_TOOL_GUIDANCE: dict[str, dict[str, Any]] = {
    ACIS_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_florida_acis.py --help",
        "note": (
            "The unified search defaults to party search. The direct adapter "
            "also exposes court metadata, case-title and case-number search, "
            "appellate calendar events with attached case hearings, document "
            "search, and publications."
        ),
    },
    FLORIDA_NINTH_OPINIONS_SOURCE_ID: {
        "mode": "unified_live_official_opinion_archive",
        "direct_tool": (
            "uv run python tools/query_florida_ninth_opinions.py --help"
        ),
        "court_id": query_florida_ninth_opinions.COURT_ID,
        "note": (
            "Unified search covers the Ninth Judicial Circuit's official "
            "archive of circuit-appellate, certiorari, and writ opinions. "
            "Each result retains its direct official PDF URL; the direct "
            "adapter also verifies or saves the exact PDF. Orange County "
            "clerk dockets, Florida ACIS, and statewide appellate opinions "
            "remain separately attributable sources."
        ),
    },
    FLORIDA_COURT_LOCATION_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_official_directory_snapshot",
        "direct_tool": (
            "uv run python "
            "tools/query_florida_court_directory_data.py locations --help"
        ),
        "record_grain": "current_official_court_and_clerk_route",
        "note": (
            "Unified search filters the current statewide courthouse, Supreme "
            "Court, and District Court of Appeal directory. These are routing "
            "snapshots, not cases. The adapter preserves the official feed's "
            "current Gadsden omission and its published map-category/region "
            "mismatches; the direct probe reports those coverage anomalies."
        ),
    },
    FLORIDA_VIRTUAL_COURTROOM_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_official_virtual_directory_snapshot",
        "direct_tool": (
            "uv run python "
            "tools/query_florida_court_directory_data.py virtual --help"
        ),
        "search_fields": [
            "directory",
            "text",
            "county",
            "judge",
            "judicial-officer",
            "live",
        ],
        "note": (
            "Unified search covers current published virtual courtrooms, "
            "county participation, named judges or hearing officers when "
            "present, jurisdiction links, and live state. Entries are current "
            "directory snapshots and the names form only a partial roster."
        ),
    },
    FLORIDA_OSCA_PUBLIC_RECORDS_SOURCE_ID: {
        "mode": "unified_live_official_request_route_snapshot",
        "direct_tool": (
            "uv run python "
            "tools/query_florida_court_directory_data.py data-request --help"
        ),
        "complementary_routes": [
            query_florida_court_directory_data.FCCC_PUBLIC_RECORDS_DIRECTORY_URL,
            query_florida_court_directory_data.ACIS_URL,
        ],
        "note": (
            "Unified search filters the current OSCA request-program record, "
            "including its published contact methods and scope. It covers "
            "OSCA-held records. Florida clerks supply local court-record "
            "routes, while ACIS supplies statewide appellate cases."
        ),
    },
    FLORIDA_TRIAL_COURT_STATISTICS_SOURCE_ID: {
        "mode": "unified_live_official_statistical_catalog",
        "direct_tool": (
            "uv run python "
            "tools/query_florida_court_directory_data.py statistics --help"
        ),
        "exact_download_tool": (
            "uv run python tools/query_florida_court_directory_data.py "
            "download SELECTOR DESTINATION"
        ),
        "search_fields": ["catalog", "text", "fiscal-year", "section"],
        "note": (
            "Unified search lists official aggregate trial-court publications "
            "by keyword, fiscal year, or catalog section. Publication rows are "
            "snapshot-only. Exact PDF selection and byte-verified saving stay "
            "on the dedicated download command so a broad shared selector is "
            "not mistaken for an exact artifact identity."
        ),
    },
    OSCEOLA_BENCHMARK_SOURCE_ID: {
        "mode": "unified_live_county_case_and_docket_system",
        "direct_tool": "uv run python tools/query_osceola_courts.py --help",
        "court_ids": [
            "fl-09-osceola-circuit",
            "fl-09-osceola-county",
        ],
        "search_fields": list(query_osceola_courts.SEARCH_MODE_TO_NATIVE),
        "note": (
            "Unified search retains the source's result scope and broad-query "
            "ceiling. Exact case and docket reads reacquire current session "
            "locators from the stable case number. Documents uses the stable "
            "docket ID and returns page metadata, including the source's "
            "public, hidden, and redaction states; it is not a certified copy. "
            "The direct adapter also describes Clerk request, certified-copy, "
            "registration, and bulk-data handoffs."
        ),
    },
    **{
        source_id: {
            "mode": "unified_live_rolling_report_snapshot",
            "direct_tool": (
                "uv run python tools/query_osceola_courts.py --help"
            ),
            "artifact_url": (
                query_osceola_courts.CALENDAR_URL
                if source_id == OSCEOLA_CALENDAR_SOURCE_ID
                else query_osceola_courts.FORECLOSURE_URL
            ),
            "note": (
                "Discovery and probe preserve this rolling PDF as a separate "
                "current report source. The report snapshot is not projected "
                "as a case or filing; the Benchmark case source remains the "
                "case-history and cancellation-status complement."
            ),
        }
        for source_id in OSCEOLA_REPORT_SOURCE_IDS
    },
    DC_APPELLATE_CASES_SOURCE_ID: {
        "mode": "unified_live_appellate_case_system",
        "direct_tool": ("uv run python tools/query_dc_appellate_cases.py --help"),
        "court_id": query_dc_appellate_cases.COURT_ID,
        "native_page_size": query_dc_appellate_cases.NATIVE_PAGE_SIZE,
        "search_fields": [
            "participant",
            "caption",
            "appellate-case-number",
            "originating-case-number",
        ],
        "complementary_source_ids": [
            route["source_id"]
            for route in query_dc_appellate_cases.related_source_routes()
        ],
        "note": (
            "Unified search covers participants, captions, appellate case "
            "numbers, and originating Superior Court or agency matter "
            "numbers. Case, docket, and documents use exact appellate case "
            "lookup; document mode resolves source-linked filing URLs, and "
            "download accepts one such official URL. The direct adapter also "
            "supports exhaustive traversal, explicit source-internal case "
            "IDs, and a component probe. Trial portals, calendars, opinions, "
            "property, and recorder records remain separately attributable."
        ),
    },
    **{
        source_id: {
            "mode": "unified_live_official_judicial_directory",
            "direct_tool": (
                "uv run python "
                "tools/query_dc_court_directory_data.py --help"
            ),
            "court_id": (
                query_dc_court_directory_data.SUPERIOR_COURT_ID
                if source_id == DC_SUPERIOR_DIRECTORY_SOURCE_ID
                else query_dc_court_directory_data.APPEALS_COURT_ID
            ),
            "search_fields": [
                "directory",
                "person",
                "name",
                "judge",
                "chief",
                "associate",
                "magistrate",
                "senior",
            ],
            "note": (
                "Unified search filters the complete current judge directory "
                "by name and optional judicial role. Results remain source "
                "snapshots rather than cases. The direct adapter also exposes "
                "court leadership and contacts, Superior Court assignment "
                "publications, the data-request program, and the aggregate "
                "reports catalog with each source identity preserved."
            ),
        }
        for source_id in DC_DIRECTORY_SOURCE_IDS
    },
    MICHIGAN_APPELLATE_SOURCE_ID: {
        "mode": "unified_live_appellate_search",
        "direct_tool": ("uv run python tools/query_michigan_appellate.py --help"),
        "native_page_sizes": [10, 25, 50, 100],
        "result_types": ["cases", "opinions", "orders"],
        "search_fields": [
            "party",
            "keyword",
            "case-number",
            "attorney",
            "bar-number",
            "lower-court",
            "author",
            "panel-member",
        ],
        "complementary_routes": [
            record["route_id"]
            for record in query_michigan_appellate.related_source_routes()
            if record["route_id"] != "michigan_appellate_portal"
        ],
        "note": (
            "Unified search selects cases, opinions, or orders with "
            "--case-type and maps the selected --search-field to the "
            "source's advanced filters. Exact case lookup uses the native "
            "case-ID filter. The direct adapter exposes every advanced and "
            "facet selector plus the cross-category preview. MiCOURT, its "
            "developer product, Business Court search, and trial-court "
            "clerks remain separately attributable routes."
        ),
    },
    MICHIGAN_BUSINESS_COURT_SOURCE_ID: {
        "mode": "unified_live_selective_trial_publication_corpus",
        "direct_tool": (
            "uv run python tools/query_michigan_business_court.py --help"
        ),
        "court_id": query_michigan_business_court.COLLECTION_COURT_ID,
        "native_page_size": query_michigan_business_court.NATIVE_PAGE_SIZE,
        "sort_orders": list(query_michigan_business_court.SORT_ORDERS),
        "direct_search_default": "exhaustive_total_pages_traversal",
        "identity_layers": [
            "official_pdf_document",
            "query_page_row_occurrence",
            "source_case_number_candidate",
        ],
        "complementary_source_ids": [
            MICHIGAN_APPELLATE_SOURCE_ID,
            "us-mi-micourt-trial-case-search",
            "us-mi-trial-court-directory",
        ],
        "note": (
            "Unified search traverses the source-reported total pages when no "
            "caller limit is supplied. Discovery lists exact native court "
            "facets, probe checks one oldest page, a true-zero sentinel, and "
            "one official PDF, and download accepts an exact source PDF URL. "
            "The source is a selective Business Court document collection, "
            "not a complete trial-case index. Document, query-row, and "
            "case-number-candidate identities remain separate; selected court "
            "facets and filename codes stay locator observations rather than "
            "court assignments. Older rows with omitted date, case name, or "
            "case number remain usable document occurrences."
        ),
    },
    DC_OPINIONS_SOURCE_ID: {
        "mode": "unified_live_document_corpus",
        "direct_tool": "uv run python tools/query_dc_opinions.py --help",
        "court_id": query_dc_opinions.COURT_ID,
        "native_page_size": query_dc_opinions.ROWS_PER_PAGE,
        "native_type_selectors": ["all", "opinions", "mojs"],
        "direct_list_default": "exhaustive",
        "direct_one_page_option": "--page-only",
        "case_search_complement": query_dc_opinions.CASE_SEARCH_PAGE,
        "superior_court_complement": (query_dc_opinions.SUPERIOR_CASE_SEARCH_PAGE),
        "note": (
            "The current D.C. Court of Appeals index exposes published "
            "opinions and Memorandum Opinion and Judgment entries. Opinion "
            "rows retain court-hosted PDFs when linked; MOJ rows retain their "
            "index metadata and source-published full-text state. Unified "
            "queries return one native page with its continuation cursor; "
            "the direct adapter also supports exhaustive traversal and the "
            "full date/type/order filter set. Appellate and Superior Court "
            "case-search systems remain separate docket complements."
        ),
    },
    DC_TODAY_CALENDAR_SOURCE_ID: {
        "mode": "unified_live_calendar",
        "direct_tool": ("uv run python tools/query_dc_superior_calendar.py --help"),
        "court_id": query_dc_superior_calendar.COURT_ID,
        "native_page_size": 10,
        "direct_default": "exhaustive",
        "representations": ["html_search", "rest_full_current_array"],
        "case_system_complements": [
            query_dc_superior_calendar.PORTAL_URL,
            query_dc_superior_calendar.EACCESS_URL,
        ],
        "note": (
            "Unified search uses party text by default; case and calendar use "
            "case number, and --search-field can select another native field. "
            "Each unified call returns one native page with its resumable "
            "cursor. The direct adapter also exposes exhaustive traversal, "
            "the complete current-day REST snapshot, filter discovery, and "
            "the related calendar families. Calendar rows are hearing "
            "occurrences rather than complete case histories."
        ),
    },
    DC_CRIMINAL_CALENDAR_SOURCE_ID: {
        "mode": "unified_live_calendar",
        "direct_tool": ("uv run python tools/query_dc_superior_calendar.py --help"),
        "court_id": query_dc_superior_calendar.COURT_ID,
        "native_page_size": 10,
        "direct_default": "exhaustive",
        "full_schedule_artifacts": [
            query_dc_superior_calendar.CRIMINAL_ATTORNEY_PDF_URL,
            query_dc_superior_calendar.CRIMINAL_COURT_PDF_URL,
        ],
        "note": (
            "Unified search uses defendant text by default; case and calendar "
            "use case number, and --search-field can select event, charge, "
            "time, attorney, judge, or courtroom. The direct adapter also "
            "lists the two official full-schedule PDFs and discovers native "
            "filter values. Hearing rows and calendar PDFs retain distinct "
            "record identities."
        ),
    },
    DC_TAX_CALENDAR_SOURCE_ID: {
        "mode": "unified_live_calendar_artifacts",
        "direct_tool": (
            "uv run python tools/query_dc_superior_calendar.py artifacts --family tax"
        ),
        "case_system_complements": [
            query_dc_superior_calendar.PORTAL_URL,
            query_dc_superior_calendar.EACCESS_URL,
        ],
        "note": (
            "Unified calendar lists the official Tax Division show-cause and "
            "mediation calendar artifacts. These are calendar documents, not "
            "case-file documents; Portal and eAccess provide the complementary "
            "case-history routes."
        ),
    },
    DC_APPEALS_CALENDAR_SOURCE_ID: {
        "mode": "unified_live_calendar_artifacts",
        "direct_tool": ("uv run python tools/query_dc_superior_calendar.py appeals"),
        "year_filter": "four_digit_calendar_year",
        "opinion_complement": DC_OPINIONS_SOURCE_ID,
        "note": (
            "Unified calendar accepts a four-digit year or all and lists "
            "regular, summary, and current weekly-panel artifacts. The "
            "separate D.C. opinions adapter remains the disposition and "
            "published-opinion complement."
        ),
    },
    CALIFORNIA_COURT_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_official_court_directory",
        "direct_tool": (
            "uv run python tools/query_california_court_directory.py --help"
        ),
        "record_grain": "current_county_court_and_service_route",
        "county_count": len(query_california_court_directory.COUNTY_FIPS),
        "note": (
            "Unified search filters the complete current 58-county directory "
            "by county, GEOID, court, appellate district, or published route. "
            "Results are discovery snapshots rather than cases. The direct "
            "adapter also emits capability-assessment candidates."
        ),
    },
    CALIFORNIA_OPINIONS_SOURCE_ID: {
        "mode": "unified_live_official_current_appellate_opinions",
        "direct_tool": (
            "uv run python tools/query_california_opinions.py --help"
        ),
        "record_grain": "current_appellate_opinion_publication",
        "current_windows_days": {
            collection: int(config["window_days"])
            for collection, config in query_california_opinions.COLLECTIONS.items()
        },
        "collection_selector": "--case-type published|unpublished|both",
        "note": (
            "Unified search covers the current published/citable and "
            "unpublished/non-citable opinion feeds. Case and documents use "
            "the exact native case-number filter and retain opinion-version "
            "and direct PDF metadata; exact URL download never derives a "
            "document path from a case number. Discovery exposes the feed "
            "manifest or the separate Appellate Case Information and "
            "corrected Official Reports routes. These rolling feeds are "
            "opinion publications rather than complete case dockets or "
            "historical coverage."
        ),
    },
    GEORGIA_COURT_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_official_court_personnel_directory",
        "direct_tool": (
            "uv run python tools/query_georgia_court_directory.py --help"
        ),
        "record_grain": "current_court_personnel_directory_entry",
        "native_page_size": query_georgia_court_directory.DEFAULT_PAGE_SIZE,
        "search_fields": list(
            query_georgia_court_directory.SEARCH_FIELD_DEFINITIONS
        ),
        "note": (
            "Unified search uses the published personnel view and preserves "
            "its native filter-bound continuation cursor. Discovery returns "
            "the verified source manifest and complementary official routes; "
            "probe runs one filtered search plus one exact detail read; detail "
            "uses the exact native Knack record ID. Compact search rows do not "
            "claim detail-only Court Class or Directory Section values. Every "
            "directory result remains a current snapshot observation rather "
            "than a case, party, docket, or historical roster."
        ),
    },
    GEORGIA_EACCESS_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_official_case_access_provider_directory",
        "direct_tool": (
            "uv run python tools/query_georgia_court_access.py --help"
        ),
        "record_grain": "current_case_access_acquisition_handoff",
        "provider_ids": ["peachcourt", "researchga"],
        "note": (
            "Unified search filters the current AOC court-to-provider routes "
            "by text, county, court class, provider, or published state. "
            "Discovery summarizes the providers and their listed court "
            "counts; probe checks both official directory artifacts. The "
            "destinations require provider accounts for case searches. Rows "
            "remain acquisition handoffs with zero case or filing projection."
        ),
    },
    GEORGIA_EFILE_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_official_efile_provider_directory",
        "direct_tool": (
            "uv run python tools/query_georgia_court_access.py --help"
        ),
        "record_grain": "current_efile_provider_availability_entry",
        "provider_ids": [
            "odyssey_efilega",
            "peachcourt",
            "greenfiling_infotrack",
        ],
        "published_states": ["mandatory", "available", "not_listed"],
        "note": (
            "Unified search filters the current court-to-filing-provider "
            "matrix by text, county, court class, provider, or published "
            "state. Discovery summarizes provider coverage and probe checks "
            "the official table. Blank cells are retained as not_listed. "
            "Rows are availability snapshots and do not initiate or evidence "
            "a filing."
        ),
    },
    GEORGIA_CASELOAD_DASHBOARD_SOURCE_ID: {
        "mode": "unified_live_official_aggregate_caseload_dashboards",
        "direct_tool": (
            "uv run python tools/query_georgia_court_data.py --help"
        ),
        "record_grain": "aggregate_self_reported_case_counts",
        "court_classes": list(query_georgia_court_data.COURT_CLASSES),
        "note": (
            "Unified search lists or filters the six official court-class "
            "dashboard routes with a source-snapshot-bound cursor. Discovery "
            "returns the verified export-request handoff without submitting "
            "it, and probe checks the current dashboard catalog. AOC describes "
            "the underlying values as self-reported aggregate counts and says "
            "the Research Office does not collect individual-case data. Rows "
            "never project as cases, parties, dockets, or court documents."
        ),
    },
    GEORGIA_WORKLOAD_ASSESSMENT_SOURCE_ID: {
        "mode": "unified_live_official_aggregate_workload_publications",
        "direct_tool": (
            "uv run python tools/query_georgia_court_data.py --help"
        ),
        "record_grain": "annual_aggregate_circuit_workload_publication",
        "baseline_years": sorted(
            query_georgia_court_data.BASELINE_WORKLOAD_YEARS
        ),
        "note": (
            "Unified search and documents list annual Superior Court workload "
            "publication metadata, optionally for one exact year, while "
            "preserving the source-snapshot-bound cursor. Detail fetches and "
            "validates one exact annual PDF without treating it as a filing. "
            "Probe checks the catalog and latest PDF. Publication and artifact "
            "rows remain aggregate observations with zero case-level "
            "projection."
        ),
    },
    GEORGIA_SUPREME_DOCKET_SOURCE_ID: {
        "mode": "unified_live_official_recent_appellate_docket",
        "direct_tool": (
            "uv run python tools/query_georgia_supreme_docket.py --help"
        ),
        "record_grain": "recent_supreme_court_case_and_docket_metadata",
        "court_id": query_georgia_supreme_docket.COURT_ID,
        "coverage": "cases docketed in the last 5 years",
        "search_fields": list(query_georgia_supreme_docket.SEARCH_FIELDS),
        "note": (
            "Unified search covers case number, caption, party, attorney, "
            "lower-court case number plus county, and Court of Appeals case "
            "number. Case and docket both retrieve one exact appellate case "
            "with filing/order, judgment, calendar, lower-court, and attorney "
            "metadata. Documents returns the metadata-only Clerk copy-request "
            "handoff and does not create document artifacts. Discovery lists "
            "native county selectors by default and can return the verified "
            "source manifest."
        ),
    },
    **{
        source_id: {
            "mode": "unified_live_official_supreme_court_publication",
            "direct_tool": (
                "uv run python "
                "tools/query_georgia_supreme_publications.py --help"
            ),
            "record_grain": "official_decision_publication_occurrence",
            "court_id": query_georgia_supreme_publications.COURT_ID,
            "publication_components": list(
                query_georgia_supreme_publications.SOURCE_METADATA[
                    source_id
                ].metadata["publication_components"]
            ),
            "note": (
                "Unified search, case, and documents retain the selected "
                "component's annual publication occurrence and exact linked "
                "documents. Discovery returns its manifest, probe checks the "
                "bounded current annual page, and download requires an exact "
                "official PDF URL. These publications complement rather than "
                "replace the separate recent public docket."
            ),
        }
        for source_id in GEORGIA_SUPREME_PUBLICATION_SOURCE_IDS
    },
    SANTA_CLARA_FAMILY_SOURCE_ID: {
        "mode": "source_family_inventory",
        "direct_tool": (
            "uv run python tools/query_santa_clara_court_records.py sources"
        ),
        "component_source_ids": list(SANTA_CLARA_SOURCE_IDS[1:]),
        "note": (
            "The family inventory keeps current tentative-ruling documents, "
            "requested civil and criminal index products, and the interactive "
            "case portal separately attributable."
        ),
    },
    SANTA_CLARA_TENTATIVE_SOURCE_ID: {
        "mode": "unified_live_current_publication",
        "direct_tool": (
            "uv run python tools/query_santa_clara_court_records.py --help"
        ),
        "court_id": query_santa_clara_court_records.COURT_ID,
        "publication_state": "current_until_replaced",
        "note": (
            "Unified search or calendar lists departments or current ruling "
            "PDFs for one department; documents uses a department selector, "
            "and download verifies one official PDF. These source snapshots "
            "do not represent a historical ruling archive or final case "
            "dispositions."
        ),
    },
    SANTA_CLARA_CIVIL_PRODUCT_SOURCE_ID: {
        "mode": "cataloged_requested_data_product",
        "direct_tool": (
            "uv run python tools/query_santa_clara_court_records.py "
            "products --kind civil"
        ),
        "note": (
            "The court describes a quarterly tab-delimited civil index "
            "product acquired by request. Its fields, form, terms, delivery, "
            "and cost basis remain distinct from the public portal."
        ),
    },
    SANTA_CLARA_CRIMINAL_PRODUCT_SOURCE_ID: {
        "mode": "cataloged_requested_data_product",
        "direct_tool": (
            "uv run python tools/query_santa_clara_court_records.py "
            "products --kind criminal"
        ),
        "note": (
            "The court describes a requested tab-delimited criminal index "
            "product containing case number, filing date, and party name."
        ),
    },
    SANTA_CLARA_PORTAL_SOURCE_ID: {
        "mode": "interactive_public_portal",
        "direct_tool": (
            "uv run python tools/query_santa_clara_court_records.py sources"
        ),
        "note": (
            "The portal's case, party, business, filing-date, and calendar "
            "forms presented reCAPTCHA when observed. Open ruling publications "
            "and requested index products remain separate components."
        ),
    },
    SAN_DIEGO_COURT_INDEX_SOURCE_ID: {
        "mode": "unified_live_headed_browser_index",
        "direct_tool": (
            "uv run python tools/query_san_diego_court_index.py --help"
        ),
        "court_id": query_san_diego_court_index.COURT_ID,
        "coverage_start_year": 1974,
        "note": (
            "Unified search performs source-native party or business lookup "
            "for one case type; case performs exact case-number lookup. The "
            "direct adapter also exposes case-detail pages and the separate "
            "five-court-day static new-filing lists. Index rows are not "
            "dockets or official case-file documents."
        ),
    },
    FRESNO_FAMILY_SOURCE_ID: {
        "mode": "source_family_inventory",
        "direct_tool": ("uv run python tools/query_fresno_superior_court.py sources"),
        "component_source_ids": list(FRESNO_SOURCE_IDS[1:]),
        "note": (
            "The family inventory keeps e-Court, daily calendars, tentative "
            "rulings, Probate Examiner Notes, ordered case indexes, and "
            "record-request routes separately attributable. Use the component "
            "source ID whose record grain matches the question."
        ),
    },
    FRESNO_PORTAL_SOURCE_ID: {
        "mode": "current_portal_observation",
        "direct_tool": ("uv run python tools/query_fresno_superior_court.py portal"),
        "note": (
            "The direct observation reports the current Journal Technologies "
            "e-Court landing, registration fields, and whether an anonymous "
            "case-search control is actually present. Other Fresno components "
            "provide immediately useful anonymous calendar, ruling, and "
            "probate-note information."
        ),
    },
    FRESNO_CALENDAR_SOURCE_ID: {
        "mode": "unified_live_calendar",
        "direct_tool": ("uv run python tools/query_fresno_superior_court.py calendar"),
        "court_id": query_fresno_superior_court.COURT_ID,
        "direct_default": "all_rows_in_selected_pdf",
        "note": (
            "Unified calendar accepts an ISO publication date or latest and "
            "parses every hearing in the selected official PDF. Trial and "
            "Master Calendar layouts retain case, department, judge, time, "
            "status, attorney, page, and source-artifact lineage."
        ),
    },
    FRESNO_RULINGS_SOURCE_ID: {
        "mode": "unified_live_tentative_rulings",
        "direct_tool": ("uv run python tools/query_fresno_superior_court.py rulings"),
        "court_id": query_fresno_superior_court.COURT_ID,
        "observed_departments": [403, 501, 502, 503],
        "note": (
            "Unified calendar uses a department number as its selector and an "
            "optional exact date. It preserves full tentative-ruling text, "
            "continuances, must-appear entries, motion and explanation fields, "
            "and the shared court PDF lineage without presenting a tentative "
            "entry as a final case disposition."
        ),
    },
    FRESNO_PROBATE_SOURCE_ID: {
        "mode": "unified_live_probate_notes",
        "direct_tool": (
            "uv run python tools/query_fresno_superior_court.py probate-notes"
        ),
        "court_id": query_fresno_superior_court.COURT_ID,
        "note": (
            "Unified notes accepts the exact probate case number and optional "
            "ISO hearing date, returning every matching examiner-note row. "
            "The source's statement that examiner notes are not part of the "
            "official court file remains attached to each occurrence."
        ),
    },
    FRESNO_INDEX_SOURCE_ID: {
        "mode": "cataloged_data_product",
        "direct_tool": (
            "uv run python tools/query_fresno_superior_court.py alternatives"
        ),
        "note": (
            "The court offers monthly PDF or text case-index reports by order "
            "and email delivery. The catalog preserves the published fields, "
            "price, order form, and delivery route as a separate data product."
        ),
    },
    FRESNO_RECORDS_SOURCE_ID: {
        "mode": "cataloged_official_alternatives",
        "direct_tool": (
            "uv run python tools/query_fresno_superior_court.py alternatives"
        ),
        "note": (
            "Archives and certified-copy routes, civil and criminal case "
            "information contacts, elevated-access materials, administrative "
            "record requests, and the Fifth District appellate complement are "
            "modeled separately so a difficult interactive portal does not "
            "hide other useful official paths."
        ),
    },
    ORANGE_CALENDAR_SOURCE_ID: {
        "mode": "unified_live_calendar",
        "direct_tool": ("uv run python tools/query_orange_county_court.py calendar"),
        "court_id": query_orange_county_court.COURT_ID,
        "native_page_size": query_orange_county_court.TRANSPORT_PAGE_SIZE,
        "direct_default": "exhaustive_all_native_pages",
        "note": (
            "The native calendar requires one of six case categories. Unified "
            "search uses title text, case uses case ID, and calendar uses case "
            "ID unless --search-field selects title, location, department, or "
            "hearing time. Omitted limits traverse every native page in the "
            "source-selected date window; each row remains a hearing "
            "occurrence rather than a complete register of actions."
        ),
    },
    **{
        source_id: {
            "mode": "unified_live_tentative_rulings",
            "direct_tool": (
                "uv run python tools/query_orange_county_court.py "
                f"ruling-index --division {division}"
            ),
            "court_id": query_orange_county_court.COURT_ID,
            "direct_default": "all_current_directory_artifacts",
            "note": (
                "Unified search and calendar list every current directory "
                "artifact, optionally filtered by department. Documents "
                "fetches the currently linked department PDF and extracts its "
                "full text and case-number candidates. The publication is "
                "tentative and rolling; case portals, the permanent index, "
                "name search, index products, probate notes, and clerk-copy "
                "routes remain distinct complements."
            ),
        }
        for source_id, division in ORANGE_RULING_DIVISIONS_BY_SOURCE.items()
    },
    RIVERSIDE_CALENDAR_SOURCE_ID: {
        "mode": "unified_live_calendar",
        "direct_tool": ("uv run python tools/query_riverside_court.py calendar --help"),
        "court_id": query_riverside_court.COURT_ID,
        "direct_default": "complete_source_published_four_business_day_window",
        "note": (
            "Unified calendar selects the court's courthouse, department, "
            "area-of-law, and date fields. Omitted limits retain every row "
            "in the selected current/future source window; the visible "
            "12-row grid is client presentation rather than transport "
            "pagination. Public Access and clerk/index products supply "
            "broader case discovery and registers."
        ),
    },
    RIVERSIDE_RULING_SOURCE_ID: {
        "mode": "unified_live_tentative_rulings",
        "direct_tool": (
            "uv run python tools/query_riverside_court.py ruling-index --help"
        ),
        "court_id": query_riverside_court.COURT_ID,
        "direct_default": "all_current_directory_links",
        "note": (
            "Unified search and calendar list every PDF linked by the current "
            "department directory; documents fetches one department PDF and "
            "extracts its full text and case-number candidates. Directory "
            "membership and artifact or hearing dates remain separate because "
            "the current page intentionally contains mixed-age files."
        ),
    },
    QLD_ECOURTS_SOURCE_ID: {
        "mode": "unified_live_civil_case_index",
        "direct_tool": "uv run python tools/query_qld_ecourts.py --help",
        "court_ids": sorted(query_qld_ecourts.COURT_IDS.values()),
        "native_page_size": query_qld_ecourts.NATIVE_PAGE_SIZE,
        "native_result_ceiling": query_qld_ecourts.NATIVE_RESULT_CEILING,
        "direct_default": "exhaustive_with_adaptive_native_partitions",
        "identity_model": ("court_code + originating_registry_code + file_number"),
        "complementary_source_ids": [
            value["source_id"]
            for value in query_qld_ecourts.COMPLEMENTARY_OFFICIAL_ROUTES
        ],
        "note": (
            "Unified search uses the party/company field by default and can "
            "select the second party or file number. Case, docket, and "
            "documents resolve an exact file number and return the full "
            "published detail. Omitted limits traverse all native pages and "
            "adaptively split a 500-result partition by court, originating "
            "registry, category, and party role. Document rows are metadata; "
            "the official copy-request route supplies filing copies, while "
            "criminal lookup, law lists, case law, judgments, and archives "
            "cover adjacent record roles."
        ),
    },
    WISCONSIN_COURT_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_official_court_directory",
        "direct_tool": (
            "uv run python tools/query_wisconsin_court_directory.py --help"
        ),
        "search_fields": [
            "directory",
            "court",
            "clerk",
            "judge",
            "district",
            "appellate",
            "supreme",
            "state-office",
        ],
        "parsed_components": list(query_wisconsin_court_directory.COMPONENTS),
        "note": (
            "Unified search filters complete current snapshots of the official "
            "circuit-court, clerk, judge, administrative-district, appellate, "
            "and state-office directories. Wisconsin or county-GEOID context "
            "can narrow results. Directory entries remain snapshot-only rather "
            "than being projected as cases. The direct adapter also exposes "
            "county aggregation, exact component coverage, county-site "
            "discovery candidates, the municipal-court PDF, juror contacts, "
            "and related case and opinion sources as distinct routes."
        ),
    },
    WISCONSIN_WSCCA_SOURCE_ID: {
        "mode": "unified_live_appellate_case_access",
        "direct_tool": ("uv run python tools/query_wisconsin_wscca.py --help"),
        "court_ids": [
            query_wisconsin_wscca.SUPREME_COURT_ID,
            query_wisconsin_wscca.COURT_OF_APPEALS_ID,
            query_wisconsin_wscca.APPELLATE_COURTS_ID,
        ],
        "component_access": {
            "case_search_and_detail": (
                "browser session with public-use acknowledgment and source validation"
            ),
            "case_rss": "direct HTTP",
        },
        "complementary_source_ids": [
            route["source_id"]
            for route in query_wisconsin_wscca.source_routes()
            if route["source_id"] != WISCONSIN_WSCCA_SOURCE_ID
        ],
        "note": (
            "Unified search supports party, business, and appellate case-number "
            "selectors; exact case, docket, document metadata, and source-listed "
            "PDF download use the browser-backed public session. The direct "
            "adapter also exposes per-case RSS, runtime checks, probes, and the "
            "full complement map. Linked circuit cases retain WCCA identity, "
            "while official opinions, library briefs, historical briefs, and "
            "clerk requests remain separately attributable."
        ),
    },
    WISCONSIN_OPINIONS_SOURCE_ID: {
        "mode": "unified_live_appellate_publication_corpus",
        "direct_tool": ("uv run python tools/query_wisconsin_opinions.py --help"),
        "collections": sorted(query_wisconsin_opinions.COLLECTIONS),
        "full_text_collections": sorted(query_wisconsin_opinions.FULLTEXT_COLLECTIONS),
        "native_metadata_paging": "one_based_page",
        "native_full_text_page_size": (query_wisconsin_opinions.FULLTEXT_PAGE_SIZE),
        "complementary_source_ids": [
            route["source_id"]
            for route in query_wisconsin_opinions.source_routes()
            if route["source_id"] != WISCONSIN_OPINIONS_SOURCE_ID
        ],
        "note": (
            "Unified search defaults to the Court of Appeals opinion index. "
            "--search-field selects Supreme opinions, Supreme orders, appellate "
            "summary dispositions, or keyword full text; --court-id selects the "
            "court for keyword search. Case and documents use the same exact "
            "case-number metadata index, and download accepts an official "
            "Wisconsin appellate PDF URL. The direct adapter additionally "
            "exposes release feeds, live filter taxonomy, exhaustive traversal, "
            "and all-component probes. A shared PDF identifier may belong to "
            "multiple consolidated case records, so case and artifact identities "
            "remain distinct."
        ),
    },
    MARYLAND_PUBLIC_CASES_SOURCE_ID: {
        "mode": "unified_live_recent_case_discovery",
        "direct_tool": ("uv run python tools/query_md_public_cases.py --help"),
        "coverage": "rolling source-published five-day cases-filed reports",
        "search_fields": [
            "query",
            "case-number",
            "name",
            "address",
            "court",
            "case-type",
            "charge",
        ],
        "note": (
            "Unified search scans every report currently in Maryland's "
            "rolling MDEC public-cases directory by party name by default. "
            "Case performs an exact recent-case-number lookup. The records "
            "include court, filing date, caption/type, source-published party "
            "names and addresses, and charges when present; they are recent "
            "filing reports rather than historical dockets. The direct "
            "adapter also lists, downloads, and locally parses individual "
            "reports and maps Case Search, judgments/liens, estates, "
            "appellate opinions, records requests, SDAT, land records, and "
            "plats as separate complements."
        ),
    },
    MARYLAND_ESTATE_SOURCE_ID: {
        "mode": "unified_live_estate_case_and_docket_index",
        "direct_tool": ("uv run python tools/query_md_estate_search.py --help"),
        "coverage": (
            "all 23 Maryland counties and Baltimore City; statewide "
            "coverage is generally 1998-present and older depth varies by "
            "jurisdiction"
        ),
        "native_page_size": query_md_estate_search.NATIVE_PAGE_SIZE,
        "search_fields": [
            "decedent",
            "representative",
            "estate-number",
        ],
        "complementary_source_ids": [
            route["source_id"]
            for route in query_md_estate_search.RELATED_ROUTES
            if route["source_id"] != MARYLAND_ESTATE_SOURCE_ID
        ],
        "note": (
            "Unified search defaults to decedent name and can select a "
            "personal representative or estate number. Case and docket "
            "resolve an estate number through its county-scoped index row, "
            "then fetch the exact RowNet detail with aliases, representatives, "
            "attorneys, dates, status, will/probate fields, and every published "
            "docket event. If an estate number appears in more than one "
            "jurisdiction, the result returns the candidates so --county or "
            "--court-id can select the intended file. Register of Wills "
            "offices, legal notices, claim search, Case Search, recent MDEC "
            "reports, judgments/liens, MDLandRec, SDAT, and circuit clerks "
            "remain separately attributable adjacent routes."
        ),
    },
    MARYLAND_ESTATE_NOTICE_SOURCE_ID: {
        "mode": "unified_live_estate_notice_occurrences",
        "direct_tool": (
            "uv run python tools/query_md_estate_notices_claims.py "
            "notices --help"
        ),
        "coverage": (
            "all Maryland counties and Baltimore City; the source default "
            "is a rolling publication-date window and explicit dates can "
            "select other published notice occurrences"
        ),
        "native_page_size": query_md_estate_notices_claims.NATIVE_PAGE_SIZE,
        "search_fields": ["decedent", "representative"],
        "complementary_source_ids": [
            MARYLAND_ESTATE_SOURCE_ID,
            MARYLAND_ESTATE_CLAIM_SOURCE_ID,
        ],
        "note": (
            "Unified search returns each source-published legal-notice "
            "occurrence with its numeric notice ID, exact title and variant, "
            "complete HTML and text, named estate participants, county, and "
            "published dates. --after/--before map to the source's publication "
            "window; --search-field representative selects the personal-"
            "representative role. The estate index and claims application "
            "remain separately attributable complements."
        ),
    },
    MARYLAND_ESTATE_CLAIM_SOURCE_ID: {
        "mode": "unified_live_estate_claim_occurrences",
        "direct_tool": (
            "uv run python tools/query_md_estate_notices_claims.py "
            "claims --help"
        ),
        "coverage": "all Maryland counties and Baltimore City",
        "native_page_size": query_md_estate_notices_claims.NATIVE_PAGE_SIZE,
        "search_fields": [
            "decedent",
            "claimant",
            "corporation",
            "estate-number",
            "claim-type",
            "claim-status",
        ],
        "complementary_source_ids": [
            MARYLAND_ESTATE_SOURCE_ID,
            MARYLAND_ESTATE_NOTICE_SOURCE_ID,
        ],
        "note": (
            "Unified search returns filed-claim occurrences and enriches each "
            "from its exact detail locator. The claims operation treats its "
            "selector as an estate number, while detail accepts a native "
            "RecordId or source-partition:RecordId pair. Person and "
            "corporation selectors, exact filed date, "
            "county, source-reported type and status remain claim fields; "
            "they do not replace the occurrence identity or establish "
            "adjudication."
        ),
    },
    MARYLAND_JUDGMENT_LIENS_SOURCE_ID: {
        "mode": "unified_live_judgment_lien_index",
        "direct_tool": ("uv run python tools/query_md_judgment_liens.py --help"),
        "coverage": "all Maryland circuit courts; District Court excluded",
        "native_page_size": query_md_judgment_liens.NATIVE_PAGE_SIZE,
        "source_result_ceiling": (query_md_judgment_liens.SOURCE_RESULT_CEILING),
        "note": (
            "Unified search selects the source's person or company mode from "
            "--entity-kind or --search-field and preserves county and filing-"
            "date filters. Case, docket, and claims retrieve the exact case's "
            "original judgment and modification events. The index preserves "
            "creditor/debtor aliases, amounts, book/page, entry and status "
            "dates, and case links. Case Search, the recent MDEC feed, circuit "
            "clerks, MDLandRec, SDAT, local finance offices, estates, and AOC "
            "requests remain separate routes for the underlying or adjacent "
            "records."
        ),
    },
    MARYLAND_OPINIONS_SOURCE_ID: {
        "mode": "unified_live_appellate_publication_corpus",
        "direct_tool": "uv run python tools/query_md_opinions.py --help",
        "collections": ["reported", "unreported"],
        "court_ids": [spec["court_id"] for spec in query_md_opinions.COURTS.values()],
        "coverage": {
            "reported": "1995-present filing-year indexes",
            "unreported_metadata": "2001-02-present monthly indexes",
            "unreported_linked_full_text": "2015-05-present",
        },
        "complementary_source_ids": [
            route["source_id"]
            for route in query_md_opinions._source_manifest()["related_source_routes"]
        ],
        "note": (
            "Unified search defaults to the complete reported-opinion archive; "
            "--search-field unreported selects the monthly unreported archive "
            "and --after/--before bound its months and rows. Case and documents "
            "use an exact published case number without presenting the "
            "publication index as a complete docket. Download accepts one "
            "source-listed official PDF URL. The direct adapter additionally "
            "selects reported filing year and source order, discovers every "
            "published year/month route, traverses unreported months, and "
            "probes both index schemas plus a PDF. Case Search, recent MDEC "
            "reports, judgments/liens, and estates remain separately "
            "attributable case-detail complements."
        ),
    },
    MARYLAND_BUSINESS_OPINIONS_SOURCE_ID: {
        "mode": "unified_live_selective_trial_publication_corpus",
        "direct_tool": ("uv run python tools/query_md_business_opinions.py --help"),
        "collections": ["current_2009_present", "annual_archives_2003_2008"],
        "coverage": "selective program publications from 2003-present",
        "document_types": ["opinion", "order", "synopsis"],
        "document_formats": ["pdf", "doc", "wpd"],
        "complementary_source_ids": [
            route["source_id"]
            for route in query_md_business_opinions._source_manifest()[
                "related_source_routes"
            ]
        ],
        "note": (
            "Unified search traverses the complete current table and all six "
            "closed annual archives, with text, exact case-number, county, "
            "judge, document-role, and source filing-date filters. Case and "
            "documents use exact source case numbers; download retains the "
            "exact source-listed attachment URL. The source is a selective "
            "Business and Technology Case Management Program publication "
            "archive rather than a complete docket. Missing case numbers and "
            "dates, month-precision dates, multiple case-number lines, shared "
            "URLs, doubled path segments, and filename/designation mismatches "
            "remain explicit source states. Case Search, rolling MDEC reports, "
            "judgments/liens, appellate opinions, and Circuit Court clerk-copy "
            "routes remain separately attributable complements."
        ),
    },
    NEW_JERSEY_TAX_COURT_SOURCE_ID: {
        "mode": "unified_live_replaceable_property_case_reports",
        "direct_tool": ("uv run python tools/query_new_jersey_tax_court.py --help"),
        "datasets": sorted(query_new_jersey_tax_court.DATASET_SPECS),
        "search_fields": ["any", "case-title", "docket", "parcel", "county"],
        "case_identity_field": "docket_number",
        "source_occurrence_identity_fields": [
            "artifact_sha256",
            "worksheet_member",
            "row_number",
            "row_sha256",
        ],
        "complementary_source_ids": [
            route["source_id"]
            for route in query_new_jersey_tax_court._alternative_routes()
        ],
        "note": (
            "Unified search traverses the current docketed and open local-property "
            "Tax Court XLSX reports, with caption, docket, parcel-component, "
            "county, and entered-date selectors. Case uses an exact normalized "
            "docket number. The reports are replaceable current snapshots rather "
            "than a historical judgment archive; repeated rows and multiple "
            "property rows for one docket retain distinct artifact/sheet/row/hash "
            "occurrence identities. The current reports do not publish "
            "municipality, so county plus block and lot is not treated as a "
            "deterministic parcel join. The direct adapter also exposes the "
            "anonymous object manifest, artifact validation, and separately "
            "attributable archive, case-jacket, opinion, assessment, sale, and "
            "local-office routes."
        ),
    },
    NEW_JERSEY_TAX_COURT_OPINIONS_SOURCE_ID: {
        "mode": "unified_live_official_opinion_indexes_and_documents",
        "direct_tool": (
            "uv run python tools/query_new_jersey_tax_court_opinions.py --help"
        ),
        "collections": ["published", "unpublished"],
        "search_fields": ["query", "docket", "published", "unpublished"],
        "identity_layers": [
            "index_occurrence",
            "official_document_path",
            "normalized_docket_number",
        ],
        "complementary_source_ids": [
            route["source_id"]
            for route in query_new_jersey_tax_court_opinions._alternative_routes()
        ],
        "note": (
            "Unified search traverses both official rolling indexes unless a "
            "published or unpublished selector is supplied. Case and documents "
            "use exact normalized docket matching; download accepts an exact "
            "official New Jersey Courts opinion URL. Each source-visible index "
            "occurrence remains distinct, while shared official document paths "
            "and every docket named by a consolidated opinion retain their own "
            "identity. Reader-rendered index pages and extracted text are "
            "labeled retrieval representations of the New Jersey Judiciary "
            "publication, not additional publishers."
        ),
    },
    WASHINGTON_APPELLATE_OPINIONS_SOURCE_ID: {
        "mode": "unified_live_official_appellate_opinions",
        "direct_tool": "uv run python tools/query_washington_courts.py --help",
        "source_component_id": WASHINGTON_APPELLATE_OPINIONS_SOURCE_ID,
        "search_fields": ["query", "caption", "title", "name", "party"],
        "identity_layers": [
            "opinion_index_or_feed_occurrence",
            "appellate_docket_number",
            "official_information_page",
            "official_pdf_path_and_hash",
        ],
        "note": (
            "Unified search filters the complete combined opinion list by "
            "source-visible text. Case and documents fetch the exact official "
            "opinion information sheet by docket number or advertised opinion "
            "filename; download follows its first source-listed PDF. The "
            "projection retains distinct list/feed occurrences, every docket "
            "stated by a consolidated record, the information page, and each "
            "PDF identity. The direct adapter also exposes court/status-specific "
            "RSS feeds and by-year lists."
        ),
    },
    WASHINGTON_COURT_DIRECTORY_SOURCE_ID: {
        "mode": "unified_live_official_court_personnel_directory",
        "direct_tool": "uv run python tools/query_washington_courts.py --help",
        "source_component_id": WASHINGTON_COURT_DIRECTORY_SOURCE_ID,
        "search_fields": ["directory", "person", "name", "judge", "staff"],
        "note": (
            "Unified search maps a last name and optional first initial to the "
            "official AOC personnel directory. Directory rows remain source "
            "snapshots rather than being projected as cases. The direct adapter "
            "also exposes county and organization pages and the statewide "
            "directory PDF."
        ),
    },
    VA_GENERAL_DISTRICT_SOURCE_ID: {
        "mode": "unified_live_court_component_case_information",
        "direct_tool": "uv run python tools/query_va_general_district.py --help",
        "search_fields": [
            "name",
            "case-number",
            "hearing-date",
            "service-process",
        ],
        "case_identity_fields": [
            "source_id",
            "court_id",
            "raw_case_number",
        ],
        "note": (
            "Select one source-published court component with --court-id "
            "va-gdc-NNN or --courthouse. Its three-digit code is an "
            "application component identifier, not a geographic FIPS code. "
            "Unified search exposes the distinct name, exact-case, hearing, "
            "and service/process roles through --search-field; calendar maps "
            "only the exact hearing-date operation. Native pages are exhausted "
            "until Next disappears unless a caller limit returns the source's "
            "session-replay cursor. Case detail preserves section publication "
            "states and masked values. The source publishes case metadata, not "
            "a filing index or filing images."
        ),
    },
    DOJ_COURT_RECORDS_SOURCE_ID: {
        "mode": "unified_live_official_release_corpus",
        "direct_tool": (
            "uv run python tools/query_doj_court_records.py --help"
        ),
        "record_grain": [
            "doj_release_case_group",
            "doj_released_court_document",
        ],
        "identity_layers": [
            "canonical_doj_case_page",
            "efta_identifier_when_published",
            "official_document_url",
        ],
        "complementary_routes": {
            "pacer_cm_ecf": "official federal docket and documents",
            "courtlistener_recap": "contributed federal docket archive",
            "named_court_clerk": "official court copy route",
            "local_efta_corpus": "locally ingested DOJ copy and OCR",
        },
        "note": (
            "Unified search filters DOJ's current case-group index by title "
            "or docket text. Documents exhaust one exact DOJ court-record "
            "case page and its native pagination, preserving EFTA identifiers "
            "and official release URLs. Discovery and probe keep DOJ, PACER, "
            "RECAP, the named court clerk, archival snapshots, and the local "
            "EFTA corpus separately attributable. DOJ case groups are an "
            "official release corpus, not complete dockets, and are not "
            "projected into the normalized court-case sidecar."
        ),
    },
    EDVA_BANKRUPTCY_SOURCE_ID: {
        "mode": "unified_read_only_recap_archive",
        "direct_tool": "uv run python tools/query_edva_bankruptcy.py --help",
        "identity_layers": [
            "courtlistener_docket_id",
            "courtlistener_docket_entry_id",
            "courtlistener_recap_document_id",
        ],
        "source_roles": {
            "courtlistener_recap": (
                "archive metadata and contributed or acquired documents"
            ),
            "pacer_ecf": "official docket and document access",
            "clerk": "official copy request",
        },
        "note": (
            "Unified case resolves an exact E.D. Virginia bankruptcy number. "
            "Docket and documents hydrate one CourtListener numeric docket ID; "
            "the same result carries entries and their nested RECAP document "
            "metadata. Discovery keeps CourtListener/RECAP, official PACER/ECF, "
            "and clerk-copy roles distinct, and probe is a bounded read-only "
            "contract check. The direct adapter also exposes explicit "
            "PACER-backed fetch, prayer, and fetch-status workflows. RECAP "
            "coverage gaps are preserved and do not establish an empty "
            "official docket."
        ),
    },
    OREGON_APPELLATE_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_oregon_appellate.py --help"),
        "note": (
            "Unified search uses the party index. Case, docket, appellate "
            "calendar, and document-metadata operations use the official "
            "anonymous API; the direct adapter also exposes case-number and "
            "title search, court enumeration, parties, and per-component "
            "completeness. Document metadata does not imply that a file is "
            "available."
        ),
    },
    OREGON_COURT_CALENDAR_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_oregon_court_calendar.py --help"),
        "note": (
            "Unified calendar treats the positional selector as an official "
            "Circuit/Tax Court location and preserves source-native hearing "
            "rows as case-linked docket events. The direct adapter also "
            "supports case, party, business, attorney, bar-number, and "
            "judicial-officer searches plus location and officer discovery. "
            "The guide's 400-result statement and the live portal's observed "
            "550-row truncated response remain separate completeness facts."
        ),
    },
    **{
        source_id: {
            "mode": (
                "unified_live"
                if tenant.case_access_state == "public"
                else "tenant_access_probe_and_official_alternatives"
            ),
            "direct_tool": (
                "uv run python tools/query_eugene_municipal_court.py "
                f"discovery --tenant {tenant.key}"
            ),
            "tenant_key": tenant.key,
            "tenant_slug": tenant.slug,
            "court_id": tenant.court_id,
            "court_type": tenant.court_type,
            "component_access": {
                "cases": tenant.case_access_state,
                "dockets": tenant.docket_access_state,
            },
            "verified_native_selectors": list(tenant.verified_selectors),
            "official_alternatives": [
                dict(route) for route in tenant.alternative_routes
            ],
            "native_search_fields": [
                field
                for field, native_selector in (
                    ("last_name", "Name"),
                    ("citation", "CitationNumber"),
                    ("docket_number", "DocketNumber"),
                    ("police_case_number", "CaseNumber"),
                    ("plate", "VehiclePlate"),
                    ("vin", "VIN"),
                )
                if (
                    not tenant.verified_selectors
                    or native_selector in tenant.verified_selectors
                )
            ],
            "note": (
                "Shared routing keeps this tenant's court identity and direct "
                "component observations. Directory links remain discovery "
                "evidence; the direct probe reports the current case/docket "
                "access state and official alternatives."
            ),
        }
        for source_id, tenant in OREGON_TYLER_TENANTS_BY_SOURCE.items()
    },
    OREGON_SMART_SEARCH_SOURCE_ID: {
        "mode": "unified_browser_handoff",
        "direct_tool": ("uv run python tools/query_oregon_smart_search.py --help"),
        "returns_case_rows": False,
        "note": (
            "Unified search prepares a validated browser handoff for the "
            "rendered Circuit and Tax Court form. The returned record is an "
            "interactive search handoff, not a case, judgment, or warrant row. "
            "Use the direct adapter for the full option vocabulary and every "
            "advanced selector."
        ),
    },
    OREGON_OJCIN_PRODUCT_DIRECTORY_SOURCE_ID: {
        "mode": "public_product_directory",
        "direct_tool": ("uv run python tools/query_oregon_ojcin_products.py --help"),
        "component_source_ids": list(OREGON_OJCIN_PRODUCT_SOURCE_IDS),
        "note": (
            "This source inventories five separately attributable OJD court-"
            "data products and their acquisition evidence. Product metadata "
            "search is not case search; acquired deliveries can be inspected "
            "into byte-level provenance receipts."
        ),
    },
    **{
        source_id: {
            "mode": "court_data_product",
            "direct_tool": (
                "uv run python tools/query_oregon_ojcin_products.py "
                f"handoff {source_id}"
            ),
            "product_id": source_id,
            "acquisition_mode": product.acquisition_mode,
            "delivery_schema_status": product.delivery_schema_status,
            "note": (
                "The product retains its own coverage, acquisition, and "
                "delivery identity. No case or docket row schema is inferred "
                "from the public product description."
            ),
        }
        for source_id, product in query_oregon_ojcin_products.PRODUCTS.items()
    },
    **{
        source_id: {
            "mode": "unified_live",
            "direct_tool": (
                "uv run python tools/query_oregon_appellate_calendars.py --help"
            ),
            "note": (
                "Unified calendar searches the separately attributed "
                "official appellate list, follows every SharePoint "
                "continuation, and preserves case-linked oral-argument or "
                "submission events. The direct adapter also exposes exact "
                "case-number filters, all accessible history, current-only "
                "selection, migration checks for the retired legacy link, "
                "and Supreme Court brief attachments when published."
            ),
        }
        for source_id in OREGON_APPELLATE_CALENDAR_SOURCE_IDS
    },
    BEXAR_HISTORICAL_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_bexar_courts.py --help",
        "note": (
            "This is the District Clerk's historical case-file archive, not "
            "the current Bexar case portal. Unified date-constrained text "
            "search uses the source's OCR search; the direct adapter also "
            "supports date-only census queries and exact page retrieval."
        ),
    },
    PA_UJS_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_pa_ujs.py --help",
        "note": (
            "Unified search uses the participant-name route by default and "
            "--entity-kind organization selects the organization route. "
            "Exact case, report links, and docket-sheet or court-summary PDF "
            "downloads are unified; filing-date and appellate census modes "
            "remain available through the direct adapter."
        ),
    },
    DELAWARE_COURTCONNECT_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_delaware_courts.py --help"),
        "note": (
            "Unified search covers public civil party and company indexes; "
            "exact case, docket, and document-metadata operations return the "
            "CourtConnect report. Judgment search, source options, and "
            "related-judgment cases are exposed by the direct adapter. "
            "Filing images remain a separate source route."
        ),
    },
    DELAWARE_OPINIONS_SOURCE_ID: {
        "mode": "direct_live_document_corpus",
        "direct_tool": ("uv run python tools/query_delaware_opinions.py --help"),
        "note": (
            "The dedicated adapter follows every official archive page by "
            "default, exposes the source's court, type, division, revision, "
            "and metadata filters, and downloads official PDFs. It is an "
            "opinion/order corpus rather than a complete case docket."
        ),
    },
    DENVER_COUNTY_DOCKET_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_denver_county_court.py --help"),
        "note": (
            "Use unified calendar with the courtroom as its selector and an "
            "exact --hearing-date. The result is the court's daily schedule "
            "and case metadata, not a filing-image collection."
        ),
    },
    COLORADO_OPINIONS_SOURCE_ID: {
        "mode": "direct_live_document_corpus",
        "direct_tool": ("uv run python tools/query_colorado_opinions.py --help"),
        "note": (
            "The dedicated adapter searches the Colorado-branded historical "
            "opinion archive by text or docket number and retrieves metadata, "
            "full text, and PDFs. The current Judicial Branch release source "
            "is retained separately for freshness."
        ),
    },
    COLORADO_OPINION_RELEASES_SOURCE_ID: {
        "mode": "direct_live_document_corpus",
        "direct_tool": ("uv run python tools/query_colorado_opinions.py --help"),
        "note": (
            "The dedicated adapter lists current Supreme Court opinions and "
            "Court of Appeals announcement packets. Packets retain their own "
            "identity because they also describe unpublished dispositions "
            "and release activity."
        ),
    },
    COLORADO_COURT_DATA_SOURCE_ID: {
        "mode": "direct_live_data_catalog",
        "direct_tool": ("uv run python tools/query_colorado_court_data.py --help"),
        "note": (
            "The dedicated adapter catalogs official reports, dashboards, "
            "and the compiled/aggregate-data request workflow. Published "
            "annual, self-represented-party, and eviction materials provide "
            "queryable complements to requested compiled data."
        ),
    },
    COLORADO_JUDICIAL_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_colorado_judicial.py --help"),
        "note": (
            "Unified search covers person, organization, and attorney names. "
            "The direct adapter also exposes the statewide court directory, "
            "location and case-component filters, native pagination, exact "
            "hearing dates, and the source-generated export."
        ),
    },
    **{
        source_id: {
            "mode": "direct_live_document_corpus",
            "direct_tool": (
                "uv run python tools/query_oregon_court_documents.py --help"
            ),
            "note": (
                "The dedicated adapter searches, pages, inspects, and "
                "downloads this official Law Library collection while "
                "retaining its collection-specific source identity. Oregon "
                "case indexes and registers of actions remain complementary "
                "routes."
            ),
        }
        for source_id in OREGON_COURT_DOCUMENT_SOURCE_IDS
    },
    PA_OPINIONS_SOURCE_ID: {
        "mode": "direct_live_document_corpus",
        "direct_tool": "uv run python tools/query_pa_opinions.py --help",
        "note": (
            "The dedicated adapter exhausts the official opinion API, "
            "supports exact docket discovery and exposed court/date/type "
            "filters, and downloads official PDFs. It is an opinion/order "
            "corpus rather than a complete case docket."
        ),
    },
    HARRIS_COURT_BULK_SOURCE_ID: {
        "mode": "unified_live_bulk_corpus",
        "direct_tool": ("uv run python tools/query_harris_court_bulk.py --help"),
        "archive_ingest": (
            "uv run python tools/ingest_harris_court_bulk.py --help"
        ),
        "note": (
            "Unified discovery lists the District Clerk's complete live "
            "artifact catalog; documents inspects an exact catalog member, "
            "probe checks the stable schema artifact, and download retrieves "
            "one exact member. The streaming ingester parses the current "
            "civil case-summary, party, and activity families and criminal "
            "filing and disposition families while retaining every source "
            "row. These extracts are a bulk metadata corpus rather than a "
            "complete filing-document portal."
        ),
    },
    LOS_ANGELES_CIVIL_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_los_angeles_court.py --help"),
        "note": (
            "Unified case, docket, and documents return the anonymous "
            "exact-number Civil Case Summary and all six published sections. "
            "Unified calendar fetches one current native tentative-ruling "
            "selection or exhaustively traverses all current selections. The "
            "direct adapter lists those exact selections and maps paid name "
            "discovery, paid image delivery, and sibling family, small-claims, "
            "probate, and appellate sources."
        ),
        "direct_default": {
            "case": "all_published_sections",
            "selections": "all_current_selections",
            "rulings_all": "all_current_selections",
        },
    },
    LOS_ANGELES_NAME_INDEX_SOURCE_ID: {
        "mode": "direct_paid_name_index_workflow",
        "direct_tool": ("uv run python tools/query_los_angeles_name_index.py --help"),
        "operations": {
            "probe": "verify the current coverage, fees, and form contracts",
            "prepare": "submit a name query and return the court cart handoff",
            "receipt --retrieve": (
                "reattach a purchased guest search and normalize its results"
            ),
            "parse-results": ("normalize a previously saved purchased result page"),
        },
        "paid_action_tool": (
            "uv run python tools/public_records_actions.py plan "
            "us-ca-los-angeles-superior-civil-name-index"
        ),
        "note": (
            "The dedicated adapter covers the free probe, cart preparation, "
            "guest-receipt recovery, saved-result parsing, and canonical "
            "case crosswalk. Checkout remains a separate court handoff. "
            "Exact-number Case Summary, document images, Archives, divorce "
            "judgment orders, appellate records, and Trellis provide "
            "complementary records or discovery routes."
        ),
    },
    LOS_ANGELES_PROBATE_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_los_angeles_probate.py --help"),
        "note": (
            "The anonymous adapter is case-number scoped. Unified case, "
            "docket, and documents use Case Summary; notes uses the separate "
            "future/past Probate Notes views; calendar uses the known-case "
            "hearing route. Name-index discovery, document-image delivery, "
            "and Archives remain separate catalog actions."
        ),
    },
    PIMA_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_pima_courts.py --help",
        "note": (
            "Unified search uses the Agave party-name route. Exact case "
            "detail includes parties, charges/dispositions when present, "
            "docket rows, and available public PDFs. The direct adapter also "
            "supports a known-party fallback for incomplete exact-case "
            "resolution."
        ),
    },
    FRANKLIN_CIO_SOURCE_ID: {
        "mode": "unified_live_party_index_and_exact_case",
        "direct_tool": (
            "uv run python tools/query_ohio_franklin_courts.py --help"
        ),
        "note": (
            "Unified search preserves the anonymous ordered lower-bound "
            "party-index window, including duplicate occurrences and lexical "
            "spillover used to establish matching-prefix coverage. Unified "
            "case, docket, and documents exhaust the exact-case route; "
            "download reacquires one emitted public filing identity in a "
            "fresh session. Recorder, auditor, sheriff-sale, and Clerk copy "
            "routes add separately attributable records."
        ),
    },
    FRANKLIN_MUNICIPAL_SOURCE_ID: {
        "mode": "unified_live_party_index_and_exact_case",
        "direct_tool": (
            "uv run python tools/query_ohio_franklin_municipal.py --help"
        ),
        "native_result_boundary": {
            "maximum_occurrences": query_ohio_franklin_municipal.NATIVE_RESULT_LIMIT,
            "continuation": None,
        },
        "note": (
            "Unified search exposes person, company, exact case-number, and "
            "ticket selectors and preserves every canonical desktop-table "
            "party occurrence. Exact case returns the published conditional "
            "case sections and docket. The download route identifies the "
            "source-generated case summary explicitly; it is not represented "
            "as an individual filed document. Eviction CSVs, arraignment "
            "reports, drop lists, and Clerk copy requests remain complementary."
        ),
    },
    DELAWARE_OHIO_COMMON_PLEAS_SOURCE_ID: {
        "mode": "unified_headed_browser_party_case_and_documents",
        "direct_tool": (
            "uv run python tools/query_ohio_delaware_common_pleas.py --help"
        ),
        "native_paging": {
            "page_sizes": [25, 50, 75, 100],
            "default": "exhaustive",
            "shared_cursor": "query_bound_offset_replay",
        },
        "note": (
            "The persistent headed helper resolves session-bound Wicket "
            "actions after the visible CourtView challenge is complete. "
            "Unified search preserves party occurrences and native paging; "
            "case, docket, and documents expose rendered sections and derived "
            "document identities; download resolves the current image action "
            "and validates the PDF. Domestic Relations and other division "
            "image limitations remain source-published access states."
        ),
    },
    LICKING_COMMON_PLEAS_SOURCE_ID: {
        "mode": "unified_verified_source_and_access_probe",
        "direct_tool": (
            "uv run python tools/query_ohio_licking_common_pleas.py --help"
        ),
        "direct_actions": [
            "targeted-browser-handoff",
            "bulk-request-handoff",
            "record-request-handoff",
            "archives-handoff",
        ],
        "note": (
            "Unified discovery and probe cover the official county landing "
            "and verified anonymous Tyler configuration routes. The direct "
            "adapter prepares targeted browser, Clerk bulk/copy, and county "
            "archive handoffs while the record-search transition presents "
            "human verification and sign-in. No post-login data endpoint is "
            "claimed by this integration."
        ),
    },
    FRANKLIN_PROBATE_SOURCE_ID: {
        "mode": "unified_live_probate_case_index",
        "direct_tool": (
            "uv run python tools/query_ohio_franklin_probate.py --help"
        ),
        "court_id": query_ohio_franklin_probate.COURT_ID,
        "native_keys": [
            "case number plus optional suffix",
            "docket logical entry position within case",
            "fiduciary number within case",
            "attorney number",
        ],
        "direct_default": "follow_source_forward_keys_to_exhaustion",
        "shared_selectors": {
            "search": (
                "case name by default; --search-field selects case-number, "
                "attorney, fiduciary, opened date, or case type"
            ),
            "case": "exact case number and optional suffix",
            "docket": "complete published docket for one exact case",
            "discovery": "source routes, identities, and copy channels",
            "probe": (
                "landing, exact case, detail, docket, fiduciary, and attorney"
            ),
        },
        "official_complements": [
            {
                "source_id": FRANKLIN_CIO_SOURCE_ID,
                "record_role": "general-division civil and criminal cases",
            },
            {
                "source_id": "us-oh-franklin-county-recorder-publicsearch",
                "record_role": "recorded real-property instruments",
            },
            {
                "source_id": "us-oh-franklin-county-auditor-property",
                "record_role": "parcel and assessment observations",
            },
        ],
        "note": (
            "The anonymous NetData indexes publish case discovery, case "
            "detail, docket descriptions and amounts, fiduciaries, and "
            "attorneys. They do not expose filing images through the verified "
            "routes; the court's certified-record and copy channels remain "
            "separately attributable acquisition paths. Native status codes "
            "are retained as published."
        ),
    },
    OHIO_REPORTER_DECISIONS_SOURCE_ID: {
        "mode": "unified_live_judicial_publications",
        "direct_tool": (
            "uv run python tools/query_ohio_reporter_decisions.py --help"
        ),
        "search_fields": [
            "full-text",
            "case-number",
            "author",
            "topics",
            "citation",
        ],
        "identity_model": {
            "publication": "WebCite",
            "case_join": "optional deciding-court case number",
            "document": "WebCite official PDF representation",
        },
        "note": (
            "Unified search exhausts the source's native WebForms pages before "
            "applying an explicitly requested caller window. It defaults to "
            "all Reporter deciding sources and full text; --court-id and "
            "--search-field select other verified native fields. Detail reads "
            "one exact WebCite publication and download resolves that WebCite "
            "before fetching its official PDF. Publications without a case "
            "number remain snapshot-only. Reporter, eCMS, Clerk's Journal, "
            "and district copies can be complementary representations of the "
            "same judicial act rather than independent corroboration."
        ),
    },
    OHIO_SUPREME_COURT_SOURCE_ID: {
        "mode": "unified_live_state_supreme_court_docket",
        "direct_tool": (
            "uv run python tools/query_ohio_supreme_court.py --help"
        ),
        "search_fields": [
            "caption",
            "case-number",
            "prior-case-number",
            "party-first-name",
            "party-last-name",
            "party-entity",
            "attorney-first-name",
            "attorney-last-name",
        ],
        "note": (
            "Unified search defaults to the source-native caption selector; "
            "--search-field selects another verified eCMS field, and "
            "--after/--before map ISO dates to the source filing-date form. "
            "Case, docket, and documents fetch one exact Supreme Court case. "
            "Download requires the case number, source document name, and an "
            "explicit DocketItems or DecisionItems section. The direct "
            "adapter separately exposes rolling recent filings. Reporter of "
            "Decisions publications, the Clerk's Journal, directories, "
            "statistics, and local trial systems remain separate components."
        ),
    },
    CONNECTICUT_CIVIL_FAMILY_SOURCE_ID: {
        "mode": "unified_live_state_trial_civil_family",
        "direct_tool": (
            "uv run python tools/query_connecticut_civil_family.py --help"
        ),
        "search_fields": ["party-name"],
        "identity_model": {
            "case": "normalized full Connecticut docket",
            "party": "publisher party number within docket",
            "filing_artifact": "publisher DocumentNo within docket",
            "other_children": (
                "publisher event/notice IDs or deterministic complete "
                "published-field tuples"
            ),
        },
        "complementary_routes": {
            "paid_bulk": query_connecticut_civil_family.BULK_DESCRIPTION_URL,
            "clerk_offices": query_connecticut_civil_family.CLERK_DIRECTORY_URL,
        },
        "note": (
            "Party search exposes the portal's fixed 50-row display slice and "
            "always labels same-name rows unresolved. An explicit caller "
            "limit may use a query- and snapshot-bound adapter cursor only "
            "within that reacquired slice; it is not publisher continuation "
            "beyond row 50. Case, docket, and documents retrieve one exact "
            "docket with published parties, appearances, filing metadata, "
            "events, transfer history, and notices. Download validates a "
            "DocumentNo-linked PDF before artifact ingestion. The official "
            "paid bulk feed is a same-publisher, field-matched complement "
            "covering pending and disposed Civil/Family cases but excluding "
            "electronic documents; clerk offices are a human-request route."
        ),
    },
    NEW_MEXICO_CASE_LOOKUP_SOURCE_ID: {
        "mode": "unified_live_statewide_case_metadata",
        "direct_tool": (
            "uv run python tools/query_new_mexico_case_lookup.py --help"
        ),
        "search_fields": ["party-name"],
        "identity_model": {
            "case": "published full case number",
            "party_search_hit": (
                "case number plus published party occurrence fields"
            ),
            "register_entry": (
                "derived from published row fields and duplicate ordinal"
            ),
        },
        "complementary_routes": {
            "documents": query_new_mexico_case_lookup.RESEARCH_NM_URL,
            "public_records_request": query_new_mexico_case_lookup.IPRA_URL,
            "source_information": query_new_mexico_case_lookup.INFO_URL,
        },
        "note": (
            "Unified search returns the first source-native page for one "
            "targeted party query. Case, docket, and claims retrieve the same "
            "caller-selected exact case response, including parties, counsel, "
            "complaints and causes, the register of actions, and judge "
            "history. Case Lookup does not publish documents; re:SearchNM, "
            "the public-records channel, and individual clerks are separately "
            "attributable complements."
        ),
    },
    SAN_MATEO_MIDX_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_san_mateo_midx.py --help"),
        "note": (
            "Unified case uses exact case number. Unified search treats the "
            "query as a business name, or as a last name when --first-name "
            "is supplied. The direct adapter also exposes the exact native "
            "person, business, and five-day filing-date selectors."
        ),
    },
    NY_ATTORNEY_REGISTRATION_SOURCE_ID: {
        "mode": "unified_live_attorney_registration",
        "direct_tool": "uv run python tools/query_ny_attorneys.py --help",
        "dataset_id": query_ny_attorneys.DATASET_ID,
        "record_grain": "quarterly_attorney_registration_snapshot",
        "identity_model": "OCA registration_number",
        "search_fields": [
            "name",
            "first-name",
            "middle-name",
            "last-name",
            "company",
            "city",
            "state",
            "zip",
            "country",
            "county",
            "law-school",
            "status",
        ],
        "complementary_routes": {
            "interactive_directory": (
                query_ny_attorneys.INTERACTIVE_DIRECTORY_URL
            ),
            "written_request_data": query_ny_attorneys.PUBLIC_ACCESS_RULE_URL,
            "public_discipline_decisions": [
                query_ny_attorneys.AD1_REGISTRATION_URL,
                query_ny_attorneys.AD2_ATTORNEY_MATTERS_URL,
                query_ny_attorneys.AD3_DISCIPLINE_URL,
                query_ny_attorneys.AD4_DISCIPLINE_URL,
                query_ny_attorneys.AD4_DECISIONS_URL,
            ],
            "nyscef_case_filings": query_ny_attorneys.NYSCEF_URL,
        },
        "note": (
            "Unified search and exact detail use OCA's public NY Open Data "
            "registration snapshot, avoiding the interactive directory "
            "challenge while preserving registration number, whole "
            "organization name, quarterly snapshot timestamp, and schema. "
            "Discovery keeps the interactive directory, written-request "
            "data, public discipline decisions, and NYSCEF case filings as "
            "separately attributable complements. Registration rows remain "
            "attorney records rather than cases, dockets, or filings."
        ),
    },
    NYSCEF_SOURCE_ID: {
        "mode": "catalog_handoff_plus_local_fulltext",
        "direct_tool": "uv run python tools/query_nyscef.py --help",
        "fulltext_tool": ("uv run python tools/query_nyscef_fulltext.py --help"),
        "local_fulltext_operations": [
            "sources",
            "probe",
            "normalize",
            "extract",
            "index",
            "search",
            "stats",
        ],
        "identity_model": {
            "case": "NYSCEF-CASE:<court>:<case-number>",
            "document": "NYSCEF-DOC:<case-identity>:<document-number>",
            "artifact": "NYSCEF-PDF:<sha256>",
            "page_evidence": "<record-identity>:p<page-number>",
        },
        "note": (
            "The main adapter reports the catalog-selected acquisition route. "
            "After a document manifest and PDFs are acquired, the full-text "
            "tool normalizes them, extracts page text with targeted OCR, "
            "builds an incremental SQLite FTS5 index, searches filing bodies, "
            "and distinguishes listed-party matches from non-party leads. "
            "Law Reporting Bureau, Court-PASS, WebCivil, county clerks, "
            "CourtListener, and commercial services remain complementary."
        ),
    },
    NY_LAW_REPORTS_SOURCE_ID: {
        "mode": "direct_tool",
        "direct_tool": ("uv run python tools/query_ny_law_reports.py --help"),
        "note": (
            "The official Law Reporting Bureau route provides selected "
            "published trial-court and Commercial Division opinions, "
            "including full opinion text. It complements rather than "
            "replaces NYSCEF case files and docket documents."
        ),
    },
    NY_COLUMN_SOURCE_ID: {
        "mode": "direct_tool",
        "direct_tool": "uv run python tools/query_ny_column.py --help",
        "note": (
            "Column provides full newspaper notice text and publication "
            "metadata for discovery. It does not replace the underlying "
            "court filing; use the referenced case and clerk routes for that "
            "record."
        ),
    },
    TAX_COURT_SOURCE_ID: {
        "mode": "direct_tool",
        "direct_tool": "uv run python tools/query_tax_court.py --help",
        "note": (
            "The dedicated DAWSON adapter exposes case, docket, order, "
            "opinion, trial-session, public-document, and printable-docket "
            "routes with their native source ceilings."
        ),
    },
    PALM_BEACH_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_palm_beach_courts.py --help"),
        "note": (
            "The public guest route runs in a local headed Playwright/Chrome "
            "session. Unified search uses exact party/company matching; use "
            "the direct adapter for full-case-number search, starts-with "
            "matching, runtime checks, and source probes. The portal reports "
            "at most 200 recent broad-search matches."
        ),
    },
    TEXAS_TAMES_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": ("uv run python tools/query_texas_appellate.py --help"),
        "note": (
            "The unified search defaults to case style and supports the "
            "source's court, filing-date, county, originating-court, and "
            "trial-case selectors. The direct adapter also exposes partial "
            "case-number and attorney search."
        ),
    },
    TEXAS_SUPREME_PUBLICATIONS_SOURCE_ID: {
        "mode": "unified_live_official_publications",
        "direct_tool": (
            "uv run python tools/query_texas_supreme_publications.py --help"
        ),
        "court_id": query_texas_supreme_publications.COURT_ID,
        "note": (
            "Unified search traverses caller-selected annual release pages "
            "using --after/--before. The direct adapter also enumerates "
            "years and release dates, reads one exact hand-down date, and "
            "preserves outage and pre-2014 aggregate artifacts."
        ),
    },
    VICOURTS_SOURCE_ID: {
        "mode": "unified_live",
        "direct_tool": "uv run python tools/query_vicourts.py --help",
        "note": (
            "Unified search uses the party route. The direct adapter also "
            "exposes case-number and title search, OCR document search, "
            "publications, court enumeration, and legacy numeric PDF items."
        ),
    },
}


def _source_guidance(source_id: str) -> dict[str, Any]:
    guidance = dict(DIRECT_TOOL_GUIDANCE.get(source_id, {"mode": "catalog_only"}))
    guidance["unified_operations"] = sorted(LIVE_ROUTES.get(source_id, {}))
    return guidance


def _jurisdiction(value: str | None) -> JurisdictionMetadata:
    normalized = str(value or "").strip()
    return JurisdictionMetadata(
        jurisdiction_id=normalized or "local",
        name=(
            f"Court jurisdiction {normalized}"
            if normalized
            else "Local normalized state and local courts"
        ),
    )


def _query(
    source: SourceMetadata,
    operation: str,
    selector: str | None,
    args: argparse.Namespace,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=source,
        jurisdiction=_jurisdiction(getattr(args, "jurisdiction", None)),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "source": getattr(args, "source", None),
                "jurisdiction": getattr(args, "jurisdiction", None),
                "court_id": getattr(args, "court_id", None),
                "courthouse": getattr(args, "courthouse", None),
                "search_field": getattr(args, "search_field", None),
                "first_name": getattr(args, "first_name", None),
                "middle_name": getattr(args, "middle_name", None),
                "name_suffix": getattr(args, "name_suffix", None),
                "party_type": getattr(args, "party_type", None),
                "case_year": getattr(args, "case_year", None),
                "case_status": getattr(args, "case_status", None),
                "court_category": getattr(args, "court_category", None),
                "date_of_birth": getattr(args, "date_of_birth", None),
                "drivers_license": getattr(args, "drivers_license", None),
                "plate_state": getattr(args, "plate_state", None),
                "violation_number": getattr(args, "violation_number", None),
                "case_type": getattr(args, "case_type", None),
                "filed_after": getattr(args, "after", None),
                "filed_before": getattr(args, "before", None),
                "hearing_date": getattr(args, "hearing_date", None),
                "document_type": getattr(args, "document_type", None),
                "document_section": getattr(args, "document_section", None),
                "case_number": getattr(args, "case_number", None),
                "case_uuid": getattr(args, "case_uuid", None),
                "view": getattr(args, "view", None),
            },
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


def _case_filters(
    args: argparse.Namespace,
    *,
    table_alias: str = "c",
) -> tuple[list[str], list[Any]]:
    conditions = [f"{table_alias}.access_state=?"]
    params: list[Any] = [PUBLIC_STATE]
    if args.court_id:
        conditions.append(f"{table_alias}.court_id=?")
        params.append(args.court_id)
    if args.jurisdiction:
        conditions.append(
            "EXISTS(SELECT 1 FROM court filter_court "
            f"WHERE filter_court.court_id={table_alias}.court_id "
            "AND (filter_court.state_code=? OR filter_court.county_geoid=?))"
        )
        params.extend([args.jurisdiction.upper(), args.jurisdiction])
    if getattr(args, "case_type", None):
        conditions.append(f"{table_alias}.case_type LIKE ? ESCAPE '\\' COLLATE NOCASE")
        params.append(_like(args.case_type))
    if getattr(args, "after", None):
        conditions.append(f"{table_alias}.filing_date>=?")
        params.append(args.after)
    if getattr(args, "before", None):
        conditions.append(f"{table_alias}.filing_date<=?")
        params.append(args.before)
    return conditions, params


def _case_record(
    db, row: Mapping[str, Any], *, include_parties: bool = True
) -> dict[str, Any]:
    row = dict(row)
    record = {
        "canonical_ref": canonical_court_ref(
            row["source_id"],
            row["court_id"],
            row["raw_case_number"],
            native_id=row["source_internal_id"],
        ),
        "case_id": row["case_id"],
        "source_id": row["source_id"],
        "source_internal_id": row["source_internal_id"],
        "court": {
            "court_id": row["court_id"],
            "native_court_id": row["native_court_id"],
            "name": row["court_name"],
            "state_code": row["state_code"],
            "county_geoid": row["county_geoid"],
            "level": row["court_level"],
            "division": row["division"],
            "official_url": row["court_official_url"],
        },
        "raw_case_number": row["raw_case_number"],
        "display_case_number": row["display_case_number"],
        "caption": row["caption"],
        "case_type": row["case_type"],
        "filing_date": row["filing_date"],
        "disposition_date": row["disposition_date"],
        "status": row["case_status"],
        "access_state": row["access_state"],
        "certified_record": bool(row["certified_record"]),
        "source_url": row["case_source_url"],
    }
    if (
        row["source_id"] == OREGON_COURT_CALENDAR_SOURCE_ID
        and row["court_id"] == OREGON_STATEWIDE_CALENDAR_COURT_ID
        and row["county_geoid"] is None
    ):
        record["identity_gap"] = {
            "field": "court",
            "state": "aggregate_location",
            "resolution": "concrete_court_unresolved",
        }
    if include_parties:
        record["parties"] = [
            {
                "case_party_id": party["case_party_id"],
                "sequence": party["sequence_no"],
                "role": party["role"],
                "raw_name": party["raw_name"],
                "normalized_name": party["normalized_name"],
                "entity_kind": party["entity_kind"],
            }
            for party in db.execute(
                """
                SELECT * FROM case_party
                WHERE case_id=? AND access_state='public'
                ORDER BY sequence_no, case_party_id
                """,
                (row["case_id"],),
            )
        ]
    return record


CASE_SELECT = """
SELECT c.case_id, c.source_id, c.court_id, c.raw_case_number,
       c.display_case_number, c.source_internal_id, c.case_identity_key,
       c.caption, c.case_type, c.filing_date,
       c.disposition_date, c.status AS case_status, c.access_state,
       c.certified_record, c.source_url AS case_source_url,
       ct.native_court_id, ct.name AS court_name, ct.state_code,
       ct.county_geoid, ct.court_level, ct.division,
       ct.official_url AS court_official_url
FROM case_record c
JOIN court ct ON ct.court_id=c.court_id
"""


def _local_search(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions, params = _case_filters(args)
    pattern = _like(selector)
    conditions.append(
        "(c.raw_case_number LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR c.display_case_number LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR c.caption LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR EXISTS(SELECT 1 FROM case_party cp "
        "WHERE cp.case_id=c.case_id AND cp.access_state='public' "
        "AND (cp.raw_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR cp.normalized_name LIKE ? ESCAPE '\\' COLLATE NOCASE)) "
        "OR EXISTS(SELECT 1 FROM case_representation cr "
        "JOIN case_party cp2 ON cp2.case_party_id=cr.case_party_id "
        "JOIN attorney a ON a.attorney_id=cr.attorney_id "
        "WHERE cr.case_id=c.case_id AND cp2.access_state='public' "
        "AND (a.raw_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR a.normalized_name LIKE ? ESCAPE '\\' COLLATE NOCASE)))"
    )
    params.extend([pattern] * 7)
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        {CASE_SELECT}
        WHERE {" AND ".join(conditions)}
        ORDER BY c.filing_date DESC, c.case_id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    return [_case_record(db, row) for row in rows], cursor


def _local_case(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions, params = _case_filters(args)
    conditions.append("(c.raw_case_number=? OR c.display_case_number=?)")
    params.extend([selector, selector, args.limit + 1, offset])
    rows = db.execute(
        f"""
        {CASE_SELECT}
        WHERE {" AND ".join(conditions)}
        ORDER BY c.filing_date DESC, c.case_id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    return [_case_record(db, row) for row in rows], cursor


def _matching_public_case_filters(
    selector: str,
    args: argparse.Namespace,
) -> tuple[list[str], list[Any]]:
    conditions, params = _case_filters(args)
    conditions.append("(c.raw_case_number=? OR c.display_case_number=?)")
    params.extend([selector, selector])
    return conditions, params


def _normalized_event_value_sql(expression: str) -> str:
    return (
        f"LOWER(REPLACE(REPLACE(TRIM(COALESCE({expression}, '')), '-', '_'), ' ', '_'))"
    )


def _calendar_event_filter(
    db: sqlite3.Connection,
) -> tuple[str, list[str]]:
    columns = {
        str(row["name"]) for row in db.execute("PRAGMA table_info(docket_entry)")
    }
    candidates = ["de.event_code"]
    if "event_type" in columns:
        candidates.insert(0, "de.event_type")
    candidates.extend(
        [
            (
                "CASE WHEN json_valid(de.raw_json) "
                "THEN json_extract(de.raw_json, '$.event_type') END"
            ),
            (
                "CASE WHEN json_valid(de.raw_json) "
                "THEN json_extract(de.raw_json, '$.event_code') END"
            ),
        ]
    )
    predicates: list[str] = []
    params: list[str] = []
    placeholders = ", ".join("?" for _ in HEARING_EVENT_ALIASES)
    for candidate in candidates:
        predicates.append(
            f"{_normalized_event_value_sql(candidate)} IN ({placeholders})"
        )
        params.extend(HEARING_EVENT_ALIASES)
    return f"({' OR '.join(predicates)})", params


def _docket_published_hearing_metadata(
    row: sqlite3.Row,
) -> dict[str, str]:
    raw = _json_mapping(row["raw_json"])
    columns = set(row.keys())
    metadata: dict[str, str] = {}
    for key in ("event_type", "event_time", "judge", "location", "status"):
        value = row[key] if key in columns else None
        if value is None and raw is not None:
            value = raw.get(key)
        if isinstance(value, str) and value.strip():
            metadata[key] = value.strip()
    return metadata


def _public_case_row(
    db: sqlite3.Connection,
    case_id: int,
    cache: dict[int, sqlite3.Row],
) -> sqlite3.Row:
    case = cache.get(case_id)
    if case is not None:
        return case
    case = db.execute(
        f"""
        {CASE_SELECT}
        WHERE c.case_id=? AND c.access_state=?
        """,
        (case_id, PUBLIC_STATE),
    ).fetchone()
    if case is None:
        raise ValueError(f"public case {case_id} is no longer available")
    cache[case_id] = case
    return case


def _local_docket(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions, params = _matching_public_case_filters(selector, args)
    conditions.append("de.access_state='public'")
    if args.command == "notes":
        conditions.append("de.event_code='probate_note'")
        view = getattr(args, "view", "all")
        if view != "all":
            conditions.append("json_extract(de.raw_json, '$.raw.view')=?")
            params.append(view)
    elif args.command == "calendar":
        event_filter, event_params = _calendar_event_filter(db)
        conditions.append(event_filter)
        params.extend(event_params)
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT de.*
        FROM docket_entry de
        JOIN case_record c ON c.case_id=de.case_id
        WHERE {" AND ".join(conditions)}
        ORDER BY
            c.filing_date DESC,
            c.case_id DESC,
            CASE WHEN de.sequence_no GLOB '[0-9]*'
                 THEN CAST(de.sequence_no AS INTEGER) END,
            de.sequence_no,
            de.subsequence_no,
            de.docket_entry_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, next_cursor = _next_cursor(offset, args.limit, rows)
    records: list[dict[str, Any]] = []
    case_cache: dict[int, sqlite3.Row] = {}
    for row in rows:
        case = _public_case_row(db, row["case_id"], case_cache)
        record = {
            "canonical_ref": canonical_court_ref(
                case["source_id"],
                case["court_id"],
                case["raw_case_number"],
                "docket",
                row["native_entry_id"],
            ),
            "case": _case_record(db, case, include_parties=False),
            "docket_entry_id": row["docket_entry_id"],
            "native_entry_id": row["native_entry_id"],
            "sequence": row["sequence_no"],
            "subsequence": row["subsequence_no"],
            "event_code": row["event_code"],
            "text": row["raw_text"],
            "filed_date": row["filed_date"],
            "entered_date": row["entered_date"],
            "event_date": row["event_date"],
            "filer_raw": row["filer_raw"],
            "document_available": (
                None
                if row["document_available"] is None
                else bool(row["document_available"])
            ),
            "access_state": row["access_state"],
        }
        record.update(_docket_published_hearing_metadata(row))
        records.append(record)
    return records, next_cursor


def _local_claims(
    db,
    selector: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions, params = _matching_public_case_filters(selector, args)
    conditions.append("COALESCE(cc.access_state, 'public')='public'")
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT cc.*
        FROM case_claim cc
        JOIN case_record c ON c.case_id=cc.case_id
        WHERE {" AND ".join(conditions)}
        ORDER BY
            c.filing_date DESC,
            c.case_id DESC,
            CASE WHEN cc.sequence_no IS NULL THEN 1 ELSE 0 END,
            cc.sequence_no,
            cc.claim_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, next_cursor = _next_cursor(offset, args.limit, rows)
    records: list[dict[str, Any]] = []
    case_cache: dict[int, sqlite3.Row] = {}
    for row in rows:
        case = _public_case_row(db, row["case_id"], case_cache)
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    case["source_id"],
                    case["court_id"],
                    case["raw_case_number"],
                    "claim",
                    row["native_claim_id"],
                ),
                "case": _case_record(db, case, include_parties=False),
                "claim_id": row["claim_id"],
                "native_claim_id": row["native_claim_id"],
                "sequence": row["sequence_no"],
                "claim_type": row["claim_type"],
                "claim_date": row["claim_date"],
                "claimant_raw": row["claimant_raw"],
                "amount_minor": row["amount_minor"],
                "currency": row["currency"],
                "status": row["status"],
                "limited_stub": (
                    None if row["limited_stub"] is None else bool(row["limited_stub"])
                ),
                "access_state": row["access_state"] or case["access_state"],
                "native_access_state": row["native_access_state"],
            }
        )
    return records, next_cursor


def _local_documents(
    db, selector: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str | None]:
    offset = _cursor_offset(args.cursor)
    conditions, params = _matching_public_case_filters(selector, args)
    conditions.append("d.access_state='public'")
    if args.document_type:
        conditions.append("d.document_type LIKE ? ESCAPE '\\' COLLATE NOCASE")
        params.append(_like(args.document_type))
    conditions.append("(d.docket_entry_id IS NULL OR de.docket_entry_id IS NOT NULL)")
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT d.*, de.native_entry_id, de.sequence_no, de.raw_text
        FROM document_artifact d
        JOIN case_record c ON c.case_id=d.case_id
        LEFT JOIN docket_entry de
          ON de.docket_entry_id=d.docket_entry_id
         AND de.access_state='public'
        WHERE {" AND ".join(conditions)}
        ORDER BY
            c.filing_date DESC,
            c.case_id DESC,
            d.filed_date,
            d.document_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, next_cursor = _next_cursor(offset, args.limit, rows)
    records: list[dict[str, Any]] = []
    case_cache: dict[int, sqlite3.Row] = {}
    for row in rows:
        case = _public_case_row(db, row["case_id"], case_cache)
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    case["source_id"],
                    case["court_id"],
                    case["raw_case_number"],
                    "document",
                    row["native_document_id"],
                ),
                "case": _case_record(db, case, include_parties=False),
                "document_id": row["document_id"],
                "native_document_id": row["native_document_id"],
                "document_type": row["document_type"],
                "filed_date": row["filed_date"],
                "source_url": row["source_url"],
                "sha256": row["sha256"],
                "mime_type": row["mime_type"],
                "page_count": row["page_count"],
                "ocr_status": row["ocr_status"],
                "certification_status": row["certification_status"],
                "access_state": row["access_state"],
                "docket_entry": (
                    {
                        "native_entry_id": row["native_entry_id"],
                        "sequence": row["sequence_no"],
                        "text": row["raw_text"],
                    }
                    if row["native_entry_id"]
                    else None
                ),
            }
        )
    return records, next_cursor


LOCAL_HANDLERS: dict[
    str,
    Callable[
        [sqlite3.Connection, str, argparse.Namespace],
        tuple[list[dict[str, Any]], str | None],
    ],
] = {
    "search": _local_search,
    "case": _local_case,
    "docket": _local_docket,
    "notes": _local_docket,
    "calendar": _local_docket,
    "claims": _local_claims,
    "documents": _local_documents,
}

LOCAL_COVERAGE_TABLES = (
    "source_snapshot",
    "court",
    "case_record",
    "case_claim",
    "case_party",
    "attorney",
    "docket_entry",
    "document_artifact",
)

_COURT_OPERATION_ALIASES = {
    "search": {"search", "case_search", "party_search"},
    "case": {"case", "case_lookup"},
    "docket": {"docket", "docket_entries"},
    "notes": {"notes", "probate_notes"},
    "calendar": {"calendar", "hearing_calendar"},
    "claims": {"claims", "claim", "probate_claims"},
    "documents": {"documents", "document", "document_search"},
    "download": {"download", "document"},
}
_COURT_SELECTOR_KEYS = (
    "selector",
    "query",
    "case_number",
    "document_id",
    "native_document_id",
    "party_name",
)


def _local_coverage_counts(db: sqlite3.Connection) -> dict[str, int]:
    """Return the rows that establish local data or query provenance."""
    return {
        table: int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in LOCAL_COVERAGE_TABLES
    }


def _json_mapping(raw: Any) -> Mapping[str, Any] | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, Mapping) else None


def _normalized_selector(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _filter_matches(
    parameters: Mapping[str, Any],
    *,
    requested: Any,
    keys: tuple[str, ...],
) -> bool:
    evidence = next(
        (parameters.get(key) for key in keys if parameters.get(key) not in (None, "")),
        None,
    )
    if requested in (None, ""):
        return evidence in (None, "")
    return str(evidence or "").casefold() == str(requested).casefold()


def _court_query_evidence(
    snapshot: Mapping[str, Any],
    args: argparse.Namespace,
    selector: str,
) -> dict[str, Any] | None:
    snapshot = dict(snapshot)
    raw = _json_mapping(snapshot.get("raw_json"))
    coverage = _json_mapping(snapshot.get("coverage_json"))
    if raw is None or coverage is None:
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
    if source.get("source_id") != snapshot.get("source_id"):
        return None
    if query.get("fingerprint") != snapshot.get("query_fingerprint"):
        return None

    operation = str(metadata.get("operation") or "").strip().casefold()
    if operation not in _COURT_OPERATION_ALIASES.get(args.command, {args.command}):
        return None
    parameters = metadata.get("parameters")
    if not isinstance(parameters, Mapping):
        return None
    selectors = {
        _normalized_selector(parameters.get(key))
        for key in _COURT_SELECTOR_KEYS
        if parameters.get(key) not in (None, "")
    }
    if _normalized_selector(selector) not in selectors:
        return None

    evidence_jurisdiction = str(jurisdiction.get("jurisdiction_id") or "").strip()
    requested_jurisdiction = str(args.jurisdiction or "").strip()
    requested_court = str(args.court_id or "").strip()
    if requested_court:
        if str(parameters.get("court_id") or "").strip() != requested_court:
            return None
    elif requested_jurisdiction:
        jurisdiction_values = {
            evidence_jurisdiction,
            str(jurisdiction.get("state_code") or "").strip(),
            str(jurisdiction.get("county_fips") or "").strip(),
            str(parameters.get("jurisdiction") or "").strip(),
        }
        if requested_jurisdiction not in jurisdiction_values:
            return None
    else:
        return None

    if not _filter_matches(
        parameters,
        requested=args.case_type,
        keys=("case_type",),
    ):
        return None
    if not _filter_matches(
        parameters,
        requested=args.after,
        keys=("filed_after", "after", "start_date"),
    ):
        return None
    if not _filter_matches(
        parameters,
        requested=args.before,
        keys=("filed_before", "before", "end_date"),
    ):
        return None
    if not _filter_matches(
        parameters,
        requested=getattr(args, "document_type", None),
        keys=("document_type",),
    ):
        return None
    if not _filter_matches(
        parameters,
        requested=getattr(args, "case_number", None),
        keys=("case_number",),
    ):
        return None

    complete_zero = (
        snapshot.get("access_status") == ResultStatus.NO_RESULTS.value
        and raw.get("status") == ResultStatus.NO_RESULTS.value
        and raw.get("records") == []
        and raw.get("next_cursor") is None
        and coverage.get("record_count") == 0
        and coverage.get("next_cursor") is None
        and metadata.get("cursor") is None
        and bool(snapshot.get("retrieved_at"))
    )
    return {
        "source_id": snapshot["source_id"],
        "status": snapshot["access_status"],
        "retrieved_at": snapshot["retrieved_at"],
        "query_fingerprint": snapshot["query_fingerprint"],
        "jurisdiction": evidence_jurisdiction,
        "court_id": parameters.get("court_id"),
        "operation": operation,
        "filed_after": args.after,
        "filed_before": args.before,
        "complete_zero": complete_zero,
    }


def _court_route_guidance(args: argparse.Namespace) -> dict[str, Any]:
    guidance: dict[str, Any] = {
        "discover": (
            "uv run python tools/query_state_courts.py sources "
            "[--jurisdiction STATE_OR_GEOID] --output FILE"
        ),
        "select_source": "--source SOURCE_ID",
        "plan_action": (
            "uv run python tools/public_records_actions.py plan SOURCE_ID "
            "--operation OPERATION --selector SELECTOR --output FILE"
        ),
        "catalog_sources": [],
    }
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        for source in catalog.list_sources(
            domain="court",
            jurisdiction=args.jurisdiction,
        ):
            source_id = source["source_id"]
            decision = catalog.machine_acquisition_decision(source_id)
            guidance["catalog_sources"].append(
                {
                    "source_id": source_id,
                    "official_url": source.get("official_url"),
                    "acquisition_status": acquisition_result_status(decision),
                }
            )
    except (CatalogError, sqlite3.Error, ValueError) as error:
        guidance["catalog_error"] = str(error)
    return guidance


def _court_local_coverage(
    db: sqlite3.Connection,
    args: argparse.Namespace,
    selector: str,
) -> dict[str, Any]:
    row_counts = _local_coverage_counts(db)
    requested_jurisdiction = str(args.jurisdiction or "").strip()
    requested_court = str(args.court_id or "").strip()
    if requested_court:
        scope_clause = "ct.court_id=?"
        scope_params: tuple[Any, ...] = (requested_court,)
    elif requested_jurisdiction:
        scope_clause = "(ct.state_code=? OR ct.county_geoid=?)"
        scope_params = (
            requested_jurisdiction.upper(),
            requested_jurisdiction,
        )
    else:
        scope_clause = "1=1"
        scope_params = ()

    requested_counts = {
        "courts": int(
            db.execute(
                f"SELECT COUNT(*) FROM court ct WHERE {scope_clause}",
                scope_params,
            ).fetchone()[0]
        ),
        "cases": int(
            db.execute(
                f"""
                SELECT COUNT(*) FROM case_record c
                JOIN court ct ON ct.court_id=c.court_id
                WHERE {scope_clause}
                """,
                scope_params,
            ).fetchone()[0]
        ),
        "public_cases": int(
            db.execute(
                f"""
                SELECT COUNT(*) FROM case_record c
                JOIN court ct ON ct.court_id=c.court_id
                WHERE {scope_clause} AND c.access_state='public'
                """,
                scope_params,
            ).fetchone()[0]
        ),
    }
    source_ids = {
        str(row[0])
        for row in db.execute(
            f"""
            SELECT DISTINCT c.source_id FROM case_record c
            JOIN court ct ON ct.court_id=c.court_id
            WHERE {scope_clause}
            """,
            scope_params,
        )
    }

    matching_evidence: list[dict[str, Any]] = []
    observed_requested_scope = False
    snapshots = db.execute(
        """
        SELECT snapshot_id, source_id, query_fingerprint, retrieved_at,
               access_status, coverage_json, raw_json
        FROM source_snapshot
        ORDER BY retrieved_at DESC, snapshot_id DESC
        """
    ).fetchall()
    for snapshot in snapshots:
        raw = _json_mapping(snapshot["raw_json"])
        if raw is not None:
            query = raw.get("query")
            jurisdiction = (
                query.get("jurisdiction") if isinstance(query, Mapping) else None
            )
            metadata = query.get("query") if isinstance(query, Mapping) else None
            parameters = (
                metadata.get("parameters") if isinstance(metadata, Mapping) else None
            )
            if isinstance(jurisdiction, Mapping):
                values = {
                    str(jurisdiction.get("jurisdiction_id") or "").strip(),
                    str(jurisdiction.get("state_code") or "").strip(),
                    str(jurisdiction.get("county_fips") or "").strip(),
                }
                if requested_jurisdiction and requested_jurisdiction in values:
                    observed_requested_scope = True
                    source_ids.add(str(snapshot["source_id"]))
            if (
                requested_court
                and isinstance(parameters, Mapping)
                and str(parameters.get("court_id") or "").strip() == requested_court
            ):
                observed_requested_scope = True
                source_ids.add(str(snapshot["source_id"]))
        evidence = _court_query_evidence(snapshot, args, selector)
        if evidence is not None:
            matching_evidence.append(evidence)

    latest_by_source: dict[str, dict[str, Any]] = {}
    for evidence in matching_evidence:
        latest_by_source.setdefault(evidence["source_id"], evidence)
    latest = list(latest_by_source.values())
    authoritative_zero = bool(latest) and all(
        evidence["complete_zero"] for evidence in latest
    )
    scope_requested = bool(requested_jurisdiction or requested_court)
    scope_covered = (
        any(row_counts.values())
        if not scope_requested
        else observed_requested_scope or any(requested_counts.values())
    )
    return {
        "authoritative_zero": authoritative_zero,
        "requested_scope": {
            "operation": args.command,
            "selector": selector,
            "jurisdiction": requested_jurisdiction or None,
            "court_id": requested_court or None,
            "case_type": args.case_type,
            "filed_after": args.after,
            "filed_before": args.before,
            "document_type": getattr(args, "document_type", None),
            "case_number": getattr(args, "case_number", None),
        },
        "sidecar": {
            "row_counts": row_counts,
            "requested_scope_counts": requested_counts,
            "requested_scope_observed": observed_requested_scope,
            "scope_covered": scope_covered,
            "source_ids": sorted(source_ids),
        },
        "matching_query_evidence": latest,
    }


def _restriction_metadata(
    db: sqlite3.Connection,
    case_id: int,
    fallback_state: str,
) -> dict[str, Any]:
    row = db.execute(
        """
        SELECT source_id, event_type, effective_at
        FROM restriction_event
        WHERE case_id=?
        ORDER BY effective_at DESC, restriction_event_id DESC
        LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        return {
            "current_access_state": fallback_state,
            "restriction_event": None,
        }
    return {
        "current_access_state": fallback_state,
        "restriction_event": {
            "source_id": row["source_id"],
            "event_type": row["event_type"],
            "effective_at": row["effective_at"],
        },
    }


def _restricted_case_tombstones(
    db: sqlite3.Connection,
    selector: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], str | None]:
    if args.command not in {
        "case",
        "docket",
        "notes",
        "calendar",
        "claims",
        "documents",
    }:
        return [], None
    offset = _cursor_offset(args.cursor)
    conditions = [
        "c.access_state<>'public'",
        "(c.raw_case_number=? OR c.display_case_number=?)",
    ]
    params: list[Any] = [selector, selector]
    if args.court_id:
        conditions.append("c.court_id=?")
        params.append(args.court_id)
    if args.jurisdiction:
        conditions.append("(ct.state_code=? OR ct.county_geoid=?)")
        params.extend([args.jurisdiction.upper(), args.jurisdiction])
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT c.case_id, c.source_id, c.court_id, c.raw_case_number,
               c.source_internal_id, c.access_state,
               ct.name AS court_name, ct.state_code, ct.county_geoid
        FROM case_record c
        JOIN court ct ON ct.court_id=c.court_id
        WHERE {" AND ".join(conditions)}
        ORDER BY c.case_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    return [
        {
            "canonical_ref": canonical_court_ref(
                row["source_id"],
                row["court_id"],
                row["raw_case_number"],
                native_id=row["source_internal_id"],
            ),
            "record_kind": "case_restriction_tombstone",
            "source_id": row["source_id"],
            "court": {
                "court_id": row["court_id"],
                "name": row["court_name"],
                "state_code": row["state_code"],
                "county_geoid": row["county_geoid"],
            },
            "raw_case_number": row["raw_case_number"],
            "source_internal_id": row["source_internal_id"],
            "access_state": row["access_state"],
            "restriction": _restriction_metadata(
                db,
                row["case_id"],
                row["access_state"],
            ),
        }
        for row in rows
    ], cursor


def _restricted_document_tombstones(
    db: sqlite3.Connection,
    selector: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], str | None]:
    if args.command != "download":
        return [], None
    offset = _cursor_offset(args.cursor)
    conditions = [
        "d.native_document_id=?",
        (
            "(d.access_state<>'public' OR c.access_state<>'public' "
            "OR (d.docket_entry_id IS NOT NULL AND "
            "COALESCE(de.access_state, 'unknown')<>'public'))"
        ),
    ]
    params: list[Any] = [selector]
    if args.case_number:
        conditions.append("(c.raw_case_number=? OR c.display_case_number=?)")
        params.extend([args.case_number, args.case_number])
    if args.court_id:
        conditions.append("c.court_id=?")
        params.append(args.court_id)
    if args.jurisdiction:
        conditions.append("(ct.state_code=? OR ct.county_geoid=?)")
        params.extend([args.jurisdiction.upper(), args.jurisdiction])
    params.extend([args.limit + 1, offset])
    rows = db.execute(
        f"""
        SELECT d.document_id, d.source_id, d.native_document_id,
               d.access_state AS document_access_state,
               c.case_id, c.raw_case_number, c.source_internal_id,
               c.access_state AS case_access_state,
               de.access_state AS docket_access_state
        FROM document_artifact d
        JOIN case_record c ON c.case_id=d.case_id
        JOIN court ct ON ct.court_id=c.court_id
        LEFT JOIN docket_entry de ON de.docket_entry_id=d.docket_entry_id
        WHERE {" AND ".join(conditions)}
        ORDER BY d.document_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    rows, cursor = _next_cursor(offset, args.limit, rows)
    records = []
    for row in rows:
        access_states = [
            state
            for state in (
                row["document_access_state"],
                row["case_access_state"],
                row["docket_access_state"],
            )
            if state and state != PUBLIC_STATE
        ]
        current_state = access_states[0] if access_states else "restricted"
        record = {
            "record_kind": "document_restriction_tombstone",
            "source_id": row["source_id"],
            "native_document_id": row["native_document_id"],
            "access_state": current_state,
            "restriction": _restriction_metadata(
                db,
                row["case_id"],
                current_state,
            ),
        }
        if row["source_internal_id"] is not None:
            record["case_source_internal_id"] = row["source_internal_id"]
        if args.case_number:
            record["case_number"] = row["raw_case_number"]
        records.append(record)
    return records, cursor


def _restricted_result(
    db: sqlite3.Connection,
    query: PublicRecordsQuery,
    selector: str,
    args: argparse.Namespace,
) -> PublicRecordsResult | None:
    if args.command == "download":
        records, cursor = _restricted_document_tombstones(
            db,
            selector,
            args,
        )
    else:
        records, cursor = _restricted_case_tombstones(
            db,
            selector,
            args,
        )
    if not records:
        return None
    return PublicRecordsResult.failure(
        query,
        ResultStatus.RESTRICTED,
        [
            PublicRecordsError(
                code="known_record_restricted",
                message=(
                    "the exact identifier is known locally, but its current "
                    "access state does not permit serving record contents"
                ),
                category="record_access",
                retryable=False,
                details={
                    "record_kind": records[0]["record_kind"],
                    "match_count": len(records),
                    "route_guidance": _court_route_guidance(args),
                },
            )
        ],
        records=records,
        next_cursor=cursor,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _download_local(
    db, selector: str, args: argparse.Namespace, query: PublicRecordsQuery
) -> PublicRecordsResult:
    conditions, params = _case_filters(args)
    conditions.extend(
        [
            "d.access_state='public'",
            "d.native_document_id=?",
            (
                "(d.docket_entry_id IS NULL OR EXISTS("
                "SELECT 1 FROM docket_entry public_de "
                "WHERE public_de.docket_entry_id=d.docket_entry_id "
                "AND public_de.access_state='public'))"
            ),
        ]
    )
    params.append(selector)
    if args.case_number:
        conditions.append("(c.raw_case_number=? OR c.display_case_number=?)")
        params.extend([args.case_number, args.case_number])
    rows = db.execute(
        f"""
        SELECT d.*, c.raw_case_number, c.source_internal_id,
               c.source_id AS case_source_id, c.court_id
        FROM document_artifact d
        JOIN case_record c ON c.case_id=d.case_id
        WHERE {" AND ".join(conditions)}
        ORDER BY d.document_id DESC
        LIMIT 2
        """,
        params,
    ).fetchall()
    if not rows:
        return PublicRecordsResult.success(query, [])
    if len(rows) > 1 and not args.case_number:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.HUMAN_REQUIRED,
            [
                PublicRecordsError(
                    code="ambiguous_document_id",
                    message=(
                        "document identifier matches multiple public cases; "
                        "provide --case-number"
                    ),
                    category="query_resolution",
                    retryable=False,
                    details={"match_count_at_least": 2},
                )
            ],
        )

    row = rows[0]
    storage_path = row["storage_path"]
    if not storage_path:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_not_stored",
                    message="public document metadata exists but no local artifact is stored",
                    category="local_store",
                    retryable=False,
                )
            ],
        )
    source_path = Path(storage_path)
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path
    if not source_path.is_file():
        return PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_missing",
                    message=f"stored artifact path does not exist: {storage_path}",
                    category="local_store",
                    retryable=False,
                )
            ],
        )
    actual_sha256 = _sha256_file(source_path)
    if row["sha256"] and actual_sha256.lower() != str(row["sha256"]).lower():
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="artifact_hash_mismatch",
                    message="stored artifact does not match its recorded SHA-256",
                    category="integrity",
                    retryable=False,
                    details={
                        "expected_sha256": row["sha256"],
                        "actual_sha256": actual_sha256,
                    },
                )
            ],
        )

    destination = None
    if args.destination:
        destination_path = Path(args.destination).expanduser()
        if destination_path.exists() and not args.overwrite:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.HUMAN_REQUIRED,
                [
                    PublicRecordsError(
                        code="destination_exists",
                        message="destination exists; pass --overwrite to replace it",
                        category="filesystem",
                        retryable=False,
                    )
                ],
            )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)
        destination = str(destination_path.resolve())

    record = {
        "canonical_ref": canonical_court_ref(
            row["case_source_id"],
            row["court_id"],
            row["raw_case_number"],
            "document",
            row["native_document_id"],
        ),
        "native_document_id": row["native_document_id"],
        "case_number": row["raw_case_number"],
        "court_id": row["court_id"],
        "sha256": actual_sha256,
        "mime_type": row["mime_type"],
        "bytes": source_path.stat().st_size,
        "download_status": "copied" if destination else "verified_local_artifact",
        "destination": destination,
    }
    if row["source_internal_id"] is not None:
        record["case_source_internal_id"] = row["source_internal_id"]
    return PublicRecordsResult.success(query, [record])


def _court_cache_miss_result(
    query: PublicRecordsQuery,
    coverage: Mapping[str, Any],
    args: argparse.Namespace,
) -> PublicRecordsResult:
    sidecar = coverage["sidecar"]
    scope_covered = bool(sidecar["scope_covered"])
    any_local_data = any(sidecar["row_counts"].values())
    if scope_covered:
        status = ResultStatus.PARTIAL
        code = "local_cache_miss"
    else:
        status = ResultStatus.UNAVAILABLE
        code = "local_scope_not_covered" if any_local_data else "no_coverage"
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=(
                    "no matching public record is cached, and no exact "
                    "source-query zero establishes an empty result"
                ),
                category="local_coverage",
                retryable=False,
                details={
                    "court_db": str(args.court_db),
                    "coverage": coverage,
                    "route_guidance": _court_route_guidance(args),
                },
            )
        ],
    )


def _local_result(args: argparse.Namespace) -> PublicRecordsResult:
    selector = " ".join(args.query.split()).strip()
    query = _query(LOCAL_SOURCE, args.command, selector, args)
    try:
        db = connect_courts(args.court_db)
        try:
            coverage = _court_local_coverage(db, args, selector)
            if args.command == "download":
                result = _download_local(db, selector, args, query)
                if result.status == ResultStatus.NO_RESULTS:
                    result = _restricted_result(db, query, selector, args) or (
                        PublicRecordsResult.success(
                            query,
                            [],
                            warnings=[
                                "Exact source-query zero preserved from "
                                + ", ".join(
                                    f"{item['source_id']} at {item['retrieved_at']}"
                                    for item in coverage["matching_query_evidence"]
                                )
                            ],
                        )
                        if coverage["authoritative_zero"]
                        else _court_cache_miss_result(
                            query,
                            coverage,
                            args,
                        )
                    )
            else:
                records, cursor = LOCAL_HANDLERS[args.command](db, selector, args)
                if records:
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        next_cursor=cursor,
                    )
                else:
                    result = _restricted_result(db, query, selector, args) or (
                        PublicRecordsResult.success(
                            query,
                            [],
                            warnings=[
                                "Exact source-query zero preserved from "
                                + ", ".join(
                                    f"{item['source_id']} at {item['retrieved_at']}"
                                    for item in coverage["matching_query_evidence"]
                                )
                            ],
                        )
                        if coverage["authoritative_zero"]
                        else _court_cache_miss_result(
                            query,
                            coverage,
                            args,
                        )
                    )
        finally:
            db.close()
    except (OSError, sqlite3.Error, TypeError, ValueError) as error:
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
    roles = detail.get("roles") or ["court"]
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


def _external_failure(
    args: argparse.Namespace,
    *,
    detail: Mapping[str, Any] | None,
    decision: Mapping[str, Any] | None,
    code: str,
    message: str,
    status: ResultStatus,
    details: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    source = (
        _catalog_source(detail)
        if detail is not None
        else SourceMetadata(
            source_id=args.source,
            name=args.source,
            source_role="unresolved_court_source",
        )
    )
    query = _query(source, args.command, args.query, args)
    error_details = {
        "access_decision": decision or {},
        "source_guidance": _source_guidance(args.source),
    }
    if details:
        error_details.update(details)
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=message,
                category="source_access",
                retryable=False,
                details=error_details,
            )
        ],
    )


def _external_requested_action(
    args: argparse.Namespace,
    detail: Mapping[str, Any],
) -> dict[str, Any]:
    """Describe the cataloged source operation represented by this route.

    A unified ``case`` lookup does not imply that the source has a direct case
    endpoint. Some portals expose case-number lookup through a case-search
    capability, so the action names that source operation while retaining the
    router operation for auditability.
    """
    supported_capabilities = {
        str(capability.get("name"))
        for capability in detail.get("capabilities", ())
        if capability.get("supported")
    }
    source_operation = args.command
    if args.command == "case" and "search_cases" in supported_capabilities:
        source_operation = "search"

    action = {
        "operation": source_operation,
        "selector": args.query,
        "court_id": args.court_id,
        "hearing_date": getattr(args, "hearing_date", None),
    }
    if source_operation != args.command:
        action["router_operation"] = args.command
    return action


def _live_result(
    args: argparse.Namespace,
) -> tuple[PublicRecordsResult | Mapping[str, Any], bool]:
    """Return one external result and whether a live adapter was invoked."""
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
            _external_failure(
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
        extra: dict[str, Any] = {
            "review": detail.get("latest_access_review"),
            "source_url": detail["source"]["official_url"],
            "terms_url": detail["source"].get("license_or_terms_url"),
            "requested_action": _external_requested_action(args, detail),
        }
        code = str(decision["reason_code"])
        if status is ResultStatus.HUMAN_REQUIRED:
            extra["manual_source_url"] = detail["source"]["official_url"]
        return (
            _external_failure(
                args,
                detail=detail,
                decision=decision,
                code=code,
                message=decision["reason"],
                status=status,
                details=extra,
            ),
            False,
        )

    source_routes = LIVE_ROUTES.get(args.source)
    if source_routes is None:
        guidance = _source_guidance(args.source)
        return (
            _external_failure(
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
            _external_failure(
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
            parameters={"domain": "court", "jurisdiction": args.jurisdiction},
        ),
    )
    try:
        catalog = PublicRecordsCatalog(args.catalog_db)
        rows = catalog.list_sources(domain="court", jurisdiction=args.jurisdiction)
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


def _ojcin_delivery_result(
    args: argparse.Namespace,
) -> tuple[PublicRecordsResult, dict[str, Any]]:
    """Inspect a user-acquired delivery without re-running acquisition."""

    receipt = query_oregon_ojcin_products.inspect_delivery(
        args.product_id,
        Path(args.query),
        delivery_version=args.delivery_version,
        received_at=args.received_at,
        provider_reference=args.provider_reference,
        correction_state=args.correction_state,
        delivery_scope_note=args.delivery_scope_note,
        specification_refs=args.specification_ref,
        case_document_refs=args.case_document_ref,
    )
    product = query_oregon_ojcin_products.PRODUCTS[args.product_id]
    query = PublicRecordsQuery(
        source=product.source_metadata(),
        jurisdiction=query_oregon_ojcin_products.JURISDICTION,
        query=QueryMetadata(
            operation="delivery",
            parameters={
                "product_id": args.product_id,
                "delivery_version": args.delivery_version,
                "delivery_path": str(Path(args.query).expanduser()),
            },
        ),
    )
    record = {
        "canonical_ref": f"OR-OJCIN-DELIVERY:{receipt['receipt_id']}",
        "source_id": args.product_id,
        "record_kind": "court_data_delivery_receipt",
        "delivery_receipt": receipt,
    }
    return PublicRecordsResult.success(query, [record]), receipt


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "sources":
        return _sources_result(args).to_dict()
    if args.command == "delivery":
        result, receipt = _ojcin_delivery_result(args)
        payload = result.to_dict()
        if args.ingest:
            payload["ingest"] = {
                "snapshot": ingest_envelope(
                    payload,
                    court_db=args.court_db,
                ),
                "delivery_receipt": ingest_court_data_delivery_receipt(
                    receipt,
                    court_db=args.court_db,
                ),
            }
        return payload
    if args.source == "local":
        if args.command in {"detail", "discovery", "probe"}:
            raise ValueError(
                f"shared court {args.command} requires an explicit --source"
            )
        if args.ingest:
            raise ValueError("--ingest requires a live source")
        return _local_result(args).to_dict()

    result, adapter_invoked = _live_result(args)
    if not adapter_invoked:
        log_search(
            canonical_json(result.query.to_dict()),
            args.source,
            None,
        )
    payload = dict(result) if isinstance(result, Mapping) else result.to_dict()
    if args.ingest:
        if not adapter_invoked:
            payload["ingest"] = {
                "status": "skipped",
                "reason": "no live adapter envelope was returned",
            }
        elif (
            args.command == "download"
            and args.source != CONNECTICUT_CIVIL_FAMILY_SOURCE_ID
        ):
            payload["ingest"] = {
                "status": "skipped",
                "reason": "download receipts are not case-shaped records",
            }
        else:
            payload["ingest"] = ingest_envelope(
                payload,
                court_db=args.court_db,
            )
    return payload


def _emit(payload: Mapping[str, Any], args: argparse.Namespace) -> None:
    if write_output(
        payload,
        args,
        summary=f"state courts {args.command} ({payload.get('status', 'unknown')})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    records = payload.get("records", [])
    print(
        f"State courts {args.command}: {payload.get('status')} ({len(records)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        label = (
            record.get("raw_case_number")
            or record.get("native_entry_id")
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


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(
        limit_explicit=False,
        minimum_interval_explicit=False,
    )
    parser.add_argument(
        "--source",
        default="local",
        help="Canonical source ID, or local (default)",
    )
    parser.add_argument("--jurisdiction", help="State code or county GEOID filter")
    parser.add_argument("--court-id", help="Canonical local court identifier")
    parser.add_argument("--case-type")
    parser.add_argument("--after", help="Filed on/after ISO date")
    parser.add_argument("--before", help="Filed on/before ISO date")
    parser.add_argument(
        "--search-scope",
        choices=tuple(query_texas_appellate.SEARCH_SCOPE_FIELDS),
        help="Source-native search field when the selected adapter supports it",
    )
    parser.add_argument(
        "--search-field",
        help="Source-native search field exposed by the selected adapter",
    )
    parser.add_argument("--style-other")
    parser.add_argument("--originating-coa")
    parser.add_argument("--county")
    parser.add_argument("--trial-court")
    parser.add_argument(
        "--first-name",
        help=(
            "Source-native first-name selector; San Mateo MIDX treats the "
            "positional query as the last name"
        ),
    )
    parser.add_argument(
        "--middle-name",
        help="Source-native middle name or initial when the index exposes it",
    )
    parser.add_argument(
        "--name-suffix",
        help="Source-native person-name suffix when the index exposes it",
    )
    parser.add_argument(
        "--party-type",
        help="Source-native party-role filter when available",
    )
    parser.add_argument(
        "--case-year",
        type=int,
        help="Source-native four-digit case-year filter",
    )
    parser.add_argument(
        "--case-status",
        help="Source-native case-status filter when available",
    )
    parser.add_argument(
        "--court-category",
        help="Source-native court division or category when available",
    )
    parser.add_argument("--date-of-birth")
    parser.add_argument("--drivers-license")
    parser.add_argument("--plate-state")
    parser.add_argument("--violation-number")
    parser.add_argument(
        "--entity-kind",
        choices=("person", "organization"),
        default="person",
        help="Select a source-native person or organization name route",
    )
    parser.add_argument(
        "--partial",
        action="store_true",
        help="Use a source-native partial-name mode when available",
    )
    parser.add_argument(
        "--phonetic",
        action="store_true",
        help="Use a source-native phonetic-name mode when available",
    )
    parser.add_argument("--exclude-inactive", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        action=_ExplicitLimitAction,
    )
    parser.add_argument(
        "--courthouse",
        help="Source-native courthouse code or exact offered option",
    )
    parser.add_argument("--cursor", help="Continuation cursor")
    parser.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    parser.add_argument("--court-db", default=str(DEFAULT_COURT_DB))
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Normalize a live result into the court sidecar",
    )
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional user-selected record ceiling for live source queries",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=0.25,
        action=_ExplicitMinimumIntervalAction,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query normalized and catalogued state/local court records"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sources = sub.add_parser("sources", help="List catalogued court sources")
    sources.add_argument("--jurisdiction", help="State code or county GEOID")
    sources.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    add_output_args(sources)

    discovery = sub.add_parser(
        "discovery",
        help="Discover a live source's published routes and capabilities",
    )
    discovery.add_argument("query", nargs="?", default="*")
    _add_common(discovery)

    probe = sub.add_parser(
        "probe",
        help="Run a live source's bounded contract probe",
    )
    probe.add_argument("query", nargs="?", default="*")
    _add_common(probe)

    detail = sub.add_parser(
        "detail",
        help="Read one exact source-native non-case record",
    )
    detail.add_argument("query", metavar="NATIVE_RECORD_ID")
    _add_common(detail)

    products = sub.add_parser(
        "products",
        help="List Oregon statewide court-data products as distinct sources",
    )
    products.add_argument("query", nargs="?", default="*")
    products.add_argument(
        "--product-id",
        choices=sorted(OREGON_OJCIN_PRODUCT_SOURCE_IDS),
    )
    _add_common(products)
    products.set_defaults(source=OREGON_OJCIN_PRODUCT_DIRECTORY_SOURCE_ID)

    handoff = sub.add_parser(
        "handoff",
        help="Return the acquisition handoff for one Oregon court-data product",
    )
    handoff.add_argument("query", metavar="PRODUCT_ID")
    handoff.add_argument(
        "--product-id",
        choices=sorted(OREGON_OJCIN_PRODUCT_SOURCE_IDS),
    )
    _add_common(handoff)
    handoff.set_defaults(source=OREGON_OJCIN_PRODUCT_DIRECTORY_SOURCE_ID)

    delivery = sub.add_parser(
        "delivery",
        help="Fingerprint an acquired Oregon court-data delivery",
    )
    delivery.add_argument("query", metavar="DELIVERY_PATH")
    delivery.add_argument(
        "--product-id",
        required=True,
        choices=sorted(OREGON_OJCIN_PRODUCT_SOURCE_IDS),
    )
    delivery.add_argument("--delivery-version", required=True)
    delivery.add_argument("--received-at")
    delivery.add_argument("--provider-reference")
    delivery.add_argument(
        "--correction-state",
        default="not_stated_in_delivery",
    )
    delivery.add_argument("--delivery-scope-note")
    delivery.add_argument("--specification-ref", action="append", default=[])
    delivery.add_argument("--case-document-ref", action="append", default=[])
    _add_common(delivery)
    delivery.set_defaults(source=OREGON_OJCIN_PRODUCT_DIRECTORY_SOURCE_ID)

    search = sub.add_parser("search", help="Search cases, parties, and attorneys")
    search.add_argument("query")
    _add_common(search)

    case = sub.add_parser("case", help="Look up a source-native case number")
    case.add_argument("query", metavar="CASE_NUMBER")
    _add_common(case)

    docket = sub.add_parser("docket", help="List public docket entries for a case")
    docket.add_argument("query", metavar="CASE_NUMBER")
    _add_common(docket)

    notes = sub.add_parser(
        "notes",
        help="List public source-native probate notes for a case",
    )
    notes.add_argument("query", metavar="CASE_NUMBER")
    notes.add_argument(
        "--view",
        choices=("future", "past", "all"),
        default="all",
    )
    notes.add_argument(
        "--hearing-date",
        help="Exact ISO hearing date when the selected notes source supports it",
    )
    _add_common(notes)

    calendar = sub.add_parser(
        "calendar",
        help="List public source-native calendar hearings",
    )
    calendar.add_argument("query", metavar="CASE_OR_CALENDAR_SELECTOR")
    calendar.add_argument(
        "--hearing-date",
        help="Exact ISO date for a source-native daily calendar",
    )
    _add_common(calendar)

    claims = sub.add_parser(
        "claims",
        help="List normalized claim records or source-native claim stubs for a case",
    )
    claims.add_argument("query", metavar="CASE_NUMBER")
    _add_common(claims)

    documents = sub.add_parser(
        "documents", help="List public document metadata for a case"
    )
    documents.add_argument("query", metavar="CASE_NUMBER")
    documents.add_argument("--document-type")
    documents.add_argument(
        "--docket-entry-uuid",
        help="Source-native docket entry UUID for routes that require one",
    )
    _add_common(documents)

    download = sub.add_parser(
        "download", help="Verify or copy a public document from local storage"
    )
    download.add_argument("query", metavar="NATIVE_DOCUMENT_ID")
    download.add_argument("--case-number")
    download.add_argument(
        "--case-uuid",
        help="Source-native case UUID needed by live document routes",
    )
    download.add_argument(
        "--page-number",
        type=int,
        help="Source-native page number for page-oriented document routes",
    )
    download.add_argument(
        "--document-section",
        choices=("DocketItems", "DecisionItems"),
        help="Source-native document section when the selected route requires it",
    )
    download.add_argument("--destination")
    download.add_argument("--overwrite", action="store_true")
    _add_common(download)
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
    if hasattr(args, "query") and not args.query.strip():
        parser.error("query must not be blank")
    try:
        payload = execute(args)
    except ValueError as error:
        parser.error(str(error))
        return
    _emit(payload, args)


if __name__ == "__main__":
    main()
