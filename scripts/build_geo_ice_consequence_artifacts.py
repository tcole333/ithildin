#!/usr/bin/env python3
"""Build lead 57784's inspection-to-contract-consequence matrix and manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


COMMON_GAP = (
    "No public cure/show-cause letter, invoice-level deduction or withholding log, "
    "award-fee adjustment, or CPARS evaluation was located in the bounded official-source "
    "review. This is an access/coverage result, not evidence that no such record or remedy exists."
)


CONTRACTS = {
    "Adelanto ICE Processing Center": {
        "award": "70CDCR20D00000009 (later direct ICE period; do not merge with historical City D-IGSA)",
        "option_extension_renewal": "Later direct IDIQ period: 2019-12-20 through 2029-12-19; FY2026 task 70CDCR26FR0000028.",
        "later_capacity_or_funding": "FY2026 task actions totaled $86,404,000 through 2026-06-10; the descriptions fund detention and transportation, not a performance remedy.",
        "action_refs": "HigherGov:70CDCR20D00000009 | USAspending:70CDCR26FR0000028",
        "linked_findings": "12789 | 12790 | 12801",
    },
    "Denver Contract Detention Facility": {
        "award": "HSCEDM11D00003 (historical); 70CDCR22D00000001 (later direct IDIQ)",
        "option_extension_renewal": "Later direct IDIQ period: 2021-10-16 through 2026-10-15; annual task orders continued after the 2024 reports.",
        "later_capacity_or_funding": "P00011 on 70CDCR25FR0000005 added $7,004,194.70 and increased the maximum number of beds on 2025-09-23.",
        "action_refs": "USAspending:70CDCR25FR0000005-P00011",
        "linked_findings": "12799 | 12800 | 12802 | 12820",
    },
    "Folkston ICE Processing Center": {
        "award": "EROIGSA-17-0002 (Charlton County prime; GEO downstream operator)",
        "option_extension_renewal": "Signed modification P00022 lists performance through 2027-02-15; it is not a remedy document.",
        "later_capacity_or_funding": "ICE reported all posts covered with overtime at the vendor's expense while hiring continued.",
        "action_refs": "ICE:EROIGSA-17-0002-P00022 | DHS-OIG:OIG-22-47#p29",
        "linked_findings": "12425 | 12426 | 12427",
    },
    "Golden State Annex": {
        "award": "70CDCR20D00000008 (shared California detention IDIQ with Mesa Verde)",
        "option_extension_renewal": "Parent IDIQ ordering period extends through 2034-12-20; FY2025 and FY2026 shared tasks continued.",
        "later_capacity_or_funding": "FY2026 task 70CDCR26FR0000042 received Golden State-specific funding on 2026-06-26; the public action does not state the revised minimum.",
        "action_refs": "USAspending:70CDCR20D00000008 | USAspending:70CDCR26FR0000042-P00004",
        "linked_findings": "12421 | 12422 | 12423 | 12424",
    },
    "Mesa Verde ICE Processing Center": {
        "award": "70CDCR20D00000008 (shared California detention IDIQ with Golden State)",
        "option_extension_renewal": "Parent IDIQ ordering period extends through 2034-12-20; FY2025 and FY2026 shared tasks continued.",
        "later_capacity_or_funding": "FY2026 task 70CDCR26FR0000042 received Mesa Verde-specific funding on 2026-05-22.",
        "action_refs": "USAspending:70CDCR20D00000008 | USAspending:70CDCR26FR0000042-P00003",
        "linked_findings": "12797 | 12798",
    },
    "Northwest ICE Processing Center": {
        "award": "HSCEDM15D00015 (through 2025); 70CDCR26D00000026 (2026 bridge)",
        "option_extension_renewal": "P00008 extended FY2025 task 70CDCR25FR0000004; a later seven-month sole-source IDIQ/task runs through 2026-10-27.",
        "later_capacity_or_funding": "P00008 added $11,894,500 for services including expansion, remote posts, and overtime beds; the 2026 bridge task records $39,042,746.99 in the current universe.",
        "action_refs": "USAspending:70CDCR25FR0000004-P00008 | USAspending:70CDCR26D00000026 | USAspending:70CDCR26FR0000055",
        "linked_findings": "12792 | 12795 | 12796 | 12803 | 12804 | 12819 | 12822 | 12823",
    },
    "South Texas ICE Processing Center": {
        "award": "HSCEDM12D00001 (historical); 70CDCR20D00000012 (later direct IDIQ)",
        "option_extension_renewal": "Later direct IDIQ ordering period runs 2020-08-06 through 2030-08-05; FY2025 task 70CDCR25FR0000091 continued into 2026.",
        "later_capacity_or_funding": "P00001 incorporated emergency beds on 2025-09-16; current task actions total $57,517,165.28, but the public descriptions do not link the expansion to OIG-22-40.",
        "action_refs": "USAspending:70CDCR20D00000012 | USAspending:70CDCR25FR0000091-P00001",
        "linked_findings": "12793 | 12794 | 12818 | 12821",
    },
    "Karnes County Residential Center": {
        "award": "Historical county/ICE arrangement; do not merge automatically with 70CDCR24DIG000018",
        "option_extension_renewal": "Not tested because the reviewed investigative summary did not substantiate the specified allegations and does not identify the operative award.",
        "later_capacity_or_funding": "Not applicable as a consequence test for this non-substantiation control.",
        "action_refs": "DHS-OIG-KARNES-2015",
        "linked_findings": "12805",
    },
    "Systemwide ICE detention oversight": {
        "award": "Systemwide; do not attribute to one GEO facility or award",
        "option_extension_renewal": "Not facility-specific.",
        "later_capacity_or_funding": "Not facility-specific.",
        "action_refs": "",
        "linked_findings": "",
    },
}


REPORTS = {
    "OIG-18-86": {
        "class": "corrective_follow_up_no_public_financial_effect",
        "notice": "The OIG report itself documented PBNDS violations; no separate contractual discrepancy/cure notice was located.",
        "corrective": "ICE said it would conduct a full inspection and Special Assessment Review; July 2024 ODO follow-up reported no findings.",
        "financial": "No public deduction, withholding, award-fee, or CPARS consequence located.",
        "status": "Resolved/open at issuance; later no-findings inspection is counterevidence, not proof of the intervening contract-administration path.",
    },
    "OIG-19-47": {
        "class": "aggregate_corrective_response_no_facility_financial_effect",
        "notice": "Aggregate OIG report; no facility-specific contract discrepancy or cure notice located.",
        "corrective": "ICE reported corrective action when warranted and promised follow-up documentation; the recommendation was resolved/open at issuance.",
        "financial": "No facility-specific deduction, withholding, award-fee, or CPARS consequence located.",
        "status": "Aggregate response cannot establish closure or consequence for each named facility.",
    },
    "OIG-20-45": {
        "class": "planned_sar_with_later_recurrence",
        "notice": "The OIG report documented Northwest grievance deficiencies; no separate contractual notice located.",
        "corrective": "ICE planned a Special Assessment Review; later OIG/ODO records found grievance or repeat deficiencies.",
        "financial": "No public deduction, withholding, award-fee, or CPARS consequence located.",
        "status": "Resolved/open at issuance; later recurrence limits any inference of durable correction.",
    },
    "OIG-22-40": {
        "class": "closed_readiness_response_minimum_preserved",
        "notice": "OIG documented deficiencies and approximately $18 million paid for unused guaranteed beds; no separate cure notice located.",
        "corrective": "Three recommendations were closed at issuance; recommendations 2 and 4 remained publicly open on 2026-07-14. Recommendation 5 closed after ICE described combining housing units to meet the guaranteed minimum while following pandemic rules.",
        "financial": "The public report documents full guaranteed-minimum economics, not a deduction or rate reduction.",
        "status": "Documented ordinary readiness response; the public record does not show that the guaranteed minimum or rates were changed.",
    },
    "OIG-22-47": {
        "class": "documented_penalty_non_enforcement_with_operational_cost",
        "notice": "ICE filed staffing-related contract discrepancy reports in 2019 and 2021.",
        "corrective": "Twelve recommendations were closed at issuance and one open; staffing recommendation 12 is now publicly closed. ICE said vendor-paid overtime covered posts while hiring continued.",
        "financial": "OIG said ICE did not enforce the stated financial penalties and Folkston continued to receive full contract funding.",
        "status": "Strongest public GEO example of documented non-enforcement; invoice amounts, waivers, and closure support remain unavailable.",
    },
    "OIG-23-26": {
        "class": "open_contract_correction_plus_later_extension",
        "notice": "OIG documented facility deficiencies; no separate cure/show-cause notice located.",
        "corrective": "Three recommendations closed, four resolved/open, and recommendation 7 unresolved/open after ICE non-concurred with adjusting the guaranteed minimum; public page still showed 1, 2, 3, 7, and 8 open on 2026-07-14.",
        "financial": "No public deduction or CPARS consequence located; recommendation 7 sought a contract-minimum adjustment.",
        "status": "Contract correction remained open while later task extension/expansion actions occurred; the records do not state that oversight caused or was ignored in those actions.",
    },
    "OIG-24-03": {
        "class": "mixed_corrective_status_no_public_financial_effect",
        "notice": "OIG documented a use-of-force reporting deficiency; no separate contractual notice located.",
        "corrective": "All three recommendations were resolved/open at issuance; the public page showed recommendation 1 open on 2026-07-14. Absence of 2 and 3 from the open list was not treated as proof of closure.",
        "financial": "No public deduction, withholding, award-fee, or CPARS consequence located.",
        "status": "Operational correction and continued task funding are documented separately; proportional financial consequence remains unknown.",
    },
    "OIG-24-23": {
        "class": "closed_minimum_update_terms_not_public",
        "notice": "OIG documented facility deficiencies and approximately $25.3 million paid for unused guaranteed beds.",
        "corrective": "Recommendation 7, requiring a housing-needs analysis and updated guaranteed minimum, is publicly closed; recommendations 1, 2, and 3 remained open on 2026-07-14.",
        "financial": "The revised minimum, effective date, rates, invoice effects, and savings are not public in the reviewed records.",
        "status": "Closure is counterevidence to a blanket non-remediation theory, but proportionality cannot be tested without the closure package and contract terms.",
    },
    "OIG-24-29": {
        "class": "mixed_corrective_status_plus_later_capacity_increase",
        "notice": "OIG documented Denver deficiencies; no separate contractual discrepancy/cure notice located.",
        "corrective": "Six recommendations were closed and eight open at issuance; public page showed 1, 4, 6, 7, 8, and 13 open on 2026-07-14. A later ODO follow-up recorded both compliance and new deficiencies.",
        "financial": "No public deduction, withholding, award-fee, or CPARS consequence located.",
        "status": "A 2025 maximum-bed increase is documented, but the award action does not link the decision to inspection performance.",
    },
    "DHS-OIG-KARNES-2015": {
        "class": "non_substantiation_control",
        "notice": "No contractual deficiency notice expected from the cited source because OIG did not substantiate the specified allegations.",
        "corrective": "OIG reported PREA reporting compliance and supplied its report to ICE/CRCL.",
        "financial": "No adverse contract consequence inferred or expected from this record.",
        "status": "Control only; not a general facility-compliance determination.",
    },
    "ICE-ODO-2024-002-386": {
        "class": "later_no_findings_control",
        "notice": "ODO reported no findings.",
        "corrective": "Later-period no-findings follow-up is positive control evidence.",
        "financial": "No adverse financial consequence expected from this report.",
        "status": "Does not retroactively negate OIG-18-86.",
    },
    "ICE-ODO-2024-002-330": {
        "class": "completed_prior_ucap_new_deficiencies_later_capacity_increase",
        "notice": "ODO reported six deficiencies in four standards and a staffing area of concern.",
        "corrective": "The report states a prior UCAP was completed and likely resolved earlier cited items; it does not show closure of the new deficiencies.",
        "financial": "No public deduction, withholding, award-fee, or CPARS consequence located.",
        "status": "Later maximum-bed increase is neutral continuation evidence because the action does not discuss performance treatment.",
    },
    "ICE-ODO-2024-005-389": {
        "class": "completed_ucap_repeat_deficiencies_plus_later_extension",
        "notice": "ODO reported 11 deficiencies in six standards, including two repeat deficiencies.",
        "corrective": "ODO said the completed January 2024 UCAP may not have been sufficient and recommended continued work on outstanding deficiencies.",
        "financial": "No public deduction, withholding, award-fee, or CPARS consequence located.",
        "status": "Durable correction was not established before later extension/expansion actions.",
    },
    "ICE-ODO-OPR-201200440": {
        "class": "mixed_compliance_control_later_contracting",
        "notice": "ODO reported three deficiencies in two standards and compliance in 13 standards.",
        "corrective": "ERO was to use the report to develop corrective actions; closeout details are not public in the reviewed record.",
        "financial": "No public financial consequence located.",
        "status": "Historical mixed control; later contract awards are not evidence of the treatment of the 2012 items.",
    },
    "ICE-DDR-GONZALEZ-2017": {
        "class": "causation_caveat_control",
        "notice": "Death review listed deficiencies but expressly disclaimed inferring that they contributed to the death.",
        "corrective": "No contract consequence inferred from the reviewed caveat.",
        "financial": "Not tested from this source.",
        "status": "Preserves the report's causation limit.",
    },
    "GAO-15-153": {
        "class": "systemwide_not_facility_attributable",
        "notice": "Systemwide inspection-consistency finding; not a GEO facility notice.",
        "corrective": "GAO later closed the related recommendation after ICE changed contractor procedures.",
        "financial": "No GEO-specific consequence can be attributed from this source.",
        "status": "Systemwide control only.",
    },
    "GAO-20-596": {
        "class": "systemwide_not_facility_attributable",
        "notice": "Systemwide trend-analysis finding; not a GEO facility notice.",
        "corrective": "Recommendation status is tracked systemwide.",
        "financial": "No GEO-specific consequence can be attributed from this source.",
        "status": "Systemwide control only.",
    },
    "GAO-21-149": {
        "class": "systemwide_not_facility_attributable",
        "notice": "Systemwide acquisition/COR-independence finding; not a GEO facility notice.",
        "corrective": "Recommendation status is tracked systemwide.",
        "financial": "No GEO-specific consequence can be attributed without the underlying sampled award records.",
        "status": "Systemwide control only.",
    },
    "GAO-25-107580": {
        "class": "systemwide_not_facility_attributable",
        "notice": "Systemwide ODO performance-goal finding; not a GEO facility notice.",
        "corrective": "ODO performance-goal recommendation remained open as of May 2026.",
        "financial": "No GEO-specific consequence can be attributed from this source.",
        "status": "Systemwide balanced control only.",
    },
}


FIELDS = [
    "facility", "report_id", "report_date", "row_evidentiary_role", "oversight_body",
    "oversight_record_type", "oversight_issue_domain", "oversight_quote", "oversight_source_url",
    "award_or_vehicle", "report_consequence_class", "deficiency_notice_or_discrepancy",
    "ucap_or_corrective_action", "cure_or_show_cause", "invoice_deduction_or_withheld_payment",
    "award_fee_or_cpars", "option_extension_renewal", "later_capacity_or_funding",
    "agency_response_or_control", "consequence_evidence_refs", "public_record_gap",
    "causation_limit", "linked_findings",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_row(source: dict[str, str]) -> dict[str, str]:
    contract = CONTRACTS[source["facility"]]
    report = REPORTS[source["report_id"]]
    role = "control_or_counterevidence" if any(
        token in source["finding_class"] for token in ("compliant", "caveat", "conclusion")
    ) else "adverse_or_systemic_observation"
    no_adverse = report["class"] in {
        "non_substantiation_control", "later_no_findings_control", "causation_caveat_control"
    }
    return {
        "facility": source["facility"],
        "report_id": source["report_id"],
        "report_date": source["report_date"],
        "row_evidentiary_role": role,
        "oversight_body": source["oversight_body"],
        "oversight_record_type": source["record_type"],
        "oversight_issue_domain": source["issue_domain"],
        "oversight_quote": source["exact_quote"],
        "oversight_source_url": source["source_url"],
        "award_or_vehicle": contract["award"],
        "report_consequence_class": report["class"],
        "deficiency_notice_or_discrepancy": report["notice"],
        "ucap_or_corrective_action": report["corrective"],
        "cure_or_show_cause": "Not applicable to this control row." if no_adverse else "No public cure/show-cause letter located in the reviewed official sources.",
        "invoice_deduction_or_withheld_payment": report["financial"],
        "award_fee_or_cpars": "No public award-fee or CPARS record located; absence is not proof that none exists.",
        "option_extension_renewal": contract["option_extension_renewal"],
        "later_capacity_or_funding": contract["later_capacity_or_funding"],
        "agency_response_or_control": source["agency_or_geo_response"] or report["status"],
        "consequence_evidence_refs": " | ".join(filter(None, [source["report_id"], contract["action_refs"]])),
        "public_record_gap": COMMON_GAP,
        "causation_limit": "Chronology establishes sequence only. No continuation, extension, capacity action, or funding action is attributed to inspection performance unless the cited record says so.",
        "linked_findings": contract["linked_findings"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oversight-matrix", required=True, type=Path)
    parser.add_argument("--action-rows", required=True, type=Path)
    parser.add_argument("--idv-families", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with args.oversight_matrix.open(encoding="utf-8") as stream:
        rows = [build_row(row) for row in csv.DictReader(stream)]
    if len(rows) != 31:
        raise ValueError(f"Expected 31 oversight rows, got {len(rows)}")

    matrix_path = args.output_dir / "2026-07-14-lead-57784-geo-ice-performance-consequence-matrix.csv"
    with matrix_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "lead_id": 57784,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Quote-reviewed oversight rows joined to public corrective-status, contract-action, extension, renewal, and capacity records. Missing private contract-administration records remain explicit unknowns.",
        "coverage": {
            "matrix_rows": len(rows),
            "distinct_facilities_or_systemic_scope": len({row["facility"] for row in rows}),
            "distinct_reports": len({row["report_id"] for row in rows}),
            "evidentiary_roles": dict(Counter(row["row_evidentiary_role"] for row in rows)),
            "consequence_classes": dict(Counter(row["report_consequence_class"] for row in rows)),
        },
        "separation_rules": [
            "absence in reviewed public sources is not absence of a consequence",
            "USAspending obligation actions do not expose invoice-level credits, offsets, deductions, or CPARS treatment",
            "continuation, extension, renewal, or capacity growth is neutral unless a source links it to performance treatment",
            "compliant findings, non-substantiation, and causation caveats remain controls",
            "facility, award, task, and IGSA-chain counts are not interchangeable",
        ],
        "audited_findings": [12422, 12425, 12426, 12427, 12428, 12789, 12790, 12792, 12793, 12794, 12795, 12796, 12797, 12798, 12799, 12800, 12801, 12802, 12803, 12804, 12805, 12806, 12818, 12819, 12820, 12821, 12822, 12823],
        "record_acquisition": {
            "human_action_38": "Existing Golden State minimum/invoice package",
            "human_action_60": "Direct-facility QASP, deficiency, invoice, CPARS, and option/capacity package",
            "human_action_61": "Folkston ICE/Charlton discrepancy, deduction, and staffing-closeout package",
            "infra_request_150": "Existing ISAP/Golden/Folkston contract-administration request",
        },
        "input_files": [
            {"path": str(path), "sha256": sha256(path)}
            for path in (args.oversight_matrix, args.action_rows, args.idv_families)
        ],
        "output_files": [
            matrix_path.name,
            "2026-07-14-lead-57784-geo-ice-performance-consequence-ach.json",
            "2026-07-14-lead-57784-geo-ice-performance-consequence-report.md",
        ],
    }
    manifest_path = args.output_dir / "2026-07-14-lead-57784-geo-ice-performance-consequence-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "matrix": str(matrix_path), "manifest": str(manifest_path)}))


if __name__ == "__main__":
    main()
