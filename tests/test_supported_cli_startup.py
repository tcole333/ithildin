"""These imports previously worked only in a manually augmented environment."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("script", [
    "query_property.py", "query_state_courts.py", "public_records_monitor.py",
    "query_oregon_tax_foreclosures.py", "query_usaspending.py",
])
def test_supported_cli_help_from_declared_environment(script, tmp_path):
    root = Path(__file__).parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / script), "--help"],
        cwd=root, capture_output=True, text=True, timeout=30,
        env={**os.environ, "ITHILDIN_DB_PATH": str(tmp_path / "unused.db")},
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert not (tmp_path / "unused.db").exists()
