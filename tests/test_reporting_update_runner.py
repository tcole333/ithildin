from __future__ import annotations

import json

from scripts.update_reporting_corpus import should_trip_gdelt_breaker


def test_gdelt_circuit_breaker_is_bounded_and_can_be_disabled():
    assert should_trip_gdelt_breaker(3, 3) is True
    assert should_trip_gdelt_breaker(2, 3) is False
    assert should_trip_gdelt_breaker(100, 0) is False


def test_update_runner_can_be_invoked_directly(tmp_path, run_python_script):
    db_path = tmp_path / "reporting.db"
    result = run_python_script(
        "scripts/update_reporting_corpus.py",
        "--db", str(db_path),
        "--skip-gdelt", "--skip-repository", "--skip-seeds", "--skip-pages",
        "--ingest-limit", "0",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["counts"]["items"] == 0
    assert payload["counts"]["archive_versions"] == 0
