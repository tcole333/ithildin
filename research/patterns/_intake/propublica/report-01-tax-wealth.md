# ProPublica Evidence Ontology — Cluster 01: Tax & Wealth

Reviewed: 2026-07-28. Method: live verification against propublica.org series indexes (`/series/the-secret-irs-files`, `/series/gutting-the-irs`), article fetches, and third-party corroboration for awards/impact. All titles, dates, bylines, and partner attributions below were checked against the live record this session unless marked [not re-verified].

**Scope corrections vs. the candidate list:**
- **Private placement life insurance: DROPPED as a ProPublica original.** The major PPLI exposé work was Bloomberg's, and the definitive public document is the Senate Finance Committee (Wyden) investigation report of Feb 2024 ("$40 billion tax shelter", finance.senate.gov). The ProPublica story initially matched to this slot — "How the Wealthy Save Billions in Taxes by Skirting a Century-Old Law" (Feb 2023) — is actually about **wash-sale skirting / tax-loss harvesting**, included below as its own entry.
- **"Gutting the IRS" partner corrected:** the Dec 11, 2018 anchor story was co-published with **The Atlantic** (confirmed on the article page), not the NYT.
- **Extension:** "The TurboTax Trap" added (not in the candidate list) — ProPublica's other flagship tax-accountability franchise, with the single most transferable detection signature in the cluster (machine-readable dark-pattern artifact) and the largest documented enforcement impact ($141M settlement, FTC order, IRS Direct File).
- Opportunity zones left to the sibling agent.
- 13 full entries (one over the 8–12 soft target) — justified by the wash-sale and TurboTax entries each carrying a detection signature that appears nowhere else in the cluster.

**Series-level provenance note (applies to every "Secret IRS Files" entry):** the underlying source was later identified through prosecution: IRS contractor **Charles Littlejohn** exfiltrated the data (Trump returns → NYT; billionaire trove → ProPublica), pleaded guilty, and was sentenced to 5 years in Jan 2024 (NPR: https://www.npr.org/2024/01/30/1227826718/ex-irs-contractor-sentenced-to-5-years-in-prison-for-leaking-trumps-tax-records). ProPublica states it did not solicit the data and verified it independently (Inside Story: https://www.propublica.org/article/the-inside-story-of-how-we-reported-the-secret-irs-files). Series awards: 2022 Selden Ring Award (USC Annenberg); 2022 Hillman Prize for web journalism; Barlett & Steele Gold announced by ProPublica Oct 2021 (per series index).

---

### The Secret IRS Files: Trove of Never-Before-Seen Records Reveal How the Wealthiest Avoid Income Tax (2021) — billionaires' "true tax rate" on wealth growth is a few percent, with repeated $0 income-tax years
- **URL**: https://www.propublica.org/article/the-secret-irs-files-trove-of-never-before-seen-records-reveal-how-the-wealthiest-avoid-income-tax (Jesse Eisinger, Jeff Ernsthausen, Paul Kiel; June 8, 2021)
- **Partner/awards**: ProPublica original; series won 2022 Selden Ring, 2022 Hillman Prize (web), Barlett & Steele Gold 2021.
- **What they found**:
  - The 25 richest Americans' wealth grew **$401B** (2014–2018) while they paid **$13.6B** federal income tax — a **3.4% "true tax rate"**. Individual rates: Buffett **0.1%** ($23.7M tax on $24.3B wealth growth), Bezos **0.98%** ($973M on $99B), Bloomberg **1.30%** ($292M on $22.5B), Musk **3.27%** ($455M on $13.9B).
  - $0 federal income tax years: Bezos **2007 and 2011**; Musk **2018**; Soros three years running; Icahn twice (2016, 2017 noted).
  - In 2011, reporting a loss, Bezos "claimed and received a $4,000 tax credit for his children."
  - Named the **"buy, borrow, die"** architecture: unrealized gains compound untaxed, borrowing against assets funds consumption tax-free, step-up at death erases the gain.
  - Follow-on from the same trove: at least **18 billionaires received CARES Act stimulus checks** because reported (not real) income fell under the $75K cutoff — 270 ultrawealthy filers with $5.7B in prior-year disclosed income qualified; only 1.4% of that income was wages (Nov 3, 2021: https://www.propublica.org/article/these-billionaires-received-taxpayer-funded-stimulus-checks-during-the-pandemic).
- **Finding type(s)**: wealth-defense-technique; statistical-outlier-practitioner; NEW: realization-avoidance (sub-type of wealth-defense: legally income-free wealth accretion); NEW: means-test-gaming (stimulus follow-on: benefit eligibility via engineered low AGI)
- **Evidence & sources**:
  - leaked IRS bulk microdata ("vast trove… thousands of the nation's wealthiest people, covering more than 15 years" — returns plus information returns and stock-trade records) [privileged]
  - Forbes billionaire wealth series (annual list, year-over-year deltas) [open-public]
  - public tax detail fragments for verification: court documents, politicians' financial disclosures, prior news stories [open-public]
  - direct confirmation with data subjects ("vetting it with individuals whose tax information is contained in the trove") [interviews]
- **Access tier**: mixed — privileged (leak) core; open-public (Forbes, court/disclosure fragments) for denominator and verification
- **Acquisition path**: leak (unsolicited) + bulk-public-data (Forbes) + interviews (subject confirmation)
- **Detection signature**: **denominator-substitution rate construction** — leaked IRS tax-paid figures joined to Forbes wealth-growth estimates per person per year; rate computed against wealth delta instead of taxable income. The story is the ratio: a legally-computed 20–37% effective rate collapses to 0.1–3.4% when the denominator is switched to economic gain. Secondary: outlier-in-microdata scan for `tax_paid = 0` years among the top-25 cohort.
- **Corroboration structure**: leak → cross-checked against dozens of already-public tax details (court records, disclosures) → subject-level confirmation contacts → named subjects offered comment pre-publication (Buffett and others responded on the record).
- **Methodology notes**: Own stated methodology: "How We Calculated the True Tax Rates of the Wealthiest" (https://www.propublica.org/article/how-we-calculated-the-true-tax-rates-of-the-wealthiest — Forbes as wealth source, IRS Publication 1304 income-tax definition, no inflation adjustment caveat) and "The Inside Story of How We Reported the Secret IRS Files" (Aug 6, 2021 — unsolicited receipt, First Amendment analysis, verification approach).
- **Impact**: Senate Finance called for investigation (July 2021); Biden proposed the Billionaire Minimum Income Tax citing the framing (Mar 2022); leak prosecuted (Littlejohn, 5 years, Jan 2024).
- **Generalization**: any regime where a *stock* grows while the *flow* is taxed: compute effective rates against independently-estimated economic gain (property value growth vs property tax paid; portfolio growth vs declared income in any disclosure regime; corporate book profit vs cash tax in 10-Ks). Generic detector: for each subject, assemble (wealth-proxy delta, tax/levy paid) pairs and rank by ratio; flag zero-payment years for high-wealth subjects.

---

### Lord of the Roths: How Peter Thiel Turned a Retirement Account for the Middle Class Into a $5 Billion Tax-Free Piggy Bank (2021) — founder shares at $0.001 inside a Roth IRA compounding to $5B tax-free
- **URL**: https://www.propublica.org/article/lord-of-the-roths-how-tech-mogul-peter-thiel-turned-a-retirement-account-for-the-middle-class-into-a-5-billion-dollar-tax-free-piggy-bank (Justin Elliott, Patricia Callahan, James Bandler; June 24, 2021)
- **Partner/awards**: ProPublica original; part of the awarded series.
- **What they found**:
  - Jan 1999: Thiel's Roth IRA bought **1.7M PayPal founders' shares at $0.001/share = $1,700**, under that year's **$2,000** contribution cap; by end-2019 the Roth held **~$5B**, permanently income-tax-free.
  - Eligibility hinge: 1999 Roth income limit was $110K (single); Thiel's PayPal salary was **$73,263**.
  - Other mega-Roths in the data: Ted Weschler (Berkshire) **$264.4M**, Randall Smith **$252.6M**, Robert Mercer **$31.5M** (2018 values).
  - "Lord of the Roths" title keyed to Thiel's **Rivendell Trust** family trust company.
- **Finding type(s)**: wealth-defense-technique; statistical-outlier-practitioner; preferential-carve-out (de facto — a mass-market vehicle repurposed at founder-equity scale)
- **Evidence & sources**:
  - leaked IRS microdata, specifically **IRA valuation reporting** (custodian-reported year-end account values, i.e., Form 5498-type data) [privileged]
  - SEC filings (PayPal share issuance/prospectus detail) [open-public]
  - court documents [open-public]
  - Thiel's **2005 New Zealand residency application**, containing his financial assistant's memo describing the founders'-share purchase inside the Roth [request-gated — NZ Official Information Act release via prior NZ reporting]
- **Access tier**: mixed — privileged (leak) for account values; open-public (SEC, courts) and request-gated (NZ OIA file) for mechanics
- **Acquisition path**: leak + bulk-public-data + litigation-records + prior-FOIA-reuse
- **Detection signature**: **impossible-value-vs-legal-limit test** — an account type with a hard statutory contribution ceiling ($2K/yr) showing a balance ($5B) unreachable by any compliant contribution+market-return path; the anomaly itself proves an in-kind pricing event. Then **silo-join on the asset**: IRS account values joined to SEC share-issuance records to identify *which* asset at *what* price entered the wrapper.
- **Corroboration structure**: leak (account values) → SEC filings fix share count/price → NZ residency memo independently documents the purchase narrative → subject/spokespeople contacted.
- **Methodology notes**: no standalone sidebar; method described in-article (cross-reference of IRA valuations with SEC filings, court records, and the NZ memo). [inferred: the load-bearing analytic move — limit-vs-balance impossibility — is reconstructed from the article's own framing of the $2,000 cap against the $5B balance.]
- **Impact**: within weeks Senate Finance chair signaled crackdown (June 25, 2021); Congress reported mega-IRA counts tripled (July 28, 2021); House W&M drafted mega-IRA caps into Build Back Better (Sept 21, 2021).
- **Generalization**: any capped or means-tested wrapper (retirement accounts, ISAs, 529s, small-business exemptions, "de minimis" thresholds) holding assets whose value could not have entered legally at market price. Generic detector: `wrapper_balance >> max_cumulative_contribution × plausible_market_return` ⇒ look for self-dealt pricing events (founder shares, pre-IPO allocations, related-party sales) at the wrapper's funding date.

---

### The Billionaire Playbook: How Sports Owners Use Their Teams to Avoid Millions in Taxes (2021) — profitable teams throw off paper losses that tax owners below their players and stadium workers
- **URL**: https://www.propublica.org/article/the-billionaire-playbook-how-sports-owners-use-their-teams-to-avoid-millions-in-taxes (Robert Faturechi, Justin Elliott, Ellis Simani; July 8, 2021)
- **Partner/awards**: ProPublica original; companion video + "Eight Takeaways" explainer same day.
- **What they found**:
  - Steve Ballmer bought the Clippers for **$2B** (2014) and reported **$700M in tax losses 2014–2018** (~$140M tax saved) while leaked NBA records showed the team profitable as recently as 2017.
  - Rate inversion, 2018: Ballmer **12%** on $656M income; LeBron James **35.9%** on $124M; Staples Center concession worker Adelaide Avila **14.1%** on $44,810.
  - Mechanic: post-2004 law (MLB-lobbied, signed by G.W. Bush) lets buyers amortize **~90% of a franchise's purchase price** over 15 years as intangibles (player contracts, TV rights, goodwill) — deducting the price of an *appreciating* asset.
  - Cohort scale: "dozens of team owners across the four largest American pro sports leagues"; Dan Gilbert (Cavaliers) cut taxable income **$443M** (2005–2018); Shahid Khan (Jaguars) **$79M** losses; Leonard Wilf (Vikings) **$66M**.
- **Finding type(s)**: wealth-defense-technique; NEW: paper-loss-manufacturing (tax losses engineered against real-world profitability); preferential-carve-out (2004 industry-lobbied amortization rule)
- **Evidence & sources**:
  - leaked IRS microdata — business profit/loss reports flowing to owners' returns (K-1/Schedule E capture) [privileged]
  - leaked NBA internal financials (third-party leak) showing operating profitability [privileged]
  - court documents, corporate registration data, news reports to attribute entities to teams [open-public]
  - franchise purchase prices and valuations (public record/Forbes) [open-public]
- **Access tier**: mixed — privileged (two independent leaks: IRS + league financials); open-public for entity attribution
- **Acquisition path**: leak + bulk-public-data + litigation-records
- **Detection signature**: **tax-books vs operations-books diff at the entity level** — "dissecting reports sent to the IRS that capture the profit or loss of a business" (their words), attributing team-linked entities to owners via registries/courts, then comparing tax-reported losses against independent profitability evidence (leaked league financials, rising franchise valuations). Plus **cross-cohort rate comparison** on the same economic event (owner vs player vs stadium worker) to render the asymmetry legible.
- **Corroboration structure**: IRS leak (losses) → entity attribution via registries/court records → real-profit check via leaked NBA books and valuation trajectories → expert framing of the 2004 amortization rule → subject comment.
- **Methodology notes**: methodology paragraph in-article; "Eight Takeaways" explainer restates approach. [inferred: entity→owner attribution relied on registry and litigation joins, consistent with the article's sourcing list.]
- **Impact**: IRS opened scrutiny of sports-owner tax avoidance — "Sports Team Owners Face New Scrutiny From IRS Over Tax Avoidance" (May 2, 2024, series index).
- **Generalization**: any sector where acquisition amortization/depreciation manufactures losses against appreciating assets (real estate, franchises, media catalogs, infrastructure concessions). Generic detector: persistent tax losses at entities whose (a) resale valuations rise, (b) internal/leaked operating data show profits, or (c) owners keep buying more of the "money-losing" asset class.

---

### More Than Half of America's 100 Richest People Exploit Special Trusts to Avoid Estate Taxes (2021) — GRATs and kin as the standard estate-tax bypass of the Forbes 100
- **URL**: https://www.propublica.org/article/more-than-half-of-americas-100-richest-people-exploit-special-trusts-to-avoid-estate-taxes (Jeff Ernsthausen, James Bandler, Justin Elliott, Patricia Callahan; Sept 28, 2021)
- **Partner/awards**: ProPublica original; part of awarded series.
- **What they found**:
  - **More than half of the 100 richest Americans** have used GRATs or similar estate/gift-tax-avoiding trusts.
  - Named users include Michael Bloomberg, Leonard Lauder, Stephen Schwarzman, Charles & David Koch, Laurene Powell Jobs, Erik Prince, Calvin Klein, Lorne Michaels, Oprah Winfrey, Mark Zuckerberg, Sheryl Sandberg, Sheldon Adelson, the Walton family.
  - GRAT mechanics: asset in trust; grantor takes back principal + modest statutory interest; all upside above the hurdle passes to heirs gift-tax-free; a failed GRAT costs nothing.
  - Scale: the lawyer who pioneered the modern GRAT estimated (2013) they had cost Treasury **~$100B over the prior 13 years**.
  - Dynasty companion: "The Great Inheritors" (Dec 15, 2021) traced Scripps, Mellon, and Mars (combined ~$114B) across a century using the IRS trove plus letters, diaries, congressional records, court documents.
- **Finding type(s)**: wealth-defense-technique; statistical-outlier-practitioner (population-prevalence variant: the outlier is the *norm* inside the cohort)
- **Evidence & sources**:
  - leaked IRS microdata — trust entities and annuity flows appearing in returns [privileged]
  - public securities filings mentioning GRATs (insider share transfers to trusts named "…GRAT") [open-public]
  - historical archives for the dynasty companion: letters, diaries, books, congressional records, court documents [open-public]
- **Access tier**: mixed — privileged (leak) + open-public (SEC filings, archives)
- **Acquisition path**: leak + bulk-public-data
- **Detection signature**: **artifact-string census over a constructed cohort** — take a fixed universe (Forbes 100), then count members "whose tax records or public filings explicitly mention GRATs or other trusts commonly used to dodge gift and estate taxes" (their stated counting rule). Conservative string/entity-name matching turns an anecdote into a prevalence statistic ("more than half").
- **Corroboration structure**: leak → SEC-filing trust names independently confirm usage for public-company insiders → estate-law experts frame mechanics → named subjects offered comment.
- **Methodology notes**: counting rule stated in-article; explicitly conservative (undercount). [inferred: SEC Form 4/13D trust-name strings provided the open-source replication path for public-company holders.]
- **Impact**: fed the 2021 Build Back Better grantor-trust crackdown drafts (provisions later dropped) [contextual — attribution partial].
- **Generalization**: prevalence-of-technique studies anywhere instruments leave a name or form trace: SLATs/IDGTs in SEC filings, foundations in registries, specific shell-agent addresses in corporate filings. Generic detector: define cohort → enumerate each member's filings → regex/entity-match the instrument fingerprint → report penetration rate, not instances.

---

### Secret IRS Files Reveal How Much the Ultrawealthy Gained by Shaping Trump's "Big, Beautiful Tax Cut" (2021) — a senator's holdout expanded a deduction whose first-year winners included his megadonors
- **URL**: https://www.propublica.org/article/secret-irs-files-reveal-how-much-the-ultrawealthy-gained-by-shaping-trumps-big-beautiful-tax-cut (Justin Elliott, Robert Faturechi; Aug 11, 2021)
- **Partner/awards**: ProPublica original.
- **What they found**:
  - Sen. Ron Johnson's threatened no-vote pushed the §199A pass-through deduction from 17.4% to **20%**; Trump personally called to secure him.
  - First-year winners: Dick & Liz Uihlein (**$118M deduction** on >$700M 2018 income) and Diane Hendricks (**$97M deduction**, ~$36M saved) — together ~$20M in donations to Johnson-supporting groups in 2016; Bloomberg took a **~$68M** deduction.
  - Just **82 ultrawealthy households** collectively gained **>$1B** in first-year savings from the expansion.
  - Conference-committee insertion of eight words — "applied without regard to the words 'engineering, architecture'" — qualified the **Bechtel** family: **$111M** in 2018 deductions for three family members.
- **Finding type(s)**: preferential-carve-out; undisclosed-benefit-to-official (inverted: benefit to the official's financiers); influence-laundering-via-intermediaries (donations → advocacy groups → provision)
- **Evidence & sources**:
  - leaked IRS microdata (per-household deduction amounts) [privileged]
  - lobbying disclosures [open-public]
  - Treasury Department emails and calendars [request-gated — FOIA litigation]
  - successive bill drafts / conference reports [open-public]
- **Access tier**: mixed — privileged (leak) for who-gained-how-much; request-gated (FOIA) for who-pushed; open-public for text evolution
- **Acquisition path**: leak + FOIA + bulk-public-data
- **Detection signature**: **legislative-diff-to-beneficiary join** — diff successive drafts of statutory text to isolate inserted language (the eight words), reverse-engineer the class of taxpayers the insertion uniquely qualifies, then use tax microdata to *name and quantify* the actual first-year beneficiaries; overlay donation and lobbying timelines (temporal-correlation) on the amendment window.
- **Corroboration structure**: bill-text diff → beneficiary identification in tax data → FOIA'd Treasury correspondence establishes advocacy channel → donation records establish financial relationship → subjects/offices offered comment.
- **Methodology notes**: sourcing enumerated in-article (tax records, lobbying disclosures, FOIA-litigated Treasury emails/calendars, drafts). [inferred: the "82 households / $1B" figure implies a microdata query for marginal savings attributable to the 17.4%→20% delta.]
- **Impact**: standing case study in §199A-reform debates and tax-equity hearings [contextual].
- **Generalization**: works for any rule change with drafts: appropriations riders, agency rulemaking redlines (NPRM vs final rule), state tax carve-outs, tariff exclusions, contract modifications. Generic detector: diff versions → for each inserted clause, construct the minimal predicate describing who newly qualifies → search beneficiary datasets for entities matching the predicate → check donor/lobbying ties to the inserters.

---

### America's Highest Earners and Their Taxes Revealed (2022) — the real top-400 income list the IRS doesn't publish with names, with rates declining at the very top
- **URL**: https://projects.propublica.org/americas-highest-incomes-and-taxes-revealed/ (interactive; Paul Kiel, Ash Ngu, Jesse Eisinger, Jeff Ernsthausen; Apr 13, 2022) + companion "America's Top 15 Earners…" + "If You're Getting a W-2, You're a Sucker" (Apr 15, 2022)
- **Partner/awards**: ProPublica original.
- **What they found**:
  - Entry to the top 400 by *reported income* (2013–2018 averages) required **≥$110M/yr**. Top 15 led by Bill Gates (**$2.85B/yr avg, 18.4% rate**), Bloomberg (~$2B, **4.1%**), Powell Jobs ($1.57B, 14.8%), Griffin (~$1.7B, 29.2%), Ballmer ($1.05B, 14.1%), Bezos ($832M, 23.2%, 15th).
  - Rate structure is humped: "a married couple making $200,000 a year could end up paying higher tax rates than a person making $200 million a year" (payroll taxes included).
  - Composition: ~1/5 of the top 400 were hedge-fund managers (short-term gains, 29–34% rates); tech founders ride long-term capital gains far lower.
  - Fame ≠ apex income: LeBron ($96M/yr) and Taylor Swift ($82M/yr) didn't crack the top 400.
- **Finding type(s)**: wealth-defense-technique (income-character arbitrage); NEW: rate-regressivity-at-apex; records-suppression-adjacent (rebuilding a named version of statistics the IRS publishes only as anonymous aggregates)
- **Evidence & sources**:
  - leaked IRS microdata, 2013–2018 [privileged]
  - payroll-tax parameters and public rate schedules for the comparison couple [open-public]
- **Access tier**: privileged (leak) core; open-public overlays
- **Acquisition path**: leak + bulk-public-data
- **Detection signature**: **denominator-construction / build-the-universe** — reconstruct a ranked, named population (top 400 by actual reported income) that official statistics only release anonymized, then compute cohort rate curves across the income distribution to expose the hump (rates rise into the millions, then fall at the apex).
- **Corroboration structure**: leak → internal consistency across six tax years → cross-check of named individuals' known liquidity events per SEC filings [inferred] → subjects offered comment via rollout.
- **Methodology notes**: the interactive carries its own about-the-data notes; core definitions follow the flagship methodology piece. [inferred beyond that.]
- **Impact**: normalized "the apex pays lower rates than the 99.99th percentile" as a quantified, named claim in 2022–2024 rate debates [contextual].
- **Generalization**: wherever an agency publishes only anonymized aggregates or discontinued a table, rebuild the named league table from microdata and compute the metric officials won't: top contractors by margin, top prescribers by reimbursement, top landlords by eviction rate. Generic detector: find the aggregate-only official table → reconstruct entity-level from independent data → publish the top tail with names.

---

### How the Wealthy Save Billions in Taxes by Skirting a Century-Old Law (2023) — industrialized wash-sale skirting: harvest losses without changing the portfolio
- **URL**: https://www.propublica.org/article/irs-files-taxes-wash-sales-goldman-sachs (Paul Kiel, Jeff Ernsthausen; Feb 9, 2023)
- **Partner/awards**: ProPublica original.
- **What they found**:
  - Goldman Sachs ran "Tax Advantaged Loss Harvesting" accounts that sold losers and immediately replaced them with *nearly* identical exposures, skirting the 1921 wash-sale rule's "substantially identical" test.
  - Steve Ballmer generated **~$579M in tax losses (2014–2018)** "without meaningfully changing his investment portfolio," saving **≥$138M**; Dustin Moskovitz accumulated **$84M** in losses across dozens of transactions (≥$20M saved); Zuckerberg and Brian Acton also named.
  - Swap fingerprints: voting↔non-voting share classes of the same company (Under Armour), twin national listings (Shell), near-equivalent index products — economically identical, legally distinct.
- **Finding type(s)**: paper-loss-manufacturing; wealth-defense-technique; fraud-enablement-by-design (bank-productized letter-vs-spirit arbitrage sold at scale)
- **Evidence & sources**:
  - leaked IRS microdata including **voluminous per-trade records** (two decades of returns + trading data) [privileged]
  - securities reference data establishing "nearly identical" pairs (share classes, dual listings, fund equivalence) [open-public]
- **Access tier**: privileged (leak) core; open-public instrument-reference overlay
- **Acquisition path**: leak + bulk-public-data
- **Detection signature**: **substitution-pair detection in transaction streams** — for each realized-loss sale, search the same taxpayer's trades within the ±30-day statutory window for purchases of economic twins that are legal non-twins. Cluster by advisor/custodian to reveal the *productized* pattern (many clients, same trade template ⇒ a bank's program, not individual cleverness).
- **Corroboration structure**: leak (trades + claimed losses) → instrument-equivalence analysis → identification of the common intermediary (Goldman program) → tax-law experts on "substantially identical" → subjects/bank comment.
- **Methodology notes**: reconstruction approach described in-article ("ProPublica reconstructed these strategies using IRS data including… extensive trading records"). [inferred: pairing logic as formalized above.]
- **Impact**: amplified proposals to modernize the wash-sale standard [contextual].
- **Generalization**: any anti-abuse rule keyed to a similarity test invites twin-substitution: crypto wash trading, sanctioned-entity re-papering (same beneficial owner, new shell), debarment evasion (same principals, new LLC). Generic detector: event (loss/ban/flag) followed within a short window by acquisition of a near-identical substitute; cluster templates across subjects to find the enabling intermediary.

---

### Meet the Billionaire and Rising GOP Mega-Donor Who's Gaming the Tax System / How Susquehanna's Jeff Yass Avoided $1 Billion in Taxes (2022) — a high-frequency-trading fortune taxed as if it were patient capital
- **URL**: https://www.propublica.org/article/jeff-yass-susquehanna-tiktok-tax-avoidance (profile, June 21, 2022) and https://www.propublica.org/article/how-susquehanna-yass-avoided-billion-taxes (mechanics; Justin Elliott, Jeff Ernsthausen, Paul Kiel; June 23, 2022)
- **Partner/awards**: ProPublica original.
- **What they found**:
  - Yass averaged a **19%** federal rate on >$1B/yr income — saving **>$1B over six years** vs. the ~40% rate normal for short-term trading gains.
  - Engine: **Susquehanna Fundamental Investments** holds large long positions (Google, Wells Fargo, Coca-Cola) while shorting the S&P 500 containing them — manufacturing short-term losses that soak up high-taxed gains while surviving income emerges as ~20%-taxed long-term gains.
  - IRS has fought Susquehanna partners repeatedly — back-tax bills **>$100M**; one dispute involved >$1B of Swiss stocks bought while shorting identical positions; Susquehanna sued the IRS in 2020.
- **Finding type(s)**: paper-loss-manufacturing; wealth-defense-technique; NEW: income-character-conversion (systematic short-term→long-term re-labeling)
- **Evidence & sources**:
  - leaked IRS microdata (returns + trading records) [privileged]
  - SEC securities filings [open-public]
  - court records of IRS disputes [litigation-records, open-public]
  - interviews with former Susquehanna traders/executives [interviews]
- **Access tier**: mixed — privileged core; open-public (SEC, courts); constructed (insider interviews)
- **Acquisition path**: leak + bulk-public-data + litigation-records + interviews
- **Detection signature**: **income-character anomaly vs business model** — a firm whose production function is short-horizon trading reporting income composed almost entirely of long-term-rate gains; then reconstruct the offsetting-position machinery from disclosed long books vs index shorts. The tell is the *composition mismatch between how the money is made and how it is taxed*.
- **Corroboration structure**: leak (rates/character) → SEC filings show the long book → litigation record shows the IRS itself contested the structure (independent-authority corroboration) → former insiders explain intent → subject comment.
- **Methodology notes**: sourcing enumerated in-article. [inferred: ">$1B saved" is a counterfactual ordinary-rate vs realized-rate application on the same income.]
- **Impact**: standing context for Yass's TikTok stake and political giving; straddle-rule discussion in Congress [contextual].
- **Generalization**: compare *declared category* to *behavioral fingerprint* wherever classification drives rates: employment vs contractor status, trading vs investment books, "charitable" vs commercial nonprofit activity. Generic detector: operational cadence (turnover, positions, filings) inconsistent with the tax/regulatory category producing favorable treatment; prior regulator disputes are the confirming breadcrumb.

---

### IRS Audit of Trump Could Cost Former President More Than $100 Million (2024) — the same Chicago-tower loss deducted twice, caught by joining an anonymized IRS memo to known tax records
- **URL**: https://www.propublica.org/article/trump-irs-audit-chicago-hotel-taxes (Paul Kiel, ProPublica; Russ Buettner, NYT; May 11, 2024)
- **Partner/awards**: formal co-publication with The New York Times.
- **What they found**:
  - 2008: Trump declared his Chicago tower investment **worthless**, reporting losses up to **$651M** (~$94M cash + $557M loan balance).
  - 2010: he merged the tower's owner into DJT Holdings — "like moving coins from one pocket to another" — and used the shift to justify **$168M more losses over 2011–2020** from the same project.
  - IRS position: the 2010 merger violated anti-double-dip law; unwind would shift **~$364M** across 2011–2017 returns; exposure **>$100M** plus interest/penalties.
  - The audit's existence surfaced via a 2019 IRS Technical Advice Memorandum naming the taxpayer only as "A".
- **Finding type(s)**: two-books-asymmetry (temporal variant: same loss, two eras); paper-loss-manufacturing
- **Evidence & sources**:
  - 2019 IRS Technical Advice Memorandum, anonymized [open-public — published agency memoranda]
  - Trump tax records previously obtained by the NYT [privileged — prior leak]
  - NY AG's 2022 fraud-suit filings [litigation-records]
  - Dec 2022 Joint Committee on Taxation report [open-public]
  - six partnership-tax experts [interviews]
- **Access tier**: mixed — open-public skeleton (memo, JCT, dockets) keyed by privileged prior records
- **Acquisition path**: mixed — leak (prior) + litigation-records + bulk-public-data + interviews
- **Detection signature**: **de-anonymization by fact-join + cross-year duplicate-claim detection** — match the anonymized memo's fact pattern (asset type, dates, loss structure) against known tax records and public litigation exhibits to identify taxpayer "A"; then line up the 2008 worthlessness deduction against 2011–2020 partnership losses to show the *same economic loss claimed twice* across a restructuring boundary.
- **Corroboration structure**: anonymized agency memo → fact-pattern match to privately-held tax records → NYAG exhibits + JCT report independently confirm details → six-expert review ("I think he ripped off the tax system" — Walter Schwidetzky) → subject comment.
- **Methodology notes**: triangulation enumerated in-article. [inferred: identification logic as reconstructed above from the article's source list.]
- **Impact**: exposed a nine-figure live audit of a presidential candidate; congressional interest in the mandatory-audit program [contextual].
- **Generalization**: agencies constantly publish anonymized decisions (tax memos, enforcement actions, medical-board orders, arbitration awards). Generic detector: treat anonymized rulings as one half of a join — match distinctive fact patterns to known entities from registries, dockets, or held data. Separately: duplicate-claim detection = same loss/asset/expense surfacing in two periods or entities bridged by a restructuring.

---

### How the IRS Was Gutted (2018) — a decade of budget cuts collapsed rich-taxpayer enforcement while cheap poor-taxpayer audits persisted
- **URL**: https://www.propublica.org/article/how-the-irs-was-gutted (Paul Kiel, Jesse Eisinger; Dec 11, 2018) + "…Facing 'Collapse'" (Oct 1, 2018) + "The IRS Tried to Take on the Ultrawealthy. It Didn't Go Well." (Apr 5, 2019)
- **Partner/awards**: **co-published with The Atlantic** (confirmed on-page). Series: "Gutting the IRS", 21 stories.
- **What they found**:
  - Budget: **$14B (2010) → ~$11.5B (2018)** inflation-adjusted; auditors **~14,300 (2010) → 9,510 (2017)** — fewest revenue agents since **1953**.
  - Enforcement: audits down **42%** (−675,000 cases 2010–2017); nonfiler investigations **2.4M (2011) → 362K (2017)**; expiring uncollected tax debt **$482M (2010) → $8.3B (2017)** (17×).
  - Money: ≥**$18B/yr** revenue foregone (~$95B cumulative since 2011).
  - Distributional core: **EITC recipients (typically <$20K income) were 36% of all audits**; millionaire audits fell from 32K (2010) to ~16K (2018), ~80% less likely than 2011; the Global High Wealth "wealth squad" unit was neutered from inside.
- **Finding type(s)**: NEW: enforcement-regressivity (enforcement redirected from powerful to powerless as capacity shrinks); algorithmic-or-systematic-denial (EITC correspondence-audit machine); regulatory-capture/revolving-door (capture-by-defunding)
- **Evidence & sources**:
  - IRS Data Books and enforcement statistics (official annual series) [open-public]
  - internal collection reports, inspector-general reports, Treasury records [open-public/request-gated mix]
  - interviews: **50+ current and former IRS employees**, dozens of tax professionals [interviews]
- **Access tier**: mixed — open-public statistical backbone; constructed insider-interview corpus. No leak required.
- **Acquisition path**: bulk-public-data + interviews (+ FOIA-adjacent internal documents)
- **Detection signature**: **policy-shadow measurement via time-series decomposition of official statistics** — the agency's own Data Book series, disaggregated by income class over a decade, shows enforcement collapsing ~80% for millionaires while persisting for EITC filers; the diff between stated mission and measured allocation is the story. Insider interviews supply the mechanism the numbers can't.
- **Corroboration structure**: official statistics → insider testimony (50+ employees) explains causation → IG/Treasury documents corroborate internal decay → agency response.
- **Methodology notes**: source base enumerated in-article; statistics replicable from published Data Books — fully reproducible without privileged access.
- **Impact**: framed the case for the Inflation Reduction Act's $80B IRS enforcement restoration (2022) and years of oversight hearings [contextual but widely credited].
- **Generalization**: any agency publishing activity statistics can be shadow-audited: SEC enforcement by target size, OSHA inspections by employer class, AG actions by industry. Generic detector: decade-scale enforcement time series segmented by target wealth/power; flag divergence between segments; pair with insider interviews for mechanism.

---

### Where in the U.S. Are You Most Likely to Be Audited by the IRS? (2019) — the most-audited county in America is poor, rural, and Black, because EITC audits are cheap
- **URL**: https://projects.propublica.org/graphics/eitc-audit (Paul Kiel, Hannah Fresques; Apr 1, 2019) + "Who's More Likely to Be Audited: A Person Making $20,000 — or $400,000?" (Dec 12, 2018) + "It's Getting Worse…" (May 30, 2019)
- **Partner/awards**: ProPublica original (map built on an outside ex-insider's model).
- **What they found**:
  - **Humphreys County, MS** (median household income $26K, majority Black, >1/3 in poverty) is the most heavily audited county in America: **~11 audits per 1,000 filings**, >40% above the national average and **51% higher than Loudoun County, VA**, the nation's richest county ($130K median).
  - The five most-audited counties are all predominantly African American rural counties in the Deep South; high rates also blanket Hispanic South Texas, reservation counties, and poor white Appalachia — because **>1/3 of all audits are EITC correspondence audits**.
  - Follow-up forced the admission: the IRS told Congress auditing the poor is the "most efficient use of available IRS examination resources" (Oct 2019).
- **Finding type(s)**: concentrated-harm-hotspot; algorithmic-or-systematic-denial; enforcement-regressivity; extraction-from-captive-population (audit burden on benefit claimants)
- **Evidence & sources**:
  - county-level audit-rate estimates modeled by **Kim Bloomquist, 20-year IRS research-division senior economist**, published in Tax Notes — built from "audit coverage rates published in the annual IRS Data Book in combination with county tax return data on the IRS website", tax years 2012–2015 [constructed — expert model on open data]
  - IRS Data Book audit statistics [open-public]
  - Census/ACS demographics for the overlay [open-public]
- **Access tier**: constructed (modeled from open-public inputs) — no leak, no FOIA
- **Acquisition path**: bulk-public-data + NEW path tag: insider-expert-model-adoption (adopting/visualizing an ex-insider's published model)
- **Detection signature**: **hotspot-mapping-from-model-data** — no agency publishes audit rates by geography, so combine two official datasets (audit coverage by return type × county-level return-type composition) to *estimate* the unpublished geographic distribution; then overlay demographics to expose disparate impact. Denominator-construction in service of a map.
- **Corroboration structure**: ex-IRS economist's peer-published model → ProPublica visualization + demographic overlay → IRS non-denial and subsequent written admission to Congress → later independent confirmation (2023 Stanford/Treasury finding that Black taxpayers are audited 2.9–4.7× more) [contextual].
- **Methodology notes**: Own stated methodology on the graphics page (Bloomquist model, Data Book + county return data, 2012–2015).
- **Impact**: congressional letters to the commissioner; the "efficient use of resources" reply became the enduring indictment; fed the 2023 IRS pledge not to raise audit rates on <$400K households [contextual].
- **Generalization**: agencies rarely publish the *geography* of their enforcement. Generic detector: (activity rate by category) × (category composition by geography) = estimated activity by geography; overlay demographics. Works for stop-and-frisk, benefit-fraud prosecutions, environmental inspections, mortgage denials — anywhere two official tables share a category key.

---

### Never-Before-Seen Trump Tax Documents Show Major Inconsistencies (2019) — two sets of books: one story for the lender, another for the property-tax office
- **URL**: https://www.propublica.org/article/trump-inc-podcast-never-before-seen-trump-tax-documents-show-major-inconsistencies (Heather Vogell; Oct 16, 2019; with the "Trump, Inc." podcast, WNYC collaboration)
- **Partner/awards**: WNYC "Trump, Inc." co-production context.
- **What they found**:
  - **40 Wall Street**: told the lender occupancy was **58.9%** (Dec 31, 2012) rising to 95% within years; told tax authorities **81%** (Jan 5, 2013); 2017 insurance reported **$744,521** to tax authorities vs **$457,414** in loan records; 2015 ground rent **$1.65M** vs **$1.24M**.
  - **Trump International Hotel & Tower (Columbus Circle)**: 2017 commercial-tenant income ~**$822K** to tax authorities vs **$1.67M** to lenders; roof-antenna lease income omitted from tax filings for nine straight years while present in loan documents; across eight years, tax-reported income ran ~**81%** of lender-reported.
  - Experts: "versions of fraud" (Nancy Wallace, Berkeley); "a set of books for the tax guy and a set for the lender" (Kevin Riordan, Montclair State).
- **Finding type(s)**: two-books-asymmetry (the canonical instance)
- **Evidence & sources**:
  - NYC property-tax appeal filings (income/expense statements) via **New York's Freedom of Information Law** — accessible because Trump appealed his tax bill nine years running [request-gated]
  - loan-level data public because **Ladder Capital securitized the debt as CMBS** (servicer reports, offering documents) [open-public via securitization disclosure / commercial CMBS data]
  - a dozen real-estate professionals for review [interviews]
- **Access tier**: mixed — request-gated (FOIL) × open-public (CMBS disclosures)
- **Acquisition path**: FOIA + bulk-public-data (securitization trail) + interviews
- **Detection signature**: **two-books-diff on a hard asset key** — same building, same year, reported to two audiences with opposite incentives (minimize to the assessor, maximize to the lender); join tax-appeal income/expense statements to CMBS servicer data on property+year and diff line items (occupancy, rent roll, insurance, ground rent). The *incentive-shaped direction* of each gap is the fraud tell.
- **Corroboration structure**: FOIL documents ↔ CMBS records (independent filing channels: owner→assessor vs owner→trustee) → 12-expert review → Trump Org comment sought.
- **Methodology notes**: acquisition described in-article (FOIL availability due to serial appeals; securitization making loan data public). [inferred: line-item join structure as above.]
- **Impact**: NYC officials including the mayor referred the discrepancies for investigation; the pattern anticipated the NY AG's 2022 civil-fraud case over parallel asymmetries [contextual].
- **Generalization**: any actor filing the same economic facts to multiple authorities with different incentives: customs value vs insurance value; SEC numbers vs tax numbers; grant budgets vs audited financials; visa income statements vs tax returns. Generic detector: enumerate all filings keyed to one asset/entity/period; diff shared fields; score gaps by whether their direction tracks the filer's incentive in each channel.

---

### The Billion-Dollar Loophole (2017) — syndicated conservation easements: buy land, inflate the appraisal, sell the deduction at 4–9× cash in
- **URL**: https://www.propublica.org/article/conservation-easements-the-billion-dollar-loophole (Peter Elkind; Dec 20, 2017; **co-published with Fortune**)
- **Partner/awards**: Fortune co-publication; National Press Club Lee Walczak Award (per ProPublica's awards listing).
- **What they found**:
  - The syndication machine: promoter buys land, commissions a compliant appraisal at a multiple of cost, sells partnership stakes; investors deduct **"$4 for each $1 they invested"** (Millstone Golf Course: bought **$9.8M**, appraised **$41M**); an IRS preliminary analysis found **$9 of deduction per $1 invested** on average.
  - Cost: **$1.2–2.1B/yr** to Treasury (Brookings' Adam Looney estimate).
  - **EcoVest** identified as the most prolific syndicator; spent **$1.13M** lobbying against IRS enforcement; per the later DOJ suit, ≥96 syndications generated **>$2.0B** in deductions from "overvalued" contributions.
  - Expert verdict: "tax shelters masquerading as conservation easement transactions, based on highly inflated appraisals" (Steve Small, who wrote the original easement regs at Treasury).
- **Finding type(s)**: NEW: valuation-arbitrage (monetizing a fabricated appraisal delta); fraud-enablement-by-design (promoter-packaged product); charity-mission-inversion (conservation deduction inverted into a profit machine)
- **Evidence & sources**:
  - promoter promotional documents and investor private-placement memoranda [privileged/insider-provided]
  - tax returns and IRS aggregate data on claimed deductions [mixed]
  - recorded conversations, interviews with land-trust officials, appraisers, brokers [interviews/field]
  - land purchase records vs claimed appraisals [open-public — deeds]
- **Access tier**: mixed — constructed (offering docs, recorded calls) + open-public (deeds, IRS notices) + privileged fragments
- **Acquisition path**: mixed — insider documents + interviews + bulk-public-data (property records); later reinforced by litigation-records (DOJ v. EcoVest, Dec 2018)
- **Detection signature**: **purchase-price-vs-claimed-value multiple** — join a property's recent arm's-length purchase price (deed records) to the value claimed months later in the tax structure (offering memos/appraisals); multiples of 4–9× within short windows are the shelter fingerprint. Promoter-level aggregation (same sponsor, many deals, same appraisers) exposes the industry.
- **Corroboration structure**: offering documents (claimed returns) → deed records (real prices) → IRS aggregate analyses → land-trust and appraisal experts → promoter comment; later fully corroborated by DOJ complaint and criminal convictions.
- **Methodology notes**: no formal sidebar; sourcing visible in-article. [inferred: deed-vs-appraisal join as the core quantitative move.]
- **Impact**: DOJ sued EcoVest promoters (2018); IRS listed-transaction designation and mass audits; promoters Fisher/Sinnott convicted (25- and 23-year sentences); Congress capped deductions at 2.5× basis in SECURE 2.0 (Dec 2022) — ProPublica retrospective: "How Congress Ended 'Syndicated Conservation Easement' Tax Scams" (https://www.propublica.org/article/syndicated-conservation-easements-tax-scam-irs-biden).
- **Generalization**: any deduction/credit keyed to an *appraised* rather than *transacted* value: art donations, façade easements, crypto donations, transfer-pricing intangibles, SPAC write-ups. Generic detector: `claimed_value / recent_transaction_price` per asset, clustered by promoter and appraiser; the repeat-appraiser graph is the enabling-professional map.

---

### The TurboTax Trap: TurboTax Deliberately Hides Its Free File Page From Search Engines (2019) — a public benefit suppressed with a machine-readable dark pattern
- **URL**: https://www.propublica.org/article/turbotax-deliberately-hides-its-free-file-page-from-search-engines (Justin Elliott; Apr 26, 2019); series anchor "Here's How TurboTax Just Tricked You…" (Apr 22, 2019)
- **Partner/awards**: ProPublica original ("The TurboTax Trap" series).
- **What they found**:
  - Intuit placed **`noindex,nofollow`** directives on the TurboTax **Free File** landing page — "It's deliberately saying: 'Google, we don't want you here. Do not bring us traffic'" (web expert Jared Spool) — while the *paid* product's page carried `index,follow`.
  - Context: under the IRS Free File MOU, industry pledged free filing for ~70% of taxpayers in exchange for the IRS not building its own tool; actual uptake was **~3%** of eligible filers.
  - Earlier installment showed deceptive design/ad funnels steering eligible low-income filers into paid products; Intuit ended the search-hiding only after publication.
- **Finding type(s)**: NEW: dark-pattern-suppression-of-public-benefit (deliberate discoverability sabotage of an obligation); algorithmic-or-systematic-denial; fraud-enablement-by-design; regulatory-capture/revolving-door (the no-compete MOU itself)
- **Evidence & sources**:
  - the live web artifact: robots meta directives / robots.txt on Intuit's own pages [open-public, machine-readable, self-authenticating]
  - IRS–industry Free File agreements and uptake statistics [open-public]
  - user-experience walkthroughs and crowdsourced reader cases [constructed]
  - later series installments: internal Intuit documents, then FTC/state-AG evidentiary records [privileged → litigation-records]
- **Access tier**: open-public core (the artifact sat in page source) + constructed walkthroughs; later privileged/litigation layers
- **Acquisition path**: scrape/field-observation (page-source inspection) + crowdsourced + bulk-public-data; later litigation-records
- **Detection signature**: **compliance-artifact inspection in machine-readable infrastructure** — when an entity is obligated to *offer* something, check the technical channel for deliberate suppression: robots/noindex directives, redirect games, dark-pattern UI forks. The gap between the paid page's `index,follow` and the free page's `noindex` is intent, written in config.
- **Corroboration structure**: page-source artifact (self-authenticating) → web-standards expert interpretation → company response → IRS-funded review later confirmed the hiding → FTC/AG proceedings adopted the findings.
- **Methodology notes**: artifact and interpretation documented in-article. [inferred: replication is a one-line fetch of page source.]
- **Impact**: IRS ended the no-compete clause and banned search-hiding (Dec 2019); Intuit exited Free File (2021); FTC sued (2022) and issued a final deception order (2024); 50-state **$141M** settlement with checks to ~4.4M customers; IRS built **Direct File** (2024).
- **Generalization**: obligations to publicize are everywhere (claim portals, benefit applications, recall notices, opt-outs, unclaimed-property lookups). Generic detector: for each obligated-disclosure URL, diff its technical accessibility signals (robots directives, sitemap presence, search ranking, form friction) against the same operator's *revenue-generating* equivalent. Asymmetry = engineered suppression.

---

## Companion stories noted, not fully extracted

| Story (date) | One-line finding | Signature it adds |
|---|---|---|
| These Billionaires Received Taxpayer-Funded Stimulus Checks (Nov 2021) | 18+ billionaires got CARES checks via engineered sub-$75K AGI | means-test-gaming join: benefit rolls × wealth list |
| A Massive Oil Spill Helped One Billionaire Avoid Income Tax for 14 Years (Dec 2021) | casualty/loss carryforwards as multi-decade tax eraser | single-event loss propagated across years |
| When You're a Billionaire, Your Hobbies Can Slash Your Tax Bill (Dec 2021) | hobby "businesses" (horses etc.) as loss farms | perpetual-loss entities with consumption value |
| Private Planes and Luxury Yachts… Huge Tax Breaks (Apr 2023) | toys structured as deductible business assets | consumption-asset-as-business detection |
| Ken Griffin Spent $54M Fighting a Tax Increase (Jul 2022) | political spend vs personal tax savings ROI | expenditure-vs-benefit temporal correlation |
| How the Ultrawealthy Use Private Foundations… (Jul 2023) | foundation deductions with minimal public benefit | charity-mission-inversion metrics (payout vs deduction) |
| The Great Inheritors (Dec 2021) | century-scale dynastic tax engineering (Scripps/Mellon/Mars) | longitudinal family-wealth tracing |
| Buffett / mutual-fund-exec personal trading (Nov 2023) | personal trades parallel institutional flows | personal-vs-institutional trade-book diff (markets cluster) |
| NIIT sidestep / Medicare-tax "limited partner" loophole (Dec 2024) | statutory gaps exploited at scale | statutory-gap census in microdata |

---

## Cluster Synthesis

### 1. Recurring evidence-source types (frequency across 13 full entries)

| Source type | Count | Notes |
|---|---|---|
| Leaked IRS bulk microdata (returns + information returns + trade-level records) | 9 | The series backbone; always *paired* with public data, never solo |
| Public securities filings (SEC: 13F, Form 4, prospectuses) | 6 | Standard verification/identification join for public-company wealth |
| Official agency statistics (IRS Data Books, JCT, aggregate analyses) | 5 | Carries two full stories on its own (Gutted, EITC map) — no leak needed |
| Litigation records (dockets, AG suits, DOJ complaints, Tax Court) | 6 | Both corroboration and independent-authority validation ("the IRS itself contested this") |
| FOIA/FOIL records (NYC tax appeals, Treasury emails, NZ OIA file) | 3 | Small count, decisive role — each unlocked the who/why layer |
| Interviews incl. insiders (ex-IRS 50+, ex-Susquehanna, land trusts, experts) | 9 | Mechanism and intent; never the quantitative spine |
| Wealth/valuation reference lists (Forbes) | 3 | The denominator nobody official publishes |
| Third-party leaked business records (NBA financials) | 1 | Independent-leak crosscheck |
| Deal/promotional documents (placement memos) | 1 | Shelter-industry self-description |
| Machine-readable web artifacts (robots directives) | 1 | Self-authenticating intent evidence |
| Property/deed records | 2 | Ground truth for valuation games |

Structural observation: ProPublica's tax work is **never single-source**. The leak is treated as a *starting index*; every published claim is re-anchored to at least one *differently-generated* record (SEC filing, court exhibit, official statistic, deed, or subject confirmation) — corroboration by independent generation process, not by repetition.

### 2. Recurring detection signatures (frequency)

| Signature | Count | Where |
|---|---|---|
| denominator-construction (build the unpublished universe/base, then compute rates) | 5 | true tax rate; top 400; Gutted audit rates; EITC map; GRAT prevalence |
| silo-join-on-hard-identifier (person/asset/property/year) | 6 | IRS×Forbes; IRS×SEC (Thiel, GRATs, Yass); FOIL×CMBS; memo×tax records |
| two-books-diff (same facts, two audiences/periods) | 3 | Trump 2019 (lender vs assessor); Trump 2024 (loss claimed twice); sports owners (tax vs operating books) |
| outlier-in-microdata (zero-tax years, impossible balances, character mismatch) | 4 | flagship $0 years; Thiel limit-vs-balance; Yass income character; wash-sale loss volumes |
| policy-shadow-measurement (measure what the owner won't publish) | 3 | Gutted; EITC map; top-400 reconstruction |
| temporal-correlation (money in → provision out; trade windows) | 3 | 199A donations; wash-sale ±30-day windows; Griffin (companion) |
| substitution-pair detection (economic twin swapped for legal non-twin) | 2 | wash sales; Yass offsetting books |
| valuation-multiple screening (transacted vs claimed value) | 2 | easements; Trump 2019 (incentive-signed gaps) |
| legislative-diff-to-beneficiary join | 1 (deep) | 199A eight words → Bechtel |
| hotspot-mapping-from-model-data | 1 | EITC county map |
| compliance-artifact inspection (machine-readable intent) | 1 | TurboTax robots directives |
| de-anonymization-by-fact-join | 1 | Trump 2024 memo "A" |

New tags coined this review — finding types: **realization-avoidance**, **means-test-gaming**, **paper-loss-manufacturing**, **income-character-conversion**, **enforcement-regressivity**, **valuation-arbitrage**, **dark-pattern-suppression-of-public-benefit**. Signatures/paths: **impossible-value-vs-legal-limit**, **substitution-pair detection**, **de-anonymization-by-fact-join**, **legislative-diff-to-beneficiary-join**, **compliance-artifact inspection**, **insider-expert-model-adoption**.

### 3. Transferable pattern candidates

**P1. Denominator Substitution ("true rate" construction)**
Mechanics: an official rate looks unremarkable because its denominator is the one the subject controls (taxable income, declared value, reported occupancy). Rebuild the rate with an *independent* denominator — wealth growth, market valuation, deed price, third-party volume — and the story is the collapse between the official rate and the economic rate. ProPublica ran this at every scale: person (3.4% true tax rate), cohort (top 400 vs the $200K couple), county (audits per 1,000 filings), agency (audits per millionaire).
Minimum data: subject-level outcome numerators from any authoritative source; an independent denominator series (valuation lists, registries, deeds, market data) joinable on subject and period.
Agent recognition cue: whenever a rate, ratio, or "effective" figure comes from a subject's own filings, ask *who controls the denominator* and whether an independent series could replace it. If substitution moves the figure by an order of magnitude, the gap is the finding.

**P2. Two-Books Diff on a Hard Key**
Mechanics: entities describe the same economic fact differently to audiences with opposing incentives (lender vs assessor, investor vs IRS, customs vs insurer), or re-describe it across a restructuring boundary to harvest it twice. Join filings on a hard key (property, EIN, docket, asset, period), diff shared fields, and score each gap by whether its *direction* matches the filer's incentive in that channel — incentive-aligned gaps are intent, random gaps are noise.
Minimum data: two independent filing channels covering the same entity/asset/period with at least one shared quantitative field.
Agent recognition cue: an entity filing to multiple authorities is a two-books candidate by default; prioritize when one channel is discretionary (appeals, appraisals, estimates) and the other is contractual. Restructurings bridging two claim periods are the temporal variant (Trump Chicago).

**P3. Impossible-Value / Limit-Anomaly Screen**
Mechanics: legal wrappers have hard parameters — contribution caps, income-eligibility ceilings, ownership thresholds. A wrapper whose observed contents could not have arisen from compliant inputs (Thiel: $5B in a $2K/yr vehicle) proves a non-market event (self-dealt pricing, related-party transfer, backdating) without observing the event itself; the anomaly licenses a targeted hunt for the entry transaction. Same math flags billionaires on stimulus rolls (means-test-gaming).
Minimum data: wrapper-level values (balances, holdings, benefit receipts) plus the statutory parameter history.
Agent recognition cue: for any capped/means-tested instrument in held data, compute `observed_value / max_legal_accumulation`; anything above a plausible market multiple is a lead.

**P4. Legislative-Diff → Beneficiary Reverse-Engineering**
Mechanics: rules accrete through drafts. Diff versions to isolate inserted language; convert each insertion into a predicate describing exactly who newly qualifies; search beneficiary-side data (tax records, contracts, subsidies) for matching entities; overlay donor/lobbying/meeting timelines on the insertion window. Eight anonymous words became "$111M for three Bechtels" only because the insertion was diffable and the beneficiary class computable.
Minimum data: two+ versions of the rule text; any beneficiary-side dataset; optionally influence records for attribution.
Agent recognition cue: any late-stage textual change in a rule, contract mod, or ordinance (this platform's ISAP V ceiling-deletion finding is exactly this pattern). The narrower the predicate's matching class, the stronger the carve-out inference.

**P5. Compliance-Artifact Inspection (intent written in infrastructure)**
Mechanics: when an actor is obligated to provide or publicize something it profits from suppressing, the suppression often leaves machine-readable residue: robots/noindex directives, redirect chains, form-friction asymmetries, dead links on the obligated path beside polished links on the revenue path. The artifact is self-authenticating, and the paid/free asymmetry within the *same operator* supplies intent.
Minimum data: the obligated channel's technical surface (page source, DNS, sitemaps, response codes) plus the operator's commercial equivalent as control.
Agent recognition cue: whenever an investigation touches an entity with a disclosure/offering obligation (Free File-style MOUs, claims portals, recall or opt-out mechanisms, transparency mandates), diff the technical accessibility of the obligated path vs the profitable path before reading a single document — the cheapest high-yield probe in this cluster, and directly executable with this platform's existing infra tooling.
