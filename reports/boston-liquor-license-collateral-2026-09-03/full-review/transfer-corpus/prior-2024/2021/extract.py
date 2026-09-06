"""Structure reviewed 2021 candidates. No inference of closing or current lien status."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DBA = r"(?<!\w)(?:d\s*/\s*b\s*/\s*a|d\s*/\s*ba\s*/|dba|doing business as)[ \t]*:?[ \t]*"


def clean(s):
    return re.sub(r"\s+", " ", s).strip(" \n_") if s else None


def outcome(raw):
    match = re.search(
        r"(?mi)^\s*(GRANTED\b|DEFERRED\b|DEFER\b|CONTINUED\b|RESCHEDULED\b|WITHDRAWN\b|REJECTED\b|CANCELLED\b|NO ACTION\b|ACKNOWLEDGED\b|TO BE RE-NOTICED\b)",
        raw,
    )
    if not match:
        return "not_stated", None
    value = match[1].lower().replace(" ", "_")
    value = {"defer": "deferred", "to_be_re-noticed": "to_be_re_noticed"}.get(
        value, value
    )
    tail = raw[match.start() :]
    tail = re.split(r"\n\s*_{4,}|\n\s*The following", tail, maxsplit=1, flags=re.I)[0]
    return value, clean(tail)


def holder(c):
    raw = c["item_text"]
    h = re.split(r"License\s*#\s*:", raw, maxsplit=1, flags=re.I)[0]
    h = re.sub(r"^\s*\d+\s*[.) ,]*", "", h)
    m = re.search(DBA, h, re.I)
    name = clean(h[: m.start()]) if m else clean(c["heading"])
    if m:
        rest = h[m.end() :]
        address_start = re.search(
            r"(?:\n\s*(?=\d|LOGAN)|(?<=\S)\s+(?=\d[^\n]*\b(?:ST|Street|AVE|Avenue|DR|HWY|Way|ROAD|Road|PL|Place|Broadway|CANAL|WASHINGTON)\b))",
            rest,
            re.I,
        )
        if address_start:
            dba = clean(rest[: address_start.start()])
            address = clean(rest[address_start.end() :])
        else:
            dba = clean(rest)
            address = None
    else:
        dba = None
        lines = [line.strip() for line in h.splitlines() if line.strip()]
        address = clean(" ".join(lines[1:])) if len(lines) > 1 else None
    if m and not h[m.end() :].splitlines()[0].strip():
        dba = None
        address = clean(h[m.end() :])
    return name, dba, address


def transfer_parties(c):
    name, dba, address = holder(c)
    norm = clean(c["item_text"])
    start = re.search(r"\btransfer the (?:license|licensed business)\b", norm, re.I)
    to = re.search(r"\bTo\s*:\s*", norm[start.end() :], re.I)
    rest = norm[start.end() + to.end() :] if to else ""
    boundary = re.search(
        DBA + r"|;|\s*\(\s*(?:at the |at |the )?same location\)|\s+located\b",
        rest,
        re.I,
    )
    target = clean(rest[: boundary.start()]) if boundary else None
    if not target:
        entity = re.match(
            r"(.+?\b(?:LLC|Inc\.?|Corporation|Corp\.?))(?:[.;]|\s+\d)", rest, re.I
        )
        target = clean(entity[1]) if entity else None
    t_dba = None
    dm = re.search(DBA, rest, re.I)
    if dm:
        drest = rest[dm.end() :]
        if boundary and dm.start() > boundary.start() + 2:
            drest = ""
        stop = re.search(
            r"\s*\(\s*(?:at the |at |the )?same location\)|\s+located\b|\s+\d",
            drest,
            re.I,
        )
        if stop:
            t_dba = clean(drest[: stop.start()]).rstrip(",;")
    if re.search(r"\(\s*(?:at the |at |the )?same location\)", rest, re.I):
        destination = address
    else:
        search_from = (
            rest[len(target) :] if target and rest.startswith(target) else rest
        )
        am = re.search(r"(?:located(?: at)?\s+|\s+)(\d.*?\b\d{5}\b)", search_from, re.I)
        destination = clean(am[1]) if am else None
    return name, dba, address, target, t_dba, destination


OVERRIDES = {
    "BLB-2021-04-01-c044": (
        "EGLESTON LIQUORS, INC.",
        "M & M LIQUORS",
        "3086 WASHINGTON ST ROXBURY, MA 02119",
    ),
    "BLB-2021-04-01-c047": (
        "DIDELLO, INC.",
        "THE WILD DUCK",
        "94 - 96 SALEM ST BOSTON, MA 02113",
    ),
    "BLB-2021-04-01-c048": (
        "NILKANTH VARNI, LLC",
        "RUSTY'S LIQUORS",
        "700 AMERICAN LEGION HWY ROSLINDALE, MA 02131",
    ),
}
# Further review overrides are keyed by source/date/item rather than candidate sequence.
HOLDERS = {
    ("2021-06-24", "1", 8): (
        "ST ORIENTAL CORPORATION",
        "NEW JUMBO SEAFOOD RESTAURANT",
        "5 - 9 HUDSON ST BOSTON, MA 02111",
    ),
    ("2021-06-24", "2", 8): (
        "Pivo Ne Vino LLC",
        "Fenway Beer Shop",
        "98 VAN NESS ST BOSTON, MA 02215",
    ),
    ("2021-07-29", "1", 14): (
        "Retail Beverages Partners - South Bay, Inc.",
        "Liquor Aisle",
        "1100 Massachusetts Ave., Dorchester, MA 02125",
    ),
    ("2021-09-30", "2", 19): (
        "Franco, LLC",
        "Pellino’s Ristorante",
        "2A Prince Street Boston 02113",
    ),
    ("2021-09-30", "3", 20): (
        "Big Bad Dog LLC",
        "Domenic’s",
        "54 Salem Street Boston, MA 02113",
    ),
    ("2021-10-28", "4", 13): (
        "RR, Inc.",
        "Best Liquors",
        "1088 Dorchester Avenue, Dorchester, MA 02125",
    ),
    ("2021-11-04", "2", 7): (
        "Mabrothers, LLC",
        "The Marliave",
        "10-11 Bosworth Street, Boston, MA 02108",
    ),
    ("2021-11-18", "3", 13): (
        "J.T.J. Corporation",
        "Daisy Buchanan’s",
        "240A Newbury Street, Boston, MA 02116",
    ),
    ("2021-12-02", "1", 11): (
        "Bitton LLC",
        "Cafeteria",
        "279A Newbury St., Boston, MA 02115",
    ),
    ("2021-12-02", "2", 12): (
        "Z-Love, LLC",
        "Telegraph Hill",
        "289 Dorchester St., South Boston, MA 02127",
    ),
    ("2021-12-02", "3", 12): (
        "VJP, LLC",
        "The Wine Cave",
        "71 - 75 Canal St., Boston, MA 02114",
    ),
    ("2021-12-16", "2", 15): (
        "Auditorium Cafe, Inc.",
        "The Pour House",
        "909 Boylston St., Boston, MA 02115",
    ),
}


def main():
    events = []
    own = []
    notices = []
    excluded = []
    proposed = []
    reviewed = json.loads((ROOT / "review-overrides.json").read_text())
    source_pages = {
        entry["source_id"]: json.loads((ROOT / entry["pages_path"]).read_text())
        for entry in json.loads((ROOT / "source-index.json").read_text())
    }
    for original in json.loads((ROOT / "candidates.json").read_text()):
        c = dict(original)
        raw = c["item_text"]
        following = re.search(
            r"(?mi)^\s*(?:Transactional Hearing|Licensed Premise Inspection Hearing|License Premise Inspection Hearing|Non[- ]?hearing Transaction|The following (?:is|are|has|have)|Old (?:&|and) New Business|ALL ONE DAY SPECIAL)",
            raw,
        )
        if following:
            raw = raw[: following.start()].rstrip(" \n\t_")
            c["item_text"] = raw
            selected = [
                p
                for p in source_pages[c["source_id"]]
                if c["page_start"] <= p["page"] <= c["page_end"]
            ]
            parts = [clean(p["text"].replace("\u200b", "")) or "" for p in selected]
            joined = " ".join(parts)
            item_end = joined.index(clean(raw)) + len(clean(raw)) - 1
            offset = 0
            for page, part in zip(selected, parts):
                if item_end < offset + len(part):
                    c["page_end"] = page["page"]
                    break
                offset += len(part) + 1
        norm = clean(raw)
        date = c["archive_date"]
        key = (date, c["item_number"], c["page_start"])
        status, stext = outcome(raw)
        lic = c["license_numbers"][0] if len(c["license_numbers"]) == 1 else None
        notes = []
        common = {
            **{
                k: c[k]
                for k in [
                    "candidate_id",
                    "source_id",
                    "source_url",
                    "source_sha256",
                    "archive_date",
                    "page_start",
                    "page_end",
                    "item_number",
                    "item_text",
                ]
            },
            "date": date,
            "document_vote_date": date,
            "license_number": lic,
            "license_num": lic.replace("-", "") if lic else None,
            "normalized_license_num": lic.replace("-", "") if lic else None,
            "outcome": status,
            "disposition": status,
            "outcome_text": stext,
            "board_granted_application": status == "granted",
            "decision_bearing": status != "not_stated",
            "completed_sale_verified": False,
            "ambiguity_notes": notes,
            "review_status": "reviewed_against_full_candidate_and_source_context",
        }
        name, dba, address = holder(c)
        name, dba, address = OVERRIDES.get(
            c["candidate_id"], HOLDERS.get(key, (name, dba, address))
        )
        scope = (
            "explicit_alcohol"
            if re.search(
                r"All[-‑ ]*Alcohol|Malt|Wines|Wine|Farmer Winery|CV7", norm, re.I
            )
            else "common_victualler_no_alcohol_stated"
        )
        if (date, c["item_number"], c["page_start"]) == ("2021-02-25", "3", 2):
            notices.append(
                {
                    **common,
                    "event_id": c["candidate_id"] + "-notice",
                    "event_type": "ownership_information_hearing",
                    "licensee": "Caffe Paradiso, Inc.",
                    "license_scope": scope,
                }
            )
            continue
        if (date, c["item_number"], c["page_start"]) == ("2021-04-01", "6", 2):
            notes.append(
                "The source describes an alleged unapproved beneficial-interest/management change. The cancellation decision does not verify that a sale or transfer closed."
            )
            notices.append(
                {
                    **common,
                    "event_id": c["candidate_id"] + "-notice",
                    "event_type": "license_cancellation",
                    "licensee": "Churrascaria Vulcao, LLC",
                    "license_scope": scope,
                }
            )
            continue
        if re.search(r"intent to\s+transfer", norm, re.I):
            notices.append(
                {
                    **common,
                    "event_id": c["candidate_id"] + "-notice",
                    "event_type": "prospective_transfer_or_status_notice",
                    "licensee_heading": c["heading"],
                    "license_scope": scope,
                }
            )
            continue
        tr = (
            bool(
                re.search(
                    r"has petitioned.*?\btransfer the (?:license|licensed business)\b",
                    norm,
                    re.I,
                )
            )
            and scope == "explicit_alcohol"
        )
        pl = bool(re.search(r"\bpledge (?:of )?(?:the )?license\b", norm, re.I))
        if date == "2021-09-02" and c["item_number"] == "3":
            tr = False
            notes.append(
                "The prior transfer and stock/inventory pledge are historical context; only the additional license-pledge petition receives the withdrawn disposition here."
            )
        if tr:
            pn, pd, pa, target, td, ta = transfer_parties(c)
            overrides = reviewed["transfers"].get(
                date + "|" + str(common["license_num"]), {}
            )
            td = overrides.get("transferee_dba", td)
            ta = overrides.get("to_address", ta)
            if name != pn or address != pa:
                ta = (
                    address
                    if re.search(
                        r"\(\s*(?:at the |at |the )?same location\)", norm, re.I
                    )
                    else ta
                )
            if (
                date == "2021-09-30"
                and c["item_number"] == "3"
                and c["page_start"] == 20
            ):
                target = "Witchcraft LLC"
                td = "New England Witchcraft Company"
                notes.append(
                    "The item separately grants transfer and a DBA amendment from Witchcraft on Salem to New England Witchcraft Company; the final granted DBA is retained."
                )
            if "transfer the licensed business" in norm.lower():
                notes.append(
                    "Source says 'transfer the licensed business' in an alcohol-license holder petition."
                )
            if lic is None:
                notes.append(
                    "No license number is stated in this item. No identifier is imputed from another meeting."
                )
            ev = {
                **common,
                "event_id": c["candidate_id"] + "-transfer",
                "event_type": "license_transfer",
                "action_subtype": "transfer_application_disposition",
                "transferor": name,
                "transferor_dba": dba,
                "transferee": target,
                "transferee_dba": td,
                "from_address": address,
                "to_address": ta,
                "pledge_recipient": None,
            }
            ev["parties"] = {"transferor": name, "transferee": target}
            (events if common["decision_bearing"] else proposed).append(ev)
        if pl:
            pm = re.search(
                r"\bpledge (?:of )?(?:the )?license(?:\s*(?:/|,|and|, and)\s*(?:inventory|stock))*\s*[-:]?\s*to\s*[-:]?\s*(.*?)(?=\s+Attorney:|\s+Manager:|\s+Closing Time:|\s+GRANTED\b|\s+DEFER(?:RED)?\b|\s+CONTINUED\b|\s+RESCHEDULED\b|\s+WITHDRAWN\b|\s+REJECTED\b|$)",
                norm,
                re.I,
            )
            recipient = clean(pm[1]).rstrip(" .") if pm and pm[1].strip() else None
            if date == "2021-10-07" and c["item_number"] == "15":
                recipient = None
                notes.append(
                    'The source ends the pledge clause with "to" and supplies no pledge recipient; the attorney is not treated as the recipient.'
                )
            ev = {
                **common,
                "event_id": c["candidate_id"] + "-pledge",
                "event_type": "license_pledge",
                "action_subtype": "pledge_application_disposition",
                "licensee": target if tr else name,
                "licensee_dba": td if tr else dba,
                "from_address": address,
                "pledge_recipient": recipient,
            }
            ev["parties"] = {"licensee": ev["licensee"], "pledge_recipient": recipient}
            (events if common["decision_bearing"] else proposed).append(ev)
        actions = []
        if (
            re.search(r"change.*?ownership|ownership.*?interest", norm, re.I)
            and "petition" in norm.lower()
        ):
            actions.append("ownership_interest_change")
        if re.search(
            r"(?:change|transfer|issuance).*?\bstock\b", norm, re.I
        ) and not re.search(r"pledge the Stock", norm, re.I):
            actions.append("stock_interest_change")
        if re.search(r"New Stockholders", norm, re.I):
            actions.append("new_stockholders")
        if re.search(r"change.*?beneficial interest", norm, re.I):
            actions.append("beneficial_interest_change")
        if re.search(r"corporate structure", norm, re.I):
            actions.append("corporate_structure_change")
        # Stock in premise descriptions and collateral pledges is not an equity transfer.
        if not re.search(
            r"petitioned.*?(?:change of Stock|change in Stock|change of Ownership|change in Ownership|change/transfer of stock|Change in Stock|change of Beneficial|change in Beneficial|transfer the stock|change the Corporate Structure|change of Officers/Directors and Ownership|change of Stock/Ownership|change of Ownership & Stock|a change of Stock)",
            norm,
            re.I,
        ):
            if not re.search(
                r"New Stockholders|change of Officer/Director.*?transfer of Stock",
                norm,
                re.I,
            ):
                actions = []
        own_override = reviewed["ownership"].get("|".join(map(str, key)))
        if own_override:
            actions = own_override["actions"]
            name = own_override["entity_name"]
            dba = own_override["entity_dba"]
        if actions:
            onotes = list(notes) + [
                "Board approval alone does not establish a completed equity transaction, current ownership/control, or private-equity sponsorship.",
                "No shareholder/beneficial-owner names or ownership percentages are stated for this action; manager names are not substituted.",
            ]
            ev = {
                **common,
                "ambiguity_notes": onotes,
                "event_id": c["candidate_id"] + "-ownership",
                "event_type": "ownership_interest",
                "event_subtype": "ownership_application_disposition",
                "actions": list(dict.fromkeys(actions)),
                "entity_name": name,
                "entity_dba": dba,
                "license_scope": scope,
                "parties_before": [],
                "parties_after": [],
                "equity_change_completion_verified": False,
                "entity_conversion_explicit": False,
                "entity_before": None,
                "entity_after": None,
                "ownership_subject_entity": name,
                "ownership_subject_scope": "licensee_entity",
                "parties": {"licensee": name},
            }
            if "corporate_structure_change" in actions:
                ev.update(
                    {
                        "entity_conversion_explicit": True,
                        "entity_before": "Lunas Restaurant LLC",
                        "entity_after": "Lunas Restaurant Corporation",
                        "entity_change_source_quote": "Corporate Structure of the licensed business – From: Lunas Restaurant LLC To: Lunas Restaurant Corporation.",
                        "ownership_subject_scope": "licensee_entity_form_conversion",
                    }
                )
                ev["ambiguity_notes"].append(
                    "Entity-form conversion is explicit; no change of beneficial control is inferred."
                )
            if own_override:
                ev.update(
                    {
                        k: own_override[k]
                        for k in [
                            "entity_name",
                            "entity_dba",
                            "parties_before",
                            "parties_after",
                        ]
                    }
                )
                ev["ambiguity_notes"] = [
                    n
                    for n in ev["ambiguity_notes"]
                    if not n.startswith("No shareholder")
                ]
                ev["ambiguity_notes"] += own_override.get("additional_notes", [])
                ev["ambiguity_notes"].append(
                    "This item is in the Common Victualler changes section and does not state an alcohol license; no linkage to another alcohol record is assumed."
                )
            (own if common["decision_bearing"] else proposed).append(ev)
        if not tr and not pl and not actions:
            why = "other_keyword_context"
            if re.search(r"pledge.*?(?:stock|inventory)", norm, re.I):
                why = "stock_or_inventory_pledge_only"
            elif re.search(r"lodging|No Liquor", norm, re.I):
                why = "non_alcohol_license_transfer"
            elif re.search(
                r"shipping|stock room|cellar for stock|stock in two rooms", norm, re.I
            ):
                why = "premises_description"
            if (
                date == "2021-09-30"
                and c["item_number"] == "12"
                and c["page_start"] == 16
            ):
                why = "manager_change_owner_unchanged"
                notes.append(
                    "James Pinho remains the named owner/manager before and after; adding Kyle Pinho as manager does not state an ownership change."
                )
            excluded.append(
                {
                    **common,
                    "event_id": c["candidate_id"] + "-excluded",
                    "classification": why,
                    "license_scope": scope,
                }
            )
    for file, data in [
        ("events.json", events),
        ("ownership-interest-events.json", own),
        ("notices.json", notices),
        ("proposed-events.json", proposed),
        ("excluded-candidates.json", excluded),
    ]:
        (ROOT / file).write_text(json.dumps(data, indent=2))
    print(
        json.dumps(
            {
                "events": dict(Counter(e["event_type"] for e in events)),
                "outcomes": dict(Counter(e["outcome"] for e in events)),
                "ownership": len(own),
                "notices": len(notices),
                "proposed": len(proposed),
                "excluded": len(excluded),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
