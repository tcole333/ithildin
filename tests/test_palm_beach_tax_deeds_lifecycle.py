from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import public_records_monitor
from tools import query_palm_beach_tax_deeds as tax_deeds
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import PublicRecordsResult, sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.public_records_priority import PublicRecordsPriority
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=tax_deeds.SOURCE_ID,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_monitor_keeps_rolling_source_state_out_of_contract_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling_total = 2
    stable_contract = {
        "home_url": tax_deeds.HOME_URL,
        "post_url": tax_deeds.POST_URL,
        "grid_url": tax_deeds.GRID_URL,
        "detail_url": tax_deeds.DETAIL_URL,
        "image_root": tax_deeds.IMAGE_ROOT,
        "search_types": {
            key: value["search_type"]
            for key, value in tax_deeds.SEARCH_CONTRACTS.items()
        },
        "status_label_value_map": dict(
            tax_deeds.OBSERVED_STATUS_OPTIONS
        ),
        "native_page_sizes": list(tax_deeds.NATIVE_PAGE_SIZES),
        "grid_fields": list(tax_deeds.GRID_FIELDS),
        "grid_schema_fingerprint": tax_deeds.GRID_SCHEMA_FINGERPRINT,
        "identity_contract": {
            "portal_case_occurrence_locator": "row_id",
            "case_identity": "case_number",
            "certificate_identity": "certificate_number",
            "parcel_join": "reversible_17_digit_pcn",
            "document_identity": "image_id",
            "identities_collapsed": False,
        },
    }
    artifact_identity = {
        "portal_row_id": tax_deeds.SENTINEL_ROW_ID,
        "case_number": tax_deeds.SENTINEL_CASE_NUMBER,
        "certificate_number": tax_deeds.SENTINEL_CERTIFICATE_NUMBER,
        "native_document_id": tax_deeds.SENTINEL_DOCUMENT_ID,
        "document_occurrence_id": "43079:document:1",
        "media_type": "application/pdf",
        "sha256": "a" * 64,
    }

    def fake_execute(args):
        record = {
            "source_id": tax_deeds.SOURCE_ID,
            "record_kind": "source_health_check",
            "native_document_id": "live-sentinel",
            "status": "ok",
            "stable_contract": stable_contract,
            "rolling_observation": {
                "website_version": "1.1.7.0",
                "sale_date_count": 512,
                "first_published_sale_date": "1996-01-10",
                "last_published_sale_date": "2026-12-16",
                "lands_available_total": rolling_total,
                "lands_available_pages": 1,
                "lands_available_first_page_row_ids": ["43079"],
                "sentinel_status": "LANDS AVAILABLE",
                "sentinel_document_inventory_count": 3,
            },
            "artifact_identity": artifact_identity,
            "request_count": 5,
            "source_url": tax_deeds.HOME_URL,
        }
        return PublicRecordsResult.success(
            tax_deeds.build_query(args),
            [record],
            retrieved_at="2026-07-30T12:00:00Z",
        )

    monkeypatch.setattr(tax_deeds, "execute", fake_execute)
    first = public_records_monitor.probe_palm_beach_tax_deeds(_context())
    rolling_total = 3
    second = public_records_monitor.probe_palm_beach_tax_deeds(_context())

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["rolling_observation"] != (
        second.details["rolling_observation"]
    )
    assert first.details["requests_made"] == 5
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
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


def test_catalog_census_priority_plan_and_handler_activate_source(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    decision = catalog.require_machine_acquisition(tax_deeds.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["limits"] == {}
    manifest = catalog.show_source(tax_deeds.SOURCE_ID)["current_manifest"]
    assert manifest["source_status"] == "active"
    assert manifest["stable_keys"] == [
        "portal_row_id_case_occurrence",
        "tax_deed_case_number",
        "certificate_number",
        "portal_row_id_and_auction_date_event",
        "portal_row_id_and_document_sequence_occurrence",
        "image_id_document",
    ]
    assert manifest["transport_contract"]["caller_limit_required"] is False
    assert manifest["transport_contract"][
        "omitted_limit_exhausts_source_reported_pages"
    ] is True
    assert manifest["identity_contract"]["identities_collapsed"] is False
    assert manifest["publication_contract"][
        "current_recorded_title_conclusion"
    ] is False

    targets = census.list_targets(
        state="FL",
        domain="property",
        role="tax_deed_cases_and_sales",
    )
    assert any(
        tax_deeds.SOURCE_ID in target["source_ids"] for target in targets
    )

    priority = PublicRecordsPriority(
        catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    priority_db = priority._catalog_connect()
    try:
        assert tax_deeds.SOURCE_ID in priority._source_inventory(priority_db)
    finally:
        priority_db.close()

    plan = build_search_plan(
        "Example Person",
        jurisdictions=["12099"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    tasks = {
        task["capability"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == tax_deeds.SOURCE_ID
    }
    assert tasks == {"search_cases", "fetch_sale", "fetch_document"}

    handler = public_records_monitor.HANDLER_REGISTRY[tax_deeds.SOURCE_ID]
    assert handler.handler is public_records_monitor.probe_palm_beach_tax_deeds
    assert handler.expected_requests == 5
    assert handler.sample_bytes is None


def test_docs_and_citation_capture_contract_and_complements() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[f"PROPERTY_SOURCE:{tax_deeds.SOURCE_ID}"] == (
        tax_deeds.HOME_URL
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
        assert "query_palm_beach_tax_deeds.py" in text
        assert "Image Not Available" in text
        assert "certified" in text.casefold()
    assert "snapshot-bound" in roadmap
    assert "43079" in reference
