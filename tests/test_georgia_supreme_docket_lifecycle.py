from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_georgia_supreme_docket as georgia
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import (
    PublicRecordsResult,
    sha256_fingerprint,
)
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=georgia.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _probe_record(
    *,
    case_status: str,
    filing_count: int,
    judgment_count: int,
    attorney_count: int,
) -> dict[str, Any]:
    return {
        "canonical_ref": f"STATECOURT:{georgia.SOURCE_ID}/probe",
        "source_id": georgia.SOURCE_ID,
        "record_kind": "source_probe",
        "source_url": georgia.PORTAL_URL,
        "stable_contract": {
            "search_endpoint": georgia.SEARCH_URL,
            "detail_endpoint": (
                f"{georgia.CASE_DETAIL_ROOT}/{{case_number}}"
            ),
            "search_response": "complete JSON array",
            "case_detail_sections": [
                "filingsAndOrders",
                "judgments",
                "attorneys",
            ],
            "document_access": "Clerk request handoff",
        },
        "rolling_observation": {
            "case_number": georgia.PROBE_CASE_NUMBER,
            "case_style": "EXAMPLE APPELLANT v. EXAMPLE APPELLEE",
            "case_status": case_status,
            "filing_metadata_count": filing_count,
            "judgment_count": judgment_count,
            "attorney_count": attorney_count,
        },
        "schema_contract": {
            "search": "a" * 64,
            "detail": "b" * 64,
        },
        "requests_made": 2,
    }


def test_monitor_separates_stable_contract_from_rolling_case_contents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "case_status": "Docketed",
        "filing_count": 3,
        "judgment_count": 0,
        "attorney_count": 2,
    }
    calls: list[Any] = []

    def fake_execute(
        args: Any,
        **_: Any,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.case_number == georgia.PROBE_CASE_NUMBER
        assert args.minimum_interval == 0.25
        calls.append(args)
        return PublicRecordsResult.success(
            georgia.build_query(args),
            [_probe_record(**state)],
        )

    monkeypatch.setattr(georgia, "execute", fake_execute)

    first = public_records_monitor.probe_georgia_supreme_docket(
        _context()
    )
    state.update(
        case_status="Remittitur",
        filing_count=8,
        judgment_count=1,
        attorney_count=4,
    )
    second = public_records_monitor.probe_georgia_supreme_docket(
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
    assert first.details["stable_contract_sha256"] == second.details[
        "stable_contract_sha256"
    ]
    assert first.details["schema_contract"] == second.details[
        "schema_contract"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.schema_sha256 == sha256_fingerprint(
        first.details["schema_contract"]
    )
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.details["requests_made"] == 2


def test_catalog_census_shared_operations_and_complements_are_exact(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    manifest = catalog.show_source(
        georgia.SOURCE_ID
    )["current_manifest"]
    assert catalog.require_machine_acquisition(georgia.SOURCE_ID)[
        "allowed"
    ] is True
    assert manifest["roles"] == [
        "appellate_case_index",
        "appellate_docket",
        "filing_and_order_metadata",
        "judgment_metadata",
        "attorney_index",
        "lower_court_case_pivots",
        "clerk_copy_request_handoff",
    ]
    assert "appellate_opinions" not in manifest["roles"]
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
        "docket",
        "documents",
        "discovery",
        "probe",
    ]
    assert capabilities["ingest_state_court_records"][
        "search_projection"
    ] == "one_case_per_case_index_hit"
    assert capabilities["ingest_state_court_records"][
        "document_rows_created"
    ] is False
    assert capabilities["ingest_state_court_records"][
        "snapshot_only_operations"
    ] == ["documents", "discovery", "probe"]

    associations = manifest["census_associations"]
    assert len(associations) == 1
    assert associations[0]["jurisdiction_geoid"] == "13"
    assert associations[0]["role"] == "appellate_case_index"
    assert associations[0]["coverage"]["court_id"] == (
        georgia.COURT_ID
    )
    assert associations[0]["coverage"]["case_window"] == (
        "cases_docketed_in_the_last_5_years"
    )
    assert manifest["probe_evidence"][
        "monitor_stable_schema_sha256"
    ] == "8d9f99b78c5b8cd5a33efb542ceff94a1c9477f4ffb60708ac0d61bbde4e17c5"
    assert manifest["probe_evidence"][
        "monitor_stable_contract_sha256"
    ] == "f54cb7776b3a8237a02d363844700e923054466bbbe33c72b3c2f78163324cf3"
    assert manifest["probe_evidence"][
        "monitor_artifact_identity_sha256"
    ] == "1d0599e575d2bbafd971f6b2628dee9dd6236c8583283d5fbdd3c2fd470b18f2"

    complements = {
        item["name"]: item
        for item in manifest["official_complements"]
    }
    assert {
        "Supreme Court opinions and noteworthy summaries",
        "Certiorari grants",
        "Certiorari denials",
        "Discretionary application grant orders",
        "Interlocutory application grant orders",
        "Supreme Court oral argument calendar",
        "Supreme Court case announcements",
    } <= set(complements)
    assert complements["Certiorari grants"]["source_id"] == (
        "us-ga-supreme-court-certiorari-grants"
    )
    assert complements["Discretionary application grant orders"][
        "component"
    ] == "discretionary"
    assert complements["Interlocutory application grant orders"][
        "component"
    ] == "interlocutory"
    assert all(
        item["dataset_equivalent"] is False
        for item in complements.values()
    )
    assert {
        item["source_id"]
        for item in complements.values()
        if item.get("integration_status") == "integrated_as_separate_source"
    } == {
        "us-ga-supreme-court-opinions",
        "us-ga-supreme-court-certiorari-grants",
        "us-ga-supreme-court-certiorari-denials",
        "us-ga-supreme-court-application-grant-orders",
    }
    assert {
        item["name"]
        for item in complements.values()
        if item.get("integration_status") == "not_integrated_complement"
    } == {
        "Supreme Court oral argument calendar",
        "Supreme Court case announcements",
    }

    audit = audit_catalog(db_path=catalog_path)
    mismatched_sources = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert georgia.SOURCE_ID not in mismatched_sources


def test_monitor_registry_has_two_request_budget() -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[
        georgia.SOURCE_ID
    ]

    assert spec.handler is (
        public_records_monitor.probe_georgia_supreme_docket
    )
    assert spec.endpoint == georgia.PORTAL_URL
    assert spec.expected_requests == 2
    assert spec.sentinel_record_count == 1


def test_citation_and_docs_cover_docket_and_publication_complements() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{georgia.SOURCE_ID}"
    ] == georgia.PORTAL_URL

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")

    assert "## Supreme Court of Georgia recent public docket" in legal
    assert "## Supreme Court of Georgia decision publications" in legal
    assert (
        "### Supreme Court of Georgia public-docket adapter"
        in tool_reference
    )
    assert (
        "### Supreme Court of Georgia decision publications"
        in tool_reference
    )
    assert georgia.SOURCE_ID in tool_reference
    assert "Supreme Court of Georgia anonymous recent-case search" in (
        roadmap
    )
