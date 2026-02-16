# Reference Guide

Reference documentation for SEC data analysis. Entity data (people, companies, organizations)
is stored in Neo4j - use the `search_aliases()` method or `--search-alias` CLI command.

---

## SEC Form Types

| Form | Description |
|------|-------------|
| 13D | Beneficial ownership > 5% (with intent) |
| 13G | Beneficial ownership > 5% (passive) |
| 14D-1 | Tender offer by bidder |
| 14D-9 | Target company response to tender |
| Form 3 | Initial insider ownership statement |
| Form 4 | Change in insider ownership |
| Form 5 | Annual insider ownership summary |

## ORS Transaction Codes

| Code | Meaning |
|------|---------|
| P | Purchase |
| S | Sale |
| T | Transfer |
| B | Beneficial ownership |
| U | Unknown/Unspecified |
| H | Holdings (initial) |
| 3 | Form 3 filing |

## ORS Relationship Codes

| Code | Meaning |
|------|---------|
| D | Director |
| O | Officer |
| B | Beneficial Owner (10%+) |
| VP | Vice President |
| AF | Affiliated Person |
| CB | Control/Board |

## Jurisdictions of Interest

Offshore jurisdictions commonly used for corporate structures:

| Jurisdiction | Notes |
|--------------|-------|
| Panama | Panama Papers primary source |
| British Virgin Islands | Common holding company jurisdiction |
| Cayman Islands | Investment fund jurisdiction |
| Bahamas | Bahamas Leaks source |
| Isle of Man | UK offshore jurisdiction |
| Jersey | Channel Islands |
| Liechtenstein | European tax haven |
| Luxembourg | European corporate structures |

## CUSIP Reference

| Company | CUSIP | Check Digit |
|---------|-------|-------------|
| Pan Am Corp | 697757 | 10 |
| Emery Air Freight | 291101 | varies |
| TWA | 893349 | 10 |
| Purolator Courier | 746380 | varies |

## Investigation Phases

1. **Initial Profile** - Basic entity documentation
2. **Source Search** - Query all data sources
3. **Cross-Reference** - Match across sources
4. **Network Mapping** - Identify connections
5. **Pattern Analysis** - Detect coordination/parking
6. **Documentation** - Write findings
