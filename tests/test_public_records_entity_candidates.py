import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools.public_records_entity_candidates import (
    DecisionConflictError,
    PublicRecordsEntityCandidates,
    normalize_name,
)
from tools.public_records_store import connect_courts, connect_property


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "public_records_entity_candidates.py"


def _create_core_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT,
            jurisdiction TEXT,
            ein TEXT,
            address TEXT
        );
        CREATE TABLE entity_addresses (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            address_type TEXT
        );
        CREATE TABLE name_aliases (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            alias TEXT NOT NULL,
            alias_type TEXT,
            entity_id INTEGER
        );
        INSERT INTO entities
            (id, name, entity_type, jurisdiction, ein, address)
        VALUES
            (1, 'Example Holdings LLC', 'llc', 'Delaware', '12-3456789',
             '10 Main Street, Albany, NY'),
            (2, 'Example Holdings LLC', 'llc', 'Nevada', '98-7654321',
             '200 Other Road, Reno, NV'),
            (3, 'Other Company Inc', 'inc', 'Delaware', NULL, NULL);
        INSERT INTO entity_addresses
            (id, entity_id, address, address_type)
        VALUES
            (1, 1, '99 Registered Agent Way', 'registered');
        INSERT INTO name_aliases
            (id, canonical_name, alias, alias_type, entity_id)
        VALUES
            (1, 'Example Holdings LLC', 'Example Hldgs., LLC',
             'entity_variant', 1),
            (2, 'Other Company Inc', 'Other Co', 'entity_variant', NULL);
        """
    )
    db.commit()
    db.close()


def _create_property_db(path):
    db = connect_property(path)
    db.execute(
        """
        INSERT INTO jurisdiction(geoid, name, jurisdiction_type, state_code)
        VALUES ('36001', 'Albany County', 'county', 'NY')
        """
    )
    parcel_id = db.execute(
        """
        INSERT INTO parcel_snapshot(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year
        ) VALUES ('test-assessor', '36001', 'P-1', '2026')
        """
    ).lastrowid
    db.execute(
        """
        INSERT INTO parcel_address(
            parcel_id, address_role, raw_address, source_id
        ) VALUES (?, 'mailing', '10 Main Street, Albany, NY', 'test-assessor')
        """,
        (parcel_id,),
    )
    db.execute(
        """
        INSERT INTO ownership_assertion(
            parcel_id, source_id, assertion_type, raw_owner_name,
            normalized_owner_name, confidence, claim_type
        ) VALUES (
            ?, 'test-assessor', 'assessment_roll', 'EXAMPLE HOLDINGS LLC',
            'example holdings llc', 'high', 'paraphrase'
        )
        """,
        (parcel_id,),
    )
    instrument_id = db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id
        ) VALUES ('test-recorder', '36001', 'D-1')
        """
    ).lastrowid
    db.execute(
        """
        INSERT INTO instrument_party(
            instrument_id, role, raw_name, normalized_name, raw_address
        ) VALUES (
            ?, 'grantee', 'Example Hldgs., LLC', 'example hldgs llc',
            '99 Registered Agent Way'
        )
        """,
        (instrument_id,),
    )
    db.commit()
    db.close()


def _create_court_db(path):
    db = connect_courts(path)
    db.execute(
        """
        INSERT INTO court(
            court_id, source_id, native_court_id, name, state_code
        ) VALUES ('test-court', 'test-source', '1', 'Test Court', 'NY')
        """
    )
    case_id = db.execute(
        """
        INSERT INTO case_record(
            source_id, court_id, raw_case_number, caption
        ) VALUES ('test-source', 'test-court', 'CV-1', 'Other Co v. Example')
        """
    ).lastrowid
    db.execute(
        """
        INSERT INTO case_party(
            case_id, role, raw_name, normalized_name
        ) VALUES (?, 'plaintiff', 'Other Co', 'other co')
        """,
        (case_id,),
    )
    db.commit()
    db.close()


@pytest.fixture
def databases(tmp_path):
    paths = {
        "candidate": tmp_path / "candidates.db",
        "property": tmp_path / "property.db",
        "court": tmp_path / "court.db",
        "core": tmp_path / "core.db",
    }
    _create_core_db(paths["core"])
    _create_property_db(paths["property"])
    _create_court_db(paths["court"])
    return paths


def _generate(store, paths):
    return store.generate(
        property_db=paths["property"],
        court_db=paths["court"],
        core_db=paths["core"],
    )


def test_conservative_name_normalization():
    assert normalize_name(" Example Holdings, L.L.C. ") == (
        "example holdings l l c"
    )
    assert normalize_name("Smith & Jones") == "smith and jones"


def test_generate_preserves_all_exact_name_and_alias_candidates(databases):
    with PublicRecordsEntityCandidates(databases["candidate"]) as store:
        result = _generate(store, databases)
        candidates = store.list_candidates()

    assert result["records_observed"] == 3
    assert result["new_candidates"] == 4
    assert len(candidates) == 4
    owner_candidates = [
        item for item in candidates if item["record_type"] == "ownership_assertion"
    ]
    assert {item["core_entity_id"] for item in owner_candidates} == {1, 2}
    by_entity = {item["core_entity_id"]: item for item in owner_candidates}
    assert {
        signal["type"] for signal in by_entity[1]["signals"]
    } == {"entity_name_exact", "address_exact"}
    assert {
        signal["type"] for signal in by_entity[2]["signals"]
    } == {"entity_name_exact"}

    instrument = next(
        item for item in candidates if item["record_type"] == "instrument_party"
    )
    assert instrument["core_entity_id"] == 1
    assert {signal["type"] for signal in instrument["signals"]} == {
        "alias_exact",
        "address_exact",
    }
    court = next(item for item in candidates if item["record_type"] == "case_party")
    assert court["core_entity_id"] == 3
    assert court["signals"][0]["alias_resolution"] == "alias_canonical_name"


def test_generation_is_idempotent_but_keeps_run_history(databases):
    with PublicRecordsEntityCandidates(databases["candidate"]) as store:
        first = _generate(store, databases)
        second = _generate(store, databases)
        candidates = store.list_candidates()
        run_count = store.db.execute(
            "SELECT COUNT(*) FROM generation_run"
        ).fetchone()[0]

    assert first["new_candidates"] == 4
    assert second["new_candidates"] == 0
    assert second["signal_observations_added"] == 0
    assert len(candidates) == 4
    assert run_count == 2


def test_accept_links_sidecar_and_undo_restores_prior_state(databases):
    with PublicRecordsEntityCandidates(databases["candidate"]) as store:
        _generate(store, databases)
        candidate = next(
            item
            for item in store.list_candidates()
            if item["record_type"] == "instrument_party"
        )
        accepted = store.decide(
            candidate["candidate_id"],
            action="accept",
            actor="analyst:test",
            reason="name and registered address agree",
            resolution_confidence=0.93,
            metadata={"review_ref": "review-1"},
        )

        property_db = sqlite3.connect(databases["property"])
        linked = property_db.execute(
            """
            SELECT core_entity_id, resolution_confidence, resolution_status
            FROM instrument_party
            """
        ).fetchone()
        property_db.close()
        assert linked == (1, 0.93, "accepted_candidate")
        assert accepted["candidate"]["state"] == "accepted"
        assert accepted["link_mutations"][0]["prior_state"]["core_entity_id"] is None

        undone = store.decide(
            candidate["candidate_id"],
            action="undo",
            actor="analyst:test",
            reason="recheck requested",
        )
        property_db = sqlite3.connect(databases["property"])
        restored = property_db.execute(
            """
            SELECT core_entity_id, resolution_confidence, resolution_status
            FROM instrument_party
            """
        ).fetchone()
        property_db.close()

    assert restored == (None, None, "unreviewed")
    assert undone["candidate"]["state"] == "open"
    assert [event["action"] for event in undone["decisions"]] == ["accept", "undo"]
    assert undone["link_mutations"][1]["reverses_mutation_id"] == undone[
        "link_mutations"
    ][0]["mutation_id"]


def test_ownership_accept_and_undo_only_changes_owned_link_field(databases):
    with PublicRecordsEntityCandidates(databases["candidate"]) as store:
        _generate(store, databases)
        candidate = next(
            item
            for item in store.list_candidates()
            if item["record_type"] == "ownership_assertion"
            and item["core_entity_id"] == 1
        )
        store.decide(
            candidate["candidate_id"],
            action="accept",
            actor="analyst:test",
        )
        db = sqlite3.connect(databases["property"])
        accepted = db.execute(
            """
            SELECT core_entity_id, confidence, claim_type
            FROM ownership_assertion
            """
        ).fetchone()
        db.close()
        assert accepted == (1, "high", "paraphrase")

        store.decide(
            candidate["candidate_id"],
            action="undo",
            actor="analyst:test",
        )
        db = sqlite3.connect(databases["property"])
        restored = db.execute(
            """
            SELECT core_entity_id, confidence, claim_type
            FROM ownership_assertion
            """
        ).fetchone()
        db.close()
    assert restored == (None, "high", "paraphrase")


def test_reject_reopen_and_undo_are_append_only(databases):
    with PublicRecordsEntityCandidates(databases["candidate"]) as store:
        _generate(store, databases)
        candidate = store.list_candidates()[0]
        store.decide(
            candidate["candidate_id"],
            action="reject",
            actor="analyst:test",
            reason="wrong jurisdiction",
        )
        store.decide(
            candidate["candidate_id"],
            action="reopen",
            actor="analyst:test",
        )
        history = store.decide(
            candidate["candidate_id"],
            action="undo",
            actor="analyst:test",
        )
        assert history["candidate"]["state"] == "rejected"
        assert [item["action"] for item in history["decisions"]] == [
            "reject",
            "reopen",
            "undo",
        ]
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.db.execute(
                "UPDATE decision_event SET actor = 'changed' WHERE decision_id = 1"
            )


def test_undo_detects_external_link_change(databases):
    with PublicRecordsEntityCandidates(databases["candidate"]) as store:
        _generate(store, databases)
        candidate = next(
            item
            for item in store.list_candidates()
            if item["record_type"] == "instrument_party"
        )
        store.decide(
            candidate["candidate_id"],
            action="accept",
            actor="analyst:test",
        )
        db = sqlite3.connect(databases["property"])
        db.execute("UPDATE instrument_party SET core_entity_id = 2")
        db.commit()
        db.close()
        with pytest.raises(DecisionConflictError, match="changed after"):
            store.decide(
                candidate["candidate_id"],
                action="undo",
                actor="analyst:test",
            )


def test_rejecting_an_accepted_candidate_requires_explicit_undo(databases):
    with PublicRecordsEntityCandidates(databases["candidate"]) as store:
        _generate(store, databases)
        candidate = store.list_candidates()[0]
        store.decide(
            candidate["candidate_id"],
            action="accept",
            actor="analyst:test",
        )
        with pytest.raises(DecisionConflictError, match="undo"):
            store.decide(
                candidate["candidate_id"],
                action="reject",
                actor="analyst:test",
            )


def test_direct_script_generate_list_decide_and_history(databases, tmp_path):
    generate_output = tmp_path / "generate.json"
    generated = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "generate",
            "--property-db",
            str(databases["property"]),
            "--court-db",
            str(databases["court"]),
            "--core-db",
            str(databases["core"]),
            "--db",
            str(databases["candidate"]),
            "--output",
            str(generate_output),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    assert json.loads(generate_output.read_text())["new_candidates"] == 4

    list_output = tmp_path / "list.json"
    listed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "list",
            "--record-type",
            "case_party",
            "--db",
            str(databases["candidate"]),
            "--output",
            str(list_output),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    candidate = json.loads(list_output.read_text())["candidates"][0]

    decision_output = tmp_path / "decision.json"
    decided = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "decide",
            str(candidate["candidate_id"]),
            "--action",
            "reject",
            "--actor",
            "cli-test",
            "--db",
            str(databases["candidate"]),
            "--output",
            str(decision_output),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert decided.returncode == 0, decided.stderr
    assert json.loads(decision_output.read_text())["candidate"]["state"] == "rejected"

    history = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "history",
            str(candidate["candidate_id"]),
            "--db",
            str(databases["candidate"]),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert history.returncode == 0, history.stderr
    assert json.loads(history.stdout)["decisions"][0]["action"] == "reject"
