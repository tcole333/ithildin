#!/usr/bin/env python3
"""Build the bounded GEO CY2025 ICE revenue/contract reconciliation.

This builder deliberately keeps SEC revenue, federal obligations, award-level
outlay snapshots, local/public-prime cash records, and annualized contract
forecasts as different measures.  It will fail rather than silently coerce a
missing outlay to zero or allocate a mixed SEC revenue bundle to ICE.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "investigations/geo-group/sources/2026-07-14-lead-62481"
REPORT_DIR = ROOT / "investigations/geo-group/reports"
PREFIX = "2026-07-14-lead-62481-geo-cy2025-ice-revenue"

SEC_URLS = {
    "geo-2025-10k.clean.txt": (
        "https://www.sec.gov/Archives/edgar/data/923796/"
        "000119312526071747/geo-20251231.htm"
    ),
    "geo-2025-q1-10q.clean.txt": (
        "https://www.sec.gov/Archives/edgar/data/923796/"
        "000095017025065689/geo-20250331.htm"
    ),
    "geo-2025-q2-10q.clean.txt": (
        "https://www.sec.gov/Archives/edgar/data/923796/"
        "000095017025104173/geo-20250630.htm"
    ),
    "geo-2025-q3-10q.clean.txt": (
        "https://www.sec.gov/Archives/edgar/data/923796/"
        "000119312525269401/geo-20250930.htm"
    ),
    "geo-2026-q1-10q.clean.txt": (
        "https://www.sec.gov/Archives/edgar/data/923796/"
        "000119312526211821/geo-20260331.htm"
    ),
    "geo-2026-q1-results-ex99-1.txt": (
        "https://www.sec.gov/Archives/edgar/data/923796/"
        "000119312526207484/d122560dex991.htm"
    ),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_path(path: Path) -> str:
    """Use a stable repo-relative label when possible, otherwise an absolute path."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def decimal_text(value: Decimal) -> str:
    return f"{value:.2f}"


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, Path):
        return display_path(value)
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_value(item) for item in value]
    return value


def require_quote(source: Path, quote: str) -> None:
    haystack = normalize_ws(source.read_text(errors="replace"))
    needle = normalize_ws(quote)
    if needle not in haystack:
        raise RuntimeError(f"Quote not found in {source}: {quote}")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def build(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sec_dir = SOURCE_DIR / "sec"
    usa_dir = SOURCE_DIR / "usaspending"
    local_dir = SOURCE_DIR / "local"

    sec_sources = {name: sec_dir / name for name in SEC_URLS}
    for path in sec_sources.values():
        if not path.exists():
            raise FileNotFoundError(path)

    quote_rows = [
        {
            "id": "SEC-2025-CONSOLIDATED-REVENUE",
            "source": sec_sources["geo-2025-10k.clean.txt"],
            "url": SEC_URLS["geo-2025-10k.clean.txt"],
            "measure": "recognized revenue",
            "quote": "Revenues $ 2,631,549",
            "boundary": "Filed dollars are in thousands; consolidated, all customers.",
        },
        {
            "id": "SEC-2025-ICE-SHARE",
            "source": sec_sources["geo-2025-10k.clean.txt"],
            "url": SEC_URLS["geo-2025-10k.clean.txt"],
            "measure": "customer revenue share",
            "quote": (
                "ICE accounting for 47.6% and 41.5% of our total consolidated "
                "revenues for 2025 and 2024, respectively"
            ),
            "boundary": "Percentage is printed to one decimal; no exact ICE dollars are filed.",
        },
        {
            "id": "SEC-2025-ISAP-SHARE-NARRATIVE",
            "source": sec_sources["geo-2025-10k.clean.txt"],
            "url": SEC_URLS["geo-2025-10k.clean.txt"],
            "measure": "program revenue share",
            "quote": (
                "our ISAP contract accounted for 9%, 10% and 14% of our consolidated "
                "revenues for the years ended December 31, 2025, 2024 and 2023, respectively"
            ),
            "boundary": "Whole-percent narrative disclosure; point estimate, not exact dollars.",
        },
        {
            "id": "SEC-2025-ISAP-FOOTNOTE-BOUND",
            "source": sec_sources["geo-2025-10k.clean.txt"],
            "url": SEC_URLS["geo-2025-10k.clean.txt"],
            "measure": "program concentration bound",
            "quote": (
                "For the year ended December 31, 2025, the ISAP contract accounted "
                "for less than 10 % of the Company's consolidated revenues."
            ),
            "boundary": "Compatible with, but not exact corroboration of, the separate 9% narrative.",
        },
        {
            "id": "SEC-2025-REVENUE-INVOICE-TIMING",
            "source": sec_sources["geo-2025-10k.clean.txt"],
            "url": SEC_URLS["geo-2025-10k.clean.txt"],
            "measure": "accounting policy",
            "quote": (
                "The timing of revenue recognition may differ from the timing of invoicing "
                "to customers. GEO records a receivable when services are performed which "
                "are due from its customers based on the passage of time."
            ),
            "boundary": "Precludes an action-date or cash-to-revenue identity without service-period records.",
        },
        {
            "id": "SEC-2025-Q2-ACTIVATION",
            "source": sec_sources["geo-2025-q2-10q.clean.txt"],
            "url": SEC_URLS["geo-2025-q2-10q.clean.txt"],
            "measure": "recognized-revenue change bundle",
            "quote": (
                "increases of $17.5 million related to the activations of our new contracts "
                "at our company-owned Delaney Hall, North Lake and D. Ray James facilities"
            ),
            "boundary": "Quarter-over-prior-year change; not total facility revenue.",
        },
        {
            "id": "SEC-2025-H1-ACTIVATION",
            "source": sec_sources["geo-2025-q2-10q.clean.txt"],
            "url": SEC_URLS["geo-2025-q2-10q.clean.txt"],
            "measure": "recognized-revenue change bundle",
            "quote": (
                "aggregate net increases of $20.2 million related to the activations of our "
                "new contracts at our company-owned Delaney Hall, North Lake and D. Ray James facilities"
            ),
            "boundary": "Six-month cumulative change; Q1 residual is derived, not separately disclosed.",
        },
        {
            "id": "SEC-2025-Q3-ACTIVATION",
            "source": sec_sources["geo-2025-q3-10q.clean.txt"],
            "url": SEC_URLS["geo-2025-q3-10q.clean.txt"],
            "measure": "recognized-revenue change bundle",
            "quote": (
                "increases of $55.8 million related to the activations of our new contracts "
                "at our company-owned Delaney Hall, North Lake and D. Ray James facilities "
                "as well as our managed-only contract at the North Florida Detention Center"
            ),
            "boundary": "Quarter-over-prior-year change; mixed facility/payment channels.",
        },
        {
            "id": "SEC-2025-9M-ACTIVATION",
            "source": sec_sources["geo-2025-q3-10q.clean.txt"],
            "url": SEC_URLS["geo-2025-q3-10q.clean.txt"],
            "measure": "recognized-revenue change bundle",
            "quote": (
                "aggregate net increases of $76.0 million related to the activations of our "
                "new contracts at our company-owned Delaney Hall, North Lake and D. Ray James "
                "facilities as well as our managed-only contract at the North Florida Detention Center"
            ),
            "boundary": "Nine-month cumulative change; mixed facility/payment channels.",
        },
        {
            "id": "SEC-2025-CY-ACTIVATION",
            "source": sec_sources["geo-2025-10k.clean.txt"],
            "url": SEC_URLS["geo-2025-10k.clean.txt"],
            "measure": "recognized-revenue change bundle",
            "quote": (
                "aggregate net increases of $152.4 million related to the activations of our "
                "new contracts at our company-owned Delaney Hall, North Lake and D. Ray James "
                "facilities as well as our managed-only contract at the North Florida Detention "
                "Center and new transportation contracts"
            ),
            "boundary": "Annual mixed bundle; includes transportation and is not ICE-only.",
        },
        {
            "id": "SEC-2026-Q1-RETROSPECTIVE",
            "source": sec_sources["geo-2026-q1-10q.clean.txt"],
            "url": SEC_URLS["geo-2026-q1-10q.clean.txt"],
            "measure": "recognized-revenue change bundle",
            "quote": (
                "increases of $79.1 million related to the activations of our new contracts "
                "at our company-owned Delaney Hall, North Lake and D. Ray James facilities as "
                "well as our managed-only contract at the North Florida Detention Center and "
                "new transportation contracts"
            ),
            "boundary": "Q1 2026 versus Q1 2025; not CY2025 revenue.",
        },
        {
            "id": "SEC-2026-Q1-ANNUALIZED-FACILITY-FORECAST",
            "source": sec_sources["geo-2026-q1-results-ex99-1.txt"],
            "url": SEC_URLS["geo-2026-q1-results-ex99-1.txt"],
            "measure": "annualized contract forecast",
            "quote": "These facility activations represent annualized revenues of approximately $300 million.",
            "boundary": "Forecast/run-rate, not recognized CY2025 revenue.",
        },
        {
            "id": "SEC-2026-Q1-ANNUALIZED-TRANSPORT-FORECAST",
            "source": sec_sources["geo-2026-q1-results-ex99-1.txt"],
            "url": SEC_URLS["geo-2026-q1-results-ex99-1.txt"],
            "measure": "annualized contract forecast",
            "quote": (
                "Overall, these new and expanded transportation services contracts are valued "
                "at approximately $60 million in incremental annualized revenue."
            ),
            "boundary": "ICE and USMS combined; forecast/run-rate, not recognized CY2025 revenue.",
        },
    ]
    for row in quote_rows:
        require_quote(row["source"], row["quote"])

    consolidated = Decimal("2631549000")
    ice_pct = Decimal("0.476")
    ice_point = consolidated * ice_pct
    ice_low = consolidated * Decimal("0.4755")
    ice_high = consolidated * Decimal("0.4765")
    isap_point = consolidated * Decimal("0.09")
    isap_low = consolidated * Decimal("0.085")
    isap_high = consolidated * Decimal("0.095")

    quarters = [
        {
            "quarter": "2025-Q1",
            "total_revenue": Decimal("604647000"),
            "us_secure_services": Decimal("405716000"),
            "electronic_monitoring": Decimal("77713000"),
            "reentry": Decimal("70376000"),
            "international": Decimal("50842000"),
            "activation_bundle_change": Decimal("2700000"),
            "activation_value_status": "derived: H1 cumulative 20.2m minus Q2 17.5m",
        },
        {
            "quarter": "2025-Q2",
            "total_revenue": Decimal("636169000"),
            "us_secure_services": Decimal("441665000"),
            "electronic_monitoring": Decimal("78925000"),
            "reentry": Decimal("71310000"),
            "international": Decimal("44269000"),
            "activation_bundle_change": Decimal("17500000"),
            "activation_value_status": "filed quarter-over-prior-year change",
        },
        {
            "quarter": "2025-Q3",
            "total_revenue": Decimal("682341000"),
            "us_secure_services": Decimal("481628000"),
            "electronic_monitoring": Decimal("80538000"),
            "reentry": Decimal("72657000"),
            "international": Decimal("47518000"),
            "activation_bundle_change": Decimal("55800000"),
            "activation_value_status": "filed quarter-over-prior-year change",
        },
        {
            "quarter": "2025-Q4",
            "total_revenue": Decimal("708392000"),
            "us_secure_services": Decimal("497991000"),
            "electronic_monitoring": Decimal("83743000"),
            "reentry": Decimal("72178000"),
            "international": Decimal("54480000"),
            "activation_bundle_change": Decimal("76400000"),
            "activation_value_status": "derived: CY 152.4m minus 9M 76.0m",
        },
    ]
    for row in quarters:
        segment_sum = sum(
            row[key]
            for key in ("us_secure_services", "electronic_monitoring", "reentry", "international")
        )
        if segment_sum != row["total_revenue"]:
            raise RuntimeError(f"Quarter segment mismatch: {row['quarter']}")
    if sum(row["total_revenue"] for row in quarters) != consolidated:
        raise RuntimeError("Quarterly revenue does not reconcile to annual total")
    if sum(row["activation_bundle_change"] for row in quarters) != Decimal("152400000"):
        raise RuntimeError("Activation bundle does not reconcile to annual disclosure")

    action_source = usa_dir / "reconciled-dhs-wide-geo-award-actions.csv"
    with action_source.open(newline="", encoding="utf-8") as handle:
        action_rows = [
            row
            for row in csv.DictReader(handle)
            if row["component"] == "ICE" and row["action_date"].startswith("2025-")
        ]
    action_total = sum(Decimal(row["action_obligation"]) for row in action_rows)
    if len(action_rows) != 124 or action_total != Decimal("699338118.97"):
        raise RuntimeError(f"Unexpected action ledger: {len(action_rows)} / {action_total}")

    detail_source = usa_dir / "usaspending-task-award-details.json"
    details = json.loads(detail_source.read_text())["awards"]
    detail_by_piid = {row["piid"]: row for row in details}
    award_ids = sorted({row["award_id"] for row in action_rows})
    missing_details = [piid for piid in award_ids if piid not in detail_by_piid]
    if missing_details:
        raise RuntimeError(f"Missing award detail: {missing_details}")

    award_rows: list[dict[str, Any]] = []
    for piid in award_ids:
        detail = detail_by_piid[piid]
        award_actions = [row for row in action_rows if row["award_id"] == piid]
        outlay = detail.get("total_outlay")
        award_rows.append(
            {
                "award_id": piid,
                "generated_unique_award_id": detail["generated_unique_award_id"],
                "recipient_legal_name": detail["recipient"]["recipient_name"],
                "recipient_uei": detail["recipient"]["recipient_uei"],
                "cy2025_action_count": len(award_actions),
                "cy2025_action_obligations": decimal_text(
                    sum(Decimal(row["action_obligation"]) for row in award_actions)
                ),
                "current_award_total_obligation": decimal_text(
                    Decimal(str(detail.get("total_obligation") or 0))
                ),
                "current_award_total_outlay": (
                    "" if outlay is None else decimal_text(Decimal(str(outlay)))
                ),
                "outlay_status": "not reported" if outlay is None else "reported award-lifetime snapshot",
                "period_start": detail["period_of_performance"]["start_date"],
                "current_end": detail["period_of_performance"]["end_date"],
                "award_description": detail["description"],
                "source_url": (
                    "https://www.usaspending.gov/award/"
                    + detail["generated_unique_award_id"]
                ),
                "measure_boundary": (
                    "CY2025 action obligations are transaction flows; current award obligation "
                    "and outlay are award-lifetime snapshots and are not CY2025 revenue or cash."
                ),
            }
        )

    detail_records = [detail_by_piid[piid] for piid in award_ids]
    current_award_obligations = sum(
        Decimal(str(row.get("total_obligation") or 0)) for row in detail_records
    )
    reported_outlays = [row for row in detail_records if row.get("total_outlay") is not None]
    current_award_outlays = sum(Decimal(str(row["total_outlay"])) for row in reported_outlays)
    missing_outlay_piids = sorted(
        row["piid"] for row in detail_records if row.get("total_outlay") is None
    )
    if len(award_rows) != 34 or len(reported_outlays) != 32:
        raise RuntimeError("Unexpected award/outlay coverage")

    recipient_totals: dict[tuple[str, str], dict[str, Decimal | int]] = defaultdict(
        lambda: {"actions": 0, "obligations": Decimal("0")}
    )
    program_totals: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"actions": 0, "obligations": Decimal("0")}
    )
    for row in action_rows:
        recipient_key = (row["recipient_legal_name"], row["recipient_uei"])
        recipient_totals[recipient_key]["actions"] += 1
        recipient_totals[recipient_key]["obligations"] += Decimal(row["action_obligation"])
        program_totals[row["program_class"]]["actions"] += 1
        program_totals[row["program_class"]]["obligations"] += Decimal(
            row["action_obligation"]
        )

    context_ratio = action_total / ice_point * Decimal("100")
    context_ratio_low = action_total / ice_high * Decimal("100")
    context_ratio_high = action_total / ice_low * Decimal("100")
    point_gap = ice_point - action_total
    gap_low = ice_low - action_total
    gap_high = ice_high - action_total

    igsa = json.loads((local_dir / "ice-igsa-nine-facility-chain.json").read_text())
    joe_corley = json.loads(
        (local_dir / "joe-corley-payment-amendment-reconciliation.json").read_text()
    )
    north_florida = json.loads(
        (local_dir / "north-florida-reimbursement-trace.json").read_text()
    )

    filing_coverage = []
    filing_accessions = {
        "geo-2025-q1-10q.clean.txt": "0000950170-25-065689",
        "geo-2025-q2-10q.clean.txt": "0000950170-25-104173",
        "geo-2025-q3-10q.clean.txt": "0001193125-25-269401",
        "geo-2025-10k.clean.txt": "0001193125-26-071747",
        "geo-2026-q1-10q.clean.txt": "0001193125-26-211821",
        "geo-2026-q1-results-ex99-1.txt": "0001193125-26-207484",
    }
    coverage_terms = (
        "immigration and customs enforcement",
        "isap",
        "revenue",
        "invoice",
        "accounts receivable",
        "general ledger",
        "contract asset",
    )
    for filename, accession in filing_accessions.items():
        path = sec_dir / filename
        text = path.read_text(errors="replace")
        lower = text.lower()
        filing_coverage.append(
            {
                "accession": accession,
                "file": path,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "line_count": len(text.splitlines()),
                "term_counts": {term: lower.count(term) for term in coverage_terms},
                "processing_status": "full extracted text parsed; exact quotes validated where used",
            }
        )

    action_output = output_dir / f"{PREFIX}-action-ledger.csv"
    action_fields = list(action_rows[0].keys())
    write_csv(action_output, action_rows, action_fields)

    award_output = output_dir / f"{PREFIX}-award-snapshot-ledger.csv"
    award_fields = list(award_rows[0].keys())
    write_csv(award_output, award_rows, award_fields)

    quarter_output = output_dir / f"{PREFIX}-quarterly-ledger.csv"
    quarter_rows = [{key: json_value(value) for key, value in row.items()} for row in quarters]
    write_csv(quarter_output, quarter_rows, list(quarter_rows[0].keys()))

    evidence_output = output_dir / f"{PREFIX}-evidence-matrix.csv"
    evidence_rows = [
        {
            "evidence_id": row["id"],
            "measure": row["measure"],
            "source_path": display_path(row["source"]),
            "source_url": row["url"],
            "source_quote": row["quote"],
            "boundary": row["boundary"],
            "quote_validated": "true",
        }
        for row in quote_rows
    ]
    calculation_quotes = [
        {
            "evidence_id": "CALC-ICE-POINT-RANGE",
            "measure": "rounding-derived revenue estimate",
            "source_path": display_path(output_dir / f"{PREFIX}-reconciliation.json"),
            "source_url": "",
            "source_quote": (
                f"$2,631,549,000 x 47.6% = ${decimal_text(ice_point)}; ordinary nearest-tenth "
                f"rounding gives ${decimal_text(ice_low)} to <${decimal_text(ice_high)}."
            ),
            "boundary": "Point/range derived from a rounded filed percentage; not disclosed ICE dollars.",
            "quote_validated": "calculation",
        },
        {
            "evidence_id": "CALC-DIRECT-ACTIONS",
            "measure": "CY2025 federal action obligations",
            "source_path": display_path(action_output),
            "source_url": "https://www.usaspending.gov/",
            "source_quote": (
                f"124 CY2025 ICE action rows across 34 task/order PIIDs total "
                f"${decimal_text(action_total)} in action-date obligations."
            ),
            "boundary": "Obligations, not outlays, invoices, cash, or revenue.",
            "quote_validated": "calculation",
        },
        {
            "evidence_id": "CALC-AWARD-SNAPSHOTS",
            "measure": "award-lifetime obligation/outlay snapshots",
            "source_path": display_path(award_output),
            "source_url": "https://www.usaspending.gov/",
            "source_quote": (
                f"The 34 awards with CY2025 ICE actions show ${decimal_text(current_award_obligations)} "
                f"in current cumulative obligations and ${decimal_text(current_award_outlays)} in "
                f"current cumulative outlays across 32 awards; outlays are not reported for "
                f"{', '.join(missing_outlay_piids)}."
            ),
            "boundary": "Award-lifetime current snapshots; missing outlays are not zero.",
            "quote_validated": "calculation",
        },
        {
            "evidence_id": "CALC-NONATTRIBUTABLE-GAP",
            "measure": "different-metric arithmetic gap",
            "source_path": display_path(output_dir / f"{PREFIX}-reconciliation.json"),
            "source_url": "",
            "source_quote": (
                f"${decimal_text(ice_point)} revenue point estimate minus ${decimal_text(action_total)} "
                f"CY2025 action-date obligations equals ${decimal_text(point_gap)}; the mechanical "
                f"rounding range is ${decimal_text(gap_low)} to <${decimal_text(gap_high)}, and no "
                "part is attributed to IGSAs, pass-throughs, transport, invoices, or facilities."
            ),
            "boundary": "Not missing money, undercount, pass-through residual, or revenue allocation.",
            "quote_validated": "calculation",
        },
        {
            "evidence_id": "CALC-ACTIVATION-Q4",
            "measure": "recognized-revenue change bundle",
            "source_path": display_path(quarter_output),
            "source_url": "",
            "source_quote": (
                "$152.4 million CY activation/transport bundle minus $76.0 million nine-month "
                "bundle equals a $76.4 million Q4 change residual; the four quarterly bundle "
                "rows reconcile to $152.4 million."
            ),
            "boundary": "Mixed ICE/state/transport channels; not ICE-only or facility-level revenue.",
            "quote_validated": "calculation",
        },
    ]
    evidence_rows.extend(calculation_quotes)
    write_csv(evidence_output, evidence_rows, list(evidence_rows[0].keys()))

    reconciliation = {
        "profile": "geo-group",
        "lead_id": 62481,
        "as_of": "2026-07-14",
        "period_basis": "calendar year 2025 unless otherwise labeled",
        "currency": "USD",
        "sec_revenue": {
            "consolidated_revenue": consolidated,
            "ice_share_reported_pct": "47.6",
            "ice_revenue_point_estimate": ice_point,
            "ice_revenue_mechanical_rounding_interval": {
                "lower_inclusive": ice_low,
                "upper_exclusive": ice_high,
                "rule": "ordinary nearest-tenth percentage interval only",
            },
            "isap_share_reported_pct_narrative": "9",
            "isap_revenue_point_estimate": isap_point,
            "isap_mechanical_rounding_interval": {
                "lower_inclusive": isap_low,
                "upper_exclusive": isap_high,
                "rule": "ordinary nearest-whole percentage interval only",
            },
            "isap_footnote_bound": "less than 10%; compatible but not exact corroboration of 9%",
            "segments": {
                "us_secure_services": Decimal("1827000000"),
                "electronic_monitoring_and_supervision": Decimal("320919000"),
                "reentry": Decimal("286521000"),
                "international": Decimal("197109000"),
            },
            "major_sources": {
                "owned_and_leased_secure_services": Decimal("1388316000"),
                "managed_only_us_secure_services": Decimal("438684000"),
                "electronic_monitoring_and_supervision": Decimal("320919000"),
            },
            "quarterly_ledger_path": quarter_output,
            "customer_schedule_disclosed": False,
            "facility_schedule_disclosed": False,
            "invoice_or_general_ledger_schedule_disclosed": False,
        },
        "filing_coverage": filing_coverage,
        "direct_ice_actions": {
            "action_count": len(action_rows),
            "award_count": len(award_rows),
            "action_date_obligations": action_total,
            "recipients": [
                {
                    "legal_name": key[0],
                    "uei": key[1],
                    "action_count": value["actions"],
                    "obligations": value["obligations"],
                }
                for key, value in sorted(recipient_totals.items())
            ],
            "program_classes": [
                {
                    "program_class": key,
                    "action_count": value["actions"],
                    "obligations": value["obligations"],
                }
                for key, value in sorted(program_totals.items())
            ],
            "action_ledger_path": action_output,
        },
        "award_snapshot_boundary": {
            "award_count": len(award_rows),
            "current_cumulative_obligations_all_award_lives": current_award_obligations,
            "current_cumulative_outlays_reported_awards_only": current_award_outlays,
            "outlay_reported_award_count": len(reported_outlays),
            "outlay_not_reported_award_count": len(missing_outlay_piids),
            "outlay_not_reported_piids": missing_outlay_piids,
            "award_snapshot_ledger_path": award_output,
            "rule": "Do not interpret current award-lifetime snapshots as CY2025 measures; do not treat missing outlays as zero.",
        },
        "different_metric_comparison": {
            "direct_obligations_to_ice_point_pct": f"{context_ratio:.4f}",
            "direct_obligations_to_ice_rounding_range_pct": {
                "lower": f"{context_ratio_low:.4f}",
                "upper": f"{context_ratio_high:.4f}",
            },
            "ice_point_less_direct_actions": point_gap,
            "ice_rounding_range_less_direct_actions": {
                "lower_inclusive": gap_low,
                "upper_exclusive": gap_high,
            },
            "classification": (
                "Context ratio and arithmetic gap only; no portion is attributed to public-prime "
                "pass-throughs, IGSAs, prior-year obligations, invoices, accruals, cash, transport, "
                "or facilities."
            ),
        },
        "public_prime_channels": {
            "independent_ice_public_prime_geo_chains": igsa["denominator"][
                "independent_federal_local_geo_chains"
            ],
            "sec_ice_igsa_facility_rows": igsa["denominator"]["sec_ice_igsa_facility_rows"],
            "compatible_cy2025_downstream_geo_total_available": False,
            "joe_corley_current_ledger_available": False,
            "joe_corley_limitation": joe_corley["conclusions"]["fund_222_fy2025"],
            "north_florida_state_payments": north_florida["state_vendor_payments"]["total_usd"],
            "north_florida_boundary": (
                "State FY2025-26 payments dated in 2026 and FEMA award-wide outlays are not "
                "CY2025 GEO ICE revenue and are not joined in the public record."
            ),
        },
        "missing_records": [
            "GEO customer subledger assigning CY2025 recognized revenue to ICE contracts/facilities",
            "contract-level service-period invoices and accounts-receivable aging",
            "dated federal disbursements/outlays for the 34 awards",
            "funded IGSA task orders and public-prime receipt/remittance ledgers for all six chains",
            "current county/state-to-GEO vendor disbursement records and administrative fees",
            "GEO Transport and ICE-air subcontract invoices/revenue schedule",
            "BI ISAP and skip-tracing contract-level recognized-revenue schedule",
        ],
        "evidence_matrix_path": evidence_output,
    }

    reconciliation_output = output_dir / f"{PREFIX}-reconciliation.json"
    reconciliation_output.write_text(
        json.dumps(json_value(reconciliation), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    source_files = sorted(path for path in SOURCE_DIR.rglob("*") if path.is_file())
    output_files = [
        action_output,
        award_output,
        quarter_output,
        evidence_output,
        reconciliation_output,
    ]
    manifest = {
        "profile": "geo-group",
        "lead_id": 62481,
        "created": "2026-07-14",
        "method": "analyze-filing supplemented by analyze-contract",
        "measurement_rule": (
            "Recognized revenue, action-date obligations, cumulative award obligations, "
            "cumulative outlays, invoices, local remittances, cash, rates, ceilings, and "
            "annualized forecasts remain distinct."
        ),
        "sources": [
            {
                "path": display_path(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "url": SEC_URLS.get(path.name, ""),
            }
            for path in source_files
        ],
        "outputs": [
            {
                "path": display_path(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in output_files
        ],
        "validated_quote_ids": [row["id"] for row in quote_rows],
        "calculation_quote_ids": [row["evidence_id"] for row in calculation_quotes],
        "credentials_included": False,
    }
    manifest_output = output_dir / f"{PREFIX}-source-manifest.json"
    manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return {
        "action_ledger": action_output,
        "award_snapshot_ledger": award_output,
        "quarterly_ledger": quarter_output,
        "evidence_matrix": evidence_output,
        "reconciliation": reconciliation_output,
        "manifest": manifest_output,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args()
    outputs = build(args.output_dir.resolve())
    print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2))


if __name__ == "__main__":
    main()
