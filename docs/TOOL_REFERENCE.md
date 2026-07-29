# Tool Reference

Complete CLI examples for all investigation tools. Referenced from CLAUDE.md.

Run `python tools/source_report.py` for live data source status.

## Canonical Source Names

When using `--sources` on `findings_tracker.py add`, use these canonical names. Using consistent names enables provenance tracking and source coverage analysis.

| Source Name | Tool(s) | Description |
|-------------|---------|-------------|
| `web_search` | WebSearch, WebFetch | Open web research |
| `kabass` | ingest_kabasshouse.py | **PRIMARY Epstein corpus** — 1,424,673 OCR document/page records (one distinct file_key per row in the current snapshot) + structured layers. Same EFTA page in kabass + doj_vol11/lmsband = one source, not corroboration |
| `fbi` | ingest_fbi_files.py | FBI release (8,150 docs) + named exhibits (Flight Log, Contact Book) |
| `efta` | EFTA evidence references | Underlying DOJ-released EFTA document; copies or re-OCRs in kabass/LMSBAND/DOJ corpora remain one source, not corroboration |
| `doj_vol11` | query_doj.py | DOJ Vol 11 document corpus (fallback — subset of kabass) |
| `justice_gov` | justice.gov | Official Department of Justice pages and documents |
| `duggan` | _(retired — tool removed 2026-06-29)_ | Duggan USA corpus — historical source name only; 42 findings cite it |
| `lmsband` | query_lmsband.py | LMSBAND document corpus |
| `unified_db` | query_unified.py | Unified document database |
| `fec` | query_fec.py | FEC campaign finance |
| `edgar` | query_edgar.py | SEC EDGAR filings |
| `courtlistener` | query_courtlistener.py | CourtListener court records |
| `supreme_court` | supremecourt.gov | Official U.S. Supreme Court dockets, filings, and opinions |
| `mn_court_appeals` | mncourts.gov | Official Minnesota Court of Appeals opinions |
| `fjc` | query_courtlistener.py fjc | Federal Judicial Center Integrated Database |
| `finra` | query_finra.py | FINRA BrokerCheck records |
| `openpayments` | query_openpayments.py | CMS Open Payments covered-recipient profiles and company-reported payment summaries |
| `senate_finance` | query_senate_finance.py | Official Senate Finance Committee releases, investigations, and attachments |
| `nyscef` | query_nyscef.py | NYSCEF New York state court records |
| `military_justice` | query_military_justice.py | CAAF + ACCA + NMCCA + AFCCA + CGCCA appellate dockets/opinions |
| `990` | query_990.py | IRS 990 nonprofit database (grants, officers, financials) |
| `registry` | query_registry.py | Unified corporate registry |
| `fdacs` | FDACS Check-A-Charity | Florida charity registrations and official attachments |
| `usaspending` | query_usaspending.py | USASpending federal contracts/grants |
| `fpds` | query_fpds.py | FPDS-NG contract actions incl. createdBy/approvedBy workflow fields |
| `federal_register` | query_federal_register.py | Federal Register documents (rules, notices, presidential docs) |
| `sam_gov` | query_sam.py | SAM.gov API |
| `sam_bulk` | ingest_sam.py | SAM.gov bulk data (local SQLite) |
| `lobbying` | query_lobbying.py | LDA lobbying disclosures |
| `fara` | query_fara.py | FARA foreign agent registrations |
| `littlesis` | query_littlesis.py | LittleSis relationship maps |
| `gdelt` | query_gdelt.py | GDELT global news |
| `reporting` | reporting_corpus.py | Reviewed reporting claims promoted only with quoted primary evidence |
| `government_releases` | government_release_corpus.py | Primary DOJ and SEC press releases, versioned and full-text searchable |
| `aleph` | query_aleph.py | OCCRP Aleph |
| `icij` | query_icij.py | ICIJ offshore leaks |
| `acris` | query_acris.py | NYC ACRIS property records |
| `la_property` | query_la_property.py | Louisiana property records (EBR via SODA) |
| `gleif` | query_gleif.py | GLEIF LEI corporate hierarchy |
| `opensanctions` | query_opensanctions.py | OpenSanctions PEP/sanctions |
| `shodan` | query_shodan.py | Shodan internet devices |
| `crtsh` | query_crtsh.py | crt.sh certificate transparency |
| `wayback` | query_wayback.py | Wayback Machine |
| `urlscan` | query_urlscan.py | URLScan.io |
| `dehashed` | query_dehashed.py | DeHashed breach/credential aggregator (v2; needs active subscription) |
| `intelx` | query_intelx.py | Intelligence X leak/paste/darkweb index (planned; gated) |
| `leak_aggregator` | selector_pivot.py | Leak/breach aggregator provenance class — caps derived findings at `medium` |
| `medicaid` | query_medicaid.py | Medicare/Medicaid spending |
| `highergov` | query_highergov.py | HigherGov contracts/grants |
| `documentcloud` | query_documentcloud.py | DocumentCloud |
| `muckrock` | query_muckrock.py | MuckRock FOIA |
| `fincen` | query_fincen.py | FinCEN filings |
| `sec_enforcement` | query_sec_enforcement.py | SEC enforcement actions (litigation, admin, AAER) |
| `opencorporates` | query_delaware/hongkong/cyprus.py | OpenCorporates API |
| `hudoc` | query_hudoc.py | ECHR case database |
| `france_sirene` | query_france.py | French SIRENE registry |
| `fl_sunbiz` | query_florida.py, ingest_florida.py | Florida SunBiz |
| `ny_dos` | query_nydos.py | New York DOS |
| `ca_sos` | query_california.py | California SOS |
| `co_sos` | Colorado Secretary of State | Colorado business registry |
| `tx_comptroller` | query_texas.py | Texas Comptroller |
| `mi_lara` | query_michigan.py | Michigan LARA |
| `nj_rev` | query_newjersey.py | New Jersey Revenue |
| `ma_corps` | query_massachusetts.py | Massachusetts Corporations |
| `wy_sos` | query_wyoming.py | Wyoming Secretary of State (WyoBiz) |
| `nv_sos` | query_nevada.py | Nevada SOS |
| `nm_sos` | ingest_newmexico.py | New Mexico SOS |
| `dc_dlcp` | ingest_dc.py | DC DLCP |
| `usvi` | ingest_usvi.py | US Virgin Islands |
| `ds10_financial` | parse_ds10_financials.py | DS10 financial records |
| `ucc` | query_registry.py ucc-search | UCC filings |
| `florida_ucc` | query_florida_ucc.py | Florida Secured Transaction Registry (commercial UCC) |
| `faa` | ingest_faa.py | FAA aircraft registry |
| `uk_companies_house` | ingest_uk_companies_house.py | UK Companies House |
| `investigations_db` | query_investigations.py | Ingested investigation reports |
| `analysis_run` | (synthesis findings) | Agent analysis/synthesis |
| `panama_rp` | query_panama.py | Panama public registry |
| `zefix` | query_zefix.py | Swiss commercial registry |
| `patents` | query_patents.py | USPTO patent search & ownership tracing |
| `trademarks` | query_trademarks.py | USPTO trademark search, ownership blocks, and goods/services |
| `military_corrections` | query_military_corrections.py | DoD BCMR/BCNR Reading Room (boards.law.af.mil) — redacted decisions of all four service correction boards |
| `ecfr` | ecfr.gov | Electronic Code of Federal Regulations |
| `nlrb` | nlrb.gov | National Labor Relations Board records |
| `usms` | usmarshals.gov | U.S. Marshals Service records |
| `massachusetts_governor` | mass.gov/governor | Massachusetts governor official releases and records |
| `val_verde_county` | valverdecounty.texas.gov | Val Verde County official records |
| `internet_archive` | archive.org | Preserved public web pages and documents |
| `elperuano` | query_elperuano.py, ingest_elperuano.py | Diario Oficial El Peruano (Peru) — gazette search, document fetch, daily bulletin |

**Important**: Use these exact names. `findings_tracker.py` requires at least one
supported source and rejects unknown names. If you need a new source name, add it
to `VALID_SOURCES` in `tools/findings_tracker.py`.

Configured corpus tools and legacy findings may expose the following explicit
aliases. `findings_tracker.py` stores their canonical value; all other unknown
tokens still fail validation.

| Alias(es) | Canonical source |
|------------|------------------|
| `kabasshouse`, `Kabasshouse Epstein Corpus` | `kabass` |
| `unified`, `unified_epstein` | `unified_db` |
| `SEC EDGAR` | `edgar` |
| `ds10` | `ds10_financial` |
| `doj_epstein_files` | `doj` |
| `house_20k`, `epstein_20k` | `house_oversight` |
| `fbi-files`, `fbi_files`, `fbi_epstein`, `fbi_epstein_files` | `fbi` |
| `epstein_reporting` | `reporting` |
| `query_investigations` | `investigations_db` |
| `scotus` | `supreme_court` |
| `scotus_filing` | `supreme_court` |
| `courtlistener_recap` | `courtlistener` |
| `sam` | `sam_gov` |
| `sam_local`, `sam_public_extract` | `sam_bulk` |
| `florida_sunbiz` | `fl_sunbiz` |
| `colorado_sos` | `co_sos` |
| `justice.gov` | `justice_gov` |
| `ecfr.gov` | `ecfr` |

## Core Investigation Tools

### Epstein Reporting Knowledge Layer

```bash
uv run python tools/reporting_corpus.py init
uv run python tools/reporting_corpus.py discover-repository
uv run python tools/reporting_corpus.py discover-gdelt '"Jeffrey Epstein"' --timespan 3m
uv run python tools/reporting_corpus.py discover-feed URL --query Epstein
uv run python tools/reporting_corpus.py ingest-candidates --limit 50
uv run python tools/reporting_corpus.py import-file export.ris --source proquest
uv run python tools/reporting_corpus.py search 'Southern Trust' --output "$WORKDIR/reporting.json"
uv run python tools/reporting_corpus.py claims 'JPMorgan' --output "$WORKDIR/reporting-claims.json"
uv run python tools/reporting_corpus.py primary-gaps --output "$WORKDIR/reporting-gaps.json"
uv run python tools/reporting_corpus.py recover-archives --failed-candidates --limit 50 --store-text
uv run python tools/reporting_corpus.py ingest-archive-url ORIGINAL_URL ARCHIVE_URL --store-text
```

Reporting claims remain attributed secondary-source assertions. `promote` refuses
claims that have not been reviewed and linked to quoted primary evidence. Full
workflow and licensed-database export guidance: `docs/modules/reporting.md`.
Public archive recovery uses Wayback CDX first and Common Crawl WARC ranges as a
fallback; archive.is snapshots can be supplied manually.

### DOJ/SEC Primary Press Releases

```bash
uv run python tools/government_release_corpus.py init
uv run python tools/government_release_corpus.py ingest-doj --max-pages 100
uv run python tools/government_release_corpus.py discover-sec --start-year 1997
uv run python tools/government_release_corpus.py fetch-sec --limit 500
uv run python tools/government_release_corpus.py search 'money laundering' --agency DOJ --output "$WORKDIR/doj-releases.json"
uv run python tools/government_release_corpus.py search 'JPMorgan' --agency SEC --output "$WORKDIR/sec-releases.json"
```

DOJ ingestion is resumable through `ingest_state`; a zero `--max-pages` completes
all remaining API pages. SEC coverage is the complete official online archive:
static yearly indexes for 1997–2011 and the newsroom index for 2012–present.
See `docs/modules/government-releases.md`.

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
python tools/findings_tracker.py search "gates foundation" --limit 20 --output /tmp/findings.json
python tools/findings_tracker.py timeline --target "Rod-Larsen"
```

New finding writes require `--sources` to contain supported source tokens. A
`direct_quote` also requires at least one `--evidence` reference and a non-empty
`--source-quote` for every reference. HTTP(S) references are stored as `url`;
canonical references such as `CourtListener:docket/69737684` remain `ref` even
when their source-specific key contains `/`. Explicit/path-like local file
references must exist. Relative file references resolve from the repository
root so their meaning does not depend on the caller's working directory.

### Audited Finding Evidence CRUD
```bash
# Add evidence (direct_quote findings require --source-quote)
uv run python tools/findings_tracker.py evidence-add 42 \
  --ref CourtListener:docket/69737684 \
  --source-quote "Exact language from the filing" \
  --source-page "p. 12" --reason "Attach primary filing" --by analyst

# Correct one evidence field; evidence_ref changes automatically reclassify its type
uv run python tools/findings_tracker.py evidence-correct 42 \
  --ref CourtListener:docket/69737684 --field source_quote \
  --value "Corrected exact language" --reason "Fix transcription" --by analyst

# Delete evidence while retaining its full pre-delete audit snapshot
uv run python tools/findings_tracker.py evidence-delete 42 \
  --ref CourtListener:docket/69737684 --reason "Superseded by certified filing" --by analyst

# Report legacy violations before correction; this never modifies finding/evidence rows
uv run python tools/findings_tracker.py evidence-audit --profile epstein --output /tmp/evidence-audit.json
uv run python tools/findings_tracker.py evidence-audit --finding-id 42

# Inspect the immutable correction trail for one composite-key evidence row
uv run python tools/findings_tracker.py audit 42 --table finding_evidence \
  --record-key CourtListener:docket/69737684
```

Evidence mutations are atomic and invalidate an already verified finding back
to `unverified`, requiring fresh review. Quote spans are checked against locally
resolvable EFTA OCR and text files. Remote URLs, binary files, and canonical
references without a local resolver remain usable; `evidence-audit` counts
those spans as `unchecked` rather than treating them as mismatches.

### Audited Connection Evidence & Verification
```bash
# Create or idempotently enrich a canonical edge with quote/page/assessment provenance
uv run python tools/findings_tracker.py connect \
  --person-a "PERSON_A" --person-b "ORGANIZATION_B" --type legal \
  --evidence CourtListener:docket/69737684 \
  --source-quote "CourtListener:docket/69737684:Exact language from the filing" \
  --source-page "CourtListener:docket/69737684:p. 12" \
  --assessment "CourtListener:docket/69737684:Names both endpoints"

# Add, correct, or delete evidence with immutable correction rows
uv run python tools/findings_tracker.py connection-evidence-add 7 \
  --ref CourtListener:docket/69737684 \
  --source-quote "Exact language from the filing" --source-page "p. 12" \
  --assessment "Names both endpoints" --reason "Attach primary filing" --by analyst
uv run python tools/findings_tracker.py connection-evidence-correct 7 \
  --ref CourtListener:docket/69737684 --field source_quote \
  --value "Corrected exact language" --reason "Fix transcription" --by analyst
uv run python tools/findings_tracker.py connection-evidence-delete 7 \
  --ref CourtListener:docket/69737684 --reason "Superseded evidence" --by analyst

# Verification is the publication gate: every evidence row needs a quote and valid ref
uv run python tools/findings_tracker.py connection-unverified --profile epstein
uv run python tools/findings_tracker.py connection-verify 7 --by analyst
uv run python tools/findings_tracker.py connections "PERSON_A" --verified-only

# Audited edge lifecycle and provenance
uv run python tools/findings_tracker.py connection-correct 7 \
  --field description --value "Corrected relationship description" \
  --reason "Clarify edge" --by analyst
uv run python tools/findings_tracker.py connection-dispute 7 \
  --reason "Relationship is contested" --by analyst
uv run python tools/findings_tracker.py connection-retract 7 \
  --reason "Edge was unsupported" --by analyst
uv run python tools/findings_tracker.py connection-audit 7
uv run python tools/findings_tracker.py connection-provenance 7 \
  --output /tmp/connection-7-provenance.json
```

Initial connection creation remains draft-friendly. Enriching an existing
canonical edge is atomic and audited; identical repeats are no-ops, while a
conflicting non-empty quote/page/assessment must use
`connection-evidence-correct` with a reason. Any substantive edge or evidence
change resets a verified connection to `unverified`; correcting a field to its
current normalized value is an explicit no-op and creates no audit row. Initial
verification appends immutable status history, while repeating verification on
an already verified, still-publishable edge preserves its reviewer, timestamp,
and audit history. Retraction is final for this workflow: a retracted edge cannot
be disputed or verified without a future explicit restoration workflow. If an edge cites
`finding_id`, that finding must also be verified before the edge can be
verified. The `--verified-only` publication view revalidates current evidence,
so legacy rows carrying a stale `verified` status are excluded without silently
rewriting their lifecycle state. Public dossier export uses that same current
evidence and upstream-finding validator; research export with
`--include-unverified` remains non-retracted rather than publication-gated.
Endpoint names are not directly correctable
because they define the canonical edge key; retract the old edge and create a
new canonical edge.

### Audit & Verification
```bash
uv run python tools/findings_tracker.py add --target "TARGET" \
  --summary "Evidence-backed claim" --sources courtlistener \
  --output "$WORKDIR/created-finding.json"  # JSON includes the committed finding ID
uv run python tools/findings_tracker.py unverified --profile epstein --output "$WORKDIR/unverified.json"
uv run python tools/findings_tracker.py unverified --all-profiles --json
uv run python tools/findings_tracker.py provenance 42    # Full provenance chain
# `verify ID [--by REVIEWER]` is the complete verification interface; it does
# not take generic `--status` or `--notes` options.
uv run python tools/findings_tracker.py verify 42 --by analyst
uv run python tools/findings_tracker.py dispute 42 --reason "Quote doesn't match source"
uv run python tools/findings_tracker.py retract 42 --reason "Hallucinated by agent"  # Cascades
uv run python tools/findings_tracker.py correct 42 --field summary \
  --value "New text" --reason "Amount was 15M not 18M"
# source_datasets corrections must be a JSON array of supported tokens
uv run python tools/findings_tracker.py correct 42 --field source_datasets \
  --value '["courtlistener","registry"]' --reason "Normalize provenance tokens"
uv run python tools/findings_tracker.py relate 42 43 --type refines \
  --assessment "Finding 42 narrows the earlier claim"
uv run python tools/findings_tracker.py relation-delete 42 43 --type refines \
  --reason "Accidental relation to the wrong concurrently created finding" --by analyst
uv run python tools/findings_tracker.py audit 42 --table findings --json  # Show correction history
```

## Analysis Tools

### Hypothesis Tracker
```bash
python tools/hypothesis_tracker.py add --title "USVI cluster suggests structural role" \
  --pattern-type structural --description "4 unrelated targets all have USVI entities 2012-2015" \
  --competition-group "usvi-formation-cluster" \
  --predicted-evidence "Shared registered agent or formation attorney" \
  --search-plan "1. query_registry.py search USVI agent  2. ingest_usvi.py agent overlap"
python tools/hypothesis_tracker.py add --title "Routine industry clustering" --as-null \
  --competition-group "usvi-formation-cluster" --description "H0 with its own falsification criterion"
python tools/hypothesis_tracker.py list [--status proposed] [--pattern-type structural] \
  [--competition-group usvi-formation-cluster]
python tools/hypothesis_tracker.py show 5
python tools/hypothesis_tracker.py evaluate --hypothesis-id 5 --finding-id 412 --assessment inconsistent
python tools/hypothesis_tracker.py matrix [--competition-group usvi-formation-cluster]
python tools/hypothesis_tracker.py compete [--competition-group usvi-formation-cluster]
python tools/hypothesis_tracker.py diagnose
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

### DOJ Vol 11 (331K pages, FTS5, EFTA IDs)
```bash
python tools/query_doj.py search "query" -n 50 --output /tmp/results.json
python tools/query_doj.py download "https://www.justice.gov/epstein/files/DataSet%209/EFTA00634292.pdf" --output /tmp/EFTA00634292.pdf
```

### LMSBAND (591,286 files, 1,693,889 entity mentions)
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

# California — BizFile browser search (no auth, bounded to 1-500 results)
# Requires Node.js + playwright/playwright-core + installed Google Chrome.
# Uses one short-lived headed process and a dedicated local Imperva cache.
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_california.py runtime-check --output "$WORKDIR/ca-runtime.json"
uv run python tools/query_california.py probe --output "$WORKDIR/ca-probe.json"
uv run python tools/query_california.py search "PARAFI CAPITAL" --limit 25 --output "$WORKDIR/ca-search.json"
uv run python tools/query_california.py search C0726332 --by-number --limit 5 --output "$WORKDIR/ca-number.json"
# Advanced filters, entity/history, and ingest commands are explicitly unavailable
# until their self-contained browser flows are live-verified. This interactive tool
# does not replace the weekly statewide bulk importer tracked by infra request #130.
# Official API (needs CA_SOS_API_KEY — pending approval)
# uv run python tools/ingest_california.py search "PARAFI CAPITAL"
# Do not wait on a pending key: use query_california.py for bounded public
# searches. Logged-in BizFile offers free weekly BE deltas; the complete master
# unload is $100 and should precede weekly updates for statewide coverage.

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

# Wyoming Secretary of State / WyoBiz (F5 WAF — needs Playwright browser helper)
# First run may require manual F5 CAPTCHA solve: `warmup` command opens browser window
python tools/query_wyoming.py warmup                                       # Solve F5 CAPTCHA, cache cookies
python tools/query_wyoming.py search "TRUMP" --output /tmp/wy-trump.json   # Starts-with search (default)
python tools/query_wyoming.py search "WORLD LIBERTY" --mode contains --output /tmp/wy-wlfi.json  # Contains search
python tools/query_wyoming.py entity 2021-001032098 --output /tmp/wy-entity.json  # By WY filing ID
python tools/query_wyoming.py detail <eFNum> --output /tmp/wy-detail.json  # By encrypted eFNum from search
python tools/query_wyoming.py ingest 2021-001032098                        # Single entity → registry.db
python tools/query_wyoming.py ingest-search "TRUMP" --limit 20            # Batch (slow — 1 browser session per entity)

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
# Read-only commands accept --output FILE for isolated JSON results.
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/ingest_uk_companies_house.py search "QUERY" --output "$WORKDIR/uk-search.json"
# Use --broad only for legacy token-based discovery; default search is phrase-sensitive.
uv run python tools/ingest_uk_companies_house.py company 12345678 --output "$WORKDIR/uk-company.json"
uv run python tools/ingest_uk_companies_house.py officers 12345678 --output "$WORKDIR/uk-officers.json"
uv run python tools/ingest_uk_companies_house.py psc 12345678 --output "$WORKDIR/uk-psc.json"
uv run python tools/ingest_uk_companies_house.py officer-search "PERSON_NAME" --output "$WORKDIR/uk-officer-search.json"
uv run python tools/ingest_uk_companies_house.py ingest-batch "Apollo"

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

# Florida UCC (commercial — floridaucc.com REST API, no auth)
uv run python tools/query_florida_ucc.py search-org "COMPANY NAME"           # Standard search logic (exact compact name)
uv run python tools/query_florida_ucc.py search-org "COMPANY NAME" --proximity --paginate  # Proximity search, all pages
uv run python tools/query_florida_ucc.py search-org "COMPANY NAME" --lapsed  # Lapsed filings only
uv run python tools/query_florida_ucc.py search-org "COMPANY NAME" --all     # Filed + lapsed
uv run python tools/query_florida_ucc.py search-individual "LAST FIRST"      # Individual debtor
uv run python tools/query_florida_ucc.py filing 202501545298                 # Full filing detail by UCC number

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

### USPTO Patents (patent search & ownership tracing, API key required)
```bash
uv run python tools/query_patents.py search "machine learning fraud" --limit 10
uv run python tools/query_patents.py inventor "Tim Draper" --limit 50
uv run python tools/query_patents.py assignee "Apollo Global" --limit 50
uv run python tools/query_patents.py patent 11234567
uv run python tools/query_patents.py assignments 11234567        # Ownership chain
uv run python tools/query_patents.py assignments 11234567 --since 2020-01-01
uv run python tools/query_patents.py portfolio "L Brands" --limit 200
uv run python tools/query_patents.py portfolio "L Brands" --skip-assignments  # Faster
uv run python tools/query_patents.py citations 11234567           # Parent/child continuity
uv run python tools/query_patents.py enrich --dry-run            # Match entities against patents
uv run python tools/query_patents.py enrich --threshold 85       # Auto-enrich
```
Requires `USPTO_API_KEY` in `.env` (register at https://data.uspto.gov/myodp, requires ID.me).
Uses the USPTO Open Data Portal API (60 req/min). Results cached in `datasets/patents.db`.

### USPTO Trademarks (mark ownership + goods/services — no auth)
```bash
# Cite trademark findings with source token `trademarks` (not `patents`).
uv run python tools/query_trademarks.py mark "HC STANDARD"                  # Exact phrase by default
uv run python tools/query_trademarks.py mark "HC STANDARD" --loose          # Broad OR-style site search
uv run python tools/query_trademarks.py mark "HC STANDARD" --include-pseudo # Also phrase-match pseudo-marks
uv run python tools/query_trademarks.py owner "Global Emergency Resources"  # Registrant and later-owner blocks
uv run python tools/query_trademarks.py serial 85877492
uv run python tools/query_trademarks.py goods "asset tracking" --live-only --class 042
uv run python tools/query_trademarks.py mark "HC STANDARD" --from-file saved-response.json
```
The default mark query uses `match_phrase` on the wordmark. The USPTO site's loose query OR-matches
terms and can return tens of thousands of irrelevant hits for a multi-word search, so use `--loose`
only when broader recall is intentional. Console and JSON results preserve every `ownerFullText`
entry, including both `(REGISTRANT)` and `(LAST LISTED OWNER)` lines that expose ownership transfers.
USPTO patents and trademarks are different registers; use `query_patents.py` and source token
`patents` for patents, and `query_trademarks.py` and source token `trademarks` for trademarks.

## Public Records

### Property and state/local-court control plane

Source facts, capabilities, routes, reviewed access decisions, terms snapshots,
and probe history live in `datasets/public_records_catalog.db`. Adapters and
planners read that shared state rather than maintaining separate source
switches.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/seed_public_records_catalog.py --json
uv run python tools/public_records_catalog.py list --domain property --json
uv run python tools/public_records_catalog.py list --domain court --json
uv run python tools/public_records_catalog.py show us-nc-onemap-parcels --json
uv run python tools/public_records_catalog.py health --json
uv run python tools/public_records_monitor.py plan us-nc-onemap-parcels \
    --output "$WORKDIR/public-record-monitor-plan.json"
uv run python tools/public_records_monitor.py history us-nc-onemap-parcels \
    --output "$WORKDIR/nc-probe-history.json"
uv run python tools/public_records_store.py init
uv run python tools/public_records_store.py stats
```

`ok`, true `no_results`, `partial`, `rate_limited`, `human_required`,
`terms_blocked`, `restricted`, `unavailable`, and `source_changed` remain
separate result states. Shared HTTP families provide Socrata and ArcGIS
pagination/cursors; the bulk family provides release manifests, resumable
transfer, hashes, and ZIP inspection/extraction. There is no platform-wide
`maximum_records_per_run` compatibility setting; caller limits and endpoint
page-size mechanics remain explicit.

### Nationwide source census and priority

```bash
uv run python tools/public_records_census.py seed
uv run python tools/public_records_census.py stats --json
uv run python tools/public_records_census.py claim --domain property --state FL \
    --by source-researcher --output "$WORKDIR/claimed-source.json"
uv run python tools/public_records_census.py associate 17 \
    --source-id us-example-source --coverage '{"counties":["001"]}' \
    --coverage-gaps '["other county systems unassessed"]' --by source-researcher
uv run python tools/public_records_census.py assess-coverage 17 \
    --status partial --gaps '["local systems still unassessed"]' \
    --by source-researcher
uv run python tools/public_records_priority.py recompute --by methodology-review
uv run python tools/public_records_priority.py metrics \
    --output "$WORKDIR/public-record-priority.json"
uv run python tools/public_records_priority.py explain 17 \
    --output "$WORKDIR/public-record-target-17.json"
```

The census tracks jurisdiction/record-role discovery, multiple source
associations, service-area evidence, and explicit coverage gaps. Source
discovery and coverage assessment are separate states. Priority stores
benefit, feasibility, and risk independently, with an auditable basis for every
recomputation.

### Unified query routers and search planning

The routers search normalized sidecars by default. A named source dispatches
through its registered adapter when available and otherwise returns the
cataloged route state.

```bash
uv run python tools/query_property.py sources --jurisdiction 37 \
    --output "$WORKDIR/property-sources.json"
uv run python tools/query_property.py owner "SMITH" --output "$WORKDIR/property-local.json"
uv run python tools/query_property.py owner "SMITH" --source us-nc-onemap-parcels \
    --county-fips 005 --limit 25 --output "$WORKDIR/property-nc.json"
uv run python tools/query_property.py parcel 3013467134 --source us-nc-onemap-parcels \
    --county-fips 005 --geometry --ingest --output "$WORKDIR/property-nc-parcel.json"

uv run python tools/query_state_courts.py sources --jurisdiction 36 \
    --output "$WORKDIR/court-sources.json"
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
    --output "$WORKDIR/court-local.json"
uv run python tools/query_state_courts.py search "EXAMPLE LLC" --source us-ny-nyscef \
    --jurisdiction 36 --output "$WORKDIR/nyscef-human-action.json"

uv run python tools/public_records_search_plan.py "Example Holdings LLC" \
    --alias "Example Holdings" --address "100 Main St, Albany, NY" \
    --jurisdiction 36 --output "$WORKDIR/public-record-search-plan.json"
```

Normalized data live in `datasets/property_records.db` and
`datasets/state_court_records.db`. Cite retained records with
`PROPERTY:<source>/<jurisdiction>/<kind>/<native-id>` or
`STATECOURT:<source>/<court>/<case>/<kind>[/<native-id>]`. See
`docs/modules/property.md` and `docs/modules/legal.md`.

### Property adapter pilots

```bash
# North Carolina OneMap: owner/address/parcel/geometry
uv run python tools/query_nc_property.py owner "SMITH" --county-fips 005 \
    --limit 25 --output "$WORKDIR/nc-owner.json"
uv run python tools/query_nc_property.py parcel 3013467134 --county-fips 005 \
    --geometry --output "$WORKDIR/nc-parcel.json"

# Cook County Parcel Universe: PIN history/geography/tax districts
uv run python tools/query_cook_property.py parcel 01-01-106-009-1001 \
    --output "$WORKDIR/cook-parcel.json"

# Maryland statewide assessments: address/parcel; current owner names are
# source-withheld and represented as such
uv run python tools/query_md_property.py address "7 TRAYMORE RD" \
    --output "$WORKDIR/md-address.json"
uv run python tools/query_md_property.py parcel 04030311078580 \
    --output "$WORKDIR/md-parcel.json"

# Florida DOR official assessment-roll and GIS releases
uv run python tools/query_fl_dor_property.py manifest --type sdf \
    --county Baker --year 2026 --output "$WORKDIR/fl-baker-manifest.json"
uv run python tools/query_fl_dor_property.py probe --type gis-pin \
    --county 12 --year 2026 --output "$WORKDIR/fl-gis-probe.json"
uv run python tools/query_fl_dor_property.py dry-run --type nal \
    --county Baker --destination "$WORKDIR/fl-dor" \
    --output "$WORKDIR/fl-transfer-plan.json"

# MassGIS official municipal snapshots
uv run python tools/query_massgis_property.py manifest --town GOSNOLD \
    --output "$WORKDIR/massgis-manifest.json"
uv run python tools/query_massgis_property.py probe --town GOSNOLD \
    --output "$WORKDIR/massgis-probe.json"
uv run python tools/query_massgis_property.py download --town GOSNOLD \
    --destination "$WORKDIR/massgis-gosnold.zip" --dry-run \
    --output "$WORKDIR/massgis-transfer-plan.json"

# Harris Central Appraisal District official manifests and bulk archives
uv run python tools/query_harris_property.py manifest --year 2026 \
    --output "$WORKDIR/hcad-2026-manifest.json"
uv run python tools/query_harris_property.py probe --year 2026 \
    --artifact Real_acct_owner.zip \
    --output "$WORKDIR/hcad-owner-probe.json"
uv run python tools/query_harris_property.py dry-run --year 2026 \
    --artifact Real_acct_owner.zip --destination "$WORKDIR/hcad" \
    --output "$WORKDIR/hcad-owner-transfer-plan.json"
```

NYC ACRIS and East Baton Rouge commands are listed later in this reference.
See `docs/modules/property.md` for each pilot's source coverage and canonical
record semantics.

### Retention, artifacts, extraction, and entity candidates

```bash
# Retain any canonical property result envelope; mapped sources also receive
# structured parcel/instrument projections
uv run python tools/ingest_property_records.py ingest \
    --input "$WORKDIR/property-result.json" \
    --output "$WORKDIR/property-ingest.json"

# Source-specific NC compatibility command
uv run python tools/ingest_property_records.py nc-onemap \
    --input "$WORKDIR/nc-parcel.json" --output "$WORKDIR/nc-ingest.json"

# Retain any canonical state/local-court result envelope
uv run python tools/ingest_state_court_records.py ingest \
    "$WORKDIR/court-result.json" --output "$WORKDIR/court-ingest.json"

# Store and verify source bytes
uv run python tools/public_records_artifacts.py put "$WORKDIR/filing.pdf" \
    --source-id us-example-court \
    --canonical-ref "STATECOURT:us-example-court/circuit/CV-42/document/7" \
    --output "$WORKDIR/filing-artifact.json"
uv run python tools/public_records_artifacts.py verify \
    --output "$WORKDIR/public-record-artifact-check.json"

# Validate/import extracted fields and manage the append-only review queue
uv run python tools/public_records_extract.py validate \
    "$WORKDIR/filing-extraction.json" \
    --output "$WORKDIR/filing-validation.json"
uv run python tools/public_records_extract.py ingest \
    "$WORKDIR/filing-extraction.json" \
    --output "$WORKDIR/filing-extraction-ingest.json"
uv run python tools/public_records_extract.py queue \
    --output "$WORKDIR/public-record-review.json"

# Generate explainable property/instrument/court-party entity candidates
uv run python tools/public_records_entity_candidates.py generate \
    --output "$WORKDIR/public-record-entity-candidates.json"
uv run python tools/public_records_entity_candidates.py list --status open \
    --output "$WORKDIR/open-public-record-candidates.json"
```

### Catalog-backed source actions and evaluation

```bash
# Render a formal-feed/account/request/paid/physical-access action
uv run python tools/public_records_actions.py plan us-in-iocs-bulk \
    --operation obtain_feed --selector "civil case metadata" \
    --output "$WORKDIR/indiana-feed-plan.json"

# Add the structured action to investigation.db when it should be tracked
uv run python tools/public_records_actions.py enqueue us-ny-nyscef \
    --operation fetch_document --selector "156728/2019 document 42" \
    --output "$WORKDIR/nyscef-document-action.json"

# ACRIS selected-image/copy route from an index document ID
uv run python tools/public_records_actions.py plan us-nyc-acris-images \
    --operation open_selected_image --selector 2017021700466001 \
    --output "$WORKDIR/acris-image-plan.json"

# Recorder product candidates (catalog/action routes, not query adapters)
uv run python tools/public_records_actions.py plan \
    us-fl-miami-dade-official-records --operation request_bulk_files \
    --selector "Miami-Dade deed index" \
    --output "$WORKDIR/miami-recorder-plan.json"
uv run python tools/public_records_actions.py plan \
    us-tx-harris-clerk-real-property --operation request_bulk_index \
    --selector "Harris County real-property index" \
    --output "$WORKDIR/harris-recorder-plan.json"

# Targeted court and compiled-data candidates
uv run python tools/public_records_actions.py plan us-pa-ujs-public-dockets \
    --operation fetch_docket_sheet --selector "CP-00-CR-0000042-2026" \
    --output "$WORKDIR/pennsylvania-docket-plan.json"
uv run python tools/public_records_actions.py plan us-md-aoc-court-data \
    --operation request_court_data --selector "civil judgments" \
    --output "$WORKDIR/maryland-court-data-plan.json"

# Adapter/extraction/triage gold-set evaluation
uv run python tools/public_records_eval.py template \
    --output "$WORKDIR/public-record-eval-template.json"
uv run python tools/public_records_eval.py run "$WORKDIR/public-record-gold.json" \
    --output "$WORKDIR/public-record-eval.json"
```

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
uv run python tools/query_usaspending.py award 70CDCR26FR0000002            # Full award detail; plain PIID resolves first
uv run python tools/query_usaspending.py recipient "QUERY"                   # Recipient profile + agency breakdown
uv run python tools/query_usaspending.py subawards "RECIPIENT"               # Subcontractor/subgrantee data
uv run python tools/query_usaspending.py transactions "RECIPIENT" --date-range 2020-01-01,2024-12-31
uv run python tools/query_usaspending.py transactions --uei JMLKZZ1NL2Z6 \
    --agency "U.S. Immigration and Customs Enforcement" --agency-tier subtier --output /tmp/transactions.json
uv run python tools/query_usaspending.py timeline "RECIPIENT" --group fiscal_year  # Spending trend
uv run python tools/query_usaspending.py geography "RECIPIENT" --geo-layer state   # Geographic distribution
uv run python tools/query_usaspending.py top-recipients --agency "Department of Defense" --limit 10
uv run python tools/query_usaspending.py agencies --limit 10                 # List top-tier federal agencies
uv run python tools/query_usaspending.py covid "QUERY"                       # COVID-19 relief awards
uv run python tools/query_usaspending.py loans "QUERY"                       # Loan awards (PPP, EIDL, etc.)
# Transaction-level keyword search — sees scope added by modification, which award search cannot
uv run python tools/query_usaspending.py transactions-keyword "skip tracing" --all-pages --output /tmp/hits.json
uv run python tools/query_usaspending.py transactions-keyword "wellness check" --naics 561611 --psc R799 \
    --agency "U.S. Immigration and Customs Enforcement" --agency-tier subtier --output /tmp/ice.json
```

### FPDS-NG (contract actions + workflow/approval fields — no auth)
```bash
# Only source for createdBy / lastModifiedBy / approvedBy. Cite as source token `fpds`.
uv run python tools/query_fpds.py piid 70CDCR26FR0000014 --output /tmp/actions.json
uv run python tools/query_fpds.py search 'VENDOR_UEI:D13LLJJZYH64' --max-pages 5 --output /tmp/vendor.json
uv run python tools/query_fpds.py piid PIID --from-file saved-feed.xml       # offline parse of saved XML
uv run python tools/query_fpds.py search 'VENDOR_UEI:UEI' --with-metadata --output /tmp/vendor.json
```
Workflow-field keys are camelCase (`createdBy`, `lastModifiedBy`, `approvedBy`) while most other keys are
snake_case; snake_case reads of those three silently return `None`.

Rows carry `record_type`: `award` for a dated contract action, `IDV` for the vehicle those actions are
placed against. A vendor whose only presence is an IDV base award still has contracting history — do not
read an absent `award` row as a first-time entrant. Hitting `--max-pages` truncates results: the tool warns
on stderr, exits 2, and sets `truncated` in `--with-metadata` output. See `docs/modules/government.md`.

### Federal Register (rules, notices, presidential documents — no auth)
```bash
# Full-text search (uses the `term` condition under the hood)
uv run python tools/query_federal_register.py search "QUERY" --start-date 2025-01-01 --output FILE
uv run python tools/query_federal_register.py search "QUERY" --agency navy-department --doc-type NOTICE --output FILE

# Term/keyword search (often a person/organization name)
uv run python tools/query_federal_register.py term "NAME" --limit 50 --output FILE

# Documents from a specific agency (use slug — list-agencies to discover)
uv run python tools/query_federal_register.py agency navy-department --start-date 2025-01-01 --output FILE
uv run python tools/query_federal_register.py list-agencies | grep -i defense

# Presidential documents (proclamations, EOs, memoranda, determinations)
uv run python tools/query_federal_register.py presidential --start-date 2025-03-01 --end-date 2025-04-15 --output FILE
uv run python tools/query_federal_register.py presidential --type executive_order --start-date 2025-01-20 --output FILE

# Single document fetch (with optional full text)
uv run python tools/query_federal_register.py document 2025-06461
uv run python tools/query_federal_register.py document 2025-06461 --full-text --output FILE
```
Citation token: `[FR:2025-06461]` -> Federal Register document URL.

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

### El Peruano (Peru official gazette — Diario Oficial, no auth)
```bash
# Search normative documents (Decretos Supremos, Resoluciones Supremas/Ministeriales).
# Endpoint: POST https://busquedas.elperuano.pe/api/graphql?op=Generic
uv run python tools/query_elperuano.py search "QUERY" --output FILE          # Full-text search across all NL
uv run python tools/query_elperuano.py search "F-16" --year 2026 --type DS --output FILE
uv run python tools/query_elperuano.py search "Comandante FAP" --date-from 20251101 --date-to 20251130 --output FILE
uv run python tools/query_elperuano.py search "QUERY" --paginate --max-pages 5 --output FILE

# Fetch a specific dispositivo by op id (from URL: /dispositivo/NL/<op>) or full URL.
uv run python tools/query_elperuano.py document 2493140-1 --full-text --output doc.json
uv run python tools/query_elperuano.py document 2493140-1 --pdf --output doc.pdf

# All dispositivos published on a single date.
uv run python tools/query_elperuano.py daily 2026-03-05 --output day.json

# Persist to datasets/elperuano/ AND register a finding (use direct_quote/confirmed since
# the sumilla is verbatim from the primary source).
uv run python tools/ingest_elperuano.py 2493140-1 \
    --finding "Lockheed Martin Peru sale" \
    --claim-type direct_quote --confidence confirmed
```

### Medicare (CMS spending, no auth)
```bash
uv run python tools/query_medicare.py search "Enkeshafi"
uv run python tools/query_medicare.py provider 1003000126
uv run python tools/query_medicare.py search "Health" --limit 20
```

### CMS Open Payments (industry payments to clinicians, no auth)
```bash
# Discover current stable dataset IDs and official bulk CSV links.
uv run python tools/query_openpayments.py datasets --query "2025 General" --output FILE

# Exact covered-recipient lookup by last name or NPI. Add first name/state to disambiguate.
uv run python tools/query_openpayments.py search MERKIN --first-name MICHAEL --state NY --output FILE
uv run python tools/query_openpayments.py search 1952494221 --output FILE

# Reporting-company and nature-of-payment summaries for one CMS profile ID.
uv run python tools/query_openpayments.py payments 704135 --year all --output FILE
uv run python tools/query_openpayments.py payments 704135 --year 2025 --output FILE

# Bounded exact-match access to any dataset returned by `datasets` (maximum 500 rows).
uv run python tools/query_openpayments.py query DATASET_UUID \
  --where covered_recipient_profile_id=704135 --limit 25 --output FILE
```

The tool uses CMS's current DKAN API at `openpaymentsdata.cms.gov/api/1`. It reports the
server's total count and whether the local page is truncated. Full CSV URLs are returned
as catalog metadata, but bulk data is not downloaded automatically. Profile results emit
the canonical citation form `OPENPAYMENTS:<profile_id>`.

### CourtListener (federal courts — COURTLISTENER_TOKEN in .env, 17 commands)
```bash
# Search with field operators (party, firm, attorney, judge, docket number)
uv run python tools/query_courtlistener.py search "QUERY" --output FILE
uv run python tools/query_courtlistener.py search --party "NAME" --court nysd --output FILE
uv run python tools/query_courtlistener.py search --firm "FIRM" --attorney "ATTORNEY" --output FILE
uv run python tools/query_courtlistener.py search --assigned-to "JUDGE" --after 2020-01-01 --output FILE
uv run python tools/query_courtlistener.py search "QUERY" --type o --semantic --output FILE

# Cases and dockets
uv run python tools/query_courtlistener.py cases "QUERY" --court nysd --after 2015-01-01 --output FILE
uv run python tools/query_courtlistener.py docket 16066603 --output FILE
uv run python tools/query_courtlistener.py party "PERSON_NAME" --court flsd --output FILE

# Opinions and full text
uv run python tools/query_courtlistener.py opinions "QUERY" --court ca2 --semantic --output FILE
uv run python tools/query_courtlistener.py opinion 12345 --lines 1000
# Auto mode treats IDs as clusters first; use --id-type opinion for a known raw opinion ID.

# Citation graph
uv run python tools/query_courtlistener.py citations <OPINION_ID> --output FILE
uv run python tools/query_courtlistener.py resolve-cite "473 F.Supp.2d 1185" --output FILE
uv run python tools/query_courtlistener.py cluster <CLUSTER_ID> --output FILE

# RECAP documents (download PDFs from storage.courtlistener.com)
uv run python tools/query_courtlistener.py recap-search "QUERY" --court flsd --output FILE
uv run python tools/query_courtlistener.py download "URL" output.pdf --extract-text

# Judge financial disclosures (1.9M investment records)
uv run python tools/query_courtlistener.py investments "COMPANY" --output FILE
uv run python tools/query_courtlistener.py reimbursements "SOURCE" --output FILE
uv run python tools/query_courtlistener.py disclosures --person-id 1234 --output FILE

# Judge career and info
uv run python tools/query_courtlistener.py career "JUDGE_NAME" --output FILE
uv run python tools/query_courtlistener.py judge "NAME" --output FILE

# FJC Integrated Database (federal case metadata)
uv run python tools/query_courtlistener.py fjc --defendant "NAME" --output FILE
uv run python tools/query_courtlistener.py fjc --plaintiff "NAME" --after 2010-01-01 --output FILE
```

### Military Justice — CAAF + service CCAs (no auth, polite scraping)

Unified scraper for the U.S. Court of Appeals for the Armed Forces (CAAF) and
the four service Courts of Criminal Appeals (ACCA, NMCCA, AFCCA, CGCCA).
These courts publish dockets and opinions on disparate static sites and are
NOT in CourtListener — military court-martial appeals (e.g. Eddie Gallagher 2019)
do not appear in CourtListener.

**Killer feature**: `attorney <NAME>` cross-searches every reachable opinion PDF
for a civilian counsel name and returns each case where that name appears.

```bash
# Cross-court keyword search (uses cached indices)
uv run python tools/query_military_justice.py search "Bergdahl" --output FILE
uv run python tools/query_military_justice.py search "Edward Gallagher" --refresh --output FILE

# CAAF October Term opinion index (year or 'current')
uv run python tools/query_military_justice.py caaf-dockets 2024 --output FILE
uv run python tools/query_military_justice.py caaf-dockets current --output FILE

# Fetch a CAAF opinion PDF and extract counsel/disposition/panel
uv run python tools/query_military_justice.py caaf-opinion 24-0156/AR --output FILE
uv run python tools/query_military_justice.py caaf-opinion 24-0156/AR --full-text --output FILE

# Service-court searches
uv run python tools/query_military_justice.py acca-search "Burke" --output FILE
uv run python tools/query_military_justice.py afcca-search "Smith" --output FILE
uv run python tools/query_military_justice.py nmcca-search "Gallagher" --output FILE   # form-POST limitation
uv run python tools/query_military_justice.py cgcca-search "Mieres" --output FILE      # 403 from CDN

# Killer feature: find every opinion where <NAME> appears as counsel
uv run python tools/query_military_justice.py attorney "Conway" --pdf-limit 200 --output FILE
uv run python tools/query_military_justice.py attorney "Parlatore" --skip-refresh --output FILE

# One-docket detail (counsel, panel, disposition, decision date)
uv run python tools/query_military_justice.py case-detail "24-0156/AR" --output FILE
```

**Coverage and limitations**:
- **CAAF** (`armfor.uscourts.gov`): full coverage — term-page index + PDF opinions + Daily Journal docket actions parsed.
- **AFCCA** (`afcca.law.af.mil`): full coverage of the public opinion index; docket page has no attorney info.
- **ACCA** (`jagcnet.army.mil/ACCALibrary`): full coverage of OC/MO/SFA/SD opinion lists; URLs return PDFs even though they don't end in `.pdf`.
- **NMCCA** (`jag.navy.mil/.../nmcca/opinions/`): server-rendered POST search form (Sitecore). Tool fetches the index page only — full party/docket search requires browser-backed automation. Counsel names are still discoverable via the cross-court `attorney` command (which scans CAAF opinions that originated from NMCCA).
- **CGCCA** (`uscg.mil/.../CGCCA-Opinions/`): returns 403 to non-browser User-Agents (Akamai/CDN). Use `--user-agent` override with a real browser UA, or query the FindLaw mirror at `caselaw.findlaw.com/court/u-s-coa-gua-crt-cri-app`.
- All HTTP and PDF responses are cached in `datasets/military_justice_cache.db` (SQLite WAL). Default rate limit is 1 req/sec per host (`--rate-limit` to override).

### NYSCEF (New York state courts — structured human action)

The cataloged source `us-ny-nyscef` currently dispatches as
`human_required`; these commands write the requested criteria and official
manual-search URLs without launching a browser:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_nyscef.py search "Jeffrey Epstein" --output "$WORKDIR/nyscef-search.json"
uv run python tools/query_nyscef.py case 156728/2019 --output "$WORKDIR/nyscef-case.json"
uv run python tools/query_nyscef.py documents <DOCKET_ID> --limit 20 \
    --output "$WORKDIR/nyscef-documents.json"
```

### IRS 990 Nonprofit Database (unified tool)

The unified `query_990.py` combines bulk grant data (2009-2024, all US nonprofits), ProPublica metadata/filings, and officer/financial analysis. The old `query_990_propublica.py` still exists as an internal module but agents should use `query_990.py` for all 990 queries.

**Search & discovery:**
```bash
python tools/query_990.py search "Gratitude America"              # FTS5 search grants + related orgs
python tools/query_990.py lookup 660789697                        # comprehensive EIN view (metadata + financials + officers + grants)
python tools/query_990.py filings 660789697                       # filing list with PDF links (via ProPublica)
```

**Grant analysis:**
```bash
python tools/query_990.py filer 660789697                         # grants MADE by EIN
python tools/query_990.py recipient "Gratitude"                   # grants RECEIVED by name (FTS5)
python tools/query_990.py recipient-ein 030213226                 # grants RECEIVED by EIN
python tools/query_990.py network 660789697 --depth 2             # BFS grant graph from seed EIN
python tools/query_990.py co-grantors "MELANOMA RESEARCH ALLIANCE"  # shared funders
python tools/query_990.py cross-ref                               # match investigation.db entities
python tools/query_990.py top --by amount --limit 20              # top grantmakers (also: count, recipients, single)
```

**Officers & compensation:**
```bash
python tools/query_990.py officers 660789697                      # officers/directors for a nonprofit by EIN
python tools/query_990.py officer-search "John Smith"             # find a person across ALL nonprofits (board overlap detection)
python tools/query_990.py top-compensated                         # highest-compensated nonprofit officers
```

**Financial analysis & red flags:**
```bash
python tools/query_990.py financials 660789697                    # financial summary over time (revenue, expenses, assets)
python tools/query_990.py red-flags 660789697                     # red-flag analysis (ratios + checklist + insiders)
```

### IRS 990 XML (Schedule I grants + Schedule R related orgs)

Separate ingestion tool for XML-level parsing. Use `query_990.py` for queries; use `ingest_990_xml.py` only for ingestion/reprocessing.
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

### IRS 990 Bulk Ingestion (data pipeline only)

Use `ingest_990_bulk.py` only for downloading/processing bulk data. All queries go through `query_990.py` above.
```bash
python tools/ingest_990_bulk.py download-index               # 1.3GB parquet from Giving Tuesday S3
python tools/ingest_990_bulk.py explore-index                # show schema, form types, year range
python tools/ingest_990_bulk.py process --form-type 990PF    # download + parse 990-PF grants (~1.5h)
python tools/ingest_990_bulk.py process --form-type 990      # download + parse 990 grants (~4.5h)
python tools/ingest_990_bulk.py process --form-type 990PF --year-start 2018 --year-end 2018  # single year
python tools/ingest_990_bulk.py resume                       # continue interrupted run
python tools/ingest_990_bulk.py build-fts                    # build FTS5 after bulk load
python tools/ingest_990_bulk.py stats                        # DB stats + process run history
```

### NYC ACRIS (property records, SODA API)
```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_acris.py party "PERSON_NAME" --output "$WORKDIR/acris-party.json"
uv run python tools/query_acris.py address --borough 1 --block 1386 --lot 10 \
    --output "$WORKDIR/acris-address.json"
uv run python tools/query_acris.py history --property-name "71st" \
    --output "$WORKDIR/acris-history.json"
uv run python tools/query_acris.py batch-entities --output "$WORKDIR/acris-batch.json"
```
Remote commands return the canonical public-record envelope with enriched
document, party, legal, master, and remark joins. Use `--cursor` for the next
page and `--catalog-db` to inspect an alternate catalog.

### Louisiana Property Records (SODA API, East Baton Rouge)
```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_la_property.py owner "LANDRY" --parish ebr \
    --output "$WORKDIR/ebr-owner.json"
uv run python tools/query_la_property.py address "HIGHLAND" --parish ebr \
    --output "$WORKDIR/ebr-address.json"
uv run python tools/query_la_property.py parcel "030-7623-7" --parish ebr \
    --output "$WORKDIR/ebr-parcel.json"
uv run python tools/query_la_property.py details "3076237" --parish ebr \
    --output "$WORKDIR/ebr-details.json"
uv run python tools/query_la_property.py adjudicated "WILLIAMS" --parish ebr \
    --output "$WORKDIR/ebr-adjudicated.json"
uv run python tools/query_la_property.py parishes --output "$WORKDIR/ebr-parishes.json"
```
Datasets: Tax Roll (owner names, values, legal), Tax Parcel (owner, address,
values, GeoJSON), Property Info (address, zoning, land use), and Adjudicated
(tax-defaulted). Remote commands return canonical source-aware envelopes and
accept assessment numbers with or without dashes.

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

### Senate Finance Committee Archive (no auth)
```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_senate_finance.py search "media-based ministries" \
  --limit 20 --output "$WORKDIR/sfc-search.json"
uv run python tools/query_senate_finance.py item \
  /ranking-members-news/grassley-releases-review-of-tax-issues-raised-by-media-based-ministries \
  --output "$WORKDIR/sfc-item.json"
```
Searches the official `finance.senate.gov` archive with a 100-result maximum.
`item` extracts the article text and official related-file links. Results include
`SENATE_FINANCE:<path>` evidence references for the citation system.

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

### ICIJ Offshore Leaks (official remote API/pages; no auth)
```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_icij.py search "QUERY" --output "$WORKDIR/icij-search.json"
uv run python tools/query_icij.py entity NODE_ID --output "$WORKDIR/icij-entity.json"
uv run python tools/query_icij.py connections NODE_ID --output "$WORKDIR/icij-connections.json"
uv run python tools/query_icij.py officers NODE_ID --output "$WORKDIR/icij-officers.json"
# Optional local Neo4j for deeper traversal only:
uv run python tools/query_icij.py connections NODE_ID --depth 2 --local \
  --output "$WORKDIR/icij-connections-depth2.json"
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

### Selector Pivot (cross-aggregator selector fan-out)
```bash
# One selector (email/username/phone/domain/IP/name) -> linked selectors + candidate entities
python tools/selector_pivot.py run "Gazprom" --type company --output out.json
python tools/selector_pivot.py run "jane@example.com" --type email --enable-paid --output out.json  # +Dehashed/IntelX
python tools/selector_pivot.py adapters --type name   # routing + availability
```
Free adapters (opensanctions, gleif, icij, littlesis, crt.sh, maigret) run by default; `--enable-paid` adds the gated leak adapters (Dehashed live, IntelX needs a key). Paid adapters fire only on the seed selector (bounds credit cost); discovered selectors re-pivot through free sources. Emits `pending_triage` leads + entities; leak-sourced findings cap at `medium`. Aggregators-only posture. Full notes: `docs/modules/network-sanctions.md`.

### Dehashed (breach/credential aggregator — DEHASHED_API_KEY, active v2 subscription)
```bash
python tools/query_dehashed.py search --email "jane@example.com" --output out.json
python tools/query_dehashed.py search --username jdoe --output out.json
python tools/query_dehashed.py search --domain example.com --size 100 --output out.json
python tools/query_dehashed.py balance   # remaining credits (~1 credit)
```
v2 needs an ACTIVE search subscription (not just a credit balance — a lapsed sub 401s). Single page by default (≈1 credit/call); `--paginate` to fetch more. `*` wildcard is server-broken — use `?`. Result fields come back as lists.

### Investigation-Specific Corpus (1,271 persons, 1.5M docs, REST API)
```bash
python tools/ingest_epstein_exposed.py download
python tools/ingest_epstein_exposed.py search "QUERY"
python tools/ingest_epstein_exposed.py person "person-slug"
python tools/ingest_epstein_exposed.py flights --passenger "PERSON_NAME" --year 2002
python tools/ingest_epstein_exposed.py match-entities
```

### MuckRock FOIA (API v2, authenticated; default project #507)

Requires a normal MuckRock account in the repo-local `.env`. The official
wrapper manages API-v2 access and refresh tokens:

```dotenv
MUCKROCK_USERNAME=your_username
MUCKROCK_PASSWORD=your_password
```

```bash
uv run python tools/query_muckrock.py project 507
uv run python tools/query_muckrock.py request 78799  # USMS
uv run python tools/query_muckrock.py download 78799 --dir datasets/muckrock
uv run python tools/query_muckrock.py search "Jeffrey Epstein" --limit 25
uv run python tools/query_muckrock.py agencies "Federal Bureau"
uv run python tools/query_muckrock.py crawl-index --output /tmp/muckrock-crawl.json
uv run python tools/query_muckrock.py crawl-index --max-pages 1 --output /tmp/muckrock-sample.json
uv run python tools/query_muckrock.py index-stats --output /tmp/muckrock-stats.json
uv run python tools/query_muckrock.py index-search "GEO Group" --without-documentcloud --responses-only --output /tmp/muckrock-index.json
uv run python tools/query_muckrock.py unlinked-files "private prison" --limit 50 --output /tmp/muckrock-unlinked.json
```

`crawl-index` creates the resumable `datasets/muckrock_index.db` catalog of
public requests, communication bodies, file metadata, agencies, jurisdictions,
and request/file linkages. `unlinked-files` searches all three text layers and
returns incoming response attachments whose MuckRock `doc_id` is blank. Treat
that as no direct DocumentCloud linkage, not proof that no separately uploaded
duplicate exists. Local `index-search`, `unlinked-files`, and `index-stats` do
not require API credentials after the index has been built.

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

### SEC Enforcement Actions (~33K actions, litigation + admin + AAER, 1995-present)
```bash
# Ingest
python tools/ingest_sec_enforcement.py ingest                           # All sources, all pages
python tools/ingest_sec_enforcement.py ingest --source litigation       # One source type
python tools/ingest_sec_enforcement.py ingest --pages 3                 # First 3 pages only
python tools/ingest_sec_enforcement.py ingest --incremental             # Stop at existing entries
python tools/ingest_sec_enforcement.py stats                            # Summary counts
python tools/ingest_sec_enforcement.py reparse                          # Re-run defendant parsing

# Query
python tools/query_sec_enforcement.py search "insider trading" --output $WORKDIR/sec-search.json
python tools/query_sec_enforcement.py search "Epstein" --source litigation --output $WORKDIR/sec-epstein.json
python tools/query_sec_enforcement.py defendant "Leon Black" --output $WORKDIR/sec-defendant.json
python tools/query_sec_enforcement.py defendant "JPMorgan" --fuzzy --threshold 80 --output $WORKDIR/sec-fuzzy.json
python tools/query_sec_enforcement.py action LR-26503 --output $WORKDIR/sec-action.json
python tools/query_sec_enforcement.py co-defendants LR-26489 --output $WORKDIR/sec-codefs.json
python tools/query_sec_enforcement.py network "Joseph Lewis" --depth 2 --output $WORKDIR/sec-network.json
python tools/query_sec_enforcement.py repeat-offenders --min-actions 2 --output $WORKDIR/sec-repeats.json
python tools/query_sec_enforcement.py stats --by-year --output $WORKDIR/sec-stats.json
python tools/query_sec_enforcement.py cross-ref --dry-run --output $WORKDIR/sec-crossref.json
python tools/query_sec_enforcement.py cross-ref --auto-leads            # Generate investigation leads
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

Use the tracker for reviewed metadata corrections. The field whitelist excludes
`name`, IDs, creation metadata, and agent provenance; identity changes belong in
the alias and merge workflows below. Every effective correction requires a
reason and appends the old and new values to `corrections`.

```bash
uv run python tools/entity_tracker.py lookup --name "ENTITY"
uv run python tools/entity_tracker.py show 3720 --output "$WORKDIR/entity-3720.json"
uv run python tools/entity_tracker.py correct 3720 --field notes \
  --value "Reviewed canonical notes" \
  --reason "Replace stale summary after primary-evidence review" --by analyst
uv run python tools/findings_tracker.py audit 3720 --table entities --json
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
# Replace stale/contradictory notes with a reviewed canonical note during merge
uv run python tools/entity_dedup.py merge --keep-id 2 --delete-id 134 \
  --replacement-notes 'Identity confirmed by reviewed primary records.'

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

## Queue Dispatcher (generic job queue)

Generic worker pool manager — spawns agent workers based on pending job types. Uses `job_queue` and `agent_instances` tables. Config: `scripts/queue_dispatch_config.json`.

> **Note**: This is the generic execution plane (HOW workers run). For investigation-aware dispatch (WHAT to run based on lead priorities, triage scheduler, analysis cooldowns), use `dispatcher.py` below.

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

## Investigation Dispatcher (primary)

Investigation-aware dispatcher — launches headless Claude Code instances based on lead priorities, triage scheduler fields (depth_tier, recommended_skill), and analysis cooldowns. Uses `dispatch_runs` table. Config: `scripts/dispatch_config.json`.

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

# Delete one audited career arc by ID
uv run python tools/pillar_tracker.py arc-delete ARC_ID

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

### papercut.py

Small, memorable front door for friction observations. Use it at the moment a dead command, misleading error, stale instruction, missing check, or similar repository issue gets in the way. Entries remain available through `methodology_tracker.py`.

```bash
# Log a papercut (only the message is required)
uv run python tools/papercut.py "query_doj.py reports a 404 for a valid document"

# Include concise reproduction details
uv run python tools/papercut.py "Unquoted glob was expanded by zsh" \
  --command "rg --glob *.json term" --expected "Search nested JSON files" \
  --context "Run from the repository root" --skill pursue-lead

# Review the open cleanup queue
uv run python tools/papercut.py --list [--limit 50]

# Close after fixing the root cause, or dismiss with a documented reason
uv run python tools/papercut.py --resolve <ID> --resolution "Quoted globs in agent examples; tests pass"
uv run python tools/papercut.py --dismiss <ID> --reason "Duplicate of #12"

# Consolidate duplicate reports
uv run python tools/papercut.py --duplicate <ID> --of <CANONICAL_ID>

# Hand substantial work to the infrastructure queue
uv run python tools/papercut.py --promote <ID> --infra-id <INFRA_ID>
```

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
uv run python tools/methodology_tracker.py duplicate <ID> --of <CANONICAL_ID>
uv run python tools/methodology_tracker.py promote <ID> --infra-id <INFRA_ID>

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
