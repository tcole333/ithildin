# ProPublica Evidence Ontology — Cluster 07: Government Spending, Contracting, Disaster & Public Funds

Reviewed: 2026-07-28. Scope: ProPublica originals and formal co-publications on public money — disaster relief and charity accountability, emergency procurement, pandemic relief lending, place-based tax subsidies, block-grant welfare spending, military readiness spending, land/records-driven public-aid exclusion, inaugural nonprofit funds, and bailout tracking infrastructure. 12 entries.

**Attribution boundaries verified (corrections to candidate list):**
- **Mississippi TANF/Favre** is Mississippi Today's work (Anna Wolfe, "The Backchannel"), not ProPublica's. Excluded. ProPublica's own TANF franchise is Eli Hager's "Welfare States" work (entry 9).
- **Project Airbridge opacity** was primarily AP reporting plus the Warren/Schumer/Blumenthal congressional investigation and a later DHS OIG report (OIG-23-14). ProPublica's own flagship in the same space is the White House-directed no-bid AirBoss contract (entry 5) and the Coronavirus Contracts database (entry 3). No dedicated ProPublica Airbridge exposé found.
- **The "Nevada zone" opportunity-zone story** (Storey County / Milken / Mnuchin) was The New York Times, not ProPublica. ProPublica's verified OZ cases are Port Covington (mapping error + lobbying), the Rybovich superyacht marina (donor appeal to Gov. Rick Scott), and Dan Gilbert's downtown Detroit tracts (White House coordination). Entries 7–8.

---

### The Red Cross' Secret Disaster (2014) — America's premier disaster charity botched Sandy/Isaac relief while diverting resources to public relations
- **URL**: https://www.propublica.org/article/the-red-cross-secret-disaster
- **Partner/awards**: Co-reported with NPR (Justin Elliott and Jesse Eisinger, ProPublica; Laura Sullivan, NPR).
- **What they found** (published Oct. 29, 2014):
  - During Hurricane Isaac (2012), supervisors ordered ~80 trucks and emergency response vehicles — normally full of meals, diapers, bleach — to be driven around **empty**, to project activity.
  - At the peak of the Sandy crisis (Nov. 2012), an internal account said **15 emergency response vehicles were assigned to public-relations duties** — roughly **40% of available ERVs** in the New York area — including serving as backdrops for press conferences, while survivors lacked food and water.
  - Roughly **3 of every 10 meals** prepared were wasted; about **half of 70,000 Danishes** were discarded for lack of distribution planning; shelter staff failed to follow sex-offender procedures.
  - CEO Gail McGovern publicly called the Sandy response "near flawless" two weeks in; the charity's own internal review concluded "Multiple systems failed" and flagged diverting assets for PR purposes.
- **Finding type(s)**: two-books-asymmetry; charity-mission-inversion; institutional-coverup/records-suppression
- **Evidence & sources**: [privileged/leaked] Confidential internal "Lessons Learned" PowerPoint and minutes of a closed-door December 2012 after-action meeting of top officials; [privileged/insider] Internal emails; accounts from current and former disaster-relief specialists; [interviews] Responders on the ground; [open-public] Red Cross public statements and fundraising claims — the comparison corpus.
- **Access tier**: mixed — privileged (leaked internal after-action documents) + interviews; public-claims side open-public.
- **Acquisition path**: leak + interviews.
- **Detection signature**: **two-books-diff** — internal after-action assessments (leaked slide decks, meeting minutes) diffed against contemporaneous public executive statements *on the same operational metrics* (vehicles deployed, meals served, response quality) revealed resources systematically reallocated from relief to PR. Trigger artifact: the org's own internal metric ("40% of ERVs on PR duty") contradicting the "near flawless" public line.
- **Corroboration structure**: internal documents corroborated by multiple independent insider interviews across two disasters (Isaac/Louisiana, Sandy/NY-NJ), then put to the Red Cross on record; denials printed against the documentary record.
- **Methodology notes**: No formal "How We Did This" page; IRE interview describes documents-first sourcing then widening insider interviews [inferred].
- **Generalization**: Any large relief/aid organization (or agency) running both external communications and internal after-action review generates two-books artifacts. Generic detector: internal after-action/lessons-learned documents, board minutes, or consultant assessments whose KPIs pair 1:1 with public claims; resource-allocation records (vehicle assignments, rosters) showing PR units drawing operational assets during the response window.

---

### How the Red Cross Raised Half a Billion Dollars for Haiti — and Built Six Homes (2015) — headline output claims collapsed on ground-truthing; "91 cents on the dollar" concealed stacked pass-through fees
- **URL**: https://www.propublica.org/article/how-the-red-cross-raised-half-a-billion-dollars-for-haiti-and-built-6-homes
- **Partner/awards**: Co-reported with NPR (Justin Elliott; Laura Sullivan), June 3, 2015.
- **What they found**:
  - Raised **~$488 million** for Haiti post-2010 earthquake; claimed it "provided homes" to **more than 130,000 people**; permanent homes actually built: **six**. Flagship Campeche/LAMIKA neighborhood project produced zero new homes.
  - The "91 cents of every dollar" claim masked **fee stacking through re-granting**: Red Cross 9% overhead, partner orgs' own cut (26% overhead/admin on one $6M IFRC rental-subsidy project), plus additional Red Cross "program management" (24% on one $5.4M shelter project).
  - Internal March 2014 evaluation found projects made "no contributions of any sort to the well being of households"; confidential 2011 memo by Haiti program director Judith St. Fort documented failed results; April 2012 org chart showed 9 of 30 leadership posts vacant; expats cost ~3x Haitian staff ($140K vs. $42K comparable roles).
  - CEO-level emails (McGovern/Meltzer, Nov. 2013) discussed a "wonderful helicopter idea" while delivery stalled.
- **Finding type(s)**: charity-mission-inversion; two-books-asymmetry; **pass-through-fee-stacking** (new tag); institutional-coverup/records-suppression (refused project-level budgets and site visits)
- **Evidence & sources**: [privileged/leaked] Internal memos, confidential evaluations, org charts, executive emails, delayed strategic plans; [interviews] A dozen+ current/former officials; Haitian officials (former PM Bellerive challenged the 130,000 figure); [field-observation] On-ground reporting in Campeche; [open-public] Red Cross public reports and published ratios.
- **Access tier**: mixed — privileged + constructed (on-ground verification) + open-public.
- **Acquisition path**: leak + interviews + field-observation.
- **Detection signature**: **ground-truth-vs-claimed-output** joined with **pass-through-fee-stacking arithmetic** — take the public output claim (130,000 people housed) and efficiency claim (91%), then (a) physically enumerate the deliverable (homes = 6) and (b) reconstruct the money path project-by-project through each intermediary's own overhead; compounding per-layer fees falsifies the headline ratio without a single smoking-gun document.
- **Corroboration structure**: leaked internal evaluations ↔ on-ground observation ↔ insider interviews ↔ the org's own public numbers; refusals (budgets, site visits) documented as part of the finding.
- **Methodology notes**: No formal methods page; fee-stacking reconstruction described in-article with named example projects (stated).
- **Impact**: Sen. Grassley's year-long investigation concluded (June 2016) the Red Cross spent **~$124–125M (25%) of Haiti donations on internal expenses** and "stonewalled" congressional investigators.
- **Generalization**: Any grant chain with re-granting intermediaries — disaster philanthropy, USAID implementers, UN pass-throughs, block-grant subrecipients. Generic detector: multiply per-layer admin rates along the actual subaward chain (990 Schedule I, subaward data, audited financials); compare cumulative extraction vs. headline efficiency; separately demand and count a physical deliverable. Our 990/trace-grants tooling can compute chain-cumulative overhead today.

---

### COVID-19 contracting: first-time-vendor mining + the Coronavirus Contracts database (2020) — $1.8B+ in pandemic deals to contractors with no federal track record, majority no-bid
- **URL**: https://www.propublica.org/article/a-closer-look-at-federal-covid-contractors-reveals-inexperience-fraud-accusations-and-a-weapons-dealer-operating-out-of-someones-house (May 27, 2020); database: https://projects.propublica.org/coronavirus-contracts/
- **Partner/awards**: Gabrielson, DePillis, McSwane, Willis (ProPublica) with Connor Sheets (AL.com); database by Moiz Syed and Derek Willis. McSwane's book "Pandemic, Inc." grew from this work.
- **What they found**:
  - ~**345 first-time federal contractors** promised **at least $1.8 billion** from March 2020 — ~13% of $13.8B in pandemic contracting at that date.
  - **51% of first-time-contractor deals awarded without competition**, vs. 32% of pandemic contracts overall.
  - Case studies surfaced by the flag: Bayhill Defense ($14.5M VA mask deal, failed, canceled — a weapons dealer operating from a residence), Fillakit ($10.5M), Aunt Flow ($14.7M, undelivered), Medea Inc. ($48.8M FEMA mask deal).
  - The public database tracks **$39.9B across 18,243 contracts from 8,266 vendors**, flagging vendor type, agency, amount, description, and **4,098 sole-source contracts**.
- **Finding type(s)**: anomalous-vendor; fraud-enablement-by-design (urgency authorities suspending competition created the opening)
- **Evidence & sources**: [open-public] FPDS procurement microdata ("all contracts tagged with the procurement code for COVID-19 or otherwise started in 2020 and containing 'COVID-19' in the description"; $10K+ threshold; 90-day DoD reporting delay noted); [open-public] State incorporation records (formation dates); litigation history of principals; [interviews] Vendors, agency spokespeople, former procurement officials.
- **Access tier**: open-public, with interview layering.
- **Acquisition path**: bulk-public-data + interviews.
- **Detection signature**: **first-time-vendor flag** — join the COVID-tagged FPDS award stream to each vendor's full FPDS history; zero-prior-award vendors flagged; cross-tab with **no-competition flag** and award size; then per flagged vendor run **entity-age-vs-award-diff** (registry incorporation date vs. award date) and principal-history checks (FTC/SEC/courts). The anomaly set becomes the story list.
- **Corroboration structure**: data flag → registry/court verification of vendor substance → direct vendor/agency contact → contract outcome tracking. Official watchdog later validated the pattern: PRAC found **$4.4B (16%) of $28B** in Apr–Sep 2020 pandemic contracts went to first-time federal contractors.
- **Methodology notes**: Database about-text quoted above (stated); flagging logic described in articles (stated); exact FPDS query mechanics [inferred: National Interest Action code + description text match].
- **Impact**: Rep. Raskin and colleagues requested a PRAC investigation citing the reporting; contract cancellations; House Select Subcommittee letters to vendors.
- **Generalization**: The canonical anomalous-vendor pipeline for ANY emergency-spending universe. Minimum data: award feed with vendor identifier + award date + competition code; vendor prior-award history; registry formation dates. Our USASpending/FPDS/SAM tooling reproduces every step; "first-seen UEI ≈ award date + sole-source + out-of-category product" should be a named standard screen.

---

### Fillakit: millions for test tubes, unusable mini soda bottles delivered (2020) — a 6-day-old LLC run by a man with an FTC fraud judgment won $10.5M from FEMA
- **URL**: https://www.propublica.org/article/the-trump-administration-paid-millions-for-test-tubes-and-got-unusable-mini-soda-bottles (June 18, 2020)
- **Partner/awards**: J. David McSwane and Ryan Gabrielson, ProPublica.
- **What they found**:
  - Fillakit LLC **formed May 1, 2020**; FEMA signed **May 7** — three deals totaling **$10.5M** for 4M specimen tubes; **$7.3M paid** for 3M+ tubes delivered.
  - Owner Paul Wexler had a 2012 FTC case (illegal robocalling, unauthorized charges, posing as a nonprofit credit counselor) settled with a **$2.7M judgment** — banning him from debt-relief services but not federal contracting.
  - The "tubes" were soda-bottle **preforms** that don't fit lab racks, filled with saline (not FDA-validated transport medium). Reporters observed workers **shoveling tubes with snow shovels**, open saline trays next to fans, no masks, loading into an unrefrigerated rental truck.
  - States confirmed unusability (NY, NJ, TX, NM); Washington received 76,000 unusable vials; Texas shelved 140,000; FEMA later warned states not to use the $10.2M in kits.
- **Finding type(s)**: anomalous-vendor; fraud-enablement-by-design (urgency authorities + no debarment linkage to consumer-fraud history)
- **Evidence & sources**: [open-public] FPDS contract records (incl. the vendor phone number that resolved to Wexler); Texas incorporation records; FTC litigation records; [constructed/field-observation] Warehouse site visit; worker interviews on site; [interviews] State health officials (usability), former employees, Wexler.
- **Access tier**: mixed — open-public + constructed.
- **Acquisition path**: bulk-public-data → field-observation → interviews.
- **Detection signature**: **entity-age-vs-award-diff** at its purest — registry formation date minus FPDS award date = **6 days**; then **selector pivot on contract metadata** (contact phone in federal data resolved the true principal, unlocking his FTC history); then physical verification of production capacity. The diff was the flag; the metadata pivot found the accountable human.
- **Corroboration structure**: procurement record → registry → principal litigation history → eyewitness field verification → state-lab confirmation of unusability → FEMA warning as capstone.
- **Methodology notes**: Article states the lead came from ProPublica's first-time-contractor procurement analysis (stated).
- **Impact**: House Select Subcommittee (Clyburn) letter to Fillakit (July 14, 2020); Sens. Peters/Stabenow pressed FEMA; a DHS special agent contacted employees per ProPublica; state testing rollouts delayed. (No Texas AG suit verified — dropped from candidate claims.)
- **Generalization**: Emergencies attract shelf companies whose principals' enforcement history sits in a *different* regulator's database than procurement checks. Generic detector: formation-vs-award < 90 days; principal resolution via contract metadata (phone/email/address) into FTC/SEC/state-AG/court records; NAICS/product mismatch with principal's prior businesses. All three run on data our platform already holds.

---

### The White House Pushed FEMA to Give Its Biggest Coronavirus Contract to a Company That Never Had to Bid (2020) — a $96M PAPR deal "ordered by the White House," recorded in the contract file itself
- **URL**: https://www.propublica.org/article/the-white-house-pushed-fema-to-give-its-biggest-coronavirus-contract-to-a-company-that-never-had-to-bid (April 10, 2020)
- **Partner/awards**: J. David McSwane and Yeganeh Torbati, ProPublica.
- **What they found**:
  - AirBoss of America (via subsidiary Immediate Response Technologies) received a **$96M no-bid contract** for 100,000 powered air-purifying respirators for New York — the largest of **$760M** in pandemic no-bid deals at that point, and two-thirds of FEMA's $140M COVID spending through April 8.
  - The procurement paper trail recorded the political direction: FEMA said "The company's proposal/offer was submitted by a White House task force," and a contracting officer noted in the government database the buy was **"ordered by the White House."**
  - Trade adviser Peter Navarro publicly championed the deal; AirBoss stock roughly doubled within a week.
  - Former FEMA deputy administrator Tim Manning: "I can't think of an example of the White House sending FEMA a directive to procure items from a particular company in a particular manner."
- **Finding type(s)**: preferential-carve-out (competition bypassed for one firm); anomalous-vendor (adjacent — selection by political channel, not market test)
- **Evidence & sources**: [open-public] FPDS contract records including **free-text justification/notes fields**; market data (stock move); White House releases; [interviews] FEMA statements, former FEMA officials, procurement experts.
- **Access tier**: open-public + interviews.
- **Acquisition path**: bulk-public-data + interviews.
- **Detection signature**: **procurement-justification-text-mining** (new tag) — rank no-bid awards by size within the emergency universe, then read the human-written fields (justification & approval text, contracting-officer remarks); the phrase "ordered by the White House" in a structured procurement record was the finding. Secondary: **temporal-correlation** between political endorsement and vendor stock move.
- **Corroboration structure**: database free-text → agency on-record confirmation → expert normalization testimony (former officials establishing the deviation) → market reaction as independent signal.
- **Methodology notes**: [inferred] Derived from the same FPDS COVID-monitoring pipeline as the database entry.
- **Impact**: Fed congressional oversight of pandemic procurement; part of the record for later PRAC/GAO reviews of noncompetitive awards.
- **Generalization**: Free-text fields in procurement systems (J&A documents, "other than full and open competition" rationales, CO notes) are an under-mined confession layer. Generic detector: for any sole-source award above threshold, extract and classify justification text; flag references to direction from outside the contracting agency, named intermediaries, or urgency citations paired with first-time vendors. Our FPDS/USASpending tools should systematically pull description + justification fields, not just amounts.

---

### Hundreds of PPP Loans Went to Fake Farms in Absurd Places (2021) — lender-side fraud enablement: Kabbage approved 378 loans to nonexistent single-person "farms," most at the exact program cap
- **URL**: https://www.propublica.org/article/ppp-farms (May 18, 2021)
- **Partner/awards**: Derek Willis and Lydia DePillis, ProPublica.
- **What they found**:
  - **378 loans totaling $7M** to fake business entities — nearly all "farms," nearly all **sole proprietorships at ~$20,833**, the exact category maximum; 60+ in New Jersey alone; all through **Kabbage**.
  - Absurdity-by-geography: "Deely Nuts" (tree-nut farm) and "Beefy King" (cattle ranch) at the Jersey Shore — Beefy King registered to the home address of Long Beach Township's mayor; a potato farm in Palm Beach; an orange grove in Minnesota; "Tomato Cramber" ($12,739), Brielle, NJ.
  - Lender-side enablement: Kabbage processed ~300,000 PPP loans in round one (second only to Bank of America), auto-approved **75% of applications with no human review**, paid surge processors escalating wages plus gift-card bonuses keyed to volume; per later congressional findings, at one point a single full-time anti-fraud employee. Former reviewer: "They weren't saying, 'Is this legitimate?' They were just saying, 'Are all the fields filled out?'"
  - Structural incentive: per-loan origination fees with a government guarantee + pending American Express acquisition rewarded volume over verification.
- **Finding type(s)**: fraud-enablement-by-design; anomalous-vendor (borrower side); **benefit-cap-clustering** (new tag); **category-geography-implausibility** (new tag)
- **Evidence & sources**: [request-gated] SBA loan-level PPP microdata **released via FOIA litigation** by news organizations; [open-public] State business-entity registries (existence checks); licensing databases; address/property records; [interviews] Former Kabbage employees/executives; named "borrowers" (identity-use victims); the mayor; [litigation-records] DOJ prosecutions referencing Kabbage-originated loans.
- **Access tier**: mixed — request-gated (FOIA-litigated SBA data) + open-public + interviews.
- **Acquisition path**: FOIA (litigated bulk release) → bulk-public-data joins → interviews.
- **Detection signature**: layered: (1) **benefit-cap-clustering** — flag mass points exactly at the sole-proprietor maximum ($20,833); (2) **category-geography-implausibility** — industry label ("cattle ranch") joined to geography (barrier island) flags impossible businesses; (3) **silo-join-on-hard-identifier** — borrower name/address joined to state registries returned *no registered entity*; address clustering surfaced multiple "farms" at single residential addresses; (4) **single-originator-concentration** — every flagged loan traced to one lender, converting a borrower-fraud story into a lender-design story.
- **Corroboration structure**: data anomaly → registry nonexistence → doorstep/phone verification with named address-holders → insider interviews on review process → congressional documents later confirming internal control failures.
- **Methodology notes**: Detection approach described in-article (SBA FOIA data compared against state registration records) (stated).
- **Impact**: House Select Subcommittee opened a Kabbage/BlueVine fintech probe days after publication; its Dec. 2022 report found fintechs took "massive profits" while abdicating fraud controls; DOJ cases cited ~$2.74M in Kabbage-originated fraudulent loans; SBA IG estimated tens of thousands of ineligible approvals program-wide.
- **Generalization**: Any high-velocity relief/lending program where originators earn per-transaction fees against a government guarantee. Minimum data: recipient-level microdata (name, address, amount, category, originator). Agent screen: (a) histogram spikes exactly at category maxima; (b) recipient nonexistence in the relevant registry; (c) address multiplicity incl. non-commercial addresses; (d) originator-conditional fraud rate — the outlier lender is the systemic story. NOTE: the "hundreds of loans to a single Chicago address" analysis was Chicago Sun-Times/BGA (2023), not ProPublica.

---

### One Trump Tax Cut Was Meant to Help the Poor. A Billionaire Ended Up Winning Big. — Port Covington opportunity zone (2019) — a wealthy, 4%-Black waterfront tract became "low-income" via a mapping error and lobbying
- **URL**: https://www.propublica.org/article/trump-inc-podcast-one-trump-tax-cut-meant-to-help-the-poor-a-billionaire-ended-up-winning-big (June 19, 2019)
- **Partner/awards**: Jeff Ernsthausen and Justin Elliott, ProPublica, with WNYC's "Trump, Inc." podcast.
- **What they found**:
  - Port Covington — the Baltimore waterfront district anchored by Under Armour CEO Kevin Plank's $5.5B development, backed by Goldman Sachs — was designated an Opportunity Zone despite being too wealthy to qualify. Gov. Hogan's deputy chief of staff had written **"Port Covington does not qualify."**
  - It became eligible only through a **digital mapping error** (stale Census layer misclassifying contiguity); actual overlap with the qualifying neighbor tract was ~**0.001 sq mi — under 0.3%**. Treasury quietly added it on a **revised** eligible-tract list.
  - Weeks after the tax law passed, Plank's Annapolis lobbyist **Nick Manis** contacted Hogan's chief of staff about Port Covington (emails obtained by ProPublica). Hogan designated it — while declining three Baltimore-recommended neighborhoods that are **68% Black with 3x the poverty rate** (Port Covington's tract: 4% Black).
- **Finding type(s)**: preferential-carve-out; beneficiary-reverse-engineering as story architecture
- **Evidence & sources**: [open-public] Treasury initial vs. revised eligible-tract lists; Census/ACS tract demographics; GIS boundary layers (old vs. new Census maps); [request-gated] Maryland governor's-office emails via state public-records law; [interviews] State officials, program designers, city leaders whose tracts were passed over.
- **Access tier**: mixed — open-public (lists, GIS, Census) + request-gated (state PRA emails).
- **Acquisition path**: bulk-public-data + FOIA/state-records + interviews.
- **Detection signature**: **designation-list-diff + eligibility-recompute** (new tags) — diff initial vs. revised official designation lists to find quiet insertions; for each insertion, recompute eligibility from primary Census data (income, poverty, contiguity); GIS-measure the claimed contiguity (0.3% sliver). Emails then supplied intent (**temporal-correlation**: lobbyist outreach → designation).
- **Corroboration structure**: geometric/statistical proof of ineligibility (irrefutable, from public data) under documentary proof of lobbying (records request) and the state's own internal admission; excluded poorer tracts quantified for contrast.
- **Methodology notes**: Map-forensics reasoning laid out in-article (stated: which Census vintage produced the phantom overlap); [inferred] GIS overlay analysis by Ernsthausen.
- **Generalization**: Every place-based subsidy (OZ, empowerment zones, TIF, enterprise zones, NMTC, EB-5 TEAs) has an official designation list, objective criteria, and a lobbyable designation authority. Generic detector: recompute eligibility for every designated unit from primary data; diff list versions over time; for failures/insertions, pull designation-authority correspondence and match property ownership around the boundary.

---

### Donor-driven Opportunity Zone designations: the superyacht marina and Dan Gilbert's Detroit (2019) — designations followed direct appeals from billionaire beneficiaries; ineligible tracts added on revision
- **URL**: https://www.propublica.org/article/superyacht-marina-west-palm-beach-opportunity-zone-trump-tax-break-to-help-the-poor-went-to-a-rich-gop-donor (Nov. 14, 2019); https://www.propublica.org/article/how-a-tax-break-to-help-the-poor-went-to-nba-owner-dan-gilbert (Oct. 24, 2019)
- **What they found**:
  - **Marina (FL)**: Then-Gov. Rick Scott designated the tract containing the Rybovich superyacht marina (Wayne Huizenga Jr.'s Marina Village luxury project) about **a week after Huizenga's direct written appeal**; Florida's own poverty/unemployment analysis had not slated the tract; Scott simultaneously rejected poorer tracts West Palm Beach requested. Documented in Florida DEO records obtained by ProPublica.
  - **Detroit (MI)**: Three downtown tracts dominated by Dan Gilbert (~$3B in property) were designated after his team "worked with the White House on it" (state economic-development official's email); **less than two weeks later Treasury revised its eligible-tract list** to include a Gilbert tract that **did not meet the poverty requirements**; Quicken's top lobbyist's name appears on the city's OZ recommendation map.
- **Finding type(s)**: preferential-carve-out; self-dealing/related-party (designation authority acting for a donor); temporal-correlation as proof structure
- **Evidence & sources**: [request-gated] State agency records: Florida DEO designation files incl. the Huizenga letter; Michigan economic-development emails; [open-public] Treasury tract-list versions; Census poverty data; property ownership mapping Gilbert's holdings to tracts; campaign-finance records (donor status); [interviews] State and city officials; program architects.
- **Access tier**: mixed — request-gated (state FOIA) + open-public.
- **Acquisition path**: FOIA/state-records + bulk-public-data + interviews.
- **Detection signature**: **beneficiary-reverse-engineering** — start from the designated tract, identify who owns the land inside it (property records → LLC resolution), check donor/relationship status, then pull designation-authority correspondence and build the timeline: *appeal date → designation date* (FL: ~8 days) and *coordination email → revised federal list adding an ineligible tract* (MI: <2 weeks). **Eligibility-recompute** flags the Detroit tract as failing poverty criteria.
- **Corroboration structure**: ownership + donor status (public data) × correspondence (records request) × timing (documents' own dates) × counterfactual (poorer tracts rejected in the same window) — each leg independently sourced.
- **Impact**: Senate Finance ranking member Wyden and House W&M chairman Neal opened an OZ abuse investigation citing the reporting wave (Nov. 6, 2019); Wyden OZ reform legislation; Treasury OIG review of designation deviations followed.
- **Generalization**: Work backward from the subsidy's geography to its landowners. Minimum data: boundary shapefiles, parcel ownership with LLC resolution, donor/lobbying records, designation correspondence. Agent screen for any geographic subsidy: rank designated units by single-owner land-value concentration, then check eligibility arithmetic and correspondence timing. Our property + FEC + registry tooling covers all legs.

---

### "Welfare States": TANF block-grant diversion in the Southwest (2021–2023) — states spend federal cash-assistance money on child-removal agencies, church-credited charity, and budget backfill
- **URL**: https://www.propublica.org/article/the-cruel-failure-of-welfare-reform-in-the-southwest (Dec. 30, 2021); impact piece: https://www.propublica.org/article/tanf-welfare-biden-proposal-state-spending-low-income-families
- **Partner/awards**: Eli Hager, ProPublica (Southwest pieces co-published with regional outlets).
- **What they found**:
  - **Arizona diverts $150M+ per year of TANF funds to its Department of Child Safety** — the agency that investigates and separates poor families — plus ~$120M more to foster care/adoption/group homes. Signature case: a mother sought cash help; the state instead used welfare-funded caseworkers to investigate her and take her son.
  - **Utah counted LDS Church charitable work as state welfare spending** via a private arrangement, avoiding **$75M+** in state spending over a decade (maintenance-of-effort gaming).
  - Nationally, **$1.7B in child support (2020) collected from fathers of TANF families was kept by governments** rather than passed to children — cost recovery baked into program design.
  - Denominators: caseload fell 4.4M families (1996) → ~1M; TANF spending per poor child ranges **$63 (Nevada) to $409 (California)**; Nevada child poverty roughly doubled 1997–2015.
- **Finding type(s)**: fraud-enablement-by-design (block-grant flexibility invites legal diversion); charity-mission-inversion (state-level analog); **block-grant-diversion-accounting** (new tag); extraction-from-captive-population (child-support interception)
- **Evidence & sources**: [open-public] State TANF expenditure reports filed to HHS/ACF (category-level spending); state budget documents showing backfill; HHS caseload statistics; Census poverty series; Urban Institute / Niskanen analyses as secondary checks; [interviews] Affected families, state officials, former administrators.
- **Access tier**: open-public + interviews.
- **Acquisition path**: bulk-public-data (federal expenditure filings + state budgets) + interviews.
- **Detection signature**: **block-grant-diversion-accounting** — from federal expenditure category filings (ACF-196R), compute per state the share of TANF going to basic cash assistance vs. agency-backfill categories; join to state budget documents to show *substitution* (welfare money funding what the general fund previously funded); construct per-poor-child denominators to rank states. Utah variant: audit maintenance-of-effort claims for third-party in-kind credits.
- **Corroboration structure**: federal filings ↔ state budget line items (two official books that must reconcile) ↔ human cases demonstrating the mechanism ↔ officials on record defending the accounting.
- **Impact**: The Biden administration's Nov. 2023 proposed TANF rule overhaul — restricting what states may count and divert — followed this investigation.
- **Generalization**: Applies to any flexible federal fund (TANF, CDBG, SSBG, opioid settlements, ARPA SLFRF, Title I). Generic detector: category-share analysis of mandated expenditure reports; substitution tests against the recipient government's own budgets; per-eligible-person denominators across peers; third-party in-kind credits toward matching requirements. "Share reaching intended beneficiaries" is a computable metric for every grant program.

---

### Disaster in the Pacific: the Navy's 7th Fleet collisions (2019) — 17 sailors died after years of documented, ignored warnings about an overstretched, undertrained fleet
- **URL**: Series: https://www.propublica.org/series/navy-accidents-pacific-7th-fleet ; flagship: https://features.propublica.org/navy-accidents/us-navy-crashes-japan-cause-mccain/ ; methodology: https://www.propublica.org/article/us-navy-uss-fitzgerald-uss-john-s-mccain-crash-pacific-how-we-investigated
- **Partner/awards**: T. Christian Miller, Megan Rose, Robert Faturechi. **Winner, 2020 Pulitzer Prize for National Reporting**; Military Reporters & Editors award.
- **What they found**:
  - The 2017 USS Fitzgerald and USS John S. McCain collisions (17 sailors drowned) followed **years of explicit warnings** to Navy leadership — GAO reports, internal readiness assessments, denied budget/training requests, and sailors themselves.
  - The McCain's **Integrated Bridge and Navigation System touchscreen** contributed directly to the collision (Navy/NTSB findings); ProPublica rebuilt the interface via simulation to demonstrate the confusion.
  - Follow-ons documented scapegoating of individual officers and unfulfilled reform promises.
- **Finding type(s)**: warning-ignored-before-disaster; institutional-coverup/records-suppression; two-books-asymmetry (internal readiness data vs. public assurances)
- **Evidence & sources**: [privileged] **Two confidential Navy investigation reports totaling 13,000+ pages** — documents, photos, sailor interview transcripts, ship logs, disciplinary records, raw data — plus insiders' emails, internal memos; [open-public] GAO readiness reports; congressional testimony; released Navy reports; NTSB/Coast Guard findings; courts-martial attended in person; [interviews] Scores of sailors/officers/commanders; dozens of admirals and senior civilians including a former Navy secretary; families; [constructed] Same-class ship tour; a **1:700 scale model**; computer simulations of the navigation system.
- **Access tier**: mixed — privileged (leaked confidential investigations) + open-public (GAO/testimony) + constructed (physical/simulation reconstruction).
- **Acquisition path**: leak + interviews + field-observation + bulk-public-data.
- **Detection signature**: **warnings-ledger-construction** (new tag) — assemble a dated ledger of every documented warning (GAO findings, internal memos, certification lapses, budget denials, sailor complaints) against the decision record of the leaders who received them, anchored to the disaster date. The internal documents supplied the decisive private layer, but the *public* GAO trail alone already showed the pattern — a version of this detection runs on open sources.
- **Corroboration structure**: leaked internal investigations ↔ interviews at every rank ↔ official public findings (NTSB, courts-martial) ↔ physical reconstruction proving mechanism. Methods page discloses the Navy's refusal to engage.
- **Methodology notes**: Formal methods article exists (URL above) — inventory of documents, interview scope, reconstruction technique (stated).
- **Impact**: Congressional hearings on surface-fleet readiness; accountability debates; Pulitzer institutionalized the template.
- **Generalization**: Portable to any institutional disaster (mine collapse, derailment, prison deaths, bank failure): collect prior IG/GAO/regulator findings, internal audits, denied budget requests; timestamp; join to the org chart of who saw what. GAO/IG corpora + budget justifications are open data; "prior-warning density before failure" is computable for any agency or contractor.

---

### Their Family Bought Land One Generation After Slavery. The Reels Brothers Spent Eight Years in Jail for Refusing to Leave It. (2019) — heirs' property law as an extraction machine for Black-owned land
- **URL**: https://features.propublica.org/black-land-loss/heirs-property-rights-why-black-families-lose-land-south/ (July 15, 2019)
- **Partner/awards**: Lizzie Presser, ProPublica co-published with The New Yorker. **George Polk Award** (magazine reporting) and John Bartlow Martin Award.
- **What they found**:
  - Melvin Davis and Licurtis Reels of Carteret County, NC spent **eight years in jail for civil contempt** for refusing to leave waterfront land their great-grandfather bought one generation after slavery — lost via heirs'-property mechanics (a distant relative's interest sold to developers).
  - African Americans lost **~90% of their farmland 1910–1997**; heirs' property comprises **more than a third of Black-owned land in the South (~3.5M acres, ~$28B)**; **76% of Black Americans lack wills** vs. ~a third of whites.
  - Mechanism: undivided fractional inheritance lets a speculator buy any single heir's sliver and force a **partition sale** of the whole property at auction, typically far below market; Torrens registration and adverse possession do parallel work. Lack of clear title also excludes families from USDA loans and FEMA disaster aid — public money gated on paperwork the system denies them.
- **Finding type(s)**: extraction-from-captive-population; fraud-enablement-by-design (partition statutes invite speculation); warning-ignored (decades of USDA/academic documentation)
- **Evidence & sources**: [constructed/fieldwork] Months of county **courthouse deed and court records** across the South; attendance at courthouse-steps auctions; [litigation-records] The Reels partition case file and contempt record; [open-public] USDA data; academic studies; [interviews] Families, heirs'-property lawyers, dozens of experts.
- **Access tier**: constructed + open-public + litigation-records.
- **Acquisition path**: field-observation + litigation-records + bulk-public-data + interviews.
- **Detection signature**: **named-cohort-tracing through deed chains** — follow specific parcels across generations in county deed books, identify partition actions where an outside speculator acquired a fractional interest shortly before filing, and compare auction price to assessed/market value. Aggregate layer: USDA farmland-by-race series for the denominator (90% loss). The unit of detection is the parcel, not the person.
- **Corroboration structure**: court records (mechanism, dates, prices) ↔ family testimony ↔ expert/academic quantification ↔ historical archives; the jail record made the stakes documentary.
- **Impact**: Accelerated state adoptions of the Uniform Partition of Heirs Property Act; cited in federal legislation to open FEMA disaster relief and USDA programs to heirs'-property owners.
- **Generalization**: The pattern — *a records/title technicality converts a population's assets into extractable value while disqualifying them from public aid* — recurs in tax-lien sales, tangled-title urban housing, tribal land fractionation, probate predation. Generic detector: in any county deed/court dataset, flag partition or tax-foreclosure sales where (a) petitioner acquired an interest < N months before filing, (b) sale price << assessed value, (c) repeat petitioners/buyers appear across cases. Our property-records roadmap supports this buyer-concentration screen.

---

### Trump's Inauguration Paid Trump's Company — With Ivanka in the Middle (2018) — a nonprofit's donor funds flowed to the beneficiary family's own hotel at above-market rates
- **URL**: https://www.propublica.org/article/trump-inc-podcast-trumps-inauguration-paid-trumps-company-with-ivanka-in-the-middle (Dec. 14, 2018)
- **Partner/awards**: Justin Elliott (ProPublica) and Ilya Marritz (WNYC), "Trump, Inc." collaboration.
- **What they found**:
  - The 58th Presidential Inaugural Committee (a nonprofit that raised a record ~$107M) paid the **Trump International Hotel ~$700,000** for four days of event space in Jan. 2017. The hotel quoted **$175,000/day**; Ivanka Trump — an executive of the vendor — was in the pricing negotiation between committee and hotel.
  - Planner Stephanie Winston Wolkoff emailed Ivanka and others to "express my concern" the rate was far above market — advising a **maximum of $85,000/day** — and warned about "when this is audited." The committee paid anyway.
  - Later DC AG filings added that nonprofit funds covered a **$300,000 private party for Trump's children** and payments for space on no-event days.
- **Finding type(s)**: self-dealing/related-party; charity-mission-inversion
- **Evidence & sources**: [privileged/insider] Internal committee emails and planning documents (incl. the Wolkoff warnings); [open-public] The committee's Form 990 and FEC donor disclosures; [interviews] Inaugural planners; hotel-industry pricing experts; [litigation-records] (downstream) DC AG complaint; Ivanka deposition (Dec. 2020).
- **Access tier**: mixed — privileged (internal emails) + open-public (990/FEC).
- **Acquisition path**: leak/insider documents + bulk-public-data + interviews.
- **Detection signature**: **related-party-price-benchmarking** (new tag) — identify vendor payments where the payer's decision-makers overlap the vendor's ownership/management (990 vendor schedules × corporate affiliation), then benchmark price against market rates and *the organization's own internal advice*; the internal email fixing fair price ($85K) converted an inference into a documented ~2x overcharge.
- **Corroboration structure**: internal contemporaneous warnings ↔ external market benchmarks ↔ public filings showing payment ↔ later sworn testimony and AG-obtained records confirming the sequence.
- **Impact**: DC AG Racine sued (Jan. 2020) over misuse of nonprofit funds; **$750,000 settlement (May 2022)** redirected to two DC youth nonprofits; federal prosecutors examined inaugural finances after the reporting.
- **Generalization**: Related-party vendor extraction from nonprofits/committees is detectable from filings alone: join 990/FEC vendor payments against officer/family business affiliations (registry data), flag matches, then benchmark price. Inaugural committees, PACs, foundations, university auxiliaries all share the structure. Our 990 + FEC + registry joins can automate the affiliation match.

---

### Eye on the Bailout / Bailout Tracker (2009–2019+) — a decade-long public ledger of every TARP and Fannie/Freddie dollar out and back
- **URL**: https://projects.propublica.org/bailout/ ; retrospective: https://www.propublica.org/article/the-bailout-was-11-years-ago-were-still-tracking-every-penny
- **Partner/awards**: ProPublica news-apps team (launched April 2009; long maintained by Paul Kiel et al.).
- **What they found / built**:
  - A recipient-level ledger covering the **$700B TARP** plus **Fannie Mae/Freddie Mac**: every disbursement, refund, dividend, interest and warrant payment, per program and institution, with recipient profiles.
  - Core accounting concept: **"Net Outstanding"** — taxpayers' per-entity hole after netting revenues against outflows; failed-repayment entities shaded red; housing-program subsidies deliberately *not* coded as losses — a published editorial-accounting judgment.
  - Scope discipline: Treasury expenditures only, excluding Fed facilities — a documented boundary choice.
- **Finding type(s)**: evidence-infrastructure (the ledger is the finding); denominator-construction at national scale
- **Evidence & sources**: [open-public] Treasury TARP transaction and dividend/interest reports, parsed continuously; FHFA/Treasury GSE disclosures.
- **Access tier**: open-public.
- **Acquisition path**: bulk-public-data (recurring official reports → normalized database).
- **Detection signature**: **longitudinal-ledger-construction** (new tag) — normalize every periodic official disclosure into one recipient-keyed money-in/money-out table maintained 10+ years; analytic products (net position, who never repaid, program P&L) fall out of the join. The *persistence* is the moat: one-off stories can't answer "did we get the money back"; a maintained ledger can.
- **Corroboration structure**: single authoritative source (Treasury's own reports); verification burden shifts to internal consistency and explicit published coding rules (what counts as a loss).
- **Methodology notes**: Accounting rules stated on the project's pages (net outstanding, loss shading, Treasury-only scope) (stated).
- **Impact**: Standard citation for bailout accounting; the model for ProPublica's later trackers (Recovery Tracker, Tracking PPP, Coronavirus Contracts) — the org's reusable pattern of turning a spending emergency into permanent queryable infrastructure.
- **Generalization**: Any bailout/subsidy/emergency-facility universe deserves a recipient-keyed longitudinal ledger with explicit repayment/netting semantics. For an agent platform: maintain derived datasets (our sidecar-DB pattern) rather than per-investigation snapshots, with coded loss/repayment semantics so "who never paid it back" is always answerable.

---

## Cluster Synthesis

### 1. Recurring evidence-source types (frequency across 12 entries)

| Source type | Count | Entries |
|---|---|---|
| Federal spending/procurement microdata (FPDS, USASpending, SBA loan-level, Treasury reports) | 6 | COVID contracts, Fillakit, AirBoss, PPP farms, TANF (ACF filings), Bailout tracker |
| Leaked/insider internal documents (after-action reviews, evaluations, investigation reports, emails) | 5 | Red Cross ×2, Navy, inaugural, OZ (state-internal emails, partial) |
| State/local public-records requests (governor's offices, economic-development agencies) | 3 | OZ Port Covington, OZ donor designations, PPP (federal FOIA litigation) |
| State business registries / incorporation records | 3 | COVID contracts, Fillakit, PPP farms |
| Census/eligibility statistical recomputation | 3 | OZ ×2, TANF |
| Field observation (site visits, auctions, on-ground verification) | 4 | Fillakit, Haiti, heirs' property, Navy (ship/model) |
| County courthouse records (deeds, partition/court files) | 1 (deep) | Heirs' property |
| Insider interviews at scale | 10 | all except Bailout tracker and the COVID DB per se |
| Official watchdog corpora (GAO/IG/NTSB) as public warning layer | 2 | Navy; COVID (PRAC corroboration) |
| Litigation/enforcement records for principal history | 3 | Fillakit (FTC), PPP (DOJ), inaugural (AG suit) |

Structural note: the cluster splits cleanly into **data-first stories** (COVID, PPP, OZ, TANF, bailout — anomaly found in public microdata, then humanized) and **document-first stories** (Red Cross, Navy, inaugural — privileged internal records, then quantified). Field observation is the universal closer: the decisive verification step in Fillakit (shovels), Haiti (six homes), and heirs' property (auctions) was physically looking.

### 2. Recurring detection signatures (frequency)

| Signature | Count | Where |
|---|---|---|
| entity-age-vs-award-diff | 3 | COVID contracts, Fillakit, PPP-adjacent |
| silo-join-on-hard-identifier | 4 | PPP (registry nonexistence, address clustering), Fillakit (phone→principal), inaugural (officer↔vendor), COVID |
| two-books-diff | 3 | Red Cross Sandy, Red Cross Haiti, Navy |
| eligibility-recompute + designation-list-diff (new) | 2 | OZ Port Covington, OZ Detroit |
| temporal-correlation | 3 | OZ marina (~8 days), OZ Detroit (<2 weeks), AirBoss (endorsement→stock) |
| denominator-construction | 4 | Haiti (91-cents arithmetic), TANF ($/poor child), Red Cross (meal-waste share), Bailout (net outstanding) |
| benefit-cap-clustering (new) | 1 (strong) | PPP ($20,833 mass point) |
| category-geography-implausibility (new) | 1 | PPP (beach-town cattle ranches) |
| beneficiary-reverse-engineering | 3 | OZ ×2 (landowners inside designated tracts), inaugural |
| warnings-ledger-construction (new) | 1 (deep) | Navy |
| pass-through-fee-stacking (new) | 1 | Haiti |
| procurement-justification-text-mining (new) | 1 | AirBoss ("ordered by the White House" in FPDS free text) |
| named-cohort-tracing | 2 | Heirs' parcels, bailout recipients |
| block-grant-diversion-accounting (new) | 1 | TANF |
| single-originator-concentration (new) | 1 | PPP/Kabbage |
| ground-truth-vs-claimed-output (new) | 2 | Haiti (6 homes), Red Cross Sandy (meals) |
| related-party-price-benchmarking (new) | 1 | Inaugural |
| longitudinal-ledger-construction (new) | 1 | Bailout tracker |

New tags coined this cluster: **eligibility-recompute, designation-list-diff, benefit-cap-clustering, category-geography-implausibility, warnings-ledger-construction, pass-through-fee-stacking, procurement-justification-text-mining, block-grant-diversion-accounting, ground-truth-vs-claimed-output, single-originator-concentration, related-party-price-benchmarking, longitudinal-ledger-construction**.

### 3. Transferable pattern candidates

**P1 — Newborn Vendor in an Emergency (anomalous-vendor screen).** When a spending program's velocity spikes (disaster, pandemic, war, surge), competition controls relax and vendors with no history appear. Mechanics: filter the award stream to the emergency universe; flag vendors whose identifier (UEI/DUNS) has zero prior awards; compute formation-date-vs-award-date from business registries (<90 days = red); cross-tab with sole-source/urgency codes and product-category mismatch vs. the vendor's or principal's history; resolve principals via contract metadata (phone/email/address) into enforcement and court records. Minimum data: award feed with vendor ID, dates, competition code; incorporation registry; principal-resolvable metadata. Agent look-for in ANY procurement universe: first-seen vendor × no competition × out-of-category product × principal with prior enforcement history.

**P2 — Program-Maximum Clustering with Ghost Recipients (relief-lending screen).** Fee-per-transaction originators processing government-guaranteed relief generate fraud with three statistical fingerprints: amount mass points exactly at statutory caps; recipients absent from the registries that should contain them; many recipients sharing one address (especially residential/mail-drop). The originator whose portfolio concentrates the flags is the systemic story — design, incentives, staffing of fraud review. Minimum data: recipient-level microdata (name, address, amount, category, originator); registries; address canonicalization. Works for PPP, EIDL, ERTC, FEMA IA, crop insurance, state relief funds.

**P3 — Boundary Drawn for a Beneficiary (place-based subsidy screen).** Geographic subsidies (zones, districts, TEAs, TIFs) are gamed at designation time. Mechanics: recompute every designated unit's eligibility from the primary statistical source; diff successive versions of the official designation list to catch quiet insertions; map parcel ownership inside designated units and rank by single-owner concentration and land value; pull designation-authority correspondence via records requests; test timing (beneficiary contact → designation, in days). Minimum data: versioned designation lists, eligibility criteria + underlying stats, parcel ownership with LLC resolution, lobbying/donor records. Agent look-for: units failing the recompute; late insertions; high single-beneficiary land concentration; sub-30-day appeal→designation intervals.

**P4 — Two Books, plus the Warnings Ledger (internal-vs-public diff).** Institutions that both self-assess and self-promote produce paired artifacts on the same KPIs. Mechanics: acquire the internal layer (FOIA for agencies: after-action reports, IG memos, readiness data; leak/discovery for private orgs), extract measurable claims from public statements, and diff. Special case: the warnings ledger — dated internal/oversight warnings joined to the later failure event and to who received each warning. Minimum data: internal assessment documents (the hard part) + a public-claims corpus (easy). Open-data precursor: high repeat-finding density in IG/GAO reports around an agency/contractor before a failure.

**P5 — Pass-Through Extraction Chains (grant/subaward screen).** Money moving through intermediaries loses a cut at each hop; headline efficiency claims quote only the first hop, and related-party vendors mid-chain convert public/donor funds into insider revenue. Mechanics: reconstruct the full chain (990 Schedule I, subaward data, audited financials, vendor schedules); compute cumulative per-layer admin extraction vs. the headline ratio; match every node against officer/family/affiliate registries for related-party hops; ground-truth the terminal deliverable. Minimum data: grant/subaward chain with amounts and per-layer fees; officer/ownership registries. Agent look-for: cumulative extraction > ~2x headline overhead; any chain node sharing principals with the payer; deliverables that can't be independently counted.

### Platform notes
- ProPublica's repeated moat in this cluster is **maintained spending infrastructure** (bailout tracker → recovery tracker → Coronavirus Contracts → Tracking PPP): when the emergency arrives, the ledger already exists. Equivalent for us: keep derived, recipient-keyed ledgers (sidecar DBs) with explicit repayment/eligibility semantics rather than per-investigation snapshots.
- The COVID/PPP mechanics confirmed and canonically named: **first-time-vendor flag** (FPDS history join), **formation-date-vs-award-date diff** (registry join), **address clustering + registry nonexistence** (PPP), plus two to adopt: **benefit-cap-clustering** and **procurement-justification-text-mining** (FPDS free-text as a confession layer).
- Field verification is the cheapest decisive step this cluster teaches: after any data flag, one physical/ground-truth observation (site, auction, count of deliverables) repeatedly converted statistical anomalies into publishable findings.
