# ProPublica Evidence Ontology — Report 11: Immigration & Border

**Scope basis (empirical census, not memory).** Series index pages fetched directly from propublica.org on 2026-07-29: `zero-tolerance` (79 articles), `the-new-immigration` (25), `inside-the-border-patrol` (26), `ms-13-on-long-island` ("Trapped in Gangland", 16), `deported-and-imprisoned` (12), `the-taking` (12), `billions-on-the-border` (5), `no-sanctuary` (10), `immigration` (resolves to "The Travel Ban", 12), plus the topic page `propublica.org/topics/immigration` (413 stories since 2016). From that universe I selected 12 investigations maximizing coverage of the evidence classes flagged in the census: leaked/secret audio, ICE/CBP custody and use-of-force records, EOIR immigration-court data, eminent-domain land records, state border-spending ledgers, and case-by-case deportee verification against foreign-country records. All are ProPublica originals or formal co-publications; partners noted per entry.

Tag and signature vocabulary is free-form and defined on first use.

---

### Listen to Children Who've Just Been Separated From Their Parents at the Border (2018) — a secret recording from inside a CBP facility made family separation audible and helped end the policy in 48 hours
- **URL**: https://www.propublica.org/article/children-separated-from-parents-border-patrol-cbp-trump-immigration-policy
- **Partner/awards**: ProPublica original (Ginger Thompson, June 18, 2018). Zero Tolerance series won the first-ever Peabody Catalyst Award (https://www.propublica.org/atpropublica/propublica-zero-tolerance-series-wins-first-ever-peabody-catalyst-award), a George Polk Award for immigration reporting, the Paul Tobenkin Award (https://www.propublica.org/atpropublica/propublica-zero-tolerance-series-wins-paul-tobenkin-award), and was a finalist for the Pulitzer Gold Medal for Public Service; Thompson won the 2019 John Chancellor Award (https://www.propublica.org/atpropublica/propublicas-ginger-thompson-wins-john-chancellor-award-for-excellence-in-journalism).
- **What they found**:
  - ~7-minute audio recorded covertly inside a U.S. Customs and Border Protection facility captured roughly 10 Central American children, estimated ages 4–10, wailing for parents they had been separated from less than 24 hours earlier.
  - A Border Patrol agent is heard joking over the crying: "Well, we have an orchestra here" — the state's own voice mocking the harm.
  - A 6-year-old Salvadoran girl, Alison Jimena Valencia Madrid, repeatedly pleads to call her aunt and recites a memorized phone number; ProPublica called the number, reached the aunt, and identified the girl and her detained mother, Cindy Madrid.
  - Context: 2,300+ children separated since the April 2018 "zero tolerance" launch (per the series description at https://www.propublica.org/series/zero-tolerance).
- **Finding type(s)**: `custody-harm concealment` (an agency hiding conditions/harm affecting people in its custody, revealed by primary evidence from inside the closed space); `sensory ground truth` (a finding whose force is that the primary evidence lets the public directly perceive the harm officials described abstractly).
- **Evidence & sources**:
  - Leaked covert audio — recorded inside the CBP facility by an unnamed person who "requested anonymity for fear of retaliation"; passed to Rio Grande Valley civil-rights attorney Jennifer Harbury, who gave it to ProPublica (chain of custody stated in the article).
  - Telephone verification interview — the aunt, reached via the number the child recites on tape, confirmed receiving the same call; family interviews identified the child and mother.
  - Government statements/policy record — zero-tolerance policy announcements used as the frame the audio contradicts in texture if not in letter.
- **Detection signature**: **Embedded-verifier leak authentication.** A leaked recording of unknown provenance contained an independently testable fact — a phone number recited by a child — and dialing that number confirmed the recording's authenticity, located the family, and converted anonymous audio into a named, corroborated case. The leak carried its own verification key.
- **Corroboration structure**: covert recording → chain-of-custody attribution (source→attorney→newsroom) → real-world test of an internal detail (the phone number) → named family interview → government response sought. Follow-ups compounded it: DHS Secretary Nielsen was confronted with the tape at a White House briefing (https://www.propublica.org/article/kirstjen-nielsen-homeland-security-crying-children-white-house-press-briefing) and the girl was tracked through reunification (https://www.propublica.org/article/salvadoran-girl-whose-cries-helped-end-family-separation-policy-embraces-new-life).
- **Methodology notes**: no standalone methods page; provenance and verification steps are stated inside the article itself. [Chain-of-custody narration is the methodology.]
- **Generalization**: any closed institution (detention, nursing homes, psychiatric wards, mines, factory farms) where policy harm is only ever described secondhand. A generic detector looks for leaked media containing self-verifying details (numbers, names, timestamps, station IDs) that can be tested against the outside world, and treats "the state's own voice on tape" as the highest-leverage artifact class.
- **Impact**: within ~48 hours of publication the president signed the executive order ending routine family separation; the recording was played in Congress and at the White House briefing.

---

### Inside the Cell Where a Sick 16-Year-Old Boy Died in Border Patrol Care (2019) — cell video obtained from a local police department proved CBP's account of Carlos Hernandez Vasquez's death was false
- **URL**: https://www.propublica.org/article/inside-the-cell-where-a-sick-16-year-old-boy-died-in-border-patrol-care ; companion video analysis: https://www.propublica.org/video/new-video-shows-border-patrol-account-of-childs-death-was-not-true
- **Partner/awards**: Robert Moore and Susan Schmidt (special to ProPublica) with Maryam Jameel; Dec 5, 2019. Follow-up co-published with El Paso Matters (https://www.propublica.org/article/internal-investigation-confirms-border-patrol-failures-leading-up-to-a-16-year-olds-death-on-the-floor-of-his-cell).
- **What they found**:
  - Carlos Gregorio Hernandez Vasquez, 16, of Guatemala, diagnosed with flu and a 103°F fever, was placed in a quarantine cell at the Weslaco, Texas station and died May 20, 2019; a nurse had ordered a 2-hour recheck and ER transfer if he worsened — neither happened.
  - CBP's press release said an agent found him "unresponsive" during a welfare check. The cell video shows his cellmate discovered the body around 6:05 a.m. and alerted agents; video shows Carlos collapsing and vomiting blood around 1:24–1:39 a.m., then lying motionless for over four hours.
  - Border Patrol's "subject activity log" recorded three welfare checks (2:02, 4:09, 5:05 a.m., attributed to a named agent) that the video does not support — the released footage has a conspicuous ~4-hour gap CBP never explained.
  - Autopsy: influenza A (H1N1) complicated by bronchopneumonia and sepsis.
- **Finding type(s)**: `official-account falsification` (a specific public statement by an agency contradicted by primary records of the same event); `custody-harm concealment`; `welfare-check fabrication` (log entries asserting care that surveillance evidence shows did not occur as logged).
- **Evidence & sources**:
  - Cell surveillance video (two segments, 33+ min and 71 min) — obtained under the Texas Public Information Act from the **Weslaco Police Department**, the local agency that investigated the in-custody death, after CBP itself refused to release its records.
  - Police reports, EMS records, detainee logs and the Border Patrol subject activity log — via the same state open-records route.
  - Health records: nurse practitioners' treatment notes; autopsy report by Dr. Norma Jean Farley.
  - Independent expert review — forensic pathologist Judy Melinek and public-health physician Joshua Sharfstein assessed the care timeline.
  - Interviews — family, teacher; CBP given opportunity to respond.
- **Detection signature**: **Parallel-custodian records route + statement/footage diff.** The federal agency controlled the video and stonewalled; the reporters identified a second institution that necessarily held a copy (the local PD that worked the death scene) and used *its* disclosure law. Then they time-aligned video, medical orders, the activity log, and CBP's press release: each pairwise diff (press release vs. video; log vs. video; nurse's orders vs. actions taken) yielded a discrete falsification.
- **Corroboration structure**: layered records triangulation (video ↔ logs ↔ medical orders ↔ autopsy) plus outside expert review of the medical timeline; official response solicited; the family's objection to publishing the video was itself disclosed (https://www.propublica.org/article/carlos-family-objects-to-publication-of-video-detailing-his-death) with an editor's note on the ethics (https://www.propublica.org/article/balancing-the-public-interest-and-a-family-grief).
- **Methodology notes**: acquisition route and reconstruction method stated in the article (video timestamps cross-referenced with police/EMS records; comparison against CBP statements). No separate methods page.
- **Generalization**: deaths/injuries in any custody or institutional setting (jails, ICE detention, group homes, hospitals). Generic detector: (1) enumerate every agency that touched the incident (local PD, EMS, coroner, state licensing) and FOIA the one with the friendliest disclosure law; (2) diff official narrative and internal activity logs against timestamped sensor evidence; (3) treat gaps in released footage as findings to be explained, not absences.
- **Impact**: CBP changed practice to require agents to physically enter cells of sick detainees and take temperatures; acting commissioner John Sanders resigned and later said the government failed Carlos; CBP's internal review, disclosed in the 2022 follow-up, confirmed the failures.

---

### Inside the Secret Border Patrol Facebook Group (2019) — a 9,500-member closed group of agents joking about migrant deaths exposed the agency's internal culture
- **URL**: https://www.propublica.org/article/secret-border-patrol-facebook-group-agents-joke-about-migrant-deaths-post-sexist-memes
- **Partner/awards**: A.C. Thompson, July 1, 2019; ProPublica original (part of the "Inside the Border Patrol" series, https://www.propublica.org/series/inside-the-border-patrol).
- **What they found**:
  - A secret Facebook group, "I'm 10-15" (Border Patrol radio code for "aliens in custody"), had ~9,500 members — current and former agents.
  - Members joked about the deaths of migrants including the 16-year-old Guatemalan who died in custody (the Carlos case above), posted a vulgar faked image targeting Rep. Alexandria Ocasio-Cortez, called visiting Latino lawmakers "scum buckets," and suggested the viral photo of a drowned father and daughter was staged.
  - Group membership included supervisory personnel (e.g., an El Paso supervisor identified).
- **Finding type(s)**: `insider-culture exposure` (a hidden internal forum revealing how an enforcement workforce actually talks about the people it polices); `identity-attributed leak` (leaked content whose news value depends on proving the posters' real-world roles).
- **Evidence & sources**:
  - Screenshots of closed-group posts and comment threads — provided by a source with access to the group (insider leak).
  - Poster-identity verification — ProPublica linked screen names to "apparently legitimate" Facebook profiles of real agents (a supervisor in El Paso; an agent in Eagle Pass) and gave CBP the names of three participants when seeking comment.
  - Independent authentication of referenced imagery — the AP photographer of the drowned father/daughter photo confirmed authenticity against the group's "staged" claim.
- **Detection signature**: **Closed-forum membership attribution.** Leaked screenshots were converted into an institutional finding by joining post authorship to verifiable employee identities (profile artifacts, duty stations, supervisory rank) and forcing the agency to respond to named members — moving the story from "someone posted vile things" to "this workforce, including supervisors, posts vile things."
- **Corroboration structure**: insider screenshots → identity linkage → agency confrontation with specific names → follow-up records reporting: CBP opened an investigation of 70 current/former employees within two weeks (https://www.propublica.org/article/revelations-about-a-secret-facebook-group-spawn-investigation-of-70-current-and-former-border-patrol-employees); a year later ProPublica audited the disciplinary outcome (https://www.propublica.org/article/after-a-year-of-investigation-the-border-patrol-has-little-to-say-about-agents-misogynistic-and-racist-facebook-group); a House committee moved to subpoena discipline records (https://www.propublica.org/article/house-committee-to-subpoena-records-on-discipline-related-to-secret-border-patrol-facebook-group).
- **Methodology notes**: verification steps stated in the article (profile linkage, named-agent confirmation requests). [inferred: the initial access came from a group member acting as whistleblower; the article shields the source.]
- **Generalization**: any closed professional forum (police WhatsApp/Signal groups, doctor forums, trading chats, military Discords). Generic detector: obtain forum content, then attribute — join usernames/avatars/biographical fragments to rosters, LinkedIn, duty stations, court testimony; the attribution join is what makes leaked speech an institutional fact. Follow with an outcome audit at +12 months (what discipline actually happened).
- **Impact**: CBP investigation of 70 employees; congressional subpoena effort; agency leadership circulated pushback deeming the reporting a threat (https://www.propublica.org/article/border-patrol-official-article-reporting-secret-facebook-group), itself newsworthy.

---

### Over 200 Allegations of Abuse of Migrant Children; 1 Case of Homeland Security Disciplining Someone (2019) — DHS's own complaint files showed a 214:1 allegation-to-discipline ratio
- **URL**: https://www.propublica.org/article/over-200-allegations-of-abuse-of-migrant-children-1-case-of-homeland-security-disciplining-someone
- **Partner/awards**: A.C. Thompson, May 31, 2019; built on records pried loose by the ACLU of Arizona and Southern California (litigation partner in the records sense, not co-publication).
- **What they found**:
  - 214 complaints of federal agents abusing or mistreating migrant children (2009–2014) — head strikes with flashlights (one boy needed three staples), punches, Taser use, denial of food and medicine.
  - Exactly one documented disciplinary action arose from those complaints.
  - The records were so heavily redacted that clustering (same agent, same station) could not be measured — a quantified opacity finding: a federal judge ordered names disclosed and the fight went to the 9th Circuit.
- **Finding type(s)**: `accountability vacuum` (a measured, near-total gap between recorded allegations and imposed consequences); `redaction-as-obstruction` (the withholding pattern itself prevents supervision analysis and becomes a finding).
- **Evidence & sources**:
  - ~30,000 pages of internal DHS complaint and investigation records — obtained via ACLU FOIA requests and a follow-on FOIA lawsuit; ProPublica performed the journalistic analysis of the release.
  - Court record of the FOIA litigation — Judge John Tuchi's order compelling disclosure of accused agents' names.
  - Interviews with ACLU attorneys on what the redactions made unmeasurable.
- **Detection signature**: **Allegation-to-consequence ratio join.** Two record streams inside the same agency — the complaint intake stream and the discipline outcome stream — were joined over a fixed period; the ratio (214 allegations : 1 discipline) is itself the finding, requiring no adjudication of any individual complaint.
- **Corroboration structure**: government's own records (primary), quantified; judicial language about the near-nonexistence of completed investigations quoted as independent institutional corroboration; agency response sought.
- **Methodology notes**: record provenance (ACLU FOIA + lawsuit) stated in the article; no separate methods page. [inferred: counting was a manual coding pass over the released complaint files.]
- **Generalization**: police oversight boards, medical boards, prison grievance systems, financial regulators, university Title IX offices — anywhere complaints and outcomes are logged in separable silos. Generic detector: obtain both streams (even redacted), compute the consequence rate, and treat redactions that specifically prevent officer-level clustering as an independent red flag.
- **Impact**: fed congressional scrutiny of CBP child-custody conduct; the litigation forced progressive unsealing of names via the 9th Circuit fight.

---

### Trapped in Gangland / MS-13 on Long Island (2018) — the federal MS-13 crackdown deported informants, ignored missing murdered teens, and labeled innocent students gang members
- **URL**: series https://www.propublica.org/series/ms-13-on-long-island ; "A Betrayal" https://features.propublica.org/ms-13/a-betrayal-ms13-gang-police-fbi-ice-deportation/ ; "The Disappeared" https://features.propublica.org/ms13-miguel/the-disappeared/ ; "He Drew His School Mascot — and ICE Labeled Him a Gang Member" https://features.propublica.org/ms-13-immigrant-students/huntington-school-deportations-ice-honduras/
- **Partner/awards**: Hannah Dreier; co-published with New York magazine, Newsday and The New York Times Magazine. **2019 Pulitzer Prize for Feature Writing** for three stories in the series (https://www.pulitzer.org/winners/hannah-dreier-propublica; https://www.propublica.org/article/pulitzer-winner-ms13-gangs-immigration-zero-tolerance).
- **What they found**:
  - "A Betrayal": a teenage informant ("Henry") who gave Suffolk County police and the FBI task force names of MS-13 killers and 11 youths marked for death was then detained by ICE for deportation — and his supposedly confidential ICE detention memo, containing details from his police interviews, exposed his informant status to jailed MS-13 members, marking him for death.
  - "The Disappeared": 11 Latino high-schoolers vanished in 2016–17 in Suffolk County; police logged them as runaways and told parents to wait at home while several (e.g., Miguel Garcia-Moran, 15) were MS-13 murder victims later found in the woods. Suffolk's missing-minor handbook prescribed a single step — "Search the area" — versus NYPD's multi-step checklist and Nassau County's two-hour state-alert rule.
  - "He Drew His School Mascot": school discipline notes and a gang database misread ordinary teenage artifacts (a mascot drawing, clothing) as gang indicia, feeding ICE detentions and deportation cases against students; Operation Matador arrests of "suspected gang members" ran ~4x prior-year levels.
- **Finding type(s)**: `cooperation betrayal` (state exposes and expels its own informant); `neglected-victim class` (a victim population whose reports are systematically downgraded by the responding agency); `evidence-integrity failure` (official designations — gang labels — resting on trivial or false indicia); `designation cascade` (a weak label in one system triggering severe consequences in another: school note → gang database → ICE detention).
- **Evidence & sources**:
  - Informant paper trail — Henry's written confession pages, his text exchanges with his police handler (Det. Angel Rivera), Facebook messages with gang members, and his cellphone contents, copied and reviewed by the reporter.
  - The ICE detention memo — the custody document proving both his cooperation and the disclosure that endangered him; reviewed by a retired FBI task-force member.
  - Police reports, court records and FOIA responses — thousands of pages, per the article; procedural comparison against NYPD/Nassau written protocols.
  - 100+ interviews — families of the missing, school officials, detectives, prosecutors, gang-intervention experts.
  - Jailhouse access — repeated in-person and phone interviews with the detained teen.
- **Detection signature**: **Designation-evidence audit + protocol diff.** (a) For each government "gang member" designation, pull the underlying evidentiary basis and test it — what document, what indicia, who attested — exposing labels built on drawings and clothing. (b) For the missing teens, diff the agency's written response protocol against neighboring jurisdictions' protocols and against case files showing what was actually done; the one-line handbook against NYPD's checklist turned anecdotes into a structural failure.
- **Corroboration structure**: primary documents (texts, memos, confession pages) anchored every claim about cooperation; officials' own words on the record; cross-jurisdiction procedure comparison; aggregate case count (11 students) assembled family-by-family where police kept no such list.
- **Methodology notes**: reporting method partially narrated in "What It Was Like Reporting on a Teenager Marked for Death by the Gang MS-13" (April 10, 2018 entry on https://www.propublica.org/series/ms-13-on-long-island). [inferred: the 11-case count was reporter-compiled from families since no agency maintained the roster.]
- **Generalization**: any watchlist/designation regime (terror lists, gang databases, sanctions lists, fraud blacklists) and any complaint stream where victims are low-status (missing sex workers, migrant workers' wage theft). Generic detectors: (1) sample designations and audit the underlying evidence quality; (2) compare an agency's written response protocol with peer agencies' and with what case files show happened; (3) build the victim roster yourself when the agency won't.
- **Impact**: ICE said it would stop producing the detailed detention memos that outed informants; Suffolk police opened a review of missing-persons handling (Sept 28, 2018 follow-up); Long Island schools curbed police roles in student referrals (Jan 10, 2019 follow-up); Henry was ultimately deported (Jan 22, 2019) — the accountability arc itself documented.

---

### No Sanctuary: In Pennsylvania, It's Open Season on Undocumented Immigrants (2018) — FOIA'd ICE arrest data showed Philadelphia's office was the national outlier in arresting non-criminals
- **URL**: https://www.propublica.org/article/pennsylvania-ice-undocumented-immigrants-immigration-enforcement
- **Partner/awards**: Deborah Sontag and Dale Russakoff, April 12, 2018; co-published with The Philadelphia Inquirer (series: https://www.propublica.org/series/no-sanctuary).
- **What they found**:
  - In 2017, 64% of the Philadelphia ICE office's "at-large" (community) arrests were of people with **no criminal conviction**, versus 38% nationally — the highest rate in the country, in a state ranked only 16th by undocumented population.
  - "Operation Cross Check," billed as targeting ~70% "criminal aliens," in practice yielded only 35% with conviction records among 248 arrests.
  - Comparator offices inverted the pattern (Los Angeles ~94% and New York ~93% of arrests involved people with criminal convictions).
  - Companion reporting documented state troopers acting as de facto immigration agents via pretextual traffic stops (https://www.propublica.org/article/racial-profiling-ice-immigration-enforcement-pennsylvania).
- **Finding type(s)**: `enforcement-pattern outlier` (one field office deviating sharply from the agency's national practice on a measurable dimension); `mission-label mismatch` (an operation's stated targeting criteria contradicted by its arrest composition); `delegated-enforcement drift` (local/state officers performing federal enforcement without authority or oversight).
- **Evidence & sources**:
  - Unpublished ICE monthly arrest records — obtained via FOIA; the quantitative backbone (at-large arrests by office, criminality flags).
  - Case-file accumulation — 175+ individual immigration arrests examined across three large operations and routine apprehensions.
  - Court filings and affidavits; interviews with arrestees, lawyers, ICE officials.
  - Explicit source-limits statement: no public records akin to police blotters exist in immigration arrests, so the case set had to be hand-assembled.
- **Detection signature**: **Field-office distribution outlier detection.** A single national administrative dataset (ICE arrests with criminal-history flags) was decomposed by field office and arrest type; Philadelphia's non-criminal share (64% vs 38% national) surfaced the story. The stated-mission mismatch (70% target vs 35% actual) is the same test run against the operation's own press language.
- **Corroboration structure**: aggregate FOIA data → 175+ hand-verified cases matching the pattern → named-victim narratives → agency comment. Statistical outlier plus case-level ground truth is the two-layer proof.
- **Methodology notes**: data provenance and the 175-arrest review are stated in the article; no separate methods page. [inferred: criminality shares computed from the FOIA'd monthly ICE spreadsheets.]
- **Generalization**: any federal agency with regional offices (DEA, OSHA, IRS audits, USCIS denials): decompose national row-level data by office and compare rates; where one office is far off baseline, hand-verify cases there. Also generalizes to "stated targeting criteria vs. realized composition" audits of any enforcement sweep.
- **Impact**: Pennsylvania State Police added oversight of trooper-ICE interactions and later formally limited immigration flagging (https://www.propublica.org/article/pennsylvania-police-now-limited-in-flagging-undocumented-immigrants-to-ice); an ACLU suit followed; by 2022, policy changes and payouts to Latino stop victims were documented (https://www.propublica.org/article/changes-in-police-policy-payouts-to-latino-victims-of-traffic-stops-and-arrests-following-investigations).

---

### The Taking (2017) — hand-built database of border-fence condemnation cases proved DHS shortchanged small landowners and skipped legal safeguards
- **URL**: https://features.propublica.org/eminent-domain-and-the-wall/the-taking-texas-government-property-seizure/
- **Partner/awards**: T. Christian Miller (ProPublica) with Kiah Collier and Julián Aguilar (The Texas Tribune); Dec 14, 2017. Methodology published separately: "How We Reported 'The Taking'" (https://www.texastribune.org/2017/12/13/how-we-reported-taking/).
- **What they found**:
  - Across 400+ (416 reviewed) DOJ eminent-domain suits for the 2006-era border fence, landowners **with attorneys** won median settlements ~207% above initial offers ($13,100 → $40,305); unrepresented owners got ~33% ($6,000 → $8,000) — same land, different bargaining power.
  - DHS raised the appraisal-waiver threshold from $10,000 to $50,000, eliminating formal appraisals for ~90% of seized tracts, and waived negotiation and conflict-of-interest safeguards.
  - Concrete errors: paid twice for the same water rights; built fence on levee land it hadn't paid for; paid $20,500 to Roberto Pedraza for land he did not own; some ownership disputes took nearly a decade.
- **Finding type(s)**: `asymmetric-bargaining extraction` (the state systematically paying less to counterparties least able to negotiate); `procedural-safeguard evasion` (thresholds and waivers used to bypass protections designed for exactly this transaction class); `transactional error ledger` (accumulated concrete mistakes proving administrative recklessness).
- **Evidence & sources**:
  - PACER condemnation dockets — 416 cases reviewed; 197 Rio Grande Valley cases hand-entered into a structured database built on top of an earlier NPR dataset (stated in methodology page).
  - FOIA-obtained DOJ records on the land program.
  - 1,104 internal DHS emails — obtained from UT Austin law professor Denise Gilman (who had extracted them for clinic research), showing internal handling of safeguards.
  - Land/appraisal records and extensive landowner interviews along the Rio Grande.
  - Statistical test — Welch two-sample t-test on represented vs. unrepresented settlement deltas, p < 2e-16 (stated).
- **Detection signature**: **Counterparty-stratified settlement delta.** Build a case-level table of government takings (offer, settlement, tract, representation status), stratify outcomes by a counterparty attribute (had a lawyer / didn't), and test the difference. The disparity — not any single case — is the abuse. Secondary signature: **safeguard-waiver tracing** — follow the internal paper trail (emails) showing protections were deliberately switched off.
- **Corroboration structure**: docket-derived statistics + internal emails explaining the mechanism + named-landowner ground truth (Pedraza, levee cases) + formal statistical significance; methodology transparently published.
- **Methodology notes**: dedicated methods article (Texas Tribune link above): database built on NPR's earlier public dataset, hand-entry from PACER, outcome coding. Stated, not inferred.
- **Generalization**: any mass state-vs-individual transaction corpus — plea bargains, tax settlements, disaster buyouts, insurance condemnations. Generic detector: case-level outcomes joined to counterparty-resource proxies; plus FOIA the agency's internal guidance for waiver/threshold changes that quietly strip protections.
- **Impact**: became the evidentiary baseline for 2019 congressional scrutiny of wall land seizures (cited in House Homeland Security materials, e.g. https://democrats-homeland.house.gov/imo/media/doc/BSFO_Vela_Cash%20In%20Hand%20FINAL.pdf) and framed coverage of the 2019 wall push (https://www.propublica.org/article/if-trumps-border-wall-becomes-reality-heres-how-he-could-easily-get-private-land-for-it).

---

### How a Local Bureaucrat Made Millions Amid the Rush to Build a Border Fence (2017) — a 1.5% per-dollar commission and family subcontracts turned a county fence program into personal enrichment
- **URL**: https://features.propublica.org/eminent-domain-and-the-wall/eminent-domain-border-wall-godfrey-garza-hidalgo-texas/
- **Partner/awards**: T. Christian Miller (ProPublica), Kiah Collier and Julián Aguilar (The Texas Tribune); Dec 29, 2017; The Taking series.
- **What they found**:
  - Godfrey Garza Jr., manager of Hidalgo County Drainage District No. 1, negotiated a 1.5%-of-construction-cost fee and collected at least **$3.5 million** (2008–2012) on a $232M levee-fence project ($174.4M federal, $58M county) — claiming the commission applied to federal dollars too, against the county's understanding.
  - Valley Data Collection Specialists — owned first by Garza's sons, then his wife Annie — took $1M+ (reported up to $1.6M) in subcontracts from project contractors including Dannenbaum Engineering; Garza's own firm Integ Inc. floated Valley Data an interest-free $100,000 loan.
  - Records relevant to the arrangement were destroyed, complicating reconstruction.
- **Finding type(s)**: `self-dealing intermediary` (the official who administers a program routes program money to entities he or his family controls); `percentage-fee inflation` (compensation indexed to project cost creates an incentive to grow the project and a hidden multiplier on federal funds).
- **Evidence & sources**:
  - County contracts, invoices, check registers and bond documents — from the county's own 2014 internal investigation; check registers had been handed to the FBI.
  - Sworn depositions and previously unreleased court files from the county's civil litigation.
  - Private investigative report by attorney Michael Lee (county-commissioned).
  - FBI and DHS emails; public records.
- **Detection signature**: **Commission-flow tracing.** Join the fee formula in the management contract to actual disbursement ledgers (check registers) to compute realized compensation; then join the project's subcontractor list to corporate-ownership records to surface family-owned vendors. Contract-term × ledger × ownership-registry is the three-way join.
- **Corroboration structure**: litigation record (depositions under oath) + accounting records + procurement records + response from Garza; disclosure that records were destroyed treated as a finding.
- **Methodology notes**: acquisition described in-story ("previously unreleased court files, sworn depositions, emails and public records"); no separate methods page. [inferred: dollar totals reconstructed by summing ledger entries against the 1.5% formula.]
- **Generalization**: program managers paid by percentage anywhere (bond programs, construction management, disaster contracts). Generic detector: flag percent-of-cost compensation clauses in public contracts; cross-reference vendor lists against officials' family names/addresses in corporate registries; treat destroyed-records notations in audits as high-priority leads.
- **Impact**: Hidalgo County sued Garza; a judge found the fraud evidence too weak for a jury and the initial suit collapsed (https://www.propublica.org/article/hidalgo-county-texas-lawsuit-fraud-border-wall-godfrey-garza; https://www.texastribune.org/2018/02/09/south-texas-judge-dismisses-fraud-lawsuit-over-border-fence-project/); the county re-sued Garza and Dannenbaum in Nov 2018 (https://www.texastribune.org/2018/11/21/hidalgo-county-sues-former-employee-dannenbaum-engineering/); FBI raided Dannenbaum offices in April 2018; DHS withheld a final $2.9M payment.

---

### Billions on the Border / Operation Lone Star (2022) — repeated pulls of Texas DPS arrest data showed the state padding its border-security metrics
- **URL**: https://www.propublica.org/article/texas-governor-brags-about-his-border-initiative-the-data-doesnt-back-him-up ; fact-check companion: https://www.propublica.org/article/texas-greg-abbott-border-crisis-facts
- **Partner/awards**: Lomi Kriel, Perla Trevizo (ProPublica), Andrew Rodriguez Calderón (The Marshall Project), Keri Blakinger; March 21, 2022; tri-way co-publication ProPublica + The Marshall Project + The Texas Tribune (series: https://www.propublica.org/series/billions-on-the-border; Jolie McCullough's trespassing analysis: https://www.propublica.org/article/texas-border-operation-is-meant-to-deter-cartels-and-smugglers-more-often-it-imprisons-lone-men-for-trespassing).
- **What they found**:
  - Gov. Abbott credited Operation Lone Star with 887 pounds of fentanyl seized; only ~160 pounds came from the operation's own reported regions (March 2021–Jan 2022) — the rest was statewide activity rebranded.
  - After reporters' questions, DPS retroactively **removed more than 2,000 charges** (cockfighting, sexual assault, stalking, etc.) from OLS metrics as unrelated to the border mission; arrests up to 250+ miles from the border (e.g., a Midland family-violence case) had been counted.
  - ~40% of OLS arrests in the sampled window were misdemeanor trespassing of lone migrant men — not smuggling or cartel activity — while state border spending grew from $110M (2008–09) to ~$3B (2022–23) per the series description.
- **Finding type(s)**: `metric inflation` (an agency padding the row-level composition of a headline statistic to justify a program); `retroactive data laundering` (quiet post-hoc edits to reported data after scrutiny — detectable only with archived snapshots); `budget-outcome mismatch` (spending ledger growth vs. outcome data that doesn't correspond).
- **Evidence & sources**:
  - Texas DPS arrest databases — multiple sequential snapshots (July 2021–Jan 2022) obtained via records requests; the diff between pulls is itself evidence.
  - Criminal court records and arrest reports — per-case verification of border-relatedness (and the trespassing docket work in county courts).
  - State budget/appropriations ledgers — the $110M→$3B trajectory.
  - Governor's press releases and legislative hearing transcripts — the claims under test.
  - Expert interviews, including former DPS commanders, on whether counting rules matched the mission.
- **Detection signature**: **Metric snapshot diffing + eligibility re-scoring.** Obtain the row-level data behind a headline metric repeatedly over time; (1) diff snapshots to catch retroactive additions/removals, and (2) re-score each row against the program's own stated eligibility criteria (geography, charge type, time window). Rows failing the program's own definition quantify the inflation.
- **Corroboration structure**: state's own data vs. state's own claims (internal contradiction is the strongest frame); per-case court-record verification; expert validation of counting standards; DPS's own retroactive removals functioned as an admission.
- **Methodology notes**: method (sequential data snapshots, geographic cross-referencing, case-file checks) stated across the articles; the April 2022 "Reality Check" piece functions as a findings-methods recap. No standalone methods page found on propublica.org [inferred: the Marshall Project co-published version carries the fuller data annex].
- **Generalization**: any politically branded enforcement surge (drug task forces, anti-gang initiatives, "crime crackdowns" — cf. ProPublica's 2026 Memphis task-force analysis where only 2% of 800+ arrests were for violent crimes: https://www.propublica.org/article/memphis-safe-task-force-immigration-arrests-crime-data). Generic detector: archive every data release; diff over time; re-score rows against the program's press-released definition of success.
- **Impact**: DPS purged 2,000+ charges from its OLS metrics; DOJ opened a civil-rights investigation of Operation Lone Star (https://www.propublica.org/article/operation-lone-star-doj-investigation-abbott).

---

### Deported and Imprisoned: The Venezuelans Trump Sent to CECOT (2025) — the government's own data showed most of the 238 men branded "criminals" had no U.S. convictions
- **URL**: https://www.propublica.org/article/trump-el-salvador-deportees-criminal-convictions-cecot-venezuela ; case-by-case interactive: https://projects.propublica.org/venezuelan-immigrants-trump-deported-cecot/
- **Partner/awards**: Mica Rosenberg, Perla Trevizo, Melissa Sanchez, Gabriel Sandoval (ProPublica) with Ronna Rísquez (Alianza Rebelde Investiga) and Adrián González (Cazadores de Fake News); co-published with The Texas Tribune; May 30, 2025 (data story) and July 23, 2025 (roster project) (series: https://www.propublica.org/series/deported-and-imprisoned).
- **What they found**:
  - Internal DHS data on the 238 Venezuelan men flown to El Salvador's CECOT prison on March 15, 2025 showed **only 32 had U.S. criminal convictions**, just 6 for violent offenses; 130 (over half) had no convictions or pending charges — immigration violations only; 67 had mostly nonviolent pending charges.
  - The reporters' independent multi-country review found arrests/convictions abroad for only 20 of 238 (11 violent) — refuting the public "worst of the worst"/"terrorists" framing.
  - 1,400-name Venezuelan law-enforcement and Interpol Tren de Aragua lists produced **zero matches** to the deportees.
  - Individual ground truth: e.g., Leonardo José Colmenares Solórzano, 31, a youth soccer coach with no criminal history anywhere, apparently selected partly for tattoos.
  - The interactive presents "a first-of-its-kind, case-by-case accounting" of all 238 men — a roster the government refused to publish.
- **Finding type(s)**: `collective-label falsification` (a mass action justified by a group characterization that per-person records disprove); `government-knowledge finding` (the internal data proves the administration knew the label was false when acting); `shadow roster construction` (journalists assembling the definitive list of affected people that the state withholds).
- **Evidence & sources**:
  - Internal DHS/administration data on the deportees — obtained through reporting (provenance protected), containing conviction/charge flags per man.
  - U.S. and South American court and police records — pulled case-by-case across relevant countries, per the stated methodology.
  - Venezuelan law enforcement + Interpol gang lists (1,400 names) — negative-match test.
  - Interviews with relatives of 100+ of the men, and attorneys.
  - Federal immigration-court (EOIR) data; social-media and tattoo analysis for the government's claimed indicia.
- **Detection signature**: **Roster-wise multi-jurisdiction ground-truth verification.** Reconstruct the full roster of a collective government action; for every person, query criminal-record systems in every relevant jurisdiction plus the specific watchlists invoked by the government; then compare the verified distribution (32/238 convictions; 0/1,400 list matches) against the government's public characterization and its internal data. The per-unit exhaustiveness is what converts anecdote into refutation.
- **Corroboration structure**: three independent layers — (1) the government's internal data, (2) journalist-verified public records across countries, (3) family/attorney testimony — all converging; partner organizations with Venezuelan records expertise (ARI, Cazadores de Fake News) supplied in-country verification capacity; the government's refusal to answer documented.
- **Methodology notes**: stated in the project and data story (internal data + thousands of pages of court records + 100+ family interviews + list checks). The exact acquisition channel for the internal data is deliberately unstated (source protection).
- **Generalization**: any mass action justified by a collective label — sanctions designations, terrorism lists, mass firings "for cause", gang injunctions, no-fly lists. Generic detector: get or build the roster; verify the labeling attribute per person against the systems that would record it; report the distribution and the gap between internal knowledge and public claims. Foreign-partner newsrooms are the key to multi-jurisdiction record access.
- **Impact**: reporting stood when the men were released to Venezuela in a July 2025 swap and testimony of abuse emerged (https://www.propublica.org/article/venezuelan-men-cecot-interviews-trump); the series became the reference accounting for litigation and congressional scrutiny of the removals.

---

### Trump Has Detained the Parents of More Than 11,000 U.S. Citizen Kids (2026) — record linkage across ICE arrest and deportation datasets quantified family separation the government doesn't count
- **URL**: https://www.propublica.org/article/trump-family-deportations-ice-citizen-kids
- **Partner/awards**: Jeff Ernsthausen, Mario Ariza, McKenzie Funk, Mica Rosenberg, Gabriel Sandoval; March 23, 2026; ProPublica original (companion: https://www.propublica.org/article/american-kids-detained-trump-immigration-deportation-democrats-investigation).
- **What they found**:
  - In the administration's first seven months, ICE arrested and detained parents of at least **11,000 U.S.-citizen children** — over 50 kids affected per day; pace projected to roughly double over a full year.
  - Mothers of U.S.-citizen kids were deported at ~4x the Biden-era rate (~60% of maternal arrests ended in deportation vs ~30%).
  - The rewritten "Detained Parents Directive" dropped the word "humane" from its preamble — a policy-text diff matching the measured shift.
  - Named cases (Doris Flores family; "Griselda") grounded the statistics.
- **Finding type(s)**: `collateral-harm quantification` (measuring a harm category the agency itself does not track or publish — citizen children of detainees); `administration-rate comparison` (same metric computed identically across administrations to isolate policy effect); `policy-text drift` (meaningful edits between versions of a directive).
- **Evidence & sources**:
  - ICE Form I-213 arrest narratives — obtained by the University of Washington Center for Human Rights through an ongoing public-records lawsuit (late 2021–mid-Aug 2025); I-213s record parenthood/family details.
  - ICE deportation/detention databases via the Deportation Data Project (FOIA-based academic repository; late 2023–mid-Oct 2025).
  - The two versions of the Detained Parents Directive; police records, court documents, flight manifests for case studies.
- **Detection signature**: **Cross-dataset identity matching for uncounted harm.** No single dataset says "parent of citizen child detained," so the team matched ~85% of I-213 arrest records to deportation-database records on composite keys (arrest date, gender, age, nationality, location, arrest method), validated on three held-out fields (marital status, disposition, entry date) at 98% consistency, then counted parents — using paternal-only counts where needed to avoid double-counting couples. The join manufactures the statistic the government won't produce.
- **Corroboration structure**: quantitative core (matched records with stated match-rate and validation) + like-for-like temporal comparison (Jan–Aug 2024 vs 2025) + policy-document diff + named-family case verification (police records, flight manifests) + agency response sought.
- **Methodology notes**: matching methodology, validation fields, consistency rate and double-count guard stated in the article — unusually explicit record-linkage disclosure. Stated, not inferred.
- **Generalization**: any "uncounted collateral" question — children of incarcerated parents, evictions affecting schoolchildren, deaths after benefit terminations. Generic detector: find two administrative datasets that each hold half the fact; design a composite-key match with held-out-field validation; publish match rate and error bounds. Academic FOIA repositories (Deportation Data Project, UWCHR) are force multipliers.
- **Impact**: cited in congressional Democrats' investigation demands on citizen-child detentions (companion piece above); Brookings-derived estimates later extended the count (https://www.propublica.org/article/trump-immigration-child-parent-separation-estimates-brookings).

---

### We Found More Than 40 Cases of Immigration Agents Using Banned Chokeholds (2026) — a coded corpus of bystander video proved systematic use of prohibited neck restraints with zero visible discipline
- **URL**: https://www.propublica.org/article/videos-ice-dhs-immigration-agents-using-chokeholds-citizens
- **Partner/awards**: Nicole Foy, McKenzie Funk (with Mariam Elba, Joanna Shan, Haley Clark, Cengiz Yar); January 13, 2026; ProPublica original.
- **What they found**:
  - 40+ verified incidents in roughly a year of immigration agents using chokeholds/carotid restraints — banned by DHS's 2023 use-of-force policy except when deadly force is authorized.
  - Victims included U.S. citizens: Arnoldo Bazan, 16 (Houston), hospitalized in a trauma unit after a chokehold; Carlos Sebastian Zapata Rivera (Massachusetts), carotid restraint inducing an apparent seizure with his 1-year-old in his lap; Luis Hipolito (Los Angeles), convulsions after being slammed into a chokehold.
  - DHS provided no evidence any agent was disciplined — the accountability null result is a core finding.
- **Finding type(s)**: `policy-violation accumulation` (individually deniable incidents aggregated into an undeniable count against the agency's own written rule); `accountability vacuum` (see entry 4 — recurring tag: violations documented, discipline absent).
- **Evidence & sources**:
  - Bystander/social video corpus — collected from English- and Spanish-language social platforms (TikTok, Instagram), local news footage, court records, and professional photography (Ryan Murphy's Border Patrol coverage).
  - DHS 2023 use-of-force policy — the written standard each clip was scored against.
  - Expert panel — eight former law-enforcement officials/scholars (incl. FLETC instructor Marc Brown, former CBP commissioner Gil Kerlikowske, former Baltimore deputy commissioner Danny Murphy, prof. Seth Stoughton) independently reviewed footage.
  - Background verification — criminal-record searches on every featured individual (research reporter Mariam Elba) to pre-empt "dangerous criminal" rebuttals; all videos sent to White House/DHS/ICE/CBP for response.
- **Detection signature**: **Video-corpus policy coding.** Systematically harvest a distributed video record of agent-civilian encounters, then code each incident against the agency's own written use-of-force rule with an independent expert panel; count only clips clearing the verification bar. The move is accumulation + rule-referenced coding: no single video is the story; the coded corpus is.
- **Corroboration structure**: multi-channel video sourcing → per-incident identity and criminal-record verification → expert-panel consensus scoring against the written policy → agency confrontation with the full evidence set → medical records/named victims for anchor cases.
- **Methodology notes**: collection channels, expert panel composition, policy standard, and verification steps stated in the article. Stated, not inferred.
- **Generalization**: any policed public interaction where bystander video accumulates (protest policing, school resource officers, bailiffs, private security). Generic detector: define the written rule; build a harvest pipeline over social video with language coverage matching the affected community; code incidents with practitioner-credible external reviewers; publish the count and the discipline count side by side. (ProPublica ran the same architecture on tear gas/pepper spray against children: https://www.propublica.org/article/kids-tear-gas-trump-immigration-crackdown, drawing congressional reform demands: https://www.propublica.org/article/lawmakers-demand-reforms-tear-gas-children.)
- **Impact**: footage set sent to DHS leadership on the record; fed 2026 congressional demands for use-of-force reform; no disciplinary response documented at publication — itself reported.

---

### These Immigrant Kids Were Once Protected. Under Trump, Their Deportations Have Tripled (2026) — EOIR and ICE data showed removal of unaccompanied minors at 3x first-term rates after protections were dismantled
- **URL**: https://www.propublica.org/article/unaccompanied-minors-deportations-elder-chavez
- **Partner/awards**: Mica Rosenberg, Jeff Ernsthausen (with Perla Trevizo, Amy Yurkanin, Gabriel Sandoval); July 6, 2026; ProPublica original.
- **What they found**:
  - Unaccompanied minors are being detained and removed at ~3x the rate of Trump's first term; immigration courts issued 10,000+ removal/voluntary-departure orders per month — nearly 4x the prior rate.
  - The vast majority removed had no criminal history.
  - Mechanism documented: elimination of funded legal counsel for minors, revocation of "deferred action" for Special Immigrant Juvenile Status (SIJ) recipients, defunding of legal-service groups, and firing of 100+ immigration judges — with court-ordered restorations incompletely implemented.
  - Anchor case: Elder Chavez, 18, SIJ holder detained after a speeding stop despite lawful status, school enrollment and no record.
- **Finding type(s)**: `protection-rollback effect` (a measurable outcome shift following the removal of specific procedural protections — dose-response between policy change and administrative data); `vulnerable-cohort rate shift` (tracking one legally distinct cohort — unaccompanied minors — through enforcement systems over time).
- **Evidence & sources**:
  - ICE detention records — obtained via FOIA, covering Oct 2018–Dec 2025 (longitudinal).
  - EOIR immigration-court data — the census's flagged evidence class: case-level records of the administrative court system that sits **outside PACER**, with removal and voluntary-departure orders by month.
  - External expert validation — UCLA Law researchers and TRAC (Transactional Records Access Clearinghouse) reviewed the analysis.
  - Policy documents on SIJ deferred action and counsel funding; case reporting (Chavez).
- **Detection signature**: **Administrative cohort rate comparison with interior-enforcement isolation.** Minors were identified by birthdate within the datasets; border apprehensions were excluded to isolate interior enforcement; removal rates were then compared across equivalent windows of two administrations. The cohort filter + venue filter + cross-administration normalization is what turns raw dockets into a causal-shaped claim.
- **Corroboration structure**: two independent longitudinal datasets (ICE custody; EOIR dockets) trending together + third-party expert replication/validation + policy-change chronology aligned to the inflection + individual case verification.
- **Methodology notes**: cohort identification (birthdate), exclusion rules, and expert validation stated in the article. Stated, not inferred.
- **Generalization**: whenever a legal protection is repealed, the before/after can be measured in the administrative court or benefits data of the affected cohort (e.g., tenant outcomes after right-to-counsel cuts; claim denials after appeals-process changes). Generic detector: define the protected cohort in the data by an intrinsic attribute (age, status code), isolate the enforcement channel the policy touched, compare identical windows across regimes, and have outside experts re-run it. Related ProPublica infrastructure: the habeas-petition tracker built from 18,000+ federal filings (https://projects.propublica.org/habeas-tracker/; https://www.propublica.org/article/habeas-petitions-immigrant-detentions-trump).
- **Impact**: published amid litigation over restored minor protections; contributed to oversight scrutiny of EOIR judge firings (documented in-story).

---

## Cluster Synthesis

### 1. Recurring evidence-source types (frequency across the 12 entries)
| Evidence class | Count | Entries |
|---|---|---|
| FOIA / state open-records / records litigation (incl. academic FOIA repositories: UWCHR, Deportation Data Project, TRAC) | 8 | Carlos video (TX PIA via local PD), 200-allegations (ACLU FOIA suit), No Sanctuary (ICE monthly data), The Taking (DOJ records, DHS emails), OLS (DPS data requests), 11,000 kids (records lawsuit + DDP), EOIR minors (ICE FOIA), MS-13 (FOI requests) |
| Leaked/insider material (audio, screenshots, internal data, custody memos) | 5 | Audio, Facebook group, CECOT internal DHS data, MS-13 (ICE detention memo), Zero Tolerance shelters strand (Heartland internal docs: https://www.propublica.org/article/chicago-immigrant-shelters-heartland-internal-documents) |
| Court records at scale (PACER, county criminal dockets, EOIR, foreign courts) | 6 | The Taking (416 dockets), Garza (depositions), OLS (trespass dockets), CECOT (US + South American records), EOIR minors, MS-13 |
| Government's own row-level enforcement data (arrests, detentions, metrics) | 6 | No Sanctuary, OLS, CECOT, 11,000 kids, EOIR minors, Memphis (census-noted sibling: https://www.propublica.org/article/memphis-safe-task-force-immigration-arrests-crime-data) |
| Video evidence (institutional CCTV or bystander corpora) | 3 | Carlos, Chokeholds, tear-gas sibling investigation |
| Mass family/affected-person interviews (roster-scale, 100+) | 3 | CECOT (100+ families), MS-13 (100+ interviews), The Taking (landowners) |
| Parallel-custodian records (local PD / county / foreign agency holding the federal story's evidence) | 4 | Carlos (Weslaco PD), Garza (county files), CECOT (foreign records), MS-13 (Suffolk PD) |
| Internal policy/directive texts used as scoring standards or diffed across versions | 4 | Chokeholds (2023 UOF policy), 11,000 kids (Detained Parents Directive diff), EOIR minors (SIJ/counsel policies), The Taking (waiver thresholds) |

Additional census-observed instances not given full entries: institution-level police-report/call-log accumulation across immigrant-youth shelters (https://www.propublica.org/article/boystown-immigrant-childrens-shelter-sexual-assault), internal-document + child-by-child tracking of the 99 separated kids sent to Chicago (https://www.propublica.org/article/trump-zero-tolerance-separated-immigrant-children-chicago), and the 18,000-case habeas docket scrape (https://projects.propublica.org/habeas-tracker/).

### 2. Recurring detection signatures (my tags; frequency)
| Signature | Count | Where |
|---|---|---|
| Official-claim vs. primary-record diff (statement/log/metric contradicted by video, data, or internal docs) | 6 | Carlos, OLS, CECOT, Facebook (photo-staging claim debunk), No Sanctuary (Cross Check), EOIR minors (rollback vs. court orders) |
| Two-stream join / ratio construction (complaints↔discipline, arrests↔convictions, arrests↔parenthood) | 4 | 200-allegations, 11,000 kids, No Sanctuary, Memphis-style arrest composition |
| Distribution outlier / stratified-delta detection (by office, by representation status, by geography) | 3 | No Sanctuary, The Taking, OLS geography |
| Corpus accumulation + rule-referenced coding (many small incidents scored against a written standard) | 3 | Chokeholds, MS-13 designation audit, shelters police-records strand |
| Roster reconstruction + per-unit verification | 2 | CECOT (238 men), Zero Tolerance Chicago (99 children) |
| Parallel-custodian records route | 3 | Carlos, Garza, CECOT (foreign jurisdictions) |
| Snapshot diffing of official data over time | 1 strong + habitual | OLS (DPS pulls); generalized longitudinal practice in 11,000-kids/EOIR work |
| Money-flow tracing through contract terms × ledgers × ownership registries | 1 | Garza |
| Embedded-verifier leak authentication | 1 | Audio |
| Protocol diff across peer jurisdictions | 1 | The Disappeared |

### 3. Transferable pattern candidates

**P1 — Parallel-Custodian Records Route.**
When the target agency controls the primary evidence and stonewalls, map every other institution that necessarily touched the event — the local police who investigated the death, the county district that banked the invoices, the foreign court that tried the deportee, the university clinic that already FOIA'd the emails — and extract the same evidence through the custodian with the weakest secrecy shield (state public-information act, civil discovery, foreign public records, academic repositories). Minimum data: an incident/transaction map listing all touching institutions and each one's disclosure regime. Recognition cue in any domain: a refusal or non-answer from the obvious custodian while the event demonstrably involved second parties (EMS, auditors, insurers, co-regulators, counterparties) who keep their own copies.

**P2 — Denominator Audit (Metric Inflation Check with Snapshot Diffing).**
Take a program's headline success metric, obtain the row-level records behind it repeatedly over time, and (a) re-score every row against the program's own published definition of eligibility (geography, offense type, time window, mission), (b) diff successive snapshots to catch retroactive edits made under scrutiny. The share of ineligible rows and the edit log are the findings. Minimum data: two or more timestamped row-level extracts plus the program's stated scope. Recognition cue: any initiative defended primarily by aggregate counts (arrests, seizures, jobs created, fraud prevented) whose row-level basis is not routinely published.

**P3 — Allegation-to-Consequence Ratio.**
Join an institution's complaint/violation intake stream to its discipline/outcome stream over a fixed window and publish the ratio; where redactions prevent per-officer clustering, report that as an obstruction finding. Works even when every individual complaint is contested, because the ratio (214:1; 40+ violations : 0 discipline) indicts the system, not any case. Minimum data: both streams at any granularity, even redacted. Recognition cue: oversight bodies that publicize intake volumes but never outcome volumes — regulators, inspectors general, HR misconduct offices, licensing boards.

**P4 — Roster-wise Ground-Truth Verification of a Collective Label.**
When a state acts against a group under a collective characterization ("criminals," "gang members," "fraudsters"), reconstruct the complete roster of affected individuals (leaked lists, manifests, family networks, litigation records), then verify the labeling attribute person-by-person in every record system that would show it — including the specific watchlists the government invokes — and report the verified distribution against both the public claim and any internal data showing what officials knew. Minimum data: the roster; per-person access to conviction/charge/watchlist systems in all relevant jurisdictions (foreign-partner organizations are the key enabler). Recognition cue: mass actions announced with group labels but no released list of names — the withheld roster is the tell.

**P5 — Counterparty-Stratified Outcome Delta.**
In any mass of similar state-vs-individual transactions (condemnation settlements, plea deals, fines, benefit awards), build a case-level table and stratify outcomes by a counterparty-resource attribute — represented vs. unrepresented, connected vs. not, English-speaking vs. not — and test the difference statistically. A large stratified delta shows the state exploiting bargaining asymmetry as policy, independent of any single unfair case. Minimum data: case-level offer/outcome pairs plus one counterparty attribute; a docket system (PACER/EOIR/state courts) usually suffices, hand-entry accepted. Recognition cue: high-volume, low-visibility transaction classes where the state is a repeat player and individuals appear once.

Cross-cutting note for detector design: in at least 8 of 12 entries the decisive artifact was the government's own record (its data, its logs, its policy text, its internal emails) turned against its public statements — the core lesson of this cluster is that self-contradiction detection over official record systems outperforms external testimony in both provability and impact.
