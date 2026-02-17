#!/usr/bin/env python3
"""Evidence integrity audit for investigation.db.

Detects misattributions, missing quotes, duplicate findings, and
confidence violations. Pattern: detect-then-apply with dry-run support
and corrections table integration (see confidence_calibration.py).

Subcommands:
    missing-quotes         Evidence rows lacking source_quote, prioritized
    overlap-detection      EFTA IDs cited by 3+ findings, Jaccard similarity
    cross-check            Verify source_quote appears in actual OCR text
    confidence-violations  direct_quote/confirmed without any source_quote
    report                 Aggregate summary of all checks
"""
import argparse
import re
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INVESTIGATION_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "investigation.db")
DOCUMENTS_DB = "/Users/travcole/projects/epstein-docs/output/documents.db"

CONFIDENCE_ORDER = ["confirmed", "high", "medium", "low", "unverified"]
CLAIM_TYPE_ORDER = ["direct_quote", "paraphrase", "synthesis", "inference"]


def get_inv_db():
    db = sqlite3.connect(INVESTIGATION_DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def get_doc_db():
    db = sqlite3.connect(DOCUMENTS_DB)
    db.row_factory = sqlite3.Row
    return db


# ── Helpers ──────────────────────────────────────────────────

def jaccard_tokens(text_a, text_b):
    """Jaccard similarity on lowercased word tokens, stop words removed."""
    stop = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "was", "were", "are",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "shall",
            "this", "that", "these", "those", "it", "its", "as", "not", "no"}
    tokens_a = {w for w in re.findall(r'\w+', text_a.lower()) if w not in stop and len(w) > 2}
    tokens_b = {w for w in re.findall(r'\w+', text_b.lower()) if w not in stop and len(w) > 2}
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def normalize_ocr(text):
    """Normalize OCR artifacts for comparison."""
    if not text:
        return ""
    # Quoted-Printable continuation (=\n)
    text = re.sub(r'=\n', '', text)
    # HTML remnants
    text = re.sub(r'=br>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


# ── Subcommands ──────────────────────────────────────────────

def cmd_missing_quotes(args):
    """Find evidence rows where source_quote IS NULL, prioritized."""
    db = get_inv_db()
    rows = db.execute("""
        SELECT fe.rowid as fe_rowid, fe.finding_id, fe.evidence_type, fe.evidence_ref,
               f.claim_type, f.confidence, f.target_name, f.summary
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE (fe.source_quote IS NULL OR fe.source_quote = '')
        ORDER BY
            CASE f.claim_type
                WHEN 'direct_quote' THEN 1 WHEN 'paraphrase' THEN 2
                WHEN 'synthesis' THEN 3 WHEN 'inference' THEN 4 ELSE 5
            END,
            CASE f.confidence
                WHEN 'confirmed' THEN 1 WHEN 'high' THEN 2
                WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5
            END
    """).fetchall()

    # Summary by claim_type
    by_claim = {}
    by_conf = {}
    for r in rows:
        ct = r["claim_type"] or "none"
        by_claim[ct] = by_claim.get(ct, 0) + 1
        conf = r["confidence"] or "none"
        by_conf[conf] = by_conf.get(conf, 0) + 1

    print(f"Missing source_quote: {len(rows)} evidence rows")
    print(f"\nBy claim_type:")
    for ct in CLAIM_TYPE_ORDER + ["none"]:
        if ct in by_claim:
            print(f"  {ct}: {by_claim[ct]}")
    print(f"\nBy confidence:")
    for conf in CONFIDENCE_ORDER + ["none"]:
        if conf in by_conf:
            print(f"  {conf}: {by_conf[conf]}")

    limit = args.limit or 20
    print(f"\nTop {limit} priority items:")
    for r in rows[:limit]:
        print(f"  #{r['finding_id']:>4} [{r['claim_type'] or '?':>12}/{r['confidence'] or '?':>10}] "
              f"{r['evidence_ref']} — {r['target_name']}")

    db.close()
    return len(rows)


def cmd_overlap_detection(args):
    """Find EFTA IDs cited by 3+ findings, compute summary overlap."""
    db = get_inv_db()

    # Find EFTA IDs with 3+ findings
    clusters = db.execute("""
        SELECT fe.evidence_ref, COUNT(DISTINCT fe.finding_id) as finding_count,
               COUNT(DISTINCT f.target_name) as target_count
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE fe.evidence_type = 'efta'
        GROUP BY fe.evidence_ref
        HAVING COUNT(DISTINCT fe.finding_id) >= 3
        ORDER BY COUNT(DISTINCT fe.finding_id) DESC
    """).fetchall()

    print(f"EFTA IDs cited by 3+ findings: {len(clusters)}")
    print()

    dup_candidates = []
    for cluster in clusters:
        efta = cluster["evidence_ref"]
        fcount = cluster["finding_count"]
        tcount = cluster["target_count"]

        # Skip clusters where findings have many different targets (registry batches)
        if tcount > fcount * 0.6:
            continue

        # Get findings for this EFTA
        findings = db.execute("""
            SELECT f.id, f.target_name, f.summary
            FROM findings f
            JOIN finding_evidence fe ON f.id = fe.finding_id
            WHERE fe.evidence_ref = ?
            ORDER BY f.id
        """, (efta,)).fetchall()

        # Compute pairwise Jaccard on summaries
        pairs = []
        for i, f1 in enumerate(findings):
            for f2 in findings[i + 1:]:
                sim = jaccard_tokens(f1["summary"], f2["summary"])
                if sim > 0.6:
                    pairs.append((f1["id"], f2["id"], sim))

        if pairs:
            dup_candidates.append({
                "efta": efta,
                "finding_count": fcount,
                "target_count": tcount,
                "high_overlap_pairs": pairs,
                "finding_ids": [f["id"] for f in findings],
            })

    print(f"Clusters with >60% overlap pairs: {len(dup_candidates)}")
    for dc in dup_candidates[:20]:
        print(f"\n  {dc['efta']} ({dc['finding_count']} findings, {dc['target_count']} targets)")
        print(f"    Findings: {dc['finding_ids']}")
        for f1, f2, sim in dc["high_overlap_pairs"]:
            print(f"    Overlap: #{f1} <-> #{f2} = {sim:.1%}")

    db.close()
    return dup_candidates


def cmd_cross_check(args):
    """Verify source_quote actually appears in the cited EFTA OCR text."""
    inv_db = get_inv_db()
    doc_db = get_doc_db()

    # Get evidence rows WITH source_quote AND EFTA ref
    rows = inv_db.execute("""
        SELECT fe.rowid as fe_rowid, fe.finding_id, fe.evidence_ref, fe.source_quote,
               f.claim_type, f.confidence, f.target_name
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE fe.source_quote IS NOT NULL AND fe.source_quote != ''
          AND fe.evidence_type = 'efta'
          AND fe.evidence_ref LIKE 'EFTA%'
          AND fe.evidence_ref NOT LIKE '%,%'
    """).fetchall()

    print(f"Cross-checking {len(rows)} evidence rows against OCR text...")
    matches = 0
    mismatches = []
    not_found = 0

    for row in rows:
        efta_id = row["evidence_ref"].strip()
        doc = doc_db.execute(
            "SELECT ocr_text FROM documents WHERE bates_id = ?", (efta_id,)
        ).fetchone()

        if not doc or not doc["ocr_text"]:
            not_found += 1
            continue

        ocr_norm = normalize_ocr(doc["ocr_text"])
        quote_norm = normalize_ocr(row["source_quote"])

        if not quote_norm or len(quote_norm) < 10:
            continue

        # Check if quote (or significant substring) appears in OCR
        # Use a 40-char window for fuzzy matching
        found = False
        if quote_norm in ocr_norm:
            found = True
        else:
            # Try matching first 40 chars
            prefix = quote_norm[:40]
            if prefix in ocr_norm:
                found = True

        if found:
            matches += 1
        else:
            mismatches.append({
                "finding_id": row["finding_id"],
                "efta": efta_id,
                "claim_type": row["claim_type"],
                "confidence": row["confidence"],
                "target": row["target_name"],
                "quote_preview": row["source_quote"][:80],
            })

    total_checked = matches + len(mismatches)
    print(f"\nResults:")
    print(f"  Checked: {total_checked}")
    print(f"  Matches: {matches}")
    print(f"  Mismatches: {len(mismatches)}")
    print(f"  EFTA not in corpus: {not_found}")

    if mismatches:
        limit = args.limit or 20
        print(f"\nTop {limit} mismatches (quote NOT found in OCR):")
        for m in mismatches[:limit]:
            print(f"  #{m['finding_id']:>4} [{m['claim_type']:>12}/{m['confidence']:>10}] {m['efta']}")
            print(f"    Target: {m['target']}")
            print(f"    Quote: \"{m['quote_preview']}...\"")

    inv_db.close()
    doc_db.close()
    return mismatches


def cmd_confidence_violations(args):
    """Find direct_quote/confirmed findings where ALL evidence lacks source_quote."""
    db = get_inv_db()

    rows = db.execute("""
        SELECT f.id, f.target_name, f.claim_type, f.confidence, f.summary,
               COUNT(fe.evidence_ref) as evidence_count,
               SUM(CASE WHEN fe.source_quote IS NOT NULL AND fe.source_quote != '' THEN 1 ELSE 0 END) as quoted_count
        FROM findings f
        LEFT JOIN finding_evidence fe ON f.id = fe.finding_id
        WHERE f.claim_type = 'direct_quote' OR f.confidence = 'confirmed'
        GROUP BY f.id
        HAVING quoted_count = 0
        ORDER BY
            CASE f.confidence
                WHEN 'confirmed' THEN 1 WHEN 'high' THEN 2
                WHEN 'medium' THEN 3 ELSE 4
            END,
            f.id
    """).fetchall()

    print(f"Confidence violations: {len(rows)}")
    print("(direct_quote or confirmed findings with NO source_quote on any evidence)")

    # By claim_type x confidence
    by_combo = {}
    for r in rows:
        key = f"{r['claim_type']}/{r['confidence']}"
        by_combo[key] = by_combo.get(key, 0) + 1

    print(f"\nBy claim_type/confidence:")
    for key, count in sorted(by_combo.items()):
        print(f"  {key}: {count}")

    limit = args.limit or 20
    print(f"\nTop {limit} violations:")
    for r in rows[:limit]:
        evidence_note = f"{r['evidence_count']} evidence rows, 0 quoted" if r['evidence_count'] else "NO evidence"
        print(f"  #{r['id']:>4} [{r['claim_type']:>12}/{r['confidence']:>10}] {r['target_name']}")
        print(f"    {evidence_note}")
        print(f"    {r['summary'][:100]}...")

    db.close()
    return len(rows)


def cmd_report(args):
    """Aggregate all checks into summary report."""
    db = get_inv_db()

    print("=" * 60)
    print("EVIDENCE INTEGRITY AUDIT REPORT")
    print("=" * 60)

    # Basic counts
    total_findings = db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    total_evidence = db.execute("SELECT COUNT(*) FROM finding_evidence").fetchone()[0]
    total_connections = db.execute("SELECT COUNT(*) FROM connections").fetchone()[0]

    print(f"\nDatabase: {total_findings} findings, {total_evidence} evidence rows, {total_connections} connections")

    # Verification status
    verif = db.execute("""
        SELECT verification_status, COUNT(*) as cnt
        FROM findings GROUP BY verification_status
    """).fetchall()
    print(f"\nVerification status:")
    for r in verif:
        print(f"  {r['verification_status'] or 'none'}: {r['cnt']}")

    # 1. Missing quotes
    missing_total = db.execute("""
        SELECT COUNT(*) FROM finding_evidence
        WHERE source_quote IS NULL OR source_quote = ''
    """).fetchone()[0]
    missing_dq = db.execute("""
        SELECT COUNT(*)
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE (fe.source_quote IS NULL OR fe.source_quote = '')
          AND f.claim_type = 'direct_quote'
    """).fetchone()[0]
    pct = 100 * missing_total / total_evidence if total_evidence else 0
    print(f"\n--- Missing source_quote ---")
    print(f"  Total: {missing_total}/{total_evidence} ({pct:.1f}%)")
    print(f"  Direct quotes missing: {missing_dq}")

    # 2. Overlap detection (quick count)
    overlap_clusters = db.execute("""
        SELECT COUNT(*) FROM (
            SELECT evidence_ref
            FROM finding_evidence
            WHERE evidence_type = 'efta'
            GROUP BY evidence_ref
            HAVING COUNT(DISTINCT finding_id) >= 3
        )
    """).fetchone()[0]
    print(f"\n--- EFTA overlap clusters (3+ findings) ---")
    print(f"  Clusters: {overlap_clusters}")

    # 3. Confidence violations
    conf_violations = db.execute("""
        SELECT COUNT(*) FROM (
            SELECT f.id
            FROM findings f
            LEFT JOIN finding_evidence fe ON f.id = fe.finding_id
            WHERE f.claim_type = 'direct_quote' OR f.confidence = 'confirmed'
            GROUP BY f.id
            HAVING SUM(CASE WHEN fe.source_quote IS NOT NULL AND fe.source_quote != '' THEN 1 ELSE 0 END) = 0
        )
    """).fetchone()[0]
    print(f"\n--- Confidence violations ---")
    print(f"  direct_quote/confirmed with no source_quote: {conf_violations}")

    # 4. Header-only quotes (starts with "From:")
    header_quotes = db.execute("""
        SELECT COUNT(*)
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE fe.source_quote LIKE 'From:%'
          AND f.claim_type = 'direct_quote'
    """).fetchone()[0]
    print(f"\n--- Header-only quotes (direct_quote starting with 'From:') ---")
    print(f"  Count: {header_quotes}")

    # 5. Short quotes (< 20 chars) for direct_quote
    short_quotes = db.execute("""
        SELECT COUNT(*)
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE fe.source_quote IS NOT NULL
          AND LENGTH(fe.source_quote) < 20
          AND f.claim_type = 'direct_quote'
    """).fetchone()[0]
    print(f"\n--- Short quotes (<20 chars, direct_quote) ---")
    print(f"  Count: {short_quotes}")

    # Cross-check summary (skip if no doc db)
    print(f"\n--- Cross-check ---")
    try:
        doc_db = get_doc_db()
        doc_count = doc_db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        doc_db.close()
        print(f"  Documents DB available ({doc_count} documents)")
        print(f"  Run 'evidence_audit.py cross-check' for full analysis")
    except Exception as e:
        print(f"  Documents DB not available: {e}")

    print(f"\n{'=' * 60}")
    print("Run individual subcommands for detailed results.")

    db.close()


# ── CLI ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evidence integrity audit for investigation.db")
    sub = parser.add_subparsers(dest="command")

    p_mq = sub.add_parser("missing-quotes", help="Find evidence rows lacking source_quote")
    p_mq.add_argument("--limit", type=int, default=20, help="Number of items to show")

    p_ol = sub.add_parser("overlap-detection", help="Find EFTA IDs cited by 3+ findings")
    p_ol.add_argument("--threshold", type=float, default=0.6, help="Jaccard similarity threshold")

    p_xc = sub.add_parser("cross-check", help="Verify source_quote against OCR text")
    p_xc.add_argument("--limit", type=int, default=20, help="Number of mismatches to show")

    p_cv = sub.add_parser("confidence-violations", help="direct_quote/confirmed without source_quote")
    p_cv.add_argument("--limit", type=int, default=20, help="Number of items to show")

    p_rpt = sub.add_parser("report", help="Aggregate summary report")

    args = parser.parse_args()

    commands = {
        "missing-quotes": cmd_missing_quotes,
        "overlap-detection": cmd_overlap_detection,
        "cross-check": cmd_cross_check,
        "confidence-violations": cmd_confidence_violations,
        "report": cmd_report,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
