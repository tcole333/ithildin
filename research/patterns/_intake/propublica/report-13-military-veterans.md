# ProPublica Evidence Ontology — Cluster 13: Military, Veterans & National Security

Research agent report. Scope: ProPublica's series index for this area (13 series / 248 items per census) — series pages fetched directly: `disposable-army`, `inside-trump-va`, `veterans-care-at-risk`, `brain-wars`, `reliving-agent-orange`, `drones`, plus `failing-the-fallen` (surfaced via topic-page sweep) and the `/topics/military` page for standalone investigations. The `navy-accidents-pacific-7th-fleet` series was extracted by a sibling agent and appears here only as a cross-reference. 12 stories/series extracted in depth below. Web research only; no database writes.

**Attribution check**: every entry below is a ProPublica original or a formal co-publication with the partner named in the entry (NPR, Los Angeles Times/ABC News, The Virginian-Pilot, PolitiFact, The Texas Tribune/Military Times). Verified against the series pages and article bylines cited inline.

---

## Cross-reference: Disaster in the Pacific / 7th Fleet (2019) — extracted by sibling agent

ProPublica's 26-story series on the USS Fitzgerald and USS McCain collisions ("Years of Warnings, Then Death and Disaster"; "Death and Valor on an American Warship Doomed by Its Own Navy", Feb. 2019, T. Christian Miller, Megan Rose, Robert Faturechi) reconstructed the two 2017 collisions that killed 17 sailors from the Navy's own mishap/command investigation files, ship logs, internal readiness warnings and years of ignored risk memos, courts-martial records of accused officers, and hundreds of sailor interviews — the core signature being a diff between years of internal readiness warnings and the Navy's public assurances, plus second-by-second bridge reconstruction. It shares this cluster's "military accident/mishap investigation file" and "courts-martial record" evidence classes with the Bonhomme Richard entry below. Series: https://www.propublica.org/series/navy-accidents-pacific-7th-fleet. Pulitzer Prize for National Reporting, 2020 (per the series page and https://www.pulitzer.org/winners/t-christian-miller-megan-rose-and-robert-faturechi-propublica). See sibling report for full extraction.

---

### 1. Brain Wars — "Brain Injuries Remain Undiagnosed in Thousands of Soldiers" (2010) — the military's own screening system was missing tens of thousands of traumatic brain injuries

- **URL**: https://www.propublica.org/article/brain-injuries-remain-undiagnosed-in-thousands-of-soldiers (series: https://www.propublica.org/series/brain-wars — 42 stories, 2010–2012)
- **Partner/awards**: Co-reported and co-published with **NPR** (T. Christian Miller, ProPublica; Daniel Zwerdling, NPR).
- **What they found**:
  - Official count was ~115,000 troops with mild traumatic brain injury (mTBI), but an unpublished Army study found military medical files contained no concussion record for **more than 75%** of soldiers who reported concussions to clinicians; a Fort Carson study found the post-deployment health assessment (PDHA) missed **up to 40%** of mTBI cases.
  - The Army's mandated ANAM cognitive screening test — administered to **580,000+ soldiers** at millions of dollars a year — had its results retrieved for diagnostic use only **~1,500 times**; a senior Army official called it "basically a coin flip."
  - Battlefield paper records were "lost, burned or abandoned in warehouses"; the MACE concussion exam was routinely "gamed" by soldiers memorizing answers (named cases: Sgt. William Fraas, Sgt. Victor Medina, Maj. Michelle Dyarman).
  - Follow-on stories: TRICARE refused to cover cognitive rehabilitation therapy ("Pentagon Health Plan Won't Cover Brain-Damage Therapy for Troops," Dec. 20, 2010) and brain-injured soldiers were denied Purple Hearts (Sept. 8, 2010) — both on the series page.
- **Finding type(s)**:
  - `systemic-undercount` — an official casualty/injury statistic materially below the real-world total, produced by the design of the counting process itself.
  - `phantom-oversight` — a mandated safeguard (screening test) that exists and consumes budget but whose outputs are never consumed downstream.
  - `care-denial-by-policy` — an insurer/benefits arm of the same institution refusing the indicated treatment for the injury the institution undercounted.
- **Evidence & sources**:
  - *Unpublished internal studies* — Army analyses of concussion reporting and ANAM performance, "previously undisclosed studies" reviewed by the reporters (obtained from researchers/insiders; not public).
  - *Private correspondence of senior medical officials* — e.g., an April 2010 email from Army psychiatrist Col. Charles Hoge asking "What's the harm in missing the diagnosis of mTBI?"; a Lt. Gen. Schoomaker email instructing base commanders not to speak to reporters (obtained and published).
  - *Published clinical literature* — Journal of Head Trauma Rehabilitation brigade study (900 soldiers, ~40% symptomatic weeks later) used as an independent prevalence anchor.
  - *Interviews* — "scores of soldiers, experts and military leaders," including on-the-record senior officials (Schoomaker, Chiarelli) and named injured soldiers whose medical files were checked against their accounts.
  - *FOIA* — the series ran a public, contested FOIA fight for screening-program records ("How Our FOIA Request Was Blocked," Dec. 20, 2010; "A Partial Victory in Our FOIA Request," Mar. 14, 2011 — series page).
- **Detection signature**: **report-to-record deficit audit** — soldiers' contemporaneous self-reports of concussion (captured in clinician interviews and unpublished Army studies) joined to their official medical files on the individual showed >75% of reported injuries absent from the record; the gap between the two record streams *is* the undercount. Secondary: **instrument dead-letter check** — usage telemetry of a mandated screening instrument (580,000 administrations vs. ~1,500 diagnostic retrievals) proved the safeguard was ceremonial.
- **Corroboration structure**: unpublished internal studies (system's own measurement of its failure) + named-case file-vs-testimony checks + civilian clinical standards as external norm + on-record admissions from the surgeon general ("a black hole of information") layered so that no finding depended on soldier testimony alone.
- **Methodology notes**: Stated in-article: "Over four months, we examined government records, previously undisclosed studies, and private correspondence between senior medical officials. We conducted interviews with scores of soldiers, experts and military leaders." (flagship URL above). No separate methodology page; the FOIA-fight posts document acquisition. Remainder [inferred] from article structure.
- **Official impact (one line)**: Senate and House hearings within weeks ("Soldier Brain Injuries to Get Senate Scrutiny...", Jun. 11, 2010), a new Pentagon TBI diagnosis/treatment policy (Jun. 29, 2010), 70+ members of Congress demanding coverage of cognitive therapy, and a congressional probe of the TRICARE denial (series page).
- **Generalization**: any institution that both *produces* injuries and *counts* them (prisons, police departments, meatpacking OSHA logs, sports leagues, nursing-home incident reports). Generic detector: sample individuals with independently attested harm; measure the fraction absent from the institution's official registry; separately, pull usage/consumption metrics for any mandated screening or audit artifact — a safeguard nobody reads is a finding by itself.

---

### 2. Disposable Army — "Injured War Zone Contractors Fight to Get Care From AIG and Other Insurers" (2009) — a taxpayer-funded insurance scheme routinely denied care to the war's civilian wounded

- **URL**: https://www.propublica.org/article/injured-war-zone-contractors-fight-to-get-care-from-aig-416 (series: https://www.propublica.org/series/disposable-army — 39 stories, 2008–2013)
- **Partner/awards**: Joint investigation with the **Los Angeles Times** and **ABC News** (T. Christian Miller; Doug Smith/LAT data). Selden Ring Award 2010 (https://www.propublica.org/article/propublicas-t.-christian-miller-wins-the-selden-ring-award).
- **What they found**:
  - Of ~31,000 Defense Base Act war-zone claims, insurers contested nearly **half of the ~9,000 serious cases** (>4 days lost work); **44% of serious injury claims** were initially rejected and **>50% of PTSD claims**; workers who appealed won ~75% of the time.
  - **AIG handled ~90%** of claims, collected **$1.5 billion in premiums** (taxpayer-funded via contract cost) and earned **~$600 million in profit** — congressional investigators' figures reported in the piece.
  - Foreign workers (Iraqi/Afghan interpreters, Filipino laborers) fared worst — "casualties twice over" (series page); the Pentagon did not even track contractor casualties ("Civilian Contractor Toll ... Ignored by Defense Dept.," Oct. 9, 2009); by 2010 contractor deaths exceeded military deaths in theater (Sept. 23, 2010, series page).
- **Finding type(s)**:
  - `benefits-denial-machine` — a claims apparatus whose economics reward contesting precisely the costliest claims.
  - `captive-market-profiteering` — a legally mandated insurance product, near-monopoly provider, public money, private spread.
  - `uncounted-population` — a class of war casualties (contractors) excluded from official casualty accounting.
- **Evidence & sources**:
  - *Government case-management database via FOIA litigation* — ~31,000 claims extracted from the Labor Department's **Longshore Case Management System**; "The LA Times filed suit against the Labor Department" to get it (methodology page below).
  - *Audit/oversight paper* — 2007 Army Audit Agency report on AIG premium rates; GAO audits on premium history; later a Pentagon IG examination and a Pentagon study proposing DBA overhaul (series page).
  - *Court files* — Longshore/DBA dispute records used to compute average time-to-resolution (mediation ~6–7 months; court ~2 years).
  - *Named-case files and interviews* — 200+ interviews across a dozen states and three countries; individual case dossiers (Russell Skoug, Tim Newman — companion pieces Apr. 16, 2009).
  - *Corporate communications* — 10,000+ pages of "court documents, government reports, and corporate communications" (methodology page).
- **Detection signature**: **severity-stratified denial screen** — claim outcomes from the Labor database joined to claim-severity strata (lost-work days; injury vs. PTSD) revealed denial/protest rates *rising* with claim cost — the inversion of what a good-faith system produces. Secondary: **definition-audit against the official metric** — the reporters re-scored "disputed" using Notices of Controversion filed by carriers rather than the Labor Department's narrower examiner-confirmed definition, showing the agency "systematically undercounts real world disputes" at "sometimes twice the rate calculated by the Labor Department."
- **Corroboration structure**: database rates → individual case files that instantiate each rate → insurer's own filings (controversion notices) → congressional-investigator financials → on-record admissions (Labor's Shelby Hallmark conceding the program was "insurance-driven").
- **Methodology notes**: Dedicated methodology page: "'Forgotten Warriors': Explanation of Analysis" — https://www.propublica.org/article/forgotten-warriors-explanation-of-analysis-416 (dataset, FOIA suit, disputed-claim definition, undercount limitation; quotes above are from it).
- **Official impact (one line)**: June 2009 congressional hearing where officials "admit major flaws," Pentagon IG examination of AIG announced May 2009, a Pentagon study proposing Defense Base Act overhaul (Sept. 2009), a 2012 reform bill, and a 2013 fine of a contractor for late casualty reports (all on the series page).
- **Generalization**: any mandated-insurance or claims regime with a dominant carrier — state workers' comp, VA disability raters, private Medicare Advantage denials, FEMA flood claims. Generic detector: per-carrier denial rate stratified by claim value; recompute the regulator's "dispute" metric from the carrier's own adversarial filings and diff the two.

---

### 3. The Drone War — "Obama Administration's Drone Death Figures Don't Add Up" (2012) — the government's own civilian-casualty claims were mutually impossible

- **URL**: https://www.propublica.org/article/obama-drone-death-figures-dont-add-up (series: https://www.propublica.org/series/drones — 17 stories, 2012–2013; interactive: https://www.propublica.org/article/how-obama-drone-death-claims-stack-up)
- **Partner/awards**: ProPublica original (Justin Elliott; additional reporting Cora Currier; interactive with Lena V. Groeger).
- **What they found**:
  - April 2011: officials claimed "about 30" civilians killed in Pakistan Aug. 2009–Aug. 2010; May 2012: a senior official said *total* civilian deaths under Obama were in the "single digits." Both cannot be true.
  - Intervening official claims (CIA internal accounting "just over 20 civilians" since Jan. 2009; "zero" civilians since May 2010 across 182 strikes) implied implausible zero-casualty streaks.
  - Independent tallies at the time: Long War Journal 138; New America Foundation 293–471; Bureau of Investigative Journalism 482–832 civilians killed.
  - Companion pieces mapped what was *structurally unknowable*: targeting of "unidentified men" via signature strikes (Mar. 1, 2013), classified enemies list ("Who Are We at War With? That's Classified," Jul. 26, 2013), condolence-payment opacity (Apr. 5 & Aug. 12, 2013) — series page.
- **Finding type(s)**:
  - `official-claims-incoherence` — a set of government statements about one quantity that cannot be jointly true.
  - `secrecy-boundary-mapping` — cataloguing precisely which facts of a lethal program are withheld (legal memos, target lists, casualty counts) as a finding in itself.
- **Evidence & sources**:
  - *Official statements as a dataset* — anonymously-sourced administration casualty claims compiled from press briefings, wire stories, and named-official speeches, each dated and bounded.
  - *Independent casualty databases* — BIJ, New America, Long War Journal counts (public, methodology-documented NGOs/press) used as external bounds, not as ground truth.
  - *Non-response as evidence* — NSC spokesman: "[W]e simply do not comment on alleged drone strikes," quoted to establish the accountability vacuum.
- **Detection signature**: **self-contradiction matrix** — array every official statement about the same quantity on a timeline with its coverage window, then test pairwise logical compatibility (cumulative totals vs. interval claims). No external data needed: "ProPublica compared administration claims exclusively against each other," making the contradiction unrebuttable since both statements are the government's own. Independent counts were used only to show even the most conservative outside floor exceeded the official ceiling.
- **Corroboration structure**: internal-consistency proof first; external NGO ranges second; the refusal-to-comment quote third — a deliberately layered structure in which the strongest claim requires zero trust in outside counters.
- **Methodology notes**: No methodology page; method stated in-article (claims-vs-claims comparison; sources for each claim linked). [inferred]: statement corpus assembled by clipping/archiving official remarks over 2009–2012.
- **Official impact (one line)**: Fed the transparency pressure that preceded Obama's May 2013 drone-policy speech; the series' Nov. 5, 2013 audit ("6 Months After Obama Promised to Divulge More...") documented the pledge remained largely unmet (series page).
- **Generalization**: any body-count or performance figure issued piecemeal by an opaque institution (police shootings, migrant deaths in custody, environmental spill volumes, casualty claims by any belligerent). Generic detector: build a dated ledger of every official quantitative claim with its coverage interval; flag interval/cumulative pairs that violate monotonicity or additivity.

---

### 4. Failing the Fallen — "The Military Is Leaving the Missing Behind" (2014) — the Pentagon's MIA-accounting agency was structurally incapable of its mission

- **URL**: https://www.propublica.org/article/missing-in-action-us-military-slow-to-identify-service-members (series: https://www.propublica.org/series/failing-the-fallen — 9 stories, 2014–2015; NPR side: https://apps.npr.org/grave-science/)
- **Partner/awards**: Co-reported with **NPR** (Megan McCloskey/ProPublica — now Megan Rose; Kelly McEvers/NPR). Gracie Award, Alliance for Women in Media (https://www.propublica.org/atpropublica/propublica-and-npr-win-alliance-for-women-in-media-award).
- **What they found**:
  - JPAC identified **372 remains over five years while spending $373.1 million** — ~72/year against ~45,000 recoverable missing: **600+ years** at that rate; a 2010 law mandating 200 IDs/year by 2015 was conceded unreachable.
  - **9,400+ servicemen lie buried as "unknowns"** whose case files (X-files) often already contain tentative identifications — the lab's own historical records tied "more than half" of them to a few candidates, sometimes one.
  - Disinterment requests were rejected at compounding rates (~80% by the disinterment unit, ~80% of the rest by scientific director Tom Holland — net ~4% proceed; 111 disinterments since 2000).
  - JPAC used DNA **last**, as confirmation only, while peer labs (ICMP Bosnia) ran DNA-first and hit ~400 identifications/month at peak.
  - Case proof: Pvt. Arthur "Bud" Kelder — National Archives dental records (gold inlays) matched unknown X-816 in Grave 717, internal JPAC staff recommended disinterment in 2011, leadership refused on paper-technical grounds.
- **Finding type(s)**:
  - `mission-throughput-failure` — an agency whose measured output rate mathematically forecloses its stated mission.
  - `risk-averse-gatekeeping` — internal veto points (disinterment approvals) tuned to protect error statistics rather than accomplish the mission.
  - `method-obsolescence` — clinging to a legacy method (anthropology-first) against a proven superior one (DNA-first) used by peers.
- **Evidence & sources**:
  - *National Archives case files* — Kelder's dental/hospital records "untouched 60 years"; Cabanatuan POW camp death report.
  - *The X-file corpus* — records for 9,400+ unknowns; a family litigant (John Eakin) obtained the full set "after a drawn-out battle," built a searchable database from 3,000 Manila cemetery files, and received a package "from a sympathetic source inside the Pentagon"; ProPublica worked from this corpus and Eakin's federal-lawsuit record (filed Oct. 2012).
  - *Internal memos/emails* — JPAC anthropologist's 2011 pro-disinterment email; DPMO research memos; Holland's 2013 refusal memo; 1999 disinterment policy memo.
  - *Budget and output data* — JPAC identifications-per-year charted against budget.
  - *Expert interviews* — Holland and JPAC command on record; former JPAC anthropologist; ICMP/Bosnia and Argentine (EAAF) forensic scientists as method benchmarks.
- **Detection signature**: **throughput-horizon arithmetic** — divide the backlog by the measured annual output (45,000 / 72 ≈ 600+ years) and set it against budget and statutory mandate; the absurd horizon is the lede. Layered with **single-case paper-trail replay** — re-running one identification (Kelder) purely from records the government already held, proving the system *could* identify him and chose not to — and **peer-institution method benchmark** (JPAC's DNA-last vs. ICMP's DNA-first throughput).
- **Corroboration structure**: agency's own output statistics → its own staff's internal recommendations → an outside litigant's document corpus → international-lab comparators → on-record defense by the gatekeeper himself (Holland defending higher-than-FBI standards), so the failure is attested at every level including the top.
- **Methodology notes**: No separate methodology page; method visible in-article (X-file database analysis quote: the military "had made tentative identifications for more than half of those X-files"). NPR's "Grave Science" carries the parallel narrative. [inferred]: budget/ID chart built from JPAC annual reports.
- **Official impact (one line)**: Defense Secretary Hagel ordered a review and then sweeping reorganization — the accounting agencies were abolished and merged (into what became DPAA), Holland was removed, and Kelder was identified on Jan. 22, 2015 (in-article update; "Pentagon Overhauls Effort...", Mar. 31, 2014, series page).
- **Generalization**: any backlog-clearing institution — rape-kit testing, immigration courts, disability adjudication, cold-case units, toxic-site cleanup. Generic detector: output rate × backlog → completion horizon; then pick one backlog item and attempt to resolve it from already-held records; if an outsider can, the constraint is institutional will, not information.

---

### 5. Reliving Agent Orange — "The Children of Agent Orange" + "Dr. Orange" (2015–2019) — the government's own registry linked exposure to birth defects while one paid consultant kept benefits blocked

- **URL**: https://www.propublica.org/article/the-children-of-agent-orange and https://www.propublica.org/article/alvin-young-agent-orange-va-military-benefits (series: https://www.propublica.org/series/reliving-agent-orange — 33 stories, 2009–2019)
- **Partner/awards**: Co-published with **The Virginian-Pilot** (Charles Ornstein/ProPublica; Mike Hixenbaugh/Virginian-Pilot; data: Hannah Fresques, Olga Pierce).
- **What they found**:
  - Analysis of the VA's own Agent Orange Registry (668,000+ exams over 34 years): among **37,535 veterans with children born both before and after service**, children born during/after the war had birth defects at **13.1% (exposed) vs. 9.8% (unexposed)** — ~30% higher odds — while pre-war rates were statistically identical (~2.6–2.8%).
  - Since 2001, **8,100+ birth-defect claims filed; only 1,325 paid** — coverage limited to spina bifida (and, for female veterans' children, 18 conditions).
  - "Dr. Orange": Alvin Young — Air Force herbicide officer → VA Agent Orange Projects Office → White House OSTP → Pentagon consultant → **$600,000 no-bid VA contract (2012–2014)** — supplied the scientific rationale for denial for four decades, called C-123 reservists "freeloaders" in email, urged "DESTROY ALL" of contaminated aircraft in memos, and cited a Monsanto/Dow-funded paper he co-authored in a Pentagon report without disclosure; the Institute of Medicine found his key claims "inaccurate" and "based on conjecture and not evidence-based."
  - Blue Water Navy thread: sick sailors were forced to hunt through deck logs to prove their ships entered territorial waters; ProPublica crowdsourced research on **700+ ships** ("Help ProPublica Research More Than 700 Navy Ships," Feb. 26, 2016) and collected **3,352 structured survey responses** from exposed families.
- **Finding type(s)**:
  - `registry-suppressed-signal` — a health signal sitting unanalyzed inside the government's own exposure registry.
  - `science-gatekeeper-capture` — one strategically placed expert, with undisclosed industry ties, shaping decades of exposure policy across agencies.
  - `burden-shifted-proof` — the injured forced to assemble archival proof (deck logs) that the government itself holds or once held.
- **Evidence & sources**:
  - *Government registry data via a novel acquisition route* — FOIA for de-identified registry data was **denied** ("clearly unwarranted invasion of ... privacy") and lost on appeal; the team then requested the data **under academic-research rules**, hiring commercial **Schulman IRB**, drafting "a formal protocol that spelled out in detail exactly what they wanted to do with the data," committing to de-identification and secure storage; the VA undersecretary for health approved; data arrived Sept. 2016. (Editor's note: https://www.propublica.org/article/children-of-agent-orange-editors-note)
  - *FOIA lawsuits* — two suits for VA Agent Orange correspondence (Dec. 20, 2016; Jan. 19, 2017 — series page) yielding internal emails used in "Dr. Orange."
  - *Internal memos/emails via veterans' FOIA and litigation* — retired Maj. Wes Carter's C-123 FOIA corpus; Young's "freeloader" emails; Pentagon destruction memos.
  - *Contract records* — Young's no-bid VA contract and Pentagon reports.
  - *Structured crowdsourcing* — 35-question Screendoor survey, 3,352 completed responses, files/photos uploaded, monthly story loop (methodology: https://guides.coralproject.net/propublica-agent-orange-crowdsourcing/).
  - *Scientific literature + IOM panel findings* as external adjudicator of Young's claims.
- **Detection signature**: two distinct moves. (a) **within-family before/after cohort** — using each veteran's *pre-service* children as their own genetic/behavioral control, then diffing post-exposure birth-defect rates between self-reported exposed and unexposed groups ("focused on a group of 37,535 veterans who had children born before their service ... because many of the factors relevant to birth defects wouldn't change, including the veterans' genetic makeup"). (b) **gatekeeper career-trace** — mapping one consultant's positions, contracts, and written recommendations across 40 years against the agency decisions that followed each, plus his undisclosed funding — influence proven by recommendation-to-adoption sequences, not by title.
- **Corroboration structure**: registry statistics → five outside experts reviewed the analysis pre-publication → claims/payment records → named multigenerational family cases → the IOM's independent demolition of Young's science → Young's own on-record interview ("Am I wrong? I could be wrong.").
- **Methodology notes**: Stated: editor's note on the IRB acquisition route (URL above); Coral Project case study on the crowdsourcing pipeline (URL above); in-article analysis description in "The Children of Agent Orange." This is the cluster's clearest example of *acquisition-route innovation* as the enabling step.
- **Official impact (one line)**: The VA called the analysis "a step in the right direction" while disclaiming expertise; in Feb. 2019 the Federal Circuit (Procopio v. Wilkie) held the VA wrong to deny Blue Water Navy benefits ("A 'Bittersweet' Moment," series page), and Congress passed the Blue Water Navy Act later that year.
- **Generalization**: any exposure registry an agency collects but never analyzes (burn-pit registry, PFAS blood surveys, workplace exposure logs, pesticide applicator registries). Generic detectors: (a) request registry microdata through research-access channels when FOIA fails — the IRB route is reusable; (b) for capture: build a position/contract/recommendation timeline for the recurring named expert in denial documents and join it to funding disclosures.

---

### 6. Inside Trump's VA — "The Shadow Rulers of the VA" (2018) — three Mar-a-Lago members with no government role directed VA policy and personnel

- **URL**: https://www.propublica.org/article/ike-perlmutter-bruce-moskowitz-marc-sherman-shadow-rulers-of-the-va (series: https://www.propublica.org/series/inside-trump-va — 32 stories, 2018–2021)
- **Partner/awards**: ProPublica original (Isaac Arnsdorf).
- **What they found**:
  - Marvel chairman **Ike Perlmutter**, Palm Beach physician **Bruce Moskowitz**, and lawyer **Marc Sherman** — none with U.S. military or government service — "spoke with VA officials daily ... reviewing all manner of policy and personnel decisions" from Mar-a-Lago.
  - They weighed in on the **$10+ billion Cerner** electronic-records contract, pushed personnel removals that then occurred (secretary, deputy secretary, chief of staff), and later chapters showed sway over contracting/budgeting (Dec. 3, 2018) and an attempt to monetize veterans' medical records via an Apple-connected project (Sept. 27, 2021 — series page).
  - Officials wrote to them in the register of subordinates: "Received. I will begin a project plan and develop a timeline for action."
- **Finding type(s)**:
  - `shadow-governance` — private, unappointed actors exercising decision authority over a federal agency.
  - `access-capitalism` — proximity to the principal (club membership) converted into agency influence and personal-venture promotion (Perlmutter comic-book empire story, Jun. 3, 2020, series page).
- **Evidence & sources**:
  - *FOIA document set* — "hundreds of documents obtained through the Freedom of Information Act": emails between the trio and VA leadership, calendars, internal communications — published in full alongside the story.
  - *Personnel-action records* — the Leinenkugel memo proposing removals, matched against subsequent departures.
  - *Interviews* — former administration officials (anonymous: "Everyone has to go down and kiss the ring"); named outside participants.
  - *Calendar records* — "On Wilkie's first day at the VA, Sherman was waiting for him in his office, according to a calendar record."
- **Detection signature**: **org-chart/deference mismatch** — join the correspondence corpus to the agency's formal org chart: repeated approval-seeking language directed at persons absent from the chart is the tell ("In email after email, officials sought approval from the trio"); then corroborate authority by matching the outsiders' written proposals and removal lists to subsequent official actions and departures (proposal-to-action sequencing).
- **Corroboration structure**: FOIA emails (documentary spine) → calendars (physical access) → personnel outcomes matched to memos → insider interviews → subjects' joint denial through a crisis-communications consultant, quoted against their own emails.
- **Methodology notes**: No methodology page; acquisition stated in-article ("We are publishing the emails and other documents we obtained through the Freedom of Information Act for this story."). [inferred]: FOIA targeted senior officials' correspondence with the three names.
- **Official impact (one line)**: Democrats vowed an investigation the next day (Aug. 8, 2018, series page), VoteVets sued to block the arrangement (Aug. 16, 2018), and House oversight followed; the series later documented the whistleblower-office abuses and secretary-misconduct probes it triggered.
- **Generalization**: any agency or company where correspondence shows deference to names outside the hierarchy (donor influence over university admissions, consultant capture of a regulator, family-office sway over a public pension). Generic detector: NER over email/calendar corpora → set-difference against staff directory → rank outsiders by officials' deference verbs and by proposal-to-action match rate.

---

### 7. Inside Trump's VA — "The VA's Private Care Program Gave Companies Billions and Vets Longer Waits" (2018) — privatized care middlemen consumed 24 cents of every dollar while veterans waited longer

- **URL**: https://www.propublica.org/article/va-private-care-program-gave-companies-billions-and-vets-longer-waits (methodology: https://www.propublica.org/article/how-we-crunched-the-numbers-on-the-vas-private-care-program)
- **Partner/awards**: Co-reported with **PolitiFact** (Isaac Arnsdorf, Jon Greenberg).
- **What they found**:
  - Of **$10.3 billion** in Veterans Choice spending since 2014, **$1.9 billion (24%)** went to the two middlemen contractors (TriWest, Health Net) as overhead — vs. the ACA's 15% cap, private-sector 10–12%, and Tricare's 8%.
  - Per-referral processing fees of **$295–$318**, against ~$201 average medical cost of a primary-care referral; the VA IG found **$140 million** in overpayments (2014–2017), including duplicate payments ($69.9M) and contractors billing VA more than they paid providers ($2M).
  - **41% of Choice referrals blew the 30-day statutory wait limit**; average waits ~50 days (up to 70), vs. the program's promise to rescue veterans from 30-day waits; 1.9 million veterans used the program.
- **Finding type(s)**:
  - `privatization-value-leak` — public money diverted to intermediary overhead without commensurate service gain.
  - `SLA-breach-at-scale` — systematic violation of the program's own statutory service-level guarantee.
- **Evidence & sources**:
  - *VA biweekly expenditure reports to Congress* (public but unanalyzed) — the claims/fee totals.
  - *VA claims-processing reports* (through Sept. 30, 2018) and *VA OIG referral-fee report*; *GAO findings*; *Congressional Research Service* figures; *fpds.gov federal contract records*.
  - *Litigation/court records* — a Nov. 2017 court opinion on a Glassdoor grand-jury subpoena revealing the TriWest criminal probe; emails between TriWest's CEO and VA officials.
  - *Company statements* — TriWest's alternative overhead math, quoted and rebutted.
- **Detection signature**: **overhead-ratio benchmark diff** — compute the administrative loss ratio from the program's own expenditure reports ("$1.9 billion in overhead costs divided by the sum of those overhead costs and the $6 billion in claims. That computes to 24 percent"), then diff against three named benchmark regimes (ACA cap, commercial norm, Tricare); pair with **statutory SLA compliance count** (share of referrals exceeding the 30-day legal limit). The referral-fee arithmetic ("5.3 million such referrals...multiplied by $295" ≈ $1.6B) reconstructed a number the agency never published.
- **Corroboration structure**: agency's own reports → IG/GAO error findings → benchmark regimes → adversarial review (figures put to VA and contractors pre-publication; "The VA declined to comment") → grand-jury/DOJ probes as independent validation of the fraud dimension.
- **Methodology notes**: Stated, dedicated page: "How We Crunched the Numbers on the VA's Private Care Program" (URL above) — formula, referral-count multiplication, flat-fee assumption, overcount caveat, benchmark-maturity caveat.
- **Official impact (one line)**: The VA secretary conceded the agency was "taken advantage of" the next day (Dec. 19, 2018, series page); House/Senate veterans' committees invoked it in MISSION Act implementation oversight; DOJ probes of both contractors proceeded.
- **Generalization**: any outsourced public program with a third-party administrator — Medicaid MCOs, charter-school management fees, privatized prison health, defense logistics. Generic detector: administrative-loss ratio from budget documents vs. statutory/industry caps; per-transaction fee × transaction count vs. value delivered; SLA breach share from the program's own performance reports.

---

### 8. The Night Raids (2022) — CIA-backed Afghan "Zero Units" killed at least 452 civilians in raids the U.S. never accounted for

- **URL**: https://www.propublica.org/article/afghanistan-night-raids-zero-units-lynzy-billing (takeaways: https://www.propublica.org/article/afghanistan-night-raids-zero-units-investigation-takeaways)
- **Partner/awards**: ProPublica original (Lynzy Billing; field production Muhammad Rehman Shirzad, Kern Hendricks). Michael Kelly Award (https://www.propublica.org/atpropublica/lynzy-billing-wins-michael-kelly-award-for-the-night-raids); Overseas Press Club Ed Cunningham Award; spawned the animated documentary "The Night Doctrine."
- **What they found**:
  - **At least 452 civilians killed in 107 raids** by the 02 unit alone over four years (June 2017–July 2021) — an acknowledged undercount; the UN had documented 80 killed by the same unit in 2019 alone.
  - Four **CIA-funded, trained, armed and directed** Zero Units (01–04); "U.S. special operations forces soldiers working with the CIA often joined them" (~10–12 Americans with 70–80 Afghans per raid); a U.S. Ranger described pre-raid "slant" calculations predicting civilian deaths.
  - Raids repeatedly hit people with no connection to the Taliban or any terrorist group; no accountability mechanism followed the deaths.
- **Finding type(s)**:
  - `atrocity-undercount` — lethal-operation casualties never aggregated by the sponsor into any official ledger.
  - `outsourced-accountability-void` — lethal action routed through a proxy force so no U.S. body owns the civilian toll.
- **Evidence & sources**:
  - *Field forensics* — 30+ raid-site visits (Nangarhar): blown doors, burn patterns, bullet-marked walls, matched to testimony.
  - *Convergent local registries* — "government statistical department records, IDs and hospital records ... In some cases, we also found death certificates and coroner reports at the federal forensics department in Kabul."
  - *Leaked operational paper* — "leaked security incident reports from the country's intelligence agency, police and nongovernmental organizations."
  - *Insider participants* — two active Zero Unit soldiers (raid details and personal diaries), a U.S. Army Ranger, former Afghan intelligence chief Rahmatullah Nabil on record.
  - *Remote sensing* — "Using satellite imagery and geolocation, we were able to verify the locations of many of those raids, especially those accompanied by airstrikes, by searching for evidence of damaged homes and structures."
  - *350+ interviews* across officials, soldiers, ex-CIA officers, doctors, coroners, eyewitnesses, elders; four years of fieldwork.
- **Detection signature**: **multi-registry casualty ledger** — build a raid-level database where each incident row is confirmed by joining at least two independent record types (eyewitness testimony × physical site evidence × medical/forensic paper × satellite damage signature × insider incident reports); the count is the sum of rows that survive the join, which is why it is presented as a floor, not an estimate.
- **Corroboration structure**: per-incident multi-source triangulation (testimony → site → paper → satellite) rather than corpus-level statistics; insider diaries corroborate the operational pattern; UN counts benchmark a subset; CIA response ("systematic propaganda campaign") quoted against the documentary record.
- **Methodology notes**: Stated in the published "How We Reported This Story" section (quotes above, from the article page).
- **Official impact (one line)**: DoD did not respond; CIA issued a denial-adjacent statement; the work won major awards and drove congressional and press attention to proxy-force accountability, with no formal U.S. accounting to date.
- **Generalization**: undercounted deaths anywhere officialdom won't count — police raid fatalities, border deaths, paramilitary violence, disaster tolls. Generic detector: define an incident schema; require ≥2 independent registry types per row (medical, forensic, geospatial, testimonial, insider-log); publish the surviving-row floor and the rejection log.

---

### 9. Military court secrecy — the Bonhomme Richard case and ProPublica v. the Navy (2022–2026) — the Navy prosecuted a junior sailor for a $1B ship fire while hiding the court record a 2016 law required it to release

- **URL**: https://www.propublica.org/article/navy-bonhomme-fire-records (Sept. 8, 2022, Megan Rose); complaint: https://www.propublica.org/atpropublica/propublica-files-complaint-and-emergency-motion-to-release-court-records-in-high-profile-ship-fire-case; ruling coverage: https://www.propublica.org/article/navy-court-records-ruling-first-amendment; case docket context: https://www.rcfp.org/briefs-comments/propublica-v-reynolds/
- **Partner/awards**: ProPublica original (Megan Rose); media-coalition amicus support (RCFP et al.).
- **What they found**:
  - Despite a **2016 law** requiring public access to court-martial records through "pretrial, trial, post-trial, and appellate processes," the Navy released **two documents** while trial was pending in the case of Seaman Recruit Ryan Mays, accused of the 2020 arson that destroyed the **$1B+ USS Bonhomme Richard**; DoD had interpreted the statute as post-trial only.
  - The Navy's own **400+ page command investigation** attributed the loss to systemic failures (readiness, firefighting, command) — a record juxtaposed with a prosecution theory hanging the loss on one 20-year-old sailor, who was acquitted (Sept. 2022, topics page).
  - A prosecutor argued compliance was impractical: "Military courts don't have a clerk to coordinate records."
- **Finding type(s)**:
  - `statute-practice-gap` — an agency's operating practice directly contradicting the transparency statute governing it.
  - `institutional-scapegoating` (flagged; supported by the acquittal and command-investigation contrast) — individual prosecution deflecting from documented systemic failure.
  - `access-litigation-as-reporting` — the news organization generating the evidence base by suing for it.
- **Evidence & sources**:
  - *Court filings obtained/contested* — defense motions, prosecutor briefs, the two released records; ProPublica's own emergency motion and federal complaint.
  - *Navy command investigation* — 400+ pages on the fire's causes.
  - *Statutory text and DoD implementing rules* — the 2016 provision vs. DoD's narrowing interpretation (later-rewritten DoD rules covered by Government Executive, Feb. 2023).
  - *Expert interviews* — retired Navy judge Paul LeBlanc; ProPublica deputy general counsel Sarah Matthews on the First/Sixth Amendment theory.
- **Detection signature**: **statute-vs-practice release audit** — enumerate what a specific transparency statute mandates, then count what the institution actually released in a live marquee case (2 documents) — the arithmetic gap is the story; layered with a **systemic-findings vs. single-defendant diff** (the service's own investigation blaming the system while its prosecutors blamed one sailor).
- **Corroboration structure**: statutory text → agency practice in a named case → agency's own investigative findings → outcome (acquittal) → federal litigation record; the March 2026 ruling (judge held the press entitled to court-martial and Article 32 records — Courthouse News; ProPublica topics page) retroactively validated the framing.
- **Methodology notes**: No methodology page; the acquisition method *is* the litigation, documented in ProPublica's own filings (URLs above). [inferred]: continued docket monitoring of United States v. Mays.
- **Official impact (one line)**: The Navy released document tranches in Oct. 2022 and Mar. 2023; DoD rewrote court-records rules (contested); in March 2026 a federal judge ruled for ProPublica that the press has a right of access to military court records (topics page; courthousenews.com coverage of the ruling).
- **Generalization**: any adjudicative system with a records mandate — immigration courts, state juvenile courts, administrative tribunals, coroner inquests. Generic detector: pair each records statute with a live high-profile docket; count mandated-vs-released items; separately diff the institution's internal causal findings against the theory of its prosecution.

---

### 10. "The Army Increasingly Allows Soldiers Charged With Violent Crimes to Leave the Military Rather Than Face Trial" (2023) — a quiet administrative exit replaced courts-martial for violent offenses

- **URL**: https://www.propublica.org/article/military-army-administrative-separation (Apr. 10, 2023; rule-change follow-up: https://www.texastribune.org/2024/04/19/us-army-soldiers-violent-crimes/)
- **Partner/awards**: Co-published with **The Texas Tribune** and **Military Times** (ProPublica–Texas Tribune investigative unit, with Military Times).
- **What they found**:
  - From ~**8,000 Army courts-martial cases** reaching arraignment: of ~**900 soldiers** granted discharge in lieu of court-martial (Chapter 10) over the past decade, **more than half** were accused of violent crimes — up from ~30% the decade before.
  - For sexual assault, roughly **1 in 4** service members charged were administratively discharged rather than tried (726 of 1,000+ across branches, 2012–2021).
  - A federal watchdog had recommended abolishing the practice in **1978**; named case studies (Faustino Vallo — aggravated assault; Tony Thomas — sexual assault with DNA evidence and a probable-cause finding) showed charges evaporating via discharge.
- **Finding type(s)**:
  - `accountability-off-ramp` — severe cases exiting the formal adjudication pipeline through a low-scrutiny administrative side door.
  - `severity-drift` — the off-ramp's caseload shifting toward graver offenses over time.
- **Evidence & sources**:
  - *Courts-martial database via FOIA* — "data from the Army Court-Martial Information System, which covers cases that were referred to the Army's two highest trial courts dating back to 1989," obtained "under the federal Freedom of Information Act."
  - *Case files/records for named soldiers* — charge sheets, probable-cause findings, discharge outcomes.
  - *Historical oversight record* — the 1978 watchdog recommendation to abolish the practice.
  - *Interviews* — victims, families, Army criminal-law chief (Col. Christopher Kennebeck) on record.
- **Detection signature**: **off-ramp migration analysis** — within a case-level pipeline dataset, isolate the administrative exit route (Chapter 10), classify each case's charges as violent using an external standard ("categorized crimes as violent using the National Institute of Justice's definition" across eight UCMJ articles: murder, manslaughter, sexual assault, robbery, physical assault, maiming, domestic violence, assault on officers), and trend the violent share of off-ramp users across decades (30% → >50%). The disclosed limitation ("The database does not include cases that were dismissed or resolved before they reached arraignment") turns the count into a floor claim.
- **Corroboration structure**: database trend → named cases instantiating the mechanism → historical watchdog recommendation showing the risk was known for 45 years → Army's own on-record defense conceding the practice's use where proof is hard ("cases in which the Army is not able to meet the necessary burden of proof to win at trial").
- **Methodology notes**: Stated in an in-article methodology sidebar (data source, FOIA, NIJ violent-crime definition, eight UCMJ articles, arraignment-only limitation — quotes above from article URL).
- **Official impact (one line)**: In April 2024 the Army stripped commanders of sole authority over these discharges — the new Office of Special Trial Counsel must now approve Chapter 10 requests in covered cases (Texas Tribune follow-up URL above).
- **Generalization**: prosecutorial diversion, nolle prosequi patterns, police-officer resignations-in-lieu-of-discipline, professional-license surrender instead of revocation, university expulsion-vs-withdrawal. Generic detector: in any sanctions pipeline, compute the share of severe-offense cases exiting via each low-scrutiny route, trended over time and benchmarked against an external severity taxonomy.

---

### 11. "Blinken Says Israeli Units Accused of Serious Violations Have Done Enough to Avoid Sanctions. Experts and Insiders Disagree." (2024) — the State Department's own vetting panel recommended cutting aid to Israeli units; the secretary declined

- **URL**: https://www.propublica.org/article/blinken-israel-military-aid-human-rights-violations-leahy-law (companion: https://www.propublica.org/article/biden-blinken-state-department-israel-gaza-human-rights-horrors)
- **Partner/awards**: ProPublica original (Brett Murphy).
- **What they found**:
  - The **Israel Leahy Vetting Forum** — the department's internal expert panel — recommended disqualifying multiple Israeli military/police units from U.S. aid over alleged gross violations (extrajudicial killings by Border Police; a battalion that gagged, handcuffed and left an elderly Palestinian American man for dead; an alleged torture/rape of a teenager in interrogation).
  - Blinken sat on the recommendations for months, then determined in May 2024 that remediation — including **three months of community service for killing an unarmed Palestinian** — was "adequate" under the Leahy law, keeping the units eligible.
  - Structural special treatment: Israel, unlike other states, is consulted during the vetting process; ex-official Charles Blaha: "there are literally dozens of Israeli security force units that have committed gross violations of human rights and remain eligible for assistance."
- **Finding type(s)**:
  - `recommendation-decision-gap` — an institution's own expert process reaching a conclusion its principal declines to act on.
  - `selective-enforcement-carve-out` — a compliance regime applied by different procedure to a favored party.
- **Evidence & sources**:
  - *Internal memo obtained* — Blinken's justification memo to Congress ("obtained by ProPublica"; channel unstated — leak).
  - *Vetting-forum meeting minutes* — internal deliberative records.
  - *Interviews* — former State officials (Blaha and others), congressional aides; prior reporting (Al-Monitor unit names) credited.
  - *Public determinations* — the department's announcements diffed against the internal paper.
- **Detection signature**: **recommendation-decision gap** — obtain the internal recommendation record and the principal's final determination for the same cases, then diff outcome, timeline (months of delay), and stated remediation against the statute's standard; the process's own paper trail proves the deviation. Secondary: **differential-process detection** — compare the procedural path applied to the favored state (consultation rights, remediation deference) with the default path applied to everyone else.
- **Corroboration structure**: internal memo → forum minutes → multiple ex-insider witnesses on record → department non-denial ("taken extensive steps to implement the Leahy law for all countries"), each layer independent of the leak.
- **Methodology notes**: No methodology page. [inferred]: sourced leak of deliberative documents plus systematic interviews of forum alumni; consistent with Murphy's companion piece built on internal dissent memos and cables.
- **Official impact (one line)**: Drove congressional letters and floor scrutiny of Leahy enforcement and became the reference reporting in the 2024–25 debate over conditioning Israel aid; no unit was sanctioned.
- **Generalization**: sanctions waivers, export-control licensing, pharmaceutical approvals, bank-examiner reports vs. enforcement actions, university misconduct panels vs. provost decisions. Generic detector: for any two-stage regime (expert recommendation → political decision), acquire both stages' records for identical case IDs and measure reversal rate, delay, and any party-specific procedural deviations.

---

### 12. Veterans' Care at Risk — "DOGE Developed Error-Prone AI Tool to 'Munch' Veterans Affairs Contracts" (2025) — a one-day-old LLM script with hallucinated values drove VA contract cancellations

- **URL**: https://www.propublica.org/article/trump-doge-veterans-affairs-ai-contracts-health-care (June 6, 2025; prompts companion: https://www.propublica.org/article/inside-ai-tool-doge-veterans-affairs-contracts-sahil-lavingia; series: https://www.propublica.org/series/veterans-care-at-risk)
- **Partner/awards**: ProPublica original (Brandon Roberts, Vernal Coleman, Eric Umansky). GIJN featured it as a "How They Did It" methods case (https://gijn.org/stories/how-the-did-it-propublica-ai-tool-cut-veterans-affairs-contracts/).
- **What they found**:
  - DOGE engineer **Sahil Lavingia** — "no health care or government experience," building on his first day — created an AI tool using outdated OpenAI models that flagged **2,000+ VA contracts** as "MUNCHABLE" (cancellable).
  - The model **hallucinated contract values**, concluding **~1,100 contracts were each worth $34 million** when some were as small as **$35,000**; it read only the **first 10,000 characters (~2,500 words)** of each contract.
  - Prompts required judgments the model couldn't ground: cancel anything not "directly supporting patient care," kill undefined "DEI" contracts; flagged-then-canceled contracts included gene-sequencer maintenance for cancer research, blood-sample analysis, and nursing-care measurement tools; at least two dozen canceled contracts traced.
  - Series companions: internal VA emails showed cuts hitting "life-saving cancer trials" and 1,000+ veterans' treatment access (May 6, 2025, series page); staffing stories found hundreds of doctors/nurses rejecting VA offers and therapist departures disrupting mental-health care (Aug. 8, 2025; Mar. 12, 2026 — same series).
- **Finding type(s)**:
  - `automation-malpractice` — consequential government decisions delegated to a demonstrably flawed automated system.
  - `decision-provenance-capture` — obtaining the literal decision artifact (code + prompts) behind official actions.
  - `hollowing-by-attrition` (series companions) — service degradation via staff/contract removal documented from inside.
- **Evidence & sources**:
  - *The code, prompts, and flagged-contract list* — "ProPublica obtained the code and the contracts it flagged from a source"; Lavingia later published the code on GitHub, locking in authenticity.
  - *Expert panel review* — "shared them with a half dozen AI and procurement experts" (named: Waldo Jaquith, ex-Treasury IT-contracting; Prof. Cary Coglianese, Penn; Prof. Shobita Parthasarathy, Michigan).
  - *Ground-truth contract records* — federal procurement data diffed against the model's value outputs.
  - *Interview with the builder* — Lavingia on record.
  - *Internal VA emails* (series companions) — leaked internal messages on care impacts; reader callouts to VA staff (series page).
- **Detection signature**: **algorithm forensics / decision-code diff** — obtain the actual decision artifact, review prompts line-by-line against the decisions taken, and diff machine-extracted fields (contract value) against authoritative procurement records: the 1,100 × "$34M" cluster is a hallucination fingerprint (identical repeated values) found by joining model outputs to real contract values. Reproducibility anchored by publishing the prompts verbatim with expert annotation.
- **Corroboration structure**: source-provided artifact → builder's own on-record confirmation and GitHub publication → six independent experts → procurement-record ground truth → traced canceled contracts to real-world service losses → VA press-office response ("multiple reviews by VA employees").
- **Methodology notes**: Stated in-article (acquisition and expert-review sentences quoted above); GIJN methods piece (URL above; 403 to our fetcher but indexed) documents the reporting pipeline; the prompts companion is effectively a published methodology annex.
- **Official impact (one line)**: Senators Blumenthal and King demanded a VA IG investigation into ~600 canceled contracts citing the reporting (June 2025, https://www.propublica.org/article/doge-ai-veterans-affairs-canceled-contracts-senators-trump), with follow-on demands after the VA refused to give Congress a complete cancellation list.
- **Generalization**: any government-by-model surface — benefits eligibility scoring, fraud-flagging, immigration triage, procurement scoring, tenant screening. Generic detector: obtain the model artifact (prompt/config/code) via source or FOIA; join its per-case outputs to authoritative registries on case ID; cluster impossible outputs (identical repeated values = hallucination fingerprint); have domain experts annotate the instructions.

---

## Additional notable items (not fully extracted)

- **"The U.S. Built a Blueprint to Avoid Civilian War Casualties. Trump Officials Scrapped It."** (Mar. 10, 2026, Hannah Allam) — dismantling of the Civilian Harm Mitigation and Response (CHMR) enterprise (~200 personnel; "around 90% of the CHMR mission is gone") amid strikes in Iran/Yemen/Somalia (Minab school strike: 165+ dead, mostly children); evidence: more than a dozen current/former national-security officials (most anonymous "for fear of retaliation"), a former CHMR adviser's private briefing notes to a Senate office, the 2022 Pentagon CHMR action plan and DoD instruction as the baseline to diff against, and third-party casualty monitors (Bellingcat, HRANA, New America, ACLED). Signature: **safeguard-demolition diff** — enumerate a written protective apparatus, then measure its removal against a rising harm series. Mirror consulted: https://www.govexec.com/defense/2026/03/us-built-blueprint-avoid-civilian-war-casualties-trump-officials-scrapped-it/412166/; follow-up: https://www.propublica.org/article/hegseth-trump-war-civilian-casualties-elizabeth-warren-pentagon (July 2026).
- Other standalone military items on the topics page (https://www.propublica.org/topics/military) not extracted here: Littoral Combat Ship program failures (2023), Coast Guard icebreaker design problems (2025), Kabul evacuation reconstruction with Alive in Afghanistan (2022), Turkish drone export oversight gaps (2022), Russia's private military expansion (2022).

---

## Cluster Synthesis

### 1) Recurring evidence-source types (frequency across the 12 extracted entries)

| Evidence class | Count | Where |
|---|---|---|
| Internal correspondence/memos/calendars (FOIA, leak, or litigation) | 7 | Brain Wars, Dr. Orange, Shadow Rulers, Leahy, DOGE (+VA emails), Failing the Fallen, 7th Fleet (x-ref) |
| Government case-level administrative databases (FOIA or negotiated access) | 6 | Longshore CMS (Disposable Army), Army Court-Martial Information System, VA Choice expenditure/claims reports, Agent Orange Registry (IRB route), X-files corpus, DOGE contract lists |
| Named-individual case-file reconstruction (medical/personnel/court records + interviews) | 6 | Brain Wars, Disposable Army, Failing the Fallen (Kelder), Agent Orange (Carter), Bonhomme (Mays), Army separations (Vallo/Thomas) |
| Unpublished internal studies / IG / GAO / audit material | 5 | Brain Wars, Disposable Army, VA Choice, Failing the Fallen, Bonhomme (command investigation) |
| Insider leaks / sympathetic sources | 5 | X-files package, DOGE code, VA internal emails, Night Raids incident reports & raid diaries, Leahy memo |
| Litigation as acquisition instrument (FOIA suits, access suits) | 4 | LAT v. Labor (Disposable Army), ProPublica FOIA suits (Agent Orange), ProPublica v. Navy (Bonhomme), Brain Wars FOIA fight |
| Third-party independent counts/benchmarks | 4 | Drone counts (BIJ/NAF/LWJ), ICMP/EAAF labs, ACA/Tricare/Medicare overhead norms, UN/monitor casualty counts |
| Official public statements treated as a dataset | 3 | Drones, Leahy determinations, Shadow Rulers denials-vs-emails |
| Structured crowdsourcing / reader callouts | 2 | Agent Orange survey (3,352) + ship-log volunteers; Veterans' Care at Risk staff callouts |
| Field forensics + satellite/geolocation | 1 (+x-ref) | Night Raids (7th Fleet used ship logs/bridge-data reconstruction) |
| Census-flagged distinctive classes — all confirmed present | — | mishap/command investigation files (7th Fleet, Bonhomme), courts-martial records (Bonhomme, Army separations), exposure registries (Agent Orange), MIA "X-files"/casualty records (Failing the Fallen, Disposable Army contractor toll), VA claims/staffing data (Choice, Veterans' Care at Risk), Pentagon IG material (Disposable Army, Brain Wars) |

### 2) Recurring detection signatures (my tags; frequency)

| Signature | Count | Entries |
|---|---|---|
| **Record-vs-record contradiction** (institution's own paper against its other paper or its public claims): report-to-record deficit; self-contradiction matrix; org-chart/deference mismatch; statute-vs-practice audit; recommendation-decision gap | 6 | Brain Wars, Drones, Shadow Rulers, Bonhomme, Leahy, 7th Fleet (x-ref: warnings vs assurances) |
| **Denominator/throughput arithmetic** (rates, horizons, ratios computed from the institution's own reports): mandate-horizon math; overhead-ratio diff; SLA breach counts; instrument dead-letter check; dispute-rate recompute | 4 | Failing the Fallen, VA Choice, Brain Wars, Disposable Army |
| **Acquisition-route innovation as the enabling move** (IRB research access, litigation, insider corpus) | 4 | Agent Orange, Bonhomme, Disposable Army, Failing the Fallen |
| **Gatekeeper/actor career-trace** (one person's positions, contracts, recommendations joined to institutional adoptions) | 3 | Dr. Orange, Shadow Rulers, DOGE (Lavingia) |
| **Single-case paper-trail replay** (re-running one case from held records to prove the system could have succeeded) | 3 | Failing the Fallen (Kelder), Agent Orange (Carter C-123), Brain Wars (Medina/Dyarman files) |
| **Peer-institution benchmark diff** (method or cost vs. comparable institutions) | 3 | Failing the Fallen (ICMP), VA Choice (Tricare/ACA), Brain Wars (civilian concussion norms) |
| **Severity-stratified adverse-outcome rates** (outcomes joined to severity strata) | 2 | Disposable Army, Army separations |
| **Multi-registry ledger construction** (floor-count built from ≥2 independent record types per row) | 2 | Night Raids, Agent Orange crowdsourced exposure ledger |
| **Algorithm forensics / decision-code diff** | 1 (new, 2025) | DOGE |
| **Safeguard-demolition diff** (protective apparatus enumerated, then its removal measured against a harm series) | 1 (+series echoes) | CHMR blueprint (additional items); Veterans' Care at Risk attrition stories |

### 3) Transferable pattern candidates

**A. Severity-Inverted Denial Screen**
Mechanics: In any claims/benefits/adjudication system, join case outcomes to a severity/cost stratum and to the deciding party. A good-faith system denies weak claims; a throughput- or profit-driven system contests the *costliest* claims at elevated rates. The 2009 Disposable Army analysis (protests in ~half of serious-injury cases, >50% of PTSD claims, while appeals succeeded ~75% of the time) and the Army's Chapter 10 drift (violent-crime share of discharges rising 30% → 50%+) are the same inversion in insurance and justice clothing. High reversal-on-appeal alongside high initial denial is the confirming second join.
Minimum data: case-level records with (outcome, severity proxy, deciding entity), ideally dated. FOIA-able case-management extracts suffice; no document text needed.
Recognition cue in any domain: denial/diversion rate that *rises* with claim cost or offense gravity, or an appeal-reversal rate far above the initial-grant rate.

**B. Mandate-Horizon Arithmetic**
Mechanics: Divide the institution's backlog by its own measured annual throughput and state the completion horizon; set it beside budget and any statutory benchmark. JPAC's 72 IDs/year against 45,000 recoverable missing (600+ years, on $373M per five years) reframed a sentimental mission story as a math scandal. Works because numerator and denominator both come from the institution's own reports, leaving nothing to dispute but the implication.
Minimum data: official output counts (annual reports), a backlog estimate, a budget line; a statutory target if one exists.
Recognition cue: any agency reporting activity ("we performed N") without ever reporting horizon; compute it — if the horizon exceeds a human lifetime, the mission is nominal.

**C. Shadow Authority Trace**
Mechanics: Acquire correspondence/calendar corpora for an institution's leadership; extract all counterparties; set-difference against the formal org chart and appointment records; rank outsiders by officials' deference language and by proposal-to-subsequent-action match rate. The Shadow Rulers finding was not that Mar-a-Lago members had opinions but that officials *reported to them* in writing and that their removal lists and policy pitches were executed. Dr. Orange is the slow-motion variant: one outside consultant's recommendations matched to four decades of agency adoptions, plus undisclosed industry funding.
Minimum data: FOIA-able email/calendar sets for named officials + a staff directory + a decision/personnel timeline.
Recognition cue: approval-seeking verbs ("for your review/approval," "as you directed") aimed at addresses outside the hierarchy; outsider names recurring across unrelated decision files.

**D. Self-Contradiction Matrix**
Mechanics: Collect every dated official statement about a single quantity (casualties, costs, counts), each with its coverage window; test all pairs for joint logical possibility (interval vs. cumulative, monotonicity). ProPublica's drone-figures piece never had to adjudicate between the government and NGOs — the government's "about 30 in one year" and later "single digits total" impeached each other. External counts serve only as bounding context.
Minimum data: a clippings/statements archive with dates and scopes — no privileged access at all.
Recognition cue: an opaque program whose spokespeople issue occasional reassuring numbers through different mouths over time; the more mouths and years, the higher the contradiction yield.

**E. Ground-Truth Undercount Ledger**
Mechanics: Where officialdom refuses to count harm, build the count bottom-up: define an incident schema, then admit a row only when ≥2 independent record types converge (testimony × physical site evidence × medical/forensic paper × satellite signature × insider logs). Publish as a floor with the rejection log. Billing's 452-deaths/107-raids ledger, the Agent Orange crowdsourced exposure corpus, and (in the sibling cluster) the 7th Fleet warning-ledger are instances at different scales.
Minimum data: at least two independent registry families reachable per incident (local medical/forensic records, remote sensing, leaked operational reports, structured survivor testimony).
Recognition cue: an official body asserting "no reliable figures exist" about harms its own operations produce — the absence of a count where one should exist is itself the lead, and the ledger is the method.

*(Runner-up patterns already described in the signature table and directly reusable as detectors: **Algorithm Forensics / decision-code diff** — obtain the deciding artifact and diff its outputs against authoritative registries, with identical repeated values as the hallucination fingerprint; and **Statute-vs-Practice Release Audit** — count mandated-vs-actual disclosures in one live marquee case, with access litigation as the evidence generator.)*

---

*Report generated 2026-07-29. All URLs verified by direct fetch except where a mirror is explicitly noted (GIJN methods piece 403'd to our fetcher; CHMR story read via Government Executive republication; DOGE main-story content verified via Truthout republication and the ProPublica prompts companion, canonical URL confirmed via the senators' follow-up article).*
