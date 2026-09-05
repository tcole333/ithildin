from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_va_general_district as gdc
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _probe_record(
    *,
    application_build: str,
    request_count: int,
    source_url: str,
) -> dict[str, Any]:
    route_pairs = [
        (
            "Traffic/Criminal Name Search",
            "nameSearch.do?searchDivision=T&searchFipsCode=013",
        ),
        (
            "Traffic/Criminal Case Number Search",
            "criminalCivilCaseSearch.do?searchDivision=T&searchFipsCode=013",
        ),
        (
            "Traffic/Criminal Hearing Date Search",
            "caseSearch.do?searchType=hearingDate&searchDivision=T&searchFipsCode=013",
        ),
        (
            "Traffic/Criminal Service/Process Search",
            "caseSearch.do?searchType=servicesName&searchDivision=T&searchFipsCode=013",
        ),
        (
            "Civil Name Search",
            "nameSearch.do?searchDivision=V&searchFipsCode=013",
        ),
        (
            "Civil Case Number Search",
            "criminalCivilCaseSearch.do?searchDivision=V&searchFipsCode=013",
        ),
        (
            "Civil Hearing Date Search",
            "caseSearch.do?searchType=hearingDate&searchDivision=V&searchFipsCode=013",
        ),
        (
            "Civil Service/Process Search",
            "caseSearch.do?searchType=servicesName&searchDivision=V&searchFipsCode=013",
        ),
    ]
    return {
        "canonical_ref": "VA-GDC:PROBE:013",
        "source_id": gdc.SOURCE_ID,
        "record_kind": "source_probe",
        "status": "ok",
        "terms_state": "accepted_by_adapter",
        "verification_required": False,
        "court_component_count": 134,
        "selected_court": {
            "canonical_ref": "VA-GDC:COURT:013",
            "source_id": gdc.SOURCE_ID,
            "record_kind": "court_component",
            "court_id": "va-gdc-013",
            "court_name": "Arlington General District Court",
            "court_source_code": "013",
            "court_source_code_semantics": (
                "source-published application court-component identifier"
            ),
            "state_code": "VA",
            "source_url": source_url,
        },
        "selected_court_route_labels": [label for label, _href in route_pairs],
        "selected_court_route_hrefs": [href for _label, href in route_pairs],
        "civil_case_form_present": True,
        "traffic_criminal_case_form_present": True,
        "source_native_hearing_types": [
            {"code": code, "source_label": f"{code} - {label}"}
            for code, label in gdc.HEARING_TYPES
            if code
        ],
        "application_build": application_build,
        "request_count": request_count,
        "native_page_size": gdc.NATIVE_PAGE_SIZE,
        "reported_total": None,
        "source_url": source_url,
    }


def test_gdc_monitor_hashes_contract_not_session_or_application_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "application_build": "6.4.0.3",
        "request_count": 6,
        "source_url": gdc.CHANGE_COURT_URL,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.court == "013"
        assert log_results is False
        return PublicRecordsResult.success(
            gdc.build_query(args),
            [_probe_record(**rolling)],
        )

    monkeypatch.setattr(gdc, "execute", fake_execute)
    context = ProbeContext(
        source_id=gdc.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = public_records_monitor.probe_virginia_general_district(context)
    rolling.update(
        application_build="6.4.0.4",
        request_count=5,
        source_url=f"{gdc.CHANGE_COURT_URL}?session=renewed",
    )
    second = public_records_monitor.probe_virginia_general_district(context)

    assert first.status == "ok"
    assert first.result_count == 134
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != (
        second.details["rolling_observation"]
    )
    stable = first.details["stable_contract"]
    assert stable["court_components"]["source_published_count"] == 134
    assert (
        stable["court_components"]["source_code_semantics"]
        == "application court-component identifier, not geographic FIPS"
    )
    assert {route["source_id"] for route in stable["alternative_routes"]} == {
        route["source_id"] for route in gdc.COMPLEMENTARY_SOURCES
    }
    assert first.details["schema_contract"]["document_access"] == {
        "filing_index_present": False,
        "filing_images_present": False,
        "official_copy_route": "individual_court_clerk",
    }


def test_catalog_exposes_verified_gdc_contract_and_complements(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    decision = catalog.require_machine_acquisition(gdc.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["access_class"] == "B"
    assert decision["automation_disposition"] == "allowed_with_limits"
    assert decision["limits"]["minimum_interval_seconds"] == 0.5

    manifest = catalog.show_source(gdc.SOURCE_ID)["current_manifest"]
    assert set(manifest["complementary_source_ids"]) == {
        route["source_id"] for route in gdc.COMPLEMENTARY_SOURCES
    }
    assert manifest["stable_keys"] == ["court_id", "raw_case_number"]
    assert manifest["identity_contract"]["case_identity_fields"] == [
        "source_id",
        "court_id",
        "raw_case_number",
    ]
    assert (
        manifest["identity_contract"]["court_source_code_is_geographic_fips"]
        is False
    )
    assert manifest["probe_evidence"]["source_published_court_component_count"] == 134
    assert manifest["publication_contract"]["filing_index_present"] is False
    assert manifest["publication_contract"]["filing_images_present"] is False

    for source_id in (
        "us-va-ocis-statewide-search",
        "us-va-general-district-court-directory",
        "us-va-local-court-clerk-records",
        "us-va-circuit-court-case-information",
        "us-va-appellate-opinions",
        "us-va-secure-remote-access-land-records",
        "us-va-virginia-date-of-birth-confirmation",
    ):
        complement = catalog.show_source(source_id)["current_manifest"]
        assert source_id != gdc.SOURCE_ID
        assert gdc.SOURCE_ID in complement["complementary_source_ids"]

    spec = public_records_monitor.HANDLER_REGISTRY[gdc.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_virginia_general_district
    assert spec.expected_requests == 6
    assert spec.sentinel_record_count == 1


def test_gdc_source_and_complement_citation_urls_are_registered() -> None:
    source_urls_path = (
        Path(__file__).parents[1] / "web" / "src" / "data" / "source-urls.json"
    )
    source_urls = json.loads(source_urls_path.read_text(encoding="utf-8"))
    expected = {
        gdc.SOURCE_ID: gdc.LANDING_URL,
        "us-va-ocis-statewide-search": gdc.STATEWIDE_OCIS_URL,
        "us-va-general-district-court-directory": gdc.GDC_DIRECTORY_URL,
        "us-va-local-court-clerk-records": gdc.PUBLIC_RECORDS_REQUEST_URL,
        "us-va-circuit-court-case-information": gdc.CIRCUIT_CASE_URL,
        "us-va-appellate-opinions": "https://www.vacourts.gov/opinions/home",
        "us-va-secure-remote-access-land-records": gdc.LAND_RECORDS_URL,
        "us-va-virginia-date-of-birth-confirmation": gdc.VDBC_URL,
    }
    for source_id, expected_url in expected.items():
        assert source_urls[f"STATECOURT_SOURCE:{source_id}"] == expected_url
