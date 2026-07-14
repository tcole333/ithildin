# Lead #58689: ISAP V and skip-tracing privacy-governance chronology

**Research date:** 2026-07-13  
**Profile / thread:** `geo-group` / 109, Electronic Monitoring & ISAP  
**Question:** Did the privacy-review and authorization record precede operational use of (1) ISAP V's supervisory biometric app with continuous-location storage and on-demand requests and (2) `26-SOL-DCR-01` commercial-data / physical-observation skip tracing?  
**Scope:** public Layer-1 government and procurement records. Missing public records are not treated as proof of nonexistence, noncompliance, or deployment.

The accompanying source matrix is [isap-v-skip-privacy-source-matrix-2026-07-13.csv](isap-v-skip-privacy-source-matrix-2026-07-13.csv).

## Result

The public record materially supports the ordinary-approval hypothesis at the **SORN and contract-control layers**, but it does not close the timing test at the **project-decision, security-authorization, or production-use layers**.

- A modified CARIER System of Records Notice was published July 5, 2024 and effective August 5, 2024—before either 2025 procurement. It expressly covers contractor-owned systems supporting ATD, an ATD purpose of geolocation tracking and biometric verification, and ATD-derived GPS/geotag records. Finding #12494.
- The same SORN covers non-detained and ATD populations, fugitive non-citizens, known or possible addresses, public and commercial sources, and disclosure to contractors when necessary for a DHS function. That is meaningful pre-procurement SORN compatibility evidence for the skip-tracing data flow, but it does not name `26-SOL-DCR-01`, physical observation, a vendor architecture, or a project-specific review. Finding #12495.
- ISAP V Attachment 13 requires support for any required PTA, PIA, SORN, or other privacy documentation. Both solicitations prohibit CUI processing in a federal information system—including a contractor system operated on the agency's behalf—until an ATO is granted. These are prospective gates, not the resulting approval records. Finding #12496.
- Exact live queries of the DHS public PIA index found only the 2023 ATD PIA for “Alternatives to Detention” and `DHS/ICE/PIA-062`; the index returned no result for “SmartLINK” or “skip tracing.” “Commercial data” returned only the HSI RAVEn PIA. This is a bounded public-index result, not evidence that no internal PTA, PIA-update decision, ATO, or risk acceptance exists. Finding #12497.
- Public award start dates do not establish production use. ISAP V specified a four-month transition and a transition plan due 14 days after award. The skip-tracing Q&A said work was expected to begin immediately, but the public record supplies neither a first case-transfer/delivery date nor vendor-specific authorization architecture.

**H0 — required privacy/security review preceded production:** materially supported, but not proven. The 2024 SORN and the two contractual authorization gates predate the public procurement/start proxies. The dated PTA/PIA determination, operative ATO, implementation-level records decision, and actual production date are not public.

**H1 — production preceded required approval or operative privacy documents omitted the new functions:** not supported by the reviewed public record. The absence of a newly indexed public PIA cannot discriminate H1 from an internal PTA, a determination that an existing PIA/SORN remained adequate, an unpublished compliance artifact, or a later production date.

No finding of noncompliance is made.

## Approval and deployment chronology

| Date | Layer | Public record | What it establishes | What it does not establish |
|---|---|---|---|---|
| 2019-12-20 | Records | NARA approved `DAA-0567-2018-0001` | ATD Participant Tracking Records include GPS points and voice-verification data; cutoff is ATD termination and disposition is seven years after cutoff | ISAP V's implementation-level records map or destruction controls |
| 2023-03-17 | PIA | `DHS/ICE/PIA-062` ATD Program | Public ATD privacy baseline; identifies the monitoring app as BI's SmartLINK and says the app was not continuously monitoring location | Coverage of ISAP V's later continuous-location / on-demand function |
| 2023-12-15 | Adjacent PIA | `DHS/ICE/PIA-064` Publicly Available Information | ICE says programs using a tool that accesses, collects, or uses PII must submit a PTA; describes commercial databases and publicly available information | Direct approval for ERO skip tracing; the document's stated organizational scope is HSI and OPR |
| 2024-07-05 | SORN publication | Modified CARIER SORN, 89 FR 55638, docket `ICEB-2023-0011` | Notice sent to Congress and OMB; adds ATD geolocation/biometric purpose, GPS records, contractor ATD systems, public/commercial sources and contractor routine use | Project-level PTA/PIA/ATO or production approval |
| 2024-08-05 | SORN effective | Modified CARIER SORN takes effect | Pre-award effective SORN layer for the covered system, individuals, records, purposes and routine uses | Whether each 2025 implementation was reviewed and mapped to it |
| 2025-08-15 | ISAP V procurement | Original SAM package includes Attachment 13, Privacy Requirements | Requires a Privacy Lead to help DHS complete any required PTA, PIA, SORN, and supporting records on schedule | That such documents had already been completed |
| 2025-08-25 | ISAP V technical baseline | Revised final SOW | Requires the changed continuous-location behavior; requires four-month transition; includes FedRAMP/A&A documentation and agency-ATO process language | A production activation date or issued ATO |
| 2025-09-30 | ISAP V award proxy | `70CDCR25D00000062` / task `70CDCR25FR0000127` | Award and reported period of performance begin | Production use; the SOW expressly provides transition time |
| 2025-10-14 | ISAP V transition proxy | Transition plan due 14 days after award | Earliest disclosed transition-control deliverable | COR approval date, go-live approval, or full-performance acceptance |
| 2025-11-10–20 | Skip procurement | `26-SOL-DCR-01`, amendments and final Q&A | Commercial-data / physical-observation workflow; CUI and conditional ATO clauses; no transition built in and work expected immediately | Vendor-specific system boundary, PTA/PIA determination, issued ATO, or first PII processing |
| 2025-12-16–18 | Skip award proxy | First 13 visible task orders begin/obligate; BI task begins December 18 | Contractual tasking exists | First case file transfer, first search, first physical observation, or first accepted delivery |
| 2026-07-13 | Public-index check | DHS PIA index exact-term pass | Only 2023 PIA-062 indexed for ATD/PIA-062; no SmartLINK or skip-tracing result | Completeness of non-public ICE/DHS compliance files |

## H0/H1 discrimination by control layer

| Control layer | H0-supporting public evidence | H1-supporting public evidence | Status |
|---|---|---|---|
| SORN compatibility — ISAP V | 2024 CARIER SORN expressly covers contractor ATD systems, ATD geolocation/biometric purpose, and GPS-derived location | None found | Strong H0 support at SORN layer |
| SORN compatibility — skip tracing | CARIER covers relevant populations, possible addresses, public/commercial sources and contractor routine use | None found | Partial H0 support; implementation mapping absent |
| PTA / PIA decision | PIA-064 describes a general ICE PTA gate; ISAP V Attachment 13 requires support for any required PTA/PIA/SORN | No later public PIA-062 update indexed | Unresolved; public absence is non-discriminating |
| Security authorization | Both solicitations contain the ATO-before-CUI-processing clause; ISAP V adds FedRAMP/A&A deliverables | No issued ATO, revocation, or exception found | Gate established; completion unresolved |
| Records implementation | NARA schedule and 2024 SORN establish public retention authorities | No implementation mapping, destruction test, or disposition approval found | Authority layer established; implementation unresolved |
| Production timing | ISAP V transition controls could place full operation after award; skip Q&A anticipated immediate work | No dated activation, first case transfer, first query, observation, or accepted delivery found | Cannot compare approval and production clocks |

## Exact public controls

The 2024 CARIER SORN states that records are maintained in “contractor-owned IT systems, including those supporting the ICE Alternatives to Detention program.” Its purpose includes “geolocation tracking, biometric verification, and rapid enrollment” into ATD, and its categories include GPS-derived ATD location data. The notice also lists “Public and commercial sources, including social media” and allows contractor access when necessary to accomplish a related agency function.

ISAP V Attachment 13 says its Privacy Lead must support DHS so that DHS can complete any required “PTA, PIA, SORN, or other supporting documentation.” Both solicitations say the contractor “shall not collect, process, store, or transmit CUI” within a federal information system until the component or headquarters CIO grants an ATO, after which the contracting officer must incorporate it into the contract.

These clauses establish required controls. They do not substitute for the approval cover sheets, determinations, authorization letters, control assessments, or acceptance records that would prove the controls operated on particular dates.

## Public PIA repository and archive boundary

The DHS PIA index was queried with `items_per_page=50` and exact terms:

| Query | Live result |
|---|---|
| `Alternatives to Detention` | One row: `DHS/ICE/PIA-062 Alternatives to Detention (ATD) Program` |
| `DHS/ICE/PIA-062` | One row: the same PIA-062 |
| `SmartLINK` | No result |
| `skip tracing` | No result |
| `commercial data` | One row: PIA-055 RAVEn, an HSI platform |

Wayback's CDX record supplies 14 successful captures of the PIA-062 PDF from 2024-05-20 through 2026-06-21 and 66 captures of the DHS PIA collection page from 2019-10-19 through 2026-06-02. Archive coverage makes the public-page check reproducible; it does not make the public library a complete index of internal privacy work.

PIA-064 is an adjacent control model, not project approval. It says an ICE program using technology that accesses, collects, or uses PII must submit a PTA to ICE Privacy and that DHS Privacy approves PTAs. Its stated office scope is HSI and OPR, not ERO, so it cannot be used as direct approval of `26-SOL-DCR-01`.

## Records-retention reconciliation issue

PIA-062 separates records held by the ATD servicer's case-management system—destroyed seven years after participant termination—from EID/EARM records it describes as destroyed 75 years after entry. In that passage, it names `DAA-0567-2018-0001-0001` Participant Tracking Records and `-0002` Incident/Violation Reports for the 75-year statement.

The approved NARA schedule itself describes those two ATD categories as cut off when the participant leaves ATD and destroyed seven years later. The 2024 CARIER SORN also says ATD program records are retained seven years after removal from ATD/no longer monitored, while separately assigning a different schedule, `DAA-563-2013-0001-0006`, to 75-year arrest, detention and removal records in EID. Finding #12498 records this as an **apparent documentary divergence requiring system-and-record-category reconciliation**, not as an established conflict or unlawful-retention finding.

The missing implementation record is the current records crosswalk: which ISAP V continuous-location and skip-tracing inputs, intermediate results, exports, audit logs and case-system records land in which system/category, under which disposition authority and trigger.

## Precise FOIA / records request

The non-public dependency is tracked as infra request #153, and lead #58689 is blocked on that request rather than closed as proved or disproved.

Submit one coordinated ICE request, asking the FOIA office to search the following custodians and to refer DHS Privacy records when necessary:

1. **ICE Office of Information Governance and Privacy / ICE Privacy Unit** and **DHS Privacy Office**: PTAs; PTA approval sheets; PIA update or non-update determinations; SORN compatibility analyses; privacy compliance reviews; FIPPs/privacy-risk assessments; records of Privacy Office questions, responses, concurrence and approval milestones.
2. **ICE OCIO / CISO and authorizing official**: releasable ATO letter and authorization date; system/FISMA inventory identifier; security categorization; privacy-control assessment; authorization/risk-acceptance memorandum; authorization boundary and vendor/cloud-system identity. Exclude exploit-sensitive control detail if needed while preserving dates, decision, system name and approving office.
3. **ERO Alternatives to Detention / CARIER system manager**: ISAP V data-flow diagrams; continuous-location design review; implementation records crosswalk; data minimization/retention configuration; transition plan; COR approvals; operational-readiness/full-performance acceptance; first production activation of three-minute coordinate storage and first Government on-demand location request.
4. **ERO Removal Management / Detention Compliance and Removals**: `26-SOL-DCR-01` data-flow and privacy review; vendor system-boundary determinations; case-file export/transfer logs; first vendor receipt, first commercial-data query, first physical-observation task and first accepted delivery, with PII redacted but dates, vendor and record counts retained.
5. **ICE Office of Acquisition Management / responsible DCR contracting office**: the ATO compliance documents incorporated into the relevant contracts/tasks; privacy/security/records deliverables; COR acceptance; any waivers, non-applicability determinations, conditional approvals, plans of action, or risk acceptances.

Use these identifiers and date range:

- ISAP V solicitation `70CDCR25R00000018`; IDIQ `70CDCR25D00000062`; task `70CDCR25FR0000127`; Attachment 13; the supervisory biometric application and its continuous-location/on-demand-location requirement.
- Skip tracing `26-SOL-DCR-01` / `26SOLDCR01`; all resulting IDIQs and first task orders; commercial databases/data aggregators; automated and manual research; physical observation; government-furnished case exports.
- Search period: 2024-01-01 through the processing date, including email, Teams/SharePoint records, approval-routing systems, contract files and records-management systems.

The 2024 SORN identifies the ICE Office of Information Governance and Privacy at `iceprivacy-generalmailbox@ice.dhs.gov`, 500 12th Street SW, Mail Stop 5004, Washington, DC 20536, and DHS Privacy at `Privacy@hq.dhs.gov`. Those are notice-identified privacy contacts, not substitutes for filing through the ICE/DHS FOIA channel.

## Sources

- [Modified CARIER SORN, 89 FR 55638 / FR Doc. 2024-14768](https://www.federalregister.gov/documents/2024/07/05/2024-14768/privacy-act-of-1974-system-of-records)
- [CARIER docket ICEB-2023-0011](https://www.regulations.gov/docket/ICEB-2023-0011)
- [DHS/ICE/PIA-062 ATD Program](https://www.dhs.gov/sites/default/files/2023-08/privacy-pia-ice062-atd-august2023.pdf)
- [DHS PIA-062 publication page](https://www.dhs.gov/publication/dhsicepia-062-alternatives-detention-atd-program)
- [DHS/ICE/PIA-064 Publicly Available Information](https://www.dhs.gov/sites/default/files/2024-11/24_1126_priv_pia_ice064_socialmedia.pdf)
- [NARA schedule DAA-0567-2018-0001](https://www.archives.gov/files/records-mgmt/rcs/schedules/departments/department-of-homeland-security/rg-0567/daa-0567-2018-0001_sf115.pdf)
- [DHS PIA public index](https://www.dhs.gov/keywords/privacy-impact-assessment-pia)
- [SAM ISAP V opportunity](https://sam.gov/opp/8bcce9c16821469395136f30f092ffbf/view)
- [USAspending ISAP V task](https://www.usaspending.gov/award/CONT_AWD_70CDCR25FR0000127_7012_70CDCR25D00000062_7012/)
- [SAM skip-tracing opportunity](https://sam.gov/opp/bc8d7837d72149479146485298ff5ed5/view)
- [DHS OIG-21-06, privacy-compliance process review](https://www.oig.dhs.gov/sites/default/files/assets/2020-12/OIG-21-06-Nov20.pdf)
- [DHS HSAM Appendix G, Privacy Considerations in Contracting](https://www.dhs.gov/sites/default/files/2023-09/23_0926_cpo-appendix-g-conformed-thru-notice-2023-11_0.pdf)

Multiple mirrors of the same federal record were treated as redundancy rather than corroboration. Award starts and obligations are contractual proxies, not proof of service delivery, first PII processing, or payment.
