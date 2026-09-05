"""Normalize reviewed year ledgers without modifying either source-year or baseline files."""

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT.parent
YEARS = (2020, 2021, 2022, 2023)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def dump(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def norm(text):
    # Source-year extraction differs only in treatment of zero-width formatting and
    # line-wrap whitespace. Preserve original item text; ignore those for containment.
    return re.sub(r"\s+", "", text.replace("\u200b", "").replace("\u00a0", " "))


def csv_dump(name, events):
    primary = ["event_id", "source_id", "source_sha256", "source_url", "license_num", "license_number",
               "date", "archive_date", "document_vote_date", "page_start", "page_end", "item_number",
               "event_type", "action_subtype", "event_subtype", "outcome", "outcome_text",
               "decision_bearing", "board_granted_application", "completed_sale_verified"]
    fields = primary + sorted({key for event in events for key in event} - set(primary))
    with (ROOT / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for event in events:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in event.items()})


def main():
    frozen = read(ROOT / "frozen-existing-files.json")
    for rel, expected in frozen.items():
        assert sha(BASELINE / rel) == expected, ("Frozen file changed", rel)
    inventory = read(BASELINE.parent / "history-access-evidence/older-archive-index.json")
    observed_urls = {url for entry in inventory["entries"] for url in entry["distinct_urls"]}
    sources, year_coverage = [], {}
    for year in YEARS:
        directory = ROOT / str(year)
        year_coverage[str(year)] = read(directory / "coverage.json")
        for source in read(directory / "source-index.json"):
            source = dict(source)
            assert source["retrieval_status"] in {"downloaded", "downloaded_identical_hash"}, source["source_id"]
            source["original_retrieval_status"] = source["retrieval_status"]
            source["retrieval_status"] = "downloaded"
            for key in ["pdf_path", "text_path", "pages_path"]:
                if source.get(key):
                    source[key] = str(Path(str(year)) / source[key])
            assert sha(ROOT / source["pdf_path"]) == source["sha256"], source["source_id"]
            source["source_window"] = "2020-2023"
            source["source_url"] = source["url"]
            source["document_sha256"] = source["sha256"]
            source["text_sha256"] = sha(ROOT / source["text_path"])
            source["url_filename"] = unquote(Path(urlsplit(source["url"]).path).name)
            source["year_manifest"] = f"{year}/source-index.json"
            source["year_coverage"] = f"{year}/coverage.json"
            source["archive_year"] = year
            source["document_date"] = source.get("document_vote_date") or source.get("document_date") or source.get("document_hearing_date")
            assert source["document_date"] == source["archive_date"], source["source_id"]
            source["date_matches_archive_label"] = True
            sources.append(source)
    assert {s["url"] for s in sources} == observed_urls
    assert len(sources) == len(observed_urls) == 91
    sources.sort(key=lambda x: (x["archive_date"], x["source_id"]))
    hash_groups = defaultdict(list)
    for source in sources:
        hash_groups[source["sha256"]].append(source)
    for group in hash_groups.values():
        canonical = next((s for s in group if not s.get("duplicate_of")), group[0])
        for source in group:
            source["canonical_source_id"] = canonical["source_id"]
            source["is_duplicate_asset"] = source["source_id"] != canonical["source_id"]
            source["include_in_unique_document_count"] = not source["is_duplicate_asset"]
            source["same_document_source_urls"] = [s["url"] for s in group]
            source["duplicate_of"] = canonical["source_id"] if source["is_duplicate_asset"] else None
    source_map = {s["source_id"]: s for s in sources}
    baseline_sources = read(BASELINE / "source-index.json")
    baseline_hashes = {s["sha256"]: s for s in baseline_sources if s.get("sha256")}
    cross_window_duplicates = [{"prior_source_id": s["source_id"], "baseline_source_id": baseline_hashes[s["sha256"]]["source_id"], "sha256": s["sha256"]}
                               for s in sources if s["sha256"] in baseline_hashes]
    for source in sources:
        source["duplicates_original_2024_2026_document"] = source["sha256"] in baseline_hashes
    page_cache = {s["source_id"]: read(ROOT / s["pages_path"]) for s in sources}
    full_text_cache = {s["source_id"]: (ROOT / s["text_path"]).read_text() for s in sources}
    outcomes = {"granted", "deferred", "continued", "rescheduled", "to_be_re_noticed", "withdrawn", "rejected", "denied", "acknowledged"}
    main_events, ownership, notices, ownership_notices, proposals = [], [], [], [], []
    routing_log = []

    def normalize(original, year, source_file, decision=False):
        event = dict(original)
        source = source_map[event["source_id"]]
        event["original_year_artifact"] = f"{year}/{source_file}"
        event["source_window"] = "2020-2023"
        event["source_sha256"] = source["sha256"]
        event["source_hash"] = source["sha256"]
        event["source_url"] = event.get("source_url") or source["url"]
        event["source_urls"] = source["same_document_source_urls"]
        event["canonical_source_id"] = source["canonical_source_id"]
        event["item_text_sha256"] = hashlib.sha256(event["item_text"].encode()).hexdigest()
        event["source_quote"] = event["item_text"]
        event["document_vote_date"] = source["document_vote_date"]
        event["archive_date"] = source["archive_date"]
        event["date"] = source["document_vote_date"] or event.get("date") or source["document_date"]
        license_id = event.get("license_num") or event.get("license_number")
        event["license_num_as_supplied"] = event.get("license_num")
        match = re.fullmatch(r"LB\s*[-‐‑–—]?\s*(\d+)", license_id or "", re.I)
        event["license_num"] = "LB" + match[1] if match else None
        event["normalized_license_num"] = event["license_num"]
        event["license_number"] = "LB-" + match[1] if match else None
        event["item_number"] = str(event["item_number"]) if event.get("item_number") is not None else None
        event["page"] = event["page_start"]
        event["item"] = event["item_number"]
        event["disposition"] = event.get("outcome", "not_stated")
        event["board_granted_application"] = decision and event["disposition"] == "granted"
        event["completed_sale_verified"] = False
        event.setdefault("ambiguity_notes", [])
        event.setdefault("decision_bearing", decision)
        scope = event.get("license_scope")
        if scope == "alcohol_stated":
            event["license_scope"] = "explicit_alcohol"
        subtype = event.get("action_subtype") or event.get("event_subtype") or event["event_type"]
        subtype = {"license_transfer_application_disposition": "transfer_application_disposition",
                   "license_pledge_application_disposition": "pledge_application_disposition",
                   "pledge_release_notice": "pledge_release_acknowledgment"}.get(subtype, subtype)
        event["action_subtype"] = subtype
        if event["event_type"] == "ownership_interest" or source_file == "ownership-interest-events.json":
            event["event_type"] = "ownership_interest"
            event["event_subtype"] = "ownership_application_disposition" if decision else event.get("event_subtype", subtype)
            event.setdefault("actions", event.get("ownership_actions", []))
            event.setdefault("parties_before", [])
            event.setdefault("parties_after", [])
            event.setdefault("entity_conversion_explicit", False)
            event["equity_change_completion_verified"] = False
        if event["event_type"] == "license_pledge":
            event.setdefault("licensee", event.get("pledging_entity") or event.get("transferee") or event.get("transferor"))
            event.setdefault("licensee_dba", event.get("transferee_dba") or event.get("transferor_dba"))
        assert norm(event["item_text"]) in norm(full_text_cache[event["source_id"]]), ("Quote outside source", event["event_id"])
        assert 1 <= event["page_start"] <= event["page_end"] <= source["page_count"], ("Page bounds", event["event_id"])
        page_text = "\n".join(p["text"] for p in page_cache[event["source_id"]] if event["page_start"] <= p["page"] <= event["page_end"])
        assert norm(event["item_text"]) in norm(page_text), ("Quote outside cited pages", event["event_id"])
        if decision:
            assert event["disposition"] in outcomes, ("Uncertain outcome in decision ledger", event["event_id"])
            assert event["outcome_text"], event["event_id"]
            assert norm(event["outcome_text"]).lower() in norm(event["item_text"]).lower(), ("Outcome quote mismatch", event["event_id"])
            event["decision_bearing"] = True
        if event["license_num"]:
            stripped_quote = re.sub(r"[^a-z0-9]", "", event["item_text"].lower())
            assert event["license_num"].lower() in stripped_quote, ("ID not printed", event["event_id"])
        return event

    for year in YEARS:
        directory = ROOT / str(year)
        for original in read(directory / "events.json"):
            main_events.append(normalize(original, year, "events.json", decision=True))
        for original in read(directory / "ownership-interest-events.json"):
            ownership.append(normalize(original, year, "ownership-interest-events.json", decision=True))
        for filename in ["proposed-events.json", "unresolved-events.json"]:
            if (directory / filename).exists():
                for original in read(directory / filename):
                    event = normalize(original, year, filename)
                    event["decision_bearing"] = False
                    event["board_granted_application"] = False
                    event["withheld_from_decision_counts"] = True
                    proposals.append(event)
        for original in read(directory / "notices.json"):
            subtype = original.get("action_subtype") or original.get("event_subtype") or original["event_type"]
            if subtype == "pledge_release_notice" and original.get("outcome") == "acknowledged":
                event = normalize(original, year, "notices.json", decision=True)
                event["board_granted_application"] = False
                main_events.append(event)
                routing_log.append({"event_id": event["event_id"], "from": f"{year}/notices.json", "to": "events.json", "reason": "Explicit acknowledgment of license-pledge release, normalized to baseline ledger convention."})
                continue
            event = normalize(original, year, "notices.json")
            owner_context = "ownership" in subtype or "ownership" in event["event_type"] or subtype in {"conditional_license_revocation_directive", "license_cancellation", "cancellation_after_alleged_unauthorized_interest_change"}
            if owner_context:
                event["original_event_type"] = event["event_type"]
                event["event_type"] = "ownership_interest"
                event["event_subtype"] = subtype
                event["equity_change_completion_verified"] = False
                event["board_granted_application"] = False
                ownership_notices.append(event)
            else:
                if subtype == "prospective_license_transfer_notice":
                    event["event_type"] = "prospective_transfer_or_status_notice"
                    event["action_subtype"] = "prospective_transfer_or_status_notice"
                notices.append(event)
    duplicate_events = []

    def dedup(events):
        result, seen = [], {}
        for event in sorted(events, key=lambda e: (e["date"], e["source_id"], e["page_start"], e["event_id"])):
            key = (event["source_sha256"], event["page_start"], event["item_number"], event["event_type"], event["action_subtype"], norm(event["item_text"]))
            if key in seen:
                duplicate_events.append({"event_id": event["event_id"], "duplicate_of": seen[key]})
            else:
                seen[key] = event["event_id"]
                result.append(event)
        return result

    main_events, ownership, notices, ownership_notices, proposals = map(dedup, [main_events, ownership, notices, ownership_notices, proposals])
    all_events = main_events + ownership + notices + ownership_notices + proposals
    assert len(all_events) == len({e["event_id"] for e in all_events}), "Event IDs collide across ledgers"
    assert not cross_window_duplicates, "Cross-window PDF duplicate requires reviewed event routing"
    for name, value in [("source-index.json", sources), ("events.json", main_events), ("ownership-interest-events.json", ownership),
                        ("notices.json", notices), ("ownership-interest-notices.json", ownership_notices), ("proposed-events.json", proposals),
                        ("normalization-log.json", routing_log), ("duplicate-event-audit.json", duplicate_events), ("year-coverage.json", year_coverage)]:
        dump(name, value)
    for name, values in [("events.csv", main_events), ("ownership-interest-events.csv", ownership), ("notices.csv", notices),
                         ("ownership-interest-notices.csv", ownership_notices), ("proposed-events.csv", proposals)]:
        csv_dump(name, values)
    coverage = {
        "integration_status": "qa_complete", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_window": "2020-2023", "scope": "All exact retained official pre-2024 archive links; not lifetime or calendar-complete license history.",
        "archive_index_url": inventory["source"]["source_url"], "archive_index_sha256": inventory["source"]["sha256"],
        "observed_urls": len(sources), "successful_pdf_downloads": len(sources), "unique_document_hashes": len(hash_groups),
        "unique_pdf_pages": sum(group[0]["page_count"] for group in hash_groups.values()),
        "document_date_range": [min(s["document_date"] for s in sources), max(s["document_date"] for s in sources)],
        "documents_without_explicit_vote_date": [{"source_id": s["source_id"], "document_date": s["document_date"], "date_basis": s.get("document_date_basis")} for s in sources if not s.get("document_vote_date")],
        "archive_date_range": [min(s["archive_date"] for s in sources), max(s["archive_date"] for s in sources)],
        "source_counts_by_year": {str(year): {"observed_urls": sum(s["archive_year"] == year for s in sources),
                                                "unique_document_hashes": len({s["sha256"] for s in sources if s["archive_year"] == year}),
                                                "unique_pdf_pages": sum(g[0]["page_count"] for g in hash_groups.values() if g[0]["archive_year"] == year)} for year in YEARS},
        "duplicate_assets": [{"source_id": s["source_id"], "duplicate_of": s["duplicate_of"], "sha256": s["sha256"]} for s in sources if s["is_duplicate_asset"]],
        "cross_window_hash_check": {"baseline_manifest": "../source-index.json", "baseline_manifest_sha256": sha(BASELINE / "source-index.json"),
                                     "baseline_source_records": len(baseline_sources), "baseline_unique_source_hashes": len(baseline_hashes),
                                     "duplicates": cross_window_duplicates, "duplicates_found": len(cross_window_duplicates)},
        "date_conflicts": [{"year": year, "details": data.get("date_conflicts") or data.get("document_date_discrepancies") or data.get("date_discrepancies") or []} for year, data in year_coverage.items()],
        "events": len(main_events), "event_subtypes": dict(Counter(e["action_subtype"] for e in main_events)),
        "event_outcomes": dict(Counter(e["outcome"] for e in main_events)),
        "action_outcomes": {sub: dict(Counter(e["outcome"] for e in main_events if e["action_subtype"] == sub)) for sub in sorted({e["action_subtype"] for e in main_events})},
        "events_by_year": {str(year): dict(Counter(e["action_subtype"] for e in main_events if e["date"].startswith(str(year)))) for year in YEARS},
        "ownership_interest_events": len(ownership), "ownership_outcomes": dict(Counter(e["outcome"] for e in ownership)),
        "ownership_license_scopes": dict(Counter(e.get("license_scope") for e in ownership)),
        "ownership_explicit_conversion_items": sum(bool(e["entity_conversion_explicit"]) for e in ownership),
        "transfer_pledge_status_notices": len(notices), "ownership_interest_notices": len(ownership_notices),
        "proposed_or_unresolved_events": len(proposals), "proposed_or_unresolved_outcomes": dict(Counter(e["outcome"] for e in proposals)),
        "missing_normalized_license_ids": {"events": sum(e["license_num"] is None for e in main_events), "ownership_interest_events": sum(e["license_num"] is None for e in ownership),
                                           "notices": sum(e["license_num"] is None for e in notices), "ownership_interest_notices": sum(e["license_num"] is None for e in ownership_notices),
                                           "proposed_or_unresolved_events": sum(e["license_num"] is None for e in proposals)},
        "duplicate_events_removed": len(duplicate_events), "full_source_quote_and_page_bounds_checks_passed": len(all_events),
        "frozen_existing_files_verified": len(frozen), "roster_join_performed": False,
        "limitations": ["Counts are source actions, not unique economic transactions or completed sales.", "Grant does not establish closing, price, current debt, current lien or ownership control.",
                        "No source linked before April23,2020 was acquired; later link completeness is not meeting-calendar completeness.", "Malformed/missing IDs are preserved, with no name/address-derived LB replacements."]}
    dump("coverage.json", coverage)
    artifact_names = ["source-index.json", "events.json", "ownership-interest-events.json", "notices.json", "ownership-interest-notices.json", "proposed-events.json", "coverage.json", "year-coverage.json", "normalization-log.json", "duplicate-event-audit.json"]
    dump("readiness.json", {"integration_status": "qa_complete", "artifacts": {name: sha(ROOT / name) for name in artifact_names},
                            "frozen_baseline_verified": True, "qa_basis": "All source hashes, exact URL inventory, document dates, quote containment within cited page spans, outcome gates, ID appearance, event uniqueness and cross-window PDF hash comparison passed."})
    print(json.dumps(coverage, indent=2))


if __name__ == "__main__":
    main()
