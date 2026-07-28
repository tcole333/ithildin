from __future__ import annotations

import argparse
import sqlite3

from tools import ingest_kabasshouse


def test_entity_groups_normalized_values_and_keeps_distinct_raw_fallbacks(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "kabasshouse.db"
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE entities (
            entity_type TEXT,
            value TEXT,
            normalized_value TEXT
        );
        INSERT INTO entities VALUES
            ('PERSON', 'Alice Raw', NULL),
            ('PERSON', 'Alice Variant', NULL),
            ('ORG', 'Acme, Inc.', 'acme'),
            ('ORG', 'Acme Incorporated', 'acme');
        """
    )
    db.close()
    monkeypatch.setattr(ingest_kabasshouse, "DB_PATH", db_path)

    ingest_kabasshouse.cmd_entity(argparse.Namespace(name="Alice", limit=10))
    raw_output = capsys.readouterr().out
    assert "[PERSON] Alice Raw  x1" in raw_output
    assert "[PERSON] Alice Variant  x1" in raw_output

    ingest_kabasshouse.cmd_entity(argparse.Namespace(name="Acme", limit=10))
    normalized_output = capsys.readouterr().out
    assert normalized_output == (
        "Entity matches for 'Acme': 1\n"
        "  [ORG] acme  x2\n"
    )
