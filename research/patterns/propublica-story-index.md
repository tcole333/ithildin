# ProPublica Story Index — Per-Story Evidence Base

The coded corpus behind every frequency claim in [propublica-ontology.md](propublica-ontology.md) and
[detection-signatures.md](detection-signatures.md). Distilled from the full extraction reports in
`_intake/propublica/` (reports 01–16), which carry the complete entries with per-claim citations; this index
compresses each story to its evidence skeleton.

**Entry fields** — URL; Partner/awards; Found (core finding); Types (finding-type tags, the coding vocabulary
of ontology §1/§6–7); Evidence (typed sources with acquisition mode); Systems (specific named record systems —
the raw material for [adapter-gaps.md](adapter-gaps.md)); Signature (the detection move — cards in
detection-signatures.md); Method (cited methodology page vs [inferred]); Impact (official consequences).
Wave-1 clusters (reports 01–08) were coded against a seed taxonomy (extended freely, NEW tags marked in the
source reports); report-09 covers methodology infrastructure; wave-2 clusters (reports 11–16) were coded
free-form with no seed taxonomy. Report-10 (the corpus census) has no story entries — it is the sampling frame.

---

## Tax & wealth (report-01)

### The Secret IRS Files: Trove of Never-Before-Seen Records Reveal How the Wealthiest Avoid Income Tax (2021) — tax-wealth
- URL: https://www.propublica.org/article/the-secret-irs-files-trove-of-never-before-seen-records-reveal-how-the-wealthiest-avoid-income-tax
- Partner/awards: ProPublica original; series won 2022 Selden Ring, 2022 Hillman Prize (web), Barlett & Steele Gold 2021
- Found: Top-25 billionaires' wealth grew $401B (2014-18) vs $13.6B income tax — 3.4% "true tax rate"; Bezos, Musk, Soros, Icahn had $0-tax years.
- Types: wealth-defense-technique; statistical-outlier-practitioner; realization-avoidance; means-test-gaming
- Evidence: leaked IRS bulk microdata (15+ years, returns + information returns + trade records); Forbes wealth series (public); court/disclosure fragments for verification; direct subject confirmation
- Systems: IRS bulk microdata (leak); Forbes billionaire wealth list; IRS Publication 1304 definitions
- Signature: denominator-substitution-rate-construction: leaked tax-paid joined to Forbes wealth-growth per person/year; rate against wealth delta collapses 20-37% to 0.1-3.4%; flag $0 years.
- Method: https://www.propublica.org/article/how-we-calculated-the-true-tax-rates-of-the-wealthiest
- Impact: Senate Finance probe call; Biden Billionaire Minimum Income Tax proposal; leaker sentenced.

### Lord of the Roths: How Peter Thiel Turned a Retirement Account for the Middle Class Into a $5 Billion Tax-Free Piggy Bank (2021) — tax-wealth
- URL: https://www.propublica.org/article/lord-of-the-roths-how-tech-mogul-peter-thiel-turned-a-retirement-account-for-the-middle-class-into-a-5-billion-dollar-tax-free-piggy-bank
- Partner/awards: ProPublica original; part of awarded series
- Found: Thiel's Roth IRA bought 1.7M PayPal founders' shares at $0.001 ($1,700, under $2,000 cap); grew to ~$5B permanently income-tax-free.
- Types: wealth-defense-technique; statistical-outlier-practitioner; preferential-carve-out
- Evidence: leaked IRS microdata (custodian IRA valuations); SEC filings (public); court documents; Thiel's 2005 NZ residency application (Official Information Act release)
- Systems: IRS microdata / Form 5498-type IRA valuations (leak); SEC issuance filings; NZ OIA residency file
- Signature: impossible-value-vs-legal-limit: $5B balance unreachable under $2,000/yr cap proves in-kind pricing; silo-join IRS values to SEC issuance identifies which asset entered.
- Method: [inferred]
- Impact: Senate crackdown signals; mega-IRA caps drafted into Build Back Better.

### The Billionaire Playbook: How Sports Owners Use Their Teams to Avoid Millions in Taxes (2021) — tax-wealth
- URL: https://www.propublica.org/article/the-billionaire-playbook-how-sports-owners-use-their-teams-to-avoid-millions-in-taxes
- Found: Ballmer reported $700M tax losses on the profitable Clippers (~$140M saved); 2004 amortization rule taxed him at 12% vs LeBron's 35.9%.
- Types: wealth-defense-technique; paper-loss-manufacturing; preferential-carve-out
- Evidence: leaked IRS microdata (K-1/Schedule E business loss capture); leaked NBA internal financials; court and corporate-registration records (public); franchise purchase prices/valuations
- Systems: IRS microdata (leak); leaked NBA internal financials; state corporate registries; Forbes franchise valuations
- Signature: tax-books-vs-operations-diff: IRS-reported entity losses attributed to owners via registries, diffed against leaked league profits and rising valuations; owner/player/worker rate comparison.
- Method: [inferred]
- Impact: IRS opened scrutiny of sports-owner tax avoidance (2024).

### More Than Half of America's 100 Richest People Exploit Special Trusts to Avoid Estate Taxes (2021) — tax-wealth
- URL: https://www.propublica.org/article/more-than-half-of-americas-100-richest-people-exploit-special-trusts-to-avoid-estate-taxes
- Partner/awards: ProPublica original; part of awarded series
- Found: More than half the Forbes 100 (Bloomberg, Kochs, Waltons, Zuckerberg) use GRATs or similar trusts; pioneer estimated ~$100B Treasury cost over 13 years.
- Types: wealth-defense-technique; statistical-outlier-practitioner (population-prevalence)
- Evidence: leaked IRS microdata (trust entities, annuity flows); SEC filings naming GRAT trusts (public); historical archives — letters, diaries, congressional records for dynasty companion
- Systems: IRS microdata (leak); SEC Form 4/13D trust-name strings; congressional/archival records
- Signature: artifact-string-census: count Forbes-100 members whose tax records or filings explicitly mention GRAT-type trusts — prevalence statistic ("more than half"), not anecdote.
- Method: [inferred]
- Impact: Fed 2021 Build Back Better grantor-trust crackdown drafts; provisions later dropped.

### Secret IRS Files Reveal How Much the Ultrawealthy Gained by Shaping Trump's "Big, Beautiful Tax Cut" (2021) — tax-wealth
- URL: https://www.propublica.org/article/secret-irs-files-reveal-how-much-the-ultrawealthy-gained-by-shaping-trumps-big-beautiful-tax-cut
- Found: Ron Johnson's holdout pushed §199A to 20%; donors Uihlein/Hendricks took $118M/$97M deductions; 82 households gained >$1B; eight inserted words qualified Bechtel ($111M).
- Types: preferential-carve-out; undisclosed-benefit-to-official (inverted); influence-laundering-via-intermediaries
- Evidence: leaked IRS microdata (per-household deductions); lobbying disclosures (public); Treasury emails/calendars (FOIA litigation); successive bill drafts and conference reports
- Systems: IRS microdata (leak); lobbying disclosure filings; FOIA-litigated Treasury emails/calendars; bill drafts/conference reports
- Signature: legislative-diff-to-beneficiary-join: diff bill drafts, isolate inserted eight words, compute who newly qualifies, name first-year winners in microdata, overlay donation timelines.
- Method: [inferred]

### America's Highest Earners and Their Taxes Revealed (2022) — tax-wealth
- URL: https://projects.propublica.org/americas-highest-incomes-and-taxes-revealed/
- Found: Named top-400 by reported income (entry >=$110M/yr): Gates $2.85B/yr at 18.4%, Bloomberg 4.1%; a $200K couple can out-pay a $200M earner.
- Types: wealth-defense-technique (income-character arbitrage); rate-regressivity-at-apex; records-suppression-adjacent
- Evidence: leaked IRS microdata 2013-2018; public payroll-tax parameters and rate schedules for the comparison couple
- Systems: IRS microdata (leak); payroll-tax/rate schedules
- Signature: denominator-construction: rebuild the named top-400 income league table officials publish only anonymized; compute cohort rate curve showing decline at the apex.
- Method: https://projects.propublica.org/americas-highest-incomes-and-taxes-revealed/

### How the Wealthy Save Billions in Taxes by Skirting a Century-Old Law (2023) — tax-wealth
- URL: https://www.propublica.org/article/irs-files-taxes-wash-sales-goldman-sachs
- Found: Goldman's "Tax Advantaged Loss Harvesting" skirted the 1921 wash-sale rule via near-identical swaps; Ballmer generated ~$579M losses (>=$138M saved) without portfolio change.
- Types: paper-loss-manufacturing; wealth-defense-technique; fraud-enablement-by-design
- Evidence: leaked IRS microdata with voluminous per-trade records (two decades); public securities reference data establishing near-identical pairs (share classes, dual listings)
- Systems: IRS microdata incl. trade-level records (leak); securities reference data
- Signature: substitution-pair-detection: for each loss sale, find same-taxpayer +/-30-day purchases of economic twins that are legal non-twins; cluster by custodian to expose Goldman's program.
- Method: [inferred]

### Meet the Billionaire and Rising GOP Mega-Donor Who's Gaming the Tax System / How Susquehanna's Jeff Yass Avoided $1 Billion in Taxes (2022) — tax-wealth
- URL: https://www.propublica.org/article/jeff-yass-susquehanna-tiktok-tax-avoidance ; https://www.propublica.org/article/how-susquehanna-yass-avoided-billion-taxes
- Found: Yass averaged 19% on >$1B/yr high-frequency-trading income, saving >$1B over six years by converting short-term gains via offsetting long books and index shorts.
- Types: paper-loss-manufacturing; wealth-defense-technique; income-character-conversion
- Evidence: leaked IRS microdata (returns + trading records); SEC filings (public); IRS-dispute court records (>$100M back taxes); ex-Susquehanna insider interviews
- Systems: IRS microdata (leak); SEC filings; IRS-dispute court dockets
- Signature: income-character-anomaly: short-horizon trading firm reporting mostly long-term-rate income; reconstruct offsetting long-vs-index-short machinery; IRS disputes as confirming breadcrumb.
- Method: [inferred]

### IRS Audit of Trump Could Cost Former President More Than $100 Million (2024) — tax-wealth
- URL: https://www.propublica.org/article/trump-irs-audit-chicago-hotel-taxes
- Partner/awards: co-published with The New York Times
- Found: Trump deducted the same Chicago-tower loss twice — up to $651M declared worthless in 2008, then $168M more 2011-2020; IRS exposure >$100M.
- Types: two-books-asymmetry (temporal); paper-loss-manufacturing
- Evidence: anonymized 2019 IRS Technical Advice Memorandum (public); Trump tax records (prior NYT leak); NY AG 2022 filings; JCT report; six partnership-tax experts
- Systems: IRS Technical Advice Memorandum; NYT-held Trump tax records (prior leak); NY AG suit filings; Joint Committee on Taxation report
- Signature: de-anonymization-by-fact-join: match anonymized memo's fact pattern to known tax records; line up 2008 worthlessness against 2011-20 losses — same loss claimed twice.
- Method: [inferred]

### How the IRS Was Gutted (2018) — tax-wealth
- URL: https://www.propublica.org/article/how-the-irs-was-gutted
- Partner/awards: co-published with The Atlantic; "Gutting the IRS" series (21 stories)
- Found: IRS budget cut $14B to ~$11.5B; audits down 42%; millionaire audits fell ~80% while EITC recipients were 36% of all audits.
- Types: enforcement-regressivity; algorithmic-or-systematic-denial; regulatory-capture/revolving-door
- Evidence: IRS Data Books and enforcement statistics (public); internal collection and inspector-general reports; interviews with 50+ current/former IRS employees
- Systems: IRS Data Books; inspector-general/Treasury reports
- Signature: policy-shadow-measurement: decade time-series of IRS's own Data Books by income class shows millionaire enforcement collapsing while EITC audits persist; insiders supply mechanism.
- Method: [inferred]
- Impact: Credited with framing the Inflation Reduction Act's $80B IRS restoration.

### Where in the U.S. Are You Most Likely to Be Audited by the IRS? (2019) — tax-wealth
- URL: https://projects.propublica.org/graphics/eitc-audit
- Found: Humphreys County, MS — poor, majority-Black — is America's most-audited county (~11 audits/1,000 filings), 51% above the richest county, because EITC audits are cheap.
- Types: concentrated-harm-hotspot; algorithmic-or-systematic-denial; enforcement-regressivity; extraction-from-captive-population
- Evidence: ex-IRS economist Bloomquist's county audit-rate model built on open data (Tax Notes); IRS Data Book statistics; Census/ACS demographic overlay — no leak, no FOIA
- Systems: Bloomquist county audit-rate model; IRS Data Book; county return data (irs.gov); Census/ACS
- Signature: hotspot-mapping-from-model-data: (audit rate by return type) x (county return composition) estimates unpublished audit geography; demographic overlay exposes disparate impact.
- Method: https://projects.propublica.org/graphics/eitc-audit
- Impact: Congressional letters; IRS "efficient use" admission; fed 2023 under-$400K audit pledge.

### Never-Before-Seen Trump Tax Documents Show Major Inconsistencies (2019) — tax-wealth
- URL: https://www.propublica.org/article/trump-inc-podcast-never-before-seen-trump-tax-documents-show-major-inconsistencies
- Partner/awards: WNYC "Trump, Inc." podcast co-production
- Found: 40 Wall Street occupancy reported 58.9% to lender vs 81% to tax authorities; Columbus Circle tax-reported income ran ~81% of lender-reported over eight years.
- Types: two-books-asymmetry
- Evidence: NYC property-tax appeal income/expense statements (FOIL); CMBS loan-level disclosures public via Ladder Capital securitization; a dozen real-estate expert reviews
- Systems: NYC property-tax appeal filings (FOIL); CMBS servicer reports/offering documents
- Signature: two-books-diff: join FOIL tax-appeal statements to CMBS servicer data on property+year; diff occupancy/rent/insurance; incentive-signed gap directions are the fraud tell.
- Method: [inferred]
- Impact: NYC officials referred discrepancies for investigation; anticipated NY AG 2022 case.

### The Billion-Dollar Loophole (2017) — tax-wealth
- URL: https://www.propublica.org/article/conservation-easements-the-billion-dollar-loophole
- Partner/awards: co-published with Fortune; National Press Club Lee Walczak Award
- Found: Syndicated conservation easements sold $4-$9 of deduction per $1 invested (Millstone: bought $9.8M, appraised $41M); EcoVest's 96 syndications drove >$2B deductions.
- Types: valuation-arbitrage; fraud-enablement-by-design; charity-mission-inversion
- Evidence: promoter placement memos (insider-provided); land deeds vs claimed appraisals (public); IRS aggregate deduction data; recorded conversations; land-trust/appraiser interviews
- Systems: county deed records; promoter private-placement memoranda; IRS aggregate analyses
- Signature: purchase-price-vs-claimed-value: deed price joined to value claimed months later; 4-9x multiples flag shelters; cluster by promoter and repeat appraiser.
- Method: [inferred]
- Impact: DOJ sued EcoVest; promoters convicted (25/23 years); SECURE 2.0 capped deductions.

### The TurboTax Trap: TurboTax Deliberately Hides Its Free File Page From Search Engines (2019) — tax-wealth
- URL: https://www.propublica.org/article/turbotax-deliberately-hides-its-free-file-page-from-search-engines
- Found: Intuit put noindex,nofollow on the TurboTax Free File page while the paid page carried index,follow; Free File uptake was ~3% of eligible filers.
- Types: dark-pattern-suppression-of-public-benefit; algorithmic-or-systematic-denial; fraud-enablement-by-design; regulatory-capture/revolving-door
- Evidence: live page-source robots directives (self-authenticating, public); IRS Free File MOU and uptake statistics; crowdsourced user walkthroughs; later internal Intuit documents and FTC/state-AG records
- Systems: robots meta directives/robots.txt page source; IRS Free File MOU/uptake stats; FTC and state-AG case records
- Signature: compliance-artifact-inspection: diff machine-readable accessibility of the obligated free page (noindex) vs the paid page (index,follow) — intent written in config.
- Method: [inferred]
- Impact: $141M 50-state settlement; FTC deception order; IRS built Direct File.

## Judicial ethics (report-02)

### Clarence Thomas and the Billionaire (2023) — judicial-ethics
- URL: https://www.propublica.org/article/clarence-thomas-scotus-undisclosed-luxury-travel-gifts-crow
- Partner/awards: anchor of the 2024 Pulitzer Public Service series (also Selden Ring, IRE 2024)
- Found: 20+ years of undisclosed Crow gifts: jet flights, Michaela Rose yacht cruises ($500K+ Indonesia trip), annual Camp Topridge stays — none on disclosure forms.
- Types: undisclosed-benefit-to-official; access-brokerage; recusal-failure
- Evidence: FAA + FlightAware jet histories (public); dozens of interviews (~15 ex-yacht crew, Topridge staff); Instagram/plane-spotter artifacts; Fix-the-Court-obtained SCOTUS security records; Crow foundation filings
- Systems: FAA registry; FlightAware; justices' disclosure filings; SCOTUS security records (via Fix the Court); Crow foundation 990s; Instagram/Facebook artifacts
- Signature: disclosure-gap-triangulation: travel ledger from tail-number histories + crew testimony + dated artifacts anti-joined to disclosure filings; Dallas-to-Dulles positioning legs as the tell.
- Method: https://www.propublica.org/article/clarence-thomas-harlan-crow-investigation-origins
- Impact: Senate hearings within days; SCOTUS adopted first code of conduct Nov 2023.

### Billionaire Harlan Crow Bought Property From Clarence Thomas (2023) — judicial-ethics
- URL: https://www.propublica.org/article/clarence-thomas-harlan-crow-real-estate-scotus
- Found: Crow LLC bought Thomas-family Savannah properties for $133,363 (2014), undisclosed despite 5 U.S.C. 13104; Thomas's mother stayed on, taxes and $36K renovations paid.
- Types: undisclosed-benefit-to-official; self-dealing/related-party; influence-laundering-via-intermediaries
- Evidence: Chatham County warranty deed and tax rolls (public); Savannah permit filings; TX-to-DE corporate registry chain to Crow; Free Law Project disclosure archive; neighbor interviews
- Systems: Chatham County deed index/tax rolls; Savannah permit records; Texas SoS registry; Free Law Project disclosure DB
- Signature: silo-join-on-hard-identifier: grantor/grantee deed index searched on the official's name; buyer LLC de-anonymized via TX-DE registry hop; anti-joined against 13104 schedule.
- Method: [inferred]
- Impact: Thomas amended disclosure Aug 2023; watchdog sought DOJ investigation.

### Clarence Thomas Had a Child in Private School. Harlan Crow Paid the Tuition (2023) — judicial-ethics
- URL: https://www.propublica.org/article/clarence-thomas-harlan-crow-private-school-tuition-scotus
- Found: Crow paid ~$100K+ boarding-school tuition for Thomas's grandnephew; $6,200 Crow Holdings wire surfaced in school's bankruptcy docket; 2002 Dixon tuition gift was disclosed.
- Types: undisclosed-benefit-to-official; prior-disclosure-self-contradiction
- Evidence: Hidden Lake Academy bankruptcy-court filings incl. bank statement (public, deeply buried); ex-administrator Grimwood on record; Thomas's 2002 disclosure as self-contradiction exhibit
- Systems: Hidden Lake Academy bankruptcy docket; Thomas disclosure filings
- Signature: defunct-institution-docket-mining: bankruptcy exhibits of institutions serving the target searched for benefactor entity wires; prior-disclosure-precedent-diff proves rule knowledge.
- Method: [inferred]

### Justice Samuel Alito Took Luxury Fishing Vacation With GOP Billionaire Who Later Had Cases Before the Court (2023) — judicial-ethics
- URL: https://www.propublica.org/article/samuel-alito-luxury-fishing-trip-paul-singer-scotus-supreme-court
- Found: Singer flew Alito to Alaska 2008 (charter >$100K), undisclosed; Singer entities then appeared >=10 times at Court incl. $2.4B NML win — no recusal.
- Types: undisclosed-benefit-to-official; recusal-failure; access-brokerage; prebuttal-response-anomaly
- Evidence: trip-planning emails (insider); FAA flight data; Alaska fishing-license records; Scalia papers at Harvard; pilot/guide/lodge interviews; SCOTUS docket research on Elliott/NML matters
- Systems: FAA flight data; Alaska fishing-license records; Scalia papers (Harvard Law Library); SCOTUS dockets
- Signature: temporal-correlation: trip fixed via licenses/flight data/photos, joined forward against benefactor's entity-resolved Court docket footprint — benefit-then-adjudication with no recusal entry.
- Method: [inferred]
- Impact: Senate Judiciary letters to Singer, Leo, Arkley; fed code of conduct.

### How Harlan Crow Slashed His Tax Bill by Taking Clarence Thomas on Superyacht Cruises (2023) — judicial-ethics
- URL: https://www.propublica.org/article/harlan-crow-slashed-tax-bill-clarence-thomas-superyacht
- Partner/awards: draws on the Secret IRS Files trove
- Found: Crow's yacht ran through Rochelle Charter Inc.: ~$8M losses over 13 years, ~$4M deductions to Crow; ~12 ex-crew recall zero genuine charters.
- Types: sham-enterprise-tax-writeoff; two-books-asymmetry; undisclosed-benefit-to-official
- Evidence: leaked IRS return microdata 2003-2015; ~12 former crew interviews; internal cruising schedules; USPTO trademark prosecution file (public); counsel letters to Senate Finance
- Systems: Secret IRS Files microdata (leak); USPTO TSDR trademark file; Senate Finance correspondence
- Signature: paper-claim-vs-operational-reality: hobby-loss persistence in microdata vs crew testimony of zero charters vs failed USPTO commercial-use specimens; loss-persistence screens, operations evidence kills.
- Method: [inferred]
- Impact: Senate Finance (Wyden) investigation deepened doubt on the deductions.

### Clarence Thomas' 38 Vacations (2023) — judicial-ethics
- URL: https://www.propublica.org/article/clarence-thomas-other-billionaires-sokol-huizenga-novelly-supreme-court
- Found: At least 38 undisclosed vacations, 26 jet flights from a billionaire consortium (Huizenga, Sokol, Novelly); Horatio Alger Association as access architecture inside the Court.
- Types: undisclosed-benefit-to-official; benefactor-consortium-subsidy; reciprocal-access-exchange; access-brokerage
- Evidence: multi-tail flight data; USMS protective-detail and university-official emails (FOIA/open-records); Horatio Alger minutes and financials; tax-court filings; 100+ interviews; photo albums
- Systems: flight data; U.S. Marshals Service records (FOIA); university email records; Horatio Alger Association minutes; tax-court dockets
- Signature: named-cohort-tracing + denominator-construction: association roll as benefactor universe; per-benefactor gift ledger summed to "at least 38"; USMS records as shadow itinerary.
- Method: [inferred]
- Impact: Escalated toward Nov 2023 Senate subpoena authorization for Crow and Leo.

### Clarence Thomas Secretly Participated in Koch Network Donor Events (2023) — judicial-ethics
- URL: https://www.propublica.org/article/clarence-thomas-secretly-attended-koch-brothers-donor-events-scotus
- Found: Thomas secretly attended Koch donor summits (2018 Palm Springs, chartered G200) as a fundraising draw; the network litigated before him (Bonta, Loper Bright) without recusal.
- Types: undisclosed-benefit-to-official; access-brokerage; recusal-failure; influence-laundering-via-intermediaries
- Evidence: three former Koch officials plus a major donor (anonymous); internal briefing video via watchdog Documented; G200 flight records; 2008-vs-2018 disclosure diff; Bohemian Grove interviews
- Systems: Koch network internal video (via Documented); charter flight records; disclosure filings
- Signature: guest-manifest-reconstruction: closed-venue placement built from insiders/video/flight records; prior-disclosure-precedent-diff — 2008 disclosed as speech, 2018 omitted — shows deliberate framing.
- Method: [inferred]

### We Don't Talk About Leonard (2023) — judicial-ethics
- URL: https://www.propublica.org/article/we-dont-talk-about-leonard-leo-supreme-court-supermajority ; https://www.propublica.org/article/leonard-leo-wisconsin-documents-state-courts-republicans-judges
- Partner/awards: co-published with WNYC's On the Media; state installment with The Guardian
- Found: Leo-orbit groups raised $600M+ (2014-20) before the $1.6B Marble windfall; $25K routed to Ginni Thomas "no mention of Ginni"; $51M Wisconsin judicial race.
- Types: access-brokerage; influence-laundering-via-intermediaries; state-judicial-capture; lifestyle-income-mismatch
- Evidence: thousands of pages of court documents, 990s, emails; Abbott calendar records; Missouri governor emails (via AP settlement); Guardian's 1,500-page Wisconsin John Doe leak archive; 100+ interviews
- Systems: IRS 990s (JCN/Concord conduits); Texas governor calendar records; Missouri governor's-office emails; Wisconsin "John Doe" trove; Maine deed records
- Signature: conduit-flow-join: 990 grant flows funder-to-JCN/Concord-to-state races joined with operative emails; lifestyle-vs-known-income diff (Maine mansion) flags broker self-enrichment.
- Method: [inferred]
- Impact: Senate Judiciary authorized Leo subpoena; DC AG self-enrichment inquiry.

### The Judiciary Has Policed Itself for Decades. It Doesn't Work. (2023) — judicial-ethics
- URL: https://www.propublica.org/article/judicial-conference-scotus-federal-judges-ethics-rules
- Found: Judicial Conference disclosure committee never referred a falsified report to DOJ; 2011-12 Thomas complaints closed uninvestigated; disclosure rules diluted between draft and final.
- Types: institutional-coverup/records-suppression; regulatory-capture; preferential-carve-out
- Evidence: internal Judicial Conference/Administrative Office memos and rule-softening emails; FOIA'd 2011-12 complaint records; Mecham archives (Stanford/Utah); whistleblower Wendy Smith plus nine judges; GAO reports
- Systems: Judicial Conference/AO internal records; Mecham papers (Stanford, Utah); GAO reports
- Signature: zero-output-enforcement-baseline: decades of committee output (DOJ referrals: zero) against intake proves capture; rulemaking-draft-vs-final diff with internal emails shows gaps designed.
- Method: [inferred]
- Impact: Frames the SCOTUS code of conduct's central defect — no enforcement mechanism.

### A "Delicate Matter": Clarence Thomas' Private Complaints About Money Sparked Fears He Would Resign (2023) — judicial-ethics
- URL: https://www.propublica.org/article/clarence-thomas-money-complaints-sparked-resignation-fears-scotus
- Found: 2000 Mecham memo: Thomas ($173,600 salary, $267K RV loan) warned justices would resign without raises; private benefactor subsidies then substituted for the raise.
- Types: benefactor-subsidy-substitution; undisclosed-benefit-to-official
- Evidence: Stearns correspondence (GWU Special Collections); confidential Mecham-to-Rehnquist memo obtained by ProPublica; CourtListener disclosure database; friend and ex-lawmaker interviews
- Systems: GWU Special Collections (Stearns papers); Mecham memo (internal judiciary record); CourtListener disclosure DB
- Signature: archival-collection-anchor: dated internal memo fixes financial distress at T0; the gift ledger time-ordered against T0 shows subsidies accelerating as public remedies failed.
- Method: [inferred]

### How a Secretive Billionaire Handed His Fortune to the Architect of the Right-Wing Takeover of the Courts (2022) — judicial-ethics
- URL: https://www.propublica.org/article/dark-money-leonard-leo-barre-seid
- Partner/awards: with The Lever (Andrew Perez)
- Found: Seid moved 100% of Tripp Lite into Leo's Marble Freedom Trust before the $1.65B Eaton sale, dodging ~$400M tax; registry shows handwritten officer swap.
- Types: influence-laundering-via-intermediaries; pre-liquidity-asset-donation; two-books-asymmetry
- Evidence: Marble Freedom Trust's first Form 990; Illinois SoS officer strike-through filings; Nova Scotia subsidiary filings; Eaton M&A record (SEC/press); tax-professor validation — all public
- Systems: Marble Freedom Trust Form 990; Illinois SoS filings; Nova Scotia corporate registry; SEC/press M&A record
- Signature: officer-succession-registry-diff: infant nonprofit's first-990 revenue matched to a same-size acquisition on amount/period; registry strike-through dates control transfer pre-liquidity.
- Method: [inferred]

### These Judges Can Have Less Training Than Barbers (2019) — judicial-ethics
- URL: https://www.propublica.org/article/these-judges-can-have-less-training-than-barbers-but-still-decide-thousands-of-cases-each-year
- Partner/awards: Joseph Cranney, The Post and Courier, via ProPublica Local Reporting Network
- Found: South Carolina's 319 magistrates handle ~800,000 cases/year; ~75% lack law degrees; 57.5 required training hours vs 1,500 for barbers; 25% in holdover status.
- Types: unqualified-gatekeeper-bench; institutional-coverup/records-suppression; regulatory-capture
- Evidence: Office of Disciplinary Counsel files and appointment archives (state records requests); case files and courtroom audio; ACLU/NACDL court-watch data; constructed bench-wide roster from thousands of records
- Systems: SC Office of Disciplinary Counsel files; magistrate appointment archives; courtroom audio; ACLU/NACDL court-watching datasets
- Signature: denominator-construction: full 319-magistrate roster with credential/training/term/discipline attributes turns anecdotes into system rates; licensing bar benchmarked against barbers.
- Method: [inferred]
- Impact: Reform bills; governor ordered disciplinary-history disclosure for magistrate candidates.

### North Carolina Supreme Court Secretly Squashed Discipline of Two GOP Judges (2024) — judicial-ethics
- URL: https://www.propublica.org/article/north-carolina-supreme-court-republican-judges-violations
- Found: Republican-majority court secretly rejected recommended reprimands of two GOP judges — the only rejections in a decade — while a Black Democratic judge got 120-day suspension.
- Types: institutional-coverup/records-suppression; partisan-discipline-asymmetry; state-judicial-capture
- Evidence: three confidential sources with direct knowledge of sealed decisions; Judicial Standards Commission annual reports since 2011 (public baseline); transcripts and courtroom recordings; party-registration records
- Systems: Judicial Standards Commission annual reports; court transcripts/recordings; voter party-registration records
- Signature: zero-output-baseline-inverted: public annual reports establish rejections essentially never happen; insider testimony of two secret co-partisan rejections makes the deviation the finding.
- Method: [inferred]

## Dark money (report-03)

### Buying Your Vote / Free the Files (2012) — dark-money
- URL: https://projects.propublica.org/free-the-files/
- Partner/awards: ~1,000 volunteers; Huffington Post distribution partnership
- Found: Volunteers structured ~16,000 FCC ad-contract files across 33 swing markets, logging ~$1B in 2012 TV buys including dark-money spending invisible in FEC data.
- Types: donor-anonymization-technique; two-books-asymmetry; evidence-infrastructure
- Evidence: FCC public-inspection ad contracts (open-but-unusable PDFs); volunteer-extracted structured dataset with two-reviewer consensus per field; FEC independent-expenditure reports for the gap comparison
- Systems: FCC public inspection files; PACTrack database; FEC IE/electioneering reports
- Signature: crowdsourced-document-liberation: two-volunteer consensus per data point structured regulatory PDFs; joined to PACTrack buyer identities; diffed against FEC to expose unreported spending.
- Method: https://www.propublica.org/article/crowdsourcing-campaign-spending-what-we-learned-from-free-the-files
- Impact: Credited with pushing FCC political-file digitization expansion [inferred].

### How Nonprofits Spend Millions on Elections and Call It Public Welfare (2012-13) — dark-money
- URL: https://www.propublica.org/article/how-nonprofits-spend-millions-on-elections-and-call-it-public-welfare
- Partner/awards: ProPublica original (Kim Barker); Toner Prize honorable mention
- Found: At least 32 of 104 politically active nonprofits reported election spending to FEC while telling IRS zero; c4s outspent super PACs on presidential TV ($71M vs $56M).
- Types: two-books-asymmetry; application-vs-conduct-gap; conduit-network; donor-anonymization-technique
- Evidence: 990s of 107 nonprofits; FEC and state election filings (public); Form 1024 exemption applications incl. confidential pending ones improperly released by IRS; YouTube/TV ad timestamps
- Systems: IRS 990s/Schedule C; FEC filings; Form 1024 applications; YouTube ad uploads
- Signature: two-books-diff: same org's IRS answers and application attestations vs FEC/state spending joined on name/EIN; every FEC>0, IRS=0 row is a finding.
- Method: [inferred]
- Impact: Fed 2013-14 IRS proposed c4 political-activity rules debate [inferred].

### Big Sky, Big Money — Western/American Tradition Partnership (2012) — dark-money
- URL: https://www.propublica.org/article/documents-found-in-meth-house-bare-inner-workings-of-dark-money-group
- Partner/awards: FRONTLINE + Marketplace; IRE Award for the joint dark-money reporting
- Found: Meth-house-found WTP files showed candidate coordination; court-ordered bank records made it the first modern dark-money group with all donors public (~$1.1M).
- Types: donor-anonymization-technique; application-vs-conduct-gap; influence-laundering-via-intermediaries; undisclosed-candidate-coordination
- Evidence: internal WTP files held by state investigators (windfall discovery); court-unsealed bank records and donor checks; Montana Commissioner of Political Practices rulings; WTP's IRS exemption application
- Systems: WTP internal files (state custody); court-unsealed bank records; Montana COPP rulings; IRS exemption application
- Signature: internal-rulebook-acquisition: the group's own solicitations marketed anonymity; application-vs-conduct diff against state rulings; released checks enabled complete donor-graph ground truth.
- Method: [inferred]

### Regulators in Retreat: FEC gridlock and the IRS's dark-money surrender (2011-2016) — dark-money
- URL: https://www.propublica.org/article/as-political-donors-push-envelope-fec-gridlock-gives-de-facto-green-light
- Found: FEC 3-3 deadlocks operate as a de facto green light; IRS granted Crossroads GPS exemption after $70M+ political spending; c4s spent $256M+ on 2012 elections.
- Types: fraud-enablement-by-design; preferential-carve-out
- Evidence: congressional oversight testimony; FEC commissioner statements and MUR enforcement files; FEC vote/enforcement outcomes; IRS approval records and scandal-era documents — all public
- Systems: FEC MUR files and vote records; IRS determination records; congressional testimony
- Signature: enforcement-denominator: ratio of regulator output (concluded votes, penalties, denials) to measurable violation base; sentinel capitulations like the Crossroads approval mark collapse.
- Method: [inferred]

### The Dark Money Man: Sean Noble, the Center to Protect Patient Rights, and the Koch conduit network (2014) — dark-money
- URL: https://www.propublica.org/article/the-dark-money-man-how-sean-noble-moved-the-kochs-cash-into-politics-and-ma
- Found: Noble's CPPR routed ~$137M (2012) from a $72/yr P.O. box; his own firms took ~$24M; $11M California laundering ended in record $1M FPPC settlement.
- Types: conduit-network; influence-laundering-via-intermediaries; fundraising-mill-self-enrichment; donor-anonymization-technique
- Evidence: 990 grant and contractor-fee schedules of CPPR/Koch nonprofits; FEC filings of recipients; California FPPC investigation file with depositions and recorded interviews; property records; dozens of anonymous interviews
- Systems: IRS 990 Schedule I; FEC filings; California FPPC investigation file; property records; state registries (ASMI/SLAH/TOHE alias LLCs)
- Signature: grant-chain-tracing + alias-resolution: donor-intermediary-spender graph from Schedule I; disregarded-entity LLC aliases resolved via registries; hub anomalies — P.O. box, officer-vendor fees ~17%.
- Method: [inferred]

### Facebook Political Ad Collector (2017-2019) — dark-money
- URL: https://www.propublica.org/article/how-we-are-monitoring-political-ads-on-facebook
- Partner/awards: international newsroom partners (Germany, Italy, Australia, Austria); later stewardship by Quartz and The Globe and Mail
- Found: Thousands of volunteers' browser extensions archived targeted Facebook political ads plus targeting metadata the platform never disclosed; Facebook blocked the tool January 2019.
- Types: donor-anonymization-technique; evidence-infrastructure; fraud-enablement-by-design
- Evidence: crowd-collected ad corpus with Facebook's own targeting explanations captured client-side with consent; Naive Bayes political-ad classifier trained by volunteer ratings; open-sourced extension code
- Systems: volunteer browser-extension ad corpus; Facebook targeting metadata; Naive Bayes classifier; GitHub (propublica/facebook-political-ads)
- Signature: adversarial-instrumentation: distribute collection to consenting users at the platform edge; classifier turns raw capture into the domain corpus; platform's own metadata becomes the disclosure.
- Method: https://www.propublica.org/article/how-we-are-monitoring-political-ads-on-facebook
- Impact: Facebook inserted blocking code, turning platform opacity itself into the story.

### Scam PACs and political-fundraising mills (2019/2024) — dark-money
- URL: https://www.propublica.org/article/conservative-majority-fund-political-fundraising-pac-kelley-rogers ; https://www.propublica.org/article/political-nonprofits-fundraising-ftc-irs-527s-pacs
- Partner/awards: 2019 story co-published with POLITICO
- Found: Conservative Majority Fund raised ~$10M, directed $48,400 to politics; 2024: ten linked 527s raised $33M+ and spent ~90% on fundraising.
- Types: fundraising-mill-self-enrichment; charity-mission-inversion; fraud-enablement-by-design; conduit-network
- Evidence: FEC receipts/disbursements; IRS Form 8872 527 data rebuilt into a searchable database; insider emails on call scripts (2019); Cuccinelli suit, DOJ wire-fraud and FTC records; web-template artifacts
- Systems: FEC bulk filings; IRS Form 8872 527 data; FTC/DOJ case records; website templates and payment processors (clustering keys)
- Signature: expenditure-composition-ratio: political output over total disbursements under ~5% flags mills; vendor-network-clustering on treasurers/accountants/processors/templates reveals one enterprise behind many committees.
- Method: [inferred]

### The $1.6 Billion Marble Freedom Trust transfer (2022) — dark-money
- URL: https://www.propublica.org/article/dark-money-leonard-leo-barre-seid
- Partner/awards: co-published with The Lever
- Found: Seid donated Tripp Lite to Leo's Marble Freedom Trust before the $1.65B Eaton sale — largest known politically focused nonprofit transfer, avoiding ~$400M capital-gains tax.
- Types: tax-optimized-megadonation; donor-anonymization-technique; influence-laundering-via-intermediaries
- Evidence: Marble's first Form 990 (the $1.65B revenue tell); Illinois SoS and Nova Scotia corporate filings; public-records requests and FOIA'd emails; court testimony; tax-professor mechanics
- Systems: Marble Freedom Trust Form 990; Illinois SoS filings; Nova Scotia corporate records; Eaton M&A record
- Signature: new-entity-first-filing-watch: infant c4's nine-figure first-990 revenue joined to registries and the M&A record; crossed-out officer line dates the pre-sale control transfer.
- Method: [inferred]
- Impact: Reference case in c4 appreciated-asset-gift policy debate; watchdog complaints [inferred].

### The IRS Looks the Other Way as Churches Endorse Candidates (2022) — dark-money
- URL: https://www.propublica.org/article/irs-church-nonprofit-endorsements-johnson-amendment
- Partner/awards: co-published with The Texas Tribune
- Found: 18-20 churches committed apparent Johnson Amendment violations on livestreams in two years; FOIA showed only 16 IRS church inquiries since 2011, one exemption ever revoked.
- Types: coordinated-charity-electioneering; fraud-enablement-by-design; two-books-asymmetry
- Evidence: livestreamed/archived church services (COVID-era open AV corpus); reader-submitted sermons via tips form; FOIA'd IRS church-investigation statistics; three independent tax-law experts per violation
- Systems: church livestream archives; FOIA'd IRS church-inquiry statistics; reader tip form
- Signature: broadcast-conduct-monitoring + enforcement-denominator: target class's own AV output adjudicated against a bright-line rule; ~20 violations in 2 years vs 16 IRS inquiries in 11.
- Method: [inferred]
- Impact: By July 2025 IRS conceded pulpit endorsements permissible, ratifying documented non-enforcement.

### True the Vote: donations for personal gain (2023) — dark-money
- URL: https://www.propublica.org/article/true-the-vote-donations-irs-engelbrecht-phillips
- Partner/awards: Livingston Award finalist (Jaramillo); earlier TTV self-dealing reporting credited to Reveal/CIR
- Found: TTV lent founder Engelbrecht ~$40K-$113K (barred under Texas law); Phillips's firms got $750K+; Bopp billed ~$280K; 990 omitted required insider-contract disclosure.
- Types: insider-self-dealing; charity-mission-inversion; two-books-asymmetry
- Evidence: Forms 990 (2019-2021) related-party schedules and omissions; court records obtained by ProPublica incl. the Bopp fee suit; Campaign for Accountability IRS complaint cross-checked; prior Reveal findings
- Systems: IRS Forms 990 Schedule L/contractor tables; litigation dockets (Bopp fee suit)
- Signature: beneficiary-reverse-engineering: payments and loans proven in litigation filings matched against 990 related-party/contractor schedules; absences are self-dealing leads and independent reporting violations.
- Method: [inferred]

### Inside Ziklag (2024) — dark-money
- URL: https://www.propublica.org/article/inside-ziklag-secret-christian-charity-2024-election
- Partner/awards: co-published with Documented
- Found: Ziklag, funded by Uihlein/Green/Waller families, budgeted ~$12M of 501(c)(3) money for 2024 election work: EagleAI voter-roll challenges, church turnout, wedge messaging.
- Types: coordinated-charity-electioneering; charity-mission-inversion; donor-anonymization-technique; influence-laundering-via-intermediaries
- Evidence: thousands of leaked members-only newsletters, internal videos, strategy documents and fundraising pitches; Forms 990 (revenue ramp, grants); six tax-law experts on the record
- Systems: leaked Ziklag internal corpus; IRS Forms 990
- Signature: internal-rulebook-acquisition: leaked strategy documents state electoral intent ("10,640 votes in Arizona") that c3 status forbids; 990s quantify the machine and its cycle-timed ramp.
- Method: [inferred]
- Impact: Freedom From Religion Foundation cited reporting in IRS complaint seeking c3 revocation.

### Nonprofit Explorer (2013-present) — dark-money
- URL: https://projects.propublica.org/nonprofits/
- Found: Turned bulk IRS 990 data — e-file XML, Business Master File, single-audit reports — into a searchable public utility with full-text search (~3M filings) and free API.
- Types: evidence-infrastructure; denominator-construction
- Evidence: IRS raw filing extracts, 990/990-EZ/990-PF images and e-file XML, Exempt Organizations Business Master File, federal single-audit clearinghouse data — all bulk public, re-engineered for usability
- Systems: IRS 990 e-file XML; EO Business Master File; federal single-audit clearinghouse; Nonprofit Explorer API
- Signature: silo-join-on-hard-identifier at platform scale: EIN as spine; full-text indexing promotes officer/vendor/grantee strings in schedule text into corpus-wide join keys.
- Method: https://www.propublica.org/nerds/announcing-the-nonprofit-explorer-api

## Healthcare (report-04)

### Dollars for Docs (2010–2019) — healthcare
- URL: https://projects.propublica.org/docdollars/
- Partner/awards: Database shared at launch with NPR and other outlets
- Found: $257.8M from seven pharma companies to ~17,700 providers at launch; 700+ doctors ultimately >$1M; payment-tier dose-response in brand-name prescribing.
- Types: undisclosed-financial-conflict; statistical-outlier-practitioner
- Evidence: Settlement-mandated company disclosure pages (scraped); CMS Open Payments and Medicare Part D bulk data; state medical board disciplinary files; Obsidian HDS/Pharmashine commercial data.
- Systems: CMS Open Payments; Medicare Part D prescriber data; state medical board disciplinary files; Obsidian HDS/Pharmashine
- Signature: aggregation-as-detection: normalize 17 incompatible company disclosure silos into one per-physician ledger; join to Part D prescribing and board discipline on physician identity.
- Method: https://www.propublica.org/article/about-our-pharma-data ; https://www.propublica.org/article/about-the-dollars-for-docs-data
- Impact: Companies cut speaker payments; database retired in favor of CMS site.

### Prescriber Checkup (2013– ) — healthcare
- URL: https://www.propublica.org/article/part-d-prescriber-checkup-mainbar
- Partner/awards: ProPublica original
- Found: Miami psychiatrist wrote 8,900 antipsychotic prescriptions for seniors in 2010; top clozapine prescriber Reinstein later imprisoned for kickbacks; CMS never monitored prescribing patterns.
- Types: statistical-outlier-practitioner; regulatory-capture; passive-payer-nonsurveillance
- Evidence: FOIA-obtained Medicare Part D prescriber-level aggregates (public from April 2015); court records of prosecutions; interviews with outlier prescribers, pharmacologists, state regulators.
- Systems: Medicare Part D prescriber-level claims data (FOIA, then CMS public release)
- Signature: outlier-in-microdata: per-provider-per-drug claim counts vs specialty-by-state peer distribution, >=2-sigma flags, minimum-denominator guards, drug-risk-list overlays turn volume into harm hypotheses.
- Method: https://www.propublica.org/article/how-we-analyzed-medicares-drug-data-long-methodology
- Impact: CMS began annual public release of prescriber-level Part D data (2015).

### Surgeon Scorecard (2015) — healthcare
- URL: https://projects.propublica.org/surgeons/
- Partner/awards: ProPublica original; no major award — formal RAND methods controversy instead
- Found: Complication rates for ~17,000 surgeons across 8 elective procedures; ~11% of surgeons accounted for ~25% of complications, including inside elite hospitals.
- Types: statistical-outlier-practitioner; institutional-coverup/records-suppression
- Evidence: Medicare inpatient billing microdata 2009–2013 under research-data agreement [inferred]; five-doctor expert panels per procedure; patient, surgeon, and safety-officer interviews.
- Systems: Medicare inpatient billing records 2009–2013
- Signature: denominator-construction: elective-only cases, death/30-day-readmission outcomes, mixed-effects model, empirical Bayes shrinkage, suppression below 20 cases — denominator discipline is the whole game.
- Method: https://www.propublica.org/article/surgeon-level-risk-short-methodology
- Impact: Forced surgeon-level transparency debate; shaped subsequent outcome-measure design.

### God Help You. You're on Dialysis. (2010) — healthcare
- URL: https://www.propublica.org/article/in-dialysis-life-saving-care-at-great-risk-and-cost
- Partner/awards: The Atlantic; finalist, 2011 National Magazine Award for Public Interest
- Found: 1-in-4 US dialysis patients die within a year vs 1-in-9 Italy; DaVita/Fresenius duopoly earned $2.2B; CMS terminated just 16 clinics 2000–2008.
- Types: extraction-from-captive-population; regulatory-capture; institutional-coverup/records-suppression
- Evidence: Thousands of state/CMS clinic inspection reports across six states; FOIA'd clinic-specific outcome data; Texas outcome data; 100+ interviews; deaths reconstructed from inspection files.
- Systems: state/CMS dialysis clinic inspection reports (6 states, 2002–2009); Texas clinic outcome data 2007–09; international dialysis registries; SEC filings
- Signature: enforcement-gap-ratio: cross-national outcome benchmark on a fixed clinical standard, plus inspection-deficiency corpus divided by enforcement actions (16 terminations in 9 years).
- Method: [inferred]
- Impact: CMS released facility-level outcomes; fed 2012 bundled-payment/QIP debate.

### Life and Death in Assisted Living (2013) — healthcare
- URL: https://www.propublica.org/article/emeritus-1-the-emerald-city
- Partner/awards: PBS Frontline
- Found: Emeritus, largest US assisted-living chain (~500 facilities), admitted residents too medically complex to hit occupancy targets; Joan Boice paid $7,125/month, died amid staffing shortage.
- Types: extraction-from-captive-population; fraud-enablement-by-design; regulatory-tier-arbitrage
- Evidence: 100+ lawsuits with discovery exhibits (internal audits, emails); six-state five-year inspection records; SEC filings; former nurses/executives interviews; on-camera film fieldwork.
- Systems: state assisted-living inspection records (CA, TX, OH, IA, MS, GA); SEC filings
- Signature: occupancy-vs-acuity-join: internal occupancy/revenue targets joined to admitted-resident acuity from lawsuits/inspections; cross-state aggregation defeats state-by-state regulatory fragmentation hiding chain patterns.
- Method: [inferred]
- Impact: Boice jury verdict with large punitive award; national regulatory scrutiny.

### Insult to Injury / The Demolition of Workers' Comp (2015) — healthcare
- URL: https://www.propublica.org/article/the-demolition-of-workers-compensation
- Partner/awards: NPR; Edward R. Murrow Award, News Series
- Found: 33 states cut workers' comp benefits since 2003; loss of an eye worth $27,280 in Alabama vs $261,525 in Pennsylvania; ~$30B/yr shifted to taxpayers.
- Types: benefit-erosion-by-statute; two-books-asymmetry; regulatory-capture
- Evidence: 50-state benefit schedules and statutes compiled; insurance-industry rate/profitability datasets; workers' medical and court files with consent; employer-written opt-out plan documents; interviews.
- Systems: 50-state workers' comp statute/benefit-schedule compilation; TX/OK opt-out plan documents
- Signature: cross-jurisdiction-statute-diff: normalize 50 state schedules to dollar-per-body-part units and diff across states and time; industry "cost crisis" claims vs its own premium/profit trend.
- Method: https://www.propublica.org/article/workers-comp-benefits-how-much-is-a-limb-worth-methodology
- Impact: OSHA echoed findings; Oklahoma Supreme Court struck down opt-out.

### Lost Mothers (2017–18) — healthcare
- URL: https://www.propublica.org/series/lost-mothers
- Partner/awards: NPR; 2017 Peabody Award; Goldsmith Prize finalist; NABJ Salute to Excellence
- Found: Hand-identified 134 named women who died of pregnancy-related causes in 2016 behind CDC's anonymous ~700–900/yr aggregate; ~5,000 submissions; 4,000+ documented near-misses.
- Types: anonymized-aggregate-accountability-gap; systemic-preventable-harm-undercount
- Evidence: ~5,000 crowdsourced submissions; scraped Facebook/Twitter/GoFundMe/YouCaring memorial and fundraiser posts; obituary/public-record verification of every case; CDC surveillance as denominator frame.
- Systems: CDC pregnancy-mortality surveillance; GoFundMe/YouCaring fundraisers; Facebook/Twitter public posts; obituaries
- Signature: crowdsourced-denominator-reconstruction: rebuild the named case cohort from social/fundraiser exhaust plus obituary verification; compare against the official anonymous aggregate to expose what anonymization hides.
- Method: https://www.propublica.org/article/how-we-collected-nearly-5-000-stories-of-maternal-harm
- Impact: Preventing Maternal Deaths Act signed December 2018; state legislators credited series.

### Profiting from the Poor — Methodist Le Bonheur (2019) — healthcare
- URL: https://mlk50.com/profiting-from-the-poor/
- Partner/awards: MLK50/ProPublica Local Reporting Network (Wendi C. Thomas); Selden Ring; Gerald Loeb; NABJ Salute to Excellence
- Found: Faith-based nonprofit Methodist filed 8,300+ collection suits 2014–2018 in Shelby County, garnishing even its own low-wage employees, through a captive collection agency.
- Types: charity-mission-inversion; two-books-asymmetry; self-dealing/related-party
- Evidence: Five years of Shelby County General Sessions Court dockets harvested by plaintiff; courtroom observation; IRS 990/financial-assistance-policy compliance checks; defendant patient and employee interviews.
- Systems: Shelby County General Sessions Court dockets; IRS Form 990
- Signature: two-books-diff: plaintiff-name aggregation across a county civil docket joined to the same institution's 990 charity-care claims; defendant list intersected with the hospital's own employee roster.
- Method: [inferred]
- Impact: Suits suspended; $11.9M erased for 5,300+ patients; Grassley demanded answers.

### The Hospice Hustle / "Endgame" (2022) — healthcare
- URL: https://www.propublica.org/article/hospice-healthcare-aseracare-medicare
- Partner/awards: The New Yorker (Ava Kofman); 2023 Hillman Prize; National Press Club award; Barlett & Steele award
- Found: For-profit hospices recruited non-dying patients in a $22B/yr per-diem benefit; one AseraCare office hit 70% live discharge; 129 hospices in one LA building.
- Types: extraction-from-captive-population; fraud-enablement-by-design; license-mill-clustering; regulatory-capture
- Evidence: 11 years of court filings including AseraCare FCA qui tam; state/federal licenses and inspection surveys; OIG/GAO reports; family-shared medical records; 150+ interviews; five-state site visits.
- Systems: state/federal hospice license records; CMS inspection and complaint surveys; OIG/GAO reports
- Signature: live-discharge-rate-inversion: in a benefit premised on 6-month terminal prognosis, survival is the fraud signature; plus address-colocation license clustering and cap-proximity patient churn.
- Method: [inferred]
- Impact: Congressional crackdown calls; CMS Hospice Special Focus Program stood up 2023–24.

### Uncovered: How Often Do Health Insurers Say No to Patients? (2023) — healthcare
- URL: https://www.propublica.org/article/how-often-do-health-insurers-deny-patients-claims
- Partner/awards: ProPublica (series includes Capitol Forum co-publications)
- Found: 13 years after ACA mandated denial-rate disclosure, data covers <10% of privately insured; insurers deny ~1 in 5 claims; NAIC keeps its data secret.
- Types: regulatory-data-void; algorithmic-or-systematic-denial; institutional-coverup/records-suppression
- Evidence: CMS transparency files for HealthCare.gov plans; KFF analyses; 50-state records-request canvass with every refusal documented as evidence; regulator and expert interviews.
- Systems: CMS HealthCare.gov marketplace-plan transparency files; NAIC denial data (withheld; only CT and VT disclose)
- Signature: policy-shadow-measurement: diff the statutory disclosure mandate against data actually collected; a 50-jurisdiction identical-request canvass converts scattered refusals into a quantified secrecy map.
- Method: [inferred]
- Impact: Framed Uncovered series producing Cigna, EviCore, UnitedHealth investigations.

### Cigna PxDx (2023) — healthcare
- URL: https://www.propublica.org/article/cigna-pxdx-medical-health-insurance-rejection-claims
- Partner/awards: The Capitol Forum (co-published); April 2023 Sidney Award
- Found: Cigna medical directors bulk-denied 300,000+ claims in two months, averaging 1.2 seconds each, without opening patient files; internal projections assumed only ~5% appeal.
- Types: algorithmic-or-systematic-denial; fraud-enablement-by-design
- Evidence: Leaked corporate spreadsheets tracking per-director denial volumes and cost-benefit presentations; anonymous former medical directors plus named ex-executive; named patient's external-review reversal; regulator comment.
- Systems: Cigna PxDx internal denial-tracking spreadsheets (leaked)
- Signature: per-reviewer-throughput-forensics: decisions divided by reviewer time from the company's own productivity ledger yields physically impossible review rates — arithmetic proof no medical judgment occurred.
- Method: [inferred]
- Impact: Congressional scrutiny; prior-auth reform wave; California class actions followed.

### EviCore, "The Denial Machine" (2024) — healthcare
- URL: https://www.propublica.org/article/evicore-health-insurance-denials-cigna-unitedhealthcare-aetna-prior-authorizations
- Partner/awards: The Capitol Forum (co-reported); broad pickup (CNN)
- Found: Cigna-owned EviCore runs prior auth for ~100M covered lives with a tunable "dial" raising denials; ~20% Arkansas turndown vs ~7% Medicare Advantage.
- Types: algorithmic-or-systematic-denial; delegated-denial-profiteering; tunable-threshold-artifact
- Evidence: Internal sales materials, contract terms, dial descriptions; Vermont Medicaid filings and Arkansas regulator denial data; 2018 CMS audit; dozens of insider interviews; Cupp case records with independent cardiologists.
- Systems: Vermont Medicaid regulatory filings; Arkansas insurance-regulator denial-rate data; 2018 CMS audit
- Signature: tunable-threshold-discovery: the internal artifact is a governance dial proving denial rates are a controlled business variable; benchmark vendor rates across clients/time against a neutral comparator.
- Method: [inferred]
- Impact: Fed prior-auth reform; CMS 2024 rule requires posting prior-auth metrics.

### UnitedHealth's Mental-Health Playbook: ALERT & Autism "Market Action Plans" (2024) — healthcare
- URL: https://www.propublica.org/article/unitedhealth-mental-health-care-denied-illegal-algorithm ; https://www.propublica.org/article/unitedhealthcare-insurance-autism-denials-applied-behavior-analysis-medicaid
- Partner/awards: ProPublica (Annie Waldman)
- Found: ALERT therapy-limiting algorithm ruled illegal in CA/MA/NY was rebranded "Outpatient Care Engagement" and redeployed into ~20 state Medicaid programs; ABA plans projected 40% Louisiana provider exclusion.
- Types: algorithmic-or-systematic-denial; network-suppression-rationing; rebrand-persistence; extraction-from-captive-population
- Evidence: Hundreds of pages of leaked playbooks, ALERT documentation, scripts, quotas, deployment plans; CA/MA/NY enforcement records and NY AG/DOL settlement; seven former Optum employees plus dozens more.
- Systems: Optum ALERT internal documentation (leaked); CA/MA/NY parity enforcement records; NY AG/DOL settlement
- Signature: rebrand-persistence-tracing: fingerprint enjoined thresholds/scripts from enforcement records, match against successor-program internals; deployment maps skewed to non-settling jurisdictions confirm regulatory arbitrage by geography.
- Method: [inferred]
- Impact: Senate Finance (Wyden) pressed UnitedHealth; series continued through 2026.

### Life of the Mother (2024–2025) — healthcare
- URL: https://www.propublica.org/series/life-of-the-mother
- Partner/awards: Pulitzer Prize for Public Service 2025 — second consecutive
- Found: Five named preventable deaths under abortion bans (Thurman, Miller, Barnica, Crain, Ngumezi); Texas second-trimester pregnancy-loss sepsis rose >50% after the ban.
- Types: policy-induced-mortality; institutional-coverup/records-suppression
- Evidence: Confidential state maternal mortality review committee determinations obtained despite confidentiality; family-shared death certificates, autopsies, hospital records; purchased Texas hospital discharge data 2017–2023; expert OB panels.
- Systems: state Maternal Mortality Review Committee determinations (GA); Texas hospital discharge data (purchased, 2017–2023); death certificates
- Signature: commercial-microdata-natural-experiment: fix the exposed denominator (second-trimester pregnancy-loss hospitalizations), diff complication rates across the ban date against pre-pandemic baseline; paired with named-cohort tracing from preventability verdicts.
- Method: https://www.propublica.org/article/texas-maternal-mortality-analysis-methodology
- Impact: Georgia dismissed its review committee; Texas passed SB 31; Pulitzer 2025.

## Criminal Justice (report-05)

### Out of Order (2013) — criminal-justice
- URL: https://www.propublica.org/article/who-polices-prosecutors-who-abuse-their-authority-usually-nobody
- Partner/awards: ProPublica original
- Found: Courts found NYC prosecutors committed conviction-reversing misconduct in 30 cases 2001–2011; only one (Claude Stuart) seriously disciplined; others got raises and promotions.
- Types: statistical-outlier-practitioner; institutional-coverup/records-suppression; accountability-gap
- Evidence: Appellate/trial opinions citing misconduct (open-public); attorney disciplinary records; request-gated DA personnel and promotion records; exoneree and defense-lawyer interviews.
- Systems: none named
- Signature: sanction-outcome-diff: corpus of appellate opinions finding misconduct joined on prosecutor name to bar-discipline and personnel/promotion records — 30 judicial findings to 1 sanction.
- Method: [inferred]
- Impact: NY prosecutorial-conduct-commission legislation followed; featured defendant later freed.

### Deadly Force, in Black and White (2014) — criminal-justice
- URL: https://www.propublica.org/article/deadly-force-in-black-and-white
- Partner/awards: ProPublica original
- Found: FBI SHR data, 1,217 fatal police shootings 2010–2012: Black males 15–19 killed at 31.17 per million vs 1.47 for white peers — 21x.
- Types: disparate-impact-by-race-or-geography; undercount-by-design
- Evidence: FBI Supplementary Homicide Report microdata via National Archive of Criminal Justice Data (open-public); census population denominators (open-public).
- Systems: FBI Supplementary Homicide Report (via NACJD); census denominators
- Signature: denominator-construction: incident-level victim records by race/age/circumstance divided by census population-at-risk yields per-capita risk ratios; confidence intervals; non-reporting agencies quantified as a second finding.
- Method: [inferred]

### An Unbelievable Story of Rape (2015) — criminal-justice
- URL: https://www.propublica.org/article/false-rape-accusations-an-unbelievable-story
- Partner/awards: The Marshall Project; 2016 Pulitzer Prize, Explanatory Reporting; Netflix's Unbelievable; book
- Found: Lynnwood, WA police coerced victim "Marie" into recanting and charged her with false reporting; Colorado detectives later caught serial rapist Marc O'Leary holding her photos.
- Types: due-process-bypass; victim-disbelief-failure; institutional-coverup/records-suppression
- Evidence: Police case files and internal reviews from multiple departments via records requests; DNA/forensic records; O'Leary confession records (litigation); victim and detective interviews.
- Systems: none named
- Signature: two-jurisdiction-narrative-join: the same crime series existed as contradictory records in unconnected agencies; joining the case files on the perpetrator exposed the first agency's failure.
- Method: [inferred]

### Machine Bias (2016) — criminal-justice
- URL: https://www.propublica.org/article/machine-bias-risk-assessments-in-criminal-sentencing
- Partner/awards: ProPublica original; canonical citation of the algorithmic-fairness field
- Found: COMPAS falsely labeled Black non-reoffenders high-risk at 44.85% vs 23.45% for whites; 45% higher scores controlling for history; only 20% of predicted-violent reoffended.
- Types: algorithmic-or-systematic-denial; disparate-impact-by-race-or-geography
- Evidence: COMPAS scores for 18,610 people via Broward County Sheriff public-records request; Broward dockets and jail/prison records for outcome construction; the COMPAS questionnaire; Northpointe documentation.
- Systems: COMPAS/Northpointe scores via Broward County Sheriff's Office; Broward County criminal dockets; jail/prison records
- Signature: ground-truth-construction: independently build the outcome the score claims to predict (two-year recidivism) via name+DOB joins; compare error rates conditional on race across three model families.
- Method: https://www.propublica.org/article/how-we-analyzed-the-compas-recidivism-algorithm (data+code: https://github.com/propublica/compas-analysis)
- Impact: Founded algorithmic-accountability reporting; dataset became standard ML-fairness benchmark.

### Busted (2016) — criminal-justice
- URL: https://www.propublica.org/article/common-roadside-drug-test-routinely-produces-false-positives
- Partner/awards: The New York Times Magazine; Sidney Award
- Found: Houston retests: 212 convictions where the substance was no controlled substance at all; median arrest-to-plea 4 days; est. 100,000+ annual pleas rest on unconfirmed $2 field tests.
- Types: wrongful-conviction-production; fraud-enablement-by-design; disparate-impact-by-race-or-geography; due-process-bypass
- Evidence: Houston crime-lab GC-MS retest records (request-gated); Harris County dockets and DA conviction-integrity letters; Florida FDLE lab data; 40-jurisdiction court survey; exoneree interviews.
- Systems: Houston crime-lab GC-MS retest records; Harris County dockets; Florida Department of Law Enforcement lab data; RTI International prosecutor survey
- Signature: retest-the-evidence: confirmatory lab results joined on case number to field-test-based charges and pleas; plea-timing analysis proves convictions systematically preceded the only reliable evidence.
- Method: [inferred]
- Impact: Harris County required lab reports before pleas; 250+ convictions overturned.

### The NYPD's Nuisance-Abatement Machine (2016) — criminal-justice
- URL: https://www.propublica.org/article/nypd-nuisance-abatement-evictions
- Partner/awards: New York Daily News; 2017 Pulitzer Prize for Public Service (shared)
- Found: Of 516 residential nuisance-abatement actions, 173 people banned were never convicted, 44 never prosecuted; judges approved 75% ex parte; nine in ten hit minority neighborhoods.
- Types: civil-process-weaponization; due-process-bypass; disparate-impact-by-race-or-geography; extraction-from-captive-population
- Evidence: Hand-assembled state supreme court civil case files (petitions, ex parte orders, settlement stipulations); criminal-court dispositions of every banned person; resident interviews.
- Systems: NY State Supreme Court nuisance-abatement case files (county clerk); NYC criminal-court dispositions
- Signature: case-corpus-construction: build the filing universe, code each case, join every banned person to criminal records — the null join (no conviction) is the finding; plus ex-parte-rate measurement.
- Method: [inferred]
- Impact: City Council passed 13-bill reform package; Pulitzer Public Service 2017.

### Walking While Black (2017) — criminal-justice
- URL: https://features.propublica.org/walking-while-black/jacksonville-pedestrian-violations-racial-profiling
- Partner/awards: Florida Times-Union; Paul Tobenkin Award; Al Nakkula Award
- Found: Black Jacksonville residents received 55% of pedestrian tickets while 29% of population; at least half of tickets under FL 316.130(11) were legally erroneous.
- Types: disparate-impact-by-race-or-geography; enforcement-without-legal-basis; extraction-from-captive-population
- Evidence: Statewide Traffic Citation Accounting Transmission dataset via Sunshine Law; 746 original citation PDFs; ACS denominators; crash/death-certificate matches; Google Street View review; stakeout field observation.
- Systems: Florida Traffic Citation Accounting Transmission dataset (Florida Court Clerks & Comptrollers); ACS 5-year estimates; Google Street View; death certificates
- Signature: statute-conformance-audit: geocoded per-capita ticket rates by race/tract, then each ticket checked against physical predicates via Street View — required traffic signals did not exist.
- Method: https://www.propublica.org/article/how-we-calculated-the-risks-of-walking-while-black
- Impact: Sheriff directed officers to stop ticketing pedestrians for lacking ID.

### Documenting Hate (2017–2019) — criminal-justice
- URL: https://projects.propublica.org/graphics/hatecrime-map
- Partner/awards: Coalition with national/local newsrooms plus Meedan and Ushahidi; Scripps Howard finalist; NLGJA Al Neuharth Award
- Found: FBI hate-crime counts are a fraction of NCVS estimates; ~20% of agencies don't report; Florida's 15 largest agencies reported 19 hate crimes combined.
- Types: undercount-by-design; institutional-coverup/records-suppression; crowdsource-enabled-pattern-detection
- Evidence: Crowdsourced incident reports via public form; verified social-media newsgathering (Meedan/Ushahidi workflow); FBI Hate Crime Statistics 2007–2016; NCVS estimates; agency-level participation records.
- Systems: FBI UCR Hate Crime Statistics; NCVS
- Signature: zero-report-anomaly: compare the mandated self-report ledger against an independent victimization estimate and a self-built corpus; flag large agencies reporting zero — missingness itself as signal.
- Method: [inferred]
- Impact: Preceded 2021 federal statute on hate-crime data collection.

### Driven Into Debt / The Ticket Trap (2018) — criminal-justice
- URL: https://www.propublica.org/series/driven-into-debt
- Partner/awards: WBEZ Chicago
- Found: Chicago ticket debt topped ~$1B; the 2012 sticker-fine hike to $200 generated debt not compliance; thousands of mostly Black motorists filed Chapter 13 over tickets.
- Types: extraction-from-captive-population; disparate-impact-by-race-or-geography; debt-spiral-by-design
- Evidence: City of Chicago internal ticket database via joint FOIA (~28.3M tickets; app covers 54M since 1996); federal bankruptcy dockets; Illinois license-suspension records; census; debtor interviews.
- Systems: City of Chicago ticket-tracking database (FOIA); federal bankruptcy dockets; Illinois license-suspension records
- Signature: fine-ledger-to-insolvency-join: city ticket ledger aggregated per household/zip joined to Chapter 13 filings and license suspensions; the 2012 price hike as natural experiment (projected vs actual revenue).
- Method: https://www.propublica.org/nerds/download-chicago-parking-ticket-data
- Impact: Chicago overhauled fines and fees; non-driving license suspensions ended.

### False Witness (2019) — criminal-justice
- URL: https://www.propublica.org/article/hes-a-liar-a-con-artist-and-a-snitch-his-testimony-could-soon-send-a-man-to-his-death
- Partner/awards: New York Times Magazine cover; 2019 Taylor Family Award; 2020 Hillman Prize for Magazine Journalism
- Found: Jailhouse informant Paul Skalnik figured in 37+ Pinellas County cases 1981–1987, four death rows; walked free five days after Dailey's death sentencing; deals undisclosed.
- Types: informant-market-corruption; statistical-outlier-practitioner; institutional-coverup/records-suppression
- Evidence: 50+ public-records requests assembling ~40 criminal case files (police reports, jail logs, probation/parole records, correspondence, affidavits); trial transcripts; interviews.
- Systems: Pinellas County, FL court-clerk case files and dockets
- Signature: career-file-assembly: aggregate every case one recurring witness touched across decades; time-align his testimony against his own charges and releases — the undisclosed exchange becomes visible.
- Method: [inferred]
- Impact: Dailey execution stayed; fed informant-disclosure registry and reliability-hearing movement.

### The NYPD Files (2020) — criminal-justice
- URL: https://projects.propublica.org/nypd-ccrb/
- Partner/awards: ProPublica original; related co-publication with THE CITY on union litigation
- Found: Published 12,056 CCRB complaints and 45,778 allegations against 3,996 active officers (1985–2020) days after the 50-a repeal; discipline typically trivial.
- Types: institutional-coverup/records-suppression; statistical-outlier-practitioner; accountability-gap
- Evidence: CCRB complaint/allegation/disposition data via records request filed immediately after the June 2020 repeal of 50-a; union-litigation filings; detailed complaint reports via partner FOIL.
- Systems: NYC CCRB complaint database; ProPublica Data Store CSV release
- Signature: secrecy-repeal-arbitrage: file for the entire historical record set the moment a confidentiality statute falls, before litigation re-seals it; the queryable database is the product.
- Method: [inferred]
- Impact: CCRB launched its own public officer-history database (March 2021).

### The Kids of Rutherford County (2021) — criminal-justice
- URL: https://www.propublica.org/article/black-children-were-jailed-for-a-crime-that-doesnt-exist
- Partner/awards: ProPublica Local Reporting Network with WPLN News/Nashville Public Radio; Serial Productions podcast (2023)
- Found: County arrested 11 Black children under a charge that does not exist in Tennessee law; its "filter system" detained 48% of juvenile cases vs 5% statewide.
- Types: due-process-bypass; enforcement-without-legal-basis; extraction-from-captive-population; disparate-impact-by-race-or-geography; undercount-by-design
- Evidence: 50+ records requests; 38 hours of internal police-investigation audio; depositions/settlements from seven federal lawsuits; detention-center procedures; 137 commission recordings; 12+ personnel files.
- Systems: Rutherford County detention-center "filter system" operating procedures; TN DCS inspection records; Board of Judicial Conduct records
- Signature: charge-validity-audit: match arrest-paperwork charges against the actual criminal code (offense nonexistent); 48%-vs-5% detention-rate outlier; internal-rulebook acquisition proved illegality by its own text.
- Method: [inferred]
- Impact: Filter system eliminated; class settlement up to $11M; Serial season.

### Criminal Justice in Elkhart, Indiana (2018–19) — criminal-justice
- URL: https://www.propublica.org/article/nearly-all-officers-in-charge-of-elkhart-indiana-police-department-have-been-disciplined
- Partner/awards: South Bend Tribune; ProPublica Local Reporting Network
- Found: 28 of 34 Elkhart police supervisors had disciplinary records, some criminal; the detective behind the Cooper/Parish wrongful convictions had been forced out over sexual misconduct.
- Types: statistical-outlier-practitioner; wrongful-conviction-production; institutional-coverup/records-suppression
- Evidence: Personnel, disciplinary, and internal-affairs files plus decades-old case files via FOIA; court records; station-house beating video (request-gated).
- Systems: none named
- Signature: personnel-file-denominator: request disciplinary files for the entire command roster and compute the disciplined fraction (28/34), converting anecdote into an institutional rate; plus cold-case re-excavation.
- Method: [inferred]
- Impact: Chief resigned; two officers federally charged; Cooper's $7.5M settlement.

### TIGER, the Algorithm Banning Louisiana Prisoners From Parole (2025) — criminal-justice
- URL: https://www.propublica.org/article/tiger-algorithm-louisiana-parole-calvin-alexander
- Partner/awards: Verite News
- Found: 2024 Louisiana law lets the TIGER risk score cancel parole hearings outright — at least 70 canceled Aug–Dec 2024; immutable pre-prison inputs, rehabilitation cannot change the score.
- Types: algorithmic-or-systematic-denial; algorithmic-eligibility-gate; due-process-bypass
- Evidence: Abbreviated entry — TIGER creator's account, seven national experts, hearing-cancellation counts, input-schema review; source types not itemized.
- Systems: none named
- Signature: rule-change-to-outcome-trace: diff the decision process before/after a statutory change, count decisions made solely by the algorithm, interrogate the input schema for immutability — gate, not assessment.
- Method: [inferred]

## Corporate & Consumer (report-06)

### The TurboTax Trap I: dark-pattern steering + hiding Free File (2019) — corporate-consumer
- URL: https://www.propublica.org/article/turbotax-just-tricked-you-into-paying-to-file-your-taxes ; https://www.propublica.org/article/turbotax-deliberately-hides-its-free-file-page-from-search-engines
- Partner/awards: ProPublica original (Elliott, Waldron); series won a Gerald Loeb Award
- Found: TurboTax charged Free File-eligible users ($29,000 TaskRabbit cleaner billed $119.99), tagged them "NONFFA," and hid its Free File page from Google via noindex directives.
- Types: dark-pattern/consumer-deception; public-benefit-interception; fraud-enablement-by-design
- Evidence: Constructed mystery-shopper walkthroughs with synthetic taxpayer personas; Intuit's own robots.txt, meta tags, analytics variables; crowdsourced technical tips (named readers); IRS Free File Alliance rules.
- Systems: Intuit robots.txt/meta-robots site code; IRS Free File Alliance program rules
- Signature: site-forensics-plus-mystery-shopper: diff noindex/nofollow treatment of free-obligation pages vs revenue pages; run an eligibility-matching persona through the funnel logging every steering screen.
- Method: [inferred]
- Impact: $141M 50-state AG settlement; FTC deceptive-advertising order; Intuit quit Free File.

### The TurboTax Trap II: 20-year lobbying war on free government filing (2019) — corporate-consumer
- URL: https://www.propublica.org/article/inside-turbotax-20-year-fight-to-stop-americans-from-filing-their-taxes-for-free
- Partner/awards: ProPublica original; part of the Loeb-winning series
- Found: Internal Intuit docs on government-filing proposals: "All were stopped"; astroturf payments ($70,000 to WIPP) bought pro-Free File letters; ~$1.5B revenue at stake.
- Types: regulatory-capture/lobbying-to-preserve-rents; dark-pattern/consumer-deception; public-benefit-interception
- Evidence: Leaked internal Intuit board and strategy decks; FOIA plus FOIA lawsuit for IRS-Intuit communications; TaxAct CEO antitrust testimony; lobbying disclosures; ex-IRS and ex-Intuit interviews.
- Systems: federal lobbying disclosures; IRS-Intuit FOIA correspondence; 2011 antitrust proceeding testimony
- Signature: internal-rulebook-plus-temporal-correlation: strategy documents name objective and method; join astroturf payments and lobbying to the timeline of each free-filing proposal's death; revolving-door mapping supplies mechanism.
- Method: [inferred]

### Unseen Toll: Wages of Millions Seized to Pay Past Debts (2014) — corporate-consumer
- URL: https://www.propublica.org/article/unseen-toll-wages-of-millions-seized-to-pay-past-debts
- Partner/awards: NPR
- Found: First national numbers: ~4M US workers (~3% of 13M studied) had wages garnished for consumer debt in 2013; over 6% among Midwest $25–40K earners.
- Types: extraction-from-captive-population; disparate-impact-by-race-or-geography
- Evidence: ADP custodian-run aggregate study commissioned by the newsroom; court filings from eight states including Missouri's 24 circuits; one anonymous major retailer's payroll figures; debtor interviews.
- Systems: ADP payroll records (custodian-run aggregate); Missouri circuit court records (24 circuits)
- Signature: third-party-data-custodian-query: persuade the chokepoint firm holding the only true denominator to run a newsroom-specified aggregate analysis, then anchor with docket-level case records.
- Method: [inferred]

### The Color of Debt (2015) — corporate-consumer
- URL: https://www.propublica.org/article/debt-collection-lawsuits-squeeze-black-neighborhoods
- Partner/awards: ProPublica original (Marketplace radio segment); National Press Club award; NABJ finalist
- Found: 184,000+ judgments across St. Louis, Cook, and Essex counties: judgment rates in majority-Black tracts ran 2x majority-white tracts, holding income constant.
- Types: disparate-impact-by-race-or-geography; courts-as-profit-center; extraction-from-captive-population
- Evidence: Bulk five-year court judgment records from three county systems; census tract race/income join layer; academically reviewed regression white paper; door-knocked defendant interviews.
- Systems: St. Louis, Cook County, and Essex County court judgment records; census tract demographics
- Signature: geocoded-disparity-join: judgments geocoded to census tracts, converted to per-capita rates, income-stratified regression; plus plaintiff-frequency-inversion ranking top filers from the same data.
- Method: https://www.propublica.org/article/how-we-analyzed-racial-disparity-in-debt-collection-lawsuits
- Impact: Missouri AG pushed debt-collection court reforms citing the race gap.

### The nonprofit hospital debt machine: Heartland/Mosaic → Methodist Le Bonheur (2014–2019) — corporate-consumer
- URL: https://www.propublica.org/article/how-nonprofit-hospitals-are-seizing-patients-wages
- Partner/awards: NPR (2014); MLK50 via ProPublica Local Reporting Network (2019); Selden Ring Award
- Found: Heartland/Mosaic's captive collector sued 11,000+ patients and garnished ~6,000 for ~$12M while the hospital booked $45M profit; Methodist filed 8,300+ suits, including against employees.
- Types: nonprofit-mission-inversion; self-dealing/related-party; courts-as-profit-center; extraction-from-captive-population
- Evidence: Bulk county dockets (Buchanan County garnishments; Shelby County General Sessions, five years by plaintiff); IRS 990s and state financial reports; crowdsourced patient callouts; courtroom observation.
- Systems: Buchanan County, MO court dockets; Shelby County General Sessions dockets; IRS Form 990
- Signature: plaintiff-frequency-inversion: rank the county docket by plaintiff, flag 501(c)(3)s among top filers, resolve the captive collector via registry/990, map defendant employers from garnishment answers.
- Method: [inferred]
- Impact: Mosaic forgave thousands of debts; Methodist erased $11.9M, raised wages.

### When Medical Debt Collectors Decide Who Gets Arrested (2019) — corporate-consumer
- URL: https://features.propublica.org/medical-debt/when-medical-debt-collectors-decide-who-gets-arrested-coffeyville-kansas
- Partner/awards: ProPublica original; Nieman Storyboard methods interview
- Found: Coffeyville, Kansas contempt process jailed medical debtors — 11 arrests, 30+ warrants in a year; $500 bail applied to the debt with the collector's one-third cut.
- Types: courts-as-profit-center; extraction-from-captive-population; debt-criminalization
- Evidence: Local court dockets (judgments, debtor's-exam summonses, contempt citations, bench warrants, bail receipts); courtroom field observation at exam days; debtor, collector, and judge interviews.
- Systems: Coffeyville, KS local court dockets
- Signature: procedural-artifact-forensics: parse the procedure, not the caseload — contempt citations, bench warrants, and cash-bail entries on consumer-debt dockets are machine-detectable debtors-prison flags.
- Method: [inferred]

### Debt Inc. / The 182 Percent Loan + The Payday Playbook (2013) — corporate-consumer
- URL: https://www.propublica.org/article/installment-loans-world-finance
- Partner/awards: Marketplace; Payday Playbook co-published with the St. Louis Post-Dispatch
- Found: World Finance flipped loans (~75% renewals); packed credit insurance turned a stated 90% APR into 182%; Missouri committee chair owned a payday store.
- Types: extraction-from-captive-population; fraud-enablement-by-design; regulatory-capture/lobbying-to-preserve-rents; dark-pattern/consumer-deception
- Evidence: World Acceptance SEC filings; loan-level court exhibits; FOIA'd FTC complaints; 5+ ex-employee interviews; borrower loan files; captive-insurer loss ratios; Missouri campaign-finance records.
- Systems: SEC/EDGAR filings (World Acceptance); FTC consumer-complaint corpus (FOIA); state insurance-commissioner loss-ratio data (Life of the South); Missouri campaign-finance and lobbying records
- Signature: two-books-diff: investor disclosures describe renewals/insurance as the profit engine vs the storefront's stated APR; recompute effective APR from actual loan documents; regulator-complaint-corpus-mining.
- Method: [inferred]
- Impact: World disclosed CFPB investigation (2014); probe dropped 2018 under Mulvaney.

### Rent Going Up? One Company's Algorithm Could Be Why (2022) — corporate-consumer
- URL: https://www.propublica.org/article/yieldstar-rent-increase-realpage-rent
- Partner/awards: ProPublica original
- Found: RealPage YieldStar priced rentals using pooled confidential competitor lease data; ~90% recommendation acceptance; 10 managers controlling 70% of Belltown units all used it.
- Types: algorithmic-price-fixing; extraction-from-captive-population
- Evidence: Vendor's own marketing materials, white papers, earnings calls, user-conference content; former employees including the algorithm's designer; CoStar/Apartments.com data for concentration and paired-building comparison.
- Systems: CoStar/Apartments.com; RealPage marketing corpus and earnings-call transcripts
- Signature: vendor-brag-mining: harvest sales artifacts for pooled-nonpublic-data plus outperformance claims; compute submarket vendor concentration (70% Belltown); paired user vs non-user rent trajectories estimate effect.
- Method: [inferred]
- Impact: DOJ antitrust suits vs RealPage (2024) and six landlords (2025).

### Trump's Inauguration Paid Trump's Company — With Ivanka in the Middle (2018) — corporate-consumer
- URL: https://www.propublica.org/article/trump-inc-podcast-trumps-inauguration-paid-trumps-company-with-ivanka-in-the-middle
- Partner/awards: WNYC "Trump, Inc."; podcast won the Alfred I. duPont-Columbia Award
- Found: The record ~$107M inaugural committee paid Trump's D.C. hotel $175,000/day for ballroom space despite planner Wolkoff's emailed $85,000 fair-price warning reaching Ivanka.
- Types: self-dealing/related-party; nonprofit-mission-inversion
- Evidence: Leaked internal emails among Ivanka Trump, Gates, and planners plus receipts; the committee's IRS Form 990 and FEC donor disclosures; worker/vendor interviews; podcast listener tips.
- Systems: IRS Form 990 (58th Presidential Inaugural Committee); FEC donor disclosures
- Signature: related-party-price-benchmarking: isolate nonprofit payments to insider-controlled vendors; benchmark the charged rate against the internal fair-price warning and market comparables — overridden warning becomes intent evidence.
- Method: [inferred]
- Impact: D.C. AG sued; $750,000 settlement, May 2022.

### Never-Before-Seen Trump Tax Documents Show Major Inconsistencies (2019) — corporate-consumer
- URL: https://www.propublica.org/article/trump-inc-podcast-never-before-seen-trump-tax-documents-show-major-inconsistencies
- Partner/awards: WNYC (Trump, Inc.)
- Found: Same buildings reported differently: 40 Wall Street occupancy 58.9% to lender vs 81% to tax officials; tax-reported income averaged ~81% of lender-reported over eight years.
- Types: two-books-asymmetry
- Evidence: NYC property-tax appeal records via FOIL (public because Trump appealed nine years running); CMBS loan disclosures and servicer statements (public via securitization); academic expert interviews.
- Systems: NYC property-tax appeal records (FOIL); Ladder Capital CMBS loan and servicer disclosures
- Signature: two-books-diff-on-hard-keys: join {property, year, line item} across filings with opposite incentive gradients; the fixed contractual ground-lease line is the checksum row proving misstatement.
- Method: [inferred]

### The Ugly Truth Behind "We Buy Ugly Houses" (2023) — corporate-consumer
- URL: https://www.propublica.org/article/ugly-truth-behind-we-buy-ugly-houses
- Partner/awards: The Dallas Morning News; Shelterforce
- Found: HomeVestors franchisees trained to "find the pain"; nearly one-third of ~71,400 purchases since 2016 from sellers over 65; 50+ franchisees used title-clouding to trap sellers.
- Types: predatory-acquisition-of-distressed-assets; extraction-from-captive-population; dark-pattern/consumer-deception; fraud-enablement-by-design
- Evidence: Bulk county deed/property records (sale prices vs assessed values; lis pendens by franchisee entity); court records; leaked training materials and leadership-call audio; 48 former franchisees interviewed.
- Systems: county deed/property records; recorded lis pendens and memoranda of contract
- Signature: below-market-transfer-screening: join buyer-entity-network deeds to assessed/appraised values flagging deep discounts from elderly grantors; count coercive recorded instruments per network; training materials supply intent.
- Method: [inferred]
- Impact: Franchisee lis pendens banned within days; CEO retired; Senate scrutiny calls.

### Minority Neighborhoods Pay Higher Car Insurance Premiums Than White Areas With the Same Risk (2017) — corporate-consumer
- URL: https://www.propublica.org/article/minority-neighborhoods-higher-car-insurance-premiums-white-areas-same-risk
- Partner/awards: Consumer Reports
- Found: Some insurers charged up to 30% more in minority zips with the same accident cost; 33 of 34 Illinois companies charged at least 10% more.
- Types: disparate-impact-by-race-or-geography; algorithmic-or-systematic-denial; price-to-risk-decoupling
- Evidence: State insurance departments' zip-level loss/payout aggregates (CA, IL, TX, MO — availability defined the geography); constructed 100,000+ quoted-premium matrix for a fixed driver profile; census demographics.
- Systems: CA/IL/TX/MO state insurance-department zip-level loss data; census demographics
- Signature: price-to-risk-join: hold the customer constant (fixed persona), join quoted price to the regulator's own per-geography loss cost; price residuals correlated with racial composition are the finding.
- Method: https://www.propublica.org/article/minority-neighborhoods-higher-car-insurance-premiums-methodology

### Medical Staffing Companies Cut Doctors' Pay While Spending Millions on Political Ads (2020) — corporate-consumer
- URL: https://www.propublica.org/article/medical-staffing-companies-cut-doctors-pay-while-spending-millions-on-political-ads
- Partner/awards: ProPublica original
- Found: PE-owned TeamHealth (Blackstone) and Envision (KKR) cut ER clinician pay during the pandemic while funding $2.2M in ads; Doctor Patient Unity spent $57M total.
- Types: regulatory-capture/lobbying-to-preserve-rents; extraction-from-captive-population; two-books-asymmetry
- Evidence: FCC political-file broadcast ad disclosures; Facebook Ad Library; Advertising Analytics commercial ad tracking; CBO analyses; anonymous affected doctors describing pay-cut memos.
- Systems: FCC political files; Facebook Ad Library; Advertising Analytics
- Signature: temporal-correlation-of-spending-books: time-align dated cost-cutting actions against dated political ad expenditures across a shock window; the simultaneity is the story.
- Method: [inferred]

## Government spending (report-07)

### The Red Cross' Secret Disaster (2014) — gov-spending
- URL: https://www.propublica.org/article/the-red-cross-secret-disaster
- Partner/awards: Co-reported with NPR (Elliott, Eisinger; Sullivan)
- Found: Isaac/Sandy relief botched: ~80 trucks driven empty for show; 40% of NY ERVs on PR duty; 3-in-10 meals wasted; CEO claimed "near flawless."
- Types: two-books-asymmetry; charity-mission-inversion; institutional-coverup/records-suppression
- Evidence: Leaked confidential "Lessons Learned" PowerPoint and Dec 2012 after-action minutes; insider emails; responder interviews; open-public Red Cross statements as the comparison corpus.
- Systems: none named
- Signature: two-books-diff: internal after-action metrics diffed against contemporaneous public executive claims on the same operational KPIs (vehicles deployed, meals served, response quality).
- Method: [inferred]

### How the Red Cross Raised Half a Billion Dollars for Haiti — and Built Six Homes (2015) — gov-spending
- URL: https://www.propublica.org/article/how-the-red-cross-raised-half-a-billion-dollars-for-haiti-and-built-6-homes
- Partner/awards: Co-reported with NPR (Elliott; Sullivan)
- Found: ~$488M raised, "130,000 housed" claimed, six permanent homes built; "91 cents" ratio concealed stacked pass-through fees (9% + 26% + 24% layers).
- Types: charity-mission-inversion; two-books-asymmetry; pass-through-fee-stacking; institutional-coverup/records-suppression
- Evidence: Leaked internal memos, confidential evaluations, org charts, executive emails; dozen-plus official interviews incl. former Haitian PM; field observation in Campeche; open-public reports and ratios.
- Systems: none named
- Signature: ground-truth-vs-claimed-output: physically enumerate the deliverable (homes = 6) and reconstruct per-layer intermediary overhead; compounding fees falsify the headline efficiency ratio.
- Method: [inferred]
- Impact: Grassley probe found ~$124-125M (25%) of Haiti donations spent internally.

### COVID-19 contracting: first-time-vendor mining + Coronavirus Contracts database (2020) — gov-spending
- URL: https://www.propublica.org/article/a-closer-look-at-federal-covid-contractors-reveals-inexperience-fraud-accusations-and-a-weapons-dealer-operating-out-of-someones-house ; https://projects.propublica.org/coronavirus-contracts/
- Partner/awards: With Connor Sheets (AL.com); database by Syed/Willis; grew into McSwane's "Pandemic, Inc."
- Found: ~345 first-time federal contractors promised $1.8B+ from March 2020; 51% of their deals no-bid; database tracks $39.9B across 18,243 contracts.
- Types: anomalous-vendor; fraud-enablement-by-design
- Evidence: Open-public FPDS procurement microdata (COVID-tagged, $10K+ threshold); state incorporation records (formation dates); principals' litigation history; vendor, agency, and former-procurement-official interviews.
- Systems: FPDS; state incorporation registries
- Signature: first-time-vendor-flag: join emergency award stream to full FPDS vendor history; flag zero-prior-award vendors; cross-tab no-competition codes, award size, entity-age-vs-award-diff.
- Method: [inferred]
- Impact: Raskin-requested PRAC probe; contract cancellations; House Subcommittee vendor letters.

### Fillakit: millions for test tubes, unusable mini soda bottles delivered (2020) — gov-spending
- URL: https://www.propublica.org/article/the-trump-administration-paid-millions-for-test-tubes-and-got-unusable-mini-soda-bottles
- Partner/awards: J. David McSwane and Ryan Gabrielson, ProPublica
- Found: LLC formed May 1, 2020; FEMA signed May 7: $10.5M for tubes; owner had $2.7M FTC fraud judgment; delivered unusable soda-bottle preforms.
- Types: anomalous-vendor; fraud-enablement-by-design
- Evidence: Open-public FPDS contract records (contact phone resolved principal); Texas incorporation records; FTC litigation records; warehouse site visit and worker interviews; state health officials, ex-employees, Wexler.
- Systems: FPDS; Texas incorporation records; FTC litigation records
- Signature: entity-age-vs-award-diff: formation-to-award gap of 6 days flagged; selector pivot on contract metadata (phone) unlocked principal's FTC history; field verification of capacity.
- Method: [inferred]
- Impact: Clyburn subcommittee letter; senators pressed FEMA; DHS agent contacted employees.

### The White House Pushed FEMA to Give Its Biggest Coronavirus Contract to a Company That Never Had to Bid (2020) — gov-spending
- URL: https://www.propublica.org/article/the-white-house-pushed-fema-to-give-its-biggest-coronavirus-contract-to-a-company-that-never-had-to-bid
- Partner/awards: J. David McSwane and Yeganeh Torbati, ProPublica
- Found: $96M no-bid FEMA respirator deal to AirBoss; contracting officer's database note said "ordered by the White House"; stock roughly doubled in a week.
- Types: preferential-carve-out; anomalous-vendor
- Evidence: Open-public FPDS records including free-text justification/notes fields; market data on stock move; White House releases; FEMA statements and former-official interviews.
- Systems: FPDS
- Signature: procurement-justification-text-mining: rank no-bid emergency awards by size, then read the human-written justification fields; the phrase in the record was the finding.
- Method: [inferred]
- Impact: Fed congressional oversight; part of later PRAC/GAO noncompetitive-award reviews.

### Hundreds of PPP Loans Went to Fake Farms in Absurd Places (2021) — gov-spending
- URL: https://www.propublica.org/article/ppp-farms
- Partner/awards: Derek Willis and Lydia DePillis, ProPublica
- Found: 378 loans ($7M) to nonexistent one-person "farms," nearly all at the exact $20,833 cap, all via Kabbage, which auto-approved 75% without human review.
- Types: fraud-enablement-by-design; anomalous-vendor; benefit-cap-clustering; category-geography-implausibility
- Evidence: FOIA-litigated SBA loan-level PPP microdata; state business registries (existence checks); licensing and address/property records; ex-Kabbage employees, identity-use victims, the mayor; DOJ prosecution records.
- Systems: SBA PPP loan-level microdata; state business-entity registries
- Signature: benefit-cap-clustering: mass points at category maximum + geography-implausible industry labels + registry nonexistence + single-originator concentration turns borrower fraud into a lender-design story.
- Method: [inferred]
- Impact: House fintech probe within days; Dec 2022 report; DOJ cases cited Kabbage loans.

### Port Covington opportunity zone (2019) — gov-spending
- URL: https://www.propublica.org/article/trump-inc-podcast-one-trump-tax-cut-meant-to-help-the-poor-a-billionaire-ended-up-winning-big
- Partner/awards: Ernsthausen and Elliott, with WNYC's "Trump, Inc." podcast
- Found: Kevin Plank's $5.5B Port Covington was ineligible; qualified via stale-Census mapping error (~0.3% overlap) after lobbyist contact; poorer Black tracts rejected.
- Types: preferential-carve-out; beneficiary-reverse-engineering
- Evidence: Open-public Treasury initial-vs-revised tract lists, Census/ACS demographics, old-vs-new GIS boundary layers; Maryland governor's-office emails via state public-records request; state/city official interviews.
- Systems: Treasury OZ eligible-tract lists; Census/ACS; Census GIS boundary layers
- Signature: designation-list-diff + eligibility-recompute: diff official list versions for quiet insertions; recompute eligibility from primary Census data; GIS-measure the claimed contiguity sliver.
- Method: [inferred]

### Donor-driven Opportunity Zone designations: superyacht marina and Dan Gilbert's Detroit (2019) — gov-spending
- URL: https://www.propublica.org/article/superyacht-marina-west-palm-beach-opportunity-zone-trump-tax-break-to-help-the-poor-went-to-a-rich-gop-donor ; https://www.propublica.org/article/how-a-tax-break-to-help-the-poor-went-to-nba-owner-dan-gilbert
- Found: Rick Scott designated the Rybovich marina tract ~a week after Huizenga's written appeal; Treasury added an ineligible Gilbert Detroit tract after White House coordination.
- Types: preferential-carve-out; self-dealing/related-party; temporal-correlation
- Evidence: State-FOIA Florida DEO designation files incl. Huizenga letter; Michigan economic-development emails; open-public Treasury tract-list versions, Census poverty data, property ownership, campaign-finance records; interviews.
- Systems: Florida DEO designation files; Treasury OZ tract lists; Census poverty data
- Signature: beneficiary-reverse-engineering: from designated tract to landowners (property-to-LLC resolution), donor status, and correspondence; appeal-to-designation timelines of ~8 days and <2 weeks.
- Method: [inferred]
- Impact: Wyden/Neal OZ abuse investigation; reform legislation; Treasury OIG review.

### "Welfare States": TANF block-grant diversion in the Southwest (2021-2023) — gov-spending
- URL: https://www.propublica.org/article/the-cruel-failure-of-welfare-reform-in-the-southwest
- Partner/awards: Eli Hager, ProPublica; Southwest pieces co-published with regional outlets
- Found: Arizona diverts $150M+/yr TANF to its child-removal agency; Utah counted LDS Church charity to avoid $75M+ state spending; $1.7B child support kept by governments.
- Types: fraud-enablement-by-design; charity-mission-inversion; block-grant-diversion-accounting; extraction-from-captive-population
- Evidence: Open-public state TANF expenditure reports to HHS/ACF; state budget documents showing backfill; HHS caseload statistics; Census poverty series; Urban Institute/Niskanen secondary checks; family and official interviews.
- Systems: ACF-196R TANF expenditure filings; HHS caseload statistics; Census poverty series
- Signature: block-grant-diversion-accounting: compute per-state share of TANF reaching cash assistance vs. backfill categories; substitution tests against state budgets; per-poor-child denominators rank states.
- Method: [inferred]
- Impact: Biden administration's Nov 2023 proposed TANF rule overhaul followed.

### Disaster in the Pacific: the Navy's 7th Fleet collisions (2019) — gov-spending
- URL: https://www.propublica.org/series/navy-accidents-pacific-7th-fleet
- Partner/awards: Miller, Rose, Faturechi; 2020 Pulitzer Prize National Reporting; Military Reporters & Editors award
- Found: Fitzgerald/McCain collisions (17 sailors dead) followed years of documented, ignored warnings; McCain touchscreen navigation system contributed; officers scapegoated, reforms unfulfilled.
- Types: warning-ignored-before-disaster; institutional-coverup/records-suppression; two-books-asymmetry
- Evidence: Leaked two confidential Navy investigations (13,000+ pages: transcripts, logs, photos); GAO reports; congressional testimony; NTSB findings; courts-martial attended; interviews at every rank; simulation and scale-model reconstruction.
- Systems: GAO readiness reports; NTSB/Coast Guard findings
- Signature: warnings-ledger-construction: dated ledger of every documented warning joined to the decision record of who received it, anchored to the disaster date; GAO trail alone shows the pattern.
- Method: https://www.propublica.org/article/us-navy-uss-fitzgerald-uss-john-s-mccain-crash-pacific-how-we-investigated
- Impact: Congressional surface-fleet readiness hearings; Pulitzer institutionalized the template.

### Their Family Bought Land One Generation After Slavery… (heirs' property) (2019) — gov-spending
- URL: https://features.propublica.org/black-land-loss/heirs-property-rights-why-black-families-lose-land-south/
- Partner/awards: Presser, co-published with The New Yorker; George Polk Award; John Bartlow Martin Award
- Found: Reels brothers jailed eight years for staying on family land lost via partition-sale mechanics; Black farmland fell ~90% 1910-1997; ~3.5M acres heirs' property.
- Types: extraction-from-captive-population; fraud-enablement-by-design; warning-ignored
- Evidence: Months of county courthouse deed and court records across the South; courthouse-auction attendance; Reels partition case file and contempt record; USDA data; academic studies; family and lawyer interviews.
- Systems: county deed/court records; USDA farmland-by-race series
- Signature: named-cohort-tracing: follow parcels across generations in deed books; flag partition actions where a speculator acquired a fractional interest shortly before filing; auction-vs-assessed price gap.
- Method: [inferred]
- Impact: Accelerated Uniform Partition of Heirs Property Act adoptions; cited in federal legislation.

### Trump's Inauguration Paid Trump's Company — With Ivanka in the Middle (2018) — gov-spending
- URL: https://www.propublica.org/article/trump-inc-podcast-trumps-inauguration-paid-trumps-company-with-ivanka-in-the-middle
- Partner/awards: Elliott (ProPublica) and Marritz (WNYC), "Trump, Inc." collaboration
- Found: Inaugural committee paid Trump hotel ~$700,000 at $175,000/day — roughly double the $85,000/day internal advice — with Ivanka in the pricing negotiation.
- Types: self-dealing/related-party; charity-mission-inversion
- Evidence: Insider internal committee emails and planning documents (Wolkoff warnings); open-public Form 990 and FEC donor disclosures; planner and hotel-pricing-expert interviews; downstream DC AG complaint and Ivanka deposition.
- Systems: IRS Form 990; FEC donor disclosures
- Signature: related-party-price-benchmarking: flag vendor payments where payer decision-makers overlap vendor ownership/management; benchmark price against market rates and the organization's own internal advice.
- Method: [inferred]
- Impact: DC AG suit; $750,000 settlement redirected to DC youth nonprofits.

### Eye on the Bailout / Bailout Tracker (2009-2019+) — gov-spending
- URL: https://projects.propublica.org/bailout/
- Partner/awards: ProPublica news-apps team (Paul Kiel et al.)
- Found: Recipient-level ledger of $700B TARP plus Fannie/Freddie: every disbursement, refund, dividend, warrant payment; "Net Outstanding" per entity, maintained 10+ years.
- Types: evidence-infrastructure; denominator-construction
- Evidence: Open-public Treasury TARP transaction and dividend/interest reports parsed continuously; FHFA/Treasury GSE disclosures; published editorial-accounting rules (loss shading, Treasury-only scope).
- Systems: Treasury TARP transaction reports; FHFA/Treasury GSE disclosures
- Signature: longitudinal-ledger-construction: normalize every periodic official disclosure into one recipient-keyed money-in/money-out table; persistence makes "did we get repaid" permanently answerable.
- Method: [inferred]
- Impact: Standard citation for bailout accounting; model for later ProPublica trackers.

## Environment, labor & tech (report-08)

### Buried Secrets: Gas Drilling's Environmental Threat (2008-2011) — environment-labor-tech
- URL: https://www.propublica.org/article/buried-secrets-is-natural-gas-drilling-endangering-us-water-supplies-1113
- Partner/awards: Some pieces with BusinessWeek; 2009 George Polk Award; 2009 Sigma Delta Chi; NPF Stokes Award
- Found: 1,000+ fracking-linked contamination cases across states; Sublette benzene 1,500x safe level; 2005 "Halliburton loophole" exempted fracking from Safe Drinking Water Act.
- Types: regulatory-capture; concentrated-harm-hotspot; institutional-coverup; statutory-exemption-as-evidence
- Evidence: Request-gated state water-test results, EPA emails and 2003 negotiation notes, hazmat shipping manifests; open/request-gated inspection records and court documents; BLM approval records; resident/regulator field interviews.
- Systems: BLM approval records
- Signature: case-accumulation-against-official-denial: aggregate state-by-state incident records against EPA's "no confirmed cases" line; join to the legislative record explaining why the agency stopped looking.
- Method: [inferred]

### Losing Ground (2014) — environment-labor-tech
- URL: https://projects.propublica.org/louisiana/
- Partner/awards: The Lens (Bob Marshall) + OpenNews fellow Jacobs, maps Al Shaw; 2015 Murrow Award; Gannett Innovation Award; OJA finalist
- Found: Louisiana lost ~2,000 sq mi of coast since the 1930s — a football field every 48 minutes — driven by levees and 10,000 miles of oil/gas canals.
- Types: concentrated-harm-hotspot; externalized-cost-visualization; remote-sensing-time-series
- Evidence: Open-public bulk NASA/USGS Landsat 8 raw band data; archival USGS topographic maps and a scanned 1922 survey map; state coastal master-plan projections; resident interviews/audio fieldwork.
- Systems: Landsat 8; USGS topographic maps; Louisiana coastal master plan
- Signature: remote-sensing-time-series: 40 years of Landsat composites with custom band math, registered against 80-year-old survey maps on a common grid; the diff of composites is the finding.
- Method: https://source.opennews.org/articles/how-we-made-losing-ground/

### Killing the Colorado (2015) — environment-labor-tech
- URL: https://www.propublica.org/series/killing-the-colorado
- Partner/awards: Lustgarten, Shaw, Larson et al.; Discovery documentary 2016; 2016 Pulitzer finalist
- Found: Seven states allocate ~1.4 trillion gallons/year more than the river carries; $1B+ federal subsidies propped Arizona desert cotton; prior-appropriation law punishes conservation.
- Types: policy-erosion/perverse-incentive-structure; regulatory-capture; two-books-diff; subsidy-incentive-join
- Evidence: Open-public USDA farm-subsidy payment data; Bureau of Reclamation flow/allocation/evaporation records; state water-rights law and adjudications; utility/power records; farmer and official field interviews.
- Systems: USDA farm-subsidy payment data; Bureau of Reclamation flow/allocation records
- Signature: subsidy-incentive-join: join subsidy payments to crop water-consumption coefficients and basin hydrology; separately diff legal allocations against gauge-measured flow to quantify structural overdraft.
- Method: [inferred]

### Fuel to the Fire (2018) — environment-labor-tech
- URL: https://features.propublica.org/palm-oil/palm-oil-biofuels-ethanol-indonesia-peatland
- Partner/awards: NYT Magazine co-publication; Overseas Press Club Whitman Bassow Award
- Found: 2007 U.S. biofuel mandate drove Indonesian peatland burning equal to ~70 new coal plants; ~100,000 estimated premature deaths; EPA's warning analysis politically neutralized.
- Types: policy-boomerang; supply-chain-harm-attribution; regulatory-capture; cross-border-policy-externality-trace
- Evidence: Open-public NASA satellite fire hot-spot data; concession maps/NGO records; EPA lifecycle rulemaking record; Kalimantan field reporting incl. whistleblower Gusti Gelambong; trade and production statistics.
- Systems: NASA fire hot-spot data; EPA lifecycle rulemaking docket
- Signature: cross-border-policy-externality-trace: correlate mandate volumes with concession expansion and satellite fire/emissions series; trace the demand shock through commodity substitution to an inverted carbon outcome.
- Method: [inferred]

### The Great Climate Migration (2020) — environment-labor-tech
- URL: https://features.propublica.org/climate-migration/model-how-climate-refugees-move-across-continents/
- Partner/awards: NYT Magazine; funded by the Pulitzer Center
- Found: First modeled, geocoded projection of climate-driven migration from Central America/Mexico; U.S. sequel mapped county-level habitability decline while Americans move toward risk.
- Types: predictive-harm-mapping; model-commissioning
- Evidence: Commissioned Bryan Jones model extending World Bank Groundswell; commercial Rhodium county climate data; USFS wildfire projections; census/agronomic datasets; NCAR supercomputer runs (>10B points); 8-scientist peer review.
- Systems: World Bank Groundswell model; Rhodium Group climate impact data; USFS wildfire projections; NCAR Cheyenne
- Signature: model-commissioning: where no agency dataset answers the question, extend a peer-lineage model with journalistic scenario design; report the scenario spread, not a single prediction.
- Method: https://www.propublica.org/article/2020-climate-migration-part-1-methodology

### Poison in the Air / Sacrifice Zones (2021) — environment-labor-tech
- URL: https://www.propublica.org/article/toxmap-poison-in-the-air
- Partner/awards: Younes, Kofman, Shaw, Song; Laredo with Texas Tribune; AHCJ Award 2022; UF Investigative Data Journalism Award; Goldsmith honoree
- Found: 1,000+ cancer-risk hotspots from EPA's own dormant RSEI model; ~256,000 people above EPA's acceptable ceiling; majority-Black tracts face double the industrial pollution.
- Types: concentrated-harm-hotspot; disparate-impact-by-race-or-geography; regulatory-capture; institutional-coverup; dormant-public-model-operationalization
- Evidence: Open-public bulk EPA RSEI output (~7B rows, 810m grid) on TRI self-reports; 193/200 top emitters contacted, 29% of responders flagged errors corrected; census joins; resident/scientist interviews.
- Systems: EPA RSEI model; Toxics Release Inventory; Census demographics
- Signature: dormant-public-model-operationalization: run the agency's own model nationally, sum across facilities per grid cell (the cumulative step EPA skips), join to demographics and school locations.
- Method: https://www.propublica.org/nerds/visualizing-toxic-air
- Impact: EPA stepped-up monitoring; Clean Air Laredo Coalition; fed EtO rulemakings.

### Temp Land (2013) — environment-labor-tech
- URL: https://www.propublica.org/article/the-expendables-how-the-temps-who-power-corporate-giants-are-getting-crushe
- Partner/awards: "Taken for a Ride" with APM Marketplace; Gold Barlett & Steele Award 2014; Sidney Award
- Found: Temps ~50% higher injury risk (CA/FL), ~6x in Florida blue-collar work; raitero fees pushed pay below minimum wage; race code words in enforcement files.
- Types: extraction-from-captive-population; disparate-impact-by-race-or-geography; algorithmic-or-systematic-denial; two-tier-labor-arbitrage
- Evidence: Request-gated state workers' comp claims microdata (>3.5M claims, 5 states, FROI/SROI filings); OSHA/EEOC enforcement files; worker pay stubs; hiring-hall field observation; lawsuits.
- Systems: state workers' comp FROI/SROI claims databases (CA/FL/MA/OR/MN); OSHA/EEOC enforcement files
- Signature: claims-microdata-denominator: classify claims temp-vs-non-temp via employer/agency codes, divide by per-sector employment denominators, compare within matched occupations; fee-stacking arithmetic proves sub-minimum wages.
- Method: https://www.propublica.org/nerds/how-we-calculated-injury-rates-for-temp-and-non-temp-workers
- Impact: California AB 1897 joint liability; OSHA temp-worker initiative.

### Insult to Injury: The Demolition of Workers' Comp (2015) — environment-labor-tech
- URL: https://www.propublica.org/article/the-demolition-of-workers-compensation
- Partner/awards: NPR (Howard Berkes) co-reporting
- Found: 33 states cut injured-worker benefits since 2003; the same arm worth $48,840 in Alabama vs. $439,858 in Illinois; ~$30B/yr shifted to taxpayers.
- Types: policy-erosion-across-jurisdictions; extraction-from-captive-population; cost-shift-to-public
- Evidence: 50-state + DC + FECA statutory benefit schedules self-codified and verified with state officials/attorneys/judges; commercial insurance premium/profitability data; consent-based case files and medical records; legislative histories; lobbyist interviews.
- Systems: state statutory benefit schedules (50 states + DC + FECA, self-codified)
- Signature: benefit-schedule-codification: price the identical standardized injury through every state's formula; one comparable table exposes inter-state inequity and post-2003 amendment-wave erosion.
- Method: https://www.propublica.org/article/workers-comp-benefits-how-much-is-a-limb-worth-methodology
- Impact: OSHA echo report; 2016 Labor Department report; Oklahoma opt-out struck down.

### COVID-19 in Meatpacking Plants (2020-2022) — environment-labor-tech
- URL: https://www.propublica.org/article/emails-reveal-chaos-as-meatpacking-companies-fought-health-agencies-over-covid-19-outbreaks-in-their-plants
- Partner/awards: ProPublica original (Grabell, Perlman, Yeung)
- Found: Tyson, Smithfield, JBS fought health departments and hid case counts; >24,000 cases and 87 worker deaths by June 2020; lobbying produced Trump's stay-open order.
- Types: institutional-coverup; regulatory-capture; extraction-from-captive-population
- Evidence: FOIA fan-out to dozens of state/local health agencies (internal emails, texts, meeting notes); independently compiled case-count aggregation; 2022 House Select Subcommittee document production; worker interviews.
- Systems: none named
- Signature: records-request-email-reconstruction: when the company is FOIA-immune, harvest the counterparty's records — identical requests to dozens of health departments reassemble the private conduct from the government side.
- Method: [inferred]

### How Dollar Stores Became Magnets for Crime and Killing (2020) — environment-labor-tech
- URL: https://www.propublica.org/article/how-dollar-stores-became-magnets-for-crime-and-killing
- Partner/awards: Co-published with The New Yorker (MacGillis; Campbell contributing)
- Found: 200+ violent gun incidents at Dollar General/Family Dollar since 2017, ~50 deaths; cause is the 2-3-worker, ~5%-of-sales payroll-cap business model.
- Types: concentrated-harm-hotspot; extraction-from-captive-population; externalized-security-cost
- Evidence: Open-public Gun Violence Archive incident aggregation; request-gated police calls-for-service by address; local news archives; SEC filings/investor materials for the payroll model; police, family, worker interviews.
- Systems: Gun Violence Archive; Dayton PD calls-for-service data; SEC filings
- Signature: incident-database-brand-join: filter a national incident database on brand/location, join to store-count growth and the disclosed labor-cost model; benchmark calls-per-address against a comparator institution.
- Method: [inferred]

### The Tiger Mom Tax & Breaking the Black Box pricing experiments (2015-2016) — environment-labor-tech
- URL: https://www.propublica.org/article/asians-nearly-twice-as-likely-to-get-higher-price-from-princeton-review ; https://www.propublica.org/article/amazon-says-it-puts-customers-first-but-its-pricing-algorithm-doesnt
- Partner/awards: Angwin, Larson, Mattu, Kirchner; Machine Bias series — 2017 Pulitzer finalist, Explanatory Reporting
- Found: Princeton Review ZIP pricing quoted Asians the top tier 1.8x as often; Amazon buy box steered ~75% of placements to Amazon/FBA at ~20% premium.
- Types: algorithmic-or-systematic-bias; disparate-impact-by-race-or-geography; platform-complicity-by-design; mystery-shopper-price-probe; self-preferencing-audit
- Evidence: Constructed scrape/mystery-shop of the target's own quote engine per ZIP; U.S. Census demographics per ZIP; Amazon listings scraped with logged-out/non-Prime simulation; company responses.
- Systems: U.S. Census ZIP demographics
- Signature: mystery-shopper-price-probe: query the seller's own pricing engine across the full ZIP space holding product constant; join quoted tier to demographics; disparate impact emerges without algorithm access.
- Method: https://www.propublica.org/article/when-big-data-becomes-bad-data
- Impact: Canonical algorithmic-fairness citations; buy-box later central to Amazon antitrust scrutiny.

### Facebook ad-targeting discrimination experiments (2016-2017) — environment-labor-tech
- URL: https://www.propublica.org/article/facebook-lets-advertisers-exclude-users-by-race
- Partner/awards: Angwin, Parris; later Tobin, Varner; Machine Bias (Pulitzer finalist 2017); age-targeting spin-off with NYT
- Found: ProPublica bought housing ads excluding protected classes ("Ethnic Affinity"), approved in ~15 minutes; $30 bought "Jew hater" targeting; 2017 re-test showed announced fix failed.
- Types: platform-complicity-by-design; algorithmic-or-systematic-denial; disparate-impact-by-race-or-geography; broken-remediation-verification
- Evidence: Constructed platform experiment — real paid ad purchases on Facebook's live ad-buying interface with screenshots/receipts and approval timestamps; Facebook policy statements; FHA legal framework; expert legal review.
- Systems: Facebook ad-buying interface (probed)
- Signature: ad-purchase-probe: construct the forbidden transaction yourself; record acceptance and approval latency; re-run the identical probe after the announced fix (remediation-audit) — the diff is the story.
- Method: [inferred]
- Impact: HUD charge 2019; 2019 civil-rights settlement; 2022 DOJ ad-delivery settlement.

### What Facebook Really Knows: instrumented crowdsourcing (2016-2019) — environment-labor-tech
- URL: https://www.propublica.org/article/facebook-doesnt-tell-users-everything-it-really-knows-about-them
- Partner/awards: Ad Collector federated with Spiegel, SZ, Tagesschau, CBC et al.; later stewarded by Quartz/Globe and Mail
- Found: Browser extension revealed 52,000+ profiling attributes and hidden data-broker categories; Political Ad Collector captured 100,000+ targeted political ads until Facebook blocked it.
- Types: platform-complicity-by-design; institutional-coverup; obstruction-as-confirmation
- Evidence: Constructed instrumented crowdsourcing — purpose-built extension harvesting ~16,000 consenting users' ad-interest pages and served ads; scraped advertiser-facing category list; first-person data-broker opt-out tests; Facebook statements.
- Systems: Political Ad Collector (purpose-built browser extension)
- Signature: instrumented-crowdsourcing: distribute a collection instrument to thousands of consenting users; diff user-facing vs. advertiser-facing views (two-views-diff); the platform's countermeasures function as confirmation.
- Method: https://propublica.github.io/political-ad-collector/
- Impact: Fed FTC/congressional scrutiny; Facebook launched weaker Ad Library under pressure.

### Rent Going Up? One Company's Algorithm Could Be Why (RealPage) (2022) — environment-labor-tech
- URL: https://www.propublica.org/article/yieldstar-rent-increase-realpage-rent
- Partner/awards: ProPublica original (Vogell; data: Coryne, Little)
- Found: YieldStar pooled competitors' nonpublic lease data to price apartments (~19.7M units touched, ~90% recommendation adoption); 10 RealPage clients ran 70% of one Seattle ZIP.
- Types: platform-complicity-by-design; algorithmic-cartel-facilitation; extraction-from-captive-population
- Evidence: Open-public marketing materials, earnings calls, user-group records, SEC filings; commercial CoStar rent data; constructed Belltown micro-market census; former-employee, landlord, tenant interviews; antitrust expert review.
- Systems: CoStar; SEC filings
- Signature: vendor-concentration-analysis: reconstruct a micro-market's inventory, attribute buildings to managers and managers to the pricing vendor; compute algorithm-priced supply share plus user-vs-nonuser price divergence.
- Method: [inferred]
- Impact: DOJ antitrust suits and settlements; tenant class actions; local ordinances.

## Meta-methods (report-09)

### Scraping for Journalism: A Guide for Collecting Data (2010) — meta-methods
- URL: https://www.propublica.org/nerds/doc-dollars-guides-collecting-the-data
- Found: Five-chapter Dollars for Docs curriculum: hostile-format pharma disclosures (Flash widgets, image PDFs, paginated HTML) engineered into one cross-company payments database.
- Evidence: Scraped company disclosure sites; Google Refine clustering/dedupe; PDF-to-text; ImageMagick+Tesseract OCR — all constructed from open but hostile-format mandated disclosures.
- Systems: pharma company disclosure portals; Google Refine; ImageMagick/Tesseract OCR
- Signature: hostile-format-normalization: treat deliberately heterogeneous mandated disclosure as a solvable engineering problem; acquire, normalize, clean, unify — published as a teachable pipeline.
- Method: same as URL

### Heart of Nerd Darkness: Why Dollars for Docs Was So Difficult (2013) — meta-methods
- URL: https://www.propublica.org/nerds/heart-of-nerd-darkness-why-dollars-for-docs-was-so-difficult
- Found: Candid record-linkage writeup: 15 companies' disclosures, different name conventions, no shared identifiers; cross-source physician matching dominates the cost of a unified database.
- Evidence: 15 pharma companies' scraped disclosure files matched against each other and license rosters — constructed entity-resolution corpus.
- Systems: state medical license rosters
- Signature: record-linkage-cost-accounting: entity resolution is the dominant cost of accountability databases; a single mandated format (CMS Open Payments) was the eventual fix the scrape demonstrated demand for.
- Method: same as URL

### Message Machine: Reverse Engineering Political Microtargeting (2012) — meta-methods
- URL: https://www.propublica.org/nerds/how-propublicas-message-machine-reverse-engineers-political-microtargeting
- Found: Readers forwarded campaign emails plus demographics; TF-IDF/cosine-similarity clustering minted email variants; variant assignment correlated with recipient demographics exposed microtargeting.
- Evidence: Crowdsourced reader-forwarded campaign emails with short demographic profiles; TF-IDF word vectors and similarity thresholds stored in Daybreak key-value store.
- Systems: Daybreak key-value store
- Signature: crowd-panel-output-reconstruction: when the targeting model is private, reconstruct it from the outputs delivered to a crowdsourced panel.
- Method: same as URL

### How We Calculated Injury Rates for Temp and Non-Temp Workers (2013) — meta-methods
- URL: https://www.propublica.org/nerds/how-we-calculated-injury-rates-for-temp-and-non-temp-workers
- Found: The statistical-standards post for accusatory disparity claims: comparable injury rates, not counts, with the denominator problem treated as the central methodological choice.
- Evidence: State workers' compensation claims microdata; employment denominators per sector [archetype partly inferred by the report from title/summary].
- Systems: state workers' comp claims databases
- Signature: defended-denominator: a disparity is a story only once you have defended the denominator.
- Method: same as URL

### Casino-Driven Design (2013) — meta-methods
- URL: https://www.propublica.org/nerds/casino-driven-design
- Found: UI discipline for crowdsourced transcription (Free the Files): remove every distraction, keep one document and few fields center-screen, make progress visible.
- Evidence: Free the Files volunteer-transcription interface design practice (constructed tooling).
- Systems: Free the Files app
- Signature: casino-driven-design: borrow the casino's attention discipline so volunteers stay accurate and engaged over thousands of repetitive documents.
- Method: same as URL

### Transcribable: Free the Files to Go (2013) — meta-methods
- URL: https://www.propublica.org/nerds/transcribable-free-the-files-to-go
- Found: The Free the Files crowdsourcing engine open-sourced as a Rails plugin so any newsroom can run verified crowd transcription of a PDF corpus.
- Evidence: Open-source Rails plugin distilled from Free the Files production use.
- Systems: Transcribable (Rails plugin)
- Signature: documents-in-structured-data-out: canonical crowd-in-the-middle transcription infrastructure, packaged for reuse across newsrooms.
- Method: same as URL

### Authenticating Email Using DKIM and ARC (Kasowitz emails) (2017) — meta-methods
- URL: https://www.propublica.org/nerds/authenticating-email-using-dkim-and-arc-or-how-we-analyzed-the-kasowitz-emails
- Found: Disputed threatening emails validated via DKIM signatures and ARC chains against the sending domains' published keys — cryptographic authentication of a leaked artifact.
- Evidence: Leaked/disputed emails; DKIM/ARC signature verification against DNS-published domain keys (constructed cryptographic check).
- Systems: DKIM/ARC domain keys
- Signature: cryptographic-document-authentication: turn he-said/she-said over a leaked artifact into a verifiable cryptographic check.
- Method: same as URL

### Chamber of Secrets: Teaching a Machine What Congress Cares About (2017) — meta-methods
- URL: https://www.propublica.org/nerds/teaching-a-machine-what-congress-cares-about
- Found: ML text classification over the congressional record/bill corpus surfaces each member's distinctive priorities; early documented "model proposes, human verifies" stance.
- Evidence: Open-public congressional record and bill corpus; machine-learning classification with human verification.
- Systems: congressional record/bill corpus
- Signature: model-proposes-human-verifies: machine classification surfaces candidate patterns; humans confirm before publication — later formalized in the AI policy.
- Method: same as URL

### GNU Make daily data pipelines (ProPublica Illinois) (2018) — meta-methods
- URL: https://www.propublica.org/nerds/gnu-make-illinois-campaign-finance-data-david-eads-propublica-illinois
- Found: Reproducible, idempotent Make-orchestrated pipeline loads 1.4GB of Illinois campaign-finance data daily; processing cut from hours to ~30 minutes; open-sourced.
- Evidence: Daily Illinois campaign-finance feeds; GNU Make as orchestration layer; open-source code release.
- Systems: Illinois campaign finance data; GNU Make
- Signature: pipeline-as-evidence-chain: reproducible, idempotent daily loads make the pipeline itself part of the evidence chain for a standing accountability database.
- Method: same as URL

### Nonprofit Explorer full-text search of 3 million 990s (2019) — meta-methods
- URL: https://www.propublica.org/nerds/new-search-full-text-of-3-million-nonprofit-tax-records-for-free
- Found: IRS 990 e-file XML plus OCR'd image filings unified into full-text-searchable Nonprofit Explorer (grants, investments, officer names), with API and people search.
- Evidence: IRS 990 e-file XML; OCR'd image filings; lineage of API (2013), 1.9M full text (2017), people search (2018), employees/officers view (2021).
- Systems: IRS 990 e-file XML; Nonprofit Explorer
- Signature: document-dump-to-database: national-scale unification of a mandated-disclosure corpus into standing searchable public infrastructure.
- Method: same as URL

### Collaborative Data Journalism Guide + Collaborate tool (2019) — meta-methods
- URL: https://www.propublica.org/nerds/collaborative-data-journalism-guide
- Found: Crowdsourcing/collaboration playbook distilled from Electionland and Documenting Hate, plus open-source django-collaborative for shared tip datasets — import, assign, track, auto-redact.
- Evidence: Distilled practice from Electionland/Documenting Hate; open-source django-collaborative on GitHub; GitBook user manuals and playbook.
- Systems: Collaborate (django-collaborative); Screendoor; Google Sheets
- Signature: shared-tip-database-management: import CSV/Sheets/Screendoor, assign tips, track contact status, auto-redact sensitive fields — coordination infrastructure for multi-newsroom tip corpora.
- Method: same as URL

### Documenting Hate database-construction retrospectives (2019) — meta-methods
- URL: https://www.propublica.org/nerds/building-a-database-from-scratch-behind-the-scenes-with-documenting-hate-partners
- Found: Constructing an incident database where no official statistic exists, plus the management layer — partner training, verification standards, access control — keeping a 180-newsroom database credible.
- Evidence: Crowdsourced hate-incident tips; partner-newsroom training and verification workflow documentation.
- Systems: Documenting Hate database
- Signature: no-official-statistic-database-construction: build the incident registry officialdom lacks; credibility comes from training, verification standards, and gated access.
- Method: same as URL

### The Data Store (2014-2023) — meta-methods
- URL: https://projects.propublica.org/datastore/
- Found: Investigation exhaust captured as citable, redistributable datasets: launched 2014 with free FOIA-derived plus $200 premium tiers; 2,000+ downloads year one; now an explicitly frozen archive.
- Evidence: Agency FOIA outputs (~half the catalog) plus constructed scraped/crowd-transcribed/leak-derived data existing nowhere else, spanning health, politics, criminal justice, education, business, environment.
- Systems: Medicare Part B/D; CMS Open Payments (Dollars for Docs); Nursing Home Compare; COMPAS Broward data; Chicago parking-ticket FOIA data; EPA RSEI/TRI toxmap data; FCC political files (Free the Files); IRS 990s
- Signature: exhaust-capture-layer: every major investigation's cleaned intermediate becomes a citable public asset; the frozen-archive banner honestly labels vintage instead of implying freshness.
- Method: [inferred]

### Machine Bias / COMPAS methodology (2016) — meta-methods
- URL: https://www.propublica.org/article/how-we-analyzed-the-compas-recidivism-algorithm
- Found: Algorithmic-audit exemplar: 18,610 Broward scores via records request; name+DOB linkage with disclosed 3.75% error on a 400-case sample; Northpointe's own definitions used.
- Evidence: Broward Sheriff public-records data matched to clerk and DOC records; logistic regression, Cox proportional hazards, race-stratified contingency tables; full notebook + SQLite DB released on GitHub.
- Systems: COMPAS scores (Broward County); Florida DOC records; GitHub compas-analysis release
- Signature: audit-with-adversarys-own-protocol: replicate the vendor's and county's own validation methodology and outcome definitions so the yardstick is not disputable.
- Method: same as URL

### Surgeon Scorecard methodology (2015) — meta-methods
- URL: https://www.propublica.org/article/surgeon-level-risk-short-methodology
- Found: Surgeon-level complication scoring: Medicare inpatient claims 2009-2013, eight electives, 16,827 surgeons; mixed-effects model with shrinkage; five-doctor panels reviewed diagnosis codes.
- Evidence: Medicare inpatient claims; R/lmer hierarchical model; white-paper PDF; published expert quotes; survived the RAND critique and rebuttal cycle on the record.
- Systems: Medicare inpatient claims (CMS)
- Signature: methodology-as-white-paper: publish the full model specification plus expert commentary; transparent methodology that survives formal external academic attack.
- Method: https://static.propublica.org/projects/patient-safety/methodology/surgeon-level-risk-methodology.pdf

### Sacrifice Zones / Toxmap methodology (2021) — meta-methods
- URL: https://www.propublica.org/article/how-we-created-the-most-detailed-map-ever-of-cancer-causing-industrial-air-pollution
- Found: Environmental-modeling sidebar: ~7B rows of RSEI output; exclusions enumerated with the directional claim the map "underestimates" risk; 193/200 top emitters contacted, 29% error flags corrected.
- Evidence: EPA RSEI output (810m grid) on self-reported TRI emissions; validation with air-modeling experts including a former RSEI contractor; full data released.
- Systems: EPA RSEI; Toxics Release Inventory
- Signature: directional-limitation-disclosure: enumerate exclusions with reasons and state the bias direction; validate the model with the audited party's own former contractor and the emitters themselves.
- Method: same as URL

### Car insurance disparities methodology (2017) — meta-methods
- URL: https://www.propublica.org/article/minority-neighborhoods-higher-car-insurance-premiums-methodology
- Partner/awards: With Consumer Reports
- Found: Pricing audit: ~30M purchased Quadrant premium quotes plus S&P rate filings compared to zip-level paid-loss risk (only CA/IL/MO/TX released data) via smoothing splines.
- Evidence: Purchased commercial Quadrant quotes (44 driver profiles); S&P Global rate filings; records requests to all 50 insurance commissioners; limitations ("relatively low R-squared") conceded in print; industry response quoted.
- Systems: Quadrant Information Services quotes; S&P Global rate filings
- Signature: purchased-quote-vs-risk-benchmark: standardized driver profile priced across ZIPs, compared against aggregate loss-based risk; disclosed thresholds, trims, and weak fits.
- Method: same as URL

### Lost Mothers methodology (2017-18) — meta-methods
- URL: https://www.propublica.org/article/how-we-collected-nearly-5-000-stories-of-maternal-harm
- Partner/awards: With NPR; distribution via Univision, Cosmopolitan, The Root, Texas Tribune, CUNY outreach
- Found: Crowdsourced cohort construction: ~5,000 callout responses; deceased mothers found via public social/GoFundMe posts, verified against obituaries and public records; representation gap measured and disclosed.
- Evidence: Callout questionnaire distributed for demographic reach; social-media discovery; obituary/public-record verification; NYU graduate students contacted families; Black-mother undercount documented with corrective outreach.
- Systems: Facebook/Twitter/GoFundMe/YouCaring (discovery surfaces)
- Signature: crowd-cohort-with-verification-chain: social discovery, obituary/public-record confirmation, then family contact makes a crowd-assembled death registry citable; publish who is missing from the sample.
- Method: same as URL

### Federal health-agency workforce tracker methodology (2025) — meta-methods
- URL: https://www.propublica.org/article/propublica-health-agencies-workers-methodology
- Found: Directory-diff estimation: HHS employee directory (~140K entries) snapshotted and diffed; disappearance of a pre-Jan 25, 2025 email counted as a departure; caveats enumerated.
- Evidence: directory.psc.gov snapshots diffed over time; LinkedIn/open-source spot checks; interviews and test cases; AI-classified job titles manually reviewed; HHS non-response noted on the record.
- Systems: HHS employee directory (directory.psc.gov); LinkedIn
- Signature: directory-diffing: archive a public roster on a cadence and diff snapshots to measure what the institution refuses to report; enumerate exclusions and alternative explanations.
- Method: same as URL

### The Secret IRS Files leak verification (2021) — meta-methods
- URL: https://www.propublica.org/article/the-inside-story-of-how-we-reported-the-secret-irs-files
- Found: Source-unknown IRS leak authenticated by contacting people in the data, cross-referencing SEC filings/court records/trade reporting, and reconstructing dataset structure; ethics and legal theory published.
- Evidence: Leaked IRS dataset of unknown provenance; SEC filings, court records, and stock-trade reporting as cross-references; subject-contact verification.
- Systems: SEC filings; court records
- Signature: authenticity-substitutes-for-source-identity: when the leaker is unknown, subject contact plus regulatory cross-reference plus structural reconstruction carries the publication decision.
- Method: same as URL

### The Opportunity Gap methodology (2011) — meta-methods
- URL: https://www.propublica.org/article/opportunity-gap-methodology
- Found: Federal dataset repurposing: U.S. Dept. of Education civil-rights data; free/reduced-price-lunch share chosen as the poverty proxy — the disclosed load-bearing analytic choice.
- Evidence: Open-public U.S. Department of Education civil-rights data collection.
- Systems: DoE Civil Rights Data Collection
- Signature: disclosed-proxy-choice: name the proxy variable and justify it (strongest observed relationship to advanced-course access).
- Method: same as URL

### Free the Files (2012) — meta-methods
- URL: https://projects.propublica.org/free-the-files/
- Found: ~1,000 volunteers transcribed 5,000+ FCC political-ad PDFs across 33 swing markets, logging on the order of $1B in 2012 ad buys — data government never held.
- Evidence: FCC station political files (open non-standardized PDFs); crowd transcription with multi-volunteer agreement before an entry counted [partly inferred]; casino-driven UI; output persists as dataset and API.
- Systems: FCC station political files; Free the Files API; Transcribable
- Signature: crowd-transcribe-the-disclosure-regime: when transparency law forces publication but not machine-readability, the verified crowd converts documents into the missing data layer.
- Method: https://www.propublica.org/article/crowdsourcing-campaign-spending-what-we-learned-from-free-the-files

### Electionland (2016-2020) — meta-methods
- URL: https://www.propublica.org/electionland/
- Found: Same-day geolocated voter-experience incident monitoring: ~600 journalism students on social discovery, tips triaged in Meedan Check, routed to 300+ local reporters.
- Evidence: Crowdsourced social-media incident discovery; First Draft verification protocols; coalition with USA Today Network, WNYC, Univision, Google News Lab.
- Systems: Meedan Check
- Signature: catcher-verifier-local-reporter-pipeline: an evidence class FOIA cannot produce (records do not exist yet), verified through a staged chain before publication.
- Method: [inferred]

### Documenting Hate (2017-2019) — meta-methods
- URL: https://projects.propublica.org/graphics/hatecrimes
- Found: National incident-level hate/bias database built because voluntary FBI UCR reporting is structurally broken: 6,000+ submissions, 180+ partner newsrooms, 230+ stories.
- Evidence: Victim/witness submissions; partner access gated by agreement; First Draft-trained verifiers; every tip verified in Check before journalistic use; ML-driven News Index.
- Systems: Meedan Check; Documenting Hate News Index; FBI UCR (broken baseline)
- Signature: tips-as-leads-not-facts: a partner-gated shared database with mandatory verification before any tip becomes reportable fact.
- Method: [inferred]

### Lost Mothers crowdsourcing machinery (2017) — meta-methods
- URL: (none in entry — cross-references §3.5) https://www.propublica.org/article/how-we-collected-nearly-5-000-stories-of-maternal-harm
- Found: Evidence class: a named cohort of U.S. maternal deaths plus ~4,000 near-misses that no agency could produce — CDC counts deaths but cannot release identities.
- Evidence: Crowd callout; social-media discovery; obituary/public-record confirmation; family contact (machinery view of the §3.5 methodology).
- Systems: none named
- Signature: crowd-assembled-death-registry: the verification chain makes citable what official statistics structurally cannot name.
- Method: same as URL

### Free-standing tip infrastructure (2014-) — meta-methods
- URL: https://www.propublica.org/tips
- Found: Standing secure intake: encrypted web form, Signal, postal mail, SecureDrop over Tor, plus a Tor onion mirror of the site; published standard for a good tip.
- Evidence: Multi-channel secure submission infrastructure; all submissions reviewed; responses may come "days, weeks, months or even years" later.
- Systems: SecureDrop; Signal; Tor onion mirror
- Signature: standing-secure-intake: persistent leak infrastructure with a published quality bar — specifics, evidence not already known, documents, powerful actors causing significant harm.
- Method: [inferred]

### Structured-callout tooling (2019) — meta-methods
- URL: https://github.com/propublica/django-collaborative
- Found: Callouts run on Screendoor forms, shared through Collaborate/django-collaborative — assignment, contact logging, auto-redaction, live sync; engagement reporting as a story-finding discipline.
- Evidence: Screendoor forms; open-source django-collaborative; GitBook manuals; Nieman Lab and GIJN engagement-reporting writeups.
- Systems: Screendoor; Collaborate (django-collaborative); Google Sheets
- Signature: engagement-reporting-as-story-finding: structured callouts plus shared tip management convert the audience into a sourced, verifiable acquisition channel.
- Method: https://propublica.gitbook.io/collaborate-user-manual

### Local Reporting Network (2018-) — meta-methods
- URL: https://www.propublica.org/article/local-investigative-journalism-growth
- Found: ProPublica reimburses a local newsroom for one reporter's salary (up to $80,000 plus benefits) for year-long investigations; ~100 projects since 2018; expanding 50-state.
- Evidence: Partnership model pairing local reporters with ProPublica editors, data, research, and news-apps staff; 2026 round is three cohorts of five partnerships.
- Systems: none named
- Signature: distributed-acquisition-network: converts methodology infrastructure into reach — deep local/state records national FOIA strategies never touch, produced at national standard [inferred by report].
- Method: [inferred]

### The "no surprises" rule (ongoing) — meta-methods
- URL: https://www.propublica.org/code-of-ethics
- Found: Subjects portrayed negatively get written bulleted assertions, interview offer, and response deadline pre-publication; extended to data subjects at scale (193/200 facilities contacted).
- Evidence: Code of Ethics text; exemplars — U.S. Century Bank questions published, Alito WSJ prebuttal proving letter specificity, Providence 100+ pages exchanged over two months.
- Systems: none named
- Signature: no-surprises-letter: critical assertions in writing with a deadline, covering framing as well as facts; the correspondence itself is publishable if the subject cries foul.
- Method: https://gijn.org/stories/seeking-comment-for-your-investigation-tips-for-the-no-surprises-letter/

### Document authentication doctrine (2017-2021) — meta-methods
- URL: https://www.propublica.org/nerds/authenticating-email-using-dkim-and-arc-or-how-we-analyzed-the-kasowitz-emails
- Found: Two authentication modes: cryptographic (DKIM/ARC for disputed emails) and triangulated (leak verification via subject contact plus regulatory cross-reference, per IRS Files).
- Evidence: Kasowitz DKIM/ARC verification; Secret IRS Files authentication practice (subject contact, SEC/court cross-reference).
- Systems: DKIM/ARC domain keys
- Signature: authenticate-before-publish: leaked artifacts get cryptographic or cross-reference authentication; source identity is not required once authenticity is established.
- Method: same as URL

### AI use policy (ongoing) — meta-methods
- URL: https://www.propublica.org/article/using-ai-responsibly-for-reporting
- Found: AI for analysis and lead-generation only, never writing; models instructed not to guess; every AI-assisted detail human-confirmed pre-publication; dual-reporter review; self-hosted models for sensitive material.
- Evidence: Published policy; Utah misconduct analysis dual-reporter review; Uvalde evidence transcription on self-hosted models.
- Systems: none named
- Signature: model-proposes-human-verifies: classification surfaces candidates, humans confirm each detail before publication; sensitive material never leaves self-hosted models.
- Method: same as URL

### Statistical review infrastructure (2017-) — meta-methods
- URL: https://www.propublica.org/nerds/introducing-our-data-journalism-advisers
- Found: Four standing academic advisers (Hernan, Lang, Lynch, Rehavi) review methodologies and white papers; physician panels; replication-grade releases deliberately invite academic audit.
- Evidence: Named advisers announcement; Surgeon Scorecard white paper plus RAND engagement; COMPAS GitHub and toxmap data releases as replication artifacts.
- Systems: GitHub (compas-analysis)
- Signature: external-eyes-before-publication: standing methodological advisers plus white-paper practice plus deliberate exposure of data/code to academic replication.
- Method: same as URL

### Corrections policy (ongoing) — meta-methods
- URL: https://www.propublica.org/corrections
- Found: "Fully, quickly and ungrudgingly": standing reverse-chronological corrections page in standardized format with dedicated intake; no fabrication, composites, plagiarism, or paying for interviews; restricted anonymity.
- Evidence: Code of Ethics correction policy; standing corrections page practice with dated standardized entries.
- Systems: none named
- Signature: standardized-correction-path: dated, formatted, publicly logged corrections with an intake address, as a trust mechanism.
- Method: [inferred]

# ProPublica index — reports 11 (immigration & border) and 12 (education, children & family services)

## Immigration & border (report-11)

### Listen to Children Who've Just Been Separated From Their Parents at the Border (2018) — immigration
- URL: https://www.propublica.org/article/children-separated-from-parents-border-patrol-cbp-trump-immigration-policy
- Partner/awards: ProPublica original (Ginger Thompson); series won Peabody Catalyst, Polk, Tobenkin; Pulitzer Public Service finalist; Thompson won 2019 John Chancellor Award
- Found: Covert CBP-facility audio caught ~10 separated children wailing, agent joking "orchestra"; 6-year-old's recited phone number let ProPublica identify her and detained mother Cindy Madrid.
- Types: custody-harm-concealment; sensory-ground-truth
- Evidence: Leaked covert audio via attorney Jennifer Harbury chain of custody; telephone verification interview with the aunt; family interviews; government policy statements as frame.
- Systems: none named
- Signature: Embedded-verifier leak authentication: leaked recording carried its own verification key — a recited phone number; dialing it authenticated the tape, located the family, named the case.
- Method: [inferred]
- Impact: Executive order ending family separation within ~48 hours; tape played in Congress.

### Inside the Cell Where a Sick 16-Year-Old Boy Died in Border Patrol Care (2019) — immigration
- URL: https://www.propublica.org/article/inside-the-cell-where-a-sick-16-year-old-boy-died-in-border-patrol-care
- Partner/awards: Robert Moore, Susan Schmidt, Maryam Jameel; follow-up co-published with El Paso Matters
- Found: Cell video disproved CBP account of Carlos Hernandez Vasquez's death: collapsed 1:24 a.m., unattended four-plus hours; three logged welfare checks unsupported by footage.
- Types: official-account-falsification; custody-harm-concealment; welfare-check-fabrication
- Evidence: Cell surveillance video plus police/EMS records and detainee logs via Texas PIA from Weslaco PD; nurse treatment notes; autopsy; independent forensic-expert review; interviews.
- Systems: Texas PIA (Weslaco Police Department records); Border Patrol subject activity log
- Signature: Parallel-custodian-route-plus-footage-diff: identified the local PD as second custodian, used its disclosure law; diffed press release, activity log and nurse orders against timestamped footage.
- Method: [inferred]
- Impact: CBP changed sick-detainee check practice; acting commissioner Sanders resigned; internal review confirmed failures.

### Inside the Secret Border Patrol Facebook Group (2019) — immigration
- URL: https://www.propublica.org/article/secret-border-patrol-facebook-group-agents-joke-about-migrant-deaths-post-sexist-memes
- Partner/awards: A.C. Thompson; ProPublica original ("Inside the Border Patrol" series)
- Found: Secret "I'm 10-15" Facebook group of ~9,500 current/former agents, including supervisors, joked about migrant deaths and posted vulgar faked AOC image.
- Types: insider-culture-exposure; identity-attributed-leak
- Evidence: Insider-leaked screenshots of closed-group posts; poster identities verified against Facebook profiles and duty stations; AP photographer authenticated the drowning photo the group called staged.
- Systems: none named
- Signature: Closed-forum membership attribution: joined leaked post authorship to verifiable employee identities and ranks, forcing agency response to named members — workforce-level finding, not anonymous posts.
- Method: [inferred]
- Impact: CBP investigated 70 employees; House committee moved to subpoena discipline records.

### Over 200 Allegations of Abuse of Migrant Children; 1 Case of Homeland Security Disciplining Someone (2019) — immigration
- URL: https://www.propublica.org/article/over-200-allegations-of-abuse-of-migrant-children-1-case-of-homeland-security-disciplining-someone
- Partner/awards: A.C. Thompson; records pried loose by ACLU of Arizona/Southern California FOIA litigation
- Found: DHS's own files showed 214 complaints of agents abusing migrant children (2009-2014) — beatings, Taser use — but exactly one disciplinary action.
- Types: accountability-vacuum; redaction-as-obstruction
- Evidence: ~30,000 pages internal DHS complaint/investigation records via ACLU FOIA request and lawsuit; FOIA-litigation court record (Judge Tuchi disclosure order); ACLU attorney interviews on redactions.
- Systems: none named
- Signature: Allegation-to-consequence ratio join: joined complaint intake stream to discipline outcome stream over a fixed period; the 214:1 ratio itself is the finding, no individual adjudication needed.
- Method: [inferred]
- Impact: Fed congressional scrutiny; litigation forced progressive unsealing of agent names.

### Trapped in Gangland / MS-13 on Long Island (2018) — immigration
- URL: https://www.propublica.org/series/ms-13-on-long-island
- Partner/awards: Hannah Dreier; co-published with New York magazine, Newsday, NYT Magazine; 2019 Pulitzer Prize for Feature Writing
- Found: Crackdown deported informant "Henry" after ICE memo exposed him; Suffolk logged murdered Latino teens as runaways; gang labels rested on mascot drawings, clothing.
- Types: cooperation-betrayal; neglected-victim-class; evidence-integrity-failure; designation-cascade
- Evidence: Informant's texts, confession pages, cellphone contents; ICE detention memo (expert-reviewed); police reports, court records, FOIA responses; 100+ interviews; jailhouse interviews with the teen.
- Systems: none named
- Signature: Designation-evidence-audit-plus-protocol-diff: pulled the evidentiary basis behind each gang designation and tested it; diffed agency's written missing-persons protocol against neighbors' and actual case files.
- Method: https://www.propublica.org/series/ms-13-on-long-island ("What It Was Like Reporting..." essay, April 10, 2018 entry)
- Impact: ICE stopped producing detailed detention memos; Suffolk reviewed missing-persons handling; schools curbed police referrals.

### No Sanctuary: In Pennsylvania, It's Open Season on Undocumented Immigrants (2018) — immigration
- URL: https://www.propublica.org/article/pennsylvania-ice-undocumented-immigrants-immigration-enforcement
- Partner/awards: Deborah Sontag, Dale Russakoff; co-published with The Philadelphia Inquirer
- Found: Philadelphia ICE office led nation: 64% of 2017 at-large arrests had no criminal conviction vs 38% nationally; Operation Cross Check yielded 35% vs billed ~70%.
- Types: enforcement-pattern-outlier; mission-label-mismatch; delegated-enforcement-drift
- Evidence: Unpublished ICE monthly arrest records via FOIA; 175+ hand-assembled individual case files; court filings and affidavits; arrestee, lawyer, and ICE-official interviews.
- Systems: ICE monthly arrest data (FOIA)
- Signature: Field-office distribution outlier detection: decomposed national arrest dataset by field office and criminality flag; Philadelphia's 64% non-criminal share vs 38% baseline surfaced the story.
- Method: [inferred]
- Impact: PA State Police limited immigration flagging; ACLU suit; policy changes and payouts.

### The Taking (2017) — immigration
- URL: https://features.propublica.org/eminent-domain-and-the-wall/the-taking-texas-government-property-seizure/
- Partner/awards: T. Christian Miller (ProPublica) with Kiah Collier and Julián Aguilar (The Texas Tribune)
- Found: Across 416 border-fence condemnation suits, represented landowners settled ~207% above initial offers vs ~33% unrepresented; DHS waived appraisals for ~90% of seized tracts.
- Types: asymmetric-bargaining-extraction; procedural-safeguard-evasion; transactional-error-ledger
- Evidence: 416 PACER condemnation dockets (197 hand-entered into database atop NPR dataset); FOIA'd DOJ records; 1,104 internal DHS emails via UT law professor; landowner interviews; Welch t-test.
- Systems: PACER; prior NPR border-fence condemnation dataset (base layer)
- Signature: Counterparty-stratified settlement delta: case-level takings table stratified by representation status, difference tested statistically (p < 2e-16); the disparity, not any single case, is the abuse.
- Method: https://www.texastribune.org/2017/12/13/how-we-reported-taking/
- Impact: Evidentiary baseline for 2019 congressional scrutiny of wall land seizures.

### How a Local Bureaucrat Made Millions Amid the Rush to Build a Border Fence (2017) — immigration
- URL: https://features.propublica.org/eminent-domain-and-the-wall/eminent-domain-border-wall-godfrey-garza-hidalgo-texas/
- Partner/awards: T. Christian Miller, Kiah Collier, Julián Aguilar (Texas Tribune); The Taking series
- Found: Godfrey Garza Jr. collected $3.5M via 1.5% commission on $232M levee-fence project; family firm Valley Data took $1M+ subcontracts from project contractors.
- Types: self-dealing-intermediary; percentage-fee-inflation
- Evidence: County contracts, invoices, check registers, bond documents from county's 2014 internal investigation; sworn depositions and unreleased civil-court files; county-commissioned investigative report; FBI/DHS emails.
- Systems: none named
- Signature: Commission-flow tracing: joined contract fee formula to disbursement ledgers to compute realized pay, then subcontractor list to corporate-ownership records to surface family-owned vendors.
- Method: [inferred]
- Impact: County lawsuits; FBI raided Dannenbaum; DHS withheld final $2.9M payment.

### Billions on the Border / Operation Lone Star (2022) — immigration
- URL: https://www.propublica.org/article/texas-governor-brags-about-his-border-initiative-the-data-doesnt-back-him-up
- Partner/awards: Kriel, Trevizo (ProPublica), Calderón (Marshall Project), Blakinger; ProPublica + The Marshall Project + The Texas Tribune
- Found: Only ~160 of 887 claimed fentanyl pounds came from OLS regions; DPS retroactively removed 2,000+ unrelated charges; ~40% of arrests were misdemeanor trespassing.
- Types: metric-inflation; retroactive-data-laundering; budget-outcome-mismatch
- Evidence: Sequential Texas DPS arrest-database snapshots via records requests (July 2021-Jan 2022); per-case criminal court records; state budget ledgers; governor's press releases and hearing transcripts; expert interviews.
- Systems: Texas DPS arrest databases (sequential snapshots)
- Signature: Metric-snapshot-diffing-plus-eligibility-re-scoring: repeated row-level pulls diffed for retroactive edits; each row re-scored against the program's own stated geography/charge/time criteria to quantify inflation.
- Method: [inferred]
- Impact: DPS purged 2,000+ charges; DOJ opened civil-rights investigation of Operation Lone Star.

### Deported and Imprisoned: The Venezuelans Trump Sent to CECOT (2025) — immigration
- URL: https://www.propublica.org/article/trump-el-salvador-deportees-criminal-convictions-cecot-venezuela
- Partner/awards: Rosenberg, Trevizo, Sanchez, Sandoval with Alianza Rebelde Investiga and Cazadores de Fake News; co-published with The Texas Tribune
- Found: Internal DHS data: only 32 of 238 CECOT deportees had U.S. convictions (6 violent); 130 had none; zero matches on 1,400-name Tren de Aragua lists.
- Types: collective-label-falsification; government-knowledge-finding; shadow-roster-construction
- Evidence: Internal DHS deportee data (provenance protected); U.S. and South American court/police records checked case-by-case; gang-list negative-match test; 100+ family interviews; EOIR data; tattoo/social-media analysis.
- Systems: EOIR case data; Venezuelan law-enforcement and Interpol Tren de Aragua lists (1,400 names)
- Signature: Roster-wise multi-jurisdiction ground-truth verification: reconstructed the full 238-man roster; verified the criminal label per person in every relevant jurisdiction and invoked watchlist; reported distribution vs claim.
- Method: [inferred]
- Impact: Reference accounting for litigation and congressional scrutiny; reporting held after men's release.

### Trump Has Detained the Parents of More Than 11,000 U.S. Citizen Kids (2026) — immigration
- URL: https://www.propublica.org/article/trump-family-deportations-ice-citizen-kids
- Partner/awards: Ernsthausen, Ariza, Funk, Rosenberg, Sandoval; ProPublica original
- Found: ICE detained parents of 11,000+ U.S.-citizen children in seven months; mothers deported at ~4x Biden-era rate; rewritten directive dropped the word "humane."
- Types: collateral-harm-quantification; administration-rate-comparison; policy-text-drift
- Evidence: ICE Form I-213 arrest narratives via UW Center for Human Rights records lawsuit; ICE deportation/detention databases via Deportation Data Project (FOIA); two directive versions; police records, flight manifests.
- Systems: ICE I-213 arrest records (UWCHR lawsuit); ICE deportation/detention databases (Deportation Data Project); Detained Parents Directive versions
- Signature: Cross-dataset identity matching for uncounted harm: matched ~85% of I-213s to deportation records on composite keys, validated 98% on held-out fields, then counted parents.
- Method: [inferred]
- Impact: Cited in congressional Democrats' investigation demands on citizen-child detentions.

### We Found More Than 40 Cases of Immigration Agents Using Banned Chokeholds (2026) — immigration
- URL: https://www.propublica.org/article/videos-ice-dhs-immigration-agents-using-chokeholds-citizens
- Partner/awards: Nicole Foy, McKenzie Funk, with Elba, Shan, Clark, Yar; ProPublica original
- Found: 40+ verified incidents in ~a year of agents using chokeholds banned by DHS's 2023 policy; victims included U.S. citizens; no evidence of discipline.
- Types: policy-violation-accumulation; accountability-vacuum
- Evidence: Bystander/social video corpus (TikTok, Instagram, local news, court records, professional photography); DHS 2023 use-of-force policy as scoring standard; eight-member expert panel review; per-person criminal-record checks.
- Systems: none named (self-built bystander-video corpus scored against DHS 2023 use-of-force policy)
- Signature: Video-corpus policy coding: harvested distributed bystander video, coded each verified incident against the agency's written rule via independent expert panel; the coded count, not any clip, is the story.
- Method: [inferred]
- Impact: Fed 2026 congressional demands for use-of-force reform.

### These Immigrant Kids Were Once Protected. Under Trump, Their Deportations Have Tripled (2026) — immigration
- URL: https://www.propublica.org/article/unaccompanied-minors-deportations-elder-chavez
- Partner/awards: Mica Rosenberg, Jeff Ernsthausen, with Trevizo, Yurkanin, Sandoval; ProPublica original
- Found: Unaccompanied minors removed at ~3x first-term rate after protections dismantled; courts issued 10,000+ removal orders monthly; most removed had no criminal history.
- Types: protection-rollback-effect; vulnerable-cohort-rate-shift
- Evidence: ICE detention records via FOIA (Oct 2018-Dec 2025, longitudinal); EOIR immigration-court case data; UCLA Law and TRAC external validation; SIJ/counsel policy documents; case reporting.
- Systems: EOIR case data; ICE detention records (FOIA); TRAC (validation)
- Signature: Administrative cohort rate comparison with interior-enforcement isolation: minors identified by birthdate, border apprehensions excluded, removal rates compared across equivalent windows of two administrations.
- Method: [inferred]
- Impact: Contributed to oversight scrutiny of EOIR judge firings.

## Education, children & family services (report-12)

### The Quiet Rooms (2019) — education-children
- URL: https://features.propublica.org/illinois-seclusion-rooms/school-students-put-in-isolated-timeouts/
- Partner/awards: ProPublica Illinois + Chicago Tribune; Shadid Award for Journalism Ethics; Hechinger Grand Prize
- Found: ~20,000 Illinois school seclusion incidents in 15 months; over a third of 12,000 detailed incidents had no documented safety reason — the sole legal justification.
- Types: statutory-violation-at-scale; undercount-exposure; documented-cruelty-in-official-records
- Evidence: FOIA'd incident narratives, timeout logs, training and notification records via 300+ requests to every Illinois district; hand-built incident database; federal CRDC counts as foil; lawsuits, police reports; 120+ interviews; site visits.
- Systems: CRDC (2015-16 self-reported seclusion counts)
- Signature: Standard-vs-log audit: every incident narrative coded against the single statutory trigger (safety) and its timing; plus zero-claim audit FOIAing 75 districts that reported zero seclusions.
- Method: https://www.propublica.org/article/illinois-school-students-seclusion-rooms-methodology
- Impact: Illinois emergency ban next day; 2021 permanent restrictions; criminal charge; federal bill.

### The Price Kids Pay (2022) — education-children
- URL: https://www.propublica.org/article/illinois-school-police-tickets-fines
- Partner/awards: ProPublica + Chicago Tribune; Worth Bingham Prize, Driehaus Award, IRE Award, EWA award, NABJ Salute to Excellence
- Found: 11,800+ police tickets to students in 141 of 199 districts circumvented Illinois' SB100 ban on school fines; Black students ticketed ~2x white peers.
- Types: law-circumvention-channel; disparate-impact-quantification; shadow-justice-process
- Evidence: Ticket-level citation records from 500+ FOIAs to districts and their police departments; SB100 and municipal-code texts; direct observation of 50+ hearing dates; family financial records and interviews.
- Systems: none named (first-of-its-kind reporter-built statewide ticket database)
- Signature: Two-institution handoff trace: banned output vanished from schools' books and reappeared in police records for the same incidents; FOIAing both sides and joining on incident/date/school exposed the relay.
- Method: [inferred]
- Impact: Superintendent urged stop within hours; AG probe; Illinois banned practice May 2025.

### Stuck Kids (2018) — education-children
- URL: https://features.propublica.org/stuck-kids/illinois-dcfs-children-psychiatric-hospitals-beyond-medical-necessity/
- Partner/awards: ProPublica Illinois original (Duaa Eldeib); 3rd-place 2018 Ruderman Foundation award
- Found: Nearly 30% of hospitalized DCFS foster children held beyond medical necessity — 800+ children, 27,000+ collective days, $7M paid for unnecessary hospital days.
- Types: custodial-warehousing; agency-self-knowledge; harm-monetization
- Evidence: DCFS "beyond medical necessity" tracking database via FOIA (~6,000 hospitalizations 2015-2017); leaked confidential DCFS case files and internal investigations; juvenile-court and public-guardian litigation files; clinician interviews.
- Systems: DCFS beyond-medical-necessity tracking database (Illinois, created 2015)
- Signature: Clearance-to-exit gap accumulation: per-child gap between discharge clearance and actual discharge, summed across the population into 27,000 lost days and a dollar figure.
- Method: https://www.propublica.org/article/illinois-psychiatric-hospitals-dcfs-reporting-duaa-eldeib (reporter essay; no formal methods page)
- Impact: Legislative hearings within days; class-action; Chicago Lakeshore lost federal funding.

### Overpolicing Parents (2022–2025) — education-children
- URL: https://www.propublica.org/article/mandatory-reporting-strains-systems-punishes-poor-families
- Partner/awards: ProPublica + NBC News (Hager, Philip, Hixenbaugh, Khimm, Rappleye)
- Found: CPS investigates ~3.5M children's homes yearly without warrants, ~5% substantiated; Maricopa investigated 38% of Black children in five years; West Virginia terminated parental rights fastest.
- Types: rights-asymmetry-mapping; disparate-impact-quantification; dragnet-yield-ratio; jurisdiction-outlier-ranking
- Evidence: NCANDS case-level files and AFCARS foster-care files from HHS archive; ACS/state administrative data via records requests; original 40-state agency survey on warrants; court rulings; 40+ interviews.
- Systems: NCANDS (FY2015-2020); AFCARS (2015-2019); HHS National Data Archive on Child Abuse and Neglect; NYC ACS entry-order data
- Signature: Population-denominator exposure rate: deduplicated federal case data per child divided by census under-18 population by race/county; paired with time-to-termination ranking and warrant-to-search ratio.
- Method: https://www.propublica.org/article/how-we-analyzed-child-welfare-investigation-data
- Impact: NY banned anonymous reports; Texas mandated Miranda-style CPS warnings.

### Level 14 (2015) — education-children
- URL: https://www.propublica.org/article/rape-drugs-disorder-shake-california-group-home-and-provoke-reform-efforts
- Partner/awards: ProPublica original (Joaquin Sapien; multimedia with Carrie Ching)
- Found: EMQ FamiliesFirst Davis campus for ~70 highest-need children collapsed after corporate policy shift: children vanished for days; 11-year-old reported rape; 911 calls surged.
- Types: institutional-collapse-reconstruction; regulator-latency
- Evidence: Facility "unusual incident reports" to state DSS via records requests; five years of complaint investigations for ~50 peer facilities; 18-month 911-call log after police denied reports; corporate/financial paper; three lawsuits; 30+ interviews.
- Systems: CA Department of Social Services unusual-incident reports and facility evaluations; Davis 911 dispatch log
- Signature: Proxy-record reconstruction: police reports refused, so 911 dispatch log substituted as frequency/type proxy, matched to interviews and incident reports; ~50 peer facilities pulled as baseline.
- Method: https://www.propublica.org/article/how-we-reported-level-14
- Impact: Campus shut; California pivoted from group homes; NYC cut contracts; liability verdict.

### The Unbefriended (2024–2026) — education-children
- URL: https://www.propublica.org/article/how-one-woman-endured-decade-neglect-new-york-guardianship
- Partner/awards: ProPublica original (Jake Pearson)
- Found: Guardian NYGS billed Judith Zbiegniewicz $450/month while she lived in squalor; guardian Yvonne Murphy routed wards to her own Beacon Eldercare — $1.5M revenue.
- Types: paper-reality-gap; self-dealing-fiduciary; oversight-capacity-arithmetic
- Evidence: Guardianship court files (accountings, examiner reviews, orders); litigation-disclosed Beacon client lists; insider NYGS records and six sources; building-inspection records and site visits; IRS exempt-organization negative check.
- Systems: NY guardianship court files (access-restricted, per named case); IRS exempt-organization records; NYC court-system caseload statistics
- Signature: Fiduciary flow cross-match: wards' court-filed accountings (money out) joined on ward name against guardian's company client list (money in); each match potential self-dealing no judge assembled.
- Method: [inferred]
- Impact: NY AG investigation; special counsel; task-force recommendations; Good Guardianship Act proposed.

### Unfit to Teach (2026) — education-children
- URL: https://www.propublica.org/article/california-fired-teacher-sexual-harassment
- Partner/awards: KQED + ProPublica co-publication (Holly McDede, Mollie Simon)
- Found: California credentialing commission left licenses intact in at least 67 district-confirmed sexual-misconduct cases (2019-2025); 14 rehired in education; Jason Agan got 7-day suspension, tenure.
- Types: dead-referral-pipeline; sanctioned-actor-migration; transparency-asymmetry
- Evidence: District misconduct files via CPRA requests to 300 largest districts (150+ produced; 350+ complaints); mandatory district reports; state credential database joined case-by-case; termination-hearing records via DGS.
- Systems: California Public Records Act; Commission on Teacher Credentialing public license database; Department of General Services termination-hearing records
- Signature: Referral-to-sanction join: local misconduct determinations reconstructed via mass records requests (central registry sealed), matched by educator name to public license status; plus longitudinal employer tracking.
- Method: https://www.propublica.org/article/california-teacher-misconduct-public-records
- Impact: Education secretary cited it launching national crackdown; profiled teacher left classroom.

### State of Disrepair (2023–2025) — education-children
- URL: https://www.propublica.org/article/idaho-deteriorating-schools-repair-bonds
- Partner/awards: ProPublica Local Reporting Network + Idaho Statesman (Becca Savransky, Asia Fields)
- Found: Journalists surveyed all 115 Idaho superintendents after 30 years without state assessment; every responder reported facility problems; 21% of 677 schools rated poor.
- Types: synthetic-census; structural-veto-mechanism; unused-remedy
- Evidence: Original structured survey of 115 superintendents (91% response); crowdsourced photos from 233 students/parents/teachers via instant-print cameras; tours of 39 buildings; bond-election and state facility-fund finance records.
- Systems: none named (journalist-built statewide facilities dataset)
- Signature: Distributed sensing census: full-frame official survey cross-checked against crowdsourced photo evidence and 39 in-person tours, producing statewide condition statistics no agency held.
- Method: https://www.propublica.org/article/idaho-hasnt-assessed-school-buildings-30-years-students-educators-helped-us-do-it ; https://www.propublica.org/article/community-reporting-tips-idaho-schools
- Impact: Legislature approved $2 billion over 10 years; long-failing district passed bond.

### Unequal Discipline (2022–2026) — education-children
- URL: https://www.propublica.org/article/gallup-mckinley-schools-native-student-discipline
- Partner/awards: ProPublica Local Reporting Network + New Mexico In Depth (Furlow; Jacobs, Fields, Miller)
- Found: Gallup-McKinley schools, with 25% of New Mexico's Native students, produced at least 75% of Native expulsions — 211 expulsions, 10x state rate; 735 police-involved incidents.
- Types: concentration-attribution; disparate-impact-quantification; definitional-elasticity-abuse
- Evidence: STARS discipline and enrollment extracts (2010-11 through 2021-22) via records requests to Public Education Department; NCES enrollment data; 80 interviews (47 parents/students); deleted district strategic plan.
- Systems: STARS (New Mexico student data system); NCES enrollment data
- Signature: Share-of-harm vs share-of-population decomposition: per-1,000 rates by district and race, state total decomposed by unit; 25% of population producing 75% of harm flags the outlier.
- Method: https://www.propublica.org/article/how-we-analyzed-new-mexico-school-discipline-data
- Impact: NM AG investigation; 2026 AG-commissioned report confirming disparities, demanding reform.

### Crackdown on Student Threats (2024–2026) — education-children
- URL: https://www.propublica.org/article/tennessee-school-threat-law-kids-arrested
- Partner/awards: ProPublica + WPLN/Nashville Public Radio (Aliyya Swaby, Paige Pfleger)
- Found: 519+ Tennessee students charged with mass-violence threats in 2023-24, youngest 7; ~80% dismissed/diverted; state confirmed 12 expulsions while reporters found 66 in 10 districts.
- Types: criminalization-of-noncrime; charge-outcome-funnel; data-vacuum-as-finding; disparate-impact-quantification
- Evidence: State juvenile-court case data via records request (charges, dispositions, three years); district records requests with catalogued refusals; police incident reports and arrest narratives; family/judge/attorney interviews; legislative records.
- Systems: Tennessee juvenile-court case data; state education department incident counts
- Signature: Arrest-to-adjudication funnel: charges followed to disposition (80% dismissed/diverted quantifies the dragnet); sample-vs-official extrapolation (66 vs 12 expulsions) proves monitoring broken; county enforcement-rate contrast.
- Method: [inferred]
- Impact: $100,000 settlement to 11-year-old's family; Tennessee fixed threats law April 2026.

### The Right to Read (2022) — education-children
- URL: https://www.propublica.org/series/the-right-to-read
- Partner/awards: ProPublica original (Swaby, Waldman; one piece with Gray Television/InvestigateTV); Emmy nomination
- Found: Across 3,100+ counties, low adult literacy correlates with depressed turnout (r=-0.57/-0.58, up to 7M votes); Olivia Coley-Pearson prosecuted twice for assisting voters.
- Types: structural-disenfranchisement-correlation; criminalized-assistance
- Evidence: NCES PIAAC small-area literacy estimates (public statistical product); Dave Leip's Atlas turnout counts over Census citizen-voting-age population (purchased/public); Coley-Pearson prosecution court records; assistance statutes; voter interviews.
- Systems: NCES PIAAC small-area literacy estimates; Dave Leip's Atlas of U.S. Elections; Census citizen-voting-age population
- Signature: Ecological correlation with robustness battery: county literacy joined to turnout across three cycles, terciles compared, 1,000-iteration resampling of small-county estimates; explicit causal humility.
- Method: https://www.propublica.org/article/voter-participation-literacy-accessibility
- Impact: No statute change; series produced multilingual voter guides in 10+ languages.

### Miseducation (2018) — education-children
- URL: https://projects.propublica.org/miseducation/
- Partner/awards: ProPublica original news app (Groeger, Waldman, Eads); reporting recipe released for local journalists
- Found: Lookup for 96,000 schools/17,000 districts: Black and Hispanic students less likely in AP/gifted, more likely suspended, expelled, referred to police; 69,000 schools skipped police question.
- Types: public-disparity-instrument; disparate-impact-quantification; undercount-exposure
- Evidence: Federal CRDC 2015-16 (public download, master school list); NCES Common Core of Data and EDGE geography; Stanford Education Data Archive pooled test scores — all public datasets.
- Systems: CRDC (2015-16); NCES Common Core of Data; NCES EDGE; Stanford Education Data Archive (SEDA)
- Signature: Risk-ratio grid with significance gating: standardized disparity risk ratios with 95% CIs computed per institution nationwide, non-significant cells suppressed; achievement gaps and segregation index joined.
- Method: https://projects.propublica.org/miseducation/methodology
- Impact: No single statute; became source infrastructure for local reporting nationwide.

### Barns, Go-Karts and Strip Malls (2026) — education-children
- URL: https://www.propublica.org/article/private-schools-vouchers-growth-florida-arizona-west-virginia
- Partner/awards: ProPublica (Smith Richards, O'Matz, Simon, Berry Hawes); companions include Texas Tribune co-publication
- Found: Voucher boom added 1,500+ private schools across 13 states ($10.6B allocated 2025); operators include convicted Ohio superintendent who drew $291,165 in Florida.
- Types: oversight-vacuum-mapping; sanctioned-actor-migration; subsidized-sector-boom-census
- Evidence: State private-school directories diffed over time (13 states); voucher/ESA payment data; cross-state licensure and criminal records for named operators; address-level site verification; agency jurisdiction-denial statements.
- Systems: State private-school directories (13 states); state voucher/ESA payment records
- Signature: Directory-diff-plus-payment-join: successive directory snapshots identify new entrants; joined to voucher payments and out-of-state discipline/criminal records to surface sanctioned-actor migration.
- Method: [inferred]

## Military, veterans & national security (report-13)

- (cross-ref) Disaster in the Pacific / 7th Fleet (2019) — military-veterans: 26-story Fitzgerald/McCain series (Pulitzer, National Reporting 2020); Navy mishap/command investigation files, courts-martial records, internal-warnings-vs-public-assurances diff; https://www.propublica.org/series/navy-accidents-pacific-7th-fleet — full extraction in sibling report.

### Brain Wars — Brain Injuries Remain Undiagnosed in Thousands of Soldiers (2010) — military-veterans
- URL: https://www.propublica.org/article/brain-injuries-remain-undiagnosed-in-thousands-of-soldiers
- Partner/awards: Co-reported/co-published with NPR (T. Christian Miller; Daniel Zwerdling)
- Found: Army files lacked concussion records for >75% of soldiers reporting concussions; ANAM test given to 580,000+ soldiers was retrieved diagnostically only ~1,500 times.
- Types: systemic-undercount; phantom-oversight; care-denial-by-policy
- Evidence: Unpublished internal Army studies (insider-obtained); private senior-official emails (Hoge, Schoomaker); published clinical literature; scores of interviews; contested FOIA fight for screening-program records.
- Systems: ANAM cognitive screening test; MACE concussion exam; post-deployment health assessment (PDHA)
- Signature: report-to-record deficit audit: join soldiers' contemporaneous concussion self-reports to official medical files; >75% absence is the undercount; plus instrument dead-letter check (580K administrations vs ~1,500 retrievals).
- Method: [inferred]
- Impact: Senate/House hearings within weeks; new Pentagon TBI policy; congressional TRICARE probe

### Disposable Army — Injured War Zone Contractors Fight to Get Care From AIG and Other Insurers (2009) — military-veterans
- URL: https://www.propublica.org/article/injured-war-zone-contractors-fight-to-get-care-from-aig-416
- Partner/awards: Joint investigation with Los Angeles Times and ABC News; Selden Ring Award 2010
- Found: AIG handled ~90% of Defense Base Act claims, collected $1.5B premiums, ~$600M profit; insurers contested nearly half of ~9,000 serious cases.
- Types: benefits-denial-machine; captive-market-profiteering; uncounted-population
- Evidence: Labor Department Longshore claims database (~31,000 claims) via LA Times FOIA suit; Army Audit Agency/GAO audits; court dispute files; 200+ interviews; 10,000+ pages corporate communications.
- Systems: Longshore Case Management System (Labor Department); carrier Notices of Controversion filings
- Signature: severity-stratified denial screen: denial/protest rates rise with claim severity strata (lost-work days, PTSD) — good-faith inversion; plus recomputing "disputed" from carriers' controversion notices vs Labor's narrower metric.
- Method: https://www.propublica.org/article/forgotten-warriors-explanation-of-analysis-416
- Impact: June 2009 congressional hearing; Pentagon IG examination; DBA overhaul study; 2012 reform bill

### The Drone War — Obama Administration's Drone Death Figures Don't Add Up (2012) — military-veterans
- URL: https://www.propublica.org/article/obama-drone-death-figures-dont-add-up
- Found: Official claims mutually impossible: "about 30" civilians killed Aug 2009-Aug 2010 vs later "single digits" total under Obama; independent tallies 138-832.
- Types: official-claims-incoherence; secrecy-boundary-mapping
- Evidence: Dated corpus of official casualty statements compiled from press briefings, wire stories, named-official speeches; independent NGO casualty databases as external bounds; NSC refusal-to-comment quoted as evidence.
- Systems: Bureau of Investigative Journalism drone database; New America Foundation tally; Long War Journal tally
- Signature: self-contradiction matrix: array dated official claims with coverage windows; test pairwise logical compatibility (interval vs cumulative); contradiction requires no external data.
- Method: [inferred]
- Impact: Fed transparency pressure preceding Obama's May 2013 drone-policy speech

### Failing the Fallen — The Military Is Leaving the Missing Behind (2014) — military-veterans
- URL: https://www.propublica.org/article/missing-in-action-us-military-slow-to-identify-service-members
- Partner/awards: Co-reported with NPR (Megan McCloskey/Rose; Kelly McEvers); Gracie Award, Alliance for Women in Media
- Found: JPAC identified 372 remains in five years on $373.1M — 600+ years to clear 45,000 missing; 9,400+ unknowns often already tentatively identified.
- Types: mission-throughput-failure; risk-averse-gatekeeping; method-obsolescence
- Evidence: National Archives case files (Kelder dental records); X-file corpus via litigant John Eakin's FOIA battle plus Pentagon insider package; internal JPAC memos/emails; budget-output data; ICMP/EAAF benchmark interviews.
- Systems: X-file corpus of 9,400+ unknowns; Eakin's searchable Manila cemetery-file database (3,000 files); National Archives POW dental/hospital records
- Signature: throughput-horizon arithmetic: backlog divided by measured annual output (45,000/72 = 600+ years) vs budget and mandate; plus single-case paper-trail replay (Kelder) and ICMP DNA-first benchmark.
- Method: [inferred]
- Impact: Hagel ordered review; agencies merged into DPAA; Holland removed; Kelder identified

### Reliving Agent Orange — The Children of Agent Orange / Dr. Orange (2015-2019) — military-veterans
- URL: https://www.propublica.org/article/the-children-of-agent-orange and https://www.propublica.org/article/alvin-young-agent-orange-va-military-benefits
- Partner/awards: Co-published with The Virginian-Pilot (Ornstein; Hixenbaugh; data Fresques, Pierce)
- Found: VA registry: birth defects 13.1% exposed vs 9.8% unexposed among 37,535 veterans; Alvin Young's $600,000 no-bid VA contract sustained decades of denial.
- Types: registry-suppressed-signal; science-gatekeeper-capture; burden-shifted-proof
- Evidence: Registry microdata via IRB research-access route after FOIA denial; two FOIA lawsuits for VA correspondence; veterans' FOIA memo corpora; contract records; 3,352-response structured crowdsourcing survey; IOM findings.
- Systems: VA Agent Orange Registry (668,000+ exams); Navy deck logs (700+ ships crowdsourced); Screendoor survey instrument
- Signature: within-family before/after cohort: each veteran's pre-service children as own control, diff post-exposure defect rates; plus gatekeeper career-trace joining Young's positions/contracts/recommendations to agency adoptions.
- Method: https://www.propublica.org/article/children-of-agent-orange-editors-note and https://guides.coralproject.net/propublica-agent-orange-crowdsourcing/
- Impact: Federal Circuit Procopio v. Wilkie ruling; Blue Water Navy Act passed 2019

### Inside Trump's VA — The Shadow Rulers of the VA (2018) — military-veterans
- URL: https://www.propublica.org/article/ike-perlmutter-bruce-moskowitz-marc-sherman-shadow-rulers-of-the-va
- Found: Ike Perlmutter, Bruce Moskowitz, Marc Sherman — no government roles — directed VA policy/personnel from Mar-a-Lago, weighing in on $10B+ Cerner contract.
- Types: shadow-governance; access-capitalism
- Evidence: Hundreds of FOIA-obtained emails and calendars between the trio and VA leadership (published in full); Leinenkugel removal memo matched to departures; insider interviews; calendar records.
- Systems: none named
- Signature: org-chart/deference mismatch: join correspondence corpus to formal org chart; approval-seeking language toward non-chart persons, corroborated by proposal-to-action and removal-list sequencing.
- Method: [inferred]
- Impact: Democrats vowed investigation; VoteVets sued; House oversight followed

### Inside Trump's VA — The VA's Private Care Program Gave Companies Billions and Vets Longer Waits (2018) — military-veterans
- URL: https://www.propublica.org/article/va-private-care-program-gave-companies-billions-and-vets-longer-waits
- Partner/awards: Co-reported with PolitiFact (Arnsdorf, Greenberg)
- Found: Middlemen TriWest and Health Net took $1.9B (24%) of $10.3B Veterans Choice spending as overhead; 41% of referrals broke 30-day statutory limit.
- Types: privatization-value-leak; sla-breach-at-scale
- Evidence: VA biweekly expenditure reports to Congress (public, unanalyzed); VA claims-processing and OIG referral-fee reports; GAO/CRS figures; fpds.gov contract records; court opinion revealing TriWest grand-jury probe; CEO emails.
- Systems: VA biweekly Choice expenditure reports to Congress; VA claims-processing reports; fpds.gov federal contract records
- Signature: overhead-ratio benchmark diff: compute administrative loss ratio ($1.9B/$7.9B = 24%) from the program's own reports, diff against ACA/commercial/Tricare benchmarks; plus statutory SLA breach count.
- Method: https://www.propublica.org/article/how-we-crunched-the-numbers-on-the-vas-private-care-program
- Impact: VA secretary conceded agency "taken advantage of"; DOJ probes proceeded

### The Night Raids (2022) — military-veterans
- URL: https://www.propublica.org/article/afghanistan-night-raids-zero-units-lynzy-billing
- Partner/awards: Michael Kelly Award; Overseas Press Club Ed Cunningham Award; spawned "The Night Doctrine" documentary
- Found: CIA-backed Afghan Zero Units killed at least 452 civilians in 107 raids (02 unit, 2017-2021), with no U.S. accounting.
- Types: atrocity-undercount; outsourced-accountability-void
- Evidence: 30+ raid-site field forensics; government statistical, hospital, death-certificate and coroner records; leaked intelligence/police/NGO incident reports; two insider Zero Unit soldiers' diaries; satellite geolocation; 350+ interviews.
- Systems: Afghan government statistical department records; Kabul federal forensics department records (death certificates, coroner reports)
- Signature: multi-registry casualty ledger: admit each raid row only when 2+ independent record types converge (testimony, site forensics, medical paper, satellite, insider reports); count published as floor.
- Method: https://www.propublica.org/article/afghanistan-night-raids-zero-units-lynzy-billing ("How We Reported This Story" in-article)
- Impact: No formal U.S. accounting; drove congressional and press attention to proxy-force accountability

### Military Court Secrecy — Bonhomme Richard and ProPublica v. the Navy (2022-2026) — military-veterans
- URL: https://www.propublica.org/article/navy-bonhomme-fire-records
- Found: Navy released two documents in Seaman Ryan Mays' $1B+ USS Bonhomme Richard arson trial despite 2016 public-access law; Mays acquitted.
- Types: statute-practice-gap; institutional-scapegoating (flagged); access-litigation-as-reporting
- Evidence: Contested court-martial filings (defense motions, prosecutor briefs); ProPublica's own federal complaint and emergency motion; Navy 400+ page command investigation; statutory text vs DoD implementing rules; expert interviews.
- Systems: USS Bonhomme Richard command investigation file; United States v. Mays court-martial docket
- Signature: statute-vs-practice release audit: enumerate statutory disclosure mandate, count actual releases in a live marquee case (two documents); plus systemic-findings vs single-defendant diff.
- Method: [inferred]
- Impact: Navy released tranches; DoD rewrote rules; March 2026 ruling for press access

### The Army Increasingly Allows Soldiers Charged With Violent Crimes to Leave the Military Rather Than Face Trial (2023) — military-veterans
- URL: https://www.propublica.org/article/military-army-administrative-separation
- Partner/awards: Co-published with The Texas Tribune and Military Times
- Found: Of ~900 soldiers granted Chapter 10 discharge in lieu of court-martial over a decade, more than half were accused of violent crimes, up from ~30%.
- Types: accountability-off-ramp; severity-drift
- Evidence: Army Court-Martial Information System data (cases back to 1989) via FOIA; named soldiers' charge sheets and probable-cause findings; 1978 watchdog recommendation; victim and Army official interviews.
- Systems: Army Court-Martial Information System
- Signature: off-ramp migration analysis: isolate Chapter 10 exits in case-level pipeline data, classify charges violent per NIJ definition across eight UCMJ articles, trend violent share 30% to 50%+.
- Method: https://www.propublica.org/article/military-army-administrative-separation (in-article methodology sidebar)
- Impact: 2024: Office of Special Trial Counsel approval now required for covered Chapter 10s

### Blinken Says Israeli Units Accused of Serious Violations Have Done Enough to Avoid Sanctions (2024) — military-veterans
- URL: https://www.propublica.org/article/blinken-israel-military-aid-human-rights-violations-leahy-law
- Found: State's Israel Leahy Vetting Forum recommended disqualifying Israeli units for gross violations; Blinken delayed months, then deemed remediation adequate, keeping units eligible.
- Types: recommendation-decision-gap; selective-enforcement-carve-out
- Evidence: Leaked internal Blinken justification memo to Congress; vetting-forum meeting minutes; ex-State official and congressional-aide interviews; public determinations diffed against internal paper.
- Systems: Israel Leahy Vetting Forum meeting minutes
- Signature: recommendation-decision gap: obtain internal recommendation record and principal's final determination for same cases; diff outcome, delay, remediation against statutory standard; plus differential-process comparison for favored party.
- Method: [inferred]
- Impact: Congressional letters and floor scrutiny; no unit sanctioned

### Veterans' Care at Risk — DOGE Developed Error-Prone AI Tool to "Munch" Veterans Affairs Contracts (2025) — military-veterans
- URL: https://www.propublica.org/article/trump-doge-veterans-affairs-ai-contracts-health-care
- Partner/awards: GIJN "How They Did It" methods feature
- Found: DOGE engineer Sahil Lavingia's day-one AI tool flagged 2,000+ VA contracts "MUNCHABLE"; hallucinated ~1,100 values at $34M each, some actually $35,000.
- Types: automation-malpractice; decision-provenance-capture; hollowing-by-attrition (series companions)
- Evidence: Source-provided code, prompts, and flagged-contract list (later published on GitHub); six-expert panel review; federal procurement ground-truth records; Lavingia on-record interview; leaked internal VA emails.
- Systems: none named (model outputs ground-truthed against federal procurement records)
- Signature: algorithm forensics / decision-code diff: obtain deciding artifact, review prompts line-by-line, join model outputs to authoritative contract values; identical repeated values are the hallucination fingerprint.
- Method: https://gijn.org/stories/how-the-did-it-propublica-ai-tool-cut-veterans-affairs-contracts/ and prompts companion https://www.propublica.org/article/inside-ai-tool-doge-veterans-affairs-contracts-sahil-lavingia
- Impact: Senators Blumenthal and King demanded VA IG investigation of ~600 canceled contracts

- (partial, not fully extracted) The U.S. Built a Blueprint to Avoid Civilian War Casualties. Trump Officials Scrapped It. (2026): CHMR enterprise ~90% dismantled (~200 personnel) amid Iran/Yemen/Somalia strikes (Minab school: 165+ dead); evidence = dozen+ officials, ex-adviser briefing notes to Senate office, 2022 Pentagon CHMR action plan/DoD instruction as baseline, third-party monitors (Bellingcat, HRANA, New America, ACLED); signature = safeguard-demolition diff; canonical ProPublica URL not captured in report (mirror https://www.govexec.com/defense/2026/03/us-built-blueprint-avoid-civilian-war-casualties-trump-officials-scrapped-it/412166/; follow-up https://www.propublica.org/article/hegseth-trump-war-civilian-casualties-elizabeth-warren-pentagon).

- (not extracted) Other standalone items on https://www.propublica.org/topics/military: Littoral Combat Ship program failures (2023); Coast Guard icebreaker design problems (2025); Kabul evacuation reconstruction with Alive in Afghanistan (2022); Turkish drone export oversight gaps (2022); Russia's private military expansion (2022).

## Housing & homelessness (report-14)

- **RealPage / YieldStar (2022–2025) — housing (cross-ref)**: YieldStar pooled nonpublic competitor lease data to recommend rents — algorithmic price-fixing hub; DOJ antitrust suit, mega-landlord suits, Greystar and DOJ–RealPage settlements. URL: https://www.propublica.org/article/yieldstar-rent-increase-realpage-rent

- **HomeVestors "We Buy Ugly Houses" (2022–2025) — housing (cross-ref)**: Largest cash-homebuyer franchise trained franchisees to target distressed/elderly owners, cloud titles with recorded purchase contracts, buy far below market; CEO resigned, 2025 Carrier fraud prosecution. URL: https://www.propublica.org/article/ugly-truth-behind-we-buy-ugly-houses

### HUD's House of Cards (2018–2019) — housing
- URL: series https://www.propublica.org/series/huds-house-of-cards; flagship https://www.propublica.org/article/hud-inspections-pass-dangerous-apartments-with-rats-roaches-toxic-mold
- Partner/awards: ProPublica Local Reporting Network with The Southern Illinoisan (Molly Parker); later The Republican, The Capital, Lee Enterprises Midwest; HUD Inspect app by ProPublica news apps team
- Found: HUD REAC inspections passed hazardous properties (Clay Arsenal scored 74 amid rats/mold; ~820 violations still passed); failure rates tripled after 2016 tightening
- Types: oversight-theater; gamed-metric; politicized-enforcement-delay
- Evidence: REAC scores via FOIA/records requests; municipal code-inspection reports; HUD enforcement notices/decertifications; internal HUD documents (requests/leaks, inferred); tenant interviews/photos; HUD IG testimony and GAO audit; resident crowdsourced callout
- Systems: HUD REAC inspection score database; HUD Inspect app (projects.propublica.org/hud); Hartford municipal occupancy/code inspection reports; HUD enforcement paper trail (notices of default, inspector decertifications)
- Signature: score-vs-ground-truth diff: passing REAC scores joined to contemporaneous independent hazard evidence; plus policy-shock inflection read — failure-rate tripling after 2016 tightening proved prior inflation
- Method: [inferred] (REAC data documented at https://projects.propublica.org/hud)
- Impact: Carson re-examined inspections; GAO critical report; NSPIRE replaced REAC 2023 (inferred)

### The Rent Racket (2015–2017) — housing
- URL: series https://www.propublica.org/series/the-rent-racket; flagship https://www.propublica.org/article/nyc-landlords-flout-rent-limits-but-still-rake-in-lucrative-tax-breaks
- Partner/awards: ProPublica original (Cezary Podkul, Marcelo Rochabrun); one item with The Real Deal
- Found: ~50,000 apartments in ~5,500 buildings taking 421-a/J-51 tax breaks ($100M+) never registered for rent stabilization; Driggs: 9%/7% hikes vs 4%/1% caps
- Types: subsidy-compliance-gap; enforcement-vacuum; registered-vs-charged-divergence
- Evidence: NYC Finance tax rolls (public); DHCR/RGB stabilized-building lists (public; unit-level FOIL denied); tenant-supplied leases and DHCR rent histories; housing-court rent rolls; housing-analyst expert interviews
- Systems: NYC Department of Finance 421-a/J-51 tax rolls; DHCR rent registrations; Rent Guidelines Board stabilized-buildings master list; DHCR tenant rent-history printouts; NYC housing-court case files
- Signature: entitlement-roll JOIN obligation-register: tax-break recipient roll cross-checked against stabilization registration; anti-join priced as tax expenditure; unit-level lease-vs-registration diff proved mechanism
- Method: https://www.propublica.org/article/landlords-fail-to-list-fifty-thousand-nyc-apartments-for-rent-limits (stated inline; FOIL denial shaped design)
- Impact: $5M settlement; 3,000 landlords put on notice; Cuomo re-regulation pledge audited

### Checked Out (2023–2024) — housing
- URL: series https://www.propublica.org/series/checked-out; flagship https://www.propublica.org/article/how-la-failed-stop-landlords-turning-low-cost-housing-hotels
- Partner/awards: Capital & Main (Robin Urevich) + ProPublica (Gabriel Sandoval); photography Barbara Davidson
- Found: 21 protected residential hotels (800+ rooms) rented to tourists at up to $235/night unenforced; 2024: 63 rent-controlled buildings bookable, 100+ registered as hotels
- Types: protected-inventory-leakage; enforcement-vacuum; intra-government-contradiction
- Evidence: City residential-hotel designation list (public); booking/review sites manually combed; 10,000+ Housing Department pages via CPRA; Office of Finance hotel-tax registration list; site visits, photography, historical imagery
- Systems: LA residential-hotel designation list (2008 ordinance); LA Housing Department records; LA Office of Finance transient-occupancy-tax registrations; Booking.com/Hotels.com/Airbnb/Vrbo/Yelp listings; Google Maps historical imagery
- Signature: protected-list JOIN commercial-listing: protected-hotel roster matched to booking listings by name/address/imagery; 2024 cross-registry contradiction join — rent-stabilization rolls vs city's own hotel-tax registrations
- Method: https://www.propublica.org/article/we-found-los-angeles-landlords-renting-residential-hotels
- Impact: City investigation within two days; demand letters; mayor ordered homeless-housing use

### Swept Away (2024–2025) — housing
- URL: series https://www.propublica.org/series/swept-away; flagship https://projects.propublica.org/homeless-encampment-sweeps-taken-belongings
- Partner/awards: ProPublica original (Ruth Talbot, Asia Fields, Nicole Santa Cruz, Maya Miller)
- Found: 14–16 cities' logs show sweeps seize tents, wheelchairs, cremated remains; storage rare (San Diego: 3,000+ removals, 19 stored; Portland retrieval 4%; Anaheim 0%)
- Types: state-loss-of-property; policy-vs-practice-gap; administrative-burden-as-denial
- Evidence: Sweep/storage logs and property inventories from 14 cities via standardized records requests; retrieval statistics; 135 interviews plus 200+ written accounts via callout; sweep-lawsuit court records; DOJ Phoenix findings
- Systems: City sweep/storage logs and inventories (San Diego, Seattle, Portland, San Francisco, Anaheim, Phoenix); DOJ June 2024 Phoenix findings; sweep-litigation dockets (LA, Phoenix, SF, Denver, Albuquerque)
- Signature: multi-jurisdiction records survey + policy-vs-practice diff: identical records template across ~16 cities; stated storage policy diffed against each city's own sweeps:storage:retrieval counts; seized-item accumulation
- Method: https://projects.propublica.org/homeless-encampment-sweeps-taken-belongings (also https://www.propublica.org/article/reporting-on-homelessness-responsibly-guide-propublica)
- Impact: SF court-ordered training improvements; DOJ found Phoenix destroyed property without notice

### Homeowner Hell (2022–2023) — housing
- URL: series https://www.propublica.org/series/homeowner-hell; flagship https://www.propublica.org/article/they-faced-foreclosure-not-from-their-mortgage-lender-but-from-their-hoa
- Partner/awards: ProPublica Local Reporting Network with Rocky Mountain PBS (Brittany Freeman); data Sophie Chou
- Found: Colorado HOAs filed 2,400+ foreclosures (2018–2022), 215 sheriff's sales; 730+ during moratoriums; Paymah's $1,515.45 debt became $25,774; seven firms filed 100+ each
- Types: fee-engine-capture; moratorium-carve-out-exploitation; regulator-jurisdiction-hole
- Evidence: Statewide Colorado court foreclosure filings; sheriff's-sale records; Paymah v. Rock Ridge case files and trial transcript; HOA billing records; law firm's own fee-disclosing court filing; adversarial interviews
- Systems: Colorado statewide court foreclosure filing data; county sheriff's-sale records; Paymah v. Rock Ridge trial record
- Signature: plaintiff-name keyword harvest of dockets: HOA-signature keywords isolate HOA plaintiffs, manually verified; then moratorium-window filter, sheriff's-sale outcome chain-link, and fee-vs-principal ratios
- Method: https://www.propublica.org/article/they-faced-foreclosure-not-from-their-mortgage-lender-but-from-their-hoa (stated inline)
- Impact: Colorado HB22-1137 passed May 2022; fee caps dropped after industry negotiation

### When Private Equity Becomes Your Landlord (2022) — housing
- URL: https://www.propublica.org/article/when-private-equity-becomes-your-landlord
- Partner/awards: ProPublica original (Heather Vogell; series Rent Barons)
- Found: PE-backed firms held ~1M of top-35 owners' units by 2021 (half, up from a third); PE took 85% of Freddie Mac's 20 largest deals, ~$16B
- Types: concentration-shift-with-conduct-change; public-finance-subsidy-to-extraction; opacity-by-structure
- Evidence: NMHC top-owner rankings 2011–2021; PitchBook/Crunchbase/PERE/trade-press funding classification; Freddie Mac deal data and Commercial Mortgage Alert; SF building-department complaints, police call logs, Olume tenant leases/interviews
- Systems: NMHC top-owner rankings; PitchBook; Crunchbase; Private Equity Real Estate (PERE); Freddie Mac deal data; Commercial Mortgage Alert; SF building-department complaint records; SF police call logs
- Signature: ownership-roster enrichment over time: NMHC roster classified by capital source yearly; PE share trended; grounded by Olume before/after acquisition diff and GSE lender-concentration slice
- Method: https://www.propublica.org/article/when-private-equity-becomes-your-landlord (classification methods stated inline)

### How Your Shadow Credit Score Could Decide Whether You Get an Apartment (2022) — housing
- URL: https://www.propublica.org/article/how-your-shadow-credit-score-could-decide-whether-you-get-an-apartment
- Partner/awards: ProPublica original (Erin Smith, Heather Vogell; series Rent Barons)
- Found: ~2,000 screening companies ($1B/yr); RealPage claimed 30M lease outcomes; error-prone opaque scores (RentGrow, LeasingDesk) denied applicants; CFPB couldn't process complaints
- Types: shadow-scoring; error-propagation-harm; asymmetric-opacity
- Evidence: Applicant-supplied denial letters, scores, correspondence; 40+ renter survey responses via callout; CFPB/FTC complaint records; company marketing materials and written responses; NCLC/NHLP/fair-housing expert interviews
- Systems: CFPB complaint records; FTC complaint records; fair-housing complaint files
- Signature: regulatory-analog gap analysis: tenant scores mapped attribute-by-attribute onto regulated consumer credit scoring; missing subject rights enumerated; repeat-denial case tracing plus crowdsourced-harm registry
- Method: [inferred]

### Housing Loophole Lets Wealthy Investors Raise Rents on Poor Tenants (2025) — housing
- URL: https://www.propublica.org/article/affordable-housing-investors-loophole-rent-tenants
- Partner/awards: ProPublica original (Jesse Coburn)
- Found: LIHTC qualified-contract exit stripped restrictions from ~115,000 units ~16 years early; Sombra Apartments: bought under $20M, deregulated, sold $63M; rents up ~50%
- Types: statutory-self-destruct-clause; regulated-asset-leakage; shell-to-beneficiary-tracing
- Evidence: Qualified-contract applications via state public-records requests; county property transaction records; NCSHA unit-loss estimates; National Housing Trust policy tracking; formula drafter Rozen on record; LinkedIn/web entity resolution
- Systems: state housing-agency qualified-contract filings; county property transaction records; NCSHA unit-loss estimates; National Housing Trust state policy tracking
- Signature: exit-mechanism tracking: collect formal deregulation (qualified-contract) applications, join to subsequent sale prices/rents, aggregate national unit loss; formula autopsy shows buyout price designed to fail
- Method: [inferred]
- Impact: Most states now require waivers; congressional repeal failed 2023; loan channel open

### Contracts for Deed Put Somali Families at Risk (2022) — housing
- URL: https://sahanjournal.com/housing/contracts-for-deed-put-somali-families-financial-risk-minnesota/ (co-published); follow-ups https://www.propublica.org/article/minnesota-attorney-general-investigation-contract-for-deed-real-estate and https://www.propublica.org/article/minnesota-jury-predatory-home-financing-chadwick-banken-contract-for-deed
- Partner/awards: ProPublica (Jessica Lussenhop; data Haru Coryne) with Sahan Journal (Joey Peters); later with Andy Mannix
- Found: Sellers (Chad Banken, 100+ properties) resold homes same-day at markups as sharia-compliant "interest-free" contracts for deed with balloons; 1,800+ recorded in 11 counties (2021)
- Types: targeted-affinity-predation; designed-to-fail-financing; deed-chain-markup-laundering
- Evidence: County recorder deed records across 11 Minnesota counties compiled; the contracts themselves reviewed with buyers; Banken's 2000s federal foreclosure-rescue litigation; buyer/attorney/seller interviews; Urban Institute/Wilder homeownership-gap statistics
- Systems: Minnesota county recorder deed/property records (11 most-populous counties); federal court records (Banken foreclosure-rescue litigation)
- Signature: same-day deed-chain flip detection: recorder data flags parcels bought conventionally then resold same-day via contract-for-deed at markup; seller-portfolio accumulation across related LLCs; contract-term autopsy
- Method: [inferred]
- Impact: Minnesota AG investigation and suit; reform law passed; June 2026 jury verdict

### Living Apart (2012) — housing
- URL: https://www.propublica.org/article/living-apart-how-the-government-betrayed-a-landmark-civil-rights-law
- Partner/awards: ProPublica original (Nikole Hannah-Jones); Sidney Award; Columbia Tobenkin Award
- Found: HUD withheld CDBG funds over fair-housing violations only twice since 1974; GAO: third of 441 grantees' impediment analyses outdated, 25 nonexistent; Westchester falsely certified
- Types: enforcement-abdication-census; certification-without-verification; archival-intent-recovery
- Evidence: Romney papers and Nixon-era memos (archival); HUD enforcement records via FOIA — production failure itself probative; GAO 441-grantee review; grantee impediment analyses; Mondale/ex-HUD interviews; Westchester paired-tester audits
- Systems: Romney papers (Bentley Historical Library); Ehrlichman/Haldeman memos; HUD CDBG enforcement/withholding records; GAO 441-grantee file review; HUD internal 70-applicant study; grantee "analyses of impediments"; Westchester paired-tester data
- Signature: enforcement-action census: count enforcement events (2 withholdings, 40 years) against full grantee population; dead-letter paperwork audit; records-absence-as-evidence — the missing ledger itself probative
- Method: https://www.propublica.org/article/living-apart-how-the-government-betrayed-a-landmark-civil-rights-law (stated inline)
- Impact: Obama 2015 Affirmatively Furthering Fair Housing rule; Westchester consent-decree enforcement continued

### The Eviction Ban Worked (2020) — housing
- URL: https://www.propublica.org/article/the-eviction-ban-worked-but-its-almost-over-some-landlords-are-getting-ready; app https://projects.propublica.org/covid-evictions/
- Partner/awards: ProPublica original (Haru Coryne, Ellis Simani; Princeton Eviction Lab data partnership)
- Found: Federally backed properties' eviction filings fell from ~7,700/month (Atlanta+Houston) to under 200 during CARES ban; landlords in four states violated with 100+ filings
- Types: moratorium-defiance; protection-coverage-inequality; rights-operationalization-tool
- Evidence: Local eviction dockets from court websites (GA, TN, FL, TX) and Princeton Eviction Lab (~10 cities); Fannie/Freddie loan lookups; HUD/FHA-subsidized property lists; parcel map files; random-sample manual validation
- Systems: court-website eviction dockets; Princeton Eviction Lab data; Fannie Mae/Freddie Mac loan lookups; HUD/FHA-subsidized property lists; digital parcel/map files; covid-evictions lookup app
- Signature: geocode JOIN coverage-list inside a prohibition window: cases geocoded to parcels, matched to CARES-covered property lists; ban-window filings at covered parcels = violations; covered-vs-uncovered differential measures effect
- Method: https://projects.propublica.org/covid-evictions/ (matching stated inline in article)
- Impact: Fed 2020–21 policy debate; CDC ban followed weeks later (causation not claimed)

### Colony Ridge settlement accountability (2026) — housing
- URL: https://www.propublica.org/article/trump-doj-colony-ridge-texas-settlement-victims; follow-up https://www.propublica.org/article/colony-ridge-settlement-court-hearing-doj
- Partner/awards: ProPublica + Texas Tribune co-publication (Zach Despart); foundational exposés by Houston Landing
- Found: Proposed $68M DOJ Colony Ridge settlement pays victims $0 ($20M police/immigration, $48M infrastructure) — largest of 183 comparable settlements since 2018 without victim compensation
- Types: settlement-outlier; remedy-diversion
- Evidence: Proposed consent decree and settlement court filings; underlying DOJ/CFPB complaint; compiled corpus of 183 prior DOJ housing/lending settlements; victim interviews (Acevedo, Sanchez); former CFPB enforcement official; hearing coverage
- Systems: court settlement/consent-decree filings; DOJ/CFPB complaint; compiled 183-settlement DOJ housing/lending corpus (public DOJ records)
- Signature: settlement-corpus benchmark: proposed terms (total, victim-compensation line, recipients) compared against population of comparable past settlements; zero-restitution outlier status converts opinion into measured anomaly
- Method: https://www.propublica.org/article/trump-doj-colony-ridge-texas-settlement-victims (stated inline; compilation details unpublished)
- Impact: Hearing Apr 11, 2026; DOJ proceeded despite judicial concern; ongoing

# Index: ProPublica intake reports 15 (democracy-elections) + 16 (tribal)

## Democracy, elections & political ethics (report-15)

- (cross-ref) Trump, Inc. (w/ WNYC) — inaugural-committee overpayment vs. market comparables + "two books" lender-vs-tax valuation contradiction; duPont-Columbia Award. URL: https://www.propublica.org/series/trump-inc
- (cross-ref) Dark money / campaign finance (FEC/990/Free the Files) — FEC filings joined to IRS 990s exposing 501(c)(4) election spending; 2012 Free the Files crowdsourced TV ad-file review. No URL in entry.
- (cross-ref) "Dark Money in Montana" / WTP (2012, w/ PBS Frontline) — Western Tradition Partnership document cache from a Colorado meth house proved candidate coordination; signature: orphaned-document-cache exploitation. No URL in entry.

### What Parler Saw During the Attack on the Capitol (2021) — democracy-elections
- URL: https://projects.propublica.org/parler-capitol-videos/
- Partner/awards: ProPublica original; no award verified; footage class became court-exhibit material
- Found: ~1M archived Parler videos filtered by GPS/timestamp metadata to 2,500 candidates; 500+ verified, time-synced clips of rioters self-documenting the Capitol breach.
- Types: evidentiary-archive-construction; self-documented-participation
- Evidence: Scraped Parler archive from anonymous civic programmer; embedded capture timestamps and location metadata; staff frame-by-frame review of every Jan. 6 candidate; general-counsel fair-use analysis.
- Systems: Parler archive (1M-video scrape)
- Signature: geofence-timewindow-metadata-join: capture timestamp x location joined to Capitol polygon and Jan. 6 window cut 1M clips to 2,500; human review converted dump into evidentiary archive.
- Method: https://www.propublica.org/article/why-we-published-parler-users-videos-capitol-attack

### Capitol Rioters Planned for Weeks in Plain Sight. The Police Weren't Ready. (2021) — democracy-elections
- URL: https://www.propublica.org/article/capitol-rioters-planned-for-weeks-in-plain-sight-the-police-werent-ready
- Partner/awards: co-published with FRONTLINE
- Found: Stop the Steal leaders publicly pre-announced the Jan. 6 occupation weeks ahead (Dec. 23 post, Ali Alexander, MyMilitia threats); Capitol Police posture ignored the dated signal.
- Types: foreseeable-threat-ignored; open-forum-mobilization-record
- Evidence: Public social posts (scores reviewed, manually collected [inferred]); interviews with 34-year Capitol Police veteran Larry Schaefer, D.C. AG Karl Racine, academic intelligence expert.
- Systems: Parler; MyMilitia.com; Twitter
- Signature: pre-event-signal-vs-institutional-posture-diff: dated public threat/planning posts compiled post-event and diffed against the agency's staffing and intelligence actions; the delta is the finding.
- Method: [inferred]

### Building the "Big Lie": Inside the Creation of Trump's Stolen Election Myth (2022) — democracy-elections
- URL: https://www.propublica.org/article/big-lie-trump-stolen-election-inside-creation
- Partner/awards: co-published with FRONTLINE; companion documentary "Plot to Overturn the Election"
- Found: Marquee fraud claims traced to named originators (Oltmann, Maras, Solomon, Ramsland, Burk); campaign staff found claims baseless within a day, promotion continued anyway.
- Types: disinformation-genealogy; knew-it-was-false-record
- Evidence: Insider-provided internal emails/documentation trove; private group chats ("Purple Unicorns"); defamation-suit depositions and filings; recorded phone calls; eight firsthand interviews; on-record recantation (Burk).
- Systems: none named
- Signature: claim-genealogy-reconstruction-with-internal-vetting-diff: each public claim traced back to first assertable source; internal debunk date compared to continued-promotion dates, establishing scienter.
- Method: [inferred]

### Facebook Hosted Surge of Misinformation and Insurrection Threats in Months Leading Up to Jan. 6 (2022) — democracy-elections
- URL: https://www.propublica.org/article/facebook-hosted-surge-of-misinformation-and-insurrection-threats-in-months-leading-up-to-jan-6-attack-records-show
- Partner/awards: co-published with The Washington Post
- Found: At least 650,000 posts attacking Biden's election legitimacy in Facebook groups Election Day-Jan. 6 (~10,000/day, a floor); 27,000 political groups, ~2,500 removed late.
- Types: platform-amplification-quantification; enforcement-gap-measurement
- Evidence: CounterAction commercial monitoring dataset (100,000+ public groups, Jan 2020-June 2021); ML political-group classifier (79% precision); 60+86-term lexicon over 18.7M posts, hand-checked at 64% precision.
- Systems: CounterAction Facebook-groups shadow-archive
- Signature: lexicon-census-over-third-party-shadow-archive: ML defines the political-group population, validated delegitimization lexicon counts behavior in the mirror corpus; precision published, result framed as floor.
- Method: [inferred]

### Redistricting dark-money arc: The Hidden Hands in Redistricting + How Dark Money Helped Republicans Hold the House and Hurt Voters (2011-2012) — democracy-elections
- URL: https://www.propublica.org/article/hidden-hands-in-redistricting-corporations-special-interests ; https://www.propublica.org/article/how-dark-money-helped-republicans-hold-the-house-and-hurt-voters
- Partner/awards: ProPublica originals
- Found: "Citizen" map groups were corporate/Koch fronts; REDMAP's $30M captured 2011 maps — Democrats won ~1M more House votes yet GOP held chamber; SGLF paid Hofeller $166,000.
- Types: front-group-unmasking; money-in-maps; votes-seats-asymmetry
- Evidence: IRS 990s and state registrations; lobbying disclosures; campaign finance records; shared-address/officer analysis; NC litigation discovery (depositions, internal emails); election-results and district-map analysis; interviews.
- Systems: IRS 990s; state nonprofit/business registrations; federal/state lobbying disclosures; NC redistricting litigation discovery record
- Signature: shared-infrastructure-resolution; outcome-vs-mandate-asymmetry: front groups joined to interest groups on agents/addresses/officers; vote-share vs. seat-share divergence traced to 990-paid mapmakers.
- Method: [inferred]

### How Democrats Fooled California's Redistricting Commission (2011) — democracy-elections
- URL: https://www.propublica.org/article/how-democrats-fooled-californias-redistricting-commission
- Partner/awards: ProPublica original
- Found: House Democrats ran covert astroturf operation — fake groups (OneSanJoaquin; Asian American Education Institute, domain registered to consultant Bill Wong); Democrats gained six-seven seats vs. 1-2 projected.
- Types: astroturf-testimony-attribution; process-capture-of-a-neutral-institution; stated-goal-vs-achieved-map-concordance
- Evidence: 100+ leaked internal Democratic emails/memos; the commission's 30,000-piece testimony corpus and meeting transcripts; WHOIS lookups; final maps vs. internal seat projections; participant interviews.
- Systems: CA Citizens Redistricting Commission testimony corpus (30,000 items) and meeting transcripts; WHOIS
- Signature: testimony-to-memo-join-with-persona-verification: public testimony matched to internal strategy memos on asks/phrasing/personnel; witnesses background-verified (residence, WHOIS); outcome concordance with memo targets confirmed.
- Method: [inferred]
- Impact: Commission issued formal response; California Republicans called for official investigation.

### The Real Bosses of New Jersey (2019) — democracy-elections
- URL: https://www.propublica.org/article/george-norcross-democratic-donor-tax-breaks ; https://www.propublica.org/article/emails-show-how-much-pull-political-bosses-had-over-state-tax-breaks-new-jersey-norcross
- Partner/awards: WNYC/ProPublica Local Reporting Network; co-published with The Star-Ledger; no award verified
- Found: $1.1B of $1.6B Camden tax breaks traced to George Norcross's network (Holtec $260M, American Water $164.2M); brother's firm Parker McCay drafted the law.
- Types: capture-of-discretionary-benefit; legislation-authorship-conflict; cost-per-outcome-outlier
- Evidence: NJ EDA applications, award ledgers, employment certifications; lobbying client lists; corporate/board records; 12,000-page OPRA email production; property records; litigation documents; Rutgers cost-per-job study; interviews.
- Systems: NJ EDA award ledger; 12,000-page NJ OPRA email cache; lobbying client rolls
- Signature: beneficiary-network-overlay-on-award-ledger: full award list joined to one person's relationship graph (ownership, boards, kin, clients-of-kin's-firms), summed to $1.1B/$1.6B; drafting emails resolved rule authorship.
- Method: [inferred]
- Impact: Murphy audit/task force; AG inquiry; $578M breaks held; program lapsed; 2024 racketeering indictment.

### A False Answer, a Big Political Connection and $260 Million (Holtec) + the Camden land assembly map (2019) — democracy-elections
- URL: https://www.propublica.org/article/holtec-international-tax-break-application-false-answer-new-jersey-on-hold ; https://projects.propublica.org/graphics/camden
- Partner/awards: WNYC/ProPublica
- Found: Holtec CEO swore "never barred" on EDA application despite 2010 TVA suspension and $2M fine, under $260M award; Norcross network bought waterfront parcels post-2013 law.
- Types: false-sworn-certification; insider-timed-asset-assembly; displacement-by-machine
- Evidence: Sworn EDA certification; federal TVA suspension/fine records; county deed and property-tax records per parcel; EDA award data; ownership-connection records; grand-jury subpoenas (follow-on); interviews.
- Systems: NJ EDA application/award data; TVA suspension/debarment records; county deed and property-tax records
- Signature: sworn-answer-vs-external-registry-diff; legislation-to-deed-timeline-join: certification diffed against TVA's record; parcel transfer dates joined to the law's drafting window and buyers' network, mapped parcel-by-parcel.
- Method: [inferred]
- Impact: $260M break frozen; task-force criminal referrals; conduct fed 2024 racketeering indictment.

### Big Jim (2019-2023) — democracy-elections
- URL: https://www.propublica.org/article/the-billionaire-governor-whos-been-sued-dozens-of-times-for-millions-in-unpaid-bills
- Partner/awards: w/ Charleston Gazette-Mail, then Mountain State Spotlight (Local Reporting Network); conflict disclosure published; no award verified
- Found: Gov. Jim Justice's family companies drew 600+ lawsuits across 25+ states, $128M-$140M judgments/settlements; seven of his own ex-law-firms among plaintiffs; up to $24M PPP.
- Types: serial-nonpayment-profile; self-regulation-conflict; pledge-vs-practice-diff
- Evidence: State/federal court dockets across 25+ states, hand-compiled [inferred PACER + state sweeps]; environmental/mine-safety regulatory records; SBA PPP disclosures; plaintiff, union, official interviews; governor's public pledges.
- Systems: SBA PPP loan disclosures; PACER + state dockets [inferred]
- Signature: cross-jurisdiction-docket-accumulation-on-resolved-entity-family: all suits naming any Justice-family company aggregated across decades and jurisdictions into counts, dollar totals, repeat-plaintiff patterns; regulator-regulated identity join.
- Method: [inferred]
- Impact: WV lawmakers called for ethics reform; federal enforcement actions continued.

### Louisiana's Ethical Swamp (2018-2019) — democracy-elections
- URL: https://www.propublica.org/article/louisiana-lawmakers-pushing-bills-that-benefit-their-own-businesses
- Partner/awards: ProPublica Local Reporting Network with The Times-Picayune | The Advocate
- Found: Legislators sponsored bills enriching their own businesses (Harris fuel bills, Mills nursing homes); 1,200 bills/year vs. average four recusals/year since 2004; third of ex-lawmakers lobby.
- Types: self-dealing-legislation; disclosure-regime-gap; revolving-door-census; enforcement-latency-finding
- Evidence: Legislative bill/vote/recusal records (stated quantitative review); personal financial disclosures; corporate ownership registries; committee testimony; lobbying registrations; ethics-board case records; interviews.
- Systems: Louisiana legislative bill/vote/recusal records; state personal financial disclosure filings; lobbying registrations; ethics-board case records
- Signature: sponsor-beneficiary-join-with-recusal-rate-baseline: member business interests joined to sponsored bills' beneficiary classes; systemic claim quantified by the near-zero recusal denominator.
- Method: [inferred]
- Impact: No legislative fix verified; kept stalled Marionneaux ethics case in public view.

### Electionland (2016-ongoing) — democracy-elections
- URL: https://www.propublica.org/electionland/ ; https://www.propublica.org/article/robocalls-told-at-least-800-000-swing-state-residents-to-stay-home-on-election-day-the-fbi-is-investigating
- Partner/awards: coalition incl. Google News Lab, Univision, USA Today Network, CUNY, WNYC, First Draft, 12 colleges; 1,100+ journalists; 2017 Online Journalism Award
- Found: 1,100-journalist real-time verification net contacted 120,000+ voters; found no widespread fraud; TelTech data showed 3M+ Election Day "stay home" robocalls, 800,000+ reaching swing states.
- Types: real-time-distributed-verification-infrastructure; negative-space-finding; coordinated-suppression-signal-quantification
- Evidence: Crowdsourced SMS/phone/WhatsApp/web tips; Election Protection hotline feed; trained-student social monitoring (First Draft protocols); Google search-trend telemetry; TelTech/RoboKiller call data and recordings; election-administration records.
- Systems: Landslide (internal triage system); 1-866-OUR-VOTE Election Protection line; Google News Lab search trends; TelTech/RoboKiller telemetry
- Signature: many-sensor-triangulation-with-human-verification-gate: independent feeds clustered by place/time in Landslide; story only when feeds corroborate and local partner confirms; third-party telemetry census for robocalls.
- Method: https://www.propublica.org/article/monitoring-the-vote-with-electionland
- Impact: FBI and NY AG action on robocalls; same-day fixes while polls open.

### Why Do Nonwhite Georgia Voters Have to Wait in Line for Hours? (2020) — democracy-elections
- URL: https://www.propublica.org/article/why-do-nonwhite-georgia-voters-have-to-wait-in-line-for-hours-their-numbers-have-soared-and-their-polling-places-have-dwindled
- Partner/awards: w/ Georgia Public Broadcasting
- Found: Post-Shelby Georgia cut 331 polling places (-13%) as rolls grew ~2M; 51-minute average waits in 90%+ nonwhite precincts vs. 6 minutes in white areas.
- Types: disparate-service-allocation; post-oversight-drift
- Evidence: State/county polling-place lists 2012 vs. 2020; voter registration files (growth, race, geography); June 2020 primary poll-closing-time records; precinct racial composition; Stanford academic partner (Rodden) wait-time analysis.
- Systems: Georgia polling-place lists; Georgia voter registration files; June 2020 poll-closing-time records
- Signature: capacity-demand-divergence-segmented-by-protected-class: polling-place time series diffed against registration growth by race/geography, anchored to Shelby 2013; burden measured from late-closing administrative side-channel.
- Method: [inferred]

### Close to 100,000 Voter Registrations Were Challenged in Georgia — Almost All by Just Six Right-Wing Activists (2023) — democracy-elections
- URL: https://www.propublica.org/article/right-wing-activists-georgia-voter-challenges
- Found: ~89,000 of 100,000 challenges filed by six activists; ~11,100 succeeded (2,350+ removed); Schneider filed 31,500+ via NCOA matching; officials knew of no fraud prosecutions.
- Types: concentrated-mass-challenge; heuristic-error-harm-audit; legislative-capture-follow-through
- Evidence: County challenge logs from 30 of 159 counties incl. 20 most populous (records requests [inferred]); challenge spreadsheets revealing NCOA method; county board outcomes; voter/activist/official interviews; internal GOP email.
- Systems: county voter-challenge logs (30 Georgia counties); National Change of Address (NCOA) data as challengers' match key
- Signature: submitter-concentration-analysis-over-aggregated-local-records: centralized county logs grouped by submitter (six people ~89% of volume); challengers' match heuristics reverse-engineered and tested for false-positive harm.
- Method: [inferred]
- Impact: Georgia Secretary of State committed to uniform challenge standards; board weighed guidance.

### Some Election Officials Refused to Certify Results. Few Were Held Accountable. (2023) — democracy-elections
- URL: https://www.propublica.org/article/election-officials-refused-certify-results-few-held-accountable
- Found: 10 refusals to certify 2022 results across NC/AZ/NV/NM; majority drew no official consequences; Surry County NC produced the first completed disciplinary process nationwide.
- Types: institutional-noncompliance-without-sanction; procedural-sabotage-early-warning
- Evidence: County board meeting minutes and recordings; certification records; mandamus court filings; state election-authority correspondence and complaints; interviews with authorities, legal experts, refusing officials.
- Systems: none named
- Signature: violation-census-x-sanction-record-join: every certification refusal enumerated from minutes/certification records, joined to disciplinary/criminal follow-through per official; the near-empty sanction column is the finding.
- Method: [inferred]

## Tribal affairs & Indigenous rights (report-16)

### America's Biggest Museums Fail to Return Native American Human Remains + the NAGPRA compliance database (2023) — tribal
- URL: https://www.propublica.org/article/repatriation-nagpra-museums-human-remains ; https://projects.propublica.org/repatriation-nagpra-database
- Partner/awards: co-published with NBC News; Mary Hudetz won 2024 Richard LaCourse Award for the series
- Found: 110,000+ Native ancestors' remains unreturned 33 years after NAGPRA; 10 institutions held about half; total fines collected since 1990: $59,111.34.
- Types: statutory-compliance-ledger; classification-as-evasion; enforcement-vacuum
- Evidence: NPS National NAGPRA inventory data (obtained from NPS); Federal Register inventory-completion notices; Interior civil-penalty records; 30 years of review-committee transcripts; institutional correspondence; tribal filings; 100+ interviews.
- Systems: National NAGPRA Program inventory database; Federal Register Notices of Inventory Completion; Interior civil-penalty records
- Signature: mandate-inventory-compliance-join: NPS inventories joined to Federal Register completion notices per institution; reported minus made-available = backlog and percent-complete; pipeline-stage precision ("made available," not transferred).
- Method: https://www.propublica.org/article/behind-propublica-reporting-on-repatriation ; https://www.propublica.org/article/how-to-report-on-repatriation-of-native-american-remains
- Impact: Senate probe; Illinois repatriation law; Dec 2023 Interior rules killed "culturally unidentifiable" loophole.

### Tribes in Maine Spent Decades Fighting to Rebury Ancestral Remains. Harvard Resisted Them at Nearly Every Turn. (2023) — tribal
- URL: https://www.propublica.org/article/inside-wabanaki-tribes-struggle-to-reclaim-ancestral-remains-from-harvard
- Partner/awards: ProPublica (Hudetz, Ngu); part of LaCourse-award-winning series
- Found: Harvard's Peabody resisted Wabanaki claims ~30 years; 2013 secret Reich Lab DNA extraction on contested remains, then cited against repatriation; returned only in 2021.
- Types: documentary-obstruction-reconstruction; secret-science-on-contested-property
- Evidence: Internal emails obtained by ProPublica (route not stated); 1995 Peabody memo-to-file; confidential Reich Lab DNA report; March 2015 federal hearing transcript; Wheeler-Newsom peer-reviewed paper; NAGPRA counts; interviews.
- Systems: National NAGPRA database (Harvard holdings counts)
- Signature: assurance-vs-conduct-timeline-diff: internal documents, public statements, filings ordered on one time axis; each contradiction between private conduct (secret DNA work) and assurances or denial rationales is the finding.
- Method: [inferred]
- Impact: Remains repatriated and reburied; fed Senate scrutiny and Dec 2023 rule overhaul.

### A Scientist Said Her Research Could Help With Repatriation. Instead, It Destroyed Native Remains. (2023) — tribal
- URL: https://www.propublica.org/article/delayed-repatriation-allows-destructive-research-native-american-remains
- Partner/awards: ProPublica (this piece solo)
- Found: Brenner Coltrain's $222,218 NSF grants (2002-2010) ground bone from 80+ Ancestral Pueblo ancestors without tribal consent, justified as aiding repatriation; zero repatriations resulted.
- Types: mission-inverted-research; grant-outcome-mismatch
- Evidence: NSF award database entries and grant reports; resulting publications (2010; 2017 Nature) naming sampled remains; NPS NAGPRA inventories; previously unreported researcher emails; interviews with scientists, tribes, museums.
- Systems: NSF award database; NPS NAGPRA inventories
- Signature: grant-promise-vs-outcome-diff-with-specimen-tracing: grant purposes joined to publications' sampled specimens and NAGPRA status per specimen/site; funded "to help repatriation," zero repatriations, remains destroyed.
- Method: [inferred]
- Impact: AMNH banned destructive research; Interior halt-on-request move; NSF drafted tribal-consultation requirements.

### A Prominent Museum Obtained Items From a Massacre of Native Americans. The Survivors' Descendants Want Them Back. (2023) — tribal
- URL: https://www.propublica.org/article/wounded-knee-american-museum-natural-history
- Partner/awards: ProPublica
- Found: AMNH holds Wounded Knee massacre items (toy saddle, doll shirt) via soldier Holzner and surgeon Mearns's 1895-documented donation; zero AMNH repatriations to Oglala Lakota.
- Types: atrocity-provenance
- Evidence: AMNH handwritten accession registers and 1895 annual report; Army captain's Jan 3, 1891 letter on removals; Eli Ricker oral-history archive (Joseph Horn Cloud); descendant, tribe, museum interviews.
- Systems: AMNH accession registers; AMNH 1895 annual report; Ricker oral-history archive
- Signature: accession-to-atrocity-provenance-join: catalog donor/date/origin metadata joined to independent military and archival event records on person + date + place; catalog entries become massacre evidence.
- Method: [inferred]
- Impact: Contributed to AMNH's Jan 2024 closure of Native American exhibit halls.

### The U.S. Has Spent More Than $2 Billion on a Plan to Save Salmon. The Fish Are Vanishing Anyway. (2022) — tribal
- URL: https://www.propublica.org/article/salmon-hatcheries-government-climate-change
- Partner/awards: Oregon Public Broadcasting via Local Reporting Network; companion documentary "Salmon People" won national Edward R. Murrow Award
- Found: ~$2.2B spent on hatcheries; federal cost $250-$650 per returning salmon; 2014-2018 none of eight monitored populations met the 4% adult-return benchmark.
- Types: outcome-per-dollar-failure; treaty-substitute-audit
- Evidence: PIT-tag detection records obtained from Columbia Basin Research (UW academic data center); NOAA hatchery budgets and infrastructure assessments; NPCC 4% benchmark; 2021 NOAA projection study; 1947 Interior memo; treaty texts.
- Systems: Columbia Basin Research PIT-tag database (University of Washington)
- Signature: cohort-survival-computation-against-government-benchmark: tagged juveniles matched to adult return detections per population across two ocean eras, benchmarked to the agencies' own 4% target; spend/returns = cost-per-fish.
- Method: https://www.propublica.org/article/salmon-hatcheries-pnw-fish-data
- Impact: $200M federal reintroduction commitment; tribes given control of salmon-recovery funds.

### The U.S. Promised Tribes They Would Always Have Fish, but the Fish They Have Pose Toxic Risks (2022) — tribal
- URL: https://www.propublica.org/article/how-the-us-broke-promise-to-protect-fish-for-tribes
- Partner/awards: Oregon Public Broadcasting
- Found: Newsroom-commissioned lab tests found mercury/PCB levels deemed unsafe in salmon above Bonneville Dam; tribal members eat 6-11x more fish; EPA flagged contamination since 1990s.
- Types: journalist-commissioned-measurement; agency-knew-timeline; exposure-inequity-quantification
- Evidence: 50 salmon purchased from tribal fishers (Sept 2021), certified ALS lab testing (13 metals + 2 chemical classes); FOIA'd 1990s-onward EPA memos/studies; EPA/state thresholds; federal consumption surveys; interviews.
- Systems: EPA internal fish-contaminant studies (FOIA); EPA/Oregon/Washington published safety thresholds; federal tribal fish-consumption surveys
- Signature: fill-the-regulators-gap-sampling-plus-threshold-join: newsroom generates the missing measurement with chain of custody, joins results to agencies' own thresholds and their own consumption data — no methodological exit.
- Method: [inferred]
- Impact: WA/OR health departments weighed official advisory; lawmaker demanded changes.

### How a Federal Agency Is Contributing to Salmon's Decline in the Northwest (2022) — tribal
- URL: https://www.propublica.org/article/salmon-protection-dam-bonneville-power-administration
- Partner/awards: Oregon Public Broadcasting, ProPublica Local Reporting Network
- Found: BPA banked a $360M revenue windfall while cutting fish-and-wildlife budget $78M inflation-adjusted; dams making ~half its power have zero fish passage 50+ years.
- Types: budget-priority-inversion; power-vs-protection-asymmetry
- Evidence: BPA 2018 strategic plan and budget series; net-revenue vs. target figures; Fish Passage Center spill analyses; NOAA + 60-scientist letters; 2018 funding accord terms; run counts, dam timeline.
- Systems: BPA strategic-plan/budget documents; Fish Passage Center analyses
- Signature: surplus-vs-mandate-ledger-diff: revenue windfall vs. inflation-adjusted mitigation spending from the agency's own documents; dams cross-tabbed by power-revenue share x fish-passage status — protection tracks revenue.
- Method: [inferred]
- Impact: Part of record behind 2023 Columbia Basin agreement (abandoned by Trump administration 2025).

### How Arizona Stands Between Tribes and Their Water (2023) — tribal
- URL: https://www.propublica.org/article/how-arizona-stands-between-tribes-and-their-water
- Partner/awards: co-published with High Country News
- Found: Arizona tribes wait ~34 years for water settlements vs. ~18 elsewhere; all four post-2003 Arizona settlements extracted land-into-trust waivers; 10 of 22 tribes unsettled.
- Types: adjudication-attrition; settlement-condition-extraction
- Evidence: Every Colorado River Basin water settlement reviewed; Leslie Sanchez (USFS) settlement-timing dataset analyzed; court filings (Winters; Arizona v. Navajo); state DWR communications via records requests; tribal letters; BIA records; interviews with 20 of 30 basin tribes.
- Systems: Sanchez/USFS settlement-timing dataset; Colorado River Basin settlement corpus; BIA land-into-trust decision records
- Signature: settlement-census-term-extraction-plus-wait-time-metric: full settlement population coded for elapsed time and attached non-water conditions; one state's 4/4 waiver pattern plus outlier waits isolates actor and mechanism.
- Method: [inferred]

### The Colorado River Flooded Chemehuevi Land. Decades Later, the Tribe Still Struggles to Take Its Share of Water. (2023) — tribal
- URL: https://www.propublica.org/article/chemehuevi-tribe-reservation-water-colorado-river-california
- Partner/awards: co-published with High Country News
- Found: Chemehuevi use ~3% of their decreed 11,340 acre-feet; 97% flows free to Southern California cities; basin-wide 1M+ acre-feet of tribal water goes unused yearly.
- Types: paper-rights-gap; uncompensated-reallocation
- Evidence: 1960s judicial decrees (Arizona v. California line); Bureau of Reclamation use records; Central Arizona Project records; 1973 National Water Commission report; USC development plan; Ten Tribes Partnership quantifications; interviews.
- Systems: Bureau of Reclamation water-use accounting; Central Arizona Project records; Arizona v. California decrees
- Signature: entitlement-vs-delivery-diff-with-beneficiary-tracing: decreed acre-feet joined to Reclamation's actual diversion accounting per rights-holder; residual traced hydrologically/contractually to its zero-price consumers; infrastructure-funding asymmetry supplies mechanism.
- Method: [inferred]

### To Reclaim Ancestral Land, All Native Hawaiians Need Is a $300,000 Mortgage and to Wait in Line for Decades (2020) — tribal
- URL: https://www.propublica.org/article/hawaii-native-land-homesteads-department-of-hawaiian-home-lands
- Partner/awards: Honolulu Star-Advertiser, ProPublica Local Reporting Network
- Found: DHHL waitlist ~23,000 (~182 years at award rates); 2,000+ applicants died waiting 1995-2020; 60% of Oahu awards went to census tracts above $75,000 income.
- Types: means-tested-program-capture; waitlist-mortality; de-facto-eligibility-test
- Evidence: DHHL applicant/lessee/transaction database 1995-2020, two logs ([inferred] records request); Google Maps geocoding to census tracts; death markers ("DEC'D") in waitlist text; HUD studies; court rulings; interviews.
- Systems: DHHL applicant/lease logs; Google Maps geocoding API; census tract income data
- Signature: queue-to-award-join-with-income-overlay-and-mortality-scan: logs linked on lessee name + lease start date; awardee addresses geocoded to tract income vs. waitlist; waitlist text scanned for death markers.
- Method: https://www.propublica.org/article/how-we-found-low-income-hawaiians-were-left-behind-by-the-homesteading-program
- Impact: Hawaii lawmakers passed $600 million (2022) to fix program, explicitly following investigation.

### The U.S. Owes Hawaiians Millions of Dollars Worth of Land. Congress Helped Make Sure the Debt Wasn't Paid. (2021) — tribal
- URL: https://www.propublica.org/article/the-us-owes-hawaiians-millions-of-dollars-worth-of-land-congress-helped-make-sure-the-debt-wasnt-paid
- Partner/awards: Honolulu Star-Advertiser, ProPublica Local Reporting Network
- Found: ~70 acres of 1995-settlement land still owed the trust ($39-55M today); Congress passed six+ laws selling federal land to churches/developers/Hunt Cos. instead.
- Types: land-debt-ledger-reconstruction; obligation-bypass-legislation
- Evidence: 1995 settlement act and six+ sale-authorization statutes; federal/state/county parcel conveyance records with prices and grantees; current-dollar appraisals; DHHL trust accounting; official and beneficiary interviews.
- Systems: federal/state/county land and parcel records; DHHL trust accounting
- Signature: statutory-debt-vs-conveyance-reconciliation-with-grantee-tracing: acres owed minus acres conveyed = arrears at current appraisal; every parallel federal disposal enumerated with grantees; diversions pinned to named acts of Congress.
- Method: [inferred]
- Impact: Fed the 2022 $600M legislative response and state scrutiny of DHHL land management.

### The Bureau of Indian Education Hasn't Told the Public How Its Schools Are Performing. So We Did It Instead. (2021) — tribal
- URL: https://www.propublica.org/article/the-bureau-of-indian-information-hasnt-told-the-public-how-its-schools-are-performing
- Partner/awards: The Arizona Republic, ProPublica Local Reporting Network
- Found: BIE published no mandated scores since 2015-16; reporters computed it — students 2+ grade levels behind nationally but only 0.3 behind local Native peers, with faster growth.
- Types: suppressed-report-reconstruction; growth-vs-proficiency-decomposition
- Evidence: ~193,000 raw score submissions in U.S. Education Department EDFacts database; Stanford Educational Opportunity Project NAEP crosswalk; hand-built school-to-assessment mapping via calls to states/schools/tribes; surrounding-district Native comparison population.
- Systems: EDFacts; Stanford Educational Opportunity Project NAEP crosswalk
- Signature: shadow-report-card-via-raw-feed-standardization: suppressed mandated report rebuilt from the EDFacts upstream feed through hand-built assessment map and NAEP crosswalk; level vs. growth decomposed against national and local-Native comparisons.
- Method: https://www.propublica.org/article/how-we-analyzed-the-performance-of-bureau-of-indian-education-schools
- Impact: First public BIE performance accounting in five years.

### Washington State Is Leaving Tribal Cultural Resources at the Mercy of Solar Developers (2024) — tribal
- URL: https://www.propublica.org/article/washington-state-is-leaving-tribal-cultural-resources-at-mercy-of-solar-developers
- Partner/awards: co-published with High Country News
- Found: State archaeologist Sara Palmer found 17 sites in ~20 hours that Tetra Tech's 800-page developer-paid survey omitted; DNR called her "rogue" and sidelined her.
- Types: proponent-paid-assessment-undercount; regulatory-capture-by-communication; green-transition-externality
- Evidence: Public-records-act texts/emails/notes (Avangrid vetting demands, relocation threats, "rogue" DNR notes); dueling surveys (Tetra Tech's 800 pages vs. Palmer's 17-site fieldwork); EFSEC proceedings; tribal objections; treaty framework; interviews.
- Systems: EFSEC siting-council proceedings; WA public-records-act productions (DNR texts/emails/notes)
- Signature: independent-recount-diff-on-paid-assessment: independent state expert's same-ground count minus proponent survey's disclosures = 17-site undercount; records requests reconstruct why it survived (agency disciplined its expert, not developer).
- Method: [inferred]
- Impact: EFSEC commissioned first independent cultural survey in decade; project paused; Yakama barred Tetra Tech.

