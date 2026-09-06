import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import investigation_context as context


def profile_database(tmp_path):
    db_path = tmp_path / "investigation.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE investigation_config(key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO investigation_config VALUES ('active_profile', 'alpha')")
    return db_path


def test_task_pin_survives_other_task_switching_default(tmp_path, monkeypatch):
    db_path = profile_database(tmp_path)
    environment = context.task_environment(db_path=db_path, environ={})
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE investigation_config SET value='beta'")
    monkeypatch.setattr(context, "DB_PATH", db_path)
    monkeypatch.setenv("ITHILDIN_PROFILE", environment["ITHILDIN_PROFILE"])
    assert context.get_active_profile_name() == "alpha"
    assert context.task_environment(db_path=db_path, environ={})["ITHILDIN_PROFILE"] == "beta"


def test_explicit_profile_and_db_override_inherited_context(tmp_path):
    selected = tmp_path / "custom.db"
    result = context.task_environment(
        "alpha", selected,
        environ={"ITHILDIN_PROFILE": "beta", "ITHILDIN_DB_PATH": "wrong.db", "OTHER": "retained"},
    )
    assert result == {
        "ITHILDIN_PROFILE": "alpha", "ITHILDIN_DB_PATH": str(selected), "OTHER": "retained",
    }
    assert not selected.exists()


@pytest.mark.parametrize("name", ["", "../alpha", "/alpha", "a/b", "alpha beta"])
def test_invalid_pin_never_falls_back_to_shared_profile(monkeypatch, name):
    monkeypatch.setenv("ITHILDIN_PROFILE", name)
    with pytest.raises(ValueError, match="Invalid investigation profile"):
        context.get_active_profile_name()


def test_missing_context_does_not_create_database(tmp_path):
    selected = tmp_path / "missing.db"
    with pytest.raises(ValueError, match="requires --profile"):
        context.task_environment(db_path=selected, environ={})
    assert not selected.exists()


def test_context_runner_pins_child_and_preserves_exit_status(tmp_path):
    selected = profile_database(tmp_path)
    script = Path(context.__file__)
    environment = dict(os.environ)
    environment.pop("ITHILDIN_PROFILE", None)
    command = [
        sys.executable, str(script), "run", "--profile", "chosen", "--db", str(selected), "--",
        sys.executable, "-c",
        "import json,os; print(json.dumps([os.environ['ITHILDIN_PROFILE'],os.environ['ITHILDIN_DB_PATH']])); raise SystemExit(7)",
    ]
    result = subprocess.run(command, text=True, capture_output=True, env=environment, check=False)
    assert result.returncode == 7, result.stderr
    assert json.loads(result.stdout) == ["chosen", str(selected)]
    with sqlite3.connect(selected) as db:
        assert db.execute("SELECT value FROM investigation_config").fetchone()[0] == "alpha"
