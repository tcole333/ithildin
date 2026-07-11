---
name: audit-contracts
description: Tier 2 comparative procurement analysis — spending acceleration, lobbying correlation, revolving door detection, partnership networks across 3-10 contractors
---

# $audit-contracts

**TIER 2: ANALYSIS AGENT** — This skill performs comparative procurement analysis across a cohort of 3-10 government contractors. It calculates spending growth rates, detects acceleration anomalies, cross-references lobbying expenditures, maps partnership networks, and checks for revolving door patterns. Every hypothesis about procurement irregularity MUST include falsification criteria. See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`.

This is NOT single-contract forensics — use `$analyze-contract` for that. This skill compares spending *patterns* across companies to detect systemic anomalies.

## Arguments

- `$audit-contracts "Palantir Technologies, Anduril Industries, Shield AI, SpaceX, Rocket Lab"` — explicit company list
- `$audit-contracts --thread 3` — extract contractors from investigation thread findings
- `$audit-contracts --sector "defense-tech"` — agent resolves companies from knowledge

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

**From explicit names:** Parse comma-separated list.

**From `--thread N`:** Query investigation.db for companies with contract-related findings:
```bash
PYTHONPATH=. uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('''
    SELECT DISTINCT target_name, COUNT(*) as cnt FROM findings
    WHERE thread_id = ? AND profile_id = ?
    AND (finding_type = 'financial' OR summary LIKE '%contract%' OR summary LIKE '%award%')
    GROUP BY target_name ORDER BY cnt DESC LIMIT 10
''', (N, 'PROFILE')).fetchall()
for r in rows: print(f'{r[1]:4d}  {r[0]}')
"
```

**Resolve each company to a full USASpending name:**
```bash
uv run python tools/query_usaspending.py search "<COMPANY>" --output $WORKDIR/<slug>-search.json
```

**Important:** Use the full legal name from search results, not short names. "Palantir" matches the wrong entity; "Palantir Technologies" works correctly.

Also check SAM.gov bulk for UEI:
```bash
uv run python tools/ingest_sam.py search "<COMPANY>" --output $WORKDIR/<slug>-sam.json
```

### 2. Pull Spending Timelines

For each company:
```bash
uv run python tools/query_usaspending.py timeline "<FULL_NAME>" --output $WORKDIR/<slug>-timeline.json
uv run python tools/query_usaspending.py recipient "<FULL_NAME>" --output $WORKDIR/<slug>-recipient.json
```

The `timeline` command returns aggregated spending per fiscal year. The `recipient` command returns agency-level breakdown.

### 3. Calculate Growth Rates and Detect Anomalies

Parse each timeline JSON and compute:
- **FY-over-FY growth rates** for the last 3-4 years
- **CAGR** (compound annual growth rate) over the full period
- **Acceleration flag**: Recent year growth > 2x historical CAGR? Flag as ACCELERATION
- **Rank** companies by most recent FY growth rate

**Growth rate thresholds:**
- >50% YoY: **HIGH** — unusual for government contractors (typical sector growth is 5-15%)
- 25-50% YoY: **MEDIUM** — noteworthy, especially if sustained
- <25% YoY: Normal range for defense/government services

**Record finding for each company with HIGH growth flag:**
```bash
PYTHONPATH=. uv run python tools/findings_tracker.py add \
  --target "<COMPANY>" \
  --summary "Procurement acceleration: <COMPANY> federal spending grew <X>% YoY (FY<PREV> $<AMT1> → FY<CURR> $<AMT2>), <N>x the sector average" \
  --type financial \
  --evidence "USASPENDING:<COMPANY>" \
  --claim-type synthesis \
  --source-quote "USASpending timeline data FY<YEARS>" \
  --sources usaspending \
  --confidence medium
```

### 4. Cross-Reference Lobbying

For each company:
```bash
uv run python tools/query_lobbying.py client "<COMPANY>" --output $WORKDIR/<slug>-lobbying.json
```

Extract lobbying spend by year from the filings. Look for:
- **Pre-acceleration lobbying increases**: Did lobbying spend rise 1-2 years before contract growth?
- **Issue code shifts**: Did lobbying focus shift to new agencies before contracts from those agencies appeared?
- **Registrant changes**: Did the company change lobbying firms around the same time as contract acceleration?

Record timing correlations as findings (`claim-type: synthesis`, confidence: `medium`).

### 5. Partnership Network Analysis (HigherGov)

For companies with known HigherGov awardee keys:
```bash
uv run python tools/query_highergov.py partnership --awardee-key <KEY> --output $WORKDIR/<slug>-partners.json
```

Look for:
- **Co-bidding patterns**: Do any two companies in the cohort frequently team together?
- **Vehicle concentration**: Does one company dominate a specific contract vehicle?
- **Subcontractor relationships**: Is Company A frequently a sub to Company B (or vice versa)?

### 6. Financial Cross-Check (Public Companies Only)

For public companies in the cohort, extract SEC financial data:
```bash
uv run python tools/query_edgar.py sections <TICKER> --section income_statement --output $WORKDIR/<slug>-income.json
uv run python tools/query_edgar.py sections <TICKER> --section balance_sheet --output $WORKDIR/<slug>-balance.json
uv run python tools/financial_ratios.py analyze $WORKDIR/<slug>-income.json $WORKDIR/<slug>-balance.json --output $WORKDIR/<slug>-ratios.json
```

Cross-check: Does SEC-reported government segment revenue track with USASpending obligations? Large discrepancies (>20% difference) may indicate:
- Revenue from classified programs (not in USASpending)
- Timing differences (obligated vs. recognized)
- International government revenue (not USASpending)

### 7. Revolving Door Check

Search investigation.db for known revolving door connections to the cohort companies:
```bash
PYTHONPATH=. uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
for company in ['<COMPANY1>', '<COMPANY2>', ...]:
    rows = db.execute('''
        SELECT target_name, summary FROM findings
        WHERE (target_name LIKE ? OR summary LIKE ?)
        AND (summary LIKE '%revolving%' OR summary LIKE '%former government%'
             OR summary LIKE '%Pentagon%' OR summary LIKE '%appointee%'
             OR summary LIKE '%deputy%' OR summary LIKE '%joined from%')
    ''', (f'%{company}%', f'%{company}%')).fetchall()
    if rows:
        print(f'{company}: {len(rows)} revolving door findings')
        for r in rows[:3]:
            print(f'  {r[\"summary\"][:100]}')
"
```

Also check if any officers from the companies appear in FEC donor records tied to relevant political committees:
```bash
uv run python tools/query_fec.py donor "<OFFICER_NAME>" --output $WORKDIR/<slug>-fec-<officer>.json
```

### 8. Generate Hypotheses

For each anomalous pattern, generate a hypothesis following the standard framework:

1. **Observation**: "[Company] federal spending grew [X]% in FY[YEAR], [N]x the sector average of [Y]%"
2. **Forensic hypothesis**: What non-market factor could explain this acceleration?
3. **Best innocent explanation**: Genuine demand increase, new capability, or contract consolidation
4. **Falsification criterion**: What evidence would disprove the concerning interpretation?
5. **Search plan**: Specific next steps (e.g., "check FPDS for competition type on largest awards")

Record via `hypothesis_tracker.py add`.

### 9. Record Findings and Create Leads

- One finding per anomalous growth pattern
- One finding per lobbying-contract timing correlation
- One finding per revolving door connection discovered
- Leads for: companies needing `$analyze-contract` deep dives, specific awards to trace, partnership patterns to investigate

### 10. Output

```
## $audit-contracts — Comparative Procurement Analysis

### Cohort: <N> Companies

### Spending Timeline
| Company | FY2022 | FY2023 | FY2024 | FY2025 | CAGR | FY24→25 | Flag |
|---------|--------|--------|--------|--------|------|---------|------|

### Agency Breakdown (Most Recent FY)
| Company | DoD | HHS | DHS | DOJ | Treasury | Other | Total |
|---------|-----|-----|-----|-----|----------|-------|-------|

### Growth Anomaly Ranking
| Rank | Company | FY24→25 Growth | Sector Avg | Anomaly Score |
|------|---------|---------------|------------|---------------|

### Lobbying-Contract Correlation
| Company | Lobby Spend (2yr) | Contract Growth | Timing |
|---------|------------------|-----------------|--------|

### Partnership Network
[Cross-teaming patterns within the cohort]

### Revolving Door Connections
| Company | Person | Government Role | Corporate Role | Dates |
|---------|--------|----------------|----------------|-------|

### Financial Cross-Check (Public Companies)
| Company | SEC Gov Revenue | USASpending | Delta | Note |
|---------|----------------|-------------|-------|------|

### Forensic Hypotheses
1. **[Company] acceleration hypothesis** — Hypothesis #ID
   - Observation: ...
   - Hypothesis: ...
   - Innocent explanation: ...
   - Falsification: ...
   - Search plan: ...

### Summary
- Companies analyzed: N
- Growth anomalies detected: N
- Lobbying correlations: N
- Revolving door connections: N
- Hypotheses generated: N
- Leads created: N
- Findings recorded: N
```

## Stop Conditions

- All companies' timelines extracted and growth rates calculated
- Lobbying data cross-referenced for all companies
- Partnership network checked (for companies with HigherGov access)
- Financial cross-check completed for public companies
- Revolving door check run against investigation.db
- Hypotheses generated for all HIGH-severity anomalies
- Findings recorded, leads spawned

## Relationship to Other Skills

- **`$analyze-contract`** (Tier 1): Use for deep single-contract forensics when this skill identifies a specific award worth investigating
- **`$compare-peers`** (Tier 2): Use for financial ratio comparison if the audit reveals companies with unusual financial profiles
- **`$screen-targets`** (Tier 0): Use for quick financial health check before running the full procurement audit
- **`$trace-grants`** (Tier 2): Use if companies have significant nonprofit/foundation arms (e.g., defense think tanks)
- **`$investigate-person`** (Tier 1): Use for revolving door individuals identified by the audit

