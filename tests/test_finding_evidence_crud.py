import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import findings_tracker, lead_tracker


@pytest.fixture
def evidence_db(tmp_path, monkeypatch):
    db_path = tmp_path / "evidence.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    yield db, db_path
    db.close()


def _add_draft(**kwargs):
    values = {
        "target_name": "Evidence Target",
        "summary": "Evidence summary",
        "source_datasets": ["courtlistener"],
        "profile_id": "test",
    }
    values.update(kwargs)
    return findings_tracker.add_finding(**values)


def test_schema_migrates_composite_record_key(evidence_db):
    db, _ = evidence_db
    columns = {row["name"] for row in db.execute("PRAGMA table_info(corrections)")}
    assert "record_key" in columns
    index = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' "
        "AND name='idx_corrections_table_record_key'"
    ).fetchone()
    assert "record_key" in index["sql"]


def test_new_findings_require_source_token_array_and_supported_tokens(evidence_db):
    db, _ = evidence_db
    with pytest.raises(ValueError, match="JSON-array-compatible"):
        _add_draft(source_datasets="courtlistener")
    with pytest.raises(ValueError, match="Unsupported source token"):
        _add_draft(source_datasets=["not_a_supported_source"])
    assert db.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0


def test_direct_quote_write_is_atomic_and_requires_quoted_evidence(evidence_db):
    db, _ = evidence_db
    with pytest.raises(ValueError, match="at least one evidence"):
        _add_draft(claim_type="direct_quote")
    with pytest.raises(ValueError, match="non-empty source_quote"):
        _add_draft(
            claim_type="direct_quote",
            evidence_ids=["COURTLISTENER:docket/123"],
        )
    assert db.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM finding_evidence").fetchone()[0] == 0


def test_http_refs_are_urls_and_canonical_slash_refs_are_not_files(evidence_db):
    db, _ = evidence_db
    url = "https://example.gov/records/123"
    url_id = _add_draft(
        claim_type="direct_quote",
        evidence_ids=[url],
        source_quotes={url: {"quote": "Exact remote source text"}},
    )
    canonical = "CourtListener:docket/69737684"
    canonical_id = _add_draft(evidence_ids=[canonical])
    rows = db.execute(
        "SELECT finding_id, evidence_type FROM finding_evidence ORDER BY finding_id"
    ).fetchall()
    assert [(row["finding_id"], row["evidence_type"]) for row in rows] == [
        (url_id, "url"),
        (canonical_id, "ref"),
    ]


def test_local_file_exists_and_resolvable_quote_span_matches(evidence_db, tmp_path):
    db, _ = evidence_db
    source = tmp_path / "record.txt"
    source.write_text("Before the exact source language after.", encoding="utf-8")
    finding_id = _add_draft(
        claim_type="direct_quote",
        evidence_ids=[str(source)],
        source_quotes={str(source): {"quote": "the exact source language"}},
    )
    assert db.execute(
        "SELECT evidence_type FROM finding_evidence WHERE finding_id = ?", (finding_id,)
    ).fetchone()[0] == "file"

    with pytest.raises(ValueError, match="failed exact quote validation"):
        _add_draft(
            target_name="Mismatch",
            claim_type="direct_quote",
            evidence_ids=[str(source)],
            source_quotes={str(source): {"quote": "words that are not present"}},
        )
    with pytest.raises(ValueError, match="does not exist"):
        _add_draft(evidence_ids=[str(tmp_path / "missing.pdf")])
    assert db.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 1


def test_evidence_crud_records_audit_and_invalidates_verification(evidence_db):
    db, _ = evidence_db
    finding_id = _add_draft()
    ref = "COURTLISTENER:docket/123"
    findings_tracker.add_finding_evidence(
        finding_id, ref, source_quote="Original exact language",
        reason="Attach primary record", corrected_by="tester",
    )
    added = db.execute(
        "SELECT * FROM corrections WHERE table_name='finding_evidence' "
        "AND record_id=? AND record_key=?",
        (finding_id, ref),
    ).fetchone()
    assert added["field_name"] == "__row__"
    assert added["old_value"] is None
    assert json.loads(added["new_value"])["source_quote"] == "Original exact language"

    findings_tracker.verify_finding(finding_id, verified_by="reviewer")
    findings_tracker.correct_finding_evidence(
        finding_id, ref, "source_quote", "Corrected exact language",
        reason="Correct transcription", corrected_by="tester",
    )
    finding = db.execute(
        "SELECT verification_status, verified_by, verified_at FROM findings WHERE id=?",
        (finding_id,),
    ).fetchone()
    assert tuple(finding) == ("unverified", None, None)
    corrected = db.execute(
        "SELECT old_value,new_value FROM corrections "
        "WHERE table_name='finding_evidence' AND record_id=? "
        "AND record_key=? AND field_name='source_quote'",
        (finding_id, ref),
    ).fetchone()
    assert tuple(corrected) == ("Original exact language", "Corrected exact language")

    findings_tracker.delete_finding_evidence(
        finding_id, ref, reason="Superseded record", corrected_by="tester"
    )
    assert db.execute(
        "SELECT COUNT(*) FROM finding_evidence WHERE finding_id=?", (finding_id,)
    ).fetchone()[0] == 0
    deleted = db.execute(
        "SELECT old_value,new_value,correction_type FROM corrections "
        "WHERE table_name='finding_evidence' AND record_id=? "
        "AND record_key=? AND field_name='__row__' ORDER BY id DESC LIMIT 1",
        (finding_id, ref),
    ).fetchone()
    assert json.loads(deleted["old_value"])["evidence_ref"] == ref
    assert deleted["new_value"] is None
    assert deleted["correction_type"] == "retraction"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email_sender", "Sender Name"),
        ("email_date", "2019-01-01"),
        ("chain_position", "1"),
    ],
)
def test_non_efta_evidence_rejects_efta_only_metadata_corrections(
    evidence_db, field, value
):
    db, _ = evidence_db
    ref = "COURTLISTENER:docket/123"
    finding_id = _add_draft(evidence_ids=[ref])

    with pytest.raises(ValueError, match=f"Cannot correct {field} on non-EFTA evidence"):
        findings_tracker.correct_finding_evidence(
            finding_id, ref, field, value,
            reason="Invalid metadata attempt", corrected_by="tester",
        )

    row = db.execute(
        "SELECT email_sender,email_date,chain_position FROM finding_evidence "
        "WHERE finding_id=? AND evidence_ref=?",
        (finding_id, ref),
    ).fetchone()
    assert tuple(row) == (None, None, None)
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE table_name='finding_evidence'"
    ).fetchone()[0] == 0


def test_efta_ref_reclassification_requires_audited_metadata_clears(evidence_db):
    db, _ = evidence_db
    finding_id = _add_draft()
    efta_ref = "EFTA00000001"
    url_ref = "https://example.gov/record/1"
    findings_tracker.add_finding_evidence(
        finding_id, efta_ref,
        email_sender="Sender Name", email_date="2019-01-01", chain_position=1,
        reason="Attach attributed email", corrected_by="tester",
    )

    with pytest.raises(ValueError, match="Clear each field first.*evidence-correct"):
        findings_tracker.correct_finding_evidence(
            finding_id, efta_ref, "evidence_ref", url_ref,
            reason="Replace source reference", corrected_by="tester",
        )
    unchanged = db.execute(
        "SELECT evidence_type,evidence_ref,email_sender,email_date,chain_position "
        "FROM finding_evidence WHERE finding_id=?",
        (finding_id,),
    ).fetchone()
    assert tuple(unchanged) == (
        "efta", efta_ref, "Sender Name", "2019-01-01", 1,
    )

    for field in ("email_sender", "email_date", "chain_position"):
        findings_tracker.correct_finding_evidence(
            finding_id, efta_ref, field, "",
            reason=f"Clear {field} before source reclassification", corrected_by="tester",
        )
    findings_tracker.correct_finding_evidence(
        finding_id, efta_ref, "evidence_ref", url_ref,
        reason="Reclassify after audited metadata clears", corrected_by="tester",
    )

    reclassified = db.execute(
        "SELECT evidence_type,evidence_ref,email_sender,email_date,chain_position "
        "FROM finding_evidence WHERE finding_id=?",
        (finding_id,),
    ).fetchone()
    assert tuple(reclassified) == ("url", url_ref, None, None, None)
    fields = db.execute(
        "SELECT field_name FROM corrections WHERE table_name='finding_evidence' "
        "AND record_id=? ORDER BY id",
        (finding_id,),
    ).fetchall()
    assert [row[0] for row in fields] == [
        "__row__", "email_sender", "email_date", "chain_position", "evidence_ref",
    ]


def test_delete_cannot_remove_last_direct_quote_evidence(evidence_db):
    db, _ = evidence_db
    ref = "COURTLISTENER:opinion/456"
    finding_id = _add_draft(
        claim_type="direct_quote",
        evidence_ids=[ref],
        source_quotes={ref: {"quote": "Exact opinion text"}},
    )
    with pytest.raises(ValueError, match="last evidence row"):
        findings_tracker.delete_finding_evidence(
            finding_id, ref, reason="Attempted removal", corrected_by="tester"
        )
    assert db.execute(
        "SELECT COUNT(*) FROM finding_evidence WHERE finding_id=?", (finding_id,)
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE table_name='finding_evidence'"
    ).fetchone()[0] == 0


def test_evidence_ref_collision_rolls_back_update_and_audit(evidence_db):
    db, _ = evidence_db
    ref_a = "COURTLISTENER:record/a"
    ref_b = "COURTLISTENER:record/b"
    finding_id = _add_draft(evidence_ids=[ref_a, ref_b])
    with pytest.raises(sqlite3.IntegrityError):
        findings_tracker.correct_finding_evidence(
            finding_id, ref_a, "evidence_ref", ref_b,
            reason="Bad deduplication", corrected_by="tester",
        )
    refs = db.execute(
        "SELECT evidence_ref FROM finding_evidence WHERE finding_id=? ORDER BY evidence_ref",
        (finding_id,),
    ).fetchall()
    assert [row[0] for row in refs] == [ref_a, ref_b]
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE table_name='finding_evidence'"
    ).fetchone()[0] == 0


def test_finding_correction_validates_sources_and_direct_quote_transition(evidence_db):
    db, _ = evidence_db
    finding_id = _add_draft()
    with pytest.raises(ValueError, match="valid JSON"):
        findings_tracker.update_finding(
            finding_id, "source_datasets", "courtlistener", "Invalid shape"
        )
    with pytest.raises(ValueError, match="without at least one evidence"):
        findings_tracker.update_finding(
            finding_id, "claim_type", "direct_quote", "Unsupported promotion"
        )
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE record_id=?", (finding_id,)
    ).fetchone()[0] == 0

    assert findings_tracker.update_finding(
        finding_id, "source_datasets", '["courtlistener", "registry"]',
        "Normalize provenance", corrected_by="tester",
    )
    stored = db.execute(
        "SELECT source_datasets FROM findings WHERE id=?", (finding_id,)
    ).fetchone()[0]
    assert json.loads(stored) == ["courtlistener", "registry"]


def test_verify_rejects_type_mismatch_and_audit_is_report_only(evidence_db):
    db, _ = evidence_db
    cursor = db.execute(
        "INSERT INTO findings (target_name,summary,source_datasets,claim_type,"
        "verification_status,profile_id) VALUES (?,?,?,?,?,?)",
        ("Legacy", "Legacy invalid row", '"courtlistener"', "direct_quote", "unverified", "test"),
    )
    finding_id = cursor.lastrowid
    db.execute(
        "INSERT INTO finding_evidence "
        "(finding_id,evidence_type,evidence_ref,source_quote) VALUES (?,?,?,NULL)",
        (finding_id, "file", "https://example.gov/legacy/1"),
    )
    db.commit()

    with pytest.raises(ValueError, match="source_datasets"):
        findings_tracker.verify_finding(finding_id, verified_by="tester")
    before = db.total_changes
    report = findings_tracker.audit_finding_evidence(
        finding_id=finding_id, all_profiles=True
    )
    assert report["report_only"] is True
    assert {item["code"] for item in report["issues"]} == {
        "invalid_source_datasets", "evidence_type_mismatch", "missing_source_quote"
    }
    assert db.total_changes == before


def test_cli_help_exposes_audited_evidence_commands():
    result = subprocess.run(
        [sys.executable, str(Path("tools/findings_tracker.py")), "--help"],
        text=True, capture_output=True, check=True,
    )
    for command in (
        "evidence-add", "evidence-correct", "evidence-delete", "evidence-audit"
    ):
        assert command in result.stdout
