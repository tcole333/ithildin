import csv
import hashlib
import json
import pathlib
import re
import sqlite3
import collections

csv.field_size_limit(16 * 1024 * 1024)
base = pathlib.Path("investigations/hassan-boston")
out = base / "evidence/wave2/timeline-baseline"
out.mkdir(parents=True, exist_ok=True)
report_dir = base / "reports/wave2"
report_dir.mkdir(parents=True, exist_ok=True)
fields = "event_id property_key property_label municipality county parcel_id event_date date_precision date_basis event_type from_party from_capacity to_party to_capacity consideration_usd loan_amount_usd registry book_page instrument_id evidence_status source_url source_ref source_quote finding_ids notes".split()
read_paths = [
    "evidence/properties/assessment-observations.json",
    "evidence/properties/parcel-inventory-fy2026.json",
    "evidence/properties/permit-observations.json",
    "evidence/properties/citation-map.json",
    "evidence/deeds-finance/instrument-ledger.csv",
    "evidence/deeds-finance/scan-observations.md",
    "evidence/deeds-finance/index-selected-transcription.txt",
    "evidence/identities/name-variants.csv",
    "evidence/litigation/fienberg-2010-opinion.txt",
    "evidence/wave2/suffolk/scan-observations.md",
]
inputs = {
    r: {
        "path": str(base / r),
        "sha256": hashlib.sha256((base / r).read_bytes()).hexdigest(),
    }
    for r in read_paths
}
assess = json.loads((base / read_paths[0]).read_text())
current = json.loads((base / read_paths[1]).read_text())
permits = json.loads((base / read_paths[2]).read_text())
citations = json.loads((base / read_paths[3]).read_text())
ledger = list(csv.DictReader((base / read_paths[4]).open(newline="")))
assert (
    next(x for x in ledger if x["book_page"] == "17988/312")["amount_usd"] == "1925000"
), "Wait for corrected 1993 source ledger; old $1.725m cannot be reused."
c = sqlite3.connect("file:investigation.db?mode=ro", uri=True)
c.row_factory = sqlite3.Row
finding_rows = [
    dict(r)
    for r in c.execute(
        "select fe.*,f.summary,f.detail,f.date_of_event,f.event_date_iso,f.date_precision from finding_evidence fe join findings f on f.id=fe.finding_id where f.profile_id='hassan-boston' and f.id<=15579"
    )
]
byref = collections.defaultdict(list)
for r in finding_rows:
    byref[r["evidence_ref"]].append(r)
assert (
    "1,925,000"
    in next(x for x in finding_rows if x["finding_id"] == 15578)["source_quote"]
)
(out / "existing-findings-evidence.json").write_text(json.dumps(finding_rows, indent=2))
index_lines = {
    line.split("\t")[1]: line
    for line in (base / "evidence/deeds-finance/index-selected-transcription.txt")
    .read_text()
    .splitlines()
    if "\t" in line
}
properties = {}
events = []
metrics = []


def slug(s):
    return re.sub("[^A-Z0-9]+", "-", s.upper()).strip("-")


def prop(pid=None, label="", key=None, group=None, join="source_exact_parcel_id"):
    key = key or "US-MA-SUFFOLK:PARCEL:" + pid
    if key not in properties:
        properties[key] = {
            "property_key": key,
            "property_label": label,
            "municipality": "Boston",
            "county": "Suffolk",
            "parcel_id": pid or "",
            "labels": set(),
            "association_group": group or "",
            "join_state": join,
        }
    if label:
        properties[key]["labels"].add(label)
    return properties[key]


for x in current:
    p = prop(
        x["parcel_id"],
        x["situs_address"] + (" unit " + str(x["unit"]) if x.get("unit") else ""),
        group=x["association_group"],
    )
    p["fy2026_owner"] = x["assessor_owner"]
    p["fy2026_land_use"] = x["land_use"]
    p["fy2026_assessed_value_usd"] = x["assessed_total_value_usd"]


def newevent(p, **kw):
    e = {f: "" for f in fields}
    e.update(
        {
            f: p.get(f, "")
            for f in [
                "property_key",
                "property_label",
                "municipality",
                "county",
                "parcel_id",
            ]
        }
    )
    e.update(kw)
    assert e["event_id"] and e["source_url"] and e["source_quote"]
    events.append(e)
    return e


for x in assess:
    p = prop(
        x["parcel_id"],
        x["situs_address"] + (" unit " + str(x["unit"]) if x.get("unit") else ""),
    )
    ref = x["evidence_ref"]
    quote = json.dumps(x["raw_row"], ensure_ascii=False, separators=(",", ":"))
    # Retain only fields necessary for the timeline quote; source raw rows remain in wave1.
    raw = x["raw_row"]
    qkeys = [
        "PID",
        "Parcel_ID",
        "ST_NUM",
        "ST_ALPHA",
        "ST_NUM2",
        "ST_NAME",
        "ST_NAME_SUF",
        "UNIT_NUM",
        "OWNER",
        "MAIL_ADDRESSEE",
        "LU",
        "TOTAL_VALUE",
        "AV_TOTAL",
        "FY2008_TOTAL",
    ]
    quote = json.dumps({k: raw[k] for k in qkeys if k in raw}, ensure_ascii=False)
    e = newevent(
        p,
        event_id=ref,
        event_date=str(x["fiscal_year"]),
        date_precision="year",
        date_basis="assessment_fiscal_year",
        event_type="assessment_observation",
        to_party=x["assessor_owner"],
        to_capacity="assessor owner field",
        registry="Boston Assessing Department",
        evidence_status="official_assessment_observation",
        source_url=x["source_url"],
        source_ref=ref,
        source_quote=quote,
        finding_ids=";".join(str(r["finding_id"]) for r in byref[ref]),
        notes=f"assessed_value_usd={x['assessed_total_value_usd']}; land_use={x['land_use']}; raw_parcel_id={x['raw_parcel_id']}; fiscal year, not an execution or recording date. No title transfer or beneficial ownership is inferred. {('Condominium master record: no unit ownership or zero economic value inferred.' if x['land_use'] == 'CM' else '')}",
    )
    metrics.append(
        {
            "event_id": e["event_id"],
            "metric": "assessment",
            "amount_usd": x["assessed_total_value_usd"],
            "qualifier": "assessed value",
            "scope": p["property_key"],
        }
    )
for x in permits:
    pid = str(int(x["parcel_id"])).zfill(10)
    p = prop(
        pid,
        x["address"],
        group="permit_only_context"
        if "US-MA-SUFFOLK:PARCEL:" + pid not in properties
        else None,
    )
    ref = x["evidence_ref"]
    raw = {
        k: x.get(k)
        for k in [
            "permitnumber",
            "parcel_id",
            "address",
            "applicant",
            "permittypedescr",
            "worktype",
            "issued_date",
            "status",
            "declared_valuation",
            "comments",
        ]
    }
    typ = "demolition_permit" if x.get("worktype") == "RAZE" else "municipal_permit"
    note = f"issued_timestamp_raw={x['issued_date']}; status={x['status']}; declared_work_valuation_raw={x['declared_valuation']}; worktype={x['worktype']}; Applicant is not necessarily owner. Permit issuance/status does not prove work completion. Address labels can span multiple parcels; only the source parcel_id is joined."
    if (x.get("applicant") or "").lower() == "sam hassan":
        note += " Sam Hassan is context-dependent and is not assigned automatically to Hicham or Houssam."
    newevent(
        p,
        event_id=ref,
        event_date=x["issued_date"][:10],
        date_precision="day",
        date_basis="permit_issue_date",
        event_type=typ,
        to_party=x.get("applicant") or "",
        to_capacity="permit applicant as recorded",
        registry="Boston Inspectional Services Department",
        instrument_id=x["permitnumber"],
        evidence_status="official_permit_observation",
        source_url=x["source_url"],
        source_ref=ref,
        source_quote=json.dumps(raw, ensure_ascii=False),
        finding_ids=";".join(str(r["finding_id"]) for r in byref[ref]),
        notes=note,
    )
# Original document review establishes parties/capacities; address-range joins remain transparent.
pidmap = {
    "17988/312": ["0501161000", "0501160000", "0501159000"],
    "19678/333": ["0501164000"],
    "19679/1": ["0501164000"],
    "20428/305": ["0501234000"],
    "20630/164": ["0503224000", "0503225000"],
    "20630/170": ["0503225000"],
    "20630/196": ["0503225000"],
    "21956/113": ["0502425000"],
    "21956/120": ["0502425000"],
    "25267/67": ["0502425000"],
    "33269/285": ["0502425000"],
    "33486/4": ["0502425000"],
    "41799/224": ["0501234000"],
    "56448/317": ["0501162000"],
    "56448/321": ["0501161000"],
    "56617/263": ["0501234000"],
    "56617/267": ["0503224000", "0503225000"],
    "56617/271": ["0501164000"],
    "56617/279": ["0502425000"],
    "58093/179": ["0402740000"],
    "63244/72": ["0103178000"],
    "66220/61": ["0503608000"],
    "69490/332": ["0103648004"],
    "72957/242": ["0503224000", "0503225000"],
}
parties = {
    "17988/312": (
        "Boylston Boston Corporation",
        "grantor",
        "Hicham Ali Hassan; Abdul Rahman Ali Hassan; Zouhair Ali Hassan",
        "trustees of 400 Boylston Street Realty Trust",
    ),
    "19679/1": (
        "Hicham Ali Hassan; Zouhair Ali Hassan",
        "trustees of 376 Boylston Street Realty Trust; mortgagors",
        "Berkshire Life Insurance Company",
        "mortgagee",
    ),
    "21956/120": (
        "Institutional Asset LLC",
        "foreclosure deed grantor",
        "Zouhair Ali Hassan",
        "trustee of Eighteen Brimmer Street Realty Trust",
    ),
    "56617/267": (
        "Hicham Ali Hassan",
        "trustee of 216-218 Newbury Street Realty Trust",
        "216-218 Newbury Street Realty LLC",
        "grantee",
    ),
    "56617/279": (
        "Hicham Ali Hassan",
        "trustee of Eighteen Brimmer Street Realty Trust",
        "Hassan Residential Properties LLC",
        "grantee",
    ),
    "72957/242": (
        "216-218 Newbury Street Realty LLC",
        "attached property owner",
        "Tivoli Audio Inc.",
        "attaching party",
    ),
}
reviewed = set(parties)
review_ids = {
    "17988/312": 15578,
    "19679/1": 15539,
    "21956/120": 15572,
    "56617/267": 15570,
    "56617/279": 15569,
    "72957/242": 15573,
}
for row in ledger:
    bp = row["book_page"]
    ref = "SUFFOLK-DEEDS:" + bp
    inst = "US-MA-SUFFOLK:RECORDED:" + bp
    pp = [prop(pid) for pid in pidmap.get(bp, [])]
    if not pp:
        label = row["property_business_pivot"]
        if label and label != "Boylston Street":
            key = "US-MA-SUFFOLK:ADDRESS:BOSTON:" + slug(label)
            join = "index_address_candidate_unjoined"
        else:
            key = "US-MA-SUFFOLK:UNRESOLVED:" + bp.replace("/", "-")
            join = "property_unresolved"
        pp = [
            prop(
                label=label or "Property unspecified in indexed tax lien",
                key=key,
                group="index_only_property_candidate",
                join=join,
            )
        ]
    if bp in reviewed:
        ev = next(r for r in byref[ref] if r["finding_id"] == review_ids[bp])
        quote = ev["source_quote"]
        status = (
            "original_complete_review"
            if bp in ["17988/312", "72957/242"]
            else "original_partial_review"
        )
        fid = str(review_ids[bp])
        fp, fc, tp, tc = parties[bp]
    else:
        quote = index_lines[bp]
        status = "index_only_candidate"
        fid = ""
        fp = fc = tp = tc = ""
        if "Grantee" in row["capacity"]:
            tp = row["parties_exact_or_read"]
            tc = "index grantee; capacity not resolved"
        else:
            fp = row["parties_exact_or_read"]
            fc = "index grantor; capacity not resolved"
    eventbase = {
        "DEED": "deed",
        "QUITCLAIM DEED": "deed",
        "FORECLOSURE DEED": "foreclosure_deed",
        "UNIT DEED": "unit_deed",
        "MORTGAGE": "mortgage",
        "FINANCING STATEMENT": "financing_statement",
        "AGREEMENT": "trust_agreement",
        "LIEN": "lien",
        "TAX LIEN": "tax_lien",
        "WRIT OF ATTACHMENT": "attachment",
    }[row["type"]]
    eventtype = eventbase + ("_recorded" if bp in reviewed else "_index_candidate")
    for p in pp:
        note = f"review_state={row['review_state']}; {row['notes']}; recorded_date={row['recorded_date']}; execution date not established unless separately stated. {row['release_or_encumbrance_status']}. "
        if bp == "17988/312":
            note = "review_state=all three original pages read; execution_date=1992-12-23; acknowledgment_date=1992-12-23; recorded_date=1993-01-15; recording_time=13:47; document_number=357. Page 1 describes 392–394 and 396–398 Boylston; page 2 describes 400–402 Boylston and references predecessor deed 17463/182 dated 1992-05-07. Current title and source of purchase funds are not established by this acquisition alone. "
        if bp in pidmap:
            note += "Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. "
        if len(pp) > 1:
            note += f"Shared instrument covering {len(pp)} property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. "
        if bp == "20630/164":
            note += "execution_date=1996-06-05 as cited by 2016 deed56617/267; two-parcel scope is documented in that later deed reference. "
        if bp in ["56617/267", "56617/279"]:
            note += "consideration_comparator=less_than; consideration_upper_bound_usd=100; exact consideration unknown, numeric consideration field intentionally blank. "
        if bp == "17988/312":
            note += "Corrected original-image reading: consideration $1,925,000; handwritten words One Million Nine Hundred Twenty Five Thousand Dollars replace crossed-out typed Two Million Dollars. The full review is recorded in evidence/wave2/suffolk/scan-observations.md and audited finding 15578. The trust beneficiary schedule remains separate from this deed. "
        if bp == "72957/242":
            note += "attachment_amount_usd=405000; approval_date=2026-06-29; issuance_date=2026-06-30; sheriff_attachment=2026-07-01 10:40; overlaps underlying court awards, not an additional debt. "
        if bp in ["17328/343", "17329/1"]:
            note += "HASSAN ABDUL R is not expanded to Abdul Rahman for this instrument. No automatic join to the modern 220 Boylston condominium from a shared unit number. "
        if bp == "64658/183":
            note += "Index address is 33 Havre, not the current 31 Havre parcel; address discrepancy unresolved and properties are not merged. "
        if bp in ["46991/183", "58093/179"]:
            note += "Mortgage index grantee may denote mortgagee/lender; do not label Houssam as borrower. "
        if bp == "72170/29":
            note += "Talal person identity remains unresolved. Precise unit detail is an internal matching pivot, not a verified subject residence. "
        numeric = row["amount_usd"] if row["amount_usd"].isdigit() else ""
        consideration = (
            numeric
            if bp in reviewed and eventbase in ["deed", "foreclosure_deed", "unit_deed"]
            else ""
        )
        loan = numeric if bp in reviewed and eventbase == "mortgage" else ""
        e = newevent(
            p,
            event_id=inst + ":" + p["property_key"].split(":", 3)[-1],
            event_date=row["recorded_date"],
            date_precision="day",
            date_basis="registry_recording_date",
            event_type=eventtype,
            from_party=fp,
            from_capacity=fc,
            to_party=tp,
            to_capacity=tc,
            consideration_usd=consideration,
            loan_amount_usd=loan,
            registry="Suffolk Registry of Deeds — Recorded Land",
            book_page=bp,
            instrument_id=inst,
            evidence_status=status,
            source_url="https://www.masslandrecords.com/SUFFOLK/D/Default.aspx",
            source_ref=ref,
            source_quote=quote,
            finding_ids=fid,
            notes=note,
        )
# Existing court decisions connected to a specific property; not title transfers.
for fid, pids in [
    (15508, ["0501162000"]),
    (15574, ["0503224000", "0503225000"]),
    (15575, ["0503224000", "0503225000"]),
    (15576, ["0503224000", "0503225000"]),
]:
    ev = next(x for x in finding_rows if x["finding_id"] == fid)
    for pid in pids:
        p = prop(pid)
        note = (
            ev["summary"]
            + " "
            + ev["detail"]
            + " Judicial order is not a recorded deed, evidence of payment, or current debt balance."
        )
        if fid == 15508:
            note += " Court address is382–390 Boylston; correspondence to assessment384–390 is an address-range candidate until the deed/legal description is reviewed."
        else:
            note += " Same court action affects both Newbury parcels; any award must be counted once, never once per property."
        newevent(
            p,
            event_id=f"MA-COURT:FINDING:{fid}:PARCEL:{pid}",
            event_date=ev["event_date_iso"],
            date_precision=ev["date_precision"],
            date_basis="court_order_date",
            event_type="court_order",
            to_party="Andrew Fienberg, trustee of Aidee Realty Trust; Hicham Ali Hassan"
            if fid == 15508
            else "216-218 Newbury Street Realty LLC; Tivoli Audio Inc.",
            to_capacity="litigants; participant list, no title transfer",
            registry="Massachusetts Appeals Court"
            if fid == 15508
            else "Suffolk Superior Court / Business Litigation Session",
            instrument_id="09-P-1545" if fid == 15508 else "2184CV00205-BLS1",
            evidence_status="judicial_text_reviewed_property_join_candidate"
            if fid == 15508
            else "judicial_text_reviewed",
            source_url=ev["evidence_ref"],
            source_ref=ev["evidence_ref"],
            source_quote=ev["source_quote"],
            finding_ids=str(fid),
            notes=note,
        )
# Property-wide public development decision; estimate is neither a purchase nor a loan.
ev = next(x for x in finding_rows if x["finding_id"] == 15566)
p = prop("0501234000")
ref = ev["evidence_ref"]
newevent(
    p,
    event_id=ref,
    event_date="2026-05-14",
    date_precision="day",
    date_basis="board_approval_date",
    event_type="development_approval",
    to_party="419 Boylston Street Realty LLC",
    to_capacity="project proponent",
    registry="Boston Planning & Development Agency",
    instrument_id="BPDA8308",
    evidence_status="official_board_document_reviewed",
    source_url=citations[ref],
    source_ref=ref,
    source_quote=ev["source_quote"],
    finding_ids="15566",
    notes="Approved plan:41 rental units,7 income-restricted; development_cost_estimate_usd=7761888; PILOT_application_date=2025-08-29. Plan webpage still describes44 units; prefer dated approved document. Approval is not evidence of construction completion, executed PILOT agreement, or funded financing.",
)
# Property-unallocated family agreement/case stays separate to avoid assigning alleged beneficial shares to title intervals.
family = prop(
    label="Family-property interests described in case2084CV00531 (property allocation unresolved)",
    key="US-MA-SUFFOLK:UNRESOLVED:FAMILY-INTERESTS-2084CV00531",
    group="family_claims_not_title",
    join="unallocated_case_context",
)
for fid, date, typ, basis in [
    (
        15505,
        "2000-12-14",
        "alleged_family_agreement",
        "agreement_date_alleged_in_2020_opinion",
    ),
    (15506, "2020-07-23", "court_order", "court_order_date"),
    (
        15579,
        "2022-08-18",
        "case_disposition",
        "docket_judgment_date_in_public_reproduction",
    ),
]:
    ev = next(x for x in finding_rows if x["finding_id"] == fid)
    note = (
        ev["summary"]
        + " "
        + ev["detail"]
        + " No ownership interval or beneficial share is created from this event. The original agreement and settlement terms remain outstanding."
    )
    if fid == 15579:
        note += "Stipulation signed/filed2022-08-17; reproduced docket judgment2022-08-18; execution and docket dates are distinct."
    newevent(
        family,
        event_id=f"MA-COURT:FINDING:{fid}:FAMILY-CONTEXT",
        event_date=date,
        date_precision="day",
        date_basis=basis,
        event_type=typ,
        to_party="Hicham Ali Hassan; Tarek Ali Hassan",
        to_capacity="parties named in court record; participant list, no title transfer",
        registry="Suffolk Superior Court / Business Litigation Session",
        instrument_id="2084CV00531",
        evidence_status="allegations_in_judicial_opinion"
        if fid == 15505
        else (
            "public_filed_document_reproduction"
            if fid == 15579
            else "judicial_text_reviewed"
        ),
        source_url=ev["evidence_ref"],
        source_ref=ev["evidence_ref"],
        source_quote=ev["source_quote"],
        finding_ids=str(fid),
        notes=note,
    )
# Exact data contract; no source metrics placed in wrong monetary columns.
events.sort(key=lambda e: (e["property_key"], e["event_date"], e["event_id"]))
assert len({x["event_id"] for x in events}) == len(events)
for e in events:
    assert set(e) == set(fields)
    assert re.fullmatch(r"\d{4}(-\d{2}-\d{2})?", e["event_date"])
    assert not (e["consideration_usd"] and e["loan_amount_usd"])
    if e["event_type"] == "assessment_observation":
        assert not e["consideration_usd"] and not e["loan_amount_usd"]
    if e["book_page"] in ["56617/267", "56617/279"]:
        assert not e["consideration_usd"]
    if e["event_type"] in [
        "court_order",
        "case_disposition",
        "alleged_family_agreement",
    ]:
        assert not e["from_party"] and not e["from_capacity"]
    assert "1,725,000" not in e["source_quote"] and "1725000" not in e["source_quote"]
with (out / "events.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(events)
(out / "events.json").write_text(json.dumps(events, indent=2))
# Compact property-level gaps and machine-readable stable aliases.
coverage = []
for key, p in sorted(properties.items()):
    rr = [x for x in events if x["property_key"] == key]
    docs = [
        x
        for x in rr
        if x["event_type"]
        in ["deed_recorded", "foreclosure_deed_recorded", "unit_deed_recorded"]
    ]
    candidates = [x for x in rr if x["evidence_status"] == "index_only_candidate"]
    a = [x for x in rr if x["event_type"] == "assessment_observation"]
    perm = [
        x for x in rr if x["event_type"] in ["municipal_permit", "demolition_permit"]
    ]
    gaps = []
    if not docs:
        gaps.append("No original title deed reviewed in baseline")
    elif any(x["evidence_status"] == "original_partial_review" for x in docs):
        gaps.append(
            "Reviewed deeds are partial-page observations; complete legal descriptions, execution dates, intervening instruments, and current recorder search remain needed"
        )
    else:
        gaps.append(
            "Complete acquisition deed reviewed; intervening instruments, beneficiary schedule, and current recorder search remain needed"
        )
    if candidates:
        gaps.append(
            "Read originals: "
            + ", ".join(dict.fromkeys(x["book_page"] for x in candidates))
        )
    if a:
        gaps.append(
            "Assessment snapshots do not fill title intervals or establish beneficial shares"
        )
    if p.get("fy2026_land_use") == "CM":
        gaps.append(
            "Condominium master: join individual units and deed/disposition schedule"
        )
    if p.get("association_group") == "houssam_historical_other_owner_current":
        gaps.append(
            "Historical subject/vehicle label differs from FY2026; disposition deed and consideration needed"
        )
    if p["join_state"] != "source_exact_parcel_id":
        gaps.append(
            "Resolve parcel and party identity before assigning to a current holding"
        )
    if key.endswith("0502425000"):
        gaps.append(
            "Brimmer:21956/113 trust;19143/176 senior mortgage;21879/264 foreclosing mortgage; remaining21956/120 pages; lien releases"
        )
    if key.endswith("0501164000"):
        gaps.append(
            "Berkshire release27659/170 unread; acquisition19678/333 and2016transfer56617/271 originals needed"
        )
    if key.endswith(("0503224000", "0503225000")):
        gaps.append(
            "Newbury:trust20592/119;acquisition20630/164;mortgage20630/170;financing20630/196;certificate56617/269;attachment72957/242 satisfaction and updated court balance"
        )
    if key.endswith("0501234000"):
        gaps.append(
            "419:acquisition20428/305;transfer56617/263;historical lien releases;executed PILOT agreement and project financing"
        )
    if "33-HAVRE" in key:
        gaps.append(
            "Do not merge33Havre with31Havre without original-document address bridge"
        )
    cover = {
        k: p.get(k, "")
        for k in [
            "property_key",
            "property_label",
            "municipality",
            "county",
            "parcel_id",
            "association_group",
            "join_state",
            "fy2026_owner",
            "fy2026_land_use",
            "fy2026_assessed_value_usd",
        ]
    }
    cover.update(
        {
            "aliases": sorted(p["labels"]),
            "event_count": len(rr),
            "date_first": min(x["event_date"] for x in rr),
            "date_last": max(x["event_date"] for x in rr),
            "assessment_count": len(a),
            "permit_count": len(perm),
            "reviewed_title_event_count": len(docs),
            "index_candidate_count": len(candidates),
            "gaps": gaps,
        }
    )
    coverage.append(cover)
(out / "coverage-manifest.json").write_text(json.dumps(coverage, indent=2))
with (out / "property-coverage.csv").open("w", newline="") as f:
    cols = list(coverage[0])
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(
        [
            {k: ("; ".join(v) if isinstance(v, list) else v) for k, v in x.items()}
            for x in coverage
        ]
    )
with (out / "event-metrics.csv").open("w", newline="") as f:
    w = csv.DictWriter(
        f, fieldnames=["event_id", "metric", "amount_usd", "qualifier", "scope"]
    )
    w.writeheader()
    w.writerows(metrics)
manifest = {
    "contract_fields": fields,
    "schema_version": "hassan-boston-wave2-v1",
    "retrieved_from_local_evidence": "2026-09-04",
    "online_searches_this_task": 0,
    "initial_wave_files_modified": False,
    "event_count": len(events),
    "property_count": len(properties),
    "exact_boston_pid_count": sum(bool(x["parcel_id"]) for x in coverage),
    "unique_recorded_instruments": len(ledger),
    "event_types": dict(collections.Counter(x["event_type"] for x in events)),
    "inputs": inputs,
    "notes": [
        "No title interval inferred from an assessment, permit, corporate officer, mortgage, index-only row, or pleading.",
        "Multi-parcel instruments share instrument_id; monetary sums require transaction-level deduplication.",
        "1993 deed 17988/312: all three original pages reviewed by source owner; three parcels; consideration 1925000; executed 1992-12-23 and recorded 1993-01-15.",
        "Property units/addresses in unresolved candidates are internal matching details; avoid identifying them as subject residences.",
    ],
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2))
# Readable property-by-property baseline; raw event chronology remains available without overwhelming permit detail.
s = [
    "# Property ownership timeline — local baseline",
    "",
    f"This baseline contains {len(events)} dated events across {len(properties)} property/context keys. It preserves all147 assessment observations,200 existing permits and32 registry instruments, plus existing property-related court and development records. No new online searches were performed. It is a source chronology, not a completed legal title chain.",
    "",
    "**Files:** `evidence/wave2/timeline-baseline/events.csv` follows the exact25-column WAVE2 contract. `coverage-manifest.json` and `property-coverage.csv` expose gaps and aliases; `event-metrics.csv` keeps assessed values out of consideration/loan fields.",
    "",
    "**Critical distinctions:** The corrected1993 acquisition consideration is$1,925,000, replacing the erroneous earlier$1,725,000 reading. The two2016quitclaims state less than$100; numeric consideration stays blank. A mortgage grantee may be lender. FY years have year precision and are not assigned a fabricated January1 date. Current ownership/beneficial shares are not inferred from officer, assessment, permit, court pleading or index records.",
    "",
    "**Unresolved joins:**33Havre versus31Havre is separate. The1992Four Seasons Place unit candidate is separate from the modern condominium parcel. Houssam mortgagee candidates and Talal unit-deed candidate remain unverified in capacity/identity. Family agreement claims remain under an unallocated case-context key rather than manufacturing property shares.",
    "",
    "## Property-by-property chronology",
    "",
]
for cover in coverage:
    key = cover["property_key"]
    rr = [x for x in events if x["property_key"] == key]
    s.extend(
        [
            "### " + cover["property_label"],
            "",
            f"`{key}` — association group: `{cover['association_group']}`; join: `{cover['join_state']}`.",
            "",
        ]
    )
    a = [x for x in rr if x["event_type"] == "assessment_observation"]
    if a:
        s.append("Assessment owner observations (not title transfers):")
        for x in a:
            s.append(
                f"- **FY{x['event_date']}** — {x['to_party']}. [{x['source_ref']}]({x['source_url']})"
            )
        s.append("")
    non = [
        x
        for x in rr
        if x["event_type"] not in ["assessment_observation", "municipal_permit"]
    ]
    for x in non:
        amount = (
            f"; consideration ${int(x['consideration_usd']):,}"
            if x["consideration_usd"]
            else ""
        ) + (
            f"; mortgage face amount ${int(x['loan_amount_usd']):,}"
            if x["loan_amount_usd"]
            else ""
        )
        if x["event_type"] in [
            "court_order",
            "case_disposition",
            "alleged_family_agreement",
        ]:
            party = "Participants: " + x["to_party"]
        else:
            party = (x["from_party"] + " → " + x["to_party"]).strip(" →")
        s.append(
            f"- **{x['event_date']} — {x['event_type']}**; {party}{amount}; {x['evidence_status']}. [{x['source_ref']}]({x['source_url']}). {x['notes']}"
        )
    pp = [x for x in rr if x["event_type"] == "municipal_permit"]
    if pp:
        s.append(
            f"- **Municipal permit history:**{len(pp)} observations from{min(x['event_date'] for x in pp)} through{max(x['event_date'] for x in pp)}. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title."
        )
    s.extend(["", "Outstanding: " + "; ".join(cover["gaps"]) + ".", ""])
s += [
    "## Coverage and learnings",
    "",
    "All exact parcel IDs in this baseline are Boston/Suffolk. Outside-county sources are assigned to other wave2 agents; this local baseline makes no claim to have searched Plymouth, Norfolk or Middlesex. Historical sold/renamed assets and condominium units remain included. No acquired property is inferred from a mortgagee candidate.",
    "",
    "No new repository papercut was encountered beyond known first-wave source/data limitations. The source-owner correction to17988/312 was received before event generation; a validation assertion prevents reuse of the old$1,725,000 quote. Every event has a source URL and source quote. All32 instruments have stable registry/book/page IDs; multi-parcel repetitions share instrument_id.",
]
text = "\n".join(s) + "\n"
for aa, bb in [
    ("all147", "all 147"),
    ("200existing", "200 existing"),
    ("32registry", "32 registry"),
    ("exact25", "exact 25"),
    ("corrected1993", "corrected 1993"),
    ("is$", "is $"),
    ("earlier$", "earlier $"),
    ("two2016quitclaims", "two 2016 quitclaims"),
    ("than$", "than $"),
    ("Unresolved joins:**33", "Unresolved joins:** 33"),
    ("versus31", "versus 31"),
    ("The1992Four", "The 1992 Four"),
    ("history:**", "history:** "),
    ("observations from", "observations from "),
    ("through20", "through 20"),
    ("to17988", "to 17988"),
    ("old$", "old $"),
    ("All32", "All 32"),
]:
    text = text.replace(aa, bb)
(report_dir / "report-timeline-baseline.md").write_text(text)
print(
    json.dumps(
        {
            k: manifest[k]
            for k in [
                "event_count",
                "property_count",
                "exact_boston_pid_count",
                "unique_recorded_instruments",
                "event_types",
            ]
        },
        indent=2,
    )
)
