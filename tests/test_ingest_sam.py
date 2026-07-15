"""Regression tests for the local SAM.gov bulk-data query tool."""

from __future__ import annotations

import json
from types import SimpleNamespace

from tools import ingest_sam


def test_exclusion_search_treats_punctuation_as_literal(monkeypatch, tmp_path):
    db_path = tmp_path / "sam.db"
    output = tmp_path / "exclusions.json"
    monkeypatch.setattr(ingest_sam, "DB_PATH", db_path)

    db = ingest_sam.get_db()
    db.execute(
        "INSERT INTO sam_exclusions (classification, name) VALUES (?, ?)",
        ("Firm", "B.I. INCORPORATED"),
    )
    db.execute("INSERT INTO sam_exclusions_fts(sam_exclusions_fts) VALUES('rebuild')")
    db.commit()
    db.close()

    args = SimpleNamespace(
        query="B.I.",
        limit=20,
        output=str(output),
        json_out=False,
    )

    ingest_sam.cmd_exclusion(args)

    result = json.loads(output.read_text())
    assert result["count"] == 1
    assert result["exclusions"][0]["name"] == "B.I. INCORPORATED"


def test_entity_search_handles_legal_name_with_and_and_comma(monkeypatch, tmp_path):
    db_path = tmp_path / "sam.db"
    output = tmp_path / "entities.json"
    monkeypatch.setattr(ingest_sam, "DB_PATH", db_path)

    db = ingest_sam.get_db()
    db.execute(
        "INSERT INTO sam_entities (legal_business_name, uei, cage_code) VALUES (?, ?, ?)",
        ("GEO CORRECTIONS AND DETENTION, LLC", "TESTUEI00001", "T1234"),
    )
    db.execute("INSERT INTO sam_entities_fts(sam_entities_fts) VALUES('rebuild')")
    db.commit()
    db.close()

    args = SimpleNamespace(
        query="GEO Corrections and Detention, LLC",
        limit=20,
        output=str(output),
        json_out=False,
    )

    ingest_sam.cmd_entity(args)

    result = json.loads(output.read_text())
    assert result["count"] == 1
    assert result["entities"][0]["uei"] == "TESTUEI00001"
