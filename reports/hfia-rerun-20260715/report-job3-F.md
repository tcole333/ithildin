# Job 3 — Agent F: Section 16 Compliance-Gap Universe (Never-Filers)

**Profile:** hfia | **Thread:** 39. HFIA (eff. 2026-03-18) extended Section 16 (Forms 3/4/5) to FPI directors/officers. Codex flagged 524 issuers with ZERO post-Act Section 16 filings by any insider. This agent re-prioritized by accountability value, verified the top 20 against live EDGAR, and separated genuine gaps from artifacts.

**Bounded-negative discipline:** "No filing found" ≠ "unlawfully failed to file." Legitimate causes exist (not truly FPI; home-country substantially-similar regime relief; no reportable holding; build miss). No finding asserted as confirmed.

## Prioritization
Codex priority_score counted all 424B* including 424B2 structured notes, ranking megabank note programs on top (UBS 92,883; Barclays 66,271) where insider invisibility does NOT matter. Rebuilt score = equity-capital-markets points (F-1/424B4=8; 424B5/F-3=4; EFFECT=2; 424B3=1; 424B2=0) + hype-sector +15 / junior-resource +4 + recency + small-cap venue +4, with structured-note/bank gate ×0.05. The 13 megabank programs fell from Codex ranks 1-8 to F-ranks 321-463. Composition of 524: recent_IPO 64, equity_shelf 144, other_424 6, resale_only 4, no_financing 293, structured_note_program 13.

## Top-20 verification (live EDGAR, EXACT form matching)
Tool artifact neutralized: `query_edgar.py filings --form "3,4,5"` substring-matched a 424B4 as a false "Form 4"; all zero-counts use exact matching.
Result: **20/20 zero exact Forms 3/4/5 since the Act; 20/20 FPI-confirmed (19 file 20-F; Optimi via 424B4+8-A12B); 0/20 file 10-K.** Board sizes 4-7 directors + 2-3 officers ⇒ ≈5-9 Section 16 reporting persons/issuer, none filed an initial Form 3.
Issuers: Optimi Health (Canada), 3 E Network (BVI), TNL Mediagene (Cayman), EPWK (China), One&one Green (China/Cayman), AKANDA (UK cannabis), PHAOS (Singapore), Everbright Digital (HK), Lytus (BVI/India), Ruanyun Edai (China), Top Wealth (HK), U-BX (Cayman), BeLive (Singapore), Bluemount (Cayman fintech), Grande Group (HK fintech), DEFSEC (Canada), Genius Group (Singapore/NYSE), Rich Sparkle (China/Cayman), Oriental Rise (China), Xinxu Copper (Cayman).

## Patterns among genuine gaps
- **(a) Shared filing agents:** 12/20 (60%) via account 0001213900, +3 via 0001493152 = 75% in two small-cap-FPI agents — the SAME agents topping the Act's late-filers (225/125 rows) and the Weiss / L.I.A. Pure Capital (Silberman) cluster. Agent 0001213900 DID file Section 16 for other clients, so non-filing is issuer-specific.
- **(b) Home-regime split:** 218 financed → 151 (69%) offshore (Cayman/BVI/HK/China/Singapore, no home insider regime) vs 57 (26%) Canada (SEDI/NI 55-104, possible relief). Top-20 = 18 offshore / 2 Canada.
- **(c) Post-Act stale exemption boilerplate:** AKANDA (6/9/26), Top Wealth (5/15/26), Bluemount (6/29/26), Optimi (5/20/26) filed AFTER the Act still asserting S16 exemption. AKANDA verbatim: "our officers, directors, and principal shareholders are exempt from the reporting and 'short swing' profit recovery provisions of Section 16."
- **(d) Sector:** software/AI, pharma/biotech/psychedelic, fintech/crypto, EV/battery — retail-hyped.
- **(e) HRT cross-check (validating negative):** 0/17 HRT-financed issuers appear as never-filers — HRT files Form 4 as 10% owner, correctly excluding them.

## Genuine-vs-artifact + extrapolation
Top-20: 20/20 genuine data-level gaps, 0 artifacts. Residual uncertainty is legal (exemption/relief), not data. Extrapolation to 524 (LABELED ESTIMATE): ~13 (2.5%) megabank note programs most artifact-prone; ~207 (40%) Canadian genuine-but-softer (SEDI relief possible); ~285 (54%) offshore sharpest genuine gaps incl. 151 financed-offshore (~29% of 524). Data-artifact rate estimated LOW (~0-5%).

**Regulatory structural gap:** Section 16(a) delinquencies are disclosable under Item 405 — but Item 405 is a domestic 10-K/proxy item; Form 20-F has NO equivalent. No verified-gap 20-F admits delinquency; several affirmatively claim exemption. The ordinary Item 405 self-reporting backstop structurally does not surface these FPI gaps.

## Findings (hfia, thread 39) — 6
#13687 aggregate bounded-negative (synthesis/medium), #13695 top-20 verification (paraphrase/high), #13698 post-Act exemption claims (paraphrase/high), #13713 filing-agent concentration (synthesis/medium), #13714 home-regime split (synthesis/medium), #13715 HRT cross-check negative (synthesis/medium).

## Proposed leads
1. Extend verification to F-ranks 21-60 (financed-offshore tail) to convert estimate to measured count. 2. Identify agents 0001213900 & 0001493152 (real firms + client rosters) and whether they advised on HFIA S16 duties — "who advises the non-compliant"; link Weiss/Pure Capital cluster. 3. Resolve SEC transition-relief / substantially-similar-regime status for Canadian FPIs. 4. Post-Act stale-exemption sweep across all financed never-filers. 5. Active-ATM overlap: never-filers with 424B5/EFFECT after 2026-03-18. 6. Adjudicate the 13 megabank structured-note vehicles.
