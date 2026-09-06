import argparse
import json
import sqlite3
import sys

from tools import fl_sunbiz_recheck, ingest_florida


def _empty_registry():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE registry_entities (
            id INTEGER PRIMARY KEY,
            source_id TEXT,
            source_jurisdiction TEXT,
            entity_name TEXT,
            entity_type TEXT,
            status TEXT,
            formation_date TEXT,
            dissolution_date TEXT,
            ein TEXT,
            principal_address TEXT,
            principal_city TEXT,
            principal_state TEXT,
            principal_zip TEXT
        )
    """)
    return db


def test_sunbiz_recheck_zero_result_search_writes_requested_output(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "nested" / "sunbiz.json"
    monkeypatch.setattr(fl_sunbiz_recheck, "get_db", _empty_registry)

    fl_sunbiz_recheck.cmd_search_single(
        argparse.Namespace(
            query="Pivotal Organization LLC",
            limit=20,
            output=str(output),
            json_out=False,
        )
    )

    assert json.loads(output.read_text()) == {
        "query": "Pivotal Organization LLC",
        "results": [],
    }
    captured = capsys.readouterr()
    assert captured.out.count("\n") == 1
    assert "0 results" in captured.out


def test_ingest_florida_search_cli_accepts_output_and_writes_zero_results(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "florida.json"
    monkeypatch.setattr(ingest_florida, "get_db", _empty_registry)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ingest_florida.py",
            "search",
            "GEO CORRECTIONS HOLDINGS",
            "--output",
            str(output),
        ],
    )

    ingest_florida.main()

    assert json.loads(output.read_text()) == {
        "query": "GEO CORRECTIONS HOLDINGS",
        "results": [],
    }
    captured = capsys.readouterr()
    assert captured.out.count("\n") == 1
    assert "0 results" in captured.out
