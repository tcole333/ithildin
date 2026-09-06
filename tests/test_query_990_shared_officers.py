import argparse
import json
import sqlite3

from tools import query_990


def test_shared_officers_matches_title_and_middle_initial_variants(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "irs990.db"
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE officers (
            ein TEXT,
            filer_name TEXT,
            person_name TEXT,
            title TEXT,
            total_comp INTEGER,
            tax_year INTEGER,
            is_director INTEGER,
            is_officer INTEGER,
            is_key_employee INTEGER
        )
        """
    )
    db.executemany(
        "INSERT INTO officers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "550839353",
                "Heritage Medical Research Institute",
                "DR RICHARD MERKIN",
                "President",
                0,
                2024,
                1,
                1,
                0,
            ),
            (
                "951643307",
                "California Institute of Technology",
                "RICHARD N MERKIN",
                "Senior Trustee",
                0,
                2024,
                1,
                0,
                0,
            ),
        ],
    )
    db.commit()
    db.close()
    monkeypatch.setattr(query_990, "DB_PATH", db_path)
    output = tmp_path / "shared.json"

    query_990.cmd_shared_officers(
        argparse.Namespace(
            eins=["55-0839353", "95-1643307"],
            output=str(output),
            json_out=False,
        )
    )

    payload = json.loads(output.read_text())
    assert payload["total_shared"] == 1
    assert payload["shared_officers"][0]["normalized"] == "richard merkin"
    assert payload["shared_officers"][0]["name_variants"] == [
        "DR RICHARD MERKIN",
        "RICHARD N MERKIN",
    ]
