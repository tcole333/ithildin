from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_washington_taxsifter as taxsifter
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
SOURCE_IDS = (
    taxsifter.UMBRELLA_SOURCE_ID,
    *(tenant.source_id for tenant in taxsifter.TENANTS),
)
SHARED_OPERATIONS = {
    "account",
    "address",
    "discovery",
    "owner",
    "parcel",
    "probe",
    "sale",
    "search",
}


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _snapshot(tenant: Any, marker: int) -> dict[str, Any]:
    if tenant.key == "mason":
        operation_states = {
            "search": {
                "status": "human_required",
                "response_state": "challenge",
                "accessible": False,
                "observation": {
                    "error_code": "source_challenge_required",
                    "marker": marker,
                },
            },
            **{
                operation.value: {
                    "status": "not_probed_after_search_failure",
                    "response_state": None,
                    "accessible": None,
                    "observation": {
                        "upstream_status": "human_required",
                        "marker": marker,
                    },
                }
                for operation in taxsifter.Operation
                if operation != taxsifter.Operation.SEARCH
            },
        }
        return {
            "source_id": tenant.source_id,
            "county": tenant.key,
            "county_geoid": tenant.county_geoid,
            "status": "human_required",
            "endpoint": tenant.portal_root,
            "operation_states": operation_states,
            "request_count": 1,
            "warnings": list(tenant.notes),
            "error": "TaxSifter operation presented an interactive challenge",
        }

    operation_states = {}
    for operation in taxsifter.Operation:
        no_results = (
            operation == taxsifter.Operation.SALES
            and tenant.key in {"lincoln", "pacific"}
        )
        operation_states[operation.value] = {
            "status": "no_results" if no_results else "ok",
            "response_state": "no_result" if no_results else "live",
            "accessible": True,
            "observation": {
                "source_url": tenant.portal_root,
                "returned_count": 0 if no_results else marker,
                "published_result_count": 0 if no_results else marker,
                "marker": marker,
            },
        }
    return {
        "source_id": tenant.source_id,
        "county": tenant.key,
        "county_geoid": tenant.county_geoid,
        "status": "ok",
        "endpoint": tenant.portal_root,
        "operation_states": operation_states,
        "request_count": 6,
        "warnings": list(tenant.notes),
        "error": None,
    }


def test_monitor_keeps_tenant_activity_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = 1

    def fake_snapshot(_context: ProbeContext, tenant: Any) -> dict[str, Any]:
        return _snapshot(tenant, marker)

    monkeypatch.setattr(
        public_records_monitor,
        "_washington_taxsifter_tenant_snapshot",
        fake_snapshot,
    )
    source_id = taxsifter.TENANTS_BY_KEY["adams"].source_id
    first = public_records_monitor.probe_washington_taxsifter(
        _context(source_id)
    )
    marker = 2
    second = public_records_monitor.probe_washington_taxsifter(
        _context(source_id)
    )

    assert first.status == "ok"
    assert first.result_count == 5
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["schema_contract"] == second.details["schema_contract"]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]

    comparison = compare_probes(
        {
            "probe_id": 1,
            "status": first.status,
            "schema_sha256": first.schema_sha256,
            "artifact_sha256": first.artifact_sha256,
        },
        {
            "probe_id": 2,
            "status": second.status,
            "schema_sha256": second.schema_sha256,
            "artifact_sha256": second.artifact_sha256,
        },
    )
    assert comparison["drift_detected"] is False


def test_family_monitor_preserves_every_tenant_operation_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        public_records_monitor,
        "_washington_taxsifter_tenant_snapshot",
        lambda _context, tenant: _snapshot(tenant, 1),
    )

    observation = public_records_monitor.probe_washington_taxsifter(
        _context(taxsifter.UMBRELLA_SOURCE_ID)
    )

    assert observation.status == "partial"
    assert observation.result_count == 50
    assert observation.error is None
    rolling = observation.details["rolling_observation"]
    snapshots = rolling["tenant_operation_states"]
    assert len(snapshots) == 11
    assert all(len(snapshot["operation_states"]) == 5 for snapshot in snapshots)

    by_county = {snapshot["county"]: snapshot for snapshot in snapshots}
    assert by_county["mason"]["status"] == "human_required"
    assert by_county["mason"]["operation_states"]["search"] == {
        "status": "human_required",
        "response_state": "challenge",
        "accessible": False,
        "observation": {
            "error_code": "source_challenge_required",
            "marker": 1,
        },
    }
    assert by_county["lincoln"]["operation_states"]["sales"][
        "status"
    ] == "no_results"
    assert by_county["lincoln"]["operation_states"]["sales"][
        "accessible"
    ] is True
    interpretation = observation.details["stable_contract"]["interpretation"]
    assert interpretation["operation_state_scope"] == "tenant_and_operation"
    assert interpretation["no_results_meaning"] == (
        "accessible_authoritative_empty_response"
    )


def test_leaf_monitor_retains_mason_challenge_without_family_reclassification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        public_records_monitor,
        "_washington_taxsifter_tenant_snapshot",
        lambda _context, tenant: _snapshot(tenant, 1),
    )
    mason = taxsifter.TENANTS_BY_KEY["mason"]

    observation = public_records_monitor.probe_washington_taxsifter(
        _context(mason.source_id)
    )

    assert observation.status == "human_required"
    assert observation.result_count == 0
    assert "interactive challenge" in str(observation.error)
    assert observation.details["rolling_observation"][
        "tenant_operation_states"
    ][0]["county"] == "mason"


def test_catalog_promotes_umbrella_and_all_leaves_without_catalog_limits(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    for source_id in SOURCE_IDS:
        decision = catalog.require_machine_acquisition(source_id)
        assert decision["allowed"] is True
        assert decision["limits"] == {}
        manifest = catalog.show_source(source_id)["current_manifest"]
        capabilities = {
            capability["name"]: capability["details"]
            for capability in manifest["capabilities"]
        }
        assert set(
            capabilities["query_shared_property_records"][
                "shared_operations"
            ]
        ) == SHARED_OPERATIONS
        assert manifest["platform_family"] == taxsifter.PLATFORM_FAMILY

    umbrella = catalog.show_source(
        taxsifter.UMBRELLA_SOURCE_ID
    )["current_manifest"]
    assert umbrella["source_coverage"]["county_count"] == 11
    assert umbrella["source_coverage"]["live_verified_count"] == 10
    assert umbrella["source_coverage"]["challenge_observed_counties"] == [
        "Mason County"
    ]
    assert set(umbrella["tenant_operation_states"]) == {
        tenant.key for tenant in taxsifter.TENANTS
    }
    assert umbrella["publication_contract"][
        "authoritative_no_result_is_accessible"
    ] is True
    assert umbrella["publication_contract"][
        "published_result_count_and_returned_page_count_are_distinct"
    ] is True
    assert umbrella["publication_contract"][
        "sales_continuation_verified"
    ] is False

    for tenant in taxsifter.TENANTS:
        manifest = catalog.show_source(tenant.source_id)["current_manifest"]
        assert manifest["source_coverage"]["county_geoid"] == (
            tenant.county_geoid
        )
        assert manifest["identity_contract"]["account_occurrence"] == [
            "source_id",
            "key_id",
            "type_id",
        ]
        assert manifest["identity_contract"]["parcel_join"] == [
            "county_geoid",
            "parcel_number",
        ]
        aliases = manifest["endpoints"]["official_root_aliases"]
        assert tenant.portal_root in aliases
        assert all(
            any(host in alias for alias in aliases)
            for host in tenant.observed_hosts
        )
        assert (
            manifest["endpoints"]["official_data_link"]
            == tenant.observed_data_link
        )
        assert manifest["publication_contract"][
            "sales_pagination_state"
        ] == taxsifter.SALES_PAGINATION_STATE
        assert manifest["publication_contract"][
            "sales_continuation_verified"
        ] is False
        assert manifest["probe_evidence"]["access_state"] == tenant.access_state


def test_mason_catalog_keeps_assessor_recorder_and_treasurer_roles_distinct(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    mason = catalog.show_source(
        taxsifter.TENANTS_BY_KEY["mason"].source_id
    )["current_manifest"]

    assert set(mason["operation_access"].values()) == {"challenge_observed"}
    complements = {
        complement["kind"]: complement
        for complement in mason["official_complements"]
    }
    assert complements["mason_county_tax_parcels_gis"]["roles"] == [
        "parcel",
        "assessment",
        "owner",
        "situs",
        "legal",
        "geometry",
    ]
    assert complements["mason_county_auditor_eagleweb"]["lineage"] == (
        taxsifter.RECORDER_LINEAGE
    )
    assert complements["washington_digital_archives_recorded_land_title"][
        "title_id"
    ] == 56
    assert complements["washington_digital_archives_recorded_land_title"][
        "lineage"
    ] == taxsifter.RECORDER_LINEAGE
    assert all(
        "treasurer" not in {
            str(role).casefold()
            for role in complement.get("roles", [])
        }
        for complement in complements.values()
    )

    monitor_complements = {
        complement["kind"]: complement
        for complement in (
            public_records_monitor._washington_taxsifter_official_complements(
                taxsifter.TENANTS_BY_KEY["mason"]
            )
        )
    }
    assert monitor_complements["mason_county_tax_parcels_gis"]["roles"] == [
        "parcel",
        "assessment",
        "owner",
        "situs",
        "legal",
        "geometry",
    ]
    assert monitor_complements["mason_county_auditor_eagleweb"][
        "lineage_id"
    ] == taxsifter.RECORDER_LINEAGE


def test_census_monitor_registry_catalog_audit_docs_and_citations(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    census = PublicRecordsCensus(catalog_path)
    audit = audit_catalog(db_path=catalog_path)

    mismatches = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert not (set(SOURCE_IDS) & mismatches)

    assessment_target = census.list_targets(
        state="WA",
        domain="property",
        role="assessment_roll",
    )[0]
    tax_target = census.list_targets(
        state="WA",
        domain="property",
        role="tax_collection",
    )[0]
    assert taxsifter.UMBRELLA_SOURCE_ID in assessment_target["source_ids"]
    assert taxsifter.UMBRELLA_SOURCE_ID in tax_target["source_ids"]

    family_handler = public_records_monitor.HANDLER_REGISTRY[
        taxsifter.UMBRELLA_SOURCE_ID
    ]
    assert family_handler.handler is (
        public_records_monitor.probe_washington_taxsifter
    )
    assert family_handler.expected_requests == 66
    assert family_handler.sentinel_record_count == 11
    for tenant in taxsifter.TENANTS:
        handler = public_records_monitor.HANDLER_REGISTRY[tenant.source_id]
        assert handler.handler is (
            public_records_monitor.probe_washington_taxsifter
        )
        assert handler.endpoint == tenant.portal_root
        assert handler.expected_requests == 6

    source_urls = json.loads(
        (
            ROOT / "web" / "src" / "data" / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[
        f"PROPERTY_SOURCE:{taxsifter.UMBRELLA_SOURCE_ID}"
    ].endswith("/FeatureServer/0")
    for tenant in taxsifter.TENANTS:
        assert source_urls[
            f"PROPERTY_SOURCE:{tenant.source_id}"
        ] == tenant.portal_root

    property_docs = (
        ROOT / "docs" / "modules" / "property.md"
    ).read_text(encoding="utf-8")
    tool_reference = (
        ROOT / "docs" / "TOOL_REFERENCE.md"
    ).read_text(encoding="utf-8")
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    for content in (property_docs, tool_reference, roadmap):
        assert taxsifter.UMBRELLA_SOURCE_ID in content
        assert "tenant-by-operation" in content
    for tenant in taxsifter.TENANTS:
        assert tenant.source_id in property_docs
    assert "authoritative empty sales response" in property_docs
    assert "does not invent sales paging" in property_docs
    assert "TaxParcels GIS" in roadmap
    assert "EagleWeb" in roadmap
    assert "Treasurer account" in roadmap


@pytest.mark.live_data
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for the official source probe",
)
def test_live_adams_monitor_preserves_all_five_operation_states() -> None:
    adams = taxsifter.TENANTS_BY_KEY["adams"]
    observation = public_records_monitor.probe_washington_taxsifter(
        _context(adams.source_id)
    )

    assert observation.status == "ok"
    snapshot = observation.details["rolling_observation"][
        "tenant_operation_states"
    ][0]
    assert snapshot["source_id"] == adams.source_id
    assert set(snapshot["operation_states"]) == {
        operation.value for operation in taxsifter.Operation
    }
    assert all(
        state["status"] in {"ok", "no_results"}
        for state in snapshot["operation_states"].values()
    )
