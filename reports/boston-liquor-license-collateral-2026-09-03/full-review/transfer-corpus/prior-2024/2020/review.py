"""Apply source-read review decisions to the retained 2020 candidates."""

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Keys refer to the deterministic page-preserving candidate scan. Party and
# destination text below is transcribed from the associated full source item.
TRANSFERS = {
    "05-21-C002": ("Lee's Quik Pik, Inc.", "Lee's Market", "1591 Commonwealth Avenue Boston, MA 02135"),
    "05-28-C003": ("Nusret Boston, LLC", "Nusret Steakhouse", None),
    "05-28-C004": ("MadMac Partners, LLC", "Sagarino's", None),
    "05-28-C005a": ("Newa Liquors, Inc.", "Walsh Wines & Liquors", "388 Washington Street Brighton, MA 02135"),
    "05-28-C005b": ("Dolce, Inc", "Dolce", "272 Hanover Street Boston, MA 02113"),
    "06-04-C003": ("Capital Burger Holdings, LLC", "The Capital Burger", None),
    "07-16-C017": ("Jwalaji Corp.", "Get N Go", None),
    "07-16-C018": ("Shivam Baba Corp", "Atlas Liquors", None),
    "07-16-C019": ("175 Ipswich Street, LLC", None, "175 Ipswich Street Boston, MA 02215"),
    "07-30-C008": ("Mario Gomes", None, None),
    "08-13-C002": ("Shivam Baba Corp.", None, "591 Hyde Park Avenue"),
    "08-20-C011": ("Elyas, LLC", "Savin Hill Wine & Spirits", None),
    "09-10-C018": ("Power Couple, LLC", "El Burro Restaurant", "69-73 Bennington Street East Boston, MA 02128"),
    "09-10-C019": ("1885 Centre Street, LLC", "Boston Ale House", None),
    "09-17-C016": ("Castaneda Gomez Corporation", "La Fonda Colombiana", None),
    "10-29-C036": ("143 145 Meridian Street, LLC.", None, None),
    "10-29-C037": ("Cummins Highway Liquor Group, Inc.", "Crest Liquors", None),
    "11-05-C003": ("Parcel A Development Lessee, LLC.", "Hampton Inn/Homewood Suites Boston Parcel A", "Raymond F. Flynn Marine Park, 15 Terminal Street (664 Summer Street), Boston, MA 02127"),
    "12-03-C023": ("Huntington Avenue Market, Inc.", "Huntington Market", None),
    "12-03-C028": ("LRTB LLC.", "Little Rose Taco Bar", None),
    "12-23-C013": ("Brasserie 560 LLC.", "Brasserie", None),
    "12-23-C014": ("GTI Properties, Inc.", "The Power Station", "550 Harrison Avenue, Boston, MA 02118"),
    "12-23-C015": ("Pho on Thayer, LLC.", "Pho on Thayer", "B-2 Thayer Street, Boston MA 02118"),
    "12-23-C016": ("Depot Realty LLC.", "Regina Pizza at the Depot", None),
    "12-23-C017": ("Lola Burger Restaurant Boston, LLC.", "Lola Burger", None),
    "12-23-C018": ("Lola 42 Restaurant Boston, LLC", "Lola 42", None),
    "12-23-C019": ("Panda Hot Pot Chinatown, Inc.", "Wei Shu Wu Hot Pot", None),
    "12-23-C020": ("Canal Street Realty LLC", None, None),
}
PLEDGES = {
    "04-30-C003": "Banco de Sabadell, S.A., Miami Branch",
    "04-30-C005": "Eastern Bank",
    "05-28-C005a": "Alfa Wines, Inc.",
    "07-16-C017": "Rockland Trust Company",
    "07-16-C018": "Atlas Liquors, Inc.",
    "08-13-C002": "Atlas Liquors, Inc.",
    "08-20-C011": "North Shore Bank",
    "09-10-C016": "Tremont Construction Management, LLC",
    "09-17-C016": "EBLL1 Holdings, LLC",
    "10-01-C018": "The Cooperative Bank",
    "10-29-C021": "Keybank National Association",
    "10-29-C037": "Newburyport Bank",
    "11-05-C007": "JDS Cap Co., LLC",
    "11-05-C008": "JDS Cap Co., LLC",
    "12-03-C023": "Rockland Trust Company",
    "12-03-C028": "LDJ Development LLC",
}
OWNERSHIP = {
    "04-23-C006": ["stock_interest_change"],
    "07-16-C007": ["ownership_interest_change", "stock_transfer"],
    "07-16-C008": ["ownership_interest_change", "stock_transfer"],
    "07-16-C009": ["ownership_interest_change", "stock_transfer"],
    "07-30-C004": ["stock_interest_change", "ownership_interest_change"],
    "08-20-C007": ["stock_interest_change"],
    "08-20-C008": ["stock_interest_change"],
    "09-17-C012": ["stock_interest_change"],
    "09-17-C020": ["stock_transfer"],
    "10-29-C018": ["ownership_interest_change"],
    "10-29-C019": ["ownership_interest_change"],
    "10-29-C020": ["ownership_interest_change"],
    "10-29-C024": ["stock_interest_change"],
    "10-29-C055": ["stock_transfer"],
    "11-05-C002": ["stock_transfer"],
    "11-05-C004": ["stock_interest_change"],
    "11-05-C005": ["stock_interest_change"],
    "12-03-C011": ["ownership_interest_change"],
    "12-03-C012": ["ownership_interest_change"],
    "12-03-C016": ["ownership_interest_change"],
    "12-03-C017": ["ownership_interest_change"],
    "12-03-C018": ["ownership_interest_change"],
    "12-03-C019": ["ownership_interest_change"],
    "12-03-C020": ["stock_interest_change"],
    "12-03-C038": ["stock_transfer", "shareholder_removal"],
    "12-23-C010": ["ownership_interest_change"],
    "12-23-C012": ["ownership_interest_change"],
}
NOTICES = {
    "08-13-C003": ("prospective_license_transfer_notice", "acknowledged", "Dicks Last Resort of Boston LLC", None),
    "10-08-C001": ("ownership_information_notice", "warning", "Churrascaria Vulcao, LLC", "Churrascaria Vulcao"),
    "10-08-C015": ("prospective_license_transfer_notice", "acknowledged", "In Vino Veritas Bistro LLC", "Les Zygomates Cafe"),
    "10-29-C010": ("ownership_information_hearing", "deferred", "Thailand International Corporation", "House Of Siam"),
    "12-03-C006": ("conditional_license_revocation_directive", "conditional_directive", "Churrascaria Vulcao, LLC", "Churrascaria Vulcao"),
    "12-23-C021": ("new_license_application_ownership_clarification", "deferred", "New Point USA, LLC.", "My Happy Hunan Kitchen"),
}
EXCLUDED = {
    "04-23-C009": "Stock denotes premises storage; only floor-plan and manager changes.",
    "05-21-C007": "Citywide alcohol-with-food condition removal; sale/service is not sale of the license.",
    "07-16-C024": "Floor-plan change; point of sale/service is not sale of the license.",
    "09-10-C030": "Lodging-house license transfers, not alcohol licenses. Full subsection retained.",
    "09-17-C010": "Lodging-house application; Shared laundry is not a shareholding reference.",
    "10-29-C007": "Underage alcohol sale allegation; not sale of the license.",
    "12-03-C024": "Stock denotes premises storage; floor-plan change only.",
    "12-03-C025": "Stock denotes premises storage; floor-plan change only.",
}


def clean(value):
    return " ".join(value.split())


def write(name, data):
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    sources = json.loads((ROOT / "source-index.json").read_text())
    source_map = {s["source_id"]: s for s in sources}
    candidates = json.loads((ROOT / "candidates.json").read_text())
    expanded = []
    for candidate in candidates:
        if candidate["candidate_id"] == "BLB-2020-05-28-C005":
            first, second = candidate["item_text"].split(" PUSHCART CAFE", 1)
            for suffix, block in [("a", first.strip()), ("b", "PUSHCART CAFE" + second)]:
                c = dict(candidate, candidate_id=candidate["candidate_id"] + suffix, item_text=block)
                if suffix == "b":
                    c.update({"item_number": None, "heading": "PUSHCART CAFE"})
                expanded.append(c)
        else:
            expanded.append(candidate)
    events, ownership, notices, proposed, unresolved, excluded = [], [], [], [], [], []
    for c in expanded:
        key = c["candidate_id"].removeprefix("BLB-2020-")
        src = source_map[c["source_id"]]
        text = (ROOT / src["text_path"]).read_text().replace("\u200b", " ").replace("\xa0", " ")
        block = c["item_text"]
        if key == "09-10-C030":
            # The keyword is in the subsection heading, not its three item bodies.
            block = text[c["character_start"]:].split("ONE CITY HALL", 1)[0].strip()
        else:
            block = re.split(r"(?m)^[ \t]*(?:Old & ?New|Non[- ]Hearing|Non Hearing|The following|ONE CITY HALL|Transactional Hearing)", block, maxsplit=1)[0].rstrip()
        start = text.find(block, c["character_start"])
        assert start >= 0, (key, block[:100])
        end = start + len(block)
        c.update({"item_text": block, "page_start": text[:start].count("\f")+1,
                  "page_end": text[:end].rstrip().count("\f")+1})
        matches = list(re.finditer(r"LB\s*[-‐‑–—]?\s*(\d+)", block))
        c["license_ids_raw"] = list(dict.fromkeys(m.group() for m in matches))
        c["license_numbers"] = list(dict.fromkeys(f"LB-{m[1]}" for m in matches))
        licenses = c["license_numbers"]
        c["ambiguity_notes"] = []
        if key in ["05-28-C005a", "05-28-C005b"]:
            c["ambiguity_notes"].append("Manual visual split: unnumbered Pushcart Cafe follows numbered Alfa Wines item 5; the separate Granted and Deferred outcomes were checked on PDF page 2.")
        base = {k: c[k] for k in ["source_id", "source_url", "source_urls", "archive_date", "page_start", "page_end", "item_number", "item_text", "ambiguity_notes"]}
        base.update({"candidate_id": c["candidate_id"], "date": src["archive_date"], "document_vote_date": src["archive_date"],
                     "license_number": licenses[0] if len(licenses)==1 else None,
                     "license_num": licenses[0] if len(licenses)==1 else None,
                     "license_id_raw": c["license_ids_raw"][0] if len(matches)==1 else None,
                     "source_quote": block})
        outcome_match = re.search(r"(?im)(?:^|(?<=\f))[ \t]*(Granted|Grated|Deferred|Defer|Acknowledged)\b", block)
        if outcome_match:
            literal = outcome_match[1].lower()
            base["outcome"] = {"defer": "deferred", "grated": "ambiguous_printed_grated"}.get(literal, literal)
            base["outcome_text"] = block[outcome_match.start():].strip()
        else:
            base.update({"outcome": "not_stated", "outcome_text": None})
        entity = c["heading"]
        dba_match = re.search(r"(?im)^[ \t]*D/B/A:[ \t]*([^\n]*)", block)
        dba = dba_match[1].strip() or None if dba_match else None
        address = None
        if dba_match:
            after_dba = block[dba_match.end():]
            address = clean(after_dba.split("License",1)[0])
        if key == "08-13-C002":
            entity, dba, address = "Atlas Liquors, Inc.", None, "591 Hyde Park Avenue"
            base["ambiguity_notes"].append("This item states no LB identifier; the apparent July 16 repeat is noted but its LB number is not silently copied. The introductory past deferral is followed by the current GRANTED outcome.")
        if key in TRANSFERS or key in PLEDGES:
            assert base["outcome"] in ["granted", "deferred"], key
            base.update({"decision_bearing": True, "license_scope": "alcohol_stated",
                         "transferor": entity, "transferor_dba": dba, "from_address": address,
                         "transferee": None, "transferee_dba": None, "to_address": None})
            if key in TRANSFERS:
                to, to_dba, to_address = TRANSFERS[key]
                base.update({"transferee": to, "transferee_dba": to_dba, "to_address": to_address or address})
                if key == "11-05-C003":
                    base["ambiguity_notes"].append("The source prints 'Hampton Inn/Homewood Suites Boston Parcel A, Raymond F. Flynn Marine Park' without a delimiter between Boston and Parcel A. The captured DBA may include part of the premises designation; the full source text controls.")
                event = dict(base, event_id=c["candidate_id"]+"-transfer", event_type="license_transfer",
                             event_subtype="license_transfer_application_disposition", actions=["license_transfer"])
                events.append(event)
            if key in PLEDGES:
                event = dict(base, event_id=c["candidate_id"]+"-pledge", event_type="license_pledge",
                             event_subtype="license_pledge_application_disposition", actions=["license_pledge"],
                             pledge_recipient=PLEDGES[key], pledging_entity=base["transferee"] or entity)
                events.append(event)
            c["review_classification"] = "transfer_or_pledge_application_disposition"
        elif key in OWNERSHIP:
            event = dict(base, event_id=c["candidate_id"]+"-ownership", event_type="ownership_interest",
                         event_subtype="ownership_application_disposition", actions=OWNERSHIP[key],
                         entity_name=entity, entity_dba=dba, address=address, parties_before=[], parties_after=[],
                         entity_before=None, entity_after=None, entity_conversion_explicit=False,
                         ownership_subject_entity=entity, ownership_scope="licensee_entity",
                         decision_bearing=True, equity_change_completion_verified=False,
                         license_scope="alcohol_stated")
            if key in ["04-23-C006", "08-20-C007", "08-20-C008"]:
                event["ambiguity_notes"].append("The source uses combined issuance/transfer wording; stock_interest_change records that explicit petition without asserting that both issuance and transfer separately occurred or identifying unnamed owners.")
                event["stock_action_wording"] = "Issuance/Transfer of Stock/New Stockholder" if key != "08-20-C008" else "issuance/transfer of stock"
            if key == "08-20-C007":
                event["ancillary_stock_pledge_recipient"] = "Rahul Jashvant Bilodariya"
                event["ambiguity_notes"].append("The stock pledge is ancillary to the explicit stock-interest application. It is not a license pledge and does not establish that the recipient owns shares.")
            if key in ["09-17-C020", "10-29-C055", "12-03-C038"]:
                event["license_scope"] = "common_victualler_no_alcohol_stated"
                short = {"09-17-C020": ("H & L Boston, Inc.", "Our Zone"), "10-29-C055": ("Ogawa Coffee, USA, Inc.", "Ogawa Coffee"), "12-03-C038": ("Asmabanu Enterprises, Inc.", "J.M.P. Fine Indian Cuisine")}[key]
                event.update({"entity_name": short[0], "entity_dba": short[1], "ownership_subject_entity": short[0]})
            if key == "10-29-C055":
                event["parties_after"] = [{"name": "Yoshinori Uda", "interest_percent": 100, "interest_quantity": None, "interest_unit": None, "role": "stock transferee", "source_quote": "petitioned to transfer 100% of the stock of the corporation to Yoshinori Uda."}]
                event["ambiguity_notes"].append("The outgoing manager/officer is not identified as the prior stock owner; parties_before remains empty.")
            if key == "12-03-C038":
                event["parties_before"] = [{"name": "Sarfaraz Jinwala", "interest_percent": None, "interest_quantity": None, "interest_unit": None, "role": "shareholder proposed for removal", "source_quote": "has petitioned to remove shareholder Sarfaraz\n               Jinwala."}]
                event["ambiguity_notes"].append("The disposition is visibly printed 'Grated' on PDF page 8. It appears in the disposition position but is not silently normalized to Granted; the exact printed outcome is unresolved.")
                event["outcome_normalization_uncertain"] = True
            if key in ["12-03-C016", "12-03-C017", "12-03-C018", "12-03-C019"]:
                event["ambiguity_notes"].append("The source repeats ownership-interest entries for the same two Del Frisco's licenses (items 10/12 and 11/13). Each source occurrence is retained; this is not a distinct transaction count.")
            if key == "12-03-C038":
                event["decision_bearing"] = False
                unresolved.append(event)
                c["review_classification"] = "unresolved_ownership_disposition_wording"
            else:
                ownership.append(event)
                c["review_classification"] = "ownership_application_disposition"
        elif key in NOTICES:
            subtype, outcome, name, notice_dba = NOTICES[key]
            event = dict(base, event_id=c["candidate_id"]+"-notice", event_type="notice", event_subtype=subtype,
                         entity_name=name, entity_dba=notice_dba, outcome=outcome,
                         decision_bearing=key not in ["08-13-C003", "10-08-C015"],
                         actions=[subtype], establishes_ownership_change=False, establishes_license_transfer=False)
            if key == "10-08-C001":
                event["outcome_text"] = clean(block[block.index("Second warning"):])
            if key == "12-03-C006":
                event["outcome_text"] = clean(block[block.index("Licensee has seven"):])
                event["ambiguity_notes"].append("Revocation is conditional on later failure to supply adequate records. This document does not establish that the condition occurred or that the license was ultimately revoked.")
            if key == "12-23-C021":
                event["ambiguity_notes"].append("A new license application is deferred to clarify ownership and a previous transaction; it is not an explicit application to change ownership interest.")
            notices.append(event)
            c["review_classification"] = "notice_or_related_directive"
        elif key in EXCLUDED:
            c.update({"review_classification": "excluded", "exclusion_reason": EXCLUDED[key]})
            excluded.append(dict(c))
        else:
            raise ValueError(f"Unreviewed candidate: {key}")
    assert len(events)==44 and len(ownership)==26 and len(unresolved)==1 and len(notices)==6 and len(excluded)==8
    for entry in sources:
        canonical = source_map[entry.get("duplicate_of", entry["source_id"])]
        text = (ROOT / canonical["text_path"]).read_text()
        date_match = re.search(r"Voting(?: Hearing)? Agenda[\s,]+([A-Z][a-z]+ \d{1,2}, 2020)", text)
        assert date_match, entry["source_id"]
        date = datetime.strptime(date_match[1], "%B %d, %Y").date().isoformat()
        entry.update({"document_vote_date": date, "document_heading_quote": date_match[0],
                      "archive_date_matches_document_heading": date==entry["archive_date"],
                      "decision_bearing_document": True, "text_reviewed": True})
    write("source-index.json", sources)
    write("reviewed-candidates.json", expanded)
    write("events.json", events)
    write("ownership-interest-events.json", ownership)
    write("notices.json", notices)
    write("proposed-events.json", proposed)
    write("unresolved-events.json", unresolved)
    write("excluded-candidates.json", excluded)
    counts = {"transfer_pledge": dict(Counter(e["event_type"] for e in events)),
              "transfer_pledge_outcomes": dict(Counter(e["outcome"] for e in events)),
              "ownership_outcomes": dict(Counter(e["outcome"] for e in ownership)),
              "ownership_license_scope": dict(Counter(e["license_scope"] for e in ownership)),
              "ownership_actions": dict(Counter(a for e in ownership for a in e["actions"])),
              "notice_subtypes": dict(Counter(e["event_subtype"] for e in notices))}
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
