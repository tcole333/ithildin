#!/usr/bin/env python3
"""Schema and shared helpers for the Epstein reporting knowledge layer.

This module is the single schema contract for ``datasets/epstein_reporting.db``.
Reporting is deliberately kept outside ``investigation.db``: an article can
assert a claim without making that claim an investigative finding.  Promotion
requires a separately reviewed primary-evidence link.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "datasets" / "epstein_reporting.db"
CORE_DB_PATH = PROJECT_ROOT / "investigation.db"
SCHEMA_VERSION = 10

TRACKING_PARAMS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "source",
}

LANGUAGE_ALIASES = {
    "english": "en", "german": "de", "turkish": "tr", "french": "fr",
    "spanish": "es", "italian": "it", "hebrew": "he", "portuguese": "pt",
    "chinese": "zh", "japanese": "ja", "russian": "ru", "polish": "pl",
    "norwegian": "no", "korean": "ko", "kr": "ko", "arabic": "ar", "dutch": "nl",
    "swedish": "sv", "danish": "da", "greek": "el",
}

COUNTRY_ALIASES = {
    "united states": "US", "united kingdom": "GB", "germany": "DE",
    "australia": "AU", "austria": "AT", "canada": "CA", "egypt": "EG",
    "india": "IN", "ireland": "IE", "japan": "JP", "malaysia": "MY",
    "new zealand": "NZ", "norway": "NO", "pakistan": "PK", "singapore": "SG",
    "south africa": "ZA", "sri lanka": "LK", "turkey": "TR",
    "virgin islands": "VI",
}

SCHEMA = r"""
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method TEXT NOT NULL,
    query TEXT,
    source_name TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    result_count INTEGER,
    imported_count INTEGER,
    parameters_json TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS publisher (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT UNIQUE,
    country TEXT,
    default_language TEXT,
    source_type TEXT NOT NULL DEFAULT 'secondary_quality' CHECK(source_type IN (
        'secondary_quality', 'secondary_compromised', 'secondary_blog',
        'wire_service', 'trade_press', 'broadcast', 'academic', 'unknown'
    )),
    reliability_notes TEXT,
    epstein_connection TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS author (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    affiliation TEXT,
    reliability_notes TEXT,
    epstein_connection TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reporting_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL DEFAULT 'article' CHECK(item_type IN (
        'article', 'investigation_series', 'newsletter', 'book_chapter',
        'podcast', 'broadcast_transcript', 'blog_post', 'other'
    )),
    title TEXT NOT NULL,
    dek TEXT,
    canonical_url TEXT NOT NULL UNIQUE,
    publisher_id INTEGER REFERENCES publisher(id),
    published_at TEXT,
    updated_at TEXT,
    language TEXT,
    access_status TEXT NOT NULL DEFAULT 'unknown' CHECK(access_status IN (
        'open', 'paywalled', 'licensed', 'archive_only', 'unavailable', 'unknown'
    )),
    rights_status TEXT NOT NULL DEFAULT 'metadata_only' CHECK(rights_status IN (
        'metadata_only', 'local_research', 'redistributable', 'unknown'
    )),
    abstract TEXT,
    source_native_id TEXT,
    discovery_method TEXT,
    independence_group TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_version_id INTEGER,
    notes TEXT
    ,scope_class TEXT NOT NULL DEFAULT 'direct' CHECK(scope_class IN ('candidate','direct','contextual','background'))
);
CREATE INDEX IF NOT EXISTS idx_reporting_item_published ON reporting_item(published_at);
CREATE INDEX IF NOT EXISTS idx_reporting_item_publisher ON reporting_item(publisher_id);
CREATE INDEX IF NOT EXISTS idx_reporting_item_group ON reporting_item(independence_group);

CREATE TABLE IF NOT EXISTS item_author (
    item_id INTEGER NOT NULL REFERENCES reporting_item(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES author(id),
    position INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(item_id, author_id)
);

CREATE TABLE IF NOT EXISTS item_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES reporting_item(id) ON DELETE CASCADE,
    retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_url TEXT NOT NULL,
    archive_url TEXT,
    content_text TEXT,
    content_hash TEXT NOT NULL,
    metadata_json TEXT,
    version_status TEXT NOT NULL DEFAULT 'current' CHECK(version_status IN (
        'current', 'superseded', 'corrected', 'retracted', 'unavailable'
    )),
    change_summary TEXT,
    UNIQUE(item_id, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_item_version_item ON item_version(item_id, retrieved_at);

CREATE TABLE IF NOT EXISTS discovery_candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    publisher_domain TEXT,
    published_at TEXT,
    language TEXT,
    discovery_run_id INTEGER REFERENCES discovery_run(id),
    discovery_method TEXT NOT NULL,
    query TEXT,
    metadata_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN (
        'pending', 'ingested', 'duplicate', 'excluded', 'failed'
    )),
    status_note TEXT,
    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TEXT
    ,scope_class TEXT NOT NULL DEFAULT 'candidate' CHECK(scope_class IN ('candidate','direct','contextual','background'))
);
CREATE INDEX IF NOT EXISTS idx_candidate_status ON discovery_candidate(status, discovered_at);

CREATE TABLE IF NOT EXISTS reporting_claim (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES reporting_item(id) ON DELETE CASCADE,
    version_id INTEGER REFERENCES item_version(id),
    claim_text TEXT NOT NULL,
    subject_text TEXT,
    predicate TEXT,
    object_text TEXT,
    event_date_raw TEXT,
    amount_raw TEXT,
    attribution TEXT,
    claim_kind TEXT NOT NULL DEFAULT 'paraphrase' CHECK(claim_kind IN (
        'direct_quote', 'paraphrase', 'inference', 'synthesis'
    )),
    verification_status TEXT NOT NULL DEFAULT 'reported_only' CHECK(verification_status IN (
        'reported_only', 'primary_supported', 'independently_corroborated',
        'partially_supported', 'contradicted', 'superseded', 'retracted', 'unresolved'
    )),
    confidence TEXT NOT NULL DEFAULT 'unverified' CHECK(confidence IN (
        'unverified', 'low', 'medium', 'high', 'confirmed'
    )),
    source_excerpt TEXT,
    source_locator TEXT,
    extracted_by TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    ,claim_fingerprint TEXT
);
CREATE INDEX IF NOT EXISTS idx_claim_status ON reporting_claim(verification_status);
CREATE INDEX IF NOT EXISTS idx_claim_item ON reporting_claim(item_id);

CREATE TABLE IF NOT EXISTS claim_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL REFERENCES reporting_claim(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK(source_type IN (
        'primary_document', 'named_interview', 'anonymous_source', 'other_reporting',
        'personal_observation', 'analysis', 'unspecified'
    )),
    source_ref TEXT NOT NULL,
    source_description TEXT,
    source_quote TEXT,
    source_page TEXT,
    independence_group TEXT,
    assessment TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0, 1)),
    UNIQUE(claim_id, source_ref)
);
CREATE INDEX IF NOT EXISTS idx_claim_source_ref ON claim_source(source_ref);

CREATE TABLE IF NOT EXISTS item_relation (
    from_item_id INTEGER NOT NULL REFERENCES reporting_item(id) ON DELETE CASCADE,
    to_item_id INTEGER NOT NULL REFERENCES reporting_item(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK(relation_type IN (
        'syndicates', 'rewrites', 'translates', 'follows_up', 'corrects',
        'retracts', 'duplicates', 'cites'
    )),
    assessment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(from_item_id, to_item_id, relation_type)
);

CREATE TABLE IF NOT EXISTS claim_relation (
    from_claim_id INTEGER NOT NULL REFERENCES reporting_claim(id) ON DELETE CASCADE,
    to_claim_id INTEGER NOT NULL REFERENCES reporting_claim(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK(relation_type IN (
        'corroborates', 'contradicts', 'supersedes', 'duplicates', 'derives_from'
    )),
    assessment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(from_claim_id, to_claim_id, relation_type)
);

CREATE TABLE IF NOT EXISTS item_entity (
    item_id INTEGER NOT NULL REFERENCES reporting_item(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL,
    mention_text TEXT NOT NULL,
    match_method TEXT NOT NULL,
    confidence REAL,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate', 'accepted', 'rejected')),
    PRIMARY KEY(item_id, entity_id, mention_text)
);

CREATE TABLE IF NOT EXISTS claim_entity (
    claim_id INTEGER NOT NULL REFERENCES reporting_claim(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL,
    role TEXT,
    mention_text TEXT,
    PRIMARY KEY(claim_id, entity_id, role)
);

CREATE TABLE IF NOT EXISTS claim_promotion (
    claim_id INTEGER PRIMARY KEY REFERENCES reporting_claim(id) ON DELETE CASCADE,
    finding_id INTEGER NOT NULL,
    promoted_by TEXT NOT NULL,
    promoted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    primary_evidence_refs_json TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS reporting_fts USING fts5(
    item_id UNINDEXED,
    title,
    dek,
    abstract,
    content_text,
    tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS claim_fts USING fts5(
    claim_id UNINDEXED,
    claim_text,
    subject_text,
    object_text,
    attribution,
    tokenize='porter unicode61'
);
"""


def normalize_url(url: str) -> str:
    """Canonicalize a URL for article-level deduplication."""
    raw = (url or "").strip()
    if not raw:
        raise ValueError("URL is required")
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"Unsupported URL: {url}")
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = f":{parts.port}" if parts.port and parts.port not in {80, 443} else ""
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit(("https", host + port, path, urlencode(sorted(query)), ""))


def domain_from_url(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def normalize_language(value: str | None) -> str | None:
    """Normalize language names and locale tags to a base ISO code."""
    raw = (value or "").strip()
    if not raw or raw.casefold() in {"unknown", "und", "undefined"}:
        return None
    folded = raw.casefold()
    if folded in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[folded]
    base = re.split(r"[-_]", folded, maxsplit=1)[0]
    if base in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[base]
    if re.fullmatch(r"[a-z]{2,3}", base):
        return base
    return folded


def normalize_published_at(value: str | None) -> str | None:
    """Normalize compact discovery timestamps while preserving valid ISO text."""
    raw = (value or "").strip()
    if not raw or raw.casefold() in {"unknown", "undefined", "none", "null", "tz"}:
        return None
    repeated_offset = re.fullmatch(r"(.+)([+-]\d{2}:\d{2})\2", raw)
    if repeated_offset:
        raw = repeated_offset.group(1) + repeated_offset.group(2)
    match = re.fullmatch(
        r"[^,]+,\s*([01]\d)/([0-3]\d)/(19\d{2}|20\d{2})\s*-\s*([0-2]\d):([0-5]\d)",
        raw,
    )
    if match:
        month, day, year, hour, minute = match.groups()
        try:
            parsed = datetime(
                int(year), int(month), int(day), int(hour), int(minute)
            )
        except ValueError:
            return None
        return parsed.isoformat()
    match = re.fullmatch(
        r"([0-3]\d)/([01]\d)/(19\d{2}|20\d{2})\s+[àa]\s+([0-2]\d)h([0-5]\d)",
        raw, re.IGNORECASE,
    )
    if match:
        day, month, year, hour, minute = match.groups()
        try:
            parsed = datetime(
                int(year), int(month), int(day), int(hour), int(minute)
            )
        except ValueError:
            return None
        return parsed.isoformat()
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z", raw)
    if match:
        year, month, day, hour, minute, second = match.groups()
        return f"{year}-{month}-{day}T{hour}:{minute}:{second}Z"
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", raw)
    if match:
        return "-".join(match.groups())
    return raw


def publication_date_from_url(url: str | None) -> str | None:
    """Extract an exact calendar date from known date-bearing article paths."""
    if not url:
        return None
    path = urlsplit(url).path
    match = re.search(r"/(19\d{2}|20\d{2})/(0[1-9]|1[0-2])/([0-2]\d|3[01])(?:/|$)", path)
    if match:
        parts = tuple(int(value) for value in match.groups())
    else:
        match = re.search(r"/(19\d{2}|20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])(?:/|$)", path)
        if match:
            parts = tuple(int(value) for value in match.groups())
        else:
            parts = None
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        if parts is None:
            italian_months = {
                "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
                "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
                "settembre": 9, "ottobre": 10, "novembre": 11,
                "dicembre": 12,
            }
            match = re.search(
                r"/(\d{2})_(" + "|".join(italian_months) + r")_([0-2]\d|3[01])(?:/|$)",
                path, re.IGNORECASE,
            )
            if match:
                short_year = int(match.group(1))
                parts = (
                    2000 + short_year if short_year < 70 else 1900 + short_year,
                    italian_months[match.group(2).lower()],
                    int(match.group(3)),
                )
        if parts is None:
            match = re.search(
                r"/(19\d{2}|20\d{2})/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/([0-2]?\d|3[01])(?:/|$)",
                path, re.IGNORECASE,
            )
            if match:
                parts = (int(match.group(1)), months[match.group(2).lower()], int(match.group(3)))
            else:
                compact = re.search(r"/(19\d{6}|20\d{6})(?:\d{4})?(?:[-/]|$)", path)
                if not compact:
                    return None
                raw = compact.group(1)
                parts = (int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    try:
        return date(*parts).isoformat()
    except ValueError:
        return None


def normalize_country(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw or raw.casefold() in {"0", "unknown", "none", "null"}:
        return None
    if raw.casefold() == "global":
        return "global"
    if raw.casefold() in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[raw.casefold()]
    if re.fullmatch(r"[A-Za-z]{2}", raw):
        return raw.upper()
    return raw


def stable_hash(*parts: str | None) -> str:
    payload = "\n\0\n".join(part or "" for part in parts)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def connect(db_path: Path | str = DEFAULT_DB_PATH, *, create: bool = True) -> sqlite3.Connection:
    path = Path(db_path)
    if not create and not path.exists():
        raise FileNotFoundError(f"Reporting database not found: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    if create:
        initialize(db)
    return db


def initialize(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA)
    row = db.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    if row and int(row[0]) > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema {row[0]} is newer than supported schema {SCHEMA_VERSION}"
        )
    current = int(row[0]) if row else 0
    if current < 2:
        item_cols = {r[1] for r in db.execute("PRAGMA table_info(reporting_item)")}
        candidate_cols = {r[1] for r in db.execute("PRAGMA table_info(discovery_candidate)")}
        if "scope_class" not in item_cols:
            db.execute("ALTER TABLE reporting_item ADD COLUMN scope_class TEXT NOT NULL DEFAULT 'direct'")
        if "scope_class" not in candidate_cols:
            db.execute("ALTER TABLE discovery_candidate ADD COLUMN scope_class TEXT NOT NULL DEFAULT 'candidate'")
    if current < 4:
        claim_cols = {r[1] for r in db.execute("PRAGMA table_info(reporting_claim)")}
        if "claim_fingerprint" not in claim_cols:
            db.execute("ALTER TABLE reporting_claim ADD COLUMN claim_fingerprint TEXT")
    if current < 5:
        for table in ("reporting_item", "discovery_candidate"):
            rows = db.execute(f"SELECT id,language FROM {table} WHERE language IS NOT NULL").fetchall()
            db.executemany(
                f"UPDATE {table} SET language=? WHERE id=?",
                [(normalize_language(row["language"]), row["id"]) for row in rows],
            )
        db.execute("DELETE FROM reporting_fts")
        db.execute(
            """INSERT INTO reporting_fts(rowid,item_id,title,dek,abstract,content_text)
               SELECT i.id,i.id,i.title,i.dek,i.abstract,v.content_text
               FROM reporting_item i LEFT JOIN item_version v ON v.id=i.current_version_id"""
        )
        db.execute("DELETE FROM claim_fts")
        db.execute(
            """INSERT INTO claim_fts(rowid,claim_id,claim_text,subject_text,object_text,attribution)
               SELECT id,id,claim_text,subject_text,object_text,attribution FROM reporting_claim"""
        )
    if current < 6:
        for table, columns in (
            ("reporting_item", ("published_at", "updated_at")),
            ("discovery_candidate", ("published_at",)),
        ):
            for column in columns:
                rows = db.execute(
                    f"SELECT id,{column} FROM {table} WHERE {column} IS NOT NULL"
                ).fetchall()
                db.executemany(
                    f"UPDATE {table} SET {column}=? WHERE id=?",
                    [(normalize_published_at(row[column]), row["id"]) for row in rows],
                )
        missing = db.execute(
            """SELECT id,canonical_url FROM reporting_item
               WHERE published_at IS NULL OR trim(published_at)=''"""
        ).fetchall()
        for item in missing:
            candidate = db.execute(
                """SELECT c.published_at,c.language
                   FROM discovery_candidate c
                   WHERE c.url=? AND c.published_at IS NOT NULL
                   UNION ALL
                   SELECT c.published_at,c.language
                   FROM item_version v JOIN discovery_candidate c
                     ON c.id=CAST(json_extract(v.metadata_json,'$.discovery_candidate_id') AS INTEGER)
                   WHERE v.item_id=? AND c.published_at IS NOT NULL
                   ORDER BY 1 DESC LIMIT 1""",
                (item["canonical_url"], item["id"]),
            ).fetchone()
            if candidate:
                db.execute(
                    """UPDATE reporting_item SET published_at=?,language=COALESCE(language,?)
                       WHERE id=?""",
                    (
                        normalize_published_at(candidate["published_at"]),
                        normalize_language(candidate["language"]), item["id"],
                    ),
                )
    if current < 7:
        publishers = db.execute(
            "SELECT id FROM publisher WHERE country IS NULL OR default_language IS NULL"
        ).fetchall()
        for publisher in publishers:
            candidate = db.execute(
                """SELECT json_extract(c.metadata_json,'$.sourcecountry') country,c.language
                   FROM reporting_item i
                   JOIN item_version v ON v.item_id=i.id
                   JOIN discovery_candidate c
                     ON c.id=CAST(json_extract(v.metadata_json,'$.discovery_candidate_id') AS INTEGER)
                   WHERE i.publisher_id=?
                     AND (json_extract(c.metadata_json,'$.sourcecountry') IS NOT NULL
                          OR c.language IS NOT NULL)
                   ORDER BY v.id DESC LIMIT 1""",
                (publisher["id"],),
            ).fetchone()
            if candidate:
                db.execute(
                    """UPDATE publisher SET country=COALESCE(country,?),
                       default_language=COALESCE(default_language,?),
                       source_type=CASE WHEN country IS NULL THEN 'unknown' ELSE source_type END,
                       updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (
                        candidate["country"], normalize_language(candidate["language"]),
                        publisher["id"],
                    ),
                )
    if current < 8:
        rows = db.execute("SELECT id,country FROM publisher WHERE country IS NOT NULL").fetchall()
        db.executemany(
            "UPDATE publisher SET country=? WHERE id=?",
            [(normalize_country(row["country"]), row["id"]) for row in rows],
        )
    if current < 9:
        missing = db.execute(
            """SELECT id,canonical_url FROM reporting_item
               WHERE published_at IS NULL OR trim(published_at)=''"""
        ).fetchall()
        db.executemany(
            "UPDATE reporting_item SET published_at=? WHERE id=?",
            [
                (inferred, row["id"])
                for row in missing
                if (inferred := publication_date_from_url(row["canonical_url"]))
            ],
        )
    if current < 10:
        db.execute(
            """UPDATE reporting_item SET language=(
                   SELECT default_language FROM publisher WHERE publisher.id=reporting_item.publisher_id
               ) WHERE language IS NULL AND publisher_id IS NOT NULL
                 AND EXISTS (
                   SELECT 1 FROM publisher
                   WHERE publisher.id=reporting_item.publisher_id
                     AND publisher.default_language IS NOT NULL
                 )"""
        )
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_claim_fingerprint ON reporting_claim(item_id,claim_fingerprint)")
    db.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    db.commit()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def refresh_item_fts(db: sqlite3.Connection, item_id: int) -> None:
    row = db.execute(
        """
        SELECT i.id, i.title, i.dek, i.abstract, v.content_text
        FROM reporting_item i
        LEFT JOIN item_version v ON v.id=i.current_version_id
        WHERE i.id=?
        """,
        (item_id,),
    ).fetchone()
    db.execute("DELETE FROM reporting_fts WHERE rowid=?", (item_id,))
    if row:
        db.execute(
            "INSERT INTO reporting_fts(rowid,item_id,title,dek,abstract,content_text) VALUES(?,?,?,?,?,?)",
            (row["id"], row["id"], row["title"], row["dek"], row["abstract"], row["content_text"]),
        )


def refresh_claim_fts(db: sqlite3.Connection, claim_id: int) -> None:
    row = db.execute("SELECT * FROM reporting_claim WHERE id=?", (claim_id,)).fetchone()
    db.execute("DELETE FROM claim_fts WHERE rowid=?", (claim_id,))
    if row:
        db.execute(
            "INSERT INTO claim_fts(rowid,claim_id,claim_text,subject_text,object_text,attribution) VALUES(?,?,?,?,?,?)",
            (row["id"], row["id"], row["claim_text"], row["subject_text"], row["object_text"], row["attribution"]),
        )
