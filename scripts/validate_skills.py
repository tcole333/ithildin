#!/usr/bin/env python3
"""Validate repository skills and documented CLI help contracts.

Runtime metadata follows the documented Claude Code / Agent Skills fields.
Command checks reconstruct declarative argparse interfaces without importing
applications or executing --help/actions. Dynamic declarations are reported as
unverified; runtime availability is a separate explicit health check. Scope defaults to this repo;
personal skills require an explicit --skills-dir.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

try:
    from scripts.cli_contract import inspect_contract, select_parser
    from scripts.skill_metadata import BASE_SKILL_KEYS, CLAUDE_SKILL_KEYS, runtime_for_path, runtime_metadata_errors
except ModuleNotFoundError:  # direct script invocation
    from cli_contract import inspect_contract, select_parser
    from skill_metadata import BASE_SKILL_KEYS, CLAUDE_SKILL_KEYS, runtime_for_path, runtime_metadata_errors


FENCED_BLOCK_RE = re.compile(r"```(?:bash|sh|zsh|shell)?\n(.*?)```", re.DOTALL | re.IGNORECASE)
LONG_OPT_RE = re.compile(r"--[A-Za-z0-9][A-Za-z0-9-]*")
SKILL_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

# Kept as a public constant for callers; runtime selection is enforced below.
ALLOWED_SKILL_KEYS = BASE_SKILL_KEYS | CLAUDE_SKILL_KEYS

MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024
MAX_SKILL_COMPATIBILITY_LENGTH = 500


@dataclass
class Issue:
    level: str  # ERROR | WARN
    path: Path
    line: int
    message: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate skill, command, and markdown docs")
    parser.add_argument(
        "--skills-dir",
        action="append",
        help="Skill directory root (repeatable). Defaults to repository .claude/skills and .agents/skills (.codex fallback)",
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
        help="Warn when a command starts with bare python for project tools/scripts paths",
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
    return parser.parse_args(argv)


def default_skill_dirs() -> list[Path]:
    cwd = Path(os.getcwd())
    return [
        cwd / ".claude" / "skills",
        cwd / ".agents" / "skills" if (cwd / ".agents" / "skills").exists() else cwd / ".codex" / "skills",
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


def validate_skill_frontmatter(text: str, runtime: str = "generic") -> list[str]:
    """Validate shared fields and only the chosen runtime's documented extensions."""
    if not text.startswith("---"):
        return ["No YAML frontmatter found"]
    match = SKILL_FRONTMATTER_RE.match(text)
    if not match:
        return ["Invalid frontmatter format (missing closing '---')"]
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return [f"Invalid YAML in frontmatter: {exc}"]
    if not isinstance(frontmatter, dict):
        return ["Frontmatter must be a YAML dictionary"]

    errors = runtime_metadata_errors(frontmatter, runtime)
    errors.extend(_skill_name_errors(frontmatter))
    errors.extend(_skill_description_errors(frontmatter))
    errors.extend(_skill_compatibility_errors(frontmatter))
    return errors


def _skill_name_errors(frontmatter: dict) -> list[str]:
    if "name" not in frontmatter:
        return ["Missing `name` in frontmatter"]
    name = frontmatter["name"]
    if not isinstance(name, str):
        return [f"`name` must be a string, got {type(name).__name__}"]
    name = name.strip()
    if not name:
        return ["`name` must not be empty"]
    errors: list[str] = []
    if not re.fullmatch(r"[a-z0-9-]+", name):
        errors.append(f"Name '{name}' should be kebab-case (lowercase letters, digits, hyphens)")
    elif name.startswith("-") or name.endswith("-") or "--" in name:
        errors.append(f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens")
    if len(name) > MAX_SKILL_NAME_LENGTH:
        errors.append(
            f"Name is too long ({len(name)} characters). Maximum is {MAX_SKILL_NAME_LENGTH}."
        )
    return errors


def _skill_description_errors(frontmatter: dict) -> list[str]:
    if "description" not in frontmatter:
        return ["Missing `description` in frontmatter"]
    description = frontmatter["description"]
    if not isinstance(description, str):
        return [f"`description` must be a string, got {type(description).__name__}"]
    description = description.strip()
    if not description:
        return ["`description` must not be empty"]
    errors: list[str] = []
    if "<" in description or ">" in description:
        errors.append("Description cannot contain angle brackets (< or >)")
    if len(description) > MAX_SKILL_DESCRIPTION_LENGTH:
        errors.append(
            f"Description is too long ({len(description)} characters). "
            f"Maximum is {MAX_SKILL_DESCRIPTION_LENGTH}."
        )
    return errors


def _skill_compatibility_errors(frontmatter: dict) -> list[str]:
    compatibility = frontmatter.get("compatibility")
    if compatibility is None:
        return []
    if not isinstance(compatibility, str):
        return [f"`compatibility` must be a string, got {type(compatibility).__name__}"]
    if len(compatibility) > MAX_SKILL_COMPATIBILITY_LENGTH:
        return [
            f"Compatibility is too long ({len(compatibility)} characters). "
            f"Maximum is {MAX_SKILL_COMPATIBILITY_LENGTH}."
        ]
    return []


def join_line_continuations(block: str) -> list[tuple[str, int]]:
    """Return shell lines with their original zero-based block line offset."""
    out = []
    current = ""
    start = 0
    for offset, raw in enumerate(block.splitlines()):
        line = raw.rstrip()
        if not current:
            start = offset
        if not line:
            if current:
                out.append((current, start))
                current = ""
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
        else:
            out.append(((current + line).strip(), start))
            current = ""
    if current:
        out.append((current.strip(), start))
    return out


def split_segments(cmd: str) -> list[str]:
    """Split shell operators without splitting quoted evidence or query text."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    segments, current = [], []
    try:
        tokens = list(lexer)
    except ValueError:
        return [cmd]  # the caller handles an incomplete/template shell line
    for token in tokens:
        if token in {"&&", "||", ";", "|"}:
            if current:
                segments.append(shlex.join(current))
                current = []
        else:
            current.append(token)
    if current:
        segments.append(shlex.join(current))
    return segments


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


@dataclass
class HelpResult:
    options: set[str]
    value_options: set[str]
    subcommands: set[str]
    error: str | None = None
    option_nargs: dict[str, int | str | None] = field(default_factory=dict)


def read_command_help(
    workspace: Path,
    script: str,
    command_path: tuple[str, ...],
    cache: dict,
) -> HelpResult:
    key = (script, command_path)
    if key in cache:
        return cache[key]
    # Read declarations, not application imports. Even --help can mutate state
    # when a tool performs work at import time; the linter must not execute it.
    contract_key = (script, "__contract__")
    if contract_key not in cache:
        cache[contract_key] = inspect_contract(resolve_script_path(workspace, script))
    contract = cache[contract_key]
    error = None
    parser = select_parser(contract.parser, list(command_path)) if contract.parser and command_path else contract.parser
    if parser is None:
        error = "No statically inspectable argparse contract; runtime --help was not executed"
    elif contract.limitations:
        error = "Partial CLI declarations; runtime --help was not executed: " + "; ".join(contract.limitations[:3])
    options = set()
    value_options = set()
    subcommands = set()
    option_nargs = {}
    if parser is not None:
        for action in parser._actions:
            options.update(option for option in action.option_strings if option.startswith('--'))
            if action.nargs != 0:
                value_options.update(action.option_strings)
            option_nargs.update({option: action.nargs for option in action.option_strings})
            if isinstance(action, argparse._SubParsersAction):
                subcommands.update(action.choices)
    result = HelpResult(options, value_options, subcommands, error, option_nargs)
    cache[key] = result
    return result


def read_help_options(workspace: Path, script: str, subcmd: str | None, cache: dict) -> HelpResult:
    """Compatibility facade; this reads declarations and never executes help."""
    return read_command_help(workspace, script, tuple(shlex.split(subcmd)) if subcmd else (), cache)


def first_positional(tokens: list[str], help_result: HelpResult) -> tuple[int, str] | None:
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            return (index + 1, tokens[index + 1]) if index + 1 < len(tokens) else None
        if token.startswith('-'):
            nargs = help_result.option_nargs.get(token, 0)
            index += 1
            if '=' in token:
                continue
            if nargs is None:
                index += 1
            elif isinstance(nargs, int):
                index += nargs
            elif nargs == '?':
                if index < len(tokens) and not tokens[index].startswith('-'):
                    index += 1
            elif nargs in {'*', '+'}:
                while index < len(tokens) and not tokens[index].startswith('-'):
                    index += 1
            elif nargs == argparse.REMAINDER:
                return None
            continue
        return index, token
    return None


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
    help_cache: dict[tuple[str, str | None], HelpResult],
    required_frontmatter_fields: tuple[str, ...] | None,
    skill_frontmatter: bool = False,
) -> list[Issue]:
    del include_hidden
    issues: list[Issue] = []
    text = md_file.read_text(encoding="utf-8", errors="replace")

    if skill_frontmatter:
        for message in validate_skill_frontmatter(text, runtime_for_path(md_file)):
            issues.append(Issue("ERROR", md_file, 1, message))
    elif required_frontmatter_fields is not None:
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

    for block_match in FENCED_BLOCK_RE.finditer(text):
        lines = join_line_continuations(block_match.group(1))
        block_line = text[:block_match.start(1)].count("\n") + 1
        for raw_line, line_offset in lines:
            command_line = block_line + line_offset
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

            segments = split_segments(line)
            for segment in segments:
                try:
                    tokens = shlex.split(segment)
                except ValueError:
                    continue
                if not tokens:
                    continue

                # Environment assignments are context, not executable tokens.
                if tokens[0] == "env":
                    tokens = tokens[1:]
                while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
                    tokens.pop(0)
                if not tokens:
                    continue

                # Optional style check for bare python.
                if require_uv and len(tokens) >= 2 and tokens[0] in {"python", "python3"}:
                    if tokens[1].startswith(("tools/", "scripts/")):
                        issues.append(
                            Issue(
                                "WARN",
                                md_file,
                                command_line,
                                f"Bare python invocation should use `uv run python`: {segment}",
                            )
                        )

                # A wrapper's -- terminates its own options. Validate an explicit
                # child Python CLI separately instead of attributing its flags
                # to the wrapper (e.g. investigation_context.py run -- ...).
                if "--" in tokens:
                    separator = tokens.index("--")
                    child = tokens[separator + 1:]
                    if child[:3] == ["uv", "run", "python"] or child and child[0] in {"python", "python3"}:
                        segments.append(shlex.join(child))
                    tokens = tokens[:separator]

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
                            command_line,
                            f"Script not found: {script}",
                        )
                    )
                    continue

                remaining = tokens[4:]
                root_help = read_command_help(workspace, script, (), help_cache)
                if root_help.error:
                    issues.append(Issue("WARN", md_file, command_line,
                                        f"{script}: {root_help.error}"))
                    continue
                allowed = set(root_help.options)
                current_help = root_help
                subcmd = None
                command_path = ()
                rest = remaining
                while current_help.subcommands:
                    positional = first_positional(rest, current_help)
                    if positional is None:
                        break
                    candidate_index, candidate = positional
                    if likely_template_token(candidate):
                        break
                    if candidate not in current_help.subcommands:
                        issues.append(Issue("ERROR", md_file, command_line,
                                            f"Invalid subcommand `{candidate}` for `{script}`"
                                            + (f" after `{subcmd}`" if subcmd else "")))
                        break
                    command_path += (candidate,)
                    subcmd = ' '.join(command_path)
                    rest = rest[candidate_index + 1:]
                    current_help = read_command_help(workspace, script, command_path, help_cache)
                    if current_help.error:
                        issues.append(Issue("WARN", md_file, command_line,
                                            f"{script} {subcmd}: {current_help.error}"))
                        break
                    allowed.update(current_help.options)

                flags = []
                for tok in remaining:
                    if tok == "--" or not tok.startswith("--"):
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
                                command_line,
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace).resolve()
    skill_dirs = [Path(p).expanduser() for p in (args.skills_dir or [str(p) for p in default_skill_dirs()])]
    command_dirs = [Path(p).expanduser() for p in (args.commands_dir or [])]
    docs_dirs = [Path(p).expanduser() for p in (args.docs_dir or [])]

    all_issues: list[Issue] = []
    help_cache: dict[tuple[str, str | None], HelpResult] = {}
    checked = 0
    seen: set[Path] = set()

    for skill_root in skill_dirs:
        if not skill_root.exists():
            all_issues.append(Issue("WARN", skill_root, 1, "Skill root does not exist; skipping"))
            continue
        for skill_file in iter_skill_files(skill_root, args.include_hidden):
            # Progressive disclosure moves executable examples into references;
            # validate those examples under the same contract as SKILL.md.
            documents = [(skill_file, True)] + [
                (path, False) for path in iter_markdown_files(skill_file.parent, args.include_hidden)
                if path != skill_file
            ]
            for document, is_skill in documents:
                resolved = document.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                checked += 1
                all_issues.extend(lint_markdown_file(
                    md_file=document, workspace=workspace, require_uv=args.require_uv,
                    include_hidden=args.include_hidden, help_cache=help_cache,
                    required_frontmatter_fields=None, skill_frontmatter=is_skill,
                ))

    for command_root in command_dirs:
        if not command_root.exists():
            all_issues.append(Issue("WARN", command_root, 1, "Command root does not exist; skipping"))
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
            all_issues.append(Issue("WARN", docs_root, 1, "Docs root does not exist; skipping"))
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

    print(f"Checked {checked} markdown files (CLI declarations only; runtime help/availability not executed).")
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
