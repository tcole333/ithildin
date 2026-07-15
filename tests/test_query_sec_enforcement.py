from __future__ import annotations

import argparse
import json
import sqlite3
import sys

import pytest

from tools import ingest_sec_enforcement, query_sec_enforcement


def _build_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        ingest_sec_enforcement.SCHEMA_SQL
        + ingest_sec_enforcement.FTS_SQL
        + ingest_sec_enforcement.FTS_TRIGGERS_SQL
    )
    db.executemany(
        """INSERT INTO enforcement_actions (
               release_number, source_type, date_published,
               respondent_text, release_url, file_number, body_text
           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                "LR-1",
                "litigation",
                "2024-01-02",
                "Brad S. Karp",
                "https://www.sec.gov/litigation/litreleases/lr-1",
                "1:24-cv-1",
                "The release names Brad S. Karp.",
            ),
            (
                "AAER-2",
                "aaer",
                "2024-01-01",
                "George C. Zoley",
                "https://www.sec.gov/enforcement-litigation/accounting-auditing/aaer-2",
                "3-2",
                "The release names George C. Zoley.",
            ),
            (
                "LR-3",
                "litigation",
                "2023-12-31",
                "Brad Jones",
                "https://www.sec.gov/litigation/litreleases/lr-3",
                "1:23-cv-3",
                "The release names Brad Jones.",
            ),
        ],
    )
    db.executemany(
        """INSERT INTO enforcement_defendants (
               action_id, name_raw, name_normalized, defendant_type
           ) VALUES (?, ?, ?, ?)""",
        [
            (1, "Brad S. Karp", "brad s karp", "person"),
            (2, "George C. Zoley", "george c zoley", "person"),
            (3, "Brad Jones", "brad jones", "person"),
        ],
    )
    db.commit()
    db.close()


def _args(output, query):
    return argparse.Namespace(
        query=query,
        source=None,
        start=None,
        end=None,
        limit=50,
        output=str(output),
        json_out=False,
    )


def test_search_treats_dotted_person_name_as_literal_terms(tmp_path, monkeypatch):
    db_path = tmp_path / "sec_enforcement.db"
    _build_db(db_path)
    monkeypatch.setattr(query_sec_enforcement, "DB_PATH", db_path)
    monkeypatch.setattr(query_sec_enforcement, "_log", lambda *args: None)
    output = tmp_path / "results.json"

    query_sec_enforcement.cmd_search(_args(output, "Brad S. Karp"))

    results = json.loads(output.read_text())
    assert [row["release_number"] for row in results] == ["LR-1"]


def test_search_preserves_explicit_fts_boolean_query(tmp_path, monkeypatch):
    db_path = tmp_path / "sec_enforcement.db"
    _build_db(db_path)
    monkeypatch.setattr(query_sec_enforcement, "DB_PATH", db_path)
    monkeypatch.setattr(query_sec_enforcement, "_log", lambda *args: None)
    output = tmp_path / "results.json"

    query_sec_enforcement.cmd_search(_args(output, "Karp OR Zoley"))

    results = json.loads(output.read_text())
    assert [row["release_number"] for row in results] == ["LR-1", "AAER-2"]


def test_cross_ref_is_exact_after_normalization(tmp_path, monkeypatch):
    db_path = tmp_path / "sec_enforcement.db"
    _build_db(db_path)
    monkeypatch.setattr(query_sec_enforcement, "DB_PATH", db_path)
    monkeypatch.setattr(
        query_sec_enforcement,
        "_gather_investigation_names",
        lambda: {
            "BRAD S. KARP": ("investigation_entity", 1),
            "Brad Karp": ("investigation_entity", 2),
        },
    )
    output = tmp_path / "cross-ref.json"

    query_sec_enforcement.cmd_cross_ref(
        argparse.Namespace(
            auto_leads=False,
            dry_run=True,
            output=str(output),
            json_out=False,
        )
    )

    results = json.loads(output.read_text())
    assert len(results) == 1
    assert results[0]["check_name"] == "BRAD S. KARP"
    assert results[0]["defendant_name"] == "Brad S. Karp"
    assert results[0]["match_type"] == "exact"
    assert results[0]["match_score"] == 1.0


def test_cross_ref_no_longer_advertises_ignored_threshold(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["query_sec_enforcement.py", "cross-ref", "--help"]
    )

    with pytest.raises(SystemExit) as exc:
        query_sec_enforcement.main()

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--threshold" not in help_text
    assert "exact normalized names" in help_text


def test_cross_ref_rejects_legacy_threshold_option(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["query_sec_enforcement.py", "cross-ref", "--threshold", "85"],
    )

    with pytest.raises(SystemExit) as exc:
        query_sec_enforcement.main()

    assert exc.value.code == 2
    assert "unrecognized arguments: --threshold 85" in capsys.readouterr().err
