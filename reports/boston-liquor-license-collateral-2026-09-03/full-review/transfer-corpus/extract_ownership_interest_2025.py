"""Review-derived 2025 ownership-interest ledger from retained Board source text."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "ownership-interest-2025"
KEYWORDS = re.compile(r"stock|member(?:ship)?|beneficial|conver(?:t|sion)|ownership|owners?\b|interest|shares?|shareholders?|corporate\s+(?:name and corporate\s+)?structure|reorgani[sz]|\bmerg", re.I)


def norm(value):
    return re.sub(r"\s+", " ", value).strip()


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")


def candidates(index):
    items = []
    for entry in index:
        if entry["archive_year"] != 2025:
            continue
        pages = json.loads((ROOT / entry["pages_path"]).read_text())
        offsets, offset = [], 0
        for page in pages:
            page["text"] = page["text"].replace("\u200b", "").replace("\u00a0", " ")
            offsets.append((offset, page["page"]))
            offset += len(page["text"]) + 1
        text = "\n".join(page["text"] for page in pages)
        matches = list(re.finditer(r"(?m)^[ \t]*(\d{1,3})[.,][ \t]+([^\n]*)", text))
        for position, match in enumerate(matches):
            end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
            raw = text[match.start():end].strip()
            if not KEYWORDS.search(raw):
                continue
            start_page = next((p for start, p in reversed(offsets) if match.start(1) >= start), None)
            end_pos = end - len(text[match.start():end]) + len(text[match.start():end].rstrip())
            end_page = next((p for start, p in reversed(offsets) if end_pos - 1 >= start), None)
            ids = list(dict.fromkeys(re.findall(r"LB\s*[-\u2010\u2011\u2013]?\s*(\d+)", raw)))
            items.append({"candidate_id": f"{entry['source_id']}-OI-{position+1:03d}",
                          "source_id": entry["source_id"], "source_url": entry["url"], "date": entry["archive_date"],
                          "page_start": start_page, "page_end": end_page, "item_number": match[1],
                          "entity_name": match[2].strip(), "license_num": "LB" + ids[0] if len(ids) == 1 else None,
                          "item_text": raw})
    return items


# Tuple fields: name, explicitly stated percentage, stated role; optional share quantity.
PARTIES = {
    "LB171735": ([('Ayr Muir', 100, 'CEO')], [('Clover Fast Food, Inc', 100, None)]),
    "LB570847": ([(n, 20, 'Manager') for n in ['Ahmed Kasem', 'Dany Abouelkhier', 'Mohamed Kassem', 'Mohammed Ali', 'Omar Neamatalla']],
                 [(n, 25, 'Manager') for n in ['Ahmed Kasem', 'Mohamed Kassem', 'Mohammed Ali', 'Omar Neamatalla']]),
    "LB463819": ([('Panupak Kraiwong', 30, None), ('Alisa Satnurugs', 40, None), ('Nakhon Rungruanatanapol', 30, None)],
                 [('Nakhon Rungruanatanapol', 45, 'Member'), ('Alisa Satnurugs', 55, 'Member')]),
    "LB100527": ([('Stavros Papantoniadis', 100, 'Owner')], [('Anastasia Papantoniadis', 50, 'President'), ('Gregorios Papantoniadis', 25, 'Treasurer, Director'), ('Anastasios Papantoniadis', 25, 'Secretary')]),
    "LB128840": ([('Stavros Papantoniadis', 100, 'Owner')], [('Anastasia Papantoniadis', 100, 'President, Secretary, Treasurer, Director')]),
    "LB100142": ([(n, p, 'LLC Manager / Member') for n, p in [('Hyuk Kim', 28.19), ('Sampson Duong', 15.96), ('Jonathan Joo', 30.57), ('Augustus Lam', 6.38), ('Edward Kang', 5.88), ('Henry Nguyen', 13.02)]], [('Jin Chong', 100, 'LLC Manager / Member')]),
    "LB98704": ([('ESTATE OF ANGELINA VARA,C/O DIMENTO AND SULLIVAN', None, None)], [('Henry D Vera, III', 33.33, 'Director / President'), ('Holli Vera', 33.33, 'Director / Treasurer / Secretary'), ('Christian Vera', 33.33, 'Director')]),
    "LB100478": ([('Lindsay Rosado', None, None, 800), ('Michael Lamattina', None, None, 800)], [('Lindsay Rosado', None, None, 300), ('Michael Lamattina', None, None, 300)]),
    "LB101176": ([('Lindsay Rosado', None, None, 46.25), ('Michael Lamattina', None, None, 46.25)], [('Lindsay Rosado', None, None, 300), ('Michael Lamattina', None, None, 300)]),
    "LB547630": ([(n, 25, None) for n in ['Qianyi Weng', 'Jieyi Chen', 'Wenyin Ma', 'Xinyi Liang']], [('Shimeng Fu', 50, None), ('Brandon Bo Hon Chiu', 50, None)]),
    "LB100852": ([('Ahmet Ozseferoglu', 50, 'Owner')], [('Gulsume Erdem', 50, 'Owner')]),
    "LB480459": ([('Ming Yang Zheng', 50, 'Owner/Treasurer')], [('Emily Chen', 100, 'Pres/Manager')]),
    "LB332339": ([('Richard Phipps', 33.33, 'Vice President'), ('Meridith Morgan', 33.33, 'Secretary')], [('Wayne Atkinson', 100, 'President')]),
    "LB114808": ([('Olcian Durham', 50, 'Vice President')], [('Andrew Gayle', 50, 'Co-Owner')]),
}
CONVERSIONS = {"LB100205": ("SANTINI BALDINI, LLC", "SANTINI BALDINI, INC"),
               "LB99058": ("James Associates, Inc.", "James Associates, LLC"),
               "LB99057": ("JABC Corp.", "JABC, LLC")}


def main():
    OUT.mkdir(exist_ok=True)
    index = json.loads((ROOT / "source-index.json").read_text())
    items = candidates(index)
    dump("candidates.json", items)
    events, excluded, notices = [], [], []
    for item in items:
        text = norm(item["item_text"])
        actions = []
        if re.search(r"change (?:of |in |the )?ownership interest", text, re.I):
            actions.append("ownership_interest_change")
        if re.search(r"change (?:of |in |the )?stock interest", text, re.I):
            actions.append("stock_interest_change")
        if re.search(r"transfer of stock", text, re.I):
            actions.append("stock_transfer")
        if "updated stockholders" in text:
            actions.append("updated_stockholders")
        if re.search(r"corporate structure", text, re.I):
            actions.append("corporate_structure_change")
        if not actions:
            why = "informational_ownership_hearing_no_action" if "Informational hearing regarding the ownership/beneficial interest" in text else "keyword_without_explicit_ownership_change"
            excluded.append({**item, "exclusion_reason": why})
            if why.startswith("informational"):
                notices.append({**item, "event_subtype": "informational_ownership_hearing", "outcome": "no_action_taken"})
            continue
        outcome = re.search(r"(?mi)^\s*(Granted\b[^\n]*|Continued\b[^\n]*|Deferred\b[^\n]*|Withdrawn\b[^\n]*)", item["item_text"])
        assert outcome, item["candidate_id"]
        header = re.split(r"License\s*#", item["item_text"], maxsplit=1, flags=re.I)[0]
        dba = re.search(r"Doing business as:\s*([^\n]+)", header, re.I)
        scope = "explicit_alcohol" if re.search(r"alcohol|wines?|malt|brewery|winery", text.split("has petition")[0], re.I) else "common_victualler_no_alcohol_stated" if re.search(r"Holder of a Common Victualler", text, re.I) else "other"
        event = {**item, "event_id": item["candidate_id"], "event_subtype": "ownership_application_disposition",
                 "entity_dba": dba[1].strip() if dba else None, "license_scope": scope,
                 "actions": actions, "outcome": outcome[1].split()[0].lower().rstrip(",."), "outcome_text": outcome[1].strip(),
                 "parties_before": [], "parties_after": [], "entity_before": None, "entity_after": None,
                 "ownership_subject_entity": item["entity_name"], "ownership_subject_scope": "licensee",
                 "ambiguity_notes": []}
        number = item["license_num"]
        if number in PARTIES:
            start = re.search(r"(?:change (?:the )?Ownership [Ii]nterest|Transfer of Stock)", text, re.I)
            assert start
            clause = re.split(r"\bSecondly\b|\bLastly\b|\bGranted\b", text[start.start():], maxsplit=1)[0].strip()
            event["ownership_clause"] = clause
            for direction, tuples in zip(["parties_before", "parties_after"], PARTIES[number]):
                for fields in tuples:
                    name, percent, role = fields[:3]
                    assert name in clause, (number, name)
                    event[direction].append({"name": name, "interest_percent": percent, "role": role, "source_quote": clause,
                                             "interest_quantity": fields[3] if len(fields) > 3 else None,
                                             "interest_unit": "shares" if len(fields) > 3 else None})
            event["ambiguity_notes"].append("Only parties and interests stated in the ownership clause are listed; this is not assumed to be a complete capitalization table.")
        if number in CONVERSIONS:
            event["entity_before"], event["entity_after"] = CONVERSIONS[number]
            event["ambiguity_notes"].append("Corporate conversion identifies entity forms, not beneficial owners or consideration.")
        if not event["parties_before"] and not event["parties_after"]:
            event["ambiguity_notes"].append("Source does not identify before/after equity holders or percentages; manager/officer names are not treated as owners.")
        if number == "LB386575":
            event["ownership_subject_entity"] = "Nightshift Brewing Inc."
            event["ownership_subject_scope"] = "parent_company_explicit"
            event["ambiguity_notes"].append("Source explicitly places the stock-interest change at the parent company Nightshift Brewing Inc.; licensee is Night Shift Lovejoy, LLC.")
        if number == "LB99350":
            event["ownership_subject_entity"] = "F.P. Restaurant, Inc."
            event["ownership_subject_scope"] = "proposed_transferee_explicit"
            event["ambiguity_notes"].append("Source explicitly says transferee has updated stockholders, but names no stockholders. License transfer is separately captured in the original frozen corpus.")
        if number == "LB171735":
            event["ambiguity_notes"].append("Source names Clover Fast Food, Inc itself as 100% holder; preserved as stated without resolving apparent self-ownership wording.")
        if number in {"LB100478", "LB101176"}:
            event["ambiguity_notes"].append("Source states share quantities without percent symbols; these are not converted to percentages. Separate officer removal does not establish disposition of that officer's shares.")
        if number == "LB463565":
            event["ambiguity_notes"].append("Same document repeats this LB number in three distinct pouring-license categories; source occurrences preserved, not assumed three separate equity transactions.")
        if number == "LB481086":
            event["ambiguity_notes"].append("Same ownership-change petition is continued May 1 then granted May 15, 2025; preserved as separate decisions.")
        if "pledge of stock" in text.lower():
            event["ambiguity_notes"].append("Item also includes a stock pledge, which does not itself establish an equity ownership transfer or control.")
        if "not to be issued" in text.lower():
            event["ambiguity_notes"].append("Grant has an explicit issuance condition retained in full item text; no assertion that the condition was satisfied.")
        events.append(event)
    uncovered = []
    for entry in index:
        if entry["archive_year"] != 2025:
            continue
        reviewed = norm("\n".join(x["item_text"] for x in items if x["source_id"] == entry["source_id"]))
        for page in json.loads((ROOT / entry["pages_path"]).read_text()):
            for line in page["text"].replace("\u200b", "").replace("\u00a0", " ").splitlines():
                if KEYWORDS.search(line) and norm(line) not in reviewed:
                    uncovered.append({"source_id": entry["source_id"], "page": page["page"], "line": line})
    dump("events.json", events)
    dump("excluded.json", excluded)
    dump("notices.json", notices)
    dump("coverage.json", {"documents_reviewed": 25, "candidate_items": len(items), "events": len(events),
                           "outcomes": dict(Counter(x["outcome"] for x in events)), "license_scopes": dict(Counter(x["license_scope"] for x in events)),
                           "notices_excluded_from_applications": len(notices), "uncovered_keyword_lines": uncovered,
                           "document_counts": [{"source_id": x["source_id"], "events": sum(e["source_id"] == x["source_id"] for e in events)} for x in index if x["archive_year"] == 2025]})
    print(json.dumps({"candidates": len(items), "events": len(events), "excluded": len(excluded), "uncovered": len(uncovered)}))


if __name__ == "__main__":
    main()
