#!/usr/bin/env python3
"""Core investigation.db model migration (Phase 1, additive / expand phase).

Adds the structural seams the epstein_derived.db sidecar will bolt onto, WITHOUT
touching existing columns, IDs, or the corrections/FTS machinery. Everything here
is expand-only: new tables + new nullable columns + deterministic, conservative
backfills. Legacy columns (target_name, date_of_event, name_aliases) stay as
dual-read fallbacks. Ambiguous work (fuzzy entity merges, profile remaps) is left
to dedicated review passes — this migration only makes links it is certain about.

What it creates:
  1. finding_entities   — findings <-> entities junction (fixes identity-by-string)
  2. finding_relations  — contradicts/corroborates/supersedes claim graph
  3. findings.event_date_iso + date_precision  — precision-aware temporal columns
  4. investigation_profiles — profile catalog (containment, not enforcement yet)
  5. data_change_sets   — batch provenance for corrections/backfills
  6. schema_migrations  — ordered migration ledger

Backfills (deterministic only):
  - event_date_iso/date_precision from date_of_event via tools.date_normalize
  - finding_entities from an EXACT (case-insensitive) target_name -> entities.name
    match, or a name_aliases alias -> entity_id link. No fuzzy matching here.
  - finding_relations seeded from explicit "#<id>" references inside
    corrections.reason on dispute/retraction rows.

Usage:
    uv run python scripts/migrate_core_model_v2.py --dry-run
    uv run python scripts/migrate_core_model_v2.py --apply
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from tools.date_normalize import normalize_date  # noqa: E402

DB = PROJECT_ROOT / "investigation.db"
MIGRATION_ID = "2026-07-04_core_model_v2"

DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note         TEXT
);

CREATE TABLE IF NOT EXISTS investigation_profiles (
    profile_id   TEXT PRIMARY KEY,
    display_name TEXT,
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finding_entities (
    finding_id        INTEGER NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    entity_id         INTEGER NOT NULL REFERENCES entities(id),
    mention_role      TEXT NOT NULL DEFAULT 'subject',
    raw_name          TEXT,
    resolution_status TEXT NOT NULL DEFAULT 'asserted',   -- asserted|candidate|reviewed
    resolution_method TEXT,                                -- exact|alias|fuzzy|manual
    resolution_score  REAL,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (finding_id, entity_id, mention_role)
);
CREATE INDEX IF NOT EXISTS idx_finding_entities_entity ON finding_entities(entity_id);

CREATE TABLE IF NOT EXISTS finding_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_finding_id INTEGER NOT NULL REFERENCES findings(id),
    to_finding_id   INTEGER NOT NULL REFERENCES findings(id),
    relation_type   TEXT NOT NULL CHECK (relation_type IN
        ('contradicts','corroborates','supersedes','duplicates','refines','depends_on')),
    assessment TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (from_finding_id <> to_finding_id),
    UNIQUE (from_finding_id, to_finding_id, relation_type)
);
CREATE INDEX IF NOT EXISTS idx_finding_relations_to ON finding_relations(to_finding_id);

CREATE TABLE IF NOT EXISTS data_change_sets (
    change_set_id TEXT PRIMARY KEY,
    change_kind   TEXT NOT NULL,   -- semantic_correction|backfill|schema_migration|deduplication
    actor         TEXT NOT NULL,
    reason        TEXT NOT NULL,
    started_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at  TEXT
);
"""

REF_RE = re.compile(r"#(\d+)")


def col_exists(db, table, col):
    return any(r[1] == col for r in db.execute(f"PRAGMA table_info({table})"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=OFF")  # backfill inserts reference existing rows only

    report = {}

    # ---- 1. DDL (idempotent) ----
    if apply:
        db.executescript(DDL)
        # additive columns (guarded)
        if not col_exists(db, "findings", "event_date_iso"):
            db.execute("ALTER TABLE findings ADD COLUMN event_date_iso TEXT")
        if not col_exists(db, "findings", "date_precision"):
            db.execute("ALTER TABLE findings ADD COLUMN date_precision TEXT")
        db.commit()

    # ---- 2. profile catalog backfill ----
    profiles = [r[0] for r in db.execute(
        "SELECT DISTINCT profile_id FROM findings WHERE profile_id IS NOT NULL")]
    report["profiles_cataloged"] = len(profiles)
    if apply:
        for p in profiles:
            db.execute("INSERT OR IGNORE INTO investigation_profiles(profile_id, display_name) VALUES (?, ?)",
                       (p, p))
        db.commit()

    # ---- 3. date normalization backfill ----
    dated = db.execute(
        "SELECT id, date_of_event FROM findings WHERE date_of_event IS NOT NULL AND date_of_event != ''"
    ).fetchall()
    date_stats = {"day": 0, "month": 0, "year": 0, "unknown": 0}
    date_updates = []
    for row in dated:
        iso, prec = normalize_date(row["date_of_event"])
        date_stats[prec] += 1
        if iso:
            date_updates.append((iso, prec, row["id"]))
    report["dates_parsed"] = date_stats
    if apply:
        db.executemany(
            "UPDATE findings SET event_date_iso = ?, date_precision = ? WHERE id = ?", date_updates)
        db.commit()

    # ---- 4. finding_entities backfill (EXACT + ALIAS only) ----
    # Build lookups once.
    name_to_id = {}
    for r in db.execute("SELECT id, name FROM entities WHERE name IS NOT NULL"):
        name_to_id.setdefault(r["name"].strip().lower(), r["id"])
    alias_to_id = {}
    for r in db.execute("SELECT alias, entity_id FROM name_aliases WHERE entity_id IS NOT NULL"):
        if r["alias"]:
            alias_to_id.setdefault(r["alias"].strip().lower(), r["entity_id"])

    findings = db.execute("SELECT id, target_name FROM findings WHERE target_name IS NOT NULL").fetchall()
    links = []       # (finding_id, entity_id, method)
    linked = exact = alias = unmatched = 0
    for row in findings:
        key = (row["target_name"] or "").strip().lower()
        if not key:
            continue
        eid = name_to_id.get(key)
        method = "exact"
        if eid is None:
            eid = alias_to_id.get(key)
            method = "alias"
        if eid is None:
            unmatched += 1
            continue
        links.append((row["id"], eid, method))
        linked += 1
        exact += method == "exact"
        alias += method == "alias"
    report["finding_entities"] = {
        "linked": linked, "via_exact": exact, "via_alias": alias,
        "unmatched_left_for_resolver": unmatched,
    }
    if apply:
        db.executemany(
            """INSERT OR IGNORE INTO finding_entities
                   (finding_id, entity_id, mention_role, raw_name, resolution_status, resolution_method)
               SELECT ?, ?, 'subject', (SELECT target_name FROM findings WHERE id = ?), 'asserted', ?""",
            [(fid, eid, fid, method) for (fid, eid, method) in links])
        db.commit()

    # ---- 5. finding_relations seed from corrections.reason ----
    valid_ids = {r[0] for r in db.execute("SELECT id FROM findings")}
    rel_rows = db.execute("""
        SELECT record_id, reason, correction_type FROM corrections
        WHERE table_name = 'findings' AND reason LIKE '%#%'
          AND (correction_type IN ('retraction') OR reason LIKE '%ontradict%'
               OR reason LIKE '%upersede%' OR reason LIKE '%onflict%')
    """).fetchall()
    seeds = []
    for r in rel_rows:
        src = r["record_id"]
        if src not in valid_ids:
            continue
        low = (r["reason"] or "").lower()
        if "contradict" in low or "conflict" in low:
            rtype = "contradicts"
        elif "supersede" in low:
            rtype = "supersedes"
        else:
            continue
        for ref in REF_RE.findall(r["reason"]):
            tgt = int(ref)
            if tgt in valid_ids and tgt != src:
                seeds.append((src, tgt, rtype, (r["reason"] or "")[:300]))
    report["finding_relations_seeded"] = len(seeds)
    if apply:
        db.executemany(
            """INSERT OR IGNORE INTO finding_relations
                   (from_finding_id, to_finding_id, relation_type, assessment, created_by)
               VALUES (?, ?, ?, ?, 'migrate_core_model_v2')""", seeds)
        db.commit()

    # ---- record migration ----
    if apply:
        db.execute("INSERT OR IGNORE INTO schema_migrations(migration_id, note) VALUES (?, ?)",
                   (MIGRATION_ID, "additive: finding_entities, finding_relations, ISO dates, "
                                  "profile catalog, change sets"))
        db.commit()

    db.close()

    label = "APPLIED" if apply else "DRY RUN"
    print(f"=== core model migration v2 ({label}) ===")
    import json
    print(json.dumps(report, indent=2))
    if not apply:
        print("\n(no writes performed; re-run with --apply)")


if __name__ == "__main__":
    main()
