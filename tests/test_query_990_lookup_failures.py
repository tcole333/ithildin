import argparse
import json
import sqlite3
import sys

import pytest

from tools import query_990


def _create_db(path):
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


def _lookup_args(ein, output):
    return argparse.Namespace(
        ein=ein,
        output=str(output),
        json_out=False,
    )


def test_local_lookup_suppresses_optional_propublica_transport_error(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "irs990.db"
    db = _create_db(db_path)
    db.execute(
        """
        INSERT INTO filings (object_id, ein, filer_name, tax_year)
        VALUES ('filing-1', '333863270', 'Local Nonprofit', 2024)
        """
    )
    db.commit()
    db.close()

    def unavailable(_ein):
        print("URL Error: temporary DNS failure", file=sys.stderr)
        return None

    monkeypatch.setattr(query_990, "DB_PATH", db_path)
    monkeypatch.setattr(query_990, "_pp_get_org", unavailable)
    output = tmp_path / "lookup.json"

    query_990.cmd_lookup(_lookup_args("33-3863270", output))

    captured = capsys.readouterr()
    payload = json.loads(output.read_text())
    assert captured.err == ""
    assert payload["org_name"] == "Local Nonprofit"
    assert payload["ein"] == "333863270"


def test_lookup_without_local_or_propublica_data_fails_without_placeholder(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "irs990.db"
    db = _create_db(db_path)
    db.close()

    def unavailable(_ein):
        print("URL Error: temporary DNS failure", file=sys.stderr)
        return None

    monkeypatch.setattr(query_990, "DB_PATH", db_path)
    monkeypatch.setattr(query_990, "_pp_get_org", unavailable)
    output = tmp_path / "lookup.json"

    with pytest.raises(SystemExit) as exc_info:
        query_990.cmd_lookup(_lookup_args("33-3863270", output))

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert captured.out == ""
    assert "no local IRS 990 data" in captured.err
    assert "URL Error" not in captured.err
    assert not output.exists()
