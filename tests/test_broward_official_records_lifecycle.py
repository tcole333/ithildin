from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_broward_official_records as broward
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import (
    PublicRecordsError,
    PublicRecordsResult,
    ResultStatus,
)
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _monitor_context() -> ProbeContext:
    return ProbeContext(
        source_id=broward.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_broward_monitor_hashes_route_contract_not_rolling_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "released_through_date": "07/29/2026",
        "released_through_instrument": "120000001",
    }

    def fake_execute(args: Any) -> PublicRecordsResult:
        assert args.command == "probe"
        record = {
            "source_id": broward.SOURCE_ID,
            "record_kind": "source_probe",
            "ok": True,
            "title": "Broward County Official Records",
            "source_url": broward.SEARCH_URL,
            "schema_fingerprint": "a" * 64,
            "release": {
                **rolling,
                "release_as_of": "07/30/2026 08:00 AM",
            },
            "search_routes": [
                {
                    "text": selector,
                    "href": f"{broward.BASE_URL}{path}",
                }
                for selector, path in broward.PORTAL_SEARCH_PATHS.items()
            ],
            "coverage_statements": [
                "All plats and maps, regardless of record date, are searchable.",
                "Other Official Records documents from 7/7/1977 are searchable.",
                "Documents recorded from 3/9/1972 through 7/7/1977 have locator search.",
                "Documents recorded prior to 3/9/1972 are not on the portal.",
            ],
        }
        return PublicRecordsResult.success(
            broward.build_query(args),
            [record],
        )

    monkeypatch.setattr(broward, "execute", fake_execute)
    first = public_records_monitor.probe_broward_official_records(
        _monitor_context()
    )
    rolling.update(
        released_through_date="07/30/2026",
        released_through_instrument="120000999",
    )
    second = public_records_monitor.probe_broward_official_records(
        _monitor_context()
    )

    assert first.status == "ok"
    assert first.result_count == len(broward.PORTAL_SEARCH_PATHS)
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != (
        second.details["rolling_observation"]
    )
    assert set(first.details["stable_contract"]["routes"]) == {
        "portal_search",
        "certified_copy",
        "daily_bulk",
        "older_record_service",
    }


def test_broward_monitor_retains_contract_when_live_portal_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute(args: Any) -> PublicRecordsResult:
        return PublicRecordsResult.failure(
            broward.build_query(args),
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="browser_blocked",
                    message="public portal returned a security-service block",
                    category="browser",
                    retryable=True,
                )
            ],
        )

    monkeypatch.setattr(broward, "execute", fake_execute)
    observation = public_records_monitor.probe_broward_official_records(
        _monitor_context()
    )

    assert observation.status == "unavailable"
    assert observation.schema_sha256
    assert observation.artifact_sha256
    assert observation.details["rolling_observation"]["status"] == (
        "unavailable"
    )
    assert set(observation.details["stable_contract"]["routes"]) == {
        "portal_search",
        "certified_copy",
        "daily_bulk",
        "older_record_service",
    }


def test_broward_catalog_census_monitor_and_citation_lifecycle(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    decision = catalog.require_machine_acquisition(broward.SOURCE_ID)
    assert decision["allowed"] is True
    detail = catalog.show_source(broward.SOURCE_ID)
    manifest = detail["current_manifest"]
    assert {item["geoid"] for item in detail["jurisdictions"]} == {
        broward.COUNTY_GEOID
    }
    assert manifest["identity_contract"]["durable_identity"] == (
        "instrument_number"
    )
    assert manifest["publication_contract"]["daily_bulk"]["availability"] == (
        "ten_continuous_days"
    )
    assert set(manifest["publication_contract"]) == {
        "portal_search",
        "public_pdf",
        "certified_copy",
        "daily_bulk",
        "older_record_service",
    }
    assert [association["role"] for association in manifest["census_associations"]] == [
        "land_records_index"
    ]
    assert all(
        association["jurisdiction_geoid"] == "12"
        for association in manifest["census_associations"]
    )

    spec = public_records_monitor.HANDLER_REGISTRY[broward.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_broward_official_records
    assert spec.expected_requests == 1

    source_urls_path = (
        Path(__file__).parents[1] / "web" / "src" / "data" / "source-urls.json"
    )
    source_urls = json.loads(source_urls_path.read_text(encoding="utf-8"))
    assert source_urls[f"PROPERTY_SOURCE:{broward.SOURCE_ID}"] == (
        broward.SEARCH_URL
    )
