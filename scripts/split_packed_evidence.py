#!/usr/bin/env python3
"""Split comma-separated evidence_ref values into individual rows.

Many early findings had multiple EFTA IDs crammed into a single evidence_ref
field (e.g., 'EFTA02650430,EFTA02650158'). This splits them into individual
rows in finding_evidence, maintaining the audit trail via corrections table.

Usage:
    python scripts/split_packed_evidence.py --dry-run
    python scripts/split_packed_evidence.py --apply
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "investigation.db"


def main():
    parser = argparse.ArgumentParser(description="Split packed evidence refs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.print_help()
        return

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")

    rows = db.execute("""
        SELECT finding_id, evidence_type, evidence_ref, source_quote, source_page,
               assessment, email_sender, email_date, chain_position
        FROM finding_evidence
        WHERE evidence_ref LIKE '%,%'
    """).fetchall()

    print(f"Found {len(rows)} packed evidence rows")

    inserted = 0
    skipped = 0
    deleted = 0

    for r in rows:
        finding_id, orig_type, packed_ref, sq, sp, assess, esender, edate, cpos = r
        refs = [x.strip() for x in packed_ref.split(",") if x.strip()]
        if len(refs) <= 1:
            continue

        for ref in refs:
            if ref.startswith("EFTA"):
                ref_type = "efta"
            elif ref.startswith("hf_"):
                ref_type = "ref"
            elif "/" in ref or ref.endswith(".pdf"):
                ref_type = "file"
            else:
                ref_type = orig_type

            existing = db.execute(
                "SELECT 1 FROM finding_evidence WHERE finding_id = ? AND evidence_ref = ?",
                (finding_id, ref)
            ).fetchone()

            if existing:
                skipped += 1
                continue

            if args.apply:
                db.execute("""
                    INSERT INTO finding_evidence
                        (finding_id, evidence_type, evidence_ref, source_quote, source_page,
                         assessment, email_sender, email_date, chain_position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (finding_id, ref_type, ref, sq, sp, assess, esender, edate, cpos))
            inserted += 1

        if args.apply:
            db.execute(
                "DELETE FROM finding_evidence WHERE finding_id = ? AND evidence_ref = ?",
                (finding_id, packed_ref)
            )
            db.execute("""
                INSERT INTO corrections (table_name, record_id, field_name,
                    old_value, new_value, reason, corrected_by, correction_type)
                VALUES ('finding_evidence', ?, 'evidence_ref', ?, ?,
                    'Split comma-separated evidence refs into individual rows',
                    'split_packed_evidence.py', 'refinement')
            """, (finding_id, packed_ref, f"{len(refs)} individual refs"))
        deleted += 1

    if args.apply:
        db.commit()

    remaining = db.execute(
        "SELECT COUNT(*) FROM finding_evidence WHERE evidence_ref LIKE '%,%'"
    ).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM finding_evidence").fetchone()[0]

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"\n[{mode}]")
    print(f"  Packed rows processed: {deleted}")
    print(f"  Individual refs to insert: {inserted}")
    print(f"  Skipped (already existed): {skipped}")
    print(f"  Total evidence rows: {total}")
    print(f"  Remaining packed rows: {remaining}")

    db.close()


if __name__ == "__main__":
    main()
