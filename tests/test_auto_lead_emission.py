"""Regression tests for auto-lead emission from cross-reference tools.

These cover the phantom-`notes`-column bug: query_icij (reconcile-all),
query_opensanctions (FtM reconcile), and query_sec_enforcement (cross-ref)
previously emitted leads with a raw INSERT into a nonexistent ``leads.notes``
column — plus an integer priority and/or an invalid category — which raised
``sqlite3.OperationalError`` at runtime (or was silently swallowed). All three
now route through ``auto_leads.create_lead()``, which hard-codes
``status='pending_triage'`` and writes the note to the ``lead_notes`` table.

The tests build a fresh DB from the real ``lead_tracker`` schema, so a
reintroduced missing-column / bad-priority / bad-category regression fails here.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def inv_db(tmp_path, monkeypatch):
    """Fresh investigation DB with the real leads/lead_notes schema."""
    db_path = tmp_path / "investigation.db"
    monkeypatch.setattr("tools.lead_tracker.DB_PATH", db_path)
    monkeypatch.setattr("tools.lead_tracker._schema_initialized", False)
    # Reset the per-run lead counter so create_lead()'s 100-lead cap doesn't
    # bleed across tests sharing the pytest process.
    monkeypatch.setattr("tools.auto_leads._leads_created_this_run", 0)
    from tools.lead_tracker import get_db

    db = get_db()
    yield db, db_path
    db.close()


def _lead_rows(db):
    return db.execute(
        """SELECT id, title, description, category, priority, status, source,
           target_name FROM leads"""
    ).fetchall()


def _note_for(db, lead_id):
    row = db.execute(
        "SELECT note FROM lead_notes WHERE lead_id = ?", (lead_id,)
    ).fetchone()
    return row["note"] if row else None


# ── ICIJ offshore-leaks reconcile-all ────────────────────────────────────────

def _icij_match():
    return {
        "our_name": "Acme Holdings",
        "our_source": "entity #1",
        "icij_name": "ACME HOLDINGS LTD",
        "icij_id": "80012345",
        "score": 97.5,
        "match": True,
        "type": ["entity"],
    }


def test_icij_lead_emission_writes_lead_and_note(inv_db):
    db, _ = inv_db
    from tools.query_icij import create_icij_leads

    created = create_icij_leads(db, [_icij_match()])
    assert created == 1

    rows = _lead_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "pending_triage"
    assert row["priority"] in ("critical", "high", "medium", "low")
    assert row["target_name"] == "Acme Holdings"
    assert row["source"] == "agent:icij_reconcile"
    # The note must land in lead_notes — never a (nonexistent) leads.notes column.
    note = _note_for(db, row["id"])
    assert note is not None
    assert "ICIJ ID: 80012345" in note
    assert row["description"] == note


def test_icij_lead_emission_dedupes(inv_db):
    db, _ = inv_db
    from tools.query_icij import create_icij_leads

    assert create_icij_leads(db, [_icij_match()]) == 1
    db.commit()
    # Re-running with the same match must not create a duplicate.
    assert create_icij_leads(db, [_icij_match()]) == 0
    assert len(_lead_rows(db)) == 1


# ── OpenSanctions FtM reconcile ──────────────────────────────────────────────

def test_opensanctions_lead_emission_writes_lead_and_note(inv_db):
    db, _ = inv_db
    from tools.query_opensanctions import create_opensanctions_leads

    match = {
        "our_name": "Ivan Petrov",
        "our_source": "connection",
        "os_id": "NK-abc123",
        "os_caption": "Ivan PETROV",
        "os_schema": "Person",
        "score": 92,
        "topics": ["sanction"],
        "datasets": ["us_ofac_sdn"],
        "countries": ["ru"],
    }
    created = create_opensanctions_leads(db, [match])
    assert created == 1

    row = _lead_rows(db)[0]
    assert row["status"] == "pending_triage"
    assert row["priority"] in ("critical", "high", "medium", "low")
    assert row["category"] == "person"  # os_schema == "Person"
    assert row["source"] == "agent:opensanctions_reconcile"
    note = _note_for(db, row["id"])
    assert note is not None and "OS ID: NK-abc123" in note


def test_opensanctions_company_schema_maps_to_entity_category(inv_db):
    db, _ = inv_db
    from tools.query_opensanctions import create_opensanctions_leads

    match = {
        "our_name": "Petrov Group LLC",
        "our_source": "entity #2",
        "os_id": "NK-def456",
        "os_caption": "PETROV GROUP",
        "os_schema": "Company",
        "score": 90,
        "topics": ["pep"],
        "datasets": ["everypolitician"],
        "countries": ["ru"],
    }
    assert create_opensanctions_leads(db, [match]) == 1
    assert _lead_rows(db)[0]["category"] == "entity"


# ── SEC enforcement cross-reference ──────────────────────────────────────────

def test_sec_enforcement_lead_emission(inv_db, monkeypatch):
    db, db_path = inv_db
    import tools.query_sec_enforcement as qse

    # The function opens its own connection via lead_tracker.get_db() and gates
    # on INVESTIGATION_DB.exists(); point that at the temp DB (DB_PATH is already
    # patched on lead_tracker by the inv_db fixture).
    monkeypatch.setattr(qse, "INVESTIGATION_DB", db_path)

    match = {
        "defendant_name": "John Q. Defendant",
        "release_number": "34-99999",
        "source_type": "AP",
        "check_source": "registry_officer",
        "check_name": "John Q. Defendant",
        "date_published": "2024-01-15",
        "respondent_text": "Order against John Q. Defendant for fraud.",
        "match_score": 0.97,
    }
    created = qse._create_enforcement_leads([match])
    assert created == 1

    rows = _lead_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "pending_triage"
    assert row["category"] == "legal"  # was an invalid 'enforcement' category
    assert row["priority"] == "high"  # match_score >= 0.95
    assert row["source"] == "agent:sec_enforcement_crossref"
    note = _note_for(db, row["id"])
    assert note is not None and "Cross-reference match" in note


def test_sec_enforcement_skips_below_threshold(inv_db, monkeypatch):
    db, db_path = inv_db
    import tools.query_sec_enforcement as qse

    monkeypatch.setattr(qse, "INVESTIGATION_DB", db_path)
    match = {
        "defendant_name": "Weak Match",
        "release_number": "34-11111",
        "source_type": "AP",
        "check_source": "entity",
        "check_name": "Weak Match",
        "date_published": "2024-02-01",
        "respondent_text": "",
        "match_score": 0.50,  # below the 0.85 gate
    }
    assert qse._create_enforcement_leads([match]) == 0
    assert len(_lead_rows(db)) == 0
