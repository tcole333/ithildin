# Elephant Clipping — infrastructure corrective wave

**Cutoff:** September 2, 2026 · **Profile:** `elephant-clipping` · **Method:** five parallel Opus 5 agents (lanes L1–L5), each scope-bounded by an explicit lead; unauthenticated public-source work only; no logins, credential use, private-group joins, identifier enumeration, active scanning, or CAPTCHA solving.

This wave was commissioned to re-run infrastructure work a prior (Codex) pass left unfinished, where it had stopped at obstacles that were *shaped* like ethical boundaries but were actually transient technical failures or denials on the wrong probe. The operating instruction to every lane: **distinguish a genuine ethical boundary (stop) from a transient failure (retry / route around) from a wrong-probe denial (try the right public probe).**

## Bottom line

The corrective premise was correct and is now demonstrated, not asserted. The single clearest example: the prior pass abandoned an archived funnel page on an HTTP 429; that 429 **cleared on one 30-second back-off**, and the recovered page named the operator. Combined with a user-supplied OpenCorporates lead, the wave **resolved the investigation's central keystone** — the previously "unnamed Company" behind ClipIt/Monster Lab.

**Keystone resolved:** the operation's US legal entity is **CLIPIT LLC**, a Wyoming LLC (`us_wy` / `2025-001687393`), organizer **Matiss Tabuns** of **Talsi, Latvia**, registered agent Unlimited Agents LLC, incorporated 2025-05-28 and administratively dissolved (tax) 2026-07-09. A Latvian natural person operating a Wyoming LLC explains every prior dead end: the Latvian *entity* searches were empty because the company is in Wyoming, and Monster Lab's terms could say it "operates in the United States" while naming no one because the entity is a privacy-jurisdiction LLC behind a commercial agent.

Separately and importantly, the wave produced **exculpatory clarity**: the named political beneficiaries advertise through fully-disclosed "Paid for by" channels that are *separate* from the undisclosed organic clipping distribution, and no ad-transparency record links the clipping operation or the coded accounts to them. Transparent paid ads are not evidence the clipping campaign was theirs.

## Per-lane results

### L1 — Firebase / Monster Lab client-surface (lead 95053, completed)
Recovered the full public Firebase config (project `monsterlab-3496`, custom `authDomain monsterlab.io`, GA `G-5HYTNHXBF6` confirmed via a live `webConfig` 200). Resolved the prior pass's abandoned `login.json` (an empty SSR shell — nothing hidden). Established the **right negative** the prior 401 never gave: Firestore *and* Storage both **403 to anonymous callers** (tested via a real object path and the Firestore REST read) — the data plane is genuinely locked, now known by the correct probe rather than the meaningless `buckets.get` 401. The public JS bundle exposes the operation's functional surface: **27 Firestore collections** (incl. `proxyPool`, `discordBots`, `impersonationLogs`, `payout*`, `system_configs`) and **250 API endpoints** incl. `admin/antifraud/clusters`, `admin/impersonation/users`, `admin/crypto-payments/config`, `billing/nowpayments/create-invoice`, a `/books` ledger, and a `myToolbox` proxy/portScan/webrtc-leak suite. Reviewed all 11 `/brand` testimonials (operator handles beyond Serviuos: @Max, @VODEGE, @nakeeb, @Clipit Payouts; second campaign label "AL Clipping"). Findings 15461, 15464–15468. **The browser recorder hit the exact same "no response body" glitch that stopped the prior pass — and this time routed around it with curl.**

### L2 — Ad-transparency libraries (lead 95055, completed)
Defeated the prior plain-HTTP 403 by driving the JS apps logged-out. **Meta Ad Library:** Turning Point USA / Action / PAC, Vivek Ramaswamy, Ben Shapiro (Daily Wire), Steven Crowder (CRTV/Blaze) are disclosed "Paid for by" advertisers; **all 29 coded/political handles are true-negatives** (not advertisers); Tulsi Gabbard, Nick Shirley, Erika Kirk appear only as *subjects* of others' ads. **TikTok CCL:** structural no-US-coverage + political-ad ban; ClipIt/MonsterLab/Serviuos = validated zero. **Google ATC:** beneficiaries are verified advertisers; clipping platforms absent. Key point: the disclosed paid channel is **separate** from the clipping channel; nothing links them. Findings 15473–15478 (15475 supersedes the prior "unobservable" 15443).

### L3 — Resilient archive retrieval (lead 95057, completed) — headline lane
The 429 on `serviuos.com/clipit-mentorship` cleared on one back-off. The recovered ClickFunnels funnel's owner metadata reads **"Matiss Tabuns' Team Workspace"** (slug `JnnKBy`), body self-ID "regular guy from a small town in Latvia," program branded ClipIt / CLIPTOCASH. Monster Lab's archived Terms (Last Updated 2025-09-29) **confirmed from a primary artifact** to name no entity/jurisdiction/VAT (only `contact@monsterlab.io`); a **third payment rail** (ClickFunnels/Rebilly `pk_live_…` publishable key). Correctly characterized the *live* TLS failure as a **genuine dead end** (funnel decommissioned Dec 2025–Jul 2026, now a Netlify cert mismatch) — not everything is retryable, and the lane said so. Findings 15469–15472.

### L4 — Search re-routing (lead 95059, completed)
Re-routed all 8 previously-unissued queries to engines that answer (Startpage/Google gave the strict-operator coverage the challenged engines never did); **no CAPTCHA solved**. First-party `whop.com/clipitnew` confirmed **"Created by SERVIUOS."** **Refuted** the apparent independent copies of the campaign brief (Google snippet-injection artifacts; primary metadata proves the brief only in the one known reel). Identified the DSH source clip but it is now private. Findings 15456, 15458, 15460, 15462, 15463.

### L5 — Discord + subdomain surface (lead 95061, completed)
Mapped the guild's public invite/discovery surface: permanent invite, **41 features incl. `CREATOR_MONETIZABLE_PROVISIONAL` / `ROLE_SUBSCRIPTIONS_ENABLED`**, description names commercial creators (Conor McGregor, Sam & Colby, The Chainsmokers, Chappell Roan). Widget **disabled (403)** — a genuine clean boundary. Subdomains: apex/www = Cloudflare; `books` = Vercel with a Stripe/Google Pay/Firebase-auth CSP; `relay` = self-managed Caddy+Fastify Ubuntu VPS at Linveo AS62564 / 98.142.250.50 (SSH exposed); `api` = NXDOMAIN. Findings 15452–15454, 15457, 15459.

## Corrective-principle scorecard: recoverable vs. caution-was-right

| Prior stop | This wave | Verdict |
|---|---|---|
| `login.json` body abandoned after tool glitch | Reproduced directly — empty SSR shell | **Recoverable** (tool glitch, not a wall) |
| Firebase `buckets.get` 401 read as settling readability | Right probes → Firestore + Storage 403 to anon | **Recoverable** (wrong probe → right probe) |
| Meta Ad Library abandoned at a 403 | Drove the JS app → fully queryable | **Recoverable** (transient bot-block) |
| Wayback 429 on mentorship body | Cleared on one 30s back-off → named the operator | **Recoverable** — highest-value miss |
| 8 search queries left unissued after CAPTCHA | Re-routed to answering engines | **Recoverable** (route around, don't solve) |
| Live `clipit-mentorship` TLS failure | Funnel was actually decommissioned | **Caution was right** — genuine dead end |
| Discord channel roster not obtained | Widget disabled + discovery is an SPA | **Caution was right** — needs a policy call |

The lesson is not "push through everything." Two of the seven were genuine walls, and the agents correctly identified them as such. The failure mode being corrected is *conflating* the transient/wrong-probe cases with the genuine ones.

## Mapping to the hunch hypotheses (#464–471)

- **elephant-platform-keystone (464/465):** Re-scored after CLIPIT LLC. The single principal (Matiss Tabuns) *is* the Serviuos persona, so **#465 (single-operator) now leads (inconsistency 0.00 vs 0.10)**. Refinement: #464's "US-operated company" half was *confirmed* (there is a real Wyoming LLC), but its "principal distinct from Serviuos" half was *refuted*. The @Max/@VODEGE/@nakeeb operator handles are unresolved staff, not evidence of a hidden separate owner. Findings 15479, 15480.
- **elephant-arbitrage-pivot (470/471):** Strengthened. L1's data model bakes in `proxyPool`, `discordBots`, an impersonation/antifraud/IP-cluster admin suite, and a `myToolbox` proxy/portScan/webrtc-leak toolset; L5 dated the proxy-support channel ~9 months ahead of the rules channel. The arbitrage stack is integral to the platform, not adjacent.
- **elephant-budget-theater (468/469):** Ambiguous-to-strengthened. No campaign ledger recoverable (data plane locked); the marketing scale figures ($1.5M+ paid / 20k creators / 2.3B views) remain claims, not a ledger. The `pk_live`/NOWPayments/Stripe rails are real but unquantified.
- **elephant-cpt-production-locus (466/467):** Modestly advanced. The DSH source clip was named but is private; CPT content-hub captures were ordinary. No campaign artifact yet carries a Wynn-side uploader identity — the Atlantic attribution stays uncorroborated.

## Mapping to the original seven gaps

1. Firebase already-fetched bodies → **closed** (read; empty/benign). 2. `buckets.get` wrong probe → **closed** (right probe: locked). 3. Meta Ad Library → **closed** (queried; beneficiaries disclosed, coded accounts negative). 4. Wayback 429 mentorship body → **closed** (recovered; named the operator). 5. Unissued search queries → **closed** (re-routed). 6. Discord public surface → **closed** (mapped; roster needs a policy call). 7. Subdomain banners → **closed** (three-posture split characterized).

## Follow-ups and the one decision for you

**Decision (blocked, yours):** lead **95233** — the ClipIt channel roster / proxy-to-coordination adjacency (what hunch 94998 wanted) is not obtainable passively now that the widget is disabled and discovery is an SPA. Going further needs joining the server or an authenticated Discord read — out of scope without your explicit say-so. Recommended: take the queued passive alternative (web-archive/cache of old channel listings) and leave the join alone.

**Open passive follow-ups:** 95292 (deep Latvian-registry / Lursoft corroboration of Matiss Tabuns), 95293 (`contact@monsterlab.io` + WHOIS pivot), 95294 (cluster the `pk_live` gateway key across other funnels), 95272 (operator handles @VODEGE/@nakeeb + "AL Clipping"), 95289 (recover the now-private DSH #311 via archives), 95236/95239 (relay/api host pivots), 95366/95368 (TikTok CCL API + beneficiary ad-detail drill).

## Data hygiene notes
- Four L4 findings (15458, 15460, 15462, 15463) have a null `thread_id` — minor tagging gap; assign to threads 206/209 on next pass.
- Durable artifacts under `artifacts/2026-09-02/infra-wave/<lane>/` were scanned free of secret keys / session material (the `pk_live`/Firebase `apiKey` are publishable client keys). No agent modified tracked repo code.
- Operational note for future waves: the five lanes shared one Browser pane and contended for tabs; isolate a browser per lane next time.

## Index
**Findings:** 15452–15480 (29). **Leads completed:** 95053/95055/95057/95059/95061. **Follow-ups:** 95233 (blocked-policy), 95236, 95239, 95272, 95289, 95292, 95293, 95294, 95366, 95368. **Hypotheses re-scored:** 464/465. **Artifacts:** `investigations/elephant-clipping/artifacts/2026-09-02/infra-wave/{firebase-surface,ad-transparency,archive-retry,search-rerouting,discord-subdomain}/` (each with a SHA-256 MANIFEST).
