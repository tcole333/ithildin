# GEO–CBP direct-award forensics and Val Verde public-prime routing

**As of:** 2026-07-13  
**Profile:** `geo-group`  
**Lead:** `#60575`  
**Scope:** all ten verified direct GEO-CBP awards in the DHS-wide award-action export, plus the Val Verde County public-prime chain and related USMS intergovernmental agreements (IGAs).

## Bottom line

The ten direct GEO-CBP PIIDs are not ten independent detention relationships. They reduce to **five physical detention-facility chains**—East Hidalgo, Coastal Bend, Brooks County, Maverick County, and Val Verde—plus one RGV hygiene-service chain that does not purchase detention space. Seven PIIDs belong to a single evolving RGV procurement family, but that family uses three distinct facilities and three distinct USMS IGAs. The correct presentation therefore needs three denominators: **ten direct awards, fewer procurement families, and five physical detention-facility chains**.

The Val Verde evidence now supports a **seventh comparable public-prime/private-operator DHS chain outside ICE** in the broader investigation. CBP first contracted directly with GEO under `70B03C25P00000029`, then deobligated the award and told the record to replace it with `03C25P0150`. Award `70B03C25P00000150` starts the same day and names the County of Val Verde. Official county records show the same CBP detention requirement historically riding USMS IGA `80-98-0061`, while a county operating agreement says GEO operates the facility, invoices the county monthly, and receives the remittance. GEO's current site and 2025 10-K continue to identify the facility as GEO-managed/owned under the USMS-IGA structure.

That supports the routing conclusion at **medium confidence as a synthesis**, consistent with the methodology confidence cap. It does not establish the current county-to-GEO per-diem rate, fee split, invoice amount, or actual payment total. Those records remain missing.

The machine-readable outputs are:

- [`2026-07-13-cbp-geo-direct-award-crosswalk.csv`](2026-07-13-cbp-geo-direct-award-crosswalk.csv)
- [`2026-07-13-cbp-geo-contract-chain-analysis.json`](2026-07-13-cbp-geo-contract-chain-analysis.json)

## Money definitions and aggregate bounds

Across the ten unique direct GEO-CBP awards, USAspending currently reports:

| Measure | Amount | Meaning |
|---|---:|---|
| Net obligations | **$3,129,104.54** | Award-level federal commitments after deobligations; not cash payments |
| Base plus exercised options | **$3,139,104.54** | Current exercised award value; differs from obligations because the hygiene award was partly deobligated |
| Base plus all options / potential value | **$4,001,324.35** | Ceiling-like potential value; not obligated or paid |
| Disclosed outlays on four awards | **$667,277.41** | Incomplete subset only; six older awards have null outlay fields |

The sum must not be described as revenue, invoices, or money received by GEO. USAspending obligation fields track federal commitments. Its outlay coverage is incomplete for this cohort, and the county-to-GEO payment layer is not captured as a federal subaward.

USAspending award details report `subaward_count = 0` for all ten direct awards and for current County prime `70B03C25P00000150`. That is not proof that GEO receives no downstream county payments: the county records show an operating-agreement remittance mechanism, not a federally reported subcontract.

## Ten-award crosswalk

| PIID | Current net obligation | Facility/chain determination | Continuity and evidence |
|---|---:|---|---|
| `HSBP1012C00101` | $646,781.94 | Probable RGV multi-facility predecessor; exact allocation unresolved | P00006 records a novation. The [SEC asset-purchase schedule](https://www.sec.gov/Archives/edgar/data/923796/000119312515175072/d921856dex21.htm) identifies this PIID as an LCS-to-DHS-CBP “Novated Contract”; the acquisition includes LCS-Hidalgo, LCS-Nueces, and LCS-Brooks entities. That supports, but does not alone prove, the three-facility allocation. |
| `HSBP9861659693` | $16,401.28 | Probable RGV bridge; exact facility allocation unresolved | The award says it bought temporary jail space “pending new contract.” Its one-month period, 2016-04-01 through 2016-04-30, sits exactly between the prior award and `HSBP1016P00277`. The Lafayette place is treated as recipient/seller miscoding, not facility proof. |
| `HSBP1016P00277` | $833,449.72 | East Hidalgo plus Coastal Bend | La Villa maps to East Hidalgo. P00005 expressly adds Coastal Bend option-year funding. Other actions repeatedly call it RGV detention space. Brooks is not named in the available action text. |
| `70B03C20P00000219` | $585,781.54 | East Hidalgo, Coastal Bend, and Brooks County | P00002 expressly names all three facilities. The award was one-source/not competed, with one offer, under solicitation `70B03C20R00000062`; the [official SAM page](https://sam.gov/opp/056bdea3f8bc436a8c3a4b1a25176aae/view) survives, but no government files were recoverable in this pass. |
| `70B03C23P00000166` | $142,298.68 | East Hidalgo, medium-confidence synthesis mapping | The description says jail space was issued against USMS IGA per-diem rates; Hidalgo place and P00003's “CBA UPDATE-HIDALGO” connect it to the East Hidalgo chain. |
| `70B03C24C00000054` | $857,297.98 | East Hidalgo, medium-confidence synthesis mapping | La Villa place matches the facility. The award is one-source/not competed; P00002 changes the daily rate, P00004 updates rates for CBAs, and P00006 exercises option year two. The numeric modified rates are not public in the action data. |
| `70B03C24P00000592` | $31,955.33 | East Hidalgo, medium-confidence synthesis mapping | Same La Villa location and overlap with the current East Hidalgo contract. The action describes “DETENTION SPACE-RATIFICATION”; the ratification determination and underlying invoices were not recovered. |
| `70B03C25P00000029` | $0 after deobligation | Val Verde | The direct GEO award performed in Del Rio/Val Verde. P00001 removed the full $9,899.85 and says “REPLACE WITH 03C25P0150.” |
| `HSBP1015P00762` | $2,711.07 | RGV hygiene service, no detention-facility chain | All descriptions concern detainee hygiene for RGV Border Patrol. It is excluded from the detention-space denominator. |
| `HSBP1016J00076` | $12,427.00 | Maverick County Detention Facility, medium-confidence synthesis | The GEO BPA call performs at Eagle Pass/Maverick under parent BPA `HSBP1012A00025`, whose purpose is detainee housing/lodging. The [official USMS IGA](https://www.usmarshals.gov/sites/default/files/media/document/IGA-Texas-Maverick-County-Tom-Bowles-Detention-Center.pdf) adds the Maverick County Detention Facility at Eagle Pass. The call's available text does not name the facility, so the mapping remains a medium-confidence synthesis rather than a confirmed facility join. |

### RGV continuity and the independence denominator

The RGV timeline is:

```text
HSBP1012C00101 (LCS → GEO novation; exact facility allocation incomplete)
  → HSBP9861659693 (one-month “pending new contract” bridge)
  → HSBP1016P00277 (RGV; East Hidalgo + Coastal Bend evidenced)
  → 70B03C20P00000219 (East Hidalgo + Coastal Bend + Brooks expressly named)
  → 70B03C23P00000166 (East-Hidalgo-focused)
  → 70B03C24C00000054 (current East-Hidalgo-focused follow-on)
      ↘ 70B03C24P00000592 (short ratification action)
```

This is one procurement-continuity family, not seven independent awards. It nevertheless contains three independently identifiable facility/IGA chains:

| Facility | USMS IGA | Official IGA snapshot | CBP-rate caveat |
|---|---|---|---|
| East Hidalgo Detention Center | `79-12-0015` | $59.26 bed-day; $22.58 guard/transport hour; 1,346 federal beds; signed 2012-07-24 | Base IGA snapshot, not current CBP rate |
| Coastal Bend Detention Center | `79-12-0013` | $66.56 bed-day; $26.00 guard/transport hour; 1,120 federal beds; signed 2012-07-24 | Base IGA snapshot, not current CBP rate |
| Brooks County Detention Center | `79-07-0006` | $63.00 bed-day; $20.81 guard/transport hour; 500 federal beds | Signature date is illegible in the retrieved copy; not current CBP rate |

Official IGA copies: [East Hidalgo](https://www.usmarshals.gov/sites/default/files/media/document/IGA-Texas-East-Hidalgo-Detention-Center.pdf), [Coastal Bend](https://www.usmarshals.gov/sites/default/files/media/document/IGA-Texas-Coastal-Bend-Detention-Center.pdf), and [Brooks County](https://www.usmarshals.gov/sites/default/files/media/document/IGA-Texas-Brooks-County-Detention-Center.pdf). Each requires monthly, itemized invoices to the responsible federal component. That tells us the billing mechanism, but no retrieved invoice ties bed-days to the federal obligation records.

## Val Verde: direct GEO award to county prime

### 1. Same-day recipient-structure change

USAspending records two actions on direct GEO award `70B03C25P00000029`:

- Base action: **+$9,899.85** for detention space in Del Rio.
- P00001 on 2025-03-21: **−$9,899.85**, with the instruction to replace it with `03C25P0150`.

County-prime award `70B03C25P00000150` begins on **2025-03-21**, names the County of Val Verde, and performs detention space in the same city/county. As of the cutoff it has:

| Measure | Value |
|---|---:|
| Net obligation | $11,566.86 |
| Outlay | $3,154.37 |
| Potential value | $49,911.25 |
| Current end | 2027-02-28 |
| Potential end | 2030-02-28 |
| Competition | Not competed; one offer |

Its action history consists of a +$9,982.25 base obligation, a zero-dollar CBA-rate change, +$9,982.25 for option year one, and −$8,397.64 of excess-fund deobligation. Those are obligations and administrative changes, not county-to-GEO payments.

### 2. Historical CBP order and USMS rider

The official [Val Verde County July 11, 2016 commissioners-court package](https://www.valverdecounty.texas.gov/DocumentCenter/View/1718/16-July-11-2016-Commissioners-Court-Regular-Meetingpdf) contains CBP award `HSBP1016P00342` and its statement of work:

- PDF p.21 identifies the contractor as Val Verde Correctional Facility and references IGA `80-98-0061`.
- PDF p.22 states pricing is based on IGA modification 3: **$56 per bed-day** and **$18.75 per guard hour**.
- PDF pp.25–27 show an initial $37,303.32 plus $50,000, for a documented funded ceiling of **$87,303.32**.
- PDF p.27 schedules 357 bed-days, 450 guard hours for two guards, and 808 miles at $0.54.
- PDF p.48 says CBP detention at the Val Verde County Correctional Facility is a rider on the USMS IGA.

The $87,303.32 is a funded ceiling in the order package. USAspending later records a final net obligation of **$41,281.58** after deobligation, and its outlay field is null. Neither number is a proven county-to-GEO payment.

The [official USMS IGA copy](https://www.usmarshals.gov/sites/default/files/media/document/IGA-Texas-Val-Verde-Correctional-Facility.pdf) independently identifies Val Verde Correctional Facility, IGA `80-98-0061`, a $56 per diem, an $18.75 guard/transport rate, and 1,516 estimated federal beds. It requires the local government to submit monthly invoices separately to responsible federal components.

### 3. County-to-GEO operating and payment mechanism

The official [Val Verde County November 9, 2015 commissioners-court package](https://www.valverdecounty.texas.gov/DocumentCenter/View/1320/31-November-09-2015-Commissioners-Court-Regular-Meetingpdf), PDF p.82 / volume p.465, states:

- the Val Verde Correctional Facility is operated by The GEO Group;
- the contractor bills $56 per man-day and $18.75 per guard hour;
- GEO submits an itemized invoice monthly in arrears;
- the county pays within 30 days and remits payment to GEO;
- the six-month primary term is renewable at negotiated rates.

The public file contains banking instructions. They were intentionally excluded from this report and from database findings because they are unnecessary to the procurement conclusion.

Current corporate evidence closes the facility-identity gap:

- GEO's [current Val Verde facility page](https://www.geogroup.com/facilities/val-verde-county-detention-facility/) says GEO was selected to design, build, finance, and manage the Del Rio facility and lists a 1,407 capacity.
- GEO's 2025 10-K lists the 1,407-bed Val Verde County Detention Facility as owned, with USMS-IGA as primary customer and a perpetual base period (already captured in finding `#12695`).

Taken together, the records support this route:

```text
CBP obligation / order
  → County of Val Verde as federal prime
    → Val Verde County Detention Facility under USMS IGA 80-98-0061
      → GEO as facility owner/operator and county invoice payee
```

What remains unproved is the **current** downstream economics. The 2015 agreement is historical, and no current county-GEO agreement or invoice has been recovered. The route is supported at medium confidence as a synthesis; the current rate, remittance amount, management fee, and margin are unresolved.

### 4. County-prime history

USAspending's County of Val Verde DHS transaction history contains nine nonzero CBP award chains from 2016 through the current award. Current net obligations across those unique county-prime awards total **$894,078.11**. This is again an obligation total, not an outlay or GEO revenue total.

The strongest continuity descriptions include:

- `70B03C22P00000141`: detention, food, and linens using the Marshals contract.
- `70B03C23P00000211`: detention, guards, meals, and laundry under IGA `80-98-0061`.
- `70B03C25P00000150`: current detention-space award following the direct-GEO replacement.

The historical chain demonstrates that the county-prime mechanism is recurring, not a one-off 2025 anomaly.

## Maverick chain

`HSBP1016J00076` is the only one of the ten direct awards that is a BPA call. USAspending ties it to GEO parent BPA `HSBP1012A00025`; HigherGov describes the BPA as “HOUSING AND LODGING OF DETAINEES.” The call performs at Eagle Pass in Maverick County, and its final modification expressly says detention space.

The [official USMS IGA `80-99-0219`](https://www.usmarshals.gov/sites/default/files/media/document/IGA-Texas-Maverick-County-Tom-Bowles-Detention-Center.pdf) adds the Maverick County Detention Facility at 742 Highway 131, Eagle Pass, facility code `6R7`, at a 2008 per diem of $52.50. Time-bounded SEC filings show GEO held a managed-only contract through November 1, 2013, terminated it on that date, and acquired the then-idle facility on March 6, 2017 for approximately $15 million. The combined record maps the 2016 CBP call to the Maverick facility only as a medium-confidence synthesis and does **not** prove that GEO operated or owned the facility when the call performed. The missing call package prevents a confirmed direct quote of the facility name, a verified 2016 rate, or resolution of GEO's 2016 service role.

## Competition, modifications, and missing packages

Nine of the ten direct awards were noncompetitive in USAspending's coded fields; `HSBP1016J00076` was competed under simplified acquisition procedures, still with one recorded offer. `70B03C20P00000219`, `70B03C23P00000166`, `70B03C24C00000054`, and `70B03C25P00000029` are one-source/not-competed awards with one offer. `HSBP1016P00277` and `70B03C24P00000592` are not competed under simplified acquisition procedures.

Recovered primary records:

- full USAspending award details and action histories for all ten PIIDs;
- HigherGov cross-checks for nine awards and the GEO BPA; HigherGov did not return the BPA call itself;
- official USMS IGA copies for East Hidalgo, Coastal Bend, Brooks, Maverick, and Val Verde;
- official Val Verde 2016 CBP order/SOW/rate package;
- official Val Verde 2015 county-GEO operating/billing agreement;
- official SEC novation/acquisition exhibit for the LCS predecessor;
- official SAM opportunity page identifier for `70B03C20R00000062`.

Not recovered:

- the promised J&A for `70B03C20R00000062`;
- original SOWs, CLIN schedules, and price sheets for the other direct awards;
- numeric rate changes incorporated through USMS IGA or collective bargaining updates;
- ratification determination and invoices for `70B03C24P00000592`;
- bed-day guarantees, utilization records, or invoices for the RGV facilities;
- the 2016 Maverick call package and rate;
- current County of Val Verde–GEO agreement, invoice, remittance, fee, and margin records;
- current solicitation/J&A package explaining the direct-GEO-to-county-prime replacement.

No live SAM API request was made. The repaired local SAM/Federal Procurement Data output, the public opportunity page, and previously retrieved award data were used to preserve quota.

## Tier 2 recommendation

A targeted Tier 2 rerun is justified. It should not be a simple rerun of the GEO-recipient query. It should:

1. Build a facility table from USMS IGA names, codes, addresses, and authorized agency users.
2. Search CBP and other DHS awards to counties, municipalities, authorities, and facility-named recipients.
3. Join those public primes to private operators and owners through SEC filings, county agreements, and current operator facility pages.
4. Link predecessor/successor PIIDs across same-day recipient changes and “replace with” modification text.
5. Report awards, procurement families, and physical facilities as separate denominators.

Val Verde is the proof of concept: a direct GEO award disappears and is replaced by a County prime, while the same GEO-owned/managed facility and USMS-IGA structure remain in place. A recipient-only screen would count the predecessor but miss the active relationship.

## Evidence cautions

- USAspending obligations are commitments, not invoices or cash receipts.
- Base/all-options values are ceilings or potential values, not obligations.
- A zero-dollar modification can change rates, terms, or facility allocation without changing the net obligation on that action.
- Three databases reproducing the same federal award record are redundancy, not corroboration.
- The original USMS IGA rates are historical snapshots; later CBP modifications explicitly updated rates.
- Facility mappings marked “probable” or “high” are syntheses and are not promoted to confirmed facts.
