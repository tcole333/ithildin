from __future__ import annotations

import json
import sqlite3
import sys

from tools import ingest_kabasshouse


def test_financials_cli_accepts_output_and_writes_matching_transactions(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "kabasshouse.db"
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE financial_transactions (
            transaction_date TEXT,
            amount REAL,
            currency TEXT,
            merchant_name TEXT,
            merchant_raw TEXT,
            cardholder TEXT,
            file_key TEXT
        );
        INSERT INTO financial_transactions VALUES
            ('2012-01-03', 125.50, 'USD', 'Example Merchant', NULL, 'Merkin', 'EFTA1'),
            ('2012-01-04', 40.00, 'USD', 'Other Merchant', NULL, 'Other', 'EFTA2');
        """
    )
    db.close()
    output = tmp_path / "financials.json"
    monkeypatch.setattr(ingest_kabasshouse, "DB_PATH", db_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ingest_kabasshouse.py",
            "financials",
            "--cardholder",
            "Merkin",
            "--output",
            str(output),
        ],
    )

    ingest_kabasshouse.main()

    assert json.loads(output.read_text()) == [
        {
            "transaction_date": "2012-01-03",
            "amount": 125.5,
            "currency": "USD",
            "merchant_name": "Example Merchant",
            "merchant_raw": None,
            "cardholder": "Merkin",
            "file_key": "EFTA1",
        }
    ]
    assert capsys.readouterr().out == (
        f"1 results (Kabasshouse financial transactions) saved to {output}\n"
    )
