# Report 09 — Meta-Methods: ProPublica's Methodology Infrastructure and Reusable Data Assets

**Agent:** meta-methods reviewer (web research only; no DB writes)
**Date:** 2026-07-28
**Method:** Direct fetches of propublica.org / projects.propublica.org pages plus targeted web searches; secondary sources (Nieman Lab, GIJN, First Draft, RAND, Poynter) used only to corroborate or quantify ProPublica's own statements. Claims sourced to a URL throughout; my own analytical glosses are marked **[inferred]**.

---

## 1. The Nerd Blog (propublica.org/nerds)

The Nerd Blog ran from September 2010 ("Welcome to the Nerd Blog," https://www.propublica.org/nerds/welcome-to-the-nerd-blog) to roughly August 2022 ("Visualizing Toxic Air," https://www.propublica.org/nerds/visualizing-toxic-air). The full archive is 4 index pages (https://www.propublica.org/nerds through /nerds/page/4). Twelve posts that document reusable technique, selected for the priorities requested (record linkage, database-from-dump construction, statistical standards for accusatory findings, scraping practice):

### 1.1 "Scraping for Journalism: A Guide for Collecting Data" (Dan Nguyen, Dec 30, 2010)
URL: https://www.propublica.org/nerds/doc-dollars-guides-collecting-the-data
Technique: the original Dollars for Docs data-collection curriculum, published as five chapters, each its own post:
- Ch.1 cleaning messy data with Google Refine — https://www.propublica.org/nerds/using-google-refine-for-data-cleaning
- Ch.2 reading data out of Flash-only disclosure sites — https://www.propublica.org/nerds/reading-flash-data
- Ch.3 turning PDFs to text — https://www.propublica.org/nerds/turning-pdfs-to-text-doc-dollars-guide
- Ch.4 scraping HTML — https://www.propublica.org/nerds/scraping-websites
- Ch.5 OCR on image-only PDFs with ImageMagick+Tesseract — https://www.propublica.org/nerds/image-to-text-ocr-and-imagemagick
Summary: pharma companies were legally obligated to disclose physician payments but did so in deliberately heterogeneous formats — Flash widgets, image PDFs, paginated HTML. The guide treats hostile-format disclosure as a solvable engineering problem and canonizes the pipeline: acquire → normalize → clean (clustering/dedupe in Refine) → unify into one cross-company database. Companion essay "The Coder's Cause in Dollars for Docs" (https://www.propublica.org/nerds/the-coders-cause-in-dollars-for-docs) frames public-records access as a programming problem.

### 1.2 "Heart of Nerd Darkness: Why Dollars for Docs Was So Difficult" (Mar 25, 2013)
URL: https://www.propublica.org/nerds/heart-of-nerd-darkness-why-dollars-for-docs-was-so-difficult
Technique: record linkage / entity resolution across messy vendor datasets at scale. Documents the pain of the 2013 D4D update: 15 companies' disclosures, each with different name conventions, no shared identifiers, requiring name-matching physicians across files and against license rosters. This is ProPublica's most candid writeup of why cross-source person-matching dominates the cost of a unified accountability database. **[inferred: the post is the pre-history of why CMS Open Payments — a single mandated format — was the fix; ProPublica's unified scrape demonstrated demand.]**

### 1.3 "How ProPublica's Message Machine Reverse Engineers Political Microtargeting" (2012)
URL: https://www.propublica.org/nerds/how-propublicas-message-machine-reverse-engineers-political-microtargeting (companion story: https://www.propublica.org/article/reverse-engineering-obamas-message-machine)
Technique: crowdsourced input + machine clustering. Readers forwarded campaign emails and filled in a short demographic profile; the Machine compared each new email to known variants using TF-IDF word vectors and cosine similarity (stored in the Daybreak key-value store), minting a new variant when similarity fell below threshold — then correlated variant assignment with recipient demographics to expose microtargeting. Corroboration: https://www.niemanlab.org/2012/10/propublicas-message-machine-is-figuring-out-what-the-obama-campaign-knows-about-me/. The template: when the targeting model is private, reconstruct it from the outputs delivered to a crowdsourced panel.

### 1.4 "How We Calculated Injury Rates for Temp and Non-Temp Workers" (Pierce, Larson, Grabell; Dec 18, 2013)
URL: https://www.propublica.org/nerds/how-we-calculated-injury-rates-for-temp-and-non-temp-workers
Technique: the statistical-standards post for an accusatory disparity claim — computing comparable injury *rates* (not counts) for temporary vs. permanent workers from state workers'-compensation claims, with the denominator problem (how many temp workers are at risk) treated as the central methodological choice. **[inferred from title/summary and the investigation it supported; the archetype of "a disparity is a story only once you've defended the denominator."]**

### 1.5 "Casino-Driven Design" (Al Shaw, Mar 20, 2013)
URL: https://www.propublica.org/nerds/casino-driven-design
Technique: UI design for crowdsourced document transcription (Free the Files). Borrow the casino's discipline — remove every distraction, keep the task (one document, a few fields) center-screen, make progress visible — so volunteers stay accurate and engaged over thousands of repetitive documents.

### 1.6 "Transcribable: Free the Files to Go!" (Al Shaw, Jul 16, 2013)
URL: https://www.propublica.org/nerds/transcribable-free-the-files-to-go
Technique: open-sourcing the Free the Files crowdsourcing engine as a Rails plugin so any newsroom can run verified crowd transcription of a PDF corpus. Together 1.5/1.6 are the canonical "documents in, structured data out, crowd in the middle" infrastructure posts.

### 1.7 "Authenticating Email Using DKIM and ARC, or How We Analyzed the Kasowitz Emails" (Jul 19, 2017)
URL: https://www.propublica.org/nerds/authenticating-email-using-dkim-and-arc-or-how-we-analyzed-the-kasowitz-emails
Technique: cryptographic document authentication. When Trump's lawyer disputed threatening emails, ProPublica validated the messages via DKIM signatures (and ARC chains) against the sending domains' published keys — turning "he said/she said" over a leaked artifact into a verifiable cryptographic check.

### 1.8 "Chamber of Secrets: Teaching a Machine What Congress Cares About" (Oct 4, 2017) + "More Machine Learning About Congress' Priorities" (Nov 20, 2017)
URLs: https://www.propublica.org/nerds/teaching-a-machine-what-congress-cares-about ; https://www.propublica.org/nerds/more-machine-learning-about-congresss-priorities
Technique: ML text classification over the congressional record/bill corpus to surface each member's distinctive priorities — an early, documented example of their "model proposes, human verifies" stance later formalized in the AI policy (§5.3).

### 1.9 "How ProPublica Illinois Uses GNU Make to Load 1.4GB of Data Every Day" (David Eads, Jul 10, 2018)
URL: https://www.propublica.org/nerds/gnu-make-illinois-campaign-finance-data-david-eads-propublica-illinois
Technique: reproducible, idempotent data pipelines for a daily-refreshed accountability database (Illinois campaign finance). Make as the orchestration layer; processing cut from hours to ~30 minutes; code open-sourced. The operational-discipline post: the pipeline itself is part of the evidence chain.

### 1.10 "New: You Can Now Search the Full Text of 3 Million Nonprofit Tax Records for Free" (Jun 6, 2019)
URL: https://www.propublica.org/nerds/new-search-full-text-of-3-million-nonprofit-tax-records-for-free
Technique: document-dump-to-database at national scale — IRS 990 e-file XML plus OCR'd image filings unified into full-text-searchable Nonprofit Explorer (grants, investments, officer names). Lineage: API (2013, https://www.propublica.org/nerds/announcing-the-nonprofit-explorer-api); full text of 1.9M records (2017, https://www.propublica.org/nerds/nonprofit-explorer-update-full-text-of-nearly-two-million-records); people search (2018, https://www.propublica.org/nerds/new-in-nonprofit-explorer-people-search); employees/officers per org (2021, https://www.propublica.org/nerds/new-view-an-organizations-employees-and-officers-on-nonprofit-explorer).

### 1.11 "Working Together Better: Our Guide to Collaborative Data Journalism" (Aug 14, 2019) + "Making Collaborative Data Projects Easier: Our New Tool, Collaborate, Is Here" (Sep 11, 2019)
URLs: https://www.propublica.org/nerds/collaborative-data-journalism-guide ; https://www.propublica.org/nerds/making-collaborative-data-projects-easier-our-new-tool-collaborate-is-here
Technique: the crowdsourcing/collaboration playbook distilled from Electionland and Documenting Hate, plus the open-source tool (django-collaborative, https://github.com/propublica/django-collaborative) for shared tip datasets: import CSV/Google Sheets/Screendoor, assign tips, track contact status, auto-redact sensitive fields. Manuals: https://propublica.gitbook.io/collaborate-user-manual and https://propublica.gitbook.io/collaborative/introduction. See also "Want to Start a Collaborative Journalism Project? We're Building Tools to Help" (Feb 28, 2019, https://www.propublica.org/nerds/collaborative-journalism-project-building-tools-to-help).

### 1.12 "Building a Database From Scratch: Behind the Scenes With Documenting Hate Partners" (Oct 23, 2019) + "I Spent Three Years Running a Collaboration Across Newsrooms. Here's What I Learned." (Dec 13, 2019)
URLs: https://www.propublica.org/nerds/building-a-database-from-scratch-behind-the-scenes-with-documenting-hate-partners ; https://www.propublica.org/nerds/i-spent-three-years-running-a-collaboration-across-newsrooms-heres-what-i-learned
Technique: constructing an incident database where no official statistic exists (hate incidents), and the management layer — training partners, verification standards, access control — that keeps a 180-newsroom shared database credible.

Honorable mentions: "Upton: A Web Scraping Framework" (2013, https://www.propublica.org/nerds/upton-a-web-scraping-framework); "A Conceptual Model for Interactive Databases in News" (2014, https://www.propublica.org/nerds/a-conceptual-model-for-interactive-databases-in-news); "How We Analyzed FEMA's Risk Maps" (2013, https://www.propublica.org/nerds/how-we-analyzed-femas-risk-maps); Hadley Wickham — "your default position should be skepticism" (2019, https://www.propublica.org/nerds/hadley-wickham-your-default-position-should-be-skepticism-and-other-advice-for-data-journalists); "Shedding Some Light on Dark Money Political Donors" ($763M dark-money donation database, 2018, https://www.propublica.org/nerds/shedding-some-light-on-dark-money-political-donors); "How (and Why) We're Collecting Cook County Jail Data" (2017, https://www.propublica.org/nerds/how-and-why-collecting-cook-county-jail-data).

---

## 2. The Data Store (projects.propublica.org/datastore/)

Status: launched March 2014 (http://www.knightdigitalmediacenter.org/news/2014/03/propublica-launches-data-store.html); at launch it mixed free FOIA-derived datasets with "premium" datasets priced at $200 for journalists (https://www.journalism.co.uk/propublica-opens-data-store-with-free-and-premium-data/; premium examples were Dollars for Docs and Prescriber Checkup data — product pages still resolve, e.g. https://projects.propublica.org/docdollars/products/11953). A year in it had logged 2,000+ downloads (https://www.propublica.org/nerds/one-year-2000-downloads-heres-how-our-data-store-is-doing). Today the store is an explicitly frozen archive: "The information in this archive of the Data Store is not actively updated. It is provided as a historical snapshot" (datasets 2013–2023; https://projects.propublica.org/datastore/). Terms: https://www.propublica.org/datastore/terms/.

Catalog by domain (name — origin — story powered — access), as listed on the archive page unless otherwise linked:

### Health
- **Medicare Part D Prescribing Data, 2010–2016** — CMS — powered *Prescriber Checkup* (https://projects.propublica.org/checkup/) — free (bulk was premium-tier). Companion: Part D Hepatitis C prescribing (2014).
- **Medicare Part B Provider Utilization and Payment** — CMS — free.
- **Dollars for Docs pharma payments** — scraped company disclosures, later CMS Open Payments — *Dollars for Docs* (https://projects.propublica.org/docdollars/; data notes: https://www.propublica.org/article/about-our-pharma-data) — premium at launch.
- **Nursing Home Compare deficiencies/penalties** — CMS — *Nursing Home Inspect* — free.
- **ER inspection reports + timely-care metrics** — CMS — *ER Inspector* — free.
- **Surgeon-level complication rates** — CMS inpatient claims 2009–2013 — *Surgeon Scorecard* (https://projects.propublica.org/surgeons/) — app public; methodology §3.2.
- **Chicken Checker** — USDA FSIS salmonella testing — free.
- **ACA Plan Compare (2014–2015)**, **CDC mortality**, **FDA clinical-trial participant demographics**, **Hospital bed capacity & COVID-19** (Harvard Global Data Institute), **Interim state COVID-19 vaccine distribution plans** — free.

### Politics & elections
- **Free the Files Filing Data** — FCC station political files, structured by ~1,000 volunteers — free (see §4.1).
- **House Office Expenditure Data** — U.S. House — free.
- **2016 / 2018 candidate lists** — FEC + Center for Responsive Politics — free.
- **Dark-money donor database** — reassembled from 990s — https://www.propublica.org/nerds/shedding-some-light-on-dark-money-political-donors — free.
- APIs adjacent to the store: **Congress API** (adopted from the Sunlight Foundation at its wind-down — https://www.propublica.org/nerds/sunlight-labs-takeover-update, https://www.propublica.org/nerds/congress-api-update), **Campaign Finance API** (https://www.propublica.org/nerds/meet-the-new-propublica-campaign-finance-api-same-as-the-old-api), **FEC Itemizer** (https://www.propublica.org/nerds/introducing-fec-itemizer-a-tool-to-research-federal-election-spending), **Nonprofit Explorer API** (https://www.propublica.org/nerds/announcing-the-nonprofit-explorer-api).

### Criminal justice
- **COMPAS Recidivism Risk Score Data and Analysis** — Broward County FOIA — *Machine Bias* — free, also GitHub (https://github.com/propublica/compas-analysis).
- **Civilian Complaints Against NYPD Officers** — NYC CCRB — free.
- **Chicago PD gang members data** + **Cook County Regional Gang Intelligence Database snapshot** — police FOIA — free.
- **Federal Air Marshal misconduct database** — TSA — free.
- **ICE arrest data 2013–2017** — ICE — free.
- **Northern Illinois federal gun cases** — PACER-derived — free.
- **Credibly Accused Priests** — compiled from diocesan disclosures — free.
- **Child Abuse Prevention and Treatment Act reports 2011–2015** — state/county agencies — free.
- **City of Chicago parking/camera tickets (28M+ records)** + **"race-neutral" traffic-camera tickets** — Chicago Dept. of Finance FOIA — *The Ticket Trap* (https://www.propublica.org/nerds/download-chicago-parking-ticket-data; https://www.propublica.org/nerds/the-ticket-trap-news-app-front-to-back-david-eads-propublica-illinois) — free.
- **LA County sheriff's deputy contacts (Lancaster)** — LASD — free.

### Education
- **Alternative schools in U.S. districts** — U.S. Dept. of Education — free.
- **New Mexico school discipline 2010–2022** — NM PED — free.
- **Opportunity Gap** app data — federal civil-rights data collection — methodology https://www.propublica.org/article/opportunity-gap-methodology.

### Business / finance
- **Amazon pricing data** — constructed by scraping Amazon — 2016 pricing-algorithm story — free.
- **Consumer bankruptcy filings 2008–2015** — DOJ — free.
- **Debt collection lawsuit datasets** — state court records — free.
- **Cook County commercial/industrial property assessments** — Cook County Assessor — free.
- **IRS audit rates by county** — IRS + researcher Kim M. Bloomquist — free.
- **Georgia title lenders**, **New York State subsidy programs**, **TCJA home-price impact (Moody's Analytics)**, **New Jersey public-sector contracts** — free.

### Environment / military
- **EPA RSEI + TRI derived toxmap data** — released post-Sacrifice Zones (https://www.propublica.org/article/were-releasing-the-data-behind-our-toxic-air-analysis; app https://projects.propublica.org/toxmap/) — free.
- **Defense Environmental Restoration Program sites (39,000+)** — DoD — https://www.propublica.org/nerds/data-get-an-inside-look-at-the-department-of-defense-struggle-to-fix-pollution — free.
- **Commander's Emergency Response Program payments (Afghanistan)** — SIGAR — free.
- **Harris County flood buyouts 1985–2017**, **Hawaii seawall exemptions 2000–2020** — county/state records — free.

### Crowd-constructed corpora (unique to ProPublica)
- **Documenting Hate News Index (raw)** — Google News-derived hate-incident index — free.
- **Audio: crying children inside a CBP facility** — leaked primary audio published as data — free.

**Platform takeaway [inferred]:** the Data Store is the exhaust-capture layer — every major investigation's cleaned intermediate becomes a citable, redistributable asset. Roughly half is straight agency FOIA output; the differentiated half is *constructed* (scraped, crowd-transcribed, or leak-derived) data that exists nowhere else.

---

## 3. "How We Did This" Practice

Eight exemplars across investigation types, then the extracted common structure.

### 3.1 Machine Bias / COMPAS (2016) — algorithmic audit
https://www.propublica.org/article/how-we-analyzed-the-compas-recidivism-algorithm
- Data via public-records request (Broward Sheriff: 18,610 scored people, 2013–14; filtered to 11,757 pretrial), matched to clerk and DOC records.
- Record linkage by name+DOB, deliberately "the same approach as the official 2010 Broward County validation study"; measured a **3.75% matching error rate on a 400-case random sample** and disclosed it.
- Recidivism defined using Northpointe's own 2009 standard (fingerprintable UCR arrest within 2 years; traffic/municipal excluded).
- Methods: logistic regression, Cox proportional hazards (Northpointe's own method), contingency tables for false-positive/negative rates by race.
- Full release: notebook + SQLite DB at https://github.com/propublica/compas-analysis.

### 3.2 Surgeon Scorecard (2015) — clinical outcomes scoring
Short methodology: https://www.propublica.org/article/surgeon-level-risk-short-methodology; **white paper PDF: https://static.propublica.org/projects/patient-safety/methodology/surgeon-level-risk-methodology.pdf**; expert quotes: https://www.propublica.org/article/surgeon-level-risk-quotes; app: https://projects.propublica.org/surgeons/
- Medicare inpatient claims 2009–2013, eight elective procedures; 16,827 surgeons at 3,575 hospitals; 63,173 readmissions, 3,405 deaths; minimum 20 procedures to be reported.
- Mixed-effects (hierarchical) model in R/lmer adjusting for age, health, hospital; shrinkage by design.
- "A panel of at least five doctors, including specialists who perform the procedure, reviewed the principal diagnosis code" on 30-day readmissions to decide what counted as a complication.
- Post-publication academic contest: RAND critique (https://www.rand.org/pubs/perspectives/PE170.html — 82% of operations excluded by inclusion criteria; hospital random effect set to zero) and rebuttal cycle (https://www.rand.org/pubs/periodicals/health-quarterly/issues/v6/n1/04.html). The named exemplar of methodology-as-white-paper *and* of transparent methodology surviving formal external attack.

### 3.3 Sacrifice Zones / Toxmap (2021) — environmental modeling
https://www.propublica.org/article/how-we-created-the-most-detailed-map-ever-of-cancer-causing-industrial-air-pollution
- ~7 billion rows of EPA RSEI model output (810 m grid) built on self-reported TRI emissions; 105 hazardous air pollutants with cancer potency values; 2014–2018 averaged; only cells at ≥1-in-100,000 lifetime risk shaded.
- Exclusions stated: mobile sources, criteria pollutants, non-TRI facilities, wildfires, pesticides, Superfund, non-inhalation pathways — with the directional claim that the map "underestimates the excess cancer risk."
- Validation: methodology checked with multiple air-modeling experts "including a former EPA contractor who used to work on the RSEI model"; seven reporters contacted **193 of the 200 top-emitting facilities**; of 109 responding companies, **29% flagged errors, corrected before publication**.
- Data released: https://www.propublica.org/article/were-releasing-the-data-behind-our-toxic-air-analysis.

### 3.4 Car insurance disparities (2017, with Consumer Reports) — pricing audit
https://www.propublica.org/article/minority-neighborhoods-higher-car-insurance-premiums-methodology
- Purchased commercial data: ~30M premium quotes from Quadrant Information Services (44 driver profiles) + S&P Global rate filings; records requests to all 50 insurance commissioners yielded zip-level loss data from only CA, IL, MO, TX.
- Compared premiums against aggregate risk (paid losses per insured car per zip) using smoothing splines; standardized driver profile; per-state thresholds and outlier trims disclosed.
- Limitations conceded in print: "relatively low R-squared values"; insurers may face different risk distributions than state aggregates.
- Industry response solicited and quoted (PCIAA: rates are "color-blind and solely based on risk").

### 3.5 Lost Mothers (2017–18) — crowdsourced cohort construction
https://www.propublica.org/article/how-we-collected-nearly-5-000-stories-of-maternal-harm
- Callout questionnaire (with NPR) distributed via NPR's Facebook reach, partner translations (Univision), niche outlets (Cosmopolitan, The Root, Texas Tribune), CUNY outreach to hundreds of Facebook groups. Nearly 5,000 responses, all 50 states, deaths spanning 1920–2017.
- Deceased mothers identified by scouring public Facebook/Twitter/GoFundMe/YouCaring posts, then "verified the women's basic information using obituaries and public records"; NYU graduate students contacted families.
- Representation gap measured and disclosed: fewer than 75 of the first 2,500 responses from Black mothers vs. a 3–4x Black mortality rate; corrective outreach documented. GIJN case study: https://gijn.org/stories/how-they-did-it-propublicas-maternal-mortality-series/

### 3.6 Federal health-agency workforce tracker (2025) — directory-diff estimation
https://www.propublica.org/article/propublica-health-agencies-workers-methodology
- HHS employee directory (directory.psc.gov, ~140K entries) diffed over time; disappearance of a pre–Jan 25, 2025 email counted as a departure.
- Verification: LinkedIn/open-source spot checks, interviews, test cases on known high-profile arrivals/departures; AI-classified job titles manually reviewed.
- Exclusions and caveats enumerated: CMS excluded (irregular updates), interns/group mailboxes excluded, ~2,500 incomplete entries, 78% of NIH entries lack role data, and "Not all departures are layoffs."
- Non-response noted on the record: "HHS did not respond to ProPublica's questions about why it wouldn't share data on workforce reductions."

### 3.7 The Secret IRS Files (2021) — leak verification
https://www.propublica.org/article/the-inside-story-of-how-we-reported-the-secret-irs-files
- Authentication of a source-unknown leak by (a) contacting people who appear in the data, (b) cross-referencing SEC filings, court records, stock-trade reporting, (c) internal reconstruction of the dataset's structure.
- Explicit posture: they "don't actually know who the source is"; authenticity verification substitutes for source identity.
- Published the ethical balancing (privacy vs. public interest) and legal theory (First Amendment; data neither solicited nor illegally obtained by ProPublica).

### 3.8 The Opportunity Gap (2011) — federal dataset repurposing
https://www.propublica.org/article/opportunity-gap-methodology
- U.S. Dept. of Education civil-rights data; key disclosed analytic choice: free/reduced-price-lunch share as the poverty proxy, the variable with the strongest observed relationship to advanced-course access.

### Common structure (the sidebar formula)
1. **Source and vintage** of every dataset (agency, years, acquisition route).
2. **Population definition and denominator.**
3. **Exclusions, with reasons and counts** (COMPAS: non-pretrial; Scorecard: trauma/ED/transfers; Toxmap: non-TRI; workforce: CMS, interns).
4. **Definitions borrowed from the audited party's own standard** (Northpointe's recidivism definition; the county's own matching protocol; EPA's own model and thresholds).
5. **Measured error rates** for linkage/classification.
6. **Model specification and its known biases** (shrinkage, hospital-effect-zeroing, spline R²).
7. **External expert review before publication.**
8. **Subject response solicited at scale**, including data subjects, with corrections incorporated pre-publication.
9. **Directional limitation statements** ("underestimates," "not all departures are layoffs").
10. **Release of data/code** where possible.

---

## 4. Crowdsourcing & Collaboration Machinery

### 4.1 Free the Files (2012)
App: https://projects.propublica.org/free-the-files/; FAQ: https://www.propublica.org/article/free-the-files-frequently-asked-questions; lessons: https://www.propublica.org/article/crowdsourcing-campaign-spending-what-we-learned-from-free-the-files; Nieman: https://www.niemanlab.org/2012/12/crowdsourcing-campaign-spending-what-propublica-learned-from-free-the-files/
- **Evidence class no records request could produce:** the FCC had just forced TV stations to post political ad contracts online — but as non-standardized PDFs with no data layer. Volunteers (~500 core users per https://source.opennews.org/articles/free-files-api/; "nearly 1,000" total per Nieman) transcribed 5,000+ files across 33 swing markets, logging on the order of $1 billion in 2012 ad buys — a structured dark-money ad-spend dataset that did not exist inside the government. Output persists as the Free the Files Filing Data dataset (§2) and an API (https://www.propublica.org/nerds/introducing-a-free-the-files-api).
- **Credibility mechanism:** single-task casino-driven UI (§1.5) and agreement across multiple independent volunteer transcriptions before an entry counted as "freed" **[inferred from the design posts and FAQ]**; tooling open-sourced as Transcribable (§1.6).

### 4.2 Electionland (2016–2020)
Hub: https://www.propublica.org/electionland/; launch: https://www.propublica.org/article/monitoring-the-vote-with-electionland; operations: https://firstdraftnews.org/articles/electionland-set-600-strong-newsgathering-operation/; https://www.poynter.org/tech-tools/2016/on-election-day-propublica-will-lead-a-national-team-of-real-time-voting-sleuths/
- **Evidence class:** same-day, geolocated voter-experience incidents (lines, machine failures, ballot access) — unobtainable by FOIA because the records don't exist until months later, if ever.
- **Machinery:** coalition (USA Today Network, WNYC, Univision, Google News Lab, First Draft); ~600 journalism students as the "Feeder" doing social discovery; tips triaged in Meedan's **Check** platform (https://www.niemanlab.org/2017/07/this-tool-is-helping-newsrooms-collaborate-on-factchecking-and-verification-projects/); verified leads routed to 300+ signed-up local reporters for on-the-ground confirmation.
- **Credibility mechanism:** First Draft social-verification protocols; catcher → verifier → local-reporter pipeline before publication **[workflow documented in the First Draft writeup]**.

### 4.3 Documenting Hate (2017–2019)
Project: https://projects.propublica.org/graphics/hatecrimes; partners: https://projects.propublica.org/graphics/hatecrimes-partners; retrospectives §1.12.
- **Evidence class:** a national incident-level hate/bias-incident database, built because official statistics are structurally broken (voluntary FBI UCR reporting). 6,000+ victim/witness submissions; 180+ partner newsrooms; 230+ stories; plus the ML-driven Documenting Hate News Index.
- **Credibility mechanism:** partner access gated by agreement (form at projects.propublica.org/graphics/hatecrimes-partnerform); student/reporter verifiers trained by First Draft; every tip verified in Check before journalistic use; tips treated as leads, not publishable facts.

### 4.4 Lost Mothers (2017)
See §3.5. Evidence class: a named cohort of U.S. maternal deaths (plus ~4,000 near-misses) that no agency could produce — the CDC counts deaths but cannot release identities. Verification chain (social-media discovery → obituary/public-record confirmation → family contact) made a crowd-assembled death registry citable.

### 4.5 Free-standing tip infrastructure
https://www.propublica.org/tips
- Channels: end-to-end-encrypted web form; Signal (917-512-0201); postal mail; SecureDrop over Tor. Earlier: "How to Send Us Files More Securely" (2014, https://www.propublica.org/nerds/how-to-send-us-files-more-securely); Tor onion mirror of the site (2016, https://www.propublica.org/nerds/a-more-secure-and-anonymous-propublica-using-tor-hidden-services).
- Standard for a good tip (their words): specifics over guesswork; evidence "that isn't already known"; documents/receipts; powerful actors causing "significant harm."
- Handling: all submissions reviewed, promising ones flagged; "You may hear from us days, weeks, months or even years after you initially reached out."

### 4.6 Structured-callout tooling
- Callouts run on **Screendoor** forms; shared with partners through **Collaborate/django-collaborative** (assignment, contact logging, auto-redaction, live Screendoor/Google Sheets sync) — https://github.com/propublica/django-collaborative; manual https://propublica.gitbook.io/collaborate-user-manual; playbook https://propublica.gitbook.io/collaborative/introduction.
- Engagement reporting as a story-finding discipline: https://www.niemanlab.org/2020/03/how-engagement-reporting-is-helping-propublica-journalists-find-their-next-big-story/; https://gijn.org/2017/10/25/how-they-did-it-propublicas-engagement-journalism/

### 4.7 Local Reporting Network (2018–)
https://www.propublica.org/article/local-investigative-journalism-growth; 2026 round: https://www.propublica.org/atpropublica/propublica-opens-applications-for-new-local-reporting-network-partnerships-in-2026
- Model: ProPublica reimburses a local newsroom for one reporter's salary (up to $80,000 + benefits stipend) for a year-long investigation with "local urgency and national resonance," pairing the reporter with ProPublica editors, data, research, and news-apps staff. ~100 projects since 2018; expanding via a 50-state initiative; 2026 = three cohorts of five partnerships.
- **Evidence class:** deep local/state records and sourcing that national FOIA strategies never reach, produced at national methodological standard — the network converts ProPublica's methodology infrastructure into a distributed acquisition system **[inferred]**.

---

## 5. Verification & Standards Doctrine

### 5.1 The "no surprises" rule
- Codified in the Code of Ethics (https://www.propublica.org/code-of-ethics): "Whenever we portray someone in a negative light, we should make a real effort to obtain a response from that person. We should give them a reasonable amount of time to get back to us before we publish."
- In practice: the **no-surprises letter** — critical assertions put to the subject in writing, in bullet form, with an interview offer and response deadline (practitioner writeup: https://gijn.org/stories/seeking-comment-for-your-investigation-tips-for-the-no-surprises-letter/).
- Named exemplars:
  - **U.S. Century Bank** — ProPublica published its own pre-publication questions after the bank characterized them as an agenda: https://www.propublica.org/article/what-we-asked-u-s-century
  - **Justice Alito** — the subject answered ProPublica's detailed pre-publication questions via a WSJ op-ed *before the story ran*, proof of the letters' existence and specificity: https://www.propublica.org/article/behind-scenes-alito-wall-street-journal-prebuttal-editorial
  - **Providence hospital chain** — "more than 100 pages" of evidence discussion exchanged with the subject's PR over ~two months pre-publication; accounting published when the subject later cried foul: https://www.propublica.org/article/a-hospital-chain-said-our-article-was-inaccurate-its-not
  - **At data scale** — Sacrifice Zones extended no-surprises to data subjects: 193 of the top 200 emitting facilities contacted; 29% of responders' error flags fixed pre-publication (§3.3).
- Framing dimension: the response opportunity covers "not only … specific facts but also … how the story is framed" (https://www.propublica.org/article/ask-ppil-on-bias-in-journalism).

### 5.2 Document authentication
- Cryptographic email verification via DKIM/ARC (Kasowitz): https://www.propublica.org/nerds/authenticating-email-using-dkim-and-arc-or-how-we-analyzed-the-kasowitz-emails
- Leak authentication by subject contact + regulatory cross-reference (IRS Files, §3.7).

### 5.3 AI use policy
https://www.propublica.org/article/using-ai-responsibly-for-reporting — AI for analysis/lead-generation only, never writing ("Our journalists write our stories, our newsletters, our headlines and the takeaways"); models instructed "not to guess if it wasn't sure"; every AI-assisted detail human-confirmed pre-publication; dual-reporter review of each classification (Utah misconduct analysis); self-hosted models for sensitive material (Uvalde evidence transcription).

### 5.4 Statistical review infrastructure
- Four standing academic advisers (biostatistics/epidemiology — Miguel Hernán; learning analytics — Charles Lang; quantitative ecology — Heather Lynch; economics — M. Marit Rehavi) named in 2017 to "help us develop methodologies … and be another set of eyes on the white papers we write": https://www.propublica.org/nerds/introducing-our-data-journalism-advisers
- White-paper practice with physician panels and published expert commentary (Surgeon Scorecard, §3.2; https://www.propublica.org/article/surgeon-level-risk-quotes), plus on-the-record engagement with the RAND critique.
- Replication-grade releases (COMPAS GitHub; toxmap data) that deliberately expose the work to academic audit.

### 5.5 Corrections
- Policy: "When mistakes are made, they need to be corrected — fully, quickly and ungrudgingly" (https://www.propublica.org/code-of-ethics).
- Practice: standing corrections page, reverse-chronological, standardized format ("Correction, [date]: This story originally [error]. [Fix].") with dedicated intake address: https://www.propublica.org/corrections
- Related integrity rules: no fabrication/composites, no plagiarism, no paying for interviews, no misidentification to sources; anonymity restricted to vital information with no alternative route and a reliable source (Code of Ethics).

---

# SYNTHESIS

## Evidence-Source Taxonomy (bottom-up, 14 categories)

| # | Category | Definition | Examples | Access | Frequency |
|---|----------|-----------|----------|--------|-----------|
| 1 | Administrative claims & payment microdata | Row-level government payment/claims records identifying providers/recipients | Medicare Part B/D (Prescriber Checkup), inpatient claims (Surgeon Scorecard), House expenditures | FOIA / agreement / purchase | **Dominant** |
| 2 | Regulatory inspection & enforcement records | Inspection findings, deficiencies, penalties from oversight agencies | Nursing Home Compare, ER inspections, FSIS salmonella tests | Open bulk / FOIA | **Dominant** |
| 3 | Mandated disclosure filings | Self-reports the law forces private actors to file | FEC/lobbying, IRS 990s (Nonprofit Explorer), FCC political files, pharma disclosures | Open but often hostile-format | **Dominant** |
| 4 | Court & docket records | Filings, dockets, outcomes | N. Illinois gun cases (PACER), bankruptcy 2008–2015, debt-collection suits | Semi-open (fees, per-court) | Common |
| 5 | Law-enforcement/agency internal databases | Operational databases never designed for release | Chicago/Cook County gang DBs, CCRB complaints, ICE arrests, air-marshal misconduct | FOIA, sometimes litigation | Common |
| 6 | Government models & geospatial risk products | Agencies' own analytic models run/republished at full resolution | EPA RSEI (Toxmap), FEMA flood maps | Open but obscure; expertise-gated | Occasional, high-impact |
| 7 | Algorithmic outputs obtained for audit | Scores/decisions of a proprietary system, obtained to test it | COMPAS scores via FOIA; Message Machine email variants | FOIA + construction | Occasional, flagship |
| 8 | Leaked / whistleblower datasets | Non-public records from insiders | Secret IRS Files, Kasowitz emails, CBP audio | Leak (SecureDrop/Signal infra) | Occasional, flagship |
| 9 | Crowd-constructed cohorts & incident registries | Structured datasets assembled from public callouts | Lost Mothers, Documenting Hate, Electionland feed | Constructed (callout + verification) | Common, differentiating |
| 10 | Crowd-transcribed document corpora | Unstructured official documents converted to data by volunteers | Free the Files ad-buy data | Constructed (open docs + crowd) | Occasional |
| 11 | Scraped commercial/web data | Data harvested from companies' own public interfaces | Dollars for Docs disclosures, Amazon pricing | Constructed (scraping) | Common |
| 12 | Purchased commercial datasets | Industry data bought from vendors | Quadrant insurance quotes, S&P rate filings, Moody's modeling | Purchase | Occasional |
| 13 | Personnel directories & employment artifacts | Staff directories, LinkedIn, license rosters diffed/linked over time | HHS directory workforce tracker; license-board recipe (https://www.propublica.org/nerds/reporting-recipe-how-to-investigate-health-professionals) | Open-ish, ephemeral — must be archived | Emerging/occasional |
| 14 | Adopted orphan datasets & APIs | Civic data assets rescued when their steward dies | Sunlight Congress API takeover; EveryBlock-era archiving ethos (https://www.propublica.org/nerds/rip-everyblock) | Adoption/stewardship | Occasional |

(Frequency ratings are portfolio-level judgment from §§1–4 — **[inferred]**.)

## Acquisition Playbooks (8)

1. **Bulk-FOIA the administrative dataset behind the individual harm story.** *Trigger:* an anecdote implies a population-level pattern. *Steps:* identify the administrative system recording every such case; request row-level with identifiers; measure linkage error; compute rates against a defended denominator. *Exemplars:* COMPAS, temp-worker injury rates, Chicago tickets. *Failure modes:* aggregates-only release; stripped identifiers killing linkage; no denominator, so honest rates are impossible.

2. **Run the regulator's own unused model at full resolution and publish the map.** *Trigger:* an agency maintains a screening model it never operationalizes for the public. *Steps:* obtain full-resolution output; average across years; adopt the agency's own risk thresholds; validate with former insiders; contact affected parties pre-publication. *Exemplars:* Toxmap (RSEI), FEMA risk maps. *Failure modes:* screening models aren't measurement — must label estimates and state bias direction; agency disowns its own model under scrutiny.

3. **Structured callout to assemble the cohort the agency won't or can't name.** *Trigger:* official statistics count a harm but cannot identify cases. *Steps:* Screendoor-class questionnaire; distribution partners chosen for demographic reach; verify each entry against public records or First Draft-style protocols in Check/Collaborate; measure and publish who is missing from the sample; treat tips as leads, not facts. *Exemplars:* Lost Mothers, Documenting Hate, Electionland. *Failure modes:* self-selection presented as prevalence; undetected demographic skew; verification backlog collapsing trust.

4. **Crowd-transcribe the disclosure regime that exists on paper but not as data.** *Trigger:* a transparency law forces publication in non-machine-readable form. *Steps:* harvest all documents; single-task transcription UI (casino-driven design); multi-volunteer agreement per record; publish dataset + API. *Exemplars:* Free the Files, Dollars for Docs. *Failure modes:* volunteer attention decays post-news-peak; format churn; without agreement thresholds crowd error poisons the asset.

5. **Audit the algorithm with its adversary's own protocol.** *Trigger:* a consequential score/price/decision comes from a proprietary system. *Steps:* obtain outputs (FOIA, volunteer panel, purchased quotes); replicate the vendor's/agency's own validation methodology so the yardstick is not disputable; publish definitions, error rates, code, data. *Exemplars:* COMPAS (Northpointe's own definitions/model), car insurance (industry's own quote engines), Message Machine. *Failure modes:* vendor disputes the outcome definition anyway; matching error inflating disparities — measure on a sample and disclose.

6. **Diff the live directory to measure what the institution refuses to report.** *Trigger:* an organization declines to quantify a change (layoffs, purges). *Steps:* archive a public roster on a cadence; diff snapshots; classify entries (AI-assisted, human-double-reviewed); spot-check via LinkedIn/interviews; enumerate exclusions and alternative explanations. *Exemplar:* HHS workforce tracker. *Failure modes:* update lag misread as events; duplicate identities; irregular sub-org updates (their CMS exclusion) — exclude and say so.

7. **Adopt the orphaned civic dataset and become its steward.** *Trigger:* a transparency project dies and its data/API would vanish. *Steps:* take custody; keep the interface stable; fold maintenance into standing products; archive predecessors' outputs. *Exemplars:* Sunlight Congress API takeover; EveryBlock archiving post. *Failure modes:* unfunded stewardship decays silently — the Data Store's frozen-archive banner is the honest end-state; adopting without a sunset plan misleads downstream users.

8. **Convert investigation exhaust into standing public infrastructure.** *Trigger:* a story required building a cleaned dataset or tool others would reuse. *Steps:* publish the dataset (Data Store), the API (Nonprofit Explorer, FEC Itemizer), the tool (Upton, Transcribable, Collaborate, TimelineSetter), and the recipe (reporting recipes; free Data Institute materials, https://www.propublica.org/nerds/announcing-free-videos-and-training-materials-from-the-propublica-data-institute); nominal journalist pricing where warranted ($200 premium tier). *Failure modes:* maintenance debt; pricing suppressing exactly the reuse that generates impact.

## Provenance Checklist (10 points)

Before an autonomous agent promotes a data-derived finding:

1. **Source + vintage stated** — originating system/agency, years covered, retrieval date, for every dataset.
2. **Acquisition mode recorded** — open / FOIA / purchase / leak / scraped / crowd-constructed, with terms; leaks additionally require independent authentication (subject contact, cryptographic checks, regulatory cross-reference).
3. **Population and denominator defended** — what universe the claim covers and what the rate divides by.
4. **Exclusions enumerated with counts and reasons** — and re-checked for whether they could reverse the finding.
5. **Definitions borrowed from the audited party's own standard** where one exists, so the yardstick is not disputable.
6. **Linkage/classification error measured on a sample and disclosed** (COMPAS's 3.75% on n=400 is the benchmark disclosure).
7. **Model choices and bias direction disclosed** ("underestimates because…"; shrinkage; weak fits conceded).
8. **Independent expert eyes before publication** — domain reviewers or standing methodological advisers; a white paper for anything scoring individuals.
9. **Subject response sought — no surprises** — specific assertions in writing with a deadline; at data scale, contact the highest-exposure subjects and incorporate corrections pre-publication.
10. **Replication artifact + correction path** — data/code released where possible (or the refusal explained); a standing, dated, standardized corrections mechanism ("fully, quickly and ungrudgingly").

---

## Cross-walk: what Ithildin can copy cheapest **[inferred]**

- The **no-surprises letter** and the **10-point checklist** map directly onto findings-tracker discipline (claim-type/confidence caps already exist; subject-response and denominator fields do not).
- The **Data Store frozen-archive banner** is the honest pattern for regenerable sidecars: label vintage, stop implying freshness.
- **Directory-diffing (playbook 6)** and **orphan-dataset adoption (playbook 7)** are immediately actionable with existing tooling (Wayback + ingest pipelines).
- The one capability we structurally lack is a **verified crowd** (playbooks 3–4). Everything else in this report is replicable by an agent platform; the callout machinery is the human moat.
