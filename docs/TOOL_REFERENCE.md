# Tool Reference

Complete CLI examples for all investigation tools. Referenced from CLAUDE.md.

Run `python tools/source_report.py` for live data source status.

## Core Investigation Tools

### Queue System (SQLite-first)
```bash
uv run python scripts/queue_tools.py status
uv run python scripts/queue_tools.py pause --by "human"
uv run python scripts/queue_tools.py resume --by "human"
uv run python scripts/queue_tools.py submit --type echo --domain system --payload '{"message":"hello"}'
uv run python scripts/queue_tools.py enqueue-triage --batch-size 20
uv run python scripts/queue_tools.py enqueue-lead 42 --sources findings --created-by "human"
uv run python scripts/queue_tools.py agents
uv run python scripts/queue_tools.py metrics
uv run python scripts/queue_tools.py mark-stale --grace-seconds 60
uv run python scripts/agent_worker.py --persona echo
uv run python scripts/agent_worker.py --persona surveyor
uv run python scripts/agent_worker.py --persona document_miner
uv run python scripts/agent_worker.py --persona entity_tracer
uv run python scripts/agent_worker.py --persona pattern_spotter
uv run python scripts/agent_worker.py --persona synthesist
uv run python scripts/agent_worker.py --persona investigation_orchestrator
uv run python scripts/agent_worker.py --persona dossier_writer
uv run python scripts/agent_worker.py --persona dossier_freshness_audit
uv run python scripts/agent_worker.py --persona visual_exporter
uv run python scripts/agent_worker.py --persona content_pipeline
uv run python scripts/agent_worker.py --persona network_analyst
uv run python scripts/agent_worker.py --persona timeline_analyst
uv run python scripts/agent_worker.py --persona systemic_analyst
uv run python scripts/agent_worker.py --persona explainer_writer
uv run python scripts/agent_worker.py --persona contextual_analyst
uv run python scripts/agent_worker.py --persona editor
uv run python scripts/agent_worker.py --persona dedupe_review
uv run python scripts/agent_worker.py --persona verify_finding
uv run python scripts/agent_worker.py --persona tool_build
uv run python scripts/agent_worker.py --persona bug_fix
uv run python scripts/agent_worker.py --persona source_ingest
uv run python scripts/agent_worker.py --persona registry_add
uv run python scripts/trigger_engine.py run --dry-run
uv run python scripts/trigger_engine.py status

# Override content output directory for writer personas
ITHILDIN_CONTENT_ROOT=site/content uv run python scripts/agent_worker.py --persona contextual_analyst
```

### Leads
```bash
python tools/lead_tracker.py add --title "..." --category person --priority high --target "Name"
python tools/lead_tracker.py list --status open --priority high
python tools/lead_tracker.py claim 42
python tools/lead_tracker.py note 42 "Found 50 ProtonMail docs in DOJ Vol 11"
python tools/lead_tracker.py complete 42 --findings "Summary of results"
python tools/lead_tracker.py search "rod-larsen"
python tools/lead_tracker.py evidence EFTA02336502   # Find all items referencing this
python tools/lead_tracker.py next                    # Get highest-priority open lead
python tools/lead_tracker.py stats
```

### Infrastructure Requests
```bash
python tools/infra_tracker.py add --title "Integrate FinCEN Files" --type new_source \
  --description "200K+ transactions including Deutsche Bank SARs relevant to Epstein flows" \
  --source-name "FinCEN Files" --source-url "https://..." \
  --data-type "financial transactions" --access-method bulk_download --auth none \
  --coverage "200K+ transactions" --priority high \
  --discovered-by "agent:deep-investigate" --discovered-during "Wave 11"
python tools/infra_tracker.py list --status open
python tools/infra_tracker.py show 12
python tools/infra_tracker.py claim 12                # status → evaluating
python tools/infra_tracker.py evaluate 12 --probe-results "API works, no auth" --proceed  # → in_progress
python tools/infra_tracker.py note 12 "Tool built, testing against known targets"
python tools/infra_tracker.py complete 12 --tool-file "tools/query_fincen.py" \
  --files-modified tools/query_fincen.py CLAUDE.md --summary "Built FinCEN integration"
python tools/infra_tracker.py reject 12 --reason "Requires paid subscription"
python tools/infra_tracker.py search "registry"
python tools/infra_tracker.py next --type new_source
python tools/infra_tracker.py stats
python tools/infra_tracker.py block-lead 42 12        # Lead #42 blocked on infra #12
```

### Findings (with provenance)
```bash
python tools/findings_tracker.py add --target "Rod-Larsen" --type financial \
  --summary "..." --evidence EFTA02336502 --claim-type paraphrase \
  --source-quote "EFTA02336502:craft purchase 18M through bjorn"
python tools/findings_tracker.py connect --person-a "Epstein" --person-b "Rod-Larsen" --type financial
python tools/findings_tracker.py connections "Epstein" --depth 2
python tools/findings_tracker.py search "gates foundation"
python tools/findings_tracker.py timeline --target "Rod-Larsen"
```

### Audit & Verification
```bash
python tools/findings_tracker.py unverified             # List findings needing human review
python tools/findings_tracker.py provenance 42           # Full provenance chain for finding #42
python tools/findings_tracker.py verify 42               # Mark as human-verified
python tools/findings_tracker.py dispute 42 --reason "Quote doesn't match source"
python tools/findings_tracker.py retract 42 --reason "Hallucinated by agent"  # Cascades to connections
python tools/findings_tracker.py correct 42 --field summary --value "New text" --reason "Amount was 15M not 18M"
python tools/findings_tracker.py audit 42 --table findings  # Show correction history
```

## Analysis Tools

### Hypothesis Tracker
```bash
python tools/hypothesis_tracker.py add --title "USVI cluster suggests structural role" \
  --pattern-type structural --description "4 unrelated targets all have USVI entities 2012-2015" \
  --predicted-evidence "Shared registered agent or formation attorney" \
  --search-plan "1. query_registry.py search USVI agent  2. ingest_usvi.py agent overlap"
python tools/hypothesis_tracker.py list [--status proposed] [--pattern-type structural]
python tools/hypothesis_tracker.py show 5
python tools/hypothesis_tracker.py investigate --id 5 --lead-id 42
python tools/hypothesis_tracker.py confirm --id 5 --evidence "findings:412,415" --reason "Shared agent confirmed"
python tools/hypothesis_tracker.py refute --id 5 --evidence "findings:420" --reason "No overlap found"
python tools/hypothesis_tracker.py supersede --id 5 --by 8 --reason "Broader hypothesis covers this"
python tools/hypothesis_tracker.py evidence --id 5 --for "findings:425"
python tools/hypothesis_tracker.py search "USVI"
python tools/hypothesis_tracker.py stats
```

### Tag Manager
```bash
python tools/tag_manager.py tag --table findings --id 412 --type pattern --value "dependency_cycle:stage_3"
python tools/tag_manager.py bulk-tag --table findings --ids 412,413,414 --type cluster --value "karp_nexus"
python tools/tag_manager.py find --type pattern --value "dependency*"   # glob match
python tools/tag_manager.py list-values --type theme                    # all theme tag values
python tools/tag_manager.py record --table findings --id 412            # all tags on a record
python tools/tag_manager.py remove --table findings --id 412 --type pattern --value "dependency_cycle:stage_3"
python tools/tag_manager.py stats
```

### Event Timeline
```bash
python tools/event_timeline.py seed                                     # populate ~100 key dates
python tools/event_timeline.py add --date 2019-07-06 --name "Epstein arrested" --category arrest
python tools/event_timeline.py window --start 2019-07-01 --end 2019-07-15  # events + findings in range
python tools/event_timeline.py near --finding-id 412 --days 14          # events near a finding
python tools/event_timeline.py near --date 2019-03-08 --days 7          # events near a date
python tools/event_timeline.py list [--category legal] [--year 2019] [-v]
python tools/event_timeline.py stats
```

### Graph Tools
```bash
python tools/graph_tools.py centrality [--metric degree|betweenness|closeness] [--top 30] [--cache]
python tools/graph_tools.py components [--min-size 3]
python tools/graph_tools.py bridges
python tools/graph_tools.py paths "Leon Black" "Ehud Barak" [--max-hops 6]
python tools/graph_tools.py neighbors "Leon Black" [--depth 2]
python tools/graph_tools.py holes [--min-degree 5]                      # structural holes / brokerage
python tools/graph_tools.py cliques [--min-size 4]                      # dense subgraphs
python tools/graph_tools.py stats
```

### Analysis Export
```bash
python tools/analysis_export.py connections-graph --output $WORKDIR/graph.json
python tools/analysis_export.py findings-dump [--thread-id 5] [--min-confidence medium] --output $WORKDIR/findings.json
python tools/analysis_export.py timeline-export [--start 2019-01-01] [--end 2019-12-31] --output $WORKDIR/timeline.json
python tools/analysis_export.py entity-network --output $WORKDIR/entities.json
python tools/analysis_export.py coverage-matrix [--top 50] --output $WORKDIR/coverage.json
python tools/analysis_export.py thread-summary [--thread-id 5] --output $WORKDIR/threads.json
python tools/analysis_export.py analysis-state --output $WORKDIR/state.json
```

### Thread Population (one-time migration)
```bash
uv run python scripts/populate_threads.py --dry-run    # preview assignments
uv run python scripts/populate_threads.py              # apply thread assignments
uv run python scripts/populate_threads.py --stats      # show current assignment counts
```

## Document Corpus

### DugganUSA (204K+ docs, all 12 DOJ datasets)
```bash
python tools/duggan_search.py "query" --output /tmp/results.json
```

### DOJ Vol 11 (331K pages, FTS5, EFTA IDs)
```bash
python tools/query_doj.py search "query" -n 50 --output /tmp/results.json
```

### LMSBAND (60K files, 851K entities)
```bash
python tools/query_lmsband.py search "query" --output /tmp/results.json
python tools/query_lmsband.py entities "name" --output /tmp/results.json
python tools/query_lmsband.py cooccurrence "name1" "name2" --output /tmp/results.json
```

### Unified DB (70K docs, 56K entities, 107K triples)
```bash
python tools/query_unified.py emails "query" --output /tmp/results.json
python tools/query_unified.py docs "query" --output /tmp/results.json
python tools/query_unified.py entities "name" --output /tmp/results.json
python tools/query_unified.py triples "subject" --output /tmp/results.json
```

### Epstein Files 20K (25,800 House Oversight docs)
```bash
python tools/ingest_epstein_20k.py search "query" --output /tmp/results.json
python tools/ingest_epstein_20k.py doc HOUSE_OVERSIGHT_028601
python tools/ingest_epstein_20k.py stats
python tools/ingest_epstein_20k.py overlap    # Cross-ref with existing DBs
```

### Investigation Reports (ingested PDFs, FTS5)
```bash
python tools/ingest_pdf.py ingest <path.pdf> --title "..." --source "GPO" --category congressional
python tools/query_investigations.py search "query" --output /tmp/results.json
python tools/query_investigations.py list
```

## Corporate/Financial Registries

### Unified Registry (CO, DC, FL, NY, NM, PA, VI, UK, CA — registry.db)
Note: Delaware (DE) and Hong Kong (HK) use separate tools via OpenCorporates API.
```bash
python tools/query_registry.py search "entity name"
python tools/query_registry.py search "Epstein" --jurisdiction fl
python tools/query_registry.py officers "Darren Indyke"
python tools/query_registry.py address "457 Madison"
python tools/query_registry.py agent "CT Corporation"
python tools/query_registry.py filings <entity_id>
python tools/query_registry.py stats
```

### State-Specific Ingest
```bash
# Florida SunBiz (SFTP bulk)
python tools/ingest_florida.py download && python tools/ingest_florida.py ingest

# New York (SODA API)
python tools/ingest_newyork.py search "Epstein"
python tools/ingest_newyork.py search-officers "Indyke"
python tools/ingest_newyork.py ingest-batch "Epstein" --with-filings

# New Mexico (REST API, 4s rate limit)
python tools/ingest_newmexico.py search "Zorro Ranch"
python tools/ingest_newmexico.py detail <internal_id>
python tools/ingest_newmexico.py ingest-batch "Zorro"

# California (BE Public Search API — needs API key: CA_SOS_API_KEY)
python tools/ingest_california.py search "PARAFI CAPITAL"
python tools/ingest_california.py search "Epstein" --begins-with
python tools/ingest_california.py search "Apollo" --date-start 1990-01-01 --date-end 2020-12-31
python tools/ingest_california.py search-number 202150010654
python tools/ingest_california.py detail 202150010654
python tools/ingest_california.py ingest-entity 202150010654
python tools/ingest_california.py ingest-batch "Epstein"
python tools/ingest_california.py server-status

# Colorado (SODA API — 1.3M+ entities, no auth)
python tools/ingest_colorado.py search "Epstein" --limit 100
python tools/ingest_colorado.py search "Zorro Ranch"
python tools/ingest_colorado.py search-agent "Corporation Service"
python tools/ingest_colorado.py search-address "Denver"
python tools/ingest_colorado.py ingest-entity 19871701849
python tools/ingest_colorado.py ingest-batch "Epstein"

# DC (ArcGIS FeatureServer — 492K entities, no auth + CorpOnline detail API)
python tools/ingest_dc.py search "Capital Athletic Foundation"
python tools/ingest_dc.py search "Epstein" --output /tmp/dc-epstein.json
python tools/ingest_dc.py search "Abramoff" --type nonprofit --status active
python tools/ingest_dc.py search-agent "Corporation Service Company" --limit 50
python tools/ingest_dc.py search-address "Dupont Circle"
python tools/ingest_dc.py detail <corponline-uuid>  # Enriched detail (principals, filings, NAICS)
python tools/ingest_dc.py ingest-entity L04091
python tools/ingest_dc.py ingest-batch "Capital Athletic" "Epstein"
python tools/ingest_dc.py stats

# Maryland SDAT (manual CAPTCHA required — not automated)
# Bulk data via SpecPrint Inc: $2,100/week (410-561-9600)
# This tool provides manual instructions only (no automated scraping)
python tools/ingest_maryland.py search "Capital Athletic Foundation" --output /tmp/md-search.json
python tools/ingest_maryland.py detail D02357507 --output /tmp/md-detail.json
python tools/ingest_maryland.py ingest-entity D02357507    # Manual process
python tools/ingest_maryland.py ingest-batch "Eshkol Academy" "Landfair Capital"

# USVI (Catalyst scraper)
python tools/ingest_usvi.py search "LSJE"
python tools/ingest_usvi.py detail 581737 --name "LSJE"
python tools/ingest_usvi.py ingest-batch "LSJE" "Maple" "Nautilus"

# Panama (ICIJ + Aleph hybrid)
python tools/ingest_panama.py search "Epstein"
python tools/ingest_panama.py ingest-batch "Epstein" --expand

# UK Companies House (needs API key)
python tools/ingest_uk_companies_house.py search "Epstein"
python tools/ingest_uk_companies_house.py company 12345678
python tools/ingest_uk_companies_house.py officers 12345678
python tools/ingest_uk_companies_house.py psc 12345678
python tools/ingest_uk_companies_house.py officer-search "Leon Black"
python tools/ingest_uk_companies_house.py ingest-batch "Apollo"

# Israeli Corporations Authority (720K+ companies, no auth)
python tools/query_israel.py search "Carbyne" --output /tmp/israel-carbyne.json
python tools/query_israel.py search "Ehud Barak" --limit 50
python tools/query_israel.py company 515106409  # By registration number
python tools/query_israel.py stats

# French Company Registry / SIRENE (all French companies, no auth)
python tools/query_france.py search "Soffer Avocats" --output /tmp/france-soffer.json
python tools/query_france.py search "Ron Soffer" --limit 10
python tools/query_france.py company 380866657  # By SIREN number
python tools/query_france.py search "Epstein" --naf 69.10Z  # Filter by activity code (69.10Z = legal)
python tools/query_france.py address "4 Rue Quentin-Bauchart" --postal 75008
python tools/query_france.py naf 64.20Z --postal 75008  # Activities of holding companies in 75008

# HUDOC — European Court of Human Rights (20K+ judgments, no auth)
python tools/query_hudoc.py search "Soffer, avocat" --output /tmp/hudoc-soffer.json
python tools/query_hudoc.py search "Epstein" --limit 20
python tools/query_hudoc.py case 001-99808  # Broadhurst Investments v Romania
python tools/query_hudoc.py appno "34868/03"  # By application number
python tools/query_hudoc.py text 001-99808  # Full text of judgment/decision
python tools/query_hudoc.py text 001-99808 --output /tmp/broadhurst-text.json  # Save full text
python tools/query_hudoc.py respondent ISR --limit 50  # All cases against Israel

# Delaware (via OpenCorporates API — requires OPENCORPORATES_API_KEY)
# Free research key: https://opencorporates.com/api_accounts/new
# Paid plans: £2,250/year minimum
python tools/query_delaware.py search "EPSTEIN"
python tools/query_delaware.py search "APOLLO" --inactive
python tools/query_delaware.py search "WEXNER" --per-page 100
python tools/query_delaware.py entity 1234567  # Company number
python tools/query_delaware.py filings 1234567
python tools/query_delaware.py batch-entities 1234567 2345678 3456789

# Hong Kong (via OpenCorporates API — requires OPENCORPORATES_API_KEY)
# Same API key as Delaware - free research key at link above
python tools/query_hongkong.py search "Mast Industries"
python tools/query_hongkong.py search "EPSTEIN" --inactive
python tools/query_hongkong.py entity 1234567  # Company number
python tools/query_hongkong.py filings 1234567
python tools/query_hongkong.py batch-entities 1234567 2345678

# Cyprus (via OpenCorporates API — requires OPENCORPORATES_API_KEY)
# Same API key as Delaware/Hong Kong - major Russia-linked offshore hub
# Key targets: Xitrans Finance Ltd (Rybolovlev), Deripaska entities
python tools/query_cyprus.py search "Xitrans"
python tools/query_cyprus.py search "EPSTEIN" --inactive
python tools/query_cyprus.py entity 12345  # Company registration number
python tools/query_cyprus.py filings 12345
python tools/query_cyprus.py batch-entities 12345 23456 34567
```

### UCC Filings
```bash
python tools/query_registry.py ucc-search "LSJE LLC"
python tools/query_registry.py ucc-filing <filing_id>
python tools/query_registry.py ucc-collateral "aircraft"
python tools/query_registry.py ucc-party "JPMorgan" --role secured

# Florida FLR (mostly IRS tax liens, NOT commercial UCC)
python tools/ingest_ucc_florida.py download && python tools/ingest_ucc_florida.py ingest
python tools/ingest_ucc_florida.py search "Epstein"

# New Mexico UCC
python tools/ingest_ucc_newmexico.py search "Zorro Ranch"
python tools/ingest_ucc_newmexico.py detail <internal_id>
```

### Swiss Zefix (SPARQL endpoint, 30K+ entities, no auth)
```bash
python tools/query_zefix.py search "UBS"
python tools/query_zefix.py search "ILEX" --limit 20
python tools/query_zefix.py company "https://register.ld.admin.ch/zefix/company/20243"
python tools/query_zefix.py uid CHE107848049
python tools/query_zefix.py stats
```

### GLEIF LEI (corporate hierarchy, no auth)
```bash
python tools/query_gleif.py search "Apollo Global"
python tools/query_gleif.py hierarchy 54930054P2G7ZJB0KM79  # Apollo full tree
python tools/query_gleif.py cross-ref  # All investigation.db entities
```

## Public Records

### SEC EDGAR (full-text search, no auth, needs User-Agent)
```bash
python tools/query_edgar.py search "jeffrey epstein" --size 20
python tools/query_edgar.py search "leon black" "gratitude america" --forms "10-K,DEF 14A"
python tools/query_edgar.py search "epstein" --forms "DEF 14A" --facets
python tools/query_edgar.py lookup "apollo global"     # Name → CIK
python tools/query_edgar.py company 0001411494         # Apollo by CIK
python tools/query_edgar.py filings 0001411494 --form "DEF 14A"
python tools/query_edgar.py insider 1032666 --limit 20  # Leon Black
python tools/query_edgar.py read "https://..." --lines 200
```
Key CIKs: Apollo=1411494/1858681, JPM=19617, Leon Black=1032666, Wexner=921462, Deutsche Bank=1159508, L Brands=701985

### CourtListener (federal courts, token in .env)
```bash
python tools/query_courtlistener.py search "Jeffrey Epstein"
python tools/query_courtlistener.py cases "Epstein" --court nysd
python tools/query_courtlistener.py docket 16066603
python tools/query_courtlistener.py party "Ghislaine Maxwell"
python tools/query_courtlistener.py opinions "Epstein" --court ca2
```

### ProPublica 990 (nonprofit filings)
```bash
python tools/query_990.py search "Gratitude America"
python tools/query_990.py ein 660789697
python tools/query_990.py filings 660789697
python tools/query_990.py batch "Epstein" "Indyke"
```

### IRS 990 XML (Schedule I grants + Schedule R related orgs)
```bash
python tools/ingest_990_xml.py download-index            # cache IRS index CSVs (2017-2025)
python tools/ingest_990_xml.py lookup 660789697           # show filings for an EIN
python tools/ingest_990_xml.py lookup --tracked           # all 10 tracked EINs
python tools/ingest_990_xml.py ingest 660789697           # download XML + parse + store
python tools/ingest_990_xml.py ingest --tracked           # ingest all tracked EINs (~60 min)
python tools/ingest_990_xml.py grants --filer 660789697   # grants MADE by this org
python tools/ingest_990_xml.py grants --recipient "Harvard"  # grants RECEIVED
python tools/ingest_990_xml.py related 237320631          # related orgs (Schedule R)
python tools/ingest_990_xml.py search "Epstein"           # keyword search grants+related
python tools/ingest_990_xml.py stats                      # summary
```

### IRS 990 Bulk Grant Database (all US nonprofits, 2009-2024)
```bash
python tools/ingest_990_bulk.py download-index               # 1.3GB parquet from Giving Tuesday S3
python tools/ingest_990_bulk.py explore-index                # show schema, form types, year range
python tools/ingest_990_bulk.py process --form-type 990PF    # download + parse 990-PF grants (~1.5h)
python tools/ingest_990_bulk.py process --form-type 990      # download + parse 990 grants (~4.5h)
python tools/ingest_990_bulk.py process --form-type 990PF --year-start 2018 --year-end 2018  # single year
python tools/ingest_990_bulk.py resume                       # continue interrupted run
python tools/ingest_990_bulk.py build-fts                    # build FTS5 after bulk load
python tools/ingest_990_bulk.py stats                        # DB stats + process run history

python tools/query_990_bulk.py search "Epstein"              # FTS5 search grants + related orgs
python tools/query_990_bulk.py filer 660789697               # grants MADE by EIN
python tools/query_990_bulk.py recipient "Gratitude"         # grants RECEIVED by name (FTS5)
python tools/query_990_bulk.py recipient-ein 030213226       # grants RECEIVED by EIN
python tools/query_990_bulk.py network 660789697 --depth 2   # BFS grant graph from seed EIN
python tools/query_990_bulk.py co-grantors "MELANOMA RESEARCH ALLIANCE"  # shared funders
python tools/query_990_bulk.py cross-ref                     # match investigation.db entities
python tools/query_990_bulk.py top --by amount --limit 20    # top grantmakers (also: count, recipients, single)
```

### NYC ACRIS (property records, SODA API)
```bash
python tools/query_acris.py party "Jeffrey Epstein"
python tools/query_acris.py address --borough 1 --block 1386 --lot 10  # 9 E 71st
python tools/query_acris.py history --property-name "71st"
python tools/query_acris.py batch-entities
```

### FEC Campaign Finance (API key in .env)
```bash
python tools/query_fec.py donor "Jeffrey Epstein" --limit 20
python tools/query_fec.py employer "Gratitude America"
python tools/query_fec.py address "10021" --name "Epstein"
python tools/query_fec.py batch-persons
```
CRITICAL: Multiple Jeffrey Epsteins — always check employer/address.

### FINRA BrokerCheck (broker registrations, no auth)
```bash
python tools/query_finra.py search "Leon Black" --limit 10
python tools/query_finra.py search "Bear Stearns" --type firm --limit 5
python tools/query_finra.py detail 1047702                     # Full individual record by CRD
python tools/query_finra.py detail 20376 --type firm           # Full firm record
python tools/query_finra.py employment 1047702                 # Employment history only
python tools/query_finra.py disclosures 1047702                # Disciplinary/regulatory events
```
Returns: CRD numbers, employment history with dates, firm affiliations, disclosures (allegations, sanctions), registered states/SROs. Search returns summary; detail/employment/disclosures return full records.

### Federal Lobbying (Senate LDA, no auth)
```bash
python tools/query_lobbying.py client "Apollo Global"
python tools/query_lobbying.py lobbyist "Weingarten"
python tools/query_lobbying.py filings --client "Apollo Global" --year 2018
```

### FARA Foreign Agents (bulk CSV → investigation.db)
```bash
python tools/query_fara.py download && python tools/query_fara.py ingest
python tools/query_fara.py search "Epstein"
python tools/query_fara.py country "Norway"
```

### LittleSis (power networks, no auth, entity 36043=Epstein)
```bash
python tools/query_littlesis.py search "Jeffrey Epstein"
python tools/query_littlesis.py entity 36043
python tools/query_littlesis.py relationships 36043 --category 5  # Donations
```

### OCCRP Aleph (registries, leaks, no auth for public)
```bash
python tools/query_aleph.py search "Jeffrey Epstein" --schema Person
python tools/query_aleph.py search "Financial Trust Company" --schema Company
python tools/query_aleph.py entity <id>
python tools/query_aleph.py expand <id>
```

### ICIJ Offshore Leaks (Neo4j, needs `./scripts/start_icij_db.sh`)
```bash
python tools/query_icij.py search "Epstein"
```

## External APIs

### GDELT (global news, 3mo window, no auth, 6s rate limit)
```bash
python tools/query_gdelt.py articles "Jeffrey Epstein" --limit 50 --timespan 3m
python tools/query_gdelt.py context "Epstein arrest" --timespan 1w
python tools/query_gdelt.py timeline "Jeffrey Epstein" --mode volume
python tools/query_gdelt.py cooccurrence "Jeffrey Epstein" --targets "Bannon,Gates,Wexner"
```

### OpenSanctions (sanctions + PEP, bulk download)
```bash
python tools/query_opensanctions.py download && python tools/query_opensanctions.py ingest
python tools/query_opensanctions.py search "Oleg Deripaska" --topic sanction
python tools/query_opensanctions.py pep-check "Ehud Barak"
python tools/query_opensanctions.py match-entities  # All investigation entities
```

### EpsteinExposed (1,271 persons, 1.5M docs, REST API)
```bash
python tools/ingest_epstein_exposed.py download
python tools/ingest_epstein_exposed.py search "wexner trust"
python tools/ingest_epstein_exposed.py person "leon-black"
python tools/ingest_epstein_exposed.py flights --passenger "clinton" --year 2002
python tools/ingest_epstein_exposed.py match-entities
```

### MuckRock FOIA (project #507, no auth)
```bash
python tools/query_muckrock.py project 507
python tools/query_muckrock.py request 78799  # USMS
python tools/query_muckrock.py download 78799 --dir datasets/muckrock
```

### DocumentCloud (project #216915, no auth)
```bash
python tools/query_documentcloud.py search "Ghislaine Maxwell"
python tools/query_documentcloud.py document 24402693 --full
python tools/query_documentcloud.py text 24402693 --page 5
```

### OffshoreAlert (29K+ offshore court cases, 4,500+ articles, MLATs, regulatory actions)
```bash
# Search (HTML scraping — rich results with scores, excerpts, tags)
uv run python tools/offshorealert_search.py search "deutsche bank" -v
uv run python tools/offshorealert_search.py search "leon black" --output /tmp/oa-results.json
uv run python tools/offshorealert_search.py search "liquid funding bermuda" -a  # all pages

# Extract tagged entities from search results (names, companies, jurisdictions)
uv run python tools/offshorealert_search.py entities "jeffrey epstein" -n 200
uv run python tools/offshorealert_search.py entities "apollo" --output /tmp/oa-entities.json

# API search (lightweight, no login needed, fewer results)
uv run python tools/offshorealert_search.py api-search "epstein"

# NOTE: Individual article pages and PDF downloads are behind reCAPTCHA.
# Use Playwright browser session for full article content.
```

## Specialized

### DS10 Financial (Deutsche Bank, 579 tx, $304M)
```bash
python tools/parse_ds10_financials.py query --entity "Plan D"
python tools/parse_ds10_financials.py query --amount-min 1000000
python tools/parse_ds10_financials.py balances --entity "Haze Trust"
python tools/parse_ds10_financials.py entities
python tools/parse_ds10_financials.py flows
```

### FAA Aircraft Registry
```bash
python tools/ingest_faa.py download && python tools/ingest_faa.py ingest
python tools/ingest_faa.py search "JEGE"
python tools/ingest_faa.py n-number N212JE
```

### FinCEN Files (4.5K tx, 5.5K connections, 2000-2017 SARs)
```bash
python tools/query_fincen.py download          # Download and cache dataset
python tools/query_fincen.py stats
python tools/query_fincen.py search-tx "Deutsche Bank" --output /tmp/fincen-db.json
python tools/query_fincen.py search-connections "singapore" --output /tmp/fincen-sg.json
python tools/query_fincen.py filer "Deutsche Bank" --output /tmp/fincen-filer.json
python tools/query_fincen.py country USA --output /tmp/fincen-usa.json
python tools/query_fincen.py sar 3297 --output /tmp/fincen-sar.json
```

### SWIFT BIC Directory (32K+ banks, BIC→LEI mappings)
```bash
python tools/ingest_bic.py download                     # Download datasets (OpenSanctions + GLEIF)
python tools/ingest_bic.py ingest                       # Download + ingest into bic.db
python tools/ingest_bic.py search "Deutsche Bank" --output /tmp/bic-db.json
python tools/ingest_bic.py search "Rothschild" --output /tmp/bic-rothschild.json
python tools/ingest_bic.py bic DEUTDEFF                 # Lookup specific BIC code
python tools/ingest_bic.py country us --output /tmp/bic-us.json   # List all US banks
python tools/ingest_bic.py lei 529900T8BM49AURSDO55    # BIC→LEI cross-reference
python tools/ingest_bic.py stats                        # Database statistics
```
Use for: Wire routing analysis, resolving BIC codes in DS10 financial transactions, bank identification.

### Auto-Leads (post-wave cross-ref generator)
```bash
python tools/auto_leads.py run        # Generate leads
python tools/auto_leads.py run --dry-run  # Preview
python tools/auto_leads.py stats
```

### Entity Registry (investigation.db)
```sql
SELECT e.name, r.person_name, r.role FROM entities e JOIN entity_roles r ON e.id = r.entity_id;
SELECT e.name FROM entities e JOIN entity_addresses a ON e.id = a.entity_id WHERE a.address LIKE '%457 Madison%';
```

### Entity Dedup / Name Aliases
```bash
# Seed known person/entity variant aliases
uv run python tools/entity_dedup.py seed

# Auto-populate entity_as_person aliases (entity names appearing in connections)
uv run python tools/entity_dedup.py apply

# Add a custom alias
uv run python tools/entity_dedup.py add-alias --canonical "Ehud Barak" --alias "Barak" --type person_variant

# List all aliases (optionally filter)
uv run python tools/entity_dedup.py list-aliases
uv run python tools/entity_dedup.py list-aliases --type entity_as_person
uv run python tools/entity_dedup.py list-aliases --canonical "Jeffrey Epstein"

# Scan for unresolved duplicates
uv run python tools/entity_dedup.py scan

# Show alias stats and unresolved collisions
uv run python tools/entity_dedup.py stats

# Merge entity table records (moves roles, addresses, relations)
uv run python tools/entity_dedup.py merge --keep-id 2 --delete-id 134

# Remove an alias
uv run python tools/entity_dedup.py remove-alias --alias "Barak"
```

Alias types:
- `person_variant`: "Barak" → "Ehud Barak" (spelling/abbreviation variants)
- `entity_variant`: "Gratitude America" → "Gratitude America Ltd" (legal name variants)
- `entity_as_person`: "Goldman Sachs" → entity:123 (org names in connections table)

Name resolution is used by:
- **Write paths**: `add_finding()` and `add_connection()` auto-resolve to canonical names
- **Export pipelines**: `export_network.py`, `export_dossiers.py`, `export_financials.py`, `compute_backlinks.py`
- **Resolver module**: `tools/name_resolver.py` — `resolve_canonical(name)`, `get_all_aliases(canonical)`

### Human Actions
```sql
SELECT * FROM human_actions WHERE status='pending' ORDER BY priority;
```

---

## Queue Dispatcher (Ithildin queue system)

Launches queue agent workers based on pending job types. Config: `scripts/queue_dispatch_config.json`.

```bash
# One-shot: check queue, spawn needed agents
uv run python scripts/queue_dispatcher.py run

# Dry run: show what would spawn without launching
uv run python scripts/queue_dispatcher.py run --dry-run

# Show pending vs active by persona
uv run python scripts/queue_dispatcher.py status

# Daemon mode: poll every N seconds
uv run python scripts/queue_dispatcher.py daemon
uv run python scripts/queue_dispatcher.py daemon --poll-interval 60
```

## Legacy Dispatcher (manual pipeline)

Launches headless Claude Code instances to process queues. Config: `scripts/dispatch_config.json`.

```bash
# One-shot: check queues, launch needed agents
uv run python scripts/dispatcher.py run

# Dry run: show what would launch without launching
uv run python scripts/dispatcher.py run --dry-run

# Show running/recent agents + queue depths + budget
uv run python scripts/dispatcher.py status

# Daemon mode: poll every N seconds (default 300s from config)
uv run python scripts/dispatcher.py daemon
uv run python scripts/dispatcher.py daemon --interval 120

# Stop running agents (all or by ID)
uv run python scripts/dispatcher.py stop
uv run python scripts/dispatcher.py stop 45
```

### Dispatch Rules (priority order)
1. **Triage** — if pending_triage > 0 and no triage running
2. **Build-infra** — if infra open > 0 and no build_infra running
3. **Pursue-lead** — if high/critical open > 0 and research slots available
4. **Auto-leads** — if 10+ completions since last auto_leads run

### dispatch_runs table (investigation.db)
```sql
SELECT * FROM dispatch_runs WHERE status='running';
SELECT run_type, COUNT(*), ROUND(SUM(cost_usd),2) FROM dispatch_runs GROUP BY run_type;
SELECT * FROM dispatch_runs ORDER BY started_at DESC LIMIT 10;
```

---

## pillar_tracker.py — Institutional Pillars & Alumni Dynamics

Models institutions as enabling infrastructure. Tracks career arcs, alumni dispersal,
cohort overlaps, and cross-pillar orchestrator scores.

### Schema Tables
- `persons` — canonical person registry (FK anchor for career_arcs/pillar_scores)
- `institutional_pillars` — institutions categorized by type (banking, legal, government, etc.)
- `career_arcs` — person-to-institution tenure records with dates and roles
- `pillar_events` — institutional-level timeline events (collapses, investigations, etc.)
- `pillar_scores` — computed orchestrator/analysis scores per person

### Institution Management

```bash
# Seed ~37 initial institutions
uv run python tools/pillar_tracker.py seed

# Register a new institution
uv run python tools/pillar_tracker.py register \
    --name "Drexel Burnham Lambert" --type banking --sub-type investment_bank \
    --status dissolved --dissolved 1990 --significance "Junk bond epicenter"

# List institutions (filterable)
uv run python tools/pillar_tracker.py list
uv run python tools/pillar_tracker.py list --type banking
uv run python tools/pillar_tracker.py list --status dissolved

# Show institution details
uv run python tools/pillar_tracker.py show 1
```

### Career Arcs

```bash
# Add a career arc
uv run python tools/pillar_tracker.py arc \
    --person "Leon Black" --pillar "Drexel Burnham Lambert" \
    --role "Managing Director" --seniority senior \
    --start 1977 --end 1990 --exit-type collapse \
    --source "Apollo prospectus"

# View career timeline
uv run python tools/pillar_tracker.py career "Leon Black"

# Bootstrap from existing data (employment connections + entity_roles)
uv run python tools/pillar_tracker.py bootstrap --dry-run
uv run python tools/pillar_tracker.py bootstrap

# Re-bootstrap with alias-aware dedup
uv run python tools/pillar_tracker.py rebootstrap
```

### Institutional Events

```bash
# Add event
uv run python tools/pillar_tracker.py event \
    --pillar "Drexel Burnham Lambert" --date 1990-02-13 \
    --type collapse --description "Filed for bankruptcy"

# View events for institution
uv run python tools/pillar_tracker.py events "Drexel Burnham Lambert"
```

### Alumni & Temporal Analysis

```bash
# All alumni of an institution
uv run python tools/pillar_tracker.py alumni "Kirkland & Ellis"
uv run python tools/pillar_tracker.py alumni "Drexel Burnham Lambert" --active-during 1985-1990

# Cohort overlap (people who were there simultaneously)
uv run python tools/pillar_tracker.py cohort "Drexel Burnham Lambert" --start 1985 --end 1990

# Where alumni went after leaving
uv run python tools/pillar_tracker.py dispersal "Drexel Burnham Lambert"

# Shared institutional tenures between two people
uv run python tools/pillar_tracker.py overlap --person-a "Leon Black" --person-b "Joshua Harris"

# Person timeline (career arcs + pillar events + external events interleaved)
uv run python tools/pillar_tracker.py timeline "Leon Black"
```

### Orchestrator Identification

```bash
# Compute orchestrator scores
uv run python tools/pillar_tracker.py score --top 30
uv run python tools/pillar_tracker.py score --person "Leon Black"
uv run python tools/pillar_tracker.py score --top 10 --cache  # saves to pillar_scores

# Find pillar type gaps in person's career
uv run python tools/pillar_tracker.py gaps --person "Leon Black"

# People spanning 3+ pillar types
uv run python tools/pillar_tracker.py cross-pillar --min-pillars 3
```

Score algorithm: `breadth * 3 + revolving_door * 4 + dispersal * 2 + sqrt(cohort) + log(years + 1)`

### Network Views

```bash
# All people at institutions of a given type
uv run python tools/pillar_tracker.py pillar-network --type legal

# Summary stats
uv run python tools/pillar_tracker.py stats
```

### graph_tools.py Extensions

```bash
# Subgraph filtered to people at pillar type institutions
uv run python tools/graph_tools.py pillar-subgraph --pillar-type legal --metric degree --top 20

# Institution-to-institution graph (edges = shared alumni)
uv run python tools/graph_tools.py institutional-graph --min-shared 2
```

### analysis_export.py Extension

```bash
# Export pillar system data
uv run python tools/analysis_export.py pillar-dump --output $WORKDIR/pillar-data.json
```

### Pillar Types
`banking`, `legal`, `accounting`, `government`, `media`, `operations`, `intelligence`, `philanthropy`, `consulting`, `academia`

### Seniority Levels
`junior`, `mid`, `senior`, `leadership`, `founder`

### Exit Types
`voluntary`, `fired`, `collapse`, `retirement`, `government_appointment`, `indictment`, `unknown`
