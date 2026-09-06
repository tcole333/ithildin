from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_new_jersey_dca_property as dca
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _probe_record(
    *,
    building_id: str,
    property_interest_id: str,
    status: str,
    observed_total: int,
) -> dict[str, Any]:
    raw_source = {field: None for field in dca.REQUIRED_ODATA_FIELDS}
    raw_source.update(
        {
            "ultra_buildingid": building_id,
            "ultra_bhibuildingregistrationnum": (
                dca.PROBE_BUILDING_REGISTRATION
            ),
            "ultra_propertyinterest": {
                "Id": property_interest_id,
                "Name": "PROBE PROPERTY",
            },
            "ultra_county": {"Id": "county-id", "Name": "ESSEX"},
            "ultra_municipality": {
                "Id": "municipality-id",
                "Name": "Newark City",
            },
            "ultra_addressline1": "PROBE ADDRESS",
            "ultra_block": "441",
            "ultra_lot": "61",
            "statuscode": {"Name": status, "Value": 1},
        }
    )
    return {
        "record_type": "property_registration_building",
        "canonical_ref": (
            "PROPERTY:us-nj-dca-property-registration/34/"
            "building-registration/0714002653001"
        ),
        "source_id": dca.SOURCE_ID,
        "dataset_id": dca.SOURCE_METADATA.dataset_id,
        "building_registration_number": dca.PROBE_BUILDING_REGISTRATION,
        "property_registration_number": dca.PROBE_PROPERTY_REGISTRATION,
        "building_id": building_id,
        "property_interest_id": property_interest_id,
        "building_address": {
            "line1": "PROBE ADDRESS",
            "postal_code": "07104",
            "aka": [],
        },
        "parcel_coordinates": {
            "county": "ESSEX",
            "county_fips": "34013",
            "county_id": "county-id",
            "municipality": "Newark City",
            "municipality_id": "municipality-id",
            "block": "441",
            "lot": "61",
        },
        "building_registration_status": {"name": status, "value": 1},
        "property_registration_status": {
            "name": "Registered",
            "value": 1,
        },
        "registered_owner": {
            "id": "owner-id",
            "name": "PROBE OWNER LLC",
            "role": "DCA property-registration owner relationship",
        },
        "registered_owner_publication_state": "published_in_search_index",
        "source_match_context": {
            "observed_total_building_rows": observed_total,
            "emitted_through_this_page": 1,
            "pages_fetched_this_request": 1,
            "count_drift": None,
        },
        "adapter_schema_fingerprint": dca.ADAPTER_SCHEMA_FINGERPRINT,
        "response_field_fingerprint": "a" * 64,
        "raw_source": raw_source,
    }


def test_dca_monitor_hashes_contract_not_mutable_registration_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "building_id": "building-id-a",
        "property_interest_id": "property-id-a",
        "status": "Registered",
        "observed_total": 1,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert log_results is False
        return PublicRecordsResult.success(
            dca.build_query(args),
            [_probe_record(**rolling)],
        )

    monkeypatch.setattr(dca, "execute", fake_execute)
    context = ProbeContext(
        source_id=dca.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = public_records_monitor.probe_new_jersey_dca_property(context)
    rolling.update(
        building_id="building-id-b",
        property_interest_id="property-id-b",
        status="Inactive",
        observed_total=2,
    )
    second = public_records_monitor.probe_new_jersey_dca_property(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    assert first.details["artifact_identity"] == {
        "source_id": dca.SOURCE_ID,
        "sentinel_building_registration": dca.PROBE_BUILDING_REGISTRATION,
        "sentinel_property_registration": dca.PROBE_PROPERTY_REGISTRATION,
        "identity_grain": "13_digit_building_registration",
    }
    assert (
        first.details["schema_contract"]["registered_owner_semantics"]
        == "DCA regulatory-registration relationship, not deed title"
    )
    assert len(first.details["stable_contract"]["alternative_routes"]) == 6


def test_catalog_exposes_dca_identity_access_and_alternative_relationships(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    decision = catalog.require_machine_acquisition(dca.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["access_class"] == "A"
    assert decision["automation_disposition"] == "allowed_with_limits"
    assert decision["limits"]["minimum_interval_seconds"] == 0.25

    source = catalog.show_source(dca.SOURCE_ID)
    manifest = source["current_manifest"]
    adapter_routes = {
        record["source_id"] for record in dca.alternative_route_records()
    }
    assert set(manifest["complementary_source_ids"]) == adapter_routes
    assert manifest["stable_keys"][:2] == [
        "building_registration_number",
        "property_registration_number",
    ]
    assert (
        manifest["identity_contract"]["registered_owner_role"]
        == "dca_regulatory_registration_relationship"
    )
    assert manifest["identity_contract"]["registered_owner_is_deed_title"] is False
    assert (
        manifest["probe_evidence"]["adapter_schema_fingerprint"]
        == dca.ADAPTER_SCHEMA_FINGERPRINT
    )

    report = catalog.show_source("us-nj-dca-bhi-active-buildings-opra")
    report_manifest = report["current_manifest"]
    assert (
        report_manifest["record_identity_source_id"]
        == "us-nj-dca-bhi-active-buildings-opra"
    )
    assert (
        report_manifest["probe_evidence"]["same_publisher_dataset_lineage_as"]
        == dca.SOURCE_ID
    )
    assert (
        report_manifest["probe_evidence"][
            "matching_registration_counts_as_independent_corroboration"
        ]
        is False
    )
    assert report_manifest["probe_evidence"]["coverage"]["included"] == (
        "active_buildings_with_a_bhi_registration"
    )

    for source_id in (
        "us-nj-njgin-parcels-modiv",
        "us-nj-treasury-sr1a-sales",
        "us-nj-local-assessors-tax-boards",
        "us-nj-county-clerks-registers",
        "us-nj-opra-property-records",
    ):
        complement = catalog.show_source(source_id)["current_manifest"][
            "complementary_source_ids"
        ]
        assert dca.SOURCE_ID in complement

    spec = public_records_monitor.HANDLER_REGISTRY[dca.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_new_jersey_dca_property
    assert spec.expected_requests == 1
    assert spec.sentinel_record_count == 1
