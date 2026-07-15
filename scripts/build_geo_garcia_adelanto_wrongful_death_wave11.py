#!/usr/bin/env python3
"""Build the lead 63730 Garcia/Adelanto public-record case package."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKDIR = Path("/tmp/osint-oep1Qb2D")
SOURCE_REL = Path(
    "investigations/geo-group/sources/"
    "2026-07-14-lead-63730-garcia-adelanto-wrongful-death-wave11"
)
REPORT_PREFIX_REL = Path(
    "investigations/geo-group/reports/"
    "2026-07-14-lead-63730-garcia-adelanto-wrongful-death-wave11"
)
SOURCE_DIR = ROOT / SOURCE_REL
REPORT_PREFIX = ROOT / REPORT_PREFIX_REL
PRIOR_SOURCE = ROOT / "investigations/geo-group/sources/2026-07-14-geo-residual-medical-cases-wave10"
PRIOR_REPORT_PREFIX = ROOT / "investigations/geo-group/reports/2026-07-14-geo-residual-medical-cases-wave10"


REPORTS = {
    "narrative": Path(str(REPORT_PREFIX) + "-case-analysis.md"),
    "matrix": Path(str(REPORT_PREFIX) + "-party-claim-disposition-matrix.csv"),
    "ledger": Path(str(REPORT_PREFIX) + "-docket-document-ledger.csv"),
    "negative": Path(str(REPORT_PREFIX) + "-negative-missing-document-log.csv"),
    "manifest": Path(str(REPORT_PREFIX) + "-source-finding-manifest.json"),
    "sha": Path(str(REPORT_PREFIX) + "-sha256.csv"),
}


SOURCE_INPUTS = {
    "courtlistener-docket-72097949-current.json": WORKDIR / "docket-current.json",
    "courtlistener-docket-entries-72097949-current-paginated.json": WORKDIR / "docket-entries-current-paginated.json",
    "courtlistener-recap-search-docket-current.json": WORKDIR / "recap-docket-current.json",
    "courtlistener-recap-search-caption-current.json": WORKDIR / "recap-caption-current.json",
    "courtlistener-opinions-caption-current.json": WORKDIR / "opinions-caption-current.json",
    "courtlistener-search-caption-current.json": WORKDIR / "search-caption-current.json",
    "courtlistener-requested-recap-documents-current.json": WORKDIR / "requested-recap-documents-current.json",
    "public-endpoint-probes.json": WORKDIR / "public-endpoint-probes.json",
    "internet-archive-recap-item-metadata.json": WORKDIR / "internet-archive-recap-item-metadata.json",
    "ice-detainee-death-report-current.pdf": WORKDIR / "ice-current-2.pdf",
    "ecf-1-attachment-1-civil-cover-sheet.pdf": PRIOR_SOURCE / "garcia-civil-cover-sheet-ecf1-attachment1.pdf",
    "ecf-30-order-to-show-cause.pdf": PRIOR_SOURCE / "garcia-order-to-show-cause-ecf30.pdf",
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_entries() -> list[dict]:
    payload = json.loads(
        (SOURCE_DIR / "courtlistener-docket-entries-72097949-current-paginated.json").read_text()
    )
    entries = [row for page in payload["pages"] for row in page["results"]]
    assert payload["count"] == len(entries) == 37
    return entries


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PREFIX.parent.mkdir(parents=True, exist_ok=True)
    for name, source in SOURCE_INPUTS.items():
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copy2(source, SOURCE_DIR / name)

    docket = json.loads((SOURCE_DIR / "courtlistener-docket-72097949-current.json").read_text())
    entries = load_entries()
    requested = json.loads(
        (SOURCE_DIR / "courtlistener-requested-recap-documents-current.json").read_text()
    )
    ia = json.loads((SOURCE_DIR / "internet-archive-recap-item-metadata.json").read_text())
    probes = json.loads((SOURCE_DIR / "public-endpoint-probes.json").read_text())

    assert docket["id"] == 72097949
    assert docket["docket_number"] == "5:25-cv-03614"
    assert docket["date_last_filing"] == "2026-07-08"
    assert docket["date_terminated"] is None
    assert len(requested) == 10
    assert sum(len(item["documents"]) for item in requested.values()) == 13

    ledger_rows: list[dict] = []
    requested_numbers = {1, 17, 18, 22, 27, 28, 29, 32, 33, 34}
    for entry in entries:
        docs = entry.get("recap_documents") or [{}]
        for doc in docs:
            number = entry.get("entry_number")
            description = entry.get("description") or doc.get("description") or ""
            ledger_rows.append(
                {
                    "docket_id": 72097949,
                    "docket_number": "5:25-cv-03614",
                    "docket_entry_id": entry.get("id"),
                    "entry_number": "" if number is None else number,
                    "date_filed": entry.get("date_filed") or "",
                    "entry_description": description,
                    "recap_document_id": doc.get("id") or "",
                    "attachment_number": "" if doc.get("attachment_number") is None else doc.get("attachment_number"),
                    "document_description": doc.get("description") or "",
                    "pacer_doc_id": doc.get("pacer_doc_id") or "",
                    "is_available": doc.get("is_available"),
                    "is_sealed": doc.get("is_sealed"),
                    "page_count": doc.get("page_count") or "",
                    "filepath_local": doc.get("filepath_local") or "",
                    "filepath_ia": doc.get("filepath_ia") or "",
                    "requested_scope": number in requested_numbers,
                    "delta_from_wave10": "none",
                    "evidence_boundary": (
                        "court order" if number == 30 else
                        "party filing or docket metadata; not an adjudicated fact"
                    ),
                }
            )
    assert len(ledger_rows) == 40

    matrix_rows = [
        {
            "record_type": "party",
            "item": "Gabriel Alejandro Garcia and Mariel Garcia Mora",
            "source": "ECF 1-1 civil cover sheet and docket metadata",
            "pleaded_or_recorded_role": "Plaintiffs",
            "requested_relief_or_position": "Jury demanded; civil cover sheet says money to be determined at trial",
            "disposition_or_posture": "Action remains active in public metadata",
            "certainty_boundary": "Names and docket roles are recorded; relationship to decedent is not authenticated by the missing complaint",
        },
        {
            "record_type": "party",
            "item": "The GEO Group, Inc.",
            "source": "ECF 1-1 civil cover sheet and docket metadata",
            "pleaded_or_recorded_role": "Corporate defendant; movant at ECF 17 and 22",
            "requested_relief_or_position": "Moved to dismiss complaint claims 4 and 5; exact arguments unavailable",
            "disposition_or_posture": "ECF 27-29 sequence unavailable",
            "certainty_boundary": "Named-defendant and movant status only; no liability inference",
        },
        {
            "record_type": "party",
            "item": "Wellpath LLC",
            "source": "ECF 1-1 civil cover sheet and docket metadata",
            "pleaded_or_recorded_role": "Corporate defendant; answered at ECF 24",
            "requested_relief_or_position": "Answer unavailable",
            "disposition_or_posture": "Active party in pretrial docket",
            "certainty_boundary": "Named-defendant status only; no liability inference",
        },
        {
            "record_type": "party",
            "item": "Does 1-100, inclusive",
            "source": "ECF 1-1 civil cover sheet",
            "pleaded_or_recorded_role": "Unidentified defendants",
            "requested_relief_or_position": "Unknown because complaint unavailable",
            "disposition_or_posture": "No identified Doe substitutions in public snapshot",
            "certainty_boundary": "No individual responsibility can be assessed",
        },
        {
            "record_type": "claim",
            "item": "Complaint theories listed by filer",
            "source": "ECF 1-1 civil cover sheet",
            "pleaded_or_recorded_role": "Negligence/wrongful death; negligent hiring, training and supervision; intentional infliction of emotional distress; California Government Code § 7320",
            "requested_relief_or_position": "Exact counts, pleaded facts, statutory theory, and prayer unavailable",
            "disposition_or_posture": "No claim-by-claim public merits record",
            "certainty_boundary": "Cover-sheet characterization is not the complaint and is not proof of an allegation",
        },
        {
            "record_type": "claim",
            "item": "Complaint claims 1-3",
            "source": "Docket metadata",
            "pleaded_or_recorded_role": "Existence implied by GEO motion targeting claims 4 and 5",
            "requested_relief_or_position": "Unknown",
            "disposition_or_posture": "No public disposition identified",
            "certainty_boundary": "Do not map claim numbers to cover-sheet theories without the complaint",
        },
        {
            "record_type": "claim",
            "item": "Complaint claims 4-5",
            "source": "ECF 17, 18, and 22 docket metadata",
            "pleaded_or_recorded_role": "Targets of GEO motion to dismiss; opposition and reply filed",
            "requested_relief_or_position": "Arguments unavailable",
            "disposition_or_posture": "ECF 27 labeled Dismiss; ECF 28 extension to amend; ECF 29 order, all documents unavailable",
            "certainty_boundary": "Exact ruling, prejudice, leave to amend, reasoning, and affected theories cannot be stated",
        },
        {
            "record_type": "holding",
            "item": "ECF 30 June 30 order to show cause",
            "source": "Court-authenticated order",
            "pleaded_or_recorded_role": "Procedural order concerning failure to file the Rule 26(f) report",
            "requested_relief_or_position": "Court required written cause and a Rule 26(f) report within seven days",
            "disposition_or_posture": "ECF 32-34 filed July 7; no public dismissal or sanction follows in current snapshot",
            "certainty_boundary": "Not a merits, causation, negligence, or compliance holding",
        },
        {
            "record_type": "official agency record",
            "item": "ICE detainee-death report for Gabriel Garcia Aviles",
            "source": "ICE current official PDF",
            "pleaded_or_recorded_role": "Records ICE custody, October 15 transfer to Adelanto, subsequent hospital transfer, and October 23 death",
            "requested_relief_or_position": "Not a party filing and requests no civil relief",
            "disposition_or_posture": "No civil causation or compliance determination",
            "certainty_boundary": "Custody/transfer/death chronology only; granular medical detail omitted for privacy",
        },
    ]

    missing_items = [
        ("ECF 1 main", "Complaint", "Exact allegations, count numbering, requested relief, and primary lawsuit-to-decedent bridge remain unavailable", "high"),
        ("ECF 1 attachment 2", "Exhibit", "Two-page exhibit unavailable", "high"),
        ("ECF 1 attachment 3", "Exhibit", "Two-page exhibit unavailable", "high"),
        ("ECF 17", "GEO motion to dismiss claims 4-5 and attachments", "Arguments and motion-specific supporting material unavailable", "high"),
        ("ECF 18", "Plaintiffs' opposition and attachments", "Plaintiffs' positions and supporting material unavailable", "high"),
        ("ECF 22", "GEO reply", "Reply arguments unavailable", "high"),
        ("ECF 27", "Docket item labeled Dismiss", "Exact holding, scope, prejudice, leave, and reasoning unavailable", "critical"),
        ("ECF 28", "Extension of Time to Amend", "Requested amendment deadline and basis unavailable", "high"),
        ("ECF 29", "Order", "Exact amendment-related holding unavailable", "critical"),
        ("ECF 32", "Joint Rule 26(f) report", "Claim and schedule details unavailable", "medium"),
        ("ECF 33", "Declaration", "OSC explanation unavailable", "medium"),
        ("ECF 34", "Declaration", "OSC explanation unavailable", "medium"),
        ("Post-2026-07-08 filings", "Any later docket activity", "No later filing appears in refreshed CourtListener metadata", "monitor"),
    ]
    negative_rows = [
        {
            "item": item,
            "indexed_description": description,
            "availability_result": "Not recovered; requested RECAP records are is_available=false and is_sealed=null" if item.startswith("ECF") else "No result",
            "sources_checked": "CourtListener docket/entry pagination and RECAP search; direct storage probe; Justia docket/PDF; GovInfo/CACD exact search; Internet Archive RECAP inventory",
            "interpretation": interpretation,
            "priority": priority,
            "human_action_id": 78 if priority in {"critical", "high", "medium"} else "",
            "paid_or_contact_action_taken": "none",
        }
        for item, description, interpretation, priority in missing_items
    ]

    write_csv(REPORTS["matrix"], list(matrix_rows[0]), matrix_rows)
    write_csv(REPORTS["ledger"], list(ledger_rows[0]), ledger_rows)
    write_csv(REPORTS["negative"], list(negative_rows[0]), negative_rows)

    db = sqlite3.connect(ROOT / "investigation.db")
    db.row_factory = sqlite3.Row
    finding = dict(db.execute(
        "SELECT id, target_name, summary, claim_type, confidence, verification_status, thread_id, profile_id FROM findings WHERE id=12993"
    ).fetchone())
    lead = dict(db.execute(
        "SELECT id, title, status, stop_reason, thread_id, profile_id FROM leads WHERE id=63730"
    ).fetchone())
    action = dict(db.execute(
        "SELECT id, title, action_type, priority, status, related_lead_id, notes FROM human_actions WHERE id=78"
    ).fetchone())
    entity = dict(db.execute(
        "SELECT id, name, entity_type, source FROM entities WHERE id=5144"
    ).fetchone())
    connection = dict(db.execute(
        "SELECT id, person_a, person_b, relationship_type, description, strength, finding_id, verification_status, profile_id FROM connections WHERE id=6414"
    ).fetchone())
    connection["evidence"] = [
        dict(row) for row in db.execute(
            "SELECT evidence_type, evidence_ref, source_quote, source_page FROM connection_evidence WHERE connection_id=6414"
        ).fetchall()
    ]
    quick = db.execute("PRAGMA quick_check").fetchone()[0]
    fk_count = len(db.execute("PRAGMA foreign_key_check").fetchall())
    db.close()

    assert finding["verification_status"] == "verified"
    assert lead["status"] == "blocked" and lead["stop_reason"]
    assert action["related_lead_id"] is None
    assert quick == "ok" and fk_count == 64

    ia_pdfs = sorted(
        f["name"] for f in ia.get("files", []) if f.get("name", "").endswith(".pdf")
    )
    assert ia_pdfs == [
        "gov.uscourts.cacd.1001144.1.1.pdf",
        "gov.uscourts.cacd.1001144.30.0.pdf",
    ]

    ice_current = SOURCE_DIR / "ice-detainee-death-report-current.pdf"
    ice_prior = PRIOR_SOURCE / "garcia-ice-detainee-death-report.pdf"
    assert sha256(ice_current) == sha256(ice_prior) == "2e32126f054b8fd6acffb6f723ed5256a627a563f372bd69502782f9615fb90d"

    report = f"""# Garcia v. GEO / Wellpath — bounded public-record case analysis

**Case:** *Gabriel Alejandro Garcia et al. v. The GEO Group, Inc. et al.*, C.D. Cal. No. 5:25-cv-03614-KK-DTB, CourtListener docket 72097949  
**Cutoff:** 2026-07-14  
**Lead / thread:** #63730 / 113  
**Disposition:** blocked at a documented public-source stop; human action #78

## Result

The refreshed CourtListener record contains the same 37 docket entries as the wave-10 capture. The docket remains un-terminated, its last filing remains July 8, 2026, and no post-July-8 filing or availability change was found. There is therefore no new docket/posture fact warranting a duplicate finding. Verified finding #12993 remains the controlling database record.

The full requested-document audit recovered no new substantive filing. Free public copies remain limited to ECF 1-1, the three-page civil cover sheet, and ECF 30, the two-page June 30 procedural order to show cause. CourtListener reports ECF 1 main and attachments 2-3; ECF 17-18 and 22; ECF 27-29; and ECF 32-34 as `is_available=false` and `is_sealed=null`. Null sealing metadata is not evidence that a document is sealed.

Direct probes of the expected CourtListener storage paths and Justia PDF paths returned 404 for the requested missing documents. Justia's docket listing stops at February 27. Exact CACD/GovInfo searches found no public package. The Internet Archive RECAP item for this docket contains only ECF 1-1 and ECF 30. No PACER purchase, RECAP request, clerk contact, or outside contact was made.

## Parties and pleaded material

The public cover sheet names Gabriel Alejandro Garcia and Mariel Garcia Mora as plaintiffs; The GEO Group, Inc., Wellpath LLC, and Does 1-100 as defendants. It characterizes the action as involving negligence/wrongful death, negligent hiring/training/supervision, intentional infliction of emotional distress, and California Government Code § 7320; it records a jury demand and money to be determined at trial. These are filer characterizations, not adjudicated facts, and the cover sheet neither replaces nor supplements the missing complaint.

The docket says GEO moved to dismiss the fourth and fifth complaint claims, plaintiffs opposed, and GEO replied. The filings are unavailable, so the claim-number-to-theory mapping, parties' arguments, requested disposition, and cited evidence cannot be stated. ECF 27 is indexed only as `Dismiss`, ECF 28 as `Extension of Time to Amend`, and ECF 29 as `Order`. Their texts are unavailable, so the scope of any dismissal, prejudice, leave to amend, deadline, governing rule, and reasoning remain unknown.

Wellpath answered at ECF 24, but the answer is unavailable. The Rule 26 report and declarations at ECF 32-34 establish continued filing activity after the June 30 warning; they do not expose the claims or the parties' explanation. The current public record establishes no judgment, settlement, merits causation finding, negligence holding, compliance determination, or individual Doe identification.

## Court holding recovered

ECF 30 holds only that the parties had not timely filed the joint Rule 26(f) report required by the June 4 scheduling order. The court ordered a written response and report within seven days and warned that failure could result in dismissal without prejudice or other sanctions. The July 7 filings show a response sequence; the refreshed docket contains no later public dismissal or sanction. The order does not decide civil liability or the adequacy of detention medical care.

## ICE record and privacy boundary

The current official ICE PDF is byte-identical to the wave-10 archived report. The prior URL now returns 404; the live official URL is `https://www.ice.gov/doclib/foia/reports/dderGabrielGarciaAviles.pdf`. The report records ICE custody, transfer to Adelanto on October 15, 2025, later hospital transfer, and death on October 23, 2025. It does not determine civil causation, negligence, GEO or Wellpath liability, or facility compliance. This package intentionally omits granular medical information, date of birth, arrest detail, and other unnecessary personal data.

Because the complaint is missing, the court record still does not independently authenticate the relationship between the named plaintiffs and the individual in the ICE report. The official ICE record and the court docket are preserved as separate provenance chains.

## Entity and database handling

Wellpath LLC was absent from the canonical entity table and was registered once as entity #5144 using CourtListener docket 72097949. Verified connection #6414 records only the docket's exact statement that GEO and Wellpath were both served as defendants; it expressly makes no business-relationship or liability inference. No private family member or medical-care individual was registered.

No new finding was created. Finding #12993 remains verified (`paraphrase`, high confidence) and is not duplicated. Lead #63730 is blocked with an explicit stop reason. Human action #78 covers only authorized PACER retrieval or a later free-RECAP/court-hosted copy of the exact missing ECFs. Its `related_lead_id` is intentionally NULL because that live column points to the legacy `leads_old_backup` table; linkage to #63730 is preserved in the action title and notes so the foreign-key baseline remains 64. Papercut #1048 records that schema defect for repair.

## Public-source stop

The unresolved questions are the complaint's exact factual allegations and counts, the parties' motion arguments, the court's June dismissal/amendment reasoning, and the current schedule details. Those questions cannot be answered from the publicly retrieved record without speculating. Human action #78 is the bounded next step; no paid retrieval is authorized by this package.

## QA

- CourtListener entries: 37 over two API pages; docket-document ledger: 40 RECAP-document rows.
- Requested RECAP records audited: 13 across ten docket entries.
- Docket delta from wave 10: zero.
- Current and prior ICE PDF SHA-256 match: `{sha256(ice_current)}`.
- Database `PRAGMA quick_check`: `{quick}`.
- Foreign-key violations: `{fk_count}`, unchanged baseline.
- No new finding, lead, or hypothesis; no `auto_leads.py` run.
"""
    REPORTS["narrative"].write_text(report, encoding="utf-8")

    source_records = []
    for path in sorted(SOURCE_DIR.iterdir()):
        source_records.append(
            {
                "path": rel(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )

    manifest = {
        "manifest_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": "geo-group",
        "thread_id": 113,
        "lead_id": 63730,
        "case": {
            "caption": "Gabriel Alejandro Garcia et al. v. The GEO Group, Inc. et al.",
            "court": "C.D. California",
            "docket_number": "5:25-cv-03614",
            "courtlistener_docket_id": 72097949,
            "last_public_filing": docket["date_last_filing"],
            "date_terminated": docket["date_terminated"],
            "docket_delta_from_wave10": 0,
        },
        "source_bundle_root": SOURCE_REL.as_posix(),
        "sources": source_records,
        "canonical_urls": {
            "courtlistener_docket": "https://www.courtlistener.com/docket/72097949/gabriel-alejandro-garcia-v-the-geo-group-inc/",
            "courtlistener_entries_api": "https://www.courtlistener.com/api/rest/v4/docket-entries/?docket=72097949",
            "internet_archive_recap_item": "https://archive.org/details/gov.uscourts.cacd.1001144",
            "ice_current": "https://www.ice.gov/doclib/foia/reports/dderGabrielGarciaAviles.pdf",
            "ice_old_404": "https://www.ice.gov/doclib/foia/reports/detaineeDeaths/Garcia-Aviles_Gabriel.pdf",
        },
        "retrieval_summary": {
            "entries": len(entries),
            "ledger_rows": len(ledger_rows),
            "requested_recap_documents": 13,
            "new_substantive_documents": 0,
            "available_substantive_documents": ["ECF 1-1 civil cover sheet", "ECF 30 order to show cause"],
            "missing_requested_documents": [row[0] for row in missing_items if row[0].startswith("ECF")],
            "internet_archive_pdfs": ia_pdfs,
            "successful_public_pdf_probes": [
                row["url"] for row in probes if row.get("pdf_magic")
            ],
        },
        "database": {
            "controlling_finding": finding,
            "new_findings": [],
            "lead": lead,
            "human_action": action,
            "human_action_linkage_note": "related_lead_id intentionally NULL because of legacy-FK target; #63730 linkage preserved in title/notes",
            "papercut_id": 1048,
            "registered_entity": entity,
            "neutral_connection": connection,
            "quick_check": quick,
            "foreign_key_violations": fk_count,
            "expected_foreign_key_baseline": 64,
        },
        "evidence_boundaries": [
            "Complaint, opposition, reply, answer, report, and declarations are party positions or allegations, not holdings.",
            "ECF 30 is a procedural holding only.",
            "ICE report supports custody, transfer, hospital-transfer, and death chronology only.",
            "No negligence, causation, liability, compliance, or medical inference is made.",
            "Granular medical and unnecessary personal information is omitted.",
        ],
        "prior_package": {
            "finding_id": 12993,
            "report": rel(Path(str(PRIOR_REPORT_PREFIX) + "-report.md")),
            "manifest": rel(Path(str(PRIOR_REPORT_PREFIX) + "-source-finding-manifest.json")),
            "source_root": rel(PRIOR_SOURCE),
        },
    }
    REPORTS["manifest"].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    ledger_targets = sorted(SOURCE_DIR.iterdir()) + [
        REPORTS["narrative"],
        REPORTS["matrix"],
        REPORTS["ledger"],
        REPORTS["negative"],
        REPORTS["manifest"],
        ROOT / "scripts/build_geo_garcia_adelanto_wrongful_death_wave11.py",
    ]
    hash_rows = [
        {"sha256": sha256(path), "path": rel(path)} for path in ledger_targets
    ]
    write_csv(REPORTS["sha"], ["sha256", "path"], hash_rows)

    print(json.dumps({
        "source_files": len(source_records),
        "matrix_rows": len(matrix_rows),
        "ledger_rows": len(ledger_rows),
        "negative_rows": len(negative_rows),
        "hash_rows": len(hash_rows),
        "outputs": [rel(path) for path in REPORTS.values()],
    }, indent=2))


if __name__ == "__main__":
    main()
