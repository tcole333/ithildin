#!/usr/bin/env python3
"""Schema contract for the DOJ/SEC primary-government press-release corpus."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "datasets" / "government_releases.db"
SCHEMA_VERSION = 2

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ingest_run(
  id INTEGER PRIMARY KEY AUTOINCREMENT, agency TEXT NOT NULL, mode TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at TEXT,
  records_seen INTEGER DEFAULT 0, records_changed INTEGER DEFAULT 0,
  cursor_start TEXT, cursor_end TEXT, error TEXT, parameters_json TEXT
);
CREATE TABLE IF NOT EXISTS ingest_state(
  key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS government_release(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agency TEXT NOT NULL CHECK(agency IN ('DOJ','SEC')),
  native_id TEXT NOT NULL,
  source_ref TEXT NOT NULL UNIQUE,
  release_number TEXT,
  title TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  published_at TEXT,
  updated_at TEXT,
  component_text TEXT,
  topic_text TEXT,
  teaser TEXT,
  fetch_status TEXT NOT NULL DEFAULT 'pending' CHECK(fetch_status IN ('pending','complete','failed','metadata_only')),
  fetch_error TEXT,
  current_version_id INTEGER,
  first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(agency,native_id)
);
CREATE INDEX IF NOT EXISTS idx_govrel_agency_date ON government_release(agency,published_at);
CREATE INDEX IF NOT EXISTS idx_govrel_number ON government_release(release_number);
CREATE INDEX IF NOT EXISTS idx_govrel_url ON government_release(canonical_url);
CREATE INDEX IF NOT EXISTS idx_govrel_status ON government_release(agency,fetch_status);
CREATE TABLE IF NOT EXISTS government_release_version(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  release_id INTEGER NOT NULL REFERENCES government_release(id) ON DELETE CASCADE,
  retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  content_text TEXT,
  content_hash TEXT NOT NULL,
  raw_metadata_json TEXT,
  version_status TEXT NOT NULL DEFAULT 'current' CHECK(version_status IN ('current','superseded','corrected','retracted')),
  UNIQUE(release_id,content_hash)
);
CREATE VIRTUAL TABLE IF NOT EXISTS government_release_fts USING fts5(
  release_id UNINDEXED,title,teaser,component_text,topic_text,content_text,
  tokenize='porter unicode61'
);
"""


def connect(path: Path | str = DEFAULT_DB_PATH, *, create: bool = True) -> sqlite3.Connection:
    db_path = Path(path)
    if not create and not db_path.exists():
        raise FileNotFoundError(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=60000")
    if create:
        db.executescript(SCHEMA)
        row = db.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        previous_version = int(row[0]) if row else 0
        if previous_version < 2:
            rebuild_fts(db)
        db.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
        db.commit()
    return db


def content_hash(*values: str | None) -> str:
    return hashlib.sha256("\n\0\n".join(v or "" for v in values).encode("utf-8", errors="replace")).hexdigest()


def rebuild_fts(db: sqlite3.Connection) -> None:
    """Rebuild FTS with release IDs as rowids for constant-time refreshes."""
    db.execute("DELETE FROM government_release_fts")
    db.execute(
        """INSERT INTO government_release_fts(
           rowid,release_id,title,teaser,component_text,topic_text,content_text)
           SELECT r.id,r.id,r.title,r.teaser,r.component_text,r.topic_text,v.content_text
           FROM government_release r
           LEFT JOIN government_release_version v ON v.id=r.current_version_id"""
    )


def refresh_fts(db: sqlite3.Connection, release_id: int) -> None:
    row = db.execute(
        """SELECT r.*,v.content_text FROM government_release r
           LEFT JOIN government_release_version v ON v.id=r.current_version_id WHERE r.id=?""",
        (release_id,),
    ).fetchone()
    db.execute("DELETE FROM government_release_fts WHERE rowid=?", (release_id,))
    if row:
        db.execute(
            """INSERT INTO government_release_fts(
               rowid,release_id,title,teaser,component_text,topic_text,content_text)
               VALUES(?,?,?,?,?,?,?)""",
            (row["id"],row["id"],row["title"],row["teaser"],row["component_text"],row["topic_text"],row["content_text"]),
        )
