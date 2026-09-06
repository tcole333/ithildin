#!/usr/bin/env python3
"""
Batch lead cleanup — dead-end low-value leads, assign profiles, enrich categories.

Usage:
    python scripts/bulk_lead_cleanup.py scan                        # Preview all changes
    python scripts/bulk_lead_cleanup.py dead-end [--dry-run]        # Aggressive dead-end
    python scripts/bulk_lead_cleanup.py assign-profiles [--status STATUS] [--dry-run]
    python scripts/bulk_lead_cleanup.py enrich-categories [--dry-run] # Infer NULL categories
    python scripts/bulk_lead_cleanup.py stats                       # Before/after summary
"""

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "investigation.db"
INVESTIGATIONS_DIR = PROJECT_ROOT / "investigations"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def _load_all_profiles():
    """Load all investigation profiles and their key_persons/threads."""
    profiles = {}
    try:
        import yaml
    except ImportError:
        print("Warning: PyYAML not installed, profile assignment will be limited", file=sys.stderr)
        return profiles

    for config_path in INVESTIGATIONS_DIR.glob("*/config.yaml"):
        if config_path.parent.name.startswith("_"):
            continue
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            if cfg and cfg.get("name"):
                profiles[cfg["name"]] = {
                    "key_persons": set(p.lower() for p in (cfg.get("key_persons") or [])),
                    "primary_subject": (cfg.get("primary_subject") or "").lower(),
                    "threads": cfg.get("threads") or [],
                }
        except Exception as e:
            print(f"  Warning: could not load {config_path}: {e}", file=sys.stderr)
    return profiles


def _build_thread_profile_map(db):
    """Map thread_id -> profile_id from investigation_threads table."""
    rows = db.execute("SELECT id, profile_id FROM investigation_threads WHERE profile_id IS NOT NULL").fetchall()
    return {row["id"]: row["profile_id"] for row in rows}


# ── Dead-end rules ──────────────────────────────────────────

DEAD_END_RULES = [
    {
        "name": "exact_duplicate_completed",
        "description": "Scan-tier auto-leads that are exact target duplicates of completed leads",
        "reason": "batch_cleanup:exact_duplicate_of_completed",
        "sql": """
            SELECT l.id FROM leads l
            WHERE l.status = 'open'
              AND l.depth_tier = 'scan'
              AND l.source LIKE 'agent:auto_leads%'
              AND l.target_name IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM leads l2
                  WHERE l2.status = 'completed'
                    AND l2.target_name = l.target_name
                    AND l2.depth_tier IN ('standard', 'deep_dive')
              )
        """,
    },
]


def run_dead_end(dry_run=False):
    """Apply all dead-end rules. Returns dict of rule_name -> count."""
    db = get_db()
    now = _utcnow().isoformat()
    results = {}
    total = 0

    for rule in DEAD_END_RULES:
        rows = db.execute(rule["sql"]).fetchall()
        lead_ids = [row["id"] for row in rows]
        results[rule["name"]] = {"count": len(lead_ids), "description": rule["description"]}

        if lead_ids and not dry_run:
            for lid in lead_ids:
                db.execute(
                    """UPDATE leads SET status = 'dead_end', findings = ?, stop_reason = ?,
                       triage_rationale = COALESCE(triage_rationale, ?),
                       updated_at = ?, completed_at = ?
                    WHERE id = ? AND status IN ('open', 'pending_triage')""",
                    (rule["reason"], rule["reason"], rule["reason"], now, now, lid)
                )
            db.commit()

        total += len(lead_ids)
        action = "would dead-end" if dry_run else "dead-ended"
        print(f"  [{rule['name']}] {action} {len(lead_ids)} leads — {rule['description']}")

    if not dry_run:
        db.commit()
    db.close()
    print(f"\nTotal: {total} leads {'would be' if dry_run else ''} dead-ended")
    return results


# ── Profile assignment ──────────────────────────────────────

def run_assign_profiles(dry_run=False, statuses=("open",)):
    """Assign profile_id to NULL-profile leads in the requested statuses."""
    db = get_db()
    profiles = _load_all_profiles()
    thread_map = _build_thread_profile_map(db)

    statuses = tuple(statuses)
    if not statuses:
        raise ValueError("at least one lead status is required")
    placeholders = ",".join("?" for _ in statuses)

    rows = db.execute(
        f"""SELECT id, title, description, target_name, thread_id, source
            FROM leads
            WHERE status IN ({placeholders}) AND profile_id IS NULL""",
        statuses,
    ).fetchall()

    if not rows:
        print(f"No NULL-profile leads found for statuses: {', '.join(statuses)}.")
        db.close()
        return {}

    # Build keyword -> profile mapping from thread keywords and key_persons
    keyword_map = {}  # pattern -> profile_name
    for pname, pdata in profiles.items():
        for person in pdata["key_persons"]:
            # Use last name as keyword (more distinctive than first name)
            parts = person.split()
            if len(parts) >= 2:
                keyword_map[parts[-1].lower()] = pname
        if pdata["primary_subject"]:
            for word in pdata["primary_subject"].split():
                if len(word) > 4:  # skip short common words
                    keyword_map[word.lower()] = pname
        for thread in pdata.get("threads", []):
            for kw in (thread.get("keywords") or []):
                keyword_map[kw.lower()] = pname

    # Profile-specific title keywords (more reliable than generic matching)
    title_keywords = {
        "epstein": ["epstein", "ghislaine", "maxwell", "wexner", "indyke", "dubin", "black stone",
                     "mega group", "deutsche bank", "gratitude america", "rod-larsen"],
        "tech-right": ["doge", "palantir", "anduril", "spacex", "shield ai", "pentagon",
                        "defense tech", "golden dome", "ice ", "dhs ", "immigration enforcement",
                        "musk", "thiel", "luckey", "emil michael", "pete hegseth"],
        "hagee": ["hagee", "cufi", "cornerstone church", "john hagee ministries"],
    }

    assignments = {}  # profile -> count
    now = _utcnow().isoformat()

    for row in rows:
        lead_id = row["id"]
        assigned = None

        # Rule 1: thread_id inheritance
        if row["thread_id"] and row["thread_id"] in thread_map:
            assigned = thread_map[row["thread_id"]]

        # Rule 2: target_name matches key_person
        if not assigned and row["target_name"]:
            target_lower = row["target_name"].lower()
            for pname, pdata in profiles.items():
                if target_lower in pdata["key_persons"]:
                    assigned = pname
                    break

        # Rule 3: title keyword matching
        if not assigned:
            title_lower = (row["title"] or "").lower()
            desc_lower = (row["description"] or "").lower()
            text = f"{title_lower} {desc_lower}"
            for pname, keywords in title_keywords.items():
                for kw in keywords:
                    if kw in text:
                        assigned = pname
                        break
                if assigned:
                    break

        if assigned:
            assignments[assigned] = assignments.get(assigned, 0) + 1
            if not dry_run:
                db.execute(
                    "UPDATE leads SET profile_id = ?, updated_at = ? WHERE id = ?",
                    (assigned, now, lead_id)
                )

    if not dry_run:
        db.commit()
    db.close()

    action = "would assign" if dry_run else "assigned"
    remaining = len(rows) - sum(assignments.values())
    for pname, count in sorted(assignments.items(), key=lambda x: -x[1]):
        print(f"  {action} {count} leads to profile '{pname}'")
    print(f"  {remaining} leads remain unassigned")
    return assignments


# ── Category enrichment ─────────────────────────────────────

CATEGORY_PATTERNS = [
    # (regex_pattern, category) — checked against title
    (r"\b(LLC|Inc|Corp|Ltd|Trust|Foundation|Holdings|Ventures|Partners|Associates)\b", "entity"),
    (r"\bCross-ref (registry|address)", "entity"),
    (r"\bCross-ref officer", "person"),
    (r"\b(SEC |EDGAR|10-K|10-Q|13[FD]|proxy|iXBRL|CIK )", "filing"),
    (r"\b(court|docket|v\.|lawsuit|litigation|complaint|indictment|sentenc)", "legal"),
    (r"\b(contract|procurement|USASpending|award|solicitation|IDIQ|task order)", "contract"),
    (r"\b(FEC|campaign|donor|lobbying|FARA|PAC)\b", "financial"),
    (r"\b(grant|990|nonprofit|EIN |IRS )", "financial"),
    (r"\b(domain|DNS|certificate|IP address|hosting|whois|subdomain)", "digital"),
    (r"\b(FOIA|document|memo|letter|email|report)\b", "document"),
    (r"\b(intelligence|classified|SIGINT|surveillance|wiretap)", "intelligence"),
]


def run_enrich_categories(dry_run=False):
    """Infer categories for NULL-category open leads from title keywords."""
    db = get_db()
    rows = db.execute(
        "SELECT id, title FROM leads WHERE status = 'open' AND (category IS NULL OR category = '')"
    ).fetchall()

    if not rows:
        print("No NULL-category open leads found.")
        db.close()
        return {}

    enriched = {}  # category -> count
    now = _utcnow().isoformat()

    for row in rows:
        title = row["title"] or ""
        matched_cat = None
        for pattern, category in CATEGORY_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                matched_cat = category
                break

        # Fallback: if title contains a person name pattern (First Last), guess person
        if not matched_cat and re.match(r"^(Investigate|Trace|Research|Map|Identify)\s+[A-Z][a-z]+\s+[A-Z][a-z]+", title):
            matched_cat = "person"

        if matched_cat:
            enriched[matched_cat] = enriched.get(matched_cat, 0) + 1
            if not dry_run:
                db.execute(
                    "UPDATE leads SET category = ?, updated_at = ? WHERE id = ?",
                    (matched_cat, now, row["id"])
                )

    if not dry_run:
        db.commit()
    db.close()

    action = "would enrich" if dry_run else "enriched"
    remaining = len(rows) - sum(enriched.values())
    for cat, count in sorted(enriched.items(), key=lambda x: -x[1]):
        print(f"  {action} {count} leads -> {cat}")
    print(f"  {remaining} leads could not be categorized")
    return enriched


# ── Stats ───────────────────────────────────────────────────

def run_stats():
    """Print current lead statistics."""
    db = get_db()
    print("=== Lead Status ===")
    for row in db.execute("SELECT status, COUNT(*) as cnt FROM leads GROUP BY status ORDER BY cnt DESC"):
        print(f"  {row['status']:<16} {row['cnt']:>5}")

    print("\n=== Open by Priority ===")
    for row in db.execute(
        "SELECT priority, COUNT(*) as cnt FROM leads WHERE status='open' GROUP BY priority ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END"
    ):
        print(f"  {row['priority']:<16} {row['cnt']:>5}")

    print("\n=== Open by Profile ===")
    for row in db.execute(
        "SELECT COALESCE(profile_id, '(none)') as p, COUNT(*) as cnt FROM leads WHERE status='open' GROUP BY profile_id ORDER BY cnt DESC"
    ):
        print(f"  {row['p']:<16} {row['cnt']:>5}")

    print("\n=== Open by Category ===")
    for row in db.execute(
        "SELECT COALESCE(category, '(none)') as c, COUNT(*) as cnt FROM leads WHERE status='open' GROUP BY category ORDER BY cnt DESC"
    ):
        print(f"  {row['c']:<16} {row['cnt']:>5}")

    print("\n=== Open by Depth Tier ===")
    for row in db.execute(
        "SELECT COALESCE(depth_tier, '(none)') as t, COUNT(*) as cnt FROM leads WHERE status='open' GROUP BY depth_tier ORDER BY cnt DESC"
    ):
        print(f"  {row['t']:<16} {row['cnt']:>5}")

    db.close()


# ── Scan (preview all) ──────────────────────────────────────

def run_scan():
    """Preview what all operations would do."""
    print("=== Dead-End Preview ===")
    run_dead_end(dry_run=True)
    print("\n=== Profile Assignment Preview ===")
    run_assign_profiles(dry_run=True)
    print("\n=== Category Enrichment Preview ===")
    run_enrich_categories(dry_run=True)


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Batch lead cleanup")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("scan", help="Preview all changes (dry-run everything)")

    dead_p = subparsers.add_parser("dead-end", help="Dead-end low-value leads")
    dead_p.add_argument("--dry-run", action="store_true")

    prof_p = subparsers.add_parser(
        "assign-profiles",
        help="Assign profile_id to NULL-profile leads in an explicit status scope",
    )
    prof_p.add_argument("--dry-run", action="store_true")
    prof_p.add_argument(
        "--status",
        choices=("open", "pending_triage", "all"),
        default="open",
        help="Lead status to process (default: open; all means open + pending_triage)",
    )

    cat_p = subparsers.add_parser("enrich-categories", help="Infer categories for NULL-category leads")
    cat_p.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("stats", help="Print lead statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scan":
        run_scan()
    elif args.command == "dead-end":
        run_dead_end(dry_run=args.dry_run)
    elif args.command == "assign-profiles":
        statuses = ("open", "pending_triage") if args.status == "all" else (args.status,)
        run_assign_profiles(dry_run=args.dry_run, statuses=statuses)
    elif args.command == "enrich-categories":
        run_enrich_categories(dry_run=args.dry_run)
    elif args.command == "stats":
        run_stats()


if __name__ == "__main__":
    main()
