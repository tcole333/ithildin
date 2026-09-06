from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts import financial_quality


def test_financial_export_default_uses_canonical_content_path():
    assert financial_quality.EXPORT_JSON_PATH == (
        Path(__file__).resolve().parents[1] / "content" / "financials" / "ds10-flows.json"
    )


def test_gate_checks_explicit_export_and_detects_changed_amount(
    tmp_path, copy_fixture_db, run_python_script
):
    inv_db = copy_fixture_db("financial_inv.db")
    ds10_db = copy_fixture_db("financial_ds10.db")
    with sqlite3.connect(ds10_db) as db:
        db.execute("UPDATE ds10_transactions SET amount=250000")
    export_dir = tmp_path / "exports"
    result = run_python_script(
        "pipeline/export_financials.py", "--diagram", "ds10",
        "--output-dir", str(export_dir), "--inv-db", str(inv_db),
        "--ds10-db", str(ds10_db), "--min-amount", "50000",
    )
    assert result.returncode == 0, result.stderr
    export_path = export_dir / "ds10-flows.json"

    def gate():
        return run_python_script(
            "scripts/financial_quality.py", "gate", "--strict", "--with-math", "--json",
            "--inv-db", str(inv_db), "--ds10-db", str(ds10_db),
            "--export-json", str(export_path),
        )

    result = gate()
    assert result.returncode == 0, result.stderr or result.stdout
    assert json.loads(result.stdout)["math_checks_passed"] is True

    payload = json.loads(export_path.read_text())
    assert payload["links"]
    payload["links"][0]["value"] += 100
    export_path.write_text(json.dumps(payload))
    result = gate()
    assert result.returncode == 2, result.stderr or result.stdout
    assert "MATH004_EXPORT_TOTAL_PARITY" in json.loads(result.stdout)["blocking_rules"]
