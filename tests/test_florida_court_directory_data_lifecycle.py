from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_florida_court_directory_data as florida_data
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.2},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_component_monitors_separate_contracts_from_rolling_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"version": 1}
    clients: list[Any] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.closed = False
            clients.append(self)

        @staticmethod
        def _artifact(label: str, url: str) -> florida_data.Artifact:
            return florida_data.Artifact(
                content=f"{label}-{state['version']}".encode(),
                source_url=url,
                media_type=(
                    "application/json"
                    if label in {"locations", "virtual"}
                    else "text/html"
                ),
                headers={},
            )

        def locations(self) -> florida_data.Artifact:
            return self._artifact("locations", florida_data.LOCATION_API_URL)

        def virtual(
            self,
            *,
            county: str | None = None,
            judge: str | None = None,
        ) -> florida_data.Artifact:
            assert county is None
            assert judge is None
            return self._artifact("virtual", florida_data.VIRTUAL_API_URL)

        def page(self, url: str) -> florida_data.Artifact:
            return self._artifact("page", url)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(florida_data, "FloridaCourtsClient", FakeClient)
    monkeypatch.setattr(
        florida_data,
        "COUNTY_GEOID_BY_NAME",
        {"Charlotte": "12015", "Gadsden": "12039"},
    )

    def location_records(
        _artifact: florida_data.Artifact,
    ) -> tuple[dict[str, Any], ...]:
        mismatch = state["version"] == 1
        return (
            {
                "record_kind": "county_courthouse_location",
                "source_id": florida_data.LOCATION_SOURCE_ID,
                "native_record_id": "101",
                "county": "Charlotte",
                "appellate_map_category": {"identifier": "6dca"},
                "published_region": {
                    "identifier": "2dca" if mismatch else "6dca"
                },
                "published_region_matches_map_category": not mismatch,
                "projection": {"projectable_as_case": False},
            },
        )

    def virtual_records(
        _artifact: florida_data.Artifact,
    ) -> tuple[dict[str, Any], ...]:
        return (
            {
                "record_kind": "virtual_courtroom_directory_entry",
                "source_id": florida_data.VIRTUAL_SOURCE_ID,
                "native_record_id": "7",
                "judge_or_hearing_officer": (
                    "Judge One" if state["version"] == 1 else None
                ),
                "counties": ["Lee County"],
                "stream": {"live": state["version"] == 1},
                "projection": {"projectable_as_case": False},
            },
        )

    def request_record(
        artifact: florida_data.Artifact,
    ) -> dict[str, Any]:
        return {
            "record_kind": "public_records_request_program",
            "source_id": florida_data.PUBLIC_RECORDS_SOURCE_ID,
            "canonical_ref": "FL-COURTS:OSCA-PUBLIC-RECORDS",
            "request_scope": "records_held_by_osca",
            "request_methods": [
                {
                    "method": "email",
                    "address": f"osca-{state['version']}@example.test",
                }
            ],
            "fee_estimate_notice_published": True,
            "source_url": artifact.source_url,
            "projection": {"projectable_as_case": False},
        }

    def statistics_records(
        _artifact: florida_data.Artifact,
    ) -> tuple[dict[str, Any], ...]:
        return (
            {
                "record_kind": "trial_court_statistical_publication",
                "source_id": florida_data.STATISTICS_SOURCE_ID,
                "native_document_id": "2472276",
                "fiscal_year": "2024-25",
                "catalog_section": "Statistics",
                "title": f"Overall Statistics {state['version']}",
                "artifact_url": "https://example.test/statistics.pdf",
                "projection": {"projectable_as_case": False},
            },
        )

    monkeypatch.setattr(
        florida_data,
        "parse_location_directory",
        location_records,
    )
    monkeypatch.setattr(
        florida_data,
        "parse_virtual_directory",
        virtual_records,
    )
    monkeypatch.setattr(
        florida_data,
        "parse_data_request_program",
        request_record,
    )
    monkeypatch.setattr(
        florida_data,
        "parse_statistics_catalog",
        statistics_records,
    )

    observations: dict[str, tuple[Any, Any]] = {}
    for source_id in florida_data.COMPONENTS:
        state["version"] = 1
        first = (
            public_records_monitor.probe_florida_court_directory_data_component(
                _context(source_id)
            )
        )
        state["version"] = 2
        second = (
            public_records_monitor.probe_florida_court_directory_data_component(
                _context(source_id)
            )
        )
        observations[source_id] = (first, second)
        assert first.status == "ok"
        assert first.schema_sha256 == second.schema_sha256
        assert first.artifact_sha256 == second.artifact_sha256
        assert (
            first.details["rolling_observation"]
            != second.details["rolling_observation"]
        )
        assert first.details["requests_made"] == 1
        assert first.details["stable_contract"]["snapshot_semantics"] == {
            "shared_ingest": "snapshot_only",
            "case_projection": False,
        }

    location = observations[florida_data.LOCATION_SOURCE_ID][0]
    assert location.details["rolling_observation"][
        "published_county_omissions"
    ] == [{"county": "Gadsden", "county_geoid": "12039"}]
    assert location.details["rolling_observation"][
        "published_region_mismatches"
    ] == [
        {
            "county": "Charlotte",
            "map_category": "6dca",
            "published_region": "2dca",
        }
    ]
    assert location.details["schema_contract"][
        "publisher_embedded_region_is_normalized_geography"
    ] is False

    statistics = observations[florida_data.STATISTICS_SOURCE_ID][0]
    assert statistics.details["schema_contract"]["exact_pdf_download"][
        "shared_router_operation"
    ] is None
    assert all(client.closed for client in clients)
    assert all(client.kwargs["minimum_interval"] == 0.2 for client in clients)


def test_catalog_preserves_four_source_roles_and_snapshot_semantics(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    manifests = {
        source_id: catalog.show_source(source_id)["current_manifest"]
        for source_id in florida_data.COMPONENTS
    }
    assert set(manifests) == set(florida_data.COMPONENTS)
    assert all(
        catalog.require_machine_acquisition(source_id)["allowed"]
        for source_id in manifests
    )
    assert {
        source_id: manifest["stable_keys"]
        for source_id, manifest in manifests.items()
    } == {
        florida_data.LOCATION_SOURCE_ID: ["native_record_id"],
        florida_data.VIRTUAL_SOURCE_ID: ["native_record_id"],
        florida_data.PUBLIC_RECORDS_SOURCE_ID: ["canonical_ref"],
        florida_data.STATISTICS_SOURCE_ID: [
            "fiscal_year",
            "catalog_section",
            "native_document_id",
        ],
    }
    assert all(
        {
            item["name"]: item["details"]
            for item in manifest["capabilities"]
        }["ingest_state_court_records"]["projection"]
        == "source_snapshot_only"
        for manifest in manifests.values()
    )
    assert all(
        {
            item["name"]: item["details"]
            for item in manifest["capabilities"]
        }["query_shared_court_records"]["shared_operations"]
        == ["search"]
        for manifest in manifests.values()
    )

    location = manifests[florida_data.LOCATION_SOURCE_ID]
    assert location["identity_contract"][
        "source_embedded_region_is_normalized_geography"
    ] is False
    assert location["probe_evidence"]["observed_published_county_omissions"] == [
        {"county": "Gadsden", "county_geoid": "12039"}
    ]
    assert len(
        location["probe_evidence"]["observed_published_region_mismatches"]
    ) == 10
    assert location["census_associations"][0]["role"] == "court_directory"

    virtual = manifests[florida_data.VIRTUAL_SOURCE_ID]
    assert virtual["publication_contract"]["complete_judicial_roster"] is False
    assert virtual["census_associations"][0]["coverage"][
        "complete_county_coverage_claimed"
    ] is False

    request = manifests[florida_data.PUBLIC_RECORDS_SOURCE_ID]
    assert request["request_contract"]["authority_scope"] == (
        "records_held_by_osca"
    )
    assert request["request_contract"]["local_court_and_clerk_records_in_scope"] is False
    assert request["census_associations"][0]["role"] == "bulk_data_program"

    statistics = manifests[florida_data.STATISTICS_SOURCE_ID]
    capabilities = {
        item["name"]: item["details"] for item in statistics["capabilities"]
    }
    assert capabilities["download_statistical_pdf"]["shared_router_operation"] == (
        "none"
    )
    assert capabilities["query_shared_court_records"][
        "exact_pdf_download_uses_direct_adapter"
    ] is True
    assert statistics["publication_contract"]["case_level_bulk_feed"] is False
    assert statistics["census_associations"][0]["role"] == "bulk_data_program"


def test_monitor_registry_covers_each_component_independently() -> None:
    assert (
        public_records_monitor.FLORIDA_COURT_DIRECTORY_DATA_MONITOR_SOURCE_IDS
        == set(florida_data.COMPONENTS)
    )
    for source_id, component in florida_data.COMPONENTS.items():
        spec = public_records_monitor.HANDLER_REGISTRY[source_id]
        assert spec.handler is (
            public_records_monitor.probe_florida_court_directory_data_component
        )
        assert spec.endpoint == component.base_url
        assert spec.expected_requests == 1
        assert spec.sentinel_record_count == 1


def test_citations_and_docs_cover_the_four_source_lifecycle() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    for source_id, component in florida_data.COMPONENTS.items():
        assert source_urls[f"STATECOURT_SOURCE:{source_id}"] == component.base_url

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")

    assert "## Florida court directory and aggregate-data family" in legal
    assert "They do not synthesize Gadsden" in legal
    assert "### Florida court-directory and aggregate-data adapter" in (
        tool_reference
    )
    assert "Exact PDF download remains on the direct adapter" in " ".join(
        tool_reference.split()
    )
    assert "frontend shell" in roadmap
    assert "publisher-hosted data" in roadmap
