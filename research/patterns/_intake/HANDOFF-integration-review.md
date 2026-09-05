# HANDOFF — pattern-library integration and review (written 2026-07-29)

Successor to `HANDOFF-icij-markup.md`, whose tasks are now **complete**. This file covers what to do next.

## State at handoff

**Branch:** `codex/post-publish-source-and-karp-20260715`. **Everything below is UNCOMMITTED**, and the branch
also carries unrelated pre-existing modifications — scope any commit to `research/patterns/` and the two new
files in `research/craft-research/frameworks/`.

Built across 2026-07-28/29, nothing written to `investigation.db`, no infra requests enqueued:

| Layer | State |
|---|---|
| Outlets profiled | 4 — ProPublica (217 index entries), ICIJ (107), OCCRP (100), The Markup (83); ~490 coded entries |
| Card layer | `detection-signatures.md`, **42 cards** (38–41 minted cross-outlet, 42 split out by validation) |
| Merged layer | `cross-outlet-ontology.md` — shared families with per-outlet frequencies, dependency comparison |
| Story indexes | one per outlet, each entry carrying a `Dependency:` class |
| Intake | 40 reports across `_intake/{propublica,icij,occrp,markup}/` + `tally/` + `raw/` |
| Adapter gaps | `adapter-gaps.md` — ProPublica ranking (rows 1–5 enqueued as infra #218–222), cross-outlet ranking (none enqueued), **and a new validation-derived V1–V4 section that outranks both** |
| Validation | **6 memos** in `_validation/`: cards 15, 16, 30 (earlier pass) + 4, 38, 39 (2026-07-29) |
| Frameworks | 2 Tier-2 **candidate** lenses: `purchased-assurance.md`, `permission-after-entry.md` (both `grounding_findings: []`) |
| Decisions record | `promotion-candidates.md` — what was promoted, what was held in the card layer, and why |

### The three results that should shape everything next

1. **All three cards validated on 2026-07-29 came back BLOCKED**, and two failed for the same infrastructure
   reason. This is the most useful thing the library has produced — read the memos before trusting any card.
2. **Card 39's payment-chain claim was refuted outright** (0 of 53,100 rows resolved to adjacent payment
   stages, 0.000% coverage, despite 97% amount/date coverage). The card was narrowed to commodity/closed-ledger
   and its surviving single-ledger tests split into new card 42.
3. **Cross-outlet convergence ≠ platform runnability.** Card 4 was graduated to "confirmed universal" on
   four-outlet evidence and then proved un-executable here (empty SEC bodies; zero admissible independent
   adjudications; proxy circularity). Those are two separate claims and must always be stated separately.

## Three background tasks are running in other sessions — integrate their results first

Each was spawned from a validation finding. When they land, the pattern library needs updating:

| Task | Fixes | On completion, update |
|---|---|---|
| `task_f1d7a697` SEC empty bodies in `government_releases.db` | adapter-gaps **V2** | Card 4's BLOCKED note + Ithildin mapping; re-run the card-4 validation if bodies land |
| `task_84fcc4c9` semantic + dated control edges on `connections` | adapter-gaps **V1** (the biggest one) | Cards 30 and 38 (both currently produce present-day sensitivities only); the header's graph-vocabulary blocker note |
| `task_6a7b1143` populate accounts/statements/counterparties in `epstein_derived` | adapter-gaps **V4**, partially | Card 39's closed-ledger form — if statement reconciliation becomes computable, record the coverage figure and lift the BLOCKED marker on that form only |

**Do not** relax any card's language on the strength of a task being *started*. Verify the fix landed and
re-measure coverage first.

**Status check 2026-07-29 (integration session, direct read-only DB measurement):**

- `task_f1d7a697` **LANDED** — the defect was in `datasets/sec_enforcement.db`, not `government_releases.db`
  as the row above says (the press-release corpus always had text). Verified: 5,464/5,464 window rows carry
  bodies; `10b-5` → 1,884 rows, `Section 10(b)` → 1,657 (both previously 0); corpus-wide backfill still in
  flight (~7.9K/37,592, count moving between queries — another session is writing). Card 4 text + memo §6
  addendum + detection-signatures header + adapter-gaps V2 all updated. Card 4 **remains blocked** on the
  numerator leg (no enumerable independent cohort), which no background task addresses.
- `task_84fcc4c9` **NOT landed** — `docs/CONTROL_EDGES_SPEC.md` (design, 2026-07-29) exists, but
  `connections` is unchanged: tech-right still 1,049 live edges, semantic set still 69, `valid_from` still
  4 / `valid_until` 0 platform-wide, the Palantir `subsidiary_of` edge still stored inverted. No card
  language relaxed.
- `task_6a7b1143` **NOT landed** — `financial_account` and `financial_statement` still 0 rows,
  transaction `account_id`/`statement_id` still all null, no `date_raw`/`date_precision` columns. No card
  language relaxed.

## Integration session progress (2026-07-29, session 2 — ran out of usage mid-queue)

Done in that session, beyond the status check above:

1. **Integration edits applied** (uncommitted, in `research/patterns/`): detection-signatures header
   blocker #2 rewritten (repaired-for-window + the `sec_enforcement.db` misattribution fixed); card 4's
   Ithildin-mapping parenthetical updated; adapter-gaps **V2** row rewritten (REPAIRED, correct DB, residual
   = `file_number` absent on 33.4% of window rows); the status-check block above added.
2. **Card-4 re-run deliberately deferred**: the memo's §6 addendum already re-measured the repaired leg;
   the numerator blocker is untouched by the fix; the corpus-wide backfill is still writing the DB
   (~7.9K/37,592 and moving), and the fixing session may run its own re-validation. Ready once backfill
   completes — scope it to the denominator leg (conduct classification + matter dedup via `file_number`),
   expect the blocked verdict to persist.
3. **Card-1 test-bed survey done** (read-only): the strongest fully-held two-books pair is
   **`datasets/sam.db` `sam_entities` (867,137 rows, self-certification channel: `uei`,
   `legal_business_name`, `dba_name`, `business_types`, `entity_structure`, `state_of_incorporation`,
   `primary_naics`, addresses, registration dates) × the DHS census FPDS conduct ledger
   (`investigations/tech-right/reports/2026-07-28-dhs-census/`, `recipient_uei` + `recipient_parent_uei`)
   — a hard UEI join end-to-end local.** Also held: `sam_exclusions` (167,862 rows, uei/cage/npi),
   `data/ppp_loans.parquet` (no EIN in public PPP → name+address join, which usefully exercises the card's
   linkage-error discipline), `datasets/irs990_grants.db` (10.8GB) + `datasets/irs_990_xml/` (2017–2025
   indexes + xml). **Not runnable:** `datasets/state_court_records.db` and `datasets/property_records.db`
   are schema-only — every table 0 rows — so the 990-posture × collection-dockets pair (Methodist Le
   Bonheur shape) has no local substrate; `datasets/nonprofits.db` is empty (no tables).
4. **Not yet done:** the Codex QA pass (item 1 below), the commit, the card-1 validation launch, the
   discipline fields for 3/5/14/21/29. Sequencing decided: run QA and card-1 concurrently (agents only
   write reports/memos; the orchestrator applies all card edits), apply QA fixes + discipline fields after
   QA returns, then commit everything in the scoped split; validation memos commit as they land.

## Work queue

### 1. Review and commit (gates everything else)
Scoped conventional commits — suggested split: intake layer, tally/story-index layer, synthesis layer
(`detection-signatures.md` + `cross-outlet-ontology.md` + `adapter-gaps.md` + `promotion-candidates.md` +
`README.md`), validation memos, then the two lens files. Optional and in keeping with repo habit: one
adversarial Codex QA pass over the four synthesis files first — the extraction reports were each
Codex-verified, but the merge layer has only had one pass.

### 2. Continue validation (highest value, no permission gate — memos are file-only)
Ranked:
- **Card 1 `two-books-diff`** — the most-used move in the entire corpus (~28 story-uses, 8/8 clusters) and
  still never executed. If it fails the way 4/38/39 did, the library's headline claim needs revisiting.
- **Cards 3, 5, 14, 21, 29** — produce computed statistics but still lack the discipline fields
  (Pre-registration / Coverage / Control / Preconditions). The card-file header flags this as a to-do.
- **Cards 40, 41** — currently blocked for want of an instrumentation harness. Validating them *is* the
  business case for that adapter, so a memo documenting the block is itself useful.
- Re-run **38** and **4** after their respective background tasks land.

Use the validation brief pattern that produced the 2026-07-29 memos: calibrate against
`_validation/card30-share-of-program.md`, demand a field-by-field executability verdict, require
pre-registered parameters *before* results, and state plainly that finding nothing is a valid outcome. The
three memos that came back blocked did so because the brief made that safe to report.

### 3. DB registration of the two candidate lenses (**needs explicit user go-ahead**)
`/discover-frameworks` includes `hypothesis_tracker.py add` and `lead_tracker.py add` steps. This wave ran
read-only by design, so those were skipped. See `promotion-candidates.md` §4. Detector wiring into
`model_detector.py` waits until a lens reaches `adopted`, which requires live grounding findings.

### 4. Adapter builds (**user's call** — the library's rule is that rows enter infra_tracker only when green-lit)
Decision-ready shortlist, validation-derived gaps first:
- **V1 semantic/dated control edges** — in flight as `task_84fcc4c9`.
- **V3 UEI/EIN/CIK/LEI ↔ registry crosswalk** — every ownership resolution currently degrades to name matching.
- **Web-instrumentation / HAR harness** — cheapest high-value external build (Blacklight is open source,
  Playwright already a dependency); unlocks cards 40/41 and the whole Markup method family.
- **FARA/LDA normalized influence layer** — free data, medium build, named by ICIJ's aid cluster as its
  specific blocker.
- **HMDA LAR**, **Latvia BO CSV**, **Poland CRBR** — all low-build, free-bulk.
- **OCCRP Azerbaijani ledger** — the only realistic way to get a genuine two-sided payment substrate.
- **Customs/bill-of-lading** — shared blocker of both registry outlets, but paid and heavier; probe first.

### 5. Agent-facing wiring (after validation, so we don't ship unvalidated cards into skills)
Two light touches, not a refactor:
- Add a pattern-screening step to `/pursue-lead`, `/screen-targets`, `/generate-hunches` posing the five
  confirmed universals (two-ledgers diff, hard-identifier join, denominator construction, missingness-as-signal,
  event-window alignment) with a pointer to the card file.
- Adopt the **instrument-snapshot rule** as a repo convention: any constructed-instrument detector persists its
  raw collected inputs at run time. This is the operational answer to the measured 31% decay in Markup-style
  detectors, and it is what keeps a dead detector artifact-replayable.

### 6. Optional — next outlet
Only if the above is clear. Ranked by expected end-to-end-runnable yield: **Bellingcat** (open-source
verification; likely the highest class-(a) share of any outlet and closest to this platform's constraints),
then Reuters investigations / BIJ (records-heavy). Another leak-centered outlet is the lowest-value option —
that ground is covered twice.

## Constraints and gotchas that cost time in the last wave

- **No investigation.db writes** unless the user green-lights a specific step. It is WAL: `sqlite3 -readonly`
  cannot open it — use `sqlite3.connect("file:investigation.db?mode=ro", uri=True)` + `PRAGMA query_only=ON`.
  Never run `investigation_context.py set` (other sessions hold different profiles).
- Other sessions write to the DB concurrently. A moved mtime is **not** evidence that your work wrote to it —
  verify by looking for rows bearing your work's fingerprint before reporting either way.
- `uv run python` for everything; `--output <file>` on any bulk query tool (a pre-tool hook blocks it
  otherwise, and it also trips on prompt text mentioning `tools/query_*` with bulk subcommand words).
- Session isolation: `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`. Scripts importing repo modules run from the
  repo root as `PYTHONPATH="$PWD" uv run python "$WORKDIR/script.py"`.
- zsh: quote URLs/globs; never assign to `path` or `status`; **dollar literals in double quotes lose their
  digits** — write them shell-safe in anything persisted.
- Relative links from `research/craft-research/frameworks/*.md` to the pattern library need `../../patterns/`,
  not `../patterns/`.
- **Verified Codex dispatch** (gpt-5.6-sol @ xhigh; network is OFF by default in workspace-write):
  ```
  cat spec.md brief.md | codex exec --cd /Users/travcole/projects/osint-research \
    --sandbox workspace-write -c 'sandbox_workspace_write.network_access=true' - > out.md 2> err.log
  ```
  Run in background; check the stderr banner ~15s in for model/sandbox/network. Splitting the prompt into a
  per-agent `spec.md` plus a shared `brief.md` and concatenating them worked well for fan-out.

## Reading order for a fresh session

1. `research/patterns/README.md` — the library, its method, and its sampling-frame caveats.
2. `research/patterns/cross-outlet-ontology.md` §3–4 — the merged families and the dependency comparison.
3. `research/patterns/detection-signatures.md` **header** — the two platform-level blockers and the
   intersection-coverage rule; then any card you intend to use.
4. `research/patterns/_validation/card39-*.md` and `card38-*.md` — the two clearest examples of what a
   validation is supposed to do to a card.
5. `research/patterns/promotion-candidates.md` — decisions already made; don't re-litigate them.
