#!/usr/bin/env python3
"""Reset worker-asserted findings.verification_status values to 'unverified'.

Dispatcher imports before 2026-07 stored worker-supplied verification_status
verbatim (scripts/dispatcher.py import_findings) — the same unvalidated-ingress
hole that produced the comma-joined source_datasets strings fixed by
migrate_source_datasets_json.py. Two damage classes, both from the 2026-03/04
staged-worker era (altman/hfia/allbirds/feeding-our-future/manosphere):

  * invalid vocabulary — values outside VALID_VERIFICATION ('confirmed',
    'corroborated', 'high', 'inference'): confidence/claim-type vocabulary
    leaking into the status column. Every affected row already carries a
    valid confidence value, so resetting the status loses no information;
    the stray label is preserved in the corrections row.
  * unstamped 'verified' — valid vocabulary, but verified_by and verified_at
    are NULL. findings_tracker stamps both inside verify_finding's evidence
    gates and add_finding always inserts 'unverified', so an unstamped
    'verified' can only be a worker self-assertion stored verbatim.

Both classes reset to 'unverified': verification is a reviewed state granted
through `findings_tracker.py verify`, never assertable at import time.
confidence, claim_type, and profile_id are untouched. A corrections row per
finding is written in the same transaction with correction_type='refinement',
mirroring _invalidate_verified_finding's verified->unverified reset.

Dry-run by default:
    uv run python scripts/migrate_verification_status.py [--db PATH] [--apply] [--report PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.findings_tracker import VALID_VERIFICATION  # noqa: E402

DEFAULT_DB_PATH = Path(os.environ.get("ITHILDIN_DB_PATH") or PROJECT_ROOT / "investigation.db")
CORRECTED_BY = "migration:migrate_verification_status"
REASONS = {
    "invalid_vocabulary": (
        "Reset invalid verification_status to 'unverified': 2026-03/04 dispatcher "
        "imports stored worker-supplied status verbatim, and this value is "
        "confidence/claim-type vocabulary, not a verification state (the "
        "confidence column already holds the row's confidence)"
    ),
    "unstamped_verified": (
        "Reset self-asserted 'verified' to 'unverified': verified_by/verified_at "
        "are NULL, so the status never passed findings_tracker verify gates "
        "(2026-03/04 dispatcher imports stored worker-supplied status verbatim)"
    ),
}


def classify_row(row: sqlite3.Row) -> str | None:
    """Damage class for a finding, or None when its status is legitimate."""
    status = row["verification_status"]
    if status is None or not str(status).strip() or status not in VALID_VERIFICATION:
        return "invalid_vocabulary"
    if status == "verified" and row["verified_by"] is None and row["verified_at"] is None:
        return "unstamped_verified"
    return None


def find_affected_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    placeholders = ", ".join("?" for _ in VALID_VERIFICATION)
    rows = db.execute(
        "SELECT id, profile_id, verification_status, verified_by, verified_at, "
        "       confidence, claim_type "
        "FROM findings "
        "WHERE verification_status IS NULL "
        "   OR TRIM(verification_status) = '' "
        f"   OR verification_status NOT IN ({placeholders}) "
        "   OR (verification_status = 'verified' "
        "       AND verified_by IS NULL AND verified_at IS NULL) "
        "ORDER BY id",
        VALID_VERIFICATION,
    ).fetchall()
    return [row for row in rows if classify_row(row) is not None]


def migrate(db_path: Path, apply: bool) -> dict:
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")

    summary: dict = {
        "db": str(db_path),
        "applied": apply,
        "updated": 0,
        "skipped_concurrent": 0,
        "by_class": Counter(),
        "by_profile": Counter(),
        "by_old_value": Counter(),
        "status_vs_confidence": Counter(),
        "rows": [],
    }

    try:
        affected = find_affected_rows(db)
        summary["affected"] = len(affected)

        if apply:
            db.execute("BEGIN IMMEDIATE")

        for row in affected:
            damage_class = classify_row(row)
            old_value = row["verification_status"]

            if apply:
                # `IS ?` (not `= ?`) so a NULL old value still matches; the
                # stamp guard keeps a concurrently verified row untouched.
                cursor = db.execute(
                    "UPDATE findings SET verification_status = 'unverified' "
                    "WHERE id = ? AND verification_status IS ? "
                    "  AND verified_by IS NULL AND verified_at IS NULL",
                    (row["id"], old_value),
                )
                if cursor.rowcount != 1:
                    summary["skipped_concurrent"] += 1
                    continue
                db.execute(
                    """
                    INSERT INTO corrections (table_name, record_id, field_name,
                                             old_value, new_value, reason,
                                             corrected_by, correction_type)
                    VALUES ('findings', ?, 'verification_status', ?, 'unverified',
                            ?, ?, 'refinement')
                    """,
                    (row["id"], old_value, REASONS[damage_class], CORRECTED_BY),
                )

            summary["rows"].append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "class": damage_class,
                    "old": old_value,
                    "confidence": row["confidence"],
                    "claim_type": row["claim_type"],
                }
            )
            summary["by_class"][damage_class] += 1
            summary["by_profile"][row["profile_id"] or ""] += 1
            summary["by_old_value"][old_value or ""] += 1
            if damage_class == "invalid_vocabulary":
                summary["status_vs_confidence"][
                    f"{old_value} (confidence={row['confidence']}, {row['claim_type']})"
                ] += 1
            summary["updated"] += 1

        if apply:
            db.commit()
    except Exception:
        if apply:
            db.rollback()
        raise
    finally:
        db.close()

    for key in ("by_class", "by_profile", "by_old_value", "status_vs_confidence"):
        summary[key] = dict(sorted(summary[key].items(), key=lambda kv: -kv[1]))
    return summary


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description="Reset worker-asserted findings.verification_status to 'unverified'"
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB_PATH,
        help=f"Path to investigation database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write changes (default is a dry run that only reports)",
    )
    parser.add_argument(
        "--report", type=Path, default=None,
        help="Optional path for a full JSON report (per-row detail)",
    )
    args = parser.parse_args(argv)

    if not args.db.exists():
        parser.error(f"Database not found: {args.db}")

    summary = migrate(args.db, apply=args.apply)

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"[{mode}] {summary['affected']} findings with worker-asserted verification_status")
    print(f"  reset to 'unverified': {summary['updated']}")
    if summary["skipped_concurrent"]:
        print(f"  skipped (concurrent change): {summary['skipped_concurrent']}")
    print(f"  by class: {summary['by_class']}")
    print(f"  by profile: {summary['by_profile']}")
    print(f"  by old value: {summary['by_old_value']}")
    print("  invalid vocabulary vs stored confidence:")
    for combo, count in summary["status_vs_confidence"].items():
        print(f"    {combo}: {count}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2))
        print(f"  full report: {args.report}")

    return summary


if __name__ == "__main__":
    main()
