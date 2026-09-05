# Cohort Extension — Post-HFIA Section 16 Universe (Agent C3)
**Profile:** `hfia` | **Pass date:** 2026-07-15 | **Data:** `datasets/hfia_universe.db` (11,718 post-Act filing-owner rows, 2026-03-18 -> 2026-07-14) + live EDGAR primary documents.
**Findings written:** #13553, #13555, #13557, #13559, #13561, #13562, #13565, #13567, #13569, #13573, #13574, #13576, #13578, #13579, #13582, #13585 (all `--profile hfia`, threads 39/40). **Entities:** #5488-5495 created; roles/relations added to #2541 (Polyrizon), #5350 (Nexera), #5352 (Nexentis), #2531/#2527/#5344/#5349/#2536 (relations). No leads written; no skills invoked; active profile untouched.

---

## 1. Systematic bridge map (Task 1) — finding #13579

Definitive computation (not eyeballed): every owner with a post-Act filing at an in-screen cluster issuer (SciSparc, Clearmind, ParaZero, Maris-Tech, Nexera, Rail Vision), joined to every other issuer where the same owner CIK filed. **Only five owners bridge out:**

| Bridge owner | CIK | Cluster seats (post-Act filings) | Destination outside cluster | Role at destination | Agent |
|---|---|---|---|---|---|
| **Oz Adler** | 1973096 | SciSparc (officer, "CEO and CFO"), Rail Vision (dir), Nexera (dir) | **Polyrizon (PLRZ)** | Director since 2021 — actually **board chairman** (20-F); Form 3 3/18 + Form 4 **sale** 4/1 | 0001213900 (1493152 at RVSN) |
| **Liron Carmel** | 1628325 | Nexera (dir) | **Polyrizon** | Director; Form 3 3/18 + two Form 4 **sales** 3/31, 4/1. Day job: **CEO of Xylo Technologies** (Pure Capital's vehicle) | 0001213900 |
| **Liat Sidi** | 1973248 | SciSparc (dir) | **Polyrizon** | Director; Form 3 only. Also Nexentis director + **Foresight Autonomous accountant since 2016** | 0001213900 |
| **Eliyahu Yoresh** | 1939392 | Rail Vision (dir) | **Foresight Autonomous (FRSX)** | **Chief Financial Officer** — Form 3 2026-03-30. Same Yoresh as Viewbix/QXL chairman (#13419) | 0001493152 |
| HRT Financial LP | 1475597 | Clearmind (10% owner) | 16 unrelated FPIs | Market-maker inventory (see section 4b) | 0001475597 (self) |

Non-bridging cluster rosters captured in full (SciSparc 9 filers, Nexera 10, ParaZero 9, Maris-Tech 8, Rail Vision 11, Clearmind 1). Notables inside the rosters: **Hila Kiron-Revach** (Weiss's Clearmind replacement) has a Form 4 at Rail Vision 6/2/26; **Israel Yakov Berenstein** (Nexera dir) has owner CIK **1826618, sequentially adjacent to Weiss's 1826620** (same-vintage EDGAR registration) and also sits on the Nexentis board ("Israel Berenshtein", proxy 3/12/26); Tali Dinar spans Nexera+ParaZero in-universe (plus CHEV CFO per prior findings).

Out-of-screen cluster issuers (from the C2 gate audit, not re-derived): Viewbix post-Act filers = Weiss/Rosenbloom/Tzedef; Nexentis = only 10%-owner **Lee Eun Young** (late Form 3 period 1/22/26 filed 3/23 + Form 4 sale, agent 0000897069); Gix and CHEV = zero.

**Bottom line:** the cluster's Section 16 perimeter is nearly closed — the only genuine cohort extension the Act surfaced is **Polyrizon**, plus a one-person spur into **Foresight Autonomous** (Yoresh CFO + Sidi accountant = two cluster-adjacent figures at FRSX).

---

## 2. Polyrizon deep-look (Task 2, CIK 1893645, PLRZ)

Nasdaq nanocap (nasal-hydrogel "T&T" platform, pre-revenue, incorporated 2005, Ra'anana IL); IPO 2024-10-30 after a 2.5-year F-1 slog (first F-1 Aug 2022, RW Mar 2024, 12 amendments). **1,608,266 shares outstanding at 12/31/25; 24 holders of record.** Same 0001213900 filing pipeline as the cluster.

### Board = cluster interlock (#13559)
- **Oz Adler — chairman** (director since Sept 2021; "Chairman of our board of directors" in the 20-F; SciSparc CEO/CFO; Jeffs'/Nexera + Rail Vision + Clearmind boards; **ex-CFO of Medigus->Xylo** Dec 2020-Apr 2021).
- **Liron Carmel** — director (Jul 2020-Sep 2024, again since Jan 2025); **CEO of Xylo** since Apr 2019; ex-Gix (TASE) director.
- **Liat Sidi** — director since Oct 2024; SciSparc director since Jun 2020; FRSX accountant since 2016.
- **Asaf Itzhaik** — director since Apr/May 2024; **Clearmind (since 2022), Gix Internet (since 2021), Save Foods (since 2024)**, Rani Zim, Plentify — a previously untracked cohort member (registered).
- Vinokur (insurance agency CEO), CEO Izraeli, CTO Turgeman, CSO Ron, outsourced CFO Ben Yosef (Shimony & Co partner).
- Officers/directors as a group: **1.8%** of shares, overwhelmingly $0-cost RSUs; legacy options struck **$1,018-$1,700** post-split. No 5% holder existed at 3/24/26.

### Financing history 2024-26 (#13557, #13567)
- **Pre-IPO = the cluster financier network:** Xylo/Medigus $80K CLA (Feb 2023) converting at qualified-financing price **minus 20%** with a lowest-price-since-Aug-2021 fallback (converted 5/12/24 -> 88,216 sh); Reuven Srugo Construction $100K on identical terms (-> 110,270 sh); **L.I.A. Pure Capital** CLAs Apr 2024 (<=$250K) and Aug 13 2024 (with Srugo; the filing states both "$60,000" and "$0.60 million" — internal inconsistency), repaid at IPO; $582K of SPAs with Xylo + four Srugos, Xylo paying $60K **in its own ADSs**.
- **The license maneuver (#13553, #13555):** the Aug 13 2024 **SciSparc license** (SCI-160; up to $3.32M milestones + 5% royalties) was paid in equity: 320,000 shares + 364,931 pre-funded warrants + 2,054,793 common warrants. **On 2024-12-30 SciSparc assigned the pre-funded warrants to Pure Capital and 1,541,096 common warrants to Pure Capital + Capitalink (Krasney)** — and Polyrizon filed the resale F-1 for them the same day. That F-1 discloses Pure Capital would have owned **~50.3% of Polyrizon** but for a 9.99% blocker (2,109,548 sh shown). Polyrizon = the **7th documented Pure Capital issuer** and **2nd Capitalink issuer**. What SciSparc received for assigning consideration owed to its own shareholders is not disclosed on the Polyrizon side — prime follow-up (cf. consulting-fee offset Side Letter, #13410).
- **Post-IPO dilution engine (#13567):** IPO 958,903 units @ $4.38 = **1 share + 3 warrants**; Mar 2025 PP ~**$17.0M** (Aegis, **10% commission**) with $1,800-strike Series A warrants + **"alternative cashless exercise option"**; Oct-2024 warrants exchanged into ~3.9M Series-A-form warrants; by 3/24/26 **all had been cashless-exercised into 993,923 shares — 61% of shares outstanding, issued for no cash**; reverse splits 1:250 (5/27/25) + 1:6 (11/28/25) = **1:1500 in six months** (vs Clearmind 1:400, Jeffs' 1:182); Dec 2025 RD $4.97M @ $9.00 (Aegis $250K); **Apr 2026 RD+PIPE $3.5M @ $9.00 — sole investor Armistice Capital (Boyd)**, Aegis 8%+$75K, Form D same day, resale F-1 within 15 days (499,999 sh), EFFECT 5/4. No post-IPO discounted-VWAP note facility here — Polyrizon's engine is Aegis unit/warrant machinery; same outcome-shape as #13405/#13434.
- **13G ledger (#13562):** Pure Capital 13G 12/12/25 = 159,235 sh; **Eli Zamir** (filer CIK 2100427 — **identical to Nexera's CEO owner CIK**) same-day 13G = **exactly 159,235 sh**; Pure Capital -> **0.00** by 13G/A 3/9/26; Zamir -> **0.00** by 13G 3/16/26 — both exits disclosed in the 9 days before the Act date, the insider Form 3 wave, and the late-March insider sales. MMCAP (100,247 sh, 4/21/26) arrived with the Armistice round.

### The March 2026 sequence (#13561) — the HFIA thesis in miniature
Nine insiders' first-ever Form 3s 3/18 -> promotional 6-Ks 3/10 (Eurofins GMP) and 3/17 (global CRO) -> **first reportable events are open-market sales**: 3/30-31 CEO Izraeli 4,400 sh @ $10.90/$11.85 (40% of his exercisable position), CTO Turgeman 2,917 @ $10.90 (50%), chairman Adler 3,292 @ $12.05, Carmel 1,042 @ $11.00-12.36 — ~$133K total -> **RD+PIPE priced 4/7 at $9.00**, i.e., insiders sold 21-37% above the offering price days before announcing dilution. Dollar amounts are small; the structure (fee/control economics, $0-cost grants, sell-into-strength-before-raise) is the cluster pattern with a Section 16 timestamp on it for the first time.

### Related-party web (#13565, #13585)
- **Taurus Transaction (10/24/25):** Polyrizon put **$465,139** into Taurus Gold Corp + **$47,647** secondary via Hike Capital Inc.; "Oz Adler, the Chairman of our board of directors, had a personal interest... by virtue of his personal investment in Taurus." A pre-revenue biotech buying gold-company paper its chairman personally holds.
- **Viewbix purchase (12/30/25-1/12/26):** 82,000 VBIX @ avg $1.52 ($124,640), **after** the 12/15/25 Quantum X exchange agreement was public; CEO Izraeli and CTO Turgeman disclosed personal interests as **Cliniquantum shareholders** (Turgeman is Cliniquantum's CEO; Quantum holds ~48% of Cliniquantum). VBIX later peaked $6.85 post-rebrand (#13419). Corporate cash entering the vehicle whose upside cluster principals held personally.
- **Clearmind development agreement** (MEAI intranasal formulation) — second business contract binding Polyrizon to a cluster issuer whose board its directors share (#13585).
- Srugo family bloc (Raul Srugo + family ~30%+ pre-IPO via SPAs/CLAs/construction co) and E.G. Europe Property (Eyal Gohar, 7.0%) — registered as entities #5489/#5488.

---

## 3. Agent-prefix 0001213900 cohort (Task 3) — finding #13582

**227 issuers** carry the prefix on post-Act ownership filings (it also accounts for 225 of the universe's 839 late Form 3 rows — the heaviest single agent). Neither CIK 1213900 nor 1493152 resolves to any public EDGAR company record — they are pure filer-agent identifiers (per the universe report's caveat, a prefix is not proof of common counsel or coordination).

Cross-issuer owners within the client base (second leg via any agent):

| Pattern | Who | Verdict |
|---|---|---|
| **Weiss cluster** | Weiss 4, Adler 3, Revach 3, Carmel 2, Sidi 2, Dinar 2 | The only genuine multi-officer multi-issuer cohort — and it extends into **Polyrizon** |
| AMTD family | Baudo (3: AMTD IDEA/AMTD Digital/Generation Essentials), Tong (2), Yung (2) | Meets the 2-officers/3-issuers gate but is a **disclosed corporate affiliate group** — not a hidden cohort |
| EZGO + WORK Medical | Robert Brian Johnson + Wu Zhenguo, both directors at both, first-ever Form 3s late May/June 2026 | **Closest structural analog** (2 shared directors) but only 2 issuers |
| Chinese small-cap chain | Zheng (Bitfufu/MaxsMaking/Youlife), Yang (SAIHEAT/ICZOOM/Youlife), Shin (SuperX AI/Globavend/Luda), Li, Cui | 7-issuer chained component, every link a single person — no pair shares >=2 officers |
| STRATASYS/Kornit | Yuval Cohen + Dov Ofer (2 shared independent directors) | Large-cap governance overlap; deprioritize per profile doctrine |

**Answer: no second Weiss-like cohort exists inside the 0001213900 client base.** The Weiss cluster is not one instance of a common service-provider pattern — within this agent's 227-issuer book it is unique. (EZGO/WORK Medical is worth one watch-item lead; see Proposed Leads.)

---

## 4. Targeted nuances (Task 4)

### (a) N2OFF/Nexentis — Weiss role reconciled (#13574, #13573, #13569)
- **Current role pinned from the issuer's own filing:** Weiss signs the 3/12/26 DEF 14A **twice as "Chairman"** — consistent with the ParaZero 20-F bio ("Chairman... since May 2021") and against his own Forms 3/4, which check only Director (#8894). Chairman is a board (not officer) role, so the checkbox is not itself a defect; the record now carries both with the proxy as anchor.
- **Post-Act absence explained:** Nexentis is a domestic registrant (Section 16 always applied). Weiss's last reportable event there is the 2/9/26 grant (Form 4 filed 2/11, #8890); the only post-Act Section 16 activity at the issuer is 10%-owner Lee Eun Young (late Form 3 + a sale). No post-Act Weiss filing does not equal a gap — no evident reportable event.
- **His lifetime EDGAR record quantifies the HFIA asymmetry (#13573):** 16 ownership filings ever; pre-Act, all ten were at his two domestic issuers (Save Foods/N2OFF since period 8/26/2020; Viewbix since 2022) — zero at the six-plus FPIs he chaired, until the 3/18/26 wave. One pre-Act Viewbix Form 4 was ~9 months late (event 6/18/24, filed 3/21/25).
- **New primary fact (#13569):** a **Form 144 at ParaZero, 12/9/24** — proposed sale of 79,866 sh / **$127,785.60** (sale date 12/05/24) — a real pre-HFIA insider sale at a cluster FPI whose only public trace is the Rule 144 notice; no Form 4 existed because Section 16 did not yet reach FPI insiders. Sharpens #13430's "only insider sale" (true only of the Section 16 record) and gives the story a concrete "what you could not see before the Act" exhibit.
- Proxy substance (#13576): shareholders asked to approve **warrants under an amended Pure Capital facility** (the EUR 6M->10M upsizing, #13429), blanket 20%-below-market placements, and a fresh **1:2-1:500 reverse-split framework** engineered around the 2025 Nasdaq one-split-per-year rule (after the 1:35 of 9/3/25). Ownership table: Pure Capital 6.19% (incl. 260K shares held personally by Kfir Silberman), SciSparc 9.60%, and **Dr. Alon Silberman (MitoCareX CEO) 9.32%** — surname coincidence with Kfir, **no relation stated**; do not conflate.

### (b) HRT Financial LP (#13578)
Exact counts: **17 issuers, 102 filing rows, 30 Form 3s / 72 Form 4s** post-Act — the most active Section 16 filer in the FPI microcap universe, always as 10% owner, never director/officer, self-filed (prefix = its own CIK 1475597). At Clearmind, the Form 3 (event 6/10/26) shows the 10% basis: **101,951 common shares held directly** — market-making inventory that crosses 10% only because the 1:400-split, death-spiral-drained float is that small; four Form 4s followed within six days (6/12-6/18, accs 0001475597-26-000080/82/91/92). The paragraph of color: at Clearmind the only entity ever to file Section 16 is a high-frequency market maker holding mechanical inventory, while the economic insiders — including the chairman who signed the F-3 describing the obligation — never filed (#13413/#13414). Compliance at the issuer is inverted relative to economic insidership.

### (c) E.D.B. / G.S.E / Capitalink presence checks
- **Universe DB persons/filings:** no E.D.B. Consulting, G.S.E Economic Consulting, Capitalink, Pure Capital, Xylo, Srugo, or Gohar as reporting owners anywhere post-Act (expected — financiers file 13G/13D, not Forms 3/4/5, unless they cross into Section 16 status; none did).
- **Cluster-issuer filings opened this pass:** **Capitalink appears at Polyrizon** (assignee of part of 1,541,096 SciSparc-license common warrants, 12/30/24 F-1 — #13553); **Pure Capital pervasive at Polyrizon** (CLAs, would-be 50.3%, 13Gs) and at Nexentis (facility warrant proposal, 6.19% + Silberman personal shares — #13576). **E.D.B. and G.S.E: zero appearances** in any document opened this pass (Polyrizon 20-F/F-1s/424B5s/13Gs, Nexentis DEF 14A) — their footprint remains confined to the SciSparc/AutoMax merger file (#13364-13369, #13397).

---

## 5. Proposed leads (NOT written to DB)

1. **SciSparc-side accounting of the warrant assignment** — what did SciSparc receive for assigning 364,931 pre-funded + 1,541,096 common Polyrizon warrants to Pure Capital/Capitalink on 12/30/24? Check SciSparc 2024/2025 20-F related-party notes + the Pure Capital Side Letter offset mechanics (#13410). Category: financial, priority: **high**. Evidence: #13553/#13555.
2. **Polyrizon insider-sales-before-offering timeline** for counsel review (sales 3/30-31 @ $10.90-12.36 -> RD 4/7 @ $9.00; the MNPI question is whether the raise was in negotiation during the sales). Category: legal, priority: high. Evidence: #13561/#13567.
3. **Eli Zamir / Pure Capital paired 159,235-share positions** — origin (Dec 5 RD allocation? warrant exercise?) and disposal path Jan-Mar 2026; Zamir became Nexera CEO while holding/exiting a >5% stake in sibling Polyrizon. Category: person, priority: high. Evidence: #13562.
4. **Cliniquantum / Quantum X / Polyrizon triangle** — Polyrizon corporate cash into VBIX post-deal-signing while CEO/CTO held Cliniquantum personally; cross-check QXL's disclosures of Cliniquantum's cap table for other cluster names. Category: financial, priority: medium. Evidence: #13565, #13419.
5. **Foresight Autonomous (FRSX) spur** — Yoresh CFO (Form 3 3/30/26) + Sidi accountant since 2016; check FRSX financing history and any Pure Capital/Capitalink presence. Category: entity, priority: medium. Evidence: #13579.
6. **Asaf Itzhaik cross-board map** — Clearmind/Gix/Save Foods/Polyrizon/Nexentis/Rani Zim/Plentify; he is the widest previously untracked connector. Category: person, priority: medium. Evidence: #13559, #13576.
7. **Taurus Gold Corp + Hike Capital Inc identity trace** (jurisdiction, principals, Adler's stake size) — Polyrizon put $512,786 of corporate cash into it. Category: entity, priority: medium. Evidence: #13565.
8. **EZGO/WORK Medical watch item** — two shared directors, both first-ever Form 3s filed late (May/June 2026), same agent; check for shared financiers/counsel before any escalation. Category: entity, priority: low. Evidence: #13582.
9. **Pre-Act Form 144 sweep across the cohort** — pull Form 144s for all cohort members' owner CIKs (Adler/Revach/Dinar/Sidi/Carmel/Dayan/Tzedef) to reconstruct pre-HFIA FPI selling the way #13569 did for Weiss. Category: financial, priority: **high** (cheap, high yield). Evidence: #13569, #13573.

## Honest limits
- **Universe scope:** the bridge computation covers only the six in-screen cluster issuers; Viewbix/Nexentis/Gix/CHEV bridges rest on the C2 gate audit (live pulls), not the DB. Owners who sit on cluster boards but never filed post-Act (e.g., at Clearmind) are invisible to this method by construction.
- **Polyrizon coverage:** 20-F read via targeted full-text extraction of governance/related-party/financing/shareholder sections plus MD&A offerings; financial-statement notes, risk factors, and business sections not exhaustively read; F-1 exhibits (CLA texts, license agreement) not opened — terms quoted from filing narratives. The Aug 2024 CLA carries an internal $60K-vs-$0.60M inconsistency in the 20-F itself; both figures recorded, unresolved.
- **13G positions** parsed from XML power fields (share counts); percent-of-class fields were not populated in the XML; event dates not extracted (filed dates used).
- The Zamir role row at entity #5350 cites accession 0001213900-26-031335 in its source field; the correct Nexera Form 3 accession is **0001213900-26-031554** (role substance verified; no role-source correction command exists in the CLI).
- March-2026 PLRZ price catalysts inferred from 6-K cadence; no market-data pull was made (price levels come from the insiders' own Form 4s).
- "No second cohort" (#13582) is bounded by the post-Act window and the >=2-officers/>=3-issuers gate; slower-moving or 13G-layer cohorts would not trip it.
- Two findings summaries rendered with a dropped apostrophe ("companys", "cohorts", "Clearminds") — zsh quote collapse, cosmetic only.
