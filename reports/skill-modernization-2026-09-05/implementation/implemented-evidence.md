# Unit C: evidence identity implementation

Implemented in `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`; no commits, production database writes, headless jobs, or live source probes performed.

## Owned files

- `tools/query_edgar.py`
- `tools/query_usaspending.py`
- `.codex/skills/analyze-filing/SKILL.md`
- `.claude/skills/analyze-filing/SKILL.md`
- `.codex/skills/analyze-contract/SKILL.md`
- `.claude/skills/analyze-contract/SKILL.md`
- `tests/test_selected_filing_identity.py` (new)
- `tests/test_selected_award_transactions.py` (new)

The parent owns shared metadata normalization and catalog documentation. Unit G added the requested filing cross-reference fixture in its owned `tests/test_analysis_skill_modernization.py`.

## Behavior

### Stable filing selection

`sections [CIK_OR_TICKER] --accession ACC` or `sections --url SEC_ARCHIVES_URL` selects the exact historical accession. `--index`, `--accession`, and `--url` are mutually exclusive. The installed edgartools `Company.get_filings(accession_number=...)` API supports historical submissions and is reused directly. Returned accession is verified; URL CIK must match a supplied company, and an explicit form must match the selected form. Missing accessions and identity mismatches fail rather than selecting the latest 10-K. Default 10-K selection remains available for ordinary index mode.

Structured financial results preserve accession/form/date/periods; section text and full-text parse fallbacks now also include accession/form/date. Missing requested financial statements return nonzero. Exact URL selection binds the accession's structured filing, not the text of a named exhibit; the skill explicitly retains separate exact-document reading. Ratio commands now bind all three statements to the selected accession and verify statement type, identity, periods, units, and consolidated scope before comparison.

### Award action identity and coverage

`transactions --uei UEI --award-id GENERATED_UNIQUE_AWARD_ID --all-pages` fetches the existing verified recipient transaction endpoint and selects rows by exact returned canonical award ID locally. A recipient name can replace UEI. Plain PIIDs are rejected for this selector because PIIDs can collide; existing `award` resolution supplies the canonical ID. Legacy numeric internal IDs are also supported against returned `internal_id`. No new server filters or endpoints were invented.

`award_selection` reports matched/excluded/unresolved counts. Rows without the necessary canonical identifier cause an error/partial artifact, preserving verified matches. Pagination totals explicitly describe the upstream recipient search rather than the selected award. Obligations, including zero and negative modifications, remain untouched. Output and skill distinguish obligation actions from cash payments.

Both transactions and subawards now support `--all-pages`, `--max-pages N` (default 50), and `--page` resume. Pagination follows successive pages, preserves successful earlier rows on retrieval/validation failure, marks capped or unreported all-page coverage partial, reports continuation, and never claims full earlier coverage for a resumed run. Subawards still validates every page against existing exact PIID/recipient/agency checks. Transaction malformed/reversed date ranges now fail before querying instead of silently widening scope.

### Skill changes

- Replaced filing literal-database SQL with the profile-aware `findings_tracker.py connections` route.
- Retained full filing and load-bearing exhibit reading; made chunk size adaptive and direct full-context reading available.
- Added persistent coverage/checkpoint artifacts and resumption across compaction/interruption.
- Native supervised chat subagents can handle independent exhibits, cross-references, subcontractors, or vehicle analyses; parent reconciles identities and evidence.
- Replaced no-theorizing role bans with factual/inference separation and alternative explanations.
- Removed model/human capability sales prose and unsupported payment/complete-tree claims.
- Preserved domain checklists, provenance, confidence ceilings, and explicit pending incorporated-document coverage.
- Updated obligation findings/examples to preserve literal currency using single quotes; follow-up leads require concrete unresolved questions.

## Validation

Using `UV_PROJECT_ENVIRONMENT=/Users/travcole/projects/osint-research/.venv UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/osint-q8INnbtl/uv-cache`:

```bash
uv run pytest --offline tests/test_selected_filing_identity.py tests/test_selected_award_transactions.py tests/test_query_edgar_sections.py tests/test_query_edgar_import_lock.py tests/test_query_edgar_read.py tests/test_query_usaspending.py tests/test_query_usaspending_subawards.py tests/test_query_usaspending_papercuts.py tests/test_query_usaspending_failures.py -q
```

Final result: **102 passed**, 3 existing edgartools deprecation warnings, 1.42s. Tests include historical 10-K and 10-Q retention through all three statements, exact URL CLI without ticker, wrong/missing accession rejection, CIK/form mismatch rejection, canonical ID filtering across mixed awards/pages, real saved transaction schema, capped/unknown/resumed pagination, partial acquisition and identity errors, invalid page controls/date scope, and subaward validation after an earlier successful page.

`uv run ruff check` passed for both changed tools and both new test files. `git diff --check` passed for all unit-owned tracked paths.

Unit G separately confirms both-runtime filing connection examples against a selected database and decoy database, with same-name foreign-profile records excluded; its 8-case fixture suite and ruff passed.

## Retained limitations

- No live endpoint claims: tests use existing repository response fixtures and mocked installed-library contracts. The new options reuse already verified endpoint payloads. No new endpoint requires probing.
- Award selection traverses the recipient search rather than an unverified dedicated award-action filter; large recipients can require more pages. API date limits, filters, affiliation expansion, and dynamic pagination remain visible in output provenance/messages. Complete means the declared search scope, not all historical government activity.
- Subaward exactness is bounded to the exposed PIID/recipient/agency fields. The skill requires checking prime recipient and agency against canonical award detail before combining reused PIIDs, and does not claim an exhaustive subcontractor tree.
- A sections parser fallback remains a complete-text artifact; it is explicitly unsuitable as a structured ratio input. Very old/non-XBRL filings may need manual extraction from the selected text.
- No comparative Claude/Codex performance benefit is claimed without repeated model evaluations.
