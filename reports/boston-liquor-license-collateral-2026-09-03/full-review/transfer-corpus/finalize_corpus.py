"""Combine reviewed events; preserve dispositions, notices, and source boundaries."""

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text())


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n")


def main():
    events = read("extraction-2024/events.json")
    subtypes = {
        "transfer_application_decision": "transfer_application_disposition",
        "pledge_application_decision": "pledge_application_disposition",
        "transfer_revocation_notice": "transfer_revocation_notice",
        "release_acknowledgment": "pledge_release_acknowledgment",
    }
    for event in events:
        event["action_subtype"] = subtypes[event.pop("event_subtype")]
        if event["event_type"] == "license_pledge":
            event["licensee"] = event.pop("pledging_party")
            event["licensee_dba"] = event.get("transferee_dba") or event.get("transferor_dba")
        if event["action_subtype"] == "transfer_revocation_notice":
            event["referenced_approval_date"] = "2024-03-28"
    events.extend(read("events-2025-2026.json"))
    notices = []
    for event in read("notices-2025-2026.json"):
        event_type = event["event_type"]
        if event_type == "transfer_revocation_notice":
            event.update(event_type="license_transfer", action_subtype="transfer_revocation_notice")
            if event["license_number"] == "LB-99671":
                event.update(transferor="Gogle Mogle, Inc.", transferor_dba="Seabiscuit",
                             transferee="Selfup LLC", transferee_dba="Selfup Cooking Classes",
                             from_address="256 Marginal St., East Boston, MA 02128",
                             to_address="19-21 Kingston St., Boston, MA 02111",
                             referenced_approval_date="2024-09-26")
            elif event["license_number"] == "LB-99070":
                event.update(transferor="D Street Music LLC", transferor_dba="D’s Keys Dueling Pianos",
                             transferee="Proctor Restaurant Enterprise, Inc.", transferee_dba="LuXXor/The Bloom Room",
                             from_address="391 D St., Boston, MA 02210",
                             to_address="28-30 Kingston St., Boston, MA 02111",
                             referenced_approval_date="2025-08-28")
            else:
                raise ValueError("Unreviewed revocation")
            event["ambiguity_notes"].append("Acknowledged mutual intent to revoke a previously approved transfer; source reports transaction not timely closed. Not a new approval or completed sale.")
            events.append(event)
        elif event_type == "pledge_release":
            if event["license_number"] != "LB-334563":
                raise ValueError("Unreviewed release")
            event.update(event_type="license_pledge", action_subtype="pledge_release_acknowledgment",
                         licensee="Shippy’s Inc.", licensee_dba="Beacon Street Liquors",
                         from_address="842 Beacon Street, Boston, MA 02215", pledge_recipient="Rockland Trust Company")
            event["ambiguity_notes"].append("Acknowledged release of previous pledges/security interests, not approval of a new pledge.")
            events.append(event)
        else:
            event["action_subtype"] = event_type
            notices.append(event)
    index = read("source-index.json")
    by_source = {x["source_id"]: x for x in index}
    source_texts = {x["source_id"]: re.sub(r"\s+", " ", (ROOT / x["text_path"]).read_text().replace("\u200b", "").replace("\u00a0", " ")) for x in index}
    for event in events + notices:
        event["item_number"] = str(event["item_number"])
        event["license_num"] = event["license_number"].replace("-", "") if event["license_number"] else None
        event["date"] = event["document_vote_date"]
        event["disposition"] = event["outcome"]
        event["board_granted_application"] = event.get("action_subtype", "").endswith("application_disposition") and event["outcome"] == "granted"
        event["completed_sale_verified"] = False
        source = by_source[event["source_id"]]
        assert re.sub(r"\s+", " ", event["item_text"]).strip() in source_texts[event["source_id"]], event["event_id"]
        if event["page_start"] is not None:
            assert 1 <= event["page_start"] <= event["page_end"] <= source["page_count"]
        if event in events:
            assert event["outcome"] != "not_stated", event["event_id"]
        else:
            event["decision_bearing"] = event["outcome"] != "not_stated"
    events.sort(key=lambda x: (x["date"], x["page_start"] or 0, int(x["item_number"]), x["event_type"]))
    assert len({x["event_id"] for x in events}) == len(events)
    write("events.json", events)
    write("notices.json", notices)
    fields = ["event_id", "date", "license_num", "event_type", "action_subtype", "disposition",
              "board_granted_application", "completed_sale_verified", "transferor", "transferor_dba",
              "transferee", "transferee_dba", "licensee", "licensee_dba", "pledge_recipient",
              "from_address", "to_address", "source_id", "source_url", "page_start", "page_end",
              "item_number", "outcome_text", "referenced_approval_date", "ambiguity_notes"]
    for kind, name in [("license_transfer", "transfers.csv"), ("license_pledge", "pledges.csv")]:
        with (ROOT / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fields, extrasaction="ignore")
            writer.writeheader()
            for event in events:
                if event["event_type"] == kind:
                    writer.writerow({**event, "ambiguity_notes": " | ".join(event["ambiguity_notes"])})
    candidates = read("candidates-2025-2026.json")
    uncovered = []
    for source in index:
        if source["archive_year"] < 2025:
            continue
        pages = read(source["pages_path"])
        reviewed = "\n".join(x["item_text"] for x in candidates if x["source_id"] == source["source_id"])
        normalized_reviewed = re.sub(r"\s+", " ", reviewed)
        for page in pages:
            for line in page["text"].replace("\u200b", "").replace("\u00a0", " ").splitlines():
                if re.search(r"transfer|pledg", line, re.I) and re.sub(r"\s+", " ", line).strip() not in normalized_reviewed:
                    uncovered.append({"source_id": source["source_id"], "page": page["page"], "text": line.strip()})
    write("uncovered-keyword-lines-2025-2026.json", uncovered)
    counts = Counter((x["event_type"], x["action_subtype"], x["outcome"]) for x in events)
    count_records = [{"event_type": k[0], "action_subtype": k[1], "outcome": k[2], "count": v} for k, v in sorted(counts.items())]
    summary = {
        "window_start": "2024-01-01", "window_end": "2026-09-03",
        "archive_url": "https://www.boston.gov/departments/licensing-board/licensing-board-information-and-members",
        "documents": len(index), "documents_by_year": dict(Counter(x["archive_year"] for x in index)),
        "downloaded_documents": sum(x["retrieval_status"] == "downloaded" for x in index),
        "pdf_pages": sum(x["page_count"] or 0 for x in index),
        "unpaginated_html_documents": [x["source_id"] for x in index if x["page_count"] is None],
        "events": len(events), "counts": count_records, "separate_status_notices": len(notices),
        "unique_transfer_license_ids": len({x["license_number"] for x in events if x["event_type"] == "license_transfer" and x["license_number"]}),
        "uncovered_keyword_lines_2025_2026": len(uncovered),
        "scope_limit": "Complete extraction of explicit transfers and license pledges in 64 linked decision-bearing records from the current official archive for 2024–2026 through September 3. This is not complete license history, a census of consummated sales, or proof of current liens. Calendar completeness is limited by the archive's links.",
        "archive_date_notes": [{"date": "2024-03-05", "evidence": "Archive lists combined transactional/voting video with no separately dated minutes; March 7 minutes explicitly include March 5 transactional decisions. Not treated as a proven missing transactional meeting."}],
        "calendar_audit_file": "extraction-2024/cross-year-coverage-audit.json",
        "calendar_audit_summary": read("extraction-2024/cross-year-coverage-audit.json")["summary"],
    }
    write("coverage.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
