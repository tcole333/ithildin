# Coordinated Positions Investigation

## Overview

Analysis of potential sub-5% coordination patterns across multiple companies, where multiple filers may have coordinated to avoid 13D disclosure triggers.

## Detection Methodology

See [METHODOLOGY.md](../../METHODOLOGY.md) for scoring criteria.

### Indicators
1. Multiple filers within 30-day window
2. Combined ownership 4-4.9%
3. Shared broker/dealer
4. Known business associations

## Companies Under Analysis

| Company | CUSIP | Period | Score | Status |
|---------|-------|--------|-------|--------|
| Pan Am Corp | 697757 | 1987-1988 | TBD | Pending |
| Emery Air Freight | 291101 | 1988-1989 | TBD | Pending |
| TWA | 893349 | 1985-1988 | TBD | Pending |

## Known Coordination Networks

### Drexel Network
- Michael Milken (Drexel's junk bond chief)
- Carl Icahn (corporate raider, Drexel client)
- Ivan Boesky (arbitrageur, Drexel co-conspirator/client - not an employee)
- [Other associates TBD]

### Towers Financial Network
- Steven Hoffenberg
- [Associates TBD]

## Analysis Approach

1. For each target company:
   - Extract all 13D filers from SEC digests
   - Cross-reference with ORS insider data
   - Identify common brokers via BDD
   - Score for coordination indicators

2. For each potential coordination:
   - Document timing
   - Calculate combined ownership
   - Identify shared connections
   - Score and prioritize

## Findings

[See findings/ folder]

## Leads

[See leads/ folder]
