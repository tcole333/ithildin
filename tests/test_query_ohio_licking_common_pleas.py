from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools import query_ohio_licking_common_pleas as licking
from tools.public_records_contract import ResultStatus


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_licking_common_pleas"
    / "probe.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _parse(*values: str):
    return licking.build_parser().parse_args(list(values))


@dataclass
class FakeResponse:
    payload: Any = None
    text: str = ""
    status_code: int = 200
    headers: dict[str, str] = field(
        default_factory=lambda: {"content-type": "application/json"}
    )

    def json(self):
        return self.payload


class QueueSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_source_contract_uses_requested_ids_and_registered_complements():
    metadata = licking.SOURCE_CATALOG_METADATA[licking.SOURCE_ID]

    assert licking.SOURCE_ID == "us-oh-licking-common-pleas-remote-records"
    assert licking.COURT_ID == "oh-licking-common-pleas"
    assert metadata["platform_family"] == "tyler_research"
    assert metadata["monitor"]["request_budget"] == 6
    complement_ids = {
        item.get("source_id") for item in metadata["complementary_sources"]
    }
    assert {
        "us-oh-licking-sheriff-realauction",
        "us-oh-licking-sheriff-foreclosure-archive",
        "us-oh-licking-county-recorder-pax",
        "us-oh-licking-county-auditor-gis",
    }.issubset(complement_ids)


def test_probe_preserves_verified_routes_and_reports_current_access_state():
    record = licking.normalize_probe(_fixture())

    assert record["application_name"] == "re:SearchOH"
    assert record["application_version"] == "2026.5.4.2302"
    assert record["county_id"] == 1
    assert record["external_source"] == "Licking County"
    assert record["county_site"] == "LickingCaseSearch"
    assert record["request_count"] == 6
    assert record["anonymous_probe_state"] == "available"
    assert (
        record["targeted_search_access_state"]
        == "human_verification_and_sign_in_required"
    )
    assert record["max_export_search_results_size"] == 1000
    assert record["max_export_is_search_page_ceiling"] is False
    assert record["court"] == licking._court_payload()


def test_rolling_app_version_does_not_change_stable_schema_fingerprint():
    before = licking.normalize_probe(_fixture())
    changed = _fixture()
    changed["app_configuration"]["payload"]["version"] = "2026.6.0.1"

    after = licking.normalize_probe(changed)

    assert before["schema_fingerprint"] == after["schema_fingerprint"]
    assert before["rolling_observations"] != after["rolling_observations"]


def test_probe_client_fetches_portal_shell_then_four_verified_anonymous_routes():
    fixture = _fixture()
    session = QueueSession(
        [
            FakeResponse(
                text=(
                    "<title>Licking County Common Pleas Case Records</title>"
                    " docket pleadings bulk"
                ),
                headers={"content-type": "text/html"},
            ),
            FakeResponse(
                text="<title>re:Search</title>",
                headers={"content-type": "text/html"},
            ),
            FakeResponse(payload=fixture["app_configuration"]["payload"]),
            FakeResponse(payload=fixture["claims"]["payload"]),
            FakeResponse(payload=fixture["subscription_configuration"]["payload"]),
            FakeResponse(payload=fixture["county_configuration"]["payload"]),
        ]
    )
    client = licking.LickingProbeClient(session=session, timeout=4)

    packet = client.probe()

    assert packet["request_count"] == 6
    assert [url for url, _kwargs in session.calls] == [
        licking.OFFICIAL_LANDING_URL,
        licking.PORTAL_URL,
        licking.APP_CONFIGURATION_URL,
        licking.CLAIMS_URL,
        licking.SUBSCRIPTION_CONFIGURATION_URL,
        licking.COUNTY_CONFIGURATION_URL,
    ]
    assert not any("/case/" in url or "/filing/" in url for url, _ in session.calls)
    assert session.calls[2][1]["headers"]["Referer"] == licking.PORTAL_URL
    assert "Chrome/150" in session.headers["User-Agent"]


def test_tyler_waf_403_is_human_required_not_generic_unavailable():
    session = QueueSession(
        [
            FakeResponse(
                text="<title>Licking County Common Pleas Case Records</title>",
                headers={"content-type": "text/html"},
            ),
            FakeResponse(
                text="Human Verification",
                status_code=403,
                headers={"content-type": "text/html"},
            ),
        ]
    )
    client = licking.LickingProbeClient(session=session, timeout=4)

    result = licking.execute(_parse("probe"), client=client)

    assert result.status == ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].code == "interactive_verification_required"
    assert result.errors[0].details["portal_url"] == licking.PORTAL_URL


def test_probe_input_produces_result_with_raw_artifact_reference():
    result = licking.execute(_parse("probe", "--input", str(FIXTURE)))

    assert result.status == ResultStatus.OK
    assert result.raw_artifact_refs == (str(FIXTURE.resolve()),)


def test_non_object_claims_contract_is_source_change():
    packet = _fixture()
    packet["claims"]["payload"] = []
    client = type("Client", (), {"probe": lambda self: packet})()

    result = licking.execute(_parse("probe"), client=client)

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "probe_json_shape_changed"


def test_targeted_browser_handoff_is_structured_and_query_bound():
    args = _parse(
        "targeted-browser-handoff",
        "--party-name",
        "Jane Smith",
        "--filed-from",
        "2024-01-01",
    )

    first = licking.execute(args)
    second = licking.execute(args)

    assert first.status == ResultStatus.OK
    record = first.records[0]
    assert record["action_kind"] == "targeted_browser_search"
    assert record["access_state"] == "human_verification_and_sign_in_required"
    assert record["selectors"]["party_name"] == "Jane Smith"
    assert "caseDataID" in record["handoff"]["capture_fields"]
    assert record["canonical_ref"] == second.records[0]["canonical_ref"]


def test_targeted_browser_handoff_requires_a_selector():
    result = licking.execute(_parse("targeted-browser-handoff"))

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "target_selector_missing"


def test_bulk_copy_and_archive_handoffs_are_distinct_official_actions():
    bulk = licking.execute(
        _parse(
            "bulk-request-handoff",
            "--scope",
            "civil party index and docket events",
            "--division",
            "general-civil",
        )
    )
    copy_result = licking.execute(
        _parse(
            "record-request-handoff",
            "2025 CV 00123",
            "--document-description",
            "judgment entry",
            "--copy-type",
            "certified",
        )
    )
    archive = licking.execute(
        _parse("archives-handoff", "--party-name", "Jane Smith", "--year", "1988")
    )

    assert bulk.records[0]["action_kind"] == "bulk_distribution_request"
    assert bulk.records[0]["handoff"]["general_civil_criminal_phone"] == (
        licking.GENERAL_CIVIL_CRIMINAL_PHONE
    )
    assert copy_result.records[0]["action_kind"] == "current_record_or_copy_request"
    assert copy_result.records[0]["handoff"]["official_copy"] is True
    assert archive.records[0]["action_kind"] == "historical_archive_lookup"
    assert archive.records[0]["source_url"] == licking.ARCHIVES_URL


def test_source_manifest_keeps_portal_and_alternatives_as_separate_capabilities():
    result = licking.execute(_parse("source"))

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["access"] == {
        "anonymous_probe": "available",
        "targeted_portal": "human_verification_and_sign_in",
        "bulk_and_copy": "official_clerk_request",
        "historical": "county_records_and_archives",
    }
    assert record["portal_url"] == licking.PORTAL_URL
    assert record["court"]["county_geoid"] == licking.COUNTY_FIPS
    assert "domestic_violence_civil_protection_orders" in record["remote_exclusions"]
