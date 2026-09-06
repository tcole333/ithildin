"""Assemble a dated, evidence-aware license review without inferring missing results."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.boston_license_review import coverage, merge_events, save  # noqa: E402

BASE = Path(__file__).resolve().parent
REPORT = BASE.parent


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def source(label, url):
    return {"label": label, "url": url}


def date_window_label(start, end):
    return f"{start} through {end}" if start and end else "Source window not supplied"


def source_manifest(index_path):
    """Count source content once while retaining every archive URL observation."""
    records = read_json(index_path)
    if not isinstance(records, list):
        raise ValueError(f"Source index must be an array: {index_path}")
    by_id = {}
    documents = {}
    for record in records:
        if record["source_id"] in by_id:
            raise ValueError(f"Duplicate source ID in {index_path}: {record['source_id']}")
        relative = record.get("pdf_path") or record.get("html_path")
        if not relative:
            raise ValueError(f"Source has no saved PDF/HTML path: {record['source_id']}")
        saved_path = index_path.parent / relative
        digest = hashlib.sha256(saved_path.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"Source document hash changed: {record['source_id']}")
        prepared = {**record, "resolved_source_file": str(saved_path.resolve())}
        by_id[record["source_id"]] = prepared
        prior = documents.get(digest)
        if prior and prior.get("page_count") is not None and record.get("page_count") is not None and prior["page_count"] != record["page_count"]:
            raise ValueError(f"Conflicting page counts for identical source bytes: {record['source_id']}")
        documents.setdefault(digest, prepared)
    return {
        "source_index_file": str(index_path.resolve()),
        "source_index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "observed_source_entries": len(records),
        "documents": len(documents),
        "pdf_documents": sum(bool(record.get("pdf_path")) for record in documents.values()),
        "pdf_pages": sum(record.get("page_count") or 0 for record in documents.values() if record.get("pdf_path")),
        "unpaginated_html_documents": [record["source_id"] for record in documents.values() if not record.get("pdf_path")],
        "source_records": list(by_id.values()),
        "by_id": by_id,
        "by_sha256": documents,
    }


def attach_window_provenance(events, window, manifest):
    stamped = []
    for event in events:
        document = manifest["by_id"].get(event["source_id"])
        if document is None:
            raise ValueError(f"Event source ID absent from source window: {event['event_id']}")
        if event.get("source_sha256") and event["source_sha256"] != document["sha256"]:
            raise ValueError(f"Event/document source hashes differ: {event['event_id']}")
        stamped.append({
            **event,
            "source_window_id": window["window_id"],
            "source_window_start": window["window_start"],
            "source_window_end": window["window_end"],
            "source_window_label": window["window_label"],
            "source_document_sha256": document["sha256"],
            "source_document_file": document["resolved_source_file"],
            "source_index_file": manifest["source_index_file"],
            "source_index_sha256": manifest["source_index_sha256"],
            "source_window_coverage_file": window["source_coverage_file"],
            "source_window_coverage_sha256": window["source_coverage_sha256"],
            "source_window_readiness_file": window.get("source_readiness_file"),
            "source_window_readiness_sha256": window.get("source_readiness_sha256"),
        })
    return stamped


def effective_event(search):
    identity = search.get("latest_effective_event_sha256")
    return next((attempt for attempt in reversed(search["attempts"])
                 if attempt.get("event_sha256") == identity), None) or next(
        (attempt for attempt in reversed(search["attempts"])
         if attempt["state"] == search["state"]), {})


def reviewed_affiliation(match):
    if "count_as_group_affiliated" in match:
        decision = match["count_as_group_affiliated"]
        if type(decision) is not bool:
            raise ValueError("count_as_group_affiliated must be a boolean")
        return decision
    status = match.get("match_status", "").lower().strip()
    return bool(status) and status != "unresolved" and not any(
        word in status for word in ("candidate", "pending", "not reviewed", "unverified"))


def canonical_license(value):
    if value is None or not str(value).strip():
        return None
    match = re.fullmatch(r"LB[\s-]*(\d+)", str(value).strip(), re.I)
    if not match:
        raise ValueError(f"Unrecognized Boston license identifier: {value!r}")
    return "LB-" + match[1]


def event_label(event):
    action = event["action_subtype"]
    disposition = event["disposition"]
    labels = {
        "transfer_application_disposition": "Transfer application",
        "pledge_application_disposition": "Pledge application",
        "pledge_release_acknowledgment": "Pledge release",
        "transfer_revocation_notice": "Notice of intent to revoke prior transfer",
    }
    if action not in labels:
        raise ValueError(f"Unrecognized board action subtype: {action}")
    return f"{labels[action]} {disposition}"


def normalize_board_events(raw_events, inventory, source_path):
    by_license = defaultdict(list)
    for row in inventory:
        by_license[canonical_license(row["license_num"])].append(row)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    normalized = []
    seen = set()
    for original in raw_events:
        if original["event_id"] in seen:
            raise ValueError("Duplicate board event_id")
        seen.add(original["event_id"])
        numbers = {canonical_license(original.get(field)) for field in ("license_num", "license_number")}
        numbers.discard(None)
        if len(numbers) > 1:
            raise ValueError(f"Conflicting identifiers in {original['event_id']}")
        number = next(iter(numbers), None)
        application = original["action_subtype"] in {
            "transfer_application_disposition", "pledge_application_disposition"}
        expected_type = "license_transfer" if original["action_subtype"].startswith("transfer_") else "license_pledge"
        if original["event_type"] != expected_type:
            raise ValueError(f"Event type conflicts with action subtype in {original['event_id']}")
        if original["board_granted_application"] != (application and original["disposition"] == "granted"):
            raise ValueError(f"Grant flag conflicts with action/disposition in {original['event_id']}")
        if original.get("completed_sale_verified"):
            raise ValueError("Decision corpus unexpectedly asserts a completed sale; review primary proof before importing")
        matches = by_license.get(number, []) if number else []
        locator = original["source_url"]
        if original.get("page_start") is not None:
            locator = locator.split("#", 1)[0] + "#page=" + str(original["page_start"])
        normalized.append({
            **original,
            "license_num_as_received": original.get("license_num"),
            "license_number_as_received": original.get("license_number"),
            "license_num": number, "license_number": number,
            "event_label": event_label(original), "source_locator_url": locator,
            "normalization_source_file": str(source_path.resolve()),
            "normalization_source_sha256": source_hash,
            "roster_join_status": ("matched_exact_license_id" if matches else
                                   "missing_source_license_id" if number is None else "license_id_absent_from_roster"),
            "roster_source_row_ids": [row["source_row_id"] for row in matches],
            "roster_holder_names": sorted({row["business_name"] for row in matches}),
            "roster_scope_classes": sorted({row["scope_class"] for row in matches}),
            "in_review_inventory": any(row["queue_included"] for row in matches),
            "roster_join_note": "Exact license-number join to all source rows; does not establish transaction closing, licensee continuity, or current debt.",
        })
    return sorted(normalized, key=lambda event: (event["date"], event["source_id"], str(event["item_number"]), event["event_id"]))


def board_counts(events):
    transfer_applications = [event for event in events if event["action_subtype"] == "transfer_application_disposition"]
    pledge_applications = [event for event in events if event["action_subtype"] == "pledge_application_disposition"]
    return {
        "event_count": len(events),
        "transfer_count": len(transfer_applications),
        "transfer_application_disposition_count": len(transfer_applications),
        "transfer_granted_count": sum(event["disposition"] == "granted" for event in transfer_applications),
        "pledge_count": len(pledge_applications),
        "pledge_application_disposition_count": len(pledge_applications),
        "pledge_granted_count": sum(event["disposition"] == "granted" for event in pledge_applications),
        "pledge_release_count": sum(event["action_subtype"] == "pledge_release_acknowledgment" for event in events),
        "transfer_revocation_notice_count": sum(event["action_subtype"] == "transfer_revocation_notice" for event in events),
    }


def normalize_ownership_interest_events(raw_events, inventory, source_path, *, notices=False):
    """Preserve ownership decisions separately from transfers and operator mappings."""
    by_license = defaultdict(list)
    for row in inventory:
        by_license[canonical_license(row["license_num"])].append(row)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    labels = {
        "ownership_application_disposition": "Ownership-interest application",
        "ownership_management_record_update_notice": "Ownership/management record-update notice",
        "ownership_management_participation_notice": "Ownership/management participation notice",
        "informational_ownership_hearing": "Informational ownership hearing",
        "required_application_notice": "Required ownership application notice",
        "ownership_information_hearing": "Ownership information hearing",
        "ownership_information_notice": "Ownership information notice",
        "conditional_license_revocation_directive": "Conditional license-revocation directive",
        "new_license_application_ownership_clarification": "New-license ownership clarification",
        "license_cancellation": "License cancellation notice",
        "ownership_clarification_notice": "Ownership clarification notice",
        "cancellation_after_alleged_unauthorized_interest_change": "Cancellation after alleged unauthorized interest change",
    }
    normalized = []
    seen = set()
    for original in raw_events:
        if original["event_id"] in seen:
            raise ValueError("Duplicate ownership-interest event_id")
        seen.add(original["event_id"])
        subtype = original["event_subtype"]
        application = subtype == "ownership_application_disposition"
        if subtype not in labels or original["event_type"] != "ownership_interest" or application == notices:
            raise ValueError(f"Unexpected ownership-interest event type in {original['event_id']}")
        if original["board_granted_application"] != (application and original["disposition"] == "granted"):
            raise ValueError(f"Ownership grant flag conflicts with disposition in {original['event_id']}")
        if original.get("equity_change_completion_verified"):
            raise ValueError("Decision corpus unexpectedly asserts completed equity change; review primary proof before importing")
        numbers = {canonical_license(original.get(field)) for field in ("license_num", "license_number")}
        numbers.discard(None)
        if len(numbers) > 1:
            raise ValueError(f"Conflicting ownership license identifiers in {original['event_id']}")
        number = next(iter(numbers), None)
        matches = by_license.get(number, []) if number else []
        locator = original["source_url"]
        if original.get("page_start") is not None:
            locator = locator.split("#", 1)[0] + "#page=" + str(original["page_start"])
        normalized.append({
            **original,
            "license_num_as_received": original.get("license_num"),
            "license_number_as_received": original.get("license_number"),
            "license_num": number, "license_number": number,
            "event_label": f"{labels[subtype]} — {original['disposition']}",
            "source_locator_url": locator,
            "normalization_source_file": str(source_path.resolve()),
            "normalization_source_sha256": source_hash,
            "roster_join_status": ("matched_exact_license_id" if matches else
                                   "missing_source_license_id" if number is None else "license_id_absent_from_roster"),
            "roster_source_row_ids": [row["source_row_id"] for row in matches],
            "roster_holder_names": sorted({row["business_name"] for row in matches}),
            "roster_scope_classes": sorted({row["scope_class"] for row in matches}),
            "in_review_inventory": any(row["queue_included"] for row in matches),
            "roster_join_note": "Exact license-number join to all source rows; does not establish completed equity change, named owners, percentages, current control, or licensee continuity.",
        })
    return sorted(normalized, key=lambda event: (event["date"], event["source_id"], str(event["item_number"]), event["event_id"]))


def ownership_interest_counts(events):
    return {
        "application_events": len(events),
        "unique_license_ids": len({event["license_num"] for event in events if event["license_num"]}),
        "application_outcomes": dict(Counter(event["disposition"] for event in events)),
        "explicit_entity_conversion_items": sum(event["entity_conversion_explicit"] for event in events),
        "items_with_named_equity_parties": sum(bool(event.get("parties_before") or event.get("parties_after")) for event in events),
        "action_occurrences_not_distinct_transactions": dict(Counter(action for event in events for action in event["actions"])),
    }


def normalize_history_observations(raw_events, inventory, source_path, bucket):
    """Join notices and unresolved proposals without promoting them to approvals."""
    by_license = defaultdict(list)
    for row in inventory:
        by_license[canonical_license(row["license_num"])].append(row)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    normalized = []
    seen = set()
    for original in raw_events:
        if original["event_id"] in seen:
            raise ValueError(f"Duplicate {bucket} event ID")
        seen.add(original["event_id"])
        if original.get("board_granted_application") or original.get("completed_sale_verified"):
            raise ValueError(f"Non-decision observation asserts approval/completion: {original['event_id']}")
        numbers = {canonical_license(original.get(field)) for field in ("license_num", "license_number")}
        numbers.discard(None)
        if len(numbers) > 1:
            raise ValueError(f"Conflicting observation identifiers: {original['event_id']}")
        number = next(iter(numbers), None)
        matches = by_license.get(number, []) if number else []
        locator = original["source_url"]
        if original.get("page_start") is not None:
            locator = locator.split("#", 1)[0] + "#page=" + str(original["page_start"])
        normalized.append({
            **original,
            "license_num_as_received": original.get("license_num"),
            "license_number_as_received": original.get("license_number"),
            "license_num": number, "license_number": number,
            "observation_bucket": bucket,
            "event_label": ("Proposed action / outcome unresolved" if bucket == "proposal_or_unresolved_outcome"
                            else "Separate source notice"),
            "source_locator_url": locator,
            "normalization_source_file": str(source_path.resolve()), "normalization_source_sha256": source_hash,
            "roster_join_status": ("matched_exact_license_id" if matches else
                                   "missing_source_license_id" if number is None else "license_id_absent_from_roster"),
            "roster_source_row_ids": [row["source_row_id"] for row in matches],
            "roster_holder_names": sorted({row["business_name"] for row in matches}),
            "roster_scope_classes": sorted({row["scope_class"] for row in matches}),
            "in_review_inventory": any(row["queue_included"] for row in matches),
            "roster_join_note": "Exact license-number join only. This observation is excluded from application-disposition and approval counts; no completed sale, current debt or equity ownership is established.",
        })
    return normalized


def load_history_window(folder, window_id, inventory, *, require_qa=False):
    coverage_path = folder / "coverage.json"
    raw_coverage = read_json(coverage_path)
    if not isinstance(raw_coverage, dict):
        raise ValueError(f"Missing source-window coverage: {coverage_path}")
    if require_qa and raw_coverage.get("integration_status") != "qa_complete":
        raise ValueError("Prior source window has not passed consolidated QA")
    readiness_path = folder / "readiness.json"
    readiness = read_json(readiness_path, {})
    if require_qa:
        if readiness.get("integration_status") != "qa_complete" or not readiness.get("artifacts"):
            raise ValueError("Prior source window lacks a completed readiness manifest")
        required = {"coverage.json", "source-index.json", "events.json", "ownership-interest-events.json",
                    "ownership-interest-notices.json", "notices.json", "proposed-events.json"}
        if not required.issubset(readiness["artifacts"]):
            raise ValueError("Readiness manifest omits a required decision/observation artifact")
        for relative, expected_hash in readiness["artifacts"].items():
            artifact = (folder / relative).resolve()
            if not artifact.is_relative_to(folder.resolve()):
                raise ValueError("Readiness artifact escapes its source window")
            if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected_hash:
                raise ValueError(f"Finalized source-window artifact hash changed: {relative}")
    date_range = raw_coverage.get("archive_date_range", [None, None])
    window_start = raw_coverage.get("window_start") or date_range[0]
    window_end = raw_coverage.get("window_end") or date_range[1]
    if not window_start or not window_end:
        raise ValueError("Source window has no explicit bounded date range")
    manifest = source_manifest(folder / "source-index.json")
    window = {
        "window_id": window_id,
        "window_start": window_start, "window_end": window_end,
        "window_label": date_window_label(window_start, window_end),
        "window_date_basis": "published corpus window bounds" if raw_coverage.get("window_start") else "observed archive date range",
        "source_readiness_file": str(readiness_path.resolve()) if readiness else None,
        "source_readiness_sha256": hashlib.sha256(readiness_path.read_bytes()).hexdigest() if readiness else None,
        "source_coverage_file": str(coverage_path.resolve()),
        "source_coverage_relative_file": str(coverage_path.relative_to(BASE)),
        "source_coverage_sha256": hashlib.sha256(coverage_path.read_bytes()).hexdigest(),
        "coverage_as_published_in_corpus": raw_coverage,
        **{key: value for key, value in manifest.items() if key not in {"by_id", "by_sha256"}},
    }
    board_path = folder / "events.json"
    ownership_path = folder / "ownership-interest-events.json"
    ownership_notice_path = folder / "ownership-interest-notices.json"
    notice_path = folder / "notices.json"
    proposal_path = folder / "proposed-events.json"
    board = normalize_board_events(read_json(board_path), inventory, board_path)
    ownership_events = normalize_ownership_interest_events(read_json(ownership_path), inventory, ownership_path)
    ownership_notices = (normalize_ownership_interest_events(read_json(ownership_notice_path), inventory,
                                                           ownership_notice_path, notices=True)
                         if ownership_notice_path.exists() else [])
    notices = (normalize_history_observations(read_json(notice_path), inventory, notice_path, "separate_source_notice")
               if notice_path.exists() else [])
    proposals = (normalize_history_observations(read_json(proposal_path), inventory, proposal_path, "proposal_or_unresolved_outcome")
                 if proposal_path.exists() else [])
    ownership_coverage_path = folder / "ownership-interest-coverage.json"
    ownership_coverage = read_json(ownership_coverage_path, {})
    if ownership_coverage:
        window["ownership_source_coverage"] = {"source_file": str(ownership_coverage_path.resolve()),
                                               "source_file_sha256": hashlib.sha256(ownership_coverage_path.read_bytes()).hexdigest(),
                                               "coverage": ownership_coverage}
    stamped = {key: attach_window_provenance(values, window, manifest)
               for key, values in (("board_events", board), ("ownership_events", ownership_events),
                                   ("ownership_notices", ownership_notices), ("notices", notices), ("proposals", proposals))}
    window.update({
        "board_counts": board_counts(stamped["board_events"]),
        "board_application_dispositions": {kind: dict(Counter(event["disposition"] for event in board if event["action_subtype"] == kind))
                                           for kind in ("transfer_application_disposition", "pledge_application_disposition")},
        "board_events_joined_to_review_inventory": sum(event["in_review_inventory"] for event in board),
        "ownership_application_counts": ownership_interest_counts(ownership_events),
        "alcohol_ownership_application_counts": ownership_interest_counts([event for event in ownership_events if event["license_scope"] == "explicit_alcohol"]),
        "ownership_application_events_joined_to_review_inventory": sum(event["in_review_inventory"] for event in ownership_events),
        "ownership_notice_count": len(ownership_notices),
        "separate_source_notice_count": len(notices),
        "proposal_or_unresolved_outcome_count": len(proposals),
        "count_note": "Unique document counts use source-file hashes; URL observations, dated decisions, notices and unresolved proposals remain separate. This is an archive window, not lifetime license history.",
    })
    return {"summary": window, "manifest": manifest, **stamped}


def load_history_windows(inventory):
    folder = BASE / "transfer-corpus"
    windows = [load_history_window(folder, "2024-2026", inventory)]
    prior_coverage = read_json(folder / "prior-2024" / "coverage.json", {})
    if prior_coverage.get("integration_status") == "qa_complete":
        windows.insert(0, load_history_window(folder / "prior-2024", "2020-2023", inventory, require_qa=True))
    seen = set()
    physical_items = {}
    for window in windows:
        for bucket in ("board_events", "ownership_events", "ownership_notices", "notices", "proposals"):
            for event in window[bucket]:
                if event["event_id"] in seen:
                    raise ValueError(f"Duplicate event across windows or decision/observation buckets: {event['event_id']}")
                seen.add(event["event_id"])
                physical_key = (event["source_document_sha256"], event.get("page_start"), str(event.get("item_number")),
                                event.get("action_subtype") or event.get("event_subtype") or event.get("event_type"))
                previous = physical_items.get(physical_key)
                if previous and previous["source_window_id"] != event["source_window_id"]:
                    raise ValueError(f"Repeated physical source item across windows requires reviewed exclusion: {previous['event_id']} / {event['event_id']}")
                physical_items.setdefault(physical_key, event)
    return windows


def combine_history_coverage(windows):
    summaries = [window["summary"] for window in windows]
    documents = {}
    for window in windows:
        for digest, record in window["manifest"]["by_sha256"].items():
            existing = documents.get(digest)
            if existing and existing.get("page_count") != record.get("page_count"):
                raise ValueError("Identical source bytes have different page counts across windows")
            documents.setdefault(digest, record)
    archive_urls = sorted({summary["coverage_as_published_in_corpus"].get("archive_url") or
                           summary["coverage_as_published_in_corpus"].get("archive_index_url")
                           for summary in summaries} - {None})
    intersections = [
        {"left_window_id": left["summary"]["window_id"], "right_window_id": right["summary"]["window_id"],
         "shared_source_sha256": sorted(set(left["manifest"]["by_sha256"]) & set(right["manifest"]["by_sha256"]))}
        for index, left in enumerate(windows) for right in windows[index + 1:]
    ]
    return {
        "window_start": min(summary["window_start"] for summary in summaries),
        "window_end": max(summary["window_end"] for summary in summaries),
        "window_label": "; ".join(summary["window_label"] for summary in summaries),
        "source_windows": summaries,
        "cross_window_source_hash_intersections": intersections,
        "cross_window_duplicate_event_check": "Passed: no repeated source hash/page/item/action across windows. Duplicate event IDs are also rejected.",
        "archive_url": archive_urls[0] if len(archive_urls) == 1 else None,
        "archive_urls": archive_urls,
        "documents": len(documents),
        "observed_source_entries": sum(summary["observed_source_entries"] for summary in summaries),
        "pdf_documents": sum(bool(record.get("pdf_path")) for record in documents.values()),
        "pdf_pages": sum(record.get("page_count") or 0 for record in documents.values() if record.get("pdf_path")),
        "unpaginated_html_documents": [record["source_id"] for record in documents.values() if not record.get("pdf_path")],
        "separate_status_notices": sum(len(window["notices"]) for window in windows),
        "proposal_or_unresolved_outcome_count": sum(len(window["proposals"]) for window in windows),
        "scope_limit": "Combined finalized archive windows, preserving their separate manifests and counts. Unique document totals deduplicate source-file hashes across windows. This is not complete lifetime license history or proof of completed sales, current debt, or equity control.",
    }


def combined_ownership_coverage(windows, coverage_summary, events, notices):
    alcohol = [event for event in events if event["license_scope"] == "explicit_alcohol"]
    return {
        "scope": "Separate ownership-interest decisions from the finalized archive windows; notices remain outside application counts.",
        "documents_reviewed": coverage_summary["documents"],
        "pdf_pages": coverage_summary["pdf_pages"],
        "unpaginated_html_documents": coverage_summary["unpaginated_html_documents"],
        "application_events": len(events),
        "notices_separate": len(notices),
        "application_outcomes": dict(Counter(event["disposition"] for event in events)),
        "applications_by_year": dict(Counter(event["date"][:4] for event in events)),
        "application_license_scopes": dict(Counter(event["license_scope"] for event in events)),
        "alcohol_application_outcomes": dict(Counter(event["disposition"] for event in alcohol)),
        "unique_license_ids_all_applications": len({event["license_num"] for event in events if event["license_num"]}),
        "unique_alcohol_license_ids": len({event["license_num"] for event in alcohol if event["license_num"]}),
        "alcohol_items_with_named_equity_parties": sum(bool(event.get("parties_before") or event.get("parties_after")) for event in alcohol),
        "alcohol_items_with_explicit_owner_percentages": None,
        "owner_percentage_count_note": "No combined zero/nonzero assertion is inferred from absent fields. Consult explicit per-window audit evidence and the individual records.",
        "explicit_entity_conversion_items": sum(event["entity_conversion_explicit"] for event in events),
        "action_occurrences_not_distinct_transactions": dict(Counter(action for event in events for action in event["actions"])),
        "source_windows": [{"window_id": window["summary"]["window_id"],
                            "window_label": window["summary"]["window_label"],
                            "source_coverage_file": window["summary"]["source_coverage_file"],
                            "source_coverage_sha256": window["summary"]["source_coverage_sha256"],
                            "application_counts": window["summary"]["ownership_application_counts"],
                            "alcohol_application_counts": window["summary"]["alcohol_ownership_application_counts"],
                            "notice_count": window["summary"]["ownership_notice_count"],
                            "ownership_source_coverage": window["summary"].get("ownership_source_coverage")}
                           for window in windows],
    }


def load_judgment_notices(inventory):
    """Keep historical notice observations outside decision and debt totals."""
    path = BASE / "judgment-attachment-review" / "notices.json"
    ledger = read_json(path)
    if ledger is None:
        return defaultdict(list), [], None
    rows = {row["source_row_id"]: row for row in inventory}
    by_license = defaultdict(list)
    outside = []
    seen = set()
    joined_observations = 0
    for notice in ledger["notices"]:
        if notice["notice_id"] in seen:
            raise ValueError("Duplicate supplemental judgment/attachment observation")
        seen.add(notice["notice_id"])
        if any(notice.get(field) for field in ("current_status_verified", "completed_sale_verified", "loan_or_sale_price_established")):
            raise ValueError("Supplemental notice unexpectedly asserts verified current debt or sale")
        for kind in ("pdf", "text"):
            saved = (BASE / notice["source"][f"{kind}_path"]).resolve()
            if not saved.is_relative_to(BASE.resolve()) or hashlib.sha256(saved.read_bytes()).hexdigest() != notice["source"][f"{kind}_sha256"]:
                raise ValueError("Supplemental notice source hash/path changed")
        matched_ids = set()
        explicit_ids = {canonical_license(number) for number in notice["source_license_ids"]}
        for match in notice["roster_matches"]:
            row = rows.get(match["source_row_id"])
            number = canonical_license(match["license_num"])
            if (row is None or number not in explicit_ids or canonical_license(row["license_num"]) != number
                    or row["holder_id"] != match["holder_id"] or row["raw_row_sha256"] != match["raw_row_sha256"]
                    or bool(row["queue_included"]) != match["in_main_review"]):
                raise ValueError("Supplemental notice exact roster lineage changed")
            if match["in_main_review"]:
                matched_ids.add(number)
        for number in sorted(matched_ids):
            by_license[number].append(notice)
        if matched_ids:
            joined_observations += 1
        else:
            outside.append(notice)
    counts = ledger["counts"]
    if (len(seen) != counts["encumbrance_or_discharge_observations"]
            or joined_observations != counts["observations_joined_to_main_review"]
            or len(by_license) != counts["distinct_license_ids_joined_to_main_review"]):
        raise ValueError("Supplemental notice counts disagree with exact joins")
    summary = {"source_file": str(path.resolve()), "source_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "report_file": "judgment-attachment-review/README.md", "scope": ledger["scope"], "counts": counts,
               "integration_note": "Separate historical observations; amounts are not summed, and repeated matter IDs remain visible. Source-party obligations are not attributed to current roster holders."}
    return by_license, outside, summary


def reconciled_history_counts(reviews):
    documents = [document for review in reviews for document in review["document_reviews"]]
    return {
        "original_histories_text_reviewed": len(reviews),
        "saved_history_entries_reviewed": sum(review["captured_history_entry_count"] for review in reviews),
        "listed_pdfs": len(documents),
        "original_pdfs_with_prior_complete_visual_review_reconciled": sum(
            document["role"] == "original" and document["pdf_review_state"] == "complete_original_visual_review_reconciled"
            for document in documents),
        "pending_original_pdfs": sum(document["role"] == "original" and document["pending"] for document in documents),
        "pending_amendment_pdfs": sum(document["role"] == "amendment" and document["pending"] for document in documents),
    }


def load_reconciled_histories(inventory):
    path = BASE / "filing-review-reconciliation.json"
    ledger = read_json(path, {})
    queue_path = BASE / "filing-review-queue.json"
    filing_queue = read_json(queue_path, {})
    candidate_keys = {(candidate["holder_id"], filing["original_filing_number"])
                      for filing in filing_queue.get("filings", []) for candidate in filing["candidates"]}
    roster_keys = {(row["holder_id"], canonical_license(row["license_num"])) for row in inventory if row["queue_included"]}
    seen = set()
    by_holder = defaultdict(dict)
    for review in ledger.get("reviews", []):
        key = (review["holder_id"], review["original_filing_number"])
        if key in seen or key not in candidate_keys:
            raise ValueError(f"Duplicate or unmatched reconciled history holder/original key: {key}")
        seen.add(key)
        if (key[0], canonical_license(review["roster_license_number"])) not in roster_keys:
            raise ValueError(f"Reconciled history does not match its explicit roster holder/license: {key}")
        if review["captured_history_entry_count"] != len(review["events"]) or not review["all_saved_entries_read"]:
            raise ValueError(f"Reconciled history entry scope is inconsistent: {key}")
        if hashlib.sha256(Path(review["source"]["path"]).read_bytes()).hexdigest() != review["source"]["sha256"]:
            raise ValueError(f"Reconciled source changed: {key}")
        by_holder[key[0]][key[1]] = review
    reviews = list(review for originals in by_holder.values() for review in originals.values())
    summary = {
        **reconciled_history_counts(reviews),
        "holder_groups": len(by_holder),
        "license_numbers": len({review["roster_license_number"] for review in reviews}),
        "source_file": str(path.resolve()),
        "source_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
        "source_scope": ledger.get("scope"),
        "review_created_at": ledger.get("created_at"),
        "base_filing_queue_file": str(queue_path.resolve()),
        "base_filing_queue_sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest() if queue_path.exists() else None,
        "base_queue_imported_prior_history_review_count_unchanged": filing_queue.get("summary", {}).get("originals_with_prior_history_review"),
        "base_queue_modified": False,
        "join_note": "Exact holder ID plus original filing number in the saved filing queue; explicit roster-license binding is also checked. This preserves the stated candidate identity and continuity caveats, not independent identity certification.",
        "count_note": "Separate analyst reconciliation of saved history text. It neither refreshes source/index coverage nor completes all PDFs, party-amendment effects, loan balances or current-lien checks. The base queue's imported prior-review counter remains separate.",
    }
    return by_holder, summary


def load_source_label_cohorts(inventory):
    path = BASE / "license-class-cohorts.json"
    cohort = read_json(path)
    if not cohort:
        raise ValueError("Build license-class-cohorts.json before assembling the review")
    for key, filename in (("inventory", "inventory-rows.json"), ("original_csv", "source-licenses.csv"),
                          ("generator", "build_license_class_cohorts.py")):
        provenance = cohort["provenance"][key]
        if provenance["path"] != filename or hashlib.sha256((BASE / filename).read_bytes()).hexdigest() != provenance["sha256"]:
            raise ValueError(f"Source-label cohort provenance changed: {key}")
    grouped = defaultdict(list)
    for row in inventory:
        if row["queue_included"]:
            grouped[row["license_num"]].append(row)
    by_license = {}
    for item in cohort["licenses"]:
        number = item["license_num"]
        if canonical_license(number) != number or number in by_license or number not in grouped:
            raise ValueError(f"Duplicate or unmatched source-label license ID: {number}")
        rows = grouped[number]
        if (item["source_license_types"] != sorted({row["license_type"] for row in rows})
                or item["source_license_categories"] != sorted({row["license_category"] for row in rows})
                or item["source_row_ids"] != sorted(row["source_row_id"] for row in rows)
                or {item["scope_class"]} != {row["scope_class"] for row in rows}
                or item["license_type"] != rows[0]["license_type"]):
            raise ValueError(f"Source-label cohort differs from inventory: {number}")
        expected_evidence = {row["source_row_id"]: (row["source_record_number"], row["raw_row_sha256"]) for row in rows}
        supplied_evidence = {row["source_row_id"]: (row["source_record_number"], row["raw_row_sha256"])
                             for row in item["source_row_evidence"]}
        if expected_evidence != supplied_evidence:
            raise ValueError(f"Source-label row provenance differs from inventory: {number}")
        by_license[number] = item
    if set(by_license) != set(grouped) or len(by_license) != cohort["counts"]["review_license_ids"]:
        raise ValueError("Source-label cohort mapping does not exhaust the review inventory")
    projection = [{key: item[key] for key in ("license_num", "license_type", "scope_class", "source_row_ids")}
                  for _, item in sorted(by_license.items())]
    projection_hash = hashlib.sha256(json.dumps(projection, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
    if projection_hash != cohort["provenance"]["review_validation"]["canonical_projection_sha256"]:
        raise ValueError("Source-label cohort review projection hash differs")
    summary = {key: value for key, value in cohort.items() if key != "licenses"}
    summary.update({"source_file": str(path.resolve()), "source_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "exact_license_id_join_complete": True})
    return by_license, summary


def build():
    queue = read_json(BASE / "ucc-queue.json")
    events = []
    for path in sorted((BASE / "ucc-cua").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
    if events:
        queue = merge_events(queue, events)
    blocker_path = BASE / "ucc-access-block.json"
    blocker = read_json(blocker_path, {})
    if blocker:
        blocker = {**blocker, "source_file": str(blocker_path.resolve()),
                   "source_file_sha256": hashlib.sha256(blocker_path.read_bytes()).hexdigest()}
    collection_path = BASE / "ucc-collection-status.json"
    collection_record = read_json(collection_path, {})
    if collection_record:
        collection_record = {**collection_record, "source_file": str(collection_path.resolve()),
                             "source_file_sha256": hashlib.sha256(collection_path.read_bytes()).hexdigest()}
    latest_collection_status = collection_record.get("status", blocker.get("status", "in_progress"))
    collection_blocked = latest_collection_status == "source_access_blocked"
    supported_access_pending = latest_collection_status == "paused_pending_supported_bulk_access"
    collection_paused = supported_access_pending or collection_blocked or bool(collection_record.get("collection_paused"))
    holders = {h["holder_id"]: h for h in queue["holders"]}
    inventory = read_json(BASE / "inventory-rows.json")
    reconciled_by_holder, reconciliation_summary = load_reconciled_histories(inventory)
    cohort_by_license, cohort_summary = load_source_label_cohorts(inventory)
    grouped = defaultdict(list)
    for row in inventory:
        if row["queue_included"]:
            grouped[row["license_num"]].append(row)
    ownership = read_json(REPORT / "ownership" / "owner-mappings.json", {"groups": []})
    assessment_by_license = {}
    for assessment in ownership.get("assessments", []):
        number = canonical_license(assessment["license_num"])
        if number in assessment_by_license:
            raise ValueError(f"Duplicate ownership assessment for {number}")
        assessment_by_license[number] = assessment
    owner_by_license = {}
    for group in ownership["groups"]:
        for match in group.get("matches", []):
            if not reviewed_affiliation(match):
                continue
            number = match["license_num"]
            if number in owner_by_license:
                raise ValueError(f"Conflicting reviewed owner/operator assignment for {number}")
            owner_by_license[number] = (group, match)
    history_windows = load_history_windows(inventory)
    corpus_coverage = combine_history_coverage(history_windows)
    history_window_label = corpus_coverage["window_label"]
    transfer_events = [event for window in history_windows for event in window["board_events"]]
    ownership_interest_events = [event for window in history_windows for event in window["ownership_events"]]
    ownership_interest_notices = [event for window in history_windows for event in window["ownership_notices"]]
    history_notices = [event for window in history_windows for event in window["notices"]]
    history_proposals = [event for window in history_windows for event in window["proposals"]]
    judgment_by_license, judgment_outside, judgment_summary = load_judgment_notices(inventory)
    ownership_interest_coverage = combined_ownership_coverage(
        history_windows, corpus_coverage, ownership_interest_events, ownership_interest_notices)
    for filename, records in (
        ("review-board-events-combined.json", transfer_events),
        ("review-ownership-interest-events-combined.json", ownership_interest_events),
        ("review-ownership-interest-notices-combined.json", ownership_interest_notices),
        ("review-history-notices-combined.json", history_notices),
        ("review-history-proposals-combined.json", history_proposals),
    ):
        save(BASE / filename, records)
    transfer_by_license = defaultdict(list)
    ownership_interest_by_license = defaultdict(list)
    ownership_notices_by_license = defaultdict(list)
    history_notices_by_license = defaultdict(list)
    history_proposals_by_license = defaultdict(list)
    for ledger, by_license in ((transfer_events, transfer_by_license),
                              (ownership_interest_events, ownership_interest_by_license),
                              (ownership_interest_notices, ownership_notices_by_license),
                              (history_notices, history_notices_by_license),
                              (history_proposals, history_proposals_by_license)):
        for event in ledger:
            if event.get("license_num"):
                by_license[event["license_num"]].append(event)
    alcohol_ownership_events = [event for event in ownership_interest_events if event["license_scope"] == "explicit_alcohol"]
    joined_ownership_events = [event for event in ownership_interest_events if event["roster_join_status"] == "matched_exact_license_id"]
    review_ownership_events = [event for event in ownership_interest_events if event["in_review_inventory"]]
    all_roster_ids = {canonical_license(row["license_num"]) for row in inventory}
    finance_marker_ids = {canonical_license(row["license_num"]) for row in inventory if row.get("financing_any_field_marker")}
    approved_pledge_ids = {event["license_num"] for event in transfer_events
                           if event["action_subtype"] == "pledge_application_disposition"
                           and event["disposition"] == "granted" and event["license_num"] in all_roster_ids}
    release_ids = {event["license_num"] for event in transfer_events
                   if event["action_subtype"] == "pledge_release_acknowledgment" and event["license_num"] in all_roster_ids}
    revocation_notice_ids = {event["license_num"] for event in transfer_events
                             if event["action_subtype"] == "transfer_revocation_notice" and event["license_num"] in all_roster_ids}
    sample = read_json(REPORT / "follow-up" / "sample-results.json", {"results": []})
    sample_by_license = {}
    for result in sample["results"]:
        for key in ("license_number", "license_num", "license_id"):
            if result.get(key):
                sample_by_license[result[key]] = result
    # Explicitly scoped, previously reviewed positive collateral observations.
    collateral = {
        "LB-98892": "UCC explicitly identifies this Boston license; 2023 continuation reviewed",
        "LB-98889": "UCC identifies ABCC liquor license; Boston-ID crosswalk pending",
        "LB-101973": "UCC identifies historical ABCC license 89702-PK-0116; continuity to current Boston license/address not independently established",
    }
    licenses = []
    for number, rows in sorted(grouped.items()):
        row = rows[0]
        cohort = cohort_by_license[number]
        holder = holders[row["holder_id"]]
        current = holder["searches"]["current"]
        lapsed = holder["searches"]["lapsed"]
        latest = effective_event(current)
        latest_lapsed = effective_event(lapsed)
        count = latest.get("reported_count")
        label = current["state"]
        if label == "complete":
            label = "Index complete — no query matches" if count == 0 else "Index complete — candidates found"
        else:
            label = label.capitalize()
        notes = []
        if len(rows) > 1:
            notes.append(f"{len(rows)} roster rows share this license number; source lineage retained.")
        if row["scope_class"] != "alcohol_license":
            notes.append("Boundary category shown separately: " + row["scope_class"])
        if any(r["active_label_with_expired_date"] for r in rows):
            notes.append("Roster says Active but expiration predates the research date.")
        if holder.get("name_mode_review_reasons"):
            notes.append("Name-mode review needed: an organization-name search does not exclude separately indexed individual or partnership-member debt.")
        if row.get("comments"):
            notes.append("Roster comment: " + row["comments"])
        if latest.get("match_note"):
            notes.append(latest["match_note"])
        notes.extend(sample_by_license.get(number, {}).get("notes", []))
        sources = [source("Boston source roster", "https://data.boston.gov/dataset/licensing-board-licenses")]
        if latest.get("source_url"):
            sources.append(source("UCC search source (query recorded in evidence)", latest["source_url"]))
        if latest_lapsed.get("source_url"):
            sources.append(source("Lapsed UCC search source (query recorded in evidence)", latest_lapsed["source_url"]))
        for filing in sample_by_license.get(number, {}).get("filings_reviewed", []):
            if filing.get("pdf_url"):
                sources.append(source("Reviewed UCC " + filing["filing_number"], filing["pdf_url"]))
        reconciled_reviews = [review for review in reconciled_by_holder.get(row["holder_id"], {}).values()
                              if canonical_license(review["roster_license_number"]) == number]
        reconciliation_counts = reconciled_history_counts(reconciled_reviews)
        for review in reconciled_reviews:
            if review["source"].get("history_url"):
                sources.append(source("Saved reconciled UCC history " + review["original_filing_number"], review["source"]["history_url"]))
            for document in review["document_reviews"]:
                if document.get("viewer_url"):
                    sources.append(source(f"UCC document {document['filing_number']} — {document['pdf_review_state']}", document["viewer_url"]))
        if number == "LB-101973":
            evidence = read_json(REPORT / "evidence" / "ucc" / "sk-201960725880-cua-observed.json", {})
            for filing in evidence.get("filings", []):
                for document in filing.get("documents", []):
                    sources.append(source("Historical Bauer UCC " + filing["filing_number"], document["viewer_url"]))
            notes.append("Bauer UCC debtor premises are 330 Newbury St; roster premises are 255 Newbury St. Historical ABCC/Boston license identifier continuity remains unverified.")
        group, match = owner_by_license.get(number, ({}, {}))
        assessment = assessment_by_license.get(number, {})
        sources.extend(source(s.get("title", group.get("group_name", "Ownership source")), s["url"])
                       for s in group.get("sources", []) if s.get("url"))
        if match.get("url"):
            sources.append(source("Venue / license crosswalk source", match["url"]))
        if match.get("note"):
            notes.append(match["note"])
        if match.get("match_note") and match["match_note"] not in notes:
            notes.append(match["match_note"])
        if match.get("corporate_officer_note"):
            notes.append(match["corporate_officer_note"])
        registry_candidate = match.get("corporate_registry_candidate", {})
        if registry_candidate.get("opencorporates_url"):
            sources.append(source("Candidate corporate-number crosswalk (OpenCorporates snapshot)", registry_candidate["opencorporates_url"]))
        for officer in match.get("corporate_officer_observations", []):
            if officer.get("opencorporates_url"):
                sources.append(source(f"Corporate role snapshot: {officer['name']} / {officer['position']}", officer["opencorporates_url"]))
        if group.get("capital_note"):
            notes.append(group["capital_note"])
        for field in ("assessment", "note"):
            if assessment.get(field):
                notes.append(assessment[field])
        sources.extend(source(s.get("title", "Ownership assessment source"), s["url"])
                       for s in assessment.get("sources", []) if s.get("url"))
        if match.get("equity_ownership_disclaimed_by_group") or group.get("equity_ownership_disclaimed_by_group"):
            notes.append("The group disclaims equity ownership; the documented relationship is portfolio affiliation.")
        board_events = transfer_by_license[number]
        transfers = [event for event in board_events if event["event_type"] == "license_transfer"]
        pledges = [event for event in board_events if event["event_type"] == "license_pledge"]
        counts = board_counts(board_events)
        interest_events = ownership_interest_by_license[number]
        interest_notices = ownership_notices_by_license[number]
        notices = history_notices_by_license[number]
        proposals = history_proposals_by_license[number]
        judgment_notices = judgment_by_license[number]
        for notice in judgment_notices:
            sources.append(source(f"{notice['source_date']}: {notice['notice_type']}", notice["source"]["page_url"]))
        interest_label = ("; ".join(sorted({event["event_label"] for event in interest_events}))
                          if interest_events else f"No ownership-interest application matched in collected archive windows: {history_window_label}")
        interest_notice_label = ("; ".join(sorted({event["event_label"] for event in interest_notices}))
                                 if interest_notices else f"No ownership-interest notice matched in collected archive windows: {history_window_label}")
        for event in board_events + interest_events + interest_notices + notices + proposals:
            sources.append(source(f"{event['date']}: {event['event_label']}", event["source_locator_url"]))
        # A missing match in bounded source windows is not a no-transfer determination.
        transfer_label = f"No transfer action matched in collected archive windows: {history_window_label}"
        if transfers:
            transfer_label = "; ".join(sorted({event["event_label"] for event in transfers}))
        pledge_label = "; ".join(sorted({event["event_label"] for event in pledges})) if pledges else f"No pledge action matched in collected archive windows: {history_window_label}"
        licenses.append({
            "license_num": number, "legal_holder": row["business_name"],
            "dba": row["dba_name"], "address": row["address"],
            "license_type": row["license_type"], "scope_class": row["scope_class"],
            "source_label_segment": cohort["source_label_segment"],
            "source_label_family": cohort["source_label_family"],
            "source_license_types": cohort["source_license_types"],
            "source_license_categories": cohort["source_license_categories"],
            "license_type_literal_flags": cohort["license_type_literal_flags"],
            "restriction_label_state": cohort["restriction_label_state"],
            "source_label_classification_status": cohort["classification_status"],
            "source_label_classification_notes": cohort["classification_notes"],
            "source_label_evidence": cohort,
            "roster_status": row["status"], "expires": row["expires"],
            "location_comments": row.get("location_comments", ""), "premises_description": row.get("descpremadd", ""),
            "finance_keyword_marker_any_field": number in finance_marker_ids,
            "finance_marker_field_names": sorted({field for source_row in rows for field in source_row.get("financing_marker_fields", {})}),
            "historical_granted_pledge_in_window": number in approved_pledge_ids,
            "holder_id": row["holder_id"], "source_row_ids": [r["source_row_id"] for r in rows],
            "owner_group": group.get("group_name", "Unresolved"),
            "capital_category": group.get("capital_category", assessment.get("capital_category", "Unresolved")),
            "documented_pe_group_affiliation": group.get("pe_backing") == "documented" and reviewed_affiliation(match),
            "ownership_status": match.get("match_status", assessment.get("state", "Not reviewed")),
            "ownership_reviewed": bool(match) or assessment.get("state") == "reviewed_unresolved",
            "ownership_match_evidence": match or None,
            "ownership_assessment_evidence": assessment or None,
            "relationship": match.get("relationship", assessment.get("relationship", "Unresolved")),
            "scale_band": group.get("scale_band", assessment.get("scale_band", "Unresolved")),
            "equity_ownership_disclaimed_by_group": match.get("equity_ownership_disclaimed_by_group", group.get("equity_ownership_disclaimed_by_group")),
            "corporate_registry_candidate": registry_candidate or None,
            "corporate_officer_observations": match.get("corporate_officer_observations", []),
            "corporate_officer_evidence": match.get("corporate_officer_evidence"),
            "corporate_officer_note": match.get("corporate_officer_note"),
            "current_ucc_status": label, "current_ucc_occurrences": count,
            "lapsed_ucc_status": lapsed["state"].capitalize(),
            "lapsed_ucc_occurrences": latest_lapsed.get("reported_count"),
            "ucc_query_evidence": {scope: {key: event.get(key) for key in (
                "query", "reported_count", "returned_count", "truncated", "retrieved_at",
                "source_file", "source_file_sha256", "source_url", "capture_method")}
                for scope, event in (("current", latest), ("lapsed", latest_lapsed))},
            "name_mode_review_reasons": holder.get("name_mode_review_reasons", []),
            "collateral_status": collateral.get(number, "Collateral review incomplete"),
            "reconciled_history_reviews": reconciled_reviews,
            "reconciled_history_count": reconciliation_counts["original_histories_text_reviewed"],
            "reconciled_history_entry_count": reconciliation_counts["saved_history_entries_reviewed"],
            "reconciled_history_prior_complete_original_pdf_count": reconciliation_counts["original_pdfs_with_prior_complete_visual_review_reconciled"],
            "reconciled_history_pending_original_pdf_count": reconciliation_counts["pending_original_pdfs"],
            "reconciled_history_pending_amendment_pdf_count": reconciliation_counts["pending_amendment_pdfs"],
            "reconciled_history_status": ("Saved history text reconciled; document and currentness gaps remain" if reconciled_reviews else "No separate saved-history reconciliation recorded"),
            "transfer_status": transfer_label, "pledge_status": pledge_label,
            **counts, "board_events": board_events, "transfer_events": transfers, "pledge_events": pledges,
            "ownership_interest_events": interest_events,
            "ownership_interest_count": len(interest_events),
            "ownership_interest_granted_count": sum(event["board_granted_application"] for event in interest_events),
            "ownership_interest_entity_conversion_count": sum(event["entity_conversion_explicit"] for event in interest_events),
            "ownership_interest_status": interest_label,
            "ownership_interest_notices": interest_notices,
            "ownership_interest_notice_count": len(interest_notices),
            "ownership_interest_notice_status": interest_notice_label,
            "history_source_notices": notices,
            "history_source_notice_count": len(notices),
            "history_proposals_or_unresolved_outcomes": proposals,
            "history_proposal_or_unresolved_outcome_count": len(proposals),
            "judgment_attachment_notices": judgment_notices,
            "judgment_attachment_observation_count": len(judgment_notices),
            "sources": list({s["url"]: s for s in sources}.values()), "notes": notes,
        })
    mapped = Counter(r["owner_group"] for r in licenses if r["owner_group"] != "Unresolved")
    group_rows = [{**{k: v for k, v in g.items() if k not in {"matches", "candidates"}},
                   "reviewed_affiliation_license_count": mapped[g["group_name"]],
                   "documented_pe_group_affiliation_license_count": sum(
                       row["owner_group"] == g["group_name"] and row["documented_pe_group_affiliation"]
                       for row in licenses),
                   "count_note": "Reviewed operator/group affiliations, not necessarily common equity control."}
                  for g in ownership["groups"]]
    result = {
        "metadata": {
            "title": "Boston liquor licenses: ownership, transfers and UCC review",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "roster_research_date": "2026-09-03",
            "scope": "1,512 alcohol licenses plus 8 separately flagged BYOB/unclear-category records; all 3,610 source rows inventoried.",
            "status": ("Full-list UCC collection is paused pending supported bulk access under the published terms. One search form load succeeded without new debtor or document requests; result and document access remain unverified. Saved results are preserved and unsearched scopes remain pending."
                       if supported_access_pending else
                       "UCC data collection blocked by source access denial; saved results are preserved and unsearched scopes remain pending. The full inventory is not a completed lien or ownership review."
                       if collection_blocked else "Research in progress; full inventory is not a completed lien or ownership review."),
            "collection_status": "blocked" if collection_blocked else latest_collection_status,
            "collection_status_record": collection_record or None,
            "collection_blocker": (collection_record or blocker) if collection_blocked else None,
            "historical_access_denial": blocker or None,
            "collection_access_options_file": "access-options.md",
            "collection_access_inquiry_file": "ucc-access-inquiry-draft.md",
            "interpretation": "Current Massachusetts UCC index coverage is query-specific; filing histories, collateral PDFs, debtor jurisdiction and historic aliases need separate review. No query match does not mean debt-free.",
            "ownership_note": "Group affiliation, management, brand membership and equity ownership are distinct. Unresolved is not independent or non-PE.",
            "source_label_cohort_note": "License categories and flags describe exact source class labels. They do not establish legal transferability, acquisition route, price, operator identity, ownership or control; absent restriction wording does not mean unrestricted.",
            "ownership_interest_note": "Ownership-interest applications and corporate-form conversions are a separate bounded decision history. Local approval does not establish transaction completion, current ownership, or control. Named equity parties and percentages require explicit source evidence; officer and manager names are not substituted for owners. Notices are separate from applications.",
            "transfer_note": f"Collected archive windows ({history_window_label}) are a bounded history. Transfer/pledge counts mean application dispositions, including repeated decisions; acknowledgments are separate. Approval is not closing and later notices of intent to revoke are retained.",
        },
        "licenses": licenses, "groups": group_rows,
        "unmatched_board_events": [event for event in transfer_events if event["roster_join_status"] != "matched_exact_license_id"],
        "board_events_matched_only_to_excluded_roster": [event for event in transfer_events
                                                        if event["roster_join_status"] == "matched_exact_license_id" and not event["in_review_inventory"]],
        "unmatched_ownership_interest_events": [event for event in ownership_interest_events if event["roster_join_status"] != "matched_exact_license_id"],
        "ownership_interest_events_matched_only_to_excluded_roster": [event for event in joined_ownership_events if not event["in_review_inventory"]],
        "unmatched_ownership_interest_notices": [event for event in ownership_interest_notices if event["roster_join_status"] != "matched_exact_license_id"],
        "ownership_interest_notices_matched_only_to_excluded_roster": [event for event in ownership_interest_notices
                                                                    if event["roster_join_status"] == "matched_exact_license_id" and not event["in_review_inventory"]],
        "history_source_notices_outside_review_inventory": [event for event in history_notices if not event["in_review_inventory"]],
        "history_proposals_outside_review_inventory": [event for event in history_proposals if not event["in_review_inventory"]],
        "judgment_attachment_notices_outside_review_inventory": judgment_outside,
        "coverage": {**coverage(queue), "ucc_collection_blocked": collection_blocked,
                     "ucc_current_access_denial": collection_blocked,
                     "ucc_collection_paused": collection_paused,
                     "reconciled_history_review": reconciliation_summary,
                     "source_label_cohorts": cohort_summary,
                     "judgment_attachment_notice_review": judgment_summary,
                     "ownership_affiliations_mapped": sum(mapped.values()),
                     "ownership_reviewed_license_count": sum(row["ownership_reviewed"] for row in licenses),
                     "ownership_reviewed_unresolved_license_count": sum(row["ownership_reviewed"] and row["owner_group"] == "Unresolved" for row in licenses),
                     "documented_pe_group_affiliation_license_count": sum(r["documented_pe_group_affiliation"] for r in licenses),
                     "documented_pe_affiliated_group_count": sum(group["documented_pe_group_affiliation_license_count"] > 0 for group in group_rows),
                     "documented_pe_count_note": "Reviewed license affiliations to groups with documented PE backing; excludes candidate matches and is not a citywide PE estimate or certified license-holder equity count.",
                     "ownership_unresolved_license_count": sum(r["owner_group"] == "Unresolved" for r in licenses),
                     "licenses_with_collected_events": sum(bool(row["board_events"]) for row in licenses),
                     "licenses_with_transfer_application_dispositions": sum(row["transfer_count"] > 0 for row in licenses),
                     "licenses_with_pledge_application_dispositions": sum(row["pledge_count"] > 0 for row in licenses),
                     "licenses_with_ownership_interest_applications": sum(row["ownership_interest_count"] > 0 for row in licenses),
                     "licenses_with_ownership_interest_notices": sum(row["ownership_interest_notice_count"] > 0 for row in licenses),
                     "licenses_with_separate_source_notices": sum(row["history_source_notice_count"] > 0 for row in licenses),
                     "licenses_with_proposed_or_unresolved_history": sum(row["history_proposal_or_unresolved_outcome_count"] > 0 for row in licenses),
                     "ownership_interest_corpus": {
                         **ownership_interest_coverage,
                         "window_start": corpus_coverage.get("window_start"),
                         "window_end": corpus_coverage.get("window_end"),
                         "window_label": history_window_label,
                         "normalized_application_ledger": str((BASE / "review-ownership-interest-events-combined.json").resolve()),
                         "normalized_notice_ledger": str((BASE / "review-ownership-interest-notices-combined.json").resolve()),
                         "all_applications": ownership_interest_counts(ownership_interest_events),
                         "alcohol_applications": ownership_interest_counts(alcohol_ownership_events),
                         "applications_joined_to_all_roster": ownership_interest_counts(joined_ownership_events),
                         "applications_joined_to_review_inventory": ownership_interest_counts(review_ownership_events),
                         "alcohol_application_events": len(alcohol_ownership_events),
                         "application_roster_join_status_counts": dict(Counter(event["roster_join_status"] for event in ownership_interest_events)),
                         "alcohol_application_roster_join_status_counts": dict(Counter(event["roster_join_status"] for event in alcohol_ownership_events)),
                         "events_joined_to_review_inventory": len(review_ownership_events),
                         "unique_review_inventory_license_ids": len({event["license_num"] for event in review_ownership_events}),
                         "notices": {
                             "notice_events": len(ownership_interest_notices),
                             "license_scopes": dict(Counter(event.get("license_scope", "not_stated") for event in ownership_interest_notices)),
                             "outcomes": dict(Counter(event["disposition"] for event in ownership_interest_notices)),
                             "roster_join_status_counts": dict(Counter(event["roster_join_status"] for event in ownership_interest_notices)),
                             "events_joined_to_review_inventory": sum(event["in_review_inventory"] for event in ownership_interest_notices),
                             "count_note": "Informational, participation and required-application notices; not ownership application approvals or completed equity transactions.",
                         },
                         "count_note": "Applications are dated local dispositions, not distinct completed equity transactions or named-owner observations. Corporate-form conversions may recur for multiple licenses. All-roster joins include excluded non-alcohol rows; review-inventory matches remain separate. Exact IDs only; absent or omitted IDs are retained without inferred matches. This ledger does not change the separate transfer/pledge counters or current group-affiliation assignments.",
                     },
                     "board_corpus": {
                         **corpus_coverage,
                         "window_start": corpus_coverage.get("window_start"),
                         "window_end": corpus_coverage.get("window_end"),
                         "documents": corpus_coverage.get("documents"),
                         "archive_url": corpus_coverage.get("archive_url"),
                         "scope_limit": corpus_coverage.get("scope_limit"),
                         **board_counts(transfer_events),
                         "application_dispositions": {
                             kind: dict(Counter(event["disposition"] for event in transfer_events if event["action_subtype"] == kind))
                             for kind in ("transfer_application_disposition", "pledge_application_disposition")},
                         "roster_join_status_counts": dict(Counter(event["roster_join_status"] for event in transfer_events)),
                         "events_joined_to_review_inventory": sum(event["in_review_inventory"] for event in transfer_events),
                         "normalized_combined_ledger": str((BASE / "review-board-events-combined.json").resolve()),
                         "separate_notice_ledger": str((BASE / "review-history-notices-combined.json").resolve()),
                         "proposed_or_unresolved_ledger": str((BASE / "review-history-proposals-combined.json").resolve()),
                         "separate_status_notices_excluded_from_event_counts": corpus_coverage.get("separate_status_notices"),
                         "count_note": "Dated source actions, not distinct completed sales, distinct loans, or current liens. Missing identifiers are retained without inferred joins.",
                     },
                     "historical_pledge_roster_note_comparison": {
                         "unit": "Distinct license identifiers found in the supplied roster; roster inclusion does not verify current operation or licensee continuity.",
                         "window_start": corpus_coverage.get("window_start"), "window_end": corpus_coverage.get("window_end"),
                         "window_label": history_window_label,
                         "roster_license_ids_with_granted_pledge_history": len(approved_pledge_ids),
                         "with_financing_keyword_marker": len(approved_pledge_ids & finance_marker_ids),
                         "without_financing_keyword_marker": len(approved_pledge_ids - finance_marker_ids),
                         "checked_fields": ["comments", "location_comments", "descpremadd"],
                         "keyword_stems": ["pledge", "collateral", "lien", "loan"],
                         "with_marker_license_ids": sorted(approved_pledge_ids & finance_marker_ids),
                         "without_marker_license_ids": sorted(approved_pledge_ids - finance_marker_ids),
                         "roster_licenses_with_pledge_release_acknowledgments": sorted(release_ids),
                         "granted_pledge_and_release_history_license_ids": sorted(approved_pledge_ids & release_ids),
                         "roster_licenses_with_acknowledged_intent_to_revoke_transfer": sorted(revocation_notice_ids),
                         "interpretation": "Roster notes omit many documented historical local pledge approvals. Releases and notices of intent to revoke transfers remain separately labeled. Approved-pledge history is not a currently outstanding loan, and this comparison is not a sensitivity estimate for active liens.",
                         "by_source_window": [
                             {
                                 "source_window_id": window["summary"]["window_id"],
                                 "window_label": window["summary"]["window_label"],
                                 "roster_license_ids_with_granted_pledge_history": len(window_pledge_ids),
                                 "with_financing_keyword_marker": len(window_pledge_ids & finance_marker_ids),
                                 "without_financing_keyword_marker": len(window_pledge_ids - finance_marker_ids),
                                 "with_marker_license_ids": sorted(window_pledge_ids & finance_marker_ids),
                                 "without_marker_license_ids": sorted(window_pledge_ids - finance_marker_ids),
                                 "count_note": "Window-specific historical approvals; license IDs can recur across windows and are deduplicated in the combined comparison. Not an active-loan sensitivity estimate.",
                             }
                             for window in history_windows
                             for window_pledge_ids in [{event["license_num"] for event in window["board_events"]
                                                        if event["action_subtype"] == "pledge_application_disposition"
                                                        and event["disposition"] == "granted"
                                                        and event["license_num"] in all_roster_ids}]
                         ],
                     }},
    }
    save(BASE / "review-data.json", result)
    fields = [k for k in licenses[0] if k not in {
        "sources", "board_events", "transfer_events", "pledge_events", "source_row_ids", "ucc_query_evidence",
        "ownership_interest_events", "ownership_interest_notices", "corporate_registry_candidate", "corporate_officer_observations",
        "reconciled_history_reviews", "ownership_match_evidence", "ownership_assessment_evidence", "source_label_evidence",
        "history_source_notices", "history_proposals_or_unresolved_outcomes", "judgment_attachment_notices"}]
    fields.append("source_urls")
    with (BASE / "license-review.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in licenses:
            values = {k: row[k] for k in fields if k != "source_urls"}
            values["notes"] = " | ".join(values["notes"])
            values["name_mode_review_reasons"] = " | ".join(values["name_mode_review_reasons"])
            values["finance_marker_field_names"] = " | ".join(values["finance_marker_field_names"])
            for key in ("source_license_types", "source_license_categories", "source_label_classification_notes"):
                values[key] = " | ".join(values[key])
            values["license_type_literal_flags"] = json.dumps(values["license_type_literal_flags"], sort_keys=True)
            values["source_urls"] = " | ".join(source["url"] for source in row["sources"])
            writer.writerow(values)
    print(json.dumps({"output": str(BASE / "review-data.json"), "licenses": len(licenses),
                      "search_states": result["coverage"]["search_states"],
                      "board_actions": len(transfer_events), "ownership_applications": len(ownership_interest_events),
                      "source_documents": corpus_coverage["documents"], "pdf_pages": corpus_coverage["pdf_pages"]}, indent=2))


if __name__ == "__main__":
    build()
