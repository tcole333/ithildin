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
```

### 1. Build Target List

**From explicit tickers:** Parse the comma/space-separated list.

**From `--sector`:** Use your knowledge to identify 10-15 public companies in the sector. Document your reasoning for each inclusion.

**From `--thread N`:** Query findings for the thread, extract company names, resolve to tickers:
```bash
PYTHONPATH=. uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('SELECT DISTINCT target_name FROM findings WHERE thread_id = ? AND profile_id = ?', (N, 'PROFILE')).fetchall()
for r in rows: print(r[0])
"
```

### 2. Extract Financial Data (per target)

For each ticker, run the extraction pipeline. **If any step fails for a company (no XBRL data, delisted, etc.), skip it and note the failure.**

```bash
# Resolve ticker to CIK
uv run python tools/query_edgar.py lookup "TICKER"

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

### 3. Event Correlation (optional, if key_dates available)

If the investigation profile has key_dates, export them and correlate:

```bash
# Export key dates to JSON
PYTHONPATH=. uv run python -c "
import yaml, json
with open('investigations/PROFILE/config.yaml') as f:
    cfg = yaml.safe_load(f)
json.dump(cfg.get('key_dates', []), open('$WORKDIR/key-dates.json', 'w'), default=str)
"

# Correlate each target
uv run python tools/query_market.py correlate TICKER --events $WORKDIR/key-dates.json --window 5 --output $WORKDIR/<ticker>-correlation.json
```

### 4. Score and Rank

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

### 5. Record Findings

For each HIGH-severity anomaly, record a finding:
```bash
PYTHONPATH=. uv run python tools/findings_tracker.py add \
  --target "COMPANY NAME" \
  --summary "Financial screening: <anomaly description>" \
  --type financial \
  --evidence "SEC:CIK<NUM>:<ACCESSION>" \
  --claim-type synthesis \
  --source-quote "SEC:CIK<NUM>:Automated ratio analysis from financial statements" \
  --sources edgar \
  --confidence medium
```

### 6. Create Leads

For companies scoring ≥ 4:
```bash
PYTHONPATH=. uv run python tools/lead_tracker.py add \
  --title "Financial forensics: <COMPANY> — <N> anomalies flagged (score <S>): <top flag description>" \
  --category financial --priority <high|medium> \
  --target "COMPANY NAME" --source "agent:screen-targets" \
  --evidence "SEC:CIK<NUM>:<ACCESSION>"
```

### 7. Output

Present results as a scored matrix:

```
## /screen-targets Results — <N> Companies Screened

| # | Ticker | Company | CIK | Anomalies | Score | Top Flag | Recommendation |
|---|--------|---------|-----|-----------|-------|----------|----------------|
| 1 | SMCI | Super Micro Computer | 1375365 | 3 | 7 | Earnings/cash divergence | Deep Dive |
| 2 | RKLB | Rocket Lab | ... | 1 | 2 | Margin compression | Monitor |
| 3 | PLTR | Palantir | 1321655 | 1 | 3 | AR outpacing revenue | Monitor |

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
- Anomaly findings recorded for all HIGH-severity items
- Leads created for all companies scoring ≥ 4
- Output table complete

## Context Management

Expect ~4 EDGAR API calls per target (lookup + 3 sections) + 1 ratio calculation. For 20 targets: ~100 tool invocations. Use `--output` on every search command to keep context lean.
