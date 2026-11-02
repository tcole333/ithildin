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
    registry = tmp_path / "registry.db"
    db = sqlite3.connect(registry)
    query_registry._ensure_schema(db)
    db.close()
    monkeypatch.setattr(query_registry, "DB_PATH", registry)
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
