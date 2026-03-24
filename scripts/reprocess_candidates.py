#!/usr/bin/env python3
"""
Score completed leads for reprocessing value based on structural signals.

Identifies which completed investigations would benefit most from running
improved/new skills that were added after the original investigation.

Scoring is based on entity type, finding content keywords, connection count,
and key person status — NOT search_log (which may have inconsistent data).

Usage:
    python scripts/reprocess_candidates.py scan                 # Ranked report
    python scripts/reprocess_candidates.py create --top 15      # Create reprocessing leads
    python scripts/reprocess_candidates.py create --skill trace-grants  # Specific skill gap
"""

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "investigation.db"
INVESTIGATIONS_DIR = PROJECT_ROOT / "investigations"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def _load_key_persons():
    """Load key_persons from all investigation profiles."""
    key_persons = {}  # person_name -> profile_name
    try:
        import yaml
    except ImportError:
        return key_persons

    for config_path in INVESTIGATIONS_DIR.glob("*/config.yaml"):
        if config_path.parent.name.startswith("_"):
            continue
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            if cfg and cfg.get("name"):
                for person in (cfg.get("key_persons") or []):
                    key_persons[person.lower()] = cfg["name"]
        except Exception:
            pass
    return key_persons


# ── Scoring ─────────────────────────────────────────────────

NONPROFIT_KEYWORDS = {"foundation", "trust", "fund", "institute", "association",
                      "society", "alliance", "coalition", "council", "center",
                      "charity", "ministries"}


def _get_finding_text(db, target_name):
    """Get concatenated finding content for keyword analysis."""
    rows = db.execute(
        "SELECT summary, detail FROM findings WHERE target_name = ? LIMIT 50",
        (target_name,)
    ).fetchall()
    return " ".join((row["summary"] or "") + " " + (row["detail"] or "") for row in rows).lower()


def score_target(db, target_name, finding_count, connection_count, key_persons):
    """Score a completed target for reprocessing value.

    Scoring is based on structural signals — entity type, finding content
    keywords, connection count, and key person status.
    """
    score = 0
    gaps = []

    target_lower = target_name.lower()
    finding_text = _get_finding_text(db, target_name)

    # Is this a key person? (+3)
    if target_lower in key_persons:
        score += 3
        gaps.append(f"key_person({key_persons[target_lower]})")

    # High connection count — structurally important (+2)
    if connection_count >= 10:
        score += 2
        gaps.append(f"high_connectivity({connection_count})")

    # Nonprofit/foundation — could benefit from /trace-grants (+2)
    is_nonprofit = any(kw in target_lower for kw in NONPROFIT_KEYWORDS)
    is_nonprofit = is_nonprofit or any(kw in finding_text for kw in ["nonprofit", "501(c)", "ein ", "irs 990", "tax-exempt", "grant"])
    if is_nonprofit:
        score += 2
        gaps.append("nonprofit_entity")

    # Public company indicators — could benefit from /analyze-filing, /screen-targets (+2)
    is_public = any(kw in finding_text for kw in ["stock", "ticker", "nasdaq", "nyse", "10-k", "sec filing", "cik", "market cap"])
    if is_public:
        score += 2
        gaps.append("public_company")

    # Government contract indicators — could benefit from /audit-contracts (+2)
    has_govt = any(kw in finding_text for kw in ["government contract", "defense contract", "federal award",
                                                  "usaspending", "dod contract", "procurement", "pentagon"])
    if has_govt:
        score += 2
        gaps.append("govt_contractor")

    # Litigation indicators — could benefit from rebuilt /analyze-case (+2)
    has_legal = any(kw in finding_text for kw in ["lawsuit", "indictment", "defendant", "plaintiff",
                                                   "docket", "complaint", "settlement", "sentenc"])
    if has_legal:
        score += 2
        gaps.append("litigation_history")

    # Has open leads referencing same target (+1)
    open_count = db.execute(
        "SELECT COUNT(*) FROM leads WHERE status = 'open' AND target_name = ?",
        (target_name,)
    ).fetchone()[0]
    if open_count > 0:
        score += 1
        gaps.append(f"open_leads({open_count})")

    # High finding count bonus (structural importance) (+1)
    if finding_count >= 20:
        score += 1
        gaps.append(f"high_findings({finding_count})")

    return score, gaps


def _infer_category(gaps):
    """Infer lead category from identified gaps."""
    gap_names = [g.split("(")[0] for g in gaps]
    if "nonprofit_entity" in gap_names:
        return "entity"
    if "govt_contractor" in gap_names:
        return "contract"
    if "public_company" in gap_names:
        return "financial"
    if "litigation_history" in gap_names:
        return "legal"
    return "person"


# ── Scan ────────────────────────────────────────────────────

def run_scan():
    """Scan completed leads and produce ranked reprocessing report."""
    db = get_db()
    key_persons = _load_key_persons()

    # Get all completed leads with distinct target_names
    rows = db.execute("""
        SELECT DISTINCT l.target_name,
            COUNT(DISTINCT f.id) as finding_count,
            (SELECT COUNT(DISTINCT c.id) FROM connections c
             WHERE c.person_a = l.target_name OR c.person_b = l.target_name) as conn_count,
            GROUP_CONCAT(DISTINCT l.id) as lead_ids
        FROM leads l
        LEFT JOIN findings f ON f.target_name = l.target_name
        WHERE l.status = 'completed' AND l.target_name IS NOT NULL
        GROUP BY l.target_name
        ORDER BY finding_count DESC
    """).fetchall()

    candidates = []
    for row in rows:
        target = row["target_name"]
        score, gaps = score_target(db, target, row["finding_count"], row["conn_count"], key_persons)
        if score > 0:
            candidates.append({
                "target_name": target,
                "score": score,
                "finding_count": row["finding_count"],
                "connection_count": row["conn_count"],
                "gaps": gaps,
                "category": _infer_category(gaps),
                "lead_ids": row["lead_ids"],
            })

    candidates.sort(key=lambda x: (-x["score"], -x["finding_count"]))
    db.close()

    # Print report
    print(f"{'Rank':<5} {'Score':<6} {'Findings':<9} {'Conns':<6} {'Target':<35} {'Category':<12} {'Gaps'}")
    print("-" * 120)
    for i, c in enumerate(candidates, 1):
        gap_str = ", ".join(c["gaps"])
        name = c["target_name"][:34]
        print(f"{i:<5} {c['score']:<6} {c['finding_count']:<9} {c['connection_count']:<6} {name:<35} {c['category']:<12} {gap_str}")

    print(f"\n{len(candidates)} candidates scored (out of {len(rows)} completed targets)")
    return candidates


# ── Create reprocessing leads ───────────────────────────────

def run_create(candidates, top_n=None, skill_filter=None):
    """Create reprocessing leads for top candidates."""
    if skill_filter:
        candidates = [c for c in candidates if c["category"] == skill_filter]
        print(f"Filtered to {len(candidates)} candidates for category {skill_filter}")

    if top_n:
        candidates = candidates[:top_n]

    if not candidates:
        print("No candidates to create leads for.")
        return

    db = get_db()
    now = _utcnow().isoformat()
    created = 0

    for c in candidates:
        # Check for existing reprocessing lead
        existing = db.execute(
            "SELECT 1 FROM leads WHERE source = 'reprocessing:skill_upgrade' AND target_name = ?",
            (c["target_name"],)
        ).fetchone()
        if existing:
            print(f"  Skip {c['target_name']} — reprocessing lead already exists")
            continue

        gap_str = ", ".join(c["gaps"])
        description = (
            f"Reprocess with improved tooling. Gaps: {gap_str}. "
            f"Original investigation: lead(s) #{c['lead_ids']}. "
            f"Findings: {c['finding_count']}, connections: {c['connection_count']}."
        )

        # Determine priority from score
        if c["score"] >= 8:
            priority = "high"
        elif c["score"] >= 5:
            priority = "medium"
        else:
            priority = "low"

        category = c["category"]

        cursor = db.execute(
            """INSERT INTO leads (title, description, category, priority, source, target_name,
                depth_tier, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, 'reprocessing:skill_upgrade', ?, 'standard', ?, ?, 'open')""",
            (
                f"Reprocess: {c['target_name']}",
                description,
                category,
                priority,
                c["target_name"],
                now,
                now,
            )
        )
        new_lead_id = cursor.lastrowid

        # Link to original completed lead(s)
        for orig_id in c["lead_ids"].split(","):
            try:
                db.execute(
                    "INSERT OR IGNORE INTO lead_relations (lead_id, related_lead_id, relation_type) VALUES (?, ?, 'reprocessing')",
                    (new_lead_id, int(orig_id.strip()))
                )
            except (ValueError, sqlite3.IntegrityError):
                pass

        created += 1
        print(f"  Created lead #{new_lead_id}: {c['target_name']} (score={c['score']}, category={category})")

    db.commit()
    db.close()
    print(f"\nCreated {created} reprocessing leads")


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Score completed leads for reprocessing")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("scan", help="Produce ranked reprocessing report")

    create_p = subparsers.add_parser("create", help="Create reprocessing leads")
    create_p.add_argument("--top", type=int, help="Create leads for top N candidates")
    create_p.add_argument("--category", help="Filter to specific category (e.g., entity, legal, contract)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scan":
        run_scan()
    elif args.command == "create":
        candidates = run_scan()
        print("\n--- Creating leads ---\n")
        run_create(candidates, top_n=args.top, skill_filter=getattr(args, "category", None))


if __name__ == "__main__":
    main()
