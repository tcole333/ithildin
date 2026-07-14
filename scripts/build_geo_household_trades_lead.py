#!/usr/bin/env python3
"""Build the public-record GEO household-trade and DHS-action control ledger.

This script deliberately keeps disclosure, ownership, trade, and procurement
fields separate.  It does not attribute a covered household transaction to a
named individual and it does not treat timing proximity as evidence of
knowledge or causation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path


WINDOWS = (1, 3, 7, 14, 30)
OBSERVATION_START = date(2025, 1, 20)
PTR_TRADE_DATE = date(2026, 3, 4)
ACTION_BUFFER_END = PTR_TRADE_DATE + timedelta(days=max(WINDOWS))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annual-text", type=Path, required=True)
    parser.add_argument("--ptr-text", type=Path, required=True)
    parser.add_argument("--actions-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_annual_account7(path: Path) -> tuple[list[dict], list[dict]]:
    lines = path.read_text(errors="replace").splitlines()
    account7_starts = [
        index
        for index, line in enumerate(lines)
        if index > 30_000 and "INVESTMENT ACCOUNT #7" in line
    ]
    if not account7_starts:
        raise ValueError("Investment Account #7 transaction section not found")
    start = account7_starts[0]
    end = next(
        index
        for index, line in enumerate(lines[start + 1 :], start + 1)
        if "INVESTMENT ACCOUNT #8" in line
    )
    row_pattern = re.compile(
        r"^\s*(?P<row>\d+)\s{2,}(?P<security>.+?)\s{2,}"
        r"(?P<type>Purchase|sale)\s+(?P<date>\d{1,2}/\d{1,2}/2025)\s+"
        r"(?P<amount>\$[\d,]+\s+-\s+\$[\d,]+)\s*$",
        re.IGNORECASE,
    )
    account_rows: list[dict] = []
    for line_number, raw in enumerate(lines[start:end], start + 1):
        match = row_pattern.match(raw)
        if not match:
            continue
        parsed = match.groupdict()
        parsed["line_number"] = line_number
        parsed["raw"] = raw.strip()
        parsed["date_iso"] = datetime.strptime(parsed["date"], "%m/%d/%Y").date().isoformat()
        parsed["type"] = parsed["type"].title()
        account_rows.append(parsed)

    geo_rows = [row for row in account_rows if row["security"].strip() == "GEO GROUP INC NEW"]
    if len(geo_rows) != 14:
        raise ValueError(f"Expected 14 annual GEO rows; parsed {len(geo_rows)}")
    if len(account_rows) < 10_000:
        raise ValueError(f"Account #7 parse unexpectedly sparse: {len(account_rows)} rows")
    return account_rows, geo_rows


def parse_ptr_context(path: Path) -> tuple[int, str, int]:
    lines = path.read_text(errors="replace").splitlines()
    accepted_ocr_tokens = ("3/4/2026", "3/412026", "314/2026", "3/4/2028")
    same_day_lines = [
        (index, raw)
        for index, raw in enumerate(lines, 1)
        if re.match(r"^\s*\d{1,4}[ .•]+\S", raw)
        and any(token in raw for token in accepted_ocr_tokens)
    ]
    geo_lines = [item for item in same_day_lines if "GEO GROUP INC NEW REIT" in item[1]]
    if len(geo_lines) != 1:
        raise ValueError(f"Expected one PTR GEO row; parsed {len(geo_lines)}")
    return len(same_day_lines), geo_lines[0][1].strip(), geo_lines[0][0]


def read_actions(path: Path) -> list[dict]:
    actions: list[dict] = []
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            action_date = parse_date(row["action_date"])
            # Keep a forward buffer so the last trade and late-period controls
            # receive the same symmetric +30-day event window as earlier dates.
            if OBSERVATION_START <= action_date <= ACTION_BUFFER_END:
                row["action_date_obj"] = action_date
                row["action_obligation_float"] = float(row["action_obligation"] or 0)
                actions.append(row)
    if not actions:
        raise ValueError("No in-window DHS action rows")
    return actions


def in_window(target: date, event_dates: set[date], days: int) -> bool:
    return any(abs((event - target).days) <= days for event in event_dates)


def nearest_action(target: date, actions: list[dict]) -> dict:
    return min(
        actions,
        key=lambda row: (
            abs((row["action_date_obj"] - target).days),
            row["action_date_obj"],
            -abs(row["action_obligation_float"]),
            row["dedup_key_sha256"],
        ),
    )


def same_weekday_controls(trade_dates: list[date]) -> list[dict]:
    trade_set = set(trade_dates)
    controls: list[dict] = []
    for trade_date in trade_dates:
        for weeks in range(1, 9):
            for direction in (-1, 1):
                candidate = trade_date + timedelta(days=7 * weeks * direction)
                if OBSERVATION_START <= candidate <= PTR_TRADE_DATE and candidate not in trade_set:
                    controls.append(
                        {
                            "source_trade_date": trade_date,
                            "control_date": candidate,
                            "offset_weeks": weeks,
                            "direction": direction,
                        }
                    )
    return sorted(
        controls,
        key=lambda row: (
            row["source_trade_date"],
            row["control_date"],
            row["offset_weeks"],
            row["direction"],
        ),
    )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    account_rows, annual_geo_rows = parse_annual_account7(args.annual_text)
    ptr_same_day_count, ptr_geo_raw, ptr_geo_line = parse_ptr_context(args.ptr_text)
    actions = read_actions(args.actions_csv)
    base_actions = [row for row in actions if row["is_modification"].lower() == "no"]
    if not base_actions:
        raise ValueError("No base actions in observation window")

    same_day = Counter(row["date_iso"] for row in account_rows)
    same_day_type = Counter((row["date_iso"], row["type"]) for row in account_rows)
    trades: list[dict] = []
    for row in annual_geo_rows:
        trades.append(
            {
                "trade_date": row["date_iso"],
                "disclosure_form": "OGE Form 278e annual report filed 2026-06-29",
                "public_filer": "Donald J. Trump",
                "covered_owner_publicly_identified": "no",
                "trade_decision_maker_publicly_identified": "no",
                "account_label": "Investment Account #7",
                "security": "GEO GROUP INC NEW",
                "security_class": "public-company stock",
                "transaction_type": row["type"],
                "value_range": row["amount"],
                "notification_over_30_days": "not a field on annual Part 7",
                "same_day_account7_rows": same_day[row["date_iso"]],
                "same_day_account7_purchases": same_day_type[(row["date_iso"], "Purchase")],
                "same_day_account7_sales": same_day_type[(row["date_iso"], "Sale")],
                "source_line": row["line_number"],
                "source_row_raw": row["raw"],
            }
        )
    trades.append(
        {
            "trade_date": PTR_TRADE_DATE.isoformat(),
            "disclosure_form": "OGE Form 278-T received 2026-05-08",
            "public_filer": "Donald J. Trump",
            "covered_owner_publicly_identified": "no",
            "trade_decision_maker_publicly_identified": "no",
            "account_label": "not shown on PTR row",
            "security": "GEO GROUP INC NEW REIT",
            "security_class": "public-company stock / issuer label includes REIT",
            "transaction_type": "Purchase",
            "value_range": "$15,001 - $50,000",
            "notification_over_30_days": "Yes",
            "same_day_account7_rows": ptr_same_day_count,
            "same_day_account7_purchases": "not reliably classified from OCR",
            "same_day_account7_sales": "not reliably classified from OCR",
            "source_line": ptr_geo_line,
            "source_row_raw": ptr_geo_raw,
        }
    )
    trades.sort(key=lambda row: row["trade_date"])

    for trade in trades:
        trade_date = parse_date(trade["trade_date"])
        nearest = nearest_action(trade_date, actions)
        nearest_base = nearest_action(trade_date, base_actions)
        for prefix, selected in (("nearest_action", nearest), ("nearest_base", nearest_base)):
            trade[f"{prefix}_date"] = selected["action_date"]
            trade[f"{prefix}_day_offset"] = (selected["action_date_obj"] - trade_date).days
            trade[f"{prefix}_award_id"] = selected["award_id"]
            trade[f"{prefix}_parent_award_id"] = selected["parent_award_id"]
            trade[f"{prefix}_modification"] = selected["modification_number"]
            trade[f"{prefix}_obligation"] = f'{selected["action_obligation_float"]:.2f}'
            trade[f"{prefix}_description"] = selected["action_description"]
            trade[f"{prefix}_source_url"] = selected["source_url"]
        for window in WINDOWS:
            selected_actions = [
                action
                for action in actions
                if abs((action["action_date_obj"] - trade_date).days) <= window
            ]
            selected_bases = [
                action
                for action in base_actions
                if abs((action["action_date_obj"] - trade_date).days) <= window
            ]
            trade[f"actions_within_{window}d"] = len(selected_actions)
            trade[f"action_obligations_net_within_{window}d"] = f'{sum(row["action_obligation_float"] for row in selected_actions):.2f}'
            trade[f"bases_within_{window}d"] = len(selected_bases)
            trade[f"base_obligations_net_within_{window}d"] = f'{sum(row["action_obligation_float"] for row in selected_bases):.2f}'

    trade_dates = [parse_date(row["trade_date"]) for row in trades]
    matched_control_records = same_weekday_controls(trade_dates)
    controls = [row["control_date"] for row in matched_control_records]
    all_dates = [
        OBSERVATION_START + timedelta(days=offset)
        for offset in range((PTR_TRADE_DATE - OBSERVATION_START).days + 1)
    ]
    weekdays = [item for item in all_dates if item.weekday() < 5]
    action_dates = {row["action_date_obj"] for row in actions}
    base_dates = {row["action_date_obj"] for row in base_actions}

    control_rows = []
    for match in matched_control_records:
        control = match["control_date"]
        row: dict[str, str | int] = {
            "source_trade_date": match["source_trade_date"].isoformat(),
            "control_date": control.isoformat(),
            "offset_weeks": match["offset_weeks"],
            "direction": "before" if match["direction"] < 0 else "after",
            "weekday": control.strftime("%A"),
        }
        for window in WINDOWS:
            row[f"any_action_within_{window}d"] = int(in_window(control, action_dates, window))
            row[f"any_base_within_{window}d"] = int(in_window(control, base_dates, window))
        control_rows.append(row)

    window_rows = []
    for window in WINDOWS:
        for event_class, dates in (("all_actions", action_dates), ("base_actions", base_dates)):
            for sample_name, sample_dates in (
                ("trade_dates", trade_dates),
                ("matched_same_weekday_controls", controls),
                ("all_weekdays", weekdays),
                ("all_calendar_dates", all_dates),
            ):
                hits = sum(in_window(sample, dates, window) for sample in sample_dates)
                window_rows.append(
                    {
                        "event_class": event_class,
                        "window_days_plus_minus": window,
                        "sample": sample_name,
                        "hits": hits,
                        "sample_size": len(sample_dates),
                        "share": f"{hits / len(sample_dates):.8f}",
                    }
                )

    trade_fields = list(trades[0].keys())
    write_csv(args.output_dir / "trade-to-action-ledger.csv", trades, trade_fields)
    control_fields = list(control_rows[0].keys())
    write_csv(args.output_dir / "matched-same-weekday-controls.csv", control_rows, control_fields)
    write_csv(
        args.output_dir / "window-control-summary.csv",
        window_rows,
        ["event_class", "window_days_plus_minus", "sample", "hits", "sample_size", "share"],
    )

    summary = {
        "method": {
            "observation_start": OBSERVATION_START.isoformat(),
            "observation_end": PTR_TRADE_DATE.isoformat(),
            "action_event_buffer_end": ACTION_BUFFER_END.isoformat(),
            "windows_days_plus_minus": WINDOWS,
            "base_definition": "canonical DHS ledger row where is_modification == no",
            "matched_controls": "same weekdays at +/- 1 through 8 weeks from each trade date, excluding trade dates and dates outside the observation interval; a calendar date matched to multiple trades remains a separate matched observation",
            "causal_boundary": "Timing proximity is not evidence of trade knowledge, direction, motive, or procurement causation.",
            "edge_boundary": "The post-inauguration action universe begins 2025-01-20; the earliest trade is fully observed at +/-7 days but its +/-14 and +/-30 windows do not include pre-inauguration actions.",
        },
        "inputs": {
            "annual_text": {"path": str(args.annual_text), "sha256": sha256(args.annual_text)},
            "ptr_text": {"path": str(args.ptr_text), "sha256": sha256(args.ptr_text)},
            "actions_csv": {"path": str(args.actions_csv), "sha256": sha256(args.actions_csv)},
        },
        "counts": {
            "annual_account7_parsed_rows": len(account_rows),
            "annual_geo_trades": len(annual_geo_rows),
            "ptr_geo_trades": 1,
            "total_geo_trades": len(trades),
            "ptr_same_day_transaction_rows": ptr_same_day_count,
            "in_window_action_rows": len(actions),
            "in_window_unique_action_dates": len(action_dates),
            "in_window_base_action_rows": len(base_actions),
            "in_window_unique_base_dates": len(base_dates),
            "matched_control_dates": len(controls),
            "all_calendar_dates": len(all_dates),
            "all_weekdays": len(weekdays),
        },
        "annual_geo_same_day_account7_counts": {
            row["trade_date"]: {
                "rows": row["same_day_account7_rows"],
                "purchases": row["same_day_account7_purchases"],
                "sales": row["same_day_account7_sales"],
            }
            for row in trades
            if row["trade_date"] != PTR_TRADE_DATE.isoformat()
        },
        "outputs": [
            "trade-to-action-ledger.csv",
            "matched-same-weekday-controls.csv",
            "window-control-summary.csv",
        ],
    }
    (args.output_dir / "build-summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    build()
