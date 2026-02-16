# Offshore Connections Investigation

## Overview

Cross-referencing SEC filers and insiders with ICIJ Offshore Leaks database to identify potential offshore structures used by key players.

## Data Sources

### Offshore Leaks Database
- Location: Neo4j @ bolt://localhost:7689
- Credentials: Default (neo4j/neo4j or as configured)
- Content: Panama Papers, Paradise Papers, Offshore Leaks, Bahamas Leaks

### SEC Data
- NARA ORS: Insider trading records
- SEC Digests: Beneficial ownership filings
- Neo4j @ localhost:7687: Unified SEC graph

## Matching Methodology

See [METHODOLOGY.md](../../METHODOLOGY.md) for scoring criteria.

### Name Matching Process
1. Normalize SEC names (strip INC, CORP, etc.)
2. Query Offshore Leaks with variations
3. Score matches based on criteria
4. Document findings with confidence levels

## Priority Targets

| Name | Type | SEC Records | Offshore Matches | Status |
|------|------|-------------|------------------|--------|
| Michael Milken | Person | 903 ORS | TBD | Pending |
| Carl Icahn | Person | 178 ORS | TBD | Pending |
| Drexel Burnham | Org | Multiple | TBD | Pending |
| Towers Financial | Company | TBD | TBD | Pending |

## Sample Queries

### Offshore Leaks Queries
```cypher
// Search for person
MATCH (e:Entity)-[r]-(o:Officer)
WHERE o.name CONTAINS 'MILKEN'
RETURN e, r, o

// Search for company
MATCH (e:Entity)
WHERE e.name CONTAINS 'DREXEL'
RETURN e
```

### Cross-Reference Query
```cypher
// Find SEC filer in offshore data
MATCH (sec:Person {name: 'MILKEN MICHAEL'})
WITH sec
MATCH (off:Officer)
WHERE off.name CONTAINS 'MILKEN'
RETURN sec.name, off.name, off.node_id
```

## Jurisdictions of Interest

| Jurisdiction | Leak Source | Priority |
|--------------|-------------|----------|
| Panama | Panama Papers | High |
| BVI | Multiple | High |
| Cayman Islands | Multiple | High |
| Bahamas | Bahamas Leaks | Medium |

## Findings

[See findings/ folder]

## Leads

[See leads/ folder]
