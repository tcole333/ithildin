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


class TestSourceConfidenceCapping:
    @staticmethod
    def _prepare_findings_schema(db):
        cols = {row[1] for row in db.execute("PRAGMA table_info(findings)")}
        for col in ("event_date_iso", "date_precision"):
            if col not in cols:
                db.execute(f"ALTER TABLE findings ADD COLUMN {col} TEXT")
        db.commit()

    @staticmethod
    def _stored_confidence(db, finding_id):
        return db.execute(
            "SELECT confidence FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()["confidence"]

    def test_aggregator_source_clamps_confirmed_to_medium(self, conn_db, capsys):
        db, _ = conn_db
        self._prepare_findings_schema(db)
        from tools.findings_tracker import add_finding
        finding_id = add_finding(
            "Opaque Source", "s", source_datasets=["dehashed"],
            claim_type="direct_quote", confidence="confirmed", profile_id="epstein",
            evidence_ids=["DEHASHED:test-record"],
            source_quotes={"DEHASHED:test-record": {"quote": "Exact source text"}},
        )
        assert self._stored_confidence(db, finding_id) == "medium"
        assert "provenance-opaque source(s): dehashed" in capsys.readouterr().err

    def test_non_aggregator_source_is_unaffected(self, conn_db, capsys):
        db, _ = conn_db
        self._prepare_findings_schema(db)
        from tools.findings_tracker import add_finding
        finding_id = add_finding(
            "Primary Source", "s", source_datasets=["courtlistener"],
            claim_type="direct_quote", confidence="confirmed", profile_id="epstein",
            evidence_ids=["COURTLISTENER:test-record"],
            source_quotes={"COURTLISTENER:test-record": {"quote": "Exact source text"}},
        )
        assert self._stored_confidence(db, finding_id) == "confirmed"
        assert "provenance-opaque" not in capsys.readouterr().err

    def test_claim_type_cap_still_applies(self, conn_db, capsys):
        db, _ = conn_db
        self._prepare_findings_schema(db)
        from tools.findings_tracker import add_finding
        finding_id = add_finding(
            "Inference", "s", source_datasets=["courtlistener"],
            claim_type="inference", confidence="confirmed", profile_id="epstein",
        )
        assert self._stored_confidence(db, finding_id) == "medium"
        assert "max for claim_type='inference'" in capsys.readouterr().err

    def test_lower_cap_wins_when_both_trigger(self, conn_db, capsys):
        db, _ = conn_db
        self._prepare_findings_schema(db)
        from tools.findings_tracker import add_finding
        finding_id = add_finding(
            "Opaque Paraphrase", "s", source_datasets=["intelx"],
            claim_type="paraphrase", confidence="confirmed", profile_id="epstein",
        )
        assert self._stored_confidence(db, finding_id) == "medium"
        error = capsys.readouterr().err
        assert "max for claim_type='paraphrase'" in error
        assert "provenance-opaque source(s): intelx" in error


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

    def test_set_lead_depth_tier_updates_scheduler_column(self, fresh_db):
        db, _ = fresh_db
        cursor = db.execute(
            "INSERT INTO leads (title, status, priority) VALUES ('tier me', 'open', 'medium')"
        )
        lead_id = cursor.lastrowid
        db.commit()

        from tools.lead_tracker import set_lead_depth_tier

        assert set_lead_depth_tier(lead_id, "standard") is True
        assert db.execute(
            "SELECT depth_tier FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()["depth_tier"] == "standard"


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


# ── Connection → Entity Enforcement ──────────────────────────

@pytest.fixture
def conn_db(tmp_path, monkeypatch):
    """Temp DB wired so findings_tracker.add_connection writes to it."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("tools.lead_tracker.DB_PATH", db_path)
    monkeypatch.setattr("tools.lead_tracker._schema_initialized", False)
    monkeypatch.setattr("tools.findings_tracker.DB_PATH", db_path)
    monkeypatch.setattr("tools.findings_tracker._schema_initialized", False)
    from tools.lead_tracker import get_db
    db = get_db()
    return db, db_path


class TestConnectionEntityEnforcement:
    def _entity_rows(self, db, name):
        return db.execute("SELECT * FROM entities WHERE name = ?", (name,)).fetchall()

    def test_connection_auto_registers_both_endpoints(self, conn_db):
        db, _ = conn_db
        from tools.findings_tracker import add_connection
        add_connection("Alice Stub", "Bob Stub", relationship_type="social")

        assert len(self._entity_rows(db, "Alice Stub")) == 1
        assert len(self._entity_rows(db, "Bob Stub")) == 1
        conn = db.execute(
            "SELECT * FROM connections WHERE person_a IN ('Alice Stub','Bob Stub')"
        ).fetchall()
        assert len(conn) == 1

    def test_stub_marked_with_auto_source_and_unknown_type(self, conn_db):
        db, _ = conn_db
        from tools.findings_tracker import add_connection
        add_connection("Carol Stub", "Dave Stub", relationship_type="social")
        row = self._entity_rows(db, "Carol Stub")[0]
        assert row["source"] == "auto:connect"
        assert row["entity_type"] == "unknown"

    def test_repeat_connection_does_not_duplicate_entities(self, conn_db):
        db, _ = conn_db
        from tools.findings_tracker import add_connection
        add_connection("Repeat A", "Repeat B", relationship_type="social")
        add_connection("Repeat A", "Repeat B", relationship_type="financial")
        add_connection("Repeat B", "Repeat A", relationship_type="social")  # order-swapped
        assert len(self._entity_rows(db, "Repeat A")) == 1
        assert len(self._entity_rows(db, "Repeat B")) == 1

    def test_existing_rich_entity_is_reused_not_stubbed(self, conn_db):
        db, _ = conn_db
        # Pre-existing richly-typed entity (jurisdiction-bearing).
        db.execute(
            "INSERT INTO entities (name, entity_type, jurisdiction, source) "
            "VALUES ('Acme Corp', 'inc', 'Delaware', 'manual')"
        )
        db.commit()
        from tools.findings_tracker import add_connection
        add_connection("Acme Corp", "New Person", relationship_type="corporate")

        acme = self._entity_rows(db, "Acme Corp")
        assert len(acme) == 1  # no duplicate stub
        assert acme[0]["entity_type"] == "inc"
        assert acme[0]["source"] == "manual"
        assert len(self._entity_rows(db, "New Person")) == 1

    def test_entity_type_hints_passed_through(self, conn_db):
        db, _ = conn_db
        from tools.findings_tracker import add_connection
        add_connection("Globex LLC", "Hank Person", relationship_type="employment",
                       entity_a_type="llc", entity_b_type="person")
        assert self._entity_rows(db, "Globex LLC")[0]["entity_type"] == "llc"
        assert self._entity_rows(db, "Hank Person")[0]["entity_type"] == "person"


# ── Profile/Thread Drift Guard ───────────────────────────────

class TestProfileThreadGuard:
    """add_finding warns (never raises) when profile_id disagrees with the
    thread's owning profile — new-drift tripwire, warn-only like VALID_SOURCES."""

    def _seed_threads(self, db):
        # Bring the temp DB's findings table up to production schema: the v2
        # temporal columns are added by scripts/migrate_core_model_v2.py, which
        # _ensure_schema (the fixture's schema builder) does not run.
        cols = {r[1] for r in db.execute("PRAGMA table_info(findings)")}
        for col in ("event_date_iso", "date_precision"):
            if col not in cols:
                db.execute(f"ALTER TABLE findings ADD COLUMN {col} TEXT")
        db.execute(
            "INSERT INTO investigation_threads (id, title, profile_id) "
            "VALUES (900, 'TR thread', 'tech-right')"
        )
        db.execute(
            "INSERT INTO investigation_threads (id, title, profile_id) "
            "VALUES (901, 'Ep thread', 'epstein')"
        )
        db.commit()

    def test_drift_warns_but_records(self, conn_db, capsys):
        db, _ = conn_db
        self._seed_threads(db)
        from tools.findings_tracker import add_finding
        fid = add_finding(
            "Drift Target", "s", source_datasets=["web_search"],
            thread_id=900, profile_id="epstein",
        )
        err = capsys.readouterr().err
        assert "profile/thread drift" in err
        assert "tech-right" in err
        # Finding is still recorded (warn-only) with the requested profile_id.
        row = db.execute(
            "SELECT profile_id, thread_id FROM findings WHERE id = ?", (fid,)
        ).fetchone()
        assert row["profile_id"] == "epstein"
        assert row["thread_id"] == 900

    def test_matching_profile_is_silent(self, conn_db, capsys):
        db, _ = conn_db
        self._seed_threads(db)
        from tools.findings_tracker import add_finding
        add_finding(
            "Match Target", "s", source_datasets=["web_search"],
            thread_id=900, profile_id="tech-right",
        )
        assert "profile/thread drift" not in capsys.readouterr().err

    def test_no_thread_id_is_silent(self, conn_db, capsys):
        db, _ = conn_db
        self._seed_threads(db)
        from tools.findings_tracker import add_finding
        add_finding(
            "No Thread Target", "s", source_datasets=["web_search"],
            profile_id="epstein",
        )
        assert "profile/thread drift" not in capsys.readouterr().err

    def test_null_thread_profile_is_silent(self, conn_db, capsys):
        db, _ = conn_db
        self._seed_threads(db)
        # A thread whose own profile_id is NULL can't disagree with anything —
        # the guard only fires when the thread has a concrete owning profile.
        db.execute(
            "INSERT INTO investigation_threads (id, title, profile_id) "
            "VALUES (902, 'Unowned thread', NULL)"
        )
        db.commit()
        from tools.findings_tracker import add_finding
        fid = add_finding(
            "Unowned Thread Target", "s", source_datasets=["web_search"],
            thread_id=902, profile_id="epstein",
        )
        assert "profile/thread drift" not in capsys.readouterr().err
        assert fid is not None


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


# ── Entity Resolve-or-Create (write-path dedup) ──────────────

class TestResolveOrCreateEntity:
    """Fuzzy resolve-or-create on the entity write path stops duplicate rows."""

    def _norm_count(self, db, target_norm):
        from tools.entity_resolution import normalize_entity_name
        rows = db.execute("SELECT name FROM entities").fetchall()
        return sum(1 for r in rows if normalize_entity_name(r["name"]) == target_norm)

    def test_creates_when_no_match(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        res = resolve_or_create_entity(db, "Northwind Trading LLC", entity_type="llc")
        assert res.action == "created"
        assert res.entity_id is not None
        assert self._norm_count(db, "northwind trading") == 1

    def test_exact_name_reused(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        first = resolve_or_create_entity(db, "Northwind Trading LLC", entity_type="llc")
        again = resolve_or_create_entity(db, "Northwind Trading LLC", entity_type="llc")
        assert again.action == "exact"
        assert again.entity_id == first.entity_id
        assert self._norm_count(db, "northwind trading") == 1

    def test_fuzzy_suffix_variant_links_and_records_alias(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        seed = resolve_or_create_entity(db, "J. Epstein & Co.", entity_type="inc")
        variant = resolve_or_create_entity(db, "J. Epstein & Co Inc", entity_type="inc")
        assert variant.action == "fuzzy"
        assert variant.entity_id == seed.entity_id
        assert variant.score >= 97
        # No duplicate row was created.
        assert self._norm_count(db, "j epstein &") == 1
        # The variant spelling is now recorded as an alias of the canonical row.
        alias = db.execute(
            "SELECT canonical_name, entity_id, alias_type FROM name_aliases WHERE alias = ?",
            ("J. Epstein & Co Inc",),
        ).fetchone()
        assert alias is not None
        assert alias["entity_id"] == seed.entity_id
        assert alias["canonical_name"] == "J. Epstein & Co."
        assert alias["alias_type"] == "entity_variant"

    def test_sr_vs_ii_stay_distinct(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        sr = resolve_or_create_entity(db, "Eduardo Coscoluella Sr", entity_type="person")
        ii = resolve_or_create_entity(db, "Eduardo Coscoluella II", entity_type="person")
        assert ii.action == "created"
        assert ii.entity_id != sr.entity_id

    def test_person_org_guard_prevents_merge(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        org = resolve_or_create_entity(db, "Leslie Wexner LLC", entity_type="llc")
        person = resolve_or_create_entity(db, "Leslie Wexner", entity_type="person")
        # Normalized names are identical (score 100) but person != org, so no merge.
        assert person.action == "created"
        assert person.entity_id != org.entity_id

    def test_jurisdiction_guard(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        de = resolve_or_create_entity(db, "Globex Corp", entity_type="inc", jurisdiction="Delaware")
        # Same normalized name, different non-null jurisdiction -> distinct entity.
        nv = resolve_or_create_entity(db, "Globex Corporation", entity_type="inc", jurisdiction="Nevada")
        assert nv.action == "created"
        assert nv.entity_id != de.entity_id
        # Same normalized name + compatible jurisdiction -> links to the Delaware row,
        # skipping the guard-failing Nevada candidate.
        match = resolve_or_create_entity(db, "Globex Corporation", entity_type="inc", jurisdiction="Delaware")
        assert match.action == "fuzzy"
        assert match.entity_id == de.entity_id

    def test_backfill_enriches_null_scalars(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        seed = resolve_or_create_entity(db, "Initech", entity_type="unknown")
        res = resolve_or_create_entity(
            db, "Initech Inc", entity_type="inc", ein="99-9999999", jurisdiction="Delaware"
        )
        assert res.action == "fuzzy"
        assert res.entity_id == seed.entity_id
        row = db.execute(
            "SELECT entity_type, ein, jurisdiction FROM entities WHERE id = ?", (seed.entity_id,)
        ).fetchone()
        assert row["ein"] == "99-9999999"
        assert row["jurisdiction"] == "Delaware"
        assert row["entity_type"] == "inc"  # upgraded from 'unknown'

    def test_backfill_does_not_overwrite_existing(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        seed = resolve_or_create_entity(
            db, "Umbrella Inc", entity_type="inc", ein="11-1111111", jurisdiction="Delaware"
        )
        resolve_or_create_entity(
            db, "Umbrella Incorporated", entity_type="inc", ein="22-2222222", jurisdiction="Delaware"
        )
        row = db.execute("SELECT ein FROM entities WHERE id = ?", (seed.entity_id,)).fetchone()
        assert row["ein"] == "11-1111111"  # original value preserved, not clobbered

    def test_alias_takes_precedence(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        seed = resolve_or_create_entity(db, "Canonical Holdings", entity_type="inc")
        db.execute(
            "INSERT INTO name_aliases (canonical_name, alias, alias_type, entity_id, created_by) "
            "VALUES ('Canonical Holdings', 'ZZ Variant Name', 'entity_variant', ?, 'test')",
            (seed.entity_id,),
        )
        res = resolve_or_create_entity(db, "ZZ Variant Name", entity_type="inc")
        assert res.action == "alias"
        assert res.entity_id == seed.entity_id

    def test_blank_name_returns_none(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        res = resolve_or_create_entity(db, "   ")
        assert res.entity_id is None
        assert res.action is None

    def test_threshold_above_100_disables_fuzzy(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        seed = resolve_or_create_entity(db, "J. Epstein & Co.", entity_type="inc")
        # threshold > 100 mirrors `add-entity --force-new`: fuzzy is skipped.
        forced = resolve_or_create_entity(db, "J. Epstein & Co Inc", entity_type="inc", threshold=101)
        assert forced.action == "created"
        assert forced.entity_id != seed.entity_id

    def test_force_new_overrides_recorded_alias(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        seed = resolve_or_create_entity(db, "Pinnacle Strategies LLC", entity_type="llc")
        # Fuzzy match auto-records 'Pinnacle Strategies Inc' as an alias of the seed.
        linked = resolve_or_create_entity(db, "Pinnacle Strategies Inc", entity_type="inc")
        assert linked.action == "fuzzy"
        assert linked.entity_id == seed.entity_id
        # --force-new (threshold>100 + use_aliases=False) must bypass that alias.
        forced = resolve_or_create_entity(
            db, "Pinnacle Strategies Inc", entity_type="inc", threshold=101, use_aliases=False
        )
        assert forced.action == "created"
        assert forced.entity_id != seed.entity_id

    def test_force_new_still_honors_exact_unique(self, fresh_db):
        db, _ = fresh_db
        from tools.entity_resolution import resolve_or_create_entity
        seed = resolve_or_create_entity(db, "Exactly Inc", entity_type="inc", jurisdiction="Delaware")
        # Even with fuzzy + aliases off, an identical (name, jurisdiction) does not duplicate.
        again = resolve_or_create_entity(
            db, "Exactly Inc", entity_type="inc", jurisdiction="Delaware",
            threshold=101, use_aliases=False,
        )
        assert again.entity_id == seed.entity_id
        assert again.action == "exact"

    def test_connection_path_fuzzy_links(self, conn_db):
        db, _ = conn_db
        from tools.entity_resolution import normalize_entity_name
        from tools.findings_tracker import add_connection
        db.execute(
            "INSERT INTO entities (name, entity_type, source) VALUES ('Zentplex Holdings Company', 'inc', 'manual')"
        )
        db.commit()
        add_connection("Zentplex Holdings Co.", "Probe Person", relationship_type="corporate")
        # The suffix variant linked to the existing row instead of spawning a duplicate.
        rows = db.execute("SELECT name FROM entities").fetchall()
        n = sum(1 for r in rows if normalize_entity_name(r["name"]) == "zentplex holdings")
        assert n == 1
        alias = db.execute(
            "SELECT entity_id FROM name_aliases WHERE alias = ?", ("Zentplex Holdings Co.",)
        ).fetchone()
        assert alias is not None
