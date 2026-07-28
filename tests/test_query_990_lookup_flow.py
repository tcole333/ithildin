import argparse
import json
import sqlite3

from tools import query_990


def _create_990_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE financials (
            object_id TEXT PRIMARY KEY,
            ein TEXT,
            filer_name TEXT,
            tax_year INTEGER,
            total_revenue INTEGER,
            total_expenses INTEGER,
            program_expenses INTEGER,
            total_assets_eoy INTEGER,
            program_expense_ratio REAL
        );
        CREATE TABLE filings (
            object_id TEXT PRIMARY KEY,
            ein TEXT,
            filer_name TEXT,
            tax_year INTEGER
        );
        CREATE TABLE grants (
            id INTEGER PRIMARY KEY,
            filer_ein TEXT,
            filer_name TEXT,
            recipient_ein TEXT,
            recipient_name TEXT,
            cash_amount INTEGER,
            tax_year INTEGER
        );
        CREATE TABLE officers (
            ein TEXT,
            person_name TEXT,
            title TEXT,
            total_comp INTEGER,
            is_director INTEGER,
            is_officer INTEGER,
            tax_year INTEGER
        );
        CREATE TABLE checklist_flags (
            ein TEXT,
            tax_year INTEGER,
            excess_benefit_transaction INTEGER,
            conflict_of_interest_policy INTEGER,
            whistleblower_policy INTEGER
        );
        """
    )
    return db


def test_lookup_prefers_latest_financial_row_with_data(tmp_path, monkeypatch):
    db_path = tmp_path / "irs990.db"
    db = _create_990_db(db_path)
    db.executemany(
        """
        INSERT INTO financials (
            object_id, ein, filer_name, tax_year, total_revenue,
            total_expenses, program_expenses, total_assets_eoy,
            program_expense_ratio
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("new-stub", "131624225", "Yeshiva University", 2024, 0, 0, 0, 0, None),
            (
                "latest-data",
                "131624225",
                "Yeshiva University",
                2023,
                2_447_837,
                2_000_000,
                1_500_000,
                5_954_345,
                0.75,
            ),
        ],
    )
    db.commit()
    db.close()
    monkeypatch.setattr(query_990, "DB_PATH", db_path)
    monkeypatch.setattr(query_990, "_pp_get_org", None)
    output = tmp_path / "lookup.json"

    query_990.cmd_lookup(
        argparse.Namespace(ein="13-1624225", output=str(output), json_out=False)
    )

    payload = json.loads(output.read_text())
    assert payload["financials"]["tax_year"] == 2023
    assert payload["financials"]["total_revenue"] == 2_447_837
    assert payload["financials"]["total_assets_eoy"] == 5_954_345


def test_lookup_uses_latest_propublica_filing_when_bulk_financials_are_absent(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "irs990.db"
    db = _create_990_db(db_path)
    db.execute(
        """
        INSERT INTO grants (
            filer_ein, filer_name, recipient_ein, recipient_name,
            cash_amount, tax_year
        ) VALUES ('131624225', 'Yeshiva University', '1', 'Recipient', 10, 2023)
        """
    )
    db.commit()
    db.close()
    monkeypatch.setattr(query_990, "DB_PATH", db_path)
    monkeypatch.setattr(
        query_990,
        "_pp_get_org",
        lambda _ein: {
            "organization": {
                "ein": 131624225,
                "name": "Yeshiva University",
            },
            "filings_with_data": [
                {
                    "tax_prd_yr": 2023,
                    "formtype": 0,
                    "totrevenue": 382_447_837,
                    "totfuncexpns": 390_718_819,
                    "totassetsend": 999_954_345,
                }
            ],
        },
    )
    output = tmp_path / "lookup.json"

    query_990.cmd_lookup(
        argparse.Namespace(ein="13-1624225", output=str(output), json_out=False)
    )

    payload = json.loads(output.read_text())
    assert payload["financials"]["source"] == "propublica_nonprofit_explorer"
    assert payload["financials"]["total_revenue"] == 382_447_837
    assert payload["financials"]["total_assets_eoy"] == 999_954_345


def test_flow_uses_financial_name_for_seed_and_circular_nodes(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "irs990.db"
    db = _create_990_db(db_path)
    db.executemany(
        """
        INSERT INTO financials (
            object_id, ein, filer_name, tax_year, total_revenue,
            total_expenses, program_expenses, total_assets_eoy,
            program_expense_ratio
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("yeshiva", "131624225", "Yeshiva University", 2023, 1, 1, 1, 1, 1),
            ("montefiore", "131740114", "Montefiore", 2023, 1, 1, 1, 1, 1),
        ],
    )
    db.executemany(
        """
        INSERT INTO grants (
            filer_ein, filer_name, recipient_ein, recipient_name,
            cash_amount, tax_year
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("131624225", "", "131740114", "Montefiore", 100_000, 2023),
            ("131740114", "Montefiore", "131624225", "", 75_000, 2023),
        ],
    )
    db.commit()
    db.close()
    monkeypatch.setattr(query_990, "DB_PATH", db_path)
    output = tmp_path / "flow.json"

    query_990.cmd_flow(
        argparse.Namespace(
            ein="13-1624225",
            depth=2,
            limit=20,
            min_amount=50_000,
            output=str(output),
            json_out=False,
        )
    )

    payload = json.loads(output.read_text())
    assert payload["root_name"] == "Yeshiva University"
    assert {node["name"] for node in payload["nodes"]} == {
        "Yeshiva University",
        "Montefiore",
    }
    assert payload["circular_flows"][0]["names"] == [
        "Yeshiva University",
        "Montefiore",
    ]
