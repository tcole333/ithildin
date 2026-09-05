from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_michigan_property_directories as michigan
from tools import query_wisconsin_court_directory as wisconsin
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _michigan_probe_record(
    *,
    snapshot_fingerprint: str,
    platform_count: int,
    route_suffix: str,
) -> dict[str, Any]:
    sentinel_counties = (
        "Alcona",
        "Arenac",
        "Genesee",
        "Oakland",
        "Wayne",
        "Wexford",
    )
    return {
        "canonical_ref": "MI-DTMB-TAX-PARCEL-PROBE:26",
        "source_id": michigan.SOURCE_ID,
        "record_kind": "source_probe",
        "source_url": michigan.DIRECTORY_URL,
        "county_count": 83,
        "county_fips_count": 83,
        "platform_counts": {
            "county_or_local_web": platform_count,
            "bsa_online": 14,
        },
        "review_flag_counts": {
            "destination_capabilities_need_review": platform_count,
        },
        "partial_coverage_count": 1,
        "schema_fingerprint": "a" * 64,
        "snapshot_fingerprint": snapshot_fingerprint,
        "sentinels": {
            county: {
                "county_fips": michigan.COUNTY_FIPS[county],
                "official_url": (
                    f"https://example.gov/{county.casefold()}/{route_suffix}"
                ),
                "platform_family": (
                    "bsa_online" if county == "Arenac"
                    else "county_or_local_web"
                ),
                "route_signals": ["parcel_map_or_gis"],
            }
            for county in sentinel_counties
        },
    }


def _wisconsin_probe_record(
    *,
    snapshot_fingerprint: str,
    record_count: int,
) -> dict[str, Any]:
    components: dict[str, Any] = {}
    for index, component in enumerate(wisconsin.COMPONENTS, start=1):
        definition = wisconsin.COMPONENT_DEFINITIONS[component]
        components[component] = {
            "status": "ok",
            "record_count": record_count + index,
            "coverage": {
                "county_count": 72
                if component in wisconsin.COUNTY_COMPONENTS
                else None
            },
            "schema_fingerprint": f"{index:x}" * 64,
            "snapshot_fingerprint": snapshot_fingerprint,
            "source_url": definition["url"],
        }
    return {
        "canonical_ref": "WI-COURT-DIRECTORY-PROBE",
        "source_id": wisconsin.SOURCE_ID,
        "record_kind": "source_probe",
        "official_url": wisconsin.DIRECTORIES_URL,
        "component_count": len(wisconsin.COMPONENTS),
        "record_count": record_count,
        "components": components,
        "county_coverage": {
            "expected_count": 72,
            "county_geoids": list(wisconsin.COUNTY_FIPS.values()),
            "complete_components": list(wisconsin.COUNTY_COMPONENTS),
        },
        "snapshot_only": True,
    }


def test_michigan_directory_monitor_separates_contract_from_route_churn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "snapshot_fingerprint": "b" * 64,
        "platform_count": 60,
        "route_suffix": "first",
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert log_results is False
        return PublicRecordsResult.success(
            michigan._query(args),
            [_michigan_probe_record(**rolling)],
        )

    monkeypatch.setattr(michigan, "execute", fake_execute)
    context = ProbeContext(
        source_id=michigan.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = public_records_monitor.probe_michigan_property_directory(context)
    rolling.update(
        snapshot_fingerprint="c" * 64,
        platform_count=61,
        route_suffix="second",
    )
    second = public_records_monitor.probe_michigan_property_directory(context)

    assert first.status == "ok"
    assert first.result_count == 83
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != (
        second.details["rolling_observation"]
    )
    role = first.details["stable_contract"]["directory_role"]
    assert role["publisher_declared_role"] == (
        "county_tax_parcel_layer_routes"
    )
    assert role["destination_capabilities_verified_by_directory"] is False
    assert {
        item["source_id"]
        for item in first.details["stable_contract"]["official_alternatives"]
    } == {
        record["alternative_id"] for record in michigan._alternatives()
    }


def test_wisconsin_directory_monitor_preserves_component_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "snapshot_fingerprint": "d" * 64,
        "record_count": 240,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert log_results is False
        return PublicRecordsResult.success(
            wisconsin._query(args),
            [_wisconsin_probe_record(**rolling)],
        )

    monkeypatch.setattr(wisconsin, "execute", fake_execute)
    context = ProbeContext(
        source_id=wisconsin.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = public_records_monitor.probe_wisconsin_court_directory(context)
    rolling.update(
        snapshot_fingerprint="e" * 64,
        record_count=245,
    )
    second = public_records_monitor.probe_wisconsin_court_directory(context)

    assert first.status == "ok"
    assert first.result_count == 240
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != (
        second.details["rolling_observation"]
    )
    identity = first.details["schema_contract"]["identity_contract"]
    assert identity["source_component_identity_preserved"] is True
    assert identity["shared_ingest_semantics"] == "snapshot_only"
    assert {
        item["component"]
        for item in first.details["stable_contract"]["components"]
    } == set(wisconsin.COMPONENTS)


def test_catalog_exposes_directory_sources_complements_and_census_roles(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    michigan_decision = catalog.require_machine_acquisition(
        michigan.SOURCE_ID
    )
    wisconsin_decision = catalog.require_machine_acquisition(
        wisconsin.SOURCE_ID
    )
    assert michigan_decision["limits"]["minimum_interval_seconds"] == 0.25
    assert wisconsin_decision["limits"]["minimum_interval_seconds"] == 0.15

    michigan_manifest = catalog.show_source(michigan.SOURCE_ID)[
        "current_manifest"
    ]
    assert michigan_manifest["identity_contract"][
        "shared_ingest_semantics"
    ] == "snapshot_only"
    assert michigan_manifest["publication_contract"][
        "publisher_and_destination_evidence_separate"
    ] is True
    assert {
        association["role"]
        for association in michigan_manifest["census_associations"]
    } == {"parcel_geometry"}

    alternative_ids = {
        record["alternative_id"] for record in michigan._alternatives()
    }
    assert alternative_ids <= set(
        michigan_manifest["complementary_source_ids"]
    )
    for source_id in alternative_ids:
        assert catalog.show_source(source_id)["current_manifest"][
            "source_status"
        ] == "active"

    assessor = catalog.show_source("us-mi-local-assessor-records")[
        "current_manifest"
    ]
    recorder = catalog.show_source(
        "us-mi-treasury-register-of-deeds-directory"
    )["current_manifest"]
    foreclosure = catalog.show_source(
        "us-mi-treasury-foreclosing-governmental-units"
    )["current_manifest"]
    assert {item["role"] for item in assessor["census_associations"]} == {
        "assessment_roll"
    }
    assert {item["role"] for item in recorder["census_associations"]} == {
        "land_records_index"
    }
    assert {item["role"] for item in foreclosure["census_associations"]} == {
        "tax_collection"
    }

    wisconsin_manifest = catalog.show_source(wisconsin.SOURCE_ID)[
        "current_manifest"
    ]
    assert wisconsin_manifest["identity_contract"][
        "shared_ingest_semantics"
    ] == "snapshot_only"
    assert {
        item["role"]
        for item in wisconsin_manifest["census_associations"]
    } == {"court_directory"}
    assert set(wisconsin_manifest["identity_contract"][
        "component_record_kinds"
    ]) == set(wisconsin.COMPONENTS)

    assert public_records_monitor.HANDLER_REGISTRY[
        michigan.SOURCE_ID
    ].handler is public_records_monitor.probe_michigan_property_directory
    assert public_records_monitor.HANDLER_REGISTRY[
        wisconsin.SOURCE_ID
    ].handler is public_records_monitor.probe_wisconsin_court_directory
    assert public_records_monitor.HANDLER_REGISTRY[
        michigan.SOURCE_ID
    ].expected_requests == 1
    assert public_records_monitor.HANDLER_REGISTRY[
        wisconsin.SOURCE_ID
    ].expected_requests == 6


def test_directory_and_complement_citation_urls_are_registered() -> None:
    source_urls_path = (
        Path(__file__).parents[1] / "web" / "src" / "data" / "source-urls.json"
    )
    source_urls = json.loads(source_urls_path.read_text(encoding="utf-8"))

    assert source_urls[
        f"STATECOURT_SOURCE:{wisconsin.SOURCE_ID}"
    ] == wisconsin.DIRECTORIES_URL
    assert source_urls[
        f"PROPERTY_SOURCE:{michigan.SOURCE_ID}"
    ] == michigan.DIRECTORY_URL
    for alternative in michigan._alternatives():
        assert source_urls[
            f"PROPERTY_SOURCE:{alternative['alternative_id']}"
        ] == alternative["official_url"]
