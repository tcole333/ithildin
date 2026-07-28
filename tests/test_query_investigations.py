import argparse
import json
import sqlite3

from tools import query_investigations


def test_search_treats_dotted_person_name_as_literal_terms(tmp_path, monkeypatch):
    db_path = tmp_path / "investigations.db"
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title TEXT,
            source TEXT,
            year INTEGER,
            category TEXT
        );
        CREATE TABLE pages (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            page_number INTEGER,
            text TEXT
        );
        CREATE VIRTUAL TABLE pages_fts USING fts5(
            text, content=pages, content_rowid=id
        );
        INSERT INTO documents
            (id, title, source, year, category)
        VALUES
            (1, 'Trustee report', 'court', 2013, 'legal');
        INSERT INTO pages
            (id, document_id, page_number, text)
        VALUES
            (1, 1, 27, 'J. Ezra Merkin appears in this report.');
        INSERT INTO pages_fts(pages_fts) VALUES ('rebuild');
        """
    )
    db.close()
    monkeypatch.setattr(query_investigations, "DB_PATH", db_path)
    output = tmp_path / "results.json"

    query_investigations.cmd_search(
        argparse.Namespace(
            query="J. Ezra Merkin",
            category=None,
            limit=10,
            output=str(output),
            json_out=False,
        )
    )

    payload = json.loads(output.read_text())
    assert payload[0]["document_id"] == 1
