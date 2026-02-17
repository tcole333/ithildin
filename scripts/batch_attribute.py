#!/usr/bin/env python3
"""Batch attribution: populate email_sender, email_date, chain_position
on finding_evidence rows for EFTA-type evidence.

For each EFTA evidence row with source_quote but no email_sender:
1. Look up EFTA in documents.db
2. Parse email chain
3. Match source_quote against parsed messages
4. Populate attribution columns
5. Record changes in corrections table

Usage:
    python scripts/batch_attribute.py --dry-run
    python scripts/batch_attribute.py
    python scripts/batch_attribute.py --limit 100
"""
import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.parse_email_chain import parse_email_chain

INVESTIGATION_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "investigation.db")
DOCUMENTS_DB = "/Users/travcole/projects/epstein-docs/output/documents.db"


def _normalize(text):
    """Normalize text for matching."""
    if not text:
        return ""
    text = re.sub(r'=\n', '', text)
    text = re.sub(r'=br>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def get_rows_to_attribute(inv_db, limit=None):
    """Get EFTA evidence rows with source_quote but no email_sender."""
    query = """
        SELECT fe.rowid as fe_rowid, fe.finding_id, fe.evidence_ref,
               fe.source_quote, f.target_name, f.claim_type, f.confidence
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE fe.evidence_type = 'efta'
          AND fe.source_quote IS NOT NULL AND fe.source_quote != ''
          AND (fe.email_sender IS NULL OR fe.email_sender = '')
          AND fe.evidence_ref LIKE 'EFTA%'
          AND fe.evidence_ref NOT LIKE '%,%'
        ORDER BY
            CASE f.claim_type
                WHEN 'direct_quote' THEN 1 WHEN 'paraphrase' THEN 2
                WHEN 'synthesis' THEN 3 ELSE 4
            END,
            CASE f.confidence
                WHEN 'confirmed' THEN 1 WHEN 'high' THEN 2
                WHEN 'medium' THEN 3 ELSE 4
            END
    """
    if limit:
        query += f" LIMIT {limit}"
    return inv_db.execute(query).fetchall()


def match_quote_to_message(messages, source_quote):
    """Find which parsed message contains the source_quote."""
    quote_norm = _normalize(source_quote)
    if not quote_norm or len(quote_norm) < 10:
        return None

    for msg in messages:
        body_norm = _normalize(msg.body)
        subj_norm = _normalize(msg.subject)
        raw_norm = _normalize(msg.raw_text)

        if quote_norm[:40] in body_norm or quote_norm[:40] in raw_norm:
            return msg
        if quote_norm[:40] in subj_norm:
            return msg

    # Fallback: try outermost message
    if messages:
        return messages[0]
    return None


def main():
    parser = argparse.ArgumentParser(description="Batch email attribution for EFTA evidence")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, help="Max rows to process")
    args = parser.parse_args()

    inv_db = sqlite3.connect(INVESTIGATION_DB)
    inv_db.row_factory = sqlite3.Row
    inv_db.execute("PRAGMA journal_mode=WAL")
    inv_db.execute("PRAGMA busy_timeout=5000")

    doc_db = sqlite3.connect(DOCUMENTS_DB)
    doc_db.row_factory = sqlite3.Row

    rows = get_rows_to_attribute(inv_db, limit=args.limit)
    print(f"Batch Email Attribution")
    print(f"{'=' * 50}")
    print(f"Evidence rows to process: {len(rows)}")

    attributed = 0
    not_found = 0
    no_parse = 0
    no_match = 0
    errors = 0

    for row in rows:
        efta_id = row["evidence_ref"].strip()
        doc = doc_db.execute(
            "SELECT ocr_text FROM documents WHERE bates_id = ?", (efta_id,)
        ).fetchone()

        if not doc or not doc["ocr_text"]:
            not_found += 1
            continue

        messages = parse_email_chain(doc["ocr_text"])
        if not messages:
            no_parse += 1
            continue

        msg = match_quote_to_message(messages, row["source_quote"])
        if not msg or not msg.sender:
            no_match += 1
            continue

        sender = msg.sender
        date = msg.date
        position = msg.chain_position

        if args.dry_run:
            if attributed < 10:
                recip = ", ".join(msg.recipients) if msg.recipients else "(unknown)"
                print(f"\n  [DRY RUN] #{row['finding_id']} ({row['target_name']})")
                print(f"    EFTA: {efta_id}")
                print(f"    Sender: {sender} -> {recip}")
                print(f"    Date: {date}")
                print(f"    Chain position: {position}")
            attributed += 1
        else:
            try:
                inv_db.execute("""
                    UPDATE finding_evidence
                    SET email_sender = ?, email_date = ?, chain_position = ?
                    WHERE rowid = ?
                """, (sender, date, position, row["fe_rowid"]))

                # Record in corrections table
                inv_db.execute("""
                    INSERT INTO corrections (table_name, record_id, field_name,
                                            old_value, new_value, reason,
                                            corrected_by, correction_type)
                    VALUES ('finding_evidence', ?, 'email_sender', NULL, ?, ?,
                            'batch_attribute', 'refinement')
                """, (row["finding_id"],
                      f"{sender} ({date})",
                      f"Auto-attributed via email chain parser for {efta_id}"))

                attributed += 1
                if attributed % 200 == 0:
                    inv_db.commit()
                    print(f"  ... {attributed} rows attributed")
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  ERROR on #{row['finding_id']}: {e}")

    if not args.dry_run:
        inv_db.commit()

    print(f"\nResults:")
    print(f"  Attributed: {attributed}")
    print(f"  EFTA not in corpus: {not_found}")
    print(f"  Could not parse: {no_parse}")
    print(f"  No quote match: {no_match}")
    if errors:
        print(f"  Errors: {errors}")
    if args.dry_run:
        print(f"\n  (dry run — no changes applied)")

    inv_db.close()
    doc_db.close()


if __name__ == "__main__":
    main()
