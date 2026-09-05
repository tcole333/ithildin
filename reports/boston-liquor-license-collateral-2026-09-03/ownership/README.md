# Boston liquor-license ownership review

As of 4 September 2026, [owner-mappings.json](owner-mappings.json) contains **72 distinct roster alcohol-license IDs with documented group or portfolio affiliations**, across 17 group records, and **11 additional reviewed-but-unresolved cases**. The 83 reviewed licenses are a targeted research subset. The rest of the roster must retain its actual review state; an unreviewed record is not an independent business.

The conservative documented PE-group affiliation lower bound is **five Boston licenses across two PE-backed groups**. This is an observed affiliation minimum, not an estimate of the PE share of Boston restaurants or a certified beneficial-ownership count.

| Documented PE-backed group | Sponsor evidence | Matched Boston license IDs |
|---|---|---|
| Fogo de Chão | [Bain Capital current portfolio](https://baincapitalprivateequity.com/portfolio) and [completed acquisition account](https://www.baincapital.com/news/bain-capital-finds-unique-qualities-consumer-sector-fogo-de-chao-and-1440-foods) | LB-98917 |
| Broadway Hospitality Group / Authentic Restaurant Brands | [Garnett Station's active equity portfolio entry](https://garnettstation.com/partner/tavern-in-the-square/) and [ARB's recapitalization announcement](https://www.nasdaq.com/press-release/authentic-restaurant-brands-adds-tavern-square-its-latest-fortress-regional-brand) | LB-98812, LB-99259, LB-99058, LB-99057 |

Broadway Hospitality Group is distinct from Boston's Broadway Restaurant Group, associated with Prima and other venues. The similar names must not carry Garnett sponsorship from one business to the other. The five-license count requires both a documented sponsorship relationship and a sufficiently supported local venue/license affiliation; it does not claim that every intermediate entity or equity percentage has been verified.

## Taxonomy

Ownership and operation are separate dimensions. A licensee is the legal holder named in the municipal record. A restaurant group may own, manage, market or partner with a venue; a hotel, landlord or franchisor may be a separate party. An officer, manager, registered agent, lender or shared address does not by itself establish equity ownership or common control.

| Dimension | Recorded categories | Interpretation |
|---|---|---|
| Review coverage | Not reviewed; reviewed with unresolved assignment; documented affiliation | Measures completed research, independently of its outcome. |
| Relationship | Restaurant/group affiliation; operator or management affiliation; portfolio affiliation; unresolved | Preserve the narrow relationship supported by the source. A portfolio link is not a complete equity chain. |
| Capital | Documented PE backing; public company; other private investment or holding-company backing; unresolved | A named sponsor and transaction/current portfolio evidence support PE classification. Private money alone is not enough. |
| Scale | Verified locations; dated location minimum; named concepts; unresolved group total | Preserve unit, date and limitations. Concepts, premises, licenses and legal entities are different counts. |
| Equity control | Documented control, when available; otherwise unresolved | Do not fill missing percentages or turn a management relationship into ownership. |

**Unknown does not mean independent.** Family-run, founder-led and privately held descriptions do not prove the absence of institutional investors. A search with no PE disclosure is an unresolved result, not a negative finding. Darden is recorded as a public parent; that category does not mean its shareholders exclude investment funds. PPX's documented investment-holding-company association remains unresolved for institutional PE structure. Big Night's counsel disclosed historical private-equity fundraising work without identifying a sponsor or control stakes; it remains outside the documented PE numerator. Debt and UCC secured-party relationships are not equity classifications.

## Affiliation qualifications and counting

[Lyons Group's current portfolio](https://lyonsgroup.com/portfolio) expressly disclaims ownership of the listed venue entities. Its 13 matched licenses therefore use `relationship: portfolio_affiliation_only_equity_ownership_disclaimed` and `equity_ownership_disclaimed_by_group: true`. They can support a disclosed-affiliation view but must not be collapsed into one common-equity owner without further evidence. The group's portfolio contains 24 named entries, while its homepage headline says 23; neither number is a Boston license count.

Big Night's six and Glynn's six matches preserve operator/portfolio qualifications and unresolved equity chains. Nia Grace's co-owner role is retained for Grace by Nia. Hotel addresses for BSMNT, Scampo or Alibi do not establish ownership of the host hotels or their separate licenses. Detailed evidence is in [additional-local-groups](evidence/additional-local-groups/README.md).

The [large-operator follow-up](evidence/large-operator-follow-up/README.md) adds five HMSHost/Avolta airport affiliations and three Delaware North arena-concession affiliations. The latter are three licenses at one TD Garden/North Station complex, not three independent restaurants. The named license-holder/operator link supports all three affiliations; the current trading name of Viva Victory Den remains unverified. Airport terminal, gate and space-description differences remain in the individual match notes.

Avolta is a public company. Its [year-end investor disclosure](https://www.avoltaworld.com/en/company/our-stakeholders/investors) names Advent among shareholders above 3% as of December 31, 2025. That dated minority holding is recorded separately from PE control and is not carried forward as a verified September 2026 stake. The current equity percentages of the local concession ventures remain unresolved.

Areas [completed its acquisition of Delaware North's U.S. airport division](https://us.areas.com/news/areas-officially-takes-over-delaware-norths-travel-hospitality-services-becoming-the-largest-privately-held-travel-hospitality-company-in-the-u-s) in December 2025. Eight Boston Flight licenses remain successor candidates, pending registered-entity continuity and the current local ownership chain. Their assessments preserve the historical PAI majority-investment evidence, joint-venture partners, and date limits without adding a current group assignment or PE numerator entry.

Several concepts share one alcohol license, including Scorpion/The Grand; Big Night Live/Studio B/Play; Bill's Bar/Lansdowne Pub; and Scampo/Alibi. Colocated concepts such as Retro Room, 88 Club and D16 do not add another license without a verified separate record. Plain Common Victualler, bowling and billiard licenses are excluded from these alcohol-license matches. Alternative street addresses and development addresses remain explicit in the match notes.

Maple Hospitality's scale is now **four Maple & Ash brand locations; total group venues unresolved**. The five MHG concepts and nine concept-location listings include colocations and do not establish nine distinct venues. No full-group 6–19 venue band is assigned on that evidence. Other groups' dated minimums and concept-based bands retain their stated units and dates.

## Reviewed cases without a group assignment

The top-level `assessments` array contains Tia's Waterfront (**LB-98892**), Committee (**LB-99301**), Sam Adams (**LB-99480**), and eight Boston Flight successor candidates. All 11 have `state: reviewed_unresolved`, null `group_id` and `group_name`, unresolved capital classification, and false flags for group affiliation, documented PE affiliation and single-unit independence. They count toward ownership-review coverage, but do not create a group assignment or a PE numerator entry. Full candidate matches, possible-group evidence, sources and dates are retained.

Tia's [registry evidence](evidence/sample-b/S04-tias-ownership.json) verifies John P. Cronin as manager. Shared business-address and historical associations do not establish a current Cronin Group equity chain. Committee's [evidence review](evidence/sample-a/S01-committee-ownership.json) preserves a historical primary operator announcement and current secondary ownership reporting without inventing a formal parent. A former manager's later Xenia affiliation is not Committee ownership evidence. Sources and unresolved questions travel with each assessment.

## What this can establish about concentration

The current results establish affiliations worth examining alongside transfers, license restrictions, dates and financing records. They do not show that license prices caused PE investment or group concentration. Prominent groups were deliberately researched, ownership disclosure is uneven, and current affiliations cannot establish the buyer's ownership at an earlier transfer date. License counts also differ from restaurant counts, capacity, revenue and market share.

A causal analysis would require dated transfer histories and verified prices, ownership at each transaction date, comparable independent and group buyers, and a consistent definition of legally transferable versus restricted licenses. It should distinguish PE sponsor acquisitions of an operating company from restaurant purchases of individual licenses and account for neighborhood, restaurant scale, business model and policy changes. Until those data are available, report descriptive patterns and coverage gaps rather than a price-driven concentration effect.

Likewise, a UCC filing is not automatically an active loan secured by a liquor license, and a municipal pledge approval is not proof of a current outstanding balance. Loan/collateral evidence, transfer evidence and ownership evidence remain separate dimensions.

## Files and reproducibility

- [owner-mappings.json](owner-mappings.json): integration source, including source URLs, relationship qualifications, unresolved assessments and summary counts.
- [Additional local groups](evidence/additional-local-groups/README.md): Big Night, Lyons and Glynn matching and archived source manifests.
- [Large operators](evidence/large-operator-follow-up/README.md) and [root integration review](evidence/large-operator-follow-up/root-integration-review.json): eight accepted affiliations, nine new unresolved cases, and the preserved pre-merge snapshot.
- [Source-label cohorts](../full-review/license-class-cohorts-README.md): exhaustive category mapping for comparisons, with restrictions, acquisition route and prices kept distinct.
- [Sample A](evidence/sample-a/report-sample-a.md), [sample B](evidence/sample-b/report-sample-b.md), and [transfer recipients](evidence/transfers/README.md): bounded research reports and source evidence.

The merge verified uniqueness of all 72 assigned license IDs across the 17 group records, excluded all 11 unresolved assessments from those assignments, and checked the five-license/two-group documented PE lower bound. The original 64 matches and two assessments were preserved unchanged. Source artifacts retain acquisition dates and observation dates; current sponsor evidence and historical venue evidence must not be silently treated as contemporaneous.
