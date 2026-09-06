---
name: compare-peers
description: Compare a target company's financial ratios with relevant peers and test unexplained differences. Use for peer benchmarking or forensic hypotheses after financial screening.
user-invocable: true
---

# /compare-peers

Produce a comparison matrix, qualified outlier flags, and testable explanations
for material differences. Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` for pinned
profile/database, source reuse and evidence handoffs; use
`docs/modules/financial.md` and current subcommand `--help` for tool details.

## Select comparable companies and periods

Accept a target plus optional `--peers`. When peers are unspecified, start with
roughly 3–8 candidates and explain the chosen scope; business model, revenue
scale and economic exposure matter more than a shared SIC code. Verify identities
and current business mix using EDGAR metadata, filings and market profiles.
A small or incomplete peer set can still support a descriptive comparison; state
its limitations and avoid population-level conclusions.

Create an isolated workdir. Resolve each company to CIK and retain the exact
filing accession, form, date, statement periods and units. Choose comparable
complete fiscal periods before calculating differences. Disclose fiscal-year
end differences, missing periods, currency/unit differences and exclusions.
If periods cannot be aligned, present the descriptive values separately and
explain which comparisons remain meaningful.

Use `query_edgar.py sections --help` to extract income, balance and cashflow
statements from the selected filing. Read the underlying filing/footnotes to the
depth needed for the comparison. Where independent company work helps,
supervise native chat workers with inherited model settings, pinned context,
chosen periods and unique artifact paths; reconcile them before comparison.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_edgar.py sections --help
uv run python tools/query_edgar.py sections "<CIK>" --accession "<SELECTED_ACCESSION>" \
  --section income_statement --output "$WORKDIR/<ticker>-income.json"
uv run python tools/query_edgar.py sections "<CIK>" --accession "<SELECTED_ACCESSION>" \
  --section balance_sheet --output "$WORKDIR/<ticker>-balance.json"
uv run python tools/query_edgar.py sections "<CIK>" --accession "<SELECTED_ACCESSION>" \
  --section cashflow_statement --output "$WORKDIR/<ticker>-cashflow.json"
uv run python tools/financial_ratios.py analyze \
  "$WORKDIR/<ticker>-income.json" "$WORKDIR/<ticker>-balance.json" \
  --cashflow "$WORKDIR/<ticker>-cashflow.json" \
  --output "$WORKDIR/<ticker>-ratios.json"
uv run python tools/financial_ratios.py compare \
  "$WORKDIR/"*-ratios.json --output "$WORKDIR/comparison.json"
```

Verify all statement outputs' accession, form, periods and `statement_type`
before ratios; full-text fallback is not a financial statement artifact.
The compare command uses each file's **latest** ratio period independently.
Inspect `latest_periods` before interpreting `matrix`, `medians`, `outliers`
or `anomaly_counts`. If selecting another period from existing ratio artifacts,
write a derived comparison input with the chosen row and an artifact manifest;
retain the original input and explain the selection.

With at least five non-null values, the reported score is median deviation over
population standard deviation (threshold 2.0). With two to four values, it is a
half-range heuristic (threshold 1.5), not a z-score. Record `sample_size`,
`outlier_score`, `threshold`, and `score_method`; null metrics reduce the
actual cohort for that ratio. These defaults prioritize review, not proof of
misconduct. Empty/error outputs and failed target extraction require an explicit
coverage result; a peer-only table does not complete analysis of a missing target.

## Explain and test differences

For materially unexplained deviations, include observation, concerning
hypothesis, best innocent explanation, falsification criterion, and search plan.
Select hypotheses for information value rather than generating one per flag.
Use `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline` and relevant
frameworks from `research/craft-research/frameworks/` when they help distinguish
competing explanations.

```bash
uv run python tools/hypothesis_tracker.py add \
  --title "<Company> <ratio> difference" --pattern-type operational \
  --description "OBSERVATION: ... HYPOTHESIS: ... INNOCENT EXPLANATION: ... FALSIFICATION: ..." \
  --predicted-evidence "..." --search-plan "..." \
  --originated-from "analysis:compare-peers"
```

Record a financial synthesis only when every value contributing to the selected
ratio's sample size is reproducible from attached exact source rows. Example
quote syntax is `--source-quote "SEC:CIK<TARGET>:<ACCESSION>:<exact period/value rows>"`,
paired with the identical `--evidence` reference before the final colon.
Repeat for each contributing company. Keep the method, periods, null/exclusion
handling, and calculation artifacts in detail; confidence is at most medium.
If provenance is incomplete, retain the hypothesis and comparison artifact with
its gap instead of promoting an unsupported finding.

Peer membership and shared SIC are analytical metadata. Register entities with
their actual jurisdiction; create graph connections only for independently
evidenced corporate relationships. Use `entity_tracker.py add-entity --help`
and `findings_tracker.py add --help` for the current interfaces.

## Complete

Create follow-up leads when an unanswered, relevant question warrants further
investigation, explaining priority without a minimum flag count. Report company
identities, peer-selection rationale, each compared period, the matrix and method,
tested explanations, finding/hypothesis/lead IDs, and artifacts. Account for
failed/skipped/partial companies and metrics. Finish when the requested comparison
and material hypotheses have a supported result or an explicit next evidence need.
