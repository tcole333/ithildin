from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _insert_open_math_critical_issue(inv_db_path: Path) -> None:
    conn = sqlite3.connect(str(inv_db_path))
    try:
        conn.execute(
            """
            INSERT INTO quality_issues
            (dataset, record_ref, issue_code, severity, status, details_json)
            VALUES ('ds10', 'ds10_transactions:1', 'MATH001_DIRECTION_AMOUNT', 'critical', 'open', '{}')
            """
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.real_fixture
def test_export_financials_ds10_honors_db_overrides(copy_fixture_db, run_python_script, tmp_path: Path) -> None:
    inv_db = copy_fixture_db("financial_inv.db")
    ds10_db = copy_fixture_db("financial_ds10.db")
    output_dir = tmp_path / "financials"

    result = run_python_script(
        "pipeline/export_financials.py",
        "--diagram",
        "ds10",
        "--output-dir",
        str(output_dir),
        "--ds10-db",
        str(ds10_db),
        "--inv-db",
        str(inv_db),
        "--min-amount",
        "10000",
    )
    assert result.returncode == 0, result.stderr or result.stdout

    payload = _load_json(output_dir / "ds10-flows.json")
    assert payload["stats"]["total_links"] >= 1
    assert payload["quality_run_id"] is None
    assert payload["math_checks_passed"] is True


@pytest.mark.integration
@pytest.mark.real_fixture
def test_export_financials_marks_math_checks_failed_when_critical_issue_present(
    copy_fixture_db,
    run_python_script,
    tmp_path: Path,
) -> None:
    inv_db = copy_fixture_db("financial_inv.db")
    ds10_db = copy_fixture_db("financial_ds10.db")
    _insert_open_math_critical_issue(inv_db)
    output_dir = tmp_path / "financials"

    result = run_python_script(
        "pipeline/export_financials.py",
        "--diagram",
        "ds10",
        "--output-dir",
        str(output_dir),
        "--ds10-db",
        str(ds10_db),
        "--inv-db",
        str(inv_db),
        "--min-amount",
        "10000",
    )
    assert result.returncode == 0, result.stderr or result.stdout

    payload = _load_json(output_dir / "ds10-flows.json")
    assert payload["math_checks_passed"] is False


@pytest.mark.integration
def test_export_financials_missing_ds10_path_returns_empty_dataset(
    copy_fixture_db,
    run_python_script,
    tmp_path: Path,
) -> None:
    inv_db = copy_fixture_db("financial_inv.db")
    output_dir = tmp_path / "financials"
    missing_ds10 = tmp_path / "missing_ds10.db"

    result = run_python_script(
        "pipeline/export_financials.py",
        "--diagram",
        "ds10",
        "--output-dir",
        str(output_dir),
        "--ds10-db",
        str(missing_ds10),
        "--inv-db",
        str(inv_db),
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "Warning:" in result.stdout

    payload = _load_json(output_dir / "ds10-flows.json")
    assert payload["nodes"] == []
    assert payload["links"] == []
    assert payload["stats"] == {}
