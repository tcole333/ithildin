from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_dc_court_directory_data as dc_data
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _probe_record(
    source_id: str,
    *,
    record_count: int,
    observation_count: int,
) -> dict[str, Any]:
    if source_id == dc_data.SUPERIOR_DIRECTORY_SOURCE_ID:
        role_counts = {
            "chief": 1,
            "associate": record_count - 58,
            "magistrate": 25,
            "senior": 32,
        }
        return {
            "record_kind": "source_health_check",
            "source_id": source_id,
            "canonical_ref": f"DC-COURTS:PROBE:{source_id}",
            "status": "ok",
            "record_count": sum(role_counts.values()),
            "role_counts": role_counts,
            "leadership_count": 2,
            "location_count": 4,
        }
    if source_id == dc_data.APPEALS_DIRECTORY_SOURCE_ID:
        role_counts = {
            "chief": 1,
            "associate": record_count - 6,
            "senior": 5,
        }
        return {
            "record_kind": "source_health_check",
            "source_id": source_id,
            "canonical_ref": f"DC-COURTS:PROBE:{source_id}",
            "status": "ok",
            "record_count": sum(role_counts.values()),
            "role_counts": role_counts,
            "leadership_count": 2,
            "location_count": 1,
        }
    assert source_id == dc_data.REPORTS_SOURCE_ID
    return {
        "record_kind": "source_health_check",
        "source_id": source_id,
        "canonical_ref": f"DC-COURTS:PROBE:{source_id}",
        "status": "ok",
        "publication_count": record_count,
        "section_counts": {
            "annual-reports": record_count - 40,
            "family-court-annual-reports": 40,
        },
        "catalog_observation_count": observation_count,
    }


@pytest.mark.parametrize(
    ("source_id", "first_count", "second_count", "first_observations"),
    [
        (dc_data.SUPERIOR_DIRECTORY_SOURCE_ID, 107, 108, 0),
        (dc_data.APPEALS_DIRECTORY_SOURCE_ID, 12, 13, 0),
        (dc_data.REPORTS_SOURCE_ID, 88, 90, 3),
    ],
)
def test_monitor_keeps_dc_rolling_counts_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    first_count: int,
    second_count: int,
    first_observations: int,
) -> None:
    rolling = {
        "record_count": first_count,
        "observation_count": first_observations,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.component == [source_id]
        assert log_results is False
        return PublicRecordsResult.success(
            dc_data.build_query(args),
            [_probe_record(source_id, **rolling)],
        )

    monkeypatch.setattr(dc_data, "execute", fake_execute)
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = (
        public_records_monitor.probe_dc_court_directory_data_component(
            context
        )
    )
    rolling.update(
        record_count=second_count,
        observation_count=first_observations + 2,
    )
    second = (
        public_records_monitor.probe_dc_court_directory_data_component(
            context
        )
    )

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    provenance = first.details["stable_contract"]["publisher_and_transport"]
    assert provenance == {
        "authority": "District of Columbia Courts",
        "publisher": "District of Columbia Courts",
        "retrieval_transport": "direct official HTTPS",
        "publisher_transport_distinct": False,
        "counts_as_independent_corroboration": False,
    }
    assert first.details["schema_contract"]["output_schema_version"] == (
        dc_data.OUTPUT_SCHEMA_VERSION
    )


def test_catalog_keeps_dc_components_and_product_types_distinct(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    superior = catalog.show_source(
        dc_data.SUPERIOR_DIRECTORY_SOURCE_ID
    )["current_manifest"]
    appeals = catalog.show_source(
        dc_data.APPEALS_DIRECTORY_SOURCE_ID
    )["current_manifest"]
    data_request = catalog.show_source(
        dc_data.DATA_REQUEST_SOURCE_ID
    )["current_manifest"]
    reports = catalog.show_source(dc_data.REPORTS_SOURCE_ID)[
        "current_manifest"
    ]

    assert superior["identity_contract"]["shared_ingest_semantics"] == (
        "snapshot_only"
    )
    assert appeals["identity_contract"]["shared_ingest_semantics"] == (
        "snapshot_only"
    )
    assert {
        item["role"] for item in superior["census_associations"]
    } == {"court_directory"}
    assert {
        item["role"] for item in appeals["census_associations"]
    } == {"court_directory"}

    assert data_request["access_class"] == "D"
    assert data_request["automation_disposition"] == "not_applicable"
    assert data_request["request_contract"][
        "direct_case_level_bulk_feed"
    ] is False
    assert reports["publication_contract"][
        "compiled_aggregate_publications"
    ] is True
    assert reports["publication_contract"][
        "case_level_bulk_feed"
    ] is False
    assert {
        item["role"] for item in data_request["census_associations"]
    } == {"bulk_data_program"}
    assert {
        item["role"] for item in reports["census_associations"]
    } == {"bulk_data_program"}

    catalog_ids = {
        item["source_id"] for item in catalog.list_sources()
    }
    assert dc_data.CATALOG_SOURCE_ID not in catalog_ids


def test_dc_monitor_registry_covers_direct_machine_readable_components() -> None:
    expected_requests = {
        dc_data.SUPERIOR_DIRECTORY_SOURCE_ID: 6,
        dc_data.APPEALS_DIRECTORY_SOURCE_ID: 2,
        dc_data.REPORTS_SOURCE_ID: 1,
    }
    for source_id, request_count in expected_requests.items():
        spec = public_records_monitor.HANDLER_REGISTRY[source_id]
        assert spec.handler is (
            public_records_monitor.probe_dc_court_directory_data_component
        )
        assert spec.expected_requests == request_count

    assert dc_data.DATA_REQUEST_SOURCE_ID not in (
        public_records_monitor.HANDLER_REGISTRY
    )
    assert dc_data.CATALOG_SOURCE_ID not in (
        public_records_monitor.HANDLER_REGISTRY
    )


def test_dc_source_citation_urls_are_registered() -> None:
    source_urls_path = (
        Path(__file__).parents[1] / "web" / "src" / "data" / "source-urls.json"
    )
    source_urls = json.loads(source_urls_path.read_text(encoding="utf-8"))
    expected = {
        dc_data.SUPERIOR_DIRECTORY_SOURCE_ID: (
            dc_data.SUPERIOR_DIRECTORY_URL
        ),
        dc_data.APPEALS_DIRECTORY_SOURCE_ID: (
            dc_data.APPEALS_DIRECTORY_URL
        ),
        dc_data.DATA_REQUEST_SOURCE_ID: dc_data.DATA_REQUEST_URL,
        dc_data.REPORTS_SOURCE_ID: dc_data.REPORTS_URL,
    }
    for source_id, expected_url in expected.items():
        assert source_urls[f"STATECOURT_SOURCE:{source_id}"] == expected_url

    assert (
        f"STATECOURT_SOURCE:{dc_data.CATALOG_SOURCE_ID}"
        not in source_urls
    )
