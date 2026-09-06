# Offline UCC filing-review queue

Snapshot built 2026-09-04T02:47:00.230783+00:00. Full-list UCC collection is [paused pending supported access](ucc-collection-status.json). One later form load succeeded without new debtor or document requests; result and document access remain unverified. The [published terms](https://www.sec.state.ma.us/divisions/terms.htm) prohibit automated and manual scraping. See [supported access options](access-options.md), the [unsent inquiry](ucc-access-inquiry-draft.md), and the separate [historical access-denial record](ucc-access-block.json). Rerun this offline builder only when additional permitted source observations have been saved. This is a filing review worklist, not a completed lien census, loan inventory, or debt-balance report.

Base queue snapshot: **194 distinct original filing families**, including broad-prefix candidates and namesakes; **115** have at least one exact normalized legal-name candidate. It contains **104** saved index observations, **19** imported prior-sample history reviews, and **175** families without an imported prior-sample review. **191 families have pending actions**; one family is retained as an explicit legal-holder false positive. There are **0 unparsed sources/records** and **0 rows lacking a resolved original number** in this snapshot.

The separate [reconciliation ledger](filing-review-reconciliation-README.md) now records analyst review of all seven older saved histories and their eleven entries. One original PDF has prior complete visual-review evidence; six original and four amendment PDFs remain pending. These reconciled records appear separately in the aggregate and dashboard; the base queue and its 19 imported-review counter remain unchanged. Saved-text review does not certify current source coverage, all party-amendment effects, or complete document review.

## Files and rerun

- `filing-review-queue.json`: sorted filing families, holder candidates, full index occurrences, per-event PDF tasks, holder-level coverage gaps, raw-capture errors, and a SHA256 source manifest.
- `filing-review-build-args.json`: exact reproducible CLI argument array for this report, including older saved query-tool inputs. Paths are relative to the repository root.
- `filing-review-decisions.json`: the evidence-backed rejection for Keryan & Co. Inc. versus the Belmont LLC. Rejection concerns this legal-holder match, not whether the businesses might share owners.
- `tools/boston_ucc_filing_review.py`: generic offline builder. No browser, network, UCC, search-log, or investigation-database calls.

From the repository root:

```bash
uv run python - <<'PYCODE'
import json
from pathlib import Path
from tools.boston_ucc_filing_review import main
recipe = Path('reports/boston-liquor-license-collateral-2026-09-03/full-review/filing-review-build-args.json')
raise SystemExit(main(json.loads(recipe.read_text())))
PYCODE
```

A minimal invocation is `uv run python tools/boston_ucc_filing_review.py build --queue QUEUE.json --observations CAPTURE_DIR --samples SAMPLE_RESULTS.json --output FILING_QUEUE.json`. Optional `--index-supplement` imports detailed mixed-sample index rows; `--tool-index HOLDER_ID=FILE` requires explicit roster binding for an older query-tool search; `--tool-history FILE` imports parsed original/amendment parties, collateral and document links. `--decisions FILE` accepts `confirmed_holder`, `rejected_false_positive`, or `successor_candidate`, each with `holder_id`, `original_filing_number`, `evidence` and `note`.

## What remains

1. **Finish source index coverage.** All 1444 roster holder groups remain in `holder_coverage`. Current and lapsed scope states are separate. New raw observations may be newer than the base queue's state; both are shown. Prior summary events can certify a reported search count without containing raw rows: `occurrence_rows_supplied=false` and `captured_occurrence_rows=0` explicitly distinguish that case from a zero-result search. Repeated saved captures are deduplicated only when their holder/scope/query/time/rows agree; repeated rows within one observation remain separate occurrences.
2. **Resolve identities.** Exact case/punctuation-normalized names are prioritized while corporate endings remain intact. A suffix difference, a prefix-only hit, or a different debtor name stays visible. Street addresses from histories are preserved separately from license premises and index city/state. Sample matching decisions are labeled as prior reported judgments. The Harvard Street LLC remains a documented successor candidate whose connection to the roster license still needs resolution. KERYAN & CO, LLC's original `201626850400` retains all four index occurrences and the prior reason for rejecting it as the roster corporation.
3. **Read remaining histories.** The prior fixed sample has 26 exact-holder originals plus one successor candidate; 18 exact histories plus the candidate were reviewed. Eight exact histories remain unopened: BNV3 `202398125640`, `202519780840`; Tavern South Station `201959766670`, `202289974430`, `202409532560`; Tia's `201308680860`, `201849432830`, `202183992350`. The new full-list candidates have their own per-family `pending_actions`. Newly indexed amendments absent from a prior review reopen the history task. The seven older captures have now been reconciled separately; their attachment, identity and continuity gaps remain explicit in that ledger.
4. **Review remaining PDFs.** Across the 19 prior histories, original-PDF evidence is 3 full, 1 partial, 7 not opened, 1 unread, 2 not visually inspected (opening unknown), and 5 unknown. Full original-PDF reviews: Tia's `201308681100`, Prima `202634020070`, Fresh Boston `202632951240`. Brother's `202178937070` had only Exhibit A pages 2–3 reviewed. An original review does not clear amendment PDFs; each filing event has its own `document_review_tasks`. A PDF link, download, collateral quote, or history completion flag is not PDF review. No PDF exemptions were recorded.
5. **Close coverage gaps before broad absence claims.** The roster does not establish formation jurisdiction, former legal names, aliases or individual debtor name components. `query_massachusetts_ucc.py` supports `search-individual` and a separate lapsed archive, but this organization-mode index does not establish those searches or searches in other applicable jurisdictions. DBA, premises, and MA mailing addresses alone cannot supply those missing facts.

Original filing number is the deduplication key for a filing family. Continuations, amendments, assignments and terminations remain distinct child events. A recorded termination does not establish a balance, and a continuation is not a second loan. Preserved history URLs may be session-dependent; use the official filing-number lookup if they expire instead of inventing URLs.

Validation: nine focused offline tests cover original/amendment grouping, repeated occurrences and captures, missing original numbers, legal-ending differences, original versus amendment PDFs, successor identity, malformed captures, false-positive retention, query-tool capture semantics, and summary-count preservation. Ruff passes for the utility and tests.
