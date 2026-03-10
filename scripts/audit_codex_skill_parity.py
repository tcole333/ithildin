#!/usr/bin/env python3
"""Audit repo-local Codex skills against the definitive Claude skills."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS_DIR = ROOT / ".claude" / "skills"
CODEX_SKILLS_DIR = ROOT / ".codex" / "skills"
INTENTIONAL_ADAPTATIONS = {"deep-investigate"}


def skill_names(base: Path) -> list[str]:
    return sorted(path.name for path in base.iterdir() if path.is_dir() and not path.name.startswith("."))


def read_skill_text(base: Path, skill_name: str) -> str:
    return (base / skill_name / "SKILL.md").read_text()


def diff_preview(left: str, right: str, *, max_lines: int = 24) -> list[str]:
    lines = list(difflib.unified_diff(left.splitlines(), right.splitlines(), lineterm=""))
    if len(lines) <= max_lines:
        return lines
    head = lines[:max_lines]
    head.append(f"... ({len(lines) - max_lines} more diff line(s))")
    return head


def main() -> int:
    parser = argparse.ArgumentParser(description="Report Codex skill parity against definitive Claude skills.")
    parser.add_argument("--show-diffs", action="store_true", help="Print unified diff previews for mismatched skills")
    args = parser.parse_args()

    claude_skills = skill_names(CLAUDE_SKILLS_DIR)
    codex_skills = skill_names(CODEX_SKILLS_DIR)

    missing_in_codex = [name for name in claude_skills if name not in codex_skills]
    extra_in_codex = [name for name in codex_skills if name not in claude_skills]

    unexpected_drift: list[str] = []
    intentional_drift: list[str] = []

    for skill_name in sorted(set(claude_skills) & set(codex_skills)):
        claude_text = read_skill_text(CLAUDE_SKILLS_DIR, skill_name)
        codex_text = read_skill_text(CODEX_SKILLS_DIR, skill_name)
        if claude_text == codex_text:
            continue
        if skill_name in INTENTIONAL_ADAPTATIONS:
            intentional_drift.append(skill_name)
        else:
            unexpected_drift.append(skill_name)

        if args.show_diffs:
            print(f"\n## {skill_name}")
            for line in diff_preview(codex_text, claude_text):
                print(line)

    print(f"Claude skills: {len(claude_skills)}")
    print(f"Codex skills: {len(codex_skills)}")
    print(f"Missing in Codex: {len(missing_in_codex)}")
    for name in missing_in_codex:
        print(f"  - {name}")

    print(f"Extra in Codex: {len(extra_in_codex)}")
    for name in extra_in_codex:
        print(f"  - {name}")

    print(f"Unexpected drift: {len(unexpected_drift)}")
    for name in unexpected_drift:
        print(f"  - {name}")

    print(f"Intentional Codex adaptations: {len(intentional_drift)}")
    for name in intentional_drift:
        print(f"  - {name}")

    if missing_in_codex or unexpected_drift:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
