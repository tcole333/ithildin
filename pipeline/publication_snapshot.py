#!/usr/bin/env python3
"""Validate and materialize a DB-free, content-bound publication finding catalog.

A snapshot is a candidate artifact, not editorial approval. Release validation
also requires the separate semantic review receipts. Neither command edits
articles or dossiers; --db is an optional local current-state audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from tools import findings_tracker as finding_policy  # noqa: E402

REFERENCE_RE = re.compile(r"\bFinding\s*#\s*(\d+)", re.IGNORECASE)
FIELDS = ("summary", "finding_type", "confidence", "claim_type", "verification_status", "date_of_event")
EVIDENCE_FIELDS = ("evidence_type", "evidence_ref", "source_quote", "source_page", "assessment")


def normalize_finding(record: dict) -> dict:
    result = {"id": str(record["id"])}
    result.update({key: record.get(key) or "" for key in FIELDS})
    evidence = [{key: item.get(key) or "" for key in EVIDENCE_FIELDS}
                for item in record.get("evidence", [])]
    result["evidence"] = sorted(evidence, key=lambda item: json.dumps(item, sort_keys=True))
    return result


def content_files(content_dir: Path) -> list[Path]:
    return sorted(
        [p for p in (content_dir / "dossiers").glob("*.json") if not p.name.startswith("_")]
        + list((content_dir / "articles").glob("*.mdx"))
        + list((content_dir / "articles").glob("*-findings.json"))
    )


def finding_issues(record: dict, *, file: str, location: str) -> list[dict]:
    """Check exported provenance without opening a DB, corpus, or local source.

    Reuse the tracker's pure vocabulary, reference classification, and confidence
    policies. Its full publication validator also resolves local quote spans and
    must not run during this self-contained snapshot check. Older exports may
    omit source_datasets; when supplied, validate it and enforce its source cap.
    """
    issues = []
    context = {"file": file, "location": location}
    raw_id = record.get("id")
    if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool) and re.fullmatch(r"[1-9]\d*", str(raw_id)):
        context["finding_id"] = str(raw_id)
    else:
        issues.append({**context, "code": "invalid_finding_id", "detail": "id must be a positive integer or its decimal string"})

    def issue(code: str, **detail) -> None:
        issues.append({**context, "code": code, **detail})

    for field in FIELDS:
        value = record.get(field)
        if value is not None and not isinstance(value, str):
            issue("invalid_finding_field", field=field, detail="expected a string or null")
    if not isinstance(record.get("summary"), str) or not record["summary"].strip():
        issue("missing_finding_summary")
    if record.get("verification_status") != "verified":
        issue("non_verified_finding", status=record.get("verification_status"))
    claim_type, confidence = record.get("claim_type"), record.get("confidence")
    valid_claim = isinstance(claim_type, str) and claim_type in finding_policy.VALID_CLAIM_TYPES
    valid_confidence = isinstance(confidence, str) and confidence in finding_policy.VALID_CONFIDENCE
    if not valid_claim:
        issue("invalid_claim_type", detail="missing or unsupported claim_type")
    if not valid_confidence:
        issue("invalid_confidence", detail="missing or unsupported confidence")
    finding_type = record.get("finding_type")
    if finding_type is not None and finding_type not in finding_policy.VALID_FINDING_TYPES:
        issue("invalid_finding_type")

    sources = []
    if "source_datasets" in record:
        try:
            sources = finding_policy._parse_stored_source_datasets(record["source_datasets"])
        except ValueError as error:
            issue("invalid_source_datasets", detail=str(error))
    if valid_claim and valid_confidence:
        allowed, claim_clamped = finding_policy._enforce_confidence_cap(claim_type, confidence)
        allowed, source_clamped = finding_policy._enforce_source_confidence_cap(sources, allowed)
        if claim_clamped or source_clamped:
            issue("confidence_exceeds_cap", confidence=confidence, max_confidence=allowed)

    evidence = record.get("evidence")
    if not isinstance(evidence, list):
        issue("invalid_evidence_collection", field="evidence", detail="expected a nonempty array")
        return issues
    if not evidence:
        issue("missing_finding_evidence")
    seen_refs = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            issue("invalid_evidence_record", evidence_index=index, detail="expected an object")
            continue
        ref = item.get("evidence_ref")
        if not isinstance(ref, str) or not ref.strip():
            issue("invalid_evidence_ref", evidence_index=index, detail="expected a nonempty string")
        else:
            if ref.strip() in seen_refs:
                issue("duplicate_evidence_ref", evidence_index=index, evidence_ref=ref)
            seen_refs.add(ref.strip())
            stored_type = item.get("evidence_type")
            if stored_type is not None:
                try:
                    expected_type = finding_policy._classify_evidence_ref(ref)
                except ValueError as error:
                    issue("invalid_evidence_ref", evidence_index=index, detail=str(error))
                else:
                    if stored_type != expected_type:
                        issue("evidence_type_mismatch", evidence_index=index, evidence_ref=ref,
                              expected_type=expected_type, stored_type=stored_type)
        quote = item.get("source_quote")
        if not isinstance(quote, str) or not quote.strip():
            issue("missing_source_quote", evidence_index=index, evidence_ref=ref,
                  detail="every reference requires a nonblank textual source quote")
        for field in ("source_page", "assessment"):
            if item.get(field) is not None and not isinstance(item[field], str):
                issue("invalid_evidence_field", evidence_index=index, field=field, detail="expected a string or null")
    return issues


def collect_content(content_dir: Path) -> tuple[dict, dict, list[dict]]:
    findings: dict[str, dict] = {}
    seen_findings: dict[str, dict] = {}
    known_finding_ids: set[str] = set()
    hashes: dict[str, str] = {}
    issues: list[dict] = []
    references: set[tuple[str, str]] = set()
    for path in content_files(content_dir):
        relative = path.relative_to(content_dir).as_posix()
        try:
            raw = path.read_bytes()
        except OSError as error:
            issues.append({"code": "unreadable_content", "file": relative, "detail": str(error)})
            continue
        hashes[relative] = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            issues.append({"code": "invalid_content_encoding", "file": relative, "detail": str(error)})
            continue
        references.update((fid, relative) for fid in REFERENCE_RE.findall(text))
        if path.suffix == ".mdx":
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            issues.append({"code": "invalid_content_json", "file": relative, "detail": str(error)})
            continue
        if not isinstance(payload, dict):
            issues.append({"code": "invalid_content_shape", "file": relative, "detail": "expected an object"})
            continue
        records = []
        if path.name.endswith("-findings.json"):
            records = list(payload.items())
        else:
            for field in ("findings", "citation_findings"):
                values = payload.get(field, [])
                if not isinstance(values, list):
                    issues.append({"code": "invalid_finding_collection", "file": relative,
                                   "field": field, "detail": "expected an array"})
                    continue
                records.extend((f"{field}[{index}]", record) for index, record in enumerate(values))
        for location, record in records:
            if not isinstance(record, dict):
                issues.append({"code": "invalid_finding_record", "file": relative,
                               "location": location, "detail": "expected an object"})
                continue
            record_issues = finding_issues(record, file=relative, location=location)
            issues.extend(record_issues)
            if not any(issue["code"] == "invalid_finding_id" for issue in record_issues):
                known_finding_ids.add(str(record["id"]))
            if any(issue["code"] in {"invalid_finding_id", "invalid_evidence_collection", "invalid_evidence_record"}
                   for issue in record_issues):
                continue
            normalized = normalize_finding(record)
            fid = normalized["id"]
            if fid in seen_findings and seen_findings[fid] != normalized:
                issues.append({"code": "conflicting_finding", "finding_id": fid, "file": relative})
            seen_findings[fid] = normalized
            if not record_issues:
                # Invalid legacy claims never enter the candidate catalog,
                # even when they carry an old verified status.
                findings[fid] = normalized
    for fid, relative in sorted(references):
        if fid not in findings:
            code = "unpublishable_cited_finding" if fid in known_finding_ids else "missing_cited_finding"
            issues.append({"code": code, "finding_id": fid, "file": relative})
    return findings, hashes, issues


def audit_database(findings: dict, db_path: Path) -> list[dict]:
    """Validate current DB provenance before comparing schema-1 fingerprints."""
    issues = []
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        for fid, snapshot in findings.items():
            row = db.execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()
            if row is None:
                issues.append({"code": "missing_database_finding", "finding_id": fid})
                continue
            record = dict(row)
            record["evidence"] = [dict(item) for item in db.execute(
                "SELECT * FROM finding_evidence WHERE finding_id=?", (fid,))]
            # Source metadata is intentionally absent from normalized snapshot
            # fields. Its current value can still invalidate publication (for
            # example, a provenance-opaque source imposes a lower confidence
            # ceiling), so normalization must not erase this audit obligation.
            record.setdefault("source_datasets", None)
            issues.extend({**issue, "scope": "database"} for issue in finding_issues(
                record, file=str(db_path), location=f"findings[{fid}]",
            ))
            current = normalize_finding(record)
            if current != snapshot:
                issues.append({"code": "database_drift", "finding_id": fid,
                               "current_status": current["verification_status"],
                               "changed_fields": [key for key in current if current[key] != snapshot[key]]})
    return issues


def validate_snapshot(content_dir: Path, snapshot_path: Path, db_path: Path | None = None) -> dict:
    findings, hashes, issues = collect_content(content_dir)
    if not snapshot_path.is_file():
        issues.append({"code": "missing_snapshot", "file": str(snapshot_path)})
    else:
        try:
            snapshot = json.loads(snapshot_path.read_text())
        except (OSError, ValueError) as error:
            issues.append({"code": "invalid_snapshot_json", "file": str(snapshot_path), "detail": str(error)})
        else:
            if not isinstance(snapshot, dict):
                issues.append({"code": "invalid_snapshot_shape", "file": str(snapshot_path), "detail": "expected an object"})
            else:
                if type(snapshot.get("schema_version")) is not int or snapshot["schema_version"] != 1:
                    issues.append({"code": "unsupported_snapshot_version", "file": str(snapshot_path)})
                if snapshot.get("source_hashes") != hashes:
                    issues.append({"code": "snapshot_content_changed"})
                if snapshot.get("findings") != findings:
                    issues.append({"code": "snapshot_findings_changed"})
    if db_path is not None:
        issues.extend(audit_database(findings, db_path))
    return {"ok": not issues, "finding_count": len(findings), "source_count": len(hashes), "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--content-dir", type=Path, default=ROOT / "content")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--db", type=Path, help="Optional read-only comparison with the live investigation DB")
    parser.add_argument("--output", type=Path, help="Required candidate snapshot for build; optional JSON report for check (default: stdout)")
    args = parser.parse_args()
    if args.command == "build" and args.output is None:
        parser.error("build requires --output for the candidate snapshot")
    try:
        if args.command == "check":
            result = validate_snapshot(args.content_dir, args.snapshot or args.content_dir / "finding-catalog.json", args.db)
        else:
            findings, hashes, issues = collect_content(args.content_dir)
            if args.db:
                issues.extend(audit_database(findings, args.db))
            if issues:
                print(json.dumps({"ok": False, "issues": issues}, indent=2))
                return 1
            result = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
                      "source_hashes": hashes, "findings": findings}
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded)
        else:
            print(encoded, end="")
        return 0 if result.get("ok", True) else 1
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        print(json.dumps({"ok": False, "issues": [{"code": "invalid_publication_input", "detail": str(error)}]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
