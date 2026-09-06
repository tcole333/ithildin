#!/usr/bin/env python3
"""Compare shared skill instructions after documented runtime normalization."""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path

import yaml

try:
    from scripts.skill_metadata import CLAUDE_SKILL_KEYS, FRONTMATTER_RE, normalized_runtime_text
except ModuleNotFoundError:
    from skill_metadata import CLAUDE_SKILL_KEYS, FRONTMATTER_RE, normalized_runtime_text

ROOT = Path(__file__).resolve().parents[1]
# Runtime-exclusive workflows are listed deliberately, never treated as missing mirrors.
CODEX_ONLY = frozenset({'audit-skills', 'discover-investigations', 'fix-papercuts'})


def skill_names(base: Path) -> set[str]:
    return {path.parent.name for path in base.glob('*/SKILL.md')}


def adapter_metadata(text: str) -> dict:
    match = FRONTMATTER_RE.match(text)
    data = yaml.safe_load(match.group(1)) if match else {}
    return {key: value for key, value in (data or {}).items() if key in CLAUDE_SKILL_KEYS}


def shared_files(base: Path, name: str) -> dict[str, Path]:
    root = base / name
    files = {'SKILL.md': root / 'SKILL.md'}
    for directory in ('references', 'scripts', 'assets'):
        for path in (root / directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                files[str(path.relative_to(root))] = path
    return files


def audit(workspace: Path, show_diffs: bool = False) -> int:
    claude = workspace / '.claude/skills'
    codex = workspace / '.codex/skills'
    if not claude.is_dir() or not codex.is_dir():
        print('Both repository runtime skill roots are required.')
        return 1
    left_names, right_names = skill_names(claude), skill_names(codex)
    names = left_names | right_names
    missing = left_names - right_names
    unexpected_extra = right_names - left_names - CODEX_ONLY
    print(f'Claude skills: {len(left_names)}; Codex skills: {len(right_names)}')
    print('Codex-only packages: ' + (', '.join(sorted(right_names - left_names)) or 'none'))
    for name in sorted(missing | unexpected_extra):
        print(f'Unpaired runtime package requires an explicit ownership decision: {name}')
    drift = []
    for name in sorted(left_names & right_names):
        left, right = shared_files(claude, name), shared_files(codex, name)
        for rel in sorted(set(left) | set(right)):
            if rel not in left or rel not in right:
                drift.append(f'{name}/{rel}')
                continue
            a, b = left[rel].read_bytes(), right[rel].read_bytes()
            if rel.endswith('.md'):
                a = normalized_runtime_text(a.decode(), names)
                b = normalized_runtime_text(b.decode(), names)
            if a != b:
                drift.append(f'{name}/{rel}')
                if show_diffs and isinstance(a, str):
                    print('\n'.join(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                                      fromfile=str(left[rel]), tofile=str(right[rel]), lineterm='')))
        metadata = adapter_metadata(left['SKILL.md'].read_text())
        if metadata and metadata != {'user-invocable': True}:
            print(f'Claude adapter metadata {name}: {metadata}')
    print(f'Shared instruction/resource drift: {len(drift)}')
    for item in drift:
        print(f'  - {item}')
    return int(bool(missing or unexpected_extra or drift))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=ROOT)
    parser.add_argument('--show-diffs', action='store_true')
    args = parser.parse_args()
    return audit(args.workspace.resolve(), args.show_diffs)


if __name__ == '__main__':
    raise SystemExit(main())
