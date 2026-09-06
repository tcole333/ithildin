#!/usr/bin/env python3
"""
Bulk data extraction for analysis skills in OSINT investigations.

Provides data export functions that analysis agents use to load investigation
data for graph analysis, timeline correlation, pattern detection, etc.
Tracks analysis runs for change detection.

Part of investigation.db.

Usage:
    python tools/analysis_export.py connections-graph [--output FILE]
    python tools/analysis_export.py findings-dump [--thread-id N] [--min-confidence medium] [--output FILE]
    python tools/analysis_export.py timeline-export [--start DATE] [--end DATE] [--output FILE]
    python tools/analysis_export.py entity-network [--output FILE]
    python tools/analysis_export.py coverage-matrix [--top N] [--output FILE]
    python tools/analysis_export.py thread-summary [--thread-id N] [--output FILE]
    python tools/analysis_export.py analysis-state [--output FILE]
"""

import argparse
import sqlite3
from collections import Counter, defaultdict

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

try:
    from tools.lead_tracker import get_db
except ImportError:
    from lead_tracker import get_db

try:
    from tools.investigation_context import get_active_profile_id
except ImportError:
    try:
        from investigation_context import get_active_profile_id
    except ImportError:
        def get_active_profile_id():
            return ""

CONFIDENCE_ORDER = {"confirmed": 4, "high": 3, "medium": 2, "low": 1, "unverified": 0}


def _resolve_profile(profile_id=None, all_profiles=False):
    """Resolve profile_id: explicit > active profile > None."""
    if all_profiles:
        return None
    if profile_id is not None:
        return profile_id
    return get_active_profile_id() or None


def _label_key(value):
    """Return a conservative lookup key for an entity/connection label.

    Connections pre-date the canonical entity registry and therefore contain
    spelling, case, and whitespace variants.  Export is read-only, so only
    exact case/whitespace-insensitive matches and already-recorded aliases are
    eligible for canonicalization; fuzzy matching belongs on the write/review
    path, not in an analysis export.
    """
    if not value:
        return ""
    return " ".join(str(value).split()).casefold()


def _load_safe_endpoint_map(db):
    """Build a read-only raw-label -> canonical-entity map.

    A label is returned only when every exact entity, recorded alias, and
    finding-entity link for that normalized label resolves to the same target.
    Ambiguous labels remain raw in the export.  This prevents an exporter from
    silently performing a fuzzy merge while still honoring reviewed aliases
    and canonical finding links.
    """
    entity_rows = [dict(r) for r in db.execute("""
        SELECT id, name, entity_type, jurisdiction
        FROM entities
        ORDER BY id
    """).fetchall()]
    entities_by_id = {row["id"]: row for row in entity_rows}
    entity_ids_by_name = defaultdict(list)
    for row in entity_rows:
        key = _label_key(row["name"])
        if key:
            entity_ids_by_name[key].append(row["id"])

    def resolve_target(canonical_name, entity_id=None):
        if entity_id in entities_by_id:
            return entities_by_id[entity_id]
        ids = entity_ids_by_name.get(_label_key(canonical_name), [])
        if len(ids) == 1:
            return entities_by_id[ids[0]]
        if canonical_name and not ids:
            # A curated alias may pre-date creation of its canonical entity.
            return {
                "id": None,
                "name": " ".join(str(canonical_name).split()),
                "entity_type": None,
                "jurisdiction": None,
            }
        return None

    candidates = defaultdict(dict)

    def add_candidate(raw_label, target):
        key = _label_key(raw_label)
        if not key or not target:
            return
        target_key = (
            "id", target["id"]
        ) if target.get("id") is not None else (
            "name", _label_key(target.get("name"))
        )
        candidates[key][target_key] = target

    for row in entity_rows:
        add_candidate(row["name"], row)

    try:
        alias_rows = db.execute("""
            SELECT canonical_name, alias, entity_id
            FROM name_aliases
            ORDER BY id
        """).fetchall()
    except sqlite3.OperationalError:
        alias_rows = []
    for row in alias_rows:
        add_candidate(
            row["alias"],
            resolve_target(row["canonical_name"], row["entity_id"]),
        )

    try:
        finding_entity_rows = db.execute("""
            SELECT fe.raw_name, e.id, e.name, e.entity_type, e.jurisdiction
            FROM finding_entities fe
            JOIN entities e ON e.id = fe.entity_id
            WHERE fe.raw_name IS NOT NULL AND TRIM(fe.raw_name) <> ''
              AND fe.resolution_status IN ('asserted', 'reviewed')
            ORDER BY fe.finding_id, e.id
        """).fetchall()
    except sqlite3.OperationalError:
        finding_entity_rows = []
    for row in finding_entity_rows:
        add_candidate(row["raw_name"], dict(row))

    return {
        key: next(iter(targets.values()))
        for key, targets in candidates.items()
        if len(targets) == 1
    }


def _canonical_endpoint(raw_label, endpoint_map):
    """Resolve one endpoint without mutating the registry."""
    target = endpoint_map.get(_label_key(raw_label))
    if not target:
        return raw_label, None, None, None
    return (
        target["name"],
        target.get("id"),
        target.get("entity_type"),
        target.get("jurisdiction"),
    )


def _max_confidence(current, candidate):
    """Return the stronger confidence using the explicit project ordering."""
    if candidate is None:
        return current
    if current is None:
        return candidate
    current_rank = CONFIDENCE_ORDER.get(current, -1)
    candidate_rank = CONFIDENCE_ORDER.get(candidate, -1)
    if candidate_rank > current_rank:
        return candidate
    if candidate_rank < current_rank:
        return current
    # Unknown/equivalent labels get a deterministic, non-strength-bearing tie.
    return min(current, candidate)


def _primary_thread(thread_counts):
    """Choose the modal assigned thread; break ties by the lowest thread id."""
    if not thread_counts:
        return None
    return min(thread_counts, key=lambda thread_id: (-thread_counts[thread_id], thread_id))


# ── Schema ────────────────────────────────────────────────────

def _ensure_analysis_schema(db):
    """Create analysis tracking tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            findings_at_start INTEGER,
            connections_at_start INTEGER,
            findings_created INTEGER DEFAULT 0,
            hypotheses_created INTEGER DEFAULT 0,
            leads_created INTEGER DEFAULT 0,
            tags_created INTEGER DEFAULT 0,
            report_path TEXT,
            status TEXT DEFAULT 'running' CHECK(status IN ('running','completed','failed')),
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_analysis_runs_skill ON analysis_runs(skill_name);
        CREATE INDEX IF NOT EXISTS idx_analysis_runs_status ON analysis_runs(status);
    """)


def get_analysis_db():
    """Get DB connection with analysis schema ensured."""
    db = get_db()
    _ensure_analysis_schema(db)
    return db


# ── Analysis Run Tracking ────────────────────────────────────

def start_analysis_run(skill_name, profile_id=None):
    """Start an analysis run and return its ID."""
    db = get_analysis_db()
    resolved = _resolve_profile(profile_id)
    if resolved:
        findings_count = db.execute("SELECT COUNT(*) FROM findings WHERE profile_id = ?", (resolved,)).fetchone()[0]
        connections_count = db.execute("SELECT COUNT(*) FROM connections WHERE profile_id = ?", (resolved,)).fetchone()[0]
    else:
        findings_count = db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        connections_count = db.execute("SELECT COUNT(*) FROM connections").fetchone()[0]

    cursor = db.execute("""
        INSERT INTO analysis_runs (skill_name, findings_at_start, connections_at_start)
        VALUES (?, ?, ?)
    """, (skill_name, findings_count, connections_count))
    run_id = cursor.lastrowid
    db.commit()
    db.close()
    return run_id


def complete_analysis_run(run_id, findings_created=0, hypotheses_created=0,
                          leads_created=0, tags_created=0, report_path=None, notes=None):
    """Mark an analysis run as completed with results."""
    db = get_analysis_db()
    db.execute("""
        UPDATE analysis_runs SET
            completed_at = CURRENT_TIMESTAMP, status = 'completed',
            findings_created = ?, hypotheses_created = ?,
            leads_created = ?, tags_created = ?,
            report_path = ?, notes = ?
        WHERE id = ?
    """, (findings_created, hypotheses_created, leads_created, tags_created,
          report_path, notes, run_id))
    db.commit()
    db.close()


def fail_analysis_run(run_id, error_msg):
    """Mark an analysis run as failed."""
    db = get_analysis_db()
    db.execute("""
        UPDATE analysis_runs SET
            completed_at = CURRENT_TIMESTAMP, status = 'failed', notes = ?
        WHERE id = ?
    """, (error_msg, run_id))
    db.commit()
    db.close()


# ── Export Functions ────────────────────────────────────────

def export_connections_graph(profile_id=None, all_profiles=False):
    """Export connections as a canonicalized, self-consistent edge list.

    ``person_a``/``person_b`` are canonical entity labels when an exact entity,
    reviewed alias, or canonical finding link resolves safely.  The original DB
    values remain available as ``raw_person_a``/``raw_person_b``.  Node metadata
    is emitted for actual edge endpoints only, including endpoints with no
    findings, so ``node_count`` describes the graph rather than the findings
    table.
    """
    db = get_analysis_db()
    resolved = _resolve_profile(profile_id, all_profiles)

    if resolved:
        rows = db.execute("""
            SELECT c.id, c.person_a, c.person_b, c.relationship_type,
                   c.description, c.strength, c.date_range, c.verification_status,
                   c.created_at
            FROM connections c
            WHERE c.profile_id = ?
            ORDER BY c.id
        """, (resolved,)).fetchall()
    else:
        rows = db.execute("""
            SELECT c.id, c.person_a, c.person_b, c.relationship_type,
                   c.description, c.strength, c.date_range, c.verification_status,
                   c.created_at
            FROM connections c
            ORDER BY c.id
        """).fetchall()

    endpoint_map = _load_safe_endpoint_map(db)
    edges = []
    node_state = {}

    def register_node(label, raw_label, entity_id, entity_type, jurisdiction):
        if label is None or label == "":
            return
        if label not in node_state:
            node_state[label] = {
                "target_name": label,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "jurisdiction": jurisdiction,
                "raw_labels": set(),
                "finding_count": 0,
                "thread_counts": Counter(),
                "max_confidence": None,
            }
        state = node_state[label]
        if raw_label is not None:
            state["raw_labels"].add(raw_label)
        # An unresolved raw endpoint can share a display label with a resolved
        # endpoint.  Enrich only missing identity fields; never overwrite one
        # canonical ID with another.
        if state["entity_id"] is None and entity_id is not None:
            state["entity_id"] = entity_id
            state["entity_type"] = entity_type
            state["jurisdiction"] = jurisdiction

    for row in rows:
        edge = dict(row)
        raw_a = edge["person_a"]
        raw_b = edge["person_b"]
        canonical_a, entity_a_id, entity_a_type, entity_a_jurisdiction = _canonical_endpoint(
            raw_a, endpoint_map
        )
        canonical_b, entity_b_id, entity_b_type, entity_b_jurisdiction = _canonical_endpoint(
            raw_b, endpoint_map
        )
        edge.update({
            "raw_person_a": raw_a,
            "raw_person_b": raw_b,
            "person_a": canonical_a,
            "person_b": canonical_b,
            "entity_a_id": entity_a_id,
            "entity_b_id": entity_b_id,
        })
        edges.append(edge)
        register_node(
            canonical_a, raw_a, entity_a_id, entity_a_type, entity_a_jurisdiction
        )
        register_node(
            canonical_b, raw_b, entity_b_id, entity_b_type, entity_b_jurisdiction
        )

    # Aggregate findings in Python so aliases converge before confidence/thread
    # rollups.  SQL MAX(confidence) is lexical (and therefore wrong), while a
    # bare grouped thread_id is undefined in SQLite.
    if resolved:
        finding_rows = db.execute("""
            SELECT id, target_name, thread_id, confidence
            FROM findings
            WHERE profile_id = ?
            ORDER BY id
        """, (resolved,)).fetchall()
    else:
        finding_rows = db.execute("""
            SELECT id, target_name, thread_id, confidence
            FROM findings
            ORDER BY id
        """).fetchall()

    for row in finding_rows:
        canonical, _entity_id, _entity_type, _jurisdiction = _canonical_endpoint(
            row["target_name"], endpoint_map
        )
        state = node_state.get(canonical)
        if state is None:
            # A finding target without an edge is not a graph endpoint.
            continue
        state["finding_count"] += 1
        if row["thread_id"] is not None:
            state["thread_counts"][row["thread_id"]] += 1
        state["max_confidence"] = _max_confidence(
            state["max_confidence"], row["confidence"]
        )

    node_meta = {}
    for label in sorted(node_state, key=lambda value: (value.casefold(), value)):
        state = node_state[label]
        thread_counts = state.pop("thread_counts")
        thread_ids = sorted(thread_counts)
        state["raw_labels"] = sorted(
            state["raw_labels"], key=lambda value: (value.casefold(), value)
        )
        state["thread_id"] = _primary_thread(thread_counts)
        state["thread_ids"] = thread_ids
        node_meta[label] = state

    db.close()
    return {
        "edges": edges,
        "edge_count": len(edges),
        "node_metadata": node_meta,
        "node_count": len(node_state),
    }


def export_findings_dump(thread_id=None, min_confidence=None, profile_id=None,
                         all_profiles=False):
    """Export all findings with optional filters."""
    db = get_analysis_db()
    conditions = []
    params = []

    resolved = _resolve_profile(profile_id, all_profiles)
    if resolved:
        conditions.append("f.profile_id = ?")
        params.append(resolved)

    if thread_id:
        conditions.append("f.thread_id = ?")
        params.append(int(thread_id))
    if min_confidence:
        min_val = CONFIDENCE_ORDER.get(min_confidence, 0)
        confidence_list = [c for c, v in CONFIDENCE_ORDER.items() if v >= min_val]
        placeholders = ",".join("?" for _ in confidence_list)
        conditions.append(f"f.confidence IN ({placeholders})")
        params.extend(confidence_list)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(f"""
        SELECT f.id, f.target_name, f.finding_type, f.summary, f.detail,
               f.confidence, f.date_of_event, f.thread_id,
               f.claim_type, f.verification_status, f.created_at
        FROM findings f
        {where}
        ORDER BY f.id
    """, params).fetchall()

    findings = [dict(r) for r in rows]
    db.close()
    return {"findings": findings, "count": len(findings)}


def export_timeline(start_date=None, end_date=None, profile_id=None,
                    all_profiles=False):
    """Export findings and events on a timeline."""
    db = get_analysis_db()
    resolved = _resolve_profile(profile_id, all_profiles)

    # Findings with dates
    f_conditions = ["f.date_of_event IS NOT NULL"]
    f_params = []
    if resolved:
        f_conditions.append("f.profile_id = ?")
        f_params.append(resolved)
    if start_date:
        f_conditions.append("f.date_of_event >= ?")
        f_params.append(start_date)
    if end_date:
        f_conditions.append("f.date_of_event <= ?")
        f_params.append(end_date)

    findings = [dict(r) for r in db.execute(f"""
        SELECT f.id, f.target_name, f.summary, f.date_of_event,
               f.confidence, f.thread_id, f.finding_type
        FROM findings f
        WHERE {' AND '.join(f_conditions)}
        ORDER BY f.date_of_event
    """, f_params).fetchall()]

    # Events
    e_conditions = []
    e_params = []
    if resolved:
        e_conditions.append("profile_id = ?")
        e_params.append(resolved)
    if start_date:
        e_conditions.append("event_date >= ?")
        e_params.append(start_date)
    if end_date:
        e_conditions.append("event_date <= ?")
        e_params.append(end_date)

    e_where = f"WHERE {' AND '.join(e_conditions)}" if e_conditions else ""
    try:
        events = [dict(r) for r in db.execute(f"""
            SELECT id, event_date, event_name, category, description, relevance
            FROM event_timeline
            {e_where}
            ORDER BY event_date
        """, e_params).fetchall()]
    except sqlite3.OperationalError:
        events = []  # table might not exist yet

    # Also get findings WITHOUT dates but with created_at as proxy
    if resolved:
        undated = db.execute(
            "SELECT COUNT(*) as n FROM findings WHERE date_of_event IS NULL AND profile_id = ?",
            (resolved,)
        ).fetchone()["n"]
    else:
        undated = db.execute(
            "SELECT COUNT(*) as n FROM findings WHERE date_of_event IS NULL"
        ).fetchone()["n"]

    db.close()
    return {
        "dated_findings": findings,
        "events": events,
        "undated_finding_count": undated,
        "dated_finding_count": len(findings),
        "event_count": len(events),
    }


def export_entity_network(profile_id=None, all_profiles=False):
    """Export entity registry with roles, relations, and addresses.

    Entities are shared across profiles, but when profile-scoped, only
    returns entities referenced by findings in that profile, entities reached
    through the legacy role-name heuristic, and the opposite endpoints of
    relations touching those entities.  Including both relation endpoints
    keeps the exported network self-contained.
    """
    db = get_analysis_db()
    resolved = _resolve_profile(profile_id, all_profiles)

    if resolved:
        # Canonical scope comes from finding_entities.  Retain the former
        # role-name path as a compatibility supplement for legacy findings
        # that pre-date canonical entity links.
        base_rows = db.execute("""
            SELECT DISTINCT fe.entity_id AS id
            FROM finding_entities fe
            JOIN findings f ON f.id = fe.finding_id
            WHERE f.profile_id = ?
            UNION
            SELECT DISTINCT e.id
            FROM entities e
            JOIN entity_roles er ON er.entity_id = e.id
            WHERE er.person_name IN (
                SELECT DISTINCT target_name FROM findings WHERE profile_id = ?
            )
        """, (resolved, resolved)).fetchall()
        base_ids = {row["id"] for row in base_rows}

        if base_ids:
            placeholders = ",".join("?" for _ in base_ids)
            base_params = list(base_ids)
            relations = [dict(r) for r in db.execute("""
                SELECT entity_a_id, entity_b_id, relation_type, description, source
                FROM entity_relations
                WHERE entity_a_id IN ({ids}) OR entity_b_id IN ({ids})
                ORDER BY entity_a_id
            """.format(ids=placeholders), base_params + base_params).fetchall()]
        else:
            relations = []

        # Relations are unusable when one endpoint is absent from the entity
        # list. Expand one hop so every emitted relation can be resolved.
        entity_ids = set(base_ids)
        for relation in relations:
            entity_ids.add(relation["entity_a_id"])
            entity_ids.add(relation["entity_b_id"])

        if entity_ids:
            placeholders = ",".join("?" for _ in entity_ids)
            entity_params = list(entity_ids)
            entities = [dict(r) for r in db.execute("""
                SELECT id, name, entity_type, jurisdiction, status, ein,
                       address, source, notes, date_formed
                FROM entities
                WHERE id IN ({ids})
                ORDER BY id
            """.format(ids=placeholders), entity_params).fetchall()]

            roles = [dict(r) for r in db.execute("""
                SELECT entity_id, person_name, role, date_start, date_end, source
                FROM entity_roles
                WHERE entity_id IN ({ids})
                ORDER BY entity_id
            """.format(ids=placeholders), entity_params).fetchall()]

            addresses = [dict(r) for r in db.execute("""
                SELECT entity_id, address, address_type, date_observed, source
                FROM entity_addresses
                WHERE entity_id IN ({ids})
                ORDER BY entity_id
            """.format(ids=placeholders), entity_params).fetchall()]
        else:
            entities = []
            roles = []
            addresses = []
    else:
        entities = [dict(r) for r in db.execute("""
            SELECT id, name, entity_type, jurisdiction, status, ein, address, source, notes,
                   date_formed
            FROM entities ORDER BY id
        """).fetchall()]

        roles = [dict(r) for r in db.execute("""
            SELECT entity_id, person_name, role, date_start, date_end, source
            FROM entity_roles ORDER BY entity_id
        """).fetchall()]

        relations = [dict(r) for r in db.execute("""
            SELECT entity_a_id, entity_b_id, relation_type, description, source
            FROM entity_relations ORDER BY entity_a_id
        """).fetchall()]

        addresses = [dict(r) for r in db.execute("""
            SELECT entity_id, address, address_type, date_observed, source
            FROM entity_addresses ORDER BY entity_id
        """).fetchall()]

    db.close()
    return {
        "entities": entities,
        "roles": roles,
        "relations": relations,
        "addresses": addresses,
        "entity_count": len(entities),
        "role_count": len(roles),
        "relation_count": len(relations),
    }


def export_coverage_matrix(top_n=50, profile_id=None, all_profiles=False):
    """Export coverage matrix: findings per target, with gaps highlighted."""
    db = get_analysis_db()
    resolved = _resolve_profile(profile_id, all_profiles)

    f_cond = " WHERE profile_id = ?" if resolved else ""
    c_cond = " WHERE profile_id = ?" if resolved else ""
    f_params = [resolved] if resolved else []
    c_params = [resolved] if resolved else []

    # Top targets by finding count
    targets = db.execute(f"""
        SELECT target_name, COUNT(*) as finding_count,
               thread_id,
               SUM(CASE WHEN confidence IN ('confirmed','high') THEN 1 ELSE 0 END) as high_conf,
               SUM(CASE WHEN confidence IN ('low','unverified') THEN 1 ELSE 0 END) as low_conf,
               MIN(created_at) as first_finding,
               MAX(created_at) as last_finding
        FROM findings{f_cond}
        GROUP BY target_name
        ORDER BY finding_count DESC
        LIMIT ?
    """, f_params + [top_n]).fetchall()

    # Connection counts per target
    conn_counts = {}
    for row in db.execute(f"""
        SELECT name, COUNT(*) as conn_count FROM (
            SELECT person_a as name FROM connections{c_cond}
            UNION ALL
            SELECT person_b as name FROM connections{c_cond}
        ) GROUP BY name
    """, c_params + c_params):
        conn_counts[row["name"]] = row["conn_count"]

    matrix = []
    for t in targets:
        name = t["target_name"]
        matrix.append({
            "target": name,
            "findings": t["finding_count"],
            "high_confidence": t["high_conf"],
            "low_confidence": t["low_conf"],
            "connections": conn_counts.get(name, 0),
            "thread_id": t["thread_id"],
            "first_finding": t["first_finding"],
            "last_finding": t["last_finding"],
        })

    # Also find high-connectivity nodes with zero/few findings
    gaps = []
    for name, conn_count in sorted(conn_counts.items(), key=lambda x: x[1], reverse=True)[:100]:
        if resolved:
            finding_count = db.execute(
                "SELECT COUNT(*) FROM findings WHERE target_name = ? AND profile_id = ?",
                (name, resolved)
            ).fetchone()[0]
        else:
            finding_count = db.execute(
                "SELECT COUNT(*) FROM findings WHERE target_name = ?", (name,)
            ).fetchone()[0]
        if conn_count >= 3 and finding_count <= 2:
            gaps.append({
                "target": name,
                "connections": conn_count,
                "findings": finding_count,
                "gap_ratio": round(conn_count / max(finding_count, 1), 1),
            })

    gaps.sort(key=lambda x: x["gap_ratio"], reverse=True)

    db.close()
    return {
        "coverage": matrix,
        "gaps": gaps[:30],
        "total_targets": len(matrix),
        "total_gaps": len(gaps),
    }


def export_thread_summary(thread_id=None, profile_id=None, all_profiles=False):
    """Export per-thread summary statistics."""
    db = get_analysis_db()
    resolved = _resolve_profile(profile_id, all_profiles)

    conditions = []
    params = []
    if resolved:
        conditions.append("f.profile_id = ?")
        params.append(resolved)
    if thread_id:
        conditions.append("f.thread_id = ?")
        params.append(int(thread_id))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    threads = {}
    rows = db.execute(f"""
        SELECT f.thread_id,
               COUNT(*) as finding_count,
               COUNT(DISTINCT f.target_name) as unique_targets,
               SUM(CASE WHEN f.confidence IN ('confirmed','high') THEN 1 ELSE 0 END) as high_conf,
               SUM(CASE WHEN f.verification_status = 'verified' THEN 1 ELSE 0 END) as verified,
               MIN(f.created_at) as first_finding,
               MAX(f.created_at) as last_finding
        FROM findings f
        {where}
        GROUP BY f.thread_id
    """, params).fetchall()

    for r in rows:
        tid = r["thread_id"] or 0
        threads[tid] = dict(r)

    # Thread names
    thread_names = {}
    for row in db.execute("SELECT id, title FROM investigation_threads"):
        thread_names[row["id"]] = row["title"]

    for tid in threads:
        threads[tid]["thread_name"] = thread_names.get(tid, "Unassigned")

    # Connection counts per thread (approximate via finding targets)
    profile_filter = " AND profile_id = ?" if resolved else ""
    for tid, data in threads.items():
        f_query_params = [tid] + ([resolved] if resolved else [])
        target_list = [r[0] for r in db.execute(
            f"SELECT DISTINCT target_name FROM findings WHERE thread_id = ?{profile_filter}",
            f_query_params
        ).fetchall()]
        if target_list:
            placeholders = ",".join("?" for _ in target_list)
            conn_cond = " AND profile_id = ?" if resolved else ""
            conn_params = target_list + target_list + ([resolved] if resolved else [])
            conn_count = db.execute(f"""
                SELECT COUNT(DISTINCT id) FROM connections
                WHERE (person_a IN ({placeholders}) OR person_b IN ({placeholders})){conn_cond}
            """, conn_params).fetchone()[0]
        else:
            conn_count = 0
        threads[tid]["connections"] = conn_count

    # Lead counts per thread
    for tid, data in threads.items():
        leads = db.execute("""
            SELECT status, COUNT(*) as n FROM leads WHERE thread_id = ?
            GROUP BY status
        """, (tid,)).fetchall()
        data["leads"] = {r["status"]: r["n"] for r in leads}

    db.close()
    return {"threads": threads}


def export_pillar_dump():
    """Export institutional pillars, career arcs, persons, events, and scores."""
    db = get_analysis_db()

    try:
        pillars = [dict(r) for r in db.execute(
            "SELECT * FROM institutional_pillars ORDER BY pillar_type, name"
        ).fetchall()]
        persons = [dict(r) for r in db.execute(
            "SELECT * FROM persons ORDER BY canonical_name"
        ).fetchall()]
        arcs = [dict(r) for r in db.execute("""
            SELECT ca.*, ip.name as pillar_name, ip.pillar_type
            FROM career_arcs ca
            JOIN institutional_pillars ip ON ca.pillar_id = ip.id
            ORDER BY ca.person_name, COALESCE(ca.date_start, '0000')
        """).fetchall()]
        events = [dict(r) for r in db.execute("""
            SELECT pe.*, ip.name as pillar_name
            FROM pillar_events pe
            JOIN institutional_pillars ip ON pe.pillar_id = ip.id
            ORDER BY pe.event_date
        """).fetchall()]
        scores = [dict(r) for r in db.execute(
            "SELECT * FROM pillar_scores ORDER BY score_value DESC"
        ).fetchall()]
    except sqlite3.OperationalError:
        return {"error": "Pillar tables not found. Run pillar_tracker.py seed first.",
                "pillar_count": 0, "person_count": 0, "arc_count": 0,
                "event_count": 0, "score_count": 0}

    db.close()
    return {
        "pillars": pillars,
        "persons": persons,
        "career_arcs": arcs,
        "pillar_events": events,
        "pillar_scores": scores,
        "pillar_count": len(pillars),
        "person_count": len(persons),
        "arc_count": len(arcs),
        "event_count": len(events),
        "score_count": len(scores),
    }


def export_analysis_state(profile_id=None, all_profiles=False):
    """Export current analysis run history and change detection state."""
    db = get_analysis_db()
    resolved = _resolve_profile(profile_id, all_profiles)

    runs = [dict(r) for r in db.execute("""
        SELECT * FROM analysis_runs ORDER BY started_at DESC LIMIT 50
    """).fetchall()]

    # Current counts
    if resolved:
        findings_count = db.execute("SELECT COUNT(*) FROM findings WHERE profile_id = ?", (resolved,)).fetchone()[0]
        connections_count = db.execute("SELECT COUNT(*) FROM connections WHERE profile_id = ?", (resolved,)).fetchone()[0]
    else:
        findings_count = db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        connections_count = db.execute("SELECT COUNT(*) FROM connections").fetchone()[0]

    try:
        hypotheses_count = db.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
    except sqlite3.OperationalError:
        hypotheses_count = 0

    try:
        tags_count = db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    except sqlite3.OperationalError:
        tags_count = 0

    # Changes since last run of each skill
    changes_since = {}
    for skill in ["analyze-network", "generate-hunches", "timeline-analysis", "systemic-analysis"]:
        last_run = db.execute("""
            SELECT findings_at_start, connections_at_start, completed_at
            FROM analysis_runs WHERE skill_name = ? AND status = 'completed'
            ORDER BY completed_at DESC LIMIT 1
        """, (skill,)).fetchone()

        if last_run:
            changes_since[skill] = {
                "last_run": last_run["completed_at"],
                "new_findings": findings_count - (last_run["findings_at_start"] or 0),
                "new_connections": connections_count - (last_run["connections_at_start"] or 0),
            }
        else:
            changes_since[skill] = {
                "last_run": None,
                "new_findings": findings_count,
                "new_connections": connections_count,
            }

    db.close()
    return {
        "runs": runs,
        "current_counts": {
            "findings": findings_count,
            "connections": connections_count,
            "hypotheses": hypotheses_count,
            "tags": tags_count,
        },
        "changes_since_last": changes_since,
    }


# ── CLI ────────────────────────────────────────────────────

def _add_profile_args(subparser):
    """Add --profile and --all-profiles to a subparser."""
    subparser.add_argument("--profile", default=None, help="Investigation profile (default: active)")
    subparser.add_argument("--all-profiles", action="store_true", help="Include all profiles")


def main():
    parser = argparse.ArgumentParser(description="Bulk data extraction for analysis skills")
    sub = parser.add_subparsers(dest="command")

    # connections-graph
    p_cg = sub.add_parser("connections-graph", help="Export connections as edge list")
    _add_profile_args(p_cg)
    add_output_args(p_cg)

    # findings-dump
    p_fd = sub.add_parser("findings-dump", help="Export all findings")
    p_fd.add_argument("--thread-id", type=int)
    p_fd.add_argument("--min-confidence", choices=list(CONFIDENCE_ORDER.keys()))
    _add_profile_args(p_fd)
    add_output_args(p_fd)

    # timeline-export
    p_te = sub.add_parser("timeline-export", help="Export timeline data")
    p_te.add_argument("--start", help="Start date YYYY-MM-DD")
    p_te.add_argument("--end", help="End date YYYY-MM-DD")
    _add_profile_args(p_te)
    add_output_args(p_te)

    # entity-network
    p_en = sub.add_parser("entity-network", help="Export entity registry")
    _add_profile_args(p_en)
    add_output_args(p_en)

    # coverage-matrix
    p_cm = sub.add_parser("coverage-matrix", help="Export coverage matrix")
    p_cm.add_argument("--top", type=int, default=50)
    _add_profile_args(p_cm)
    add_output_args(p_cm)

    # thread-summary
    p_ts = sub.add_parser("thread-summary", help="Export thread summaries")
    p_ts.add_argument("--thread-id", type=int)
    _add_profile_args(p_ts)
    add_output_args(p_ts)

    # analysis-state
    p_as = sub.add_parser("analysis-state", help="Export analysis run history")
    _add_profile_args(p_as)
    add_output_args(p_as)

    # pillar-dump
    p_pd = sub.add_parser("pillar-dump", help="Export institutional pillars, career arcs, and scores")
    add_output_args(p_pd)

    args = parser.parse_args()
    p_id = getattr(args, "profile", None)
    p_all = getattr(args, "all_profiles", False)

    if args.command == "connections-graph":
        result = export_connections_graph(profile_id=p_id, all_profiles=p_all)
        if write_output(result, args, summary="connections graph"):
            return
        print(f"Connections Graph: {result['edge_count']} edges, {result['node_count']} nodes")
        for e in result["edges"][:10]:
            print(f"  {e['person_a']} --[{e['relationship_type']}]--> {e['person_b']}")
        if result["edge_count"] > 10:
            print(f"  ... ({result['edge_count'] - 10} more)")

    elif args.command == "findings-dump":
        result = export_findings_dump(
            thread_id=args.thread_id,
            min_confidence=args.min_confidence,
            profile_id=p_id, all_profiles=p_all,
        )
        if write_output(result, args, summary=f"findings dump ({result['count']})"):
            return
        print(f"Findings Dump: {result['count']} findings")

    elif args.command == "timeline-export":
        result = export_timeline(start_date=args.start, end_date=args.end,
                                 profile_id=p_id, all_profiles=p_all)
        if write_output(result, args, summary="timeline export"):
            return
        print("Timeline Export:")
        print(f"  {result['dated_finding_count']} dated findings")
        print(f"  {result['event_count']} events")
        print(f"  {result['undated_finding_count']} undated findings")

    elif args.command == "entity-network":
        result = export_entity_network(profile_id=p_id, all_profiles=p_all)
        if write_output(result, args, summary="entity network"):
            return
        print("Entity Network:")
        print(f"  {result['entity_count']} entities")
        print(f"  {result['role_count']} roles")
        print(f"  {result['relation_count']} relations")

    elif args.command == "coverage-matrix":
        result = export_coverage_matrix(top_n=args.top, profile_id=p_id, all_profiles=p_all)
        if write_output(result, args, summary=f"coverage matrix (top {args.top})"):
            return
        print(f"Coverage Matrix (top {args.top}):")
        print(f"{'Target':<40} {'Findings':>8} {'Hi-Conf':>7} {'Conns':>5}")
        print("-" * 65)
        for c in result["coverage"][:20]:
            print(f"{c['target']:<40} {c['findings']:>8} {c['high_confidence']:>7} {c['connections']:>5}")
        if result["gaps"]:
            print("\nCoverage Gaps (high connectivity, low findings):")
            for g in result["gaps"][:10]:
                print(f"  {g['target']:<40} conns={g['connections']} findings={g['findings']}")

    elif args.command == "thread-summary":
        result = export_thread_summary(thread_id=args.thread_id,
                                       profile_id=p_id, all_profiles=p_all)
        if write_output(result, args, summary="thread summary"):
            return
        print("Thread Summary:")
        for tid, data in sorted(result["threads"].items()):
            print(f"\n  Thread {tid}: {data['thread_name']}")
            print(f"    Findings: {data['finding_count']} ({data['unique_targets']} targets)")
            print(f"    High confidence: {data['high_conf']}")
            print(f"    Verified: {data['verified']}")
            print(f"    Connections: {data['connections']}")
            if data.get("leads"):
                leads_str = ", ".join(f"{s}={n}" for s, n in data["leads"].items())
                print(f"    Leads: {leads_str}")

    elif args.command == "analysis-state":
        result = export_analysis_state(profile_id=p_id, all_profiles=p_all)
        if write_output(result, args, summary="analysis state"):
            return
        counts = result["current_counts"]
        print("Analysis State:")
        print(f"  Findings: {counts['findings']}, Connections: {counts['connections']}")
        print(f"  Hypotheses: {counts['hypotheses']}, Tags: {counts['tags']}")
        print("\nChanges Since Last Run:")
        for skill, changes in result["changes_since_last"].items():
            last = changes["last_run"] or "never"
            print(f"  {skill:<25} last={last}  "
                  f"+{changes['new_findings']} findings, +{changes['new_connections']} connections")

    elif args.command == "pillar-dump":
        result = export_pillar_dump()
        if write_output(result, args, summary="pillar dump"):
            return
        print("Pillar Dump:")
        print(f"  {result['pillar_count']} institutions")
        print(f"  {result['person_count']} persons")
        print(f"  {result['arc_count']} career arcs")
        print(f"  {result['event_count']} pillar events")
        print(f"  {result['score_count']} scores")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
