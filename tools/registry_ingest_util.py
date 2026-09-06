"""Stable writes for undated current registry-party observations.

Legacy registry databases permit duplicate NULL dates in their UNIQUE keys.
Use a NULL-safe update before insert without requiring a destructive cleanup or
schema migration. Dated, ended, and filing-linked historical rows are untouched.
"""

from __future__ import annotations

import sqlite3
from typing import Any


def _upsert_current_party(
    db: sqlite3.Connection,
    table: str,
    identity: dict[str, Any],
    details: dict[str, Any],
    *,
    filing_link: bool = False,
) -> int:
    db.execute("SAVEPOINT registry_current_party")
    try:
        return _write_current_party(db, table, identity, details, filing_link=filing_link)
    except Exception:
        db.execute("ROLLBACK TO registry_current_party")
        raise
    finally:
        db.execute("RELEASE registry_current_party")


def _write_current_party(
    db: sqlite3.Connection,
    table: str,
    identity: dict[str, Any],
    details: dict[str, Any],
    *,
    filing_link: bool,
) -> int:
    # Table and column names are internal constants from the two callers below.
    where = " AND ".join(f"{column} IS ?" for column in identity)
    where += " AND effective_date IS NULL AND end_date IS NULL"
    if filing_link:
        where += " AND source_filing_id IS NULL"
    assignments = ", ".join(f"{column} = ?" for column in details)
    # UPDATE takes the writer lock before checking for a match, preventing two
    # concurrent ingests from both deciding that the current party is absent.
    existing = db.execute(
        f"UPDATE {table} SET {assignments} WHERE id = "
        f"(SELECT id FROM {table} WHERE {where} ORDER BY id LIMIT 1) RETURNING id",
        (*details.values(), *identity.values()),
    ).fetchone()
    if existing is not None:
        return int(existing[0])
    values = {**identity, **details}
    inserted = db.execute(
        f"INSERT INTO {table} ({', '.join(values)}) "
        f"VALUES ({', '.join('?' for _ in values)}) RETURNING id",
        tuple(values.values()),
    ).fetchone()
    return int(inserted[0])


def upsert_current_agent(
    db: sqlite3.Connection,
    *,
    entity_id: int,
    agent_name: str,
    agent_type: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
    country: str | None = None,
) -> int:
    """Refresh one undated current agent, preserving its stable row ID."""
    return _upsert_current_party(
        db,
        "registry_agents",
        {"entity_id": entity_id, "agent_name": agent_name},
        {"agent_type": agent_type, "address": address, "city": city,
         "state": state, "zip": zip, "country": country},
    )


def upsert_current_officer(
    db: sqlite3.Connection,
    *,
    entity_id: int,
    officer_name: str,
    title: str | None = None,
    officer_type: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
    country: str | None = None,
) -> int:
    """Refresh one undated current office, preserving dated filing history."""
    return _upsert_current_party(
        db,
        "registry_officers",
        {"entity_id": entity_id, "officer_name": officer_name, "title": title},
        {"officer_type": officer_type, "address": address, "city": city,
         "state": state, "zip": zip, "country": country},
        filing_link=True,
    )
