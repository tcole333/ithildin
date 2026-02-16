# Pan Am Corp Takeover Investigation

## Overview

Investigation into the 1987-1988 Pan Am Corp takeover attempts, focusing on beneficial ownership accumulation patterns and potential coordination among filers.

## Key Facts

| Field | Value |
|-------|-------|
| Target | Pan Am Corp |
| CUSIP | 697757 |
| Ticker | PN |
| Period | 1987-1988 |
| Status | Active |

## Known Beneficial Owners

| Filer | First Filing | Peak % | Status | Profile |
|-------|--------------|--------|--------|---------|
| Resorts International | July 1987 | >10% (Beneficial Owner) | Divested July 1987 | [Profile](../../entities/companies/resorts_international.md) |

### Resorts International Divestiture Summary
- **Period**: July 13-21, 1987 (7 trading days)
- **Debentures Sold**: ~$500M face value
- **Common Stock Sold**: ~115M shares
- **Timing Significance**: Same week as Trump's Resorts International takeover
- **Filed**: August 7, 1987

## Investigation Questions

1. Who were the major beneficial owners during the takeover period?
2. Is there evidence of sub-5% coordination?
3. What role did Drexel Burnham Lambert play in financing?
4. Are there offshore connections to any filers?

## Data Sources

- NARA ORS: `data/nara-filings/pan_am_ors.txt` (129 records)
- SEC Digests: Search for CUSIP 697757 or "PAN AM"
- Neo4j: `MATCH (c:Company {cusip: "697757"}) RETURN c`

## Timeline

[See timeline.md for detailed chronology]

## Findings

[See findings/ folder]

## Leads

[See leads/ folder]
