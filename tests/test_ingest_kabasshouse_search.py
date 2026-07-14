from __future__ import annotations

import argparse
import json
import sqlite3


def _build_search_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            file_key TEXT,
            dataset TEXT,
            document_type TEXT,
            date TEXT,
            ocr_source TEXT,
            char_count INTEGER,
            full_text TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            file_key,
            full_text,
            content=documents,
            content_rowid=rowid
        );
        INSERT INTO documents VALUES
            ('1', 'EFTA1', '10', 'email', '2020-01-01', 'ocr', 80,
             'Contact drobertson@k2intelligence.com through powerscourtgroup.com.'),
            ('2', 'EFTA2', '10', 'court', '2020-01-02', 'ocr', 45,
             'The matter was filed as docket 93-B-41558.'),
            ('3', 'EFTA3', '10', 'note', '2020-01-03', 'ocr', 20,
             'Epstein reference.'),
            ('4', 'EFTA4', '10', 'note', '2020-01-04', 'ocr', 20,
             'Maxwell reference.');
        INSERT INTO documents_fts(documents_fts) VALUES ('rebuild');
        """
    )
    db.close()


def _search_args(query, output):
    return argparse.Namespace(
        query=query,
        limit=20,
        dataset=None,
        min_chars=None,
        json_out=False,
        output=str(output),
    )


def test_search_quotes_literal_selectors_and_preserves_explicit_fts_operators(
    tmp_path, monkeypatch
):
    from tools import ingest_kabasshouse

    db_path = tmp_path / "kabasshouse.db"
    _build_search_db(db_path)
    monkeypatch.setattr(ingest_kabasshouse, "DB_PATH", db_path)

    expected = {
        "drobertson@k2intelligence.com": ["EFTA1"],
        "powerscourtgroup.com": ["EFTA1"],
        "93-B-41558": ["EFTA2"],
        "Epstein OR Maxwell": ["EFTA3", "EFTA4"],
        "Epstein AND reference": ["EFTA3"],
        "Epstein NOT Maxwell": ["EFTA3"],
    }
    for index, (query, file_keys) in enumerate(expected.items()):
        output = tmp_path / f"results-{index}.json"
        ingest_kabasshouse.cmd_search(_search_args(query, output))
        results = json.loads(output.read_text())
        assert [row["file_key"] for row in results] == file_keys
