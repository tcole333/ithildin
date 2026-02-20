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
def test_financial_quality_gate_clean_fixture_passes(copy_fixture_db, run_python_script) -> None:
    inv_db = copy_fixture_db("financial_inv.db")
    ds10_db = copy_fixture_db("financial_ds10.db")

    result = run_python_script(
        "scripts/financial_quality.py",
        "gate",
        "--scope",
        "publish",
        "--strict",
        "--json",
        "--inv-db",
        str(inv_db),
        "--ds10-db",
        str(ds10_db),
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["critical_count"] == 0


@pytest.mark.integration
@pytest.mark.real_fixture
def test_financial_quality_gate_strict_blocks_on_critical(copy_fixture_db, run_python_script) -> None:
    inv_db = copy_fixture_db("financial_inv.db")
    ds10_db = copy_fixture_db("financial_ds10.db")
    _insert_open_critical_issue(str(inv_db))

    result = run_python_script(
        "scripts/financial_quality.py",
        "gate",
        "--scope",
        "publish",
        "--strict",
        "--json",
        "--inv-db",
        str(inv_db),
        "--ds10-db",
        str(ds10_db),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "fail"
    assert payload["critical_count"] >= 1
    assert "MATH001_DIRECTION_AMOUNT" in payload["blocking_rules"]
