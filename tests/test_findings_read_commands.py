import json
import sys

import pytest

from tools import findings_tracker, investigation_context, lead_tracker


@pytest.fixture
def findings_db(tmp_path, monkeypatch):
    db_path = tmp_path / "findings-read.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    yield db
    db.close()


def _add_unverified(profile_id, target):
    return findings_tracker.add_finding(
        target_name=target,
        summary=f"{target} summary",
        source_datasets=["courtlistener"],
        evidence_ids=["COURTLISTENER:fixture-record"],
        source_quotes={"COURTLISTENER:fixture-record": {"quote": "The record identifies the subject."}},
        profile_id=profile_id,
    )


def test_get_unverified_defaults_to_active_profile_and_can_include_all(
    findings_db, monkeypatch
):
    _add_unverified("alpha", "Alpha")
    _add_unverified("beta", "Beta")
    monkeypatch.setattr(investigation_context, "get_active_profile_id", lambda: "alpha")

    assert [row["profile_id"] for row in findings_tracker.get_unverified()] == ["alpha"]
    assert {
        row["profile_id"] for row in findings_tracker.get_unverified(all_profiles=True)
    } == {"alpha", "beta"}


def test_unverified_cli_profile_filter_supports_structured_output(
    findings_db, monkeypatch, capsys, tmp_path
):
    alpha_id = _add_unverified("alpha", "Alpha")
    _add_unverified("beta", "Beta")
    monkeypatch.setattr(
        sys, "argv",
        ["findings_tracker.py", "unverified", "--profile", "alpha", "--json"],
    )

    findings_tracker.main()

    payload = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in payload] == [alpha_id]

    output = tmp_path / "unverified.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findings_tracker.py",
            "unverified",
            "--profile",
            "alpha",
            "--output",
            str(output),
        ],
    )
    findings_tracker.main()
    assert [row["id"] for row in json.loads(output.read_text())] == [alpha_id]
    assert "saved to" in capsys.readouterr().out


def test_audit_cli_supports_json_and_output_file(
    findings_db, monkeypatch, capsys, tmp_path
):
    finding_id = _add_unverified("alpha", "Alpha")
    findings_db.execute(
        """INSERT INTO corrections
           (table_name, record_id, field_name, old_value, new_value, reason, corrected_by)
           VALUES ('findings', ?, 'summary', 'old', 'new', 'fix', 'tester')""",
        (finding_id,),
    )
    findings_db.commit()

    monkeypatch.setattr(
        sys, "argv", ["findings_tracker.py", "audit", str(finding_id), "--json"]
    )
    findings_tracker.main()
    assert json.loads(capsys.readouterr().out)[0]["new_value"] == "new"

    output = tmp_path / "audit.json"
    monkeypatch.setattr(
        sys, "argv",
        ["findings_tracker.py", "audit", str(finding_id), "--output", str(output)],
    )
    findings_tracker.main()
    assert json.loads(output.read_text())[0]["record_id"] == finding_id
    assert "saved to" in capsys.readouterr().out


@pytest.mark.parametrize(
    "query_args",
    [
        ["Alpha"],
        ["--query", "Alpha"],
    ],
)
def test_search_cli_accepts_positional_and_query_flag(
    findings_db, monkeypatch, capsys, query_args
):
    finding_id = _add_unverified("alpha", "Alpha")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findings_tracker.py",
            "search",
            *query_args,
            "--all-profiles",
            "--json",
        ],
    )

    findings_tracker.main()

    payload = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in payload] == [finding_id]


@pytest.mark.parametrize("type_flag", ["--type", "--relation-type"])
def test_relate_cli_accepts_short_and_explicit_relation_type(
    monkeypatch, capsys, type_flag
):
    calls = []
    monkeypatch.setattr(
        findings_tracker,
        "relate_findings",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findings_tracker.py",
            "relate",
            "10",
            "11",
            type_flag,
            "corroborates",
        ],
    )

    findings_tracker.main()

    assert calls == [
        (
            (10, 11, "corroborates"),
            {"assessment": None, "created_by": "human"},
        )
    ]
    assert "Recorded: #10 corroborates #11" in capsys.readouterr().out
