import sqlite3
from types import SimpleNamespace

from tools import investigation_context
from tools import lead_tracker
from tools import profile_threads
from tools import triage_policy


def test_triage_policy_loads_active_profile_metadata(monkeypatch):
    monkeypatch.setattr(
        investigation_context,
        "get_active_profile",
        lambda: SimpleNamespace(
            key_persons=["Carlos Ghosn"],
            known_addresses={"42 Example Street": "test address"},
        ),
    )

    key_persons, known_addresses = triage_policy._load_profile_config()

    assert key_persons == ["Carlos Ghosn"]
    assert known_addresses == {"42 Example Street": "test address"}


def test_lead_search_matches_name_with_intervening_initial(tmp_path, monkeypatch):
    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "investigation.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_id = lead_tracker.add_lead(
        "Review the subject's archived client roster",
        target_name="Brad S. Karp",
        profile_id="brad-karp",
    )

    results = lead_tracker.search_leads("Brad Karp", profile_id="brad-karp")

    assert [result["id"] for result in results] == [lead_id]


def test_explicit_bridge_global_id_precedes_colliding_local_id():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE investigation_threads "
        "(id INTEGER PRIMARY KEY, title TEXT, profile_id TEXT)"
    )
    db.executemany(
        "INSERT INTO investigation_threads(id, title, profile_id) VALUES (?, ?, ?)",
        [
            (3, "Deutsche Bank Pipeline", "epstein"),
            (54, "Medical-Investment Bridge", "epstein-aetna"),
        ],
    )

    resolved = profile_threads.resolve_profile_thread_id(
        db,
        3,
        "epstein-aetna",
        local_thread_ids={3: 54},
        bridge_thread_ids={3},
    )

    assert resolved == 3
