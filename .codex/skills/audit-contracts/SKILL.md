---
name: audit-contracts
description: Compare procurement patterns across contractors using spending, lobbying, partnership and staffing evidence. Use analyze-contract for a specific award's lifecycle.
---

# $audit-contracts

Accept a contractor list, `--sector`, or `--thread N`. Produce a cohort
comparison and testable explanations of material patterns. Roughly 3–10
contractors is a useful initial scope for a broad request; explicit user scope
and evidence needs determine the work.

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the profile/database first.
Use `docs/modules/government.md`, `docs/modules/political.md` and
`docs/modules/financial.md` as applicable; inspect subcommand `--help`
instead of assuming optional filters. Independent company/source tracks may use
native chat workers with inherited models, pinned context, unique artifacts and
parent reconciliation.

## Resolve cohort identity

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show --output "$WORKDIR/profile.json"
PROFILE=$(jq -r '.name' "$WORKDIR/profile.json")
```

Verify sector membership from current evidence. For `--thread N`, map the
profile-local number before querying the tracker:

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
jq -r '.[] | select(.finding_type == "financial" or ((.summary // "") | test("contract|award"; "i"))) | .target_name' \
  "$WORKDIR/thread-findings.json" | sort -u
```

Resolve company candidates using USASpending search and SAM to exact legal
identity/UEI and parent/subsidiary scope. A full name helps disambiguation but does
not guarantee the correct recipient. Verify the returned identity for every
query; split unrelated name matches. An empty cohort is a complete empty result.
If the findings limit is reached, obtain remaining records before claiming full
thread coverage.

## Compare spending periods

```bash
uv run python tools/query_usaspending.py search "<COMPANY>" --output "$WORKDIR/<slug>-search.json"
uv run python tools/ingest_sam.py search "<COMPANY>" --output "$WORKDIR/<slug>-sam.json"
uv run python tools/query_usaspending.py timeline "<VERIFIED_RECIPIENT>" --output "$WORKDIR/<slug>-timeline.json"
uv run python tools/query_usaspending.py recipient "<VERIFIED_RECIPIENT>" --output "$WORKDIR/<slug>-recipient.json"
```

Retain exact query filters, recipient identity, retrieval time and artifacts.
Timeline results aggregate obligations by fiscal year by default. Compare
complete years with consistent entity scope; show current partial-year data
separately or compare matched year-to-date windows. Handle zero/negative bases
and deobligations explicitly; CAGR is not meaningful for every series.

The recipient helper's agency categories have **all available periods** scope;
label that table accordingly. A most-recent-FY agency table requires an explicitly
date-filtered source/query, with the filter verified in its artifact. Never
relabel all-period totals as annual amounts.

Use YoY growth, CAGR and acceleration to select questions for review. Historical
25%/50% growth and twice-CAGR cutoffs are optional triage defaults, not established
sector baselines. Explain the benchmark cohort, period and adjustment for small
bases, acquisitions, new capabilities, consolidated awards and demand changes.
Describe an unavailable source as a gap; do not convert it to zero spending.

## Test relevant explanations

Assess lobbying timing/issues/registrants, partnerships and subcontracting, SEC
financials for public companies, and revolving-door evidence where those bear
on the observed pattern. The canonical modules and `--help` expose
`query_lobbying.py client`, `query_highergov.py partnership`, EDGAR sections,
and FEC donor checks. Confirm identity before attaching a person or organization.

To inspect existing revolving-door evidence, use a profile-scoped tracker search
and structured rows; expand aliases and limits when coverage requires it:

```bash
uv run python tools/findings_tracker.py search "<COMPANY>" --profile "$PROFILE" \
  --limit 1000 --output "$WORKDIR/<slug>-existing-findings.json"
jq -r '.[] | select((.summary // "") | test("revolving|former government|Pentagon|appointee|deputy|joined from"; "i")) | .summary' \
  "$WORKDIR/<slug>-existing-findings.json"
```

Keyword matches are candidates; open the underlying evidence for actual role
and service/employment dates. Search negatives are bounded to those aliases and
terms. Political giving or a former role alone does not establish influence.

For SEC comparison, retain statement periods and accessions. Recognized revenue
and federal obligations measure different things; reconcile period, entity,
classified/international work and timing before treating a delta as unexplained.
Read relevant contracts, filings and footnotes to the depth the question needs.

## Persist and finish

Promote material supported patterns, not one finding per numerical flag. Every
procurement-irregularity hypothesis includes observation, best innocent
explanation, falsification criterion and a concrete search plan, following
`research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`.

A supported growth synthesis uses exact load-bearing rows, with matching quote
references (substitute observed values and a reproducible source reference):

```bash
uv run python tools/findings_tracker.py add \
  --target "<COMPANY>" --summary "Federal obligations changed <X>% between complete FY<PREV> and FY<CURR>" \
  --type financial --evidence "USASPENDING:<SCOPE_REF>" \
  --source-quote "USASPENDING:<SCOPE_REF>:<exact fiscal-year and obligation rows>" \
  --detail "Identity/filters, periods, benchmark, calculation and artifact path: ..." \
  --sources usaspending --claim-type synthesis --confidence medium
```

Keep temporal correlations distinct from causal claims and preserve legal
allegation/status language. Link follow-up leads to specific unanswered questions
or awards, with justified priority rather than a required count. Use
`$analyze-contract` for award forensics and `$compare-peers` for financial peers.

Return cohort identities, complete-year timeline, all-period agency breakdown
(or explicitly filtered alternative), qualified growth comparisons, relevant
lobbying/partnership/staffing evidence, hypotheses, IDs and artifacts. Account for
each source track as completed/reused/partial/unavailable/not applicable. Continue
until the requested comparison is supported or unresolved work has explicit
evidence needs and disposition, preserving progress for long investigations.
