# GEO Transport, Inc. legal-entity lineage and federal-recipient attribution

## Status: completed

Lead `#57848` is resolved at the level supported by free public primary records. GEO Transport, Inc. is the active Florida profit corporation formed October 4, 2007, under document `P07000109960`, EIN `56-2677868`. SEC, SAM, and USAspending identifiers align to that same legal entity: CIK `0001517753`, UEI `DFEKRCYPZD84`, and CAGE `6PV86`.

The evidence establishes GEO as the ultimate direct-or-indirect owner and federal parent recipient. It does **not** disclose GEO Transport's exact immediate-parent rung. No intermediate parent was inferred.

## Exact identity chain

| System | Legal name | Identifier | Matching fields | Present boundary |
|---|---|---|---|---|
| Florida Division of Corporations | GEO TRANSPORT, INC. | `P07000109960`; EIN `56-2677868` | Florida; filed 2007-10-04; active; 4955 Technology Way | Official detail says “No Events” and “No Name History”; this is a Florida-record boundary |
| SEC EDGAR | GEO Transport, Inc. | CIK `0001517753`; EIN `562677868` | Florida incorporation; exact legal name; empty `formerNames` | SEC submissions metadata retains an older Boca Raton address and does not identify the immediate parent |
| SAM public extract | GEO TRANSPORT, INC. | UEI `DFEKRCYPZD84`; CAGE `6PV86` | Entity start 2007-10-04; 4955 Technology Way; no DBA | March 2026 extract snapshot; no live SAM call used |
| USAspending ICE award details | GEO TRANSPORT, INC. | UEI `DFEKRCYPZD84` | Both records carry parent recipient THE GEO GROUP, INC. / `JMLKZZ1NL2Z6` | Parent-recipient grouping is not an immediate-parent disclosure |

Finding `#13058` records this cross-source resolution as a medium-confidence synthesis rather than treating database agreement as independent corroboration of every field.

## Formation, name history, and continuity

Florida's official live detail records GEO Transport as a Florida profit corporation filed October 4, 2007. It lists annual-report images for every year from 2008 through 2025 and explicitly displays “No Events” and “No Name History.” The local unified registry independently preserves the legal name, Florida document number, formation date, active status, EIN, current address, agent, and the first six officer slots. The local filing-history table is empty, so the live official page—not the incomplete local filing table—controls the annual-report history.

SEC's CIK record supplies the same legal name, Florida jurisdiction, and EIN. A June 2, 2011 S-4/A co-registrant table identifies “GEO Transport, Inc.,” “Florida,” and `56-2677868`. GEO's FY2025 Exhibit 21 again lists GEO Transport and states that, unless otherwise specified, GEO holds the listed subsidiaries directly or indirectly 100%. Exhibit 22 lists GEO Transport among the subsidiary guarantors of GEO's outstanding senior notes.

Together, those filings establish continuity from at least the 2011 co-registrant group through the December 31, 2025 subsidiary and guarantor disclosures. They do not show a merger, former name, or exact immediate parent. Finding `#13057` preserves the Florida legal record; finding `#13061` preserves the bounded SEC continuity synthesis.

## DHS and ICE recipient attribution

USAspending's detail records for the 2021 ICE definitive contract `70CDCR21C00000005` and the 2026 ICE delivery order `70CDCR26FR0000002` contain the same recipient fields:

- recipient name: `GEO TRANSPORT, INC.`
- recipient UEI: `DFEKRCYPZD84`
- parent recipient name: `THE GEO GROUP, INC.`
- parent recipient UEI: `JMLKZZ1NL2Z6`

The records were dependency-collapsed as one federal legal-recipient attribution chain in finding `#13060`. Existing finding `#12474` already controls the two-award obligation total, so this trace neither repeats nor recomputes the dollar amount. The earlier CSI Aviation subcontract is a separate subcontract relationship already controlled by finding `#12892`; it was not converted into a direct-prime award or used to infer the immediate corporate parent.

## Current Sunbiz officer roster

The live Florida detail page listed fourteen current officers when retrieved July 14, 2026. The exact titles are preserved in the [officer-address matrix](2026-07-14-lead-57848-geo-transport-lineage-wave11-officer-address-matrix.csv) and entity-role rows `#2585` and `#2613`–`#2625`.

The roster includes George C. Zoley as “DIRECTOR, Executive Chairman,” J. David Donahue as “President, Director,” and twelve vice-presidential or director-title records. Every listed officer uses the 4955 Technology Way address. These are Sunbiz's current listed titles as retrieved. They are neither beneficial-ownership evidence nor evidence that any listed person participated in an operational or contract decision.

The registered agent is Corporate Creations Network Inc. at 801 US Highway 1, North Palm Beach. Because it is a mass-market agent, no probative relationship or new entity was created from that appearance.

## Canonical database result

Canonical entity `#4812` now carries:

- jurisdiction `fl`
- EIN `562677868`
- formation date `2007-10-04`
- current address `4955 Technology Way, Boca Raton, FL 33431`
- source notes for CIK `0001517753`, UEI `DFEKRCYPZD84`, and CAGE `6PV86`

Existing relation `#843` remains `GEO Transport, Inc. --subsidiary_of--> The GEO Group Inc. (#1290)`, but its description now states that the evidence proves ultimate/direct-or-indirect parent attribution while the exact immediate parent remains unresolved. The provenance now includes Exhibit 21, Exhibit 22, and both USAspending parent-recipient records.

No alias was added for the upper-case legal name because it is only a case variant. No duplicate entity was merged, and no new entity, relation, or speculative connection was created.

## Findings added

| Finding | Claim class | Result |
|---|---|---|
| `#13057` | direct quote / confirmed | Florida formation, active status, EIN, “No Events,” and “No Name History” |
| `#13058` | synthesis / medium | Florida–SEC–SAM identifier crosswalk |
| `#13059` | synthesis / medium | Fourteen current Sunbiz-listed officers with strict non-ownership/non-operational boundary |
| `#13060` | direct quote / confirmed | USAspending recipient and parent-recipient identifiers across both ICE records |
| `#13061` | synthesis / medium | 2011 co-registrant to FY2025 subsidiary and guarantor continuity |

All five findings are verified by `lead-57848-primary-source-audit` and contain evidence references plus source quotes.

## Remaining bounded gap

The exact immediate-parent entity between GEO Transport and The GEO Group, if any, remains unresolved in the reviewed free public sources. Closing that gap would require a direct ownership schedule, tax/legal organization chart, formation/share ledger, or equivalent corporate record. The gap does not prevent legal-recipient attribution to GEO Transport or ultimate/direct-or-indirect attribution to GEO.

## Artifacts

- [Legal-lineage timeline](2026-07-14-lead-57848-geo-transport-lineage-wave11-legal-lineage-timeline.csv)
- [Registry and federal-status matrix](2026-07-14-lead-57848-geo-transport-lineage-wave11-registry-status-matrix.csv)
- [Officer and address matrix](2026-07-14-lead-57848-geo-transport-lineage-wave11-officer-address-matrix.csv)
- [Negative and boundary log](2026-07-14-lead-57848-geo-transport-lineage-wave11-negative-log.md)
- [Source and database manifest](2026-07-14-lead-57848-geo-transport-lineage-wave11-source-db-manifest.json)
- [SHA-256 ledger](2026-07-14-lead-57848-geo-transport-lineage-wave11-SHA256SUMS.txt)

## Stop reason

Completed: official Florida, SEC, local SAM, and USAspending records resolve formation, current status, identifiers, current officer/address roster, ultimate GEO continuity, and exact ICE recipient attribution. The only remaining ownership gap is the exact immediate-parent rung, which the reviewed public records do not disclose; no further inference is warranted.
