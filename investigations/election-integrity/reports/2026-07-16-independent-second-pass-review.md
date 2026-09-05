---
date: 2026-07-16
review_type: independent-second-pass
scope: four White House election-integrity ZIP collections
pdf_instances: 58
unique_pdf_hashes: 55
pages_reviewed: 269
database_writes: false
originals_modified: false
privacy: user-designated identities omitted
---

# White House election-integrity release: independent second-pass review

## Executive assessment

The release contains genuine government records and several real disclosures, but its public framing repeatedly states the most accusatory interpretation more strongly than the enclosed documents support.

The defensible cross-collection conclusions are:

1. **The voting-system documents establish vulnerability, hostile capability, attempted access, collection, and analytic disagreement. They do not establish that a certified U.S. vote total was altered.** The contemporaneous assessments repeatedly say large-scale undetected manipulation would be difficult and that paper trails or audits would likely expose it.
2. **PRC-linked actors obtained or handled extensive U.S. voter data through mixed channels.** The visible records include purchase, public/commercial download, cyber collection, and possession of catalogs describing leaked or compromised datasets. They do not show 220 million unique voters, one 220-million-record compromise, or intrusions into 18 state government systems.
3. **The Michigan files document a real investigation and credible evidence that some registration applications were fabricated.** The 8,000-10,000 figure is the total volume associated with the operation, not a fraud count. The released record does not show that a fabricated application produced a counted ballot or changed a result.
4. **The approximately 278,000 noncitizen headline appears to be White House arithmetic from two differently scoped lower-bound figures on one unsigned DHS page.** The package discloses no common methodology, four-state denominator, duplicate-control procedure, false-positive rate, naturalization adjudication, or count of ballots tied to the headline population.
5. **The ZIPs preserve unusually informative release-preparation metadata.** The four collections are strongly linked to one macOS filesystem-owner/account context and a 38-second Chrome acquisition sequence, followed by at least two later packaging bursts. The evidence does not identify a person or a unique physical computer.
6. **Apart from the user-designated issue intentionally omitted from this report, no additional improper redaction or sensitive file-level metadata leak was found.** A second adversarial pass covered all 58 PDFs and 269 pages and tested live text, vector masks, raster bars, OCR layers, object graphs, prior revisions, attachments, forms, annotations, optional layers, and active content.

This was a read-only local review. Nothing was written to `investigation.db`, and the downloaded ZIPs and extracted originals were not modified.

## Scope, integrity, and method

The corpus contains four ZIPs, 58 PDF entries, 269 pages, and 55 unique PDF byte streams. Three PDFs are exact duplicates cross-filed in collections 1 and 2: the July 2020 CIA wire memo, the August 2020 NICA, and the December 2021 internal email.

All four ZIP SHA-256 values match `datasets/wh_election_integrity/provenance/sha256sums-20260716.txt`. Every extracted PDF matches both its manifest row and its ZIP payload in size and SHA-256. No archive is encrypted, split, prefixed with an executable stub, trailed by an extra payload, or affected by path traversal, duplicate entry names, or CRC failure.

Each collection was first reviewed independently without opening the prior reports. The blind reports were then compared against the day-one review, with consequential disagreements reopened against the original PDFs. Derived OCR was used for discovery only; page citations and redaction conclusions were checked against the released originals and rendered pages.

Technical review included `pdfinfo`, `pdftotext`, `pdffonts`, `pdfimages`, `pdfdetach`, `qpdf`, `zipinfo`, raw ZIP/AppleDouble parsing, pypdf, PyMuPDF, pdfplumber, high-resolution rendering, independent OCR, vector-to-text geometry, image-channel and near-black transforms, xref/EOF analysis, and earlier-revision reconstruction.

## Collection 1: voting-system vulnerabilities

### What the documents establish

- `NICM_VulnerabilitiesInUS2020ElectionInfrastructure_15JAN2020_DECLASS_REDACTEDed.pdf` is a capability assessment, not an intent or incident finding. It says the IC did not know of specific plans, judges coordinated statewide or multistate manipulation difficult, and says testing, paper trails, and audits would very likely expose such an effort (PDF pp. 1, 3-4). It also warns that real low-impact intrusions could be paired with false compromise narratives to erode public confidence (p. 4).
- `NICA_ Foreign Threats to 2020 US election_19AUG2020 - DECLASS_REDACTED.pdf` similarly says localized manipulation was possible but a broad campaign would be difficult; paper trails and audits would probably expose it, and disruption of results-reporting systems probably would not affect certified results (PDF p. 5).
- `CIA Wire Memo Summer 2020 DECLASS REDACTED.pdf` reports Chinese collection and unsuccessful campaign spear-phishing. Its contemporaneous judgment was that China did not then intend covert interference to sway the result, although collected information could enable later operations (PDF p. 1).
- `NICM_ChinaStepsToInfluenceElection_16OCT2020_DECLASS_REDACTED.pdf` is an expressly non-coordinated alternative analysis with low-to-medium confidence. The mainline and minority views disagreed over whether low-level public, diplomatic, and covert activity qualified as election influence; both agreed China avoided interference with U.S. election systems (PDF pp. 1, 6-7).
- The December 2020 coordination email shows that the minority analysis faced substantive source-quality objections: leadership intent was described as unsupported, some reporting chains as weak or dubious, and collection gaps as insufficient substitutes for evidence (PDF pp. 1-2). This proves an analytic dispute occurred; it does not make the minority conclusion an IC consensus.

### Venezuela note

`CIA Note - Venezuela Machines Intel Memo_29JUNE2026_DECLASS_REDACTED.pdf` is a new June 2026 CIA-only synthesis of selected 2004-2020 reporting, not a contemporaneous or IC-coordinated 2020 assessment. It recounts reporting about Venezuelan plans and an alleged virtual-machine/hash-substitution technique, but states that large-scale electronic fraud was not definitively confirmed and that the advanced technique came from limited reporting (PDF pp. 2-4). CIA's 2012 baseline analysis found no large-scale electronic fraud; a contrary 2013 scenario was a Devil's Advocacy exercise with conflicting reporting and limited insight (pp. 3, 5). The White House framing reflects the alleged technique but omits these central limitations.

### Newly authored CISA product

`CISA Election Report - FINAL.pdf` is a July 2026 retrospective, not a declassified 2020 intelligence product. It describes real weaknesses found in selected, owner-requested assessments, but gives no denominator for systems, networks, vulnerabilities, jurisdictions, remediations, or affected voters (PDF pp. 1-6). It does not state that a vulnerability changed a certified result.

Its metadata is informative:

- created/as-of July 13, 2026, then modified in Acrobat at 12:14:24 EDT on release day;
- Word/Adobe producer lineage;
- template headline `Factsheet Final 2024-03 Template` and placeholder keywords;
- a retained Microsoft Purview `For Official Use Only (FOUO)` label set in 2024; and
- no named individual author, source path, personal email, or embedded Office document.

The 2024 template/label date shows template lineage, not that the July 2026 report existed in 2024.

## Collection 2: China voter data

### Record count, not unique voters

No released PDF visibly prints `220 million`. The only disclosed numerical route is the sum of four table rows in `200M Voter Records Compromised - declass marked_Redacted.pdf`, PDF pp. 3-4:

`204,822,241 + 1,746,069 + 7,893,248 + 5,578,302 = 220,039,860 records`.

That is an arithmetic sum of records, not a disclosed count of unique people or files. The package provides no row-level data, unique identifiers, overlap analysis, or deduplication method. The 204.8-million national/unspecified row may already overlap the three state rows. Five other state-database rows have unknown volumes. The product describes a PRC entity's possession of a document listing likely leaked or compromised datasets and, for the largest row, only possible possession by a person referenced in the reporting. It does not document one PRC operation compromising 220 million records.

The aggregate number in `PRC Collection of US VoterMilitaryData - clean - declass marked_Redacted.pdf` is fully blacked out. OCR that appeared to read `220` was a false reading and cannot be used as evidence. That report combines consumer, voter-registration, and military databases and is not an independent visible confirmation of the table sum.

### Mixed acquisition mechanisms

- `US Voter Registration for 6 States...pdf` says historical registration repositories for six states were downloaded from public commercial websites in January 2022; motivation was unknown, and future misuse was described as theoretical (PDF pp. 1-3).
- `PRC US Voter Data 7 States 2023...pdf` says 2020 data had been purchased and samples were supplied for seven states (PDF pp. 1-2).
- `PRC U.S. Presidential Election-Related Intelligence in 2020...pdf` concerns collection of public U.S.-government election information (PDF pp. 1-2).
- `18 States Memo...pdf` supports analysis of registration data associated with 18 states for identity matching, target discovery, and public-opinion analysis (PDF pp. 1-4). It does not disclose intrusions into 18 state systems; acquisition clauses and much state-level provenance are redacted.

The public page's blanket `bought, stolen, or hacked` framing collapses materially different channels. No visible passage establishes that China hacked 18 state voter systems or stole every dataset described.

### Dedicated unit and analytic dispute

No unredacted passage substantiates the page's dedicated `data exploitation unit` claim. Organizational names are masked, so the assertion may depend on withheld text, but the public package does not permit verification.

The internal dispute was real and consequential. The November chain includes the statement that a pending PDB had been `deliberately massaged` away from direct election links. The same record also says reports would be split, cross-posted, or downgraded for the statutory 45-day assessment; the concern was sent to the IC Analytic Ombudsman the same day. The October chain shows the alternative-analysis route being used, and the resulting non-coordinated minority memorandum appears in collection 1. These records support scrutiny of analytic framing, but do not alone prove a completed effort to hide all relevant reporting from policymakers or the public.

### Albany raw reporting

The six-page Albany IIR was raw, indirect, and explicitly not finally evaluated. It relied on an identified source's indirect access to an unidentified PRC-government subsource and warned recipients not to act without FBI coordination (PDF pp. 2-4). The later review packet documents unusually aggressive and politically sensitive handling, but also substantial reliability and counterevidence: the source was new and required reinterview, related reporting raised credibility concerns, CBP said most counterfeit licenses it encountered were used by underage purchasers seeking alcohol, and the claimed address data central to the mechanism did not fit one cited platform's collection practices. The process warrants scrutiny; the package does not validate the alleged voting scheme.

### Metadata

Twenty-two source-package PDFs plus the collection folder share one Chrome quarantine event at `16:02:57Z`. The 2026 task-force statement was separately added through Mattermost at `16:25:47Z` and opened at `16:26:19Z`. Three unsigned summary pages were scanned on an HP multifunction device within 34 seconds on July 14, strongly indicating one physical three-page item rather than three independent reports. Seventeen linearized PDFs have malformed hint tables, but no stale prior revisions or hidden object payloads.

## Collection 3: Michigan voter-registration investigation

### What the evidence supports

The files document a real investigation triggered after a city clerk identified suspicious registration applications. They contain database anomalies, several inculpatory witness statements, repeated investigative work, charging debate, and a protracted disposition process.

The strongest witness account is serious: the interview summary describes management instructions to invent information, form-by-form admissions concerning 22 applications, and an estimate of about 100 fabricated submissions (PDF pp. 1-3). A material credibility/context detail omitted from the day-one synthesis is that the witness first said she remembered all the people on the forms, then gave the fabrication account after agents said the forms appeared fabricated. The admission should neither be dismissed nor generalized without that sequence, the applications, or a transcript.

Two other interviews contain a changed-account admission involving friends or relatives and an equivocal statement about probable forgery. Other released interviews contain denials, hearsay, workplace observations, compensation accounts, and speculation. They are not interchangeable corroboration.

### Scale and samples

- The October 2020 referral associates approximately 8,000-10,000 applications with the operation and says an **undetermined number** appeared fraudulent (PDF pp. 1-3). The headline is total volume, not a fraud count.
- A 20-application review reports serious anomalies, including fabricated identities and mismatched identifiers, but the source calls the forms randomly selected while also saying their handwriting differed from forms initially flagged by the clerk. The sampling frame and randomization method are absent, so the set cannot be extrapolated to 8,000-10,000 (PDF pp. 1-2).
- A separate 107-application review reports 91 with no database return, 16 corresponding to existing people, and four of those 16 with matching signatures. `No database return` is not proof of a fictitious person, and the package omits the source spreadsheet, search tolerances, signature material, and selection method.

The prior synthesis incorrectly said the 107-item box was intercepted unprocessed. The chronology separately describes **100** applications as reportedly not processed, with unreleased results. No released document links that 100-item set to the later 107-item evidence box. The processing and voter-roll disposition of the 107 therefore remain unknown.

### Disposition, ballots, and motive

The September 25, 2025 closure says leads were exhausted, no criminal violation or national-security priority was identified, no evidence established false submissions for the purpose of enabling voting, no instruction to falsify was found, and an AUSA concurred. This materially undercuts the public framing and creates tension with the strongest 2023 interview. Redactions and missing reasoning prevent determining whether the closure addressed exactly the same person, conduct, institutional-liability theory, voting-purpose element, or statute.

The released record does not show that a fabricated application was accepted into the voter file, generated a ballot, produced a counted vote, or affected a result. It also does not establish formal party affiliation or an intentional cover-up. The timeline supports criticism of scope-gating, a roughly five-week election-policy pause, an approximately eight-month laboratory processing interval, and prolonged charging indecision. It does not prove the motive behind those delays.

### Metadata

All 25 PDFs are rasterized, optimized PDF 1.6 files stripped of standard Info and XMP metadata. One file has a nonstandard catalog-level `Producer = MuPDF 1.27.2`, likely reflecting release processing rather than original authorship. The collection carries one Chrome-originated quarantine event and two later filesystem handling clusters. Unix `ctime` is a status-change time, so the clusters are consistent with staged assembly but do not prove exactly when each document was added.

## Collection 4: noncitizen voter rolls

### The approximately 278,000 figure

`Alien Voter Registration Summary.pdf_Redacted.pdf` states two differently scoped lower bounds on one page:

- `over 250,000` in public voter files from four states; and
- `over 28,000` identified across 25 states that processed more than 68 million records through SAVE.

No released PDF prints approximately 278,000. The White House appears to add the two rounded lower bounds. The page does not disclose whether the populations are independent, although it describes the four named states as not having used SAVE.

The displayed ten-state table independently sums to 360,176 deceased entries and 10,716 noncitizen entries, only part of the narrative totals. The one-page summary supplies no four-state denominator, record-linkage fields, definition of a match, duplicate handling, naturalization update procedure, manual adjudication, false-positive rate, confidence interval, or state confirmation. It uses `allegations`, `identify`, and categorical `illegally registered` language without explaining the transition.

The page says officials used SAVE to identify people who `registered and/or voted`, but supplies no count, cases, or linkage between any votes and the 250,000/28,000 headline populations. The precise conclusion is not that the document never uses the word `voted`; it is that the release does not show that the people counted in the headline figures cast illegal ballots.

### Companion cybersecurity report

`Voter Registration Database Threats - FINAL.pdf` is a July 2026 cyber-risk and mitigation report. It contains no noncitizen estimate and does not corroborate the 278,000 arithmetic. Its executive summary says hackers probed all 50 states and had confirmed successes in at least 20, while a later example says the number of successful probes could not be determined and cites at least seven compromised networks. The report neither lists nor defines the 20-state total (PDF pp. 2-3).

The report was created in Word on June 24, modified July 13, and shares a Microsoft Purview label GUID and tenant/site identifier with the CISA report. It contains one recoverable earlier PDF state. The base and final versions both have 11 pages and the same 3,089-token sequence; differences are layout/antialiasing and reference-page reflow, not removed substantive or sensitive text.

## Cross-ZIP packaging-computer metadata

### Direct evidence

| Artifact | Finding | What it supports |
|---|---|---|
| AppleDouble and `.DS_Store` | All archives preserve macOS metadata conventions; 64 AppleDouble files are present | macOS handling and Finder/copyfile-style metadata preservation |
| Embedded ownership | All 128 ZIP entries contain the same unusual UID `568130747` and GID `1649063471` | same filesystem-owner/directory-service context |
| Chrome quarantine | Four collection-specific events occurred in collection order at `16:02:35Z`, `16:02:57Z`, `16:03:05Z`, and `16:03:13Z` | one tightly grouped acquisition/extraction workflow |
| Application-specific events | CISA file: Adobe Acrobat at `16:14:24Z`; task-force statement: Mattermost at `16:25:47Z` | two files introduced or handled through different applications |
| Writer timezone | DOS timestamps are consistently UTC-4 relative to UT fields | writer environment used UTC-4; geography is not proved |
| Writer structure | Unix/2.0 creator field, `0x7875` then `0x5455` extras, streamed data descriptors, AppleDouble sidecars | libarchive-like ZIP writer plus macOS copyfile-style metadata |
| Michigan `.DS_Store` | one Finder record for `NEW ADDED FOR UPLOAD 7.15.26` | a temporary curation-folder label existed during assembly |

### Supported inferences

- **High confidence:** all four collection trees passed through one macOS account/filesystem-owner context.
- **High confidence:** the four source packages were acquired sequentially in one 38-second Chrome session and then staged locally.
- **Medium confidence:** final packaging occurred in at least two later bursts: collections 2/3 in the afternoon and collections 1/4 in the evening.
- **Likely but not proved:** one physical Mac performed all steps. A shared volume, cloned account, or copied metadata could reproduce much of the pattern.

### Not present

No archive-embedded field discloses a username, hostname, hardware or volume UUID, IP address, absolute path, home directory, account email, Chrome profile, browser version, source URL, Mattermost workspace/channel, or human-readable UID/GID mapping. The quarantine UUIDs are event identifiers, not device or user identifiers. The exact ZIP application and macOS version are not recoverable.

Local xattrs on the four downloaded ZIPs describe the research machine that fetched them and were excluded from attribution to the White House packaging environment.

## Redaction and hidden-content review

The user-designated issue is intentionally not reproduced, described, located, hashed, or made easier to identify. The conclusion below concerns **additional** leaks only.

No additional improper redaction or sensitive file-level metadata leak was found.

The adversarial QC independently reconciled all 58 manifest rows and 269 pages. Key results:

- 208 opaque live-vector rectangles across four PDFs produced zero word intersections, zero non-space character centers inside a mask, zero characters after a 1.5-point inset, and zero invisible characters inside masks;
- 31 coarse bounding-box overlaps all resolved to adjacent visible-glyph edge contacts;
- high-risk raster regions were tested at 300 dpi with thresholding, histogram stretching, CLAHE, RGB residuals, OCR, and visual comparison; apparent pseudo-text was compression/scanner texture or bar-edge noise;
- 38 annotations were ordinary links, 41 AcroForm dictionaries were empty, and no attachment, script, launch action, stored form value, redaction annotation, or active hidden layer was found;
- one optional-content definition is unused by page content and carries no hidden text;
- 18 apparent extra image objects were mask resources rather than orphaned page images;
- 49 qpdf-warning files contain malformed linearization/hint-table metadata, not damaged-object reconstruction or stale prior revisions; and
- the one genuine incremental prior state contains the same 3,089-token sequence as the final PDF.

This supports high confidence against ordinary PDF redaction failures in the released files. It does not prove that every pre-flattening source was redacted correctly, that every withholding was justified, or that omitted source files contain no additional material.

## Corrections and refinements to the day-one review

The first review's central narrative is independently corroborated, but the following changes materially improve precision:

| Day-one wording or implication | Second-pass correction |
|---|---|
| CISA report was `finalized July 13` | It was created/as-of July 13 and modified in Acrobat on July 16. Metadata does not prove an organizational final-approval event. |
| CISA/noncitizen reports were `never classified` | The released copies are unclassified and lack declassification stamps. That does not prove every earlier lifecycle state. |
| CIA Venezuela note `contradicts` the page | The note recounts the alleged plan but materially qualifies certainty and applicability. `Qualified by` is more accurate. |
| The CIA note had a `two-day classification lifetime` | It is dated two days before its declassification stamp; the file does not state when classification first attached. |
| A 15-fold noncitizen flag-rate gap is internally established | No four-state denominator is disclosed. Any rate comparison requires external population and method assumptions. |
| Public-file possession disproves a claim that states `refused` data | The refusal claim is unsupported by the released documents, but public files do not disprove refusal of a different request. |
| Neither noncitizen document says anyone voted | The one-pager uses `registered and/or voted`, but supplies no count or link to the headline figures. |
| Michigan's 107-item box was intercepted unprocessed | The unprocessed description belongs to a separate 100-item set. The 107 forms' processing and roll disposition are unknown. |
| Eight-month FBI laboratory `backlog` | The documents show an approximately eight-month processing interval; `backlog` assigns an unproved cause. |
| The 2025 Michigan closure simply contradicts the page | It materially undercuts the framing and creates unresolved tension, but redaction and missing reasoning obscure exact subject/theory scope. |
| The 204.8-million dataset matches a known public dataset | The count/size/date profile is suggestive, but identity remains a hypothesis without a source copy, hash, schema, or uniquely matching fields. |
| All ZIPs were rebuilt in one evening event | Embedded times support at least two packaging bursts; collection 2 was assembled around 16:26Z, not 22:26Z. |
| `Downloaded via Chrome` proves a click-by-click workflow | Quarantine metadata proves Chrome-associated events, not the source URL or exact user action. |
| Same Mac is proved | Same macOS account/filesystem-owner context is high confidence; same physical machine is likely but not uniquely attributable. |
| White House Counsel authority is `nonstandard` | The stamps raise a legal/administrative question, but that conclusion needs the applicable delegation and classification-authority record. |
| No FOIA lineage | The released copies lack FOIA exemption codes and carry White House release marks; that does not exclude an earlier FOIA-processing stage. |

## Missing evidence and unresolved questions

The largest remaining limitations are omissions, not technical redaction leaks:

- the CIA Venezuela note's source apparatus and underlying reporting;
- row-level voter datasets, hashes, schemas, acquisition records, and a deduplicated unique-person count;
- before-and-after PDB language, final distribution records, customer briefing history, and the complete 45-day assessment workflow;
- the Michigan source spreadsheets, applications, 100- and 107-item result sets, laboratory report, full interview corpus, reasoned charging analysis, and voter-file/ballot dispositions;
- the noncitizen matching keys, four-state denominators, naturalization handling, duplicate controls, manual adjudication, false-positive rate, state confirmations, and ballot-level evidence; and
- external legal authority needed to evaluate the declassification stamps and any earlier production lineage.

## Durable second-pass artifacts

All durable artifacts are privacy-sanitized and contain no user-excluded identities:

- `investigations/election-integrity/reports/2026-07-16-independent-second-pass-review.md` — this synthesis.
- `datasets/wh_election_integrity/analysis/second-pass-20260716/archive-packaging-forensics.md` — detailed ZIP/header/AppleDouble/`.DS_Store` analysis.
- `datasets/wh_election_integrity/analysis/second-pass-20260716/redaction-qc.md` — adversarial redaction and privacy QC.
- `datasets/wh_election_integrity/analysis/second-pass-20260716/zip-forensics.json` — complete machine-readable archive/entry metadata.
- `datasets/wh_election_integrity/analysis/second-pass-20260716/cross-archive-summary.json` — compact cross-archive timeline and correlations.
- `datasets/wh_election_integrity/analysis/second-pass-20260716/pdf-metadata-compact.json` and `pdf-xmp-signals.json` — document metadata extracts.
- `datasets/wh_election_integrity/analysis/second-pass-20260716/redaction-audit.json` and `redaction-deep-checks.json` — machine-readable redaction coverage and high-risk checks.

