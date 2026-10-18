from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.link_worktree_runtime import link_runtime
from tools.runtime_db import connect

REPO_ROOT = Path(__file__).resolve().parent.parent
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.test",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.test",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=GIT_ENV)


def _sqlite_with_row(path: Path, value: str) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE marker(value TEXT)")
        db.execute("INSERT INTO marker VALUES (?)", (value,))
    db.close()


@pytest.fixture
def checkout(tmp_path: Path) -> tuple[Path, Path]:
    """A main checkout with ignored runtime files and a fresh worktree of it."""
    main = tmp_path / "main"
    (main / "data").mkdir(parents=True)
    _git(main, "init", "-q", "-b", "main")
    (main / ".gitignore").write_text(
        ".env\n.claude/worktrees/\ndatasets/\n*.db\n*.db-*\ndata/*\n!data/keep.json\n"
    )
    (main / "data" / "keep.json").write_text("{}\n")
    _git(main, "add", ".gitignore", "data/keep.json")
    _git(main, "commit", "-q", "-m", "init")

    (main / ".env").write_text("FIXTURE_TOKEN=not-a-secret\n")
    (main / "datasets").mkdir()
    _sqlite_with_row(main / "datasets" / "corpus.db", "corpus")
    _sqlite_with_row(main / "investigation.db", "shared investigation")
    _sqlite_with_row(main / "registry.db", "shared registry")
    (main / "data" / "loans.parquet").write_bytes(b"PAR1")
    (main / "data" / "cases").mkdir()
    (main / "data" / "cases" / "a.txt").write_text("case\n")
    (main / "data" / "loans.db-wal").write_bytes(b"")

    worktree = main / ".claude" / "worktrees" / "task"
    _git(main, "worktree", "add", "-q", "-b", "task", str(worktree))
    return main, worktree


def test_links_every_ignored_runtime_path_to_the_main_checkout(checkout):
    main, worktree = checkout

    results = {result.path: result.status for result in link_runtime(worktree)}

    expected = {
        ".env", "datasets", "registry.db", "investigation.db", "data/loans.parquet", "data/cases",
    }
    assert results == {path: "linked" for path in expected}
    for relative in expected:
        assert (worktree / relative).is_symlink()
        assert (worktree / relative).resolve() == (main / relative).resolve()
    assert not (worktree / "data" / "loans.db-wal").exists()
    assert not (worktree / "data" / "keep.json").is_symlink()


def test_linked_database_reads_and_writes_the_shared_file(checkout):
    main, worktree = checkout
    link_runtime(worktree)

    with connect(worktree / "investigation.db", "rw") as db:
        assert db.execute("SELECT value FROM marker").fetchall() == [("shared investigation",)]
        db.execute("INSERT INTO marker VALUES ('written from worktree')")
        database_file = db.execute("PRAGMA database_list").fetchone()[2]
    db.close()

    assert Path(database_file) == (main / "investigation.db").resolve()
    with sqlite3.connect(main / "investigation.db") as shared:
        assert ("written from worktree",) in shared.execute("SELECT value FROM marker").fetchall()
    shared.close()


def test_existing_worktree_files_are_reported_and_left_unchanged(checkout):
    _, worktree = checkout
    stand_in = worktree / "registry.db"
    _sqlite_with_row(stand_in, "empty stand-in")
    before = stand_in.read_bytes()

    first = {result.path: result.status for result in link_runtime(worktree)}
    second = {result.path: result.status for result in link_runtime(worktree)}

    assert first["registry.db"] == "conflict"
    assert first["investigation.db"] == "linked"
    assert second["registry.db"] == "conflict"
    assert second["investigation.db"] == "already_linked"
    assert not stand_in.is_symlink()
    assert stand_in.read_bytes() == before


def test_dry_run_creates_no_links(checkout):
    _, worktree = checkout

    results = link_runtime(worktree, dry_run=True)

    assert {result.status for result in results} == {"would_link"}
    assert not (worktree / ".env").exists()
    assert not (worktree / "investigation.db").exists()


def test_main_checkout_is_refused(checkout):
    main, _ = checkout

    with pytest.raises(RuntimeError, match="main checkout"):
        link_runtime(main)


def test_cli_exits_nonzero_when_a_path_was_not_linked(checkout):
    _, worktree = checkout
    (worktree / "datasets").mkdir()

    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "link_worktree_runtime.py"),
         "--worktree", str(worktree)],
        capture_output=True, text=True, env=GIT_ENV,
    )

    assert completed.returncode == 1
    assert "conflict  datasets" in completed.stdout
    assert (worktree / "investigation.db").is_symlink()
