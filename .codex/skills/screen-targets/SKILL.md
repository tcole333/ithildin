---
name: screen-targets
description: Screen a public-company list, sector, or investigation thread for financial anomalies and prioritize evidence-backed follow-up. Use compare-peers for a focused peer comparison.
---

# $screen-targets

Produce an anomaly matrix with coverage, accounting periods, and justified follow-up.
The requested cohort controls scope; 5–20 companies is a useful starting size when
the user gives only a broad sector. Continue until the agreed cohort is accounted
for, adapting the work when evidence or user steering changes the question.

## Establish the cohort

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md`, pin the profile/database context,
and create the isolated workdir before source selection. Use
`docs/modules/financial.md` and each tool's subcommand `--help` for current
interfaces. When separate companies benefit from parallel analysis, supervise
native chat workers, inherit the configured model, and give each worker the
pinned context and unique artifacts. Collect their results before ranking.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show --output "$WORKDIR/profile.json"
PROFILE=$(jq -r '.name' "$WORKDIR/profile.json")
```

Resolve explicit company names/tickers to SEC identities. For a sector, verify
current membership and explain inclusions; model knowledge is a starting list.
For `--thread N`, resolve the profile's local number to its global database ID:

```bash
LOCAL_THREAD_ID="<REQUESTED_LOCAL_THREAD_ID>"
GLOBAL_THREAD_ID=$(jq -r --arg local "$LOCAL_THREAD_ID" \
  '.threads[] | select((.id | tostring) == $local) | .global_id // empty' \
  "$WORKDIR/profile.json")
if [[ -z "$GLOBAL_THREAD_ID" || "$GLOBAL_THREAD_ID" == "null" ]]; then
  printf 'No global mapping for profile %s thread %s\n' "$PROFILE" "$LOCAL_THREAD_ID" >&2
  exit 1
fi
uv run python tools/findings_tracker.py list --thread-id "$GLOBAL_THREAD_ID" \
  --profile "$PROFILE" --limit 10000 --output "$WORKDIR/thread-findings.json"
jq -r '.[].target_name' "$WORKDIR/thread-findings.json" | sort -u
```

Treat a result limit as a coverage bound; obtain remaining records if that bound
affects the cohort. An empty thread or no public companies is a complete empty
result, with no new leads/findings.

## Extract and review

For each SEC registrant, resolve and retain the filing accession, form, filing
date, statement periods, units, and exact rows used. Read enough of the filing
and footnotes to interpret the ratios; there is no excerpt or page-count ceiling.
Use the same filing for all statements and record extraction failures explicitly.

```bash
uv run python tools/query_edgar.py sections --help
uv run python tools/query_edgar.py sections "<CIK>" --accession "<SELECTED_ACCESSION>" \
  --section income_statement --output "$WORKDIR/<ticker>-income.json"
uv run python tools/query_edgar.py sections "<CIK>" --accession "<SELECTED_ACCESSION>" \
  --section balance_sheet --output "$WORKDIR/<ticker>-balance.json"
uv run python tools/query_edgar.py sections "<CIK>" --accession "<SELECTED_ACCESSION>" \
  --section cashflow_statement --output "$WORKDIR/<ticker>-cashflow.json"
uv run python tools/financial_ratios.py analyze --help
uv run python tools/financial_ratios.py analyze \
  "$WORKDIR/<ticker>-income.json" "$WORKDIR/<ticker>-balance.json" \
  --cashflow "$WORKDIR/<ticker>-cashflow.json" \
  --output "$WORKDIR/<ticker>-ratios.json"
```

The statement artifacts come from `query_edgar.py sections` with
`income_statement`, `balance_sheet`, and `cashflow_statement`; use the
current CLI's filing selector and verify the returned accession, form, periods,
and `statement_type` before ratios. Full-text fallback is not a financial
statement artifact. A failed or missing metric is unavailable coverage, not a
clean result.

Assess regulatory sources for the target's actual nexus. SEC enforcement uses
the exact normalized registrant name by default; a fuzzy alias match is a
candidate. FINRA is relevant to regulated firms: confirm identity/CRD with
`detail` before reporting a match. Preserve allegation, charge, settlement and
conviction language. Keep regulatory status separate from the ratio score, and
distinguish unavailable sources from zero exact matches.

```bash
uv run python tools/query_sec_enforcement.py defendant "<EXACT_LEGAL_NAME>" \
  --output "$WORKDIR/<ticker>-sec-enforcement.json"
uv run python tools/query_finra.py search "<EXACT_LEGAL_NAME>" --type firm \
  --limit 10 --output "$WORKDIR/<ticker>-finra-firms.json"
```

When profile key dates bear on the question, use `query_market.py correlate`
with those dates and an explained event window. Timing association is a hypothesis.

## Prioritize and persist

A reproducible starting heuristic weights high/medium/low tool flags 3/2/1,
with scores 6+ suggesting deeper review and 4–5 suggesting standard follow-up.
These are triage defaults, not calibrated probabilities or mandatory lead counts.
Explain adjustments for business model, repeated/correlated flags, missing
metrics, accounting period, and the investigation question. Show the raw flags
and method so the ranking is reviewable. Label low scores “no screened flags”
when appropriate, and identify the metrics actually tested.

Promote relevant, verified anomalies after considering the best innocent
explanation and how to falsify the concerning interpretation. Record computed
results as synthesis, maximum medium confidence, with exact load-bearing filing
rows for each accession. Use `findings_tracker.py add --help` for
`--evidence` plus matching `--source-quote "REF:exact excerpt"` pairs.
Keep calculations and artifact paths in detail. Resolve prior work before creating
follow-up leads; prioritize questions that remain unanswered over numeric quotas.

## Complete

Return the cohort matrix: company/CIK, filing accession and period, available
metrics, flags, explained score/rank, regulatory coverage, and recommendation.
Include recorded finding/lead IDs, artifacts, skipped/unavailable/partial work,
and next useful tests. Finish when each requested target is analyzed or has a
specific coverage gap and disposition. Preserve resumable progress during long
runs and continue useful work while resolving source failures.
