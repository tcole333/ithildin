#!/usr/bin/env python3
"""Build an offline original-filing review queue from saved Boston UCC evidence.

No browser, network, search-log or investigation writes. A filing family is not
a loan. Exact normalized names prioritize candidates; they do not prove identity.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

try:
    from tools.boston_license_review import normalized_holder, proposed_query
    from tools.boston_ucc_cua_bridge import COLUMNS, validate_observation
    from tools.output_util import add_output_args, write_output
except ImportError:
    from boston_license_review import normalized_holder, proposed_query
    from boston_ucc_cua_bridge import COLUMNS, validate_observation
    from output_util import add_output_args, write_output


LIMITATIONS = [
    "Original filing families, party occurrences and loans are different grains; no loan count or outstanding balance is computed.",
    "Current and lapsed are search scopes, not active/inactive debt conclusions. Continuation and termination events remain separately visible.",
    "Exact normalized legal-name equality is a candidate-priority rule, not identity verification. Corporate endings are retained; suffix changes and successors need evidence.",
    "Index rows disclose city/state, not full street addresses. Preserve history debtor addresses separately from license premises; different mailing addresses do not disprove identity.",
    "Formation jurisdiction is not established by a Boston license, MA mailing address or UCC party corporation-type label. Resolve organization type and formation jurisdiction before calling a nationwide lien search complete.",
    "Organization-name searches do not cover all former legal names, aliases, trade names or predecessor/successor entities. A DBA alone is not proof of debtor identity.",
    "The original query tool supports search-individual, but the roster organization-mode queue does not establish individual-debtor coverage. Resolve person-name components before using that mode.",
    "A PDF URL, page count or download is not evidence that all pages were reviewed. Prior visual-review notes are preserved without certifying every attachment complete.",
]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def original_number(row: dict) -> str | None:
    value = str(row.get("original_filing_number") or "")
    if value.isdigit():
        return value
    # Never turn an amendment number into an invented original.
    if re.match(r"^UCC-1\b", row.get("filing_type", "")):
        value = str(row.get("filing_number") or "")
        return value if value.isdigit() else None
    return None


def name_assessment(name: str, holder: dict) -> dict:
    key = normalized_holder(name)
    variants = holder.get("name_variants", []) + [holder["business_name"]]
    exact = key and key in {normalized_holder(v) for v in variants}
    suffix = key and normalized_holder(proposed_query(name)) in {
        normalized_holder(proposed_query(v)) for v in variants
    }
    category = "exact_normalized_legal_name" if exact else (
        "legal_ending_variant_requires_evidence" if suffix else "other_name_requires_review"
    )
    return {"category": category, "score": 100 if exact else 50 if suffix else 20,
            "identity_verified": False}


def attachment_state(review: dict) -> str:
    note = " ".join(str(review.get(k, "")) for k in ("pdf_review", "pdf_verification_note", "collateral_note"))
    note += " " + " ".join(review.get("notes", []))
    if re.search(r"not (?:separately )?opened", note, re.I):
        return "not_opened"
    if re.search(r"\bunread\b|not (?:separately )?read", note, re.I):
        return "unread_opening_unknown"
    if re.search(r"both pages visually read|complete original one-page|one-page original PDF was visually inspected", note, re.I):
        return "complete_original_pdf_as_reported"
    if re.search(r"pages 2[–-]3 visually reviewed", note, re.I):
        return "partial_original_pdf_as_reported"
    docs = review.get("documents", [])
    if (review.get("pdf_visually_verified") is True
            or review.get("pdf_visually_inspected") is True
            or any(d.get("pdf_visually_inspected") is True for d in docs)
            or re.search(r"visually reviewed|visually inspected|visually read", note, re.I)):
        return "visual_review_reported_completeness_unverified"
    if (review.get("pdf_visually_verified") is False
            or review.get("pdf_visually_inspected") is False
            or any(d.get("pdf_visually_inspected") is False for d in docs)):
        return "not_visually_inspected_opening_unknown"
    return "listed_review_unknown" if review.get("pdf_url") or docs else "unknown"


class Builder:
    def __init__(self, queue_path: Path):
        self.manifest = []
        self.errors = []
        self.queue = self.read(queue_path)
        self.holders = {h["holder_id"]: h for h in self.queue["holders"]}
        self.license_holders = {}
        for holder in self.holders.values():
            for number in holder["license_numbers"]:
                self.license_holders.setdefault(number, []).append(holder["holder_id"])
        self.observations = {}
        self.families = {}
        self.unresolved = []
        self.sample_status = {}

    def read(self, path: Path):
        raw = path.read_bytes()
        self.manifest.append({"path": str(path.resolve()),
                              "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        return json.loads(raw)

    def family(self, number: str) -> dict:
        if not str(number).isdigit():
            raise ValueError("Original filing number must be numeric")
        return self.families.setdefault(number, {
            "original_filing_number": number, "citation": f"MA-UCC:{number}",
            "candidates": {}, "index_occurrences": [], "history_reviews": [],
            "history_captures": [], "observed_history_urls": [], "decisions": [],
        })

    def candidate(self, family: dict, holder_id: str) -> dict:
        holder = self.holders[holder_id]
        return family["candidates"].setdefault(holder_id, {
            "holder_id": holder_id, "business_name": holder["business_name"],
            "license_numbers": holder["license_numbers"], "dbas": holder.get("dbas", []),
            "roster_premises": holder.get("premises", []), "debtor_names": [],
            "debtor_history_addresses": [], "name_assessments": [],
            "relationship": "unverified_candidate", "provenance": [],
        })

    def debtor(self, family: dict, holder_id: str, name: str | None, address=None):
        item = self.candidate(family, holder_id)
        if name and name not in item["debtor_names"]:
            item["debtor_names"].append(name)
            item["name_assessments"].append({"name": name, **name_assessment(name, self.holders[holder_id])})
        if address and address not in item["debtor_history_addresses"]:
            item["debtor_history_addresses"].append(address)
        return item

    def observation(self, event: dict, source: dict):
        holder_id = event["holder_id"]
        if holder_id not in self.holders:
            raise ValueError("Unknown holder_id")
        rows = event.get("occurrences", [])
        signature = {k: event.get(k) for k in (
            "holder_id", "scope", "query", "reported_count", "retrieved_at"
        )}
        signature["occurrences"] = rows
        key = digest(signature)
        if key in self.observations:
            self.observations[key]["provenance"].append(source)
            return
        self.observations[key] = {
            **signature, "observation_id": key, "state": event.get("state", "unknown"),
            "truncated": event.get("truncated"), "returned_count": event.get("returned_count", len(rows)),
            "occurrence_rows_supplied": "occurrences" in event, "captured_occurrence_rows": len(rows),
            "source_url": event.get("source_url"), "provenance": [source],
            "capture_method": event.get("capture_method"),
            "source_record_file": event.get("source_file"),
            "source_record_file_sha256": event.get("source_file_sha256"),
        }
        for i, row in enumerate(rows):
            if not isinstance(row, dict) or not all(k in row for k in COLUMNS):
                self.unresolved.append({"observation_id": key, "row_index": i, "raw": row,
                                        "reason": "missing_index_columns"})
                continue
            number = original_number(row)
            if number is None:
                self.unresolved.append({"observation_id": key, "row_index": i, "raw": row,
                                        "reason": "original_filing_number_unresolved"})
                continue
            family = self.family(number)
            self.debtor(family, holder_id, row["name"])
            family["index_occurrences"].append({
                **row, "holder_id": holder_id, "scope": event.get("scope"),
                "observation_id": key, "row_index": i,
            })
            if row.get("history_url") and row["history_url"] not in family["observed_history_urls"]:
                family["observed_history_urls"].append(row["history_url"])

    def queue_events(self):
        for holder in self.holders.values():
            for scope, search in holder.get("searches", {}).items():
                for i, event in enumerate(search.get("attempts", [])):
                    self.observation(event, {"path": self.manifest[0]["path"],
                                            "pointer": f"holders/{holder['holder_id']}/searches/{scope}/attempts/{i}"})

    def raw_observations(self, directory: Path):
        # Snapshot the filenames once; re-run to include an ongoing index run.
        for path in sorted(directory.glob("*.json")):
            try:
                value = self.read(path)
                rows = value.get("results") if isinstance(value, dict) else value
                if not isinstance(rows, list):
                    rows = [value]
                for i, row in enumerate(rows):
                    try:
                        event = validate_observation(row, self.holders)
                        self.observation(event, {"path": str(path.resolve()), "pointer": f"results/{i}"})
                    except (ValueError, KeyError, TypeError) as exc:
                        self.errors.append({"path": str(path), "record": i, "error": str(exc), "raw": row})
            except (ValueError, OSError) as exc:
                self.errors.append({"path": str(path), "error": str(exc)})

    def samples(self, path: Path):
        data = self.read(path)
        rows = data.get("results") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError("--samples requires normalized follow-up sample-results.json")
        for i, row in enumerate(rows):
            linked = self.license_holders.get(row["license_number"], [])
            if len(linked) != 1:
                self.errors.append({"path": str(path), "record": i,
                                    "error": "Sample license maps to zero or multiple roster holder groups"})
                continue
            holder_id = linked[0]
            provenance = {"path": str(path.resolve()), "pointer": f"results/{i}"}
            self.sample_status[holder_id] = {
                "sample_id": row["sample_id"], "search_complete": row.get("search_complete"),
                "reported_count": row.get("current_index_result_count"),
                "complete_history_review_as_reported": row.get("complete_history_review"),
                "category": row.get("category"), "provenance": provenance,
            }
            numbers = row.get("original_filing_numbers", []) + row.get("candidate_original_filing_numbers", [])
            for number in set(numbers):
                item = self.candidate(self.family(number), holder_id)
                item["provenance"].append(provenance)
                if row.get("matches_exact_legal_holder") is True:
                    item["relationship"] = "prior_sample_matched_holder_as_reported"
                # Do not replace a successor relationship with exact-name equality.
                if row.get("successor_ucc_record_found"):
                    item["relationship"] = "documented_successor_as_reported"
                    item["successor_evidence"] = row.get("corporate_chain_evidence")
            for j, review in enumerate(row.get("filings_reviewed", [])):
                number = review.get("original_filing_number", review.get("filing_number"))
                if number not in numbers:
                    self.errors.append({"path": str(path), "record": i,
                                        "error": "Reviewed number is absent from declared original/candidate numbers",
                                        "raw": review})
                    continue
                family = self.family(number)
                item = self.debtor(family, holder_id, review.get("debtor_as_recorded"),
                                   review.get("debtor_business_address"))
                if row.get("successor_ucc_record_found"):
                    item["relationship"] = "documented_successor_as_reported"
                    item["successor_evidence"] = row.get("corporate_chain_evidence")
                family["history_reviews"].append({
                    "holder_id": holder_id, "history_state": "reviewed_prior_sample",
                    "attachments_state": attachment_state(review),
                    "provenance": {**provenance, "pointer": f"results/{i}/filings_reviewed/{j}"},
                    "record": review,
                })
                if review.get("history_url"):
                    family["observed_history_urls"].append(review["history_url"])

    def tool_index(self, holder_id: str, path: Path):
        """Import saved query_massachusetts_ucc search output with explicit binding."""
        data = self.read(path)
        if data.get("query", {}).get("command") not in {"search-org", "search-individual"}:
            raise ValueError("--tool-index needs a saved query-tool search response")
        if not isinstance(data.get("results"), list):
            raise ValueError("Saved query-tool response lacks results")
        self.observation({"holder_id": holder_id, "scope": data["scope"],
                          "query": data["query"], "reported_count": data["reported_count"],
                          "retrieved_at": data.get("retrieved_at"), "occurrences": data["results"],
                          "state": "partial" if data.get("truncated") else "complete",
                          "truncated": data.get("truncated"), "source_url": data.get("source_url")},
                         {"path": str(path.resolve()), "pointer": "results"})

    def tool_history(self, path: Path):
        """Capture availability is separate from an analyst's review completion."""
        data = self.read(path)
        entries = data.get("filings", [])
        originals = [f for f in entries if f.get("action") == "InitialFiling"
                     or re.match(r"^UCC-1\b", f.get("filing_type", ""))]
        if data.get("query", {}).get("command") != "filing" or len(originals) != 1:
            raise ValueError("Saved filing response must identify one original")
        family = self.family(originals[0]["filing_number"])
        family["history_captures"].append({"provenance": {"path": str(path.resolve())},
                                           "review_state": "captured_not_review_certified", "record": data})
        if data.get("history_url"):
            family["observed_history_urls"].append(data["history_url"])
        for entry in entries:
            for debtor in entry.get("debtors", []):
                name = debtor.get("name", "")
                for holder in self.holders.values():
                    if name_assessment(name, holder)["category"] == "exact_normalized_legal_name":
                        self.debtor(family, holder["holder_id"], name, debtor.get("address_lines"))

    def index_supplement(self, path: Path):
        """Import the detailed mixed sample's complete rows, including namesakes."""
        data = self.read(path)
        linked = self.license_holders.get(data["selection"]["license_num"], [])
        if len(linked) != 1:
            raise ValueError("Index supplement needs an unambiguous roster license")
        rows = []
        for row in data.get("index_rows", []):
            rows.append({"name_type": "DEBTOR", **row})
        self.observation({"holder_id": linked[0], "scope": "current", "query": data.get("query"),
                          "reported_count": data["reported_count"], "occurrences": rows,
                          "retrieved_at": data.get("recorded_at"),
                          "state": "complete" if data.get("all_index_rows_retrieved") else "partial",
                          "source_url": data.get("search_url"),
                          "truncated": not data.get("all_index_rows_retrieved")},
                         {"path": str(path.resolve()), "pointer": "index_rows"})

    def decisions(self, path: Path):
        for row in self.read(path):
            if row.get("decision") not in {"confirmed_holder", "rejected_false_positive", "successor_candidate"}:
                raise ValueError("Unsupported holder decision")
            if not row.get("evidence") or not row.get("note"):
                raise ValueError("Holder decisions require evidence and a note")
            family = self.family(row["original_filing_number"])
            self.candidate(family, row["holder_id"])["relationship"] = row["decision"]
            family["decisions"].append(row)

    def result(self) -> dict:
        families = []
        for family in self.families.values():
            family["candidates"] = list(family["candidates"].values())
            family["observed_history_urls"] = sorted(set(family["observed_history_urls"]))
            family["lookup"] = {"filing_number": family["original_filing_number"],
                                 "observed_scopes": sorted({r["scope"] for r in family["index_occurrences"] if r.get("scope")}),
                                 "note": "Use the official filing-number UI or supported filing command if a preserved session URL expires; do not construct a history URL."}
            reviews = family["history_reviews"]
            family["history_state"] = "reviewed_prior_sample" if reviews else "not_started"
            family["history_capture_state"] = "available" if reviews or family["history_captures"] else "not_captured"
            family["attachments_state"] = (
                "prior_notes_require_completeness_check" if reviews else "not_started"
            )
            family["observed_actions"] = sorted({r.get("filing_type", "") for r in family["index_occurrences"]} | {
                str(e.get("action", e.get("type", "")))
                for r in reviews for e in r["record"].get("history_events", [])
            } | {str(e.get("action", "")) for c in family["history_captures"] for e in c["record"]["filings"]})
            document_tasks = {}
            for row in family["index_occurrences"]:
                document_tasks.setdefault(row["filing_number"], {"filing_number": row["filing_number"],
                    "role": "original" if row["filing_number"] == family["original_filing_number"] else "amendment",
                    "state": "locate_and_review_document", "observed_urls": [], "review_evidence": []})
            for capture in family["history_captures"]:
                for entry in capture["record"]["filings"]:
                    number = entry["filing_number"]
                    task = document_tasks.setdefault(number, {"filing_number": number,
                        "role": "original" if number == family["original_filing_number"] else "amendment",
                        "state": "captured_document_list_review_unverified", "observed_urls": [], "review_evidence": []})
                    for document in entry.get("documents", []):
                        url = document.get("viewer_url")
                        if url and url not in task["observed_urls"]:
                            task["observed_urls"].append(url)
            for review in reviews:
                record = review["record"]
                events = [{"filing_number": family["original_filing_number"], "pdf_url": record.get("pdf_url")}]
                events += record.get("history_events", [])
                for event in events:
                    number = event.get("filing_number")
                    if not number:
                        continue
                    task = document_tasks.setdefault(number, {"filing_number": number,
                        "role": "original" if number == family["original_filing_number"] else "amendment",
                        "state": "locate_and_review_document", "observed_urls": [], "review_evidence": []})
                    if event.get("pdf_url") and event["pdf_url"] not in task["observed_urls"]:
                        task["observed_urls"].append(event["pdf_url"])
                    if number == family["original_filing_number"]:
                        task["state"] = review["attachments_state"]
                        task["review_evidence"].append(review["provenance"])
            family["document_review_tasks"] = list(document_tasks.values())
            reviewed_numbers = {str(e.get("filing_number")) for r in reviews
                                for e in r["record"].get("history_events", [])}
            if reviews:
                reviewed_numbers.add(family["original_filing_number"])
            unseen = {r["filing_number"] for r in family["index_occurrences"]} - reviewed_numbers
            family["index_filing_numbers_not_in_prior_history_review"] = sorted(unseen)
            if reviews and unseen:
                family["history_state"] = "prior_review_new_index_entries_pending"
            rejected = bool(family["candidates"]) and all(c["relationship"] == "rejected_false_positive" for c in family["candidates"])
            documents_pending = not document_tasks or any(t["state"] != "complete_original_pdf_as_reported" for t in document_tasks.values())
            pending = [] if rejected else (["history_and_party_review"] if not reviews else [])
            if reviews and unseen and not rejected:
                pending.append("review_history_entries_not_in_prior_sample")
            if documents_pending and not rejected:
                pending.append("attachment_inventory_and_remaining_pages_review")
            if not family["candidates"]:
                pending.append("identify_roster_holder_or_reject_capture")
            if not rejected and any(c["relationship"] not in {"confirmed_holder", "prior_sample_matched_holder_as_reported"}
                                    for c in family["candidates"]):
                pending.insert(0, "resolve_holder_identity")
            family["pending_actions"] = pending
            score = max((a["score"] for c in family["candidates"] for a in c["name_assessments"]), default=10)
            if any(c["relationship"] in {"confirmed_holder", "prior_sample_matched_holder_as_reported"}
                   for c in family["candidates"]):
                score = max(score, 100)
            family["priority_score"] = 0 if rejected else score + (20 if not reviews else 0)
            family["priority_explanation"] = "Legal-name candidates first, then unreviewed histories; no lender/loan/active-lien inference."
            families.append(family)
        families.sort(key=lambda f: (-f["priority_score"], -int(f["original_filing_number"])))
        holder_coverage = []
        for holder in self.holders.values():
            observed = [o for o in self.observations.values() if o["holder_id"] == holder["holder_id"]]
            scopes = {}
            for scope in ("current", "lapsed"):
                observations = [o for o in observed if o["scope"] == scope]
                scopes[scope] = {"queue_state": holder.get("searches", {}).get(scope, {}).get("state", "pending"),
                                 "observed_states": dict(Counter(o["state"] for o in observations)),
                                 "observation_ids": [o["observation_id"] for o in observations]}
            holder_coverage.append({
                "holder_id": holder["holder_id"], "business_name": holder["business_name"],
                "index_scopes": scopes, "prior_sample": self.sample_status.get(holder["holder_id"]),
                "formation_jurisdiction": "not_assessed_by_this_queue",
                "aliases_and_former_names": "not_exhaustively_assessed",
                "individual_mode": "not_established", "name_mode_review_reasons": holder.get("name_mode_review_reasons", []),
            })
        return {"schema_version": 1, "built_at": datetime.now(timezone.utc).isoformat(),
                "as_of": self.queue.get("as_of"), "offline": True,
                "summary": {"roster_holder_groups": len(self.holders), "index_observations": len(self.observations),
                            "saved_occurrences_across_observations": sum(len(o["occurrences"]) for o in self.observations.values()),
                            "original_filing_families": len(families),
                            "families_with_exact_normalized_name_candidate": sum(any(a["category"] == "exact_normalized_legal_name" for c in f["candidates"] for a in c["name_assessments"]) for f in families),
                            "families_all_candidates_rejected": sum(bool(f["candidates"]) and all(c["relationship"] == "rejected_false_positive" for c in f["candidates"]) for f in families),
                            "originals_with_prior_history_review": sum(bool(f["history_reviews"]) for f in families),
                            "originals_without_prior_history_review": sum(not f["history_reviews"] for f in families),
                            "prior_original_pdf_review_states": dict(Counter(r["attachments_state"] for f in families for r in f["history_reviews"])),
                            "originals_with_pending_actions": sum(bool(f["pending_actions"]) for f in families),
                            "unparsed_sources_or_records": len(self.errors), "unresolved_index_rows": len(self.unresolved)},
                "limitations": LIMITATIONS, "source_manifest": self.manifest,
                "filings": families, "holder_coverage": holder_coverage,
                "index_observations": list(self.observations.values()),
                "unresolved_index_rows": self.unresolved, "unparsed": self.errors}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Rebuild from local snapshots without changing source files")
    build.add_argument("--queue", type=Path, required=True)
    build.add_argument("--observations", type=Path, required=True)
    build.add_argument("--samples", type=Path, required=True)
    build.add_argument("--index-supplement", type=Path, action="append", default=[])
    build.add_argument("--tool-index", action="append", default=[], metavar="HOLDER_ID=FILE")
    build.add_argument("--tool-history", type=Path, action="append", default=[])
    build.add_argument("--decisions", type=Path)
    add_output_args(build)
    args = parser.parse_args(argv)
    try:
        builder = Builder(args.queue)
        builder.queue_events()
        builder.raw_observations(args.observations)
        builder.samples(args.samples)
        for path in args.index_supplement:
            builder.index_supplement(path)
        for binding in args.tool_index:
            holder_id, separator, path = binding.partition("=")
            if not separator:
                raise ValueError("--tool-index requires HOLDER_ID=FILE")
            builder.tool_index(holder_id, Path(path))
        for path in args.tool_history:
            builder.tool_history(path)
        if args.decisions:
            builder.decisions(args.decisions)
        result = builder.result()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Cannot build filing-review queue: {exc}\n")
    if not write_output(result, args, summary="Offline filing review", result_count=len(result["filings"])):
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
