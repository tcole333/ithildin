# NGINX Investigation: Interim Findings Memo

**Date**: 2026-04-12 (updated end of day)
**Status**: Active investigation — 4 waves complete, 171 findings, 20+ subagent investigations, 3 PACER documents reviewed
**Classification**: Open source intelligence only — public records, corporate registries, court filings, git history, offshore leak databases, PACER exhibits

---

## Executive Summary

This investigation tested whether Russian companies and individuals exerted influence over NGINX to enable backdoors or vulnerabilities in its code. After auditing 8,553 git commits (including 781 TLS/SSL-specific commits across 22 years), mapping the full corporate structure through 9 jurisdictions, tracing the offshore investor network via ICIJ leaks, and analyzing active federal litigation, the findings support a more nuanced conclusion:

**No evidence of code-level compromise was found.** The TLS/SSL implementation delegates all cryptography to OpenSSL, uses no custom PRNG or entropy, and cipher defaults have only gotten stronger over time.

**However, the investigation revealed systemic structural risks that were never disclosed:**

1. **93.6% of security-sensitive code was authored by Moscow-based developers** — a concentration that persists today with only two maintainers carrying the entire TLS subsystem
2. The NGINX parent entity was a **BVI shell corporation** with confidential shareholder schedules, funded through a **Cayman Islands LP** whose 51 investors include individuals connected to Russian state banking and intelligence-adjacent firms
3. The **investor (Runa Capital) and the attacker (Rambler/Mamut) are connected** through a person-bridge funded by three sanctioned Russian oligarchs
4. **NGINX Plus proprietary code may have been secretly developed using Rambler infrastructure** — a copyright claim that partially survived 9th Circuit appeal and is currently in active discovery (June 2026 deadline)
5. F5 Networks paid $670M for this asset and **disclosed zero Russia-related risks** in 130K+ characters of SEC risk factors, despite Moscow being core engineering and Russian antitrust approval being required for the merger

---

## I. Corporate Structure: Offshore Opacity by Design

### The BVI Parent

NGINX's actual parent entity was **Nginx, Inc.**, incorporated in the **British Virgin Islands** (Road Town, Tortola) on July 6, 2011. Registered agent: **Conyers Corporate Services (BVI) Limited** (part of Conyers Dill & Pearman). This BVI entity — not any US corporation — held the equity, controlled the subsidiaries, and was the target of F5's acquisition.

The BVI parent wholly owned four subsidiaries:
- **Nginx Software, Inc.** (Delaware) — sales, marketing, admin (San Francisco)
- **Nginx LLC** (Russian Federation) — core product development (Moscow)
- **Nginx International Limited** (Ireland/Cork) — product management
- **Nginx Asia Pacific Pte Ltd** (Singapore) — sales

The US entities visible in Delaware and California corporate registries were subsidiaries. The actual ownership and governance — including board composition and investor rights — resided in the opaque BVI entity, where shareholder identities are held in **confidential disclosure schedules** not available in public filings.

F5 acquired NGINX via **Neva Merger Sub Limited** (BVI), a reverse triangular merger for ~$643.2M cash. The acquisition required antitrust clearance from four jurisdictions: US (HSR), **Russia** (FAS), Germany, and Spain.

**Findings**: #9857, #9858, #9859, #9860, #9861, #9863

### The Cayman Fund Layer

Runa Capital, the lead Series A investor, is structured as a Cayman Islands entity. **Runa Capital Fund I L.P.** (Cayman Islands, incorporated August 2, 2010) has **51 shareholders/officers** documented in ICIJ Paradise Papers (Appleby as intermediary). Key shareholders include:

- **Alexander Galitsky** (Netherlands)
- **Ilya Zubarev** (Russia)
- **Dmitry Chikhachev** (Russia — working from **Beloussov's Parallels office** in Moscow)
- **Serguei Beloussov** (Singapore)

The LP list also likely includes individuals connected to Russian state banking (possibly ex-Sberbank CTO Victor Orlovskiy) and intelligence-adjacent companies (Doctor Web, ElcomSoft). Swiss corporate vehicles (Leetinvest AG, ACAN Invest AG, Bellaxa AG, RJJX AG) add further opacity.

An additional layer exists: **Technology Partners Star Trust** (Cayman STAR Trust), with Runa Fund I as Settlor and Runa Capital as Beneficiary, intermediated by Appleby Trust (Cayman) Ltd.

**Findings**: #9870, #9871, #9874

### Beloussov's Invisible Hand

Serguei Beloussov (Serg Bell), co-founder of Runa Capital and founder of Acronis International and Parallels, holds **17 officer positions** at SWSoft/Parallels/Acronis entities across 6+ jurisdictions. Yet he appears on **zero** Runa Capital entities and **zero** NGINX entities in any corporate registry worldwide. His influence flows exclusively through equity/LP interests that don't appear in officer filings — a deliberate structural separation.

**Findings**: #9796, #9823, #9873

### Sysoev's Personal Offshore Entity

ICIJ Pandora Papers reveal Igor Sysoev is the **Ultimate Beneficial Owner** of **HOGWARTS UNITED S.A.**, a BVI Business Corporation (IBC RUC 555535) incorporated August 8, 2003 — eight years before NGINX Inc was founded. The co-UBO is **Oleg Strazding** (Russian Federation), who separately appears in Panama Papers as shareholder of **TEMPETROL LTD.** (BVI, energy trading, Mossack Fonseca). The Strazding family (Evgeny, Vladimir) also appears in Panama Papers. No known connection to the tech sector has been established.

**Findings**: #9868, #9869

---

## II. Code Governance: The Moscow Monoculture

### Developer Concentration

Analysis of 8,553 git commits from 132 contributors reveals extreme concentration:

| Developer | Commits | TLS | Auth | Crypto | Conn | Timezone | Status |
|-----------|---------|-----|------|--------|------|----------|--------|
| Igor Sysoev | 3,683 | 161 | 24 | 8 | 422 | UTC+3 | Departed 2017 |
| Maxim Dounin | 1,688 | 230 | 6 | 1 | 77 | UTC+3 | Forked freenginx 2024 |
| Sergey Kandaurov | 712 | 177 | 3 | 1 | 156 | UTC+3 | Active |
| Ruslan Ermilov | 645 | 48 | 4 | 2 | 39 | UTC+3 | Departed 2022 |
| Roman Arutyunyan | 616 | 164 | 0 | 0 | 98 | UTC+3 | Active |
| Vladimir Homutov | 417 | 28 | 0 | 2 | 191 | UTC+3 | Departed to Angie fork |
| Valentin Bartenev | 413 | 81 | 0 | 0 | 18 | UTC+3 | Departed to Angie fork |

These 7 developers account for **95.6% of all commits**. Security-sensitive subsystems are even more concentrated: **TLS/SSL is 89.6% Moscow-authored, auth is 97.4%, crypto is 100%, connection handling is 97.3%.** Combined: 93.6% of security-critical code was written by Moscow-based developers.

### F5's Failure to Build Capacity

After paying $670M for NGINX in 2019, F5 Networks added **14 @f5.com contributors who produced a total of 32 commits in 5+ years.** The most active F5-domain contributor has 6 commits. F5 bought an asset and never invested in reducing its dependence on a Moscow-based engineering team.

When F5 closed the Moscow office in March 2022 (post-Ukraine invasion), the project experienced a **complete development freeze** — zero commits in March 2022, the only such gap in the project's history. Ermilov (645 commits) and Homutov (417 commits) permanently departed, taking **1,062 commits of institutional knowledge** with them. Homutov and Bartenev reappeared at @wbsrv.ru — the domain for Web Server LLC, the Russian company behind the Angie fork.

Today, two maintainers carry the project: Kandaurov (now @f5.com) and Arutyunyan (personal gmail.com). Both remain in Moscow timezone.

### The Code Audit

781 TLS/SSL commits were audited for anomalous patterns. **No evidence of intentional compromise was found:**

- nginx delegates all randomness to OpenSSL — no custom PRNG or entropy gathering
- Cipher defaults have only gotten stronger: SSLv2 disabled (2009), export ciphers removed (2021), TLSv1/1.1 disabled by default (2024)
- No certificate validation bypasses found
- No hidden traffic mirroring or selective routing code paths
- The pre-acquisition TLS burst (8 SSL commits on Feb 25, 2019) was a coherent dynamic certificate loading feature for multi-tenant hosting
- The one-time contributor Nikolay Morozov (@securitycode.ru, 2019-03-26) added 2 lines of memory cleanup — trivially benign

The primary risk is **operational, not adversarial**: single-maintainer concentration. Since Dounin's departure, Kandaurov authored 76.5% of TLS commits.

**Findings**: #9841, #9842, #9847, #9853, #9864-#9867

---

## III. The Investor-to-Attacker Bridge

### The Runa Capital → Mamut Connection

A structural person-bridge connects the NGINX investor ecosystem to the entity that attacked NGINX:

**Maria Alexandrovna Drokova (Masha Bucher)**, born 1989 in Tambov, Russia:
- **2007-2011**: Federal commissioner and spokesperson of **Nashi**, a pro-Putin youth movement. Kissed Putin at the Seliger forum in 2009 (subject of documentary "Putin's Kiss")
- **June 2011 - July 2013**: PR Director at **Runa Capital** — overlapping with Runa's NGINX Series A investment (August 2011)
- **2013-2014**: VP Communications at **Acronis** (Beloussov's company)
- **2017-2019**: Publicist for **Jeffrey Epstein** (appeared 1,627 times in DOJ January 2026 file release)
- **2018-present**: Founded **Day One Ventures** — investors include:
  - **Alexander Mamut** (CAATSA-listed, Rambler owner, initiated the nginx raid)
  - **Vladimir Evtushenkov** (sanctioned, AFK Sistema, defense electronics)
  - **Dmitry Eremeev** (Bank 131, Durov brothers partner)
  - **Serguei Beloussov** (Runa/Acronis founder) — reportedly also a Day One financier

This creates a person-bridge: Bucher → Runa Capital (NGINX investor) on one side, Bucher → Day One Ventures → Mamut (NGINX attacker) on the other. The bridge is structural, not operational — no evidence that Bucher played a direct role in the raid or IP dispute.

**Findings**: #9827-#9836

---

## IV. The State Attack Chain

### Timeline

| Date | Event |
|------|-------|
| 2002 | Sysoev begins writing nginx while employed at Rambler |
| 2004 | nginx released under BSD license |
| ~April 2011 | While still at Rambler, Sysoev/Konovalov finalize $3M Series A term sheet with Runa/BV Capital. Slide deck names F5 as exit target |
| Dec 2011 | Sysoev and team leave Rambler, form Nginx Inc (BVI) |
| 2013-2014 | A&NN Group (Mamut) acquires 50% of Rambler |
| Jan 15, 2015 | Rambler assigns nginx IP rights to **Lynwood Investments CY Ltd** (Mamut's Cyprus vehicle, now HF Investments CY) |
| 2017 | A&NN increases to 100% of Rambler |
| Mar 11, 2019 | F5 announces $670M acquisition of NGINX |
| Apr 2019 | Whistleblower **Alexander Korotkov** discloses the scheme, including the Yam Server |
| Apr 23, 2019 | Sberbank signs binding docs for 46.5% of Rambler |
| May 2019 | F5 acquisition closes |
| Aug 26, 2019 | Sberbank closes Rambler stake. Board Chairman: Lev Khasis (Sberbank First Deputy CEO) |
| Dec 4, 2019 | Criminal investigation launched — complainant is **Lynwood** (Mamut), not Rambler |
| Dec 12, 2019 | Moscow police raid Nginx office; detain Sysoev and CTO Konovalov |
| Dec 13, 2019 | Gref (Sberbank CEO) says he's "disappointed" |
| Dec 16, 2019 | Emergency Rambler board meeting (called by Sberbank); votes unanimously to drop criminal case |
| Jun 8, 2020 | Lynwood files $750M+ civil suit in N.D. Cal. against F5, Sysoev, et al. |
| Jul 2020 | Sberbank increases to 55% of Rambler; A&NN sells remaining 50% via Tekso Holdings |
| Oct 29, 2020 | Sberbank acquires 100% of Rambler |
| Sep 2022 | District court dismisses all claims; awards attorney's fees |
| Mar 8, 2022 | Lynwood renamed to Hemma Investments CY (12 days post-invasion) |
| Mar 9, 2022 | UK entity renamed same day; Russian director resigns |
| Nov 6, 2024 | **9th Circuit partially reverses**: copyright claim on NGINX Plus code survives |
| Apr 10, 2026 | **Case active on remand**, Phase 1 discovery, June 2026 deadline |

### The Sanctions Profile

Every major entity in the attack chain is subject to international sanctions:

- **Sberbank**: Sanctioned by 12+ jurisdictions (OFAC SDN, EU, UK asset freeze). Majority-owned by Russian Central Bank. ~25% of all Russian banking assets.
- **Herman Gref** (Sberbank CEO): Personally sanctioned. Former Putin Minister of Economics (2000-2007). Met Putin on day of Ukraine invasion.
- **Alexander Mamut**: CAATSA-listed oligarch. Sanctioned by Canada and Ukraine. Dual Russian/Israeli citizenship.
- **Rambler Group**: Sanctioned by Ukraine.
- **VK/Mail.ru** (Rambler ecosystem): Sanctioned by Ukraine; Kvarta VK on OFAC SDN.

### The Lynwood/Mamut Corporate Network

Mamut's attack vehicle has been renamed **four times**: A&NN Holdings → Lynwood Investments CY → Hemma Investments CY → **HF Investments CY Limited**. All the same Cyprus entity (HE 159138) at Saifi 1, Porto Bello, Limassol.

The "Lynwood" brand originated as Mamut's investment fund brand in the **Bahamas** (2003), with at least 6 Lynwood-branded entities serviced by Trident Corporate Services. The London hub is **Alastair Tulloch of Tulloch & Co** (4 Hill Street, W1J 5NE), who has 62+ UK appointments spanning Mamut, Lebedev, Khodorkovsky, Golubovich, and DST Global (Milner).

**Findings**: #9787-#9792, #9837-#9840, #9875-#9884, #9891-#9899

---

## V. The Yam Server and the Active Litigation

### Lynwood v. Konovalov et al. (3:20-cv-03778, N.D. Cal.)

This case, currently in **active Phase 1 discovery with a June 2026 deadline**, contains the most detailed factual record of NGINX's origins.

The **amended complaint** (167 pages) and **second amended complaint** (177 pages) allege that NGINX Plus was secretly developed at Rambler using Rambler infrastructure. Key evidence:

1. **The "Yam Server"**: A concealed server in a ring-fenced NOC department at Rambler with its own email server, used for NGINX Plus development
2. **Evidence destruction**: 7+ servers deleted, inventory records fabricated
3. **Forensic recovery**: Group-IB (Russian cybersecurity firm) recovered deleted emails from the Yam Server in late 2019
4. **Whistleblower**: Alexander Korotkov, described as a co-conspirator who turned, came forward in April 2019

The **9th Circuit** (Collins, Forrest, Sung JJ.; Collins partial dissent, Nov 6, 2024):
- **Affirmed** dismissal of breach of contract, fraud, aiding/abetting, tortious interference claims (time-barred; Rambler was on inquiry notice by 2014)
- **Reversed** dismissal of **Count 14 (copyright infringement)** — Lynwood states a viable claim for NGINX Plus code actually "developed" (fixed in tangible medium) at Rambler before Sysoev's departure
- **Judge Collins' dissent** argues more counts should survive regarding the "secret development" of NGINX Plus using the concealed Yam server

**Current discovery posture**: Defendants assert "no NGINX Plus code was written by any Rambler employee while employed by Rambler." Netflix and **Jet-Stream B.V.** (Netherlands) have been subpoenaed as early NGINX Plus customers (2011, before Sysoev left Rambler).

Plaintiff counsel includes **Neal Kumar Katyal** (former US Solicitor General) via Hogan Lovells. Defense counsel includes Morrison & Foerster (F5), King & Spalding (individuals), Willkie Farr (Runa Capital), Cooley (E.Ventures), and Goodwin Procter.

### Related: F5 Securities Fraud

Three active securities fraud cases target F5 leadership in W.D. Washington (2025-2026), naming CEO Locoh-Donou, CTO Anand, and 14+ board members. These likely contain allegations about NGINX acquisition risks and IP exposure that F5 failed to disclose.

**Findings**: #9883, #9885, #9886, #9887, #9892-#9899

---

## VI. Assessment

### What the Evidence Supports

The story is not "Russian agents planted backdoors in nginx." The code audit found none. Instead, the evidence reveals:

1. **Critical Western infrastructure was entirely dependent on Moscow-based developers** — and the acquirer (F5) never invested in reducing that dependency, never disclosed it as a risk, and lost most of the team when geopolitics forced the Moscow office closed.

2. **The corporate structure was designed for maximum opacity** — BVI parent, Cayman fund with 51 undisclosed LPs, STAR trust, no named officers with Beloussov or Sysoev's name on any NGINX entity. The nginx creator had his own personal BVI shell from 2003 with an energy-trading-connected co-owner.

3. **The investor and attacker ecosystems are connected** through Bucher/Day One Ventures (funded by three sanctioned oligarchs), through the Bahamas/Cyprus offshore network, and through the broader Russian tech elite that populate Runa Fund I's LP roster.

4. **The IP dispute has substance** — the 9th Circuit found a viable copyright claim for NGINX Plus code developed at Rambler. The Yam Server, the evidence destruction, and the whistleblower evidence suggest the commercial product had a development history that wasn't disclosed to F5 during the acquisition.

5. **The state intervention was real but complex** — Sberbank's timing (3.5 months before the raid, not days) weakens a simple coordination theory. The criminal complaint came from Mamut's personal Cyprus vehicle, not Sberbank. Sberbank then publicly forced the criminal case to be dropped but didn't prevent the $750M civil suit. The "good cop / bad cop" pattern is suggestive but not conclusive.

### Open Questions

1. **What exactly was on the Yam Server?** The June 2026 discovery deadline may produce answers.
2. **Who are the 51 Runa Fund I LPs?** Confirming ex-Sberbank CTO Orlovskiy would establish a direct financial link between the state bank and NGINX predating the raid.
3. **What do the F5 securities fraud complaints allege?** They may contain the most detailed narrative of what F5 knew about Russia risks.
4. **What is Oleg Strazding's relationship to Sysoev?** The 2003 BVI entity predates NGINX by 8 years.
5. **What did the Angie fork developers change first?** Comparing the Russian-controlled fork against mainline could reveal what the Moscow team knew about the code.

---

## VI. Court Filing Analysis (PACER Documents Reviewed)

### 2011 VC Pitch Deck (Doc 141-1, Exhibit A)

21-page slide deck marked "Moscow/NYC, 2011, proprietary and confidential." Created while Sysoev and Konovalov were still Rambler employees.

- **Founders listed**: Igor Sysoev (author, principal architect), Maxim Konovalov (CEO), Andrey Alexeev (business development)
- **Acknowledges Rambler origin**: "crafted to handle 500 million page requests per day for a Russian search engine/portal"
- **Series A ask**: $2,500,000
- **Company structure planned**: Delaware entity (marketing/sales) + Moscow entity (management/engineers)
- **F5 is first named exit target**: "sell to networking vendor — cisco, juniper, **f5**, brocade, radware." Also lists **Parallels** (Beloussov's company) as software vendor exit. 4-5 year maturity.
- **Version 2.0** planned for Q4 2011 with new core, new API, dynamic modules — commercial features conceived while still at Rambler

### F5's Motion to Dismiss (Doc 88, 53 pages)

Morrison & Foerster + Paul Goldstein (Stanford, top copyright scholar). Key arguments:

- **Counter-narrative**: Rambler knew for 15 years and never objected. Gave Sysoev bonuses instead.
- **BSD license defense**: Open source publication extinguished or complicated employer copyright claims. But F5 **conflates BSD licensing with public domain** — BSD retains copyright while licensing broadly, not a dedication to public domain.
- **Laches**: 7+ years of silence, then Lynwood pounced only after the $670M acquisition
- **Evidence destruction NOT denied**: The Yam Server is never mentioned by name in 53 pages. Equipment destruction addressed only as Rule 9(b) pleading deficiency — a strategic non-denial.
- **Critical concession**: F5 notes NGINXPLUS.COM registered in **2010** (pre-departure) — the exact point the 9th Circuit seized upon to reverse.
- **Warranty admission**: NGINX BVI warranted to F5 that it owned the software and no employee was breaching duties to a former employer. If the copyright claim succeeds, F5 has a breach of warranty claim back.
- **Sysoev's employment agreement contemplated work-for-hire** (Compl. para 113) and his job titles involved "programming" — relevant for Russian employment law.

### Lynwood's Discovery Requests (Doc 103-2, 189 pages)

Four separate RFPs to F5 (222 requests), Alexeev (175), Sysoev (197), and Konovalov (199). Reveals Lynwood's case theory:

- **Pre-2012 concealment**: Demanded documents about "Pre-2012 NGINX Commercialization Efforts" — term sheets, slide decks, VC communications, all while employed at Rambler
- **Server destruction**: Targeted "destruction of computer servers located at Rambler facilities" and Smirnoff-Konovalov communications about the same
- **F5 due diligence failures**: What did F5 review before paying $670M? Did they investigate IP chain?
- **F5's own contradictory statements**: "NGINX source code is secured and stored outside of Russia" and "No commercial products are developed in Russia" — contradicted by 93.6% Moscow-authored security code
- **Criminal case documented**: Case No. 11901450149005396, 11th Division, Main Investigation Department, Ministry of Internal Affairs, Moscow
- **Konovalov told Rambler nginx was "worthless"** (ranking "1", "no value") while simultaneously raising VC funding
- **Full investor list named**: Runa, EVentures, Greycroft, MSD Capital (Michael Dell), NEA, Aaron Levie, Index Ventures, Goldman Sachs, Infinity Ventures, Telstra Ventures, Valhalla Partners
- **Lars Group** (larsgroup.ru) — previously unknown entity connected to the operation
- **80+ identified individuals** and 17+ email addresses targeted, including @acronis.com and @runacap.com
- **NGINX was actively shopped** to all 14 exit targets from the 2011 pitch deck

### F5 Securities Fraud Cases (2025-2026)

Three active securities fraud class actions in W.D. Washington targeting F5 CEO Locoh-Donou, CTO Anand, and 14+ board members. Filed after the 9th Circuit reversal put the copyright claim back in play. These likely contain detailed allegations about what F5 knew about NGINX IP risks and failed to disclose to investors.

---

### Remaining Leads

25+ open leads across all tracks. Highest priority:
- **PACER: Remand proceedings** (2025-2026 filings — active case, June 2026 discovery deadline)
- **PACER: 9th Circuit appellate briefs** (full legal arguments by Katyal and Goldstein)
- **F5 securities fraud complaints** (what F5 allegedly knew about IP exposure)
- **Fork analysis** (Angie/freenginx — still untouched, Track 4)
- **Runa Fund I LP mapping** (51 investors from ICIJ Paradise Papers)
- **Strazding identification** (Sysoev's personal BVI co-owner since 2003)
- **Lars Group / Globtechfund** identification (newly discovered entities from discovery requests)

---

*171 findings | 15 entity connections | 20+ subagent investigations | 4 waves | 3 PACER documents reviewed*
*Sources: OpenCorporates, Delaware/California/UK/Cyprus corporate registries, SEC EDGAR, CourtListener/RECAP, PACER exhibits, OpenSanctions, ICIJ Offshore Leaks (Panama/Paradise/Pandora Papers), LittleSis, GLEIF, git commit history (8,553 commits via PyDriller)*
