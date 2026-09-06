from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_georgia_court_directory as directory
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=directory.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.2},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _probe_record(version: int) -> dict[str, Any]:
    return {
        "canonical_ref": f"STATECOURT:{directory.SOURCE_ID}/probe",
        "source_id": directory.SOURCE_ID,
        "record_kind": "source_probe",
        "source_url": directory.LANDING_URL,
        "snapshot_only": True,
        "stable_contract": {
            "application_id": directory.APP_ID,
            "search_view": {
                "scene_id": directory.SEARCH_SCENE,
                "view_id": directory.SEARCH_VIEW,
            },
            "detail_view": {
                "scene_id": directory.DETAIL_SCENE,
                "view_id": directory.DETAIL_VIEW,
            },
            "filter": list(
                directory.build_filters(
                    {"directory_section": "Superior Court Clerks"}
                )
            ),
            "identity": "exact native record ID",
        },
        "schema_contract": {
            "search": ["1" * 64],
            "detail": "2" * 64,
        },
        "rolling_observation": {
            "matching_total_records": 153 + version,
            "sample_record_id": f"sample-{version}",
            "sample_display_name": f"Example Clerk {version}",
            "sample_directory_sections": ["Superior Court Clerks"],
        },
        "requests_made": 2,
    }


def test_monitor_separates_emitted_contract_from_rolling_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"version": 1}
    calls: list[Any] = []

    def fake_execute(args: Any, **_: Any) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.minimum_interval == 0.2
        calls.append(args)
        return PublicRecordsResult.success(
            directory.build_query(args),
            [_probe_record(state["version"])],
        )

    monkeypatch.setattr(directory, "execute", fake_execute)

    first = public_records_monitor.probe_georgia_court_personnel_directory(
        _context()
    )
    state["version"] = 2
    second = public_records_monitor.probe_georgia_court_personnel_directory(
        _context()
    )

    assert len(calls) == 2
    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details[
        "stable_contract"
    ]
    assert first.details["schema_contract"] == second.details[
        "schema_contract"
    ]
    assert first.details["artifact_identity"] == second.details[
        "artifact_identity"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.result_count == 154
    assert second.result_count == 155
    assert first.details["requests_made"] == 2
    assert first.details["stable_contract"]["snapshot_semantics"] == {
        "snapshot_only": True,
        "historical_roster": False,
        "case_projection": False,
    }
    assert first.details["stable_contract"]["probe"]["filter"] == [
        {
            "field": "field_19",
            "operator": "is",
            "value": "Superior Court Clerks",
        }
    ]


def test_catalog_census_and_capabilities_match_adapter_contract(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = catalog.show_source(directory.SOURCE_ID)["current_manifest"]

    assert catalog.require_machine_acquisition(directory.SOURCE_ID)[
        "allowed"
    ] is True
    assert manifest["stable_keys"] == ["native_record_id"]
    assert manifest["identity_contract"][
        "source_identity_fields"
    ] == ["source_id", "native_record_id"]
    assert manifest["identity_contract"]["storage_semantics"] == (
        "snapshot_observation_only"
    )
    assert manifest["identity_contract"]["case_projection"] is False
    assert manifest["publication_contract"][
        "directory_records_are_case_records"
    ] is False
    assert manifest["publication_contract"]["historical_roster"] is False

    capabilities = {
        item["name"]: item["details"]
        for item in manifest["capabilities"]
    }
    search = capabilities["search_current_personnel_directory"]
    assert search["filters"] == list(directory.SEARCH_FIELD_DEFINITIONS)
    assert search["pagination"] == (
        "native_pages_with_filter_and_page_size_bound_cursor"
    )
    assert search["detail_hydration"] == "optional"
    assert search["case_projection"] is False
    emitted_top_level = {
        "canonical_ref",
        "native_record_id",
        "source_url",
        "person",
        "location",
        "contact",
        "classifications",
        "selection_context",
        "query_observation",
        "provenance",
        "raw_fields",
    }
    assert set(search["output_fields"]) == emitted_top_level
    assert capabilities["fetch_exact_directory_entry"]["selector"] == (
        "exact_native_record_id"
    )
    assert capabilities["query_shared_court_records"][
        "shared_operations"
    ] == ["search", "detail", "discovery", "probe"]
    assert capabilities["query_shared_court_records"][
        "case_operations_exposed"
    ] is False
    assert capabilities["ingest_state_court_records"]["projection"] == (
        "source_snapshot_only"
    )
    assert capabilities["ingest_state_court_records"][
        "case_rows_created"
    ] is False
    assert capabilities["probe_source"]["expected_requests"] == 2
    assert capabilities["probe_source"]["stable_contract"] == list(
        _probe_record(1)["stable_contract"]
    )
    assert capabilities["probe_source"]["rolling_observations"] == list(
        _probe_record(1)["rolling_observation"]
    )

    assert manifest["endpoints"] == {
        "landing": directory.LANDING_URL,
        "published_application": directory.APP_URL,
        "application_loader": directory.LOADER_URL,
        "search_view": directory.SEARCH_API_URL,
        "detail_view": directory.DETAIL_API_URL,
    }
    association = manifest["census_associations"][0]
    assert association["jurisdiction_geoid"] == "13"
    assert association["role"] == "court_directory"
    assert association["coverage"]["snapshot_only"] is True
    assert association["coverage"]["observed_probe_match_count"] == 154
    assert association["coverage"][
        "exact_detail_by_native_record_id"
    ] is True
    assert association["coverage"]["detail_fields"] == [
        "person",
        "location.address_lines",
        "location.city",
        "location.state",
        "location.postal_code",
        "location.county",
        "location.circuit",
        "location.municipal_judge_city",
        "location.chief_municipal_judge_city",
        "contact.phone",
        "contact.fax",
        "contact.email",
        "contact.email_visibility",
        "classifications",
    ]
    assert "cases" in " ".join(association["coverage_gaps"]).casefold()

    complements = manifest["official_complements"]
    assert all(item["dataset_equivalent"] is False for item in complements)
    assert {
        item.get("source_id") for item in complements if item.get("source_id")
    } == {"us-ga-gsccca-real-estate-index"}
    assert manifest["probe_evidence"]["observed_request_count"] == 2
    assert manifest["probe_evidence"]["observed_probe_match_count"] == 154


def test_monitor_registry_has_bounded_search_and_detail_probe() -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[directory.SOURCE_ID]

    assert spec.handler is (
        public_records_monitor.probe_georgia_court_personnel_directory
    )
    assert spec.endpoint == directory.LANDING_URL
    assert spec.expected_requests == 2
    assert spec.sentinel_record_count == 1


def test_state_court_citation_and_docs_cover_source_lifecycle() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{directory.SOURCE_ID}"
    ] == directory.LANDING_URL

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")

    assert "## Georgia AOC Court Personnel Directory" in legal
    assert "current directory observations rather than case filings" in legal
    assert "use the AOC eAccess routes" in legal
    assert "### Georgia AOC court-personnel directory adapter" in (
        tool_reference
    )
    assert directory.SOURCE_ID in tool_reference
    assert "Georgia AOC's current statewide Court Personnel Directory" in (
        roadmap
    )
    assert "Record filter scope separately from compact result scope" in (
        roadmap
    )
