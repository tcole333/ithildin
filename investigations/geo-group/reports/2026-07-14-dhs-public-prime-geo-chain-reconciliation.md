# DHS public-prime / GEO-operator chain reconciliation

**Date:** 2026-07-14  
**Lead:** 60824  
**Profile:** `geo-group`  
**Scope:** Layer-1 search for DHS detention awards whose legal prime is a public body but whose physical facility was operated by The GEO Group, with emphasis on chains missed by recipient-name searches.

## Bottom line

The bounded search did **not add a new verified public-prime/private-GEO-operator chain**. It found one **probable historical CBP chain** at Maverick County that merits an original-award-package request:

`CBP -> County of Maverick (legal prime, HSBP1012P00868) -> probable Maverick County Detention Facility -> GEO (managed-only operator in 2012) -> Maverick County (owner in 2012)`

The award record says only **“DETENTION SPACE”**, identifies Eagle Pass/Maverick County as the place of performance, and overlaps GEO's documented managed-only period. It does not name the facility. That omission matters because USMS IGA `80-99-0219` covered both the Tom Bowles Detention Center and the separately added Maverick County Detention Facility in Eagle Pass. The chain is therefore a probable synthesis recorded at medium confidence, not a verified direct-document join.

The verified denominator remains:

- **7 verified DHS public-prime/private-GEO-operator chains**: six ICE chains plus the CBP Val Verde chain.
- **11 unique physical facilities** across the seven verified public-prime chains and four additional direct-GEO CBP comparator facilities.
- **1 additional probable public-prime award/procurement family** at Maverick, but **0 additional physical facilities**, because Maverick is already one of the direct-GEO CBP comparator facilities.

If the original `HSBP1012P00868` package names the 742 Highway 131 facility or facility code `6R7`, the public-prime-chain count should increase from 7 to 8 while the physical-facility count remains 11.

## Bounded search universe

USAspending was queried from its supported lower bound, 2007-10-01, through 2026-07-14. Results can include awards with earlier start dates when a transaction falls inside that action-date window.

| Query | Result rows |
|---|---:|
| DHS NAICS `922140` | 202 |
| DHS PSC `X1FF` | 41 |
| CBP keyword `detention` | 139 |
| CBP keyword `detainee` | 485 |
| CBP keyword `jail` | 36 |
| CBP keyword `lodging` | 740 |
| Deduplicated union | 1,490 awards / 543 recipients |
| Public-recipient name heuristic | 163 awards / 64 recipients |

The public-recipient set was cross-checked against GEO facility names and locations in seven full 10-K snapshots (fiscal 2007, 2011, 2012, 2014, 2016, 2018, and 2025) plus targeted 2013 and 2017 filings. USAspending award detail and HigherGov were used for exact PIID, legal-recipient, obligation, PSC/NAICS, and place-of-performance reconciliation. The County of Maverick UEI was checked only in the local SAM mirror.

This is a bounded acquisition result, not proof that no other public-prime chain exists. The main falsifiers are an award using an unrelated description, miscoded recipient, predecessor/successor PIID absent from these search terms, or a private operating agreement that never appeared in GEO's SEC facility disclosures.

## Maverick chronology and role separation

| Date / PIID | Record | Legal prime | Operator at award date | Owner at award date | Disposition |
|---|---|---|---|---|---|
| 2005-08-01, `HSBP1005P07705` | CBP purchase order; $9,304.48 net obligation; no description; Eagle Pass/Maverick place | County of Maverick | Not established as GEO | Not facility-resolved | Excluded. GEO's fiscal-2007 filing treated the Maverick project as not yet commenced; the award does not identify a facility. |
| 2008-11-10, USMS IGA mod 1 | Adds Maverick County Detention Facility, 742 Highway 131, code `6R7`, at a $52.50 document-snapshot per diem | Maverick County under IGA `80-99-0219` | Separate operator evidence required | Maverick County | Facility identity anchor only. The $52.50 rate is not proven to be the rate on any CBP purchase order. |
| 2012-07-26, `HSBP20120027801393` | CBP purchase order; $11,941.65; “DETENTION SPACE FOR FEDERAL DETAINEES; DEL RIO SECTOR” | County of Maverick | GEO operated the Maverick facility during this period, but award geography is inconsistent | County-owned Maverick facility possible; Val Verde place also possible | Excluded from the Maverick chain denominator. USAspending codes the place of performance as Del Rio, Val Verde County. |
| Signed/action 2012-09-14; USAspending POP start 2012-09-15, `HSBP1012P00868` | CBP purchase order; base action $7,181.50; current net obligation $5,758.75; PSC `X1FF`; “DETENTION SPACE”; Eagle Pass/Maverick place | County of Maverick | GEO, if the award used the 688-bed Maverick County Detention Facility | Maverick County | **Probable chain.** HigherGov reports the period start as 2012-09-14 while USAspending award detail reports 2012-09-15. The recipient, county, service, and GEO's managed-only disclosure align; missing facility name prevents verification. |
| 2013-11-01 | GEO says it terminated the managed-only contract for the county-owned 688-bed facility | N/A | GEO ended management | Maverick County | Temporal cutoff. |
| POP start 2014-05-25; signed/action 2014-07-21, `HSBP1014P00452` | CBP purchase order; $11,760; “LODGING OF DETAINEES”; Eagle Pass/Maverick place | County of Maverick | Not GEO under the terminated management contract | Maverick County | Excluded. Both the POP start and signed/action date postdate GEO's 2013 termination. |
| POP 2015-10-01 to 2016-11-29; signed 2016-01-27, `HSBP1016J00076` | Direct-GEO CBP BPA call previously mapped to Maverick at medium confidence | GEO | Unknown; GEO is the legal prime, but operation after the 2013 termination is not proved | Unknown; GEO did not acquire the idle facility until 2017 | Existing direct comparator, not a new public-prime chain. Facility mapping does not establish 2016 operator or owner status. |
| 2017-03-06 | GEO acquired the idle 688-bed Maverick County Detention Center for about $15 million | N/A | Idle | GEO after acquisition | Ownership transition; must not be back-projected into the 2012 award. |

### Primary-record excerpts

- The 2012 award description is **“DETENTION SPACE.”** USAspending and HigherGov both identify the legal awardee as County of Maverick and the place as Eagle Pass/Maverick County.
- GEO's fiscal-2012 10-K facility row identifies **“Maverick County Detention Facility ... USMS/BOP ... Manage Only.”**
- The USMS modification says, **“The purpose of this modification is to add the following facility to the IGA: Maverick County Detention Facility”** and lists **“Facility Code: 6R7”** and a **“Per Diem Rate: $52.50.”**
- GEO later reported: **“On November 1, 2013, GEO terminated the contract for the management of the county-owned 688-bed Maverick County Detention Center.”**
- GEO's 2017 10-Q states: **“On March 6, 2017, the Company acquired the 688-bed Maverick County Detention Center in Texas for approximately $15 million.”**

## What the money fields do—and do not—show

For `HSBP1012P00868`:

- **Base action obligation:** $7,181.50.
- **Current net obligation:** $5,758.75 after a later reduction reflected in the award total.
- **Potential/current award value in HigherGov:** $5,758.75.
- **Outlays:** not established by the retrieved award records.
- **Downstream payment to GEO:** not established.
- **County fee or retained spread:** not established.
- **Applicable detention rate:** not established. The IGA's $52.50 rate is a 2008 document snapshot, not a verified CBP purchase-order rate.
- **GEO facility revenue:** not established at award level. SEC facility or segment revenue disclosures cannot be equated to this purchase order.

The award establishes federal obligation to the County of Maverick, not federal payment directly to GEO and not GEO revenue. Any denominator that treats the $5,758.75 as downstream GEO revenue would be unsupported.

## Negative and control searches

Three name collisions were resolved with primary location data rather than counted as chains:

- **City of Aurora, `HSCEDM08P00062`:** ICE paid the city $2,900 for detainee space at Aurora, Colorado `80012` in Arapahoe County. GEO's SEC property exhibit locates Aurora ICE Processing Center at `80010`. The shared city name is not a facility join.
- **City of Burlington, `HSCEDM08P00055`:** the zero-obligation ICE award performs in Burlington, Colorado. GEO filing hits for Burlington are community-program locations in Burlington, Massachusetts.
- **Hidalgo County, `HSBP1016P00143`:** CBP paid Hidalgo County $19,182 for jail/detention in Edinburg `78542`. GEO's disclosed East Hidalgo and Coastal Bend facilities are in La Villa `78562` and Robstown `78380`, respectively.

The current `70B03C25F00001321` record is also a false geographic match for the known Joe Corley/Montgomery County, Texas chain: its legal recipient is a Montgomery County, New York soil-and-water district and USAspending codes performance to Swanton, Vermont.

Targeted SEC full-text searches found no GEO filing match for the candidate facility names associated with Crystal City, San Luis Regional, Zapata, La Salle County Regional, Imperial County, Taylor County, San Bernardino County, Yuma County, Cascade County, Albany County, Clinton County, Coos County, Franklin County, Rensselaer County, or Schenectady County. These are bounded negatives, not proof of non-operation.

## Acquisition gaps and falsifiers

The following record would resolve the probable Maverick chain:

1. The original award and modification package for `HSBP1012P00868`, including invoice/remittance instructions, bed-day detail, facility address, or IGA/facility-code reference.
2. County vouchers, accounts-payable records, or operating-company invoices covering 2012-09-14 through 2012-12-31.
3. Any CBP detention log or facility roster that identifies whether the purchase order used Tom Bowles (`6DM`) or the 742 Highway 131 Maverick facility (`6R7`).

The chain should be rejected if those records identify Tom Bowles, another county facility, or a non-GEO service site. It should be promoted to verified if they identify 742 Highway 131, code `6R7`, or the 688-bed Maverick County Detention Facility.

## Audit note

Awards, procurement families, public-prime chains, and physical facilities remain separate units. Legal prime, operator, owner, rate, federal obligation, outlay, downstream payment, retained fee, and corporate revenue are also kept separate. No downstream-dollar finding is claimed.

Existing finding `#12717` remains valid only as a **medium-confidence facility mapping** for the 2016 direct-GEO call. It must not be read as evidence that GEO operated or owned Maverick in 2016. Its detail was refined in the correction log to record the 2013 management termination and 2017 acquisition boundary.

The companion [crosswalk CSV](./2026-07-14-dhs-public-prime-geo-chain-crosswalk.csv), [crosswalk JSON](./2026-07-14-dhs-public-prime-geo-chain-crosswalk.json), and [source manifest](./2026-07-14-dhs-public-prime-geo-chain-source-manifest.json) preserve the dispositions and source boundaries.
