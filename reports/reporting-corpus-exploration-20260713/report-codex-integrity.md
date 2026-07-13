# Epstein Reporting Corpus Integrity and Coverage Audit

Audit date: 2026-07-13  
Corpus: `datasets/epstein_reporting.db`  
Mode: read-only SQLite `SELECT`, read-only Python connections, and non-mutating corpus analysis. No database or corpus mutation was performed. `uv run python` crashed in this environment before executing a helper, so the expressly permitted `.venv/bin/python`/`sqlite3 -readonly` fallback was used.

Audited snapshot: 7,775 reporting items; 9,292 versions; 8,893 discovery candidates (7,683 ingested / 771 excluded / 439 failed); 386 publisher rows, of which 323 are represented by items; 1,107 item relations; and 7,781 FTS rows.

## VERDICT

**Trust classification: conditional, discovery-grade; not measurement-grade.**

The corpus is useful for locating known reporting, finding recent multilingual coverage, building a bibliography, and close-reading the subset whose current version contains a substantive article body. It is not currently safe for counting independent reports, comparing publisher attention, measuring entity or topic frequencies, inferring historical silence, treating an empty search as absence, or regarding `content_text`/`broadcast_transcript` as proof that full article or transcript text is present.

The database mechanics themselves are mostly healthy: `PRAGMA integrity_check` returned `ok`; `foreign_key_check` found no violations; all 7,775 items have a valid current-version pointer owned by the same item; and every item has exactly one version marked `current`. The principal defects are semantic and coverage defects:

- **Era skew:** 5,159/7,775 items (66.35%) date from 2024 through 2026; 3,135 (40.32%) are from 2026 alone. The apparent pre-2005 count of 42 is actually only two core Jeffrey Epstein articles plus 40 wrong-person NRC records.
- **Publisher skew:** NBC (1,444), CBS (1,064), and Guardian (1,036) supply 3,544 items, or 45.58% of the corpus. Much of the NBC/CBS volume is video-page chrome rather than transcripts.
- **Text-quality skew:** 6,773 current versions have non-NULL `content_text`, 6,763 have nonempty text, and 6,759 have at least 100 characters. A conservative 1,267/6,773 (18.71%) are definite extraction junk or pages with only a short audiovisual synopsis rather than the represented full text. Using the task's >=100-character denominator, the equivalent inspected floor is 1,253/6,759 (18.54%).
- **Relevance skew:** `scope_class='direct'` is a lexical ingest label, not an editorial judgment that the item is centrally about Jeffrey Epstein. At least 234/7,559 direct rows (3.10%) are demonstrable wrong-person/concept or incidental records, and several obvious examples fall outside even that conservative floor.
- **Genealogy failure:** `independence_group` usually identifies an outlet, not an independently originated story. It simultaneously collapses every story from one outlet and separates modified wire/affiliate copies across outlets.
- **Canonical holes:** the corpus has strong searchable text for the 2002 New York Magazine profile, 2003 Vanity Fair profile, and 2006-2008 Palm Beach Post run, plus extensive Guardian coverage. But the Miami Herald series is nearly all metadata-only; the requested NYT/Landon Thomas period, WSJ series, FT, most Bloomberg finance reporting, historic BBC record, 2015 Vicky Ward article, original New Yorker/Mother Jones investigations, and meaningful book/podcast coverage are absent.

| Analytical use | Current trust level | Reason |
|---|---|---|
| Locate a known title/URL/item; build a bibliography | **Usable with inspection** | Metadata coverage is broader than body-text coverage; verify item and current version. |
| Search recent 2024-2026 reporting for leads | **Usable as high-recall discovery** | Strong recent volume, but publisher/stub/relevance skew requires filtering. |
| Close-read NYMag 2002, Vanity Fair 2003, Palm Beach Post 2006-08 | **Usable** | Substantive current text is present; reporting remains secondary evidence under the corpus contract. |
| Within-Guardian Prince Andrew chronology | **Usable with deduplication** | Coverage is extensive, but not a substitute for missing BBC originals and not independent corroboration by count. |
| Count independent stories or corroborating outlets | **Unsafe** | `independence_group` and relation semantics do not model story origin reliably. |
| Historical completeness or absence claims | **Unsafe** | Severe pre-2019 holes, metadata-only pillars, false historical NRC rows, and undated CBS concentration. |
| Publisher comparisons, trend lines, entity/co-mention frequencies, topic models | **Unsafe** | Era/publisher imbalance and large repeated page-chrome artifacts dominate raw FTS. |
| Transcript, podcast, or book analysis by `item_type` | **Unsafe** | At least 97.30% of inspected broadcast rows have no transcript; podcast/book taxonomy is nearly empty or wrong. |

Per `docs/modules/reporting.md`, even a clean reporting item is a secondary reporting record, not primary corroboration. Reported claims still require quoted primary evidence before promotion.

## INTEGRITY FINDINGS

### 1. Independence, duplication, and double-counting

All 7,775 items have an `independence_group`, but the field is not measuring what its name suggests.

| Measure | Result |
|---|---:|
| Distinct independence groups | 251 |
| Singleton groups | 113 |
| Shared groups | 138 groups containing 7,662 items |
| `outlet:*` groups | 238 groups / 7,661 items |
| `content:*` groups | 13 groups / 114 items |
| Largest group | `outlet:nbcnews.com`, 1,444 items |

The default ingest behavior is `outlet:<domain>`. As a result, every unrelated NBC article is nominally one “independent” group, while the same wire story modified slightly by different affiliates can occupy several groups. There are 323 publishers represented by items but only 238 outlet groups. `COUNT(DISTINCT independence_group)` therefore cannot be interpreted as either article count or originated-report count.

The exact-duplicate pass did correctly group sampled copies:

- 43 Newsquest outlets carrying the same PA News Agency story, IDs 1856-1964;
- ten local outlets carrying another byte-identical PA story;
- eight Sinclair affiliates carrying the same headline/body; and
- GDN URL aliases IDs 1975 and 1976.

The 13 `content:*` groups contain 114 items and create all 1,107 `item_relation` rows. Every relation is type `duplicates`; there are no `syndicates`, `rewrites`, `translates`, or follow-up relations. The 1,107 figure is the all-pairs edge count, `sum(n*(n-1)/2)`, not 1,107 distinct stories. Those 114 rows represent 13 exact groups, so naive item counting already creates 101 excess copies within the cases the system did catch.

Detection nevertheless misses obvious copies because `item_version.content_hash` is not a text hash. It hashes title, dek, abstract, content, and `updated_at` together. Metadata differences can therefore split byte-identical article bodies even though the duplicate code describes the field as an exact stored-content hash.

A normalized-title/calendar-day cross-publisher screen found 21 same-title/day clusters containing 146 rows. Seven clusters/79 rows were already one group; **14 clusters/67 rows spanned more than one independence group**. Text comparison within those candidates found 166 cross-group pairs at >=0.80 similarity, involving 39 items in the six highest-confidence clusters described below. This screen is deliberately conservative: it misses rewritten headlines and copies for which extraction captured different page chrome.

A direct SHA-256 census of current `content_text` found 33 repeated-text clusters containing 618 rows; excluding the ten shared empty-text artifacts leaves 32 clusters/608 rows. Much of this repetition is extraction junk, not syndication, but it exposes why the composite hash is unsuitable. Examples of genuine missed genealogy include:

- 20 Scripps stations, IDs 2085-2087, 2089-2092, 2094-2096, 2104, and 2132-2140: one byte-identical article split across six groups;
- Scripps IDs 2055 and 2057: one byte-identical report in two outlet groups;
- NBC O&O IDs 2028, 2029, 2031, 2034: the same report in four groups, with 0.96+ text similarity;
- CNN/Newsource IDs 2098, 2107, 2111, 2150: one report in four groups;
- Swedish TT IDs 2226, 2231, 2239, 2244: one wire report in four groups; and
- PA/Standard/Newsquest IDs 1915, 1918, 1919, 1921, 1965, 1974, 2040: one report in two groups.

These six high-confidence families contain 41 item rows in 22 current groups but represent at most six originated reports. In this audited sample:

- naive item counting yields 41 instead of six: **35 excess copies, or 6.8x**;
- distinct independence-group counting yields 22 instead of six: **16 excess groups, or 3.7x**.

This is a demonstrated floor, not a corpus-wide extrapolation. The reverse error is even larger in principle: counting groups treats all 1,444 NBC records as one independent report. The current field is directionally unreliable for quantitative work.

### 2. Pollution, scope semantics, navigation, and stubs

Corpus distributions are:

| Dimension | Value | Items | Nonempty current text |
|---|---|---:|---:|
| Scope | direct | 7,559 | 6,549 |
|  | background | 215 | 213 |
|  | contextual | 1 | 1 |
| Type | article | 6,515 | 5,523 |
|  | broadcast_transcript | 1,257 | 1,239 |
|  | investigation_series | 2 | 0 |
|  | podcast | 1 | 1 |

The relevance implementation accepts a single Epstein/Maxwell alias in title, dek, abstract, or URL, or two body mentions. A pre-labeled direct seed can remain direct after the fetched page fails the same rule, and file/import records are exempted from the later relevance audit. Bare surname matches such as `epstein` and roundup/photo-caption mentions therefore survive.

A conservative, item-specific pollution floor is **234/7,559 direct items (3.10%)**:

- 70 direct NRC items concern another Epstein or Epstein-Barr virus. This includes all 64 NRC items before 2019 and six later wrong-entity rows.
- 164 other direct imports fail the current direct-reporting rule and are plainly incidental/non-article material after removing three known relevant exceptions. Of these, 161 are NBC-family items and three are NRC crossword/fictional references.

The floor misses records that technically pass the lexical rule but are still irrelevant. For example, six ABC Audio affiliate copies (IDs 1922, 1924, 1925, 1927-1929) are about a Fulton County election subpoena; their only Epstein/Maxwell text is an unrelated photo caption. CBS #6422 is a Shanghai Disneyland roundup with one short Jes Staley/Epstein segment. NBC #7862 is an Iran-war/gas-price rally article with one contextual Epstein mention.

The deterministic 40-item sample used `ORDER BY ((id * 1103515245 + 12345) & 2147483647), id`. Manual results were:

| Sample class | Count |
|---|---:|
| Topical, substantive article/synopsis | 26 |
| Topical metadata-only | 7 |
| Topical video stub/chrome, no transcript | 4 |
| Direct but merely incidental | 1 |
| Correctly labeled background | 2 |

Among the 38 direct rows in the sample, one (2.6%) was merely incidental and four (10.5%) had relevant metadata but non-substantive captured video text. No accidental tag/index/navigation page appeared in the sample.

Navigation cleanup is relatively effective on its defined patterns. Applying the repository's own navigation/topic predicates to all live items matched only Miami Herald #43, the intentionally retained `investigation_series` hub. There are, however, three corrupt `Untitled reporting item` Novinky rows (#2735, #2736, #2738), and raw FTS retains two deleted privacy-gate ghosts.

The larger pollution problem is page extraction and audiovisual labeling:

- **418 NBC video rows** share the same unrelated 344-character recommendation block beginning “Top Graham staffer says ‘no indication’...”.
- **All 96 La Nación rows** contain recommendation/navigation lists rather than their article body; none contains its exact title.
- **Fourteen current texts under 100 characters** comprise ten empty Chosun/ChosunBiz rows, three two-byte Novinky artifacts, and Daily Mail #2001's tip-email line.
- Newser #1877 is only an ad-blocker wall.

Those signatures produce a definite-junk floor of **529/6,773 non-NULL current-text rows (7.81%)**. Adding the 738 CBS pages that contain navigation plus only a short video description, not a transcript, gives **1,267/6,773 (18.71%)** that are either extraction junk or not the represented full text.

`broadcast_transcript` is especially misleading:

| Publisher | Rows | Assessment |
|---|---:|---|
| CBS | 738 | All undated; page chrome plus title/one-sentence synopsis, no transcript |
| NBC | 458 | 418 unrelated repeated block, 35 video stubs/chrome, five empty; no transcript |
| Guardian | 27 | 14 short synopses/credits and 13 empty, not transcripts |
| Other | 34 | Mixed; not all individually classified |

At least **1,223/1,257 broadcast rows (97.30%)** lack an actual transcript. CBS/NBC alone contribute 1,191/6,763 (17.61%) of all nonempty current text as stubs/chrome. Le Monde podcast pages #1580/#1581 are player-error stubs, and AP video pages wrap a short video record in tens of thousands of characters of current-site navigation.

No broad current cookie/consent-wall epidemic was found with high-precision phrase checks. The more serious recurring defects are publisher-specific page chrome, short media descriptions, and recommendation modules.

### 3. Date integrity

The 742 undated items are highly concentrated:

| Publisher/type | Count | Characterization |
|---|---:|---|
| CBS `broadcast_transcript` | 738 | Video stubs; current metadata records JSON-LD parse error; candidate `published_at` is null |
| Novinky article | 3 | Unrelated corrupt background rows |
| Miami Herald series | 1 | Series hub #43, reasonably undated |

No current or historical item-version metadata contains a usable publication date for the CBS set, and candidate metadata is also null. The configured URL-date parser recovers zero. A broader deterministic parser can recover **22 exact CBS dates** already present in slugs/titles: five `YYYY-MM-DD` slugs, twelve `MMDDYY` slugs, and five explicit title dates. This leaves 720 items genuinely undated in stored data, including 716 CBS videos.

The 1938 NRC item #5154 is **not a date parse artifact**. Its URL and both JSON-LD date fields agree on 1938-01-30. It is a relevance/entity-resolution error concerning another Epstein. Of the 42 raw pre-2005 items, 40 are such NRC surname collisions; only New York Magazine #1801 and Vanity Fair #1802 concern Jeffrey Epstein. Wrong-person NRC items also inflate the 2005-08 bucket by ten, 2009-14 by thirteen, and 2015-19H1 by one.

Seven stored dates disagree with parseable current JSON-LD publication dates and require manual resolution:

| Item | Stored | JSON-LD | Likely issue |
|---|---|---|---|
| #1737 Der Spiegel | 2026-02-11 | 2025-12-20 | Modification date substituted for original year/date |
| #1739 Der Spiegel | 2026-02-28 | 2026-02-27 | One-day seed/update substitution |
| #1807 Der Spiegel | 2026-01-31 | 2026-01-30 | One-day seed/update substitution |
| #1813 JBpress | 2026-06-01 | 2026-06-08 | Placeholder/seed error |
| #1814 TBS News Dig | 2025-12-01 | 2025-12-03 | Placeholder/seed error |
| #1815 President Online | 2026-03-01 | 2026-02-21 | Placeholder/seed error |
| #2177 Daily Beast | 2018-03-28 | 2018-06-22 | Publisher JSON-LD conflict; manual review needed |

There is also a query-level date trap: **398/7,033 dated rows (5.66%)** end in compact timezone offsets such as `-0500` or `+0200`. SQLite `date(published_at)` returns NULL for all 398, silently removing them from date-range analyses.

### 4. Failed and excluded discovery candidates

#### Failed: 439

All 439 failed candidates are dated, explicitly name Epstein/Maxwell in title or URL, have been materialized as metadata-only items at the same canonical URL, and have zero current body text. They are visible to title/date/publisher queries but invisible to body-content analysis.

| Cause | Count | Share | Domains | Best next action |
|---|---:|---:|---|---|
| HTTP 403/access denial | 348 | 79.3% | Expresso 91; Ouest-France family 91; Libération 86; Público 81 | Public archive recovery; retry only after access strategy review |
| HTTP 302 redirect loop | 85 | 19.4% | Tages-Anzeiger | Canonical/redirect fix, then retry; archive fallback |
| HTTP 404 | 6 | 1.4% | NBC 5; Novo19/Ouest-France 1 | Archive-only or moved-URL discovery |

All 439 are plausible recovery targets; successful recovery is not guaranteed. **Seventy predate 2024** (33 in 2019H2, 25 in 2020-21, 12 in 2022-23) and should be prioritized because they cover weak eras. Representative high-value stuck records include:

- Ouest-France 2019 arrest/indictment, candidate #9546 -> item #4210;
- Público 2019 trafficking/power-network coverage, #7086 -> #3273;
- NBC 2019 cash, diamonds, and foreign passport report, #21279 -> #8112;
- Tages-Anzeiger 2020 Deutsche Bank report, #11037 -> #4519;
- Expresso 2021 Jes Staley resignation, #7528 -> #3452;
- Libération 2023 JPMorgan $290 million settlement, #9374 -> #4135;
- Ouest-France 2026 French wealth-tax report, #9479 -> #4143; and
- Ouest-France 2026 Rothschild-bank search report, #9543 -> #4207.

#### Excluded: 771

| Exclusion class | Count | Components |
|---|---:|---|
| Structural/duplicate/navigation | 340 | 288 pagination; 29 topic/index/source pages; 16 inaccessible syndication carriers with origin present; five mobile aliases; one TV schedule; one rolling live page |
| Relevance exclusions | 253 | 204 fetched item lacks direct subject; 47 manual contextual/malformed; two incidental after recovery |
| Stale repository seeds | 178 | Not present in latest relevance-scoped seed; inspected examples are unrelated cross-investigation references |

Most exclusions appear intentional, but at least **eight of the 204 “lacks direct reporting” exclusions are obvious likely false negatives** from their stored title/URL and do not exist as items: candidates #4216 (DN podcast on Norway's elite/Epstein), #4231 (Göteborgs-Posten ambassador/political pressure), #3695 (NZCity on Giuffre's legacy), #444 (RealClearInvestigations on the USVI legacy), #3478 (Las Vegas Review-Journal on a Maxwell pardon), #3654 (Sing Tao USA on the New Mexico truth commission/subpoenas), and Onet #5886/#5894 (Epstein assistant and reported 2006 Trump call). These deserve targeted recovery/review, not blanket reversal of the exclusion ledger.

### 5. Versions, current pointers, and FTS

Version-pointer integrity is strong:

- zero NULL or dangling `current_version_id` values;
- zero pointers to another item's version or to a non-current version;
- exactly one `version_status='current'` row per item;
- 9,292 versions: 7,775 current and 1,517 superseded;
- 1,452 items have multiple versions; maximum 12;
- zero orphan versions or dangling relation foreign keys; and
- zero invalid `metadata_json` values.

Version counts should not automatically be interpreted as editorial revisions. Of 27 items with at least three versions, 24 accumulated those versions within ten minutes and all within six hours, consistent with extraction/page-chrome volatility. `change_summary` is generic, so lineage can show captures but does not reliably explain substantive editorial change.

FTS is close to synchronized but not exact. `reporting_fts` contains 7,781 rows for 7,775 items:

- six orphan rowids: 2157, 2246, 2269, 2283, 2284, 2363; #2283/#2284 are empty “DPG Media Privacy Gate” ghosts;
- no live reporting item is missing from FTS; and
- live item #2360 has a stale FTS title (`속보서비스 - Chosunbiz`) while its item-table title is the actual Korean headline. Dek, abstract, and current content otherwise match live items.

The CLI search joins FTS to `reporting_item`, hiding the six ghosts. Raw FTS counts or downstream consumers that omit this join include them. Page chrome also creates major false-hit sets: `"Top Graham staffer"` returns 418 junk NBC rows; `"Iran War"` returns 820 hits with at least 738 contributed by CBS navigation; and `"World Cup"` returns 861 with the same CBS artifact floor.

## COVERAGE HOLES

“Present” below distinguishes bibliographic presence from claim-searchable article body text.

| Pillar | Status | Local evidence and limitation |
|---|---|---|
| Miami Herald, “Perversion of Justice” and follow-ups | **PARTIAL: bibliography present, body corpus absent** | 36 Miami items. Series hubs #43/#44; Nov. 28, 2018 anchors #45/#46/#77; follow-ups through #76. IDs #43-77 are metadata-only/paywalled. The only Miami item with text is #2222, an Acosta-defense op-ed, not a core series installment. Title/date search works; Julie K. Brown's article bodies are not searchable. |
| New York Magazine, 2002 “International Moneyman of Mystery” | **PRESENT** | #1801, 2002-10-28, 25,087 characters of current text. |
| Vanity Fair, 2003 Vicky Ward “The Talented Mr. Epstein” | **PRESENT** | #1802, 2003-03-01, 45,290 characters; 2011 follow-up #1806 also present. |
| Palm Beach Post, 2006-08 investigation era | **PRESENT, substantially searchable; exhaustiveness unproven** | Nineteen full-text items #1816-1834, 2006-07-24 through 2008-12-11. Representative anchors #1816, #1821, #1829, #1834. The 2017 reopening item #2215 is metadata-only. |
| NYT/Landon Thomas Jr., 2008-19 | **MISSING for requested period** | Historical NYT has only #1804, a 2006 article, and it is metadata-only. There are zero NYT items dated 2008-2019; later NYT items begin in 2025. The July 2008 Landon Thomas article and 2019 wave are absent. |
| WSJ 2023 calendar/bank series and 2025-26 work | **MISSING** | Sole WSJ item #26 is a 2020 SoftBank/Rajeev Misra contextual article with a 781-character paywall excerpt, not direct Epstein reporting. No requested WSJ series items exist. |
| Bloomberg/FT financial reporting | **NEARLY MISSING / MISSING** | Bloomberg #2305/#2306 are 2026 metadata-only items; historic Staley/JPMorgan/wealth coverage is absent. FT has a publisher row but zero items and zero candidates. |
| Vicky Ward, Daily Beast 2015 | **MISSING** | No 2015 Daily Beast item or exact-title FTS hit. Daily Beast 2010/2018 rows are not substitutes. |
| Guardian/BBC Prince Andrew arc | **Guardian PRESENT; historic BBC MISSING** | Guardian: 1,036 items, 547 with text; representative #1520 (2011), #1518/#1517 (2015), #1473 (2019), #1381/#1375 (Newsnight coverage), #1237 (2021 suit), #1166 (2022 settlement). BBC has only 11 items, all 2025-26; ten are Portuguese-language pages. The original 2019 Newsnight and subsequent Panorama record are absent. |
| New Yorker/Mother Jones; Farrow MIT investigation | **MISSING** | Zero items for both publishers. Farrow's original 2019 MIT Media Lab investigation and Mother Jones's 2020 black-book project are absent; downstream rewrites do not replace them. |
| Giuffre v. Maxwell unsealing coverage | **PARTIAL and poorly indexed by case name** | H1 2019 includes Miami #51 metadata-only and CBS #6654 full text; Miami #58 falls just after H1 and is metadata-only. Aug. 2019 coverage includes CBS #6625, Guardian #1473, NBC #7233. Exact case-name FTS is an ineffective retrieval route because titles omit the docket style. |
| Podcasts and books | **MISSING as a useful genre corpus** | One literal podcast item (#1769, Meduza, 2026) and zero `book_chapter` rows. A heuristic finds dozens of podcast-like URLs mislabeled as articles, but the major books and official podcast series are not systematically represented. |

### The sparse 2015-2019H1 window

The interval contains only 68 dated items; 46 have text and 22 are metadata-only. NBC (26), Miami Herald (14), Guardian (9), and CBS (8) supply 57/68 (83.8%). Annual counts are 2015: 16; 2016: 5; 2017: 3; 2018: 22; and 2019H1: 22.

That thin slice lacks Vicky Ward's 2015 article, most first-party Giuffre/Maxwell civil-case and unsealing reporting, searchable text for the 2018 Miami investigation, book-length reporting beginning with *Filthy Rich*, and every NYT, WSJ, Bloomberg, FT, New Yorker, and Mother Jones item in the window. It also contains at least one NRC wrong-person record and other marginal/incidental items, making its effective coverage weaker than 68 suggests. The 2018 Herald series is bibliographically present at the boundary but not claim-searchable.

The missing pillars generally are not waiting in the failed queue. NYT has no 2008-19 subject candidates; WSJ has no requested 2023-26 candidates; Bloomberg's requested finance series is absent from discovery; FT and Mother Jones have no candidates; New Yorker has only an unrelated excluded candidate. Miami is the important exception: discovery succeeded, but text recovery did not.

The author index cannot repair these searches. No normalized author row matches Julie K. Brown, Landon Thomas Jr., Vicky Ward, or Ronan Farrow, even where a corresponding item title is present.

## FILL PLAN

**Everything in this section is PROPOSED ONLY. No command below was executed during this audit. Run only in a separately authorized write session.**

### Priority 0 — fix trust gates before certifying quantitative use

Do not certify independent-report counts until `independence_group` is redesigned as story lineage, with outlet identity stored separately. Duplicate detection should use a normalized article-body digest plus title/date/byline/wire evidence, not the current composite `content_hash`. Quarantine known NBC/La Nación/CBS extraction signatures, require transcript evidence before assigning `broadcast_transcript`, backfill the 22 deterministic dates, review the seven date conflicts and 70 NRC wrong-entity rows, and rebuild FTS so it has exactly one live row per item. There is no current one-shot command that safely performs these semantic repairs; running the existing duplicate mutator without fixing hash/group semantics would preserve the wrong model.

### Priority 1 — add exact canonical pillar URLs

Create a reviewed JSONL file at `investigations/epstein/reporting_pillar_gap_seed.jsonl` using the existing historical-seed fields. Live publisher pages/search results were checked for the following proposed targets:

- [Daily Beast, Vicky Ward, 2015](https://www.thedailybeast.com/i-tried-to-warn-you-about-sleazy-billionaire-jeffrey-epstein-in-2003/)
- [New Yorker, Ronan Farrow, 2019](https://www.newyorker.com/news/news-desk/how-an-elite-university-research-center-concealed-its-relationship-with-jeffrey-epstein)
- [Bloomberg, Staley/Epstein, 2021](https://www.bloomberg.com/news/articles/2021-11-01/jeffrey-epstein-and-jes-staley-the-ties-that-cost-barclays-ceo-his-job)
- [Bloomberg, longer-than-disclosed ties, 2025](https://www.bloomberg.com/news/articles/2025-01-30/jeffrey-epstein-ties-to-jes-staley-prince-andrew-lasted-longer-than-disclosed)
- [Bloomberg, Staley testimony, 2025-03-11](https://www.bloomberg.com/news/articles/2025-03-11/epstein-often-knew-more-about-jpmorgan-than-me-claims-staley)
- [Bloomberg, five testimony findings, 2025-03-15](https://www.bloomberg.com/news/articles/2025-03-15/five-things-we-learned-from-jes-staley-s-epstein-testimony)
- [Bloomberg Big Take, Staley/Epstein/FCA, 2025](https://www.bloomberg.com/features/2025-jes-staley-jeffrey-epstein-fca/)
- [WSJ private calendar, 2023](https://www.wsj.com/us-news/jeffrey-epstein-calendar-cia-director-goldman-sachs-noam-chomsky-c9f6a3ff)
- [WSJ birthday-book report, 2025](https://www.wsj.com/politics/trump-jeffrey-epstein-birthday-letter-we-have-certain-things-in-common-f918d796)
- [FT, senior UK ministers, 2023](https://www.ft.com/content/2710193e-0188-4269-ba56-166c6effa234)

Mark three additional plausible URLs `VERIFY_BEFORE_SEED`: NYT 2008 `https://www.nytimes.com/2008/07/01/business/01epstein.html`, Mother Jones 2020 `https://www.motherjones.com/politics/2020/10/i-called-everyone-in-jeffrey-epsteins-little-black-book/`, and WSJ 2023 `https://www.wsj.com/articles/jpmorgan-jeffrey-epstein-525febe3`. Their title/date/article existence is corroborated, but this audit could not resolve the publisher page directly enough to certify the exact canonical URL. Add complete 2019 NYT, 2023/2025-26 WSJ, FT, and BBC URLs only after publisher-page or licensed-index verification; do not invent slugs.

```bash
# PROPOSED ONLY — after the JSONL has been manually reviewed
uv run python tools/reporting_corpus.py discover-file \
  investigations/epstein/reporting_pillar_gap_seed.jsonl \
  --source curated_pillar_gap_audit

uv run python tools/reporting_corpus.py ingest-candidates \
  --limit 100 --workers 4 --store-text --rights-status local_research
```

Use a second reviewed seed for official genre records: publisher/ISBN pages for *Filthy Rich*, *Relentless Pursuit*, and *The Perversion of Justice*; official feeds/episode pages for *Broken: Jeffrey Epstein* and *Chasing Ghislaine*; and BBC Newsnight/Panorama program pages. Store metadata only unless rights permit text, and label `broadcast_transcript` only when an actual transcript is captured.

```bash
# PROPOSED ONLY
uv run python tools/reporting_corpus.py discover-file \
  investigations/epstein/reporting_books_podcasts_seed.jsonl \
  --source curated_genre_gap_audit
```

### Priority 1 — recover text for known pillars and historically valuable failures

Recover the 35 known textless Miami items, then NYT #1804 and Palm Beach Post #2215:

```bash
# PROPOSED ONLY — writes recovered versions if successful
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
sqlite3 -readonly datasets/epstein_reporting.db \
  "SELECT i.id
   FROM reporting_item i
   JOIN publisher p ON p.id=i.publisher_id
   JOIN item_version v ON v.id=i.current_version_id
   WHERE p.name='Miami Herald'
     AND trim(coalesce(v.content_text,''))=''" \
  > "$WORKDIR/miami-textless-ids.txt"

while IFS= read -r item_id; do
  uv run python tools/reporting_corpus.py recover-archives \
    --item-id "$item_id" --provider auto --store-text --limit 1
done < "$WORKDIR/miami-textless-ids.txt"

uv run python tools/reporting_corpus.py recover-archives \
  --item-id 1804 --item-id 2215 --provider auto --store-text --limit 2
```

Prioritize the 70 pre-2024 failed URLs before the recent backlog:

```bash
# PROPOSED ONLY
WORKDIR=${WORKDIR:-$(mktemp -d /tmp/osint-XXXXXXXX)}
sqlite3 -readonly datasets/epstein_reporting.db \
  "SELECT url FROM discovery_candidate
   WHERE status='failed' AND substr(published_at,1,10)<'2024-01-01'
   ORDER BY published_at,id" \
  > "$WORKDIR/failed-pre2024-urls.txt"

while IFS= read -r url; do
  uv run python tools/reporting_corpus.py recover-archives \
    --url "$url" --provider auto --store-text --limit 1
done < "$WORKDIR/failed-pre2024-urls.txt"
```

Review/recover the eight likely false exclusions separately rather than reopening all exclusions:

```bash
# PROPOSED ONLY
WORKDIR=${WORKDIR:-$(mktemp -d /tmp/osint-XXXXXXXX)}
sqlite3 -readonly datasets/epstein_reporting.db \
  "SELECT url FROM discovery_candidate
   WHERE id IN (4216,4231,3695,444,3478,3654,5886,5894)
   ORDER BY id" \
  > "$WORKDIR/likely-false-exclusions.txt"

while IFS= read -r url; do
  uv run python tools/reporting_corpus.py recover-archives \
    --url "$url" --provider auto --store-text --limit 1
done < "$WORKDIR/likely-false-exclusions.txt"
```

After those targeted passes, the remaining failed set can be attempted with a bounded archive batch. HTTP 403s should be treated as archive/access cases; Tages-Anzeiger redirect loops should first receive a canonical-redirect fix; 404s are archive/moved-URL cases.

```bash
# PROPOSED ONLY — broad second pass after prioritized review
uv run python tools/reporting_corpus.py recover-archives \
  --failed-candidates --provider auto --store-text --limit 439 \
  --max-consecutive-errors 0
```

### Priority 2 — Wayback discovery for publisher/date holes

Use separate passes so failures are resumable and results can be reviewed by coverage family:

```bash
# PROPOSED ONLY — historical/general pillars
uv run python tools/reporting_corpus.py discover-wayback \
  --domain nytimes.com --domain thedailybeast.com --domain motherjones.com \
  --domain newyorker.com --domain miamiherald.com --domain palmbeachpost.com \
  --url-pattern epstein --url-pattern maxwell --url-pattern giuffre \
  --from 20000101 --to 20191231 --limit-per-domain 1000

# PROPOSED ONLY — finance pillars
uv run python tools/reporting_corpus.py discover-wayback \
  --domain wsj.com --domain ft.com --domain bloomberg.com \
  --url-pattern epstein --url-pattern staley --url-pattern jpmorgan \
  --url-pattern deutsche-bank --url-pattern leon-black \
  --from 20000101 --to 20261231 --limit-per-domain 1000

# PROPOSED ONLY — original BBC Andrew/Giuffre record
uv run python tools/reporting_corpus.py discover-wayback \
  --domain bbc.co.uk --domain bbc.com \
  --url-pattern epstein --url-pattern prince-andrew --url-pattern giuffre \
  --url-pattern newsnight --url-pattern panorama \
  --from 20110101 --to 20241231 --limit-per-domain 1000
```

Wayback CDX discovers URLs, not article text. Review candidates for relevance and canonical identity, then ingest/recover only verified publisher URLs.

### Priority 2 — licensed-database searches from the investigation contract

Use `investigations/epstein/licensed_database_searches.yaml` as both the reproducibility log and rights boundary. Run these searches in the licensed interfaces and record database, exact query, date range, facets, result count, review count, and selected citation IDs back into that YAML in an authorized session:

| Priority | Database/query | Date/facets | Purpose |
|---|---|---|---|
| 1 | ProQuest `NOFT("Jeffrey Epstein")` | 1960-01-01/2009-12-31 | Review the configured 264 pre-2010 indexed records citation by citation; exclude wrong-person Epsteins. |
| 1 | ProQuest `NOFT(Epstein AND (Wexner OR Maxwell OR "Palm Beach" OR Dershowitz OR Brunel))` | 1990-01-01/2018-12-31 | Recover network stories whose titles omit Jeffrey's full name. |
| 1 | Nexis Uni `"Jeffrey Epstein"` | Split 2000-09 and 2010-18; facet NYT, Palm Beach Post, Miami Herald, BBC, magazines | Fill historical publisher holes without treating syndication hits as independent articles. |
| 1 | Factiva `Epstein AND (JPMorgan OR "Deutsche Bank" OR Staley OR Dimon OR "Leon Black" OR Wexner)` | 2019-26; facet WSJ, FT, Bloomberg | Reconstruct missing finance/bank reporting. |
| 2 | Nexis/ProQuest `Giuffre AND Maxwell AND (unseal* OR deposition OR defamation)` | 2015-20 | Fill civil-case/unsealing coverage that title-only searches miss. |
| 2 | Exact author/title queries for Julie K. Brown, Landon Thomas Jr., Vicky Ward, Ronan Farrow | Relevant publication/date facets | Repair canonical pillar bibliography and author metadata. |

The existing broad licensed counts (for example, 199,393 ProQuest full-text hits) are mention universes dominated by syndication and must never be imported or reported as article/independence counts. Import bibliographic exports as licensed metadata unless the license expressly permits local text storage:

```bash
# PROPOSED ONLY — replace paths with reviewed exports
WORKDIR=${WORKDIR:-$(mktemp -d /tmp/osint-XXXXXXXX)}
uv run python tools/reporting_corpus.py import-file \
  "$WORKDIR/proquest-early-epstein.ris" \
  --source proquest --access-status licensed --rights-status metadata_only

uv run python tools/reporting_corpus.py import-file \
  "$WORKDIR/factiva-finance-epstein.ris" \
  --source factiva --access-status licensed --rights-status metadata_only
```

## QUERY HYGIENE NOTES

1. **Treat the corpus as a reporting index, not primary evidence.** A reporting hit supports “publisher X reported Y.” Verify the underlying proposition against primary records and preserve attribution/allegation language.

2. **Never use `COUNT(*)` or `COUNT(DISTINCT independence_group)` as independent-report counts.** Deduplicate by a story-family workflow using normalized article body, title/day, byline, wire credit, and explicit syndication lineage. Do not count the 1,107 all-pairs duplicate edges as reports.

3. **Join raw FTS to live items/current versions.** This removes the six orphan FTS rows and makes text availability visible:

```sql
SELECT i.id,p.name,i.title,i.published_at,length(v.content_text) AS body_chars
FROM reporting_fts
JOIN reporting_item i ON i.id=reporting_fts.rowid
JOIN item_version v ON v.id=i.current_version_id
LEFT JOIN publisher p ON p.id=i.publisher_id
WHERE reporting_fts MATCH :query
  AND i.scope_class='direct';
```

4. **Specify the FTS column for claim/body searches.** `reporting_fts MATCH 'content_text:"phrase"'` avoids confusing a title/dek hit with evidence that the article body contains the phrase. Conversely, pair body search with title/URL/publisher/date queries because Miami, NYT #1804, Bloomberg, and all failed candidates can exist without body text.

5. **Do not equate `direct` with central relevance.** Default CLI search excludes `background` but includes the one `contextual` row; raw FTS has no scope field. Inspect title/dek/context and watch for wrong-person Epsteins, roundups, photo captions, and direct seeds that bypassed relevance auditing.

6. **Do not equate non-NULL text with full text.** For body-level analysis, quarantine the known NBC repeated block, La Nación recommendation pages, CBS/NBC audiovisual stubs, sub-100-character artifacts, and access/player walls. A length threshold alone is insufficient because AP/navigation pages can be very long.

7. **Do not use `item_type='broadcast_transcript'` as transcript availability.** Require an actual transcript locator or inspected body. Treat CBS/NBC pages as bibliographic video records/synopses unless recovered text proves otherwise. Likewise, `podcast` and `book_chapter` counts are coverage defects, not genre distributions.

8. **Avoid SQLite `date(published_at)` on raw values.** It silently drops 398 compact-offset timestamps. For calendar-day bounds when the value starts ISO-formatted, use `substr(published_at,1,10)`:

```sql
WHERE substr(i.published_at,1,10) BETWEEN '2015-01-01' AND '2019-06-30'
```

Exclude undated CBS videos from temporal denominators. Twenty-two can be dated from existing slug/title data, but those dates are not yet stored.

9. **Treat negative searches as coverage-conditioned.** For pre-2019 work, first ask whether the publisher/series and substantive body text are present. An empty FTS result does not establish that an event was unreported. This is especially critical for the 68-item 2015-19H1 window.

10. **Do not rely on author tables for pillar absence.** Brown, Thomas, Ward, and Farrow have no normalized author rows. Search canonical title, URL, publisher, and date independently.

11. **Version count is not editorial-change count.** Many multi-version items were recaptured within minutes and have generic summaries. Compare content/body hashes and timestamps before interpreting a version as correction, update, or changed claim.

12. **Run publisher-sensitive sanity checks before frequency analysis.** Terms such as “Iran War,” “World Cup,” “Toronto festival,” and “Top Graham staffer” have hundreds of artifact hits from navigation/recommendation blocks. Any entity, co-mention, topic-model, or burst result should be rerun after excluding known extraction signatures and deduplicating story families.

In short: search broadly, inspect the current version, distinguish metadata presence from article-body presence, deduplicate at the originated-story level, condition every absence claim on documented coverage, and return to primary evidence before treating a reported claim as fact.
