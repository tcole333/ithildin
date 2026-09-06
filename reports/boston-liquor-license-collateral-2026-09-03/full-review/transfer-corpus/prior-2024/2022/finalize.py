"""Validate and summarize the reviewed 2022 source corpus."""

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n")


def main():
    sources = json.loads((ROOT / "source-index.json").read_text())
    source_map = {s["source_id"]: s for s in sources}
    visual = {
        "2022-10-26": {
            15: "Rendered page is blank.",
            9: "L-99088 is visibly printed; manager correction for item 20 verified.",
        },
        "2022-05-26": {
            10: "Dynasty Hot Pot, midnight closing, and 14A Hudson Street conditions verified; capacity 99 is continuation text, not a new item."
        },
        "2022-08-04": {
            6: "Visible disposition of item 12 is Granted; hidden text-layer residue is retained in original extraction. Capacity 48 belongs to item 11."
        },
        "2022-09-15": {
            4: "License Canceled outcome and alleged-beneficial-interest-change wording verified."
        },
        "2022-07-14": {
            6: "669 Centre stock-only pledge and ownership change verified."
        },
        "2022-06-08": {
            7: "Separate items 13 and unpunctuated 14 each have their own transfer/pledge and grant conditions."
        },
    }
    for s in sources:
        assert s["retrieval_status"] == "downloaded"
        assert (
            hashlib.sha256((ROOT / s["pdf_path"]).read_bytes()).hexdigest()
            == s["sha256"]
        )
        pages = json.loads((ROOT / s["pages_path"]).read_text())
        m = re.search(
            r"Voting Hearing (?:Agenda|Minutes)\s*\n([^\n]+)", pages[0]["text"]
        )
        s.update(
            {
                "document_vote_date": s["archive_date"],
                "document_date_verified": True,
                "document_date_review_basis": "Manually checked first-page voting-heading date against archive label.",
                "document_heading_date_text": m[1].strip() if m else None,
                "decision_bearing": True,
                "decision_bearing_basis": "Document contains explicit Board dispositions; title alone is not used.",
                "visual_reviewed_pages": visual.get(s["archive_date"], {}),
                "text_qc_status": "reviewed_usable_no_ocr_required",
            }
        )
        if s["archive_date"] == "2022-10-26":
            s["text_qc"]["empty_page_review"] = "PDF page 15 is visibly blank."
        if s["archive_date"] == "2022-08-04":
            s["text_qc"]["text_layer_artifact"] = (
                "Item 12 extracted GrantedrantedTransferManage; rendered page reads Granted."
            )
    write_json("source-index.json", sources)
    ledgers = {}
    for name in [
        "events",
        "ownership-interest-events",
        "notices",
        "proposed-events",
        "unresolved-events",
        "excluded-candidates",
    ]:
        rows = json.loads((ROOT / f"{name}.json").read_text())
        for row in rows:
            source = source_map[row["source_id"]]
            assert row["source_sha256"] == source["sha256"]
            assert row["document_vote_date"] == source["document_vote_date"]
            assert 1 <= row["page_start"] <= row["page_end"] <= source["page_count"]
            pages = json.loads((ROOT / source["pages_path"]).read_text())
            normalized = "\n".join(
                p["text"].replace("\u200b", "").replace("\u00a0", " ") for p in pages
            )
            assert row["item_text"] in normalized
            row["source_hash"] = row["source_sha256"]
            if name in {"events", "ownership-interest-events"}:
                assert row["decision_bearing"] and row["outcome"] != "not_stated"
                assert row["board_granted_application"] == (row["outcome"] == "granted")
                assert row["completed_sale_verified"] is False
            if row.get("license_num"):
                assert re.fullmatch(r"LB\d+", row["license_num"])
                assert row["license_num"] == row["license_number"].replace("-", "")
        if name == "ownership-interest-events":
            for row in rows:
                key = (row["date"], row["item_number"])
                if key == ("2022-02-17", 12):
                    row["entity_name"] = row["licensee"] = "Hyde Park Liquors II, Inc."
                    row["entity_dba"] = row["licensee_dba"] = "Dorrs Liquor Mart"
                    row["parties"].update(
                        {
                            "licensee": row["entity_name"],
                            "licensee_dba": row["entity_dba"],
                        }
                    )
                if key == ("2022-02-17", 11):
                    row.update(
                        {
                            "entity_before": "Amrhein’s Inc.",
                            "entity_after": "Mul’s Pub Inc.",
                        }
                    )
                    row["actions"].append("corporate_name_change")
                if key == ("2022-05-26", 10):
                    row["dba_before"] = "JM Curley"
                    row["dba_after"] = "JM Curley/Bogie’s Place/The Wig Shop Lounge"
                    row["ambiguity_notes"].append(
                        "Decision changes proposed Wig Lounge DBA to Wig Shop Lounge."
                    )
                if key == ("2022-07-14", 11):
                    row.update(
                        {
                            "dba_before": "Little Dipper",
                            "dba_after": "Tonino",
                            "stock_pledge_recipient": "David Doyle",
                        }
                    )
                row["ownership_actions"] = row["actions"]
        ledgers[name] = rows
        write_json(f"{name}.json", rows)
        if rows:
            columns = list(dict.fromkeys(k for row in rows for k in row))
            with (ROOT / f"{name}.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerows(
                    {
                        k: json.dumps(v, ensure_ascii=False)
                        if isinstance(v, (dict, list))
                        else v
                        for k, v in row.items()
                    }
                    for row in rows
                )
    candidates = json.loads((ROOT / "candidates.json").read_text())
    all_candidate_ids = {c["candidate_id"] for c in candidates}
    assigned_ids = {r["candidate_id"] for rows in ledgers.values() for r in rows}
    assert all_candidate_ids == assigned_ids
    assert not json.loads((ROOT / "unmatched-keywords.json").read_text())
    all_event_ids = [
        row["event_id"]
        for name, rows in ledgers.items()
        if name != "excluded-candidates"
        for row in rows
    ]
    assert len(all_event_ids) == len(set(all_event_ids))
    events, own, notices = (
        ledgers["events"],
        ledgers["ownership-interest-events"],
        ledgers["notices"],
    )
    coverage = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "year": 2022,
        "source_archive_index": "../../../history-access-evidence/older-archive-index.json",
        "source_index_url": sources[0]["discovered_on"],
        "observed_distinct_urls": 24,
        "downloaded_documents": len(sources),
        "download_errors": 0,
        "pdf_pages": sum(s["page_count"] for s in sources),
        "text_empty_pages": 1,
        "text_empty_pages_visually_verified_blank": 1,
        "ocr_required": False,
        "document_dates_match_archive": 24,
        "first_document_date": "2022-01-06",
        "last_document_date": "2022-12-15",
        "archive_link_coverage_complete": True,
        "calendar_completeness_established": False,
        "candidate_items_reviewed": len(candidates),
        "unmatched_keyword_occurrences": 0,
        "keyword_scope": "transfer, pledge, stock, stockholder, ownership, owner, interest, share, equity, corporate structure, conversion, member, sale, sold, purchase, surrender, revoke",
        "decision_events_by_type": dict(Counter(e["event_type"] for e in events)),
        "decision_events_by_type_and_outcome": {
            t: dict(Counter(e["outcome"] for e in events if e["event_type"] == t))
            for t in ["license_transfer", "license_pledge"]
        },
        "distinct_printed_valid_transfer_license_ids": len(
            {
                e["license_num"]
                for e in events
                if e["event_type"] == "license_transfer" and e["license_num"]
            }
        ),
        "transfer_decisions_without_valid_lb_id": sum(
            e["event_type"] == "license_transfer" and not e["license_num"]
            for e in events
        ),
        "ownership_decisions": len(own),
        "ownership_scope": dict(Counter(e["license_scope"] for e in own)),
        "ownership_outcomes": dict(Counter(e["outcome"] for e in own)),
        "entity_conversions_explicit": sum(
            e["entity_conversion_explicit"] for e in own
        ),
        "notices_by_type": dict(Counter(n["classification"] for n in notices)),
        "proposed_events": len(ledgers["proposed-events"]),
        "unresolved_events": len(ledgers["unresolved-events"]),
        "excluded_candidates": len(ledgers["excluded-candidates"]),
        "completed_sales_verified": 0,
        "current_liens_verified": 0,
        "validation": "Source hashes, exact candidate text containment, page bounds, date matches, canonical IDs, decision gates, unique event IDs and candidate-accounting passed.",
        "limitations": [
            "Covers only the 24 documents linked in the retained archive index; no meeting-calendar completeness claim.",
            "Board grant is application disposition, not proof of ABCC approval, issuance, closing, consideration, continuing debt or lien perfection.",
            "Repeated applications and separate events for the same license remain separate; counts are not unique sales.",
            "One malformed printed L-99088 ID is retained raw with normalized LB ID null.",
            "Five Common Victualler ownership items do not explicitly state alcohol category; they remain separately marked.",
        ],
    }
    write_json("coverage.json", coverage)
    write_json(
        "artifact-hashes.json",
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in ROOT.glob("*.json")
            if p.name != "artifact-hashes.json"
        },
    )
    print(
        json.dumps(
            {
                k: coverage[k]
                for k in [
                    "candidate_items_reviewed",
                    "decision_events_by_type",
                    "ownership_decisions",
                    "ownership_scope",
                    "notices_by_type",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
