#!/usr/bin/env python3
"""Build durable artifacts for GEO lead 60206 from archived primary records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11"
REPORTS = ROOT / "investigations/geo-group/reports"
PREFIX = REPORTS / "2026-07-14-lead-60206-western-cdf-economics-wave11"


FACILITY_SPECS = [
    {
        "facility": "Aurora / Denver Contract Detention Facility",
        "source_label": "DENVER CONTRACT DETENTION FACILITY",
        "period": "ICE FY25-to-2025-09-15",
        "data_as_of": "2025-09-15",
        "source_cell": "Facilities FY25!A62:Z62",
        "levels": ["553.234957020057", "226.742120343839", "238.429799426934", "162.541547277937"],
        "guarantee": "600",
        "task": "70CDCR25FR0000005",
        "parent": "70CDCR22D00000001",
        "source_file": "FY25_detentionStats.xlsx",
    },
    {
        "facility": "Adelanto ICE Processing Center",
        "source_label": "ADELANTO ICE PROCESSING CENTER",
        "period": "ICE FY25-to-2025-09-15",
        "data_as_of": "2025-09-15",
        "source_cell": "Facilities FY25!A94:Z94",
        "levels": ["174.939828080229", "58.836676217765", "159.014326647564", "182.753581661891"],
        "guarantee": "640",
        "task": "70CDCR25FR0000009",
        "parent": "70CDCR20D00000009",
        "source_file": "FY25_detentionStats.xlsx",
    },
    {
        "facility": "Desert View Annex",
        "source_label": "DESERT VIEW ANNEX",
        "period": "ICE FY25-to-2025-09-15",
        "data_as_of": "2025-09-15",
        "source_cell": "Facilities FY25!A95:Z95",
        "levels": ["254.991404011462", "49.1174785100287", "55.5329512893982", "63.6618911174785"],
        "guarantee": "480",
        "task": "70CDCR25FR0000010",
        "parent": "70CDCR20D00000009",
        "source_file": "FY25_detentionStats.xlsx",
    },
    {
        "facility": "Tacoma / Northwest ICE Processing Center",
        "source_label": "NORTHWEST ICE PROCESSSING CENTER",
        "period": "ICE FY25-to-2025-09-15",
        "data_as_of": "2025-09-15",
        "source_cell": "Facilities FY25!A146:Z146",
        "levels": ["596.985673352435", "134.085959885387", "234.936962750716", "213.607449856733"],
        "guarantee": "1181",
        "task": "70CDCR25FR0000004",
        "parent": "HSCEDM15D00015",
        "source_file": "FY25_detentionStats.xlsx",
    },
    {
        "facility": "Adelanto ICE Processing Center",
        "source_label": "ADELANTO ICE PROCESSING CENTER",
        "period": "ICE FY26-to-2026-04-02",
        "data_as_of": "2026-04-02",
        "source_cell": "Facilities FY26!A12:Z12",
        "levels": ["642.688525", "179.273224", "418.147541", "493.043716"],
        "guarantee": "640",
        "task": "70CDCR26FR0000028",
        "parent": "70CDCR20D00000009",
        "source_file": "FY26_detentionStats_04092026.xlsx",
    },
    {
        "facility": "Aurora / Denver Contract Detention Facility",
        "source_label": "DENVER CONTRACT DETENTION FACILITY",
        "period": "ICE FY26-to-2026-04-02",
        "data_as_of": "2026-04-02",
        "source_cell": "Facilities FY26!A56:Z56",
        "levels": ["573.650273", "261.677596", "271.016393", "153.693989"],
        "guarantee": "600",
        "task": "70CDCR25FR0000111",
        "parent": "70CDCR22D00000001",
        "source_file": "FY26_detentionStats_04092026.xlsx",
    },
    {
        "facility": "Desert View Annex",
        "source_label": "DESERT VIEW ANNEX",
        "period": "ICE FY26-to-2026-04-02",
        "data_as_of": "2026-04-02",
        "source_cell": "Facilities FY26!A58:Z58",
        "levels": ["333.874317", "51.038251", "33.431694", "7.262295"],
        "guarantee": "120",
        "task": "70CDCR26FR0000031",
        "parent": "70CDCR20D00000009",
        "source_file": "FY26_detentionStats_04092026.xlsx",
    },
    {
        "facility": "Tacoma / Northwest ICE Processing Center",
        "source_label": "NORTHWEST ICE PROCESSSING CENTER",
        "period": "ICE FY26-to-2026-04-02",
        "data_as_of": "2026-04-02",
        "source_cell": "Facilities FY26!A150:Z150",
        "levels": ["537.278689", "201.065574", "355.644809", "195.448087"],
        "guarantee": "1181",
        "task": "70CDCR26FR0000055",
        "parent": "70CDCR26D00000026",
        "source_file": "FY26_detentionStats_04092026.xlsx",
    },
]

TASKS = {spec["task"] for spec in FACILITY_SPECS}
FACILITY_BY_TASK = {spec["task"]: spec["facility"] for spec in FACILITY_SPECS}


def money(value: object) -> str:
    if value is None:
        return ""
    return f"{Decimal(str(value)):.2f}"


def decimal_text(value: Decimal, places: int = 6) -> str:
    return f"{value:.{places}f}"


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def classify_action(description: str, amount: Decimal) -> tuple[str, str]:
    text = description.upper()
    if "CLOSE" in text or "DE-OBLIGAT" in text or "DEOBLIGAT" in text:
        return "closeout/deobligation", "Not a performance deduction, invoice credit, or unused-bed adjustment unless the source says so."
    if "EXERCISE" in text or "EXTENDS THE TERM" in text:
        return "option/extension funding", "An option/extension action is not an invoice or an occupied-bed measure."
    if "MAXIMUM NUMBER OF BEDS" in text or "MAXIMUM NUMBER" in text:
        return "capacity/administrative change", "Maximum beds are not the same as guaranteed minimum or average daily population."
    if amount == 0:
        return "zero-dollar administrative/unknown", "A zero obligation does not establish zero economic effect or a performance remedy."
    return "ordinary or incremental funding", "Action obligation is not an invoice, outlay, unit rate, or recognized facility revenue."


def build_facility_ledger(awards: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in FACILITY_SPECS:
        levels = [Decimal(value) for value in spec["levels"]]
        adp = sum(levels, Decimal("0"))
        guarantee = Decimal(spec["guarantee"])
        unused = max(guarantee - adp, Decimal("0"))
        above = max(adp - guarantee, Decimal("0"))
        award = awards[spec["task"]]
        pop = award.get("period_of_performance") or {}
        rows.append(
            {
                "facility": spec["facility"],
                "source_facility_label": spec["source_label"],
                "occupancy_period": spec["period"],
                "occupancy_data_as_of": spec["data_as_of"],
                "guaranteed_minimum": spec["guarantee"],
                "adp_level_a": spec["levels"][0],
                "adp_level_b": spec["levels"][1],
                "adp_level_c": spec["levels"][2],
                "adp_level_d": spec["levels"][3],
                "adp_total_calculated": decimal_text(adp),
                "average_unused_minimum_calculated": decimal_text(unused),
                "average_above_minimum_calculated": decimal_text(above),
                "parent_idv": spec["parent"],
                "task_order": spec["task"],
                "task_performance_start": pop.get("start_date", ""),
                "task_performance_end": pop.get("end_date", ""),
                "task_cumulative_obligation_snapshot": money(award.get("total_obligation")),
                "task_cumulative_outlay_snapshot": money(award.get("total_account_outlay")),
                "current_unit_rate": "not publicly recovered",
                "gross_invoices": "not publicly recovered",
                "payment_vouchers": "not publicly recovered; USAspending outlay kept separate",
                "credits_or_deductions": "not publicly recovered",
                "source": f"ICE {spec['source_file']} {spec['source_cell']}; USAspending award snapshot",
                "boundary": "ICE workbook ADP is the sum of Level A-D; task obligation/outlay dates do not make the award stock period-compatible with the occupancy row.",
            }
        )

    rows.append(
        {
            "facility": "Tacoma / Northwest ICE Processing Center",
            "source_facility_label": "Northwest",
            "occupancy_period": "2021-09-01 to 2022-08-31 (historical comparator)",
            "occupancy_data_as_of": "2022-08-31",
            "guaranteed_minimum": "1181",
            "adp_total_calculated": "374",
            "average_unused_minimum_calculated": "not calculated: OIG's $40m window is October 2021-August 2022",
            "average_above_minimum_calculated": "0",
            "parent_idv": "HSCEDM15D00015",
            "task_order": "",
            "task_performance_start": "",
            "task_performance_end": "",
            "task_cumulative_obligation_snapshot": "",
            "task_cumulative_outlay_snapshot": "",
            "current_unit_rate": "historical: 138.86 per detainee-day as of 2021-10",
            "gross_invoices": "not published",
            "payment_vouchers": "OIG: ICE paid more than 40 million for unused bed space for one year; nearly 5 million monthly contract payment",
            "credits_or_deductions": "not identified in OIG report",
            "source": "DHS OIG OIG-23-26 pp. 3, 14-15",
            "boundary": "Historical comparator only; do not carry the 2021 rate forward to FY25/FY26.",
        }
    )
    return rows


def build_transaction_ledger(transaction_groups: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in transaction_groups:
        piid = group["piid"]
        if piid not in TASKS:
            continue
        for transaction in group["transactions"]:
            amount = Decimal(str(transaction.get("federal_action_obligation") or 0))
            remedy_class, limit = classify_action(transaction.get("description") or "", amount)
            rows.append(
                {
                    "facility": FACILITY_BY_TASK[piid],
                    "task_order": piid,
                    "action_date": transaction.get("action_date", ""),
                    "modification_number": transaction.get("modification_number", ""),
                    "official_action_type": transaction.get("action_type_description") or transaction.get("action_type") or "not populated",
                    "federal_action_obligation": money(amount),
                    "description": transaction.get("description", ""),
                    "classification": remedy_class,
                    "interpretation_limit": limit,
                    "evidence": f"USAspending transaction {transaction.get('id', '')}",
                }
            )
    return sorted(rows, key=lambda row: (str(row["facility"]), str(row["action_date"]), str(row["modification_number"])))


def build_negative_log() -> list[dict[str, str]]:
    return [
        {
            "facility": "Adelanto / Desert View",
            "source_class": "ICE FOIA contract",
            "query_or_document": "70CDCR20D00000009 original plus P00004",
            "missing_or_redacted_field": "unit prices, obligated amounts, revised Desert View guarantee",
            "result": "2019 schedule discloses Adelanto 1-1,455 and Desert View 1-600 tiers but price fields are withheld; P00004 visibly removes the revised Desert View bed count",
            "boundary": "Historic schedule architecture is not a current FY25/FY26 rate schedule; the ICE workbooks independently provide later operational minimums.",
            "next_record_holder": "ICE Office of Acquisition Management",
        },
        {
            "facility": "Aurora",
            "source_class": "ICE FOIA modification",
            "query_or_document": "70CDCR22D00000001/P00011",
            "missing_or_redacted_field": "monthly, bed-day, transportation, and labor rates; quantities and amounts",
            "result": "document shows the rate-bearing CLIN architecture but numeric fields are redacted",
            "boundary": "Redaction is not zero and cannot be reconstructed from cumulative obligations.",
            "next_record_holder": "ICE Office of Acquisition Management",
        },
        {
            "facility": "Tacoma / Northwest",
            "source_class": "ICE FOIA modification",
            "query_or_document": "HSCEDM15D00015/P00049",
            "missing_or_redacted_field": "guaranteed-minimum beds, bed-day rate, staffing-plan headcount, quantity, unit price and amount",
            "result": "modification explicitly changes and incorporates those fields but withholds the values",
            "boundary": "OIG's 2021 rate is historical and cannot substitute for the current redacted schedule.",
            "next_record_holder": "ICE Office of Acquisition Management",
        },
        {
            "facility": "All four Western CDFs",
            "source_class": "USAspending",
            "query_or_document": "eight FY25/FY26 task-order award and transaction histories",
            "missing_or_redacted_field": "CLIN quantities and rates, invoices, receiving reports, vouchers, facility revenue allocation and performance deductions",
            "result": "award stocks and transaction obligations recovered; current cumulative outlays recovered",
            "boundary": "Outlay is an award/account disbursement measure, not a gross invoice or proof of a specific service-period payment.",
            "next_record_holder": "ICE finance/contracting office",
        },
        {
            "facility": "All four Western CDFs",
            "source_class": "ICE detention statistics",
            "query_or_document": "FY25 and FY26 facility workbooks",
            "missing_or_redacted_field": "daily/monthly population series aligned to task invoices and rates",
            "result": "facility-level YTD ADP classification components and guaranteed minimum recovered",
            "boundary": "YTD average occupancy cannot be converted to billed bed-days without the applicable schedule, daily/monthly series and invoice rules.",
            "next_record_holder": "ICE ERO and contracting office",
        },
        {
            "facility": "All four Western CDFs",
            "source_class": "public contract search",
            "query_or_document": "exact current task PIIDs and parent IDs across ICE/SAM/GAO official records",
            "missing_or_redacted_field": "funded task-order CLIN schedules and invoice packages",
            "result": "zero current unredacted official schedule/invoice results in bounded search",
            "boundary": "A bounded zero result is an access/coverage result, not proof that records do not exist.",
            "next_record_holder": "ICE Office of Acquisition Management",
        },
        {
            "facility": "Aurora",
            "source_class": "USAspending closeout action",
            "query_or_document": "70CDCR25FR0000005/P00012",
            "missing_or_redacted_field": "invoice reconciliation or performance-penalty basis",
            "result": "2026-04-07 action deobligates 1,795,324.02 in remaining funds and closes the award",
            "boundary": "The description says remaining funds; it does not call the deobligation a deduction, credit, penalty, or unused-bed adjustment.",
            "next_record_holder": "ICE contracting office",
        },
        {
            "facility": "Desert View",
            "source_class": "USAspending closeout action",
            "query_or_document": "70CDCR25FR0000010/P00009",
            "missing_or_redacted_field": "closeout reconciliation and invoice treatment",
            "result": "2026-06-16 zero-obligation closeout modification",
            "boundary": "A zero-dollar closeout action does not prove no deduction, no credit, or full invoice payment.",
            "next_record_holder": "ICE contracting office",
        },
        {
            "facility": "All four Western CDFs",
            "source_class": "GEO 2025 Form 10-K",
            "query_or_document": "SEC filing",
            "missing_or_redacted_field": "facility-specific ICE revenue, invoices, credits and deductions",
            "result": "company/segment context only; no facility-period payment ledger",
            "boundary": "Corporate revenue recognition and government procurement measures remain separate.",
            "next_record_holder": "agency contract-administration records",
        },
        {
            "facility": "All four Western CDFs",
            "source_class": "restricted/non-used sources",
            "query_or_document": "HigherGov, live SAM, paid PACER",
            "missing_or_redacted_field": "not applicable",
            "result": "not used",
            "boundary": "No conclusion relies on prohibited or paid access.",
            "next_record_holder": "not applicable",
        },
    ]


def build_report(facility_rows: list[dict[str, object]], finding_ids: list[int]) -> str:
    by_key = {(row["facility"], row["occupancy_period"]): row for row in facility_rows}
    fy25_order = [
        "Adelanto ICE Processing Center",
        "Desert View Annex",
        "Aurora / Denver Contract Detention Facility",
        "Tacoma / Northwest ICE Processing Center",
    ]
    finding_text = ", ".join(f"#{finding_id}" for finding_id in finding_ids) if finding_ids else "pending database write"

    def occupancy_table(period: str) -> str:
        lines = ["| Facility | Guaranteed minimum | ADP (A-D sum) | Avg. unused minimum | Avg. above minimum |", "|---|---:|---:|---:|---:|"]
        for facility in fy25_order:
            row = by_key[(facility, period)]
            lines.append(
                f"| {facility} | {row['guaranteed_minimum']} | {row['adp_total_calculated']} | {row['average_unused_minimum_calculated']} | {row['average_above_minimum_calculated']} |"
            )
        return "\n".join(lines)

    completed = [spec for spec in FACILITY_SPECS if spec["period"].startswith("ICE FY25")]
    current = [spec for spec in FACILITY_SPECS if spec["period"].startswith("ICE FY26")]
    award_lines = ["| Facility / task | Performance | Cumulative obligation | Cumulative outlay |", "|---|---|---:|---:|"]
    for spec in completed + current:
        row = by_key[(spec["facility"], spec["period"])]
        award_lines.append(
            f"| {spec['facility']} / `{spec['task']}` | {row['task_performance_start']} to {row['task_performance_end']} | ${Decimal(str(row['task_cumulative_obligation_snapshot'])):,.2f} | ${Decimal(str(row['task_cumulative_outlay_snapshot'])):,.2f} |"
        )

    return f"""# Western GEO contract detention facility economics

**Lead:** 60206  
**Profile / thread:** `geo-group` / 110  
**Workflow:** `analyze-contract`  
**Status:** blocked on unreleased contract-administration records

## Result

Official ICE workbooks materially narrow the guarantee and occupancy gap for Adelanto, Desert View, Aurora, and Tacoma. The FY25 workbook is a year-to-date extract as of **September 15, 2025**, not a locked full-fiscal-year dataset. The FY26 workbook is year-to-date as of **April 2, 2026**. Both report facility-level detainee-classification ADP components and a `Guaranteed Minimum` field.

{occupancy_table('ICE FY25-to-2025-09-15')}

In the FY25-to-September-15 extract, Adelanto averaged 64.455587 below its reported minimum, Desert View 56.696275 below, and Tacoma 1.383954 below; Aurora averaged 580.948424 above. These are arithmetic differences between the workbook's minimum and the sum of its four classification-level ADP fields. They are **not** billed empty-bed counts, payment amounts, or evidence that the same rate applied throughout the average period.

{occupancy_table('ICE FY26-to-2026-04-02')}

All four FY26-to-April-2 ADPs were above their reported minimums on average. The reported Adelanto minimum remained 640 and Aurora remained 600; Tacoma remained 1,181. Desert View changed from 480 in the FY25 workbook to 120 in the FY26 workbook. The workbook label is operational evidence of the minimum but does not identify the governing CLIN, amendment, effective date, pricing tier, or invoice rule. Accordingly, this pass does not call the change a contract amendment without the funded schedule.

The best recovered rate/payment comparator remains historical Tacoma evidence. DHS OIG reported that Northwest had a 1,181-detainee minimum, a $138.86 daily rate as of October 2021, a September 2021-August 2022 ADP of 374, and more than $40 million paid for unused bed space for the year before its inspection. The OIG also said ICE paid nearly $5 million monthly. Those findings establish historical economics, not the current FY25/FY26 rate.

Current unit rates, complete funded CLIN schedules, gross invoices, receiving reports, Treasury/payment vouchers, and facility-specific credits or deductions were not recovered. Public Aurora P00011 and Tacoma P00049 modifications prove that rate, quantity, guarantee and staffing fields exist but visibly withhold the values. The Adelanto/Desert View IDV shows the historic tier architecture and withholds price fields; a 2020 modification removes the revised Desert View minimum. Existing human actions 60 and 74 already target performance deductions and current rate pages. A separate Adelanto/Desert View rate-and-invoice request is recorded with this pass.

## ICE workbook method and period controls

The raw workbooks were imported and inspected with the repository's spreadsheet workflow. Target cells were inspected directly, the two facility sheets were rendered and visually checked, and a formula-error scan returned zero errors. The derived extraction JSON preserves the exact cell ranges and raw values. `FY25_detentionStats.xlsx` and `FY25_detentionStats09242025.xlsx` are byte-identical with SHA-256 `3b9e2d626b1e249b2c87539554758333b27bc0da64a37e5dac99944a210c0782`.

The FY25 facility sheet states `Data Source: ICE Integrated Decision Support (IIDS), 09/15/2025`; the FY26 sheet states `Data Source: ICE Integrated Decision Support (IIDS), 04/02/2026`. The FY26 filename embeds `04092026`, while the internal data-as-of date is April 2, 2026; the ledger uses the internal as-of date and preserves the filename separately. This report therefore uses explicit as-of labels and does not describe either extract as the final completed performance year. ADP is calculated only as Level A + Level B + Level C + Level D. No occupancy component is combined with a task award stock to derive an implied rate.

## Facility-specific reconstruction

### Adelanto and Desert View

The 2019 IDV schedule identified Adelanto CLIN 0002 as 1-1,455 guaranteed beds and CLIN 0003 as the 1,456-1,940 above-minimum tier. It identified Desert View CLIN 0002A as 1-600 guaranteed beds and CLIN 0003A as 601-750 above minimum. Unit prices and obligated amounts are withheld. P00004 says it changes Desert View's guaranteed-minimum CLIN to a new number of beds effective October 26, 2020, but the number is withheld.

The later ICE facility workbooks report Adelanto at 640 in both reviewed extracts and Desert View at 480 then 120. Because the IDV/task-order schedule establishing those later numbers was not recovered, the ledger labels them as ICE-reported operational minimums rather than reconstructing a contract rate.

USAspending separates the sites into task orders. The FY25-period tasks report cumulative obligations/outlays of $120,393,306.26 / $103,779,111.73 at Adelanto and $34,270,827.48 / $34,317,588.35 at Desert View. Their successor tasks report $86,404,000.00 / $35,037,490.56 and $17,972,900.00 / $9,822,302.78. Transaction descriptions refer to facility operating charges, daily occupancy, transportation, guard services and per-diem rates, but disclose no billable quantities or unit prices.

### Aurora

The FY25-to-September-15 workbook reports a 600 minimum and 1,180.948424 ADP; the FY26-to-April-2 workbook reports the same minimum and 1,260.038251 ADP. P00011 changes multiple rate-bearing CLINs but withholds monthly, bed-day, transportation and labor rates. USAspending P00011 on the FY25 task added $7,004,194.70 while increasing the maximum number of beds; P00012 later deobligated $1,795,324.02 in remaining funds and closed the award. The latter description is not evidence of a performance deduction, invoice credit, or unused-bed adjustment.

### Tacoma / Northwest

The ICE workbooks report a 1,181 minimum in both periods. FY25-to-September-15 ADP was 1,179.616046, almost exactly the minimum on average; FY26-to-April-2 ADP was 1,289.437159. P00049 says it changes the guaranteed-minimum bed-day rate and incorporates guaranteed-minimum and full-capacity staffing plans but withholds the bed counts, rate, headcounts, quantities, unit price, and amount.

The FY25 task accumulated $117,431,349.50 in obligations and $114,161,655.04 in outlays; its actions included funding above-guarantee services, fuel, expansion, remote posts, overtime beds, and an $11,894,500 option/extension. The successor task reports $39,042,746.99 obligated and $1,243,153.97 outlaid. These award measures do not disclose current per-diem rates or invoice allocation.

## Award and transaction measures

{"\n".join(award_lines)}

The four first rows are the most recently completed or closed predecessor tasks recovered for each facility; the four later rows are successor/current tasks aligned to the FY26 context. Values are current cumulative snapshots in the archived USAspending response, not cash paid within the workbook's occupancy period. Outlays can slightly exceed obligations in public snapshots (Aurora and Desert View predecessor tasks); this pass preserves the reported figures and does not recast the difference as an overpayment.

The transaction/modification ledger contains every public action for the eight task orders. It classifies closeouts and extensions only when the description supports that label. No action is called a performance deduction merely because it is negative or closes an award.

## Evidence-class controls

- A guaranteed minimum is not physical capacity, maximum beds, funded quantity, above-minimum ceiling, or ADP.
- ADP-to-minimum arithmetic measures average utilization relative to the reported floor, not invoice bed-days.
- A federal action obligation is a legal commitment or deobligation, not an invoice, payment or recognized revenue.
- USAspending's cumulative outlay is retained as an award/account disbursement measure, not a gross invoice or facility-period payment ledger.
- A closeout deobligation is not a penalty, credit, or unused-bed adjustment unless the source identifies it that way.
- The historical Tacoma rate is not carried into FY25/FY26.
- The SEC filing is used only for corporate context; it does not provide facility-level invoice or revenue allocation.

## Source coverage and stop rule

This pass used the official ICE detention-management page and raw FY25/FY26 workbooks, ICE FOIA contract releases, current archived USAspending award and transaction histories, parent IDV records, DHS OIG reports, local SAM bulk identity/exclusion checks, and GEO's 2025 SEC filing. HigherGov, live SAM, and paid PACER were not used.

The lead's stop condition is not met. None of the four facility chains has a period-compatible package containing the funded minimum, current rate, occupancy, gross invoice/payment and deduction inputs. ICE's public releases document agency redaction of current Aurora/Tacoma rate-bearing pages and older Adelanto/Desert View economic fields, but no current task-order schedule or agency no-record response was acquired. Current invoices, vouchers and deductions also remain agency-held. The lead is therefore blocked rather than completed.

## Database disposition

New verified findings: {finding_text}. Existing findings on the historical IDV schedules and redacted modifications are reused rather than duplicated. No post-write automatic lead generation was run; the root coordinator reserved that batch operation until all wave-11 tracks finish.

Companion artifacts preserve the [facility-period ledger](./2026-07-14-lead-60206-western-cdf-economics-wave11-facility-period-ledger.csv), [transaction/modification ledger](./2026-07-14-lead-60206-western-cdf-economics-wave11-transaction-modification-ledger.csv), [negative/redaction log](./2026-07-14-lead-60206-western-cdf-economics-wave11-negative-redaction-log.csv), source/finding manifest, and checksum ledger.
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finding-ids", nargs="*", type=int, default=[])
    parser.add_argument("--human-action-ids", nargs="*", type=int, default=[])
    args = parser.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)
    award_bundle = json.loads((SOURCE / "usaspending/usaspending-task-award-details.json").read_text())
    transaction_bundle = json.loads((SOURCE / "usaspending/usaspending-award-transactions-action-types.json").read_text())
    awards = {award["piid"]: award for award in award_bundle["awards"] if award["piid"] in TASKS}
    if awards.keys() != TASKS:
        raise RuntimeError(f"Missing task awards: {sorted(TASKS - awards.keys())}")

    facility_rows = build_facility_ledger(awards)
    transaction_rows = build_transaction_ledger(transaction_bundle["awards"])
    negative_rows = build_negative_log()

    facility_path = Path(f"{PREFIX}-facility-period-ledger.csv")
    transaction_path = Path(f"{PREFIX}-transaction-modification-ledger.csv")
    negative_path = Path(f"{PREFIX}-negative-redaction-log.csv")
    report_path = Path(f"{PREFIX}-report.md")
    manifest_path = Path(f"{PREFIX}-source-finding-manifest.json")
    sha_path = Path(f"{PREFIX}-sha256.csv")

    write_csv(
        facility_path,
        facility_rows,
        [
            "facility", "source_facility_label", "occupancy_period", "occupancy_data_as_of", "guaranteed_minimum",
            "adp_level_a", "adp_level_b", "adp_level_c", "adp_level_d", "adp_total_calculated",
            "average_unused_minimum_calculated", "average_above_minimum_calculated", "parent_idv", "task_order",
            "task_performance_start", "task_performance_end", "task_cumulative_obligation_snapshot",
            "task_cumulative_outlay_snapshot", "current_unit_rate", "gross_invoices", "payment_vouchers",
            "credits_or_deductions", "source", "boundary",
        ],
    )
    write_csv(
        transaction_path,
        transaction_rows,
        [
            "facility", "task_order", "action_date", "modification_number", "official_action_type",
            "federal_action_obligation", "description", "classification", "interpretation_limit", "evidence",
        ],
    )
    write_csv(
        negative_path,
        negative_rows,
        ["facility", "source_class", "query_or_document", "missing_or_redacted_field", "result", "boundary", "next_record_holder"],
    )
    report_path.write_text(build_report(facility_rows, args.finding_ids), encoding="utf-8")

    source_files = sorted(path for path in SOURCE.rglob("*") if path.is_file())
    manifest = {
        "generated_on": "2026-07-14",
        "profile_id": "geo-group",
        "thread_id": 110,
        "lead_id": 60206,
        "workflow": "analyze-contract",
        "disposition": "blocked",
        "disposition_reason": "Current funded CLIN/rate schedules, gross invoices/payment vouchers, and facility-specific credits or deductions remain unavailable; public ICE releases document redactions but no current task-order schedule or agency no-record response was acquired.",
        "findings_created": args.finding_ids,
        "findings_reused": [12633, 12637, 12648, 12649, 12654, 12655, 12990],
        "finding_source_map": {
            "13024": {
                "evidence_refs": [
                    "ICE-DETENTION-STATS:FY25#Facilities-FY25-A94-Z94",
                    "ICE-DETENTION-STATS:FY26-04092026#Facilities-FY26-A12-Z12",
                ],
                "local_paths": [
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY25_detentionStats.xlsx",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY26_detentionStats_04092026.xlsx",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/ice-workbook-target-inspection.json",
                ],
            },
            "13025": {
                "evidence_refs": [
                    "ICE-DETENTION-STATS:FY25#Facilities-FY25-A95-Z95",
                    "ICE-DETENTION-STATS:FY26-04092026#Facilities-FY26-A58-Z58",
                ],
                "local_paths": [
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY25_detentionStats.xlsx",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY26_detentionStats_04092026.xlsx",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/ice-workbook-target-inspection.json",
                ],
            },
            "13026": {
                "evidence_refs": [
                    "ICE-DETENTION-STATS:FY25#Facilities-FY25-A62-Z62",
                    "ICE-DETENTION-STATS:FY26-04092026#Facilities-FY26-A56-Z56",
                ],
                "local_paths": [
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY25_detentionStats.xlsx",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY26_detentionStats_04092026.xlsx",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/ice-workbook-target-inspection.json",
                ],
            },
            "13027": {
                "evidence_refs": [
                    "ICE-DETENTION-STATS:FY25#Facilities-FY25-A146-Z146",
                    "ICE-DETENTION-STATS:FY26-04092026#Facilities-FY26-A150-Z150",
                ],
                "local_paths": [
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY25_detentionStats.xlsx",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY26_detentionStats_04092026.xlsx",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/ice-workbook-target-inspection.json",
                ],
            },
            "13028": {
                "evidence_refs": [
                    "DHS-OIG:OIG-23-26#p3-northwest-adp-payment",
                    "DHS-OIG:OIG-23-26#p14-northwest-rate",
                    "DHS-OIG:OIG-23-26#p15-unused-payment",
                ],
                "local_paths": [
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/oversight/OIG-23-26-May23.pdf",
                    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/oversight/OIG-23-26-May23.txt",
                ],
            },
        },
        "human_actions_reused_or_created": args.human_action_ids,
        "source_root": str(SOURCE.relative_to(ROOT)),
        "primary_sources": [str(path.relative_to(ROOT)) for path in source_files],
        "source_roles": {
            "ICE detention statistics": "facility-level YTD ADP components and reported guaranteed minimum",
            "ICE FOIA contracts": "schedule architecture, redactions and historic tiers",
            "USAspending": "task award stock, parent IDV, cumulative outlay and transaction actions",
            "DHS OIG": "historical Tacoma rate, population and actual unused-space payment finding",
            "SEC": "corporate boundary/context only, not facility payment evidence",
            "SAM local bulk": "recipient identity and bounded local exclusion cross-check only",
        },
        "separation_rules": [
            "guarantee, funded quantity, ADP, maximum beds, capacity, unit rate, obligation, outlay, invoice, deduction and GEO revenue are not interchangeable",
            "YTD ADP cannot be converted to invoice bed-days without a rate schedule, daily/monthly population and invoice rules",
            "USAspending outlay is not relabeled as an invoice or GEO facility revenue",
            "historic Tacoma rate is not carried into FY25/FY26",
            "absence of a public deduction record is not evidence that no deduction occurred",
        ],
        "bounded_negative_searches": {row["query_or_document"]: row["result"] for row in negative_rows},
        "database_qa": {
            "foreign_key_baseline_rows": 64,
            "papercuts_logged": [1029, 1033, 1037],
            "auto_leads_run": False,
            "auto_leads_note": "Deferred by root coordinator until all wave-11 tracks complete.",
        },
        "outputs": [
            str(report_path.relative_to(ROOT)),
            str(facility_path.relative_to(ROOT)),
            str(transaction_path.relative_to(ROOT)),
            str(negative_path.relative_to(ROOT)),
            str(manifest_path.relative_to(ROOT)),
            str(sha_path.relative_to(ROOT)),
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    hash_targets = source_files + [report_path, facility_path, transaction_path, negative_path, manifest_path]
    hash_rows = [
        {"sha256": sha256(path), "bytes": path.stat().st_size, "path": str(path.relative_to(ROOT))}
        for path in sorted(hash_targets)
    ]
    write_csv(sha_path, hash_rows, ["sha256", "bytes", "path"])

    print(json.dumps({
        "facility_rows": len(facility_rows),
        "transaction_rows": len(transaction_rows),
        "negative_rows": len(negative_rows),
        "source_files": len(source_files),
        "finding_ids": args.finding_ids,
        "outputs": manifest["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
