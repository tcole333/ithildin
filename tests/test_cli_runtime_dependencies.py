from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("script", [
    "tools/offshorealert_search.py",
    "scripts/backfill_ds09_text_entities.py",
])
def test_supported_cli_starts_with_project_dependencies(script):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / script), "--help"], cwd=root,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
