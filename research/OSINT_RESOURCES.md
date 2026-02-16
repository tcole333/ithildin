# OSINT Resources Reference

Tools, techniques, and databases for open-source intelligence research. Organized for agent use — each section includes what it's good for and when to use it.

**For agents**: Consult this when your local databases don't have what you need. The open web has far more information than our Epstein-specific datasets.

---

## Search Techniques

### Google Dorking
Use advanced operators to find specific document types, domains, or content:

```
site:sec.gov "jeffrey epstein"              # SEC filings mentioning Epstein
filetype:pdf "enhanced education"           # PDF documents about Enhanced Education
site:govinfo.gov "BCCI" filetype:pdf        # Government reports on BCCI
"457 madison" "registered agent"            # Registered agent records at 457 Madison
inurl:docket "epstein" site:courtlistener.com  # Court dockets
"gratitude america" 990                     # Tax filings for Gratitude America
site:littlesis.org "jeffrey epstein"        # Pre-mapped relationships
```

### Specialized Search Engines
- **Google Scholar**: Academic papers, legal opinions, cited cases
- **Wayback Machine** (web.archive.org): Historical snapshots of websites that have been modified or taken down
- **DocumentCloud**: Searchable document repository (journalism-sourced)

---

## People Research

### LittleSis (littlesis.org)
- **What**: Database of connections between powerful people and organizations. Pre-mapped relationships with amounts, dates, categories
- **Epstein**: Entity 36043, 500+ relationships including financial amounts
- **Tool**: `python tools/query_littlesis.py search/entity/relationships/connections`
- **When to use**: First stop when investigating a person's corporate/political connections

### Professional Registrations & Licenses
- **State bar associations**: Verify lawyer status, disciplinary history
- **FINRA BrokerCheck** (brokercheck.finra.org): Broker/dealer registrations, disciplinary history, employment history
- **SEC Investment Adviser Search** (adviserinfo.sec.gov): Registered investment advisers
- **State medical boards**: Physician licenses

### Public Records Aggregators
- **PACER** (pacer.uscourts.gov): Federal court filings ($0.10/page)
- **CourtListener** (courtlistener.com): Free federal court data — `python tools/query_courtlistener.py`
- **Unicourt**: State and federal court records (freemium)
- **State court systems**: Each state has its own e-filing system

### Biographical / Social
- **Wikipedia**: Starting point only (can be edited by subjects/PR firms). Always verify against primary sources
- **Crunchbase**: Startup/VC connections, funding rounds, board memberships
- **LinkedIn** (via Google cache/Wayback): Professional history (requires login for live data)

---

## Corporate / Financial Research

### SEC EDGAR (sec.gov/edgar)
- **What**: All SEC filings — 10-K, 10-Q, DEF 14A (proxy), 13-F (holdings), 8-K (events)
- **EFTS full-text search**: `python tools/query_edgar.py search "query"`
- **Company lookup**: `python tools/query_edgar.py company <CIK>`
- **When to use**: Any publicly traded company connection, executive compensation, board memberships, related-party transactions

### OpenCorporates (opencorporates.com)
- **What**: Largest open database of companies — 200M+ companies from 140+ jurisdictions
- **When to use**: International corporate registry searches, especially for jurisdictions we don't have local tools for
- **Access**: Web search or API (limited free tier)

### Corporate Registries (Local Tools)
- Florida SunBiz: `python tools/ingest_florida.py` / `python tools/query_registry.py search --jurisdiction fl`
- New York DoS: `python tools/ingest_newyork.py` / `python tools/query_registry.py search --jurisdiction ny`
- New Mexico SoS: `python tools/ingest_newmexico.py` / `python tools/query_registry.py search --jurisdiction nm`
- **Add more**: `/add-registry` skill for new jurisdictions

### OCCRP Aleph (aleph.occrp.org)
- **What**: Global corporate registries, leaks, court records, sanctions lists
- **Tool**: `python tools/query_aleph.py search/entity/expand`
- **When to use**: International entities, especially those in offshore jurisdictions or sanctioned entities

### Financial Regulators
- **FDIC BankFind** (fdic.gov/bankfind): Bank information, historical data
- **OCC** (occ.gov): National bank enforcement actions
- **NYDFS** (dfs.ny.gov): State banking enforcement (Deutsche Bank consent order)
- **FinCEN** (fincen.gov): BSA/AML enforcement actions, FinCEN Files

### IRS / Nonprofits
- **ProPublica Nonprofit Explorer**: `python tools/query_990.py search/ein/filings`
- **GuideStar/Candid** (candid.org): Deeper nonprofit data (freemium)
- **Charity Navigator**: Basic nonprofit ratings and financials
- **State AG charity registries**: Many states require charity registration

### Beneficial Ownership
- **FinCEN BOI Registry** (fincen.gov/boi): New US beneficial ownership reporting (as of 2024)
- **UK Companies House** (companieshouse.gov.uk): Free, includes person of significant control
- **EU Anti-Money Laundering Directive registers**: Varies by member state

---

## Aviation Research

### FAA Registry
- **What**: Complete US aircraft registration database — owner names, addresses, N-numbers
- **Tool**: `python tools/ingest_faa.py download && python tools/ingest_faa.py ingest`
- **Search**: `python tools/ingest_faa.py search/n-number/address`
- **Key targets**: N908JE (727), N212JE (Gulfstream), JEGE INC, PLAN D LLC

### Flight Tracking
- **ADS-B Exchange** (adsbexchange.com): Real-time and historical flight tracking. No filtering of government/military
- **FlightAware** (flightaware.com): Flight tracking with historical data (freemium)
- **FlightRadar24** (flightradar24.com): Global flight tracking
- **When to use**: When you have an N-number and need to track where an aircraft has been

### Aviation Records
- **NTSB** (ntsb.gov): Accident/incident reports
- **FAA Airmen Certification** (faa.gov): Pilot license lookups
- **ICAO Aircraft Type Designators**: Aircraft type identification

---

## Archives & Document Repositories

### Government Archives
- **National Archives** (archives.gov): Federal records, presidential libraries
- **GPO/GovInfo** (govinfo.gov): Congressional reports, federal register, CFR
- **FBI Vault** (vault.fbi.gov): FOIA-released FBI files
- **CIA FOIA** (cia.gov/readingroom): Declassified CIA documents
- **State Department FOIA**: Historical diplomatic cables

### Investigation-Specific
- **DugganUSA API**: `python tools/duggan_search.py` — 204K+ docs across all 12 DOJ datasets
- **DOJ Vol 11**: `python tools/query_doj.py` — 331K OCR'd pages
- **LMSBAND**: `python tools/query_lmsband.py` — 60K files, 851K entities
- **Ingested Reports**: `python tools/query_investigations.py` — FTS5 search of downloaded investigation PDFs

### Journalism Archives
- **DocumentCloud** (documentcloud.org): Source documents from journalism investigations
- **ICIJ Offshore Leaks**: `python tools/query_icij.py` — 800K offshore entities (Neo4j)
- **OCCRP Aleph**: `python tools/query_aleph.py` — investigative journalism datasets

---

## FOIA Strategy

### When to File
- Federal agencies: 5 USC 552 (FOIA)
- State agencies: State-specific public records laws
- Most responsive: FBI (backlog but systematic), State Department, Treasury

### Key FOIA Targets for Epstein Investigation
1. **FBI**: Full investigation files (beyond vault releases)
2. **Treasury/FinCEN**: SARs filed on Epstein accounts
3. **State Department**: Rod-Larsen diplomatic cables, IPI diplomatic correspondence
4. **Secret Service**: White House visitor logs (Clinton era)
5. **FAA**: Flight plan filings for Epstein aircraft
6. **IRS**: Tax-exempt determination letters for Epstein entities
7. **NYDFS**: Full Deutsche Bank examination files

### Filing Tips
- Be specific: narrow requests get faster responses
- Reference EFTA IDs or specific document dates when possible
- Appeal all denials — agencies over-redact by default
- Fee waivers available for journalistic/educational purposes

---

## Research Methodology

### Timeline Building
1. Start with known dates (court filings, financial transactions, email timestamps)
2. Map against world events (elections, investigations, market events)
3. Look for clusters — communication spikes around specific events reveal relationships
4. Note gaps — periods of silence may indicate channel changes (ProtonMail, intermediaries)

### Following the Money
1. Start with known entities (KPMG report entities, 990 filings)
2. Trace officer/director overlaps across entities
3. Map financial flows: source → intermediary → destination
4. Check jurisdiction choices — they reveal intent
5. Cross-reference with ICIJ offshore data

### Network Mapping
1. Start with LittleSis pre-mapped relationships
2. Supplement with co-occurrence analysis from LMSBAND/Unified DB
3. Add corporate relationships from registry tools
4. Weight by evidence quality (primary source > media report)
5. Identify broker nodes — people connecting otherwise separate clusters

### Source Triangulation
For any claim to be considered reliable:
1. Primary source document (EFTA, court filing, financial record)
2. Independent corroboration from a different source type
3. Consistency with known timeline and patterns
4. No contradictory evidence from equally reliable sources

**Remember**: Same document in 3 databases = redundancy, NOT corroboration. True corroboration requires independent sources.
