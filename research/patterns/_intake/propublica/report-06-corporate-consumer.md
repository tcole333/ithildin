# ProPublica Evidence Ontology — Cluster 06: Corporate Accountability, Consumer Finance & Debt

Reviewed: 2026-07-28. Method: live-site verification via web search + direct fetches of propublica.org articles and methodology pages. Scope: ProPublica originals and formal co-publications only.

**Attribution verification results (candidate-list corrections):**
- **DROPPED — Hurricane Sandy altered engineering reports (2014-15):** NOT ProPublica. That investigation belongs to NPR (Laura Sullivan) with PBS Frontline ("The Business of Disaster") and, separately, CBS 60 Minutes ("The Storm After the Storm," March 2015). FEMA reopened all ~144K Sandy claims and paid ~$240M more. The litigation-discovery-mining lesson (altered draft vs. final engineering reports surfaced in federal court exhibits) is real but not ProPublica's — noted for the cross-outlet pattern library only.
- **DROPPED — Roof/hail insurance claim underpayment (2023-24):** No ProPublica original found. The recent hail-claims-suppression reporting (State Farm) is NPR, April 2026.
- **DROPPED — Conservatorship/guardianship extraction:** Not verified as ProPublica; the marquee guardianship exposés are The New Yorker's (Rachel Aviv) and local outlets'.
- **DROPPED — Sears/Lampert, Boeing:** Not ProPublica originals (Boeing 737 MAX = Seattle Times/NYT).
- **CORRECTED — Private equity ER staffing:** The surprise-billing/balance-billing research on Envision/EmCare and TeamHealth is Yale health economists' work, popularized by NYT; the unmasking of the "Doctor Patient Unity" dark-money ad group was NYT (Sept. 2019). ProPublica's own original is the April 2020 pay-cuts-vs-ad-spending story — included below with the boundary drawn.
- **Trump, Inc. episode-level caution:** Only the inaugural-overpayment thread and the two-books story were verified as ProPublica/WNYC originals this session. Panama and Baku episode material substantially builds on Reuters/NBC/Global Witness and New Yorker primaries [inferred]; treat episode-level claims from those threads as aggregation-risk and verify before reuse.

---

### The TurboTax Trap I: dark-pattern steering + hiding Free File from search engines (2019) — Intuit engineered its own web assets so eligible taxpayers could not find the free product it was obligated to offer
- **URL**: https://www.propublica.org/article/turbotax-just-tricked-you-into-paying-to-file-your-taxes (April 22, 2019); https://www.propublica.org/article/turbotax-deliberately-hides-its-free-file-page-from-search-engines (April 26, 2019); series: https://www.propublica.org/series/the-turbotax-trap
- **Partner/awards**: ProPublica original (Justin Elliott, Lucas Waldron). Series won a Gerald Loeb Award.
- **What they found**:
  - Walking through the product as test users, ProPublica showed TurboTax charged people who qualified for free filing: a TaskRabbit house cleaner earning $29,000 was charged $119.99; a Walgreens cashier without insurance, $59.99. Key line: "Even though TurboTax could tell we were eligible to file for free, the company never told us about the truly free version."
  - Users who clicked "FREE Guaranteed" ads were internally tagged "NONFFA" (Non Free File Alliance) and routed to paid SKUs; deliberately confusable product names ("Free Edition" — not actually free for most — vs. the truly free "Free File Program"/"Freedom Edition").
  - The truly free Free File landing page carried `noindex,nofollow` directives (robots.txt + HTML meta) while paid pages carried `index,follow` — i.e., Intuit actively de-listed its free product from Google. H&R Block did the same on its Free File page.
  - After publication Intuit removed the code (April 28, 2019); Rep. Katie Porter requested IRS and FTC investigations (April 29, 2019).
- **Finding type(s)**: dark-pattern/consumer-deception; **public-benefit-interception** (new tag: profiting by standing between eligible people and a free public alternative); fraud-enablement-by-design.
- **Evidence & sources**:
  - [constructed] Product walkthroughs with synthetic taxpayer personas (mystery shopping the filing flow end-to-end).
  - [open-public] The company's own web assets: robots.txt, HTML meta tags, URL/analytics tagging variables (NONFFA), ad landing pages.
  - [crowdsourced] Technical tips: the noindex code was flagged to ProPublica by named readers (Larissa Williams via Twitter, Arkadiy Kulev via Reddit) after the first story.
  - [open-public] IRS Free File Alliance program rules (the eligibility baseline the deception is measured against).
- **Access tier**: open-public + constructed (the whole case is buildable from the subject's public website plus a test persona; no privileged access).
- **Acquisition path**: scrape/inspection of subject web assets + constructed walkthrough + crowdsourced technical tips.
- **Detection signature**: **site-forensics + mystery-shopper-walkthrough.** (1) Subject's own page code (robots.txt/meta robots) compared across its free-obligation page vs. revenue pages revealed asymmetric `noindex,nofollow` vs `index,follow` — machine-checkable intent evidence. (2) A synthetic user matching the program's eligibility criteria run through the product flow, with every screen recorded, revealed that eligibility-known users were steered to paid products (NONFFA tagging = the smoking-gun variable name in their own code).
- **Corroboration structure**: The walkthrough (behavior) + the code (intent) + the program rules (obligation) close the triangle; replicated on a second company (H&R Block) to show industry practice; later externally confirmed by an IRS-funded MITRE review and ultimately by FTC adjudication.
- **Methodology notes**: Methodology is stated inside the articles themselves (test personas described step-by-step with screenshots; code quoted). [inferred: the articles serve as the methods doc].
- **Impact**: $141M 50-state+DC AG settlement, ~4.4M consumers, TY2016-18; FTC final opinion/order that Intuit engaged in deceptive advertising, banning unqualified "free" claims (Jan. 2024); Intuit quit the IRS Free File program (July 2021); IRS renegotiated Free File terms and later built Direct File [inferred downstream].
- **Generalization**: Any regulated entity with a mandated free/disclosure obligation hosted on its own infrastructure: insurers' provider directories and SBC disclosures, banks' fee schedules, telecoms' broadband labels, airlines' refund pages, drug-price transparency files, hospital chargemaster/price-transparency JSON. Generic detector: diff robots.txt/meta-robots/sitemaps between the subject's obligation pages and its revenue pages (Wayback lets you do this historically); walk the consumer flow with an eligibility-matching persona and log where eligibility-known users land; grep site JS/analytics for segmentation variable names that encode the steering.

### The TurboTax Trap II: Inside Intuit's 20-year lobbying war on free government filing (2019) — regulatory capture documented from the company's own internal strategy documents
- **URL**: https://www.propublica.org/article/inside-turbotax-20-year-fight-to-stop-americans-from-filing-their-taxes-for-free (Oct. 17, 2019; Justin Elliott and Paul Kiel)
- **Partner/awards**: ProPublica original; part of the Loeb-winning series.
- **What they found**:
  - Internal 2007 Intuit board presentation on government-filing proposals: "All were stopped." A 2014-15 internal "encroachment strategy" document planned to "manufacture 3rd-party grass roots support" and "buy ads for op-eds/editorials/stories in African American and Latino media."
  - Astroturf money trail: $70,000 to Women Impacting Public Policy; payments to the Latino Coalition and National Black Chamber of Commerce, which then signed pro-Free File letters to Congress.
  - Revolving door: Bernie McKay hired 1998 to run the anti-government-filing effort; the IRS's own top Free File negotiator, Dave Williams, became Intuit's chief tax officer (2013).
  - Stakes quantified: ~15M paying TurboTax customers eligible to file free ≈ $1.5B revenue, "more than half" of TurboTax's total; $800M Intuit ad spend (2019) vs. the IRS's $2M/year Free File promotion budget.
- **Finding type(s)**: regulatory-capture/lobbying-to-preserve-rents; dark-pattern/consumer-deception; public-benefit-interception.
- **Evidence & sources**:
  - [privileged] Internal Intuit documents (board presentation, encroachment-strategy deck, marketing/call-analysis PowerPoints), published via DocumentCloud embeds.
  - [request-gated] FOIA for IRS–Intuit communications; ProPublica sued the IRS (Aug. 2019) over 100+ withheld pages.
  - [litigation-records] Sworn testimony of TaxAct CEO Lance Dunn from 2011 antitrust proceedings — pre-existing litigation mined for competitor's-eye evidence.
  - [interviews] Former IRS commissioner (Rossotti), former IRS e-file head, OMB e-gov director, former H&R Block CEO, three former Intuit designers/developers/marketers.
  - [open-public] Lobbying disclosures; the DOJ antitrust letter to the IRS; IRS Advisory Council report criticizing Free File oversight.
- **Access tier**: mixed — privileged (leaked internal decks) + request-gated (FOIA + FOIA litigation) + open-public (lobbying records) + litigation-records.
- **Acquisition path**: leak + FOIA + litigation-records + interviews.
- **Detection signature**: **internal-rulebook-acquisition + temporal-correlation.** The internal strategy documents named the objective and the method (manufactured grassroots); joining lobbying/astroturf payments to the timeline of every federal free-filing proposal showed each proposal die shortly after coordinated opposition ("All were stopped" is the company grading its own detector output). Revolving-door mapping (IRS Free File negotiator → Intuit officer) supplied the capture mechanism.
- **Corroboration structure**: Internal documents (intent) corroborated by public lobbying filings and grant recipients' congressional letters (execution) and by outcome history (no IRS filing product for 20 years); adversarial interviews with ex-IRS and competitor executives; FOIA suit to force the government side of the correspondence.
- **Generalization**: Any incumbent whose revenue is a government inefficiency: tax prep, PBMs vs. drug-price reform, title insurers vs. e-recording, payroll processors vs. state-run portals, credit bureaus vs. public credit registries. Generic detector: for a policy that repeatedly dies, build the event timeline of proposals and join (a) lobbying disclosures, (b) 990 grants from the incumbent's foundation/trade group to letter-signing nonprofits, (c) revolving-door employment records between regulator negotiating team and incumbent. Astroturf tell: minority-outreach or small-business coalitions signing identical letters within days of an industry payment.

### Unseen Toll: Wages of Millions Seized to Pay Past Debts (2014) — first national numbers on consumer-debt wage garnishment, produced by getting the payroll processor to run the analysis
- **URL**: https://www.propublica.org/article/unseen-toll-wages-of-millions-seized-to-pay-past-debts (Sept. 15, 2014; Paul Kiel)
- **Partner/awards**: Co-published/co-reported with NPR.
- **What they found**:
  - At ProPublica's request, ADP — the largest U.S. payroll processor — analyzed 2013 payroll records for 13 million employees: ~4 million U.S. workers (~3%) had wages garnished for consumer debt in 2013; more than 1 in 10 employees aged 35-44 had some garnishment.
  - Among workers earning $25,000-$40,000, ~5% were garnished for consumer debt nationally — over 6% ("one in 16") in the Midwest.
  - Court-records layer: filings from eight states, incl. Missouri data across 24 circuit courts; an anonymous major retailer (~250K employees) provided its own payroll numbers.
- **Finding type(s)**: extraction-from-captive-population (paycheck as the collection chokepoint); disparate-impact-by-race-or-geography (regional skew).
- **Evidence & sources**:
  - [commercial-data, constructed] ADP aggregate study commissioned by the newsroom — data the government does not collect at all.
  - [open-public] State court records (8 states; Missouri 24 circuits).
  - [privileged] One large employer's internal payroll figures (granted anonymity).
  - [interviews] Debtors, creditors' attorneys, payroll professionals.
- **Access tier**: mixed — constructed (custodian-run analysis of otherwise inaccessible microdata) + open-public (dockets) + privileged (employer figures).
- **Acquisition path**: commercial-data (custodian partnership) + bulk-public-data + interviews.
- **Detection signature**: **third-party-data-custodian-query** (new tag): when the phenomenon's denominator exists only inside a private data custodian (payroll processor, clearinghouse, claims processor), persuade the custodian to run and publish an aggregate analysis to the newsroom's specification — then anchor it with docket-level case records. The headline finding is literally "a rate nobody had ever computed because nobody had the denominator."
- **Corroboration structure**: ADP aggregates (national rates) cross-checked against independent state-court garnishment filings (case-level mechanics) and one employer's internal numbers; anecdotes selected from dockets, not from the custodian's data.
- **Methodology notes**: The custodian arrangement is stated in-article. The approach was subsequently adopted by academic economists (NBER WP 30724 uses ADP data) — evidence the constructed denominator became canonical.
- **Generalization**: Whenever an extraction practice is administered through a concentrated private intermediary — payroll processors (garnishment), health clearinghouses (claim denials), core banking processors (NSF/overdraft), property managers' software (evictions; see RealPage) — the intermediary holds the only true denominator. Agent move: identify the chokepoint firm, request/negotiate an aggregate cut, and pre-specify the rate definitions; flag as a human-action lead when a data partnership is required.

### The Color of Debt (2015) — collection judgments hit majority-Black neighborhoods at twice the rate of white ones at the same income
- **URL**: https://www.propublica.org/article/debt-collection-lawsuits-squeeze-black-neighborhoods (Oct. 8, 2015; Paul Kiel, Annie Waldman). Methodology: https://www.propublica.org/article/how-we-analyzed-racial-disparity-in-debt-collection-lawsuits
- **Partner/awards**: ProPublica original (radio segment with Marketplace). National Press Club award; NABJ finalist.
- **What they found**:
  - Five years of court judgments in three metros — St. Louis 47,401 judgments, Chicago (Cook County) 81,923, Newark (Essex County) 54,903 (2008-2012) — mapped to census tracts: judgment rates in majority-Black tracts ran about **2x majority-white tracts, holding income constant**.
  - In Jennings, Mo. (~90% Black St. Louis suburb), roughly one-third of residents had been sued over a debt — including the mayor and five of eight council members.
  - Disparities were largest for debt buyers and high-cost/subprime auto lenders; plaintiffs included hospitals, utilities, and payday/installment lenders.
  - Follow-up "So Sue Them" (May 2016): debt buyers accounted for 42% of collection suits in some Missouri counties (2013); Encore Capital collected $1.2B from consumers in 2015, more than half through courts; also documented "sewer service" producing default judgments.
- **Finding type(s)**: disparate-impact-by-race-or-geography; **courts-as-profit-center** (new tag: civil judiciary functioning as a subsidized collection department for volume plaintiffs); extraction-from-captive-population.
- **Evidence & sources**:
  - [open-public, bulk] Court judgment records from three county-level court systems, five-year windows, restricted to cases ending in judgment (the enforceable event enabling garnishment).
  - [open-public] Census tract demographics (race, median household income) — the join layer.
  - [constructed] A statistical white paper with regression holding income constant; methodology reviewed by academics.
  - [interviews] Defendants located through dockets; collection-industry attorneys.
- **Access tier**: open-public (bulk dockets + census), constructed (the analytic layer is the product).
- **Acquisition path**: bulk-public-data (court records acquisition per county) + interviews.
- **Detection signature**: **denominator-construction + geocoded-disparity-join.** Bulk judgment records geocoded to census tracts, joined to tract race/income, converted to per-capita judgment RATES, then income-stratified regression: "the risk of judgment... was about twice as high in majority black census tracts as majority white census tracts, holding income constant." Race is never in the court record — residence is the proxy layer, which is exactly what makes the method reproducible anywhere. Secondary signature: **plaintiff-frequency-inversion** — re-sorting the same dockets by plaintiff to rank the top filers.
- **Corroboration structure**: Three independent metros run through the identical pipeline (replication built into the design); income control to pre-empt the "it's just poverty" rebuttal; academic review of the white paper; ground-truthing by door-knocking sued households in the highest-rate tracts.
- **Methodology notes**: Stated, unusually fully: dedicated methods article + white paper. This is the cluster's gold standard for published methodology.
- **Impact**: Missouri AG pushed debt-collection court reforms citing the race gap; fed the CFPB-era debate on debt-buyer litigation practices [inferred].
- **Generalization**: The denominator pipeline transfers to ANY case type with defendant addresses: evictions, foreclosures, license suspensions, civil forfeiture, hospital suits, tax liens, towing/impound. Platform mapping: CourtListener/state-court tools already return party+address; census join is trivial. Generic detector: (1) per-tract case rates vs. tract demographics with income stratification; (2) top-N plaintiff ranking per court — any single plaintiff filing thousands of cases in one county is a story candidate regardless of demographics.

### The nonprofit hospital debt machine: Heartland/Mosaic → Methodist Le Bonheur (2014-2019) — charities running captive collection agencies that sue and garnish their own patients (and employees)
- **URL**: https://www.propublica.org/article/how-nonprofit-hospitals-are-seizing-patients-wages (Dec. 19, 2014; Paul Kiel + NPR); Methodist series via MLK50 (2019, Wendi C. Thomas, LRN)
- **Partner/awards**: NPR (2014); MLK50 via ProPublica Local Reporting Network (2019) — "Profiting from the Poor" won the Selden Ring Award.
- **What they found**:
  - Heartland Regional Medical Center (renamed Mosaic Life Care), St. Joseph, Mo.: its wholly owned for-profit collector, Northwest Financial Services, sued 11,000+ patients (2009-2013) and garnished ~6,000 people for ~$12M — while the nonprofit hospital booked a $45M profit (2013).
  - Methodist Le Bonheur (Memphis): 8,300+ suits in Shelby County 2014-2018 — more than every creditor but one — including suits against its own low-wage employees; example: Carrie Barrett ($9.05/hr at Kroger), sued over a $12,000 bill that grew past $33,000 with interest and fees.
  - Both systems enjoyed tax exemption while running the most aggressive collection dockets in their counties.
- **Finding type(s)**: **nonprofit-mission-inversion** (new tag: tax-exempt charity operating a for-profit extraction arm against its beneficiary class); self-dealing/related-party (hospital-owned collection agency); courts-as-profit-center; extraction-from-captive-population.
- **Evidence & sources**:
  - [open-public, bulk] County court dockets (Buchanan County garnishments; Shelby County General Sessions — five years, aggregated by plaintiff).
  - [open-public] IRS Form 990s and state financial reports (nonprofit profits, executive comp, the captive-collector relationship, charity-care policies).
  - [crowdsourced] Public callouts for sued patients.
  - [interviews] Defendants found via dockets; hospital officials; courtroom observation.
- **Access tier**: open-public (dockets + 990s) + constructed (crowdsourced case pool).
- **Acquisition path**: bulk-public-data + crowdsourced + interviews.
- **Detection signature**: **plaintiff-frequency-inversion joined to 990 status.** Aggregate the county civil docket by plaintiff; rank; flag any 501(c)(3) in the top filers; then join the hospital's 990 (charity-care policy, profitability, ownership of the collection entity, executive pay) against its docket behavior. The Heartland variant adds a related-party hop: the top-filing "financial services" plaintiff resolved, via registry/990 disclosures, to a subsidiary OF the hospital. The Methodist variant adds the employer-employee join: garnishment answers name the employer, showing the hospital garnishing its own staff.
- **Corroboration structure**: Docket counts (behavior) x 990/financials (means and mission) x named-defendant case studies (harm), with the subject's own charity-care policy as the standard it violates; Senate follow-through (Grassley letters) functioned as adversarial verification.
- **Impact**: Mosaic overhauled financial assistance and forgave thousands of debts; IRS 501(r) billing/collection rules took effect amid the coverage; Methodist suspended suits within days, erased at least $11.9M in debt, expanded assistance from 125% to 250% of poverty, raised its minimum wage $10.08 → $15, stopped suing employees.
- **Generalization**: Every 501(c)(3) with customer relationships: hospitals, universities (tuition suits), nonprofit utilities, credit unions, housing nonprofits. Generic detector: top-plaintiff docket ranking ∩ IRS exempt-org list; then 990 Schedule R related-party scan for captive collection/servicing subsidiaries; garnishment answers to map defendant employers (self-garnishment tell).

### When Medical Debt Collectors Decide Who Gets Arrested (2019) — Coffeyville, Kansas: contempt process converts medical debt into jail, with bail money routed to the collector
- **URL**: https://features.propublica.org/medical-debt/when-medical-debt-collectors-decide-who-gets-arrested-coffeyville-kansas (Oct. 16, 2019; Lizzie Presser)
- **Partner/awards**: ProPublica original. Nieman Storyboard methods interview exists.
- **What they found**:
  - In Coffeyville (pop. ~9,000, poverty 2x national), collection attorney Michael Hassenplug ran quarterly "debtor's exams": debtors summoned every three months to swear they are too poor to pay; miss two and the judge issues contempt, an arrest warrant, and $500 bail — with bail applied to the debt, of which the collector takes his one-third contingency fee.
  - Presiding magistrate judge David Casement is a cattle rancher who never studied law; on one docket day 90 people were summoned.
  - Presser tallied 11 arrests and 30+ warrants over medical debt in the prior year; one man jailed over an $818 bill; a woman four months pregnant arrested over $230.
- **Finding type(s)**: courts-as-profit-center (its purest form: bail as collection revenue); extraction-from-captive-population; **debt-criminalization** (new tag: civil debt converted to custodial coercion via contempt).
- **Evidence & sources**:
  - [open-public] Local court dockets: judgments, debtor's-exam summonses, contempt citations, bench warrants, bail receipts — the procedural artifacts ARE the finding.
  - [field-observation] Courtroom attendance at exam days.
  - [interviews] Debtors, the collector, the judge, provider plaintiffs.
- **Access tier**: open-public + constructed (fieldwork); nothing privileged.
- **Acquisition path**: bulk-public-data (small-court dockets) + field-observation + interviews.
- **Detection signature**: **procedural-artifact-forensics** (new tag): instead of counting cases, parse the PROCEDURE attached to them — recurring civil-contempt citations, bench warrants, and cash-bail entries on consumer-debt dockets are a machine-detectable anomaly (warrant/bail records joined to underlying civil case type = "debtors' prison" flag). Presser's stated method was hypothesis-first: hunt the intersection of two known mechanisms — broad contempt powers x medical-debt collection — then venue-shop dockets for where both fire maximally.
- **Corroboration structure**: Docket paper trail (warrants, bail amounts, fee splits) + in-room observation of the exam ritual + on-record interviews with the system's beneficiaries (collector, judge) confirming the mechanics themselves.
- **Generalization**: Any jurisdiction pairing civil judgments with contempt enforcement: rent debt, fines-and-fees, child support, HOA liens, payday judgments. Generic detector: join warrant/booking/bail data to civil case numbers; any nonzero count of custodial events with civil-collection origins is reportable. Also profile the enforcement personnel: single repeat creditor's-attorney + lay judge + standing quarterly docket = the capture pattern.

### Debt Inc. / The 182 Percent Loan + The Payday Playbook (2013) — installment lenders' loan-flipping and credit-insurance packing, and the statehouse machinery that keeps triple-digit rates legal
- **URL**: https://www.propublica.org/article/installment-loans-world-finance (May 13, 2013; Paul Kiel); lobbying piece: https://www.propublica.org/article/how-high-cost-lenders-fight-to-stay-legal (Aug. 2013); series: https://www.propublica.org/series/debt-inc
- **Partner/awards**: Co-reported with Marketplace; Payday Playbook co-published with the St. Louis Post-Dispatch.
- **What they found**:
  - World Finance (World Acceptance Corp., Nasdaq-listed): ~75% of loans are renewals — serial "flipping" restarts front-loaded charges; borrower Katrina Sutton's $207 loan carried a stated 90% APR that was effectively 182% once packed credit-insurance premiums ($76 on $207) were counted; borrower Emma Johnson, 71, renewed two loans 20+ times each, paying $21,000+ at effective rates reaching 800%+.
  - ProPublica "examined more than 100 of the company's loans in 10 states" and obtained FTC consumer complaints about World and peers via FOIA; five-plus former employees described renewal quotas and insurance packing as trained practice.
  - Payday Playbook (Missouri): payday lenders spent $371,000 on lawmakers/committees in the 2010 cycle; the chair of the House Financial Institutions Committee, Rep. Don Wells, owned a payday store (Kwik Kash); the industry derailed a 36%-cap ballot initiative.
- **Finding type(s)**: extraction-from-captive-population (renewal treadmill); fraud-enablement-by-design (insurance packing to evade rate caps); regulatory-capture/lobbying-to-preserve-rents; dark-pattern/consumer-deception (stated vs. effective APR).
- **Evidence & sources**:
  - [open-public] SEC filings of World Acceptance (renewal rates and insurance revenue disclosed to investors — the business model self-described for Wall Street).
  - [open-public] Court records: World's own garnishment suits and bankruptcy files (loan-level exhibits).
  - [request-gated] FOIA'd FTC complaint corpus for World and peer lenders.
  - [interviews] 5+ named former employees; borrowers (loan documents shared by them).
  - [open-public] State insurance-commissioner data on the captive insurer (Life of the South) claims/loss ratios; Missouri campaign-finance and lobbying records.
- **Access tier**: mixed — open-public (SEC, dockets, campaign finance) + request-gated (FTC complaints) + constructed (loan-file collection from borrowers).
- **Acquisition path**: bulk-public-data + FOIA + interviews.
- **Detection signature**: **two-books-diff between investor disclosures and consumer marketing.** The 10-K tells shareholders renewals and credit insurance are the profit engine; the storefront tells borrowers a "90% APR." Recompute effective APR from actual loan documents including packed products; the gap between stated rate, investor-described economics, and borrower experience is the finding. Secondary: **regulator-complaint-corpus-mining** (new tag: FOIA the FTC/CFPB complaint database for a target and its peers as victim-sourcing and pattern index) and temporal-correlation of campaign money to rate-cap kill votes, plus the direct conflict-of-interest join (committee chair owns a licensee).
- **Corroboration structure**: Investor filings (model) x loan-level documents (instance) x ex-employee training accounts (intent) x captive-insurer loss ratios (proving the insurance is priced as fee, not coverage); each layer independent.
- **Impact**: World Acceptance disclosed a CFPB investigation (2014); CFPB dropped the probe in 2018 under Mulvaney, whose campaigns had received World money; CFPB later ordered supervisory designation over World, withdrawn May 2025.
- **Generalization**: Rate-cap-evasion-by-ancillary-product appears in auto lending (GAP/VSC packing), rent-to-own, refund products, MCA/small-business lending, crypto "earn" products. Generic detector: for any licensed lender that is also SEC-registered, diff 10-K unit economics (renewal %, ancillary revenue share, captive-insurer loss ratio) against the product's advertised price; loss ratio below ~40% on packed insurance is a fee-in-disguise flag. EDGAR + state-registry + FEC/lobbying tools cover all three layers.

### Rent Going Up? One Company's Algorithm Could Be Why (2022) — RealPage YieldStar: pooled nonpublic lease data + pricing algorithm as a cartel coordination device
- **URL**: https://www.propublica.org/article/yieldstar-rent-increase-realpage-rent (Oct. 15, 2022; Heather Vogell; data analysis Haru Coryne, Ryan Little)
- **Partner/awards**: ProPublica original.
- **What they found**:
  - RealPage's YieldStar/AI Revenue Management priced units using confidential lease-transaction data pooled from competing landlords; property managers accepted ~90% of its recommendations; ~19.7M rental units ran through RealPage platforms by end-2020.
  - Concentration: in Seattle's Belltown, 10 property managers controlled 70% of ~9,066 market-rate units — every one using RealPage pricing.
  - The company's own people described the mechanism: "The beauty of YieldStar is that it pushes you to go places that you wouldn't have gone" (client); developer Jeffrey Roper on human pricers: "We said there's way too much empathy going on here."
  - Antitrust framing on the record: ex-FTC acting chair Maureen Ohlhausen's "a guy named Bob" hypothetical; ex-DOJ prosecutor Maurice Stucke: "Machines quickly learn the only way to win is to push prices above competitive levels."
- **Finding type(s)**: **algorithmic-price-fixing** (new tag; coordination-by-vendor); extraction-from-captive-population (renters in concentrated submarkets).
- **Evidence & sources**:
  - [open-public] The vendor's own marketing materials, white papers, website performance claims; earnings-call transcripts; RealPage User Group conference content.
  - [interviews] Former RealPage employees (incl. the algorithm's designer), property managers, tenants.
  - [commercial-data] CoStar / Apartments.com data for the Belltown concentration and paired-building comparison (YieldStar building +42% since 2012 vs. ~33% downtown average; non-user building +3.9%/yr).
- **Access tier**: mixed — open-public (vendor's self-description) + commercial-data (listings databases) + constructed (paired-building comparison).
- **Acquisition path**: scrape/marketing-corpus + commercial-data + interviews.
- **Detection signature**: **vendor-brag-mining** (new tag): the coordination mechanism was documented almost entirely from the vendor's own sales artifacts — marketing decks quantifying above-market yield, earnings calls explaining the pooled nonpublic-data advantage, user-conference sessions urging rivals to feed data in. Join to **geographic-concentration-analysis**: compute the share of units in one submarket priced by a single vendor's algorithm (70% in Belltown) — once share is high, "decision support" reads as cartel infrastructure. Paired-building rent trajectories (user vs. non-user) supply the effect estimate.
- **Corroboration structure**: Vendor statements (mechanism) x market-share computation (capability) x paired outcomes (effect) x named antitrust authorities pre-validating the legal theory x former-insider confirmation of data pooling.
- **Impact**: Sen. Klobuchar referral; DOJ civil antitrust suit against RealPage (Aug. 2024); DOJ suit against six of the largest landlords (Jan. 2025); DOJ-RealPage settlement; private class actions and municipal algorithmic-rent-pricing bans [inferred].
- **Generalization**: Same pattern anywhere a SaaS vendor sells "revenue management" fed by competitor data: hotel RM systems, ag-data platforms, chargemaster consultants, PBM pricing, airline seat tools, dynamic wage-setting benchmarks, insurance rating vendors. Generic detector: crawl vendor marketing + earnings calls for the tuple {pooled/nonpublic competitor data} + {yield/outperformance claim} + {high adoption share in a defined market}; each element verifiable from EDGAR transcripts, the vendor's site (Wayback), and market-share data. A standing screen our EDGAR full-text tooling can run today.

### Trump's Inauguration Paid Trump's Company — With Ivanka in the Middle (2018) — a nonprofit inaugural committee overpaying the incumbent family's hotel, documented from internal emails and the committee's own tax filing
- **URL**: https://www.propublica.org/article/trump-inc-podcast-trumps-inauguration-paid-trumps-company-with-ivanka-in-the-middle (Dec. 14, 2018; Justin Elliott, ProPublica; Ilya Marritz, WNYC)
- **Partner/awards**: WNYC ("Trump, Inc.," run as an "open investigation" soliciting listener tips); podcast won the Alfred I. duPont-Columbia Award.
- **What they found**:
  - The 58th Presidential Inaugural Committee (a nonprofit that raised a record ~$107M, ~2x Obama 2009) paid the Trump International Hotel D.C.; hotel managing director proposed "$175,000 per day for use of the Presidential Ballroom and meeting rooms" — $700,000 over four days.
  - Lead planner Stephanie Winston Wolkoff warned in a December 2016 email — reaching Ivanka Trump — "Please take into consideration that when this is audited it will become public knowledge," proposing $85,000/day as a fair ceiling; the family business charged more anyway.
  - ~$40M of inaugural spending remained unaccounted for under the thin disclosure regime; committee workers were housed at the Trump hotel at ~$350/night.
- **Finding type(s)**: self-dealing/related-party; nonprofit-mission-inversion (donor-funded entity enriching insiders' business).
- **Evidence & sources**:
  - [privileged] Internal emails among Ivanka Trump, Rick Gates, and inaugural planners; receipts reviewed by WNYC/ProPublica; hotel staff resumes.
  - [open-public] The inaugural committee's IRS Form 990 and FEC donor disclosures.
  - [interviews] Inaugural workers and vendors.
  - [crowdsourced] Open-investigation podcast format; listener tips fed the series.
- **Access tier**: mixed — privileged (leaked internal emails/receipts) anchored to open-public (990/FEC).
- **Acquisition path**: leak + bulk-public-data (990, FEC) + interviews + crowdsourced.
- **Detection signature**: **related-party price benchmarking inside a nonprofit's spend.** Take the nonprofit's 990 vendor flows; isolate payments to insider-controlled businesses; benchmark the charged rate against (a) a contemporaneous internal fair-price warning (the Wolkoff email — from the org's own agent) and (b) market comparables. "Record revenue + insider vendor + internal warning overridden" converts a pricing dispute into intent evidence.
- **Corroboration structure**: Internal emails (rate negotiation + warning) x 990 totals (money actually moved) x receipts (line items) x participant interviews; independently confirmed when the D.C. AG's subpoena-powered complaint reproduced and extended the findings.
- **Impact**: D.C. AG sued the committee and Trump businesses (Jan. 2020) on the overpayment theory; $750,000 settlement, May 2022; SDNY criminal inquiry into inaugural spending reported by WSJ/NYT.
- **Generalization**: Any nonprofit/campaign/inaugural/PAC whose officers also control vendors: match 990/FEC disbursements to officer-linked entities (registry join on officers/addresses — our unified-registry + 990 + FEC tools do this natively), then benchmark rates. Internal fair-price dissent (board minutes, planner emails, RFP losers) is the highest-value corroboration to hunt in discovery documents and leaks.

### Never-Before-Seen Trump Tax Documents Show Major Inconsistencies (2019) — the same buildings reported richer to the lender and poorer to the tax authority
- **URL**: https://www.propublica.org/article/trump-inc-podcast-never-before-seen-trump-tax-documents-show-major-inconsistencies (Oct. 16, 2019; Heather Vogell, with WNYC's Trump, Inc.)
- **Partner/awards**: WNYC (Trump, Inc.). (Cluster note: kept here because the asymmetry runs lender-vs-tax-authority — a corporate-books integrity story.)
- **What they found**:
  - 40 Wall Street: told the lender occupancy was 58.9% (Dec. 31, 2012) rising to 95%; told NYC tax officials 81% (Jan. 5, 2013) — a gap persisting two years before the books "synced" in Jan. 2016.
  - Trump International Hotel & Tower (2017): ~$822,000 commercial-tenant income reported for tax vs. $1.67M to loan officials — over an eight-year pattern, tax-reported income averaged ~81% of lender-reported; 2017 insurance cost $744,521 (tax) vs. $457,414 (loan); 2015 ground lease $1.65M (tax) vs. ~$1.24M (loan-servicer statement).
  - Experts on the record: Berkeley's Nancy Wallace — the discrepancies are "versions of fraud"; real-estate finance professor Kevin Riordan — "a set of books for the tax guy and a set for the lender."
- **Finding type(s)**: two-books-asymmetry (canonical instance).
- **Evidence & sources**:
  - [request-gated] NYC property-tax appeal records via New York FOIL — public only BECAUSE Trump appealed his property taxes nine years running (the subject's own litigiousness created the record).
  - [open-public] Loan-level disclosures and servicer income/expense statements, public because lender Ladder Capital securitized the debt into CMBS.
  - [interviews] Independent finance/valuation academics and a former prosecutor for characterization.
- **Access tier**: mixed — request-gated (FOIL) + open-public (CMBS disclosure chain).
- **Acquisition path**: FOIA/FOIL + bulk-public-data (securitization documents).
- **Detection signature**: **two-books-diff on hard asset keys.** Same building, same year, two mandatory filings with OPPOSITE incentive gradients (minimize income to the assessor; maximize to the lender). Join on {property, year, line item: occupancy, rental income, insurance, ground lease} and diff. Any persistent signed gap aligned with incentive direction is the finding; the ground-lease line (a fixed contractual number that cannot legitimately differ) is the checksum row converting "estimates differ" into "someone is misstating."
- **Corroboration structure**: Two independent official reporting chains diffed against each other (self-corroborating design); fixed-fact line items used as internal controls; expert panel to calibrate the fraud characterization; Trump Org given the numbers pre-publication.
- **Generalization**: Replicates wherever one asset is described to two masters: property-tax appeals vs. CMBS servicing (any securitized commercial building — both sides public); insurance vs. tax filings; customs invoices vs. VAT books; SEC segment data vs. state utility filings; SBA/PPP applications vs. tax returns. Our platform already holds both sides for the property case (ACRIS/property tools + EDGAR/ABS data); generic detector: for each {entity, asset, year}, harvest every filed line item from independent regimes, flag signed persistent divergences aligned with incentive direction.

### The Ugly Truth Behind "We Buy Ugly Houses" (2023) — HomeVestors franchisees trained to "find the pain," buying homes from the elderly and cognitively impaired at deep discounts and trapping sellers with title clouds
- **URL**: https://www.propublica.org/article/ugly-truth-behind-we-buy-ugly-houses (May 11, 2023; Anjeanette Damon, Byard Duncan, Mollie Simon); series: https://www.propublica.org/series/the-ugly-truth
- **Partner/awards**: Co-published with The Dallas Morning News and Shelterforce.
- **What they found**:
  - Stated method in-article: findings "based on court documents, property records, company training materials and interviews with 48 former franchise owners and dozens of homeowners"; scale ~71,400 purchases since 2016 across ~1,150 franchises in 48 states; company's own figures put nearly one-third of purchases from sellers over 65.
  - Training and marketing taught targeting distress: mailing lists keyed to probate, divorce, code violations, water shutoffs, proximity to nursing homes; ex-franchisee: "You were always lying to them. That's what we were trained."
  - Victims: Corrine Casanova, 82, with dementia, sold a ~$440,000-appraised home for ~$275,000, dying 19 days later; 50+ franchisees used title-clouding (lis pendens/recorded contracts) to block sellers from backing out — one Florida franchise clouded 300+ properties.
  - Internal check: audio of an April 2023 leadership call captured the GC warning serial title-clouders they were "putting the entire system at risk" — while the company simultaneously honored franchisees who did it.
- **Finding type(s)**: **predatory-acquisition-of-distressed-assets** (new tag); extraction-from-captive-population (cognitively impaired/poverty-trapped sellers); dark-pattern/consumer-deception; fraud-enablement-by-design (franchise training as mechanism).
- **Evidence & sources**:
  - [open-public, bulk] County deed/property records (sale prices vs. assessed/appraised values; lis pendens filings by franchisee entity); court records (breach suits, probate collisions).
  - [privileged] Company training materials, franchise agreements, internal correspondence, leadership-call audio.
  - [interviews] 48 former franchise owners (the insider cohort is the backbone) + dozens of sellers/families.
- **Access tier**: mixed — open-public (deeds, dockets) + privileged (training materials, call audio) + constructed (victim-case assembly).
- **Acquisition path**: bulk-public-data (property records) + leak/insider + interviews.
- **Detection signature**: **below-market-transfer screening + instrument-abuse counting.** (1) Join purchase deeds by buyer-entity network (franchise LLCs resolved to the brand) to assessed/appraised values: systematic deep-discount purchases from elderly grantors (probate/estate flags) form the harm signature. (2) Count lis pendens and memoranda-of-contract recorded by the same buyer network: title-clouding at volume is a machine-countable coercion instrument. (3) Internal training materials convert the statistical pattern into corporate intent.
- **Corroboration structure**: Property-record quantification x insider training documents x a 48-member former-franchisee interview cohort x named-victim files (appraisals, cognitive evaluations) x the company's own recorded words.
- **Impact**: HomeVestors banned franchisee lis pendens use within days; CEO David Hicks retired after the series; senators and a regulator called for scrutiny.
- **Generalization**: Identical screens work for any distressed-asset roll-up: wholesalers/"novation" operators, heirs-property buyers, tax-lien investors, structured-settlement factoring, viatical buyers, timeshare-exit firms. Generic detector: buyer-entity network resolution (registry + deed grantee clustering), price-to-assessment ratio distribution per buyer network, seller-vulnerability proxies (probate, age, code-violation liens), plus per-network counts of coercive recorded instruments.

### Minority Neighborhoods Pay Higher Car Insurance Premiums Than White Areas With the Same Risk (2017) — price decoupled from actuarial risk along racial lines
- **URL**: https://www.propublica.org/article/minority-neighborhoods-higher-car-insurance-premiums-white-areas-same-risk (April 5, 2017; Angwin, Larson, Kirchner, Mattu)
- **Partner/awards**: Co-published with Consumer Reports. (Cross-cluster note: institutionally part of the Machine Bias strand; flag for de-duplication against the algorithms cluster.)
- **What they found**:
  - Analysis of 100,000+ liability premiums (standardized profile: 30-year-old woman, safe record) against zip-code-level average liability payouts: some major insurers charged up to 30% more in minority zips than in white zips with the SAME accident cost.
  - Illinois: 33 of 34 companies charged at least 10% more in minority zips; six exceeded 30%. Missouri and Texas: at least half of insurers overcharged safe drivers in high-risk minority zips relative to comparable non-minority zips. Even price-regulated California: eight insurers 10%+.
  - Paired example: Otis Nash (Chicago, minority zip) $190.69/month vs. Ryan Hedges (same insurer, whiter zip, actuarially riskier) $54.67/month.
- **Finding type(s)**: disparate-impact-by-race-or-geography; algorithmic-or-systematic-denial (rating-territory machinery); **price-to-risk-decoupling** (new tag).
- **Evidence & sources**:
  - [open-public/request-gated] State insurance departments' zip-level aggregate loss/payout data — obtainable only in the four states that release it (CA, IL, TX, MO); data availability defined the study's geography.
  - [commercial-data/constructed] Quoted-premium dataset for the standardized driver profile across insurers and zips.
  - [open-public] Census demographics for minority-zip definitions.
- **Access tier**: mixed — open-public (loss data, census) + commercial/constructed (premium matrix).
- **Acquisition path**: bulk-public-data + commercial-data + constructed standardization.
- **Detection signature**: **price-to-risk-join.** Hold the customer constant (fixed persona), join quoted price to the regulator's own per-geography loss cost, and regress: price differences unexplained by loss cost, correlated with racial composition, are the finding. The defensibility move: the risk measure comes from the industry's own aggregate payouts, not the newsroom's model.
- **Corroboration structure**: Four-state replication under different regulatory regimes; insurer-by-insurer publication (not industry averages) forcing specific rebuttals; industry and state-regulator methodological objections published and answered in-article.
- **Methodology notes**: Core method quoted in-article; fuller companion methodology writeup exists (https://www.propublica.org/article/minority-neighborhoods-higher-car-insurance-premiums-methodology).
- **Generalization**: Anywhere price and risk are separately observable by geography: homeowners insurance (FAIR-plan vs. voluntary market), auto lending rate sheets, small-dollar-loan pricing, HMDA mortgage pricing vs. default data, utility deposits. Generic detector: fixed-persona price matrix x official loss/outcome data x demographics; alert on price residuals correlated with protected-class geography after risk controls.

### Medical Staffing Companies Cut Doctors' Pay While Spending Millions on Political Ads (2020) — PE-owned ER staffing firms cut clinician pay in the pandemic while bankrolling the campaign to preserve surprise billing
- **URL**: https://www.propublica.org/article/medical-staffing-companies-cut-doctors-pay-while-spending-millions-on-political-ads (April 20, 2020; Isaac Arnsdorf)
- **Partner/awards**: ProPublica original. **Attribution boundary:** balance-billing economics = Yale researchers; Doctor Patient Unity unmasking = NYT (Sept. 2019). This entry extracts only ProPublica's original juxtaposition reporting.
- **What they found**:
  - TeamHealth (Blackstone; 16,000+ clinicians) and Envision (KKR; 25,000+ providers) cut ER doctor pay, hours, and benefits as non-COVID volumes collapsed — while entities they fund spent $2.2M on political ads after the Jan. 31, 2020 health-emergency declaration.
  - Their advocacy vehicle Doctor Patient Unity had spent $57M total on ads opposing surprise-billing legislation.
- **Finding type(s)**: regulatory-capture/lobbying-to-preserve-rents; extraction-from-captive-population (ER patients cannot choose their physician group); two-books-asymmetry (clinician-first rhetoric vs. spending behavior).
- **Evidence & sources**:
  - [open-public] FCC political-file disclosures (broadcast ad buys); Facebook Ad Library; CBO analyses.
  - [commercial-data] Advertising Analytics ad-buy tracking.
  - [privileged/interviews] Affected doctors (anonymous) describing pay-cut memos; company statements.
- **Access tier**: mixed — open-public (FCC files, ad library) + commercial-data (ad tracking) + insider interviews.
- **Acquisition path**: bulk-public-data + commercial-data + interviews.
- **Detection signature**: **temporal-correlation of spending books**: time-align the subject's cost-cutting actions (dated internal memos) against its political ad expenditures (FCC political files + ad tracking, also dated) across a shock window; the simultaneity is the story. FCC public files are an underused, fully open ledger of broadcast influence, joinable to dark-money vehicles by disclosed sponsor names.
- **Corroboration structure**: Ad-spend triangulated across FCC filings, a commercial tracker, and platform ad libraries; pay cuts corroborated by multiple clinicians per firm; ownership chain (Blackstone/KKR) from corporate disclosures.
- **Generalization**: The two-ledgers-in-time move works for any austerity-plus-influence story: layoffs vs. buybacks, wage cuts vs. lobbying spikes, safety-budget cuts vs. trade-association dues. Minimum data: dated internal cost actions (leaks, WARN notices, earnings calls) + dated influence spend (FCC political files, lobbying disclosures, ad libraries). Our FEC/lobbying and EDGAR tools cover the open half; WARN-notice ingestion would complete it.

---

## Cluster Synthesis

### 1. Recurring evidence-source types (frequency across 12 entries)

| Source type | Count | Entries |
|---|---|---|
| Bulk local court dockets (suits, judgments, garnishments, warrants, lis pendens) | 6 | Color of Debt; garnishment; hospitals; Coffeyville; Debt Inc.; HomeVestors |
| Interviews with former insiders (employees, franchisees, ex-officials) | 8 | TurboTax II; Debt Inc.; RealPage; HomeVestors; hospitals; inaugural; PE staffing; garnishment |
| Internal corporate documents (board decks, strategy memos, training materials, emails, call audio) | 5 | TurboTax II; HomeVestors; inaugural; RealPage (partial); PE staffing (memos) |
| Subject's own public commercial artifacts (website code, marketing, earnings calls, SEC filings) | 5 | TurboTax I; RealPage; Debt Inc. (10-K); two-books (CMBS); PE staffing (ownership) |
| Records-law acquisitions (FOIA/FOIL: IRS comms, FTC complaint corpus, NYC tax appeals) | 3 | TurboTax II; Debt Inc.; two-books |
| Nonprofit/political money disclosures (990s, FEC, FCC political files, lobbying, campaign finance) | 5 | hospitals; inaugural; TurboTax II; Debt Inc.; PE staffing |
| Commercial/proprietary datasets via partnership or purchase (ADP, CoStar, Advertising Analytics, premium quotes) | 4 | garnishment; RealPage; PE staffing; auto insurance |
| Census/demographic join layers | 3 | Color of Debt; auto insurance; hospitals (context) |
| Crowdsourced tips and callouts | 3 | TurboTax I; hospitals/MLK50; Trump, Inc. |
| Constructed test personas / mystery shopping | 2 | TurboTax I; auto insurance (fixed-profile pricing) |
| Field observation (courtrooms) | 1 | Coffeyville |
| Pre-existing litigation records mined for evidence | 3 | TurboTax II (antitrust testimony); HomeVestors (franchise suits); inaugural (AG complaint enrichment) |

Structural observation: this cluster runs overwhelmingly on OPEN or CONSTRUCTIBLE evidence. Only 3 of 12 entries required a leak at their core (TurboTax II, inaugural, HomeVestors training materials), and in each case the leak supplied intent while open records had already supplied behavior. Dominant architecture: open-data quantification first, insider/leak confirmation second.

### 2. Recurring detection signatures (frequency)

| Signature | Count | Entries |
|---|---|---|
| denominator-construction (bulk records → per-capita rates) | 4 | Color of Debt; garnishment (custodian variant); hospitals; Coffeyville (warrant counts) |
| plaintiff-frequency-inversion (rank filers, not defendants) | 3 | hospitals (both phases); Color of Debt/So Sue Them; HomeVestors (per-network instrument counts, variant) |
| two-books-diff (same fact, two authorities/audiences) | 3 | two-books (canonical); Debt Inc. (10-K vs. storefront); PE staffing (temporal variant) |
| internal-rulebook-acquisition | 3 | TurboTax II; HomeVestors; Debt Inc. (trained practice via insiders) |
| temporal-correlation (money/action timelines) | 3 | TurboTax II; Payday Playbook; PE staffing |
| crowdsourced-case-aggregation | 3 | TurboTax I; hospitals/MLK50; Trump, Inc. |
| vendor-brag-mining (marketing/earnings-call self-incrimination) | 2 | RealPage; Debt Inc. (investor disclosures) |
| mystery-shopper-walkthrough / fixed-persona pricing | 2 | TurboTax I; auto insurance |
| geocoded-disparity-join | 2 | Color of Debt; auto insurance |
| related-party price benchmarking (nonprofit spend → insider vendor) | 2 | inaugural; hospitals (captive collector) |
| procedural-artifact-forensics (contempt/bail/lis pendens as countable instruments) | 2 | Coffeyville; HomeVestors |
| site-forensics (subject's own web assets) | 1 deep | TurboTax I (noindex/robots + NONFFA tagging) |
| price-to-risk-join | 1 | auto insurance |
| third-party-data-custodian-query | 1 | garnishment (ADP) |
| regulator-complaint-corpus-mining (FOIA'd FTC/CFPB complaints) | 1 | Debt Inc. |
| geographic-concentration-analysis (vendor/market share in a submarket) | 1 | RealPage |

New tags coined this cluster: **public-benefit-interception; courts-as-profit-center; nonprofit-mission-inversion; debt-criminalization; algorithmic-price-fixing; predatory-acquisition-of-distressed-assets; price-to-risk-decoupling** (finding types); **mystery-shopper-walkthrough; third-party-data-custodian-query; plaintiff-frequency-inversion; vendor-brag-mining; procedural-artifact-forensics; regulator-complaint-corpus-mining; geocoded-disparity-join; geographic-concentration-analysis; related-party-price-benchmarking** (detection signatures).

### 3. Transferable pattern candidates

**Pattern: Docket Denominator (the Color-of-Debt pipeline).** Acquire a court system's civil filings in bulk for a multi-year window; reduce to enforceable events (judgments, garnishments, warrants); geocode defendants to census tracts and join demographics; compute per-capita rates with income stratification; separately invert the same data by plaintiff to rank top filers and resolve them through registries/990s. Two stories fall out of one dataset: the disparate-impact story (defendant side) and the industrial-plaintiff story (filer side). Minimum data: party names + addresses + case type + disposition; census tables. Agent watch-for in ANY investigation: a single plaintiff with four-digit annual filing counts in one county; a 501(c)(3) in a top-filer list; garnishment answers listing the plaintiff itself as the defendant's employer; contempt/bail entries attached to civil collection cases (escalate to debt-criminalization immediately). Platform fit: CourtListener/NYSCEF/state-court + 990 tools cover acquisition; buildable as a standing screen.

**Pattern: Two-Books Asymmetry on Hard Keys.** Find any asset or fact an entity must report to two authorities with opposite incentive gradients (assessor vs. lender; investor vs. customer; regulator vs. marketer; customs vs. tax). Join on hard keys {entity/asset, period, line item} and diff, using fixed-fact rows (contractual ground rent, insurance premiums) as checksums that cannot legitimately diverge. Persistent signed gaps aligned with incentive direction = misrepresentation to at least one audience. Minimum data: two independent filed documents per asset-year — often both public (property-tax appeals + CMBS servicing; 10-K + storefront pricing). Watch-for: securitized debt anywhere in a subject's capital stack (it makes private loan books public); a subject who litigates their own taxes (appeals create records); "free"/price claims in marketing vs. unit economics in investor materials.

**Pattern: Vendor-Brag Mining (self-incriminating sales channel).** Vendors of pricing/collection/"optimization" services must advertise the mechanism to sell it — so coordination, yield extraction, and denial engines get documented by their own marketing decks, earnings calls, user conferences, patents, case studies. Harvest vendor claims for the tuple {pooled nonpublic competitor data} + {above-market outperformance} + {adoption share}; compute vendor concentration inside one submarket; pair user vs. non-user outcome trajectories. Minimum data: EDGAR transcripts/filings, vendor web archive (Wayback), one market-share source. Watch-for: any B2B vendor whose pitch quantifies gains over "manual" decisions; user conferences where competitors meet; "data contribution" requirements in SaaS contracts. Runnable today via EDGAR full-text + Wayback tooling.

**Pattern: Public-Benefit Interception with Site Forensics.** Where a company profits from consumers NOT finding a free/mandated alternative (free filing, charity care, refunds, price-transparency files), the steering machinery lives in the company's own web assets and product flows. Detector: (1) diff robots.txt/meta-robots/sitemap treatment of obligation pages vs. revenue pages, historically via Wayback; (2) run an eligibility-matching synthetic persona through the funnel, logging screens and URL/analytics variables (segmentation variable names like NONFFA are intent evidence); (3) compare marketing claims to eligibility outcomes. Minimum data: the subject's public website + the benefit's eligibility rules. Escalation: crowd tips on code artifacts are high-yield — publish the first finding and solicit.

**Pattern: Nonprofit Self-Dealing via Captive Vendor.** A nonprofit's money exits to insiders through vendors it controls or prices set by insiders. Detector: 990 (Schedule L/R) + FEC/committee disbursements joined through registries to officer-linked entities; benchmark charged rates against market comparables; hunt contemporaneous internal dissent (the fair-price email, the board-minute objection), which converts overpricing into knowledge/intent. Variant: captive vendor as extraction arm pointed AT the beneficiary class (hospital-owned collection agency suing patients). Minimum data: 990s + corporate registry + one price benchmark. Watch-for: nonprofit paying an entity sharing an address/agent/officer with its board; a charity in a county's top-10 civil plaintiff list; record fundraising followed by vendor concentration.

**Pattern: Custodian-Run Denominator.** When the true base rate of a practice exists only inside a private intermediary (payroll processor, claims clearinghouse, listing platform), the newsroom-grade move is negotiating an aggregate analysis run by the custodian to the investigator's specification, then anchoring with case-level public records. Minimum data: none held — the asset is the ask; prerequisite is identifying the chokepoint firm with monopoly-grade coverage. Watch-for: any phenomenon where court/agency data captures only the enforcement tail (garnishment orders) while the operational base (paychecks docked) sits with a processor. On our platform this is a human-action lead type (partnership request), not a tool query — flag explicitly rather than substituting a weaker proxy denominator.
