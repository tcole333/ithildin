"""Audit retained provenance and emit 2021 coverage/CSV artifacts."""

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY = re.compile(
    r"transfer|pledg|owner|interest|share|equity|sale|sold|stock|beneficial|membership|corporate structure|convert|conversion",
    re.I,
)


def normalized(s):
    return re.sub(r"\s+", " ", s.replace("\u200b", "").replace("\xa0", " ")).strip()


def write(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2))


def main():
    index = json.loads((ROOT / "source-index.json").read_text())
    candidates = json.loads((ROOT / "candidates.json").read_text())
    events = json.loads((ROOT / "events.json").read_text())
    own = json.loads((ROOT / "ownership-interest-events.json").read_text())
    notices = json.loads((ROOT / "notices.json").read_text())
    excluded = json.loads((ROOT / "excluded-candidates.json").read_text())
    by_source = {e["source_id"]: e for e in index}
    for s in index:
        assert (
            hashlib.sha256((ROOT / s["pdf_path"]).read_bytes()).hexdigest()
            == s["sha256"]
        )
        text = (ROOT / s["text_path"]).read_text()
        m = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|Oct|November|December)\s+\d{1,2},?\s+2021",
            text[:1600],
        )
        assert m, s["source_id"]
        pattern = "%b %d, %Y" if m[1] == "Oct" else "%B %d, %Y"
        actual = datetime.strptime(m[0], pattern).strftime("%Y-%m-%d")
        assert actual == s["archive_date"], (s["source_id"], actual)
        s.update(
            {
                "document_date": actual,
                "date_matches_archive": True,
                "document_vote_date": actual if actual != "2021-04-20" else None,
                "document_hearing_date": actual if actual == "2021-04-20" else None,
                "document_date_basis": "Voting Agenda/Voting Hearing Agenda heading"
                if actual != "2021-04-20"
                else "Emergency hearing date in annotated notice; the actual vote date is not independently stated",
                "decision_bearing": True,
                "document_classification": "annotated_hearing_notice_with_explicit_disciplinary_dispositions"
                if actual == "2021-04-20"
                else "voting_agenda_with_explicit_dispositions",
                "scope_decision_count": sum(
                    e["source_id"] == s["source_id"] for e in events
                ),
                "ownership_decision_count": sum(
                    e["source_id"] == s["source_id"] for e in own
                ),
            }
        )
        if s.get("duplicate_of"):
            s["scope_decision_count"] = None
            s["ownership_decision_count"] = None
            s["deduplication_note"] = (
                "Identical PDF SHA-256 to canonical April 8 asset; no independent events extracted."
            )
        if actual == "2021-04-29":
            s["text_qc"]["blank_pages_visually_verified"] = [9]
    write("source-index.json", index)
    errors = []
    for e in events + own + notices:
        s = by_source[e["source_id"]]
        assert e["source_sha256"] == s["sha256"]
        assert e["source_url"] == s["url"]
        pages = json.loads((ROOT / s["pages_path"]).read_text())
        selected = "\n".join(
            p["text"] for p in pages if e["page_start"] <= p["page"] <= e["page_end"]
        )
        if normalized(e["item_text"]) not in normalized(selected):
            errors.append((e["event_id"], "source text or page span mismatch"))
        assert e["decision_bearing"]
        assert e["outcome"] != "not_stated"
        assert e["board_granted_application"] == (e["outcome"] == "granted")
        assert e["completed_sale_verified"] is False
        if e["license_num"]:
            ids = ["LB" + n for n in re.findall(r"LB\s*[-–‑]?\s*(\d+)", e["item_text"])]
            assert e["license_num"] in ids, e["event_id"]
        if e["event_type"] == "ownership_interest":
            assert e["equity_change_completion_verified"] is False
        if e["event_type"] == "license_pledge":
            match = re.search(
                r"pledge (?:of )?(?:the )?license(.{0,80}?)\bto\b",
                normalized(e["item_text"]),
                re.I,
            )
            e["collateral_as_stated"] = ["license"] + [
                v for v in ["stock", "inventory"] if match and v in match[1].lower()
            ]
            if e["date"] == "2021-10-07" and e["license_num"] == "LB98956":
                assert e["pledge_recipient"] is None
    assert not errors, errors
    write("events.json", events)
    current_stock = []
    for c in candidates:
        if (c["archive_date"], c["item_number"], c["page_start"]) not in [
            ("2021-04-01", "8", 4),
            ("2021-07-29", "22", 9),
        ]:
            continue
        base = next(
            (e for e in excluded + events if e["candidate_id"] == c["candidate_id"]),
            None,
        )
        assert base
        stock = {
            **base,
            "event_id": c["candidate_id"] + "-stock-pledge",
            "event_type": "stock_inventory_pledge",
            "action_subtype": "stock_inventory_pledge_application_disposition",
            "license_collateral_explicit": False,
            "pledge_recipient": "Cambridge Savings Bank"
            if c["archive_date"] == "2021-04-01"
            else "LE, Inc.",
            "collateral_as_stated": ["stock"]
            if c["archive_date"] == "2021-04-01"
            else ["stock", "inventory"],
            "ambiguity_notes": [
                "A stock/inventory pledge is explicitly stated; it is not counted as a license-pledge decision."
            ],
        }
        stock.pop("classification", None)
        current_stock.append(stock)
    write("stock-pledge-events.json", current_stock)
    unmatched = []
    for s in index:
        if s.get("duplicate_of"):
            continue
        texts = [
            normalized(c["item_text"])
            for c in candidates
            if c["source_id"] == s["source_id"]
        ]
        for p in json.loads((ROOT / s["pages_path"]).read_text()):
            for i, line in enumerate(p["text"].splitlines()):
                if KEY.search(line) and not any(
                    normalized(line) in text for text in texts
                ):
                    unmatched.append(
                        {
                            "source_id": s["source_id"],
                            "page": p["page"],
                            "line": i + 1,
                            "text": line.strip(),
                            "review_classification": "non_alcohol_license_transfer_section_header",
                            "reviewed": True,
                        }
                    )
    assert len(unmatched) == 5
    write("unmatched-keyword-contexts.json", unmatched)
    for filename, rows in [
        ("events.csv", events),
        ("ownership-interest-events.csv", own),
        ("notices.csv", notices),
    ]:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with (ROOT / filename).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        k: json.dumps(v, ensure_ascii=False)
                        if isinstance(v, (list, dict))
                        else v
                        for k, v in row.items()
                    }
                )
    coverage = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_year": 2021,
        "archive_date_range": ["2021-01-21", "2021-12-16"],
        "archive_date_entries": 25,
        "distinct_observed_urls": 26,
        "downloaded_urls": 26,
        "http_errors": 0,
        "unique_pdf_hashes": 25,
        "unique_pdf_pages": 230,
        "duplicate_pdf_urls": 1,
        "duplicate_pair": ["BLB-2021-04-08-v1", "BLB-2021-04-08-v2"],
        "archive_label_dates_verified": 25,
        "date_mismatches": 0,
        "actual_vote_date_not_independently_stated": ["BLB-2021-04-20"],
        "candidate_items_reviewed": len(candidates),
        "keyword_lines_reviewed": len(
            json.loads((ROOT / "all-keyword-contexts.json").read_text())
        ),
        "keyword_pattern": KEY.pattern,
        "unmatched_keyword_lines": 5,
        "unmatched_keyword_lines_reviewed_as_non_alcohol_section_headers": 5,
        "main_events": len(events),
        "event_types": dict(Counter(e["event_type"] for e in events)),
        "event_outcomes_by_type": {
            kind: dict(Counter(e["outcome"] for e in events if e["event_type"] == kind))
            for kind in ["license_transfer", "license_pledge"]
        },
        "distinct_transfer_license_ids": len(
            {
                e["license_num"]
                for e in events
                if e["event_type"] == "license_transfer" and e["license_num"]
            }
        ),
        "transfer_events_missing_explicit_license_id": sum(
            e["license_num"] is None
            for e in events
            if e["event_type"] == "license_transfer"
        ),
        "ownership_interest_decisions": len(own),
        "ownership_scope": dict(Counter(e["license_scope"] for e in own)),
        "ownership_outcomes": dict(Counter(e["outcome"] for e in own)),
        "ownership_with_named_before_after_parties": sum(
            bool(e["parties_before"] or e["parties_after"]) for e in own
        ),
        "explicit_entity_conversions": sum(
            e["entity_conversion_explicit"] for e in own
        ),
        "notices": len(notices),
        "notice_types": dict(Counter(e["event_type"] for e in notices)),
        "stock_inventory_only_pledge_decisions_separate": len(current_stock),
        "proposed_or_unresolved_events": 0,
        "excluded_candidates": len(excluded),
        "provenance_span_audit": "passed for all main/ownership/notice rows",
        "completed_sale_verified_count": 0,
        "current_lien_status_verified_count": 0,
        "limits": [
            "Coverage is every observed link in the retained official archive index, not proof that every 2021 meeting or transaction is represented.",
            "April 20 is an annotated emergency inspection notice; its printed hearing date matches the archive but actual vote date is not independently stated. It produces no in-scope transfer/pledge/ownership event.",
            "Applications granted/deferred/rejected at different meetings remain separate source occurrences, not unique completed deals.",
            "No sale price, payment, closing or currently outstanding secured balance is verified by this decision corpus.",
            "No historical/current-roster ID is imputed when an item omits its license number.",
            "No Massachusetts SOS portal, paid API or records-request submission was used.",
        ],
    }
    write("coverage.json", coverage)
    work = Path(json.loads((ROOT / "acquisition-run.json").read_text())["workdir"])
    write(
        "visual-qc.json",
        {
            "method": "pdftoppm rendered pages visually inspected",
            "render_directory": str(work),
            "pages": [
                {
                    "source_id": "BLB-2021-04-29",
                    "page": 9,
                    "result": "Blank page visually confirmed.",
                },
                {
                    "source_id": "BLB-2021-09-30",
                    "page": 16,
                    "result": "Air Ventures shares as printed (75., 12.25, 12.25) and separate manager-only Oak Sq. item confirmed.",
                },
                {
                    "source_id": "BLB-2021-10-07",
                    "page": 6,
                    "result": "Silhouette grant and blank pledge recipient after the word to confirmed.",
                },
                {
                    "source_id": "BLB-2021-11-18",
                    "page": 11,
                    "result": "Flat Black share changes and Raluca owner spelling discrepancy confirmed.",
                },
                {
                    "source_id": "BLB-2021-12-02",
                    "page": 11,
                    "result": "Rosas/TeaMoji share changes and Bitton grant confirmed.",
                },
                {
                    "source_id": "BLB-2021-12-16",
                    "page": 4,
                    "result": "Lunas LLC-to-Corporation entity conversion confirmed; neighboring Big Night item is DBA-only.",
                },
                {
                    "source_id": "BLB-2021-09-02",
                    "page": 1,
                    "result": "Le additional license pledge withdrawn; earlier transfer/stock pledge historical context confirmed.",
                },
            ],
        },
    )
    write(
        "validation.json",
        {
            "passed": True,
            "event_rows_audited": len(events),
            "ownership_rows_audited": len(own),
            "notice_rows_audited": len(notices),
            "source_hashes_audited": 26,
            "unique_pdf_pages": 230,
            "assertions": [
                "Source URL/hash matches manifest",
                "Exact normalized item text is present within cited page span",
                "Explicit license IDs occur in source item",
                "Included decisions have explicit outcomes",
                "All completion flags remain false",
                "Identical PDF variants are deduplicated",
                "Five unmatched keyword lines are non-alcohol section headings",
            ],
        },
    )
    print(json.dumps(coverage, indent=2))


if __name__ == "__main__":
    main()
