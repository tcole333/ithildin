#!/usr/bin/env python3
"""Fail if dossier evidence blocks drift from investigation.db.

This compares:
1) findings[*].evidence against finding_evidence rows
2) connections[*].evidence against connection_evidence rows
3) factual/source-corrected finding fields against canonical findings values

Rows are canonicalized with pipeline/evidence_refs.py so packed refs are expanded
and ordering differences do not produce false positives.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "investigation.db"
DOSSIER_DIR = REPO_ROOT / "content" / "dossiers"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.evidence_refs import canonicalize_evidence_rows


@dataclass(frozen=True)
class Mismatch:
    dossier: str
    block_type: str
    record_id: int
    dossier_rows: int
    db_rows: int


@dataclass(frozen=True)
class CorrectedFieldMismatch:
    dossier: str
    record_id: int
    field_name: str


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def canonical_tuple_finding(row: dict) -> tuple:
    return (
        row.get("evidence_type"),
        row.get("evidence_ref"),
        normalize_text(row.get("source_quote")),
        row.get("source_page"),
        row.get("assessment"),
    )


def canonical_tuple_connection(row: dict) -> tuple:
    return (
        row.get("evidence_type"),
        row.get("evidence_ref"),
        normalize_text(row.get("source_quote")),
        row.get("source_page"),
    )


def sorted_tuples(rows: list[dict], mode: str) -> list[tuple]:
    if mode == "finding":
        return sorted(canonical_tuple_finding(row) for row in rows)
    if mode == "connection":
        return sorted(canonical_tuple_connection(row) for row in rows)
    raise ValueError(f"Unknown mode: {mode}")


def load_finding_evidence_map(conn: sqlite3.Connection) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    rows = conn.execute(
        """
        SELECT finding_id, evidence_type, evidence_ref, source_quote, source_page, assessment
        FROM finding_evidence
        """
    ).fetchall()
    for row in rows:
        grouped[int(row["finding_id"])].append(dict(row))
    return {fid: canonicalize_evidence_rows(items) for fid, items in grouped.items()}


def load_connection_evidence_map(conn: sqlite3.Connection) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    rows = conn.execute(
        """
        SELECT connection_id, evidence_type, evidence_ref, source_quote, source_page
        FROM connection_evidence
        """
    ).fetchall()
    for row in rows:
        grouped[int(row["connection_id"])].append(dict(row))
    return {cid: canonicalize_evidence_rows(items) for cid, items in grouped.items()}


def load_finding_map(conn: sqlite3.Connection) -> dict[int, dict]:
    return {
        int(row["id"]): dict(row)
        for row in conn.execute("SELECT * FROM findings").fetchall()
    }


def load_corrected_finding_fields(conn: sqlite3.Connection) -> dict[int, set[str]]:
    grouped: dict[int, set[str]] = defaultdict(set)
    rows = conn.execute(
        """
        SELECT record_id, field_name
        FROM corrections
        WHERE table_name = 'findings'
          AND correction_type IN ('factual_error', 'source_mismatch')
        """
    ).fetchall()
    for row in rows:
        grouped[int(row["record_id"])].add(row["field_name"])
    return dict(grouped)


def normalize_canonical_value(field_name: str, value: object) -> object:
    if field_name == "source_datasets" and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def iter_dossier_paths(dossier_dir: Path, only: list[str]) -> list[Path]:
    all_paths = sorted(p for p in dossier_dir.glob("*.json") if not p.name.startswith("_"))
    if not only:
        return all_paths

    by_name = {p.name: p for p in all_paths}
    resolved: list[Path] = []
    for value in only:
        raw = value.strip()
        if not raw:
            continue
        if raw.endswith(".json"):
            key = Path(raw).name
            if key not in by_name:
                raise FileNotFoundError(f"Dossier file not found: {raw}")
            resolved.append(by_name[key])
            continue
        slug_name = f"{raw}.json"
        if slug_name not in by_name:
            raise FileNotFoundError(f"Dossier slug not found: {raw}")
        resolved.append(by_name[slug_name])
    return resolved


def check_sync(
    dossier_paths: list[Path],
    finding_evidence_map: dict[int, list[dict]],
    connection_map: dict[int, list[dict]],
    canonical_findings: dict[int, dict],
    corrected_finding_fields: dict[int, set[str]],
) -> list[Mismatch | CorrectedFieldMismatch]:
    mismatches: list[Mismatch | CorrectedFieldMismatch] = []

    for path in dossier_paths:
        dossier = json.loads(path.read_text())
        dossier_name = path.name

        for finding in dossier.get("findings", []):
            fid = finding.get("id")
            if fid is None:
                continue
            fid = int(fid)
            dossier_rows = canonicalize_evidence_rows(list(finding.get("evidence") or []))
            db_rows = finding_evidence_map.get(fid, [])
            if sorted_tuples(dossier_rows, "finding") != sorted_tuples(db_rows, "finding"):
                mismatches.append(
                    Mismatch(
                        dossier=dossier_name,
                        block_type="finding",
                        record_id=fid,
                        dossier_rows=len(dossier_rows),
                        db_rows=len(db_rows),
                    )
                )

            canonical = canonical_findings.get(fid)
            marked_fields = set(finding.get("canonical_corrected_fields") or [])
            for field_name in sorted(marked_fields | corrected_finding_fields.get(fid, set())):
                if canonical is None or field_name not in canonical:
                    mismatches.append(
                        CorrectedFieldMismatch(dossier_name, fid, field_name)
                    )
                    continue
                dossier_value = normalize_canonical_value(field_name, finding.get(field_name))
                canonical_value = normalize_canonical_value(field_name, canonical[field_name])
                if dossier_value != canonical_value:
                    mismatches.append(
                        CorrectedFieldMismatch(dossier_name, fid, field_name)
                    )

        for connection in dossier.get("connections", []):
            cid = connection.get("id")
            if cid is None:
                continue
            cid = int(cid)
            dossier_rows = canonicalize_evidence_rows(list(connection.get("evidence") or []))
            db_rows = connection_map.get(cid, [])
            if sorted_tuples(dossier_rows, "connection") != sorted_tuples(db_rows, "connection"):
                mismatches.append(
                    Mismatch(
                        dossier=dossier_name,
                        block_type="connection",
                        record_id=cid,
                        dossier_rows=len(dossier_rows),
                        db_rows=len(db_rows),
                    )
                )

    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description="Check dossier evidence sync with investigation.db")
    parser.add_argument(
        "--dossier",
        action="append",
        default=[],
        help="Optional dossier slug or filename. Repeat to check multiple.",
    )
    parser.add_argument("--limit", type=int, default=50, help="Max mismatch lines to print (default: 50)")
    parser.add_argument(
        "--db-path",
        default=str(DB_PATH),
        help=f"Path to investigation database (default: {DB_PATH})",
    )
    parser.add_argument(
        "--dossier-dir",
        default=str(DOSSIER_DIR),
        help=f"Path to dossier directory (default: {DOSSIER_DIR})",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    dossier_dir = Path(args.dossier_dir)

    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 2
    if not dossier_dir.exists():
        print(f"Dossier directory not found: {dossier_dir}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Check that required tables exist (investigation.db may be absent in CI)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "finding_evidence" not in tables:
            print("Skipping dossier evidence sync: finding_evidence table not found (CI mode).")
            conn.close()
            return 0
        dossier_paths = iter_dossier_paths(dossier_dir, args.dossier)
        finding_evidence_map = load_finding_evidence_map(conn)
        connection_map = load_connection_evidence_map(conn)
        canonical_findings = load_finding_map(conn) if "findings" in tables else {}
        corrected_finding_fields = (
            load_corrected_finding_fields(conn) if "corrections" in tables else {}
        )
        mismatches = check_sync(
            dossier_paths,
            finding_evidence_map,
            connection_map,
            canonical_findings,
            corrected_finding_fields,
        )
    finally:
        conn.close()

    if not mismatches:
        print(f"Dossier evidence sync OK: {len(dossier_paths)} file(s) checked, 0 mismatches.")
        return 0

    print(
        f"Dossier evidence sync FAILED: {len(dossier_paths)} file(s) checked, "
        f"{len(mismatches)} mismatches."
    )
    for mismatch in mismatches[: args.limit]:
        if isinstance(mismatch, CorrectedFieldMismatch):
            print(
                f"- {mismatch.dossier} finding#{mismatch.record_id}: "
                f"corrected field {mismatch.field_name!r} differs from canonical DB"
            )
            continue
        print(
            f"- {mismatch.dossier} {mismatch.block_type}#{mismatch.record_id}: "
            f"dossier_rows={mismatch.dossier_rows} db_rows={mismatch.db_rows}"
        )
    remaining = len(mismatches) - min(len(mismatches), args.limit)
    if remaining > 0:
        print(f"- ... {remaining} additional mismatch(es) omitted")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
