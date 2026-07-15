# GEO federal-recipient identity map: closure audit

**Lead:** #57693  
**Audit date:** 2026-07-14  
**Canonical deliverables:** [CSV](2026-07-13-geo-federal-recipient-identity-map.csv), [JSON](2026-07-13-geo-federal-recipient-identity-map.json), and [narrative](2026-07-13-geo-federal-recipient-identity-map.md)  
**Source manifest:** [JSON](2026-07-14-lead-57693-geo-recipient-map-source-manifest.json)

## Result

The canonical map is fit for use in GEO federal-contract searches. It contains 75 search-manifest rows—60 exact names from GEO's FY2025 Exhibit 22.1 plus 15 parent, legacy, former-name, and punctuation variants—normalized to 62 legal identities. Fourteen distinct federal-recipient identities have verified UEI/CAGE pairs: 12 appear in the March 2026 SAM public extract and two are legacy award recipients retained through exact USAspending/HigherGov records. The six GEO-affiliated identities observed as ICE recipients in the verified bounded DHS reconstruction are The GEO Group, B.I. Incorporated, Cornell Companies, Correctional Services Corporation, GEO Care Services, and GEO Transport.

This closure audit made **no live SAM call**. Exact local SAM queries returned the same 12 current registrations and no record for the same two legacy UEIs. Fresh HigherGov awardee lookups resolved all 14 UEI/CAGE pairs. HigherGov's legal-business-name field is blank for legacy Correctional Services Corporation, although its clean name, UEI, CAGE, awardee key, and GEO parent key remain populated. HigherGov also self-parents GEO Management Services; the map correctly follows GEO's primary SEC subsidiary disclosure instead of that secondary hierarchy anomaly.

## Recipient denominator

| Recipient | UEI | CAGE | Current-source treatment | DHS actions, 2015-01-01–2026-07-13 |
|---|---|---|---|---:|
| B.I. Incorporated | `PKK6L9KLMYR5` | `3CUH9` | Current SAM | 166 |
| Community Education Centers, Inc. | `K197TCMH5UB5` | `3YET9` | Current SAM | 0 |
| Cornell Companies, Inc. | `TLDCDE29G781` | `3MTH6` | Legacy recipient; absent current SAM | 24 |
| Correctional Services Corporation | `LTXHRJ986LF3` | `3KGQ1` | Legacy recipient; absent current SAM | 3 |
| GEO Care Services, LLC | `G6XJKMJUNB91` | `7D4M5` | Current SAM | 92 |
| GEO Care, Inc. | `J8LEF6VCY967` | `15A51` | Current SAM | 0 |
| GEO CPM, Inc. | `XHRVS1L8YE54` | `99YL8` | Current SAM | 0 |
| GEO Management Services, Inc. | `ZBJYBK7M9A44` | `7T8J8` | Current SAM | 0 |
| GEO Reentry, Inc. | `KDQ3R3N44ZJ1` | `7CUD5` | Current SAM | 0 |
| GEO Reentry of Alaska, Inc. | `FNT5N5HMB9A7` | `7G0K5` | Current SAM | 0 |
| GEO Reentry Services LLC | `CLKXSJLN8EN1` | `7G0N6` | Current SAM | 0 |
| GEO Secure Services, LLC | `JLG3JBCL4CC7` | `7G0P0` | Current SAM | 0 |
| GEO Transport, Inc. | `DFEKRCYPZD84` | `6PV86` | Current SAM | 3 |
| The GEO Group, Inc. | `JMLKZZ1NL2Z6` | `3JMR1` | Current SAM | 1,128 |

The action counts are exact-recipient rows in the verified 14-UEI, direct-prime DHS ledger. They are not all-agency totals, payments, ceilings, revenue, subawards, or facility-level IGSAs. Zero means no action in that bounded scan.

## Lineage rules supported by primary filings

- **Wackenhut Corrections Corporation → The GEO Group, Inc.** The same issuer CIK filed the 2003 proposed corporate-name change. This is a former legal name of the parent, not a second current recipient.
- **Correctional Services Corporation.** GEO's 2006 Form 10-K says CSC merged into GEO Acquisition, Inc. on November 4, 2005. The legacy recipient UEI remains searchable, but it is not collapsed into the separately listed FY2025 entity Correctional Services Corporation LLC without primary evidence of a direct name conversion.
- **Cornell Companies, Inc.** Cornell's 2010 Form 8-K says the merger sub merged into Cornell, Cornell survived, and Cornell became a wholly owned GEO subsidiary. Its legacy UEI therefore remains attached to Cornell rather than the parent.
- **B.I. Incorporated.** GEO acquired BII Holding, the indirect owner of BI, on February 10, 2011. BI remains a separately registered federal recipient.
- **Community Education Centers.** GEO's 2017 Form 8-K records the closing of its acquisition of CEC. CEC remains a separately registered federal recipient.
- **GEO Care, LLC → GEO Care Services, LLC.** GEO's 2026 credit amendment signs the guarantor as “GEO CARE SERVICES, LLC (f/k/a GEO CARE, LLC).” GEO Care, Inc. is a different legal entity with a different UEI and must not be merged into this row.

## Search and attribution rules

Use the UEI as the primary join key, confirm the exact recipient legal name and CAGE, and deduplicate transaction rows after any parent-UEI expansion. Do not promote a facility, operating division, or trade name to a federal registration without a UEI/CAGE record. Do not attribute a subsidiary award to the GEO parent merely because a secondary source supplies a parent key.

The remaining 48 exact Exhibit 22 identities are bounded current-source nonmatches, not historical negatives. The principal unresolved contract-search identity is **GEO Corrections Holdings, Inc.**: the exact SEC name has no matched current SAM registration or exact USAspending recipient in the reviewed sources. Follow-up lead #60299 isolates that residual question, so it does not prevent closing the broader canonical-map lead.

## Audited findings

Verified findings #12662–#12666 support the current/legacy registrations, coverage denominator, live-status supplement, and Wackenhut former-name rule. Verified findings #12531 and #12534 support the bounded DHS exact-recipient denominator and the GEO Corrections Holdings residual gap. Finding #12773 independently supports Cornell's 2010 acquisition timing. This audit adds one synthesis finding for the four acquisition structures and preserves all remaining uncertainty in the source manifest.
