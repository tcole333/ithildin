#!/usr/bin/env python3
"""Validate publication inputs once, then stage and verify the exact deploy artifact.

No investigation database is read. Missing review receipts or finding snapshots
are publication debt and fail this command; deterministic PR checks run separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_NAME = "release-receipt.json"


def file_manifest(directory: Path) -> dict[str, str]:
    if directory.is_symlink():
        raise ValueError(f"Release inputs cannot contain symlinks: {directory}")
    manifest = {}
    for file in sorted(directory.rglob("*")):
        if file.is_symlink():
            raise ValueError(f"Release inputs cannot contain symlinks: {file}")
        if file.is_file():
            manifest[file.relative_to(directory).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    if not manifest:
        raise ValueError(f"Release directory contains no files: {directory}")
    return manifest


def stage_artifact(content_dir: Path, build_dir: Path, artifact_dir: Path) -> dict:
    destination = artifact_dir.resolve()
    for source in (content_dir.resolve(), build_dir.resolve()):
        if destination == source or destination in source.parents or source in destination.parents:
            raise ValueError("Artifact directory must not overlap content or build inputs")
    if artifact_dir.exists():
        raise ValueError(f"Artifact directory already exists; choose a fresh destination: {artifact_dir}")
    # Inspect before copying; external symlinks must never enter an artifact.
    inputs = file_manifest(content_dir)
    files = file_manifest(build_dir)
    artifact_dir.mkdir(parents=True)
    shutil.copytree(build_dir, artifact_dir / "site")
    receipt = {"schema_version": 1, "content_sha256": inputs, "files_sha256": files}
    (artifact_dir / RECEIPT_NAME).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    verify_artifact(artifact_dir)
    return receipt


def verify_artifact(artifact_dir: Path) -> dict:
    if artifact_dir.is_symlink():
        raise ValueError(f"Release inputs cannot contain symlinks: {artifact_dir}")
    receipt_file = artifact_dir / RECEIPT_NAME
    if receipt_file.is_symlink():
        raise ValueError(f"Release inputs cannot contain symlinks: {receipt_file}")
    receipt = json.loads(receipt_file.read_text())
    if (not isinstance(receipt, dict) or type(receipt.get("schema_version")) is not int
            or receipt["schema_version"] != 1 or not isinstance(receipt.get("files_sha256"), dict)):
        raise ValueError("Unsupported or invalid release receipt")
    actual = file_manifest(artifact_dir / "site")
    expected = receipt["files_sha256"]
    if actual != expected:
        changed = sorted(key for key in actual.keys() | expected.keys() if actual.get(key) != expected.get(key))
        raise ValueError("Release artifact differs from validated build: " + ", ".join(changed[:20]))
    return receipt


def run_step(label: str, command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print(f"Validating {label}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def validate(args: argparse.Namespace) -> None:
    initial_content = file_manifest(args.content_dir)
    content_dir = args.content_dir.resolve()
    snapshot = (args.snapshot or content_dir / "finding-catalog.json").resolve()
    receipts = (args.receipts or content_dir / "dossier-review-receipts.json").resolve()
    env = {
        **os.environ,
        "ITHILDIN_CONTENT_DIR": str(content_dir),
        "ITHILDIN_FINDING_SNAPSHOT": str(snapshot),
        "PUBLIC_ENABLE_EVIDENCE_MODE": "false",
    }
    # Keep source corpus and review requirements before expensive tests/builds.
    run_step("finding snapshot", [
        sys.executable, "pipeline/publication_snapshot.py", "check",
        "--content-dir", str(content_dir), "--snapshot", str(snapshot),
    ], cwd=ROOT, env=env)
    run_step("semantic review receipts", [
        sys.executable, "scripts/review_dossier_checks.py", "validate-receipts",
        "--receipt-file", str(receipts), "--json",
    ], cwd=ROOT, env=env)
    run_step("Python regressions", [
        sys.executable, "-m", "pytest", "--offline", "--require-critical-tests", "-m", "not live_data", "-q",
    ], cwd=ROOT, env=env)
    for command in ("check", "test:frontend", "test:frontend:browser", "lint:citations"):
        run_step(command, ["npm", "run", command], cwd=ROOT / "web", env=env)
    run_step("production build", ["npm", "run", "build"], cwd=ROOT / "web", env=env)
    run_step("built citation checks", ["npm", "run", "test:citations:build"], cwd=ROOT / "web", env=env)
    if file_manifest(content_dir) != initial_content:
        raise ValueError("Publication content changed during validation; review and rerun")
    stage_artifact(content_dir, ROOT / "web" / "dist", args.artifact_dir.resolve())
    print(f"Validated artifact: {args.artifact_dir.resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="Validate reviewed content, test, build, and stage publication")
    check.add_argument("--content-dir", type=Path, default=ROOT / "content")
    check.add_argument("--snapshot", type=Path)
    check.add_argument("--receipts", type=Path)
    check.add_argument("--artifact-dir", type=Path, required=True, help="Fresh output directory")
    verify = sub.add_parser("verify-artifact", help="Reject changed/missing/extra built artifact files")
    verify.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate(args)
        else:
            receipt = verify_artifact(args.artifact_dir)
            print(f"Artifact verified: {len(receipt['files_sha256'])} files")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Release validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
