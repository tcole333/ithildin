from __future__ import annotations

import argparse
import json
import sqlite3

from tools import query_registry


def test_ucc_party_zero_results_write_requested_output(
    monkeypatch,
    tmp_path,
    capsys,
):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE ucc_filings (
            id INTEGER PRIMARY KEY,
            filing_number TEXT,
            filing_type TEXT,
            filing_date TEXT,
            status TEXT,
            source_jurisdiction TEXT
        );
        CREATE TABLE ucc_debtors (
            id INTEGER PRIMARY KEY,
            filing_id INTEGER,
            debtor_name TEXT,
            address TEXT,
            city TEXT,
            state TEXT
        );
        """
    )
    monkeypatch.setattr(query_registry, "get_db", lambda: db)
    output = tmp_path / "ucc-party.json"

    query_registry.cmd_ucc_party(
        argparse.Namespace(
            name="Allbirds",
            role="debtor",
            limit=20,
            output=str(output),
            json_out=False,
        )
    )

    assert json.loads(output.read_text()) == []
    assert "0 results" in capsys.readouterr().out
    db.close()
