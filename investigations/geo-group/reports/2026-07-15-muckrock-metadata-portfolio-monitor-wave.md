# MuckRock metadata, requester-portfolio, and completion-monitor wave

**Research date:** 2026-07-15  
**Primary profile:** `geo-group`  
**Companion reports:** `2026-07-15-muckrock-cross-investigation-sweep.md` and `2026-07-15-muckrock-hidden-release-search.md`  
**Result:** three newly preserved MuckRock releases, one visually reviewed aggregate table, one confirmed 27-attachment processing lead, and a bounded negative result for the active `epstein-gates-ipi` gaps

## Outcome

This pass used MuckRock's metadata structures rather than released-file OCR: requester portfolios, request descriptions, agency/status/document-class filters, projects, tags, federal-jurisdiction filters, completion ordering, communication bodies, file metadata, and FOIA tracking identifiers. Exact remote queries and local metadata scans were checked against and written to `search_log`/`search_history` under source `muckrock`.

The strongest discovery is MuckRock request `131234`, a newly completed DHS-OIG production of the working papers behind OIG-22-47 on GEO-operated Folkston. The public OIG report and its conclusions are already represented in the investigation, but the underlying working papers are not. The production directly targets an existing gap for the contract-discrepancy/penalty calculations, non-enforcement decision, invoices, recommendation-closure support, and related correspondence.

Three requests were downloaded, preserving the original MuckRock deliveries:

| Request | Local package | API file refs / unique local files | Release status |
|---:|---|---:|---|
| `131234` | `datasets/muckrock/131234/` | 8 refs / 7 unique files; 733 MB | Completed; 3,866-page interim production plus 322-page final production; final responsive PDF unlocks with a public follow-up message |
| `137245` | `datasets/muckrock/137245/` | 7 files; 676 KB | Completed; only the final one-page PDF is substantive responsive material; earlier ZIPs are response/appeal letters |
| `20845` | `datasets/muckrock/20845/` | 5 files; 17 MB | Completed; three substantive image-only grievance-log PDFs totaling 37 pages plus two 100x100 delivery-image artifacts |

No finding or lead was inserted into the database. Import-ready items appear below. Request descriptions and requester assertions were used only for discovery and were not treated as evidence.

## Highest-value confirmed releases

### 1. Request 131234 — DHS-OIG working papers for Folkston OIG-22-47

- **Request:** `131234`, “DHS-OIG Working Papers OIG-22-47”
- **Requester:** user `25665`
- **Agency:** DHS Office of Inspector General, agency `236`
- **Tracking:** `2022-IGFO-00222`
- **Status / completion:** `done`, 2026-01-28
- **Requested class:** working papers, interview notes, correspondence, and other records used to prepare OIG-22-47 concerning GEO-operated Folkston IPC and Annex
- **Files:** 8 API file references, 7 unique local files because two acknowledgement references resolve to the same file; package is 733 MB

The May 14, 2025 interim response letter says DHS-OIG released 3,833 pages in full and 33 in part, with 1,066 pages referred to ICE. The delivered `First_Interim_Response_Documents_-_2022-IGFO-00222.pdf` is 3,866 pages and approximately 716 MB. It is unencrypted but image-only: the first 20 pages yield only form-feed characters under native extraction.

The January 28, 2026 final response letter says DHS-OIG released 222 pages in full and 100 in part, with another 644 pages referred to ICE. `DHS-OIG_Final_Response_Documents_2022-IGFO-00222.pdf` is a separate 322-page, 16 MB production. It is password-protected, but communication `2203366`, sent two minutes after the delivery, publicly supplies the password. The password was used transiently, was not printed or persisted, and successfully authenticated the original. The final production has approximately 789,000 native-text characters.

An index-only search of the unlocked 322-page final production found high-priority review pages without promoting their contents as facts:

| Term | Candidate PDF pages |
|---|---|
| `contract discrepancy` / `financial penalt` / `full contract funding` | 48, 122 |
| `invoice` | 259, 276–279 |
| `waiver` | 307, 308, 310 |
| `recommendation 12` | 52, 60, 72, 104, 126, 134, 146, 180, 218 |
| `overtime` | 48, 60, 122, 134, 180, 209 |

These are processing pointers, not findings. Every promoted claim still requires page-level text and visual review. The 644- and 1,066-page ICE referrals are not part of the delivered OIG productions and remain an access gap.

**Deduplication:** OIG-22-47 itself and its public conclusion about attempted but unenforced staffing penalties are already represented by findings `12425`–`12427` and several July 13–14 reports. Request `131234` is valuable because it is the underlying working-paper corpus, not because the already-known public report is a new source. Any repeated copy of the OIG report or ICE response must be treated as redundancy.

### 2. Request 137245 — FY2022 corrective-action count table

- **Request:** `137245`, “CDRs & CAPs - Q1-Q3 FY22”
- **Requester:** user `25665`
- **Agency:** ICE, agency `133`
- **Tracking:** `2023-ICAP-00260` on the appeal; underlying request `2023-ICFO-04524`
- **Status / completion:** `done`, 2024-06-27
- **Files:** seven delivered files, including four ZIPs; the first three ZIPs contain only response or appeal letters, while the final ZIP contains one substantive PDF
- **Substantive release:** `FOIA_Facilities Subject to AP_2022.pdf.pdf`, one native-text page, visually reviewed

The page is a two-column facility table headed “Number of corrective actions FY22 (Q1, Q2, Q3).” The Tacoma / Northwest ICE Processing Center row shows `12`. This is an aggregate count only. It does **not** identify the corrective action, standard, severity, outcome, contract remedy, financial consequence, or whether a particular action came from a CDR versus another corrective-action process. It should not be characterized as 12 violations or 12 enforced penalties.

**Import-ready candidate (not inserted):**

- Profile: `geo-group`
- Proposed title: `ICE listed 12 FY2022 Q1–Q3 corrective actions for Tacoma/Northwest ICE Processing Center`
- Claim type: `paraphrase`
- Confidence: `high`
- Evidence: `MUCKROCK:137245:FOIA_Facilities Subject to AP_2022.pdf.pdf:p1`
- Required qualifier: aggregate corrective-action count only; no severity, outcome, or financial-consequence inference

**Deduplication:** the investigation already has later Tacoma inspection and repeat-deficiency evidence, but no existing evidence reference to request `137245` was found. The table can supply period-specific context; it is not independent corroboration of a particular later deficiency.

### 3. Request 20845 — Arizona GEO-facility grievance logs

- **Request:** `20845`, “Unit Coordinator Grievance Logs, AZ GEO facilities”
- **Requester:** user `2116`
- **Agency:** Arizona Department of Corrections, agency `643`
- **Status / completion:** `done`, 2016-01-12
- **Requested facilities:** Arizona State Prison–Florence West, Arizona State Prison–Phoenix West, and Central Arizona Correctional Facility
- **Substantive files:** `PHXW_2015_Grievance_Logs_REDACTED.pdf` (12 pages), `FLOW_2015_Grievance_Logs_REDACTED.pdf` (13 pages), and `CACF_2015_Grievance_Logs_REDACTED.pdf` (12 pages)

All 37 pages are 300-DPI page images with essentially no native text. A visual check of CACF page 1 confirmed an Arizona Department of Corrections Unit Coordinator Grievance Log with handwritten grievance descriptions, case numbers, routing dates, and a printed category legend. The logs are suitable for human-assisted transcription or handwriting-aware OCR, but individual entries have not been reviewed or promoted. Operator identity and contract period should be rechecked before attributing every facility row to GEO.

**Import-ready processing lead (not inserted):** OCR/transcribe each month, normalize the printed category codes, retain redactions, and count only administrative log entries—never infer substantiation or agency agreement from a grievance description.

### 4. Request 136588 — ICE public-affairs response records for deaths at GEO Aurora and CoreCivic Torrance

- **Request:** `136588`, “ICE Public Affairs Responses to In-Custody Deaths at Aurora, Torrance”
- **Requester:** user `25665`
- **Agency:** ICE, agency `133`
- **Tracking:** `2025-ICAP-00083`
- **Status / completion:** `done`, 2025-02-13
- **Release status:** 27 confirmed file references: 26 ZIP archives and one small delivery JPG; reported page counts are all zero because the releases remain inside archives
- **Scope:** the request sought ICE public-affairs emails, calendar entries, Teams messages, SharePoint material, and related records concerning deaths at GEO's Aurora facility and CoreCivic's Torrance facility
- **Local status:** intentionally not downloaded in this wave; no page-level review

This is a mixed-operator corpus. It is an import-ready `geo-group` processing lead because Aurora is directly in profile, but Torrance records are a peer/control and must not be silently attributed to GEO. The 26 archives arrived through repeated appeal/remand communications from April 2023 through February 2025 and should be downloaded newest/final-first, unpacked outside the evidence directory, and deduplicated by hash before OCR or review.

Exact attachment manifest:

| File ID | Delivery date | Title | Release URL |
|---:|---|---|---|
| `1080121` | 2023-04-06 | `1471183-20230406144758251` | https://cdn.muckrock.com/foia_files/2023/04/06/1471183-20230406144758251.zip |
| `1097431` | 2023-06-21 | `2127532-20230621141436829` | https://cdn.muckrock.com/foia_files/2023/06/21/2127532-20230621141436829.zip |
| `1097927` | 2023-06-23 | `2134126-20230623085416062` | https://cdn.muckrock.com/foia_files/2023/06/23/2134126-20230623085416062.zip |
| `1104539` | 2023-07-25 | `~WRD0002` | https://cdn.muckrock.com/foia_files/2023/07/25/WRD0002.jpg |
| `1109016` | 2023-08-16 | `2927829-20230816140845778` | https://cdn.muckrock.com/foia_files/2023/08/16/2927829-20230816140845778.zip |
| `1130242` | 2023-11-08 | `6086497-20231108163745151` | https://cdn.muckrock.com/foia_files/2023/11/08/6086497-20231108163745151.zip |
| `1141831` | 2023-12-27 | `6250719-20231227145841696` | https://cdn.muckrock.com/foia_files/2023/12/27/6250719-20231227145841696.zip |
| `1141832` | 2023-12-27 | `6250768-20231227150449759` | https://cdn.muckrock.com/foia_files/2023/12/27/6250768-20231227150449759.zip |
| `1145439` | 2024-01-11 | `6304928-20240111101437151` | https://cdn.muckrock.com/foia_files/2024/01/11/6304928-20240111101437151.zip |
| `1148101` | 2024-01-23 | `6354309-20240123101657974` | https://cdn.muckrock.com/foia_files/2024/01/23/6354309-20240123101657974.zip |
| `1148488` | 2024-01-24 | `6363234-20240124124903988` | https://cdn.muckrock.com/foia_files/2024/01/24/6363234-20240124124903988.zip |
| `1155903` | 2024-02-20 | `6477296-20240220160106724` | https://cdn.muckrock.com/foia_files/2024/02/20/6477296-20240220160106724.zip |
| `1156685` | 2024-02-21 | `6480660-20240221092542327` | https://cdn.muckrock.com/foia_files/2024/02/21/6480660-20240221092542327.zip |
| `1157637` | 2024-02-27 | `6515255-20240227114356735` | https://cdn.muckrock.com/foia_files/2024/02/27/6515255-20240227114356735.zip |
| `1157639` | 2024-02-27 | `6515276-20240227114613833` | https://cdn.muckrock.com/foia_files/2024/02/27/6515276-20240227114613833.zip |
| `1162612` | 2024-03-15 | `6624744-20240315153432144` | https://cdn.muckrock.com/foia_files/2024/03/15/6624744-20240315153432144.zip |
| `1163625` | 2024-03-21 | `6652294-20240321130641725` | https://cdn.muckrock.com/foia_files/2024/03/21/6652294-20240321130641725.zip |
| `1170633` | 2024-04-18 | `6896065-20240418140034093` | https://cdn.muckrock.com/foia_files/2024/04/18/6896065-20240418140034093.zip |
| `1170634` | 2024-04-18 | `6896159-20240418140349171` | https://cdn.muckrock.com/foia_files/2024/04/18/6896159-20240418140349171.zip |
| `1186115` | 2024-06-11 | `7209616-20240611150158160` | https://cdn.muckrock.com/foia_files/2024/06/11/7209616-20240611150158160.zip |
| `1208118` | 2024-08-12 | `7411904-20240812095040887` | https://cdn.muckrock.com/foia_files/2024/08/12/7411904-20240812095040887.zip |
| `1236440` | 2024-11-12 | `8061005-20241112103456441` | https://cdn.muckrock.com/foia_files/2024/11/12/8061005-20241112103456441.zip |
| `1239184` | 2024-11-20 | `8110530-20241120101654819` | https://cdn.muckrock.com/foia_files/2024/11/20/8110530-20241120101654819.zip |
| `1248431` | 2024-12-18 | `8255839-20241218125701496` | https://cdn.muckrock.com/foia_files/2024/12/18/8255839-20241218125701496.zip |
| `1259983` | 2025-02-11 | `8587844-20250211112437243` | https://cdn.muckrock.com/foia_files/2025/02/11/8587844-20250211112437243.zip |
| `1260086` | 2025-02-11 | `8590847-20250211143950901` | https://cdn.muckrock.com/foia_files/2025/02/11/8590847-20250211143950901.zip |
| `1260588` | 2025-02-13 | `8605566-20250213102109036` | https://cdn.muckrock.com/foia_files/2025/02/13/8605566-20250213102109036.zip |

## Other confirmed requests and lower-priority controls

| Request | Confirmed release | Assessment |
|---:|---|---|
| `29952` | One-page CIA “Fix Required” letter | The title matches the CIA vaccination-policy gap, but the request is abandoned and the only file is administrative, not responsive evidence. |
| `77302` | Seven files, including two ICE delivery ZIPs and appeal material | The request sought Detention Standards Compliance Unit reports, but the visible file layer is dominated by appeals and a requester-supplied Novoa declaration. The final appeal affirmed the search; not ranked above the new working papers. |
| `127467` | 11 refs / 123 reported pages plus a final ZIP | CRCL Stewart oversight records, 2017–2021; CoreCivic peer/control, not GEO evidence. |
| `98784` | Six files including a responsive ZIP and a requester-supplied GEO contractor-status spreadsheet | Arizona ICE suicide SIR/SEN corpus. Relevant systemically; operator/facility attribution requires file review. |
| `192063` | One confirmed ZIP | IHSC Stewart 911 SIR/SEN records, 2024–2025; CoreCivic peer/control. |
| `192528` | Two confirmed ZIPs | FY2025 Narcan administration and positive-drug-test records by facility; systemic lead requiring facility/operator normalization. |
| `137286` | 12-page PDF plus two ZIPs | CoreCivic CDRs, a peer-contract consequence control rather than GEO evidence. |
| `140889` | One ZIP plus ten PDFs / 37 pages | Arizona ICE suicide-attempt SIRs, 2020–2023; facility/operator attribution needed. |
| `15922` | 16 refs / 1,576 reported pages | ICE Adelanto contract production. Substantive but overlaps existing Adelanto contracts and litigation exhibits. |
| `15925` | 8 refs / 609 reported pages | ICE Broward contract production. Useful base-contract corpus but lower novelty than the working papers. |
| `20086` | 24 refs / 427 reported pages | Vermont North Lake GEO proposal/contract material with pricing, personnel, operations plan, and compliance matrix; older and likely duplicative of project-era contract research. |

## Active Epstein/Gates/IPI gaps: bounded negative result

Ask-shaped and agency-filtered searches were run for CIA vaccination/genetic-material policy, Shakil Afridi, John Brennan calendars/visitor logs/correspondence, Lisa Monaco's May 16, 2014 public-health-deans letter, Kathryn Ruemmler/White House Counsel records, International Peace Institute / 777 UN Plaza / Terje Rod-Larsen correspondence, and Gates Foundation program/grant records.

Only `search=vaccination program` returned a result: request `29952`. The request was filed by productive requester `2116` with CIA tracking `F-2017-01331`, but it is abandoned and contains only a one-page “Fix Required” letter. All completed CIA/White House/NSC/State variants returned zero. This is a current MuckRock metadata negative, not proof that the records do not exist in MuckRock releases, DocumentCloud, or agency reading rooms.

## Exact new searches and counts

All entries below are in `search_history` under source `muckrock`.

### Requester portfolios, projects, and agency discovery

| Exact query | Count |
|---|---:|
| `user=19413` / `user=19413 status=done` | 56 / 38 |
| `user=106540` / `user=106540 status=done` | 2,423 / 1,378 |
| `user=10773` / `user=10773 status=done` | 119 / 45 |
| `user=62590` / `user=62590 status=done` | 8 / 1 |
| `user=25665` / `user=25665 status=done` | 503 / 121 |
| `user=2116` / `user=2116 status=done` | 5,455 / 2,409 |
| `user=2116 local title+requested_docs metadata scan epstein-gaps+geo-docclasses` | 104 |
| `user=19413 local title+requested_docs metadata scan epstein-gaps+geo-docclasses` | 1 |
| `user=10773 local title+requested_docs metadata scan epstein-gaps+geo-docclasses` | 1 |
| `user=62590 local title+requested_docs metadata scan epstein-gaps+geo-docclasses` | 0 |
| `projects title=Private Prison` / `project=8` | 1 project / 78 requests |
| `projects title=Immigration` / `project=145` | 1 project / 2 requests |
| `projects title=Detention` / `project=437` | 1 project / 178 requests |
| `projects title=Electronic Monitoring` | 0 |
| `projects title=GEO` | 0 |
| `projects title=Epstein` | 1 |
| `agencies name=Central Intelligence Agency` | 2 |
| `agencies name=White House` | 5 |
| `agencies name=National Security Council` | 1 |
| `agencies name=Department of State` | 33 |
| `agencies name=Bill and Melinda Gates Foundation` | 0 |

### Epstein/Gates/IPI ask-shaped searches

| Exact query | Count |
|---|---:|
| `search=vaccination program` | 1 |
| `search=vaccine program` | 0 |
| `search=vaccination policy genetic material` | 0 |
| `search=genetic material vaccination` | 0 |
| `search=Shakil Afridi` | 0 |
| `search=Brennan calendars` | 0 |
| `search=John Brennan calendar` | 0 |
| `search=John Brennan visitor logs` | 0 |
| `search=John Brennan correspondence` | 0 |
| `search=Monaco public health deans` | 0 |
| `search=Lisa Monaco public health` | 0 |
| `search=Lisa Monaco May 16 2014` | 0 |
| `search=Ruemmler White House Counsel` | 0 |
| `search=Kathryn Ruemmler correspondence` | 0 |
| `search=International Peace Institute correspondence` | 0 |
| `search=777 United Nations Plaza` | 0 |
| `search=Terje Rod-Larsen correspondence` | 0 |
| `search=Gates Foundation grant records` | 0 |
| `search=Gates Foundation program records` | 0 |

Agency/status variants all returned zero: `agency=6 status=done search=` plus each of `vaccination`, `vaccine`, `genetic`, `Afridi`, and `Brennan`; `agency=234 status=done search=` plus each of `Brennan`, `calendar`, `visitor logs`, `Monaco`, and `Ruemmler`; `agency=36586 status=done search=` plus `Brennan`, `calendar`, and `visitor logs`; and `agency=14 status=done search=` plus `International Peace Institute`, `Rod-Larsen`, `777 UN Plaza`, and `Gates Foundation`.

### ICE document classes, tags, jurisdiction, identifiers, and monitor

| Exact query | Count |
|---|---:|
| `agency=133 status=done search=Contract Discrepancy` | 1 |
| `agency=133 status=done search=Corrective Action` | 0 |
| `agency=133 status=done search=Mortality Review` | 4 |
| `agency=133 status=done search=annual inspection` | 0 |
| `agency=133 status=done search=medical care` | 0 |
| `agency=133 status=done search=staffing plan` | 0 |
| `agency=133 status=done search=invoice withholding` | 0 |
| `agency=133 status=done search=quality assurance surveillance` | 0 |
| `agency=133 status=done search=use of force` | 2 |
| `agency=133 status=done search=sexual abuse` | 1 |
| `agency=133 status=done search=grievance` | 0 |
| `agency=133 status=done search=Folkston` | 0 |
| `agency=133 status=done search=Northwest ICE Processing Center` | 0 |
| `tags=private prisons` | 18 |
| `tags=mortality reviews` | 17 |
| `tags=death in custody` | 35 |
| `tags=geo group` | 63 |
| `tags=electronic monitoring` | 1 |
| `tags=bi incorporated` | 1 |
| `jurisdiction=10 status=done ordering=-datetime_done search=GEO Group` | 11 |
| `jurisdiction=10 status=done ordering=-datetime_done search=mortality review` | 4 |
| `jurisdiction=10 status=done ordering=-datetime_done search=contract discrepancy` | 1 |
| `jurisdiction=10 status=done ordering=-datetime_done search=corrective action` | 0 |
| `jurisdiction=10 status=done ordering=-datetime_done search=Folkston` | 0 |
| `jurisdiction=10 status=done ordering=-datetime_done search=Northwest ICE Processing Center` | 0 |
| `agency=133 status=done ordering=-datetime_done` | 240 |
| `search=EROIGSA-17-0002` | 0 |
| `search=70CDCR contract discrepancy` | 0 |
| `search=ICFO Contract Discrepancy Report` | 0 |

The exact probes `tracking_id=2022-IGFO-00222`, `tracking_id=2023-ICAP-00260`, and `tracking_id=2020-ICFO-64605` each returned the full 119,705-request universe rather than a filtered result. They are logged with that count as negative controls: the API silently ignores `tracking_id=`. Search tracking IDs through titles/requester portfolios or retrieve the known request directly; do not trust this filter.

## Negative controls and limitations

- `status=done` still does not imply a responsive release; `29952` demonstrates the inverse pattern too—a file may exist while being only an administrative “fix required” letter.
- `ordering=-datetime_done` puts requests with null completion dates before dated rows in the observed ICE result. It remains useful after skipping nulls, but it is not a clean “newest release first” feed by itself.
- The `tracking_id=` filter is silently ignored and returns the full request universe.
- Exact contract identifiers such as `EROIGSA-17-0002` are usually absent from request titles even when the contract appears inside the release.
- Projects and tags are curated but sparse. Project 8 and user `2116` largely reproduce older private-prison contract work; project membership is not evidence of responsiveness.
- Request `136588` includes GEO and CoreCivic material. Same-origin copies, repeated appeal productions, and mirrors must be deduplicated rather than counted as corroboration.
- Request `137245` reports aggregate corrective-action counts only. The table does not establish severity, substantiation, completion, recurrence, or a financial remedy.
- Request `20845` contains grievance descriptions, which record complaints and routing—not findings that the complaints were true.
- No allegations in request descriptions were promoted. Only request `137245` page 1 and a representative structural page of request `20845` received visual review in this wave.

## Next processing order

1. **Request `131234`, 322-page final production:** use the public delivery-message password transiently; start with pages 48, 122, 259, 276–279, and 307–310, then review surrounding document boundaries. This is the best chance to close the existing Folkston penalty/non-enforcement/closure-support gap without OCR.
2. **Request `136588`, newest/final-first:** acquire the February 2025 archives first, inventory contents, then work backward only as needed. Hash-deduplicate all 26 ZIP payloads before OCR. Separate GEO/Aurora from CoreCivic/Torrance at document level.
3. **Request `131234`, 3,866-page interim production:** build chunked OCR sidecars without altering the 716 MB original. Search for the same penalty, invoice, waiver, staffing, overtime, closeout, and correspondence terms. Track the 1,066-page ICE referral as absent, not negative evidence.
4. **Request `20845`:** run handwriting-aware OCR or manual transcription, normalize categories and months, and sample every page visually. Preserve complaint/substantiation boundaries.
5. **Request `137245`:** if imported, use only the qualified aggregate-count paraphrase above and link it to existing Tacoma oversight chronology without inferring severity or outcome.
6. **Lower-priority peer/systemic controls:** `192063`, `192528`, `137286`, `140889`, `127467`, and `98784` after the directly profile-scoped material.

No FOIA request was filed, and no commit or push was performed.
