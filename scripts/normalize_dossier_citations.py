#!/usr/bin/env python3
"""Normalize citation tokens in dossier prose to canonical bracket form.

Problem:
    Legacy dossiers wrote citations as `(Finding 2866)` or `(EFTA02576529)`.
    The renderer only footnotes `[Token]` bracket form. Paren-form WITH a
    matching canonical token pattern is converted by `normalizeCitationPatterns`
    in `web/src/lib/citations.ts` at render time — but `(Finding 2866)` without
    a `#` does NOT match the canonical Finding pattern and renders as plain text.

Fix:
    Walk `curation.lead` and `curation.sections[*].content` for every dossier:
      1. Add `#` to any `Finding N` that lacks one (inside parens OR brackets).
      2. Convert `(tokens)` → `[tokens]` when the paren content is entirely made
         up of citation tokens plus separators (mirrors the TS normalizer).

Safety:
    - Only touches content inside round parentheses or square brackets.
    - Never alters markdown-link tails like `](https://...)` — the content must
      not start with `https://` or match the markdown-link pattern.
    - Never alters non-citation parens (e.g. `(1981)`, `(see below)`).
    - Idempotent: running twice is a no-op on the second run.

Usage:
    uv run python scripts/normalize_dossier_citations.py --all
    uv run python scripts/normalize_dossier_citations.py --slug jeffrey-epstein
    uv run python scripts/normalize_dossier_citations.py --profile epstein --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOSSIER_DIR = ROOT / "content" / "dossiers"
INDEX_PATH = DOSSIER_DIR / "_index.json"

# Canonical single-token patterns mirror the registry in web/src/lib/citations.ts.
# Intentionally looser on `Finding` (hash optional) so legacy paren-form gets
# normalized. The normalizer re-emits with `#` so renderer output is canonical.
TOKEN_PATTERNS = [
    r"Finding\s*#?\s*\d+",
    r"EFTA\d{6,}",
    r"HOUSE_OVERSIGHT_\d+",
    r"SEC:\d{10}-\d{2}-\d{6}",
    r"EDGAR:\d{10}-\d{2}-\d{6}",
    r"990:\d{9}",
    r"ACRIS:\d{13,16}",
    r"CL:\d+",
    r"NYSCEF_CASE:[A-Za-z0-9%+/_=.-]+",
    r"FEC:[A-Za-z0-9_/-]+",
    r"FARA:\d+",
    r"USVI:[A-Za-z0-9]+",
    r"FL[-_]?SunBiz[:\s]+[A-Za-z0-9]+",
    r"NM[-_]?SoS[:\s]+[A-Za-z0-9]+",
    r"NY[-_]?SoS[:\s]+[A-Za-z0-9]+",
    r"REG:[A-Z]{2}:[A-Za-z0-9]+",
    r"DS10(?::[A-Za-z0-9_-]+)?",
    r"KPMG:[A-Za-z0-9_-]+",
    r"LDA:[A-Za-z0-9_ -]+",
    r"OpenSanctions:[A-Za-z0-9]+",
    r"DOCUMENTCLOUD:\d+",
    r"OffshoreAlert:[A-Za-z0-9_-]+",
    r"MUCKROCK:\d+(?:/[A-Za-z0-9_.-]+)?",
    r"LittleSis[_:]?\d+",
    r"ICIJ(?:-PP|-node)?[:\s]\d+",
    r"LMSBAND[:\-]\S+",
    r"DOJ[:\-]\S+",
]
TOKEN_GROUP_RE = re.compile("(?i:" + "|".join(f"(?:{p})" for p in TOKEN_PATTERNS) + ")")

FINDING_REF_RE = re.compile(r"Finding\s*#?\s*(\d+)", re.IGNORECASE)


def canonicalize_finding(token: str) -> str:
    """Rewrite `Finding 2866` → `Finding #2866`. No-op if already canonical."""

    def _sub(match: re.Match[str]) -> str:
        return f"Finding #{match.group(1)}"

    return FINDING_REF_RE.sub(_sub, token)


def is_pure_citation_group(inner: str) -> bool:
    """True if `inner` contains only citation tokens plus whitespace/separators."""
    candidate = inner.strip()
    if not candidate:
        return False
    remainder = TOKEN_GROUP_RE.sub("", candidate)
    remainder = re.sub(r"[\s,;|/]+", "", remainder)
    remainder = re.sub(r"\band\b", "", remainder, flags=re.IGNORECASE)
    return remainder == ""


def normalize_group_content(inner: str) -> str:
    """Normalize tokens inside an already-confirmed citation group."""
    out: list[str] = []
    last_end = 0
    for m in TOKEN_GROUP_RE.finditer(inner):
        token = canonicalize_finding(m.group(0).strip())
        out.append(token)
        last_end = m.end()
    return ", ".join(out) if out else inner.strip()


def normalize_text(text: str) -> tuple[str, int]:
    """Normalize citations in a string. Returns (new_text, changes)."""
    if not text:
        return text, 0

    changes = 0

    # Step 1: paren → bracket. Only convert when ENTIRE paren content is citations.
    def paren_sub(match: re.Match[str]) -> str:
        nonlocal changes
        inner = match.group(1)

        # Skip markdown-link tails: `]<space>*(url)`. Dossier prose uses HTML <a>
        # tags, so this is belt-and-suspenders, but preserve the invariant.
        start = match.start()
        preceding = text[:start].rstrip()
        if preceding.endswith("]"):
            return match.group(0)

        # Skip pure URLs and non-citation parens.
        stripped = inner.strip()
        if stripped.startswith("http"):
            return match.group(0)
        if not is_pure_citation_group(inner):
            return match.group(0)

        normalized = normalize_group_content(inner)
        changes += 1
        return f"[{normalized}]"

    text = re.sub(r"\(([^()]+)\)", paren_sub, text)

    # Step 2: add `#` to hashless `Finding N` inside existing brackets.
    def bracket_sub(match: re.Match[str]) -> str:
        nonlocal changes
        inner = match.group(1)
        new_inner = canonicalize_finding(inner)
        if new_inner != inner:
            changes += 1
            return f"[{new_inner}]"
        return match.group(0)

    text = re.sub(r"\[([^\[\]]+)\]", bracket_sub, text)

    return text, changes


def normalize_dossier(path: Path, dry_run: bool = False) -> dict:
    data = json.loads(path.read_text())
    curation = data.get("curation", {})
    total_changes = 0

    lead = curation.get("lead")
    if lead:
        new_lead, changes = normalize_text(lead)
        if changes:
            curation["lead"] = new_lead
            total_changes += changes

    for sec in curation.get("sections", []) or []:
        content = sec.get("content")
        if not content:
            continue
        new_content, changes = normalize_text(content)
        if changes:
            sec["content"] = new_content
            total_changes += changes

    if total_changes and not dry_run:
        path.write_text(json.dumps(data, indent=2, default=str) + "\n")

    return {"slug": path.stem, "changes": total_changes}


def load_slugs(profile: str | None, slug: str | None, all_: bool) -> list[str]:
    if slug:
        return [slug]
    index = json.loads(INDEX_PATH.read_text())
    if profile:
        return [d["slug"] for d in index if profile in d.get("profile_ids", [])]
    if all_:
        return [d["slug"] for d in index]
    raise SystemExit("Must specify --slug, --profile, or --all")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="Normalize a single dossier")
    parser.add_argument("--profile", help="Normalize all dossiers in profile (e.g. epstein)")
    parser.add_argument("--all", action="store_true", help="Normalize every curated dossier")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = parser.parse_args()

    slugs = load_slugs(args.profile, args.slug, args.all)

    total_changes = 0
    touched = 0
    for s in slugs:
        path = DOSSIER_DIR / f"{s}.json"
        if not path.exists():
            continue
        result = normalize_dossier(path, dry_run=args.dry_run)
        if result["changes"]:
            touched += 1
            total_changes += result["changes"]
            prefix = "[dry]" if args.dry_run else "     "
            print(f"{prefix} {s}: {result['changes']} citation normalizations")

    suffix = " (dry run — nothing written)" if args.dry_run else ""
    print(f"\nTouched {touched}/{len(slugs)} dossiers, {total_changes} normalizations{suffix}")


if __name__ == "__main__":
    main()
