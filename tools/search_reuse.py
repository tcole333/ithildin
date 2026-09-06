"""Reuse a search only when its scope, outcome, freshness, and artifact match.

The legacy search log remains historical evidence of work, not a cache. This
small companion stores the metadata needed to decide whether results can be
reused. It never upgrades a legacy log entry into a reusable result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

try:
    from tools.search_log_util import canonical_search_key
except ImportError:
    from search_log_util import canonical_search_key

ROOT = Path(__file__).resolve().parents[1]
OUTCOMES = {"success", "partial", "failed", "unavailable"}


def _db_path(db_path=None) -> Path:
    return Path(db_path or os.environ.get("ITHILDIN_DB_PATH") or ROOT / "investigation.db")


def _identity(request: dict) -> tuple[str, str, str | None]:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    source, operation = request.get("source"), request.get("operation")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("request.source must be a non-empty string")
    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("request.operation must be a non-empty string")
    filters = request.get("filters", {})
    if not isinstance(filters, dict) or {"mode", "query"}.intersection(filters):
        raise ValueError("request.filters must be an object without mode/query keys")
    version = request.get("source_version")
    if version is not None and (not isinstance(version, str) or not version.strip()):
        raise ValueError("source_version must be a non-empty immutable corpus version")
    key = canonical_search_key(operation, request.get("query"), **filters)
    return source, key, version


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def record_result(
    request: dict, *, outcome: str, result_count: int | None = None,
    artifact=None, db_path=None, now: datetime | None = None,
) -> None:
    """Record the latest attempt. Success means a complete, inspected response.

    Record partial responses, access errors and failed attempts with their actual
    outcome; even a zero can only be reused after a successful complete search.
    Artifact loss or modification later invalidates reuse.
    """
    source, key, version = _identity(request)
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}")
    if result_count is not None and (
        isinstance(result_count, bool) or not isinstance(result_count, int) or result_count < 0
    ):
        raise ValueError("result_count must be a nonnegative integer or null")
    artifact_path, digest = None, None
    if outcome == "success":
        if result_count is None or artifact is None:
            raise ValueError("successful results require a count and an existing output artifact")
        artifact_path = str(Path(artifact).resolve(strict=True))
        digest = _sha256(Path(artifact_path))
    timestamp = (now or datetime.now(timezone.utc)).timestamp()
    with sqlite3.connect(_db_path(db_path), timeout=30) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS search_reuse (
            source TEXT NOT NULL, request_key TEXT NOT NULL,
            source_version TEXT, outcome TEXT NOT NULL, result_count INTEGER,
            artifact_path TEXT, artifact_sha256 TEXT, searched_at REAL NOT NULL,
            PRIMARY KEY (source, request_key)
        )""")
        db.execute("""INSERT INTO search_reuse VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, request_key) DO UPDATE SET
            source_version=excluded.source_version, outcome=excluded.outcome,
            result_count=excluded.result_count, artifact_path=excluded.artifact_path,
            artifact_sha256=excluded.artifact_sha256, searched_at=excluded.searched_at
        """, (source, key, version, outcome, result_count, artifact_path, digest, timestamp))


def check_reusable(
    request: dict, *, max_age_seconds: float | None = None,
    db_path=None, now: datetime | None = None,
) -> dict:
    """Return an explicit decision; dynamic sources require a freshness policy.

    An exact immutable source_version permits reuse without an age limit. Pass
    max_age_seconds as well if an additional freshness bound is needed.
    """
    source, key, version = _identity(request)
    if max_age_seconds is not None and (
        not math.isfinite(max_age_seconds) or max_age_seconds <= 0
    ):
        raise ValueError("max_age_seconds must be finite and greater than zero")

    def miss(reason):
        return {"reusable": False, "reason": reason}

    if version is None and max_age_seconds is None:
        return miss("dynamic source requires an explicit freshness limit")
    path = _db_path(db_path)
    if not path.is_file():
        return miss("no reusable search recorded")
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='search_reuse'"
        ).fetchone()
        if not exists:
            return miss("legacy search history has no reusable result metadata")
        row = db.execute(
            "SELECT * FROM search_reuse WHERE source=? AND request_key=?", (source, key)
        ).fetchone()
    if row is None:
        return miss("no result with matching source, operation, query, and filters")
    if row["outcome"] != "success":
        return miss(f"latest attempt was {row['outcome']}")
    if row["source_version"] != version:
        return miss("source version changed")
    age = (now or datetime.now(timezone.utc)).timestamp() - row["searched_at"]
    if age < 0 or (max_age_seconds is not None and age > max_age_seconds):
        return miss("result is outside the freshness window")
    artifact = Path(row["artifact_path"] or "")
    try:
        if not artifact.is_file() or _sha256(artifact) != row["artifact_sha256"]:
            return miss("result artifact is missing or changed")
    except OSError:
        return miss("result artifact cannot be read")
    return {
        "reusable": True, "reason": "matching successful search with intact artifact",
        "artifact": str(artifact), "result_count": row["result_count"],
        "age_seconds": age, "source_version": version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "record"):
        child = sub.add_parser(command)
        child.add_argument("--request-file", required=True, type=Path)
        child.add_argument("--db", type=Path)
        child.add_argument("--output", required=True, type=Path)
        if command == "check":
            child.add_argument("--max-age-hours", type=float)
        else:
            child.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
            child.add_argument("--result-count", type=int)
            child.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    try:
        request = json.loads(args.request_file.read_text())
        if args.command == "check":
            hours = args.max_age_hours
            result = check_reusable(
                request, max_age_seconds=None if hours is None else hours * 3600,
                db_path=args.db,
            )
        else:
            record_result(
                request, outcome=args.outcome, result_count=args.result_count,
                artifact=args.artifact, db_path=args.db,
            )
            result = {"recorded": True, "outcome": args.outcome}
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Search reuse {args.command}: {args.output}")


if __name__ == "__main__":
    main()
