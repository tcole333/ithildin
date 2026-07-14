#!/usr/bin/env python3
"""Build the GEO executive/director FEC identity and refund ledgers for lead 59035.

This is deliberately deterministic and offline.  It consumes archived FEC API
responses and SEC proxy statements; it does not make network requests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


GEO_PAC_ID = "C00382150"
TRUMP_NAME_TOKENS = ("TRUMP", "SAVE AMERICA", "NEVER SURRENDER", "MAGA")


@dataclass(frozen=True)
class Person:
    slug: str
    name: str
    role: str
    roster_status: str
    identity_basis: str


PEOPLE = [
    Person("thomas-c-bartzokis", "Thomas C. Bartzokis", "Director nominee", "current", "SEC proxy confirms the distinctive full name, Boca Raton medical practice, and director service since 2022."),
    Person("jack-brewer", "Jack Brewer", "Director nominee", "current", "SEC proxy name plus Boca Raton, GEO employer, and Board of Director occupation; same-name rows elsewhere remain unresolved."),
    Person("donna-arduin-kauranen", "Donna Arduin Kauranen", "Director nominee", "current", "SEC proxy name plus distinctive three-part FEC name, Boca Raton, GEO, and director title."),
    Person("scott-m-kernan", "Scott M. Kernan", "Director nominee", "current", "Exact SEC full name; no FEC Schedule A rows returned in the six-cycle search."),
    Person("lindsay-l-koren", "Lindsay L. Koren", "Director nominee", "current", "SEC proxy confirms Darden service from 2015 and GEO board service from December 2022, matching the Orlando-to-Boca FEC transition."),
    Person("julie-myers-wood", "Julie Myers Wood", "Director nominee", "current", "SEC proxy name plus the distinctive hyphenated FEC name, GEO employer, Boca Raton, and board title."),
    Person("george-c-zoley", "George C. Zoley", "Chairman and Chief Executive Officer; director nominee", "current", "SEC proxy full name and role match the full-middle-name Boca Raton FEC records."),
    Person("mark-suchinski", "Mark Suchinski", "Chief Financial Officer", "current_at_proxy", "SEC proxy states Spirit AeroSystems CFO service through June 2024 and GEO appointment effective July 8, 2024, matching the FEC employer/location transition."),
    Person("paul-laird", "Paul Laird", "Senior Vice President, Secure Services", "current", "SEC proxy states GEO service since 2015 and operations-to-secure-services progression; only Charlotte/Boca/Delray GEO-title records are retained."),
    Person("matthew-t-albence", "Matthew T. Albence", "Senior Vice President, Client Relations", "current", "SEC full name and title match the Boca Raton GEO FEC records."),
    Person("richard-k-long", "Richard K. Long", "Senior Vice President, Project Development", "current", "SEC proxy name/role plus FEC full middle name Kent, Coral Springs, GEO, and senior project/service titles."),
    Person("david-o-meehan", "David O. Meehan", "Senior Vice President, GEO Care", "current", "SEC full name and role match the Boca Raton GEO FEC records."),
    Person("christopher-d-ryan", "Christopher D. Ryan", "Senior Vice President, Human Resources", "current", "SEC proxy states GEO human-resources service since 2011; only full-middle-name Florida GEO HR records are retained."),
    Person("donald-houston", "Donald Houston", "Senior Vice President, Health Services", "current", "SEC proxy title plus Boca Raton, GEO employer, and matching health-services title; other same-name records remain unresolved."),
    Person("daniel-ragsdale", "Daniel Ragsdale", "Senior Vice President, Contract Administration and Compliance", "current", "SEC proxy title plus Boca Raton GEO contract/compliance titles; San Antonio and other common-name clusters remain unresolved."),
    Person("scott-a-schipma", "Scott A. Schipma", "Senior Vice President, General Counsel and Corporate Secretary", "current", "SEC full name and legal role match the Boca Raton GEO FEC records."),
    Person("ronald-a-brack", "Ronald A. Brack", "Executive Vice President, Chief Accounting Officer and Controller", "current", "SEC full name and accounting role match the Boca Raton GEO FEC records."),
    Person("shayn-p-march", "Shayn P. March", "Executive Vice President, Finance and Treasurer", "current", "SEC full name and finance role match the Parkland/Boca GEO FEC records."),
    Person("nicole-mannarino", "Nicole Mannarino", "Chief Compliance Officer and Controller, Financial Reporting", "current", "SEC proxy states GEO financial-reporting service since 2012; the distinctive Florida GEO accounting records match."),
    Person("brian-r-evans", "Brian R. Evans", "Former Chief Executive Officer and former Senior Vice President and CFO", "former", "2024 SEC proxy confirms GEO CFO service since 2009 and CEO appointment in 2024; only Florida GEO/CFO/CEO records are retained."),
]
PERSON_BY_SLUG = {p.slug: p for p in PEOPLE}


REFUND_LINKS = {
    "SB28A.9944": ("source_linked", "2015-09-30 C00458844 non-memo $2,700 receipt plus $2,600 redesignation memo in archived 2016 Schedule A file"),
    "GENREF0221": ("source_linked", "2014-09-16 C00458844 non-memo $3,520 receipt in targeted 2014 Schedule A lookup"),
    "D438-001801": ("source_linked", "2015-06-25 C00575910 non-memo $2,700 receipt"),
    "10987691": ("source_linked", "C00382150 Schedule A filing carries a same-page $192.30 direct receipt and an explicit refund-total memo"),
    "B5D524A2FD4604EF49B8": ("source_linked", "C00382150 payroll source-receipt series for the same identified donor; exact source transaction is not specified in the refund description"),
    "BC8520D217952413F99A": ("source_linked", "Refund description says 12.31.21 contribution; archived Schedule A has the same donor/committee/date payroll receipt"),
    "BE3DC6EE1E3AF4C85BD8": ("confirmed_unmatched", "Two targeted C00736983 Schedule A name searches returned zero; preserve but do not subtract"),
}


def dec(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def norm(value: object) -> str:
    return str(value or "").upper().strip()


def committee_name(row: dict) -> str:
    committee = row.get("committee") or {}
    return committee.get("name") or row.get("committee_name") or ""


def party_name(row: dict) -> str:
    return (row.get("committee") or {}).get("party_full") or ""


def identity_resolution(slug: str, row: dict) -> tuple[str, str]:
    n = norm(row.get("contributor_name"))
    city = norm(row.get("contributor_city"))
    state = norm(row.get("contributor_state"))
    employer = norm(row.get("contributor_employer"))
    occupation = norm(row.get("contributor_occupation"))
    geo = "GEO" in employer or "GEO" in occupation

    matched = False
    status = "confirmed"
    if slug == "thomas-c-bartzokis":
        matched = n.startswith("BARTZOKIS, THOMAS C") and city == "BOCA RATON" and state == "FL"
    elif slug == "jack-brewer":
        matched = n == "BREWER, JACK" and city == "BOCA RATON" and state == "FL" and geo
        status = "high"
    elif slug == "donna-arduin-kauranen":
        matched = n.startswith("ARDUIN KAURANEN, DONNA") and state == "FL" and geo
    elif slug == "scott-m-kernan":
        matched = False
    elif slug == "lindsay-l-koren":
        matched = n.startswith("KOREN, LINDSAY") and state == "FL" and (
            (city == "ORLANDO" and "DARDEN" in employer) or (city == "BOCA RATON" and geo)
        )
        status = "high"
    elif slug == "julie-myers-wood":
        matched = n.startswith("MYERS-WOOD, JULIE") and state == "FL" and geo
    elif slug == "george-c-zoley":
        matched = n.startswith("ZOLEY, GEORGE C") and state == "FL"
    elif slug == "mark-suchinski":
        matched = n.startswith("SUCHINSKI, MARK") and (
            (state == "KS" and "SPIRIT" in employer)
            or (state == "FL" and (geo or (city == "BOCA RATON" and row.get("committee_id") == GEO_PAC_ID)))
        )
        if matched and " J" not in n:
            status = "high"
    elif slug == "paul-laird":
        matched = n == "LAIRD, PAUL" and state in {"NC", "FL"} and geo
        status = "high"
    elif slug == "matthew-t-albence":
        matched = n.startswith("ALBENCE, MATTHEW T") and state == "FL" and geo
    elif slug == "richard-k-long":
        matched = n.startswith("LONG, RICHARD KENT") and state == "FL" and geo
    elif slug == "david-o-meehan":
        matched = n.startswith("MEEHAN, DAVID O") and state == "FL" and geo
    elif slug == "christopher-d-ryan":
        matched = n.startswith("RYAN, CHRISTOPHER D") and state == "FL" and geo
    elif slug == "donald-houston":
        matched = n.startswith("HOUSTON, DONALD") and city == "BOCA RATON" and state == "FL" and geo
        status = "high"
    elif slug == "daniel-ragsdale":
        matched = n.startswith("RAGSDALE, DANIEL") and city == "BOCA RATON" and state == "FL" and geo
        if matched and "DANIEL H" not in n:
            status = "high"
    elif slug == "scott-a-schipma":
        matched = n.startswith("SCHIPMA, SCOTT A") and state == "FL" and geo
    elif slug == "ronald-a-brack":
        matched = n.startswith("BRACK, RONALD A") and state == "FL" and geo
    elif slug == "shayn-p-march":
        matched = n.startswith("MARCH, SHAYN P") and state == "FL" and geo
    elif slug == "nicole-mannarino":
        matched = n.startswith("MANNARINO, NICOLE") and state == "FL" and geo
        status = "high"
    elif slug == "brian-r-evans":
        matched = n.startswith("EVANS, BRIAN") and state == "FL" and geo
        if matched and "BRIAN R" not in n:
            status = "high"

    if matched:
        return status, PERSON_BY_SLUG[slug].identity_basis

    expected_surname = {
        "thomas-c-bartzokis": "BARTZOKIS,",
        "jack-brewer": "BREWER,",
        "donna-arduin-kauranen": "ARDUIN KAURANEN,",
        "scott-m-kernan": "KERNAN,",
        "lindsay-l-koren": "KOREN,",
        "julie-myers-wood": "MYERS-WOOD,",
        "george-c-zoley": "ZOLEY,",
        "mark-suchinski": "SUCHINSKI,",
        "paul-laird": "LAIRD,",
        "matthew-t-albence": "ALBENCE,",
        "richard-k-long": "LONG,",
        "david-o-meehan": "MEEHAN,",
        "christopher-d-ryan": "RYAN,",
        "donald-houston": "HOUSTON,",
        "daniel-ragsdale": "RAGSDALE,",
        "scott-a-schipma": "SCHIPMA,",
        "ronald-a-brack": "BRACK,",
        "shayn-p-march": "MARCH,",
        "nicole-mannarino": "MANNARINO,",
        "brian-r-evans": "EVANS,",
    }[slug]
    if not n.startswith(expected_surname):
        return "false_positive", "Search-token collision or different surname/name order; not the SEC-listed person."
    return "unresolved_same_name", "Common-name or mismatched geography/employer/title cluster lacks enough primary-record discriminators."


def row_class(row: dict, identity_status: str) -> tuple[str, bool]:
    if identity_status not in {"confirmed", "high"}:
        return identity_status, False
    label = norm(row.get("line_number_label"))
    if row.get("memoed_subtotal") is True:
        return "memo_or_adjustment", False
    if "TRANSFER" in label:
        return "downstream_transfer", False
    if row.get("entity_type") == "IND" and "CONTRIBUTIONS FROM INDIVIDUALS" in label:
        return "source_individual_receipt", True
    return "other_non_source_receipt", False


def read_schedule_a(source_dir: Path) -> list[dict]:
    rows = []
    pattern = re.compile(r"fec-donor-(.+)-(20\d\d)\.json$")
    for path in sorted((source_dir / "fec").glob("fec-donor-*.json")):
        match = pattern.search(path.name)
        if not match:
            continue
        slug, cycle = match.groups()
        if slug not in PERSON_BY_SLUG:
            continue
        payload = json.loads(path.read_text())
        for row in payload.get("results", []):
            rows.append({"person_slug": slug, "query_cycle": int(cycle), "source_file": str(path), "row": row})
    return rows


def read_refunds(source_dir: Path) -> list[dict]:
    rows = []
    for path in sorted((source_dir / "fec-refund-transactions").glob("*.json")):
        if path.name == "query-summary.json":
            continue
        payload = json.loads(path.read_text())
        if payload.get("classification") != "confirmed_candidate":
            continue
        for row in payload.get("results", []):
            txid = row.get("transaction_id") or ""
            link_status, link_basis = REFUND_LINKS[txid]
            person = payload["person"]
            rows.append({"person": person, "source_file": str(path), "link_status": link_status, "link_basis": link_basis, "row": row})
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):,.2f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    args.report_dir.mkdir(parents=True, exist_ok=True)

    raw = read_schedule_a(args.source_dir)
    matrix = []
    eligible = []
    person_stats = defaultdict(lambda: {"raw": 0, "retained": 0, "source_rows": 0, "gross": Decimal("0"), "geo_pac_rows": 0, "geo_pac_gross": Decimal("0"), "external_rows": 0, "external_gross": Decimal("0"), "trump_named_rows": 0, "trump_named_gross": Decimal("0")})
    committee_stats = defaultdict(lambda: {"rows": 0, "gross": Decimal("0"), "party": "", "name": "", "class": "", "trump_named": False})
    cycle_stats = defaultdict(lambda: {"rows": 0, "gross": Decimal("0")})

    for item in raw:
        slug = item["person_slug"]
        person = PERSON_BY_SLUG[slug]
        row = item["row"]
        status, basis = identity_resolution(slug, row)
        record_class, aggregate = row_class(row, status)
        amount = dec(row.get("contribution_receipt_amount"))
        cid = row.get("committee_id") or ""
        cname = committee_name(row)
        party = party_name(row)
        recipient_class = "geo_company_pac" if cid == GEO_PAC_ID else "external_political_committee"
        trump_named = any(token in cname.upper() for token in TRUMP_NAME_TOKENS)
        person_stats[slug]["raw"] += 1
        if status in {"confirmed", "high"}:
            person_stats[slug]["retained"] += 1
        if aggregate:
            eligible.append((person, row, item))
            ps = person_stats[slug]
            ps["source_rows"] += 1
            ps["gross"] += amount
            if cid == GEO_PAC_ID:
                ps["geo_pac_rows"] += 1
                ps["geo_pac_gross"] += amount
            else:
                ps["external_rows"] += 1
                ps["external_gross"] += amount
            if trump_named:
                ps["trump_named_rows"] += 1
                ps["trump_named_gross"] += amount
            cs = committee_stats[cid]
            cs["rows"] += 1
            cs["gross"] += amount
            cs["party"] = party
            cs["name"] = cname
            cs["class"] = recipient_class
            cs["trump_named"] = trump_named
            cycle_stats[item["query_cycle"]]["rows"] += 1
            cycle_stats[item["query_cycle"]]["gross"] += amount
        matrix.append({
            "canonical_person": person.name,
            "sec_role": person.role,
            "roster_status": person.roster_status,
            "identity_status": status,
            "identity_basis": basis,
            "record_class": record_class,
            "aggregate_eligible": "yes" if aggregate else "no",
            "query_cycle": item["query_cycle"],
            "contribution_date": str(row.get("contribution_receipt_date") or "")[:10],
            "amount": str(amount),
            "contributor_name": row.get("contributor_name") or "",
            "contributor_city": row.get("contributor_city") or "",
            "contributor_state": row.get("contributor_state") or "",
            "contributor_zip": row.get("contributor_zip") or "",
            "employer": row.get("contributor_employer") or "",
            "occupation": row.get("contributor_occupation") or "",
            "committee_id": cid,
            "committee_name": cname,
            "committee_party_official": party,
            "recipient_class": recipient_class,
            "trump_named_committee": "yes" if trump_named else "no",
            "line_number": row.get("line_number") or "",
            "line_number_label": row.get("line_number_label") or "",
            "memoed_subtotal": row.get("memoed_subtotal"),
            "memo_text": row.get("memo_text") or "",
            "amendment_indicator": row.get("amendment_indicator") or "",
            "transaction_id": row.get("transaction_id") or "",
            "sub_id": row.get("sub_id") or "",
            "image_number": row.get("image_number") or "",
            "file_number": row.get("file_number") or "",
            "pdf_url": row.get("pdf_url") or "",
            "source_file": item["source_file"],
        })

    refunds = read_refunds(args.source_dir)
    refund_rows = []
    linked_by_person = defaultdict(lambda: Decimal("0"))
    linked_by_committee = defaultdict(lambda: Decimal("0"))
    all_refunds = Decimal("0")
    linked_refunds = Decimal("0")
    unmatched_refunds = Decimal("0")
    for item in sorted(refunds, key=lambda x: (x["row"].get("disbursement_date") or "", x["row"].get("transaction_id") or "")):
        row = item["row"]
        amount = dec(row.get("disbursement_amount"))
        all_refunds += amount
        if item["link_status"] == "source_linked":
            linked_refunds += amount
            linked_by_person[item["person"]] += amount
            linked_by_committee[row.get("committee_id") or ""] += amount
        else:
            unmatched_refunds += amount
        refund_rows.append({
            "canonical_person": item["person"],
            "committee_id": row.get("committee_id") or "",
            "recipient_name": row.get("recipient_name") or "",
            "recipient_city": row.get("recipient_city") or "",
            "recipient_state": row.get("recipient_state") or "",
            "recipient_zip": row.get("recipient_zip") or "",
            "refund_date": str(row.get("disbursement_date") or "")[:10],
            "refund_amount": str(amount),
            "description": row.get("disbursement_description") or "",
            "line_number": row.get("line_number") or "",
            "memo_text": row.get("memo_text") or "",
            "memoed_subtotal": row.get("memoed_subtotal"),
            "transaction_id": row.get("transaction_id") or "",
            "sub_id": row.get("sub_id") or "",
            "image_number": row.get("image_number") or "",
            "file_number": row.get("file_number") or "",
            "link_status": item["link_status"],
            "link_basis": item["link_basis"],
            "subtracted_from_linked_net": "yes" if item["link_status"] == "source_linked" else "no",
            "source_file": item["source_file"],
        })

    person_rows = []
    for person in PEOPLE:
        s = person_stats[person.slug]
        linked = linked_by_person[person.name]
        person_rows.append({
            "canonical_person": person.name,
            "sec_role": person.role,
            "roster_status": person.roster_status,
            "raw_candidate_rows": s["raw"],
            "identity_retained_rows": s["retained"],
            "excluded_or_unresolved_rows": s["raw"] - s["retained"],
            "source_receipt_rows": s["source_rows"],
            "gross_source_receipts": str(s["gross"]),
            "geo_pac_source_rows": s["geo_pac_rows"],
            "geo_pac_gross": str(s["geo_pac_gross"]),
            "external_source_rows": s["external_rows"],
            "external_gross": str(s["external_gross"]),
            "trump_named_source_rows": s["trump_named_rows"],
            "trump_named_gross": str(s["trump_named_gross"]),
            "linked_refunds": str(linked),
            "linked_refund_net": str(s["gross"] - linked),
            "identity_basis": person.identity_basis,
        })

    committee_rows = []
    for cid, s in sorted(committee_stats.items(), key=lambda kv: (-kv[1]["gross"], kv[0])):
        linked = linked_by_committee[cid]
        committee_rows.append({
            "committee_id": cid,
            "committee_name": s["name"],
            "committee_party_official": s["party"],
            "recipient_class": s["class"],
            "trump_named_committee": "yes" if s["trump_named"] else "no",
            "source_receipt_rows": s["rows"],
            "gross_source_receipts": str(s["gross"]),
            "linked_refunds": str(linked),
            "linked_refund_net": str(s["gross"] - linked),
        })

    cycle_rows = []
    for cycle, s in sorted(cycle_stats.items()):
        cycle_rows.append({"cycle": cycle, "source_receipt_rows": s["rows"], "gross_source_receipts": str(s["gross"])})

    party_class_stats = defaultdict(lambda: {"rows": 0, "gross": Decimal("0")})
    for row in committee_rows:
        key = (
            row["committee_party_official"] or "UNREPORTED_BY_FEC_COMMITTEE_OBJECT",
            row["recipient_class"],
            row["trump_named_committee"],
        )
        party_class_stats[key]["rows"] += int(row["source_receipt_rows"])
        party_class_stats[key]["gross"] += dec(row["gross_source_receipts"])
    party_class_rows = [
        {
            "committee_party_official": party,
            "recipient_class": recipient_class,
            "trump_named_committee": trump_named,
            "source_receipt_rows": values["rows"],
            "gross_source_receipts": str(values["gross"]),
        }
        for (party, recipient_class, trump_named), values in sorted(
            party_class_stats.items(), key=lambda item: (-item[1]["gross"], item[0])
        )
    ]

    prefix = args.report_dir / "2026-07-14-lead-59035-geo-donor"
    write_csv(Path(f"{prefix}-identity-row-matrix.csv"), matrix, list(matrix[0]))
    write_csv(Path(f"{prefix}-person-summary.csv"), person_rows, list(person_rows[0]))
    write_csv(Path(f"{prefix}-committee-summary.csv"), committee_rows, list(committee_rows[0]))
    write_csv(Path(f"{prefix}-cycle-summary.csv"), cycle_rows, list(cycle_rows[0]))
    write_csv(Path(f"{prefix}-party-class-summary.csv"), party_class_rows, list(party_class_rows[0]))
    write_csv(Path(f"{prefix}-refund-ledger.csv"), refund_rows, list(refund_rows[0]))

    gross = sum((s["gross"] for s in person_stats.values()), Decimal("0"))
    geo_pac_gross = sum((s["geo_pac_gross"] for s in person_stats.values()), Decimal("0"))
    external_gross = sum((s["external_gross"] for s in person_stats.values()), Decimal("0"))
    trump_named_gross = sum((s["trump_named_gross"] for s in person_stats.values()), Decimal("0"))
    trump_named_rows = sum(s["trump_named_rows"] for s in person_stats.values())
    summary = {
        "universe_people": len(PEOPLE),
        "people_with_identity_retained_rows": sum(1 for p in PEOPLE if person_stats[p.slug]["retained"]),
        "people_with_zero_raw_rows": [p.name for p in PEOPLE if person_stats[p.slug]["raw"] == 0],
        "raw_schedule_a_candidate_rows": len(raw),
        "identity_retained_rows": sum(s["retained"] for s in person_stats.values()),
        "excluded_or_unresolved_rows": sum(s["raw"] - s["retained"] for s in person_stats.values()),
        "source_receipt_rows": len(eligible),
        "gross_source_receipts": str(gross),
        "geo_pac_source_receipts": str(geo_pac_gross),
        "external_source_receipts": str(external_gross),
        "trump_named_committee_source_rows": trump_named_rows,
        "trump_named_committee_gross": str(trump_named_gross),
        "confirmed_refund_transactions": len(refunds),
        "confirmed_refunds_all": str(all_refunds),
        "source_linked_refund_transactions": sum(r["link_status"] == "source_linked" for r in refunds),
        "source_linked_refunds": str(linked_refunds),
        "confirmed_unmatched_refund_transactions": sum(r["link_status"] == "confirmed_unmatched" for r in refunds),
        "confirmed_unmatched_refunds_non_subtractive": str(unmatched_refunds),
        "source_linked_refund_net": str(gross - linked_refunds),
        "identity_rule": "SEC roster plus full name, geography, title, employer, date, and official career transition; common-name/employer-only mismatches excluded.",
        "source_receipt_rule": "Identity-retained IND rows whose official FEC line label is Contributions From Individuals and memoed_subtotal is false; transfers and memo adjustments excluded.",
        "cycle_2026_boundary": "Year-to-date through the 2026-07-14 archive date; not a completed two-year cycle and not directly comparable to completed-cycle totals.",
        "tenure_boundary": "Identity-scoped, not tenure-scoped. Some retained receipts predate GEO employment or board service; no in-tenure subtotal is inferred.",
    }
    Path(f"{prefix}-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    negative_lines = [
        "# GEO donor identity ambiguity and negative log — lead 59035",
        "",
        "## Identity exclusions",
        "",
        "The row-level matrix preserves every candidate record. The following counts are excluded or unresolved and are not added to personal totals:",
        "",
    ]
    for row in sorted(person_rows, key=lambda r: (-int(r["excluded_or_unresolved_rows"]), r["canonical_person"])):
        if int(row["excluded_or_unresolved_rows"]):
            negative_lines.append(f"- {row['canonical_person']}: {row['excluded_or_unresolved_rows']} of {row['raw_candidate_rows']} candidate rows excluded/unresolved.")
    negative_lines += [
        "",
        "Paul Laird's Los Angeles `GEO GROUP / PROFESSOR` and Redondo Beach `GEO / PROFESSIONAL` records remain unresolved because geography and occupation conflict with the SEC-documented GEO operations career; exact employer text alone was not accepted.",
        "",
        "## Refund-resolution negatives",
        "",
        "- The corrected official Schedule B by-recipient pass returned 57 aggregate candidate rows. Most were organizations containing the searched name or unrelated common-name persons. Transaction-level Florida/amount tests returned zero for the ambiguous Jack Brewer, generic Daniel Ragsdale, and generic Donald Houston hits.",
        "- A $2,200 Schedule B refund from DLJCC PAC to George C. Zoley is identity-confirmed by full name and Boca Raton address, but targeted official Schedule A searches for that committee/name returned zero. It is preserved and not subtracted.",
        "- Earlier ad hoc files used an invalid Schedule B route and encountered HTTP 429 responses. They were overwritten by corrected `/v1/schedules/schedule_b/by_recipient/` cycle results and are excluded from every conclusion.",
        "",
        "## State-record boundary",
        "",
        "The official Florida campaign-finance portal returned a Cloudflare challenge, and the advertised in-app browser backend had no available browser session. The archived challenge page documents access failure. No Florida person-level zero or state total is asserted.",
        "",
    ]
    Path(f"{prefix}-ambiguity-negative-log.md").write_text("\n".join(negative_lines))

    top_people = sorted(person_rows, key=lambda r: -dec(r["gross_source_receipts"]))[:10]
    report = [
        "# GEO executive/director federal donor identity resolution — lead 59035",
        "",
        "## Outcome",
        "",
        f"The SEC-bounded universe contains {summary['universe_people']} people. Nineteen have identity-retained FEC Schedule A rows; Scott M. Kernan returned zero exact-full-name rows across cycles 2016, 2018, 2020, 2022, 2024, and 2026. This is a bounded federal negative, not a claim that he never donated.",
        "",
        f"The FEC pass produced {summary['raw_schedule_a_candidate_rows']:,} candidate rows. Identity controls retain {summary['identity_retained_rows']:,}; the memo/transfer-safe source rule retains {summary['source_receipt_rows']:,} individual-receipt rows totaling ${money(gross)} gross. Those receipts split into ${money(geo_pac_gross)} to GEO's federal PAC and ${money(external_gross)} to external federal political committees. These are receipts attributed to individuals, not corporate contributions.",
        "",
        "The totals are identity-scoped to people in the SEC-bounded roster, not tenure-scoped to dates when each person served GEO. Some retained receipts expressly predate GEO employment or board service, including Suchinski/Spirit AeroSystems, Koren/Darden, and Bartzokis medical-practice records. No in-tenure subtotal is inferred.",
        "",
        f"Transaction-level Schedule B review confirms seven refunds totaling ${money(all_refunds)}. Six totaling ${money(linked_refunds)} have a source-receipt link and produce a conservative linked-refund net of ${money(gross - linked_refunds)}. The separate ${money(unmatched_refunds)} DLJCC PAC refund is confirmed but not subtracted because the original Schedule A receipt was not found in targeted processed-data searches.",
        "",
        "## Identity method",
        "",
        "The 2026 SEC proxy supplies the current seven-director slate and thirteen-officer roster (George C. Zoley overlaps); the 2024 proxy supplies former CFO/CEO Brian R. Evans. A row is retained only when the name is corroborated by a combination of full/middle name, location, employer, title, date, or a career transition described in the proxy. Employer text alone is insufficient for common names.",
        "",
        "The source-receipt rule then requires an identity-retained FEC `IND` row, an official line label for contributions from individuals, and `memoed_subtotal=false`. This keeps Form 3P line 17A individual receipts where the official label identifies them as individual contributions, while excluding memo redesignations, reattributions, and JFC/downstream transfers.",
        "",
        "## Largest gross personal receipt totals",
        "",
        "| Person | Source rows | Gross | GEO PAC | External | Linked refunds | Linked-refund net |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in top_people:
        report.append(
            f"| {row['canonical_person']} | {row['source_receipt_rows']} | ${money(dec(row['gross_source_receipts']))} | ${money(dec(row['geo_pac_gross']))} | ${money(dec(row['external_gross']))} | ${money(dec(row['linked_refunds']))} | ${money(dec(row['linked_refund_net']))} |"
        )
    report += [
        "",
        "The full 20-person table, committee table, cycle table, and party/class table are in the CSV artifacts. Committee party fields are reproduced only where the FEC committee object supplies official party metadata. `trump_named_committee` is a literal committee-name flag, not an ideological or influence assessment.",
        "",
        "## Literal Trump-named committee subset",
        "",
        f"Ten source-receipt rows totaling ${money(trump_named_gross)} went to committees whose official FEC names literally contain Trump, Save America, Never Surrender, or MAGA. The person breakdown is George C. Zoley ${money(person_stats['george-c-zoley']['trump_named_gross'])}, Brian R. Evans ${money(person_stats['brian-r-evans']['trump_named_gross'])}, Daniel Ragsdale ${money(person_stats['daniel-ragsdale']['trump_named_gross'])}, and Thomas C. Bartzokis ${money(person_stats['thomas-c-bartzokis']['trump_named_gross'])}. This is a gross committee-name classification only, not a complete ideological category, tenure-scoped total, or evidence of access or influence.",
        "",
        "## Notable identity resolutions",
        "",
        "- Mark Suchinski's records transition from Wichita/Spirit AeroSystems through June 2024 to Florida/GEO after his SEC-reported July 8, 2024 appointment. This resolves records beyond a GEO-only employer search.",
        "- Lindsay Koren's Orlando/Darden records and later Boca/GEO board records follow the employer/role chronology in the SEC proxy.",
        "- Thomas Bartzokis's pre-board Boca medical-practice records match the distinctive practice named in his SEC biography.",
        "- Brian Evans's Florida GEO CFO and 2024 CEO records match the 2024 SEC proxy; the Tonawanda, New York debt-collector cluster is excluded.",
        "- Paul Laird's Charlotte/Boca/Delray GEO operations and secure-services records are retained. The Los Angeles and Redondo Beach records are unresolved despite GEO employer text and are excluded.",
        "",
        "## Refund controls",
        "",
        "Schedule B aggregate hits are not themselves treated as refunds. The refund ledger contains only transaction rows with person, committee, date, amount, description, line, filing identifiers, and link status. The unmatched $2,200 item remains outside the net.",
        "",
        "## Coverage and limitations",
        "",
        "- Federal Schedule A coverage: six cycles from 2016 through 2026, plus one targeted 2014 lookup solely to resolve a 2015 refund link. Cycle 2026 is year-to-date through the July 14, 2026 archive date; it is not a completed two-year cycle and should not be compared as an equal-duration total.",
        "- Federal Schedule B coverage: the same six cycles for all 20 names, followed by transaction-level resolution of plausible hits.",
        "- Florida state coverage: unavailable because the official portal returned a Cloudflare challenge and no interactive browser backend was available. This is logged as an access boundary, not a zero.",
        "- Candidate-name searches produce substring and same-name noise; every excluded row remains in the matrix for audit.",
        "- The totals are identity-scoped, not tenure-scoped. They include retained pre-GEO or pre-board receipts where SEC career history resolves identity; no in-tenure subtotal was built.",
        "- Totals describe receipts reported under resolved individual identities. They do not establish motive, access, favor, or policy influence.",
        "",
        "## Primary evidence",
        "",
        f"- `{args.source_dir / 'sec/geo-2026-def14a.html'}`",
        f"- `{args.source_dir / 'sec/geo-2024-def14a.html'}`",
        f"- `{args.source_dir / 'fec'}` (120 Schedule A cycle files)",
        f"- `{args.source_dir / 'fec-refunds'}` (120 corrected Schedule B aggregate cycle files)",
        f"- `{args.source_dir / 'fec-refund-transactions'}` (transaction-resolution files)",
        f"- `{args.source_dir / 'fec-refund-links'}` (targeted Schedule A/committee link files)",
        "",
    ]
    Path(f"{prefix}-report.md").write_text("\n".join(report))

    state_diag = {
        "source": "Florida Division of Elections campaign-finance portal",
        "status": "blocked_by_cloudflare_challenge",
        "browser_backend": "unavailable",
        "interpretation": "access diagnostic only; not a zero-result search",
        "archived_response": str(args.source_dir / "state/florida-campaign-finance-cloudflare-response.html"),
    }
    (args.source_dir / "state/florida-campaign-finance-access-diagnostic.json").write_text(json.dumps(state_diag, indent=2, sort_keys=True) + "\n")

    manifest_paths = sorted(
        [p for p in args.source_dir.rglob("*") if p.is_file()]
        + [p for p in args.report_dir.glob("2026-07-14-lead-59035-geo-donor-*") if p.is_file() and not p.name.endswith("manifest.sha256")]
    )
    manifest = []
    for path in manifest_paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.append(f"{digest}  {path}")
    Path(f"{prefix}-manifest.sha256").write_text("\n".join(manifest) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
