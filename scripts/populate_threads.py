#!/usr/bin/env python3
"""
Classify findings into investigation threads.

Assigns thread_id to all findings currently with NULL thread_id,
based on target_name matching against thread definitions from the
active investigation profile.

Usage:
    uv run python scripts/populate_threads.py --dry-run    # preview assignments
    uv run python scripts/populate_threads.py              # apply assignments
    uv run python scripts/populate_threads.py --stats      # show current assignment counts
"""

import argparse
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "investigation.db"


def _load_thread_defs():
    """Load thread definitions from the active investigation profile."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from tools.investigation_context import get_active_profile
        profile = get_active_profile()
        defs = {}
        for thread in profile.threads:
            tid = thread.get("id")
            if tid is None:
                continue
            defs[tid] = {
                "name": thread.get("name", f"Thread {tid}"),
                "targets": thread.get("targets", []),
                "keywords": thread.get("keywords", []),
            }
        return defs, profile.name
    except Exception:
        return {}, ""


THREAD_DEFS_CACHE = None


def get_thread_defs():
    global THREAD_DEFS_CACHE
    if THREAD_DEFS_CACHE is None:
        THREAD_DEFS_CACHE = _load_thread_defs()
    return THREAD_DEFS_CACHE


_LEGACY_THREAD_DEFS = {
    2: {
        "name": "Mega Group",
        "targets": [
            "wexner", "leslie wexner", "abigail wexner",
            "lauder", "ronald lauder", "estee lauder", "leonard lauder",
            "steinhardt", "michael steinhardt",
            "bronfman", "clare bronfman", "edgar bronfman", "sara bronfman",
            "tisch", "james tisch", "andrew tisch",
            "crown", "lester crown",
            "fisher", "max fisher",
            "lender", "marvin lender",
            "abramson", "leonard abramson",
            "nxivm", "raniere",
            "l brands", "limited brands", "victoria's secret", "victoria secret",
            "wexner foundation",
        ],
        "keywords": [
            r"mega\s*group", r"wexner\s+foundation", r"victoria.s?\s+secret",
            r"l\s+brands", r"bbwi", r"limited\s+brands",
            r"birthright\s+israel", r"steinhardt.*philanthrop",
        ],
    },
    3: {
        "name": "Deutsche Bank Pipeline",
        "targets": [
            "deutsche bank", "db ", "wanek",
            "paul morris", "rm 82289",
        ],
        "keywords": [
            r"deutsche\s+bank", r"\bsar\b.*bank", r"bank\s+compliance",
            r"rm\s*82289", r"wanek", r"nydfs.*consent",
            r"suspicious\s+activity\s+report",
        ],
    },
    4: {
        "name": "Israeli Intelligence Nexus",
        "targets": [
            "ehud barak", "barak",
            "carbyne", "carbyne911",
            "ghislaine maxwell", "robert maxwell",
            "maxwell", "isabel maxwell", "christine maxwell",
            "ari ben-menashe", "ben-menashe",
            "rafi eitan",
            "achrayut", "reporty",
        ],
        "keywords": [
            r"\bmossad\b", r"\bidf\b", r"israel.*intelligence",
            r"carbyne", r"unit\s*8200", r"shin\s*bet",
            r"aman\b", r"military\s+intelligence.*israel",
        ],
    },
    5: {
        "name": "Apollo / Leon Black Financial",
        "targets": [
            "leon black", "black family foundation",
            "leon d. black foundation", "leon d black",
            "debra black",
            "josh harris", "joshua harris",
            "marc rowan",
            "apollo", "apollo global",
            "southern trust", "stc",
            "dechert",
        ],
        "keywords": [
            r"apollo\s+global", r"leon\s+black", r"southern\s+trust",
            r"dechert\s+report", r"\bstc\b.*payment", r"\bstc\b.*transfer",
            r"black.*foundation", r"consulting.*black",
        ],
    },
    6: {
        "name": "Gulf State Operations",
        "targets": [
            "al thani", "sheikh hamad", "qatar",
            "alsabbagh", "al sabbagh",
            "alahmadi", "al ahmadi",
            "broidy", "elliott broidy",
            "george nader",
            "sulayem", "sultan ahmed bin sulayem",
            "tamince", "ali tamince",
            "alrasheed", "faisal al rasheed",
            "ruemmler", "kathy ruemmler", "kathryn ruemmler",
            "hbj", "hamad bin jassim",
        ],
        "keywords": [
            r"qatar", r"\bsaudi\b", r"\buae\b", r"\bemirati\b",
            r"gulf\s+state", r"gulf\s+operation",
            r"radical\s+breakthrough", r"broidy.*nader",
            r"three.tier", r"three-tier",
        ],
    },
}


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def classify_finding(finding, thread_defs):
    """Classify a finding into a thread. Returns (thread_id, method, confidence)."""
    target = (finding["target_name"] or "").lower()
    summary = (finding["summary"] or "").lower()
    detail = (finding["detail"] or "").lower()
    text = f"{summary} {detail}"

    matches = []

    for tid, tdef in thread_defs.items():
        score = 0
        method = None

        # Check target name matches (highest confidence)
        for pattern in tdef["targets"]:
            if pattern.lower() in target:
                score += 10
                method = "target_match"
                break

        # Check keyword matches in text (lower confidence)
        keyword_hits = 0
        for kw in tdef["keywords"]:
            if re.search(kw, text, re.IGNORECASE):
                keyword_hits += 1

        if keyword_hits > 0:
            score += keyword_hits * 2
            if method is None:
                method = "keyword_match"
            else:
                method = "target+keyword"

        if score > 0:
            matches.append((tid, score, method))

    if not matches:
        return None, "unclassified", "none"

    # Sort by score descending, pick highest
    matches.sort(key=lambda x: x[1], reverse=True)
    best_tid, best_score, best_method = matches[0]

    # Ambiguity check: if top two are close, mark as ambiguous
    confidence = "high" if best_method == "target_match" or best_method == "target+keyword" else "medium"
    if len(matches) > 1 and matches[1][1] >= best_score * 0.7:
        confidence = "ambiguous"

    return best_tid, best_method, confidence


def run_classification(dry_run=False):
    """Classify all unassigned findings."""
    db = get_db()

    findings = db.execute("""
        SELECT id, target_name, summary, detail, thread_id
        FROM findings
        WHERE thread_id IS NULL
        ORDER BY id
    """).fetchall()

    print(f"Classifying {len(findings)} findings with NULL thread_id...\n")

    assignments = defaultdict(list)  # thread_id -> list of (finding_id, method, confidence)
    ambiguous = []
    unclassified = []

    # Load thread definitions from profile (with legacy fallback)
    thread_defs, profile_name = get_thread_defs()
    if not thread_defs:
        thread_defs = _LEGACY_THREAD_DEFS

    for f in findings:
        tid, method, confidence = classify_finding(f, thread_defs)

        if tid is None:
            # Default to Thread 1 (Core) for unclassified
            assignments[1].append((f["id"], "default_core", "low"))
            unclassified.append(f["id"])
        elif confidence == "ambiguous":
            ambiguous.append((f["id"], f["target_name"], tid, method))
            assignments[tid].append((f["id"], method, confidence))
        else:
            assignments[tid].append((f["id"], method, confidence))

    # Report — build thread names from profile
    first_thread = thread_defs.get(1, {}).get("name", "Core Network")
    thread_names = {1: first_thread, **{k: v["name"] for k, v in thread_defs.items()}}
    print("Assignment Summary:")
    print("=" * 60)
    for tid in sorted(assignments.keys()):
        name = thread_names.get(tid, f"Thread {tid}")
        items = assignments[tid]
        high = sum(1 for _, _, c in items if c == "high")
        med = sum(1 for _, _, c in items if c == "medium")
        amb = sum(1 for _, _, c in items if c == "ambiguous")
        low = sum(1 for _, _, c in items if c == "low")
        print(f"  Thread {tid} ({name}): {len(items)} findings "
              f"(high={high}, medium={med}, ambiguous={amb}, low={low})")

    print(f"\n  Unclassified (→ Thread 1): {len(unclassified)}")
    print(f"  Ambiguous (assigned to best match): {len(ambiguous)}")

    if ambiguous[:20]:
        print(f"\nAmbiguous cases (first 20):")
        for fid, target, tid, method in ambiguous[:20]:
            print(f"  finding #{fid} [{target}] → Thread {tid} ({method})")

    if dry_run:
        print(f"\n[DRY RUN] No changes written to database.")
        db.close()
        return

    # Apply assignments
    total_updated = 0
    for tid, items in assignments.items():
        for fid, method, confidence in items:
            db.execute("UPDATE findings SET thread_id = ? WHERE id = ?", (tid, fid))
            total_updated += 1

    db.commit()
    print(f"\nUpdated {total_updated} findings with thread assignments.")
    db.close()


def show_stats():
    """Show current thread assignment statistics."""
    db = get_db()

    total = db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    null_thread = db.execute("SELECT COUNT(*) FROM findings WHERE thread_id IS NULL").fetchone()[0]

    print("Thread Assignment Statistics")
    print("=" * 60)
    print(f"  Total findings: {total}")
    print(f"  Unassigned:     {null_thread}")
    print()

    rows = db.execute("""
        SELECT
            COALESCE(t.title, 'Unassigned') as thread_name,
            f.thread_id,
            COUNT(*) as count
        FROM findings f
        LEFT JOIN investigation_threads t ON f.thread_id = t.id
        GROUP BY f.thread_id
        ORDER BY f.thread_id
    """).fetchall()

    for r in rows:
        tid = r["thread_id"] or "NULL"
        print(f"  Thread {tid:<5} {r['thread_name']:<35} {r['count']:>5} findings")

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Classify findings into investigation threads"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview assignments without writing to DB")
    parser.add_argument("--stats", action="store_true",
                        help="Show current thread assignment statistics")

    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        run_classification(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
