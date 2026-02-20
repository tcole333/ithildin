#!/usr/bin/env python3
"""
Hypothesis lifecycle tracker for the Epstein OSINT investigation.

Structured, trackable hypotheses with evidence tracking and status management.
Part of investigation.db.

Usage:
    python tools/hypothesis_tracker.py add --title "..." --pattern-type structural --description "..."
    python tools/hypothesis_tracker.py list [--status proposed] [--pattern-type X]
    python tools/hypothesis_tracker.py show 5
    python tools/hypothesis_tracker.py investigate --id 5 --lead-id 42
    python tools/hypothesis_tracker.py confirm --id 5 --evidence "findings:412,415" --reason "..."
    python tools/hypothesis_tracker.py refute --id 5 --evidence "findings:420" --reason "..."
    python tools/hypothesis_tracker.py supersede --id 5 --by 8 --reason "..."
    python tools/hypothesis_tracker.py search "USVI"
    python tools/hypothesis_tracker.py stats
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

try:
    from tools.lead_tracker import get_db
except ImportError:
    from lead_tracker import get_db

VALID_STATUSES = ["proposed", "investigating", "confirmed", "refuted", "superseded", "stale"]
VALID_PATTERN_TYPES = ["emerging_theme", "structural", "temporal", "financial", "operational", "framework_candidate"]


# ── Schema ────────────────────────────────────────────────────

def _ensure_hypothesis_schema(db):
    """Create hypothesis tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS hypotheses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            pattern_type TEXT,
            status TEXT DEFAULT 'proposed'
                CHECK(status IN ('proposed','investigating','confirmed','refuted','superseded','stale')),
            predicted_evidence TEXT,
            search_plan TEXT,
            evidence_for TEXT,
            evidence_against TEXT,
            originated_from TEXT,
            lead_id INTEGER REFERENCES leads(id),
            thread_id INTEGER REFERENCES investigation_threads(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            resolved_by TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON hypotheses(status);
        CREATE INDEX IF NOT EXISTS idx_hypotheses_pattern ON hypotheses(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_hypotheses_thread ON hypotheses(thread_id);
    """)


def get_hypothesis_db():
    """Get DB connection with hypothesis schema ensured."""
    db = get_db()
    _ensure_hypothesis_schema(db)
    return db


# ── CRUD ────────────────────────────────────────────────────

def add_hypothesis(title, pattern_type=None, description=None, predicted_evidence=None,
                   search_plan=None, originated_from=None, thread_id=None):
    """Add a new hypothesis. Returns the hypothesis ID."""
    if pattern_type and pattern_type not in VALID_PATTERN_TYPES:
        print(f"ERROR: Invalid pattern_type '{pattern_type}'. Valid: {VALID_PATTERN_TYPES}")
        return None

    db = get_hypothesis_db()
    cursor = db.execute("""
        INSERT INTO hypotheses (title, description, pattern_type, predicted_evidence,
                                search_plan, originated_from, thread_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, description, pattern_type, predicted_evidence,
          search_plan, originated_from, thread_id))
    hyp_id = cursor.lastrowid
    db.commit()
    db.close()
    return hyp_id


def list_hypotheses(status=None, pattern_type=None, thread_id=None, limit=50):
    """List hypotheses with optional filters."""
    db = get_hypothesis_db()
    conditions = []
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if pattern_type:
        conditions.append("pattern_type = ?")
        params.append(pattern_type)
    if thread_id:
        conditions.append("thread_id = ?")
        params.append(int(thread_id))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT * FROM hypotheses {where}
        ORDER BY
            CASE status
                WHEN 'proposed' THEN 0 WHEN 'investigating' THEN 1
                WHEN 'confirmed' THEN 2 WHEN 'refuted' THEN 3
                WHEN 'superseded' THEN 4 WHEN 'stale' THEN 5
            END,
            created_at DESC
        LIMIT ?
    """
    params.append(limit)
    rows = db.execute(query, params).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_hypothesis(hyp_id):
    """Get a single hypothesis by ID."""
    db = get_hypothesis_db()
    row = db.execute("SELECT * FROM hypotheses WHERE id = ?", (hyp_id,)).fetchone()
    db.close()
    return dict(row) if row else None


def investigate_hypothesis(hyp_id, lead_id):
    """Link hypothesis to an active lead and set status to investigating."""
    db = get_hypothesis_db()
    row = db.execute("SELECT id, status FROM hypotheses WHERE id = ?", (hyp_id,)).fetchone()
    if not row:
        print(f"ERROR: Hypothesis #{hyp_id} not found")
        db.close()
        return False
    if row["status"] not in ("proposed", "stale"):
        print(f"ERROR: Hypothesis #{hyp_id} is '{row['status']}', can only investigate proposed/stale")
        db.close()
        return False

    db.execute("""
        UPDATE hypotheses SET status = 'investigating', lead_id = ?,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (lead_id, hyp_id))
    db.commit()
    db.close()
    return True


def resolve_hypothesis(hyp_id, resolution, evidence=None, reason=None, resolved_by=None):
    """Confirm or refute a hypothesis."""
    if resolution not in ("confirmed", "refuted"):
        print(f"ERROR: Resolution must be 'confirmed' or 'refuted'")
        return False

    db = get_hypothesis_db()
    row = db.execute("SELECT id, status, evidence_for, evidence_against FROM hypotheses WHERE id = ?",
                     (hyp_id,)).fetchone()
    if not row:
        print(f"ERROR: Hypothesis #{hyp_id} not found")
        db.close()
        return False

    # Append evidence to the appropriate field
    if evidence:
        if resolution == "confirmed":
            existing = row["evidence_for"] or ""
            updated = f"{existing}; {evidence}" if existing else evidence
            db.execute("UPDATE hypotheses SET evidence_for = ? WHERE id = ?", (updated, hyp_id))
        else:
            existing = row["evidence_against"] or ""
            updated = f"{existing}; {evidence}" if existing else evidence
            db.execute("UPDATE hypotheses SET evidence_against = ? WHERE id = ?", (updated, hyp_id))

    update_reason = f" — {reason}" if reason else ""
    db.execute("""
        UPDATE hypotheses SET status = ?, updated_at = CURRENT_TIMESTAMP,
               resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
        WHERE id = ?
    """, (resolution, (resolved_by or "") + update_reason, hyp_id))
    db.commit()
    db.close()
    return True


def supersede_hypothesis(hyp_id, by_id, reason=None):
    """Mark hypothesis as superseded by another."""
    db = get_hypothesis_db()
    row = db.execute("SELECT id FROM hypotheses WHERE id = ?", (hyp_id,)).fetchone()
    by_row = db.execute("SELECT id FROM hypotheses WHERE id = ?", (by_id,)).fetchone()
    if not row:
        print(f"ERROR: Hypothesis #{hyp_id} not found")
        db.close()
        return False
    if not by_row:
        print(f"ERROR: Superseding hypothesis #{by_id} not found")
        db.close()
        return False

    resolved_msg = f"Superseded by #{by_id}"
    if reason:
        resolved_msg += f" — {reason}"

    db.execute("""
        UPDATE hypotheses SET status = 'superseded', updated_at = CURRENT_TIMESTAMP,
               resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
        WHERE id = ?
    """, (resolved_msg, hyp_id))
    db.commit()
    db.close()
    return True


def add_evidence(hyp_id, evidence, direction="for"):
    """Add evidence for or against a hypothesis without changing status."""
    db = get_hypothesis_db()
    row = db.execute("SELECT evidence_for, evidence_against FROM hypotheses WHERE id = ?",
                     (hyp_id,)).fetchone()
    if not row:
        print(f"ERROR: Hypothesis #{hyp_id} not found")
        db.close()
        return False

    field = "evidence_for" if direction == "for" else "evidence_against"
    existing = row[field] or ""
    updated = f"{existing}; {evidence}" if existing else evidence
    db.execute(f"UPDATE hypotheses SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
               (updated, hyp_id))
    db.commit()
    db.close()
    return True


def search_hypotheses(query, limit=50):
    """Search hypotheses by text across title, description, predicted_evidence, search_plan."""
    db = get_hypothesis_db()
    pattern = f"%{query}%"
    rows = db.execute("""
        SELECT * FROM hypotheses
        WHERE title LIKE ? OR description LIKE ? OR predicted_evidence LIKE ?
              OR search_plan LIKE ? OR evidence_for LIKE ? OR evidence_against LIKE ?
        ORDER BY created_at DESC LIMIT ?
    """, (pattern, pattern, pattern, pattern, pattern, pattern, limit)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def hypothesis_stats():
    """Get hypothesis statistics."""
    db = get_hypothesis_db()
    stats = {}

    total = db.execute("SELECT COUNT(*) as n FROM hypotheses").fetchone()["n"]
    stats["total"] = total

    for status in VALID_STATUSES:
        row = db.execute("SELECT COUNT(*) as n FROM hypotheses WHERE status = ?", (status,)).fetchone()
        stats[f"status_{status}"] = row["n"]

    for pt in VALID_PATTERN_TYPES:
        row = db.execute("SELECT COUNT(*) as n FROM hypotheses WHERE pattern_type = ?", (pt,)).fetchone()
        stats[f"pattern_{pt}"] = row["n"]

    with_leads = db.execute("SELECT COUNT(*) as n FROM hypotheses WHERE lead_id IS NOT NULL").fetchone()
    stats["linked_to_leads"] = with_leads["n"]

    db.close()
    return stats


# ── CLI ────────────────────────────────────────────────────

def _format_hypothesis(h, verbose=False):
    """Format a hypothesis for display."""
    status_icons = {
        "proposed": "?", "investigating": ">", "confirmed": "+",
        "refuted": "x", "superseded": "~", "stale": "."
    }
    icon = status_icons.get(h["status"], " ")
    pt = f" [{h['pattern_type']}]" if h.get("pattern_type") else ""
    lead = f" lead=#{h['lead_id']}" if h.get("lead_id") else ""
    thread = f" T{h['thread_id']}" if h.get("thread_id") else ""

    line = f"  [{icon}] #{h['id']:>3} {h['status']:<14}{pt}{thread}{lead}  {h['title']}"

    if verbose and h.get("description"):
        line += f"\n         {h['description'][:200]}"
    if verbose and h.get("predicted_evidence"):
        line += f"\n         Predict: {h['predicted_evidence'][:150]}"
    if verbose and h.get("search_plan"):
        line += f"\n         Plan: {h['search_plan'][:150]}"
    if verbose and h.get("evidence_for"):
        line += f"\n         For: {h['evidence_for'][:150]}"
    if verbose and h.get("evidence_against"):
        line += f"\n         Against: {h['evidence_against'][:150]}"

    return line


def main():
    parser = argparse.ArgumentParser(description="Hypothesis lifecycle tracker")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="Add a new hypothesis")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--pattern-type", choices=VALID_PATTERN_TYPES)
    p_add.add_argument("--description")
    p_add.add_argument("--predicted-evidence")
    p_add.add_argument("--search-plan")
    p_add.add_argument("--originated-from")
    p_add.add_argument("--thread-id", type=int)

    # list
    p_list = sub.add_parser("list", help="List hypotheses")
    p_list.add_argument("--status", choices=VALID_STATUSES)
    p_list.add_argument("--pattern-type", choices=VALID_PATTERN_TYPES)
    p_list.add_argument("--thread-id", type=int)
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("-v", "--verbose", action="store_true")
    add_output_args(p_list)

    # show
    p_show = sub.add_parser("show", help="Show hypothesis detail")
    p_show.add_argument("id", type=int)
    add_output_args(p_show)

    # investigate
    p_inv = sub.add_parser("investigate", help="Link hypothesis to lead, set status to investigating")
    p_inv.add_argument("--id", type=int, required=True)
    p_inv.add_argument("--lead-id", type=int, required=True)

    # confirm
    p_conf = sub.add_parser("confirm", help="Confirm a hypothesis")
    p_conf.add_argument("--id", type=int, required=True)
    p_conf.add_argument("--evidence")
    p_conf.add_argument("--reason")
    p_conf.add_argument("--resolved-by")

    # refute
    p_ref = sub.add_parser("refute", help="Refute a hypothesis")
    p_ref.add_argument("--id", type=int, required=True)
    p_ref.add_argument("--evidence")
    p_ref.add_argument("--reason")
    p_ref.add_argument("--resolved-by")

    # supersede
    p_sup = sub.add_parser("supersede", help="Mark hypothesis as superseded by another")
    p_sup.add_argument("--id", type=int, required=True)
    p_sup.add_argument("--by", type=int, required=True)
    p_sup.add_argument("--reason")

    # evidence
    p_ev = sub.add_parser("evidence", help="Add evidence for or against a hypothesis")
    p_ev.add_argument("--id", type=int, required=True)
    p_ev.add_argument("--for", dest="evidence_for")
    p_ev.add_argument("--against", dest="evidence_against")

    # search
    p_search = sub.add_parser("search", help="Search hypotheses by text")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=50)
    add_output_args(p_search)

    # stats
    sub.add_parser("stats", help="Show hypothesis statistics")

    args = parser.parse_args()

    if args.command == "add":
        hyp_id = add_hypothesis(
            title=args.title,
            pattern_type=args.pattern_type,
            description=args.description,
            predicted_evidence=args.predicted_evidence,
            search_plan=args.search_plan,
            originated_from=args.originated_from,
            thread_id=args.thread_id,
        )
        if hyp_id:
            print(f"Hypothesis #{hyp_id} created: {args.title}")

    elif args.command == "list":
        results = list_hypotheses(
            status=args.status,
            pattern_type=args.pattern_type,
            thread_id=args.thread_id,
            limit=args.limit,
        )
        if write_output(results, args, summary=f"hypotheses ({len(results)})"):
            return
        if not results:
            print("No hypotheses found.")
            return
        print(f"Hypotheses ({len(results)}):")
        for h in results:
            print(_format_hypothesis(h, verbose=args.verbose))

    elif args.command == "show":
        h = get_hypothesis(args.id)
        if not h:
            print(f"Hypothesis #{args.id} not found")
            sys.exit(1)
        if write_output(h, args, summary=f"hypothesis #{args.id}"):
            return
        print(f"Hypothesis #{h['id']}: {h['title']}")
        print(f"  Status:       {h['status']}")
        print(f"  Pattern:      {h['pattern_type'] or 'unset'}")
        print(f"  Thread:       {h['thread_id'] or 'unset'}")
        print(f"  Lead:         #{h['lead_id']}" if h.get('lead_id') else "  Lead:         none")
        print(f"  Origin:       {h['originated_from'] or 'manual'}")
        print(f"  Created:      {h['created_at']}")
        print(f"  Updated:      {h['updated_at']}")
        if h.get("description"):
            print(f"  Description:  {h['description']}")
        if h.get("predicted_evidence"):
            print(f"  Predicted:    {h['predicted_evidence']}")
        if h.get("search_plan"):
            print(f"  Search plan:  {h['search_plan']}")
        if h.get("evidence_for"):
            print(f"  Evidence FOR: {h['evidence_for']}")
        if h.get("evidence_against"):
            print(f"  Evidence AGT: {h['evidence_against']}")
        if h.get("resolved_at"):
            print(f"  Resolved:     {h['resolved_at']}  by: {h['resolved_by']}")

    elif args.command == "investigate":
        if investigate_hypothesis(args.id, args.lead_id):
            print(f"Hypothesis #{args.id} → investigating (linked to lead #{args.lead_id})")

    elif args.command == "confirm":
        if resolve_hypothesis(args.id, "confirmed", evidence=args.evidence,
                              reason=args.reason, resolved_by=args.resolved_by):
            print(f"Hypothesis #{args.id} → confirmed")

    elif args.command == "refute":
        if resolve_hypothesis(args.id, "refuted", evidence=args.evidence,
                              reason=args.reason, resolved_by=args.resolved_by):
            print(f"Hypothesis #{args.id} → refuted")

    elif args.command == "supersede":
        if supersede_hypothesis(args.id, args.by, reason=args.reason):
            print(f"Hypothesis #{args.id} → superseded by #{args.by}")

    elif args.command == "evidence":
        if args.evidence_for:
            if add_evidence(args.id, args.evidence_for, direction="for"):
                print(f"Added supporting evidence to hypothesis #{args.id}")
        if args.evidence_against:
            if add_evidence(args.id, args.evidence_against, direction="against"):
                print(f"Added contradicting evidence to hypothesis #{args.id}")
        if not args.evidence_for and not args.evidence_against:
            print("ERROR: Provide --for or --against with evidence text")

    elif args.command == "search":
        results = search_hypotheses(args.query, limit=args.limit)
        if write_output(results, args, summary=f"hypothesis search '{args.query}'"):
            return
        if not results:
            print(f"No hypotheses matching '{args.query}'")
            return
        print(f"Hypotheses matching '{args.query}' ({len(results)}):")
        for h in results:
            print(_format_hypothesis(h))

    elif args.command == "stats":
        s = hypothesis_stats()
        print("Hypothesis Statistics")
        print("=" * 40)
        print(f"  Total:          {s['total']}")
        print(f"  Proposed:       {s['status_proposed']}")
        print(f"  Investigating:  {s['status_investigating']}")
        print(f"  Confirmed:      {s['status_confirmed']}")
        print(f"  Refuted:        {s['status_refuted']}")
        print(f"  Superseded:     {s['status_superseded']}")
        print(f"  Stale:          {s['status_stale']}")
        print(f"  Linked to leads: {s['linked_to_leads']}")
        print(f"\nBy pattern type:")
        for pt in VALID_PATTERN_TYPES:
            count = s.get(f"pattern_{pt}", 0)
            if count:
                print(f"  {pt:<18} {count}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
