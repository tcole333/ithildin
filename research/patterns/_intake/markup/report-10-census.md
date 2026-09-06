# The Markup corpus census

**Snapshot:** July 29, 2026. **Unit of the headline article count:** one distinct, dated editorial URL in the union of The Markup's live archive pagination and every exposed series pagination. This is a URL-page census, not a semantic deduplication of stories. All judgments below are marked **[inferred]**; unmarked counts come from the enumerable pulls in [`raw/`](raw/).

## 1. Method and sources

### Merger and site-structure resolution

This had to be resolved before counting.

- On **April 18, 2024**, The Markup announced that it was "[joining forces with CalMatters](https://themarkup.org/inside-the-markup/2024/04/18/the-markup-is-joining-forces-with-calmatters)." It explicitly said, "The Markup, as a publication, isn't going anywhere," and that national work would continue. CalMatters' same-day announcement described an [acquisition expected to produce one integrated newsroom later in 2024](https://calmatters.org/inside-the-newsroom/2024/04/calmatters-acquires-themarkup/). The CalMatters page now carries an updated date of February 10, 2026; the underlying announcement date remains April 18, 2024.
- `themarkup.org` was still a live, self-canonical publication site at the July 29, 2026 pull. Pre-merger examples returned `200` at their original Markup URLs with self-canonical tags. Post-merger work continued to publish there through at least [July 28, 2026](https://themarkup.org/privacy/2026/07/28/brazil-gives-parents-social-media-controls-for-their-kids-should-the-u-s).
- CalMatters often publishes a second copy. A comparison of all **3,733** CalMatters WordPress posts since April 18, 2024 against the Markup frame found **47** conservative same/near-title pairs at normalized title similarity `>=0.85`. Tested pairs are separately self-canonical; they are not migrated Markup URLs or redirect targets. The 47 is deliberately conservative because headlines and publication dates sometimes differ.
- No Markup sitemap was exposed: `/sitemap.xml` and `/sitemap_index.xml` returned `404`. `/series` redirected to `/archive`; `/topics`, `/tags`, and `/tag` returned `404`. The live enumerating structures were therefore archive pages and individual series pages.

> **Attribution rule.** Count every dated editorial URL exposed by The Markup's own live archive/series structure once, including pre-merger work and post-merger work published or co-published on `themarkup.org`. Do **not** add a separately self-canonical CalMatters copy, a CalMatters-only story, or a Spanish translation/syndication variant. This is a domain-structural rule, not a staff-byline rule. It deliberately avoids reclassifying all work by employees of the integrated newsroom as "The Markup."

Under that rule, there were **zero CalMatters URL additions**. This does not mean CalMatters publishes no joint work; it means the Markup-domain copy is the counted representation when one exists, while CalMatters-only material is outside this site's structural corpus. The raw [topology tests](raw/site-topology.json), [full CalMatters feed pull](raw/calmatters-posts-since-merger.json), [64-result WP search audit](raw/calmatters-markup-search.json), and [attribution audit](raw/calmatters-attribution-audit.json) preserve the evidence.

### Enumeration table

| Source / endpoint | Pull and enumeration method | Enumerable result | Trust decision |
|---|---|---:|---|
| [Markup archive](https://themarkup.org/archive) | Crawled all 69 numbered pages and parsed dated cards | 689 rows; 689 distinct URLs | **Incomplete alone.** It omits 146 newsletter URLs exposed by series pages. |
| 43 exposed `/series/<slug>` pages | Discovered every distinct series link in archive cards/article footers, then crawled every series pagination | 1,093 series-membership rows; 818 distinct URLs | Best available taxonomy frame, but no master series index exists, so a completely orphaned series remains possible. |
| Archive ∪ series | URL-normalized set union | **835 distinct dated editorial URLs** | Headline article denominator. |
| Archive ∩ series | Set intersection | 672 URLs | Demonstrates that neither index contains the other. |
| Archive only | Set difference | 17 URLs | Dated pages with no exposed series membership. |
| Series only | Set difference | 146 URLs: 133 `newsletter/hello-world` and 13 `newsletter/citizen-browser` | Proves the visible archive lies by omission. |
| Markup article pages | Fetched all 689 archive URLs; extracted canonical, date, authors, series links, code/data links, and CalMatters markers | 689 successful page pulls; 0 errors | Used for topology and link inspection; the full 835 denominator comes from card dates and URLs. |
| Markup sitemap/robots | Tested `/sitemap.xml`, `/sitemap_index.xml`; saved `robots.txt` | Both sitemap routes `404`; robots has no sitemap declaration | Sitemap enumeration unavailable. |
| CalMatters WP REST API | Paginated every post after April 17, 2024 | 3,733 posts on 38 API pages | Used only for merger/parallel-copy audit, never added to the Markup denominator. |
| CalMatters WP search for "The Markup" | Audited all results and their full content | 64 candidates: 38 parallel counterparts, 23 references/Cal-only/institutional, 3 Spanish variants | **Not a complete duplicate index.** The full feed finds parallel copies the search misses. |
| [Show Your Work](https://themarkup.org/series/show-your-work) | Crawled all methodology cards and their explicit data/download links | 28 methodology pages; 22 first-party data/reproduction packages | Current site-side dataset frame because `/data` and `/datasets` both return `404`. |
| [GitHub organization](https://github.com/the-markup) and REST API | Paginated all public repos and fetched the default-branch README for each | **84 public repos; 84 READMEs** | First-class code/data corpus. |
| [Awards page](https://themarkup.org/awards) | Counted each linked card or unlinked list item under a year; fetched all linked announcements | **33 structural entries**: 20 linked, 13 unlinked | Entry count, not prize count; page stops at 2024 and is stale. |

All pulls were made on **July 29, 2026**. The principal audit files are:

- Article enumeration: [archive pages](raw/archive-pages.json), [archive audit](raw/archive-audit.json), [series inventory](raw/series-inventory.json), [complete 835-URL union](raw/content-urls-complete.json), [archive gap](raw/archive-gap.json), and [annual counts](raw/annual-counts.json).
- Merger/topology: [site tests](raw/site-topology.json), [CalMatters full feed](raw/calmatters-posts-since-merger.json), [CalMatters attribution audit](raw/calmatters-attribution-audit.json), [CalMatters sitemap index](raw/calmatters-sitemap-index.xml), and [Markup robots](raw/themarkup-robots.txt).
- Data/code: [site-linked assets](raw/site-data-assets.json), [GitHub API pull](raw/github-repos-api.json), [READMEs](raw/github-readmes.json), and [classified repo inventory](raw/github-repo-inventory.json).
- Awards and analysis: [awards inventory](raw/awards-inventory.json), [series classification](raw/series-classification.json), [exclusive portfolio assignments](raw/portfolio-clusters.json), [famous-work frame](raw/famous-frame.json), and [second-wave rankings](raw/second-wave-recommendations.json).

No repository database or investigation tool was used.

## 2. Headline census numbers

### Article pages

The census contains **835 distinct dated editorial URLs**, spanning **September 12, 2019 to July 28, 2026**. The first page is the pre-launch newsletter ["Hello from The Markup"](https://themarkup.org/newsletter/hello-world/hello-from-the-markup); the organization describes its public launch as 2020. All **835/835** URLs have an exact HTML `datetime` from an archive or series card. No year was imputed.

The set arithmetic is:

`689 archive URLs + 818 series-indexed URLs - 672 in both = 835 distinct URLs`.

The archive therefore omits **146/835 = 17.5%** of the complete union; equivalently, the union is **21.2% larger** than the visible archive. All 146 omissions are legacy newsletter pages. Some newsletter pages repeat or abridge reporting found at another URL, so 835 is a page count, not a content-similarity-deduplicated story count.

| Publication year | Distinct dated URLs | Date resolution |
|---:|---:|---|
| 2019 | 1 | Exact day |
| 2020 | 150 | Exact day |
| 2021 | 166 | Exact day |
| 2022 | 150 | Exact day |
| 2023 | 160 | Exact day |
| 2024 | 140 | Exact day |
| 2025 | 45 | Exact day |
| 2026 through July 28 | 23 | Exact day; partial year |
| **Total** | **835** | **835/835 exact** |

### Series / investigations

The site exposes **43 named series taxonomy pages**. That is the reproducible site count. Applying the bounded-project rule in §3 yields **23 named investigation/project series [inferred]** and **20 broad topic, format, resource, umbrella, review, or institutional series [inferred]**. The 23—not all 43—form the substantive project denominator used in §§6–8.

## 3. Their own taxonomy and bottom-up candidate clusters

### What the site exposes

The Markup uses one overlapping `/series/` vocabulary for unlike things:

- bounded investigations such as `Amazon's Advantage`, `Denied`, and `Prediction: Bias`;
- broad beats/topics such as `Artificial Intelligence`, `Machine Learning`, and `Privacy`;
- newsletters and service formats such as `Hello World`, `Data Is Plural`, `The Breakdown`, and `LevelUp`;
- methodology/resource channels such as `Show Your Work`, `Story Recipes`, and `Tools`;
- institutional/update channels such as `Inside The Markup`, `Impact`, `News`, and `Investigations`.

There is no separate live topic/tag directory. `/topics`, `/tags`, and `/tag` returned `404`, and `/series` redirected to the incomplete archive. The **43 series pages produce 1,093 membership occurrences over 818 distinct URLs**, so memberships overlap. They cannot be summed as stories.

### Bottom-up coding rule

**[inferred]** A named series enters the project backbone only if it denotes a bounded investigation/project rather than a beat, recurring format, method channel, or institutional container. Classify each project by the **institution or system being investigated**, not by a generic technology label ("AI") or by the harmed group. Each of the 23 bounded projects receives exactly one cluster. The full 43-row assignment is Appendix A.

For article distribution, use only pages with at least one bounded-project membership. If all project memberships map to one cluster, assign that cluster. If a page crosses clusters, use the primary archive label when that label is a bounded project. Otherwise assign `X0` institutional/meta. This produces mutually exclusive article counts.

The nine candidate clusters are:

1. **C1 Platform ranking, moderation & information ecosystems [inferred]**
2. **C2 Privacy, tracking & data brokerage [inferred]**
3. **C3 Public-sector & institutional decision systems [inferred]**
4. **C4 Platform labor & worker surveillance [inferred]**
5. **C5 Housing, lending, insurance & consumer scoring [inferred]**
6. **C6 Digital access & public-service infrastructure [inferred]**
7. **C7 E-commerce, advertising & market power [inferred]**
8. **C8 Health allocation & care technology [inferred]**
9. **C9 Elections & political influence [inferred]**

## 4. Datasets and code as a first-class corpus

### Site-side data and reproduction packages

The current site has no working `/data` or `/datasets` route. Its homepage's "Blueprints" promise routes readers to [Show Your Work](https://themarkup.org/series/show-your-work), whose 28 pages are therefore the auditable site-side methods/data index. Across them, **22 distinct first-party GitHub data or reproduction packages** are explicitly linked: **7 data releases** and **15 analysis-code packages** under the mutually exclusive repository rule below. These 22 are a site-linked subset of the 84-repository GitHub corpus, not 22 additional repos.

| Site-linked package | Primary class [inferred] | License detected | Linking methodology page(s) | README-stated story mapping |
|---|---|---|---|---|
| [citizen-browser-widely-viewed-content](https://github.com/the-markup/citizen-browser-widely-viewed-content) | data release | BSD-3-Clause | [How We Investigated Facebook’s Most  Popular Content](https://themarkup.org/show-your-work/2021/11/18/how-we-investigated-facebooks-most-popular-content) | [Facebook Isn’t Telling You How Popular Right-Wing Content Is on the Platform](https://themarkup.org/citizen-browser/2021/11/18/facebook-isnt-telling-you-how-popular-right-wing-content-is-on-the-platform)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [investigate-mi-insurance-territories](https://github.com/the-markup/investigate-mi-insurance-territories) | analysis code | BSD-3-Clause | [How We Investigated Car Insurance Loopholes in Michigan](https://themarkup.org/premium-penalty/2024/07/18/how-we-investigated-car-insurance-loopholes-in-michigan) | [Michigan's 'Fair and Reasonable' Reforms Allowed Car Insurers to Charge More in Black Neighborhoods](https://mrkup.org/l5W6g) |
| [investigation-allstates-algorithm](https://github.com/the-markup/investigation-allstates-algorithm) | analysis code | none detected | [How We Analyzed Allstate’s Car Insurance Algorithm ﻿](https://themarkup.org/allstates-algorithm/2020/02/25/show-your-work-car-insurance-suckers-list) | ["Suckers List: How Allstate’s Secret Auto Insurance Algorithm Squeezes Big Spenders."](https://themarkup.org/allstates-algorithm/2020/02/25/car-insurance-suckers-list)<br>["How We Analyzed Allstate’s Car Insurance Algorithm."](https://themarkup.org/allstates-algorithm/2020/02/25/show-your-work-car-insurance-suckers-list) |
| [investigation-amazon-banned-items](https://github.com/the-markup/investigation-amazon-banned-items) | data release | none detected | [How We Investigated Banned Items on Amazon.com](https://themarkup.org/show-your-work/2020/06/18/how-we-investigated-banned-items-on-amazon-com) | [Amazon’s Enforcement Failures Leave Open a Seedy Back Door to Banned Goods—Some Sold and Shipped by Amazon Itself](https://themarkup.org/banned-bounty/2020/06/18/amazons-enforcement-failures-leave-open-a-back-door) |
| [investigation-amazon-banned-items-screenshots](https://github.com/the-markup/investigation-amazon-banned-items-screenshots) | data release | none detected | [How We Investigated Banned Items on Amazon.com](https://themarkup.org/show-your-work/2020/06/18/how-we-investigated-banned-items-on-amazon-com) | [Amazon’s Enforcement Failures Leave Open a Seedy Back Door to Banned Goods—Some Sold and Shipped by Amazon Itself](https://themarkup.org/banned-bounty/2020/06/18/amazons-enforcement-failures-leave-open-a-back-door) |
| [investigation-amazon-brands](https://github.com/the-markup/investigation-amazon-brands) | analysis code | BSD-3-Clause | [How We Analyzed Amazon's Treatment of Its "Brands" in Search Results](https://themarkup.org/amazons-advantage/2021/10/14/how-we-analyzed-amazons-treatment-of-its-brands-in-search-results) | [Amazon Puts Its Own 'Brands' First Above Better-Rated Products](https://themarkup.org/amazons-advantage/2021/10/14/amazon-puts-its-own-brands-first-above-better-rated-products)<br>[When Amazon Takes the Buy Box, it Doesn’t Give it up](https://themarkup.org/amazons-advantage/2021/10/14/when-amazon-takes-the-buy-box-it-doesnt-give-it-up) |
| [investigation-blacklight-the-high-cost-of-free](https://github.com/the-markup/investigation-blacklight-the-high-cost-of-free) | analysis code | none detected | [How We Built a Real-time Privacy Inspector](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector) | [The High Privacy Cost of a ‘Free’ Website](https://themarkup.org/blacklight/2020/09/22/blacklight-tracking-advertisers-digital-privacy-sensitive-websites)<br>[Show Your Work](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector#survey) |
| [investigation-covid19-testing-guidelines](https://github.com/the-markup/investigation-covid19-testing-guidelines) | data release | none detected | [How We Analyzed States’ Coronavirus Testing Plans](https://themarkup.org/show-your-work/2020/04/16/how-we-analyzed-states-coronavirus-testing-plans) | ["How We Analyzed States’ Coronavirus Testing Plans"](https://themarkup.org/coronavirus/2020/04/16/how-we-analyzed-states-coronavirus-testing-plans) |
| [investigation-fb-ads-biden-trump-pricing](https://github.com/the-markup/investigation-fb-ads-biden-trump-pricing) | analysis code | none detected | [How We Analyzed the Cost of Trump’s and Biden's Campaign Ads on Facebook](https://themarkup.org/show-your-work/2020/10/29/how-we-analyzed-the-cost-of-trumps-and-bidens-campaign-ads-on-facebook) | [Facebook Charged Biden a Higher Price Than Trump for Campaign Ads](https://themarkup.org/election-2020/2020/10/29/facebook-political-ad-targeting-algorithm-prices-trump-biden) |
| [investigation-geolitica-plainfield](https://github.com/the-markup/investigation-geolitica-plainfield) | analysis code | none detected | [How We Assessed the Accuracy of Predictive Policing Software](https://themarkup.org/show-your-work/2023/10/02/how-we-assessed-the-accuracy-of-predictive-policing-software) | ["Predictive Policing Software Terrible At Predicting Crimes."](https://themarkup.org/prediction-bias/2023/10/02/predictive-policing-software-terrible-at-predicting-crimes) |
| [investigation-google-search-audit](https://github.com/the-markup/investigation-google-search-audit) | analysis code | none detected | [How We Analyzed Google’s Search Results](https://themarkup.org/google-the-giant/2020/07/28/how-we-analyzed-google-search-results-web-assay-parsing-tool) | [Google’s Top Search Result? Surprise! It’s Google](https://themarkup.org/google-the-giant/2020/07/28/google-search-results-prioritize-google-products-over-competitors) |
| [investigation-isp](https://github.com/the-markup/investigation-isp) | analysis code | BSD-3-Clause | [How We Uncovered Disparities in Internet Deals](https://themarkup.org/show-your-work/2022/10/19/how-we-uncovered-disparities-in-internet-deals) | [Dollars to Megabits: You May Be Paying 400 Times As Much As Your Neighbor for Internet](https://themarkup.org/still-loading/2022/10/19/dollars-to-megabits-you-may-be-paying-400-times-as-much-as-your-neighbor-for-internet-service)<br>[story recipe](https://themarkup.org/story-recipes/2022/10/19/journalists-investigate-which-neighborhoods-in-your-city-are-offered-the-worst-internet-deals) |
| [investigation-nyc-high-school-admissions](https://github.com/the-markup/investigation-nyc-high-school-admissions) | analysis code | BSD-3-Clause | [How We Investigated NYC High School Admissions](https://themarkup.org/show-your-work/2021/05/26/how-we-investigated-nyc-high-school-admissions) | [NYC’s School Algorithms Cement Segregation. This Data Shows How](https://themarkup.org/investigation/2021/05/26/nycs-school-algorithms-cement-segregation-this-data-shows-how) |
| [investigation-organs](https://github.com/the-markup/investigation-organs) | analysis code | BSD-3-Clause | [How We Investigated Racial Disparities in Liver Transplants](https://themarkup.org/show-your-work/2024/02/08/how-we-investigated-racial-disparities-in-liver-transplants)<br>[How We Investigated UNOS’s Liver Allocation Policy](https://themarkup.org/show-your-work/2023/03/21/how-we-investigated-unoss-liver-allocation-policy) | [our investigation on liver transplants](https://themarkup.org/organ-failure/2023/03/21/poorer-states-suffer-under-new-organ-donation-rules-as-livers-go-to-waste)<br>[a subsequent investigation on racial inequities in the liver transplant system](https://themarkup.org/organ-failure/2024/02/08/a-death-sentence-native-americans-shut-out-of-the-nations-liver-transplant-system) |
| [investigation-prediction-bias](https://github.com/the-markup/investigation-prediction-bias) | analysis code | BSD-3-Clause | [How We Determined Crime Prediction Software Disproportionately Targeted Low-Income, Black, and Latino Neighborhoods](https://themarkup.org/show-your-work/2021/12/02/how-we-determined-crime-prediction-software-disproportionately-targeted-low-income-black-and-latino-neighborhoods) | [investigation](https://themarkup.org/prediction-bias/2021/12/02/crime-prediction-software-promised-to-be-free-of-biases-new-data-shows-it-perpetuates-them) |
| [investigation-redlining](https://github.com/the-markup/investigation-redlining) | analysis code | none detected | [How We Investigated Racial Disparities in Federal Mortgage Data](https://themarkup.org/show-your-work/2021/08/25/how-we-investigated-racial-disparities-in-federal-mortgage-data) | [The Secret Bias Hidden in Mortgage-Approval Algorithms](https://themarkup.org/denied/2021/08/25/the-secret-bias-hidden-in-mortgage-approval-algorithms)<br>[Dozens of Mortgage Lenders Showed Significant Disparities; Here Are the Worst](https://themarkup.org/denied/2021/08/25/dozens-of-mortgage-lenders-showed-significant-disparities-here-are-the-worst) |
| [investigation-tenant-screening](https://github.com/the-markup/investigation-tenant-screening) | data release | none detected | [How We Investigated the Tenant Screening Industry](https://themarkup.org/show-your-work/2020/05/28/how-we-investigated-the-tenant-screening-industry) | [Access Denied: Faulty Automated Background Checks Freeze Out Renters](https://themarkup.org/locked-out/2020/05/28/access-denied-faulty-automated-background-checks-freeze-out-renters)<br>[Locked Out](https://themarkup.org/locked-out/) |
| [investigation-vi-spdat](https://github.com/the-markup/investigation-vi-spdat) | analysis code | BSD-3-Clause | [How We Investigated L.A.’s Homelessness Scoring System](https://themarkup.org/show-your-work/2023/02/28/how-we-investigated-l-a-s-homelessness-scoring-system) | [L.A.’s Scoring System for Subsidized Housing Gives Black and Latino People Experiencing Homelessness Lower Priority Scores](https://themarkup.org/investigation/2023/02/28/l-a-s-scoring-system-for-subsidized-housing-gives-black-and-latino-people-experiencing-homelessness-lower-priority-scores) |
| [investigation-wheres-my-email](https://github.com/the-markup/investigation-wheres-my-email) | analysis code | none detected | [How We Examined Gmail's Treatment of Political Emails](https://themarkup.org/google-the-giant/2020/02/26/show-your-work-wheres-my-email) | [Swinging the vote?](https://www.themarkup.org/google-the-giant/2020/02/26/wheres-my-email)<br>[Google the Giant](https://themarkup.org/google-the-giant/)<br>[paper](https://themarkup.org/google-the-giant/2020/02/26/show-your-work-wheres-my-email) |
| [investigation-youtube-ad-placements](https://github.com/the-markup/investigation-youtube-ad-placements) | analysis code | NOASSERTION | [How We Discovered Google’s Social Justice Blocklist for YouTube Ad Placements](https://themarkup.org/google-the-giant/2021/04/09/how-we-discovered-googles-social-justice-blocklist-for-youtube-ad-placements)<br>[How We Discovered Google’s Hate Blocklist for Ad Placements on YouTube](https://themarkup.org/google-the-giant/2021/04/08/how-we-discovered-googles-hate-blocklist-for-ad-placements-on-youtube) | [Google Has a Secret Blocklist that Hides YouTube Hate Videos from Advertisers—But It’s Full of Holes](https://themarkup.org/google-the-giant/2021/04/08/google-youtube-hate-videos-ad-keywords-blocklist-failures)<br>[Google Blocks Advertisers from Targeting Black Lives Matter YouTube Videos](https://themarkup.org/google-the-giant/2021/04/09/google-blocks-advertisers-from-targeting-black-lives-matter-youtube-videos) |
| [meta-pixel-student-aid](https://github.com/the-markup/meta-pixel-student-aid) | data release | none detected | Site link preserved in raw pull | [Applied for Student Aid Online? Facebook Saw You](https://themarkup.org/pixel-hunt/2022/04/28/applied-for-student-aid-online-facebook-saw-you) |
| [split-screen-news-sources](https://github.com/the-markup/split-screen-news-sources) | data release | none detected | [How We Built a Facebook Feed Viewer](https://themarkup.org/show-your-work/2021/03/11/how-we-built-a-facebook-feed-viewer) | [Split Screen](https://themarkup.org/citizen-browser/2021/03/11/split-screen)<br>[here](https://themarkup.org/citizen-browser/2021/03/11/how-we-built-a-facebook-feed-viewer) |

### GitHub organization

The [the-markup GitHub organization](https://github.com/the-markup) exposed **84 public repositories** on the pull date. Each repository was assigned one primary purpose:

- **Data release:** data/evidence preservation or publication is the lead purpose.
- **Analysis code:** reproducing a reported analysis is the lead purpose.
- **Scraping/collection tooling:** a reusable collector, inspector, or public auditing utility is the lead purpose.
- **Infrastructure:** newsroom publishing, development, design, or internal tooling is the lead purpose.

Mixed repos were forced into one class by their declared lead purpose so the distribution is mutually exclusive.

| Primary class | Repos | Share |
|---|---:|---:|
| Data release | 47 | 56.0% |
| Analysis code | 26 | 31.0% |
| Scraping/collection tooling | 7 | 8.3% |
| Infrastructure | 4 | 4.8% |
| **Total** | **84** | **100.0%** |

README text states at least one Markup story link for **75/84 repositories (89.3%)**. The complete repo→story map appears in Appendix B and is preserved with all links in [the raw inventory](raw/github-repo-inventory.json).

License detection is uneven:

| API/README license result | Repos |
|---|---:|
| No license detected | 49 |
| BSD-3-Clause | 26 |
| `NOASSERTION` | 4 |
| GPL-3.0 | 3 |
| Apache-2.0 | 1 |
| MIT | 1 |
| **Total** | **84** |

"No license detected" is not a statement that the code is public domain or may be reused without restriction. `NOASSERTION` means GitHub detected licensing material but did not resolve an SPDX identifier.

## 5. Awards census

The live [Awards page](https://themarkup.org/awards) contains **33 structural entries**:

| Page year | Linked announcement cards | Unlinked list entries | Total entries |
|---:|---:|---:|---:|
| 2021 | 0 | 4 | 4 |
| 2022 | 2 | 9 | 11 |
| 2023 | 10 | 0 | 10 |
| 2024 | 8 | 0 | 8 |
| **Total** | **20** | **13** | **33** |

This is **not** a count of individual prizes. A single entry can announce several prizes ("wins six awards"), while an unlinked bullet may represent an award, finalist placement, or honorable mention. The correct auditable unit is therefore "entry on the awards page."

Seventeen of the 20 linked announcements can be mapped to at least one bounded project series from their prose **[inferred]**. Counting announcement entries that mention each project—not prizes—produces: Still Loading 10; Pixel Hunt 5; Languages of Misinformation 3; Digital Book Banning 2; and one each for Automated Censorship, Blacklight, Neighborhood Watch, Working for an Algorithm, Citizen Browser, Prediction: Bias, and Amazon's Advantage. Three linked entries concern an individual, institutional/media-literacy work, or the standalone L.A. homelessness scoring investigation rather than a bounded series. The 13 unlinked bullets do not support project mapping from the page itself.

The page stops at 2024 even though the live corpus contains later award announcements, including a [2025 Sigma finalist item](https://themarkup.org/inside-the-markup/2025/05/13/the-markup-named-sigma-award-finalist) and a [2026 SABEW win](https://themarkup.org/inside-the-markup/2026/03/30/the-markup-wins-sabew-award-for-best-in-business-journalism). Those later pages are **not added** to the 33-entry page census; their absence is an index-staleness bias. Appendix C preserves every page entry and the linked-announcement mapping.

## 6. Portfolio distribution

The 23 bounded project series have **307 series-membership occurrences across 293 distinct article URLs**. Three of those 293 are institutional award posts tagged across projects; removing them leaves **290 mutually exclusive substantive project pages**.

| Cluster [inferred] | Bounded series | Series count | Membership sum | Exclusive substantive pages | Share of 290 | Famous-frame covered / missed |
|---|---|---:|---:|---:|---:|---:|
| **C1. Platform ranking, moderation & information ecosystems** | Automated Censorship, Citizen Browser, Google the Giant, Languages of Misinformation | 4 | 88 | 84 | 29.0% | 62 / 22 |
| **C2. Privacy, tracking & data brokerage** | Blacklight, Pixel Hunt | 2 | 53 | 51 | 17.6% | 51 / 0 |
| **C3. Public-sector & institutional decision systems** | Digital Book Banning, Neighborhood Watch, Prediction: Bias, Remote Justice | 4 | 24 | 22 | 7.6% | 19 / 3 |
| **C4. Platform labor & worker surveillance** | Working for an Algorithm | 1 | 17 | 16 | 5.5% | 16 / 0 |
| **C5. Housing, lending, insurance & consumer scoring** | Allstate’s Algorithm, Denied, Locked Out, Premium Penalty | 4 | 36 | 31 | 10.7% | 6 / 25 |
| **C6. Digital access & public-service infrastructure** | Coronavirus, Still Loading | 2 | 52 | 49 | 16.9% | 18 / 31 |
| **C7. E-commerce, advertising & market power** | Amazon’s Advantage, Banned Bounty | 2 | 14 | 14 | 4.8% | 9 / 5 |
| **C8. Health allocation & care technology** | On Borrowed Time, Organ Failure | 2 | 11 | 11 | 3.8% | 8 / 3 |
| **C9. Elections & political influence** | Election 2020, Election 2026 | 2 | 12 | 12 | 4.1% | 0 / 12 |
| **X0 institutional/meta cross-tags** | Award announcements spanning projects | — | — | 3 | — | 3 / 0 |

The top three clusters by exclusive page volume—C1 platform systems (84), C2 privacy/tracking (51), and C6 digital access/public services (49)—contain **184/290 = 63.4%** of substantive project pages while accounting for **8/23 = 34.8%** of bounded project series. C1 alone is **84/290 = 29.0%**. The portfolio is therefore much more concentrated by article volume than by number of named projects.

The project frame itself covers only **293/835 = 35.1%** of all dated pages. The other 542 pages live only in broad beats, newsletters, explainers, methods, news/impact, or institutional channels—or in the 17 archive-only untagged pages. Frequencies computed only from named projects describe the investigation portfolio, not the whole publication.

## 7. Coverage diff: the empirically derived "famous work" frame

The fame frame is not a memory list. It is the union of:

1. bounded projects in the live homepage's persistent "Investigations and Tools" links;
2. bounded projects named in the Awards-page introduction;
3. bounded projects named in linked award announcements; and
4. the three-page, Sigma-winning L.A. homelessness scoring project, which lacks a bounded series.

This yields **13 famous bounded series**: Amazon's Advantage; Automated Censorship; Blacklight; Citizen Browser; Denied; Digital Book Banning; Languages of Misinformation; Neighborhood Watch; Organ Failure; Pixel Hunt; Prediction: Bias; Still Loading; and Working for an Algorithm. `Split Screen` is captured as two pages inside Citizen Browser, not inflated into a separate series.

Coverage:

| Denominator | Covered | Missed | Coverage |
|---|---:|---:|---:|
| Bounded project series | 13 | 10 | 56.5% |
| All dated article URLs | 195 | 640 | 23.4% |
| Project-tagged URLs plus 3-page standalone L.A. project | 195 | 101 | 65.9% |

The 10 missed project series are **Allstate's Algorithm, Banned Bounty, Coronavirus, Election 2020, Election 2026, Google the Giant, Locked Out, On Borrowed Time, Premium Penalty, and Remote Justice**. The famous frame therefore captures nearly two-thirds of the project core but less than one-quarter of the full publication and entirely misses several evidence-rich families.

## 8. Ranked second-wave extraction recommendations

To make "second wave" operational, the ranking uses **famous-frame-missed exclusive pages × evidentiary-distinctiveness weight [inferred]**. Weight 3 means the cluster contains original, reusable structured evidence or audit instruments; weight 2 means its strongest contribution is mixed documentary/qualitative evidence. Ties break on missed volume, then full cluster volume. This ranks overlooked evidence families above already famous clusters even when the famous cluster is large.

| Rank | Cluster [inferred] | Full exclusive pages | Fame-frame missed pages | Evidence weight [inferred] | Score [inferred] | Suggested file |
|---:|---|---:|---:|---:|---:|---|
| 1 | C6 Digital access & public-service infrastructure | 49 | 31 | 3 | 93 | `report-11-digital-access-public-services.md` |
| 2 | C5 Housing, lending, insurance & consumer scoring | 31 | 25 | 3 | 75 | `report-12-housing-lending-insurance-scoring.md` |
| 3 | C1 Platform ranking, moderation & information ecosystems | 84 | 22 | 3 | 66 | `report-13-platform-ranking-moderation.md` |
| 4 | C9 Elections & political influence | 12 | 12 | 2 | 24 | `report-14-elections-political-influence.md` |
| 5 | C7 E-commerce, advertising & market power | 14 | 5 | 3 | 15 | `report-15-ecommerce-market-power.md` |
| 6 | C3 Public-sector & institutional decision systems | 22 | 3 | 3 | 9 | `report-16-public-sector-decision-systems.md` |
| 7 | C8 Health allocation & care technology | 11 | 3 | 2 | 6 | `report-17-health-allocation-care-tech.md` |
| 8 | C2 Privacy, tracking & data brokerage | 51 | 0 | 3 | 0 | `report-18-privacy-tracking-data-brokerage.md` |
| 9 | C4 Platform labor & worker surveillance | 16 | 0 | 2 | 0 | `report-19-platform-labor-worker-surveillance.md` |

### 1. C6 Digital access & public-service infrastructure [inferred]

**Suggested file:** `report-11-digital-access-public-services.md`

**Why this rank:** 31 famous-frame-missed pages × weight 3 = **93**. Full exclusive cluster volume is 49 pages.

**Distinctive evidence/method:** Address-level offer collection, representative place sampling, public-benefit website testing, state plan comparison, accessibility testing, and story recipes. [inferred]

**Seed URLs:**

- [themarkup.org/series/coronavirus](https://themarkup.org/series/coronavirus)
- [themarkup.org/series/still-loading](https://themarkup.org/series/still-loading)
- [themarkup.org/coronavirus/2020/05/07/how-unemployment-systems-are-failing-workers-around-the-nation](https://themarkup.org/coronavirus/2020/05/07/how-unemployment-systems-are-failing-workers-around-the-nation)
- [themarkup.org/coronavirus/2020/04/21/blind-users-struggle-with-state-coronavirus-websites](https://themarkup.org/coronavirus/2020/04/21/blind-users-struggle-with-state-coronavirus-websites)
- [themarkup.org/still-loading/2022/10/19/dollars-to-megabits-you-may-be-paying-400-times-as-much-as-your-neighbor-for-internet-service](https://themarkup.org/still-loading/2022/10/19/dollars-to-megabits-you-may-be-paying-400-times-as-much-as-your-neighbor-for-internet-service)
- [themarkup.org/show-your-work/2022/10/19/how-we-uncovered-disparities-in-internet-deals](https://themarkup.org/show-your-work/2022/10/19/how-we-uncovered-disparities-in-internet-deals)
- [github.com/the-markup/investigation-isp](https://github.com/the-markup/investigation-isp)

### 2. C5 Housing, lending, insurance & consumer scoring [inferred]

**Suggested file:** `report-12-housing-lending-insurance-scoring.md`

**Why this rank:** 25 famous-frame-missed pages × weight 3 = **75**. Full exclusive cluster volume is 31 pages.

**Distinctive evidence/method:** HMDA regression, insurance-territory and pricing analysis, tenant-screening records, litigation/regulatory filings, and reproducible disparity tests. [inferred]

**Seed URLs:**

- [themarkup.org/allstates-algorithm/2020/02/25/car-insurance-suckers-list](https://themarkup.org/allstates-algorithm/2020/02/25/car-insurance-suckers-list)
- [themarkup.org/denied/2021/08/25/the-secret-bias-hidden-in-mortgage-approval-algorithms](https://themarkup.org/denied/2021/08/25/the-secret-bias-hidden-in-mortgage-approval-algorithms)
- [themarkup.org/locked-out/2020/05/28/access-denied-faulty-automated-background-checks-freeze-out-renters](https://themarkup.org/locked-out/2020/05/28/access-denied-faulty-automated-background-checks-freeze-out-renters)
- [themarkup.org/premium-penalty/2024/07/18/michigans-fair-and-reasonable-reforms-allowed-car-insurers-to-charge-more-in-black-neighborhoods](https://themarkup.org/premium-penalty/2024/07/18/michigans-fair-and-reasonable-reforms-allowed-car-insurers-to-charge-more-in-black-neighborhoods)
- [themarkup.org/show-your-work/2021/08/25/how-we-investigated-racial-disparities-in-federal-mortgage-data](https://themarkup.org/show-your-work/2021/08/25/how-we-investigated-racial-disparities-in-federal-mortgage-data)
- [themarkup.org/show-your-work/2020/05/28/how-we-investigated-the-tenant-screening-industry](https://themarkup.org/show-your-work/2020/05/28/how-we-investigated-the-tenant-screening-industry)
- [github.com/the-markup/investigate-mi-insurance-territories](https://github.com/the-markup/investigate-mi-insurance-territories)

### 3. C1 Platform ranking, moderation & information ecosystems [inferred]

**Suggested file:** `report-13-platform-ranking-moderation.md`

**Why this rank:** 22 famous-frame-missed pages × weight 3 = **66**. Full exclusive cluster volume is 84 pages.

**Distinctive evidence/method:** Representative-panel browser telemetry, feed comparison, search-result auditing, ad-placement blocklists, and multilingual community sourcing. [inferred]

**Seed URLs:**

- [themarkup.org/automated-censorship/2024/02/25/demoted-deleted-and-denied-theres-more-than-just-shadowbanning-on-instagram](https://themarkup.org/automated-censorship/2024/02/25/demoted-deleted-and-denied-theres-more-than-just-shadowbanning-on-instagram)
- [themarkup.org/automated-censorship/2024/02/25/how-we-investigated-shadowbanning-on-instagram](https://themarkup.org/automated-censorship/2024/02/25/how-we-investigated-shadowbanning-on-instagram)
- [themarkup.org/google-the-giant/2020/07/28/google-search-results-prioritize-google-products-over-competitors](https://themarkup.org/google-the-giant/2020/07/28/google-search-results-prioritize-google-products-over-competitors)
- [themarkup.org/google-the-giant/2020/07/28/how-we-analyzed-google-search-results-web-assay-parsing-tool](https://themarkup.org/google-the-giant/2020/07/28/how-we-analyzed-google-search-results-web-assay-parsing-tool)
- [themarkup.org/citizen-browser/2021/01/05/how-we-built-a-facebook-inspector](https://themarkup.org/citizen-browser/2021/01/05/how-we-built-a-facebook-inspector)
- [themarkup.org/citizen-browser/2021/03/11/split-screen](https://themarkup.org/citizen-browser/2021/03/11/split-screen)
- [themarkup.org/languages-of-misinformation/2023/06/09/vietnamese-youtuber-is-filling-information-voids-with-newsmax-and-breitbart](https://themarkup.org/languages-of-misinformation/2023/06/09/vietnamese-youtuber-is-filling-information-voids-with-newsmax-and-breitbart)

### 4. C9 Elections & political influence [inferred]

**Suggested file:** `report-14-elections-political-influence.md`

**Why this rank:** 12 famous-frame-missed pages × weight 2 = **24**. Full exclusive cluster volume is 12 pages.

**Distinctive evidence/method:** Campaign-ad pricing experiments, voter-site availability tests, voting-machine inventories, political-spending trails, and influence-site provenance. [inferred]

**Seed URLs:**

- [themarkup.org/series/election-2020](https://themarkup.org/series/election-2020)
- [themarkup.org/series/election-2026](https://themarkup.org/series/election-2026)
- [themarkup.org/election-2020/2020/10/29/facebook-political-ad-targeting-algorithm-prices-trump-biden](https://themarkup.org/election-2020/2020/10/29/facebook-political-ad-targeting-algorithm-prices-trump-biden)
- [themarkup.org/show-your-work/2020/10/29/how-we-analyzed-the-cost-of-trumps-and-bidens-campaign-ads-on-facebook](https://themarkup.org/show-your-work/2020/10/29/how-we-analyzed-the-cost-of-trumps-and-bidens-campaign-ads-on-facebook)
- [themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures](https://themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures)
- [themarkup.org/news/2026/01/05/could-this-mysterious-california-news-site-influence-the-2026-election](https://themarkup.org/news/2026/01/05/could-this-mysterious-california-news-site-influence-the-2026-election)
- [themarkup.org/election-2026/2026/03/09/it-was-john-waynes-political-club-now-its-spending-millions-on-online-influence](https://themarkup.org/election-2026/2026/03/09/it-was-john-waynes-political-club-now-its-spending-millions-on-online-influence)

### 5. C7 E-commerce, advertising & market power [inferred]

**Suggested file:** `report-15-ecommerce-market-power.md`

**Why this rank:** 5 famous-frame-missed pages × weight 3 = **15**. Full exclusive cluster volume is 14 pages.

**Distinctive evidence/method:** Large-scale product/search snapshots, Buy Box and ranking experiments, prohibited-item classification, screenshots, and antitrust follow-through. [inferred]

**Seed URLs:**

- [themarkup.org/series/amazons-advantage](https://themarkup.org/series/amazons-advantage)
- [themarkup.org/series/banned-bounty](https://themarkup.org/series/banned-bounty)
- [themarkup.org/banned-bounty/2020/06/18/amazons-enforcement-failures-leave-open-a-back-door](https://themarkup.org/banned-bounty/2020/06/18/amazons-enforcement-failures-leave-open-a-back-door)
- [themarkup.org/show-your-work/2020/06/18/how-we-investigated-banned-items-on-amazon-com](https://themarkup.org/show-your-work/2020/06/18/how-we-investigated-banned-items-on-amazon-com)
- [themarkup.org/amazons-advantage/2021/10/14/amazon-puts-its-own-brands-first-above-better-rated-products](https://themarkup.org/amazons-advantage/2021/10/14/amazon-puts-its-own-brands-first-above-better-rated-products)
- [themarkup.org/amazons-advantage/2021/10/14/how-we-analyzed-amazons-treatment-of-its-brands-in-search-results](https://themarkup.org/amazons-advantage/2021/10/14/how-we-analyzed-amazons-treatment-of-its-brands-in-search-results)
- [github.com/the-markup/investigation-amazon-brands](https://github.com/the-markup/investigation-amazon-brands)

### 6. C3 Public-sector & institutional decision systems [inferred]

**Suggested file:** `report-16-public-sector-decision-systems.md`

**Why this rank:** 3 famous-frame-missed pages × weight 3 = **9**. Full exclusive cluster volume is 22 pages.

**Distinctive evidence/method:** FOIA/public-records audits, algorithm-output validation against observed events, court/process comparisons, and crowdsourced school tests. [inferred]

**Seed URLs:**

- [themarkup.org/digital-book-banning/2024/04/13/schools-were-just-supposed-to-block-porn-instead-they-sabotaged-homework-and-censored-suicide-prevention-sites](https://themarkup.org/digital-book-banning/2024/04/13/schools-were-just-supposed-to-block-porn-instead-they-sabotaged-homework-and-censored-suicide-prevention-sites)
- [themarkup.org/show-your-work/2024/04/13/how-we-investigated-web-censorship-in-schools](https://themarkup.org/show-your-work/2024/04/13/how-we-investigated-web-censorship-in-schools)
- [themarkup.org/neighborhood-watch/2023/10/11/amazons-neighborhood-watch-might-be-turning-police-officers-into-reddit-moderators](https://themarkup.org/neighborhood-watch/2023/10/11/amazons-neighborhood-watch-might-be-turning-police-officers-into-reddit-moderators)
- [themarkup.org/neighborhood-watch/2023/10/11/how-we-investigated-rings-crime-alert-system-for-police-departments](https://themarkup.org/neighborhood-watch/2023/10/11/how-we-investigated-rings-crime-alert-system-for-police-departments)
- [themarkup.org/prediction-bias/2023/10/02/predictive-policing-software-terrible-at-predicting-crimes](https://themarkup.org/prediction-bias/2023/10/02/predictive-policing-software-terrible-at-predicting-crimes)
- [themarkup.org/show-your-work/2023/10/02/how-we-assessed-the-accuracy-of-predictive-policing-software](https://themarkup.org/show-your-work/2023/10/02/how-we-assessed-the-accuracy-of-predictive-policing-software)
- [themarkup.org/remote-justice/2022/03/16/payday-lenders-are-big-winners-in-utahs-chatroom-justice-program](https://themarkup.org/remote-justice/2022/03/16/payday-lenders-are-big-winners-in-utahs-chatroom-justice-program)

### 7. C8 Health allocation & care technology [inferred]

**Suggested file:** `report-17-health-allocation-care-tech.md`

**Why this rank:** 3 famous-frame-missed pages × weight 2 = **6**. Full exclusive cluster volume is 11 pages.

**Distinctive evidence/method:** Transplant allocation simulation/normalization, procurement and policy emails, geography/race outcome analysis, and patient-navigation evidence. [inferred]

**Seed URLs:**

- [themarkup.org/series/organ-failure](https://themarkup.org/series/organ-failure)
- [themarkup.org/series/on-borrowed-time](https://themarkup.org/series/on-borrowed-time)
- [themarkup.org/organ-failure/2023/03/21/poorer-states-suffer-under-new-organ-donation-rules-as-livers-go-to-waste](https://themarkup.org/organ-failure/2023/03/21/poorer-states-suffer-under-new-organ-donation-rules-as-livers-go-to-waste)
- [themarkup.org/organ-failure/2024/02/08/a-death-sentence-native-americans-shut-out-of-the-nations-liver-transplant-system](https://themarkup.org/organ-failure/2024/02/08/a-death-sentence-native-americans-shut-out-of-the-nations-liver-transplant-system)
- [themarkup.org/show-your-work/2023/03/21/how-we-investigated-unoss-liver-allocation-policy](https://themarkup.org/show-your-work/2023/03/21/how-we-investigated-unoss-liver-allocation-policy)
- [themarkup.org/on-borrowed-time/2025/10/14/is-the-patient-black-check-this-box-for-yes](https://themarkup.org/on-borrowed-time/2025/10/14/is-the-patient-black-check-this-box-for-yes)
- [github.com/the-markup/investigation-organs](https://github.com/the-markup/investigation-organs)

### 8. C2 Privacy, tracking & data brokerage [inferred]

**Suggested file:** `report-18-privacy-tracking-data-brokerage.md`

**Why this rank:** 0 famous-frame-missed pages × weight 3 = **0**. Full exclusive cluster volume is 51 pages.

**Distinctive evidence/method:** Instrumented tracker scans, controlled form submissions, network-request inspection, and reusable privacy-inspection code/data. [inferred]

**Seed URLs:**

- [themarkup.org/series/blacklight](https://themarkup.org/series/blacklight)
- [themarkup.org/series/pixel-hunt](https://themarkup.org/series/pixel-hunt)
- [themarkup.org/blacklight/2020/09/22/blacklight-tracking-advertisers-digital-privacy-sensitive-websites](https://themarkup.org/blacklight/2020/09/22/blacklight-tracking-advertisers-digital-privacy-sensitive-websites)
- [themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector)
- [themarkup.org/pixel-hunt/2022/06/16/facebook-is-receiving-sensitive-medical-information-from-hospital-websites](https://themarkup.org/pixel-hunt/2022/06/16/facebook-is-receiving-sensitive-medical-information-from-hospital-websites)
- [themarkup.org/show-your-work/2022/04/28/how-we-built-a-meta-pixel-inspector](https://themarkup.org/show-your-work/2022/04/28/how-we-built-a-meta-pixel-inspector)
- [github.com/the-markup/meta-pixel-student-aid](https://github.com/the-markup/meta-pixel-student-aid)

*Lower-priority consolidation note:* the empirical fame frame already covers every exclusive project page in this cluster; extract it after the missed-volume clusters unless the pattern library lacks its method family.

### 9. C4 Platform labor & worker surveillance [inferred]

**Suggested file:** `report-19-platform-labor-worker-surveillance.md`

**Why this rank:** 0 famous-frame-missed pages × weight 2 = **0**. Full exclusive cluster volume is 16 pages.

**Distinctive evidence/method:** Worker-supplied records, incident databases assembled across jurisdictions, subpoenas/police response timelines, and platform-pay rule reporting. [inferred]

**Seed URLs:**

- [themarkup.org/series/working-for-an-algorithm](https://themarkup.org/series/working-for-an-algorithm)
- [themarkup.org/working-for-an-algorithm/2022/03/01/secretive-algorithm-will-now-determine-uber-driver-pay-in-many-cities](https://themarkup.org/working-for-an-algorithm/2022/03/01/secretive-algorithm-will-now-determine-uber-driver-pay-in-many-cities)
- [themarkup.org/working-for-an-algorithm/2022/07/28/more-than-350-gig-workers-carjacked-28-killed-over-the-last-five-years](https://themarkup.org/working-for-an-algorithm/2022/07/28/more-than-350-gig-workers-carjacked-28-killed-over-the-last-five-years)
- [themarkup.org/working-for-an-algorithm/2022/04/06/more-than-50-u-s-gig-workers-murdered-on-the-job-in-five-years](https://themarkup.org/working-for-an-algorithm/2022/04/06/more-than-50-u-s-gig-workers-murdered-on-the-job-in-five-years)
- [themarkup.org/working-for-an-algorithm/2022/12/09/when-drivers-are-attacked-uber-leaves-police-waiting-for-help](https://themarkup.org/working-for-an-algorithm/2022/12/09/when-drivers-are-attacked-uber-leaves-police-waiting-for-help)
- [themarkup.org/working-for-an-algorithm/2024/09/04/california-companies-wrote-their-own-gig-worker-law-now-no-one-is-enforcing-it](https://themarkup.org/working-for-an-algorithm/2024/09/04/california-companies-wrote-their-own-gig-worker-law-now-no-one-is-enforcing-it)
- [themarkup.org/working-for-an-algorithm/2023/10/05/what-happens-when-nurses-are-hired-like-ubers](https://themarkup.org/working-for-an-algorithm/2023/10/05/what-happens-when-nurses-are-hired-like-ubers)

*Lower-priority consolidation note:* the empirical fame frame already covers every exclusive project page in this cluster; extract it after the missed-volume clusters unless the pattern library lacks its method family.

## 9. Sampling-frame biases

1. **No sitemap.** The Markup exposes neither a sitemap nor a master series directory. The union is the strongest available live-site frame, but a completely orphaned URL or series with no archive/series link can still be absent.
2. **The visible archive lies by omission.** It excludes 146 dated newsletter pages—17.5% of the 835-page union. An archive-only census would suppress 2019 entirely and undercount 2020–2022 most heavily.
3. **Newsletter pages are not necessarily independent stories.** The 146 recovered pages include newsletter renditions that can repeat, abridge, or point to a reported article. URL-level frequencies overstate independent reporting units if interpreted as semantic stories.
4. **Merger copies are separate pages, not migrations.** Old Markup URLs remain live; post-merger articles often have separately canonical CalMatters copies with altered slugs, titles, or dates. Adding both domains would double count. Conversely, the domain rule excludes CalMatters-only work by integrated-newsroom staff even if their institutional lineage is Markup.
5. **CalMatters search is censored/incomplete as an index.** Its 64-result "The Markup" WP search misses obvious parallel copies found in the full 3,733-post feed. It is useful for candidate review, not corpus enumeration.
6. **Translations and syndications alter the unit.** Spanish CalMatters variants and some multilingual Markup pages can represent a translation of another work while remaining distinct URLs. The attribution rule excludes CalMatters translation copies; the Markup-domain URL census retains Markup-hosted multilingual pages.
7. **Taxonomy terms are heterogeneous and overlapping.** A "series" may be an investigation, beat, newsletter, method, tool, year package, or impact channel. Summing 1,093 memberships would double count 818 pages. The 23-project backbone and all nine clusters are analytical **[inferred]**, not The Markup's own ontology.
8. **Series discovery can miss unlinked terms.** Forty-three is the complete set exposed in the crawled pages, not proof that no dormant/orphaned series route exists.
9. **Awards-page entries are not prizes.** Cards can announce multiple wins; bullets mix wins, finalists, and other honors. The page also stops at 2024 despite later award posts, biasing prominence toward 2022–2024 projects.
10. **The site-side dataset index under-surfaces GitHub.** `/data` and `/datasets` are dead routes. The 22 direct packages come from 28 methodology pages, while the organization has 84 repos. Treating the site-linked 22 as the full open-source corpus would miss 62 repos.
11. **License detection is not legal clearance.** Repository API labels and README scans can miss custom or nested license terms; absence of a detected license is substantively important.
12. **Unlike units cannot be added.** Article pages, series, dataset packages, repos, awards-page entries, and individual prizes answer different questions. A dataset repo may support several stories; a story may have several repos; a series may contain methods, impacts, newsletters, and awards.
13. **Current-year truncation.** The 2026 count ends July 28. It must not be compared with complete years as an annual rate without adjustment.
14. **The 2019 edge is pre-launch.** The single 2019 newsletter page expands the structural year span, but The Markup's own launch language says 2020. Both facts should be retained.

---

## Appendix A. Full site-series taxonomy and cluster coding

Every type and cluster assignment in this appendix is **[inferred]**. Article counts are direct distinct URL counts from each series pagination.

| Site series | Distinct URLs | Span | Analytical type [inferred] | Cluster [inferred] |
|---|---:|---|---|---|
| [2020 in Review](https://themarkup.org/series/2020-in-review) | 6 | 2020-12-15–2020-12-31 | year/review package | X0 Beat/format/umbrella/meta |
| [Allstate’s Algorithm](https://themarkup.org/series/allstates-algorithm) | 5 | 2020-02-25–2022-02-01 | bounded project/investigation | C5 Housing, lending, insurance & consumer scoring |
| [Amazon’s Advantage](https://themarkup.org/series/amazons-advantage) | 9 | 2021-10-14–2023-09-28 | bounded project/investigation | C7 E-commerce, advertising & market power |
| [Artificial Intelligence](https://themarkup.org/series/artificial-intelligence) | 36 | 2024-03-29–2026-07-09 | broad topic/beat | X0 Beat/format/umbrella/meta |
| [Automated Censorship](https://themarkup.org/series/automated-censorship) | 8 | 2024-02-25–2025-05-13 | bounded project/investigation | C1 Platform ranking, moderation & information ecosystems |
| [Banned Bounty](https://themarkup.org/series/banned-bounty) | 5 | 2020-06-18–2020-09-17 | bounded project/investigation | C7 E-commerce, advertising & market power |
| [Blacklight](https://themarkup.org/series/blacklight) | 14 | 2020-09-22–2026-02-09 | bounded project/investigation | C2 Privacy, tracking & data brokerage |
| [Blueprints](https://themarkup.org/series/blueprints) | 1 | 2024-01-31–2024-01-31 | resource format | X0 Beat/format/umbrella/meta |
| [Build Your Own Dataset](https://themarkup.org/series/build-your-own-dataset) | 1 | 2023-05-11–2023-05-11 | resource format | X0 Beat/format/umbrella/meta |
| [Citizen Browser](https://themarkup.org/series/citizen-browser) | 43 | 2021-01-05–2022-10-25 | bounded project/investigation | C1 Platform ranking, moderation & information ecosystems |
| [Coronavirus](https://themarkup.org/series/coronavirus) | 32 | 2020-03-19–2021-03-24 | bounded project/investigation | C6 Digital access & public-service infrastructure |
| [Data Is Plural](https://themarkup.org/series/data-is-plural) | 44 | 2022-05-11–2023-03-29 | newsletter/curation format | X0 Beat/format/umbrella/meta |
| [Denied](https://themarkup.org/series/denied) | 6 | 2021-08-25–2022-02-04 | bounded project/investigation | C5 Housing, lending, insurance & consumer scoring |
| [Digital Book Banning](https://themarkup.org/series/digital-book-banning) | 9 | 2024-04-13–2025-01-16 | bounded project/investigation | C3 Public-sector & institutional decision systems |
| [Election 2020](https://themarkup.org/series/election-2020) | 10 | 2020-09-10–2020-11-17 | bounded project/investigation | C9 Elections & political influence |
| [Election 2026](https://themarkup.org/series/election-2026) | 2 | 2026-01-05–2026-03-09 | bounded project/investigation | C9 Elections & political influence |
| [Gentle January](https://themarkup.org/series/gentle-january) | 22 | 2024-01-02–2024-01-31 | service package | X0 Beat/format/umbrella/meta |
| [Google the Giant](https://themarkup.org/series/google-the-giant) | 23 | 2020-02-26–2022-01-21 | bounded project/investigation | C1 Platform ranking, moderation & information ecosystems |
| [Hello World](https://themarkup.org/series/hello-world) | 221 | 2019-09-12–2026-06-30 | newsletter | X0 Beat/format/umbrella/meta |
| [Impact](https://themarkup.org/series/impact) | 94 | 2020-04-21–2026-04-17 | impact/update channel | X0 Beat/format/umbrella/meta |
| [Inside The Markup](https://themarkup.org/series/inside-the-markup) | 34 | 2022-10-06–2026-03-30 | institutional/meta channel | X0 Beat/format/umbrella/meta |
| [Investigations](https://themarkup.org/series/investigations) | 71 | 2020-02-25–2026-05-27 | umbrella channel | X0 Beat/format/umbrella/meta |
| [Languages of Misinformation](https://themarkup.org/series/languages-of-misinformation) | 14 | 2023-06-09–2024-09-26 | bounded project/investigation | C1 Platform ranking, moderation & information ecosystems |
| [LevelUp](https://themarkup.org/series/levelup) | 13 | 2022-10-27–2024-04-04 | service/resource format | X0 Beat/format/umbrella/meta |
| [Locked Out](https://themarkup.org/series/locked-out) | 13 | 2020-05-28–2024-12-02 | bounded project/investigation | C5 Housing, lending, insurance & consumer scoring |
| [Machine Learning](https://themarkup.org/series/machine-learning) | 20 | 2021-03-02–2026-03-07 | broad topic/beat | X0 Beat/format/umbrella/meta |
| [Mark As Read](https://themarkup.org/series/mark-as-read) | 8 | 2022-05-13–2022-07-22 | newsletter/curation format | X0 Beat/format/umbrella/meta |
| [Neighborhood Watch](https://themarkup.org/series/neighborhood-watch) | 6 | 2023-10-11–2024-01-24 | bounded project/investigation | C3 Public-sector & institutional decision systems |
| [News](https://themarkup.org/series/news) | 36 | 2020-11-24–2026-04-17 | news/update channel | X0 Beat/format/umbrella/meta |
| [On Borrowed Time](https://themarkup.org/series/on-borrowed-time) | 3 | 2025-10-14–2025-11-14 | bounded project/investigation | C8 Health allocation & care technology |
| [Organ Failure](https://themarkup.org/series/organ-failure) | 8 | 2023-03-21–2024-02-08 | bounded project/investigation | C8 Health allocation & care technology |
| [Pixel Hunt](https://themarkup.org/series/pixel-hunt) | 39 | 2022-01-21–2025-06-23 | bounded project/investigation | C2 Privacy, tracking & data brokerage |
| [Prediction: Bias](https://themarkup.org/series/prediction-bias) | 6 | 2021-12-02–2024-01-29 | bounded project/investigation | C3 Public-sector & institutional decision systems |
| [Premium Penalty](https://themarkup.org/series/premium-penalty) | 12 | 2020-02-25–2025-06-11 | bounded project/investigation | C5 Housing, lending, insurance & consumer scoring |
| [Privacy](https://themarkup.org/series/privacy) | 65 | 2021-03-25–2026-07-28 | broad topic/beat | X0 Beat/format/umbrella/meta |
| [Remote Justice](https://themarkup.org/series/remote-justice) | 3 | 2020-06-09–2022-03-30 | bounded project/investigation | C3 Public-sector & institutional decision systems |
| [Show Your Work](https://themarkup.org/series/show-your-work) | 28 | 2020-02-25–2026-01-21 | methodology/resource format | X0 Beat/format/umbrella/meta |
| [Still Loading](https://themarkup.org/series/still-loading) | 20 | 2022-04-12–2024-09-23 | bounded project/investigation | C6 Digital access & public-service infrastructure |
| [Story Recipes](https://themarkup.org/series/story-recipes) | 3 | 2022-10-19–2024-09-27 | methodology/resource format | X0 Beat/format/umbrella/meta |
| [The Breakdown](https://themarkup.org/series/the-breakdown) | 79 | 2020-02-25–2025-06-17 | explainer/service format | X0 Beat/format/umbrella/meta |
| [Tools](https://themarkup.org/series/tools) | 2 | 2023-05-11–2025-04-16 | tool/resource channel | X0 Beat/format/umbrella/meta |
| [Working for an Algorithm](https://themarkup.org/series/working-for-an-algorithm) | 17 | 2021-02-18–2024-10-16 | bounded project/investigation | C4 Platform labor & worker surveillance |
| [Year in Review](https://themarkup.org/series/year-in-review) | 2 | 2023-12-26–2024-01-11 | year/review package | X0 Beat/format/umbrella/meta |

## Appendix B. Complete GitHub repository inventory

The class is mutually exclusive and **[inferred]** from the repository's declared primary purpose. License values are API/README detections. Story mappings reproduce links stated in the README; `—` means no Markup story link was found there.

| Repository | Primary class [inferred] | License detected | README-stated Markup story link(s) |
|---|---|---|---|
| [Ad-Library-API-Script-Repository](https://github.com/the-markup/Ad-Library-API-Script-Repository) | scraping/collection tooling | NOASSERTION | — |
| [blacklight-collector](https://github.com/the-markup/blacklight-collector) | scraping/collection tooling | GPL-3.0 | — |
| [blacklight-query](https://github.com/the-markup/blacklight-query) | scraping/collection tooling | GPL-3.0 | — |
| [blacklight-reporter](https://github.com/the-markup/blacklight-reporter) | scraping/collection tooling | none detected | [The High Privacy Cost of a ‘Free’ Website](https://themarkup.org/blacklight/2020/09/22/blacklight-tracking-advertisers-digital-privacy-sensitive-websites) |
| [citizen-browser-antivaxx-groups](https://github.com/the-markup/citizen-browser-antivaxx-groups) | data release | none detected | ["Facebook Said It Would Stop Recommending Anti-Vaccine Groups. It Didn’t"](https://themarkup.org/citizen-browser/2021/05/20/facebook-said-it-would-stop-recommending-anti-vaccine-groups-it-didnt)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-capitol-riot](https://github.com/the-markup/citizen-browser-capitol-riot) | analysis code | none detected | [Biden and Trump Voters Were Exposed to Radically Different Coverage of the Capitol Riot on Facebook](https://themarkup.org/citizen-browser/2021/01/14/biden-and-trump-voters-were-exposed-to-radically-different-coverage-of-the-capitol-riot-on-facebook) |
| [citizen-browser-covid-public-info](https://github.com/the-markup/citizen-browser-covid-public-info) | data release | none detected | [Official Information About COVID-19 Is Reaching Fewer Black People on Facebook](https://themarkup.org/citizen-browser/2021/03/04/official-information-about-covid-19-is-reaching-fewer-black-people-on-facebook)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-daily-wire-targeting](https://github.com/the-markup/citizen-browser-daily-wire-targeting) | data release | BSD-3-Clause | ["How The Daily Wire Uses Facebook's Targeted Advertising to Build Its Brand"](https://themarkup.org/citizen-browser/2021/08/10/how-the-daily-wire-uses-facebooks-targeted-advertising-to-build-its-brand)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-fb-political-groups](https://github.com/the-markup/citizen-browser-fb-political-groups) | analysis code | none detected | [Facebook Said It Would Stop Pushing Users to Join Partisan Political Groups. It Didn’t.](https://themarkup.org/citizen-browser/2021/01/19/facebook-said-it-would-stop-pushing-users-to-join-partisan-political-groups-it-didnt)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-fb-political-groups-technical-difficulties](https://github.com/the-markup/citizen-browser-fb-political-groups-technical-difficulties) | data release | none detected | [Facebook Says 'Technical Issues' Were the Cause of Broken Promise to Congress](https://themarkup.org/citizen-browser/2021/02/12/facebook-says-technical-issues-were-the-cause-of-broken-promise-to-congress)<br>[Citizen Browser](https://themarkup.org/citizen-browser/)<br>[Facebook Said It Would Stop Pushing Users to Join Partisan Political Groups. It Didn’t.](https://themarkup.org/citizen-browser/2021/01/19/facebook-said-it-would-stop-pushing-users-to-join-partisan-political-groups-it-didnt) |
| [citizen-browser-fb-still-recommends-political-groups](https://github.com/the-markup/citizen-browser-fb-still-recommends-political-groups) | data release | BSD-3-Clause | ["After Repeatedly Promising Not to, Facebook Keeps Recommending Political Groups to Its Users"](https://themarkup.org/citizen-browser/2021/06/24/after-repeatedly-promising-not-to-facebook-keeps-recommending-political-groups-to-its-users)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-flags](https://github.com/the-markup/citizen-browser-flags) | data release | none detected | [Trump's False Posts Were Treated with Kid Gloves by Facebook](https://themarkup.org/citizen-browser/2021/02/16/trumps-false-posts-were-treated-with-kid-gloves-by-facebook) |
| [citizen-browser-georgia](https://github.com/the-markup/citizen-browser-georgia) | analysis code | none detected | [In Georgia, Facebook’s Changes Brought Back a Partisan News Feed](https://themarkup.org/citizen-browser/2021/01/05/in-georgia-facebooks-changes-brought-back-a-partisan-news-feed)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-hashtag-demographics](https://github.com/the-markup/citizen-browser-hashtag-demographics) | analysis code | none detected | [Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-jan6-2022](https://github.com/the-markup/citizen-browser-jan6-2022) | analysis code | BSD-3-Clause | [One Year After the Capitol Riot, Americans Still See Two Very Different Facebooks](https://themarkup.org/citizen-browser/2022/01/06/one-year-after-the-capitol-riot-americans-still-see-two-very-different-facebooks) |
| [citizen-browser-newsletter](https://github.com/the-markup/citizen-browser-newsletter) | data release | BSD-3-Clause | — |
| [citizen-browser-pharmaceuticals](https://github.com/the-markup/citizen-browser-pharmaceuticals) | data release | none detected | [How Big Pharma Finds Sick Users on Facebook](https://themarkup.org/citizen-browser/2021/05/06/how-big-pharma-finds-sick-users-on-facebook)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-political-groups-germany](https://github.com/the-markup/citizen-browser-political-groups-germany) | data release | BSD-3-Clause | ["Germany’s Far-Right Political Party, the AfD, Is Dominating Facebook This Election"](https://themarkup.org/citizen-browser/2021/09/22/germanys-far-right-political-party-the-afd-is-dominating-facebook-this-election)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [citizen-browser-widely-viewed-content](https://github.com/the-markup/citizen-browser-widely-viewed-content) | data release | BSD-3-Clause | [Facebook Isn’t Telling You How Popular Right-Wing Content Is on the Platform](https://themarkup.org/citizen-browser/2021/11/18/facebook-isnt-telling-you-how-popular-right-wing-content-is-on-the-platform)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [data-gig-worker-deaths](https://github.com/the-markup/data-gig-worker-deaths) | data release | BSD-3-Clause | [More Than 50 U.S. Gig Workers Murdered on the Job in Five Years](https://themarkup.org/working-for-an-algorithm/2022/04/06/more-than-50-u-s-gig-workers-murdered-on-the-job-in-five-years) |
| [facebook-removed-interests](https://github.com/the-markup/facebook-removed-interests) | data release | BSD-3-Clause | [Facebook Promised to Remove “Sensitive” Ads. Here’s What It Left Behind](https://themarkup.org/citizen-browser/2022/05/12/facebook-promised-to-remove-sensitive-ads-heres-what-it-left-behind)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [facebook-report-verification](https://github.com/the-markup/facebook-report-verification) | analysis code | BSD-3-Clause | [Facebook Isn’t Telling You How Popular Right-Wing Content Is on the Platform](https://themarkup.org/citizen-browser/2021/11/18/facebook-isnt-telling-you-how-popular-right-wing-content-is-on-the-platform)<br>[Citizen Browser](https://themarkup.org/citizen-browser/) |
| [graphics-template](https://github.com/the-markup/graphics-template) | infrastructure | none detected | — |
| [investigate-mi-insurance-territories](https://github.com/the-markup/investigate-mi-insurance-territories) | analysis code | BSD-3-Clause | [Michigan's 'Fair and Reasonable' Reforms Allowed Car Insurers to Charge More in Black Neighborhoods](https://mrkup.org/l5W6g) |
| [investigation-allstates-algorithm](https://github.com/the-markup/investigation-allstates-algorithm) | analysis code | none detected | ["Suckers List: How Allstate’s Secret Auto Insurance Algorithm Squeezes Big Spenders."](https://themarkup.org/allstates-algorithm/2020/02/25/car-insurance-suckers-list)<br>["How We Analyzed Allstate’s Car Insurance Algorithm."](https://themarkup.org/allstates-algorithm/2020/02/25/show-your-work-car-insurance-suckers-list) |
| [investigation-amazon-banned-items](https://github.com/the-markup/investigation-amazon-banned-items) | data release | none detected | [Amazon’s Enforcement Failures Leave Open a Seedy Back Door to Banned Goods—Some Sold and Shipped by Amazon Itself](https://themarkup.org/banned-bounty/2020/06/18/amazons-enforcement-failures-leave-open-a-back-door) |
| [investigation-amazon-banned-items-screenshots](https://github.com/the-markup/investigation-amazon-banned-items-screenshots) | data release | none detected | [Amazon’s Enforcement Failures Leave Open a Seedy Back Door to Banned Goods—Some Sold and Shipped by Amazon Itself](https://themarkup.org/banned-bounty/2020/06/18/amazons-enforcement-failures-leave-open-a-back-door) |
| [investigation-amazon-brands](https://github.com/the-markup/investigation-amazon-brands) | analysis code | BSD-3-Clause | [Amazon Puts Its Own 'Brands' First Above Better-Rated Products](https://themarkup.org/amazons-advantage/2021/10/14/amazon-puts-its-own-brands-first-above-better-rated-products)<br>[When Amazon Takes the Buy Box, it Doesn’t Give it up](https://themarkup.org/amazons-advantage/2021/10/14/when-amazon-takes-the-buy-box-it-doesnt-give-it-up) |
| [investigation-amazon-covid](https://github.com/the-markup/investigation-amazon-covid) | analysis code | BSD-3-Clause | [Amazon Is Rolling Back COVID Protocols in Its Warehouses. Workers Say It’s Premature](https://themarkup.org/2021/12/21/amazon-is-rolling-back-covid-protocols-in-its-warehouses-workers-say-its-premature) |
| [investigation-amazon-covid-notifications](https://github.com/the-markup/investigation-amazon-covid-notifications) | data release | BSD-3-Clause | [Data Provided by Amazon Workers Offers Rare Glimpse into COVID Cases in California Warehouses](https://themarkup.org/working-for-an-algorithm/2022/02/10/data-provided-by-amazon-workers-offers-rare-glimpse-into-covid-cases-in-california-warehouses) |
| [investigation-amazon-peptides](https://github.com/the-markup/investigation-amazon-peptides) | data release | none detected | [Labeled “Research” Chemicals, Doping Drugs Sold Openly on Amazon.com](https://themarkup.org/banned-bounty/2020/09/17/amazon-sales-peptides-doping-drugs) |
| [investigation-blacklight-the-high-cost-of-free](https://github.com/the-markup/investigation-blacklight-the-high-cost-of-free) | analysis code | none detected | [The High Privacy Cost of a ‘Free’ Website](https://themarkup.org/blacklight/2020/09/22/blacklight-tracking-advertisers-digital-privacy-sensitive-websites)<br>[Show Your Work](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector#survey) |
| [investigation-covered-california-linkedin-tracker](https://github.com/the-markup/investigation-covered-california-linkedin-tracker) | data release | BSD-3-Clause | ["How California sent residents’ personal health data to LinkedIn"](https://themarkup.org/pixel-hunt/2025/04/28/how-california-sent-residents-personal-health-data-to-linkedin) |
| [investigation-covid19-testing-guidelines](https://github.com/the-markup/investigation-covid19-testing-guidelines) | data release | none detected | ["How We Analyzed States’ Coronavirus Testing Plans"](https://themarkup.org/coronavirus/2020/04/16/how-we-analyzed-states-coronavirus-testing-plans) |
| [investigation-d2c-privacy](https://github.com/the-markup/investigation-d2c-privacy) | data release | none detected | ['Out of control': Dozens of telehealth startups sent sensitive health information to big tech companies](https://themarkup.org/privacy/2022/12/13/out-of-control-dozens-of-telehealth-startups-sent-sensitive-health-information-to-big-tech-companies) |
| [investigation-data-broker-lobbying](https://github.com/the-markup/investigation-data-broker-lobbying) | analysis code | none detected | [The Little-Known Data Broker Industry Is Spending Big Bucks Lobbying Congress](https://themarkup.org/privacy/2021/04/01/the-little-known-data-broker-industry-is-spending-big-bucks-lobbying-congress) |
| [investigation-data-broker-opt-out-pages](https://github.com/the-markup/investigation-data-broker-opt-out-pages) | data release | Apache-2.0 | ["We caught companies making it harder to delete your personal data online"](https://themarkup.org/privacy/2025/08/12/we-caught-companies-making-it-harder-to-delete-your-data) |
| [investigation-drug-store-website-tracking](https://github.com/the-markup/investigation-drug-store-website-tracking) | data release | none detected | [Need to Get Plan B or an HIV Test Online? Facebook May Know About It](https://themarkup.org/pixel-hunt/2023/06/30/need-to-get-plan-b-or-an-hiv-test-online-facebook-may-know-about-it) |
| [investigation-ebb-lifeline](https://github.com/the-markup/investigation-ebb-lifeline) | data release | BSD-3-Clause | — |
| [investigation-fb-ads-biden-trump-pricing](https://github.com/the-markup/investigation-fb-ads-biden-trump-pricing) | analysis code | none detected | [Facebook Charged Biden a Higher Price Than Trump for Campaign Ads](https://themarkup.org/election-2020/2020/10/29/facebook-political-ad-targeting-algorithm-prices-trump-biden) |
| [investigation-florida-online-attendance](https://github.com/the-markup/investigation-florida-online-attendance) | analysis code | none detected | [Remote Learning During the Pandemic Has Hit Vulnerable Students the Hardest.](https://themarkup.org/coronavirus/2020/08/13/remote-learning-attendance-inequity-florida-schools) |
| [investigation-geolitica-plainfield](https://github.com/the-markup/investigation-geolitica-plainfield) | analysis code | none detected | ["Predictive Policing Software Terrible At Predicting Crimes."](https://themarkup.org/prediction-bias/2023/10/02/predictive-policing-software-terrible-at-predicting-crimes) |
| [investigation-gig-carjacking](https://github.com/the-markup/investigation-gig-carjacking) | data release | BSD-3-Clause | [More Than 350 Gig Workers Carjacked, 28 Killed, Over the Last Five Years](https://themarkup.org/working-for-an-algorithm/2022/07/28/more-than-350-gig-workers-carjacked-28-killed-over-the-last-five-years)<br>[Uber And Lyft Drivers Are Being Carjacked at Alarming Rates](https://themarkup.org/working-for-an-algorithm/2021/07/22/uber-and-lyft-drivers-are-being-carjacked-at-alarming-rates)<br>[When Drivers Are Attacked, Uber Leaves Police Waiting for Help](https://themarkup.org/working-for-an-algorithm/2022/12/09/when-drivers-are-attacked-uber-leaves-police-waiting-for-help) |
| [investigation-gig-spending](https://github.com/the-markup/investigation-gig-spending) | data release | BSD-3-Clause | [Uber and Lyft Donated to Community Groups Who Then Pushed the Companies’ Agenda](https://themarkup.org/news/2021/06/17/uber-and-lyft-donated-to-community-groups-who-then-pushed-the-companies-agenda) |
| [investigation-google-keyword-planner](https://github.com/the-markup/investigation-google-keyword-planner) | analysis code | none detected | [Google Ad Portal Equated 'Black Girls' With Porn](https://themarkup.org/google-the-giant/2020/07/23/google-advertising-keywords-black-girls) |
| [investigation-google-search-audit](https://github.com/the-markup/investigation-google-search-audit) | analysis code | none detected | [Google’s Top Search Result? Surprise! It’s Google](https://themarkup.org/google-the-giant/2020/07/28/google-search-results-prioritize-google-products-over-competitors) |
| [investigation-healthcare-exchange-tracking](https://github.com/the-markup/investigation-healthcare-exchange-tracking) | data release | BSD-3-Clause | ["We caught 4 more states sharing personal health data with Big Tech"](https://themarkup.org/pixel-hunt/2025/06/17/we-caught-4-more-states-sharing-personal-health-data-with-big-tech)<br>["How California sent residents’ personal health data to LinkedIn"](https://themarkup.org/pixel-hunt/2025/04/28/how-california-sent-residents-personal-health-data-to-linkedin) |
| [investigation-isp](https://github.com/the-markup/investigation-isp) | analysis code | BSD-3-Clause | [Dollars to Megabits: You May Be Paying 400 Times As Much As Your Neighbor for Internet](https://themarkup.org/still-loading/2022/10/19/dollars-to-megabits-you-may-be-paying-400-times-as-much-as-your-neighbor-for-internet-service)<br>[story recipe](https://themarkup.org/story-recipes/2022/10/19/journalists-investigate-which-neighborhoods-in-your-city-are-offered-the-worst-internet-deals) |
| [investigation-meta-political-violence-ads](https://github.com/the-markup/investigation-meta-political-violence-ads) | data release | none detected | [How Meta Brings in Millions Off Political Violence](https://themarkup.org/investigations/2024/10/04/how-meta-brings-in-millions-off-political-violence) |
| [investigation-nonprofit-privacy](https://github.com/the-markup/investigation-nonprofit-privacy) | analysis code | none detected | [Nonprofit Websites Are Riddled With Ad Trackers](https://themarkup.org/) |
| [investigation-nyc-high-school-admissions](https://github.com/the-markup/investigation-nyc-high-school-admissions) | analysis code | BSD-3-Clause | [NYC’s School Algorithms Cement Segregation. This Data Shows How](https://themarkup.org/investigation/2021/05/26/nycs-school-algorithms-cement-segregation-this-data-shows-how) |
| [investigation-organs](https://github.com/the-markup/investigation-organs) | analysis code | BSD-3-Clause | [our investigation on liver transplants](https://themarkup.org/organ-failure/2023/03/21/poorer-states-suffer-under-new-organ-donation-rules-as-livers-go-to-waste)<br>[a subsequent investigation on racial inequities in the liver transplant system](https://themarkup.org/organ-failure/2024/02/08/a-death-sentence-native-americans-shut-out-of-the-nations-liver-transplant-system) |
| [investigation-pixel-hospitals](https://github.com/the-markup/investigation-pixel-hospitals) | data release | none detected | ["Facebook is Receiving Sensitive Medical Information from Hospital Websites."](https://themarkup.org/pixel-hunt/2022/06/16/facebook-is-receiving-sensitive-medical-information-from-hospital-websites) |
| [investigation-prediction-bias](https://github.com/the-markup/investigation-prediction-bias) | analysis code | BSD-3-Clause | [investigation](https://themarkup.org/prediction-bias/2021/12/02/crime-prediction-software-promised-to-be-free-of-biases-new-data-shows-it-perpetuates-them) |
| [investigation-redlining](https://github.com/the-markup/investigation-redlining) | analysis code | none detected | [The Secret Bias Hidden in Mortgage-Approval Algorithms](https://themarkup.org/denied/2021/08/25/the-secret-bias-hidden-in-mortgage-approval-algorithms)<br>[Dozens of Mortgage Lenders Showed Significant Disparities; Here Are the Worst](https://themarkup.org/denied/2021/08/25/dozens-of-mortgage-lenders-showed-significant-disparities-here-are-the-worst) |
| [investigation-tenant-screening](https://github.com/the-markup/investigation-tenant-screening) | data release | none detected | [Access Denied: Faulty Automated Background Checks Freeze Out Renters](https://themarkup.org/locked-out/2020/05/28/access-denied-faulty-automated-background-checks-freeze-out-renters)<br>[Locked Out](https://themarkup.org/locked-out/) |
| [investigation-twitter-patreon](https://github.com/the-markup/investigation-twitter-patreon) | data release | none detected | [Twitter is Throttling Patreon Links, Creators Say It Undermines Their Livelihood](https://themarkup.org/news/2023/10/16/twitter-is-throttling-patreon-links-creators-say-it-undermines-their-livelihood)<br>[The Markup reported](https://themarkup.org/investigations/2023/09/15/twitter-is-still-throttling-competitors-links-check-for-yourself) |
| [investigation-twitter-throttle](https://github.com/the-markup/investigation-twitter-throttle) | data release | none detected | [Twitter is Still Throttling Competitors’ Links](https://themarkup.org/2023/09/15/twitter-is-still-throttling-competitors-links-check-for-yourself) |
| [investigation-unemployment-wait-times](https://github.com/the-markup/investigation-unemployment-wait-times) | data release | none detected | [Need Help with an Unemployment Claim in Florida? Good Luck](https://themarkup.org/coronavirus/2020/06/23/need-help-with-an-unemployment-claim-in-florida-good-luck) |
| [investigation-vi-spdat](https://github.com/the-markup/investigation-vi-spdat) | analysis code | BSD-3-Clause | [L.A.’s Scoring System for Subsidized Housing Gives Black and Latino People Experiencing Homelessness Lower Priority Scores](https://themarkup.org/investigation/2023/02/28/l-a-s-scoring-system-for-subsidized-housing-gives-black-and-latino-people-experiencing-homelessness-lower-priority-scores) |
| [investigation-wheres-my-email](https://github.com/the-markup/investigation-wheres-my-email) | analysis code | none detected | [Swinging the vote?](https://www.themarkup.org/google-the-giant/2020/02/26/wheres-my-email)<br>[Google the Giant](https://themarkup.org/google-the-giant/)<br>[paper](https://themarkup.org/google-the-giant/2020/02/26/show-your-work-wheres-my-email) |
| [investigation-wisconsin-dews](https://github.com/the-markup/investigation-wisconsin-dews) | data release | none detected | ["False Alarm: How Wisconsin Uses Race and Income to Label Students 'High Risk'"](https://themarkup.org/machine-learning/2023/04/27/false-alarm-how-wisconsin-uses-race-and-income-to-label-students-high-risk) |
| [investigation-youtube-ad-placements](https://github.com/the-markup/investigation-youtube-ad-placements) | analysis code | NOASSERTION | [Google Has a Secret Blocklist that Hides YouTube Hate Videos from Advertisers—But It’s Full of Holes](https://themarkup.org/google-the-giant/2021/04/08/google-youtube-hate-videos-ad-keywords-blocklist-failures)<br>[Google Blocks Advertisers from Targeting Black Lives Matter YouTube Videos](https://themarkup.org/google-the-giant/2021/04/09/google-blocks-advertisers-from-targeting-black-lives-matter-youtube-videos) |
| [life360-security](https://github.com/the-markup/life360-security) | data release | BSD-3-Clause | [Family Safety App Touting Digital Security Leaves Its Own Users' Sensitive Data at Risk](https://themarkup.org/privacy/2022/02/17/family-safety-app-touting-digital-security-leaves-its-own-users-sensitive-data-at-risk) |
| [location-data-industry](https://github.com/the-markup/location-data-industry) | data release | none detected | [There’s a Multibillion-Dollar Market for Your Phone’s Location Data](https://themarkup.org/privacy/2021/09/30/theres-a-multibillion-dollar-market-for-your-phones-location-data) |
| [meta-crypto-ads](https://github.com/the-markup/meta-crypto-ads) | data release | none detected | ["Facebook Scammers Are Schilling Fake Cryptocurrency Using Big Tech’s Biggest Names"](https://themarkup.org/citizen-browser/2022/02/22/facebook-scammers-are-schilling-fake-cryptocurrency-using-big-techs-biggest-names) |
| [meta-pixel-988](https://github.com/the-markup/meta-pixel-988) | data release | none detected | [Suicide Hotlines Promise Anonymity. Dozens of Their Websites Send Sensitive Data to Facebook](https://themarkup.org/pixel-hunt/2023/06/13/suicide-hotlines-promise-anonymity-dozens-of-their-websites-send-sensitive-data-to-facebook)<br>[here](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector) |
| [meta-pixel-edtech](https://github.com/the-markup/meta-pixel-edtech) | data release | none detected | [Facebook Watches Teens Online As They Prep for College](https://themarkup.org/pixel-hunt/2023/11/22/facebook-watches-teens-online-as-they-prep-for-college)<br>[here](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector) |
| [meta-pixel-mortgage](https://github.com/the-markup/meta-pixel-mortgage) | data release | none detected | [Mortgage Brokers Sent People’s Estimated Credit, Address, and Veteran Status to Facebook](https://themarkup.org/pixel-hunt/2024/05/15/mortgage-brokers-sent-peoples-estimated-credit-address-and-veteran-status-to-facebook)<br>[here](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector) |
| [meta-pixel-student-aid](https://github.com/the-markup/meta-pixel-student-aid) | data release | none detected | [Applied for Student Aid Online? Facebook Saw You](https://themarkup.org/pixel-hunt/2022/04/28/applied-for-student-aid-online-facebook-saw-you) |
| [meta-pixel-taxes](https://github.com/the-markup/meta-pixel-taxes) | data release | none detected | [Tax Filing Websites Have Been Sending Users’ Financial Information to Facebook](https://themarkup.org/pixel-hunt/2022/11/22/tax-filing-websites-have-been-sending-users-financial-information-to-facebook) |
| [Online-dispute-resolution](https://github.com/the-markup/Online-dispute-resolution) | data release | BSD-3-Clause | [Payday Lenders Are Big Winners in Utah’s Chatroom Justice Program](https://themarkup.org/zoom-justice/2022/03/16/payday-lenders-are-big-winners-in-utahs-chatroom-justice-program/) |
| [pinterest-hate](https://github.com/the-markup/pinterest-hate) | data release | none detected | [Anti-Semitic Merchandise Persists on Pinterest, Despite Restrictions](https://themarkup.org/2021/08/06/anti-semitic-merchandise-persists-on-pinterest-despite-restrictions) |
| [puppeteer-har](https://github.com/the-markup/puppeteer-har) | scraping/collection tooling | MIT | — |
| [redistributable-graphics-denied](https://github.com/the-markup/redistributable-graphics-denied) | infrastructure | NOASSERTION | [The Secret Bias Hidden in Mortgage-Approval Algorithms](https://themarkup.org/denied/2021/08/25/the-secret-bias-hidden-in-mortgage-approval-algorithms) |
| [smol-links](https://github.com/the-markup/smol-links) | infrastructure | NOASSERTION | — |
| [split-screen-news-sources](https://github.com/the-markup/split-screen-news-sources) | data release | none detected | [Split Screen](https://themarkup.org/citizen-browser/2021/03/11/split-screen)<br>[here](https://themarkup.org/citizen-browser/2021/03/11/how-we-built-a-facebook-feed-viewer) |
| [split-tests](https://github.com/the-markup/split-tests) | infrastructure | GPL-3.0 | — |
| [state_covid-19-vaccine_websites_audit](https://github.com/the-markup/state_covid-19-vaccine_websites_audit) | data release | none detected | [We Ran Tests on Every State’s COVID-19 Vaccine Website](https://themarkup.org/coronavirus/2021/03/24/we-ran-tests-on-every-states-covid-19-vaccine-website)<br>[here](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector)<br>[here](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector#limitations) |
| [tool-amazon-brand-detector](https://github.com/the-markup/tool-amazon-brand-detector) | scraping/collection tooling | BSD-3-Clause | [Introducing Amazon Brand Detector](https://themarkup.org/amazons-advantage/2021/11/29/introducing-amazon-brand-detector)<br>[investigation](https://themarkup.org/amazons-advantage/2021/10/14/amazon-puts-its-own-brands-first-above-better-rated-products) |
| [tool-simple-search](https://github.com/the-markup/tool-simple-search) | scraping/collection tooling | none detected | [Introducing Simple Search](https://themarkup.org/google-the-giant/2020/11/10/introducing-simple-search) |
| [vehicle-data-collection](https://github.com/the-markup/vehicle-data-collection) | data release | none detected | [Who Is Collecting Data from Your Car?](https://themarkup.org/the-breakdown/2022/07/27/who-is-collecting-data-from-your-car) |
| [xandr-audience-segments](https://github.com/the-markup/xandr-audience-segments) | data release | none detected | [From Heavy Purchasers of Pregnancy Tests to the Depression-Prone: We Found 650,000 Ways Advertisers Label You](https://themarkup.org/privacy/2023/06/08/from-heavy-purchasers-of-pregnancy-tests-to-the-depression-prone-we-found-650000-ways-advertisers-label-you) |
| [xmode-apps](https://github.com/the-markup/xmode-apps) | data release | none detected | [Gay/Bi Dating App, Muslim Prayer Apps Sold Data on People’s Location to A Controversial Data Broker](https://themarkup.org/privacy/2022/01/27/gay-bi-dating-app-muslim-prayer-apps-sold-data-on-peoples-location-to-a-controversial-data-broker) |

## Appendix C. Awards-page entries

Project mappings are **[inferred]** from the linked announcement's prose. Unlinked items remain unmapped.

| Year | Entry type | Awards-page entry | Bounded project mapping [inferred] |
|---:|---|---|---|
| 2024 | linked announcement | [Sisi Wei Recognized as a Freedom of the Press Rising Star in 2024 RCFP Awards](https://themarkup.org/inside-the-markup/2024/10/17/sisi-wei-rcfp-rising-star-2024) | — |
| 2024 | linked announcement | [The Markup Wins ONA Awards for General Excellence and Community-Centered Journalism](https://themarkup.org/inside-the-markup/2024/09/23/online-news-general-excellence-gather-community-award) | Automated Censorship, Blacklight, Still Loading, Languages of Misinformation, Digital Book Banning |
| 2024 | linked announcement | [The Markup’s “Clear and Beautiful” Reporting Wins Online Journalism Award](https://themarkup.org/inside-the-markup/2024/08/17/the-markups-clear-and-beautiful-reporting-wins-online-journalism-award) | Digital Book Banning |
| 2024 | linked announcement | [CalMatters/The Markup Honored for Leadership in Diversity and Solidarity, Community Innovation, by Asian American Journalists Association](https://themarkup.org/inside-the-markup/2024/08/13/calmatters-the-markup-honored-for-leadership-in-diversity-and-solidarity-community-innovation-by-asian-american-journalists-association) | Still Loading |
| 2024 | linked announcement | [The Markup Wins AAJA Journalism Excellence Award](https://themarkup.org/inside-the-markup/2024/05/28/the-markup-wins-aaja-journalism-excellence-award) | Languages of Misinformation |
| 2024 | linked announcement | [The Markup Wins Six Awards of Excellence from the Society for News Design](https://themarkup.org/inside-the-markup/2024/05/14/the-markup-wins-six-awards-of-excellence-from-the-society-for-news-design) | Still Loading, Neighborhood Watch |
| 2024 | linked announcement | [The Markup Wins Sigma Award](https://themarkup.org/inside-the-markup/2024/03/22/the-markup-wins-sigma-award) | — |
| 2024 | linked announcement | [The Markup Wins Philip Meyer Journalism Award](https://themarkup.org/inside-the-markup/2024/01/17/the-markup-wins-philip-meyer-journalism-award) | Still Loading |
| 2023 | linked announcement | [The Markup Wins Scripps Howard Innovation Award](https://themarkup.org/inside-the-markup/2023/10/24/the-markup-wins-scripps-howard-innovation-award) | Still Loading |
| 2023 | linked announcement | [The Markup Wins ONA Award in Technology Reporting](https://themarkup.org/inside-the-markup/2023/08/28/the-markup-wins-ona-award-in-technology-reporting) | Still Loading |
| 2023 | linked announcement | [The Markup Wins NABJ Salute to Excellence Award](https://themarkup.org/inside-the-markup/2023/08/15/the-markup-wins-nabj-salute-to-excellence-award) | Still Loading |
| 2023 | linked announcement | [The Markup Wins National Press Club Award](https://themarkup.org/inside-the-markup/2023/07/26/the-markup-wins-national-press-club-award) | Pixel Hunt |
| 2023 | linked announcement | [The Markup Honored by NAMLE for Media Literacy Work](https://themarkup.org/inside-the-markup/2023/07/03/the-markup-honored-by-namle-for-media-literacy-work) | — |
| 2023 | linked announcement | [The Markup Wins Digiday Media Award](https://themarkup.org/inside-the-markup/2023/06/20/the-markup-wins-digiday-media-award) | Pixel Hunt |
| 2023 | linked announcement | [The Markup Wins Two SND Best of News Design Awards](https://themarkup.org/inside-the-markup/2023/05/23/the-markup-wins-two-snd-best-of-news-design-awards) | Still Loading, Languages of Misinformation |
| 2023 | linked announcement | [The Markup Wins Sigma Award for Series on Internet Disparities](https://themarkup.org/inside-the-markup/2023/03/17/the-markup-wins-sigma-award-for-series-on-internet-disparities) | Still Loading |
| 2023 | linked announcement | [The Markup Wins Four SABEW Awards for Business Journalism](https://themarkup.org/inside-the-markup/2023/03/10/the-markup-wins-four-sabew-awards-for-business-journalism) | Working for an Algorithm, Still Loading, Pixel Hunt |
| 2023 | linked announcement | [The Markup Honored by AHCJ Awards for Excellence in Health Care Journalism](https://themarkup.org/inside-the-markup/2023/02/22/the-markup-honored-by-ahcj-awards-for-excellence-in-health-care-journalism) | Pixel Hunt |
| 2022 | linked announcement | [The Markup Receives Honors from Adweek and the National Edward R. Murrow Awards](https://themarkup.org/inside-the-markup/2022/10/25/the-markup-receives-honors-from-adweek-and-the-national-edward-r-murrow-awards) | Pixel Hunt, Citizen Browser, Prediction: Bias |
| 2022 | linked announcement | [The Markup Wins Loeb Award for Amazon’s Advantage](https://themarkup.org/amazons-advantage/2022/10/06/the-markup-wins-loeb-award-for-amazons-advantage) | Amazon’s Advantage |
| 2022 | unlinked list item | Fast Company World Changing Ideas Award | — |
| 2022 | unlinked list item | SND Best of News Design Award , Multiple Categories including Best in Show | — |
| 2022 | unlinked list item | Sigma Award For Data Journalism , Finalist | — |
| 2022 | unlinked list item | Scripps Howard Award , Finalist | — |
| 2022 | unlinked list item | Deadline Club Award | — |
| 2022 | unlinked list item | SPJ New America Award | — |
| 2022 | unlinked list item | National Headliner Award | — |
| 2022 | unlinked list item | NABJ Salute to Excellence Award | — |
| 2022 | unlinked list item | ONA Online Journalism Award , Finalist | — |
| 2021 | unlinked list item | Electronic Privacy Information Center's Champion of Freedom Award | — |
| 2021 | unlinked list item | Loeb Award , Finalist | — |
| 2021 | unlinked list item | Deadline Club Award , Finalist | — |
| 2021 | unlinked list item | Sigma Award for Data Journalism , Finalist | — |
