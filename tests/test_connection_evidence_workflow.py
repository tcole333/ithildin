import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import findings_tracker, lead_tracker


@pytest.fixture
def connection_workflow_db(tmp_path, monkeypatch):
    db_path = tmp_path / "connection-workflow.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    yield db, db_path
    db.close()


def _add_connection(**kwargs):
    values = {
        "person_a": "Alpha Person",
        "person_b": "Beta Organization",
        "relationship_type": "legal",
        "profile_id": "test",
    }
    values.update(kwargs)
    return findings_tracker.add_connection(**values)


def test_connect_ingests_quote_page_and_assessment(connection_workflow_db):
    db, _ = connection_workflow_db
    ref = "https://example.gov/filing/123"
    connection_id = _add_connection(
        evidence_ids=[ref],
        source_quotes={
            ref: {
                "quote": "Exact filing language",
                "page": "p. 12",
                "assessment": "Names both endpoints",
            }
        },
    )
    row = db.execute(
        "SELECT * FROM connection_evidence WHERE connection_id=?", (connection_id,)
    ).fetchone()
    assert (
        row["evidence_type"], row["source_quote"],
        row["source_page"], row["assessment"],
    ) == ("url", "Exact filing language", "p. 12", "Names both endpoints")
    assert db.execute("SELECT COUNT(*) FROM connections").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0] == 0


def test_idempotent_connect_enrichment_is_audited_and_invalidates_verification(
    connection_workflow_db,
):
    db, _ = connection_workflow_db
    ref = "COURTLISTENER:docket/123"
    connection_id = _add_connection(evidence_ids=[ref])
    db.execute(
        "UPDATE connections SET verification_status='verified',verified_by='old-review' "
        "WHERE id=?",
        (connection_id,),
    )
    db.commit()

    repeated_id = _add_connection(
        evidence_ids=[ref],
        source_quotes={ref: {"quote": "Exact docket text", "page": "entry 4"}},
    )
    assert repeated_id == connection_id
    assert db.execute("SELECT COUNT(*) FROM connections").fetchone()[0] == 1
    evidence = db.execute(
        "SELECT source_quote,source_page FROM connection_evidence WHERE connection_id=?",
        (connection_id,),
    ).fetchone()
    assert tuple(evidence) == ("Exact docket text", "entry 4")
    connection = db.execute(
        "SELECT verification_status,verified_by,verified_at FROM connections WHERE id=?",
        (connection_id,),
    ).fetchone()
    assert tuple(connection) == ("unverified", None, None)
    audit_fields = db.execute(
        "SELECT table_name,field_name FROM corrections WHERE record_id=? ORDER BY id",
        (connection_id,),
    ).fetchall()
    assert [tuple(row) for row in audit_fields] == [
        ("connection_evidence", "source_quote"),
        ("connection_evidence", "source_page"),
        ("connections", "verification_status"),
    ]

    correction_count = db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
    _add_connection(
        evidence_ids=[ref],
        source_quotes={ref: {"quote": "Exact docket text", "page": "entry 4"}},
    )
    assert db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0] == correction_count


def test_connect_refuses_silent_provenance_overwrite_and_rolls_back(
    connection_workflow_db,
):
    db, _ = connection_workflow_db
    ref = "COURTLISTENER:docket/456"
    connection_id = _add_connection(
        evidence_ids=[ref],
        source_quotes={ref: {"quote": "Original quote"}},
    )
    db.execute(
        "UPDATE connections SET verification_status='verified' WHERE id=?",
        (connection_id,),
    )
    db.commit()

    with pytest.raises(ValueError, match="connection-evidence-correct"):
        _add_connection(
            evidence_ids=[ref],
            source_quotes={ref: {"quote": "Conflicting quote"}},
        )
    row = db.execute(
        "SELECT source_quote FROM connection_evidence WHERE connection_id=?",
        (connection_id,),
    ).fetchone()
    assert row[0] == "Original quote"
    assert db.execute(
        "SELECT verification_status FROM connections WHERE id=?", (connection_id,)
    ).fetchone()[0] == "verified"
    assert db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0] == 0


def test_connection_evidence_crud_is_audited_and_atomic(connection_workflow_db):
    db, _ = connection_workflow_db
    connection_id = _add_connection()
    ref = "COURTLISTENER:opinion/789"
    findings_tracker.add_connection_evidence(
        connection_id, ref, source_quote="Exact opinion language",
        source_page="p. 3", assessment="Directly supports the edge",
        reason="Attach opinion", corrected_by="tester",
    )
    added = db.execute(
        "SELECT * FROM corrections WHERE table_name='connection_evidence' "
        "AND record_id=? AND record_key=?",
        (connection_id, ref),
    ).fetchone()
    assert added["field_name"] == "__row__"
    assert json.loads(added["new_value"])["source_page"] == "p. 3"

    findings_tracker.verify_connection(connection_id, verified_by="reviewer")
    findings_tracker.correct_connection_evidence(
        connection_id, ref, "assessment", "Refined edge assessment",
        reason="Clarify support", corrected_by="tester",
    )
    assert db.execute(
        "SELECT verification_status FROM connections WHERE id=?", (connection_id,)
    ).fetchone()[0] == "unverified"

    findings_tracker.delete_connection_evidence(
        connection_id, ref, reason="Superseded evidence", corrected_by="tester"
    )
    assert db.execute(
        "SELECT COUNT(*) FROM connection_evidence WHERE connection_id=?",
        (connection_id,),
    ).fetchone()[0] == 0
    deleted = db.execute(
        "SELECT old_value,new_value,correction_type FROM corrections "
        "WHERE table_name='connection_evidence' AND record_id=? "
        "AND field_name='__row__' ORDER BY id DESC LIMIT 1",
        (connection_id,),
    ).fetchone()
    assert json.loads(deleted["old_value"])["evidence_ref"] == ref
    assert deleted["new_value"] is None
    assert deleted["correction_type"] == "retraction"


def test_identical_evidence_correction_is_a_noop_without_invalidation(
    connection_workflow_db,
):
    db, _ = connection_workflow_db
    ref = "COURTLISTENER:record/noop"
    connection_id = _add_connection(
        evidence_ids=[ref],
        source_quotes={ref: {"quote": "Exact stable quote", "page": "p. 7"}},
    )
    findings_tracker.verify_connection(connection_id, verified_by="reviewer")
    before = db.execute(
        "SELECT verification_status,verified_by,verified_at FROM connections WHERE id=?",
        (connection_id,),
    ).fetchone()
    correction_count = db.execute(
        "SELECT COUNT(*) FROM corrections WHERE record_id=?", (connection_id,)
    ).fetchone()[0]

    assert findings_tracker.correct_connection_evidence(
        connection_id, ref, "source_quote", "Exact stable quote",
        reason="Repeat the same value", corrected_by="tester",
    ) is False

    after = db.execute(
        "SELECT verification_status,verified_by,verified_at FROM connections WHERE id=?",
        (connection_id,),
    ).fetchone()
    assert tuple(after) == tuple(before)
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE record_id=?", (connection_id,)
    ).fetchone()[0] == correction_count


def test_connection_evidence_ref_collision_rolls_back_audit(connection_workflow_db):
    db, _ = connection_workflow_db
    ref_a = "COURTLISTENER:record/a"
    ref_b = "COURTLISTENER:record/b"
    connection_id = _add_connection(evidence_ids=[ref_a, ref_b])
    with pytest.raises(sqlite3.IntegrityError):
        findings_tracker.correct_connection_evidence(
            connection_id, ref_a, "evidence_ref", ref_b,
            reason="Bad merge", corrected_by="tester",
        )
    refs = db.execute(
        "SELECT evidence_ref FROM connection_evidence "
        "WHERE connection_id=? ORDER BY evidence_ref",
        (connection_id,),
    ).fetchall()
    assert [row[0] for row in refs] == [ref_a, ref_b]
    assert db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0] == 0


def test_verify_connection_enforces_evidence_quote_and_upstream_finding(
    connection_workflow_db,
):
    db, _ = connection_workflow_db
    empty_connection = _add_connection(person_a="Empty A", person_b="Empty B")
    with pytest.raises(ValueError, match="no evidence"):
        findings_tracker.verify_connection(empty_connection)

    ref = "COURTLISTENER:docket/900"
    unquoted_connection = _add_connection(
        person_a="Quote A", person_b="Quote B", evidence_ids=[ref]
    )
    with pytest.raises(ValueError, match="requires a non-empty source_quote"):
        findings_tracker.verify_connection(unquoted_connection)
    findings_tracker.correct_connection_evidence(
        unquoted_connection, ref, "source_quote", "Exact docket quote",
        reason="Add verification quote", corrected_by="tester",
    )
    findings_tracker.verify_connection(unquoted_connection, verified_by="tester")

    finding_ref = "COURTLISTENER:record/upstream"
    finding_id = findings_tracker.add_finding(
        "Upstream Subject", "Upstream claim", source_datasets=["courtlistener"],
        evidence_ids=[finding_ref],
        source_quotes={finding_ref: {"quote": "Exact upstream language"}},
        profile_id="test",
    )
    connection_ref = "COURTLISTENER:record/edge"
    upstream_connection = _add_connection(
        person_a="Upstream A", person_b="Upstream B", finding_id=finding_id,
        evidence_ids=[connection_ref],
        source_quotes={connection_ref: {"quote": "Exact edge language"}},
    )
    with pytest.raises(ValueError, match="until upstream finding"):
        findings_tracker.verify_connection(upstream_connection)
    findings_tracker.verify_finding(finding_id, verified_by="tester")
    findings_tracker.verify_connection(upstream_connection, verified_by="tester")
    assert db.execute(
        "SELECT verification_status FROM connections WHERE id=?", (upstream_connection,)
    ).fetchone()[0] == "verified"


def test_verify_connection_is_idempotent_and_preserves_immutable_status_history(
    connection_workflow_db,
):
    db, _ = connection_workflow_db
    ref = "COURTLISTENER:record/verify-idempotent"
    connection_id = _add_connection(
        evidence_ids=[ref], source_quotes={ref: {"quote": "Exact verification quote"}}
    )
    assert findings_tracker.verify_connection(connection_id, verified_by="reviewer") is True
    first = db.execute(
        "SELECT verification_status,verified_by,verified_at FROM connections WHERE id=?",
        (connection_id,),
    ).fetchone()
    history = db.execute(
        "SELECT old_value,new_value,corrected_by FROM corrections "
        "WHERE table_name='connections' AND record_id=? AND field_name='verification_status'",
        (connection_id,),
    ).fetchall()
    assert [tuple(row) for row in history] == [("unverified", "verified", "reviewer")]

    assert findings_tracker.verify_connection(connection_id, verified_by="other") is False
    second = db.execute(
        "SELECT verification_status,verified_by,verified_at FROM connections WHERE id=?",
        (connection_id,),
    ).fetchone()
    assert tuple(second) == tuple(first)
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE table_name='connections' "
        "AND record_id=? AND field_name='verification_status'",
        (connection_id,),
    ).fetchone()[0] == 1


def test_connection_lifecycle_and_corrections_are_auditable(connection_workflow_db):
    db, _ = connection_workflow_db
    ref = "COURTLISTENER:record/lifecycle"
    connection_id = _add_connection(
        evidence_ids=[ref],
        source_quotes={ref: {"quote": "Exact lifecycle quote"}},
    )
    findings_tracker.verify_connection(connection_id, verified_by="reviewer")
    findings_tracker.correct_connection(
        connection_id, "description", "Corrected description",
        "Add precise description", corrected_by="tester",
    )
    assert db.execute(
        "SELECT verification_status FROM connections WHERE id=?", (connection_id,)
    ).fetchone()[0] == "unverified"
    findings_tracker.dispute_connection(
        connection_id, "Relationship is contested", corrected_by="tester"
    )
    findings_tracker.retract_connection(
        connection_id, "Edge was unsupported", corrected_by="tester"
    )
    correction_count = db.execute(
        "SELECT COUNT(*) FROM corrections WHERE table_name='connections' AND record_id=?",
        (connection_id,),
    ).fetchone()[0]
    with pytest.raises(ValueError, match="retracted and cannot be disputed"):
        findings_tracker.dispute_connection(
            connection_id, "Attempted resurrection", corrected_by="tester"
        )
    with pytest.raises(ValueError, match="retracted"):
        findings_tracker.verify_connection(connection_id)
    assert db.execute(
        "SELECT verification_status FROM connections WHERE id=?", (connection_id,)
    ).fetchone()[0] == "retracted"
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE table_name='connections' AND record_id=?",
        (connection_id,),
    ).fetchone()[0] == correction_count
    fields = db.execute(
        "SELECT field_name,new_value FROM corrections "
        "WHERE table_name='connections' AND record_id=? ORDER BY id",
        (connection_id,),
    ).fetchall()
    assert [tuple(row) for row in fields] == [
        ("verification_status", "verified"),
        ("description", "Corrected description"),
        ("verification_status", "unverified"),
        ("verification_status", "disputed"),
        ("verification_status", "retracted"),
    ]
    with pytest.raises(ValueError, match="Endpoint corrections require"):
        findings_tracker.correct_connection(
            connection_id, "person_a", "Different Person", "Unsafe endpoint edit"
        )


def test_provenance_unverified_and_verified_publication_filter(connection_workflow_db):
    db, _ = connection_workflow_db
    verified_ref = "COURTLISTENER:verified/1"
    verified_id = _add_connection(
        person_a="Shared Node", person_b="Verified Node",
        evidence_ids=[verified_ref],
        source_quotes={verified_ref: {"quote": "Verified edge quote"}},
    )
    findings_tracker.verify_connection(verified_id, verified_by="tester")
    unverified_id = _add_connection(
        person_a="Shared Node", person_b="Draft Node",
    )
    legacy_ref = "COURTLISTENER:legacy/verified-without-quote"
    legacy_id = _add_connection(
        person_a="Shared Node", person_b="Legacy Verified Node",
        evidence_ids=[legacy_ref],
    )
    db.execute(
        "UPDATE connections SET verification_status='verified' WHERE id=?",
        (legacy_id,),
    )
    db.commit()

    unverified = findings_tracker.get_unverified_connections(
        profile_id="test", all_profiles=False
    )
    assert [row["id"] for row in unverified] == [unverified_id]
    published = findings_tracker.get_connections(
        "Shared Node", profile_id="test", verification_status="verified"
    )
    assert [row["id"] for row in published] == [verified_id]
    provenance = findings_tracker.get_connection_provenance(verified_id)
    assert provenance["verification_status"] == "verified"
    assert provenance["publication_ready"] is True
    assert provenance["evidence"][0]["source_quote"] == "Verified edge quote"
    assert [row["new_value"] for row in provenance["corrections"]] == ["verified"]
    assert provenance["evidence_corrections"] == []
    legacy_provenance = findings_tracker.get_connection_provenance(legacy_id)
    assert legacy_provenance["verification_status"] == "verified"
    assert legacy_provenance["publication_ready"] is False
    assert "source_quote" in legacy_provenance["publication_error"]
    assert db.execute("SELECT COUNT(*) FROM connections").fetchone()[0] == 3


def test_cli_help_exposes_connection_evidence_and_lifecycle_commands():
    result = subprocess.run(
        [sys.executable, str(Path("tools/findings_tracker.py")), "--help"],
        text=True, capture_output=True, check=True,
    )
    for command in (
        "connection-evidence-add", "connection-evidence-correct",
        "connection-evidence-delete", "connection-verify", "connection-dispute",
        "connection-retract", "connection-correct", "connection-audit",
        "connection-provenance", "connection-unverified",
    ):
        assert command in result.stdout
