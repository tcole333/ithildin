#!/usr/bin/env python3
"""Deterministic entity resolution pipeline.

Scans the entities table for duplicate candidates using normalized name
matching (suffix stripping, case folding, fuzzy matching via rapidfuzz).
Cross-references against registry.db officers for person-entity links.

Usage:
    uv run python tools/entity_resolution.py scan [--limit N] [--threshold N]
    uv run python tools/entity_resolution.py scan-registry [--limit N] [--threshold N]
    uv run python tools/entity_resolution.py review <candidate_id>
    uv run python tools/entity_resolution.py merge <entity_id_keep> <entity_id_drop> [--dry-run]
    uv run python tools/entity_resolution.py stats
"""

import argparse
import re
import sqlite3
import sys
from collections import namedtuple
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

DB_PATH = Path(__file__).parent.parent / "investigation.db"
REGISTRY_DB_PATH = Path(__file__).parent.parent / "registry.db"

# Suffixes to strip for normalization (order matters — longest first)
ENTITY_SUFFIXES = [
    "limited liability company",
    "limited liability",
    "limited partnership",
    "incorporated",
    "corporation",
    "limited",
    "company",
    "l.l.c.",
    "l.l.p.",
    "l.p.",
    "llc",
    "inc",
    "ltd",
    "lp",
    "corp",
    "co",
    "plc",
    "sa",
    "ag",
    "gmbh",
    "nv",
    "bv",
]

# Person name prefixes/suffixes to normalize
PERSON_SUFFIXES = ["jr", "sr", "ii", "iii", "iv", "esq", "phd", "md"]
PERSON_PREFIXES = ["mr", "mrs", "ms", "dr", "prof"]


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def normalize_entity_name(name):
    """Normalize an entity name for comparison.

    Strips suffixes (LLC, Inc, Corp, etc.), punctuation, extra whitespace,
    and folds to lowercase.
    """
    if not name:
        return ""
    s = name.strip().lower()
    # Remove punctuation except hyphens and apostrophes
    s = re.sub(r"[.,;:!?\"()\[\]{}]", " ", s)
    # Strip entity suffixes (longest first to avoid partial matches)
    for suffix in ENTITY_SUFFIXES:
        pattern = r"\b" + re.escape(suffix) + r"\.?\s*$"
        s = re.sub(pattern, "", s).strip()
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_person_name(name):
    """Normalize a person name for comparison.

    Strips titles, suffixes, punctuation, and folds to lowercase.
    """
    if not name:
        return ""
    s = name.strip().lower()
    # Remove punctuation
    s = re.sub(r"[.,;:!?\"()\[\]{}]", " ", s)
    # Strip person prefixes
    for prefix in PERSON_PREFIXES:
        s = re.sub(r"^" + re.escape(prefix) + r"\.?\s+", "", s).strip()
    # Strip person suffixes
    for suffix in PERSON_SUFFIXES:
        s = re.sub(r"\s+" + re.escape(suffix) + r"\.?\s*$", "", s).strip()
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def classify_confidence(score):
    """Classify a fuzzy match score into confidence tiers."""
    if score >= 97:
        return "confirmed"
    elif score >= 90:
        return "probable"
    elif score >= 82:
        return "possible"
    return None


# ── Write-path resolve-or-create ─────────────────────────────
#
# The single guard that keeps duplicate entity rows from accruing. Ingestion
# tools call resolve_or_create_entity() instead of a bare INSERT so a new name
# is matched against the existing registry before a row is created.

EntityResolution = namedtuple("EntityResolution", ["entity_id", "action", "matched_name", "score"])

# Auto-match confidence. 97 == the "confirmed" tier in classify_confidence();
# Sr/II father-son pairs score ~91 on token_sort_ratio and therefore stay distinct.
DEFAULT_MATCH_THRESHOLD = 97

# Entity types denoting a natural person (everything else is an organization).
_PERSON_ENTITY_TYPES = {"person"}

# Below this normalized length fuzzy matching is too noisy to trust (e.g. "x", "j").
_MIN_FUZZY_LEN = 2


def _entity_type_family(entity_type):
    """Coarse family for compatibility checks. None == unknown/unconstrained."""
    if not entity_type or entity_type == "unknown":
        return None
    return "person" if entity_type in _PERSON_ENTITY_TYPES else "org"


def _jurisdiction_compatible(a, b):
    """Two jurisdictions are compatible if either is unknown or they're equal."""
    if not a or not b:
        return True
    return a.strip().lower() == b.strip().lower()


def _pick_jurisdiction_match(rows, jurisdiction):
    """Choose the best same-name row given the caller's jurisdiction, or None.

    Prefers an equal jurisdiction, then a NULL-jurisdiction stub to enrich. If the
    only same-name rows carry a *different* non-null jurisdiction, returns None so
    the caller inserts a distinct row (distinct jurisdiction => possibly distinct
    entity, matching the UNIQUE(name, jurisdiction) intent). When the caller gives
    no jurisdiction, prefers a jurisdiction-bearing (richer) row.
    """
    if not rows:
        return None
    if jurisdiction:
        jl = jurisdiction.strip().lower()
        for r in rows:
            if r["jurisdiction"] and r["jurisdiction"].strip().lower() == jl:
                return r
        for r in rows:
            if not r["jurisdiction"]:
                return r
        return None
    return sorted(rows, key=lambda r: (r["jurisdiction"] is None, r["id"]))[0]


def _backfill_entity_scalars(db, row, *, entity_type=None, jurisdiction=None, ein=None, address=None):
    """Fill NULL/empty scalar columns on an existing entity from new data.

    Never overwrites an existing non-empty value. entity_type is only upgraded when
    the stored type is unknown/NULL, so a richer ingest can promote a stub without
    clobbering a deliberate classification. Does not commit.
    """
    updates = {}
    for col, val in (("jurisdiction", jurisdiction), ("ein", ein), ("address", address)):
        if val and not row[col]:
            updates[col] = val
    if entity_type and entity_type != "unknown" and (not row["entity_type"] or row["entity_type"] == "unknown"):
        updates["entity_type"] = entity_type
    if not updates:
        return
    sets = ", ".join(f"{c} = ?" for c in updates)
    db.execute(f"UPDATE entities SET {sets} WHERE id = ?", (*updates.values(), row["id"]))


def _record_variant_alias(db, *, canonical, alias, entity_id, entity_type):
    """Record a fuzzy-discovered spelling as an alias so the exact cache resolves it next time."""
    if not alias or not canonical or alias.strip().lower() == canonical.strip().lower():
        return
    alias_type = "person_variant" if _entity_type_family(entity_type) == "person" else "entity_variant"
    db.execute(
        "INSERT OR IGNORE INTO name_aliases (canonical_name, alias, alias_type, entity_id, created_by) "
        "VALUES (?, ?, ?, ?, 'resolve_or_create')",
        (canonical, alias.strip(), alias_type, entity_id),
    )
    # Best-effort: drop the in-process alias cache so name_resolver picks this up.
    try:
        from tools.name_resolver import invalidate_cache
    except ImportError:
        try:
            from name_resolver import invalidate_cache
        except ImportError:
            invalidate_cache = None
    if invalidate_cache:
        invalidate_cache()


def _best_fuzzy_match(db, norm, entity_type, jurisdiction, threshold):
    """Return (row, score) for the best guard-passing fuzzy match, or None."""
    from rapidfuzz import fuzz, process

    rows = db.execute(
        "SELECT id, name, entity_type, jurisdiction, ein, address FROM entities"
    ).fetchall()
    candidates = []
    norm_names = []
    for r in rows:
        cn = normalize_entity_name(r["name"])
        if not cn:
            continue
        candidates.append(r)
        norm_names.append(cn)
    if not norm_names:
        return None
    fam = _entity_type_family(entity_type)
    # Pull several so a guard-failing top hit doesn't mask a valid lower one.
    for _cand_norm, score, idx in process.extract(
        norm, norm_names, scorer=fuzz.token_sort_ratio, limit=5, score_cutoff=threshold
    ):
        row = candidates[idx]
        if not _jurisdiction_compatible(jurisdiction, row["jurisdiction"]):
            continue
        cand_fam = _entity_type_family(row["entity_type"])
        if fam and cand_fam and fam != cand_fam:
            continue
        return (row, score)
    return None


def _insert_entity(db, name, *, entity_type, jurisdiction, ein, address, status, source, notes, agent_run_id):
    """INSERT a new entity row, tolerating a UNIQUE(name, jurisdiction) race."""
    cols = ["name", "entity_type"]
    vals = [name, entity_type or "unknown"]
    for col, val in (
        ("jurisdiction", jurisdiction), ("ein", ein), ("address", address),
        ("status", status), ("source", source), ("notes", notes), ("agent_run_id", agent_run_id),
    ):
        if val is not None:
            cols.append(col)
            vals.append(val)
    collist = ", ".join(cols)
    placeholders = ", ".join("?" for _ in vals)
    try:
        cur = db.execute(f"INSERT INTO entities ({collist}) VALUES ({placeholders})", vals)
        return EntityResolution(cur.lastrowid, "created", name, None)
    except sqlite3.IntegrityError:
        row = db.execute(
            "SELECT id, name FROM entities WHERE name = ? AND COALESCE(jurisdiction, '') = COALESCE(?, '')",
            (name, jurisdiction),
        ).fetchone()
        if row:
            return EntityResolution(row["id"], "exact", row["name"], 100.0)
        raise


def resolve_or_create_entity(
    db,
    name,
    *,
    entity_type="unknown",
    jurisdiction=None,
    ein=None,
    address=None,
    status=None,
    source=None,
    notes=None,
    agent_run_id=None,
    threshold=DEFAULT_MATCH_THRESHOLD,
    record_alias=True,
    backfill=True,
    use_aliases=True,
):
    """Resolve `name` to an existing entity, or insert a new one.

    The write-path guard against duplicate entity rows. Resolution order:
      1. alias  — name_aliases maps this name to a known entity_id (use_aliases)
      2. exact  — an existing row has this exact name (jurisdiction-compatible)
      3. fuzzy  — an existing row's normalized name matches at >= threshold
                  (token_sort_ratio), subject to jurisdiction + person/org guards
      4. create — otherwise INSERT a new row

    On an exact/alias/fuzzy match, NULL scalar columns are backfilled from the
    supplied data (never overwriting) when backfill=True. On a fuzzy match an
    entity_variant/person_variant alias is recorded (record_alias=True) so the
    exact path resolves this spelling next time.

    To force a distinct row (e.g. `add-entity --force-new`), pass threshold > 100
    (skip fuzzy) and use_aliases=False (ignore recorded aliases). The exact
    UNIQUE(name, jurisdiction) constraint is always honored, so this never yields
    a true duplicate of an identical (name, jurisdiction).

    Does NOT commit — the caller owns the transaction. Returns an EntityResolution
    (entity_id, action, matched_name, score); entity_id is None for a blank name.
    """
    if not name or not name.strip():
        return EntityResolution(None, None, None, None)
    name = name.strip()

    # 1. Alias table (curated or previously auto-recorded variants).
    if use_aliases:
        arow = db.execute(
            "SELECT canonical_name, entity_id FROM name_aliases "
            "WHERE lower(alias) = lower(?) AND entity_id IS NOT NULL LIMIT 1",
            (name,),
        ).fetchone()
        if arow and arow["entity_id"]:
            if backfill:
                erow = db.execute(
                    "SELECT id, name, entity_type, jurisdiction, ein, address FROM entities WHERE id = ?",
                    (arow["entity_id"],),
                ).fetchone()
                if erow:
                    _backfill_entity_scalars(db, erow, entity_type=entity_type,
                                             jurisdiction=jurisdiction, ein=ein, address=address)
            return EntityResolution(arow["entity_id"], "alias", arow["canonical_name"], 100.0)

    # 2. Exact name match (jurisdiction-aware).
    same_name = db.execute(
        "SELECT id, name, entity_type, jurisdiction, ein, address FROM entities WHERE name = ?",
        (name,),
    ).fetchall()
    match = _pick_jurisdiction_match(same_name, jurisdiction)
    if match:
        if backfill:
            _backfill_entity_scalars(db, match, entity_type=entity_type,
                                     jurisdiction=jurisdiction, ein=ein, address=address)
        return EntityResolution(match["id"], "exact", match["name"], 100.0)

    # 3. Fuzzy normalized match.
    norm = normalize_entity_name(name)
    if threshold <= 100 and len(norm) >= _MIN_FUZZY_LEN:
        fuzzy = _best_fuzzy_match(db, norm, entity_type, jurisdiction, threshold)
        if fuzzy:
            row, score = fuzzy
            if backfill:
                _backfill_entity_scalars(db, row, entity_type=entity_type,
                                         jurisdiction=jurisdiction, ein=ein, address=address)
            if record_alias:
                _record_variant_alias(db, canonical=row["name"], alias=name,
                                      entity_id=row["id"], entity_type=row["entity_type"])
            return EntityResolution(row["id"], "fuzzy", row["name"], round(float(score), 1))

    # 4. Create.
    return _insert_entity(db, name, entity_type=entity_type, jurisdiction=jurisdiction,
                          ein=ein, address=address, status=status, source=source,
                          notes=notes, agent_run_id=agent_run_id)


def cmd_scan(args):
    """Scan entities table for duplicate candidates."""
    from rapidfuzz import fuzz

    db = get_db()
    threshold = args.threshold

    # Load all entities
    rows = db.execute(
        "SELECT id, name, entity_type, jurisdiction, status FROM entities ORDER BY name"
    ).fetchall()
    entities = [dict(r) for r in rows]

    if not entities:
        print("No entities found in investigation.db")
        return

    # Build normalized name map
    norm_map = {}
    for e in entities:
        norm = normalize_entity_name(e["name"])
        norm_map.setdefault(norm, []).append(e)

    candidates = []

    # Phase 1: Exact normalized matches (different raw names)
    for norm, group in norm_map.items():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    candidates.append({
                        "entity_a": group[i],
                        "entity_b": group[j],
                        "score": 100,
                        "confidence": "confirmed",
                        "match_type": "exact_normalized",
                    })

    # Phase 2: Fuzzy matching across normalized names
    norms = list(norm_map.keys())
    for i in range(len(norms)):
        for j in range(i + 1, len(norms)):
            if norms[i] == norms[j]:
                continue
            score = fuzz.token_sort_ratio(norms[i], norms[j])
            conf = classify_confidence(score)
            if conf:
                for ea in norm_map[norms[i]]:
                    for eb in norm_map[norms[j]]:
                        candidates.append({
                            "entity_a": ea,
                            "entity_b": eb,
                            "score": score,
                            "confidence": conf,
                            "match_type": "fuzzy",
                        })

    # Sort by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Apply limit
    if args.limit:
        candidates = candidates[: args.limit]

    # Load existing aliases for context
    alias_count = db.execute("SELECT COUNT(*) FROM name_aliases").fetchone()[0]

    results = {
        "total_entities": len(entities),
        "existing_aliases": alias_count,
        "candidates_found": len(candidates),
        "candidates": [
            {
                "entity_a_id": c["entity_a"]["id"],
                "entity_a_name": c["entity_a"]["name"],
                "entity_a_type": c["entity_a"]["entity_type"],
                "entity_a_jurisdiction": c["entity_a"]["jurisdiction"],
                "entity_b_id": c["entity_b"]["id"],
                "entity_b_name": c["entity_b"]["name"],
                "entity_b_type": c["entity_b"]["entity_type"],
                "entity_b_jurisdiction": c["entity_b"]["jurisdiction"],
                "score": c["score"],
                "confidence": c["confidence"],
                "match_type": c["match_type"],
            }
            for c in candidates
        ],
    }

    if write_output(results, args, summary=f"entity scan: {len(candidates)} candidates"):
        return

    if getattr(args, "json_out", False):
        import json
        print(json.dumps(results, indent=2))
        return

    print(f"\nEntity Resolution Scan")
    print(f"{'='*70}")
    print(f"Total entities: {len(entities)}")
    print(f"Existing aliases: {alias_count}")
    print(f"Duplicate candidates: {len(candidates)}")
    print(f"Threshold: {threshold}")
    print()

    for c in candidates:
        ea, eb = c["entity_a"], c["entity_b"]
        print(f"  [{c['confidence']:>9s}] {c['score']:3.0f}%  {c['match_type']}")
        print(f"    A: #{ea['id']} {ea['name']} ({ea['entity_type']}, {ea['jurisdiction']})")
        print(f"    B: #{eb['id']} {eb['name']} ({eb['entity_type']}, {eb['jurisdiction']})")
        print()


def cmd_scan_registry(args):
    """Cross-match entities against registry.db officers."""
    from rapidfuzz import fuzz

    db = get_db()
    threshold = args.threshold

    if not REGISTRY_DB_PATH.exists():
        print(f"Registry DB not found: {REGISTRY_DB_PATH}")
        return

    reg_db = sqlite3.connect(str(REGISTRY_DB_PATH))
    reg_db.row_factory = sqlite3.Row

    # Load entity_roles persons from investigation.db
    persons = db.execute(
        "SELECT DISTINCT person_name FROM entity_roles"
    ).fetchall()
    person_names = {normalize_person_name(r["person_name"]): r["person_name"] for r in persons}

    # Load registry officers
    officers = reg_db.execute(
        "SELECT DISTINCT officer_name, title FROM registry_officers LIMIT 50000"
    ).fetchall()
    officer_names = {}
    for o in officers:
        norm = normalize_person_name(o["officer_name"])
        if norm:
            officer_names.setdefault(norm, []).append(dict(o))

    candidates = []

    # Cross-match: find investigation persons who appear in registry
    for norm_person, raw_person in person_names.items():
        if not norm_person:
            continue
        # Exact match
        if norm_person in officer_names:
            for off in officer_names[norm_person]:
                candidates.append({
                    "person": raw_person,
                    "officer": off["officer_name"],
                    "title": off["title"],
                    "score": 100,
                    "confidence": "confirmed",
                    "match_type": "exact_normalized",
                })
            continue
        # Fuzzy match (only if not too many officers)
        for norm_off, off_list in officer_names.items():
            score = fuzz.token_sort_ratio(norm_person, norm_off)
            if score >= threshold:
                for off in off_list:
                    candidates.append({
                        "person": raw_person,
                        "officer": off["officer_name"],
                        "title": off["title"],
                        "score": score,
                        "confidence": classify_confidence(score),
                        "match_type": "fuzzy",
                    })

    reg_db.close()

    candidates.sort(key=lambda c: c["score"], reverse=True)
    if args.limit:
        candidates = candidates[: args.limit]

    results = {
        "investigation_persons": len(person_names),
        "registry_officers": len(officer_names),
        "cross_matches": len(candidates),
        "candidates": candidates,
    }

    if write_output(results, args, summary=f"registry cross-match: {len(candidates)} matches"):
        return

    if getattr(args, "json_out", False):
        import json
        print(json.dumps(results, indent=2))
        return

    print(f"\nRegistry Cross-Match")
    print(f"{'='*70}")
    print(f"Investigation persons: {len(person_names)}")
    print(f"Registry officers (unique): {len(officer_names)}")
    print(f"Cross-matches: {len(candidates)}")
    print()

    for c in candidates:
        print(f"  [{c['confidence']:>9s}] {c['score']:3.0f}%  {c['match_type']}")
        print(f"    Investigation: {c['person']}")
        print(f"    Registry:      {c['officer']} ({c['title']})")
        print()


def cmd_review(args):
    """Show details for a specific entity pair merge candidate."""
    db = get_db()
    entity_id = args.entity_id

    row = db.execute(
        "SELECT * FROM entities WHERE id = ?", (entity_id,)
    ).fetchone()
    if not row:
        print(f"Entity #{entity_id} not found")
        return

    entity = dict(row)

    # Get roles
    roles = [dict(r) for r in db.execute(
        "SELECT * FROM entity_roles WHERE entity_id = ?", (entity_id,)
    ).fetchall()]

    # Get addresses
    addresses = [dict(r) for r in db.execute(
        "SELECT * FROM entity_addresses WHERE entity_id = ?", (entity_id,)
    ).fetchall()]

    # Get relations
    relations = [dict(r) for r in db.execute(
        """SELECT * FROM entity_relations
           WHERE entity_a_id = ? OR entity_b_id = ?""",
        (entity_id, entity_id),
    ).fetchall()]

    # Get existing aliases
    aliases = [dict(r) for r in db.execute(
        "SELECT * FROM name_aliases WHERE entity_id = ?", (entity_id,)
    ).fetchall()]

    # Get findings referencing this entity
    finding_count = db.execute(
        "SELECT COUNT(*) FROM findings WHERE target_name LIKE ?",
        (f"%{entity['name']}%",),
    ).fetchone()[0]

    # Get connections referencing this entity
    connection_count = db.execute(
        """SELECT COUNT(*) FROM connections
           WHERE person_a LIKE ? OR person_b LIKE ?""",
        (f"%{entity['name']}%", f"%{entity['name']}%"),
    ).fetchone()[0]

    result = {
        "entity": entity,
        "roles": roles,
        "addresses": addresses,
        "relations": relations,
        "aliases": aliases,
        "finding_references": finding_count,
        "connection_references": connection_count,
    }

    if write_output(result, args, summary=f"entity #{entity_id} review"):
        return

    if getattr(args, "json_out", False):
        import json
        print(json.dumps(result, indent=2, default=str))
        return

    print(f"\nEntity #{entity_id}: {entity['name']}")
    print(f"{'='*70}")
    print(f"  Type: {entity['entity_type']}  |  Jurisdiction: {entity['jurisdiction']}")
    print(f"  Status: {entity['status']}  |  EIN: {entity.get('ein', 'N/A')}")
    print(f"  Source: {entity.get('source', 'N/A')}")

    if roles:
        print(f"\n  Roles ({len(roles)}):")
        for r in roles:
            print(f"    - {r['person_name']}: {r['role']} ({r.get('date_start', '?')} - {r.get('date_end', 'present')})")

    if addresses:
        print(f"\n  Addresses ({len(addresses)}):")
        for a in addresses:
            print(f"    - [{a['address_type']}] {a['address']}")

    if relations:
        print(f"\n  Relations ({len(relations)}):")
        for rel in relations:
            print(f"    - {rel['relation_type']}: entity #{rel['entity_a_id']} <-> #{rel['entity_b_id']}")

    if aliases:
        print(f"\n  Aliases ({len(aliases)}):")
        for a in aliases:
            print(f"    - {a['alias']} -> {a['canonical_name']} ({a['alias_type']})")

    print(f"\n  Referenced in: {finding_count} findings, {connection_count} connections")


def _merge_text(keep_notes, drop_notes, drop_id):
    """Return keep_notes with drop_notes appended (tagged), unless already contained."""
    keep_notes = (keep_notes or "").strip()
    drop_notes = (drop_notes or "").strip()
    if not drop_notes or drop_notes in keep_notes:
        return keep_notes
    tag = f"[merged from #{drop_id}] {drop_notes}"
    return f"{keep_notes}\n{tag}".strip()


def _merge_sources(keep_source, drop_source):
    """Union comma-separated source lists, preserving order, de-duplicated."""
    seen, out = set(), []
    for chunk in (keep_source or ""), (drop_source or ""):
        for s in (p.strip() for p in chunk.split(",")):
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
    return ",".join(out)


def cmd_merge(args):
    """Merge two entities — keep one, alias the other."""
    db = get_db()

    keep = db.execute("SELECT * FROM entities WHERE id = ?", (args.keep_id,)).fetchone()
    drop = db.execute("SELECT * FROM entities WHERE id = ?", (args.drop_id,)).fetchone()

    if not keep:
        print(f"Entity #{args.keep_id} (keep) not found")
        return
    if not drop:
        print(f"Entity #{args.drop_id} (drop) not found")
        return

    keep, drop = dict(keep), dict(drop)

    print(f"\nMerge Plan:")
    print(f"  KEEP: #{keep['id']} {keep['name']} ({keep['entity_type']}, {keep['jurisdiction']})")
    print(f"  DROP: #{drop['id']} {drop['name']} ({drop['entity_type']}, {drop['jurisdiction']})")

    if args.dry_run:
        print("\n  [DRY RUN] Would perform:")
    else:
        print("\n  Executing:")

    actions = []

    # 1. Create name alias
    actions.append(f"  - Add alias: '{drop['name']}' -> '{keep['name']}'")

    # 2. Move roles from drop to keep
    drop_roles = db.execute(
        "SELECT COUNT(*) FROM entity_roles WHERE entity_id = ?", (drop["id"],)
    ).fetchone()[0]
    if drop_roles:
        actions.append(f"  - Move {drop_roles} roles from #{drop['id']} to #{keep['id']}")

    # 3. Move addresses
    drop_addrs = db.execute(
        "SELECT COUNT(*) FROM entity_addresses WHERE entity_id = ?", (drop["id"],)
    ).fetchone()[0]
    if drop_addrs:
        actions.append(f"  - Move {drop_addrs} addresses from #{drop['id']} to #{keep['id']}")

    # 4. Move relations
    drop_rels_a = db.execute(
        "SELECT COUNT(*) FROM entity_relations WHERE entity_a_id = ?", (drop["id"],)
    ).fetchone()[0]
    drop_rels_b = db.execute(
        "SELECT COUNT(*) FROM entity_relations WHERE entity_b_id = ?", (drop["id"],)
    ).fetchone()[0]
    if drop_rels_a + drop_rels_b:
        actions.append(f"  - Reassign {drop_rels_a + drop_rels_b} relations")

    # 5. Repoint other FK references (name_aliases, institutional_pillars)
    drop_aliases = db.execute(
        "SELECT COUNT(*) FROM name_aliases WHERE entity_id = ?", (drop["id"],)
    ).fetchone()[0]
    if drop_aliases:
        actions.append(f"  - Repoint {drop_aliases} name aliases (drop self-aliases)")
    drop_pillars = db.execute(
        "SELECT COUNT(*) FROM institutional_pillars WHERE entity_id = ?", (drop["id"],)
    ).fetchone()[0]
    if drop_pillars:
        actions.append(f"  - Repoint {drop_pillars} institutional pillars")

    # Preserve the dropped entity's notes/source into the kept entity — a merge
    # must not silently discard intel. Union sources; append notes if not already
    # contained. Also inherit a more-specific entity_type if keep is 'unknown'.
    merged_notes = _merge_text(keep.get("notes"), drop.get("notes"), drop["id"])
    merged_source = _merge_sources(keep.get("source"), drop.get("source"))
    inherit_type = (
        drop["entity_type"]
        if keep["entity_type"] in (None, "", "unknown")
        and drop["entity_type"] not in (None, "", "unknown")
        else None
    )
    if merged_notes != (keep.get("notes") or ""):
        actions.append(f"  - Merge notes from #{drop['id']} into #{keep['id']}")
    if merged_source != (keep.get("source") or ""):
        actions.append(f"  - Union sources -> '{merged_source}'")
    if inherit_type:
        actions.append(f"  - Adopt entity_type '{inherit_type}' from #{drop['id']}")

    for a in actions:
        print(a)

    if args.dry_run:
        print("\n  [DRY RUN] No changes made.")
        return

    # Execute merge
    try:
        # Add alias
        db.execute(
            """INSERT OR IGNORE INTO name_aliases
               (canonical_name, alias, alias_type, entity_id, created_by)
               VALUES (?, ?, 'entity_variant', ?, 'entity_resolution')""",
            (keep["name"], drop["name"], keep["id"]),
        )

        # Move roles (ignore duplicates)
        db.execute(
            """UPDATE OR IGNORE entity_roles SET entity_id = ?
               WHERE entity_id = ?""",
            (keep["id"], drop["id"]),
        )
        # Delete any that couldn't move due to unique constraint
        db.execute("DELETE FROM entity_roles WHERE entity_id = ?", (drop["id"],))

        # Move addresses (ignore duplicates)
        db.execute(
            """UPDATE OR IGNORE entity_addresses SET entity_id = ?
               WHERE entity_id = ?""",
            (keep["id"], drop["id"]),
        )
        db.execute("DELETE FROM entity_addresses WHERE entity_id = ?", (drop["id"],))

        # Move relations
        db.execute(
            """UPDATE OR IGNORE entity_relations SET entity_a_id = ?
               WHERE entity_a_id = ?""",
            (keep["id"], drop["id"]),
        )
        db.execute(
            """UPDATE OR IGNORE entity_relations SET entity_b_id = ?
               WHERE entity_b_id = ?""",
            (keep["id"], drop["id"]),
        )
        # Clean up any self-referencing relations
        db.execute(
            "DELETE FROM entity_relations WHERE entity_a_id = entity_b_id"
        )
        # Delete orphaned relations
        db.execute(
            "DELETE FROM entity_relations WHERE entity_a_id = ? OR entity_b_id = ?",
            (drop["id"], drop["id"]),
        )

        # Repoint name_aliases that referenced the dropped entity to the kept one,
        # then drop any alias that now points at its own canonical name (self-alias).
        # Without this the FK name_aliases.entity_id -> entities.id blocks the delete.
        db.execute(
            """UPDATE OR IGNORE name_aliases SET entity_id = ?, canonical_name = ?
               WHERE entity_id = ?""",
            (keep["id"], keep["name"], drop["id"]),
        )
        db.execute(
            """DELETE FROM name_aliases
               WHERE entity_id = ? OR alias = canonical_name""",
            (drop["id"],),
        )

        # Repoint any institutional_pillars FK references
        db.execute(
            "UPDATE OR IGNORE institutional_pillars SET entity_id = ? WHERE entity_id = ?",
            (keep["id"], drop["id"]),
        )
        db.execute(
            "DELETE FROM institutional_pillars WHERE entity_id = ?", (drop["id"],)
        )

        # Preserve notes/source/type from the dropped entity into the kept one
        db.execute(
            "UPDATE entities SET notes = ?, source = ?, entity_type = ? WHERE id = ?",
            (merged_notes, merged_source, inherit_type or keep["entity_type"], keep["id"]),
        )

        # Delete the dropped entity
        db.execute("DELETE FROM entities WHERE id = ?", (drop["id"],))

        db.commit()
        print(f"\n  Merge complete. Entity #{drop['id']} merged into #{keep['id']}.")

    except Exception as e:
        db.rollback()
        print(f"\n  ERROR: {e}")
        sys.exit(1)


def cmd_stats(args):
    """Show entity resolution metrics."""
    db = get_db()

    total_entities = db.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    total_aliases = db.execute("SELECT COUNT(*) FROM name_aliases").fetchone()[0]

    # Alias type breakdown
    alias_types = db.execute(
        "SELECT alias_type, COUNT(*) as cnt FROM name_aliases GROUP BY alias_type"
    ).fetchall()

    # Entity type breakdown
    entity_types = db.execute(
        "SELECT entity_type, COUNT(*) as cnt FROM entities GROUP BY entity_type ORDER BY cnt DESC"
    ).fetchall()

    # Jurisdiction breakdown
    jurisdictions = db.execute(
        "SELECT jurisdiction, COUNT(*) as cnt FROM entities GROUP BY jurisdiction ORDER BY cnt DESC LIMIT 15"
    ).fetchall()

    # Entities with roles
    with_roles = db.execute(
        "SELECT COUNT(DISTINCT entity_id) FROM entity_roles"
    ).fetchone()[0]

    # Entities with addresses
    with_addresses = db.execute(
        "SELECT COUNT(DISTINCT entity_id) FROM entity_addresses"
    ).fetchone()[0]

    results = {
        "total_entities": total_entities,
        "total_aliases": total_aliases,
        "alias_types": {r["alias_type"]: r["cnt"] for r in alias_types},
        "entity_types": {r["entity_type"]: r["cnt"] for r in entity_types},
        "top_jurisdictions": {r["jurisdiction"]: r["cnt"] for r in jurisdictions},
        "entities_with_roles": with_roles,
        "entities_with_addresses": with_addresses,
    }

    if write_output(results, args, summary="entity resolution stats"):
        return

    if getattr(args, "json_out", False):
        import json
        print(json.dumps(results, indent=2))
        return

    print(f"\nEntity Resolution Stats")
    print(f"{'='*50}")
    print(f"  Total entities:          {total_entities}")
    print(f"  Total name aliases:      {total_aliases}")
    print(f"  Entities with roles:     {with_roles}")
    print(f"  Entities with addresses: {with_addresses}")

    if alias_types:
        print(f"\n  Alias Types:")
        for r in alias_types:
            print(f"    {r['alias_type']:20s} {r['cnt']:5d}")

    print(f"\n  Entity Types:")
    for r in entity_types:
        print(f"    {r['entity_type']:20s} {r['cnt']:5d}")

    print(f"\n  Top Jurisdictions:")
    for r in jurisdictions:
        j = r["jurisdiction"] or "(none)"
        print(f"    {j:20s} {r['cnt']:5d}")


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic entity resolution pipeline"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p = sub.add_parser("scan", help="Scan entities for duplicate candidates")
    p.add_argument("--limit", type=int, default=50, help="Max candidates to show")
    p.add_argument("--threshold", type=int, default=82, help="Fuzzy match threshold (0-100)")
    add_output_args(p)

    # scan-registry
    p = sub.add_parser("scan-registry", help="Cross-match entities against registry officers")
    p.add_argument("--limit", type=int, default=50, help="Max candidates to show")
    p.add_argument("--threshold", type=int, default=82, help="Fuzzy match threshold (0-100)")
    add_output_args(p)

    # review
    p = sub.add_parser("review", help="Review a specific entity with all linked data")
    p.add_argument("entity_id", type=int, help="Entity ID to review")
    add_output_args(p)

    # merge
    p = sub.add_parser("merge", help="Merge two entities (keep one, alias the other)")
    p.add_argument("keep_id", type=int, help="Entity ID to keep")
    p.add_argument("drop_id", type=int, help="Entity ID to merge in and delete")
    p.add_argument("--dry-run", action="store_true", help="Show plan without executing")

    # stats
    p = sub.add_parser("stats", help="Entity resolution metrics")
    add_output_args(p)

    args = parser.parse_args()

    handlers = {
        "scan": cmd_scan,
        "scan-registry": cmd_scan_registry,
        "review": cmd_review,
        "merge": cmd_merge,
        "stats": cmd_stats,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
