#!/usr/bin/env python3
"""Read-only evidence checks against the selected database/profile and current article.

A text match proves quote presence, not claim support or the truth of allegations.
Unavailable source text is unknown, never a successful cross-check.
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.story_clustering import classify_evidence_ref  # noqa: E402


def open_readonly(db_path):
    db = sqlite3.connect(Path(db_path).expanduser().resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def ensure_safe_output(output, inputs, databases=()):
    """Protect source bytes and SQLite state, including existing hardlink aliases."""
    protected = [Path(item).expanduser().resolve() for item in inputs if item]
    for database in databases:
        if database:
            resolved = Path(database).expanduser().resolve()
            protected.extend(Path(str(resolved) + suffix) for suffix in ("-wal", "-shm", "-journal"))
    destination = Path(output).expanduser().resolve()
    for source in protected:
        if destination == source or (destination.exists() and source.exists() and destination.samefile(source)):
            raise ValueError("--output must not overwrite a database, SQLite sidecar, article, or source input")


def normalize_ocr(text):
    text = re.sub(r"=\n", "", text or "")
    text = re.sub(r"=br>", "\n", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip().lower()


def jaccard_tokens(text_a, text_b):
    stop = {"the", "and", "for", "that", "with", "from", "was", "were", "this"}
    sets = [set(re.findall(r"\w{3,}", text.lower())) - stop for text in (text_a, text_b)]
    return len(sets[0] & sets[1]) / len(sets[0] | sets[1]) if all(sets) else 0.0


def article_citations(text):
    """Extract explicit finding IDs/canonical tokens. Never fuzzy-join identities."""
    ids, refs = set(), set()
    text = re.sub(r"\A---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)", "", text, count=1)
    for match in re.finditer(r"\[([^\[\]\n]+)\]", text):
        token = match[1].strip()
        finding = re.fullmatch(r"Finding\s*#?\s*(\d+)", token, re.IGNORECASE)
        if finding:
            ids.add(int(finding[1]))
        elif not text[match.end():].startswith("("):
            # Keep bracket tokens conservatively, including numeric, mixed-case,
            # hyphenated and legacy space-separated references. Unknown aliases
            # must remain visible rather than silently producing a clean audit.
            refs.add(token)
    refs.update(re.findall(r"\]\((https?://[^\s)]+)\)", text))
    return ids, refs


def resolve_profile(db, profile, all_profiles):
    if all_profiles:
        return None
    selected = profile or os.environ.get("ITHILDIN_PROFILE")
    if not selected:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "investigation_config" in tables:
            row = db.execute("SELECT value FROM investigation_config WHERE key='active_profile'").fetchone()
            selected = row[0] if row else None
    if not selected:
        raise ValueError("No pinned profile: pass --profile or explicitly use --all-profiles")
    return selected


def load_scope(db, profile, finding_ids=(), article=None):
    requested_ids, refs, article_hash = set(finding_ids), set(), None
    if article:
        raw = Path(article).read_bytes()
        article_hash = hashlib.sha256(raw).hexdigest()
        article_ids, refs = article_citations(raw.decode("utf-8"))
        requested_ids.update(article_ids)
    conditions, params = [], []
    if profile:
        conditions.append("f.profile_id = ?")
        params.append(profile)
    if article or requested_ids:
        selectors = []
        if requested_ids:
            selectors.append(f"f.id IN ({','.join('?' for _ in requested_ids)})")
            params.extend(sorted(requested_ids))
        if refs:
            selectors.append("EXISTS (SELECT 1 FROM finding_evidence ce WHERE ce.finding_id=f.id "
                             f"AND ce.evidence_ref IN ({','.join('?' for _ in refs)}))")
            params.extend(sorted(refs))
        conditions.append("(" + " OR ".join(selectors or ["0"]) + ")")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    findings = [dict(row) for row in db.execute("SELECT f.* FROM findings f" + where + " ORDER BY f.id", params)]
    evidence = [dict(row) for row in db.execute(
        "SELECT fe.* FROM finding_evidence fe JOIN findings f ON f.id=fe.finding_id" + where
        + " ORDER BY fe.finding_id, fe.evidence_ref", params)]
    return findings, evidence, {
        "article": str(Path(article).resolve()) if article else None,
        "content_sha256": article_hash,
        "finding_ids": [row["id"] for row in findings],
        "requested_finding_ids": sorted(requested_ids),
        "missing_or_out_of_profile_finding_ids": sorted(requested_ids - {row["id"] for row in findings}),
        "unmapped_citations": sorted(refs - {row["evidence_ref"] for row in evidence}),
        "citation_mapping": "exact identifiers only; unresolved aliases require review",
    }


def source_text(ref, sources, manifest_dir, documents_db):
    if ref in sources:
        item = sources[ref]
        file_path = Path(item["path"] if isinstance(item, dict) else item)
        if not file_path.is_absolute():
            file_path = manifest_dir / file_path
        try:
            return file_path.read_text(), str(file_path.resolve()), None
        except (OSError, UnicodeError) as exc:
            return None, str(file_path), f"source artifact unreadable: {exc}"
    if documents_db and re.fullmatch(r"EFTA\d+", ref):
        try:
            db = open_readonly(documents_db)
            try:
                row = db.execute("SELECT ocr_text FROM documents WHERE bates_id=?", (ref,)).fetchone()
            finally:
                db.close()
            if row and row[0]:
                return row[0], f"{Path(documents_db).resolve()}#{ref}", None
            return None, str(documents_db), "document or OCR text missing"
        except (OSError, sqlite3.Error) as exc:
            return None, str(documents_db), f"document corpus unavailable: {exc}"
    return None, None, "no local source text supplied for this reference"


def cross_check(evidence, sources=None, manifest_dir=ROOT, documents_db=None):
    results = []
    for row in evidence:
        ref = row["evidence_ref"]
        item = {"finding_id": row["finding_id"], "evidence_ref": ref, "result": "unknown"}
        quote = normalize_ocr(row.get("source_quote"))
        if len(quote) < 10:
            item["reason"] = "missing or too-short quote for a meaningful text check"
        else:
            content, locator, reason = source_text(ref, sources or {}, manifest_dir, documents_db)
            item["source"] = locator
            if content is None:
                item["reason"] = reason
            else:
                item["source_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
                item["result"] = "match" if quote in normalize_ocr(content) else "mismatch"
                item["reason"] = ("full normalized quote present" if item["result"] == "match"
                                  else "full normalized quote absent; inspect source/OCR before correcting")
        results.append(item)
    return results


def build_report(db_path, *, profile=None, all_profiles=False, finding_ids=(), article=None,
                 documents_db=None, source_texts=None, threshold=0.6):
    db = open_readonly(db_path)
    try:
        db.execute("BEGIN")
        selected_profile = resolve_profile(db, profile, all_profiles)
        findings, evidence, scope = load_scope(db, selected_profile, finding_ids, article)
    finally:
        db.close()
    sources = json.loads(Path(source_texts).read_text()) if source_texts else {}
    if not isinstance(sources, dict):
        raise ValueError("--source-texts requires a JSON object mapping evidence_ref to a text-file path")
    checks = cross_check(evidence, sources,
                         Path(source_texts).resolve().parent if source_texts else ROOT, documents_db)
    missing = [{"finding_id": row["finding_id"], "evidence_ref": row["evidence_ref"],
                "source_type": classify_evidence_ref(row["evidence_ref"])}
               for row in evidence if not (row.get("source_quote") or "").strip()]
    by_finding, by_ref = defaultdict(list), defaultdict(list)
    for row in evidence:
        by_finding[row["finding_id"]].append(row)
        by_ref[row["evidence_ref"]].append(row["finding_id"])
    findings_by_id = {row["id"]: row for row in findings}
    violations = []
    for row in findings:
        reasons = []
        if not by_finding[row["id"]]:
            reasons.append("no evidence references")
        if row.get("confidence") == "confirmed" and row.get("claim_type") not in {"direct_quote", "user_provided"}:
            reasons.append("confirmed confidence requires a primary direct quote")
        if row.get("claim_type") in {"inference", "synthesis"} and row.get("confidence") in {"high", "confirmed"}:
            reasons.append("inference/synthesis confidence exceeds medium")
        if row.get("verification_status") in {"disputed", "retracted"}:
            reasons.append("finding is " + row["verification_status"])
        if reasons:
            violations.append({"finding_id": row["id"], "reasons": reasons})
    overlap = []
    for ref, ids in by_ref.items():
        unique = sorted(set(ids))
        if len(unique) < 3:
            continue
        pairs = []
        for index, first in enumerate(unique):
            for second in unique[index + 1:]:
                score = jaccard_tokens(findings_by_id[first].get("summary") or "",
                                       findings_by_id[second].get("summary") or "")
                if score > threshold:
                    pairs.append({"finding_ids": [first, second], "similarity": round(score, 3)})
        overlap.append({"evidence_ref": ref, "finding_ids": unique, "similar_pairs": pairs,
                        "assessment": "shared source / possible overlap; not an adjudicated duplicate"})
    counts = {state: sum(item["result"] == state for item in checks) for state in ("match", "mismatch", "unknown")}
    needs_review = bool(missing or violations or counts["mismatch"] or scope["missing_or_out_of_profile_finding_ids"])
    incomplete = bool(counts["unknown"] or scope["unmapped_citations"] or not findings)
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(Path(db_path).expanduser().resolve()), "profile": selected_profile,
        "scope": scope, "finding_count": len(findings), "evidence_count": len(evidence),
        "status": "needs_review" if needs_review else "incomplete" if incomplete else "passed",
        "checks_complete": not incomplete,
        "missing_quotes": missing, "confidence_or_integrity_issues": violations,
        "source_overlap_candidates": overlap, "cross_check_counts": counts, "cross_checks": checks,
        "limitations": ["Text presence does not establish claim support, authenticity, source independence, or allegation truth.",
                        "Overlap candidates require semantic review; they are not adjudicated duplicates."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("report", "missing-quotes", "overlap-detection", "cross-check", "confidence-violations"):
        child = sub.add_parser(command)
        child.add_argument("--db", type=Path, default=Path(os.environ.get("ITHILDIN_DB_PATH") or ROOT / "investigation.db"))
        scope = child.add_mutually_exclusive_group()
        scope.add_argument("--profile")
        scope.add_argument("--all-profiles", action="store_true")
        child.add_argument("--article", type=Path, help="Audit the exact current article bytes and explicit citations")
        child.add_argument("--finding-id", action="append", type=int, default=[])
        child.add_argument("--documents-db", type=Path, default=os.environ.get("ITHILDIN_DOCUMENTS_DB"),
                           help="Optional EFTA corpus with documents.bates_id and ocr_text")
        child.add_argument("--source-texts", type=Path,
                           help="JSON map of evidence refs to UTF-8 text paths, relative to the JSON file")
        child.add_argument("--output", type=Path, help="Write complete JSON results")
        child.add_argument("--limit", type=int, default=20, help="Console detail limit; output JSON remains complete")
        child.add_argument("--threshold", type=float, default=0.6, help="Candidate overlap threshold, not a duplicate judgment")
    args = parser.parse_args()
    try:
        for name in ("db", "article", "documents_db", "source_texts", "output"):
            if getattr(args, name):
                setattr(args, name, Path(getattr(args, name)).expanduser().resolve())
        report = build_report(args.db, profile=args.profile, all_profiles=args.all_profiles,
                              finding_ids=args.finding_id, article=args.article,
                              documents_db=args.documents_db, source_texts=args.source_texts,
                              threshold=args.threshold)
        report["command"] = args.command
        if args.output:
            protected = [args.db, args.article, args.documents_db, args.source_texts]
            if args.source_texts:
                for source in json.loads(args.source_texts.read_text()).values():
                    source_path = Path(source["path"] if isinstance(source, dict) else source)
                    protected.append(source_path if source_path.is_absolute() else args.source_texts.parent / source_path)
            ensure_safe_output(args.output, protected, databases=(args.db, args.documents_db))
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(f"Evidence audit: {report['status']}; {report['finding_count']} findings; {report['cross_check_counts']} → {args.output}")
        else:
            report["console_detail_limit"] = args.limit
            report["detail_counts"] = {key: len(value) for key, value in report.items() if isinstance(value, list)}
            for key, value in list(report.items()):
                if isinstance(value, list):
                    report[key] = value[:args.limit]
            print(json.dumps(report, indent=2))
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        parser.error(str(exc))
    # Diagnostic completion is not publication readiness: consumers inspect status.


if __name__ == "__main__":
    main()
