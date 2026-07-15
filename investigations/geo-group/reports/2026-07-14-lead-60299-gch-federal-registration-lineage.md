# GEO Corrections Holdings federal-registration lineage

**Lead:** #60299  
**Profile / thread:** `geo-group` / 110  
**As of:** 2026-07-14  
**Scope:** exact legal-name, former-name, address, identifier, merger, and recipient-history reconciliation. No live SAM call was used.

## Result

No distinct UEI or CAGE code can be verified for **GEO Corrections Holdings, Inc.** (`GCH`). The March 2026 local SAM public extract contains no exact GCH registration, and neither current USAspending recipient history nor HigherGov's 15-row GEO parent hierarchy contains GCH. GCH's verified identifiers are instead corporate and securities identifiers: Florida document `P12000103643`, EIN `46-1972528`, and SEC CIK `0001578145`.

One historical DUNS candidate requires careful treatment. A 2016 FEC complaint linked to a legacy USAspending recipient profile labeled “GEO Corrections Holdings, Inc.” using `DUNSNumber=079242241`. A 2018 Wayback capture proves that the requested legacy profile URL existed, but the archived shell loaded its data through uncaptured application iframes and does not independently identify the DUNS owner. Current official USAspending endpoints return no recipient, award, transaction, or subaward for `079242241`. The number is therefore an **unresolved obsolete profile key, not a verified GCH DUNS**.

The exact `$266,666` fiscal-2015 record underlying that complaint is now resolved. Current USAspending data identifies it as a February 1, 2015 DOJ Office of Justice Programs **sub-grant** from the Louisiana Department of Public Safety and Corrections to **GEO Reentry Services, LLC**, UEI `CLKXSJLN8EN1`, legacy DUNS `079805752`, at 621 NW 53rd Street. The downloadable 113-column USAspending row independently supplies that DUNS and UEI. The FEC's own factual and legal analysis likewise said the respondents supplied a contract confirming that the parties were GEO Reentry and Louisiana; it concluded that this Louisiana record did not demonstrate that GCH was a federal contractor.

This resolves the award-attribution question for that record: it belonged to a separately registered operating subsidiary, not GCH. It does **not** resolve every historical contractor-status dispute. In the same matter, the FEC relied separately on a 2013 NLRB brief in which GCH described itself as having federal-agency contracts. GEO's sworn response said Cornell Companies, Inc. held the D. Ray James federal contract and that GCH did not seek, hold, or perform government contracts. The Commission found reason to believe based on the conflicting NLRB representations, while accepting that the Louisiana record was not proof of a GCH federal contract. This report therefore answers registration and recipient identity without treating either party's broader characterization as a final adjudication of every contract relationship.

## Corporate identity and name history

Florida formed GCH on December 26, 2012. The current record is active, gives EIN `46-1972528`, and reports the principal address as 4955 Technology Way, Boca Raton. The official page reports **“No Name History.”** SEC's submission record for CIK `0001578145` also has an empty `formerNames` array and preserves the earlier One Park Place / 621 NW 53rd Street address.

The singular payer spelling `GEO CORRECTIONS HOLDING INC` is therefore a reporting variant, not a supported former legal name. CIK `0001578146` must not be assigned to GCH: it belongs to **GEO Leasing, LLC**, formerly **GEO Operations, LLC**, with EIN `46-1288456`.

GCH appeared in GEO's March 1, 2013 subsidiary exhibit shortly after formation. GEO's December 2012 REIT-reorganization filing said non-real-estate operations would be reorganized into taxable REIT subsidiaries. In a sworn 2017 FEC affidavit, Amber Martin described GCH as a wholly owned holding company for operating subsidiaries. SEC ownership schedules independently show the parent owned 100% of GCH and GCH owned operating entities including GEO Corrections and Detention, GEO Reentry Services, GEO Design Services, GEO Operations LLC, and GEO Transport.

GCH also has a capital-markets role that should not be mistaken for a procurement registration. SEC filings make it a co-borrower under GEO credit agreements and the issuer of exchangeable senior notes. Those filings explain why it has a CIK and financing history even though no distinct federal procurement identifier surfaced.

## 2024 merger test

Florida records show that **GEO Operations, Inc.** (`P17000042350`) was formed May 11, 2017 and became inactive after a merger filing on December 18, 2024. The event file says it “WAS PART OF A MERGER” and identifies GCH as the qualified corporation. GCH's reciprocal event says it “WAS A MERGER RESULT.” The merger was effective December 30, 2024.

Exact current searches for `GEO Operations, Inc.`, `GEO Operations LLC`, and `GEO Corrections and Detention, LLC` did not produce a new GCH federal-registration lineage. The first two names returned no current SAM or exact USAspending award/transaction match; HigherGov's parent hierarchy contains neither GCH nor GEO Operations. The 2024 merger therefore explains a state-law successor event but does not reveal a predecessor UEI/CAGE that rolled into GCH.

The verified corporate graph now records `GEO Corrections Holdings, Inc.` (#5038) as successor to `GEO Operations, Inc.` (#5059), with the direction and effective date stated explicitly.

## Bounded federal-source denominator

| Source / selector | Result | Limit |
|---|---:|---|
| Local SAM public extract dated 2026-03-01: exact `GEO Corrections Holdings` and singular variant | 0 | Current public extract, not a complete CCR-era archive |
| Local SAM: 4955 Technology Way | 11 GEO-related registrations, none GCH | Current address-based denominator |
| Local SAM: 621 NW 53rd Street | 2 rows, none GCH | Current/legacy-address denominator; broad token matching can add noise |
| Local SAM: `GEO Operations, Inc.` / `GEO Operations LLC` | 0 | Current extract only |
| USAspending exact GCH recipient autocomplete, prime awards, transactions, and advanced subawards | 0 | Transactions searched 2007-10-01–2026-07-14, covering GCH's entire lifespan |
| USAspending exact `079242241` recipient, prime award, transaction, and advanced subaward | 0 | Current database; legacy profile shell survives only in Wayback |
| USAspending exact `GEO Reentry Services` advanced subaward search | 1 | The `$266,666` Louisiana record, with UEI `CLKXSJLN8EN1` |
| HigherGov awardees under GEO parent key `10000076` | 15, none GCH | Parent hierarchy and historical awardee rows returned by the API |
| Florida GCH name history | 0 prior names | Official state record and bulk name-history table |
| SEC GCH former names | 0 | CIK `0001578145`; 31 recent co-registrant filings in the retrieved submission set |

## Identifier disposition

| Identifier | Disposition |
|---|---|
| Florida document `P12000103643` | Verified GCH |
| EIN `46-1972528` | Verified GCH in Florida and SEC records |
| SEC CIK `0001578145` | Verified GCH |
| UEI | No verified distinct GCH value |
| CAGE | No verified distinct GCH value |
| DUNS `079242241` | Unresolved legacy USAspending profile key; do not attach to GCH |
| DUNS `079805752` | Verified on the exact `$266,666` row for GEO Reentry Services, LLC, not GCH |
| UEI `CLKXSJLN8EN1` / CAGE `7G0N6` | Current GEO Reentry Services registration, not GCH |

## Residual gap

The only material unresolved registration question is whether an archived CCR/SAM or legacy USAspending backend record can identify the owner of `079242241`. Public web, current USAspending, current SAM, HigherGov, SEC, and state records did not do so. A future acquisition should seek a historical CCR/SAM entity extract or Treasury's legacy recipient-profile backend snapshot, not infer ownership from the obsolete URL.

That residual gap does not prevent closure of the broad lead. The public record supports a bounded conclusion: no distinct GCH UEI/CAGE was located; the one concrete award cited as GCH was actually reported under GEO Reentry Services; Cornell was the named D. Ray James contractor in GEO's sworn response; and the 2024 GEO Operations merger did not expose a hidden federal recipient identity.

## Primary sources

- [Florida GCH record](https://search.sunbiz.org/Inquiry/CorporationSearch/SearchByNumber?searchNumber=P12000103643)
- [Florida GEO Operations record](https://search.sunbiz.org/Inquiry/CorporationSearch/SearchByNumber?searchNumber=P17000042350)
- [SEC submission record for CIK 0001578145](https://data.sec.gov/submissions/CIK0001578145.json)
- [GEO 2012 REIT-reorganization filing](https://www.sec.gov/Archives/edgar/data/923796/000119312512500268/d451366d8k.htm)
- [2014 SEC ownership schedule](https://www.sec.gov/Archives/edgar/data/923796/000119312514330726/d783514dex101.htm)
- [FEC MUR 7180 complaint](https://www.fec.gov/files/legal/murs/7180/7180_01.pdf)
- [GEO respondents' MUR 7180 response and sworn affidavits](https://www.fec.gov/files/legal/murs/7180/7180_15.pdf)
- [FEC MUR 7180 factual and legal analysis](https://www.fec.gov/files/legal/murs/7180/7180_19.pdf)
- [Current USAspending record for prime award 2013CZBX0023](https://www.usaspending.gov/award/ASST_NON_2013CZBX0023_015/)
- [2018 archived legacy USAspending profile shell](https://web.archive.org/web/20180227150159id_/https://www.usaspending.gov/transparency/Pages/RecipientProfile.aspx?DUNSNumber=079242241&FiscalYear=2015)

Machine-readable deliverables:

- `2026-07-14-lead-60299-gch-federal-registration-lineage-map.json`
- `2026-07-14-lead-60299-gch-federal-registration-source-manifest.json`
