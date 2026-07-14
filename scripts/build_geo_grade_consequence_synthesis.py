#!/usr/bin/env python3
"""Join the complete ICE inspection/death denominator to consequence evidence.

This is an analysis artifact builder, not a causal classifier.  It preserves
inspection grades, component status, UCAP/corrective records, OIG status,
penalties, award actions, and death reviews as separate evidence classes.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


ADDED_COLUMNS = [
    "grade_component_relation",
    "repeat_status",
    "inspection_corrective_class",
    "facility_consequence_row_count",
    "oversight_record_classes",
    "oig_or_odo_consequence_classes",
    "ucap_or_corrective_evidence",
    "penalty_or_invoice_evidence",
    "option_extension_or_renewal_evidence",
    "award_modification_or_capacity_evidence",
    "consequence_linked_findings",
    "systemwide_oversight_row_count",
    "ach_relevance",
    "causal_limit",
]


def unique_join(values: list[str]) -> str:
    return " || ".join(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def grade_component_relation(row: dict[str, str]) -> str:
    if row["record_type"] == "death_review":
        return "not_applicable_death_review"
    return {
        "compliant_grade_with_component_deficiencies": "compliant_grade_with_deficient_components",
        "compliant_grade_no_component_deficiencies": "compliant_grade_with_explicit_zero_deficient_components",
        "compliant_grade_component_status_not_stated": "compliant_grade_component_status_not_stated_or_ambiguous",
        "no_noncompliance_identified": "monthly_area_level_no_noncompliance_statement",
        "conditional_preoccupancy_action_plans": "not_selected_conditional_preoccupancy",
        "deep_dive_recommendations_no_issue": "deep_dive_issue_column_none",
        "one_noncompliance_with_mitigation": "explicit_noncompliance_with_mitigation",
    }[row["control_class"]]


def ach_relevance(row: dict[str, str]) -> str:
    if row["record_type"] == "death_review":
        return "not_applicable: death review/report evidence is not an inspection-grade or contract-remedy test"
    relation = grade_component_relation(row)
    if relation == "compliant_grade_with_deficient_components":
        return "grade/component divergence; consequence mechanism remains unproved without linked administration records"
    if relation == "compliant_grade_with_explicit_zero_deficient_components":
        return "H0 control: explicit zero-component compliant inspection"
    if relation == "compliant_grade_component_status_not_stated_or_ambiguous":
        return "neutral control: component status is not supportably known"
    if relation == "monthly_area_level_no_noncompliance_statement":
        return "H0 control: area-level no-noncompliance statement, not a component count"
    if relation in {"not_selected_conditional_preoccupancy", "explicit_noncompliance_with_mitigation"}:
        return "H0 counterexample to universal grade compression; completion/durability remains a separate question"
    return "H0 control: no issue stated in the reviewed deep-dive record"


def consequence_fields(rows: list[dict[str, str]]) -> dict[str, str]:
    return {
        "facility_consequence_row_count": str(len(rows)),
        "oversight_record_classes": unique_join([r["oversight_record_type"] for r in rows]),
        "oig_or_odo_consequence_classes": unique_join([r["report_consequence_class"] for r in rows]),
        "ucap_or_corrective_evidence": unique_join([r["ucap_or_corrective_action"] for r in rows]),
        "penalty_or_invoice_evidence": unique_join([r["invoice_deduction_or_withheld_payment"] for r in rows]),
        "option_extension_or_renewal_evidence": unique_join([r["option_extension_renewal"] for r in rows]),
        "award_modification_or_capacity_evidence": unique_join([r["later_capacity_or_funding"] for r in rows]),
        "consequence_linked_findings": unique_join([r["linked_findings"] for r in rows]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True, type=Path)
    parser.add_argument("--consequences", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with args.coverage.open(newline="", encoding="utf-8") as stream:
        coverage = list(csv.DictReader(stream))
        base_columns = list(coverage[0])
    with args.consequences.open(newline="", encoding="utf-8") as stream:
        consequences = list(csv.DictReader(stream))

    by_facility: dict[str, list[dict[str, str]]] = defaultdict(list)
    systemwide = []
    for row in consequences:
        if row["facility"] == "Systemwide ICE detention oversight":
            systemwide.append(row)
        else:
            by_facility[row["facility"]].append(row)

    output_rows = []
    for row in coverage:
        facilities = [x.strip() for x in row["canonical_facility"].split("|")]
        matched = []
        for facility in facilities:
            matched.extend(by_facility.get(facility, []))
        joined = consequence_fields(matched)
        if not matched:
            joined.update({
                "facility_consequence_row_count": "0",
                "oversight_record_classes": "not covered by the 31-row facility consequence crosswalk",
                "oig_or_odo_consequence_classes": "not tested",
                "ucap_or_corrective_evidence": "not tested",
                "penalty_or_invoice_evidence": "not tested; no absence inference",
                "option_extension_or_renewal_evidence": "not tested",
                "award_modification_or_capacity_evidence": "not tested",
                "consequence_linked_findings": "",
            })
        relation = grade_component_relation(row)
        repeat_status = (
            "explicit_repeat_deficiency_language"
            if "repeat deficien" in row["repeat_issue_language"].lower()
            else "no_repeat_language_in_extracted_deficiency_section"
        )
        if row["record_type"] == "death_review":
            corrective_class = "separate_death_review_response_class"
        elif row["ucap_or_corrective_action_language"].startswith("No UCAP language"):
            corrective_class = "no_literal_ucap_or_corrective_action_in_linked_inspection_artifacts"
        else:
            corrective_class = "explicit_action_plan_mitigation_or_corrective_language"
        causal_parts = [row["scope_note"]]
        causal_parts.extend(r["causation_limit"] for r in matched)
        output_rows.append({
            **row,
            "grade_component_relation": relation,
            "repeat_status": repeat_status,
            "inspection_corrective_class": corrective_class,
            **joined,
            "systemwide_oversight_row_count": str(len(systemwide)),
            "ach_relevance": ach_relevance(row),
            "causal_limit": unique_join(causal_parts),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=base_columns + ADDED_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
