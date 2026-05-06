# Allbirds / NewBird AI — Forensic Memo

**Prepared**: 2026-04-16
**Subject**: Allbirds, Inc. (NASDAQ: BIRD) — April 15 2026 announcement of $50M senior secured convertible financing, rebrand to "NewBird AI, Inc.", and pivot to GPU-as-a-Service
**Scope**: Structural analysis of the transaction and its counterparty network; identification of disclosure failures and predictive enforcement targets
**Method**: Multi-wave automated forensic investigation (17 worker runs, 190 findings, 138 leads, 87 connections). All sources are primary SEC/FINRA filings, WHOIS records, SEC enforcement releases, and the registered text of the PREM14A (accession 0001193125-26-155866). Hypotheses are labeled; inferences are flagged.

---

## 1. Thesis

Allbirds is not becoming an AI company. It is the 7th confirmed public company to be placed into a standardized "distressed-micro-cap-pivots-to-hot-sector" product operated by **Chardan Capital Markets LLC** as sole placement agent. The investor in the $50M senior secured convertible facility is undisclosed in the public record, but the deal's structural signatures are an 80% match to prior convertibles funded by **ATW Partners LLC**, whose Managing Partner **Kerry Propper** is simultaneously **Executive Chairman of Chardan**. The transaction is engineered to transfer residual shareholder value to the unnamed investor through a death-spiral conversion mechanism, while the "GPU-as-a-Service" narrative serves primarily to inflate the post-announcement stock price to create immediate conversion arbitrage.

## 2. The deal, in one table

| Element | Value | Source |
|---|---|---|
| Issuer | Allbirds, Inc. (CIK 1653909); to be renamed **NewBird AI, Inc.** | PREM14A Annex C (charter amendment) |
| Ticker | BIRD | NASDAQ |
| Facility | Up to **$50,000,000** senior secured convertible notes | PREM14A Proposal 3 |
| Initial draw | $3M at first closing + $2M after Nasdaq approval | PREM14A |
| Remaining tranches | **Solely at Investor's option** | PREM14A |
| OID | 5% | PREM14A |
| Interest | 12% cash / up to 18% on default | PREM14A |
| Maturity | 2 years | PREM14A |
| Primary conversion | 120% of lower of (a) April 14 2026 close = $2.49 → **$2.99**, or (b) closing bid on each tranche day | PREM14A |
| **Alternate conversion** | **93% of lowest VWAP over 10 consecutive trading days** (85% + 25% premium on default) | PREM14A |
| **Floor price** | **None** | PREM14A |
| Beneficial ownership cap | 4.99% (expandable to 9.99% on 61-day notice) | PREM14A |
| Collateral | All assets (including future GPU assets) | PREM14A |
| Investor governance rights | Appoint new COO; 55% participation right on all future financings for 24 months; lease payments to blocked control account for Investor's benefit; approval over GPU purchases and AI infrastructure counterparty selection | PREM14A |
| Placement agent | **Chardan Capital Markets LLC** (mentioned in GlobeNewswire press release **but NOT mentioned anywhere in the 488KB PREM14A**) | Press release 2026-04-15 vs. PREM14A text search |
| Issuer counsel | Holland & Hart LLP (Denver-based) | PREM14A |
| **Investor** | **"an institutional investor (the 'Investor')"** — no name disclosed | PREM14A |
| Missing exhibits | Securities Purchase Agreement, Registration Rights Agreement, Form of Convertible Notes, Support Agreements, Transition Services Agreement — all referenced, none filed | PREM14A |

**One-day stock reaction on PREM14A filing date**:
- April 14 close: $2.49
- April 15 open: $6.82 (+174% gap)
- April 15 intraday high: $24.31
- April 15 close: **$16.99 (+582%)**
- Volume: **285,766,200 shares** (2,788× the Jan–Mar average of ~102K)
- Multiple LULD circuit breaker halts

**Immediate arbitrage created for the Investor on day one**: April 15 alternate conversion price ≈ $2.22 (93% × $2.39 lowest pre-announcement VWAP). Market price $16.99. **>7× immediate gap**, bounded per-conversion by the 4.99% blocker but not bounded in total over time.

**Dilution at full conversion**: At $2.99 primary conversion, $50M = 16.72M new shares; existing shares outstanding ~8.71M; post-conversion dilution to existing holders = **~65.8%**.

## 3. The 16-day blackout

The transaction emerged in a window of structural silence:

| Date | Event |
|---|---|
| 2026-03-29 | Asset Purchase Agreement signed with American Exchange Group (AXNY) for $39M footwear IP sale |
| 2026-03-30 | 8-K publicly announces "asset sale + subsequent dissolution and winding down" — **zero mention of AI pivot, GPU, convertible, or NewBird AI** |
| 2026-03-31 | FY2025 10-K filed with **going-concern** language; $55.1M negative operating cash flow reported |
| 2026-04-08 | **Support agreements** signed — Maveron, Zwillinger, Brown, Boyce — **71% voting power** committed to vote FOR all Special Meeting proposals. **MNPI window opens.** |
| 2026-04-09–14 | BIRD equity volume was **below** Jan–Mar average; no unusual accumulation visible |
| 2026-04-14 | Conversion-price reference day ($2.49 close) — SPA's pricing finalized |
| 2026-04-15 | PREM14A filed; DEFA14A (support agreements) filed; press release issues; AI pivot emerges fully formed |

No Item 1.01 Form 8-K was filed to disclose the signing of the Securities Purchase Agreement itself. The PREM14A contains a 10-page "Background of the Asset Sale" section but has **no corresponding "Background of the Nasdaq Proposal" or "Background of the Convertible Financing" section**. When the AI pivot was conceived, who proposed it, and when the SPA was negotiated are all absent from the public record.

## 4. Counterparty network (primary subject excluded)

### 4.1 The Chardan / ATW hub

The network has a single structural broker: **Kerry Propper**. Graph analysis of the investigation shows his betweenness centrality at **0.5574 — rank #1**, higher than the primary subject itself. Every shortest path between an ATW investor vehicle and a Chardan deal counterparty passes through him.

- **Chardan Capital Markets LLC** — FINRA CRD 120128, SEC CIK 0001170705. Placement agent on every confirmed deal in the cohort. 14 BrokerCheck final disclosures. Address: 1 Pennsylvania Plaza, Ste 4800, NY.
- **Kerry Propper** — FINRA CRD 2916505. Co-Founder, Executive Chairman of Chardan. Co-Founder, Managing Partner of ATW Partners. Individually, clean FINRA record.
- **ATW Partners LLC** / **ATW Partners Opportunities Management LLC** (CIK 0001947975) / **ATW SPAC Management LLC**. Address: 1 Pennsylvania Plaza, **Suite 4810**, NY — **same building as Chardan's Ste 4800**.
- **Serial SPV naming pattern**: ATW Digital Asset Opportunities VI LLC is the confirmed LGHL $600M investor (Schedule 13G filed by Propper as Managing Member). Predicted SPV for BIRD: **ATW Digital Asset Opportunities VII LLC** (hypothesis H3; falsifiable when SPA is filed).

### 4.2 The Chaince / Mercurity satellite

A second, integrated advisory arm operates alongside Chardan:

- **Chaince Digital Holdings Inc.** (NASDAQ: CD; formerly MFH, JMU, Wowo) — a Cayman Islands holding company that has executed **four sector rebrands since 2011**.
- **Chaince Securities LLC** — wholly owned subsidiary; FINRA Continuing Membership Application approved March 2025; immediately took KIDZ as first advisory client (Solana treasury strategy).
- On KIDZ, Chaince was paid 2,000 CD shares for advisory; Chardan was paid 1% of proceeds (~$110K on $11M drawn). "Chaince provides the narrative; Chardan monetizes the placement."
- CD's own stock rose from $2.01 (Jul 2025) to $35.79 (Oct 6 2025) — 17.8× in 2.5 months — then collapsed 87% to ~$4.70 by April 2026. A **Form 144 was filed at the peak** (Oct 15 2025). CD subsequently raised $5.031M via a February 2026 Regulation S placement at $0.774 — **an 87% discount to market**.
- CD is 46.664% owned by "**Apollo Multi-Asset Growth Fund**" — identity, jurisdiction, and beneficial owners **unknown**. Not Apollo Global Management (NYSE: APO).

### 4.3 The Sol\* investor cluster (KIDZ, not BIRD)

Distinct from both ATW and Chaince, but integrated with the deal flow:

- **Solana Growth Ventures LLC** (SGV) — $500M KIDZ note investor; Manager **Steven Oliveira** (Jupiter FL 33477)
- **SOL Collateral Management LLC** — collateral agent; Manager **Steven Oliveira** (same address)
- **Solana Strategic Holdings LLC** (SSH) — $400M KIDZ EPFA (never drawn, terminated 2026-02-28); Managing Member **William R. Samuels** (San Francisco, c/o Cole Frieman & Mallon LLP)
- Oliveira also operates Nemean Asset Management LLC; prior SC 13G filings across biotech SPACs
- **Not ATW-affiliated** per EDGAR analysis — separate operator cluster
- Sol\* appears operationally integrated with Chaince/Chardan deal flow despite separate principals — plausibly introduced through shared intermediaries

### 4.4 American Exchange Group (AXNY) — structurally disconnected

- Acquirer of Allbirds footwear IP for $39M via Delaware SPE "Allbirds IP LLC"
- Genuine operating brand-management company (1400 Broadway, NY; 500+ employees; 30+ brands — Aerosoles, White Mountain, Indie Lee, iTOUCH)
- Founded 2008 by Alen Mamrout; family-operated
- **No overlap with Allbirds board, Chardan, ATW, or Chaince** (confirmed in network analysis)
- AXNY's watches subsidiary (American Exchange Time LLC) went through 3 bankruptcies 2016-2020 — execution red flag but not deal-network-relevant
- AXNY initially declined Jan 22 2026; re-engaged Feb 19; chosen over higher-headline bids primarily for AP assumption (net $15.2M to Allbirds after $23.8M AP assumed)

### 4.5 "Party M" — the uninvestigated alternative

PREM14A Background describes Party M as "**a global footwear and apparel retailer with which the Company previously had engaged in discussions regarding a potential convertible note investment**." Party M submitted a $60M bid on March 4 2026; selected loser on net-comparable basis.

- **Primary hypothesis: Dick's Sporting Goods (post-Foot Locker merger)** — evidence: (a) Allbirds/DKS wholesale partnership since 2022; (b) DKS completed $2.4B Foot Locker acquisition Sept 8 2025; (c) **Ann Freeman resigned Allbirds board Sept 8 2025 (same day) to become Foot Locker NA President**; (d) Allbirds board first discussed "structured convertible note" Sept 18 2025 — 10 days after Freeman's departure; (e) Party M was excluded from TD Cowen's 91-party formal outreach — consistent with Holland & Hart flagging a Freeman conflict.
- **Implication if Party M = DKS**: The "prior convertible discussions" were a **strategic** convertible (healthy retailer taking a stake in a wholesale partner), structurally unrelated to the death-spiral convertible ultimately executed with the undisclosed Chardan/ATW investor. The Board chose the Chardan/ATW path over the strategic path.

## 5. The comparable cohort

Chardan self-reports $2B+ in coordinated distressed-pivot placements 2025-2026. Seven deals are confirmed:

| Issuer | Ticker | Facility | Placement agent | Investor | Pivot narrative | Outcome |
|---|---|---|---|---|---|---|
| Lion Group Holding | LGHL | $600M | Chardan (2% fee) | ATW Digital Asset Opportunities VI LLC | HYPE / SOL / SUI treasury | **-98.7% in 146 days** ($62.92 peak → $0.81) |
| Classover Holdings | KIDZ | $500M | Chardan Capital Markets Inc. (1% fee) | Solana Growth Ventures LLC (Oliveira) | Solana treasury | **-99.7%** from peak |
| Hyperion DeFi (fka Eyenovia) | HYPD | $50M | Chardan | Undisclosed | HYPE token | Pivot active |
| Bit Origin | BTOG | $100M + $400M EPFA | Chardan | ATW Partners LLC | Dogecoin treasury | Pivot active |
| ZOOZ Power / ZOOZ Strategy | ZOOZ | $180M PIPE + $1B ATM | Chardan | ATW Partners LLC | Bitcoin treasury | **Propper dual-role EXPLICITLY DISCLOSED in 6-K (Aug 8 2025)** |
| VivoPower International | VVPR | $121M ATM | Chardan | Various subscription parties | XRP treasury | **VVPR terminated its Chardan ATM 2026-02-02** |
| Allbirds → NewBird AI | BIRD | $50M | Chardan (confirmed via press release only) | **Unnamed** | GPU-as-a-Service | +582% announcement; outcome pending |

**LGHL is the direct template**. ATW drew only $24.4M of its $600M facility (4.1%) — the product is optionality, not principal. Amendment No. 1 (Dec 2025) gave ATW 50% of all crypto staking yields. Volume anomalies (Aug 28, Sept 9 2025) with no public event = ATW conversion dumps through the F-3 resale registration.

## 6. Disclosure failures

### 6.1 The ZOOZ–LGHL disclosure inversion (Aug 2025)

On **August 8, 2025**, ZOOZ's 6-K disclosed explicitly: *"Mr. Propper is also a co-founder and the Executive Chairman of Chardan, which is acting as our placement agent in connection with the Private Placement…"* — establishing the Rule 14a-9 / Section 11 disclosure benchmark.

**Fourteen days later**, on August 22 2025, LGHL filed its F-3 (resale registration statement for ATW's $600M convertible). The F-3 identified Propper only as an ATW Managing Member and **named Chardan zero times**. The F-3/A (Nov 12 2025) and both 424B3 prospectuses (Dec 10–11 2025) maintained this omission. During November-December 2025, ATW was actively converting and reselling shares into the public market under an effective registration statement that did not disclose the principal conflict.

**This is a measurable securities law deficiency, not a drafting choice.** LGHL's counsel had contemporaneous access to the ZOOZ precedent.

### 6.2 The BIRD PREM14A omission (Apr 2026)

A direct text search of the 488,787-character PREM14A returns zero occurrences of: ATW, Propper, Kerry, Chardan, Defender, Digital Asset Opportunities, SPV. The Investor is referred to only as "an institutional investor." No placement agent is identified anywhere in the proxy. The Support Agreement parties, the SPA, and the Registration Rights Agreement are referenced but not filed as exhibits.

If the Investor is ATW (hypothesis H1 at 70–80% confidence), the PREM14A is materially deficient under Rule 14a-9 as of the filing date. If the definitive proxy (DEF 14A) maintains the same omission, it becomes actionable upon effectiveness.

### 6.3 The Propper FINRA de-registration (Sept 2025)

FINRA BrokerCheck shows Propper de-registered as a broker-dealer representative in September 2025 — **one month after** the ZOOZ disclosure benchmark and **one month before** the next Chardan-placed ZOOZ closing (Oct 2025). He retained the Executive Chairman title at Chardan on a non-registered basis. De-registration removes individual FINRA supervisory jurisdiction (Rules 2010, 2040, 3110) while preserving the economic architecture of the dual role. The timing is tight enough to be structural rather than coincidental — hypothesis H2.

### 6.4 The 2026 FINRA "AABA" action against Chardan

OpenSanctions pulled a FINRA enforcement entity `us-finra-chardan-capital-market-llc-aaba-or-the-firm` on **February 5, 2026**. The entity persists in FINRA's source system through April 1 2026. BrokerCheck shows no pending action. FINRA monthly disciplinary publications Jan-Mar 2026 do not mention Chardan. **The action exists but has not yet been made public.**

It emerged three days after **VivoPower terminated its Chardan ATM agreement on February 2 2026**. The correlation is consistent with either (a) Chardan disclosing the investigation to VVPR as part of a termination notice, or (b) VVPR terminating proactively upon learning of the investigation. Absence from the BIRD PREM14A of Chardan's regulatory status is a material-risk-factor omission if the AABA action concerns placement-agent conduct.

## 7. Domain and brand-preparation trail

| Date | Domain | Registrant | Significance |
|---|---|---|---|
| 2025-05-09 | allbirds.ai | Unknown (GoDaddy + Domains By Proxy) | **11 months pre-pivot**; registered by Allbirds or a third party — needs WHOIS verification and Wayback review |
| 2026-01-22 | newbird.ai | NeuBird Inc. (high-confidence defensive registration; both domains updated Jan 27; redirect served from NeuBird AWS EC2) | **Same calendar day as Allbirds Special Committee meeting** where AXNY was noted as having declined |
| 2026-04-15 | newbirdai.com | Privacy-protected (Registrar.eu; dyna-ns.net dynamic DNS) | Registered day-of announcement |

No USPTO trademark application for "NewBird AI" has been filed as of 2026-04-16. There are no AI/ML executives at Allbirds; no GPU procurement agreements; no data-center leases; no colocation contracts; no customers. **Substance score on the operational pivot: 1/10.**

## 8. Insider trading analysis

- Form 4 transactions Sep 2025–Apr 2026: 6 sales, 0 buys, 1 initial RSU grant to new director Lily Yan Hughes (2025-10-31)
- **All sales were sell-to-cover for RSU tax withholding** (`aff10b5One=0` with standardized F1 footnote). Under SEC guidance these are non-discretionary and do not require a 10b5-1 plan.
- CEO Vernachio sold 3,666 (Sep 3), 4,384 (Dec 2), 4,413 (Mar 3) — all coincident with quarterly vesting dates
- Equity volume April 9–14 was **below** the Jan-Mar average. No unusual accumulation visible in lit markets pre-announcement.
- No listed options existed pre-announcement (float too small for OCC eligibility) — options-leak hypothesis structurally inapplicable.
- **This is the structural inverse of the Long Blockchain 2017 pattern**, in which insiders bought before the pivot announcement. Here, if any MNPI-driven profit was taken, it was not through Section 16 insiders via the equity markets. The Investor's SPA position, if taken pre-announcement, would be the obvious channel — and that is where the conversion-price anchoring to April 14 close places the economic upside.
- FINRA ATS (dark pool) weekly data for Apr 8–14 will be published ~April 22 and should be the next monitoring step.

## 9. Predictive model from LGHL template

Based on LGHL, 98.7% decline in 146 days, BIRD holders should expect:

| Horizon | Prediction |
|---|---|
| Week 1 | ~44% retracement from announcement high (LGHL precedent) |
| Month 1 | 40–60% below announcement spike |
| Month 3 | 70–85% below spike |
| Month 5 | >95% below spike; possible reverse stock split to restore $1 minimum bid |
| Month 6–12 | Amendment granting Investor yield-participation rights (50% of staking / GPU rents) — LGHL Amendment No. 1 precedent |

The Investor's economic return does not depend on NewBird AI actually building a GPU business. It depends on the conversion-and-resale spiral operating for 12-24 months. The operational narrative is structurally optional.

## 10. Enforcement target ranking

In order of strict-liability exposure and evidentiary maturity:

1. **LGHL F-3 Section 11 / 12(a)(2) omission** — highest. Strict liability, effective registration, 14 days after the ZOOZ benchmark established materiality, active resale through the omission period. Identifiable parties (LGHL issuer, ATW as selling stockholder, Chardan as placement agent, Propper as dual-role principal).
2. **Chardan Rule 5110 placement-fee reasonableness** (FINRA) — the 2024 $900K SPAC AWC established the enforcement template; applying it to placement-as-investor arrangements extends cleanly. The 2026 AABA action (unpublished) may already target this conduct.
3. **BIRD PREM14A Rule 14a-9** — crystallizes upon effectiveness (DEF 14A). If the Investor is ATW and the dual-role omission is maintained in the definitive proxy, the path to enforcement is direct.
4. **Propper Section 10(b) / 10b-5 personal liability** — harder but not foreclosed by FINRA de-registration. The deliberate timing (Sept 2025) relative to the ZOOZ benchmark would be discoverable in enforcement.
5. **Chardan Rule 2010 / 3110 supervisory failure** — pattern of repeat placement-agent/investor conflicts across 7 deals, with the earliest (CNAQ, Jan 2021) expressly flagged in FINRA Form U4 where Propper self-disclosed "WILL BE AN INVESTOR" in a SPAC Chardan underwrote.

## 11. Open items / monitoring schedule

Investor identity confirmation is the single most valuable outstanding data point. Disclosure vectors, in likely-arrival order:

| Due | Vector | What it reveals |
|---|---|---|
| ~2026-04-17–21 | Post-announcement Form 4 (if any insider traded Apr 15) | Any BIRD insider activity into the spike |
| ~2026-04-22 | FINRA ATS weekly report (Apr 8–14 settlement) | Dark-pool / off-exchange positioning |
| ~2026-04-23–30 | Form D filing for the convertible offering | Total issuer count; offering-level economics; rarely names investor |
| Before 2026-05-18 | DEF 14A definitive proxy | Standard practice would require naming the Investor; if it still does not, escalates the Rule 14a-9 question |
| Upon first closing | Item 1.01 Form 8-K with SPA/RRA/Notes as exhibits | The SPA exhibit will name the Investor entity |
| 30–60 days post-close | S-3 resale registration | Selling Stockholder table names the Investor; discloses full share count |

Supplemental items:
- Unmask the `allbirds.ai` May 2025 registrant via WHOIS + Wayback
- Delaware SOS lookup on "ATW Digital Asset Opportunities VII LLC" and on "Allbirds IP LLC"
- Identity of "Apollo Multi-Asset Growth Fund" (46.664% of Chaince Digital Holdings)
- FINRA U5 termination code for Propper's September 2025 de-registration
- Confirmation that Party M = DKS + Foot Locker via DKS 10-K disclosures for FY2025

## 12. What this investigation establishes vs. what it alleges

**Established by direct primary-source evidence**:
- The deal structure, mechanics, and governance rights are as described.
- Chardan is the placement agent and is not mentioned in the PREM14A.
- Propper holds simultaneous roles at Chardan and ATW and has been the subject of explicit dual-role disclosure at ZOOZ that was omitted from LGHL's registration filings.
- LGHL's F-3 and 424B3 filings omitted the dual-role disclosure while ATW was actively converting and reselling shares.
- LGHL declined ~99% post-announcement.
- The Chardan cohort of 7 distressed-pivot deals follows a common structural template.
- Chaince Securities and Chardan operated simultaneously and integratedly on the KIDZ deal.
- A 2026 FINRA enforcement action against Chardan (AABA) exists in FINRA's source system.
- BIRD insider Form 4 sales were sell-to-cover, not discretionary.

**Inferred with stated confidence, open to falsification**:
- ATW Partners is the BIRD convertible investor — 70–80% (directly falsifiable on SPA filing).
- Propper's September 2025 FINRA de-registration was liability-firewalling, not career transition (inference from timing) — falsifiable by U5 termination code.
- Party M is DKS + Foot Locker (inference from Freeman bridge + timing + commercial relationship) — falsifiable by DKS 10-K or press disclosure.

**Neither established nor alleged**:
- Whether any specific Allbirds officer, director, or advisor breached fiduciary duty by selecting the Chardan/ATW path over the DKS/Foot Locker path.
- Whether any individual trader used material non-public information for personal gain.
- Whether the AI pivot was conceived before or during the 16-day blackout.

The pattern is a hypothesis for structural comparison, not an allegation. The specific individuals SEC-charged in the Long Blockchain matter (Watson, Barret-Lindsay, Giguiere) are not projected onto current BIRD actors. The structural similarity establishes where to look; the evidence itself must be developed for any person-specific claim.

---

## Appendix A — Investigation telemetry

- **17 automated investigation runs** executed via the dispatcher (4 waves)
- **190 findings**, **138 leads**, **87 connections** imported into the investigation database
- **Total API cost**: ~$42
- **Primary sources** queried: SEC EDGAR (CIKs 1653909, 1170705, 1947975, 1820465, 1878495, 1527762, 1806524, 2022308, 1735556, 1992818, 1682639), FINRA BrokerCheck (CRDs 120128, 2916505, 283146, 283737), OpenSanctions us_finra_actions, GoDaddy WHOIS, crt.sh Certificate Transparency, OpenCorporates, Delaware/Florida/NY state registries (partially rate-limited)
- **Active profile**: `allbirds` in `investigations/allbirds/config.yaml`
- **Case notes**: `investigations/allbirds/CLAUDE.md`

## Appendix B — Key evidentiary citations

- PREM14A (full text, 488,787 chars): EDGAR accession 0001193125-26-155866, filed 2026-04-15
- 8-K (Support Agreements only): accession 0001193125-26-155150, event date 2026-04-08
- 8-K (Asset Sale with AXNY APA): accession 0001628280-26-022181, event date 2026-03-29
- 10-K (going concern): accession 0001628280-26-022192, FY ending 2025-12-31
- ZOOZ 6-K (disclosure benchmark): accession 0001641172-25-022793, filed 2025-08-08
- LGHL 6-K ($600M ATW facility): accession 0001213900-25-055423, filed 2025-06-18
- LGHL F-3 (resale registration, omission): accession 0001213900-25-079899, filed 2025-08-22
- LGHL 13G (ATW): accession 0001947975-25-000006, filed 2025-07-09
- KIDZ 8-K (SGV SPA): accession 0001477932-25-004289, filed 2025-06-02
- CD (MFH) 6-K (Solana ELOC): filed 2025-07-21
- Chardan SEC AML action: Release 34-83251 (2018)
- Chardan FINRA SPAC AWC: 2021072554901 (Dec 4 2024, $900K)
- Long Blockchain comparables: SEC Release 2021-121 (charges filed 2021-07-09)
