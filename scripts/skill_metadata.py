"""Shared skill metadata and runtime normalization (no runtime execution).

Claude fields: https://code.claude.com/docs/en/skills#frontmatter-reference
Shared fields: https://agentskills.io/specification
Codex runtime policy belongs in agents/openai.yaml, not Claude frontmatter.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

BASE_SKILL_KEYS = frozenset({'name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility'})
CLAUDE_SKILL_KEYS = frozenset({
    'when_to_use', 'argument-hint', 'arguments', 'disable-model-invocation',
    'user-invocable', 'disallowed-tools', 'model', 'effort', 'context', 'agent',
    'background', 'hooks', 'paths', 'shell',
})
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---(?:\n|$)', re.DOTALL)


def runtime_for_path(path: Path) -> str:
    # Worktrees may themselves live under .claude/worktrees. Match the nearest
    # actual skill-root pair, not any runtime-looking ancestor name.
    pairs = list(zip(path.parts, path.parts[1:]))
    for directory, child in reversed(pairs):
        if child != 'skills':
            continue
        if directory == '.claude':
            return 'claude'
        if directory in {'.codex', '.agents'}:
            return 'codex'
    return 'generic'


def runtime_metadata_errors(frontmatter: dict, runtime: str) -> list[str]:
    allowed = BASE_SKILL_KEYS | (CLAUDE_SKILL_KEYS if runtime == 'claude' else frozenset())
    unknown = set(map(str, frontmatter)) - allowed
    errors = []
    if unknown:
        errors.append(f"Unexpected frontmatter key(s) for {runtime}: {', '.join(sorted(unknown))}. "
                      f"Allowed: {', '.join(sorted(allowed))}")
    for key in ('metadata', 'hooks'):
        if key in frontmatter and not isinstance(frontmatter[key], dict):
            errors.append(f'`{key}` must be a YAML mapping')
    for key in ('user-invocable', 'disable-model-invocation', 'background'):
        if key in frontmatter:
            value = frontmatter[key]
            if not (isinstance(value, bool) or type(value) is int and value in (0, 1)
                    or isinstance(value, str) and value.lower() in {'true', 'false', 'yes', 'no', 'on', 'off', '0', '1'}):
                errors.append(f'`{key}` must be a boolean')
    for key in ('allowed-tools', 'disallowed-tools', 'arguments', 'paths'):
        if key in frontmatter:
            value = frontmatter[key]
            if not (isinstance(value, str) or isinstance(value, list) and all(isinstance(v, str) for v in value)):
                errors.append(f'`{key}` must be a string or a list of strings')
    for key in ('when_to_use', 'argument-hint', 'agent', 'model', 'license'):
        if key in frontmatter and not isinstance(frontmatter[key], str):
            errors.append(f'`{key}` must be a string')
    for key, choices in {'context': {'fork'}, 'effort': {'low', 'medium', 'high', 'xhigh', 'max'}, 'shell': {'bash', 'powershell'}}.items():
        if key in frontmatter and (not isinstance(frontmatter[key], str) or frontmatter[key] not in choices):
            errors.append(f"`{key}` must be one of: {', '.join(sorted(choices))}")
    return errors


def data_fence_spans(text: str) -> list[tuple[int, int]]:
    """JSON/YAML examples contain stored values, not runtime invocations."""
    pattern = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[ \t]*(?:json|yaml|yml)[ \t]*\n.*?^[ \t]*\1[ \t]*(?:\n|$)")
    return [(match.start(), match.end()) for match in pattern.finditer(text)]


def normalized_runtime_text(text: str, skill_names: set[str]) -> str:
    """Normalize adapter metadata and invocation spelling, never body policy.

    Runtime metadata is reported separately by parity; this comparison concerns
    shared instructions, descriptions and bundled reference content.
    """
    match = FRONTMATTER_RE.match(text)
    if match:
        data = yaml.safe_load(match.group(1))
        if isinstance(data, dict):
            for key in CLAUDE_SKILL_KEYS | {'user_invocable'}:
                data.pop(key, None)
            text = '---\n' + yaml.safe_dump(data, sort_keys=True).strip() + '\n---\n' + text[match.end():]
    def normalize_prose(segment: str) -> str:
        for name in sorted(skill_names, key=len, reverse=True):
            segment = re.sub(rf'(?<![A-Za-z0-9_.~/-])/{re.escape(name)}\b', f'${name}', segment)
        return segment.replace('CLAUDE.md', 'AGENTS.md')

    parts = []
    start = 0
    for left, right in data_fence_spans(text):
        parts.extend((normalize_prose(text[start:left]), text[left:right]))
        start = right
    parts.append(normalize_prose(text[start:]))
    return ''.join(parts).strip()
