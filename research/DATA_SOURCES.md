# Data Source Strategy

## Overview

This document outlines the data sources available for investigative research, their integration status, and priority sources to add. The platform is designed to support financial investigations with a current focus on 1980s-1990s data.

---

## Current Data Sources (Operational)

### NARA Electronic Records
| File | Records | Status | Research Value |
|------|---------|--------|----------------|
| ORS.CUM.MAR91 | 949,346 | Parsed, Neo4j loader ready | Insider trading patterns (Forms 3/4/5) |
| STACK.BDD | 24,019 | Parsed | Broker-dealer relationships, addresses |
| STACK.CIN | 55,652 | Parsed | Company registration index, CIK/SIC codes |
| STACK.IA | 39,294 | Parsed | Investment adviser network |

### SEC News Digests
| Period | Status | Content |
|--------|--------|---------|
| 1987-1989 | 705 PDFs downloaded, extraction in progress | 13D/14D beneficial ownership filings |

### ICIJ Offshore Leaks
- **Status**: Connected via Neo4j (localhost:7689)
- **Content**: ~800K entities from Panama Papers, Paradise Papers, Offshore Leaks, Bahamas Leaks
- **Use**: Cross-reference SEC filers with offshore entities

---

## Priority Data Sources to Add

### Tier 1: High Value, Readily Accessible

#### 1. PACER Court Records
**Value**: Connection goldmines - defendant/plaintiff lists reveal hidden relationships
**Key Case Types**:
- Bankruptcy cases (creditor lists, asset disclosures)
- Criminal securities fraud cases
- Civil SEC enforcement actions
- Shareholder derivative suits

**Access**: PACER account ($0.10/page), bulk via RECAP archive
**Data Points**: Parties, attorneys, creditors, related cases
**Format**: PDF dockets, some structured data

#### 2. State Corporate Registrations
**Value**: Officers/directors/registered agents not in SEC filings

| State | Portal | Priority |
|-------|--------|----------|
| Delaware | corp.delaware.gov | Most public companies, LLCs |
| Nevada | nvsos.gov | Privacy-focused entities |
| Wyoming | wyoming.gov/sos | Anonymous LLCs |
| New York | dos.ny.gov | Financial firms |

**Data Points**: Officers, directors, registered agent, formation date, status
**Format**: Varies by state, some APIs available

#### 3. Form 990s (Nonprofit Filings)
**Value**: Foundation officers, grant recipients, charitable giving patterns
**Sources**:
- ProPublica Nonprofit Explorer (bulk download)
- IRS EO BMF extract
- Foundation Center 990 Finder

**Data Points**: Officers, highest-paid employees, grants made/received, related entities

#### 4. FINRA BrokerCheck
**Value**: Employment history, disciplinary actions for registered persons
**Coverage**: Current and historical (varies)
**Access**: Web scraping, some bulk data available
**Data Points**: Employment timeline, licenses, disclosures, complaints

#### 5. FEC Campaign Finance
**Value**: Political connections, lobbying relationships
**Sources**:
- FEC bulk data (fec.gov)
- OpenSecrets API

**Data Points**: Donors, recipients, amounts, dates, employer/occupation

---

### Tier 2: Medium Effort, High Value

#### 6. Property Records
**Value**: Wealth flows not visible in securities filings

| Jurisdiction | System | Notes |
|--------------|--------|-------|
| NYC | ACRIS | Manhattan real estate |
| Florida | County PAPA systems | High-value properties |
| Delaware | Land Records | Corporate headquarters |

**Data Points**: Sales, mortgages, liens, parties, prices, dates

#### 7. UCC Filings
**Value**: Secured transactions reveal lending relationships, collateral arrangements
**Sources**: State SOS offices, commercial aggregators
**Use Case**: Track financing flows, identify lenders

#### 8. FDIC Failed Bank Records
**Value**: Bank failure documentation - connections to financial networks
**Sources**:
- FDIC Research Database
- RTC archives (via NARA)
- OTS records

#### 9. Congressional Hearing Transcripts
**Value**: Witness lists and testimony name names, provide timelines
**Sources**:
- GPO.gov (recent)
- HeinOnline (historical)
- ProQuest Congressional

---

### Tier 3: Harder But Potentially Revealing

#### 10. FARA Filings (Foreign Agents)
**Value**: Foreign government/entity connections
**Source**: fara.gov

#### 11. Historical Newspaper Archives
**Value**: Details that didn't make official filings

| Source | Coverage | Notes |
|--------|----------|-------|
| ProQuest Historical | WSJ, NYT, LAT | Best for period research |
| American Banker | Banking industry | Financial coverage |
| Newspapers.com | Regional papers | Local business coverage |

#### 12. Delaware Court of Chancery
**Value**: Shareholder derivative suits, M&A litigation reveal players and roles
**Source**: courts.delaware.gov (limited online), physical records

---

## Data Integration Architecture

```
                    ┌─────────────────────────────────────────┐
                    │         UNIFIED RESEARCH GRAPH          │
                    │         (Neo4j localhost:7687)          │
                    └─────────────────────────────────────────┘
                                        │
        ┌───────────────┬───────────────┼───────────────┬───────────────┐
        │               │               │               │               │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │   SEC   │    │  NARA   │    │  ICIJ   │    │  PACER  │    │  State  │
   │ Digests │    │  ORS    │    │Offshore │    │ Courts  │    │  Corps  │
   └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘

                    Entity Resolution Layer
                    ├── Name normalization
                    ├── CUSIP/CIK matching
                    ├── Address clustering
                    └── Relationship inference
```

### Node Types to Add

```cypher
// Court Cases
(:CourtCase {
  case_id: String,
  case_name: String,
  court: String,
  filed_date: Date,
  case_type: String  // bankruptcy, criminal, civil
})

// Corporate Registrations
(:CorporateRegistration {
  entity_name: String,
  state: String,
  formation_date: Date,
  status: String,
  registered_agent: String
})

// Nonprofit
(:Nonprofit {
  ein: String,
  name: String,
  fiscal_year: Integer,
  total_revenue: Float,
  total_assets: Float
})

// Political Contribution
(:Contribution {
  fec_id: String,
  amount: Float,
  date: Date,
  recipient: String
})

// Relationships
(:Person)-[:PARTY_TO {role: String}]->(:CourtCase)
(:Person)-[:OFFICER_OF]->(:CorporateRegistration)
(:Person)-[:CONTRIBUTED {amount: Float}]->(:Politician|Committee)
(:Person)-[:EMPLOYED_BY {start_date, end_date}]->(:Organization)
```

---

## Adding a New Data Source

1. **Assess value**: Does this source provide new entity/relationship data?
2. **Check access**: Is bulk download available? API? Web scraping needed?
3. **Design schema**: What node types and relationships will be created?
4. **Build parser**: Create parser in `tools/` following existing patterns
5. **Add loader**: Extend `neo4j_loader.py` with new load method
6. **Document**: Add to this file and update CLAUDE.md schema docs

---

## Success Metrics

1. **Entity Coverage**: Key investigation entities have data from 3+ sources
2. **Connection Density**: Average 5+ documented connections per entity
3. **Source Diversity**: Data from SEC, courts, state records, nonprofits, FINRA
4. **Lead Generation**: Research leads generated from cross-source connections
