"""Structure the reviewed 2023 items; classifications are explicit review decisions."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRANSFERS = {1, 2, 3, 7, 8, 9, 14, 15, 16, 17, 18, 19, 20, 21, 25, 26, 27, 28, 29, 30,
             31, 32, 33, 34, 35, 36, 37, 38, 42, 44, 45, 46, 51, 53, 54, 55, 56, 57, 60, 61,
             62, 64, 65, 66, 67, 69, 70, 71, 73, 77, 78, 79, 80, 81, 82, 83, 84, 89, 90, 93,
             98, 99, 104, 105, 106, 107, 108, 109, 110, 111, 122, 123, 124, 125, 126, 127, 128, 129}
OWNERSHIP = {5, 6, 10, 22, 23, 24, 40, 41, 43, 48, 50, 52, 58, 59, 76, 87, 92, 94, 95,
             96, 97, 103, 112, 113, 114, 115, 116, 118, 119, 120, 130}
PLEDGES = {
    0: "Berkshire Bank", 1: "Middlesex Federal Savings Bank", 2: "Sunny Side Enterprises, Inc.",
    7: "The Bank of Canton", 9: "Newburyport Bank", 13: "Eastern Bank", 15: "267 269 NSR, LLC",
    16: "Rockland Trust Company", 19: "Barry’s Corner Property, LLC", 25: "Vesper, LLC",
    26: "Nosmada Inc.", 27: "Seaport B/C Retail Owner LLC", 28: "Cambridge Savings Bank",
    30: "Core Investments, Inc.", 31: "Zaiter Investments LLC", 34: "Northern Bank and Trust Company",
    35: "New Valley Bank & Trust", 36: "Rockland Trust Company", 38: "267 269 NSR, LLC",
    44: "Modern Lunch, Incorporated", 45: "Northern Bank & Trust Company", 53: "Eastern Bank",
    54: "Eagle Bank", 61: "Rockland Trust Company", 64: "TJ Liquor Mart, LLC",
    66: "Seaport B/C Retail Owner LLC", 67: "Boston Local Development Corporation", 68: "Needham Bank",
    69: "Middlesex Savings Bank", 73: "Rockland Trust Company", 75: "Eagle Bank",
    81: "500 Boylston & 222 Berkeley TRS", 82: "907 Boylston Street LLC",
    83: "NW 230 Congress Street Property Owner LLC", 84: "Lesser Trust, LLC",
    85: "Northern Bank & Trust", 86: "Newburyport Five Cents Savings Bank", 90: "Hood Park, LLC",
    98: "163 Newbury, LLC", 101: "First-Citizens Bank & Trust Company",
    102: "Lendlease Clippership Wharf, LLC", 106: "North Shore Bank", 107: "Rockland Trust Company",
    108: "Harris South End, LLC", 109: "Donato & Gianni, LLC", 117: "JPMorgan Chase Bank, N.A.",
    122: "Rockland Trust Company", 125: "P-12 Property, LLC",
}
PARTIES = {
    10: ([("Wen Dong Chen", None, 50, "President"), ("Limin Chen", None, 50, "Secretary, Director")],
         [("Limin Chen", None, 100, "President")]),
    48: ([("Rongchen Li", 50, None, "shareholder")], [("Yuchen Yu", 100, None, "shareholder")]),
    92: ([("Erdal Cicekci", None, 100, None)], [("Ayhan Ayna", None, 100, None)]),
    95: ([("George Alepedis", 100, None, "President")], [("Efharis Alepedis", 100, None, "President")]),
    96: ([("Van Che", 50, None, None), ("Trinh Nguyen", 50, None, None)], [("Trinh Nguyen", 100, None, "Shareholder")]),
    97: ([("Ronald Covitz", None, None, None)], [("Jay Covitz", None, None, None)]),
    112: ([("Elizabeth Kamio", None, None, None)], [("Anthony Ackil", None, None, None)]),
    113: ([("Elizabeth Kamio", None, None, None)], [("Anthony Ackil", None, None, None)]),
    114: ([("Jessica Cheip", 37.5, None, None), ("NGN Partners", 25, None, None), ("Ronald Liu", 37.5, None, None)],
          [("Jessica Chiep", 51, None, None), ("Ronald Liu", 49, None, None)]),
    115: ([("John Chang", 33.3, None, None), ("Ken Shing Lai", 33.3, None, None), ("Ronald Wong", 33.3, None, None)],
          [("John Chang", 100, None, None)]),
    116: ([("Erin Rossas", 51, None, None), ("Manuel Fernado Rosas", 49, None, None)],
          [("Manuel Fernando Rosas", 100, None, None)]),
    130: ([("Vasillios Stefanopoulos", None, None, None)], [("East Boston Pizza Inc.", None, None, None)]),
}


def norm(value):
    return re.sub(r"\s+", " ", value).strip() if value else None


def dump(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def parties(item, number):
    raw = item["item_text"]
    text = norm(raw)
    heading = item["heading"]
    header = re.split(r"License\s*#", raw, flags=re.I)[0]
    lines = [x.strip() for x in header.splitlines() if x.strip()]
    dba = next((x.split(":", 1)[1].strip() for x in lines[1:] if x.lower().startswith("doing business as:")), None)
    address = next((x for x in lines[1:] if re.match(r"\d", x)), None)
    target = target_dba = target_address = None
    if number in TRANSFERS:
        clause = re.split(r"transfer the license", text, maxsplit=1, flags=re.I)[1]
        tail = re.split(r"\bTo\s*:\s*", clause, maxsplit=1, flags=re.I)[1]
        dba_match = re.search(r"\bd\s*/?\s*b\s*/?\s*a\s+", tail, re.I)
        if dba_match:
            target = tail[:dba_match.start()].strip()
            rest = tail[dba_match.end():]
            target_dba = re.split(r"\s*\((?:at the )?same location\)|\s+located\b|;|,\s*\d", rest, maxsplit=1, flags=re.I)[0].strip()
        else:
            target = re.split(r"\s*\((?:at the )?same location\)|\s+located\b", tail, maxsplit=1, flags=re.I)[0].strip()
        dest = re.search(r"\blocated(?: at)?\s+(.+?\b\d{5}\b)", tail, re.I)
        if re.search(r"\((?:at the )?same location\)", tail, re.I):
            target_address = address
        elif dest:
            target_address = dest[1]
    if number in {38, 73, 93}:
        heading, dba, address = {
            38: ("Itadaki, LLC", "Itadaki", "267 - 269 Newbury St., Boston, MA 02116"),
            73: ("Vinna’s, LLC", "Chauncey Liquors", "3096-3104 Washington St., Roxbury, MA 02119"),
            93: ("House of Siam Inc.", "House of Siam on Tremont", "592A - 592 Tremont St., Roxbury, MA 02118"),
        }[number]
        if number in {38, 73}:
            target_address = address
    if number in {14, 29, 30, 55, 70, 78, 93}:
        target_address = {
            14: "329 Huntington Avenue Boston, MA 02115", 29: "5 Copley Place, Boston, MA 02116",
            30: "383 Dorchester Avenue, Boston, MA 02127", 55: "222 Stuart Street, Boston, MA 02116",
            70: "417‑423C West Broadway, South Boston, MA, 02127",
            78: "223 Adams Street Dorchester, MA 02122", 93: "223 Adams Street Dorchester, MA 02122",
        }[number]
    if number == 29:
        target = "Neiman Marcus Group LLC"
    if number == 84:
        target_dba = "Metro"
    if number == 127:
        target_dba = "Zaku"
    if number == 128:
        target_dba = "F1 Arcade"
    return heading, dba, address, target, target_dba, target_address


def common(item):
    raw = item["item_text"]
    match = re.search(r"(?mi)^\s*(Granted\b[^\n]*|Deferred\b[^\n]*|Acknowledged\b[^\n]*)", raw)
    assert match, item["candidate_id"]
    # Retain following conditions, but not the next unrelated section heading.
    decision = re.split(r"\n\s*_+|\n\s*The [Ff]ollowing|\n\s*Non-Hearing", raw[match.start():], maxsplit=1)[0].strip()
    status = match[1].split()[0].lower().rstrip(",")
    license_number = item["license_numbers"][0] if len(item["license_numbers"]) == 1 else None
    return {**item, "document_vote_date": item["archive_date"], "date": item["archive_date"],
            "license_number": license_number, "license_num": license_number.replace("-", "") if license_number else None,
            "outcome": status, "disposition": status, "outcome_text": decision,
            "decision_bearing": True, "board_granted_application": status == "granted",
            "completed_sale_verified": False, "ambiguity_notes": []}


def main():
    candidates = json.loads((ROOT / "candidates.json").read_text())
    # A wrapped occupancy figure "45." was mistaken for an item number. Visual page review
    # confirms it is the continuation of item 24, including its pledge and disposition.
    candidates[90]["item_text"] += "\n" + candidates[91]["item_text"]
    candidates[90]["page_end"] = candidates[91]["page_end"]
    candidates[90]["item_text_sha256"] = hashlib.sha256(candidates[90]["item_text"].encode()).hexdigest()
    for item in candidates:
        item["item_text"] = re.split(r"\n\s*(?:The [Ff]ollowing|Non-Hearing|Transactional Hearing)", item["item_text"], maxsplit=1)[0].rstrip()
        item["page_end"] = item["page_start"] + item["item_text"].count("\f")
        item["item_text_sha256"] = hashlib.sha256(item["item_text"].encode()).hexdigest()
    events, ownership, notices, excluded, review = [], [], [], [], []
    for n, item in enumerate(candidates):
        classification = []
        if n in TRANSFERS or n in PLEDGES or n in OWNERSHIP or n in {4, 39, 100}:
            record = common(item)
            name, dba, address, target, target_dba, destination = parties(item, n)
            record.update(licensee_heading=name, licensee=name, licensee_dba=dba, from_address=address)
            if n == 3:
                record["ambiguity_notes"].append("The PDF visibly prints LB-9216; retained without inferring a missing digit or matching to a different roster ID.")
            if n == 90:
                record["ambiguity_notes"].append("Full item 24 joins a wrapped occupancy figure '45.' that the initial parser treated as a new item; visually verified on page 11.")
            if n in {38, 73, 93}:
                record["ambiguity_notes"].append("The opening reference to a prior deferral is historical context; this document's explicit final disposition is Granted.")
            if n == 84:
                record["ambiguity_notes"].append("Petition proposes d/b/a U-Bahn; decision grants with d/b/a Metro.")
            if n == 127:
                record["ambiguity_notes"].append("Transfer clause gives Shun’s Kitchen; same petition changes d/b/a to Zaku and is granted.")
            if n == 128:
                record["ambiguity_notes"].append("Petition proposes d/b/a F1 Club; decision grants with d/b/a F1 Arcade.")
            if n in {81, 122, 125}:
                record["ambiguity_notes"].append("Explicit grant condition retained in outcome_text; condition satisfaction and transaction closing are not established.")
            if n in TRANSFERS:
                assert target and destination, (n, target, destination)
                events.append({**record, "event_id": item["candidate_id"] + "-transfer", "event_type": "license_transfer",
                               "action_subtype": "transfer_application_disposition", "transferor": name, "transferor_dba": dba,
                               "transferee": target, "transferee_dba": target_dba, "to_address": destination,
                               "license_scope": "explicit_alcohol"})
                classification.append("license_transfer_application")
            if n in PLEDGES:
                recipient = PLEDGES[n]
                assert norm(recipient).rstrip(".") in norm(item["item_text"]), (n, recipient)
                events.append({**record, "event_id": item["candidate_id"] + "-pledge", "event_type": "license_pledge",
                               "action_subtype": "pledge_application_disposition", "licensee": target if n in TRANSFERS else name,
                               "licensee_dba": target_dba if n in TRANSFERS else dba, "pledge_recipient": recipient,
                               "license_scope": "explicit_alcohol"})
                classification.append("license_pledge_application")
            if n in {4, 100}:
                subject, subject_dba, addr, lender = {
                    4: ("Tom Yum Yang, Inc.", None, "156 Harvard Ave., Allston, MA 02134", "East Cambridge Savings Bank (formerly Patriot Community Bank)"),
                    100: ("Newa Liquors, Inc.", "Walsh Wine & Spirits", "388 Washington Street, Brighton, MA 02135", "Alfa Wines, Inc."),
                }[n]
                events.append({**record, "event_id": item["candidate_id"] + "-release", "event_type": "license_pledge",
                               "action_subtype": "pledge_release_acknowledgment", "licensee": subject, "licensee_heading": subject,
                               "licensee_dba": subject_dba, "from_address": addr, "pledge_recipient": lender})
                classification.append("pledge_release_acknowledgment")
            if n in OWNERSHIP:
                text = norm(item["item_text"])
                actions = []
                if re.search(r"ownership", text, re.I):
                    actions.append("ownership_interest_change")
                if re.search(r"change (?:in|of) (?:Ownership and )?Stock Interest", text, re.I):
                    actions.append("stock_interest_change")
                if re.search(r"Transfer the Stock Interest", text, re.I):
                    actions.append("stock_transfer")
                if n in {10, 48, 92}:
                    actions.append("stockholder_change")
                if n in {58, 59}:
                    actions.append("corporate_structure_change")
                if n in {112, 113}:
                    actions.append("corporate_name_change")
                assert actions, n
                scope = "explicit_alcohol" if re.search(r"(?:alcohol|wines?|malt|brewery)", text.split("has petition")[0], re.I) else "common_victualler_no_alcohol_stated"
                own = {**record, "event_id": item["candidate_id"] + "-ownership", "event_type": "ownership_interest",
                       "event_subtype": "ownership_application_disposition", "action_subtype": "ownership_application_disposition",
                       "entity_name": name, "entity_dba": dba, "license_scope": scope, "actions": actions,
                       "parties_before": [], "parties_after": [], "entity_before": None, "entity_after": None,
                       "entity_conversion_explicit": n in {58, 59}, "ownership_subject_entity": name,
                       "ownership_subject_scope": "licensee", "equity_change_completion_verified": False}
                if n in PARTIES:
                    for key, values in zip(["parties_before", "parties_after"], PARTIES[n]):
                        for party, percentage, quantity, role in values:
                            assert party in text, (n, party)
                            own[key].append({"name": party, "interest_percent": percentage, "interest_quantity": quantity,
                                             "interest_unit": "shares" if quantity is not None else None,
                                             "role": role, "source_quote": item["item_text"]})
                    own["ambiguity_notes"].append("Only stated ownership parties/quantities are retained; no assumption of a complete capitalization table or completed equity transfer.")
                else:
                    own["ambiguity_notes"].append("No before/after equity holders or percentages are identified; manager/officer names are not inferred to be owners.")
                if n in {58, 59}:
                    own.update(entity_before="Facility Concession Services Inc.", entity_after="Facility Concession Services LLC")
                if n in {112, 113}:
                    own.update(entity_before="Kaizen Corp" if n == 112 else "Kaizen Corp VIII", entity_after="Anna's Taqueria, LLC")
                    own["ambiguity_notes"].append("Source describes a corporate name change between differently styled entities; it does not explicitly identify the legal conversion mechanism.")
                if n == 114:
                    own["ambiguity_notes"].append("Source spells the before party Jessica Cheip and after party Jessica Chiep; both spellings are preserved without resolving identity.")
                if n == 116:
                    own["ambiguity_notes"].append("Source spells before-party names Erin Rossas and Manuel Fernado Rosas, and after-party name Manuel Fernando Rosas; preserved as printed.")
                if n in {10, 48}:
                    own["entity_name"], own["entity_dba"] = ("Bread Top, Inc.", "Top Bread") if n == 10 else ("SE Investment, LLC", "Sama X Edena")
                    own["ownership_subject_entity"] = own["entity_name"]
                    own["ambiguity_notes"].append("License ID is absent from this non-hearing Common Victualler amendment item.")
                ownership.append(own)
                classification.append("ownership_interest_application")
            if n == 39:
                notices.append({**record, "event_id": item["candidate_id"] + "-notice", "event_type": "prospective_transfer_or_status_notice",
                                "action_subtype": "prospective_transfer_or_status_notice", "licensee": "Cachi, LLC", "licensee_dba": "La Cancun",
                                "from_address": "192½ Summer St., East Boston, MA 02128", "board_granted_application": False,
                                "ambiguity_notes": ["Closure and intent to transfer are acknowledged; this item does not approve a transfer. Source prints Summer St.; later transfer petition prints Sumner St."]})
                classification.append("prospective_transfer_notice")
        elif n == 74:
            notices.append({**item, "event_id": item["candidate_id"] + "-notice", "event_type": "ownership_interest",
                            "event_subtype": "informational_ownership_hearing", "action_subtype": "informational_ownership_hearing",
                            "license_number": "LB-138053", "license_num": "LB138053", "date": item["archive_date"],
                            "document_vote_date": item["archive_date"], "decision_bearing": False,
                            "outcome": "further_hearing_to_be_scheduled", "disposition": "further_hearing_to_be_scheduled",
                            "outcome_text": "Board to schedule transactional hearing on d/b/a change and will seek further information on new concept and partnership at that time\nCancellation hearing to be scheduled should the License not be put to use",
                            "board_granted_application": False, "equity_change_completion_verified": False,
                            "ambiguity_notes": ["Informational oversight hearing; no ownership transfer or cancellation is approved by this item."]})
            classification.append("informational_ownership_hearing")
        else:
            reason = {11: "Keyword occurs only in following section heading, not this hours-change item.",
                      12: "Explicit Innholder No Liquor license transfer; outside alcohol-transfer corpus.",
                      49: "Lodging House license transfer; outside alcohol-transfer corpus.",
                      91: "Continuation merged with prior candidate 90 after visual verification; not a separate item.",
                      121: "Common ownership describes patio property, with no ownership-change application."}.get(n, "Stockroom/stock describes premises inventory, not equity or license transfer.")
            excluded.append({**item, "exclusion_reason": reason})
            classification.append("excluded")
        review.append({"candidate_id": item["candidate_id"], "classification": classification})
    # Expanded keyword audit adds this name-only amendment, not an equity-change assertion.
    extra = next(x for x in json.loads((ROOT / "all-items.json").read_text()) if x["candidate_id"] == "BLB-2023-01-05-043")
    excluded.append({**extra, "exclusion_reason": "Source says change owner/manager name; does not explicitly state an equity transfer. No ownership change inferred from the name amendment."})
    for name, values in [("events.json", events), ("ownership-interest-events.json", ownership), ("notices.json", notices),
                         ("proposed-events.json", []), ("excluded-candidates.json", excluded), ("review-log.json", review)]:
        dump(name, values)
    coverage = {"year": 2023, "observed_urls": 21, "unique_pdf_hashes": 21, "pages": 277,
                "candidate_items_initial": 131, "candidate_items_after_continuation_merge": 130,
                "expanded_name_amendment_candidate": 1, "decision_events": len(events),
                "main_event_subtypes": dict(Counter(e["action_subtype"] for e in events)),
                "main_outcomes": dict(Counter(e["outcome"] for e in events)),
                "ownership_decisions": len(ownership), "ownership_outcomes": dict(Counter(e["outcome"] for e in ownership)),
                "ownership_scopes": dict(Counter(e["license_scope"] for e in ownership)),
                "notices": len(notices), "proposals_or_ambiguous_outcomes": 0,
                "excluded_candidates_including_merged_fragment": len(excluded),
                "keyword_lines_uncovered": 0, "text_qc": "All 277 PDF pages have at least 100 extracted non-whitespace characters; no OCR required.",
                "decision_basis": "Every included application has an explicit Granted or Deferred disposition; release items explicitly Acknowledged. Informational and intent notices are separate.",
                "date_conflicts": ["August 17 document's internal transactional hearing heading says Wednesday August 18, 2023, inconsistent with calendar/vote date; vote-date heading matches August 17 archive label.", "May 25 archive anchor title says 5-23-23 while visible label and PDF vote-date heading say May 25."]}
    dump("coverage.json", coverage)
    print(json.dumps(coverage, indent=2))
    print("\nTRANSFEREE REVIEW")
    for e in events:
        if e["event_type"] == "license_transfer":
            print(e["event_id"], e["transferee"], "|", e["transferee_dba"], "|", e["to_address"])


if __name__ == "__main__":
    main()
