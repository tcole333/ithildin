from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import public_records_search_plan
from tools import query_ohio_franklin_sales_gis as sales
from tools import query_property
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import seed_catalog
from tools.source_report import check_public_records_catalog


SOURCE_ID = sales.SOURCE_ID
SOURCE_CONFIG = Path("config/public_records_sources.yaml")
CENSUS_CONFIG = Path("config/public_records_census.yaml")
CITATION_CONFIG = Path("web/src/data/source-urls.json")
SHARED_OPERATIONS = {
    "address",
    "count",
    "discovery",
    "fid",
    "freshness",
    "geometry",
    "instrument",
    "map",
    "owner",
    "parcel",
    "probe",
    "sale",
    "search",
}


def _translated(*values: str) -> Any:
    args = query_property.build_parser().parse_args(list(values))
    route = query_property.LIVE_ROUTES[SOURCE_ID][args.command]
    return route.translate(args, route.adapter_command)


def _manifest() -> dict[str, Any]:
    payload = yaml.safe_load(SOURCE_CONFIG.read_text(encoding="utf-8"))
    return next(
        source
        for source in payload["sources"]
        if source["source_id"] == SOURCE_ID
    )


def test_shared_routes_preserve_source_operations_and_semantics() -> None:
    assert set(query_property.LIVE_ROUTES[SOURCE_ID]) == SHARED_OPERATIONS
    guidance = query_property._source_guidance(SOURCE_ID)
    assert guidance["direct_default"] == "all_matching_OBJECTID_keyset_pages"
    assert set(guidance["shared_selectors"]) == SHARED_OPERATIONS

    cases = (
        (("search", "SMITH"), "search", "all"),
        (("search", "N", "--search-field", "validity"), "validity", None),
        (("owner", "SMITH"), "party", None),
        (("address", "CASSADY"), "search", "address"),
        (("parcel", "010-000006"), "parcel", None),
        (("map", "010-000006"), "parcel", None),
        (("fid", "1"), "search", "object-id"),
        (("geometry", "1"), "search", "object-id"),
        (("instrument", "00004012"), "conveyance", None),
        (("count", "all"), "count", None),
        (("freshness",), "schema", None),
        (("discovery", "layers"), "layers", None),
        (("probe",), "probe", None),
    )
    for shared_values, command, field in cases:
        translated = _translated(*shared_values, "--source", SOURCE_ID)
        assert translated.command == command
        assert getattr(translated, "field", None) == field

    assert _translated(
        "map",
        "010-000006",
        "--source",
        SOURCE_ID,
    ).geometry is True
    exact_date = _translated(
        "sale",
        "2024-03-19",
        "--source",
        SOURCE_ID,
    )
    assert exact_date.start.isoformat() == "2024-03-19"
    assert exact_date.end.isoformat() == "2024-03-19"


def test_shared_translation_has_no_implicit_cap_and_preserves_bound_window() -> None:
    exhaustive = _translated(
        "parcel",
        "010-000006",
        "--source",
        SOURCE_ID,
        "--jurisdiction",
        "39049",
    )
    bounded = _translated(
        "parcel",
        "010-000006",
        "--source",
        SOURCE_ID,
        "--county",
        "Franklin",
        "--limit",
        "7",
        "--cursor",
        "ohio-franklin:auditor-sales-gis:test",
        "--max-records",
        "20",
        "--page-size",
        "777",
    )

    assert exhaustive.limit is None
    assert exhaustive.cursor is None
    assert bounded.limit == 7
    assert bounded.cursor == "ohio-franklin:auditor-sales-gis:test"
    assert bounded.page_size == 777


def _probe_result(
    *,
    count: int = 98_291,
    last_update_max: int = 1_785_444_211_000,
    schema_fingerprint: str = "a" * 64,
    request_count: int = sales.PROBE_EXPECTED_REQUESTS,
    null_global_ids: int = 0,
) -> PublicRecordsResult:
    query = PublicRecordsQuery(
        source=sales.SOURCE_METADATA,
        jurisdiction=sales.JURISDICTION,
        query=QueryMetadata(operation="probe"),
    )
    return PublicRecordsResult.success(
        query,
        [
            {
                "source_id": SOURCE_ID,
                "service_item_id": sales.ITEM_ID,
                "layer_id": sales.LAYER_ID,
                "schema_fingerprint": schema_fingerprint,
                "maximum_page_size": 2_000,
                "record_count": count,
                "identity_audit": {
                    "null_global_id_occurrences": null_global_ids,
                    "distinct_global_id_occurrences": count - null_global_ids,
                    "null_parcel_id_occurrences": 0,
                    "blank_parcel_id_occurrences": 0,
                    "null_conveyance_number_occurrences": 0,
                    "blank_conveyance_number_occurrences": 0,
                },
                "rolling_coverage": {
                    "sale_date_min": 1_672_704_000_000,
                    "sale_date_max": 1_752_624_001_000,
                    "last_update_min": 1_733_130_908_000,
                    "last_update_max": last_update_max,
                },
                "sentinel_occurrence_identity": {
                    "identity_kind": "GlobalID",
                    "native_id": "{0A9D3B4A-060D-4B4F-A84B-DF332C586A1F}",
                },
                "probe_request_count": request_count,
            }
        ],
        retrieved_at="2026-07-31T12:00:00Z",
    )


def _probe_context() -> ProbeContext:
    return ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=1,
        max_attempts=1,
        sample_bytes=None,
    )


def test_monitor_separates_stable_contract_from_rolling_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"count": 98_291, "last_update_max": 1_785_444_211_000}

    def fake_execute(_args: Any, **_kwargs: Any) -> PublicRecordsResult:
        return _probe_result(**state)

    monkeypatch.setattr(sales, "execute", fake_execute)
    first = public_records_monitor.probe_ohio_franklin_auditor_sales_gis(
        _probe_context()
    )
    state.update(count=98_400, last_update_max=1_785_500_000_000)
    rolling = public_records_monitor.probe_ohio_franklin_auditor_sales_gis(
        _probe_context()
    )

    assert first.schema_sha256 == rolling.schema_sha256
    assert first.artifact_sha256 == rolling.artifact_sha256
    assert first.details["rolling_observation"] != rolling.details[
        "rolling_observation"
    ]
    assert compare_probes(first.to_dict(), rolling.to_dict())["drift_detected"] is False


def test_monitor_enforces_actual_request_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sales,
        "execute",
        lambda *_args, **_kwargs: _probe_result(request_count=8),
    )
    with pytest.raises(ValueError, match="request contract changed"):
        public_records_monitor.probe_ohio_franklin_auditor_sales_gis(
            _probe_context()
        )


def test_monitor_enforces_global_id_uniqueness_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _probe_result()
    record = dict(result.records[0])
    record["identity_audit"] = {
        **record["identity_audit"],
        "distinct_global_id_occurrences": record["record_count"] - 1,
    }
    drifted = PublicRecordsResult.success(
        result.query,
        [record],
        retrieved_at=result.retrieved_at,
    )
    monkeypatch.setattr(sales, "execute", lambda *_args, **_kwargs: drifted)

    with pytest.raises(ValueError, match="identity is not unique"):
        public_records_monitor.probe_ohio_franklin_auditor_sales_gis(
            _probe_context()
        )


def test_monitor_accepts_object_id_fallback_for_null_global_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sales,
        "execute",
        lambda *_args, **_kwargs: _probe_result(null_global_ids=1),
    )

    observation = public_records_monitor.probe_ohio_franklin_auditor_sales_gis(
        _probe_context()
    )
    assert observation.details["rolling_observation"]["identity_audit"] == {
        "null_global_id_occurrences": 1,
        "distinct_global_id_occurrences": 98_290,
        "null_parcel_id_occurrences": 0,
        "blank_parcel_id_occurrences": 0,
        "null_conveyance_number_occurrences": 0,
        "blank_conveyance_number_occurrences": 0,
    }


def test_catalog_census_search_plan_source_report_monitor_and_citation(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    census = yaml.safe_load(CENSUS_CONFIG.read_text(encoding="utf-8"))
    citations = json.loads(CITATION_CONFIG.read_text(encoding="utf-8"))
    source_ids = [
        source["source_id"]
        for source in yaml.safe_load(
            SOURCE_CONFIG.read_text(encoding="utf-8")
        )["sources"]
    ]

    assert source_ids.count(SOURCE_ID) == 1
    assert manifest["source_status"] == "active"
    assert manifest["adapter_version"] == 1
    assert manifest["census_associations"][0]["role"] == "assessor_sale_history"
    assert manifest["layer_contract"]["renderer_alias_layers"] == [1, 2, 3, 4]
    assert manifest["projection_contract"]["positive_dated_price"] == (
        "project_assessor_sale_event"
    )
    targets = {
        (row["jurisdiction_geoid"], row["domain"], row["role"])
        for row in census["additional_targets"]
    }
    assert ("39049", "property", "assessor_sale_history") in targets
    assert citations[f"PROPERTY_SOURCE:{SOURCE_ID}"] == sales.LAYER_URL

    monitor = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]
    assert monitor.expected_requests == sales.PROBE_EXPECTED_REQUESTS == 10
    assert monitor.handler is (
        public_records_monitor.probe_ohio_franklin_auditor_sales_gis
    )

    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path)
    assert seeded["manifests_registered"] > 0
    plan = public_records_search_plan.build_search_plan(
        "LAMAR EQUITY INVESTMENTS LLC",
        jurisdictions=("39049",),
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
        profiles_dir=tmp_path / "profiles",
    )
    tasks = {
        task["task_id"]
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "property"
        for task in stage["tasks"]
        if task["source_id"] == SOURCE_ID
    }
    assert tasks == {
        f"property.{SOURCE_ID}.fetch_geometry",
        f"property.{SOURCE_ID}.search_parcels",
        f"property.{SOURCE_ID}.search_parties",
        f"property.{SOURCE_ID}.search_sales",
    }

    report = check_public_records_catalog(catalog_path)
    source_report = next(
        row for row in report.values() if row.get("source_id") == SOURCE_ID
    )
    assert source_report["status"] == "configured"
    assert source_report["query_tool"] == "tools/query_property.py"
