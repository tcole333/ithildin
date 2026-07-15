#!/usr/bin/env python3
"""Build the GEO CourtListener docket inventory from isolated search outputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


PARTY_FILES = {
    "party-geo-group.json": "The GEO Group, Inc.",
    "party-geo-corrections-holdings.json": "GEO Corrections Holdings, Inc.",
    "party-geo-secure-services.json": "GEO Secure Services, LLC",
    "party-geo-care.json": "GEO Care, Inc.",
    "party-bi-inc.json": "B.I. Incorporated",
    "party-cornell.json": "Cornell Companies, Inc.",
    "party-correctional-services.json": "Correctional Services Corporation",
    "party-community-education-centers.json": "Community Education Centers, Inc.",
    "party-wackenhut-corrections.json": "Wackenhut Corrections Corporation",
}

LEGACY_ALIASES = {
    "Cornell Companies, Inc.",
    "Correctional Services Corporation",
    "Community Education Centers, Inc.",
    "Wackenhut Corrections Corporation",
}

TARGETED_DOCKET_FILES = {
    "docket-geo-v-us.json": "targeted procurement search",
    "docket-geo-hcc-florida.json": "targeted insurance search",
}

TARGETED_SECURITIES_IDS = {17329078, 60987359, 64919885}
DEEP_READ_DOCKET_IDS = {
    63759997,  # GEO Group, Inc. v. United States
    16229592,  # Hynd
    6114747,  # Burciaga
    17329078,  # Hartel
    60987359,  # Zhang
    4669735,  # HCC Life (Texas)
    13426410,  # GEO v. HCC Life (Florida)
}


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def triage_category(row: dict[str, Any]) -> str:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("case_name", "suit_nature", "cause")
    ).lower()
    docket_id = row["docket_id"]

    if docket_id == 63759997 or "bid protest" in text or "pre award" in text:
        return "procurement_or_bid_protest"
    if "false claims" in text or "qui tam" in text:
        return "false_claims_act"
    if "securities" in text or "stockholder" in text or "derivative" in text:
        return "securities_or_derivative"
    if (
        re.search(r"\b(710|720|730|740|750|751|790)\b", text)
        or "labor:" in text
        or "labor litigation" in text
        or "fair labor" in text
        or "title vii" in text
        or "employment" in text
        or "equal employment" in text
        or "age discrimination" in text
    ):
        return "employment_or_labor"
    if any(term in text for term in ("contract", "insurance", "arbitration", "breach")):
        return "contract_or_commercial"
    if any(term in text for term in ("tax", "internal revenue")):
        return "tax"
    if any(
        term in text
        for term in (
            "prison",
            "habeas",
            "civil rights",
            "personal injury",
            "p.i.:",
            "torts - injury",
            "federal tort claims",
            "conditions of confinement",
            "immigration",
        )
    ):
        return "detention_civil_rights_or_tort"
    return "other"


def normalize_search_row(raw: dict[str, Any], alias: str) -> dict[str, Any]:
    return {
        "docket_id": int(raw["docket_id"]),
        "courtlistener_url": "https://www.courtlistener.com"
        + raw["docket_absolute_url"],
        "court_id": raw.get("court_id"),
        "court": raw.get("court"),
        "docket_number": raw.get("docketNumber"),
        "case_name": raw.get("caseName"),
        "date_filed": raw.get("dateFiled"),
        "date_terminated": raw.get("dateTerminated"),
        "suit_nature": raw.get("suitNature"),
        "cause": raw.get("cause"),
        "matched_party_names": sorted(set(raw.get("party") or [])),
        "query_aliases": [alias],
        "source_queries": [f"party endpoint: {alias}"],
        "recap_document_hits": len(raw.get("recap_documents") or []),
    }


def normalize_docket_row(raw: dict[str, Any], source_query: str) -> dict[str, Any]:
    return {
        "docket_id": int(raw["id"]),
        "courtlistener_url": "https://www.courtlistener.com" + raw["absolute_url"],
        "court_id": raw.get("court_id"),
        "court": None,
        "docket_number": raw.get("docket_number"),
        "case_name": raw.get("case_name"),
        "date_filed": raw.get("date_filed"),
        "date_terminated": raw.get("date_terminated"),
        "suit_nature": raw.get("nature_of_suit"),
        "cause": raw.get("cause"),
        "matched_party_names": [],
        "query_aliases": [],
        "source_queries": [source_query],
        "recap_document_hits": None,
    }


def merge(rows: dict[int, dict[str, Any]], candidate: dict[str, Any]) -> None:
    docket_id = candidate["docket_id"]
    if docket_id not in rows:
        rows[docket_id] = candidate
        return

    existing = rows[docket_id]
    for field in ("matched_party_names", "query_aliases", "source_queries"):
        existing[field] = sorted(set(existing[field]) | set(candidate[field]))
    if existing["recap_document_hits"] is None:
        existing["recap_document_hits"] = candidate["recap_document_hits"]


def entity_scope_status(row: dict[str, Any]) -> str:
    aliases = set(row["query_aliases"])
    if not aliases:
        return "targeted_supplement"
    if "B.I. Incorporated" in aliases:
        return "ambiguous_name_requires_manual_identity_confirmation"
    if aliases & LEGACY_ALIASES:
        return "legacy_name_requires_corporate_lineage_check"
    return "current_geo_name_match"


def add_targeted_securities(rows: dict[int, dict[str, Any]], input_dir: Path) -> None:
    for raw in load(input_dir / "cases-geo-zoley-securities.json"):
        if raw.get("docket_id") not in TARGETED_SECURITIES_IDS:
            continue
        candidate = normalize_search_row(raw, "")
        candidate["query_aliases"] = []
        candidate["source_queries"] = ["targeted GEO/Zoley securities search"]
        merge(rows, candidate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    rows: dict[int, dict[str, Any]] = {}
    raw_query_counts: dict[str, int] = {}
    party_raw_total = 0

    for filename, alias in PARTY_FILES.items():
        raw_rows = load(args.input_dir / filename)
        raw_query_counts[alias] = len(raw_rows)
        party_raw_total += len(raw_rows)
        for raw in raw_rows:
            merge(rows, normalize_search_row(raw, alias))

    party_unique_total = len(rows)

    for filename, source_query in TARGETED_DOCKET_FILES.items():
        merge(rows, normalize_docket_row(load(args.input_dir / filename), source_query))

    add_targeted_securities(rows, args.input_dir)

    for row in rows.values():
        row["triage_category"] = triage_category(row)
        row["entity_scope_status"] = entity_scope_status(row)
        row["selected_for_deep_read"] = row["docket_id"] in DEEP_READ_DOCKET_IDS

    ordered = sorted(
        rows.values(),
        key=lambda row: (row["date_filed"] or "", row["docket_id"]),
        reverse=True,
    )
    category_counts = Counter(row["triage_category"] for row in ordered)
    scope_counts = Counter(row["entity_scope_status"] for row in ordered)

    metadata = {
        "title": "GEO Group CourtListener deduplicated docket inventory",
        "generated_on": "2026-07-13",
        "profile": "geo-group",
        "party_endpoint_raw_total": party_raw_total,
        "party_endpoint_unique_dockets": party_unique_total,
        "targeted_supplement_count": len(ordered) - party_unique_total,
        "final_unique_dockets": len(ordered),
        "raw_query_counts": raw_query_counts,
        "triage_category_counts": dict(sorted(category_counts.items())),
        "entity_scope_counts": dict(sorted(scope_counts.items())),
        "limitations": [
            "CourtListener search results are a bounded index, not a complete PACER universe.",
            "The GEO Group party query reached the 200-result collection cap.",
            "B.I. Incorporated matches require manual entity confirmation because the name is not unique.",
            "Legacy-company matches require a corporate-lineage check before attribution to GEO.",
            "Triage categories are deterministic screening labels, not adjudicated case characterizations.",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "geo-courtlistener-dockets-deduplicated.json"
    csv_path = args.output_dir / "geo-courtlistener-dockets-deduplicated.csv"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump({"metadata": metadata, "dockets": ordered}, handle, indent=2)
        handle.write("\n")

    fields = [
        "docket_id",
        "courtlistener_url",
        "court_id",
        "court",
        "docket_number",
        "case_name",
        "date_filed",
        "date_terminated",
        "suit_nature",
        "cause",
        "triage_category",
        "entity_scope_status",
        "selected_for_deep_read",
        "recap_document_hits",
        "matched_party_names",
        "query_aliases",
        "source_queries",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in ordered:
            output = dict(row)
            for field in ("matched_party_names", "query_aliases", "source_queries"):
                output[field] = " | ".join(output[field])
            writer.writerow({field: output.get(field) for field in fields})

    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
