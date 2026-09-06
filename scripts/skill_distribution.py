#!/usr/bin/env python3
"""Check project skill discovery; inventory or back up personal collisions.

No command overwrites, removes, or installs personal skills. Inventory does not
read unrelated skill bodies. Backups are opt-in and preserve symlinks as links.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tree_manifest(root: Path) -> dict:
    if root.is_symlink():
        return {'.': {'symlink': os.readlink(root)}}
    if root.is_file():
        return {'.': {'sha256': hashlib.sha256(root.read_bytes()).hexdigest(), 'size': root.stat().st_size}}
    result = {}
    if not root.exists():
        return result
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            rel = str(path.relative_to(root))
            if '__pycache__' in path.parts or name == '.DS_Store':
                continue
            if path.is_symlink():
                result[rel] = {'symlink': os.readlink(path)}
            elif path.is_file():
                result[rel] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size}
    return result


def check(workspace: Path) -> dict:
    canonical = workspace / '.codex/skills'
    discovery = workspace / '.agents/skills'
    skills = sorted(p.parent.name for p in canonical.glob('*/SKILL.md'))
    valid = canonical.is_dir() and bool(skills) and discovery.is_dir() and discovery.resolve() == canonical.resolve()
    return {'status': 'ok' if valid else 'error', 'canonical': str(canonical), 'discovery': str(discovery),
            'skill_count': len(skills), 'skills': skills,
            'detail': 'Repository discovery resolves to canonical skills.' if valid else
            'Expected .agents/skills -> ../.codex/skills; existing paths are never replaced automatically.'}


def inventory(workspace: Path, personal: Path) -> dict:
    canonical = workspace / '.codex/skills'
    if not canonical.is_dir():
        raise ValueError(f'Canonical skill root does not exist: {canonical}')
    names = sorted(p.parent.name for p in canonical.glob('*/SKILL.md'))
    entries = []
    for name in names:
        target = personal / name
        if not target.exists() and not target.is_symlink():
            continue
        original, current = tree_manifest(target), tree_manifest(canonical / name)
        same = original == current or target.is_symlink() and target.resolve() == (canonical / name).resolve()
        entries.append({'name': name, 'personal_path': str(target),
                        'status': 'identical' if same else 'different_preserve',
                        'personal_manifest': original, 'repository_manifest': current,
                        'next_step': 'Back up and review this collision before any separately authorized retirement.'})
    unrelated = sorted(p.name for p in personal.iterdir() if p.name not in names) if personal.is_dir() else []
    return {'schema_version': 1, 'status': 'inventory', 'workspace': str(workspace),
            'personal_root': str(personal), 'collisions': entries, 'unrelated_preserved': unrelated,
            'policy': 'No personal path is changed. Different content may be a user edit, not merely stale.'}


def backup(workspace: Path, personal: Path, destination: Path) -> dict:
    personal, destination = personal.resolve(), destination.resolve()
    if destination == personal or personal in destination.parents:
        raise ValueError('Backup destination must be outside the personal skill root')
    report = inventory(workspace, personal)
    destination.mkdir(parents=True, exist_ok=False)
    report['status'] = 'backup_incomplete'
    report['backup_root'] = str(destination)
    manifest_file = destination / 'manifest.json'
    manifest_file.write_text(json.dumps(report, indent=2) + '\n')
    for entry in report['collisions']:
        source = personal / entry['name']
        target = destination / entry['name']
        if source.is_symlink():
            target.symlink_to(os.readlink(source), target_is_directory=True)
        elif source.is_dir():
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target, follow_symlinks=False)
        if tree_manifest(target) != entry['personal_manifest'] or tree_manifest(source) != entry['personal_manifest']:
            raise ValueError(f"Backup verification failed for {entry['name']}; preserve the incomplete backup and retry into a new destination")
    report['status'] = 'backed_up_originals_preserved'
    manifest_file.write_text(json.dumps(report, indent=2) + '\n')
    return report


def validate_output_destination(output: Path | None, workspace: Path, personal: Path, destination: Path | None = None) -> None:
    if output is None:
        return
    output = output.expanduser()
    resolved = output.resolve()
    protected = [personal.resolve(), workspace / '.codex/skills', workspace / '.claude/skills', workspace / '.agents/skills']
    if destination is not None:
        protected.append(destination.expanduser().resolve())
    if any(resolved == root.resolve() or root.resolve() in resolved.parents for root in protected):
        raise ValueError('Report output must be outside personal/managed skill roots and the backup destination')
    # Exclusive output creation also protects hardlink aliases and unrelated
    # existing files outside the named roots. Never silently replace a report.
    if output.exists() or output.is_symlink():
        raise ValueError('Report output already exists; choose a new report path')
    if not output.parent.is_dir():
        raise ValueError('Report output parent directory does not exist')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=ROOT)
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('check', help='Check the version-controlled repository discovery link')
    for name in ('inventory', 'backup'):
        command = sub.add_parser(name, help='Inspect personal collisions' if name == 'inventory' else 'Copy collisions to a new verified backup; preserve originals')
        command.add_argument('--personal-root', type=Path, required=True)
        command.add_argument('--output', type=Path)
        if name == 'backup':
            command.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()
    try:
        if args.command in {'inventory', 'backup'}:
            if args.output is not None:
                args.output = args.output.expanduser()
            validate_output_destination(args.output, workspace, args.personal_root.expanduser(), getattr(args, 'destination', None))
        if args.command in (None, 'check'):
            report = check(workspace)
        elif args.command == 'inventory':
            report = inventory(workspace, args.personal_root.expanduser().absolute())
        else:
            report = backup(workspace, args.personal_root.expanduser().absolute(), args.destination.expanduser().resolve())
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    payload = json.dumps(report, indent=2) + '\n'
    if getattr(args, 'output', None):
        with args.output.open("x") as report_file:
            report_file.write(payload)
        print(f"{report['status']}: {args.output}")
    else:
        print(payload, end='')
    return int(report['status'] == 'error')


if __name__ == '__main__':
    raise SystemExit(main())
