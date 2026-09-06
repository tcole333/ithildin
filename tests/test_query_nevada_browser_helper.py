import json
import os
import shutil
import subprocess

import pytest

from tools import query_nevada
from tests.browser_runtime_fixture import browser_runtime_env


def test_nevada_helper_runtime_check_smoke(tmp_path):
    node = shutil.which("node")
    assert node, "Node.js is required for the Nevada SilverFlume browser helper"

    env = browser_runtime_env(tmp_path, "NV")
    result = subprocess.run(
        [node, str(query_nevada.HELPER_PATH), "runtime-check"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["playwright_module"] == env["NV_PLAYWRIGHT_MODULE"]
    assert data["browser_channel"] in {"chrome", "chromium"}
    assert "chrome" in data["browser_executable"].lower()


def test_nevada_missing_browser_is_actionable(tmp_path):
    result = subprocess.run(
        ["node", str(query_nevada.HELPER_PATH), "runtime-check"],
        env=browser_runtime_env(tmp_path, "NV", browser_present=False),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1
    assert "Google Chrome runtime not found" in result.stderr
    assert not result.stdout


def test_nevada_helper_missing_playwright_is_actionable():
    node = shutil.which("node")
    assert node, "Node.js is required to exercise the helper dependency check"
    env = os.environ.copy()
    env["NV_PLAYWRIGHT_MODULE"] = "definitely-missing-playwright-for-test"

    result = subprocess.run(
        [node, str(query_nevada.HELPER_PATH), "runtime-check"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode == 1
    assert "RUNTIME ERROR: Playwright runtime not found" in result.stderr
    assert "npm --prefix web ci" in result.stderr
    assert result.stdout == ""


def test_run_helper_reports_missing_node(monkeypatch, capsys):
    monkeypatch.setattr(query_nevada.shutil, "which", lambda _name: None)

    assert query_nevada._run_helper(["runtime-check"]) is None

    stderr = capsys.readouterr().err
    assert "Node.js runtime not found in PATH" in stderr
    assert "npm --prefix web ci" in stderr


def test_runtime_check_command_exits_nonzero_when_dependency_missing(monkeypatch):
    monkeypatch.setattr(query_nevada, "_run_helper", lambda *_args, **_kwargs: None)

    with pytest.raises(SystemExit) as exc:
        query_nevada.cmd_runtime_check(object())

    assert exc.value.code == 1
