from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from tools.public_records_catalog import (
    ACCESS_CLASSES,
    AUTOMATION_DISPOSITIONS,
    CatalogError,
    ManifestValidationError,
    PublicRecordsCatalog,
    acquisition_result_status,
    canonical_source_id,
    main,
    validate_source_manifest,
)


NOW = "2026-07-28T12:00:00Z"


@pytest.fixture
def source_manifest() -> dict:
    return {
        "source_id": "us-fl-dor-property-roll",
        "name": "Florida DOR Property Roll",
        "domain": "property",
        "roles": ["assessment", "parcel_geometry", "sales"],
        "authority": "Florida Department of Revenue",
        "operator": "Florida Department of Revenue",
        "jurisdiction_geoids": ["12"],
        "official_url": (
            "https://www.floridarevenue.com/property/Pages/"
            "DataPortal_RequestAssessmentRollGISData.aspx"
        ),
        "platform_family": "official_bulk",
        "access_class": "A",
        "automation_disposition": "allowed_with_limits",
        "authentication": "none",
        "fees": "none",
        "license_or_terms_url": None,
        "redistribution": "review_required",
        "protected_record_policy": "source_redactions_preserved",
        "coverage_start": "source_specific",
        "update_cadence": "annual",
        "stable_keys": ["county_fips", "native_parcel_id", "roll_year"],
        "adapter_family": "bulk_property_roll",
        "adapter_version": 1,
        "last_verified_at": NOW,
        "health_status": "candidate",
        "capabilities": [
            "probe",
            {
                "name": "sync",
                "supported": True,
                "details": {"incremental": False},
            },
            {"name": "fetch_document", "supported": False, "details": {}},
        ],
    }


@pytest.fixture
def catalog(tmp_path: Path) -> PublicRecordsCatalog:
    return PublicRecordsCatalog(tmp_path / "public_records_catalog.db")


def register(
    catalog: PublicRecordsCatalog,
    manifest: dict,
    *,
    submitted_at: str = NOW,
) -> dict:
    return catalog.register_manifest(
        manifest,
        submitted_by="test:reviewer",
        submitted_at=submitted_at,
    )


def test_initializes_expected_control_plane_schema(
    catalog: PublicRecordsCatalog,
) -> None:
    db = sqlite3.connect(catalog.db_path)
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    schema_version = db.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()[0]
    db.close()

    assert {
        "jurisdictions",
        "sources",
        "source_manifests",
        "source_jurisdictions",
        "source_roles",
        "capabilities",
        "access_reviews",
        "terms_snapshots",
        "probes",
        "source_census_targets",
        "source_census_target_sources",
        "source_census_events",
    }.issubset(tables)
    assert schema_version == "3"


def test_canonical_source_ids_are_normalized_but_manifests_must_use_them(
    source_manifest: dict,
) -> None:
    assert (
        canonical_source_id(" US FL DOR Property Roll ")
        == "us-fl-dor-property-roll"
    )

    noncanonical = copy.deepcopy(source_manifest)
    noncanonical["source_id"] = "US-FL-DOR Property Roll"
    with pytest.raises(ManifestValidationError, match="already be canonical"):
        validate_source_manifest(noncanonical)

    with pytest.raises(ManifestValidationError, match="country prefix"):
        canonical_source_id("property-roll")


@pytest.mark.parametrize("missing", ["roles", "stable_keys", "official_url"])
def test_manifest_validation_rejects_missing_required_fields(
    source_manifest: dict,
    missing: str,
) -> None:
    source_manifest.pop(missing)
    with pytest.raises(ManifestValidationError, match=missing):
        validate_source_manifest(source_manifest)


def test_manifest_validation_rejects_invalid_access_and_urls(
    source_manifest: dict,
) -> None:
    source_manifest["access_class"] = "Z"
    with pytest.raises(ManifestValidationError, match="access_class"):
        validate_source_manifest(source_manifest)

    source_manifest["access_class"] = "A"
    source_manifest["automation_disposition"] = "probably"
    with pytest.raises(
        ManifestValidationError, match="automation_disposition"
    ):
        validate_source_manifest(source_manifest)

    source_manifest["automation_disposition"] = "allowed"
    source_manifest["official_url"] = "javascript:alert(1)"
    with pytest.raises(ManifestValidationError, match=r"HTTP\(S\)"):
        validate_source_manifest(source_manifest)


def test_register_preserves_manifest_and_requires_separate_access_review(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    registered = register(catalog, source_manifest)
    detail = catalog.show_source(source_manifest["source_id"])

    assert registered["access_review_required"] is True
    assert len(registered["manifest_sha256"]) == 64
    assert detail["source"]["proposed_access_class"] == "A"
    assert (
        detail["source"]["proposed_automation_disposition"]
        == "allowed_with_limits"
    )
    assert detail["latest_access_review"] is None
    assert detail["roles"] == ["assessment", "parcel_geometry", "sales"]
    assert detail["jurisdictions"][0]["geoid"] == "12"
    assert detail["jurisdictions"][0]["jurisdiction_id"] == "us-geoid-12"
    assert detail["capabilities"] == [
        {
            "name": "fetch_document",
            "supported": False,
            "details": {},
            "recorded_at": detail["capabilities"][0]["recorded_at"],
        },
        {
            "name": "probe",
            "supported": True,
            "details": {},
            "recorded_at": detail["capabilities"][1]["recorded_at"],
        },
        {
            "name": "sync",
            "supported": True,
            "details": {"incremental": False},
            "recorded_at": detail["capabilities"][2]["recorded_at"],
        },
    ]

    decision = catalog.machine_acquisition_decision(
        source_manifest["source_id"],
        as_of=NOW,
    )
    assert decision["allowed"] is False
    assert decision["reason_code"] == "access_review_required"
    assert acquisition_result_status(decision) == "unavailable"


def test_register_supports_explicit_jurisdictions_and_list_filters(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    manifest = copy.deepcopy(source_manifest)
    manifest.update(
        {
            "source_id": "us-ny-courts-nyscef",
            "name": "NYSCEF",
            "domain": "court",
            "roles": ["clerk", "court"],
            "authority": "New York State Unified Court System",
            "operator": "New York State Unified Court System",
            "jurisdictions": [
                {
                    "jurisdiction_id": "us-ny",
                    "name": "New York",
                    "kind": "state",
                    "country_code": "US",
                    "subdivision_code": "NY",
                    "geoid": "36",
                    "coverage": {"courts": ["supreme"]},
                    "exclusions": ["sealed"],
                }
            ],
            "platform_family": "official_browser_portal",
            "access_class": "C",
            "automation_disposition": "unclear",
            "stable_keys": ["court_id", "case_number"],
            "adapter_family": "browser_court",
        }
    )
    manifest.pop("jurisdiction_geoids")
    register(catalog, manifest)
    catalog.evaluate_access(
        manifest["source_id"],
        access_class="C",
        automation_disposition="unclear",
        reviewed_by="human:legal",
        review_basis="Official terms restrict bot extraction.",
        reviewed_at=NOW,
    )

    assert [
        row["source_id"]
        for row in catalog.list_sources(domain="court", jurisdiction="36")
    ] == [manifest["source_id"]]
    assert [
        row["source_id"]
        for row in catalog.list_sources(
            access_class="C", automation_disposition="unclear"
        )
    ] == [manifest["source_id"]]
    assert catalog.list_sources(domain="property") == []


def test_explicit_jurisdiction_and_matching_geoid_shorthand_do_not_duplicate(
    source_manifest: dict,
) -> None:
    source_manifest["jurisdictions"] = [
        {
            "jurisdiction_id": "us-fl",
            "name": "Florida",
            "kind": "state",
            "country_code": "US",
            "geoid": "12",
        }
    ]
    normalized = validate_source_manifest(source_manifest)

    assert [item["jurisdiction_id"] for item in normalized["jurisdictions"]] == [
        "us-fl"
    ]


def test_list_sources_matches_state_and_local_geoid_hierarchy(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    county_manifest = copy.deepcopy(source_manifest)
    county_manifest.update(
        {
            "source_id": "us-ny-new-york-county-recorder",
            "name": "New York County Recorder",
            "jurisdiction_geoids": ["36061"],
        }
    )
    register(catalog, county_manifest)

    assert [
        row["source_id"]
        for row in catalog.list_sources(domain="property", jurisdiction="36")
    ] == [county_manifest["source_id"]]
    assert [
        row["source_id"]
        for row in catalog.list_sources(domain="property", jurisdiction="36061")
    ] == [county_manifest["source_id"]]


def test_manifest_history_is_append_only_and_duplicate_hash_is_idempotent(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    first = register(catalog, source_manifest)
    duplicate = register(catalog, source_manifest)
    changed = copy.deepcopy(source_manifest)
    changed["update_cadence"] = "annual_preliminary_and_final"
    second = register(
        catalog,
        changed,
        submitted_at="2026-07-29T12:00:00Z",
    )

    detail = catalog.show_source(source_manifest["source_id"])
    assert duplicate["manifest_id"] == first["manifest_id"]
    assert second["manifest_id"] != first["manifest_id"]
    assert len(detail["manifest_history"]) == 2
    assert detail["manifest_history"][0]["submitted_at"] == (
        "2026-07-29T12:00:00Z"
    )
    assert detail["current_manifest"]["update_cadence"] == (
        "annual_preliminary_and_final"
    )


def test_terms_snapshots_preserve_capture_and_review_provenance(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    text = "Automated access is permitted at no more than one request per second."
    snapshot = catalog.record_terms_snapshot(
        source_manifest["source_id"],
        snapshot_type="terms",
        source_url="https://example.gov/terms",
        captured_at="2026-07-01T09:30:00-04:00",
        recorded_by="human:legal",
        content_text=text,
        artifact_ref="sha256/terms.txt",
        notes="Official terms page.",
    )
    review = catalog.evaluate_access(
        source_manifest["source_id"],
        access_class="B",
        automation_disposition="allowed_with_limits",
        limits={"requests_per_second": 1, "bulk": False},
        reviewed_by="human:legal",
        reviewed_at="2026-07-02T10:00:00-04:00",
        review_basis="Official terms snapshot.",
        terms_snapshot_id=snapshot["terms_snapshot_id"],
    )
    detail = catalog.show_source(source_manifest["source_id"])

    assert snapshot["captured_at"] == "2026-07-01T13:30:00Z"
    assert snapshot["content_sha256"] == hashlib.sha256(
        text.encode()
    ).hexdigest()
    assert review["reviewed_at"] == "2026-07-02T14:00:00Z"
    assert detail["terms_snapshots"][0]["captured_at"] == (
        "2026-07-01T13:30:00Z"
    )
    assert detail["terms_snapshots"][0]["recorded_by"] == "human:legal"
    assert detail["latest_access_review"]["terms_snapshot_id"] == (
        snapshot["terms_snapshot_id"]
    )


def test_terms_snapshot_rejects_mismatched_content_hash(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    with pytest.raises(CatalogError, match="does not match"):
        catalog.record_terms_snapshot(
            source_manifest["source_id"],
            snapshot_type="terms",
            source_url="https://example.gov/terms",
            captured_at=NOW,
            recorded_by="human:legal",
            content_text="actual",
            content_sha256="0" * 64,
        )


def test_terms_artifact_reference_requires_real_content_hash(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    with pytest.raises(CatalogError, match="actual content_sha256"):
        catalog.record_terms_snapshot(
            source_manifest["source_id"],
            snapshot_type="terms",
            source_url="https://example.gov/terms",
            captured_at=NOW,
            recorded_by="human:legal",
            artifact_ref="/evidence/terms.html",
        )


def test_class_a_allowed_review_is_the_single_catalog_decision(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    catalog.evaluate_access(
        source_manifest["source_id"],
        access_class="A",
        automation_disposition="allowed",
        reviewed_by="human:legal",
        review_basis="Official bulk download license.",
        reviewed_at=NOW,
    )

    allowed = catalog.assert_machine_acquisition_allowed(
        source_manifest["source_id"],
        as_of=NOW,
    )
    assert allowed["allowed"] is True
    assert allowed["access_class"] == "A"
    assert acquisition_result_status(allowed) == "ok"


def test_allowed_with_limits_requires_and_returns_limits_contract(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    with pytest.raises(CatalogError, match="non-empty limits"):
        catalog.evaluate_access(
            source_manifest["source_id"],
            access_class="B",
            automation_disposition="allowed_with_limits",
            reviewed_by="human:legal",
            review_basis="Official rate policy.",
            reviewed_at=NOW,
        )

    limits = {"requests_per_second": 0.5, "maximum_page_size": 1000}
    catalog.evaluate_access(
        source_manifest["source_id"],
        access_class="B",
        automation_disposition="allowed_with_limits",
        limits=limits,
        reviewed_by="human:legal",
        review_basis="Official rate policy.",
        reviewed_at=NOW,
    )
    decision = catalog.require_machine_acquisition(
        source_manifest["source_id"],
        as_of=NOW,
    )
    assert decision["allowed"] is True
    assert decision["limits"] == limits


@pytest.mark.parametrize(
    ("access_class", "disposition", "reason_code", "result_status"),
    [
        ("B", "prohibited", "automation_not_approved", "terms_blocked"),
        ("C", "unclear", "automation_not_approved", "human_required"),
        ("E", "not_applicable", "automation_not_approved", "human_required"),
        ("X", "prohibited", "no_acquisition_route", "terms_blocked"),
    ],
)
def test_non_machine_acquisition_modes_are_reported_precisely(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
    access_class: str,
    disposition: str,
    reason_code: str,
    result_status: str,
) -> None:
    register(catalog, source_manifest)
    catalog.evaluate_access(
        source_manifest["source_id"],
        access_class=access_class,
        automation_disposition=disposition,
        reviewed_by="human:legal",
        review_basis="Reviewed official access policy.",
        reviewed_at=NOW,
    )

    decision = catalog.machine_acquisition_decision(
        source_manifest["source_id"],
        as_of=NOW,
    )
    assert decision["allowed"] is False
    assert decision["reason_code"] == reason_code
    assert acquisition_result_status(decision) == result_status


@pytest.mark.parametrize("access_class", ["C", "E"])
def test_reviewed_disposition_can_expose_machine_route_independently_of_class(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
    access_class: str,
) -> None:
    register(catalog, source_manifest)
    catalog.evaluate_access(
        source_manifest["source_id"],
        access_class=access_class,
        automation_disposition="allowed",
        reviewed_by="human:legal",
        review_basis="A current structured route was verified.",
        reviewed_at=NOW,
    )

    decision = catalog.machine_acquisition_decision(
        source_manifest["source_id"],
        as_of=NOW,
    )
    assert decision["allowed"] is True
    assert decision["access_class"] == access_class
    assert acquisition_result_status(decision) == "ok"


def test_class_d_uses_verified_license_state_from_catalog_review(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    catalog.evaluate_access(
        source_manifest["source_id"],
        access_class="D",
        automation_disposition="allowed",
        reviewed_by="human:procurement",
        review_basis="Vendor API is technically suitable.",
        reviewed_at=NOW,
    )
    decision = catalog.machine_acquisition_decision(
        source_manifest["source_id"],
        as_of=NOW,
    )
    assert decision["reason_code"] == "licensed_contract_required"
    assert acquisition_result_status(decision) == "restricted"

    catalog.evaluate_access(
        source_manifest["source_id"],
        access_class="D",
        automation_disposition="allowed",
        reviewed_by="human:procurement",
        review_basis="Executed data license verified.",
        reviewed_at="2026-07-29T12:00:00Z",
        contract_verified=True,
        contract_reference="PROCUREMENT-2026-17",
    )
    assert catalog.require_machine_acquisition(
        source_manifest["source_id"],
        as_of="2026-07-29T13:00:00Z",
    )["allowed"]


def test_expired_access_review_blocks_machine_acquisition(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    catalog.evaluate_access(
        source_manifest["source_id"],
        access_class="A",
        automation_disposition="allowed",
        reviewed_by="human:legal",
        review_basis="Time-bounded pilot.",
        reviewed_at=NOW,
        valid_until="2026-07-29T12:00:00Z",
    )
    decision = catalog.machine_acquisition_decision(
        source_manifest["source_id"],
        as_of="2026-07-30T12:00:00Z",
    )
    assert decision["allowed"] is False
    assert decision["reason_code"] == "access_review_expired"


def test_access_taxonomies_are_complete() -> None:
    assert ACCESS_CLASSES == {"A", "B", "C", "D", "E", "X"}
    assert AUTOMATION_DISPOSITIONS == {
        "allowed",
        "allowed_with_limits",
        "unclear",
        "prohibited",
        "not_applicable",
    }


def test_probe_health_distinguishes_true_zero_degradation_and_restriction(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    assert catalog.health(
        source_manifest["source_id"], as_of=NOW
    )[0]["health"] == "unknown"

    first = catalog.record_probe(
        source_manifest["source_id"],
        status="no_results",
        result_count=0,
        endpoint="https://example.gov/api?q=sentinel",
        http_status=200,
        latency_ms=125,
        probed_by="agent:sentinel",
        probed_at=NOW,
        details={"fixture": "known-absent-selector"},
    )
    health = catalog.health(
        source_manifest["source_id"],
        max_age_hours=24,
        as_of="2026-07-28T13:00:00Z",
    )[0]
    assert health["health"] == "healthy"
    assert health["observed_status"] == "no_results"
    assert health["probe_id"] == first["probe_id"]

    catalog.record_probe(
        source_manifest["source_id"],
        status="partial",
        probed_by="agent:sentinel",
        probed_at="2026-07-28T14:00:00Z",
        details={"pages_completed": 1, "pages_expected": 2},
    )
    assert catalog.health(
        source_manifest["source_id"],
        as_of="2026-07-28T15:00:00Z",
    )[0]["health"] == "degraded"

    catalog.record_probe(
        source_manifest["source_id"],
        status="terms_blocked",
        probed_by="agent:sentinel",
        probed_at="2026-07-28T16:00:00Z",
        details={"policy": "automation prohibited"},
    )
    assert catalog.health(
        source_manifest["source_id"],
        as_of="2026-07-28T17:00:00Z",
    )[0]["health"] == "restricted"


def test_probe_history_accepts_websocket_transport_endpoints(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)

    probe = catalog.record_probe(
        source_manifest["source_id"],
        status="ok",
        endpoint="wss://records.example.gov/ws",
        result_count=1,
        probed_by="agent:sentinel",
        probed_at=NOW,
    )

    assert catalog.probe_history(
        source_manifest["source_id"],
        probe_ids=[probe["probe_id"]],
    )[0]["endpoint"] == "wss://records.example.gov/ws"
    assert catalog.health(
        source_manifest["source_id"],
        as_of="2026-07-28T13:00:00Z",
    )[0]["endpoint"] == "wss://records.example.gov/ws"


def test_probe_history_rejects_non_network_endpoint(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)

    with pytest.raises(CatalogError, match="WebSocket URL"):
        catalog.record_probe(
            source_manifest["source_id"],
            status="ok",
            endpoint="file:///tmp/probe.json",
            probed_by="agent:sentinel",
            probed_at=NOW,
        )


def test_probe_health_marks_old_latest_probe_stale(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    catalog.record_probe(
        source_manifest["source_id"],
        status="ok",
        probed_by="agent:sentinel",
        probed_at="2026-07-01T12:00:00Z",
    )
    health = catalog.health(
        source_manifest["source_id"],
        max_age_hours=24,
        as_of=NOW,
    )[0]
    assert health["health"] == "stale"
    assert health["observed_status"] == "ok"
    assert health["age_hours"] == 648


def test_error_probe_requires_error_message(
    catalog: PublicRecordsCatalog,
    source_manifest: dict,
) -> None:
    register(catalog, source_manifest)
    with pytest.raises(CatalogError, match="error message"):
        catalog.record_probe(
            source_manifest["source_id"],
            status="error",
            probed_by="agent:sentinel",
            probed_at=NOW,
        )


def test_cli_supports_db_override_and_json_workflow(
    tmp_path: Path,
    source_manifest: dict,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "cli-catalog.db"
    manifest_path = tmp_path / "source.json"
    manifest_path.write_text(json.dumps(source_manifest))

    assert main(
        [
            "--db",
            str(db_path),
            "--json",
            "register",
            str(manifest_path),
            "--submitted-by",
            "test:cli",
            "--submitted-at",
            NOW,
        ]
    ) == 0
    registered = json.loads(capsys.readouterr().out)
    assert registered["source_id"] == source_manifest["source_id"]
    assert registered["access_review_required"] is True

    assert main(
        [
            "evaluate-access",
            source_manifest["source_id"],
            "--access-class",
            "A",
            "--disposition",
            "allowed",
            "--reviewed-by",
            "human:legal",
            "--reviewed-at",
            NOW,
            "--basis",
            "Official bulk terms.",
            "--db",
            str(db_path),
            "--json",
        ]
    ) == 0
    review = json.loads(capsys.readouterr().out)
    assert review["automation_disposition"] == "allowed"

    assert main(
        [
            "record-probe",
            source_manifest["source_id"],
            "--status",
            "ok",
            "--probed-by",
            "test:cli",
            "--probed-at",
            NOW,
            "--result-count",
            "1",
            "--db",
            str(db_path),
            "--json",
        ]
    ) == 0
    probe = json.loads(capsys.readouterr().out)
    assert probe["status"] == "ok"

    assert main(
        [
            "health",
            source_manifest["source_id"],
            "--as-of",
            "2026-07-28T13:00:00Z",
            "--db",
            str(db_path),
            "--json",
        ]
    ) == 0
    health = json.loads(capsys.readouterr().out)
    assert health[0]["health"] == "healthy"


def test_cli_errors_are_structured_in_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(
        [
            "--db",
            str(tmp_path / "catalog.db"),
            "--json",
            "show",
            "us-fl-missing-source",
        ]
    ) == 2
    error = json.loads(capsys.readouterr().out)
    assert error["status"] == "error"
    assert "unknown source_id" in error["error"]
