from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tools.public_records_catalog import CatalogError, PublicRecordsCatalog
from tools.public_records_monitor import (
    HANDLER_REGISTRY,
    ProbeHandlerSpec,
    ProbeObservation,
    compare_probes,
    diff_history,
    history,
    plan_sources,
    record_observation,
    registered_handlers,
    run_sources,
)


NOW = "2026-07-28T12:00:00Z"
NC_SOURCE = "us-nc-onemap-parcels"
MA_SOURCE = "us-ma-massgis-parcels"
OTHER_SOURCE = "us-tx-local-parcels"
BLOCKED_SOURCE = "us-ny-local-courts"


def manifest(
    source_id: str,
    *,
    geoid: str,
    access_class: str = "A",
    disposition: str = "allowed",
) -> dict:
    return {
        "source_id": source_id,
        "name": source_id,
        "domain": "court" if "courts" in source_id else "property",
        "roles": ["assessment"],
        "authority": "Test public authority",
        "operator": "Test public operator",
        "jurisdiction_geoids": [geoid],
        "official_url": f"https://example.test/{source_id}",
        "platform_family": "documented_rest",
        "access_class": access_class,
        "automation_disposition": disposition,
        "authentication": "none",
        "fees": "none",
        "redistribution": "source_terms_apply",
        "protected_record_policy": "source_managed",
        "coverage_start": "2020",
        "update_cadence": "source_managed",
        "stable_keys": ["native_id"],
        "adapter_family": "test",
        "adapter_version": 1,
        "last_verified_at": NOW,
        "source_status": "active",
        "capabilities": ["probe"],
    }


def add_source(
    catalog: PublicRecordsCatalog,
    source_id: str,
    *,
    geoid: str,
    access_class: str = "A",
    disposition: str = "allowed",
) -> None:
    catalog.register_manifest(
        manifest(
            source_id,
            geoid=geoid,
            access_class=access_class,
            disposition=disposition,
        ),
        submitted_by="test",
        submitted_at=NOW,
    )
    catalog.evaluate_access(
        source_id,
        access_class=access_class,
        automation_disposition=disposition,
        reviewed_by="test",
        reviewed_at=NOW,
        review_basis="Test catalog decision",
    )


@pytest.fixture
def catalog(tmp_path: Path) -> PublicRecordsCatalog:
    value = PublicRecordsCatalog(tmp_path / "catalog.db")
    add_source(value, NC_SOURCE, geoid="37")
    add_source(value, MA_SOURCE, geoid="25")
    add_source(value, OTHER_SOURCE, geoid="48")
    add_source(
        value,
        BLOCKED_SOURCE,
        geoid="36",
        access_class="C",
        disposition="prohibited",
    )
    return value


def handler_spec(
    source_id: str,
    handler: Callable,
) -> ProbeHandlerSpec:
    return ProbeHandlerSpec(
        source_id=source_id,
        capability="probe",
        endpoint=f"https://example.test/{source_id}/probe",
        observation="Test sentinel",
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=handler,
    )


def ok_observation(
    *,
    schema: str = "1" * 64,
    artifact: str | None = None,
    status: str = "ok",
) -> ProbeObservation:
    return ProbeObservation(
        status=status,
        endpoint="https://example.test/probe",
        http_status=200,
        schema_sha256=schema,
        artifact_sha256=artifact,
        result_count=0 if status == "no_results" else 1,
        details={"fixture": True},
    )


def test_handler_registry_is_centralized_and_visible():
    assert set(HANDLER_REGISTRY) == {NC_SOURCE, MA_SOURCE}
    visible = registered_handlers()
    assert [item["source_id"] for item in visible] == [
        MA_SOURCE,
        NC_SOURCE,
    ]
    massgis = next(item for item in visible if item["source_id"] == MA_SOURCE)
    assert massgis["sample_bytes"] == 4096
    assert massgis["expected_requests"] == 3


def test_plan_reads_catalog_decisions_without_dispatching(catalog):
    calls = []

    def handler(_context):
        calls.append("called")
        return ok_observation()

    handlers = {NC_SOURCE: handler_spec(NC_SOURCE, handler)}
    result = plan_sources(catalog, [NC_SOURCE, OTHER_SOURCE], handlers=handlers)

    assert calls == []
    assert result["sources"][0]["mode"] == "registered_probe"
    assert result["sources"][0]["catalog_decision"]["allowed"] is True
    assert result["sources"][1]["mode"] == "no_registered_handler"
    assert result["sources"][1]["catalog_decision"]["allowed"] is True


def test_run_dispatches_only_explicit_source_ids_and_records_probe(catalog):
    calls = []

    def nc_handler(context):
        calls.append(context.source_id)
        return ok_observation()

    def ma_handler(context):
        calls.append(context.source_id)
        return ok_observation()

    handlers = {
        NC_SOURCE: handler_spec(NC_SOURCE, nc_handler),
        MA_SOURCE: handler_spec(MA_SOURCE, ma_handler),
    }
    result = run_sources(catalog, [NC_SOURCE], handlers=handlers)

    assert calls == [NC_SOURCE]
    assert result["requested_source_ids"] == [NC_SOURCE]
    assert result["results"][0]["dispatched"] is True
    assert result["results"][0]["recorded"] is True
    assert catalog.probe_history(NC_SOURCE)[0]["status"] == "ok"
    assert catalog.probe_history(MA_SOURCE) == []


def test_catalog_barrier_is_not_dispatched_and_never_becomes_no_results(catalog):
    calls = []

    def forbidden_handler(_context):
        calls.append("called")
        return ok_observation(status="no_results")

    handlers = {
        BLOCKED_SOURCE: handler_spec(BLOCKED_SOURCE, forbidden_handler)
    }
    result = run_sources(catalog, [BLOCKED_SOURCE], handlers=handlers)
    item = result["results"][0]

    assert calls == []
    assert item["catalog_decision"]["allowed"] is False
    assert item["dispatched"] is False
    assert item["recorded"] is True
    assert item["probe"]["status"] == "human_required"
    assert item["probe"]["status"] != "no_results"
    assert item["probe"]["details"]["catalog_decision"]["access_class"] == "C"


def test_allowed_source_without_handler_is_transparent_and_not_false_probe(catalog):
    result = run_sources(catalog, [OTHER_SOURCE], handlers={})
    item = result["results"][0]

    assert item["catalog_decision"]["allowed"] is True
    assert item["dispatched"] is False
    assert item["recorded"] is False
    assert item["status"] == "error"
    assert catalog.probe_history(OTHER_SOURCE) == []


def test_handler_exception_records_failure_not_no_results(catalog):
    def broken_handler(_context):
        raise RuntimeError("fixture transport failure")

    result = run_sources(
        catalog,
        [NC_SOURCE],
        handlers={NC_SOURCE: handler_spec(NC_SOURCE, broken_handler)},
    )
    probe = result["results"][0]["probe"]

    assert probe["status"] == "unavailable"
    assert probe["status"] != "no_results"
    assert probe["error"] == "fixture transport failure"
    assert probe["result_count"] is None


def test_successful_authoritative_empty_probe_can_record_no_results(catalog):
    def empty_handler(_context):
        return ok_observation(status="no_results")

    result = run_sources(
        catalog,
        [NC_SOURCE],
        handlers={NC_SOURCE: handler_spec(NC_SOURCE, empty_handler)},
    )

    assert result["results"][0]["probe"]["status"] == "no_results"
    assert result["results"][0]["probe"]["error"] is None


def test_schema_artifact_and_status_drift_are_compared(catalog):
    observations = iter(
        [
            ok_observation(schema="1" * 64, artifact="a" * 64),
            ok_observation(schema="2" * 64, artifact="b" * 64, status="partial"),
        ]
    )

    def changing_handler(_context):
        return next(observations)

    handlers = {NC_SOURCE: handler_spec(NC_SOURCE, changing_handler)}
    first = run_sources(catalog, [NC_SOURCE], handlers=handlers)
    second = run_sources(catalog, [NC_SOURCE], handlers=handlers)

    assert first["results"][0]["drift"]["baseline"] is True
    drift = second["results"][0]["drift"]
    assert drift["drift_detected"] is True
    assert drift["changes"]["status"]["changed"] is True
    assert drift["changes"]["schema_sha256"]["changed"] is True
    assert drift["changes"]["artifact_sha256"]["changed"] is True


def test_history_returns_every_catalog_probe_without_monitor_cap(catalog):
    for index in range(25):
        catalog.record_probe(
            NC_SOURCE,
            status="ok",
            probed_by="test",
            probed_at=f"2026-07-28T12:{index:02d}:00Z",
            schema_sha256=f"{index:064x}",
        )
    result = history(catalog, NC_SOURCE)

    assert len(result["probes"]) == 25
    assert result["probes"][0]["probe_id"] > result["probes"][-1]["probe_id"]


def test_diff_can_compare_exact_probe_ids(catalog):
    first = catalog.record_probe(
        NC_SOURCE,
        status="ok",
        probed_by="test",
        probed_at="2026-07-28T12:00:00Z",
        schema_sha256="1" * 64,
    )
    second = catalog.record_probe(
        NC_SOURCE,
        status="ok",
        probed_by="test",
        probed_at="2026-07-28T12:01:00Z",
        schema_sha256="2" * 64,
    )

    result = diff_history(
        catalog,
        NC_SOURCE,
        from_probe_id=first["probe_id"],
        to_probe_id=second["probe_id"],
    )

    assert result["comparison"]["previous_probe_id"] == first["probe_id"]
    assert result["comparison"]["current_probe_id"] == second["probe_id"]
    assert result["comparison"]["drift_detected"] is True


def test_manual_record_uses_catalog_history_and_returns_decision(catalog):
    result = record_observation(
        catalog,
        NC_SOURCE,
        ok_observation(schema="f" * 64),
        probed_by="test:manual",
        probed_at=NOW,
    )

    assert result["catalog_decision"]["allowed"] is True
    assert result["probe"]["probed_by"] == "test:manual"
    assert result["drift"]["baseline"] is True


def test_compare_probes_handles_first_observation():
    comparison = compare_probes(
        None,
        {"probe_id": 1, "status": "ok", "schema_sha256": "1" * 64},
    )
    assert comparison == {
        "baseline": True,
        "drift_detected": False,
        "previous_probe_id": None,
        "current_probe_id": 1,
        "changes": {},
    }


def test_no_results_observation_rejects_embedded_error():
    with pytest.raises(ValueError, match="cannot contain an error"):
        ProbeObservation(status="no_results", error="transport failed")


def test_catalog_probe_history_rejects_foreign_probe_ids(catalog):
    other = catalog.record_probe(
        MA_SOURCE,
        status="ok",
        probed_by="test",
    )

    with pytest.raises(CatalogError):
        diff_history(
            catalog,
            NC_SOURCE,
            from_probe_id=other["probe_id"],
            to_probe_id=other["probe_id"] + 1,
        )
