from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from tools import query_oregon_smart_search as smart


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_smart_search"
    / "probe_sample.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_catalog_metadata_keeps_components_and_complements_distinct():
    metadata = smart.SOURCE_CATALOG_METADATA[smart.SOURCE_ID]

    assert metadata["authority"] == "Oregon Judicial Department"
    assert metadata["probe_evidence"]["location_count"] == 38
    assert metadata["probe_evidence"]["search_by_count"] == 11
    assert metadata["probe_evidence"]["captcha_enabled_for_anonymous_search"]
    assert {
        "us-or-ojcin-oeci-subscription",
        "us-or-ojcin-acms-subscription",
        "us-or-ojcin-standard-report-package",
        "us-or-ojcin-bulk-data-transfer",
        "us-or-osca-statewide-court-data-request",
    }.issubset(set(metadata["complementary_source_ids"]))


def test_normalize_probe_preserves_live_contract_and_ignores_dynamic_control():
    record = smart.normalize_probe(_fixture())

    assert record["source_id"] == smart.SOURCE_ID
    assert record["form"]["method"] == "post"
    assert record["option_sets"]["CourtLocation"]["count"] == 38
    assert record["option_sets"]["CaseStatus"]["count"] == 46
    assert record["option_sets"]["JudicialOfficer"]["count"] == 1112
    assert all(record["expected_option_count_matches"].values())
    assert record["captcha"]["frame_count"] == 2
    names = {control["name"] for control in record["form"]["stable_controls"]}
    assert "caseCriteria.SearchCriteria" in names
    assert "g-recaptcha-response" in names
    assert "a-rendered-session-field" not in names
    assert "JudicialOfficer" not in record["schema"]["option_counts"]
    assert record["rolling_observations"]["option_counts"] == {
        "JudicialOfficer": 1112,
        "JudicialOfficerSearchBy": 1112,
    }
    assert len(record["schema_fingerprint"]) == 64


def test_normalize_probe_judge_roster_does_not_change_schema_fingerprint():
    before = smart.normalize_probe(_fixture())
    changed = _fixture()
    changed["option_sets"]["JudicialOfficer"]["count"] += 1
    changed["option_sets"]["JudicialOfficerSearchBy"]["count"] += 1

    after = smart.normalize_probe(changed)

    assert after["schema_fingerprint"] == before["schema_fingerprint"]
    assert (
        after["rolling_observations"]["option_counts"]
        != (before["rolling_observations"]["option_counts"])
    )


def test_normalize_probe_detects_form_route_change():
    payload = _fixture()
    payload["form"]["action"] = "https://webportal.courts.oregon.gov/portal/Changed"

    with pytest.raises(smart.SmartSearchError) as raised:
        smart.normalize_probe(payload)

    assert raised.value.code == "probe_form_action_changed"
    assert raised.value.status.value == "source_changed"


def test_normalize_options_preserves_native_values_and_fingerprint():
    payload = {
        "source_url": smart.SOURCE_URL,
        "final_url": smart.SOURCE_URL,
        "http_status": 200,
        "field": "SearchBy",
        "options": [
            {"text": "Smart Search", "value": "SmartSearch"},
            {"text": "Business Name", "value": "BusinessName"},
        ],
        "option_count": 2,
        "runtime": {"playwright_module": "playwright"},
    }

    record = smart.normalize_options(payload, expected_field="SearchBy")

    assert record["option_count"] == 2
    assert record["options"][1]["value"] == "BusinessName"
    assert len(record["options_fingerprint"]) == 64


def test_prepare_business_search_maps_native_values_and_dates():
    args = smart.build_parser().parse_args(
        [
            "prepare",
            "ACME LLC",
            "--search-by",
            "BusinessName",
            "--location",
            "Hood River",
            "--case-type",
            "Civil",
            "--case-status",
            "ACT",
            "--file-date-start",
            "2025-01-02",
            "--file-date-end",
            "02/03/2026",
            "--no-search-warrants",
        ]
    )

    result = smart.execute(args)
    record = result.to_dict()["records"][0]
    strings = record["form_values"]["strings"]

    assert result.status.value == "ok"
    assert record["search_mode"]["value"] == "BusinessName"
    assert record["coverage"]["selected_location"] == "Hood River"
    assert record["coverage"]["selected_location_native_value"] == "Hood River "
    assert strings["caseCriteria.SearchCriteria"] == "ACME LLC"
    assert strings["caseCriteria.CaseType"] == "Civil"
    assert strings["caseCriteria.FileDateStart"] == "01/02/2025"
    assert strings["caseCriteria.FileDateEnd"] == "02/03/2026"
    assert (
        record["form_values"]["booleans"]["caseCriteria.SearchByBusinessName"] is True
    )
    assert record["form_values"]["booleans"]["caseCriteria.SearchByPartyName"] is False
    assert record["requested_components"] == ["cases", "judgments"]
    assert record["prepared_search_is_case_result"] is False


def test_prepare_name_search_exposes_advanced_fields():
    args = smart.build_parser().parse_args(
        [
            "prepare",
            "--last-name",
            "Smith",
            "--first-name",
            "Jane",
            "--location",
            "Tax Court",
            "--no-search-warrants",
            "--soundex",
        ]
    )

    result = smart.execute(args)
    record = result.to_dict()["records"][0]

    assert result.status.value == "ok"
    assert record["form_values"]["strings"]["caseCriteria.NameLast"] == "Smith"
    assert (
        record["form_values"]["booleans"]["caseCriteria.AdvancedSearchOptionsOpen"]
        is True
    )
    assert record["form_values"]["booleans"]["caseCriteria.UseSoundex"] is True


def test_advanced_prepare_inputs_change_fingerprint_and_handoff_identity():
    smith_args = smart.build_parser().parse_args(
        [
            "prepare",
            "--last-name",
            "Smith",
            "--first-name",
            "Jane",
            "--judgment-type",
            "JTCV",
            "--soundex",
        ]
    )
    jones_args = smart.build_parser().parse_args(
        [
            "prepare",
            "--last-name",
            "Jones",
            "--first-name",
            "Jane",
            "--judgment-type",
            "JTCV",
            "--soundex",
        ]
    )

    smith = smart.execute(smith_args)
    jones = smart.execute(jones_args)

    assert set(smith.query.query.parameters) == {
        "query_text",
        "search_by",
        "location",
        "last_name",
        "first_name",
        "middle_name",
        "suffix",
        "phone_number",
        "fbi_number",
        "so_number",
        "booking_number",
        "case_type",
        "case_status",
        "file_date_start",
        "file_date_end",
        "judicial_officer",
        "judgment_type",
        "judgment_date_from",
        "judgment_date_to",
        "warrant_type",
        "warrant_status",
        "warrant_date_issued_from",
        "warrant_date_issued_to",
        "search_cases",
        "search_judgments",
        "search_warrants",
        "party_name",
        "nickname",
        "business_name",
        "soundex",
    }
    assert smith.query.fingerprint != jones.query.fingerprint
    assert smith.records[0]["canonical_ref"] != jones.records[0]["canonical_ref"]
    assert smith.records[0]["query_fingerprint"] == smith.query.fingerprint
    assert jones.records[0]["query_fingerprint"] == jones.query.fingerprint


def test_prepare_requires_a_selector():
    args = smart.build_parser().parse_args(["prepare"])

    result = smart.execute(args)

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "search_selector_missing"


def test_prepare_requires_a_requested_component():
    args = smart.build_parser().parse_args(
        [
            "prepare",
            "SAMPLE",
            "--no-search-cases",
            "--no-search-judgments",
            "--no-search-warrants",
        ]
    )

    result = smart.execute(args)

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "search_component_missing"


def test_probe_can_normalize_saved_browser_packet():
    args = smart.build_parser().parse_args(["probe", "--input", str(FIXTURE)])

    result = smart.execute(args)

    assert result.status.value == "ok"
    assert result.records[0]["option_sets"]["CourtLocation"]["count"] == 38
    assert result.raw_artifact_refs == (str(FIXTURE.resolve()),)


def test_probe_uses_injected_browser_runner():
    args = smart.build_parser().parse_args(["probe"])
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return deepcopy(_fixture())

    result = smart.execute(args, helper_runner=runner)

    assert result.status.value == "ok"
    assert calls == [("probe", {"timeout": smart.DEFAULT_BROWSER_TIMEOUT})]


def test_options_uses_injected_browser_runner():
    args = smart.build_parser().parse_args(["options", "WarrantType"])

    def runner(command, **kwargs):
        assert command == "options"
        assert kwargs["field"] == "WarrantType"
        return {
            "source_url": smart.SOURCE_URL,
            "final_url": smart.SOURCE_URL,
            "http_status": 200,
            "field": "WarrantType",
            "options": [{"text": "Bench Warrant", "value": "WTBN"}],
            "option_count": 1,
            "runtime": {},
        }

    result = smart.execute(args, helper_runner=runner)

    assert result.status.value == "ok"
    assert result.records[0]["options"][0]["value"] == "WTBN"


def test_runtime_dependency_error_is_structured():
    error = smart._helper_error(
        json.dumps(
            {
                "error": {
                    "type": "RuntimeDependencyError",
                    "message": "missing browser runtime",
                }
            }
        ),
        1,
    )

    assert error.code == "browser_runtime_unavailable"
    assert error.category == "runtime"
    assert error.retryable is False


def test_sources_returns_source_and_each_complement():
    args = smart.build_parser().parse_args(["sources"])

    result = smart.execute(args)

    assert result.status.value == "ok"
    assert len(result.records) == 1 + len(smart.COMPLEMENTARY_SOURCES)
    assert result.records[0]["record_kind"] == "court_search_source"


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for the rendered Smart Search probe",
)
def test_live_rendered_probe():
    args = smart.build_parser().parse_args(["probe", "--browser-timeout", "120"])

    result = smart.execute(args)

    assert result.status.value == "ok"
    assert result.records[0]["http_status"] == 200
    assert result.records[0]["option_sets"]["CourtLocation"]["count"] >= 38
