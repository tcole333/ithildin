import json
import sqlite3
import sys

import pytest

from tools import lead_tracker


@pytest.fixture
def scoped_lead_db(monkeypatch, tmp_path):
    db_path = tmp_path / "investigation.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(
        lead_tracker,
        "_profile_thread_id_map",
        lambda profile_id: {1: 61} if profile_id == "allbirds" else {},
    )
    db = lead_tracker.get_db()
    db.executemany(
        "INSERT INTO investigation_threads (id, title, profile_id) "
        "VALUES (?, ?, ?)",
        [
            (1, "Epstein Core Network", "epstein"),
            (61, "Financing Counterparties", "allbirds"),
            (900, "Tech thread", "tech-right"),
        ],
    )
    db.commit()
    db.close()
    return db_path


def _lead_row(db_path, lead_id):
    db = sqlite3.connect(db_path)
    row = db.execute(
        "SELECT profile_id, thread_id, status FROM leads WHERE id = ?",
        (lead_id,),
    ).fetchone()
    db.close()
    return row


def test_add_lead_maps_profile_local_thread_to_global(scoped_lead_db):
    lead_id = lead_tracker.add_lead(
        "Allbirds financing counterparty",
        profile_id="allbirds",
        thread_id=1,
    )

    assert _lead_row(scoped_lead_db, lead_id) == ("allbirds", 61, "open")


def test_matching_global_thread_does_not_load_local_profile_map(
    scoped_lead_db, monkeypatch
):
    monkeypatch.setattr(
        lead_tracker,
        "_profile_thread_id_map",
        lambda _profile_id: pytest.fail(
            "matching global IDs must not load the local-thread map"
        ),
    )

    lead_id = lead_tracker.add_lead(
        "Already globally threaded",
        profile_id="allbirds",
        thread_id=61,
    )

    assert _lead_row(scoped_lead_db, lead_id) == ("allbirds", 61, "open")


def test_add_lead_rejects_cross_profile_global_thread(scoped_lead_db):
    with pytest.raises(ValueError, match="belongs to profile 'tech-right'"):
        lead_tracker.add_lead(
            "Wrongly threaded lead",
            profile_id="allbirds",
            thread_id=900,
        )

    db = sqlite3.connect(scoped_lead_db)
    assert db.execute(
        "SELECT COUNT(*) FROM leads WHERE title = 'Wrongly threaded lead'"
    ).fetchone()[0] == 0
    db.close()


def test_thread_assign_accepts_profile_local_thread(scoped_lead_db):
    lead_id = lead_tracker.add_lead(
        "Unthreaded Allbirds lead",
        profile_id="allbirds",
    )

    assert lead_tracker.assign_lead_thread(lead_id, 1)
    assert _lead_row(scoped_lead_db, lead_id) == ("allbirds", 61, "open")


def test_show_cli_validates_explicit_profile(
    scoped_lead_db, monkeypatch, tmp_path, capsys
):
    lead_id = lead_tracker.add_lead(
        "Profile-scoped exact lookup",
        profile_id="allbirds",
    )
    output_path = tmp_path / "lead.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lead_tracker.py",
            "show",
            str(lead_id),
            "--profile",
            "allbirds",
            "--output",
            str(output_path),
        ],
    )

    lead_tracker.main()

    assert json.loads(output_path.read_text())["profile_id"] == "allbirds"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lead_tracker.py",
            "show",
            str(lead_id),
            "--profile",
            "epstein",
        ],
    )
    with pytest.raises(SystemExit):
        lead_tracker.main()
    assert f"Lead #{lead_id} not found in profile 'epstein'." in capsys.readouterr().out


def test_claim_cli_cannot_cross_explicit_profile(
    scoped_lead_db, monkeypatch, capsys
):
    lead_id = lead_tracker.add_lead(
        "Profile-scoped claim",
        profile_id="allbirds",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lead_tracker.py",
            "claim",
            str(lead_id),
            "--profile",
            "epstein",
        ],
    )

    with pytest.raises(SystemExit):
        lead_tracker.main()

    assert _lead_row(scoped_lead_db, lead_id) == ("allbirds", None, "open")
    assert f"Lead #{lead_id} not found in profile 'epstein'." in capsys.readouterr().err

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lead_tracker.py",
            "claim",
            str(lead_id),
            "--profile",
            "allbirds",
        ],
    )
    lead_tracker.main()
    assert _lead_row(scoped_lead_db, lead_id) == (
        "allbirds",
        None,
        "in_progress",
    )
