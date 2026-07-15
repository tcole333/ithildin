import sqlite3
import sys

import pytest

from tools import findings_tracker
from tools.findings_tracker import (
    _classify_evidence_ref,
    _normalize_event_date,
    _parse_source_quote_args,
    verify_finding,
)


def _verification_db(monkeypatch, tmp_path):
    db_path = tmp_path / "verification.db"
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY,
            claim_type TEXT DEFAULT 'inference',
            source_datasets TEXT DEFAULT '["courtlistener"]',
            verification_status TEXT,
            verified_by TEXT,
            verified_at TEXT
        );
        CREATE TABLE finding_evidence (
            finding_id INTEGER,
            evidence_type TEXT DEFAULT 'ref',
            evidence_ref TEXT,
            source_quote TEXT
        );
        """
    )
    db.commit()
    db.close()
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", True)
    return db_path


def test_url_is_classified_before_path_separator():
    assert _classify_evidence_ref("https://example.gov/record/123") == "url"
    assert _classify_evidence_ref("data/case/record.pdf") == "file"
    assert _classify_evidence_ref("EFTA01315387") == "efta"


def test_source_quote_parser_preserves_colons_in_canonical_ref():
    evidence = ["FL-SunBiz:L10000130392"]
    parsed = _parse_source_quote_args(
        ["FL-SunBiz:L10000130392:BIER GARDEN LLC; RAMON L. COSCOLLUELA"],
        evidence,
    )
    assert parsed == {
        "FL-SunBiz:L10000130392": {
            "quote": "BIER GARDEN LLC; RAMON L. COSCOLLUELA",
        }
    }


def test_source_quote_parser_rejects_duplicate_quote_for_same_ref():
    evidence = ["COURTLISTENER:primary-record"]

    with pytest.raises(
        ValueError,
        match="Duplicate quote metadata for evidence 'COURTLISTENER:primary-record'",
    ):
        _parse_source_quote_args(
            [
                "COURTLISTENER:primary-record:first excerpt",
                "COURTLISTENER:primary-record:second excerpt",
            ],
            evidence,
        )


def test_correct_help_lists_source_datasets_and_json_value_format(
    monkeypatch, capsys
):
    monkeypatch.setattr(sys, "argv", ["findings_tracker.py", "correct", "--help"])

    with pytest.raises(SystemExit) as exc:
        findings_tracker.main()

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "source_datasets" in help_text
    assert "JSON array" in help_text


def test_normalize_event_date_populates_iso_and_precision():
    assert _normalize_event_date("2010-12-22") == ("2010-12-22", "day")
    assert _normalize_event_date(None) == (None, None)


def test_verify_rejects_evidence_without_source_quote(monkeypatch, tmp_path):
    db_path = _verification_db(monkeypatch, tmp_path)
    db = sqlite3.connect(db_path)
    db.execute("INSERT INTO findings (id, verification_status) VALUES (1, 'unverified')")
    db.execute(
        "INSERT INTO finding_evidence (finding_id, evidence_ref, source_quote) VALUES (1, ?, NULL)",
        ("COURTLISTENER:primary-record",),
    )
    db.commit()
    db.close()

    with pytest.raises(ValueError, match="missing source_quote.*COURTLISTENER:primary-record"):
        verify_finding(1, verified_by="test")

    db = sqlite3.connect(db_path)
    assert db.execute(
        "SELECT verification_status FROM findings WHERE id = 1"
    ).fetchone()[0] == "unverified"
    db.close()


def test_verify_accepts_only_fully_quoted_evidence(monkeypatch, tmp_path):
    db_path = _verification_db(monkeypatch, tmp_path)
    db = sqlite3.connect(db_path)
    db.execute("INSERT INTO findings (id, verification_status) VALUES (2, 'unverified')")
    db.executemany(
        "INSERT INTO finding_evidence (finding_id, evidence_ref, source_quote) VALUES (2, ?, ?)",
        [
            ("COURTLISTENER:record-a", "Exact source language A"),
            ("COURTLISTENER:record-b", "Exact source language B"),
        ],
    )
    db.commit()
    db.close()

    verify_finding(2, verified_by="test")

    db = sqlite3.connect(db_path)
    row = db.execute(
        "SELECT verification_status, verified_by, verified_at FROM findings WHERE id = 2"
    ).fetchone()
    assert row[0] == "verified"
    assert row[1] == "test"
    assert row[2]
    db.close()
