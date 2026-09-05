# ProPublica Evidence Ontology — Cluster 03: Dark Money & Campaign Finance

Reviewed: 2026-07-28. Scope: ProPublica originals and formal co-publications on political money, 2010–present. All entries verified against live propublica.org pages (plus partner-site copies for formal co-publications). Depth priority per brief: the 990-vs-FEC diff and donor→intermediary→spender grant-chain mechanics.

**Verification notes on candidate list (corrections/drops):**
- **FARA/foreign influence**: DROPPED. Searches found no substantial ProPublica-original FARA investigative series; the major FARA loophole reporting in this space is POLITICO/CRP/POGO. (ProPublica touched FARA incidentally in Manafort-era coverage, but nothing rising to a cluster entry.)
- **Trump, Inc. / American Made Media Consultants**: EXCLUDED as an entry. The AMMC "clearinghouse" spending-laundering allegation was principally a Campaign Legal Center FEC complaint amplified by many outlets; the Trump, Inc. podcast (WNYC+ProPublica co-production) covered adjacent campaign-money territory but the load-bearing analysis is not ProPublica's. Kept out per outlet-attribution quality bar.
- **True the Vote**: VERIFIED as ProPublica's own (Cassandra Jaramillo, 2023), with the caveat that earlier self-dealing reporting on TTV was Reveal/CIR's; ProPublica's piece adds new court records and 990 analysis (noted in entry).
- **Scam PACs**: VERIFIED — a 2019 ProPublica+POLITICO co-publication and a 2024 ProPublica 527-network investigation; treated as one entry (one continuous beat, two detection variants).
- Everything else on the candidate list confirmed as ProPublica originals or formal co-publications.

**New tags coined in this report** (extensions to the starting taxonomies):
- Finding types: `fundraising-mill-self-enrichment`, `application-vs-conduct-gap`, `insider-self-dealing`, `tax-optimized-megadonation`, `coordinated-charity-electioneering`, `evidence-infrastructure`
- Detection signatures: `expenditure-composition-ratio`, `vendor-network-clustering`, `alias-resolution (disregarded-entity LLC → parent org)`, `adversarial-instrumentation`, `crowdsourced-document-liberation`, `new-entity-first-filing-watch`, `enforcement-denominator` (a sharpened form of policy-shadow-measurement), `broadcast-conduct-monitoring`

---

### Buying Your Vote / Free the Files (2012) — Crowdsourced digitization of FCC political ad files exposed ~$1B in TV ad buys, including dark-money buys invisible in FEC data
- **URL**: https://projects.propublica.org/free-the-files/ (app); https://www.propublica.org/article/crowdsourcing-campaign-spending-what-we-learned-from-free-the-files (retrospective); https://www.propublica.org/article/free-the-files-frequently-asked-questions (FAQ)
- **Partner/awards**: Volunteer crowd (~1,000 people); distribution partnership with Huffington Post for swing-state recruitment (https://www.propublica.org/article/free-the-files-partners-with-huffington-post-to-unlock-political-ads-in-swi). Part of ProPublica's 2012 "Buying Your Vote" election-money coverage.
- **What they found**:
  - Nearly 1,000 volunteers reviewed ~16,000 political ad contract files from TV stations in 33 swing markets over 10 weeks, logging as much as $1 billion in 2012 ad buys.
  - The FCC had just ordered top-50-market stations to post their "public inspection files" online (Aug 2012) — but as non-standardized, unsearchable PDFs, making spending totals impossible to compute without human extraction.
  - The structured output let ProPublica link station-level ad contracts to dark-money buyers (via its PACTrack database) — spending that never appears in FEC data when groups run "issue ads" outside reporting windows, e.g. market-level dark-money pieces on Las Vegas and Florida.
- **Finding type(s)**: donor-anonymization-technique (issue-ad non-reporting); two-books-asymmetry (station files vs FEC filings); evidence-infrastructure
- **Evidence & sources**:
  - [regulatory filings, open-but-unusable] FCC public inspection files (ad contracts: buyer, agency, contract number, amount)
  - [constructed dataset] Volunteer-extracted structured records with consensus verification
  - [bulk public data] FEC independent-expenditure/electioneering reports (for the gap comparison)
- **Access tier**: constructed (crowdsource) over open-public raw material
- **Acquisition path**: crowdsourced + scrape (pre-Aug-2012 phase involved volunteers physically visiting stations to request paper files; then the FCC's online dump)
- **Detection signature**: `crowdsourced-document-liberation` — non-machine-readable regulatory PDFs (FCC ad contracts) converted to structured data by ≥2-volunteer consensus per data point (avg 2.8 reviewers/file), then joined to committee/buyer identities (PACTrack), revealing ad spending absent from FEC disclosure. Station files became the ground truth against which FEC reporting gaps were measured.
- **Corroboration structure**: Dual-entry crowd verification (a file "freed" only when two volunteers agreed on each of four fields: buyer, placing agency, contract number, amount); contract documents themselves are primary station records, so extraction accuracy — not source truth — was the risk being controlled.
- **Methodology notes**: ProPublica's own retrospective by Amanda Zamora (Dec 12, 2012): https://www.propublica.org/article/crowdsourcing-campaign-spending-what-we-learned-from-free-the-files; Nieman Lab process pieces (https://www.niemanlab.org/2012/12/crowdsourcing-campaign-spending-what-propublica-learned-from-free-the-files/); Free the Files API nerd post (https://www.propublica.org/nerds/introducing-a-free-the-files-api). Quoted rule: "In order for a file to be freed, at least two volunteers had to agree on each data point."
- **Generalization**: Applies wherever disclosure exists on paper but not in data — state PUC dockets, county campaign filings, court exhibit scans, FOIA reading rooms, procurement attachments. A generic detector: any regulator that "publishes" PDFs without structured fields is hiding a joinable dataset; the play is consensus extraction, then diff against the adjacent structured disclosure regime (here FEC) to find what only the unstructured system captures. Impact line: the FCC's political-file digitization (later extended to all stations/cable/radio) was pushed along by this demonstration [inferred — widely credited, not claimed on the cited pages].

---

### How Nonprofits Spend Millions on Elections and Call It Public Welfare (2012–13, Kim Barker series) — 501(c)(4)s told the IRS "no politics" while reporting millions in political spending to the FEC
- **URL**: https://www.propublica.org/article/how-nonprofits-spend-millions-on-elections-and-call-it-public-welfare (flagship, Aug 18, 2012); https://www.propublica.org/article/what-karl-roves-dark-money-nonprofit-told-the-irs (Crossroads GPS application, Dec 2012); https://www.propublica.org/article/controversial-dark-money-group-among-five-that-told-irs-they-would-stay-out (Jan 2, 2013)
- **Partner/awards**: ProPublica original (Kim Barker). Defining "dark money" coverage of the 2012 cycle (Face the Nation, Hardball appearances; Toner Prize honorable mention per Syracuse listing).
- **What they found**:
  - Reviewing filings of 107 politically active nonprofits from the 2010 cycle: at least 32 of 104 groups that reported political spending to the FEC or state election officials told the IRS they spent no money to influence elections.
  - Center for Individual Freedom reported $2.5M in political ads to the FEC but "nothing" to the IRS (classified as "education"). Commission on Hope, Growth and Opportunity ran an estimated $2.3M in 2010 political ads, reported zero political spending to both IRS and FEC; its 990 showed $4.6M (96% of expenditures) as "advertising."
  - By Aug 8, 2012, 501(c)(4)s had spent $71M+ on presidential TV ads — more than all super PACs combined ($56M). Undisclosed-donor outside spending grew from under 2% (2006) to 40% (2010).
  - Application-level lying: 32 of 72 groups examined answered "No" to political activity on their IRS exemption applications, then reported political spending; American Future Fund uploaded a political ad to YouTube the same day it mailed the IRS an application denying political plans. The IRS — improperly, since pending applications are confidential by law — released to ProPublica nine pending applications including Crossroads GPS's (which promised "limited" election activity while spending $90M+ across 2010–12) and five groups that promised no politics then spent millions (Americans for Responsible Leadership alone: $5.2M+ in Oct–Nov 2012 federal spending plus $11M routed into California ballot fights).
- **Finding type(s)**: two-books-asymmetry; application-vs-conduct-gap; conduit-network (c4s funding c4s to obscure origin); donor-anonymization-technique
- **Evidence & sources**:
  - [bulk public data] IRS Form 990s of 107 nonprofits (political-activity questions, Schedule C, grants schedules)
  - [bulk public data] FEC independent-expenditure/electioneering filings; state election-authority records
  - [request-gated/improper agency release] Form 1024 exemption applications, including confidential pending ones the IRS should not have released
  - [open media artifacts] YouTube ad uploads and TV transcripts (content + timestamps used to classify ads as political)
- **Access tier**: mixed — open-public (990s, FEC) + request-gated (applications; some obtained only because the IRS erred)
- **Acquisition path**: bulk-public-data + FOIA-style records requests (the confidential releases became themselves a news event and later a thread in the 2013 IRS scandal hearings)
- **Detection signature**: `two-books-diff` — the canonical form. Join the same organization's IRS books (990 Part IV/Schedule C political-expenditure answers; application attestations) against its FEC/state books (independent expenditures, electioneering communications) on organization name/EIN; every row where FEC > 0 and IRS = 0 (or application = "No") is a finding. Secondary signature: `temporal-correlation` at document granularity (ad uploaded the same day the application denying politics was mailed).
- **Corroboration structure**: Three-layer: (1) the two filing systems diffed against each other; (2) ad content itself (YouTube/TV transcripts) evaluated against the IRS "facts and circumstances" definition, with outside tax experts reviewing specific ads; (3) grant schedules showing c4→c4 transfers corroborating the obscuring function. ProPublica's stated method: "ProPublica reviewed thousands of pages of filings for 107 nonprofits active during the 2010 election cycle, tracking what portion of their funds went into politics."
- **Methodology notes**: Methodology stated in-article (quote above; classification by "the content of ads, when they ran, and how they relate to groups' other spending"). No separate nerd-blog post found for this series.
- **Generalization**: Any actor filing to two regulators with different incentives will keep two books. Generic detector: enumerate every entity present in both filing systems (IRS 990 universe × FEC spender universe; equivalently: state charity registrations × state campaign-finance spenders), normalize names/EINs, and diff the self-characterizations. Our platform's 990 + FEC tooling can run this exactly: FEC spender name → EIN resolution → 990 Schedule C / Part IV answers → flag contradictions. Impact: fed directly into the 2013–14 IRS proposed c4 political-activity rules debate [inferred from timing; the rules were later shelved].

---

### Big Sky, Big Money — Western/American Tradition Partnership (2012, with FRONTLINE and Marketplace) — A dark-money group's internal files (found in a meth house) plus court-ordered bank records made it the first such group with all donors public
- **URL**: https://www.propublica.org/article/documents-found-in-meth-house-bare-inner-workings-of-dark-money-group (Oct 29, 2012); https://www.pbs.org/wgbh/frontline/article/check-em-out-donations-to-dark-money-group-revealed (Nov 8, 2012 co-publication); https://www.pbs.org/wgbh/frontline/article/dark-money-group-central-to-citizens-united-may-have-misled-irs
- **Partner/awards**: FRONTLINE (film "Big Sky, Big Money") + Marketplace; IRE Award for the joint dark-money reporting (https://www.propublica.org/atpropublica/propublica-and-partners-win-ire-award)
- **What they found**:
  - Boxes of Western Tradition Partnership (later American Tradition Partnership) internal records — surfaced from a Colorado meth house in 2011 and held by Montana investigators — contained files on 23 Montana candidates: draft mailers marked as campaign-paid, cut-out signatures affixed to fliers, candidate surveys, and a folder labeled "Montana $ Bomb" — evidence bearing on illegal candidate coordination.
  - Fundraising pitches marketed anonymity as the product (donors could "sit back on election night and see what a difference you've made" without disclosure).
  - WTP told the IRS under penalty of perjury it would not attempt to influence elections — after it already had; Montana's commissioner had ruled in Oct 2010 that WTP should have registered as a political committee and that its "Coalition for Energy and the Environment" was a sham organization.
  - After a Montana district judge ordered WTP's bank records released (Slate reported the unsealing came at ProPublica/PBS's request: https://slate.com/news-and-politics/2012/11/western-tradition-partnership-monta-judge-reveals-dark-money-donors-at-request-of-propublica-pbs.html), it became "the first modern dark money group to have all of its donors made public": ~$1.1M from March 2008–Dec 2010; largest individual donor Norman Asbjornson ($50K, plus $20K from his HVAC company). ProPublica/FRONTLINE published all six batches of donor checks online, redacted.
- **Finding type(s)**: donor-anonymization-technique (anonymity marketed as product); application-vs-conduct-gap; influence-laundering-via-intermediaries (sham front group); undisclosed candidate coordination
- **Evidence & sources**:
  - [windfall primary documents] Internal WTP files (mailer drafts, candidate folders, donor pitches) — obtained via state investigators after a serendipitous third-party discovery
  - [litigation records, unsealed] Bank records and donor checks released by court order
  - [regulatory rulings] Montana Commissioner of Political Practices findings
  - [request-gated] WTP's IRS exemption application vs. its observed conduct
- **Access tier**: mixed — privileged-adjacent windfall (documents found by a felon, then in state custody) + litigation-unsealed records + open rulings
- **Acquisition path**: mixed — field-observation/windfall + litigation-records (court unsealing pursued during reporting) + records requests
- **Detection signature**: `internal-rulebook-acquisition` — the group's own solicitation materials stating anonymity and its candidate files did the work; layered with `application-vs-conduct-diff` (IRS attestation vs prior electioneering already documented by the state regulator). The donor checks enabled full `grant-chain-tracing` for one group — a rare complete ground-truth graph.
- **Corroboration structure**: State investigative file (primary) + court-released bank records (primary) + IRS application (primary) + interviews; each layer independent in origin (police custody, judiciary, IRS) — true corroboration rather than redundancy.
- **Methodology notes**: In-article sourcing description; the co-published FRONTLINE piece documents the records release ("Today, after redacting addresses, phone numbers and account numbers, ProPublica and FRONTLINE are putting all six batches of checks to the group online."). [inferred] The unsealing-motion attribution rests on Slate's contemporaneous account.
- **Generalization**: Two transferable moves: (1) when any enforcement body (state campaign regulator, AG, bankruptcy trustee) holds seized/obtained internal files of an opaque org, those files may be reachable by request or by intervening in the court file — always inventory what litigation/administrative custody already exists around a target; (2) a single fully-unmasked group is a calibration set — WTP's complete donor list showed what categories of money hide behind c4 anonymity, informing priors for every group that stays masked. Watch for: front groups whose founding documents postdate their observed campaign activity.

---

### Regulators in Retreat: FEC gridlock and the IRS's dark-money surrender (2011–2016) — Both referees of political money stopped calling fouls, by design
- **URL**: https://www.propublica.org/article/as-political-donors-push-envelope-fec-gridlock-gives-de-facto-green-light (Nov 7, 2011, Marian Wang); https://www.propublica.org/article/six-facts-lost-in-irs-scandal (May 22, 2013, Barker & Elliott); https://www.propublica.org/article/irs-grants-nonprofit-status-to-dark-money-group (Feb 9, 2016, Faturechi & Willis)
- **Partner/awards**: ProPublica originals.
- **What they found**:
  - FEC: 3–3 party-line deadlocks operate as "a de facto green light" — deregulatory commissioners "can get a lot done simply by saying no" (Bradley Smith, former GOP commissioner); five of six commissioners were serving on expired terms; the commission twice failed in 2011 even to open public comment on post-Citizens United rules; in one enforcement matter a violator's penalty check was refunded after a deadlock closed the case.
  - IRS: social-welfare nonprofits spent $256M+ on 2012 federal elections (at least 80% from conservative groups; Crossroads GPS alone $70M+). Structural gaps: c4s "can simply incorporate and start raising and spending money, without ever applying to the IRS"; the "primary purpose" test rests on undefined "facts and circumstances" with no numeric threshold — "the IRS has avoided clarifying any limits."
  - Terminal data point: in Nov 2015 the IRS granted Crossroads GPS tax-exempt status after a five-year fight — the group whose application an IRS official (Lois Lerner) had reportedly tried to deny; former IRS Exempt Organizations director Marcus Owens: "Operating for the benefit of one particular candidate or party, it's hard to say that's not private benefit." Dark-money spending ran ~$125M conservative vs ~$35M liberal in 2014.
  - [Candidate-list correction: no substantial ProPublica story specifically on the 2011 mass auto-revocations was found; auto-revocation data instead surfaces through Nonprofit Explorer (see infrastructure entry).]
- **Finding type(s)**: fraud-enablement-by-design (enforcement collapse); preferential-carve-out (self-declaration loophole)
- **Evidence & sources**:
  - [government proceedings] Congressional oversight testimony; FEC commissioner statements; MUR (Matter Under Review) enforcement files
  - [bulk public data] FEC vote/enforcement outcomes; dark-money spending totals by cycle
  - [agency records] IRS approval outcomes (Crossroads determination), scandal-era documents
- **Access tier**: open-public
- **Acquisition path**: bulk-public-data + hearings/records
- **Detection signature**: `enforcement-denominator` — construct the ratio of regulator output (enforcement votes concluded, penalties, denials) to the measurable violation base (deadlock share of substantive votes; dollars of unreported-donor spending; applications like Crossroads' where conduct plainly exceeded attestations). The story is the widening gap, plus marquee capitulations (Crossroads approval) as sentinel events.
- **Corroboration structure**: The agency's own vote records and determinations (primary) + named former-insider commissioners on the record explaining the mechanism + external spending data quantifying what went unpoliced.
- **Methodology notes**: [inferred] No dedicated methodology post; analysis assembled from hearing records, MUR documents, and FEC/IRS outcome data as cited in-article.
- **Generalization**: Enforcement-collapse measurement transfers to any regulator: SEC ALJ outcomes, OSHA penalty mills, state charity bureaus. Generic detector: time-series regulator actions vs violation proxy; flag agencies where the action series goes to zero while the violation proxy grows — that gap is itself the enabling mechanism for every other pattern in this cluster, and predicts where bad actors will concentrate next.

---

### The Dark Money Man: Sean Noble, the Center to Protect Patient Rights, and the Koch conduit network (2014) — $137M/year in anonymous money routed through a P.O.-box nonprofit whose operator paid his own firms $24M
- **URL**: https://www.propublica.org/article/the-dark-money-man-how-sean-noble-moved-the-kochs-cash-into-politics-and-ma (Feb 14, 2014, Barker & Meyer); network map: https://projects.propublica.org/graphics/koch; LLC-alias decode: https://www.propublica.org/article/who-controls-koch-political-network-asmi-slah-tohe; California fines: https://www.propublica.org/article/dark-money-groups-pay-1-million-dollars-in-fines-in-california-case
- **Partner/awards**: ProPublica original.
- **What they found**:
  - CPPR — run from P.O. Box 72465, Phoenix ($72/year) yet reporting $50K "occupancy" expenses — raised $62M in 2010 (distributing $44.6M to 22 groups) and distributed nearly $137M in 2012.
  - Three firms owned by Noble took almost $24M in 2012 — more than $1 of every $6 CPPR spent; Noble's personal earnings rose from ~$200K to an estimated $3M/year.
  - California's FPPC investigation of $11M laundered through Americans for Responsible Leadership into two 2012 California ballot campaigns ended in a record $1M settlement and the FPPC's "campaign money laundering" characterization; the investigation file (including recorded interviews with operatives) became reporting substrate.
  - The companion network graphic mapped Freedom Partners Chamber of Commerce and TC4 Trust distributing ~$264M to 30 nonprofits (mid-2011–Oct 2012), nearly half via CPPR; recipient groups reported $75M+ in 2012 political spending. TC4's grants were recorded to "disregarded entity" LLC aliases (ASMI, SLAH, TOHE...), which ProPublica resolved to their parent nonprofits.
- **Finding type(s)**: conduit-network; influence-laundering-via-intermediaries; fundraising-mill-self-enrichment (operator fees); donor-anonymization-technique
- **Evidence & sources**:
  - [bulk public data] Form 990s of CPPR and Koch-affiliated nonprofits — grant schedules (Schedule I) and contractor-fee schedules
  - [bulk public data] FEC filings of recipient groups
  - [litigation/regulatory records] California FPPC investigation file, depositions, recorded interviews; settlement documents
  - [public records] Property records (office/occupancy contradiction)
  - [interviews] Dozens, mostly anonymous ("due to fears of retaliation")
- **Access tier**: mixed — open-public (990/FEC) + request-gated (state investigation records)
- **Acquisition path**: bulk-public-data + litigation-records + interviews
- **Detection signature**: `grant-chain-tracing` + `alias-resolution` — build the donor→intermediary→spender graph from 990 Schedule I grants (grantor side) matched to recipients' 990 revenue and FEC spending; where grants are booked to disregarded-entity LLC names, resolve aliases via state registry filings and 990 footnotes to reconstruct the true edge list. Hub anomaly detectors: extreme grant throughput with no program activity; P.O.-box address; occupancy expenses inconsistent with physical footprint; vendor fees flowing to officer-owned firms (self-enrichment share = officer-linked vendor payments / total spending, here ~17%).
- **Corroboration structure**: The 990 grant graph (self-reported by both grantor and recipient — a built-in double-entry check) + an independent state enforcement file with sworn/recorded statements + property records contradicting expense claims + human sources. California's file corroborated intent (laundering) that filings alone could only suggest.
- **Methodology notes**: In-article sourcing enumeration (990s, FEC, court records and depositions, California investigation records incl. recorded interviews, property records, interviews). Network-graphic sourcing implicit in the filings [inferred for the graphic; the ASMI/SLAH/TOHE article documents the alias-resolution move].
- **Generalization**: The master pattern for /trace-grants tooling: (1) two-sided grant reconciliation (grantor Schedule I vs grantee reported revenue — mismatches are leads); (2) alias resolution of LLC/DBA grant recipients through state registries; (3) hub scoring (throughput/program-expense ratio, address type, officer-vendor overlap). Appears identically in donor-advised-fund chains, fiscal-sponsorship networks, and international NGO regranting. Flag any nonprofit whose top expense lines are grants to entities that themselves mostly regrant.

---

### Facebook Political Ad Collector (2017–2019) — Volunteer browser extensions built the public archive of targeted political ads that Facebook refused to provide — until Facebook blocked it
- **URL**: https://www.propublica.org/article/how-we-are-monitoring-political-ads-on-facebook (methodology); https://propublica.org/article/facebook-blocks-ad-transparency-tools (Jan 2019 shutdown); code: https://github.com/propublica/facebook-political-ads
- **Partner/awards**: International newsroom partners for country deployments (Germany, Italy, Australia, Austria); later stewardship by Quartz (April 2020) and revival at The Globe and Mail (https://www.niemanlab.org/2019/06/propublicas-facebook-monitoring-political-ad-tool-which-facebook-fought-is-alive-again-with-a-new-home-at-the-globe-and-mail/).
- **What they found**:
  - Thousands of volunteers installed a Chrome/Firefox extension that captured the ads (and Facebook's targeting explanations) from their own feeds, feeding a public searchable database of political ads that otherwise vanished after delivery — including ads targeted at demographics the researcher could never see.
  - A Naive Bayes classifier — spam-detection tech — separated political from commercial ads, trained continuously by volunteer ratings ("works particularly well on classifying text into one of two groups... political and not political").
  - Privacy engineered in: Facebook IDs, tracking pixels, and user names stripped before publication.
  - In January 2019 Facebook inserted code to block the extension (and Mozilla's and Who Targets Me's equivalents), months after executives had urged ProPublica to shut the project down — turning platform opacity itself into the story.
- **Finding type(s)**: donor-anonymization-technique (ephemeral targeted ads as undisclosable spending); evidence-infrastructure; fraud-enablement-by-design (platform withholding the disclosure layer)
- **Evidence & sources**:
  - [constructed dataset] Crowd-collected ad corpus + targeting metadata
  - [platform artifacts] Facebook's own targeting explanations, captured client-side
  - [open-source instrument] Published extension code and classifier
- **Access tier**: constructed (instrumented crowdsourcing) against a closed platform
- **Acquisition path**: crowdsourced + scrape (client-side, user-consented)
- **Detection signature**: `adversarial-instrumentation` — when the dataset needed for accountability exists only inside a private platform, distribute collection to consenting users at the edge; a lightweight classifier turns raw capture into the domain corpus, and the platform's own microtargeting metadata becomes the disclosure it never filed. Diffing collected ads against the platform's later official ad archive exposes archive gaps [inferred as practiced by successor projects].
- **Corroboration structure**: Each ad is a self-authenticating platform artifact (screenshot + metadata); crowd ratings cross-check the classifier; volume across thousands of independent feeds guards against spoofed submissions.
- **Methodology notes**: ProPublica's own methodology article (URL above; Larson/Angwin/Valentino-DeVries) and open-sourced code. The 2019 blocking article documents scale ("thousands of volunteers") and Facebook's countermeasures.
- **Generalization**: Transfers to any walled-garden distribution channel: streaming political ads, influencer sponsorship, algorithmic pricing. Requirements: (1) a consenting panel at the edge; (2) a narrow classifier; (3) privacy-stripping by design. Strategic lesson: expect the platform to retaliate; assume the collection channel is perishable and archive aggressively.

---

### Scam PACs and political-fundraising mills (2019 with POLITICO; 2024) — Committees that exist to fundraise for their fundraisers: $10M raised, $48,400 to politics; a 527 network spending ~90% on fundraising
- **URL**: https://www.propublica.org/article/conservative-majority-fund-political-fundraising-pac-kelley-rogers (Jul 26, 2019, Derek Willis & Maggie Severns); guilty-plea follow-up: https://www.propublica.org/article/political-fundraiser-pleads-guilty-to-fraud; 527 network: https://www.propublica.org/article/political-nonprofits-fundraising-ftc-irs-527s-pacs (Jun 18, 2024, Ellis Simani)
- **Partner/awards**: 2019 story co-published with POLITICO.
- **What they found**:
  - Conservative Majority Fund raised nearly $10M from mid-2012 while directing only $48,400 to political contributions; a single $371K TV ad (Aug 2012) was its only real political output, followed by years of pure telemarketing. InfoCision charged ~$9M in fundraising fees; operative Kelley Rogers' Strategic Campaign Group took $229K; treasurer Scott B. Mackenzie $172K. FEC response: a $3,500 fine (2016). Rogers pleaded guilty to federal wire fraud (ProPublica follow-up above); Ken Cuccinelli had earlier sued Rogers over a PAC that raised $2M and gave his campaign $10K (settled for $85K in 2015).
  - 2024: at least 10 connected 527 nonprofits (American Breast Cancer Coalition, National Coalition for Disabled Veterans PAC, National Committee for Volunteer Firefighters, National Police & Sheriffs Coalition PAC...) raised $33M+ and spent roughly 90% on fundraising; ABCC collected ~$9M since 2019 and spent under 0.5% on its stated "voter advocacy and outreach."
  - The 2024 network was knit together by shared operators and infrastructure: Thomas Berkenbush (Office Edge LLC, ~$866K; formerly of FTC-shuttered Outreach Calling), Alan Bohms (~$1.5M via shells), one shared Tennessee accounting firm (Purkey, Carter, Compton, Swann & Carter), plus matching website templates and payment processors. Enforcement vacuum stated flatly: "There is no enforcement whatsoever. It's just not a big enough issue for the IRS" (William Josephson, former NY AG charities-bureau chief).
- **Finding type(s)**: fundraising-mill-self-enrichment; charity-mission-inversion; fraud-enablement-by-design (FEC/IRS non-enforcement); conduit-network (vendor shells)
- **Evidence & sources**:
  - [bulk public data] FEC receipts/disbursements (2019); IRS Form 8872 527 filings — a "hard-to-use data file" ProPublica converted into a searchable expenditure database (2024)
  - [privileged] Internal emails/documents "from someone with direct knowledge" revealing call-script decisions (2019)
  - [litigation records] Cuccinelli v. Rogers suit; DOJ wire-fraud case; FTC action against Outreach Calling
  - [open web artifacts] Website design patterns, payment processors (clustering keys)
- **Access tier**: mixed — open-public filings + privileged insider documents (2019) + litigation records
- **Acquisition path**: bulk-public-data + leak + litigation-records
- **Detection signature**: Two-stage. (1) `expenditure-composition-ratio`: for every committee, compute (contributions to candidates + independent expenditures) / total disbursements from FEC or 8872 data; mills sit under ~5% with the remainder to fundraising vendors. (2) `vendor-network-clustering`: cluster flagged committees on shared treasurers, fundraising vendors, accountants, addresses, web templates, and payment processors — the cluster, not the single committee, is the story and reveals the operators.
- **Corroboration structure**: Filing math (primary, self-reported) established the ratio; insider documents established intent (aggressive scripts); court/FTC records established operators' histories; the shared-vendor graph established that "independent" committees were one enterprise.
- **Methodology notes**: 2024 story describes the data build in-article (IRS 527 "hard-to-use data file" → searchable expenditure database; clustering on vendors/accountant/web patterns). 2019 methodology in-article (FEC comparison + internal documents). [inferred] No standalone nerd post found.
- **Generalization**: Composition ratio + operator clustering generalizes to charity telemarketing mills (990 Schedule G professional-fundraiser fees), veterans/police "coalition" charities, crowdfunding mills, shell-vendor procurement rings. Our FEC tooling can compute the ratio corpus-wide today; the clustering keys (treasurer name, vendor EIN/address, processor, web template hash) are exactly what our silo-join tooling handles.

---

### The $1.6 Billion Marble Freedom Trust transfer (2022, with The Lever) — The largest known dark-money seed: Barre Seid gave Leonard Leo's trust an entire company, pre-sale, avoiding ~$400M in tax
- **URL**: https://www.propublica.org/article/dark-money-leonard-leo-barre-seid (Aug 22, 2022; Andrew Perez/The Lever, Andy Kroll, Justin Elliott); series continuation: https://www.propublica.org/article/we-dont-talk-about-leonard-leo-supreme-court-supermajority
- **Partner/awards**: Co-published with The Lever (simultaneous NYT reporting existed independently; the ProPublica/Lever piece stands on its own documents).
- **What they found**:
  - Electronics magnate Barre Seid donated 100% of Tripp Lite's shares to Marble Freedom Trust — the new 501(c)(4) run by Federalist Society co-chair Leonard Leo — before Eaton Corp. acquired Tripp Lite for $1.65B (closed 2021), making the trust's first 990 show a $1.65B contribution: the largest known transfer to a politically focused nonprofit.
  - Donating the appreciated company instead of selling it let Seid avoid up to ~$400M in capital gains taxes (mechanics per tax scholar Ellen Aprill: appreciation in assets given to a c4 escapes tax entirely) — the treasury effectively co-financed the political war chest.
  - Corporate paperwork carried the fingerprints: Illinois filings show Seid's name crossed out as Tripp Lite officer in Feb 2021 with Leo's added by hand; Nova Scotia corporate records tied the holding structure together.
  - Leo, "positioned to finance his already sprawling network," gained one of the largest pools of political capital in U.S. history, invisible to donor-disclosure regimes. The article notes the structure "does not appear to violate any laws."
- **Finding type(s)**: tax-optimized-megadonation; donor-anonymization-technique; influence-laundering-via-intermediaries (trust as perpetual funder of the Leo network)
- **Evidence & sources**:
  - [bulk public data / filing-watch] Marble Freedom Trust's first Form 990 (the revenue line is the tell)
  - [public registries] Illinois Secretary of State corporate filings; Nova Scotia corporate records
  - [request-gated] Public-records requests; FOIA'd email exchanges
  - [litigation records] Court testimony transcripts
  - [expert analysis] Tax-law professors on the record explaining the mechanics
- **Access tier**: open-public (with FOIA supplements)
- **Acquisition path**: bulk-public-data (new filings monitored) + FOIA + records
- **Detection signature**: `new-entity-first-filing-watch` + `silo-join-on-hard-identifier` — monitor first-ever 990s of newly formed c4s/trusts for revenue wildly disproportionate to age; explain the anomaly by joining to corporate registries on officer names and dates (the crossed-out officer line dated the control transfer; the acquisition announcement dated the monetization). General form: a nine-figure revenue line in an infant nonprofit is either a data error or the biggest story in the file.
- **Corroboration structure**: The 990 (self-reported) + two independent corporate registries + the public M&A record of the Eaton acquisition + expert quantification of the tax motive; timeline assembly across the four sources is what proved the pre-sale donation structure.
- **Methodology notes**: In-article sourcing enumeration (corporate filings, tax returns, public-records requests, court testimony). [inferred] The trigger was reporters tracking newly available filings from Leo-network entities.
- **Generalization**: Watch for appreciated-asset donations (whole companies, closely held stock, crypto) into c4s/DAFs/trusts timed just before liquidity events — registry officer-change dates vs deal-announcement dates is the detector. Automatable with our registries + 990 tooling: new EIN + first-990 revenue > $50M → join officer names to corporate registry changes within ±12 months of any M&A record. Impact: became the reference case in congressional/IRS-policy debate over c4 appreciated-asset gifts and drew watchdog complaints against the Leo network [inferred — post-publication scrutiny widely reported].

---

### The IRS Looks the Other Way as Churches Endorse Candidates (2022, with The Texas Tribune) — More pulpit-politics violations found in two years of livestreams than the IRS investigated in a decade
- **URL**: https://www.propublica.org/article/irs-church-nonprofit-endorsements-johnson-amendment (Oct 30, 2022, Jeremy Schwartz & Jessica Priest); violations list: https://www.propublica.org/article/johnson-amendment-violation-examples
- **Partner/awards**: Co-published with The Texas Tribune.
- **What they found**:
  - 18–20 churches committed apparent Johnson Amendment violations in two years (KingdomLife/Frisco pastor Brandon Burden; Legacy Church/Albuquerque's Steve Smothermon calling the governor "demonic"; Mercy Culture/Fort Worth; Gateway Church displaying candidate names on screens; First Baptist Grapevine) — each confirmed by nonprofit tax-law experts.
  - FOIA'd IRS records: only 16 church political-intervention inquiries since 2011, outcomes secret; exactly one church has ever lost exemption over politics (Branch Ministries).
  - Root cause: a 2009 federal ruling found church audits require a high-level sign-off that a 1998 reorganization had abolished — audits effectively suspended ~2009–2014; the 2019 fix (designating the TE/GE commissioner) is viewed as symbolic.
- **Finding type(s)**: coordinated-charity-electioneering; fraud-enablement-by-design (structural non-enforcement); two-books-asymmetry (tax-exempt status vs broadcast conduct)
- **Evidence & sources**:
  - [open media artifacts] Livestreamed/archived church services (COVID-era streaming created the corpus)
  - [crowdsourced] Reader-submitted sermons via a tips form
  - [request-gated] FOIA'd IRS church-investigation statistics
  - [expert review] Three independent tax-law experts confirming each violation
- **Access tier**: mixed — constructed (systematic AV review + crowdsourcing) + FOIA
- **Acquisition path**: mixed — monitoring of streams + crowdsourced + FOIA
- **Detection signature**: `broadcast-conduct-monitoring` + `enforcement-denominator` — systematically review a target class's own public AV output against a bright-line legal standard, expert-adjudicate each case, then FOIA the regulator's caseload for the same period; journalist-found violations (~20 in 2 years) vs regulator inquiries (16 in 11 years) quantifies abdication.
- **Corroboration structure**: The violation evidence is the subject's own recorded speech (self-authenticating); an expert panel converts observation into legal characterization; FOIA data supplies the institutional-failure layer; subjects' on-record responses close the loop.
- **Methodology notes**: In-article: "reviewed dozens of livestreamed church services," reader submission pipeline, three-expert confirmation standard.
- **Generalization**: Any compliance regime where regulated entities self-publish conduct: broker-dealer podcasts vs FINRA rules, officials' streams vs Hatch Act, charity galas vs electioneering bans. Detector: build the corpus (streams/transcripts), classify against the bright-line rule, FOIA the enforcement stats, publish the ratio. Impact one-liner: by July 2025 the IRS formally conceded in litigation that pulpit endorsements are permissible — ratifying the non-enforcement the series documented.

---

### True the Vote: donations for personal gain (2023) — The election-denial fundraising machine's charity money flowed to its founder and insiders
- **URL**: https://www.propublica.org/article/true-the-vote-donations-irs-engelbrecht-phillips (Jun 5, 2023, Cassandra Jaramillo); arc context: https://www.propublica.org/article/a-reading-guide-to-true-the-vote-the-controversial-voter-fraud-watchdog (2012); adjacent: https://www.propublica.org/article/poll-worker-recruitment-swing-states-true-the-vote-lion-of-judah
- **Partner/awards**: ProPublica original; Jaramillo's True the Vote reporting was a Livingston Award finalist (per her ProPublica bio). Attribution note: earlier TTV self-dealing reporting was Reveal/CIR's; this piece adds ProPublica-obtained court records and 990 analysis, published alongside the Campaign for Accountability's IRS complaint.
- **What they found**:
  - The 501(c)(3) lent founder Catherine Engelbrecht ~$40K–$113K — nonprofit loans to directors are barred under Texas law — while she held director and employee roles simultaneously.
  - Longtime director Gregg Phillips' firms received at least $750K for "research analysis" of questioned substance.
  - General counsel James Bopp Jr. billed ~$280K in about a week around four post-2020 election lawsuits (of seven promised) that were filed then quickly withdrawn; he later sued TTV for nearly $1M more in unpaid fees.
  - Disclosure failures compounded: the 2020 Form 990 omitted required reporting of >$100K insider contracts; a promised amended 2019 return apparently was never filed with the IRS.
- **Finding type(s)**: insider-self-dealing; charity-mission-inversion; two-books-asymmetry (990 disclosure omissions vs documented payments)
- **Evidence & sources**:
  - [bulk public data] Forms 990 (2019–2021) — related-party disclosure schedules and their omissions
  - [litigation records] Court records obtained by ProPublica (incl. the Bopp fee suit)
  - [advocacy filing] Campaign for Accountability IRS complaint (contemporaneous, cross-checked rather than relied on)
  - [prior reporting] Reveal's earlier self-dealing findings (credited)
- **Access tier**: open-public + litigation records
- **Acquisition path**: bulk-public-data + litigation-records
- **Detection signature**: `beneficiary-reverse-engineering` via 990-vs-court-record diff — payments and loans proven in litigation filings were matched against the charity's 990 related-party/contractor schedules; every payment present in court records but absent from Schedule L/contractor disclosure is both a self-dealing lead and an independent reporting violation.
- **Corroboration structure**: Court filings (sworn, adversarial — high evidentiary value) corroborate and exceed the self-reported 990s; state nonprofit law supplies the illegality frame (director loans); the target's own amended-return promise vs IRS records shows the cover-up layer.
- **Methodology notes**: [inferred] In-article sourcing (990s, court records, complaint); no standalone methodology post.
- **Generalization**: For any movement-fundraising nonprofit: cross-reference litigation dockets involving the org (fee disputes are gold — vendors suing reveal true payment flows) against 990 Schedules L/J/contractor tables. Detector: entity appears in ≥1 money-dispute docket AND 990 related-party schedules are empty or thin → audit gap. Directly runnable with our CourtListener + 990 tooling.

---

### Inside Ziklag (2024, with Documented) — A secret 501(c)(3) of ultrawealthy Christian families budgeted ~$12M to swing the 2024 election, including a million-voter purge plan
- **URL**: https://www.propublica.org/article/inside-ziklag-secret-christian-charity-2024-election (Jul 13, 2024, Andy Kroll & Nick Surgey); partner copy: https://documented.org/reporting/inside-ziklag-secret-christian-charity-2024-election
- **Partner/awards**: Co-published with Documented.
- **What they found**:
  - Ziklag — a charity whose revenue grew from $1.3M (2018) to ~$12M (2022), funded by the Uihlein, Green (Hobby Lobby), and Waller (Jockey) families — budgeted nearly $12M for 2024 election work while holding c3 charitable status.
  - Three named operations: Checkmate ($800K into EagleAI voter-roll-challenge software; internal goal of 10,640 net votes in Arizona and up to 1M registrations challenged across swing states), Steeplechase (church-based turnout), Watchtower (anti-trans wedge messaging).
  - Money flowed to Alliance Defending Freedom, Turning Point USA, and allied groups.
  - Six nonpartisan tax experts reviewed the documents: "across the line without a question" (Mayer, Notre Dame); the reporting "casts serious doubt on this organization's status as a 501(c)(3)" (Colinvaux).
- **Finding type(s)**: coordinated-charity-electioneering; charity-mission-inversion; donor-anonymization-technique (c3 secrecy + tax deduction for political work); influence-laundering-via-intermediaries
- **Evidence & sources**:
  - [privileged/leaked] "Thousands of Ziklag's members-only email newsletters, internal videos, strategy documents and fundraising pitches" — not previously public
  - [bulk public data] Forms 990 (revenue trajectory, grants)
  - [expert review] Six tax-law experts on the record
- **Access tier**: privileged (insider material) corroborated by open-public filings
- **Acquisition path**: leak + bulk-public-data
- **Detection signature**: `internal-rulebook-acquisition` — the group's own strategy documents stated electoral intent ("10,640 votes in Arizona") that its public c3 posture denied; 990s then quantified the machine (revenue ramp timed to election cycles, grants to movement orgs). The two-layer diff — internal stated purpose vs legal-status constraints — converts a leak into a finding.
- **Corroboration structure**: Internal documents (primary, self-authored) × public filings (primary, self-reported to IRS) × six independent experts converting the gap into legal significance; donor identifications cross-checked against known family giving.
- **Methodology notes**: Sourcing stated in-article ("obtained thousands of..."); expert-panel adjudication described. [inferred] Document provenance not further specified (source protection).
- **Generalization**: Election-cycle-synchronized revenue ramps in c3s are a filings-only tell (990 revenue by year vs cycle calendar) even without a leak. With insider material, the detector is intent-vs-status diff: any tax status, license, or registration that forbids the purpose stated in internal documents. Impact one-liner: Freedom From Religion Foundation cited the reporting in an IRS complaint seeking revocation of Ziklag's c3 status (https://www.taxnotes.com/lr/resolve/exempt-organizations/freedom-from-religion-reports-ministry-charity-to-irs/7mfwm).

---

### Nonprofit Explorer (2013–present) — ProPublica turned bulk IRS 990 data into the queryable public utility that powers dark-money tracing everywhere (including its own)
- **URL**: https://projects.propublica.org/nonprofits/ ; API announcement: https://www.propublica.org/nerds/announcing-the-nonprofit-explorer-api ; full-text milestone: https://www.propublica.org/nerds/nonprofit-explorer-update-full-text-of-nearly-two-million-records
- **Partner/awards**: ProPublica news application (launched May 2013; continuously expanded).
- **What they found** (as infrastructure, "findings" = capabilities):
  - Integrates IRS raw filing extracts, the Exempt Organizations Business Master File, Form 990/990-EZ/990-PF documents as PDF and e-file XML, and federal single-audit reports (orgs spending $750K+ in federal grant funds, FY2015+), across all 27 subsections of 501(c).
  - Full-text search across millions of filings (announced at ~2M records, since grown to ~3M per Chronicle of Philanthropy coverage) — officer names, vendor names, and grantees buried in schedule text became searchable hard identifiers.
  - A free public API making the corpus programmatically joinable by outside newsrooms, researchers, and tools.
  - Editorially, it is the substrate under most entries in this cluster: grant-chain tracing (CPPR/Koch, Ziklag), revenue-anomaly detection (Marble), self-dealing schedules (True the Vote), fundraising-fee analysis (527 mills).
- **Finding type(s)**: evidence-infrastructure; denominator-construction (the searchable universe of exempt orgs is the denominator for every nonprofit story)
- **Evidence & sources**:
  - [bulk public data] IRS 990 image files, e-file XML releases, Business Master File, single-audit clearinghouse data
- **Access tier**: open-public (re-engineered for usability)
- **Acquisition path**: bulk-public-data
- **Detection signature**: `silo-join-on-hard-identifier` at platform scale — EIN as spine; full-text indexing promotes soft strings (officer names, addresses, grantee names in schedule text) into join keys across the entire exempt sector. The tool converts one-off document pulls into corpus-wide queries ("every 990 mentioning X").
- **Corroboration structure**: N/A (infrastructure); reliability inherits from IRS primary data; ProPublica layers version/date provenance per filing.
- **Methodology notes**: Nerd-blog posts document each data-layer addition (URLs above; also https://www.propublica.org/nerds/form-990-documents-return-to-nonprofit-explorer and https://www.propublica.org/article/nonprofit-explorer-adds-a-million-new-form-990s).
- **Generalization**: When a story cluster depends on a hostile-to-use public dataset, build the utility once, publicly — it compounds (internal reporting advantage + external ecosystem + inbound tips). Candidates for the same play in our domains: FARA exhibits, state charity-regulator filings, FCC political files, 8872/527 data (ProPublica repeated the play there in 2024), state campaign-finance systems. A standing agent question: "is there a Nonprofit-Explorer-equivalent for this filing system?" — absence = opportunity.

---

## Cluster Synthesis

### 1. Recurring evidence-source types (frequency across 12 entries)
| Source type | Count | Entries |
|---|---|---|
| IRS Form 990 family (990/990-EZ/990-PF, Schedules B/C/I/L, applications 1023/1024) | 9 | c4 series, Montana, IRS/FEC collapse, CPPR/Koch, Marble, churches (status frame), True the Vote, Ziklag, Nonprofit Explorer |
| FEC / state campaign-finance filings | 7 | Free the Files (diff target), c4 series, FEC collapse, CPPR, scam PACs, Marble (context), TTV (context) |
| Litigation & enforcement records (dockets, depositions, settlements, unsealed exhibits, FTC/DOJ actions) | 7 | Montana, CPPR (FPPC), scam PACs, Marble (testimony), TTV, churches (2009 ruling), FEC (MURs) |
| Leaked / windfall internal documents | 4 | Montana (meth-house files), scam PACs (insider emails), Ziklag (newsletters/videos), Ad Collector (platform-held data liberated by users) |
| FOIA / records requests | 4 | churches (IRS caseload), Marble, c4 series (applications), FEC/IRS coverage |
| Constructed corpora (crowdsourced extraction, instrumented collection, AV monitoring) | 4 | Free the Files, Ad Collector, churches, 527 database build |
| Corporate registries (state SoS, foreign registries) | 3 | Marble (IL + Nova Scotia), CPPR alias resolution, Montana |
| Expert adjudication panels (tax-law professors converting facts into legal significance) | 4 | c4 series, churches, Ziklag, Marble |

Notable: near-total absence of anonymous-single-source narrative — the cluster's evidentiary spine is *paired self-reported filings* plus *adversarial documents* (court records), with leaks used to establish intent, never scale.

### 2. Recurring detection signatures (frequency)
| Signature | Count | Where |
|---|---|---|
| two-books-diff (incl. application-vs-conduct variant) | 6 | c4 series (990 vs FEC; 1024 vs FEC), Montana (application vs conduct), TTV (990 vs court records), churches (status vs broadcast conduct), Ziklag (internal intent vs c3 status), Free the Files (station files vs FEC) |
| grant-chain-tracing | 4 | c4 series (c4→c4 grants), CPPR/Koch (the exemplar), Ziklag, Nonprofit Explorer (enabler) |
| enforcement-denominator / policy-shadow-measurement | 4 | FEC/IRS collapse, churches, scam PACs (FEC $3,500 fine), 527 mills |
| silo-join-on-hard-identifier (EIN/officer/address/vendor) | 4 | Marble (officer names across registries), CPPR (alias LLCs), 527 mills (treasurer/accountant/processor), Nonprofit Explorer |
| crowdsourced-document-liberation / adversarial-instrumentation | 3 | Free the Files, Ad Collector, churches (stream review + reader submissions) |
| internal-rulebook-acquisition | 3 | Montana, Ziklag, scam PACs (call scripts) |
| expenditure-composition-ratio | 2 | scam PACs (both waves) — plus CPPR officer-fee share as a cousin |
| temporal-correlation | 2 | c4 series (same-day ad/application), Ziklag (revenue ramp vs election cycles) |
| new-entity-first-filing-watch | 1 (high leverage) | Marble |

### 3. Transferable pattern candidates

**P1. Two-Books Diff (the flagship)**
Mechanics: Every regulated actor reporting to two authorities with different incentives (tax authority wants "not political"; election authority forces spending disclosure; a court record forces truth under adversarial pressure) will, under stress, keep inconsistent books. Enumerate entities present in both filing universes, normalize identity (EIN, name, treasurer), and diff the self-characterizations — including the *attestation layer* (applications, registrations) against the *conduct layer* (spending, broadcast behavior, internal documents). The contradiction is simultaneously the lead, the proof, and often an independent violation (false statement).
Minimum data: two overlapping filing systems with entity identifiers and at least one quantitative or yes/no field carried in both (e.g., 990 Schedule C political expenditure vs FEC IE totals; application question on politics vs any dated political act).
Recognition cue: same entity name/EIN in two silos with a zero/None in one where the other shows activity; or a registration/attestation dated *after* observable regulated conduct.

**P2. Conduit Grant-Chain Tracing with Alias Resolution**
Mechanics: Anonymous money acquires direction through intermediary nonprofits. Build the directed graph from 990 Schedule I grants (grantor side) reconciled against recipients' reported revenue; resolve disregarded-entity LLC/DBA grant names to parent orgs via state registries and filing footnotes; score hubs by throughput/program-expense ratio, address type (P.O. box), officer-vendor fee overlap, and election-cycle timing of flows. The hub with maximal throughput and minimal substance (CPPR: $137M/yr from a $72 P.O. box, $24M to officer-owned firms) is the operational center; its fee flows identify the human operators.
Minimum data: 990 e-file grant schedules for 2+ tiers, corporate registry access for alias resolution, FEC (or equivalent) spending for terminal nodes.
Recognition cue: nonprofit whose grants-out ≈ revenue-in, granted mostly to orgs that also mostly regrant; grant recipients that don't resolve to a known EIN (alias); vendor payments to firms sharing officers with the hub.

**P3. Fundraising-Mill Composition Ratio + Operator Clustering**
Mechanics: Committees/charities that exist for their fundraisers are detectable from their own filings: programmatic output (candidate contributions, IEs, grants, program expense) divided by total spending falls below ~5%, with the residual concentrated in professional-fundraiser/telemarketer fees. The individual mill is a misdemeanor; the *cluster* is the story — group flagged entities on shared treasurers, accountants, fundraising vendors, payment processors, addresses, and website templates to reveal a single enterprise wearing many sympathetic masks (veterans, police, breast cancer, election integrity).
Minimum data: committee-level receipts/disbursements (FEC bulk, IRS 8872, or state charity reports incl. Schedule G), with vendor/treasurer fields; optionally web artifacts for template matching.
Recognition cue: emotional-cause branding + high telemarketing fees + shared back-office identifiers across "unrelated" committees; regulator response absent or trivially small (a $3,500 fine against a $10M mill is confirmation, not refutation).

**P4. Enforcement-Denominator Measurement (regulatory abdication as the finding)**
Mechanics: Construct the violation base rate yourself (journalist-found violations, deadlock share of enforcement votes, dollars of undisclosed spending), then obtain the regulator's own output series (FOIA caseload stats, vote records, penalty totals) and publish the ratio. The gap both quantifies capture/paralysis and *predicts* where money migrates next — every other pattern in this cluster flourished precisely where this ratio collapsed (FEC deadlocks → scam PACs; church-audit freeze → pulpit politics; IRS c4 retreat → dark-money conduits).
Minimum data: any regulator's enforcement output over time + an independently constructible violation proxy for the same period.
Recognition cue: an agency whose action count trends to zero while regulated-activity volume grows; sentinel capitulations (approving the flagship violator); enforcement powers that exist on paper but require an officer/office that no longer exists.

**P5. Public-but-Unusable Corpus Liberation (constructed evidence infrastructure)**
Mechanics: When disclosure exists as unstructured PDFs (FCC political files), hostile data dumps (IRS 527 files, 990 images), or platform-internal state (Facebook ad targeting), the investigative act is building the dataset: consensus crowdsourcing, edge instrumentation with privacy stripping, or a permanent public utility (Nonprofit Explorer). The resulting corpus then feeds patterns P1–P4 — and compounds across investigations and outside users. Expect resistance from the data holder (Facebook's blocking) and design collection channels as perishable.
Minimum data: any legally public but practically inaccessible record class; a validation scheme (multi-reviewer consensus, classifier + human rating loop, or authoritative identifiers).
Recognition cue: a filing system everyone cites but no one can query; a regulator that "publishes" without structure; a platform holding the disclosure layer of a market. Standing question for any investigation: does a Nonprofit-Explorer-equivalent exist for this record system — and if not, is building it the highest-leverage move?
