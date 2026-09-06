#!/usr/bin/env python3
"""Export a read-only, cross-profile snapshot for editorial candidate discovery."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TABLE_COLUMNS = {
    "investigation_profiles": ["profile_id", "display_name", "status", "created_at"],
    "investigation_threads": ["id", "profile_id", "name", "description", "status"],
    "findings": [
        "id", "profile_id", "target_name", "finding_type", "summary", "detail",
        "source_datasets", "confidence", "claim_type", "verification_status",
        "quality_state", "date_of_event", "event_date_iso", "date_precision",
        "lead_id", "thread_id", "created_at",
    ],
    "leads": [
        "id", "profile_id", "title", "description", "category", "priority",
        "status", "source", "target_name", "findings", "thread_id", "depth_tier",
        "recommended_skill", "triage_rationale", "stop_reason", "created_at",
        "updated_at",
    ],
    "connections": [
        "id", "profile_id", "person_a", "person_b", "relationship_type",
        "description", "strength", "date_range", "finding_id",
        "verification_status", "valid_from", "valid_until", "created_at",
    ],
    "entities": [
        "id", "name", "entity_type", "jurisdiction", "ein", "address", "status",
        "source", "notes", "date_formed", "created_at",
    ],
    "hypotheses": [
        "id", "title", "description", "pattern_type", "status",
        "predicted_evidence", "search_plan", "evidence_for", "evidence_against",
        "originated_from", "lead_id", "thread_id", "competition_group",
        "is_null_hypothesis", "created_at", "updated_at",
    ],
    "finding_relations": [
        "id", "from_finding_id", "to_finding_id", "relation_type", "assessment",
        "created_by", "created_at",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export evidence-aware platform state without modifying investigation.db"
    )
    parser.add_argument("--db", default=os.environ.get("ITHILDIN_DB_PATH") or "investigation.db",
                        help="SQLite database path (default: ITHILDIN_DB_PATH or investigation.db)")
    parser.add_argument("--repo-root", default=".", help="Repository root for content inventory")
    parser.add_argument("--output", required=True, help="Destination JSON file")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    return parser.parse_args()


def table_names(db: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def existing_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def select_rows(
    db: sqlite3.Connection, available_tables: set[str], table: str, desired: list[str]
) -> list[dict[str, Any]]:
    if table not in available_tables:
        return []
    available = existing_columns(db, table)
    columns = [column for column in desired if column in available]
    if not columns:
        return []
    order = "id" if "id" in available else columns[0]
    query = f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order}"
    return [dict(row) for row in db.execute(query)]


def finding_evidence(
    db: sqlite3.Connection, available_tables: set[str]
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if "finding_evidence" not in available_tables:
        return grouped
    columns = existing_columns(db, "finding_evidence")
    wanted = [
        name for name in (
            "finding_id", "evidence_type", "evidence_ref", "source_quote",
            "source_page", "assessment", "email_sender", "email_date", "chain_position",
        ) if name in columns
    ]
    for row in db.execute(
        f"SELECT {', '.join(wanted)} FROM finding_evidence "
        "ORDER BY finding_id, evidence_ref"
    ):
        item = dict(row)
        finding_id = int(item.pop("finding_id"))
        grouped[finding_id].append(item)
    return grouped


def finding_entities(
    db: sqlite3.Connection, available_tables: set[str]
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if "finding_entities" not in available_tables:
        return grouped
    columns = existing_columns(db, "finding_entities")
    wanted = [
        name for name in (
            "finding_id", "entity_id", "mention_role", "raw_name",
            "resolution_status", "resolution_method", "resolution_score",
        ) if name in columns
    ]
    for row in db.execute(
        f"SELECT {', '.join(wanted)} FROM finding_entities "
        "ORDER BY finding_id, entity_id"
    ):
        item = dict(row)
        finding_id = int(item.pop("finding_id"))
        grouped[finding_id].append(item)
    return grouped


def table_stats(
    db: sqlite3.Connection, available_tables: set[str], table: str
) -> dict[str, Any]:
    if table not in available_tables:
        return {"count": 0, "max_id": None}
    count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    columns = existing_columns(db, table)
    max_id = db.execute(f"SELECT MAX(id) FROM {table}").fetchone()[0] if "id" in columns else None
    return {"count": count, "max_id": max_id}


def file_inventory(repo_root: Path) -> dict[str, list[dict[str, Any]]]:
    groups = {
        "investigation_configs": list(repo_root.glob("investigations/*/config.yaml")),
        "articles": list(repo_root.glob("content/articles/*.mdx")),
        "dossiers": list(repo_root.glob("content/dossiers/*.json")),
        "reports": list(repo_root.glob("reports/**/*")),
        "research_memos": list(repo_root.glob("research/**/*.md")),
        "dataset_databases": (
            list(repo_root.glob("datasets/**/*.db"))
            + list(repo_root.glob("datasets/**/*.sqlite"))
            + list(repo_root.glob("datasets/**/*.duckdb"))
        ),
    }
    result: dict[str, list[dict[str, Any]]] = {}
    for name, paths in groups.items():
        entries = []
        for path in sorted({path.resolve() for path in paths if path.is_file()}):
            stat = path.stat()
            entries.append({
                "path": str(path.relative_to(repo_root.resolve())),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })
        result[name] = entries
    return result


def git_state(repo_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(
                ["git", "-C", str(repo_root), *args],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    commit = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return {"commit": commit or None, "dirty": bool(status) if commit else None}


def build_snapshot(db_path: Path, repo_root: Path) -> dict[str, Any]:
    db_uri = db_path.resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(db_uri, uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("BEGIN")
        available_tables = table_names(db)
        data = {
            table: select_rows(db, available_tables, table, columns)
            for table, columns in TABLE_COLUMNS.items()
        }
        evidence = finding_evidence(db, available_tables)
        linked_entities = finding_entities(db, available_tables)
        for finding in data["findings"]:
            finding_id = int(finding["id"])
            finding["evidence"] = evidence.get(finding_id, [])
            finding["entities"] = linked_entities.get(finding_id, [])

        stats = {
            table: table_stats(db, available_tables, table)
            for table in TABLE_COLUMNS
        }
    finally:
        db.close()

    db_stat = db_path.stat()
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "path": str(db_path.resolve()),
            "size_bytes": db_stat.st_size,
            "modified_at": datetime.fromtimestamp(
                db_stat.st_mtime, tz=timezone.utc
            ).isoformat(),
            "tables": stats,
        },
        "git": git_state(repo_root),
        "content_inventory": file_inventory(repo_root),
        "data": data,
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db).expanduser().resolve()
    repo_root = Path(args.repo_root)
    output = Path(args.output).expanduser().resolve()
    protected = [db_path, *(Path(str(db_path) + suffix) for suffix in ("-wal", "-shm", "-journal"))]
    destination = output.expanduser().resolve()
    if any(destination == source or (destination.exists() and source.exists() and destination.samefile(source))
           for source in protected):
        raise SystemExit("Snapshot output must not overwrite the selected database or SQLite sidecars")
    if not db_path.is_file():
        raise SystemExit(f"Database not found: {db_path}")
    if not repo_root.is_dir():
        raise SystemExit(f"Repository root not found: {repo_root}")

    snapshot = build_snapshot(db_path, repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(
            snapshot,
            handle,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
        handle.write("\n")

    counts = snapshot["database"]["tables"]
    print(
        f"Wrote {output}: "
        f"{counts['findings']['count']} findings, "
        f"{counts['leads']['count']} leads, "
        f"{counts['entities']['count']} entities, "
        f"{counts['connections']['count']} connections"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
