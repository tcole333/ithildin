import json
import sys

import pytest

from tools import graph_tools, hypothesis_tracker, lead_tracker, pillar_tracker


@pytest.fixture
def ach_db(tmp_path, monkeypatch):
    db_path = tmp_path / "analysis-cli.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    db = hypothesis_tracker.get_hypothesis_db()
    db.execute(
        "INSERT INTO findings (id, target_name, summary) VALUES (1, 'Target', 'Evidence')"
    )
    db.commit()
    db.close()
    return db_path


def test_diagnose_filters_disagreements_by_competition_group(ach_db):
    included = hypothesis_tracker.add_hypothesis(
        "Included", competition_group="included"
    )
    excluded = hypothesis_tracker.add_hypothesis(
        "Excluded", competition_group="excluded"
    )
    for hypothesis_id in (included, excluded):
        hypothesis_tracker.evaluate_evidence(
            hypothesis_id, 1, "consistent", assessed_by="alpha"
        )
        hypothesis_tracker.evaluate_evidence(
            hypothesis_id, 1, "inconsistent", assessed_by="beta"
        )

    disagreements = hypothesis_tracker.diagnose_disagreements(
        competition_group="included"
    )

    assert [row["hypothesis_id"] for row in disagreements] == [included]


def test_diagnose_cli_accepts_competition_group(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(
        hypothesis_tracker,
        "diagnose_disagreements",
        lambda competition_group=None: seen.append(competition_group) or [],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hypothesis_tracker.py",
            "diagnose",
            "--competition-group",
            "focused-set",
            "--json",
        ],
    )

    hypothesis_tracker.main()

    assert seen == ["focused-set"]
    assert json.loads(capsys.readouterr().out) == []


def test_matrix_accepts_positional_hypothesis_ids(ach_db, monkeypatch, capsys):
    included = hypothesis_tracker.add_hypothesis("Included")
    hypothesis_tracker.add_hypothesis("Excluded")
    hypothesis_tracker.evaluate_evidence(
        included, 1, "consistent", assessed_by="tester"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["hypothesis_tracker.py", "matrix", str(included), "--json"],
    )

    hypothesis_tracker.main()

    payload = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in payload["hypotheses"]] == [included]


def test_graph_stats_writes_standard_output_file(monkeypatch, tmp_path, capsys):
    output = tmp_path / "graph-stats.json"
    monkeypatch.setattr(
        graph_tools,
        "build_graph",
        lambda **kwargs: ({"A": {"B": []}, "B": {"A": []}}, {"A", "B"}),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graph_tools.py",
            "--profile",
            "alpha",
            "stats",
            "--output",
            str(output),
        ],
    )

    graph_tools.main()

    assert json.loads(output.read_text())["edges"] == 1
    assert "saved to" in capsys.readouterr().out


def test_pillar_gaps_writes_standard_output_file(monkeypatch, tmp_path, capsys):
    output = tmp_path / "pillar-gaps.json"
    monkeypatch.setattr(
        pillar_tracker,
        "get_pillar_gaps",
        lambda person: ("Canonical Person", ["legal"], ["banking"]),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pillar_tracker.py",
            "gaps",
            "--person",
            "Person",
            "--output",
            str(output),
        ],
    )

    pillar_tracker.main()

    assert json.loads(output.read_text()) == {
        "person": "Canonical Person",
        "present": ["legal"],
        "missing": ["banking"],
    }
    assert "saved to" in capsys.readouterr().out
