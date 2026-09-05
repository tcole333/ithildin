"""Emit reviewed 2022 decisions, keeping applications and notices distinct."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def clean(s):
    return re.sub(r"\s+", " ", s).strip(" \t\n_") if s else None


def result(raw):
    m = re.search(
        r"(?mi)^\s*(Granted[^\n]*|Deferred[^\n]*|Continued[^\n]*|Withdrawn[^\n]*|Rejected[^\n]*|Acknowledged[^\n]*|Denied[^\n]*|License Canceled[^\n]*)",
        raw,
    )
    if not m:
        return "not_stated", None
    status = (
        "granted"
        if m[1].startswith("Granted")
        else "canceled"
        if m[1].startswith("License Canceled")
        else m[1].split()[0].lower()
    )
    # Preserve subsequent conditions/corrections to the same item, not a following section header.
    decision = re.split(
        r"\n\s*_{5,}|\n\s*Non-Hearing Transactions|\n\s*The [Ff]ollowing|\n\s*All Special",
        raw[m.start() :],
        maxsplit=1,
    )[0]
    return status, clean(decision)


def parties(c):
    raw = c["item_text"]
    text = clean(raw)
    header = re.split(r"License\s*#", raw, flags=re.I)[0]
    lines = [line.strip() for line in header.splitlines() if line.strip()]
    name = c["heading"]
    dba = address = None
    for line in lines[1:]:
        if re.match(r"Doing business as:", line, re.I):
            dba = clean(line.split(":", 1)[1])
        elif re.match(r"(?:Location:|\d|Logan Airport)", line):
            address = clean(re.sub(r"^Location:\s*", "", line))
    if "The Board deferred" in name:
        part = re.split(r"which has (?:since )?occurred:|review:", text, flags=re.I)[1]
        name, rest = re.split(r"\s*d/b/a\s*", part, maxsplit=1, flags=re.I)
        dba, address = re.split(
            r",?\s*located\s*(?:at)?\s*", rest, maxsplit=1, flags=re.I
        )
        address = re.split(r"License\s*#", address, flags=re.I)[0].strip(" .,")
    match = re.search(
        r"\btransfer the (?:licensed business|license)\b.*?\bTo\s*:\s*(.*)", text, re.I
    )
    target = target_dba = target_address = None
    if match:
        tail = match[1]
        target = clean(
            re.split(
                r"\s+d\s*/?\s*b\s*/?\s*a/?\s+|\s*\((?:at the |the )?same location\)|\s+located\b|[,;]\s*\d+\s|(?<=Inc\.)\s+\d+\s",
                tail,
                maxsplit=1,
                flags=re.I,
            )[0]
        ).strip(" ,")
        dm = re.search(
            r"\bd\s*/?\s*b\s*/?\s*a/?\s+(.*?)(?=\s*\((?:at the |the )?same|\s+located\b|[,;]\s*\d+\s)",
            tail,
            re.I,
        )
        if dm:
            target_dba = clean(dm[1]).strip(" ,;")
        if re.search(r"\((?:at the |the )?same location\)", tail, re.I):
            target_address = address
        else:
            am = re.search(
                r"(?:located(?: at)?|[,;]|(?<=Inc\.))\s*(\d[^;]*?\b\d{5}\b)", tail, re.I
            )
            if am:
                target_address = clean(am[1])
    return {
        "licensee": clean(name),
        "licensee_dba": clean(dba),
        "from_address": address,
        "transferor": clean(name),
        "transferor_dba": dba,
        "transferee": target,
        "transferee_dba": target_dba,
        "to_address": target_address,
    }


def pledge_recipient(text):
    m = re.search(
        r"\bpledge\s+(?:their|the)\s+license\b(.*?)(?=\s+Attorney:|\s+Manager:|\s+Granted|\s+Deferred|\s+Continued|\s+Lastly,|\s+Secondly,|$)",
        text,
        re.I,
    )
    if not m:
        return None
    tail = m[1]
    to = re.search(r"\bto\b\s*[:–-]?\s*", tail, re.I)
    return clean(tail[to.end() :] if to else tail).strip(" .")


def main():
    events, ownership, notices, proposed, excluded = [], [], [], [], []
    candidates = json.loads((ROOT / "candidates.json").read_text())
    for c in candidates:
        raw = c["item_text"]
        text = clean(raw)
        notes = []
        status, statement = result(raw)
        lid = c["license_numbers"][0] if len(c["license_numbers"]) == 1 else None
        raw_lid = re.search(r"License\s*#\s*:\s*(L[B]?\s*[-‑]?\s*\d+)", raw, re.I)
        common = {
            **c,
            "date": c["archive_date"],
            "document_vote_date": c["archive_date"],
            "license_number": lid,
            "license_num": lid.replace("-", "") if lid else None,
            "normalized_license_num": lid.replace("-", "") if lid else None,
            "license_number_raw": clean(raw_lid[1]) if raw_lid else lid,
            "outcome": status,
            "disposition": status,
            "outcome_text": statement,
            "decision_bearing": status != "not_stated",
            "board_granted_application": status == "granted",
            "completed_sale_verified": False,
            "ambiguity_notes": notes,
            "review_status": "manually_reviewed",
        }
        petition_text = re.split(
            r"(?mi)^\s*(?:Granted|Deferred|Continued|Withdrawn|Rejected|Acknowledged|Denied|License Canceled)",
            raw,
            maxsplit=1,
        )[0]
        alcohol = bool(
            re.search(r"Alcohol|Beverages|Pouring Permit", petition_text, re.I)
        )
        transfer = alcohol and bool(
            re.search(
                r"has petitioned to transfer the (?:license|licensed business)\b",
                text,
                re.I,
            )
        )
        pledge = bool(re.search(r"\bpledge\s+(?:their|the)\s+license\b", text, re.I))
        own = bool(
            re.search(
                r"(?:change (?:in|of) (?:Ownership|Stock)|change in Stock|transfer \d+ shares|change of shares|change (?:officers and |the officers, and )?shares|Corporate Structure)",
                text,
                re.I,
            )
        )
        p = parties(c)
        key = (c["archive_date"], c["item_number"])
        if key == ("2022-06-30", 17):
            p.update(
                {
                    "licensee_dba": "McCormick & Schmick’s Seafood Restaurant",
                    "transferor_dba": "McCormick & Schmick’s Seafood Restaurant",
                    "from_address": "300 Faneuil Hall Marketplace Boston, MA 02109",
                    "to_address": "300 Faneuil Hall Marketplace Boston, MA 02109",
                }
            )
            notes.append(
                "DBA and street address run together on the same printed line; split according to the explicit address in the item."
            )
        if key == ("2022-05-26", 19):
            p["transferee_dba"] = "Dynasty Hot Pot"
            p["to_address"] = "14A Hudson Street, Boston, MA 02111"
            notes.append(
                "Decision condition corrects proposed DBA Dailongy Hot Pot to Dynasty Hot Pot, address 14 Hudson Street to 14A Hudson Street, and closing hour to midnight; revised application required."
            )
        if key == ("2022-08-25", 18):
            p["transferee_dba"] = "The Crossing Wine and Spirits"
            notes.append(
                "Decision requires revised application adding The Crossing Wine and Spirits DBA."
            )
        if key == ("2022-08-25", 20):
            p["to_address"] = "392-398 Cambridge Street, Allston, MA 02134"
            notes.append(
                "Decision corrects destination from 336 Sumner Street to 392-398 Cambridge Street; legal advertisement and notice required."
            )
        if key == ("2022-09-15", 13):
            p["transferee"] = None
            p["transferee_dba"] = None
            p["to_address"] = "392 - 398 Cambridge Street, Allston, MA 02134"
            notes.append(
                "Item names only destination street address after To:, not transferee legal entity. No entity is inferred from earlier hearing."
            )
        if key == ("2022-10-26", 21):
            notes.append(
                "Printed license ID is L-99088, not LB-99088. Normalized LB ID withheld pending independent resolution."
            )
        if key == ("2022-08-04", 12):
            common["outcome_text_raw"] = statement
            common["outcome_text"] = "Granted"
            notes.append(
                "PDF text layer contains GrantedrantedTransferManage, but rendered page visibly states Granted. Visible disposition is used; original extracted item text is retained."
            )
        if key == ("2022-10-26", 20):
            notes.append(
                "Decision requires updated application naming Qian Huang as manager, replacing proposed Ming Lin, and correcting premise description."
            )
        if key == ("2022-04-28", 22):
            notes.append(
                "Pledge is explicitly granted in a supplemental Board decision sentence, not in the advertised petition summary."
            )
        if "not_stated" == status:
            notes.append(
                "No explicit disposition found; proposal is not a Board approval."
            )
        if transfer:
            row = {
                **common,
                **p,
                "event_id": c["candidate_id"] + "-transfer",
                "event_type": "license_transfer",
                "action_subtype": "transfer_application_disposition",
                "parties": p,
            }
            (events if common["decision_bearing"] else proposed).append(row)
        if pledge:
            recipient = pledge_recipient(text)
            recipient_raw = recipient
            if recipient and recipient.startswith("Seller, "):
                recipient = recipient.removeprefix("Seller, ")
                notes.append("Source explicitly identifies pledge recipient as seller.")
            pp = {
                **p,
                "licensee": p["transferee"] if transfer else p["licensee"],
                "licensee_dba": p["transferee_dba"] if transfer else p["licensee_dba"],
                "pledge_recipient": recipient,
            }
            row = {
                **common,
                **pp,
                "event_id": c["candidate_id"] + "-pledge",
                "event_type": "license_pledge",
                "action_subtype": "pledge_application_disposition",
                "pledge_recipient": recipient,
                "pledge_recipient_raw": recipient_raw,
                "pledge_recipients": [s.strip() for s in recipient.split(";")]
                if recipient
                else [],
                "parties": pp,
                "current_lien_verified": False,
            }
            (events if common["decision_bearing"] else proposed).append(row)
        if own:
            actions = []
            if re.search(
                r"Ownership Interest|Ownership and Stock|Stock Ownership|Stock/Ownership|Stock and Ownership",
                text,
                re.I,
            ):
                actions.append("ownership_interest_change")
            if re.search(
                r"change (?:in|of) Stock|change of Ownership and Stock", text, re.I
            ):
                actions.append("stock_interest_change")
            if re.search(r"transfer \d+ shares", text, re.I):
                actions.append("share_transfer")
            if "Pledge the Stock" in text:
                actions.append("stock_pledge")
                notes.append(
                    "Pledge explicitly covers stock only; no license pledge inferred."
                )
            row = {
                **common,
                **p,
                "event_id": c["candidate_id"] + "-ownership",
                "event_type": "ownership_interest",
                "action_subtype": "ownership_application_disposition",
                "ownership_actions": actions,
                "actions": actions,
                "event_subtype": "ownership_application_disposition",
                "license_scope": "explicit_alcohol"
                if alcohol
                else "common_victualler_no_alcohol_stated",
                "entity_conversion_explicit": False,
                "entity_name": p["licensee"],
                "entity_dba": p["licensee_dba"],
                "parties_before": [],
                "parties_after": [],
                "equity_change_completion_verified": False,
                "alcohol_license_explicit": alcohol,
                "license_category_scope": "alcohol_explicit"
                if alcohol
                else "common_victualler_non_alcohol_or_unspecified",
                "parties": p,
                "prior_equity_holders": [],
                "new_equity_holders": [],
                "equity_percentage_stated": False,
                "private_equity_control_inferred": False,
            }
            if key == ("2022-09-15", 2):
                row.update(
                    {
                        "licensee": "Omid’s Donuts, Inc.",
                        "licensee_dba": "Dunkin Donuts",
                        "prior_equity_holders": ["Hamid M. Omid"],
                        "new_equity_holders": ["Afshin B. Omid"],
                        "share_count": 25,
                        "from_address": "209-211 North Harvard Street, Allston, MA 02134",
                    }
                )
                row["parties"] = {
                    "licensee": row["licensee"],
                    "licensee_dba": row["licensee_dba"],
                    "share_transferor": "Hamid M. Omid",
                    "share_transferee": "Afshin B. Omid",
                }
                notes.append(
                    "Source states 25 shares, not an ownership percentage; item lacks a license ID and does not state an alcohol category."
                )
            if key == ("2022-05-05", 8):
                row.update(
                    {
                        "entity_conversion_explicit": True,
                        "entity_before": "Badoinkas, LLC",
                        "entity_after": "Badoinkas, Incorporated",
                        "actions": ["corporate_structure_change"],
                    }
                )
                notes.append(
                    "Corporate-structure change from LLC to Incorporated is explicit. No change in ultimate equity ownership is inferred; a separate license-transfer application is also heard the same day."
                )
            if key == ("2022-02-03", 2):
                row.update(
                    {
                        "entity_name": "Fratello's Pizzeria and Shawarma, Inc.",
                        "entity_dba": None,
                        "licensee": "Fratello's Pizzeria and Shawarma, Inc.",
                        "parties_before": [
                            {"name": "Aleksandr Yeghiyan", "shares": 30},
                            {"name": "Harutyun Sahakyan", "shares": 70},
                        ],
                        "parties_after": [{"name": "Harutyun Sahakyan", "shares": 100}],
                        "from_address": "563 Washington St, Brighton, Ma 02135",
                        "actions": ["share_change"],
                    }
                )
                notes.append(
                    "Source states share counts, not ownership percentages. Common Victualler item does not state alcohol category or license ID."
                )
            if key == ("2022-10-26", 4):
                row.update(
                    {
                        "entity_name": "Rosas Group, LLC",
                        "entity_dba": "La Casa De Pan Debona",
                        "licensee": "Rosas Group, LLC",
                        "parties_before": [
                            {"name": "Berta Rosas", "percentage": 20},
                            {"name": "Joan Gross", "percentage": 39},
                            {"name": "Manuel Fernando Rosas", "percentage": 41},
                        ],
                        "parties_after": [
                            {"name": "Erin Rosas", "percentage": 51},
                            {"name": "Marvel Fernando Rosas", "percentage": 49},
                        ],
                        "equity_percentage_stated": True,
                        "entity_before": "Rosas Group, LLC",
                        "entity_after": "GR Restaurant and Catering, Inc.",
                        "actions": ["share_change", "corporate_name_change"],
                        "from_address": "271 Meridian Street, East Boston, MA 02128",
                    }
                )
                notes.append(
                    "Source explicitly describes corporate-name and share changes; legal-form labels differ, but no formal entity conversion is inferred. Manuel and Marvel spellings are preserved as printed."
                )
            if key == ("2022-10-26", 5):
                row.update(
                    {
                        "entity_name": "Chen’s Corner, Inc.",
                        "entity_dba": "Cafe Corner",
                        "licensee": "Chen’s Corner, Inc.",
                        "parties_before": [
                            {"name": "Wen Dong Chen", "shares": 50},
                            {"name": "Limin Chen", "shares": 50},
                        ],
                        "parties_after": [{"name": "Limin Chen", "shares": 100}],
                        "actions": ["share_change"],
                        "from_address": "62 Harrison Avenue, Boston, MA 02111",
                    }
                )
                notes.append(
                    "Source states share counts, not ownership percentages. Common Victualler item lacks alcohol category and license ID."
                )
            if key == ("2022-11-17", 1) and "Bingo Catering" in text:
                row.update(
                    {
                        "entity_name": "Bingo Catering LLC",
                        "entity_dba": "Bos’ Sichuan Taste",
                        "licensee": "Bingo Catering LLC",
                        "parties_before": [
                            {"name": "Guang Ping Ding", "percentage": 35},
                            {"name": "Hao Shen", "percentage": 10},
                            {"name": "LiLuo", "percentage": 20},
                            {"name": "Xiang Zhou", "percentage": 35},
                        ],
                        "parties_after": [
                            {"name": "Jiaying Chen", "percentage": 20},
                            {"name": "Yingnan Liu", "percentage": 15},
                            {"name": "Xiang Zhou", "percentage": 35},
                            {"name": "Hao Shen", "percentage": 10},
                            {"name": "Zihang Yu", "percentage": 20},
                        ],
                        "equity_percentage_stated": True,
                        "actions": ["share_change"],
                        "from_address": "204 Harvard Avenue, Allston, MA 02134",
                    }
                )
            if key == ("2022-09-15", 2):
                row["entity_name"] = row["licensee"]
                row["entity_dba"] = row["licensee_dba"]
                row["parties_before"] = [
                    {"name": "Hamid M. Omid", "shares_transferred": 25}
                ]
                row["parties_after"] = [
                    {"name": "Afshin B. Omid", "shares_received": 25}
                ]
            if not row["parties_before"]:
                notes.append(
                    "No prior or new equity holders or percentages are stated; officer/manager changes are not substituted for equity ownership."
                )
            row["prior_equity_holders"] = [p["name"] for p in row["parties_before"]]
            row["new_equity_holders"] = [p["name"] for p in row["parties_after"]]
            row["ownership_actions"] = row["actions"]
            row["licensee_dba"] = row["entity_dba"]
            row["parties"]["licensee"] = row["entity_name"]
            row["parties"]["licensee_dba"] = row["entity_dba"]
            (ownership if common["decision_bearing"] else proposed).append(row)
        if not transfer and not pledge and not own:
            if re.search(r"Release of Pledge", text, re.I):
                kind = "pledge_release"
                eventtype = "license_pledge"
                action = "pledge_release_notice"
            elif "License Canceled" in text:
                kind = "license_cancellation"
                eventtype = "license_cancellation"
                action = "cancellation_after_alleged_unauthorized_interest_change"
                notes.append(
                    "Notice describes alleged unapproved beneficial-interest/management change; explicit Board outcome is cancellation, not an approved transfer."
                )
            elif "clarify the ownership" in text:
                kind = "ownership_clarification_notice"
                eventtype = kind
                action = kind
            else:
                kind = (
                    "non_alcohol_lodging_transfer"
                    if "transfer the lodging" in text.lower()
                    else "other_keyword_context"
                )
                excluded.append({**common, "classification": kind})
                continue
            row = {
                **common,
                "event_id": c["candidate_id"] + "-notice",
                "event_type": eventtype,
                "action_subtype": action,
                "classification": kind,
                "board_granted_application": False,
            }
            if kind == "pledge_release":
                release_map = {
                    ("2022-03-24", 1): (
                        "Mullins Way LLC",
                        "Shore Leave",
                        "Cambridge Trust Company",
                        "345 Harrison Avenue, Roxbury, MA 02118",
                    ),
                    ("2022-03-24", 2): (
                        "30 Traveler LLC",
                        "Bar Mezzana",
                        "Cambridge Trust Company",
                        "360 Harrison Avenue, Roxbury, MA 02118",
                    ),
                    ("2022-03-24", 3): (
                        "571 Tremont LLC",
                        "Black Lamb",
                        "DT Capital LLC",
                        "571 Tremont Street, Roxbury, MA 02118",
                    ),
                    ("2022-05-26", 1): (
                        "Sip Wine Bar and Kitchen, Inc.",
                        None,
                        "Santander Bank, N.A.",
                        "571-581 Washington Street, Boston, MA 02111",
                    ),
                    ("2022-10-06", 1): (
                        "South of Hixbridge, LLC",
                        None,
                        "Salem Five Cents Savings Bank",
                        "50 Lovejoy Wharf, Boston, MA 02114",
                    ),
                }
                name, dba, lender, address = release_map[key]
                row.update(
                    {
                        "licensee": name,
                        "licensee_dba": dba,
                        "pledge_recipient": lender,
                        "from_address": address,
                        "parties": {
                            "licensee": name,
                            "licensee_dba": dba,
                            "releasing_pledge_holder": lender,
                        },
                        "current_lien_verified": False,
                    }
                )
                notes.append(
                    "Board acknowledges receipt of release from named creditor; this does not establish absence of other or later security interests."
                )
            elif kind == "license_cancellation":
                row["parties"] = {
                    "licensee": "Bubor Cha-Cha Restaurant, LLC",
                    "address": "45 Beach St Boston, MA 02111",
                }
            else:
                row["parties"] = {
                    "licensee": "154 Maverick LLC",
                    "licensee_dba": "Maverick House Tavern",
                    "address": "154 Maverick Street, East Boston, MA 02128",
                }
            notices.append(row)
    for name, rows in [
        ("events", events),
        ("ownership-interest-events", ownership),
        ("notices", notices),
        ("proposed-events", proposed),
        ("unresolved-events", []),
        ("excluded-candidates", excluded),
    ]:
        (ROOT / f"{name}.json").write_text(json.dumps(rows, indent=2))
    print(
        json.dumps(
            {
                "events": dict(Counter(e["event_type"] for e in events)),
                "outcomes": dict(Counter(e["outcome"] for e in events)),
                "ownership": len(ownership),
                "notices": len(notices),
                "proposed": len(proposed),
                "excluded": len(excluded),
            }
        )
    )


if __name__ == "__main__":
    main()
