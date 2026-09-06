# L4 corrective search re-routing — coverage table

Cutoff 2026-09-02. Agent agent-L4-search, lead 95059. Labels kept separate per methodology note 2585: **acquired** (engine served a genuine result page), **challenged/blocked** (bot-gate; NOT solved), **unissued** (never sent). "Operators honored?" is a distinct axis: an acquired page may still relax/rewrite the query.

## The 5 shared queries
| Key | Exact query |
|---|---|
| Q1 | `site:instagram.com "ML-" politics` |
| Q2 | `"leaving a high earner with only fifteen percent"` |
| Q3 | `"Elephant Clipping"` |
| Q4 | `"Serviuos" site:drive.google.com` |
| Q5 | `"ClipIt" site:docs.google.com` |

## Engine × query × operators-honored? × result state

| Engine | Q1 | Q2 | Q3 | Q4 | Q5 | Notes |
|---|---|---|---|---|---|---|
| Bing (prior pass) | acquired / operators partial / 2 coded accts | acquired / relaxed / unrelated | acquired / n/a / animal pages | acquired / off-domain / no target | acquired / off-domain / no target | strict-filter coverage not established (prior report) |
| Brave (prior pass) | acquired / operators DROPPED | acquired / operators DROPPED | acquired / 3 (seed) | acquired / **rewrote Serviuos→servicios** | acquired / operators DROPPED | query relaxation throughout |
| DuckDuckGo | unissued | unissued | **challenged** (duck-image) | unissued | unissued | 4 unissued (challenged) |
| Yandex | unissued | unissued | **challenged** (SmartCaptcha) | unissued | unissued | 4 unissued (challenged) |
| **Startpage (L4)** | **acquired / HONORED / 10 → 0 MonsterLab (all CPI-ML collisions)** | **acquired / HONORED / 3 (known Kirk-tax carriers)** | not run | **acquired / HONORED / genuine 0** | **acquired / HONORED / genuine 0** | Google index; PoW auto-cleared; hard-CAPTCHA-blocked once, recovered. Delivered the strict answers the challenged/relaxing engines could not. |
| **Mojeek (L4)** | — | — | — | **blocked (HTTP 403 "automated queries")** | — | network bot-gated; NOT solved |
| **Marginalia (L4)** | empty-by-design (no IG index) | **acquired / HONORED / 0** | rate-limited ("Wait A Moment") | empty-by-design (no Drive index) | empty-by-design (no Docs index) | independent small-web index; rate-limits; no big-platform coverage |
| **WebSearch/Claude (L4)** | acquired / site HONORED, term relaxed / no target | (prior 0) | — | acquired / site HONORED, term relaxed / no target | acquired / site HONORED, term relaxed / no target | allowed_domains enforces site: scope; exact-phrase relaxed |

### The 8 previously-unissued combinations — disposition
`{DuckDuckGo, Yandex} × {Q1, Q2, Q4, Q5}` = 8. All four distinct queries were **re-issued to engines that answer**:
- **Q1** → Startpage (acquired, honored; 0 MonsterLab, CPI-ML collisions) + WebSearch site-scoped (no target).
- **Q2** → Startpage (acquired, honored; 3 known Kirk-tax carriers) + Marginalia (acquired, honored; 0).
- **Q4** → Startpage (acquired, honored; genuine 0) + WebSearch site-scoped (no target). Mojeek blocked.
- **Q5** → Startpage (acquired, honored; genuine 0) + WebSearch site-scoped (no target).

DuckDuckGo and Yandex themselves were **not re-attempted** (known challenge; not solved). No CAPTCHA was solved anywhere.

## Brief-fingerprint queries (hunt a)
| Query | Engine | Operators | Result |
|---|---|---|---|
| `"issues such the economy, foreign policy, public safety"` | Startpage | honored | 2 reels (1 known + 1 refuted artifact) |
| `"issues such the economy…"` | Marginalia | honored | 0 |
| `"issues such the economy… education, and community development"` | WebSearch | relaxed to topical | 7, no verbatim |
| `"The goal is to showcase how modern conservative figures approach"` | Startpage | honored | 5 reels → 4 refuted as index artifacts (finding 15458) |
| `"highlighting commentary…prominent conservative voices"` | WebSearch | relaxed | 7, no verbatim |
| `"create a strong positive narrative…social welfare advocacy"` | WebSearch | relaxed | 8, no verbatim |

## Hunt queries (b legal name, c structure, d DSH)
| Query | Engine | Result |
|---|---|---|
| whop/ClipIt Whop IDs | WebSearch | surfaced whop.com/clipitnew + whop.com/clipit slugs; peer op The Clip Ship; Korean app collision |
| whop.com/clipitnew (store) | browser | **"Created by SERVIUOS"**, 237,377 joined, 4.7/1037 reviews, Location hidden (finding 15460) |
| monsterlab.io/clipit | WebFetch | "$1.5M+ Paid Out", "20,000+ Creators", "2.3B Views", "Paid Every Week"; no legal entity (finding 15463) |
| `"Digital Social Hour" poker Celebrity Poker Tour` (youtube) | WebSearch | **DSH #311 "Celebrity Poker Tournament Live Interviews" (YnzJledYLn0)** |
| DSH #311 watch page | browser | now a **Private video** (finding 15462) |
| `MonsterLab ClipIt "ML-" clipper referral` | WebSearch | monsterlab.io/clipit landing; discord/invite/clipping; no code-scheme doc |
