# ProPublica Evidence Ontology — Cluster 16: Tribal Affairs & Indigenous Rights

Research date: 2026-07-29. Method: fetched all six series index pages (propublica.org/series/<slug>), then deep-fetched 15 articles/methodology pages/database pages. Web research only; no DB writes. The `/topics/indigenous` and `/topics/indigenous-affairs` topic pages both 404; the six series pages themselves served as the complete census (matching the empirical census of 6 series / 73 items).

**Series covered (all 6):**

| Series | Theme | Partner | Items |
|---|---|---|---|
| [The Repatriation Project](https://www.propublica.org/series/the-repatriation-project) | NAGPRA non-compliance; Native remains held by museums/universities | NBC News | ~25 |
| [Broken Promises](https://www.propublica.org/series/broken-promises) | Columbia Basin salmon collapse vs. 1850s treaty guarantees | Oregon Public Broadcasting (Local Reporting Network) | ~21 |
| [Waiting for Water](https://www.propublica.org/series/waiting-for-water) | Tribal water rights in the Colorado River Basin | High Country News (+KJZZ, 2026) | 6 |
| [Promised Land](https://www.propublica.org/series/promised-land) | Hawaiian Home Lands homesteading failure | Honolulu Star-Advertiser (Local Reporting Network) | ~14 |
| [Lessons Lost](https://www.propublica.org/series/lessons-lost) | Bureau of Indian Education school failure | Arizona Republic (Local Reporting Network) | 5 |
| [Power Grab](https://www.propublica.org/series/power-grab) | Green-energy siting vs. tribal cultural resources in Washington | High Country News | 4 |

Coverage below: 11 story extractions across the 6 series, deepest on The Repatriation Project as directed.

---

## SERIES 1: THE REPATRIATION PROJECT (deepest extraction)

### America's Biggest Museums Fail to Return Native American Human Remains + the NAGPRA compliance database (2023) — the country's most prestigious institutions still hold the remains of 110,000+ Native ancestors 33 years after federal law ordered them returned

- **URL**: https://www.propublica.org/article/repatriation-nagpra-museums-human-remains (flagship, Jan 11, 2023); interactive database: https://projects.propublica.org/repatriation-nagpra-database
- **Partner/awards**: Co-published with NBC News (Graham Lee Brewer co-byline with Logan Jaffe, Mary Hudetz, Ash Ngu). Reporter Mary Hudetz won the [2024 Richard LaCourse Award for Investigative Journalism](https://www.propublica.org/atpropublica/mary-hudetz-honored-with-2024-richard-lacourse-award-for-investigative-journalism) for the series.
- **What they found**:
  - More than 110,000 Native American, Native Hawaiian and Alaska Native ancestors' remains were still held by U.S. institutions at publication (Jan 2023), despite the 1990 Native American Graves Protection and Repatriation Act (NAGPRA); **10 institutions held about half** of all unreturned remains.
  - Institution-level compliance scorecards: UC Berkeley 9,000+ not returned (~22% made available at publication), Harvard's Peabody 6,100+ (39%), Illinois State Museum 7,500+ (2%), Ohio History Connection 7,100+ with only 17 (0.2%) made available; ~200 institutions had made available none of the roughly 14,000 ancestors they collectively reported.
  - Enforcement was essentially nonexistent: Interior Department records showed only **$59,111.34 in total fines collected from 20 institutions since 1990**.
  - Institutions weaponized the "culturally unidentifiable" classification to indefinitely retain remains; museums that received federal preservation grants (Field Museum, $400,000) spent little on repatriation.
  - Database mechanics: for each of ~650 reporting institutions the tool shows remains **not** made available for return, remains made available, and percent made available. National totals as of the Jan 2025 update: 210,000+ total remains reported since 1990; 90,831 (42%) still not made available; 613 tribes notified of remains availability ([database](https://projects.propublica.org/repatriation-nagpra-database); [Feb 2025 update note](https://www.propublica.org/article/native-american-remains-returned-repatriation-nagpra)).
- **Finding type(s)**:
  - `statutory-compliance-ledger` — a per-institution scorecard measuring compliance with a specific legal mandate, built from the government's own records (defined here; recurs below).
  - `classification-as-evasion` — use of a legal category ("culturally unidentifiable") as an escape hatch that converts a return mandate into indefinite retention (defined here).
  - `enforcement-vacuum` — quantifying near-zero penalties against widespread documented violations (defined here).
- **Evidence & sources** (typed):
  - *Federal program inventory data*: National Park Service National NAGPRA Program public inventory data (institution-by-institution counts of remains and funerary objects reported under the law) — obtained from NPS; database states current update data as of Jan. 6, 2025.
  - *Legal-notice stream*: Federal Register "Notice of Inventory Completion" notices, in which institutions formally publish which tribes may claim remains — used to determine what has been "made available for return."
  - *Regulatory enforcement records*: Interior Department civil-penalty data (the $59,111.34 figure).
  - *Advisory-body transcripts*: 30 years of federal NAGPRA Review Committee meeting transcripts — dispute-by-dispute record of institutional resistance.
  - *Institutional correspondence*: e.g., 2018 University of Alabama–tribal leader emails; March 2022 Field Museum CEO letter to the Interior Secretary; 19th-century Smithsonian correspondence (1873 Joseph Henry letter) establishing the collecting era's intent.
  - *Tribal filings*: e.g., a 117-page Muskogean cultural-affiliation document submitted to the federal review committee (2021).
  - *Interviews*: 100+ tribal leaders, museum professionals, NAGPRA practitioners.
- **Detection signature**: **Mandate-inventory compliance join.** The federal government already collects, but does not publish usably, an institution-level ledger of NAGPRA obligations. ProPublica joined NPS National NAGPRA inventory data to Federal Register inventory-completion notices on institution identity, computing for every institution: (reported holdings) − (remains published as available to tribes) = unreturned backlog and a percent-complete metric. The critical design decision was **pipeline-stage precision**: they measured "made available for return" (the legally reportable step) rather than physical transfer, because "the law doesn't require reporting on actual transfers" ([database methodology](https://projects.propublica.org/repatriation-nagpra-database)). Ranking institutions by absolute backlog and percent-complete surfaced both the hoarders (Berkeley, Illinois State Museum, Ohio History Connection) and the concentration finding (10 institutions ≈ half of everything).
- **Corroboration structure**: Self-reported federal data (floor estimate) → cross-checked against Federal Register notices → institution responses solicited pre-publication → the tool itself shown to "14 tribal representatives and several repatriation experts and museum officials" before launch → individual case studies (Alabama, Field, Berkeley) documented with correspondence and interviews. Explicit undercount discipline: numbers are "a minimum estimate of individuals"; "institutions frequently adjust these numbers when they reinventory groups"; some institutions "entirely failed to report the remains in their possession" ([Behind ProPublica's Reporting on Repatriation](https://www.propublica.org/article/behind-propublica-reporting-on-repatriation)).
- **Methodology notes**: Two stated methodology pages — ["Behind ProPublica's Reporting on Repatriation"](https://www.propublica.org/article/behind-propublica-reporting-on-repatriation) (data source = NPS National NAGPRA public inventory data; limitation: "The program is only able to look up data by institution, rather than by tribe"; self-reporting caveats above) and the replication recipe ["How to Report on the Repatriation of Native American Remains at Museums and Universities Near You"](https://www.propublica.org/article/how-to-report-on-repatriation-of-native-american-remains), which spells out the analytic sequence: search the database by institution/tribe/state; compare institutions handling remains from the same county to find **conflicting affiliation decisions** ("federal agencies have been generally more likely than museums to repatriate remains taken from the Southwest area"; where determinations differ, "ask why their determinations were different"); read Federal Register notices for acquisition history; request excavation field notes, consultation records and internal correspondence; and defines terms ("cultural affiliation" = "shared group identity connecting a present-day tribe with an earlier group" by "a preponderance of evidence"; "made available for return" used "only for remains that have already been through that process, and the only step left is for the specified tribes to decide").
- **Generalization**: Any statute imposing a duty on hundreds of decentralized institutions with self-reported inventories supports the same build: consent-decree compliance, ADA remediation, mine-reclamation bonding, hospital charity-care obligations, pension funding, art looted in wartime. Generic detector: government mandate + entity-level self-reports + a formal legal-notice stream marking completion → join on entity, compute percent-complete, rank, and check whether the same underlying item gets different legal classifications at different entities.
- **Impact (one line)**: Senate probe of universities/museums (Apr 2023), Illinois repatriation law (Aug 2023), Interior's overhauled NAGPRA rules (Dec 2023) that among other things killed the "culturally unidentifiable" loophole, AMNH closing Native exhibit halls (Jan 2024), UC Berkeley moving to repatriate 4,400 (Nov 2023), and record-scale returns in 2023–2024 — all documented in follow-ups on the [series page](https://www.propublica.org/series/the-repatriation-project).

### Tribes in Maine Spent Decades Fighting to Rebury Ancestral Remains. Harvard Resisted Them at Nearly Every Turn. (2023) — a 30-year obstruction playbook reconstructed from Harvard's own paper trail

- **URL**: https://www.propublica.org/article/inside-wabanaki-tribes-struggle-to-reclaim-ancestral-remains-from-harvard (Dec 4, 2023)
- **Partner/awards**: ProPublica (Mary Hudetz, Ash Ngu); part of the LaCourse-award-winning series.
- **What they found**:
  - Four Wabanaki nations (Penobscot, Passamaquoddy, Maliseet, Mi'kmaq) sought ~43 ancestors from Blue Hill Bay; Harvard's Peabody rejected claims in 2011 and 2013 for insufficient evidence despite oral histories and research.
  - A Peabody official assured tribes in 1995 that no destructive analysis would occur without permission — while museum policy actually permitted it; in October 2013 Harvard's Reich Lab extracted ancient DNA from remains in a report marked confidential; Harvard then cited unpublished DNA work against repatriation, and tribes learned of the testing only through rumor at a March 2015 federal hearing.
  - Peabody director Jeffrey Quilter pressured Phillips Academy's Ryan Wheeler (2013–14) to reverse his repatriation commitment — emails obtained by ProPublica show the campaign; an allied archaeologist called tribes "anti-science thugs" in email.
  - Harvard agreed to return the remains only in 2021, after George Floyd-era reckoning and its slavery report — roughly 30 years after NAGPRA passed.
- **Finding type(s)**:
  - `documentary-obstruction-reconstruction` — a multi-decade timeline proving deliberate institutional delay, assembled from the institution's internal records against its public statements (defined here).
  - `secret-science-on-contested-property` — undisclosed destructive research performed on items subject to a pending legal claim, then used as leverage in that claim (defined here).
- **Evidence & sources** (typed):
  - *Internal emails* (obtained by ProPublica — acquisition route not stated; [inferred] via sources or records of the public institutions involved): Quilter–Wheeler pressure exchange; Bourque emails; Quilter "stakes are very high" memo.
  - *Institutional memoranda*: 1995 memo-to-file of the Peabody's visit with tribes recording the no-destructive-analysis assurance.
  - *Confidential lab report*: Reich Lab ancient-DNA report (Oct 2013, marked confidential).
  - *Federal hearing transcript*: March 2015 NAGPRA Review Committee session where the testing surfaced publicly.
  - *Peer-reviewed literature*: Wheeler & Newsom paper characterizing Harvard's "tactical strategy" of delay.
  - *Federal compliance data*: NAGPRA database counts (Harvard ~5,500 held; under half returned as of Nov 2023).
  - *Interviews*: tribal elders, attorneys, the Phillips Academy director, Harvard geneticist David Reich (by email).
- **Detection signature**: **Assurance-vs-conduct timeline diff.** Order every internal document, public statement, filing and hearing transcript on one time axis; the finding is each point where the institution's contemporaneous private conduct (confidential DNA extraction, pressure emails) contradicts its assurances to the claimant (1995 memo) or its stated reasons for denial (citing research the tribes were never told about). Verbatim: "Emails obtained by ProPublica show that Quilter pressured Wheeler to change his mind…"
- **Corroboration structure**: Internal documents anchored to public records (hearing transcripts, NAGPRA filings), then validated by on-the-record interviews with participants on both sides; adversaries (Reich, Bourque) given the documents and quoted responding.
- **Methodology notes**: No standalone methods page; [inferred] from in-article sourcing ("emails obtained by ProPublica," the 1995 memo, hearing transcript). The series-level methodology (above) covers the compliance-data layer.
- **Generalization**: The move works wherever an institution both adjudicates and benefits from a claim against itself (universities, churches, insurers, employers self-investigating). Generic detector: obtain the internal correspondence around each claim-denial date and diff it against the stated denial rationale; flag undisclosed actions taken on the contested asset while the claim was pending.
- **Impact (one line)**: Remains were finally repatriated and reburied; the story fed the Senate scrutiny of Harvard and the Dec 2023 federal rule overhaul documented elsewhere in the series.

### A Scientist Said Her Research Could Help With Repatriation. Instead, It Destroyed Native Remains. (2023) — federally funded science pulverized ancestors' bones under a repatriation justification that never produced a repatriation

- **URL**: https://www.propublica.org/article/delayed-repatriation-allows-destructive-research-native-american-remains (July 20, 2023, Mary Hudetz)
- **Partner/awards**: ProPublica (series-level partner NBC News on flagship; this piece solo).
- **What they found**:
  - University of Utah anthropologist Joan Brenner Coltrain received **$222,218 in NSF grants (2002–2010)** to study Ancestral Pueblo remains held by Harvard's Peabody and the American Museum of Natural History — grinding bone for mitochondrial DNA and isotope chemistry on 80+ ancestors, without tribal consent.
  - The stated justification was that the work could help institutions determine affiliation and "help the institutions finally return the remains to descendant tribes"; in fact "the studies never resulted in Harvard or the AMNH repatriating human remains to any of the tribes that trace their ancestry to sites studied by Brenner Coltrain."
  - The work seeded further destructive studies (Plog radiocarbon sampling; a 2017 Nature paper on Pueblo Bonito Room 33 mtDNA).
- **Finding type(s)**:
  - `mission-inverted-research` — activity funded and justified as advancing a legal mandate that in practice consumed/destroyed the very assets the mandate protects (defined here).
  - `grant-outcome-mismatch` — a claimed public-benefit outcome in funding documents matched against the real-world outcome record and found empty (defined here).
- **Evidence & sources** (typed):
  - *Federal grant records*: NSF award database entries and grant reports (stated purposes, amounts, dates).
  - *Scientific literature*: the resulting publications (2010; 2017 Nature) identifying which remains were sampled.
  - *NAGPRA inventories*: NPS filings showing the same remains never repatriated.
  - *Researcher correspondence*: previously unreported emails between the scientists.
  - *Interviews*: scientists, tribal representatives, museum staff.
- **Detection signature**: **Grant-promise vs. outcome diff with specimen-level tracing.** Join (a) grant proposals' stated purpose, (b) publications' materials-and-methods sections identifying specific remains/sites sampled, and (c) NAGPRA inventory/repatriation status for those same remains. The join key is the specimen/site (e.g., Pueblo Bonito Room 33). The mismatch — funded "to help repatriation," zero resulting repatriations, remains partially destroyed — is the finding. A timeline overlay showed grants predated inventory completion, i.e., research ran ahead of the legal process.
- **Corroboration structure**: Public grant records + published papers (immutable) anchored the claim; emails and interviews supplied intent; institutions and the scientist responded on the record.
- **Methodology notes**: [inferred] from in-article sourcing (NSF records, publications, inventories); no standalone page.
- **Generalization**: Works for any funding stream justified by a compliance/benefit narrative: "diversity" grants, restoration funds, opioid-settlement spending, carbon offsets. Generic detector: extract stated-purpose text from awards; enumerate the concrete assets/populations touched (from outputs/publications/deliverables); query the authoritative registry for whether the promised end-state ever occurred.
- **Impact (one line)**: AMNH banned destructive research on human remains (2020, after Room 33 fallout); Interior moved to require halting research on request of a tribe; NSF drafted tribal-consultation requirements for grantees.

### A Prominent Museum Obtained Items From a Massacre of Native Americans. The Survivors' Descendants Want Them Back. (2023) — AMNH accession registers tie children's belongings in its collection to the Wounded Knee killing field

- **URL**: https://www.propublica.org/article/wounded-knee-american-museum-natural-history (Oct 20, 2023, Nicole Santa Cruz)
- **Partner/awards**: ProPublica.
- **What they found**:
  - AMNH holds items taken from the field of the 1890 Wounded Knee massacre (250+ Lakota killed), including "a toy saddle, a doll shirt, beaver bones, an adornment piece and a bear claw."
  - Provenance runs through a soldier (Frank X. Holzner) and an 1895-documented donation via Army surgeon Edgar Mearns, recorded in the museum's own handwritten accession registers and annual report.
  - Despite NAGPRA's "expeditious return" mandate, the Oglala Lakota had received zero repatriations from AMNH; descendants (Wendell Yellow Bull, descendant of Joseph Horn Cloud) want the items back: "If they are from the killing field, they need to come back."
- **Finding type(s)**:
  - `atrocity-provenance` — held property traced to acquisition at a specific documented atrocity, converting an abstract "collection" into evidence of the event and a live legal/moral claim (defined here).
- **Evidence & sources** (typed):
  - *Museum accession registers* (handwritten) and the museum's 1895 annual report — the institution's own acquisition ledger.
  - *Military records*: an Army captain's Jan 3, 1891 letter describing removal of bodies/objects from the site.
  - *Early-20th-century oral-history archive*: Joseph Horn Cloud's firsthand accounts recorded by researcher Eli Ricker.
  - *Interviews*: survivor descendants, tribe, museum.
- **Detection signature**: **Accession-to-atrocity provenance join.** Museum catalog metadata (donor name, accession date, described origin) joined to independent military and archival records of the event on person + date + place: soldier/donor present at the massacre → items entered collection immediately after → items described as from the site. The chain converts catalog entries into massacre evidence.
- **Corroboration structure**: Institution's own ledgers (against interest) + contemporaneous military correspondence + descendant oral history + tribal confirmation; museum given chance to respond.
- **Methodology notes**: [inferred] from cited records; no standalone page (series methodology covers the database layer).
- **Generalization**: Identical to Nazi-era art provenance, colonial loot (Benin bronzes), conflict antiquities, and even seized-asset auctions. Generic detector: for any held-asset registry with donor/date metadata, join donor names against rosters of participants in documented violent/coercive events and flag acquisitions within a short window after the event.
- **Impact (one line)**: Contributed to the pressure arc that preceded AMNH's January 2024 closure of its Native American exhibit halls ([follow-up](https://www.propublica.org/article/american-museum-natural-history-to-close-native-american-exhibits)).

---

## SERIES 2: BROKEN PROMISES (salmon / treaty fishing rights)

### The U.S. Has Spent More Than $2 Billion on a Plan to Save Salmon. The Fish Are Vanishing Anyway. (2022) — the hatchery system that replaced treaty-guaranteed wild salmon fails its own recovery benchmark

- **URL**: https://www.propublica.org/article/salmon-hatcheries-government-climate-change (May 24, 2022, Tony Schick/OPB + Irena Hwang/ProPublica); data methodology: ["How Not to Count Salmon"](https://www.propublica.org/article/salmon-hatcheries-pnw-fish-data) (May 31, 2022, Irena Hwang)
- **Partner/awards**: Oregon Public Broadcasting via ProPublica's Local Reporting Network; the companion documentary "Salmon People" won a national [Edward R. Murrow Award](https://www.propublica.org/atpropublica/propublica-and-partners-win-five-edward-r-murrow-awards) (news documentary).
- **What they found**:
  - ~$2.2 billion spent over two decades on aging Columbia Basin hatcheries (the federal substitute for wild runs destroyed by dams), with **federal cost per returning salmon of $250–$650** at the largest hatchery cluster and a $320 million unfunded repair backlog.
  - Survival analysis: **2014–2018, none of eight monitored salmon/steelhead populations met the 4% adult-return benchmark** the Northwest Power and Conservation Council says is needed to rebuild runs; even in good ocean years (2008–2013) only two of eight did; some returns as low as 0.8–2.2%.
  - Treaty context: 1850s treaties guaranteed tribes fish at "usual and accustomed places"; a **1947 Interior Department memo** declared the salmon run "must be sacrificed" for dam development — hatcheries were the compromise; a 2021 NOAA study projected steep further decline under warming.
- **Finding type(s)**:
  - `outcome-per-dollar-failure` — computing unit cost and success rate of a program against its own stated numeric goal (defined here).
  - `treaty-substitute-audit` — evaluating the performance of the thing government offered *in place of* a treaty obligation, against the standard of that obligation (defined here).
- **Evidence & sources** (typed):
  - *Scientific tag-tracking database*: PIT-tag (passive integrated transponder) detection records from Columbia Basin Research, University of Washington — juvenile releases matched to adult return detections; obtained from the academic data center.
  - *(Rejected) coded-wire-tag databases*: initial approach abandoned (see below).
  - *Federal budget/spending records*: NOAA hatchery budgets, infrastructure assessments.
  - *Agency planning benchmarks*: NPCC 4% recovery target.
  - *Peer-reviewed and agency science*: 2021 NOAA projection study.
  - *Archival policy documents*: 1947 Interior memo; treaty texts.
- **Detection signature**: **Cohort survival computation against the government's own benchmark.** Verbatim: they "obtained data from Columbia Basin Research… describing fish in several salmon and steelhead trout populations that were embedded with electronic tags" and "calculated survival rates across two time periods: 2008–2013 and 2014–2018," comparing tagged juveniles released against adults later detected returning upriver, then benchmarked against the 4% goal. A second computation divided federal hatchery spending by adult returns → cost-per-fish. The killer design choice, per the methodology piece, was abandoning facility-level accounting for **population-level cohort tracking**: "Instead of the database of hatchery-by-hatchery performance we'd initially envisioned, I ended up with just 16 numbers: two for each of the eight salmon or trout populations."
- **Corroboration structure**: Two ocean-condition eras analyzed separately (controls for the agencies' favorite confounder); benchmark taken from the government itself (immune to "wrong yardstick" rebuttal); paired with agency budget records and expert/tribal interviews; visual reporting fact-checked separately (["Yes, We Fact-Checked These Watercolors"](https://www.propublica.org/article/fact-checking-illustrations-accuracy)).
- **Methodology notes**: Stated, in unusual candor — ["How Not to Count Salmon"](https://www.propublica.org/article/salmon-hatcheries-pnw-fish-data) documents the failed first approach: "In the world of hatcheries, there is no one metric for success. Each hatchery seemed to have a different target for the number of juveniles it released"; multi-facility production chains ("Brood stock might be collected at one location, their eggs fertilized at a different place…") made facility attribution "impossible," forcing the redesign to PIT-tag cohorts and a single scanning location near the river mouth. The *measurement chaos itself* is reported as a finding about the program.
- **Generalization**: Any subsidized production/restoration program with unit-level tracking (job-training completions, reforestation seedlings, prisoner reentry, refugee resettlement): compute cohort success rate at a fixed downstream checkpoint against the program's own target, and treat "no standardized success metric across facilities" as a reportable accountability defect, not just an obstacle.
- **Impact (one line)**: Fed the policy arc documented in series follow-ups — $200M federal commitment to reintroduction (Sept 2023), tribes given control of salmon-recovery funds (Dec 2023), White House acknowledgment of dam harms (2024) ([series page](https://www.propublica.org/series/broken-promises)).

### The U.S. Promised Tribes They Would Always Have Fish, but the Fish They Have Pose Toxic Risks (2022) — reporters commissioned their own lab tests and found the salmon tribes were told to eat carry unsafe mercury/PCB levels regulators never tested for

- **URL**: https://www.propublica.org/article/how-the-us-broke-promise-to-protect-fish-for-tribes (Nov 22, 2022, Tony Schick/OPB, Maya Miller/ProPublica)
- **Partner/awards**: Oregon Public Broadcasting.
- **What they found**:
  - OPB/ProPublica's own testing showed "concentrations of two chemicals in the salmon that the EPA and both Oregon and Washington's health agencies deem unsafe" (mercury, PCBs; dioxin cancer risk also flagged) in salmon caught above Bonneville Dam.
  - Risk is concentrated on tribes: members eat 6–11x more fish than the general population; at even half of commonly reported tribal consumption rates the detected levels exceed health thresholds; roughly 1-in-20,000 lifetime cancer risk at average tribal diet.
  - FOIA'd EPA records showed staff had flagged contamination in Columbia River fish **since the 1990s** (1992 carp study; 92+ contaminants detected in 1990s testing) while agencies did "so little testing for toxic chemicals in fish that even public health and environmental agencies admit they don't have enough information."
- **Finding type(s)**:
  - `journalist-commissioned-measurement` — the newsroom generates the missing primary data itself (purchases samples, pays a certified lab) where regulators declined to measure (defined here).
  - `agency-knew-timeline` — FOIA-built chronology showing internal knowledge of a hazard long predating public warning or action (defined here).
  - `exposure-inequity-quantification` — same hazard, differential dose: matching contaminant levels to subpopulation consumption rates (defined here).
- **Evidence & sources** (typed):
  - *Commissioned lab science*: 50 salmon purchased from tribal fishers upriver of Bonneville Dam (Sept 2021), composite samples tested by certified lab (ALS) for 13 metals + 2 chemical classes.
  - *FOIA documents*: internal EPA studies/memos from the 1990s onward.
  - *Regulatory standards*: EPA, Oregon Health Authority, Washington DOH thresholds — the benchmarking layer.
  - *Federal consumption surveys*: tribal vs. general-population fish-consumption rates.
  - *Interviews*: tribal members/fishers, health officials.
- **Detection signature**: **Fill-the-regulator's-gap sampling + threshold join.** Where the finding is an *absence* (no agency fish-tissue testing program), generate the measurement yourself with defensible chain of custody, then join results against the agencies' *own published safety thresholds* and *their own consumption survey data* for the affected population. The two-sided join (their thresholds × their consumption numbers × your measurements) leaves agencies no methodological exit.
- **Corroboration structure**: Certified lab (defensible chemistry) → agency thresholds as benchmark → FOIA record proving prior internal knowledge → agencies confronted, responses printed; legislative reaction documented in a follow-up ([Dec 2022](https://www.propublica.org/article/toxic-salmon-columbia-river-basin-lawmaker-response)).
- **Methodology notes**: Sampling/testing design stated in-article (purchase count, location, lab, analyte classes); no separate methods page — finer detail [inferred from article text].
- **Generalization**: Anywhere a regulator's testing regime has a hole with a disparately exposed subpopulation: drinking water in prisons, soil in redlined neighborhoods, subsistence-hunted game near military ranges. Generic detector: enumerate what the agency is supposed to monitor vs. what it actually samples (testing-coverage diff); where the hole overlaps a high-dose subgroup, commission the measurement.
- **Impact (one line)**: Washington and Oregon health departments said they would weigh an official public-health advisory; a lawmaker called the findings "deeply troubling" and demanded changes (series follow-up above).

### How a Federal Agency Is Contributing to Salmon's Decline in the Northwest (2022) — Bonneville Power Administration banked a $360M surplus while cutting inflation-adjusted fish spending and protecting its dams

- **URL**: https://www.propublica.org/article/salmon-protection-dam-bonneville-power-administration (Aug 4, 2022, Tony Schick/OPB)
- **Partner/awards**: Oregon Public Broadcasting, ProPublica Local Reporting Network.
- **What they found**:
  - BPA's two-year fish-and-wildlife budget fell $78M (inflation-adjusted) from 2016–17 levels even as net revenues beat targets by $360M — none of the windfall went to fish; a 2018 strategic plan capped fish spending at inflation.
  - Structural asymmetry: two upper-Columbia dams generating ~half of BPA's power have had **zero fish passage for 50+ years**, while the four lower Snake dams — producing only ~4% of its power — are the ones scientists (NOAA, 60+ signatories) say must be breached; Snake River Chinook fell from ~90,000 (mid-1950s) to ~10,000 (1980) as dams multiplied; salmon recovery has cost over $20 billion since 1980.
  - Agency "flexible spill" survival claims (35% improvement) contradicted by Fish Passage Center analyses; a 2018 funding accord restricted tribal salmon-reintroduction work.
- **Finding type(s)**:
  - `budget-priority-inversion` — an agency's discretionary allocations diffed against its legal/mitigation obligations, revealing which mission actually governs (defined here).
  - `power-vs-protection-asymmetry` — mapping which assets get protected against which produce revenue, exposing that protection tracks revenue, not stated mission (defined here).
- **Evidence & sources** (typed):
  - *Agency strategic/budget documents*: BPA 2018 strategic plan, budget series 2016–present.
  - *Financial results*: net-revenue vs. target figures.
  - *Independent scientific monitor*: Fish Passage Center spill analyses.
  - *Scientists' letters*: NOAA + 60-scientist dam-breaching conclusions.
  - *Contracts*: 2018 funding accord terms limiting tribal reintroduction efforts.
  - *Historical run counts + dam construction timeline*.
- **Detection signature**: **Surplus-vs-mandate ledger diff.** Compute (revenue windfall) vs. (change in mandated-mitigation spending, inflation-adjusted) from the agency's own financial documents; then cross-tab dams by (share of power revenue) × (fish-passage/breach status). The two matrices together show mitigation dollars and dam protection both align with revenue, not with fish — while public messaging claims the opposite (public statements diffed against internal strategy documents and emails).
- **Corroboration structure**: Agency's own documents → independent technical monitor (FPC) → external scientific consensus letters → tribal accord terms → agency response.
- **Methodology notes**: [inferred] from in-article description of records; no standalone page.
- **Generalization**: Any revenue-generating public authority with a statutory mitigation duty (port authorities, turnpikes, utilities with cleanup obligations): diff surplus disposition against mitigation-budget trajectory; cross-tab asset protection against asset revenue share.
- **Impact (one line)**: Part of the record behind the 2023 Columbia Basin agreement giving tribes control of restoration funds and BPA's diminished role — later abandoned by the Trump administration in 2025 ([series follow-up](https://www.propublica.org/article/trump-salmon-columbia-river-tribes-deal)).

---

## SERIES 3: WAITING FOR WATER (Colorado River Basin tribal water rights)

### How Arizona Stands Between Tribes and Their Water (2023) — a census of every basin water settlement shows Arizona uniquely extracts sovereignty concessions and imposes decades-long delays

- **URL**: https://www.propublica.org/article/how-arizona-stands-between-tribes-and-their-water (June 14, 2023, Mark Olalde, Umar Farooq/ProPublica, Anna V. Smith/High Country News)
- **Partner/awards**: Co-published with High Country News.
- **What they found**:
  - Of Arizona's 22 federally recognized tribes, 10 still have unsettled water claims; ProPublica computed Arizona tribes wait ~34 years on average for resolution (vs. ~18 years on average elsewhere/for partial settlements), using settlement-timeline data.
  - Arizona uniquely conditions water settlements on tribes **waiving the ability to take new land into trust** — all four tribes that settled with Arizona since 2003 accepted this; in 2020 Arizona Republicans proposed barring casino licenses for tribes with unresolved water litigation (coercive linkage).
  - Adjudication design as denial: no specialized water courts; two mega-cases with "tens of thousands" of parties before a single judge have "dragged on for decades." Consequences documented: the $128M Dilkon Medical Center on Navajo land finished but unable to open for lack of clean water; Navajo Nation blocked from transporting its New Mexico water into Arizona during COVID.
  - Doctrinal stakes: the 1908 *Winters* doctrine ("tribes with reservations have a right to water, and most should have priority in times of shortage") was under threat in the pending Navajo SCOTUS case.
- **Finding type(s)**:
  - `adjudication-attrition` — procedural structure (venue, party count, no specialized court) functioning as substantive denial, quantified by wait-time metrics (defined here).
  - `settlement-condition-extraction` — comparative review of settlement terms revealing one jurisdiction systematically extracting unrelated sovereignty concessions as the price of a legal entitlement (defined here).
- **Evidence & sources** (typed):
  - *Comprehensive settlement corpus*: verbatim — they "reviewed every water rights settlement in the Colorado River Basin and interviewed presidents, water managers, attorneys and other officials from 20 of the 30 federally recognized basin tribes."
  - *Academic timeline dataset*: settlement-timing data from researcher Leslie Sanchez (USFS Rocky Mountain Research Station), which ProPublica analyzed for average waits.
  - *Court filings*: 1908 *Winters*; 2023 *Arizona v. Navajo Nation* arguments.
  - *Public-records requests*: state Department of Water Resources communications.
  - *Tribal government correspondence*: 2020 Pascua Yaqui chairman letter; Navajo AG letter calling Arizona's stance "an invasion of the Nation's sovereign authority."
  - *Federal administrative records*: BIA land-into-trust decisions/appeals; legislation with inserted water-transport restrictions.
  - *Expert interviews*: former Interior water official Anne Castle ("additional hurdles"), Indigenous-law scholars.
- **Detection signature**: **Settlement-census term extraction + wait-time metric.** Assemble the complete population of settlements in a basin (not a sample); code each for (a) elapsed time from claim to resolution and (b) attached non-water conditions. One state's outlier pattern — land-into-trust waivers present in 4/4 of its post-2003 settlements, absent elsewhere — plus outlier wait times (34 vs. 18 years) isolates the obstruction to a specific actor and mechanism.
- **Corroboration structure**: Full-population document review → quantitative timeline analysis → 20-of-30-tribes interview coverage → named-expert validation → state given response opportunity.
- **Methodology notes**: Stated in-article (the "reviewed every water rights settlement… interviewed 20 of the 30" sentence); no separate methods page. The wait-time computation attributed to analysis of Sanchez's data.
- **Generalization**: Any entitlement resolvable only through negotiation with a hostile counterparty: code the full corpus of consent decrees / settlements / plea agreements for attached unrelated conditions and elapsed time, grouped by jurisdiction. A single jurisdiction whose agreements systematically carry off-topic concessions is running a leverage scheme.
- **Impact (one line)**: No quantified policy change at publication; the series framed the 2024–26 basin negotiations (see the June 2026 follow-up on four states stalling the tribal deal, same series).

### The Colorado River Flooded Chemehuevi Land. Decades Later, the Tribe Still Struggles to Take Its Share of Water. (2023) — a tribe legally entitled to 11,340 acre-feet uses ~3% of it while Southern California cities consume the rest free

- **URL**: https://www.propublica.org/article/chemehuevi-tribe-reservation-water-colorado-river-california (July 5, 2023, Mark Olalde, Umar Farooq/ProPublica, Anna V. Smith/HCN)
- **Partner/awards**: Co-published with High Country News.
- **What they found**:
  - The Chemehuevi hold a decreed entitlement of 11,340 acre-feet/year (~3.7B gallons) — quantified in the 1960s "at a time when the tribe didn't have federal recognition" — but use only ~3%; "97% of the tribe's water remains in the river and ends up being used by Southern California cities."
  - Basin-wide, **1+ million acre-feet per year of quantified tribal water goes unused** by tribes and is consumed downstream without compensation.
  - Root cause is infrastructure, not law: Parker Dam (1930s) flooded ~7,000 acres of the tribe's arable bottomland to create Lake Havasu; the federal government then never funded pumps/delivery, while taxpayers built the Central Arizona Project canal delivering the same river to cities. "It's not enough to have the right to the water. You also have to have the infrastructure." / "From the perspective of the people using that water, why would they pay when they're already getting it for free?"
- **Finding type(s)**:
  - `paper-rights-gap` — legal entitlement vs. physical delivery/use, quantified, with identification of who captures the undelivered share (defined here).
  - `uncompensated-reallocation` — benefit of an unused legal right flowing systematically to third parties at zero price (defined here).
- **Evidence & sources** (typed):
  - *Judicial decrees*: the 1960s quantification of the tribe's right (Arizona v. California line of decrees).
  - *Federal water accounting*: Bureau of Reclamation use records; Central Arizona Project records — the "actual use" side of the diff.
  - *Historical federal reports*: 1973 National Water Commission report to Congress (documented the government building non-Indian projects while neglecting tribal ones).
  - *Development plans*: a USC agricultural development plan for the reservation (what was possible but unfunded).
  - *Research organizations*: Ten Tribes Partnership / Water & Tribes Initiative quantifications of unused tribal water.
  - *Interviews*: tribal leadership, water-law scholars.
- **Detection signature**: **Entitlement-vs-delivery diff with beneficiary tracing.** Join the decreed acre-feet (paper ledger) to Reclamation's actual diversion/use accounting (physical ledger) per rights-holder → the unused residual; then trace hydrologically/contractually who consumes the residual (Southern California cities) and at what price (zero). The infrastructure-funding asymmetry (CAP built for cities; nothing built for the tribe) supplies the causal mechanism.
- **Corroboration structure**: Court decree (legal fact) + federal accounting (usage fact) + historical commission reports (long-standing federal knowledge) + present-day interviews; the 1973 report shows the gap was known to Congress for 50 years.
- **Methodology notes**: [inferred] from records cited in-article; series-level statement ("reviewed every water rights settlement…") applies.
- **Generalization**: Royalty owners vs. operators, restitution awards vs. collections, housing-voucher issuance vs. lease-up, broadband subsidies vs. buildout: wherever a right requires an unfunded delivery mechanism. Generic detector: for each holder in an entitlement registry, compute utilization from the operational ledger; where utilization ≈ 0, identify the free-riding consumer of the residual and the missing funded infrastructure step.
- **Impact (one line)**: No discrete policy change stated; contributed to basin-wide attention culminating in the tribal coalition deal tracked in the June 2026 series follow-up.

---

## SERIES 4: PROMISED LAND (Hawaiian Home Lands)

### To Reclaim Ancestral Land, All Native Hawaiians Need Is a $300,000 Mortgage and to Wait in Line for Decades (2020) — a land trust created for the poor was run so only the affluent could collect, and 2,000+ died waiting

- **URL**: https://www.propublica.org/article/hawaii-native-land-homesteads-department-of-hawaiian-home-lands (Oct 24, 2020, Rob Perez/Honolulu Star-Advertiser, Agnel Philip/ProPublica); methodology: ["How We Found Low-Income Hawaiians Were Left Behind by the Homesteading Program"](https://www.propublica.org/article/how-we-found-low-income-hawaiians-were-left-behind-by-the-homesteading-program)
- **Partner/awards**: Honolulu Star-Advertiser, ProPublica Local Reporting Network.
- **What they found**:
  - The Department of Hawaiian Home Lands (DHHL) waitlist stood at ~23,000 applicants; at recent award rates the queue implies ~182 years to satisfy demand; **at least 2,000 applicants died while waiting (1995–2020)** — an explicit undercount.
  - **60% of ~2,200 Oahu residential lease awards since 1995 went to applicants living in census tracts with median household income above $75,000**, in a program created by the 1921 Hawaiian Homes Commission Act as, in Prince Kuhio's words, "the first opportunity given the poor man to go on the land with funds to help him make a living." Median homestead-subdivision income (~$100,000) is nearly double waitlister household income (~$55,000).
  - Mortgage qualification became a de facto eligibility test (turnkey homes at $300–400K; only ~25% of waitlisters could afford a 10% down payment on even a $150K home); DHHL "routinely had to go thousands deep on its waitlist to find applicants willing and able to accept a lease."
- **Finding type(s)**:
  - `means-tested-program-capture` — a program legally aimed at the poor whose award mechanics filter for the affluent (defined here).
  - `waitlist-mortality` — deaths-in-queue as the human-cost metric of administrative failure (defined here).
  - `de-facto-eligibility-test` — an unlegislated financial requirement functioning as the real gatekeeper (defined here).
- **Evidence & sources** (typed):
  - *Agency transactional database*: "the department's database of applicants, lessees and transactions from 1995… to January 2020" — two separate logs (waitlist changes; lease changes). Acquisition route not stated in the methods piece ([inferred]: records request to the state agency).
  - *Geocoding + census overlay*: Google Maps geocoding API on addresses → census tracts → tract median income and Native Hawaiian population share.
  - *Mortality markers in administrative text*: waitlist records "that included some indicator that the individual had died" — death dates or the literal string "DEC'D."
  - *Federal context studies*: HUD research on Native Hawaiian housing; Hawaii Supreme Court rulings; trust documents.
  - *Interviews*: beneficiaries, officials.
- **Detection signature**: **Queue-to-award join with income-tract overlay and in-queue mortality scan.** The two agency logs were linked "using the lessee name and lease start date" (their stated join key), yielding per-person wait duration (application date → lease date). Award recipients' addresses geocoded and aggregated to census tracts gave the income distribution of *winners* vs. the waitlist population — the 60%-above-$75K finding. A text scan of the waitlist log for death markers ("DEC'D") produced the 2,000-deaths floor. Analysis deliberately restricted to Oahu "due to data reliability concerns on other islands."
- **Corroboration structure**: Findings and methods "presented… to DHHL, but officials said the department doesn't have the capacity to evaluate them" (the agency couldn't even audit its own data); conservative counting posture stated ("almost certainly conservative because the department records a death only if it is reported by a family member"); individual beneficiary stories verified separately.
- **Methodology notes**: Stated — dedicated methods page (URL above) with join keys, geocoding method, tract aggregation, Oahu restriction, and mortality-scan procedure quoted above.
- **Generalization**: Any queue-based benefit (public housing, Section 8, transplant lists, disability adjudication, visa backlogs): join application log to award log on person+date; overlay awardee geography/income; scan status fields for deceased markers. Red flags: awards requiring private financing, and agencies "going thousands deep" past list order — both signs the formal queue is not the real allocation rule.
- **Impact (one line)**: Hawaii lawmakers proposed and then passed **$600 million** (2022) to fix the program, explicitly following the investigation ([proposal](https://www.propublica.org/article/lawmakers-propose-600-million-to-fix-housing-program-for-native-hawaiians); [passage](https://www.propublica.org/article/lawmakers-approve-600-million-to-help-fix-housing-program-for-native-hawaiians)).

### The U.S. Owes Hawaiians Millions of Dollars Worth of Land. Congress Helped Make Sure the Debt Wasn't Paid. (2021) — the federal government sold land it owed to the Hawaiian trust to churches, developers and a private school instead

- **URL**: https://www.propublica.org/article/the-us-owes-hawaiians-millions-of-dollars-worth-of-land-congress-helped-make-sure-the-debt-wasnt-paid (May 7, 2021, Rob Perez); companion: [How the Deals Approved by Congress Bypassed Thousands of Hawaiians Waiting for Homes](https://www.propublica.org/article/how-the-deals-approved-by-congress-bypassed-thousands-of-hawaiians-waiting-for-homes)
- **Partner/awards**: Honolulu Star-Advertiser, ProPublica Local Reporting Network.
- **What they found**:
  - Under a 1995 federal law settling the U.S. debt for 1,400+ acres taken from the Hawaiian Home Lands trust without compensation, ~960 acres were to be conveyed; only ~900 acres arrived, ~70 still outstanding — a shortfall worth **$39–55M in today's dollars**.
  - Congress passed **at least six laws authorizing federal land sales to private parties** rather than to the trust; ~40 deals covering ~520 acres in a decade benefited "the Catholic Church; the nonprofit operator of a private school; a developer that intends to sell a site to another company with plans to construct hundreds of private-sector homes."
  - Navy parcels sold to six churches, a veterans group and school operators (2013–2019) generated ~$9M — none reaching the trust; Ford Island redevelopment legislation (1999, 2006) routed land to Texas developer Hunt Cos.
  - Meanwhile ~11,000 Hawaiians sought Oahu homesteads and the trust held land for under a third of them.
- **Finding type(s)**:
  - `land-debt-ledger-reconstruction` — computing an unpaid in-kind government obligation by reconciling the statutory debt against actual conveyance records (defined here).
  - `obligation-bypass-legislation` — specific statutes enumerated that diverted assets owed to a beneficiary class toward third parties (defined here).
- **Evidence & sources** (typed):
  - *Statutes*: the 1995 settlement act; the six+ subsequent sale-authorization laws (1999, 2006 Ford Island acts, etc.).
  - *Federal, state and county land records*: parcel-level conveyances, sale prices, grantees (the article states reliance on "federal, state and county records").
  - *Valuations/appraisals*: current-dollar estimates of the outstanding acreage ($39–55M).
  - *Trust accounting*: what DHHL actually received.
  - *Interviews*: officials, beneficiaries.
- **Detection signature**: **Statutory-debt vs. conveyance reconciliation with grantee tracing.** Build a ledger: acres owed (statute) − acres actually conveyed (deed records) = arrears, valued at current appraisal; in parallel, enumerate every federal disposal of nearby/eligible land during the same period and identify grantees — each sale to a church/developer while the trust went unpaid is a diversion entry. The bypass mechanism is pinned to named acts of Congress, not bureaucratic drift.
- **Corroboration structure**: Statute text + deed/parcel records (both primary, mutually independent) + valuation + agency/congressional response; human stakes anchored by the waitlist series data.
- **Methodology notes**: [inferred] from in-article sourcing ("federal, state and county records"); no standalone page for this installment.
- **Generalization**: Reparations/settlement obligations payable in kind (land, water, housing units) anywhere: reconcile the obligation register against the asset-disposal register for the same estate; any disposal to third parties while the obligation is unpaid is the story. Works for military base disposals, school-trust lands, bankruptcy estates, and treaty annuities.
- **Impact (one line)**: Fed the same 2022 $600M legislative response and state scrutiny of DHHL land management (series impact noted on the [series page](https://www.propublica.org/series/promised-land)).

---

## SERIES 5: LESSONS LOST (Bureau of Indian Education)

### The Bureau of Indian Education Hasn't Told the Public How Its Schools Are Performing. So We Did It Instead. (2021) — journalists built the federal school report card the agency was legally required to publish and had suppressed for years

- **URL**: https://www.propublica.org/article/the-bureau-of-indian-information-hasnt-told-the-public-how-its-schools-are-performing (June 9, 2021, Alden Woods/Arizona Republic, Agnel Philip/ProPublica); methodology: ["How We Analyzed the Performance of Bureau of Indian Education Schools"](https://www.propublica.org/article/how-we-analyzed-the-performance-of-bureau-of-indian-education-schools)
- **Partner/awards**: The Arizona Republic, ProPublica Local Reporting Network.
- **What they found**:
  - "The BIE is still required to publish its schools' test scores. It hasn't done so since the 2015-16 school year" — so the reporters computed it: BIE students scored **more than two grade levels below the national average**; over 70% of analyzed schools were 2+ grade levels behind.
  - Nuanced counter-finding: 40%+ of BIE schools showed learning *growth* significantly above the national average, and against Native students in surrounding public districts the gap "shrunk from… two grade levels behind to 0.3 grade levels" — schools are under-resourced more than under-performing.
  - Scale: ~193,000 standardized test scores, grades 3–8, school years 2008-09 through 2016-17/2017-18 (2013–2015 and 2018 excluded for late BIE submissions); the methodology page describes 141 BIE schools in the standardized dataset (the BIE runs 183 schools, ~45,000 students; the main article describes school-level comparisons covering 92 schools).
- **Finding type(s)**:
  - `suppressed-report-reconstruction` — independently rebuilding a legally mandated public report an agency stopped publishing (defined here).
  - `growth-vs-proficiency-decomposition` — separating school effect (growth) from poverty effect (level) so the accountability lands on the right actor (defined here).
- **Evidence & sources** (typed):
  - *Federal education database*: raw score submissions in the U.S. Department of Education's **EDFacts** database — BIE schools' scores existed inside a federal system even though BIE published nothing.
  - *Academic standardization partner*: Stanford's Educational Opportunity Project linked state-specific test scales to **NAEP** benchmarks, making 23 states' different assessments comparable.
  - *Original assessment-mapping legwork*: reporters identified which assessment each BIE school actually administered "through calls with states, schools and tribal education departments" — "data Stanford previously lacked."
  - *Comparison population*: Native American students in surrounding public school district boundaries.
  - *Interviews/agency response*: results shared with BIE and Interior pre-publication.
- **Detection signature**: **Shadow report card via raw-feed standardization.** The agency suppressed the report but not the raw feed: scores flowed into EDFacts regardless. Join EDFacts raw scores → school-to-assessment mapping (hand-built) → Stanford NAEP crosswalk → three metrics (average achievement; grade slope = within-cohort yearly improvement; cohort slope = school-level yearly change; "Grade slope most directly reflects the actual performance" per cited experts). Then run two comparisons — national, and Native peers in adjacent public districts — so the headline (2 grades behind) and the structural excuse-buster (only 0.3 behind local Native peers, faster growth) are both quantified.
- **Corroboration structure**: Federal raw data + independent academic methodology (Stanford) + manual verification of the assessment map with each state/tribe + pre-publication review by the agency; exclusions (high schools; late-submission years) disclosed.
- **Methodology notes**: Stated — dedicated methods page (URL above) covering dataset bounds, exclusions, NAEP linking, weighting ("Stanford-standardized scores, weighted by… student" populations), and the three-metric design.
- **Generalization**: Whenever an agency defunds/suppresses its own mandated reporting, look for the upstream raw feed it still must submit to someone else (federal rollups, court filings, bond disclosures, insurance filings) and rebuild the report; always decompose level vs. growth so deprivation isn't misread as institutional failure. Works for prison education, IHS hospitals, VA facilities, charter authorizers.
- **Impact (one line)**: Provided the first public BIE performance accounting in five years; companion pieces documented COVID tech-promise failures ([Sept 2020](https://www.propublica.org/article/the-federal-government-promised-native-american-students-computers-and-internet-many-are-still-waiting)) and the accountability vacuum ([Aug 2020](https://www.propublica.org/article/the-federal-government-gives-native-students-an-inadequate-education-and-gets-away-with-it)).

---

## SERIES 6: POWER GRAB (green energy vs. tribal cultural resources)

### Washington State Is Leaving Tribal Cultural Resources at the Mercy of Solar Developers (2024) — a state archaeologist found 17 sites in 20 hours that the developer's 800-page paid survey missed; the state sidelined her, not the developer

- **URL**: https://www.propublica.org/article/washington-state-is-leaving-tribal-cultural-resources-at-mercy-of-solar-developers (Jan 19, 2024, B. "Toastie" Oaster/High Country News)
- **Partner/awards**: Co-published with High Country News.
- **What they found**:
  - At Avangrid's Badger Mountain solar project (Colville/Yakama territory), state Department of Natural Resources archaeologist Sara Palmer found **at least 17 archaeological sites during ~20 hours of fieldwork that Tetra Tech's 800-page developer-commissioned survey omitted** — "serious deficiencies," a situation she called "extraordinary."
  - Structural defect: developers hire the archaeologists who survey their own project sites; DNR's leasing head conceded "potential pitfalls" but said the agency "doesn't regulate renewable energy developers" and treats surveys as "a proprietary or business relationship"; Washington's siting council has never stopped a project on cultural-resource grounds ("I've never had EFSEC stop a project on cultural resources — not that I'm aware of").
  - Records show the developer's official demanded to vet agency communications and threatened to relocate the project; DNR notes describe Palmer as having gone "rogue"; a DNR manager documented the official's "combative and provocative" behavior toward female staff — the agency isolated its own experts rather than confront the developer.
  - Scale driver: the 2021 Climate Commitment Act spurred 50+ solar and 12+ wind proposals, mostly on eastern Washington ancestral lands; Colville council member Andy Joseph Jr. estimated the project "would destroy roughly half the root vegetable harvest in the area."
- **Finding type(s)**:
  - `proponent-paid-assessment-undercount` — a regulated party's self-procured expert assessment materially undercounting the impacts it exists to disclose (defined here).
  - `regulatory-capture-by-communication` — records showing an agency policing its own staff's speech at a developer's demand rather than policing the developer (defined here).
  - `green-transition-externality` — climate-policy urgency creating a fast lane that bypasses existing cultural/treaty protections (defined here).
- **Evidence & sources** (typed):
  - *Public-records requests*: text messages between Avangrid's Brian Walsh and Palmer (May 2022); June 2022 emails (vetting demands, relocation threats); December 2022 internal DNR email on Walsh's conduct; handwritten DNR meeting notes ("rogue").
  - *Dueling technical surveys*: Tetra Tech's 800-page cultural survey vs. Palmer's independent field findings (17 sites) — the quantitative core.
  - *Regulatory record*: EFSEC siting-council proceedings; tribal formal objections; DNR and state historic-preservation comments echoing them.
  - *Treaty framework*: harvesting-rights treaties "equivalent to an act of the legislature."
  - *Interviews*: Palmer, tribal archaeologists and leaders (Colville, Yakama, Quinault), DNR and EFSEC officials, an Indigenous-rights attorney.
- **Detection signature**: **Independent-recount diff on a paid assessment.** The finding is a simple subtraction with devastating provenance: (sites found by an independent state expert on the same ground) − (sites disclosed in the proponent-funded survey) = 17-site undercount, achieved in 20 hours against an 800-page product. Public-records requests then reconstructed *why* the undercount survived: correspondence showing developer pressure on the agency and the agency disciplining its expert instead of the survey. Two joined layers: measurement diff + capture-correspondence reconstruction.
- **Corroboration structure**: Independent expert fieldwork → tribal archaeologists' concurrence → agency records against interest (their own notes/emails) → formal objections from two tribes echoed by two state agencies → developer/contractor response sought.
- **Methodology notes**: [inferred] from in-article description; the acquisition channel (state public-records act requests for texts/emails/notes) is stated in the article.
- **Generalization**: Every self-assessment regime: environmental impact statements, bank-hired appraisers, sponsor-run clinical trials, employer-paid workplace investigations. Generic detector: obtain any independent measurement of the same object (state expert, second lab, spot audit) and diff it against the paid assessment; then pull agency-developer correspondence for evidence the referee was moved rather than the player.
- **Impact (one line)**: EFSEC commissioned its first independent cultural survey in at least a decade (Oct 2023) — "agency leaders do not recall ever previously commissioning an independent cultural survey" — the state paused the project amid cultural-site concerns ([Aug 2024 follow-up](https://www.propublica.org/article/washington-badger-mountain-solar-native-cultural-sites)), and the Yakama Nation barred Tetra Tech from future work on its lands.

---

## Cluster Synthesis

### 1. Recurring evidence-source types (frequency across the 11 extractions)

| Evidence class | Freq | Where |
|---|---|---|
| **Federal program/administrative databases** (National NAGPRA inventories, EDFacts scores, Bureau of Reclamation water accounting, NSF grant records) | 6 | Repatriation flagship, destructive research, BIE, Chemehuevi, hatcheries (benchmark), land debt |
| **Agency internal records via FOIA / state public-records acts** (EPA memos, DNR texts/emails/notes, AZ DWR communications, BPA strategy docs) | 5 | Toxic fish, Power Grab, Arizona water, Bonneville, Harvard (institutional correspondence) |
| **Historical/archival primary documents** (museum accession registers + 1895 annual report, 1891 Army letters, 1873 Smithsonian letter, 1947 Interior "must be sacrificed" memo, 1973 National Water Commission report, treaty texts, 1921 Act) | 6 | AMNH, flagship, hatcheries, Chemehuevi, Arizona, Promised Land |
| **Structured interview campaigns at population scale** (100+ NAGPRA interviews; officials from 20 of 30 basin tribes; tribal consultation on the database pre-launch) | 11 | all |
| **Legal-notice streams as data** (Federal Register inventory-completion notices) | 2 | flagship database, how-to guide |
| **Court/adjudication records** (Winters, Arizona v. Navajo, 1960s decrees, settlement corpus) | 3 | Arizona, Chemehuevi, flagship context |
| **Scientific unit-level tracking data from academic custodians** (UW PIT-tag detections; Stanford NAEP crosswalk) | 2 | hatcheries, BIE |
| **Journalist-commissioned laboratory measurement** (50 fish, certified lab) | 1 | toxic fish |
| **Land/lease/transaction registers** (DHHL applicant+lease logs; federal/state/county deeds) | 2 | Promised Land flagship, land debt |
| **Dueling expert assessments** (developer survey vs. state archaeologist recount; Fish Passage Center vs. BPA spill claims) | 2 | Power Grab, Bonneville |
| **Hearing/advisory-committee transcripts** (30 yrs of NAGPRA Review Committee; 2015 hearing) | 2 | flagship, Harvard |
| **Scientific literature as a provenance trail** (papers naming sampled specimens) | 2 | destructive research, Harvard (Wheeler-Newsom) |

The cluster's most distinctive classes — confirmed as the census predicted — are (a) NAGPRA inventories + Federal Register notices as a *joinable compliance ledger*, (b) treaty/trust-obligation documents used as the *benchmark* rather than background, (c) BIA/BIE records reachable only through upstream federal rollups, (d) water-rights decrees vs. Reclamation delivery accounting, and (e) museum accession registers as atrocity-provenance evidence. No other ProPublica cluster produces these.

### 2. Recurring detection signatures (my tags, frequency)

| Signature | Freq | Instances |
|---|---|---|
| **Mandate-vs-performance census** (join a legal duty to entity-level self-reports; rank; percent-complete) | 3 | NAGPRA database; BIE shadow report card; water-settlement census |
| **Paper-entitlement vs. physical-delivery diff** (right on ledger A, delivery on ledger B, quantify residual, trace who captures it) | 4 | Chemehuevi water; Hawaiian land debt; homestead waitlist (land promised vs. delivered); BIE tech promise |
| **Money-vs-outcome computation** (spend ÷ outcomes against the program's own benchmark) | 3 | hatcheries cost-per-fish + 4% benchmark; Bonneville surplus-vs-fish-budget; repatriation preservation-vs-repatriation funding |
| **Internal-correspondence conduct reconstruction** (records against interest ordered on a timeline vs. public statements) | 4 | Harvard; Power Grab; Bonneville; Arizona (DWR comms) |
| **Provenance chain tracing** (object/specimen-level joins across registries and events) | 2 | AMNH accession-to-atrocity; destructive-research specimen tracing |
| **Independent-recount diff on self-assessed data** (re-measure what the regulated party measured) | 2 | Power Grab 17-site diff; toxic fish (re-measuring what regulators didn't) |
| **Queue forensics** (application-log × award-log join + demographic overlay + mortality scan) | 1 | Promised Land (the cluster's single most replicable database method) |
| **Pipeline-stage precision** (defining exactly which stage of a legal process a metric measures — "made available" ≠ "returned") | 2 | NAGPRA database; water settlements (settled ≠ wet water) |
| **Classification-as-evasion detection** (same item classified differently by different institutions; category used to escape duty) | 2 | "culturally unidentifiable"; conflicting county-level affiliation decisions (how-to guide) |
| **Measurement-chaos-as-finding** (absence of a standard success metric reported as the accountability defect) | 2 | How Not to Count Salmon; toxic fish testing-coverage gap |

### 3. Transferable pattern candidates

**Pattern 1 — Trust-Obligation Compliance Census.**
When a law imposes a duty on many decentralized institutions and the compliance data is self-reported to a registry no one reads, build the scorecard the government won't: join the registry's entity-level inventory to the legal-notice stream that marks completion (Federal Register notices, closure filings, discharge notices), compute percent-complete per entity, rank, and interrogate the entities that classify their way out (NAGPRA's "culturally unidentifiable"). Crucial discipline: measure the precisely defined legal stage, publish numbers as floors, and pre-validate the tool with the affected community. *Minimum data*: statute text; entity-level self-reports; a completion-event stream; entity identifiers stable enough to join. *Recognition cue in any domain*: a decades-old mandate + a federal office that "administers" it + no public entity-level accounting + a penalty total that fits on a lunch receipt ($59,111.34 in 33 years). Applies to: consent decrees, ADA transition plans, mine reclamation, hospital community-benefit, pension funding, looted-art registries.

**Pattern 2 — Paper Rights, No Pipes (entitlement-delivery gap with beneficiary capture).**
A right exists in a decree/statute; the physical or financial delivery mechanism was never funded; the undelivered benefit flows silently to a better-connected third party at zero price. Detect by two-ledger reconciliation: entitlement register (decrees, settlement acts, allotments) vs. operational delivery accounting (diversion records, conveyance deeds, disbursement logs) per rights-holder; quantify the residual; then trace hydrology/contracts/deeds to name who consumes it. The infrastructure-funding asymmetry (canal built for cities, no pump for the tribe) is the mechanism paragraph. *Minimum data*: quantified entitlements; delivery/usage records; enough network data to identify the residual's consumer. *Recognition cue*: utilization ≈ 0% by the rights-holder + no complaint from anyone else (silence of the beneficiaries of the gap). Applies to: royalties, restitution, water, spectrum, housing subsidies, treaty annuities, carbon-credit revenue sharing.

**Pattern 3 — Queue Forensics (who actually gets to the front of a benefit line).**
Any waitlist program: obtain the applicant log and the award log; join on person + date keys; compute wait durations; geocode awardees and overlay census income/demographics to test whether winners resemble the intended beneficiary class; scan status fields for death markers to count mortality-in-queue; and look for evidence the agency skips list order ("going thousands deep") because an unlegislated requirement (mortgage qualification) is the real filter. *Minimum data*: two administrative logs with a linkage key; addresses; a census overlay. *Recognition cue*: a program "for the poor" whose product requires private financing; award counts in single digits some years against a five-figure list. Applies to: public housing, organ transplant, visas, disability claims, veterans' benefits, land restitution anywhere.

**Pattern 4 — Shadow Report Card (rebuild the suppressed mandated report from upstream raw feeds).**
Agencies can stop publishing but rarely stop submitting: raw data usually still flows into some federal rollup, court filing, or funder database. Rebuild the mandated report from the upstream feed, borrowing academic standardization to make heterogeneous units comparable (NAEP crosswalk), and always decompose *level* vs. *growth* so poverty isn't misattributed as institutional failure — which also protects the analysis from the agency's likeliest rebuttal. *Minimum data*: the upstream raw feed; a crosswalk/standardization method; a defensible comparison population (nearest peers, not just national average). *Recognition cue*: "required to publish X; last published X five years ago." Applies to: prison programs, IHS/VA facilities, charter schools, police early-warning systems, nursing-home inspections.

**Pattern 5 — Independent Recount of a Proponent-Paid Assessment.**
Wherever the regulated party procures its own expert assessment (cultural survey, EIS, appraisal, audit, trial), the detector is a recount: get any independent measurement of the same object — a state specialist's fieldwork, a commissioned lab, a second survey — and publish the diff (17 omitted sites; contaminant levels above the agencies' own thresholds). Then FOIA the correspondence triangle (developer / agency / in-house expert) to show whether the referee was moved rather than the play called back; agency notes disparaging their own expert ("rogue") are the capture signature. *Minimum data*: the paid assessment; one independent measurement channel; correspondence via records acts. *Recognition cue*: an approval pipeline where no project has ever been stopped on the ground the assessment covers. Applies to: environmental review, mortgage appraisal, sponsor-run clinical research, workplace investigations, credit ratings.

**Cross-cutting observation for detector design**: this cluster's stories almost never rest on leaks. The load-bearing evidence is (1) the government's own registries joined in ways the government declines to, (2) records-act correspondence, (3) archival primary documents establishing the promise, and (4) occasionally journalist-generated measurement. The common deep structure is **promise-ledger vs. performance-ledger**: a treaty/statute/decree/grant creates a written, quantified promise; a separate operational system records what actually happened; the investigation is the join, and tribal/beneficiary testimony supplies the human verification layer that self-reported data cannot. A generic detector for this whole cluster: inventory every quantified standing obligation to a defined beneficiary class in a jurisdiction, locate the operational dataset that would show performance, and compute the reconciliation — flagging both the gap and (critically) whoever is quietly consuming it.
