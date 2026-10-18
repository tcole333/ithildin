#!/usr/bin/env python3
"""Link the main checkout's ignored runtime files into a git worktree.

Credentials, runtime databases, and bulk datasets are ignored by Git, so a new
worktree starts without them, and a tool that opens a missing database used to
create an empty stand-in and report false zero results. This script symlinks
the main checkout's copies into the worktree (never copies them), so every
worktree reads and writes the same shared files. Existing files are never
replaced; they are reported for review instead.

Usage:
    uv run python scripts/link_worktree_runtime.py                  # current worktree
    uv run python scripts/link_worktree_runtime.py --worktree PATH
    uv run python scripts/link_worktree_runtime.py --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

RUNTIME_PATHS = (".env", "datasets", "registry.db", "investigation.db")
# Ignored entries inside this tracked directory are linked one by one.
DATA_DIR = "data"
SKIPPED_NAMES = frozenset({".DS_Store"})
# SQLite keeps these beside the resolved database file; never link them.
SQLITE_SIDE_SUFFIXES = ("-wal", "-shm", "-journal")


@dataclass(frozen=True)
class LinkResult:
    path: str
    status: str  # linked, would_link, already_linked, missing_source, conflict
    detail: str


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout


def main_checkout(worktree: Path) -> Path:
    """Return the repository's main working tree, which Git lists first."""
    for line in _git(worktree, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree "))
    raise RuntimeError(f"git worktree list returned no worktrees for {worktree}")


def ignored_data_entries(main: Path) -> list[str]:
    """List the main checkout's ignored files and directories under data/."""
    # The trailing slash matters: with --directory, a bare "data" pathspec
    # also reports the sibling "datasets/" directory.
    listing = _git(
        main, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory",
        "--", f"{DATA_DIR}/",
    )
    entries = []
    for line in listing.splitlines():
        relative = line.rstrip("/")
        name = PurePosixPath(relative).name
        if name in SKIPPED_NAMES or name.endswith(SQLITE_SIDE_SUFFIXES):
            continue
        entries.append(relative)
    return entries


def _conflict_detail(target: Path) -> str:
    if target.is_symlink():
        return f"symlink to {target.readlink()} left unchanged"
    if target.is_dir():
        return "existing directory left unchanged"
    return (
        f"existing {target.stat().st_size:,}-byte file left unchanged; if it is an empty "
        "stand-in created by an older tool, move it aside and rerun"
    )


def link_runtime(
    worktree: Path, main: Path | None = None, *, dry_run: bool = False
) -> list[LinkResult]:
    """Symlink each ignored runtime path of ``main`` into ``worktree``."""
    worktree = worktree.resolve()
    main = (main or main_checkout(worktree)).resolve()
    if worktree == main:
        raise RuntimeError(f"{worktree} is the main checkout; there is nothing to link")

    results = []
    for relative in (*RUNTIME_PATHS, *ignored_data_entries(main)):
        source = main / relative
        target = worktree / relative
        if not source.exists():
            results.append(LinkResult(relative, "missing_source", f"{source} does not exist"))
        elif target.is_symlink() and target.resolve() == source.resolve():
            results.append(LinkResult(relative, "already_linked", str(source)))
        elif target.is_symlink() or target.exists():
            results.append(LinkResult(relative, "conflict", _conflict_detail(target)))
        elif dry_run:
            results.append(LinkResult(relative, "would_link", str(source)))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source, target_is_directory=source.is_dir())
            results.append(LinkResult(relative, "linked", str(source)))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--worktree", type=Path, default=Path.cwd(),
        help="Worktree to populate (default: the current directory's worktree)",
    )
    parser.add_argument(
        "--main", type=Path, help="Main checkout to link from (default: from git worktree list)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Report without creating links")
    args = parser.parse_args(argv)

    try:
        worktree = Path(_git(args.worktree, "rev-parse", "--show-toplevel").strip())
        results = link_runtime(worktree, args.main, dry_run=args.dry_run)
    except subprocess.CalledProcessError as error:
        print(f"ERROR: {' '.join(error.cmd)} failed: {error.stderr.strip()}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    for result in results:
        print(f"{result.status:>15}  {result.path}  {result.detail}", flush=True)
    conflicts = [result for result in results if result.status == "conflict"]
    if conflicts:
        print(
            f"{len(conflicts)} path(s) already exist in {worktree} and were not linked.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
