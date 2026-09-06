"""Behavioral regressions for scoped, snapshot-bound lead review operations."""

import copy
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import lead_dedup, lead_tracker, triage_policy


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def review_dbs(tmp_path, monkeypatch):
    paths = [tmp_path / "canonical.db", tmp_path / "selected.db"]
    for db_path in paths:
        monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
        monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
        db = lead_tracker.get_db()
        db.execute("INSERT OR REPLACE INTO investigation_config (key,value) VALUES ('active_profile','alpha')")
        db.commit()
        db.close()
    canonical, selected = paths
    for module in (lead_tracker, lead_dedup, triage_policy):
        monkeypatch.setattr(module, "DB_PATH", selected)
    monkeypatch.setenv("ITHILDIN_PROFILE", "alpha")
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(selected))
    return canonical, selected


def add_lead(db_path, *, title="Ownership question", target="Example Company", profile="alpha",
             status="pending_triage", description=None, depth="standard"):
    with sqlite3.connect(db_path) as db:
        return db.execute(
            "INSERT INTO leads (title,description,target_name,profile_id,status,priority,depth_tier,category) "
            "VALUES (?,?,?,?,?,'medium',?,'entity')",
            (title, description, target, profile, status, depth),
        ).lastrowid


def dump(db_path):
    with sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True) as db:
        return "\n".join(db.iterdump())


def promote(lead_id):
    return {"lead_id": lead_id, "action": "promote", "priority": "high", "depth_tier": "standard",
            "recommended_skill": "/trace-entity", "rationale": "Trace the $25,000 ownership transfer."}


def dedup_decisions(batch, action="keep_all"):
    return [{"group_hash": group["group_hash"], "decision": action,
             "keeper_id": group["lead_ids"][0] if action != "keep_all" else None,
             "dead_end_ids": group["lead_ids"][1:] if action != "keep_all" else [],
             "rationale": "Reviewed identity and question scope.", "target_name_fills": {}}
            for group in batch["groups"]]


def test_triage_cli_respects_environment_and_rejects_another_database(review_dbs, tmp_path):
    canonical, selected = review_dbs
    original_id = add_lead(canonical, title="Canonical sentinel")
    selected_id = add_lead(selected, title="Selected question")
    foreign_id = add_lead(selected, title="Other profile question", profile="beta")
    assert original_id == selected_id  # A realistic dangerous ID collision.
    baseline = dump(canonical)
    batch_path, decision_path = tmp_path / "batch.json", tmp_path / "decisions.json"
    env = dict(os.environ, ITHILDIN_PROFILE="alpha", ITHILDIN_DB_PATH=str(selected))
    command = [sys.executable, str(ROOT / "tools/lead_tracker.py")]
    exported = subprocess.run(command + ["triage-export", "--output", str(batch_path)], env=env, text=True, capture_output=True)
    assert exported.returncode == 0, exported.stderr
    batch = json.loads(batch_path.read_text())
    assert batch["database_path"] == str(selected)
    assert [item["id"] for item in batch["leads"]] == [selected_id]
    decision_path.write_text(json.dumps([promote(selected_id)]))
    apply_args = ["triage-apply", "--batch-file", str(batch_path), "--decisions-file", str(decision_path)]
    wrong = subprocess.run(command + apply_args, env=dict(env, ITHILDIN_DB_PATH=str(canonical)), text=True, capture_output=True)
    assert wrong.returncode == 1 and "database/profile" in wrong.stderr
    applied = subprocess.run(command + apply_args, env=env, text=True, capture_output=True)
    assert applied.returncode == 0, applied.stderr
    assert dump(canonical) == baseline
    with sqlite3.connect(selected) as db:
        assert db.execute("SELECT status FROM leads WHERE id=?", (selected_id,)).fetchone()[0] == "open"
        assert db.execute("SELECT status FROM leads WHERE id=?", (foreign_id,)).fetchone()[0] == "pending_triage"
        assert "$25,000" in db.execute("SELECT note FROM lead_notes WHERE lead_id=?", (selected_id,)).fetchone()[0]


@pytest.mark.parametrize("change", ["status", "title", "note", "evidence"])
def test_triage_rejects_stale_context_without_partial_application(review_dbs, change):
    _, selected = review_dbs
    first, stale = add_lead(selected), add_lead(selected)
    batch = lead_tracker.export_triage_batch()
    with sqlite3.connect(selected) as db:
        if change == "status":
            db.execute("UPDATE leads SET status='in_progress' WHERE id=?", (stale,))
        elif change == "title":
            db.execute("UPDATE leads SET title='Different question' WHERE id=?", (stale,))
        elif change == "note":
            db.execute("INSERT INTO lead_notes (lead_id,note) VALUES (?, 'New evidence')", (stale,))
        else:
            db.execute("INSERT INTO lead_evidence VALUES (?, 'url', 'https://example.org/new')", (stale,))
    baseline = dump(selected)
    with pytest.raises(ValueError, match="changed since export"):
        lead_tracker.apply_triage_decisions(batch, [promote(first), promote(stale)])
    assert dump(selected) == baseline


@pytest.mark.parametrize("field", ["lead_id", "keeper_id", "related_lead_ids", "thread_id"])
def test_triage_rejects_foreign_ids(review_dbs, field):
    _, selected = review_dbs
    lead_id = add_lead(selected)
    foreign_id = add_lead(selected, profile="beta", status="open")
    with sqlite3.connect(selected) as db:
        thread_id = db.execute("INSERT INTO investigation_threads (title,profile_id) VALUES ('Foreign','beta')").lastrowid
    decision = promote(lead_id)
    if field == "keeper_id":
        decision.update(action="dead_end", stop_reason="duplicate", keeper_id=foreign_id)
    else:
        decision[field] = {"lead_id": foreign_id, "related_lead_ids": [foreign_id], "thread_id": thread_id}[field]
    batch, baseline = lead_tracker.export_triage_batch(), dump(selected)
    with pytest.raises(ValueError):
        lead_tracker.apply_triage_decisions(batch, [decision])
    assert dump(selected) == baseline


def test_triage_requires_complete_batch_and_validates_dry_run(review_dbs):
    _, selected = review_dbs
    first, second = add_lead(selected), add_lead(selected)
    batch, baseline = lead_tracker.export_triage_batch(), dump(selected)
    with pytest.raises(ValueError, match="exactly once"):
        lead_tracker.apply_triage_decisions(batch, [promote(first)])
    result = lead_tracker.apply_triage_decisions(batch, [promote(first), promote(second)], dry_run=True)
    assert result["actions"]["promote"] == 2
    assert dump(selected) == baseline


def test_triage_records_a_scoped_duplicate_keeper_and_hold(review_dbs):
    _, selected = review_dbs
    duplicate, held = add_lead(selected), add_lead(selected)
    keeper = add_lead(selected, status="open")
    batch = lead_tracker.export_triage_batch(reference_lead_ids=[keeper])
    result = lead_tracker.apply_triage_decisions(batch, [
        {"lead_id": duplicate, "action": "dead_end", "stop_reason": f"Duplicate of lead #{keeper}",
         "keeper_id": keeper, "rationale": "Same question, period and supporting source."},
        {"lead_id": held, "action": "hold", "rationale": "Wait for the registry access dependency."},
    ])
    assert result["actions"] == {"promote": 0, "hold": 1, "dead_end": 1}
    with sqlite3.connect(selected) as db:
        assert db.execute("SELECT relation_type FROM lead_relations WHERE lead_id=? AND related_lead_id=?", (duplicate, keeper)).fetchone()[0] == "duplicate"
        assert db.execute("SELECT status FROM leads WHERE id=?", (held,)).fetchone()[0] == "pending_triage"


def test_dedup_fill_and_scan_are_scoped_and_readonly_preview_does_not_create_schema(review_dbs, monkeypatch):
    canonical, selected = review_dbs
    add_lead(canonical, title="Cross-ref officer: Canonical Sentinel — find other entity roles", target=None)
    local_id = add_lead(selected, title="Cross-ref officer: Jane Reviewer — find other entity roles", target=None)
    foreign_id = add_lead(selected, title="Cross-ref officer: Foreign Reviewer — find other entity roles", target=None, profile="beta")
    baseline = dump(canonical)
    before_preview = dump(selected)
    assert lead_dedup.fill_targets(dry_run=True)["filled"] == 1
    assert dump(selected) == before_preview
    assert lead_dedup.fill_targets()["filled"] == 1
    assert dump(canonical) == baseline
    with sqlite3.connect(selected) as db:
        assert db.execute("SELECT target_name FROM leads WHERE id=?", (local_id,)).fetchone()[0] == "Jane Reviewer"
        assert db.execute("SELECT target_name FROM leads WHERE id=?", (foreign_id,)).fetchone()[0] is None
    first = add_lead(selected, status="open")
    second = add_lead(selected, status="open")
    add_lead(selected, status="open", profile="beta")
    monkeypatch.delenv("ITHILDIN_PROFILE")  # Resolve the selected DB's default, not global context.
    batch = lead_dedup.export_batch()
    assert batch["profile_id"] == "alpha"
    assert batch["groups"][0]["lead_ids"] == [first, second]


@pytest.mark.parametrize("mutation", ["foreign_keeper", "outside_group", "unknown_hash", "missing_keeper", "missing_group", "unknown_action"])
def test_dedup_rejects_invalid_decisions_atomically(review_dbs, mutation):
    _, selected = review_dbs
    for _ in range(2):
        add_lead(selected, status="open")
    outside = add_lead(selected, target="Other Corporation", status="open")
    foreign = add_lead(selected, profile="beta", status="open")
    batch = lead_dedup.export_batch()
    decisions = dedup_decisions(batch, "merge")
    decision = decisions[0]
    if mutation == "foreign_keeper":
        decision["keeper_id"] = foreign
    elif mutation == "outside_group":
        decision["dead_end_ids"] = [outside]
    elif mutation == "unknown_hash":
        decision["group_hash"] = "not-exported"
    elif mutation == "missing_keeper":
        decision["keeper_id"] = None
    elif mutation == "missing_group":
        decisions = []
    else:
        decision["decision"] = "delete"
    baseline = dump(selected)
    with pytest.raises(ValueError):
        lead_dedup.apply_decisions(batch, decisions)
    assert dump(selected) == baseline


def test_dedup_rejects_foreign_batch_database_and_profile(review_dbs, monkeypatch):
    canonical, selected = review_dbs
    for db_path in review_dbs:
        add_lead(db_path, status="open")
        add_lead(db_path, status="open")
    batch = lead_dedup.export_batch()
    decisions = dedup_decisions(batch, "merge")
    baseline = dump(canonical)
    monkeypatch.setattr(lead_dedup, "DB_PATH", canonical)
    with pytest.raises(ValueError, match="database/profile"):
        lead_dedup.apply_decisions(batch, decisions)
    assert dump(canonical) == baseline
    monkeypatch.setattr(lead_dedup, "DB_PATH", selected)
    with pytest.raises(ValueError, match="database/profile"):
        lead_dedup.apply_decisions(batch, decisions, profile_id="beta")


def test_dedup_stale_status_blocks_all_groups(review_dbs):
    _, selected = review_dbs
    for target in ("First Corporation", "Second Corporation"):
        add_lead(selected, status="open", target=target)
        stale = add_lead(selected, status="open", target=target)
    batch = lead_dedup.export_batch()
    with sqlite3.connect(selected) as db:
        db.execute("UPDATE leads SET status='in_progress' WHERE id=?", (stale,))
    baseline = dump(selected)
    with pytest.raises(ValueError, match="changed since export"):
        lead_dedup.apply_decisions(batch, dedup_decisions(batch, "merge"))
    assert dump(selected) == baseline


def test_consolidation_preserves_all_context_and_is_idempotent(review_dbs):
    _, selected = review_dbs
    keeper = add_lead(selected, status="open")
    source = add_lead(selected, status="open", description="Long context " * 100 + "ESSENTIAL END")
    with sqlite3.connect(selected) as db:
        db.execute("INSERT INTO lead_notes (lead_id,note) VALUES (?, 'Unique note with $750,000')", (source,))
        db.execute("INSERT INTO lead_evidence VALUES (?, 'url', 'https://example.org/evidence')", (source,))
    batch = lead_dedup.export_batch()
    decisions = dedup_decisions(batch, "consolidate")
    before = dump(selected)
    assert lead_dedup.apply_decisions(batch, decisions, dry_run=True)["applied"] == 1
    assert dump(selected) == before
    assert lead_dedup.apply_decisions(batch, decisions)["dead_ended"] == 1
    after = dump(selected)
    assert lead_dedup.apply_decisions(batch, decisions)["skipped_already_applied"] == 1
    assert dump(selected) == after
    with sqlite3.connect(selected) as db:
        note = db.execute("SELECT note FROM lead_notes WHERE lead_id=?", (keeper,)).fetchone()[0]
        assert "ESSENTIAL END" in note and "$750,000" in note
        assert f"lead #{source}" in note
        assert db.execute("SELECT evidence_ref FROM lead_evidence WHERE lead_id=?", (keeper,)).fetchone()[0] == "https://example.org/evidence"
    db = lead_dedup.get_db()
    try:
        assert lead_dedup._verify(db, "alpha", 15)["issues"] == []
    finally:
        db.close()


def test_ninety_groups_complete_without_shrinking_offset_skips(review_dbs):
    _, selected = review_dbs
    for index in range(90):
        for _ in range(2):
            add_lead(selected, status="open", target=f"Group Corporation {index:04}")
    reviewed = []
    for expected in (90, 30):
        # All wave exports happen before any apply; each subsequent wave resets offsets.
        packets = [lead_dedup.export_batch(batch_size=20, offset=offset) for offset in (0, 20, 40)]
        assert packets[0]["unprocessed_count"] == expected
        for packet in packets:
            result = lead_dedup.apply_decisions(packet, dedup_decisions(packet))
            reviewed.extend(group["group_hash"] for group in packet["groups"])
            assert result["applied"] == len(packet["groups"])
    assert len(reviewed) == len(set(reviewed)) == 90
    assert lead_dedup.export_batch()["unprocessed_count"] == 0


def test_same_target_and_depth_preserve_distinct_questions_and_scoped_signals(review_dbs):
    _, selected = review_dbs
    current = add_lead(selected, title="Which court claims concern this company?")
    related = add_lead(selected, title="Who owns this company?", status="open")
    add_lead(selected, title="Other profile", status="open", profile="beta")
    with sqlite3.connect(selected) as db:
        for index in range(10):
            db.execute("INSERT INTO findings (target_name,summary,profile_id) VALUES ('Example Company',?,'alpha')", (f"Fragment {index}",))
        for index in range(12):
            db.execute("INSERT INTO connections (person_a,person_b,profile_id) VALUES ('Example Company',?,'beta')", (f"Somebody {index}",))
    db = lead_dedup.get_db()
    try:
        overlaps = triage_policy.candidate_overlaps("Example Company", db, lead_id=current)
        assert [row["id"] for row in overlaps] == [related]
        stop, reason = triage_policy.should_dead_end("Example Company", "standard", None, db)
        assert stop is False and "Review" in reason
        assert triage_policy._get_structural_signals("Example Company", db)["connections"] == 0
    finally:
        db.close()
    result = lead_tracker.apply_triage_decisions(lead_tracker.export_triage_batch(), [promote(current)])
    assert result["actions"]["promote"] == 1


def test_tampered_snapshot_membership_is_rejected(review_dbs):
    _, selected = review_dbs
    for _ in range(2):
        add_lead(selected, status="open")
    packet = lead_dedup.export_batch()
    tampered = copy.deepcopy(packet)
    tampered["groups"][0]["lead_ids"].append(99999)
    baseline = dump(selected)
    with pytest.raises(ValueError, match="hash"):
        lead_dedup.apply_decisions(tampered, dedup_decisions(packet))
    assert dump(selected) == baseline


def test_unknown_categories_use_general_research_routes():
    assert triage_policy.recommend_skill("standard", "novel_question") == "/pursue-lead"
    assert triage_policy.recommend_skill("deep_dive", "novel_question") == "/deep-investigate"
    assert triage_policy.recommend_skill("standard", "contract") == "/analyze-contract"


def test_dedup_rejects_packet_content_changed_without_updating_revision(review_dbs):
    _, selected = review_dbs
    add_lead(selected, status="open")
    add_lead(selected, status="open", description="Original supporting description")
    packet = lead_dedup.export_batch()
    packet["groups"][0]["leads"][1]["description"] = "Invented detail after export"
    baseline = dump(selected)
    with pytest.raises(ValueError, match="changed since export"):
        lead_dedup.apply_decisions(packet, dedup_decisions(packet, "consolidate"))
    assert dump(selected) == baseline


def test_triage_requires_an_unchanged_reviewed_external_keeper(review_dbs):
    _, selected = review_dbs
    victim = add_lead(selected)
    keeper = add_lead(selected, status="open")
    decision = {"lead_id": victim, "action": "dead_end", "keeper_id": keeper,
                "stop_reason": "Duplicate", "rationale": "Same question and scope."}
    with pytest.raises(ValueError, match="reference-lead-id"):
        lead_tracker.apply_triage_decisions(lead_tracker.export_triage_batch(), [decision])
    batch = lead_tracker.export_triage_batch(reference_lead_ids=[keeper])
    with sqlite3.connect(selected) as db:
        db.execute("UPDATE leads SET title='An unrelated court question' WHERE id=?", (keeper,))
    baseline = dump(selected)
    with pytest.raises(ValueError, match="changed since export"):
        lead_tracker.apply_triage_decisions(batch, [decision])
    assert dump(selected) == baseline
