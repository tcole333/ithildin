# Epstein reporting corpus: pilot extraction and methodology memo

## APPROACH

I treated datasets/epstein_reporting.db as an immutable reporting snapshot and
read it through SQLite URI mode=ro with PRAGMA query_only enabled. I verified the
Phase 4 guidance and the live add-claim/import-claims implementation before
extracting. The JSONL therefore contains only the fields the importer actually
reads:

- item_id, claim_text, subject_text, predicate, object_text
- event_date_raw, amount_raw, attribution, claim_kind
- source_excerpt, source_locator, extracted_by

I selected 16 queue items, at ranks 1, 2, 3, 4, 5, 6, 8, 10, 14, 16, 17, 21,
39, 58, 64, and 87. The selection deliberately favors early and non-financial
coverage: eight items predate 2015, three are from 2015-2018, four are from
2019, and one is from 2026. It includes New York Magazine #1801, Vanity Fair
#1802, two Palm Beach Post stories, three Daily Beast stories, three Guardian
stories, and two French-language Franceinfo investigations. Four items are
primarily money-centered (#1801, #1802, #1514, and #27), staying below the
five-item ceiling; the rest emphasize recruitment/Maxwell, legal accountability,
political relationships, properties, staff, or operations.

The 61 claims are atomic at the level useful for later verification. A plea,
payment, search result, recorded statement, or discrete allegation is a separate
claim. Allegations remain attributed to a complaint, deposition, interview,
police report, or outlet. Amounts and event dates are preserved when the article
supplies them. Direct_quote is used for quoted speaker/document language;
paraphrase is used for the outlet's account or for English renderings of French
text. Neither claim kind upgrades secondary reporting to established fact.

For stable locators, “paragraph N” means the Nth non-empty newline-delimited
text block in the stored current-version content_text. The extractor frequently
stores linked words as separate blocks, so this is a reproducible corpus locator,
not always a typographic paragraph. Excerpts were not whitespace-normalized.

## PILOT NOTES + validation summary

The pilot produced 61 claims from 16 items: 49 paraphrases and 12 direct
quotations. The strongest verification-ready groups are:

- Palm Beach investigative chronology: the 2005 police opening, Robson's sworn
  account, the October search, employee accounts of massage frequency, plea
  discussions, the 2008 plea, sentencing, counseling waiver, and the reported
  termination of the federal investigation.
- Staff and operating system: the four named employees protected by the
  non-prosecution agreement, appointment-book staffing, cash on hand, Groff's
  nondisclosure agreement, daily massage scheduling, cash payments, and
  travel/visa arrangements.
- Maxwell/recruitment: Ransome complaint allegations, Ward's account of what
  her 2003 profile did not pursue, the 2019 unsealed-document allegations, and
  Maxwell's contemporaneous denials.
- Science and philanthropy: the early Harvard pledge, Reuters-identified grants,
  MIT's direct contradiction of two Epstein press releases, and the documented
  Closer to Truth pledge and transfers.
- Properties and transnational operations: the JEP acquisition of 22 avenue
  Foch, the Paris flight-log chronology, the address-book “massage Paris”
  column, Brunel's flight-log frequency, the MC2 investment, and apartment rent
  arrangements described in a sworn deposition.
- Political and legal accountability: contemporaneous Trump, Clinton, and
  Mitchell statements; the Central Park photograph; the Acosta letter; the FBI
  memo; congressional oversight requests; and the ongoing-conspiracy statement
  by the SDNY U.S. attorney.

Several controls matter when reviewing these claims. Item #1801 is retained as
early narrative evidence, not ordinary corroboration: the Epstein profile flags
author Landon Thomas Jr. for an operational conflict. The two Franceinfo pages
store their entire article bodies as paragraph 1, making the excerpt essential
to navigation. I read AP/Guardian settlement item #1512 during screening but
excluded it from the selected pilot because its useful assertions restated the
CBS/Guardian legal-accountability material already represented.

The final read-only validator recomputed the importer's exact normalization and
SHA-256 fingerprint logic and returned:

| Check | Result |
|---|---:|
| JSONL claims / source items | 61 / 16 |
| Exact importer field sets | 61 / 61 |
| Excerpts that are exact content_text substrings | 61 / 61 |
| Direct-quote claim spans found verbatim in their excerpts | 12 / 12 |
| Locators containing a paragraph number | 61 / 61 |
| Excerpts present in the specifically located paragraph | 61 / 61 |
| Unique (item_id, normalized claim) pairs | 61 / 61 |
| Unique computed claim fingerprints | 61 / 61 |
| Existing (item_id, claim_fingerprint) matches | 0 |
| Validation failures | 0 |

The reporting corpus was never opened for write access and no mutating
reporting_corpus.py command was run. One read-only uv invocation crashed before
Python started. I then used .venv/bin/python as authorized. In following the
repository's mandatory papercut instruction, I logged that crash as papercut
#750; that created one friction observation in investigation.db and is the sole
unintended departure from the task's broader “no DB mutation” instruction. I
did not attempt to remove it because doing so would require another database
mutation.

## METHODOLOGY MEMO

### Unit of work and batch sizing

Do not send the remaining roughly 6,700 items directly to extraction. First
freeze a work manifest containing item_id, current_version_id, content_hash,
published_at, language, publisher, and a derived story-cluster identifier. The
importer binds a claim to whatever version is current at import time and ignores
a supplied version_id, so every batch must be revalidated against the current
version immediately before human approval/import. A changed version goes back
to extraction review.

Use two batch sizes:

1. A clustering tranche of 400-600 items. This is large enough to expose
   syndication and same-news-cycle rewrites across outlets.
2. An extraction microbatch of 15-20 story leaders, capped at about 150,000
   cleaned article-body characters. The pilot rate was 3.8 claims per item, so
   this should yield roughly 50-90 claims. Review in packets of no more than 50
   claims so attribution and duplication checks remain careful.

Double-review the first ten microbatches. Track claims per article, rejection
rate, claims merged as non-atomic, translated-claim corrections, story-cluster
false merges/splits, and primary-evidence yield. Recalibrate before increasing
throughput. Do not assume how much clustering will reduce the 6,700-item pool
until the first 2,000 items have measured cluster statistics.

### Story deduplication and ordering

The stored independence_group cannot serve as the rewrite cluster. The audit
found 238 outlet-level groups covering almost the whole corpus and only 13
exact-content groups. Selecting one item per current group would mean selecting
one story per outlet; treating every item within an outlet as independent would
re-extract rewrites. The data model should separate three concepts:

- outlet_independence_group: who produced the reporting;
- exact_content_group: identical current content hashes;
- story_cluster_id: rewrites, syndications, updates, and translations about the
  same reported event.

Build story_cluster_id in descending-confidence passes:

1. Collapse identical content_hash values.
2. Compute a cleaned-body hash after locating the article headline/byline
   window and removing navigation, related-story modules, and repeated chrome.
3. Normalize titles with Unicode NFKC/casefolding; remove outlet suffixes,
   “live/update/explainer” markers, timestamps, punctuation, and boilerplate.
   Combine title-token similarity with a publication window, overlapping named
   entities, dates, locations, docket/document identifiers, and amounts.
4. Use paragraph shingles or MinHash/SimHash on the cleaned body to catch light
   rewrites and syndication. A wire byline or copied lead is a strong signal,
   not conclusive proof.
5. After provisional extraction, compute a claim signature from normalized
   subject, predicate, object, event date, amount, and attribution. Same-day
   items with several matching signatures are candidate rewrites even when
   their prose differs.
6. For cross-language candidates, match names, dates, amounts, document IDs,
   and multilingual semantic similarity, then require bilingual review before
   merging.

Choose one leader per story cluster: prefer the earliest demonstrable original,
then the version with the clearest named sourcing/primary-document basis and
cleanest body. Keep followers for lineage, corrections, contradictions, or
additional genuinely new assertions. Only after leader selection should batches
be interleaved by outlet_independence_group, era, language, and topic. In other
words, clustering prevents repeat extraction; outlet independence controls
source diversity and corroboration. The current independence_group should not
do both jobs.

### Extraction and pre-verification review

Each extraction packet should include the frozen manifest, clean numbered text,
the proposed JSONL, and cluster neighbors. Automated gates should run before a
reviewer sees it:

- exact importer field names and allowed claim kinds;
- non-empty atomic claim_text, attribution, excerpt, and paragraph locator;
- excerpt exactness against the frozen current version;
- event-date/amount preservation checks;
- within-item normalized-claim and fingerprint uniqueness;
- cross-corpus near-duplicate claim signatures, especially within the story
  cluster and same-day news cycle;
- headline terms absent from the article body;
- version/content-hash drift since extraction.

The editorial reviewer then accepts, revises, merges, or rejects each claim.
The reviewer asks: Is it one independently testable assertion? Does the
attribution identify who actually said or recorded it? Is allegation/denial
language preserved? Is it new reporting or a restated old fact? Does the excerpt
support every material element, including date and amount? Is the source a
rewrite of an already-extracted item? For translated text, a second reviewer
checks modality, legal vocabulary, currency, names, and negation against the
original excerpt.

Only accepted packets should be imported, and import should leave every claim
reported_only/unverified. Import is not verification. A separate lineage pass
records rewrite, syndication, translation, correction, and contradiction
relationships. Another evidence researcher locates primary support and records
the exact quote/page and an assessment of what the source does and does not
establish. Only then should a reviewer use verify-claim. Promotion remains
limited to reviewed, primary-supported or independently corroborated claims
with quoted primary evidence.

### Staged entity resolution

Canonical entities live in investigation.db and are shared across profiles.
Entity work should not mint a new entity merely because a reporting claim
contains an unfamiliar string.

Stage 1 is offline suggestion: for accepted claims only, normalize
subject_text/object_text and named attribution mentions, then query canonical
entities and name_aliases read-only. Emit candidate entity IDs with the matched
alias and intended role (subject, object, attribution, location, organization).
Group descriptions such as “fifteen House Democrats” or “four staff members”
remain mention text unless each member is explicitly enumerated.

Stage 2 is item-level review. The current resolve-entities implementation scans
article text for exact aliases and inserts candidate item_entity rows; it does
not populate claim_entity. Run it only after a scoped review plan, then accept or
reject ambiguous aliases such as common surnames, organizations with changing
names, and people sharing family names.

Stage 3 is claim-role linkage. There is currently no reviewed CLI path that
populates claim_entity, and that table has no candidate/accepted status. Do not
write it directly. Add or approve a linkage workflow that consumes the Stage 1
review artifact, requires role and mention_text, verifies the canonical ID
against investigation.db, and records reviewer identity. Until that exists,
leave claim_entity empty rather than create silent false precision. Only
accepted claim links should feed graph analysis or finding promotion.

### Primary gaps as the verification queue

After reviewed claims are imported, primary-gaps identifies reported-only,
unresolved, or partially supported claims with no primary claim_source link.
Its current ordering is recency, not evidentiary importance, so enrich the
export outside the database and deduplicate it by canonical claim signature.

Prioritize gaps by:

1. Harm/sensitivity and decision relevance.
2. A named, retrievable primary source in the attribution: court filing,
   police report, non-prosecution agreement, SEC testimony, Form 990, deed,
   flight log, will, or released email.
3. Exact dates, amounts, document IDs, or quoted language that make the search
   falsifiable.
4. Novel claims not already supported through another rewrite.
5. Contradictions, explicit denials, author/source conflicts, and claims likely
   to affect multiple investigation threads.
6. Retrieval cost and expected evidentiary yield.

The pilot's first verification packets should therefore include the Palm Beach
police report and plea documents; the federal non-prosecution agreement and
draft charging records; the quoted FBI memo; SEC testimony; Forms 990; the
avenue Foch deed/JEP record; flight logs; the Groff FBI interview; and the
Vasquez deposition. Primary-gaps is a worklist, not proof that the reporting is
true, and linking another article or another OCR of the same released document
does not close the gap.

## RISKS

- Restated-history inflation: retrospectives repeat old facts with new prose.
  Extract only a cluster leader's inherited facts; followers contribute only
  genuinely new sourcing, detail, correction, denial, or contradiction.
- Translation drift: English paraphrases can lose hedges, evidentiary posture,
  legal distinctions, or currency conventions. Preserve the original excerpt
  and amount_raw, mark the claim as paraphrase, and require language review.
- Headline/body mismatch: headlines and key-point boxes may overstate a body,
  refer to linked coverage, or survive after the article changes. No claim
  should rely on the headline alone.
- Chrome and transcript contamination: AP captures can place about 35,000
  characters of navigation before the article; NBC pages can contain program
  transcripts in which Epstein is only a short segment. Locate the article
  window before scoring, clustering, numbering, or extraction.
- Paragraph artifacts: HTML links split logical sentences into multiple stored
  blocks, while some Franceinfo bodies are one giant block. Locators must use a
  documented deterministic rule and always carry an exact excerpt.
- Version drift: a correction or refreshed page can change current_version_id
  between extraction and import. Freeze version/hash, compare again before
  import, and re-review changed claims.
- Attribution laundering: “court records show” may actually refer to another
  outlet's paraphrase; “sources say” may be recycled through many rewrites.
  Record the immediate attributed basis and trace it to the primary record.
- Direct-quote overconfidence: a verbatim quote proves that a person/document
  said something, not that the underlying assertion is true.
- Source conflicts: Landon Thomas Jr. and Michael Wolff require special
  caution; outlet-level quality scores must never override author-level
  conflicts.
- Fingerprint limits: import idempotence is only (item_id, normalized
  claim_text). It cannot prevent the same assertion from being imported from
  twelve rewrites; story and claim clustering must happen before import.
- Entity false positives: exact aliases in full article text do not prove that
  an entity occupies a role in a specific claim. Resolve claim roles only after
  editorial acceptance.
- Corroboration inflation: archives, syndications, translations, and multiple
  OCRs of one document are lineage, not independent evidence.
