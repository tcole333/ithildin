# Emery Air Freight Takeover Investigation

## Overview

Investigation into the 1988-1989 Emery Air Freight Corp acquisition by Consolidated Freightways, examining insider trading patterns and beneficial ownership.

## Key Facts

| Field | Value |
|-------|-------|
| Target | Emery Air Freight Corp |
| CUSIP | 291101 |
| Ticker | EAF |
| Period | 1988-1989 |
| Acquirer | Consolidated Freightways |
| Status | Active |

## Known Insiders

From ORS data (57 records in `data/nara-filings/emery_ors.txt`):
- EMERY JOHN C JR (Director)
- STUECK CLIFFORD J (Officer)
- MCCARTHY DENIS M (Officer)
- BOESCH WILLIAM R (Officer/VP)
- WAGNER ROBERT P (Officer)
- And others...

## Investigation Questions

1. What was the insider trading pattern before the acquisition?
2. Were there unusual accumulations by beneficial owners?
3. Any coordination patterns among filers?
4. Connections to Drexel or other known players?

## Data Sources

- NARA ORS: `data/nara-filings/emery_ors.txt` (57 records)
- SEC Digests: Search for CUSIP 291101 or "EMERY"
- Neo4j: `MATCH (c:Company {cusip: "291101"}) RETURN c`

## Timeline

[See timeline.md for detailed chronology]

## Findings

[See findings/ folder]

## Leads

[See leads/ folder]
