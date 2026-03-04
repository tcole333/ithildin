# Data Source Index

Quick reference for all data sources available to investigation agents. Each source has a dedicated doc in this directory with schema, cross-reference potential, and known issues.

Run `uv run python tools/source_report.py` for live availability status.

## Document Corpora (Local)

| Source | Tool | Auth | Records | Description |
|--------|------|------|---------|-------------|
| DOJ Vol 11 | `query_doj.py` | None (local) | 331K pages | OCR'd DOJ Volume 11 release |
| LMSBAND | `query_lmsband.py` | None (local) | 60K files | Files, entities, co-occurrences |
| Unified DB | `query_unified.py` | None (local) | Emails/docs | Consolidated emails, entities, triples |
| Doc-Explorer | sqlite3 | None (local) | 25K docs | RDF triples, entities |
| DugganUSA | `duggan_search.py` | API key | 329K docs | All 12 DOJ datasets via API |
| HF Emails | pandas | None (local) | 4,272 | House Oversight emails (parquet) |
| FBI Files | pandas | None (local) | 8,150 | FBI docs, Textract OCR (parquet) |
| Email Threads | pandas | None (local) | 5,082 | Email thread analysis (parquet) |
| DDoSecrets EML | `search_emails.py` | None (local) | 13K+ | Raw .eml files |
| Barak Emails | `search_emails.py` | None (local) | 1,411 | Ehud Barak email files |
| Investigations DB | `query_investigations.py` | None (local) | Varies | Ingested PDFs with FTS5 |
| FinCEN Files | `query_fincen.py` | None (local) | Varies | Leaked SAR transactions |

## Federal Spending & Contracts

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| [USAspending](usaspending.md) | `query_usaspending.py` | None | All federal spending — contracts, grants, loans |
| SAM.gov | `query_sam.py` | Free API key | Entity registrations, exclusions, contracts |
| SAM.gov Bulk | `ingest_sam.py` | None (local) | 874K entities, 167K exclusions |
| [HigherGov](highergov.md) | `query_highergov.py` | Paid API key | Contract/grant/vehicle intelligence |
| Medicare (CMS) | `query_medicare.py` | None | Provider-level Medicare spending |
| Medicaid T-MSIS | `query_medicaid.py` | None (local) | 227M rows, $1.09T spending |
| SBA PPP Loans | `query_ppp.py` | None (local) | ~11M PPP/EIDL loans |

## Securities & Financial

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| [SEC EDGAR](edgar.md) | `query_edgar.py` | None | Full-text search across all SEC filings |
| [FDIC BankFind](fdic-bankfind.md) | `query_fdic.py` | None | Bank institutions, failures, financials, branches |

## Campaign Finance & Lobbying

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| [FEC](fec.md) | `query_fec.py` | Free API key | Political donations (Schedule A) |
| Federal Lobbying (LDA) | `query_lobbying.py` | None | 1.9M+ lobbying filings |
| FARA | `query_fara.py` | None (local) | Foreign agent registrations |

## Corporate Registries

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| [Unified Registry](registry.md) | `query_registry.py` | None (local) | FL, NY, NM, PA + unified schema |
| Florida | `query_florida_corps.py` | None | Sunbiz corporate registry |
| New York | `query_ny_corps.py` | None | DOS corporate search |
| California | `query_ca_corps.py` | None | SOS business search |
| Texas | `query_tx_corps.py` | None | SOS business search |
| Michigan | `query_mi_corps.py` | None | LARA corporate search |
| Massachusetts | `query_ma_corps.py` | None | SOS corporate search |
| New Jersey | `query_nj_corps.py` | None | Treasury business search |
| New Mexico | `query_nm_corps.py` | None | SOS corporate search |
| Colorado | `query_co_corps.py` | None | SOS corporate search |
| DC | `query_dc_corps.py` | None | DCRA corporate search |
| USVI | `query_usvi_corps.py` | None | USVI corporate registry |
| Panama | `query_panama_corps.py` | None | Registro Publico |
| UK Companies House | `ingest_uk_companies_house.py` | Free API key | UK corporate + PSC beneficial ownership |
| France (SIRENE) | `query_france.py` | None | French company registry |
| Swiss Zefix | `query_zefix.py` | None | Swiss commercial registry (SPARQL) |
| OpenCorporates | `query_opencorporates.py` | Paid API key | DE/HK/CY + global search |

## Legal & Court Records

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| [CourtListener](courtlistener.md) | `query_courtlistener.py` | Free API key | Federal dockets, RECAP archive |
| HUDOC | `query_hudoc.py` | None | ECHR case database |

## Sanctions & Watchlists

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| [OpenSanctions](opensanctions.md) | `query_opensanctions.py` | None (local) | Global sanctions/PEP/debarment graph |

## Property & Land Records

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| NYC ACRIS | `query_acris.py` | None | NYC property transactions (SODA) |

## People & Networks

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| LittleSis | `query_littlesis.py` | None | Power network relationships |
| Maigret | `maigret` | None | Username enumeration |
| Dehashed | `query_dehashed.py` | Paid (limited) | Breach data search |

## Infrastructure Recon

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| crt.sh | `query_crtsh.py` | None | Certificate Transparency logs |
| Wayback Machine | `query_wayback.py` | None | Historical web snapshots |
| URLScan.io | `query_urlscan.py` | Free (search) | Passive web scans |
| Shodan | `query_shodan.py` | Paid API key | Internet device search, DNS, SSL |

## Other

| Source | Tool | Auth | Description |
|--------|------|------|-------------|
| ICIJ Offshore Leaks | `query_icij.py` | None (Neo4j) | ~800K offshore entities |
| FAA Registry | `ingest_faa.py` | None (local) | Aircraft registration |
| DocumentCloud | `query_documentcloud.py` | None | Public document archive |
| MuckRock FOIA | `query_muckrock.py` | None | FOIA request metadata |
| GDELT | `query_gdelt.py` | None | Global news events |
| IRS 990 | `query_990.py` | None | Nonprofit tax filings |
