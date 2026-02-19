#!/usr/bin/env python3
"""Validate skills, command docs, and markdown tool-call snippets.

Default targets:
- .claude/skills (repo)
- $HOME/.codex/skills

Optional targets:
- command markdown directories (e.g. ~/.claude/commands)
- arbitrary markdown docs directories

Checks include:
- Required frontmatter keys (for skills/commands, when configured)
- No duplicate `uv run uv run`
- Optional warning for `.venv/bin/python*` and bare `python tools/...`
- Command snippets reference existing scripts (when concrete, not templated)
- Long flags appear in `--help` output for the script/subcommand (best effort)
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


FENCED_BLOCK_RE = re.compile(r"```(?:bash|sh|zsh|shell)?\n(.*?)```", re.DOTALL | re.IGNORECASE)
LONG_OPT_RE = re.compile(r"--[A-Za-z0-9][A-Za-z0-9-]*")


@dataclass
class Issue:
    level: str  # ERROR | WARN
    path: Path
    line: int
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate skill, command, and markdown docs")
    parser.add_argument(
        "--skills-dir",
        action="append",
        help="Skill directory root (repeatable). Defaults to .claude/skills and ~/.codex/skills",
    )
    parser.add_argument(
        "--commands-dir",
        action="append",
        help="Command markdown directory root (repeatable). Recursively lints *.md.",
    )
    parser.add_argument(
        "--docs-dir",
        action="append",
        help="Additional markdown docs directory root (repeatable). Recursively lints *.md.",
    )
    parser.add_argument(
        "--workspace",
        default=os.getcwd(),
        help="Workspace root used to resolve script paths (default: cwd)",
    )
    parser.add_argument(
        "--require-uv",
        action="store_true",
        help="Warn when a command starts with bare python for project tools/scripts/site paths",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero on WARN in addition to ERROR",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden skill directories such as .system",
    )
    return parser.parse_args()


def default_skill_dirs() -> list[Path]:
    return [
        Path(os.getcwd()) / ".claude" / "skills",
        Path.home() / ".codex" / "skills",
    ]


def iter_skill_files(skill_root: Path, include_hidden: bool) -> Iterable[Path]:
    if not skill_root.exists():
        return
    for child in sorted(skill_root.iterdir()):
        if not child.is_dir():
            continue
        if not include_hidden and child.name.startswith("."):
            continue
        skill_file = child / "SKILL.md"
        if skill_file.exists():
            yield skill_file


def iter_markdown_files(root: Path, include_hidden: bool) -> Iterable[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        if include_hidden:
            yield path
            continue
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        yield path


def parse_frontmatter(text: str) -> tuple[dict[str, str], int]:
    """Return frontmatter map and line offset of body start."""
    if not text.startswith("---\n"):
        return {}, 1
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, 1
    fm_raw = parts[1]
    body_start_line = fm_raw.count("\n") + 3
    fm: dict[str, str] = {}
    for line in fm_raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm, body_start_line


def join_line_continuations(block: str) -> list[str]:
    out: list[str] = []
    current = ""
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line:
            if current:
                out.append(current)
                current = ""
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
        else:
            out.append((current + line).strip())
            current = ""
    if current:
        out.append(current.strip())
    return out


def split_segments(cmd: str) -> list[str]:
    # Good enough for skill snippets; this is a lint tool, not a shell parser.
    segments = re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd)
    return [s.strip() for s in segments if s.strip()]


def likely_template_token(token: str) -> bool:
    return (
        "<" in token
        or ">" in token
        or "[" in token
        or "]" in token
        or "{{" in token
        or "}}" in token
        or "{%" in token
        or "%}" in token
        or token.startswith("$")
        or token.startswith("query_<")
        or token.startswith("ingest_<")
        or token.startswith("${")
    )


def resolve_script_path(workspace: Path, script_token: str) -> Path:
    if script_token.startswith("/"):
        return Path(script_token)
    return workspace / script_token


def help_options_cache_key(script: str, subcmd: str | None) -> tuple[str, str | None]:
    return (script, subcmd)


def read_help_options(
    workspace: Path,
    script: str,
    subcmd: str | None,
    cache: dict[tuple[str, str | None], set[str]],
) -> set[str]:
    key = help_options_cache_key(script, subcmd)
    if key in cache:
        return cache[key]

    cmd = ["uv", "run", "python", script]
    if subcmd:
        cmd.append(subcmd)
    cmd.append("--help")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except Exception:
        cache[key] = set()
        return cache[key]

    opts = set(LONG_OPT_RE.findall(text))
    cache[key] = opts
    return opts


def line_number_of(text: str, needle: str, start: int = 1) -> int:
    idx = text.find(needle)
    if idx < 0:
        return start
    return text[:idx].count("\n") + 1


def lint_markdown_file(
    md_file: Path,
    workspace: Path,
    require_uv: bool,
    include_hidden: bool,  # kept for signature symmetry and future use
    help_cache: dict[tuple[str, str | None], set[str]],
    required_frontmatter_fields: tuple[str, ...] | None,
) -> list[Issue]:
    del include_hidden
    issues: list[Issue] = []
    text = md_file.read_text(encoding="utf-8", errors="replace")

    if required_frontmatter_fields is not None:
        fm, _ = parse_frontmatter(text)
        if not fm:
            issues.append(Issue("ERROR", md_file, 1, "Missing or malformed YAML frontmatter"))
        else:
            for key in required_frontmatter_fields:
                if key not in fm:
                    issues.append(Issue("ERROR", md_file, 1, f"Frontmatter missing `{key}`"))

    if "uv run uv run" in text:
        issues.append(
            Issue(
                "ERROR",
                md_file,
                line_number_of(text, "uv run uv run"),
                "Found duplicate `uv run uv run` prefix",
            )
        )
    if require_uv and re.search(r"\.venv/bin/python(?:3)?", text):
        issues.append(
            Issue(
                "WARN",
                md_file,
                line_number_of(text, ".venv/bin/python"),
                "Found `.venv/bin/python*` hardcoded invocation",
            )
        )

    for block in FENCED_BLOCK_RE.findall(text):
        lines = join_line_continuations(block)
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            if line.startswith(("Read(", "Write(", "WebSearch", "WebFetch")):
                continue

            # remove list markers / numeric prefixes
            line = re.sub(r"^\d+\.\s+", "", line)
            line = re.sub(r"^-\s+", "", line)
            line = re.sub(r"^Bash:\s*", "", line)
            line = re.sub(r"^\$\s+", "", line)

            for segment in split_segments(line):
                try:
                    tokens = shlex.split(segment)
                except ValueError:
                    continue
                if not tokens:
                    continue

                # Optional style check for bare python.
                if require_uv and len(tokens) >= 2 and tokens[0] == "python":
                    if tokens[1].startswith(("tools/", "scripts/", "site/")):
                        issues.append(
                            Issue(
                                "WARN",
                                md_file,
                                line_number_of(text, raw_line),
                                f"Bare python invocation should use `uv run python`: {segment}",
                            )
                        )

                # Validate only uv python segments.
                if len(tokens) < 4 or tokens[:3] != ["uv", "run", "python"]:
                    continue

                script = tokens[3]
                if script.startswith("-"):
                    continue  # e.g. uv run python -c
                if likely_template_token(script):
                    continue

                script_path = resolve_script_path(workspace, script)
                if not script_path.exists():
                    issues.append(
                        Issue(
                            "ERROR",
                            md_file,
                            line_number_of(text, raw_line),
                            f"Script not found: {script}",
                        )
                    )
                    continue

                remaining = tokens[4:]
                subcmd = None
                for tok in remaining:
                    if tok.startswith("-"):
                        continue
                    if likely_template_token(tok):
                        continue
                    subcmd = tok
                    break

                root_opts = read_help_options(workspace, script, None, help_cache)
                sub_opts = read_help_options(workspace, script, subcmd, help_cache) if subcmd else set()
                allowed = root_opts | sub_opts
                if not allowed:
                    continue

                flags = []
                for tok in remaining:
                    if not tok.startswith("--"):
                        continue
                    flag = tok.split("=", 1)[0]
                    if likely_template_token(flag):
                        continue
                    flags.append(flag)

                for flag in flags:
                    if flag not in allowed:
                        issues.append(
                            Issue(
                                "WARN",
                                md_file,
                                line_number_of(text, raw_line),
                                f"Possibly invalid flag `{flag}` for `{script}`"
                                + (f" subcommand `{subcmd}`" if subcmd else ""),
                            )
                        )

    return issues


def print_report(issues: list[Issue]) -> None:
    if not issues:
        print("No issues found.")
        return
    for i in issues:
        print(f"{i.level:5} {i.path}:{i.line}  {i.message}")
    errors = sum(1 for i in issues if i.level == "ERROR")
    warns = sum(1 for i in issues if i.level == "WARN")
    print(f"\nSummary: {errors} errors, {warns} warnings")


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    skill_dirs = [Path(p).expanduser() for p in (args.skills_dir or [str(p) for p in default_skill_dirs()])]
    command_dirs = [Path(p).expanduser() for p in (args.commands_dir or [])]
    docs_dirs = [Path(p).expanduser() for p in (args.docs_dir or [])]

    all_issues: list[Issue] = []
    help_cache: dict[tuple[str, str | None], set[str]] = {}
    checked = 0
    seen: set[Path] = set()

    for skill_root in skill_dirs:
        if not skill_root.exists():
            print(f"WARN  {skill_root} does not exist; skipping")
            continue
        for skill_file in iter_skill_files(skill_root, args.include_hidden):
            resolved = skill_file.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            checked += 1
            all_issues.extend(
                lint_markdown_file(
                    md_file=skill_file,
                    workspace=workspace,
                    require_uv=args.require_uv,
                    include_hidden=args.include_hidden,
                    help_cache=help_cache,
                    required_frontmatter_fields=("name", "description"),
                )
            )

    for command_root in command_dirs:
        if not command_root.exists():
            print(f"WARN  {command_root} does not exist; skipping")
            continue
        for md_file in iter_markdown_files(command_root, args.include_hidden):
            resolved = md_file.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            checked += 1
            all_issues.extend(
                lint_markdown_file(
                    md_file=md_file,
                    workspace=workspace,
                    require_uv=args.require_uv,
                    include_hidden=args.include_hidden,
                    help_cache=help_cache,
                    required_frontmatter_fields=("description",),
                )
            )

    for docs_root in docs_dirs:
        if not docs_root.exists():
            print(f"WARN  {docs_root} does not exist; skipping")
            continue
        for md_file in iter_markdown_files(docs_root, args.include_hidden):
            resolved = md_file.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            checked += 1
            all_issues.extend(
                lint_markdown_file(
                    md_file=md_file,
                    workspace=workspace,
                    require_uv=args.require_uv,
                    include_hidden=args.include_hidden,
                    help_cache=help_cache,
                    required_frontmatter_fields=None,
                )
            )

    print(f"Checked {checked} markdown files.")
    print_report(all_issues)

    errors = any(i.level == "ERROR" for i in all_issues)
    warns = any(i.level == "WARN" for i in all_issues)
    if errors:
        return 1
    if args.strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
