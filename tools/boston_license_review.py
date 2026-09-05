#!/usr/bin/env python3
"""Build and audit a local Boston license-review queue; never queries the network.

Inventory retains source row lineage while grouping only punctuation/case variants
of legal holder names. Current and lapsed UCC searches, document review, transfers,
and supplied ownership evidence are separate coverage dimensions.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path


EXCLUDED_TYPES = {
    "Common Victualler", "Dormitory", "Lodging Houses (Frat/Dorm)",
    "Billiards/Sippio", "Innholder No Liquor", "Bowling Alley", "Fortune Teller",
}
BOUNDARY_TYPES = {"SPCMWA", "Druggist"}
ALCOHOL_TYPES = {
    "CV7 All Alc.", "Retail All Alc.", "CV7 Malt Wine Liq.", "CV7 Malt Wine",
    "Inn. All Alc.", "Retail Malt Wine", "CV7 All Alc. Airp.",
    "CV7ALN - Neighborhood Restricted", "CV7 All Alc by Zip Restricted",
    "Clb. All Alc.", "CV7 All Alc. Restrict.", "CV7 Malt Wine by Zip Restricted",
    "GOP All Alc.", "CV7 Malt Wine Restrict.", "CV7 Malt Wine Liq. Restrict.",
    "Famer-Brewery Pouring", "CV7 All Alc. (Special Legislation)",
    "Clb. All Alc. Vet.", "CV7 Malt Wine Liq by Zip Restricted",
    "Farmer Brewery,Winery & Distillery License", "CV7 All Alc. South Bay Restricted",
    "Farmer Brewery and Winery", "CV7MWN - Neighborhood Restricted",
    "Clb. All Alc. Airport", "Inn. All Alc. Restrict.",
    "CV7MWLN - Neighborhood Restricted", "Farmer Distillery Pouring License",
    "General On Premise Comm Spaces Restricted", "CV & All Alc Oak Sq Restricted",
    "CV7 All Alc Comm Spaces Restricted", "GOP Malt Wine Liq.",
    "Farmer Brewery Distillery Pouring License", "CV7 All Alc Unrestricted 2024",
    "Common Victualler 7 Day All-Alcohol Bolling Building Restricted",
    "CV7 Malt Wine Airp.", "INNALN - Neighborhood Restricted",
    "Club Malt, Wine & Liqueur", "Tavern Licenses", "Innholder Malt & Wine",
    "GOP Malt Wine", "Farmer-Winery Pouring", "GOPALN - Neighborhood Restricted",
    "Common Victualler 7 Day Malt & Wine (South Bay Restricted)",
    "Gen Prem All Alcohol Rest", "GOP All Alcohol Airport", "Club Malt & Wine",
}
BUSINESS_FIELDS = (
    "license_num", "historicallicensenum", "status", "license_category", "license_type",
    "issued", "expires", "business_name", "dba_name", "comments", "location_comments", "descpremadd",
    "address", "city", "state", "zip",
)
STATES = {"pending", "complete", "partial", "blocked", "error"}


def normalized_holder(name: str) -> str:
    """Retain corporate endings; this is a string group, not beneficial ownership."""
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def holder_id(key: str) -> str:
    return "BH-" + hashlib.sha256(key.encode()).hexdigest()[:16]


def proposed_query(name: str) -> str:
    return re.sub(
        r"(?:,?\s+)(?:L\.?L\.?C\.?|Inc\.?|Incorporated|Corp\.?|Corporation|L\.?P\.?|L\.?L\.?P\.?)\s*$",
        "", name, flags=re.I,
    ).strip(" ,")


def classify_type(value: str) -> str:
    if value in EXCLUDED_TYPES:
        return "excluded_non_alcohol"
    if value == "BYOB Bring Your Own Bottle":
        return "byob_separate"
    if value in BOUNDARY_TYPES:
        return "category_needs_verification"
    if value in ALCOHOL_TYPES:
        return "alcohol_license"
    return "unknown_type_needs_verification"


def name_mode_reasons(name: str) -> list[str]:
    if re.search(r"\bINDIVIDUAL\b", name, re.I):
        return ["explicit_individual_label_requires_person_name_resolution"]
    compact = normalized_holder(name)
    designator = re.search(r"(?:LLC|LLP|LLLP|INC|INCORPORATED|CORP|CORPORATION|LP|LTD|LIMITED)$", compact)
    institution = re.search(
        r"\b(?:COMPANY|TRUST|ASSOCIATION|SOCIETY|COLLEGE|UNIVERSITY|COUNCIL|CHURCH|CLUB|SCHOOL|"
        r"AUTHORITY|HOTEL|CO|HOSPITAL|INSTITUTE|PARTNERSHIP|MUSEUM|LIBRARY|COMMUNITY|LODGE|POST|CONGREGATION|FOUNDATION)\b",
        name, re.I,
    )
    return [] if designator or institution else ["organization_form_not_explicit_person_or_trade_name_review"]


def read_csv(path: Path) -> list[dict]:
    csv.field_size_limit(2_000_000)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(BUSINESS_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing roster columns: {sorted(missing)}")
        return list(reader)


def load(path: Path):
    return json.loads(path.read_text())


def load_events(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    value = load(path)
    if isinstance(value, dict):
        value = value.get("events", value.get("results"))
    if not isinstance(value, list):
        raise ValueError("Expected an events array, envelope, or JSONL file")
    return value


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty table without an explicit schema")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict))
                             else value for key, value in row.items()})


def inventory(roster: Path, as_of: str) -> tuple[dict, list[dict], dict]:
    cutoff = date.fromisoformat(as_of)
    raw = read_csv(roster)
    license_counts = Counter(row["license_num"] for row in raw)
    raw_hashes = [hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest() for row in raw]
    hash_counts = Counter(raw_hashes)
    license_names = defaultdict(set)
    for row in raw:
        license_names[row["license_num"]].add(normalized_holder(row["business_name"]))
    rows = []
    groups = defaultdict(list)
    for number, (source, digest) in enumerate(zip(raw, raw_hashes, strict=True), start=1):
        expiry = source["expires"]
        try:
            expiry_state = "expired" if date.fromisoformat(expiry) < cutoff else "not_expired"
        except ValueError:
            expiry_state = "missing" if not expiry else "invalid"
        key = normalized_holder(source["business_name"])
        classification = classify_type(source["license_type"])
        marker_fields = {
            field: sorted({match.group(0).lower() for match in re.finditer(r"pledge|collateral|lien|loan", source[field], re.I)})
            for field in ("comments", "location_comments", "descpremadd")
        }
        marker_fields = {field: terms for field, terms in marker_fields.items() if terms}
        item = {
            "source_row_id": f"R{number:05d}", "source_record_number": number,
            "raw_row_sha256": digest, "scope_class": classification,
            "queue_included": classification != "excluded_non_alcohol",
            "holder_key": key, "holder_id": holder_id(key) if key else None,
            "license_row_count": license_counts[source["license_num"]],
            "exact_raw_row_copies": hash_counts[digest],
            "license_holder_conflict": len(license_names[source["license_num"]]) > 1,
            "expiry_assessment": expiry_state,
            "active_label_with_expired_date": source["status"] == "Active" and expiry_state == "expired",
            "pledge_comment_marker": bool(re.search(r"pledge", source["comments"], re.I)),
            "financing_comment_marker": bool(re.search(r"pledge|collateral|lien|loan", source["comments"], re.I)),
            "financing_marker_fields": marker_fields,
            "pledge_any_field_marker": any("pledge" in terms for terms in marker_fields.values()),
            "financing_any_field_marker": bool(marker_fields),
            **{field: source[field] for field in BUSINESS_FIELDS},
        }
        rows.append(item)
        if item["queue_included"] and key:
            groups[key].append(item)
    holders = []
    for key, group in sorted(groups.items()):
        name = group[0]["business_name"].strip()
        query = proposed_query(name)
        scope_classes = sorted({row["scope_class"] for row in group})
        holders.append({
            "holder_id": holder_id(key), "holder_key": key, "business_name": name,
            "name_variants": sorted({row["business_name"] for row in group}),
            "dbas": sorted({row["dba_name"] for row in group if row["dba_name"]}),
            "license_numbers": sorted({row["license_num"] for row in group}),
            "source_row_ids": [row["source_row_id"] for row in group],
            "scope_classes": scope_classes,
            "has_core_alcohol_license": "alcohol_license" in scope_classes,
            "license_types": sorted({row["license_type"] for row in group}),
            "premises": sorted({", ".join(row[field] for field in ("address", "city", "state", "zip")) for row in group}),
            "expired_source_row_count": sum(row["expiry_assessment"] == "expired" for row in group),
            "pledge_comment_marker": any(row["pledge_comment_marker"] for row in group),
            "pledge_any_field_marker": any(row["pledge_any_field_marker"] for row in group),
            "financing_any_field_marker": any(row["financing_any_field_marker"] for row in group),
            "query_proposal": {"command": "search-org", "query": query, "role": "debtor",
                               "search_type": "begins", "city": None, "state": None, "since": None, "limit": 500},
            "query_input_requires_review": len(query) > 175 or not query,
            "name_mode_review_reasons": name_mode_reasons(name),
            "name_mode_note": "Organization mode proposed from roster business_name; resolve a personal/partnership debtor form if evidence requires it.",
            "searches": {scope: {"state": "pending", "attempts": []} for scope in ("current", "lapsed")},
            "document_review": {"state": "not_started", "note": "Index completion does not complete filing histories or attachments."},
            "ownership_review": {"state": "not_started"},
        })
    classes = {}
    for classification in sorted({row["scope_class"] for row in rows}):
        subset = [row for row in rows if row["scope_class"] == classification]
        classes[classification] = {
            "rows": len(subset), "unique_license_numbers": len({row["license_num"] for row in subset}),
            "unique_nonempty_holder_keys": len({row["holder_key"] for row in subset if row["holder_key"]}),
        }
    included = [row for row in rows if row["queue_included"]]
    summary = {
        "as_of": as_of, "raw_rows": len(rows), "raw_unique_license_numbers": len(license_counts),
        "scope_classes": classes, "included_rows": len(included),
        "included_unique_license_numbers": len({row["license_num"] for row in included}),
        "included_legal_holder_groups": len(holders),
        "included_missing_legal_names": sum(not row["holder_key"] for row in included),
        "included_expired_rows": sum(row["expiry_assessment"] == "expired" for row in included),
        "included_expired_unique_licenses": len({row["license_num"] for row in included if row["expiry_assessment"] == "expired"}),
        "included_repeated_license_numbers": len({row["license_num"] for row in included if row["license_row_count"] > 1}),
        "included_holder_conflict_license_numbers": sorted({row["license_num"] for row in included if row["license_holder_conflict"]}),
        "included_pledge_comment_licenses": sorted({row["license_num"] for row in included if row["pledge_comment_marker"]}),
        "included_pledge_any_field_licenses": sorted({row["license_num"] for row in included if row["pledge_any_field_marker"]}),
        "included_financing_any_field_licenses": sorted({row["license_num"] for row in included if row["financing_any_field_marker"]}),
        "all_roster_status_counts": dict(Counter(row["status"] for row in rows)),
        "license_type_rows": dict(sorted(Counter(row["license_type"] for row in rows).items())),
    }
    queue = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of, "source_roster": str(roster.resolve()),
        "source_roster_sha256": hashlib.sha256(roster.read_bytes()).hexdigest(),
        "normalization": "Uppercase ASCII letters/digits; punctuation and spacing removed; corporate endings retained. String groups are not verified corporate identities or common control.",
        "scope_note": "Core alcohol licenses plus separately labeled BYOB and unresolved categories; retain expiry/status exceptions and every source row. This is not a historical transfer register.",
        "holders": holders,
    }
    return summary, rows, queue


def validate_event(event: dict, known: set[str]) -> None:
    if event.get("holder_id") not in known:
        raise ValueError("Event has unknown holder_id")
    if event.get("scope") not in {"current", "lapsed"} or event.get("state") not in STATES - {"pending"}:
        raise ValueError("Event requires current/lapsed scope and a non-pending state")
    if not event.get("source_file") or not event.get("capture_method") or not event.get("query"):
        raise ValueError("Event requires source_file, capture_method and query provenance")
    if event["state"] == "complete":
        reported, returned = event.get("reported_count"), event.get("returned_count")
        if (type(reported) is not int or type(returned) is not int or reported < 0
                or returned != reported or event.get("truncated") is not False):
            raise ValueError("Complete search requires equal nonnegative reported/returned counts and truncated:false")
        query = event["query"]
        if not isinstance(query, dict) or query.get("role") != "debtor":
            raise ValueError("Holder index completion requires documented debtor search parameters")
        if any(query.get(field) for field in ("city", "state", "since")):
            raise ValueError("Filtered searches cannot complete the all-location/date holder queue scope")


def merge_events(queue: dict, events: list[dict]) -> dict:
    merged = copy.deepcopy(queue)
    holders = {holder["holder_id"]: holder for holder in merged["holders"]}
    for event in events:
        validate_event(event, set(holders))
        target = holders[event["holder_id"]]["searches"][event["scope"]]
        identity = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        if any(attempt.get("event_sha256") == identity for attempt in target["attempts"]):
            continue
        target["attempts"].append({**event, "event_sha256": identity})
        # Preserve a successful same-scope observation if a later attempt fails.
        if target["state"] != "complete" or event["state"] == "complete":
            target["state"] = event["state"]
            target["latest_effective_event_sha256"] = identity
        reviewed = event.get("review", {}).get("reviewed_filing_numbers", [])
        if reviewed:
            document = holders[event["holder_id"]]["document_review"]
            document["state"] = "partial_prior_evidence"
            document["reviewed_filing_numbers"] = sorted(set(document.get("reviewed_filing_numbers", [])) | set(reviewed))
            document["note"] = "Supplied history evidence exists; scope-wide history and attachment completion is not established."
    return merged


def validate_queue(queue: dict) -> dict:
    holders = queue["holders"]
    ids = [holder["holder_id"] for holder in holders]
    keys = [holder["holder_key"] for holder in holders]
    if len(ids) != len(set(ids)) or len(keys) != len(set(keys)):
        raise ValueError("Duplicate holder ID or normalized name in queue")
    row_ids = []
    for holder in holders:
        if holder["holder_id"] != holder_id(holder["holder_key"]) or not holder["license_numbers"]:
            raise ValueError("Invalid stable holder ID or missing license lineage")
        row_ids.extend(holder["source_row_ids"])
        for scope in ("current", "lapsed"):
            search = holder["searches"][scope]
            if search["state"] not in STATES:
                raise ValueError("Unknown queue state")
            for event in search["attempts"]:
                validate_event(event, set(ids))
                if event["holder_id"] != holder["holder_id"] or event["scope"] != scope:
                    raise ValueError("Search event stored under wrong holder or scope")
            if search["state"] == "complete" and not any(event["state"] == "complete" for event in search["attempts"]):
                raise ValueError("Complete state lacks a complete evidence event")
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("A source row is assigned to multiple holders")
    return {"valid": True, "holders": len(ids), "source_rows": len(row_ids)}


def coverage(queue: dict, transfers: list[dict] | None = None, owners: list[dict] | None = None) -> dict:
    validate_queue(queue)
    holders = queue["holders"]
    known_ids = {holder["holder_id"] for holder in holders}
    licenses = {number for holder in holders for number in holder["license_numbers"]}
    result = {
        "holder_groups": len(holders), "unique_license_numbers": len(licenses),
        "core_alcohol_holder_groups": sum(holder["has_core_alcohol_license"] for holder in holders),
        "search_states": {scope: dict(Counter(holder["searches"][scope]["state"] for holder in holders)) for scope in ("current", "lapsed")},
        "both_scopes_complete": sum(all(holder["searches"][scope]["state"] == "complete" for scope in ("current", "lapsed")) for holder in holders),
        "document_review_states": dict(Counter(holder["document_review"]["state"] for holder in holders)),
        "holder_groups_needing_name_mode_review": sum(bool(holder.get("name_mode_review_reasons")) for holder in holders),
        "limits": "Search completion is query/index coverage, not all filing documents, an active lien, a license pledge, an outstanding loan, or ownership verification.",
    }
    if transfers is not None:
        unique = {(row["license_number"], row["vote_date"], row["item"], row.get("pdf_url")) for row in transfers}
        if len(unique) != len(transfers):
            raise ValueError("Duplicate supplied transfer events")
        result["supplied_transfer_evidence"] = {
            "events": len(transfers), "granted_events": sum(row["board_disposition"] == "Granted" for row in transfers),
            "events_with_roster_license": sum(row["license_number"] in licenses for row in transfers),
            "events_with_pledge": sum(bool(row.get("related_pledge")) for row in transfers),
            "scope": "Counts supplied reviewed events only; not a census of all historical transfers or completed sales.",
        }
    if owners is not None:
        for owner in owners:
            if owner.get("holder_id") not in known_ids or not owner.get("evidence") or not owner.get("relationship_type"):
                raise ValueError("Owner mapping requires known holder_id, relationship_type and evidence")
        result["supplied_owner_evidence"] = {
            "mappings": len(owners), "holders_with_any_mapping": len({owner["holder_id"] for owner in owners}),
            "relationship_types": dict(Counter(owner["relationship_type"] for owner in owners)),
            "scope": "Includes supplied evidence mappings by relationship type. Registered agents, managers, lenders and brand affiliations do not establish common control or PE ownership.",
        }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("inventory")
    build.add_argument("--roster", type=Path, required=True)
    build.add_argument("--as-of", required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--prior-events", type=Path)
    for name in ("merge", "coverage", "validate"):
        child = commands.add_parser(name)
        child.add_argument("--queue", type=Path, required=True)
        child.add_argument("--output", type=Path, required=True)
        if name == "merge":
            child.add_argument("--events", type=Path, required=True)
        if name == "coverage":
            child.add_argument("--transfers", type=Path)
            child.add_argument("--owners", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            out = args.output_dir
            if (out / "ucc-queue.json").exists():
                raise ValueError("Inventory would replace an existing queue; use a fresh output directory to preserve live progress")
            summary, rows, queue = inventory(args.roster, args.as_of)
            if args.prior_events:
                queue = merge_events(queue, load_events(args.prior_events))
            validate_queue(queue)
            out.mkdir(parents=True, exist_ok=True)
            save(out / "inventory-summary.json", summary)
            save(out / "inventory-rows.json", rows)
            write_csv(out / "inventory-rows.csv", rows)
            save(out / "ucc-queue.json", queue)
            flat = [{"holder_id": h["holder_id"], "business_name": h["business_name"], "holder_key": h["holder_key"],
                     "license_numbers": h["license_numbers"], "dbas": h["dbas"], "scope_classes": h["scope_classes"],
                     "query": h["query_proposal"]["query"], "current_state": h["searches"]["current"]["state"],
                     "lapsed_state": h["searches"]["lapsed"]["state"]} for h in queue["holders"]]
            write_csv(out / "ucc-queue.csv", flat)
            result = coverage(queue)
            save(out / "ucc-queue-coverage.json", result)
        else:
            queue = load(args.queue)
            if args.command == "merge":
                result = merge_events(queue, load_events(args.events))
                validate_queue(result)
            elif args.command == "validate":
                result = validate_queue(queue)
            else:
                result = coverage(queue, load(args.transfers) if args.transfers else None,
                                  load(args.owners) if args.owners else None)
            save(args.output, result)
        print(json.dumps(result if args.command != "merge" else coverage(result), indent=2))
        return 0
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
