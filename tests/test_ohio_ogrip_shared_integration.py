from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import public_records_search_plan
from tools import query_ohio_statewide_parcels as ohio
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import (
    ProbeContext,
    compare_probes,
    probe_ohio_statewide_parcels,
)
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_statewide_parcels"
)
SOURCE_CONFIG = Path("config/public_records_sources.yaml")
CENSUS_CONFIG = Path("config/public_records_census.yaml")
OHIO_ROUTE_SOURCE_IDS = {
    "us-oh-ogrip-statewide-parcels",
    "us-oh-franklin-county-auditor-property",
    "us-oh-franklin-county-recorder-publicsearch",
    "us-oh-licking-county-auditor-ontrac",
    "us-oh-licking-county-recorder-pax",
    "us-oh-licking-county-recorder-instrument-detail",
    "us-oh-licking-county-recorder-archives",
    "us-oh-delaware-county-auditor-property",
    "us-oh-delaware-county-auditor-gis",
    "us-oh-delaware-county-recorder-pax",
}
SHARED_OPERATIONS = {
    "address",
    "count",
    "discovery",
    "freshness",
    "land-use",
    "map",
    "parcel",
    "probe",
    "search",
}


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _fixture_feature(index: int = 0) -> dict[str, Any]:
    payload = json.loads(
        (FIXTURE_ROOT / "features.json").read_text(encoding="utf-8")
    )
    return deepcopy(payload["features"][index])


def _normalized_record(
    *,
    feature: dict[str, Any] | None = None,
    geometry: bool = True,
) -> dict[str, Any]:
    return ohio._normalize_feature(
        feature or _fixture_feature(),
        schema_fingerprint="a" * 64,
        geometry_requested=geometry,
    )


def _envelope(record: dict[str, Any]) -> dict[str, Any]:
    args = ohio.build_parser().parse_args(
        ["parcel", "39049-010-042534", "--geometry"]
    )
    return PublicRecordsResult.success(
        ohio._build_query(args),
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _source_manifests() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(SOURCE_CONFIG.read_text(encoding="utf-8"))
    return {
        source["source_id"]: source
        for source in payload["sources"]
        if source["source_id"] in OHIO_ROUTE_SOURCE_IDS
    }


def test_shared_route_manifest_and_canonical_keys_are_exact() -> None:
    routes = query_property.LIVE_ROUTES[ohio.SOURCE_ID]
    manifests = _source_manifests()
    manifest = manifests[ohio.SOURCE_ID]
    shared = next(
        capability
        for capability in manifest["capabilities"]
        if capability["name"] == "query_shared_property_records"
    )
    record = _normalized_record()

    assert set(routes) == SHARED_OPERATIONS
    assert set(shared["details"]["shared_operations"]) == SHARED_OPERATIONS
    assert set(manifests) == OHIO_ROUTE_SOURCE_IDS
    assert manifest["stable_keys"] == [
        "state_parcel_id",
        "county_local_parcel_id",
        "global_id",
        "object_id",
    ]
    assert all(key in record for key in manifest["stable_keys"])
    assert record["state_parcel_id"] == "39049-010-042534"
    assert record["local_parcel_id"] == "010-042534"
    assert record["county_local_parcel_id"] == "39049|010-042534"


def test_shared_translation_preserves_exhaustive_default_and_caller_bounds() -> None:
    parcel = query_property._ohio_statewide_parcel_args(
        _shared_args(
            "parcel",
            "39049-010-042534",
            "--source",
            ohio.SOURCE_ID,
            "--jurisdiction",
            "39049",
        ),
        "parcel",
    )
    bounded = query_property._ohio_statewide_parcel_args(
        _shared_args(
            "search",
            "DODRIDGE",
            "--source",
            ohio.SOURCE_ID,
            "--county",
            "Franklin",
            "--search-field",
            "mailing",
            "--limit",
            "7",
            "--cursor",
            "cursor-value",
        ),
        "search",
    )
    mapped = query_property._ohio_statewide_parcel_args(
        _shared_args(
            "map",
            "39049-010-042534",
            "--source",
            ohio.SOURCE_ID,
        ),
        "parcel",
    )
    land_use = query_property._ohio_statewide_parcel_args(
        _shared_args(
            "land-use",
            "520",
            "--source",
            ohio.SOURCE_ID,
            "--county-fips",
            "049",
        ),
        "land-use",
    )
    freshness = query_property._ohio_statewide_parcel_args(
        _shared_args(
            "freshness",
            "--source",
            ohio.SOURCE_ID,
        ),
        "metadata",
    )

    assert parcel.command == "parcel"
    assert parcel.county == "39049"
    assert parcel.limit is None
    assert bounded.command == "search"
    assert bounded.field == "mailing"
    assert bounded.limit == 7
    assert bounded.cursor == "cursor-value"
    assert mapped.geometry is True
    assert land_use.command == "search"
    assert land_use.field == "land-use"
    assert land_use.county == "39049"
    assert freshness.command == "metadata"


def test_shared_translation_rejects_conflicting_ohio_counties() -> None:
    args = _shared_args(
        "parcel",
        "39049-010-042534",
        "--source",
        ohio.SOURCE_ID,
        "--jurisdiction",
        "39049",
        "--county",
        "Licking",
    )

    with pytest.raises(ValueError, match="county selectors conflict"):
        query_property._ohio_statewide_parcel_args(args, "parcel")


def test_missing_state_parcel_id_remains_a_feature_occurrence() -> None:
    feature = _fixture_feature()
    feature["attributes"]["StateParcelID"] = None
    record = _normalized_record(feature=feature)

    assert record["state_parcel_id"] is None
    assert "/feature_occurrence/" in record["canonical_ref"]
    assert "/parcel/" not in record["canonical_ref"]
    assert record["native_id"] == record["global_id"]


def test_ogrip_projection_creates_only_parcel_address_geometry_context(
    tmp_path: Path,
) -> None:
    record = _normalized_record()
    db_path = tmp_path / "property.db"

    report = ingest_property_envelope(_envelope(record), db_path=db_path)

    assert report["records_ingested"] == 1
    projection = report["records"][0]
    assert projection["land_observation_preserved"] is True
    assert projection["owners_upserted"] == 0
    assert projection["assessments_upserted"] == 0
    assert projection["sales_upserted"] == 0
    assert projection["geometry_upserted"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT native_parcel_id, roll_year, source_good_through, raw_json
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (ohio.SOURCE_ID,),
        ).fetchone()
        aliases = {
            (row["alias_type"], row["alias_value"])
            for row in db.execute(
                """
                SELECT alias_type, alias_value
                FROM parcel_alias
                WHERE source_id=?
                """,
                (ohio.SOURCE_ID,),
            )
        }
        addresses = db.execute(
            """
            SELECT address_role, raw_address
            FROM parcel_address
            WHERE source_id=?
            ORDER BY address_role
            """,
            (ohio.SOURCE_ID,),
        ).fetchall()
        geometry = db.execute(
            """
            SELECT geometry_format, crs, accuracy_disclaimer
            FROM parcel_geometry
            WHERE source_id=?
            """,
            (ohio.SOURCE_ID,),
        ).fetchone()
        assertion_counts = {
            table: db.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in (
                "ownership_assertion",
                "assessment",
                "sale_event",
                "tax_account_event",
                "recorded_instrument",
            )
        }
    finally:
        db.close()

    assert parcel["native_parcel_id"] == "39049-010-042534"
    assert parcel["roll_year"] == ""
    assert (
        parcel["source_good_through"]
        == record["source_freshness"]["current_to_iso"]
    )
    assert json.loads(parcel["raw_json"])["land"] == record["land"]
    assert aliases == {
        ("local_parcel_id", "010-042534"),
        ("local_parcel_id_normalized", "010042534"),
        ("county_local_parcel_id", "39049|010-042534"),
    }
    assert {(row["address_role"], row["raw_address"]) for row in addresses} == {
        ("situs", "84 W DODRIDGE ST"),
        ("mailing", "84 W DODRIDGE ST COLUMBUS OH 43202"),
    }
    assert geometry["geometry_format"] == "esri_json"
    assert geometry["crs"] == "EPSG:4326"
    assert "county-contributed" in geometry["accuracy_disclaimer"]
    assert assertion_counts == {
        "ownership_assertion": 0,
        "assessment": 0,
        "sale_event": 0,
        "tax_account_event": 0,
        "recorded_instrument": 0,
    }


def test_missing_state_parcel_id_is_preserved_without_projection(
    tmp_path: Path,
) -> None:
    feature = _fixture_feature()
    feature["attributes"]["StateParcelID"] = None
    record = _normalized_record(feature=feature)

    report = ingest_property_envelope(
        _envelope(record),
        db_path=tmp_path / "property.db",
    )

    assert report["records_ingested"] == 0
    assert report["records_preserved_without_projection"] == 1
    assert report["projection_skips"][0]["reason"] == (
        "ohio_row_is_not_a_state_identified_parcel_observation"
    )


def _probe_result(
    *,
    count_delta: int = 0,
    current_to: str = "2023-09-26T20:32:00Z",
) -> PublicRecordsResult:
    args = ohio.build_parser().parse_args(["probe"])
    targets = []
    for geoid, target in ohio.TARGET_COUNTIES.items():
        targets.append(
            {
                "county_geoid": geoid,
                "county_name": target["name"],
                "record_count": int(target["observed_count"]) + count_delta,
                "prior_observed_count": target["observed_count"],
                "prior_observed_at": target["observed_at"],
                "sample_state_parcel_id": target["sample_state_parcel_id"],
                "sample_current_to_iso": current_to,
            }
        )
    return PublicRecordsResult.success(
        ohio._build_query(args),
        [
            {
                "source_id": ohio.SOURCE_ID,
                "county_count": 88,
                "expected_statewide_county_count": 88,
                "maximum_page_size": 2000,
                "schema_fingerprint": "b" * 64,
                "target_counties": targets,
            }
        ],
        retrieved_at="2026-07-30T12:00:00Z",
    )


def test_monitor_hashes_stable_contract_but_not_rolling_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"count_delta": 0, "current_to": "2023-09-26T20:32:00Z"}

    def fake_execute(_args: Any, **_kwargs: Any) -> PublicRecordsResult:
        return _probe_result(**state)

    monkeypatch.setattr(ohio, "execute", fake_execute)
    context = ProbeContext(
        source_id=ohio.SOURCE_ID,
        catalog_decision={"limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = probe_ohio_statewide_parcels(context)
    state.update(count_delta=9, current_to="2026-07-30T00:00:00Z")
    rolling = probe_ohio_statewide_parcels(context)
    rolling_comparison = compare_probes(first.to_dict(), rolling.to_dict())

    assert first.schema_sha256 == rolling.schema_sha256
    assert first.artifact_sha256 == rolling.artifact_sha256
    assert rolling_comparison["drift_detected"] is False
    assert (
        first.details["rolling_observation"]["target_counties"][0][
            "record_count"
        ]
        != rolling.details["rolling_observation"]["target_counties"][0][
            "record_count"
        ]
    )

    monkeypatch.setattr(ohio, "FIELDS", (*ohio.FIELDS, "FutureField"))
    contract_change = probe_ohio_statewide_parcels(context)
    stable_comparison = compare_probes(
        rolling.to_dict(),
        contract_change.to_dict(),
    )
    assert contract_change.artifact_sha256 != rolling.artifact_sha256
    assert stable_comparison["drift_detected"] is True


def test_monitor_registry_matches_native_probe_shape() -> None:
    handler = public_records_monitor.HANDLER_REGISTRY[ohio.SOURCE_ID]

    assert handler.expected_requests == 8
    assert handler.sentinel_record_count == 1
    assert handler.sample_bytes is None
    assert handler.handler is probe_ohio_statewide_parcels


def test_catalog_census_and_exact_search_plan_cover_each_county(
    tmp_path: Path,
) -> None:
    manifests = _source_manifests()
    census = yaml.safe_load(CENSUS_CONFIG.read_text(encoding="utf-8"))
    additional_jurisdictions = {
        row["geoid"]: row for row in census["additional_jurisdictions"]
    }
    targets = {
        (row["jurisdiction_geoid"], row["domain"], row["role"])
        for row in census["additional_targets"]
    }
    ogrip_associations = {
        (row["jurisdiction_geoid"], row["role"])
        for row in manifests[ohio.SOURCE_ID]["census_associations"]
    }

    assert {
        geoid: additional_jurisdictions[geoid]["parent_geoid"]
        for geoid in ("39049", "39089", "39041")
    } == {
        "39049": "39",
        "39089": "39",
        "39041": "39",
    }
    assert "parcel_geometry" in census["roles"]["property"]
    for geoid in ("39049", "39089", "39041"):
        assert (geoid, "property", "assessment_roll") in targets
        assert (geoid, "property", "parcel_geometry") in targets
        assert (geoid, "property", "land_records_index") in targets
        assert (geoid, "parcel_geometry") in ogrip_associations
    assert ("39", "parcel_geometry") in ogrip_associations

    licking = manifests["us-oh-licking-county-auditor-ontrac"]
    licking_exact = manifests[
        "us-oh-licking-county-recorder-instrument-detail"
    ]
    licking_archives = manifests["us-oh-licking-county-recorder-archives"]
    assert (licking["access_class"], licking["automation_disposition"]) == (
        "B",
        "unclear",
    )
    assert (
        licking["capabilities"][0]["details"]["observed_route_state"]
        == "http_403_on_2026_07_30"
    )
    licking_alternative_ids = {
        item["source_id"] for item in licking["field_matched_alternatives"]
    }
    assert {
        ohio.SOURCE_ID,
        "us-oh-licking-county-auditor-gis",
    } <= licking_alternative_ids
    assert (
        licking_exact["automation_disposition"]
        == "allowed_with_limits"
    )
    assert licking_archives["automation_disposition"] == "not_applicable"

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = public_records_search_plan.build_search_plan(
        "INN INVESTMENT CORP.",
        jurisdictions=("39049", "39089", "39041"),
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
        profiles_dir=tmp_path / "profiles",
    )
    property_tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "property"
        for task in stage["tasks"]
        if task["source_id"] in OHIO_ROUTE_SOURCE_IDS
    }
    recorder_tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "recorder"
        for task in stage["tasks"]
        if task["source_id"] in OHIO_ROUTE_SOURCE_IDS
    }

    assert {
        "property.us-oh-franklin-county-auditor-property.search_owner",
        "property.us-oh-licking-county-auditor-ontrac.search_owner",
        "property.us-oh-delaware-county-auditor-property.search_owner",
        "property.us-oh-ogrip-statewide-parcels.search_parcels",
        "property.us-oh-ogrip-statewide-parcels.fetch_geometry",
    } <= set(property_tasks)
    assert {
        "recorder.us-oh-franklin-county-recorder-publicsearch.search_instruments",
        "recorder.us-oh-licking-county-recorder-pax.search_instruments",
        "recorder.us-oh-licking-county-recorder-instrument-detail.fetch_instrument",
        "recorder.us-oh-licking-county-recorder-archives.request_instrument_copy",
        "recorder.us-oh-delaware-county-recorder-pax.search_instruments",
    } <= set(recorder_tasks)
    assert (
        recorder_tasks[
            "recorder.us-oh-licking-county-recorder-instrument-detail.fetch_instrument"
        ]["catalog_access"]["mode"]
        == "allowed_with_limits"
    )
    assert plan["coverage"]["query_template_counts"]["property"] >= 15
    assert plan["coverage"]["query_template_counts"]["recorder"] >= 10
