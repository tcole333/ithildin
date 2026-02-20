from __future__ import annotations

import json
import sqlite3

import pytest


def _insert_open_critical_issue(inv_db_path: str) -> None:
    db = sqlite3.connect(inv_db_path)
    try:
        db.execute(
            """
            INSERT INTO quality_issues
            (dataset, record_ref, issue_code, severity, status, details_json)
            VALUES ('ds10', 'ds10_transactions:1', 'MATH001_DIRECTION_AMOUNT', 'critical', 'open', '{}')
            """
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.integration
@pytest.mark.real_fixture
def test_financial_backfill_demotes_and_creates_review_task(copy_fixture_db, run_python_script) -> None:
    inv_db = copy_fixture_db("financial_inv.db")
    ds10_db = copy_fixture_db("financial_ds10.db")
    _insert_open_critical_issue(str(inv_db))

    result = run_python_script(
        "scripts/financial_quality.py",
        "backfill-financial",
        "--queue",
        "--apply",
        "--run-id",
        "pytest_backfill_run",
        "--inv-db",
        str(inv_db),
        "--ds10-db",
        str(ds10_db),
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["demoted_promoted_transactions"] >= 1

    ds10_conn = sqlite3.connect(str(ds10_db))
    ds10_conn.row_factory = sqlite3.Row
    inv_conn = sqlite3.connect(str(inv_db))
    inv_conn.row_factory = sqlite3.Row
    try:
        row = ds10_conn.execute("SELECT qa_status FROM ds10_transactions WHERE id = 1").fetchone()
        assert row is not None
        assert row["qa_status"] == "needs_review"

        task = inv_conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM review_tasks
            WHERE dataset = 'ds10' AND record_ref = 'ds10_transactions:1'
            """
        ).fetchone()
        assert task is not None
        assert int(task["c"]) >= 1
    finally:
        ds10_conn.close()
        inv_conn.close()
