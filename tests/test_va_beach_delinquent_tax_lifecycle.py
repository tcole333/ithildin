from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_va_beach_delinquent_tax as va_tax
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import PublicRecordsResult, sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
LIVE_RESPONSE_SCHEMA_SHA256 = (
    "de4fdd05304ba93dfeb65b9dc8fe71d0d8df0f3f8ac0a14a9e17ef2241794d78"
)
MONITOR_HASHES = {
    "monitor_stable_schema_sha256": (
        "83249d20d32e1d80f3f3dfb4034e9bd6c0aef11d357bd8ec65167b64c2f090d4"
    ),
    "monitor_stable_contract_sha256": (
        "450b3cdb3463b345daf008a1d5c3e7aec9e79ba78752f467e0248ac7a1e4167f"
    ),
    "monitor_artifact_identity_sha256": (
        "8c83b52d9b13235a94843396319f8938074a27b2ea892848f295da3dea0cfba7"
    ),
}


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=va_tax.SOURCE_ID,
        catalog_decision={
            "allowed": True,
            "limits": {
                "minimum_interval_seconds": 0.1,
                "maximum_page_size": 2000,
            },
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _probe_record(marker: int) -> dict[str, Any]:
    bill_number = "1125000027"
    installment = "2"
    gpin = "14469645070000"
    tax_year = 2025
    native_event_id = f"{bill_number}:{installment}:{gpin}:{tax_year}"
    total_due_minor = 145_678 + marker
    return {
        "source_id": va_tax.SOURCE_ID,
        "record_kind": "property_tax_delinquency",
        "record_scope": "delinquent_real_estate_tax_installment",
        "canonical_ref": (
            f"PROPERTY:{va_tax.SOURCE_ID}/51810/tax-delinquency/"
            f"{native_event_id}"
        ),
        "source_url": va_tax.QUERY_URL,
        "native_document_id": native_event_id,
        "native_event_id": native_event_id,
        "native_object_id": marker,
        "native_parcel_id": gpin,
        "native_account_id": bill_number,
        "gpin": gpin,
        "tax_year": tax_year,
        "bill_number": bill_number,
        "installment": installment,
        "owner_observation": {
            "raw_name": "EXAMPLE OWNER",
            "role": "published_primary_owner",
            "additional_owners_may_be_omitted": True,
        },
        "stable_key_fields": [
            "bill_number",
            "installment",
            "gpin",
            "tax_year",
        ],
        "amounts": {
            "tax_due_minor": total_due_minor - 3_400,
            "penalty_due_minor": 1_000,
            "interest_due_minor": 2_000,
            "fee_due_minor": 400,
            "total_due_minor": total_due_minor,
            "component_total_minor": total_due_minor,
            "component_difference_minor": 0,
            "currency": "USD",
        },
        "source_snapshot": {
            "data_last_edit_epoch_ms": 1_785_400_000_000 + marker,
            "data_last_edit_at": f"2026-07-30T08:39:4{marker}Z",
            "update_frequency": "daily",
        },
        "adapter_schema_fingerprint": va_tax.ADAPTER_SCHEMA_FINGERPRINT,
        "response_schema_fingerprint": LIVE_RESPONSE_SCHEMA_SHA256,
    }


def test_monitor_keeps_daily_snapshot_changes_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = 1

    def fake_execute(
        args: Any,
        *,
        access_decision: dict[str, Any],
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.page_size == 1
        assert access_decision["allowed"] is True
        return PublicRecordsResult.success(
            va_tax.build_query(
                "probe",
                va_tax.SearchCriteria(),
                limit=1,
                cursor=None,
            ),
            [_probe_record(marker)],
            warnings=(
                f"Authoritative source count for this query snapshot: {marker}.",
            ),
        )

    monkeypatch.setattr(va_tax, "execute", fake_execute)
    first = public_records_monitor.probe_virginia_beach_delinquent_tax(
        _context()
    )
    marker = 2
    second = public_records_monitor.probe_virginia_beach_delinquent_tax(
        _context()
    )

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["schema_contract"] == second.details["schema_contract"]
    assert first.details["artifact_identity"] == second.details[
        "artifact_identity"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.details["stable_schema_sha256"] == sha256_fingerprint(
        first.details["schema_contract"]
    )
    assert {
        "monitor_stable_schema_sha256": first.schema_sha256,
        "monitor_stable_contract_sha256": first.details[
            "stable_contract_sha256"
        ],
        "monitor_artifact_identity_sha256": first.artifact_sha256,
    } == MONITOR_HASHES

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


def test_catalog_census_and_projection_contracts_are_source_specific(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    assert catalog.require_machine_acquisition(va_tax.SOURCE_ID)["allowed"] is True
    manifest = catalog.show_source(va_tax.SOURCE_ID)["current_manifest"]
    capabilities = {
        capability["name"]: capability["details"]
        for capability in manifest["capabilities"]
    }
    assert capabilities["query_shared_property_records"]["shared_operations"] == [
        "address",
        "discovery",
        "event",
        "owner",
        "parcel",
        "probe",
        "search",
    ]
    assert manifest["identity_contract"][
        "tax_installment_occurrence_fields"
    ] == ["bill_number", "installment", "gpin", "tax_year"]
    assert manifest["identity_contract"]["parcel_join_fields"] == [
        "gpin",
        "jurisdiction_geoid",
    ]
    assert manifest["identity_contract"]["transport_locator"] == "OBJECTID"
    assert (
        manifest["identity_contract"]["transport_locator_is_occurrence_identity"]
        is False
    )
    assert manifest["publication_contract"]["event_date_published"] is False
    assert (
        manifest["publication_contract"]["source_snapshot_is_delinquency_onset"]
        is False
    )
    assert manifest["publication_contract"]["monetary_storage"] == (
        "exact_integer_cents"
    )
    assert {
        complement["role"] for complement in manifest["official_complements"]
    } == {
        "current_tax_account_detail_and_payment_history",
        "assessment_and_current_owner_context",
        "recorded_deeds_judgments_and_ucc",
        "circuit_court_case_index",
        "general_district_court_case_index",
        "tax_sale_notices_and_auction_links",
    }
    assert {
        field_name: manifest["probe_evidence"][field_name]
        for field_name in MONITOR_HASHES
    } == MONITOR_HASHES

    target = census.list_targets(
        state="VA",
        domain="property",
        role="tax_collection",
    )[0]
    association = next(
        item
        for item in target["source_associations"]
        if item["source_id"] == va_tax.SOURCE_ID
    )
    assert target["geoid"] == "51"
    assert association["coverage"]["statewide"] is False
    assert association["coverage"]["locality_geoid"] == "51810"
    assert association["coverage"]["record_grain"] == (
        "current_delinquent_real_estate_tax_installment"
    )


def test_catalog_audit_monitor_registry_docs_and_citation(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    audit = audit_catalog(db_path=catalog_path)
    mismatches = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert va_tax.SOURCE_ID not in mismatches

    handler = public_records_monitor.HANDLER_REGISTRY[va_tax.SOURCE_ID]
    assert handler.handler is (
        public_records_monitor.probe_virginia_beach_delinquent_tax
    )
    assert handler.endpoint == va_tax.ITEM_API_URL
    assert handler.expected_requests == 5
    assert handler.sentinel_record_count == 1
    assert handler.sample_bytes is None

    source_urls = json.loads(
        (
            ROOT / "web" / "src" / "data" / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[
        f"PROPERTY_SOURCE:{va_tax.SOURCE_ID}"
    ] == va_tax.OPEN_DATA_URL

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
        assert va_tax.SOURCE_ID in content
    assert "bill number + installment + GPIN + tax year" in property_docs
    assert "does not invent a delinquency-onset date" in property_docs
    assert "Manatron" in property_docs
    assert "Circuit Court" in property_docs
    assert "tax-sale" in property_docs


@pytest.mark.live_data
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for the bounded official source probe",
)
def test_live_monitor_hashes_match_catalog_pins() -> None:
    observation = public_records_monitor.probe_virginia_beach_delinquent_tax(
        _context()
    )

    assert observation.status == "ok"
    assert observation.schema_sha256 == MONITOR_HASHES[
        "monitor_stable_schema_sha256"
    ]
    assert observation.details["stable_contract_sha256"] == MONITOR_HASHES[
        "monitor_stable_contract_sha256"
    ]
    assert observation.artifact_sha256 == MONITOR_HASHES[
        "monitor_artifact_identity_sha256"
    ]
    assert observation.details["rolling_observation"]["source_snapshot"][
        "update_frequency"
    ] == "daily"
    assert observation.details["stable_contract"]["snapshot_semantics"][
        "source_snapshot_is_not_delinquency_onset"
    ] is True
