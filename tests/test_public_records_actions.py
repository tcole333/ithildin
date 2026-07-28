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
