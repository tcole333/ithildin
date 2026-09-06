# Ad-transparency sweep — sanitized evidence manifest

**Lane:** Infra corrective wave, Lane 2 (agent-L2-adlib)
**Lead:** #95055
**Profile:** elephant-clipping
**Capture date (UTC):** 2026-09-02
**Method:** public platform ad-transparency tools driven via browser, logged out, no auth, no CAPTCHA solving, no API-key/private-endpoint use. All queries also recorded in `search_log` (sources `meta_ad_library`, `tiktok_ccl`, `google_ads_transparency`).

## Corrective context

Supersedes the abandoned attempt behind finding **15443**, which logged a single plain-HTTP `403 Forbidden`
from `facebook.com/ads/library/` (search_log #13483) and concluded ad-disclosure state was "unobservable."
Driving the real JS app defeats that raw-HTTP bot-block: the tools are reachable and fully queryable.
Findings added this lane: **#15473–#15478**; relation **#15475 supersedes #15443**.

## Files (SHA-256)

| File | SHA-256 | What it captures |
|------|---------|------------------|
| `captures/meta_turningpoint_us_political.txt` | `693da0c635a4a3a8a1abf369921a00ec873ed3d458b06da806c2036b16c8e74f` | Meta Ad Library rendered result for "Turning Point Action" (US, Issues/elections/politics): "Paid for by" disclaimers, spend/impression/date ranges for TPUSA/TP Action/TP PAC |
| `captures/meta_vivek-ramaswamy_us_political.txt` | `4563cef84bf8dd1375243ffb574f7ddff17a808b344d5fd4fbcbad18e53b5eca` | Meta Ad Library rendered result for "Vivek Ramaswamy" (VIVEK 2024; Vivek Ramaswamy and Rob McColley for Ohio) |
| `captures/meta_commentators_us_political.txt` | `8eb8665b42a2522c4d5ce09310871c53f7cc3782cc9cb76651af1fb19dba2c6f` | Meta Ad Library rendered results for Tulsi Gabbard, Ben Shapiro, Steven Crowder, Nick Shirley, Erika Kirk (advertiser-side) |
| `captures/meta_coded-handles_sweep.txt` | `33cc54258ee5d53a13382a80d12dc83a79dfc52b7bfb18afa98629960350e557` | Per-handle advertiser sweep of all 29 coded/political Instagram handles (unordered + exact-phrase); all true-negative |
| `captures/tiktok_commercial_content_library.txt` | `5b061d619af644d4a04404956a4f1c33e6adec34169aa006ebc30d64f57f67be` | TikTok Commercial Content Library: country-coverage boundary (no US), political-ad ban, Temu control (138), MonsterLab/ClipIt/Serviuos=0, Turning Point SRL collision |
| `captures/google_ads_transparency_center.txt` | `c2fcfab766e80a4ce20fa3d9d4ed4bc12f7cbdff87df1659bd652e80ff364bf3` | Google Ads Transparency Center (US): verified beneficiary advertisers + ad counts; clipping platforms absent (only unrelated collisions) |

## Coverage summary (library × target class)

| Library | Beneficiary orgs/committees | Named commentators | 29 coded/political handles | Clipping platforms (ClipIt/MonsterLab/Serviuos) |
|---|---|---|---|---|
| **Meta Ad Library** (US) | TPUSA/Action/PAC = ACTIVE, full "Paid for by" + spend/impressions | Vivek + Ben Shapiro disclosed advertisers; Tulsi/Crowder/Shirley/Erika = subjects, not first-party | all 29 = true-negative (not advertisers) | not named in any observed disclaimer |
| **TikTok CCL** (EU/EEA scope; NO US) | political ads banned; "Turning Point"=SRL collision only | n/a (no US coverage; political banned) | n/a (no US coverage) | MonsterLab/ClipIt/Serviuos = 0 (validated, All countries 30d) |
| **Google ATC** (US) | TPUSA/Action/PAC = Verified advertisers | Vivek (Ohio cmtes) + Ben Shapiro = Verified; Tulsi/Crowder/Shirley/Erika = none | not applicable (advertiser search) | absent; only unrelated collisions (Clipit News B.V., monsterlab.com.ua) |

## Method notes / result-state discipline

- **True-zero vs challenged/unavailable:** every zero above is an OBSERVED rendered empty state
  ("No ads match your search criteria" / "No ads found" / empty advertiser autocomplete), not a
  challenge, timeout, or access failure. No search was blocked or CAPTCHA-gated.
- **Keyword tokenization noise (Meta):** default `keyword_unordered` search tokenizes dotted/worded
  handles (e.g. `politics.ts` -> "politics" -> ~9,400 unrelated ads). Per-handle non-advertiser status
  was confirmed with `keyword_exact_phrase`, which returned zero. Do not read unordered counts as
  advertiser presence.
- **Name collisions (TikTok/Google):** "Turning Point" on TikTok = unrelated "TURNING POINT SRL";
  "ClipIt" on Google = unrelated "Clipit News B.V." (Netherlands). Neither is an investigation target.
- **TikTok pitfalls:** direct URL navigation to `/ads?...&adv_name=X` does NOT execute the search (renders
  a false zero) — discarded. Multi-year windows return HTTP 425 (date-span cap); only the ~30-day window is
  validated (HTTP 200), positive control "Temu"=138.
- **Sanitization:** captures contain only rendered public result text (advertiser names, public "Paid for
  by" disclaimers, spend/impression buckets, public Library IDs, ad-count buckets). No session tokens,
  cookies, nonces, signed URLs, or logged-in views were captured or used. Minimal incidental PII: public
  advertiser/committee names only.
