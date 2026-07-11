# SoftBank Caper — Agent Context Addendum

Case-specific context for agents working the `softbank-caper` profile. Supplements the
generic platform instructions in the root `CLAUDE.md`.

## Thesis (what we're testing)

Two operations on the same private rails:
1. **The Caper (2015-2019)** — established, primary-sourced. Epstein as undisclosed
   back-channel between Paul Weiss (Karp, SoftBank) and Steptoe (Weingarten, Misra) in the
   Jan 2019 window. See `research/softbank-caper-evidence.md` and `content/articles/softbank-caper.mdx`.
2. **The Extraction (2017-2024, WeWork)** — USER-PROVIDED hypothesis under active
   investigation. SoftBank lost ~$14B+ of ~$16B in WeWork while insiders extracted value
   (Neumann's ~$1.7B exit + ~$430M non-recourse loan; Misra's OneIM $470M letter of credit →
   ~$105M profit, both sides of the deal).

The connective claim — "the same machinery ran both" — rests on **shared cast** (Misra,
Paul Weiss, Weingarten), NOT on a direct Epstein-WeWork document. Build accordingly.

## Hard evidentiary rules for this case

- **The WeWork story stands on PRIMARY documents**: SEC filings (S-1, S-4/DEFM14A, 10-K,
  8-K exhibits) and court records (Delaware Chancery 2020; District of New Jersey bankruptcy
  23-19865). Every dollar figure must trace to one of these or be labeled secondary.
- **Read in full, do not skim.** Each deep-read agent gets ONE bounded document or section.
  Extract verbatim quotes with page/section/docket citations. Never summarize a filing from
  prior knowledge — open it and quote it.
- **Epstein-WeWork link is presumed NEGATIVE until proven.** Unified/DOJ/LMSBAND/Duggan
  searches for neumann/wework/schreiber returned only false positives (a Barbara Neumann re
  Brunel; a job-seeker re the WeWork design studio). Report the sweep result honestly even
  if it stays empty.

## Source reliability (case overrides)

| Source | Treatment |
|--------|-----------|
| SEC EDGAR filings, court dockets | **Primary.** `direct_quote` → may be `confirmed`. |
| WSJ — Eliot Brown ("A Possible Winner..."), Hope & Strasburg | Reliable secondary. `paraphrase`, max `high`. Brown literally wrote the book on WeWork (*The Cult of We*) — strong but still verify figures against filings. |
| The Real Deal, Inc42, Semafor, Bloomberg recaps | Secondary. Corroboration only, not primary. |
| The "looting"/intent framing | `inference`/`synthesis`, max `medium`. Self-dealing is documentable; *intent to loot* is argued, not proven. |

## Key figures to verify against primary sources (do not assume from WSJ)

- Neumann ~$430M **non-recourse** loan (collateral = WeWork shares) — confirm structure & non-recourse feature
- Neumann $185M consulting fee; ~$500M JPMorgan credit-line payoff; ~$970M tender proceeds; $5.9M "We" trademark
- OneIM $470M letter of credit (Feb 2023); SoftBank guarantee; 18-month interest guarantee; ~15% rate; early repayment → ~$105M
- SoftBank totals: >$10B under Neumann, up-to-$5B new debt guarantee, ~$16B total / ~$14B+ lost
- Joel Schreiber ~33% stake — **verify the date** (user cited a 2017 RealDeal piece that recounts a 2013 transaction)
- Paul Weiss role in the 2019 SoftBank funding deal — confirm via the deal docs, and whether Karp personally appears

## Existing assets

- `research/softbank-caper-evidence.md` — the caper evidence summary
- `content/articles/softbank-caper.mdx` — ~5,000-word draft (2015-2019 + 2026 coda); WeWork is the missing middle
- `content/financials/softbank-caper-wire.json` — the $500K wire ledger (extend pattern → `softbank-caper-wework-wire.json`)
- `content/timelines/softbank-caper.json`, `content/ego/softbank-caper.json`, `content/cluster-softbank-caper.json`

## Note on profile history

Findings created before 2026-06-22 may carry `profile_id = 'epstein'` (this work predated
the formal profile). New findings should use `profile_id = 'softbank-caper'`.
