# GEO historical ICE rates and guarantees

Lead 57786 is substantiated, but only one historical housing-price schedule was recoverable in unredacted unit-price form. The December 2010 Karnes County IGSA states $68.75 per detainee for the first 480 and $56.48 for detainees 481–600, plus $0.50 per transportation mile and $1 per detainee work-program day. The contract does **not** safely support treating 480 as an unconditional payable guarantee: it calls 480 the minimum bed availability, states that ICE is liable for actual detainee days, and makes the start of minimum payments depend on a separate ramp-up plan.

The strongest direct-GEO guarantee evidence comes from South Texas/Pearsall. A 2009 task-order modification names CLIN 3029 as “ADULT DETAINEES 1146 GUARANTEED HOUSING” and CLIN 3030 as “ADULT DETAINEES ABOVE GUARANTEED MINIMUM 758 MAX.” Those phrases are recorded literally. The 1,146 guarantee and 758 incremental maximum are never merged into a quoted capacity, and the b(4)-redacted unit prices remain null.

The facility-name collision is resolved on primary evidence, not fuzzy similarity. P00001 under the same ACD-4-C-0001/HSCEDM-09-F-00001 contract family uses “South Texas Detention Cent” in its funding-purpose text and, on the continuation sheet, “SOUTHWEST TEXAS DETENTION COMPLEX” for the delivery location at 566 Veterans Drive, Pearsall. The database now keeps **South Texas Detention Complex** as canonical and **Southwest Texas Detention Complex** as an entity-variant alias.

## What the historical schedules disclose

- Pearsall's base PWS specified 850 adult-male beds, 150 adult-female beds and 20 juvenile beds. Its staffing rule required coverage for an estimated 1,000 adults and 20 juveniles, officers of both sexes at all times, and at least five female officers per shift excluding transportation. The adult male/female component subcounts do not reconcile with the quoted headline totals; the ledger preserves the quoted totals and makes no silent correction.
- Broward's 2009 schedule used a guaranteed-minimum CLIN and additional bed-day tiers, but withheld the guarantee count and bed-day prices. It disclosed detainee work-program wages at $1 per day and a $111.55 million total award. The total award is kept in an award-value field and is not compared with unit prices.
- Tacoma's 2009 schedule separated a base bed-day tier from an excess tier. It disclosed extended line amounts of $50.37 million and $1.45 million but redacted counts and unit rates. Its $114,975 detainee-work-program lot reimbursed actual cost at $1 per detainee-day. Again, the lot ceiling is not treated as a unit price.
- Aurora's 2008 modification explicitly separated bed-day minimum guarantees without healthcare, excess bed requirements with daily healthcare, and healthcare for the guaranteed minimum. Counts and unit prices were redacted, while some extended line amounts survived. Housing and healthcare components stay separate in the ledger.
- Adelanto's 2011 modification increased medical staffing under an attached plan, but the number of FTEs and related pricing were b(4)-redacted.

The GEO role at Karnes is independently anchored in GEO's 2025 Form 10-K, which says GEO provides ICE support services there under an IGSA between Karnes County and ICE. This avoids converting an IGSA with the county into a falsely labeled direct ICE–GEO contract.

## Current-award comparison boundary

Current USAspending snapshots were retrieved for Aurora, Broward, South Texas/Pearsall, Tacoma, Adelanto and Desert View. They identify GEO as recipient and provide performance periods and award-level obligations. They do not contain bed-day quantities, guarantees or unit prices. Those obligation amounts are therefore stored only as award snapshots; no obligation was divided by an assumed bed count or used as a rate proxy.

The latest retrieved ICE contract modifications reinforce the missing-data diagnosis:

- Tacoma P00049 says it incorporates staffing plans for guaranteed-minimum and full-capacity beds and changes the guaranteed-minimum bed-day rate, but redacts all counts and old/new rates.
- Aurora P00011 updates a staffing plan and says its bed-day CLIN rate changed, but redacts the values.
- Broward P00011 changes a facility-operations monthly rate, guaranteed-minimum transportation miles/guard-hours rate and on-call guard rate, but redacts the values. These units are not comparable to a bed day.

Accordingly, there is no honest like-for-like historical-to-current unit-price comparison in this report. There is also no CPI-U transformation: inflation adjustment would imply comparability that the public values do not support. If an unredacted current bed-day schedule is later recovered, the comparison should use the same facility, service bundle, bed category, guarantee status, tier boundary and unit; only then should official BLS CPI-U be applied.

## Evidence controls and limitations

The Deportation Research Clinic, Detention Watch Network and NIJC materials were used for discovery and routing. Findings rely on the underlying government contracts, ICE FOIA releases, USAspending API responses and SEC filing. The full 525-page 2012 GEO payment production and scan-only Aurora/Tacoma material received targeted OCR. OCR recovered contract architecture and invoice totals but did not reconstruct redacted values; every visible b(4) field remains null.

The companion files are:

- `2026-07-14-lead-57786-historical-ice-rates-ledger.csv` — normalized schedule, staffing and current-award rows.
- `2026-07-14-lead-57786-historical-ice-rates-quotes.csv` — exact quote/source matrix.
- `2026-07-14-lead-57786-historical-ice-rates-unavailable.csv` — negative and unavailable-field log.
- `2026-07-14-lead-57786-historical-ice-rates-sha256.csv` — source/output integrity manifest (excluding itself to avoid a self-referential hash).

Database findings 12986–12991 preserve the Karnes schedule/guarantee distinction, South Texas guarantee tiers, Pearsall staffing rule, GEO's Karnes role, the current-rate redaction diagnosis and the primary-supported South/Southwest facility-name alias. Each has an exact source quote for every evidence reference and passed the repository verifier; all are assigned to thread 110. Human action 74 is a narrowly scoped FOIA diagnostic for the missing current CLIN/staffing pages; its `related_lead_id` is deliberately null.

Bottom line: the evidence establishes historical GEO/ICE guarantee architectures and staffing requirements, recovers Karnes' $68.75/$56.48 two-tier schedule, and confirms that contemporary ICE modifications still use comparable guarantee and bed-day fields. Publicly released current values are redacted, so any claimed current rate comparison would be unsupported.
