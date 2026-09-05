# Job 3 Forensics Wave — AGENT A: Financier-Network Mapping (HRT cluster)

**Profile:** hfia | **Thread:** 40 | **Question:** Does a SECOND, larger financier network exist, fronted by HRT Financial LP across 17 microcap issuers?

## Bottom line
**No.** The #1 HFIA cluster by issuer count is a **false positive** for "predatory financier network." HRT Financial LP (CIK 0001475597) is **Hudson River Trading's SEC-registered broker-dealer / HFT market-making affiliate**, not a discount-convertible lender like Pure Capital. Its 17-issuer, 102-filing Section-16 footprint is a **market-microstructure artifact of HFIA extending Section 16 to FPI insiders**: two-sided market-making inventory in ultra-thin micro-float FPIs briefly crosses the 10% line, now triggering Forms 3/4/5. Inverts the naive cluster ranking — still newsworthy (HFIA now sweeps in HFT market makers), but the opposite of a Pure Capital II.

## 1. HRT identity and instrument
- Legal: HRT FINANCIAL LP (formerly HRT FINANCIAL LLC 2011–2020), Delaware, formed 2009-08-10.
- HQ: 3 World Trade Center, 175 Greenwich St, 76th Fl, NYC (Hudson River Trading HQ).
- Regulatory: ACTIVE SEC broker-dealer, FINRA firm #152144, approved 2009-12-18.
- Filing profile (236 filings): 46× 13F-HR, 15× X-17A-5, 8× FOCUSN, 53 Form 3, 111 Form 4.
- Instrument NOT convertible notes/PIPEs/warrants — X-17A-5/FOCUS are broker-dealer filings; no 13G/13D, no resale registrations. "10%" = open-market market-making inventory (Clearmind Form 4 leaves 81,353 sh = ~10% only because float is tiny post-1:400 reverse split).

## 2. The 17-issuer pattern — market-making, not a network
All 17 verified bona fide FPIs (20-F + 6-K each). Decisive:
- Two-sided churn at every issuer (buys P AND sells S, often adjacent days: Hub Cyber P 5/14→S 5/15; WORK Medical 10 buys/5 sells). A death-spiral financier accumulates then dumps one-way.
- Always indirect (form D), always exactly "10% Owner," never director/officer; bare Form 4s, no footnotes/disclaimer.
- No thematic coherence — 9 unrelated jurisdictions/sectors (vs Pure Capital's coherent Israeli-microcap chain).
- Timing: first Section-16 form 2026-03-23, five days after HFIA; all 102 filings post-Act.

## 3. Weiss-cluster crossover (Clearmind Medicine, CIK 0001892500)
OPPOSITE Section-16 postures at the same issuer: L.I.A. Pure Capital (Kfir Silberman, entity #5344) finances Clearmind via $7.55M discounted convertibles (#13434) using a 9.99% conversion cap to stay UNDER 10% (#13555) — files no Section-16 forms, invisible in the 10%-owner universe. HRT (market maker) crosses 10% and files Form 3 + 4 Form 4s (6/12–6/18). The beneficial-ownership count captures the market maker but NOT the actual predatory financier — a sharp, publishable contrast.

## 4. Other serial / fund-like owners
Serial 10% owners (≥2 issuers) — HRT is the ONLY fund: HRT (17); others are individuals — Cerrone Gabriele M (2), Elsztain Eduardo S (2), Zhao Jie (2), Lin Frank Hurst (2). No second Pure-Capital-shaped serial financier in the 10%-owner data. Only same-type entity is another market maker: Jane Street Group LLC crossed 10% at HiTek Global (China FPI) — single-issuer, corroborating the phenomenon.
Single-issuer institutional owners (present, not serial): Opaleye (Sol-Gel), Saba Capital (Vertical Aerospace), Perceptive, Cormorant, Liberty Strategic/Liberty 77 (Satellogic; Mnuchin), SoftBank, QVT, M13, MVM, JS&W Group, Kandal M Venture, Garden City Private Capital, STM Partners. (Xiradakis Georgios, 3-issuer Greek shipping → Agent C.)

## 5. Regulatory cross-check
- SEC enforcement: HRT FINANCIAL LP / Hudson River Trading → no actions found (local corpus coverage limit, not a clean-record determination).
- FINRA: firm #152144 ACTIVE/Approved; full disclosure history not retrievable (coverage gap).

## Proposed Leads (NOT written to DB)
1. Quantify HFIA over-inclusion of registered market makers (HRT + Jane Street) as FPI "insiders" — regulatory-analysis, high. Ev #13596/13597/13598/13601.
2. Section-16 evasion via sub-10% conversion caps (Pure Capital 9.99% vs HRT crossing) — financier-structure, high. Ev #13600/13555/13434.
3. Confirm HRT → Hudson River Trading parent from primary filing (Form BD / X-17A-5) — entity-resolution, medium. Ev #13595.
4. Micro-float / reverse-split screen as enabling condition for 10% market-maker crossings — market-microstructure, medium. Ev #13592/13600.
5. Watchlist single-issuer institutional owners for emerging ≥2-issuer clusters — monitoring, low.

## Findings created (hfia, thread 40)
#13592 (identity/confirmed), #13593 (financial/high), #13594 (identity/confirmed), #13595 (relationship/medium), #13596 (financial/medium), #13597 (financial/medium), #13598 (financial/medium), #13599 (negative_result/medium), #13600 (relationship/medium), #13601 (intelligence/medium). Prior-wave #13578 corroborated.
Entities: #5480 HRT Financial LP (enriched); #5506 Hudson River Trading LLC (new); #5506 —parent_of→ #5480 (inference).
