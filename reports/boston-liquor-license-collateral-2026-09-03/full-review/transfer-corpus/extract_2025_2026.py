"""Structure manually reviewed transfer/pledge candidate items for 2025-2026."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def clean(value):
    return re.sub(r"\s+", " ", value).strip(" -\n\t") if value else None


def outcome(raw):
    match = re.search(r"(?mi)^\s*(Granted\b[^\n]*|Withdrawn\b[^\n]*|Continued\b[^\n]*|Deferred\b[^\n]*|Acknowledged\b[^\n]*|Denied\b[^\n]*|No Action Taken[^\n]*)", raw)
    if not match:
        return "not_stated", None
    status = match[1].split()[0].lower().rstrip(",.")
    return status, clean(match[1])


def parties(candidate):
    raw = candidate["item_text"]
    normal = clean(raw)
    name = clean(candidate["heading"])
    dba = None
    address = None
    header = re.split(r"License\s*#", raw, flags=re.I)[0]
    lines = [line.strip() for line in header.splitlines() if line.strip()]
    for line in lines[1:]:
        if line.lower().startswith("doing business as:"):
            dba = clean(line.split(":", 1)[1])
        elif re.match(r"\d", line) or line.startswith("Location:"):
            address = clean(re.sub(r"^Location:\s*", "", line))
    transfer = re.search(r"\btransfer the (?:licensed business|license)\b", normal, re.I)
    target = target_dba = target_address = None
    notes = []
    if transfer and re.search(r"has petition(?:ed)?", normal, re.I):
        clause = normal[transfer.end():]
        to = re.search(r"\bTo\s*:\s*", clause, re.I)
        if to:
            remainder = clause[to.end():]
            target = clean(re.split(r"\s+d\s*/?\s*b\s*/?\s*a\s*|\s*\((?:at the )?same location\)|\s+located\b|\s*\(with updated", remainder, maxsplit=1, flags=re.I)[0])
            dbam = re.search(r"\bd\s*/?\s*b\s*/?\s*a\s*(.+?)(?=\s*\((?:at the )?same location\)|\s+located\b)", remainder, re.I)
            target_dba = clean(dbam[1]) if dbam else None
            loc = re.search(r"\blocated(?: at)?\s+(.+?\b\d{5}\b)", remainder, re.I)
            target_address = clean(loc[1]) if loc else address if re.search(r"\((?:at the )?same location\)", remainder, re.I) else None
            from_m = re.search(r"\bFrom\s*:\s*(.*?)\s+located(?: at)?\s+(.+?\b\d{5}\b)", clause[:to.start()], re.I)
            if from_m:
                from_name = clean(from_m[1])
                from_dba = re.search(r"\s+d\s*/?\s*b\s*/?\s*a\s+(.+)$", from_name, re.I)
                if from_dba:
                    dba = clean(from_dba[1])
                    from_name = from_name[:from_dba.start()].strip()
                if from_name != name:
                    notes.append(f"Transferor heading is {name!r}; transfer clause identifies {from_name!r}.")
                name, address = from_name, clean(from_m[2])
        if "transfer the licensed business" in normal.lower():
            notes.append("Source uses 'transfer the licensed business' in an alcoholic-beverages license-holder petition.")
    return name, dba, address, target, target_dba, target_address, notes


def main():
    candidates = json.loads((ROOT / "candidates-2025-2026.json").read_text())
    events, excluded, notices = [], [], []
    for item in candidates:
        raw = item["item_text"]
        text = clean(raw)
        license_id = item["license_numbers"][0] if len(item["license_numbers"]) == 1 else None
        status, status_text = outcome(raw)
        name, dba, address, target, target_dba, target_address, notes = parties(item)
        transfer = bool(re.search(r"has petition(?:ed)?.*?\btransfer the (?:license|licensed business)\b", text, re.I))
        pledge = bool(re.search(r"\bpledge (?:of )?(?:the )?license\b", text, re.I)) and not re.search(r"release of pledge", text, re.I)
        # Explicit corrections in the board's decision supersede the petition's proposed details.
        if license_id == "LB-99452" and item["archive_date"] == "2025-06-05":
            notes.append("Petition names 1928 Boston Harbor, LLC; decision corrects transferee to 1928 Rowes Wharf LLC.")
            target = "1928 Rowes Wharf LLC"
        if license_id == "LB-99389" and item["archive_date"] == "2025-11-20":
            notes.append("Petition says 289 Dorchester Ave; decision corrects address to 289 Dorchester St.")
            target_address = "289 Dorchester St, South Boston, MA 02127"
        if license_id == "LB-98927" and item["archive_date"] == "2026-05-21":
            target, target_dba, target_address = "Hawksmoor Boston, Inc", "Hawksmoor Boston", address
            notes.append("Transferee follows 'from the above -' without a To: marker; extracted from that explicit clause.")
        if license_id == "LB-546003" and item["archive_date"] == "2025-06-26":
            name, dba, address = "B.U., LLC", "B.U. Bistro", "3840 Washington St, Roslindale, MA 02131"
            target_address = address
        if license_id == "LB-101911" and item["archive_date"] == "2026-03-05":
            target_dba = "Jersey Street Liquors"
            notes.append("Petition proposes Sip City Liquors; decision grants with d/b/a of Jersey Street Liquors.")
        if license_id == "LB-99134" and item["archive_date"] == "2026-03-05":
            notes.append("Source omits a street address. Same-location transfer is explicit, but no address is inferred.")
        if "not to be issued" in text.lower():
            notes.append("Grant has an explicit issuance condition; see complete item text.")
        common = {
            "source_id": item["source_id"], "source_url": item["source_url"],
            "archive_date": item["archive_date"], "document_vote_date": item["archive_date"],
            "page_start": item["page_start"], "page_end": item["page_end"], "item_number": item["item_number"],
            "license_number": license_id, "licensee_heading": item["heading"], "outcome": status,
            "outcome_text": status_text, "item_text": raw, "ambiguity_notes": notes, "decision_bearing": True,
            "candidate_id": item["candidate_id"],
        }
        if transfer:
            events.append({**common, "event_id": item["candidate_id"] + "-transfer", "event_type": "license_transfer",
                           "action_subtype": "transfer_application_disposition", "transferor": name,
                           "transferor_dba": dba, "transferee": target, "transferee_dba": target_dba,
                           "from_address": address, "to_address": target_address})
        if pledge:
            pm = re.search(r"\bpledge (?:of )?(?:the )?license(?: and (?:inventory|stock))?\s*[-:]?\s*to\s*[-:]?\s*(.*?)(?=\s+Attorney:|\s+Manager:|\s+Closing Time:|\s+Granted\b|\s+Lastly,|\s+Thirdly,|\s+Secondly,|\s+Additionally,|$)", text, re.I)
            recipient = clean(pm[1]).rstrip(" .") if pm else None
            events.append({**common, "event_id": item["candidate_id"] + "-pledge", "event_type": "license_pledge",
                           "action_subtype": "pledge_application_disposition", "licensee": target if transfer else name,
                           "licensee_dba": target_dba if transfer else dba, "from_address": address,
                           "pledge_recipient": recipient})
        if not transfer and not pledge:
            reason = "stock_or_ownership_only" if re.search(r"(?:transfer|pledge) of stock", text, re.I) else "other_keyword_context"
            if re.search(r"mutual intent to revoke", text, re.I):
                reason = "transfer_revocation_notice"
            elif re.search(r"intent to transfer|transfer its license|unless.*?transfer|upon the transfer", text, re.I):
                reason = "prospective_transfer_or_status_notice"
            elif re.search(r"release of pledge", text, re.I):
                reason = "pledge_release"
            elif "non-transferable" in text or "nontransferable" in text:
                reason = "nontransferability_policy_or_new_license"
            excluded.append({**item, "classification": reason})
            if reason in {"transfer_revocation_notice", "prospective_transfer_or_status_notice", "pledge_release"}:
                notices.append({**common, "event_id": item["candidate_id"] + "-notice", "event_type": reason})
    (ROOT / "events-2025-2026.json").write_text(json.dumps(events, indent=2))
    (ROOT / "notices-2025-2026.json").write_text(json.dumps(notices, indent=2))
    (ROOT / "excluded-candidates-2025-2026.json").write_text(json.dumps(excluded, indent=2))
    print(json.dumps({"events": dict(Counter(e["event_type"] for e in events)), "notices": len(notices), "excluded_items": len(excluded)}))


if __name__ == "__main__":
    main()
