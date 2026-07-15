import json
import os
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_california


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "_ca_browser_helper.js"


def test_california_runtime_check_uses_node_playwright_and_chrome() -> None:
    result = subprocess.run(
        ["node", str(HELPER), "runtime-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["playwright_module"] in {"playwright", "playwright-core"}
    assert data["browser_channel"] == "chrome"
    assert Path(data["browser_executable"]).is_file()
    assert data["headless"] is False


def test_california_missing_playwright_error_is_actionable() -> None:
    env = os.environ.copy()
    env["CA_PLAYWRIGHT_MODULE"] = "definitely-missing-ca-playwright-for-test"
    result = subprocess.run(
        ["node", str(HELPER), "runtime-check"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "Playwright runtime not found" in result.stderr
    assert "npm install playwright" in result.stderr


def test_california_helper_rejects_unbounded_limit_before_browser_launch() -> None:
    result = subprocess.run(
        ["node", str(HELPER), "search", "APPLE", "--limit", "501"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "--limit must be an integer from 1 to 500" in result.stderr


def test_california_helper_classifies_waf_html_before_json_parse() -> None:
    script = f"""
const helper = require({json.dumps(str(HELPER))});
try {{
  helper.parseSearchBody('<html>Request unsuccessful. Incapsula</html>', 'text/html');
}} catch (error) {{
  process.stderr.write(error.message);
  process.exit(7);
}}
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 7
    assert "non-JSON HTML" in result.stderr
    assert "Imperva challenge" in result.stderr
    assert "Unexpected token" not in result.stderr


def test_python_search_bridge_preserves_bounded_result_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def fake_helper(args, timeout=120):
        calls.append((args, timeout))
        return {
            "count": 2,
            "returned": 2,
            "truncated": False,
            "results": [
                {"internal_id": "1", "entity_name": "ALPHA", "entity_number": "1"},
                {"internal_id": "2", "entity_name": "BETA", "entity_number": "2"},
            ],
        }

    monkeypatch.setattr(query_california, "_run_helper", fake_helper)
    monkeypatch.setattr(query_california, "log_search", lambda *args, **kwargs: None)
    output = tmp_path / "results.json"
    args = Namespace(
        query="C0123456",
        by_number=True,
        status="all",
        type=None,
        officer_first=None,
        officer_middle=None,
        officer_last=None,
        limit=2,
        output=str(output),
        json_out=False,
    )

    query_california.cmd_search(args)

    assert calls == [(["search", "0123456", "--limit", "2"], 120)]
    data = json.loads(output.read_text())
    assert [row["internal_id"] for row in data] == ["1", "2"]


def test_unverified_california_paths_fail_before_browser_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        query_california,
        "_run_helper",
        lambda *args, **kwargs: pytest.fail("helper must not run"),
    )
    filtered = Namespace(
        query="APPLE",
        by_number=False,
        status="active",
        type=None,
        officer_first=None,
        officer_middle=None,
        officer_last=None,
        limit=5,
        output=None,
        json_out=False,
    )
    with pytest.raises(SystemExit) as search_exit:
        query_california.cmd_search(filtered)
    assert search_exit.value.code == 2

    with pytest.raises(SystemExit) as entity_exit:
        query_california.cmd_entity(Namespace(entity_id="C0726332", history=False))
    assert entity_exit.value.code == 2
