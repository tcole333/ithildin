from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_mason_county_tax_parcels as mason
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=mason.SOURCE_ID,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _contract() -> mason.LayerContract:
    return mason.LayerContract(
        schema_fingerprint="a" * 64,
        field_names=mason.REQUIRED_FIELDS,
        max_record_count=1_000,
        object_id_field="FID",
        geometry_type=mason.GEOMETRY_TYPE,
        spatial_reference={"wkid": 102749, "latestWkid": 2286},
        supports_pagination=False,
        supports_order_by=False,
        supports_statistics=False,
        supports_advanced_queries=False,
    )


def _batch(marker: int) -> mason.FeatureBatch:
    return mason.FeatureBatch(
        features=(
            {
                "attributes": {
                    "FID": 0,
                    "PIN": "219010090013",
                    "TERRA_PIN": "21901-00-90013",
                    "Taxlot": "0090013",
                    "Assessment": f"REAL PROPERTY {marker}",
                    "TotalMarke": 425_000 + marker,
                    "TotalAsses": 410_000 + marker,
                    "Situs": f"{100 + marker} TEST RD",
                }
            },
        ),
        contract=_contract(),
        matching_object_ids=(0, 1, 2),
        ids_fingerprint=sha256_fingerprint([0, 1, 2]),
        next_cursor=("mason-tax-parcels:v1:fixture" if marker else None),
        requests_made=3,
    )


def test_monitor_keeps_current_values_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = 1

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

    def fake_fetch(*_args: Any, **_kwargs: Any) -> mason.FeatureBatch:
        return _batch(marker)

    monkeypatch.setattr(mason, "MasonCountyTaxParcelsClient", FakeClient)
    monkeypatch.setattr(mason, "fetch_feature_batch", fake_fetch)
    first = public_records_monitor.probe_mason_county_tax_parcels(_context())
    marker = 2
    second = public_records_monitor.probe_mason_county_tax_parcels(_context())

    assert first.status == "ok"
    assert first.result_count == 3
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["schema_contract"] == second.details["schema_contract"]
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["requests_made"] == 3
    assert first.details["rolling_observation"]["smallest_object_id"] == 0
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.details["stable_contract"]["traversal"] == {
        "id_snapshot": "returnIdsOnly",
        "stable_order": "client_sorted_FID_ascending",
        "feature_fetch": "objectIds_batches",
        "offset_pagination_used": False,
        "server_order_by_used": False,
    }

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


def test_catalog_census_monitor_and_shared_operation_lifecycle(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    decision = catalog.require_machine_acquisition(mason.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["limits"] == {}
    detail = catalog.show_source(mason.SOURCE_ID)
    manifest = detail["current_manifest"]

    assert manifest["jurisdiction_geoids"] == ["53045"]
    assert set(manifest["roles"]) == {
        "assessment_roll",
        "parcel_geometry",
        "assessor_name_index",
        "situs_address",
        "mailing_address",
        "assessed_and_market_values",
        "parcel_identifier_index",
    }
    identity = manifest["identity_contract"]
    assert identity["source_occurrence"] == ["FID"]
    assert identity["candidate_parcel_join_precedence"] == [
        "PIN",
        "TERRA_PIN",
        "Taxlot",
    ]
    assert identity["candidate_parcel_join_uniqueness_assumed"] is False
    transport = manifest["transport_contract"]
    assert transport["supports_pagination"] is False
    assert transport["supports_order_by"] is False
    assert transport["id_snapshot_operation"] == "returnIdsOnly"
    assert transport["feature_fetch"] == (
        "objectIds_batches_at_published_service_ceiling"
    )

    publication = manifest["publication_contract"]
    assert publication["recorder_instrument_index"] is False
    assert publication["treasury_balance_or_payment_history"] is False
    assert publication["recorded_title_conclusion"] is False
    assert publication["surveyed_legal_boundary"] is False

    evidence = manifest["probe_evidence"]
    assert (
        evidence["parameterized_feature_response_observed_during_implementation"]
        is True
    )
    assert evidence["query_probe_transport"] == "official_arcgis_get_form"
    assert evidence["rolling_feature_count_observed"] == 60_522
    assert evidence["rolling_fid_range_observed"] == [0, 60_521]
    assert evidence["verified_sentinel"] == {
        "FID": 0,
        "PIN": "219010090013",
        "Taxlot": "0090013",
        "TERRA_PIN": "21901-00-90013",
    }

    associations = {
        association["role"]: association
        for association in manifest["census_associations"]
    }
    assert set(associations) == {"assessment_roll", "parcel_geometry"}
    assert all(
        association["jurisdiction_geoid"] == "53045"
        for association in associations.values()
    )
    for role in ("assessment_roll", "parcel_geometry"):
        targets = census.list_targets(
            state="WA",
            domain="property",
            role=role,
        )
        assert any(mason.SOURCE_ID in target["source_ids"] for target in targets)

    complements = {
        complement["kind"]: complement
        for complement in manifest["official_complements"]
    }
    assert set(complements) == {
        "challenged_interactive_assessor_and_treasurer_portal",
        "county_auditor_instrument_index",
        "archived_county_auditor_instrument_index",
        "normalized_statewide_current_parcels",
    }
    assert complements["county_auditor_instrument_index"]["adds"] == [
        "grantor",
        "grantee",
        "instrument",
        "recording_date",
        "legal_description",
    ]
    assert (
        complements["normalized_statewide_current_parcels"]["relationship"]
        == "same_county_assessor_origin_not_independent_corroboration"
    )

    audit = audit_catalog(db_path=catalog_path)
    mismatches = {
        item["source_id"] for item in audit["shared_adapter_operation_mismatches"]
    }
    assert mason.SOURCE_ID not in mismatches

    handler = public_records_monitor.HANDLER_REGISTRY[mason.SOURCE_ID]
    assert handler.handler is (public_records_monitor.probe_mason_county_tax_parcels)
    assert handler.expected_requests == 3
    assert handler.sentinel_record_count == 1
    assert handler.sample_bytes is None


def test_docs_citations_and_iteration_learning_capture_verified_contract() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"PROPERTY_SOURCE:{mason.SOURCE_ID}"] == mason.LAYER_URL

    property_docs = (ROOT / "docs" / "modules" / "property.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md").read_text(
        encoding="utf-8"
    )
    for content in (property_docs, tool_reference, roadmap):
        assert mason.SOURCE_ID in content
        assert "FID=0" in content
        assert "Mason" in content
    for content in (property_docs, tool_reference):
        assert "60,522" in content
        assert "21901-00-90013" in content
        assert "rolling" in content
    assert "published capability flags select the traversal family" in roadmap
    assert "Preserve source features that lack a business join key" in roadmap
