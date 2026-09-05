# OCCRP Corpus Census — Empirical Sampling Frame

**Corpus census | 2026-07-29**
**Purpose:** Establish what the Organized Crime and Corruption Reporting Project has actually published from OCCRP's own site structure, rather than from a remembered canon of famous leaks, so later pattern extraction can be audited against the real portfolio.

---

## 1. Method and sources (read this before using any number)

Everything below was pulled on 2026-07-29. The backbone is OCCRP's own English [Projects index](https://www.occrp.org/en/projects/page/1), English [Investigations index](https://www.occrp.org/en/investigations/page/1), and [sitemap index](https://www.occrp.org/sitemap.xml).

| What | OCCRP source and counting method | Nature |
|---|---|---|
| Projects | `/en/projects/page/1` through `/page/9`; 12 cards on pages 1–8 and 9 on page 9 | **105 counted project pages** |
| Project metadata | All 105 project landing pages; landing date and intro; internal story cards; “Partner Stories” outlet/language labels | **Counted**; 1,038 internal-story placements, 965 distinct internal URLs, 390 partner links |
| Investigation/article index | `/en/investigations/page/1` through `/page/149`; 1,785 cards; canonical-URL dedup leaves 1,777 | **Counted in full** |
| Sitemap article corpus | Three article children of `sitemap.xml`: 10,000 + 10,000 + 1,674 URL records | **21,674 counted URL records** across all OCCRP-hosted languages |
| English editorial output | English article-sitemap URLs, excluding the 105 project landing pages | **12,535 counted URL records** |
| Publication years | Full investigation pagination plus binary boundary counts on the chronological News (786 pages), Features (87), Announcements (18), and Scoops (7) listings; boundary pages saved under `raw/year-boundary-pages/` | **12,527 dated listing-card estimate** |
| Network roster | [Our Global Network](https://www.occrp.org/en/about-us/our-global-network): rendered outlet names under region/country headings | **71 listed member-center names + 4 regional partners counted**; page text says “75+” member centers |
| Infrastructure | [OCCRP About](https://www.occrp.org/en/about-us), [Aleph Pro](https://aleph.occrp.org/), [OCCRP ID](https://id.occrp.org/), [Aleph Pro announcement](https://www.occrp.org/en/announcement/occrp-announces-a-new-chapter-for-its-investigative-data-platform-aleph-pro), and [2023 Annual Report](https://www.occrp.org/en/about-us/annual-reports/annual-report-2023/index.html) | Page/document census |
| Awards | [Awards](https://www.occrp.org/en/about-us/awards); each award-result `h3` plus each leaf list item within a year block | **186 counted display records**; conservative because one record can name several prizes |

Machine-readable derivatives are in [raw/projects-index.json](raw/projects-index.json), [raw/project-details.json](raw/project-details.json), [raw/investigations-index.json](raw/investigations-index.json), [raw/sitemap-summary.json](raw/sitemap-summary.json), [raw/publication-year-counts.json](raw/publication-year-counts.json), [raw/classification-summary.json](raw/classification-summary.json), [raw/awards-census.json](raw/awards-census.json), and [raw/network-roster.json](raw/network-roster.json). The raw HTML/XML pulls are alongside them.

### Known limits

- The article sitemap's `lastmod` field is **not a publication date**. Every English URL has a 2024–2026 `lastmod`, reflecting migration/update activity. Publication years therefore come from the dated chronological indexes.
- Section indexes and sitemaps do not reconcile perfectly: listing cards are +1 News, +34 Features, +3 Scoops, and −46 Investigation/Project URLs relative to the sitemaps. The net gap is only eight, but the offsets matter. Use **12,535** for the English URL census and **12,527** for dated output.
- Eight investigation-index URLs repeat; some repeat with conflicting dates. The dedup rule is one canonical URL, retaining the later displayed date. Raw cards remain preserved.
- A story can appear on more than one project page. The 1,038 project-story placements collapse to 965 distinct URLs. Cluster placement totals therefore sum cleanly; per-cluster distinct URL counts can overlap.
- OCCRP project pages label external items as “Partner Stories” but do not consistently identify which outlets were member centers at publication time. Appendix A reproduces the outlet labels without upgrading “partner” to “member.”
- Project page story lists are curated and can omit sitemap-visible URLs. They are the best reproducible project-to-story relation exposed by OCCRP, not a claim that every project article is still linked.
- Cluster and primary-region assignments are **[inferred]** from each project's own title and intro under the explicit rule in §6. Counts after that coding are reproducible from [raw/project-classification.csv](raw/project-classification.csv).

---

## 2. Headline census numbers

- **105 named projects**, dated 2007-08-24 through 2026-05-11 on the Projects index.
- **12,535 English editorial URL records** in the three article sitemaps after excluding 105 project landing pages: 9,428 News, 1,122 project-story subpages, 1,003 Features, 701 standalone Investigations, 207 Announcements, and 74 Scoops.
- **12,527 dated listing cards** across the five English editorial indexes, including three archival cards from 2004. This is the publication-year denominator; the sitemap is eight URLs larger on net.
- **1,785 investigation-index cards / 1,777 unique URLs** from 149 fully paginated pages.
- **1,038 project-story placements / 965 distinct internal URLs** currently exposed by the 105 landing pages.
- **390 external partner-story links** on 23 project pages, representing 184 outlet labels. Of 326 links with a language label, **160 (49.1%)** are labelled something other than plain “English.”
- **21,674 total article-sitemap URL records across languages**: 12,640 English, 8,915 Russian, 99 Spanish, and 20 Ukrainian.
- **186 awards-page result records**, 2012–2026 plus a 21-item “2011 and previously” block.
- **11 bottom-up candidate clusters [inferred]**. The largest by project count is regional state capture (20 projects); the largest by project-story placements is laundromats/banking leaks (261).
- A deliberately explicit “famous laundromat canon” (§6.2) contains **11/105 projects (10.5%)** and **232/965 distinct project-linked story URLs (24.0%)**. It misses **94 projects and 733 distinct project-linked URLs**.

### English output by publication year

Counted from the chronological listing boundaries described in §1; 2026 runs through July 29. These are listing-card counts, not the sitemap `lastmod` years.

| Year | Articles | Year | Articles |
|---|---:|---|---:|
| 2004 | 3 | 2016 | 671 |
| 2005 | 0 | 2017 | 871 |
| 2006 | 0 | 2018 | 939 |
| 2007 | 55 | 2019 | 1,011 |
| 2008 | 180 | 2020 | 999 |
| 2009 | 230 | 2021 | **1,022** |
| 2010 | 312 | 2022 | 952 |
| 2011 | 408 | 2023 | 803 |
| 2012 | 450 | 2024 | 641 |
| 2013 | 497 | 2025 | 836 |
| 2014 | 518 | 2026 (→Jul 29) | 493 |
| 2015 | 636 |  |  |

The dated series rises from a small pre-2011 archive to roughly 800–1,000 items a year in 2017–2023, dips to 641 in 2024, and rebounds to 836 in 2025. This is publishing volume, not “investigations completed”: News alone supplies 9,429 listing cards, while the project/investigation index supplies 1,777 unique URLs.

---

## 3. OCCRP's own site structure

### 3.1 Projects are a curated layer; investigations are the story layer

The Projects index is nine pages and 105 entries. The separate Investigations index is 149 pages and 1,785 cards. It mixes 1,085 `/en/project/<slug>/<story>` cards with 700 `/en/investigation/<slug>` cards; after the site's eight duplicate URLs are removed, 1,777 remain.

Project landing pages expose 1,038 project-to-story placements but only 965 distinct internal URLs. This is a taxonomy relation, not an article count: the same story can support several projects, and some standalone investigations never receive a project home.

### 3.2 Sitemap section census

Counted from `sitemap_articles_1.xml` through `_3.xml`; project roots are separated from project-story URLs.

| English section | Sitemap URLs | Share of 12,535 editorial URLs |
|---|---:|---:|
| News | 9,428 | 75.2% |
| Project stories | 1,122 | 9.0% |
| Features | 1,003 | 8.0% |
| Standalone investigations | 701 | 5.6% |
| Announcements | 207 | 1.7% |
| Scoops | 74 | 0.6% |
| **Total, excluding 105 project roots** | **12,535** | **100%** |

The famous-project layer is therefore a small, heavily curated slice of the publishing system. Even all 1,122 project-subpath URLs are only 9.0% of the English editorial sitemap.

Appendix A reports the sitemap count for every current project slug. Of the 1,122 project-story URLs counted from the article sitemaps, 1,121 map to 101 of the 105 current project slugs. One URL sits under the orphaned `loose-tobacco` slug; A Murderer's Trail, Internet Ownership, Magnitsky Stories, and The Steward Files have no current sitemap project-subpath URL. This is another reason not to equate a landing page with a complete URL container.

### 3.3 Regional structure exists outside the project taxonomy

OCCRP's current [Global Network](https://www.occrp.org/en/about-us/our-global-network) is organized into Africa, Central Asia, Europe, Latin America, Middle East and North Africa, and South Pacific, plus four regional partners. The rendered roster contains 71 member-center outlet names: Europe 44, Africa 13, Latin America 6, Central Asia 3, MENA 3, and South Pacific 2. It separately lists ARIJ, CENOZO, CLIP, and RFE/RL as regional partners.

The page's prose says “75+ local member centers and four regional partners” and “more than 60” additional publishing partners each year. The 71-name rendered count and the 75+ marketing claim do not reconcile; both are preserved rather than silently merged.

---

## 4. Infrastructure corpus: Aleph, ID, and tools

Editorial output and investigative infrastructure are separate sampling frames. Treating Aleph datasets as “articles” would corrupt both.

### 4.1 OCCRP Aleph Pro

OCCRP's [About page](https://www.occrp.org/en/about-us) describes Aleph Pro as holding more than 4 billion documents; its [2025 product announcement](https://www.occrp.org/en/announcement/occrp-announces-a-new-chapter-for-its-investigative-data-platform-aleph-pro) says more than 4.5 billion records and 24,000+ users. The product combines structured records, searchable documents, entity cross-referencing, private investigations, and leaked archives.

The following seven-family taxonomy is **[inferred grouping]**, normalized from the record types and examples named on OCCRP's public-facing Aleph pages:

| Dataset family **[inferred grouping]** | Direct OCCRP description/example |
|---|---|
| Corporate ownership | Company registries, beneficial ownership, directors, shareholders, and corporate-control data |
| Property and movable assets | Land/real-estate records; shipping and other asset registers |
| Public money | Procurement, government expenditure, treasury records, and government-to-private-sector payments |
| Legal and official publications | Court records, official gazettes, and government journals |
| Risk lists | Sanctions, watchlists, and politically exposed person data |
| Open/public information | Official government datasets, open-data repositories, media, and public reports |
| Investigative archives | Leaks, project-specific document corpora, and reporter-contributed collections |

Direct examples counted from the [2023 Annual Report](https://www.occrp.org/en/about-us/annual-reports/annual-report-2023/index.html) are the Greek shipping registry (vessels, owning companies, directors, managers) and Kenya treasury documents. The [ARIJ Aleph Archive announcement](https://www.occrp.org/en/announcement/new-tool-helps-journalists-in-arab-world-follow-the-money) adds government journals, company ownership, and procurement records from 16 MENA jurisdictions.

Access is tiered. OCCRP says public government records/open databases are available broadly and extended material is approved case by case. On 2026-07-29, an anonymous request to `https://aleph.occrp.org/api/2/collections?limit=10` returned HTTP 401 (`raw/aleph-public-collections.*`), so the live collection catalogue could not be counted anonymously. The family census above is therefore direct from OCCRP's descriptions and named examples, not an invented collection count.

**Local-platform note:** this investigation platform already runs a local OpenAleph. OCCRP's announcement identifies OpenAleph as the DARC-maintained open-source fork of legacy Aleph. No duplicate deployment is needed; second-wave extraction should record Aleph dataset/evidence patterns and ingest only appropriately licensed derived material into the existing local service.

### 4.2 OCCRP ID / Investigative Dashboard

[OCCRP ID](https://id.occrp.org/) has two distinct sides:

- A public registry index: **1,000+ sources from 180+ countries**, covering company, land, and court records.
- A network research desk: experts with commercial databases and little-known open sources trace people, companies, ships, planes, and other assets, and assist with acquisition, wrangling, and analysis.

The older “Investigative Dashboard” name joined database search, visualizations, and a human research desk. Coders should record ID as a research-service/tool dependency, not as the publisher of every source record it retrieves.

### 4.3 Adjacent infrastructure

OCCRP also foregrounds Reporters Shield (legal defense against SLAPPs), its internal investigative platform (research, data, visual scenarios, secure sharing, collaboration), and the legacy open-source Aleph/FollowTheMoney ecosystem. These matter to a pattern library because safety, structured collaboration, and source handling are recurring investigative methods even when they do not produce a public article URL.

---

## 5. Awards census (prominence indicator, not the frame)

The [Awards page](https://www.occrp.org/en/about-us/awards) contains **186 counted result display records**. Counting unit: every award-result heading and every leaf list item under a year. A bullet that names two or three awards remains one record, so 186 is a conservative page-entry count, not the number of trophies.

| Year | Listed records | Year | Listed records |
|---|---:|---|---:|
| 2011 and earlier | 21 | 2019 | 2 |
| 2012 | 13 | 2020 | 11 |
| 2013 | 17 | 2021 | 6 |
| 2014 | 16 | 2022 | 7 |
| 2015 | **25** | 2023 | 8 |
| 2016 | 16 | 2024 | 8 |
| 2017 | 7 | 2025 | 15 |
| 2018 | 5 | 2026 | 9 |

The awards page itself demonstrates why awards cannot define the corpus. Recent entries honor Scam Empire, Bad Practice, Dubai Unlocked, NarcoFiles, Story Killers, the Russian Asset Tracker, the Rotenberg Files, and Cyprus Confidential alongside individual journalists and institutional achievements. That mix crosses scams, health regulation, property/asset tracing, narco networks, disinformation, banking leaks, and press freedom.

Awards also mingle attribution levels: OCCRP institution, OCCRP staff, member centers, OCCRP-led projects, and collaborations led by ICIJ or Forbidden Stories. §9 supplies a coder rule that prevents an award mention from turning contribution into project ownership.

---

## 6. Bottom-up project distribution

### 6.1 Explicit classification rule

Each of the 105 project pages receives one primary cluster **[inferred]** based on the central object named in its title and intro:

1. a financial-transfer/bank/offshore leak system;
2. a ruler's wealth or asset network;
3. a criminal group/market/scam operation;
4. a professional or institutional facilitator;
5. an illicit commodity or trafficking corridor;
6. an extractive/energy resource;
7. a surveillance, influence, or media-control system;
8. a country/regional public-power system;
9. direct human/public-service harm;
10. an attack on journalists and continuation response; or
11. an explainer, method, or narrative format.

The rule is mutually exclusive at project level. “Primary region” is separately coded from the project's main locus; genuinely global leaks remain global. Full assignments are in [raw/project-classification.csv](raw/project-classification.csv).

| Candidate cluster **[inferred]** | Projects | % projects | Story placements shown | % of 1,038 placements |
|---|---:|---:|---:|---:|
| Regional desks / state capture | 20 | 19.0% | 180 | 17.3% |
| Laundromats, banking & offshore leaks | 14 | 13.3% | 261 | 25.1% |
| Kleptocracy & asset tracing | 12 | 11.4% | 107 | 10.3% |
| Narco, mafia, scams & criminal communications | 12 | 11.4% | 100 | 9.6% |
| Illicit trade, smuggling & trafficking | 12 | 11.4% | 67 | 6.5% |
| Human rights, public welfare & direct harms | 8 | 7.6% | 91 | 8.8% |
| Enablers, gatekeepers & secrecy services | 7 | 6.7% | 64 | 6.2% |
| Surveillance, influence operations & media capture | 6 | 5.7% | 40 | 3.9% |
| Attacks on journalists / continuation projects | 5 | 4.8% | 48 | 4.6% |
| Methods, explainers & formats | 5 | 4.8% | 44 | 4.2% |
| Extractives, energy & environmental corruption | 4 | 3.8% | 36 | 3.5% |
| **Total** | **105** | **100%** | **1,038** | **100%** |

### 6.2 The “famous laundromat canon” coverage test

To make the comparison reproducible, the canon is **[inferred frame]** but rule-based: all named Laundromat projects plus Panama Papers, Paradise Papers, Pandora Papers, FinCEN Files, Suisse Secrets, OpenLux, and Cyprus Confidential. OCCRP lists the Russian Laundromat and Russian Laundromat Exposed as separate project pages, so both remain.

That yields 11 projects: Azerbaijani, Russian, Russian Exposed, and Troika Laundromats; Panama, Paradise, and Pandora Papers; FinCEN Files; Suisse Secrets; OpenLux; and Cyprus Confidential.

- **Projects covered:** 11/105 = **10.5%**.
- **Distinct project-linked OCCRP story URLs covered:** 232/965 = **24.0%**.
- **Missed:** 94 projects and 733 distinct project-linked URLs = **76.0%** of the named-project story frame.
- Even the broader full laundromats/banking-leaks cluster is only 14/105 projects and 261/1,038 story placements.

The famous canon is output-dense, so it covers one-quarter of project-linked stories while representing only one-tenth of project names. But it would teach the pattern library overwhelmingly about bulk leaks, bank records, shell companies, and cross-border transaction graphs while skipping most other evidence regimes.

### 6.3 Regional-desk weight

Primary-region coding **[inferred]**, counted from the project classification and project-page story URLs:

| Region emphasized in the brief | Projects | Distinct project-linked story URLs |
|---|---:|---:|
| Balkans | 17 | 143 |
| Caucasus | 7 | 91 |
| Central Asia | 8 | 55 |
| Africa | 4 | 20 |
| Latin America & Caribbean | 11 | 65 |
| **Combined** | **47 (44.8%)** | **374 (38.8%)** |

After removing the one famous-canon project in this set (Azerbaijani Laundromat), **46 projects and 360 distinct URLs** remain. A famous-canon frame would therefore skip almost the entire regional-desk layer: procurement, local company registries, land allocation, customs, public banks, political patronage, judicial files, and local-language reporting.

---

## 7. Coverage diff — what a laundromat-first frame misses

### 7.1 Regional state capture and elite networks

The largest project-count cluster is 20 projects / 180 placements. It includes [Uncensored: The Kyrgyzstan Project](https://www.occrp.org/en/project/uncensored-the-kyrgyzstan-project), [The Matraimov Kingdom](https://www.occrp.org/en/project/the-matraimov-kingdom), [The State Capture Papers](https://www.occrp.org/en/project/the-state-capture-papers), [Plunder and Patronage in the Heart of Central Asia](https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia), [Corruptistan: Azerbaijan](https://www.occrp.org/en/project/corruptistan-azerbaijan), and [Unholy Alliances](https://www.occrp.org/en/project/unholy-alliances). The distinctive pattern is not one giant leak; it is repeated local records work that reconstructs a power system over time.

### 7.2 Narco, mafia, scam, and communications systems

Twelve projects / 100 placements, including [NarcoFiles](https://www.occrp.org/en/project/narcofiles-the-new-criminal-order), [Scam Empire](https://www.occrp.org/en/project/scam-empire), [The Crime Messenger](https://www.occrp.org/en/project/the-crime-messenger), [Balkan Cocaine Wars](https://www.occrp.org/en/project/balkan-cocaine-wars), [The 'Ndrangheta](https://www.occrp.org/en/project/the-ndrangheta), and [Fraud Factory](https://www.occrp.org/en/project/fraud-factory). These use encrypted-chat leaks, phone calls, undercover access, logistics, victim tracing, and criminal-case records rather than primarily bank ledgers.

### 7.3 Kleptocracy and asset tracing beyond bank leaks

Twelve projects / 107 placements: [Russian Asset Tracker](https://www.occrp.org/en/project/russian-asset-tracker), [Dubai Unlocked](https://www.occrp.org/en/project/dubai-unlocked), [The Rotenberg Files](https://www.occrp.org/en/project/the-rotenberg-files), [Dubai's Golden Sands](https://www.occrp.org/en/project/dubais-golden-sands), [The Great Gambia Heist](https://www.occrp.org/en/project/the-great-gambia-heist), and [YanukovychLeaks](https://www.occrp.org/en/project/yanukovychleaks-national-project). Property, aircraft, vessels, beneficial ownership, sanctions, and proxies become the evidence spine.

### 7.4 Illicit trade, smuggling, and trafficking corridors

Twelve projects / 67 placements: [China Tobacco Goes Global](https://www.occrp.org/en/project/china-tobacco-goes-global), [Making a Killing](https://www.occrp.org/en/project/making-a-killing), [Tobacco Underground](https://www.occrp.org/en/project/tobacco-underground), [The Cruel Road North](https://www.occrp.org/en/project/the-cruel-road-north), [War Dog Millionaire](https://www.occrp.org/en/project/war-dog-millionaire), and [Veggie Scam](https://www.occrp.org/en/project/veggie-scam). The distinctive evidence is customs/shipping data, commodity flows, weapons inventories, border routes, and supply-chain intermediaries.

### 7.5 Enablers and gatekeepers

Seven projects / 64 placements: [The Worldclear Files](https://www.occrp.org/en/project/the-worldclear-files), [#29LEAKS](https://www.occrp.org/en/project/29leaks-inside-a-london-company-mill), [Biometric Bribery](https://www.occrp.org/en/project/biometric-bribery-inside-semlexs-global-playbook), [Gold for Visas](https://www.occrp.org/en/project/gold-for-visas), [Dominica: Passports of the Caribbean](https://www.occrp.org/en/project/dominica-passports-of-the-caribbean), and [The Proxy Platform](https://www.occrp.org/en/project/the-proxy-platform). This cluster centers the formation agent, auditor, passport vendor, correspondent/payment service, or development bank that makes abuse possible.

### 7.6 Human harms and public-service failures

Eight projects / 91 placements: [Bad Practice](https://www.occrp.org/en/project/bad-practice), [The Steward Files](https://www.occrp.org/en/project/the-steward-files), [Slaves to Progress](https://www.occrp.org/en/project/slaves-to-progress), [Birth and Death in Venezuela's Time of Hunger](https://www.occrp.org/en/project/birth-and-death-in-venezuelas-time-of-hunger), [Crime, Corruption, and Coronavirus](https://www.occrp.org/en/project/crime-corruption-and-coronavirus), and [Battered Justice](https://www.occrp.org/en/project/battered-justice). Medical licensing, hospital ownership, labor records, mortality, public-health procurement, and court protection orders introduce evidence types absent from the financial-leak canon.

### 7.7 Surveillance, influence operations, and media capture

Six projects / 40 placements: [The Pegasus Project](https://www.occrp.org/en/project/the-pegasus-project), [Story Killers](https://www.occrp.org/en/project/story-killers), [Dear Compatriots](https://www.occrp.org/en/project/dear-compatriots), [Spooks and Spin](https://www.occrp.org/en/project/spooks-and-spin-information-war-in-the-balkans), and [Internet Ownership](https://www.occrp.org/en/project/internet-ownership). Device forensics, leaked target lists, propaganda networks, reputation firms, and media-ownership records are distinct investigative systems.

### 7.8 Attacks on journalists and continuation reporting

Five projects / 48 placements: [The Daphne Project](https://www.occrp.org/en/project/the-daphne-project), [A Murdered Journalist's Last Investigation](https://www.occrp.org/en/project/a-murdered-journalists-last-investigation), [Unfinished Lives, Unfinished Justice](https://www.occrp.org/en/project/unfinished-lives-unfinished-justice), [A Journalist's Undying Legacy](https://www.occrp.org/en/project/a-journalists-undying-legacy), and [Death on the Border](https://www.occrp.org/en/project/death-on-the-border). The method is itself distinctive: secure handoff, collaborative continuation, murder-case evidence, and separating support/coordination from editorial ownership.

### 7.9 Extractives, energy, and environmental corruption

Four projects / 36 placements: [The Steinmetz Scandals](https://www.occrp.org/en/project/the-steinmetz-scandals), [Gold and Chaos in Orinoco](https://www.occrp.org/en/project/gold-and-chaos-in-orinoco), [The Battle for Mineral Resources](https://www.occrp.org/en/project/the-battle-for-mineral-resources), and [The Power Brokers](https://www.occrp.org/en/project/the-power-brokers). Concession contracts, mine ownership, energy trading, environmental damage, and local community testimony deserve a separate evidence pattern.

---

## 8. Second-wave extraction recommendations (ranked)

Ranked **[inferred recommendation]** by counted volume × evidentiary distinctiveness. “Volume” is current project-page story placements; “distinctiveness” is whether the cluster introduces source types or workflows the famous financial-leak canon does not.

**R1. Regional state capture and elite networks** — 20 projects, 180 placements, 161 distinct URLs.
Distinct evidence: local corporate and land registries, procurement, customs, public-bank records, municipal decisions, patronage appointments, and local-language reporting accumulated over years. Seeds: [Uncensored Kyrgyzstan](https://www.occrp.org/en/project/uncensored-the-kyrgyzstan-project), [Matraimov Kingdom](https://www.occrp.org/en/project/the-matraimov-kingdom), [State Capture Papers](https://www.occrp.org/en/project/the-state-capture-papers), [Plunder and Patronage](https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia), [Corruptistan: Azerbaijan](https://www.occrp.org/en/project/corruptistan-azerbaijan), [Unholy Alliances](https://www.occrp.org/en/project/unholy-alliances).

**R2. Narco, mafia, scams, and criminal communications** — 12 projects, 100 placements, plus 139 partner-story links.
Distinct evidence: encrypted messaging, intercepted calls, undercover access, payment scripts, logistics chains, victim verification, and transnational criminal-case records. Seeds: [NarcoFiles](https://www.occrp.org/en/project/narcofiles-the-new-criminal-order), [Scam Empire](https://www.occrp.org/en/project/scam-empire), [Crime Messenger](https://www.occrp.org/en/project/the-crime-messenger), [Balkan Cocaine Wars](https://www.occrp.org/en/project/balkan-cocaine-wars), [Fraud Factory](https://www.occrp.org/en/project/fraud-factory).

**R3. Kleptocracy and asset tracing beyond the leak canon** — 12 projects, 107 placements.
Distinct evidence: property cadasters, aircraft/vessel registries, sanctions lists, beneficial ownership, family/proxy relationships, and valuation across jurisdictions. Seeds: [Russian Asset Tracker](https://www.occrp.org/en/project/russian-asset-tracker), [Dubai Unlocked](https://www.occrp.org/en/project/dubai-unlocked), [Rotenberg Files](https://www.occrp.org/en/project/the-rotenberg-files), [Great Gambia Heist](https://www.occrp.org/en/project/the-great-gambia-heist), [Dubai's Golden Sands](https://www.occrp.org/en/project/dubais-golden-sands).

**R4. Illicit trade, smuggling, and trafficking corridors** — 12 projects, 67 placements.
Distinct evidence: customs manifests, shipping routes, commodity classifications, weapons inventories, excise/tax records, border crossings, and supply-chain reconstruction. Seeds: [China Tobacco](https://www.occrp.org/en/project/china-tobacco-goes-global), [Making a Killing](https://www.occrp.org/en/project/making-a-killing), [Tobacco Underground](https://www.occrp.org/en/project/tobacco-underground), [Cruel Road North](https://www.occrp.org/en/project/the-cruel-road-north), [War Dog Millionaire](https://www.occrp.org/en/project/war-dog-millionaire).

**R5. Enablers and gatekeepers** — 7 projects, 64 placements.
Distinct evidence: internal compliance files, customer due-diligence records, formation-agent documents, professional-service correspondence, passport programs, and development-finance governance. Seeds: [Worldclear Files](https://www.occrp.org/en/project/the-worldclear-files), [#29LEAKS](https://www.occrp.org/en/project/29leaks-inside-a-london-company-mill), [Biometric Bribery](https://www.occrp.org/en/project/biometric-bribery-inside-semlexs-global-playbook), [Gold for Visas](https://www.occrp.org/en/project/gold-for-visas), [Proxy Platform](https://www.occrp.org/en/project/the-proxy-platform).

**R6. Human harms and public-service failures** — 8 projects, 91 placements.
Distinct evidence: medical licensing and discipline, hospital ownership, labor exploitation, mortality and public-health data, court protection failures, and victim-centered verification. Seeds: [Bad Practice](https://www.occrp.org/en/project/bad-practice), [Steward Files](https://www.occrp.org/en/project/the-steward-files), [Slaves to Progress](https://www.occrp.org/en/project/slaves-to-progress), [Birth and Death in Venezuela](https://www.occrp.org/en/project/birth-and-death-in-venezuelas-time-of-hunger), [Battered Justice](https://www.occrp.org/en/project/battered-justice).

**R7. Surveillance, influence, and media capture** — 6 projects, 40 placements.
Distinct evidence: device forensics, spyware traces, target lists, influence networks, disinformation contractors, digital advertising, and media ownership. Seeds: [Pegasus](https://www.occrp.org/en/project/the-pegasus-project), [Story Killers](https://www.occrp.org/en/project/story-killers), [Dear Compatriots](https://www.occrp.org/en/project/dear-compatriots), [Spooks and Spin](https://www.occrp.org/en/project/spooks-and-spin-information-war-in-the-balkans), [Internet Ownership](https://www.occrp.org/en/project/internet-ownership).

**R8. Attacks on journalists and continuation reporting** — 5 projects, 48 placements.
Distinct evidence: secure document transfer, collaborative continuation protocols, murder dockets, telecom/travel evidence, source protection, and explicit coordination roles. Seeds: [Daphne Project](https://www.occrp.org/en/project/the-daphne-project), [Murdered Journalist's Last Investigation](https://www.occrp.org/en/project/a-murdered-journalists-last-investigation), [Unfinished Lives](https://www.occrp.org/en/project/unfinished-lives-unfinished-justice), [Undying Legacy](https://www.occrp.org/en/project/a-journalists-undying-legacy), [Death on the Border](https://www.occrp.org/en/project/death-on-the-border).

Honorable mention: extractives/energy is smaller (4 projects, 36 placements) but evidentially distinctive enough to ride with R4; methods/explainers should be harvested as cross-cutting annotations rather than a standalone subject wave.

---

## 9. Sampling-frame biases and coder rules

### 9.1 Consortium/member-center attribution

OCCRP is a network and coordination platform, not a single conventional newsroom. The current site lists 71 rendered member-center names, four regional partners, and says it works with 60+ other publishing partners annually. A project can be OCCRP-hosted while externally coordinated; an OCCRP researcher can contribute without OCCRP owning the project; a member center can publish the originating local story while OCCRP publishes an English adaptation.

**Proposed coder rule:**

1. Record separate fields for `project_coordinator`, `publication_host`, `originating_outlet`, `contributor_outlets`, `source_archive_owner`, and `OCCRP_role`.
2. Project-level ownership follows explicit verbs in the landing-page credits: “led,” “coordinated,” or “organized.” Hosting at `occrp.org` is not leadership.
3. Article-level ownership follows the canonical originating URL and byline. An OCCRP-hosted story is an OCCRP publication; an external “Partner Story” remains the partner's publication.
4. “OCCRP facilitated,” “research by OCCRP ID,” editing, data support, or member-center participation are contributor roles, not automatic project ownership.
5. If leadership is not stated, use `coordinator_unknown`; assigning OCCRP by default would be **[inferred]** and must be marked.
6. Current membership status is not backdated. Preserve the outlet label shown on the project page and separately record whether it appears on the 2026 network roster.

### 9.2 English-index bias

Two direct measures show the problem:

- OCCRP's article sitemaps contain **9,034 non-English URL records (41.7% of 21,674)**: 8,915 Russian, 99 Spanish, 20 Ukrainian. English is 58.3%. These can include translations or parallel editions, so 41.7% is URL-language exclusion, not 41.7% unique stories.
- Project pages expose 390 external partner links. Of 326 with language labels, **160 (49.1%)** are labelled something other than plain “English.” This is a curated partner-link sample, not the full network.

The larger blind spot cannot be quantified from `occrp.org`: 71 listed member centers publish on their own domains, often in local languages, and OCCRP says it works with 60+ additional partners yearly. Their output is outside OCCRP's sitemaps. Any corpus based only on `/en/` is therefore an English-facing coordination/publication census, not an OCCRP-network production census.

### 9.3 Project versus article unit

A project is an editorial container; an article is a publication event. The 105 project pages generate 1,038 story placements but 965 distinct URLs; project paths in the sitemap contain 1,122 story subpages; the investigation listing contains 1,777 distinct URLs; the full English editorial sitemap contains 12,535 URLs.

**Rule:** use the project as the sampling/stratification unit and the canonical article URL as the extraction unit. Multi-project articles get one article record plus many project relations. Do not sum project-page counts as unique output without URL deduplication.

### 9.4 ICIJ / Forbidden Stories mega-project deduplication

The OCCRP landing pages make several leadership cases explicit:

- [Pandora Papers](https://www.occrp.org/en/project/the-pandora-papers): coordinated by ICIJ; 70+ OCCRP-network journalists participated.
- [Cyprus Confidential](https://www.occrp.org/en/project/cyprus-confidential): led by ICIJ and Paper Trail Media; OCCRP supplied reporting and at least one source tranche.
- [Pegasus Project](https://www.occrp.org/en/project/the-pegasus-project): coordinated by Forbidden Stories; Amnesty International's Security Lab supplied technical support.
- [Daphne Project](https://www.occrp.org/en/project/the-daphne-project): coordinated and led by Forbidden Stories; OCCRP facilitated document sharing and assigned researchers/reporters.

**Cross-census dedup rule:**

1. Create one canonical project ID under the named coordinator (`icij:pandora-papers`, `icij+paper-trail:cyprus-confidential`, `forbidden-stories:pegasus-project`, etc.).
2. In the OCCRP census, retain the OCCRP project page and OCCRP-hosted articles as contribution/publication edges to that canonical project; do not create a second independent project in comparative project counts.
3. Deduplicate syndicated or substantially identical articles by canonical origin URL, normalized title/date/byline, and—where available—content hash. Keep outlet-specific adaptations as separate publications linked to one story family.
4. Deduplicate evidence separately: the same leaked document, registry extract, or source archive is one evidence object even when ICIJ, OCCRP, and a member center all cite it.
5. If two organizations are explicitly joint leads, use a single joint namespace. Do not choose a winner merely to simplify the table.

This rule prevents the ICIJ census and OCCRP census from double-counting Panama/Pandora/Cyprus-style projects while preserving OCCRP's real reporting, research, and publication contribution.

### 9.5 Additional structural biases

1. **Migration/index bias:** sitemap `lastmod` dates are unusable for publication chronology, and section indexes contain duplicates/stale cards. Counts must preserve both sitemap and index denominators.
2. **Project-curation bias:** only 9.0% of English editorial sitemap URLs sit under project-story paths. Project-only extraction omits the large News/Feature layer.
3. **Partner-showcase bias:** the 390 partner links are selected examples on 23 pages, not a census of every co-publication.
4. **Award-canon bias:** 186 awards records over-represent work that fits prize categories and mix institutional, individual, member-center, and collaborative credit.
5. **Regional coding bias [inferred]:** one primary region simplifies cross-border work. Multi-region tags should be added during extraction; the primary-region numbers here are a reproducible lower-dimensional sampling aid.

---

## Appendix A — Full 105-project backbone

Date span is the first–last dated internal OCCRP story currently shown on the project page; if a page shows none, the landing date is used. “Landing stories” means internal story placements displayed on that landing page. “Sitemap URLs” means English `/en/project/<slug>/<story>` records in the three article sitemaps and excludes the project root. “Partner/member-center labels shown” reproduces OCCRP's Partner Stories outlet labels and does **not** assert current or historical member-center status. Cluster and primary region are **[inferred]** under §6.

### A.1 Regional desks / state capture — 20 projects, 180 landing-story placements, 178 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [Know Your Host: Why It Matters That Azerbaijan Is Hosting the COP29 Climate Summit](https://www.occrp.org/en/project/know-your-host)<br><code>know-your-host</code> | 2015–2024 | Caucasus | 34 | 4 | This year’s ‘COP29’ — the world’s premier climate change conference — is about to begin in Azerbaijan. | — |
| [Uncensored: The Kyrgyzstan Project](https://www.occrp.org/en/project/uncensored-the-kyrgyzstan-project)<br><code>uncensored-the-kyrgyzstan-project</code> | 2022–2025 | Central Asia | 5 | 3 | Kyrgyzstan was once the most democratic of Central Asia’s former Soviet republics, with genuine elections, a vigorous civil society, and a vibrant media scene. | — |
| [The Shadow Investor](https://www.occrp.org/en/project/the-shadow-investor)<br><code>the-shadow-investor</code> | 2023 | Central Asia | 6 | 7 | For years, one man colluded with corrupt customs officials to dominate the vast flow of Chinese imports — everything from t-shirts to high-end electronics — that sustain Central Asia. | — |
| [The Matraimov Kingdom](https://www.occrp.org/en/project/the-matraimov-kingdom)<br><code>the-matraimov-kingdom</code> | 2019–2021 | Central Asia | 18 | 13 | At a recent performance on Kyrgyzstan’s independence day, an improvisational poet known as an akyn memorably called out the country’s endemic corruption in front of its president, top officials, and foreign guests. | — |
| [Revolution to Riches](https://www.occrp.org/en/project/revolution-to-riches)<br><code>revolution-to-riches</code> | 2020 | Latin America/Caribbean | 5 | 38 | Venezuela’s National Bolivarian Armed Forces have been described as “ impenetrable ,” with very little about the country's military publicly known — other than that it clearly plays a large role in the survival of the embattled regime of Nicolás... | — |
| [The State Capture Papers](https://www.occrp.org/en/project/the-state-capture-papers)<br><code>the-state-capture-papers</code> | 2017–2020 | Africa | 7 | 1 | In a South African corruption scandal so grand it became known as “ state capture ,” former President Jacob Zuma is alleged to have colluded with members of the wealthy and influential Gupta family to embezzle billions of dollars of public funds, while massively... | — |
| [Plunder and Patronage in the Heart of Central Asia](https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia)<br><code>plunder-and-patronage-in-the-heart-of-central-asia</code> | 2019–2020 | Central Asia | 10 | 10 | “I’m Aierken Saimaiti,” the man said. “Between 2011 and 2016, I transferred more than $700 million out of Kyrgyzstan.” | — |
| [Public Land, Private Hands](https://www.occrp.org/en/project/public-land-private-hands)<br><code>public-land-private-hands</code> | 2019 | Central Asia | 4 | 7 | Between 2000 and 2008, authorities in Kyrgyzstan divided up a large swath of Ataturk Park, a beloved green space in the country’s capital, Bishkek, and handed it out to 173 people — many of them wealthy and well-connected. | — |
| [Tajikistan: Money by Marriage](https://www.occrp.org/en/project/tajikistan-money-by-marriage)<br><code>tajikistan-money-by-marriage</code> | 2018–2019 | Central Asia | 7 | 15 | Since marrying one of the seven daughters of the president of Tajikistan, a young businessman has built an empire that stretches across the country. An OCCRP investigation show how unlimited political power leads to business success in one of Central Asia's poorest countries. | — |
| [Agents of Influence](https://www.occrp.org/en/project/agents-of-influence)<br><code>agents-of-influence</code> | 2017 | Balkans | 2 | 2 | Bombardier is a Canadian transportation conglomerate that controls Bombardier Transportation, a Swedish engineering firm and one of the world’s largest producers of railway signaling equipment. Bombardier technology makes the trains run from Eurasia to Latin America, and its globe-spanning business shows no signs of slowing down. | — |
| [Mayor's Story](https://www.occrp.org/en/project/mayors-story)<br><code>mayors-story</code> | 2015 | Balkans | 3 | 3 | Siniša Mali, the powerful mayor of the Serbian capital of Belgrade and a close associate and former advisor of current Serbian Prime Minister Aleksandar Vučić, prides himself on being a modern, progressive leader. | — |
| [Corruptistan: Uzbekistan](https://www.occrp.org/en/project/corruptistan-uzbekistan)<br><code>corruptistan-uzbekistan</code> | 2015–2020 | Central Asia | 10 | 10 | Under President Islam Karimov, in power since 1989, Uzbekistan has boasted of steady economic growth based on exports like cotton, gas and gold. But the political system is highly authoritarian, and its human rights record widely decried. | — |
| [Corruptistan: Tajikistan](https://www.occrp.org/en/project/corruptistan-tajikistan)<br><code>corruptistan-tajikistan</code> | 2018 | Central Asia | 1 | 1 | No one-line intro displayed. | — |
| [Corruptistan: Azerbaijan](https://www.occrp.org/en/project/corruptistan-azerbaijan)<br><code>corruptistan-azerbaijan</code> | 2015–2016 | Caucasus | 28 | 24 | Oil-rich Azerbaijan has redefined itself over the past two decades from a struggling newly independent state to a major regional energy player. It has also used its resources to rebuild its army, which is seen as a government priority as the country grapples with the breakaway territory of Nagorno-Karabakh. | — |
| [Unholy Alliances](https://www.occrp.org/en/project/unholy-alliances)<br><code>unholy-alliances</code> | 2014 | Balkans | 6 | 6 | How Organized Crime, Government and Business Interact in Montenegro. | — |
| [Georgia: Sex, Files and Videotape](https://www.occrp.org/en/project/georgia-sex-files-and-videotape)<br><code>georgia-sex-files-and-videotape</code> | 2013 | Caucasus | 5 | 5 | The " Georgia: Sex, Files and Videotape " stories were reported by Elza Ketsbaia and Nini Japaridze and edited by Jody McPhillips and David Bloss. Photographs shot by Ketsbaia, and McPhillips. | — |
| [The Mišković Millions](https://www.occrp.org/en/project/the-miskovic-millions)<br><code>the-miskovic-millions</code> | 2010–2011 | Balkans | 6 | 6 | The investigation of " Mišković's Millions " was a joint project of the Center of Investigative Reporting Serbia and the Organized Crime and Corruption Reporting Project. The stories were researched, reported and written by Stevan Dojčinović, Vladimir Kostić, Anđela Milivojević, Dragana Pećo and Bojana Jovanović in Belgrade. Azhar... | — |
| [Security Chaos](https://www.occrp.org/en/project/security-chaos)<br><code>security-chaos</code> | 2010 | Balkans | 10 | 10 | No place needs security more than in the Balkans! | — |
| [Man In The Middle](https://www.occrp.org/en/project/man-in-the-middle)<br><code>man-in-the-middle</code> | 2010 | Balkans | 5 | 5 | No one-line intro displayed. | — |
| [The Big Bet](https://www.occrp.org/en/project/the-big-bet)<br><code>the-big-bet</code> | 2009 | Balkans | 8 | 8 | No one-line intro displayed. | — |

### A.2 Laundromats, banking, and offshore leaks — 14 projects, 261 landing-story placements, 394 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [Cyprus Confidential](https://www.occrp.org/en/project/cyprus-confidential)<br><code>cyprus-confidential</code> | 2019–2025 | EU/Western Europe | 18 | 7 | Poet Leonidas Malenis likened his native Cyprus to a “golden-green leaf thrown in the sea,” but in recent years the east Mediterranean island nation has earned a darker reputation. | — |
| [Suisse Secrets](https://www.occrp.org/en/project/suisse-secrets)<br><code>suisse-secrets</code> | 2022–2023 | Global | 32 | 35 | Swiss banks have been synonymous with secrecy for decades, conjuring up visions of vast riches safely held in mountain vaults. It's a strong brand — one Switzerland's government does everything it can to protect. | — |
| [The Pandora Papers](https://www.occrp.org/en/project/the-pandora-papers)<br><code>the-pandora-papers</code> | 2021–2024 | Global | 29 | 32 | An 11-year-old boy from Azerbaijan who owned nearly $49 million of prime commercial real estate in London. A Czech prime minister who loaned himself 15 million euros to buy a French chateau. The unofficial wife of a Kazakh president who received a mysterious $30 million payment. A Serbian politician who swore he didn’t own 24 seaside apartments, but really did. | BBC; El Espectador; El Pais; Finance Uncovered; ICIJ; International Consortium of Investigative Journalists (ICIJ); Le Monde; The Guardian; Washington Post |
| [OpenLux](https://www.occrp.org/en/project/openlux)<br><code>openlux</code> | 2021–2022 | EU/Western Europe | 13 | 14 | Luxembourg is a tiny country — officially a Grand Duchy — that sits on barely more than 2,500 square kilometers of land wedged between Germany, France, and Belgium. | Bivol; IStories; Investigace.cz; IrpiMedia; Le Monde; Le Soir; Miami Herald; Süddeutsche Zeitung; Transparency International; Woxx |
| [The FinCEN Files](https://www.occrp.org/en/project/the-fincen-files)<br><code>the-fincen-files</code> | 2020 | Global | 20 | 20 | Money makes the world go round. | — |
| [The Austrian Bank Job](https://www.occrp.org/en/project/the-austrian-bank-job)<br><code>the-austrian-bank-job</code> | 2019 | EU/Western Europe | 2 | 2 | When it came to stripping assets from their financial institutions, Eastern European bankers found the infrastructure they needed in a century-old Austrian bank. | — |
| [The Troika Laundromat](https://www.occrp.org/en/project/the-troika-laundromat)<br><code>the-troika-laundromat</code> | 2019–2022 | Russia/Eastern Europe | 17 | 40 | Laundromats are complex systems for moving money that allow corrupt politicians, organized crime figures, and wealthy business people to secretly invest their ill-gotten millions, launder money, evade taxes, and fulfill other goals. | Armenia: Hetq; Austria: Profil; Belgium: Knack; Bulgaria: Bivol; Canada: The Globe and Mail; Denmark: Berlingske; Finland: Yle; Germany: Suddeutsche Zeitung; Lithuania: 15min.lt; Russia: Meduza; Spain: El Periodico; Switzerland: Tages Anzeiger; Switzerland: Tages-Anzeiger; The Netherlands: Groene; The Netherlands: Investico; The Netherlands: Trouw; UK: BBC; UK: The Guardian; US: Barron’s |
| [Paradise Papers](https://www.occrp.org/en/project/paradise-papers)<br><code>paradise-papers</code> | 2017–2018 | Global | 21 | 42 | The Paradise Papers is a major new leak of documents from two offshore services firms based in Bermuda and Singapore, as well as from 19 corporate registries maintained by governments in secret offshore jurisdictions. The documents were obtained by the Süddeutsche Zeitung and shared with the International Consortium of Investigative Journalists (ICIJ), which... | — |
| [The Azerbaijani Laundromat](https://www.occrp.org/en/project/the-azerbaijani-laundromat)<br><code>the-azerbaijani-laundromat</code> | 2017–2022 | Caucasus | 19 | 62 | The Azerbaijani Laundromat is a complex money-laundering operation and slush fund that handled $2.9 billion over a two-year period through four shell companies registered in the UK. | — |
| [The Moldovan Banking Wars](https://www.occrp.org/en/project/the-moldovan-banking-wars)<br><code>the-moldovan-banking-wars</code> | 2016 | Russia/Eastern Europe | 3 | 3 | Moldovan banks are in a life-and-death struggle. Many have been involved in money laundering and asset thefts that have moved tens of billions of dollars from Russia to the West. Then when $1 billion disappeared from three Moldovan banks last year, the theft raised more questions than it answered and dealt a brutal blow to the economy. | — |
| [The Panama Papers](https://www.occrp.org/en/project/the-panama-papers)<br><code>the-panama-papers</code> | 2016–2020 | Global | 46 | 66 | No one-line intro displayed. | — |
| [The Russian Laundromat](https://www.occrp.org/en/project/the-russian-laundromat)<br><code>the-russian-laundromat</code> | 2014–2015 | Russia/Eastern Europe | 9 | 6 | Call it the Laundromat. It’s a complex system for laundering more than $20 billion in Russian money stolen from the government by corrupt politicians or earned through organized crime activity. It was designed to not only move money from Russian shell companies into EU banks through Latvia, it had the added feature of getting corrupt or uncaring judges in Moldova to... | — |
| [The Russian Laundromat Exposed](https://www.occrp.org/en/project/the-russian-laundromat-exposed)<br><code>the-russian-laundromat-exposed</code> | 2014–2017 | Russia/Eastern Europe | 19 | 52 | Three years ago, OCCRP exposed the “Russian Laundromat” - an immense financial fraud scheme that enabled vast sums to be pumped out of Russia. The money was laundered and moved into Europe and beyond through bribery and a clever exploitation of the Moldovan legal system. | 15min; Barron's; Beobachter; Berlingske Business; Czech Center for Investigative Journalism; De Correspondent; Delo; Dossier; Korea Center for Investigative Journalism; Newsweek; Novaya Gazeta; Postimees; Rise Moldova; Süddeutsche Zeitung; The Guardian; Vice; YLE |
| [Offshore Crime, Inc](https://www.occrp.org/en/project/offshore-crime-inc)<br><code>offshore-crime-inc</code> | 2010–2011 | Global | 13 | 13 | No one-line intro displayed. | — |

### A.3 Kleptocracy and asset tracing — 12 projects, 107 landing-story placements, 101 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [Podcast: White Collars, Dirty Hands](https://www.occrp.org/en/project/white-collars-dirty-hands)<br><code>white-collars-dirty-hands</code> | 2026 | Latin America/Caribbean | 6 | 6 | Ever since it was pumped by commercial rigs from beneath the shores of Lake Maracaibo over a century ago, oil has been both a blessing and a curse for Venezuela. It has fueled boom times and bust times. It gave rise to an urban middle class — and then an echelon of elites who plundered the nation’s oil wealth, amassing billions as the rest of the country collapsed... | — |
| [Dubai Unlocked](https://www.occrp.org/en/project/dubai-unlocked)<br><code>dubai-unlocked</code> | 2018–2025 | Middle East | 13 | 6 | From its humble days as desert tradepost to its current status as a global financial hub, Dubai has long served as a crossroads for commerce. | — |
| [The Rotenberg Files](https://www.occrp.org/en/project/the-rotenberg-files)<br><code>the-rotenberg-files</code> | 2023 | Russia/Eastern Europe | 7 | 7 | Vladimir Putin has spent his presidency crushing dissent, jailing journalists and opposition leaders, and waging a relentless war against Ukraine. | — |
| [Russian Asset Tracker](https://www.occrp.org/en/project/russian-asset-tracker)<br><code>russian-asset-tracker</code> | 2022–2024 | Russia/Eastern Europe | 15 | 14 | Introducing a project to track down and catalogue the vast wealth held outside Russia by oligarchs and key figures close to Russian President Vladimir Putin. | — |
| [The Great Gambia Heist](https://www.occrp.org/en/project/the-great-gambia-heist)<br><code>the-great-gambia-heist</code> | 2019 | Africa | 5 | 6 | For more than two decades, Yahya Jammeh ruled over Gambia, a tiny West African country known for tropical beaches and tranquility in a region often rocked by conflict. | — |
| [The Chávez Man and His Millions](https://www.occrp.org/en/project/the-chavez-man-and-his-millions)<br><code>the-chavez-man-and-his-millions</code> | 2019 | Latin America/Caribbean | 3 | 3 | Venezuela's economy is in ruins, but there are still fortunes to be made. One of these — estimated to be worth $100 million — is that of a man named Carlos Luis Aguilera Borjas. And he's not just a businessman. For years Aguilera served the country's revolutionary leader, Hugo Chávez, as a bodyguard, later rising to lead its security agency. How did he... | — |
| [Paradise Leased: The Theft of the Maldives](https://www.occrp.org/en/project/paradise-leased-the-theft-of-the-maldives)<br><code>paradise-leased-the-theft-of-the-maldives</code> | 2018 | South Asia | 4 | 4 | Maldives tourism isn’t all swaying palm trees and white sand beaches. The truth is something far uglier. | — |
| [Dubai’s Golden Sands](https://www.occrp.org/en/project/dubais-golden-sands)<br><code>dubais-golden-sands</code> | 2018–2019 | Middle East | 19 | 24 | Dubai has transformed itself into an extravagant metropolis where the police drive Lamborghinis and edible gold ice cream costs US $800 a scoop. | — |
| [Putin and the Proxies](https://www.occrp.org/en/project/putin-and-the-proxies)<br><code>putin-and-the-proxies</code> | 2017 | Russia/Eastern Europe | 2 | 2 | A Novaya Gazeta and OCCRP investigation looks into the wealth surrounding Russian President Vladimir Putin. | — |
| [YanukovychLeaks National Project](https://www.occrp.org/en/project/yanukovychleaks-national-project)<br><code>yanukovychleaks-national-project</code> | 2014 | Russia/Eastern Europe | 14 | 16 | A group investigating the documents found in Mezhihirya. | — |
| [Magnitsky Stories](https://www.occrp.org/en/project/magnitsky-stories)<br><code>magnitsky-stories</code> | 2011–2013 | Russia/Eastern Europe | 4 | 0 | OCCRP has reported extensively on the Magnitsky story. Here are our stories on this important topic. | — |
| [First Bank - First Family](https://www.occrp.org/en/project/first-bank-first-family)<br><code>first-bank-first-family</code> | 2012 | Caucasus | 15 | 13 | The project is a joint effort of the OCCRP and BBC’s Newsnight. Over the next two weeks we will publish more than a dozen stories on this topic. | — |

### A.4 Narco, mafia, scams, and criminal communications — 12 projects, 100 landing-story placements, 113 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [Scam Empire](https://www.occrp.org/en/project/scam-empire)<br><code>scam-empire</code> | 2025 | Asia-Pacific | 9 | 8 | Scam call centers have been a scourge for years, conning ordinary people around the world out of hundreds of billions of dollars. | AmaBhungane Centre for Investigative Journalism; Amphora Media; Berlingske; Bird; CBC/Radio-Canada; CIReN; De Tijd; Der Spiegel; Follow the Money; IRPIMedia; Investico; Le Monde; Reporter.lu; SVT; Siena.lt; The Guardian; YLE; infoLibre |
| [The Crime Messenger: How Sky ECC Phones Became a Tool of the Criminal Trade](https://www.occrp.org/en/project/the-crime-messenger)<br><code>the-crime-messenger</code> | 2024–2026 | Global | 3 | 5 | What do criminals say to each other when they think nobody can hear? | Der Standard; Investigace.cz; KRIK; NRC; Télérama |
| [NarcoFiles: The New Criminal Order](https://www.occrp.org/en/project/narcofiles-the-new-criminal-order)<br><code>narcofiles-the-new-criminal-order</code> | 2023–2024 | Latin America/Caribbean | 10 | 11 | Drug trafficking is a globe-spanning business. Cocaine might start life at a plantation in Colombia before being repackaged in Mexico, processed in the Netherlands, and sold on to users as far away as Bulgaria. Markets are booming in Asia, Africa, and Australia, generating billions in illicit revenues that flow back across the world through bank wires, cash... | Agencia Ocote; Aristegui Noticias; Armando.info; BIRD; Berlingske; CLIP; CNN en Español; Cerosetenta / 070; Clip; Con Criterio; Contracorriente; Cuestión Pública; De Tijd; Der Standard; Die Dunkelkammer; El Nuevo Herald; El Universal; Expresso; FrontStory.PL; InSight Crime; InfoLibre; Investigace.cz; IrpiMedia; Irpimedia; Knack; La Prensa; Mexicanos Contra la Corrupción y la Impunidad (MCCI); Miami Herald; Mongabay Latam; Narcodiario; NoFicción; Noticias Caracol; Ojo Público; OjoPúblico; Ojoconmipisto; Plan V; Plaza Pública; Profil; Quinto Elemento Lab; SVT; UOL; Univisión; Verdad Abierta; Voragine; Vorágine; piauí |
| [The 'Ndrangheta](https://www.occrp.org/en/project/the-ndrangheta)<br><code>the-ndrangheta</code> | 2017–2024 | EU/Western Europe | 18 | 4 | The 'Ndrangheta might not be as well known as the Sicilian Mafia, but with an estimated annual turnover of US$60 billion, it's one of the world’s most powerful criminal organizations. | — |
| [GROUP AMERICA: A US-Serbian Drug Gang With Friends In The Shadows](https://www.occrp.org/en/project/group-america-a-us-serbian-drug-gang-with-friends-in-the-shadows)<br><code>group-america-a-us-serbian-drug-gang-with-friends-in-the-shadows</code> | 2020–2021 | Balkans | 8 | 8 | They’ve been accused of dismembering enemies with chainsaws, assassinating senior government officials and trading on ties with intelligence agencies. They’ve smuggled cocaine — tons and tons of it — across the world and now feed a sizable share of Europe’s drug habit. | — |
| [How a Crew of Romanian Criminals Conquered the World of ATM Skimming](https://www.occrp.org/en/project/how-a-crew-of-romanian-criminals-conquered-the-world-of-atm-skimming)<br><code>how-a-crew-of-romanian-criminals-conquered-the-world-of-atm-skimming</code> | 2020–2022 | Global | 10 | 11 | They weren’t the people you’d peg for success in the world of finance and technology: a group of young men from a small city in an agricultural region of Romania. But they were clever and they had grit — and a unique skill set. | — |
| [Balkan Cocaine Wars](https://www.occrp.org/en/project/balkan-cocaine-wars)<br><code>balkan-cocaine-wars</code> | 2020–2023 | Balkans | 4 | 4 | In February 2015, Goran Radoman parked his armored BMW under his apartment building in Serbia’s capital, Belgrade. As he stepped out of the garage, he was cut down by a hail of machine gun fire. The suspected assassin is still on the run. | — |
| [Fraud Factory](https://www.occrp.org/en/project/fraud-factory)<br><code>fraud-factory</code> | 2020 | Global | 4 | 4 | One January night in Kyiv, a company called Milton Group threw a glitzy New Year’s party for its staff. To the strains of a pop-rock cover band, contortionists and fire-dancers whirled under neon lights as young salespeople revelled in the spoils of a record-breaking year selling investments in cryptocurrencies and stocks. The firm’s management distributed cash,... | Australia: The Guardian; Colombia: La Semana; Croatia: Ostro; Czech Republic: Investigace.cz; Denmark: Politiken; Finland: Helsingin Sanomat; Hungary: Direkt36; Italy: La Stampa; Lithuania: Siena.lt; Norway: VG; Slovenia: Ostro; Spain: El Confidencial; Sweden: Dagens Nyheter; UK: The Guardian; US: McClatchy/Miami Herald |
| [The Two Bosses](https://www.occrp.org/en/project/the-two-bosses)<br><code>the-two-bosses</code> | 2014 | Balkans | 5 | 5 | Seven years after a charismatic mobster was gunned down outside a Sarajevo apartment building, prosecutors think they know what happened that night and who was involved—a suspected drug trafficker and a former media mogul now running for president of Bosnia and Herzegovina. Fahrudin Radoncic and Naser Kelmendi say it is all lies, but a star witness will testify at... | — |
| [A Murderer's Trail](https://www.occrp.org/en/project/a-murderers-trail)<br><code>a-murderers-trail</code> | 2013 | Russia/Eastern Europe | 4 | 0 | No one-line intro displayed. | — |
| [Drug Cartel's Mystery Man](https://www.occrp.org/en/project/drug-cartels-mystery-man)<br><code>drug-cartels-mystery-man</code> | 2012–2013 | Latin America/Caribbean | 6 | 6 | No one-line intro displayed. | — |
| [Game of Control](https://www.occrp.org/en/project/game-of-control)<br><code>game-of-control</code> | 2008–2009 | Balkans | 19 | 47 | Football has ugly, sometimes lethal aspects not immediately obvious to the billions of fans around the world who watch their favorite teams in stadiums or on television. | — |

### A.5 Illicit trade, smuggling, and trafficking — 12 projects, 67 landing-story placements, 69 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [China Tobacco Goes Global](https://www.occrp.org/en/project/china-tobacco-goes-global)<br><code>china-tobacco-goes-global</code> | 2021–2023 | Asia-Pacific | 8 | 10 | You’ve heard of Marlboro, Camel, and Lucky Strike, but what about Silver Elephant, Red Pagoda Mountain, and Double Happiness? | — |
| [How Iran Used an International Playboy to Launder Oil Money](https://www.occrp.org/en/project/how-iran-used-an-international-playboy-to-launder-oil-money)<br><code>how-iran-used-an-international-playboy-to-launder-oil-money</code> | 2020–2021 | Middle East | 7 | 3 | The Republic of Iran had a problem throughout the 2010s: How to sell oil to countries like China that didn’t want to flout U.S. and EU sanctions aimed at Iran’s nuclear program. | — |
| [The Cruel Road North](https://www.occrp.org/en/project/the-cruel-road-north)<br><code>the-cruel-road-north</code> | 2020 | Latin America/Caribbean | 4 | 4 | Every year, Latin American smuggling networks exploit thousands of people from Africa and Asia as they try to make their way to the United States and Canada. | — |
| [Blowing Unsmoke](https://www.occrp.org/en/project/blowing-unsmoke)<br><code>blowing-unsmoke</code> | 2020–2022 | Global | 5 | 5 | No one-line intro displayed. | Aristegui Noticias; IRL; Report RAI3; Rise Romania; The Bureau of Investigative Journalism; The Kyiv Post; Waseda Chronicle |
| [Without a Trace](https://www.occrp.org/en/project/without-a-trace)<br><code>without-a-trace</code> | 2020 | Global | 3 | 3 | Last century, tobacco was one of the world’s most successful industries. This century, if current trends continue, it is expected to kill one billion people. | — |
| [Theatre of War](https://www.occrp.org/en/project/theatre-of-war)<br><code>theatre-of-war</code> | 2018 | Global | 1 | 2 | In just a few years, Pierre Konrad Dadak rose from a small-time Parisian fraudster to become a top representative for one of Central Europe’s biggest arms companies. The Spanish police who arrested Dadak believe he is a global arms trafficker, in bed with the French gangsters. His former business partners say his arms deals were fakes, designed to defraud them of... | — |
| [War Dog Millionaire](https://www.occrp.org/en/project/war-dog-millionaire)<br><code>war-dog-millionaire</code> | 2018 | Balkans | 3 | 3 | Jaroslav Strnad, the chief financial backer of the Czech president, has been secretly snapping up arms stockpiles and factories throughout the Balkans with the help of a cast of notorious local characters. The buy-up has included tens of millions of rounds of old ammunition of a type so unreliable that a previous attempt to sell it inspired a Hollywood movie. | — |
| [Making a Killing](https://www.occrp.org/en/project/making-a-killing)<br><code>making-a-killing</code> | 2016–2017 | Balkans | 14 | 17 | Since the outbreak of war in Syria, weapons from Central and Eastern Europe have flooded the conflict zone through two distinct pipelines – one sponsored by Saudi Arabia and coordinated by the CIA, and the other funded and directed by the Pentagon. | — |
| [Veggie Scam](https://www.occrp.org/en/project/veggie-scam)<br><code>veggie-scam</code> | 2014 | Russia/Eastern Europe | 3 | 3 | What connects terrorists in Iraq, cleaning ladies in Ukraine, and dodgy businessmen in Turkey? Vegetables and tax fraud. A series of scams helped Al Qaeda and hurt Romanian tax officials to the tune of at least € 50 million. | — |
| [The Turbulent World of Armenian Airlines](https://www.occrp.org/en/project/the-turbulent-world-of-armenian-airlines)<br><code>the-turbulent-world-of-armenian-airlines</code> | 2013 | Caucasus | 4 | 4 | Since 2004, airplanes owned or registered to Armenian outfits -- and often flown by Armenian crews outside their native country -- have been involved in a number of dangerous and deadly incidents. Authorities in the countries involved, the airlines and even the manufacturer do not appear interested in looking too closely at the cause of the crashes. The disastrous... | — |
| [Big Trouble at Big Tobacco](https://www.occrp.org/en/project/big-trouble-at-big-tobacco)<br><code>big-trouble-at-big-tobacco</code> | 2011 | Global | 5 | 5 | No one-line intro displayed. | — |
| [Tobacco Underground](https://www.occrp.org/en/project/tobacco-underground)<br><code>tobacco-underground</code> | 2008 | Global | 10 | 10 | The Tobacco Underground is a project of the International Consortium of Investigative Journalists (ICIJ) , program of the Center for Public Integrity in Washington DC. It was done in cooperation with OCCRP journalists in Bosnia and Herzegovina, Romania, Russia and Ukraine and journalists in... | — |

### A.6 Human rights, public welfare, and direct harms — 8 projects, 91 landing-story placements, 60 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [Bad Practice](https://www.occrp.org/en/project/bad-practice)<br><code>bad-practice</code> | 2025–2026 | Global | 11 | 3 | When patients put themselves in the hands of a doctor, they trust they'll be treated with care. But what happens when that trust is abused? | 15min; AmphoraMedia; CIReN; DW Turkish; De Tijd; Der Spiegel; Der Standard; Eesti Ekspress; Expresso; FTM; France Télévisions; Heimildin; Hetq; InfoLibre; Inside Story; Investico; Investigace; Investigative Center of Jan Kuciak (ICJK); Investigative Journalism Bureau at the University of Toronto; L'Espresso; Le Monde; Oštro (Croatia); Oštro (Slovenia); Public Record; RISE Moldova; Re:Baltica; Reporter.lu; Tamedia; The Irish Times; The Times; VG; VSquare; Yle; ZDF; infoLibre; Átlátszó |
| [The Steward Files](https://www.occrp.org/en/project/the-steward-files)<br><code>the-steward-files</code> | 2024 | North America | 6 | 0 | At its height, Steward Health Care ran more than 30 private hospitals across the U.S. helmed by an ambitious CEO who touted a vision of high-quality cost-effective medical services. But as Steward expanded across America and sought to enter international markets, it was secretly lurching towards bankruptcy. The Steward Files reveal how private equity, real estate... | Boston Globe; Times of Malta |
| [Slaves to Progress](https://www.occrp.org/en/project/slaves-to-progress)<br><code>slaves-to-progress</code> | 2020 | Caucasus | 4 | 4 | Few authoritarian states have worked harder than Azerbaijan to leverage major international events to boost their image on the world stage. | — |
| [Crime, Corruption, and Coronavirus](https://www.occrp.org/en/project/crime-corruption-and-coronavirus)<br><code>crime-corruption-and-coronavirus</code> | 2020–2022 | Global | 34 | 16 | Countries around the world are struggling to contain the coronavirus pandemic. But in times of crisis, there are those who seek their own advantage. | — |
| [Birth and Death in Venezuela's Time of Hunger](https://www.occrp.org/en/project/birth-and-death-in-venezuelas-time-of-hunger)<br><code>birth-and-death-in-venezuelas-time-of-hunger</code> | 2018 | Latin America/Caribbean | 10 | 10 | Venezuela’s humanitarian crisis is threatening those who carry the future in their bellies. Pregnant women are going without adequate food or medical attention in the midst of a national economic emergency. The government insists on attributing the crisis to an external plot to overthrow it, while the opposition blames the administration for inefficiency and... | — |
| [The Faces of the Victims of Corruption](https://www.occrp.org/en/project/the-faces-of-the-victims-of-corruption)<br><code>the-faces-of-the-victims-of-corruption</code> | 2017 | Global | 7 | 7 | Corruption is everywhere. An estimated $1 trillion is paid in bribes and another $2.6 trillion is stolen worldwide every year, according to the United Nations . These incredible sums make up five percent of the world’s economy. And they mostly come out of the pockets of the... | — |
| [Document Dilemma](https://www.occrp.org/en/project/document-dilemma)<br><code>document-dilemma</code> | 2009 | Balkans | 11 | 12 | Travel Across Region Brings Legal Ordeal or Costly Risks. | — |
| [Battered Justice](https://www.occrp.org/en/project/battered-justice)<br><code>battered-justice</code> | 2008–2009 | Balkans | 8 | 8 | No one-line intro displayed. | — |

### A.7 Enablers, gatekeepers, and secrecy services — 7 projects, 64 landing-story placements, 66 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [The Worldclear Files](https://www.occrp.org/en/project/the-worldclear-files)<br><code>the-worldclear-files</code> | 2026 | Asia-Pacific | 1 | 2 | From the 10th floor of an office block in the New Zealand city of Hamilton, a small team at a financial services provider called Worldclear transferred millions of dollars for high-risk clients. | Expressen; Interest.co.nz |
| [The Dictators' Bank](https://www.occrp.org/en/project/the-dictators-bank)<br><code>the-dictators-bank</code> | 2023 | Latin America/Caribbean | 5 | 5 | Dante Mossi, the president of the Central American Bank for Economic Integration (CABEI), likes to say the bank sponsors dreams. Where other development banks see obstacles, he says, CABEI sees possibilities. | Confidencial; ContraCorriente; Foreign Policy; Newstapa; TAWPA |
| [Dominica: Passports of the Caribbean](https://www.occrp.org/en/project/dominica-passports-of-the-caribbean)<br><code>dominica-passports-of-the-caribbean</code> | 2023 | Latin America/Caribbean | 6 | 7 | Unlike the traditional path to citizenship in countries around the world, for years, Dominica citizenship could be secured without even stepping on the island. | — |
| [Biometric Bribery: Inside Semlex’s Global Playbook](https://www.occrp.org/en/project/biometric-bribery-inside-semlexs-global-playbook)<br><code>biometric-bribery-inside-semlexs-global-playbook</code> | 2018–2020 | Africa | 6 | 3 | Semlex is an unassuming Brussels-based company that supplies biometric documents such as passports and driving licenses to governments and international bodies. | — |
| [#29LEAKS: Inside a London Company Mill](https://www.occrp.org/en/project/29leaks-inside-a-london-company-mill)<br><code>29leaks-inside-a-london-company-mill</code> | 2019–2021 | EU/Western Europe | 9 | 12 | What do a Swedish Hells Angels boss, an Iranian state oil company, the Italian mob, and a fake Gambian bank have in common? The answer: A company services firm called Formations House, hidden behind the doors of one of London’s most exclusive addresses. | — |
| [Gold for Visas](https://www.occrp.org/en/project/gold-for-visas)<br><code>gold-for-visas</code> | 2018 | Global | 18 | 18 | For refugees and poor migrants, travel can be terrifying, with no guarantee of a welcome at the end. For the one percent,​ ​it's a different story, as a growing number of cash-strapped countries invite them in​ ​—​ ​as long as they bring plenty of money. | — |
| [The Proxy Platform](https://www.occrp.org/en/project/the-proxy-platform)<br><code>the-proxy-platform</code> | 2011–2012 | Russia/Eastern Europe | 19 | 19 | While governments and citizens of Eastern Europe were struggling with the recent financial crisis and trying to borrow money from international financial institutions, billions of euros circulated in the region in an illegal, parallel, system that enriched organized crime figures and corrupt politicians.The system is built on hundreds, maybe thousands, of... | — |

### A.8 Surveillance, influence operations, and media capture — 6 projects, 40 landing-story placements, 33 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [Dear Compatriots](https://www.occrp.org/en/project/dear-compatriots)<br><code>dear-compatriots</code> | 2025–2026 | Russia/Eastern Europe | 10 | 3 | Under the banner of legal aid for fellow Russians in trouble abroad, a state-backed foundation in the center of Moscow has for years advanced the Kremlin’s agenda across the world. | Buro Media; Context.ro; DR; Dagbladet Information; Delfi Estonia; Der Spiegel; Der Standard; Frontstory.pl; Göteborgs-Posten; Knack; LRT; RISE Moldova; Schemes (Radio Liberty); ZDF; investigace.cz |
| [Story Killers](https://www.occrp.org/en/project/story-killers)<br><code>story-killers</code> | 2023 | Global | 5 | 4 | Indian journalist Gauri Lankesh was uncharacteristically relaxed the day she was murdered. | Forbidden Stories; The Guardian |
| [The Pegasus Project](https://www.occrp.org/en/project/the-pegasus-project)<br><code>the-pegasus-project</code> | 2021 | Global | 13 | 17 | They never heard it. There was no beep, no sound at all. But in those silent seconds, a digital intruder entered their phones. Their private moments and their professional secrets became instantly accessible. Even their cameras could be activated to snap photos at the will of a faraway attacker. | Aristegui Noticias; Forbidden Stories; Haaretz; The Washington Post |
| [Euros to the East](https://www.occrp.org/en/project/euros-to-the-east)<br><code>euros-to-the-east</code> | 2019 | Russia/Eastern Europe | 3 | 3 | In collaboration with Danwatch, a Danish investigative research center, OCCRP looked into an EU program that provided surveillance gear, patrol vehicles, and other equipment to Belarusian and Ukrainian authorities with the goal of strengthening the two countries’ border on the eastern edge of Europe. | — |
| [Spooks and Spin: Information War in the Balkans](https://www.occrp.org/en/project/spooks-and-spin-information-war-in-the-balkans)<br><code>spooks-and-spin-information-war-in-the-balkans</code> | 2017–2018 | Balkans | 9 | 6 | Great power politics has returned to the Balkans. The countries of the region – riven by authoritarianism, political rivalry, and ethnic tensions – are caught between an increasingly assertive Russia and a NATO eager for new allies. As the world reckons with a new era of propaganda, this European hotspot has become a key battleground in information warfare. | — |
| [Internet Ownership](https://www.occrp.org/en/project/internet-ownership)<br><code>internet-ownership</code> | 2015 | Russia/Eastern Europe | 0 | 0 | The Organized Crime and Corruption Reporting Project, Euractiv and RISE Project spent months investigating who owns the Internet across Eastern Europe. In the coming weeks and months, we will release stories and data about the individuals and companies that control the technology that brings the internet to you. | — |

### A.9 Attacks on journalists / continuation projects — 5 projects, 48 landing-story placements, 47 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [A Journalist’s Undying Legacy](https://www.occrp.org/en/project/a-journalists-undying-legacy)<br><code>a-journalists-undying-legacy</code> | 2019–2023 | EU/Western Europe | 10 | 7 | Two years have passed since investigative journalist Ján Kuciak and his fiancée, Martina Kušnírová, were gunned down in cold blood in their home south of Bratislava. | — |
| [Unfinished Lives, Unfinished Justice](https://www.occrp.org/en/project/unfinished-lives-unfinished-justice)<br><code>unfinished-lives-unfinished-justice</code> | 2019 | EU/Western Europe | 4 | 4 | One year ago, a former policeman slipped into the home investigative journalist Ján Kuciak shared with his fiancee, Martina Kušnírová, and shot them both at close range, authorities say. | — |
| [Death On The Border](https://www.occrp.org/en/project/death-on-the-border)<br><code>death-on-the-border</code> | 2018 | Latin America/Caribbean | 5 | 5 | Seven months ago, three employees of the Ecuadorian newspaper El Comercio were abducted in the Mataje River region on the border between Ecuador and Colombia. After almost three weeks in captivity, reporter Javier Ortega, photographer Paul Rivas, and their driver, Efrain Segarra, were executed by the Oliver Sinisterra Front, a group of former FARC guerillas and drug... | — |
| [The Daphne Project](https://www.occrp.org/en/project/the-daphne-project)<br><code>the-daphne-project</code> | 2018–2022 | EU/Western Europe | 13 | 14 | In October 2017, Maltese journalist Daphne Caruana Galizia was brutally killed by a car bomb just meters from her home. The investigation into her killing is ongoing, but there is little doubt that she was murdered because of her work. With a brazen, unapologetic and uncompromising style, she denounced corruption, nepotism, clientelism, and all kinds of criminal... | — |
| [A Murdered Journalist's Last Investigation](https://www.occrp.org/en/project/a-murdered-journalists-last-investigation)<br><code>a-murdered-journalists-last-investigation</code> | 2018 | EU/Western Europe | 16 | 17 | In late February 2018, Jan Kuciak, a young Slovak investigative journalist, was shot dead. His fiancée was killed alongside him. | — |

### A.10 Extractives, energy, and environmental corruption — 4 projects, 36 landing-story placements, 47 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [The Steinmetz Scandals](https://www.occrp.org/en/project/the-steinmetz-scandals)<br><code>the-steinmetz-scandals</code> | 2024 | Africa | 2 | 2 | Mining magnate Beny Steinmetz earned a reputation as a titan in the diamond world, and then cemented his fortune with a multibillion-dollar deal over coveted iron ore deposits. | — |
| [Gold and Chaos in Orinoco](https://www.occrp.org/en/project/gold-and-chaos-in-orinoco)<br><code>gold-and-chaos-in-orinoco</code> | 2017 | Latin America/Caribbean | 5 | 5 | A joint investigation by Efecto Cocuyo and OCCRP ​explores the Orinoco Mining Arc — the Venezuelan government's controversial attempt to find new sources of wealth — and the devastating effects of the mining on the people who live there. | — |
| [The Battle for Mineral Resources](https://www.occrp.org/en/project/the-battle-for-mineral-resources)<br><code>the-battle-for-mineral-resources</code> | 2013–2016 | Russia/Eastern Europe | 7 | 7 | Throughout Eastern Europe and the CIS countries, governments have squandered natural resources allowing bribery, corruption and theft to deprive the people of the valuable mineral resources that lie beneath the ground. OCCRP looked at one bribery case to understand how this is being done. | — |
| [The Power Brokers](https://www.occrp.org/en/project/the-power-brokers)<br><code>the-power-brokers</code> | 2007 | Balkans | 22 | 33 | Reporters from Albania, Bosnia-Herzegovina, Bulgaria and Romania looked at the regional energy market and energy traders. What they found was a murky, closed system that is not open to fair trade and where the state companies are giving away their advantage to well-connected energy traders. | — |

### A.11 Methods, explainers, and formats — 5 projects, 44 landing-story placements, 13 sitemap URLs

Counts in this heading and table are from the 105 fetched OCCRP project landing pages, the three article sitemaps, and `raw/project-classification.csv`.

| Project and slug | Story date span | Primary region **[inferred]** | Landing stories | Sitemap URLs | One-line subject from OCCRP | Partner/member-center labels shown |
|---|---:|---|---:|---:|---|---|
| [Dirty Deeds Podcast](https://www.occrp.org/en/project/dirty-deeds-podcast)<br><code>dirty-deeds-podcast</code> | 2023 | Global | 7 | 7 | Are you ready to venture into the shadows? Dirty Deeds: Tales of Global Crime & Corruption is a gripping podcast that delves deep into the realm of investigative journalism, unraveling hidden stories of jaw-dropping fraud and deceit. | — |
| [Beneficial Ownership Data is Critical in the Fight Against Corruption](https://www.occrp.org/en/project/beneficial-ownership-data-is-critical-in-the-fight-against-corruption)<br><code>beneficial-ownership-data-is-critical-in-the-fight-against-corruption</code> | 2020–2023 | Global | 9 | 3 | In the aftermath of a “disastrous” European court ruling, we explain why journalists — and the public — need access to corporate ownership registries. | Atlatszo.hu; Direkt36; Forbes; IRPI; IStories; Inside Story; Proekt; Re:Baltica; The Insider; The Investigative Center of Ján Kuciak; Transparency International |
| [What Is “Unexplained Wealth”?](https://www.occrp.org/en/project/what-is-unexplained-wealth)<br><code>what-is-unexplained-wealth</code> | 2014–2021 | Global | 26 | 1 | The prime minister’s bodyguard who lives luxuriously in a dual-wing, classically designed, multi-million-dollar mansion. The son of a railway official who sits on the throne of a real estate empire spread across an entire continent. The city mayor whose offshore holdings control some of his home country’s most lucrative construction firms. | — |
| [Ask OCCRP: Our Team Answers Questions from OCCRP Accomplices](https://www.occrp.org/en/project/ask-occrp-our-team-answers-questions-from-occrp-accomplices)<br><code>ask-occrp-our-team-answers-questions-from-occrp-accomplices</code> | 2020 | Global | 2 | 1 | Global crime and corruption thrive in obscurity. OCCRP is dedicated to exposing the complex financial networks that facilitate white-collar crime. | — |
| [‘Laundromats,’ Explained: How Shell Companies Are Used to Launder Money](https://www.occrp.org/en/project/laundromats-explained-how-shell-companies-are-used-to-launder-money)<br><code>laundromats-explained-how-shell-companies-are-used-to-launder-money</code> | 2019 | Global | 0 | 1 | Much of the money that moves around the world is hidden. | — |
