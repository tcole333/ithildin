"""Merge only the new ownership-interest ledgers; never rewrite transfer/benchmark files."""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text())


def norm(text):
    return re.sub(r"\s+", " ", text.replace("\u200b", "").replace("\u00a0", " ")).strip()


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n")


def main():
    frozen = ["events.json", "benchmark/input.json", "benchmark/reference.json", "benchmark/rubric.md"]
    before = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in frozen}
    raw = []
    for year in [2024, 2025, 2026]:
        raw.extend(read(f"ownership-interest-{year}/events.json"))
    raw.extend(read("ownership-interest-2025/notices.json"))
    sources = {x["source_id"]: x for x in read("source-index.json")}
    source_texts = {key: norm((ROOT / source["text_path"]).read_text()) for key, source in sources.items()}
    applications, notices = [], []
    for event in raw:
        event.setdefault("event_id", event.get("candidate_id"))
        event["event_type"] = "ownership_interest"
        event["license_num"] = re.sub(r"[^A-Z0-9]", "", event["license_num"].upper()) if event["license_num"] else None
        event["license_number"] = event["license_num"].replace("LB", "LB-", 1) if event["license_num"] else None
        event["item_number"] = str(event["item_number"])
        event["license_scope"] = "explicit_alcohol" if event.get("license_scope") == "alcohol_stated" else event.get("license_scope", "common_victualler_no_alcohol_stated")
        event.setdefault("entity_dba", None)
        event.setdefault("actions", [event["event_subtype"]])
        event.setdefault("parties_before", [])
        event.setdefault("parties_after", [])
        event.setdefault("entity_before", None)
        event.setdefault("entity_after", None)
        event.setdefault("ownership_subject_entity", event["entity_name"])
        event.setdefault("ownership_subject_scope", "licensee")
        event.setdefault("ambiguity_notes", [])
        event.setdefault("outcome_text", "No Action Taken" if event["outcome"] == "no_action_taken" else None)
        event.setdefault("entity_conversion_explicit", bool("corporate_structure_change" in event["actions"] and event["entity_before"] and event["entity_after"]))
        event["disposition"] = event["outcome"]
        event["board_granted_application"] = event["event_subtype"] == "ownership_application_disposition" and event["outcome"] == "granted"
        event["equity_change_completion_verified"] = False
        for party in event["parties_before"] + event["parties_after"]:
            party.setdefault("interest_quantity", None)
            party.setdefault("interest_unit", None)
            assert norm(party["source_quote"]) in norm(event["item_text"]), event["event_id"]
        assert norm(event["item_text"]) in source_texts[event["source_id"]], event["event_id"]
        source = sources[event["source_id"]]
        if event["page_start"] is not None:
            assert 1 <= event["page_start"] <= event["page_end"] <= source["page_count"]
        if event["event_subtype"] == "ownership_application_disposition":
            applications.append(event)
        else:
            notices.append(event)
    def key(event):
        return event["date"], event["page_start"] or 0, int(event["item_number"])
    applications.sort(key=key)
    notices.sort(key=key)
    assert len({e["event_id"] for e in applications + notices}) == len(applications + notices)
    write("ownership-interest-events.json", applications)
    write("ownership-interest-notices.json", notices)
    fields = ["event_id", "date", "license_num", "license_scope", "event_subtype", "entity_name", "entity_dba",
              "actions", "outcome", "board_granted_application", "ownership_subject_entity", "ownership_subject_scope",
              "parties_before", "parties_after", "entity_before", "entity_after", "entity_conversion_explicit",
              "source_url", "page_start", "page_end", "item_number", "outcome_text", "ambiguity_notes", "item_text"]
    with (ROOT / "ownership-interest-events.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields, extrasaction="ignore")
        writer.writeheader()
        for event in applications:
            row = dict(event)
            for field in ["actions", "parties_before", "parties_after", "ambiguity_notes"]:
                row[field] = json.dumps(row[field], ensure_ascii=False)
            writer.writerow(row)
    alcohol = [e for e in applications if e["license_scope"] == "explicit_alcohol"]
    docs = []
    for source in sources.values():
        matches = [e for e in applications if e["source_id"] == source["source_id"]]
        docs.append({"source_id": source["source_id"], "source_url": source["url"], "date": source["archive_date"],
                     "pages": source["page_count"], "application_events": len(matches),
                     "alcohol_application_events": sum(e["license_scope"] == "explicit_alcohol" for e in matches),
                     "notices": sum(e["source_id"] == source["source_id"] for e in notices), "reviewed": True})
    summary = {
        "scope": "All 64 retained Board decision records, 2024 through September 3, 2026; ownership-interest and corporate-structure items only. This is not complete license or ownership history.",
        "documents_reviewed": len(docs), "pdf_pages": sum(s["page_count"] or 0 for s in sources.values()),
        "unpaginated_html_documents": [s["source_id"] for s in sources.values() if s["page_count"] is None],
        "application_events": len(applications), "notices_separate": len(notices),
        "application_outcomes": dict(Counter(e["outcome"] for e in applications)),
        "applications_by_year": dict(Counter(e["date"][:4] for e in applications)),
        "application_license_scopes": dict(Counter(e["license_scope"] for e in applications)),
        "alcohol_application_outcomes": dict(Counter(e["outcome"] for e in alcohol)),
        "unique_license_ids_all_applications": len({e["license_num"] for e in applications if e["license_num"]}),
        "unique_alcohol_license_ids": len({e["license_num"] for e in alcohol if e["license_num"]}),
        "alcohol_items_with_named_equity_parties": sum(bool(e["parties_before"] or e["parties_after"]) for e in alcohol),
        "alcohol_items_with_explicit_owner_percentages": sum(any(p["interest_percent"] is not None for p in e["parties_before"] + e["parties_after"]) for e in alcohol),
        "explicit_entity_conversion_items": sum(e["entity_conversion_explicit"] for e in applications),
        "action_occurrences_not_distinct_transactions": dict(Counter(a for e in applications for a in e["actions"])),
        "year_audits": [f"ownership-interest-{year}/coverage.json" for year in [2024, 2025, 2026]],
        "documents": docs,
        "frozen_files_unchanged": all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in before.items()),
        "limits": ["Counts are source application decisions, not distinct completed equity transactions.",
                   "Generic ownership/stock-interest changes do not identify sponsors, equity control, economic terms, or completed closings.",
                   "Nonalcohol Common Victualler and billiards records are retained but separately tagged; filter license_scope for alcohol analysis.",
                   "Corporate entity-form changes are kept separate from shareholders; repeated occurrences across licenses or categories are not deduplicated into economic transactions.",
                   "Manager/officer changes, stock pledges alone, inventory storage, premises conversions, and license-type changes alone are excluded."]
    }
    assert summary["frozen_files_unchanged"]
    write("ownership-interest-coverage.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"documents", "limits"}}, indent=2))


if __name__ == "__main__":
    main()
