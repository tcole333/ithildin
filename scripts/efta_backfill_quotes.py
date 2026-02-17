#!/usr/bin/env python3
"""Backfill source_quote for EFTA evidence rows from DOJ Vol 11 corpus.

For each finding_evidence row where:
  - evidence_type = 'efta'
  - source_quote IS NULL or empty
  - evidence_ref is a single EFTA ID (no commas)

Looks up the EFTA ID in documents.db, parses email chain to extract
body text (skipping headers), and uses first ~300 chars of body.

Modes:
  --dry-run    Show what would be updated without changing DB
  --verify     Compare existing source_quote values against OCR, flag mismatches
  --specific   Backfill for specific finding IDs only (comma-separated)

Priority order: confirmed > high > medium > low (by finding confidence).
"""
import sys
import os
import sqlite3
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.parse_email_chain import parse_email_chain

INVESTIGATION_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "investigation.db")
DOCUMENTS_DB = "/Users/travcole/projects/epstein-docs/output/documents.db"
MAX_QUOTE_LENGTH = 300
CONFIDENCE_ORDER = ["confirmed", "high", "medium", "low", "unverified"]


def extract_body_quote(ocr_text):
    """Extract a meaningful body quote from OCR text, skipping email headers.

    Uses the email chain parser to find the outermost message body.
    Falls back to raw OCR with header stripping if parser fails.
    """
    if not ocr_text or len(ocr_text.strip()) < 10:
        return None

    # Try parsing as email chain
    messages = parse_email_chain(ocr_text)
    if messages and messages[0].body:
        body = messages[0].body.strip()
        if len(body) >= 10:
            return _truncate_quote(body)

    # Fallback: strip obvious email headers from raw text
    text = ocr_text.strip()
    # Remove header block at start
    header_end = 0
    lines = text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith(('from:', 'fran:', 'sent:', 'to:', 'cc:', 'subject:', 'date:')):
            header_end = i + 1
        elif header_end > 0 and not stripped:
            header_end = i + 1  # Skip blank lines after headers
        elif header_end > 0:
            break  # First non-header, non-blank line

    if header_end > 0 and header_end < len(lines):
        body = '\n'.join(lines[header_end:]).strip()
    else:
        body = text

    if len(body) < 10:
        return None

    return _truncate_quote(body)


def _truncate_quote(text):
    """Truncate to MAX_QUOTE_LENGTH at word boundary."""
    # Clean excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {3,}', '  ', text)
    text = text.strip()

    # Remove email footer boilerplate
    for pattern in [
        r'(?:please note|This email and any files|The infor.?ation contained).*$',
        r'(?:conversation-id|date-last-viewed|date-received|flags|gmail-label-ids|remote-id)\s+\d+.*$',
        r'EFTA_R\d+_\d+\s*\nEFTA\d+\s*$',
    ]:
        text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE).strip()

    if len(text) < 10:
        return None

    if len(text) > MAX_QUOTE_LENGTH:
        cut = text[:MAX_QUOTE_LENGTH].rfind(' ')
        if cut > 100:
            text = text[:cut] + "..."
        else:
            text = text[:MAX_QUOTE_LENGTH] + "..."
    return text


def get_rows_to_backfill(inv_db, specific_ids=None):
    """Get EFTA evidence rows missing source_quote, ordered by confidence priority."""
    if specific_ids:
        placeholders = ",".join("?" * len(specific_ids))
        rows = inv_db.execute(f"""
            SELECT fe.rowid, fe.finding_id, fe.evidence_ref, f.confidence, f.claim_type, f.target_name
            FROM finding_evidence fe
            JOIN findings f ON fe.finding_id = f.id
            WHERE fe.evidence_type = 'efta'
              AND (fe.source_quote IS NULL OR fe.source_quote = '')
              AND fe.evidence_ref NOT LIKE '%,%'
              AND fe.evidence_ref LIKE 'EFTA%'
              AND fe.finding_id IN ({placeholders})
            ORDER BY fe.finding_id
        """, specific_ids).fetchall()
    else:
        rows = inv_db.execute("""
            SELECT fe.rowid, fe.finding_id, fe.evidence_ref, f.confidence, f.claim_type, f.target_name
            FROM finding_evidence fe
            JOIN findings f ON fe.finding_id = f.id
            WHERE fe.evidence_type = 'efta'
              AND (fe.source_quote IS NULL OR fe.source_quote = '')
              AND fe.evidence_ref NOT LIKE '%,%'
              AND fe.evidence_ref LIKE 'EFTA%'
            ORDER BY
              CASE f.confidence
                WHEN 'confirmed' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
              END,
              CASE f.claim_type
                WHEN 'direct_quote' THEN 1
                WHEN 'paraphrase' THEN 2
                WHEN 'synthesis' THEN 3
                ELSE 4
              END
        """).fetchall()
    return rows


def cmd_backfill(inv_db, doc_db, dry_run=False, specific_ids=None):
    """Backfill missing source_quotes using email body text."""
    rows = get_rows_to_backfill(inv_db, specific_ids)
    print(f"EFTA Source Quote Backfill (body-aware)")
    print(f"{'=' * 50}")
    print(f"Evidence rows to process: {len(rows)}")

    found = 0
    not_found = 0
    empty_ocr = 0
    updated = 0
    by_confidence = {}

    for row in rows:
        efta_id = row["evidence_ref"].strip()
        doc = doc_db.execute(
            "SELECT ocr_text FROM documents WHERE bates_id = ?", (efta_id,)
        ).fetchone()

        if not doc:
            not_found += 1
            continue

        quote = extract_body_quote(doc["ocr_text"])
        if not quote:
            empty_ocr += 1
            continue

        found += 1
        conf = row["confidence"]
        by_confidence[conf] = by_confidence.get(conf, 0) + 1

        if dry_run:
            if found <= 10:
                starts_with_from = quote.strip().startswith("From:")
                flag = " [HEADER!]" if starts_with_from else ""
                print(f"\n  [DRY RUN] Finding #{row['finding_id']} ({row['target_name']})")
                print(f"    EFTA: {efta_id} | {conf}/{row['claim_type']}")
                print(f"    Quote: {quote[:100]}...{flag}")
        else:
            inv_db.execute(
                "UPDATE finding_evidence SET source_quote = ? WHERE rowid = ?",
                (quote, row["rowid"])
            )
            updated += 1
            if updated % 200 == 0:
                inv_db.commit()
                print(f"  ... {updated} rows updated")

    if not dry_run:
        inv_db.commit()

    print(f"\nResults:")
    print(f"  Documents found in corpus: {found}")
    print(f"  Documents NOT in corpus:   {not_found}")
    print(f"  Empty/unusable OCR text:   {empty_ocr}")
    if dry_run:
        print(f"  Would update: {found} rows")
    else:
        print(f"  Rows updated: {updated}")
    print(f"\nBy confidence level:")
    for conf in CONFIDENCE_ORDER:
        if conf in by_confidence:
            print(f"  {conf}: {by_confidence[conf]}")
    if rows:
        print(f"\nHit rate: {found}/{len(rows)} ({100*found/len(rows):.1f}%)")


def cmd_verify(inv_db, doc_db):
    """Compare existing source_quote values against actual OCR body text."""
    rows = inv_db.execute("""
        SELECT fe.rowid, fe.finding_id, fe.evidence_ref, fe.source_quote,
               f.confidence, f.claim_type, f.target_name
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE fe.evidence_type = 'efta'
          AND fe.source_quote IS NOT NULL AND fe.source_quote != ''
          AND fe.evidence_ref LIKE 'EFTA%'
          AND fe.evidence_ref NOT LIKE '%,%'
    """).fetchall()

    print(f"EFTA Source Quote Verification")
    print(f"{'=' * 50}")
    print(f"Evidence rows to check: {len(rows)}")

    header_only = 0
    mismatches = 0
    ok = 0
    not_in_corpus = 0

    for row in rows:
        current = row["source_quote"]
        efta_id = row["evidence_ref"].strip()

        # Check for header-only quotes
        if current.strip().startswith("From:") or current.strip().startswith("Fran:"):
            header_only += 1
            doc = doc_db.execute(
                "SELECT ocr_text FROM documents WHERE bates_id = ?", (efta_id,)
            ).fetchone()
            if doc:
                better = extract_body_quote(doc["ocr_text"])
                if better and not better.strip().startswith("From:"):
                    if header_only <= 5:
                        print(f"\n  [HEADER] #{row['finding_id']} ({row['target_name']})")
                        print(f"    Current: {current[:60]}...")
                        print(f"    Better:  {better[:60]}...")
            continue

        # For non-header quotes, verify they appear in the OCR
        doc = doc_db.execute(
            "SELECT ocr_text FROM documents WHERE bates_id = ?", (efta_id,)
        ).fetchone()
        if not doc or not doc["ocr_text"]:
            not_in_corpus += 1
            continue

        ocr_norm = re.sub(r'\s+', ' ', (doc["ocr_text"] or "").lower())
        quote_norm = re.sub(r'\s+', ' ', current[:80].lower())
        if quote_norm in ocr_norm:
            ok += 1
        else:
            mismatches += 1

    print(f"\nResults:")
    print(f"  OK (quote found in OCR): {ok}")
    print(f"  Header-only quotes: {header_only}")
    print(f"  Quote not in OCR: {mismatches}")
    print(f"  EFTA not in corpus: {not_in_corpus}")


def main():
    dry_run = "--dry-run" in sys.argv
    verify_mode = "--verify" in sys.argv
    specific_ids = None

    for arg in sys.argv[1:]:
        if arg.startswith("--specific="):
            specific_ids = [int(x) for x in arg.split("=", 1)[1].split(",")]

    inv_db = sqlite3.connect(INVESTIGATION_DB)
    inv_db.row_factory = sqlite3.Row
    doc_db = sqlite3.connect(DOCUMENTS_DB)
    doc_db.row_factory = sqlite3.Row

    if verify_mode:
        cmd_verify(inv_db, doc_db)
    else:
        cmd_backfill(inv_db, doc_db, dry_run=dry_run, specific_ids=specific_ids)

    inv_db.close()
    doc_db.close()


if __name__ == "__main__":
    main()
