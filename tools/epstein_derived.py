#!/usr/bin/env python3
"""epstein_derived.db — the derived-data sidecar (schema contract + shared helpers).

This module is the SINGLE SOURCE OF TRUTH for the sidecar schema. Every builder
(build_evidence_registry.py, build_temporal_events.py, build_financials.py,
person_resolution.py) imports `get_db()` / `attach_*()` from here and writes into
tables defined by `SCHEMA` below. Do not CREATE TABLE anywhere else.

Design contract (from the 2026-07-04 data-model retrospective):
  * kabasshouse_epstein.db stays IMMUTABLE (source evidence). Read-only.
  * investigation.db owns CANONICAL entities + curated findings. The sidecar
    NEVER mints a competing person store; it references core entities by
    `core_entity_id` (a logical/soft FK — SQLite can't enforce cross-file FKs)
    and stages its own resolution in `entity_crosswalk` until reviewed.
  * Corroboration is counted by `independence_group`, never by row count: three
    re-OCRs of one released page are one source. The evidence_item /
    evidence_representation split enforces this structurally.
  * Dates are integer epoch-days as intervals [start_day_min, start_day_max] +
    precision, so a year-only value spans its whole year (see date_normalize).
  * Derived facts become core findings ONLY via findings_tracker.add_finding
    (never a direct cross-db write); `derived_fact_provenance` records the link.

CLI:
    uv run python tools/epstein_derived.py init      # create all tables
    uv run python tools/epstein_derived.py stats     # row counts per table
    uv run python tools/epstein_derived.py new-run <builder> [--note ...]   # -> run_id
"""

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DERIVED_DB = PROJECT_ROOT / "datasets" / "epstein_derived.db"
KABASS_DB = PROJECT_ROOT / "datasets" / "kabasshouse_epstein.db"
LMSBAND_DB = PROJECT_ROOT / "datasets" / "lmsband_epstein_files.db"
UNIFIED_DB = PROJECT_ROOT / "datasets" / "unified_epstein.db"
CORE_DB = PROJECT_ROOT / "investigation.db"

SCHEMA_VERSION = 1

SCHEMA = """
-- ─────────────────────────── meta / provenance ───────────────────────────
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY, value TEXT
);

CREATE TABLE IF NOT EXISTS source_system (
    source_system_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,             -- kabasshouse | lmsband | unified | doj_vol11 | fbi
    source_class TEXT NOT NULL,            -- primary_release | reocr | extraction | curation
    default_independence_group TEXT
);

CREATE TABLE IF NOT EXISTS derivation_run (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    builder TEXT NOT NULL,
    code_version TEXT,
    core_correction_highwater INTEGER,     -- max(corrections.id) at build time (staleness signal)
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    record_count INTEGER,
    note TEXT
);

-- One released page/artifact. Never overwritten. EFTA id is the canonical ref.
CREATE TABLE IF NOT EXISTS evidence_item (
    evidence_item_id INTEGER PRIMARY KEY,
    canonical_ref TEXT NOT NULL UNIQUE,    -- EFTA00039357 (or SOURCE:ID for non-EFTA)
    item_kind TEXT NOT NULL DEFAULT 'page',-- page | image | external_document
    dataset TEXT,
    primary_source_system_id INTEGER REFERENCES source_system(source_system_id),
    content_date_raw TEXT,
    created_by_run INTEGER REFERENCES derivation_run(run_id)
);
CREATE INDEX IF NOT EXISTS idx_evitem_dataset ON evidence_item(dataset);

-- Each OCR/parse/extraction OF an evidence_item. independence_group is what
-- corroboration counts by (same group = same underlying source, not a 2nd witness).
CREATE TABLE IF NOT EXISTS evidence_representation (
    representation_id INTEGER PRIMARY KEY,
    evidence_item_id INTEGER NOT NULL REFERENCES evidence_item(evidence_item_id),
    source_system_id INTEGER NOT NULL REFERENCES source_system(source_system_id),
    source_native_id TEXT NOT NULL,
    representation_type TEXT NOT NULL,     -- ocr | metadata | email_parse | entity_extract | financial_parse
    content_hash TEXT,
    extraction_model TEXT,
    extraction_confidence REAL,
    independence_group TEXT NOT NULL,
    UNIQUE(source_system_id, source_native_id, representation_type)
);
CREATE INDEX IF NOT EXISTS idx_evrep_item ON evidence_representation(evidence_item_id);

CREATE TABLE IF NOT EXISTS source_crosswalk (
    source_system_id INTEGER NOT NULL REFERENCES source_system(source_system_id),
    source_native_id TEXT NOT NULL,
    evidence_item_id INTEGER REFERENCES evidence_item(evidence_item_id),
    match_method TEXT NOT NULL,            -- efta_exact | filename | content_hash | message_id
    match_confidence REAL,
    match_status TEXT NOT NULL DEFAULT 'accepted',
    PRIMARY KEY (source_system_id, source_native_id)
);

-- Links a derived fact back to the core finding it was promoted to / from.
CREATE TABLE IF NOT EXISTS derived_fact_provenance (
    derived_type TEXT NOT NULL,            -- event | transaction | canonical_person ...
    derived_id INTEGER NOT NULL,
    core_finding_id INTEGER,
    core_evidence_ref TEXT,
    run_id INTEGER REFERENCES derivation_run(run_id),
    PRIMARY KEY (derived_type, derived_id, core_finding_id, core_evidence_ref)
);

-- ─────────────────────────── temporal events ─────────────────────────────
-- Dates are integer epoch-days (days since 1970-01-01) as INTERVALS. A range
-- query is: start_day_min <= window_end AND COALESCE(end_day_max,start_day_max) >= window_start.
CREATE TABLE IF NOT EXISTS event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,              -- email|call|flight|meeting|transaction|filing|document
    subtype TEXT,
    summary TEXT,
    start_day_min INTEGER NOT NULL,
    start_day_max INTEGER NOT NULL,
    end_day_min INTEGER,
    end_day_max INTEGER,
    time_local TEXT,
    timezone TEXT,
    date_precision TEXT NOT NULL,          -- day|month|year|range|approximate
    date_raw TEXT,
    date_parse_method TEXT,
    date_confidence REAL,
    amount_minor INTEGER,                  -- for transaction/flight events (convenience)
    location TEXT,
    assertion_kind TEXT NOT NULL DEFAULT 'observed',   -- observed|inferred
    source_system_id INTEGER REFERENCES source_system(source_system_id),
    extraction_run_id INTEGER REFERENCES derivation_run(run_id),
    dedupe_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_window ON event(start_day_min, start_day_max, end_day_max);
CREATE INDEX IF NOT EXISTS idx_event_type_window ON event(event_type, start_day_min);
CREATE UNIQUE INDEX IF NOT EXISTS idx_event_dedupe ON event(dedupe_key) WHERE dedupe_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS event_participant (
    event_id INTEGER NOT NULL REFERENCES event(event_id) ON DELETE CASCADE,
    core_entity_id INTEGER,                -- logical ref -> investigation.db entities(id)
    derived_person_id INTEGER,             -- -> canonical_person(person_id) when not yet in core
    raw_name TEXT,
    role TEXT NOT NULL,                    -- sender|recipient|passenger|payer|payee|participant
    resolution_confidence REAL,
    PRIMARY KEY (event_id, role, raw_name)
);
CREATE INDEX IF NOT EXISTS idx_event_participant_core ON event_participant(core_entity_id);
CREATE INDEX IF NOT EXISTS idx_event_participant_derived ON event_participant(derived_person_id);

CREATE TABLE IF NOT EXISTS event_evidence (
    event_id INTEGER NOT NULL REFERENCES event(event_id) ON DELETE CASCADE,
    evidence_item_id INTEGER REFERENCES evidence_item(evidence_item_id),
    canonical_ref TEXT,                    -- denormalized EFTA for convenience
    source_locator TEXT,                   -- json path / line / table row
    PRIMARY KEY (event_id, canonical_ref, source_locator)
);

-- ─────────────────────────── financial model ─────────────────────────────
-- Amounts are signed INTEGER minor units (cents); raw string always preserved.
CREATE TABLE IF NOT EXISTS financial_account (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_key TEXT UNIQUE,               -- normalized (owner|bank|last4)
    institution_name TEXT,
    owner_entity_id INTEGER,               -- -> investigation.db entities(id)
    owner_raw TEXT,
    account_type TEXT,
    account_digits TEXT,
    currency TEXT DEFAULT 'USD',
    resolution_confidence REAL
);

CREATE TABLE IF NOT EXISTS financial_statement (
    statement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES financial_account(account_id),
    period_start_day INTEGER,
    period_end_day INTEGER,
    statement_date_day INTEGER,
    beginning_balance_minor INTEGER,
    ending_balance_minor INTEGER,
    recon_status TEXT,                     -- ok|delta|unknown (from LMSBAND recon)
    recon_delta_minor INTEGER,
    evidence_item_id INTEGER REFERENCES evidence_item(evidence_item_id)
);

CREATE TABLE IF NOT EXISTS merchant (
    merchant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    merchant_category TEXT,
    is_structural INTEGER NOT NULL DEFAULT 0   -- 1 = "Beginning Balance"/"Interest Payment" etc: exclude from spend
);

CREATE TABLE IF NOT EXISTS financial_transaction (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system_id INTEGER REFERENCES source_system(source_system_id),
    source_native_id TEXT NOT NULL,
    evidence_item_id INTEGER REFERENCES evidence_item(evidence_item_id),
    canonical_ref TEXT,
    statement_id INTEGER REFERENCES financial_statement(statement_id),
    account_id INTEGER REFERENCES financial_account(account_id),
    txn_day_min INTEGER,
    txn_day_max INTEGER,
    amount_minor INTEGER,                  -- signed; negative = outflow
    currency TEXT DEFAULT 'USD',
    direction TEXT,                        -- debit|credit|unknown
    txn_type TEXT,                         -- card|wire|check|deposit|transfer|fee|interest
    merchant_id INTEGER REFERENCES merchant(merchant_id),
    cardholder_entity_id INTEGER,
    cardholder_raw TEXT,                   -- raw statement cardholder/account owner (resolution -> cardholder_entity_id later)
    counterparty_entity_id INTEGER,
    counterparty_raw TEXT,
    raw_amount TEXT,
    raw_description TEXT,
    parse_confidence REAL,
    is_outlier INTEGER NOT NULL DEFAULT 0,
    is_duplicate_of INTEGER REFERENCES financial_transaction(transaction_id),
    dedupe_key TEXT,
    UNIQUE(source_system_id, source_native_id)
);
CREATE INDEX IF NOT EXISTS idx_txn_day ON financial_transaction(txn_day_min);
CREATE INDEX IF NOT EXISTS idx_txn_counterparty ON financial_transaction(counterparty_entity_id);
CREATE INDEX IF NOT EXISTS idx_txn_cardholder ON financial_transaction(cardholder_entity_id);
CREATE INDEX IF NOT EXISTS idx_txn_merchant ON financial_transaction(merchant_id);
CREATE INDEX IF NOT EXISTS idx_txn_dedupe ON financial_transaction(dedupe_key);

CREATE TABLE IF NOT EXISTS balance_snapshot (
    balance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES financial_account(account_id),
    owner_raw TEXT,
    as_of_day INTEGER NOT NULL,
    balance_minor INTEGER NOT NULL,
    currency TEXT DEFAULT 'USD',
    evidence_item_id INTEGER REFERENCES evidence_item(evidence_item_id)
);
CREATE INDEX IF NOT EXISTS idx_balance_day ON balance_snapshot(as_of_day);

CREATE TABLE IF NOT EXISTS security (
    security_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    identifier_type TEXT,
    identifier_value TEXT
);

CREATE TABLE IF NOT EXISTS position_snapshot (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES financial_account(account_id),
    owner_raw TEXT,
    security_id INTEGER REFERENCES security(security_id),
    as_of_day INTEGER NOT NULL,
    market_value_minor INTEGER,
    cost_basis_minor INTEGER,
    currency TEXT DEFAULT 'USD',
    is_outlier INTEGER NOT NULL DEFAULT 0,
    evidence_item_id INTEGER REFERENCES evidence_item(evidence_item_id)
);

CREATE TABLE IF NOT EXISTS fin_flight (
    flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system_id INTEGER REFERENCES source_system(source_system_id),
    source_native_id TEXT,
    evidence_item_id INTEGER REFERENCES evidence_item(evidence_item_id),
    passenger_entity_id INTEGER,
    passenger_raw TEXT,
    flight_day INTEGER,
    airline TEXT,
    flight_number TEXT,
    origin TEXT,
    destination TEXT,
    ticket_cost_minor INTEGER,
    ticket_number TEXT,
    record_locator TEXT,
    linked_txn_id INTEGER REFERENCES financial_transaction(transaction_id)
);
CREATE INDEX IF NOT EXISTS idx_flight_day ON fin_flight(flight_day);

-- ─────────────────────── entity / nickname resolution ────────────────────
-- Sidecar-local canonical persons, bridged to core entities via entity_crosswalk.
-- These are CANDIDATES until reconciled; core `entities` remains authoritative.
CREATE TABLE IF NOT EXISTS canonical_person (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    normalized_key TEXT,
    surname_metaphone TEXT,
    category TEXT,
    core_entity_id INTEGER,                -- set once reconciled to investigation.db
    seed_source TEXT,                      -- kabass_persons|curated_docs|name_aliases|derived
    mention_count INTEGER DEFAULT 0,
    doc_count INTEGER DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'unreviewed'
);
CREATE INDEX IF NOT EXISTS idx_canon_person_key ON canonical_person(normalized_key);
CREATE INDEX IF NOT EXISTS idx_canon_person_metaphone ON canonical_person(surname_metaphone);
CREATE INDEX IF NOT EXISTS idx_canon_person_core ON canonical_person(core_entity_id);

CREATE TABLE IF NOT EXISTS person_mention (
    raw_value TEXT PRIMARY KEY,            -- distinct kabass entities.value string
    canonical_id INTEGER REFERENCES canonical_person(person_id),
    match_method TEXT,                     -- exact_norm|phonetic|nickname|fuzzy|llm|seed
    score REAL,
    confidence TEXT,                       -- high|medium|low (inference -> <= medium)
    mention_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_person_mention_canon ON person_mention(canonical_id);

-- The bridge: a sidecar person -> a core entity. status gates promotion.
CREATE TABLE IF NOT EXISTS entity_crosswalk (
    derived_person_id INTEGER NOT NULL REFERENCES canonical_person(person_id),
    core_entity_id INTEGER,                -- investigation.db entities(id)
    match_method TEXT NOT NULL,
    match_score REAL,
    match_status TEXT NOT NULL DEFAULT 'candidate',   -- candidate|reviewed|rejected|redirected
    run_id INTEGER REFERENCES derivation_run(run_id),
    PRIMARY KEY (derived_person_id, core_entity_id)
);

-- ───────────────── redaction inference (schema only; Phase 3 builder) ─────
CREATE TABLE IF NOT EXISTS masked_mention (
    masked_mention_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_item_id INTEGER REFERENCES evidence_item(evidence_item_id),
    canonical_ref TEXT,
    field_path TEXT,                       -- email_fields.from_field | inline
    literal_text TEXT NOT NULL,
    mask_type TEXT NOT NULL,               -- foia_b6 | foia_b7c | redacted | initials | truncated
    surviving_fragment TEXT,
    surviving_domain TEXT,
    context_before TEXT,
    context_after TEXT,
    occurrence_signature TEXT,
    UNIQUE(evidence_item_id, field_path, occurrence_signature)
);
CREATE TABLE IF NOT EXISTS candidate_hypothesis (
    hypothesis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    masked_mention_id INTEGER NOT NULL REFERENCES masked_mention(masked_mention_id),
    candidate_core_entity_id INTEGER,
    candidate_derived_person_id INTEGER REFERENCES canonical_person(person_id),
    probability REAL NOT NULL,
    model_version TEXT,
    status TEXT NOT NULL DEFAULT 'candidate',   -- candidate|reviewed|rejected
    explanation TEXT,
    rank INTEGER
);
CREATE TABLE IF NOT EXISTS candidate_feature (
    hypothesis_id INTEGER NOT NULL REFERENCES candidate_hypothesis(hypothesis_id),
    feature_type TEXT NOT NULL,            -- domain|fragment|cooccurrence|timing|signature|stylometry
    feature_value TEXT,
    weight REAL NOT NULL,
    polarity TEXT NOT NULL DEFAULT 'supports',  -- supports|contradicts
    evidence_ref TEXT,
    PRIMARY KEY (hypothesis_id, feature_type, feature_value)
);
"""

# Seed rows for the source_system dimension (idempotent).
SOURCE_SYSTEMS = [
    ("kabasshouse", "reocr", "DOJ-primary"),
    ("lmsband", "extraction", "DOJ-primary"),
    ("unified", "extraction", "DOJ-primary"),
    ("doj_vol11", "primary_release", "DOJ-primary"),
    ("fbi", "primary_release", "FBI-release"),
    ("house_oversight", "primary_release", "House-release"),
]


def get_db(path=DERIVED_DB):
    # uri=True so read-only ATTACH of source DBs (file:...?mode=ro) is honored.
    db = sqlite3.connect(f"file:{path}", uri=True, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=60000")  # absorb write contention when builders run in parallel
    return db


def attach(db, alias, path):
    """ATTACH a read-only source DB (kabass/lmsband/unified/core) for a build."""
    db.execute(f"ATTACH DATABASE 'file:{path}?mode=ro' AS {alias}")


# Additive column migrations for DBs created before a column existed. CREATE
# TABLE IF NOT EXISTS never alters an existing table, so new columns are applied
# here (idempotent — a duplicate-column error is swallowed).
_COLUMN_MIGRATIONS = [
    ("financial_transaction", "cardholder_raw", "TEXT"),
]


def init_schema(db):
    db.executescript(SCHEMA)
    for table, col, col_def in _COLUMN_MIGRATIONS:
        try:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already present
    db.execute("INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
               (str(SCHEMA_VERSION),))
    for name, cls, grp in SOURCE_SYSTEMS:
        db.execute(
            "INSERT OR IGNORE INTO source_system(name, source_class, default_independence_group) "
            "VALUES (?, ?, ?)", (name, cls, grp))
    db.commit()


def new_run(db, builder, note=None, code_version=None):
    """Open a derivation_run, stamping the core corrections high-water mark."""
    hw = None
    try:
        core = sqlite3.connect(f"file:{CORE_DB}?mode=ro", uri=True)
        row = core.execute("SELECT MAX(id) FROM corrections").fetchone()
        hw = row[0] if row else None
        core.close()
    except Exception:
        pass
    cur = db.execute(
        "INSERT INTO derivation_run(builder, code_version, core_correction_highwater, note) "
        "VALUES (?, ?, ?, ?)", (builder, code_version, hw, note))
    db.commit()
    return cur.lastrowid


def source_system_id(db, name):
    row = db.execute("SELECT source_system_id FROM source_system WHERE name = ?", (name,)).fetchone()
    return row[0] if row else None


def _cli():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create all tables + seed source_system")
    sub.add_parser("stats", help="row counts per table")
    nr = sub.add_parser("new-run", help="open a derivation_run, print run_id")
    nr.add_argument("builder")
    nr.add_argument("--note")
    args = ap.parse_args()

    db = get_db()
    if args.cmd == "init":
        init_schema(db)
        n = len(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
        print(f"initialized {DERIVED_DB} — {n} tables, schema v{SCHEMA_VERSION}")
    elif args.cmd == "stats":
        init_schema(db)
        for (name,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            try:
                c = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                print(f"  {name:28} {c:>12,}")
            except sqlite3.Error:
                pass
    elif args.cmd == "new-run":
        init_schema(db)
        print(new_run(db, args.builder, note=args.note))
    db.close()


if __name__ == "__main__":
    _cli()
