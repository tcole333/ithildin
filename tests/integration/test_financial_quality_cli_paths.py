from __future__ import annotations

import json
import sqlite3

import pytest


@pytest.mark.integration
@pytest.mark.real_fixture
def test_financial_quality_qa_ds10_honors_db_overrides(copy_fixture_db, run_python_script) -> None:
    inv_db = copy_fixture_db("financial_inv.db")
    ds10_db = copy_fixture_db("financial_ds10.db")

    result = run_python_script(
        "scripts/financial_quality.py",
        "qa-ds10",
        "--run-id",
        "pytest_qa_paths",
        "--inv-db",
        str(inv_db),
        "--ds10-db",
        str(ds10_db),
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["run_db_id"] >= 1

    inv_conn = sqlite3.connect(str(inv_db))
    inv_conn.row_factory = sqlite3.Row
    try:
        row = inv_conn.execute(
            """
            SELECT dataset, run_type, run_id, status
            FROM quality_runs
            WHERE run_id = 'pytest_qa_paths'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
        assert row["dataset"] == "ds10"
        assert row["run_type"] == "qa"
        assert row["status"] == "passed"
    finally:
        inv_conn.close()


@pytest.mark.integration
@pytest.mark.real_fixture
def test_financial_quality_recon_report_honors_ds10_override(copy_fixture_db, run_python_script) -> None:
    ds10_db = copy_fixture_db("financial_ds10.db")

    result = run_python_script(
        "scripts/financial_quality.py",
        "recon-report",
        "--json",
        "--ds10-db",
        str(ds10_db),
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert "total_statements" in payload
    assert "pass_count" in payload
