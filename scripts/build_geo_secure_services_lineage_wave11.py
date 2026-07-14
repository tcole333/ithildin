#!/usr/bin/env python3
"""Build the durable source and report package for GEO lead 57847."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "2026-07-14-lead-57847-geo-secure-services-lineage-wave11"
SOURCE_DIR = ROOT / "investigations" / "geo-group" / "sources" / PREFIX
REPORT_DIR = ROOT / "investigations" / "geo-group" / "reports"
DB_PATH = ROOT / "investigation.db"

GSS_URL = (
    "https://search.sunbiz.org/Inquiry/CorporationSearch/"
    "SearchByNumber?searchNumber=L12000160666"
)
GSSH_URL = (
    "https://search.sunbiz.org/Inquiry/CorporationSearch/"
    "SearchByNumber?searchNumber=L22000531201"
)
PRED_URL = (
    "https://search.sunbiz.org/Inquiry/CorporationSearch/"
    "SearchByNumber?searchNumber=P12000083665"
)
GSS_2026_AR_URL = (
    "https://search.sunbiz.org/Inquiry/CorporationSearch/GetDocument?"
    "aggregateId=flal-l12000160666-e9e0a86b-50b0-45a6-ac14-e7b760b95ebd"
    "&formatType=PDF"
    "&transactionId=l12000160666-45b94f6e-16e9-4a7a-86c8-63bc01dc11e4"
)
SEC_EX21_URL = (
    "https://www.sec.gov/Archives/edgar/data/923796/"
    "000119312526071747/geo-ex21_1.htm"
)
SEC_EX22_URL = (
    "https://www.sec.gov/Archives/edgar/data/923796/"
    "000119312526071747/geo-ex22_1.htm"
)


def jsonable(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def copy_if_present(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def extract_prefixed_lines(paths: list[Path], prefixes: tuple[str, ...]) -> list[dict]:
    output: list[dict] = []
    for path in paths:
        with path.open("r", encoding="latin-1", errors="replace") as handle:
            for line_number, line in enumerate(handle, 1):
                if line.startswith(prefixes):
                    output.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "line_number": line_number,
                            "raw_line": line.rstrip("\n"),
                        }
                    )
    return output


def build_source_archive(workdir: Path, db: sqlite3.Connection) -> None:
    for subdir in ("context", "registry", "sam", "sec", "courtlistener"):
        (SOURCE_DIR / subdir).mkdir(parents=True, exist_ok=True)

    workdir_files = {
        "registry-gss-search.json": "registry/unified-registry-gss-search.json",
        "registry-gss-holdings-search.json": "registry/unified-registry-gss-holdings-search.json",
        "sam-bulk-gss.json": "sam/sam-public-extract-gss.json",
        "courtlistener-gss-corporate-disclosure-search.json": (
            "courtlistener/corporate-disclosure-search.json"
        ),
        "existing-entity-audit.txt": "context/existing-entity-audit.txt",
        "existing-findings-search-audit-fixed.txt": (
            "context/existing-findings-search-audit.txt"
        ),
        "baseline-schema.txt": "context/db-baseline-schema.txt",
    }
    for source_name, destination_name in workdir_files.items():
        copy_if_present(workdir / source_name, SOURCE_DIR / destination_name)

    prior_sec = (
        ROOT
        / "investigations"
        / "geo-group"
        / "sources"
        / "2026-07-14-lead-57846-bi-incorporated-lineage-wave11"
        / "sec"
    )
    copy_if_present(
        prior_sec / "sec-geo-fy2025-ex21.html",
        SOURCE_DIR / "sec" / "sec-geo-fy2025-ex21.html",
    )
    copy_if_present(
        prior_sec / "sec-geo-fy2025-ex22.html",
        SOURCE_DIR / "sec" / "sec-geo-fy2025-ex22.html",
    )

    sunbiz_extract = f"""Florida Division of Corporations web-visible record extracts
Retrieval date: 2026-07-14
Scope: legal identity, current status, predecessor/name history, merger boundary, roles, and addresses.
Direct archival fetches returned HTTP 403; these exact fields were transcribed from the official web-visible detail, event-history, name-history, and annual-report text. See papercut #1057.

SOURCE: {GSS_URL}
Florida Limited Liability Company
GEO SECURE SERVICES, LLC
Document Number L12000160666
FEI/EIN Number 46-1258100
Date Filed 12/26/2012
Effective Date 10/02/2012
State FL
Status ACTIVE
Last Event CORPORATE MERGER
Event Date Filed 01/23/2023
Principal Address: 4955 TECHNOLOGY WAY, BOCA RATON, FL 33431
Mailing Address: 4955 TECHNOLOGY WAY, BOCA RATON, FL 33431
Registered Agent: CORPORATE CREATIONS NETWORK, INC., 801 US HIGHWAY 1, NORTH PALM BEACH, FL 33408

EVENT HISTORY FOR L12000160666
MERGER 01/23/2023 CORPORATION WAS A MERGER RESULT. TOTAL NUMBER OF QUALIFIED CORPORATION(S) INVOLVED WAS 1
LC NAME CHANGE 08/01/2019 OLD NAME WAS : GEO CORRECTIONS AND DETENTION, LLC
MERGER 12/20/2017 CORPORATION WAS A MERGER RESULT. TOTAL NUMBER OF QUALIFIED CORPORATION(S) INVOLVED WAS 0
CONVERSION 12/26/2012 CONVERTING TO: CORPORATION WAS A CONVERSION RESULT. CONVERTING CORPORATION WAS P12000083665

SOURCE: {PRED_URL}
Florida Profit Corporation
GEO CORRECTIONS & DETENTION, INC.
Document Number P12000083665
FEI/EIN Number NONE
Date Filed 10/02/2012
State FL
Status INACTIVE
Last Event CONVERSION
Event Date Filed 12/26/2012
Principal and mailing address: ONE PARK PLACE, SUITE 700, 621 N.W. 53RD STREET, BOCA RATON, FL 33487
Registered Agent: CORPORATE CREATIONS INTERNATIONAL INC., 11380 PROSPERITY FARMS ROAD, #221E, PALM BEACH GARDENS, FL 33410

SOURCE: {GSSH_URL}
Florida Limited Liability Company
GEO GSS HOLDINGS, LLC
Document Number L22000531201
FEI/EIN Number APPLIED FOR
Date Filed 12/20/2022
Effective Date 12/20/2022
State FL
Status INACTIVE
Last Event CORPORATE MERGER
Event Date Filed 01/23/2023
Principal and mailing address: 4955 TECHNOLOGY WAY, BOCA RATON, FL 33431
Registered Agent: CORPORATE CREATIONS NETWORK INC., 801 US HIGHWAY 1, NORTH PALM BEACH, FL 33408
EVENT HISTORY: MERGER 01/23/2023 CORPORATION WAS PART OF A MERGER. QUALIFIED CORPORATION WAS L12000160666
Authorized persons:
GEORGE C. ZOLEY — Manager, Executive Chairman
BRIAN R. EVANS — Manager, VP, Finance and CFO
JOE NEGRON — MGR, VP, Secretary
Jose Gordo — CEO
Wayne Calabrese — President
Ron Brack — VP, Accounting
Beth A. Crews — VP, Asst. Secretary
Marcel Maier — VP, Tax
Shayn March — VP, Treasurer

SOURCE: {GSS_2026_AR_URL}
Filed Mar 24, 2026
2026 FLORIDA LIMITED LIABILITY COMPANY ANNUAL REPORT
Entity Name: GEO SECURE SERVICES, LLC
DOCUMENT# L12000160666
FEI Number: 46-1258100
Current Principal Place of Business and Current Mailing Address: 4955 TECHNOLOGY WAY, BOCA RATON, FL 33431
Current Registered Agent: CORPORATE CREATIONS NETWORK, INC., 801 US HIGHWAY 1, NORTH PALM BEACH, FL 33408
Managers: ZOLEY, GEORGE C; CALABRESE, WAYNE; MARCH, SHAYN; DONAHUE, J. DAVID; SCHIPMA, SCOTT
Electronic signature: SCOTT SCHIPMA, MANAGER, 03/24/2026
"""
    (SOURCE_DIR / "registry" / "sunbiz-official-web-extracts.txt").write_text(
        sunbiz_extract, encoding="utf-8"
    )

    raw_paths = [
        ROOT / "datasets" / "fl_sunbiz" / "quarterly" / "corps" / "corprindata6.txt",
        ROOT / "datasets" / "fl_sunbiz" / "quarterly" / "events" / "corevt.txt",
        ROOT / "datasets" / "fl_sunbiz" / "quarterly" / "cordata" / "cordata1.txt",
    ]
    raw_extract = extract_prefixed_lines(
        raw_paths, ("L12000160666", "L22000531201", "P12000083665")
    )
    write_json(SOURCE_DIR / "registry" / "sunbiz-local-bulk-extract.json", raw_extract)

    findings = jsonable(
        db.execute(
            """
            SELECT * FROM findings
            WHERE id IN (12382,12484,12662,12665,12824,13062,13063,13064)
            ORDER BY id
            """
        ).fetchall()
    )
    evidence = jsonable(
        db.execute(
            """
            SELECT * FROM finding_evidence
            WHERE finding_id IN (12382,12484,12662,12665,12824,13062,13063,13064)
            ORDER BY finding_id,evidence_ref
            """
        ).fetchall()
    )
    write_json(
        SOURCE_DIR / "context" / "finding-controls-and-new-findings.json",
        {"findings": findings, "evidence": evidence},
    )

    entities = jsonable(
        db.execute("SELECT * FROM entities WHERE id IN (1290,4811,5146,5165) ORDER BY id").fetchall()
    )
    roles = jsonable(
        db.execute(
            "SELECT * FROM entity_roles WHERE entity_id IN (4811,5146,5165) ORDER BY entity_id,id"
        ).fetchall()
    )
    addresses = jsonable(
        db.execute(
            "SELECT * FROM entity_addresses WHERE entity_id IN (4811,5146,5165) ORDER BY entity_id,id"
        ).fetchall()
    )
    relations = jsonable(
        db.execute(
            """
            SELECT r.*,a.name entity_a,b.name entity_b
            FROM entity_relations r
            JOIN entities a ON a.id=r.entity_a_id
            JOIN entities b ON b.id=r.entity_b_id
            WHERE r.entity_a_id IN (4811,5146,5165)
               OR r.entity_b_id IN (4811,5146,5165)
            ORDER BY r.id
            """
        ).fetchall()
    )
    aliases = jsonable(
        db.execute("SELECT * FROM name_aliases WHERE entity_id=4811 ORDER BY id").fetchall()
    )
    write_json(
        SOURCE_DIR / "context" / "entity-db-snapshot.json",
        {
            "entities": entities,
            "roles": roles,
            "addresses": addresses,
            "relations": relations,
            "aliases": aliases,
        },
    )

    current_sam_control = db.execute(
        "SELECT * FROM findings WHERE id=12665"
    ).fetchone()
    current_sam_evidence = jsonable(
        db.execute("SELECT * FROM finding_evidence WHERE finding_id=12665").fetchall()
    )
    write_json(
        SOURCE_DIR / "sam" / "sam-live-current-control.json",
        {
            "provenance_note": (
                "Existing verified finding/evidence control for the July 13, 2026 live SAM response; "
                "this is not a second live API call or a raw-response substitute."
            ),
            "finding": dict(current_sam_control),
            "evidence": current_sam_evidence,
        },
    )


def build_matrices(db: sqlite3.Connection) -> None:
    legal_rows = [
        {
            "date": "2012-10-02",
            "entity": "GEO Corrections & Detention, Inc.",
            "db_entity_id": 5165,
            "jurisdiction": "Florida",
            "document_or_identifier": "P12000083665",
            "record_type": "formation",
            "status_or_event": "Florida profit corporation filed; later inactive by conversion",
            "legal_effect": "Distinct predecessor corporation",
            "source": PRED_URL,
        },
        {
            "date": "2012-12-26",
            "entity": "GEO Secure Services, LLC (then GEO Corrections and Detention, LLC)",
            "db_entity_id": 4811,
            "jurisdiction": "Florida",
            "document_or_identifier": "L12000160666",
            "record_type": "conversion",
            "status_or_event": "Conversion result from P12000083665",
            "legal_effect": "LLC succeeds converted corporation; filing date 2012-12-26, effective 2012-10-02",
            "source": GSS_URL,
        },
        {
            "date": "2019-08-01",
            "entity": "GEO Secure Services, LLC",
            "db_entity_id": 4811,
            "jurisdiction": "Florida",
            "document_or_identifier": "L12000160666",
            "record_type": "former legal name",
            "status_or_event": "LC name change",
            "legal_effect": "Old name was GEO CORRECTIONS AND DETENTION, LLC; same LLC, not a second entity",
            "source": GSS_URL,
        },
        {
            "date": "2022-12-20",
            "entity": "GEO GSS HOLDINGS, LLC",
            "db_entity_id": 5146,
            "jurisdiction": "Florida",
            "document_or_identifier": "L22000531201",
            "record_type": "formation",
            "status_or_event": "Florida LLC filed/effective",
            "legal_effect": "Distinct short-lived legal entity",
            "source": GSSH_URL,
        },
        {
            "date": "2023-01-23",
            "entity": "GEO GSS HOLDINGS, LLC -> GEO Secure Services, LLC",
            "db_entity_id": "5146 -> 4811",
            "jurisdiction": "Florida",
            "document_or_identifier": "L22000531201 -> L12000160666",
            "record_type": "single merger event chain",
            "status_or_event": "GSS Holdings was part of merger; L12000160666 was qualified corporation and merger result",
            "legal_effect": "GSS Holdings merged into surviving GEO Secure Services; not evidence of parentage",
            "source": GSSH_URL,
        },
        {
            "date": "2025-12-31",
            "entity": "GEO Secure Services, LLC",
            "db_entity_id": 4811,
            "jurisdiction": "Florida",
            "document_or_identifier": "SEC Exhibit 21.1",
            "record_type": "subsidiary disclosure",
            "status_or_event": "Listed GEO subsidiary",
            "legal_effect": "GEO holds directly or indirectly 100%; directness/intermediate owner unresolved",
            "source": SEC_EX21_URL,
        },
        {
            "date": "2026-03-24",
            "entity": "GEO Secure Services, LLC",
            "db_entity_id": 4811,
            "jurisdiction": "Florida",
            "document_or_identifier": "2026 annual report",
            "record_type": "current registry status",
            "status_or_event": "Active; five managers; principal/mailing and agent addresses",
            "legal_effect": "Current Florida public-record snapshot",
            "source": GSS_2026_AR_URL,
        },
        {
            "date": "2026-06-01",
            "entity": "GEO Secure Services, LLC",
            "db_entity_id": 4811,
            "jurisdiction": "SAM / United States",
            "document_or_identifier": "UEI JLG3JBCL4CC7 / CAGE 7G0P0",
            "record_type": "federal entity registration update",
            "status_or_event": "Active through 2027-05-20; DBA GEO SECURE SERVICES LLC",
            "legal_effect": "Federal registration identity only; not ownership evidence",
            "source": "SAM:UEI:JLG3JBCL4CC7 (verified finding #12665)",
        },
    ]
    write_csv(
        REPORT_DIR / f"{PREFIX}-legal-lineage-status-matrix.csv",
        list(legal_rows[0].keys()),
        legal_rows,
    )

    role_rows = jsonable(
        db.execute(
            """
            SELECT r.id db_record_id,e.id db_entity_id,e.name entity,
                   'role' record_kind,r.person_name subject,r.role capacity,
                   '' address,r.date_start,r.date_end,r.source
            FROM entity_roles r JOIN entities e ON e.id=r.entity_id
            WHERE r.entity_id IN (4811,5146)
            ORDER BY e.id,r.id
            """
        ).fetchall()
    )
    address_rows = jsonable(
        db.execute(
            """
            SELECT a.id db_record_id,e.id db_entity_id,e.name entity,
                   'address' record_kind,'' subject,a.address_type capacity,
                   a.address,'' date_start,'' date_end,a.source
            FROM entity_addresses a JOIN entities e ON e.id=a.entity_id
            WHERE a.entity_id IN (4811,5146)
            ORDER BY e.id,a.id
            """
        ).fetchall()
    )
    combined = role_rows + address_rows
    write_csv(
        REPORT_DIR / f"{PREFIX}-officer-role-address-matrix.csv",
        [
            "db_record_id",
            "db_entity_id",
            "entity",
            "record_kind",
            "subject",
            "capacity",
            "address",
            "date_start",
            "date_end",
            "source",
        ],
        combined,
    )

    parent_rows = [
        {
            "entity_a": "GEO Corrections & Detention, Inc. (#5165)",
            "relationship": "converted_into",
            "entity_b": "GEO Secure Services, LLC (#4811)",
            "date_or_as_of": "2012-12-26",
            "evidence_boundary": "Exact Florida conversion event from P12000083665 to L12000160666",
            "source": GSS_URL,
            "db_relation_id": 860,
        },
        {
            "entity_a": "GEO GSS HOLDINGS, LLC (#5146)",
            "relationship": "merged_into",
            "entity_b": "GEO Secure Services, LLC (#4811)",
            "date_or_as_of": "2023-01-23",
            "evidence_boundary": "Exact single Florida merger event chain; does not establish parentage",
            "source": GSSH_URL,
            "db_relation_id": 861,
        },
        {
            "entity_a": "GEO Secure Services, LLC (#4811)",
            "relationship": "subsidiary_of",
            "entity_b": "The GEO Group Inc. (#1290)",
            "date_or_as_of": "2025-12-31",
            "evidence_boundary": "SEC says direct or indirect 100%; exact intermediate owner is not disclosed",
            "source": SEC_EX21_URL,
            "db_relation_id": 817,
        },
        {
            "entity_a": "GEO Secure Services, LLC (#4811)",
            "relationship": "subsidiary guarantor",
            "entity_b": "The GEO Group, Inc. senior notes",
            "date_or_as_of": "FY2025 filing",
            "evidence_boundary": "Exhibit 22 list membership; not a parent-chain diagram",
            "source": SEC_EX22_URL,
            "db_relation_id": "",
        },
        {
            "entity_a": "GEO Secure Services, LLC",
            "relationship": "court disclosure identifies corporate parent",
            "entity_b": "The GEO Group, Inc.",
            "date_or_as_of": "2024-02-02",
            "evidence_boundary": "CourtListener docket-entry metadata only; RECAP document unavailable; SEC controls",
            "source": "https://www.courtlistener.com/docket/68221441/5/",
            "db_relation_id": 817,
        },
    ]
    write_csv(
        REPORT_DIR / f"{PREFIX}-parent-affiliate-matrix.csv",
        list(parent_rows[0].keys()),
        parent_rows,
    )


def build_narratives() -> None:
    report = f"""# GEO Secure Services legal-identity and lineage trace

Lead: #57847  
Profile: `geo-group`  
Scope: corporate identity, statutory lineage, status, names, officers/managers, addresses, GEO parent disclosure, merger boundary, and federal registration identity. Award, wage-case, contract-performance, and facility analysis were excluded.

## Bottom line

**GEO Secure Services, LLC is one active Florida LLC, document L12000160666.** Florida lists a December 26, 2012 filing date, an October 2, 2012 effective date, FEI `46-1258100`, and active status. The entity began as the conversion result of the distinct Florida corporation **GEO Corrections & Detention, Inc.**, P12000083665. The LLC later used the legal name **GEO Corrections and Detention, LLC** before changing its name to GEO Secure Services on August 1, 2019. That former legal name and SAM's punctuation-only DBA `GEO SECURE SERVICES LLC` are aliases of canonical entity #4811, not separate companies.

Florida also resolves the otherwise ambiguous **GEO GSS Holdings, LLC**. L22000531201 was formed on December 20, 2022. Its event history says it was part of a January 23, 2023 merger whose qualified corporation was L12000160666; the GEO Secure Services event record says L12000160666 was the merger result. The two registry rows are one reciprocal event chain. The evidence supports relation #861, `#5146 --merged_into--> #4811`. It does **not** support treating GSS Holdings as a parent, subsidiary, or intermediate owner.

## Statutory identity and name history

Florida's event history provides the exact legal chain:

1. P12000083665, GEO Corrections & Detention, Inc., was filed as a Florida profit corporation on October 2, 2012.
2. On December 26, 2012, P12000083665 converted into Florida LLC L12000160666. The LLC's filing date is December 26 and its effective date is October 2.
3. The LLC's old name was GEO CORRECTIONS AND DETENTION, LLC. A Florida LLC name-change event filed August 1, 2019 produced the current legal name.
4. On January 23, 2023, the short-lived GSS Holdings entity merged into L12000160666. GEO Secure Services survived and remains active.

These events are recorded as predecessor entity #5165, conversion relation #860, former-name alias #228, merger relation #861, and finding #13062-#13063. Compound auto-entities #4870 and #4977 remain finding-cluster nodes; they were not merged into or substituted for the legal entity.

## Current status, roles, and addresses

The March 24, 2026 Florida annual report lists five managers for GEO Secure Services: George C. Zoley, J. David Donahue, Wayne Calabrese, Scott Schipma, and Shayn March. Sunbiz lists `4955 Technology Way, Boca Raton, FL 33431` as the entity's principal and mailing address and Corporate Creations Network, Inc., `801 US Highway 1, North Palm Beach, FL 33408`, as registered agent. Finding #13064 and roles #2626-#2630 preserve that current snapshot without inventing appointment dates.

The GSS Holdings detail record lists nine merger-era roles. Role #2587 was corrected in place from a truncated Florida title code to `Manager, Executive Chairman`; roles #2631-#2638 add the remaining exact titles. The entity's principal, mailing, and agent addresses are stored separately. Shared managers and addresses corroborate group context but are not the legal basis for the merger relation.

## Parent, guarantor, and ownership boundary

GEO's fiscal-2025 Exhibit 21 lists `GEO Secure Services, LLC (FL)` and states that GEO holds directly or indirectly 100% of the listed subsidiaries unless otherwise noted. Existing verified finding #12382 and preserved relation #817 already record that boundary. The exhibit does not state whether GEO's ownership of this LLC is direct and does not identify an intermediate owner.

Exhibit 22 separately lists GEO Secure Services as a subsidiary guarantor for GEO's outstanding senior notes. A bounded CourtListener RECAP search also returned a 2024 docket-entry description identifying The GEO Group, Inc. as GEO Secure Services' corporate parent. The underlying RECAP document was unavailable, so the SEC filing remains the controlling ownership source. No additional ownership edge was created.

## Federal registration identity

The March 2026 SAM public extract identifies GEO Secure Services as UEI `JLG3JBCL4CC7`, CAGE `7G0P0`, state of incorporation Florida, entity start date October 2, 2012, and DBA `GEO SECURE SERVICES LLC`. Existing verified finding #12665 records the July 13, 2026 live SAM update: active registration through May 20, 2027, last updated and activated June 1, 2026. This lead reused that verified live control rather than consuming another limited SAM call.

SAM is an identity/status source, not evidence of parentage. The no-comma DBA is alias #229, marked by `created_by=lead57847:sam_dba` while retaining the schema's `entity_variant` alias type.

## Database actions

- Enriched canonical GEO Secure Services entity #4811 with FEI, formation date, official address, status, and Sunbiz lineage provenance.
- Created distinct predecessor corporation #5165; created conversion relation #860 to #4811.
- Enriched GEO GSS Holdings #5146 with formation date and exact merger boundary; created merger relation #861 to #4811.
- Added aliases #228 (former legal name) and #229 (SAM DBA), with explicit `created_by` provenance.
- Corrected role #2587 in place and added roles #2626-#2638.
- Added address records #1076-#1081 while preserving existing SAM physical-address row #1065.
- Added and verified findings #13062-#13064 in global thread 111.
- Preserved relation #817 and all compound auto-entities; no merge or deletion was performed.

## Limits

No reviewed filing reveals whether GEO's 100% interest is direct or routed through an intermediate owner. No Delaware certificate or foreign-qualification record was recovered; Florida's own record establishes domestic Florida formation. OpenCorporates could not be used because the configured token was invalid, and no inference was drawn from the failed secondary lead check. The precise party to the 2017 zero-qualified-corporation Florida merger was not resolved because it does not change the supported 2012 conversion, 2019 name change, or 2023 GSS Holdings bridge.

See the legal-lineage/status matrix, officer-role/address matrix, parent/affiliate matrix, negative log, source/DB manifest, and SHA-256 ledger for the full audit trail.
"""
    (REPORT_DIR / f"{PREFIX}-report.md").write_text(report, encoding="utf-8")

    negatives = """# GEO Secure Services lineage negative and ambiguity log

- **Direct versus indirect ownership unresolved.** Fiscal-2025 Exhibit 21 applies a blanket direct-or-indirect 100% statement. It does not identify an intermediate owner for GEO Secure Services.
- **GSS Holdings is not treated as a parent.** Florida supplies an exact merger bridge: L22000531201 was part of a merger whose qualified corporation was L12000160666. Shared name, officers, and address are not the basis of the relation.
- **Reciprocal event rows are one chain.** The disappearing-party and merger-result entries describe the same January 23, 2023 event; they were not counted as two mergers.
- **No Delaware formation claim.** Florida identifies GEO Secure Services as a domestic Florida LLC. No Delaware certificate or separate Delaware legal entity was recovered. Search-engine absence is not a registry-status conclusion.
- **OpenCorporates not used.** `account-status` rejected the configured token before any target query. Papercut #1063 records the environment problem. No secondary result was promoted.
- **Unified registry coverage gap.** The exact unified search returned zero for GEO Secure Services even though local Sunbiz officer and event rows exist. Papercut #1054 records the missing aggregate entity row. Official Florida web records control.
- **Direct Sunbiz archival fetch blocked.** Curl received HTTP 403 from the detail and filing endpoints; papercut #1057 records the gap. The archive includes exact official web-visible transcriptions and local official bulk rows, with stable official URLs.
- **2017 merger party unresolved.** The local/official event label says L12000160666 was a merger result with zero qualified corporations. The underlying filing was not necessary to the scoped 2012 conversion, 2019 name change, or 2023 GSS Holdings bridge.
- **Court metadata is corroboration only.** The bounded RECAP search returned docket descriptions identifying The GEO Group as corporate parent, but the relevant documents were unavailable. SEC Exhibit 21 remains the ownership control.
- **SAM is not parent evidence.** SAM resolves legal name, DBA, UEI, CAGE, addresses, incorporation state, start date, and current registration window only.
- **Current SAM raw response not repeated.** Existing verified finding #12665 supplies the July 2026 live status quote. This lead archived that finding/evidence control and did not consume another live API call.
- **Compound auto-entities preserved.** #4870 and #4977 are finding-cluster nodes, not legal duplicates of #4811. No merge or deletion was attempted.
- **No award or wage analysis.** Findings #12484 and #12824 were controls only. Contract, facility, payment, and employment merits were excluded.
- **Source-quote shell trap repaired.** One zsh variable-colon expansion dropped a quote from finding #13064; papercut #1062 records the trap. The evidence row was repaired before verification.
"""
    (REPORT_DIR / f"{PREFIX}-negative-log.md").write_text(negatives, encoding="utf-8")


def build_manifest(db: sqlite3.Connection) -> None:
    lead = dict(db.execute("SELECT * FROM leads WHERE id=57847").fetchone())
    counts = {
        table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in (
            "entities",
            "entity_roles",
            "entity_addresses",
            "entity_relations",
            "name_aliases",
            "findings",
            "search_log",
        )
    }
    manifest = {
        "profile": "geo-group",
        "lead_id": 57847,
        "lead_status": lead["status"],
        "agent_run_id": "lead-57847-wave11",
        "scope": (
            "GEO Secure Services legal identity, formation/conversion/name history, current status, "
            "roles/addresses, GEO parent disclosure, GSS Holdings merger boundary, and SAM identity."
        ),
        "excluded": [
            "award and contract analysis",
            "wage-case analysis",
            "facility operations",
            "PACER purchase or paid registry retrieval",
        ],
        "primary_sources": [
            {"source": "Florida Division of Corporations", "url": GSS_URL},
            {"source": "Florida Division of Corporations", "url": GSSH_URL},
            {"source": "Florida Division of Corporations", "url": PRED_URL},
            {"source": "Florida 2026 annual report", "url": GSS_2026_AR_URL},
            {"source": "SEC Exhibit 21.1", "url": SEC_EX21_URL},
            {"source": "SEC Exhibit 22.1", "url": SEC_EX22_URL},
            {
                "source": "SAM March 2026 public extract",
                "path": f"investigations/geo-group/sources/{PREFIX}/sam/sam-public-extract-gss.json",
            },
            {
                "source": "Existing verified live SAM control",
                "finding_id": 12665,
                "path": f"investigations/geo-group/sources/{PREFIX}/sam/sam-live-current-control.json",
            },
        ],
        "corroborating_sources": [
            {
                "source": "CourtListener RECAP search metadata",
                "path": f"investigations/geo-group/sources/{PREFIX}/courtlistener/corporate-disclosure-search.json",
                "boundary": "Document descriptions only; relevant underlying documents unavailable.",
            }
        ],
        "database_actions": {
            "entities": [4811, 5146, 5165],
            "aliases": [228, 229],
            "roles": [2587] + list(range(2626, 2639)),
            "addresses": list(range(1076, 1082)),
            "relations": [860, 861],
            "preserved_relation": 817,
            "findings": [13062, 13063, 13064],
            "existing_controls": [12382, 12484, 12662, 12665, 12824],
            "papercuts": [1054, 1057, 1062, 1063],
        },
        "database_counts_at_build": counts,
        "unresolved": [
            "whether GEO's 100% ownership is direct or indirect",
            "any intermediate owner",
            "the precise party/substance of the 2017 zero-qualified-corporation merger event",
            "any unobserved foreign qualification outside Florida",
        ],
        "artifacts": [
            f"investigations/geo-group/reports/{PREFIX}-report.md",
            f"investigations/geo-group/reports/{PREFIX}-legal-lineage-status-matrix.csv",
            f"investigations/geo-group/reports/{PREFIX}-officer-role-address-matrix.csv",
            f"investigations/geo-group/reports/{PREFIX}-parent-affiliate-matrix.csv",
            f"investigations/geo-group/reports/{PREFIX}-negative-log.md",
            f"investigations/geo-group/reports/{PREFIX}-source-db-manifest.json",
            f"investigations/geo-group/reports/{PREFIX}-sha256.txt",
        ],
        "source_archive": f"investigations/geo-group/sources/{PREFIX}/",
    }
    write_json(REPORT_DIR / f"{PREFIX}-source-db-manifest.json", manifest)


def build_hash_ledger() -> None:
    ledger_path = REPORT_DIR / f"{PREFIX}-sha256.txt"
    report_paths = sorted(
        path
        for path in REPORT_DIR.glob(f"{PREFIX}-*")
        if path != ledger_path and path.is_file()
    )
    source_paths = sorted(path for path in SOURCE_DIR.rglob("*") if path.is_file())
    lines = []
    for path in report_paths + source_paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT)}")
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    workdir = args.workdir.resolve()
    if not workdir.is_dir():
        raise SystemExit(f"Workdir does not exist: {workdir}")

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        build_source_archive(workdir, db)
        build_matrices(db)
        build_narratives()
        build_manifest(db)
    finally:
        db.close()
    build_hash_ledger()


if __name__ == "__main__":
    main()
