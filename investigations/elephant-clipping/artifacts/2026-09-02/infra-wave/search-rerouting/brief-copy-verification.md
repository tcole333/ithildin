# Brief-copy hunt — Startpage exact-phrase results vs primary og-metadata

**Question (hunt a):** Are there independent public copies of the 258-word campaign brief (finding 15400)?

**Method:** Routed the brief's distinctive sentences through Startpage (Google index; exact-phrase operator honored — Startpage served a proof-of-work interstitial that its own page JS completed passively, no interaction). Startpage returned Instagram reel URLs whose snippets contained the verbatim brief text. Each surfaced reel was then checked against its **primary og-metadata** (unauthenticated HTTP GET of `https://www.instagram.com/reel/<id>/`, facebookexternalhit UA) to confirm whether the brief is actually in that reel's caption.

**Distinctive fingerprints used:**
- `"issues such the economy, foreign policy, public safety"` (grammatical error "such the" — near-unique)
- `"The goal is to showcase how modern conservative figures approach"`

## Startpage exact-phrase SERP (2026-09-02) — 5 reel URLs surfaced

| Reel URL | Startpage snippet variant | Google date |
|---|---|---|
| /reel/Dbnq4gyOiWL/ | "such **the** economy" (error) | 2026-08-04 |
| /reel/DQKoA1qgUW5/ | "such **the** economy" (error) | 2025-10-23 |
| /reel/DTJRVTejdw2/ | "such **as the** economy" (corrected) | 2026-01-05 |
| /reel/DaloqOcDfH-/ | "such **as the** economy" (corrected) | 2026-07-09 |
| /reel/Dcb0U05EmPY/ | "such **as the** economy" (corrected) | 2026-08-24 |

## Primary og-metadata verification — the decisive check

| Reel | Owner handle (og) | og date | Brief in ACTUAL caption? |
|---|---|---|---|
| Dbnq4gyOiWL | frontrawpolitics | 2026-08-04 | **YES** — og:description is the full 258-word brief (re-confirms finding 15400) |
| DQKoA1qgUW5 | karthikrajcomedy | 2025-10-23 | NO — caption is "Young Republicans PR training after the group chat leak" |
| DTJRVTejdw2 | newjerseyoag (NJ Office of the Attorney General) | 2026-01-05 | NO — caption is a job/PSA ("This job isn't about staying quiet…") |
| DaloqOcDfH- | nancyrmace (Rep. Nancy Mace) | 2026-07-09 | NO — caption "The country I was raised in doesn't look the same…" |
| Dcb0U05EmPY | danbongino (Dan Bongino) | 2026-08-24 | NO — caption "Pay attention to how the media is gaslighting you…" |

## Conclusion

- **No independent verbatim copy of the 258-word brief was confirmed.** Only the already-known @frontrawpolitics reel (`Dbnq4gyOiWL`) contains the brief in its actual caption.
- The four "new" URLs belong to **unrelated public accounts** (a comedy account, the New Jersey Attorney General's office, Rep. Nancy Mace, and Dan Bongino). Their real captions have nothing to do with the operation.
- Google/Startpage **injected the brief text into these URLs' snippets as an index artifact** (most plausibly leaked from embedded related-reel content on each reel page). The Dan Bongino reel is the clean counter-example: primary caption "Pay attention to how the media is gaslighting you…", yet its Google snippet showed the brief.
- **Methodological caution (note 2585):** Startpage HONORED the exact-phrase operator (the phrase is genuinely in Google's index), and the result page was genuine — but the per-URL snippet attribution was false. For Instagram reels, a caption-copy claim MUST be primary-verified via og-metadata; search snippets are not sufficient.
- Two textual variants exist in Google's index ("such the" error vs "such as the" corrected). The error variant matches the known reel. A corrected-variant copy may exist on some real reel, but no such URL could be reliably identified because snippet attribution is unreliable — recorded as an open follow-up.

Provenance: raw reel HTML captures held only in session scratch (login-wall markup, incidental metadata); this durable note keeps only public handle + date + caption first line + the brief-present/absent determination.
