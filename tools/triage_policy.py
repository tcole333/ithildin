#!/usr/bin/env python3
"""
Suggested triage scheduling policy — depth, skill routing, overlap candidates,
and thread coverage cues for review.

The triage skill uses these defaults; the reviewer owns question equivalence,
evidence coverage, and final decisions. Counts do not trigger automatic closure.

Usage:
    uv run python tools/triage_policy.py assess "Target Name"
    uv run python tools/triage_policy.py rules
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    from tools.lead_tracker import open_review_db, review_profile_id
    from tools.output_util import add_output_args, write_output
except ImportError:
    from lead_tracker import open_review_db, review_profile_id
    from output_util import add_output_args, write_output

DB_PATH = Path(os.environ.get("ITHILDIN_DB_PATH", Path(__file__).resolve().parent.parent / "investigation.db"))

# ── Constants ────────────────────────────────────────────────

DEPTH_TIERS = ("scan", "standard", "deep_dive")

SKILL_RECOMMENDATION = {
    ("deep_dive", "person"): "/deep-investigate",
    ("deep_dive", "entity"): "/deep-investigate",
    ("deep_dive", "financial"): "/deep-investigate",
    ("standard", "person"): "/investigate-person",
    ("standard", "entity"): "/trace-entity",
    ("standard", "financial"): "/pursue-lead",
    ("standard", "connection"): "/pursue-lead",
    ("scan", "person"): "/pursue-lead",
    ("scan", "entity"): "/pursue-lead",
    ("scan", "financial"): "/pursue-lead",
    ("scan", "connection"): "/pursue-lead",
    # Depth-analysis skills: route specific source types to focused analyzers
    ("standard", "filing"): "/analyze-filing",
    ("standard", "contract"): "/analyze-contract",
    ("standard", "case"): "/analyze-case",
    ("deep_dive", "filing"): "/analyze-filing",
    ("deep_dive", "contract"): "/analyze-contract",
    ("deep_dive", "case"): "/analyze-case",
    ("scan", "filing"): "/analyze-filing",
    ("scan", "contract"): "/analyze-contract",
    ("scan", "case"): "/analyze-case",
    # Nonprofit/grant routing
    ("deep_dive", "nonprofit"): "/trace-grants",
    ("standard", "nonprofit"): "/trace-grants",
    ("scan", "nonprofit"): "/trace-grants",
    ("deep_dive", "grant"): "/trace-grants",
    ("standard", "grant"): "/trace-grants",
    ("scan", "grant"): "/trace-grants",
}

THREAD_QUEUE_REVIEW_SIZE = 30

# Structural signals that trigger tier escalation
STANDARD_TIER_MIN_ROLES = 3
STANDARD_TIER_MIN_CONNECTIONS = 3
DEEP_DIVE_MIN_ROLES = 5
DEEP_DIVE_MIN_CONNECTIONS = 8


# ── Assessment Functions ─────────────────────────────────────

def _get_structural_signals(target_name, db, profile_id=None):
    """Query entity_roles, connections, and findings counts for a target."""
    profile_id = review_profile_id(db, profile_id)
    roles = db.execute(
        "SELECT COUNT(*) FROM entity_roles WHERE person_name LIKE ?",
        (f"%{target_name}%",)
    ).fetchone()[0]
    connections = db.execute(
        "SELECT COUNT(*) FROM connections WHERE profile_id=? AND (person_a=? COLLATE NOCASE OR person_b=? COLLATE NOCASE)",
        (profile_id, target_name, target_name)
    ).fetchone()[0]
    findings = db.execute(
        "SELECT COUNT(*) FROM findings WHERE profile_id=? AND target_name=? COLLATE NOCASE",
        (profile_id, target_name)
    ).fetchone()[0]
    return {"roles": roles, "connections": connections, "findings": findings}


def assess_depth_tier(target_name, db, key_persons=None, known_addresses=None, profile_id=None):
    """Assign a depth tier based on structural signals and profile context.

    Returns (tier, reason) tuple.
    """
    key_persons = key_persons or []
    known_addresses = known_addresses or []

    # Key person → deep_dive
    target_lower = target_name.lower()
    for kp in key_persons:
        if kp.lower() in target_lower or target_lower in kp.lower():
            return "deep_dive", f"key person match: {kp}"

    signals = _get_structural_signals(target_name, db, profile_id)

    # High structural position → deep_dive
    if signals["roles"] >= DEEP_DIVE_MIN_ROLES or signals["connections"] >= DEEP_DIVE_MIN_CONNECTIONS:
        return "deep_dive", (
            f"{signals['roles']} roles, {signals['connections']} connections "
            f"(thresholds: {DEEP_DIVE_MIN_ROLES} roles or {DEEP_DIVE_MIN_CONNECTIONS} connections)"
        )

    # Moderate structural position → standard
    if signals["roles"] >= STANDARD_TIER_MIN_ROLES or signals["connections"] >= STANDARD_TIER_MIN_CONNECTIONS:
        return "standard", (
            f"{signals['roles']} roles, {signals['connections']} connections "
            f"(thresholds: {STANDARD_TIER_MIN_ROLES} roles or {STANDARD_TIER_MIN_CONNECTIONS} connections)"
        )

    # Known address → standard
    for addr in known_addresses:
        # Check if any entity at this address is linked to the target
        has_addr = db.execute(
            """SELECT COUNT(*) FROM entity_addresses ea
               JOIN entity_roles er ON ea.entity_id = er.entity_id
               WHERE ea.address LIKE ? AND er.person_name LIKE ?""",
            (f"%{addr}%", f"%{target_name}%")
        ).fetchone()[0]
        if has_addr:
            return "standard", f"entity at known address: {addr}"

    # Default → scan
    return "scan", (
        f"{signals['roles']} roles, {signals['connections']} connections, "
        f"{signals['findings']} findings — no escalation signals"
    )


def recommend_skill(depth_tier, category):
    """Return the recommended skill for a given depth tier and lead category.

    Unknown categories use the general research skill for the requested depth.
    """
    # Exact match
    key = (depth_tier, category)
    if key in SKILL_RECOMMENDATION:
        return SKILL_RECOMMENDATION[key]

    return "/deep-investigate" if depth_tier == "deep_dive" else "/pursue-lead"


def candidate_overlaps(target_name, db, *, profile_id=None, lead_id=None):
    """Same-target leads need question/scope review; their depth proves no duplication."""
    profile_id = review_profile_id(db, profile_id)
    return [dict(row) for row in db.execute(
        "SELECT id, title, description, category, depth_tier, status FROM leads "
        "WHERE profile_id=? AND target_name=? COLLATE NOCASE "
        "AND status IN ('open','in_progress','pending_triage') AND id IS NOT ? ORDER BY id",
        (profile_id, target_name, lead_id),
    )]


def should_dead_end(target_name, depth_tier, thread_id, db, *, profile_id=None):
    """Compatibility API: structural signals alone cannot justify closing a lead.

    Call candidate_overlaps to inspect questions, then record an explicit reviewed
    disposition through triage-apply. Queue saturation is a scheduling hold, never
    evidence that an investigation question is exhausted.
    """
    overlaps = candidate_overlaps(target_name, db, profile_id=profile_id)
    if overlaps:
        return False, f"Review {len(overlaps)} candidate overlaps for question/scope coverage; do not automatically dead-end"
    return False, ""


def get_thread_priority_boost(thread_id, db, profile_id=None):
    """Calculate priority adjustment based on thread coverage imbalance.

    Returns -1 (lower), 0 (keep), or +1 (raise) relative to other threads.
    """
    if not thread_id:
        return 0
    profile_id = review_profile_id(db, profile_id)
    if not db.execute("SELECT 1 FROM investigation_threads WHERE id=? AND profile_id=?", (thread_id, profile_id)).fetchone():
        raise ValueError("Thread does not belong to the selected profile")

    stats = db.execute(
        """SELECT
            (SELECT COUNT(*) FROM findings WHERE thread_id = ? AND profile_id=?) as my_findings,
            (SELECT AVG(cnt) FROM (
                SELECT COUNT(*) as cnt FROM findings
                WHERE thread_id IS NOT NULL AND profile_id=?
                GROUP BY thread_id
            )) as avg_findings,
            (SELECT COUNT(*) FROM leads
             WHERE thread_id = ? AND profile_id=? AND status IN ('open', 'in_progress')) as my_active
        """,
        (thread_id, profile_id, profile_id, thread_id, profile_id)
    ).fetchone()

    my_findings = stats["my_findings"] or 0
    avg_findings = stats["avg_findings"] or 0
    my_active = stats["my_active"] or 0

    # Starved thread: below average findings AND few active leads
    if my_findings < avg_findings * 0.5 and my_active < 10:
        return 1  # boost

    # Saturated thread: well above average
    if my_findings > avg_findings * 2.0:
        return -1  # lower

    return 0


# ── CLI ──────────────────────────────────────────────────────

def _load_profile_config(profile_id):
    """Load key_persons and known_addresses from the explicitly selected profile."""
    try:
        try:
            from tools.investigation_context import load_profile
        except ImportError:
            from investigation_context import load_profile

        profile = load_profile(profile_id)
        return profile.key_persons or [], profile.known_addresses or {}
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        print(f"WARNING: Could not load active investigation profile: {exc}", file=sys.stderr)
        return [], {}


def cmd_assess(args):
    db = open_review_db(db_path=DB_PATH)
    try:
        profile_id = review_profile_id(db, args.profile)
        key_persons, known_addresses = _load_profile_config(profile_id)
        tier, reason = assess_depth_tier(args.target, db, key_persons, known_addresses, profile_id)
        result = {
            "profile_id": profile_id, "target": args.target,
            "suggested_depth_tier": tier, "recommended_skill": recommend_skill(tier, args.category or "person"),
            "reason": reason, "signals": _get_structural_signals(args.target, db, profile_id),
            "roles_scope": "global shared entity records",
            "candidate_overlaps": candidate_overlaps(args.target, db, profile_id=profile_id, lead_id=args.lead_id),
            "thread_priority_suggestion": get_thread_priority_boost(args.thread_id, db, profile_id),
            "automatic_dead_end": False,
        }
    finally:
        db.close()
    if not write_output(result, args):
        print(json.dumps(result, indent=2))


def cmd_rules(_args):
    print("=== Depth Tier Thresholds ===")
    print(f"  deep_dive: key_person OR roles >= {DEEP_DIVE_MIN_ROLES} OR connections >= {DEEP_DIVE_MIN_CONNECTIONS}")
    print(f"  standard:  roles >= {STANDARD_TIER_MIN_ROLES} OR connections >= {STANDARD_TIER_MIN_CONNECTIONS} OR known_address")
    print("  scan:      default (no escalation signals)")
    print()
    print("=== Skill Recommendation ===")
    for (tier, cat), skill in sorted(SKILL_RECOMMENDATION.items()):
        print(f"  {tier:10} + {cat or 'any':12} -> {skill}")
    print()
    print("Depth thresholds are review suggestions, not caps or evidence of exhaustive coverage.")
    print(f"Review thread scheduling at {THREAD_QUEUE_REVIEW_SIZE}+ active leads; hold only when justified by current workload.")
    print("Same target/depth creates candidate overlaps; distinct questions must remain available.")


def main():
    parser = argparse.ArgumentParser(description="Triage scheduling policy")
    sub = parser.add_subparsers(dest="command")

    assess_p = sub.add_parser("assess", help="Assess a target's depth tier and recommended skill")
    assess_p.add_argument("target", help="Target name to assess")
    assess_p.add_argument("--category", default=None, help="Lead category (person, entity, financial)")
    assess_p.add_argument("--thread-id", type=int, default=None, help="Thread ID for coverage balancing")
    assess_p.add_argument("--lead-id", type=int, help="Exclude the current lead from overlap candidates")
    assess_p.add_argument("--profile", help="Override the pinned/default profile")
    add_output_args(assess_p)

    sub.add_parser("rules", help="Show decision tables and thresholds")

    args = parser.parse_args()
    if args.command == "assess":
        try:
            cmd_assess(args)
        except (ValueError, OSError, sqlite3.Error) as exc:
            parser.exit(1, f"ERROR: {exc}\n")
    elif args.command == "rules":
        cmd_rules(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
