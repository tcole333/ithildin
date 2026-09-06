---
name: screen-targets
description: Tier 0 financial red flag screening — scan 5-20 public companies via automated ratio analysis, flag anomalies, create leads
user_invocable: true
---

# /screen-targets

**TIER 0: FINANCIAL SCREENING** — This is a breadth-first financial scan. You are screening multiple public companies for red flags using automated ratio analysis, not performing deep forensic analysis. Record anomalies, score targets, create leads for companies that warrant Tier 1 investigation via `/analyze-filing` or `/compare-peers`.

Scan 5-20 public companies for financial red flags using structured financial data from SEC EDGAR. The primary output is a **scored anomaly matrix** and **leads for flagged companies**.

## Arguments

- `/screen-targets "PLTR, SMCI, RKLB, ASTS"` — explicit ticker list (comma or space separated)
- `/screen-targets --sector "defense-tech"` — resolve tickers from sector knowledge
- `/screen-targets --thread 3` — extract public companies mentioned in investigation thread findings

### Context Loading
```bash
uv run python tools/investigation_context.py show
```

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
uv run python tools/investigation_context.py show --json > "$WORKDIR/profile.json"
PROFILE=$(jq -r '.name' "$WORKDIR/profile.json")
```

### 1. Build Target List

**From explicit tickers:** Parse the comma/space-separated list.

**From `--sector`:** Use your knowledge to identify 10-15 public companies in the sector. Document your reasoning for each inclusion.

**From `--thread N`:** Treat `N` as the active profile's local thread number.
Resolve it to the database's global thread ID using the structured profile
artifact, then query findings through the supported tracker interface. Do not
query `investigation.db` directly and do not fall back to an identically numbered
thread owned by another profile.

```bash
LOCAL_THREAD_ID="<REQUESTED_LOCAL_THREAD_ID>"
GLOBAL_THREAD_ID=$(jq -r --arg local "$LOCAL_THREAD_ID" \
  '.threads[] | select((.id | tostring) == $local) | .global_id // empty' \
  "$WORKDIR/profile.json")

if [[ -z "$GLOBAL_THREAD_ID" || "$GLOBAL_THREAD_ID" == "null" ]]; then
  printf 'No global thread mapping for profile %s local thread %s\n' \
    "$PROFILE" "$LOCAL_THREAD_ID" >&2
  exit 1
fi

uv run python tools/findings_tracker.py list \
  --thread-id "$GLOBAL_THREAD_ID" \
  --profile "$PROFILE" \
  --limit 10000 \
  --output "$WORKDIR/thread-findings.json"
jq -r '.[].target_name' "$WORKDIR/thread-findings.json" | sort -u
```

Resolve the resulting company names to tickers. If the thread has no findings or
none resolve to public companies, report an empty target set and stop without
creating leads or findings.

### 2. Extract Financial Data (per target)

For each ticker, run the extraction pipeline. **If any step fails for a company (no XBRL data, delisted, etc.), skip it and note the failure.**

```bash
# Resolve ticker to CIK
uv run python tools/query_edgar.py lookup "TICKER" --output "$WORKDIR/<ticker>-lookup.json"

# Extract 3 financial statements
uv run python tools/query_edgar.py sections TICKER --section income_statement --output $WORKDIR/<ticker>-income.json
uv run python tools/query_edgar.py sections TICKER --section balance_sheet --output $WORKDIR/<ticker>-balance.json
uv run python tools/query_edgar.py sections TICKER --section cashflow_statement --output $WORKDIR/<ticker>-cashflow.json

# Run ratio analysis
uv run python tools/financial_ratios.py analyze \
  $WORKDIR/<ticker>-income.json $WORKDIR/<ticker>-balance.json \
  --cashflow $WORKDIR/<ticker>-cashflow.json \
  --output $WORKDIR/<ticker>-ratios.json
```

### 3. Regulatory Cross-Check (per target)

Resolve the SEC registrant's exact legal name from the company artifact, then
run read-only target checks:

```bash
uv run python tools/query_sec_enforcement.py defendant "<EXACT_LEGAL_NAME>" \
  --output "$WORKDIR/<ticker>-sec-enforcement.json"
uv run python tools/query_finra.py search "<EXACT_LEGAL_NAME>" --type firm --limit 10 \
  --output "$WORKDIR/<ticker>-finra-firms.json"
```

The SEC command uses exact normalized matching by default. If it returns zero,
run `defendant --fuzzy` only for documented aliases and label those results as
candidates pending review. FINRA search is also candidate discovery: confirm an
exact firm identity/CRD with `detail <ID> --type firm` before reporting it.
Preserve allegation, charge, settlement, and conviction language exactly.

Record regulatory counts/status separately in the matrix; do not silently add
them to the financial-anomaly score. If either source is unavailable, report
that coverage gap rather than treating it as zero results.

### 4. Event Correlation (optional, if key_dates available)

If the investigation profile has key_dates, export them and correlate:

```bash
# Export active-profile key dates from the already resolved profile artifact
jq '.key_dates // []' "$WORKDIR/profile.json" > "$WORKDIR/key-dates.json"

# Correlate each target
uv run python tools/query_market.py correlate TICKER --events $WORKDIR/key-dates.json --window 5 --output $WORKDIR/<ticker>-correlation.json
```

### 5. Score and Rank

Read each `<ticker>-ratios.json` file and score:

**Scoring formula:** `score = sum(severity_weight for each anomaly)`
- HIGH severity: 3 points
- MEDIUM severity: 2 points
- LOW severity: 1 point

**Escalation thresholds:**
- Score ≥ 6: **Deep Dive** → create lead with priority `high`, recommend `/analyze-filing`
- Score 4-5: **Standard** → create lead with priority `medium`, recommend `/analyze-filing`
- Score 2-3: **Monitor** → note in output, no lead
- Score 0-1: **Clean** → note in output

### 6. Record Findings

For each HIGH-severity anomaly, record a finding:
```bash
PYTHONPATH=. uv run python tools/findings_tracker.py add \
  --target "COMPANY NAME" \
  --summary "Financial screening: <anomaly description>" \
  --detail "Computed anomaly and ratio inputs; see <ticker>-ratios.json" \
  --type financial \
  --evidence "SEC:CIK<NUM>:<ACCESSION>" \
  --claim-type synthesis \
  --source-quote "SEC:CIK<NUM>:<ACCESSION>:<EXACT_SOURCE_ROWS_USED_WITH_PERIODS_AND_VALUES>" \
  --sources edgar \
  --confidence medium
```

Use the exact load-bearing filing rows or footnote excerpt as the source quote;
the analysis method belongs in `--detail`, not in `--source-quote`. Record a
regulatory finding only after opening the exact SEC action or confirmed FINRA
firm record and preserving its source text.

### 7. Create Leads

For companies scoring ≥ 4:
```bash
PYTHONPATH=. uv run python tools/lead_tracker.py add \
  --title "Financial forensics: <COMPANY> — <N> anomalies flagged (score <S>): <top flag description>" \
  --category financial --priority <high|medium> \
  --target "COMPANY NAME" --source "agent:screen-targets" \
  --evidence "SEC:CIK<NUM>:<ACCESSION>"
```

### 8. Output

Present results as a scored matrix:

```
## /screen-targets Results — <N> Companies Screened

| # | Ticker | Company | CIK | Anomalies | Score | SEC exact actions | FINRA status | Top Flag | Recommendation |
|---|--------|---------|-----|-----------|-------|-------------------|--------------|----------|----------------|
| 1 | SMCI | Super Micro Computer | 1375365 | 3 | 7 | 1 | exact firm | Earnings/cash divergence | Deep Dive |
| 2 | RKLB | Rocket Lab | ... | 1 | 2 | 0 | no exact firm | Margin compression | Monitor |
| 3 | PLTR | Palantir | 1321655 | 1 | 3 | unavailable | candidate only | AR outpacing revenue | Monitor |

### Event Correlation Summary (if available)
| Ticker | Notable Events | Biggest Move | Event |
|--------|---------------|-------------|-------|
| SMCI | 5/5 | -44.9% | BDO appointment |

### Leads Created: N
### Findings Recorded: N
### Skipped: N (reasons listed)
```

## Stop Conditions

- All targets processed (or skipped with documented reason)
- SEC exact and FINRA firm checks completed per target, or coverage gaps recorded
- Anomaly findings recorded for all HIGH-severity items
- Leads created for all companies scoring ≥ 4
- Output table complete

## Context Management

Expect ~4 EDGAR API calls per target (lookup + 3 sections) + 1 ratio calculation. For 20 targets: ~100 tool invocations. Use `--output` on every search command to keep context lean.
