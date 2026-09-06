from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_osceola_courts as osceola
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.5},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _search_record() -> dict[str, Any]:
    return {
        "canonical_ref": "STATECOURT:fixture",
        "source_id": osceola.PORTAL_SOURCE_ID,
        "record_kind": "case_search_hit",
        "court": {"court_id": "fl-09-osceola-circuit"},
        "raw_case_number": "2023 CF 001540",
        "display_case_number": "2023 CF 001540",
        "source_internal_id": "3284536",
        "caption": "STATE OF FLORIDA VS EXAMPLE",
        "search_matches": [],
        "source_result_row_count": 1,
        "detail_available": True,
        "source_url": osceola.SEARCH_LANDING_URL,
        "projection": {"projectable_as_case_record": True},
    }


def _case_record(state: dict[str, str]) -> dict[str, Any]:
    return {
        "canonical_ref": "STATECOURT:fixture",
        "source_id": osceola.PORTAL_SOURCE_ID,
        "record_kind": "case",
        "court": {"court_id": "fl-09-osceola-circuit"},
        "raw_case_number": "2023 CF 001540",
        "display_case_number": "2023 CF 001540",
        "source_internal_id": "3284536",
        "caption": state["caption"],
        "parties": [],
        "attorneys": [],
        "charges": [],
        "case_events": [],
        "docket_entries": [
            {
                "canonical_ref": "STATECOURT:fixture:docket:56773534",
                "source_id": osceola.PORTAL_SOURCE_ID,
                "record_kind": "docket_entry",
                "raw_case_number": "2023 CF 001540",
                "native_entry_id": "56773534",
                "entry_text": "INFORMATION",
                "documents": [],
            }
        ],
        "projection": {"projectable_as_case_record": True},
        "source_document_sha256": state["case_sha"],
    }


def _document_record(state: dict[str, str]) -> dict[str, Any]:
    return {
        "canonical_ref": "STATECOURT:fixture:document:76951980",
        "source_id": osceola.PORTAL_SOURCE_ID,
        "record_kind": "document_page_metadata",
        "court": {"court_id": "fl-09-osceola-circuit"},
        "raw_case_number": "2023 CF 001540",
        "source_internal_id": "3284536",
        "native_entry_id": "56773534",
        "native_document_id": "76951980",
        "page_sequence": 1,
        "access_state": "public",
        "source_access_state": "public_image_route",
        "source_document_sha256": state["document_sha"],
    }


def test_catalog_census_shared_operations_and_citations_are_distinct(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    main = catalog.show_source(osceola.PORTAL_SOURCE_ID)["current_manifest"]
    calendar = catalog.show_source(
        osceola.CALENDAR_SOURCE_ID
    )["current_manifest"]
    foreclosure = catalog.show_source(
        osceola.FORECLOSURE_SOURCE_ID
    )["current_manifest"]

    main_capabilities = {
        item["name"]: item["details"] for item in main["capabilities"]
    }
    assert main_capabilities["query_shared_state_courts"][
        "shared_operations"
    ] == [
        "case",
        "discovery",
        "docket",
        "documents",
        "probe",
        "search",
    ]
    assert main_capabilities["probe_source"]["expected_requests"] == 12
    assert main["probe_evidence"]["monitor_stable_schema_sha256"] == (
        "9224a0a5cc54287c1f111ef7e631951e3a3bad63d4a764d19540c3e3d2feafcc"
    )

    main_associations = main["census_associations"]
    assert len(main_associations) == 1
    assert main_associations[0]["jurisdiction_geoid"] == "12"
    assert main_associations[0]["role"] == "trial_case_index"
    assert main_associations[0]["coverage"]["county_fips"] == "12097"
    assert main_associations[0]["coverage"]["coverage_status"] == "partial"

    calendar_capabilities = {
        item["name"]: item["details"] for item in calendar["capabilities"]
    }
    assert calendar_capabilities["query_shared_state_courts"][
        "shared_operations"
    ] == ["discovery", "probe"]
    assert calendar_capabilities["ingest_state_court_records"][
        "projection"
    ] == "source_snapshot_only"
    assert calendar["census_associations"][0]["role"] == "hearing_calendars"
    assert calendar["census_associations"][0]["coverage"][
        "coverage_status"
    ] == "partial"

    foreclosure_capabilities = {
        item["name"]: item["details"] for item in foreclosure["capabilities"]
    }
    assert foreclosure_capabilities["query_shared_state_courts"][
        "shared_operations"
    ] == ["discovery", "probe"]
    assert "census_associations" not in foreclosure
    assert foreclosure["snapshot_contract"]["projectable_as_case_record"] is False

    audit = audit_catalog(db_path=catalog_path)
    mismatches = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert {
        osceola.PORTAL_SOURCE_ID,
        osceola.CALENDAR_SOURCE_ID,
        osceola.FORECLOSURE_SOURCE_ID,
    }.isdisjoint(mismatches)

    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{osceola.PORTAL_SOURCE_ID}"
    ] == osceola.SEARCH_LANDING_URL
    assert source_urls[
        f"STATECOURT_SOURCE:{osceola.CALENDAR_SOURCE_ID}"
    ] == osceola.CALENDAR_URL
    assert source_urls[
        f"STATECOURT_SOURCE:{osceola.FORECLOSURE_SOURCE_ID}"
    ] == osceola.FORECLOSURE_URL


def test_benchmark_monitor_keeps_rolling_case_values_out_of_drift_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "caption": "STATE OF FLORIDA VS EXAMPLE",
        "bootstrap_sha": "a" * 64,
        "search_sha": "b" * 64,
        "case_sha": "c" * 64,
        "document_sha": "d" * 64,
    }
    clients: list[Any] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.request_count = 12
            self.closed = False
            clients.append(self)

        def bootstrap(self) -> osceola.BenchmarkSearchForm:
            return osceola.BenchmarkSearchForm(
                action_url=osceola.CASE_SEARCH_URL,
                hidden_fields={"__RequestVerificationToken": "fixture"},
                native_search_modes=tuple(sorted(osceola.NATIVE_SEARCH_MODES)),
                platform_version="2.9.10.0",
                source_url=osceola.SEARCH_LANDING_URL,
                source_document_sha256=state["bootstrap_sha"],
            )

        def search(self, *_args: Any, **_kwargs: Any) -> Any:
            locator = osceola.BenchmarkCaseLocator(
                case_id="3284536",
                digest="fixture",
                case_number="2023 CF 001540",
                detail_url=(
                    osceola.PORTAL_BASE_URL
                    + "CourtCase.aspx/Details/3284536?digest=fixture"
                ),
            )
            return osceola.BenchmarkSearchPage(
                hits=(
                    osceola.BenchmarkSearchHit(
                        record=_search_record(),
                        locator=locator,
                    ),
                ),
                source_row_count=1,
                total_reported=1,
                offset=0,
                too_broad=False,
                source_document_sha256=state["search_sha"],
            )

        def fetch_case(
            self,
            _case_number: str,
        ) -> osceola.BenchmarkCaseBundle:
            record = _case_record(state)
            return osceola.BenchmarkCaseBundle(
                record=record,
                docket_locators={
                    "56773534": osceola.DocketLocator(
                        docket_id="56773534",
                        digest="fixture",
                        source_access_state="public_image_metadata",
                    )
                },
                source_document_sha256=state["case_sha"],
            )

        def document_metadata_from_bundle(
            self,
            _bundle: osceola.BenchmarkCaseBundle,
            _docket_id: str,
        ) -> list[dict[str, Any]]:
            return [_document_record(state)]

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(osceola, "PioneerBenchmarkClient", FakeClient)
    first = public_records_monitor.probe_osceola_benchmark(
        _context(osceola.PORTAL_SOURCE_ID)
    )

    state.update(
        caption="STATE OF FLORIDA VS UPDATED EXAMPLE",
        bootstrap_sha="1" * 64,
        search_sha="2" * 64,
        case_sha="3" * 64,
        document_sha="4" * 64,
    )
    second = public_records_monitor.probe_osceola_benchmark(
        _context(osceola.PORTAL_SOURCE_ID)
    )

    assert first.status == second.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    assert first.details["requests_made"] == 12
    assert all(client.closed for client in clients)
    assert all(
        client.kwargs["minimum_interval"] == 0.5 for client in clients
    )


@pytest.mark.parametrize(
    ("source_id", "kind", "url"),
    [
        (
            osceola.CALENDAR_SOURCE_ID,
            "calendar",
            osceola.CALENDAR_URL,
        ),
        (
            osceola.FORECLOSURE_SOURCE_ID,
            "foreclosure",
            osceola.FORECLOSURE_URL,
        ),
    ],
)
def test_report_monitors_keep_head_metadata_rolling(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    kind: str,
    url: str,
) -> None:
    state = {"etag": '"first"', "last_modified": "first"}

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.request_count = 1

        def report_head(self, selected_kind: str) -> osceola.Artifact:
            assert selected_kind == kind
            return osceola.Artifact(
                content=b"",
                source_url=url,
                status_code=200,
                media_type="application/pdf",
                headers={
                    "content-length": "1234",
                    "etag": state["etag"],
                    "last-modified": state["last_modified"],
                },
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(osceola, "PioneerBenchmarkClient", FakeClient)
    first = public_records_monitor.probe_osceola_report(_context(source_id))
    state.update(etag='"second"', last_modified="second")
    second = public_records_monitor.probe_osceola_report(_context(source_id))

    assert first.status == second.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    assert first.details["requests_made"] == 1


def test_monitor_registration_and_docs_cover_all_three_sources() -> None:
    expected = {
        osceola.PORTAL_SOURCE_ID: (
            osceola.SEARCH_LANDING_URL,
            12,
            public_records_monitor.probe_osceola_benchmark,
        ),
        osceola.CALENDAR_SOURCE_ID: (
            osceola.CALENDAR_URL,
            1,
            public_records_monitor.probe_osceola_report,
        ),
        osceola.FORECLOSURE_SOURCE_ID: (
            osceola.FORECLOSURE_URL,
            1,
            public_records_monitor.probe_osceola_report,
        ),
    }
    for source_id, (endpoint, requests, handler) in expected.items():
        registered = public_records_monitor.HANDLER_REGISTRY[source_id]
        assert registered.endpoint == endpoint
        assert registered.expected_requests == requests
        assert registered.sentinel_record_count == 1
        assert registered.handler is handler

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    assert "## Osceola County Clerk Benchmark records" in legal
    assert "### Osceola Clerk Benchmark adapter" in tool_reference
    assert osceola.PORTAL_SOURCE_ID in tool_reference
