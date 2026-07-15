#!/usr/bin/env python3
"""Hash and validate the durable artifact package for GEO lead #59356."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "investigations/geo-group/sources/2026-07-14-lead-59356"
REPORT_ROOT = ROOT / "investigations/geo-group/reports"
PREFIX = "2026-07-14-lead-59356-"
MANIFEST = REPORT_ROOT / f"{PREFIX}source-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def item(path: Path) -> dict:
    result = {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }
    if path.suffix == ".csv":
        with path.open(newline="") as handle:
            result["data_rows"] = max(sum(1 for _ in csv.reader(handle)) - 1, 0)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hash and validate the durable artifact package for GEO lead #59356."
    )
    parser.parse_args()

    if not SOURCE_ROOT.is_dir():
        raise SystemExit(f"Missing source archive: {SOURCE_ROOT}")
    source_paths = sorted(path for path in SOURCE_ROOT.rglob("*") if path.is_file())
    report_paths = sorted(
        path
        for path in REPORT_ROOT.glob(f"{PREFIX}*")
        if path.is_file() and path != MANIFEST
    )
    script_paths = [
        ROOT / "scripts/build_geo_household_trades_lead.py",
        Path(__file__).resolve(),
    ]

    build_summary_path = REPORT_ROOT / f"{PREFIX}build-summary.json"
    build_summary = json.loads(build_summary_path.read_text())
    counts = build_summary["counts"]
    expected = {
        "annual_account7_parsed_rows": 10311,
        "annual_geo_trades": 14,
        "ptr_geo_trades": 1,
        "total_geo_trades": 15,
        "ptr_same_day_transaction_rows": 204,
        "in_window_action_rows": 155,
        "in_window_unique_action_dates": 112,
        "in_window_base_action_rows": 18,
        "matched_control_dates": 198,
        "all_weekdays": 293,
    }
    for key, value in expected.items():
        if counts.get(key) != value:
            raise SystemExit(f"Integrity failure: {key}={counts.get(key)!r}, expected {value!r}")

    input_paths = [Path(entry["path"]) for entry in build_summary["inputs"].values()]
    if any(path.is_absolute() or str(path).startswith("/tmp/") for path in input_paths):
        raise SystemExit("Integrity failure: build summary depends on an ephemeral or absolute input")
    if any(not (ROOT / path).is_file() for path in input_paths):
        raise SystemExit("Integrity failure: one or more durable build inputs are missing")

    ptr_texts = list((SOURCE_ROOT / "oge/ptr-texts").glob("*.txt"))
    if len(ptr_texts) != 17:
        raise SystemExit(f"Integrity failure: expected 17 PTR text extracts, found {len(ptr_texts)}")

    controls_path = REPORT_ROOT / f"{PREFIX}window-control-summary.csv"
    control_rows = list(csv.DictReader(controls_path.open(newline="")))
    lookup = {
        (row["event_class"], int(row["window_days_plus_minus"]), row["sample"]): (
            int(row["hits"]),
            int(row["sample_size"]),
        )
        for row in control_rows
    }
    control_expectations = {
        ("all_actions", 14, "trade_dates"): (15, 15),
        ("all_actions", 14, "matched_same_weekday_controls"): (198, 198),
        ("all_actions", 14, "all_weekdays"): (292, 293),
        ("base_actions", 14, "trade_dates"): (7, 15),
        ("base_actions", 14, "matched_same_weekday_controls"): (128, 198),
        ("base_actions", 14, "all_weekdays"): (186, 293),
    }
    for key, value in control_expectations.items():
        if lookup.get(key) != value:
            raise SystemExit(f"Integrity failure: control {key}={lookup.get(key)!r}, expected {value!r}")

    manifest = {
        "as_of": "2026-07-14",
        "profile": "geo-group",
        "lead_id": 59356,
        "thread_id": 111,
        "scope": "Public-record household-reportable GEO holdings/trades, ownership-control boundary, same-day portfolio cadence, and controlled comparison with DHS/GEO procurement actions.",
        "integrity": {
            "status": "pass",
            "source_files": len(source_paths),
            "ptr_text_extracts": len(ptr_texts),
            "durable_build_inputs": True,
            "expected_counts_verified": expected,
            "control_cells_verified": [
                {"key": list(key), "hits": value[0], "sample_size": value[1]}
                for key, value in control_expectations.items()
            ],
        },
        "database_result": {
            "prior_findings_checked": [12514, 12515, 12516, 12543],
            "new_verified_findings": [12948, 12957],
            "lead_id": 59356,
            "human_action_id": 69,
            "papercut_ids": [991, 995, 997],
            "hypotheses_reviewed_unscored": [351, 352],
        },
        "interpretive_boundaries": [
            "The disclosure identifies a public filer and covered household universe, not the beneficial owner or trade decision maker for each row.",
            "Family-member identities and account numbers are intentionally absent from the public form and were not reconstructed.",
            "Same-day portfolio cadence does not prove discretion, automation, routine motive, or absence of knowledge.",
            "Action-date proximity does not establish procurement initiation, evaluation, selection, notice, knowledge, trade instruction, or causation.",
            "Base actions, modifications, deobligations, closeouts, obligations, outlays, payments, GEO revenue, and trade profits are distinct concepts.",
            "No HigherGov API call or HigherGov source was used in this wave.",
        ],
        "negative_coverage": [
            "Seventeen official Trump PTRs were indexed and screened; one contained an exact GEO issuer hit.",
            "No public OGE record reviewed identified the covered owner, trade decision maker, adviser/broker discretion, account number, share count, cost basis, or instruction time.",
            "No reviewed public acquisition record supplied Delaney proposal, evaluation, selection, awardee-notice, or trade-instruction timestamps.",
            "Live SAM wrapper calls failed silently and are recorded as papercut #991; indexed official SAM pages and official USAspending fields were used instead.",
        ],
        "sources": [item(path) for path in source_paths],
        "generated_outputs": [item(path) for path in report_paths],
        "rebuild_scripts": [item(path) for path in script_paths],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {MANIFEST.relative_to(ROOT)} with {len(source_paths)} sources and {len(report_paths)} outputs")


if __name__ == "__main__":
    main()
