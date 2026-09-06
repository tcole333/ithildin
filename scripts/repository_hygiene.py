#!/usr/bin/env python3
"""Check the Git index or a commit diff without reading unstaged file contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath


MAX_BLOB_BYTES = 5 * 1024 * 1024
ROOT_ARTIFACT_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".csv", ".txt", ".mp4", ".wav"}
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")
TOKEN_PATTERNS = (
    re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(rb"\bsk-(?:proj-|svcacct-)[A-Za-z0-9_-]{40,}\b"),
)
COMMIT_SUBJECT = re.compile(
    r"^(?:feat|fix|refactor|test|docs|chore|build|ci|data|research)"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?!?: \S.{5,98}$"
)


@dataclass(frozen=True)
class Violation:
    path: str
    rule: str
    message: str


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def repository_root() -> Path:
    return Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())


def forbidden_path(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    name = parts[-1]
    if name in {".env", ".envrc"} or (name.startswith(".env.") and name not in {".env.example", ".env.sample", ".env.template"}):
        return "Credential environment files stay local; commit a value-free example."
    local_parts = {"node_modules", "__pycache__", ".cache", ".venv", ".dispatch_staging", ".playwright-cli", ".playwright-mcp"}
    if any(part in local_parts for part in parts) or parts[0] in {"backups", "datasets", "output", "outputs", "scratchpad", "tmp", "workbench-agents"}:
        return "Local data, caches, and disposable outputs stay outside Git."
    if parts[:2] in {("web", "dist"), ("web", "test-results")}:
        return "Generated builds and test output stay outside Git."
    if len(parts) == 1 and PurePosixPath(path).suffix.lower() in ROOT_ARTIFACT_SUFFIXES:
        return "Put reviewed assets in their owning directory; keep acquisition output local."
    if re.search(r"\.(?:db|sqlite|sqlite3)(?:$|[-.])", name) and parts[:2] != ("tests", "fixtures"):
        return "Runtime databases stay local; small deliberate test fixtures belong in tests/fixtures."
    return None


def inspect_blob(path: str, data: bytes, *, large_files: dict | None = None) -> list[Violation]:
    violations = []
    reason = forbidden_path(path)
    if reason:
        violations.append(Violation(path, "local-artifact", reason))
    if len(data) > MAX_BLOB_BYTES:
        exception = (large_files or {}).get(path, {})
        if not (
            exception.get("reason")
            and exception.get("sha256") == hashlib.sha256(data).hexdigest()
        ):
            violations.append(Violation(path, "large-blob", "Blob exceeds 5 MiB; use local storage plus a manifest, or an exact reviewed hash exception."))
    if PRIVATE_KEY.search(data) or any(pattern.search(data) for pattern in TOKEN_PATTERNS):
        violations.append(Violation(path, "credential", "Possible private key or service credential; remove the value before committing."))
    return violations


def changed_blobs(root: Path, *, base: str | None = None, head: str = "HEAD") -> list[tuple[str, str]]:
    if base:
        paths = git(root, "diff", "--name-only", "--diff-filter=ACMRT", "-z", base, head).split(b"\0")
        rows = git(root, "ls-tree", "-r", "-z", head).split(b"\0")
    else:
        paths = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z").split(b"\0")
        rows = git(root, "ls-files", "--stage", "-z").split(b"\0")
    selected = {p.decode() for p in paths if p}
    blobs = []
    for row in rows:
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        mode, field, third = metadata.split()
        path = raw_path.decode()
        if path not in selected or mode == b"160000":
            continue
        if base:
            if field != b"blob":
                continue
            oid = third.decode()
        else:
            if third != b"0":
                raise ValueError(f"Unresolved index entry: {path}")
            oid = field.decode()
        blobs.append((path, oid))
    return blobs


def check(root: Path, *, base: str | None = None, head: str = "HEAD", check_branch: bool = True) -> list[Violation]:
    violations = []
    if check_branch:
        branch = git(root, "branch", "--show-current").decode().strip()
        if not branch or branch in {"main", "master"}:
            violations.append(Violation("HEAD", "branch", "Create a workstream branch before committing; main/master and detached HEAD are integration states."))
    # Read policy from the same staged/committed state that is being validated.
    spec = f"{head}:config/repository_policy.json" if base else ":config/repository_policy.json"
    result = subprocess.run(["git", "-C", str(root), "show", spec], capture_output=True, check=False)
    policy = json.loads(result.stdout) if result.returncode == 0 else {}
    for path, oid in changed_blobs(root, base=base, head=head):
        data = git(root, "cat-file", "blob", oid)
        violations.extend(inspect_blob(path, data, large_files=policy.get("large_files")))
    return violations


def check_commit_message(text: str) -> str | None:
    subject = next((line for line in text.splitlines() if line and not line.startswith("#")), "")
    if not COMMIT_SUBJECT.fullmatch(subject) or len(subject) > 100:
        return "Use type(scope): concrete result, at most 100 characters (for example: fix(evidence): invalidate verification after claim edits)."
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    checks = sub.add_parser("check", help="Validate staged blobs, or changed blobs between two commits")
    checks.add_argument("--staged", action="store_true", help="Check the index (default)")
    checks.add_argument("--base", help="Diff base for CI")
    checks.add_argument("--head", default="HEAD")
    checks.add_argument("--no-branch-check", action="store_true", help="For detached CI checkouts; content rules still apply")
    checks.add_argument("--json", action="store_true")
    message = sub.add_parser("commit-message", help="Validate a proposed commit message")
    message.add_argument("file", type=Path)
    args = parser.parse_args()
    if args.command == "commit-message":
        error = check_commit_message(args.file.read_text())
        if error:
            print(error, file=sys.stderr)
        return int(bool(error))
    if args.staged and args.base:
        parser.error("--staged and --base are mutually exclusive")
    try:
        violations = check(repository_root(), base=args.base, head=args.head, check_branch=not args.no_branch_check)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"Repository check failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"passed": not violations, "violations": [asdict(v) for v in violations]}, indent=2))
    else:
        for violation in violations:
            print(f"{violation.path}: {violation.rule}: {violation.message}", file=sys.stderr)
        if not violations:
            print("Repository staged/commit checks passed.")
    return int(bool(violations))


if __name__ == "__main__":
    raise SystemExit(main())
