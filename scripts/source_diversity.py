#!/usr/bin/env python3
"""Analyze citation diversity in an MDX article.

Parses citation tokens, classifies by source type, computes diversity metrics,
and cross-references investigation.db for available but uncited evidence.

Usage:
    uv run python scripts/source_diversity.py site/content/articles/gulf-intelligence-web.mdx
    uv run python scripts/source_diversity.py site/content/articles/gulf-intelligence-web.mdx --json
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "investigation.db"
CLUSTERS_PATH = Path(__file__).parent.parent / "site" / "content" / "clusters.json"

# Citation token patterns matching citations.ts
CITATION_PATTERNS = [
    ("efta", re.compile(r"\[EFTA\d{6,}\]")),
    ("sec_edgar", re.compile(r"\[SEC:\d{10}-\d{2}-\d{6}\]")),
    ("irs_990", re.compile(r"\[990:\d{9}\]")),
    ("acris", re.compile(r"\[ACRIS:\d{13,16}\]")),
    ("courtlistener", re.compile(r"\[CL:\d+\]")),
    ("fec", re.compile(r"\[FEC:C\d{8}\]")),
    ("fara", re.compile(r"\[FARA:\d+\]")),
    ("usvi_registry", re.compile(r"\[USVI:\d+\]")),
    ("state_registry", re.compile(r"\[REG:[A-Z]{2}:[A-Za-z0-9]+\]")),
    ("ds10", re.compile(r"\[DS10\]")),
    ("house_oversight", re.compile(r"\[HOUSE_OVERSIGHT_\d+\]")),
    ("finding_ref", re.compile(r"\[Finding\s*#\s*\d+\]", re.IGNORECASE)),
]

# Evidence ref classification (same as story_clustering.py)
EVIDENCE_REF_PATTERNS = [
    ("efta", re.compile(r"^EFTA\d", re.IGNORECASE)),
    ("house_oversight", re.compile(r"^HOUSE_OVERSIGHT", re.IGNORECASE)),
    ("acris", re.compile(r"^ACRIS", re.IGNORECASE)),
    ("fec", re.compile(r"^FEC", re.IGNORECASE)),
    ("littlesis", re.compile(r"^LittleSis", re.IGNORECASE)),
    ("usvi_registry", re.compile(r"^USVI", re.IGNORECASE)),
    ("courtlistener", re.compile(r"^(?:CourtListener|CL:)", re.IGNORECASE)),
    ("fara", re.compile(r"^FARA", re.IGNORECASE)),
    ("lda", re.compile(r"^LDA", re.IGNORECASE)),
    ("sec_edgar", re.compile(r"^(?:SEC|EDGAR)", re.IGNORECASE)),
    ("irs_990", re.compile(r"^(?:990|IRS.?990|ProPublica|PP990|PROPUBLICA)", re.IGNORECASE)),
    ("ds10", re.compile(r"^DS10", re.IGNORECASE)),
    ("lmsband", re.compile(r"^LMSBAND", re.IGNORECASE)),
    ("doj_vol11", re.compile(r"^DOJ.?(?:Vol|11)", re.IGNORECASE)),
    ("duggan", re.compile(r"^DugganUSA", re.IGNORECASE)),
    ("unified", re.compile(r"^Unified", re.IGNORECASE)),
    ("gleif", re.compile(r"^GLEIF", re.IGNORECASE)),
    ("opensanctions", re.compile(r"^OpenSanctions", re.IGNORECASE)),
    ("icij", re.compile(r"^ICIJ", re.IGNORECASE)),
    ("occrp", re.compile(r"^OCCRP", re.IGNORECASE)),
    ("gdelt", re.compile(r"^GDELT", re.IGNORECASE)),
    ("faa", re.compile(r"^FAA", re.IGNORECASE)),
    ("ucc", re.compile(r"^UCC", re.IGNORECASE)),
    ("state_registry", re.compile(r"^(?:FL_SUNBIZ|FL.SunBiz|FL:|NY_DOS|NY.SoS|NY.DOS|NM.SoS|DC_|OC:|UK.Companies)", re.IGNORECASE)),
    ("url", re.compile(r"^https?://", re.IGNORECASE)),
]


def classify_evidence_ref(ref: str) -> str:
    if not ref:
        return "unknown"
    for source_type, pattern in EVIDENCE_REF_PATTERNS:
        if pattern.search(ref):
            return source_type
    return "other"


def extract_citations(text: str) -> Counter:
    """Extract and classify all citation tokens from article text."""
    counts = Counter()
    # Count markdown hyperlinks as contextual
    contextual_links = re.findall(r"\[[^\]]+\]\(https?://[^)]+\)", text)
    counts["contextual_link"] = len(contextual_links)

    for source_type, pattern in CITATION_PATTERNS:
        matches = pattern.findall(text)
        counts[source_type] += len(matches)

    return counts


def find_cluster_for_article(article_path: Path) -> dict | None:
    """Find the cluster definition matching an article."""
    if not CLUSTERS_PATH.exists():
        return None

    cluster_id = article_path.stem
    clusters = json.loads(CLUSTERS_PATH.read_text())
    for c in clusters:
        if c.get("id") == cluster_id:
            return c
    return None


def find_available_evidence(conn: sqlite3.Connection, targets: list[str]) -> Counter:
    """Count available evidence by source type for given targets."""
    counts = Counter()
    placeholders = ",".join("?" * len(targets))
    rows = conn.execute(
        f"""
        SELECT fe.evidence_ref
        FROM finding_evidence fe
        JOIN findings f ON fe.finding_id = f.id
        WHERE f.target_name IN ({placeholders})
          AND f.verification_status != 'retracted'
          AND fe.evidence_ref IS NOT NULL
        """,
        targets,
    ).fetchall()

    for row in rows:
        stype = classify_evidence_ref(row[0])
        counts[stype] += 1

    return counts


def main():
    parser = argparse.ArgumentParser(description="Analyze article citation diversity")
    parser.add_argument("article", type=Path, help="Path to MDX article")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.article.exists():
        print(f"File not found: {args.article}", file=sys.stderr)
        sys.exit(1)

    text = args.article.read_text()
    citations = extract_citations(text)
    total = sum(citations.values())

    # Find cluster and available evidence
    cluster = find_cluster_for_article(args.article)
    available = Counter()
    if cluster and DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        available = find_available_evidence(conn, cluster.get("targets", []))
        conn.close()

    # Compute metrics
    dominant_pct = 0.0
    dominant_type = "none"
    if total > 0:
        dominant_type = citations.most_common(1)[0][0]
        dominant_pct = round(citations.most_common(1)[0][1] / total * 100, 1)

    available_total = sum(available.values())

    # Identify uncited source types
    uncited = {}
    for stype, count in sorted(available.items(), key=lambda x: -x[1]):
        if count > 0 and citations.get(stype, 0) == 0:
            uncited[stype] = count

    result = {
        "article": str(args.article),
        "citations": dict(citations.most_common()),
        "total_citations": total,
        "source_types_cited": len([k for k, v in citations.items() if v > 0]),
        "dominant_source": dominant_type,
        "dominant_pct": dominant_pct,
        "single_source_warning": dominant_pct > 80,
        "available_evidence": dict(available.most_common()),
        "available_total": available_total,
        "uncited_sources": uncited,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    # Human-readable output
    print(f"\n  Citation Diversity: {args.article.name}")
    print(f"  {'=' * 50}")
    print(f"\n  Total citations: {total}")
    print(f"  Source types cited: {result['source_types_cited']}")
    print(f"  Dominant source: {dominant_type} ({dominant_pct}%)")
    if result["single_source_warning"]:
        print(f"  WARNING: >80% from single source type")

    print(f"\n  {'Source Type':<20} {'Cited':<8} {'Available':<10} {'Gap'}")
    print(f"  {'-' * 50}")

    all_types = sorted(set(list(citations.keys()) + list(available.keys())))
    for stype in all_types:
        cited = citations.get(stype, 0)
        avail = available.get(stype, 0)
        gap = avail - cited if avail > cited else ""
        marker = " <--" if avail > 0 and cited == 0 else ""
        print(f"  {stype:<20} {cited:<8} {avail:<10} {gap}{marker}")

    if uncited:
        print(f"\n  Available but uncited sources:")
        for stype, count in sorted(uncited.items(), key=lambda x: -x[1]):
            print(f"    {stype}: {count} evidence items")


if __name__ == "__main__":
    main()
