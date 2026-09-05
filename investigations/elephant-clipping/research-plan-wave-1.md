# Manual research plan — launch wave 1

Date: 2026-09-02  
Coordinator: interactive Codex task `/root`  
Working directory: `/tmp/osint-E6iGgeNz`

This investigation is being dispatched and supervised manually through the
interactive task. The repository headless dispatcher and queue workers are not
used. All article assertions are leads until corroborated.

## Expected report set

The initial multi-target landscape uses eight durable-database-first research
tracks, plus one bounded supplemental handle-triage pass prompted by reader
discovery. Reports are summaries and are written to the session working directory:

1. `report-cloud-artifacts.md`
2. `report-serviuos-clipit.md`
3. `report-enclave-wynn.md`
4. `report-clipson-norway.md`
5. `report-monster-infra.md`
6. `report-distribution-network.md`
7. `report-finance-politics.md`
8. `report-law-controls.md`
9. `report-handle-triage-b.md` (supplement to the distribution-network report)

Two local-article preflight reports (`article-facts.md` and `article-links.md`)
support planning but do not count as independent corroboration.

## Source ownership matrix

| Source or source family | Primary owner | Scope |
|---|---|---|
| Attached Atlantic HTML and embedded Next.js data | Article preflight agents | Extract claims, named entities, and links only |
| Google Drive/Docs/Sheets/Slides/Forms; public cloud copies; Discord CDN artifacts | Cloud-artifacts agent | Public/archived artifacts, IDs, metadata, hashes, referrers |
| Search-engine discovery for cloud-document identifiers and distinctive campaign text | Cloud-artifacts agent | Exact strings, filenames, uploader names, public links |
| Latvian Enterprise Register, Lursoft public material, EU VAT/VIES, Latvian official gazette | Serviuos/ClipIt agent | ClipIt and responsibly resolved principals |
| OpenCorporates/unified registries, GLEIF, ICIJ for ClipIt/Serviuos | Serviuos/ClipIt agent | Cross-jurisdiction entity resolution |
| Nevada and other U.S. corporate registries; archived Enclave & Key first-party pages | Enclave/Wynn agent | Legal entities, trade names, officers, subsidiaries, addresses, staff roles |
| EDGAR and property/recorder catalog for Enclave/Wynn entities | Enclave/Wynn agent | Structured corporate/property baselines |
| Norwegian Brønnøysund Register Centre and Norwegian primary business records | ClipSon/Norway agent | ClipSon, Anders Wedøe/Wedoe, related entities and principals |
| Passive DNS, certificate transparency, URLScan, Wayback, Shodan, analytics IDs | Monster-infrastructure agent | Monster Lab and campaign marketplace infrastructure |
| Monster Lab public/archived campaign pages, terms, and payout descriptions | Monster-infrastructure agent | Portfolio and meaning of displayed budget fields |
| TikTok, Instagram, YouTube, and other distribution accounts/posts | Distribution-network agent | Account enumeration, captions, media reuse, public metrics, timing |
| Reader-supplied Instagram handle batch B | Supplemental handle-triage agent | Passive profile/code/post triage only; findings consolidated by the distribution owner |
| FEC, IRS 990, LDA lobbying, FARA, USASpending, committee/vendor disclosures | Finance/politics agent | Political funders, clients, beneficiaries, nonprofit and committee links |
| Public payment-provider terms, transaction clues, invoices, wallets, VAT/tax evidence | Finance/politics agent | Validate budget and payout mechanics; no paid or private access |
| CourtListener, RECAP, state/local court catalog, enforcement dockets | Law/controls agent | Cases involving resolved key people/entities; legal posture |
| Statutes, regulations, advisory opinions, FEC/FTC guidance and enforcement | Law/controls agent | Element-by-element legal analysis using primary sources |
| TikTok/Meta/YouTube disclosure and political-content policies | Law/controls agent | Time-specific platform rules and archived versions |
| Ordinary commercial clipping campaigns as negative controls | Law/controls agent | Compare common instructions, payouts, and disclosures |

Agents may flag an out-of-scope record for its owner, but should not duplicate the
owner's search or persist duplicate findings. The coordinator performs the final
corroboration, contradiction, coverage, and follow-up review.

## Shared execution contract

- Load and verify the active `elephant-clipping` profile before any database write.
- Claim the assigned lead with a unique `agent:manual-*` identifier.
- Check `search_log` before querying and record exact zero-result scope and limits.
- Use `--output /tmp/osint-E6iGgeNz/...` for every repository search command.
- Register all verified entities/roles/addresses and persist every factual
  discovery before writing the report; reports may not be the sole record.
- Findings require evidence, claim type, source quote, source token, confidence,
  profile, and the assigned lead/thread when supported.
- Secondary/web reporting is normally a paraphrase; primary-source direct quotes
  may be confirmed. Cross-source inference is synthesis at no more than medium.
- Preserve denials, uncertainty, false-positive checks, and alternative explanations.
- Search only publicly accessible material. Do not request access, contact subjects,
  use leaked credentials, evade controls, actively scan hosts, or modify documents.
- Do not mark a lead complete merely because time expires. Complete only when its
  defined question is actually resolved; otherwise add notes and leave it open or
  block it with a precise reason.

## Reader-supplied account pivots

The reader supplied the search pattern `site:instagram.com "ML-" politics` and
two batches of candidate handles. These are treated as discovery leads, not proof
of participation. The distribution owner is responsible for validating live
profile identity, exact `ML-*` bio text, public timestamps and metadata, and any
post-level match before a handle is added to the supported cluster. Batch B was
split to a supplemental agent solely to keep the manual review bounded and fast;
the distribution-network agent retains source ownership and deduplication.
