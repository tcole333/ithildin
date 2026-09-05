# Boston liquor licenses: full-roster review

This expands the initial collateral sample into a reproducible review of every alcohol-license entry in the supplied Boston dataset. The decision-archive passes are complete for the two stated source windows; the full UCC index, filing-document and ownership checks remain incomplete.

**Full-list UCC collection is paused pending supported access.** One normal navigation in the same in-app browser loaded the search form on September 4; no new debtor query or filing-document request was submitted. Result and document access remain unverified. The Secretary's [Terms of Use](https://www.sec.state.ma.us/divisions/terms.htm) prohibit scraping by automated or manual means, so the full-roster run awaits a supported export or records-delivery route. See the [current collection status](ucc-collection-status.json), [access options](access-options.md) and [unsent inquiry](ucc-access-inquiry-draft.md).

The checkpoint preserves **96 completed current-index holder queries**, with 1,348 current and 1,444 lapsed queries pending in the broad queue. These are query counts, not reviewed loans. The earlier Access Denied/Error 15 observation at 2026-09-04 02:42:12 UTC remains in the immutable [historical access-denial record](ucc-access-block.json). It is separate from the current pause and from a no-match result.

Open [the review dashboard](dashboard.html) or [the sortable license CSV](license-review.csv). [review-data.json](review-data.json) records the latest generated coverage; the append-only UCC evidence and queue can be newer than a dashboard build.

## The notes miss most recorded pledge approvals

Matching both finalized windows against the source roster finds **202 distinct roster licenses with a granted pledge application**. Only two have a financing marker across the roster's comments, location comments and premises description. **200 have none.** Five of the 202 also have recorded pledge-release acknowledgments. The original 2024–2026 comparison remains separately visible: 93 licenses, two with markers and 91 without. This establishes that dataset notes are an inadequate way to identify historical pledge approvals. It does not estimate the sensitivity of those notes for active loans or establish present debt balances.

The [original decision corpus](transfer-corpus/README.md) and [reviewed earlier extension](transfer-corpus/prior-2024/README.md) retain separate manifests, source documents, normalized events and quality reviews. Combined coverage is **153 distinct documents: 152 PDFs containing 1,824 pages, plus one HTML document**. The 155 observed source URL entries include two duplicate PDF assets within the earlier window; source hashes have no overlap across windows.

| Finalized archive window | Distinct documents / PDF pages | Transfer / pledge actions | Exact roster joins / distinct licenses |
|---|---:|---:|---:|
| April 23, 2020–December 14, 2023 | 89 / 906 | 473 | 446 / 263 |
| January 1, 2024–September 3, 2026 | 64 / 918, plus one HTML document included in 64 | 307 | 281 / 192 |
| Combined, deduplicated license IDs | 153 / 1,824 | 780 | 727 / 412 |

The combined action ledger contains:

| Recorded action | Count | Disposition detail |
|---|---:|---|
| License-transfer applications | 518 | 465 granted; 53 other dispositions |
| License-pledge applications | 249 | 232 granted; 17 other dispositions |
| Notices of intent to revoke prior transfer approvals | 3 | Acknowledgments retained separately |
| Pledge releases | 10 | Acknowledgments retained separately |

Of the 780 events, 727 match 412 license numbers in the full source roster. The 53 unmatched events remain visible: 44 reference license numbers absent from the snapshot and nine lack a usable normalized Boston license ID, including missing and malformed identifiers. Nineteen other source notices, fourteen ownership-interest notices, and one unresolved proposal remain in separate ledgers; none increases these application or approval counts. The unresolved proposal preserves the printed word “Grated” without treating it as a grant. No speculative name match fills identifier gaps. A decision can precede a later reversal, and a granted application does not establish closing or final state approval. These retained archive windows are not every license's complete lifetime history.

The separate [attachment, execution, seizure and discharge notice review](judgment-attachment-review/README.md) contains thirteen observations from a keyword review of the saved corpus. Eight observations join seven inventory licenses by explicit license number; historical named parties remain distinct from roster holders. Six observations contain literal amounts covering five identified monetary matters, including a repeated Fire & Ice execution notice. The dashboard preserves each notice and its qualifications without adding these observations to transfer, pledge or UCC counts, or summing amounts. A Board acknowledgment is not review of the underlying court or tax instrument and does not establish current liability, priority or enforceability.

## Population and current review coverage

The source contains 3,610 rows and 3,593 distinct license numbers, including many non-alcohol categories. The core alcohol population is **1,512 distinct licenses held by 1,437 normalized legal-holder groups**. Five BYOB licenses and three ambiguous-category licenses are separately available in the broad queue; it contains 1,520 licenses and 1,444 holder groups. Duplicate row lineage and active-label/expired-date inconsistencies are preserved. See [inventory scope](inventory-scope.md).

The dashboard's **License category** filter uses the [source-label cohorts](license-class-cohorts-README.md), an exhaustive exact-ID mapping of all 1,520 licenses into nine segments. Airport-labeled licenses (51), innholder/hotel-labeled licenses (82), and retail/druggist-labeled licenses (306) can be examined separately. The default core-alcohol view includes 305 retail licenses; the additional druggist record remains a flagged boundary case. The original license-class filter and a separate restriction-wording filter remain available. Literal flags preserve the roster's wording, including ambiguous abbreviations. They do not determine legal transferability, acquisition route, price or ownership; absent restriction wording does not mean unrestricted. Source types, row lineage and hashes remain available in each record's evidence.

The UCC queue records current and lapsed searches separately, with query text, response counts, source observations and review state. A complete index query is not a completed lien review. Search results may include similarly named debtors, amendments, continuations or terminated filings; counts are not counts of loans. Filing histories and collateral attachments must be examined, with exact legal-entity matching, historical aliases and debtor formation jurisdiction considered. A Massachusetts query with no matches does not establish the absence of financing.

The original [sample review](../follow-up/README.md) provides examples where filing documents explicitly name a liquor license. The sample and first-pass findings retain their original scope and entity/identifier caveats; the larger inventory does not silently strengthen them.

The separate [saved-history reconciliation](filing-review-reconciliation-README.md) adds analyst review of seven older histories containing eleven entries: three for CMG CP1/Caveau and four for SK Wine and Liquors/Bauer. Only one original PDF has prior complete visual-review evidence; six original and four amendment PDFs remain pending. The dashboard binds these records by holder ID and original filing number while preserving identity and license-continuity caveats. It does not change the base filing queue's 19 imported prior-history-review count or refresh source coverage. SK's historical ABCC license identifier still lacks a verified crosswalk to the current Boston license; C T Corporation is recorded as a representative, with the underlying lender unresolved.

## Ownership and concentration

The [ownership review](../ownership/README.md) currently documents **72 license affiliations across 17 groups**, plus **11 reviewed-but-unresolved cases**, for 83 reviewed licenses. Of the documented affiliations, **five license affiliations across two groups have documented PE backing**: Fogo de Chão/Bain and Broadway Hospitality Group/Authentic Restaurant Brands/Garnett Station. This is a targeted observed minimum, not a citywide PE estimate. The similarly named Broadway Restaurant Group associated with Prima is a different group.

The dashboard keeps capital classification, operating-group affiliation, scale and review coverage separate. Operator and capital filters use the reviewed snapshot affiliation; they do not establish that the same affiliation or backing existed on an earlier transfer or pledge date. Historical source parties remain in each event. Group websites can establish management, marketing or portfolio relationships without common equity ownership. Lyons explicitly disclaims owning its listed venue entities. Unknown capital backing remains unknown; it does not become independent or non-PE.

The [large-operator follow-up](../ownership/evidence/large-operator-follow-up/root-integration-review.json) adds five reviewed HMSHost/Avolta and three Delaware North affiliations. One Sam Adams/HMSHost candidate and eight Areas candidates remain reviewed but unassigned. Historical ownership and dated minority-shareholder observations are preserved in the full match/assessment evidence; they do not become current private-equity control findings. Terminal, gate, current-DBA and corporate-crosswalk qualifications remain visible in each record.

To test the price/concentration hypothesis, the missing variables are transaction-level license consideration, acquisition route, closing date, seller and buyer ownership at the time, and comparable entrant cohorts. Directly awarded transferable licenses, restricted awards, private transfers and beer/wine upgrades must be distinguished. A sponsor's purchase of an existing restaurant group can change ownership without any license sale. See the [policy and comparison design](../ownership/evidence/policy/report-policy.md). Current affiliation counts cannot establish that expensive licenses caused concentration.

The separate [original ownership-interest ledger](transfer-corpus/ownership-interest-README.md) and [earlier extension](transfer-corpus/prior-2024/README.md) cover stock, membership-interest and corporate-structure applications. The [combined ledger](review-ownership-interest-events-combined.json) contains **301 application decisions, including 237 explicitly concerning alcohol licenses across 200 source license IDs**, plus fourteen separate notices. Of the applications, 215 join 182 licenses in this review inventory; other exact joins concern excluded non-alcohol roster categories. The original 146-decision ledger remains unchanged. Named parties, percentages and control require source-specific review; an application does not establish a completed equity transaction. These actions are not added to the 780 transfer/pledge actions and do not change the researched operator assignments.

The [Christine Freeman/Glynn network review](../ownership/evidence/christine-freeman/README.md) uses a bounded three-call OpenCorporates check and historical state records to connect corporate roles with license-holder entities. Officer-name matches and management relationships remain separate from beneficial ownership; the same license is not counted twice when a new source corroborates its affiliation.

## Reproduce and inspect

From the repository root:

```bash
uv run python reports/boston-liquor-license-collateral-2026-09-03/full-review/build_review_data.py
uv run python reports/boston-liquor-license-collateral-2026-09-03/full-review/build_dashboard.py
```

The saved source CSV, inventory, search queue, decision documents, normalized events, unmatched-event audit, ownership evidence and raw UCC observations are retained alongside the derived dashboard. Combined ledgers add window provenance without replacing either source window or the original benchmark. The [earlier-window quality review](transfer-corpus/prior-2024/quality-review/README.md) checks saved-source hashes, references, outcomes and purposeful visual cases. The [Terra/Sol pilot](transfer-corpus/benchmark/README.md) found three unsupported current-lien assertions by Terra and no scored errors by Sol on the same 13 selected cases. It does not alter source findings or establish a general model ranking.

The [UCC access options](access-options.md), [corporate-records access options](corporate-records-access-options.md) and [combined unsent data inquiry](massachusetts-bulk-data-inquiry-draft.md) describe supported access questions. No inquiry has been sent, paid order placed or bulk dataset received.

No findings were written into the unrelated active investigation profile. No subjects were contacted or paid documents ordered.
