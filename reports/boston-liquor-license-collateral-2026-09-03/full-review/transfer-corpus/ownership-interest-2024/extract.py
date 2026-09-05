import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
sources = [
    s
    for s in json.loads((ROOT / "source-index.json").read_text())
    if s["archive_year"] == 2024
]
keyword = re.compile(
    r"\bownership\b|\bstock\b|\bshares?\b|shareholder|stockholder|\bequity\b|benefici|membership|\bmembers\b|corporate\s+structure|\bconvert\w*|\bconversion\b|reorgani|entity\s+(?:type|structure)",
    re.I,
)
candidates = []
coverage = []
for source in sources:
    text = (ROOT / "documents" / f"{source['source_id']}.txt").read_text()
    headers = list(re.finditer(r"(?m)^\s*(\d{1,2})[.)]\s+([^\n]+)", text))
    date_match = re.search(
        r"Voting\s+Hearing\s+Agenda\s+([A-Za-z]+\s+\d{1,2},\s*20\d{2})", text
    )
    date = dt.datetime.strptime(date_match.group(1), "%B %d, %Y").date().isoformat()
    src_items = []
    for i, header in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[header.start() : end].strip()
        block = re.split(
            r"\n\s*(?:Non-Hearing Transactions|Transactional Hearing|THE BOARD WILL DEFER)",
            block,
            maxsplit=1,
        )[0].strip()
        block = re.split(r"\n\s*_{5,}", block, maxsplit=1)[0].strip()
        if not keyword.search(block):
            continue
        start = text.index(block, header.start())
        license_match = re.search(r"LB\s*[‐‑–—-]?\s*(\d+)", block)
        dba_match = re.search(r"Doing business as:\s*([^\n]+)", block, re.I)
        outcome_match = re.search(
            r"(?im)^\s*((?:Granted|Denied|Deferred|Withdrawn|Rejected|Approved|No Action|Acknowledged|Rescinded|Not approved|Rescheduled)\b[\s\S]*)",
            block,
        )
        outcome_text = (
            re.sub(r"[_]{5,}.*", "", outcome_match.group(1)).strip()
            if outcome_match
            else None
        )
        flat = " ".join(block.split())
        actions = []
        if re.search(
            r"(?:change|changes)\s+(?:(?:the|of|in)\s+)*(?:Change of\s+)?Ownership\s+Interest",
            flat,
            re.I,
        ):
            actions.append("ownership_interest_change")
        if re.search(
            r"(?:change|changes)\s+(?:(?:the|of|in)\s+)*Stock\s+Interest", flat, re.I
        ):
            actions.append("stock_interest_change")
        if re.search(r"change\s+(?:the\s+)?Corporate\s+Structure", flat, re.I):
            actions.append("corporate_structure_change")
        if re.search(
            r"change\s+the\s+Ownership\s+of\s+the\s+Licensed\s+Business", flat, re.I
        ):
            actions.append("licensed_business_ownership_change")
        is_notice = source["source_id"] == "BLB-2024-08-22" and header.group(1) in [
            "3",
            "9",
        ]
        if is_notice:
            actions.append(
                "ownership_management_record_update_notice"
                if header.group(1) == "3"
                else "ownership_management_participation_notice"
            )
        candidate = {
            "source_id": source["source_id"],
            "source_url": source["url"],
            "date": date,
            "license_num": f"LB-{license_match.group(1)}" if license_match else None,
            "page_start": text[:start].count("\f") + 1,
            "page_end": text[: start + len(block)].count("\f") + 1,
            "item_number": header.group(1),
            "entity_name": header.group(2).strip(),
            "entity_dba": dba_match.group(1).strip() if dba_match else None,
            "actions": actions,
            "outcome": outcome_text.split()[0].lower().rstrip(",:;")
            if outcome_text
            else "not_stated",
            "outcome_text": outcome_text,
            "parties_before": [],
            "parties_after": [],
            "item_text": block,
            "ambiguity_notes": [],
            "license_scope": "alcohol_stated"
            if re.search(
                r"Alcohol|Wines?\s+(?:and|&)\s+Malt|Brewery|Winery|Distillery|Category:\s*CV7AL\b",
                flat,
                re.I,
            )
            else "common_victualler_no_alcohol_stated",
            "inclusion_status": "included" if actions else "excluded",
            "exclusion_reason": None
            if actions
            else "Stock inventory or other nontransactional ownership reference; no explicit ownership-interest action.",
        }
        if is_notice:
            candidate["outcome"] = "notice"
            candidate["outcome_text"] = flat[
                flat.index(
                    "The Licensee is on notice"
                    if header.group(1) == "3"
                    else "The Board will hold a second hearing"
                ) :
            ]
        candidates.append(candidate)
        src_items.append(candidate)
    uncovered = [
        line.strip()
        for line in text.splitlines()
        if keyword.search(line)
        and not any(line.strip() in item["item_text"] for item in src_items)
    ]
    coverage.append(
        {
            "source_id": source["source_id"],
            "source_url": source["url"],
            "date": date,
            "checked": True,
            "page_count": text.count("\f"),
            "candidate_items": len(src_items),
            "included_items": sum(bool(x["actions"]) for x in src_items),
            "excluded_items": sum(not bool(x["actions"]) for x in src_items),
            "uncovered_keyword_lines": uncovered,
        }
    )

# Source-specific facts below were manually checked against each complete item.
# Generic manager/officer names intentionally never enter these owner arrays.
percent_facts = {
    ("BLB-2024-04-25", "LB-100822"): (
        [("Kelly Fernandes", 100)],
        [("Elizabeth Santos", 50), ("Marvin Mathelier", 50)],
    ),
    ("BLB-2024-04-25", "LB-99949"): (
        [("Jennifer Gallagher", 70), ("Dave O'Donnell", 15), ("John Abbott", 15)],
        [("Jennifer Gallagher", 65), ("Dave O'Donnell", 35)],
    ),
    ("BLB-2024-05-23", "LB-405940"): (
        [("Kelsey Munger", 50), ("Javier Amador‑Pena", 50)],
        [("Kelsey Munger", 100)],
    ),
    ("BLB-2024-10-31", "LB-100760"): (
        [("Robert Eng", 60), ("Paul Eng", 40)],
        [("Robert Eng", 60), ("Wu Hua Wu", 40)],
    ),
    ("BLB-2024-10-31", "LB-100912"): (
        [("Xiaoheng Peng", 50), ("Xiaoqo Peng", 50)],
        [("Xiaoheng Peng", 100)],
    ),
    ("BLB-2024-10-31", "LB-128286"): (
        [("Jian Hong Huang", 50), ("Ren Quan Chen", 50)],
        [("Jian Hong Huang", 100)],
    ),
}
for license_num in ["LB-429465", "LB-386471", "LB-100654", "LB-100165"]:
    percent_facts[("BLB-2024-10-31", license_num)] = (
        [("David Jenks", 75), ("Dominic Benvenuti", 20), ("Shawn Brunelle", 5)],
        [("David Jenks", 51), ("Dominic Benvenuti", 49)],
    )

for candidate in candidates:
    if not candidate["actions"]:
        continue
    candidate["event_id"] = (
        f"{candidate['source_id']}-OWN-p{candidate['page_start']}-i{candidate['item_number']}"
    )
    candidate["event_subtype"] = "ownership_application_disposition"
    if any(action.endswith("_notice") for action in candidate["actions"]):
        candidate["event_subtype"] = candidate["actions"][0]
        candidate["ambiguity_notes"].append(
            "Ownership/management compliance or participation notice, not an approved ownership change. No buyer, seller, shareholder, percentage, or specific ownership transaction is identified."
        )
    flat = " ".join(candidate["item_text"].split())
    candidate["entity_before"] = None
    candidate["entity_after"] = None
    candidate["entity_change_source_quote"] = None
    candidate["entity_conversion_explicit"] = False
    candidate["ownership_subject_entity"] = candidate["entity_name"]
    candidate["ownership_subject_scope"] = (
        "named_licensee_or_licensed_business; indirect_ownership_level_not_further_specified"
    )
    if candidate["license_num"] is None:
        candidate["ambiguity_notes"].append(
            "Boston LB identifier omitted in this source item; not inferred from another record."
        )
    key = (candidate["source_id"], candidate["license_num"])
    if key in percent_facts or key == ("BLB-2024-10-17", "LB-100635"):
        owner_clause = re.search(r"Ownership\s+Interest\b.*", flat, re.I).group(0)
        owner_clause = re.split(
            r"\s+(?:Secondly|Lastly),?\s|\s+Granted\b",
            owner_clause,
            maxsplit=1,
            flags=re.I,
        )[0].strip()
        facts = percent_facts.get(key, ([], [("Wiyada Chunlawat", None)]))
        for side, values in zip(["parties_before", "parties_after"], facts):
            candidate[side] = [
                {
                    "name": name,
                    "interest_percent": percent,
                    "role": "ownership_interest_holder",
                    "source_quote": owner_clause,
                }
                for name, percent in values
            ]
            for party in candidate[side]:
                assert party["name"] in owner_clause
                assert party["interest_percent"] is None or "%" in owner_clause
        if key == ("BLB-2024-10-17", "LB-100635"):
            candidate["ambiguity_notes"].append(
                "Ownership clause independently names Wiyada Chunlawat, but no percentage or prior owner is stated. The manager From/To clause is not used as ownership evidence."
            )
    if candidate["source_id"] == "BLB-2024-01-04" and candidate["item_number"] in [
        "14",
        "15",
        "16",
    ]:
        structure = re.search(
            r"Corporate Structure.*?From:\s*(.*?)\s+To:\s*(.*?)\s+Secondly", flat, re.I
        )
        candidate["entity_before"] = structure.group(1).strip()
        candidate["entity_after"] = structure.group(2).strip().rstrip(".")
        candidate["entity_change_source_quote"] = structure.group(0).rsplit(
            " Secondly", 1
        )[0]
        candidate["entity_conversion_explicit"] = True
        candidate["ownership_subject_scope"] = "licensee_entity_form_conversion"
        candidate["ambiguity_notes"].append(
            "Corporate-to-LLC conversion is explicit. Entity before/after names are not shareholders or beneficial owners; no change in equity control is inferred."
        )
        if candidate["item_number"] in ["14", "15"]:
            candidate["ambiguity_notes"].append(
                "Same Marriott Hotel Services Inc-to-LLC conversion appears for Long Wharf and Copley license applications; preserve both source occurrences without counting two distinct equity transactions."
            )
    if key == ("BLB-2024-10-17", "LB-160484"):
        change = re.search(
            r"Ownership of the Licensed Business From:\s*(.*?)\s+To:\s*(.*?)\s+Secondly",
            flat,
            re.I,
        )
        candidate["entity_before"] = change.group(1).strip()
        candidate["entity_after"] = change.group(2).strip().rstrip(".")
        candidate["entity_change_source_quote"] = change.group(0).rsplit(
            " Secondly", 1
        )[0]
        candidate["ambiguity_notes"].append(
            "Source calls this ownership of the licensed business, naming Ltd and Inc entities. Names are retained separately as entity before/after, not treated as beneficial owners; legal conversion versus separate entity transfer is not established."
        )
    if (
        candidate["source_id"] == "BLB-2024-10-31"
        and candidate["entity_name"] == "RBSBW, INC."
    ):
        candidate["ambiguity_notes"].append(
            "Same meeting repeats each RBSBW/Roche Bros license in two items, with and without corporate structure change. Preserve source occurrences; not evidence of two distinct equity transactions. No owners, percentages, or resulting corporate form are supplied."
        )
    if (
        candidate["source_id"] == "BLB-2024-11-21"
        and candidate["entity_name"] == "Night Shift Lovejoy, LLC"
    ):
        candidate["ambiguity_notes"].append(
            "Source repeats LB-431061 for four separate 19C/19B/19E/19H pouring-license items. Preserve all source occurrences and their stated IDs/types; not four distinct equity transactions. Manager change does not establish personal shareholding."
        )
    if (
        candidate["source_id"] == "BLB-2024-10-31"
        and candidate["entity_name"] == "Boston Pie, Inc."
    ):
        candidate["ambiguity_notes"].append(
            "Same named owners and before/after percentages recur for four Boston Pie licensed locations in this meeting. Preserve the four license-item occurrences, not four distinct underlying equity transactions."
        )
    if key in [("BLB-2024-02-29", "LB-101846"), ("BLB-2024-06-06", "LB-101846")]:
        candidate["ambiguity_notes"].append(
            "Golden Goose stock-interest changes recur on February 29 and June 6. Parties and amounts are unstated, so whether these reflect the same or different underlying equity transaction is unresolved."
        )
    if not candidate["parties_before"] and not candidate["parties_after"]:
        candidate["ambiguity_notes"].append(
            "No owner/shareholder names or ownership percentages are stated for the ownership action; officer and manager names in the item are not substituted."
        )
    if candidate["event_subtype"] == "ownership_application_disposition":
        candidate["ambiguity_notes"].append(
            "Board approval alone does not establish a completed transaction, current capitalization, control, or private-equity sponsorship."
        )

for row in coverage:
    relevant = [
        x for x in candidates if x["source_id"] == row["source_id"] and x["actions"]
    ]
    row["action_counts"] = dict(
        Counter(action for x in relevant for action in x["actions"])
    )
    row["outcome_counts"] = dict(Counter(x["outcome"] for x in relevant))
    row["license_scope_counts"] = dict(Counter(x["license_scope"] for x in relevant))
    row["items_with_explicit_percentages"] = sum(
        any(
            p["interest_percent"] is not None
            for side in ["parties_before", "parties_after"]
            for p in x[side]
        )
        for x in relevant
    )
    row["review_method"] = (
        "All keyword candidate items read; exact ownership clauses manually transcribed for percentages and entity changes. Keyword coverage includes corporate structure, reorganization, shares/shareholders, stock, ownership, membership, and beneficial interest."
    )
    row["visual_checked_pages"] = {
        "BLB-2024-01-04": [7],
        "BLB-2024-04-25": [11],
        "BLB-2024-10-17": [19],
        "BLB-2024-10-31": [6, 17],
    }.get(row["source_id"], [])
(OUT / "candidates.json").write_text(
    json.dumps(candidates, ensure_ascii=False, indent=2) + "\n"
)
(OUT / "events.json").write_text(
    json.dumps([x for x in candidates if x["actions"]], ensure_ascii=False, indent=2)
    + "\n"
)
(OUT / "coverage.json").write_text(
    json.dumps(coverage, ensure_ascii=False, indent=2) + "\n"
)
for x in candidates:
    print(
        x["source_id"],
        "p" + str(x["page_start"]),
        "item" + x["item_number"],
        x["entity_name"],
        x["actions"],
        x["outcome"],
    )
print(
    "TOTAL",
    len(candidates),
    "INCLUDED",
    sum(bool(x["actions"]) for x in candidates),
    "UNREVIEWED KEYWORD LINES",
    sum(len(x["uncovered_keyword_lines"]) for x in coverage),
)
print("ACTIONS", dict(Counter(a for x in candidates for a in x["actions"])))
