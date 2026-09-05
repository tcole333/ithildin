from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_california_opinions as opinions
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import (
    PublicRecordsResult,
    sha256_fingerprint,
)
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=opinions.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.35},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _taxonomy(collection: str, *, short: bool) -> dict[str, str]:
    values = {
        native_id: str(spec["name"])
        for native_id, spec in opinions.COURTS.items()
        if collection in spec["collections"]
    }
    if short:
        first = next(iter(values))
        return {first: values[first]}
    return values


def _probe_record(state: dict[str, Any]) -> dict[str, Any]:
    operations: dict[str, Any] = {}
    for collection in opinions.COLLECTIONS:
        operations[f"{collection}_listing"] = {
            "state": "available",
            "visible_count": state[f"{collection}_visible"],
            "total_count": state[f"{collection}_total"],
            "total_pages": state[f"{collection}_pages"],
            "schema_fingerprint": (
                "a" * 64 if collection == "published" else "b" * 64
            ),
            "page_fingerprint": state[f"{collection}_page_sha"],
            "source_document_sha256": state[
                f"{collection}_listing_sha"
            ],
            "source_taxonomy": _taxonomy(
                collection,
                short=state["short_taxonomy"],
            ),
            "source_url": opinions.COLLECTIONS[collection]["url"],
        }
        operations[f"{collection}_detail"] = {
            "state": "available",
            "case_number": state[f"{collection}_case"],
            "publication_status": opinions.COLLECTIONS[collection][
                "publication_status"
            ],
            "formats": state.get(
                f"{collection}_formats",
                ["pdf", "docx"],
            ),
            "source_document_sha256": state[
                f"{collection}_detail_sha"
            ],
            "source_url": (
                f"{opinions.BASE_URL}/opinion/{collection}/"
                f"2026-07-30/{state[f'{collection}_case'].lower()}"
            ),
        }
    return {
        "record_kind": "source_probe",
        "source_id": opinions.SOURCE_ID,
        "status": "ok",
        "operations": operations,
        "feed_totals": {
            collection: state[f"{collection}_total"]
            for collection in opinions.COLLECTIONS
        },
        "stable_contract_fingerprint": "c" * 64,
        "live_state_fingerprint": state["live_state_sha"],
    }


def test_monitor_keeps_publication_activity_out_of_drift_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, Any] = {
        "published_visible": 50,
        "published_total": 243,
        "published_pages": 5,
        "published_page_sha": "d" * 64,
        "published_listing_sha": "e" * 64,
        "published_case": "S287786",
        "published_detail_sha": "f" * 64,
        "unpublished_visible": 50,
        "unpublished_total": 1277,
        "unpublished_pages": 26,
        "unpublished_page_sha": "1" * 64,
        "unpublished_listing_sha": "2" * 64,
        "unpublished_case": "H052909",
        "unpublished_detail_sha": "3" * 64,
        "short_taxonomy": False,
        "live_state_sha": "4" * 64,
    }
    calls: list[Any] = []

    def fake_execute(
        args: Any,
        **_: Any,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.minimum_interval == 0.35
        calls.append(args)
        return PublicRecordsResult.success(
            opinions.build_query(args),
            [_probe_record(state)],
        )

    monkeypatch.setattr(opinions, "execute", fake_execute)
    first = public_records_monitor.probe_california_opinions(
        _context()
    )

    state.update(
        published_total=247,
        published_pages=5,
        published_page_sha="5" * 64,
        published_listing_sha="6" * 64,
        published_case="S289001",
        published_formats=["pdf"],
        published_detail_sha="7" * 64,
        unpublished_total=1284,
        unpublished_pages=26,
        unpublished_page_sha="8" * 64,
        unpublished_listing_sha="9" * 64,
        unpublished_case="B350634",
        unpublished_detail_sha="0" * 64,
        short_taxonomy=True,
        live_state_sha="a" * 64,
    )
    second = public_records_monitor.probe_california_opinions(
        _context()
    )

    assert len(calls) == 2
    assert first.status == second.status == "ok"
    assert first.result_count == second.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details[
        "stable_contract"
    ]
    assert first.details["schema_contract"] == second.details[
        "schema_contract"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.details["requests_made"] == 4
    assert first.details["stable_contract_sha256"] == (
        sha256_fingerprint(first.details["stable_contract"])
    )
    assert first.details["stable_schema_sha256"] == (
        sha256_fingerprint(first.details["schema_contract"])
    )
    drift = compare_probes(
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
    assert drift["drift_detected"] is False


def test_catalog_census_and_shared_operations_match_current_feeds(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    decision = catalog.require_machine_acquisition(opinions.SOURCE_ID)
    assert decision["allowed"] is True
    manifest = catalog.show_source(
        opinions.SOURCE_ID
    )["current_manifest"]

    assert manifest["roles"] == [
        "appellate_opinions",
        "published_slip_opinions",
        "unpublished_opinions",
        "direct_pdf_documents",
        "direct_docx_documents",
        "opinion_citings_archive",
    ]
    assert "official_reports" not in manifest["roles"]
    assert "appellate_case_index" not in manifest["roles"]
    assert "appellate_calendars" not in manifest["roles"]

    capabilities = {
        item["name"]: item["details"]
        for item in manifest["capabilities"]
    }
    assert capabilities["query_shared_court_records"][
        "shared_operations"
    ] == [
        "search",
        "case",
        "documents",
        "discovery",
        "probe",
        "download",
    ]
    ingest = capabilities["ingest_state_court_records"]
    assert ingest["search_case_documents_projection"] == {
        "cases": "one_sparse_appellate_case_shell",
        "docket_entries": "one_appellate_opinion_publication",
        "documents": "currently_listed_official_pdf_documents",
        "parties": "zero",
    }
    assert ingest["preserve_existing_case_fields"] is True
    assert ingest["shared_download_ingest"] == "skipped"
    assert manifest["probe_evidence"][
        "stable_adapter_contract_fingerprint"
    ] == "34b8f4f384e31e9866284b533ceb26ab23442bfad97451b7613a36978c0b3687"
    assert manifest["probe_evidence"][
        "monitor_stable_schema_sha256"
    ] == "7b4aef0d44f5b37fab6f27364389b287e477ae53e0c0400e193f9df38b6e1884"
    assert manifest["probe_evidence"][
        "monitor_stable_contract_sha256"
    ] == "f11e182110a3a7b285d71adefaaa2903862fb0faf6b785ae6204b3b7b615e83b"
    assert manifest["probe_evidence"][
        "monitor_artifact_identity_sha256"
    ] == "57024e00bf7e0133ddccd3104245b6948b2825259e977f136a60e83b31eb382c"

    associations = manifest["census_associations"]
    assert len(associations) == 1
    association = associations[0]
    assert association["jurisdiction_geoid"] == "06"
    assert association["role"] == "appellate_opinions"
    assert association["coverage"]["current_collections"] == {
        "published": {
            "window_days": 120,
            "publication_state": "as_filed_slip_opinion",
        },
        "unpublished": {
            "window_days": 60,
            "publication_state": (
                "source_designated_unpublished_opinion"
            ),
        },
    }
    assert len(association["coverage_gaps"]) == 4

    complements = {
        item["name"]: item for item in manifest["official_complements"]
    }
    assert set(complements) == {
        "California Appellate Case Information",
        "California Official Reports Opinions",
    }
    assert complements["California Official Reports Opinions"][
        "coverage"
    ] == "1850-present"
    assert all(
        item["integrated_by_current_feed_adapter"] is False
        and item["dataset_equivalent"] is False
        for item in complements.values()
    )

    audit = audit_catalog(db_path=catalog_path)
    mismatched_sources = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert opinions.SOURCE_ID not in mismatched_sources


def test_monitor_registration_is_bounded_and_visible() -> None:
    handler = public_records_monitor.HANDLER_REGISTRY[
        opinions.SOURCE_ID
    ]

    assert handler.capability == "probe_source"
    assert handler.endpoint == opinions.OPINIONS_HOME_URL
    assert handler.expected_requests == 4
    assert handler.sentinel_record_count == 1
    assert handler.handler is public_records_monitor.probe_california_opinions


def test_citation_and_docs_cover_current_and_corrected_versions() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{opinions.SOURCE_ID}"
    ] == opinions.OPINIONS_HOME_URL

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")

    assert "## California Judicial Branch current appellate opinions" in legal
    assert "B350634M" in legal
    assert "### California current appellate opinions" in tool_reference
    assert opinions.SOURCE_ID in tool_reference
    assert "California current-opinion feeds" in roadmap
