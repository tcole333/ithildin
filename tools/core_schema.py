"""Versioned, schema-only additions shared by startup and explicit backfills.

The historical core-v2 script owns reviewed data backfills. Normal startup must
install its schema too, without claiming those backfills have been performed.
"""

SCHEMA_MIGRATION_ID = "2026-09-05_core_model_v2_schema"

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


def ensure_core_model_schema(db):
    """Install current additive core DDL atomically within the caller's transaction.

    A distinct ledger entry records schema installation only; the explicit v2
    migration retains its own ID for the historical backfills. A savepoint avoids
    executescript's implicit commit of unrelated caller writes.
    """
    db.execute("SAVEPOINT core_model_schema")
    try:
        statements = [statement.strip() for statement in DDL.split(";") if statement.strip()]
        db.execute(statements[0])  # The ledger must exist before inspecting it.
        if not db.execute(
            "SELECT 1 FROM schema_migrations WHERE migration_id = ?",
            (SCHEMA_MIGRATION_ID,),
        ).fetchone():
            for statement in statements[1:]:
                db.execute(statement)
            columns = {row[1] for row in db.execute("PRAGMA table_info(findings)")}
            for column in ("event_date_iso", "date_precision"):
                if column not in columns:
                    db.execute(f"ALTER TABLE findings ADD COLUMN {column} TEXT")
            db.execute(
                "INSERT INTO schema_migrations(migration_id, note) VALUES (?, ?)",
                (SCHEMA_MIGRATION_ID, "Core-v2 schema installed; no historical data backfills"),
            )
    except Exception:
        db.execute("ROLLBACK TO core_model_schema")
        raise
    finally:
        db.execute("RELEASE core_model_schema")
