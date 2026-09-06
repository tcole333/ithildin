from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_ohio_franklin_municipal as municipal
from tools import query_state_courts
from tools import source_report
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import (
    ProbeContext,
    probe_franklin_municipal,
)
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import DEFAULT_CONFIG_PATH, seed_catalog


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_franklin_municipal"
)
SOURCE_ID = "us-oh-franklin-municipal-court-records"


def _fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _query(operation: str) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=municipal.SOURCE_METADATA,
        jurisdiction=municipal.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )


def _envelope(
    records: list[dict[str, Any]],
    *,
    operation: str,
) -> dict[str, Any]:
    return PublicRecordsResult.success(
        _query(operation),
        records,
    ).to_dict()


class _MunicipalCatalog:
    def show_source(self, source_id: str) -> dict[str, Any]:
        assert source_id == SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": "Franklin County Municipal Court Clerk Records Search",
                "official_url": municipal.SEARCH_URL,
                "authority": "Franklin County Municipal Court Clerk",
                "platform_family": municipal.PLATFORM_FAMILY,
            },
            "roles": [
                "trial_case_index",
                "party_name_index",
                "docket_entries",
                "generated_case_summary",
            ],
            "capabilities": [
                {"name": "search_cases", "supported": True},
                {"name": "fetch_case", "supported": True},
                {"name": "list_docket_entries", "supported": True},
                {"name": "list_document_index", "supported": True},
                {"name": "fetch_document", "supported": True},
            ],
            "latest_access_review": {"access_class": "B"},
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, Any]:
        assert source_id == SOURCE_ID
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "B",
            "reason": "review permits machine acquisition",
            "reason_code": "allowed",
        }


def _install_router_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _MunicipalCatalog(),
    )
    monkeypatch.setattr(query_state_courts, "log_search", lambda *_args: None)


def test_shared_router_preserves_person_and_company_search_selectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return PublicRecordsResult.success(_query(args.command), [])

    monkeypatch.setattr(municipal, "execute", fake_execute)
    person_args = query_state_courts.build_parser().parse_args(
        [
            "search",
            "BURKHALTER",
            "--source",
            SOURCE_ID,
            "--first-name",
            "ERIKA",
            "--middle-name",
            "Q",
            "--date-of-birth",
            "05/15/1978",
            "--party-type",
            "DEFENDANT",
            "--case-type",
            "CIVIL",
            "--case-year",
            "2022",
            "--case-status",
            "CLOSED",
            "--limit",
            "20",
        ]
    )
    company_args = query_state_courts.build_parser().parse_args(
        [
            "search",
            "L BRANDS",
            "--source",
            SOURCE_ID,
            "--entity-kind",
            "organization",
        ]
    )

    assert query_state_courts.execute(person_args)["status"] == "no_results"
    assert query_state_courts.execute(company_args)["status"] == "no_results"

    person, company = calls
    assert person.command == "person"
    assert person.last_name == "BURKHALTER"
    assert person.first_name == "ERIKA"
    assert person.middle_name == "Q"
    assert person.date_of_birth == "05/15/1978"
    assert person.party_type == "DEFENDANT"
    assert person.case_type == "CIVIL"
    assert person.year == 2022
    assert person.status == "CLOSED"
    assert person.shared_requested_limit == 20
    assert company.command == "company"
    assert company.company_name == "L BRANDS"
    assert company.shared_requested_limit is None


@pytest.mark.parametrize("operation", ["case", "docket", "documents"])
def test_shared_router_maps_exact_case_views(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return PublicRecordsResult.success(_query(args.command), [])

    monkeypatch.setattr(municipal, "execute", fake_execute)
    args = query_state_courts.build_parser().parse_args(
        [operation, "2022 CVF 020731", "--source", SOURCE_ID]
    )

    payload = query_state_courts.execute(args)

    assert payload["status"] == "no_results"
    assert calls[0].command == "case"
    assert calls[0].case_number == "2022 CVF 020731"


def test_shared_router_labels_generated_summary_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return PublicRecordsResult.success(_query(args.command), [])

    monkeypatch.setattr(municipal, "execute", fake_execute)
    destination = tmp_path / "case-summary.pdf"
    args = query_state_courts.build_parser().parse_args(
        [
            "download",
            "generated-case-summary",
            "--case-number",
            "2022 CVF 020731",
            "--destination",
            str(destination),
            "--source",
            SOURCE_ID,
        ]
    )

    payload = query_state_courts.execute(args)

    assert payload["status"] == "no_results"
    assert calls[0].command == "summary-pdf"
    assert calls[0].case_number == "2022 CVF 020731"
    assert calls[0].destination == str(destination)
    assert query_state_courts._source_guidance(SOURCE_ID)[
        "unified_operations"
    ] == [
        "case",
        "discovery",
        "docket",
        "documents",
        "download",
        "probe",
        "search",
    ]


def test_party_occurrence_ingestion_preserves_duplicate_case_roles(
    tmp_path: Path,
) -> None:
    page = municipal.parse_search_results(
        _fixture_text("exact_results.html"),
        query_fingerprint="e" * 64,
        matched_query={"case_number": "2022 CVF 020731"},
    )
    court_db = tmp_path / "party-index.db"
    envelope = _envelope(
        [dict(record) for record in page.records],
        operation="search",
    )

    first = ingest_envelope(envelope, court_db=court_db)
    second = ingest_envelope(envelope, court_db=court_db)

    assert first["projected"]["cases"] == 2
    assert first["projected"]["parties"] == 2
    assert first["projected"]["documents"] == 0
    assert second["status"] == "ingested"
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 1
        parties = db.execute(
            "SELECT role, raw_name FROM case_party ORDER BY case_party_id"
        ).fetchall()
        assert [(row["role"], row["raw_name"]) for row in parties] == [
            ("PLAINTIFF", "L BRANDS DIRECT FULFILLMENT LLC"),
            ("DEFENDANT", "ERIKA  BURKHALTER"),
        ]
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 0
    finally:
        db.close()


def test_exact_case_and_generated_summary_have_distinct_projection_states(
    tmp_path: Path,
) -> None:
    case_record = municipal.parse_case_detail(
        _fixture_text("civil_detail.html"),
        requested_case_number="2022 CVF 020731",
    )
    summary_record = {
        "record_kind": "case_summary_artifact",
        "source_id": SOURCE_ID,
        "court": {
            "court_id": municipal.COURT_ID,
            "name": municipal.COURT_NAME,
        },
        "display_case_number": "2022 CVF 020731",
        "normalized_case_number": "2022CVF020731",
        "canonical_case_ref": case_record["canonical_case_ref"],
        "document_kind": "generated_case_summary",
        "is_filed_document": False,
        "availability": "online_case_summary",
        "media_type": "application/pdf",
        "filename": "FCMC Case Information - 2022 CVF 020731.pdf",
        "sha256": "a" * 64,
        "size_bytes": 100,
        "destination": str(tmp_path / "case-summary.pdf"),
        "source_url": municipal.CASE_PDF_URL,
        "filed_document_copy_route": municipal.PUBLIC_RECORDS_POLICY_URL,
        "canonical_ref": f"{case_record['canonical_case_ref']}/case_summary",
    }
    court_db = tmp_path / "exact-case.db"

    case_report = ingest_envelope(
        _envelope([case_record], operation="case"),
        court_db=court_db,
    )
    summary_report = ingest_envelope(
        _envelope([summary_record], operation="summary-pdf"),
        court_db=court_db,
    )

    assert case_report["projected"]["cases"] == 1
    assert case_report["projected"]["parties"] == 2
    assert case_report["projected"]["attorneys"] == 1
    assert case_report["projected"]["representations"] == 1
    assert case_report["projected"]["assignments"] == 1
    assert case_report["projected"]["docket_entries"] == 3
    assert case_report["projected"]["case_events"] == 1
    assert case_report["projected"]["documents"] == 0
    assert summary_report["projected"]["documents"] == 0
    assert summary_report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"case_summary_artifact": 1},
    }
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 0
        stored = json.loads(
            db.execute("SELECT raw_json FROM case_record").fetchone()["raw_json"]
        )
        assert stored["documents"] == []
        assert stored["document_access"]["generated_case_summary"][
            "is_filed_document"
        ] is False
        assert stored["document_access"]["filed_documents"][
            "availability"
        ] == "not_linked_online"
    finally:
        db.close()


def _probe_record() -> dict[str, Any]:
    return {
        "record_kind": "source_probe",
        "source_id": SOURCE_ID,
        "status": "available",
        "request_count": municipal.PROBE_REQUEST_COUNT,
        "csrf_present": True,
        "search_field_names": [
            "_token",
            "last_name",
            "first_name",
            "desktop_view",
        ],
        "person_search_occurrences": 1,
        "person_search_truncated": False,
        "sentinel_case_number": "2022CVF020731",
        "sentinel_party_occurrences": 2,
        "sentinel_sections": [
            "overview",
            "parties",
            "attorneys",
            "disposition",
            "financial-summary",
            "receipts",
            "docket",
        ],
        "sentinel_docket_entries": 3,
        "summary_media_type": "application/pdf",
        "summary_sha256": "a" * 64,
        "summary_document_kind": "generated_case_summary",
        "summary_is_filed_document": False,
        "native_result_limit": municipal.NATIVE_RESULT_LIMIT,
        "native_pagination": "none",
        "rate_limit_headers": {
            "x-ratelimit-limit": "25",
            "x-ratelimit-remaining": "23",
        },
        "transport_secrets_persisted": False,
    }


def _probe_context() -> ProbeContext:
    return ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_monitor_separates_generated_summary_hash_from_stable_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _probe_record()
    rolling = copy.deepcopy(base)
    rolling["summary_sha256"] = "b" * 64
    rolling["rate_limit_headers"]["x-ratelimit-remaining"] = "7"
    schema_changed = copy.deepcopy(base)
    schema_changed["sentinel_sections"].append("new-section")
    queued = [base, rolling, schema_changed, base]

    def fake_execute(args, *, record_search=False):
        assert args.command == "probe"
        assert record_search is False
        return PublicRecordsResult.success(_query("probe"), [queued.pop(0)])

    monkeypatch.setattr(municipal, "execute", fake_execute)
    first = probe_franklin_municipal(_probe_context())
    second = probe_franklin_municipal(_probe_context())
    third = probe_franklin_municipal(_probe_context())
    monkeypatch.setattr(
        municipal,
        "CASE_PDF_URL",
        f"https://{municipal.OFFICIAL_HOST}/case/changed-summary-route",
    )
    fourth = probe_franklin_municipal(_probe_context())

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.schema_sha256 != third.schema_sha256
    assert first.artifact_sha256 == third.artifact_sha256
    assert first.schema_sha256 == fourth.schema_sha256
    assert first.artifact_sha256 != fourth.artifact_sha256
    assert first.details["stable_contract"]["document_states"] == {
        "generated_case_summary_is_filed_document": False,
        "individual_filing_links": "not_published_in_verified_case_view",
    }
    assert first.details["rolling_observation"]["summary_sha256"] == "a" * 64
    assert second.details["rolling_observation"]["summary_sha256"] == "b" * 64


def test_monitor_registry_declares_exact_five_request_contract() -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]

    assert municipal.PROBE_REQUEST_COUNT == 5
    assert spec.capability == "probe_source"
    assert spec.expected_requests == 5
    assert spec.sentinel_record_count == 1
    assert spec.sample_bytes is None
    assert spec.handler is probe_franklin_municipal


def test_manifest_census_search_plan_source_report_and_citation(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row for row in config["sources"] if row["source_id"] == SOURCE_ID
    )
    assert source["jurisdiction_geoids"] == ["39049"]
    assert "party_name_index" in source["roles"]
    assert source["stable_keys"] == [
        "court_id_plus_normalized_case_number",
        "query_fingerprint_plus_response_ordinal",
        "case_number_source_ordinal_and_docket_content",
    ]
    shared = next(
        capability
        for capability in source["capabilities"]
        if capability["name"] == "query_shared_state_courts"
    )
    assert shared["details"]["shared_operations"] == [
        "search",
        "case",
        "docket",
        "documents",
        "download",
        "discovery",
        "probe",
    ]
    assert shared["details"]["download_artifact_kind"] == (
        "generated_case_summary"
    )
    assert shared["details"]["download_is_filed_document"] is False
    fetch_document = next(
        capability
        for capability in source["capabilities"]
        if capability["name"] == "fetch_document"
    )
    assert fetch_document["details"]["artifact_kind"] == (
        "generated_case_summary"
    )
    assert fetch_document["details"]["is_filed_document"] is False

    census = yaml.safe_load(
        Path("config/public_records_census.yaml").read_text(encoding="utf-8")
    )
    target = next(
        target
        for target in census["additional_targets"]
        if target["jurisdiction_geoid"] == "39049"
        and target["domain"] == "court"
        and target["role"] == "trial_case_index"
    )
    assert "Municipal" in target["description"]

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"STATECOURT_SOURCE:{SOURCE_ID}"] == municipal.SEARCH_URL

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["39049"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
    )
    planned_source = next(
        row for row in plan["sources"] if row["source_id"] == SOURCE_ID
    )
    assert planned_source["access"]["mode"] == "allowed_with_limits"
    tasks = {
        task["capability"]: task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
        for task in stage["tasks"]
        if task["source_id"] == SOURCE_ID
    }
    assert set(tasks) == {
        "search_cases",
        "fetch_case",
        "list_docket_entries",
        "list_document_index",
        "fetch_document",
    }
    assert tasks["search_cases"]["capability_details"][
        "native_result_limit"
    ] == 250
    assert tasks["fetch_document"]["capability_details"][
        "is_filed_document"
    ] is False
    complements = next(
        group
        for group in plan["complementary_routes"]
        if group["primary_source_id"] == SOURCE_ID
    )
    assert {
        row["source_id"] for row in complements["complements"]
    } >= {
        "us-oh-franklin-common-pleas-cio",
        "us-oh-franklin-probate-netdata",
        "us-oh-franklin-county-recorder-publicsearch",
        "us-oh-franklin-county-auditor-property",
    }

    report = source_report.check_public_records_catalog(catalog_path)
    entry = report[
        "Public records / Franklin County Municipal Court Clerk Records Search"
    ]
    assert entry["source_id"] == SOURCE_ID
    assert entry["query_tool"] == "tools/query_state_courts.py"
