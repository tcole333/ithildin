from __future__ import annotations

import argparse
import json
import sqlite3

import pytest


def _db(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def test_literal_fts_query_handles_email_and_domain_punctuation(tmp_path, monkeypatch):
    from tools import query_doj, query_lmsband, query_unified
    from tools.fts_query import literal_fts_query

    email = "ch.communication.sa@gmail.com"
    assert literal_fts_query(email) == '"ch.communication.sa@gmail.com"'
    assert literal_fts_query('"exact phrase"') == '"exact phrase"'
    assert literal_fts_query("alpha OR beta") == "alpha OR beta"
    assert literal_fts_query("GEO Corrections and Detention, LLC") == (
        '"GEO" "Corrections" "and" "Detention," "LLC"'
    )
    assert query_lmsband._fts_query(email) == '"ch.communication.sa@gmail.com"'

    doj_path = tmp_path / "doj.db"
    db = _db(doj_path)
    db.executescript("""
        CREATE TABLE documents (bates_id TEXT, page_count INTEGER, word_count INTEGER, ocr_text TEXT);
        CREATE VIRTUAL TABLE documents_fts USING fts5(bates_id, ocr_text, content=documents, content_rowid=rowid);
        INSERT INTO documents VALUES ('EFTA1', 1, 3, 'Contact ch.communication.sa@gmail.com today');
        INSERT INTO documents_fts(documents_fts) VALUES ('rebuild');
    """)
    db.close()
    monkeypatch.setattr(query_doj, "DB_PATH", str(doj_path))
    assert query_doj.search(email, limit=5)[0]["bates_id"] == "EFTA1"
    assert query_doj.count_matches(email) == 1

    unified_path = tmp_path / "unified.db"
    db = _db(unified_path)
    db.executescript("""
        CREATE TABLE emails (
            id INTEGER PRIMARY KEY, source_dataset TEXT, from_address TEXT,
            to_address TEXT, subject TEXT, timestamp_iso TEXT, body TEXT
        );
        CREATE VIRTUAL TABLE emails_fts USING fts5(
            from_address, to_address, subject, body, content=emails, content_rowid=id
        );
        INSERT INTO emails VALUES (1, 'test', 'ch.communication.sa@gmail.com', 'x@example.com', 'Hello', '2020-01-01', 'Body');
        INSERT INTO emails_fts(emails_fts) VALUES ('rebuild');
    """)
    db.close()
    monkeypatch.setattr(query_unified, "DB_PATH", unified_path)
    assert query_unified.search_emails(email, limit=5)[0]["id"] == 1

    lmsband_path = tmp_path / "lmsband.db"
    db = _db(lmsband_path)
    db.executescript("""
        CREATE VIRTUAL TABLE text_fts USING fts5(filename, dataset, text);
        CREATE TABLE text_cache (file_id INTEGER, char_count INTEGER, method TEXT);
        INSERT INTO text_fts(filename, dataset, text)
        VALUES ('email.txt', '10', 'Contact ch.communication.sa@gmail.com today');
        INSERT INTO text_cache VALUES (1, 48, 'test');
    """)
    db.close()
    monkeypatch.setattr(query_lmsband, "DB_PATH", lmsband_path)
    assert query_lmsband.text_search(email, limit=5)[0]["filename"] == "email.txt"


def test_corpus_searches_write_json_output(tmp_path, monkeypatch):
    from tools import ingest_epstein_20k, ingest_kabasshouse

    kabass_path = tmp_path / "kabass.db"
    db = _db(kabass_path)
    db.executescript("""
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, file_key TEXT, dataset TEXT, document_type TEXT,
            date TEXT, ocr_source TEXT, char_count INTEGER, full_text TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            file_key, full_text, content=documents, content_rowid=rowid
        );
        INSERT INTO documents VALUES ('1', 'EFTA1', '10', 'email', '2020-01-01', 'ocr', 11, 'hello world');
        INSERT INTO documents_fts(documents_fts) VALUES ('rebuild');
    """)
    db.close()
    monkeypatch.setattr(ingest_kabasshouse, "DB_PATH", kabass_path)
    kabass_output = tmp_path / "kabass.json"
    ingest_kabasshouse.cmd_search(argparse.Namespace(
        query="hello", limit=5, dataset=None, min_chars=None,
        json_out=False, output=str(kabass_output),
    ))
    assert json.loads(kabass_output.read_text())[0]["file_key"] == "EFTA1"

    epstein_path = tmp_path / "epstein.db"
    db = _db(epstein_path)
    db.executescript("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, filename TEXT, house_oversight_id TEXT,
            source_prefix TEXT, char_count INTEGER, word_count INTEGER, text TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            filename, text, content=documents, content_rowid=id
        );
        INSERT INTO documents VALUES (1, 'doc.txt', 'HOUSE_OVERSIGHT_1', 'TEXT-001', 11, 2, 'hello world');
        INSERT INTO documents_fts(documents_fts) VALUES ('rebuild');
    """)
    db.close()
    monkeypatch.setattr(ingest_epstein_20k, "DB_PATH", epstein_path)
    epstein_output = tmp_path / "epstein.json"
    ingest_epstein_20k.cmd_search(argparse.Namespace(
        query="hello", limit=5, prefix=None, min_chars=None,
        json_out=False, output=str(epstein_output),
    ))
    assert json.loads(epstein_output.read_text())[0]["house_oversight_id"] == "HOUSE_OVERSIGHT_1"


def test_profile_thread_mapping_exposes_global_ids(monkeypatch):
    from tools import investigation_context

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE investigation_threads (id INTEGER, title TEXT, profile_id TEXT)")
    db.execute("INSERT INTO investigation_threads VALUES (81, 'Core', 'sample')")
    monkeypatch.setattr(investigation_context, "_get_read_db", lambda: db)
    profile = investigation_context.InvestigationProfile(
        name="sample", primary_subject="Subject", threads=[{"id": 1, "name": "Core"}]
    )
    assert investigation_context.get_global_thread_ids(profile) == {1: 81}


def test_active_profile_read_does_not_contend_with_an_open_writer(
    tmp_path, monkeypatch
):
    from tools import investigation_context

    db_path = tmp_path / "investigation.db"
    setup = sqlite3.connect(db_path)
    setup.execute("PRAGMA journal_mode=WAL")
    setup.execute(
        "CREATE TABLE investigation_config "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    setup.execute(
        "INSERT INTO investigation_config VALUES ('active_profile', 'sample')"
    )
    setup.commit()

    writer = sqlite3.connect(db_path)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute(
        "UPDATE investigation_config SET value = 'uncommitted' "
        "WHERE key = 'active_profile'"
    )
    monkeypatch.setattr(investigation_context, "DB_PATH", db_path)

    try:
        assert investigation_context.get_active_profile_name() == "sample"
    finally:
        writer.rollback()
        writer.close()
        setup.close()


def test_log_search_validates_registered_session(tmp_path, monkeypatch):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    session_id = db.execute("INSERT INTO sessions (agent_id) VALUES ('test')").lastrowid
    db.commit()
    db.close()

    with pytest.raises(ValueError, match="sessions table"):
        lead_tracker.log_search("query", "source", 0, session_id="lead-123")
    with pytest.raises(ValueError, match="not registered"):
        lead_tracker.log_search("query", "source", 0, session_id=9999)

    lead_tracker.log_search("query", "source", 1, session_id=session_id)
    db = lead_tracker.get_db()
    row = db.execute("SELECT session_id FROM search_log WHERE query_text='query'").fetchone()
    assert row["session_id"] == session_id
    db.close()


def test_profile_stats_label_unscoped_search_totals_global(tmp_path, monkeypatch):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_tracker.log_search("query", "source", 1)

    stats = lead_tracker.get_stats(profile_id="test")

    assert stats["profile_id"] == "test"
    assert stats["total_searches"] == 1
    assert stats["search_scope"] == "global"


def test_lead_stats_recent_completion_excludes_other_terminal_statuses(
    tmp_path, monkeypatch
):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    completed = lead_tracker.add_lead("Completed lead", profile_id="test")
    dead_end = lead_tracker.add_lead("Dead-end lead", profile_id="test")
    db = lead_tracker.get_db()
    db.execute(
        "UPDATE leads SET status = 'completed', completed_at = datetime('now') "
        "WHERE id = ?",
        (completed,),
    )
    db.execute(
        "UPDATE leads SET status = 'dead_end', completed_at = datetime('now') "
        "WHERE id = ?",
        (dead_end,),
    )
    db.commit()
    db.close()

    assert lead_tracker.get_stats(profile_id="test")["recently_completed"] == 1


def test_lead_search_accepts_a_result_limit(tmp_path, monkeypatch):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_tracker.add_lead("Needle alpha", profile_id="test")
    lead_tracker.add_lead("Needle beta", profile_id="test")

    assert len(lead_tracker.search_leads("Needle", profile_id="test", limit=1)) == 1


def test_lead_evidence_classifies_https_before_file_paths(tmp_path, monkeypatch):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    url = "https://www.courtlistener.com/api/rest/v4/documents/123/"
    lead_id = lead_tracker.add_lead(
        "URL evidence lead",
        profile_id="test",
        evidence=[url],
    )

    evidence = lead_tracker.get_lead(lead_id)["evidence"]
    assert [(row["evidence_type"], row["evidence_ref"]) for row in evidence] == [
        ("url", url)
    ]


def test_existing_lead_can_be_assigned_to_a_profile_thread(tmp_path, monkeypatch):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_id = lead_tracker.add_lead("Unthreaded lead", profile_id="test")
    db = lead_tracker.get_db()
    thread_id = db.execute(
        "INSERT INTO investigation_threads (title, profile_id) VALUES (?, ?)",
        ("Test thread", "test"),
    ).lastrowid
    db.commit()
    db.close()

    assert lead_tracker.assign_lead_thread(lead_id, thread_id)
    assigned = lead_tracker.get_lead(lead_id)
    assert assigned["thread_id"] == thread_id
    assert any("Assigned to investigation thread" in note["note"] for note in assigned["notes"])


def test_block_lead_preserves_structured_stop_reason(tmp_path, monkeypatch):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_id = lead_tracker.add_lead("Await a nonpublic filing", profile_id="test")

    lead_tracker.block_lead(lead_id, "The filing is not public until 2027-01-15")

    db = lead_tracker.get_db()
    lead = db.execute(
        "SELECT status, stop_reason FROM leads WHERE id = ?",
        (lead_id,),
    ).fetchone()
    note = db.execute(
        "SELECT note FROM lead_notes WHERE lead_id = ? ORDER BY id DESC LIMIT 1",
        (lead_id,),
    ).fetchone()
    assert tuple(lead) == ("blocked", "The filing is not public until 2027-01-15")
    assert note["note"] == "BLOCKED: The filing is not public until 2027-01-15"
    db.close()


def test_reopen_lead_clears_stale_claim_and_block_state(tmp_path, monkeypatch):
    from tools import lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_id = lead_tracker.add_lead("Reopen a closed lead", profile_id="test")
    db = lead_tracker.get_db()
    db.execute(
        """
        UPDATE leads
        SET status = 'blocked',
            claimed_by = 'stale-agent',
            claimed_at = '2026-01-01T00:00:00',
            lease_until = '2026-01-01T02:00:00',
            completed_at = '2026-01-01T03:00:00',
            stop_reason = 'Waiting on access',
            blocked_by_infra_id = NULL
        WHERE id = ?
        """,
        (lead_id,),
    )
    db.commit()
    db.close()

    lead_tracker.reopen_lead(lead_id)

    reopened = lead_tracker.get_lead(lead_id)
    assert reopened["status"] == "open"
    for field in (
        "claimed_by",
        "claimed_at",
        "lease_until",
        "completed_at",
        "stop_reason",
        "blocked_by_infra_id",
    ):
        assert reopened[field] is None


def test_infra_block_preserves_structured_stop_reason(tmp_path, monkeypatch):
    from tools import infra_tracker, lead_tracker

    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_id = lead_tracker.add_lead("Await registry access", profile_id="test")
    infra_id = infra_tracker.add_request(
        "Authenticated registry lookup",
        "new_source",
        "Obtain the official filing behind a login",
    )

    infra_tracker.block_lead_on_infra(lead_id, infra_id, "Login approval is pending")

    db = lead_tracker.get_db()
    lead = db.execute(
        "SELECT status, blocked_by_infra_id, stop_reason FROM leads WHERE id = ?",
        (lead_id,),
    ).fetchone()
    assert tuple(lead) == (
        "blocked",
        infra_id,
        f"Waiting on infra request #{infra_id} — Login approval is pending",
    )
    db.close()


def test_findings_search_limit_and_date_correction_stay_consistent(tmp_path, monkeypatch):
    from tools import findings_tracker, lead_tracker

    db_path = tmp_path / "investigation.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    db = lead_tracker.get_db()
    columns = {row["name"] for row in db.execute("PRAGMA table_info(findings)")}
    for name in ("event_date_iso", "date_precision"):
        if name not in columns:
            db.execute(f"ALTER TABLE findings ADD COLUMN {name} TEXT")
    db.commit()
    db.close()


def test_finding_correction_can_link_an_existing_lead(tmp_path, monkeypatch):
    from tools import findings_tracker, lead_tracker

    db_path = tmp_path / "investigation.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    db = lead_tracker.get_db()
    columns = {row["name"] for row in db.execute("PRAGMA table_info(findings)")}
    for name in ("event_date_iso", "date_precision"):
        if name not in columns:
            db.execute(f"ALTER TABLE findings ADD COLUMN {name} TEXT")
    lead_id = db.execute(
        "INSERT INTO leads (title, profile_id) VALUES (?, ?)",
        ("CourtListener universe", "test"),
    ).lastrowid
    db.commit()
    db.close()
    monkeypatch.setattr(findings_tracker, "_schema_initialized", True)

    finding_id = findings_tracker.add_finding(
        "Target",
        "Verified finding created before its lead link was supplied",
        source_datasets=["courtlistener"],
        evidence_ids=["COURTLISTENER:fixture-record"],
        source_quotes={"COURTLISTENER:fixture-record": {"quote": "The record identifies the subject."}},
        profile_id="test",
    )

    assert findings_tracker.update_finding(
        finding_id,
        "lead_id",
        lead_id,
        "Attach the source lead",
        corrected_by="test",
    )

    db = findings_tracker.get_db()
    row = db.execute(
        "SELECT lead_id FROM findings WHERE id = ?",
        (finding_id,),
    ).fetchone()
    correction = db.execute(
        """
        SELECT old_value, new_value
        FROM corrections
        WHERE table_name = 'findings' AND record_id = ? AND field_name = 'lead_id'
        """,
        (finding_id,),
    ).fetchone()
    assert row["lead_id"] == lead_id
    assert tuple(correction) == (None, str(lead_id))
    db.close()
    monkeypatch.setattr(findings_tracker, "_schema_initialized", True)

    ids = [
        findings_tracker.add_finding(
            f"Target {index}", "shared searchable phrase", date_of_event="2020",
            source_datasets=["web_search"], profile_id="test",
            evidence_ids=["https://example.gov/fixture-record"],
            source_quotes={"https://example.gov/fixture-record": {"quote": "The record identifies the subject."}},
        )
        for index in range(3)
    ]
    assert len(findings_tracker.search_findings("shared", all_profiles=True, limit=2)) == 2

    assert findings_tracker.update_finding(
        ids[0], "date_of_event", "March 2021", "Corrected month", corrected_by="test"
    )
    db = findings_tracker.get_db()
    row = db.execute(
        "SELECT date_of_event, event_date_iso, date_precision FROM findings WHERE id = ?",
        (ids[0],),
    ).fetchone()
    assert tuple(row) == ("March 2021", "2021-03-01", "month")
    db.close()


def _auto_lead_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY, name TEXT, jurisdiction TEXT,
            date_formed TEXT, created_at TEXT
        );
        CREATE TABLE entity_roles (entity_id INTEGER, person_name TEXT);
        CREATE TABLE auto_crossref_log (
            id INTEGER PRIMARY KEY, table_name TEXT, record_id INTEGER,
            crossref_type TEXT, lead_id INTEGER,
            UNIQUE(table_name, record_id, crossref_type)
        );
    """)
    return db


def test_filing_clusters_require_real_dates_and_unique_entities():
    from tools.auto_leads import process_filing_clusters

    db = _auto_lead_db()
    db.executemany(
        "INSERT INTO entities VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Election Transparency Initiative", "US", "2020-01-01", "2026-01-01"),
            (2, "Election Transparency Initiative", "DC", "2020-01-02", "2026-01-01"),
            (3, "No Date One", "US", None, "2026-01-01"),
            (4, "No Date Two", "US", None, "2026-01-01"),
        ],
    )
    db.executemany(
        "INSERT INTO entity_roles VALUES (?, 'Ken Cuccinelli')",
        [(1,), (2,), (3,), (4,)],
    )
    db.commit()
    assert process_filing_clusters(db, dry_run=True) == (0, 0)

    db.execute("INSERT INTO entities VALUES (5, 'Distinct Entity', 'DC', '2020-01-03', '2026-01-01')")
    db.execute("INSERT INTO entity_roles VALUES (5, 'Ken Cuccinelli')")
    db.commit()
    assert process_filing_clusters(db, dry_run=True) == (1, 1)
    db.close()
