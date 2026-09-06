from __future__ import annotations

import sqlite3

from tools.financial_flows import promoted_flows


def test_flow_aggregation_normalizes_aliases_before_thresholding():
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE ds10_transactions (
            sender TEXT, receiver TEXT, amount REAL, tx_date TEXT, qa_status TEXT
        );
        INSERT INTO ds10_transactions VALUES
            ('Alias A', 'B', 20000, '2026-01-01', 'promoted'),
            (' A ', 'B', 30000, '2026-02-01', 'promoted'),
            ('Alias A', 'A', 999999, '2026-01-01', 'promoted'),
            ('A', 'B', 999999, '2026-01-01', 'needs_review');
    """)
    aliases = sqlite3.connect(":memory:")
    aliases.executescript("""
        CREATE TABLE name_aliases (id INTEGER PRIMARY KEY, alias TEXT, canonical_name TEXT);
        INSERT INTO name_aliases VALUES (1, 'Alias A', 'A');
    """)
    assert promoted_flows(db, inv_db=aliases) == [{
        "source": "A", "target": "B", "value": 50000.0, "tx_count": 2,
        "first_date": "2026-01-01", "last_date": "2026-02-01",
    }]
    assert promoted_flows(db, inv_db=None)[0]["source"] == "Alias A"
    db.close()
    aliases.close()
