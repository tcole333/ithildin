#!/usr/bin/env python3
"""Lead deduplication for investigation.db.

Groups open leads into candidate duplicate clusters, infers missing target_names,
and applies subagent dedup decisions (dead-end duplicates, link via lead_relations).

Usage:
    python tools/lead_dedup.py fill-targets [--dry-run] [--batch-size 200]
    uv run python tools/lead_dedup.py scan [--profile-id NAME] --output FILE
    uv run python tools/lead_dedup.py show-group <group_hash_or_lead_id>
    uv run python tools/lead_dedup.py export-batch --batch-size 20 --offset 0 --output FILE
    uv run python tools/lead_dedup.py apply --batch-file BATCH --decisions-file FILE [--dry-run]
    uv run python tools/lead_dedup.py verify [--sample-size 15]
    uv run python tools/lead_dedup.py stats
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path

try:
    from tools.lead_tracker import (open_review_db, review_context, review_profile_id,
                                    review_lead_snapshot, validate_review_context, validate_review_lead)
    from tools.output_util import add_output_args, write_output
except ImportError:
    from lead_tracker import (open_review_db, review_context, review_profile_id,
                             review_lead_snapshot, validate_review_context, validate_review_lead)
    from output_util import add_output_args, write_output

DB_PATH = Path(os.environ.get("ITHILDIN_DB_PATH", Path(__file__).parent.parent / "investigation.db"))

# ---------------------------------------------------------------------------
# Shared utilities (subset of finding_dedup.py patterns)
# ---------------------------------------------------------------------------

_GENERIC_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "was", "were", "are",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall",
    "this", "that", "these", "those", "it", "its", "as", "not", "no",
    "cross", "ref", "officer", "search", "registry", "investigate",
    "entity", "find", "other", "roles", "check", "corporate", "all",
    "sources", "deep", "analyze", "trace", "review", "lead", "follow",
    "up", "new", "possible", "potential", "via", "also", "related",
}

_LEAD_STOP_WORDS = None


def _build_stop_words():
    global _LEAD_STOP_WORDS
    if _LEAD_STOP_WORDS is not None:
        return _LEAD_STOP_WORDS
    words = set(_GENERIC_STOP_WORDS)
    try:
        from tools.investigation_context import get_active_profile
        profile = get_active_profile()
        if profile.primary_subject:
            words |= set(profile.primary_subject.lower().split())
    except Exception:
        pass
    _LEAD_STOP_WORDS = words
    return words


def _tokens(text):
    """Extract meaningful tokens for similarity comparison."""
    stop = _build_stop_words()
    return {w for w in re.findall(r'\w+', text.lower())
            if w not in stop and len(w) > 2 and not w.isdigit()}


def jaccard(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def normalize_name(name):
    """Normalize a name for comparison: lowercase, strip punctuation, collapse whitespace."""
    if not name:
        return ""
    return re.sub(r'[^a-z0-9 ]', '', name.lower()).strip()


def group_hash(lead_ids):
    """Stable hash for a set of lead IDs."""
    key = ",".join(str(i) for i in sorted(lead_ids))
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db(*, write=False):
    return open_review_db(write=write, db_path=DB_PATH)


def _ensure_dedup_schema(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS lead_dedup_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_hash TEXT NOT NULL UNIQUE,
            lead_ids TEXT NOT NULL,
            decision TEXT NOT NULL,
            keeper_id INTEGER,
            dead_ended_ids TEXT,
            rationale TEXT,
            decided_by TEXT DEFAULT 'agent:dedup',
            decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , profile_id TEXT
            , decision_json TEXT
        )
    """)
    columns = {row[1] for row in db.execute("PRAGMA table_info(lead_dedup_log)")}
    for column in ("profile_id", "decision_json"):
        if column not in columns:
            db.execute(f"ALTER TABLE lead_dedup_log ADD COLUMN {column} TEXT")


def _has_log(db):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='lead_dedup_log'").fetchone())


def _scoped_log_rows(db, profile_id):
    """Legacy rows are attributable only when all recorded IDs belong to this profile."""
    if not _has_log(db):
        return []
    columns = {row[1] for row in db.execute("PRAGMA table_info(lead_dedup_log)")}
    legacy = """EXISTS (SELECT 1 FROM json_each(d.lead_ids)) AND NOT EXISTS (
        SELECT 1 FROM json_each(d.lead_ids) ids LEFT JOIN leads l ON l.id=ids.value
        WHERE l.profile_id IS NOT ?)"""
    if "profile_id" in columns:
        where, params = f"d.profile_id=? OR (d.profile_id IS NULL AND {legacy})", (profile_id, profile_id)
    else:
        where, params = legacy, (profile_id,)
    return db.execute(f"SELECT d.* FROM lead_dedup_log d WHERE {where} ORDER BY decided_at DESC, id DESC", params).fetchall()


# ---------------------------------------------------------------------------
# Union-Find for grouping
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[rx] = ry

    def groups(self):
        """Return dict of root -> [members]."""
        result = {}
        for x in self.parent:
            root = self.find(x)
            result.setdefault(root, []).append(x)
        return result


# ---------------------------------------------------------------------------
# fill-targets: Infer missing target_name from title patterns
# ---------------------------------------------------------------------------

# Patterns for extracting target names from auto-generated and manual lead titles
_TARGET_PATTERNS = [
    # Auto-leads patterns
    (r'^Cross-ref officer:\s*(.+?)\s*[-—]', None),
    (r'^Cross-ref registry:\s*(.+?)\s*[-—]', None),
    (r'^Cross-ref address:\s*(.+?)\s*[-—]', None),
    (r'^Serial director:\s*(.+?)\s*[-—]', None),
    (r'^Filing cluster:\s*\d+\s+entities\s+by\s+(.+?)\s+within', None),
    (r'^Jurisdiction cluster:\s*(.+?)\s+has\s+\d+', None),
    (r'^Coverage gap:\s*(.+?)\s*[-—]', None),
    # Common manual patterns — more specific patterns first
    (r'^(?:Deep-)?[Ii]nvestigate\s+(.+?)(?:\s*[-—])', None),
    (r'^(?:Deep-)?[Ii]nvestigate\s+(.+?)(?:\s+10-K|\s+role\b|\s+connection\b|\s+financial\b|\s+corporate\b)', None),
    (r'^(?:Deep |Deep-)?[Dd]ive:?\s+(.+?)(?:\s*[-—]|$)', None),
    (r'^(?:Deep-)?[Ii]nvestigate\s+(.+?)$', None),
    (r'^Trace\s+(.+?)\s+(?:corporate|financial|representation|entity|through|13F|connection)', None),
    (r'^Analyze\s+(.+?)\s+(?:10-K|proxy|13[DF]|SEC|financial|contract|corporate|filing)', None),
    (r'^SEC EDGAR (?:deep-dive|search|analysis) (?:on|for)\s+(.+?)(?:\s+CIK|\s*[-—]|$)', None),
    (r'^(?:Identify|Map|Review)\s+(.+?)\s+(?:role|who|network|full|in\s+|as\s+|codename)', None),
    (r'^(.+?)\s+(?:master contact|investment vehicle|foreknowledge|financial compensation)', None),
    (r'^(.+?)\s+(?:10-K|proxy|13[DF]|Form ADV|13F)\b', None),
    (r'^(.+?)\s+SEC (?:Non-Enforcement|Filing|enforcement)', None),
]


def _clean_target(candidate):
    """Clean up an extracted target name."""
    if not candidate:
        return None
    # Remove trailing possessives
    candidate = re.sub(r"'s$", "", candidate)
    # Remove CIK numbers and parenthetical registry IDs
    candidate = re.sub(r'\s*\(CIK[^)]*\)', '', candidate)
    candidate = re.sub(r'\s*\([A-Z]\d{8,}\)', '', candidate)
    # Remove leading "the "
    candidate = re.sub(r'^[Tt]he\s+', '', candidate)
    # Remove trailing prepositions/articles/source tags
    candidate = re.sub(r'\s+(?:in|to|for|from|and|the|a|an|SEC|EDGAR|via|what)$', '', candidate)
    # Remove leading "what/remaining/the"
    candidate = re.sub(r'^(?:what|remaining|the)\s+', '', candidate, flags=re.IGNORECASE)
    return candidate.strip()


def _extract_target_from_title(title):
    """Try to extract a target name from a lead title using regex patterns."""
    for pattern, _ in _TARGET_PATTERNS:
        m = re.match(pattern, title)
        if m:
            candidate = _clean_target(m.group(1).strip())
            if not candidate:
                continue
            # Skip if it looks like a generic description, not a name
            if len(candidate) < 3 or len(candidate) > 80:
                continue
            # Skip if all lowercase (likely a description, not a proper noun)
            if candidate == candidate.lower() and not re.search(r'[A-Z]', title[:50]):
                continue
            return candidate
    return None


def fill_targets(*, profile_id=None, dry_run=False):
    """Infer missing target names in one scoped, atomic operation."""
    db = get_db(write=not dry_run)
    try:
        db.execute("BEGIN" if dry_run else "BEGIN IMMEDIATE")
        profile_id = review_profile_id(db, profile_id)
        leads = db.execute(
            "SELECT id, title, description, source FROM leads WHERE profile_id=? "
            "AND status IN ('open','pending_triage') AND (target_name IS NULL OR target_name='') ORDER BY id",
            (profile_id,),
        ).fetchall()
        fills, unfilled = [], []
        for lead in leads:
            target = _extract_target_from_title(lead["title"])
            if not target:
                unfilled.append(dict(lead))
                continue
            fills.append({"lead_id": lead["id"], "target_name": target, "title": lead["title"]})
            if not dry_run:
                db.execute(
                    "UPDATE leads SET target_name=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND profile_id=? "
                    "AND status IN ('open','pending_triage') AND (target_name IS NULL OR target_name='')",
                    (target, lead["id"], profile_id),
                )
                db.execute("INSERT INTO lead_notes (lead_id, note) VALUES (?, ?)",
                           (lead["id"], f"target_name inferred from title: '{target}'"))
        db.commit() if not dry_run else db.rollback()
        return {"profile_id": profile_id, "dry_run": dry_run, "filled": len(fills),
                "fills": fills, "unfilled": unfilled}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# scan: Group open leads into candidate duplicate clusters
# ---------------------------------------------------------------------------

def _load_name_aliases(db):
    """Load name_aliases table into a lookup dict: alias -> canonical_name."""
    try:
        rows = db.execute("SELECT alias, canonical_name FROM name_aliases").fetchall()
        return {r["alias"]: r["canonical_name"] for r in rows}
    except Exception:
        return {}


def _resolve_target(target, aliases):
    """Resolve a target_name through aliases to its canonical form."""
    if not target:
        return target
    return aliases.get(target, target)


def _build_groups(db, profile_id=None, min_group_size=2):
    """Build candidate duplicate groups using 4 strategies + union-find."""
    profile_id = review_profile_id(db, profile_id)
    uf = UnionFind()

    # Load open leads
    conditions = ["status = 'open'", "target_name IS NOT NULL", "target_name != ''"]
    params = []
    if profile_id:
        conditions.append("profile_id = ?")
        params.append(profile_id)

    where = " AND ".join(conditions)
    leads = db.execute(f"""
        SELECT id, title, description, category, priority, source,
               target_name, depth_tier, profile_id
        FROM leads WHERE {where}
        ORDER BY id
    """, params).fetchall()

    leads_by_id = {lead["id"]: dict(lead) for lead in leads}
    aliases = _load_name_aliases(db)

    # Strategy 1: Exact target_name match (after alias resolution)
    by_target = {}
    for lead in leads:
        resolved = _resolve_target(lead["target_name"], aliases)
        normalized = normalize_name(resolved)
        if normalized:
            by_target.setdefault(normalized, []).append(lead["id"])

    s1_pairs = 0
    for norm_target, ids in by_target.items():
        if len(ids) >= 2:
            for i in range(1, len(ids)):
                uf.union(ids[0], ids[i])
                s1_pairs += 1

    # Strategy 2: Normalized name variants (prefix overlap)
    sorted_targets = sorted(by_target.keys())
    s2_pairs = 0
    for i, t1 in enumerate(sorted_targets):
        if len(t1) < 6:
            continue
        ids1 = by_target[t1]
        for t2 in sorted_targets[i + 1:]:
            if len(t2) < 6:
                continue
            # Check prefix overlap (one name is prefix of another)
            if t1.startswith(t2) or t2.startswith(t1):
                ids2 = by_target[t2]
                uf.union(ids1[0], ids2[0])
                s2_pairs += 1

    # Strategy 3: Title Jaccard similarity (within same category)
    by_category = {}
    for lead in leads:
        cat = lead["category"] or "unknown"
        by_category.setdefault(cat, []).append(lead)

    s3_pairs = 0
    for cat, cat_leads in by_category.items():
        # Only check leads that share a target group already or have similar titles
        # For efficiency, limit pairwise comparison to leads within same target group
        for norm_target, ids in by_target.items():
            if len(ids) < 2:
                continue
            cat_ids_in_group = [lid for lid in ids if lid in leads_by_id
                                and (leads_by_id[lid].get("category") or "unknown") == cat]
            if len(cat_ids_in_group) < 2:
                continue
            for i, id_a in enumerate(cat_ids_in_group):
                t_a = _tokens(leads_by_id[id_a]["title"])
                for id_b in cat_ids_in_group[i + 1:]:
                    t_b = _tokens(leads_by_id[id_b]["title"])
                    sim = jaccard(t_a, t_b)
                    if sim >= 0.5:
                        uf.union(id_a, id_b)
                        s3_pairs += 1

    # Build groups from union-find
    raw_groups = uf.groups()
    groups = []
    has_log = _has_log(db)
    for root, members in raw_groups.items():
        if len(members) < min_group_size:
            continue
        member_ids = sorted(members)
        ghash = group_hash(member_ids)

        # Check if already processed
        existing = has_log and db.execute(
            "SELECT id FROM lead_dedup_log WHERE group_hash = ?", (ghash,)
        ).fetchone()
        if existing:
            continue

        # Get target names in group
        targets = set()
        for lid in member_ids:
            if lid in leads_by_id:
                targets.add(leads_by_id[lid].get("target_name", ""))

        groups.append({
            "group_hash": ghash,
            "lead_ids": member_ids,
            "size": len(member_ids),
            "targets": sorted(t for t in targets if t),
            "primary_target": max(targets, key=lambda t: sum(
                1 for lid in member_ids
                if leads_by_id.get(lid, {}).get("target_name") == t
            )) if targets else None,
        })

    groups.sort(key=lambda g: (-g["size"], g["lead_ids"]))

    return groups, {"s1_pairs": s1_pairs, "s2_pairs": s2_pairs, "s3_pairs": s3_pairs}


def export_batch(*, profile_id=None, batch_size=20, offset=0, min_group_size=2):
    """Export a stable packet; offsets address the current unprocessed queue."""
    if batch_size < 1 or offset < 0 or min_group_size < 2:
        raise ValueError("batch-size must be positive, offset nonnegative, and min-group-size at least 2")
    db = get_db()
    try:
        db.execute("BEGIN")
        packet = review_context(db, profile_id)
        groups, _ = _build_groups(db, packet["profile_id"], min_group_size)
        selected = groups[offset:offset + batch_size]
        packet["groups"] = [dict(group, leads=[
            review_lead_snapshot(db, lead_id, packet["profile_id"]) for lead_id in group["lead_ids"]
        ]) for group in selected]
        packet.update(unprocessed_count=len(groups), offset=offset,
                      remaining_after_batch=max(0, len(groups) - offset - len(selected)))
        return packet
    finally:
        db.close()


def apply_decisions(batch, decisions, *, profile_id=None, dry_run=False):
    """Apply exactly the reviewed groups, rejecting foreign/stale input atomically."""
    if not isinstance(decisions, list) or any(not isinstance(item, dict) for item in decisions):
        raise ValueError("Decisions must be a JSON array of objects")
    db = get_db(write=not dry_run)
    try:
        db.execute("BEGIN" if dry_run else "BEGIN IMMEDIATE")
        profile_id = validate_review_context(db, batch, profile_id)
        groups = batch.get("groups")
        if not isinstance(groups, list) or any(not isinstance(item, dict) for item in groups):
            raise ValueError("Batch must contain exported groups")
        by_hash = {}
        all_ids = set()
        for group in groups:
            ids = group.get("lead_ids")
            snapshots = group.get("leads")
            if not isinstance(ids, list) or any(type(item) is not int for item in ids):
                raise ValueError("Group lead_ids must be integers")
            if len(ids) < 2 or len(set(ids)) != len(ids) or all_ids.intersection(ids):
                raise ValueError("Groups must have distinct, non-overlapping lead IDs")
            if group.get("group_hash") != group_hash(ids):
                raise ValueError("Group hash does not match its exported lead IDs")
            if not isinstance(snapshots, list) or any(not isinstance(item, dict) for item in snapshots):
                raise ValueError("Every group needs its exported lead snapshots")
            if any(type(item.get("id")) is not int for item in snapshots) or len(snapshots) != len(ids) or {item.get("id") for item in snapshots} != set(ids):
                raise ValueError("Group snapshots do not match lead_ids")
            by_hash[group["group_hash"]] = group
            all_ids.update(ids)
        hashes = [item.get("group_hash") for item in decisions]
        if any(not isinstance(item, str) for item in hashes) or len(set(hashes)) != len(hashes) or set(hashes) != set(by_hash):
            raise ValueError("Decisions must cover each exported group exactly once")
        allowed = {"group_hash", "decision", "keeper_id", "dead_end_ids", "rationale", "target_name_fills"}
        prepared = []
        skipped = 0
        for decision in decisions:
            if set(decision) - allowed:
                raise ValueError(f"Unknown decision fields: {sorted(set(decision) - allowed)}")
            group = by_hash[decision["group_hash"]]
            ids = set(group["lead_ids"])
            action = decision.get("decision")
            keeper = decision.get("keeper_id")
            dead_ids = decision.get("dead_end_ids", [])
            fills = decision.get("target_name_fills", {})
            if not isinstance(action, str) or action not in {"keep_all", "merge", "consolidate"}:
                raise ValueError("decision must be keep_all, merge, or consolidate")
            if not isinstance(decision.get("rationale"), str) or not decision["rationale"].strip():
                raise ValueError("Every decision requires a rationale")
            if not isinstance(dead_ids, list) or any(type(item) is not int for item in dead_ids):
                raise ValueError("dead_end_ids must be an array of integers")
            if len(set(dead_ids)) != len(dead_ids) or not set(dead_ids).issubset(ids):
                raise ValueError("Dead-ended leads must be distinct members of the reviewed group")
            if action == "keep_all":
                if keeper is not None or dead_ids:
                    raise ValueError("keep_all cannot specify a keeper or dead-ended leads")
            elif type(keeper) is not int or keeper not in ids or keeper in dead_ids or not dead_ids:
                raise ValueError("A merge/consolidation requires a group keeper and other group members to close")
            if not isinstance(fills, dict):
                raise ValueError("target_name_fills must be an object")
            for lead_id, target in fills.items():
                if not isinstance(lead_id, str) or not lead_id.isdecimal() or str(int(lead_id)) != lead_id or int(lead_id) not in ids:
                    raise ValueError("Target fills must name reviewed group members")
                if not isinstance(target, str) or not target.strip():
                    raise ValueError("Target fills must contain nonempty names")
            canonical = json.dumps(decision, sort_keys=True, ensure_ascii=False)
            prior = db.execute("SELECT * FROM lead_dedup_log WHERE group_hash=?", (group["group_hash"],)).fetchone() if _has_log(db) else None
            if prior:
                if "decision_json" not in prior.keys() or prior["decision_json"] != canonical or prior["profile_id"] != profile_id:
                    raise ValueError("Group was previously reviewed with a different decision; export remaining work")
                skipped += 1
                continue
            for snapshot in group["leads"]:
                current = validate_review_lead(db, snapshot, profile_id, status="open")
                if str(current["id"]) in fills and current.get("target_name"):
                    raise ValueError("Target fills cannot overwrite an existing target_name")
            prepared.append((decision, group, canonical))
        if not dry_run and prepared:
            _ensure_dedup_schema(db)
        dead_ended = 0
        for decision, group, canonical in prepared:
            action = decision["decision"]
            keeper = decision.get("keeper_id")
            dead_ids = decision.get("dead_end_ids", [])
            dead_ended += len(dead_ids)
            if dry_run:
                continue
            for lead_id, target in decision.get("target_name_fills", {}).items():
                db.execute("UPDATE leads SET target_name=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND profile_id=?",
                           (target, int(lead_id), profile_id))
                db.execute("INSERT INTO lead_notes (lead_id, note) VALUES (?, ?)",
                           (int(lead_id), f"Target inferred during dedup review: {target}"))
            for lead_id in dead_ids:
                prefix = "Duplicate of" if action == "merge" else "Consolidated into"
                updated = db.execute(
                    "UPDATE leads SET status='dead_end', stop_reason=?, updated_at=CURRENT_TIMESTAMP, "
                    "completed_at=CURRENT_TIMESTAMP WHERE id=? AND profile_id=? AND status='open'",
                    (f"{prefix} lead #{keeper}", lead_id, profile_id),
                )
                if updated.rowcount != 1:
                    raise ValueError(f"Lead #{lead_id} changed during dedup")
                db.execute(
                    "INSERT INTO lead_relations (lead_id, related_lead_id, relation_type) VALUES (?, ?, ?) "
                    "ON CONFLICT(lead_id, related_lead_id) DO UPDATE SET relation_type=excluded.relation_type",
                    (lead_id, keeper, "duplicate" if action == "merge" else "supersedes"),
                )
                db.execute("INSERT INTO lead_notes (lead_id, note) VALUES (?, ?)",
                           (lead_id, f"Dedup {action}: {decision['rationale']}"))
                if action == "consolidate":
                    source = next(item for item in group["leads"] if item["id"] == lead_id)
                    detail = f"Consolidated from lead #{lead_id}: {source['title']}"
                    if source.get("description"):
                        detail += "\n" + source["description"]
                    for note in source["notes"]:
                        detail += f"\nOriginal note #{note['id']}: {note['note']}"
                    db.execute("INSERT INTO lead_notes (lead_id, note) VALUES (?, ?)", (keeper, detail))
                    db.execute(
                        "INSERT OR IGNORE INTO lead_evidence (lead_id, evidence_type, evidence_ref) "
                        "SELECT ?, evidence_type, evidence_ref FROM lead_evidence WHERE lead_id=?", (keeper, lead_id),
                    )
            db.execute(
                "INSERT INTO lead_dedup_log (group_hash, lead_ids, decision, keeper_id, dead_ended_ids, rationale, profile_id, decision_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (group["group_hash"], json.dumps(group["lead_ids"]), action, keeper,
                 json.dumps(dead_ids), decision["rationale"], profile_id, canonical),
            )
        db.commit() if not dry_run else db.rollback()
        return {"profile_id": profile_id, "dry_run": dry_run, "applied": len(prepared),
                "skipped_already_applied": skipped, "dead_ended": dead_ended}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _show_group(db, identifier, profile_id):
    groups, _ = _build_groups(db, profile_id)
    candidates = [(group["group_hash"], group["lead_ids"]) for group in groups]
    candidates += [(row["group_hash"], json.loads(row["lead_ids"])) for row in _scoped_log_rows(db, profile_id)]
    matches = {key: ids for key, ids in candidates if key.startswith(identifier) or
               (identifier.isdecimal() and int(identifier) in ids)}
    if len(matches) != 1:
        raise ValueError("Group not found in this profile or identifier is ambiguous")
    key, ids = next(iter(matches.items()))
    return {"group_hash": key, "leads": [review_lead_snapshot(db, item, profile_id) for item in ids]}


def _verify(db, profile_id, sample_size):
    issues = []
    rows = _scoped_log_rows(db, profile_id)[:sample_size]
    for row in rows:
        keeper_id = row["keeper_id"]
        if keeper_id is not None:
            keeper = db.execute("SELECT status FROM leads WHERE id=? AND profile_id=?", (keeper_id, profile_id)).fetchone()
            if not keeper or keeper["status"] == "dead_end":
                issues.append(f"Keeper #{keeper_id} is missing or dead-ended")
        for lead_id in json.loads(row["dead_ended_ids"] or "[]"):
            lead = db.execute("SELECT status FROM leads WHERE id=? AND profile_id=?", (lead_id, profile_id)).fetchone()
            if not lead or lead["status"] != "dead_end":
                issues.append(f"Lead #{lead_id} is missing or no longer dead-ended")
            if not db.execute("SELECT 1 FROM lead_relations WHERE lead_id=? AND related_lead_id=?", (lead_id, keeper_id)).fetchone():
                issues.append(f"Missing relation #{lead_id} -> #{keeper_id}")
    return {"profile_id": profile_id, "verified": len(rows), "issues": issues}


def main():
    parser = argparse.ArgumentParser(description="Profile-scoped lead deduplication with reviewed batch snapshots")
    sub = parser.add_subparsers(dest="command", required=True)
    fill = sub.add_parser("fill-targets", help="Infer missing targets within the selected profile")
    fill.add_argument("--dry-run", action="store_true")
    fill.add_argument("--verbose", "-v", action="store_true")
    scan = sub.add_parser("scan", help="List unprocessed candidate groups")
    scan.add_argument("--min-group-size", type=int, default=2)
    show = sub.add_parser("show-group", help="Show a group in the selected profile")
    show.add_argument("identifier")
    export = sub.add_parser("export-batch", help="Export a database/profile-bound group snapshot")
    export.add_argument("--batch-size", type=int, default=20)
    export.add_argument("--offset", type=int, default=0, help="Offset into currently unprocessed groups; reset after applying a wave")
    export.add_argument("--min-group-size", type=int, default=2)
    apply = sub.add_parser("apply", help="Validate and atomically apply all decisions for an exported batch")
    apply.add_argument("--batch-file", required=True)
    apply.add_argument("--decisions-file", required=True)
    apply.add_argument("--dry-run", action="store_true")
    verify = sub.add_parser("verify", help="Check recent scoped decisions and keeper relationships")
    verify.add_argument("--sample-size", type=int, default=15)
    stats = sub.add_parser("stats", help="Report scoped queue and dedup metrics")
    for command in (fill, scan, show, export, apply, verify, stats):
        command.add_argument("--profile-id", "--profile", help="Override the pinned/default investigation profile")
        add_output_args(command)
    args = parser.parse_args()
    try:
        if args.command == "fill-targets":
            result = fill_targets(profile_id=args.profile_id, dry_run=args.dry_run)
        elif args.command == "export-batch":
            result = export_batch(profile_id=args.profile_id, batch_size=args.batch_size,
                                  offset=args.offset, min_group_size=args.min_group_size)
        elif args.command == "apply":
            result = apply_decisions(json.loads(Path(args.batch_file).read_text()),
                                     json.loads(Path(args.decisions_file).read_text()),
                                     profile_id=args.profile_id, dry_run=args.dry_run)
        else:
            db = get_db()
            try:
                profile_id = review_profile_id(db, args.profile_id)
                if args.command == "show-group":
                    result = _show_group(db, args.identifier, profile_id)
                elif args.command == "verify":
                    if args.sample_size < 1:
                        raise ValueError("sample-size must be positive")
                    result = _verify(db, profile_id, args.sample_size)
                else:
                    if getattr(args, "min_group_size", 2) < 2:
                        raise ValueError("min-group-size must be at least 2")
                    groups, pair_stats = _build_groups(db, profile_id, getattr(args, "min_group_size", 2))
                    result = {"profile_id": profile_id, "unprocessed_count": len(groups)}
                    if args.command == "scan":
                        result.update(groups=groups, pair_stats=pair_stats)
                    else:
                        rows = db.execute("SELECT status, COUNT(*) n FROM leads WHERE profile_id=? GROUP BY status", (profile_id,)).fetchall()
                        result.update(leads_by_status={row["status"]: row["n"] for row in rows},
                                      reviewed_groups=len(_scoped_log_rows(db, profile_id)))
            finally:
                db.close()
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    if not write_output(result, args):
        print(json.dumps(result, indent=2))
    if args.command == "verify" and result["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
