from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest


def _count(path: Path, sql: str, params: tuple = ()) -> int:
    conn = sqlite3.connect(str(path))
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.real_fixture
def test_fixture_manifest_matches_check_sync_artifacts(fixtures_root: Path, fixtures_data_dir: Path) -> None:
    manifest = json.loads((fixtures_root / "manifest.json").read_text())
    check_sync = manifest["artifacts"]["check_sync"]

    generated_at = manifest.get("generated_at_utc")
    assert generated_at
    datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ")

    dossier = json.loads((fixtures_data_dir / "dossiers" / "check-sync.json").read_text())
    finding_rows = dossier["findings"][0]["evidence"]
    assert len(finding_rows) == check_sync["finding_rows_in_fixture"]
    assert finding_rows[0]["evidence_ref"] == check_sync["packed_refs"]

    refs = [token.strip() for token in check_sync["packed_refs"].split(",") if token.strip()]
    db_path = fixtures_data_dir / "check_sync_investigation.db"
    finding_id = int(check_sync["source_finding_id"])
    db_rows = _count(db_path, "SELECT COUNT(*) FROM finding_evidence WHERE finding_id = ?", (finding_id,))
    assert db_rows == len(refs)

    connection_rows = _count(db_path, "SELECT COUNT(*) FROM connection_evidence")
    assert bool(connection_rows) == bool(check_sync["has_connection_fixture"])


@pytest.mark.integration
@pytest.mark.real_fixture
def test_fixture_manifest_matches_financial_artifacts(fixtures_root: Path, fixtures_data_dir: Path) -> None:
    manifest = json.loads((fixtures_root / "manifest.json").read_text())
    financial = manifest["artifacts"]["financial"]

    ds10_db = fixtures_data_dir / "financial_ds10.db"
    tx_count = _count(ds10_db, "SELECT COUNT(*) FROM ds10_transactions")
    assert tx_count == 1

    conn = sqlite3.connect(str(ds10_db))
    conn.row_factory = sqlite3.Row
    try:
        tx = conn.execute(
            "SELECT id, efta_id, qa_status FROM ds10_transactions WHERE id = ?",
            (financial["fixture_transaction_id"],),
        ).fetchone()
        assert tx is not None
        assert tx["efta_id"] == financial["source_efta_id"]
        assert tx["qa_status"] == financial["fixture_qa_status"]
    finally:
        conn.close()

    inv_db = fixtures_data_dir / "financial_inv.db"
    quality_runs = _count(inv_db, "SELECT COUNT(*) FROM quality_runs")
    quality_issues = _count(inv_db, "SELECT COUNT(*) FROM quality_issues")
    assert quality_runs == 0
    assert quality_issues == 0
