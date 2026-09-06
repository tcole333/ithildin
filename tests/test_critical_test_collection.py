"""Exercise the actual pytest selector boundary without executing research tests."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import CRITICAL_TEST_NODEIDS

ROOT = Path(__file__).resolve().parents[1]
CRITICAL_FILES = sorted({nodeid.split("::", 1)[0] for nodeid in CRITICAL_TEST_NODEIDS})


def collect(tmp_path, *selectors, files=CRITICAL_FILES, required=True):
    env = {
        **os.environ,
        "ITHILDIN_PROFILE": "epstein",
        "ITHILDIN_DB_PATH": str(tmp_path / "unused-investigation.db"),
        "PYTEST_ADDOPTS": "",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *files, "--collect-only", "--offline", "-q",
         *(["--require-critical-tests"] if required else []), *selectors],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
    )
    assert not Path(env["ITHILDIN_DB_PATH"]).exists()
    return result


def test_deterministic_selector_retains_critical_integrity_tests(tmp_path):
    result = collect(tmp_path, "-m", "not live_data")
    assert result.returncode == 0, result.stdout + result.stderr
    for nodeid in CRITICAL_TEST_NODEIDS:
        assert nodeid in result.stdout


def test_former_integration_only_selector_is_rejected_after_deselection(tmp_path):
    result = collect(tmp_path, "-m", "integration and not live_data")
    assert result.returncode == 4, result.stdout + result.stderr
    assert "deselected" in result.stdout
    assert "Required critical tests were omitted from collection" in result.stderr
    for nodeid in CRITICAL_TEST_NODEIDS:
        assert nodeid in result.stderr


def test_keyword_filter_cannot_drop_a_critical_test(tmp_path):
    omitted = "test_delete_cannot_remove_last_direct_quote_evidence"
    result = collect(tmp_path, "-k", f"not {omitted}")
    assert result.returncode == 4, result.stdout + result.stderr
    assert omitted in result.stderr
    assert "test_inference_confirmed_clamps_to_medium" not in result.stderr


def test_narrowed_file_selection_cannot_satisfy_ci_contract(tmp_path):
    result = collect(tmp_path, files=["tests/test_enforcement.py"])
    assert result.returncode == 4, result.stdout + result.stderr
    assert "tests/test_lead_tracker_fk_migration.py" in result.stderr
    assert "test_inference_confirmed_clamps_to_medium" not in result.stderr


def test_focused_local_collection_remains_available_without_ci_guard(tmp_path):
    result = collect(tmp_path, files=["tests/test_enforcement.py"], required=False)
    assert result.returncode == 0, result.stdout + result.stderr
