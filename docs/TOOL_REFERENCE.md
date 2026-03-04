# Tool Reference

Complete CLI examples for all investigation tools. Referenced from CLAUDE.md.

Run `python tools/source_report.py` for live data source status.

## Canonical Source Names

When using `--sources` on `findings_tracker.py add`, use these canonical names. Using consistent names enables provenance tracking and source coverage analysis.

| Source Name | Tool(s) | Description |
|-------------|---------|-------------|
| `web_search` | WebSearch, WebFetch | Open web research |
| `doj_vol11` | query_doj.py | DOJ Vol 11 document corpus |
| `duggan` | duggan_search.py | Duggan USA corpus |
| `lmsband` | query_lmsband.py | LMSBAND document corpus |
| `unified_db` | query_unified.py | Unified document database |
| `fec` | query_fec.py | FEC campaign finance |
| `edgar` | query_edgar.py | SEC EDGAR filings |
| `courtlistener` | query_courtlistener.py | CourtListener court records |
| `990` | query_990.py | ProPublica 990 nonprofits |
| `registry` | query_registry.py | Unified corporate registry |
| `usaspending` | query_usaspending.py | USASpending federal contracts/grants |
| `sam_gov` | query_sam.py | SAM.gov API |
| `sam_bulk` | ingest_sam.py | SAM.gov bulk data (local SQLite) |
| `lobbying` | query_lobbying.py | LDA lobbying disclosures |
| `fara` | query_fara.py | FARA foreign agent registrations |
| `littlesis` | query_littlesis.py | LittleSis relationship maps |
| `gdelt` | query_gdelt.py | GDELT global news |
| `aleph` | query_aleph.py | OCCRP Aleph |
| `icij` | query_icij.py | ICIJ offshore leaks |
| `acris` | query_acris.py | NYC ACRIS property records |
| `gleif` | query_gleif.py | GLEIF LEI corporate hierarchy |
| `opensanctions` | query_opensanctions.py | OpenSanctions PEP/sanctions |
| `shodan` | query_shodan.py | Shodan internet devices |
| `crtsh` | query_crtsh.py | crt.sh certificate transparency |
| `wayback` | query_wayback.py | Wayback Machine |
| `urlscan` | query_urlscan.py | URLScan.io |
| `medicaid` | query_medicaid.py | Medicare/Medicaid spending |
| `highergov` | query_highergov.py | HigherGov contracts/grants |
| `documentcloud` | query_documentcloud.py | DocumentCloud |
| `muckrock` | query_muckrock.py | MuckRock FOIA |
| `fincen` | query_fincen.py | FinCEN filings |
| `opencorporates` | query_delaware/hongkong/cyprus.py | OpenCorporates API |
| `hudoc` | query_hudoc.py | ECHR case database |
| `france_sirene` | query_france.py | French SIRENE registry |
| `fl_sunbiz` | query_florida.py, ingest_florida.py | Florida SunBiz |
| `ny_dos` | query_nydos.py | New York DOS |
| `ca_sos` | query_california.py | California SOS |
| `tx_comptroller` | query_texas.py | Texas Comptroller |
| `mi_lara` | query_michigan.py | Michigan LARA |
| `nj_rev` | query_newjersey.py | New Jersey Revenue |
| `ma_corps` | query_massachusetts.py | Massachusetts Corporations |
| `nv_sos` | query_nevada.py | Nevada SOS |
| `nm_sos` | ingest_newmexico.py | New Mexico SOS |
| `dc_dlcp` | ingest_dc.py | DC DLCP |
| `usvi` | ingest_usvi.py | US Virgin Islands |
| `ds10_financial` | parse_ds10_financials.py | DS10 financial records |
| `ucc` | query_registry.py ucc-search | UCC filings |
| `faa` | ingest_faa.py | FAA aircraft registry |
| `uk_companies_house` | ingest_uk_companies_house.py | UK Companies House |
| `investigations_db` | query_investigations.py | Ingested investigation reports |
| `analysis_run` | (synthesis findings) | Agent analysis/synthesis |
| `panama_rp` | query_panama.py | Panama public registry |
| `zefix` | query_zefix.py | Swiss commercial registry |

**Important**: Use these exact names. The hook validates `--sources` is present, and `findings_tracker.py` warns on unknown source names. If you need a new source name, add it to `VALID_SOURCES` in `tools/findings_tracker.py`.

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
ITHILDIN_CONTENT_ROOT=content uv run python scripts/agent_worker.py --persona contextual_analyst
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
  --description "200K+ transactions including suspicious activity reports relevant to investigation" \
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
python tools/findings_tracker.py connect --person-a "PERSON_A" --person-b "PERSON_B" --type financial
python tools/findings_tracker.py connections "PERSON_NAME" --depth 2
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
python tools/event_timeline.py add --date 2019-07-06 --name "EVENT_NAME" --category arrest
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
python tools/graph_tools.py paths "PERSON_A" "PERSON_B" [--max-hops 6]
python tools/graph_tools.py neighbors "PERSON_NAME" [--depth 2]
python tools/graph_tools.py holes [--min-degree 5]                      # structural holes / brokerage
python tools/graph_tools.py cliques [--min-size 4]                      # dense subgraphs
python tools/graph_tools.py triangles [--top 50] [--min-strength medium] [--rel-type financial]  # open triads / closure gaps
python tools/graph_tools.py clustering [--min-degree 2] [--top 50]      # local clustering coefficients
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

### House Oversight Files 20K (25,800 House Oversight docs)
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
python tools/query_registry.py search "QUERY" --jurisdiction fl
python tools/query_registry.py officers "Darren Indyke"
python tools/query_registry.py address "ADDRESS"
python tools/query_registry.py agent "CT Corporation"
python tools/query_registry.py filings <entity_id>
python tools/query_registry.py stats
```

### State-Specific Ingest
```bash
# Florida SunBiz (SFTP bulk)
python tools/ingest_florida.py download && python tools/ingest_florida.py ingest

# New York (SODA API — bulk data)
python tools/ingest_newyork.py search "QUERY"
python tools/ingest_newyork.py search-officers "PERSON_NAME"
python tools/ingest_newyork.py ingest-batch "QUERY" --with-filings

# New York DOS Public Inquiry (REST API — entity detail, filings, names)
python tools/query_nydos.py search "HOME CARE" --status Active --output /tmp/ny-homecare.json
python tools/query_nydos.py search "QUERY" --match Contains --output /tmp/ny-results.json
python tools/query_nydos.py search "873065" --by-id --output /tmp/ny-dosid.json
python tools/query_nydos.py entity 873065 --filings --names --output /tmp/ny-entity.json
python tools/query_nydos.py filings 873065 --output /tmp/ny-filings.json
python tools/query_nydos.py names 873065 --output /tmp/ny-names.json
python tools/query_nydos.py ingest 873065                          # Single entity → registry.db
python tools/query_nydos.py ingest-search "HOME CARE" --status Active --limit 50  # Batch ingest

# Medicaid Provider Spending (T-MSIS 2018-2024, 227M rows)
python tools/query_medicaid.py stats                                             # Dataset overview
python tools/query_medicaid.py top-billers --limit 20 --output /tmp/top.json
python tools/query_medicaid.py top-codes --limit 20 --output /tmp/codes.json
python tools/query_medicaid.py provider 1962650622 --output /tmp/provider.json   # Provider detail
python tools/query_medicaid.py provider 1962650622 --timeline                    # Monthly timeline
python tools/query_medicaid.py code T1019 --limit 20 --output /tmp/t1019.json   # HCPCS code analysis
python tools/query_medicaid.py network 1376097303 --output /tmp/net.json         # Billing network
python tools/query_medicaid.py anomalies --output /tmp/anomalies.json            # Composite anomaly scoring
python tools/query_medicaid.py sql "SELECT billing_npi, sum(paid) FROM m GROUP BY 1 ORDER BY 2 DESC LIMIT 10"

# Medicaid Provider Trace Pipeline (NPI → NPPES → Registry → Officers)
python tools/trace_provider.py trace 1962650622 --output /tmp/trace.json         # Single NPI trace
python tools/trace_provider.py batch --top-anomalies 20 --output /tmp/batch.json # Top anomalous billers
python tools/trace_provider.py batch --file /tmp/npis.txt --output /tmp/batch.json
python tools/trace_provider.py excluded --output /tmp/excluded.json              # OIG exclusion cross-ref
python tools/trace_provider.py officer-network --min-entities 2 --output /tmp/officers.json
python tools/trace_provider.py agent-network --min-entities 3 --output /tmp/agents.json
python tools/trace_provider.py pipeline --top-anomalies 50 --output /tmp/pipeline.json

# New Mexico (REST API, 4s rate limit)
python tools/ingest_newmexico.py search "Zorro Ranch"
python tools/ingest_newmexico.py detail <internal_id>
python tools/ingest_newmexico.py ingest-batch "Zorro"

# California — bizfileonline web API (no auth, up to 500 results)
# Requires MCP Playwright Chrome running (trigger with any browser_navigate call)
python tools/query_california.py search "PARAFI CAPITAL"
python tools/query_california.py search "QUERY" --status active --type corp
python tools/query_california.py search "Apollo" --officer-last "BLACK"
python tools/query_california.py search "726332" --by-number
python tools/query_california.py entity 726332 --history --output /tmp/entity.json
python tools/query_california.py entity C0726332 --output /tmp/entity.json
python tools/query_california.py history 726332 --output /tmp/history.json
python tools/query_california.py ingest 726332
python tools/query_california.py ingest-search "QUERY" --limit 50
# Official API (needs CA_SOS_API_KEY — pending approval)
# python tools/ingest_california.py search "PARAFI CAPITAL"

# Texas Comptroller — franchise tax entity search (no auth)
python tools/query_texas.py search "QUERY" --output /tmp/tx-results.json
python tools/query_texas.py search "APOLLO" --limit 50 --output /tmp/tx-apollo.json
python tools/query_texas.py search --taxpayer-id 32044352170 --output /tmp/tx-tid.json
python tools/query_texas.py search --file-number 0801432227 --output /tmp/tx-fileno.json
python tools/query_texas.py entity 32044352170 --output /tmp/tx-entity.json
python tools/query_texas.py entity 32044352170 --json                     # Raw JSON to stdout
python tools/query_texas.py ingest 32044352170                            # Single entity → registry.db
python tools/query_texas.py ingest-search "QUERY" --limit 50              # Batch ingest

# Michigan LARA Business Registry (Cloudflare WAF — needs Playwright browser helper)
# First run may require manual Cloudflare challenge solve in browser window
python tools/query_michigan.py search "QUERY" --contains --output /tmp/mi-results.json
python tools/query_michigan.py search "APOLLO" --output /tmp/mi-apollo.json    # StartsWith by default
python tools/query_michigan.py entity 85956 802112570 --output /tmp/mi-entity.json  # internal_id filing_number
python tools/query_michigan.py ingest 85956 802112570                     # Single entity → registry.db
python tools/query_michigan.py ingest-search "QUERY" --limit 20           # Batch (slow — 1 browser session per entity)

# New Jersey Division of Revenue (HTML scraping — no detail pages)
python tools/query_newjersey.py search "QUERY" --output /tmp/nj-results.json
python tools/query_newjersey.py search "APOLLO" --limit 50 --output /tmp/nj-apollo.json
python tools/query_newjersey.py entity 0600092144 --output /tmp/nj-entity.json   # By 10-digit entity ID
python tools/query_newjersey.py keywords "HOME CARE" --output /tmp/nj-homecare.json  # Keyword search
python tools/query_newjersey.py ingest 0600092144                          # Single entity → registry.db
python tools/query_newjersey.py ingest-search "QUERY" --limit 20           # Batch ingest

# Massachusetts Corporations Division (Incapsula WAF — needs Playwright browser helper)
# First run may require manual Incapsula challenge solve in browser window
python tools/query_massachusetts.py search "QUERY" --output /tmp/ma-results.json
python tools/query_massachusetts.py search "APOLLO" --type F --output /tmp/ma-apollo.json  # Full text search
python tools/query_massachusetts.py entity 000487270 --output /tmp/ma-entity.json   # By MA ID number
python tools/query_massachusetts.py ingest 000487270                       # Single entity → registry.db
python tools/query_massachusetts.py ingest-search "QUERY" --limit 20       # Batch (slow — 1 browser session per entity)

# Colorado (SODA API — 1.3M+ entities, no auth)
python tools/ingest_colorado.py search "QUERY" --limit 100
python tools/ingest_colorado.py search "Zorro Ranch"
python tools/ingest_colorado.py search-agent "Corporation Service"
python tools/ingest_colorado.py search-address "Denver"
python tools/ingest_colorado.py ingest-entity 19871701849
python tools/ingest_colorado.py ingest-batch "QUERY"

# DC (ArcGIS FeatureServer — 492K entities, no auth + CorpOnline detail API)
python tools/ingest_dc.py search "Capital Athletic Foundation"
python tools/ingest_dc.py search "QUERY" --output /tmp/dc-results.json
python tools/ingest_dc.py search "Abramoff" --type nonprofit --status active
python tools/ingest_dc.py search-agent "Corporation Service Company" --limit 50
python tools/ingest_dc.py search-address "Dupont Circle"
python tools/ingest_dc.py detail <corponline-uuid>  # Enriched detail (principals, filings, NAICS)
python tools/ingest_dc.py ingest-entity L04091
python tools/ingest_dc.py ingest-batch "ENTITY_NAME_1" "ENTITY_NAME_2"
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
python tools/ingest_panama.py search "QUERY"
python tools/ingest_panama.py ingest-batch "QUERY" --expand

# UK Companies House (needs API key)
python tools/ingest_uk_companies_house.py search "QUERY"
python tools/ingest_uk_companies_house.py company 12345678
python tools/ingest_uk_companies_house.py officers 12345678
python tools/ingest_uk_companies_house.py psc 12345678
python tools/ingest_uk_companies_house.py officer-search "PERSON_NAME"
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
python tools/query_france.py search "QUERY" --naf 69.10Z    # Filter by activity code (69.10Z = legal)
python tools/query_france.py address "4 Rue Quentin-Bauchart" --postal 75008
python tools/query_france.py naf 64.20Z --postal 75008  # Activities of holding companies in 75008

# HUDOC — European Court of Human Rights (20K+ judgments, no auth)
python tools/query_hudoc.py search "Soffer, avocat" --output /tmp/hudoc-soffer.json
python tools/query_hudoc.py search "QUERY" --limit 20
python tools/query_hudoc.py case 001-99808  # Broadhurst Investments v Romania
python tools/query_hudoc.py appno "34868/03"  # By application number
python tools/query_hudoc.py text 001-99808  # Full text of judgment/decision
python tools/query_hudoc.py text 001-99808 --output /tmp/broadhurst-text.json  # Save full text
python tools/query_hudoc.py respondent ISR --limit 50  # All cases against Israel

# Delaware (via OpenCorporates API — requires OPENCORPORATES_API_KEY)
# Free research key: https://opencorporates.com/api_accounts/new
# Paid plans: £2,250/year minimum
python tools/query_delaware.py search "QUERY"
python tools/query_delaware.py search "APOLLO" --inactive
python tools/query_delaware.py search "QUERY" --per-page 100
python tools/query_delaware.py entity 1234567  # Company number
python tools/query_delaware.py filings 1234567
python tools/query_delaware.py batch-entities 1234567 2345678 3456789

# Hong Kong (via OpenCorporates API — requires OPENCORPORATES_API_KEY)
# Same API key as Delaware - free research key at link above
python tools/query_hongkong.py search "Mast Industries"
python tools/query_hongkong.py search "QUERY" --inactive
python tools/query_hongkong.py entity 1234567  # Company number
python tools/query_hongkong.py filings 1234567
python tools/query_hongkong.py batch-entities 1234567 2345678

# Cyprus (via OpenCorporates API — requires OPENCORPORATES_API_KEY)
# Same API key as Delaware/Hong Kong - major Russia-linked offshore hub
# Key targets: Xitrans Finance Ltd (Rybolovlev), Deripaska entities
python tools/query_cyprus.py search "Xitrans"
python tools/query_cyprus.py search "QUERY" --inactive
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
python tools/ingest_ucc_florida.py search "QUERY"

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
python tools/query_edgar.py search "TARGET" --size 20
python tools/query_edgar.py search "PERSON_NAME" "ENTITY_NAME" --forms "10-K,DEF 14A"
python tools/query_edgar.py search "QUERY" --forms "DEF 14A" --facets
python tools/query_edgar.py lookup "apollo global"     # Name → CIK
python tools/query_edgar.py company 0001411494         # Apollo by CIK
python tools/query_edgar.py filings 0001411494 --form "DEF 14A"
python tools/query_edgar.py insider CIK_NUMBER --limit 20  # By person CIK
python tools/query_edgar.py read "https://..." --lines 200
```
Look up relevant CIKs for current investigation targets via `query_edgar.py lookup "entity name"`

### USAspending (federal spending — contracts, grants, loans — no auth)
```bash
# Set OSINT_INSECURE_SSL=true if environment has SSL cert issues
uv run python tools/query_usaspending.py search "QUERY"                      # Recipient autocomplete
uv run python tools/query_usaspending.py awards "RECIPIENT" --limit 20       # Contract awards
uv run python tools/query_usaspending.py awards "RECIPIENT" --grants         # Grant awards
uv run python tools/query_usaspending.py award CONT_AWD_123_456             # Full award detail by ID
uv run python tools/query_usaspending.py recipient "QUERY"                   # Recipient profile + agency breakdown
uv run python tools/query_usaspending.py subawards "RECIPIENT"               # Subcontractor/subgrantee data
uv run python tools/query_usaspending.py transactions "RECIPIENT" --date-range 2020-01-01,2024-12-31
uv run python tools/query_usaspending.py timeline "RECIPIENT" --group fiscal_year  # Spending trend
uv run python tools/query_usaspending.py geography "RECIPIENT" --geo-layer state   # Geographic distribution
uv run python tools/query_usaspending.py top-recipients --agency "Department of Defense" --limit 10
uv run python tools/query_usaspending.py agencies --limit 10                 # List top-tier federal agencies
uv run python tools/query_usaspending.py covid "QUERY"                       # COVID-19 relief awards
uv run python tools/query_usaspending.py loans "QUERY"                       # Loan awards (PPP, EIDL, etc.)
```

### SAM.gov (entity registrations, exclusions, contracts, opportunities — requires SAM_API_KEY)
```bash
# Free API key: sam.gov → Account Details → API Key. Basic tier: 10 req/day.
uv run python tools/query_sam.py entity "QUERY"                              # Entity registration search
uv run python tools/query_sam.py entity "QUERY" --status A --sections all    # Active entities with full detail
uv run python tools/query_sam.py entity --uei RN99S3S7N977                   # Search by UEI
uv run python tools/query_sam.py entity --cage 1ABC2                         # Search by CAGE code
uv run python tools/query_sam.py exclusions "QUERY"                          # Debarments/suspensions search
uv run python tools/query_sam.py exclusions "QUERY" --classification Firm    # Firm exclusions only
uv run python tools/query_sam.py exclusions --npi 1234567890                 # Exclusions by NPI
uv run python tools/query_sam.py contracts "RECIPIENT"                       # Federal contract awards (replaces FPDS)
uv run python tools/query_sam.py contracts "RECIPIENT" --naics 541511 --min-amount 1000000
uv run python tools/query_sam.py contracts --piid GS-35F-0119T              # Search by procurement ID
uv run python tools/query_sam.py opportunities "surveillance" --posted-from 01/01/2025  # Solicitations
```

### Medicare (CMS spending, no auth)
```bash
uv run python tools/query_medicare.py search "Enkeshafi"
uv run python tools/query_medicare.py provider 1003000126
uv run python tools/query_medicare.py search "Health" --limit 20
```

### CourtListener (federal courts, token in .env)
```bash
python tools/query_courtlistener.py search "TARGET"
python tools/query_courtlistener.py cases "QUERY" --court nysd
python tools/query_courtlistener.py docket 16066603
python tools/query_courtlistener.py party "PERSON_NAME"
python tools/query_courtlistener.py opinions "QUERY" --court ca2
```

### ProPublica 990 (nonprofit filings)
```bash
python tools/query_990.py search "Gratitude America"
python tools/query_990.py ein 660789697
python tools/query_990.py filings 660789697
python tools/query_990.py batch "QUERY_1" "QUERY_2"
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
python tools/ingest_990_xml.py search "QUERY"              # keyword search grants+related
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

python tools/query_990_bulk.py search "QUERY"                # FTS5 search grants + related orgs
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
python tools/query_acris.py party "PERSON_NAME"
python tools/query_acris.py address --borough 1 --block 1386 --lot 10  # 9 E 71st
python tools/query_acris.py history --property-name "71st"
python tools/query_acris.py batch-entities
```

### FEC Campaign Finance (API key in .env)
```bash
python tools/query_fec.py donor "PERSON_NAME" --limit 20
python tools/query_fec.py employer "Gratitude America"
python tools/query_fec.py address "ZIP_CODE" --name "PERSON_NAME"
python tools/query_fec.py batch-persons
```
CRITICAL: Common names return multiple people — always check employer/address to disambiguate.

### FINRA BrokerCheck (broker registrations, no auth)
```bash
python tools/query_finra.py search "PERSON_NAME" --limit 10
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
python tools/query_fara.py search "QUERY"
python tools/query_fara.py country "Norway"
```

### LittleSis (power networks, no auth — look up entity IDs via search)
```bash
python tools/query_littlesis.py search "PERSON_NAME"
python tools/query_littlesis.py entity ENTITY_ID
python tools/query_littlesis.py relationships ENTITY_ID --category 5  # Donations
```

### OCCRP Aleph (registries, leaks, no auth for public)
```bash
python tools/query_aleph.py search "PERSON_NAME" --schema Person
python tools/query_aleph.py search "Financial Trust Company" --schema Company
python tools/query_aleph.py entity <id>
python tools/query_aleph.py expand <id>
```

### ICIJ Offshore Leaks (Neo4j, needs `./scripts/start_icij_db.sh`)
```bash
python tools/query_icij.py search "QUERY"
```

## External APIs

### GDELT (global news, 3mo window, no auth, 6s rate limit)
```bash
python tools/query_gdelt.py articles "TARGET" --limit 50 --timespan 3m
python tools/query_gdelt.py context "EVENT_NAME" --timespan 1w
python tools/query_gdelt.py timeline "TARGET" --mode volume
python tools/query_gdelt.py cooccurrence "TARGET" --targets "PERSON_A,PERSON_B,PERSON_C"
```

### OpenSanctions (sanctions + PEP, bulk download)
```bash
python tools/query_opensanctions.py download && python tools/query_opensanctions.py ingest
python tools/query_opensanctions.py search "Oleg Deripaska" --topic sanction
python tools/query_opensanctions.py pep-check "Ehud Barak"
python tools/query_opensanctions.py match-entities  # All investigation entities
```

### Investigation-Specific Corpus (1,271 persons, 1.5M docs, REST API)
```bash
python tools/ingest_epstein_exposed.py download
python tools/ingest_epstein_exposed.py search "QUERY"
python tools/ingest_epstein_exposed.py person "person-slug"
python tools/ingest_epstein_exposed.py flights --passenger "PERSON_NAME" --year 2002
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
python tools/query_documentcloud.py search "QUERY"
python tools/query_documentcloud.py document 24402693 --full
python tools/query_documentcloud.py text 24402693 --page 5
```

### Shodan (internet-connected devices, DNS, SSL certs — paid plan, SHODAN_API_KEY)
```bash
uv run python tools/query_shodan.py host 198.202.211.1
uv run python tools/query_shodan.py search "ssl:leadingthefuture.com"
uv run python tools/query_shodan.py search "org:\"Webflow\" port:443" --limit 50
uv run python tools/query_shodan.py domain leadingthefuture.com --history
uv run python tools/query_shodan.py dns-resolve google.com,example.com
uv run python tools/query_shodan.py reverse-dns 8.8.8.8,8.8.4.4
uv run python tools/query_shodan.py ssl-cert leadingthefuture.com
uv run python tools/query_shodan.py info  # check remaining credits
```

### crt.sh Certificate Transparency (CT log aggregator, no auth)
```bash
uv run python tools/query_crtsh.py search example.com
uv run python tools/query_crtsh.py search example.com --subdomains
uv run python tools/query_crtsh.py search "Goldman Sachs" --org
uv run python tools/query_crtsh.py search example.com --exclude-expired
uv run python tools/query_crtsh.py subdomains withpersona.com
uv run python tools/query_crtsh.py timeline leadingthefuture.com
uv run python tools/query_crtsh.py cert 12345678
```

### Wayback Machine CDX (historical web snapshots, no auth)
```bash
uv run python tools/query_wayback.py snapshots example.com
uv run python tools/query_wayback.py snapshots example.com --from 2019 --to 2020
uv run python tools/query_wayback.py snapshots "*.example.com" --subdomains
uv run python tools/query_wayback.py timeline example.com --monthly
uv run python tools/query_wayback.py first example.com
uv run python tools/query_wayback.py diff example.com --from 20190101 --to 20200101
uv run python tools/query_wayback.py fetch example.com --timestamp 20190715
```

### URLScan.io (passive web scan search, no auth for search)
```bash
uv run python tools/query_urlscan.py search "domain:example.com"
uv run python tools/query_urlscan.py search "ip:198.202.211.1"
uv run python tools/query_urlscan.py search "page.title:Leading The Future"
uv run python tools/query_urlscan.py search "server:cloudflare AND domain:example.com"
uv run python tools/query_urlscan.py result <scan-uuid>
uv run python tools/query_urlscan.py technologies <scan-uuid>
uv run python tools/query_urlscan.py links <scan-uuid>
```

### OffshoreAlert (29K+ offshore court cases, 4,500+ articles, MLATs, regulatory actions)
```bash
# Search (HTML scraping — rich results with scores, excerpts, tags)
uv run python tools/offshorealert_search.py search "ENTITY_NAME" -v
uv run python tools/offshorealert_search.py search "PERSON_NAME" --output /tmp/oa-results.json
uv run python tools/offshorealert_search.py search "liquid funding bermuda" -a  # all pages

# Extract tagged entities from search results (names, companies, jurisdictions)
uv run python tools/offshorealert_search.py entities "TARGET" -n 200
uv run python tools/offshorealert_search.py entities "apollo" --output /tmp/oa-entities.json

# API search (lightweight, no login needed, fewer results)
uv run python tools/offshorealert_search.py api-search "QUERY"

# NOTE: Individual article pages and PDF downloads are behind reCAPTCHA.
# Use Playwright browser session for full article content.
```

## Specialized

### DS10 Financial (579 tx, $304M)
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
python tools/query_fincen.py search-tx "ENTITY_NAME" --output /tmp/fincen-results.json
python tools/query_fincen.py search-connections "singapore" --output /tmp/fincen-sg.json
python tools/query_fincen.py filer "ENTITY_NAME" --output /tmp/fincen-filer.json
python tools/query_fincen.py country USA --output /tmp/fincen-usa.json
python tools/query_fincen.py sar 3297 --output /tmp/fincen-sar.json
```

### SWIFT BIC Directory (32K+ banks, BIC→LEI mappings)
```bash
python tools/ingest_bic.py download                     # Download datasets (OpenSanctions + GLEIF)
python tools/ingest_bic.py ingest                       # Download + ingest into bic.db
python tools/ingest_bic.py search "ENTITY_NAME" --output /tmp/bic-results.json
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
SELECT e.name FROM entities e JOIN entity_addresses a ON e.id = a.entity_id WHERE a.address LIKE '%ADDRESS%';
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
uv run python tools/entity_dedup.py list-aliases --canonical "PERSON_NAME"

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
    --person "PERSON_NAME" --pillar "Drexel Burnham Lambert" \
    --role "Managing Director" --seniority senior \
    --start 1977 --end 1990 --exit-type collapse \
    --source "Apollo prospectus"

# View career timeline
uv run python tools/pillar_tracker.py career "PERSON_NAME"

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
uv run python tools/pillar_tracker.py overlap --person-a "PERSON_A" --person-b "PERSON_B"

# Person timeline (career arcs + pillar events + external events interleaved)
uv run python tools/pillar_tracker.py timeline "PERSON_NAME"
```

### Orchestrator Identification

```bash
# Compute orchestrator scores
uv run python tools/pillar_tracker.py score --top 30
uv run python tools/pillar_tracker.py score --person "PERSON_NAME"
uv run python tools/pillar_tracker.py score --top 10 --cache  # saves to pillar_scores

# Find pillar type gaps in person's career
uv run python tools/pillar_tracker.py gaps --person "PERSON_NAME"

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

---

## Methodology Tracker

Tracks operational learnings from investigation agents. Part of investigation.db.

### methodology_tracker.py

```bash
# Record an observation
uv run python tools/methodology_tracker.py add --category friction --description "query_doj.py FTS5 times out for common words" --skill pursue-lead --lead-id 42

# List observations
uv run python tools/methodology_tracker.py list [--category friction] [--status open] [--limit 50]

# Show detail
uv run python tools/methodology_tracker.py show <ID>

# Update status
uv run python tools/methodology_tracker.py acknowledge <ID>
uv run python tools/methodology_tracker.py address <ID> --resolution "Added FTS5 phrase quoting"
uv run python tools/methodology_tracker.py dismiss <ID> --reason "Duplicate of #3"

# Detect recurring patterns across observations
uv run python tools/methodology_tracker.py patterns [--min-count 3]

# Bulk ingest learnings from a structured handoff report
uv run python tools/methodology_tracker.py ingest-report $WORKDIR/report-agent-a.md [--skill deep-investigate] [--lead-id N]

# Statistics
uv run python tools/methodology_tracker.py stats
```

### Observation Categories
`friction`, `surprise`, `methodology`, `process_gap`, `source_quality`

### Observation Statuses
`open`, `acknowledged`, `addressed`, `dismissed`, `duplicate`

### validate_report.py

Validates structured handoff reports (YAML frontmatter + required sections + categorized learnings).

```bash
uv run python tools/validate_report.py <file-or-dir>
uv run python tools/validate_report.py $WORKDIR/report-agent-a.md    # single file
uv run python tools/validate_report.py $WORKDIR/                     # all report-*.md in dir
```
