#!/usr/bin/env python3
"""Re-anchor corpus-cited findings onto the kabasshouse corpus (append-only).

For findings whose source_datasets cite a superseded/subset corpus key
(doj_vol11, lmsband, duggan, fbi_parquet, fbi_warrant) AND whose
finding_evidence carries at least one EFTA id verified present in
datasets/kabasshouse_epstein.db, append "kabass" to source_datasets.

Design constraints:
- APPEND-ONLY: original source keys are kept for audit trail.
- Writes go through findings_tracker.update_finding() so every change
  lands a row in the corrections table.
- A shared EFTA file_key across corpora is the same page re-OCR'd, NOT
  independent corroboration. This migration adds provenance, not
  corroboration; confidence/claim_type are untouched.
- Legacy source_datasets encodings (bare string, comma-joined) are
  normalized to a JSON array on write.

Usage:
    uv run python scripts/reanchor_kabass_findings.py --dry-run
    uv run python scripts/reanchor_kabass_findings.py --apply
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.findings_tracker import update_finding  # noqa: E402

INVESTIGATION_DB = PROJECT_ROOT / "investigation.db"
KABASS_DB = PROJECT_ROOT / "datasets" / "kabasshouse_epstein.db"

# Findings citing these keys are candidates for kabass co-citation.
SUPERSEDED_KEYS = {"doj_vol11", "lmsband", "duggan", "fbi_parquet", "fbi_warrant"}
# Ad-hoc FBI keys additionally gain the canonical "fbi" key.
FBI_ADHOC_KEYS = {"fbi_parquet", "fbi_warrant"}

EFTA_RE = re.compile(r"EFTA\d{8}")


def parse_source_datasets(raw):
    """Tolerantly parse the mixed legacy encodings of source_datasets."""
    if raw is None:
        return []
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(s).strip() for s in parsed if str(s).strip()]
        except json.JSONDecodeError:
            pass
    if "," in raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return [raw]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="report only, no writes")
    mode.add_argument("--apply", action="store_true", help="write corrections")
    args = ap.parse_args()

    inv = sqlite3.connect(f"file:{INVESTIGATION_DB}?mode=ro", uri=True)
    inv.row_factory = sqlite3.Row
    kab = sqlite3.connect(f"file:{KABASS_DB}?mode=ro", uri=True)

    findings = inv.execute(
        "SELECT id, source_datasets FROM findings WHERE source_datasets IS NOT NULL"
    ).fetchall()

    candidates = []
    for row in findings:
        sources = parse_source_datasets(row["source_datasets"])
        cited = SUPERSEDED_KEYS.intersection(sources)
        if not cited or "kabass" in sources:
            continue
        candidates.append((row["id"], sources, cited))

    stats = Counter()
    changes = []
    for finding_id, sources, cited in candidates:
        evidence = inv.execute(
            "SELECT evidence_ref FROM finding_evidence WHERE finding_id = ?",
            (finding_id,),
        ).fetchall()
        efta_ids = sorted(
            {m for row in evidence for m in EFTA_RE.findall(row["evidence_ref"] or "")}
        )
        if not efta_ids:
            stats["skipped_no_efta"] += 1
            continue

        verified = [
            e for e in efta_ids
            if kab.execute(
                "SELECT 1 FROM documents WHERE file_key = ? LIMIT 1", (e,)
            ).fetchone()
        ]
        if not verified:
            stats["skipped_efta_not_in_kabass"] += 1
            continue

        new_sources = list(sources) + ["kabass"]
        if FBI_ADHOC_KEYS.intersection(sources) and "fbi" not in new_sources:
            new_sources.append("fbi")
        changes.append((finding_id, sources, new_sources, verified, sorted(cited)))
        stats["reanchored"] += 1
        for key in cited:
            stats[f"via_{key}"] += 1

    inv.close()
    kab.close()

    label = "DRY RUN" if args.dry_run else "APPLY"
    print(f"=== kabass re-anchor migration ({label}) ===")
    print(f"candidate findings citing superseded keys: {len(candidates)}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")

    if args.dry_run:
        for finding_id, old, new, verified, cited in changes[:10]:
            print(f"  e.g. #{finding_id}: {old} -> {new} "
                  f"({len(verified)} EFTA verified, via {cited})")
        if len(changes) > 10:
            print(f"  ... and {len(changes) - 10} more")
        return

    applied = 0
    for finding_id, old, new, verified, cited in changes:
        ok = update_finding(
            finding_id,
            "source_datasets",
            json.dumps(new),
            reason=(
                f"Re-anchor to kabasshouse: {len(verified)} EFTA evidence id(s) "
                f"verified present in kabasshouse documents.file_key "
                f"(e.g. {verified[0]}). Append-only co-citation via {sorted(cited)}; "
                "same underlying page re-OCR'd, not independent corroboration. "
                "Legacy encoding normalized to JSON array."
            ),
            correction_type="refinement",
            corrected_by="reanchor-kabass-migration",
        )
        if ok:
            applied += 1
    print(f"applied: {applied}/{len(changes)}")


if __name__ == "__main__":
    main()
