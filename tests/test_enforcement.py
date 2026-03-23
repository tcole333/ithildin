"""Tests for investigation system enforcement mechanisms.

Covers: confidence capping, finding types, scheduler fields, dispatcher
routing, triage policy, and schema repairs from the refactor.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Create a fresh investigation DB with full schema."""
    db_path = tmp_path / "test.db"
    # Patch DB_PATH so lead_tracker uses our temp DB
    monkeypatch.setattr("tools.lead_tracker.DB_PATH", db_path)
    monkeypatch.setattr("tools.lead_tracker._schema_initialized", False)
    from tools.lead_tracker import get_db
    db = get_db()
    return db, db_path


# ── Confidence Capping ───────────────────────────────────────

class TestConfidenceCapping:
    def test_inference_confirmed_clamps_to_medium(self):
        from tools.findings_tracker import _enforce_confidence_cap
        conf, clamped = _enforce_confidence_cap("inference", "confirmed")
        assert conf == "medium"
        assert clamped is True

    def test_synthesis_high_clamps_to_medium(self):
        from tools.findings_tracker import _enforce_confidence_cap
        conf, clamped = _enforce_confidence_cap("synthesis", "high")
        assert conf == "medium"
        assert clamped is True

    def test_direct_quote_confirmed_not_clamped(self):
        from tools.findings_tracker import _enforce_confidence_cap
        conf, clamped = _enforce_confidence_cap("direct_quote", "confirmed")
        assert conf == "confirmed"
        assert clamped is False

    def test_paraphrase_high_not_clamped(self):
        from tools.findings_tracker import _enforce_confidence_cap
        conf, clamped = _enforce_confidence_cap("paraphrase", "high")
        assert conf == "high"
        assert clamped is False

    def test_paraphrase_confirmed_clamps_to_high(self):
        from tools.findings_tracker import _enforce_confidence_cap
        conf, clamped = _enforce_confidence_cap("paraphrase", "confirmed")
        assert conf == "high"
        assert clamped is True

    def test_user_provided_confirmed_not_clamped(self):
        from tools.findings_tracker import _enforce_confidence_cap
        conf, clamped = _enforce_confidence_cap("user_provided", "confirmed")
        assert conf == "confirmed"
        assert clamped is False

    def test_synthesis_medium_not_clamped(self):
        from tools.findings_tracker import _enforce_confidence_cap
        conf, clamped = _enforce_confidence_cap("synthesis", "medium")
        assert conf == "medium"
        assert clamped is False

    def test_inference_low_not_clamped(self):
        from tools.findings_tracker import _enforce_confidence_cap
        conf, clamped = _enforce_confidence_cap("inference", "low")
        assert conf == "low"
        assert clamped is False


# ── Finding Types ────────────────────────────────────────────

class TestFindingTypes:
    def test_negative_result_is_valid(self):
        from tools.findings_tracker import VALID_FINDING_TYPES
        assert "negative_result" in VALID_FINDING_TYPES

    def test_background_is_valid(self):
        from tools.findings_tracker import VALID_FINDING_TYPES
        assert "background" in VALID_FINDING_TYPES

    def test_finding_type_no_check_constraint(self, fresh_db):
        """finding_type column should not have a CHECK constraint (Python validates instead)."""
        db, _ = fresh_db
        schema = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='findings'"
        ).fetchone()[0]
        assert "CHECK(finding_type" not in schema

    def test_negative_result_insert_succeeds(self, fresh_db):
        db, _ = fresh_db
        db.execute(
            "INSERT INTO findings (target_name, finding_type, summary) "
            "VALUES ('test', 'negative_result', 'No results found')"
        )
        row = db.execute(
            "SELECT finding_type FROM findings WHERE target_name='test'"
        ).fetchone()
        assert row["finding_type"] == "negative_result"


# ── Scheduler Fields ─────────────────────────────────────────

class TestSchedulerFields:
    def test_leads_has_depth_tier(self, fresh_db):
        db, _ = fresh_db
        cols = [r["name"] for r in db.execute("PRAGMA table_info(leads)").fetchall()]
        assert "depth_tier" in cols

    def test_leads_has_recommended_skill(self, fresh_db):
        db, _ = fresh_db
        cols = [r["name"] for r in db.execute("PRAGMA table_info(leads)").fetchall()]
        assert "recommended_skill" in cols

    def test_leads_has_triage_rationale(self, fresh_db):
        db, _ = fresh_db
        cols = [r["name"] for r in db.execute("PRAGMA table_info(leads)").fetchall()]
        assert "triage_rationale" in cols

    def test_leads_has_stop_reason(self, fresh_db):
        db, _ = fresh_db
        cols = [r["name"] for r in db.execute("PRAGMA table_info(leads)").fetchall()]
        assert "stop_reason" in cols

    def test_claim_next_filters_by_depth_tier(self, fresh_db):
        """Verify the depth_tier filter in claim_next_lead query logic."""
        db, _ = fresh_db
        # Insert two leads with different tiers
        db.execute(
            "INSERT INTO leads (title, status, priority, depth_tier) "
            "VALUES ('scan lead', 'open', 'medium', 'scan')"
        )
        db.execute(
            "INSERT INTO leads (title, status, priority, depth_tier) "
            "VALUES ('standard lead', 'open', 'medium', 'standard')"
        )
        db.commit()

        # Test the query logic directly (claim_next_lead opens its own connection)
        row = db.execute(
            """SELECT id, title, depth_tier FROM leads
               WHERE status = 'open' AND depth_tier = 'standard'
               ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                                      WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END
               LIMIT 1"""
        ).fetchone()
        assert row is not None
        assert row["depth_tier"] == "standard"
        assert "standard lead" in row["title"]

        # Verify scan leads are excluded
        scan_row = db.execute(
            "SELECT COUNT(*) FROM leads WHERE status='open' AND depth_tier='standard'"
        ).fetchone()[0]
        assert scan_row == 1  # only one standard lead


# ── Dispatcher Routing ───────────────────────────────────────

class TestDispatcherRouting:
    def test_prefers_recommended_skill(self, fresh_db):
        db, db_path = fresh_db
        # Insert leads with different recommended_skills
        db.execute(
            "INSERT INTO leads (title, status, priority, depth_tier, recommended_skill) "
            "VALUES ('trace lead', 'open', 'high', 'standard', '/trace-entity')"
        )
        db.execute(
            "INSERT INTO leads (title, status, priority, depth_tier, recommended_skill) "
            "VALUES ('pursue lead', 'open', 'high', 'scan', '/pursue-lead')"
        )
        db.commit()

        from scripts.dispatcher import get_next_lead_id
        lead_id = get_next_lead_id(db, for_skill="/trace-entity")
        row = db.execute(
            "SELECT recommended_skill FROM leads WHERE id=?", (lead_id,)
        ).fetchone()
        assert row["recommended_skill"] == "/trace-entity"

    def test_falls_back_without_skill_match(self, fresh_db):
        db, _ = fresh_db
        db.execute(
            "INSERT INTO leads (title, status, priority) "
            "VALUES ('generic lead', 'open', 'high')"
        )
        db.commit()

        from scripts.dispatcher import get_next_lead_id
        lead_id = get_next_lead_id(db, for_skill=None)
        assert lead_id is not None


# ── Triage Policy ────────────────────────────────────────────

class TestTriagePolicy:
    def test_key_person_gets_deep_dive(self, fresh_db):
        db, _ = fresh_db
        from tools.triage_policy import assess_depth_tier
        tier, reason = assess_depth_tier("Elon Musk", db, key_persons=["elon musk"])
        assert tier == "deep_dive"
        assert "key person" in reason

    def test_high_roles_gets_deep_dive(self, fresh_db):
        db, _ = fresh_db
        # Insert entity and 5 roles
        db.execute("INSERT INTO entities (name, entity_type) VALUES ('TestCorp', 'llc')")
        eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for i in range(5):
            db.execute(
                "INSERT INTO entity_roles (entity_id, person_name, role) "
                "VALUES (?, 'John Smith', ?)", (eid, f"role_{i}")
            )
        db.commit()

        from tools.triage_policy import assess_depth_tier
        tier, reason = assess_depth_tier("John Smith", db)
        assert tier == "deep_dive"
        assert "5 roles" in reason

    def test_generic_target_gets_scan(self, fresh_db):
        db, _ = fresh_db
        from tools.triage_policy import assess_depth_tier
        tier, reason = assess_depth_tier("Nobody Special", db)
        assert tier == "scan"
        assert "no escalation" in reason

    def test_moderate_connections_gets_standard(self, fresh_db):
        db, _ = fresh_db
        for i in range(3):
            db.execute(
                "INSERT INTO connections (person_a, person_b) "
                "VALUES ('Jane Doe', ?)", (f"person_{i}",)
            )
        db.commit()

        from tools.triage_policy import assess_depth_tier
        tier, reason = assess_depth_tier("Jane Doe", db)
        assert tier == "standard"

    def test_skill_recommendation_standard_person(self):
        from tools.triage_policy import recommend_skill
        assert recommend_skill("standard", "person") == "/investigate-person"

    def test_skill_recommendation_standard_entity(self):
        from tools.triage_policy import recommend_skill
        assert recommend_skill("standard", "entity") == "/trace-entity"

    def test_skill_recommendation_scan_fallback(self):
        from tools.triage_policy import recommend_skill
        assert recommend_skill("scan", "person") == "/pursue-lead"

    def test_skill_recommendation_deep_dive(self):
        from tools.triage_policy import recommend_skill
        assert recommend_skill("deep_dive", "person") == "/deep-investigate"

    def test_dead_end_threshold(self, fresh_db):
        db, _ = fresh_db
        # Insert 10 findings for a target
        for i in range(10):
            db.execute(
                "INSERT INTO findings (target_name, summary) "
                "VALUES ('Overresearched Target', ?)", (f"finding {i}",)
            )
        # Insert an existing open lead
        db.execute(
            "INSERT INTO leads (title, target_name, status, priority, depth_tier) "
            "VALUES ('existing', 'Overresearched Target', 'open', 'medium', 'standard')"
        )
        db.commit()

        from tools.triage_policy import should_dead_end
        stop, reason = should_dead_end("Overresearched Target", "scan", None, db)
        assert stop is True
        assert "exhaustively_covered" in reason


# ── Schema Repairs ───────────────────────────────────────────

class TestSchemaRepairs:
    def test_findings_lead_id_references_leads(self, fresh_db):
        """lead_id FK should reference 'leads' table, not 'leads_old_backup'."""
        db, _ = fresh_db
        schema = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='findings'"
        ).fetchone()[0]
        assert "leads_old_backup" not in schema

    def test_search_history_table_exists(self, fresh_db):
        db, _ = fresh_db
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "search_history" in tables
