#!/usr/bin/env python3
"""Normalize legacy comma-joined findings.source_datasets strings to JSON arrays.

Dispatcher imports before 2026-04 stored worker-supplied source lists verbatim
("edgar,parazero_20f_2026,scisparc_20f_2025"), but findings_tracker requires a
JSON array — verify/evidence-audit fail on those rows with "source_datasets is
not valid JSON".

For each affected row this script:
  * splits the stored string on commas and trims whitespace
  * canonicalizes registered-source spelling variants (SOURCE_ALIASES plus the
    PREFIX_FAMILIES below, e.g. edgar_forms_345 -> edgar)
  * preserves unregistered ad-hoc labels verbatim (parazero_20f_2026 stays in
    the array; evidence-audit reports such tokens as warnings, and the strict
    write paths in findings_tracker still reject them for new findings)
  * writes a corrections row in the same transaction, mirroring the audit
    trail of `findings_tracker.py correct`

verification_status and profile_id are intentionally untouched: only the
encoding of the provenance claim changes, not the claim itself, so previously
verified rows stay verified and profile scoping is preserved.

Dry-run by default:
    uv run python scripts/migrate_source_datasets_json.py [--db PATH] [--apply] [--report PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.findings_tracker import SOURCE_ALIASES, VALID_SOURCES  # noqa: E402

DEFAULT_DB_PATH = PROJECT_ROOT / "investigation.db"
CORRECTED_BY = "migration:migrate_source_datasets_json"
REASON = (
    "Normalize legacy comma-joined source_datasets string to JSON array "
    "(2026-03/04 dispatcher imports stored worker output verbatim)"
)

# Variant families that denote the same retrieval system as a registered token.
# Tokens naming a *document* or *publisher* (parazero_20f_2026, startribune)
# deliberately do not match and are preserved verbatim.
PREFIX_FAMILIES = [
    (re.compile(r"^(sec_)?edgar[_.].+$", re.IGNORECASE), "edgar"),
    (re.compile(r"^opencorporates[_.].+$", re.IGNORECASE), "opencorporates"),
    (re.compile(r"^courtlistener[_.].+$", re.IGNORECASE), "courtlistener"),
    (re.compile(r"^icij[_.].+$", re.IGNORECASE), "icij"),
]


def is_stored_json_array(raw_value: str) -> bool:
    """True when the stored value already parses as a JSON list."""
    try:
        return isinstance(json.loads(raw_value), list)
    except (TypeError, json.JSONDecodeError):
        return False


def canonicalize_token(token: str) -> str:
    """Map a variant spelling onto its registered token; keep ad-hoc labels."""
    tok = SOURCE_ALIASES.get(token, token)
    if tok in VALID_SOURCES:
        return tok
    for pattern, target in PREFIX_FAMILIES:
        if pattern.match(tok):
            return target
    return token


def normalized_tokens(raw_value: str) -> list[str]:
    """Split a legacy comma-joined string into canonicalized, deduped tokens."""
    tokens: list[str] = []
    for part in raw_value.split(","):
        part = part.strip()
        if not part:
            continue
        token = canonicalize_token(part)
        if token not in tokens:
            tokens.append(token)
    return tokens


def find_affected_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = db.execute(
        "SELECT id, profile_id, source_datasets FROM findings "
        "WHERE source_datasets IS NOT NULL AND TRIM(source_datasets) != '' "
        "ORDER BY id"
    ).fetchall()
    return [row for row in rows if not is_stored_json_array(row["source_datasets"])]


def migrate(db_path: Path, apply: bool) -> dict:
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")

    summary: dict = {
        "db": str(db_path),
        "applied": apply,
        "updated": 0,
        "skipped_concurrent": 0,
        "needs_review": [],
        "by_profile": Counter(),
        "token_mapping": Counter(),
        "unregistered_preserved": Counter(),
        "rows": [],
    }

    try:
        affected = find_affected_rows(db)
        summary["affected"] = len(affected)

        if apply:
            db.execute("BEGIN IMMEDIATE")

        for row in affected:
            old_value = row["source_datasets"]
            tokens = normalized_tokens(old_value)
            if not tokens:
                summary["needs_review"].append(
                    {"id": row["id"], "source_datasets": old_value}
                )
                continue

            new_value = json.dumps(tokens)

            if apply:
                cursor = db.execute(
                    "UPDATE findings SET source_datasets = ? "
                    "WHERE id = ? AND source_datasets = ?",
                    (new_value, row["id"], old_value),
                )
                if cursor.rowcount != 1:
                    summary["skipped_concurrent"] += 1
                    continue
                db.execute(
                    """
                    INSERT INTO corrections (table_name, record_id, field_name,
                                             old_value, new_value, reason,
                                             corrected_by, correction_type)
                    VALUES ('findings', ?, 'source_datasets', ?, ?, ?, ?, 'refinement')
                    """,
                    (row["id"], old_value, new_value, REASON, CORRECTED_BY),
                )

            for part in (p.strip() for p in old_value.split(",")):
                if not part:
                    continue
                canonical = canonicalize_token(part)
                if canonical != part:
                    summary["token_mapping"][f"{part} -> {canonical}"] += 1
                elif canonical not in VALID_SOURCES:
                    summary["unregistered_preserved"][canonical] += 1
            summary["rows"].append(
                {
                    "id": row["id"],
                    "profile_id": row["profile_id"],
                    "old": old_value,
                    "new": new_value,
                }
            )
            summary["by_profile"][row["profile_id"] or ""] += 1
            summary["updated"] += 1

        if apply:
            db.commit()
    except Exception:
        if apply:
            db.rollback()
        raise
    finally:
        db.close()

    summary["by_profile"] = dict(summary["by_profile"])
    summary["token_mapping"] = dict(
        sorted(summary["token_mapping"].items(), key=lambda kv: -kv[1])
    )
    summary["unregistered_preserved"] = dict(
        sorted(summary["unregistered_preserved"].items(), key=lambda kv: -kv[1])
    )
    return summary


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description="Normalize comma-joined findings.source_datasets to JSON arrays"
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
        help="Optional path for a full JSON report (per-row old/new values)",
    )
    args = parser.parse_args(argv)

    if not args.db.exists():
        parser.error(f"Database not found: {args.db}")

    summary = migrate(args.db, apply=args.apply)

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"[{mode}] {summary['affected']} rows with non-JSON source_datasets")
    print(f"  normalized: {summary['updated']}")
    if summary["skipped_concurrent"]:
        print(f"  skipped (concurrent change): {summary['skipped_concurrent']}")
    if summary["needs_review"]:
        print(f"  needs manual review (no tokens): {len(summary['needs_review'])}")
    print(f"  by profile: {summary['by_profile']}")
    print("  variant tokens canonicalized:")
    for mapping, count in summary["token_mapping"].items():
        print(f"    {mapping}: {count}")
    print("  unregistered labels preserved verbatim "
          f"({len(summary['unregistered_preserved'])} distinct):")
    for token, count in list(summary["unregistered_preserved"].items())[:20]:
        print(f"    {token}: {count}")
    if len(summary["unregistered_preserved"]) > 20:
        print("    ... (see --report for the full list)")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2))
        print(f"  full report: {args.report}")

    return summary


if __name__ == "__main__":
    main()
