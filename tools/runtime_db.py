#!/usr/bin/env python3
"""Locate and open the shared runtime SQLite databases without creating them.

``sqlite3.connect(path)`` creates an empty database when ``path`` is missing.
The runtime databases are ignored by Git, so a tool run from a fresh worktree
used to create an empty stand-in and report zero results as if they were real
negative evidence. These helpers resolve the shared paths through environment
overrides and refuse to open a missing file unless the caller explicitly asks
SQLite to create one.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INVESTIGATION_DB_ENV = "ITHILDIN_DB_PATH"
REGISTRY_DB_ENV = "ITHILDIN_REGISTRY_DB_PATH"
WORKTREE_LINK_COMMAND = "uv run python scripts/link_worktree_runtime.py"

OPEN_MODES = ("ro", "rw", "rwc")


class MissingDatabaseError(FileNotFoundError):
    """Raised instead of letting SQLite create an empty stand-in database."""


def _selected_path(env_var: str, default: Path) -> Path:
    selected = os.environ.get(env_var)
    return Path(selected).expanduser() if selected else default


def investigation_db_path() -> Path:
    """Return ITHILDIN_DB_PATH, else this checkout's investigation.db."""
    return _selected_path(INVESTIGATION_DB_ENV, PROJECT_ROOT / "investigation.db")


def registry_db_path() -> Path:
    """Return ITHILDIN_REGISTRY_DB_PATH, else this checkout's registry.db."""
    return _selected_path(REGISTRY_DB_ENV, PROJECT_ROOT / "registry.db")


def missing_database_message(path: Path, env_var: str | None = None) -> str:
    """Explain a missing database and how to point the tool at the shared one."""
    lines = [
        f"SQLite database not found: {path}",
        "Refusing to create an empty database there: every query would return "
        "zero rows that look like real negative results.",
    ]
    configured = os.environ.get(env_var) if env_var else None
    if configured and Path(configured).expanduser() == path:
        lines.append(f"{env_var} points at this missing file; correct it.")
    elif env_var:
        lines.append(f"Set {env_var} to the shared database path.")
    lines.append(
        "In a git worktree, link the main checkout's ignored runtime files with: "
        f"{WORKTREE_LINK_COMMAND}"
    )
    return "\n".join(lines)


def require_database(path: str | Path, *, env_var: str | None = None) -> Path:
    """Return ``path`` when it is an existing file, else raise MissingDatabaseError."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise MissingDatabaseError(missing_database_message(path, env_var))
    return path


def connect(
    path: str | Path,
    mode: str = "ro",
    *,
    env_var: str | None = None,
    timeout: float = 5.0,
) -> sqlite3.Connection:
    """Open ``path`` with SQLite URI ``mode``: ro (default), rw, or rwc.

    ``ro`` and ``rw`` require an existing file. Only ``rwc`` may create a
    database, so a caller that creates one says so at the call site. SQLite's
    ``:memory:`` name still opens a private in-memory database.
    """
    if mode not in OPEN_MODES:
        raise ValueError(f"Unsupported SQLite open mode {mode!r}; use one of {OPEN_MODES}")
    if str(path) == ":memory:":
        return sqlite3.connect(":memory:", timeout=timeout)
    path = Path(path).expanduser()
    if mode != "rwc":
        require_database(path, env_var=env_var)
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode={mode}", uri=True, timeout=timeout)


def connect_investigation_db(
    path: str | Path | None = None,
    mode: str = "ro",
    *,
    timeout: float = 5.0,
) -> sqlite3.Connection:
    """Open investigation.db (``path`` or ITHILDIN_DB_PATH) without implicit creation."""
    selected = investigation_db_path() if path is None else path
    return connect(selected, mode, env_var=INVESTIGATION_DB_ENV, timeout=timeout)


def connect_registry_db(
    path: str | Path | None = None,
    mode: str = "ro",
    *,
    timeout: float = 5.0,
) -> sqlite3.Connection:
    """Open registry.db (``path`` or ITHILDIN_REGISTRY_DB_PATH) without implicit creation."""
    selected = registry_db_path() if path is None else path
    return connect(selected, mode, env_var=REGISTRY_DB_ENV, timeout=timeout)
