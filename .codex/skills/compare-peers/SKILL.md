---
name: compare-peers
description: Tier 2 peer benchmarking — compare target financial profile against 3-8 industry peers, flag outliers, generate forensic hypotheses
---

# $compare-peers

**TIER 2: ANALYSIS AGENT** — This is a theory-building skill on the Analysis Plane. You are comparing a target company's financial profile against industry peers to detect statistical outliers and generate forensic hypotheses. Every hypothesis MUST include falsification criteria and a best innocent explanation. See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`.

Compare a target company's financial ratios against 3-8 industry peers. The primary output is a **comparison matrix**, **statistical outlier flags**, and **forensic hypotheses** for anomalous ratios.

## Arguments

- `$compare-peers "Palantir" --peers "Booz Allen, Leidos, SAIC, Raytheon"` — explicit peer list
- `$compare-peers "Palantir"` — auto-select peers by SIC code and agent knowledge

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

### 1. Identify Target and Peers

```bash
# Get target SIC code and metadata
uv run python tools/query_edgar.py company <TARGET_CIK> --output $WORKDIR/target-company.json
uv run python tools/query_market.py profile <TARGET_TICKER> --output $WORKDIR/target-profile.json
```

**If peers specified:** Resolve each to CIK via `query_edgar.py lookup`.

**If peers not specified:** Select 4-6 peers based on:
- Same SIC code (from EDGAR company metadata)
- Same sector/industry (from yfinance profile)
- Similar revenue scale (within 3x of target)
- Agent knowledge of competitive landscape

**Document your peer selection reasoning.** Peer group composition matters — comparing a software company to hardware companies produces misleading outlier flags. Group by business model, not just industry classification.

### 2. Extract Financial Data (all companies)

For each company (target + peers):

```bash
# Extract financial statements
uv run python tools/query_edgar.py sections <TICKER> --section income_statement --output $WORKDIR/<ticker>-income.json
uv run python tools/query_edgar.py sections <TICKER> --section balance_sheet --output $WORKDIR/<ticker>-balance.json
uv run python tools/query_edgar.py sections <TICKER> --section cashflow_statement --output $WORKDIR/<ticker>-cashflow.json

# Compute individual ratios
uv run python tools/financial_ratios.py analyze \
  $WORKDIR/<ticker>-income.json $WORKDIR/<ticker>-balance.json \
  --cashflow $WORKDIR/<ticker>-cashflow.json \
  --output $WORKDIR/<ticker>-ratios.json
```

**If extraction fails for a peer:** Skip it, note in output. Minimum 3 companies total for meaningful comparison.

### 3. Run Peer Comparison

```bash
uv run python tools/financial_ratios.py compare \
  $WORKDIR/*-ratios.json \
  --output $WORKDIR/comparison.json
```

Read the comparison output. Key fields:
- `matrix`: ratio values for each company
- `medians`: group median for each ratio
- `outliers`: flagged values with `sample_size`, `outlier_score`, `threshold`, and `score_method`
- `anomaly_counts`: number of outlier flags per company

Interpret the method exactly as reported. With at least five non-null values,
the score is deviation from the median divided by population standard deviation
and the threshold is 2.0. With two to four values, it is a small-cohort
heuristic using half the observed range and a 1.5 threshold—not a z-score.

### 4. Generate Forensic Hypotheses

For each statistical outlier flagged in the comparison, generate a hypothesis:

**Every hypothesis MUST include:**

1. **The observation**: "[Company] has [ratio] of [X] vs peer median of [Y] (score=[Z], n=[N], method=[METHOD])"
2. **Forensic hypothesis**: What might explain this deviation beyond business model differences?
3. **Best innocent explanation**: The most plausible non-concerning reason
4. **Falsification criterion**: What evidence would disprove the concerning interpretation?
5. **Search plan**: Specific next steps to test the hypothesis

**Quality bar:** 3 well-reasoned hypotheses are better than 10 obvious ones. Don't flag things that are easily explained by known business model differences.

Record each hypothesis:
```bash
PYTHONPATH=. uv run python tools/hypothesis_tracker.py add \
  --title "<Company> <ratio> outlier: <value> vs median <median>" \
  --pattern-type operational \
  --description "OBSERVATION: ... HYPOTHESIS: ... INNOCENT EXPLANATION: ..." \
  --predicted-evidence "..." \
  --search-plan "..." \
  --originated-from "analysis:compare-peers"
```

### 5. Record Findings

For each notable outlier (forensically significant, not just business-model-different):

```bash
PYTHONPATH=. uv run python tools/findings_tracker.py add \
  --target "<COMPANY>" \
  --summary "Peer comparison: <ratio> is <value> vs industry median <median> (<direction> outlier)" \
  --detail "Outlier score <SCORE>, n=<N>, method=<SCORE_METHOD>, threshold=<THRESHOLD>" \
  --type financial \
  --evidence "SEC:CIK<NUM>:<ACCESSION>" \
  --claim-type synthesis \
  --source-quote "SEC:CIK<NUM>:<ACCESSION>:<EXACT_SOURCE_ROWS_USED_WITH_PERIODS_AND_VALUES>" \
  --sources edgar \
  --confidence medium
```

The quote must preserve the exact load-bearing filing rows or footnote excerpt;
put the calculation method in `--detail`, never in `--source-quote`.

Connect target to peer group if structural relationships discovered:
```bash
PYTHONPATH=. uv run python tools/findings_tracker.py connect \
  --person-a "<TARGET>" --person-b "<PEER>" \
  --type corporate \
  --description "Same SIC <CODE>, compared in peer analysis" \
  --entity-a-type inc --entity-b-type inc
```

`connect` auto-registers any endpoint that isn't already an entity, but it can only guess `entity_type='unknown'` — so pass `--entity-a-type`/`--entity-b-type` (here `inc`) to type the companies correctly. For the richest graph, register each company explicitly with its jurisdiction so peer-group and shared-officer patterns are queryable:

```bash
uv run python tools/entity_tracker.py add-entity --name "<PEER>" --entity-type inc --jurisdiction <STATE> --source "edgar"
```

### 6. Create Leads

For companies with unexplained outliers (≥2 outlier flags with no innocent explanation):

```bash
PYTHONPATH=. uv run python tools/lead_tracker.py add \
  --title "Financial forensics: <COMPANY> — <N> statistical outliers vs peers: <top outlier>" \
  --category financial --priority medium \
  --target "<COMPANY>" --source "agent:compare-peers"
```

### 7. Output

```
## $compare-peers: <TARGET> vs <N> Peers

### Peer Group
| Company | Ticker | SIC | Revenue | Selection Rationale |
|---------|--------|-----|---------|-------------------|

### Comparison Matrix
| Ratio | Target | Peer 1 | Peer 2 | ... | Median | Target vs Median |
|-------|--------|--------|--------|-----|--------|-----------------|

### Statistical Outliers
| Company | Ratio | Value | Median | z-score | Forensic Note |
|---------|-------|-------|--------|---------|---------------|

### Forensic Hypotheses
1. **<Company> <ratio> outlier** — Hypothesis #<ID>
   - Observation: ...
   - Hypothesis: ...
   - Innocent explanation: ...
   - Falsification: ...
   - Search plan: ...

### Summary
- Companies analyzed: N
- Outliers detected: N
- Hypotheses generated: N
- Leads created: N
- Findings recorded: N
```

## Stop Conditions

- All companies processed (or skipped with reason)
- Comparison matrix generated
- Hypotheses created for all forensically significant outliers
- Findings recorded for notable deviations
- Output complete

## Key Analytical Frameworks

When generating hypotheses, consider applying relevant frameworks from `research/craft-research/frameworks/`:
- **Revenue Recognition Anomalies** — DSO outliers, receivables/revenue divergence
- **Cash Flow / Earnings Divergence** — accruals ratio outliers, cash conversion anomalies
- **Related-Party Transaction Scoring** — margin outliers that might indicate RPT-driven pricing
- **Corporate Governance Red Flags** — compound governance indicators across the peer group
- **Peripheral Collapse** — margin outliers suggesting pass-through or shell entity behavior
