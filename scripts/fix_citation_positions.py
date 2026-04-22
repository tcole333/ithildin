#!/usr/bin/env python3
"""Mechanically fix citations placed just after a period — move them inside.

Observed pattern (G42, many Tier C dossiers): a claim sentence ends with an
attribution phrase and period, and the supporting `[Finding #N]` token sits
at the start of the next sentence. The review script's sentence splitter
strips the attribution from the citation's sentence, triggering a false
`claim_compliance` flag even though the citation was clearly intended to
support the preceding claim.

Example (before):
  Analysis of the filings indicates X. [Finding #42] Context continues.
Split into:
  S1: "Analysis of the filings indicates X."
  S2: "[Finding #42] Context continues."
S2 has Finding #42 (synthesis) but no attribution → flag.

Fix (after):
  Analysis of the filings indicates X [Finding #42]. Context continues.
Split into:
  S1: "Analysis of the filings indicates X [Finding #42]."
  S2: "Context continues."

Safety rules:
  1. Only swap when the preceding sentence already carries attribution
     language (mirrors ATTRIBUTION_RE in scripts/review_dossier_checks.py).
  2. Only swap when the cited finding exists in this dossier's findings[]
     AND its claim_type is `inference` or `synthesis` (the cases the
     checker flags).
  3. Only move one token at a time; a group like `[Finding #N, Finding #M]`
     moves as a unit.
  4. Leave markdown-link tails (`](url)`) alone.

Usage:
    uv run python scripts/fix_citation_positions.py --profile epstein
    uv run python scripts/fix_citation_positions.py --slug bo-hines --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOSSIER_DIR = ROOT / "content" / "dossiers"
INDEX_PATH = DOSSIER_DIR / "_index.json"

# Copied from scripts/review_dossier_checks.py so we match its judgment.
ATTRIBUTION_RE = re.compile(
    r"(?:analysis\s+(?:of|indicates|suggests)|"
    r"cross-?reference\s+of|"
    r"(?:grant|fund|financial)\s+flow\s+analysis|"
    r"review\s+of\s+(?:the\s+)?(?:records?|filings?|documents?)|"
    r"examination\s+of|"
    r"according\s+to|"
    r"records?\s+(?:show|indicate|reveal)|"
    r"hypothesis\s+#?\d+\s+proposes?)",
    re.IGNORECASE,
)

FINDING_REF_RE = re.compile(r"Finding\s*#\s*(\d+)", re.IGNORECASE)

# Match a period (or other sentence terminator) optionally followed by a
# closing HTML tag, then whitespace, then a bracket citation group.
# The bracket group must start with a Finding reference (we only move
# claim_compliance-relevant tokens, not standalone EFTA refs).
SWAP_RE = re.compile(
    r"(?P<pre>[.!?])"                       # sentence terminator
    r"(?P<close>(?:\s*</\w+>)?)"           # optional close tag like </p>
    r"(?P<gap>\s+)"                         # whitespace between sentences
    r"(?P<bracket>\[(?P<inner>[^\[\]]*Finding\s*#\s*\d+[^\[\]]*)\])",
    re.IGNORECASE,
)


def load_findings(dossier: dict) -> dict[int, str]:
    """Return {finding_id: claim_type}."""
    return {f["id"]: f.get("claim_type", "") for f in dossier.get("findings", []) or []}


def preceding_sentence(text: str, terminator_index: int) -> str:
    """Return the sentence that ends at `terminator_index` (the `.` position)."""
    # Scan backward for the nearest prior terminator or start of string.
    start = 0
    for m in re.finditer(r"[.!?]\s+", text[:terminator_index]):
        start = m.end()
    return text[start:terminator_index + 1]


def swap_positions(text: str, claim_map: dict[int, str]) -> tuple[str, int]:
    """Move `[Finding #N]` tokens from sentence-start to preceding sentence-end."""
    changes = 0
    cursor = 0
    out_parts: list[str] = []

    while True:
        m = SWAP_RE.search(text, cursor)
        if not m:
            out_parts.append(text[cursor:])
            break

        inner = m.group("inner")
        finding_ids = [int(x) for x in FINDING_REF_RE.findall(inner)]
        # Require at least one synthesis/inference finding to justify the move.
        relevant = [fid for fid in finding_ids if claim_map.get(fid) in ("inference", "synthesis")]
        if not relevant:
            out_parts.append(text[cursor:m.end()])
            cursor = m.end()
            continue

        # Check preceding sentence for attribution language.
        prev = preceding_sentence(text, m.start("pre"))
        if not ATTRIBUTION_RE.search(prev):
            out_parts.append(text[cursor:m.end()])
            cursor = m.end()
            continue

        # Perform the swap: attach bracket INSIDE the preceding sentence
        # (before the terminator), and drop it from the new sentence start.
        out_parts.append(text[cursor:m.start("pre")])
        out_parts.append(f" {m.group('bracket')}")
        out_parts.append(m.group("pre"))
        out_parts.append(m.group("close"))
        # Collapse the gap that's now followed immediately by the next sentence.
        out_parts.append(" " if m.group("gap") else "")
        cursor = m.end()
        changes += 1

    return "".join(out_parts), changes


def process_dossier(path: Path, dry_run: bool) -> dict:
    dossier = json.loads(path.read_text())
    claim_map = load_findings(dossier)
    curation = dossier.get("curation", {})
    total_changes = 0

    lead = curation.get("lead")
    if lead:
        new_lead, n = swap_positions(lead, claim_map)
        if n:
            curation["lead"] = new_lead
            total_changes += n

    for sec in curation.get("sections", []) or []:
        content = sec.get("content")
        if not content:
            continue
        new_content, n = swap_positions(content, claim_map)
        if n:
            sec["content"] = new_content
            total_changes += n

    if total_changes and not dry_run:
        path.write_text(json.dumps(dossier, indent=2, default=str) + "\n")

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
    parser.add_argument("--slug")
    parser.add_argument("--profile")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slugs = load_slugs(args.profile, args.slug, args.all)
    total = 0
    touched = 0
    for s in slugs:
        path = DOSSIER_DIR / f"{s}.json"
        if not path.exists():
            continue
        result = process_dossier(path, dry_run=args.dry_run)
        if result["changes"]:
            touched += 1
            total += result["changes"]
            prefix = "[dry]" if args.dry_run else "     "
            print(f"{prefix} {s}: {result['changes']} citation repositions")

    suffix = " (dry run — nothing written)" if args.dry_run else ""
    print(f"\nTouched {touched}/{len(slugs)} dossiers, {total} repositions{suffix}")


if __name__ == "__main__":
    main()
