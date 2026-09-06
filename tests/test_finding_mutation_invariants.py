"""Regression boundaries for canonical writes, corrections, and verification."""

import json
import sqlite3

import pytest

from tools import findings_tracker as ft
from tools import lead_tracker as lt
from tools.entity_resolution import EntityResolutionAmbiguity, resolve_or_create_entity


@pytest.fixture
def store(tmp_path, monkeypatch):
    db_path = tmp_path / "investigation.db"
    monkeypatch.setattr(lt, "DB_PATH", db_path)
    monkeypatch.setattr(lt, "_schema_initialized", False)
    monkeypatch.setattr(ft, "DB_PATH", db_path)
    monkeypatch.setattr(ft, "_schema_initialized", False)
    db = lt.get_db()
    yield db
    db.close()


def draft(**overrides):
    values = {
        "target_name": "Original Company LLC",
        "summary": "The company filed an annual report.",
        "detail": "A primary record identifies the filing.",
        "finding_type": "legal",
        "source_datasets": ["courtlistener"],
        "profile_id": "fixture",
        "claim_type": "direct_quote",
        "confidence": "confirmed",
        "evidence_ids": ["COURTLISTENER:fixture-record"],
        "source_quotes": {"COURTLISTENER:fixture-record": {"quote": "The company filed an annual report."}},
        "date_of_event": "2025",
    }
    values.update(overrides)
    return values


def verified(**overrides):
    finding_id = ft.add_finding(**draft(**overrides))
    ft.verify_finding(finding_id, verified_by="original-reviewer")
    return finding_id


def test_caller_owned_write_preserves_evidence_dates_and_transaction(store, monkeypatch):
    # This is the same composition staged import needs: a receipt and canonical
    # records must commit or roll back together, with no hidden second writer.
    store.execute("CREATE TABLE import_receipts (id INTEGER PRIMARY KEY)")
    store.commit()
    store.execute("BEGIN IMMEDIATE")
    store.execute("INSERT INTO import_receipts VALUES (1)")

    def unexpected_open(*args, **kwargs):
        raise AssertionError("canonical writer must use only its caller's connection")

    monkeypatch.setattr(sqlite3, "connect", unexpected_open)
    finding_id = ft.add_finding_to_db(
        store, **draft(claim_type="inference", confidence="confirmed")
    )
    row = store.execute("SELECT * FROM findings WHERE id=?", (finding_id,)).fetchone()
    assert (row["confidence"], row["confidence_requested"], row["event_date_iso"], row["date_precision"]) == (
        "medium", "confirmed", "2025-01-01", "year",
    )
    assert store.execute("SELECT source_quote FROM finding_evidence WHERE finding_id=?", (finding_id,)).fetchone()[0] == "The company filed an annual report."
    assert store.execute("SELECT COUNT(*) FROM finding_entities WHERE finding_id=?", (finding_id,)).fetchone()[0] == 1
    assert store.in_transaction
    store.rollback()
    for table in ("findings", "finding_evidence", "finding_entities", "entities", "import_receipts"):
        assert store.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_invalid_staged_record_does_not_partially_insert(store):
    with pytest.raises(ValueError, match="duplicate references"):
        ft.add_finding_to_db(store, **draft(evidence_ids=["SOURCE:one", " SOURCE:one "], source_quotes={}))
    assert store.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0


@pytest.mark.parametrize("claim_type", ft.VALID_CLAIM_TYPES)
@pytest.mark.parametrize("incomplete", ["no_refs", "missing_quote", "blank_quote", "second_unquoted_ref"])
def test_new_findings_require_complete_provenance_for_every_claim_type(store, claim_type, incomplete):
    values = draft(claim_type=claim_type)
    ref = values["evidence_ids"][0]
    if incomplete == "no_refs":
        values.update(evidence_ids=[], source_quotes={})
    elif incomplete == "missing_quote":
        values["source_quotes"] = {}
    elif incomplete == "blank_quote":
        values["source_quotes"] = {ref: {"quote": " \t\n "}}
    else:
        values["evidence_ids"].append("COURTLISTENER:second-record")

    # Validation must neither publish an incomplete claim nor disturb an
    # enclosing import transaction that the caller may still roll back.
    store.execute("CREATE TABLE import_receipts (id INTEGER PRIMARY KEY)")
    store.commit()
    store.execute("BEGIN IMMEDIATE")
    store.execute("INSERT INTO import_receipts VALUES (1)")
    with pytest.raises(ValueError, match="evidence reference|non-empty source_quote"):
        ft.add_finding_to_db(store, **values)
    for table in ("findings", "finding_evidence", "finding_entities", "entities"):
        assert store.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert store.in_transaction
    assert store.execute("SELECT COUNT(*) FROM import_receipts").fetchone()[0] == 1
    store.rollback()


@pytest.mark.parametrize("claim_type", ft.VALID_CLAIM_TYPES)
def test_complete_new_claims_still_require_separate_verification(store, claim_type):
    finding_id = ft.add_finding_to_db(store, **draft(claim_type=claim_type))
    row = store.execute(
        "SELECT verification_status, verified_by, verified_at FROM findings WHERE id=?",
        (finding_id,),
    ).fetchone()
    assert tuple(row) == ("unverified", None, None)


@pytest.mark.parametrize("quote", [None, 42, ["Quoted words"], {"text": "Quoted words"}])
def test_new_findings_reject_nontext_quotes_before_any_insert(store, quote):
    with pytest.raises(ValueError, match="non-empty source_quote string"):
        ft.add_finding_to_db(store, **draft(
            claim_type="inference",
            source_quotes={"COURTLISTENER:fixture-record": {"quote": quote}},
        ))
    for table in ("findings", "finding_evidence", "finding_entities", "entities"):
        assert store.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_legacy_incomplete_claim_can_be_read_corrected_and_repaired(store):
    # Reproduce historical state directly; the canonical insert API must never
    # gain a draft bypass merely to construct legacy fixtures.
    cursor = store.execute(
        """INSERT INTO findings (
            target_name, summary, source_datasets, confidence, claim_type,
            verification_status, profile_id
        ) VALUES ('Legacy Company', 'Original claim', '["courtlistener"]',
                  'medium', 'inference', 'unverified', 'fixture')"""
    )
    finding_id = cursor.lastrowid
    store.commit()
    assert ft.get_finding(finding_id)["evidence"] == []
    assert ft.update_finding(finding_id, "summary", "Corrected claim", "Repair historical wording")
    with pytest.raises(ValueError, match="without at least one evidence reference"):
        ft.verify_finding(finding_id)
    ft.add_finding_evidence(
        finding_id, "COURTLISTENER:legacy-record", source_quote="The historical record identifies the company.",
        reason="Restore primary provenance", corrected_by="fixture-reviewer",
    )
    ft.verify_finding(finding_id, verified_by="fixture-reviewer")
    row = store.execute("SELECT summary,verification_status FROM findings WHERE id=?", (finding_id,)).fetchone()
    assert tuple(row) == ("Corrected claim", "verified")


@pytest.mark.parametrize(("field", "value"), [
    ("summary", "The company faces a different allegation."),
    ("detail", "Different facts require another review."),
    ("target_name", "Unrelated Organization Inc"),
    ("date_of_event", "2026-07-01"),
    ("confidence", "low"),
    ("finding_type", "financial"),
])
def test_semantic_corrections_invalidate_previous_verification(store, field, value):
    finding_id = verified()
    assert ft.update_finding(finding_id, field, value, "Correct the claim", corrected_by="editor")
    row = store.execute("SELECT * FROM findings WHERE id=?", (finding_id,)).fetchone()
    assert (row["verification_status"], row["verified_by"], row["verified_at"]) == ("unverified", None, None)
    if field == "date_of_event":
        assert (row["event_date_iso"], row["date_precision"]) == ("2026-07-01", "day")
    assert store.execute("SELECT COUNT(*) FROM corrections WHERE table_name='findings' AND record_id=? AND field_name='verification_status'", (finding_id,)).fetchone()[0] == 1


def test_same_value_correction_does_not_invalidate_review(store):
    finding_id = verified()
    ft.update_finding(finding_id, "summary", draft()["summary"], "Confirm existing wording")
    row = store.execute("SELECT verification_status,verified_by FROM findings WHERE id=?", (finding_id,)).fetchone()
    assert tuple(row) == ("verified", "original-reviewer")


@pytest.mark.parametrize(("field", "value", "expected"), [
    ("claim_type", "inference", "medium"),
    ("claim_type", "paraphrase", "high"),
    ("source_datasets", '["dehashed"]', "medium"),
])
def test_correction_recomputes_and_audits_confidence_cap(store, field, value, expected):
    finding_id = verified()
    ft.update_finding(finding_id, field, value, "Correct provenance", corrected_by="editor")
    row = store.execute("SELECT confidence,verification_status FROM findings WHERE id=?", (finding_id,)).fetchone()
    assert tuple(row) == (expected, "unverified")
    audit = store.execute("SELECT old_value,new_value FROM corrections WHERE table_name='findings' AND record_id=? AND field_name='confidence'", (finding_id,)).fetchone()
    assert tuple(audit) == ("confirmed", expected)
    ft.verify_finding(finding_id, verified_by="new-reviewer")


def test_explicit_confidence_correction_cannot_bypass_inference_cap(store):
    finding_id = verified(claim_type="inference", confidence="low")
    ft.update_finding(finding_id, "confidence", "confirmed", "Requested confidence increase")
    row = store.execute("SELECT confidence,confidence_requested,verification_status FROM findings WHERE id=?", (finding_id,)).fetchone()
    assert tuple(row) == ("medium", "confirmed", "unverified")


@pytest.mark.parametrize(("claim_type", "sources", "confidence"), [
    ("inference", '["courtlistener"]', "confirmed"),
    ("paraphrase", '["courtlistener"]', "confirmed"),
    ("direct_quote", '["dehashed"]', "high"),
])
def test_verify_rejects_preexisting_above_cap_rows_without_rewriting_them(store, claim_type, sources, confidence):
    finding_id = ft.add_finding(**draft())
    store.execute("UPDATE findings SET claim_type=?,source_datasets=?,confidence=? WHERE id=?", (claim_type, sources, confidence, finding_id))
    store.commit()
    with pytest.raises(ValueError, match="exceeds.*cap"):
        ft.verify_finding(finding_id)
    row = store.execute("SELECT confidence,verification_status FROM findings WHERE id=?", (finding_id,)).fetchone()
    assert tuple(row) == (confidence, "unverified")


def test_subject_correction_reconciles_generated_link_and_preserves_manual_mention(store):
    finding_id = verified()
    manual = resolve_or_create_entity(store, "Witness Person", entity_type="person")
    store.execute("INSERT INTO finding_entities(finding_id,entity_id,mention_role,raw_name,resolution_method) VALUES (?,?, 'witness','Witness Person','manual')", (finding_id, manual.entity_id))
    store.commit()
    ft.update_finding(finding_id, "target_name", "Unrelated Organization Inc", "Correct mistaken subject", corrected_by="editor")
    links = store.execute("SELECT fe.mention_role,e.name FROM finding_entities fe JOIN entities e ON e.id=fe.entity_id WHERE finding_id=? ORDER BY fe.mention_role", (finding_id,)).fetchall()
    assert [tuple(row) for row in links] == [("subject", "Unrelated Organization Inc"), ("witness", "Witness Person")]
    audit = store.execute("SELECT old_value,new_value FROM corrections WHERE table_name='finding_entities' AND record_id=?", (finding_id,)).fetchone()
    assert json.loads(audit[0])[0]["raw_name"] == "Original Company LLC"
    assert json.loads(audit[1])[0]["raw_name"] == "Unrelated Organization Inc"


def test_ambiguous_subject_correction_rolls_back_claim_links_and_audit(store, monkeypatch):
    finding_id = verified()
    initial_links = [tuple(row) for row in store.execute("SELECT * FROM finding_entities")]

    def ambiguous(*args, **kwargs):
        raise EntityResolutionAmbiguity("new target is ambiguous")

    monkeypatch.setattr(ft, "_link_finding_entity", ambiguous)
    with pytest.raises(EntityResolutionAmbiguity):
        ft.update_finding(finding_id, "target_name", "Ambiguous Organization", "Attempt identity correction")
    row = store.execute("SELECT target_name,verification_status FROM findings WHERE id=?", (finding_id,)).fetchone()
    assert tuple(row) == ("Original Company LLC", "verified")
    assert [tuple(row) for row in store.execute("SELECT * FROM finding_entities")] == initial_links
    assert store.execute("SELECT COUNT(*) FROM corrections").fetchone()[0] == 0


def test_connection_cannot_publish_from_legacy_above_cap_finding(store):
    finding_id = verified()
    ref = "COURTLISTENER:edge"
    connection_id = ft.add_connection("Source Entity", "Destination Entity", relationship_type="financial", finding_id=finding_id, evidence_ids=[ref], source_quotes={ref: {"quote": "A payment was recorded."}}, profile_id="fixture")
    store.execute("UPDATE findings SET claim_type='inference',confidence='confirmed' WHERE id=?", (finding_id,))
    store.commit()
    with pytest.raises(ValueError, match="exceeds.*cap"):
        ft.verify_connection(connection_id)
    assert store.execute("SELECT verification_status FROM connections WHERE id=?", (connection_id,)).fetchone()[0] == "unverified"
