#!/usr/bin/env python3
"""Build the GEO FY2025-FY2026 DHS action-mechanism matrix.

The script starts from the canonical 14-UEI DHS action ledger, enriches every
FY2025/FY2026 row with USAspending's award-scoped transaction action type,
current task-award totals/outlays, and parent-IDV value snapshots, and writes a
transaction matrix plus calculation and provenance artifacts.

It deliberately keeps obligations, outlays, potential values, invoices, and
recognized revenue in separate fields.  Current award/IDV snapshots repeat on
transaction rows and must not be summed across those rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return round(float(value), 2)


def fiscal_year(action_date: str) -> int:
    year, month, _ = map(int, action_date.split("-"))
    return year + (1 if month >= 10 else 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generated_award_id(row: dict[str, str]) -> str:
    agency = "7014" if row["component"] == "CBP" else "7012"
    if row["parent_award_id"]:
        parent = f"{row['parent_award_id']}_{agency}"
    else:
        parent = "-NONE-_-NONE-"
    return f"CONT_AWD_{row['award_id']}_{agency}_{parent}"


def facility_or_service(row: dict[str, str]) -> str:
    award_id = row["award_id"]
    text = f"{row['action_description']} {row['award_description']}".upper()

    exact = {
        "70B03C20P00000219": "CBP RGV detention/jail space",
        "70B03C23P00000166": "CBP local jail-space purchase order",
        "70B03C24C00000054": "CBP RGV / La Villa detention space",
        "70B03C24P00000592": "CBP detention-space ratification",
        "70B03C25P00000029": "CBP Val Verde direct-to-county reroute",
        "70CDCR25FR0000075": "Emergency detention vehicle minimum",
        "70CDCR26FR0000002": "GEO Transport / Salt Lake City ground transportation",
        "70CDCR26FR0000021": "B.I. nationwide skip tracing",
    }
    if award_id in exact:
        return exact[award_id]
    if "INTENSIVE SUPERVISION APPEARANCE PROGRAM" in text:
        if "SKIP TRACING" in text:
            return "B.I. ISAP V skip tracing"
        if "ISAP V" in text or "ISAP) V" in text:
            return "B.I. ISAP V supervision/case management"
        return "B.I. ISAP IV supervision/case management"
    if "NORTH LAKE" in text:
        return "North Lake"
    if "AURORA" in text or "DENVER" in text:
        return "Aurora / Denver"
    if "DESERT VIEW" in text:
        return "Desert View / Adelanto annex"
    if "ADELANTO" in text:
        return "Adelanto"
    if "TACOMA" in text or "NORTHWEST" in text:
        return "Tacoma / Northwest"
    if "SOUTH TEXAS" in text or "STIPC" in text:
        return "South Texas"
    if any(term in text for term in ("MESA VERDE", "GOLDEN STATE", "CENTRAL VALLEY")):
        return "Mesa Verde / Golden State / Central Valley"
    if "MONTGOMERY" in text or "HOUSTON DETENTION" in text:
        return "Montgomery Processing Center"
    if "DELANEY" in text:
        return "Delaney Hall"
    if "BROWARD" in text:
        return "Broward Transitional Center"
    if "RIO GRANDE" in text:
        return "Rio Grande Detention Center"
    if "DEYTON" in text:
        return "Robert A. Deyton Detention Facility"
    raise ValueError(f"No facility/service classification for {award_id}: {text[:160]}")


def action_flags(row: dict[str, Any]) -> dict[str, Any]:
    amount = money(row["action_obligation"])
    action_type = row.get("action_type_code") or ""
    text = f"{row['action_description']} {row['award_description']}".upper()
    is_initial = not action_type and (
        row["modification_number"] in ("", "0", "-NONE-")
        or row["is_modification"] == "no"
    )
    is_option = action_type == "G"
    is_closeout = action_type == "K" or any(
        term in text for term in ("CLOSEOUT", "CLOSE OUT", "CLOSE THIS TASK", "CLOSES OUT")
    )
    is_deobligation = amount < 0 or "DE-OBLIGAT" in text or "DEOBLIGAT" in text
    is_term_extension = any(
        term in text for term in ("EXTEND THE TERM", "EXTEND THE PERIOD", "UPDATE THE PERIOD OF PERFORMANCE")
    )
    is_rate_adjustment = any(
        term in text
        for term in (
            "EQUITABLE ADJUSTMENT",
            "WAGE ADJUSTMENT",
            "WAGE DETERMINATION",
            "CHANGE IN DAILY RATE",
            "UPDATE RATES",
            "INCREASES RATES",
            "UPDATE THE RATE",
            "ADJUST THE GUARD",
            "PER DIEM RATES",
        )
    )
    is_capacity_scope = any(
        term in text
        for term in (
            "EMERGENCY BEDS",
            "OVERTIME BEDS",
            "EXPANSION",
            "MAXIMUM NUMBER OF BEDS",
            "ESTABLISH A DETENTION FACILITY",
            "TRANSITION, DETENTION",
            "CENTRAL VALLEY ANNEX",
            "DAILY OCCUPANCY",
            "MOBILIZATION",
        )
    )
    is_admin_or_correction = action_type == "M" or any(
        term in text for term in ("ADMIN MOD", "ADMINISTRATIVE", "CORRECTION", "UPDATE THE COR")
    )

    if is_closeout:
        mechanism = "closeout/deobligation"
    elif is_option:
        mechanism = "explicit option exercise"
    elif is_rate_adjustment:
        mechanism = "rate/wage/equitable adjustment"
    elif is_initial:
        mechanism = "new/base/successor task action"
    elif is_deobligation:
        mechanism = "deobligation without explicit closeout"
    elif action_type == "B":
        mechanism = "supplemental agreement within scope"
    elif action_type == "D":
        mechanism = "change order"
    elif is_capacity_scope:
        mechanism = "capacity/scope funding addition"
    elif action_type == "M":
        mechanism = "other administrative action"
    elif action_type == "C":
        mechanism = "funding-only action"
    else:
        mechanism = "other/unresolved action"

    if amount > 0:
        sign = "positive obligation"
    elif amount < 0:
        sign = "negative obligation/deobligation"
    else:
        sign = "zero-dollar action"

    month = int(row["action_date"][5:7])
    day = int(row["action_date"][8:10])
    if month == 9 and day >= 26:
        timing = "fiscal-year final five calendar days"
    elif month == 9:
        timing = "fiscal-year-end September"
    elif month in (10, 11, 12):
        timing = "fiscal-year first quarter"
    else:
        timing = "in-year"

    return {
        "primary_action_mechanism": mechanism,
        "amount_sign": sign,
        "is_new_or_base_task_action": int(is_initial),
        "is_explicit_option_exercise": int(is_option),
        "is_closeout": int(is_closeout),
        "is_deobligation": int(is_deobligation),
        "is_term_extension": int(is_term_extension),
        "is_rate_or_equitable_adjustment": int(is_rate_adjustment),
        "is_capacity_or_scope_change": int(is_capacity_scope),
        "is_administrative_or_correction": int(is_admin_or_correction),
        "fiscal_timing_class": timing,
    }


def grouped(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    return [
        {
            key: group,
            "action_count": len(items),
            "net_action_obligations": round(sum(money(r["action_obligation"]) for r in items), 2),
            "gross_positive_obligations": round(
                sum(max(money(r["action_obligation"]), 0) for r in items), 2
            ),
            "gross_deobligations": round(
                sum(min(money(r["action_obligation"]), 0) for r in items), 2
            ),
        }
        for group, items in sorted(
            groups.items(),
            key=lambda pair: sum(money(r["action_obligation"]) for r in pair[1]),
            reverse=True,
        )
    ]


def summarize_fy(rows: list[dict[str, Any]], fy: int) -> dict[str, Any]:
    subset = [row for row in rows if int(row["fiscal_year"]) == fy]
    net = round(sum(money(row["action_obligation"]) for row in subset), 2)
    positive = round(sum(max(money(row["action_obligation"]), 0) for row in subset), 2)
    negative = round(sum(min(money(row["action_obligation"]), 0) for row in subset), 2)
    september = [row for row in subset if row["action_date"][5:7] == "09"]
    last_five = [
        row
        for row in subset
        if row["action_date"][5:7] == "09" and int(row["action_date"][8:10]) >= 26
    ]
    funding_new = [
        row
        for row in subset
        if row["action_type_description"] == "FUNDING ONLY ACTION"
        or row["is_new_or_base_task_action"] == 1
    ]
    options = [row for row in subset if row["is_explicit_option_exercise"] == 1]
    ice_rows = [row for row in subset if row["component"] == "ICE"]
    ice_net = round(sum(money(row["action_obligation"]) for row in ice_rows), 2)
    ice_options = [row for row in ice_rows if row["is_explicit_option_exercise"] == 1]
    return {
        "fiscal_year": fy,
        "coverage_end": max(row["action_date"] for row in subset),
        "action_count": len(subset),
        "unique_awards": len({row["award_id"] for row in subset}),
        "net_action_obligations": net,
        "gross_positive_obligations": positive,
        "gross_deobligations": negative,
        "zero_dollar_actions": sum(money(row["action_obligation"]) == 0 for row in subset),
        "deobligations_as_pct_of_gross_positive": round(abs(negative) / positive * 100, 4),
        "september_net": round(sum(money(row["action_obligation"]) for row in september), 2),
        "september_share_of_net_pct": round(
            sum(money(row["action_obligation"]) for row in september) / net * 100, 4
        ),
        "final_five_days_net": round(sum(money(row["action_obligation"]) for row in last_five), 2),
        "final_five_days_share_of_net_pct": round(
            sum(money(row["action_obligation"]) for row in last_five) / net * 100, 4
        ),
        "funding_only_plus_new_task_net": round(
            sum(money(row["action_obligation"]) for row in funding_new), 2
        ),
        "funding_only_plus_new_task_share_of_net_pct": round(
            sum(money(row["action_obligation"]) for row in funding_new) / net * 100, 4
        ),
        "explicit_option_net": round(sum(money(row["action_obligation"]) for row in options), 2),
        "explicit_option_share_of_net_pct": round(
            sum(money(row["action_obligation"]) for row in options) / net * 100, 4
        ),
        "ice_net_action_obligations": ice_net,
        "ice_explicit_option_count": len(ice_options),
        "ice_explicit_option_net": round(
            sum(money(row["action_obligation"]) for row in ice_options), 2
        ),
        "ice_explicit_option_share_of_ice_net_pct": round(
            sum(money(row["action_obligation"]) for row in ice_options) / ice_net * 100,
            4,
        ),
        "by_component": grouped(subset, "component"),
        "by_transaction_action_type": grouped(subset, "action_type_description"),
        "by_primary_action_mechanism": grouped(subset, "primary_action_mechanism"),
        "by_facility_or_service": grouped(subset, "facility_or_service"),
        "by_month": grouped(subset, "action_month"),
    }


def build(args: argparse.Namespace) -> None:
    ledger_path = Path(args.ledger)
    transactions_path = Path(args.transactions)
    task_details_path = Path(args.task_details)
    parent_dir = Path(args.parent_idv_dir)

    with ledger_path.open(newline="") as handle:
        all_ledger_rows = list(csv.DictReader(handle))
    ledger_rows = [row for row in all_ledger_rows if fiscal_year(row["action_date"]) in (2025, 2026)]

    transaction_payload = json.loads(transactions_path.read_text())
    transaction_index: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for award in transaction_payload["awards"]:
        for transaction in award["transactions"]:
            key = (
                award["piid"],
                transaction["action_date"],
                str(transaction["modification_number"]),
                money(transaction.get("federal_action_obligation")),
            )
            transaction_index[key].append(transaction)

    task_payload = json.loads(task_details_path.read_text())
    task_by_generated_id = {
        award["generated_unique_award_id"]: award for award in task_payload["awards"]
    }
    parent_by_piid: dict[str, dict[str, Any]] = {}
    for path in sorted(parent_dir.glob("*.json")):
        detail = json.loads(path.read_text())
        parent_by_piid[detail["piid"]] = detail

    output_rows: list[dict[str, Any]] = []
    for source in ledger_rows:
        transaction_key = (
            source["award_id"],
            source["action_date"],
            str(source["modification_number"]),
            money(source["action_obligation"]),
        )
        matches = transaction_index.get(transaction_key, [])
        if len(matches) != 1:
            raise ValueError(f"Expected one transaction match for {transaction_key}; got {len(matches)}")
        transaction = matches[0]
        gid = generated_award_id(source)
        task = task_by_generated_id.get(gid)
        if task is None:
            raise ValueError(f"Missing task detail for {gid}")
        parent = parent_by_piid.get(source["parent_award_id"], {})
        task_pop = task.get("period_of_performance") or {}
        parent_pop = parent.get("period_of_performance") or {}

        row: dict[str, Any] = {
            "dedup_key_sha256": source["dedup_key_sha256"],
            "fiscal_year": fiscal_year(source["action_date"]),
            "action_month": source["action_date"][:7],
            "component": source["component"],
            "program_class": source["program_class"],
            "facility_or_service": facility_or_service(source),
            "action_date": source["action_date"],
            "award_id": source["award_id"],
            "parent_award_id": source["parent_award_id"],
            "instrument_type": source["instrument_type"],
            "modification_number": source["modification_number"],
            "is_modification": source["is_modification"],
            "recipient_legal_name": source["recipient_legal_name"],
            "recipient_uei": source["recipient_uei"],
            "action_obligation": f"{money(source['action_obligation']):.2f}",
            "action_type_code": transaction.get("action_type") or "",
            "action_type_description": transaction.get("action_type_description") or "NEW/INITIAL ACTION TYPE NOT POPULATED",
            "transaction_id": transaction.get("id") or "",
            "action_description": source["action_description"],
            "award_description": source["award_description"],
            "source_url": source["source_url"],
            "task_current_total_obligation": task.get("total_obligation"),
            "task_current_total_outlay": task.get("total_outlay"),
            "task_current_base_exercised_options": task.get("base_exercised_options"),
            "task_current_base_and_all_options_value": task.get("base_and_all_options"),
            "task_current_period_start": task_pop.get("start_date"),
            "task_current_period_end": task_pop.get("end_date"),
            "task_current_potential_end": task_pop.get("potential_end_date"),
            "parent_idv_current_total_obligation": parent.get("total_obligation"),
            "parent_idv_current_total_outlay": parent.get("total_outlay"),
            "parent_idv_current_base_exercised_options": parent.get("base_exercised_options"),
            "parent_idv_current_base_and_all_options_value": parent.get("base_and_all_options"),
            "parent_idv_current_period_start": parent_pop.get("start_date"),
            "parent_idv_current_period_end": parent_pop.get("end_date"),
            "parent_idv_current_potential_end": parent_pop.get("potential_end_date"),
            "invoice_record_in_sources": "not present",
            "recognized_revenue_record_in_sources": "not transaction-attributable",
            "metric_boundary": (
                "action_obligation is a transaction flow; task/IDV obligations, outlays, and values are "
                "current award snapshots repeated across rows; no invoice or transaction-attributable "
                "recognized-revenue record is present"
            ),
        }
        row.update(action_flags(row))
        output_rows.append(row)

    if len(output_rows) != 215:
        raise ValueError(f"Expected 215 FY2025/FY2026 rows; got {len(output_rows)}")
    if len({row["dedup_key_sha256"] for row in output_rows}) != 215:
        raise ValueError("Transaction matrix contains duplicate canonical rows")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    historical_fy = []
    for fy in sorted({fiscal_year(row["action_date"]) for row in all_ledger_rows}):
        rows = [row for row in all_ledger_rows if fiscal_year(row["action_date"]) == fy]
        historical_fy.append(
            {
                "fiscal_year": fy,
                "action_count": len(rows),
                "net_action_obligations": round(sum(money(row["action_obligation"]) for row in rows), 2),
            }
        )

    fy2025_same_elapsed = [
        row for row in output_rows if "2024-10-01" <= row["action_date"] <= "2025-07-09"
    ]
    fy2026_same_elapsed = [
        row for row in output_rows if "2025-10-01" <= row["action_date"] <= "2026-07-09"
    ]
    fy25_same = round(sum(money(row["action_obligation"]) for row in fy2025_same_elapsed), 2)
    fy26_same = round(sum(money(row["action_obligation"]) for row in fy2026_same_elapsed), 2)
    same_elapsed_facilities = []
    facility_names = sorted(
        {row["facility_or_service"] for row in fy2025_same_elapsed + fy2026_same_elapsed}
    )
    total_same_elapsed_difference = round(fy26_same - fy25_same, 2)
    for facility in facility_names:
        fy25_value = round(
            sum(
                money(row["action_obligation"])
                for row in fy2025_same_elapsed
                if row["facility_or_service"] == facility
            ),
            2,
        )
        fy26_value = round(
            sum(
                money(row["action_obligation"])
                for row in fy2026_same_elapsed
                if row["facility_or_service"] == facility
            ),
            2,
        )
        difference = round(fy26_value - fy25_value, 2)
        same_elapsed_facilities.append(
            {
                "facility_or_service": facility,
                "fy2025_same_elapsed_net": fy25_value,
                "fy2026_same_elapsed_net": fy26_value,
                "difference": difference,
                "share_of_total_difference_pct": round(
                    difference / total_same_elapsed_difference * 100, 4
                ),
            }
        )
    same_elapsed_facilities.sort(key=lambda row: row["difference"], reverse=True)

    january_spike = [
        row for row in output_rows if "2026-01-21" <= row["action_date"] <= "2026-01-28"
    ]
    calculations = {
        "as_of": "2026-07-14",
        "lead_id": 57842,
        "matrix_rows": len(output_rows),
        "historical_fiscal_year_net_actions": historical_fy,
        "same_elapsed_fiscal_comparison": {
            "fy2025_window": "2024-10-01 through 2025-07-09",
            "fy2025_net_action_obligations": fy25_same,
            "fy2026_window": "2025-10-01 through 2026-07-09",
            "fy2026_net_action_obligations": fy26_same,
            "difference": round(fy26_same - fy25_same, 2),
            "change_pct": round((fy26_same / fy25_same - 1) * 100, 4),
            "by_facility_or_service": same_elapsed_facilities,
            "fy2025_by_transaction_action_type": grouped(
                fy2025_same_elapsed, "action_type_description"
            ),
            "fy2026_by_transaction_action_type": grouped(
                fy2026_same_elapsed, "action_type_description"
            ),
        },
        "fy2026_january_21_28_cluster": {
            "action_count": len(january_spike),
            "net_action_obligations": round(
                sum(money(row["action_obligation"]) for row in january_spike), 2
            ),
            "share_of_fy2026_ytd_net_pct": round(
                sum(money(row["action_obligation"]) for row in january_spike)
                / sum(
                    money(row["action_obligation"])
                    for row in output_rows
                    if int(row["fiscal_year"]) == 2026
                )
                * 100,
                4,
            ),
            "actions": [
                {
                    key: row[key]
                    for key in (
                        "action_date",
                        "facility_or_service",
                        "award_id",
                        "modification_number",
                        "action_obligation",
                        "action_type_description",
                        "primary_action_mechanism",
                        "action_description",
                    )
                }
                for row in sorted(
                    january_spike,
                    key=lambda row: money(row["action_obligation"]),
                    reverse=True,
                )
            ],
        },
        "fiscal_years": [summarize_fy(output_rows, 2025), summarize_fy(output_rows, 2026)],
        "explicit_option_actions": [
            {
                key: row[key]
                for key in (
                    "fiscal_year",
                    "action_date",
                    "facility_or_service",
                    "award_id",
                    "modification_number",
                    "action_obligation",
                    "action_description",
                )
            }
            for row in output_rows
            if row["is_explicit_option_exercise"] == 1
        ],
        "largest_positive_actions": [
            {
                key: row[key]
                for key in (
                    "fiscal_year",
                    "action_date",
                    "facility_or_service",
                    "award_id",
                    "modification_number",
                    "action_obligation",
                    "action_type_description",
                    "primary_action_mechanism",
                    "action_description",
                )
            }
            for row in sorted(output_rows, key=lambda r: money(r["action_obligation"]), reverse=True)[:30]
        ],
        "largest_negative_actions": [
            {
                key: row[key]
                for key in (
                    "fiscal_year",
                    "action_date",
                    "facility_or_service",
                    "award_id",
                    "modification_number",
                    "action_obligation",
                    "action_type_description",
                    "primary_action_mechanism",
                    "action_description",
                )
            }
            for row in sorted(output_rows, key=lambda r: money(r["action_obligation"]))[:20]
        ],
    }
    Path(args.calculations).write_text(json.dumps(calculations, indent=2) + "\n")

    action_types = Counter(
        (row["action_type_code"], row["action_type_description"]) for row in output_rows
    )
    parent_snapshots = []
    for piid, parent in sorted(parent_by_piid.items()):
        pop = parent.get("period_of_performance") or {}
        parent_snapshots.append(
            {
                "piid": piid,
                "description": parent.get("description"),
                "current_total_obligation": parent.get("total_obligation"),
                "current_total_outlay": parent.get("total_outlay"),
                "current_base_exercised_options": parent.get("base_exercised_options"),
                "current_base_and_all_options_value": parent.get("base_and_all_options"),
                "period_start": pop.get("start_date"),
                "period_end": pop.get("end_date"),
                "potential_end": pop.get("potential_end_date"),
                "boundary": "parent IDV snapshot; not a task obligation, invoice, payment, or revenue figure",
            }
        )

    manifest = {
        "as_of": "2026-07-14",
        "profile": "geo-group",
        "lead_id": 57842,
        "scope": "FY2025 and FY2026-through-2026-07-09 actions from the canonical 14-UEI DHS ledger",
        "sources": [
            {
                "id": "canonical-14-uei-dhs-ledger",
                "path": str(ledger_path),
                "sha256": sha256(ledger_path),
                "source_type": "official USAspending API-derived local artifact",
                "rows_all_periods": len(all_ledger_rows),
                "rows_in_scope": len(ledger_rows),
            },
            {
                "id": "usaspending-award-transactions",
                "path": str(transactions_path),
                "endpoint": "https://api.usaspending.gov/api/v2/transactions/",
                "official_documentation": "https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/transactions.md",
                "sha256_of_raw_batch": sha256(transactions_path),
                "award_queries": transaction_payload["query_count"],
                "raw_transaction_rows": sum(
                    len(award["transactions"]) for award in transaction_payload["awards"]
                ),
                "exact_rows_joined": len(output_rows),
                "request_method": "POST",
                "request_body_per_award": {
                    "award_id": "{generated_award_id}",
                    "page": 1,
                    "sort": "action_date",
                    "order": "asc",
                    "limit": 5000,
                },
                "generated_award_ids": sorted(
                    award["generated_award_id"] for award in transaction_payload["awards"]
                ),
            },
            {
                "id": "usaspending-task-award-details",
                "path": str(task_details_path),
                "endpoint": "https://api.usaspending.gov/api/v2/awards/{generated_award_id}/",
                "sha256_of_raw_batch": sha256(task_details_path),
                "award_snapshots": len(task_payload["awards"]),
                "request_method": "GET",
                "generated_award_ids": sorted(task_by_generated_id),
                "boundary": "current award-level totals/outlays; not transaction-period outlays",
            },
            {
                "id": "usaspending-parent-idv-details",
                "path": str(parent_dir),
                "endpoint": "https://api.usaspending.gov/api/v2/awards/{generated_parent_idv}/",
                "parent_idv_snapshots": len(parent_by_piid),
                "request_method": "GET",
                "generated_parent_idv_ids": sorted(
                    parent["generated_unique_award_id"] for parent in parent_by_piid.values()
                ),
                "boundary": "current parent value/period snapshots; parent value is not task obligation",
            },
            {
                "id": "geo-2025-form-10-k-revenue-boundary",
                "url": "https://www.sec.gov/Archives/edgar/data/923796/000119312526071747/geo-20251231.htm",
                "reused_artifact": "investigations/geo-group/reports/2026-07-14-lead-57844-geo-ice-revenue-source-manifest.json",
                "exact_quote": "The timing of revenue recognition may differ from the timing of invoicing to customers.",
                "boundary": "recognized revenue is not transaction-attributable in the procurement records",
            },
        ],
        "join_audit": {
            "canonical_rows": len(ledger_rows),
            "exact_matches": len(output_rows),
            "unmatched": 0,
            "ambiguous": 0,
            "join_key": ["PIID", "action date", "modification number", "action obligation rounded to cents"],
            "unique_canonical_hashes": len({row["dedup_key_sha256"] for row in output_rows}),
        },
        "action_type_counts": [
            {
                "code": code or None,
                "description": description,
                "row_count": count,
            }
            for (code, description), count in sorted(
                action_types.items(), key=lambda item: (-item[1], item[0][0])
            )
        ],
        "classification": {
            "facility_method": "exact award overrides plus literal facility/program terms in official descriptions",
            "action_method": "official action type controls; descriptive flags use literal modification text",
            "initial_action_rule": "missing action type plus modification 0/non-modification is classified as new/base/successor task action",
            "causal_rule": "timing and action labels establish procurement mechanics, not political causation or service-period revenue",
        },
        "metric_boundaries": {
            "action_obligation": "transaction-date legal commitment or deobligation",
            "parent_idv_value": "potential authority at the parent vehicle; not a task obligation",
            "task_obligation": "current cumulative award stock; not an invoice or payment",
            "task_outlay": "current cumulative award cash-disbursement snapshot; not a transaction-period outlay",
            "invoice": "not present in these sources",
            "recognized_revenue": "SEC accounting recognition; not joined to a federal transaction",
        },
        "sam_crosscheck": {
            "attempted": True,
            "result": "HTTP 429 documented daily rate limit",
            "used_as_evidence": False,
        },
        "parent_idv_snapshots": parent_snapshots,
        "outputs": {
            "matrix": str(output_path),
            "matrix_sha256": sha256(output_path),
            "calculations": str(args.calculations),
        },
        "rebuild": {
            "command": (
                "uv run python scripts/build_geo_fy25_fy26_action_matrix.py "
                "--ledger investigations/geo-group/reports/2026-07-13-dhs-wide-geo-award-actions.csv "
                "--transactions investigations/geo-group/sources/2026-07-14-lead-57842/"
                "usaspending-award-transactions-action-types.json "
                "--task-details investigations/geo-group/sources/2026-07-14-lead-57842/"
                "usaspending-task-award-details.json "
                "--parent-idv-dir investigations/geo-group/sources/2026-07-14-lead-57842/parent-idvs "
                "--output investigations/geo-group/reports/2026-07-14-lead-57842-geo-fy25-fy26-action-matrix.csv "
                "--calculations investigations/geo-group/reports/2026-07-14-lead-57842-geo-fy25-fy26-action-calculations.json "
                "--manifest investigations/geo-group/reports/2026-07-14-lead-57842-geo-fy25-fy26-source-manifest.json"
            ),
            "network_required": False,
            "note": "Durable raw snapshots are the controlling inputs. Re-fetching would update current award/outlay/value snapshots and must be treated as a new as-of run.",
        },
    }
    Path(args.manifest).write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--transactions", required=True)
    parser.add_argument("--task-details", required=True)
    parser.add_argument("--parent-idv-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--calculations", required=True)
    parser.add_argument("--manifest", required=True)
    build(parser.parse_args())


if __name__ == "__main__":
    main()
