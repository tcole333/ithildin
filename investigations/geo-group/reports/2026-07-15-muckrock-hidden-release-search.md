# MuckRock hidden-release and OCR search

**Research date:** 2026-07-15  
**Profile used for imports:** `geo-group`  
**Companion report:** `2026-07-15-muckrock-cross-investigation-sweep.md`  
**Result:** 13 verified findings from requester, delivery-message, archive, OCR, and MuckRock-to-DocumentCloud pivots

## Outcome

This pass tested ways to search MuckRock when the released files themselves have no usable OCR. The most productive approach was to treat a MuckRock request as a layered record rather than a document-search result:

1. search request titles and descriptions;
2. pivot through a productive requester and agency;
3. enumerate every communication and file attachment;
4. read public delivery-message bodies for archive or PDF passwords;
5. unpack nested ZIP/PDF layers;
6. build temporary local OCR sidecars;
7. search the sidecars by document class and regulatory language;
8. use DocumentCloud only for documents whose metadata links them back to MuckRock.

That method recovered two signed EPA Notices of Warning that were invisible to native PDF text search. It also unlocked a previously blocked 191-page ICE/Stewart healthcare production and surfaced its staffing-enforcement terms.

The pass created findings `13534`–`13542`, `13575`, `13590`, `13591`, and `13637`. All received quote-level and visual page review and are marked verified. Finding `13591`, based on the signed EPA notice, supersedes the earlier inspection-report characterization in `13534`. Finding `13590`, the underlying signed Tacoma notice, corroborates GEO's response in `13575`.

## What the new search layers found

### Requester pivot

MuckRock requester `25665` has 503 requests, with a dense concentration of ICE detention inspections, mortality reviews, contract-discrepancy reports, requests for equitable adjustment, intergovernmental service agreements, and medical-service records. Searching and ranking that request corpus produced 163 detention-related candidates. This was substantially more productive than repeating company-name searches because many useful request titles name a facility, report type, or FOIA tracking number but not GEO or BI Incorporated.

### MuckRock-to-DocumentCloud OCR pivot

The search reconstructed 116 anchor terms from the investigation database and prior MuckRock searches, then issued DocumentCloud queries restricted to documents carrying MuckRock request metadata:

```text
+data__mr_request:* +text:"TERM"
```

Forty-three terms produced at least one hit. Most broad-name hits were incidental, but the method identified useful BI Incorporated contracts and helped prioritize which MuckRock requests deserved full expansion. Exact queries and counts are stored in `search_log` and `search_history` under `documentcloud`.

### Public delivery-message pivot

ICE often delivered a password-protected ZIP or PDF in one communication and the password in a separate public communication. The normalized `query_muckrock.py request` output currently lists communication metadata and files but omits message bodies, so this pass read the authenticated communication object's public `communication` field programmatically. Passwords were used locally without printing or persisting them in this report.

This unlocked:

- request `72956`, a 38-page ICE contract-discrepancy/REA production;
- request `117845`, a 117-page compilation of ICE ODO annual inspection reports; and
- request `72901`, a 191-page Stewart Detention Center healthcare production that had remained encrypted in the prior sweep.

The omission of message bodies from normalized request output remains papercut `1272`. Transient 503 responses during concurrent request expansion remain papercut `1301`.

### Local OCR pivot

Request `137546` contained 32 delivered files, including seven ZIP archives. After deduplication by extracted filename, it yielded 295 unique PDFs and 1,070 pages. Native text was effectively absent from 265 PDFs covering 762 pages. Temporary OCR added approximately 930,000 searchable characters and recovered:

- EPA Region 10's signed July 6, 2021 Tacoma/NWIPC FIFRA Notice of Warning; and
- EPA Region IX's signed March 2, 2021 Adelanto FIFRA Notice of Warning.

The unlocked Stewart production in request `72901` was a second-layer example: the 191-page PDF decrypted successfully but contained only page images. OCR produced approximately 387,000 searchable characters and exposed contract modification `DROIGSA-06-00005/P00032` at pages 102–105.

## Strongest primary-source findings

### 1. EPA formally found a FIFRA violation at GEO's Tacoma facility

EPA Region 10's signed July 6, 2021 Notice of Warning states that GEO was in violation of FIFRA at the Northwest ICE Processing Center because GS Neutral and Sani-T-10 Plus were applied inconsistently with their labels and required PPE was not made available. EPA's sanitation records indicated as many as 48 separate pesticide applications per housing unit per day. The letter also cited multiple detainees reporting sore throats and headaches and warned that later violations could carry penalties up to `$20,528` per violative act.

- Finding: `13590` (`direct_quote`, `confirmed`, verified)
- Evidence: `MUCKROCK:137546:ED_014093C_00004480:p1` and `p2`
- Release: `datasets/muckrock/137546/`

GEO's July 28 response disputed reuse of contaminated clothing and said it could not substantiate reported medical claims. It nevertheless committed to provide reusable or disposable gowns and to relocate nearby detainees for at least ten minutes during disinfectant application.

- Finding: `13575` (`paraphrase`, `high`, verified)
- Evidence: `MUCKROCK:137546:2021_07_28_GEO_Response:p1` and `p2`

### 2. EPA's Adelanto warning identified multiple label-inconsistent practices

EPA Region IX's signed March 2, 2021 Notice of Warning says its Adelanto investigation uncovered multiple FIFRA violations. It lists application at twice the label's disinfection concentration; optional goggles and gloves; spray exposure affecting detainees and food; application to bedding; mixing HDQ Neutral with Clean by Peroxy, shampoo, and toothpaste; and spraying inside microwaves without the required rinse. EPA stated that each listed activity constituted use inconsistent with labeling.

- Finding: `13591` (`direct_quote`, `confirmed`, verified)
- Evidence: `MUCKROCK:137546:ED_014093C_00003077:p1`–`p3`
- Relation: supersedes inspection-report finding `13534`

The underlying EPA inspection materials add two useful facts. GEO denied the California Department of Pesticide Regulation access, causing the state agency to refer the inspection to EPA; and Adelanto's response said 11 detainees attended sick call alleging exposure symptoms and five filed internal grievances, while emphasizing that causation had not been established.

- Findings: `13535` and `13536` (`paraphrase`, `high`, verified)
- Evidence: request `137244`

### 3. ICE documented medical and suicide-prevention contract failures

The password-protected release in request `72956` contained 2018 Adelanto and 2015 Mesa Verde contract-discrepancy records.

At Adelanto, ICE Health Service Corps identified serious noncompliance with accepted medical practice and PBNDS standards. Every sampled psychiatric medication administration record and 60% of sampled general-medical records contained discontinued orders.

- Finding: `13537` (`paraphrase`, `high`, verified)
- Evidence: `MUCKROCK:72956:2019-ICFO-38991:p32`–`p36`

At Mesa Verde, all licensed-clinical-social-worker positions had been vacant for more than 120 days, GEO had submitted no candidates, and ICE said the facility appeared not to meet the PBNDS suicide-prevention standard. ICE threatened a 15% invoice withholding if corrective action was not implemented.

- Finding: `13542` (`paraphrase`, `high`, verified)
- Evidence: `MUCKROCK:72956:2019-ICFO-38991:p37`–`p38`

### 4. ICE's mortality review directly attributed Jaspal Singh's death to unsafe care

The ICE Health Service Corps mortality review released in request `182995` states that care at Folkston Main ICE Processing Center deviated beyond safe limits and directly contributed to Jaspal Singh's April 2024 death. It describes failure to send him promptly to an emergency department despite symptoms and an abnormal EKG, plus triage by an LPN outside the applicable scope of practice.

- Finding: `13538` (`paraphrase`, `high`, verified)
- Evidence: `MUCKROCK:182995:Jaspal-Singh-Mortality-Review:p2` and `p8`

### 5. Electronic-monitoring contracts exposed pricing and surveillance functions

A 2019 Marin County contract made BI Incorporated's SmartLINK optional at `$1` per assigned day and described biometric facial-recognition check-ins, self-reporting, location sampling, and two-way video at `$3.75` per occurrence.

- Finding: `13539` (`paraphrase`, `high`, verified)
- Evidence: `MUCKROCK:126511:DOCUMENTCLOUD:21560815:p15`

An Illinois Department of Corrections amendment estimated `$23.4 million` for BI Day Reporting services across FY2019–FY2024, including `$4.68 million` in each of FY2020–FY2023.

- Finding: `13540` (`paraphrase`, `high`, verified)
- Evidence: `MUCKROCK:155395:DOCUMENTCLOUD:24213185:p100`

### 6. Local agreements and peer-contract controls

GEO's Pine Prairie agreement required a `$7,500` monthly administrative fee to the Village and was extended through June 30, 2025, subject to termination provisions tied to notice, the ICE arrangement, or the detainee population.

- Finding: `13541` (`paraphrase`, `high`, verified)
- Evidence: `MUCKROCK:133882:Pine-Prairie-agreement:p1` and `p4`

The newly unlocked Stewart production provides peer-comparison evidence. A September 2018 ICE/Stewart County bilateral modification identified CoreCivic as subcontractor, added medical services, required health-services staffing to remain at or above 90% of the approved plan, required monthly vacancy reporting, and allowed invoice deductions for positions vacant more than 120 days when total staffing fell below the floor. The document establishes contractual authority, not proof that ICE imposed a deduction.

- Finding: `13637` (`direct_quote`, `confirmed`, verified)
- Evidence: `MUCKROCK:72901:2019-ICFO-38345:p102`–`p104`

## Useful releases not promoted as new findings

| Request | Release | Assessment |
|---|---|---|
| `117845` | 117-page ICE ODO annual-report compilation, FY2018–FY2021 | Valuable systemic corpus. It contains annual deficiency and repeat-deficiency totals but was not imported because the aggregate is not GEO-specific and needs facility-level normalization. |
| `137546` | EPA Region 10 GEO/Tacoma production | In addition to the warning, contains the November 2020 EPA-GEO inspection interview, agency emails, product labels, sanitation materials, and GEO's response. The interview is strong supporting context but largely subsumed by the signed warning. |
| `72956` | ICE contract-discrepancy and REA material | Also includes ICE denials of GEO equitable-adjustment requests for Adelanto Novoa and Aurora Menocal; those matters were already represented in existing findings. |
| `137244` | 171-PDF EPA Region IX Adelanto production | Approximately 1.42 million native-text characters. The strongest new evidence was imported; remaining files include response exhibits and duplicated regulatory materials. |
| `72901` | 191-page ICE/Stewart healthcare production | Contains broad medical standards, formularies, audit templates, and staffing matrices. Only the executed modification and staffing enforcement language were promoted. |

## False positives and negative controls

- `N722JE` appeared in an Oregon attorney-general release only because a complaint repeated already-known aircraft language; it was not new evidence.
- `Coscolluela` appeared in an FAA remote-pilot name list without a basis to disambiguate the person.
- One `Andrew Tate` result concerned a different person, while another was only an external-news mention.
- Broad terms such as `GEO Group`, `immigration detention`, `Gates Foundation`, and `Jeffrey Epstein` frequently exhausted DocumentCloud's result cap and required exact metadata, identifier, or document-class constraints.
- Multiple MuckRock files or DocumentCloud mirrors containing the same agency production were treated as redundancy, not corroboration.
- A request description or requester allegation was never promoted without reviewing the released primary record.

## Recommended search workflow

The evidence supports using MuckRock and DocumentCloud together rather than choosing one.

1. **Start in MuckRock for discovery and provenance.** Search request descriptions, agencies, requester portfolios, tracking numbers, facility names, and document classes. MuckRock preserves the request/agency/communication/file chain and often hosts releases that never entered DocumentCloud.
2. **Use DocumentCloud as an OCR accelerator.** Restrict to MuckRock-linked documents with `data__mr_request:*`, then search text, pages, and extracted entities. A DocumentCloud hit should be traced back to its MuckRock request before citation.
3. **Search document classes, not only entities.** High-yield terms in this pass included `Notice of Warning`, `Contract Discrepancy Report`, `Mortality Review`, `Request for Equitable Adjustment`, `IGSA`, `modification`, `staffing plan`, `quality of medical care`, and FOIA tracking IDs such as `ICFO`/`ICAP`.
4. **Pivot through productive requesters and agencies.** Requester `25665` and ICE/EPA agency portfolios exposed records whose titles omitted GEO and BI Incorporated.
5. **Always enumerate communication bodies.** A delivered file can be inaccessible until a separate public message supplies its password or link. This should become a normalized field in `query_muckrock.py` after the relevant papercut is fixed.
6. **Create OCR sidecars without modifying evidence.** Preserve the original ZIP/PDF bytes; decrypt and OCR only temporary working copies. Record the original MuckRock request/file as the evidence reference and visually verify cited pages against the source rendering.
7. **Rank before OCR.** Prioritize image-only releases whose request descriptions, agencies, tracking IDs, file sizes, or neighboring communications indicate contracts, inspection reports, mortality reviews, or enforcement records.
8. **Log exact negative searches.** Request-level search, DocumentCloud metadata search, password-layer results, and OCR terms should have separate search-log entries so a zero at one layer is not mistaken for a true corpus-wide negative.

## Stored material and audit trail

Raw MuckRock deliveries are under:

- `datasets/muckrock/137244`
- `datasets/muckrock/137546`
- `datasets/muckrock/72956`
- `datasets/muckrock/72901`
- `datasets/muckrock/117845`
- `datasets/muckrock/182995`
- `datasets/muckrock/126511`
- `datasets/muckrock/155395`
- `datasets/muckrock/133882`

All temporary decrypted files, extracted ZIP contents, OCR sidecars, and page renders were kept outside the evidence directories. Exact DocumentCloud terms, requester/file pivots, hidden-release searches, and OCR passes were logged in `search_log`/`search_history`. The post-wave `auto_leads.py` pass for `geo-group` scanned 1,001 items and generated 70 profile-scoped follow-up leads from newly available entity, officer, connection, and coverage-gap data; these automated leads require normal triage and should not be read as 70 MuckRock discoveries.
