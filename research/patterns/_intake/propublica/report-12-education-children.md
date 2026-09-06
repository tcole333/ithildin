# ProPublica Evidence Ontology — Cluster 12: Education, Children & Family Services

Reviewed 2026-07-29 from the live series pages (propublica.org/series/<slug>) and topic page (propublica.org/topics/education), plus per-story and methodology pages. 13 stories/series covered. All are ProPublica originals or formal co-publications; partners named per story. Finding-type and detection-signature tags are free-form, defined on first use.

Series pages consulted: [illinois-school-seclusions-timeouts-restraints](https://www.propublica.org/series/illinois-school-seclusions-timeouts-restraints), [the-price-kids-pay](https://www.propublica.org/series/the-price-kids-pay), [stuck-kids](https://www.propublica.org/series/stuck-kids), [overpolicing-parents](https://www.propublica.org/series/overpolicing-parents), [level-14](https://www.propublica.org/series/level-14), [the-unbefriended](https://www.propublica.org/series/the-unbefriended), [unfit-to-teach](https://www.propublica.org/series/unfit-to-teach), [state-of-disrepair](https://www.propublica.org/series/state-of-disrepair), [unequal-discipline](https://www.propublica.org/series/unequal-discipline), [crackdown-on-student-threats](https://www.propublica.org/series/crackdown-on-student-threats), [the-right-to-read](https://www.propublica.org/series/the-right-to-read).

---

### The Quiet Rooms (2019) — Illinois schools locked children in seclusion rooms tens of thousands of times, often illegally
- **URL**: https://features.propublica.org/illinois-seclusion-rooms/school-students-put-in-isolated-timeouts/ (series: https://www.propublica.org/series/illinois-school-seclusions-timeouts-restraints)
- **Partner/awards**: ProPublica Illinois + Chicago Tribune (Jennifer Smith Richards, Jodi S. Cohen, Lakeidra Chavis). Won the [Shadid Award for Journalism Ethics](https://www.propublica.org/atpropublica/propublica-illinois-and-chicago-tribune-series-the-quiet-rooms-wins-shadid-award-for-journalism-ethics) and the [Hechinger Grand Prize for Distinguished Education Reporting](https://www.propublica.org/atpropublica/the-quiet-rooms-wins-national-award-for-education-reporting).
- **What they found**:
  - ~20,000 seclusion incidents documented across 100+ Illinois districts in a 15-month window (2017-18 school year through early Dec 2018), from ~50,000 pages of records; children as young as 5.
  - Of ~12,000 incidents detailed enough to determine the trigger, more than a third had **no documented safety reason** — the sole legal justification under Illinois law; nearly 6,000 were for disruption/disrespect only (spilled milk, refusing classwork, throwing Legos).
  - Concentration in special-ed co-ops: Bridges Learning Center (Kaskaskia) logged 1,288 seclusions for ~65 students in 15 months; Special Education District of Lake County (Gages Lake) ~1,200; The Center, East Moline ~850.
  - Staff-written logs recorded children begging: "Please, please, please open the door. Please, I'll be good."
- **Finding type(s)**:
  - `statutory-violation-at-scale` — individual records aggregated to show an institution routinely breaching an explicit legal standard (not one bad incident, but a base-rate of illegality).
  - `undercount-exposure` — official statistics (federal Civil Rights Data Collection) contradicted by ground-level records the reporters collected themselves.
  - `documented-cruelty-in-official-records` — the harm is described in the institution's own contemporaneous paperwork, in staff's own words.
- **Evidence & sources**:
  - FOIA'd incident paperwork — narrative reports on isolated timeout and physical restraint, timeout logs, staff training documentation, parent notifications, from a mass request to every Illinois district (~200 responded; 100+ produced records; 9 refused). Obtained via 300+ public records requests.
  - Hand-built incident database — reporters keyed each incident: location, date, duration, documented reason, staff names, parent notification, demographics.
  - Federal CRDC self-reported seclusion counts (2015-16) — public download, used as the foil.
  - Civil lawsuits, state/federal special-education complaints, police reports, injury reports, school handbooks — public filings and FOIA.
  - 120+ interviews (parents, children, staff, experts); site visits to 3 districts (20+ asked); 20 follow-up FOIAs for floor plans/dimensions/photos of the rooms; children's drawings of the rooms collected with parental consent.
- **Detection signature**: **Standard-vs-log audit** — every incident narrative was coded against the single statutory trigger (safety threat) and its timing; incidents where no safety issue was documented, or where it arose only *after* confinement began, were counted as outside the law. Secondary: **zero-claim audit** — 75 randomly chosen districts that reported *zero* seclusions to the federal CRDC were FOIA'd for incident records since 2015, proving the federal numbers "don't add up."
- **Corroboration structure**: Layered — records first, then a 631-record/53-district spot-check by a separate team on 14 critical fields; conservative inclusion rules (voluntary calm-down visits excluded); physical verification of rooms; parent and staff interviews matched to specific logged incidents; districts given pre-publication response.
- **Methodology notes**: Dedicated page, ["How We Reported This Story"](https://www.propublica.org/article/illinois-school-students-seclusion-rooms-methodology): requested "all narrative reports on isolated timeout and physical restraint incidents, logs of isolated timeout use, staff training documentation and parent notifications"; "Illinois law allows seclusion only when students pose a safety threat"; coding captured "whether it occurred before or after the start of the isolated timeout."
- **Official impact**: Illinois issued an emergency ban on isolated timeout the day after publication (Nov 20, 2019); permanent restrictions on seclusion and face-down restraint followed in 2021; a staffer was criminally charged; a federal ban was introduced in Congress ([series page](https://www.propublica.org/series/illinois-school-seclusions-timeouts-restraints)).
- **Generalization**: Works anywhere a coercive practice is legal only under a narrow trigger condition but self-documented by the institution: police use-of-force reports, prison segregation logs, nursing-home chemical-restraint charts, involuntary psychiatric holds. Generic detector: acquire the incident-level paperwork, extract the "justification" field, diff against the statutory trigger; separately, sample entities self-reporting zero to a central collector and demand their raw logs.

---

### The Price Kids Pay (2022) — Illinois schools evaded a state ban on fining students by having police ticket them for misbehavior
- **URL**: https://www.propublica.org/article/illinois-school-police-tickets-fines (series: https://www.propublica.org/series/the-price-kids-pay; interactive: https://projects.propublica.org/illinois-school-police-tickets-fines/)
- **Partner/awards**: ProPublica + Chicago Tribune (Jodi S. Cohen, Jennifer Smith Richards). Won the [Worth Bingham Prize](https://nieman.harvard.edu/propublica-and-the-chicago-tribune-win-the-2022-worth-bingham-prize-at-harvard-for-the-price-kids-pay/), [Driehaus Award](https://www.propublica.org/atpropublica/propublica-chicago-tribune-win-driehaus-award-for-the-price-kids-pay), IRE Award, EWA award, NABJ Salute to Excellence (per [series page](https://www.propublica.org/series/the-price-kids-pay)).
- **What they found**:
  - 11,800+ municipal-ordinance tickets written to students over three school years (2019–2022) in 141 of 199 districts examined (covering 86% of Illinois high-schoolers); children as young as 8; fines $50–$1,000 plus up to ~$150 fees.
  - The mechanism: Illinois' 2015 SB100 bans schools from fining students as discipline, so deans call the school resource officer, who writes a city ticket for the same conduct — ~3,300 for vaping/tobacco, ~1,900 drug possession, 700+ fighting, 1,200+ disorderly conduct; 1,800+ truancy tickets, 1,000+ of them after a 2019 law barred referring truants for ticketing.
  - Black students were roughly twice as likely to be ticketed as white peers where race was recorded; quasi-judicial hearings offered no lawyer, no interpreter, near-certain liability (Crystal Lake: 7 not-liable out of 1,888 cases), debts routed to collections and state tax-refund garnishment.
- **Finding type(s)**:
  - `law-circumvention-channel` — a banned practice re-implemented by handing it to an adjacent institution outside the ban's scope (school→police→municipal code).
  - `disparate-impact-quantification` — group-normalized rates showing a burden falling disproportionately on a protected class.
  - `shadow-justice-process` — a fine/punishment apparatus operating without the procedural protections of the formal system it mimics.
- **Evidence & sources**:
  - Ticket-level citation records — 500+ FOIA requests to school districts *and* their local police departments (both sides of the handoff), assembled into a first-of-its-kind statewide database with offense, fine, and race where available.
  - Municipal ordinance codes and SB100 statutory text — public law, establishing the ban being circumvented.
  - Direct observation — reporters attended 50+ administrative-hearing dates, watching hundreds of cases.
  - Family-level financial records and interviews (e.g., an $800 tax-refund garnishment); district counterexamples (Evanston, CPS: zero tickets).
- **Detection signature**: **Two-institution handoff trace** — the prohibited output (fines on students) disappeared from the regulated entity's books and reappeared in a *different* agency's records for the same incidents; FOIAing both the school and the police department and joining on incident/date/school exposed the relay. Rate normalization by enrollment and race supplied the disparity finding.
- **Corroboration structure**: Paper records + courtroom observation + named-family case studies; district-by-district publication of counts in a lookup app (inviting local correction); legal framing validated with juvenile-justice attorneys; districts and police given comment.
- **Methodology notes**: No standalone methodology page found; method described in the main story and interactive ("more than 500 Freedom of Information Act requests... attended more than 50 hearing dates") — [stated in article](https://www.propublica.org/article/illinois-school-police-tickets-fines). Otherwise [inferred] from the article's "about the data" descriptions.
- **Official impact**: State superintendent urged schools to stop within hours of publication; state stopped collecting some ticket debt; AG civil-rights investigation; federal probe of the Garrison school; Illinois banned police ticketing/fining of students for school misbehavior in [May 2025](https://www.propublica.org/article/illinois-bans-police-ticketing-students-school-price-kids-pay).
- **Generalization**: Whenever a reform bans a revenue/punishment practice, look for the same cash-flow or sanction rerouted through an unregulated neighbor: court fees replacing banned fines, "voluntary" hospital liens, third-party debt collectors for public agencies, school-police referrals replacing suspensions. Generic detector: post-ban, query the *adjacent* institution's transaction records for the banned category and join to the regulated entity's population.

---

### Stuck Kids (2018) — Illinois held foster children in psychiatric hospitals long after doctors cleared them for release
- **URL**: https://features.propublica.org/stuck-kids/illinois-dcfs-children-psychiatric-hospitals-beyond-medical-necessity/ (series: https://www.propublica.org/series/stuck-kids; graphic: https://projects.propublica.org/graphics/il/stuck-kids/)
- **Partner/awards**: ProPublica Illinois original (Duaa Eldeib). Series page notes a 3rd-place 2018 Ruderman Foundation award for disability reporting ([series page](https://www.propublica.org/series/stuck-kids)).
- **What they found**:
  - Nearly 30% of all psychiatrically hospitalized children in DCFS care (2015–2017) were held **beyond medical necessity** — 800+ children, 27,000+ collective days (~75 years), because the agency had nowhere to place them.
  - Average stay for stuck kids: 64 days vs ~10-day national norm; 40%+ confined a month or longer past clearance; an 8-year-old girl held 153 days of which only 20 were medically justified; named cases include Gabriel Brasfield (58 days) and James Martin (7 months beyond necessity).
  - The state paid at least $7 million for the unnecessary hospital days; admissions beyond necessity jumped from 88 (2014) to 301 (2017).
  - Follow-on reporting exposed child-abuse allegations at Chicago Lakeshore Hospital, where DCFS kept sending kids; the hospital lost federal funding ([series page](https://www.propublica.org/series/stuck-kids)).
- **Finding type(s)**:
  - `custodial-warehousing` — people held in restrictive institutions past the point their confinement is medically/legally justified, because the responsible agency lacks placements.
  - `agency-self-knowledge` — the scandal was already quantified inside the agency's own tracking system; the finding is that the agency knew and did not act.
  - `harm-monetization` — attaching a public-dollar figure to the dysfunction ($7M for non-care).
- **Evidence & sources**:
  - DCFS's own "beyond medical necessity" tracking database (created 2015) — obtained via FOIA; covered ~6,000 psychiatric hospitalizations 2015–2017 with clearance vs discharge dating.
  - Confidential DCFS case records and internal investigation documents — leaked/source-provided ("confidential documents obtained by ProPublica Illinois").
  - Juvenile-court records and public-guardian litigation files; hospital records documenting discharge readiness.
  - Interviews: treating psychiatrists, hospital staff, Cook County Public Guardian, DCFS director (on record acknowledging the problem), and children/families reached through guardians with consent.
- **Detection signature**: **Clearance-to-exit gap accumulation** — each case carries two timestamps (clinically ready for discharge; actually discharged); computing the per-child gap and summing across the population converted an internal flag into 27,000 lost days and a dollar figure. The agency's own field ("beyond medical necessity") was the join key; the story is the distribution of that gap.
- **Corroboration structure**: Agency data cross-checked against individual case files and hospital discharge recommendations; clinicians on record; the agency's acting director conceded the numbers; follow-ups tracked the same metric over time ("Still No Answers," 2020).
- **Methodology notes**: No formal methodology page; a reporter's essay, ["Reporting on the Layers of Potential Harm..."](https://www.propublica.org/article/illinois-psychiatric-hospitals-dcfs-reporting-duaa-eldeib), describes sourcing confidential documents and agency figures. Data description otherwise [inferred] from the feature (FOIA'd dataset of ~6,000 hospitalizations; DCFS's 2015 tracking DB).
- **Official impact**: Legislative hearings within days; ACLU demands; a class-action lawsuit over languishing children; Chicago Lakeshore lost federal funding and DCFS stopped placements there ([series page](https://www.propublica.org/series/stuck-kids)).
- **Generalization**: Any custody system with a "ready for release" event and a separate "released" event: jail detainees held past bond/served time, immigrants past ordered release, nursing-home patients past rehab authorization, psychiatric boarding in ERs. Generic detector: demand the internal queue/flag dataset (agencies often already track their own failure), compute ready-vs-exit gaps, price the gap using the payer's daily rate.

---

### Overpolicing Parents (2022–2025) — The U.S. child-welfare system subjects millions of (disproportionately Black and poor) families to warrantless investigation, and some states terminate parental rights at speed
- **URL**: main stories: https://www.propublica.org/article/mandatory-reporting-strains-systems-punishes-poor-families ; https://www.propublica.org/article/child-welfare-search-seizure-without-warrants ; https://www.propublica.org/article/six-months-or-less-parents-lose-kids-forever (series: https://www.propublica.org/series/overpolicing-parents)
- **Partner/awards**: ProPublica + NBC News co-publication (Eli Hager, Agnel Philip, Mike Hixenbaugh, Suzy Khimm, Hannah Rappleye).
- **What they found**:
  - CPS agencies investigate the homes of ~3.5 million children a year — "opening refrigerators and closets without a warrant" — and only ~5% of investigated children are ultimately found physically or sexually abused.
  - NYC's ACS conducted 150+ home inspections per day but obtained fewer than 94 court entry orders a year (<0.2% of ~56,400 cases); a 40-state agency survey found warrants sought only after refusals, with no agency tracking how often.
  - In Maricopa County, 38% of Black children were subject to an investigation within the 5-year window (≈3x the white rate); researchers estimate 63% of Black children there are investigated by 18; Pennsylvania's 2015 mandatory-reporting expansion nearly quadrupled medical-neglect reports (~9,600 children investigated over five years).
  - "Death penalty of child welfare": West Virginia terminated parental rights for 2% of the state's children (2015–19), the nation's highest rate, with median removal-to-termination time nine months shorter than the national median.
- **Finding type(s)**:
  - `rights-asymmetry-mapping` — documenting that a state process imposing police-like intrusions operates without the constitutional protections of the criminal system it parallels.
  - `disparate-impact-quantification` (defined above).
  - `dragnet-yield-ratio` — comparing the scale of intrusive investigation to its confirmed-harm yield (3.5M investigated : ~5% substantiated) to show a system optimized for surveillance rather than detection.
  - `jurisdiction-outlier-ranking` — ranking states/counties on a normalized harm metric to name the extreme (West Virginia on termination speed; Maricopa on investigation rates).
- **Evidence & sources**:
  - NCANDS federal case-level files (FY2015–2020) — obtained from HHS's National Data Archive on Child Abuse and Neglect; millions of investigation records, deduplicated by child ID.
  - AFCARS foster-care files (2015–2019) — same archive; removals, terminations of parental rights, adoptions.
  - ACS/state administrative data (entry orders, hotline stats), obtained via records requests; caseworker training materials and agency policy manuals.
  - Original 40-state structured survey of child-welfare agencies on warrant practice.
  - Court rulings and statutes (Fourth Amendment case law; NY entry-order provisions); 40+ interviews with former caseworkers, judges, parents, attorneys; published epidemiology (lifetime-risk estimates) for context.
- **Detection signature**: **Population-denominator exposure rate** — case-level federal data deduplicated per child, first-investigation-per-county extracted, divided by ACS under-18 population by race → cumulative 5-year exposure rates by county and race. Paired with **time-to-event ranking**: AFCARS grouped by state, median time from first removal to termination computed and ranked. And a **warrant-to-search ratio**: intrusions counted from agency operations data vs judicial orders counted from court/agency records.
- **Corroboration structure**: Federal data triangulated with agency-level records requests, the 40-state survey, named-family case files (with parents' consent), caseworker testimony, and published academic estimates; methodological conservatism disclosed (no race imputation → undercounts).
- **Methodology notes**: Dedicated page: ["How We Analyzed Child Welfare Investigations"](https://www.propublica.org/article/how-we-analyzed-child-welfare-investigation-data) — "merged the separate fiscal year files... deduplicated according to the unique child IDs"; "our counts of investigations by race could be lower than the true number"; county masking below 1,000 entries/year noted.
- **Official impact**: New York banned anonymous child-welfare reports (June 2025); Texas mandated Miranda-style warnings in CPS investigations; Arizona's incoming governor named a disparities critic to lead its CPS agency ([series page](https://www.propublica.org/series/overpolicing-parents)).
- **Generalization**: Any mass administrative process with intrusive powers and case-level federal reporting (benefit-fraud investigations, immigration raids, housing inspections, stop-and-frisk): compute per-capita exposure by group and geography, the yield ratio (intrusions : confirmed findings), and time-to-irreversible-outcome by jurisdiction. Generic detector: national case-level archive + census denominators + a survey instrument for the procedural facts no one records.

---

### Level 14 (2015) — A California group home for the state's most troubled children collapsed into violence, drugs and rape while regulators dithered
- **URL**: https://www.propublica.org/article/rape-drugs-disorder-shake-california-group-home-and-provoke-reform-efforts (series: https://www.propublica.org/series/level-14)
- **Partner/awards**: ProPublica original (Joaquin Sapien; illustrated multimedia with Carrie Ching). No partner named on the methodology page.
- **What they found**:
  - In 2013, staff at EMQ FamiliesFirst's Davis campus — a "Level 14" (highest-intensity) home for ~70 children — lost control after a corporate policy shift; children as young as 9 disappeared for days, returning with accounts of drugs, sex and alcohol; the crisis culminated in an 11-year-old girl reporting rape by two boys from the home.
  - Police calls from the campus surged during the breakdown (an 18-month 911-call log documented location and nature of each call); the state's oversight investigations of group homes were "marked by delays and uncertainty."
  - Fallout tracked across jurisdictions: NYC cut ties with a group-home agency; Congress weighed scaling down group homes; California pivoted to foster-family models; a court later found the group home liable for millions in a child-abuse case ([series page](https://www.propublica.org/series/level-14)).
- **Finding type(s)**:
  - `institutional-collapse-reconstruction` — a chronological rebuild of how a facility deteriorated, using internal reports and emergency-call patterns as the spine.
  - `regulator-latency` — measuring the lag between documented incidents/complaints and oversight action.
- **Evidence & sources**:
  - "Unusual incident reports" filed by the facility to the Department of Social Services — three years of summaries plus six months of full reports, via public records requests.
  - Five years of state complaint investigations and facility evaluation reports for the Davis campus **and ~50 other Level 14 facilities statewide** — records requests; comparative baseline.
  - 911-call spreadsheet covering 18 months before closure (location + nature of every call) — obtained after Davis police **denied** the full incident reports.
  - Corporate paper: budgets, org charts, training manuals, financial statements, audits; county deeds/trusts/mortgages.
  - Court records from three lawsuits by residents and ex-employees; 30+ interviews (executives, counselors, therapists, children, parents, regulators, responding officers).
- **Detection signature**: **Proxy-record reconstruction** — when the primary incident record (police reports) was refused, the reporters substituted the 911 dispatch log as a frequency-and-type proxy, then rebuilt the narrative by matching calls to interviews and internal incident reports. Comparative pull of the same record type across ~50 peer facilities distinguished "this home went bad" from "all such homes look like this."
- **Corroboration structure**: Triple-sourced across institutional (incident reports, audits), law-enforcement (911 log, officer interviews), and human (staff, children, parents) layers; litigation records supplied sworn accounts.
- **Methodology notes**: Dedicated page: ["How We Reported 'Level 14'"](https://www.propublica.org/article/how-we-reported-level-14) — details the records inventory above, including the police denial and 911-log workaround.
- **Official impact**: The Davis campus shut; California moved away from group-home reliance toward foster families (Nov 2015); NYC terminated contracts; congressional reform hearings; multimillion-dollar liability verdict (2017) ([series page](https://www.propublica.org/series/level-14)).
- **Generalization**: For any licensed residential facility (group homes, halfway houses, assisted living, contracted shelters): mandated self-reports to the licensor + emergency-dispatch logs + peer-facility baselines are almost always obtainable even when police reports are not. Generic detector: spike detection in 911/EMS calls per bed relative to peer facilities, joined to the licensor's complaint-investigation latency.

---

### The Unbefriended (2024–2026) — New York's guardianship system left wards neglected in squalor while guardians billed them, and judges signed off
- **URL**: https://www.propublica.org/article/how-one-woman-endured-decade-neglect-new-york-guardianship ; https://www.propublica.org/article/new-york-guardianship-services-care-sick-elderly-confused-alone ; https://www.propublica.org/article/new-york-guardian-yvonne-murphy-beacon-eldercare-judges (series: https://www.propublica.org/series/the-unbefriended)
- **Partner/awards**: ProPublica original (Jake Pearson). No partner named on series page.
- **What they found**:
  - Judith Zbiegniewicz lived for years amid bedbugs, rats, mold, no heat and a partially collapsed roof while her guardian, New York Guardianship Services, collected $450/month from her account and told the court she was "thriving"; court examiners and a judge approved the reports annually.
  - Structural starvation of oversight: ~12 judges and 157 examiners for 17,411 NYC guardianship cases; reviews ran 2+ years late with no filing deadline; guardian training = one day (vs 250 hours for a NY nail-tech license); NYGS ran 167–300 wards per pair of case managers and claimed nonprofit status without IRS tax exemption.
  - Guardian Yvonne Murphy referred wards under her control to her own home-care company, Beacon Eldercare, in at least 20 documented instances — $1.5M of Beacon's revenue over three years (~25% of company income) came from her wards; one ward, Martin Chorost, had $417,697 moved to Beacon over 8 years; judges permitted the dual role for years despite examiner warnings of conflict of interest.
  - A judge later ordered a guardianship firm to repay thousands taken from an elderly woman "for services it never provided" ([series page](https://www.propublica.org/series/the-unbefriended)).
- **Finding type(s)**:
  - `paper-reality-gap` — official filings to an oversight body assert wellbeing/compliance flatly contradicted by physically verifiable conditions.
  - `self-dealing-fiduciary` — a court-appointed fiduciary routing the protected person's money to entities the fiduciary owns.
  - `oversight-capacity-arithmetic` — proving oversight is nominal by simple division (cases ÷ reviewers ÷ time).
- **Evidence & sources**:
  - Guardianship court files — hundreds of pages: annual accountings, guardian reports, court-examiner reviews, judicial orders (guardianship files are access-restricted; reviewed per named case).
  - Litigation-disclosed business records — three years of Beacon Eldercare client lists surfaced in a lawsuit, enabling the ward-to-vendor match.
  - Internal NYGS records and accounts from six people familiar with operations, including former employees (insider sourcing).
  - Building/inspection records and direct observation of the ward's housing; email correspondence between ward and guardian; IRS exempt-organization records (negative check: no tax exemption).
  - Court-system statistics (case and examiner counts).
- **Detection signature**: **Fiduciary flow cross-match** — the wards' court-filed financial accountings (money out) were joined against the guardian's own company's client list (money in), on ward name: every match is potential self-dealing that each individual judge, seeing one case at a time, never assembled. Secondary: **filing-vs-inspection diff** — the guardian's sworn "thriving" reports set against housing-inspection records and the reporter's own site visit.
- **Corroboration structure**: Court paper + insider accounts + physical verification + the oversight body's own workload numbers; subjects and company given detailed comment; findings framed per named ward with document citations.
- **Methodology notes**: No standalone methodology page found; method [inferred] from in-story sourcing statements (e.g., "reviewed three years of Beacon's client lists, which were disclosed in a lawsuit, and discovered that in at least 20 instances, Murphy referred a ward under her care to her own agency" — [Murphy story](https://www.propublica.org/article/new-york-guardian-yvonne-murphy-beacon-eldercare-judges)).
- **Official impact**: NY AG opened an investigation of guardianship providers (Jan 2025); courts appointed a special counsel to oversee reform (Nov 2024); governor's task force recommendations (Aug 2025); "Good Guardianship Act" proposed (Feb 2026) ([series page](https://www.propublica.org/series/the-unbefriended)).
- **Generalization**: Any court-supervised fiduciary regime (guardianships, conservatorships, bankruptcy trustees, estate executors, veterans' fiduciaries): cross-match the protected person's accountings against corporate registries/vendor lists linked to the fiduciary; divide caseload by reviewer capacity; ground-truth a sample of "all is well" filings. Minimum data: per-case accountings + fiduciary's business affiliations.

---

### Unfit to Teach (2026) — California's licensing agency let at least 67 educators found by their districts to have committed sexual misconduct keep their credentials
- **URL**: https://www.propublica.org/article/california-fired-teacher-sexual-harassment (series: https://www.propublica.org/series/unfit-to-teach)
- **Partner/awards**: KQED + ProPublica co-publication (Holly McDede, KQED; Mollie Simon, ProPublica).
- **What they found**:
  - At least 67 cases (2019–2025) where districts formally determined an educator committed sexual harassment/misconduct and reported it, yet the Commission on Teacher Credentialing did not revoke the license; at least 14 were rehired in education and 12 were still working.
  - Case spine: Jason Agan — fired in 2019 after 11+ students complained; an independent panel unanimously found him "unfit to teach"; the state took ~500 days to act, then imposed a 7-day suspension (2 days on a weekend); he was rehired at two more schools, drew a new complaint, and received tenure in 2024.
  - The public credential database shows only an unexplained red-flag icon; California law bars the licensing agency from releasing disciplinary records — unlike doctors, nurses, and lawyers in the state.
- **Finding type(s)**:
  - `dead-referral-pipeline` — mandatory reports flow from local institutions to a central discipline authority and terminate without action; the finding is the count of un-acted-on referrals.
  - `sanctioned-actor-migration` — individuals with adverse findings moving to new employers who cannot or do not see the record.
  - `transparency-asymmetry` — a licensing regime structurally more opaque than parallel professions.
- **Evidence & sources**:
  - District misconduct files — public-records requests to the 300 largest California districts; 150+ produced files; 350+ complaints obtained over more than a year (California Public Records Act; 10-day determination clock invoked).
  - Mandatory district reports to the credentialing commission on misconduct firings/resignations — requested from the districts (the commission itself is barred from releasing them).
  - State credentialing database — public lookup, joined case-by-case: "If the district determined that an educator had committed misconduct that it characterized as sexual... we checked the state licensing database to see whether the state had revoked the teacher's license."
  - Termination-hearing records — "presumed public when teachers object to their dismissals... or appeal"; obtained via the Department of General Services (which houses the hearings office) when direct routes stalled.
  - Interviews with students, parents, district officials; commission's on-record responses.
- **Detection signature**: **Referral-to-sanction join** — the local determinations (input side of the pipeline, reconstructed via mass records requests because the central registry is sealed) were matched by educator name against the public license status (output side); every "district found misconduct + license intact" pair increments the 67. The migration finding comes from **longitudinal employer tracking** of the same names across districts.
- **Corroboration structure**: District files (primary determinations) + independent hearing-panel records + state database status + rehiring employers' responses + named-student accounts; the count is a floor ("at least 67") since only 150 of 300 districts complied.
- **Methodology notes**: First-person methods piece: ["I Got Access to Hundreds of Teacher Misconduct Complaints in California — and You Can Too"](https://www.propublica.org/article/california-teacher-misconduct-public-records) — including the workaround doctrine: "If you can't get records from one agency, the answers you're looking for may exist somewhere else."
- **Official impact**: The Trump administration launched a national crackdown on district handling of teacher sexual misconduct, with the education secretary citing this investigation ([follow-up](https://www.propublica.org/article/trump-teacher-sexual-misconduct-crackdown-linda-mcmahon)); the profiled teacher left the classroom after new complaints.
- **Generalization**: Every licensed profession with local discipline feeding a central licensing body: police decertification, physician boards, securities brokers, childcare operators, contractors. Generic detector: reconstruct the input stream from the reporting institutions (employers, courts, insurers) when the registry is sealed, join to license status, count live licenses with adverse local findings; then track those names across subsequent employers.

---

### State of Disrepair (2023–2025) — Idaho, with the nation's worst-funded schools, hadn't assessed its buildings in 30 years — so reporters and the community did it themselves
- **URL**: https://www.propublica.org/article/idaho-deteriorating-schools-repair-bonds (series: https://www.propublica.org/series/state-of-disrepair)
- **Partner/awards**: ProPublica Local Reporting Network + Idaho Statesman (Becca Savransky, Statesman; Asia Fields, ProPublica).
- **What they found**:
  - Statewide census-by-journalism: all 115 superintendents surveyed (91% response); **every** responding district reported at least one facility problem posing a significant challenge; 78% reported five or more; heating (68%), cooling (67%), roof damage (61%); of 677 schools rated, 21% were in poor condition.
  - Collapsing roofs, sewage smells, freezing classrooms and flooded rooms documented at named schools, while Idaho ranked last in the nation in per-student school spending and required a two-thirds supermajority to pass building bonds — repeatedly dooming repair funding at the ballot (bond-threshold reform coverage on [series page](https://www.propublica.org/series/state-of-disrepair)).
  - A $25M state emergency-repair fund sat almost unused because its terms made it impractical for poor districts ([Sept 2023 story](https://www.propublica.org/series/state-of-disrepair)).
  - Post-publication: legislature approved $2 billion over 10 years for buildings — later shown to be "not nearly enough," with disabled students' access still unaddressed.
- **Finding type(s)**:
  - `synthetic-census` — journalists constructing the official dataset the state stopped collecting (30 years without a facilities assessment), then publishing it as the de facto public record.
  - `structural-veto-mechanism` — identifying the procedural rule (66.7% bond supermajority) that converts underfunding into permanent disrepair.
  - `unused-remedy` — a nominal fix (the $25M fund) whose design guarantees non-use.
- **Evidence & sources**:
  - Original structured survey of all 115 district superintendents — designed with a data team, piloted with district leaders, distributed through the administrators' association; May–Dec collection window.
  - Crowdsourced ground-truth — callout via Facebook/Reddit/local media/Idaho Education Association (10,000 members): 233 students, parents, teachers and others; instant-print cameras handed to students, who photographed boilers, stained ceilings, exposed wires ("dozens of photographs back").
  - Physical verification — tours of 39 school buildings with maintenance directors/superintendents; notecard interviews at six schools.
  - Public finance records: bond election results, state facility-fund usage, national per-pupil spending comparisons.
- **Detection signature**: **Distributed sensing census** — with no state dataset to FOIA, the reporters instrumented the population itself: a full-frame superintendent survey (supply side) cross-checked against crowdsourced student/teacher photo evidence (demand side) and 39 in-person tours (verification), producing statewide condition statistics no agency held. The funding-mechanism finding is a **rule-to-outcome trace**: supermajority requirement joined to repeated failed bond votes in the very districts reporting the worst conditions.
- **Corroboration structure**: Every crowd account was taken back to the district for confirmation before publication — "nearly every example that made it into our story was something that the districts agreed was an issue"; survey + photos + tours triangulated the same buildings.
- **Methodology notes**: Two dedicated pages: ["Idaho Hasn't Assessed School Buildings for 30 Years. Students and Educators Helped Us Do It Ourselves."](https://www.propublica.org/article/idaho-hasnt-assessed-school-buildings-30-years-students-educators-helped-us-do-it) and the replication guide ["How We Enlisted a Community to Report on Idaho's Crumbling Schools"](https://www.propublica.org/article/community-reporting-tips-idaho-schools).
- **Official impact**: Governor proposed and the legislature approved $2 billion for school buildings (Mar 2024); a district that had failed bonds for decades finally passed one (May 2024) ([series page](https://www.propublica.org/series/state-of-disrepair)).
- **Generalization**: Wherever a mandated inspection/assessment regime has lapsed (bridges, public housing, water systems, prisons): run a full-population survey of the responsible local officials plus a citizen photo callout, verify a sample in person, and publish the missing dataset. Minimum data: a complete roster of units and a repeatable instrument; the state's own non-measurement becomes the headline.

---

### Unequal Discipline (2022–2026) — One New Mexico district with a quarter of the state's Native students produced three-quarters of their expulsions
- **URL**: https://www.propublica.org/article/gallup-mckinley-schools-native-student-discipline (series: https://www.propublica.org/series/unequal-discipline)
- **Partner/awards**: ProPublica Local Reporting Network + New Mexico In Depth (Bryant Furlow; ProPublica's Joel Jacobs, Asia Fields, Maya Miller).
- **What they found**:
  - Gallup-McKinley County Schools — the largest Native American enrollment of any U.S. district (~12,000 students, 75% Native, mostly Navajo) — enrolled ~25% of New Mexico's Native students but accounted for at least 75% of the state's Native-student expulsions (2016-17 to 2019-20): 211 expulsions, an annual 4.6 per 1,000 — at least 10x the rest of the state.
  - 735 discipline incidents involving law enforcement over four years (~4x the state average); ~90% of the state's Native-student "disorderly conduct" expulsions occurred in this one district, under an offense the district didn't define until 2022-23.
  - When the superintendent claimed a relabeled category explained the numbers, reporters showed the reclassification didn't change the disparity ([rebuttal](https://www.propublica.org/article/propublica-responds-to-gallup-sun-native-american-student-discipline)); the district later claimed improvement using incomplete data ([2025 follow-up](https://www.propublica.org/article/gallup-mckinley-native-student-discipline-improvement-data)).
- **Finding type(s)**:
  - `concentration-attribution` — a statewide disparity decomposed by unit to show one institution generates most of it (the "ground zero" move).
  - `disparate-impact-quantification` (defined above).
  - `definitional-elasticity-abuse` — an undefined catch-all offense category ("disorderly conduct") absorbing discretionary punishment of one group.
- **Evidence & sources**:
  - State discipline incident extracts from New Mexico's STARS student data system (2010-11 through 2021-22) — public records requests to the Public Education Department; per-incident discipline type, police involvement, demographics.
  - STARS enrollment figures for the same years (rate denominators); NCES enrollment data confirming the "largest Native enrollment" claim.
  - 80 interviews, including 47 parents, grandparents, and current/former students; case files like "Matthew," expelled after write-ups for glue on a desk and playing on an elevator.
  - District artifacts: the strategic plan the district deleted from its website after inquiries; school-board records.
- **Detection signature**: **Share-of-harm vs share-of-population decomposition** — expulsion and police-referral counts normalized per 1,000 by district and race, then the state total decomposed by district: 25% of the population producing 75% of the harm identifies the outlier node. Robustness moves: multi-measure consistency ("for all measures of severe punishment, stark disparities persisted"), deliberately conservative ratio construction (publishing "4 times" when the raw computation showed 13x), and inclusion of a second data field ("Criminal Charge Code") districts used inconsistently for police involvement.
- **Corroboration structure**: Data + 80 human sources + adversarial engagement (two published rebuttals to the superintendent's objections, each re-running the numbers under his assumptions); pre-publication confrontation attempts over months.
- **Methodology notes**: Dedicated page: ["How We Found the School District Responsible for Much of New Mexico's Outsized Discipline of Native Students"](https://www.propublica.org/article/how-we-analyzed-new-mexico-school-discipline-data) — pandemic years excluded, pre-K denominator distortion and Hispanic-ethnicity classification limits disclosed.
- **Official impact**: New Mexico AG investigation (Sept 2023); AG-commissioned report confirming "substantial racial disparities" and demanding reform (2026) ([series page](https://www.propublica.org/series/unequal-discipline)).
- **Generalization**: Any regulated network of units reporting incident data to a state (districts, police departments, hospitals, nursing homes): decompose the aggregate disparity by unit; when one unit dominates, drill into its use of undefined/catch-all categories. Generic detector: concentration of adverse events vs population share, plus category-mix shifts after adverse attention (relabeling as evasion).

---

### Crackdown on Student Threats (2024–2026) — Tennessee's zero-tolerance threats law put hundreds of children — disproportionately disabled and Black — in handcuffs for jokes and rumors
- **URL**: https://www.propublica.org/article/tennessee-school-threat-law-kids-arrested (series: https://www.propublica.org/series/crackdown-on-student-threats)
- **Partner/awards**: ProPublica + WPLN/Nashville Public Radio (Aliyya Swaby, Paige Pfleger).
- **What they found**:
  - At least 519 Tennessee students were charged with threats of mass violence in 2023-24 (up from 442), before a 2024 law made even non-credible threats a **felony**; the youngest child charged was 7.
  - ~80% of juveniles charged over three school years had charges dismissed or diverted — the system's own outcomes showing the arrests didn't correspond to real threats; an 11-year-old was arrested at a family birthday dinner after the school had already cleared him to return.
  - Hamilton County arrested 18 students in the first six weeks of 2024-25 (more than double Nashville's count with fewer students); 39% of its arrested students were Black (30% of district) and 33% had disabilities (>2x their share); a 13-year-old autistic boy was arrested over a backpack that held a stuffed bunny.
  - No one can say how many students were expelled under the law: the state confirmed 12 expulsions while reporters documented 66 across just 10 districts; the education department's ~170 statewide "incidents" were undercut by ~100 more found in a sub-20-district sample ([data story](https://www.propublica.org/article/tennessee-school-threat-law-expulsions-data)).
- **Finding type(s)**:
  - `criminalization-of-noncrime` — a statute's enforcement dragnet applied predominantly to conduct its own courts later deem non-culpable.
  - `charge-outcome-funnel` — using downstream adjudication outcomes to characterize the quality of upstream arrests.
  - `data-vacuum-as-finding` — the state's inability/refusal to count the law's effects becomes the accountability story itself.
  - `disparate-impact-quantification` (defined above).
- **Evidence & sources**:
  - State juvenile-court case data — obtained via records request; charge counts and dispositions across three school years.
  - District-level records requests (arrest and expulsion counts) — met with refusals citing security, "no database," non-resident requester rules; the refusals were catalogued and published.
  - Police/sheriff incident reports and arrest narratives for named cases; school threat-assessment records.
  - Interviews with families (on record with minors' guardians), judges, defense attorneys, threat-assessment researchers; legislative records tracking the felony upgrade and copycat laws in Georgia and New Mexico.
- **Detection signature**: **Arrest-to-adjudication funnel** — charges pulled from juvenile-court data were followed to disposition; an 80% dismissal/diversion rate quantifies a dragnet criminalizing non-threats. Paired with **sample-vs-official extrapolation**: reporter-collected district counts (66 expulsions in 10 districts) set against the state's confirmed figure (12) to prove the official monitoring is broken, and county-to-county **enforcement-rate contrast** (Hamilton vs Davidson) to show arbitrary geography of enforcement.
- **Corroboration structure**: Court data + district records + named-case documents + expert literature on threat assessment; each anecdote anchored to paperwork (arrest records, school letters); state agencies' non-answers quoted directly.
- **Methodology notes**: No standalone methodology page; data provenance [stated in articles] ("Data that ProPublica and WPLN obtained through a records request..." — [main story](https://www.propublica.org/article/tennessee-school-threat-law-kids-arrested)); the data-gap mechanics detailed in the [expulsions-data story](https://www.propublica.org/article/tennessee-school-threat-law-expulsions-data). Otherwise [inferred].
- **Official impact**: A district paid $100,000 to settle the 11-year-old's family's suit (May 2025); Tennessee lawmakers passed a fix to the threats law (Apr 2026) ([series page](https://www.propublica.org/series/crackdown-on-student-threats)).
- **Generalization**: Any new mandatory-enforcement statute (school threats, retail-theft felonies, fare evasion): join arrest/charge data to dispositions to compute the funnel; compare enforcement intensity across similar jurisdictions; and test whether anyone in government can produce the law's basic usage statistics. Minimum data: charge-level court data with outcomes; a sample of local records to audit the official aggregate.

---

### The Right to Read (2022) — Where fewer adults can read, fewer people vote — and a Georgia woman was prosecuted for helping them
- **URL**: series: https://www.propublica.org/series/the-right-to-read ; methodology: https://www.propublica.org/article/voter-participation-literacy-accessibility
- **Partner/awards**: ProPublica original (Aliyya Swaby, Annie Waldman; one co-published piece with Gray Television/InvestigateTV). Series received an Emmy nomination (per [series page](https://www.propublica.org/series/the-right-to-read)).
- **What they found**:
  - Across 3,100+ counties, the share of adults with low literacy correlates strongly and negatively with turnout in 2016/2018/2020 (r = -0.57 to -0.58, p < 0.0001); lowest-literacy-tercile counties averaged 58.8% turnout in 2020 vs 73.1% for the highest — a gap worth "up to 7 million votes."
  - About 1 in 5 U.S. adults struggle to read at a basic level; the adult-education system reaches a tiny fraction of them ([adult-ed story on series page](https://www.propublica.org/series/the-right-to-read)).
  - Narrative spine: Olivia Coley-Pearson of Douglas, Georgia, was criminally prosecuted — twice — for assisting voters who couldn't read their ballots; ballot design, assistance restrictions and new voting laws compound the barrier.
- **Finding type(s)**:
  - `structural-disenfranchisement-correlation` — an ecological statistical association linking a capability deficit to depressed civic participation, presented with explicit causal humility.
  - `criminalized-assistance` — prosecution of the workaround people use to exercise a right.
- **Evidence & sources**:
  - NCES PIAAC small-area literacy estimates (surveys 2012/2014/2017; county/state modeled via small-area estimation with census covariates) — public statistical product.
  - County turnout: Dave Leip's Atlas of U.S. Elections vote counts ÷ Census citizen-voting-age population — purchased/public data.
  - Court records of Coley-Pearson's prosecutions; state voting statutes on assistance; interviews with low-literacy voters and advocates.
- **Detection signature**: **Ecological correlation with robustness battery** — county literacy joined to county turnout across three cycles; terciles compared; 1,000-iteration resampling of small-county estimates to show stability; explicit disclosure that "correlation is not causation" and that model covariates (poverty, education) could confound. The move is not proving causation but establishing a stable, large-magnitude association the state has no program to address.
- **Corroboration structure**: Statistical finding paired with ground-level narrative (prosecuted helper, named voters) and policy analysis (multilingual guides, ballot-complexity critique); national survey literature cited for individual-level plausibility.
- **Methodology notes**: Dedicated page: ["How We Analyzed Literacy and Voter Turnout"](https://www.propublica.org/article/voter-participation-literacy-accessibility) — quotes above; limitations stated at unusual length.
- **Official impact**: No statute change claimed; the series produced multilingual voter guides in 10+ languages and an Emmy-nominated video component (per series page).
- **Generalization**: Join any modeled capability surface (literacy, broadband, disability rates, English proficiency) to participation outcomes (turnout, benefit uptake, court appearance rates) at small geography; where the correlation is strong, look for the enforcement mechanism punishing the coping behavior (assistance bans, strict signature rules). Minimum data: small-area estimates + administrative participation data + the statute governing "help."

---

### Miseducation (2018) — A national database exposing racial gaps in opportunity, discipline and achievement at 96,000 U.S. schools
- **URL**: https://projects.propublica.org/miseducation/ (methodology: https://projects.propublica.org/miseducation/methodology)
- **Partner/awards**: ProPublica original news app (Lena V. Groeger, Annie Waldman, David Eads); reporting recipe released for local journalists.
- **What they found**:
  - At 96,000+ public and charter schools and 17,000 districts, Black and Hispanic students are on average less likely to be enrolled in gifted programs and AP courses than white peers, and more likely to be suspended, expelled, and referred to law enforcement.
  - District-level achievement gaps (grade-level-equivalent differences) and a segregation dissimilarity index computed for 2,500+ districts made every district's disparity publicly lookup-able.
  - Data-quality finding embedded in the tool: 69,000+ schools skipped the law-enforcement-officer question in the federal collection, making police-in-schools figures "a minimum, not exact, number."
- **Finding type(s)**:
  - `public-disparity-instrument` — packaging a federal dataset into a per-institution accountability lookup that localizes a national pattern (the finding is delivered as infrastructure, not narrative).
  - `disparate-impact-quantification` (defined above).
  - `undercount-exposure` (defined above — the skipped-question audit).
- **Evidence & sources**:
  - Federal Civil Rights Data Collection (2015-16), Office for Civil Rights — public download; the "master list for all schools and districts."
  - NCES Common Core of Data (2015-16) and EDGE geography — public.
  - Stanford Education Data Archive (SEDA) pooled test scores 2008-09 to 2014-15 — academic public dataset.
- **Detection signature**: **Risk-ratio grid with significance gating** — for each school/district, the relative likelihood of each racial group's presence in AP/gifted (opportunity) and suspension/expulsion/arrest (discipline) computed as risk ratios with 95% confidence intervals, suppressing non-significant cells; achievement gaps joined from SEDA; segregation via dissimilarity index. The innovation is running one standardized disparity computation across *every* institution in the country simultaneously.
- **Corroboration structure**: Self-reported federal data caveated explicitly ("There may be errors in the CRDC, as with any self-reported data"); Hawaii's gifted data dropped; statistical gating instead of anecdote; local verification delegated to users via the published reporting recipe.
- **Methodology notes**: Dedicated page: [Miseducation Methodology](https://projects.propublica.org/miseducation/methodology).
- **Official impact**: No single statute; the tool became source infrastructure for local reporting nationwide (companion: ["Reporting Recipe: How to Investigate Racial Disparities at Your School"](https://www.propublica.org/getinvolved/reporting-recipe-how-to-investigate-racial-disparities-at-your-school)).
- **Generalization**: Any federal per-institution compliance dataset (CRDC, HMDA, Medicare Compare, EEO-1) can be converted into a standardized per-unit disparity instrument with significance gating; the skipped-question rate is itself an audit finding. Minimum data: one cycle of the federal collection + denominators; publishing the tool recruits distributed verification.

---

### Barns, Go-Karts and Strip Malls (2026) — Voucher money is spawning thousands of unregulated private schools, some run by people already sanctioned in public education
- **URL**: https://www.propublica.org/article/private-schools-vouchers-growth-florida-arizona-west-virginia (topic page: https://www.propublica.org/topics/education)
- **Partner/awards**: ProPublica (Jennifer Smith Richards, Megan O'Matz, Mollie Simon, Jennifer Berry Hawes); companion pieces include an Arkansas school expose built on video evidence ([Delta Institute story](https://www.propublica.org/article/arkansas-private-schools-vouchers-delta-institute-developing-brain-autism-harm)) and a Texas Tribune co-publication on private-school voucher applicants.
- **What they found**:
  - Across 13 states with published private-school directories and voucher-style programs, at least 1,500 more private schools exist than five years ago (9,600+ total); Florida added ~100/year; Arkansas ~120 in three years after its voucher launch; states allocated $10.6 billion to private-school programs in 2025 (+29% YoY).
  - New "schools" operate out of barns, farms, addiction-treatment centers, co-working spaces, homes and a family fun center next to a go-kart track (West Virginia); Arizona's education department says state law *prohibits* it from overseeing private schools, and some states cannot say how many private schools exist.
  - Sanctioned operators resurface: an Ohio superintendent convicted of misusing public funds reopened in Florida and drew $291,165 in public money over three years; a Florida teacher stripped of her license for sexual abuse opened a private school in 2025; students with disabilities are lawfully turned away.
- **Finding type(s)**:
  - `oversight-vacuum-mapping` — establishing, jurisdiction by jurisdiction, that no agency claims authority over a publicly funded activity.
  - `sanctioned-actor-migration` (defined above — across state lines and school sectors).
  - `subsidized-sector-boom-census` — measuring the gold-rush entry of new operators that follows a new public funding stream.
- **Evidence & sources**:
  - State private-school directories over time (13 states) — public listings, diffed across years to count entrants.
  - Voucher/ESA payment data — state records showing public dollars per school/operator.
  - Cross-state licensure and criminal records for named operators (Ohio conviction → Florida operation; Florida license revocation → new school).
  - Site-level verification: addresses resolved to barns/strip malls/fun centers; agency statements disclaiming jurisdiction; interviews with families of excluded disabled students.
- **Detection signature**: **Directory diff + payment join** — successive snapshots of each state's private-school directory identify new entrants; joining entrants to voucher payment data quantifies public money flowing to unregulated operators; joining operator names to out-of-state discipline/criminal records surfaces sanctioned-actor migration. The Arizona finding is a **jurisdiction-denial collection**: on-record statements from each regulator that nobody is in charge.
- **Corroboration structure**: Data census + named-case deep dives (payment records, conviction records, license actions) + physical/address verification + state-agency statements; disability-exclusion documented through family accounts and school policies.
- **Methodology notes**: No standalone methodology page yet; method [stated in article] ("analyzed data from 13 states" with published directories and funding programs; cross-referenced with voucher payment data). Otherwise [inferred].
- **Official impact**: Recent publication (July 2026); no legislative response yet recorded on the topic page.
- **Generalization**: Any newly subsidized private sector with an entity register (home-care agencies after Medicaid waivers, private colleges under GI Bill, childcare subsidy networks): diff the register over time, join to the subsidy ledger, then screen operators against other states' and sectors' sanction lists. Minimum data: periodic entity lists + payment records + sanction registries.

---

## Cluster Synthesis

### 1. Recurring evidence-source types (frequency across the 13 investigations)

| Evidence class | Count | Where |
|---|---|---|
| Mass parallel public-records requests to many local agencies (100–500+ FOIAs) | 7 | Quiet Rooms (300+), Price Kids Pay (500+), Unfit to Teach (300 districts), Unequal Discipline, Crackdown, Level 14, Stuck Kids |
| State administrative databases extracted via records request (discipline systems, tracking DBs, court data, credential registries) | 7 | STARS (NM), DCFS beyond-necessity DB, TN juvenile-court data, CA credential DB, IL ticket records, NY court workload stats, voucher payment data |
| Federal statistical collections (CRDC, NCANDS, AFCARS, PIAAC, CCD, SEDA) | 4 | Miseducation, Overpolicing Parents, Quiet Rooms (CRDC foil), Right to Read |
| Institution-authored incident paperwork (seclusion logs, "unusual incident reports," discipline write-ups, guardians' annual reports) | 5 | Quiet Rooms, Level 14, Unequal Discipline, Unbefriended, Stuck Kids |
| Court files as investigative substrate (guardianship accountings, juvenile courts, lawsuits, administrative hearings) | 7 | Unbefriended, Crackdown, Level 14, Stuck Kids, Price Kids Pay (hearings observed), Unfit to Teach (termination hearings), Right to Read (prosecutions) |
| Confidential/internal records via insider sources | 3 | Stuck Kids (DCFS files), Unbefriended (NYGS internals), Level 14 (corporate paper) |
| Original structured surveys of officials/agencies | 3 | State of Disrepair (115 superintendents), Overpolicing Parents (40 states), Quiet Rooms (district canvass) |
| Crowdsourced/citizen documentation (photo callouts, tip callouts) | 3 | State of Disrepair, Unfit to Teach, Right to Read guides |
| Physical site verification (tours, home visits, room inspections, address checks) | 4 | State of Disrepair (39 tours), Quiet Rooms (3 districts), Unbefriended, Vouchers |
| Emergency-dispatch/police proxy records when primary records refused | 1 (decisive) | Level 14 (911 logs) |
| Large-N interviews (80–120+) anchored to specific records | ~all | e.g., Quiet Rooms 120+, Unequal Discipline 80 |

A distinctive access layer runs through the child-welfare stories: confidential juvenile/guardianship records were reached through insiders, guardians'/parents' consent, litigation-disclosed exhibits (Beacon client lists), and public-guardian intermediaries — negotiating access to confidential records is itself a method in this cluster.

### 2. Recurring detection signatures (my tags; frequency)

| Signature | Count | Instances |
|---|---|---|
| **Standard-vs-record audit** — incident records diffed against the legal trigger that authorizes the practice | 3 | Quiet Rooms (safety-reason field), Crackdown (credible-threat standard), Overpolicing (warrant requirement vs searches) |
| **Denominator-normalized disparity ratio** — adverse events ÷ group population, compared across groups/units | 5 | Price Kids Pay, Unequal Discipline, Miseducation, Overpolicing Parents, Crackdown |
| **Pipeline join (referral→action / clearance→exit)** — two stages of one bureaucratic process joined on person/case to find the drop-off | 4 | Unfit to Teach (misconduct finding→license), Stuck Kids (clearance→discharge), Crackdown (charge→disposition funnel), Unbefriended (examiner warning→judicial action) |
| **Official-count vs ground-records diff (undercount exposure)** | 4 | Quiet Rooms zero-claim audit, Crackdown expulsions (12 vs 66), Miseducation skipped-question audit, Unequal Discipline reporting-gap checks |
| **Concentration decomposition** — aggregate harm decomposed by unit to find the dominant contributor | 2 | Unequal Discipline (75% from one district), Price Kids Pay (district league table) |
| **Two-institution handoff trace** — banned/regulated practice rerouted through an adjacent agency, exposed by joining both agencies' records | 2 | Price Kids Pay (school→police), Vouchers (public funds→unregulated schools) |
| **Fiduciary/self-dealing flow cross-match** — protected person's outflows joined to fiduciary-linked entities | 1 | Unbefriended (accountings × Beacon client list) |
| **Paper-vs-reality diff** — sworn filings vs physical inspection | 2 | Unbefriended, State of Disrepair (cousin: nominal remedy vs unusable terms) |
| **Synthetic census / distributed sensing** — build the dataset the state stopped collecting | 3 | State of Disrepair, Miseducation (as public instrument), Vouchers (directory diff) |
| **Proxy-record reconstruction** — substitute record stream when the primary is refused | 2 | Level 14 (911 logs), Unfit to Teach (DGS hearing files when the registry sealed) |
| **Sanctioned-actor migration tracking** — follow disciplined individuals across employers/states | 2 | Unfit to Teach, Vouchers |
| **Ecological correlation with robustness battery** | 1 | Right to Read |
| **Time-to-event distribution ranking across jurisdictions** | 2 | Overpolicing (removal→termination by state), Stuck Kids (days past clearance) |

### 3. Transferable pattern candidates

**Pattern: The Banned-Practice Relay.**
When a practice is prohibited for institution A, it rarely stops — it migrates to adjacent institution B that the ban does not reach (schools barred from fining students → police write municipal tickets at the school's request; fine collection → tax-refund garnishment). Mechanics: obtain records from *both* sides of the handoff, join on incident/person/date/location, and show the regulated entity initiating what the unregulated entity executes. Minimum data: the prohibition's text and effective date; transaction/citation/incident records from the adjacent institution; a join key tying events to the regulated entity's population. Recognition cue in any domain: a reform "succeeds" on the regulated entity's own metrics while a neighboring agency's volume in the same category rises; staff of A appear as initiators/complainants in B's records.

**Pattern: The Dead-Referral Pipeline.**
Mandatory reporting regimes create a paper trail from local determinations to a central sanctioning authority — and the pipeline silently terminates (districts' sexual-misconduct findings → licensing board inaction; court examiners' conflict warnings → judges' continued appointments). Mechanics: reconstruct the input stream from the *reporting* institutions (mass records requests to employers/courts, since the central registry is usually sealed), then join by name to the public output (license status, appointment lists); every "adverse local finding + no central action" pair is a countable failure, and following the names forward exposes migration to new victims. Minimum data: local determinations from a meaningful sample of reporters; the central registry's public status field; stable person identifiers. Recognition cue: any profession/system where the sanctioning body cites confidentiality while local institutions each hold their fragment.

**Pattern: The Clearance-to-Exit Gap.**
Custodial and queue-based systems record when a person becomes *eligible* to leave and when they actually leave; the gap distribution is the scandal (psychiatric clearance vs discharge; ready-for-placement vs placed). Mechanics: obtain the internal tracking data (agencies frequently flag their own failures — DCFS literally maintained a "beyond medical necessity" table), compute per-case gaps, sum person-days, and price them at the payer's daily rate; name the incentive holding people in place (per-diem billing, missing capacity). Minimum data: two timestamps per case plus the daily cost. Recognition cue: waitlists, boarding, "administrative holds," or any population described as "awaiting placement" — ask for the eligibility date field.

**Pattern: The Zero-Report Audit.**
Central statistics built from self-reporting are falsified from below; the tell is implausible zeros or minima. Mechanics: from the central collection, sample entities reporting zero/lowest-decile incidents; records-request their raw ground-level logs for the same period; publish the ratio of found-to-reported (75 zero-seclusion districts probed for incident files; 66 expulsions found where the state confirmed 12; 69,000 schools skipping the police question). Minimum data: the central self-reported dataset and raw local records for a purposive sample. Recognition cue: any compliance statistic where the reporting entity bears the cost of accurate reporting and no one audits (restraint counts, use-of-force, infection rates, wage-theft complaints).

**Pattern: The Synthetic Census.**
When the state has stopped measuring (no facilities assessment in 30 years; no register of subsidized private schools; no warrant statistics), build the missing official dataset and publish it as infrastructure: full-roster surveys of responsible officials, crowdsourced photographic ground truth, directory diffs over time, or standardized computation over a federal collection (Miseducation). Mechanics: enumerate the complete population of units; design one repeatable instrument; verify a sample physically; take every finding back to the institution for confirmation pre-publication; release the dataset/lookup so others extend it. Minimum data: a complete unit roster and any repeatable measurement channel (survey, callout, directory snapshots). Recognition cue: an agency that answers "we don't track that" about its core statutory duty — the non-measurement is the first finding, and the built dataset is both the evidence and the impact vehicle.

---

*Report compiled 2026-07-29. URLs verified live via propublica.org during compilation; no database writes performed.*
