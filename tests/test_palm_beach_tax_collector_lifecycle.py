from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_palm_beach_tax_collector as tax
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "palm_beach_tax_collector"
)


def _json(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=tax.SOURCE_ID,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_settings_preserve_native_page_and_publisher_ceiling() -> None:
    settings = tax.parse_search_settings(_json("search-settings.json"))

    assert settings.records_per_page == 10
    assert settings.maximum_records == 300
    assert settings.data_source == "AUMENTUMTAX"
    assert settings.selected_view == "QuickSearch"
    assert "Processing.aspx" in settings.auto_forward
    assert settings.confidentiality_published is True
    assert {"Owner", "ParcelID", "PaidStatus"} <= set(
        settings.advanced_fields
    )


def test_exact_search_keeps_pcn_and_account_locator_separate() -> None:
    settings = tax.parse_search_settings(_json("search-settings.json"))
    rows, total = tax.parse_search_page(_json("search-exact.json"))
    record = tax.normalize_search_result(
        rows[0],
        criteria=tax.SENTINEL_PCN,
        native_page=1,
        native_row=1,
        settings=settings,
        source_reported_total=total,
    )

    assert record["native_parcel_id"] == "04364325000005040"
    assert record["formatted_pcn"] == "04-36-43-25-00-000-5040"
    assert record["native_account_id"] == "1081671"
    assert record["parcel_join"]["value"] != record["native_account_id"]
    assert record["owners"][0]["role"] == "tax_account_publisher_label"


def test_confidential_result_preserves_mask_without_reconstruction() -> None:
    settings = tax.parse_search_settings(_json("search-settings.json"))
    rows, total = tax.parse_search_page(_json("search-confidential.json"))
    record = tax.normalize_search_result(
        rows[0],
        criteria="CONFIDENTIAL",
        native_page=1,
        native_row=1,
        settings=settings,
        source_reported_total=total,
    )

    assert record["publisher_redaction_state"]["confidential"] is True
    assert set(record["publisher_redaction_state"]["masked_fields"]) == {
        "owner",
        "owners",
        "delivery",
        "situs",
    }
    assert record["publisher_redaction_state"][
        "masked_values_reconstructed"
    ] is False


def test_native_paging_cursor_binds_query_settings_total_and_ceiling() -> None:
    settings_payload = {
        **_json("search-settings.json"),
        "recordsPerPage": 2,
        "maximumRecords": 3,
    }
    rows = [
        {
            "TotalItems": 3,
            "PrimaryKey": f"0436432500000{index:04d}",
            "AlternateKey": str(1081670 + index),
            "ParcelID": f"04-36-43-25-00-000-{index:04d}",
            "Owner": f"OWNER {index}",
        }
        for index in range(1, 4)
    ]

    class FakeClient:
        def __init__(self) -> None:
            self.request_count = 0

        def fetch_search_settings(self):
            self.request_count += 1
            return settings_payload

        def fetch_search_page(self, criteria: str, page: int):
            assert criteria == "SMITH"
            self.request_count += 1
            start = (page - 1) * 2
            return {"Items": rows[start : start + 2]}

    first = tax.fetch_search_records(
        FakeClient(),
        criteria="SMITH",
        limit=1,
        cursor=None,
    )
    assert len(first.records) == 1
    assert first.next_cursor
    assert first.source_ceiling_reached is True
    assert first.source_reported_total == 3

    second = tax.fetch_search_records(
        FakeClient(),
        criteria="SMITH",
        limit=None,
        cursor=first.next_cursor,
    )
    assert len(second.records) == 2
    assert second.next_cursor is None
    assert second.source_effective_total == 3

    with pytest.raises(tax.PalmBeachTaxError, match="different search"):
        tax.fetch_search_records(
            FakeClient(),
            criteria="JONES",
            limit=1,
            cursor=first.next_cursor,
        )


def test_account_bill_and_payment_records_preserve_operation_grain() -> None:
    account = tax.normalize_account(
        pcn=tax.SENTINEL_PCN,
        alternate_key="1081671",
        sections={
            462: _json("account-462.json"),
            465: _json("account-465.json"),
        },
    )
    bills = tax.normalize_bills(
        _json("bills.json"),
        pcn=tax.SENTINEL_PCN,
        alternate_key="1081671",
    )
    payment = tax.normalize_payment(
        _json("payment-page.json")["Data"][0],
        pcn=tax.SENTINEL_PCN,
        alternate_key="1081671",
        native_page=1,
        native_row=1,
    )

    assert account["record_kind"] == "property_tax_account_snapshot"
    assert account["source_last_updated"] == "07/30/2026 10:12:13 AM"
    assert account["snapshot_semantics"][
        "last_updated_is_property_event_date"
    ] is False
    assert account["owners"][0]["role"] == "tax_account_publisher_label"

    assert len(bills) == 2
    omitted = next(value for value in bills if value["tax_year"] == "2018")
    assert omitted["native_ids"] == {
        "bill_id": "770001",
        "bill_number": "2018-009991",
        "installment": "1",
        "tax_year": "2018",
    }
    assert omitted["amounts"]["amount_due"] == "1150.00"
    assert omitted["publisher_messages"][0]["text"] == (
        "LANDS AVALABLE-TAXES HAVE BEEN OMITTED-CONTACT CLERK OF COURT"
    )
    assert omitted["snapshot_semantics"]["amounts_are_retrieved_state"] is True

    assert payment["record_kind"] == "property_tax_payment"
    assert payment["native_ids"]["receipt_number"] == "R-240001"
    assert payment["receipt_amount"] == "1234.56"
    assert payment["payer_observation"]["role"] == "source_observed_payer"
    assert payment["payer_observation"]["owner_or_title_role"] is False


def test_bill_detail_discovers_tenant_modules_and_document_links() -> None:
    record = tax.parse_bill_detail_html(
        (FIXTURE_DIR / "bill-detail.html").read_text(encoding="utf-8"),
        url=(
            f"{tax.BILL_DETAIL_URL}?p={tax.SENTINEL_PCN}&a=1081671"
            "&b=770001&y=2018&t=Real%20Property&n=2018-009991"
        ),
        pcn=tax.SENTINEL_PCN,
        alternate_key="1081671",
        bill_id="770001",
        tax_year="2018",
        bill_number="2018-009991",
    )

    assert record["published_module_ids"] == [466, 467, 671, 678]
    assert record["documents"][0]["label"] == "Download Tax Bill"
    assert record["bill_detail_semantics"][
        "module_ids_are_universal_aumentum_constants"
    ] is False


def test_refresh_status_is_routing_metadata_not_completion_poll() -> None:
    record = tax._sync_status_record(_json("sync-status.json"))

    assert record["module_id"] == 461
    assert record["tab_id"] == 48
    assert record["refresh_selector"] == {
        "field_name": "RevObjId",
        "parameter_name": "a",
    }
    assert record["semantics"]["per_account_completion_poll"] is False


def test_monitor_separates_stable_contract_from_rolling_account_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = "PRIEST DANNY"

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.request_count = 0

        def fetch_search_settings(self):
            self.request_count += 1
            return _json("search-settings.json")

        def fetch_sync_status(self):
            self.request_count += 1
            return _json("sync-status.json")

        def fetch_search_page(self, criteria: str, page: int):
            assert criteria == tax.SENTINEL_PCN
            assert page == 1
            self.request_count += 1
            payload = _json("search-exact.json")
            payload["Items"][0]["Owner"] = owner
            payload["Items"][0]["Owners"] = [owner]
            return payload

    monkeypatch.setattr(tax, "PalmBeachTaxClient", FakeClient)
    first = public_records_monitor.probe_palm_beach_tax_collector(
        _context()
    )
    owner = "CURRENT ACCOUNT LABEL"
    second = public_records_monitor.probe_palm_beach_tax_collector(
        _context()
    )

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["rolling_observation"] != (
        second.details["rolling_observation"]
    )
    assert first.details["requests_made"] == 3
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.details["stable_contract"]["account_refresh"][
        "per_account_completion_poll"
    ] is False
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


def test_catalog_census_and_handler_activate_verified_tax_source(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    decision = catalog.require_machine_acquisition(tax.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["limits"] == {}
    manifest = catalog.show_source(tax.SOURCE_ID)["current_manifest"]
    assert manifest["source_status"] == "active"
    assert manifest["platform_family"] == (
        "aumentum_publicaccessnow_dnn_property_tax"
    )
    assert manifest["search_contract"]["publisher_maximum_records"] == 300
    assert manifest["search_contract"][
        "adapter_selected_result_cap"
    ] is None
    assert manifest["identity_contract"]["identities_collapsed"] is False
    assert manifest["account_contract"][
        "refresh_status_is_per_account_completion_poll"
    ] is False
    capability_names = {
        capability["name"] for capability in manifest["capabilities"]
    }
    assert {
        "search_tax_accounts",
        "fetch_tax_status",
        "fetch_account",
        "fetch_bills",
        "fetch_payment_history",
        "ingest_property_records",
        "probe_source",
    } <= capability_names

    targets = census.list_targets(
        state="FL",
        domain="property",
        role="tax_collection",
    )
    assert any(tax.SOURCE_ID in target["source_ids"] for target in targets)

    handler = public_records_monitor.HANDLER_REGISTRY[tax.SOURCE_ID]
    assert handler.handler is (
        public_records_monitor.probe_palm_beach_tax_collector
    )
    assert handler.expected_requests == 3
    assert handler.sample_bytes is None


def test_docs_and_citation_capture_tax_source_contract_and_complements() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[f"PROPERTY_SOURCE:{tax.SOURCE_ID}"] == (
        tax.OFFICIAL_GUIDANCE_URL
    )

    module = (ROOT / "docs" / "modules" / "property.md").read_text(
        encoding="utf-8"
    )
    reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    for text in (module, reference, roadmap):
        assert "query_palm_beach_tax_collector.py" in text
        assert "AlternateKey" in text
        assert "maximumRecords" in text
    assert "AUMENTUMTAX" in module
    assert "payment-history payer" in reference.casefold()
    assert "PublicAccessNow" in roadmap
