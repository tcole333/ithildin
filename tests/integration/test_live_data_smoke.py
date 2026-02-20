from __future__ import annotations

from pathlib import Path

import pytest


def _require_path(path: Path, label: str) -> None:
    if not path.exists():
        pytest.skip(f"{label} not available at {path}")


@pytest.mark.integration
@pytest.mark.live_data
@pytest.mark.slow
def test_live_unified_stats_smoke(repo_root: Path, run_python_script) -> None:
    unified_db = repo_root / "datasets" / "unified_epstein.db"
    _require_path(unified_db, "Unified DB")

    result = run_python_script("tools/query_unified.py", "stats")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "Unified Database Statistics" in result.stdout
    assert "Emails:" in result.stdout


@pytest.mark.integration
@pytest.mark.live_data
@pytest.mark.slow
def test_live_lmsband_stats_smoke(repo_root: Path, run_python_script) -> None:
    lmsband_db = repo_root / "datasets" / "lmsband_epstein_files.db"
    _require_path(lmsband_db, "LMSBAND DB")

    result = run_python_script("tools/query_lmsband.py", "stats")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "LMSBAND Database Statistics" in result.stdout
    assert "Files:" in result.stdout
