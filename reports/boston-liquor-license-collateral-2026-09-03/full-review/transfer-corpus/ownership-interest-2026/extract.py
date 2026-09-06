"""Rebuild the manually reviewed 2026 ownership-interest extraction, offline."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT.parent
SCAN = re.compile(
    r"stock|member|owner|interest|shares|shareholder|corporate|reorgani|conversion|convert|equity",
    re.I,
)


def flat(value):
    return " ".join(value.split())


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def owner(name, percentage, quote):
    return {
        "name": name,
        "interest_percent": percentage,
        "role": "owner" if name == "Jia Liang Ruan" else "shareholder",
        "source_quote": quote,
    }


def classify(raw):
    text = flat(raw)
    if "shall submit applications for Change of Ownership" in text:
        return ["ownership_change_application_required"], "required_application_notice"
    actions = []
    if re.search(r"change (?:of |the )?ownership interest", text, re.I):
        actions.append("ownership_interest_change")
    if re.search(r"change (?:of |the )?stock interest", text, re.I):
        actions.append("stock_interest_change")
    if re.search(r"transfer of stock", text, re.I):
        actions.append("stock_transfer")
    if re.search(r"change (?:of |the )?(?:corporate name and )?corporate structure", text, re.I):
        actions.append("corporate_structure_change")
    return actions, "ownership_application_disposition" if actions else None


def exclusion_reason(raw):
    text = flat(raw)
    if re.search(r"Corporate Controller", text, re.I):
        return "Officer/controller addition only; no explicit ownership-interest change."
    if re.search(r"corporate name", text, re.I):
        return "Corporate name change only; no explicit entity conversion or ownership-interest change."
    if "stock burners" in text:
        return "Kitchen stock burners; no equity interest."
    if re.search(r"pledge (?:the license and )?stock|pledge of stock", text, re.I):
        return "Stock pledge or license transfer alone; no explicit transfer/change of ownership interest."
    if re.search(r"Conversion to outdoor", text, re.I):
        return "Premises conversion; no entity conversion or ownership-interest change."
    return "Storage/inventory, managerial or other keyword use without an explicit ownership-interest or entity-structure change."


def event_from(candidate, actions, subtype):
    raw = candidate["item_text"]
    text = flat(raw)
    dba = re.search(r"Doing business as:[ \t]*([^\n]+)", raw)
    licenses = candidate["license_numbers"]
    assert len(licenses) == 1, candidate["candidate_id"]
    alcohol = bool(re.search(r"Alcoholic Beverages|Wines and Malt Beverages|Category: CV7AL", text, re.I))
    scope = (
        "explicit_alcohol" if alcohol else
        "common_victualler_no_alcohol_stated" if "Common Victualler License" in text else "other"
    )
    outcome_match = re.search(r"(?m)^(Granted\b|Violation\s*-)", raw)
    assert outcome_match, candidate["candidate_id"]
    outcome_text = raw[outcome_match.start():].split("________________")[0].strip()
    outcome_text = re.split(
        r"\n(?:The following|Non-Hearing|Non Hearing|Common Victualler|Old & New|One Day)",
        outcome_text,
    )[0].strip()
    event = {
        "event_id": candidate["candidate_id"].replace("-OI-C", "-OI-E"),
        "source_id": candidate["source_id"],
        "source_url": candidate["source_url"],
        "date": candidate["date"],
        "license_num": licenses[0],
        "page_start": candidate["page_start"],
        "page_end": candidate["page_end"],
        "item_number": candidate["item_number"],
        "entity_name": candidate["entity_name"],
        "entity_dba": dba[1].strip() if dba else None,
        "license_scope": scope,
        "actions": actions,
        "event_subtype": subtype,
        "outcome": "required_application_notice" if subtype == "required_application_notice" else "granted",
        "outcome_text": outcome_text,
        "parties_before": [],
        "parties_after": [],
        "entity_before": None,
        "entity_after": None,
        "item_text": raw,
        "ambiguity_notes": [],
    }
    if "corporate_structure_change" in actions:
        match = re.search(
            r"Corporate (?:Name and Corporate )?Structure.*?From:\s*(.*?)\s+To:\s*(.*?)(?=\s+(?:Additionally,|Lastly,|Granted)|$)",
            text,
            re.I,
        )
        assert match, candidate["candidate_id"]
        event["entity_before"] = match[1].strip()
        event["entity_after"] = match[2].strip()
        # Sentence punctuation follows the LLC name; Inc. punctuation is retained.
        if event["entity_after"].endswith("LLC."):
            event["entity_after"] = event["entity_after"][:-1]
        event["ambiguity_notes"].append(
            "Corporate-structure change only. The item does not establish a change in beneficial ownership or identify shareholders."
        )
    elif subtype == "required_application_notice":
        event["ambiguity_notes"].append(
            "Enforcement disposition directs submission of ownership- and manager-change applications within 30 days; it does not approve an ownership change. The July 16 petition is a separate event."
        )
    elif licenses[0] == "LB-584421":
        quote = "From: Orhan Berten (50% Shares) To: Sezar Yavuz (100%shares)"
        event["parties_before"] = [owner("Orhan Berten", 50, quote)]
        event["parties_after"] = [owner("Sezar Yavuz", 100, quote)]
        event["ambiguity_notes"].append(
            "Only the stated 50% prior interest is recorded. The item does not identify the other prior 50% or state Sezar Yavuz's prior percentage. Manager roles do not supply missing ownership."
        )
    elif licenses[0] == "LB-577304":
        quote = "From: Daniel Lam (43% Shares) , Uyen Lai (43% Shares & Trang Tran (14% Shares) To: Daniel Lam (100% Shares)"
        event["parties_before"] = [
            owner("Daniel Lam", 43, quote), owner("Uyen Lai", 43, quote), owner("Trang Tran", 14, quote),
        ]
        event["parties_after"] = [owner("Daniel Lam", 100, quote)]
        event["ambiguity_notes"].append(
            "The source omits a closing parenthesis after Uyen Lai's 43% interest; names and percentages are preserved as stated."
        )
    elif licenses[0] == "LB-99928":
        quote = "To: Jia Liang Ruan, Manager of Record, President, Treasurer, Clerk, and 100% Owner"
        event["parties_after"] = [owner("Jia Liang Ruan", 100, quote)]
        event["ambiguity_notes"].append(
            "The prior named people are identified only as manager/officers, with no prior ownership percentages stated. They are not classified as prior owners."
        )
    else:
        event["ambiguity_notes"].append(
            "The item states a change of ownership/stock interest but does not identify the before/after owners or their percentages. Named managers, officers, attorneys and pledge recipients are not treated as shareholders."
        )
    for party in event["parties_before"] + event["parties_after"]:
        assert flat(party["source_quote"]) in text, (candidate["candidate_id"], party)
    return event


def main():
    sources = [s for s in json.loads((CORPUS / "source-index.json").read_text()) if s["archive_year"] == 2026]
    candidates, events, documents = [], [], []
    for source in sources:
        pages = json.loads((CORPUS / source["pages_path"]).read_text())
        normalized = [p["text"].replace("\u200b", "").replace("\u00a0", " ") for p in pages]
        text = "\n".join(normalized)
        offsets = []
        cursor = 0
        for page, page_text in zip(pages, normalized, strict=True):
            offsets.append((cursor, page["page"]))
            cursor += len(page_text) + 1
        # Some source items use "4.Tatte"; reject decimal rule numbers such as 1.15.
        headings = list(re.finditer(r"(?m)^[ \t]*(\d{1,3})[.,](?=[ \t]|[^\d\s])[ \t]*([^\n]*)", text))
        covered_spans = []
        source_candidates, source_events = [], []
        for position, heading in enumerate(headings):
            end = headings[position + 1].start() if position + 1 < len(headings) else len(text)
            start = heading.start(1)
            raw = text[start:end].rstrip()
            if not SCAN.search(raw):
                continue
            covered_spans.append((start, end))
            candidate = {
                "candidate_id": f"{source['source_id']}-OI-C{position + 1:03d}",
                "source_id": source["source_id"], "source_url": source["url"],
                "date": source["archive_date"],
                "page_start": next(p for offset, p in reversed(offsets) if start >= offset),
                "page_end": next(p for offset, p in reversed(offsets) if start + len(raw) - 1 >= offset),
                "item_number": int(heading[1]), "entity_name": heading[2].strip(),
                "license_numbers": list(dict.fromkeys(
                    f"LB-{x}" for x in re.findall(r"LB\s*[-\u2010\u2011\u2013]?\s*(\d+)", raw)
                )),
                "keyword_matches": sorted({match[0].lower() for match in SCAN.finditer(raw)}),
                "item_text": raw,
            }
            actions, subtype = classify(raw)
            candidate["review_status"] = "included" if actions else "excluded"
            candidate["review_reason"] = (
                "Explicit ownership/stock-interest change, corporate-structure change, or required ownership application."
                if actions else exclusion_reason(raw)
            )
            if actions:
                event = event_from(candidate, actions, subtype)
                candidate["event_id"] = event["event_id"]
                source_events.append(event)
            source_candidates.append(candidate)
        uncovered = []
        for match in SCAN.finditer(text):
            if not any(start <= match.start() < end for start, end in covered_spans):
                uncovered.append(text[max(0, match.start() - 150):match.end() + 150])
        assert not uncovered, (source["source_id"], uncovered)
        documents.append({
            "source_id": source["source_id"], "source_url": source["url"],
            "date": source["archive_date"], "page_count": len(pages),
            "source_sha256": source["sha256"],
            "review_status": "all_pages_keyword_audited_all_candidate_items_manually_reviewed",
            "numbered_items_scanned": len(headings),
            "keyword_match_count": len(list(SCAN.finditer(text))),
            "candidate_count": len(source_candidates),
            "event_count": len(source_events),
            "application_disposition_count": sum(e["event_subtype"] == "ownership_application_disposition" for e in source_events),
            "notice_count": sum(e["event_subtype"] == "required_application_notice" for e in source_events),
            "uncovered_keyword_hits": uncovered,
            "candidate_ids": [c["candidate_id"] for c in source_candidates],
        })
        candidates.extend(source_candidates)
        events.extend(source_events)
    assert len(sources) == 16
    assert len(events) == 36
    assert len({e["event_id"] for e in events}) == len(events)
    assert Counter(e["outcome"] for e in events) == {"granted": 35, "required_application_notice": 1}
    coverage = {
        "scope": "All 16 downloaded Boston Licensing Board decision documents indexed for 2026 through September 3, 2026; archive-linked scope only.",
        "method": "Every page was scanned offline for broad owner/ownership/stock/member/interest/share/corporate/reorganization/conversion/equity terms. Every candidate's full item text was manually reviewed. A supplementary issuance/issuing scan found only license-issuance language, not equity issuance. All keyword occurrences are covered by candidate item spans; zero-event documents are retained. Dates use the previously verified document-heading dates in the corpus source index.",
        "inclusions": "Explicit ownership/stock-interest changes or stock transfers; explicit corporate-structure changes; required ownership application notices, distinctly classified. Common Victualler items with no alcohol stated remain tagged separately.",
        "exclusions": "Officer/manager/name-only changes, license transfers alone, stock pledges alone, stock inventory/storage/burners, premises conversions and license-type conversions alone. No beneficial owner, control change, private-equity affiliation, completion or unstated percentage inferred.",
        "source_count": len(documents), "pdf_page_count": sum(d["page_count"] for d in documents),
        "numbered_items_scanned": sum(d["numbered_items_scanned"] for d in documents),
        "candidate_count": len(candidates), "event_count": len(events),
        "application_disposition_count": 35, "required_application_notice_count": 1,
        "outcome_counts": dict(Counter(e["outcome"] for e in events)),
        "action_counts": dict(Counter(a for e in events for a in e["actions"])),
        "license_scope_counts": dict(Counter(e["license_scope"] for e in events)),
        "visual_validation": [
            {"render": "validation/2026-01-29-p12.png", "confirmed": "Zarhan's stated before 50% and after 100%; grant; no unstated prior owner inferred."},
            {"render": "validation/2026-01-29-p13.png", "confirmed": "Pho Que's 43/43/14 to Daniel Lam 100%; source parenthesis omission; grant."},
            {"render": "validation/2026-04-30-p16.png", "confirmed": "China Bros' after-owner 100%; prior people have manager/officer roles only; grant."},
            {"render": "validation/2026-05-21-p8.png", "confirmed": "Naqvi sole-proprietor to Shaboo Bee, Inc.; all grant conditions preserved."},
            {"render": "validation/2026-08-06-p19.png", "confirmed": "Whole Foods CV corporate-structure changes; LB-101174 item continues to next page for outcome."},
            {"render": "validation/2026-08-06-p20.png", "confirmed": "LB-101174 grant at top of page belongs to prior-page item; LB-101028 and LB-108942 grants also confirmed."},
        ],
        "documents": documents,
    }
    write_json("candidates.json", candidates)
    write_json("events.json", events)
    write_json("coverage.json", coverage)
    print(json.dumps({k: v for k, v in coverage.items() if k.endswith("count") or k.endswith("counts")}, indent=2))


if __name__ == "__main__":
    main()
