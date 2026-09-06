# ProPublica Corpus Census — Empirical Sampling Frame

**Agent 10 (census) | 2026-07-28**
**Purpose:** Establish what ProPublica has actually published — from their own site structure, not from memory of famous stories — so the flagship-cluster extraction agents' selection can be audited against the real distribution of output.

---

## 1. Method and sources (read this before using any number)

Everything below was pulled on 2026-07-28 directly from propublica.org. The site runs on WordPress (migrated recently; `wp-content/uploads/2026/07` assets), and its REST API is fully open. That let me replace scraping estimates with **counted** values from the CMS itself:

| What | Source | Nature |
|---|---|---|
| Series list (287 terms, names, descriptions, per-series item counts) | `https://www.propublica.org/wp-json/wp/v2/series?per_page=100` (3 pages; `X-WP-Total: 287`) | **Counted** |
| Series year spans (first/last article per series) | Per-series queries `wp/v2/posts?series=<id>&order=asc|desc&per_page=1` — 2 queries × 287 series | **Counted** (2 series resolved manually, flagged below) |
| Articles per year | `wp/v2/posts?after=YYYY-01-01&before=YYYY-12-31&per_page=1`, reading `X-WP-Total` | **Counted** |
| Topic taxonomy (32 terms + counts) | `wp/v2/topics` | **Counted**, but coverage-biased (see §3) |
| Units, locations taxonomies | `wp/v2/units`, `wp/v2/locations` | **Counted** |
| Awards (929 entries), Nerd Blog (168), podcasts (291), reports (84) | `wp/v2/awards`, `wp/v2/nerds`, `wp/v2/podcasts`, `wp/v2/reports` (custom post types) | **Counted** |
| Series index & pagination | https://www.propublica.org/series/ (paginates to `/series/page/15`) | Corroboration of the API list |
| Topics page taxonomy as presented | https://www.propublica.org/topics/ | Presentation layer |
| Local Reporting Network | https://www.propublica.org/local-reporting-network/ | Page parse (68 series links, 28 current partner slots) |
| Awards page | https://www.propublica.org/awards | Corroboration of `pp_award` data |
| Impact page / annual reports | https://www.propublica.org/impact ; 2025 Annual Report PDF: https://www.propublica.org/wp-content/uploads/2026/05/2025_ProPublica_AnnualReport_Final_digital.pdf | What they count as major work |
| Sitemap index | https://www.propublica.org/sitemap.xml — 4,759 daily child sitemaps, 2008–2026 | Structure corroboration |

**Known limits of the counts:**
- Series term counts include every content type the series taxonomy attaches to (articles, videos, podcasts, callouts) — e.g., *Paper Trail* (7) is all podcast episodes. Term-count totals are therefore "tagged items," slightly above pure article counts.
- Year spans are from the **articles** endpoint. Two series have no articles: *Losing Ground* (single 2014-12-08 interactive; date read from the series page `datetime` attribute) and *Paper Trail* (podcast, 2026-05-14→2026-07-09 from the podcasts endpoint). Both patched manually and flagged in the data file.
- One post may carry multiple series tags; per-cluster item sums (6,048 total) exceed the count of distinct series-tagged articles (5,628 — counted via a single all-287-IDs query).
- My cluster assignment of each series (§7) is judgment applied to their own names/descriptions — every underlying row is in Appendix A so the coding can be re-done differently.

---

## 2. Headline census numbers (all counted)

- **12,391 articles** published 2008 through 2026-07-28 (type `post`; excludes podcasts/videos/newsroom announcements).
- **287 named series/investigations** in their own series taxonomy — this is the backbone (Appendix A lists all 287 with years, item counts, URLs).
- **5,628 articles (45.4%)** belong to at least one named series. The other ~55% is non-series output — daily/explainer/aggregation pieces, especially in the 2008–2013 era.
- **929 award entries** on their awards system (2009–2026), including **22 Pulitzer entries** (10 wins incl. shared/partner, 12 finalist entries).
- **168 Nerd Blog posts** (2010–2022; peak 2012–2013; ≤2/yr since 2020 — the methodology blog is effectively dormant). Data Store lives at `propublica.org/datastore/` (redirects; live). Newsroom announcements (`@ProPublica`): 1,126. Corrections: 574 (a published corrections post type — itself a transparency artifact).
- **84 "reports"** — annual reports, Form 990s, financial statements, and (since ~2022) tri-annual impact reports.

### Articles per year (counted via X-WP-Total)

| Year | Articles | Year | Articles |
|---|---|---|---|
| 2008 | 655 | 2018 | 773 |
| 2009 | **1,477** | 2019 | 649 |
| 2010 | 1,092 | 2020 | **1,055** |
| 2011 | 707 | 2021 | 464 |
| 2012 | 545 | 2022 | 492 |
| 2013 | 471 | 2023 | 565 |
| 2014 | 429 | 2024 | 507 |
| 2015 | 422 | 2025 | 648 |
| 2016 | 577 | 2026 (→Jul 28) | 308 |
| 2017 | 555 | | |

Eras: 2008–2013 = 4,947 articles (blog-era high volume, much of it aggregation); 2014–2019 = 3,405 (fewer, longer investigations); 2020–2026 = 4,039 (COVID spike in 2020, then ~500–650/yr with 2025 rising). **Volume is not comparable across eras as "investigations per year"** — the early corpus is inflated by short daily posts. The sitemap index corroborates the shape: 176 publishing days in 2008, ~300 in 2009 and 2020, ~275–280 recently.

---

## 3. Their own taxonomy: topics, units, locations

### Topics (pp_topic, 32 terms; counts = tagged articles, all years)

Health Care 1,037 · Trump Administration 667 · Criminal Justice 587 · Regulation 560 · Politics 501 · Climate and Environment 489 · Immigration 413 · Racial Justice 380 · Education 322 · Technology 173 · Democracy 166 · Debt 164 · Labor 157 · Police 122 · Civil Rights 117 · Real Estate 117 · Taxes 109 · Military 99 · Pregnancy 91 · Sex and Gender 88 · Courts 81 · Abortion 72 · Health Insurance 68 · Prison 61 · Mental Health 59 · Pollution 58 · DOGE 43 · Stock 25 · Biden Administration 16 · Nonprofits 16 · USAID 11 · Jan. 6 5

The public https://www.propublica.org/topics/ page presents a curated ~22 of these (dropping admin-era tags and small ones). **Note what their own top-line taxonomy contains that the flagship clusters don't:** Immigration (#7, 413), Racial Justice (#8, 380), Education (#9, 322), Democracy (166), Military (99), Pregnancy/Abortion (91+72), Real Estate (117).

**Coverage limit (measured):** topic tagging is a modern practice. Share of each year's articles carrying ≥1 topic: 2008 1.2% (8/655) · 2010 1.7% · 2012 3.1% · 2014 9.1% · 2016 11.6% · 2018 66.0% · 2020 70.2% · 2022 68.3% · 2024 81.1% · 2025 90.1% · 2026 92.5%. **Topic counts describe the 2018+ corpus; they are nearly blind to 2008–2016.** For the older canon, the series taxonomy (retroactively complete) is the reliable frame.

### Units (pp_unit; counts span all content types)

National 12,650 · **Local Reporting Network 1,086** · Local 651 · **Electionland 409** · ProPublica Illinois (deprecated) 359 · Texas Tribune (co-publishing unit) 239.

Electionland — their recurring election-administration monitoring operation — is an entire 409-item unit that barely registers in the series taxonomy. It is the single largest named body of work with no home in the flagship clusters.

### Locations (pp_location; 50 states + DC tagged)

Top: Texas 301 · Illinois 202 · New York 172 · California 102 · Georgia 87 · Arizona 85 · Wisconsin 77 · Louisiana 76 · Alaska 75 · Tennessee 70 · Florida 68 · Oregon 68. Every state has ≥1. The Alaska/Louisiana/Mississippi/Idaho density reflects the LRN, not bureau presence.

---

## 4. Local Reporting Network (the structural growth engine)

From the page itself: founded **2018**; in **2024** they launched the **"50 State Initiative, a commitment to support yearlong projects in every state by 2029,"** plus a "Sustainability Desk" for short-term work with former partners. Current cycle: **28 partner slots** (27 newsrooms; CT Mirror twice) — Anchorage Daily News, Arizona Luminaria, The Assembly (NC), Baltimore Banner, BridgeDetroit, Capitol News Illinois, Centro de Periodismo Investigativo (PR), Concord Monitor, CT Mirror, Denver Gazette, Flatwater Free Press (NE), The Frontier (OK), Invisible Institute (Chicago), KQED, LAist, Lexington Herald-Leader, MLK50 (Memphis), NY Amsterdam News, Oregon Public Broadcasting, Philadelphia Inquirer, The Record/NorthJersey.com, Seven Days (VT), The Tributary (Jacksonville), Verite News (New Orleans), WBUR, Wisconsin Watch, WPLN Nashville.

The LRN page links **68 named series**; the LRN unit holds 1,086 items (~9% of all-time output, but a much larger share of recent investigative series). My cluster coding of the 68: criminal justice 15, environment/labor 12, gov-spending/disaster 6, healthcare 5, judicial ethics 3, consumer 2 — and **25/68 (37%) in areas outside the flagship clusters** (housing 6, education 4, tribal 4, children/family 4, plus democracy, immigration, religion, transportation). LRN topics are structurally state/local accountability: schools funding, sheriffs, coroners, guardianship, utility regulators, towing, title lending, tribal land.

---

## 5. Awards (prominence indicator — not the frame)

929 award entries 2009–2026; 38–96/yr since 2014 (peak 2019 = 96). The award mix (Pulitzers, Goldsmith, IRE, Peabody, Emmys, SEJ, National Awards for Education Reporting, health-care journalism awards, Best of News Design) itself shows the portfolio breadth.

All 22 Pulitzer entries, with the honored work and my cluster coding:

| Year | Result | Work | Cluster |
|---|---|---|---|
| 2010 | Win (Investigative) | Deadly Choices at Memorial | F4 healthcare |
| 2010 | Finalist (Public Service) | When Caregivers Harm | F4 |
| 2011 | Win (National) | The Wall Street Money Machine | F6 finance |
| 2016 | Win (Explanatory, shared) | An Unbelievable Story of Rape | F5 criminal justice |
| 2016 | Finalist (National) | Killing the Colorado | F8 environment |
| 2017 | Win (Public Service, w/ NY Daily News) | Nuisance abatement (NYPD) | F5 |
| 2017 | Finalist (Explanatory) | Machine Bias | F8/F5 algorithmic |
| 2018 | Finalist (Local) | The Tax Divide | F1 tax |
| 2018 | Finalist (Explanatory) | Lost Mothers | F4 |
| 2019 | **Win (Feature)** | **Trapped in Gangland (MS-13, immigration)** | **UNCOVERED: immigration** |
| 2019 | **Finalist (Public Service)** | **Zero Tolerance (family separation)** | **UNCOVERED: immigration** |
| 2020 | Win (Public Service, LRN w/ ADN) | Lawless (Alaska public safety) | F5 |
| 2020 | **Win (National)** | **Disaster in the Pacific (Navy 7th Fleet)** | **UNCOVERED: military** |
| 2021 | Finalist (Public Service) | COVID accountability reporting | F4 |
| 2022 | Finalist (Local) | Black Snow (sugar burns) | F8 |
| 2022 | Finalist (Feature) | Juvenile Injustice, Tennessee | F5 |
| 2023 | Finalist (Explanatory) | Stillbirths | F4 |
| 2024 | Win (Public Service) | Friends of the Court (SCOTUS) | F2 |
| 2024 | Finalist (Explanatory) | Uvalde response (w/ TX Tribune/FRONTLINE) | F5 |
| 2025 | **Win (Public Service)** | **Life of the Mother (abortion bans)** | **UNCOVERED: reproductive rights** |
| 2025 | Finalist (Explanatory) | America's Mental Barrier | F4 |
| 2026 | Win (Local, LRN w/ CT Mirror) | On the Hook (towing) | F6 consumer |

**4 of 22 Pulitzer entries (3 of 10 wins) fall outside the flagship clusters** — immigration twice, military, reproductive rights.

What they themselves foreground right now (site nav "Our Biggest Series," on every page): **Life of the Mother, The New Immigration, Friends of the Court** — plus "Reporting on: Dismantling USAID, Skipping Newborn Shots, Contaminated Water." Two of their three self-declared biggest series sit outside the flagship-cluster frame. The impact page and 2025 Annual Report lead with towing-law reform (CT), the Rx Inspector tool, the RealPage settlement, and NIH stillbirth funding — a consumer/health/data-tool mix, not the tax/SCOTUS canon.

---

## 6. Topic distribution of the actual portfolio

Counting method: each of the 287 series assigned to exactly one cluster (my coding of their own names/descriptions; full assignment in Appendix A); "items" = their term counts. Distinct series-tagged articles = 5,628; the ~55% non-series articles are distributed via the topics taxonomy only for 2018+ (see §3 limit).

| Cluster | Series | % series | Tagged items | % items |
|---|---|---|---|---|
| F1 Tax & wealth / IRS | 6 | 2.1% | 164 | 2.7% |
| F2 SCOTUS & judicial ethics | 3 | 1.0% | 46 | 0.8% |
| F3 Dark money & campaign finance | 3 | 1.0% | 168 | 2.8% |
| F4 Healthcare, pharma & insurance | 41 | 14.3% | 1,206 | 19.9% |
| F5 Criminal justice & policing | 42 | 14.6% | 732 | 12.1% |
| F6 Corporate/consumer finance/debt | 18 | 6.3% | 559 | 9.2% |
| F7 Gov spending/disaster/public funds | 15 | 5.2% | 179 | 3.0% |
| F8 Environment, labor & tech | 45 | 15.7% | 862 | 14.3% |
| F9 Methodology & newsroom meta | 12 | 4.2% | 390 | 6.4% |
| **Flagship total** | **185** | **64.5%** | **4,306** | **71.2%** |
| U Immigration & border | 9 | 3.1% | 197 | 3.3% |
| U Education & schools | 17 | 5.9% | 192 | 3.2% |
| U Children/family/social services | 11 | 3.8% | 155 | 2.6% |
| U Housing & homelessness | 10 | 3.5% | 127 | 2.1% |
| U Military/veterans/natsec | 13 | 4.5% | 248 | 4.1% |
| U Tribal affairs | 6 | 2.1% | 73 | 1.2% |
| U Democracy/elections/political ethics | 9 | 3.1% | 274 | 4.5% |
| U Religion | 3 | 1.0% | 21 | 0.3% |
| U International | 5 | 1.7% | 71 | 1.2% |
| U Nonprofits & charity | 4 | 1.4% | 58 | 1.0% |
| U Transportation safety | 4 | 1.4% | 47 | 0.8% |
| U Civil rights/racial justice/hate | 8 | 2.8% | 201 | 3.3% |
| U Reproductive rights post-Roe | 2 | 0.7% | 66 | 1.1% |
| U Other (sports medicine) | 1 | 0.3% | 12 | 0.2% |
| **Uncovered total** | **102** | **35.5%** | **1,742** | **28.8%** |

Largest single series all-time (items): Coronavirus 391 · Fracking 166 · Foreclosure Crisis 161 · Buying Your Vote 128 · Illinois Newsletter 125 (meta) · A Closer Look 124 (meta) · Trump, Inc. 98 · Dollars for Doctors 92 · The Trade 92 · Documenting Hate 90.

Coding choices that move numbers (flagged for reproducibility): *Life of the Mother* + *Post-Roe America* coded as uncovered "reproductive rights" rather than F4-healthcare (maternal-health series like Lost Mothers/Stillbirths stayed in F4); *Trump, Inc.* coded under political ethics (UG), arguable as F6; guns series (Under the Gun etc., ~79 items) kept inside F5; *America's Dairyland* (immigrant farmworkers) kept in F8-labor. Reversing all four calls moves the flagship share by only ±2–3 points.

---

## 7. Coverage diff — what the 8+1 flagship clusters miss

The flagship clusters capture roughly **two-thirds of named series and ~71% of series-tagged output**. What they miss, in order of significance:

### 7.1 Immigration & the border — the biggest single blind spot
9 series, 197 items, one 2019 Pulitzer win + one finalist, and one of the site's three self-declared "Biggest Series" today. Not a niche: arguably their most sustained post-2017 national beat.
- [Zero Tolerance](https://www.propublica.org/series/zero-tolerance) (2018–2022, 79) — family separation; the secret detention-audio scoop.
- [The New Immigration](https://www.propublica.org/series/the-new-immigration) (2024–2025, 25) — current flagship.
- [Inside the Border Patrol](https://www.propublica.org/series/inside-the-border-patrol) (2019–2020, 26); [Trapped in Gangland](https://www.propublica.org/series/ms-13-on-long-island) (2018–2019, 16); [Deported and Imprisoned](https://www.propublica.org/series/deported-and-imprisoned) (2025, 12, CECOT deportees); [The Taking](https://www.propublica.org/series/the-taking) (2017–2019, border-wall eminent domain); [No Sanctuary](https://www.propublica.org/series/no-sanctuary) (2018–2022); [The Travel Ban](https://www.propublica.org/series/immigration) (2017); [Billions on the Border](https://www.propublica.org/series/billions-on-the-border) (2022, Operation Lone Star spending).
- Plus the Immigration topic tag: 413 articles (7th-largest topic).

### 7.2 Education & schools — the largest series count of any uncovered area
17 series, 192 items, growing fast (7 of 17 started 2023+; heavy LRN). [The Quiet Rooms](https://www.propublica.org/series/illinois-school-seclusions-timeouts-restraints) (2019–2021, 27, IL seclusion rooms), [Restraints](https://www.propublica.org/series/restraints) (2014–2019, 23), [The Right to Read](https://www.propublica.org/series/the-right-to-read) (2022, 21, literacy), [School Wars](https://www.propublica.org/series/school-wars) (2024–2025, 16), [State of Disrepair](https://www.propublica.org/series/state-of-disrepair) (2023–2025, 16, Idaho school funding), [Frozen Out](https://www.propublica.org/series/frozen-out) (2025–2026, Alaska), [Unfit to Teach](https://www.propublica.org/series/unfit-to-teach) (2026, CA teacher discipline — already producing federal action per their impact page), [Crackdown on Student Threats](https://www.propublica.org/series/crackdown-on-student-threats) (2024–2026, TN), [Unequal Discipline](https://www.propublica.org/series/unequal-discipline) (2022–2026, NM Native students), [Campus Complicity](https://www.propublica.org/series/campus-complicity), [Dollars for Profs](https://www.propublica.org/series/dollars-for-profs), [The Failure Track](https://www.propublica.org/series/the-failure-track), [Evaluating Charter Schools](https://www.propublica.org/series/evaluating-charter-schools), [Inside Shrub Oak](https://www.propublica.org/series/inside-shrub-oak), [Chaos at the School Board](https://www.propublica.org/series/chaos-at-the-school-board), [Financial Aid Loophole](https://www.propublica.org/series/college-financial-aid-loophole), [The Pandemic and Illinois Schools](https://www.propublica.org/series/the-pandemic-and-illinois-schools). Education topic tag: 322 articles.

### 7.3 Military, veterans & national security
13 series, 248 items, a 2020 Pulitzer win. Early-era: [Disposable Army](https://www.propublica.org/series/disposable-army) (2008–2013, 39, war-zone contractors), [Brain Wars](https://www.propublica.org/series/brain-wars) (2010–2012, 42, TBI), [Reliving Agent Orange](https://www.propublica.org/series/reliving-agent-orange) (2009–2019, 33), [Lost to History](https://www.propublica.org/series/lost-to-history), [Failing the Fallen](https://www.propublica.org/series/failing-the-fallen), [The Drone War](https://www.propublica.org/series/drones). Modern: [Disaster in the Pacific](https://www.propublica.org/series/navy-accidents-pacific-7th-fleet) (2019–2020, 26), [Inside Trump's VA](https://www.propublica.org/series/inside-trump-va) (2018–2021, 32), [Veterans' Care at Risk](https://www.propublica.org/series/veterans-care-at-risk) (2025–2026, 13), [Veterans Without Assistance](https://www.propublica.org/series/veterans-without-assistance) (2024), [Trauma After Tragedy](https://www.propublica.org/series/trauma-after-tragedy), plus terrorism sets ([Attacks in Europe](https://www.propublica.org/series/terror-in-europe), [Terror in Little Saigon](https://www.propublica.org/series/terror-in-little-saigon)).

### 7.4 Democracy, elections administration & political ethics
9 series, 274 items — plus the **Electionland unit (409 items)** that the series frame doesn't capture. [Trump, Inc.](https://www.propublica.org/series/trump-inc) (2018–2023, 98, w/ WNYC — business-conflicts investigation), [The Insurrection](https://www.propublica.org/series/the-insurrection) (2021–2022, 36, incl. the Parler video archive), [Redistricting](https://www.propublica.org/series/redistricting) (2011–2013, 24), [A User's Guide to Democracy](https://www.propublica.org/series/a-users-guide-to-democracy) (2022), [Big Jim](https://www.propublica.org/series/big-jim) (2019–2023, WV governor conflicts), [The Real Bosses of New Jersey](https://www.propublica.org/series/the-real-bosses-of-new-jersey) (2019–2020), [Louisiana's Ethical Swamp](https://www.propublica.org/series/louisianas-ethical-swamp) (2018–2019), [The Breakdown](https://www.propublica.org/series/the-breakdown) (2015–2017, 49), [Politic-IL Insider](https://www.propublica.org/series/politic-il-insider-mick-dumke-propublica-illinois-politics). Distinct from flagship-3 (campaign finance): this is election *administration*, gerrymandering, officeholder conflicts, and anti-democratic violence.

### 7.5 Civil rights, racial justice & hate
8 series, 201 items. [Documenting Hate](https://www.propublica.org/series/documenting-hate) (2016–2021, 90 — their flagship crowdsourced data collaboration), [Segregation Now](https://www.propublica.org/series/segregation-now) (2012–2015, 33), [Segregation Academies](https://www.propublica.org/series/segregation-academies) (2024–2025, 13), [Uprooted](https://www.propublica.org/series/uprooted) (2023–2024, 14, university land takings), [Dispossessed](https://www.propublica.org/series/dispossessed) (2019–2024, Black land loss), [Inside Terrorgram](https://www.propublica.org/series/the-rise-and-fall-of-terrorgram) (2024–2025, w/ FRONTLINE), [Freedom Summer](https://www.propublica.org/series/freedom-summer) (2014), [Sex and Gender](https://www.propublica.org/series/sex-and-gender) (2013–2016). Racial Justice topic tag: 380 articles (8th largest).

### 7.6 Children, family services & the social safety net
11 series, 155 items — a signature LRN/Illinois strength. [Stuck Kids](https://www.propublica.org/series/stuck-kids) (2018–2020, 24), [Level 14](https://www.propublica.org/series/level-14) (2015–2017, 20), [Overpolicing Parents](https://www.propublica.org/series/overpolicing-parents) (2022–2025, 11, w/ NBC), [Nowhere to Go](https://www.propublica.org/series/nowhere-to-go) (2022–2023, NM foster care), [Division of Families](https://www.propublica.org/series/division-of-families) (2024, GA), [Parental Alienation](https://www.propublica.org/series/parental-alienation) (2022–2024, family courts), [The Unbefriended](https://www.propublica.org/series/the-unbefriended) (2024–2026, 12, NY guardianship), [State of Denial](https://www.propublica.org/series/state-of-denial) (2020–2021, 24, AZ disability services), [Culture of Cruelty](https://www.propublica.org/series/culture-of-cruelty) (2022–2025, 19, IL institutions), [Welfare States](https://www.propublica.org/series/welfare-states) (2021–2024, TANF), [Profiting From the Poor](https://www.propublica.org/series/profiting-from-the-poor) (2019–2020, Memphis).

### 7.7 Housing & homelessness
10 series, 127 items. [The Rent Racket](https://www.propublica.org/series/the-rent-racket) (2015–2017, 35, NYC), [HUD's House of Cards](https://www.propublica.org/series/huds-house-of-cards) (2018–2022, 24), [Rent Barons](https://www.propublica.org/series/rent-barons) (2022–2025, 15 — the RealPage price-fixing investigation that just produced a DOJ settlement per their impact page), [The Ugly Truth](https://www.propublica.org/series/the-ugly-truth) (2023–2025, HomeVestors), [Checked Out](https://www.propublica.org/series/checked-out) (2023–2024, LA residential hotels), [Swept Away](https://www.propublica.org/series/swept-away) (2024–2025, encampment sweeps), [Homeowner Hell](https://www.propublica.org/series/homeowner-hell) (2022–2023, HOA foreclosures), [Invisible Walls](https://www.propublica.org/series/invisible-walls) (2019–2020, CT segregation), [Locked Out](https://www.propublica.org/series/locked-out) (2024), [Coming to Collect](https://www.propublica.org/series/coming-to-collect) (2020). Real Estate topic: 117 articles.

### 7.8 Tribal affairs & Indigenous rights
6 series, 73 items — small but almost entirely post-2020 and evidentiarily unique. [The Repatriation Project](https://www.propublica.org/series/the-repatriation-project) (2023–2025, 25 — NAGPRA compliance database), [Broken Promises](https://www.propublica.org/series/broken-promises) (2022–2025, 20, Columbia River salmon treaty), [Waiting for Water](https://www.propublica.org/series/waiting-for-water) (2023–2026, tribal water rights), [Promised Land](https://www.propublica.org/series/promised-land) (2020–2023, 13, Hawaiian Home Lands), [Lessons Lost](https://www.propublica.org/series/lessons-lost) (2020–2021, Bureau of Indian Education), [Power Grab](https://www.propublica.org/series/power-grab) (2024, WA climate policy vs tribal rights).

### 7.9 Smaller distinct areas
- **Reproductive rights post-Roe** (2 series, 66 items, 2025 Pulitzer): [Life of the Mother](https://www.propublica.org/series/life-of-the-mother) (2024–2026, 36), [Post-Roe America](https://www.propublica.org/series/post-roe-america) (2022–2024, 30). (Maternal-health siblings Lost Mothers/Stillbirths coded F4.)
- **International** (5 series, 71): [Finding Oscar](https://www.propublica.org/series/finding-oscar) (2012–2017), [Firestone and the Warlord](https://www.propublica.org/series/firestone-and-the-warlord) (2014–2015), [Shadow Diplomats](https://www.propublica.org/series/shadow-diplomats) (2022–2023, w/ ICIJ), [The Syria Documents](https://www.propublica.org/series/the-syria-documents) (2012), [The End of Aid](https://www.propublica.org/series/the-end-of-aid) (2025–2026, USAID dismantling — currently nav-featured).
- **Nonprofit & charity accountability** (4 series, 58): [Red Cross](https://www.propublica.org/series/red-cross) (2012–2018, 40 — Haiti/Sandy), [Unprotected](https://www.propublica.org/series/unprotected) (2018–2019, More Than Me), [St. Jude's Unspent Billions](https://www.propublica.org/series/st-judes-unspent-billions) (2021–2022), [Bittersweet](https://www.propublica.org/series/bittersweet) (2021, Hershey Trust). NB: Nonprofit Explorer (the 990 tool) is methodology-cluster infrastructure, but the *editorial* charity beat is uncovered.
- **Transportation safety** (4 series, 47): [America's Dangerous Trucks](https://www.propublica.org/series/americas-dangerous-trucks) (2023, underride), [Train Country](https://www.propublica.org/series/train-country) (2023–2026, 14), [Flight Risk](https://www.propublica.org/series/flight-risk) (2021, Alaska aviation/FAA), [Body Scanners](https://www.propublica.org/series/body-scanners) (2011–2013, TSA).
- **Religion & religious power** (3 series, 21): [Sins of Omission](https://www.propublica.org/series/sins-of-omission) (2020, diocese abuser lists), [Forgive and Forget](https://www.propublica.org/series/forgive-and-forget) (2025–2026, Old Apostolic Lutheran Church), [Faith in Power](https://www.propublica.org/series/faith-in-power) (2024, Christian right).
- **Sports medicine**: [Chasing an Edge](https://www.propublica.org/series/chasing-an-edge) (2014–2017, 12, doping).

---

## 8. Second-wave extraction recommendations (ranked)

Ranked by output volume × evidentiary distinctiveness (does the area use evidence types/methods the flagship clusters don't?). Each is seedable directly from the URLs here + Appendix A — no memory-based seeding needed.

**R1. Immigration & the border** (9 series, 197 items + 413 topic-tagged articles; 2 Pulitzer entries; a top-3 "Biggest Series" by their own nav).
Distinct evidence: immigration-court (EOIR) records outside PACER; ICE/CBP detention, inspection and use-of-force records; leaked/secret audio (Zero Tolerance); eminent-domain land records (The Taking); state border-spending ledgers (Billions on the Border); case-by-case deportee verification against foreign records (Deported and Imprisoned). Seeds: zero-tolerance, the-new-immigration, inside-the-border-patrol, ms-13-on-long-island, deported-and-imprisoned, the-taking, billions-on-the-border, no-sanctuary, immigration (all at `propublica.org/series/<slug>`).

**R2. Education, children & family services** (§7.2 + §7.6 combined: 28 series, 347 items; the largest uncovered series pool and the LRN's core).
Distinct evidence: state teacher-licensure and discipline databases; restraint/seclusion incident logs; juvenile-court and child-welfare agency records (negotiating access to confidential records is a method in itself); school-finance formula analysis; guardianship courts. Seeds: illinois-school-seclusions-timeouts-restraints, stuck-kids, overpolicing-parents, the-unbefriended, unfit-to-teach, state-of-disrepair, unequal-discipline, crackdown-on-student-threats, the-right-to-read, level-14, welfare-states.

**R3. Military, veterans & national security** (13 series, 248 items; 2020 Pulitzer win).
Distinct evidence: military accident/mishap investigations, courts-martial and service-record analysis, VA claims/staffing data, Pentagon IG material, MIA/casualty records — none used by the 8 flagship clusters. (Direct platform relevance: BCMR/BCNR + CAAF/MilJustice tools already exist here.) Seeds: navy-accidents-pacific-7th-fleet, disposable-army, inside-trump-va, veterans-care-at-risk, brain-wars, reliving-agent-orange, drones.

**R4. Housing & homelessness** (10 series, 127 items; RealPage settlement just landed).
Distinct evidence: HUD inspection (REAC) scores, eviction dockets, rent-stabilization filings, HOA foreclosure records, algorithmic rent-setting analysis (Rent Barons bridges to tech accountability), property/deed chains — the closest match to this platform's property-records roadmap. Seeds: rent-barons, huds-house-of-cards, the-rent-racket, the-ugly-truth, checked-out, swept-away, homeowner-hell.

**R5. Democracy, elections administration & political ethics** (9 series, 274 items + Electionland unit 409).
Distinct evidence: real-time crowdsourced poll monitoring (Electionland's collaborative methodology), precinct/certification records, redistricting cartography, officeholder financial-conflict tracing (Trump, Inc.; Big Jim), platform-video OSINT (The Insurrection/Parler archive). Seeds: trump-inc, the-insurrection, redistricting, big-jim, the-real-bosses-of-new-jersey, louisianas-ethical-swamp; Electionland via the `democracy` topic and unit pages.

**R6. Tribal affairs & Indigenous rights** (6 series, 73 items — lowest volume, highest evidentiary distinctiveness).
Distinct evidence: NAGPRA inventories (they built a compliance database), treaty/trust-obligation documents, BIA/BIE records, water-rights adjudications. No flagship cluster produces these methods. Seeds: the-repatriation-project, broken-promises, waiting-for-water, promised-land, lessons-lost, power-grab.

Honorable mentions if capacity allows: **Civil rights/hate** (Documenting Hate's crowdsourced-tip infrastructure is methodologically unique; 201 items) and **Reproductive rights** (Life of the Mother's maternal-mortality-review-committee sourcing; 66 items, current Pulitzer canon). Religion, transportation, nonprofits, and international are each coherent but small; they can ride as satellites of R2/R6-style extraction rather than standalone clusters.

---

## 9. Sampling-frame notes

**What fraction do the 8 flagship clusters represent?** By their own series taxonomy: **64.5% of named series (185/287) and ~71% of series-tagged items (4,306/6,048)**; excluding the meta/methodology bucket, 60% of series. Roughly **one-third of ProPublica's named investigative portfolio is invisible to the flagship frame.** (Counted, with the coding caveats of §6; series-tagged work is itself only 45.4% of all articles — the flagship share of untagged daily output cannot be measured for pre-2018 years.)

**Selection biases a flagship-only analysis carries:**
1. **Award-canon bias (measurable):** flagship clusters cover 18/22 Pulitzer entries (82%) but only ~71% of output — the frame over-represents award-anointed work. And the misses are not random: 3 of the 5 most recent Pulitzer *wins* (2019 Gangland, 2020 Pacific, 2025 Life of the Mother) are in uncovered areas.
2. **National-vs-local bias:** 37% of the 68 Local Reporting Network series fall in uncovered areas, and the uncovered areas (education, housing, child welfare, tribal, local courts) are precisely where the LRN concentrates. With the 2024 "50 State Initiative" committing to yearlong projects in all 50 states by 2029, the uncovered share of *new* series will grow. A flagship-only frame reads ProPublica as a national data-journalism shop and misses that its growth engine is state/local records work.
3. **Evidence-type bias:** the flagship clusters contain most of their large-scale structured-data work (Dollars for Docs, Secret IRS Files, Machine Bias, Nonprofit Explorer, Surgeon Scorecard). The uncovered third leans on confidential/agency records, courts below the federal level, crowdsourcing (Documenting Hate, Electionland), leaked audio, and state-agency FOIA — a flagship-only evidence-pattern extraction will over-learn "big dataset + outlier analysis" and under-learn "state agency records + human sourcing."
4. **Era bias is NOT material:** uncovered share is ~35% among series ended before 2017 and ~36% among the 100 series active in 2024+ — the blind spot is structural, not a recency artifact. (Counted from spans.)
5. **Topic-taxonomy trap:** their pp_topic counts only describe 2018+ output (tagging coverage 66–93% there vs 1–12% for 2008–2016). Any distributional claim sourced from their topic pages inherits this censoring; the series taxonomy is retroactively complete and is the correct frame for the older canon.

**Does 2024–2026 output differ from the older canon?** Yes, three measurable shifts: (a) administration-accountability surge — Trump Administration (667), DOGE (43), USAID (11) tags, and series like The End of Aid and Veterans' Care at Risk make "dismantling-of-government" coverage a top-line beat straddling flagship-7 and uncovered democracy/military/international areas; (b) LRN-ization — most new series are state-scoped (36 of the 100 series active in 2024+ are in uncovered, largely local, areas); (c) reproductive-health prominence — Pregnancy+Abortion tags (91+72) and the 2025 Pulitzer sit in an area the flagship frame folds awkwardly into "healthcare." Headline volume itself is stable (~500–650 articles/yr since 2021; 2025 = 648, above 2024's 507).

**Frame completeness check for the parallel analysis:** the 8 clusters + methodology cover the canonical famous investigations well (every pre-2019 Pulitzer entry). What the census adds: ProPublica's actual portfolio is a ~2/3–1/3 split between that canon's territory and a state/local-services-and-rights territory (schools, kids, housing, tribes, immigrants, soldiers, elections) that produces their most recent prizes and their own top-of-site flagships. A second wave along §8 R1–R6 brings honest coverage to ~95% of named-series output.

---

## Appendix A — Full series backbone (287 series, grouped by cluster assignment)

Every named series in their taxonomy as of 2026-07-28, with first–last article years (counted), tagged-item counts (counted), and URL. Machine-readable source data alongside this report: `raw/series-spans.json` (name/slug/count/first/last/description for all 287), `raw/classification.json` (slug→cluster), `raw/clusters.json` (aggregates).

### Flagship 1 — Tax & wealth / IRS — 6 series, 164 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [The Secret IRS Files](https://www.propublica.org/series/the-secret-irs-files) | 2021–2024 | 55 | A massive trove of tax information obtained by ProPublica, covering thousands of America’s wealthiest individuals, reveals what’s inside the… |
| [The TurboTax Trap](https://www.propublica.org/series/the-turbotax-trap) | 2013–2024 | 46 | ProPublica has long detailed how Intuit, the maker of TurboTax, and other companies have worked against making tax preparation easier and le… |
| [Gutting the IRS](https://www.propublica.org/series/gutting-the-irs) | 2018–2023 | 21 | A multiyear campaign to slash the IRS budget has left it understaffed and on the defensive. That’s been good news for tax cheats, the rich, … |
| [The ProPublica Free Tax Guide](https://www.propublica.org/series/the-propublica-free-tax-guide) | 2020–2023 | 20 | ProPublica has reported extensively about taxes, the IRS Free File program and the IRS. Specifically, the ways in which the for-profit tax p… |
| [The Tax Divide](https://www.propublica.org/series/the-tax-divide) | 2017–2018 | 17 | For years, the Cook County assessor’s office overvalued low-priced properties while undervaluing high-priced ones. The deeply flawed system … |
| [The Inside Edge](https://www.propublica.org/series/the-inside-edge) | 2023–2023 | 5 | Top executives and investors who are privy to key information enjoy uncanny results, according to trading and tax records in leaked IRS data… |

### Flagship 2 — Supreme Court & judicial ethics — 3 series, 46 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Friends of the Court](https://www.propublica.org/series/supreme-court-scotus) | 2023–2025 | 35 | Supreme Court Justice Clarence Thomas’ decadeslong friendship with real estate tycoon Harlan Crow and Samuel Alito’s luxury travel with bill… |
| [The Untouchables](https://www.propublica.org/series/the-untouchables) | 2019–2021 | 8 | South Carolina’s judges are some the most powerful, but least scrutinized officials in the criminal justice system, thanks in part to the st… |
| [Mayor, Judge and Jury](https://www.propublica.org/series/mayor-judge-and-jury) | 2023–2024 | 3 | If you break the law in many small towns in Louisiana, the mayor could be your judge. The arrangement is ripe for conflict of interest. |

### Flagship 3 — Dark money & campaign finance — 3 series, 168 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Buying Your Vote](https://www.propublica.org/series/buying-your-vote) | 2011–2015 | 128 | A series of court rulings led to the creation of super PACs and an influx of “dark money” into politics, fundamentally changing how election… |
| [Free the Files](https://www.propublica.org/series/free-the-files) | 2012–2012 | 34 | Outside groups are spending hundreds of millions to influence the coming elections. Help unlock outside spending by “freeing” political ad b… |
| [The Money Game](https://www.propublica.org/series/the-money-game-illinois-governors-race-campaign-finance-widget) | 2018–2018 | 6 | The 2018 race for Illinois governor could be the most expensive in U.S. history. To track this money circus, ProPublica Illinois has created… |

### Flagship 4 — Healthcare, pharma & insurance — 41 series, 1206 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Coronavirus](https://www.propublica.org/series/coronavirus) | 2020–2022 | 391 | Read our latest investigations into the crisis response and public health infrastructure. |
| [Dollars for Doctors](https://www.propublica.org/series/dollars-for-docs) | 2010–2022 | 92 | ProPublica is tracking the financial ties between doctors and medical companies. |
| [Patient Safety](https://www.propublica.org/series/patient-safety) | 2012–2016 | 70 | More than 1 million patients suffer harm each year while being treated in the U.S. health care system. Even more receive substandard care or… |
| [Obamacare and You](https://www.propublica.org/series/obamacare-and-you) | 2013–2014 | 53 | The Affordable Care Act, passed in 2010, is the most significant health care overhaul in a generation. It seeks to decrease the number of pe… |
| [The Prescribers](https://www.propublica.org/series/prescribers) | 2013–2019 | 49 | Never-before-released government prescription records shows that some doctors and other health professionals across the country prescribe la… |
| [When Caregivers Harm](https://www.propublica.org/series/nurses) | 2008–2017 | 40 | California nurses accused of serious wrongdoing have often been left free to practice for years while their cases were being investigated — … |
| [Policing Patient Privacy](https://www.propublica.org/series/patient-privacy) | 2014–2018 | 38 | ProPublica is exploring how patient privacy violations are affecting patients and the medical care they receive. |
| [Lost Mothers](https://www.propublica.org/series/lost-mothers) | 2017–2024 | 33 | The U.S. has the highest rate of deaths related to pregnancy and childbirth in the developed world. Half of the deaths are preventable, vict… |
| [Heart Failure](https://www.propublica.org/series/heart-failure) | 2018–2024 | 30 | ProPublica and the Houston Chronicle are investigating troubles at Baylor St. Luke’s in Houston, an illustrious heart program that has recen… |
| [Stillbirths](https://www.propublica.org/series/stillbirths) | 2022–2025 | 23 | The U.S. has not prioritized stillbirth prevention, and American parents are losing babies even as other countries make larger strides to re… |
| [Rx Roulette](https://www.propublica.org/series/rx-roulette) | 2025–2026 | 22 | The agency charged with ensuring the safety of the country’s drug supply has for years allowed risky drugs into your medicine cabinet. A fin… |
| [Birth Rights](https://www.propublica.org/series/birth-rights) | 2021–2022 | 21 | The NICA program was intended to reduce doctors’ malpractice bills and provide a dignified existence and financial cushion for families crus… |
| [Breach of Trust](https://www.propublica.org/series/breach-of-trust) | 2023–2026 | 21 | When health care workers sexually abuse their patients in Utah, survivors confront obstacles to justice: in the law, in the courts — and in … |
| [With Every Breath](https://www.propublica.org/series/with-every-breath) | 2023–2025 | 21 | Philips Respironics received thousands of complaints about a dangerous defect in its breathing machines but kept them secret for years as st… |
| [Uncovered](https://www.propublica.org/series/uncovered) | 2023–2025 | 19 | Health insurers reject millions of claims for treatment every year in America. Corporate insiders, recordings and internal emails expose the… |
| [Health Insurance Hustle](https://www.propublica.org/series/the-health-insurance-hustle) | 2018–2021 | 17 | Americans pay insurance companies to make sure their medical needs are covered — and at a cost they can afford. But games, side deals and hi… |
| [America’s Mental Barrier](https://www.propublica.org/series/americas-mental-barrier) | 2024–2026 | 16 | American insurance companies — quietly, and with little government pushback — have assumed an outsize role in mental health care. People in … |
| [Omniscan](https://www.propublica.org/series/general-electric-omniscan) | 2009–2013 | 16 | General Electric is in a liability fight over a rare disease that has been linked to dyes used in MRIs. Nearly all cases of the disease, nep… |
| [Dialysis](https://www.propublica.org/series/dialysis) | 2010–2012 | 15 | Nearly 40 years after Congress created a unique entitlement for patients with kidney failure, U.S. death rates and per-patient costs are amo… |
| [Overdose](https://www.propublica.org/series/overdose) | 2013–2015 | 15 | About 150 Americans a year die by accidentally taking too much acetaminophen, the active ingredient in Tylenol. The toll does not have to be… |
| [Sloan Kettering’s Crisis](https://www.propublica.org/series/sloan-kettering-cancer-centers-crisis) | 2018–2020 | 15 | Memorial Sloan Kettering Cancer Center in New York is re-examining conflicts of interest after articles by ProPublica and The New York Times… |
| [Arterial Motives](https://www.propublica.org/series/arterial-motives) | 2023–2026 | 14 | Millions of Americans suffer from clogged arteries. But doctors have dangerous incentives to perform excessive and risky procedures. |
| [Right to Fail](https://www.propublica.org/series/right-to-fail) | 2017–2019 | 14 | Hunger, confusion, desperation and death. In 2014, thousands of New Yorkers with severe mental illness living in troubled group homes won th… |
| [Life and Death in Assisted Living](https://www.propublica.org/series/life-and-death-in-assisted-living) | 2013–2014 | 13 | More and more elderly Americans are choosing to spend their later years in assisted living facilities. But is this loosely regulated, multi-… |
| [Nursing Homes](https://www.propublica.org/series/nursing-homes) | 2012–2019 | 13 | Our Nursing Home Inspect tool allows anyone to easily search and analyze the details of recent nursing home inspections, as well as penaltie… |
| [Vaccines](https://www.propublica.org/series/vaccines) | 2020–2022 | 13 | Tracking the rollout of the COVID-19 vaccines as the United States emerges from the pandemic. |
| [Examining Medicare](https://www.propublica.org/series/examining-medicare) | 2014–2017 | 12 | A closer look at the services delivered by providers in Medicare’s Part B program — and the money they collect. |
| [Roots of an Outbreak](https://www.propublica.org/series/roots-of-an-outbreak) | 2023–2023 | 12 | The next pandemic is just a forest clearing away. We’re not doing enough to prevent viruses from spilling over from wildlife to humans. |
| [Wasted Medicine](https://www.propublica.org/series/wasted-medicine) | 2017–2018 | 12 | Billions of dollars are routinely wasted every day by health care providers in the United States — and it’s driving up the cost of care for … |
| [A 911 Emergency](https://www.propublica.org/series/a-911-emergency) | 2019–2021 | 11 | The way Rhode Island handles medical emergencies puts people in harm’s way. |
| [Crisis Point](https://www.propublica.org/series/crisis-point) | 2022–2024 | 10 | State leaders promised to expand young people’s access to mental health services. Now, families are struggling to get care for youth in cris… |
| [Unchecked](https://www.propublica.org/series/unchecked) | 2021–2022 | 10 | In the U.S., food poisoning sickens roughly 1 in 6 people every year, and a fractured and largely toothless food safety system fails to prot… |
| [COVID-19 Inequities in Chicago](https://www.propublica.org/series/covid-19-inequities-in-chicago) | 2020–2020 | 9 | ProPublica’s Midwest reporters examine the impact of the COVID-19 outbreak on Chicago’s most vulnerable communities, including the dispropor… |
| [The $3 Million Research Breakdown](https://www.propublica.org/series/research-breakdown-uic-university-of-illinois-chicago-mani-pavuluri) | 2018–2019 | 9 | The University of Illinois at Chicago’s acclaimed child psychiatrist Mani Pavuluri put vulnerable children at serious risk in one of her cli… |
| [The Hospice Hustle](https://www.propublica.org/series/the-hospice-hustle) | 2022–2024 | 8 | Easy money and a lack of regulation have transformed a crusade to provide death with dignity into a $22 billion industry rife with fraud, ab… |
| [Opioid Billionaires](https://www.propublica.org/series/opioid-billionaires) | 2018–2021 | 6 | Long insulated by their philanthropy, the Sackler family faces a growing backlash over the role of their company, Purdue Pharma, in spawning… |
| [Broken Pathways](https://www.propublica.org/series/broken-pathways) | 2025–2025 | 5 | Caught up in technical glitches and red tape, thousands of low-income Georgians have given up on trying to get free health care under Pathwa… |
| [Critical Condition](https://www.propublica.org/series/critical-condition) | 2020–2021 | 5 | Rural communities desperate to save their hospitals are turning to for-profit companies for help, but many fail to deliver on lofty promises… |
| [HeartWare](https://www.propublica.org/series/heartware) | 2021–2022 | 5 | A life-sustaining device was implanted inside thousands of people, even though the federal government knew about serious problems. |
| [A Simple Shot](https://www.propublica.org/series/a-simple-shot) | 2026–2026 | 4 | Vitamin K shots, given at birth to prevent uncontrollable bleeding, are not vaccines. Yet this long-standard injection has become collateral… |
| [Long-Term Challenge](https://www.propublica.org/series/long-term-challenge) | 2023–2024 | 4 | With the disappearance of nursing home beds across Maine, thousands of aging Mainers are being sent to “nonmedical” residences that aren’t e… |

### Flagship 5 — Criminal justice & policing — 42 series, 732 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Law & Disorder](https://www.propublica.org/series/law-and-disorder) | 2008–2013 | 81 | In the chaotic aftermath of Hurricane Katrina, NOPD officers shot 11 civilians, five of whom died. Criminal cases have now been brought agai… |
| [Under the Gun](https://www.propublica.org/series/guns) | 2012–2024 | 66 | As America emerged from the pandemic, communities continued to experience a rising tide of gun violence. School shootings and the rate of ch… |
| [Lawless](https://www.propublica.org/series/lawless) | 2019–2025 | 54 | The Anchorage Daily News and ProPublica are investigating sexual violence in Alaska, and why the situation isn’t getting better. |
| [The NYPD Files](https://www.propublica.org/series/the-nypd-files) | 2020–2026 | 44 | ProPublica reporters uncover abuse and impunity inside the NYPD, using confidential documents and insider interviews, giving the public unpr… |
| [Presidential Pardons](https://www.propublica.org/series/presidential-pardons) | 2011–2017 | 41 | White criminals seeking presidential pardons are nearly four times as likely to succeed as people of color, a ProPublica examination has fou… |
| [Post Mortem](https://www.propublica.org/series/post-mortem) | 2011–2014 | 30 | A year-long investigation into the nation’s 2,300 coroner and medical examiner offices uncovered a deeply dysfunctional system that quite li… |
| [Accused in Elkhart](https://www.propublica.org/series/accused-in-elkhart) | 2018–2024 | 29 | Indiana’s first man to be pardoned based on innocence was tried in Elkhart County. But that troubling case doesn’t stand alone. In a county … |
| [Out of Order](https://www.propublica.org/series/out-of-order) | 2013–2020 | 29 | The innocent can wind up in prison. The guilty can be set free. But New York City prosecutors who withhold evidence, tolerate false testimon… |
| [The Price Kids Pay](https://www.propublica.org/series/the-price-kids-pay) | 2022–2025 | 26 | Illinois law bans schools from fining students. But police routinely issue tickets to children for minor misbehavior at school, burdening fa… |
| [Juvenile Injustice, Tennessee](https://www.propublica.org/series/juvenile-injustice-tennessee) | 2021–2025 | 19 | Children in Rutherford County have been arrested and jailed at rates unparalleled in the state. We’re investigating how that happened — and … |
| [The Etan Patz Case](https://www.propublica.org/series/the-etan-patz-case) | 2014–2025 | 18 | The disappearance of a 6-year-old New York boy has mystified and frustrated police for decades. The trial of his alleged killer ended with a… |
| [Walking While Black](https://www.propublica.org/series/walking-while-black) | 2017–2018 | 17 | Race can affect the enforcement of laws on a wide range of ordinary conduct, from driving to bicycling. Here’s our look at whether that kind… |
| [A Sick System](https://www.propublica.org/series/a-sick-system) | 2018–2019 | 16 | Editor’s Note, Jan. 18, 2019: Several stories in this series about Oregon’s handling of people found “guilty except for insanity” contain si… |
| [Busted](https://www.propublica.org/series/busted) | 2016–2023 | 16 | Tens of thousands of people every year are sent to jail based on the results of a $2 roadside drug test. Widespread evidence shows that thes… |
| [Black Boxes](https://www.propublica.org/series/black-boxes) | 2020–2024 | 15 | Body-worn cameras were supposed to deliver a revolution in transparency and accountability to policing. But in cities across America, the re… |
| [Ignoring Innocence](https://www.propublica.org/series/ignoring-innocence) | 2017–2021 | 15 | Even after proving their innocence, defendants locked away for crimes they didn’t commit are sometimes told they have to plead guilty if the… |
| [Nuisance Abatement](https://www.propublica.org/series/nuisance-abatement) | 2016–2017 | 15 | How New York City police are using little-known laws to kick people out of their homes, even if they haven’t been charged with a crime. |
| [Criminal Justice Rollback](https://www.propublica.org/series/criminal-justice-rollback) | 2024–2026 | 14 | Criminal justice reformers spent years trying to fix Louisiana’s reputation as the incarceration capital of the country. Now, under Gov. Jef… |
| [Grace](https://www.propublica.org/series/grace) | 2020–2023 | 14 | (no description on series term) |
| [Overcorrection](https://www.propublica.org/series/overcorrection) | 2019–2021 | 14 | (no description on series term) |
| [Unwatched](https://www.propublica.org/series/unwatched) | 2021–2025 | 14 | The sheriff of Louisiana’s Jefferson Parish answers only to voters. In this conservative suburb, that translates to nearly unchecked power. |
| [Blood Will Tell](https://www.propublica.org/series/blood-will-tell) | 2018–2020 | 12 | Bloodstain-pattern analysis, and the experts who specialize in it, have helped prosecutors secure convictions across the country. But how mu… |
| [Cold Justice](https://www.propublica.org/series/cold-justice) | 2021–2024 | 12 | Starting in the 1970s, a Baltimore doctor quietly preserved DNA evidence from rape victims, believing science would eventually catch up. Muc… |
| [Defenseless](https://www.propublica.org/series/defenseless) | 2020–2022 | 11 | An investigation by The Maine Monitor and ProPublica found that more than a quarter of Maine attorneys disciplined in the past decade for se… |
| [Slow Justice](https://www.propublica.org/series/slow-justice) | 2024–2026 | 10 | Although Alaska court rules say defendants must go on trial within 120 days from arrest, judges have routinely granted requests for postpone… |
| [Committed to Jail](https://www.propublica.org/series/committed-to-jail) | 2023–2025 | 9 | In Mississippi, many people awaiting court-ordered treatment for mental illness or substance abuse are jailed, even though they haven’t been… |
| [Locked Down](https://www.propublica.org/series/locked-down) | 2019–2022 | 8 | Mississippi has one of the highest incarceration rates in the United States, and its prison system has long been plagued by accusations of b… |
| [Unbelievable](https://www.propublica.org/series/an-unbelievable-story-of-rape) | 2015–2019 | 8 | An 18-year-old said she was attacked at knifepoint. Then she said she made it up. That’s where our story begins. |
| [Guns in Dangerous Hands](https://www.propublica.org/series/guns-in-dangerous-hands) | 2023–2025 | 7 | Tennessee has one of the highest rates of women killed by men in the country. Loose gun laws and weak enforcement make it easier for dangero… |
| [Police Accountability in Chicago](https://www.propublica.org/series/chicago-police-accountability) | 2017–2018 | 7 | The Chicago Police Department is among the largest law enforcement agencies in the United States. We have investigated the city’s new police… |
| [Unattended](https://www.propublica.org/series/unattended) | 2024–2026 | 7 | In Idaho, elected coroners face limited oversight, often have little training and typically work on shoestring budgets. They also order auto… |
| [Unchecked Power](https://www.propublica.org/series/unchecked-power) | 2019–2019 | 7 | Alabama sheriffs operate with little oversight, and there are vast county-by-county disparities in how they execute their duties and enforce… |
| [Fields of Green](https://www.propublica.org/series/fields-of-green) | 2024–2024 | 6 | A quadruple murder at an illegal marijuana farm in Kingfisher County, Oklahoma, opened a window into a disturbing reality. Chinese criminal … |
| [Gilded Badges](https://www.propublica.org/series/gilded-badges) | 2020–2021 | 6 | New Jersey police officers and unions have cut deals, to reduce their discipline and increase their benefits, that are costing the public. |
| [Without Knowledge or Consent](https://www.propublica.org/series/without-knowledge-or-consent) | 2024–2025 | 6 | For decades, gun manufacturers gathered sensitive, intimate information from their customers and secretly shared it with political operative… |
| [Words of Conviction](https://www.propublica.org/series/911-call-analysis-forensic-science-investigation) | 2022–2023 | 6 | For more than a decade, a training program known as 911 call analysis and its methods have spread across the country and burrowed deep into … |
| [No Defense](https://www.propublica.org/series/no-defense) | 2023–2024 | 5 | Mississippi is among a handful of states that rely on local officials to fund and deliver almost all public defense for people facing trial.… |
| [Policing in St. Louis](https://www.propublica.org/series/policing-in-st-louis) | 2022–2022 | 5 | St. Louis has one of the nation’s highest violent crime rates, and its police department struggles to keep up. Many neighborhoods hire offic… |
| [Asset Mismanagement](https://www.propublica.org/series/asset-mismanagement) | 2021–2021 | 4 | Under a system called civil asset forfeiture, police and prosecutors can confiscate — and keep — money and property they suspect is part of … |
| [Accusation Dismissed](https://www.propublica.org/series/accusation-dismissed) | 2025–2025 | 3 | Slow investigations and a lax disciplinary system allow Chicago police officers to escape punishment for sexual misconduct. |
| [Schoolyard Sheriffs](https://www.propublica.org/series/schoolyard-sheriffs) | 2021–2022 | 3 | More than five years ago, the Department of Justice found that sheriff’s deputies in the northernmost suburbs of Los Angeles disproportionat… |
| [Unguarded](https://www.propublica.org/series/unguarded) | 2020–2022 | 3 | There are systems meant to safeguard the health and wellbeing of people imprisoned in Illinois. But many of those systems don’t hold staff t… |

### Flagship 6 — Corporate accountability, consumer finance & debt — 18 series, 559 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Foreclosure Crisis](https://www.propublica.org/series/foreclosure-crisis) | 2009–2013 | 161 | Systemic failures at the country's banks and mortgage servicers have exacerbated the most severe foreclosure crisis since the Great Depressi… |
| [The Trade](https://www.propublica.org/series/the-trade) | 2010–2015 | 92 | In this column, co-published with New York Times’ DealBook, Jesse Eisinger monitors the financial markets to hold companies, executives and … |
| [The Wall Street Money Machine](https://www.propublica.org/series/the-wall-street-money-machine) | 2010–2014 | 59 | Enticed by profits and bonuses, Wall Street took advantage of complicated mortgage-based instruments to reap billions, only to exacerbate th… |
| [Driven Into Debt](https://www.propublica.org/series/driven-into-debt) | 2018–2022 | 44 | Parking, traffic camera and vehicle tickets generate millions of dollars in desperately needed cash each year for the City of Chicago. But f… |
| [Tainted Drywall](https://www.propublica.org/series/tainted-drywall) | 2010–2013 | 34 | Foul air from Chinese-made drywall has created a nightmare for thousands of homeowners. |
| [College Debt](https://www.propublica.org/series/college-debt) | 2011–2017 | 29 | Total outstanding college debt is estimated at $1 trillion dollars — and with costs still soaring, the burden on students and their families… |
| [Unforgiven](https://www.propublica.org/series/unforgiven) | 2014–2017 | 29 | The way lenders and collectors pursue consumer debt has undergone an aggressive transformation in America. Collectors today don’t give up ea… |
| [On the Hook](https://www.propublica.org/series/on-the-hook) | 2025–2026 | 20 | Connecticut allows tow truck companies to sell some people’s cars in 15 days, one of the shortest windows in the country. This and other law… |
| [Fed Tapes](https://www.propublica.org/series/fed-tapes) | 2013–2015 | 18 | A confidential report and a fired examiner’s hidden recorder penetrate the cloistered world of Wall Street’s top regulator — and its history… |
| [Debt Inc.](https://www.propublica.org/series/debt-inc) | 2013–2018 | 16 | Payday loans represent only one part of a high-cost lending industry that targets lower income consumers, trapping many in deep debt. When r… |
| [Freddie Mac](https://www.propublica.org/series/freddie-mac) | 2012–2013 | 12 | The taxpayer-owned mortgage giant made investments that profited if borrowers stayed stuck in high-interest loans while making it harder for… |
| [Too Broke for Bankruptcy](https://www.propublica.org/series/too-broke-for-bankruptcy) | 2017–2019 | 12 | (no description on series term) |
| [McKinsey’s Rules](https://www.propublica.org/series/mckinseys-rules) | 2019–2022 | 9 | How McKinsey & Co., best known for advising Fortune 500 corporations, played by its own rules as it expanded into assignments for government… |
| [The Title Pawn Trap](https://www.propublica.org/series/the-title-pawn-trap) | 2022–2023 | 7 | Title lenders offer quick cash to anyone who can use their car as collateral, but in Georgia, lax regulation leaves many borrowers trapped i… |
| [Desperate Loans](https://www.propublica.org/series/desperate-loans) | 2024–2025 | 6 | Online lenders affiliated with Native American tribes are often able to skirt state laws, offering short-term loans for 600% or more. That s… |
| [Smoke and Mirrors](https://www.propublica.org/series/smoke-and-mirrors) | 2026–2026 | 5 | Colorado was the first state to legalize recreational marijuana, and it was once a model for regulation. But it has failed to keep up with o… |
| [Bad Loan](https://www.propublica.org/series/bad-loan) | 2025–2026 | 3 | When Tennessee lawmakers created the Flex Loan, they allowed triple-digit interest. Poor borrowers are struggling to keep up. |
| [The New Debtors Prisons](https://www.propublica.org/series/the-new-debtors-prisons) | 2019–2020 | 3 | State laws that give extensive powers to creditors, combined with aggressive collections efforts, let payday lenders, medical-debt collector… |

### Flagship 7 — Government spending, contracting, disaster & public funds — 15 series, 179 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [The Pandemic Economy](https://www.propublica.org/series/the-pandemic-economy) | 2020–2022 | 45 | Our latest investigations into the efforts to save Americans’ livelihoods in an unprecedented crisis. |
| [The Bad Bet](https://www.propublica.org/series/the-bad-bet) | 2019–2020 | 17 | A decade ago, lawmakers legalized video gambling, saying it would generate billions of dollars for the state. Instead, revenues for the stat… |
| [Fatal Outages](https://www.propublica.org/series/fatal-outages) | 2021–2023 | 14 | Carbon monoxide deaths predictably follow every major weather-related power outage. Experts say these fatalities are preventable. ProPublica… |
| [Tobacco Debt](https://www.propublica.org/series/tobacco-bonds) | 2014–2015 | 14 | A landmark 1998 settlement with Big Tobacco awarded states billions of dollars a year to offset health-care costs of smoking. In many cases,… |
| [After Hurricane Harvey](https://www.propublica.org/series/after-hurricane-harvey) | 2017–2018 | 12 | In 2016, ProPublica and The Texas Tribune sounded the alarm that Houston’s overdevelopment and underestimation of flood risk had made it a s… |
| [Hell and High Water](https://www.propublica.org/series/hell-and-high-water) | 2016–2017 | 12 | Houston is the fourth-largest city in the country. It's home to the nation’s largest refining and petrochemical complex, where billions of g… |
| [G.I. Dough](https://www.propublica.org/series/g-i-dough) | 2015–2017 | 11 | ProPublica is investigating how billions of U.S. tax dollars have been spent on questionable or failed projects and how those responsible fo… |
| [After the Flood](https://www.propublica.org/series/after-the-flood) | 2013–2013 | 10 | More than 8 million Americans live in high-risk flood areas, and the number is expected to climb sharply as the climate changes. In the afte… |
| [The Long Burn](https://www.propublica.org/series/the-long-burn) | 2023–2024 | 9 | The federal government accidentally set the Hermits Peak-Calf Canyon wildfire. Disaster aid has been hard to get and slow to arrive, and res… |
| [Disaster After Disaster](https://www.propublica.org/series/disaster-after-disaster) | 2022–2023 | 8 | The costs of natural disasters are skyrocketing. America’s systems for preparing for them and helping victims are falling short. |
| [Desperation Town](https://www.propublica.org/series/desperation-town) | 2020–2021 | 7 | The Business Journal and ProPublica are investigating how Ohio’s Mahoning Valley has used financial incentives in hopes of an economic comeb… |
| [At a Great Price](https://www.propublica.org/series/at-a-great-price-sears) | 2020–2020 | 6 | The historic $500 million Sears deal with Illinois was one of the United States’ first major tax incentive agreements to relocate a corporat… |
| [California Burning](https://www.propublica.org/series/california-burning) | 2020–2022 | 6 | Yes, California always had wildfires, but no one was prepared for them to get this big, this soon. What do we do now? |
| [Miswired](https://www.propublica.org/series/miswired) | 2019–2020 | 6 | Kentucky is among the worst states in the nation when it comes to high-speed internet use, but its signature plan to catch up is years behin… |
| [No Pressure](https://www.propublica.org/series/no-pressure) | 2023–2024 | 2 | Gurgling faucets. Broken water mains. Boil-water notices. Residents of Jackson, Mississippi, knew for years that the city’s water system was… |

### Flagship 8 — Environment, labor & tech/algorithm accountability — 45 series, 862 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Fracking](https://www.propublica.org/series/fracking) | 2008–2016 | 166 | Vast deposits of natural gas have brought a drilling boom across much of the country, but the technique being used, called hydraulic fractur… |
| [Dragnets](https://www.propublica.org/series/dragnets) | 2012–2016 | 73 | ProPublica investigates the threats to privacy in an era of cellphones, data mining and cyberwar, including how citizens are digitally track… |
| [Machine Bias](https://www.propublica.org/series/machine-bias) | 2015–2022 | 67 | Investigating algorithmic injustice and the formulas that influence our lives. |
| [Gulf Oil Spill](https://www.propublica.org/series/gulf-oil-spill) | 2010–2010 | 57 | The 2010 oil spill in the Gulf of Mexico was the largest in U.S. history. ProPublica's coverage focused on BP’s safety and cost-cutting reco… |
| [Sacrifice Zones](https://www.propublica.org/series/sacrifice-zones) | 2021–2024 | 31 | Polluters are turning neighborhoods into “sacrifice zones” where residents breathe in carcinogens. The EPA allows it. We mapped the hot spot… |
| [Nuclear Safety](https://www.propublica.org/series/nuclear-safety) | 2011–2011 | 25 | We are tracking the nuclear disaster in Japan, and looking at questions about nuclear safety in the U.S. and elsewhere. |
| [Internships](https://www.propublica.org/series/internships) | 2013–2014 | 24 | The number of internships in the United States has ballooned over the past few decades. But oversight and legal protection for unpaid intern… |
| [The New Power Brokers](https://www.propublica.org/series/the-new-power-brokers) | 2018–2022 | 24 | Coal, long West Virginia’s most dominant industry, is ailing. Natural gas is taking over, as a powerful economic and political force. Is the… |
| [Insult to Injury](https://www.propublica.org/series/workers-compensation) | 2015–2016 | 23 | Driven by big business and insurers, states nationwide are dismantling workers’ compensation, slashing benefits to injured workers and makin… |
| [Killing the Colorado](https://www.propublica.org/series/killing-the-colorado) | 2015–2022 | 21 | The Colorado River is dying — the victim of legally sanctioned overuse, the relentless forces of urban growth, willful ignorance among polic… |
| [Temp Land](https://www.propublica.org/series/temp-land) | 2013–2017 | 20 | Temp employment is climbing to record levels following the Great Recession. The system benefits brand-name companies but harms American work… |
| [Trashed](https://www.propublica.org/series/trashed) | 2018–2019 | 20 | Fatal accidents; brutal work conditions; suspicious unions; lax oversight. Every night in New York, trucks from scores of private trash coll… |
| [America’s Dairyland](https://www.propublica.org/series/americas-dairyland) | 2023–2024 | 19 | Dairy farms are some of the most dangerous job sites in America. Much of the labor is done by immigrants working on small farms that operate… |
| [Zero Trust](https://www.propublica.org/series/zero-trust) | 2024–2026 | 18 | Investigating how the world’s largest software provider handles the security of its own ubiquitous products. |
| [Bombs in Our Backyard](https://www.propublica.org/series/bombs-in-our-backyard) | 2017–2018 | 17 | The Pentagon has poisoned millions of acres and left Americans to guess at the threat to their health. Its oversight of thousands of toxic s… |
| [Peligro en las granjas](https://www.propublica.org/series/peligro-en-las-granjas) | 2023–2024 | 17 | Trabajar en las granjas lecheras de los Estados Unidos es peligroso. Frecuentemente, son inmigrantes los que trabajan en ranchos  donde hay … |
| [Polluter’s Paradise](https://www.propublica.org/series/polluters-paradise) | 2019–2021 | 16 | The petrochemical industry has grown in Louisiana, with more plants on the way, but the state’s environmental regulations haven’t kept up. |
| [The Cutting](https://www.propublica.org/series/the-cutting) | 2020–2024 | 16 | The timber industry helped build Oregon, but now, the state has prioritized wealthy corporations over the economy and environment. |
| [Black Snow](https://www.propublica.org/series/black-snow) | 2021–2022 | 14 | Investigating how regulators have allowed the sugar industry to burn crops at the expense of poor communities of color in Florida’s heartlan… |
| [Half-life](https://www.propublica.org/series/half-life) | 2018–2018 | 13 | Thousands of nuclear workers became sick with cancer and other deadly diseases from undisclosed radiation and chemical exposures during the … |
| [On the Line](https://www.propublica.org/series/on-the-line) | 2020–2022 | 13 | ProPublica investigates how big meat companies pushed to keep their plants running even as their workers, and the communities they lived in,… |
| [Age Discrimination](https://www.propublica.org/series/age-discrimination) | 2018–2020 | 12 | For a half century, it has been the law of the land that with few exceptions older workers can't be treated differently than younger ones. B… |
| [Nike’s Gold Standard](https://www.propublica.org/series/nikes-gold-standard) | 2024–2026 | 12 | In 2016, Nike co-founder Phil Knight wrote that the shoe maker had risen above a sweatshop scandal of the 1990s, with one person venturing t… |
| [Paradise Lost](https://www.propublica.org/series/paradise-lost) | 2020–2021 | 12 | Investigating how policymakers are undermining laws and regulations intended to protect the state’s all-important beaches, which are eroding… |
| [The Great Climate Migration](https://www.propublica.org/series/the-great-climate-migration) | 2020–2024 | 12 | Food scarcity and rising temperatures have already begun to reshape how and where people live. ProPublica and The New York Times Magazine, w… |
| [Injection Wells](https://www.propublica.org/series/injection-wells) | 2012–2014 | 11 | Injection wells used to dispose of the nation’s most toxic waste are showing increasing signs of stress as regulatory oversight falls short … |
| [Toxic Burden](https://www.propublica.org/series/toxic-burden) | 2022–2023 | 11 | The United States designed its chemical regulation system to keep businesses humming with little interference. That decision had health repe… |
| [Unplugged](https://www.propublica.org/series/unplugged) | 2022–2026 | 11 | Unplugged oil and gas wells accelerate climate change, threaten public health and risk hitting taxpayers’ wallets. Money set aside to fix th… |
| [The Extortion Economy](https://www.propublica.org/series/ransomware-enablers) | 2019–2021 | 10 | Ransomware has become one of the most common types of cyber-crime, devastating individuals, businesses, and government agencies. Law enforce… |
| [Buried Truth](https://www.propublica.org/series/buried-truth) | 2025–2026 | 8 | Omaha and the Environmental Protection Agency spent decades cleaning up dust from a lead smelter that poisoned residents. But the Flatwater … |
| [Toxic Pressure](https://www.propublica.org/series/toxic-pressure) | 2025–2026 | 8 | Wastewater from Oklahoma oil and gas operations is spreading uncontrollably belowground, blasting out of old wells and contaminating drinkin… |
| [Power Struggle](https://www.propublica.org/series/power-struggle) | 2024–2026 | 7 | Oregon and Washington leaders wanted to eliminate fossil fuels, but the results are dismal so far — in large part because of a federal agenc… |
| [Selling a Mirage](https://www.propublica.org/series/selling-a-mirage) | 2024–2024 | 7 | The world is drowning in plastic. Producers are peddling a “solution” that is more like an illusion. |
| [The New Sweatshop](https://www.propublica.org/series/the-new-sweatshop) | 2020–2024 | 6 | Companies that provide remote customer support services help large corporations shed costs at the expense of workers. |
| [Unreasonable Risk](https://www.propublica.org/series/unreasonable-risk) | 2024–2025 | 6 | Formaldehyde is all around us and causes more cancer than any other chemical in the air. The industry that makes and uses it has repeatedly … |
| [Free Range](https://www.propublica.org/series/free-range) | 2025–2026 | 5 | The federal grazing system, propped up by subsidies and access to 375,000 square miles of the West, disproportionately benefits billionaires… |
| [The Social Machine](https://www.propublica.org/series/the-social-machine) | 2021–2021 | 5 | The social media giant has said it is dedicated to privacy and transparency, but this series of investigations shows the company has repeate… |
| [Extracted](https://www.propublica.org/series/extracted) | 2025–2025 | 4 | Oil companies are holding back a large portion of revenue payments to the people they lease drilling rights from, often with little explanat… |
| [Power Hungry](https://www.propublica.org/series/power-hungry) | 2024–2025 | 4 | Washington leaders embraced energy-guzzling data centers with tax breaks even as the state pushed to phase out fossil fuels. |
| [Waiting on Paychecks](https://www.propublica.org/series/waiting-on-paychecks) | 2023–2024 | 4 | Investigating the prevalence of wage theft in New York and how the state is failing to protect workers. |
| [Carbon Captured](https://www.propublica.org/series/carbon-captured) | 2026–2026 | 3 | For decades, fossil fuel companies have been funding climate research at prestigious colleges, helping to amplify the work of scientists who… |
| [Pollution Profiteers](https://www.propublica.org/series/pollution-profiteers) | 2020–2021 | 3 | California waste businesses are turning a profit while skirting laws meant to protect residents and the environment. |
| [Power Play](https://www.propublica.org/series/power-play) | 2020–2021 | 3 | The Richmond Times-Dispatch and ProPublica are investigating the influence operation of Dominion Energy, the largest public utility in the s… |
| [Sunken Costs](https://www.propublica.org/series/sunken-costs) | 2020–2022 | 3 | How a Southern utility giant passed along the costs of its risky waste disposal practices to Georgians. |
| [Losing Ground](https://www.propublica.org/series/losing-ground) | 2014–2014 | 1 | Scientists say one of the greatest environmental and economic disasters in the nation’s history—the rapid land loss occurring in the Mississ… |

### Flagship 9 — Methodology infrastructure & newsroom meta — 12 series, 390 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Illinois Newsletter](https://www.propublica.org/series/propublica-illinois-newsletters-archive) | 2017–2020 | 125 | Each of our email newsletters are written by a ProPublica Illinois journalist, and we also republish each edition here online. One week, you… |
| [A Closer Look](https://www.propublica.org/series/a-closer-look) | 2013–2025 | 124 | (no description on series term) |
| [ProPublica Reporting Network](https://www.propublica.org/series/reporting-network) | 2010–2010 | 51 | (no description on series term) |
| [Ask ProPublica Illinois](https://www.propublica.org/series/ask-propublica-illinois-journalism-questions) | 2018–2019 | 18 | At ProPublica Illinois, we strive to be transparent about how our journalism gets done. But we can’t predict what you will find useful about… |
| [10 Years of Impact](https://www.propublica.org/series/10-years-of-impact) | 2018–2018 | 15 | Impact has been at the core of ProPublica’s mission since we launched 10 years ago, and it remains the principal yardstick for our success t… |
| [Meet ProPublica Illinois](https://www.propublica.org/series/propublica-illinois-staff-q-and-a) | 2017–2017 | 13 | We’re here and we’re listening. So we’d like to introduce ourselves to communities across Illinois. The ProPublica Illinois team brings expe… |
| [Visual Evidence](https://www.propublica.org/series/visual-evidence) | 2016–2017 | 12 | (no description on series term) |
| [ProPublica Reader Survey](https://www.propublica.org/series/propublica-reader-survey) | 2008–2021 | 10 | Learning about you and how you think we’re doing. |
| [ChangeTracker](https://www.propublica.org/series/changetracker) | 2009–2009 | 7 | (no description on series term) |
| [Paper Trail](https://www.propublica.org/series/paper-trail) | 2026–2026 | 7 | Investigative reporters at ProPublica chase down evidence of wrongdoing and bring it to light. Each episode, you’ll ride along as we talk to… |
| [When Journalism Meets Theater](https://www.propublica.org/series/propublica-illinois-free-street-theater-collaboration) | 2017–2018 | 7 | ProPublica Illinois, Free Street Theater and Illinois Humanities have partnered to develop and host theater workshops in rural and urban com… |
| [Illinois Reporting Project](https://www.propublica.org/series/illinois-reporting-project) | 2018–2018 | 1 | In 2018, we funded reporting projects about issues critical to communities outside the Chicago metropolitan area. |

### Uncovered A — Immigration & the border — 9 series, 197 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Zero Tolerance](https://www.propublica.org/series/zero-tolerance) | 2018–2022 | 79 | The Trump administration’s “zero tolerance” policy called for the prosecution of all people who attempt to enter the country illegally, and … |
| [Inside the Border Patrol](https://www.propublica.org/series/inside-the-border-patrol) | 2019–2020 | 26 | The Border Patrol is the nation’s largest law enforcement agency, with some 20,000 members. But even as its power grows, it has largely evad… |
| [The New Immigration](https://www.propublica.org/series/the-new-immigration) | 2024–2025 | 25 | America is experiencing new types and patterns of immigration. How did we get here? |
| [Trapped In Gangland](https://www.propublica.org/series/ms-13-on-long-island) | 2018–2019 | 16 | President Trump has held out the brutal Central American gang as a national public safety priority and embodiment of the consequences of ill… |
| [Deported and Imprisoned](https://www.propublica.org/series/deported-and-imprisoned) | 2025–2025 | 12 | A case-by-case investigation that examines the Trump administration’s claims that these immigrants are all “sick criminals” and “terrorists”… |
| [The Taking](https://www.propublica.org/series/the-taking) | 2017–2019 | 12 | When the Department of Homeland Security built a border fence a decade ago, it used the federal power of eminent domain to seize hundreds of… |
| [The Travel Ban](https://www.propublica.org/series/immigration) | 2017–2017 | 12 | (no description on series term) |
| [No Sanctuary](https://www.propublica.org/series/no-sanctuary) | 2018–2022 | 10 | The Trump administration has unshackled ICE, making all undocumented immigrants fair game for deportation — even those with no criminal reco… |
| [Billions on the Border](https://www.propublica.org/series/billions-on-the-border) | 2022–2022 | 5 | Together with The Texas Tribune and The Marshall Project, ProPublica investigates border initiatives under Gov. Greg Abbott. State funding f… |

### Uncovered B — Education & schools — 17 series, 192 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [The Quiet Rooms](https://www.propublica.org/series/illinois-school-seclusions-timeouts-restraints) | 2019–2021 | 27 | The spaces have gentle names, like “the reflection room.” But shut inside them, schoolchildren as young as 5 wail for their parents, scream … |
| [Restraints](https://www.propublica.org/series/restraints) | 2014–2019 | 23 | Do you know a child who has been forcibly restrained or secluded at school? Help us investigate by sharing your story. |
| [The Right to Read](https://www.propublica.org/series/the-right-to-read) | 2022–2022 | 21 | One in five American adults struggles to read at a basic level. ProPublica examines the causes and consequences of America’s literacy crisis… |
| [School Wars](https://www.propublica.org/series/school-wars) | 2024–2025 | 16 | Political conflict has shifted how the nation educates kids, leaving them on increasingly different and unequal paths at school. |
| [State of Disrepair](https://www.propublica.org/series/state-of-disrepair) | 2023–2025 | 16 | Idaho spends less, per student, on schools than any other state. Restrictive policies created a funding crisis that’s left rural schools wit… |
| [Crackdown on Student Threats](https://www.propublica.org/series/crackdown-on-student-threats) | 2024–2026 | 13 | Students in Tennessee are being kicked out of school and arrested on felony charges, sometimes because of rumors and misunderstandings. Expe… |
| [Financial Aid Loophole](https://www.propublica.org/series/college-financial-aid-loophole) | 2019–2019 | 9 | Some Illinois parents have been exploiting a legal loophole to win their children need-based college financial aid and scholarships they wou… |
| [Unequal Discipline](https://www.propublica.org/series/unequal-discipline) | 2022–2026 | 9 | Native American students in New Mexico are expelled far more often than members of any other group. One school district, Gallup-McKinley Cou… |
| [The Failure Track](https://www.propublica.org/series/the-failure-track) | 2017–2017 | 8 | Under pressure to meet accountability standards, school districts dump struggling students into alternative schools that are rife with profi… |
| [The Pandemic and Illinois Schools](https://www.propublica.org/series/the-pandemic-and-illinois-schools) | 2020–2020 | 8 | ProPublica’s Midwest newsroom and the Chicago Tribune investigate how the pandemic exposed inequities in the state’s education system and of… |
| [Dollars for Profs](https://www.propublica.org/series/dollars-for-profs) | 2019–2020 | 7 | Professors’ outside income can influence their research topics and findings, policy views and legislative testimony. But these conflicts of … |
| [Evaluating Charter Schools](https://www.propublica.org/series/evaluating-charter-schools) | 2014–2015 | 7 | ProPublica is exploring how this new model of schooling has raised questions about public transparency and private profits. |
| [Campus Complicity](https://www.propublica.org/series/campus-complicity) | 2019–2019 | 6 | Professors and employees at the University of Illinois who face credible accusations of sexual harassment often face minimal consequences. |
| [Frozen Out](https://www.propublica.org/series/frozen-out) | 2025–2026 | 6 | With no tax base, many Alaska school districts rely on the state to repair their schools. But most requests are denied for years as building… |
| [Inside Shrub Oak](https://www.propublica.org/series/inside-shrub-oak) | 2024–2024 | 6 | Shrub Oak International School, a private, for-profit boarding school in New York, promises personalized assistance for autistic students wi… |
| [Chaos at the School Board](https://www.propublica.org/series/chaos-at-the-school-board) | 2023–2023 | 5 | Once considered tame, even boring, school board meetings have become culture-war battlegrounds in recent years. On dozens of occasions, tens… |
| [Unfit to Teach](https://www.propublica.org/series/unfit-to-teach) | 2026–2026 | 5 | Scores of California teachers remain licensed to teach even after schools reported them to the state for misconduct. And with the disciplina… |

### Uncovered C — Children, family services & the social safety net — 11 series, 155 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [State of Denial](https://www.propublica.org/series/state-of-denial) | 2020–2021 | 24 | Arizona’s services for people with intellectual and developmental disabilities are supposed to be the best in the country. But the state is … |
| [Stuck Kids](https://www.propublica.org/series/stuck-kids) | 2018–2020 | 24 | The Illinois Department of Children and Family Services struggles to find appropriate homes for young people with mental illness, often hold… |
| [Level 14](https://www.propublica.org/series/level-14) | 2015–2017 | 20 | How a home for troubled children came undone and what it means for California’s chance at reform. |
| [Culture of Cruelty](https://www.propublica.org/series/culture-of-cruelty) | 2022–2025 | 19 | State-run facilities in Illinois are supposed to care for people with mental and developmental disabilities. But patients have been subjecte… |
| [Profiting From the Poor](https://www.propublica.org/series/profiting-from-the-poor) | 2019–2020 | 16 | An investigation into what keeps poor people poor in a city where wages are low. |
| [“The Unbefriended”](https://www.propublica.org/series/the-unbefriended) | 2024–2026 | 12 | In New York, more than 28,000 adults are under the care of legally appointed guardians. But the system is in shambles, and weak oversight ha… |
| [Overpolicing Parents](https://www.propublica.org/series/overpolicing-parents) | 2022–2025 | 11 | An investigation in partnership with NBC News uncovers the unequal treatment of poor families and parents of color by the child welfare syst… |
| [Welfare States](https://www.propublica.org/series/welfare-states) | 2021–2024 | 11 | Welfare reform allowed states to choose how they provide assistance to the poor — or hardly provide it at all. In the rapidly changing South… |
| [Parental Alienation](https://www.propublica.org/series/parental-alienation) | 2022–2024 | 10 | Psychiatry’s diagnostic bodies have not accepted parental alienation as a mental health disorder. But it’s being leveraged in family courtro… |
| [Nowhere to Go](https://www.propublica.org/series/nowhere-to-go) | 2022–2023 | 5 | New Mexico committed to reforming its child welfare system, but it’s leaving some of its most troubled foster teens without the help they ne… |
| [Division of Families](https://www.propublica.org/series/division-of-families) | 2024–2024 | 3 | While the state’s Division of Family and Children Services provides little housing assistance, “inadequate housing” keeps parents from their… |

### Uncovered D — Housing & homelessness — 10 series, 127 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [The Rent Racket](https://www.propublica.org/series/the-rent-racket) | 2015–2017 | 35 | ProPublica is exploring New York City’s broken rent stabilization system, the tax breaks that underpin it, the regulators who look the other… |
| [HUD’s House of Cards](https://www.propublica.org/series/huds-house-of-cards) | 2018–2022 | 24 | HUD’s flawed oversight of living conditions in federally subsidized housing can leave people living among rats, roaches, mold and other dang… |
| [Rent Barons](https://www.propublica.org/series/rent-barons) | 2022–2025 | 15 | Powerful interests, including a real estate tech company and private equity firms, are contributing to soaring rents. |
| [Checked Out](https://www.propublica.org/series/checked-out) | 2023–2024 | 12 | A 2008 city law was intended to preserve Los Angeles’ residential hotels as safety net housing. But the city has failed to enforce the law, … |
| [The Ugly Truth](https://www.propublica.org/series/the-ugly-truth) | 2023–2025 | 12 | HomeVestors of America claims to be the country’s largest cash homebuyer and says it helps homeowners out of jams. But a closer look reveals… |
| [Invisible Walls](https://www.propublica.org/series/invisible-walls) | 2019–2020 | 10 | Housing segregation is a national trend, but Connecticut is somewhat ahead of the pack. |
| [Swept Away](https://www.propublica.org/series/swept-away) | 2024–2025 | 8 | As homelessness surges to record levels, cities are increasingly removing, or “sweeping,” encampments of people living outdoors. What cities… |
| [Homeowner Hell](https://www.propublica.org/series/homeowner-hell) | 2022–2023 | 6 | Nearly half of Colorado lives in neighborhoods governed by homeowners associations, which have the authority to levy fines and even file for… |
| [Locked Out](https://www.propublica.org/series/locked-out) | 2024–2025 | 4 | Government programs to help renters and low-income homeowners are full of holes, exacerbating the problems they aim to fix. |
| [Coming to Collect](https://www.propublica.org/series/coming-to-collect) | 2020–2020 | 1 | As housing authorities nationwide contend with  dwindling funds, public housing residents pick up the tab. |

### Uncovered E — Military, veterans & national security — 13 series, 248 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Brain Wars](https://www.propublica.org/series/brain-wars) | 2010–2012 | 42 | While military statistics show that more than 115,000 soldiers have suffered mild traumatic brain injuries, unpublished research suggests th… |
| [Disposable Army](https://www.propublica.org/series/disposable-army) | 2008–2013 | 39 | The U.S. war effort in Iraq and Afghanistan has relied heavily on civilian workers, to transport supplies, protect diplomats and other tasks… |
| [Reliving Agent Orange](https://www.propublica.org/series/reliving-agent-orange) | 2009–2019 | 33 | ProPublica and The Virginian-Pilot are exploring the effects of the chemical mixture Agent Orange on Vietnam veterans and their families, as… |
| [Inside Trump’s VA](https://www.propublica.org/series/inside-trump-va) | 2018–2021 | 32 | President Donald Trump made appeals to America’s military veterans central to his campaign. How is his administration delivering on those pr… |
| [Disaster in the Pacific](https://www.propublica.org/series/navy-accidents-pacific-7th-fleet) | 2019–2020 | 26 | Broken ships. Poor training. Ignored warnings. Multiple tragedies. The world’s most powerful armada in decline. |
| [The Drone War](https://www.propublica.org/series/drones) | 2012–2013 | 17 | U.S. counterterror operations have stretched beyond al-Qaida and the war in Afghanistan, with hundreds of drone strikes occurring in Yemen, … |
| [Attacks in Europe](https://www.propublica.org/series/terror-in-europe) | 2015–2016 | 14 | A look at how the region is grappling with terrorism attacks — and how revolving-door prisons could be compounding the threat. |
| [Veterans’ Care at Risk](https://www.propublica.org/series/veterans-care-at-risk) | 2025–2026 | 13 | Upheaval at the Department of Veterans Affairs has meant an exodus of medical personnel and a fraying of the systems in place to help care f… |
| [Failing the Fallen](https://www.propublica.org/series/failing-the-fallen) | 2014–2015 | 9 | Investigating the Pentagon’s failing efforts to timely recover and ID those missing in action from World War II, Korea and Vietnam. |
| [Lost to History](https://www.propublica.org/series/lost-to-history) | 2012–2013 | 8 | Military leaders botched the job of recordkeeping in two of our most-protracted wars, robbing historians of firsthand accounts of the fighti… |
| [Trauma After Tragedy](https://www.propublica.org/series/trauma-after-tragedy) | 2018–2018 | 6 | Whether it’s called shell shock or combat fatigue, there has long been a recognized link between war and the symptoms we now call PTSD, such… |
| [Terror in Little Saigon](https://www.propublica.org/series/terror-in-little-saigon) | 2015–2016 | 5 | Between 1981 and 1990, five Vietnamese-American journalists were killed in what the FBI suspected was a string of political assassinations. … |
| [Veterans Without Assistance](https://www.propublica.org/series/veterans-without-assistance) | 2024–2024 | 4 | What happens when veterans can’t access the psychiatric care they need? |

### Uncovered F — Tribal affairs & Indigenous rights — 6 series, 73 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [The Repatriation Project](https://www.propublica.org/series/the-repatriation-project) | 2023–2025 | 25 | America’s institutions hold human remains and sacred items taken from the graves of tens of thousands of Native Americans. A federal law, th… |
| [Broken Promises](https://www.propublica.org/series/broken-promises) | 2022–2025 | 20 | Before building dams on the Columbia River, the U.S. guaranteed the tribes of the Pacific Northwest salmon forever. But the system it create… |
| [Promised Land](https://www.propublica.org/series/promised-land) | 2020–2023 | 13 | The Honolulu Star-Advertiser and ProPublica are investigating the decadeslong failure of the state Department of Hawaiian Home Lands to retu… |
| [Waiting for Water](https://www.propublica.org/series/waiting-for-water) | 2023–2026 | 6 | The U.S. Supreme Court ruled in 1908 that tribes with reservations have a right to water. But ProPublica and High Country News found that in… |
| [Lessons Lost](https://www.propublica.org/series/lessons-lost) | 2020–2021 | 5 | More than 40,000 Native American students in schools run by the Bureau of Indian Education aren’t getting the education the federal governme… |
| [Power Grab](https://www.propublica.org/series/power-grab) | 2024–2024 | 4 | Washington said it would reduce almost all its greenhouse gasses by 2050. But what happens when the process to get there is at odds with tri… |

### Uncovered G — Democracy, elections & political ethics — 9 series, 274 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Trump, Inc.](https://www.propublica.org/series/trump-inc) | 2018–2023 | 98 | He’s the president, yet we’re still trying to answer basic questions about how his business works: what deals are happening, whom they’re ha… |
| [The Breakdown](https://www.propublica.org/series/the-breakdown) | 2015–2017 | 49 | Our series seeks to show how politics and government really work, and why they don’t. |
| [The Insurrection](https://www.propublica.org/series/the-insurrection) | 2021–2022 | 36 | Reporting on the mob that attacked and breached the Capitol, the fallout from that day, and ongoing far-right violence. |
| [Politic-IL Insider](https://www.propublica.org/series/politic-il-insider-mick-dumke-propublica-illinois-politics) | 2018–2020 | 24 | When it comes to politics, there’s nowhere like Illinois. Throughout the election season, ProPublica Illinois reporter and political junkie … |
| [Redistricting](https://www.propublica.org/series/redistricting) | 2011–2013 | 24 | How secret money and power interests are drawing you out of a vote. |
| [Big Jim](https://www.propublica.org/series/big-jim) | 2019–2023 | 15 | When West Virginia’s richest son ascended to the governor’s mansion, the line between his business empire and the state government blurred. |
| [The Real Bosses of New Jersey](https://www.propublica.org/series/the-real-bosses-of-new-jersey) | 2019–2020 | 13 | They weren’t on the ballot. They may avoid the public eye. But these unelected New Jerseyans are riding on tax breaks and running your gover… |
| [A User’s Guide to Democracy](https://www.propublica.org/series/a-users-guide-to-democracy) | 2022–2022 | 8 | From understanding political ads to seeing what your representatives are actually doing (or not doing), these short guides will help you bec… |
| [Louisiana’s Ethical Swamp](https://www.propublica.org/series/louisianas-ethical-swamp) | 2018–2019 | 7 | A decade ago, Louisiana legislators passed a set of reforms dubbed the “Gold Standard” to rid the state of its reputation for political corr… |

### Uncovered H — Religion & religious power — 3 series, 21 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Sins of Omission](https://www.propublica.org/series/sins-of-omission) | 2020–2020 | 9 | Since 2018, the majority of U.S. dioceses, as well as nearly two dozen religious orders, have released lists of abusers who served within th… |
| [Faith in Power](https://www.propublica.org/series/faith-in-power) | 2024–2024 | 6 | The Christian right has become an increasingly powerful force in American politics. Ahead of the 2024 presidential election, some of its lea… |
| [Forgive and Forget](https://www.propublica.org/series/forgive-and-forget) | 2025–2026 | 6 | Instead of reporting child sexual abuse allegations to police, the Old Apostolic Lutheran Church encouraged victims to forgive their abusers… |

### Uncovered I — International — 5 series, 71 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Firestone and the Warlord](https://www.propublica.org/series/firestone-and-the-warlord) | 2014–2015 | 21 | In the first detailed examination of the relationship between Firestone and Liberian warlord Charles Taylor, this ProPublica/Frontline inves… |
| [Finding Oscar](https://www.propublica.org/series/finding-oscar) | 2012–2017 | 19 | In 1982 amid Guatemala’s civil war, 20 army commandos invaded Dos Erres disguised as rebels. The squad members, or Kaibiles, killed more tha… |
| [The End of Aid](https://www.propublica.org/series/the-end-of-aid) | 2025–2026 | 14 | The U.S. Agency for International Development saved lives and promoted American interests around the globe. As the Trump administration aban… |
| [Shadow Diplomats](https://www.propublica.org/series/shadow-diplomats) | 2022–2023 | 13 | A first-of-its-kind global investigation by ProPublica and the International Consortium of Investigative Journalists identified at least 500… |
| [The Syria Documents](https://www.propublica.org/series/the-syria-documents) | 2012–2012 | 4 | A trove of Syrian government documents show how Bashar al-Assad seeks outside aid. |

### Uncovered J — Nonprofit & charity accountability — 4 series, 58 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Red Cross](https://www.propublica.org/series/red-cross) | 2012–2018 | 40 | (no description on series term) |
| [Unprotected](https://www.propublica.org/series/unprotected) | 2018–2019 | 12 | Katie Meyler established More Than Me to save some of the world’s most vulnerable girls from sexual exploitation. Then, some were raped, and… |
| [Bittersweet](https://www.propublica.org/series/bittersweet) | 2021–2021 | 3 | Hershey profits benefit a boarding school that spends lavishly on its low-income students. The Philadelphia Inquirer, Spotlight PA and ProPu… |
| [St. Jude’s Unspent Billions](https://www.propublica.org/series/st-judes-unspent-billions) | 2021–2022 | 3 | St. Jude Children’s Research Hospital raises more money than any health charity in the country. It promises no family will receive a bill. T… |

### Uncovered K — Transportation safety — 4 series, 47 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Body Scanners](https://www.propublica.org/series/body-scanners) | 2011–2013 | 22 | The Transportation Security Administration plans to install body scanners at nearly every airport security lane in the country by the end of… |
| [Train Country](https://www.propublica.org/series/train-country) | 2023–2026 | 14 | As powerful railroad companies race to maximize profits through efficiency, safety is left behind. |
| [Flight Risk](https://www.propublica.org/series/flight-risk) | 2021–2021 | 6 | Alaska’s terrain and infrastructure pose unique challenges when flying. Some say the Federal Aviation Administration has been slow to accoun… |
| [America’s Dangerous Trucks](https://www.propublica.org/series/americas-dangerous-trucks) | 2023–2023 | 5 | Hundreds of people die every year when cars slide beneath trucks. In the face of opposition from the industry, the federal government has fa… |

### Uncovered L — Civil rights, racial justice & hate — 8 series, 201 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Documenting Hate](https://www.propublica.org/series/documenting-hate) | 2016–2021 | 90 | Hate crimes and bias incidents are a national problem, but there’s no reliable data on the nature or prevalence of the violence. We’re colle… |
| [Segregation Now](https://www.propublica.org/series/segregation-now) | 2012–2015 | 33 | Investigating America’s racial divide in education, housing and beyond. |
| [Sex and Gender](https://www.propublica.org/series/sex-and-gender) | 2013–2016 | 25 | ProPublica's Nina Martin reporting on American systems and institutions that fail or mistreat people on the basis of their gender or sexuali… |
| [Uprooted](https://www.propublica.org/series/uprooted) | 2023–2024 | 14 | In the second half of the 20th century, the establishment and expansion of public universities across Virginia uprooted Black families, hind… |
| [Segregation Academies](https://www.propublica.org/series/segregation-academies) | 2024–2025 | 13 | Hundreds of the private schools that opened for white children fleeing the arrival of Black students still operate across the South. And the… |
| [Dispatches from Freedom Summer](https://www.propublica.org/series/freedom-summer) | 2014–2014 | 10 | In 1964, whites and blacks joined to, as some put it, drag Mississippi back into the United States. Violence erupted. Lives were lost. But c… |
| [Inside Terrorgram](https://www.propublica.org/series/the-rise-and-fall-of-terrorgram) | 2024–2025 | 9 | ProPublica and FRONTLINE investigate how an online network known as Terrorgram spread white supremacy, extremism and violence. |
| [Dispossessed](https://www.propublica.org/series/dispossessed) | 2019–2024 | 7 | Black landowners are disproportionately vulnerable to laws and discriminatory practices that allow speculators and developers to acquire the… |

### Uncovered M — Reproductive rights after Roe — 2 series, 66 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Life of the Mother](https://www.propublica.org/series/life-of-the-mother) | 2024–2026 | 36 | When the Supreme Court overturned Roe v. Wade in 2022, doctors warned that women would die, but lawmakers who passed state abortion bans did… |
| [Post-Roe America](https://www.propublica.org/series/post-roe-america) | 2022–2024 | 30 | After the Supreme Court overturned Roe v. Wade, ending nearly 50 years of federal protection for abortion, some states began enforcing stric… |

### Uncovered N — Other (sports medicine) — 1 series, 12 tagged items

| Series | Years | Items | One-line subject |
|---|---|---|---|
| [Chasing an Edge](https://www.propublica.org/series/chasing-an-edge) | 2014–2017 | 12 | ProPublica is examining doping and unorthodox medicine in the big-money world of professional sports, and why it’s so hard to police. |