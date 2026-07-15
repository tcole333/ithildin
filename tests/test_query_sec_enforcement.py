from __future__ import annotations

import argparse
import json
import sqlite3

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
