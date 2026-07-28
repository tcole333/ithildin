from __future__ import annotations

import sqlite3

from tools import parse_ds10_financials


def test_counterparty_query_combines_name_and_date_filters(capsys):
    db = sqlite3.connect(":memory:")
    db.execute(
        """
        CREATE TABLE ds10_transactions (
            tx_date TEXT,
            direction TEXT,
            amount REAL,
            currency TEXT,
            sender TEXT,
            receiver TEXT,
            bank TEXT,
            efta_id TEXT
        )
        """
    )
    db.executemany(
        "INSERT INTO ds10_transactions VALUES (?, ?, ?, 'USD', ?, ?, 'DB', ?)",
        [
            (
                "2013-06-01",
                "outgoing",
                100.0,
                "MC2 Model Management",
                "Example Recipient",
                "EFTA-MATCH",
            ),
            (
                "2011-06-01",
                "outgoing",
                200.0,
                "MC2 Model Management",
                "Old Recipient",
                "EFTA-OUTSIDE-DATE",
            ),
            (
                "2013-07-01",
                "outgoing",
                300.0,
                "Unrelated Sender",
                "Unrelated Recipient",
                "EFTA-UNRELATED",
            ),
        ],
    )

    parse_ds10_financials.query_counterparty(
        db,
        "MC2 Model Management",
        limit=200,
        date_start="2012-01-01",
        date_end="2014-12-31",
    )

    output = capsys.readouterr().out
    assert "EFTA-MATCH" in output
    assert "EFTA-OUTSIDE-DATE" not in output
    assert "EFTA-UNRELATED" not in output
    assert "1 transactions" in output
    db.close()
