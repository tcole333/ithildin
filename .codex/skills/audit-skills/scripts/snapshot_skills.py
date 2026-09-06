#!/usr/bin/env python3
"""Create a compact, read-only structural snapshot of project skill packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---(?:\n|$)", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
TODO_RE = re.compile(r"\b(?:TODO|FIXME|TBD)\b|\[(?:TODO|PLACEHOLDER)[^\]]*\]", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".", help="Repository root (default: current directory)")
    parser.add_argument(
        "--skills-dir",
        action="append",
        help="Skill root relative to workspace or absolute (repeatable)",
    )
    parser.add_argument("--skill", action="append", help="Skill name to include (repeatable)")
    parser.add_argument("--changed", action="store_true", help="Include only changed skill packages")
    parser.add_argument(
        "--run-repo-validator",
        action="store_true",
        help="Run scripts/validate_skills.py checks only for the selected variants",
    )
    parser.add_argument("--output", required=True, help="Destination JSON file")
    return parser.parse_args()


def relpath(path: Path, workspace: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace))
    except ValueError:
        return str(path.resolve())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_frontmatter(text: str) -> tuple[dict[str, Any], str | None]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, "missing or malformed YAML frontmatter"
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return {}, f"invalid YAML frontmatter: {exc}"
    if not isinstance(data, dict):
        return {}, "frontmatter is not a mapping"
    return data, None


def issue(
    issues: list[dict[str, Any]],
    *,
    severity: str,
    category: str,
    skill: str,
    path: str,
    line: int,
    message: str,
) -> None:
    issues.append(
        {
            "severity": severity,
            "category": category,
            "skill": skill,
            "path": path,
            "line": line,
            "message": message,
        }
    )


def configured_roots(workspace: Path, values: list[str] | None) -> list[Path]:
    if values:
        roots = [Path(value).expanduser() for value in values]
        return [path if path.is_absolute() else workspace / path for path in roots]
    return [workspace / ".claude" / "skills", workspace / ".codex" / "skills"]


def iter_skill_dirs(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return []
    return (
        child
        for child in sorted(root.iterdir())
        if child.is_dir() and not child.name.startswith(".") and (child / "SKILL.md").is_file()
    )


def git_changed_paths(workspace: Path) -> set[str]:
    commands = (
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    paths: set[str] = set()
    for command in commands:
        proc = subprocess.run(command, cwd=workspace, capture_output=True, text=True, check=False)
        if proc.returncode not in (0, 1):
            continue
        paths.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return paths


def changed_skill_names(changed_paths: set[str], roots: list[Path], workspace: Path) -> set[str]:
    names: set[str] = set()
    for root in roots:
        root_rel = relpath(root, workspace).rstrip("/") + "/"
        for changed in changed_paths:
            if not changed.startswith(root_rel):
                continue
            remainder = changed[len(root_rel) :]
            if "/" in remainder:
                names.add(remainder.split("/", 1)[0])
    return names


def extract_local_links(text: str) -> list[tuple[str, int]]:
    links: list[tuple[str, int]] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1).strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        if target.startswith(("http://", "https://", "mailto:", "#", "/")):
            continue
        target = target.split("#", 1)[0]
        if not target or target.lower() in {"url", "uri", "path", "link"}:
            continue
        if any(marker in target for marker in ("<", ">", "{", "}", "[", "]", "$")):
            continue
        links.append((target, text[: match.start()].count("\n") + 1))
    return links


def all_resource_files(skill_dir: Path) -> list[Path]:
    files: list[Path] = []
    for resource_dir in ("scripts", "references", "assets"):
        base = skill_dir / resource_dir
        if base.is_dir():
            files.extend(path for path in base.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    return sorted(files)


def inspect_openai_yaml(
    skill_dir: Path,
    skill_name: str,
    workspace: Path,
    issues: list[dict[str, Any]],
) -> dict[str, Any] | None:
    metadata_path = skill_dir / "agents" / "openai.yaml"
    if not metadata_path.is_file():
        issue(
            issues,
            severity="info",
            category="interface-metadata",
            skill=skill_name,
            path=relpath(skill_dir / "SKILL.md", workspace),
            line=1,
            message="Codex skill has no agents/openai.yaml (recommended, not required)",
        )
        return None

    metadata_rel = relpath(metadata_path, workspace)
    try:
        data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        issue(
            issues,
            severity="error",
            category="interface-metadata",
            skill=skill_name,
            path=metadata_rel,
            line=1,
            message=f"Cannot parse agents/openai.yaml: {exc}",
        )
        return {"path": metadata_rel, "valid": False}

    interface = data.get("interface") if isinstance(data, dict) else None
    if not isinstance(interface, dict):
        issue(
            issues,
            severity="error",
            category="interface-metadata",
            skill=skill_name,
            path=metadata_rel,
            line=1,
            message="agents/openai.yaml lacks an interface mapping",
        )
        return {"path": metadata_rel, "valid": False}

    display_name = interface.get("display_name")
    short_description = interface.get("short_description")
    default_prompt = interface.get("default_prompt")
    for field, value in (
        ("display_name", display_name),
        ("short_description", short_description),
        ("default_prompt", default_prompt),
    ):
        if not isinstance(value, str) or not value.strip():
            issue(
                issues,
                severity="warning",
                category="interface-metadata",
                skill=skill_name,
                path=metadata_rel,
                line=1,
                message=f"interface.{field} is missing or empty",
            )

    if isinstance(short_description, str) and not 25 <= len(short_description) <= 64:
        issue(
            issues,
            severity="warning",
            category="interface-metadata",
            skill=skill_name,
            path=metadata_rel,
            line=1,
            message=f"short_description is {len(short_description)} characters; expected 25-64",
        )
    if isinstance(default_prompt, str) and f"${skill_name}" not in default_prompt:
        issue(
            issues,
            severity="warning",
            category="interface-metadata",
            skill=skill_name,
            path=metadata_rel,
            line=1,
            message=f"default_prompt does not explicitly mention ${skill_name}",
        )

    return {
        "path": metadata_rel,
        "valid": True,
        "display_name": display_name,
        "short_description": short_description,
        "default_prompt": default_prompt,
    }


def inspect_variant(
    skill_dir: Path,
    root: Path,
    workspace: Path,
    known_skill_names: set[str],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    skill_path = skill_dir / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8", errors="replace")
    frontmatter, frontmatter_error = load_frontmatter(text)
    directory_name = skill_dir.name
    declared_name = frontmatter.get("name") if isinstance(frontmatter.get("name"), str) else None
    skill_name = declared_name or directory_name
    skill_rel = relpath(skill_path, workspace)
    if root.parent.name == ".codex":
        root_kind = "codex"
    elif root.parent.name == ".claude":
        root_kind = "claude"
    else:
        root_kind = "other"

    if frontmatter_error:
        issue(
            issues,
            severity="error",
            category="frontmatter",
            skill=directory_name,
            path=skill_rel,
            line=1,
            message=frontmatter_error,
        )
    if declared_name and declared_name != directory_name:
        issue(
            issues,
            severity="error",
            category="identity",
            skill=directory_name,
            path=skill_rel,
            line=1,
            message=f"frontmatter name '{declared_name}' does not match directory '{directory_name}'",
        )

    line_count = text.count("\n") + (0 if text.endswith("\n") else 1)
    if line_count > 500:
        issue(
            issues,
            severity="warning",
            category="context-efficiency",
            skill=skill_name,
            path=skill_rel,
            line=1,
            message=f"SKILL.md is {line_count} lines; review progressive disclosure above roughly 500 lines",
        )

    todo_match = TODO_RE.search(text)
    if todo_match:
        issue(
            issues,
            severity="error",
            category="placeholder",
            skill=skill_name,
            path=skill_rel,
            line=text[: todo_match.start()].count("\n") + 1,
            message=f"unresolved placeholder: {todo_match.group(0)}",
        )

    expected_heading = f"# ${skill_name}" if root_kind == "codex" else f"# /{skill_name}"
    if root_kind in {"codex", "claude"} and expected_heading not in text:
        issue(
            issues,
            severity="warning",
            category="runtime-convention",
            skill=skill_name,
            path=skill_rel,
            line=1,
            message=f"expected runtime heading '{expected_heading}' not found",
        )

    invocation_pattern = (
        re.compile(r"(?<![A-Za-z0-9_.~-])/((?:" + "|".join(map(re.escape, known_skill_names)) + r"))\b")
        if root_kind == "codex" and known_skill_names
        else None
    )
    stale_invocations: list[str] = []
    if invocation_pattern:
        data_spans = _runtime_helpers().data_fence_spans(text)
        for match in invocation_pattern.finditer(text):
            if any(start <= match.start() < end for start, end in data_spans):
                continue
            stale_invocations.append(match.group(0))
            issue(
                issues,
                severity="warning",
                category="runtime-convention",
                skill=skill_name,
                path=skill_rel,
                line=text[: match.start()].count("\n") + 1,
                message=f"Codex text appears to use Claude invocation '{match.group(0)}'",
            )

    local_links = extract_local_links(text)
    resolved_links: list[dict[str, Any]] = []
    linked_paths: set[Path] = set()
    for target, link_line in local_links:
        resolved = (skill_dir / target).resolve()
        linked_paths.add(resolved)
        exists = resolved.exists()
        resolved_links.append({"target": target, "line": link_line, "exists": exists})
        if not exists:
            issue(
                issues,
                severity="error",
                category="broken-link",
                skill=skill_name,
                path=skill_rel,
                line=link_line,
                message=f"local Markdown link does not resolve: {target}",
            )

    resources = []
    for resource in all_resource_files(skill_dir):
        resource_rel_to_skill = str(resource.relative_to(skill_dir))
        mentioned = resource.resolve() in linked_paths or resource_rel_to_skill in text
        resources.append({"path": resource_rel_to_skill, "mentioned": mentioned})
        if not mentioned:
            issue(
                issues,
                severity="info",
                category="unreachable-resource",
                skill=skill_name,
                path=relpath(resource, workspace),
                line=1,
                message="bundled resource is not referenced directly from SKILL.md",
            )

    metadata = None
    if root_kind == "codex":
        metadata = inspect_openai_yaml(skill_dir, skill_name, workspace, issues)

    return {
        "skill": skill_name,
        "directory_name": directory_name,
        "root_kind": root_kind,
        "root": relpath(root, workspace),
        "path": skill_rel,
        "frontmatter": frontmatter,
        "line_count": line_count,
        "character_count": len(text),
        "sha256": sha256_text(text),
        "links": resolved_links,
        "resources": resources,
        "stale_invocations": stale_invocations,
        "interface": metadata,
    }


def _runtime_helpers():
    # Installed copies resolve shared helpers from the selected repository cwd.
    import sys

    repo = Path(__file__).resolve().parents[4]
    if not (repo / "scripts/skill_metadata.py").exists():
        repo = Path.cwd()
    sys.path.insert(0, str(repo))
    try:
        from scripts import skill_metadata
        return skill_metadata
    finally:
        sys.path.pop(0)


def normalized_runtime_text(text: str, skill_names: set[str]) -> str:
    return _runtime_helpers().normalized_runtime_text(text, skill_names)


def resolve_selector(selector: str, workspace: Path, available_names: set[str]) -> str | None:
    if selector in available_names:
        return selector
    candidate = Path(selector).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    candidate = candidate.resolve()
    if candidate.name == "SKILL.md":
        candidate = candidate.parent
    if (candidate / "SKILL.md").is_file() and candidate.name in available_names:
        return candidate.name
    return None


def append_repo_validator_issues(
    variants: list[dict[str, Any]],
    workspace: Path,
    issues: list[dict[str, Any]],
) -> None:
    import sys

    sys.path.insert(0, str(workspace))
    try:
        from scripts.validate_skills import lint_markdown_file
    except Exception as exc:
        issue(
            issues,
            severity="error",
            category="repo-validator",
            skill="audit-skills",
            path="scripts/validate_skills.py",
            line=1,
            message=f"could not load repository skill validator: {exc}",
        )
        return
    finally:
        if sys.path and sys.path[0] == str(workspace):
            sys.path.pop(0)

    help_cache: dict[tuple[str, str | None], set[str]] = {}
    for variant in variants:
        skill_path = Path(variant["path"])
        if not skill_path.is_absolute():
            skill_path = workspace / skill_path
        documents = [(skill_path, True)] + [
            (path, False) for path in sorted(skill_path.parent.rglob("*.md"))
            if path != skill_path and not any(part.startswith(".") for part in path.relative_to(skill_path.parent).parts)
        ]
        for document, is_skill in documents:
            validator_issues = lint_markdown_file(
                md_file=document,
                workspace=workspace,
                require_uv=True,
                include_hidden=False,
                help_cache=help_cache,
                required_frontmatter_fields=None,
                skill_frontmatter=is_skill,
            )
            for validator_issue in validator_issues:
                issue(
                    issues,
                    severity="error" if validator_issue.level == "ERROR" else "warning",
                    category="repo-validator",
                    skill=variant["skill"],
                    path=relpath(validator_issue.path, workspace),
                    line=validator_issue.line,
                    message=validator_issue.message,
                )


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    roots = [root.resolve() for root in configured_roots(workspace, args.skills_dir)]
    requested_selectors = set(args.skill or [])
    changed_paths = git_changed_paths(workspace) if args.changed else set()
    changed_names = changed_skill_names(changed_paths, roots, workspace) if args.changed else set()
    available: dict[str, list[tuple[Path, Path]]] = defaultdict(list)
    for root in roots:
        for skill_dir in iter_skill_dirs(root):
            available[skill_dir.name].append((skill_dir, root))

    requested: set[str] = set()
    unknown_selectors: list[str] = []
    for selector in sorted(requested_selectors):
        resolved = resolve_selector(selector, workspace, set(available))
        if resolved is None:
            unknown_selectors.append(selector)
        else:
            requested.add(resolved)
    if unknown_selectors:
        raise SystemExit(f"Unknown skill selector(s): {', '.join(unknown_selectors)}")

    selected_names = requested | changed_names

    changed_missing_from_worktree = changed_names - set(available)
    selected_names &= set(available)
    if requested_selectors or args.changed:
        names_to_scan = sorted(selected_names)
    else:
        names_to_scan = sorted(available)

    known_skill_names = set(available)
    issues: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for name in sorted(changed_missing_from_worktree):
        issue(
            issues,
            severity="info",
            category="changed-skill-removed",
            skill=name,
            path=name,
            line=1,
            message="changed skill package is absent from the current worktree; inspect the Git deletion",
        )

    for name in names_to_scan:
        for skill_dir, root in available[name]:
            variant = inspect_variant(skill_dir, root, workspace, known_skill_names, issues)
            variants.append(variant)
            by_skill[name].append(variant)

    if args.run_repo_validator:
        append_repo_validator_issues(variants, workspace, issues)

    cross_tree: list[dict[str, Any]] = []
    for name in names_to_scan:
        skill_variants = by_skill[name]
        kinds = {variant["root_kind"] for variant in skill_variants}
        if {"claude", "codex"} - kinds and any(kind in {"claude", "codex"} for kind in kinds):
            missing = sorted({"claude", "codex"} - kinds)
            issue(
                issues,
                severity="info",
                category="unpaired-runtime",
                skill=name,
                path=skill_variants[0]["path"],
                line=1,
                message=f"skill has no {' or '.join(missing)} runtime variant",
            )

        claude = next((variant for variant in skill_variants if variant["root_kind"] == "claude"), None)
        codex = next((variant for variant in skill_variants if variant["root_kind"] == "codex"), None)
        equivalent = None
        if claude and codex:
            claude_text = (workspace / claude["path"]).read_text(encoding="utf-8")
            codex_text = (workspace / codex["path"]).read_text(encoding="utf-8")
            equivalent = normalized_runtime_text(claude_text, known_skill_names) == normalized_runtime_text(
                codex_text, known_skill_names
            )
            if not equivalent:
                issue(
                    issues,
                    severity="warning",
                    category="cross-tree-drift",
                    skill=name,
                    path=codex["path"],
                    line=1,
                    message=(
                        "Claude and Codex variants differ beyond normalized "
                        "invocation/frontmatter syntax"
                    ),
                )
        cross_tree.append(
            {
                "skill": name,
                "present_in": sorted(kinds),
                "equivalent_after_runtime_normalization": equivalent,
            }
        )

    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(
        key=lambda item: (
            severity_order.get(item["severity"], 9),
            item["skill"],
            item["path"],
            item["line"],
            item["category"],
        )
    )
    counts = defaultdict(int)
    for item in issues:
        counts[item["severity"]] += 1

    result = {
        "workspace": str(workspace),
        "scope": {
            "requested": sorted(requested_selectors),
            "resolved_requested": sorted(requested),
            "changed_only": args.changed,
            "changed_skill_names": sorted(changed_names),
            "changed_missing_from_worktree": sorted(changed_missing_from_worktree),
            "resolved_skill_names": names_to_scan,
            "repo_validator_enabled": args.run_repo_validator,
        },
        "roots": [relpath(root, workspace) for root in roots if root.exists()],
        "summary": {
            "unique_skills": len(names_to_scan),
            "variants": len(variants),
            "errors": counts["error"],
            "warnings": counts["warning"],
            "info": counts["info"],
        },
        "issues": issues,
        "cross_tree": cross_tree,
        "variants": variants,
    }

    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = workspace / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Scanned {result['summary']['unique_skills']} skills / {result['summary']['variants']} variants: "
        f"{result['summary']['errors']} errors, {result['summary']['warnings']} warnings, "
        f"{result['summary']['info']} info."
    )
    print(f"Snapshot: {output}")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
