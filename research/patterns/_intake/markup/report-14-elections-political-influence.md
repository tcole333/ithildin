# The Markup Evidence Ontology — Cluster 14: Elections & Political Influence

Compiled July 29, 2026. Web-verified against The Markup, CalMatters, source organizations, public-record interfaces, and released code. This report covers eight investigation-bearing stories from the 12-page Election 2020/Election 2026 census cluster. The Election 2020 methodology page is attached to its parent investigation rather than counted as a ninth story; the ballot-measure roundup, pre-election platform preview, and general voting-machine explainer are excluded because they do not add a distinct evidentiary detector.

## Scope, attribution, and candidate-method corrections

- **Domain-structural attribution.** This report follows the census rule: a dated editorial URL exposed by The Markup's own live series structure counts as The Markup work, including post-merger work published on `themarkup.org`; a separately self-canonical CalMatters copy is named as a co-publication but not counted again. The two post-merger entries have parallel [CalMatters copies](https://calmatters.org/economy/technology/2026/01/mysterious-website-2026-election/) ([March follow-up](https://calmatters.org/economy/technology/2026/03/old-political-club-is-big-social-influencer/)).
- **"Campaign-ad pricing experiments" — corrected to an observational pricing audit.** The Markup did not buy matched ads or randomize audiences. It analyzed Meta Ad Library records supplied through NYU, estimated CPM from disclosed spend/impression ranges, and stratified by candidate, time, and geography. The causal reason for the price gap remained unidentified, as the [methodology page](https://themarkup.org/show-your-work/2020/10/29/how-we-analyzed-the-cost-of-trumps-and-bidens-campaign-ads-on-facebook) states.
- **"Voter-site availability tests" — not found.** The registration story did not probe, load-test, or continuously monitor state websites. It reconstructed already-observed outages from Election Protection hotline reports, court proceedings, agency explanations, and contemporaneous reporting. A prospective availability monitor is a valid generalization, but attributing one to the published story would be incorrect ([story](https://themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures)).
- **Open-source census check.** Of these eight stories, only the Facebook-pricing investigation has a first-party Markup repository and a dedicated Show Your Work page. The other seven have no dedicated methodology page in the live [Show Your Work index](https://themarkup.org/series/show-your-work) and no story-specific repository in [The Markup's GitHub organization](https://github.com/the-markup). A third-party NYU repository supports the QAnon-ad story but does not preserve the decisive story-specific ad corpus.

---

### Voter Registration Websites Are Crashing, Locking Out Would-Be Voters (2020) — deadline-day infrastructure failures denied access before courts could reopen registration

- **URL**: [The Markup, Oct. 27, 2020](https://themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures)
- **Partner/awards**: The Markup original; no reporting partner or project-specific award identified in the live corpus.
- **What they found**:
  - Florida's registration site failed at its deadline for what a voting-rights lawyer described as the **fourth time in three years**; the state reported an unprecedented **1.1 million requests per hour** and acknowledged server misconfiguration as a contributing vulnerability ([story](https://themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures)).
  - Virginia's site went completely down on its last registration day after a cut fiber-optic cable; Pennsylvania suffered a data-center outage, and earlier cases in Georgia and New York showed the failure pattern was not confined to one vendor or state ([story](https://themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures)).
  - Virginia's federal court granted a **two-day extension**. Florida offered less than a day, and a federal judge said the state had failed its citizens but declined a longer extension because it might create additional confusion ([story](https://themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures)).
  - No national outage census existed, so the number of people who attempted and failed to register remained unknowable; the article carefully presented “tens of thousands” as an advocate's plausible scale, not a measured count ([story](https://themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures)).
- **Finding type(s)**: **deadline-critical-infrastructure failure** (new tag: a public service fails at the legal cutoff when demand is most consequential); **remedy-after-denial** (new tag: access is restored only through emergency litigation after some users have already been excluded).
- **Evidence & sources**:
  - **Constructed tip channel — Election Protection hotline and advocate interview**: contemporaneous callers in Florida and Virginia surfaced the failure pattern to the Lawyers' Committee; The Markup interviewed project lawyer Ryan Snow.
  - **Litigation records — emergency federal complaints and orders**: Virginia and Florida proceedings established outage dates and the different remedies.
  - **Agency operational accounts — state statements and traffic metrics**: Florida supplied the request-rate figure; Pennsylvania described outage duration and said no data were lost.
  - **Contemporaneous incident reporting — local and national press**: reports established the cut cable, data-center outage, server configuration, and prior incidents.
  - **Expert interviews — VotingWorks and voting-rights practitioners**: separated ordinary capacity failure from unsupported claims of malicious attack.
- **INPUT DEPENDENCY**: **(b) re-anchoring.** Discovery came through a non-public, contemporaneous advocate/hotline channel; the reusable verification half was public or publicly requestable—court dockets/orders, state statements, outage notices, and contemporaneous local reports. The public half can verify that a named state system failed and what remedy followed, but it cannot recover the hotline's denominator of unsuccessful users. This was **not** an availability-test instrument.
- **Detection signature**: **deadline-outage-remedy reconstruction** — hotline incidents and official outage reports **joined to** registration deadlines and federal-court remedies **on state + event date** revealed recurring capacity failures whose legal repair arrived after access had already been denied.
- **Corroboration structure**: user reports supplied the alert; distinct state explanations supplied causes; sworn/public court records supplied the remedy; an independent technical expert ruled out the unsupported leap from outage to attack.
- **Methodology notes**: No dedicated Show Your Work page or GitHub repository. **[Inferred]** The method is recoverable from the article's explicit source chain: identify incidents through Election Protection, reconstruct each outage with public reporting and agency responses, then align the failure window with the statutory deadline and court action. The decisive detector is **not re-runnable from released artifacts alone** because no incident table, hotline export, or source bundle was released.
- **Official response/outcome**: Virginia reopened registration for two days by federal order; Florida extended for less than a day. The article does not claim that its publication caused either remedy ([story](https://themarkup.org/election-2020/2020/10/27/voter-registration-websites-crashing-failures)).
- **Generalization**: Apply to any legally timed public service—benefits recertification, tax filing, licensing, grant applications, school enrollment. A generic detector monitors service status and error responses, joins downtime to cutoff calendars and demand spikes, and measures remedy latency plus the unrecoverable population whose failed attempts leave no official record.

---

### Facebook Charged Biden a Higher Price Than Trump for Campaign Ads (2020) — binned ad disclosures exposed an 11% overall CPM gap and a two-to-one swing-state gap

- **URL**: [The Markup, Oct. 29, 2020](https://themarkup.org/election-2020/2020/10/29/facebook-political-ad-targeting-algorithm-prices-trump-biden)
- **Partner/awards**: The Markup original. **Data partner, not co-publisher:** NYU Online Political Transparency Project/Ad Observatory supplied a database derived from Meta's Ad Library API ([method](https://themarkup.org/show-your-work/2020/10/29/how-we-analyzed-the-cost-of-trumps-and-bidens-campaign-ads-on-facebook)).
- **What they found**:
  - Across analyzable ads, Biden paid an estimated **$25.52 per 1,000 impressions** and Trump **$23.09**, an **11% difference**. At Trump's average rate, Biden would have spent about **$8 million less** ([method](https://themarkup.org/show-your-work/2020/10/29/how-we-analyzed-the-cost-of-trumps-and-bidens-campaign-ads-on-facebook)).
  - For swing-state ads in July and August, Biden paid **$34.34 CPM** versus Trump's **$16.55**—more than double. The advantage disappeared in September, and Biden paid slightly less in early October, showing a time-varying disparity rather than a fixed partisan tariff ([story](https://themarkup.org/election-2020/2020/10/29/facebook-political-ad-targeting-algorithm-prices-trump-biden)).
  - The Markup began with **51,844 Biden ads** and **289,650 Trump ads** in the window. After excluding unbounded low-spend/low-impression and over-one-million-impression records, **22,522 Biden ads** and **60,737 Trump ads** supported CPM estimation; **8,996** and **21,888**, respectively, met the swing-state rule ([method](https://themarkup.org/show-your-work/2020/10/29/how-we-analyzed-the-cost-of-trumps-and-bidens-campaign-ads-on-facebook)).
  - A paired illustration showed Facebook charging Trump about **$14 CPM** and Biden **$91 CPM** to reach older Arizonans with different messages; the broader cohort, not that anecdote, carried the finding ([story](https://themarkup.org/election-2020/2020/10/29/facebook-political-ad-targeting-algorithm-prices-trump-biden)).
- **Finding type(s)**: **algorithmic price disparity** (new tag: a platform's allocation/auction system produces systematically different effective prices between comparable political actors); **range-disclosure reconstruction** (new tag: a hidden metric is estimated from regulator/platform-published bins rather than exact values).
- **Evidence & sources**:
  - **Closed-company transparency API, publicly accessible — Meta Ad Library API**: ad creative, payer/page, dates, state delivery shares, spend ranges, and impression ranges.
  - **Third-party structured mirror — NYU Ad Observatory database**: normalized Meta records and page ownership tables supplied to The Markup.
  - **Public electoral classification — Cook Political Report**: “Lean” and “Toss Up” states defined the swing-state set as of Sept. 29.
  - **Derived measures — midpoint CPM and geographic concentration**: spend-range midpoint divided by impression-range midpoint, multiplied by 1,000; an ad was “swing state” when at least 60% of spend landed there, 1.5 times those states' population share.
  - **Interviews and right of reply — campaign strategists, election lawyers, and Facebook**: established market context and bounded causal interpretation.
- **INPUT DEPENDENCY**: **(a) open-record-runnable.** The decisive fields originated in Meta's public political-ad archive, and the transformations are published. **Instrument path today:** runnable, with friction. Meta says political/issue ads remain searchable for seven years and its 2026 election notice says the archive contains more than 18 million U.S. entries ([Help Center](https://www.facebook.com/help/259468828226154), [2026 notice](https://about.fb.com/news/2026/02/meta-prepares-for-2026-us-midterms/amp/)). The 2020 records therefore remain within the seven-year window in July 2026 but will begin aging out in 2027. Identity/developer access and a fresh ingestion layer are required.
- **Detection signature**: **binned-price geographic cohort audit** — Meta spend/impression ranges **joined to** candidate page ownership and state delivery shares **on ad archive ID**, then compared by candidate × week × swing-state concentration, revealed a time-varying CPM disparity that aggregate campaign spend concealed.
- **Corroboration structure**: cohort averages; temporal stratification; a sensitivity check on excluded one-million-plus-impression ads; paired audience examples; and Facebook's response, which disputed the interpretation but not the reported calculations.
- **Methodology notes**: Dedicated [Show Your Work](https://themarkup.org/show-your-work/2020/10/29/how-we-analyzed-the-cost-of-trumps-and-bidens-campaign-ads-on-facebook); first-party repository [`the-markup/investigation-fb-ads-biden-trump-pricing`](https://github.com/the-markup/investigation-fb-ads-biden-trump-pricing). The repository releases one preprocessing/analysis notebook, but **not** the underlying NYU PostgreSQL database; the notebook expects a `DATABASE_URL` and NYU-specific tables. The detector is therefore **not re-runnable from the released artifacts alone**. An outside investigator must re-ingest Ad Library data and recreate the schema.
- **Official response/outcome**: Facebook said auctions were fair and prices reflected targeting and bid strategy; it did not dispute the calculations. No policy change attributable to the story was identified in the article ([story](https://themarkup.org/election-2020/2020/10/29/facebook-political-ad-targeting-algorithm-prices-trump-biden)).
- **Generalization**: Use wherever a marketplace discloses ranges but hides exact transaction prices: procurement bid bands, insurance quotes, marketplace placement fees, app-store auctions. Build midpoint and boundary sensitivity estimates, segment by comparable cohorts and time, and report what unobserved targeting or quality variables prevent causal attribution.

---

### Gig-Worker-Based Tech Companies Are Throwing Everything at a California Election (2020) — a nearly $200 million campaign turned worker and customer apps into political channels

- **URL**: [The Markup, Oct. 30, 2020](https://themarkup.org/election-2020/2020/10/30/prop-22-california-gig-workers-uber-lyft-doordash-instacart)
- **Partner/awards**: The Markup original; no reporting partner or project-specific award identified.
- **What they found**:
  - Uber, Lyft, DoorDash, and Instacart had put **nearly $200 million** behind Proposition 22 versus about **$16 million** for opponents, making it California's costliest ballot initiative at the time ([story](https://themarkup.org/election-2020/2020/10/30/prop-22-california-gig-workers-uber-lyft-doordash-instacart)).
  - A San Francisco lawsuit alleged Uber pressured drivers to submit supportive videos/statements and answer preference surveys in the company's favored way. A judge denied a temporary restraining order because retaliation had not been shown; the allegation was not presented as adjudicated fact ([story](https://themarkup.org/election-2020/2020/10/30/prop-22-california-gig-workers-uber-lyft-doordash-instacart)).
  - Anonymous Uber, Lyft, and Postmates drivers supplied screenshots of pro-22 messages delivered while working; DoorDash distributed campaign-branded delivery bags, and Instacart encouraged campaign stickers in orders ([story](https://themarkup.org/election-2020/2020/10/30/prop-22-california-gig-workers-uber-lyft-doordash-instacart)).
  - Customers received texts, email, mandatory-looking confirmation prompts, and persistent banners. One message reached an Uber user in Ireland who had not been in California since 2018, revealing how an operational customer channel became a political distribution system ([story](https://themarkup.org/election-2020/2020/10/30/prop-22-california-gig-workers-uber-lyft-doordash-instacart)).
- **Finding type(s)**: **captive-channel electioneering** (new tag: an organization uses a work/service interface that its audience cannot easily avoid to deliver political advocacy); **spending-power asymmetry** (new tag: one side's funding overwhelms the opposition and finances distribution unavailable on equal terms).
- **Evidence & sources**:
  - **Public campaign-finance records — California disclosures**: cash and in-kind contributions established spending scale and treated some company communications as reportable campaign support.
  - **Constructed distributed collection — worker/customer screenshots**: affected users documented transient in-app messages, push notifications, texts, email, and banners.
  - **Litigation records — San Francisco Superior Court filing and ruling**: supplied coercion allegations, Uber's denial, and the court's refusal to issue a temporary restraining order.
  - **Company policies — Uber and DoorDash privacy terms**: showed the contractual language companies invoked for election and promotional communications.
  - **Interviews and prior reporting — drivers, customers, employment/election/privacy lawyers, Eater, CNN, and KQED**: triangulated the tactics across apps and participant roles.
- **INPUT DEPENDENCY**: **(a) open-record-runnable**, treating the participant screenshot network as a rebuildable constructed instrument. Campaign filings, court records, and policy text remain public, and the California Secretary of State still exposes contribution and independent-expenditure data through [Power Search](https://powersearch.sos.ca.gov/) and CAL-ACCESS. **Instrument path today:** **degraded for the historical event**. The 2020 in-app messages were ephemeral and The Markup released no raw screenshot set or participant protocol; the detector remains prospectively runnable only by recruiting current workers/customers during a live campaign and capturing messages contemporaneously.
- **Detection signature**: **campaign-ledger-to-captive-channel reconstruction** — cash/in-kind campaign disclosures **joined to** worker/customer app receipts and court allegations **on sponsor + campaign + date** revealed that the firms' political spending included privileged distribution through labor and service interfaces.
- **Corroboration structure**: official finance records established scale; multiple independent users on several apps established channel recurrence; the lawsuit supplied a sworn allegation while the ruling and company denials bounded it; privacy and campaign-finance lawyers tested legality separately from ethics.
- **Methodology notes**: No Show Your Work page or GitHub repository. **[Inferred]** The reporting instrument was a distributed call for evidence from users and workers, followed by record linkage to filings, court papers, and privacy policies. The decisive detector is **not re-runnable from released artifacts alone** because neither screenshots nor collection instructions were published.
- **Official response/outcome**: Proposition 22 passed with **58%** after total campaign spending reached about **$205 million**; The Markup's follow-up reported companies preparing to export the model beyond California ([follow-up](https://themarkup.org/news/2020/12/01/prop-22-lyft-uber-gig-workers-battle)).
- **Generalization**: Audit employers, utilities, schools, platforms, banks, landlords, and membership bodies that can inject advocacy into compulsory or high-switching-cost channels. Minimum detector: campaign-disclosure ledger + timestamped interface captures + audience role + message frequency + sponsor policy terms.

---

### Where You Live in the United States Could Radically Change How You Vote (2020) — county inventories showed uneven adoption of auditable paper systems

- **URL**: [The Markup, Nov. 3, 2020](https://themarkup.org/election-2020/2020/11/03/voting-machines-security-progress-by-states)
- **Partner/awards**: The Markup original. **Data source, not co-publisher:** Verified Voting.
- **What they found**:
  - **Twenty-seven states** used hand-marked paper ballots in every county, along with Washington, D.C.; **17 more states** had at least one county using them. The physical record makes an independent audit possible ([story](https://themarkup.org/election-2020/2020/11/03/voting-machines-security-progress-by-states)).
  - Utah moved from direct-recording electronic machines in every county in 2012 to paper-based systems in most counties by 2020, but populous Salt Lake County remained an exception ([story](https://themarkup.org/election-2020/2020/11/03/voting-machines-security-progress-by-states)).
  - Louisiana still relied on paperless direct-recording electronic systems after Georgia and South Carolina upgraded; a procurement challenge delayed Louisiana's planned replacement ([story](https://themarkup.org/election-2020/2020/11/03/voting-machines-security-progress-by-states)).
  - Neighboring Texas counties illustrated local fragmentation: Bosque used hand-marked paper, Erath used ballot-marking devices, and McLennan used paperless DREs ([story](https://themarkup.org/election-2020/2020/11/03/voting-machines-security-progress-by-states)).
- **Finding type(s)**: **jurisdictional security patchwork** (new tag: materially different safeguards depend on local geography inside one legal system); **modernization lag** (new tag: a high-stakes asset remains on a weaker generation after peers replace it).
- **Evidence & sources**:
  - **Public structured inventory — Verified Voting county equipment data**: voting method and machine type by county for 2012 and 2020; territories were explicitly missing.
  - **Derived graphics — state/county maps and before-after views**: normalized equipment into hand-marked paper, ballot-marking device, and paperless DRE categories.
  - **Procurement reporting — Louisiana bidding challenge**: explained why a detected lag persisted.
  - **Expert interview — Verified Voting**: supplied the security interpretation and caveat that paper trails enable, but do not themselves perform, an audit.
- **INPUT DEPENDENCY**: **(a) open-record-runnable.** Verified Voting made the decisive county inventory public. **Instrument path today:** runnable. Its live [Verifier](https://verifiedvoting.org/verifier/) and [Voting Equipment Database](https://verifiedvoting.org/equipmentdb/) remained available in July 2026, although an outside investigator must preserve snapshots because current inventory can change and The Markup did not release its 2012/2020 extract.
- **Detection signature**: **county-inventory temporal and adjacency diff** — Verified Voting equipment records for 2012 **compared to** 2020 **on state + county**, then neighboring counties compared on shared borders, revealed both modernization trajectories and local security discontinuities.
- **Corroboration structure**: a single specialist inventory carried the quantitative map; specific states/counties served as inspectable examples; procurement reporting explained one lag; an expert supplied the threat model. This is strong for configuration, weaker for actual failure or tampering incidence.
- **Methodology notes**: No Show Your Work page, first-party data package, or GitHub repository. **[Inferred]** The article's graphics and source labels show a two-year equipment-inventory diff followed by selected county/state case studies. The detector is **not re-runnable from released artifacts alone**; the historical source snapshots and transformation code were not published.
- **Official response/outcome**: No government response or change attributable to the article was identified; it documented the 2020 configuration on Election Day.
- **Generalization**: Use for any decentralized infrastructure—hospital devices, police body-camera vendors, school filters, water treatment, dispatch systems. Compare asset inventories over time, classify safeguards, map adjacent-jurisdiction discontinuities, and flag locations that fail to upgrade after demographically or fiscally comparable peers do.

---

### How Tech Companies' Election Promises Have Held Up (2020) — a promise-to-event audit found broad labels but delayed and inconsistent post-level enforcement

- **URL**: [The Markup, Nov. 5, 2020](https://themarkup.org/election-2020/2020/11/05/tech-platforms-election-moderation-promises-twitter-facebook-youtube)
- **Partner/awards**: The Markup original; no reporting partner or project-specific award identified.
- **What they found**:
  - Twitter, Facebook/Instagram, and YouTube deployed promised site-wide notices that counting continued; Facebook also removed a group with more than **300,000 members** after calls for election-related violence ([story](https://themarkup.org/election-2020/2020/11/05/tech-platforms-election-moderation-promises-twitter-facebook-youtube)).
  - Twitter labeled multiple premature or false Trump campaign claims. Facebook, after initially indicating it would label only national victory declarations, reversed course and began labeling premature state-level claims ([story](https://themarkup.org/election-2020/2020/11/05/tech-platforms-election-moderation-promises-twitter-facebook-youtube)).
  - YouTube left up two One America News videos claiming Trump had won, while removing their ads; it said the videos did not meet the narrower threshold for removal ([story](https://themarkup.org/election-2020/2020/11/05/tech-platforms-election-moderation-promises-twitter-facebook-youtube)).
  - An Eric Trump premature Pennsylvania-victory post remained unlabeled for more than **20 minutes** and accumulated about **14,000 retweets**, making action latency—not just final disposition—the decisive harm measure ([story](https://themarkup.org/election-2020/2020/11/05/tech-platforms-election-moderation-promises-twitter-facebook-youtube)).
- **Finding type(s)**: **policy-enforcement gap** (new tag: public rules and observed treatment diverge); **moderation latency** (new tag: enforcement eventually occurs but only after substantial exposure).
- **Evidence & sources**:
  - **Platform rulebooks — Twitter, Facebook, YouTube, and Google policy announcements**: precommitted labels, removals, and election-period ad restrictions.
  - **Closed-platform observation — public posts, labels, groups, videos, and screenshots**: observed treatment of named examples during Nov. 3–5.
  - **Event ground truth — mainstream/AP race-call status**: established whether victory claims were premature at posting time.
  - **Platform statements — Twitter, Facebook/Instagram, and YouTube spokespeople/executives**: explained policy interpretation and midstream change.
  - **Expert interview — content-moderation scholar**: focused the audit on delay and exposure rather than the eventual presence of a label.
- **INPUT DEPENDENCY**: **(d) closed-platform-dependent.** The decisive evidence was ephemeral platform state: when a label appeared, how many retweets accrued first, and whether a group/video remained visible. No complete public event log or released panel exists. **Nearest public substitute:** archived screenshots, public-figure post archives, platform transparency reports, and news captures. They preserve selected examples but lose the denominator of all eligible posts, personalized visibility, exact enforcement timestamps, and deleted content.
- **Detection signature**: **promise-outcome latency audit** — published election rules **joined to** observed posts and enforcement actions **on platform + policy category + timestamp**, then compared with ground-truth race-call time, revealed inconsistent thresholds and large exposure before intervention.
- **Corroboration structure**: platform-authored promises defined the benchmark; screenshots and live observations tested it; race-call status supplied external ground truth; company responses confirmed actions and exceptions. The sample was illustrative, not a platform-wide rate.
- **Methodology notes**: No Show Your Work page, code, dataset, or story repository. **[Inferred]** The method was a manually maintained promise matrix plus event-day observation of high-profile test cases. The detector is **not re-runnable from released artifacts alone**; no timestamped observation log or sampling frame was released.
- **Official response/outcome**: During the observation window, Facebook expanded labels to state-level victory claims, Twitter labeled disputed posts, and YouTube removed ads but not the cited videos. The story does not claim it caused those actions ([story](https://themarkup.org/election-2020/2020/11/05/tech-platforms-election-moderation-promises-twitter-facebook-youtube)).
- **Generalization**: Convert any public commitment into testable cases before a stress event: content policies, disaster-response SLAs, fraud reimbursement promises, safety recalls. Record the first violation time, first intervention time, exposure before intervention, final disposition, and exception rationale.

---

### Targeting Trump Fans, QAnon Ad Slips Through Facebook's Filters (2020) — volunteer browser observations caught a “Cue” alias bypassing both a ban and political-ad disclosure

- **URL**: [The Markup, Nov. 17, 2020](https://themarkup.org/election-2020/2020/11/17/targeting-trump-fans-qanon-ad-slips-through-facebooks-filters)
- **Partner/awards**: The Markup original. **Data partner, not co-publisher:** NYU Ad Observer/Cybersecurity for Democracy.
- **What they found**:
  - After Facebook banned QAnon content and advertising, a “Connect with Cue” ad using Pepe imagery directed users to a page hosting explicit QAnon videos. The Markup found it in volunteer-submitted NYU Ad Observer data ([story](https://themarkup.org/election-2020/2020/11/17/targeting-trump-fans-qanon-ad-slips-through-facebooks-filters)).
  - The Cue page grew from about **8,400 likes on Nov. 5** to more than **10,800 eight days later** before Facebook removed the page and stopped the ad after The Markup flagged it ([story](https://themarkup.org/election-2020/2020/11/17/targeting-trump-fans-qanon-ad-slips-through-facebooks-filters)).
  - The captured targeting panel showed interests including Donald Trump, Eric Trump, the Heritage Foundation, and Rush Limbaugh. Because Facebook had not classified the ad as political, its archive did not disclose the buyer's identity ([story](https://themarkup.org/election-2020/2020/11/17/targeting-trump-fans-qanon-ad-slips-through-facebooks-filters)).
  - The same participant data exposed NRA and anti-lockdown-rally ads targeted to Trump interests during the political-ad moratorium; Facebook also removed those after The Markup's inquiry ([story](https://themarkup.org/election-2020/2020/11/17/targeting-trump-fans-qanon-ad-slips-through-facebooks-filters)).
- **Finding type(s)**: **adversarial alias evasion** (new tag: a prohibited actor uses a trivial lexical/visual substitute to bypass a detector); **political-ad misclassification** (new tag: political intent or targeting is visible in delivery evidence but absent from the platform's disclosure category).
- **Evidence & sources**:
  - **Constructed browser panel — NYU Ad Observer volunteers**: captured ads actually delivered, “Why am I seeing this ad?” targeting attributes, timing, creative, and destination.
  - **Platform artifacts — Cue ad/page/video screenshots and like counts**: established explicit QAnon content behind the euphemistic ad.
  - **Policy timeline — Facebook's August restrictions, Oct. 6 ban, and Nov. 4 ad moratorium**: defined what the observed ad should have triggered.
  - **Direct interview — Cue/Cuetoob co-founder**: acknowledged using “Cue,” avoiding obvious Q symbols, and relying on longer videos that were harder to catch.
  - **Platform response and external expertise — Facebook, QAnon researcher, Media Matters, and Sen. Mark Warner**: confirmed removals and interpreted the evasion.
- **INPUT DEPENDENCY**: **(d) closed-platform-dependent.** Volunteer observations exposed delivery and targeting fields omitted from Facebook's self-classified political archive. **Nearest public substitute:** Meta's Ad Library and vetted research products; these capture ads Meta classifies as political but lose misclassified ads, personalized delivery context, and some targeting attributes. The original path is materially degraded: Meta disabled NYU Ad Observatory accounts/access in 2021 ([NYU account](https://engineering.nyu.edu/news/we-research-misinformation-facebook-it-just-disabled-our-accounts), [Meta account](https://about.fb.com/news/2021/08/research-cannot-be-the-justification-for-compromising-peoples-privacy/)). The [Firefox extension](https://addons.mozilla.org/en-US/firefox/addon/ad-observer/) remains listed but was last updated in November 2022, and the public [daily-summary page](https://adobserver.org/ad-database) exposes no files.
- **Detection signature**: **ban-to-alias delivery mismatch** — Facebook's prohibited-entity terms and ban date **joined to** volunteer-captured ad targeting and destination-page content **on ad + landing page + delivery date** revealed that “Q” → “Cue” evaded both enforcement and disclosure.
- **Corroboration structure**: user-side delivery capture proved the ad ran; destination content proved QAnon substance; policy dates proved nonconformance; the operator described the evasion tactic; Facebook's removals confirmed its own classification after review.
- **Methodology notes**: No Markup Show Your Work page or first-party repo. Third-party source code: [`CybersecurityForDemocracy/social-media-collector`](https://github.com/CybersecurityForDemocracy/social-media-collector). The public code can build a browser collector, but the decisive detector is **not re-runnable from released artifacts alone**: the story-specific volunteer records/back end were not released, and current Facebook DOM/access controls may break the 2022 collector.
- **Official response/outcome**: Facebook removed the Cue page/ad and the two additional undisclosed political ads after The Markup flagged them ([story](https://themarkup.org/election-2020/2020/11/17/targeting-trump-fans-qanon-ad-slips-through-facebooks-filters)).
- **Generalization**: Audit blocklists, sanctions filters, marketplace bans, app-store moderation, and fraud controls for homophones, transliteration, logo-only signaling, redirects, and euphemisms. The minimum detector resolves destination content and ownership rather than trusting the platform's label on the ad or listing.

---

### Could This Mysterious California News Site Influence the 2026 Election? (2026) — weak public traces tied an unattributed “local” outlet to a conservative media network

- **URL**: [The Markup, Jan. 5, 2026](https://themarkup.org/news/2026/01/05/could-this-mysterious-california-news-site-influence-the-2026-election)
- **Partner/awards**: Co-published in the integrated newsroom with **CalMatters** ([parallel CalMatters copy](https://calmatters.org/economy/technology/2026/01/mysterious-website-2026-election/)); no project-specific award identified.
- **What they found**:
  - The California Courier had spent more than **$80,000 since 2021** on Meta ads promoting political/social-issue stories, potentially reaching tens of thousands of users in a week, while its own site disclosed no ownership or funding ([story](https://themarkup.org/news/2026/01/05/could-this-mysterious-california-news-site-influence-the-2026-election)).
  - Almost all articles were unattributed. The few bylines supplied weak identifiers: one writer described himself as a Lincoln Media Foundation content creator; another matched an Orange County Republican strategist; a third listed conservative organizations ([story](https://themarkup.org/news/2026/01/05/could-this-mysterious-california-news-site-influence-the-2026-election)).
  - Lincoln Media Foundation and Courier Facebook pages promoted the same political documentary **one hour apart**; the Courier omitted the foundation tie. Prior ISD research had found other Lincoln Media sites disclosing ownership only deep in privacy policies ([story](https://themarkup.org/news/2026/01/05/could-this-mysterious-california-news-site-influence-the-2026-election), [ISD network report](https://www.isdglobal.org/digital_dispatches/lincoln-media-local-news-influence-operation-attempts-to-shape-public-opinion-ahead-of-the-us-elections/)).
  - The site used the name of an unrelated **67-year-old Armenian diaspora newspaper** whose publisher had not known the new outlet existed, creating local-news credibility through an identity collision ([story](https://themarkup.org/news/2026/01/05/could-this-mysterious-california-news-site-influence-the-2026-election)).
- **Finding type(s)**: **disguised-media provenance** (new tag: an outlet presents as local news while concealing the political organization behind it); **identity collision** (new tag: a new actor adopts an established organization's name or local authority signals).
- **Evidence & sources**:
  - **Platform transparency archive — Meta Ad Library**: sponsor/page, issue/political ad history, spend, and estimated reach.
  - **Open-web content audit — Courier articles, bylines, mission/ownership omissions, and Facebook posts**: exposed attribution gaps and synchronized publication.
  - **Identity resolution — author bios and social profiles**: linked rare named contributors to Lincoln Media and conservative political work.
  - **Nonprofit record — Lincoln Media Foundation Form 990**: established the legal organization and officers ([Nonprofit Explorer/IRS-derived record](https://projects.propublica.org/nonprofits/organizations/863820336)).
  - **Prior independent network research — Institute for Strategic Dialogue**: supplied sibling sites and the privacy-policy ownership fingerprint.
  - **Interviews/right of reply — the legitimate Courier publisher, researchers, and nonresponsive network actors**: tested mistaken identity and provenance.
- **INPUT DEPENDENCY**: **(a) open-record-runnable.** Every decisive link used public ads, web pages, bios, synchronized posts, nonprofit filings, or prior published research. **Instrument path today:** runnable. Meta's political-ad archive remains public with seven-year retention, IRS 990/XML data remain open, and live/archived pages can be crawled. Countermeasure risk is moderate: owners can delete bylines, alter privacy policies, or remove posts, so continuous snapshots and web archives are necessary.
- **Detection signature**: **weak-identifier provenance graph** — an ownership-silent outlet **joined to** author employment traces, synchronized posts, sibling-site privacy-policy language, 990 identity, and ad spend **on names + text fingerprints + timestamps + sponsor pages** revealed the likely Lincoln Media network.
- **Corroboration structure**: no single trace proved ownership. Convergence came from employee self-identification, synchronized distribution, the foundation's own promotion, known sibling patterns, nonprofit identity, and directional ad spending; the article accordingly used “apparent ties,” not definitive beneficial-ownership language.
- **Methodology notes**: No Show Your Work page, code release, dataset, or GitHub repository. **[Inferred]** The in-article trail shows manual ad-library review, content/byline extraction, social-profile resolution, synchronized-post comparison, prior-network matching, and 990 confirmation. The detector is **not re-runnable from released artifacts alone** because the outlet corpus, ad export, and match table were not released.
- **Official response/outcome**: No regulator or platform action was reported. The Lincoln Club, Lincoln Media, Courier, and named writers did not respond to provenance questions at publication ([story](https://themarkup.org/news/2026/01/05/could-this-mysterious-california-news-site-influence-the-2026-election)).
- **Generalization**: Apply to fake trade journals, front nonprofits, reputation-management sites, astroturf associations, and vendor-written “research.” Crawl ownership/contact/privacy/byline text, resolve staff and shared infrastructure, compare synchronized posts, and join ad spend and legal-entity filings. Treat a graph of independent weak links as stronger than one WHOIS or name match.

---

### It Was John Wayne's Political Club. Now It's Spending Millions on Online Influence (2026) — a 990 revenue inflection aligned with a claimed 27-publication battleground-state network

- **URL**: [The Markup, Mar. 9, 2026](https://themarkup.org/election-2026/2026/03/09/it-was-john-waynes-political-club-now-its-spending-millions-on-online-influence)
- **Partner/awards**: Co-published in the integrated newsroom with **CalMatters** ([parallel CalMatters copy](https://calmatters.org/economy/technology/2026/03/old-political-club-is-big-social-influencer/)); no project-specific award identified.
- **What they found**:
  - Lincoln Media Foundation revenue rose from **$414,505 in 2021** to **$3,881,696 in 2024**, almost tenfold; the 2024 filing reported virtually all revenue as contributions ([IRS-derived filings](https://projects.propublica.org/nonprofits/organizations/863820336)).
  - The affiliated Lincoln Club grew from **$1.59 million** in 2021 to **$3.13 million** in 2024—substantial, but much slower than the media foundation ([IRS-derived filings](https://projects.propublica.org/nonprofits/organizations/900734244)).
  - In its own promotional video, the foundation said it operated **27 publications in seven states**, used targeted web ads to reach millions, and focused on what it called the country's most influential **2% of voters** ([story](https://themarkup.org/election-2026/2026/03/09/it-was-john-waynes-political-club-now-its-spending-millions-on-online-influence)).
  - The network's new direct-to-voter media strategy extended a political history that included the Lincoln Club's partial funding of the anti-Hillary Clinton film at issue in *Citizens United* and its role in California's failed Proposition 32 campaign ([story](https://themarkup.org/election-2026/2026/03/09/it-was-john-waynes-political-club-now-its-spending-millions-on-online-influence), [FEC litigation record](https://www.fec.gov/resources/legal-resources/litigation/citizens_united_fec_memo_opp_cu_pi.pdf)).
- **Finding type(s)**: **nonprofit mission migration** (new tag: an established influence organization shifts resources into a different operational vehicle or channel); **revenue inflection** (new tag: an abrupt financial increase signals a change in scale that becomes legible when joined to outputs).
- **Evidence & sources**:
  - **Primary financial records — IRS Form 990 filings, 2021–2024**: revenue, contribution share, expenses, officers, and related-party disclosures for the foundation and club.
  - **First-party promotional artifact — Lincoln Media Foundation video/LinkedIn post**: self-reported network size, geography, targeting strategy, reach, and mission.
  - **Open-web network output — named local-news sites and political content**: connected the funding vehicle to observable publications and distribution.
  - **Prior research — ISD's network mapping and the January Courier investigation**: supplied initial site candidates and ownership fingerprints.
  - **Historical legal/reporting record — FEC filing and archival press**: established the parent club's earlier electoral influence work without treating history as proof of current coordination.
  - **Interviews/right of reply — historians, political scientists, critics, Meta, and nonresponsive foundation/club officials**: contextualized the strategy; Meta said the linked sites did not violate its inauthentic-activity rules.
- **INPUT DEPENDENCY**: **(a) open-record-runnable.** Financial inflection, legal history, network claims, sites, and ads were public. **Instrument path today:** runnable. IRS bulk XML/990 data and the foundation's public artifacts can be collected by any investigator; the 990 stack can reproduce the revenue series. The fragile portion is output attribution: promotional videos and websites can disappear, so preservation at discovery is essential.
- **Detection signature**: **revenue-inflection-to-output join** — annual 990 revenue for the foundation and parent club **compared over time**, then **joined to** first-party claims and a site inventory **on organization + fiscal year + publication brand**, revealed a funded transition from candidate/cause support to direct online influence.
- **Corroboration structure**: IRS records proved the money and growth; the foundation's own video proved its claimed scale and targeting; independent site research verified examples; historical records established continuity of political purpose; Meta's response bounded the claim by saying the sites did not breach its rule.
- **Methodology notes**: No Show Your Work page, code, data package, or GitHub repository. **[Inferred]** The method is a nonprofit longitudinal comparison followed by mission/output validation against promotional media, site observations, prior research, and legal history. The detector is **not re-runnable from released artifacts alone**, though the primary 990s make its core financial finding independently reproducible.
- **Official response/outcome**: Meta said the sites linked to the organization did not violate its inauthentic-activity rules; the club and foundation did not respond to interview requests ([story](https://themarkup.org/election-2026/2026/03/09/it-was-john-waynes-political-club-now-its-spending-millions-on-online-influence)).
- **Generalization**: Monitor nonprofits, trade groups, foundations, and shell companies for revenue/expense inflections; extract mission text, contractors, officers, and related parties; then join the inflection year to new websites, grant recipients, ads, media brands, litigation, and procurement. The same detector catches policy shops becoming ad networks, charities becoming litigation vehicles, and dormant companies becoming acquisition shells.

---

## Cluster Synthesis

### 1. Evidence-source types and frequency

Frequencies count stories using a source type, not documents; one story can occupy several rows.

| Evidence/source type | Stories | Frequency |
|---|---:|---:|
| Interviews, participant accounts, expert interpretation, or right of reply | voter sites; pricing; Prop 22; voting inventory; platform promises; QAnon; Courier; Lincoln Media | **8/8** |
| Platform/site-native artifacts (ads, posts, labels, app screens, policies, videos, or page content) | pricing; Prop 22; platform promises; QAnon; Courier; Lincoln Media | **6/8** |
| Public administrative, financial, litigation, or legal records | voter sites; Prop 22; Courier; Lincoln Media | **4/8** |
| Structured public or public-facing datasets | Meta ads (pricing); Verified Voting; Meta ads + 990 (Courier); 990 (Lincoln Media) | **4/8** |
| Prior independent research or contemporaneous reporting used as a lead/corroborator | voter sites; Prop 22; voting inventory; Courier; Lincoln Media | **5/8** |
| Constructed participant instruments/submissions | Prop 22 screenshot network; NYU Ad Observer panel | **2/8** |
| Dedicated first-party Show Your Work page | Facebook pricing | **1/8** |
| First-party Markup code repository | Facebook pricing | **1/8** |

The cluster's signature is not “election data” in the narrow sense. It is **cross-surface reconstruction**: political influence becomes visible only when platform artifacts are joined to finance/legal records, organizational provenance, or time-bounded promises. Interviews are universal, but in the strongest entries they interpret or bound a documentary detector rather than substitute for one.

### 2. Detection signatures and frequency

Exact story-level signatures each occur once:

| Detection signature | Frequency |
|---|---:|
| `deadline-outage-remedy-reconstruction` | 1 |
| `binned-price-geographic-cohort-audit` | 1 |
| `campaign-ledger-to-captive-channel-reconstruction` | 1 |
| `county-inventory-temporal-and-adjacency-diff` | 1 |
| `promise-outcome-latency-audit` | 1 |
| `ban-to-alias-delivery-mismatch` | 1 |
| `weak-identifier-provenance-graph` | 1 |
| `revenue-inflection-to-output-join` | 1 |

Mechanically, they consolidate into four reusable families:

- **Cross-ledger/entity joins — 5/8**: pricing, captive-channel campaigning, QAnon delivery, Courier provenance, and Lincoln Media all join records generated for different purposes.
- **Temporal diffs or latency measurements — 4/8**: registration failure versus deadline/remedy, equipment 2012→2020, post versus moderation, and 990 2021→2024.
- **Policy/disclosure mismatch audits — 4/8**: ad price transparency, platform election promises, QAnon classification, and hidden media provenance.
- **Geographic segmentation/adjacency — 2/8**: swing-state ad prices and county equipment patchworks.

### 3. Input-dependency profile

| Class | Count | Stories |
|---|---:|---|
| **(a) open-record-runnable** | **5** | Facebook pricing; Prop 22 campaigning; voting equipment; California Courier; Lincoln Media |
| **(b) re-anchoring** | **1** | voter-registration outages |
| **(c) leak-dependent** | **0** | — |
| **(d) closed-platform-dependent** | **2** | election-promise enforcement; QAnon ad evasion |
| **Total** | **8** | |

Among the **five class-(a)** entries:

- **Runnable today: 4** — Facebook pricing (while 2020 ads remain inside Meta's seven-year window, with new ingestion work), voting equipment, California Courier provenance, and Lincoln Media's revenue/output join.
- **Degraded today: 1** — the Prop 22 detector remains prospectively rebuildable, but the 2020 in-app messages are gone and the participant screenshot corpus was not released.

The **class-(b)** voter-site verification path remains public, but the non-public hotline discovery channel and failed-user denominator cannot be reconstructed. The **class-(d)** QAnon path is especially degraded: third-party code survives, but Meta disabled project access, the extension is stale, and no story-specific panel data were released.

### 4. Transferable pattern candidates

#### Pattern candidate A — `Promise-to-Outcome Latency Audit`

- **Mechanics**: convert promises/policies into event predicates; capture every qualifying event, enforcement action, and timestamp; measure violation→intervention lag and exposure before action.
- **Minimum data**: versioned policy text; event/post ID; event time; ground truth; intervention time/type; exposure counter.
- **Recognition cues**: “we label/remove/respond within…,” visible reversals, eventual compliance after high early reach, exceptions invented during the incident.
- **Any-domain use**: safety recalls, bank fraud reimbursement, government emergency response, vendor SLAs, content moderation.

#### Pattern candidate B — `Disguised-Asset Provenance Graph`

- **Mechanics**: start with an ownership-silent site/entity; resolve bylines, staff bios, synchronized posts, privacy/contact text, ad sponsors, legal entities, officers, and funding into a weighted graph.
- **Minimum data**: pages/bylines/timestamps; legal-entity filings; ad/archive records; at least two independent weak identifiers.
- **Recognition cues**: generic local branding, absent masthead, copied name, unattributed articles, near-simultaneous posts, repeated privacy-policy text, staff with undisclosed political employment.
- **Any-domain use**: astroturf groups, fake journals, front charities, vendor-written think tanks, reputation sites.

#### Pattern candidate C — `Range-to-Rate Reconstruction`

- **Mechanics**: transform disclosed spend/outcome bins into midpoint and boundary estimates; exclude or sensitivity-test open-ended bins; compare rates across actor, time, and geography.
- **Minimum data**: entity ID; spend range; output/exposure range; dates; cohort attributes; documented exclusion rules.
- **Recognition cues**: the source publishes “$X–$Y” and “N–M impressions” but no unit price; totals look similar while effective rates may differ.
- **Any-domain use**: ad auctions, insurance, procurement, marketplace fees, grant bands, hospital price ranges.

#### Pattern candidate D — `Revenue-Inflection-to-Output Join`

- **Mechanics**: detect year-over-year financial jumps, then join the inflection window to new brands, sites, grants, vendors, litigation, campaigns, or geographic expansion.
- **Minimum data**: three years of financials; canonical entity/officer IDs; dated output inventory.
- **Recognition cues**: contribution-funded revenue spike, mission-text change, new related-party payments, sudden multi-state footprint, dormant entity becomes operational.
- **Any-domain use**: political influence, nonprofit capture, shell-company activation, litigation campaigns, procurement vehicles.

#### Pattern candidate E — `Deadline-Critical Availability Ledger`

- **Mechanics**: continuously probe public services, align outages with legal deadlines/demand, preserve errors, and join incidents to court/agency remedies and affected-population estimates.
- **Minimum data**: endpoint and workflow probes; status/latency timestamps; deadline calendar; agency/vendor; remedy time; demand proxy.
- **Recognition cues**: repeated deadline-day failures, emergency extensions, “unprecedented traffic,” no failed-user denominator, backup channel that requires more effort.
- **Any-domain use**: voting, benefits, licensing, taxes, school admissions, public-comment portals.

### 5. What this platform can run now, and what is missing

**Runnable with stated holdings now**

- **Revenue-Inflection-to-Output Join — strong.** The 990 stack can reproduce the Lincoln Media financial series; corporate registries, OpenCorporates, GLEIF, OpenSanctions, ICIJ Offshore Leaks, and local OpenAleph can resolve officers, related entities, and cross-border vehicles. CourtListener/RECAP can add litigation, and USASpending/FPDS can reveal public-money relationships.
- **Disguised-Asset Provenance Graph — partial but useful.** Registries, nonprofit filings, sanctions/offshore records, property/deeds, court records, and IP/patent/FAA holdings can establish the legal and asset graph once an outlet or sponsor is seeded. The platform can recognize shared officers, addresses, counterparties, and related-party transactions.
- **Campaign/vendor follow-the-money — partial.** If campaign-finance exports are supplied, the existing entity-resolution and network holdings can connect donors/vendors to companies, nonprofits, property, contracts, litigation, patents, aircraft, and blockchain addresses.

**Missing or not present in the stated holdings**

- A versioned **Meta Ad Library collector** with creative, spend/impression ranges, regional delivery, payer/page ownership, and archival snapshots.
- A lawful, maintained **participant browser panel** or comparable platform research access for personalized ad targeting, misclassified ads, moderation state, and exact intervention latency.
- A **state campaign-finance ingestion layer** for CAL-ACCESS and equivalent systems, including in-kind expenditures and committee/vendor normalization.
- A historical **voting-equipment inventory connector** with county boundaries, equipment classes, paper-trail attributes, and year snapshots.
- A **deadline-aware uptime/workflow monitor** for registration and other public-service sites; simple homepage pings are insufficient because transaction forms can fail behind a healthy landing page.
- A versioned **influence-site crawler** that preserves bylines, privacy/contact text, synchronized posts, ad landing pages, DNS/certificate/hosting history, and text fingerprints.

The platform can therefore run the cluster's strongest financial and legal provenance patterns today, and can enrich any supplied campaign/ad dataset deeply. It cannot independently reproduce the platform-behavior findings without new acquisition instruments, nor the election-infrastructure findings without dedicated voting-equipment and service-availability feeds.
