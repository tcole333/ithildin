import subprocess
import sys
from pathlib import Path


def test_query_sec_is_a_discoverable_edgar_alias():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(project_root / "tools/query_sec.py"), "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "SEC EDGAR" in result.stdout
    assert "lookup" in result.stdout
