# Track C — Boston property and municipal records, 2026-09-04

Initial verified map: 26 FY2026 Boston assessment records match identified vehicles or the named Hicham trust. These are administrative assessment-owner observations, not legal title opinions or estimates of family wealth. Three of the Houssam-linked records are parking units. Another 17 records are preserved separately as historical assets, condominium masters, or attribution candidates. Neither family shares nor beneficial ownership follow from a manager name.

The main deliverables are `investigations/hassan-boston/evidence/properties/parcel-inventory-fy2026.csv` (43 current parcel observations with classification), `assessment-observations.csv` (147 selected dated observations), `assessment-observations.json` (including exact raw rows), `permit-observations.json` (200 focused municipal observations), and `finding-manifest.json` (26 findings, IDs 15543–15568). `citation-map.json` maps every finding evidence reference to a canonical source URL.

## Current core property map

All values below are FY2026 assessed values from the [official Boston roll](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv); they are not transaction consideration, equity, outstanding debt or a current market valuation. Read corporate control alongside Track B, independently of the assessor labels.

### Boylston / Newbury / Brimmer vehicle cluster

| Assessor situs | Parcel ID | Exact assessed owner | FY2026 assessed total | Finding |
|---|---|---|---:|---|
| 400 Boylston ST | 0501159000 | 392-402 BOYLSTON STREET REALTY LLC | $2,305,200 | 15554 |
| 396 Boylston ST | 0501160000 | 392-402 BOYLSTON STREET REALTY LLC | $1,816,000 | 15554 |
| 392 Boylston ST | 0501161000 | 392-402 BOYLSTON STREET REALTY LLC | $2,370,900 | 15554 |
| 384 Boylston ST | 0501162000 | 384 BOYLSTON STREET  REALTY LLC | $4,668,000 | 15555 |
| 372 Boylston ST | 0501164000 | 376 BOYLSTON STREET REALTY  LLC | $8,636,200 | 15556 |
| 419 Boylston ST | 0501234000 | 419 BOYLSTON STREET REALTY LLC | $10,470,300 | 15558 |
| 18 Brimmer ST | 0502425000 | HASSAN RESIDENTIAL | $3,154,300 | 15559 |
| 33 Exeter ST | 0503202000 | 711 BOYLSTON STREET REALTY LLC | $20,688,100 | 15560 |
| 218 NEWBURY ST | 0503224000 | 216-218 NEWBURY STREET REALTY LLC | $5,019,894 | 15561 |
| 216 NEWBURY ST | 0503225000 | 216-218 NEWBURY STREET  REALTY LLC | $5,139,606 | 15561 |

These ten distinct parcels total **$64,268,500 in assessed value**. The 33 Exeter Street parcel carries the owner name 711 BOYLSTON STREET REALTY LLC; municipal permits on the same PID use 705–711 Boylston. Thus the store location now has a concrete parcel/vehicle pivot. Separate 216 and 218 Newbury parcels must both be retained: their combined assessment is $10,159,500.

An additional residential condominium record (PID 0501185054) names **400 BOYLSTON STREET REALTY TRUST**, with mail addressee **C/O HICHAM ALI HASSAN**, assessed at $2,518,700 (finding 15557). Exact unit/address is in the internal parcel inventory; the residential location need not be repeated in a public summary. The trust is spelled 400, whereas the litigation excerpt encountered in search uses 4000; the recorded instrument remains the authoritative resolution route.

### Houssam-associated vehicles

| Assessor situs / units | Parcel ID | Exact assessed owner | FY2026 assessed total | Finding |
|---|---|---|---:|---|
| 77 Montgomery ST | 0400327000 | 77 MONTGOMERY STREET LLC | $3,533,100 | 15548 |
| 201 W BROOKLINE ST / 203 | 0400450012 | 201 WEST BROOKLINE STREET UNIT 203 LLC | $4,528,000 | 15549 |
| 201 W BROOKLINE ST / PS-3 | 0400450021 | 201 WEST BROOKLINE STREET UNIT 203 LLC | $43,000 | 15549 |
| 201 W BROOKLINE ST / PS-4 | 0400450022 | 201 WEST BROOKLINE STREET UNIT 203 LLC | $43,000 | 15549 |
| 174 W Brookline ST | 0400530000 | 174 WEST BROOKLINE LLC | $2,068,900 | 15550 |
| 36 Holyoke ST | 0400735000 | 36 HOLYOKE TOWNHOUSE LLC | $3,537,600 | 15551 |
| 28 BRADDOCK PK | 0400779000 | 28 BRADDOCK TOWNHOUSE LLC | $3,790,700 | 15552 |
| 18 CLAREMONT PK / 1 | 0402517002 | 18 CLAREMONT PARK LLC | $4,210,800 | 15553 |
| 18 CLAREMONT PK / PS-1 | 0402517005 | 18 CLAREMONT PARK LLC | $37,100 | 15553 |
| 137 W Concord ST | 0900512000 | 137 WEST CONCORD LLC | $1,483,900 | 15562 |

These ten assessment records total $23,276,100, include three parking units and describe seven street properties. Track B finding 15534 supplies the exact corporate-role matches; this table does not infer ownership percentages or treat a signatory role as beneficial ownership.

### Tarek-associated vehicles

| Assessor situs | Parcel ID | Exact assessed owner | FY2026 assessed total | Finding |
|---|---|---|---:|---|
| 238 Lexington ST | 0103178000 | 238LS LLC | $975,400 | 15543 |
| 334 Meridian ST | 0103648004 | 334 MERIDIAN ST LLC | $1,196,200 | 15544 |
| 31 Havre ST | 0105622000 | 31 HAVRE ST LLC | $652,800 | 15545 |
| 18 Meridian ST | 0105676000 | MAVERICK SQUARE LLC | $1,798,900 | 15546 |
| 143 Meridian ST | 0105898000 | 143-145 MERIDIAN STREET LLC | $735,100 | 15547 |

These five records total $5,358,400 assessed. The matching person-to-vehicle registry roles are in Track B finding 15535. **Maverick Square LLC is not Maverick Square Properties LLC or Maverick Square Management LLC**: unrelated broader-search matches were excluded. A separate individual-name record at PID 0503608000 says HASSAN TAREK; the 384 Marlborough company provides a second contextual pivot, but individual-versus-LLC title and person identity remain explicitly unresolved in this table. An unrelated Tarek Alexander Hassan record was excluded.

## Historical ownership labels and current exclusions

- The [FY2008 roll](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv) and [FY2014 CSV](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv) both name **HASSAN ZOUHAIR A TS** at 18 Brimmer, **HASSAN ZOUHAIR A** at 419 Boylston, and **HASSAN ZOUHAIR ALI** at 216 and 218 Newbury. This is four distinct parcel IDs, observed in two snapshots (finding 15563). The current LLC labels are not enough to infer when interests moved or what Zouhair owned beneficially.

- FY2008 names ALI HASSAN HICHAM at the three 392–402 Boylston parcels and HASSAN HICHAM A at the 372–378 Boylston parcel. FY2014 also names HASSAN HICHAM ALI at 384–390 Boylston. The later snapshots place these PIDs under the related LLC labels.

- Houssam appears personally at Washington Street condo PID 0801499002 in FY2008 and Pembroke condo/parking PIDs 0400484002/0400484006 in FY2014. Different FY2026 names are recorded (finding 15564); these are historical observations, not current holdings.

- FY2021 labels at 81 Warren,149WNewton and126 Pembroke unit2 plus parking are Houssam-associated companies. FY2026 has different owner labels (finding 15565, synthesis/medium). Deeds must establish actual transfer dates and whether any economic interest was retained.

- Condominium masters at204WSpringfield,196WSpringfield,196WBrookline,126Pembroke,21Rutland,14Holyoke and31Dwight are separated from unit ownership. A zero or blank master assessment does not mean the building has no value or that the old developer still owns its units.

- The current source labels ONE121 PEMBROKE TOWNHOUSE and1200 WASHINGTON STREET are retained as name candidates, not silently treated as exact corporate matches.

## Current municipal developments

**419 Boylston:** [Board Approved Document 8308, May14,2026](https://bpda.box.com/s/2xynvi7uzas3muawzc3u2091euhsylh8), pp.1–4, names419 Boylston Street Realty LLC as proponent and authorizes a **41-unit** office conversion, including 7 income-restricted units, with a development-cost estimate of **$7,761,888**. It records an August29,2025 PILOT-program application. The approved memorandum authorizes approval and PILOT-related agreements; it does not prove execution of the final PILOT agreement, construction completion or loan funding (finding 15566). The [project webpage](https://www.bostonplans.org/projects/development-projects/419-boylston-street) still describes44 units; use the dated approved41-unit version. Full PDF, text and a visually inspected first-page render are archived.

**Demolition permits:** The [official approved-building-permit dataset](https://data.boston.gov/dataset/approved-building-permits/resource/6ddcd912-32a0-43df-9908-63574f8c7e77) records the following (finding 15567):

| Permit | Address | Issued | Applicant | Recorded status | Declared work valuation |
|---|---|---|---|---|---:|
| SF1742941 |396 Boylston|2025-10-10|Carlos Ferreira|Open|$100,000|
| SF1805998 |384–390 Boylston|2026-02-11|Carlos Ferreira|Open|$200,000|
| SF1790036 |400–402 Boylston|2026-02-18|Carlos Ferreira|Open|$100,000|

All three have worktype RAZE and describe demolition. Issuance and Open status are not evidence that demolition occurred. Declared valuations are proposed work amounts, not audited spending.

**Permit identity pivots:** Official records name Houssam Hassan at 142WConcord (ALT257044) and 196WSpringfield (COO764998), **Houssan Ali Hassan** at 21Rutland (COO935794), and Tarek Hassan at 216–218Newbury (ALT78137/COO70362). Applicant capacity does not establish title (finding 15568). “Sam Hassan” also appears across Houssam-associated South End properties, so the alias must not automatically be assigned to Hicham in permit data.

## All-person coverage and limitations

| Person | Result in this track |
|---|---|
| Hicham Ali Hassan | Historical named owners, current trust c/o exact full name, and current commercial/property vehicles; title/beneficiary share requires TrackD. |
| Zouhair Ali Hassan | Four named historical parcel observations across FY2008/FY2014; current property labels differ. |
| Houssam Ali Hassan | Current vehicle matches, named historical records, municipal permit trail, and former-asset/condominium-master separation. |
| Tarek Ali Hassan | Five exact vehicle assessment matches to registry roles, Newbury permit-name pivots, and one unresolved individual-name parcel. |
| Talal Ali Hassan | No identity-resolved direct assessor result in the reviewed Boston snapshots or Cambridge extract; York Outfitters/Trend Boston produced no Cambridge owner result. This is not an absence-of-property conclusion. TrackD has a recent candidate deed. |
| Abdul Rahman Ali Hassan | No identity-resolved direct assessor match from these surname/known-vehicle searches; no property holding assertion. Alternate names, trusts and holdings outside Boston remain uncovered. |

Boston snapshots examined: FY2008,2014,2019,2021,2026. Search exact-owner and mail-addressee HASSAN, seed property addresses/PIDs, and documented corporate vehicles. This is not a full annual or historical title chain. The inventory separately lists earliest/latest examined snapshots and earliest/latest exact current-owner-label observations; neither means acquisition/disposition date.

The [Cambridge FY2016–FY2026 extract](https://data.cambridgema.gov/Assessing/Cambridge-Property-Database-FY2016-FY2026/eey2-rv59) returned 162 surname-containing owner/co-owner rows but no identity-resolved subject matches. The bounded retail-vehicle query returned 0. Cambridge itself directs users to the property database for official assessments. No ownership absence is inferred, and no adjacent jurisdiction is claimed searched.

Unified `query_property.py sources --jurisdiction 25` returned the MassGIS source; local owner/address queries were **unavailable**, not zero results. Search plan artifact is saved. Boston CKAN public data/municipal pages supplied the working routes. Old assessor individual URLs redirect to a new SPA and supplied no deed-book reference in this pass. No title instrument, deed consideration or outstanding loan balance was inferred from assessment data.

## Follow-up priorities

1. Trace recorded deeds and trust instruments for the four Zouhair-labeled parcels through later LLC labels; verify beneficiaries, trustee changes and transfer consideration.

2. Complete the 392/396/400,384,372/376,419 and33Exeter/711 parcel chains using the exact PIDs and vehicle spellings.

3. For Houssam companies, join condominium master deeds to retained/sold unit schedules; master-record labels cannot resolve current holdings. Prioritize201WBrookline,18Claremont and historical126Pembroke/81Warren/149WNewton.

4. Retrieve the executed419Boylston PILOT agreement and financing documents; board authorization alone is not a funded transaction. Verify actual demolition status through subsequent inspections/completion records.

5. Resolve Talal’s recent candidate deed and Abdul Rahman’s alternate names/jurisdictions before extending the portfolio.

## Learnings

- FY2014 Boston CKAN datastore has a schema but **zero underlying records**, while its publishedCSV has data. Downloading and reading the CSV recovered the exact historical owners. Logged papercut#2671; no tool change. Preserve raw underscore-suffixedPID while normalizing a separate join field.

- Published Boston snapshots vary field names and street ranges; schema inspection prevented false joins.33Exeter/711Boylston illustrates why exact property vehicles and parcel IDs are needed alongside addresses.

- Parent/condominium-master rows and parking units can inflate a portfolio count. Preserve classifications and separate them before summing.

- `findings_tracker correct --field target_name` left stale canonical subject links. Logged#2675, reconciled the two affected finding links (15567/15568), and marked the two newly created aggregate label nodes7237/7238 as `non_entity_label`. No general tool fix was attempted.

- Use exact entity names when persisting property findings to avoid pseudo-entity group labels. Finding15565 is synthesis/medium; remaining property findings are paraphrase/high with quotes. No conclusions about illicit funds, kinship or personal net worth are supported by this track.
