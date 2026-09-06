# ProPublica Evidence Ontology — Cluster 05: Criminal Justice & Policing

Compiled 2026-07-28. Web-verified against propublica.org and partner/award sites. 12 full entries + 2 abbreviated entries, chronological. Machine Bias receives the deepest extraction per brief.

## Verification notes — candidate corrections

- **"2017 leaked CCRB file trove" — DROPPED (misattributed).** The leaked NYPD disciplinary-files trove was **BuzzFeed News (2018)**, not ProPublica. ProPublica's NYPD disciplinary work is the post-50-a-repeal 2020 database (entry below).
- **Mississippi restitution centers / debtors-prison camps — DROPPED (misattributed).** That series is **The Marshall Project + Mississippi Today** (Anna Wolfe, Michelle Liu, Jan 2020). ProPublica's fines-and-fees-as-revenue work is Driven Into Debt/The Ticket Trap (entry below).
- **"Alive and Alone" — NOT FOUND.** No ProPublica investigation by that title surfaced; likely a false memory. Nearest match: ProPublica/Marshall Project/NBC juvenile solitary-confinement reporting in Louisiana.
- **Dedicated parole/probation-revocation series — NOT FOUND** as a standalone ProPublica series. Closest verified ProPublica parole work is the 2025 TIGER algorithm investigation with Verite News (abbreviated entry below).
- **Eviction/civil debt collection** (Paul Kiel's work) — excluded per scope as the civil-courts sibling cluster.
- **"The Ticket Trap" partner** verified as **WBEZ Chicago** (with ProPublica Illinois) — candidate memory correct.

---

### Out of Order (2013) — Courts found NYC prosecutors committed harmful misconduct in 30 reversed cases; exactly one was ever disciplined
- **URL**: https://www.propublica.org/article/who-polices-prosecutors-who-abuse-their-authority-usually-nobody (Apr 3, 2013; Joaquin Sapien, Sergio Hernandez)
- **Partner/awards**: ProPublica original.
- **What they found**:
  - Reviewing state and federal court rulings 2001–2011 (plus civil cases back to 1985), they identified **30 instances** in which judges explicitly concluded NYC prosecutors committed misconduct serious enough to overturn convictions.
  - **Only one prosecutor** — Queens ADA Claude Stuart — suffered serious professional consequences (job loss; license suspension). Others received raises and promotions after courts cited their abuses.
  - Named victims: Jabbar Collins (15 years; evidence withheld by Brooklyn prosecutor Michael Vecchione; later a multimillion-dollar settlement); Shih-Wei Su (12 years; false testimony elicited); Amine Baba-Ali (exonerating medical records withheld; $2.1M settlement).
- **Finding type(s)**: statistical-outlier-practitioner; institutional-coverup/records-suppression; **accountability-gap** (new tag: authoritative findings of wrongdoing produce no sanction)
- **Evidence & sources**: appellate/trial court opinions citing misconduct (open-public); attorney disciplinary records (open-public/request-gated); DA office personnel and promotion records (request-gated); interviews with exonerees and defense lawyers (constructed).
- **Access tier**: mixed — open-public (opinions) + request-gated (personnel/disciplinary)
- **Acquisition path**: bulk-public-data (opinion mining) + FOIA + interviews
- **Detection signature**: **sanction-outcome-diff** — corpus of appellate opinions explicitly finding prosecutorial misconduct, joined on prosecutor name to bar-disciplinary records and office personnel/promotion histories, revealed a near-total accountability gap (30 judicial findings → 1 sanction).
- **Corroboration structure**: each misconduct instance anchored to a court's own written finding (primary, adjudicated); consequences verified in a second independent record system (bar/personnel); illustrative cases deepened with settlements and interviews.
- **Methodology notes**: method described in-article: identify misconduct via opinions "explicitly citing prosecutorial violations," cross-reference disciplinary outcomes, review personnel records for raises/promotions. No public dataset. [inferred: opinion identification likely keyword search of legal databases — not stated.]
- **Impact**: NY legislation proposing a prosecutorial-conduct commission followed; a featured defendant walked free seven years later.
- **Generalization**: works for any profession whose failures are adjudicated in one ledger and disciplined in another: physicians (malpractice judgments vs. medical-board actions), brokers (arbitration awards vs. FINRA BrokerCheck), auditors (restatements vs. PCAOB sanctions), police (court suppression findings vs. IA outcomes). Generic detector: entities with N≥2 adjudicated-wrongdoing findings and zero entries in the corresponding sanction registry.

---

### Deadly Force, in Black and White (2014) — Federal homicide microdata showed young Black males were killed by police at 21x the rate of white peers
- **URL**: https://www.propublica.org/article/deadly-force-in-black-and-white (Oct 10, 2014; Ryan Gabrielson, Eric Sagara, Ryann Grochowski Jones)
- **Partner/awards**: ProPublica original.
- **What they found**:
  - From FBI Supplementary Homicide Report (SHR) data covering **12,000+ police homicides 1980–2012**, the 2010–2012 subset (1,217 fatal police shootings) showed Black males 15–19 killed at **31.17 per million vs. 1.47 per million** for white males — a **21x risk ratio** (95% CI: 10x–40x).
  - Of 41 children ≤14 reported killed by police 1980–2012: 27 Black, 8 white. Of 15 teens shot while fleeing (2010–12), 14 were Black.
  - Data caveats stated prominently: SHR is a "minimum count"; many of ~17,000 departments never file; Florida stopped reporting in 1997, NYC in 2007.
- **Finding type(s)**: disparate-impact-by-race-or-geography; **undercount-by-design** (the reporting regime itself conceals scale)
- **Evidence & sources**: FBI SHR microdata (open-public, via the National Archive of Criminal Justice Data); census population denominators (open-public).
- **Access tier**: open-public
- **Acquisition path**: bulk-public-data
- **Detection signature**: **denominator-construction on federal incident microdata** — incident-level victim records (race × age × circumstance) divided by census population-at-risk produced per-capita risk ratios that raw counts concealed; confidence intervals computed to survive the small-N critique.
- **Corroboration structure**: single authoritative federal dataset, self-limited: the story simultaneously reported the disparity and quantified the dataset's incompleteness (named non-reporting agencies) — turning the data gap into a second finding.
- **Methodology notes**: caveats and CI stated in-article. [inferred: this pre-dated and helped motivate the Washington Post/Guardian independent police-killings databases launched 2015.]
- **Generalization**: any incident-report system with victim demographics supports the same move: traffic stops, use-of-force reports, school discipline, child-welfare removals. Generic detector: compute per-capita rates against the correct at-risk population, report CI, and separately measure which reporters are missing (missingness map = second story).

---

### An Unbelievable Story of Rape (2015) — Police charged a rape victim with false reporting; the serial rapist was caught two states away with photos of her
- **URL**: https://www.propublica.org/article/false-rape-accusations-an-unbelievable-story (Dec 16, 2015; T. Christian Miller, ProPublica; Ken Armstrong, The Marshall Project)
- **Partner/awards**: Co-published with **The Marshall Project**; **2016 Pulitzer Prize, Explanatory Reporting**; adapted as Netflix's *Unbelievable* (2019); book *Unbelievable*.
- **What they found**:
  - Lynnwood, WA police coerced 18-year-old "Marie" into recanting her 2008 rape report (polygraph threats, threatened loss of housing) and **charged her with false reporting**.
  - ~2.5 years later, Colorado detectives in two suburbs linked a serial-rapist MO across jurisdictions and caught **Marc O'Leary**, whose photos proved Marie's rape; he received 327.5 years (CO) + 28.5 years (WA).
  - Lynnwood's handling was audited by an external reviewer (Sgt. Gregg Rinta) who called the coercion improper; Marie settled with Lynnwood for $150,000.
- **Finding type(s)**: due-process-bypass (victim criminalized); **victim-disbelief-failure** (new tag); institutional-coverup/records-suppression (soft form)
- **Evidence & sources**: police case files and internal reviews from multiple departments (request-gated); DNA/forensic records in the files; O'Leary confession records (litigation-records); victim and detective interviews (constructed).
- **Access tier**: mixed — request-gated (police files) + constructed (interviews)
- **Acquisition path**: FOIA/records requests + interviews + litigation-records
- **Detection signature**: **two-jurisdiction narrative join** — the same crime series existed as contradictory records in unconnected agencies (WA: "false report" prosecution of the victim; CO: serial-rape investigation); joining the two case files on the perpetrator exposed the first agency's failure. The story measures what happens when cross-jurisdiction MO linkage does not occur.
- **Corroboration structure**: dual-track reconstruction — every claim about the failed investigation grounded in the departments' own paper (reports, the Rinta review, charging documents), validated against the perpetrator's confession and forensic record.
- **Methodology notes**: no formal methodology page; sourcing described in-article. [inferred: files obtained via WA/CO public-records acts and court records.]
- **Generalization**: "victim recast as offender" is detectable wherever complaint dispositions are recorded: flag agencies with outlier rates of unfounded/false-report charges relative to peers; join unsolved-case MO attributes across neighboring jurisdictions to find serial actors exploiting fragmentation (fraud rings across bank compliance silos, serial harassers across employers, contractor fraud across procurement offices).

---

### Machine Bias (2016) — COMPAS recidivism scores were twice as likely to falsely label Black defendants high-risk; the story that created algorithmic accountability reporting
- **URL**: https://www.propublica.org/article/machine-bias-risk-assessments-in-criminal-sentencing (May 23, 2016; Julia Angwin, Jeff Larson, Surya Mattu, Lauren Kirchner)
- **Partner/awards**: ProPublica original. Canonical citation of the algorithmic-fairness field; triggered the error-rate-balance vs. predictive-parity impossibility literature.
- **What they found**:
  - Black defendants who did **not** reoffend were misclassified higher-risk at **44.85%** vs. **23.45%** for white defendants; white reoffenders were mislabeled low-risk at **47.72%** vs. **27.99%** for Black reoffenders.
  - Controlling for criminal history, age, gender and charge, Black defendants were **45% more likely** to get higher general-recidivism scores and **77% more likely** for violent-recidivism scores.
  - Predictive accuracy was mediocre: 61% overall for general recidivism; of people predicted violent, only **20%** committed a violent crime within two years.
  - COMPAS (Northpointe, now Equivant): 137-question instrument; race not an input but proxies abound; paired narrative contrasts (Brisha Borden high-risk/no reoffense vs. Vernon Prater low-risk/reoffended).
- **Finding type(s)**: algorithmic-or-systematic-denial (bias); disparate-impact-by-race-or-geography
- **Evidence & sources**: COMPAS scores for 18,610 people scored 2013–2014 via **public records request to the Broward County Sheriff's Office** (request-gated); Broward public criminal dockets + jail/prison records for outcome construction (open-public); the COMPAS questionnaire itself (internal-rulebook, obtained as public record); Northpointe practitioner documentation defining score bands (open-public).
- **Access tier**: mixed — request-gated (scores) + open-public (arrest/incarceration outcomes)
- **Acquisition path**: FOIA + bulk-public-data
- **Detection signature**: **ground-truth-construction** — obtained a scoring system's predictions for a full cohort (11,757 pretrial assessments), independently built the outcome variable the score claims to predict (two-year recidivism through Apr 1, 2016, defined as a fingerprintable arrest with a UCR charge, excluding traffic/municipal/failure-to-appear; violent recidivism per FBI definition) by joining scores to subsequent arrest records on name+DOB, and compared **error rates conditional on race**, not just overall accuracy.
  - Sub-signatures: (1) match-quality audit — hand-checked 400 random matches, 3.75% error rate; (2) three independent statistical frames — logistic regression on score level (N=6,172 general / 4,020 violent), Cox proportional-hazards on time-to-reoffense with incarceration periods removed (N=10,314; concordance 63.6%), and contingency-table FPR/FNR by race; (3) exact replication of the vendor's own two-year validation benchmark so the comparison could not be dismissed as apples-to-oranges.
- **Corroboration structure**: convergent results across three model families; error-audited record linkage; the vendor's own documentation used to define score cutoffs; publication of full data + code inviting adversarial replication. Northpointe's rebuttal (equal predictive parity across races) did not contradict the finding — it exposed that the two fairness definitions are mathematically incompatible when base rates differ, which became the enduring result.
- **Methodology notes**: stated in full — "How We Analyzed the COMPAS Recidivism Algorithm" (https://www.propublica.org/article/how-we-analyzed-the-compas-recidivism-algorithm); data + Jupyter notebooks on GitHub (https://github.com/propublica/compas-analysis: compas-scores-two-years.csv, cox-parsed.csv, SQLite db, 2 notebooks; ~695 stars / 293 forks — a standard ML-fairness benchmark).
- **Impact**: founded the algorithmic-accountability genre; the dataset is the reference corpus of the fairness-metrics impossibility literature; risk-score transparency became a litigation and legislative issue.
- **Generalization**: the template for auditing ANY scoring/screening system: obtain (a) scores/decisions with subject identifiers, (b) the later ground-truth outcome from an independent record system, (c) protected-class attributes. Compute FPR/FNR by class, not just AUC. Applies to credit scoring, tenant screening, fraud flags, hiring filters, insurance pricing, sanctions/AML screening, child-welfare risk models. Minimum viable version: compare score distributions for matched cohorts (the regression-control move). Key acquisition insight: **scores held by government agencies are public records even when the algorithm is proprietary.**

---

### Busted (2016) — $2 roadside drug tests that turn positive on household chemicals fed tens of thousands of guilty pleas
- **URL**: https://www.propublica.org/article/common-roadside-drug-test-routinely-produces-false-positives (Jul 7, 2016; Ryan Gabrielson, Topher Sanders; series: https://www.propublica.org/series/busted)
- **Partner/awards**: Co-published with **The New York Times Magazine**; Sidney Award.
- **What they found**:
  - Houston crime-lab retests 2004–2015 identified **416 "variant" cases** where the lab result contradicted the field test; in **212** the substance was **not a controlled substance at all**; 301 originated from Houston PD arrests.
  - **58% pleaded guilty at first court appearance; median arrest-to-plea: 4 days** — years before lab retesting; 93% of the 212 innocent defendants got jail or prison; 59% of the wrongfully convicted were Black in a county 24% Black.
  - Scaled up: ~1.2M annual drug-possession arrests; est. **100,000+ guilty pleas per year rest on unconfirmed field tests**; Florida state lab data showed 21% of "methamphetamine" evidence was wrong.
  - Amy Albritton: pleaded guilty in 48 hours to crack possession; the "crack" was food debris and BC Powder (aspirin/caffeine); exonerated via Harris County conviction-integrity review.
- **Finding type(s)**: **wrongful-conviction-production** (new tag); fraud-enablement-by-design (courts accepting known-unreliable tests); disparate-impact-by-race-or-geography; due-process-bypass (plea-before-evidence)
- **Evidence & sources**: Houston lab GC-MS retest records and examination sheets (request-gated); Harris County dockets and DA conviction-integrity correspondence (open-public/request-gated); Florida Dept. of Law Enforcement lab data (request-gated); court-record survey of the 40 largest US jurisdictions + RTI International prosecutor survey (open-public/constructed); exoneree interviews (constructed).
- **Access tier**: mixed — request-gated (lab internals) + open-public (dockets)
- **Acquisition path**: FOIA + bulk-public-data + interviews
- **Detection signature**: **two-books-diff via retest ledger** — the crime lab's confirmatory-test results joined on case number to the original field-test-based charge and plea disposition revealed the false-positive cohort; then **plea-timing analysis** (docket timestamps: plea date vs. lab-report date) proved convictions systematically preceded the only reliable evidence.
- **Corroboration structure**: lab science (GC-MS, primary) → court dockets (primary) → DA's own exoneration letters (admission) → national scaling from surveys; independent chemistry literature on cobalt-thiocyanate test error rates.
- **Methodology notes**: data provenance described in-article; no standalone methodology page found. [inferred: Houston cohort assembled from DA disclosure letters plus lab records.]
- **Impact**: Harris County DA began requiring lab reports before plea deals (dismissals rose 31%); 250+ Houston convictions ultimately overturned; civil suits in four states.
- **Generalization**: wherever a cheap screening test gates an irreversible decision faster than the confirmatory test arrives: breathalyzers vs. blood tests, hair tests in custody cases, SNAP/UI fraud flags, plate readers, AI content matches leading to account bans. Generic detector: join screening-result → final-adjudication → confirmatory-result on case ID; measure (a) contradiction rate, (b) fraction of adjudications predating confirmation.

---

### The NYPD's Nuisance-Abatement Machine (2016) — Civil "nuisance" actions locked people out of homes and shops, mostly in minority neighborhoods, without convictions or hearings
- **URL**: https://www.propublica.org/article/nypd-nuisance-abatement-evictions (Feb 4, 2016, Sarah Ryley; series: https://www.propublica.org/series/nuisance-abatement)
- **Partner/awards**: Joint with the **New York Daily News**; **2017 Pulitzer Prize for Public Service** (shared).
- **What they found**:
  - Reviewed **516 residential nuisance-abatement actions** (Jan 1, 2013–Jun 30, 2014) and traced the underlying criminal cases of the people banned: **173 never convicted; 44 apparently never prosecuted at all**.
  - In **75% of cases judges approved ex parte lockouts** before residents could appear in court.
  - Settlements extracted onerous terms: lifetime bans of named family members, consent to **warrantless searches**, automatic lease forfeiture upon future accusation; sting-driven actions targeted immigrant-owned shops.
  - Nine of ten actions landed in minority neighborhoods.
- **Finding type(s)**: **civil-process-weaponization** (new tag); due-process-bypass; disparate-impact-by-race-or-geography; extraction-from-captive-population (rights extracted as settlement currency)
- **Evidence & sources**: state supreme court civil case files — petitions, ex parte orders, settlement stipulations (open-public, laboriously assembled); criminal-court dispositions of the banned individuals (open-public); resident interviews (constructed).
- **Access tier**: open-public (but only via constructed corpus — no bulk feed existed)
- **Acquisition path**: bulk-public-data (hand-built case-file corpus) + interviews
- **Detection signature**: **case-corpus construction + criminal-outcome join** — built the universe of nuisance-abatement filings, coded each for target/neighborhood/settlement terms, then joined every banned person to criminal records; the null result of that join (no conviction, no prosecution) was the finding. Plus **ex-parte-rate measurement**: fraction of orders granted before any adversarial hearing.
- **Corroboration structure**: the city's own filings and signed stipulations (primary) → criminal dockets (primary) → geographic/demographic overlay → named case studies; officials' on-record reactions.
- **Methodology notes**: counts and review scope stated in-series. No public dataset found. [inferred: corpus built by pulling every filing under the nuisance-abatement statute from county clerk records.]
- **Impact**: City Council passed a **13-bill reform package**; litigation followed; Pulitzer Public Service 2017.
- **Generalization**: any parallel civil/administrative channel that imposes punishment while evading criminal-procedure protections: civil forfeiture, code-enforcement condemnations, emergency license suspensions, immigration detainers, platform debanking. Generic detector: enumerate the civil actions, join respondents to the criminal system, measure (a) conviction rate of the "criminals" punished, (b) ex parte rate, (c) boilerplate rights-waiver terms, (d) geographic concentration.

---

### Walking While Black (2017) — Jacksonville pedestrian tickets fell on Black residents at 3x the white rate, and at least half of one statute's tickets were legally wrong
- **URL**: https://features.propublica.org/walking-while-black/jacksonville-pedestrian-violations-racial-profiling (Nov 2017; Topher Sanders, ProPublica; Ben Conarck, Florida Times-Union; Kate Rabinowitz)
- **Partner/awards**: Co-published with the **Florida Times-Union**; Paul Tobenkin Award; Al Nakkula Award.
- **What they found**:
  - Over five years, Black residents received **55% of all pedestrian tickets** while being **29% of the population** — ~3x the white rate; Jacksonville enforces **28 separate pedestrian statutes**.
  - Tickets clustered in poor Black zip codes; ticket locations correlated only weakly with pedestrian-fatality locations (Pearson r=0.37), undercutting the safety rationale.
  - **Statute-conformance audit**: for FL 316.130(11) (crossing between adjacent signalized intersections), Google Street View review showed "at minimum, half of the tickets were given in error" — no traffic signals existed where required.
  - Reporters staked out downtown and watched uniformed officers commit the same violations their agency tickets.
- **Finding type(s)**: disparate-impact-by-race-or-geography; **enforcement-without-legal-basis** (tickets legally invalid on their face); extraction-from-captive-population (fines + ID-production demands)
- **Evidence & sources**: statewide Traffic Citation Accounting Transmission dataset from Florida Court Clerks & Comptrollers, Jan 2012–Jul 2017, via Sunshine Law (request-gated bulk); original citation PDFs for 746 tickets missing locations (request-gated); ACS 5-year denominators (open-public); crash/fatality records matched to dispositions and death certificates on name+DOB — race resolved in 190 of 194 pedestrian deaths; Google Street View (open-public); field observation (constructed).
- **Access tier**: mixed — request-gated (bulk citations, PDFs) + open-public (census, imagery) + constructed (stakeouts)
- **Acquisition path**: bulk-public-data (Sunshine Law) + field-observation
- **Detection signature**: **denominator-construction + statute-conformance-audit** — 2,208 pedestrian tickets geocoded to block level and rated per-capita by race/tract (incidence risk ratio, chi-square) exposed disparity; each ticket under one statute was checked against the physical world (Street View: does the required signal pair exist?) exposing mass legally-baseless enforcement; safety justification tested via spatial correlation of tickets vs. fatal crashes.
- **Corroboration structure**: bulk data → hand-recovered paper citations for missing fields → independent physical verification (imagery) → behavioral control (officers jaywalking) → agency non-rebuttal.
- **Methodology notes**: stated in full — "How We Calculated the Risks of Walking While Black" (https://www.propublica.org/article/how-we-calculated-the-risks-of-walking-while-black). No code/data release found.
- **Impact**: Sheriff's office directed officers to stop ticketing pedestrians for failure to carry ID; NAACP Legal Defense Fund engaged.
- **Generalization**: the paired move (rate disparity + facial invalidity) transfers to any citation regime: bike tickets, fare evasion, loitering, park curfews, code enforcement. Generic detector: per-capita citation rates by class/geo, then sample citations against the statute's physical/legal predicates (signage, signal placement, posted hours, jurisdiction boundaries) via imagery or GIS.

---

### Documenting Hate (2017–2019) — A crowdsourced national hate-incident database built to measure what the FBI's numbers miss
- **URL**: launch: https://www.propublica.org/atpropublica/propublica-and-coalition-of-news-organizations-launch-documenting-hate-to-collect-data-on-hate-crimes-and-bias-incidents-in-the-most-complete-sustained-effort-to-date (Jan 2017); flagship analysis: https://projects.propublica.org/graphics/hatecrime-map (Nov 17, 2017; Ken Schwencke, Hannah Fresques)
- **Partner/awards**: Coalition led by ProPublica with national and local newsroom partners plus verification partners Meedan and Ushahidi; Scripps Howard finalist; NLGJA Al Neuharth Award for Schwencke.
- **What they found**:
  - The FBI's national hate-crime count is "only a fraction" of the National Crime Victimization Survey estimate; roughly **20% of law-enforcement agencies don't participate** in FBI hate-crime reporting.
  - Anomaly example: Florida (3rd most populous state) reported fewer hate crimes than North Carolina (half its population); Florida's 15 largest agencies, covering 40% of residents, reported **19 hate crimes combined** vs. 27 for Charlotte-Mecklenburg alone.
  - **More than 100 federal agencies** failed to report hate-crime data to the FBI's national database.
  - The tip corpus powered dozens of stories, including A.C. Thompson's white-supremacist-network exposés. [inferred: the Atomwaffen/Frontline strand grew out of Documenting Hate tips.]
- **Finding type(s)**: **undercount-by-design**; institutional-coverup/records-suppression (passive: non-reporting); crowdsource-enabled pattern detection
- **Evidence & sources**: crowdsourced incident reports via public form (constructed); social-media newsgathering with verification partners (constructed); FBI Hate Crime Statistics 2007–2016 (open-public); NCVS estimates (open-public); agency-level participation records (open-public).
- **Access tier**: mixed — constructed (crowdsourced corpus) + open-public (federal statistics)
- **Acquisition path**: crowdsourced + bulk-public-data
- **Detection signature**: **two-ledger reporting-gap measurement + zero-report anomaly** — compare the mandated self-report ledger (FBI UCR hate crimes) against an independent victimization estimate (NCVS) and a self-built incident corpus; flag agencies serving 10,000+ residents that report zero or <1 per 100K — treating **missingness itself as the signal** and mapping it.
- **Corroboration structure**: every crowdsourced tip verified by journalists before use (Meedan/Ushahidi workflow); statistical claims anchored in the government's own two contradictory data systems; agency anomalies confirmed with departments directly.
- **Methodology notes**: stated in map piece and launch materials.
- **Impact**: sustained coverage of the reporting gap preceded a federal statute aimed at fixing hate-crime data collection (2021).
- **Generalization**: build-the-missing-registry works wherever mandated reporting is voluntary in practice: use-of-force, workplace injuries (OSHA vs. BLS survey), hospital adverse events, wage theft. Generic detector: (a) ratio of official counts to an independent estimate; (b) rank reporters by population-normalized counts and investigate the zeros; (c) if no registry exists, crowdsource one with a verification layer.

---

### Driven Into Debt / The Ticket Trap (2018) — Chicago's ticket machine pushed tens of thousands of Black motorists into bankruptcy and license suspension
- **URL**: series: https://www.propublica.org/series/driven-into-debt (Melissa Sanchez et al., ProPublica Illinois; Elliott Ramos, WBEZ); app: https://projects.propublica.org/chicago-tickets (Nov 2018)
- **Partner/awards**: Partnership with **WBEZ Chicago**.
- **What they found**:
  - Chicago's 2012 city-sticker fine hike ($120 → $200) generated debt, not compliance: only ~1 in 3 sticker tickets issued in 2016 was paid within a year; motorists owe **$500M+** in sticker-ticket debt since 1990; total ticket debt ~$1B.
  - Black neighborhoods were hit with sticker tickets at higher per-household rates, with police-issued tickets driving the disparity; thousands of mostly Black, low-income motorists filed **Chapter 13 bankruptcy** over ticket debt — fewer than 1 in 4 completed their payment plans.
  - Tens of thousands had driver's licenses suspended over non-driving debt.
- **Finding type(s)**: extraction-from-captive-population (fines/fees as revenue); disparate-impact-by-race-or-geography; **debt-spiral-by-design** (new tag)
- **Evidence & sources**: City of Chicago internal ticket-tracking database via joint FOIA with WBEZ — ~28.3M parking/compliance tickets from 2007 in the first release; the Ticket Trap app covers 54M tickets since 1996 (nerd blog: https://www.propublica.org/nerds/download-chicago-parking-ticket-data); federal bankruptcy dockets (open-public); IL license-suspension records (request-gated); census (open-public); debtor interviews (constructed).
- **Access tier**: mixed — request-gated (city ledger) + open-public (bankruptcy dockets, census)
- **Acquisition path**: FOIA (bulk) + litigation-records (bankruptcy) + interviews
- **Detection signature**: **fine-ledger-to-insolvency join** — the city's complete ticket ledger (issuance, penalty growth, payment status) aggregated per household/zip and joined to Chapter 13 filings and license-suspension records showed a revenue instrument manufacturing insolvency, concentrated by race; a **price-change natural experiment** (2012 hike) showed payment rates collapsing while debt ballooned — projected vs. actual revenue diffed.
- **Corroboration structure**: administrative ledger (primary) → court dockets (primary) → geographic/demographic overlay → named debtor case studies → city's own revenue projections vs. outcomes.
- **Methodology notes**: stated — provenance, plate anonymization, cleaning in the release post; full dataset published for reuse.
- **Impact**: City Council passed ticket/debt-collection reforms — reportedly the largest US city to overhaul fines and fees; license suspensions for non-moving violations ended, licenses restored; sticker debt relief.
- **Generalization**: any fee/fine ledger + insolvency/enforcement join: court fees vs. probation revocation, toll debt vs. registration holds, utility arrears vs. shutoffs, medical debt vs. garnishment. Generic detector: (a) per-capita assessment rates by geography/race; (b) payment-completion curves by neighborhood income; (c) share of a bankruptcy/garnishment docket attributable to one government creditor; (d) before/after of any penalty hike (did revenue rise, or just debt?).

---

### False Witness (2019) — One con man's testimony helped convict dozens, including four men sent to death row, in exchange for undisclosed leniency
- **URL**: https://www.propublica.org/article/hes-a-liar-a-con-artist-and-a-snitch-his-testimony-could-soon-send-a-man-to-his-death (Dec 4, 2019; Pamela Colloff)
- **Partner/awards**: **New York Times Magazine** cover co-publication; 2019 Taylor Family Award; 2020 Hillman Prize for Magazine Journalism.
- **What they found**:
  - Paul Skalnik testified or provided information in **at least 37 cases in Pinellas County, FL alone (1981–1987)**; claimed to have put 34 people in prison including **four on death row**; 18 defendants he informed on faced murder charges.
  - James Dailey was sentenced to death in 1987 largely on Skalnik's claimed jailhouse confession; **Skalnik walked free five days after the sentencing**; benefits were not disclosed to jurors.
  - Skalnik's own ledger: serial fraud/grand theft/forgery arrests; a 1982 child sexual abuse charge **dropped in a plea deal** while he served as an informant; a 1991 no-contest plea to sexual assault of a child.
  - Context: jailhouse-informant testimony figures in ~1 in 5 DNA exonerations and is the leading documented cause of wrongful capital convictions (2004 Northwestern study).
- **Finding type(s)**: **informant-market-corruption** (new tag); statistical-outlier-practitioner (the outlier is a witness); institutional-coverup/records-suppression (undisclosed deals = Brady issues)
- **Evidence & sources**: 50+ public-records requests assembling ~40 criminal case files spanning the 1970s–2010s: police/arrest reports, jail logs, probation/parole records, pretrial interviews, official correspondence, affidavits (request-gated); trial transcripts (open-public); interviews (constructed).
- **Access tier**: request-gated (dominant) + open-public (dockets/transcripts)
- **Acquisition path**: FOIA/records requests + litigation-records + interviews
- **Detection signature**: **career-file assembly on a repeat intermediary** — aggregate every case one recurring witness touched across decades of dockets, align the timeline of his testimony against the timeline of his own charges/releases; the exchange (testimony ↔ leniency) becomes visible even though no single case file discloses it.
- **Corroboration structure**: the state's own records supply both sides of the trade (his testimony in others' files; his dispositions in his own); sworn recantations and correspondence layered on top; pattern contextualized with exoneration-registry statistics.
- **Methodology notes**: records-request scope described in-article and award materials. [inferred: case list reconstructed from court-clerk indexes searched by informant name/aliases.]
- **Impact**: intensified scrutiny of Dailey's death sentence (execution stayed as of publication); fed the state-level movement for informant-disclosure registries and reliability hearings.
- **Generalization**: repeat-intermediary mining transfers directly: expert witnesses in hundreds of trials, CIs in warrant affidavits, notaries on fraudulent deeds, appraisers in mortgage fraud, recurring straw directors in shell networks. Generic detector: frequency-rank all non-party names across a docket/filing corpus; for top outliers, build the career file and time-align appearances against their own benefit ledger (charges dropped, sentence reductions, fees earned).

---

### The NYPD Files (2020) — Publishing the complaint histories 50-a kept secret: 12,056 complaints against nearly 4,000 active officers
- **URL**: https://projects.propublica.org/nypd-ccrb/ (database, Jul 26, 2020; Derek Willis, Eric Umansky, Moiz Syed); data: https://www.propublica.org/datastore/dataset/civilian-complaints-against-new-york-city-police-officers
- **Partner/awards**: ProPublica original; related co-publication with THE CITY on union litigation.
- **What they found**:
  - Published database: **3,996 active-duty officers, 12,056 complaints, 45,778 allegations, September 1985–January 2020** — closed, fully investigated CCRB cases for officers with at least one substantiated allegation.
  - Includes 7,600+ force allegations; discipline for substantiated misconduct was typically trivial (instructions, loss of vacation days), and officers with substantiated findings were promoted.
  - Published while police unions were actively suing to block release — obtained in the window after repeal.
  - Deliberate exclusions documented: unfounded allegations removed; 62 officers with pending administrative prosecutions withheld.
- **Finding type(s)**: institutional-coverup/records-suppression (the repeal-and-release itself); statistical-outlier-practitioner (repeat-complaint officers); **accountability-gap** (substantiated findings vs. trivial discipline)
- **Evidence & sources**: CCRB complaint/allegation/disposition data via records request immediately after the June 2020 repeal of NY Civil Rights Law 50-a (request-gated, newly unlocked); union-litigation filings (litigation-records); detailed complaint reports via partner FOIL (request-gated).
- **Access tier**: request-gated (post-repeal records request)
- **Acquisition path**: FOIA — a **statute-change-triggered request** filed the moment a secrecy law fell
- **Detection signature**: **secrecy-repeal arbitrage + publish-the-database** — when a confidentiality statute is repealed, immediately request the entire historical record set before litigation re-seals it; the primary journalistic product is the queryable database itself, from which outlier officers and the substantiation→discipline gap fall out as derived findings.
- **Corroboration structure**: the agency's own investigative dispositions are the evidence; editorial layer = published data dictionary, documented inclusion/exclusion rules, per-record provenance; civil-suit settlements used as a second ledger on the same officers.
- **Methodology notes**: stated on the database's about page (scope, exclusions, caveats, staleness warning); full CSV released in the Data Store.
- **Impact**: became the public reference for NYPD misconduct histories; CCRB subsequently launched its own public officer-history database (Mar 2021).
- **Generalization**: monitor transparency-law changes (repeals, sunsets, court rulings) as acquisition events; file day-one requests for the full historical archive, then publish structured data with explicit inclusion rules. Applies to police records (California SB 1421 analogs), sealed regulatory actions, newly unsealed court archives, declassification tranches. Generic detector on the data: practitioners with N substantiated findings vs. discipline actually imposed.

---

### The Kids of Rutherford County (2021) — A Tennessee county jailed children under an invented charge and an illegal "filter system," at ~10x the state detention rate
- **URL**: https://www.propublica.org/article/black-children-were-jailed-for-a-crime-that-doesnt-exist (Oct 8, 2021; Meribah Knight, Nashville Public Radio/WPLN; Ken Armstrong, ProPublica)
- **Partner/awards**: ProPublica Local Reporting Network with **WPLN News/Nashville Public Radio**; four-part **Serial Productions** podcast (Oct 2023).
- **What they found**:
  - April 15, 2016: police arrested **11 Black children** (youngest 8) over a schoolyard scuffle — including children who merely watched — under **"criminal responsibility for conduct of another," a charge that does not exist** in Tennessee law; judicial commissioners devised it after consulting the code.
  - Under Judge Donna Scott Davenport's standing process, all arrested juveniles went to the detention center, where an undefined **"filter system"** ("TRUE threat" standard) let jailers decide whom to hold: the county detained **48% of juvenile cases vs. a 5% statewide average** — nearly 10x the state rate by 2014.
  - Plaintiffs' lawyers estimated ~**500 wrongful arrests and ~1,500 illegal filter-system detentions**; 50+ children jailed for status offenses.
  - State oversight failed: DCS missed the illegal system in nine inspections; the county reported "unknown" for 90% of detention dispositions (2005–09), and the state stopped publishing the comparative statistics that would have exposed the outlier.
- **Finding type(s)**: due-process-bypass; **enforcement-without-legal-basis** (charge does not exist); extraction-from-captive-population (detention as default); disparate-impact-by-race-or-geography; undercount-by-design (the "unknown" reporting)
- **Evidence & sources**: 50+ public-records requests (request-gated); **38 hours of internal police-investigation audio** (request-gated internal record); depositions of the judge and detention director + settlement agreements from seven federal lawsuits (litigation-records); Board of Judicial Conduct records; detention-center operating procedures (the rulebook); 137 county-commission meeting recordings; 12+ personnel files.
- **Access tier**: mixed — request-gated (internal investigation, procedures) + litigation-records (depositions) + open-public (court filings)
- **Acquisition path**: FOIA saturation + litigation-records + interviews
- **Detection signature**: **internal-rulebook acquisition + outlier-in-aggregate-statistics** — the detention center's own written "filter system" procedure proved illegality by its text; the 48%-vs-5% detention rate was the quantitative outlier flag; and a **charge-validity audit** (matching the charge on arrest paperwork against the actual criminal code) showed the offense did not exist. Federal-lawsuit depositions supplied sworn admissions the records requests could not.
- **Corroboration structure**: the institution's own documents and recorded voices (procedures, internal-affairs tapes, the judge's depositions) → court findings (federal judge: system "departs drastically" from law) → state inspection/data-reporting records showing oversight failure → named-cohort reconstruction of the 11 kids.
- **Methodology notes**: records inventory described in-article and in the reporter's essay; data follow-up documented disproportionality worsening.
- **Impact**: filter system ordered eliminated (2017); juvenile solitary banned by federal court (2016); class settlement **up to $11M** plus $397,500 for the 11 children; near-zero individual accountability documented at publication; Serial podcast season (2023).
- **Generalization**: three portable detectors: (a) **charge-validity audit** — join charge codes on arrest/citation records to the authoritative statute table; nonexistent/repealed/inapplicable codes are automatic findings (also works for tax penalty codes, billing codes, HOA fines); (b) jurisdiction-level outlier rates vs. peer average on any discretionary deprivation (detention, seclusion, involuntary commitment, expulsion); (c) when an agency's stats go "unknown"-heavy or a comparative report is discontinued, treat the disappearance as a flag.

---

## Adjacent verified entries (abbreviated)

### Criminal Justice in Elkhart, Indiana (2018–19) — In one police department, 28 of 34 supervisors had disciplinary records; wrongful convictions followed
- **URL**: https://www.propublica.org/article/nearly-all-officers-in-charge-of-elkhart-indiana-police-department-have-been-disciplined (Christian Sheckler, South Bend Tribune; Ken Armstrong, ProPublica Local Reporting Network)
- **What they found**: 28 of 34 supervisors (chief to sergeant) had disciplinary records, some criminal; the detective behind the Keith Cooper/Christopher Parish wrongful convictions had been forced out over sexual misconduct with an informant; the elected prosecutor faced a misconduct complaint for contradictory allegations across cases.
- **Finding type(s)**: statistical-outlier-practitioner (an outlier *institution*); wrongful-conviction-production; institutional-coverup/records-suppression.
- **Evidence/access/acquisition**: personnel, disciplinary, and internal-affairs files plus decades-old case files (request-gated FOIA); court records (open-public); station-house beating video (request-gated).
- **Detection signature**: **personnel-file denominator** — request disciplinary files for the *entire* command roster and compute the disciplined fraction (28/34), converting anecdote into an institutional rate; plus cold-case-file re-excavation.
- **Impact**: police chief resigned; two officers federally charged (one guilty plea); Cooper received Indiana's largest wrongful-conviction settlement, $7.5M.
- **Generalization**: request the full leadership roster's disciplinary/complaint files for any institution and compute the rate — outlier institutions (not just individuals) predict downstream harms.

### TIGER, the Algorithm Banning Louisiana Prisoners From Parole (2025) — A static risk score now cancels parole hearings outright
- **URL**: https://www.propublica.org/article/tiger-algorithm-louisiana-parole-calvin-alexander (Apr 10, 2025; Richard A. Webster, ProPublica, with **Verite News**)
- **What they found**: a 2024 Louisiana law ceded parole-board gatekeeping to TIGER, a risk score built ~a decade earlier for programming needs, not release decisions (per its own creator); Louisiana is the only state using risk scores to automatically exclude prisoners from parole consideration (per seven national experts); **Aug 1–Dec 13, 2024: at least 70 hearings canceled**; inputs are immutable pre-prison facts (age at first arrest, work history, marijuana convictions, prior revocations) — in-prison rehabilitation cannot change the score.
- **Finding type(s)**: algorithmic-or-systematic-denial; **algorithmic-eligibility-gate** (new tag: score used as an absolute gate, not an input); due-process-bypass.
- **Detection signature**: **rule-change-to-outcome trace** — diff the decision process before/after a statutory change, count decisions now made solely by the algorithm, and interrogate the input schema for immutability (can the affected person ever change the outcome? If no: gate, not assessment).
- **Generalization**: audit any scoring system promoted from advisory to dispositive (tenant screening, benefits-fraud scores, no-fly lists): the story is often the *promotion*, not the model. Detector: input-schema immutability + absence of appeal path.

---

## New taxonomy tags coined in this cluster

**Finding types**: `accountability-gap`; `wrongful-conviction-production`; `victim-disbelief-failure`; `civil-process-weaponization`; `enforcement-without-legal-basis`; `undercount-by-design`; `debt-spiral-by-design`; `informant-market-corruption`; `algorithmic-eligibility-gate`.

**Detection signatures**: `sanction-outcome-diff` (subtype of two-books-diff); `retest-the-evidence` (two-books-diff via confirmatory-test ledger); `plea/process-timing-analysis` (adjudication timestamp vs. evidence timestamp); `career-file-assembly` (repeat-intermediary mining; extends named-cohort-tracing); `zero-report-anomaly` (missingness as signal); `ex-parte-rate-measurement`; `statute/charge-validity-audit`; `personnel-file-denominator`; `secrecy-repeal-arbitrage` (statute-change-triggered acquisition); `fine-ledger-to-insolvency-join`; `rule-change-to-outcome-trace`; `records-request-saturation`; `field-observation-control`.

---

## Cluster Synthesis

### 1. Recurring evidence-source types (frequency across 14 entries)

| Source type | Count | Entries |
|---|---|---|
| Bulk administrative microdata (FOIA'd or published ledgers: scores, tickets, complaints, homicide reports, citations) | 7 | Machine Bias, Ticket Trap, Walking While Black, NYPD Files, Deadly Force, Documenting Hate, Nuisance Abatement |
| Court records at case level (dockets, opinions, transcripts, bankruptcy filings) | 8 | Busted, Out of Order, False Witness, Nuisance Abatement, Rutherford, Elkhart, Ticket Trap, Unbelievable |
| The institution's own internal records (lab retests, personnel files, internal-affairs tapes, SOPs/rulebooks, the algorithm itself) | 7 | Busted, Elkhart, Rutherford, NYPD Files, Machine Bias, Unbelievable, TIGER |
| Litigation-derived records (depositions, settlements, civil-suit files) | 5 | Rutherford, Elkhart, Nuisance Abatement, Out of Order, False Witness |
| Census/population denominators | 4 | Deadly Force, Walking While Black, Ticket Trap, Documenting Hate |
| Affected-cohort interviews | 7 | Busted, Unbelievable, Rutherford, Ticket Trap, Nuisance Abatement, False Witness, TIGER |
| Crowdsourced/constructed corpora & field observation | 2 | Documenting Hate, Walking While Black |

Notable: leaks play almost **no role** in this cluster (the famous NYPD leak was BuzzFeed's). ProPublica's criminal-justice canon runs overwhelmingly on **request-gated public records + open dockets** — fully reproducible by an OSINT platform with FOIA capability and docket access. Highest-yield acquisition moves observed: **file for the entire historical record set the moment a secrecy rule falls** (NYPD Files), and **request the government's copy of a proprietary system's outputs** (Machine Bias — scores were public records even though the algorithm wasn't).

### 2. Recurring detection signatures (frequency)

| Signature | Count | Entries |
|---|---|---|
| Denominator-construction (per-capita/per-roster rates by race, geography, or institution) | 6 | Deadly Force, Walking While Black, Ticket Trap, Documenting Hate, Elkhart, Rutherford |
| Two-books-diff family (sanction-outcome diff; retest ledger; self-report vs. independent estimate; substantiation vs. discipline) | 5 | Out of Order, Busted, Documenting Hate, NYPD Files, False Witness |
| Named-cohort-tracing (follow N affected people/cases to outcomes) | 5 | Busted (416 variants), Nuisance Abatement, Out of Order, False Witness (37 cases), Rutherford (11 kids) |
| Internal-rulebook-acquisition (the SOP, the questionnaire, the score matrix, the boilerplate settlement) | 4 | Rutherford, Machine Bias, TIGER, Nuisance Abatement |
| Silo-join-on-hard-identifier (name+DOB or case number across systems) | 3 | Machine Bias, Ticket Trap, Walking While Black |
| Statute/charge-validity-audit (does the legal predicate exist?) | 3 | Walking While Black, Rutherford, Nuisance Abatement |
| Ground-truth-construction | 2 deep | Machine Bias, Busted (retest as ground truth) |
| Process-timing-analysis (adjudication vs. evidence timestamps; ex parte rates) | 2 | Busted, Nuisance Abatement |
| Outlier-in-aggregate + zero-report anomaly | 3 | Rutherford (48% vs 5%), Documenting Hate (FL vs NC; zeros), Elkhart (28/34) |
| Crowdsourced-case-aggregation | 1 | Documenting Hate |

### 3. Transferable pattern candidates

**P1. Audit-the-scorer (ground-truth-construction).** Obtain a scoring/screening system's historical decisions with subject identifiers (the government/enterprise copy is often a public or discoverable record even when the model is proprietary); independently construct the outcome variable the system claims to predict from a second record system; join on hard identifiers with an explicit match-error audit; compute error rates **conditional on protected class or segment**, replicating the vendor's own validation window so results are undismissable; publish data+code for adversarial replication. *Minimum data*: decision ledger with identities; outcome records covering the same cohort and horizon; class attributes. *Agent looks for*: any consequential score (credit, tenant, fraud, hiring, AML, child-welfare, parole) plus any downstream outcome ledger; weaker one-ledger version = score distributions across matched cohorts. Escalation flag: a score promoted from advisory to **dispositive gate** (TIGER pattern) with immutable inputs.

**P2. Sanction-outcome diff (accountability-gap detector).** Harvest authoritative findings of wrongdoing from ledger A (appellate opinions citing misconduct, substantiated complaints, lab-confirmed errors, IG findings), then join the responsible party into ledger B — the discipline/license/career registry. The systematic absence of consequences (or presence of promotions) is the finding, and it is computable. *Minimum data*: a searchable adjudication corpus; a sanction/roster registry; name resolution. *Agent looks for*: professions with dual ledgers — prosecutors/bar, police/IA, doctors/boards, brokers/FINRA, auditors/PCAOB, contractors/debarment. High-value variant: time-align an individual's benefit ledger with their cooperation ledger (False Witness) to expose undisclosed exchange.

**P3. Authority-validity audit (enforcement without legal basis).** For each enforcement action in a bulk ledger, verify the legal and physical predicates actually exist: the charged statute exists and applies (Rutherford's nonexistent crime), the required infrastructure exists (Walking While Black's missing traffic signals, checkable via imagery/GIS), a conviction underlies the punishment (nuisance abatement's 173 never-convicted). *Minimum data*: enforcement ledger with statute codes and locations; the authoritative code table; imagery or docket access for predicates. *Agent looks for*: charge codes not in the statute table; citations whose geo-predicates fail; civil punishments joined to empty criminal dockets. Generalizes to billing-code validity (upcoding), fee-schedule conformance, license-condition enforcement.

**P4. Two-ledger undercount measurement (missingness as signal).** Compare mandated self-reported statistics against an independent estimate (victimization survey, claims data, a crowdsourced registry you build), and rank reporting units per-capita to find implausible zeros; treat discontinued comparative reports and "unknown"-heavy fields as affirmative flags. *Minimum data*: official counts by reporting unit; any independent proxy; population denominators. *Agent looks for*: zero-report anomalies among large units; official-to-proxy ratios far from peers; data series that stop publishing right when an outlier would show. Generalizes to OSHA logs vs. injury claims, SAR filings vs. fraud losses, adverse-event reporting, environmental self-monitoring.

**P5. Captive-population extraction trace (fines/fees → insolvency join).** Take a government/institutional assessment ledger (tickets, court fees, room-and-board, commissary), compute per-capita burden by geography/race, then join debtors into insolvency/enforcement systems (bankruptcy dockets, license suspensions, garnishments, probation revocations) to show the penalty system manufacturing the harm it punishes; exploit any price hike as a natural experiment (projected vs. actual revenue — the diff exposes the extraction rationale failing on its own terms). *Minimum data*: assessment ledger with geography; payment/collection outcomes; an enforcement/insolvency docket to join. *Agent looks for*: one creditor dominating a bankruptcy docket; payment-completion curves collapsing below an income threshold; penalty escalation exceeding principal; suspension-of-livelihood used as a collection tool.

*(Runner-up: **secrecy-repeal arbitrage** — monitor transparency-law changes as acquisition events and file day-one requests for the full historical archive; an acquisition pattern rather than a detection pattern, but it produced the cluster's largest single dataset.)*
