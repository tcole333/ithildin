#!/usr/bin/env python3
"""
Backfill source_datasets for existing findings that have NULL source_datasets.

Infers source from finding_evidence.evidence_ref patterns:
  - EFTA... → doj_vol11
  - sec.gov or edgar → edgar
  - fec.gov or opensecrets → fec
  - courtlistener → courtlistener
  - 990 or propublica → 990
  - analysis-run → analysis_run
  - littlesis → littlesis
  - sunbiz → fl_sunbiz
  - dos.ny.gov → ny_dos
  - registry → registry
  - usaspending → usaspending
  - sam.gov → sam_gov
  - lobbying or lda → lobbying
  - fara → fara
  - gdelt → gdelt
  - aleph or occrp → aleph
  - icij → icij
  - shodan → shodan
  - crt.sh → crtsh
  - web.archive.org or wayback → wayback
  - urlscan → urlscan
  - gleif → gleif
  - opensanctions → opensanctions
  - acris → acris

Run: uv run python scripts/backfill_source_datasets.py [--dry-run]
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "investigation.db"

# Map evidence_ref patterns to source_datasets values
EVIDENCE_PATTERNS = [
    (re.compile(r"^EFTA\d+", re.I), "doj_vol11"),
    (re.compile(r"sec\.gov|edgar", re.I), "edgar"),
    (re.compile(r"fec\.gov|opensecrets", re.I), "fec"),
    (re.compile(r"courtlistener", re.I), "courtlistener"),
    (re.compile(r"propublica.*990|990.*propublica|PP990|query_990", re.I), "990"),
    (re.compile(r"analysis.?run", re.I), "analysis_run"),
    (re.compile(r"littlesis", re.I), "littlesis"),
    (re.compile(r"sunbiz|fl_sunbiz|fl\.dos", re.I), "fl_sunbiz"),
    (re.compile(r"dos\.ny\.gov|ny_dos|nydos", re.I), "ny_dos"),
    (re.compile(r"usaspending|usaspend", re.I), "usaspending"),
    (re.compile(r"sam\.gov", re.I), "sam_gov"),
    (re.compile(r"lobbying|lda\.senate", re.I), "lobbying"),
    (re.compile(r"fara\.gov|fara", re.I), "fara"),
    (re.compile(r"gdelt", re.I), "gdelt"),
    (re.compile(r"aleph|occrp", re.I), "aleph"),
    (re.compile(r"icij|offshore.*leak", re.I), "icij"),
    (re.compile(r"shodan", re.I), "shodan"),
    (re.compile(r"crt\.sh|crtsh", re.I), "crtsh"),
    (re.compile(r"web\.archive\.org|wayback", re.I), "wayback"),
    (re.compile(r"urlscan", re.I), "urlscan"),
    (re.compile(r"gleif", re.I), "gleif"),
    (re.compile(r"opensanctions", re.I), "opensanctions"),
    (re.compile(r"acris", re.I), "acris"),
    (re.compile(r"opencorporates", re.I), "opencorporates"),
    (re.compile(r"companies\.?house|uk_companies", re.I), "uk_companies_house"),
    (re.compile(r"registry|sos\.state|sunbiz|corps\.state", re.I), "registry"),
    # Web search fallback — URLs that are news/media sites
    (re.compile(r"https?://(?!.*(?:sec\.gov|fec\.gov|courtlistener|propublica|littlesis|gdelt|aleph|icij|shodan|crt\.sh|urlscan|gleif|opensanctions|acris|usaspending|sam\.gov))", re.I), "web_search"),
]


def infer_sources(evidence_refs: list[str]) -> list[str]:
    """Infer source_datasets from a list of evidence_ref values."""
    sources = set()
    for ref in evidence_refs:
        if not ref:
            continue
        for pattern, source in EVIDENCE_PATTERNS:
            if pattern.search(ref):
                sources.add(source)
                break  # First match wins per evidence ref
    return sorted(sources) if sources else []


def main():
    parser = argparse.ArgumentParser(description="Backfill source_datasets for findings with NULL values")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of findings to process (0=all)")
    args = parser.parse_args()

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")

    # Find findings with NULL source_datasets
    query = "SELECT id, target_name, summary FROM findings WHERE source_datasets IS NULL"
    if args.limit:
        query += f" LIMIT {args.limit}"
    null_findings = db.execute(query).fetchall()

    print(f"Found {len(null_findings)} findings with NULL source_datasets")

    updated = 0
    skipped = 0
    by_source = {}

    for finding in null_findings:
        fid = finding["id"]

        # Get all evidence refs for this finding
        evidence_rows = db.execute(
            "SELECT evidence_ref FROM finding_evidence WHERE finding_id = ?", (fid,)
        ).fetchall()
        refs = [r["evidence_ref"] for r in evidence_rows if r["evidence_ref"]]

        sources = infer_sources(refs)
        if not sources:
            skipped += 1
            continue

        sources_json = json.dumps(sources)
        for src in sources:
            by_source[src] = by_source.get(src, 0) + 1

        if args.dry_run:
            print(f"  #{fid} {finding['target_name'][:30]:30} refs={refs[:2]}... -> {sources}")
        else:
            db.execute(
                "UPDATE findings SET source_datasets = ? WHERE id = ?",
                (sources_json, fid)
            )
        updated += 1

    if not args.dry_run:
        db.commit()

    db.close()

    print(f"\n{'Would update' if args.dry_run else 'Updated'}: {updated} findings")
    print(f"Skipped (no inference possible): {skipped}")
    print(f"\nSource distribution:")
    for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")


if __name__ == "__main__":
    main()
