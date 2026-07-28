from __future__ import annotations

import sqlite3

from tools import query_nydos, query_registry


def _detail(name):
    return {
        "requestStatus": "Success",
        "entityGeneralInfo": {
            "entityName": name,
            "entityType": "DOMESTIC LIMITED LIABILITY COMPANY",
            "entityStatus": "Active",
            "dateOfInitialDosFiling": "2020-01-02T00:00:00",
            "jurisdiction": "NEW YORK",
        },
        "sopAddress": {
            "address": {
                "streetAddress1": "1 Main Street",
                "city": "Albany",
                "state": "NY",
                "zipCode": "12207",
                "country": "US",
            }
        },
    }


def test_single_entity_ingest_updates_fts_incrementally(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    query_registry._ensure_schema(db)
    current = {"detail": _detail("Original Registry Name LLC")}
    monkeypatch.setattr(
        query_nydos,
        "_fetch_entity_detail",
        lambda *_args: current["detail"],
    )
    monkeypatch.setattr(query_nydos, "_fetch_filing_history", lambda *_args: None)
    monkeypatch.setattr(query_nydos, "_fetch_name_history", lambda *_args: None)

    entity_id = query_nydos._ingest_entity_to_registry(db, "2729862")
    assert [
        row[0]
        for row in db.execute(
            "SELECT rowid FROM registry_entities_fts "
            "WHERE registry_entities_fts MATCH 'Original'"
        ).fetchall()
    ] == [entity_id]

    current["detail"] = _detail("Updated Registry Name LLC")
    updated_id = query_nydos._ingest_entity_to_registry(db, "2729862")

    assert updated_id == entity_id
    assert db.execute(
        "SELECT rowid FROM registry_entities_fts "
        "WHERE registry_entities_fts MATCH 'Original'"
    ).fetchall() == []
    assert [
        row[0]
        for row in db.execute(
            "SELECT rowid FROM registry_entities_fts "
            "WHERE registry_entities_fts MATCH 'Updated'"
        ).fetchall()
    ] == [entity_id]
    db.close()
