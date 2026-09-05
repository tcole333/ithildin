import copy
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
candidates = json.loads((OUT / "candidates.json").read_text())
sources = {
    s["source_id"]: s
    for s in json.loads((ROOT / "source-index.json").read_text())
    if s["archive_year"] == 2024
}
events = []
exclusions = []


def norm(t):
    return " ".join(t.split())


def match(pattern, text, flags=re.I):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def dates(src):
    txt = (ROOT / "documents" / (src + ".txt")).read_text()
    date_text = match(
        r"Voting\s*Hearing\s*Agenda\s+([A-Za-z]+\s+\d{1,2},\s*2024)", txt[:1800]
    )
    return (
        dt.datetime.strptime(date_text, "%B %d, %Y").date().isoformat()
        if date_text
        else None
    )


for c in candidates:
    key = (c["source_id"], c["item_number"])
    b = c["item_text"]
    # Cut section transitions from the preceding item, not any part of its outcome.
    b = re.split(
        r"\n\s*(?:Non-Hearing Transactions|Transactional Hearing|THE BOARD WILL DEFER)",
        b,
        maxsplit=1,
    )[0].strip()
    flat = norm(b)
    is_transfer = bool(
        re.search(
            r"(?:to\s+transfer|transfer of)\s+the\s+licen(?:se|sed business)\b",
            flat,
            re.I,
        )
    )
    is_pledge = bool(re.search(r"pledge\s+the\s+license\b", flat, re.I))
    is_release = "Release of Pledge of License" in flat
    is_revoke = key == ("BLB-2024-06-06", "5")
    if not (is_transfer or is_pledge or is_release or is_revoke):
        exclusions.append(
            dict(
                c,
                exclusion_reason="No explicit transfer or new pledge action: prospective, conditional, or unrelated nonalcohol item.",
            )
        )
        continue
    if key in [
        ("BLB-2024-03-28", "3"),
        ("BLB-2024-05-23", "9"),
        ("BLB-2024-06-06", "3"),
        ("BLB-2024-09-26", "6"),
    ]:
        exclusions.append(
            dict(
                c,
                exclusion_reason="Prospective transfer mention or nonalcohol approval; not an actual transfer application/decision.",
            )
        )
        continue
    outcome_raw = match(
        r"^\s*((?:Granted|Denied|Deferred|Withdrawn|Rejected|Approved|No Action|Acknowledged|Rescinded|Not approved|Rescheduled)\b[\s\S]*)",
        b,
        re.I | re.M,
    )
    outcome_raw = re.sub(r"[_]{5,}.*", "", outcome_raw or "").strip()
    outcome = (
        outcome_raw.split()[0].lower().rstrip(",:;") if outcome_raw else "not_stated"
    )
    # No invented license number where omitted in the primary document.
    hlines = [x.strip() for x in b.splitlines() if x.strip()]
    party = c["party_heading"]
    dba = match(r"Doing business as:\s*([^\n]+)", b)
    address = next(
        (
            x
            for x in hlines[1:5]
            if re.search(r"\bMA\s*,?\s*\d{5}", x, re.I) and not x.startswith("Holder")
        ),
        None,
    )
    transfer_part = (
        match(
            r"(?:to\s+transfer|transfer of)\s+the\s+licen(?:se|sed business).*?\bTo\s*:\s*(.*)",
            flat,
        )
        if is_transfer
        else None
    )
    transferee = transferee_dba = to_address = None
    if transfer_part:
        transferee = re.split(
            r"\s+(?:dba|d/b/a|located at)\s+|\s*\((?:at )?(?:the )?same location\)",
            transfer_part,
            maxsplit=1,
            flags=re.I,
        )[0].strip()
        transferee_dba = match(
            r"\b(?:dba|d/b/a)\s+(.*?)(?:\s+located at\b|\s*\((?:at )?(?:the )?same location\))",
            transfer_part,
        )
        if re.search(r"\((?:at )?(?:the )?same location\)", transfer_part, re.I):
            to_address = address
        else:
            to_address = match(
                r"\blocated at\s+(.*?\b(?:MA|Ma)\s*\d{5})", transfer_part
            )
    pledge_recipient = match(
        r"pledge\s+the\s+license(?:\s+and\s+inventory)?\s*[-–]?\s*to\s*:?\s*(.*?)(?:\s+Attorney:|\s+(?:Lastly|Secondly|Thirdly|Additionally),|\s+Granted\b|\s+Deferred\b)",
        flat,
    )
    if pledge_recipient:
        pledge_recipient = pledge_recipient.rstrip(" .")
        if pledge_recipient.endswith(("Inc", "Corp")):
            pledge_recipient += "."
    notes = []
    if c["license_number"] is None:
        notes.append(
            "The source item omits a Boston LB license number; not inferred from another roster or document."
        )
    if is_transfer and "licensed business" in flat:
        notes.append(
            "Source expressly says transfer the licensed business by the named alcoholic-beverages license holder, rather than transfer the license."
        )
    if "same location" in flat:
        notes.append(
            "Destination address carried from explicit same-location statement."
        )
    if key == ("BLB-2024-01-04", "2"):
        party = "Juan Reyes, Individual"
        dba = "Miami Restaurant"
        address = "381 Centre St., Jamaica Plain, MA 02130"
        to_address = address
        notes.append(
            "Old and New Business resolution of a previously deferred transfer; this document grants it, with closing-hour condition."
        )
    if key in [("BLB-2024-02-01", "13"), ("BLB-2024-02-01", "14")]:
        notes.append(
            "Same meeting records sequential transfers of LB-98957: Bedford Dining to 116 Brighton License, then 116 Brighton License to Jongro BBQ. These are separate proposed legs of one license chain."
        )
    if key == ("BLB-2024-03-28", "15"):
        notes.append(
            "Later June 6 Old/New Business item 5 acknowledges notice that this purchase and sale agreement was voided and the parties mutually intended to revoke the transfer; do not present as completed sale."
        )
    if is_revoke:
        party, dba = "Mirage Charcoal Kebab, Inc.", "Zen Restaurant"
        address, to_address = (
            "21A Beacon St., Boston, MA 02109",
            "21A Beacon St., Boston, MA 02109",
        )
        transferee, transferee_dba = "LZZ LLC", "Zen Japanese Grill and Sushi Bar"
        notes.append(
            "Board acknowledged seller and buyer notice of mutual intent to revoke the March 28 transfer; source says purchase and sale agreement was voided. This is not a new grant or proof of a completed sale."
        )
    if is_release:
        if key == ("BLB-2024-04-25", "1"):
            party, dba, address, pledge_recipient = (
                "Flatbread Boston Landing LLC",
                "Flatbread Company",
                "76 Guest Street, Brighton, MA 02135",
                "Newburyport Five Cents Savings Bank",
            )
        else:
            party, dba, address, pledge_recipient = (
                "Cami 1975 Corporation",
                "Melodias",
                "1045 Saratoga Street, East Boston, MA 02128",
                "Lazaro Orellana",
            )
            notes.append(
                "Release item says Cami 1975 Corporation; new pledge item 8 in same document says CAMI 1974 Corporation. Preserve source discrepancy; same LB-99655 and premises."
            )
        notes.append(
            "Acknowledged release of prior pledges/security interests, not approval of a new pledge."
        )
    source_text = (ROOT / "documents" / (c["source_id"] + ".txt")).read_text()
    block_offset = source_text.find(b)
    assert block_offset >= 0
    page_start = source_text[:block_offset].count("\f") + 1
    page_end = source_text[: block_offset + len(b)].count("\f") + 1
    base = {
        "source_id": c["source_id"],
        "source_url": c["source_url"],
        "archive_date": c["archive_date"],
        "document_vote_date": dates(c["source_id"]),
        "page_start": page_start,
        "page_end": page_end,
        "item_number": c["item_number"],
        "license_number": c["license_number"],
        "transferor": party,
        "transferor_dba": dba,
        "transferee": transferee,
        "transferee_dba": transferee_dba,
        "from_address": address,
        "to_address": to_address,
        "outcome": outcome,
        "outcome_text": outcome_raw or None,
        "item_text": b,
        "pledge_recipient": pledge_recipient,
        "ambiguity_notes": notes,
        "decision_bearing": outcome != "not_stated",
    }
    if is_transfer or is_revoke:
        e = copy.deepcopy(base)
        e.update(
            event_id=f"{c['source_id']}-T-{c['item_number']}",
            event_type="license_transfer",
            event_subtype="transfer_revocation_notice"
            if is_revoke
            else "transfer_application_decision",
        )
        events.append(e)
    if is_pledge or is_release:
        e = copy.deepcopy(base)
        e.update(
            event_id=f"{c['source_id']}-P-{c['item_number']}",
            event_type="license_pledge",
            event_subtype="release_acknowledgment"
            if is_release
            else "pledge_application_decision",
            pledging_party=transferee if is_transfer else party,
        )
        events.append(e)

# Each document is accounted for, including no-hit documents.
coverage = []
visual_checks = {
    "BLB-2024-01-04": {
        "pages": [14],
        "result": "Old/New Business item 2 actually grants previously deferred Miami Restaurant transfer, with 1 AM closing.",
    },
    "BLB-2024-02-01": {
        "pages": [7],
        "result": "Items 13 and 14 separately grant two sequential legs of LB-98957; item 14 also grants pledge to intermediate holder.",
    },
    "BLB-2024-02-08": {
        "pages": [5],
        "result": "H and M Restaurant transfer and HarborOne pledge granted; source visibly omits LB identifier.",
    },
    "BLB-2024-06-06": {
        "pages": [10],
        "result": "Item 5 says Mirage/LZZ purchase and sale agreement voided and mutual intent to revoke approved transfer; Board outcome is Acknowledged.",
    },
    "BLB-2024-08-01": {
        "pages": [14],
        "result": "Old/New Business item 1 acknowledges release from Lazaro Orellana; source spells Cami 1975 Corporation.",
    },
    "BLB-2024-10-17": {
        "pages": [10],
        "result": "Item 21 rescheduled; item 22 granted but no license issuance until community process completed; item 23 separately granted.",
    },
    "BLB-2024-12-12": {
        "pages": [9],
        "result": "Item 22 Mai transfer granted; item 23 Flik transfer and pledge deferred for license-type application.",
    },
}
for sid, s in sources.items():
    txt = (ROOT / "documents" / (sid + ".txt")).read_text()
    ev = [e for e in events if e["source_id"] == sid]
    ex = [e for e in exclusions if e["source_id"] == sid]
    date = dates(sid)
    coverage.append(
        {
            "source_id": sid,
            "source_url": s["url"],
            "archive_date": s["archive_date"],
            "document_vote_date": date,
            "page_count": txt.count("\f"),
            "checked": True,
            "review_method": "Poppler layout text, all transfer/pledge candidate items read; targeted visual checks recorded separately.",
            "events": len(ev),
            "event_type_counts": dict(Counter(e["event_type"] for e in ev)),
            "outcome_counts": dict(Counter(e["outcome"] for e in ev)),
            "excluded_keyword_items": len(ex),
            "date_discrepancy": None
            if date == s["archive_date"]
            else {"archive": s["archive_date"], "document": date},
            "visual_check": visual_checks.get(sid),
        }
    )
(OUT / "events.json").write_text(
    json.dumps(events, ensure_ascii=False, indent=2) + "\n"
)
(OUT / "coverage.json").write_text(
    json.dumps(coverage, ensure_ascii=False, indent=2) + "\n"
)
(OUT / "excluded-items.json").write_text(
    json.dumps(exclusions, ensure_ascii=False, indent=2) + "\n"
)
for e in events:
    if e["event_type"] == "license_transfer":
        print(
            e["event_id"],
            e["license_number"],
            e["transferor"],
            "->",
            e["transferee"],
            "DBA",
            e["transferee_dba"],
            "TO",
            e["to_address"],
            "OUTCOME",
            e["outcome"],
        )
    else:
        print(
            e["event_id"],
            e["license_number"],
            "PLEDGE",
            e["pledging_party"],
            "->",
            e["pledge_recipient"],
            "OUTCOME",
            e["outcome"],
            e["event_subtype"],
        )
print(
    "COUNTS",
    dict(Counter(e["event_type"] for e in events)),
    dict(Counter(e["outcome"] for e in events)),
    "EXCLUDED",
    len(exclusions),
)
