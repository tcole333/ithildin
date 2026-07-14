from __future__ import annotations

import json

import pytest

from tools import lead_tracker, papercut


@pytest.fixture
def papercut_db(tmp_path, monkeypatch):
    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    return tmp_path / "investigation.db"


def test_format_description_includes_reproduction_details():
    assert papercut.format_description(
        "Glob missed files",
        command="rg --glob *.json term",
        expected="search nested JSON",
        context="zsh expanded the glob",
    ) == (
        "Glob missed files | Command/tool: rg --glob *.json term | "
        "Expected: search nested JSON | Context: zsh expanded the glob"
    )


def test_log_list_and_resolve_papercut(papercut_db, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["papercut.py", "Tool emitted a misleading error", "--skill", "pursue-lead"],
    )
    papercut.main()
    assert "Papercut #1 logged" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["papercut.py", "--list"])
    papercut.main()
    listed = capsys.readouterr().out
    assert "Open papercuts (showing 1 of 1 open papercuts)" in listed
    assert "Tool emitted a misleading error" in listed

    monkeypatch.setattr(
        "sys.argv",
        ["papercut.py", "--resolve", "1", "--resolution", "Corrected the error message"],
    )
    papercut.main()
    assert "Papercut #1 addressed" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["papercut.py", "--list"])
    papercut.main()
    assert "No open papercuts" in capsys.readouterr().out


def test_list_writes_structured_json_output(papercut_db, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("sys.argv", ["papercut.py", "Tool emitted a misleading error"])
    papercut.main()
    capsys.readouterr()

    output = tmp_path / "papercuts.json"
    monkeypatch.setattr(
        "sys.argv",
        ["papercut.py", "--list", "--limit", "1", "--output", str(output)],
    )
    papercut.main()

    payload = json.loads(output.read_text())
    assert len(payload) == 1
    assert payload[0]["id"] == 1
    assert payload[0]["category"] == "friction"
    assert payload[0]["description"] == "Tool emitted a misleading error"
    assert capsys.readouterr().out == (
        f"1 results (showing 1 of 1 open papercuts) saved to {output}\n"
    )


def test_list_reports_total_when_limit_truncates_queue(
    papercut_db, monkeypatch, capsys, tmp_path
):
    for number in range(3):
        monkeypatch.setattr("sys.argv", ["papercut.py", f"Papercut {number}"])
        papercut.main()
        capsys.readouterr()

    output = tmp_path / "limited.json"
    monkeypatch.setattr(
        "sys.argv",
        ["papercut.py", "--list", "--limit", "1", "--output", str(output)],
    )
    papercut.main()

    assert len(json.loads(output.read_text())) == 1
    assert "showing 1 of 3 open papercuts" in capsys.readouterr().out


def test_resolve_requires_resolution(papercut_db, monkeypatch):
    monkeypatch.setattr("sys.argv", ["papercut.py", "--resolve", "99"])
    with pytest.raises(SystemExit) as exc:
        papercut.main()
    assert exc.value.code == 2


def test_duplicate_and_promote_lifecycle(papercut_db, monkeypatch, capsys):
    for message in ("First report", "Repeated report", "Larger repair"):
        monkeypatch.setattr("sys.argv", ["papercut.py", message])
        papercut.main()
        capsys.readouterr()

    monkeypatch.setattr("sys.argv", ["papercut.py", "--duplicate", "2", "--of", "1"])
    papercut.main()
    assert "marked duplicate" in capsys.readouterr().out
    assert papercut.get_observation(2)["status"] == "duplicate"

    db = lead_tracker.get_db()
    infra_id = db.execute(
        """
        INSERT INTO infra_requests (title, description, request_type)
        VALUES ('Larger repair', 'Needs a dedicated build', 'tool_fix')
        """
    ).lastrowid
    db.commit()
    db.close()

    monkeypatch.setattr(
        "sys.argv",
        ["papercut.py", "--promote", "3", "--infra-id", str(infra_id)],
    )
    papercut.main()
    assert "promoted to infra request" in capsys.readouterr().out
    promoted = papercut.get_observation(3)
    assert promoted["status"] == "acknowledged"
    assert promoted["related_infra_id"] == infra_id
