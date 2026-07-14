import sqlite3

from tools import analysis_export


def _timeline_export_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY,
            target_name TEXT,
            summary TEXT,
            date_of_event TEXT,
            confidence TEXT,
            thread_id INTEGER,
            finding_type TEXT,
            profile_id TEXT
        );
        CREATE TABLE event_timeline (
            id INTEGER PRIMARY KEY,
            event_date TEXT,
            event_name TEXT,
            category TEXT,
            description TEXT,
            relevance TEXT,
            profile_id TEXT
        );
        """
    )
    db.executemany(
        """INSERT INTO findings
               (id, target_name, summary, date_of_event, confidence, thread_id,
                finding_type, profile_id)
           VALUES (?, ?, ?, ?, 'confirmed', 108, 'document', ?)""",
        [
            (1, "GEO", "GEO dated finding", "2025-01-10", "geo-group"),
            (2, "Other", "Other dated finding", "2025-01-11", "other-profile"),
            (3, "GEO", "GEO undated finding", None, "geo-group"),
            (4, "Other", "Other undated finding", None, "other-profile"),
        ],
    )
    db.executemany(
        """INSERT INTO event_timeline
               (id, event_date, event_name, category, description, relevance,
                profile_id)
           VALUES (?, ?, ?, 'legal', '', '', ?)""",
        [
            (1, "2025-01-09", "GEO event", "geo-group"),
            (2, "2025-01-09", "Other event", "other-profile"),
            (3, "2025-01-09", "Legacy unscoped event", None),
        ],
    )
    db.commit()
    return db


def test_timeline_export_scopes_events_and_findings_to_active_profile(monkeypatch):
    db = _timeline_export_db()
    monkeypatch.setattr(analysis_export, "get_analysis_db", lambda: db)
    monkeypatch.setattr(analysis_export, "get_active_profile_id", lambda: "geo-group")

    result = analysis_export.export_timeline()

    assert [row["summary"] for row in result["dated_findings"]] == [
        "GEO dated finding"
    ]
    assert [row["event_name"] for row in result["events"]] == ["GEO event"]
    assert result["dated_finding_count"] == 1
    assert result["undated_finding_count"] == 1
    assert result["event_count"] == 1
