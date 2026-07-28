import json
import sqlite3

import pytest

from tools import ingest_kabasshouse


@pytest.mark.parametrize("command", ["doc", "document"])
def test_doc_accepts_output_and_writes_all_pages(monkeypatch, tmp_path, command):
    db_path = tmp_path / "kabasshouse.db"
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE documents (
            id TEXT,
            file_key TEXT,
            dataset TEXT,
            document_type TEXT,
            date TEXT,
            ocr_source TEXT,
            char_count INTEGER,
            page_number INTEGER,
            email_fields TEXT,
            full_text TEXT
        )
        """
    )
    db.executemany(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("1", "EFTA00000001", "1", "email", "2010-01-01", "ocr", 5, 1, None, "page one"),
            ("2", "EFTA00000001", "1", "email", "2010-01-01", "ocr", 5, 2, None, "page two"),
        ],
    )
    db.commit()
    db.close()
    output = tmp_path / "document.json"
    monkeypatch.setattr(ingest_kabasshouse, "DB_PATH", db_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ingest_kabasshouse.py",
            command,
            "EFTA00000001",
            "--full",
            "--output",
            str(output),
        ],
    )

    ingest_kabasshouse.main()

    data = json.loads(output.read_text())
    assert [row["full_text"] for row in data] == ["page one", "page two"]


def test_doc_resolves_canonical_page_marker_inside_parent(
    monkeypatch, tmp_path, capsys
):
    db_path = tmp_path / "kabasshouse.db"
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE documents (
            id TEXT,
            file_key TEXT,
            dataset TEXT,
            document_type TEXT,
            date TEXT,
            ocr_source TEXT,
            char_count INTEGER,
            page_number INTEGER,
            email_fields TEXT,
            full_text TEXT
        )
        """
    )
    db.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "1",
            "EFTA01087623",
            "1",
            "filing",
            "2010-01-01",
            "ocr",
            60,
            1,
            None,
            "Parent document text\nEFTA01087635\nRequested page text",
        ),
    )
    db.commit()
    db.close()
    output = tmp_path / "embedded-page.json"
    monkeypatch.setattr(ingest_kabasshouse, "DB_PATH", db_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ingest_kabasshouse.py",
            "doc",
            "EFTA01087635",
            "--output",
            str(output),
        ],
    )

    ingest_kabasshouse.main()

    data = json.loads(output.read_text())
    assert data[0]["file_key"] == "EFTA01087623"
    assert data[0]["requested_page_id"] == "EFTA01087635"
    assert data[0]["resolved_via"] == "embedded_page_marker"
    assert (
        "Resolved page marker EFTA01087635 inside parent document(s): "
        "EFTA01087623"
    ) in capsys.readouterr().err
