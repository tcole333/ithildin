# GEO-linked ICE IGSA terms and control review

Date: 2026-07-13  
Profile: `geo-group`  
Lead: `57966`  
Skill: `analyze-contract`

## Outcome

The recovered records establish the recurring federal-prime/local-government/GEO-operator structure, but they do not support a conclusion that one standard GEO template governs all five facilities. The LaSalle and Charlton local agreements materially differ in control, fee, termination, and indemnity provisions. Three local operator agreements and most federal base instruments/task orders remain unavailable in the reviewed public collections, so the cross-facility comparison is incomplete.

## Instrument and terms matrix

| Facility / federal prime | PIID and reviewed federal instrument | GEO role recoverable from primary record | Local operator agreement | Price / modification control | Oversight / audit | Termination / indemnity | Exact record-access gap |
|---|---|---|---|---|---|---|---|
| Folkston / D. Ray James — County of Charlton | `EROIGSA-17-0002`; ICE `P00022`; county-release copy of `P00032` | `P00022` says “Subcontractor: GEO.” `P00032` names GEO subcontractor contacts and adds D. Ray James. | 2016 operating agreement plus amendments 1 and 2 recovered as DocumentCloud record `26055306`; public compensation figures are redacted. | Agreement ties county compensation to ICE payment under the IGSA, but rate basis and county fee are visibly redacted. Changes require mutual written agreement. | County may inspect; GEO may postpone a facility inspection for a health/safety risk. On five business days’ notice, no more than quarterly, county may examine contracts, invoices, payroll, personnel, and related data. | Cause: 30-day cure then five-day termination notice. Convenience: either party, 30 days. ADA indemnity and negligence allocation; not the broad all-operations indemnity seen at LaSalle. | Federal base IGSA, task orders, modifications other than `P00022/P00032`, unredacted compensation schedules, county ledgers/invoices, and any later operator amendments not in record `26055306`. |
| Pine Prairie / South Louisiana — Evangeline Parish Sheriff’s Office | `EROIGSA-15-0006`; `P00034–P00037` | `P00036` says “Subcontractor: GEO.” | Not recovered. | Mods incorporate wage determinations, approve retroactive rate increases/payments, and correct the Pine Prairie guard/transportation rate. Amounts are redacted. | Not recoverable from reviewed mods. | Not recoverable. | Federal base IGSA and task orders; parish-GEO agreement and all amendments; rate schedules; COR/QASP records; invoices/check registers; fee, audit, termination, and indemnity provisions. |
| Alexandria / Central Louisiana — LaSalle Economic Development District | `DROIGSA-07-0015`; `P00050–P00051` | Mods say “Sub-K: Geo Group.” | Full 2007 services contract and 2010 fee amendment recovered. | LEDD pays GEO the same per diem ICE pays LEDD; GEO bills on the same basis; GEO receives the same ICE-originated price adjustment. GEO assumes activation, transport, guard, intake/discharge, and invoice duties. | ICE and LEDD retain periodic inspection rights. IGSA performance requirements/QASP flow to GEO. | Term is linked to continuing IGSA status. GEO broadly indemnifies LEDD and ICE for management/operation claims, detainee claims, negligence, damage, and fees. | Federal base IGSA/task orders; post-2010 local amendments; unredacted federal rates; invoice-level reconciliation; precise early-termination language if contained only in the missing IGSA. |
| Moshannon Valley — County of Clearfield | `70CDCR21DIG000012`; `P00014–P00016` | `P00014` states GEO Group, Inc. submitted the Oct. 21, 2024 request for equitable adjustment. | Not recovered. | ICE approved GEO-submitted rate changes effective Sept. 29, 2024; reviewed amounts are redacted. | Not recoverable from reviewed mods. | Not recoverable. | Federal base IGSA/task orders and rate schedules; county-GEO services agreement/amendments; QASP/COR records; invoices/general ledger; fee, termination, audit, and indemnity clauses. |
| Karnes County Immigration Processing Center — Karnes County | `70CDCR24DIG000018`; base and `P00001` | GEO is not named in the reviewed federal base. Any operator attribution requires the missing county-GEO record or another primary record. | Not recovered. | Base obligates no funds; annual funded task orders authorize service. All IGSA provisions must flow into subcontracts. Invoices must align with CLINs and support bed-day, transportation, and guard charges. | Attachment list includes a QASP and performance requirements, but substantive operator-level audit/control terms were not fully recoverable. | Not recoverable. | Funded task orders, county-GEO agreement/amendments, unredacted rates/amounts, invoice packages, fee records, operator identity in a primary agreement, termination and indemnity terms. |

## Cross-case assessment

- Fact: Charlton and LaSalle each place operating duties on GEO beneath a local public prime and tie local-to-GEO compensation to the ICE IGSA.
- Fact: Their local contractual controls differ. Charlton provides express bilateral 30-day convenience termination and quarterly record audit; LaSalle uses broad operational flow-down, ICE/LEDD inspection, IGSA-linked term, and broad GEO indemnification.
- Fact: Evangeline and Clearfield modifications show GEO participating in rate implementation beneath local primes, but the reviewed modifications cannot establish local control allocation.
- Fact: Karnes supplies the clearest federal invoice traceability and subcontract-flow-down language, while the reviewed base does not name GEO or obligate funds.
- Scope limit: the five cases cannot yet be compared on competition history, statutory authority, complete rate setting, or all operator termination/indemnity provisions because four federal bases and three local operator agreements were not recovered.

## Baselines and disconfirmation

- Direct-prime baseline: finding `12403` reconstructs 202 direct ICE prime awards to GEO, B.I. Incorporated, and GEO Transport in USAspending, showing that ICE also awards directly to GEO-affiliated recipients; the IGSA architecture is therefore not the only ICE-GEO procurement path.
- Non-GEO local-prime baseline: not completed. No exact, complete, non-GEO local IGSA/operator pair was recovered within this bounded review. This remains necessary before attributing the repeated architecture to GEO rather than ordinary ICE/local-government contracting.
- Structured disconfirmation: exact HigherGov award-ID searches returned no record for all five PIIDs. SAM returned no award record for four tested PIIDs; Karnes was not tested after the daily quota response. USAspending exact legal-recipient/DHS contract searches returned no matching prime award for the five local counterparties. These API results do not prove the awards are absent from archival federal systems.

## Findings recorded

`12435`, `12439` (corrected after visual redaction review), `12442`, with earlier primary findings `12405–12408`.

## Lead disposition

Do not complete `57966`. Block on the enumerated base instruments, task orders, and local operator agreements. The records recovered meet partial-terms extraction but not the lead’s five-case comparison stop condition.

## Learnings

- [Source Quality] Public ICE detention-contract PDFs frequently expose only selected modifications. Treat a modification bundle as a partial instrument, never as the complete agreement.
- [Methodology] For IGSA forensics, local audit reports and operator agreements are often more informative than federal award APIs because they disclose the downstream operator, administrative fee, and control allocation.
- [Process Gap] OCR can reconstruct hidden-looking text across scans, but visually inspect compensation fields before treating OCR as evidence; redactions produced an initially overbroad Charlton payment description that was corrected in finding `12439`.
- [Methodology] A rigorous comparison needs an explicit recoverability matrix. “Not in reviewed modification,” “redacted,” “API returned zero,” and “not tested because quota” are different negative states.

## Sources

- ICE Folkston `P00022`: https://www.ice.gov/doclib/foia/detFacContracts/EROIGSA170002_P00022_FolkstonIPC_CharlstonCo_IGSA_FolkstonGA.pdf
- Charlton 2016 operating agreement and amendments: https://www.documentcloud.org/documents/26055306-orr25-0028-documents-2.pdf
- Charlton `P00032`: https://www.documentcloud.org/documents/26055307-orr25-0028-documents.pdf
- ICE Evangeline `P00034–P00037`: https://www.ice.gov/doclib/foia/detFacContracts/EROIGSA150006_P00034-37_SouthLouisiana_PinePrairieLA.pdf
- LaSalle services contract: https://cdn.muckrock.com/foia_files/2015/08/19/LEDD_Agreement_4-1-2007.pdf
- LaSalle fee amendment: https://cdn.muckrock.com/foia_files/2015/08/19/Amd_1_re_administrative_fee.pdf
- ICE LaSalle `P00050–P00051`: https://www.ice.gov/doclib/foia/detFacContracts/DROIGSA-07-0015_P00050-P00051.pdf
- ICE Moshannon `P00014–P00016`: https://www.ice.gov/doclib/foia/detFacContracts/70CDCR21DIG000012_P00014-16_MoshannonValleyPC_PA.pdf
- ICE Karnes base–`P00001`: https://www.ice.gov/doclib/foia/detFacContracts/70CDCR24DIG000018_BASE-P00001_KarnesCoResidentialCntr_IGSA_KarnesCityTX.pdf
