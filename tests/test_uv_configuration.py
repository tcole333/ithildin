from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]


def _uv_config() -> dict[str, object]:
    return tomllib.loads((ROOT / "uv.toml").read_text(encoding="utf-8"))


def test_uv_version_guard_excludes_sandbox_panic_release() -> None:
    requirement = SpecifierSet(str(_uv_config()["required-version"]))

    assert Version("0.9.28") not in requirement
    assert Version("0.9.29") in requirement


def test_uv_run_starts_project_python() -> None:
    result = subprocess.run(
        ["uv", "run", "python", "-c", "print('uv-sandbox-ok')"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "uv-sandbox-ok"
