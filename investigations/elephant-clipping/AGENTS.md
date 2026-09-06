# Elephant Clipping Investigation Guidance

## Scope

Investigate the cross-border political video-clipping network seeded by The
Atlantic's September 2, 2026 report. The central questions are who commissioned
and funded the campaigns; which legal entities, people, and payment services
operated them; how content moved from suppliers to clippers; which accounts and
audiences were reached; and whether disclosures, election law, tax obligations,
platform policies, or contractual rules applied.

Do not merely restate the seed article. Treat every article-derived assertion as
a lead until independently corroborated, and actively test innocent, commercial,
political, and deceptive explanations.

## Seed Source and Reliability

- Canonical seed reference: `ATLANTIC:688447`
- Article: Ali Breland, "Inside a Conservative Operation to Hijack Your
  Social-Media Feed," The Atlantic, September 2, 2026.
- The article is secondary reporting. It may justify `paraphrase` findings at no
  more than `high` confidence, but it is not independent corroboration for facts
  that ultimately derive from the same Discord or Google Drive artifacts.
- Preserve the article's reported denials and limitations alongside allegations:
  Serviuos called the questions out of context; Blake Wynn said there were
  inaccuracies; Enclave & Key characterized the activity as routine and lawful;
  Turning Point USA denied familiarity with the campaign; Anders Wedøe declined
  to discuss it.
- `Serviuos` is an online alias until identity resolution is supported by public
  evidence. Do not merge it with a person merely because of a name, face, accent,
  or geographic match.

## Public Cloud-Document Research

Search for Google Drive, Docs, Sheets, Slides, Forms, Dropbox, OneDrive, Notion,
Discord CDN, and similar artifacts that their owners intentionally made publicly
accessible or that are preserved in public web archives.

- Use only public, unauthenticated access. Do not request access, authenticate as
  another person, evade permissions, enumerate private resources, or exploit a
  service.
- Do not alter, comment on, or interact with a target-controlled document.
- Preserve the public URL, stable document/folder ID, discovery URL, access time,
  HTTP status, visible owner/uploader attribution, filenames, timestamps, and a
  cryptographic hash for lawfully downloaded files.
- A public link that later becomes inaccessible remains a lead; use archives,
  search-result traces, referrers, filenames, and independently published copies.
- Treat Google uploader display names and email-like attributions as identifiers
  requiring corroboration, not definitive proof of authorship or employment.
- Minimize incidental personal information and never publish access tokens,
  session identifiers, private emails, or unrelated personal files.

Useful public-search patterns include exact campaign/company names and domains
combined with `site:docs.google.com`, `site:drive.google.com`, `site:forms.gle`,
`site:discord.com`, `site:cdn.discordapp.com`, `filetype:pdf`, distinctive quoted
campaign instructions, filenames, uploader names already reported publicly, and
archived campaign URLs. Search Latvian and Norwegian variants as entities resolve.

## Evidence Discipline

- Separate facts, source allegations, and inference. Financial totals displayed
  by a campaign interface are claims until payment records or counterparties
  corroborate them.
- Preserve exact date ranges and denominators when validating view counts,
  budgets, or payouts. Do not add totals from overlapping campaigns or weeks.
- Three accounts reposting the same source video are distribution evidence, not
  three independent sources.
- Platform account ownership requires more than a matching handle or avatar.
- Use primary registries, filings, court records, archived first-party pages,
  platform transparency libraries, and original artifacts wherever available.
- Record scoped negative searches in `search_log`; absence from a search engine or
  archive is not proof that a document, company, payment, or relationship never existed.
- Do not contact subjects or join private groups. Passive review of a server or
  page that is openly accessible without circumvention is allowed, but record how
  access was obtained and avoid posting or reacting.

## Identity and Entity Aliases

- `Elephant Clipping`, `ClipIt`, and `Monster Lab` may be campaign/product names
  rather than legal entities; resolve them before assigning jurisdiction.
- Search both `Anders Wedøe` and `Anders Wedoe`.
- Search `Enclave & Key`, `Enclave and Key`, and any registry punctuation variants.
- Distinguish Benjamin Goodman and Jack O'Hara from common-name false positives by
  company role, location, domain, and time period.

## Wave-One Resolutions and Selectors (2026-09-02)

- Official Clark County and USPTO records resolve `Enclave & Key` as a DBA/trade
  name of Nevada entity `B WYNN SPORTS LLC` (`E0456082018-2`). Treat Celebrity
  Poker Tour as a same-LLC brand/mark unless a separate legal entity is found.
- Norway's official register resolves `CLIPSON WEDØE` as organization
  `935490014`, an Anders Wedøe sole proprietorship. Its public product stack does
  not independently establish the article-reported US Politics Clipping link.
- The public SERVIUOS digital persona is stable across Whop user
  `user_dWDlSFuNxFzH8`, ClipIt business `biz_MTuyZYomLpS6Hu`, Ai Profit business
  `biz_Obii9qxYQC2vk4`, YouTube `@ogserviuos` (`UCtnBA-3CRpSSg4uPwRtqoOw`),
  YouTube `@servtheclipper` (`UC4FZg3CI7djeCGMYPWUVFhA`), and `serviuos.com`.
  This resolves a digital operator, not a civil identity or legal company.
- Monster Lab's public client and terms document a workflow in which a user puts
  a server-returned verification code in a social profile bio. Twenty-six live
  political Instagram profiles displayed distinct `ML-*` codes in the bounded
  wave. This is consistent with that workflow but is not a public account-to-
  Monster enrollment record; retain the finding as synthesis.
- `crowders.debate` was live in the reader-supplied control batch but displayed no
  `ML-*` code at capture. Do not include it in the coded cluster without new evidence.
- Public cloud selectors, sanitized hashes, discovery chains, and exclusions are
  recorded in `artifacts/2026-09-02/cloud-artifacts/MANIFEST.md`. Do not reproduce
  passwords, dummy credentials, signed media URLs, or incidental account details
  from raw viewer pages.

## Wave-Two Handoff (2026-09-02)

Before extending search, media comparisons, merchant attribution, or tutorial
provenance, read `reports/2026-09-02-wave-2.md` and its lane-specific evidence
manifest. It distinguishes the new record from the historical launch census.

- Bing selectors: `ykpolitics` / `ML-T0UJ` / numeric ID `46452494248`, and
  `us_politicstoday` / `ML-EC19` / numeric ID `12005255780`. Findings 15441–15442
  establish unauthenticated first-party metadata only; privacy and reel grids
  remain unknown. Earlier missing numeric IDs leave a rename caveat. Keep this
  layer separate from the 27 previously reviewed public timelines.
- Four matched edited-caption packages are documented in
  `artifacts/2026-09-02/distribution-wave-2/report-agent-d.md`. For attribution,
  pursue earliest exact public edits under lead 94829, not merely earlier raw
  speeches. Hypotheses 461–463 remain unresolved; all current assessments are
  non-discriminating. Inter-post times are conditional media-ID derivations.
- Use corrected audio evidence in finding 15323. The prior APSNR magnitude
  failed a known-different control and is withdrawn; methods and controls are
  preserved in the wave-two evidence bundle.
- Challenge folder `1gkKBLN5aLI2GDohDTCKxk8BU-JaKf9qV` contains 15 tutorial
  files. Only two thumbnails were reviewed. Sample file
  `1GKwLAdk3qXsyDs9UVfEHwO5aKmM7IFcE` has partial branding consistent with
  Digital Social Hour; lead 94826 seeks exact episode provenance. This is not a
  documented political source packet or client/payment relationship.
- A shared archived course link with a current `Kreator` checkout label is not
  a valid ClipIt legal-merchant bridge; read the earlier-page control in finding
  15432 before reusing that selector. Merchant and actual campaign payments
  remain unresolved.
- Search-engine acquisition and strict query execution are separate fields.
  Bing/Brave produced results; Brave relaxed several queries and rewrote
  `Serviuos` to `servicios`. DuckDuckGo/Yandex challenged. Preserve unavailable,
  rewritten, and unissued searches distinctly from true zero results.

## Wave-Three Handoff (2026-09-02)

Before extending the organizational hunches, read `reports/2026-09-02-wave-3.md`
and `artifacts/2026-09-02/wave-3-review/MANIFEST.md`. Findings 15447–15451 and
15455–15456 are this manually commissioned wave; concurrent profile additions
are not part of its seven-finding count.

- Monster Lab's published client claims a `Political Clip` generation mode.
  Display text `May 21` and internal ID `2026-05-21` are a self-dated history
  claim, not an independently verified release date. No exact campaign output
  or operator use was established. Auto-submit describes collection/submission
  of already-published posts, not observed social publication.
- July/December 2025 mentorship archives link forms that currently advertise
  four-figure coaching. Do not backdate current form wording to the archives or
  infer sales, revenue, legal seller identity or political funding.
- The complete 25.983333-second training sample is preserved. Its captions and
  programme metadata nominate DSH episode 721 (`4uYmzucv4WQ`) as a candidate,
  not an exact segment match. The other 14 training files were not downloaded.
  Five sparse CPT content-hub captures do not constitute political packet or
  uploader coverage. The wave-two partial-thumbnail description is superseded
  only for this one sample, not the entire folder.
- The six-LLC payment pass adds qualified FEC/state/IRS coverage but no payment
  edge. Ohio local and statewide systems are separate. The 18 statewide target
  scopes had empty displayed sections and unknown source counts; Florida's
  failed date validation is blocked coverage, not a negative result.
- Leads 94992, 94994, 94996, 94998 and 95000 remain open after the bounded wave.
  Read their coordinator notes before the original hunch descriptions. The
  baseline hypotheses 464–471 retain disputed comparisons and nonexclusive
  alternatives; this wave did not endorse, promote or rescore their rankings.
- The post-wave automatic proposals 95353–95354 are reciprocal fuzzy entity
  candidates from concurrent profile work, pending review; no merge or new
  relationship was approved. Continue manual orchestration unless the user
  changes that instruction.

## Initial Geographic Priorities

Nevada and other U.S. jurisdictions tied to Enclave & Key; Latvia for ClipIt and
Serviuos; Norway for ClipSon and Anders Wedøe; and jurisdictions surfaced by
payment processors, corporate filings, domains, or contractor records.
