from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

import pytest


def _db(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def test_methodology_list_can_select_oldest_records(tmp_path, monkeypatch):
    from tools import lead_tracker, methodology_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(methodology_tracker, "get_db", lead_tracker.get_db)

    first = methodology_tracker.add_observation("friction", "first")
    second = methodology_tracker.add_observation("friction", "second")

    rows = methodology_tracker.list_observations(
        category="friction", status="open", limit=1, oldest_first=True
    )
    assert [row["id"] for row in rows] == [first]
    assert second > first


def test_claim_cli_records_agent_attribution(tmp_path, monkeypatch):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_id = lead_tracker.add_lead("Attribution test")
    monkeypatch.setattr(
        sys, "argv", ["lead_tracker.py", "claim", str(lead_id), "--agent", "agent-a"]
    )

    lead_tracker.main()

    db = lead_tracker.get_db()
    row = db.execute(
        "SELECT status, claimed_by FROM leads WHERE id = ?", (lead_id,)
    ).fetchone()
    db.close()
    assert tuple(row) == ("in_progress", "agent-a")


def test_edgar_lookup_writes_structured_output(tmp_path, monkeypatch, capsys):
    from tools import query_edgar

    atom = b"""<?xml version='1.0'?>
    <feed xmlns='http://www.w3.org/2005/Atom'><entry><content>
      <company-info><cik>42</cik><name>ACME PERSON</name><sic>1234</sic>
      <state-of-incorporation>NY</state-of-incorporation></company-info>
    </content></entry></feed>"""

    def fake_request(url, params=None, accept="application/json"):
        if url.endswith("company_tickers.json"):
            return {
                "0": {"cik_str": 1, "ticker": "ACME", "title": "ACME INC"},
                "1": {"cik_str": 1, "ticker": "ACM", "title": "ACME INC"},
            }
        if url == query_edgar.EFTS_URL:
            return {
                "hits": {"total": {"value": 3}},
                "aggregations": {
                    "entity_filter": {
                        "buckets": [{"key": "ACME INC (CIK 1)", "doc_count": 3}]
                    }
                },
            }
        return atom

    monkeypatch.setattr(query_edgar, "_request", fake_request)
    output = tmp_path / "lookup.json"
    query_edgar.cmd_lookup(
        argparse.Namespace(name=["Acme"], output=str(output), json_out=False)
    )

    payload = json.loads(output.read_text())
    assert payload["public_companies"][0] == {
        "cik": "0000000001",
        "title": "ACME INC",
        "tickers": ["ACME", "ACM"],
    }
    assert payload["registered_entities"][0]["cik"] == "0000000042"
    assert capsys.readouterr().out.count("\n") == 1


def test_fbi_search_writes_json_output(tmp_path, monkeypatch, capsys):
    from tools import ingest_fbi_files

    db_path = tmp_path / "fbi.db"
    db = _db(db_path)
    db.executescript("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, bates_number TEXT, efta_id TEXT,
            char_count INTEGER, word_count INTEGER, confidence REAL, text TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            bates_number, text, content=documents, content_rowid=id
        );
        INSERT INTO documents VALUES (1, 'EFTA1', 'EFTA1', 11, 2, 0.9, 'hello world');
        INSERT INTO documents_fts(documents_fts) VALUES ('rebuild');
    """)
    db.close()
    monkeypatch.setattr(ingest_fbi_files, "DB_PATH", db_path)
    output = tmp_path / "fbi.json"

    ingest_fbi_files.cmd_search(
        argparse.Namespace(
            query="hello", limit=5, min_chars=None,
            output=str(output), json_out=False,
        )
    )

    assert json.loads(output.read_text())[0]["bates_number"] == "EFTA1"
    assert capsys.readouterr().out.count("\n") == 1


def test_fbi_search_json_stdout_has_no_human_prefix(
    tmp_path, monkeypatch, capsys
):
    from tools import ingest_fbi_files

    db_path = tmp_path / "fbi.db"
    db = _db(db_path)
    db.executescript("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, bates_number TEXT, efta_id TEXT,
            char_count INTEGER, word_count INTEGER, confidence REAL, text TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            bates_number, text, content=documents, content_rowid=id
        );
        INSERT INTO documents VALUES (1, 'EFTA1', 'EFTA1', 11, 2, 0.9, 'hello world');
        INSERT INTO documents_fts(documents_fts) VALUES ('rebuild');
    """)
    db.close()
    monkeypatch.setattr(ingest_fbi_files, "DB_PATH", db_path)

    ingest_fbi_files.cmd_search(
        argparse.Namespace(
            query="absent", limit=5, min_chars=None,
            output=None, json_out=True,
        )
    )

    assert json.loads(capsys.readouterr().out) == []


def test_lobbyist_zero_results_honors_output(tmp_path, monkeypatch, capsys):
    from tools import query_lobbying

    monkeypatch.setattr(
        query_lobbying, "_fetch", lambda endpoint, params=None: {"results": []}
    )
    monkeypatch.setattr(
        query_lobbying,
        "_paginate",
        lambda endpoint, params, max_results=100: ([], 0),
    )
    monkeypatch.setattr(query_lobbying, "_log", lambda *args: None)
    output = tmp_path / "lobbyist.json"

    query_lobbying.cmd_lobbyist(
        argparse.Namespace(
            query="Nobody Here", limit=20,
            output=str(output), json_out=False,
        )
    )

    assert json.loads(output.read_text()) == []
    assert capsys.readouterr().out.count("\n") == 1


def test_pursue_lead_specific_id_uses_supported_show_command():
    skill = (
        Path(__file__).parents[1]
        / ".codex/skills/pursue-lead/SKILL.md"
    ).read_text()

    assert "uv run python tools/lead_tracker.py show " in skill
    assert "lead_tracker.py search --id" not in skill


def test_agent_guidance_warns_about_zsh_currency_and_status_parameter():
    root = Path(__file__).parents[1]
    for filename in ("AGENTS.md", "CLAUDE.md"):
        guidance = (root / filename).read_text()
        assert "zsh expands dollar-prefixed values" in guidance
        assert "exit_code=$?" in guidance
        assert "tools.env_loader.load_env_file()" in guidance


def test_fbi_search_treats_email_punctuation_as_literal(tmp_path, monkeypatch):
    from tools import ingest_fbi_files

    db_path = tmp_path / "fbi.db"
    db = _db(db_path)
    db.executescript("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, bates_number TEXT, efta_id TEXT,
            char_count INTEGER, word_count INTEGER, confidence REAL, text TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            bates_number, text, content=documents, content_rowid=id
        );
        INSERT INTO documents VALUES (
            1, 'EFTA1', 'EFTA1', 28, 2, 0.9, 'Contact p.selana@yahoo.com'
        );
        INSERT INTO documents_fts(documents_fts) VALUES ('rebuild');
    """)
    db.close()
    monkeypatch.setattr(ingest_fbi_files, "DB_PATH", db_path)
    output = tmp_path / "fbi-email.json"

    ingest_fbi_files.cmd_search(
        argparse.Namespace(
            query="p.selana@yahoo.com", limit=5, min_chars=None,
            output=str(output), json_out=False,
        )
    )

    assert json.loads(output.read_text())[0]["bates_number"] == "EFTA1"


def test_house_20k_search_treats_dotted_name_as_literal(tmp_path, monkeypatch):
    from tools import ingest_epstein_20k

    db_path = tmp_path / "house-20k.db"
    db = _db(db_path)
    db.executescript("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, filename TEXT, house_oversight_id TEXT,
            source_prefix TEXT, char_count INTEGER, word_count INTEGER, text TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            filename, text, content=documents, content_rowid=id
        );
        INSERT INTO documents VALUES (
            1, 'doc.txt', 'HOUSE_OVERSIGHT_1', 'TEXT-001', 12, 3,
            'Brad S. Karp'
        );
        INSERT INTO documents_fts(documents_fts) VALUES ('rebuild');
    """)
    db.close()
    monkeypatch.setattr(ingest_epstein_20k, "DB_PATH", db_path)
    output = tmp_path / "house-20k-name.json"

    ingest_epstein_20k.cmd_search(
        argparse.Namespace(
            query="Brad S. Karp", limit=5, prefix=None, min_chars=None,
            output=str(output), json_out=False,
        )
    )

    assert json.loads(output.read_text())[0]["house_oversight_id"] == (
        "HOUSE_OVERSIGHT_1"
    )


def test_kabasshouse_zero_match_entity_lookup_succeeds(tmp_path, monkeypatch, capsys):
    from tools import ingest_kabasshouse

    db_path = tmp_path / "kabass.db"
    db = _db(db_path)
    db.execute(
        "CREATE TABLE entities (entity_type TEXT, value TEXT, normalized_value TEXT)"
    )
    db.close()
    monkeypatch.setattr(ingest_kabasshouse, "DB_PATH", db_path)

    ingest_kabasshouse.cmd_entity(
        argparse.Namespace(name="not-present", limit=10)
    )

    assert capsys.readouterr().out == "Entity matches for 'not-present': 0\n"


def test_crtsh_timeout_is_reported_without_traceback(monkeypatch, capsys):
    from tools import query_crtsh

    monkeypatch.setattr(query_crtsh.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(
        query_crtsh, "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(TimeoutError()),
    )

    with pytest.raises(SystemExit) as exc:
        query_crtsh._fetch({"q": "example.com"}, timeout=7)

    assert exc.value.code == 1
    error = capsys.readouterr().err
    assert error.count("WARNING: crt.sh attempt") == 2
    assert "ERROR: crt.sh query failed after 3 attempts" in error
    assert "timeout after 7s" in error
    assert "Traceback" not in error
