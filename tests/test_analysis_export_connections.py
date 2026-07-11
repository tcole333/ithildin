import sqlite3

from tools import analysis_export


def _connection_export_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY,
            person_a TEXT,
            person_b TEXT,
            relationship_type TEXT,
            description TEXT,
            strength TEXT,
            date_range TEXT,
            verification_status TEXT,
            created_at TEXT,
            profile_id TEXT
        );
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY,
            target_name TEXT,
            thread_id INTEGER,
            confidence TEXT,
            profile_id TEXT
        );
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            name TEXT,
            entity_type TEXT,
            jurisdiction TEXT
        );
        CREATE TABLE name_aliases (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            alias TEXT,
            entity_id INTEGER
        );
        CREATE TABLE finding_entities (
            finding_id INTEGER,
            entity_id INTEGER,
            raw_name TEXT,
            resolution_status TEXT NOT NULL DEFAULT 'asserted'
        );
        """
    )
    db.executemany(
        "INSERT INTO entities (id, name, entity_type, jurisdiction) VALUES (?, ?, ?, ?)",
        [
            (1, "Ed Coscolluela", "person", None),
            (2, "Grand Wilshire Group", "corporation", "California"),
            (3, "Alpha LLC", "llc", "Delaware"),
            (4, "Beta LLC", "llc", "Nevada"),
        ],
    )
    db.executemany(
        "INSERT INTO name_aliases (id, canonical_name, alias, entity_id) VALUES (?, ?, ?, ?)",
        [
            (1, "Ed Coscolluela", "Eduardo S. Coscolluela", 1),
            # Conflicting reviewed aliases must remain unresolved at export.
            (2, "Alpha LLC", "Shared Co", 3),
            (3, "Beta LLC", "Shared Co", 4),
        ],
    )
    db.executemany(
        """INSERT INTO findings
               (id, target_name, thread_id, confidence, profile_id)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (1, "Eduardo S. Coscolluela", 72, "medium", "coscoluella"),
            (2, "Ed Coscolluella", 72, "confirmed", "coscoluella"),
            (3, "Ed Coscolluela", 71, "high", "coscoluella"),
            # Reverse insertion order for an equal-count thread tie. The
            # deterministic aggregate must still choose the lower id (71).
            (4, "Grand Wilshire Group", 72, "medium", "coscoluella"),
            (5, "Grand Wilshire Group", 71, "high", "coscoluella"),
            (6, "Finding Only", 99, "confirmed", "coscoluella"),
            (7, "Ed Coscolluela", 10, "low", "other-profile"),
        ],
    )
    db.execute(
        """INSERT INTO finding_entities
               (finding_id, entity_id, raw_name, resolution_status)
           VALUES (2, 1, 'Ed Coscolluella', 'reviewed')"""
    )
    db.executemany(
        """INSERT INTO connections
               (id, person_a, person_b, relationship_type, description,
                strength, date_range, verification_status, created_at, profile_id)
           VALUES (?, ?, ?, ?, '', 'medium', NULL, 'unverified', '2026-01-01', ?)""",
        [
            (1, "Eduardo S. Coscolluela", "Grand Wilshire Group", "employment", "coscoluella"),
            (2, "Ed Coscolluella", "Unmodeled Node", "social", "coscoluella"),
            (3, "Shared Co", "Alpha LLC", "corporate", "coscoluella"),
            (4, "Other A", "Other B", "social", "other-profile"),
        ],
    )
    db.commit()
    return db


def test_connections_graph_canonicalizes_safe_aliases_and_counts_endpoints(monkeypatch):
    db = _connection_export_db()
    monkeypatch.setattr(analysis_export, "get_analysis_db", lambda: db)

    result = analysis_export.export_connections_graph(profile_id="coscoluella")

    assert result["edge_count"] == 3
    assert result["node_count"] == 5
    assert "Finding Only" not in result["node_metadata"]

    first, second, ambiguous = result["edges"]
    assert first["person_a"] == "Ed Coscolluela"
    assert first["raw_person_a"] == "Eduardo S. Coscolluela"
    assert first["entity_a_id"] == 1
    assert second["person_a"] == "Ed Coscolluela"
    assert second["raw_person_a"] == "Ed Coscolluella"
    assert second["entity_a_id"] == 1

    # Two conflicting alias records are not silently merged.
    assert ambiguous["person_a"] == "Shared Co"
    assert ambiguous["raw_person_a"] == "Shared Co"
    assert ambiguous["entity_a_id"] is None
    assert ambiguous["person_b"] == "Alpha LLC"
    assert ambiguous["entity_b_id"] == 3


def test_connections_graph_uses_ranked_confidence_and_deterministic_threads(monkeypatch):
    db = _connection_export_db()
    monkeypatch.setattr(analysis_export, "get_analysis_db", lambda: db)

    result = analysis_export.export_connections_graph(profile_id="coscoluella")
    ed = result["node_metadata"]["Ed Coscolluela"]
    grand = result["node_metadata"]["Grand Wilshire Group"]
    unmodeled = result["node_metadata"]["Unmodeled Node"]

    assert ed["finding_count"] == 3
    assert ed["max_confidence"] == "confirmed"
    assert ed["thread_id"] == 72
    assert ed["thread_ids"] == [71, 72]
    assert ed["raw_labels"] == ["Ed Coscolluella", "Eduardo S. Coscolluela"]

    # Lexical MAX would choose "medium" over "high". Explicit ranking must not.
    assert grand["max_confidence"] == "high"
    assert grand["thread_id"] == 71
    assert grand["thread_ids"] == [71, 72]

    assert unmodeled["finding_count"] == 0
    assert unmodeled["max_confidence"] is None
    assert unmodeled["thread_id"] is None
    assert unmodeled["thread_ids"] == []
