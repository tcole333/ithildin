from __future__ import annotations

import os
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_CONFTEST_SPEC = spec_from_file_location(
    "public_records_test_conftest",
    Path(__file__).with_name("conftest.py"),
)
assert _CONFTEST_SPEC is not None and _CONFTEST_SPEC.loader is not None
_CONFTEST = module_from_spec(_CONFTEST_SPEC)
_CONFTEST_SPEC.loader.exec_module(_CONFTEST)
_enable_live_public_record_tests = (
    _CONFTEST._enable_live_public_record_tests
)
_live_public_record_env_names = _CONFTEST._live_public_record_env_names


def test_live_gate_discovery_and_activation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "test_live_fixture.py").write_text(
        "\n".join(
            [
                "import os",
                'A = os.environ.get("RUN_LIVE_EXAMPLE") == "1"',
                'B = os.getenv("LIVE_PUBLIC_RECORDS") == "1"',
                'C = os.getenv("OSINT_LIVE_TESTS") == "1"',
                'D = os.getenv("UNRELATED_SETTING") == "1"',
            ]
        ),
        encoding="utf-8",
    )
    expected = (
        "LIVE_PUBLIC_RECORDS",
        "OSINT_LIVE_TESTS",
        "RUN_LIVE_EXAMPLE",
    )
    for name in expected:
        monkeypatch.delenv(name, raising=False)

    assert _live_public_record_env_names(tmp_path) == expected
    assert _enable_live_public_record_tests(tmp_path) == expected
    assert {name: os.environ.get(name) for name in expected} == {
        name: "1" for name in expected
    }
    assert os.environ.get("UNRELATED_SETTING") is None


def test_pytest_help_exposes_live_public_record_switch(
    repo_root: Path,
) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--run-live-public-records" in completed.stdout
