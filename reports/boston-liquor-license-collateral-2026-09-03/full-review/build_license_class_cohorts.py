#!/usr/bin/env python3
"""Build bounded, offline analytic cohorts from exact roster class labels.

The whitelist below is deliberately exhaustive for the saved 2026-09-03
inventory. New or conflicting classes fail closed. These assignments make no
legal, transaction-price, acquisition-route, or ownership determinations.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


BASE = Path(__file__).resolve().parent
EXPECTED_LICENSES = 1520

# Exact source strings, including the source's "Famer" spelling. Airport
# precedence is explicit; source family survives the primary cohort assignment.
RULE_GROUPS = [
    (
        "airport_labeled", "common_victualler", "Common Victualler",
        ["CV7 All Alc. Airp.", "CV7 Malt Wine Airp."],
    ),
    ("airport_labeled", "club", "Club", ["Clb. All Alc. Airport"]),
    (
        "airport_labeled", "general_on_premise", "General on Premise",
        ["GOP All Alcohol Airport"],
    ),
    (
        "innholder_labeled", "innholder", "Inn",
        [
            "INNALN - Neighborhood Restricted", "Inn. All Alc.",
            "Inn. All Alc. Restrict.", "Innholder Malt & Wine",
        ],
    ),
    (
        "retail_druggist_labeled", "retail", "Misc",
        ["Retail All Alc.", "Retail Malt Wine"],
    ),
    ("retail_druggist_labeled", "druggist", "Misc", ["Druggist"]),
    (
        "club_labeled_nonairport", "club", "Club",
        ["Clb. All Alc.", "Clb. All Alc. Vet.", "Club Malt & Wine", "Club Malt, Wine & Liqueur"],
    ),
    (
        "producer_farmer_labeled", "producer_farmer", "Misc",
        [
            "Famer-Brewery Pouring", "Farmer Brewery Distillery Pouring License",
            "Farmer Brewery and Winery", "Farmer Brewery,Winery & Distillery License",
            "Farmer Distillery Pouring License", "Farmer-Winery Pouring",
        ],
    ),
    (
        "common_victualler_onprem_nonairport", "common_victualler", "Common Victualler",
        [
            "CV & All Alc Oak Sq Restricted", "CV7 All Alc Comm Spaces Restricted",
            "CV7 All Alc Unrestricted 2024", "CV7 All Alc by Zip Restricted",
            "CV7 All Alc.", "CV7 All Alc. (Special Legislation)",
            "CV7 All Alc. Restrict.", "CV7 All Alc. South Bay Restricted",
            "CV7 Malt Wine", "CV7 Malt Wine Liq by Zip Restricted",
            "CV7 Malt Wine Liq.", "CV7 Malt Wine Liq. Restrict.",
            "CV7 Malt Wine Restrict.", "CV7 Malt Wine by Zip Restricted",
            "CV7ALN - Neighborhood Restricted", "CV7MWLN - Neighborhood Restricted",
            "CV7MWN - Neighborhood Restricted",
            "Common Victualler 7 Day All-Alcohol Bolling Building Restricted",
            "Common Victualler 7 Day Malt & Wine (South Bay Restricted)",
        ],
    ),
    (
        "other_onprem_labeled", "general_on_premise", "General on Premise",
        [
            "GOP All Alc.", "GOP Malt Wine", "GOP Malt Wine Liq.",
            "GOPALN - Neighborhood Restricted", "Gen Prem All Alcohol Rest",
            "General On Premise Comm Spaces Restricted",
        ],
    ),
    ("other_onprem_labeled", "tavern", "Misc", ["Tavern Licenses"]),
    ("byob_separate", "byob", "Common Victualler", ["BYOB Bring Your Own Bottle"]),
    ("unresolved_abbreviation", "unresolved", "Misc", ["SPCMWA"]),
]

SEGMENT_LABELS = {
    "airport_labeled": "Airport-labeled",
    "innholder_labeled": "Innholder / hotel-labeled",
    "retail_druggist_labeled": "Retail / druggist-labeled",
    "club_labeled_nonairport": "Club-labeled — no airport label",
    "producer_farmer_labeled": "Producer / farmer-labeled",
    "common_victualler_onprem_nonairport": "Common Victualler on-premises — no airport label",
    "other_onprem_labeled": "Other on-premises-labeled — no airport label",
    "byob_separate": "BYOB — separate scope",
    "unresolved_abbreviation": "Unresolved source abbreviation",
}

FLAG_DEFINITIONS = {
    "restricted_literal": "Whole word Restricted or explicit abbreviation Restrict. in license_type only; Unrestricted does not match.",
    "unrestricted_literal": "Whole word Unrestricted in license_type only.",
    "special_legislation_literal": "Literal phrase Special Legislation in license_type only.",
    "ambiguous_rest_abbreviation": "Exact class Gen Prem All Alcohol Rest; Rest is not decoded as Restricted.",
    "community_spaces_literal": "Literal phrase Comm Spaces in license_type only.",
}

LIMITATIONS = [
    "These are analytic source-label cohorts, not legal conclusions about transferability, license eligibility, acquisition route, transaction completion, purchase price, ownership, or control.",
    "Only license_type supplies literal restriction and special-legislation flags. Comments, statutes, awards, applications, and individual instruments may contain additional conditions.",
    "No restriction label does not mean unrestricted. Special Legislation does not itself establish restricted or unrestricted status. Unrestricted 2024 does not establish a market purchase.",
    "Airport takes precedence over club, Common Victualler, and general-on-premises in the primary segment; source family is retained separately. These labels do not identify the current concession operator or owner.",
    "Innholder labels help separate a source-labeled cohort; they do not verify hotel ownership. A hotel restaurant may have a Common Victualler label, so no innholder label does not establish no hotel connection.",
    "Common Victualler is a source license family, not proof of a conventional restaurant. Bars, stadium or arena venues, community spaces, and other settings may remain in that family unless separately evidenced.",
    "The pre-existing core/boundary scope is preserved. Druggist remains category_needs_verification even though its label is placed beside retail. SPCMWA remains opaque and unresolved. BYOB is separate.",
    "The full 1,520-ID label mapping is complete; legal, ownership, lien, price, and transaction reviews are not thereby complete. No ownership information was used in these assignments.",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(value: object) -> str:
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def literal_flags(label: str) -> dict[str, bool]:
    return {
        "restricted_literal": bool(re.search(r"\bRestricted\b|\bRestrict\.(?=\s|$|\))", label)),
        "unrestricted_literal": bool(re.search(r"\bUnrestricted\b", label)),
        "special_legislation_literal": "Special Legislation" in label,
        "ambiguous_rest_abbreviation": label == "Gen Prem All Alcohol Rest",
        "community_spaces_literal": "Comm Spaces" in label,
    }


def restriction_label_state(flags: dict[str, bool]) -> str:
    if flags["restricted_literal"]:
        return "restricted_literal"
    if flags["unrestricted_literal"]:
        return "unrestricted_literal"
    if flags["ambiguous_rest_abbreviation"]:
        return "ambiguous_rest_abbreviation"
    return "none_in_class_label"


def build() -> dict:
    inventory_bytes = (BASE / "inventory-rows.json").read_bytes()
    csv_bytes = (BASE / "source-licenses.csv").read_bytes()
    inventory = json.loads(inventory_bytes)
    # review-data is validation-only: ownership changes do not affect assignment.
    review = json.loads((BASE / "review-data.json").read_bytes())["licenses"]
    csv.field_size_limit(16 * 1024 * 1024)
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"), newline=""))
    require({"license_num", "license_type", "license_category"} <= set(reader.fieldnames or []), "Unexpected source CSV header")
    csv_rows = list(reader)
    require(len(csv_rows) == len(inventory), "Source CSV and inventory row counts differ")

    rules = {}
    for segment, family, category, labels in RULE_GROUPS:
        for label in labels:
            require(label not in rules, f"Duplicate whitelist class: {label!r}")
            rules[label] = {
                "license_type": label,
                "expected_source_category": category,
                "source_label_segment": segment,
                "source_label_family": family,
                "license_type_literal_flags": literal_flags(label),
            }

    require(not literal_flags("CV7 All Alc Unrestricted 2024")["restricted_literal"], "Unrestricted must not match Restricted")
    require(not literal_flags("Gen Prem All Alcohol Rest")["restricted_literal"], "Rest must remain ambiguous")
    require(literal_flags("CV7 All Alc. Restrict.")["restricted_literal"], "Explicit Restrict. flag failed")

    grouped = defaultdict(list)
    for row in inventory:
        original = csv_rows[row["source_record_number"] - 1]
        for key in ("license_num", "license_type", "license_category"):
            require(row[key] == original[key], f"Inventory/source mismatch at {row['source_row_id']}: {key}")
        if row["queue_included"]:
            grouped[row["license_num"]].append(row)

    require(len(grouped) == EXPECTED_LICENSES, f"Expected {EXPECTED_LICENSES} review IDs, got {len(grouped)}")
    require(len(review) == len({row["license_num"] for row in review}), "Duplicate review license IDs")
    review_by_id = {row["license_num"]: row for row in review}
    require(set(grouped) == set(review_by_id), "Inventory queue and review ID sets differ")
    actual_classes = {row["license_type"] for rows in grouped.values() for row in rows}
    require(actual_classes <= set(rules), f"Unrecognized source classes: {sorted(actual_classes - set(rules))}")
    require(actual_classes == set(rules), f"Whitelist classes absent from this snapshot: {sorted(set(rules) - actual_classes)}")

    licenses = []
    projection = []
    for license_num, rows in sorted(grouped.items()):
        types = sorted({row["license_type"] for row in rows})
        categories = sorted({row["license_category"] for row in rows})
        scopes = {row["scope_class"] for row in rows}
        row_ids = sorted(row["source_row_id"] for row in rows)
        require(len(types) == 1, f"Conflicting source classes for {license_num}: {types}")
        require(len(scopes) == 1, f"Conflicting scope for {license_num}: {scopes}")
        rule = rules[types[0]]
        require(categories == [rule["expected_source_category"]], f"Unexpected category for {license_num}: {categories}")
        scope = next(iter(scopes))
        review_row = review_by_id[license_num]
        require(review_row["license_type"] == types[0], f"Review/inventory class mismatch: {license_num}")
        require(review_row["scope_class"] == scope, f"Review/inventory scope mismatch: {license_num}")
        require(sorted(review_row["source_row_ids"]) == row_ids, f"Review/inventory source IDs mismatch: {license_num}")
        flags = rule["license_type_literal_flags"]
        require(not (flags["restricted_literal"] and flags["unrestricted_literal"]), f"Conflicting literal flags: {license_num}")
        expected_scope = {
            "byob": "byob_separate", "druggist": "category_needs_verification",
            "unresolved": "category_needs_verification",
        }.get(rule["source_label_family"], "alcohol_license")
        require(scope == expected_scope, f"Unexpected scope/class pairing: {license_num}")
        notes = []
        if rule["source_label_segment"] == "airport_labeled":
            notes.append("Airport label takes primary-segment precedence; secondary source family is retained.")
        if flags["ambiguous_rest_abbreviation"]:
            notes.append("Rest is an ambiguous source abbreviation; it is not treated as Restricted.")
        if rule["source_label_family"] == "unresolved":
            notes.append("SPCMWA is preserved without expanding or interpreting the abbreviation.")
        if rule["source_label_family"] == "druggist":
            notes.append("Retail/druggist grouping does not resolve whether this boundary record is an alcohol license.")
        licenses.append({
            "license_num": license_num,
            "scope_class": scope,
            "license_type": types[0],
            "source_license_types": types,
            "source_license_categories": categories,
            "source_row_ids": row_ids,
            "source_row_count": len(rows),
            "source_row_evidence": [
                {key: row[key] for key in ("source_row_id", "source_record_number", "raw_row_sha256")}
                for row in sorted(rows, key=lambda item: item["source_row_id"])
            ],
            "source_label_segment": rule["source_label_segment"],
            "source_label_family": rule["source_label_family"],
            "license_type_literal_flags": flags,
            "restriction_label_state": restriction_label_state(flags),
            "classification_status": "unresolved_opaque_source_label" if rule["source_label_family"] == "unresolved" else "source_label_mapped",
            "classification_notes": notes,
            "legal_transferability": "not_determined_from_source_labels",
            "acquisition_route": "unknown_from_source_labels",
            "license_purchase_price": None,
            "price_status": "unknown_from_source_labels",
        })
        projection.append({"license_num": license_num, "license_type": types[0], "scope_class": scope, "source_row_ids": row_ids})

    class_mapping = []
    for label, rule in sorted(rules.items()):
        matching = [row for row in licenses if row["license_type"] == label]
        class_mapping.append({
            **rule,
            "restriction_label_state": restriction_label_state(rule["license_type_literal_flags"]),
            "license_count": len(matching),
            "source_row_count": sum(row["source_row_count"] for row in matching),
            "scope_counts": dict(sorted(Counter(row["scope_class"] for row in matching).items())),
        })
    segments = []
    for segment, label in SEGMENT_LABELS.items():
        matching = [row for row in licenses if row["source_label_segment"] == segment]
        segments.append({
            "source_label_segment": segment, "label": label, "license_count": len(matching),
            "core_alcohol_count": sum(row["scope_class"] == "alcohol_license" for row in matching),
            "boundary_count": sum(row["scope_class"] != "alcohol_license" for row in matching),
            "source_family_counts": dict(sorted(Counter(row["source_label_family"] for row in matching).items())),
        })
    marker_example = [row for row in inventory if row["license_num"] == "LB-464491"]
    require(len(marker_example) == 1 and marker_example[0]["license_type"] == "CV7 All Alc.", "Source-label limitation example changed")
    example = marker_example[0]
    flag_counts = {flag: sum(row["license_type_literal_flags"][flag] for row in licenses) for flag in FLAG_DEFINITIONS}
    return {
        "schema_version": "1.0",
        "title": "Boston license-class cohorts from literal source labels",
        "source_snapshot_date": "2026-09-03",
        "assignment_basis": "Exact source license_type whitelist; inventory queue_included selects the review universe; review-data validates ID/class/scope/source-row identity only.",
        "provenance": {
            "inventory": {"path": "inventory-rows.json", "sha256": digest(inventory_bytes), "rows": len(inventory)},
            "original_csv": {"path": "source-licenses.csv", "sha256": digest(csv_bytes), "rows": len(csv_rows)},
            "generator": {"path": Path(__file__).name, "sha256": digest(Path(__file__).read_bytes())},
            "review_validation": {
                "path": "review-data.json",
                "validated_fields": ["license_num", "license_type", "scope_class", "source_row_ids"],
                "canonical_projection_sha256": canonical_digest(projection),
                "ownership_fields_used": False,
            },
        },
        "counts": {
            "review_license_ids": len(licenses),
            "matched_source_rows": sum(row["source_row_count"] for row in licenses),
            "distinct_source_license_types": len(class_mapping),
            "scope_counts": dict(sorted(Counter(row["scope_class"] for row in licenses).items())),
            "source_family_counts": dict(sorted(Counter(row["source_label_family"] for row in licenses).items())),
            "literal_flag_license_counts": flag_counts,
            "restriction_label_state_counts": dict(sorted(Counter(row["restriction_label_state"] for row in licenses).items())),
            "unrecognized_source_classes": 0,
            "known_unresolved_label_license_ids": [row["license_num"] for row in licenses if row["classification_status"] == "unresolved_opaque_source_label"],
            "ambiguous_rest_label_license_ids": [row["license_num"] for row in licenses if row["license_type_literal_flags"]["ambiguous_rest_abbreviation"]],
            "excluded_source_rows": len(inventory) - sum(row["source_row_count"] for row in licenses),
        },
        "segments": segments,
        "literal_flag_definitions": FLAG_DEFINITIONS,
        "limitations": LIMITATIONS,
        "source_field_mismatch_example": {
            "license_num": example["license_num"], "source_row_id": example["source_row_id"],
            "license_type": example["license_type"], "source_comments": example["comments"],
            "interpretation": "Restriction and special-legislation language is present in comments but absent from this class label. The class-only flags therefore cannot establish legal transferability.",
        },
        "suggested_filters": [
            {"field": "source_label_segment", "label": "Source-label venue cohort"},
            {"field": "source_label_family", "label": "Source license family"},
            {"field": "scope_class", "label": "Core alcohol / separate boundary records"},
            {"field": "restriction_label_state", "label": "Restriction wording in class label"},
            {"field": "license_type_literal_flags.special_legislation_literal", "label": "Special Legislation wording in class label"},
            {"field": "license_type_literal_flags.community_spaces_literal", "label": "Community-space wording in class label"},
            {"field": "license_type", "label": "Exact source license type"},
        ],
        "class_mapping": class_mapping,
        "licenses": licenses,
    }


def readme(result: dict) -> str:
    counts = result["counts"]
    lines = [
        "# Boston source-label license cohorts", "",
        "This offline mapping covers all **1,520 review license IDs**: **1,512 core alcohol licenses**, five separate BYOB records, and three unclear-category records. The IDs correspond to 1,530 of the 3,610 saved source rows and 49 exact license-type strings. The remaining 2,080 source rows are outside the existing review queue.", "",
        "These are **analytic cohorts from source labels**, not legal findings about transferability, market purchases, acquisition routes, prices, ownership, or control. Assignments use no ownership fields. A complete class mapping does not mean those other reviews are complete.", "",
        "## Cohorts", "",
        "Primary cohorts are mutually exclusive. An airport label takes precedence over club, Common Victualler, and general-on-premises; `source_label_family` retains those secondary families.", "",
        "| Source-label cohort | All review IDs | Core alcohol | Boundary |",
        "| --- | ---: | ---: | ---: |",
    ]
    for segment in result["segments"]:
        lines.append(f"| {segment['label']} | {segment['license_count']:,} | {segment['core_alcohol_count']:,} | {segment['boundary_count']:,} |")
    lines += [
        "| **Total** | **1,520** | **1,512** | **8** |", "",
        "The 51 airport-labeled IDs retain families of 45 Common Victualler, five club, and one general-on-premises. Innholder labels are not a hotel ownership census. Hotel restaurants, arenas, stadiums, bars, and other venues may appear under Common Victualler or another class. A missing airport/hotel label does not prove the venue is an ordinary restaurant.", "",
        "The retail/druggist cohort includes `LB-101303` (`Druggist`), which **remains an unclear-category boundary record**. `SPCMWA` remains unresolved for `LB-102883` and `LB-102890`; no expansion of that abbreviation is assumed. The five BYOB records retain their separate scope. The source typo `Famer-Brewery Pouring` is preserved exactly.", "",
        "## Literal flags", "",
        "Flags inspect `license_type` only. They are separate from venue cohorts and are not a legal transferability classification.", "",
        "| Wording found in class label | License IDs |",
        "| --- | ---: |",
        f"| Restricted or Restrict. | {counts['literal_flag_license_counts']['restricted_literal']} |",
        f"| Unrestricted | {counts['literal_flag_license_counts']['unrestricted_literal']} |",
        f"| Special Legislation | {counts['literal_flag_license_counts']['special_legislation_literal']} |",
        f"| Ambiguous Rest abbreviation | {counts['literal_flag_license_counts']['ambiguous_rest_abbreviation']} |",
        f"| Comm Spaces | {counts['literal_flag_license_counts']['community_spaces_literal']} |", "",
        "`Unrestricted` cannot match the `Restricted` flag. `Gen Prem All Alcohol Rest` (`LB-352398`, Institute of Contemporary Art) receives the ambiguous `Rest` flag, not a restricted flag. Special-legislation and community-space flags are independent; flag counts should not be summed as exclusive cohorts.", "",
        "Absence of restriction wording is not proof of unrestricted transferability. For example, `LB-464491` has class `CV7 All Alc.` while its saved comments include “Special Legislation Restricted” and a same-location transfer condition. The JSON preserves this source-field mismatch example. Likewise, the class `CV7 All Alc Unrestricted 2024` does not establish whether a license was purchased or directly awarded. Acquisition route and purchase price remain unknown in this class-only artifact.", "",
        "## Suggested comparison filters", "",
        "Use **Source-label venue cohort**, **Source license family**, **Core alcohol / separate boundary records**, **Restriction wording in class label**, **Special Legislation wording in class label**, and **Exact source license type**. Keep restriction choices as literal restricted, literal unrestricted, ambiguous Rest, and no wording in class label; do not rename the last choice unrestricted.", "",
        "For a restaurant-oriented comparison, show the Common Victualler cohort separately and offer explicit inclusion of other on-premises, airport, innholder, club, and producer cohorts. Show the selected denominator and retain unknown ownership separately. These comparisons can describe source-label composition; testing a price effect still requires actual transactions, acquisition routes, venue context, and ownership evidence.", "",
        "## Provenance and regeneration", "",
        "`license-class-cohorts.json` preserves every exact license ID, original class/category strings, scope, source-row IDs and raw-row hashes. It includes the complete 49-class whitelist, cohort counts, flags, limitations, and stable input hashes. `inventory-rows.json` selects the queue; `source-licenses.csv` verifies original class/category fields. `review-data.json` is checked only for the stable ID/class/scope/source-row projection, so ownership updates do not alter the mapping.", "",
        "Run from the repository root:", "",
        "```sh",
        "uv run python reports/boston-liquor-license-collateral-2026-09-03/full-review/build_license_class_cohorts.py",
        "```", "",
        "The generator performs no network requests. It fails before writing if an unknown class, conflicting class/category/scope, unexpected license count, or inventory/source/review mismatch appears. Known opaque `SPCMWA` records are explicitly unresolved. The whitelist and output need deliberate review if the snapshot changes.", "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    result = build()
    (BASE / "license-class-cohorts.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (BASE / "license-class-cohorts-README.md").write_text(readme(result))
    print(json.dumps({"counts": result["counts"], "segments": result["segments"]}, indent=2))
