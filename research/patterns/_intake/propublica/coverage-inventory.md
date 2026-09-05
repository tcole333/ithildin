# Ithildin Source Coverage Inventory (our side of the adapter-gap diff)
Compiled 2026-07-28 from docs/modules/* headers + tools/ listing + docstring spot-checks.

## What we HAVE (source → tool)

**Corporate structure & ownership**
- SEC EDGAR full-text + filings: query_edgar.py, query_sec.py; enforcement: query_sec_enforcement.py (+ingest)
- State registries: CA/CO/DC/FL(sunbiz)/MD/NM/NY(DOS)/OH/TX/MA/MI/NJ/NV/TN/WY/DE/PR + unified router query_registry.py
- International: UK Companies House (ingest), France, Israel, Hong Kong, Cyprus, Switzerland (zefix), Panama (ingest), USVI, Peru (SUNARP/SUNAT)
- OpenCorporates (rate-limited), GLEIF LEI, ICIJ Offshore Leaks, OpenSanctions (PEPs/debarment), LittleSis, Aleph (local OpenAleph), SWIFT BIC
- UCC liens: FL + NM

**Money: political**
- FEC: query_fec.py; Senate LDA lobbying; FARA; Congress.gov; GovInfo; Federal Register; Senate Finance archive

**Money: nonprofit**
- IRS 990: query_990.py + ProPublica Nonprofit Explorer API (query_990_propublica.py) + bulk/XML ingest (ingest_990_bulk/xml, parse_990_xml)

**Money: government spending**
- USASpending, FPDS-NG, HigherGov, SAM.gov (API + bulk), PPP/EIDL (DuckDB local)

**Health sector**
- Medicare provider spending (data.cms.gov), Medicaid T-MSIS (DuckDB), CMS Open Payments, NPI→registry trace pipeline (trace_provider.py)

**Financial institutions & markets**
- FDIC, FINRA BrokerCheck, market data (query_market.py), financial_ratios, FinCEN Files (leak corpus)

**Courts & legal**
- CourtListener/RECAP (v4), NYSCEF, Florida ACIS, state-court unified router (query_state_courts.py, in flight this branch), HUDOC/ECHR, military justice + BCMR/BCNR, FJC IDB (via legal module)

**Property & assets**
- ACRIS (NYC), Cook, Miami-Dade (property+recorder), Bexar, Harris, LA, Orleans, NC OneMap, MassGIS, MD, FL DOR; unified router query_property.py (in flight); FAA aircraft registry (ingest_faa.py — registration, NOT flight tracking)

**People & disclosures**
- ProPublica Trump-appointee financial disclosures (ingest_propublica_disclosures.py — 1,573 appointees; NOT congressional/judicial disclosures generally)
- Dehashed (paid), Maigret username enum, selector_pivot orchestrator

**Documents & corpora**
- DocumentCloud, MuckRock (+index), DOJ/LMSBAND/Unified/kabasshouse Epstein corpora, government releases DB (DOJ/SEC PRs), reporting corpus (epstein_reporting), GDELT (query_gdelt.py), Wayback CDX, OffshoreAlert search, PDF ingest+OCR pipeline

**Infra/OSINT**
- crt.sh, Shodan, URLScan, git repo analysis

**Blockchain**: Etherscan, Solscan, Dune
**IP**: USPTO patents + trademarks + assignments
**Peru**: El Peruano, Infogob, OEFA, SEACE, Contraloría

## Preliminary GAP hypotheses (validate against agent reports before writing adapter-gaps.md)

1. **Flight tracking / ADS-B history** (FlightAware AeroAPI, ADS-B Exchange, OpenSky, JetSpy-style). We have FAA *registration* only. Needed for: Thomas/Crow-style travel reconstruction, silo-join tail-number patterns. (Judicial-ethics cluster will confirm exact sources ProPublica used.)
2. **Judicial + congressional financial disclosures** (judicial: US Courts financial-disclosure portal / Fix the Court / Free Law Project disclosure DB; congressional: Clerk/Senate eFD, PTRs). Our disclosure tool covers Trump appointees only. Core input to disclosure-gap triangulation.
3. **EPA data family**: ECHO (enforcement/compliance), TRI (toxic release), RSEI (risk model — the Sacrifice Zones source), air-monitor data. Nothing EPA-side currently.
4. **OSHA**: establishment inspections, violations, severe-injury reports (SIR), fatality data. Nothing currently.
5. **Census/ACS demographic denominators**: no adapter. Required for every disparity-rate pattern (rates by race/geo need denominators).
6. **FCC public inspection files** (political ad buys, OPIF API) — Free the Files source. Nothing currently.
7. **Meta/Google ad libraries** (political + issue ads APIs). Nothing currently.
8. **CMS institutional data**: hospital cost reports (HCRIS), Care Compare (nursing homes/hospice — live-discharge rates!), Provider of Services file, Medicare Part D prescriber PUF (check whether query_medicare covers Part D prescriber-level).
9. **State insurance regulators / NAIC** filings & market-conduct exams. Nothing.
10. **Vessel registries** (USCG documented vessels, IMO/Equasis) — yacht joins. Nothing (FAA only).
11. **IRS exempt-org lifecycle**: determination letters, auto-revocation list, Form 8871/8872 (527s) — partially covered via 990s; 527 disclosures likely missing.
12. **Bankruptcy** courts specifically (PACER/RECAP partial via CourtListener; check coverage adequacy for bulk docket denominators).
13. **Workers' comp / state wage-claim data** — state-fragmented; possibly out of scope.
14. **Lobbying at STATE level** (we have federal LDA only).
15. **Property assessment bulk** beyond covered counties — partially in flight via public_records_*.
16. **Court opinion/docket BULK analytics** for denominator construction (RECAP bulk exports?) — check if existing tooling suffices at scale.
17. **CDC WONDER / vital statistics** (maternal mortality-style denominators). Nothing.
18. **HUD datasets** (FHA, LIHTC, housing inspections). Nothing.
19. **Charity regulators beyond IRS**: state AG charity registries (NY CHAR500 etc.). Nothing.
20. **FEC-adjacent**: 24/48-hr independent-expenditure feeds fine via FEC API; scam-PAC detection needs bulk expenditure joins — likely covered.

Rank later by: (a) how many ProPublica patterns each unlocks, (b) fit to active investigations, (c) build cost/access.
