# Baseline audit — September 4, 2026

The corrected baseline is ready for merge: **395 events, 62 property/context keys, 54 exact Boston parcel IDs, and 32 distinct registry instruments**. This was a local audit of saved evidence; no new online searches or first-wave artifact edits were performed.

Two corrections were made:

- **Suffolk 17988/312:** added parcel 0501159000 (400–402 Boylston), alongside 0501160000 (396–398) and 0501161000 (392–394). The source owner's completed three-page review and audited finding 15578 establish execution and acknowledgment on December 23, 1992; recording remains January 15, 1993. All three event rows carry the single transaction's $1,925,000 consideration and the same instrument ID. Do not sum the amount across parcels. The obsolete partial-review note was removed and status changed to `original_complete_review`.
- **Court participants:** removed directional From→To fields from all ten court/claim events. Their names now form one expressly labeled participant list, with no title-transfer capacity. No award, attachment or alleged family percentage enters the consideration or loan fields.

Verification compared all **147 assessment quotes** field by field with saved raw government rows and checked parcel normalization, fiscal-year dates, owner spellings, source URLs and assessed amounts. Six FY2021 condominium master rows have null assessed totals; the metric export correctly leaves them blank, rather than reporting zero. Assessment quotes now also retain `ST_ALPHA` and `ST_NUM2` where supplied by the source.

All **200 permit quotes** match their saved source fields, including applicant, parcel, issuance timestamp, status and declared valuation. Each event joins only the PID supplied by the permit, including permits with broader address ranges. All **32 instrument recording dates** match the saved registry ledger. The two reviewed 2016 quitclaims stating consideration under $100 retain blank numeric consideration with an explicit upper-bound note. The corrected 1993 amount and separate execution/recording dates passed dedicated checks. Ruff passes for the baseline generator.

The baseline is a source chronology, not a completed title opinion. Remaining limitations are explicit: index-only parties/capacities are unresolved, 33 Havre is not merged with 31 Havre, the Four Seasons and Talal unit candidates remain identity-qualified, and Fienberg's 382–390 Boylston litigation is still marked as a candidate address-range join. Mortgage grantee candidates are not treated as borrowers. Court awards and the 2026 attachment overlap and do not establish a current balance.

**Merge instruction:** incoming source-owner original reviews should replace baseline index candidates by county and book/page, preserving every newly established parcel. In particular, the Suffolk owner reports that original 56448/321 corrects misleading index capacities and covers all three 392–402 Boylston parcels; root is handling that replacement from the completed Suffolk export. Do not count candidate and original rows as separate transactions. The Brookline life-estate events are likewise source-owned and should be merged from the other-counties export.

Artifacts: `evidence/wave2/timeline-baseline/events.csv`, `coverage-manifest.json`, `event-metrics.csv`, `manifest.json`, and `audit-checks.json`. The regenerated property-by-property narrative is `reports/wave2/report-timeline-baseline.md`.

No new repository papercut arose during this audit. No new finding was needed: this corrects derived timeline rows using the source owner's audited finding and preserves source ownership.
