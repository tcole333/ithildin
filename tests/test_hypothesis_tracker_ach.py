import json
import sqlite3

import pytest

from tools import hypothesis_tracker, lead_tracker


@pytest.fixture
def ach_db(tmp_path, monkeypatch):
    db_path = tmp_path / "investigation.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    db = hypothesis_tracker.get_hypothesis_db()
    db.executemany(
        "INSERT INTO findings (target_name, summary) VALUES (?, ?)",
        [("Target", "shared evidence"), ("Target", "discriminating evidence")],
    )
    db.commit()
    db.close()
    return db_path


def test_schema_migration_is_idempotent(tmp_path):
    db = sqlite3.connect(tmp_path / "legacy.db")
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE hypotheses (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT,
            pattern_type TEXT, status TEXT DEFAULT 'proposed', predicted_evidence TEXT,
            search_plan TEXT, evidence_for TEXT, evidence_against TEXT,
            originated_from TEXT, lead_id INTEGER, thread_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP,
            resolved_by TEXT
        )
    """)
    db.execute("CREATE TABLE findings (id INTEGER PRIMARY KEY, target_name TEXT, summary TEXT)")

    hypothesis_tracker._ensure_hypothesis_schema(db)
    hypothesis_tracker._ensure_hypothesis_schema(db)

    columns = {row["name"] for row in db.execute("PRAGMA table_info(hypotheses)")}
    assert {"competition_group", "is_null_hypothesis"} <= columns
    db.close()


def test_competition_group_filters_list_matrix_and_compete(ach_db):
    h1 = hypothesis_tracker.add_hypothesis("Group A", competition_group="phenomenon-a")
    h2 = hypothesis_tracker.add_hypothesis("Group B", competition_group="phenomenon-b")
    hypothesis_tracker.evaluate_evidence(h1, 1, "consistent", assessed_by="test")
    hypothesis_tracker.evaluate_evidence(h2, 1, "inconsistent", assessed_by="test")

    listed = hypothesis_tracker.list_hypotheses(competition_group="phenomenon-a")
    matrix = hypothesis_tracker.get_ach_matrix(competition_group="phenomenon-a")
    ranked = hypothesis_tracker.compete_hypotheses(competition_group="phenomenon-a")

    assert [h["id"] for h in listed] == [h1]
    assert [h["id"] for h in matrix["hypotheses"]] == [h1]
    assert [h["id"] for h in ranked] == [h1]


def test_list_filters_hypotheses_by_thread_profile(ach_db, monkeypatch, capsys):
    db = hypothesis_tracker.get_hypothesis_db()
    db.executemany(
        "INSERT INTO investigation_threads (title, profile_id) VALUES (?, ?)",
        [("Alpha thread", "alpha"), ("Beta thread", "beta")],
    )
    thread_ids = [
        row["id"]
        for row in db.execute(
            "SELECT id FROM investigation_threads ORDER BY id DESC LIMIT 2"
        ).fetchall()[::-1]
    ]
    db.commit()
    db.close()

    alpha = hypothesis_tracker.add_hypothesis("Alpha hypothesis", thread_id=thread_ids[0])
    hypothesis_tracker.add_hypothesis("Beta hypothesis", thread_id=thread_ids[1])

    assert [
        row["id"] for row in hypothesis_tracker.list_hypotheses(profile_id="alpha")
    ] == [alpha]

    monkeypatch.setattr(
        "sys.argv",
        ["hypothesis_tracker.py", "list", "--profile", "alpha"],
    )
    hypothesis_tracker.main()
    output = capsys.readouterr().out
    assert "Alpha hypothesis" in output
    assert "Beta hypothesis" not in output


def test_null_hypothesis_is_labeled_in_all_ach_views(ach_db, monkeypatch, capsys):
    h0 = hypothesis_tracker.add_hypothesis(
        "Routine overlap", competition_group="overlap", is_null_hypothesis=True
    )
    hypothesis = hypothesis_tracker.get_hypothesis(h0)

    assert hypothesis["is_null_hypothesis"] == 1
    assert "[H0]" in hypothesis_tracker._format_hypothesis(hypothesis)

    for command in (
        ["list", "--competition-group", "overlap"],
        ["show", str(h0)],
        ["matrix", "--competition-group", "overlap"],
        ["compete", "--competition-group", "overlap"],
    ):
        monkeypatch.setattr("sys.argv", ["hypothesis_tracker.py", *command])
        hypothesis_tracker.main()
        assert "[H0]" in capsys.readouterr().out


def test_diagnosticity_classifies_rows_and_counts_per_hypothesis(ach_db):
    h1 = hypothesis_tracker.add_hypothesis("Coordination", competition_group="timing")
    h0 = hypothesis_tracker.add_hypothesis(
        "Coincidence", competition_group="timing", is_null_hypothesis=True
    )
    for hypothesis_id in (h1, h0):
        hypothesis_tracker.evaluate_evidence(
            hypothesis_id, 1, "consistent", assessed_by="test"
        )
    hypothesis_tracker.evaluate_evidence(h1, 2, "consistent", assessed_by="test")
    hypothesis_tracker.evaluate_evidence(h0, 2, "inconsistent", assessed_by="test")

    matrix = hypothesis_tracker.get_ach_matrix(competition_group="timing")

    assert matrix["diagnosticity"] == {"1": "non_diagnostic", "2": "diagnostic"}
    assert {h["id"]: h["diagnostic_evidence"] for h in matrix["hypotheses"]} == {
        h1: 1,
        h0: 1,
    }


def test_legacy_no_group_path_includes_all_active_hypotheses(ach_db):
    ungrouped = hypothesis_tracker.add_hypothesis("Legacy hypothesis")
    grouped = hypothesis_tracker.add_hypothesis("New hypothesis", competition_group="new-set")

    matrix = hypothesis_tracker.get_ach_matrix()
    ranked = hypothesis_tracker.compete_hypotheses()

    assert {h["id"] for h in matrix["hypotheses"]} == {ungrouped, grouped}
    assert {h["id"] for h in ranked} == {ungrouped, grouped}


def test_remove_evaluation_is_atomic_and_audited(ach_db):
    hypothesis_id = hypothesis_tracker.add_hypothesis("Correction candidate")
    hypothesis_tracker.evaluate_evidence(
        hypothesis_id,
        1,
        "inconsistent",
        assessed_by="mistaken-agent",
        notes="Wrong finding selected",
    )

    removed = hypothesis_tracker.remove_evaluation(
        hypothesis_id,
        1,
        assessed_by="mistaken-agent",
        reason="Assessment was attached to the wrong finding",
        removed_by="reviewer",
    )

    assert removed["assessment"] == "inconsistent"
    db = hypothesis_tracker.get_hypothesis_db()
    assert db.execute(
        "SELECT COUNT(*) FROM hypothesis_evidence_matrix "
        "WHERE hypothesis_id = ? AND finding_id = ?",
        (hypothesis_id, 1),
    ).fetchone()[0] == 0
    correction = db.execute(
        "SELECT * FROM corrections "
        "WHERE table_name = 'hypothesis_evidence_matrix'"
    ).fetchone()
    db.close()
    assert correction["record_id"] == removed["id"]
    assert correction["record_key"] == f"{hypothesis_id}:1:mistaken-agent"
    assert json.loads(correction["old_value"])["notes"] == "Wrong finding selected"
    assert correction["reason"] == "Assessment was attached to the wrong finding"
    assert correction["corrected_by"] == "reviewer"
    assert correction["correction_type"] == "retraction"
