---
agent: investigate-person
target: "Malcolm Scott Macintyre"
skill: investigate-person
status: completed
findings_added: 5
connections_added: 2
entities_registered: 1
leads_spawned: 5
---
# Investigation Report: Malcolm Scott Macintyre

## Key Discoveries

### 1. Confirmed ASA share receipt — with critical disclosure gap
Macintyre received 200,000 CRML shares (~$2M at deal price) under the November 21, 2025 Asset Sale Agreement. His role is **not disclosed** in any SEC filing. The press release and financial statements describe all 2M shares going to "the Seller" (Swiss Commodity Re) — which is facially inaccurate given that 200K went to Macintyre under the same agreement.

### 2. Infrastructure finance executive with no visible commodity background
Macintyre is MD of Capella Capital (Sydney), an elite Australian PPP finance firm acquired by Sojitz Corporation (Japan) for ~AUD 470M in June 2025. His career: ABN AMRO Infrastructure Capital Group (Local MD, 12 years) → Babcock & Brown North America → Capella Capital. No mining, commodity, or copper expertise in his public profile.

### 3. Sojitz acquisition as potential bridge
The Sojitz-Capella deal closed **June 23, 2025** — exactly 5 months before the copper deal (November 21, 2025). Sojitz has a significant Metals, Mineral Resources & Recycling division. This raises the hypothesis that Sojitz's metals network connected Macintyre to CRML or Deayton.

### 4. Deayton-Macintyre Australian shared background
Both Deayton (RMIT/UQ) and Macintyre have Australian CPA/financial backgrounds. Deayton has been in Hong Kong since 1975; Macintyre spent 12 years at ABN AMRO's Australia infrastructure group. Both entered Asian financial networks through different vectors.

### 5. No Form 144 filed as of March 23, 2026
Macintyre has not yet disclosed any intent to sell. The $1.4-1.8M position (at $7-9/share) remains apparently undisposed. However, as a foreign-based non-affiliate, he could sell without Form 144.

## Findings Added
5 findings (#7714–7719)

## Connections Added
2 connections:
- Macintyre ↔ Tony Sage (corporate, weak — via CRML deal)
- Macintyre ↔ Kenneth Deayton (financial, medium — via ASA structure; FK error on Deayton connection, need to retry)

## Entities Registered
- Capella Capital (already existed as ID 1345); MD role registered

## Network Map
- **Macintyre** → Capella Capital (MD) → Sojitz Corporation (owner since June 2025) [Sojitz has metals division]
- **Macintyre** → CRML (200K shares via ASA, Nov 2025) ← Tony Sage (CEO)
- **CRML** ← Swiss Commodity Re (1.8M shares) ← Kenneth Deayton (HKCS Group)
- **Connection pathway between Macintyre and Deayton**: UNKNOWN

## Negative Results
- No public link to Tony Sage, Kenneth Deayton, Jett Capital, Perth mining promoters
- No ASIC enforcement history
- No US court cases
- No ABR personal ABN
- No LMSBAND/DOJ/LittleSis/SAM hits

## Sources Checked
| Source | Results | Findings |
|--------|---------|----------|
| SEC EDGAR FULL TEXT | 0 results ("Malcolm Macintyre") | — |
| CRML F-3 (Feb 23, 2026) | Full footnote extracted via curl | #7714 |
| CRML 424B3 (Mar 4, 2026) | Selling shareholder table confirmed | — |
| CRML 6-K (Nov 25, 2025) | Macintyre NOT named | #7717 |
| CRML half-year financials (Mar 13, 2026) | Macintyre NOT named | #7717 |
| Capella Capital website | Full biography | #7715 |
| Web searches (15+) | No direct public links to CRML/Deayton/Sage | #7719 |
| LMSBAND | 0 hits | — |
| DOJ corpus | 0 relevant hits | — |
| LittleSis | 0 results | — |
| SAM.gov bulk | 0 records | — |
| CourtListener | 0 relevant cases | — |
| ABR | No personal ABN under "Malcolm Scott Macintyre" | — |
| GlobeNewswire press release | "European family office" description confirmed false | #7718 |

## Gaps / Follow-up Needed
1. **ASIC personal name search** (paid) → Lead #32389
2. **AFSL/ASIC licensing** — is Macintyre licensed as a financial intermediary for commodity deals?
3. **Sojitz metals division relationship to CRML** → Lead #32393
4. **ABN AMRO HK alumni network** — Deayton-Macintyre overlap period (1997-2009)?
5. **Form 144 monitoring** → Lead #32395
6. **HK Companies Registry** — any Macintyre-controlled HK entities?
7. **The actual ASA text** — not filed publicly, would name Macintyre's precise role

## Leads Spawned
5 leads: #32387, #32389, #32391, #32393, #32395

## Learnings
- **Friction**: SEC EDGAR full-text search returned 0 results for "Malcolm Macintyre" even though he's in the F-3. The text extraction tool truncated table footnotes. Direct HTML fetch via curl was required.
- **Friction**: query_edgar.py `--offset` flag not supported; had to use grep line numbers instead.
- **Surprise**: CRML financial statements (half-year Dec 31, 2025) describe all 2M shares going to "the Seller" — Macintyre's 200K share receipt is entirely absent, even though he's a named recipient in the ASA. This is a material presentation inconsistency worth flagging for article.
- **Methodology**: For foreign private issuers, related-party disclosure requirements differ from US issuers. CRML does not need to disclose Macintyre under Section 16 (exempt as FPI). But the omission from the financial statements is notable under IFRS related-party standards (IAS 24).
- **Source quality**: The GlobeNewswire press release was drafted by CRML/Sage and describes Swiss Commodity RE as "a long-only multi-generational European based single family office." This is a verifiably false claim in an SEC-filed document.
