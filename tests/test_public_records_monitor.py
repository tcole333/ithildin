from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest
import yaml

from tools import (
    public_records_monitor,
    query_dc_opinions,
    query_dc_superior_calendar,
    query_fresno_superior_court,
    query_los_angeles_court,
    query_los_angeles_name_index,
    query_los_angeles_ttc,
    query_new_jersey_parcels,
    query_new_jersey_sr1a,
    query_orange_county_court,
    query_palm_beach_official_records,
    query_philadelphia_property,
    query_qld_ecourts,
    query_riverside_court,
    query_oregon_ojcin_products,
    query_oregon_smart_search,
    query_rrc_bulk,
    query_texas_appellate,
    query_wisconsin_parcels,
)
from tools.public_records_catalog import CatalogError, PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult, ResultStatus
from tools.public_records_monitor import (
    HANDLER_REGISTRY,
    ProbeContext,
    ProbeHandlerSpec,
    ProbeObservation,
    compare_probes,
    diff_history,
    history,
    plan_sources,
    probe_arlington_property,
    probe_bexar_historical_courts,
    probe_delaware_firstmap,
    probe_deschutes_cdd_weblink,
    probe_deschutes_dial,
    probe_deschutes_property,
    probe_denver_county_court,
    probe_denver_delinquent_tax,
    probe_denver_foreclosures,
    probe_denver_property,
    probe_dc_calendar_component,
    probe_dc_opinions,
    probe_eugene_municipal_court_component,
    probe_florida_acis,
    probe_fresno_court_component,
    probe_colorado_court_data,
    probe_colorado_judicial,
    probe_colorado_opinion_releases,
    probe_colorado_opinions_archive,
    probe_govos_recorder,
    probe_los_angeles_civil,
    probe_los_angeles_name_index,
    probe_los_angeles_assessor_ain,
    probe_los_angeles_ttc_payment,
    probe_los_angeles_ttc_sale,
    probe_los_angeles_probate,
    probe_ny_column,
    probe_ny_law_reports,
    probe_orange_hearing_calendar,
    probe_orange_county_court_component,
    probe_philadelphia_property_component,
    probe_qld_ecourts,
    probe_riverside_court_component,
    probe_oregon_appellate,
    probe_oregon_appellate_calendar_component,
    probe_oregon_court_calendar,
    probe_oregon_court_directory_component,
    probe_oregon_court_document_component,
    probe_oregon_helion_property_component,
    probe_oregon_helion_recorder_component,
    probe_oregon_county_assessor_component,
    probe_oregon_jackson_accela_component,
    probe_oregon_jackson_property_event_component,
    probe_oregon_ojcin_public_directory,
    probe_oregon_benton_property_component,
    probe_oregon_county_property_component,
    probe_oregon_lincoln_propertyweb,
    probe_oregon_lincoln_taxlots,
    probe_oregon_lane_marion_property_component,
    probe_oregon_multnomah_sail_component,
    probe_oregon_smart_search,
    probe_oregon_tax_foreclosure_component,
    probe_oregon_taxlot_component,
    probe_oregon_washington_case_permit_component,
    probe_oregon_washington_property_component,
    probe_washington_parcel_companion,
    probe_washington_parcel_lineage,
    probe_washington_parcel_representation,
    probe_orleans_property,
    probe_palm_beach_official_records,
    probe_palm_beach_courts,
    probe_pima_courts,
    probe_reeves_records,
    probe_san_mateo_midx,
    probe_new_jersey_sr1a,
    probe_statewide_parcel_source,
    probe_tax_court_dawson,
    probe_texas_rrc_release,
    probe_texas_tames,
    probe_vicourts,
    record_observation,
    registered_handlers,
    run_sources,
)
from tools.seed_public_records_catalog import DEFAULT_CONFIG_PATH


NOW = "2026-07-28T12:00:00Z"
NC_SOURCE = "us-nc-onemap-parcels"
MA_SOURCE = "us-ma-massgis-parcels"
BEXAR_SOURCE = "us-tx-bexar-bcad-property"
DENVER_PROPERTY_SOURCE = "us-co-denver-parcels"
DENVER_FORECLOSURE_SOURCE = "us-co-denver-public-trustee-gts"
DENVER_DELINQUENT_TAX_SOURCE = "us-co-denver-delinquent-real-property-tax-list"
COLORADO_JUDICIAL_SOURCE = "us-co-judicial-docket-search"
COLORADO_COURT_DATA_SOURCE = "us-co-judicial-data-reports"
COLORADO_OPINIONS_SOURCE = "us-co-appellate-case-law-search"
COLORADO_OPINION_RELEASES_SOURCE = "us-co-judicial-appellate-opinion-releases"
DC_OPINIONS_SOURCE = "us-dc-court-of-appeals-opinions-mojs"
DENVER_COUNTY_COURT_SOURCE = "us-co-denver-county-court-public-docket"
DELAWARE_FIRSTMAP_SOURCE = "us-de-firstmap-parcels"
DESCHUTES_PROPERTY_SOURCE = "us-or-deschutes-county-taxlots"
DESCHUTES_DIAL_SOURCE = "us-or-deschutes-dial-property"
DESCHUTES_CDD_WEBLINK_SOURCE = "us-or-deschutes-cdd-weblink"
ARLINGTON_PROPERTY_SOURCE = "us-va-arlington-property-map"
BEXAR_HISTORICAL_SOURCE = "us-tx-bexar-district-historical-cases"
TEXAS_TAMES_SOURCE = "us-tx-appellate-tames"
REEVES_RECORDS_SOURCE = "us-tx-reeves-county-clerk-official-records"
GOVOS_RECORDER_SOURCE = "us-pa-berks-recorder-publicsearch"
TEXAS_RRC_P4_SOURCE = "us-tx-rrc-p4-bulk"
TEXAS_RRC_P5_SOURCE = "us-tx-rrc-p5-bulk"
TEXAS_RRC_WELLBORE_SOURCE = "us-tx-rrc-wellbore-bulk"
MIAMI_PA_SOURCE = "us-fl-miami-dade-property-appraiser"
MIAMI_RECORDER_PUBLIC_SOURCE = "us-fl-miami-dade-official-records-public"
FLORIDA_ACIS_SOURCE = "us-fl-acis"
ORANGE_CALENDAR_SOURCE = "us-fl-orange-county-hearing-calendar"
LOS_ANGELES_CIVIL_SOURCE = "us-ca-los-angeles-superior-civil"
LOS_ANGELES_ASSESSOR_SOURCE = "us-ca-los-angeles-county-assessor-parcels"
LOS_ANGELES_TTC_PAYMENT_SOURCE = "us-ca-los-angeles-county-ttc-payment-history"
LOS_ANGELES_TTC_SALE_SOURCE = "us-ca-los-angeles-county-ttc-tax-sale"
LOS_ANGELES_PROBATE_SOURCE = "us-ca-los-angeles-superior-probate"
ORLEANS_SOURCE = "us-la-orleans-property-viewer"
PALM_BEACH_SOURCE = "us-fl-palm-beach-ecaseview"
PIMA_SOURCE = "us-az-pima-superior-agave"
SAN_MATEO_SOURCE = "us-ca-san-mateo-midx"
NY_LAW_REPORTS_SOURCE = "us-ny-law-reporting-bureau"
NY_COLUMN_SOURCE = "us-ny-public-notices-column"
TAX_COURT_SOURCE = "us-tax-court-dawson"
VICOURTS_SOURCE = "us-vi-c-track"
PA_UJS_SOURCE = "us-pa-ujs-public-dockets"
PA_OPINIONS_SOURCE = "us-pa-appellate-opinions-postings"
DELAWARE_COURTCONNECT_SOURCE = "us-de-courtconnect"
DELAWARE_OPINIONS_SOURCE = "us-de-opinions-orders"
HARRIS_RECORDER_SOURCE = "us-tx-harris-clerk-real-property"
HARRIS_FORECLOSURE_SOURCE = "us-tx-harris-clerk-foreclosures"
HARRIS_COURT_BULK_SOURCE = "us-tx-harris-district-clerk-public-datasets"
OREGON_PORTLAND_TAXLOT_SOURCE = "us-or-portland-regional-taxlots"
OREGON_APPELLATE_SOURCE = "us-or-appellate-record-search"
OREGON_COURT_CALENDAR_SOURCE = "us-or-circuit-tax-court-calendars"
OREGON_SMART_SEARCH_SOURCE = "us-or-ojd-smart-search"
OREGON_OJCIN_SOURCE = "us-or-ojd-statewide-court-data-products"
EUGENE_MUNICIPAL_COURT_SOURCE = "us-or-eugene-municipal-record-search"
OREGON_BENTON_TAXLOT_SOURCE = "us-or-benton-county-taxlot-owners"
OREGON_BENTON_BULK_SOURCE = "us-or-benton-county-assessment-bulk"
OREGON_BENTON_MAP_SOURCE = "us-or-benton-county-assessment-maps"
OREGON_LINCOLN_PROPERTYWEB_SOURCE = "us-or-lincoln-propertyweb"
OREGON_LINCOLN_TAXLOT_SOURCE = "us-or-lincoln-county-taxlots-wfs"
OREGON_COA_CALENDAR_SOURCE = "us-or-court-of-appeals-calendar"
OREGON_SUPREME_CALENDAR_SOURCE = "us-or-supreme-court-calendar"
OREGON_STATE_COURT_DIRECTORY_SOURCE = "us-or-state-court-directory"
OREGON_MORROW_HELION_PROPERTY_SOURCE = "us-or-morrow-helion-property"
OREGON_WASCO_HELION_SOURCE = "us-or-wasco-helion-recorder"
OREGON_JACKSON_ASSESSOR_SOURCE = "us-or-jackson-county-assessor-taxlots"
OREGON_LINN_ASSESSOR_SOURCE = "us-or-linn-county-assessor-taxlots"
OREGON_JACKSON_BUILDING_EVENT_SOURCE = "us-or-jackson-county-building-permits"
OREGON_JACKSON_ACCELA_BUILDING_SOURCE = "us-or-jackson-county-accela-building-details"
OREGON_TILLAMOOK_TAX_FORECLOSURE_SOURCE = "us-or-tillamook-tax-foreclosure-publications"
OREGON_SUPREME_OPINIONS_SOURCE = "us-or-law-library-supreme-opinions"
OTHER_SOURCE = "us-tx-local-parcels"
BLOCKED_SOURCE = "us-ny-local-courts"


def manifest(
    source_id: str,
    *,
    geoid: str,
    access_class: str = "A",
    disposition: str = "allowed",
) -> dict:
    return {
        "source_id": source_id,
        "name": source_id,
        "domain": "court" if "courts" in source_id else "property",
        "roles": ["assessment"],
        "authority": "Test public authority",
        "operator": "Test public operator",
        "jurisdiction_geoids": [geoid],
        "official_url": f"https://example.test/{source_id}",
        "platform_family": "documented_rest",
        "access_class": access_class,
        "automation_disposition": disposition,
        "authentication": "none",
        "fees": "none",
        "redistribution": "source_terms_apply",
        "protected_record_policy": "source_managed",
        "coverage_start": "2020",
        "update_cadence": "source_managed",
        "stable_keys": ["native_id"],
        "adapter_family": "test",
        "adapter_version": 1,
        "last_verified_at": NOW,
        "source_status": "active",
        "capabilities": ["probe"],
    }


def add_source(
    catalog: PublicRecordsCatalog,
    source_id: str,
    *,
    geoid: str,
    access_class: str = "A",
    disposition: str = "allowed",
) -> None:
    catalog.register_manifest(
        manifest(
            source_id,
            geoid=geoid,
            access_class=access_class,
            disposition=disposition,
        ),
        submitted_by="test",
        submitted_at=NOW,
    )
    catalog.evaluate_access(
        source_id,
        access_class=access_class,
        automation_disposition=disposition,
        reviewed_by="test",
        reviewed_at=NOW,
        review_basis="Test catalog decision",
    )


@pytest.fixture
def catalog(tmp_path: Path) -> PublicRecordsCatalog:
    value = PublicRecordsCatalog(tmp_path / "catalog.db")
    add_source(value, NC_SOURCE, geoid="37")
    add_source(value, MA_SOURCE, geoid="25")
    add_source(value, OTHER_SOURCE, geoid="48")
    add_source(
        value,
        BLOCKED_SOURCE,
        geoid="36",
        access_class="C",
        disposition="prohibited",
    )
    return value


def handler_spec(
    source_id: str,
    handler: Callable,
) -> ProbeHandlerSpec:
    return ProbeHandlerSpec(
        source_id=source_id,
        capability="probe",
        endpoint=f"https://example.test/{source_id}/probe",
        observation="Test sentinel",
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=handler,
    )


def ok_observation(
    *,
    schema: str = "1" * 64,
    artifact: str | None = None,
    status: str = "ok",
) -> ProbeObservation:
    return ProbeObservation(
        status=status,
        endpoint="https://example.test/probe",
        http_status=200,
        schema_sha256=schema,
        artifact_sha256=artifact,
        result_count=0 if status == "no_results" else 1,
        details={"fixture": True},
    )


def test_handler_registry_is_centralized_and_visible():
    config = yaml.safe_load(
        DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    )
    sources = config["sources"]
    catalog_source_ids = {
        source["source_id"] for source in sources
    }
    declared_monitor_source_ids = {
        source["source_id"]
        for source in sources
        for capability in source.get("capabilities", [])
        if isinstance(capability, dict)
        and isinstance(capability.get("details"), dict)
        and capability["details"].get("adapter_tool")
        == "public_records_monitor.py"
    }
    registry_source_ids = set(HANDLER_REGISTRY)

    assert declared_monitor_source_ids <= registry_source_ids
    assert registry_source_ids <= catalog_source_ids
    assert all(
        source_id == spec.source_id
        for source_id, spec in HANDLER_REGISTRY.items()
    )
    visible = registered_handlers()
    assert [item["source_id"] for item in visible] == sorted(HANDLER_REGISTRY)
    florida_acis = next(
        item for item in visible if item["source_id"] == FLORIDA_ACIS_SOURCE
    )
    assert florida_acis["capability"] == "probe_source"
    assert florida_acis["expected_requests"] == 4
    assert florida_acis["sentinel_record_count"] == 1
    deschutes_dial = next(
        item for item in visible if item["source_id"] == DESCHUTES_DIAL_SOURCE
    )
    assert deschutes_dial["capability"] == "probe_source"
    assert deschutes_dial["expected_requests"] == 15
    assert deschutes_dial["sentinel_record_count"] == 1
    deschutes_cdd = next(
        item for item in visible if item["source_id"] == DESCHUTES_CDD_WEBLINK_SOURCE
    )
    assert deschutes_cdd["capability"] == "probe_source"
    assert deschutes_cdd["expected_requests"] == 6
    assert deschutes_cdd["sentinel_record_count"] == 2
    oregon_calendar = next(
        item for item in visible if item["source_id"] == OREGON_COURT_CALENDAR_SOURCE
    )
    assert oregon_calendar["capability"] == "probe_source"
    assert oregon_calendar["expected_requests"] == 3
    assert oregon_calendar["sentinel_record_count"] == 1
    smart_search = next(
        item for item in visible if item["source_id"] == OREGON_SMART_SEARCH_SOURCE
    )
    assert smart_search["capability"] == "probe_source"
    assert smart_search["expected_requests"] == 1
    assert smart_search["sentinel_record_count"] == 1
    ojcin = next(item for item in visible if item["source_id"] == OREGON_OJCIN_SOURCE)
    assert ojcin["capability"] == "probe_source"
    assert ojcin["expected_requests"] == 13
    assert ojcin["sentinel_record_count"] == 13
    assert not set(query_oregon_ojcin_products.PRODUCTS).intersection(HANDLER_REGISTRY)
    bexar = next(item for item in visible if item["source_id"] == BEXAR_SOURCE)
    assert bexar["expected_requests"] == 1
    rrc = next(
        item for item in visible if item["source_id"] == TEXAS_RRC_WELLBORE_SOURCE
    )
    assert rrc["expected_requests"] == 1
    assert rrc["sample_bytes"] is None
    assert bexar["sentinel_record_count"] == 1
    bexar_historical = next(
        item for item in visible if item["source_id"] == BEXAR_HISTORICAL_SOURCE
    )
    assert bexar_historical["capability"] == "probe_source"
    assert bexar_historical["expected_requests"] == 3
    assert bexar_historical["sentinel_record_count"] == 1
    texas_tames = next(
        item for item in visible if item["source_id"] == TEXAS_TAMES_SOURCE
    )
    assert texas_tames["capability"] == "probe_source"
    assert texas_tames["expected_requests"] == 3
    assert texas_tames["sentinel_record_count"] == 1
    reeves = next(
        item for item in visible if item["source_id"] == REEVES_RECORDS_SOURCE
    )
    assert reeves["capability"] == "probe_source"
    assert reeves["expected_requests"] == 3
    assert reeves["sentinel_record_count"] == 1
    govos = next(item for item in visible if item["source_id"] == GOVOS_RECORDER_SOURCE)
    assert govos["capability"] == "probe_source"
    assert govos["expected_requests"] == 6
    assert govos["sentinel_record_count"] == 1
    harris = next(
        item for item in visible if item["source_id"] == HARRIS_RECORDER_SOURCE
    )
    assert harris["capability"] == "probe_source"
    assert harris["expected_requests"] == 5
    assert harris["sentinel_record_count"] == 3
    foreclosure = next(
        item for item in visible if item["source_id"] == HARRIS_FORECLOSURE_SOURCE
    )
    assert foreclosure["capability"] == "probe_source"
    assert foreclosure["expected_requests"] == 3
    assert foreclosure["sentinel_record_count"] == 2
    harris_bulk = next(
        item for item in visible if item["source_id"] == HARRIS_COURT_BULK_SOURCE
    )
    assert harris_bulk["capability"] == "probe_source"
    assert harris_bulk["expected_requests"] == 2
    assert harris_bulk["sentinel_record_count"] == 1
    assert harris_bulk["sample_bytes"] == 4096
    pa_ujs = next(item for item in visible if item["source_id"] == PA_UJS_SOURCE)
    assert pa_ujs["capability"] == "probe_source"
    assert pa_ujs["expected_requests"] == 4
    assert pa_ujs["sentinel_record_count"] == 2
    pa_opinions = next(
        item for item in visible if item["source_id"] == PA_OPINIONS_SOURCE
    )
    assert pa_opinions["capability"] == "probe_source"
    assert pa_opinions["expected_requests"] == 2
    assert pa_opinions["sentinel_record_count"] == 1
    delaware = next(
        item for item in visible if item["source_id"] == DELAWARE_COURTCONNECT_SOURCE
    )
    assert delaware["capability"] == "probe_source"
    assert delaware["expected_requests"] == 4
    assert delaware["sentinel_record_count"] == 2
    delaware_opinions = next(
        item for item in visible if item["source_id"] == DELAWARE_OPINIONS_SOURCE
    )
    assert delaware_opinions["capability"] == "probe_source"
    assert delaware_opinions["expected_requests"] == 2
    assert delaware_opinions["sentinel_record_count"] == 1
    miami_pa = next(item for item in visible if item["source_id"] == MIAMI_PA_SOURCE)
    assert miami_pa["expected_requests"] == 2
    miami_recorder = next(
        item for item in visible if item["source_id"] == MIAMI_RECORDER_PUBLIC_SOURCE
    )
    assert miami_recorder["expected_requests"] == 1
    massgis = next(item for item in visible if item["source_id"] == MA_SOURCE)
    assert massgis["sample_bytes"] == 4096
    assert massgis["expected_requests"] == 3
    orleans = next(item for item in visible if item["source_id"] == ORLEANS_SOURCE)
    assert orleans["capability"] == "fetch_account"
    assert orleans["expected_requests"] == 4
    assert orleans["sentinel_record_count"] == 1
    vicourts = next(item for item in visible if item["source_id"] == VICOURTS_SOURCE)
    assert vicourts["capability"] == "probe_source"
    assert vicourts["expected_requests"] == 6
    assert vicourts["sentinel_record_count"] == 1
    orange = next(
        item for item in visible if item["source_id"] == ORANGE_CALENDAR_SOURCE
    )
    assert orange["capability"] == "probe_source"
    assert orange["expected_requests"] == 2
    los_angeles = next(
        item for item in visible if item["source_id"] == LOS_ANGELES_PROBATE_SOURCE
    )
    assert los_angeles["capability"] == "probe_source"
    assert los_angeles["expected_requests"] == 5
    assert los_angeles["sentinel_record_count"] == 1
    pima = next(item for item in visible if item["source_id"] == PIMA_SOURCE)
    assert pima["capability"] == "probe_source"
    assert pima["expected_requests"] == 2
    san_mateo = next(item for item in visible if item["source_id"] == SAN_MATEO_SOURCE)
    assert san_mateo["capability"] == "probe_source"
    assert san_mateo["expected_requests"] == 2
    tax_court = next(item for item in visible if item["source_id"] == TAX_COURT_SOURCE)
    assert tax_court["capability"] == "probe_source"
    assert tax_court["expected_requests"] == 2
    assert tax_court["sentinel_record_count"] == 2
    ny_law_reports = next(
        item for item in visible if item["source_id"] == NY_LAW_REPORTS_SOURCE
    )
    assert ny_law_reports["capability"] == "probe_source"
    assert ny_law_reports["expected_requests"] == 7
    assert ny_law_reports["sentinel_record_count"] == 7
    ny_column = next(item for item in visible if item["source_id"] == NY_COLUMN_SOURCE)
    assert ny_column["capability"] == "probe_source"
    assert ny_column["expected_requests"] == 2
    assert ny_column["sentinel_record_count"] == 2
    palm_beach = next(
        item for item in visible if item["source_id"] == PALM_BEACH_SOURCE
    )
    assert palm_beach["capability"] == "probe_source"
    assert palm_beach["expected_requests"] == 1


def test_harris_court_bulk_probe_fingerprints_schema_workbook(
    monkeypatch: pytest.MonkeyPatch,
):
    catalog_state = {
        "artifact_count": 117,
        "section_counts": {"Civil": 97, "Criminal": 20},
        "family_counts": {"schema_reference": 2},
        "publication_dates": {},
        "artifact_fingerprint": "a" * 64,
    }

    class FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class FakeClient:
        instances = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.session = FakeSession()
            self.instances.append(self)

    monkeypatch.setattr(
        public_records_monitor,
        "HarrisCourtBulkClient",
        FakeClient,
    )
    monkeypatch.setattr(
        public_records_monitor,
        "run_harris_court_bulk_sentinel",
        lambda _client: {
            "status": "ok",
            "catalog_url": "https://example.test/harris-bulk",
            "sentinel": {
                "native_locator": (r"Civil\2024-08-15 FIELD_CODES.xlsx"),
                "filename": "FIELD_CODES.xlsx",
                "published_date": "2024-08-15",
                "format": "xlsx",
                "sample_bytes": 4096,
                "signature_hex": "504b0304",
                "response_filename": ("2024-08-15 FIELD_CODES.xlsx"),
            },
            "catalog": {
                **catalog_state,
            },
        },
    )

    context = ProbeContext(
        source_id=HARRIS_COURT_BULK_SOURCE,
        catalog_decision={"limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=4096,
    )
    observation = public_records_monitor.probe_harris_court_bulk(context)
    catalog_state.update(
        artifact_count=118,
        section_counts={"Civil": 98, "Criminal": 20},
        artifact_fingerprint="b" * 64,
    )
    refreshed = public_records_monitor.probe_harris_court_bulk(context)
    drift = compare_probes(
        observation.to_dict(),
        refreshed.to_dict(),
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.schema_sha256 == refreshed.schema_sha256
    assert observation.artifact_sha256 == refreshed.artifact_sha256
    assert observation.details["rolling_observation"]["sentinel"][
        "signature_hex"
    ] == "504b0304"
    assert observation.details["rolling_observation"]["catalog"][
        "artifact_count"
    ] == 117
    assert refreshed.details["rolling_observation"]["catalog"][
        "artifact_count"
    ] == 118
    assert drift["drift_detected"] is False
    assert all(client.session.closed for client in FakeClient.instances)


class _BexarHistoricalProbeClient:
    def __init__(self, *_args, **_kwargs):
        self.calls = []
        self.closed = False

    def bootstrap(self):
        self.calls.append(("bootstrap", {}))
        return type(
            "Bootstrap",
            (),
            {
                "state": {
                    "configuration": {
                        "tenantId": "48029dc",
                        "departments": [{"code": "HC"}],
                    }
                },
                "tenant_id": "48029dc",
                "department_codes": ("HC",),
                "department_date_ranges": {
                    "HC": {"min": "18000101", "max": "19190917"}
                },
            },
        )()

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return type(
            "Page",
            (),
            {
                "records": (
                    {
                        "id": 229799154,
                        "docId": 229799154,
                        "docNumber": "14350",
                        "rsId": "BexarTXCivilCaseFiles-014350",
                    },
                ),
                "total_count": 463,
                "offset": 0,
                "limit": 1,
                "response_type": ("@kofile/FETCH_DOCUMENTS_FULFILLED/v6"),
            },
        )()

    def fetch_document(self, doc_id):
        self.calls.append(("fetch_document", {"doc_id": doc_id}))
        return {
            "id": doc_id,
            "docNumber": "14350",
            "rsId": "BexarTXCivilCaseFiles-014350",
            "recordedDate": "9/17/1919",
            "metadataVersion": 4,
            "docVersion": 5,
            "parties": [
                {
                    "partyTypeCode": "DT",
                    "name": "EXAMPLE PLAINTIFF",
                }
            ],
        }

    def close(self):
        self.closed = True


def test_bexar_historical_probe_covers_bootstrap_search_and_detail(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _BexarHistoricalProbeClient()
    monkeypatch.setattr(
        public_records_monitor,
        "KofilePublicSearchClient",
        lambda *_args, **_kwargs: client,
    )

    observation = probe_bexar_historical_courts(
        ProbeContext(
            source_id=BEXAR_HISTORICAL_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["tenant_id"] == "48029dc"
    assert observation.details["doc_id"] == 229799154
    assert observation.details["rs_id"] == ("BexarTXCivilCaseFiles-014350")
    assert observation.details["probe_range"] == "19190101,19191231"
    assert observation.details["requests_made"] == 3
    assert [name for name, _details in client.calls] == [
        "bootstrap",
        "search",
        "fetch_document",
    ]
    assert client.calls[1][1]["limit"] == 1
    assert client.closed is True


def test_govos_recorder_probe_rejects_transport_count_drift(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _GovOSRecorderProbeClient()
    client.request_count = 5
    tenant = public_records_monitor.GOVOS_RECORDER_TENANTS[
        GOVOS_RECORDER_SOURCE
    ]
    monkeypatch.setitem(
        public_records_monitor.GOVOS_RECORDER_TENANTS,
        GOVOS_RECORDER_SOURCE,
        replace(
            tenant,
            probe_page_sha256=hashlib.sha256(client.page_content).hexdigest(),
        ),
    )
    monkeypatch.setattr(
        public_records_monitor,
        "ReevesRecordsClient",
        lambda *_args, **_kwargs: client,
    )

    with pytest.raises(
        public_records_monitor.KofileSourceChangedError,
        match="probe transport count changed",
    ) as raised:
        probe_govos_recorder(
            ProbeContext(
                source_id=GOVOS_RECORDER_SOURCE,
                catalog_decision={"limits": {}},
                timeout=5,
                max_attempts=1,
                sample_bytes=None,
            )
        )

    assert raised.value.code == "probe_request_contract_changed"
    assert raised.value.details == {
        "expected_requests": 6,
        "observed_requests": 5,
    }
    assert client.closed is True


def test_denver_property_probe_uses_exact_schedule_sentinel(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    class FakeArcGISClient:
        query_url = "https://example.test/denver/query"

        def __init__(self, layer_url, **kwargs):
            calls.append(("init", layer_url, kwargs))

        def query(self, **kwargs):
            calls.append(("query", kwargs))
            return SimpleNamespace(
                records=[
                    {
                        "attributes": {
                            "OBJECTID": 991475,
                            "SCHEDNUM": "0017103008000",
                            "PARCELNUM": "008",
                            "SYSTEM_START_DATE": 1_291_766_400_000,
                            "RECEPTION_NUM": "2026006375",
                        }
                    }
                ],
                schema_fingerprint="d" * 64,
                pages_fetched=1,
                requests_made=1,
                next_cursor=None,
                warnings=(),
            )

    monkeypatch.setattr(
        public_records_monitor,
        "ArcGISRESTClient",
        FakeArcGISClient,
    )

    observation = probe_denver_property(
        ProbeContext(
            source_id=DENVER_PROPERTY_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert observation.schema_sha256 == "d" * 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["sentinel_schedule_number"] == ("0017103008000")
    assert calls[1][1]["where"] == "SCHEDNUM='0017103008000'"
    assert calls[1][1]["requested_limit"] == 1
    assert calls[1][1]["return_geometry"] is False


def test_delaware_firstmap_probe_preserves_both_layer_schemas(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "canonical_ref": (
                        "PROPERTY:us-de-firstmap-parcels/10003/parcel/1001300033"
                    ),
                    "source_feature_ids": (
                        "polygon:OBJECTID:18356825",
                        "centroid:OBJECTID:18352054",
                    ),
                    "probe": {
                        "sentinel": {
                            "county": "New Castle",
                            "pin": "1001300033",
                        },
                        "polygon_feature_count": 1,
                        "centroid_feature_count": 1,
                        "schema_fingerprints": {
                            "polygon": "p" * 64,
                            "centroid": "c" * 64,
                        },
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_delaware_firstmap",
        fake_execute,
    )

    observation = probe_delaware_firstmap(
        ProbeContext(
            source_id=DELAWARE_FIRSTMAP_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["polygon_feature_count"] == 1
    assert observation.details["centroid_feature_count"] == 1
    assert calls[0][0].command == "probe"
    assert calls[0][1]["access_decision"]["limits"] == {}
    assert calls[0][1]["log_results"] is False


def test_denver_county_court_probe_preserves_live_table_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_health_check",
                    "courtroom_count": 35,
                    "courtrooms": ["3A", "3B"],
                    "table_columns": ["Case No", "AB/TK", "Defendant"],
                    "parsed_row_count": 14,
                    "captcha_enabled": False,
                    "request_parameters": {
                        "SelectedCourtroom": "3A",
                        "Court_Date": "07/29/2026",
                        "token": "transient-value",
                    },
                    "schema_fingerprint": "c" * 64,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_denver_county_court",
        fake_execute,
    )

    observation = probe_denver_county_court(
        ProbeContext(
            source_id=DENVER_COUNTY_COURT_SOURCE,
            catalog_decision={"limits": {"minimum_interval_seconds": 0.4}},
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert observation.schema_sha256 == "c" * 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["courtroom_count"] == 35
    assert observation.details["parsed_row_count"] == 14
    assert observation.details["request_parameters"] == {
        "SelectedCourtroom": "3A",
        "Court_Date": "07/29/2026",
    }
    assert calls[0][0].command == "probe"
    assert calls[0][0].minimum_interval == 0.4
    assert calls[0][1]["log_results"] is False


def test_denver_foreclosure_probe_preserves_case_and_document_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_health_check",
                    "foreclosure_number": "2026-000418",
                    "status_option_count": 36,
                    "source_reported_total_results": 5_062,
                    "native_page_size": 25,
                    "detail_sections": ["Address", "Basics", "View Documents"],
                    "document_count": 4,
                    "persistent_session_required": True,
                    "schema_fingerprint": "f" * 64,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_denver_foreclosures",
        fake_execute,
    )

    observation = probe_denver_foreclosures(
        ProbeContext(
            source_id=DENVER_FORECLOSURE_SOURCE,
            catalog_decision={"limits": {"minimum_interval_seconds": 0.3}},
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.schema_sha256 == "f" * 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["source_reported_total_results"] == 5_062
    assert observation.details["native_page_size"] == 25
    assert observation.details["document_count"] == 4
    assert calls[0][0].foreclosure_number == "2026-000418"
    assert calls[0][0].minimum_interval == 0.3
    assert calls[0][1]["log_results"] is False


def test_denver_delinquent_tax_probe_preserves_hash_schema_and_counts(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_health_check",
                    "release": {
                        "tax_year": 2024,
                        "release_date": "2025-08-28",
                        "artifact_url": "https://example.test/list.xlsx",
                    },
                    "artifact_receipt": {
                        "sha256": "a" * 64,
                    },
                    "workbook_inspection": {
                        "artifact_size": 984_387,
                        "artifact_sha256": "a" * 64,
                        "worksheet": "Delinquent Tax List",
                        "data_row_count": 8_373,
                        "rows_by_tax_year": {"2024": 8_373},
                        "schema_fingerprint": "b" * 64,
                        "archive": {"member_count": 12},
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_denver_delinquent_tax",
        fake_execute,
    )

    observation = probe_denver_delinquent_tax(
        ProbeContext(
            source_id=DENVER_DELINQUENT_TAX_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=2,
            sample_bytes=128,
        )
    )

    assert observation.status == "ok"
    assert observation.schema_sha256 == "b" * 64
    assert observation.artifact_sha256 == "a" * 64
    assert observation.result_count == 8_373
    assert observation.details["tax_year"] == 2024
    assert observation.details["archive_member_count"] == 12
    assert "path" not in observation.details
    assert calls[0][0].sample_bytes == 128
    assert calls[0][1]["log_results"] is False


def test_colorado_judicial_probe_preserves_directory_and_export_state(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_health_check",
                    "directory_counts": {
                        "district": 23,
                        "county": 66,
                        "courthouse": 74,
                    },
                    "result_state": "results",
                    "source_total_count": 56,
                    "parsed_row_count": 20,
                    "native_pagination": True,
                    "export_link_advertised": True,
                    "export_status": "unavailable",
                    "schema_fingerprint": "c" * 64,
                    "directory_fingerprint": "d" * 64,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_colorado_judicial",
        fake_execute,
    )

    observation = probe_colorado_judicial(
        ProbeContext(
            source_id=COLORADO_JUDICIAL_SOURCE,
            catalog_decision={"limits": {"minimum_interval_seconds": 0.2}},
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.schema_sha256 == "c" * 64
    assert observation.artifact_sha256 == "d" * 64
    assert observation.result_count == 20
    assert observation.details["directory_counts"]["courthouse"] == 74
    assert observation.details["native_pagination"] is True
    assert observation.details["export_status"] == "unavailable"
    assert calls[0][0].minimum_interval == 0.2
    assert calls[0][1]["log_results"] is False


def test_colorado_court_data_probe_preserves_component_and_artifact_state(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []
    client_options = []
    closed = []
    fake_client = SimpleNamespace(
        session=SimpleNamespace(close=lambda: closed.append(True))
    )

    def fake_client_factory(**kwargs):
        client_options.append(kwargs)
        return fake_client

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_health_check",
                    "canonical_ref": (
                        "COURT-DATA:us-co-judicial-data-reports/"
                        "source-health-live-probe"
                    ),
                    "source_url": "https://example.test/reports",
                    "result_count": 18,
                    "component_counts": {
                        "us-co-judicial-annual-statistical-reports": 9,
                        "us-co-judicial-compiled-aggregate-data-requests": 3,
                    },
                    "source_pages": {"annual_reports": "https://example.test"},
                    "sentinels": {
                        "addendum_a": {"sha256": "e" * 64},
                    },
                    "schema_fingerprint": "c" * 64,
                    "artifact_identity": "d" * 64,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "ColoradoCourtDataClient",
        fake_client_factory,
    )
    monkeypatch.setattr(
        public_records_monitor,
        "execute_colorado_court_data",
        fake_execute,
    )

    observation = probe_colorado_court_data(
        ProbeContext(
            source_id=COLORADO_COURT_DATA_SOURCE,
            catalog_decision={"limits": {"minimum_interval_seconds": 0.25}},
            timeout=5,
            max_attempts=3,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.schema_sha256 == "c" * 64
    assert observation.artifact_sha256 == "d" * 64
    assert observation.result_count == 18
    assert (
        observation.details["component_counts"][
            "us-co-judicial-annual-statistical-reports"
        ]
        == 9
    )
    assert client_options == [
        {
            "timeout": 5,
            "minimum_interval": 0.25,
            "max_retries": 2,
        }
    ]
    assert calls[0][0].command == "probe"
    assert calls[0][1]["client"] is fake_client
    assert calls[0][1]["log_results"] is False
    assert closed == [True]


def test_oregon_taxlot_probe_preserves_publisher_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": OREGON_PORTLAND_TAXLOT_SOURCE,
                    "component_total_count": 606_572,
                    "sentinel_count": 1,
                    "schema_fingerprint": "a" * 64,
                    "layer_name": "Taxlots",
                    "max_record_count": 4_000,
                    "sentinel": {
                        "canonical_ref": (
                            "PROPERTY:us-or-portland-regional-taxlots/"
                            "41051/parcel/R123456"
                        ),
                        "native_parcel_id": "R123456",
                        "upstream_source": "Multnomah County",
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_taxlots",
        fake_execute,
    )

    decision = {
        "source_id": OREGON_PORTLAND_TAXLOT_SOURCE,
        "limits": {"minimum_interval_seconds": 0.35},
    }
    observation = probe_oregon_taxlot_component(
        ProbeContext(
            source_id=OREGON_PORTLAND_TAXLOT_SOURCE,
            catalog_decision=decision,
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.schema_sha256 == "a" * 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.result_count == 606_572
    assert observation.details["sentinel_count"] == 1
    assert observation.details["upstream_source"] == "Multnomah County"
    assert calls[0][0].source == OREGON_PORTLAND_TAXLOT_SOURCE
    assert calls[0][0].minimum_interval == 0.35
    assert calls[0][1]["access_decision"] is decision


def test_lane_marion_probe_separates_count_and_freshness_from_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_id = "us-or-marion-county-assessor-parcels"
    live = {
        "count": 115_385,
        "last_edit": "2026-07-29",
    }
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": source_id,
                    "component_total_count": live["count"],
                    "schema_fingerprint": "a" * 64,
                    "layer_name": "Parcels",
                    "service_item_id": ("bc90901732a4443bbfa1f949cc9cc205"),
                    "max_record_count": 2_000,
                    "source_crs": "EPSG:2913",
                    "service_data_last_edit": live["last_edit"],
                    "cadence_fact": "service and record freshness differ",
                    "component_scope": "current parcel component",
                    "sentinel_strategy": "configured_exact_identifier",
                    "sentinel_count": 1,
                    "sentinel": {
                        "canonical_ref": (
                            "PROPERTY:us-or-marion-county-assessor-parcels/"
                            "41047/parcel/032W290000400"
                        ),
                        "record_kind": "parcel",
                        "native_parcel_id": "032W290000400",
                        "assessment_account_ids": ["510174"],
                    },
                    "complementary_sources": [
                        {
                            "name": "Marion County Sales Data",
                            "access": "public_download",
                        }
                    ],
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_lane_marion_property",
        fake_execute,
    )
    decision = {
        "source_id": source_id,
        "limits": {"minimum_interval_seconds": 0.2},
    }
    context = ProbeContext(
        source_id=source_id,
        catalog_decision=decision,
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_oregon_lane_marion_property_component(context)
    live.update(count=115_386, last_edit="2026-07-30")
    second = probe_oregon_lane_marion_property_component(context)

    assert first.status == "ok"
    assert first.result_count == 115_385
    assert second.result_count == 115_386
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert second.details["service_data_last_edit"] == "2026-07-30"
    assert calls[0][0].source == source_id
    assert calls[0][0].minimum_interval == 0.2
    assert calls[0][1]["access_decision"] is decision
    assert calls[0][1]["log_results"] is False


def test_deschutes_property_probe_preserves_relationship_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": DESCHUTES_PROPERTY_SOURCE,
                    "service_item_id": "901cdd4a5ca24cc3b72cc8e3e0f11f02",
                    "component_counts": {
                        "taxlot": 109_508,
                        "owners": 210_139,
                        "sales": 109_477,
                    },
                    "declared_relationships": [
                        {"component": f"component-{index}"} for index in range(8)
                    ],
                    "keyed_complements": [{"component": "sales"}],
                    "sales_relationship_status": {
                        "component": "sales",
                        "declared_arcgis_relationship": False,
                        "provenance_kind": ("same_service_taxlot_key_complement"),
                    },
                    "sentinel": {
                        "native_parcel_id": "141031B000700",
                        "assessment_account_ids": ["135278"],
                        "last_sale": {"source_document_ref": "2018-38616"},
                        "response_schema_fingerprint": "d" * 64,
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_deschutes_property",
        fake_execute,
    )
    decision = {
        "source_id": DESCHUTES_PROPERTY_SOURCE,
        "limits": {"minimum_interval_seconds": 0.3},
    }

    observation = probe_deschutes_property(
        ProbeContext(
            source_id=DESCHUTES_PROPERTY_SOURCE,
            catalog_decision=decision,
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.schema_sha256 == "d" * 64
    assert observation.result_count == 109_508
    assert observation.details["declared_relationship_count"] == 8
    assert observation.details["keyed_complement_count"] == 1
    assert observation.details["sentinel_accounts"] == ["135278"]
    assert (
        observation.details["sales_relationship_status"]["declared_arcgis_relationship"]
        is False
    )
    assert len(observation.artifact_sha256 or "") == 64
    assert calls[0][0].minimum_interval == 0.3
    assert calls[0][1]["access_decision"] is decision


def test_deschutes_dial_probe_preserves_component_and_complement_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    component_names = public_records_monitor.DESCHUTES_DIAL_COMPONENTS

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": DESCHUTES_DIAL_SOURCE,
                    "sentinel": {
                        "native_account_id": "135278",
                        "native_parcel_id": "141031B000700",
                    },
                    "search": {
                        "field": "taxlot",
                        "resolution": "direct_account_summary",
                        "schema_fingerprint": "a" * 64,
                    },
                    "components": {
                        name: {
                            "status": "ok",
                            "source_url": (f"https://example.test/components/{name}"),
                            "schema_fingerprint": f"{index:064x}",
                        }
                        for index, name in enumerate(component_names, start=1)
                    },
                    "pdf_probe": {
                        "document_kind": "ownership",
                        "source_url": "https://example.test/ownership.pdf",
                        "signature_verified": True,
                        "size_bytes": 80_591,
                        "media_type": "application/pdf",
                    },
                    "linked_source_observations": {
                        "tax_payment_store": "ok",
                        "recorder_documents": "external_viewer_links",
                        "development_documents": "external_viewer_links",
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_deschutes_dial",
        fake_execute,
    )
    decision = {
        "source_id": DESCHUTES_DIAL_SOURCE,
        "limits": {"minimum_interval_seconds": 0.3},
    }

    observation = probe_deschutes_dial(
        ProbeContext(
            source_id=DESCHUTES_DIAL_SOURCE,
            catalog_decision=decision,
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.result_count == len(component_names)
    assert observation.details["native_account_id"] == "135278"
    assert observation.details["native_parcel_id"] == "141031B000700"
    assert observation.details["pdf_signature_verified"] is True
    assert observation.details["arcgis_complement_source_id"] == (
        DESCHUTES_PROPERTY_SOURCE
    )
    assert (
        observation.details["linked_source_observations"]["development_documents"]
        == "external_viewer_links"
    )
    assert calls[0][0].minimum_interval == 0.3
    assert calls[0][1]["access_decision"] is decision


def test_deschutes_cdd_probe_tracks_both_storage_modes_without_downloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": DESCHUTES_CDD_WEBLINK_SOURCE,
                    "account_discovery": {
                        "account_id": "135278",
                        "map_taxlot": "141031B000700",
                        "unique_document_count": 26,
                        "schema_fingerprint": "a" * 64,
                    },
                    "electronic_document": {
                        "laserfiche_entry_id": "1383062",
                        "parent_folder_id": "1378494",
                        "retrieval_mode": "electronic_file",
                    },
                    "imaged_document": {
                        "laserfiche_entry_id": "333623",
                        "parent_folder_id": "333580",
                        "page_count": 5,
                        "retrieval_mode": "generated_pdf_from_imaged_pages",
                    },
                    "parent_folder": {
                        "laserfiche_folder_id": "1378494",
                        "laserfiche_path": r"CDD\Planning\2025",
                    },
                    "viewer_access": {
                        "schema_fingerprint": "b" * 64,
                        "has_export_rights": True,
                    },
                    "downloads": [],
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_deschutes_cdd_weblink",
        fake_execute,
    )
    decision = {
        "source_id": DESCHUTES_CDD_WEBLINK_SOURCE,
        "limits": {"minimum_interval_seconds": 0.4},
    }
    observation = probe_deschutes_cdd_weblink(
        ProbeContext(
            source_id=DESCHUTES_CDD_WEBLINK_SOURCE,
            catalog_decision=decision,
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 26
    assert observation.details["electronic_document_id"] == "1383062"
    assert observation.details["electronic_retrieval_mode"] == "electronic_file"
    assert observation.details["imaged_document_id"] == "333623"
    assert observation.details["imaged_retrieval_mode"] == (
        "generated_pdf_from_imaged_pages"
    )
    assert observation.details["routine_downloads"] == 0
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert calls[0][0].with_download is False
    assert calls[0][0].minimum_interval == 0.4
    assert calls[0][1] == {"log_results": False}


def test_oregon_court_document_probe_preserves_collection_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_health_check",
                    "source_id": OREGON_SUPREME_OPINIONS_SOURCE,
                    "collection_alias": "p17027coll3",
                    "sentinel_item_id": "18161",
                    "sentinel_canonical_ref": (
                        "ORCOURT-DOC:us-or-law-library-supreme-opinions:18161"
                    ),
                    "sentinel_total_results": 1,
                    "metadata_field_count": 12,
                    "full_text_character_count": 24_000,
                    "is_compound": True,
                    "page_count": 14,
                    "download_uri": (
                        "https://cdm17027.contentdm.oclc.org/"
                        "digital/api/singleitem/collection/p17027coll3/id/18161"
                    ),
                    "search_schema_fingerprint": "b" * 64,
                    "item_schema_fingerprint": "c" * 64,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_court_documents",
        fake_execute,
    )

    decision = {
        "source_id": OREGON_SUPREME_OPINIONS_SOURCE,
        "limits": {"minimum_interval_seconds": 0.25},
    }
    observation = probe_oregon_court_document_component(
        ProbeContext(
            source_id=OREGON_SUPREME_OPINIONS_SOURCE,
            catalog_decision=decision,
            timeout=5,
            max_attempts=3,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.result_count == 1
    assert observation.details["collection_alias"] == "p17027coll3"
    assert observation.details["page_count"] == 14
    assert calls[0][0].source == OREGON_SUPREME_OPINIONS_SOURCE
    assert calls[0][0].minimum_interval == 0.25
    assert calls[0][1]["access_decision"] is decision
    assert calls[0][1]["log_results"] is False


def test_oregon_appellate_probe_preserves_component_partiality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.PARTIAL,
            records=(
                {
                    "record_kind": "probe",
                    "source_id": OREGON_APPELLATE_SOURCE,
                    "source_result_limit": 10_000,
                    "checks": {
                        "manage_info": {
                            "status": "ok",
                            "result": {"reported_search_results_limit": 10_000},
                        },
                        "case_detail": {
                            "status": "ok",
                            "result": {"case_number": "A182332"},
                        },
                        "docket": {
                            "status": "ok",
                            "result": {"records": 1, "total_elements": 25},
                        },
                        "judgments": {
                            "status": "unavailable",
                            "error": {"code": "judgments_http_error"},
                        },
                    },
                },
            ),
            errors=(
                SimpleNamespace(
                    to_dict=lambda: {
                        "code": "judgments_http_error",
                        "message": "official judgments endpoint returned 500",
                    }
                ),
            ),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_appellate",
        fake_execute,
    )
    decision = {
        "source_id": OREGON_APPELLATE_SOURCE,
        "limits": {"minimum_interval_seconds": 0.4},
    }

    observation = probe_oregon_appellate(
        ProbeContext(
            source_id=OREGON_APPELLATE_SOURCE,
            catalog_decision=decision,
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "partial"
    assert observation.result_count == 3
    assert observation.details["sentinel_case_number"] == "A182332"
    assert observation.details["source_result_limit"] == 10_000
    assert observation.details["component_status"]["judgments"] == ("unavailable")
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert calls[0][0].minimum_interval == 0.4
    assert calls[0][1]["access_decision"] is decision
    assert calls[0][1]["log_results"] is False


def test_oregon_court_calendar_probe_preserves_documented_and_live_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "probe",
                    "source_id": OREGON_COURT_CALENDAR_SOURCE,
                    "location": {"name": "Deschutes"},
                    "checks": {
                        "location_directory_count": 39,
                        "judicial_officer_count": 1112,
                        "reported_result_count": 128,
                        "parsed_result_count": 128,
                        "documented_result_ceiling": 400,
                        "live_observed_returned_rows": 550,
                        "native_truncation_detected": False,
                        "source_alerts": [],
                        "maximum_forward_date_window_days": 90,
                        "forward_only": True,
                    },
                    "schema_fingerprints": {
                        "landing": "landing-sha",
                        "form": "form-sha",
                        "results": "results-sha",
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_court_calendar",
        fake_execute,
    )
    decision = {
        "source_id": OREGON_COURT_CALENDAR_SOURCE,
        "limits": {"maximum_forward_date_window_days": 90},
    }
    observation = probe_oregon_court_calendar(
        ProbeContext(
            source_id=OREGON_COURT_CALENDAR_SOURCE,
            catalog_decision=decision,
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 128
    assert observation.details["location_directory_count"] == 39
    assert observation.details["judicial_officer_count"] == 1112
    assert observation.details["documented_result_ceiling"] == 400
    assert observation.details["live_observed_returned_rows"] == 550
    assert observation.details["native_truncation_detected"] is False
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert calls[0][0].location == "Deschutes"
    assert calls[0][1]["access_decision"] is decision
    assert calls[0][1]["log_results"] is False


def test_oregon_court_calendar_daily_counts_do_not_change_contract_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_counts = {
        "location_directory_count": 39,
        "judicial_officer_count": 1112,
        "reported_result_count": 128,
        "parsed_result_count": 128,
    }

    def fake_execute(_args, **_kwargs):
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "probe",
                    "source_id": OREGON_COURT_CALENDAR_SOURCE,
                    "location": {"name": "Deschutes"},
                    "checks": {
                        **current_counts,
                        "documented_result_ceiling": 400,
                        "live_observed_returned_rows": 550,
                        "native_truncation_detected": False,
                        "source_alerts": [],
                        "maximum_forward_date_window_days": 90,
                        "forward_only": True,
                    },
                    "schema_fingerprints": {
                        "landing": "landing-sha",
                        "form": "form-sha",
                        "results": "results-sha",
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_court_calendar",
        fake_execute,
    )
    context = ProbeContext(
        source_id=OREGON_COURT_CALENDAR_SOURCE,
        catalog_decision={"source_id": OREGON_COURT_CALENDAR_SOURCE},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = probe_oregon_court_calendar(context)
    current_counts.update(
        location_directory_count=40,
        judicial_officer_count=1115,
        reported_result_count=141,
        parsed_result_count=141,
    )
    second = probe_oregon_court_calendar(context)

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.result_count == 128
    assert second.result_count == 141


def test_oregon_smart_search_probe_separates_roster_and_runtime_from_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "public_records"
        / "oregon_smart_search"
        / "probe_sample.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    rolling_changed = deepcopy(fixture)
    rolling_changed["option_sets"]["JudicialOfficer"]["count"] += 3
    rolling_changed["option_sets"]["JudicialOfficerSearchBy"]["count"] += 3
    rolling_changed["runtime"]["browser_channel"] = "chromium"
    stable_changed = deepcopy(rolling_changed)
    stable_changed["option_sets"]["CaseStatus"]["count"] += 1
    records = [
        query_oregon_smart_search.normalize_probe(payload)
        for payload in (fixture, rolling_changed, stable_changed)
    ]
    calls = []

    def fake_execute(args):
        calls.append(args)
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(records.pop(0),),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_smart_search",
        fake_execute,
    )
    context = ProbeContext(
        source_id=OREGON_SMART_SEARCH_SOURCE,
        catalog_decision={"source_id": OREGON_SMART_SEARCH_SOURCE},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = probe_oregon_smart_search(context)
    rolling = probe_oregon_smart_search(context)
    stable = probe_oregon_smart_search(context)

    assert first.status == "ok"
    assert first.http_status == 200
    assert first.schema_sha256 == rolling.schema_sha256
    assert first.artifact_sha256 == rolling.artifact_sha256
    assert stable.schema_sha256 != rolling.schema_sha256
    assert stable.artifact_sha256 != rolling.artifact_sha256
    option_contract = first.details["stable_contract"]["option_sets"]
    assert option_contract["CourtLocation"]["count"] == 38
    assert "JudicialOfficer" not in option_contract
    assert first.details["rolling_observation"]["officer_option_counts"] == {
        "JudicialOfficer": 1112,
        "JudicialOfficerSearchBy": 1112,
    }
    assert rolling.details["rolling_observation"]["officer_option_counts"] == {
        "JudicialOfficer": 1115,
        "JudicialOfficerSearchBy": 1115,
    }
    assert (
        first.details["rolling_observation"]["runtime"]
        != (rolling.details["rolling_observation"]["runtime"])
    )
    assert all(call.command == "probe" and call.browser_timeout == 5 for call in calls)


def test_oregon_ojcin_probe_separates_http_observations_from_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def packet(*, changed_http: bool) -> dict:
        probes = []
        for index, endpoint in enumerate(query_oregon_ojcin_products.ENDPOINTS):
            changed = changed_http and index == 0
            probes.append(
                {
                    "endpoint_id": endpoint.endpoint_id,
                    "url": endpoint.url,
                    "final_url": endpoint.url,
                    "role": endpoint.role,
                    "source_ids": list(endpoint.source_ids),
                    "status": "http_error" if changed else "ok",
                    "http_status": 503 if changed else 200,
                    "content_type": (
                        "application/pdf"
                        if endpoint.media_kind == "pdf"
                        else "text/html"
                    ),
                    "content_length": 900 + index + (10 if changed else 0),
                    "etag": f'"fixture-{index + int(changed)}"',
                    "last_modified": (
                        "Wed, 29 Jul 2026 12:00:00 GMT"
                        if changed
                        else "Tue, 28 Jul 2026 12:00:00 GMT"
                    ),
                    "expected_media_kind": endpoint.media_kind,
                    "expected_marker": endpoint.marker,
                    "representation_ok": not changed,
                }
            )
        ok_count = sum(probe["status"] == "ok" for probe in probes)
        return {
            "schema_version": query_oregon_ojcin_products.OUTPUT_SCHEMA_VERSION,
            "adapter_source_id": OREGON_OJCIN_SOURCE,
            "adapter_schema_fingerprint": (
                query_oregon_ojcin_products.ADAPTER_SCHEMA_FINGERPRINT
            ),
            "status": "ok" if ok_count == len(probes) else "partial",
            "endpoint_count": len(probes),
            "ok_count": ok_count,
            "probes": probes,
        }

    packets = [packet(changed_http=False), packet(changed_http=True)]

    def fake_probe(_client):
        return packets.pop(0)

    monkeypatch.setattr(
        public_records_monitor,
        "run_oregon_ojcin_endpoint_probe",
        fake_probe,
    )
    context = ProbeContext(
        source_id=OREGON_OJCIN_SOURCE,
        catalog_decision={
            "source_id": OREGON_OJCIN_SOURCE,
            "limits": {"minimum_interval_seconds": 0},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = probe_oregon_ojcin_public_directory(context)
    rolling = probe_oregon_ojcin_public_directory(context)

    assert first.status == "ok"
    assert rolling.status == "partial"
    assert first.result_count == 13
    assert rolling.result_count == 12
    assert first.schema_sha256 == rolling.schema_sha256
    assert first.artifact_sha256 == rolling.artifact_sha256
    stable_contract = first.details["stable_contract"]
    assert len(stable_contract["product_contracts"]) == 5
    assert len(stable_contract["endpoint_contracts"]) == 13
    assert "http_status" not in stable_contract["endpoint_contracts"][0]
    assert first.details["rolling_observation"]["endpoints"][0]["http_status"] == 200
    assert rolling.details["rolling_observation"]["endpoints"][0]["http_status"] == 503

    changed_endpoint = replace(
        query_oregon_ojcin_products.ENDPOINTS[0],
        role="changed_fixture_role",
    )
    monkeypatch.setattr(
        public_records_monitor,
        "OREGON_OJCIN_ENDPOINTS",
        (changed_endpoint, *query_oregon_ojcin_products.ENDPOINTS[1:]),
    )
    packets.append(packet(changed_http=True))
    stable_changed = probe_oregon_ojcin_public_directory(context)

    assert stable_changed.schema_sha256 == rolling.schema_sha256
    assert stable_changed.artifact_sha256 != rolling.artifact_sha256


def _appellate_calendar_probe_record(
    *,
    source_id: str,
    list_count: int,
    attachment_count: int,
) -> dict:
    return {
        "record_kind": "probe",
        "source_id": source_id,
        "legacy_entrypoint": {"migrated_to_error_path": True},
        "page_contract": {"list_title": "ORCTrack"},
        "view_contract": {"row_limit": 300},
        "list_contract": {
            "list_id": "list-guid",
            "server_relative_url": "/courts/appellate/go/Lists/ORCTrack",
        },
        "checks": {
            "component_status": {
                "legacy_entrypoint": "migrated",
                "current_official_page": "ok",
                "sharepoint_list_api": "ok",
                "official_page_view": "partial",
                "adapter_acquisition": "ok",
            },
            "list_item_count": list_count,
            "declared_list_item_count": list_count,
            "source_pages_fetched": 4,
            "official_view_eligible_item_count": list_count,
            "official_view_may_truncate": True,
            "attachment_item_count": 0,
            "attachment_document_count": attachment_count,
            "oldest_event_date": "2026-07-29",
            "newest_event_date": "2026-10-28",
        },
        "schema_fingerprints": {
            "page_contract": "a" * 64,
            "view_contract": "b" * 64,
            "list_contract": "c" * 64,
            "list_items": "d" * 64,
        },
    }


def test_oregon_appellate_calendar_probe_separates_list_growth_from_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_state = {"count": 321, "attachments": 0}

    def fake_execute(args, **kwargs):
        assert args.court == "coa"
        assert kwargs["log_results"] is False
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                _appellate_calendar_probe_record(
                    source_id=OREGON_COA_CALENDAR_SOURCE,
                    list_count=list_state["count"],
                    attachment_count=list_state["attachments"],
                ),
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_appellate_calendars",
        fake_execute,
    )
    decision = {
        "source_id": OREGON_COA_CALENDAR_SOURCE,
        "limits": {"minimum_interval_seconds": 0.2},
    }
    context = ProbeContext(
        source_id=OREGON_COA_CALENDAR_SOURCE,
        catalog_decision=decision,
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_oregon_appellate_calendar_component(context)
    list_state.update(count=322, attachments=1)
    second = probe_oregon_appellate_calendar_component(context)

    assert first.status == "ok"
    assert first.result_count == 321
    assert second.result_count == 322
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert second.details["fetched_list_item_count"] == 322


def test_oregon_court_directory_probe_separates_roster_growth_from_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = {"reported": 40, "parsed": 36}
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "probe",
                    "source_id": OREGON_STATE_COURT_DIRECTORY_SOURCE,
                    "checks": {
                        "anonymous_page_bootstrap": True,
                        "cookie_bound_soap_request": True,
                        "soap_action_header_required": False,
                        "reported_item_count": counts["reported"],
                        "parsed_item_count": counts["parsed"],
                        "complete_response": True,
                        "live_view_count": 7,
                        "configured_view_count": 5,
                        "unconfigured_live_view_count": 2,
                    },
                    "list": {
                        "source_list_id": "{LIST-GUID}",
                        "source_title": "TCA-Locations",
                        "source_reported_item_count": counts["reported"],
                        "declared_field_count": 146,
                        "schema_fingerprint": "a" * 64,
                    },
                    "view": {
                        "view_id": "{VIEW-GUID}",
                        "live_display_name": ("Circuit Court Locations and Contacts"),
                        "schema_fingerprint": "b" * 64,
                    },
                    "rowset_schema_fingerprint": "c" * 64,
                    "live_views": [
                        {
                            "view_id": "{VIEW-GUID}",
                            "display_name": ("Circuit Court Locations and Contacts"),
                            "url": "Lists/TCA-Locations/AllItems.aspx",
                        }
                    ],
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_court_directories",
        fake_execute,
    )
    decision = {
        "source_id": OREGON_STATE_COURT_DIRECTORY_SOURCE,
        "limits": {"minimum_interval_seconds": 0.2},
    }
    context = ProbeContext(
        source_id=OREGON_STATE_COURT_DIRECTORY_SOURCE,
        catalog_decision=decision,
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_oregon_court_directory_component(context)
    counts.update(reported=41, parsed=37)
    second = probe_oregon_court_directory_component(context)

    assert first.status == "ok"
    assert first.result_count == 36
    assert second.result_count == 37
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert second.details["list_reported_item_count"] == 41
    assert calls[0][0].source == OREGON_STATE_COURT_DIRECTORY_SOURCE
    assert calls[0][0].minimum_interval == 0.2
    assert calls[0][1]["access_decision"] is decision


def test_oregon_tax_foreclosure_probe_separates_contract_from_current_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = {
        "page_sha256": "1" * 64,
        "label": "2025 Foreclosure List",
        "document_url": "https://www.tillamookcounty.gov/list-2025.pdf",
        "payload": b"%PDF-1.7\nfirst publication",
    }

    def fake_discover(config, *, timeout):
        assert config.source_id == OREGON_TILLAMOOK_TAX_FORECLOSURE_SOURCE
        assert timeout == 5
        return {
            "publication_routes": [
                {
                    "source_id": config.source_id,
                    "document_id": "publication-2025",
                    "publication_label": live["label"],
                    "document_url": live["document_url"],
                    "publication_page_url": config.primary_page,
                    "publication_page_role": "foreclosure_publication_index",
                    "process_stage": "foreclosure_list_published",
                    "publication_status": "published_artifact",
                    "publication_year": 2025,
                    "publication_date": None,
                    "court_case_number": "25-CV47055",
                    "version_identity": "artifact_sha256_after_download",
                }
            ],
            "landing_page_observations": [
                {
                    "url": config.primary_page,
                    "role": "foreclosure_publication_index",
                    "page_sha256": live["page_sha256"],
                    "discovered_route_count": 1,
                }
            ],
        }

    def fake_fetch(url, timeout, max_bytes):
        assert url == live["document_url"]
        assert timeout == 5
        assert max_bytes > len(live["payload"])
        return live["payload"]

    monkeypatch.setattr(
        public_records_monitor,
        "discover_oregon_tax_foreclosure_source",
        fake_discover,
    )
    monkeypatch.setattr(
        public_records_monitor,
        "fetch_oregon_tax_foreclosure_bytes",
        fake_fetch,
    )
    context = ProbeContext(
        source_id=OREGON_TILLAMOOK_TAX_FORECLOSURE_SOURCE,
        catalog_decision={"source_id": OREGON_TILLAMOOK_TAX_FORECLOSURE_SOURCE},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_oregon_tax_foreclosure_component(context)
    live["page_sha256"] = "2" * 64
    live["label"] = "2026 Foreclosure List"
    live["document_url"] = "https://www.tillamookcounty.gov/list-2026.pdf"
    live["payload"] = b"%PDF-1.7\nsecond publication"
    second = probe_oregon_tax_foreclosure_component(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    first_rolling = first.details["rolling_observation"]
    second_rolling = second.details["rolling_observation"]
    assert first_rolling["landing_pages"][0]["page_sha256"] == "1" * 64
    assert second_rolling["landing_pages"][0]["page_sha256"] == "2" * 64
    assert (
        first_rolling["current_artifact"]["sha256"]
        != second_rolling["current_artifact"]["sha256"]
    )
    assert first.details["stable_contract"]["supported_process_stages"] == [
        "foreclosure_list_published"
    ]
    assert first.details["artifact_contract"]["text_representation_parent_key"] == (
        "parent_artifact_sha256"
    )


def test_oregon_helion_probe_tracks_form_contract_and_index_freshness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    live = {
        "indexed_through_raw": "07/28/2026",
        "select_options": {
            "Criteria.Filter.PartyType": [{"value": "", "label": "All"}]
        },
    }

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": OREGON_WASCO_HELION_SOURCE,
                    "county_name": "Wasco County",
                    "county_fips": "41065",
                    "search_action": (
                        "https://public.co.wasco.or.us/"
                        "DigitalResearchRoomPublic/RecordingSearch"
                    ),
                    "search_method": "post",
                    "indexed_through_raw": live["indexed_through_raw"],
                    "form_fields": [
                        "Criteria.Filter.YearStart",
                        "Criteria.Filter.LastName",
                    ],
                    "select_options": {
                        key: [dict(option) for option in options]
                        for key, options in live["select_options"].items()
                    },
                    "source_schema_fingerprint": "e" * 64,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_helion_recorder",
        fake_execute,
    )
    decision = {
        "source_id": OREGON_WASCO_HELION_SOURCE,
        "limits": {"minimum_interval_seconds": 0.25},
    }
    context = ProbeContext(
        source_id=OREGON_WASCO_HELION_SOURCE,
        catalog_decision=decision,
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_oregon_helion_recorder_component(context)
    live["indexed_through_raw"] = "07/29/2026"
    second = probe_oregon_helion_recorder_component(context)
    live["select_options"]["Criteria.Filter.PartyType"][0]["label"] = "All Parties"
    third = probe_oregon_helion_recorder_component(context)

    assert first.status == "ok"
    assert first.result_count == 2
    assert first.schema_sha256 == "e" * 64
    assert len(first.artifact_sha256 or "") == 64
    assert first.artifact_sha256 == second.artifact_sha256
    assert third.artifact_sha256 != second.artifact_sha256
    assert second.details["indexed_through_raw"] == "07/29/2026"
    assert calls[0][0].source == OREGON_WASCO_HELION_SOURCE
    assert calls[0][0].minimum_interval == 0.25
    assert calls[0][1]["access_decision"] is decision


def test_oregon_helion_property_probe_separates_contract_from_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    live = {
        "title": "Property Search Online - Account Search",
        "access_outcome": "search_form_ready",
        "footer": "© 2022 - 2026 Helion Software All rights reserved",
        "transport_events": ["websocket"],
        "runtime": {
            "node": "v20.19.5",
            "browser_channel": "chrome",
        },
        "search_options": [
            {"label": "Account ID", "value": "AccountId", "selected": False},
            {
                "label": "Tax Account ID",
                "value": "TaxAccountId",
                "selected": False,
            },
            {"label": "Name", "value": "Name", "selected": False},
            {"label": "Address", "value": "Address", "selected": True},
            {"label": "Map", "value": "Map", "selected": False},
            {"label": "Legal", "value": "Legal", "selected": False},
        ],
    }

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": OREGON_MORROW_HELION_PROPERTY_SOURCE,
                    "observed_access": {"outcome": "public_search_and_detail_ready"},
                    "live_probe": {
                        **live,
                        "runtime": dict(live["runtime"]),
                        "transport_events": list(live["transport_events"]),
                        "search_options": [
                            dict(option) for option in live["search_options"]
                        ],
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_helion_property",
        fake_execute,
    )
    decision = {
        "source_id": OREGON_MORROW_HELION_PROPERTY_SOURCE,
        "allowed": True,
        "limits": {},
    }
    context = ProbeContext(
        source_id=OREGON_MORROW_HELION_PROPERTY_SOURCE,
        catalog_decision=decision,
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_oregon_helion_property_component(context)
    live["footer"] = "© 2022 - 2027 Helion Software All rights reserved"
    live["transport_events"] = [
        "websocket_failed",
        "long_polling_fallback",
    ]
    live["runtime"]["node"] = "v22.0.0"
    second = probe_oregon_helion_property_component(context)
    live["search_options"][0]["label"] = "Account Number"
    third = probe_oregon_helion_property_component(context)

    assert first.status == "ok"
    assert first.result_count == 6
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert third.artifact_sha256 != second.artifact_sha256
    assert second.details["volatile_observation"]["runtime"]["node"] == ("v22.0.0")
    assert second.details["volatile_observation"]["transport_events"] == [
        "websocket_failed",
        "long_polling_fallback",
    ]
    assert (
        second.details["stable_contract"]["configured_native_search_options"]["legal"]
        == "Legal"
    )
    assert calls[0][0].command == "probe"
    assert calls[0][0].source == OREGON_MORROW_HELION_PROPERTY_SOURCE
    assert calls[0][1]["access_decision"] is decision
    assert calls[0][1]["log_results"] is False


def test_oregon_county_assessor_probe_separates_contract_from_rolling_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    live = {
        "component_total_count": 104_000,
        "sentinel_count": 1,
        "representative_row": {
            "canonical_ref": "PUBLICRECORDSOURCE:linn/example",
            "native_id": "example",
            "native_parcel_id": "12345",
            "object_id": 10,
        },
        "update_metadata": {"latest_native_update": 1_700_000_000_000},
        "item_identity": {"modified": 1_700_000_000_000},
    }

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": OREGON_LINN_ASSESSOR_SOURCE,
                    "schema_fingerprint": "a" * 64,
                    "count_baseline": {
                        "expected_minimum": 100_000,
                        "observed": live["component_total_count"],
                    },
                    **live,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_linn_josephine_klamath_assessors",
        fake_execute,
    )
    decision = {
        "source_id": OREGON_LINN_ASSESSOR_SOURCE,
        "allowed": True,
        "limits": {},
    }
    context = ProbeContext(
        source_id=OREGON_LINN_ASSESSOR_SOURCE,
        catalog_decision=decision,
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_oregon_county_assessor_component(context)
    live["component_total_count"] = 104_101
    live["representative_row"]["object_id"] = 11
    live["update_metadata"]["latest_native_update"] = 1_710_000_000_000
    live["item_identity"]["modified"] = 1_710_000_000_000
    second = probe_oregon_county_assessor_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == "a" * 64
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert second.details["rolling_observation"]["component_total_count"] == (104_101)
    assert calls[0][0].command == "probe"
    assert calls[0][0].source == OREGON_LINN_ASSESSOR_SOURCE
    assert calls[0][1] == {"log_results": False}


def test_oregon_jackson_event_probe_keeps_event_window_out_of_contract_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = {
        "component_total_count": 21_000,
        "first_ordered_observation": {
            "native_event_id": "first",
            "event_date_raw": 1_600_000_000_000,
        },
        "last_ordered_observation": {
            "native_event_id": "last",
            "event_date_raw": 1_700_000_000_000,
        },
        "source_time_reference": {"zone": "America/Los_Angeles"},
    }

    def fake_execute(args, **kwargs):
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": OREGON_JACKSON_BUILDING_EVENT_SOURCE,
                    "schema_fingerprint": "b" * 64,
                    "complementary_sources": [
                        {
                            "source_id": OREGON_JACKSON_ACCELA_BUILDING_SOURCE,
                            "relationship": "record_detail",
                        }
                    ],
                    **live,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_jackson_property_events",
        fake_execute,
    )
    decision = {
        "source_id": OREGON_JACKSON_BUILDING_EVENT_SOURCE,
        "allowed": True,
        "limits": {},
    }
    context = ProbeContext(
        source_id=OREGON_JACKSON_BUILDING_EVENT_SOURCE,
        catalog_decision=decision,
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_oregon_jackson_property_event_component(context)
    live["component_total_count"] = 21_005
    live["last_ordered_observation"] = {
        "native_event_id": "new-last",
        "event_date_raw": 1_710_000_000_000,
    }
    second = probe_oregon_jackson_property_event_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == "b" * 64
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert second.result_count == 21_005


def test_oregon_jackson_accela_probe_separates_detail_contract_from_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = {
        "native_record_id": "439-24-001234-STR",
        "record_status": "Issued",
        "document_count": 2,
        "record_detail_representation": {"sha256": "c" * 64},
        "attachment_list_representation": {"sha256": "d" * 64},
    }

    def fake_execute(args, **kwargs):
        return {
            "status": "ok",
            "components": [
                {
                    "status": "ok",
                    "records": [
                        {
                            "record_kind": "source_probe",
                            "source_id": OREGON_JACKSON_ACCELA_BUILDING_SOURCE,
                            "schema_fingerprint": "e" * 64,
                            **live,
                        }
                    ],
                    "warnings": [],
                    "errors": [],
                }
            ],
        }

    monkeypatch.setattr(
        public_records_monitor,
        "execute_oregon_jackson_accela",
        fake_execute,
    )
    context = ProbeContext(
        source_id=OREGON_JACKSON_ACCELA_BUILDING_SOURCE,
        catalog_decision={
            "source_id": OREGON_JACKSON_ACCELA_BUILDING_SOURCE,
            "allowed": True,
            "limits": {},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_oregon_jackson_accela_component(context)
    live["record_status"] = "Finaled"
    live["document_count"] = 3
    live["attachment_list_representation"] = {"sha256": "f" * 64}
    second = probe_oregon_jackson_accela_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == "e" * 64
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert second.details["rolling_observation"]["document_count"] == 3


def test_eugene_municipal_probe_separates_source_contract_from_docket_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stable = {
        "court": {
            "court_id": "EUGENE_MUNICIPAL",
            "court_level": "municipal",
            "county_name": "Lane",
        },
        "platform_family": "central_square_public_access",
        "tenant_key": "eugene",
        "tenant_slug": "eugeneor",
        "case_search_url": "https://example.test/cases",
        "case_search_method": "POST",
        "available_search_options": [
            {"value": "CaseNumber", "label": "Case Number"},
            {"value": "Party", "label": "Party"},
        ],
        "dockets_url": "https://example.test/dockets",
        "configured_direct_verification": {"status": "verified"},
        "official_referrer_chain": ["https://example.test/official"],
        "request_complement": {
            "source_id": "us-or-eugene-municipal-court-record-request"
        },
    }
    live = {
        "upcoming_docket_count": 18,
        "component_access": {"case_search": "ready", "dockets": "ready"},
        "case_form_snapshot": {"sha256": "1" * 64},
        "docket_snapshot": {"sha256": "2" * 64},
    }

    def fake_execute(args):
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": EUGENE_MUNICIPAL_COURT_SOURCE,
                    "schema_fingerprints": {
                        "case_search": "3" * 64,
                        "dockets": "4" * 64,
                    },
                    **stable,
                    **live,
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_eugene_municipal_court",
        fake_execute,
    )
    context = ProbeContext(
        source_id=EUGENE_MUNICIPAL_COURT_SOURCE,
        catalog_decision={
            "source_id": EUGENE_MUNICIPAL_COURT_SOURCE,
            "allowed": True,
            "limits": {},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )
    first = probe_eugene_municipal_court_component(context)
    live["upcoming_docket_count"] = 22
    live["docket_snapshot"] = {"sha256": "5" * 64}
    second = probe_eugene_municipal_court_component(context)
    stable["available_search_options"].append(
        {"value": "Attorney", "label": "Attorney"}
    )
    third = probe_eugene_municipal_court_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert third.artifact_sha256 != second.artifact_sha256
    assert second.details["rolling_observation"]["upcoming_docket_count"] == 22


def test_tyler_monitor_binds_non_eugene_tenant_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = public_records_monitor.OREGON_TYLER_MUNICIPAL_TENANTS["medford"]
    calls = []

    def fake_execute(args):
        calls.append(args)
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_probe",
                    "source_id": tenant.source_id,
                    "court": {
                        "court_id": tenant.court_id,
                        "name": tenant.court_name,
                    },
                    "platform_family": "tyler_municipal_record_search",
                    "tenant_key": tenant.key,
                    "tenant_slug": tenant.slug,
                    "case_search_url": tenant.url("Cases/Search"),
                    "case_search_method": "get",
                    "available_search_options": list(tenant.verified_selectors),
                    "dockets_url": tenant.url("Dockets"),
                    "configured_direct_verification": {
                        "cases": "public",
                        "dockets": "public",
                    },
                    "official_referrer_chain": [tenant.official_url],
                    "request_complement": None,
                    "schema_fingerprints": {
                        "case_search": "3" * 64,
                        "dockets": "4" * 64,
                    },
                    "upcoming_docket_count": 141,
                    "component_access": {
                        "cases": "public",
                        "dockets": "public",
                    },
                    "case_form_snapshot": {"sha256": "1" * 64},
                    "docket_snapshot": {"sha256": "2" * 64},
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_eugene_municipal_court",
        fake_execute,
    )

    observation = probe_eugene_municipal_court_component(
        ProbeContext(
            source_id=tenant.source_id,
            catalog_decision={
                "source_id": tenant.source_id,
                "allowed": True,
                "limits": {},
            },
            timeout=12,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert calls[0].tenant == tenant.key
    assert observation.details["stable_contract"]["source_id"] == (tenant.source_id)
    assert observation.details["stable_contract"]["court"]["court_id"] == (
        tenant.court_id
    )


@pytest.mark.parametrize(
    ("source_id", "component"),
    [
        (OREGON_BENTON_TAXLOT_SOURCE, "parcel"),
        (OREGON_BENTON_BULK_SOURCE, "bulk"),
        (OREGON_BENTON_MAP_SOURCE, "maps"),
    ],
)
def test_benton_component_monitors_separate_contract_from_rolling_state(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    component: str,
) -> None:
    adapter = public_records_monitor.query_oregon_benton_property
    source = {
        "parcel": adapter.PARCEL_SOURCE_METADATA,
        "bulk": adapter.BULK_SOURCE_METADATA,
        "maps": adapter.MAP_SOURCE_METADATA,
    }[component]
    rolling = {"value": 100}
    stable_schema = {"fields": ["Account_Num", "MapTaxlot", "ORTaxlot", "MapNumber"]}

    def record():
        if component == "parcel":
            return {
                "record_kind": "source_probe",
                "source_id": source_id,
                "layer_identity": {
                    "service": "Public/TaxlotOwners",
                    "layer": 0,
                },
                "jurisdiction_identity": {
                    "county_geoid": "41003",
                    "verified": True,
                },
                "schema_baseline": stable_schema,
                "schema_fingerprint": "a" * 64,
                "component_total_count": rolling["value"],
                "count_baseline": {"observed": rolling["value"]},
                "sentinel_count": 1,
                "representative_row": {
                    "canonical_ref": "PROPERTY:benton/example",
                    "object_id": rolling["value"],
                    "account_number": "802377",
                    "map_taxlot": "11513A000100",
                    "or_taxlot": "0211.00S05.00W13A0--000000100",
                    "map_number": "11513A",
                },
                "update_evidence": {
                    "observed_count": rolling["value"],
                },
            }
        if component == "bulk":
            return {
                "record_kind": "source_probe",
                "source_id": source_id,
                "directory_identity": {
                    "path": "/gisdata/Assessment/",
                },
                "directory_entry_count": rolling["value"],
                "listing_fingerprint": str(rolling["value"]),
                "release": {
                    "manifest": {
                        "dataset_id": "benton-assessment",
                        "schema": stable_schema,
                        "release": {"release_id": str(rolling["value"])},
                        "artifacts": [
                            {
                                "artifact_id": "file_geodatabase",
                                "filename": "BentonTaxlots.gdb.zip",
                                "media_type": "application/zip",
                                "archive_format": "zip",
                            },
                            {
                                "artifact_id": "taxlot_shapefile",
                                "filename": "Taxlot.zip",
                                "media_type": "application/zip",
                                "archive_format": "zip",
                            },
                            {
                                "artifact_id": "taxlot_owner_shapefile",
                                "filename": "TaxlotOwners.zip",
                                "media_type": "application/zip",
                                "archive_format": "zip",
                            },
                        ],
                    }
                },
                "artifact_probes": [
                    {"filename": "TaxlotOwners.zip", "size": rolling["value"]}
                ],
            }
        return {
            "record_kind": "source_probe",
            "source_id": source_id,
            "directory_identity": {
                "path": "/gisdata/Assessment/AssessmentMapsPDF/",
            },
            "pdf_count": rolling["value"],
            "listing_fingerprint": str(rolling["value"]),
            "latest_directory_entry": {"filename": f"{rolling['value']}.pdf"},
            "representative_map": {
                "filename": "11513A.pdf",
                "map_number": "11513A",
            },
            "artifact_probe": {
                "filename": "11513A.pdf",
                "size": rolling["value"],
            },
        }

    calls = []

    def fake_execute(args, *, log_results):
        calls.append((args, log_results))
        query = adapter._public_query(
            source,
            operation="probe",
            parameters={"component": component},
            limit=1,
        )
        return PublicRecordsResult.success(query, [record()])

    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={
            "source_id": source_id,
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=8 if component != "parcel" else None,
    )

    first = probe_oregon_benton_property_component(context)
    rolling["value"] += 1
    second = probe_oregon_benton_property_component(context)

    assert first.status == "ok"
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert calls[0][0].component == component
    assert calls[0][1] is False


def test_oregon_county_component_monitor_separates_contract_from_rolling_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_oregon_wasco_property
    source_id = adapter.LAND_CORNERS_SOURCE_ID
    rolling = {"count": 1394}
    calls = []

    def fake_execute(args, *, log_results):
        calls.append((args, log_results))
        query = adapter._query(source_id, "probe", parameters={})
        return PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": source_id,
                    "component_count": rolling["count"],
                    "observed_count": 1394,
                    "max_record_count": 1000,
                    "schema_fingerprint": "a" * 64,
                    "native_contract": {
                        "service_item_id": adapter.SURVEY_SERVICE_ITEM_ID,
                        "layer_id": 53,
                    },
                }
            ],
        )

    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={
            "source_id": source_id,
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_oregon_county_property_component(context)
    rolling["count"] += 1
    second = probe_oregon_county_property_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert calls[0][0].source == source_id
    assert calls[0][1] is False


def test_all_new_oregon_county_components_have_monitor_handlers() -> None:
    expected = {
        *public_records_monitor.query_oregon_yamhill_property.SOURCE_IDS,
        *public_records_monitor.query_oregon_clackamas_property.SOURCE_IDS,
        *public_records_monitor.query_oregon_wasco_property.SOURCE_IDS,
    }

    assert expected.issubset(HANDLER_REGISTRY)
    assert all(
        HANDLER_REGISTRY[source_id].handler is probe_oregon_county_property_component
        for source_id in expected
    )


def test_washington_component_monitor_separates_contract_from_rolling_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_oregon_washington_property
    source_id = adapter.SURVEY_API_SOURCE_ID
    rolling = {"total": 1}

    def fake_component_probe(context):
        assert context.source_id == source_id
        return {
            "endpoint": adapter.SURVEY_SEARCH_URL,
            "schema_contract": {
                "envelope_keys": ["data", "total"],
                "record_fields": ["Surveynumber"],
            },
            "rolling_observation": {
                "total": rolling["total"],
                "sentinel": adapter.PROBE_SURVEY,
            },
            "result_count": 1,
        }

    monkeypatch.setattr(
        public_records_monitor,
        "_run_washington_property_component_probe",
        fake_component_probe,
    )
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={
            "source_id": source_id,
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_oregon_washington_property_component(context)
    rolling["total"] += 1
    second = probe_oregon_washington_property_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["stable_contract"]["survey_kinds"]["survey"][
        "native_id_fields"
    ] == ["Surveynumber", "Surveyornumber"]


def test_all_washington_components_have_selective_monitor_handlers() -> None:
    adapter = public_records_monitor.query_oregon_washington_property

    assert set(adapter.SOURCES).issubset(HANDLER_REGISTRY)
    assert all(
        HANDLER_REGISTRY[source_id].handler
        is probe_oregon_washington_property_component
        for source_id in adapter.SOURCES
    )
    assert HANDLER_REGISTRY[adapter.SURVEY_API_SOURCE_ID].expected_requests == 1
    assert HANDLER_REGISTRY[adapter.INTERMAP_SOURCE_ID].expected_requests == 1
    assert HANDLER_REGISTRY[adapter.TAX_SOURCE_ID].expected_requests == 1
    assert HANDLER_REGISTRY[adapter.SURVEY_MAP_SOURCE_ID].expected_requests == 2
    assert HANDLER_REGISTRY[adapter.TAXLOT_SOURCE_ID].expected_requests == 2
    assert HANDLER_REGISTRY[adapter.SITUS_SOURCE_ID].expected_requests == 2


class _WashingtonParcelMonitorClient:
    def __init__(
        self,
        metadata,
        rows,
        *,
        total_count,
        layer_url="https://example.test/FeatureServer/0",
    ):
        self.metadata = deepcopy(metadata)
        self.rows = deepcopy(rows)
        self.total_count = total_count
        self.layer_url = layer_url
        self.request_count = 0

    def fetch_metadata(self):
        self.request_count += 1
        return deepcopy(self.metadata)

    def fetch_count(self, where, *, parameters=None):
        del parameters
        self.request_count += 1
        if where == "1=1":
            return self.total_count
        sentinel = public_records_monitor.query_washington_parcels.SENTINEL_PARCEL_ID
        if sentinel in where:
            return sum(
                row.get("attributes", {}).get("PARCEL_ID_NR") == sentinel
                for row in self.rows
            )
        return len(self.rows)

    def fetch_page(
        self,
        *,
        where,
        offset,
        record_count,
        out_fields="*",
        return_geometry,
        parameters=None,
    ):
        del out_fields, return_geometry, parameters
        self.request_count += 1
        rows = self.rows
        sentinel = public_records_monitor.query_washington_parcels.SENTINEL_PARCEL_ID
        if sentinel in where:
            rows = [
                row
                for row in rows
                if row.get("attributes", {}).get("PARCEL_ID_NR") == sentinel
            ]
        return tuple(deepcopy(rows[offset : offset + record_count]))


def _washington_parcel_fixture(name: str):
    fixture_root = (
        Path(__file__).parent / "fixtures" / "public_records" / "washington_parcels"
    )
    return json.loads((fixture_root / f"{name}.json").read_text())


def _washington_parcel_context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "source_id": source_id,
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )


def test_washington_parcel_representation_monitor_keeps_values_rolling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_washington_parcels
    rolling = {"land_value": 100}

    def fake_client(context, layer_url, *, maximum_page_size):
        del context, maximum_page_size
        row = _washington_parcel_fixture("sentinels")["ecology"]
        row["attributes"]["VALUE_LAND"] = rolling["land_value"]
        return _WashingtonParcelMonitorClient(
            _washington_parcel_fixture("ecology_metadata"),
            [row],
            total_count=3_321_859,
            layer_url=layer_url,
        )

    monkeypatch.setattr(
        public_records_monitor,
        "_washington_parcel_client",
        fake_client,
    )
    context = _washington_parcel_context(adapter.ECOLOGY_SOURCE_ID)

    first = probe_washington_parcel_representation(context)
    rolling["land_value"] += 1
    second = probe_washington_parcel_representation(context)

    assert first.status == "ok"
    assert first.result_count == 3_321_859
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["requests_made"] == 4
    assert first.details["schema_contract"]["owner_fields_detected"] == []
    assert (
        first.details["stable_contract"]["mirror_comparison_is_corroboration"] is False
    )


def test_washington_parcel_companion_monitor_keeps_counts_rolling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_washington_parcels
    rolling = {"count": 39}

    def fake_client(context, layer_url, *, maximum_page_size):
        del context, maximum_page_size
        fixture = _washington_parcel_fixture("county_freshness")
        return _WashingtonParcelMonitorClient(
            fixture,
            fixture["features"][:1],
            total_count=rolling["count"],
            layer_url=layer_url,
        )

    monkeypatch.setattr(
        public_records_monitor,
        "_washington_parcel_client",
        fake_client,
    )
    context = _washington_parcel_context(adapter.FRESHNESS_SOURCE_ID)

    first = probe_washington_parcel_companion(context)
    rolling["count"] = 40
    second = probe_washington_parcel_companion(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"]["expected_count_met"] is True
    assert second.details["rolling_observation"]["expected_count_met"] is False
    assert first.details["requests_made"] == 3


def test_washington_parcel_lineage_monitor_treats_parity_as_rolling_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_washington_parcels
    rolling = {"land_value": 100}

    def fake_clients(args):
        del args
        sentinels = _washington_parcel_fixture("sentinels")
        ecology = sentinels["ecology"]
        ecology["attributes"]["VALUE_LAND"] = rolling["land_value"]
        freshness = _washington_parcel_fixture("county_freshness")
        return {
            "ecology": _WashingtonParcelMonitorClient(
                _washington_parcel_fixture("ecology_metadata"),
                [ecology],
                total_count=3_321_859,
            ),
            "dnr": _WashingtonParcelMonitorClient(
                _washington_parcel_fixture("dnr_metadata"),
                [sentinels["dnr"]],
                total_count=3_321_859,
            ),
            "wisaard": _WashingtonParcelMonitorClient(
                _washington_parcel_fixture("wisaard_metadata"),
                [sentinels["wisaard"]],
                total_count=3_192_327,
            ),
            "freshness": _WashingtonParcelMonitorClient(
                freshness,
                freshness["features"][:1],
                total_count=1,
            ),
            "landuse": _WashingtonParcelMonitorClient(
                _washington_parcel_fixture("county_land_use"),
                [],
                total_count=0,
            ),
        }

    monkeypatch.setattr(adapter, "_client_map", fake_clients)
    context = _washington_parcel_context(adapter.LINEAGE_ID)

    first = probe_washington_parcel_lineage(context)
    rolling["land_value"] += 1
    second = probe_washington_parcel_lineage(context)

    assert first.status == "ok"
    assert first.result_count == 3
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["requests_made"] == 15
    assert first.details["stable_contract"]["parity_interpretation"] == (
        "mirror_health_not_corroboration"
    )


def test_all_washington_parcel_sources_have_bounded_monitor_handlers() -> None:
    adapter = public_records_monitor.query_washington_parcels
    expected = {
        adapter.LINEAGE_ID,
        adapter.FRESHNESS_SOURCE_ID,
        adapter.LAND_USE_SOURCE_ID,
        *{
            representation.source_id
            for representation in adapter.REPRESENTATIONS.values()
        },
    }

    assert expected.issubset(HANDLER_REGISTRY)
    for representation in adapter.REPRESENTATIONS.values():
        spec = HANDLER_REGISTRY[representation.source_id]
        assert spec.handler is probe_washington_parcel_representation
        assert spec.expected_requests == 4
    assert HANDLER_REGISTRY[adapter.FRESHNESS_SOURCE_ID].expected_requests == 3
    assert HANDLER_REGISTRY[adapter.LAND_USE_SOURCE_ID].expected_requests == 3
    assert HANDLER_REGISTRY[adapter.LINEAGE_ID].expected_requests == 15
    assert HANDLER_REGISTRY[adapter.LINEAGE_ID].sentinel_record_count == 3


def _dc_property_fixture(name: str):
    fixture_root = Path(__file__).parent / "fixtures" / "public_records" / "dc_property"
    return json.loads((fixture_root / f"{name}.json").read_text())


def _dc_property_context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "source_id": source_id,
            "allowed": True,
            "limits": {},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )


def test_dc_property_component_monitor_keeps_values_rolling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_dc_property
    rolling = {"sale_price": 498_360}

    class FakeClient:
        request_count = 0

        def fetch_metadata(self):
            self.request_count += 1
            return _dc_property_fixture("metadata")

        def fetch_count(self):
            self.request_count += 1
            return 421_472

        def query(self, **_kwargs):
            self.request_count += 1
            feature = _dc_property_fixture("sale")
            feature["attributes"]["SALE_PRICE"] = rolling["sale_price"]
            return SimpleNamespace(
                records=(feature,),
                schema_fingerprint="sale-response-schema",
            )

    monkeypatch.setattr(
        public_records_monitor,
        "_dc_property_client",
        lambda _context, _component: FakeClient(),
    )
    context = _dc_property_context(adapter.SALES_SOURCE_ID)

    first = public_records_monitor.probe_dc_property_component(context)
    rolling["sale_price"] += 1
    second = public_records_monitor.probe_dc_property_component(context)

    assert first.status == "ok"
    assert first.result_count == 421_472
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["requests_made"] == 3
    assert first.details["stable_contract"]["lineage_relationship"] == (
        "cama_sale_observation"
    )


def test_dc_property_lineage_monitor_keeps_components_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_dc_property
    rolling = {"count": 100}

    def fake_probe(context):
        component = next(
            component
            for component in adapter.COMPONENTS.values()
            if component.source_id == context.source_id
        )
        return ProbeObservation(
            status="ok",
            endpoint=component.layer_url,
            schema_sha256=f"{component.layer_id:064x}"[-64:],
            artifact_sha256=f"{component.layer_id + 1:064x}"[-64:],
            result_count=rolling["count"],
            details={
                "rolling_observation": {"count": rolling["count"]},
                "requests_made": 3,
            },
        )

    monkeypatch.setattr(
        public_records_monitor,
        "probe_dc_property_component",
        fake_probe,
    )
    context = _dc_property_context(adapter.LINEAGE_ID)

    first = public_records_monitor.probe_dc_property_lineage(context)
    rolling["count"] += 1
    second = public_records_monitor.probe_dc_property_lineage(context)

    assert first.status == "ok"
    assert first.result_count == 4
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["requests_made"] == 12
    assert {
        component["source"]["source_id"]
        for component in first.details["stable_contract"]["components"]
    } == {component.source_id for component in adapter.COMPONENTS.values()}
    assert first.details["stable_contract"]["account_polygon_cardinality"] == (
        "not_assumed_one_to_one"
    )


def test_all_dc_queryable_components_have_bounded_monitor_handlers() -> None:
    adapter = public_records_monitor.query_dc_property
    expected = {
        adapter.LINEAGE_ID,
        *{component.source_id for component in adapter.COMPONENTS.values()},
    }

    assert expected.issubset(HANDLER_REGISTRY)
    for component in adapter.COMPONENTS.values():
        spec = HANDLER_REGISTRY[component.source_id]
        assert spec.handler is public_records_monitor.probe_dc_property_component
        assert spec.expected_requests == 3
        assert spec.sentinel_record_count == 1
    lineage = HANDLER_REGISTRY[adapter.LINEAGE_ID]
    assert lineage.handler is public_records_monitor.probe_dc_property_lineage
    assert lineage.expected_requests == 12
    assert lineage.sentinel_record_count == 4
    assert adapter.RECORDER_SOURCE_ID not in HANDLER_REGISTRY


def test_washington_case_permit_monitor_separates_contract_from_rolling_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_oregon_washington_case_permits
    source_id = adapter.CASEFILE_SOURCE_ID
    rolling = {"count": 1}
    calls = []

    def fake_execute(args, *, log_results):
        calls.append((args, log_results))
        query = adapter._query(
            source_id,
            args.command,
            {"sentinel": adapter.PROBE_CASEFILE},
        )
        records = [
            {
                "source_id": source_id,
                "record_kind": f"{args.command}_probe",
                "native_record_id": f"{args.command}-{index}",
                "schema_fingerprint": "a" * 64,
            }
            for index in range(rolling["count"])
        ]
        return PublicRecordsResult.success(query, records)

    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={
            "source_id": source_id,
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_oregon_washington_case_permit_component(context)
    rolling["count"] += 1
    second = probe_oregon_washington_case_permit_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.result_count == 4
    assert second.result_count == 8
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert [call[0].command for call in calls[:4]] == [
        "case-detail",
        "case-review",
        "case-decisions",
        "case-staff",
    ]
    assert all(call[1] is False for call in calls)


def test_all_washington_case_permit_components_have_scoped_monitors() -> None:
    adapter = public_records_monitor.query_oregon_washington_case_permits
    expected_requests = {
        adapter.CASEFILE_SOURCE_ID: 4,
        adapter.TAXLOT_ACTIVITY_SOURCE_ID: 1,
        adapter.BUILDING_SOURCE_ID: 2,
        adapter.PERMIT_REPORT_SOURCE_ID: 5,
        adapter.ACCELA_SOURCE_ID: 3,
        adapter.DOCUMENT_ROUTE_SOURCE_ID: 0,
    }

    assert set(adapter.SOURCES).issubset(HANDLER_REGISTRY)
    for source_id, request_count in expected_requests.items():
        spec = HANDLER_REGISTRY[source_id]
        assert spec.handler is probe_oregon_washington_case_permit_component
        assert spec.expected_requests == request_count
        commands = public_records_monitor._washington_case_permit_probe_commands(
            source_id
        )
        assert sum(int(uses_network) for _, _, uses_network in commands) == (
            1 if source_id == adapter.ACCELA_SOURCE_ID else request_count
        )


def test_multnomah_sail_monitor_separates_contract_from_rolling_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_oregon_multnomah_sail
    source_id = adapter.SURVEY_SOURCE_ID
    component = adapter.COMPONENTS[source_id]
    rolling = {"count": component.observed_count}
    calls = []

    def fake_execute(args, *, access_decision, log_results):
        calls.append((args, access_decision, log_results))
        query = adapter._build_query(
            component,
            operation="probe",
            parameters={"sentinel_where": "SURVEYID = '05335'"},
            requested_limit=1,
            cursor=None,
            access_decision=access_decision,
        )
        return PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": source_id,
                    "component_total_count": rolling["count"],
                    "observed_count_reference": component.observed_count,
                    "schema_fingerprint": "a" * 64,
                    "layer_name": component.layer_name,
                    "layer_id": 0,
                    "service_item_id": component.item_id,
                    "geometry_type": component.geometry_type,
                    "native_crs": component.source_crs_label,
                    "max_record_count": 2000,
                    "ordering": "OBJECTID ASC",
                    "complete_sort_tuple": ["OBJECTID"],
                    "sentinel": {
                        "source_record_id": "7220",
                        "survey_document_id": "05335",
                    },
                    "image_resolution": {
                        "survey_document_id": "05335",
                        "viewer_sha256": f"{rolling['count']:064x}",
                    },
                }
            ],
        )

    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={
            "source_id": source_id,
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_oregon_multnomah_sail_component(context)
    rolling["count"] += 1
    second = probe_oregon_multnomah_sail_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert (
        first.details["stable_contract"]["layer_contract"]["object_id_field"]
        == "OBJECTID"
    )
    assert first.details["stable_contract"]["image_viewer_template"] == (
        adapter.IMAGE_VIEWER_TEMPLATE
    )
    assert all(call[0].resolve_image is True for call in calls)
    assert all(call[2] is False for call in calls)


def test_all_multnomah_sail_components_have_selective_monitor_handlers() -> None:
    adapter = public_records_monitor.query_oregon_multnomah_sail

    assert set(adapter.SOURCE_IDS).issubset(HANDLER_REGISTRY)
    assert all(
        HANDLER_REGISTRY[source_id].handler is probe_oregon_multnomah_sail_component
        for source_id in adapter.SOURCE_IDS
    )
    assert HANDLER_REGISTRY[adapter.SURVEY_SOURCE_ID].expected_requests == 4
    assert all(
        HANDLER_REGISTRY[source_id].expected_requests == 3
        for source_id in adapter.SOURCE_IDS
        if source_id != adapter.SURVEY_SOURCE_ID
    )


def test_lincoln_propertyweb_monitor_separates_contract_from_account_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_oregon_lincoln_propertyweb
    rolling = {"count": 44966, "tax_year": 2026}
    calls = []

    def fake_execute(args, *, log_results):
        calls.append((args, log_results))
        query = adapter._basic_query("probe", {})
        return PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": adapter.SOURCE_ID,
                    "home": {
                        "tax_year": rolling["tax_year"],
                        "schema_fingerprint": "a" * 64,
                    },
                    "search": {
                        "record_count": rolling["count"],
                        "schema_fingerprint": "b" * 64,
                        "snapshot_fingerprint": str(rolling["count"]),
                    },
                    "detail": {
                        "property_quick_ref": "R452940",
                        "party_quick_ref": "O0064958",
                        "property_id": "61623",
                        "property_owner_id": "143319",
                        "party_id": "208038",
                        "map_number": "07-11-03-DC-05800-00",
                        "response_schema_fingerprint": "c" * 64,
                    },
                    "document": None,
                }
            ],
        )

    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=adapter.SOURCE_ID,
        catalog_decision={
            "source_id": adapter.SOURCE_ID,
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_oregon_lincoln_propertyweb(context)
    rolling["count"] += 1
    rolling["tax_year"] += 1
    second = probe_oregon_lincoln_propertyweb(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert calls[0][0].command == "probe"
    assert calls[0][1] is False


def test_lincoln_wfs_monitor_separates_protocol_from_rolling_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = public_records_monitor.query_oregon_lincoln_taxlots
    monkeypatch.setattr(adapter, "build_parser", lambda: pytest.fail("internal CLI parsing"))
    rolling = {"count": 44966, "fid": "42750936"}
    calls = []

    def fake_execute(args, *, log_results):
        calls.append((args, log_results))
        query = adapter._build_query(
            operation="probe",
            selector=adapter.SENTINEL_PROPERTY_ID,
            field="property",
            match="exact",
            geometry=True,
            limit=1,
            cursor=None,
        )
        return PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": adapter.SOURCE_ID,
                    "service_identity": {
                        "wfs_endpoint": adapter.MAPSERVER_URL,
                        "feature_type": adapter.TYPE_NAME,
                    },
                    "jurisdiction_evidence": {
                        "county_geoid": adapter.COUNTY_GEOID,
                        "verified": True,
                    },
                    "protocol_contract": {
                        "version": adapter.WFS_VERSION,
                        "result_paging": True,
                        "sorting": True,
                    },
                    "crs_lineage": {
                        "source_default_crs": adapter.SOURCE_DEFAULT_CRS,
                        "requested_srs": adapter.REQUESTED_CRS,
                        "geojson_reported_crs": adapter.EXPECTED_RETURNED_CRS,
                    },
                    "declared_schema": {"fields": list(adapter.DECLARED_FIELDS)},
                    "schema_baseline": {
                        "observed_fingerprint": adapter.EXPECTED_SCHEMA_FINGERPRINT,
                    },
                    "count_baseline": {
                        "current_count": rolling["count"],
                        "source_timestamp": str(rolling["count"]),
                    },
                    "sentinel_count": 1,
                    "representative_row": {
                        "native_identity": {
                            "propertyid": adapter.SENTINEL_PROPERTY_ID,
                            "parcelid": adapter.SENTINEL_PARCEL_ID,
                            "ogc_fid": rolling["fid"],
                            "imagekey": "07 11 03 DC",
                        }
                    },
                    "complementary_sources": list(adapter.COMPLEMENTARY_SOURCES),
                }
            ],
        )

    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=adapter.SOURCE_ID,
        catalog_decision={
            "source_id": adapter.SOURCE_ID,
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=12,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_oregon_lincoln_taxlots(context)
    rolling["count"] += 1
    rolling["fid"] = "42750937"
    second = probe_oregon_lincoln_taxlots(context)

    assert first.status == "ok"
    assert first.schema_sha256 == adapter.EXPECTED_SCHEMA_FINGERPRINT
    assert isinstance(calls[0][0], adapter.QueryOptions)
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert calls[0][0].command == "probe"
    assert calls[0][1] is False


@pytest.mark.parametrize(
    ("source_id", "component", "probe"),
    [
        (
            COLORADO_OPINIONS_SOURCE,
            "archive",
            probe_colorado_opinions_archive,
        ),
        (
            COLORADO_OPINION_RELEASES_SOURCE,
            "releases",
            probe_colorado_opinion_releases,
        ),
    ],
)
def test_colorado_opinions_probes_keep_component_identity(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    component: str,
    probe: Callable[[ProbeContext], ProbeObservation],
) -> None:
    calls = []
    component_record = {
        "source_id": source_id,
        "search_schema_fingerprint": "a" * 64,
        "count_schema_fingerprint": "b" * 64,
        "metadata_schema_fingerprint": "c" * 64,
        "sentinel_document_id": "887202075",
        "sentinel_result_count": 1,
        "full_text_sha256": "d" * 64,
        "pdf_byte_length": 45572,
        "pdf_media_type": "application/pdf",
        "pdf_sha256": "e" * 64,
        "supreme_schema_fingerprint": "f" * 64,
        "appeals_schema_fingerprint": "1" * 64,
        "supreme_current_page_records": 75,
        "appeals_current_page_packets": 20,
        "appeals_records_are_opinions": False,
    }

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "record_kind": "source_health_check",
                    "source_id": source_id,
                    "canonical_ref": (
                        f"STATECOURT:{source_id}/source-health/probe-{component}"
                    ),
                    "source_url": "https://example.test/colorado-opinions",
                    "result_count": 1 if component == "archive" else 95,
                    "schema_fingerprint": "2" * 64,
                    "artifact_identity": "3" * 64,
                    "component_sources": [component_record],
                    "source_roles_kept_distinct": True,
                    "native_pagination": {
                        "short_page_is_not_exhaustion": True,
                    },
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_colorado_opinions",
        fake_execute,
    )

    observation = probe(
        ProbeContext(
            source_id=source_id,
            catalog_decision={"limits": {"minimum_interval_seconds": 0.3}},
            timeout=5,
            max_attempts=2,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.schema_sha256 == "2" * 64
    assert observation.artifact_sha256 == "3" * 64
    assert observation.result_count == (1 if component == "archive" else 95)
    assert observation.details["probe_component"] == component
    assert observation.details["component_source"]["source_id"] == source_id
    assert observation.details["source_roles_kept_distinct"] is True
    assert calls[0][0].component == component
    assert calls[0][0].minimum_interval == 0.3
    assert calls[0][1]["access_decision"] == {
        "limits": {"minimum_interval_seconds": 0.3}
    }
    assert calls[0][1]["log_results"] is False


def test_dc_opinions_probe_separates_stable_contract_from_rolling_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    rolling = {
        "page_total_items": 16_313,
        "page_total_pages": 1_632,
        "pdf_size_bytes": 45_572,
    }
    fixture = Path(
        "tests/fixtures/public_records/dc_opinions/list_page.html"
    ).read_text(encoding="utf-8")
    opinion = dict(
        query_dc_opinions.parse_page(
            fixture,
            source_url=query_dc_opinions.INDEX_URL,
            requested_page=0,
            selected_type="Opinions",
        ).records[0]
    )

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        record = {
            **opinion,
            "probe": {
                **rolling,
                "pdf_sha256": "d" * 64,
                "pdf_media_type": "application/pdf",
            },
        }
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(record,),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_dc_opinions",
        fake_execute,
    )
    context = ProbeContext(
        source_id=DC_OPINIONS_SOURCE,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.3}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_dc_opinions(context)
    rolling["page_total_items"] = 16_314
    rolling["page_total_pages"] = 1_633
    rolling["pdf_size_bytes"] = 45_600
    second = probe_dc_opinions(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    stable = first.details["stable_contract"]
    assert stable["index_url"] == query_dc_opinions.INDEX_URL
    assert stable["native_page_size"] == 10
    assert stable["native_pagination"] == "zero_based_page"
    assert stable["publication_semantics"] == {
        "opinions": "court_hosted_pdf_when_linked",
        "mojs": "index_metadata_without_court_published_full_text",
    }
    assert calls[0][0].command == "probe"
    assert calls[0][0].minimum_interval == 0.3
    assert calls[0][1] == {"log_results": False}

    spec = HANDLER_REGISTRY[DC_OPINIONS_SOURCE]
    assert spec.handler is probe_dc_opinions
    assert spec.expected_requests == 2
    assert spec.sentinel_record_count == 1


@pytest.mark.parametrize(
    ("source_id", "expected_command", "expected_requests"),
    [
        (
            query_dc_superior_calendar.TODAY_SOURCE_ID,
            "probe",
            5,
        ),
        (
            query_dc_superior_calendar.CRIMINAL_SOURCE_ID,
            "filters",
            1,
        ),
        (
            query_dc_superior_calendar.TAX_SOURCE_ID,
            "artifacts",
            1,
        ),
        (
            query_dc_superior_calendar.APPEALS_SOURCE_ID,
            "appeals",
            1,
        ),
    ],
)
def test_dc_calendar_component_probe_keeps_contract_separate_from_rolling_rows(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    expected_command: str,
    expected_requests: int,
) -> None:
    calls = []
    rolling_count = 3

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        command_sources = {
            "probe": query_dc_superior_calendar.TODAY_SOURCE_ID,
            "filters": query_dc_superior_calendar.CRIMINAL_SOURCE_ID,
            "artifacts": query_dc_superior_calendar.TAX_SOURCE_ID,
            "appeals": query_dc_superior_calendar.APPEALS_SOURCE_ID,
        }
        selected_source = command_sources[args.command]
        if args.command == "probe":
            record = {
                "source_id": selected_source,
                "record_kind": "court_calendar_source_probe",
                "operations": {
                    "today_html": {
                        "state": "ok",
                        "returned_rows": rolling_count,
                        "schema_fingerprint": "today-schema",
                    }
                },
            }
        elif args.command == "filters":
            record = {
                "source_id": selected_source,
                "record_kind": "court_calendar_filter_taxonomy",
                "calendar": "criminal",
                "filters": {"text_fields": ["defendant"]},
            }
        else:
            record = {
                "source_id": selected_source,
                "record_kind": "court_calendar_artifact",
                "artifact_type": "calendar_pdf",
                "calendar_year": 2026,
                "document_url": "https://www.dccourts.gov/calendar.pdf",
            }
        query = query_dc_superior_calendar.PublicRecordsQuery(
            source=query_dc_superior_calendar.SOURCE_METADATA_BY_ID[selected_source],
            jurisdiction=query_dc_superior_calendar.JURISDICTION,
            query=query_dc_superior_calendar.QueryMetadata(
                operation=args.command,
                parameters={},
            ),
        )
        return PublicRecordsResult.success(query, [record])

    monkeypatch.setattr(
        public_records_monitor,
        "execute_dc_superior_calendar",
        fake_execute,
    )
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.4}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_dc_calendar_component(context)
    rolling_count = 4
    second = probe_dc_calendar_component(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"]["source"]["source_id"] == source_id
    assert (
        first.details["stable_contract"]["endpoint"]
        == (public_records_monitor.DC_CALENDAR_PROBE_ENDPOINTS[source_id])
    )
    assert calls[0][0].command == expected_command
    assert calls[0][0].retry_attempts == 2
    assert calls[0][0].minimum_interval == 0.4
    assert calls[0][1] == {"log_results": False}

    spec = HANDLER_REGISTRY[source_id]
    assert spec.handler is probe_dc_calendar_component
    assert spec.expected_requests == expected_requests
    assert spec.sentinel_record_count == 1


@pytest.mark.parametrize(
    ("source_id", "expected_command", "expected_requests"),
    [
        (
            query_fresno_superior_court.FAMILY_SOURCE_ID,
            "probe",
            8,
        ),
        (
            query_fresno_superior_court.PORTAL_SOURCE_ID,
            "portal",
            2,
        ),
        (
            query_fresno_superior_court.CALENDAR_SOURCE_ID,
            "calendar-index",
            1,
        ),
        (
            query_fresno_superior_court.RULINGS_SOURCE_ID,
            "rulings-index",
            1,
        ),
        (
            query_fresno_superior_court.PROBATE_SOURCE_ID,
            "probate-notes",
            2,
        ),
    ],
)
def test_fresno_component_probe_separates_contract_from_rolling_content(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    expected_command: str,
    expected_requests: int,
) -> None:
    calls = []
    rolling_value = 3

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        command_sources = {
            "probe": query_fresno_superior_court.FAMILY_SOURCE_ID,
            "portal": query_fresno_superior_court.PORTAL_SOURCE_ID,
            "calendar-index": query_fresno_superior_court.CALENDAR_SOURCE_ID,
            "rulings-index": query_fresno_superior_court.RULINGS_SOURCE_ID,
            "probate-notes": query_fresno_superior_court.PROBATE_SOURCE_ID,
        }
        selected_source = command_sources[args.command]
        record_kinds = {
            "probe": "source_probe",
            "portal": "portal_observation",
            "calendar-index": "document_artifact",
            "rulings-index": "document_artifact",
            "probate-notes": "probate_examiner_note",
        }
        record = {
            "source_id": selected_source,
            "record_kind": record_kinds[args.command],
            "canonical_ref": f"FRESNO:{args.command}",
            "publication_date": f"2026-07-{rolling_value:02d}",
            "case_number": ("19CEPR00967" if args.command == "probate-notes" else None),
            "source_url": (f"https://www.fresno.courts.ca.gov/{rolling_value}.pdf"),
        }
        if args.command == "probe":
            record["portal"] = {"visible_registration_field_count": rolling_value}
        query = query_fresno_superior_court.PublicRecordsQuery(
            source=query_fresno_superior_court.SOURCE_METADATA[selected_source],
            jurisdiction=query_fresno_superior_court.JURISDICTION,
            query=query_fresno_superior_court.QueryMetadata(
                operation=args.command,
                parameters={},
            ),
        )
        return PublicRecordsResult.success(query, [record])

    monkeypatch.setattr(
        public_records_monitor,
        "execute_fresno_superior_court",
        fake_execute,
    )
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.35}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_fresno_court_component(context)
    rolling_value = 4
    second = probe_fresno_court_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"]["source"]["source_id"] == source_id
    assert calls[0][0].command == expected_command
    assert calls[0][0].max_attempts == 2
    assert calls[0][0].minimum_interval == 0.35
    assert calls[0][1] == {"log_results": False}

    spec = HANDLER_REGISTRY[source_id]
    assert spec.handler is probe_fresno_court_component
    assert spec.expected_requests == expected_requests
    assert spec.sentinel_record_count == 1


@pytest.mark.parametrize(
    ("source_id", "expected_command", "expected_requests"),
    [
        (
            query_orange_county_court.SOURCE_FAMILY_ID,
            "probe",
            5,
        ),
        (
            query_orange_county_court.CALENDAR_SOURCE_ID,
            "calendar",
            2,
        ),
        *[
            (source_id, "ruling-index", 1)
            for source_id in (query_orange_county_court.RULING_SOURCE_IDS.values())
        ],
    ],
)
def test_orange_county_component_probe_separates_contract_from_rolling_content(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    expected_command: str,
    expected_requests: int,
) -> None:
    calls = []
    rolling_value = 3

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        if args.command == "probe":
            selected_source = query_orange_county_court._family_source()
            record = {
                "source_id": query_orange_county_court.SOURCE_FAMILY_ID,
                "record_kind": "source_probe",
                "canonical_ref": f"OC-PROBE:{rolling_value}",
                "retrieved_at": "2026-07-30T12:00:00Z",
                "calendar": {"one_day_civil_total": rolling_value},
                "tentative_rulings": {
                    "current_directory_counts": {
                        "civil": rolling_value,
                        "family": 0,
                        "probate": 6,
                    }
                },
            }
        elif args.command == "calendar":
            selected_source = query_orange_county_court.CALENDAR_SOURCE
            record = {
                "source_id": query_orange_county_court.CALENDAR_SOURCE_ID,
                "record_kind": "court_hearing",
                "canonical_ref": f"OC-HEARING:{rolling_value}",
                "retrieved_at": "2026-07-30T12:00:00Z",
                "case": {"case_number": f"30-2026-{rolling_value:08d}"},
                "hearing": {"date": "2026-07-30"},
            }
        else:
            selected_source = query_orange_county_court._ruling_source(args.division)
            record = {
                "source_id": selected_source.source_id,
                "record_kind": "tentative_ruling_artifact_index",
                "canonical_ref": f"OC-RULING:{rolling_value}",
                "retrieved_at": "2026-07-30T12:00:00Z",
                "department": "C44",
                "artifact_url": (
                    f"https://www.occourts.org/rulings/{rolling_value}.pdf"
                ),
            }
        query = query_orange_county_court._query(
            selected_source,
            args.command,
            {},
        )
        return PublicRecordsResult.success(query, [record])

    monkeypatch.setattr(
        query_orange_county_court,
        "execute",
        fake_execute,
    )
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.35}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_orange_county_court_component(context)
    rolling_value = 4
    second = probe_orange_county_court_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"]["source"]["source_id"] == source_id
    assert calls[0][0].command == expected_command
    assert calls[0][0].retry_attempts == 2
    assert calls[0][0].minimum_interval == 0.35
    assert calls[0][1] == {"log_results": False}
    assert first.details["rolling_observation"] != second.details["rolling_observation"]

    spec = HANDLER_REGISTRY[source_id]
    assert spec.handler is probe_orange_county_court_component
    assert spec.expected_requests == expected_requests
    assert spec.sentinel_record_count == 1


@pytest.mark.parametrize(
    ("source_id", "expected_command", "expected_requests"),
    [
        (
            query_riverside_court.CALENDAR_SOURCE_ID,
            "calendar",
            2,
        ),
        (
            query_riverside_court.RULING_SOURCE_ID,
            "ruling-index",
            1,
        ),
    ],
)
def test_riverside_component_probe_separates_contract_from_rolling_content(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    expected_command: str,
    expected_requests: int,
) -> None:
    calls = []
    rolling_value = 3

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        if args.command == "calendar":
            selected_source = query_riverside_court.CALENDAR_SOURCE
            record = {
                "source_id": query_riverside_court.CALENDAR_SOURCE_ID,
                "record_kind": "court_calendar_event",
                "canonical_ref": f"RIVERSIDE-CALENDAR:{rolling_value}",
                "case_number": f"PRRI26010{rolling_value:02d}",
                "department": "8",
                "hearing": {
                    "date": "2026-07-30",
                    "date_time": "2026-07-30T08:30:00-07:00",
                },
                "retrieved_at": "2026-07-30T12:00:00Z",
            }
        else:
            selected_source = query_riverside_court.RULING_SOURCE
            record = {
                "source_id": query_riverside_court.RULING_SOURCE_ID,
                "record_kind": "tentative_ruling_artifact_index",
                "canonical_ref": f"RIVERSIDE-RULING:{rolling_value}",
                "department": "PS1",
                "artifact_url": (
                    "https://www.riverside.courts.ca.gov/system/files/"
                    f"2026-07/ps1-{rolling_value}.pdf"
                ),
                "artifact_path_month": "2026-07",
                "artifact_filename_date_candidates": ["2026-07-30"],
                "retrieved_at": "2026-07-30T12:00:00Z",
            }
        query = query_riverside_court._query(
            selected_source,
            args.command,
            {},
            metadata={"coverage": {"returned": rolling_value}},
        )
        return PublicRecordsResult.success(query, [record])

    monkeypatch.setattr(query_riverside_court, "execute", fake_execute)
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.35}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_riverside_court_component(context)
    rolling_value = 4
    second = probe_riverside_court_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"]["source"]["source_id"] == source_id
    assert calls[0][0].command == expected_command
    assert calls[0][0].retry_attempts == 2
    assert calls[0][0].minimum_interval == 0.35
    assert calls[0][1] == {"log_results": False}
    assert first.details["rolling_observation"] != second.details["rolling_observation"]

    spec = HANDLER_REGISTRY[source_id]
    assert spec.handler is probe_riverside_court_component
    assert spec.expected_requests == expected_requests
    assert spec.sentinel_record_count == 1


def test_qld_ecourts_probe_separates_contract_from_rolling_case_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    rolling_value = 1

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        query = query_qld_ecourts.build_query(args)
        record = {
            "record_type": "court_case",
            "canonical_ref": query_qld_ecourts.qld_canonical_ref(
                "SUPRE",
                "BRISB",
                "6819/11",
            ),
            "evidence_ref": query_qld_ecourts.qld_evidence_ref(
                "SUPRE",
                "BRISB",
                "6819/11",
            ),
            "file_number": "6819/11",
            "case_name": f"FIXTURE CASE {rolling_value}",
            "court_code": "SUPRE",
            "court_name": "Supreme",
            "originating_location_code": "BRISB",
            "originating_location": "Brisbane",
            "current_location_code": "BRISB",
            "current_location": "Brisbane",
            "date_filed_iso": "2011-08-05",
            "parties": [
                {
                    "last_company_name": f"PARTY {index}",
                    "first_name": None,
                    "acn": None,
                    "party_role": "Defendant",
                    "representative": None,
                }
                for index in range(rolling_value)
            ],
            "events": [],
            "documents": [],
            "related_files": [],
            "status_notices": [],
            "source_url": query_qld_ecourts.DETAIL_URL,
            "schema_fingerprint": "a" * 64,
        }
        return PublicRecordsResult.success(query, [record])

    monkeypatch.setattr(query_qld_ecourts, "execute", fake_execute)
    context = ProbeContext(
        source_id=query_qld_ecourts.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.4}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_qld_ecourts(context)
    rolling_value = 2
    second = probe_qld_ecourts(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["stable_contract"]["native_result_ceiling"] == 500
    assert first.details["stable_contract"]["case_identity_fields"] == [
        "court_code",
        "originating_location_code",
        "file_number",
    ]
    assert calls[0][0].command == "probe"
    assert calls[0][0].minimum_interval == 0.4
    assert calls[0][1] == {"log_results": False}

    spec = HANDLER_REGISTRY[query_qld_ecourts.SOURCE_ID]
    assert spec.handler is probe_qld_ecourts
    assert spec.expected_requests == 1
    assert spec.sentinel_record_count == 1


@pytest.mark.parametrize(
    ("source_id", "expected_command"),
    [
        (query_philadelphia_property.SOURCE_ID, "probe"),
        (query_philadelphia_property.HISTORY_SOURCE_ID, "history"),
        (query_philadelphia_property.DOR_SOURCE_ID, "parcel-shape"),
    ],
)
def test_philadelphia_property_component_probe_separates_transport_contract(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    expected_command: str,
) -> None:
    calls = []
    rolling_value = 199_600

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        if args.command == "probe":
            record = {
                "source_id": query_philadelphia_property.SOURCE_ID,
                "record_type": "current_property_assessment_observation",
                "canonical_ref": "PHILA-OPA:341086700",
                "native_parcel_id": "341086700",
                "pin": "1001666377",
                "registry_number": "062N200131",
                "assessment": {"market_value": rolling_value},
                "source_snapshot": {
                    "reported_total_matches": 1,
                    "data_last_edit_epoch_ms": rolling_value,
                },
            }
        elif args.command == "history":
            record = {
                "source_id": query_philadelphia_property.HISTORY_SOURCE_ID,
                "record_type": "annual_property_assessment_observation",
                "canonical_ref": "PHILA-HISTORY:341086700",
                "native_parcel_id": "341086700",
                "assessment_year": "2023",
                "object_id": 2_762_703,
                "assessment": {"market_value": rolling_value},
                "source_snapshot": {
                    "reported_total_matches": rolling_value,
                },
            }
        else:
            record = {
                "source_id": query_philadelphia_property.DOR_SOURCE_ID,
                "record_type": "deed_description_parcel_map_observation",
                "canonical_ref": "PHILA-DOR:062N200131",
                "map_registry_number": "062N200131",
                "base_registry_number": "062N200131",
                "pin": "1001666377",
                "source_shape_area": rolling_value,
                "source_snapshot": {
                    "data_last_edit_epoch_ms": rolling_value,
                },
            }
        return PublicRecordsResult.success(
            query_philadelphia_property.build_query(args),
            [record],
        )

    monkeypatch.setattr(
        query_philadelphia_property,
        "execute",
        fake_execute,
    )
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.35}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_philadelphia_property_component(context)
    rolling_value += 1
    second = probe_philadelphia_property_component(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"]["source"]["source_id"] == source_id
    assert (
        "not corroboration" in first.details["stable_contract"]["transport_semantics"]
    )
    assert calls[0][0].command == expected_command
    assert calls[0][0].retry_attempts == 2
    assert calls[0][0].minimum_interval == 0.35
    assert calls[0][1] == {"log_results": False}
    assert first.details["rolling_observation"] != second.details["rolling_observation"]

    spec = HANDLER_REGISTRY[source_id]
    assert spec.handler is probe_philadelphia_property_component
    assert spec.expected_requests == 4
    assert spec.sentinel_record_count == 1


@pytest.mark.parametrize(
    ("adapter", "expected_requests"),
    [
        (query_wisconsin_parcels, 5),
        (query_new_jersey_parcels, 7),
    ],
)
def test_statewide_parcel_probe_separates_contract_from_rolling_release(
    monkeypatch: pytest.MonkeyPatch,
    adapter,
    expected_requests: int,
) -> None:
    calls = []
    rolling_value = 1

    def fake_execute(args):
        calls.append(args)
        if adapter is query_wisconsin_parcels:
            record = {
                "source_id": adapter.SOURCE_ID,
                "record_type": "statewide_annual_parcel_observation",
                "canonical_ref": "PROPERTY:WI:FIXTURE",
                "native_parcel_id": "008015540000",
                "object_id": rolling_value,
                "owner_visibility": {"state": "published"},
                "situs_address": {"raw": f"{rolling_value} MAIN ST"},
                "source_snapshot": {
                    "compatible_schema_fingerprint": "a" * 64,
                    "dataset_release": f"V12 fixture {rolling_value}",
                    "data_last_edit_epoch_ms": rolling_value,
                },
            }
        else:
            record = {
                "source_id": adapter.SOURCE_ID,
                "record_type": "statewide_parcel_modiv_observation",
                "canonical_ref": "PROPERTY:NJ:FIXTURE",
                "native_parcel_id": adapter.PROBE_PIN,
                "object_id": 1,
                "owner_observation": {"visibility_state": "redacted_by_source"},
                "modiv_join": {"state": "matched_to_modiv"},
                "situs_address": {"raw": f"{rolling_value} MAPLE HILL DR"},
                "source_snapshot": {
                    "compatible_schema_fingerprint": "b" * 64,
                    "data_last_edit_epoch_ms": rolling_value,
                    "resolved_layer_url": adapter.DEFAULT_LAYER_URL,
                },
            }
        return PublicRecordsResult.success(
            adapter.build_query(args),
            [record],
        )

    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=adapter.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.3}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_statewide_parcel_source(context)
    rolling_value = 2
    second = probe_statewide_parcel_source(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["stable_contract"]["required_fields"] == list(
        adapter.REQUIRED_FIELDS
    )
    assert calls[0].command == "probe"
    assert calls[0].retry_attempts == 2
    assert calls[0].minimum_interval == 0.3

    spec = HANDLER_REGISTRY[adapter.SOURCE_ID]
    assert spec.handler is probe_statewide_parcel_source
    assert spec.expected_requests == expected_requests
    assert spec.sentinel_record_count == 1


def test_new_jersey_sr1a_probe_separates_contract_from_release_validators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = query_new_jersey_sr1a
    release = adapter.Release(
        release_id="sr1a-ytd-2026",
        year=2026,
        series="year_to_date",
        label="Current SR1A",
        url=("https://www.nj.gov/treasury/taxation/lpt/statdata/YTDSR1A2026.zip"),
    )
    snapshot = adapter.ManifestSnapshot(
        releases=(release,),
        layout_url=adapter.LAYOUT_URL,
    )
    calls = []
    rolling_value = 1

    def fake_fetch_release_manifest(**kwargs):
        calls.append(("manifest", kwargs))
        return snapshot

    def fake_execute(args, **kwargs):
        calls.append(("execute", args, kwargs))
        record = {
            **release.manifest_record(snapshot),
            "probe": {
                "format_hint": "zip",
                "etag": f'"fixture-{rolling_value}"',
                "last_modified": f"rolling-{rolling_value}",
                "content_length": 1_000 + rolling_value,
            },
        }
        return PublicRecordsResult.success(
            adapter.build_query(args),
            [record],
        )

    monkeypatch.setattr(
        adapter,
        "fetch_release_manifest",
        fake_fetch_release_manifest,
    )
    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=adapter.SOURCE_ID,
        catalog_decision={},
        timeout=5,
        max_attempts=2,
        sample_bytes=64,
    )

    first = probe_new_jersey_sr1a(context)
    rolling_value = 2
    second = probe_new_jersey_sr1a(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["stable_contract"]["schema"] == adapter.DECLARED_SCHEMA
    assert "release_id" in first.details["stable_contract"]["release_occurrence_fields"]
    assert calls[0] == (
        "manifest",
        {"timeout": 5, "retry_attempts": 2},
    )
    execute_call = calls[1]
    assert execute_call[0] == "execute"
    assert execute_call[1].command == "probe"
    assert execute_call[1].range_bytes == 64
    assert execute_call[2] == {"manifest_snapshot": snapshot}

    spec = HANDLER_REGISTRY[adapter.SOURCE_ID]
    assert spec.handler is probe_new_jersey_sr1a
    assert spec.expected_requests == 3
    assert spec.sentinel_record_count == 1


def test_palm_beach_recorder_probe_keeps_image_state_out_of_contract_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = query_palm_beach_official_records
    rolling_value = 1
    calls = []

    def fake_execute(args):
        calls.append(args)
        record = {
            "source_id": adapter.SOURCE_ID,
            "record_kind": "source_health_check",
            "native_document_id": "live-sentinel",
            "status": "ok",
            "sentinel": {
                "instrument_number": adapter.SENTINEL_INSTRUMENT,
                "document_id": adapter.SENTINEL_DOCUMENT_ID,
                "book": str(adapter.SENTINEL_BOOK),
                "page": str(adapter.SENTINEL_PAGE),
                "document_type": adapter.SENTINEL_DOC_TYPE,
                "image_media_type": "image/png",
                "image_byte_count": 100 + rolling_value,
                "image_sha256": f"{rolling_value:064x}",
            },
            "broad_search_captcha_required": True,
            "request_count": 9,
            "routes": {
                "home": adapter.HOME_URL,
                "instrument": adapter.DIRECT_CFN_URL,
                "book_page": adapter.DIRECT_BOOK_PAGE_URL,
                "document_details": adapter.DOCUMENT_DETAILS_URL,
                "document_information": adapter.DOCUMENT_INFORMATION_URL,
                "image": adapter.IMAGE_URL,
            },
        }
        return PublicRecordsResult.success(
            adapter.build_query(args),
            [record],
        )

    monkeypatch.setattr(adapter, "execute", fake_execute)
    context = ProbeContext(
        source_id=adapter.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.4}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_palm_beach_official_records(context)
    rolling_value = 2
    second = probe_palm_beach_official_records(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    contract = first.details["stable_contract"]
    assert contract["record_identity_field"] == "instrument_number"
    assert contract["portal_locator_field"] == "native_document_id"
    assert {item["source_id"] for item in contract["complementary_sources"]} >= {
        "us-fl-palm-beach-official-records-daily-index",
        "us-fl-palm-beach-property-appraiser",
        "us-fl-palm-beach-tax-deeds",
    }
    assert calls[0].command == "probe"
    assert calls[0].minimum_interval == 0.4

    spec = HANDLER_REGISTRY[adapter.SOURCE_ID]
    assert spec.handler is probe_palm_beach_official_records
    assert spec.expected_requests == 9
    assert spec.sentinel_record_count == 1


def test_arlington_property_probe_uses_adapter_schema_and_rpc_identity(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            status=ResultStatus.OK,
            records=(
                {
                    "canonical_ref": (
                        "PROPERTY:us-va-arlington-property-map/51013/parcel/03001009"
                    ),
                    "response_schema_fingerprint": "a" * 64,
                    "rpc_number": "03001009",
                    "parcel_id": "03001009",
                    "object_id": 1,
                    "source_last_updated": "2026-07-29T00:00:00Z",
                },
            ),
            errors=(),
            warnings=(),
        )

    monkeypatch.setattr(
        public_records_monitor,
        "execute_arlington_property",
        fake_execute,
    )

    observation = probe_arlington_property(
        ProbeContext(
            source_id=ARLINGTON_PROPERTY_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.schema_sha256 == "a" * 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["rpc_number"] == "03001009"
    assert calls[0][0].command == "probe"
    assert calls[0][1]["log_results"] is False


def test_bexar_historical_probe_closes_client_on_department_drift(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _BexarHistoricalProbeClient()
    bootstrap = client.bootstrap

    def missing_department():
        value = bootstrap()
        value.department_codes = ("NR",)
        return value

    monkeypatch.setattr(client, "bootstrap", missing_department)
    monkeypatch.setattr(
        public_records_monitor,
        "KofilePublicSearchClient",
        lambda *_args, **_kwargs: client,
    )

    with pytest.raises(ValueError, match="department HC"):
        probe_bexar_historical_courts(
            ProbeContext(
                source_id=BEXAR_HISTORICAL_SOURCE,
                catalog_decision={"limits": {}},
                timeout=5,
                max_attempts=1,
                sample_bytes=None,
            )
        )

    assert client.closed is True


class _ReevesRecordsProbeClient:
    def __init__(self, *_args, **_kwargs):
        self.calls = []
        self.closed = False

    def bootstrap(self):
        self.calls.append(("bootstrap", {}))
        return type(
            "Bootstrap",
            (),
            {
                "state": {
                    "configuration": {
                        "tenantId": "48389",
                        "departments": [{"code": "RP"}],
                    }
                },
                "tenant_id": "48389",
                "department_codes": ("RP",),
                "department_date_ranges": {
                    "RP": {
                        "recordedDateRange": "18840101,20260720",
                    }
                },
            },
        )()

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return type(
            "Page",
            (),
            {
                "records": (
                    {
                        "id": 20798096,
                        "instrumentNumber": "18-06481",
                        "rsId": "208461",
                    },
                ),
                "total_count": 1,
                "offset": 0,
                "limit": 1,
                "response_type": ("@kofile/FETCH_DOCUMENTS_FULFILLED/v6"),
            },
        )()

    def fetch_document(self, doc_id):
        self.calls.append(("fetch_document", {"doc_id": doc_id}))
        return {
            "id": doc_id,
            "instrumentNumber": "18-06481",
            "rsId": "208461",
            "recordedDate": "4/19/2018",
            "metadataVersion": 10,
            "docVersion": 7,
            "parties": [
                {
                    "partyTypeCode": "D",
                    "name": "THREE RIVERS ACQUISITION III LLC",
                },
                {
                    "partyTypeCode": "I",
                    "name": "APR OPERATING LLC",
                },
            ],
        }

    def close(self):
        self.closed = True


def test_reeves_records_probe_covers_bootstrap_search_and_detail(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _ReevesRecordsProbeClient()
    monkeypatch.setattr(
        public_records_monitor,
        "KofilePublicSearchClient",
        lambda *_args, **_kwargs: client,
    )

    observation = probe_reeves_records(
        ProbeContext(
            source_id=REEVES_RECORDS_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["tenant_id"] == "48389"
    assert observation.details["department"] == "RP"
    assert observation.details["doc_id"] == 20798096
    assert observation.details["instrument_number"] == "18-06481"
    assert observation.details["requests_made"] == 3
    assert [name for name, _details in client.calls] == [
        "bootstrap",
        "search",
        "fetch_document",
    ]
    assert client.calls[1][1]["search_value"] == "18-06481"
    assert client.closed is True


class _GovOSRecorderProbeClient:
    page_content = b"\x89PNG\r\n\x1a\nmonitor-fixture"

    def __init__(self, *_args, **_kwargs):
        self.calls = []
        self.closed = False
        self.request_count = 6

    def bootstrap(self):
        self.calls.append(("bootstrap", {}))
        return type(
            "Bootstrap",
            (),
            {
                "state": {
                    "configuration": {
                        "tenantId": "42011",
                        "departments": [
                            {"code": "RP"},
                            {"code": "MISC"},
                        ],
                    }
                },
                "tenant_id": "42011",
                "department_codes": ("RP", "MISC"),
                "department_date_ranges": {
                    "RP": {
                        "recordedDateRange": "16000101,20260729",
                    }
                },
            },
        )()

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return type(
            "Page",
            (),
            {
                "records": (
                    {
                        "id": 203097905,
                        "instrumentNumber": "2024000062",
                        "rsId": "5177273",
                    },
                ),
                "total_count": 1,
                "offset": 0,
                "limit": 1,
                "response_type": ("@kofile/FETCH_DOCUMENTS_FULFILLED/v6"),
            },
        )()

    def fetch_document(self, doc_id):
        self.calls.append(("fetch_document", {"doc_id": doc_id}))
        return {
            "id": doc_id,
            "docNumber": "2024000062",
            "rsId": "5177273",
            "recordedDate": "1/2/2024",
            "docType": "ACT3",
            "pageCount": 3,
            "parties": [
                {
                    "partyTypeCode": "D",
                    "name": "EXAMPLE OWNER",
                }
            ],
        }

    def fetch_page_image(self, doc_id, page_number):
        self.calls.append(
            (
                "fetch_page_image",
                {"doc_id": doc_id, "page_number": page_number},
            )
        )
        return type(
            "PageImage",
            (),
            {
                "content": self.page_content,
                "media_type": "image/png",
            },
        )()

    def close(self):
        self.closed = True


def test_govos_recorder_probe_checks_search_detail_and_page_digest(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _GovOSRecorderProbeClient()
    tenant = public_records_monitor.GOVOS_RECORDER_TENANTS[GOVOS_RECORDER_SOURCE]
    monkeypatch.setitem(
        public_records_monitor.GOVOS_RECORDER_TENANTS,
        GOVOS_RECORDER_SOURCE,
        replace(
            tenant,
            probe_page_sha256=hashlib.sha256(client.page_content).hexdigest(),
        ),
    )
    monkeypatch.setattr(
        public_records_monitor,
        "ReevesRecordsClient",
        lambda *_args, **_kwargs: client,
    )

    observation = probe_govos_recorder(
        ProbeContext(
            source_id=GOVOS_RECORDER_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert observation.details["tenant_id"] == "42011"
    assert observation.details["doc_id"] == 203097905
    assert observation.details["instrument_number"] == "2024000062"
    assert observation.details["page_count"] == 3
    assert observation.details["requests_made"] == 6
    assert (
        observation.artifact_sha256 == hashlib.sha256(client.page_content).hexdigest()
    )
    assert [name for name, _details in client.calls] == [
        "bootstrap",
        "search",
        "fetch_document",
        "fetch_page_image",
    ]
    assert client.closed is True


@pytest.mark.parametrize(
    ("error", "expected_status"),
    (
        (
            public_records_monitor.KofileAccessError(
                "restricted",
                code="fixture_access",
                retryable=False,
            ),
            "restricted",
        ),
        (
            public_records_monitor.KofileRateLimitError(
                "limited",
                code="fixture_rate",
                retryable=True,
            ),
            "rate_limited",
        ),
        (
            public_records_monitor.KofileSourceChangedError(
                "changed",
                code="fixture_schema",
                retryable=False,
            ),
            "source_changed",
        ),
    ),
)
def test_kofile_monitor_errors_keep_structured_status(
    error,
    expected_status,
):
    observation = public_records_monitor._exception_observation(
        error,
        endpoint="wss://example.gov/ws",
        latency_ms=1.0,
    )

    assert observation.status == expected_status
    assert observation.details["error"]["code"] == error.code
    assert observation.details["error"]["retryable"] == error.retryable


class _OrangeCalendarProbeClient:
    def __init__(self, **_kwargs):
        self.closed = False

    def probe(self):
        return type(
            "Page",
            (),
            {
                "schema_fingerprint": "a" * 64,
                "rows": (object(), object()),
                "total_count": 2,
                "columns": (
                    "Case Number",
                    "Hearing Date",
                    "Time Slot",
                    "Location",
                    "Name",
                    "Judge",
                    "Status",
                ),
                "request_parameters": {
                    "hearDate": "2026-07-29",
                    "caseNumber": "",
                    "firstName": "",
                    "lastName": "",
                    "judge": "",
                },
            },
        )()

    def close(self):
        self.closed = True


def test_orange_calendar_probe_preserves_complete_daily_table(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _OrangeCalendarProbeClient()
    monkeypatch.setattr(
        public_records_monitor,
        "OrangeCountyCourtsClient",
        lambda **_kwargs: client,
    )

    observation = probe_orange_hearing_calendar(
        ProbeContext(
            source_id=ORANGE_CALENDAR_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 2
    assert observation.schema_sha256 == "a" * 64
    assert observation.details["source_total_hearings"] == 2
    assert observation.details["client_side_pagination"] is True
    assert client.closed is True


class _LosAngelesCivilProbeClient:
    def __init__(self, rolling_count: int, **kwargs):
        self.rolling_count = rolling_count
        self.kwargs = kwargs
        self.closed = False

    def probe(self):
        selection = query_los_angeles_court.TentativeSelection(
            native_value="ALH,3,07/30/2026",
            label="Alhambra Courthouse, Dept. 3, 07/30/2026",
            location_code="ALH",
            department="3",
            hearing_date="07/30/2026",
            hearing_date_iso="2026-07-30",
        )
        return SimpleNamespace(
            case_search=SimpleNamespace(schema_fingerprint="1" * 64),
            case_summary=SimpleNamespace(
                schema_fingerprint="2" * 64,
                response_sha256=f"{self.rolling_count:064x}",
                case_number=query_los_angeles_court.PROBE_CASE_NUMBER,
                future_hearings=tuple(range(self.rolling_count)),
                parties=(1, 2),
                documents=(1, 2, 3),
                past_proceedings=(1,),
                register_actions=(1, 2, 3, 4),
            ),
            tentative_index=SimpleNamespace(
                schema_fingerprint="3" * 64,
                selections=tuple(selection for _ in range(self.rolling_count)),
            ),
            tentative_selection=selection,
            tentative_result=SimpleNamespace(
                schema_fingerprint="4" * 64,
                response_sha256=f"{self.rolling_count + 1:064x}",
                rulings=tuple(range(self.rolling_count)),
            ),
        )

    def close(self):
        self.closed = True


def test_los_angeles_civil_probe_separates_contract_from_rolling_content(
    monkeypatch: pytest.MonkeyPatch,
):
    clients = []
    rolling_counts = iter((3, 4))

    def client_factory(**kwargs):
        client = _LosAngelesCivilProbeClient(
            next(rolling_counts),
            **kwargs,
        )
        clients.append(client)
        return client

    monkeypatch.setattr(
        public_records_monitor,
        "LosAngelesCourtClient",
        client_factory,
    )
    context = ProbeContext(
        source_id=LOS_ANGELES_CIVIL_SOURCE,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.45}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_los_angeles_civil(context)
    second = probe_los_angeles_civil(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"]["source"]["source_id"] == (
        LOS_ANGELES_CIVIL_SOURCE
    )
    assert first.details["rolling_observation"]["tentative_selection_count"] == 3
    assert second.details["rolling_observation"]["tentative_selection_count"] == 4
    assert clients[0].kwargs["minimum_interval"] == 0.45
    assert clients[0].kwargs["retry_policy"].max_attempts == 2
    assert all(client.closed for client in clients)

    spec = HANDLER_REGISTRY[LOS_ANGELES_CIVIL_SOURCE]
    assert spec.handler is probe_los_angeles_civil
    assert spec.expected_requests == 4
    assert spec.sentinel_record_count == 1


def test_los_angeles_name_index_probe_separates_contract_from_rolling_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    rolling_value = 3

    def fake_execute(args, **kwargs):
        calls.append((args, kwargs))
        query = query_los_angeles_name_index.build_query(args)
        record = {
            "source_id": query_los_angeles_name_index.SOURCE_ID,
            "record_kind": "source_probe",
            "source_url": query_los_angeles_name_index.CIVIL_INDEX_URL,
            "landing": {
                "coverage": [
                    {
                        "case_type": "Unlimited Civil",
                        "source_date_range": f"1983 - 202{rolling_value}",
                    }
                ],
                "result_fields": [
                    "litigant_name",
                    "case_number",
                    "case_type",
                    "filing_date",
                    "filing_location",
                    "available_imaged_document_count",
                ],
                "updated_daily": True,
                "archive_url": query_los_angeles_name_index.ARCHIVES_URL,
                "schema_fingerprint": "1" * 64,
            },
            "fees": {
                "name_search_fees": [
                    {
                        "account_type": "guest",
                        "description": "Name Search",
                        "amount_text": f"${rolling_value}.75",
                        "amount_usd": rolling_value + 0.75,
                    }
                ],
                "schema_fingerprint": f"{rolling_value:064x}",
            },
            "search_form": {
                "method": "post",
                "action_url": query_los_angeles_name_index.SEARCH_URL,
                "field_names": [
                    "LastName",
                    "FirstName",
                    "CompanyName",
                    "Remark",
                    "FilingDateStart",
                    "FilingDateEnd",
                    "__RequestVerificationToken",
                ],
                "remark_max_length": 30,
                "schema_fingerprint": "2" * 64,
            },
            "guest": {
                "services": [
                    {
                        "name": "CivilIndex",
                        "url": query_los_angeles_name_index.CIVIL_INDEX_URL,
                    },
                    {
                        "name": "DocumentImages",
                        "url": query_los_angeles_name_index.DOCUMENT_IMAGES_URL,
                    },
                ],
                "receipt_field_names": [
                    "ReceiptNumber",
                    "Last4CC",
                    "ActionToPerform",
                    "ActionDocumentID",
                    "ActionReceiptNumber",
                    "SecurityKey",
                    "__RequestVerificationToken",
                ],
                "result_availability_statement": (
                    f"Name Search results remain available for {rolling_value} hours."
                ),
                "faq_redo_statement": (
                    f'The "Redo Search" button will only be available for '
                    f"{rolling_value} hours."
                ),
                "schema_fingerprint": "3" * 64,
            },
            "access": {
                "guest_session": "anonymous",
                "query_submission": "same_session_antiforgery_post",
                "result_delivery": "after_payment_confirmation",
                "receipt_recovery": ("receipt_number_plus_last_four_card_digits"),
            },
        }
        return PublicRecordsResult.success(query, [record])

    monkeypatch.setattr(
        query_los_angeles_name_index,
        "execute",
        fake_execute,
    )
    context = ProbeContext(
        source_id=query_los_angeles_name_index.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.45}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_los_angeles_name_index(context)
    rolling_value = 4
    second = probe_los_angeles_name_index(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["stable_contract"]["result_fields"][0] == ("litigant_name")
    assert calls[0][0].minimum_interval == 0.45
    assert calls[0][0].max_attempts == 2
    assert calls[0][1] == {"log_results": False}

    spec = HANDLER_REGISTRY[query_los_angeles_name_index.SOURCE_ID]
    assert spec.handler is probe_los_angeles_name_index
    assert spec.expected_requests == 6
    assert spec.sentinel_record_count == 1


class _LosAngelesTTCProbeClient:
    def __init__(self, rolling_value: int, **kwargs):
        self.rolling_value = rolling_value
        self.kwargs = kwargs
        self.closed = False

    def assessor_exact(self, ain):
        assert ain == query_los_angeles_ttc.PROBE_AIN
        return {
            "AIN": ain,
            "APN": "2004-001-003",
            "OBJECTID": self.rolling_value,
            "Roll_Year": str(2025 + self.rolling_value),
        }

    def payment_bootstrap(self):
        return query_los_angeles_ttc.PaymentBootstrap(
            ajax_url=query_los_angeles_ttc.PAYMENT_AJAX_URL,
            nonce="fixture-nonce",
            script_url=(
                f"{query_los_angeles_ttc.TTC_BASE_URL}PaymentHistory/phf-script.js"
            ),
            schema_fingerprint="1" * 64,
        )

    def payment_page(self, ain, page, *, bootstrap):
        assert page == 1
        assert bootstrap.nonce == "fixture-nonce"
        if ain == query_los_angeles_ttc.INVALID_PROBE_AIN:
            return query_los_angeles_ttc.PaymentPage(
                rows=(),
                meta={},
                native_page=1,
                no_result=True,
                native_state={"status": 404, "title": "Not Found"},
                schema_fingerprint="3" * 64,
            )
        return query_los_angeles_ttc.PaymentPage(
            rows=(
                {
                    "payment_id": "7",
                    "ain": ain,
                    "effective_date": "02/01/2026",
                    "installment_key": "2",
                    "group_number": "1",
                    "tax_paid": "100.00",
                    "penalty_paid": "0.00",
                    "cost_paid": "0.00",
                    "total_paid": "100.00",
                    "tax_year": 2025,
                    "sequence": "1",
                    "group_description": "fixture",
                },
            ),
            meta={
                "totalRecords": self.rolling_value,
                "totalPages": self.rolling_value,
                "lastUpdated": f"2026-07-{20 + self.rolling_value:02d}",
            },
            native_page=1,
            no_result=False,
            native_state=None,
            schema_fingerprint="2" * 64,
        )

    def html(self, url):
        fixture_root = Path("tests/fixtures/public_records/los_angeles_ttc")
        if url == query_los_angeles_ttc.AUCTION_SCHEDULE_URL:
            return (fixture_root / "auction_schedule.html").read_text(encoding="utf-8")
        if url == query_los_angeles_ttc.AUCTION_CONTACT_URL:
            return (fixture_root / "publications.html").read_text(encoding="utf-8")
        raise AssertionError(url)

    def bytes(self, url, *, max_bytes):
        content = f"%PDF-fixture-{self.rolling_value}".encode()
        assert len(content) < max_bytes
        return query_los_angeles_ttc.ResponseArtifact(
            content=content,
            source_url=url,
            headers={"content-type": "application/pdf"},
            status_code=200,
        )

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("source_id", "probe_function", "expected_requests"),
    [
        (
            LOS_ANGELES_ASSESSOR_SOURCE,
            probe_los_angeles_assessor_ain,
            1,
        ),
        (
            LOS_ANGELES_TTC_PAYMENT_SOURCE,
            probe_los_angeles_ttc_payment,
            3,
        ),
        (
            LOS_ANGELES_TTC_SALE_SOURCE,
            probe_los_angeles_ttc_sale,
            3,
        ),
    ],
)
def test_los_angeles_ttc_component_probes_keep_rolling_values_out_of_contract(
    monkeypatch: pytest.MonkeyPatch,
    source_id,
    probe_function,
    expected_requests,
):
    state = {"value": 1}
    clients = []

    def client_factory(**kwargs):
        client = _LosAngelesTTCProbeClient(state["value"], **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(
        query_los_angeles_ttc,
        "LosAngelesTTCClient",
        client_factory,
    )
    monkeypatch.setattr(
        query_los_angeles_ttc,
        "extract_pdf_text",
        lambda _artifact: (
            Path("tests/fixtures/public_records/los_angeles_ttc/sale_results_2025b.txt")
            .read_text(encoding="utf-8")
            .replace("2025B", "2025C")
        ),
    )
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.4}},
        timeout=5,
        max_attempts=2,
        sample_bytes=None,
    )

    first = probe_function(context)
    state["value"] = 2
    second = probe_function(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["requests_made"] == expected_requests
    assert clients[0].kwargs["minimum_interval"] == 0.4
    assert clients[0].kwargs["retry_policy"].max_attempts == 2
    assert all(client.closed for client in clients)

    spec = HANDLER_REGISTRY[source_id]
    assert spec.handler is probe_function
    assert spec.expected_requests == expected_requests
    assert spec.sentinel_record_count == 1


class _LosAngelesProbateProbeClient:
    def __init__(self):
        self.closed = False

    def probe(self):
        return type(
            "Snapshot",
            (),
            {
                "case_search": type(
                    "CaseSearch",
                    (),
                    {
                        "schema_fingerprint": "1" * 64,
                        "courthouse_options": {
                            "": "Select a Courthouse (Optional)",
                            ("ATP;Michael Antonovich Antelope Valley Courthouse"): (
                                "Michael Antonovich Antelope Valley Courthouse"
                            ),
                            "LA;Stanley Mosk Courthouse": ("Stanley Mosk Courthouse"),
                        },
                    },
                )(),
                "case_summary": type(
                    "CaseSummary",
                    (),
                    {
                        "schema_fingerprint": "2" * 64,
                        "case_number": "17STPB02676",
                        "case_title": ("HAMILTON, CLARISSA RUNNELS - DECEDENT"),
                        "filing_date": "3/28/2017",
                        "status": "Closed on 7/20/2020",
                        "future_hearings": (),
                        "parties": tuple(range(10)),
                        "documents": tuple(range(68)),
                        "past_proceedings": tuple(range(18)),
                        "register_actions": tuple(range(86)),
                    },
                )(),
                "notes_search": type(
                    "NotesSearch",
                    (),
                    {"schema_fingerprint": "3" * 64},
                )(),
                "calendar": type(
                    "Calendar",
                    (),
                    {
                        "schema_fingerprint": "4" * 64,
                        "message": (
                            "There are no future hearings scheduled for "
                            "Case Number 17STPB02676 in the next 266 days "
                            "(180 business days)."
                        ),
                    },
                )(),
            },
        )()

    def close(self):
        self.closed = True


def test_los_angeles_probate_probe_fingerprints_all_anonymous_contracts(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _LosAngelesProbateProbeClient()
    monkeypatch.setattr(
        public_records_monitor,
        "LosAngelesProbateClient",
        lambda **_kwargs: client,
    )

    observation = probe_los_angeles_probate(
        ProbeContext(
            source_id=LOS_ANGELES_PROBATE_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["case_number"] == "17STPB02676"
    assert observation.details["counts"] == {
        "future_hearings": 0,
        "parties": 10,
        "documents": 68,
        "past_proceedings": 18,
        "register_actions": 86,
    }
    assert (
        observation.details["courthouse_options"]["LA;Stanley Mosk Courthouse"]
        == "Stanley Mosk Courthouse"
    )
    assert observation.details["requests_made"] == 5
    assert client.closed is True


def test_palm_beach_probe_checks_public_guest_search_controls(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[list[str], float]] = []

    def fake_helper(arguments, timeout):
        calls.append((list(arguments), timeout))
        return {
            "ok": True,
            "source_url": ("https://appsgp.mypalmbeachclerk.com/ecaseview/Search"),
            "title": "eCaseView",
            "case_search_box_count": 1,
            "party_search_box_count": 1,
        }

    monkeypatch.setattr(
        public_records_monitor,
        "run_palm_beach_browser_helper",
        fake_helper,
    )

    observation = probe_palm_beach_courts(
        ProbeContext(
            source_id=PALM_BEACH_SOURCE,
            catalog_decision={"limits": {}},
            timeout=45,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert calls == [(["probe"], 45)]
    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert observation.details["case_search_box_count"] == 1
    assert observation.details["party_search_box_count"] == 1
    assert observation.details["browser_session"] == "headed_guest"


class _PimaProbeClient:
    def __init__(self, **_kwargs):
        self.request_count = 0
        self.closed = False

    def bootstrap(self):
        self.request_count = 2
        return type(
            "Form",
            (),
            {
                "search_url": ("https://wwww.cosc.pima.gov/PublicDocs/search2a.aspx"),
                "hidden_fields": {
                    "__VIEWSTATE": "opaque",
                    "__VIEWSTATEGENERATOR": "opaque",
                    "__EVENTVALIDATION": "opaque",
                },
            },
        )()

    def close(self):
        self.closed = True


def test_pima_probe_fingerprints_stable_search_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _PimaProbeClient()
    monkeypatch.setattr(
        public_records_monitor,
        "PimaCourtClient",
        lambda **_kwargs: client,
    )

    observation = probe_pima_courts(
        ProbeContext(
            source_id=PIMA_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert observation.details["request_count"] == 2
    assert observation.details["hidden_fields"] == [
        "__EVENTVALIDATION",
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
    ]
    assert client.closed is True


class _SanMateoProbeClient:
    def __init__(self, **_kwargs):
        self.closed = False

    def probe(self):
        return type(
            "Result",
            (),
            {
                "rows": ({"case_number": "PRO116668-B"},),
                "total_reported": 3,
                "source_total_pages": 1,
                "pages_fetched": 1,
                "current_as_of": "July 28, 2026 at 05:30 AM",
                "schema_fingerprint": "e" * 64,
                "source_url": ("https://web.sanmateocourt.org/midx/lookup.php"),
            },
        )()

    def close(self):
        self.closed = True


def test_san_mateo_probe_uses_known_case_browser_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _SanMateoProbeClient()
    monkeypatch.setattr(
        public_records_monitor,
        "MIDXClient",
        lambda **_kwargs: client,
    )

    observation = probe_san_mateo_midx(
        ProbeContext(
            source_id=SAN_MATEO_SOURCE,
            catalog_decision={"limits": {}},
            timeout=30,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert observation.schema_sha256 == "e" * 64
    assert observation.details["total_reported"] == 3
    assert observation.details["transport"] == "anonymous_browser_form"
    assert client.closed is True


class _TaxCourtProbeClient:
    def __init__(self, **_kwargs):
        self.session = _CloseTrackingTransport()

    def health(self):
        return {
            "resource": {"status": "ok"},
            "metadata": {
                "schema_fingerprint": "f" * 64,
                "contracts": {"case_search_result_ceiling": 5000},
                "requests_made": 1,
            },
        }

    def search_cases(self, petitioner_name):
        assert petitioner_name == "Hagee"
        return {
            "records": [
                {"docketNumberWithSuffix": "9072-14S"},
                {"docketNumberWithSuffix": "455-22S"},
            ],
            "metadata": {
                "schema_fingerprint": "e" * 64,
                "requests_made": 1,
            },
        }


def test_tax_court_probe_fingerprints_health_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _TaxCourtProbeClient()
    monkeypatch.setattr(
        public_records_monitor,
        "TaxCourtClient",
        lambda **_kwargs: client,
    )

    observation = probe_tax_court_dawson(
        ProbeContext(
            source_id=TAX_COURT_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 2
    assert len(observation.schema_sha256 or "") == 64
    assert observation.details["contracts"] == {"case_search_result_ceiling": 5000}
    assert observation.details["sentinel_dockets"] == [
        "455-22S",
        "9072-14S",
    ]
    assert observation.details["requests_made"] == 2
    assert client.session.closed is True


def test_ny_law_reports_probe_fingerprints_all_official_routes(
    monkeypatch: pytest.MonkeyPatch,
):
    checks = [
        {
            "name": f"check-{index}",
            "status": "ok",
            "source_url": f"https://www.nycourts.gov/reporter/{index}",
            "record_count": index,
        }
        for index in range(7)
    ]
    exact_urls = {
        f"route-{index}": f"https://www.nycourts.gov/reporter/{index}"
        for index in range(7)
    }
    monkeypatch.setattr(
        public_records_monitor,
        "run_ny_law_reports_sentinel",
        lambda: {
            "status": "ok",
            "checks": checks,
            "exact_urls": exact_urls,
        },
    )

    observation = probe_ny_law_reports(
        ProbeContext(
            source_id=NY_LAW_REPORTS_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 7
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["checks"] == checks
    assert observation.details["exact_urls"] == exact_urls


def test_ny_column_probe_fingerprints_notice_and_ceiling_contracts(
    monkeypatch: pytest.MonkeyPatch,
):
    checks = [
        {
            "name": "partitioned_notice",
            "status": "ok",
            "notice_id": "notice-1",
        },
        {
            "name": "display_ceiling",
            "status": "ok",
            "source_display_ceiling": 10000,
        },
    ]
    exact_urls = {
        "portal": "https://newyork.column.us/",
        "sentinel_notice": ("https://newyork.column.us/?activeNotice=notice-1"),
    }
    monkeypatch.setattr(
        public_records_monitor,
        "run_ny_column_sentinel",
        lambda: {
            "status": "ok",
            "checks": checks,
            "exact_urls": exact_urls,
        },
    )

    observation = probe_ny_column(
        ProbeContext(
            source_id=NY_COLUMN_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 2
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["checks"] == checks


class _TexasTAMESProbeClient:
    def __init__(self, page):
        self.page = page
        self.closed = False
        self.calls = []

    def probe(self):
        self.calls.append(("probe",))
        return {
            "source_url": query_texas_appellate.SEARCH_URL,
            "form_action": "/CaseSearch.aspx?coa=cossup",
            "court_labels": list(query_texas_appellate.COURT_NAMES.values()),
            "county_option_count": 255,
            "trial_court_option_count": 1142,
            "schema_fingerprint": "a" * 64,
        }

    def case(self, case_number, *, court_code):
        self.calls.append(("case", case_number, court_code))
        return self.page

    def download(self, source_url, native_document_id):
        self.calls.append(("download", source_url, native_document_id))
        return query_texas_appellate.TAMESDownload(
            native_document_id=native_document_id,
            source_url=source_url,
            content=b"%PDF-1.7\nfixture\n",
            media_type="application/pdf",
            raw_content_type="Application/pdf",
            filename="0D6.pdf",
        )

    def close(self):
        self.closed = True


def test_texas_tames_probe_checks_form_case_and_public_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = query_texas_appellate.parse_case_page(
        Path(
            "tests/fixtures/public_records/texas_appellate/case_detail.html"
        ).read_text(encoding="utf-8"),
        source_url=(
            "https://search.txcourts.gov/Case.aspx?cn=03-25-00287-CV&coa=coa03"
        ),
    )
    assert page is not None
    client = _TexasTAMESProbeClient(page)
    monkeypatch.setattr(
        public_records_monitor,
        "TexasTAMESClient",
        lambda **_kwargs: client,
    )

    observation = probe_texas_tames(
        ProbeContext(
            source_id=TEXAS_TAMES_SOURCE,
            catalog_decision={"limits": {"minimum_interval_seconds": 0.25}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["case_number"] == "03-25-00287-CV"
    assert observation.details["native_document_id"] == (
        "bc16a831-998e-449f-9d28-84b61486178b"
    )
    assert observation.details["requests_made"] == 3
    assert [call[0] for call in client.calls] == [
        "probe",
        "case",
        "download",
    ]
    assert client.closed is True


class _RRCProbeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _RRCProbeClient:
    def __init__(self):
        self.calls: list[str] = []
        self.entries = {
            "p4": [
                query_rrc_bulk.GoDriveEntry(
                    index=0,
                    filename="p4f606.ebc.gz",
                    modified_display="07/27/26 10:00:00 AM",
                    modified_at="2026-07-27T10:00:00",
                    size_display="197.98 MB",
                )
            ],
            "p5": [
                query_rrc_bulk.GoDriveEntry(
                    index=0,
                    filename="orf850.ebc.gz",
                    modified_display="07/25/26 10:00:00 AM",
                    modified_at="2026-07-25T10:00:00",
                    size_display="20 MB",
                ),
                query_rrc_bulk.GoDriveEntry(
                    index=1,
                    filename="orf850.txt.gz",
                    modified_display="07/25/26 10:00:00 AM",
                    modified_at="2026-07-25T10:00:00",
                    size_display="18.59 MB",
                ),
            ],
            "wellbore": [
                query_rrc_bulk.GoDriveEntry(
                    index=70,
                    filename="OG_WELLBORE_EWA_Report_2026-06-02.csv",
                    modified_display="06/02/26 10:00:00 AM",
                    modified_at="2026-06-02T10:00:00",
                    size_display="470 MB",
                ),
                query_rrc_bulk.GoDriveEntry(
                    index=71,
                    filename="OG_WELLBORE_EWA_Report_2026-07-02.csv",
                    modified_display="07/02/26 10:00:54 AM",
                    modified_at="2026-07-02T10:00:54",
                    size_display="473.55 MB",
                ),
            ],
        }

    def list(self, source):
        self.calls.append(source)
        return self.entries[source], "fixture-view-state"


@pytest.mark.parametrize(
    ("source_id", "source_key", "expected_filename"),
    [
        (
            TEXAS_RRC_P4_SOURCE,
            "p4",
            "p4f606.ebc.gz",
        ),
        (
            TEXAS_RRC_P5_SOURCE,
            "p5",
            "orf850.txt.gz",
        ),
        (
            TEXAS_RRC_WELLBORE_SOURCE,
            "wellbore",
            "OG_WELLBORE_EWA_Report_2026-07-02.csv",
        ),
    ],
)
def test_texas_rrc_probe_fingerprints_release_listing_without_download(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    source_key: str,
    expected_filename: str,
) -> None:
    sessions: list[_RRCProbeSession] = []
    client = _RRCProbeClient()

    def make_session():
        session = _RRCProbeSession()
        sessions.append(session)
        return session

    monkeypatch.setattr(
        public_records_monitor,
        "system_trust_session",
        make_session,
    )
    monkeypatch.setattr(
        public_records_monitor,
        "RRCGoDriveClient",
        lambda **_kwargs: client,
    )

    observation = probe_texas_rrc_release(
        ProbeContext(
            source_id=source_id,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["source_key"] == source_key
    assert observation.details["preferred_release"]["filename"] == (expected_filename)
    assert observation.details["download_performed"] is False
    assert client.calls == [source_key]
    assert len(sessions) == 1
    assert sessions[0].closed is True


class _CloseTrackingTransport:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _VICourtsProbeClient:
    def __init__(self, *_args, document_records=None, **_kwargs):
        self.request_count = 0
        self.transport = _CloseTrackingTransport()
        self.document_records = (
            [
                {
                    "documentLinkUUID": "document-link-1",
                    "documentName": "Estate filing",
                }
            ]
            if document_records is None
            else document_records
        )

    @staticmethod
    def _page(records):
        return type(
            "Page",
            (),
            {
                "records": tuple(records),
                "schema": {"kind": "fixture"},
            },
        )()

    def info(self):
        self.request_count += 1
        return {
            "version": "4.8",
            "constants": {"SEARCH_RESULTS_LIMIT": 10_000},
        }

    def list_courts(self, **_kwargs):
        self.request_count += 1
        return self._page(
            [
                {
                    "resourceID": "superior-resource-uuid",
                    "externalIdentifier": "1",
                    "displayName": ("Superior Court of the Virgin Islands"),
                },
                {
                    "resourceID": "supreme-resource-uuid",
                    "externalIdentifier": "2",
                    "displayName": ("Supreme Court of the Virgin Islands"),
                },
            ]
        )

    def search_cases(self, *_args, **_kwargs):
        self.request_count += 1
        return self._page(
            [
                {
                    "caseHeader": {
                        "caseNumber": "ST-2019-PB-00080",
                        "caseInstanceUUID": "case-instance-uuid",
                    }
                }
            ]
        )

    def search_documents(self, **_kwargs):
        self.request_count += 1
        return self._page(self.document_records)

    def search_publications(self, **_kwargs):
        self.request_count += 1
        return self._page(
            [
                {
                    "publicationUUID": "publication-uuid",
                    "publicationNumber": "PB-2026-00032",
                }
            ]
        )

    def legacy_file(self, item_id):
        assert item_id == 16911884
        self.request_count += 1
        return type(
            "PDF",
            (),
            {
                "media_type": "application/pdf",
                "content": b"%PDF-1.7\nfixture",
                "sha256": "d" * 64,
            },
        )()


def test_vicourts_probe_covers_ctrack_and_legacy_backends(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _VICourtsProbeClient()
    monkeypatch.setattr(
        public_records_monitor,
        "VICourtsClient",
        lambda *_args, **_kwargs: client,
    )

    observation = probe_vicourts(
        ProbeContext(
            source_id=VICOURTS_SOURCE,
            catalog_decision={"limits": {}},
            timeout=5,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["court_count"] == 2
    assert observation.details["case_number"] == "ST-2019-PB-00080"
    assert observation.details["case_instance_uuid"] == ("case-instance-uuid")
    assert observation.details["document_link_uuid"] == "document-link-1"
    assert observation.details["publication_uuid"] == "publication-uuid"
    assert observation.details["legacy_item_id"] == 16911884
    assert observation.details["legacy_sha256"] == "d" * 64
    assert observation.details["requests_made"] == 6
    assert client.transport.closed is True


def test_vicourts_probe_does_not_accept_missing_document_sentinel(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _VICourtsProbeClient(document_records=[])
    monkeypatch.setattr(
        public_records_monitor,
        "VICourtsClient",
        lambda *_args, **_kwargs: client,
    )

    with pytest.raises(ValueError, match="document-search sentinel"):
        probe_vicourts(
            ProbeContext(
                source_id=VICOURTS_SOURCE,
                catalog_decision={"limits": {}},
                timeout=5,
                max_attempts=1,
                sample_bytes=None,
            )
        )

    assert client.transport.closed is True


def _orleans_probe_payloads(*, maximum_lastupdate=1781531741000):
    sentinel_fields = [
        {"name": "OBJECTID", "type": "esriFieldTypeOID"},
        {"name": "PARCELID", "type": "esriFieldTypeString"},
        {"name": "PARID", "type": "esriFieldTypeString"},
        {"name": "TAXBILLID", "type": "esriFieldTypeString"},
        {"name": "SITEADDRESS", "type": "esriFieldTypeString"},
        {"name": "LASTUPDATE", "type": "esriFieldTypeDate"},
    ]
    sentinel = {
        "fields": sentinel_fields,
        "features": [
            {
                "attributes": {
                    "OBJECTID": 100,
                    "PARCELID": "41026779",
                    "PARID": "1600-PERDIDOST",
                    "TAXBILLID": "104103301",
                    "SITEADDRESS": "1600 PERDIDO ST",
                    "LASTUPDATE": 1781531741000,
                }
            }
        ],
    }
    freshness = {"features": [{"attributes": {"max_lastupdate": maximum_lastupdate}}]}
    locator = {
        "candidates": [
            {
                "address": "104103301",
                "score": 100,
                "attributes": {
                    "Loc_name": "ParcelTaxbillL",
                    "Match_addr": "104103301",
                    "User_fld": "1227 POYDRAS ST",
                },
            }
        ]
    }
    viewer = {
        "id": 15,
        "name": "Property Information [Parcels]",
        "geometryType": "esriGeometryPolygon",
        "capabilities": "Map,Query,Data",
        "fields": [
            {"name": "OBJECTID", "type": "esriFieldTypeOID"},
            {"name": "PARCELID", "type": "esriFieldTypeString"},
            {"name": "PARID", "type": "esriFieldTypeString"},
            {"name": "TAXBILLID", "type": "esriFieldTypeString"},
        ],
    }
    return [sentinel, freshness, locator, viewer]


class _OrleansProbeClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []
        self.request_count = 0

    def _request_json(self, url, *, params):
        self.calls.append((url, params))
        self.request_count += 1
        if not self.payloads:
            raise AssertionError("unexpected Orleans monitor request")
        return self.payloads.pop(0)


def _orleans_context():
    return ProbeContext(
        source_id=ORLEANS_SOURCE,
        catalog_decision={"limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_orleans_probe_is_data_bearing_across_all_live_routes(
    monkeypatch: pytest.MonkeyPatch,
):
    client = _OrleansProbeClient(_orleans_probe_payloads())
    monkeypatch.setattr(
        public_records_monitor,
        "_BaseJSONClient",
        lambda **_kwargs: client,
    )

    observation = probe_orleans_property(_orleans_context())

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert len(observation.schema_sha256 or "") == 64
    assert len(observation.artifact_sha256 or "") == 64
    assert observation.details["sentinel_geopin"] == "41026779"
    assert observation.details["sentinel_tax_bill_id"] == "104103301"
    assert observation.details["maximum_source_last_updated"] == (
        "2026-06-15T13:55:41Z"
    )
    assert observation.details["locator_role"] == "ParcelTaxbillL"
    assert observation.details["viewer_layer_id"] == 15
    assert (
        "/dev/property3/MapServer/15" in (observation.details["deployed_viewer_layer"])
    )
    assert (
        "/apps/property3/MapServer/15"
        in (observation.details["canonical_viewer_layer_mirror"])
    )
    assert observation.details["requests_made"] == 4
    assert len(client.calls) == 4
    assert client.calls[0][0].endswith("/LGIM/TaxParcelQuery/MapServer/0/query")
    assert client.calls[0][1]["where"] == "PARCELID='41026779'"
    assert "max_lastupdate" in client.calls[1][1]["outStatistics"]
    assert client.calls[2][1]["SingleLine"] == "104103301"
    assert client.calls[2][1]["maxLocations"] == 1
    assert client.calls[3] == (
        public_records_monitor.ORLEANS_PROPERTY_DEPLOYED_VIEWER_LAYER_URL,
        {"f": "json"},
    )


def test_orleans_probe_does_not_report_ok_when_locator_loses_sentinel(
    monkeypatch: pytest.MonkeyPatch,
):
    payloads = _orleans_probe_payloads()
    payloads[2] = {"candidates": []}
    client = _OrleansProbeClient(payloads)
    monkeypatch.setattr(
        public_records_monitor,
        "_BaseJSONClient",
        lambda **_kwargs: client,
    )

    with pytest.raises(ValueError, match="exactly one bounded candidate"):
        probe_orleans_property(_orleans_context())


def test_orleans_probe_does_not_report_ok_on_viewer_schema_drift(
    monkeypatch: pytest.MonkeyPatch,
):
    payloads = _orleans_probe_payloads()
    payloads[3]["fields"] = [
        field for field in payloads[3]["fields"] if field["name"] != "TAXBILLID"
    ]
    client = _OrleansProbeClient(payloads)
    monkeypatch.setattr(
        public_records_monitor,
        "_BaseJSONClient",
        lambda **_kwargs: client,
    )

    with pytest.raises(ValueError, match="schema is missing: TAXBILLID"):
        probe_orleans_property(_orleans_context())


def test_orleans_freshness_change_updates_artifact_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
):
    first_client = _OrleansProbeClient(_orleans_probe_payloads())
    monkeypatch.setattr(
        public_records_monitor,
        "_BaseJSONClient",
        lambda **_kwargs: first_client,
    )
    first = probe_orleans_property(_orleans_context())

    second_client = _OrleansProbeClient(
        _orleans_probe_payloads(maximum_lastupdate=1781531742000)
    )
    monkeypatch.setattr(
        public_records_monitor,
        "_BaseJSONClient",
        lambda **_kwargs: second_client,
    )
    second = probe_orleans_property(_orleans_context())

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 != second.artifact_sha256


def test_florida_acis_probe_rejects_duplicate_court_identities(
    monkeypatch: pytest.MonkeyPatch,
):
    duplicate = SimpleNamespace(
        resource_uuid="same-resource-id",
        external_id="1",
        display_name="Duplicate",
        active=True,
        raw={
            "resourceID": "same-resource-id",
            "externalIdentifier": "1",
            "displayName": "Duplicate",
            "active": True,
        },
    )

    class FakeClient:
        def __init__(self, **_kwargs):
            self.request_count = 0

        def courts(self):
            self.request_count += 1
            return (duplicate,) * 7

    monkeypatch.setattr(
        public_records_monitor,
        "FloridaACISClient",
        FakeClient,
    )

    with pytest.raises(ValueError, match="duplicate court identities"):
        probe_florida_acis(
            ProbeContext(
                source_id=FLORIDA_ACIS_SOURCE,
                catalog_decision={"limits": {}},
                timeout=5.0,
                max_attempts=1,
                sample_bytes=None,
            )
        )


def test_plan_reads_catalog_decisions_without_dispatching(catalog):
    calls = []

    def handler(_context):
        calls.append("called")
        return ok_observation()

    handlers = {NC_SOURCE: handler_spec(NC_SOURCE, handler)}
    result = plan_sources(catalog, [NC_SOURCE, OTHER_SOURCE], handlers=handlers)

    assert calls == []
    assert result["sources"][0]["mode"] == "registered_probe"
    assert result["sources"][0]["catalog_decision"]["allowed"] is True
    assert result["sources"][1]["mode"] == "no_registered_handler"
    assert result["sources"][1]["catalog_decision"]["allowed"] is True


def test_run_dispatches_only_explicit_source_ids_and_records_probe(catalog):
    calls = []

    def nc_handler(context):
        calls.append(context.source_id)
        return ok_observation()

    def ma_handler(context):
        calls.append(context.source_id)
        return ok_observation()

    handlers = {
        NC_SOURCE: handler_spec(NC_SOURCE, nc_handler),
        MA_SOURCE: handler_spec(MA_SOURCE, ma_handler),
    }
    result = run_sources(catalog, [NC_SOURCE], handlers=handlers)

    assert calls == [NC_SOURCE]
    assert result["requested_source_ids"] == [NC_SOURCE]
    assert result["results"][0]["dispatched"] is True
    assert result["results"][0]["recorded"] is True
    assert catalog.probe_history(NC_SOURCE)[0]["status"] == "ok"
    assert catalog.probe_history(MA_SOURCE) == []


def test_catalog_barrier_is_not_dispatched_and_never_becomes_no_results(catalog):
    calls = []

    def forbidden_handler(_context):
        calls.append("called")
        return ok_observation(status="no_results")

    handlers = {BLOCKED_SOURCE: handler_spec(BLOCKED_SOURCE, forbidden_handler)}
    result = run_sources(catalog, [BLOCKED_SOURCE], handlers=handlers)
    item = result["results"][0]

    assert calls == []
    assert item["catalog_decision"]["allowed"] is False
    assert item["dispatched"] is False
    assert item["recorded"] is True
    assert item["probe"]["status"] == "human_required"
    assert item["probe"]["status"] != "no_results"
    assert item["probe"]["details"]["catalog_decision"]["access_class"] == "C"


def test_allowed_source_without_handler_is_transparent_and_not_false_probe(catalog):
    result = run_sources(catalog, [OTHER_SOURCE], handlers={})
    item = result["results"][0]

    assert item["catalog_decision"]["allowed"] is True
    assert item["dispatched"] is False
    assert item["recorded"] is False
    assert item["status"] == "error"
    assert catalog.probe_history(OTHER_SOURCE) == []


def test_handler_exception_records_failure_not_no_results(catalog):
    def broken_handler(_context):
        raise RuntimeError("fixture transport failure")

    result = run_sources(
        catalog,
        [NC_SOURCE],
        handlers={NC_SOURCE: handler_spec(NC_SOURCE, broken_handler)},
    )
    probe = result["results"][0]["probe"]

    assert probe["status"] == "unavailable"
    assert probe["status"] != "no_results"
    assert probe["error"] == "fixture transport failure"
    assert probe["result_count"] is None


def test_successful_authoritative_empty_probe_can_record_no_results(catalog):
    def empty_handler(_context):
        return ok_observation(status="no_results")

    result = run_sources(
        catalog,
        [NC_SOURCE],
        handlers={NC_SOURCE: handler_spec(NC_SOURCE, empty_handler)},
    )

    assert result["results"][0]["probe"]["status"] == "no_results"
    assert result["results"][0]["probe"]["error"] is None


def test_schema_artifact_and_status_drift_are_compared(catalog):
    observations = iter(
        [
            ok_observation(schema="1" * 64, artifact="a" * 64),
            ok_observation(schema="2" * 64, artifact="b" * 64, status="partial"),
        ]
    )

    def changing_handler(_context):
        return next(observations)

    handlers = {NC_SOURCE: handler_spec(NC_SOURCE, changing_handler)}
    first = run_sources(catalog, [NC_SOURCE], handlers=handlers)
    second = run_sources(catalog, [NC_SOURCE], handlers=handlers)

    assert first["results"][0]["drift"]["baseline"] is True
    drift = second["results"][0]["drift"]
    assert drift["drift_detected"] is True
    assert drift["changes"]["status"]["changed"] is True
    assert drift["changes"]["schema_sha256"]["changed"] is True
    assert drift["changes"]["artifact_sha256"]["changed"] is True


def test_history_returns_every_catalog_probe_without_monitor_cap(catalog):
    for index in range(25):
        catalog.record_probe(
            NC_SOURCE,
            status="ok",
            probed_by="test",
            probed_at=f"2026-07-28T12:{index:02d}:00Z",
            schema_sha256=f"{index:064x}",
        )
    result = history(catalog, NC_SOURCE)

    assert len(result["probes"]) == 25
    assert result["probes"][0]["probe_id"] > result["probes"][-1]["probe_id"]


def test_diff_can_compare_exact_probe_ids(catalog):
    first = catalog.record_probe(
        NC_SOURCE,
        status="ok",
        probed_by="test",
        probed_at="2026-07-28T12:00:00Z",
        schema_sha256="1" * 64,
    )
    second = catalog.record_probe(
        NC_SOURCE,
        status="ok",
        probed_by="test",
        probed_at="2026-07-28T12:01:00Z",
        schema_sha256="2" * 64,
    )

    result = diff_history(
        catalog,
        NC_SOURCE,
        from_probe_id=first["probe_id"],
        to_probe_id=second["probe_id"],
    )

    assert result["comparison"]["previous_probe_id"] == first["probe_id"]
    assert result["comparison"]["current_probe_id"] == second["probe_id"]
    assert result["comparison"]["drift_detected"] is True


def test_cli_accepts_catalog_db_before_or_after_subcommand():
    parser = public_records_monitor.build_parser()

    before = parser.parse_args(["--db", "/tmp/before.db", "run", NC_SOURCE])
    after = parser.parse_args(["run", NC_SOURCE, "--db", "/tmp/after.db"])

    assert before.db == "/tmp/before.db"
    assert after.db == "/tmp/after.db"


@pytest.mark.parametrize("status", ["ok", "no_results"])
def test_monitor_run_exit_code_accepts_healthy_recorded_probes(status):
    assert (
        public_records_monitor._run_exit_code(
            {
                "results": [
                    {
                        "recorded": True,
                        "probe": {"status": status},
                    }
                ]
            }
        )
        == 0
    )


@pytest.mark.parametrize(
    "result",
    [
        {
            "recorded": False,
            "status": "error",
            "error": "No registered low-cost probe handler",
        },
        {
            "recorded": True,
            "probe": {"status": "unavailable"},
        },
        {
            "recorded": True,
            "probe": {"status": "source_changed"},
        },
        {
            "recorded": True,
            "probe": {"status": "partial"},
        },
    ],
)
def test_monitor_run_exit_code_flags_unhealthy_or_undispatched_results(result):
    assert public_records_monitor._run_exit_code({"results": [result]}) == 1


def test_monitor_main_propagates_unhealthy_run_exit_code(monkeypatch):
    monkeypatch.setattr(
        public_records_monitor,
        "execute",
        lambda _args: {
            "results": [
                {
                    "recorded": True,
                    "probe": {"status": "source_changed"},
                }
            ]
        },
    )
    monkeypatch.setattr(
        public_records_monitor,
        "_emit",
        lambda _data, _args: None,
    )

    assert public_records_monitor.main(["run", NC_SOURCE]) == 1


def test_execute_diff_uses_selected_catalog(catalog):
    first = catalog.record_probe(
        NC_SOURCE,
        status="ok",
        probed_by="test",
        schema_sha256="1" * 64,
    )
    second = catalog.record_probe(
        NC_SOURCE,
        status="ok",
        probed_by="test",
        schema_sha256="2" * 64,
    )
    args = public_records_monitor.build_parser().parse_args(
        [
            "diff",
            NC_SOURCE,
            "--db",
            str(catalog.db_path),
            "--from-probe-id",
            str(first["probe_id"]),
            "--to-probe-id",
            str(second["probe_id"]),
        ]
    )

    result = public_records_monitor.execute(args)

    assert result["comparison"]["previous_probe_id"] == first["probe_id"]
    assert result["comparison"]["current_probe_id"] == second["probe_id"]


def test_manual_record_uses_catalog_history_and_returns_decision(catalog):
    result = record_observation(
        catalog,
        NC_SOURCE,
        ok_observation(schema="f" * 64),
        probed_by="test:manual",
        probed_at=NOW,
    )

    assert result["catalog_decision"]["allowed"] is True
    assert result["probe"]["probed_by"] == "test:manual"
    assert result["drift"]["baseline"] is True


def test_record_observation_serializes_nested_immutable_adapter_details(
    catalog,
):
    result = record_observation(
        catalog,
        NC_SOURCE,
        ProbeObservation(
            status="ok",
            details={
                "probe": MappingProxyType(
                    {"sentinel": MappingProxyType({"parcel_id": "0017103008000"})}
                )
            },
        ),
        probed_by="test:immutable-details",
        probed_at=NOW,
    )

    assert result["probe"]["details"]["probe"]["sentinel"] == {
        "parcel_id": "0017103008000"
    }


def test_compare_probes_handles_first_observation():
    comparison = compare_probes(
        None,
        {"probe_id": 1, "status": "ok", "schema_sha256": "1" * 64},
    )
    assert comparison == {
        "baseline": True,
        "drift_detected": False,
        "previous_probe_id": None,
        "current_probe_id": 1,
        "changes": {},
    }


def test_no_results_observation_rejects_embedded_error():
    with pytest.raises(ValueError, match="cannot contain an error"):
        ProbeObservation(status="no_results", error="transport failed")


def test_catalog_probe_history_rejects_foreign_probe_ids(catalog):
    other = catalog.record_probe(
        MA_SOURCE,
        status="ok",
        probed_by="test",
    )

    with pytest.raises(CatalogError):
        diff_history(
            catalog,
            NC_SOURCE,
            from_probe_id=other["probe_id"],
            to_probe_id=other["probe_id"] + 1,
        )
