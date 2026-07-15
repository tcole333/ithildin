from __future__ import annotations

from tools import source_report


SOURCES = {
    "Example source": {
        "status": "available",
        "description": "Deterministic test source",
        "query_tool": "tools/query_example.py",
        "records": 3,
    }
}


def test_explicit_report_command_prints_coverage(monkeypatch, capsys):
    monkeypatch.setattr(source_report, "load_env_file", lambda: None)
    monkeypatch.setattr(source_report, "generate_report", lambda: SOURCES)
    monkeypatch.setattr("sys.argv", ["source_report.py", "report"])

    source_report.main()

    output = capsys.readouterr().out
    assert "OSINT DATA SOURCE REPORT" in output
    assert "Example source (3 records)" in output
    assert "Sources available: 1/1" in output


def test_bare_invocation_remains_report_alias(monkeypatch, capsys):
    monkeypatch.setattr(source_report, "load_env_file", lambda: None)
    monkeypatch.setattr(source_report, "generate_report", lambda: SOURCES)
    monkeypatch.setattr("sys.argv", ["source_report.py"])

    source_report.main()

    assert "Sources available: 1/1" in capsys.readouterr().out
