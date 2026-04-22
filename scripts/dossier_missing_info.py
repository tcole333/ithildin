#!/usr/bin/env python3
"""Diff dossier prose against its findings[] to surface unreferenced evidence.

For each dossier, list the highest-scoring findings that do NOT appear in
`curation.lead` or `curation.sections[*].content`. This is a review aid for
the editorial pass — the curator decides which belong in the prose.

Ranking uses `_score_finding` from `pipeline/curate_dossier.py` (same algorithm
the curation pipeline uses to pick key findings), so the top hits are what an
editor would most want to know about.

Usage:
    uv run python scripts/dossier_missing_info.py --profile epstein
    uv run python scripts/dossier_missing_info.py --slug jeffrey-epstein --top 20
    uv run python scripts/dossier_missing_info.py --all --top 10
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOSSIER_DIR = ROOT / "content" / "dossiers"
INDEX_PATH = DOSSIER_DIR / "_index.json"
OUTPUT_DIR = Path("/tmp/missing-info")

sys.path.insert(0, str(ROOT))
from pipeline.curate_dossier import _score_finding  # reuse ranking

FINDING_REF_RE = re.compile(r"Finding\s*#?\s*(\d+)", re.IGNORECASE)


def referenced_findings(dossier: dict) -> set[int]:
    curation = dossier.get("curation", {}) or {}
    blobs: list[str] = []
    if curation.get("lead"):
        blobs.append(curation["lead"])
    for sec in curation.get("sections", []) or []:
        if sec.get("content"):
            blobs.append(sec["content"])

    ids: set[int] = set()
    for blob in blobs:
        for m in FINDING_REF_RE.finditer(blob):
            ids.add(int(m.group(1)))
    return ids


def connection_counts(dossier: dict) -> dict[int, int]:
    counts: dict[int, int] = defaultdict(int)
    for conn in dossier.get("connections", []) or []:
        for ev in conn.get("evidence", []) or []:
            ref = ev.get("evidence_ref", "")
            if ref.startswith("Finding #"):
                try:
                    fid = int(ref.split("#")[1].strip())
                except (ValueError, IndexError):
                    continue
                counts[fid] += 1
    return counts


def rank_missing(dossier: dict, top: int) -> list[dict]:
    referenced = referenced_findings(dossier)
    counts = connection_counts(dossier)

    missing: list[tuple[float, dict]] = []
    for f in dossier.get("findings", []) or []:
        if f["id"] in referenced:
            continue
        score = _score_finding(f, counts)
        missing.append((score, f))

    missing.sort(key=lambda x: -x[0])
    return [{"score": round(score, 1), **f} for score, f in missing[:top]]


def format_report(slug: str, dossier_name: str, missing: list[dict], total_findings: int, referenced_count: int) -> str:
    lines = [
        f"# Missing-info report: {dossier_name} ({slug})",
        "",
        f"- Total findings in dossier: **{total_findings}**",
        f"- Findings cited in prose: **{referenced_count}**",
        f"- Unreferenced findings: **{total_findings - referenced_count}**",
        f"- Top unreferenced by score (showing {len(missing)}):",
        "",
    ]
    for f in missing:
        evidence = f.get("evidence", []) or []
        primary = any(
            (e.get("evidence_type") in ("primary", "court_filing", "government_record"))
            or (e.get("evidence_ref") or "").startswith("EFTA")
            for e in evidence
        )
        refs = ", ".join(str(e.get("evidence_ref", "")) for e in evidence[:3] if e.get("evidence_ref"))
        summary = (f.get("summary") or "").strip().replace("\n", " ")
        if len(summary) > 320:
            summary = summary[:317] + "…"
        primary_flag = "★" if primary else " "
        lines.extend([
            f"### Finding #{f['id']} · score {f['score']} {primary_flag}",
            f"- type: `{f.get('finding_type', '?')}` · claim_type: `{f.get('claim_type', '?')}` · confidence: `{f.get('confidence', '?')}` · verification: `{f.get('verification_status', '?')}`",
            f"- date: `{f.get('date_of_event') or '-'}` · evidence refs: `{refs or '-'}`",
            f"- {summary}",
            "",
        ])
    return "\n".join(lines)


def load_slugs(profile: str | None, slug: str | None, all_: bool) -> list[tuple[str, str]]:
    if slug:
        for entry in json.loads(INDEX_PATH.read_text()):
            if entry["slug"] == slug:
                return [(slug, entry["name"])]
        return [(slug, slug)]
    index = json.loads(INDEX_PATH.read_text())
    if profile:
        return [(d["slug"], d["name"]) for d in index if profile in d.get("profile_ids", [])]
    if all_:
        return [(d["slug"], d["name"]) for d in index]
    raise SystemExit("Must specify --slug, --profile, or --all")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="Report for a single dossier")
    parser.add_argument("--profile", help="Report for all dossiers in a profile (e.g. epstein)")
    parser.add_argument("--all", action="store_true", help="Report for every curated dossier")
    parser.add_argument("--top", type=int, default=10, help="Top N unreferenced findings per dossier")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory for per-slug reports")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict] = []

    for slug, name in load_slugs(args.profile, args.slug, args.all):
        path = DOSSIER_DIR / f"{slug}.json"
        if not path.exists():
            continue
        dossier = json.loads(path.read_text())
        findings = dossier.get("findings") or []
        if not findings:
            continue
        referenced = referenced_findings(dossier)
        missing = rank_missing(dossier, args.top)

        report = format_report(slug, name, missing, total_findings=len(findings), referenced_count=len(referenced))
        (out_dir / f"{slug}.md").write_text(report)

        high_value_primary = sum(
            1 for f in missing
            if f.get("confidence") in ("confirmed", "high")
            and any(
                (e.get("evidence_type") in ("primary", "court_filing", "government_record"))
                or (e.get("evidence_ref") or "").startswith("EFTA")
                for e in (f.get("evidence") or [])
            )
        )

        summary_rows.append({
            "slug": slug,
            "name": name,
            "total_findings": len(findings),
            "referenced": len(referenced),
            "unreferenced": len(findings) - len(referenced),
            "top_shown": len(missing),
            "high_value_missing": high_value_primary,
        })

    summary_rows.sort(key=lambda r: -r["high_value_missing"])

    lines = [
        "# Dossier missing-info summary",
        "",
        f"Reports in: `{out_dir}/<slug>.md`",
        "",
        "| High-value missing | Unref / Total | Referenced | Dossier |",
        "|-------------------:|--------------:|-----------:|---------|",
    ]
    for r in summary_rows:
        lines.append(
            f"| {r['high_value_missing']:>3} | {r['unreferenced']}/{r['total_findings']} | {r['referenced']} | [{r['name']}]({r['slug']}.md) |"
        )
    (out_dir / "_summary.md").write_text("\n".join(lines) + "\n")

    print(f"Wrote {len(summary_rows)} per-dossier reports to {out_dir}/")
    print(f"Summary: {out_dir}/_summary.md")
    print()
    print("Top 10 dossiers with most high-value unreferenced findings:")
    for r in summary_rows[:10]:
        print(f"  {r['high_value_missing']:>3} high-value  {r['unreferenced']:>3} total missing  {r['slug']}")


if __name__ == "__main__":
    main()
