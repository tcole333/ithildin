"""One deterministic definition of exported DS10 financial flow edges."""

from __future__ import annotations

import sqlite3


def promoted_flows(
    ds10_db: sqlite3.Connection,
    *,
    inv_db: sqlite3.Connection | None,
    min_amount: float = 50000,
) -> list[dict]:
    """Aggregate promoted transactions using aliases from the supplied database.

    Apply the threshold to each aggregate edge, so multiple smaller transfers
    are counted consistently by the export and its independent parity check.
    """
    aliases = {}
    if inv_db is not None and inv_db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='name_aliases'"
    ).fetchone():
        aliases = {
            alias.strip().casefold(): canonical.strip()
            for alias, canonical in inv_db.execute(
                "SELECT alias, canonical_name FROM name_aliases ORDER BY id"
            )
            if alias and canonical
        }

    def canonical(name: str) -> str:
        name = name.strip()
        return aliases.get(name.casefold(), name)

    columns = {row[1] for row in ds10_db.execute("PRAGMA table_info(ds10_transactions)")}
    qa_filter = "AND qa_status='promoted'" if "qa_status" in columns else ""
    rows = ds10_db.execute(
        f"""SELECT sender, receiver, SUM(amount), COUNT(*), MIN(tx_date), MAX(tx_date)
        FROM ds10_transactions
        WHERE amount >= 0 AND sender IS NOT NULL AND receiver IS NOT NULL
          AND sender != '' AND receiver != '' {qa_filter}
        GROUP BY sender, receiver"""
    ).fetchall()
    edges: dict[tuple[str, str], dict] = {}
    for raw_sender, raw_receiver, amount, count, first_date, last_date in rows:
        sender, receiver = canonical(raw_sender), canonical(raw_receiver)
        if not sender or not receiver or sender == receiver:
            continue
        if sender in {"INTERNAL TRANSFER", "TRANSFER"} or receiver in {"INTERNAL TRANSFER", "TRANSFER"}:
            continue
        edge = edges.setdefault((sender, receiver), {
            "source": sender, "target": receiver, "value": 0.0, "tx_count": 0,
            "first_date": first_date, "last_date": last_date,
        })
        edge["value"] += float(amount)
        edge["tx_count"] += count
        dates = [date for date in (edge["first_date"], first_date) if date is not None]
        edge["first_date"] = min(dates) if dates else None
        dates = [date for date in (edge["last_date"], last_date) if date is not None]
        edge["last_date"] = max(dates) if dates else None
    result = []
    for edge in edges.values():
        edge["value"] = round(edge["value"], 2)
        if edge["value"] >= min_amount:
            result.append(edge)
    return sorted(result, key=lambda edge: (-edge["value"], edge["source"], edge["target"]))
