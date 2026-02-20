#!/usr/bin/env python3
"""Bucket missing source_quote rows into actionable citation triage queues.

Buckets:
1) canonical-but-missing-quote
2) search-breadcrumb
3) malformed
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INV_DB = REPO_ROOT / "investigation.db"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "evidence-triage"
DOCS_DB = Path("/Users/travcole/projects/epstein-docs/output/documents.db")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.evidence_refs import canonicalize_evidence_ref


@dataclass
class MissingRow:
    finding_id: int
    target_name: str
    claim_type: str
    confidence: str
    evidence_type: str
    evidence_ref: str
    summary: str
    bucket: str
    priority_group: str
    priority_score: int
    docsdb_status: str
    suggested_action: str


CANONICAL_PATTERNS = [
    re.compile(r"^EFTA\d+$", re.IGNORECASE),
    re.compile(r"^HOUSE_OVERSIGHT_\d+$", re.IGNORECASE),
    re.compile(r"^DS10(?::[A-Za-z0-9_-]+)?$", re.IGNORECASE),
    re.compile(r"^SEC:\d{10}-\d{2}-\d{6}$", re.IGNORECASE),
    re.compile(r"^EDGAR:\d{10}-\d{2}-\d{6}$", re.IGNORECASE),
    re.compile(r"^990:\d{9}$", re.IGNORECASE),
    re.compile(r"^ACRIS:\d{13,16}$", re.IGNORECASE),
    re.compile(r"^CL:\d+$", re.IGNORECASE),
    re.compile(r"^FEC:[A-Za-z0-9_/-]+$", re.IGNORECASE),
    re.compile(r"^FARA:\d+$", re.IGNORECASE),
    re.compile(r"^USVI:[A-Za-z0-9]+$", re.IGNORECASE),
    re.compile(r"^REG:[A-Z]{2}:[A-Za-z0-9]+$", re.IGNORECASE),
    re.compile(r"^FL[-_]?SunBiz[:\s]+[A-Za-z0-9]+$", re.IGNORECASE),
    re.compile(r"^NM[-_]?SoS[:\s]+[A-Za-z0-9]+$", re.IGNORECASE),
    re.compile(r"^NY[-_]?SoS[:\s]+[A-Za-z0-9]+$", re.IGNORECASE),
    re.compile(r"^https?://\S+$", re.IGNORECASE),
    re.compile(r"^DOCUMENTCLOUD:\d+$", re.IGNORECASE),
    re.compile(r"^MUCKROCK:[^\s]+$", re.IGNORECASE),
    re.compile(r"^OffshoreAlert:[A-Za-z0-9._:-]+$", re.IGNORECASE),
    re.compile(r"^LittleSis[: ](?:entity )?\d+$", re.IGNORECASE),
    re.compile(r"^OpenSanctions\b[\w:.-]*$", re.IGNORECASE),
    re.compile(r"^ICIJ[\w:.-]*$", re.IGNORECASE),
    re.compile(r"^OCCRP[\w:.-]*$", re.IGNORECASE),
    re.compile(r"^LMSBAND:[A-Za-z0-9_.:-]+$", re.IGNORECASE),
]

SEARCH_BREADCRUMB_RE = re.compile(
    r"(search|query|hits?|results?|negative|analysis-run|docs searched|0 results|api\b|_search\b)",
    re.IGNORECASE,
)


def is_high_priority(claim_type: str, confidence: str) -> bool:
    return claim_type == "direct_quote" or confidence == "confirmed"


def is_canonical_ref(value: str) -> bool:
    text = value.strip()
    return any(pattern.match(text) for pattern in CANONICAL_PATTERNS)


def is_search_breadcrumb(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    return bool(SEARCH_BREADCRUMB_RE.search(text))


def choose_bucket(evidence_ref: str) -> str:
    text = (evidence_ref or "").strip()
    if is_search_breadcrumb(text):
        return "search-breadcrumb"
    if is_canonical_ref(text):
        return "canonical-but-missing-quote"
    return "malformed"


def docsdb_efta_status_map() -> set[str]:
    if not DOCS_DB.exists():
        return set()
    conn = sqlite3.connect(str(DOCS_DB))
    try:
        rows = conn.execute(
            "SELECT bates_id FROM documents WHERE bates_id LIKE 'EFTA%'"
        ).fetchall()
        return {str(row[0]).strip() for row in rows if row and row[0]}
    finally:
        conn.close()


def suggested_action(row: MissingRow, normalized_tokens: list[str]) -> str:
    ref = row.evidence_ref.strip()
    if row.bucket == "search-breadcrumb":
        return "Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail."

    if row.bucket == "canonical-but-missing-quote":
        if ref.upper().startswith("EFTA"):
            if row.docsdb_status == "present":
                return "Run EFTA quote backfill for this finding/ref."
            return "Ingest missing EFTA document into docs DB, then rerun quote backfill."
        if ref.lower().startswith("http://") or ref.lower().startswith("https://"):
            return "Extract a concise source quote from the URL content or downgrade claim confidence."
        if row.evidence_type == "file":
            return "Extract a direct quote from the file evidence and populate source_quote."
        return "Populate source_quote from the cited source record."

    if normalized_tokens and len(normalized_tokens) > 1:
        tokens = ", ".join(normalized_tokens[:6])
        suffix = "..." if len(normalized_tokens) > 6 else ""
        return f"Split/normalize evidence_ref into canonical tokens: {tokens}{suffix}"
    if normalized_tokens and normalized_tokens[0] != ref:
        return f"Normalize evidence_ref to canonical token: {normalized_tokens[0]}"
    return "Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token."


def priority_score(claim_type: str, confidence: str, bucket: str) -> int:
    score = 0
    if is_high_priority(claim_type, confidence):
        score += 1000
    if bucket == "canonical-but-missing-quote":
        score += 100
    elif bucket == "malformed":
        score += 50
    return score


def bucket_sort_key(bucket: str) -> int:
    order = {
        "canonical-but-missing-quote": 0,
        "search-breadcrumb": 1,
        "malformed": 2,
    }
    return order.get(bucket, 9)


def load_missing_rows(conn: sqlite3.Connection, efta_docs: set[str]) -> list[MissingRow]:
    rows = conn.execute(
        """
        SELECT fe.finding_id,
               f.target_name,
               f.claim_type,
               f.confidence,
               fe.evidence_type,
               fe.evidence_ref,
               COALESCE(f.summary, '') AS summary
        FROM finding_evidence fe
        JOIN findings f ON f.id = fe.finding_id
        WHERE fe.source_quote IS NULL OR fe.source_quote = ''
        ORDER BY fe.finding_id
        """
    ).fetchall()

    out: list[MissingRow] = []
    for raw in rows:
        evidence_ref = str(raw["evidence_ref"] or "").strip()
        bucket = choose_bucket(evidence_ref)
        claim_type = str(raw["claim_type"] or "")
        confidence = str(raw["confidence"] or "")
        docs_status = "n/a"
        if evidence_ref.upper().startswith("EFTA"):
            docs_status = "present" if evidence_ref in efta_docs else "absent"

        normalized_tokens = canonicalize_evidence_ref(evidence_ref)
        priority_group = "high" if is_high_priority(claim_type, confidence) else "normal"
        row = MissingRow(
            finding_id=int(raw["finding_id"]),
            target_name=str(raw["target_name"] or ""),
            claim_type=claim_type,
            confidence=confidence,
            evidence_type=str(raw["evidence_type"] or ""),
            evidence_ref=evidence_ref,
            summary=str(raw["summary"] or "").strip(),
            bucket=bucket,
            priority_group=priority_group,
            priority_score=priority_score(claim_type, confidence, bucket),
            docsdb_status=docs_status,
            suggested_action="",
        )
        row.suggested_action = suggested_action(row, normalized_tokens)
        out.append(row)

    out.sort(
        key=lambda r: (
            -r.priority_score,
            bucket_sort_key(r.bucket),
            r.finding_id,
            r.evidence_ref.lower(),
        )
    )
    return out


def write_csv(path: Path, rows: list[MissingRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "priority_group",
                "bucket",
                "finding_id",
                "target_name",
                "claim_type",
                "confidence",
                "evidence_type",
                "evidence_ref",
                "docsdb_status",
                "suggested_action",
                "summary",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.priority_group,
                    row.bucket,
                    row.finding_id,
                    row.target_name,
                    row.claim_type,
                    row.confidence,
                    row.evidence_type,
                    row.evidence_ref,
                    row.docsdb_status,
                    row.suggested_action,
                    row.summary,
                ]
            )


def summarize(rows: list[MissingRow]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for row in rows:
        slot = stats.setdefault(row.bucket, {"total": 0, "high": 0})
        slot["total"] += 1
        if row.priority_group == "high":
            slot["high"] += 1
    return stats


def markdown_table_rows(rows: list[MissingRow], limit: int) -> str:
    lines = [
        "| finding_id | target | claim/confidence | evidence_ref | action |",
        "|---|---|---|---|---|",
    ]
    for row in rows[:limit]:
        claim = f"{row.claim_type}/{row.confidence}"
        ref = row.evidence_ref.replace("|", "\\|")
        action = row.suggested_action.replace("|", "\\|")
        lines.append(
            f"| {row.finding_id} | {row.target_name} | {claim} | `{ref}` | {action} |"
        )
    return "\n".join(lines)


def write_markdown(path: Path, rows: list[MissingRow], stats: dict[str, dict[str, int]], top_n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = dt.datetime.now().isoformat(timespec="seconds")
    high_rows = [row for row in rows if row.priority_group == "high"]
    efta_missing = [row for row in rows if row.evidence_ref.upper().startswith("EFTA")]
    efta_missing_docs_absent = [row for row in efta_missing if row.docsdb_status == "absent"]
    ds10_rows = [row for row in rows if row.evidence_ref.upper().startswith("DS10")]
    duggan_rows = [row for row in rows if row.evidence_ref.upper().startswith("DUGGAN")]

    by_bucket = {
        bucket: [row for row in rows if row.bucket == bucket]
        for bucket in ["canonical-but-missing-quote", "search-breadcrumb", "malformed"]
    }
    high_by_bucket = {
        bucket: [row for row in high_rows if row.bucket == bucket]
        for bucket in by_bucket
    }

    md = []
    md.append("# Missing Evidence Citation Triage")
    md.append("")
    md.append(f"- Generated: `{generated}`")
    md.append(f"- Total missing `source_quote` rows: **{len(rows)}**")
    md.append(f"- High-priority rows (`direct_quote` or `confirmed`): **{len(high_rows)}**")
    md.append(f"- DS10 missing rows: **{len(ds10_rows)}**")
    md.append(f"- Duggan missing rows: **{len(duggan_rows)}**")
    md.append(f"- Missing EFTA rows: **{len(efta_missing)}**")
    md.append(
        f"- Missing EFTA rows absent from local docs DB: **{len(efta_missing_docs_absent)}**"
    )
    md.append("")
    md.append("## Bucket Counts")
    md.append("")
    md.append("| bucket | total | high-priority |")
    md.append("|---|---:|---:|")
    for bucket in ["canonical-but-missing-quote", "search-breadcrumb", "malformed"]:
        slot = stats.get(bucket, {"total": 0, "high": 0})
        md.append(f"| {bucket} | {slot['total']} | {slot['high']} |")
    md.append("")

    for bucket in ["canonical-but-missing-quote", "search-breadcrumb", "malformed"]:
        md.append(f"## Top High-Priority: {bucket}")
        md.append("")
        md.append(markdown_table_rows(high_by_bucket[bucket], top_n))
        md.append("")

    md.append("## Top Queue (All Buckets)")
    md.append("")
    md.append(markdown_table_rows(rows, top_n))
    md.append("")
    md.append("## Notes")
    md.append("")
    md.append("- `search-breadcrumb` rows usually represent tool/search provenance rather than citable evidence items.")
    md.append("- `malformed` rows usually include packed refs, free-text references, or non-canonical token variants.")
    md.append("- `canonical-but-missing-quote` rows usually need quote extraction/backfill from the underlying source.")
    md.append("")

    path.write_text("\n".join(md) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage missing evidence citations into action buckets.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--top-n", type=int, default=40, help="Rows to show per markdown table.")
    args = parser.parse_args()

    if not INV_DB.exists():
        print(f"Missing investigation DB: {INV_DB}", file=sys.stderr)
        return 2

    efta_docs = docsdb_efta_status_map()
    conn = sqlite3.connect(str(INV_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = load_missing_rows(conn, efta_docs)
    finally:
        conn.close()

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir
    csv_path = out_dir / f"missing-evidence-triage-{timestamp}.csv"
    md_path = out_dir / f"missing-evidence-triage-{timestamp}.md"
    latest_csv = out_dir / "missing-evidence-triage-latest.csv"
    latest_md = out_dir / "missing-evidence-triage-latest.md"

    stats = summarize(rows)
    write_csv(csv_path, rows)
    write_markdown(md_path, rows, stats, args.top_n)
    write_csv(latest_csv, rows)
    write_markdown(latest_md, rows, stats, args.top_n)

    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(f"Updated {latest_md}")
    print(f"Updated {latest_csv}")
    print(f"Rows triaged: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
