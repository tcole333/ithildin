import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

from tools.public_records_actions import (
    ACTION_SCHEMA_VERSION,
    build_action,
    enqueue_action,
    list_actions,
)
from tools.public_records_catalog import PublicRecordsCatalog
from tools.seed_public_records_catalog import seed_catalog


def _db_factory(path):
    def factory():
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS human_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                action_type TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                related_lead_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                notes TEXT
            )
            """
        )
        return db

    return factory


def test_build_action_retains_catalog_capabilities_without_behavioral_gate(tmp_path):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    action = build_action(
        PublicRecordsCatalog(catalog_path),
        source_id="us-in-iocs-bulk",
        operation="obtain_feed",
        selector="civil case metadata",
        requested_fields=["case_number", "docket_entries"],
    )

    assert action["schema_version"] == ACTION_SCHEMA_VERSION
    assert action["source"]["official_url"].startswith("https://")
    assert action["request"]["requested_fields"] == [
        "case_number",
        "docket_entries",
    ]
    assert action["selected_action_type"] in action["suggested_action_types"]
    assert {item["name"] for item in action["capabilities"]} >= {
        "search_cases",
        "sync",
    }


def test_enqueue_is_idempotent_for_active_equivalent_action(tmp_path):
    catalog_path = tmp_path / "catalog.db"
    actions_path = tmp_path / "investigation.db"
    seed_catalog(db_path=catalog_path)
    action = build_action(
        PublicRecordsCatalog(catalog_path),
        source_id="us-ny-nyscef",
        operation="fetch_document",
        selector="156728/2019 document 42",
        action_type="manual_verification",
    )
    factory = _db_factory(actions_path)

    first = enqueue_action(action, db_factory=factory)
    second = enqueue_action(action, db_factory=factory)
    forced = enqueue_action(action, db_factory=factory, force=True)

    assert first["status"] == "enqueued"
    assert second == {
        "status": "existing",
        "action_id": first["action_id"],
        "action": action,
    }
    assert forced["status"] == "enqueued"
    assert forced["action_id"] != first["action_id"]


def test_list_filters_structured_public_record_actions(tmp_path):
    catalog_path = tmp_path / "catalog.db"
    actions_path = tmp_path / "investigation.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    factory = _db_factory(actions_path)
    for source_id in ("us-ny-nyscef", "us-wi-wcca-rest"):
        action = build_action(
            catalog,
            source_id=source_id,
            operation="search",
            selector="EXAMPLE LLC",
        )
        enqueue_action(action, db_factory=factory)

    records = list_actions(
        source_id="us-wi-wcca-rest",
        status="pending",
        db_factory=factory,
    )

    assert len(records) == 1
    assert records[0]["action"]["source"]["source_id"] == "us-wi-wcca-rest"


def test_execute_plan_and_direct_cli_help(tmp_path):
    from tools import public_records_actions

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    args = argparse.Namespace(
        command="plan",
        source_id="us-in-iocs-bulk",
        operation="obtain_feed",
        selector=None,
        jurisdiction="18",
        court_or_office=None,
        requested_field=[],
        action_type=None,
        priority="high",
        related_lead_id=None,
        notes=None,
        catalog_db=str(catalog_path),
    )
    payload = public_records_actions.execute(args)
    assert payload["priority"] == "high"

    root = Path(__file__).resolve().parent.parent
    completed = subprocess.run(
        [sys.executable, "tools/public_records_actions.py", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "enqueue" in completed.stdout


def test_los_angeles_paid_name_and_physical_recorder_actions_remain_distinct(
    tmp_path,
):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    name_action = build_action(
        catalog,
        source_id="us-ca-los-angeles-superior-probate-name-index",
        operation="search_cases",
        selector="EXAMPLE PERSON",
        action_type="paid_lookup",
    )
    recorder_action = build_action(
        catalog,
        source_id="us-ca-los-angeles-registrar-recorder-real-estate",
        operation="request_instrument_copy",
        selector="EXAMPLE GRANTOR 2020",
    )

    assert name_action["selected_action_type"] == "paid_lookup"
    assert {"purchase", "paid_lookup"} <= set(
        name_action["suggested_action_types"]
    )
    assert len(name_action["capabilities"]) == 1
    name_capability = name_action["capabilities"][0]
    assert name_capability["name"] == "search_cases"
    assert name_capability["supported"] is True
    assert name_capability["details"] == {
        "route_type": "paid_lookup",
        "input_fields": [
            "party_last_name_and_first_name",
            "company_name",
        ],
        "output_fields": [
            "litigant_name",
            "case_type",
            "filing_date",
            "filing_location",
            "raw_case_number",
            "available_image_count",
        ],
    }

    assert recorder_action["selected_action_type"] == "physical_records"
    recorder_capabilities = {
        capability["name"]: capability["details"]
        for capability in recorder_action["capabilities"]
    }
    assert recorder_capabilities["search_parties"]["input_fields"] == [
        "grantor_name",
        "grantee_name",
        "recording_year",
    ]
    assert recorder_capabilities["request_instrument_copy"][
        "input_fields"
    ] == [
        "document_title",
        "listed_names",
        "recording_year_or_range",
        "recording_document_number",
    ]


def test_los_angeles_civil_name_index_action_exposes_implemented_stages(
    tmp_path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)

    action = build_action(
        PublicRecordsCatalog(catalog_path),
        source_id="us-ca-los-angeles-superior-civil-name-index",
        operation="prepare_name_search",
        selector="EXAMPLE HOLDINGS LLC",
        action_type="paid_lookup",
    )

    assert action["selected_action_type"] == "paid_lookup"
    assert {"purchase", "paid_lookup"} <= set(
        action["suggested_action_types"]
    )
    capabilities = {
        capability["name"]: capability["details"]
        for capability in action["capabilities"]
    }
    assert capabilities["probe_source"]["adapter_command"] == "probe"
    assert capabilities["prepare_name_search"]["adapter_command"] == (
        "prepare"
    )
    assert capabilities["recover_purchased_search"][
        "retrieve_option"
    ] == "--retrieve"
    assert capabilities["parse_purchased_results"]["adapter_command"] == (
        "parse-results"
    )
    assert capabilities["ingest_court_records"][
        "source_occurrence_table"
    ] == "case_source_occurrence"


def test_nyscef_action_includes_local_fulltext_follow_on(
    tmp_path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)

    action = build_action(
        PublicRecordsCatalog(catalog_path),
        source_id="us-ny-nyscef",
        operation="fetch_document",
        selector="156728/2019 document 7",
        action_type="manual_verification",
    )

    capabilities = {
        capability["name"]: capability["details"]
        for capability in action["capabilities"]
    }
    assert capabilities["fetch_document"]["adapter_tool"] == (
        "query_nyscef.py"
    )
    assert capabilities["normalize_document_manifest"][
        "adapter_tool"
    ] == "query_nyscef_fulltext.py"
    assert capabilities["build_fulltext_index"]["incremental_identity"] == (
        "record_identity_plus_pdf_sha256"
    )
    assert capabilities["search_filing_text"]["modes"] == [
        "phrase",
        "all",
        "fts",
    ]
