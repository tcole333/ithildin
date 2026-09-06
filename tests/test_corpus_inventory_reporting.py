from __future__ import annotations

import sqlite3

from tools import source_report


def _build_inventory_db(path, statements):
    db = sqlite3.connect(path)
    db.executescript(statements)
    db.close()


def test_check_sqlite_inventory_returns_named_live_counts(tmp_path):
    db_path = tmp_path / "source.db"
    _build_inventory_db(
        db_path,
        """
        CREATE TABLE files (id INTEGER);
        CREATE TABLE entities (id INTEGER);
        INSERT INTO files VALUES (1), (2);
        INSERT INTO entities VALUES (1), (2), (3);
        """,
    )

    result = source_report.check_sqlite_inventory(
        db_path,
        {
            "files": "SELECT COUNT(*) FROM files",
            "entity_mentions": "SELECT COUNT(*) FROM entities",
        },
        primary_metric="files",
    )

    assert result["status"] == "available"
    assert result["records"] == 2
    assert result["inventory"] == {"files": 2, "entity_mentions": 3}


def test_source_report_corpus_descriptions_use_live_inventory(monkeypatch):
    def fake_inventory(path, _queries, *, primary_metric):
        if path.name == "kabasshouse_epstein.db":
            inventory = {
                "document_page_records": 12,
                "distinct_file_keys": 12,
                "entity_mentions": 34,
                "financial_transactions": 5,
            }
        elif path.name == "epstein_derived.db":
            inventory = {
                "artifact_locations": 27,
                "unique_artifacts": 14,
                "metadata_observations": 56,
            }
        else:
            inventory = {
                "files": 67,
                "entity_mentions": 89,
                "cooccurrences": 10,
            }
        return {
            "status": "available",
            "path": str(path),
            "records": inventory[primary_metric],
            "inventory": inventory,
        }

    monkeypatch.setattr(source_report, "check_sqlite_inventory", fake_inventory)
    monkeypatch.setattr(
        source_report,
        "check_sqlite",
        lambda path, query: {"status": "missing", "path": str(path), "records": 0},
    )
    monkeypatch.setattr(
        source_report,
        "check_parquet",
        lambda path: {"status": "missing", "path": str(path), "records": 0},
    )
    monkeypatch.setattr(
        source_report,
        "check_directory",
        lambda path: {"status": "missing", "path": str(path), "records": 0},
    )
    monkeypatch.setattr(
        source_report, "check_api", lambda *_args, **_kwargs: {"status": "configured"}
    )
    monkeypatch.setattr(source_report, "check_neo4j", lambda: {"status": "stopped"})
    monkeypatch.setattr(
        source_report, "check_muckrock", lambda: {"status": "no_credentials"}
    )
    monkeypatch.setattr(source_report, "check_public_records_catalog", lambda: {})

    report = source_report.generate_report()

    assert report["Kabasshouse"]["records"] == 12
    assert "12 OCR document/page records across 12 distinct file_keys" in (
        report["Kabasshouse"]["description"]
    )
    assert report["LMSBAND"]["records"] == 67
    assert report["LMSBAND"]["description"] == (
        "67 files, 89 entity mentions, and 10 co-occurrences"
    )
    assert report["Epstein Artifact Metadata"]["records"] == 27
    assert report["Epstein Artifact Metadata"]["inventory"] == {
        "artifact_locations": 27,
        "unique_artifacts": 14,
        "metadata_observations": 56,
    }
