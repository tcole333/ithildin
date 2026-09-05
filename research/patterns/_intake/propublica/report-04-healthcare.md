# ProPublica Evidence Ontology — Cluster 04: Healthcare, Pharma & Insurance

Reviewed: 2026-07-28. Method: live-site verification via web search + direct fetches of propublica.org story pages, methodology pages, and partner sites (MLK50, PBS Frontline, CMS, Senate). 14 entries + attribution corrections. All claims carry URL citations; stated methodology is quoted or cited, inferences are marked `[inferred]`.

**Attribution corrections applied (candidates dropped from scope):**
- **Organs damaged/lost in transit** — NOT ProPublica. The lost-in-transit investigation was Kaiser Health News + Reveal (2020); the UNOS "organs arriving late, damaged or diseased" reporting followed the Senate Finance Committee's two-year inquiry and was covered by NPR/KHN (2022). Dropped.
- **For-profit psychiatric hospitals** — the landmark chain exposés were BuzzFeed News (UHS, 2016) and The New York Times (Acadia, 2024), not ProPublica. Dropped.
- **"Diagnosis: Debt"** — KHN/NPR (2022), not ProPublica. ProPublica's medical-debt entry point is the Methodist Le Bonheur partnership with MLK50. Dropped.
- **Medicare Advantage nH Predict AI denials** — STAT News, not ProPublica. ProPublica's algorithmic-denial work is Cigna PxDx, EviCore, and UnitedHealth ALERT.

---

### Dollars for Docs (2010–2019) — Pharma's payroll of physicians made searchable before the government's own database existed
- **URL**: https://projects.propublica.org/docdollars/ (app); https://www.propublica.org/series/dollars-for-docs (series); provenance: https://www.propublica.org/article/about-our-pharma-data and https://www.propublica.org/article/about-the-dollars-for-docs-data
- **Partner/awards**: Database shared at launch with NPR and other outlets.
- **What they found**:
  - Launch (Oct 2010): $257.8M in payments from seven companies (AstraZeneca, Cephalon, Eli Lilly, GSK, J&J, Merck, Pfizer) to ~17,700 providers; 384 providers earned >$100K in 2009–2010.
  - Hundreds of paid speakers/consultants had disciplinary records or thin credentials.
  - By 2013 the archive covered 17 companies, ~$4B, 2009–2013 — companies representing "about half of the U.S. market in 2013."
  - Finale (2019): 700+ doctors received >$1M from drug/device makers; >2,500 received ≥$500K over five years of Open Payments data.
  - 2016 join analysis: doctors taking industry money prescribe more brand-name drugs, with a dose-response gradient (internists with no payments ~20% brand-name rate vs ~30% for those receiving >$5,000; 9 in 10 cardiologists over the claims threshold took payments).
- **Finding type(s)**: undisclosed-financial-conflict (payments→prescribing); statistical-outlier-practitioner (million-dollar recipients; disciplined-doctor speakers)
- **Evidence & sources**:
  - [settlement-mandated corporate disclosure] Company payment webpages posted "as part of settlements in whistleblower lawsuits" — the original seven companies
  - [regulatory bulk data] CMS Open Payments (post-Sunshine Act, Aug 2013 onward)
  - [regulatory bulk data] Medicare Part D prescribing data (for the join)
  - [government records] State medical board disciplinary files (speaker-vetting story)
  - [commercial data] 2013 disclosures partly supplied by Obsidian HDS/Pharmashine
- **Access tier**: mixed — constructed (scraping/parsing hostile company disclosure formats: "some of the firms published the data on their websites in a way that made it nearly impossible to analyze or, in some cases, even download") + open-public (Open Payments era) + commercial-data
- **Acquisition path**: scrape → bulk-public-data → commercial-data; disclosures existed only because of DOJ whistleblower settlements (settlement-mandated-disclosure-harvest — new acquisition tag)
- **Detection signature**: (1) Aggregation-as-detection: 17 incompatible company disclosure silos normalized into one searchable per-physician ledger revealed cumulative individual totals no single silo showed. (2) Open Payments joined to Medicare Part D prescriber file on physician identity (NPI-era) revealed payment-tier vs brand-name-prescribing-share dose-response. (3) Paid-speaker roster joined to state medical board discipline records revealed pharma QA failure.
- **Corroboration structure**: Companies confirmed their own data (it was their disclosure); named doctors given comment opportunity; explicit causation caveat preserved ("ProPublica's analysis doesn't prove industry payments sway doctors to prescribe particular drugs"); board records as independent second silo.
- **Methodology notes**: Stated: about-our-pharma-data (normalization pain: "Each firm reported its spending differently"); about-the-dollars-for-docs-data (Open Payments version details; NPs/PAs excluded because reporting wasn't required); join methodology inside the 2016 article (≥1,000 Part D prescriptions threshold; five specialties).
- **Impact**: Companies cut speaker payments as scrutiny mounted. D4D became the de facto public interface until CMS Open Payments matured; database retired in favor of CMS's own site. Note: the Sunshine Act (ACA, March 2010) predates the October 2010 launch — D4D accelerated disclosure culture and usability, it did not cause the statute.
- **Generalization**: Any influence-spend disclosure regime (lobbying, FARA, FEC, EU transparency registers, state gift registries) + any behavior ledger keyed by the same professional registry ID. Generic detector: normalize fragmented mandated disclosures into one per-recipient ledger; join to the recipient's decision/output stream; rank by cumulative payment and test behavior gradient by payment tier.

---

### Prescriber Checkup (2013– ) — Medicare Part D's blind spot: outlier prescribers of antipsychotics and opioids the government never monitored
- **URL**: https://www.propublica.org/article/part-d-prescriber-checkup-mainbar ; methods: https://www.propublica.org/article/how-we-analyzed-medicares-drug-data-long-methodology and https://www.propublica.org/article/prescriber-checkup-our-methods
- **Partner/awards**: ProPublica original.
- **What they found**:
  - A Miami psychiatrist wrote 8,900 antipsychotic prescriptions in 2010 for patients 65+, many with dementia, despite black-box warnings.
  - The nation's top clozapine prescriber, Dr. Michael Reinstein, was later sentenced to 9 months in prison (March 2016) for taking kickbacks from the drug's makers — an outlier the data had surfaced.
  - CMS "had never allowed outsiders to access" prescriber-level Part D records and did not itself monitor prescribing patterns for fraud/safety.
- **Finding type(s)**: statistical-outlier-practitioner; regulatory-capture (payer as passive check-writer — new tag: passive-payer-nonsurveillance)
- **Evidence & sources**:
  - [request-gated federal data] Medicare Part D prescriber-level aggregates "obtained under the Freedom of Information Act"
  - [government records] Court records for prosecutions (Reinstein)
  - [interviews] Outlier prescribers themselves, pharmacologists, state regulators
- **Access tier**: request-gated (FOIA) at launch → open-public from April 2015 ("In April 2015, the Centers for Medicare and Medicaid Services began releasing the information on its website")
- **Acquisition path**: FOIA → bulk-public-data
- **Detection signature**: Per-provider-per-drug claim counts (with NPI) compared against specialty × state peer distribution; flag at ≥2 standard deviations from the peer mean; suppress comparisons where peer cell <20 providers; display only providers with ≥50 claims for a drug; CMS privacy redaction of cells ≤10 claims. Drug-risk overlays (opioid/antipsychotic/AGS "risky for seniors" lists) turn volume outliers into harm hypotheses.
- **Corroboration structure**: Data outlier → direct interview with the prescriber → medical-board/court records → expert clinical review. The methodology explicitly lists innocent explanations to exclude (shared NPI billing arrangements, long-term-care specialization, no-generic drug classes).
- **Methodology notes**: Stated in full at how-we-analyzed-medicares-drug-data-long-methodology — file scope (Part D claims incl. refills; excludes hospital/SNF-administered drugs paid under Parts A/B), 2015 file ≈1.4M providers/1.4B claims, metrics per provider-drug pair.
- **Impact**: CMS reversed its position and began annual public release of prescriber-level Part D data (April 2015); Reinstein prosecution outcome; contributed to Part D integrity tightening [inferred].
- **Generalization**: Identical machinery for any payer/professional claims universe: Medicaid T-MSIS, workers' comp pharmacy, DEA ARCOS, state PDMPs, dental/optometry billing, attorney billing to courts, guardianship fees. Generic detector: entity-level transaction aggregates + peer-group z-score + minimum-denominator guard + domain risk-list overlay. Our Medicare/Medicaid tooling can replicate this directly.

---

### Surgeon Scorecard (2015) — Individual surgeons' complication rates computed from Medicare claims; the methodology fight is part of the lesson
- **URL**: https://projects.propublica.org/surgeons/ ; methodology: https://www.propublica.org/article/surgeon-level-risk-short-methodology
- **Partner/awards**: ProPublica original (Olga Pierce, Marshall Allen). No major award; instead a formal methods controversy (RAND critique + peer-reviewed evaluation).
- **What they found**:
  - Complication rates for ~17,000 surgeons across 8 elective procedures; ~11% of surgeons accounted for ~25% of complications; hundreds ran double/triple the national rate.
  - Variation was surgeon-level, not just hospital-level — high-complication surgeons operated inside elite hospitals.
- **Finding type(s)**: statistical-outlier-practitioner; institutional-coverup/records-suppression (secondary — data existed inside CMS but was never published at surgeon grain)
- **Evidence & sources**:
  - [government microdata] Medicare inpatient billing records (hospital stays), 2009–2013
  - [expert panels] "a panel of at least five doctors" per procedure reviewed principal diagnosis codes on readmissions
  - [interviews] Patients, surgeons, hospital safety officers
- **Access tier**: request-gated [inferred — CMS research-data-use agreement is the standard path]
- **Acquisition path**: bulk-public-data (restricted government microdata under agreement) + interviews
- **Detection signature**: Denominator construction is the whole game: (1) restrict to 8 elective procedures; (2) exclude trauma/high-risk, ED admissions, and transfers to isolate scheduled comparable cases; (3) outcome = in-hospital death or 30-day readmission with procedure-related principal diagnosis, single-counted; (4) attribute case to operating surgeon; (5) mixed-effects model with fixed patient factors and surgeon/hospital random effects; (6) empirical Bayes shrinkage pulls low-volume extremes toward the mean; (7) suppress below 20 cases.
- **Corroboration structure**: Physician panels validated the complication code list; named-patient narratives matched to claims patterns; RAND's external critique and ProPublica's published response functioned as adversarial peer review after publication.
- **Methodology notes**: Stated: short methodology + longer technical white paper (https://static.propublica.org/projects/patient-safety/methodology/surgeon-level-risk-methodology.pdf). The controversy (readmission ≠ complication; risk-adjustment adequacy) is itself instructive: publish the model, expect methodological siege, pre-recruit clinical validators.
- **Impact**: Forced the surgeon-level transparency debate into the open; RAND/academic responses shaped subsequent outcome-measure design. Scorecard not maintained after 2015/2016 [inferred].
- **Generalization**: Practitioner-level outcome scoring from any transactional system with (a) an operator identifier, (b) a comparable elective event, (c) a downstream failure event linkable to the operator. Analogues: contractor rework/change-orders, auditor restatement rates, judge reversal rates, pilot incidents. Generic detector needs the same three guards: elective-only denominator, risk adjustment, small-n shrinkage/suppression — otherwise the output is noise and reputational libel risk.

---

### God Help You. You're on Dialysis. (2010) — A universal-entitlement industry with First World costs and Third World outcomes
- **URL**: https://www.propublica.org/article/in-dialysis-life-saving-care-at-great-risk-and-cost (co-published with The Atlantic, Dec 2010); series: https://www.propublica.org/series/dialysis ; data app: https://projects.propublica.org/dialysis/
- **Partner/awards**: The Atlantic; finalist, 2011 National Magazine Award for Public Interest.
- **What they found**:
  - 1 in 4 U.S. dialysis patients dies within 12 months of starting treatment vs ~1 in 9 in Italy; taxpayer cost $20B+/yr, ~$77K/patient/yr — worst-of-both-worlds outcome/cost pairing.
  - Duopoly extraction: DaVita + Fresenius operated ~two-thirds of ~5,000 clinics; combined 2009 operating profits $2.2B.
  - Six-state inspection review (2002–2009): nearly half of clinics cited for unsanitary/unsafe conditions; ~10% of facilities went years without full inspection; CMS terminated just 16 facilities 2000–2008 and "can demand correction plans but cannot fine violators."
  - CMS held clinic-level outcome data confidential for decades.
- **Finding type(s)**: extraction-from-captive-population; regulatory-capture (no intermediate sanctions); institutional-coverup/records-suppression (withheld facility outcomes)
- **Evidence & sources**:
  - [government inspection records] Thousands of state/CMS clinic inspection reports (6 states, 2002–2009)
  - [request-gated federal data] Clinic-specific outcome data via FOIA
  - [state data] Texas clinic outcome data 2007–09
  - [interviews] 100+ patients, doctors, policymakers, experts
  - [named-case records] Individual deaths reconstructed from inspection files
- **Access tier**: mixed — request-gated (FOIA outcomes) + open-public (inspection reports, scattered) + constructed (six-state inspection corpus assembly)
- **Acquisition path**: FOIA + bulk-public-data + interviews
- **Detection signature**: (1) Cross-national outcome benchmarking on a condition with a fixed global clinical standard — same treatment, same payer generosity, divergent mortality → structural extraction hypothesis. (2) Inspection-deficiency corpus aggregated across states vs enforcement-action count (16 terminations in 9 years) = enforcement-gap ratio. (3) Chain-level profit vs staffing/treatment-duration measures.
- **Corroboration structure**: Inspection citations (regulator's own words) anchor each named death; international registry comparisons; industry financials from SEC filings; FOIA'd outcomes quantified what anecdotes illustrated.
- **Methodology notes**: [inferred from article text] — no standalone methods page found.
- **Impact**: CMS released facility-level outcome data → ProPublica's Dialysis Facility Tracker made it public-facing; fed the 2012 bundled-payment/QIP debate.
- **Generalization**: Any per-diem/per-treatment entitlement with a captive clinical population and chain consolidation: nursing homes, hospice, methadone clinics, group homes, detention medical care. Generic detector: (payer generosity × chain concentration × inspection-deficiency rate) ÷ enforcement actions; cross-jurisdiction outcome benchmark where the clinical standard is fixed.

---

### Life and Death in Assisted Living (2013) — The largest assisted-living chain filled beds with residents too sick for its staffing model
- **URL**: https://www.propublica.org/article/emeritus-1-the-emerald-city ; Frontline film: https://www.pbs.org/wgbh/frontline/documentary/life-and-death-in-assisted-living/
- **Partner/awards**: PBS Frontline (A.C. Thompson, Jonathan Jones, Carl Byker).
- **What they found**:
  - Emeritus Corp.: ~500 facilities in 45 states, the nation's largest assisted-living operator, admitting patients "too medically complex for assisted living" to meet occupancy targets during the 2008 recession.
  - Joan Boice, 81, Alzheimer's, paid $7,125/month for "memory care"; facility cycled through four nurses in three years, sometimes no full-time nurse; internal complaint described "a huge shortage of staff."
  - Reporters reviewed 100+ lawsuits and thousands of pages of inspection records across CA, TX, OH, IA, MS, GA — deaths included a Texas resident who froze outdoors on Christmas morning.
  - Structural finding: assisted living is state-regulated, far weaker than federally regulated nursing homes, while housing a nursing-home-acuity population.
- **Finding type(s)**: extraction-from-captive-population; fraud-enablement-by-design (occupancy/revenue targets vs care capacity); regulatory-tier-arbitrage (new tag — operating nursing-home-acuity beds under lighter assisted-living rules)
- **Evidence & sources**:
  - [litigation records] 100+ lawsuits incl. discovery exhibits (internal audits, emails)
  - [state inspection records] Six states, five years
  - [internal documents] Company audit findings, staffing complaints (via litigation/leak)
  - [interviews] Former nurses, executives, families
  - [financial filings] SEC filings on occupancy economics
- **Access tier**: mixed — open-public (dockets, inspections, SEC) + privileged (internal documents via litigation discovery) + constructed (multi-state inspection corpus)
- **Acquisition path**: litigation-records + bulk-public-data + interviews + field-observation (film)
- **Detection signature**: Occupancy/revenue-pressure documents (internal targets) joined to acuity of admitted residents (from lawsuits/inspections) — the mismatch between marketed care level and licensed/staffed care level is the finding. Cross-state inspection aggregation defeats the state-by-state regulatory fragmentation that hides chain-level patterns.
- **Corroboration structure**: Litigation exhibits (company's own audits) → inspection citations (state's words) → former-staff interviews → named-death reconstructions; film adds on-camera admissions.
- **Impact**: Jury verdict for the Boice family with a large punitive award [inferred — ~$23M widely reported]; national scrutiny of assisted-living regulation.
- **Generalization**: Regulatory-tier arbitrage detector: chains housing high-acuity populations under the lowest available licensure tier. Look for marketing above licensure level, internal occupancy targets, citations for care beyond license scope. Applies to sober homes, community-release detention alternatives, unlicensed group homes, day-care overcapacity.

---

### Insult to Injury / The Demolition of Workers' Comp (2015) — 33 states quietly dismantled the century-old wage-for-injury bargain
- **URL**: https://www.propublica.org/article/the-demolition-of-workers-compensation (with NPR; Michael Grabell, Howard Berkes); opt-out exposé: https://www.propublica.org/article/inside-corporate-americas-plan-to-ditch-workers-comp
- **Partner/awards**: NPR; Edward R. Murrow Award, News Series.
- **What they found**:
  - 33 states cut benefits or restricted eligibility since 2003; Florida cut severely-disabled compensation 65% since 1994.
  - Grotesque cross-state body-part pricing: maximum for loss of an eye $27,280 (Alabama) vs $261,525 (Pennsylvania) — ~10x spread for identical injury.
  - Employers paid the lowest comp rates in 25 years while insurers had their most profitable year in a decade (18% return, 2013).
  - ~$30B/yr in injury costs shifted onto taxpayers; TX/OK opt-out laws let employers write their own benefit plans.
- **Finding type(s)**: benefit-erosion-by-statute (new tag); two-books-asymmetry (employer "cost crisis" lobbying narrative vs historic-low premiums); regulatory-capture (industry-drafted state legislation)
- **Evidence & sources**:
  - [statute/schedule compilation] Benefit schedules and comp statutes across all 50 states
  - [industry data] Insurance-industry rate and profitability datasets
  - [confidential records] Workers' medical and court files (with consent)
  - [interviews] Injured workers, regulators, John Burton (Nixon-commission chair)
  - [corporate documents] Employer-written opt-out plan documents
- **Access tier**: mixed — open-public (statutes, schedules) + commercial/industry data + privileged (workers' own files, shared)
- **Acquisition path**: bulk-public-data (50-state statute compilation) + commercial-data + interviews + litigation-records
- **Detection signature**: Cross-jurisdiction-statute-diff (new tag): normalize 50 state benefit schedules into a comparable unit (dollar value per scheduled body part; weekly caps; duration limits) and diff across states and time. Second signature: two-books diff between the industry's legislative "cost crisis" claims and its own premium/profit trend.
- **Corroboration structure**: Statutory text (primary) → industry's own financial data → named workers whose case files instantiate each statutory cut → architect interviews (the lawyer drafting opt-out plans on record).
- **Methodology notes**: methodology page exists: https://www.propublica.org/article/workers-comp-benefits-how-much-is-a-limb-worth-methodology
- **Impact**: OSHA report explicitly echoed the findings; Labor Department review; Oklahoma Supreme Court struck down opt-out, stalling the national campaign.
- **Generalization**: Any federated benefit system administered state-by-state (unemployment insurance, Medicaid eligibility, tort caps, staffing laws). Generic detector: normalized cross-state benefit table; large spreads + monotonic cut-trend + model-legislation fingerprints (identical statutory language across states) = coordinated erosion campaign.

---

### Lost Mothers (2017–18) — Counting and naming the mothers the CDC counts but doesn't identify
- **URL**: series: https://www.propublica.org/series/lost-mothers ; methodology: https://www.propublica.org/article/how-we-collected-nearly-5-000-stories-of-maternal-harm
- **Partner/awards**: NPR. 2017 Peabody Award; Goldsmith Prize finalist; NABJ Salute to Excellence.
- **What they found**:
  - Identified 134 women who died from pregnancy-related causes in 2016 — hand-assembling the named cohort behind the CDC's anonymous aggregate (~700–900/yr).
  - ~5,000 crowdsourced submissions across all 50 states; 4,000+ documented near-misses (severe maternal morbidity) — the death count is the tip of a morbidity iceberg.
  - Black women die at 3–4x the white rate; the first 2,500 submissions included <75 from Black mothers → targeted outreach redesign mid-investigation.
- **Finding type(s)**: anonymized-aggregate-accountability-gap (new tag — official statistics without names or cases); systemic preventable-harm undercount
- **Evidence & sources**:
  - [crowdsourced] Public callout — ~2,500 responses in days, ~5,000 total
  - [social-platform exhaust] Systematic searches of public Facebook posts, Twitter, GoFundMe, YouCaring for pregnancy-death fundraisers/memorials
  - [public records] Obituaries and public records to verify each identity
  - [distribution partners] Cosmopolitan, The Root, Texas Tribune, Univision (Spanish) to reach missing demographics
  - [agency data] CDC pregnancy-mortality surveillance as denominator frame
- **Access tier**: constructed (crowdsource + scrape) with open-public verification layer
- **Acquisition path**: crowdsourced + scrape + interviews
- **Detection signature**: Crowdsourced-denominator-reconstruction: when official statistics exist only as anonymous aggregates, rebuild the named case list from social exhaust (fundraisers are high-precision death markers with dates, causes, families) + obituary verification, then compare the reconstructed cohort against the official aggregate to expose what anonymization hides (preventability, hospital identity, race patterns).
- **Corroboration structure**: Every crowdsourced case verified against obituary/public record; family interviews; medical experts reviewed care narratives; official CDC data used as frame, never as substitute for cases.
- **Methodology notes**: Stated in full — including the demographic-bias correction, a rare published example of sampling-bias remediation in crowdsourcing.
- **Impact**: Preventing Maternal Deaths Act signed Dec 21, 2018, funding state maternal mortality review committees; state legislators in IN, OR, DC, MD credited the series.
- **Generalization**: Works wherever a bureaucracy publishes counts without cases: deaths in custody, evictions, workplace deaths, veteran suicides, deportation deaths. Generic detector: fundraiser/memorial-platform scraping keyed to event vocabulary + date window, verified against obits/vital records; compare reconstructed cohort size to official count for undercount estimation.

---

### Profiting from the Poor — Methodist Le Bonheur (2019) — A faith-based nonprofit hospital running a collection-lawsuit machine against its own patients and employees
- **URL**: series hub: https://mlk50.com/profiting-from-the-poor/ ; ProPublica impact pieces: https://www.propublica.org/article/methodist-le-bonheur-healthcare-debt-collection-raised-wages-policy-change-after-mlk50-propublica-investigation
- **Partner/awards**: MLK50: Justice Through Journalism (Wendi C. Thomas; ProPublica Local Reporting Network). Selden Ring, Gerald Loeb, NABJ Salute to Excellence.
- **What they found**:
  - Methodist filed 8,300+ collection lawsuits 2014–2018 in Shelby County General Sessions Court — more suits and garnishment orders than any other hospital system in the county — in a city where ~1 in 4 residents is poor.
  - Defendants included Methodist's own low-wage employees, whose paychecks it garnished.
  - A church-affiliated nonprofit with charity-care obligations that flouted IRS rules by not publicly posting financial assistance policies.
  - It owned its own collection agency — vertical integration of the extraction pipeline.
- **Finding type(s)**: charity-mission-inversion; two-books-asymmetry (charity-care posture vs docket conduct); self-dealing/related-party (captive collection agency)
- **Evidence & sources**:
  - [court records] Five years of Shelby County General Sessions Court dockets — suits, judgments, garnishments, by plaintiff
  - [courtroom observation] Direct observation of collection dockets
  - [IRS filings] Form 990 / financial-assistance-policy compliance check
  - [interviews] Defendant patients and employees
- **Access tier**: open-public (dockets, 990s) — the power came from labor-intensive assembly, not privileged access
- **Acquisition path**: litigation-records (bulk docket harvest) + interviews + field-observation
- **Detection signature**: Two-books-diff executed literally: plaintiff-name aggregation across a county civil docket (who sues, how often, for what amounts, with what garnishment follow-through) joined against the same institution's IRS-990 charity-care claims and public mission statements. Refinement: intersect the defendant list with the plaintiff's own employee roster (garnishment filings reveal employer) — suing-your-own-workers is the headline artifact.
- **Corroboration structure**: Docket data (primary, adversarial) → named defendants interviewed → hospital's own policies and 990s → judges/collection attorneys observed in court; hospital response solicited pre-publication.
- **Impact**: Within weeks Methodist suspended suits, then erased debts — >6,500 sued patients released, $11.9M erased for 5,300+ patients by December; raised minimum wage toward $15; expanded financial assistance; Sen. Grassley demanded answers on nonprofit-hospital obligations.
- **Generalization**: Instantly portable: any nonprofit with a docket. Generic detector: for each nonprofit hospital/university/church system, count civil filings as plaintiff, compute suits-per-revenue and garnishment rate, diff against 990 Schedule H community-benefit claims. Our court + 990 tooling covers both books; join key = institutional plaintiff name + subsidiaries/captive collection agencies from registry data.

---

### The Hospice Hustle / "Endgame" (2022) — Hospice as a per-diem extraction vehicle: patients recruited to not die
- **URL**: https://www.propublica.org/article/hospice-healthcare-aseracare-medicare (co-published as "Endgame" in The New Yorker, Dec 5, 2022); series: https://www.propublica.org/series/the-hospice-hustle
- **Partner/awards**: The New Yorker (Ava Kofman). 2023 Hillman Prize for Magazine Journalism; National Press Club award; Barlett & Steele award.
- **What they found**:
  - $22B/yr, taxpayer-funded; for-profit share grew from ~30% to 70%+; private-equity ownership tripled 2011–2019; a 20-patient hospice bills >$1M/yr; for-profit margins ~3x nonprofits.
  - Recruitment of the non-dying: an AseraCare marketer targeted "run-down places where people were more on the poverty line"; her office's live-discharge rate hit 70% (2007). In the AseraCare FCA trial, the government's expert found 86% of sampled patients ineligible; the case settled for $1M vs a $200M demand.
  - License-mill clustering: 33 new hospices at one Phoenix address; 129 hospices in one Los Angeles building — churn-and-rebirth licensure to evade the Medicare aggregate cap.
  - Enforcement void: inspections every ~3 years; majority of hospices had serious deficiencies (2012–2016 review) yet only 19 of 4,000+ lost Medicare funding 2014–2017 ("pay and chase").
- **Finding type(s)**: extraction-from-captive-population; fraud-enablement-by-design (per-diem benefit rewards non-dying enrollees); license-mill-clustering (new tag); regulatory-capture
- **Evidence & sources**:
  - [litigation records] 11 years of court filings incl. FCA qui tam (AseraCare), criminal cases (Dr. Scott Nelson: 763 patients certified to 25 hospices, convicted)
  - [government records] State/federal licenses, inspection and complaint surveys, OIG/GAO reports
  - [medical records] Family-shared patient files (Patricia Marble: ~5-year enrollment, ~$500K billed; Amedisys settled $7.75M)
  - [interviews] 150+ families, employees, elder-care experts, attorneys, officials
  - [field observation] Site visits: AL, MS, CA, AZ, TX
- **Access tier**: mixed — open-public (licenses, dockets, surveys) + privileged (family-shared records; qui tam material) + constructed (address-level license census)
- **Acquisition path**: litigation-records + bulk-public-data + interviews + field-observation
- **Detection signature**: Live-discharge-rate-inversion (new tag): in a benefit defined by a 6-month terminal prognosis, high rates of patients leaving alive are the fraud signature — survival as evidence. Companions: (1) address-colocation-clustering of licenses (dozens of "hospices" in one suite = cap-evasion shells); (2) cap-proximity churn (dumping stable patients as the aggregate cap approaches); (3) ownership-background screen (licensees with no clinical history).
- **Corroboration structure**: Benefit-design analysis → FCA trial record (sampled-eligibility expert review) → insider recruitment testimony → named patients' records → regulator survey citations; the AseraCare judicial reversal candidly reported as a limit on the falsity theory.
- **Methodology notes**: Sourcing enumerated in the piece; no standalone data-methods page [inferred]. CA hospice-mill groundwork also laid by LA Times (2020–21) [attribution hygiene].
- **Impact**: Congressional calls for a crackdown citing the reporting; CMS stood up the Hospice Special Focus Program and enhanced enrollment oversight effective late 2023/CY2024.
- **Generalization**: Per-diem benefits gated by an eligibility prognosis/threshold: SSDI, veterans' benefits, special-education services, residential addiction-treatment per-diems. Generic detector: outcome-inversion metrics, licensure address clustering (registry + geocode), enrollment churn timed to caps. Our registry + Medicare tooling computes all three; address-colocation is an existing platform capability.

---

### Uncovered (anchor): "How Often Do Health Insurers Say No to Patients? No One Knows." (2023) — The denial-rate data void as the finding
- **URL**: https://www.propublica.org/article/how-often-do-health-insurers-deny-patients-claims (Robin Fields, June 28, 2023); series: https://www.propublica.org/series/uncovered ; tool: https://projects.propublica.org/claimfile/
- **Partner/awards**: ProPublica (series includes Capitol Forum co-publications).
- **What they found**:
  - The ACA (2010) gave federal regulators authority to require denial-rate disclosure from all plans; 13 years later collection covers only HealthCare.gov plans (~12M people, <10% of the privately insured), published only since 2017 — "It's not standardized, it's not audited, it's not meaningful."
  - What exists shows insurers deny ~1 in 5 claims on average, ranging 2% to nearly 50%; one insurer swung 66%→7% year over year — implausible absent definitional chaos.
  - NAIC collects detailed denial data from nearly all states and keeps it secret; every state refused ProPublica's data request; only CT and VT disclose.
- **Finding type(s)**: regulatory-data-void (new tag — mandated transparency never operationalized); algorithmic-or-systematic-denial (series frame); institutional-coverup/records-suppression (NAIC secrecy)
- **Evidence & sources**:
  - [regulatory data] CMS transparency files for marketplace plans; KFF analyses
  - [refusal documentation] 50-state records-request canvass (all denied) — the refusals are themselves evidence
  - [interviews] Regulators, KFF's Karen Pollitz, exchange officials
- **Access tier**: open-public (what exists) + request-gated (refused — documented denial of access)
- **Acquisition path**: bulk-public-data + records-request canvass (negative result as finding)
- **Detection signature**: Policy-shadow-measurement: diff the statutory mandate (ACA disclosure authority) against data actually collected/published; a 90%+ coverage hole in a 13-year-old transparency mandate is the story. A systematic 50-jurisdiction records-request canvass converts scattered refusals into a quantified secrecy map.
- **Corroboration structure**: Statute text → agency's own published data inventory → structured refusal log → expert validation of the void's consequences.
- **Methodology notes**: Stated within article; Claim File Helper (constructed tool) operationalizes the individual-level workaround: patients request their own claim files, generating microdata regulators won't.
- **Impact**: Framed the Uncovered series that produced the Cigna/EviCore/United investigations; companion piece documented insurers repeatedly violating state coverage laws via market-conduct exams.
- **Generalization**: The unenforced-transparency-mandate pattern recurs everywhere: beneficial-ownership registries, hospital price transparency, police misconduct databases. Generic detector: for each disclosure statute, measure (entities covered ÷ entities reporting) and (fields mandated ÷ fields published); canvass all jurisdictions with identical requests and tabulate refusals.

---

### Cigna PxDx (2023) — Batch claim "review": 300,000 denials in two months, 1.2 seconds each
- **URL**: https://www.propublica.org/article/cigna-pxdx-medical-health-insurance-rejection-claims (Patrick Rucker/Capitol Forum, Maya Miller, David Armstrong; Mar 25, 2023)
- **Partner/awards**: The Capitol Forum (co-published). April 2023 Sidney Award.
- **What they found**:
  - PxDx ("procedure-to-diagnosis"): algorithm flags procedure/diagnosis mismatches against Cigna-approved lists; medical directors then deny in bulk without opening patient files — "We literally click and submit. It takes all of 10 seconds to do 50 at a time."
  - Over two months in 2022: 300,000+ denials, average 1.2 seconds per claim; one medical director rejected 60,000 in a month; internal projections assumed only ~5% of denied members appeal; ~18M people covered/administered.
  - Legality hinges on state medical-necessity review statutes; Maryland regulators saw "red flags"; former CA commissioner Dave Jones: "It's hard to imagine that spending only seconds to review medical records complies with the California law."
- **Finding type(s)**: algorithmic-or-systematic-denial; fraud-enablement-by-design (appeal-rate arbitrage: denial economics priced off the 5% who fight back)
- **Evidence & sources**:
  - [internal documents] Corporate spreadsheets tracking each medical director's PxDx denial volumes; presentations weighing cost-benefit of adding procedures to the denial list
  - [insider interviews] Multiple former Cigna medical directors (anonymous); former Cigna executive Ron Howrigon (named)
  - [named patient case] Nick van Terheyden's $350 vitamin-D test denial → overturned on external review
  - [regulator comment] State insurance departments
- **Access tier**: privileged (leaked internal documents + insiders) with open-public corroboration (appeal outcomes, statutes)
- **Acquisition path**: leak + interviews
- **Detection signature**: Per-reviewer-throughput-forensics (new tag): decisions ÷ reviewer-time from the company's own productivity ledger yields physically impossible review rates (1.2 sec/claim), converting a process description into arithmetic proof that no medical judgment occurred. Paired with internal-rulebook-acquisition (the PxDx list itself — which procedures get auto-denied, and the cost-benefit memos adding new ones).
- **Corroboration structure**: Internal spreadsheets (quantitative) → multiple independent insider accounts → named patient's external-review reversal (outcome test) → state-law diff (legal standard vs measured conduct) → company response documented.
- **Impact**: Congressional scrutiny of PxDx; Sidney Award; contributed to the prior-auth/algorithmic-review reform wave; class-action litigation followed in California [inferred].
- **Generalization**: Any high-volume adjudication with per-adjudicator logs: content moderation, loan underwriting, disability determinations, immigration adjudication, parole reviews. Generic detector: obtain throughput ledgers (discovery, leak, FOIA for public agencies) and compute time-per-decision against a plausible-human-review floor; harvest the auto-decision rulebook and diff against the legal standard requiring individualized judgment.

---

### EviCore, "The Denial Machine" (2024) — An outsourced prior-authorization contractor that tunes its algorithm to hit denial targets
- **URL**: https://www.propublica.org/article/evicore-health-insurance-denials-cigna-unitedhealthcare-aetna-prior-authorizations ("Not Medically Necessary," Oct 2024)
- **Partner/awards**: The Capitol Forum (co-reported); broad pickup (CNN).
- **What they found**:
  - EviCore (owned by Cigna) runs prior authorization for 100+ insurers incl. UnitedHealthcare and Aetna — ~100M covered lives, 1 in 3 insured Americans.
  - "The dial": an AI-backed scoring algorithm whose approval threshold can be adjusted to push more cases to medical-director review — "We could control that. That's the game we would play" (former executive). More reviews → more denials.
  - Business model sells denial: marketed 3-to-1 ROI to insurer clients; salespeople boasted of 15% denial increases; risk contracts let EviCore keep savings.
  - Measured rates: ~20% turndown in Arkansas (2021– ) vs ~7% for Medicare Advantage plans (2022); Vermont Medicaid filings showed its denial rate swinging 6.1%→15%; a 2018 CMS audit found inappropriate denials for 30 cancer patients.
  - Named case: Little John Cupp, 61 — heart catheterization twice denied; died of cardiac arrest 36 hours after an approved stress test; 3 of 4 independent cardiologists said catheterization was appropriate.
- **Finding type(s)**: algorithmic-or-systematic-denial; delegated-denial-profiteering (new tag — UM outsourced to a vendor whose revenue is the denial spread); tunable-threshold-artifact
- **Evidence & sources**:
  - [internal documents] Sales materials (ROI claims), contract terms, dial descriptions
  - [state regulatory filings] Vermont Medicaid presentations; Arkansas regulator denial-rate data
  - [federal audit] 2018 CMS audit findings
  - [insider interviews] Former EviCore executives and medical directors (dozens)
  - [named-case records] Cupp medical records + independent expert panel
- **Access tier**: mixed — privileged (internal docs, insiders) + open-public/request-gated (state filings, CMS audit)
- **Acquisition path**: leak + interviews + bulk-public-data (state regulatory filings) + expert review
- **Detection signature**: Internal-rulebook-acquisition upgraded to tunable-threshold discovery: the artifact is not a fixed rule list but a governance dial — proof that denial rates are a controlled business variable, not a clinical outcome. Quantitative wrapper: vendor denial rate benchmarked against a neutral comparator (MA ~7%) and against itself across clients/time (6.1%→15% swings correlated with contract type = the thresholds, not medicine, moved).
- **Corroboration structure**: Insider descriptions of the dial → contract/sales documents monetizing it → state-filed denial-rate data showing the predicted variance → CMS audit as government validation → named-death case reviewed by independent specialists → company denial documented.
- **Impact**: Fed the congressional prior-auth reform push; CMS's 2024 Interoperability and Prior Authorization Rule requires payers to post prior-auth metrics.
- **Generalization**: Delegated-adjudication vendors exist across sectors: PBMs, disability-exam contractors, background-check vendors, moderation BPOs, tax-credit processors. Generic detector: (1) map the delegation chain (who actually decides); (2) obtain the vendor's compensation structure — any contract where vendor margin grows with adverse decisions is the finding; (3) benchmark decision rates across clients/jurisdictions; unexplained inter-client variance implies a dial.

---

### UnitedHealth's Mental-Health Playbook: ALERT & the Autism "Market Action Plans" (2024) — An algorithm ruled illegal in three states, rebranded and redeployed against Medicaid's children
- **URL**: ALERT: https://www.propublica.org/article/unitedhealth-mental-health-care-denied-illegal-algorithm ; autism/ABA: https://www.propublica.org/article/unitedhealthcare-insurance-autism-denials-applied-behavior-analysis-medicaid (Annie Waldman; Nov–Dec 2024)
- **Partner/awards**: ProPublica.
- **What they found**:
  - ALERT: algorithms flagging "excessive" therapy — triggers include >20 sessions in 6 months, twice-weekly therapy ≥6 weeks, therapists billing >8 hrs/day; up to 15% of outpatient recipients flagged; savings target up to $52M; in NY alone 34,000+ sessions (~$8M) denied 2013–2020.
  - Ruled unlawful under mental-health parity by California (2018), Massachusetts (2020), and New York (2021, with US DOL; $4M+ restitution/penalties).
  - After the NY settlement, Optum rebranded the machinery as "Outpatient Care Engagement" and deployed it into ~20 state Medicaid programs and dual-eligible plans in 18 states + DC — near-identical scripts, aimed at populations (~6M+ Medicaid members) outside the settling regulators' reach; manuals showed ALERT "still operational in Louisiana."
  - Autism playbook: internal Optum documents describe "market-specific action plans" to cut ABA spending (~$290M/yr Medicaid) while calling ABA "the evidence-based gold standard": "prevent new providers from joining the network," "terminate" cost-outlier providers, authorize "less units than requested"; projected exclusion of up to 40% of Louisiana ABA provider groups; up to 19% of patients losing access in some states.
- **Finding type(s)**: algorithmic-or-systematic-denial; network-suppression-rationing (new tag — rationing by shrinking the provider network rather than denying claims); rebrand-persistence (new tag — enjoined practice redeployed under new name in unregulated jurisdictions); extraction-from-captive-population (Medicaid children)
- **Evidence & sources**:
  - [internal documents] Hundreds of pages: playbooks, ALERT documentation (50+ algorithms), rebranded program materials, care-advocate scripts, productivity quotas, state-by-state deployment plans
  - [enforcement records] CA/MA/NY regulatory findings; NY AG/DOL settlement
  - [insider interviews] Seven former Optum employees (2006–2021) + dozens of current/former staff and in-network providers
  - [state records] Medicaid agency responses
- **Access tier**: mixed — privileged (leaked playbooks; insiders) + open-public (settlements, enforcement findings)
- **Acquisition path**: leak + interviews + litigation/enforcement-records
- **Detection signature**: Rebrand-persistence-tracing: take the enjoined practice's operational fingerprint (thresholds, scripts, quotas) from enforcement records, then match it against the successor program's internal materials — near-identical scripts + new name + deployment map skewed to jurisdictions not party to the settlement = regulatory arbitrage by geography. Secondary: network-suppression arithmetic — provider-termination targets and unit-authorization haircuts in internal projections vs the insurer's public "access" commitments and Medicaid contract obligations.
- **Corroboration structure**: Regulators' prior findings (adjudicated facts) → leaked successor-program documents → insider testimony bridging the two eras → provider and family experiences instantiating the paper policies → company response logged against the Louisiana-manual contradiction.
- **Methodology notes**: In-article sourcing statements; fragmentation finding stated: "more than 50 different state and federal regulatory entities" oversee the network — the arbitrage surface itself.
- **Impact**: Senate Finance (Wyden) pressed UnitedHealth on mental-health coverage shortfalls; series continued through 2026.
- **Generalization**: Wherever enforcement is jurisdiction-bounded and the operator is national: payday-lending rebrands, for-profit-college name changes, debt-collector entity churn. Generic detector: build the enforcement-record fingerprint (specific thresholds/scripts found unlawful), then scan the operator's other jurisdictions and successor brands for the same fingerprint; deployment maps that avoid settling states are confirmatory.

---

### Life of the Mother (2024–2025) — Preventable deaths under abortion bans, proven with the states' own confidential review records and purchased hospital microdata
- **URL**: series: https://www.propublica.org/series/life-of-the-mother ; sepsis analysis: https://www.propublica.org/article/texas-abortion-ban-sepsis-maternal-mortality-analysis ; methodology: https://www.propublica.org/article/texas-maternal-mortality-analysis-methodology
- **Partner/awards**: ProPublica (Kavitha Surana, Lizzie Presser, Cassandra Jaramillo, Stacy Kranitz). **Pulitzer Prize for Public Service, 2025** — second consecutive.
- **What they found**:
  - Five named preventable deaths: Amber Thurman and Candi Miller (Georgia — the state maternal mortality review committee deemed the deaths preventable); Josseli Barnica (Texas — family told intervening in her miscarriage would be "a crime"), Nevaeh Crain (18, died after three ER visits), Porsha Ngumezi.
  - Quantitative confirmation: ProPublica purchased seven years (2017–2023) of Texas hospital discharge data; second-trimester pregnancy-loss sepsis rates rose >50% after the ban (67 sepsis cases in 2021 → 90 in 2022 → 99 in 2023); dozens more pregnant/postpartum women died in Texas hospitals than in pre-pandemic baseline years.
- **Finding type(s)**: policy-induced-mortality (new tag — deaths caused by legal chilling effects, not a single bad actor); institutional-coverup/records-suppression (confidential committee findings; Georgia's retaliatory committee dismissal)
- **Evidence & sources**:
  - [confidential government review records] State maternal mortality review committee determinations (obtained despite confidentiality)
  - [vital/medical records] Death certificates, autopsy reports, hospital records shared by families
  - [commercial state microdata] Purchased Texas hospital discharge data (anonymized billing with gestational age, complications, procedures)
  - [expert panels] Maternal-health researchers and obstetricians consulted on the analytic framework; independent physician review of each case
- **Access tier**: mixed — privileged (confidential MMRC findings), constructed (family-provided records assembly), commercial-data (discharge microdata purchase), open-public (death certificates)
- **Acquisition path**: leak + interviews + commercial-data + records-from-families
- **Detection signature**: Two-layer proof: (1) named-cohort-tracing — obtain the state's own confidential "preventable" determinations (the gold-standard adjudication the public never sees) and attach names and narratives; (2) policy-shadow-measurement via pre/post natural experiment on purchased microdata — define the exposed denominator precisely ("hospitalizations that included miscarriages, terminations and births from the beginning of the second trimester up to 22 weeks' gestation"), hold it fixed 2017–2023, use pre-pandemic baseline to dodge COVID confounding, and measure complication-rate deltas around the ban's effective date.
- **Corroboration structure**: Committee determination (state's own experts) → medical records → independent OB review → statistical layer showing the named cases are not anecdotes → hospital/state comment. The layers cross-validate: microdata trends predict exactly the case type the named deaths instantiate.
- **Methodology notes**: Stated: texas-maternal-mortality-analysis-methodology ("built a framework for analyzing Texas hospital discharge data from 2017 to 2023 in consultation with maternal health researchers and obstetricians").
- **Impact**: Georgia dismissed its entire maternal mortality review committee over the disclosure (Nov 2024); Texas passed the "Life of the Mother Act" (SB 31) clarifying medical exceptions; Pulitzer Public Service 2025.
- **Generalization**: The purchased-microdata natural experiment generalizes to any policy with a dateable effective moment and a claims-visible harm channel (Medicaid unwinding, drug-law changes, staffing-ratio repeals): buy/obtain state discharge or all-payer claims data; pre-register the exposed denominator with domain experts; diff outcome rates across the policy date against a clean baseline. The confidential-review-leak arm generalizes to any internal death-review regime (child-fatality, in-custody, prison mortality reviews): the state's own preventability verdicts are the highest-value target.

---

## Cluster Synthesis

### 1) Recurring evidence-source types (frequency across 14 entries)
- **Government transactional microdata** (Part D, inpatient claims, discharge data, Open Payments) — 6 (D4D, Prescriber Checkup, Surgeon Scorecard, Dialysis, EviCore benchmark, Life of the Mother)
- **Litigation records** (dockets, FCA/qui tam, discovery exhibits, verdicts) — 6 (Methodist, Hospice, Assisted Living, Insult to Injury, United enforcement records, Prescriber prosecutions)
- **Insider/whistleblower interviews** (ex-medical directors, executives, marketers, nurses) — 6 (Cigna, EviCore, United, Hospice, Assisted Living, D4D-adjacent)
- **Internal corporate documents** (playbooks, algorithms, throughput spreadsheets, sales decks) — 5 (Cigna, EviCore, United, Assisted Living, Hospice via litigation)
- **Inspection/survey/regulatory-exam records** — 4 (Dialysis, Assisted Living, Hospice, Uncovered market-conduct exams)
- **FOIA / records requests, incl. documented refusals as evidence** — 4 (Prescriber Checkup, Dialysis, Uncovered 50-state canvass, Surgeon Scorecard data agreement)
- **Crowdsourced/social-exhaust case data** — 2 (Lost Mothers; Life of the Mother family-records assembly adjacent)
- **Commercial data purchases** — 2 (Pharmashine for D4D 2013; Texas discharge data)
- **Confidential internal government reviews** (MMRC determinations, CMS audits) — 2 (Life of the Mother, EviCore)
- **Statute/benefit-schedule corpora** — 2 (Insult to Injury, Uncovered mandate-vs-collection diff)

### 2) Recurring detection signatures (frequency)
- **Outlier-in-microdata with denominator discipline** (peer z-scores, minimum volumes, shrinkage) — 4 (Prescriber Checkup, Surgeon Scorecard, D4D million-dollar list, EviCore benchmarking)
- **Internal-rulebook-acquisition** (algorithm/threshold/playbook document) — 4 (PxDx lists, EviCore dial, ALERT triggers, Optum market action plans)
- **Two-books-diff** (mission/lobbying ledger vs conduct ledger) — 4 (Methodist 990-vs-docket; comp "crisis" claims vs profit data; hospice marketing vs live discharges; United "access" claims vs termination targets)
- **Silo-join-on-hard-identifier (NPI as master key)** — 3 (payments×Part D; speakers×board discipline; claims×surgeon identity)
- **Policy-shadow-measurement / natural experiment around a policy date** — 3 (Life of the Mother sepsis; Uncovered mandate-vs-collection; comp-cuts timeline)
- **Enforcement-gap ratio** (deficiencies ÷ sanctions) — 3 (Dialysis 16 terminations; Hospice 19 of 4,000+; Uncovered state-law violations without penalty)
- **Per-reviewer-throughput-forensics** (new) — 2 (Cigna 1.2 sec/claim; United care-advocate quotas)
- **Cross-jurisdiction-statute-diff** (new) — 2 (comp schedules; parity-enforcement patchwork)
- **Outcome-inversion as fraud signal** (new; live-discharge rates) — 1 strong (Hospice), conceptually present in ALERT ("too much" therapy = too-well patients)
- **Address-colocation / license-mill clustering** (new) — 1 strong (129 hospices, one building)
- **Crowdsourced-denominator-reconstruction** — 1 (Lost Mothers)
- **Rebrand-persistence-tracing / jurisdictional-arbitrage mapping** (new) — 1 strong (ALERT → Outpatient Care Engagement)

New tags coined this cluster — *finding types*: benefit-erosion-by-statute; delegated-denial-profiteering; network-suppression-rationing; license-mill-clustering; regulatory-data-void; policy-induced-mortality; rebrand-persistence; regulatory-tier-arbitrage; passive-payer-nonsurveillance; anonymized-aggregate-accountability-gap. *Signatures*: per-reviewer-throughput-forensics; address-colocation-clustering; outcome-inversion (live-discharge-rate-inversion); tunable-threshold-artifact; rebrand-persistence-tracing; cross-jurisdiction-statute-diff; enforcement-gap-ratio; settlement-mandated-disclosure-harvest (acquisition); commercial-microdata-natural-experiment.

### 3) Transferable pattern candidates

**P1 — Outlier Practitioner (licensed-professional transaction screening).** Any payer or registry that logs transactions per licensed professional supports peer-group outlier detection: aggregate transactions per professional per product/procedure, compare within specialty × jurisdiction peer cells, flag ≥2σ, guard with minimum denominators (≥20–50 events; ≥20 peers) and small-n shrinkage, overlay a domain risk list. Then interview the outlier — innocent explanations (shared IDs, niche specialization) are enumerable and checkable. Minimum data: transaction microdata with a hard professional ID + a registry for peer grouping. Agent lookout in ANY sector: attorneys (e-filing volumes, guardianship fees), FINRA brokers, DME suppliers, notaries, veterinarians (controlled substances), purchasing officers (award concentration per officer). Platform fit: Medicare/Medicaid + NPI tooling already present.

**P2 — Influence-Payment × Behavior Join on a Hard Identifier.** Normalize a mandated influence-disclosure stream (industry payments, lobbying, gifts, campaign money) into a per-recipient ledger; join to the recipient's decision stream (prescribing, votes, contract awards, rulings) on the registry key; test level differences and dose-response by payment tier; publish with the causation caveat and let the gradient speak. Minimum data: disclosure data + decision data sharing one identifier (NPI, bar number, member ID, UEI). Lookout: FEC/lobbying × votes; state gift registries × procurement; expert-witness fees × testimony; CME sponsorship × guideline authorship. D4D lesson: deliberately unusable disclosure formats are themselves a finding — and aggregation alone, before any join, creates accountability.

**P3 — Two-Books Diff (mission ledger vs conduct ledger).** Institutions maintain a self-description ledger (990 Schedule H community benefit, ESG reports, charity-care policies, "access" commitments) and an adversarial conduct ledger (dockets as plaintiff, garnishments, denial rates, termination notices, premium/profit data). Pull both, normalize to comparable units, publish the diff. Sharpest variant intersects the two populations: defendants who are also the plaintiff's employees. Minimum data: IRS 990s/public filings + county-court docket search by party name (+ registry data to catch captive subsidiaries like collection agencies). Lookout: nonprofit hospitals/universities suing patients/students; "affordable housing" nonprofits filing evictions; banks' CRA claims vs foreclosure dockets; safety-award companies vs OSHA logs. Platform fit: 990 + state-court + registry tooling covers all three legs.

**P4 — The Denial Machine (delegated adjudication + throughput + tunable thresholds).** Industrialized high-volume adjudication is detectable three ways: (a) a rulebook artifact (auto-decision lists, scoring thresholds) substituting for legally required individualized judgment; (b) per-adjudicator throughput ledgers whose arithmetic (seconds per decision) proves no judgment occurred; (c) an economic dial — vendor contracts or internal targets where revenue rises with adverse decisions, visible as unexplained rate variance across clients/jurisdictions/time. Acquisition is usually privileged (leak, insider, discovery) but corroboration is public: benchmark rates (regulator filings, CMS audits, state Medicaid decks), appeal-reversal rates, enforcement records. Watch for rebrand-persistence: practices found unlawful in one jurisdiction redeployed under a new name where the settlement doesn't reach — fingerprint the enjoined thresholds/scripts and scan sibling jurisdictions. Lookout: PBMs, disability-exam contractors, background-check vendors, moderation BPOs, tax-credit processors.

**P5 — Captive-Population Extraction Screen (per-diem benefits + weak inspection).** Sectors where a public payer pays per-diem for a captive or cognitively vulnerable population, with infrequent inspection and no intermediate sanctions, evolve toward extraction. Composite screen: (payer generosity × chain/PE concentration) + enforcement-gap ratio (deficiencies ÷ sanctions) + outcome-inversion metrics (live-discharge rates where terminality is the eligibility premise; mortality vs fixed-standard benchmarks) + registry red flags (license address colocation, rapid license churn, owners with no clinical history). Minimum data: provider registry with addresses/ownership, payer utilization aggregates, inspection reports, and the benefit's eligibility rule. Lookout: hospice, dialysis, assisted living, sober homes, group homes, private detention medical contracts, veterans homes, ABA mills — directly relevant to the GEO Group investigation; address-colocation and ownership screens are existing platform capabilities.

Also viable but narrower: crowdsourced-denominator-reconstruction (rebuild named cohorts from fundraiser/obituary exhaust when official counts are anonymous) and regulatory-data-void mapping (measure the gap between a transparency statute's mandate and actual collection via a 50-jurisdiction records-request canvass — the void is the story).
