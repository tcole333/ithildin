# ICIJ Corpus Census — Empirical Sampling Frame

**Agent 10 (census) | 2026-07-29**  
**Purpose:** Establish what ICIJ has actually published from its own site structure—not from memory of the famous leaks—so pattern extraction can be audited against the real distribution of projects, articles, data products and prizes.

---

## 1. Method and sources (read this before using any number)

Everything below was pulled on 2026-07-29 from ICIJ-owned site structures. The census uses the project sitemap as the named-project backbone and the editorial sitemaps as the item frame.

| What | Source | Nature |
|---|---|---|
| Investigations index and advertised pagination | [icij.org/investigations](https://www.icij.org/investigations/) through `/category/investigations/page/10/` | Page parse; all ten pages currently repeat the same ten newest cards |
| Named project backbone | [project-sitemap.xml](https://www.icij.org/project-sitemap.xml) | **Counted: 50 project URLs** |
| Editorial output | [sitemap.xml](https://www.icij.org/sitemap.xml), `post-sitemap1..9.xml`, `article-sitemap1..5.xml` | **Counted: 2,480 rows; 2,475 distinct URLs after five duplicate rows** |
| Project-path output | Editorial URLs whose path begins `/investigations/<one-of-the-50-slugs>/` | **Counted: 1,664 distinct items** |
| Project names and descriptions | Each of the 50 ICIJ project landing pages | ICIJ's own text, recovered from current or archived copies |
| Publication years | Explicit ICIJ URL dates and `datePublished`/`article:published_time` metadata on ICIJ pages; archived copies used when the current CDN rate-limited the pull | Counted where resolved; unresolved URLs are not silently assigned their sitemap modification year |
| ICIJ topic vocabulary | [All topics](https://www.icij.org/topics/) and ICIJ's tag structure | Presentation layer; 135 topic/tag terms at census time |
| Data products | ICIJ's Data navigation, [Data Archives](https://www.icij.org/category/category-data/), [Offshore Leaks data notes](https://offshoreleaks.icij.org/pages/data), [download page](https://offshoreleaks.icij.org/pages/database), Datashare, Medical Devices and FinCEN data pages | Separate asset census |
| Awards | [ICIJ's awards](https://www.icij.org/about/awards/) | **Counted by project heading and list entry** |

### The index could not be trusted as pagination

The investigations page advertises ten pages through `rel=next`, but pages 1–10 returned the same ten project cards and the same main-content SHA-256. The census therefore did **not** mistake the visible ten for the corpus or count them ten times. The complete backbone is the 50 URLs in `project-sitemap.xml`. The raw pagination audit is in `raw/archive-pagination.json`.

### What “item count” means here

ICIJ does not expose a clean all-history article count per project. “Project-path items” are distinct editorial sitemap URLs under an official project slug. They include reported stories and follow-ups, but also project-scoped explainers, impact updates, videos, FAQs and methodology/about pages. They are the closest reproducible, site-native approximation to article volume and should not be read as 1,664 long-form investigations.

The 14 editorial child sitemaps contain 1,651 `post` rows and 829 `article` rows. Five URLs are duplicated inside their sitemap children: two `inside-icij` URLs and three *Windfalls of War* URLs. Deduplication produces **2,475 distinct editorial URLs**. Four additional `/investigations/2020/...` or `/investigations/2025/...` paths do not match any official project slug; they remain in the all-editorial denominator but not the named-project denominator.

My seven-cluster assignment is a mutually exclusive judgment applied to ICIJ's own project descriptions and recurring topics. It is marked **[inferred]**; every row appears in Appendix A so it can be recoded.

---

## 2. Headline census numbers

- **50 named projects**, counted from ICIJ's project sitemap.
- **2,475 distinct editorial URLs**, counted from ICIJ's 14 post/article sitemap children after removing five duplicate rows.
- **1,664 distinct project-path items** assigned to one of the 50 official project slugs; **811 editorial URLs** sit outside the named-project paths.
- **7 candidate clusters** [inferred], ranging from 102 to 815 items.
- The seven-project “famous leaks canon” is only **14.0% of projects (7/50)** but contains **50.7% of named-project-path output (843/1,664)**.
- The same canon is **34.1% of the complete ICIJ-hosted editorial sitemap (843/2,475)**; **65.9%** of distinct editorial URLs fall outside it.

### Editorial URLs per publication year

Publication year is counted from an explicit date in the ICIJ URL or from publication metadata on the ICIJ page, including an archived copy of that same page when necessary. Sitemap `lastmod` is **not** treated as publication date because the 2025–2026 migration modified large numbers of old pages.

| Year | Resolved URLs | Year | Resolved URLs |
|---|---:|---|---:|
| 2000 | 5 | 2014 | 113 |
| 2001 | 14 | 2015 | 107 |
| 2002 | 8 | 2016 | 107 |
| 2003 | 13 | 2017 | 60 |
| 2006 | 30 | 2018 | 107 |
| 2007 | 21 | 2019 | 140 |
| 2008 | 10 | 2020 | 122 |
| 2009 | 16 | 2021 | 94 |
| 2010 | 9 | 2022 | 109 |
| 2011 | 7 | 2023 | 135 |
| 2012 | 189 | 2024 | 145 |
| 2013 | 92 | 2025 | 121 |
|  |  | 2026 (→Jul 29) | 75 |

**Coverage:** 1,849/2,475 distinct URLs have a resolved publication year in the saved pull; 626 remain undated. These are **counted lower bounds by year**, not inferred totals. The undated URLs remain enumerated in `raw/content-urls-complete.json`, making the uncertainty auditable rather than hiding it in a false annual estimate. The all-years editorial-output estimate is the complete sitemap count: **2,475 distinct URLs**.

The visible era shape must be interpreted carefully. ICIJ migrated old projects into newer URL/content structures, while modern leak projects continue to receive impact stories for years. A project span therefore measures the first and last ICIJ-hosted items now attached to the project, not only the initial publication window.

---

## 3. Their own taxonomy and the bottom-up candidate clusters

ICIJ's [All topics](https://www.icij.org/topics/) page exposes **135 A–Z terms** at census time. It mixes substantive beats (corruption, environment, healthcare, human rights, money laundering), regions (Africa, Europe, Latin America), project names (Panama Papers, China Cables), formats (data journalism, multimedia) and institutional/meta tags (impact, behind the scenes). It is useful vocabulary but not a mutually exclusive frame.

The counts ICIJ surfaces most prominently in its tag navigation also reveal the site's weighting: Impact 518 · Accountability 379 · Europe 348 · Panama Papers 324 · Offshore secrecy 318 · Offshore finance 308 · Tax havens 253 · Investigative journalism 228 · Pandora Papers 212 · Investigative reporting 200. These are overlapping tag assignments, not article totals.

For a pattern library, I assigned every official project to one primary cluster using this rule: **classify by the principal system being investigated, not by geography, leak name or evidence format**. When a project could fit two clusters, the object of accountability controls—for example, *FinCEN Files* goes under dirty-money systems rather than offshore ownership; *Cancer Calculus* under regulatory capture rather than general health; *Caspian Cabals* under corruption/enablers rather than extractives. All assignments are **[inferred]**.

| Cluster | Explicit coding rule | Projects | Project-path items | Span |
|---|---|---:|---:|---:|
| C1 Offshore finance, tax and hidden assets | Offshore structures, tax-minimization systems, private-bank secrecy or hidden cross-border ownership | 12 | 815 | 2013–2026 |
| C2 Dirty money, corruption, kleptocracy and enablers | Laundering, bribery, sanctions evasion, state capture or professional/corporate enablers | 8 | 218 | 2019–2026 |
| C3 Corporate lobbying and regulatory capture | Corporate influence over law, regulation, public-health policy, pricing or market access | 5 | 102 | 2000–2026 |
| C4 Natural resources, extractives and environment | Mining, fishing, forests, water, climate or natural-resource trade | 8 | 138 | 2003–2024 |
| C5 Conflict, repression and transnational rights | War commerce, political violence, detention, surveillance or cross-border state repression | 7 | 116 | 2002–2026 |
| C6 Health, labor and human exploitation | Unsafe medical products, occupational disease, tissue chains, labor/sex trafficking | 5 | 164 | 2010–2025 |
| C7 Aid, development finance and public contracting | Aid, multilateral finance, military assistance, privatized utilities or wartime procurement | 5 | 111 | 2006–2020 |
| **Total** | Each project assigned once | **50** | **1,664** | **2000–2026** |

---

## 4. The data side is a different corpus

ICIJ's top navigation explicitly separates **Investigations** from **Data**. The latter contains database releases, downloadable extracts, interactives and software; these should not be counted as ordinary articles or assumed to be locally integrated.

### 4.1 Offshore Leaks Database — integrated here

[ICIJ's database](https://offshoreleaks.icij.org/) says it contains **more than 810,000 offshore companies, foundations and trusts**, more than 750,000 names, records spanning more than 80 years through 2020, and more than 200 countries and territories. Its [data-source notes](https://offshoreleaks.icij.org/pages/data) identify five public database releases:

| Public database release | Release | Entity count stated by ICIJ |
|---|---:|---:|
| Offshore Leaks | 2013 | about 100,000 |
| Panama Papers | 2016 | more than 200,000 |
| Bahamas Leaks | 2016 | more than 175,000 companies, trusts and foundations |
| Paradise Papers | 2017 | more than 290,000 |
| Pandora Papers | 2021 | more than 27,000 companies/foundations/trusts and 29,000 ultimate beneficial owners from 11 providers |

The China Leaks installment was published in 2014 but is folded into the Offshore Leaks source family rather than listed as a sixth database release. The Pandora Papers leak itself contained **11.9 million records (2.94 TB) from 14 providers**; only a much smaller entity extract is public in the database.

The [download page](https://offshoreleaks.icij.org/pages/database) provides CSV node/relationship tables, Neo4j v4/v5 dumps, API/reconciliation access and ODbL/CC BY-SA terms. The public database excludes raw documents, bank accounts, emails and transactions.

**Platform status:** integrated (**user-specified**, with ICIJ lookup capability corroborated by local tool documentation). This platform holds the Offshore Leaks database and has ICIJ lookup tooling. That makes the entity/relationship corpus locally queryable; it does **not** mean the underlying raw leaks are held.

### 4.2 Datashare — software, not a public leak corpus

[Datashare](https://datashare.icij.org/) is ICIJ's open-source OCR, search, filtering and named-entity-analysis software, usable locally or on a server. ICIJ describes it as a gateway for reporters to more than 100 million leaked files, but the software release is not a public download of those files. Its [source is public](https://github.com/ICIJ/datashare).

**Platform status:** no Datashare-specific integration appears in the local tool documentation **[inferred local audit]**. The platform runs Aleph locally (**user-specified**), which overlaps functionally in document/entity analysis; local Aleph must not be described as possession of ICIJ's Datashare corpus.

### 4.3 Other public data assets — editorial/public only

- [International Medical Devices Database](https://medicaldevices.icij.org/): more than **120,000** recalls, safety alerts and field safety notices, built for the Implant Files collaboration of more than 250 journalists in 36 countries.
- [FinCEN Files transaction data](https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/): the investigation covered more than 2,100 SARs, more than 200,000 transactions and more than 6,900 correspondent connections. The public map/download represents more than **$35 billion** of more than **$2 trillion** flagged; it is not the full leak or the raw SAR set.
- [ICIJ Data Archives](https://www.icij.org/category/category-data/): nine indexed items at census time, including migrant-journey and Land Lords databases, FinCEN data/method pages, Datashare, The Influencers, Swiss Leaks data and the Luxembourg Leaks document database.

**Platform status:** editorial/public assets only unless separately ingested. Offshore Leaks is the one ICIJ bulk database explicitly held here; local Aleph is infrastructure, not an ICIJ dataset.

---

## 5. Awards census (prominence indicator—not the frame)

ICIJ's [awards page](https://www.icij.org/about/awards/) contains **23 headings that map to the 50-project backbone**, covering **46.0% of projects**. Under those headings are **93 award-list entries**. A list entry can name multiple prizes, so 93 is a page-structure count, not an exact count of individual awards. ICIJ also says partner outlets receive local honors not included on this page.

| Cluster | Awarded projects | Award-page list entries | Projects carrying prizes |
|---|---:|---:|---|
| C1 Offshore finance/tax | 10 | 53 | Offshore, Luxembourg, Swiss, Mauritius, Panama, Paradise, West Africa, Luanda, Pandora, Cyprus |
| C2 Dirty money/corruption | 4 | 8 | FinCEN, Bribery Division, Shadow Diplomats, Caspian Cabals |
| C3 Corporate capture | 1 | 1 | Uber Files |
| C4 Resources/environment | 2 | 6 | Fatal Extraction, Deforestation Inc. |
| C5 Conflict/repression | 2 | 3 | China Cables, Solitary Voices |
| C6 Health/labor/exploitation | 3 | 15 | Implant Files, Trafficking Inc., Skin and Bone |
| C7 Aid/development/contracts | 1 | 7 | Evicted and Abandoned |
| **Total** | **23** | **93** | |

The famous seven projects account for **54/93 (58.1%)** of these project-mapped award-list entries while representing 14.0% of projects. Awards therefore amplify exactly the mega-project/canon bias the census is intended to control. Additional awards-page headings—*Inside the IRS*, *Cargo Trucks*, general honors and *Meet the Investigators*—do not map to the 50 official project sitemap entries and are excluded from the project comparison.

---

## 6. Distribution of the actual named-project portfolio

Counting method: each of the 50 official projects is assigned to exactly one candidate cluster [inferred]; items are distinct editorial sitemap URLs under that project's path.

| Cluster | Projects | % projects | Items | % items |
|---|---:|---:|---:|---:|
| C1 Offshore finance, tax and hidden assets | 12 | 24.0% | 815 | 49.0% |
| C2 Dirty money, corruption, kleptocracy and enablers | 8 | 16.0% | 218 | 13.1% |
| C3 Corporate lobbying and regulatory capture | 5 | 10.0% | 102 | 6.1% |
| C4 Natural resources, extractives and environment | 8 | 16.0% | 138 | 8.3% |
| C5 Conflict, repression and transnational rights | 7 | 14.0% | 116 | 7.0% |
| C6 Health, labor and human exploitation | 5 | 10.0% | 164 | 9.9% |
| C7 Aid, development finance and public contracting | 5 | 10.0% | 111 | 6.7% |
| **Total** | **50** | **100%** | **1,664** | **100%** |

The volume distribution is extremely concentrated: C1 is only 24% of projects but 49% of project-path items. Panama Papers alone has 211 items; Pandora 163; Paradise 134; Implant Files 101; FinCEN 88; Offshore 85. The other 44 projects average about 20 items each.

The clusters also expose methodological breadth that a “leaks” label obscures. ICIJ's frame includes corporate filings and licenses (*Fatal Extraction*), fish DNA and subsidy records (*Looting the Seas*), detention manuals (*China Cables*), Red Notices (*Interpol's Red Flag*), World Bank displacement records, tissue traceability, medical recall databases, public contracts, crypto tracing and private corporate lobbying files.

---

## 7. Coverage diff—what the famous leaks canon covers and misses

The stipulated canon is Offshore Leaks + Panama Papers + Paradise Papers + Pandora Papers + FinCEN Files + Implant Files + Luanda Leaks.

The coverage arithmetic below is counted; the interpretation of what those omissions mean for a pattern library is **[inferred]** from the projects' subjects and evidence descriptions.

| Denominator | Canon | Covered | Missed |
|---|---:|---:|---:|
| Named projects | 7/50 | **14.0%** | **86.0%** |
| Distinct official project-path items | 843/1,664 | **50.7%** | **49.3%** |
| All distinct editorial sitemap URLs | 843/2,475 | **34.1%** | **65.9%** |

The canon therefore looks broad if weighted by URLs but narrow if weighted by investigative undertakings. Its apparent 50.7% coverage is produced by seven unusually large project archives.

What it misses is not simply “small stories”:

1. **Noncanonical offshore/tax families:** China Leaks, Luxembourg Leaks, Swiss Leaks, Mauritius Leaks, West Africa Leaks, Cyprus Confidential and Hidden Treasures—**7 projects, 161 items**.
2. **Dirty-money and corruption methods outside FinCEN:** crypto transaction tracing, Odebrecht bribery systems, Ericsson's internal records, sanctions/oligarch archives, Eswatini FIU files, Kazakhstan oil contracts and honorary-consul networks—**7 projects, 130 items**.
3. **Natural resources/environment:** mining fatalities, fisheries enforcement and subsidies, forest certification, water privatization, climate lobbying and conflict minerals—**8 projects, 138 items**.
4. **Conflict/repression:** Xinjiang detention architecture, transnational repression, Syrian atrocity documentation, immigration detention, Red Notice abuse, mercenaries and the Pearl murder network—**7 projects, 116 items**.
5. **Aid/development/procurement:** World Bank displacement, PEPFAR conditionality, military assistance, water concessions and Iraq/Afghanistan contracting—**5 projects, 111 items**.
6. **Corporate capture and residual health/labor work:** the tobacco investigations, Uber, Cancer Calculus, asbestos, sugarcane kidney disease, tissue trade and trafficking—**9 noncanonical projects, 165 items**.

---

## 8. Second-wave extraction recommendations (ranked)

Ranked by **volume × evidentiary distinctiveness**: the amount of residual output multiplied by whether it introduces evidence and reasoning patterns absent from the famous canon. The volumes are counted; the ranking and evidence-type judgments are **[inferred]**.

**R1. Dirty money, corruption, kleptocracy and enablers beyond FinCEN** (7 projects, 130 items).  
Distinct evidence: blockchain transaction tracing and victim reconstruction; internal bribery ledgers; telecom/vendor records involving sanctioned or armed actors; FIU records; oil concessions and lobbying; honorary-consul appointment and misconduct records. Seeds: [Coin Laundry](https://www.icij.org/investigations/coin-laundry/), [Bribery Division](https://www.icij.org/investigations/bribery-division/), [Ericsson List](https://www.icij.org/investigations/ericsson-list/), [Russia Archive](https://www.icij.org/investigations/russia-archive/), [Swazi Secrets](https://www.icij.org/investigations/swazi-secrets/), [Caspian Cabals](https://www.icij.org/investigations/caspian-cabals/), [Shadow Diplomats](https://www.icij.org/investigations/shadow-diplomats/).

**R2. Natural resources, extractives and environment** (8 projects, 138 items).  
Distinct evidence: fisheries quota/subsidy records and DNA testing; stock-exchange filings, mining licenses and fatality reconciliation; environmental certification chains and timber trade data; climate-lobby records; water-concession contracts. Seeds: [Fatal Extraction](https://www.icij.org/investigations/fatal-extraction/), [Deforestation Inc.](https://www.icij.org/investigations/deforestation-inc/), [Looting the Seas I](https://www.icij.org/investigations/looting-the-seas/), [II](https://www.icij.org/investigations/looting-the-seas-ii/), [III](https://www.icij.org/investigations/looting-seas-iii/), [Water Barons](https://www.icij.org/investigations/waterbarons/), [Coltan](https://www.icij.org/investigations/coltan/), [Global Climate Change Lobby](https://www.icij.org/investigations/global-climate-change-lobby/).

**R3. Conflict, repression and transnational rights** (7 projects, 116 items).  
Distinct evidence: detention manuals and algorithmic surveillance documents; dissident/refugee case reconstruction; solitary-confinement records; Interpol Red Notices; atrocity-photo verification; mercenary and arms-company networks. Seeds: [China Cables](https://www.icij.org/investigations/china-cables/), [China Targets](https://www.icij.org/investigations/china-targets/), [Solitary Voices](https://www.icij.org/investigations/solitary-voices/), [Interpol's Red Flag](https://www.icij.org/investigations/interpols-red-flag/), [Damascus Dossier](https://www.icij.org/investigations/damascus-dossier/), [Making a Killing](https://www.icij.org/investigations/makingkilling/), [Daniel Pearl](https://www.icij.org/investigations/daniel-pearl/).

**R4. Noncanonical offshore and tax leak families** (7 projects, 161 items).  
This is the largest residual set, but methodologically closer to the existing canon. Its value is comparative: bank secrecy versus service-provider leaks; tax rulings versus beneficial ownership; regional collaborations; art provenance; post-invasion sanctions enforcement. Seeds: [Luxembourg Leaks](https://www.icij.org/investigations/luxembourg-leaks/), [Swiss Leaks](https://www.icij.org/investigations/swiss-leaks/), [Mauritius Leaks](https://www.icij.org/investigations/mauritius-leaks/), [West Africa Leaks](https://www.icij.org/investigations/west-africa-leaks/), [Cyprus Confidential](https://www.icij.org/investigations/cyprus-confidential/), [China Leaks](https://www.icij.org/investigations/zhong-guo-chi-jin-rong-jie-mi/), [Hidden Treasures](https://www.icij.org/investigations/hidden-treasures/).

**R5. Aid, development finance and public contracting** (5 projects, 111 items).  
Distinct evidence: displacement/resettlement case databases; multilateral lender accountability files; PEPFAR grant conditions; military-aid and human-rights records; FOIA procurement data, campaign contributions and lobbying. Seeds: [Evicted and Abandoned](https://www.icij.org/investigations/world-bank/), [Divine Intervention](https://www.icij.org/investigations/divine-intervention/), [U.S. Aid in Latin America](https://www.icij.org/investigations/us-aid-latin-america/), [Collateral Damage](https://www.icij.org/investigations/collateraldamage/), [Windfalls of War](https://www.icij.org/investigations/windfalls-war/).

**R6. Corporate lobbying and regulatory capture** (5 projects, 102 items).  
Distinct evidence: internal corporate documents, lobbying campaigns across jurisdictions, patent families, medicine pricing/court records and “ask forgiveness” market-entry strategies. Seeds: [Big Tobacco Smuggling](https://www.icij.org/investigations/big-tobacco-smuggling/), [Tobacco Underground](https://www.icij.org/investigations/tobacco-underground/), [Smoke Screen](https://www.icij.org/investigations/smoke-screen/), [Uber Files](https://www.icij.org/investigations/uber-files/), [Cancer Calculus](https://www.icij.org/investigations/cancer-calculus/).

**R7. Residual health, labor and human exploitation** (4 noncanonical projects, 63 items).  
Distinct evidence: WHO/national mortality series, occupational disease and trade lobbying, tissue-provenance chains, recruitment-fee and subcontractor networks. Seeds: [Dangers in the Dust](https://www.icij.org/investigations/dangers-dust/), [Island of the Widows](https://www.icij.org/investigations/island-widows/), [Skin and Bone](https://www.icij.org/investigations/tissue/), [Trafficking Inc.](https://www.icij.org/investigations/trafficking-inc/).

---

## 9. Sampling-frame notes

The measured denominators below retain their counted status; the bias diagnoses and proposed coding rules are **[inferred]** methodological judgments.

**Consortium-attribution ambiguity:** ICIJ projects are collaborations, not closed magazines. A project banner may coordinate hundreds of reporters while partner outlets publish many stories on their own domains; ICIJ may host only a subset, summaries or selected republications. **Coder rule:** the empirical ICIJ-hosted frame includes each distinct editorial URL in ICIJ's own post/article sitemaps once. A project is assigned only when the URL uses one of the 50 official project slugs. A partner-only URL is not an ICIJ-hosted output item, but may be recorded as partner evidence with outlet and project attribution. An ICIJ-hosted republication counts once at its canonical ICIJ URL. This keeps the denominator reproducible without erasing consortium credit.

**English-index bias:** the ICIJ sitemap is an English-centered institutional index. It includes a Chinese China Leaks project page, but it does not enumerate the complete Spanish, French, German, Arabic, Chinese or other-language output of member outlets. The 2,475 count is ICIJ-hosted output, not the global publication yield of ICIJ collaborations.

**Project-versus-article unit problem:** seven mega-projects generate half the project-path URLs. Those paths mix launch investigations with impact updates, methods, FAQs and videos. A pattern extraction should use a two-stage sample: first weight projects equally to preserve investigative diversity, then sample within projects by content type and time. A flat article sample will recreate the offshore canon even after the frame is complete.

**Topic censoring:** ICIJ's 135 terms are overlapping and heterogeneous—project labels, regions, formats and substantive topics share one vocabulary. Older migrated work is less consistently tagged, while modern projects carry many process and impact tags. Tag counts should guide discovery, not estimate mutually exclusive portfolio shares.

**Chronology/migration bias:** sitemap `lastmod` is frequently a 2025–2026 migration/update date for much older work. It cannot substitute for publication date. Project “last year” often reflects a later impact story rather than the investigation's launch. The saved year file distinguishes URL-derived dates, direct metadata, archived ICIJ metadata and unresolved items.

**Pagination failure:** the advertised investigations archive currently repeats page 1 through page 10. A crawler that follows the UI alone sees ten projects—or one hundred duplicated cards. The project sitemap is the defensible backbone.

**Sitemap duplication and unit mixing:** five duplicate rows were removed. The post/article split reflects ICIJ's CMS history, not necessarily editorial genre; counts use their union. Project landing pages themselves come from the project sitemap and are not added to the editorial-item numerator.

**Award and fame bias:** the famous canon holds 58.1% of project-mapped award-list entries. Choosing by prize visibility over-samples offshore mega-leaks and Implant Files, while under-sampling environmental, conflict, procurement, labor and corporate-capture methods.

**Data/editorial conflation:** Offshore Leaks, Medical Devices, FinCEN extracts and Datashare have different units and access conditions. The public Offshore Leaks database contains entity extracts, not raw leak documents or transactions; Datashare is software, not a downloadable ICIJ corpus. Pattern coders must record whether evidence came from an editorial page, a public data product, a local integration or an unavailable collaboration corpus.

**Frame completeness:** the 50-project frame is complete for official project landing pages in `project-sitemap.xml` on the pull date. It is intentionally not a claim that ICIJ has coordinated only 50 investigations, nor that the ICIJ site holds every consortium partner story. Older work can also appear only as ordinary editorial URLs or awards headings. Those are precisely the reasons the 811 non-project editorial URLs and nonmatching award headings remain visible rather than being forced into the appendix.

---

## Appendix A — Full project backbone (50 projects, grouped by candidate cluster)

Every project in ICIJ's `project-sitemap.xml` as of 2026-07-29. Each project name links its canonical URL; the slug is the terminal `/investigations/<slug>/` segment and is also an explicit field in `raw/projects.json`. “Items” are counted from distinct post/article sitemap URLs under that slug. “Years” are the first and last resolved ICIJ publication years among those items/project-page cards or an explicit ICIJ launch page; they are not inferred from sitemap modification dates. The one-line subjects are concise **[inferred]** summaries of ICIJ's descriptions; the exact ICIJ text is preserved in `raw/projects.json`.

### C1 — Offshore finance, tax and hidden assets — 12 projects, 815 items

| Project | Years | Items | One-line subject |
|---|---:|---:|---|
| [Secrecy for Sale](https://www.icij.org/investigations/offshore/) | 2013–2024 | 85 | Inside the Global Offshore Money Maze |
| [Luxembourg Leaks](https://www.icij.org/investigations/luxembourg-leaks/) | 2014–2024 | 40 | Global Companies' Secrets Exposed |
| [中国离岸金融解密 China Leaks](https://www.icij.org/investigations/zhong-guo-chi-jin-rong-jie-mi/) | 2014 | 10 | Leaked records reveal offshore holdings of China’s elite. |
| [Swiss Leaks](https://www.icij.org/investigations/swiss-leaks/) | 2015–2023 | 23 | Murky Cash Sheltered by Bank Secrecy |
| [The Panama Papers](https://www.icij.org/investigations/panama-papers/) | 2016–2026 | 211 | Exposing the Rogue Offshore Finance Industry |
| [West Africa Leaks](https://www.icij.org/investigations/west-africa-leaks/) | 2018–2020 | 12 | In the region’s largest-ever journalism collaboration, reporters from 11 countries expose the financial secrets of some of West Africa’s most powerful politicians, moguls and corporations. |
| [Mauritius Leaks](https://www.icij.org/investigations/mauritius-leaks/) | 2019–2022 | 16 | Multinational companies use the tiny tax haven Mauritius to avoid paying taxes to countries in Africa, Asia, the Middle East and the United States. |
| [Luanda Leaks](https://www.icij.org/investigations/luanda-leaks/) | 2020–2024 | 61 | How two decades of corrupt deals made Isabel dos Santos Africa’s wealthiest woman and left oil- and diamond-rich Angola one of the world’s poorest countries. |
| [Pandora Papers](https://www.icij.org/investigations/pandora-papers/) | 2021–2026 | 163 | The largest investigation in journalism history exposes a shadow financial system that benefits the world's most rich and powerful. |
| [Paradise Papers](https://www.icij.org/investigations/paradise-papers/) | 2017–2026 | 134 | Secrets of the Global Elite |
| [Hidden Treasures](https://www.icij.org/investigations/hidden-treasures/) | 2022–2026 | 15 | How art and antiquities became prized offshore assets and, in some cases, cover for looters and thieves. |
| [Cyprus Confidential](https://www.icij.org/investigations/cyprus-confidential/) | 2023–2026 | 45 | How a sprawling financial industry powered the Putin regime and undermined the West. |

### C2 — Dirty money, corruption, kleptocracy and enablers — 8 projects, 218 items

| Project | Years | Items | One-line subject |
|---|---:|---:|---|
| [Bribery Division](https://www.icij.org/investigations/bribery-division/) | 2019–2024 | 16 | Leaked Odebrecht files expose a cash-for-contracts bribery system and implicated public works. |
| [FinCEN Files](https://www.icij.org/investigations/fincen-files/) | 2020–2025 | 88 | The role of global banks in industrial-scale money laundering and its human consequences. |
| [Russia Archive](https://www.icij.org/investigations/russia-archive/) | 2022–2025 | 21 | ICIJ's leaked-file reporting on hidden wealth connected to Russia's ruling elites. |
| [Shadow Diplomats](https://www.icij.org/investigations/shadow-diplomats/) | 2022–2023 | 14 | How rogue honorary consuls, including alleged criminals and terror financiers, undermined diplomacy. |
| [The Ericsson List](https://www.icij.org/investigations/ericsson-list/) | 2022–2023 | 26 | How a telecom giant dealt with terrorists and financed questionable deals in pursuit of profit. |
| [Caspian Cabals](https://www.icij.org/investigations/caspian-cabals/) | 2024–2025 | 15 | How Western oil companies accepted Kazakhstan corruption risks and became exposed to Putin's leverage. |
| [Swazi Secrets](https://www.icij.org/investigations/swazi-secrets/) | 2024–2025 | 9 | Suspicious money flows and elite access in Eswatini, Africa's last absolute monarchy. |
| [The Coin Laundry](https://www.icij.org/investigations/coin-laundry/) | 2025–2026 | 29 | How the crypto boom created a crime-friendly shadow economy and a trail of victims. |

### C3 — Corporate lobbying and regulatory capture — 5 projects, 102 items

| Project | Years | Items | One-line subject |
|---|---:|---:|---|
| [Big Tobacco Smuggling](https://www.icij.org/investigations/big-tobacco-smuggling/) | 2000–2001 | 19 | Big Tobacco's conduct in cigarette smuggling and emerging markets. |
| [Tobacco Underground](https://www.icij.org/investigations/tobacco-underground/) | 2008–2010 | 30 | How illicit cigarette trade fuels organized crime, corruption and tax losses. |
| [Smoke Screen](https://www.icij.org/investigations/smoke-screen/) | 2012 | 12 | Big Tobacco's lobbying pivot from developed countries to emerging markets. |
| [The Uber Files](https://www.icij.org/investigations/uber-files/) | 2022–2023 | 24 | How Uber accessed leaders, courted oligarchs and dodged taxes during global expansion. |
| [Cancer Calculus](https://www.icij.org/investigations/cancer-calculus/) | 2026 | 17 | How Merck sustains Keytruda's price, restricting access and straining health systems. |

### C4 — Natural resources, extractives and environment — 8 projects, 138 items

| Project | Years | Items | One-line subject |
|---|---:|---:|---|
| [The Water Barons](https://www.icij.org/investigations/waterbarons/) | 2003 | 16 | The growth of private water utilities and loss of public control over water. |
| [Spain’s $8 Billion Fish](https://www.icij.org/investigations/looting-the-seas-ii/) | 2011–2012 | 16 | Spain's fishing subsidies and an industry's record of flouting rules. |
| [Plunder in the Pacific](https://www.icij.org/investigations/looting-seas-iii/) | 2012 | 17 | Giant trawlers pursuing South Pacific fisheries toward collapse. |
| [The Black Market in Bluefin](https://www.icij.org/investigations/looting-the-seas/) | 2012 | 15 | Fraud and official negligence across the bluefin tuna supply chain. |
| [The Global Climate Change Lobby](https://www.icij.org/investigations/global-climate-change-lobby/) | 2012 | 22 | The battle to influence the world's central climate treaty. |
| [The Illicit Trade of Coltan](https://www.icij.org/investigations/coltan/) | 2012 | 7 | Conflict-mineral supply chains from criminally controlled regions into electronics. |
| [Fatal Extraction](https://www.icij.org/investigations/fatal-extraction/) | 2015 | 10 | Australian mining companies' damaging expansion in Africa. |
| [Deforestation Inc.](https://www.icij.org/investigations/deforestation-inc/) | 2023–2024 | 35 | How sustainability certification overlooks forest destruction and rights violations. |

### C5 — Conflict, repression and transnational rights — 7 projects, 116 items

| Project | Years | Items | One-line subject |
|---|---:|---:|---|
| [Making a Killing](https://www.icij.org/investigations/makingkilling/) | 2002 | 11 | Companies with government and organizational connections profiting from war commerce. |
| [Interpol’s Red Flag](https://www.icij.org/investigations/interpols-red-flag/) | 2011–2012 | 5 | Governments' use of Interpol against political opponents and refugees. |
| [Inside the Kidnapping and Murder of Daniel Pearl](https://www.icij.org/investigations/daniel-pearl/) | 2012 | 2 | The roles of 27 men linked to Daniel Pearl's kidnapping and murder. |
| [China Cables](https://www.icij.org/investigations/china-cables/) | 2019–2026 | 35 | Surveillance and mass internment of Uyghurs and other Muslim minorities in Xinjiang. |
| [Solitary Voices](https://www.icij.org/investigations/solitary-voices/) | 2019–2024 | 25 | Misuse and overuse of solitary confinement in U.S. immigration detention. |
| [China Targets](https://www.icij.org/investigations/china-targets/) | 2025–2026 | 30 | Beijing's abuse of international institutions to pursue critics worldwide. |
| [Damascus Dossier](https://www.icij.org/investigations/damascus-dossier/) | 2025 | 8 | Secret photos and intelligence files documenting the Assad regime's killing machine. |

### C6 — Health, labor and human exploitation — 5 projects, 164 items

| Project | Years | Items | One-line subject |
|---|---:|---:|---|
| [Dangers in the Dust](https://www.icij.org/investigations/dangers-dust/) | 2010–2012 | 14 | The global asbestos lobby and a projected disease burden concentrated in developing countries. |
| [Island of the Widows](https://www.icij.org/investigations/island-widows/) | 2011–2020 | 11 | Chronic kidney disease deaths among Central American sugarcane workers. |
| [Skin and Bone](https://www.icij.org/investigations/tissue/) | 2012–2019 | 19 | The lucrative global trade that turns human tissue into medical implants. |
| [Implant Files](https://www.icij.org/investigations/implant-files/) | 2018–2024 | 101 | Global regulatory failure to protect patients from poorly tested medical implants. |
| [Trafficking Inc.](https://www.icij.org/investigations/trafficking-inc/) | 2022–2025 | 19 | Companies, people and business practices profiting from labor and sex trafficking. |

### C7 — Aid, development finance and public contracting — 5 projects, 111 items

| Project | Years | Items | One-line subject |
|---|---:|---:|---|
| [Collateral Damage](https://www.icij.org/investigations/collateraldamage/) | 2006–2007 | 23 | The effects of post-9/11 U.S. military aid abroad and at home. |
| [Divine Intervention](https://www.icij.org/investigations/divine-intervention/) | 2006 | 32 | U.S. AIDS policy and faith-based conditions abroad. |
| [U.S. Aid in Latin America](https://www.icij.org/investigations/us-aid-latin-america/) | 2012 | 10 | Anti-drug aid routed through abusive or corrupt military, paramilitary and intelligence bodies. |
| [Windfalls of War](https://www.icij.org/investigations/windfalls-war/) | 2012 | 17 | The companies winning major U.S. contracts in postwar Iraq and Afghanistan. |
| [Evicted and Abandoned](https://www.icij.org/investigations/world-bank/) | 2015–2020 | 29 | The World Bank's broken promise to people displaced or harmed by development projects. |

### Machine-readable appendix

- `raw/projects.json` — all 50 projects with names, slugs, URLs, subjects, spans, item counts, award rows and cluster codes.
- `raw/classification.json` — slug → cluster.
- `raw/clusters.json` — cluster rules and aggregates.
- `raw/canon-coverage.json` — famous-canon denominators and shares.
- `raw/annual-counts.json` — resolved annual counts and date-source breakdown.
- `raw/awards-census.json` and `raw/data-assets.json` — separate prize and data-product frames.
- `raw/taxonomy-summary.json` and `raw/data-category.json` — ICIJ topic/sidebar counts and the nine-item Data archive.
- `raw/content-urls-complete.json`, unresolved-page metadata, sitemap XML files and duplicate audit — enumerated editorial frame, date recovery and raw site pulls.
