#!/usr/bin/env python3
"""Batch confidence calibration: enforce claim_type → max confidence rules.

Rules:
  direct_quote  → can be confirmed
  paraphrase    → max high
  inference     → max medium
  synthesis     → max medium
  user_provided → as specified (no change)

Each correction is recorded in the corrections table via update_finding().
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.findings_tracker import update_finding
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "investigation.db")

# claim_type -> max allowed confidence (ordered: confirmed > high > medium > low > unverified)
CONFIDENCE_ORDER = ["unverified", "low", "medium", "high", "confirmed"]
MAX_CONFIDENCE = {
    "paraphrase": "high",
    "synthesis": "medium",
    "inference": "medium",
}

def get_violations():
    """Find all findings that violate claim_type → max confidence rules."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    violations = []
    for claim_type, max_conf in MAX_CONFIDENCE.items():
        max_idx = CONFIDENCE_ORDER.index(max_conf)
        # Find findings where confidence is higher than allowed
        higher_confs = CONFIDENCE_ORDER[max_idx + 1:]
        if not higher_confs:
            continue
        placeholders = ",".join("?" * len(higher_confs))
        rows = db.execute(
            f"SELECT id, target_name, claim_type, confidence FROM findings "
            f"WHERE claim_type = ? AND confidence IN ({placeholders})",
            [claim_type] + higher_confs
        ).fetchall()
        for row in rows:
            violations.append({
                "id": row["id"],
                "target_name": row["target_name"],
                "claim_type": row["claim_type"],
                "current": row["confidence"],
                "corrected_to": max_conf,
            })
    db.close()
    return violations


def apply_corrections(violations, dry_run=False):
    """Apply confidence corrections with audit trail."""
    stats = {"paraphrase": 0, "synthesis": 0, "inference": 0}
    errors = []

    for v in violations:
        reason = (
            f"Confidence calibration: {v['claim_type']} claim_type has max "
            f"confidence '{v['corrected_to']}', was '{v['current']}'"
        )
        if dry_run:
            print(f"  [DRY RUN] #{v['id']} ({v['target_name']}): "
                  f"{v['claim_type']}/{v['current']} -> {v['corrected_to']}")
        else:
            ok = update_finding(
                v["id"], "confidence", v["corrected_to"],
                reason=reason,
                correction_type="refinement",
                corrected_by="confidence_calibration_audit"
            )
            if ok:
                stats[v["claim_type"]] += 1
            else:
                errors.append(v["id"])

    return stats, errors


def main():
    dry_run = "--dry-run" in sys.argv
    violations = get_violations()

    print(f"Confidence calibration audit")
    print(f"{'=' * 50}")
    print(f"Total violations found: {len(violations)}")
    print()

    # Summary by type
    by_type = {}
    for v in violations:
        key = f"{v['claim_type']}: {v['current']} -> {v['corrected_to']}"
        by_type[key] = by_type.get(key, 0) + 1
    for key, count in sorted(by_type.items()):
        print(f"  {key}: {count}")
    print()

    if dry_run:
        print("DRY RUN mode — no changes applied")
        print()
        for v in violations[:20]:
            print(f"  #{v['id']} ({v['target_name']}): "
                  f"{v['claim_type']}/{v['current']} -> {v['corrected_to']}")
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")
        return

    if not violations:
        print("No violations found. All findings comply with confidence rules.")
        return

    print(f"Applying {len(violations)} corrections...")
    stats, errors = apply_corrections(violations)
    print()
    print(f"Results:")
    for claim_type, count in stats.items():
        if count > 0:
            print(f"  {claim_type}: {count} corrected")
    if errors:
        print(f"  ERRORS: {len(errors)} findings could not be updated: {errors}")
    print(f"\nTotal corrected: {sum(stats.values())}")
    print(f"All corrections recorded in corrections table with type='refinement'")


if __name__ == "__main__":
    main()
