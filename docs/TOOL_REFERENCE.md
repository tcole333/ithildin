# Tool Reference

CLI examples and module routes for investigation tools. For a compact offline
inventory and parser declarations, use:

```bash
uv run python tools/tool_catalog.py list --domain legal --query court --limit 10 --json
uv run python tools/tool_catalog.py describe query_courtlistener search --json
```

The catalog reads repository declarations without importing source tools or
probing endpoints. It reports incomplete/dynamic declarations and points to
operation-specific `--help`; inspect that help before a new command. Module
guides explain access, evidence identity, output scope and source limitations.
Catalog presence is not a live health claim. For read-only investigation status,
use `tools/investigation_status.py --profile NAME --db PATH --output FILE`.

Before choosing a dispatcher, submitting workers, or reviewing/recovering their
output, read the [execution contract](EXECUTION_CONTRACT.md) for context pinning,
canonical writes, review/import, and cancellation guarantees.

Run `uv run python tools/source_report.py` for live data source status.

## Scoped lead review

For lead review operations, `lead_tracker.py triage-export --output FILE` captures
a profile/database-bound packet. Include external duplicate keepers with repeated
`--reference-lead-id ID`. Review the packet, then use `triage-apply --batch-file
FILE --decisions-file FILE --dry-run --output FILE`; omit `--dry-run` only for an
authorized application. It validates complete snapshots and applies atomically.

`lead_dedup.py apply` now requires both `--batch-file` and `--decisions-file`.
Unbound legacy decisions must be re-exported and reviewed. Export every disjoint
packet for a wave before applying any, then reset offsets for the next wave as
processed groups leave the queue. See the paired triage/dedup skills for schemas,
write ownership, and disposition rules.

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
| `doj_court_release` | query_doj_court_records.py | Official DOJ Epstein case-grouped court-record release copies; not the complete underlying dockets |
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
| `ny_attorneys` | query_ny_attorneys.py | New York OCA quarterly attorney registrations, status, admission, and office/organization data |
| `nyscef` | query_nyscef.py | NYSCEF New York state court records |
| `nyscef_fulltext` | query_nyscef_fulltext.py | Normalize acquired NYSCEF manifests/PDFs, extract page text/OCR, and build/search a local FTS5 corpus |
| `dc_appellate_cases` | query_dc_appellate_cases.py | D.C. Court of Appeals C-Track cases, participants, originating matters, dockets, and filing PDFs |
| `dc_opinions` | query_dc_opinions.py | D.C. Court of Appeals opinion PDFs and Memorandum Opinion and Judgment index metadata |
| `dc_court_calendars` | query_dc_superior_calendar.py | D.C. Superior Court hearing calendars, Tax Division calendar PDFs, and Court of Appeals calendar artifacts |
| `dc_court_directory_data` | query_dc_court_directory_data.py | D.C. judicial directories and contacts, data-request forms, and aggregate report publications |
| `md_public_cases` | query_md_public_cases.py | Maryland MDEC rolling Cases Filed PDFs with case, party/address, and charge extraction |
| `md_estate_search` | query_md_estate_search.py | Maryland statewide decedent, personal-representative, estate-number, detail, and docket search |
| `md_estate_notices_claims` | query_md_estate_notices_claims.py | Maryland statewide estate legal-notice occurrences and filed-claim records with exact detail enrichment |
| `md_judgment_liens` | query_md_judgment_liens.py | Maryland Circuit Court judgment/lien person and company searches plus exact event history |
| `md_opinions` | query_md_opinions.py | Maryland reported/unreported appellate indexes, metadata-only historical rows, official PDFs, and case joins |
| `md_business_opinions` | query_md_business_opinions.py | Maryland Business and Technology selective trial-court publications, official PDF/DOC/WPD attachments, and case joins |
| `md_plats` | query_md_plats.py | Maryland State Archives Plats.net county, book/page, plat, right-of-way, description, filing-date, and archive-series search; metadata-only units and PDF/TIFF/JPEG representations are retained |
| `michigan_appellate` | query_michigan_appellate.py | Michigan appellate cases, opinions, orders, lower-court pivots, attorney P-numbers, and official PDFs |
| `michigan_business_court` | query_michigan_business_court.py | Michigan Business Court document search, native facets, case-label candidates, and official PDFs |
| `washington_courts` | query_washington_courts.py | Washington AOC court directory and appellate opinions plus official case, document, data-product, caseload, and historical routes |
| `wisconsin_court_directory` | query_wisconsin_court_directory.py | Wisconsin circuit offices, clerks, judges, administrative districts, appellate offices, state offices, and local-source discovery |
| `california_opinions` | query_california_opinions.py | California current published slip and unpublished appellate-opinion feeds, exact detail formats, citings archives, and complementary older/corrected-text routes |
| `california_court_directory` | query_california_court_directory.py | California’s official 58-county superior-court and service-route directory |
| `santa_clara_court_records` | query_santa_clara_court_records.py | Santa Clara tentative-ruling PDFs, requested case-index products, and portal access state |
| `san_diego_court_index` | query_san_diego_court_index.py | San Diego party/case index, case detail, recent filing lists, and official alternatives |
| `fresno_court` | query_fresno_superior_court.py | Fresno daily hearing calendars, civil tentative rulings, Probate Examiner Notes, and official case-record alternatives |
| `orange_county_court` | query_orange_county_court.py | Orange County, California hearing calendars, current tentative-ruling PDFs/text, and official substitute routes |
| `riverside_court` | query_riverside_court.py | Riverside, California eCourtCalendars, tentative-ruling PDFs/text, and official substitute routes |
| `qld_ecourts` | query_qld_ecourts.py | Queensland Supreme and District Court civil case search, parties, events, document metadata, and complementary official routes |
| `la_civil_court` | query_los_angeles_court.py | Los Angeles Superior Court civil Case Summary sections and current full-text tentative rulings |
| `la_civil_name_index` | query_los_angeles_name_index.py | Los Angeles Superior Court paid party-name discovery, cart preparation, receipt recovery, and purchased-result normalization |
| `philadelphia_property` | query_philadelphia_property.py | Philadelphia OPA current assessments, annual history, DOR parcel polygons, and official recorded-document alternatives |
| `michigan_property_directories` | query_michigan_property_directories.py | Michigan DTMB's 83-county parcel-route directory, platform triage, discovery seeds, and official property-source complements |
| `wisconsin_parcels` | query_wisconsin_parcels.py | Wisconsin annual statewide parcels, assessment/tax fields, owner visibility, county lineage, geometry, and official bulk/local/transfer alternatives |
| `ohio_statewide_parcels` | query_ohio_statewide_parcels.py | Ohio OGRIP all-88-county parcel identifiers, address observations, land use, geometry, local-CAMA routes, and Franklin/Licking/Delaware source graph |
| `ohio_licking_property` | query_ohio_licking_property.py | Licking County Auditor parcel, assessment-owner, address, value, transfer-observation, building, and polygon records with GlobalID occurrence retention |
| `ohio_franklin_auditor_bulk` | query_ohio_franklin_auditor_bulk.py | Franklin County Auditor appraisal, tax-accounting, daily-conveyance, GIS, and parcel-release discovery, verified/resumable artifact download, inspection, and row streaming |
| `ohio_franklin_sales_gis` | query_ohio_franklin_sales_gis.py | Franklin County Auditor sale occurrences, exact parcel/conveyance joins, grantor/grantee search, date and qualification filters, structure context, and point geometry |
| `ohio_pax_recorders` | query_ohio_pax_recorders.py | Delaware anonymous PAX instrument search/detail/PDF and Licking account-state plus anonymous exact-instrument detail/PDF, with identity-preserving shared ingestion |
| `ohio_franklin_probate` | query_ohio_franklin_probate.py | Franklin County Probate case/name/type/date, attorney, and fiduciary indexes plus exact case detail and docket/person records |
| `ohio_sheriff_sales` | query_ohio_sheriff_sales.py | Franklin, Delaware, and Licking official RealAuction calendars, exhaustive auction listings, status overlays, and exact tenant+AID events |
| `licking_foreclosure_archive` | query_licking_foreclosure_archive.py | Licking County official foreclosure year inventory, complete selected-year arrays, rolling current subset, and exact case records |
| `new_york_parcels` | query_ny_statewide_parcels.py | New York statewide assessment/owner centroids, public and state-owned parcel polygons, exact cross-component joins, coverage, and official alternatives |
| `new_york_salesweb` | query_ny_salesweb.py | New York ORPTS buyer/seller transfer search, exact sale detail, reference tables, CSV export, and parcel joins |
| `census_acs` | query_census_acs.py | ACS 5-year demographic and housing estimates, published margins of error, point-estimate rates, and Census-geography joins |
| `new_jersey_parcels` | query_new_jersey_parcels.py | NJGIN parcel geometry and partial MOD-IV joins, with redacted-owner and unmatched-parcel states preserved |
| `new_jersey_sr1a` | query_new_jersey_sr1a.py | New Jersey Treasury SR1A release discovery, validation, and property-sale search |
| `new_jersey_tax_court` | query_new_jersey_tax_court.py | New Jersey Tax Court current local-property report discovery, complete XLSX search, validation, and alternative routes |
| `new_jersey_tax_court_opinions` | query_new_jersey_tax_court_opinions.py | New Jersey Tax Court published/unpublished index search, official document retrieval, transport-aware probing, and complementary routes |
| `new_jersey_dca_property` | query_new_jersey_dca_property.py | New Jersey DCA building-granular property registration, current lookup, keyset search, source probe, and alternative routes |
| `montana_cadastral` | query_montana_cadastral.py | Montana statewide live parcel/CAMA search, explicit 56-county ORION-to-Census crosswalk, and monthly parcel/ORION release discovery and transfer |
| `virginia_parcels` | query_virginia_parcels.py | VGIN statewide parcel identity, geometry, locality coverage/freshness, runtime item resolution, and official bulk/local/title complements |
| `virginia_beach_delinquent_tax` | query_va_beach_delinquent_tax.py | Virginia Beach current daily delinquent real-estate tax installments, exact-cent balances, GPIN joins, and official tax/property/court complements |
| `military_justice` | query_military_justice.py | CAAF + ACCA + NMCCA + AFCCA + CGCCA appellate dockets/opinions |
| `colorado_opinions` | query_colorado_opinions.py | Colorado appellate historical case law and current Judicial Branch release surfaces, with component provenance retained |
| `colorado_court_data` | query_colorado_court_data.py | Colorado Judicial reports, dashboards, and compiled/aggregate-data request materials |
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
| `orleans_property` | query_orleans_property.py | Orleans Parish current assessment accounts and parcels |
| `washington_digital_archives_land` | query_washington_digital_archives_land.py | Washington State Archives recorded-land title inventory, party index, exact instrument detail, image metadata state, and 13 county-recorder gap routes |
| `mason_county_tax_parcels` | query_mason_county_tax_parcels.py | Mason County current assessor/GIS names, addresses, values, parcel identifiers, legal/map fields, and polygons using FID-snapshot traversal |
| `washington_parcels` | query_washington_parcels.py | Washington statewide normalized parcel representations, county freshness, county land-use vocabularies, and same-lineage parity |
| `dc_property` | query_dc_property.py | D.C. ITSPE assessment/tax accounts, common-ownership polygons, CAMA sales, and Surveyor documents |
| `oregon_taxlots` | query_oregon_taxlots.py | Oregon publisher-scoped ArcGIS parcel, assessment, sale, owner-where-published, and geometry records |
| `oregon_benton_property` | query_oregon_benton_property.py | Benton County taxlot owner-party rows, parcel geometry, current bulk snapshots, and assessment-map PDFs |
| `oregon_lincoln_propertyweb` | query_oregon_lincoln_propertyweb.py | Lincoln County account search/detail, values, sales, taxes, payments, improvements, and property-document PDFs |
| `oregon_lincoln_taxlots` | query_oregon_lincoln_taxlots.py | Lincoln County WFS 2.0 taxlot identifiers, owners, addresses, assessor-map links, and optional geometry |
| `deschutes_property` | query_deschutes_property.py | Deschutes County relationship-aware parcels, owners, accounts, values, improvements, sales, and geometry |
| `deschutes_dial` | query_deschutes_dial.py | Deschutes County account detail, assessment/tax/payment history, sales, improvements, permits, development records, and property-report PDFs |
| `deschutes_cdd_weblink` | query_deschutes_laserfiche.py | Deschutes CDD account-linked Laserfiche metadata, folders, electronic files, and generated PDFs |
| `oregon_helion_property` | query_oregon_helion_property.py | Six county Helion/ORCATS Property Search Online account indexes, certified-roll values, tax state, sales, improvements, and reports |
| `oregon_helion_recorder` | query_oregon_helion_recorder.py | County-scoped Helion recorded-instrument indexes, exact detail, parties, legal/reference fields, and tenant-published document-delivery states |
| `oregon_tax_foreclosures` | query_oregon_tax_foreclosures.py | Four county foreclosure, redemption, tax-title, and tax-deed auction publication ecosystems with artifact/text provenance |
| `oregon_lane_marion_property` | query_oregon_lane_marion_parcels.py | Lane parcel and recent-sale components plus Marion parcel/value/latest-sale records |
| `oregon_lane_property` | query_oregon_lane_property.py | Lane property-account search/detail plus tax-map locator and official PDF retrieval |
| `oregon_marion_downloads` | query_oregon_marion_downloads.py | Marion current/historical assessor sales manifest and comprehensive assessment snapshot: probe, resumable transfer, inspection, local search, and shared projection |
| `oregon_jackson_douglas_assessors` | query_oregon_jackson_douglas_assessors.py | Jackson taxlots and Douglas assessor parcels, owners, addresses, values, identifiers, sale references, and geometry |
| `oregon_jackson_property_events` | query_oregon_jackson_property_events.py | Separate Jackson building-permit, land-use-permit, and code-compliance event layers |
| `oregon_jackson_accela` | query_oregon_jackson_accela.py | Jackson Building and Planning record detail, attachments, stable document metadata, and document binaries |
| `washington_taxsifter` | query_washington_taxsifter.py | Eleven Washington county TaxSifter assessor, treasurer, appraisal, and assessor-sale tenants with source-native identity and operation states |
| `oregon_yamhill_property` | query_oregon_yamhill_property.py | Yamhill AscendWeb accounts, current and retired taxlots, assessment permits, and geometry |
| `oregon_clackamas_property` | query_oregon_clackamas_property.py | Clackamas AscendWeb accounts and CMap taxlots with an exact account join |
| `oregon_wasco_property` | query_oregon_wasco_property.py | Wasco AscendWeb accounts, taxlots, eight survey-index layers, and selected attachments |
| `oregon_washington_property` | query_oregon_washington_property.py | Washington County Survey Explorer records/documents, survey and taxlot geometry, situs points, Intermap assessment reports, and WashCoTax accounts/statements |
| `oregon_washington_case_permits` | query_oregon_washington_case_permits.py | Washington County planning casefiles, taxlot project/activity links, building permits, permit reports, Accela CurrentPlanning records/documents, and official casefile document routes |
| `oregon_multnomah_sail` | query_oregon_multnomah_sail.py | Eight Multnomah County SAIL tax-parcel, survey, plat, road, corner, field-book, image-viewer, and PDF representations |
| `oregon_appellate` | query_oregon_appellate.py | Oregon Supreme Court and Court of Appeals cases, parties, dockets, events, and document metadata |
| `oregon_appellate_calendars` | query_oregon_appellate_calendars.py | Separate Supreme Court and Court of Appeals calendar lists with complete SharePoint continuation and published attachments |
| `oregon_court_calendar` | query_oregon_court_calendar.py | Oregon Circuit and Tax Court locations, judicial officers, and hearing-calendar searches |
| `oregon_court_directories` | query_oregon_court_directories.py | Oregon state/local court and judge directories plus official local-source discovery seeds |
| `oregon_tyler_municipal_courts` | query_eugene_municipal_court.py | Eight Oregon Tyler Municipal Record Search tenants with tenant-specific case/docket access, selectors, court identity, and official alternatives |
| `oregon_court_documents` | query_oregon_court_documents.py | Oregon Supreme Court, Court of Appeals, Tax Court, appellate brief, and selected order collections |
| `oregon_smart_search` | query_oregon_smart_search.py | Oregon Circuit and Tax Court rendered search contract, live options, and browser-ready handoffs |
| `oregon_ojcin_products` | query_oregon_ojcin_products.py | OECI, ACMS, standard reports, bulk transfer, OSCA handoffs, official route probes, and delivery receipts |
| `reeves_records` | query_reeves_records.py | Reeves County recorded instruments, OCR, detail, and page images |
| `govos_recorders` | query_govos_recorders.py | Configured county recorder indexes, OCR, detail, and page images |
| `rrc_bulk` | query_rrc_bulk.py | Texas RRC P-4 operator history, P-5 organizations, Wellbore records, and native-key resolution |
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
| `massachusetts_ucc` | query_massachusetts_ucc.py | Massachusetts public UCC search and filing lookup |
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

### Epstein Artifact Metadata Audit

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/epstein_metadata.py pilot --max-files 500 \
  --output "$WORKDIR/metadata-pilot.json"
uv run python tools/epstein_metadata.py scan PATH [PATH ...] \
  --collection local-import --output "$WORKDIR/metadata-scan.json"
uv run python tools/epstein_metadata.py report --reference-date 2019-07-06 \
  --output "$WORKDIR/metadata-report.json"
uv run python tools/epstein_metadata.py show EFTA01091533 \
  --output "$WORKDIR/metadata-show.json"
uv run python tools/epstein_metadata.py stats \
  --output "$WORKDIR/metadata-stats.json"
```

The scanner reads source files without modifying them and stores byte hashes,
locations, and format-aware observations in `datasets/epstein_derived.db`.
Metadata is separated into `source_native`, `production_lineage`,
`release_container`, `container_embedded`, and `acquisition` layers. Reports
redact GPS/location/originating-IP/BCC values unless `--include-sensitive` is
explicitly requested. ExifTool is optional; without it, image EXIF/IPTC/XMP
coverage is incomplete.

### Epstein Damaged-Artifact Recovery

```bash
uv run python tools/epstein_recovery.py ledger --actionable \
  --output "$WORKDIR/recovery-queue.json"
uv run python tools/epstein_recovery.py inspect INPUT --efta-id EFTA00147557 \
  --expected-sha256 HASH --output "$WORKDIR/inspect.json"
uv run python tools/epstein_recovery.py extract-text INPUT --pages 3-29 \
  --text-output "$WORKDIR/source.txt" \
  --candidate-output "$WORKDIR/candidate.b64.txt" \
  --output "$WORKDIR/text-audit.json"
uv run python tools/epstein_recovery.py ocr-pages INPUT --pages 4-28 \
  --ocr-dir "$WORKDIR/ocr" --psm 6 --psm 11 \
  --output "$WORKDIR/ocr-manifest.json"
uv run python tools/epstein_recovery.py decode-infopath CANDIDATE \
  --artifact-dir "$WORKDIR/artifacts" --write-artifact \
  --source-ref EFTA00147557 --output "$WORKDIR/decode.json"
```

The ledger at `investigations/epstein/recovery/ledger.json` is the deduplication
gate: completed public recoveries and finite sources with physically absent
bytes are excluded before new work begins. `decode-infopath` writes no artifact
unless strict Base64 and the full Microsoft InfoPath header, filename, and size
contract validate. Unknown media remains quarantined and metadata-only.

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

# Massachusetts UCC (public WebForms; Node Playwright + installed Chrome, no auth)
uv run python tools/query_massachusetts_ucc.py runtime-check --output "$WORKDIR/ma-ucc-runtime.json"
uv run python tools/query_massachusetts_ucc.py probe --output "$WORKDIR/ma-ucc-probe.json"
uv run python tools/query_massachusetts_ucc.py search-org "HARVARD" --limit 25 --output "$WORKDIR/ma-ucc-org.json"
uv run python tools/query_massachusetts_ucc.py search-individual "SMITH" --first "JOHN" --output "$WORKDIR/ma-ucc-person.json"
uv run python tools/query_massachusetts_ucc.py search-org "BANK" --role secured --search-type begins --output "$WORKDIR/ma-ucc-secured.json"
uv run python tools/query_massachusetts_ucc.py search-org "HARVARD" --lapsed --output "$WORKDIR/ma-ucc-lapsed.json"
uv run python tools/query_massachusetts_ucc.py filing "<FILING_NUMBER>" --output "$WORKDIR/ma-ucc-filing.json"

# Florida FLR (mostly IRS tax liens, NOT commercial UCC)
python tools/ingest_ucc_florida.py download && python tools/ingest_ucc_florida.py ingest
python tools/ingest_ucc_florida.py search "QUERY"

# New Mexico UCC
python tools/ingest_ucc_newmexico.py search "Zorro Ranch"
python tools/ingest_ucc_newmexico.py detail <internal_id>
```

Massachusetts search modes, role restrictions, date/location filters, occurrence
counts, citations, and complementary certified/lien routes are documented in
[the Massachusetts UCC section](modules/registries.md#massachusetts-ucc-query_massachusetts_uccpy).
The Massachusetts adapter performs live lookup without local registry ingestion.
`boston_ucc_runner.py --queue QUEUE.json --output-dir CAPTURE_DIR --scope current
--max-queries 20 --batch-size 20` adds resumable serial batches with one isolated
browser, raw HTML checkpoints, saved CUA-event import, and name-mode deferral.
The new persistent session path is offline tested; live parity is unverified.
The September 4, 2026 access denial stopped the run. A later search-form load
succeeded, but full-roster collection remains paused under the Secretary's
[published scraping restriction](https://www.sec.state.ma.us/divisions/terms.htm).
Use the official bulk-data service or another supported route for the full
roster; see the module for access options and checkpoint semantics.
For offline Boston follow-up, `uv run python tools/boston_ucc_filing_review.py build
--queue QUEUE.json --observations CAPTURE_DIR --samples SAMPLE_RESULTS.json
--output FILING_QUEUE.json` creates a per-original filing review queue. It retains
namesakes, separates original/amendment PDF tasks, and does not equate filings to
loans. Optional saved query-tool inputs and evidence-backed identity decisions
are described in the Massachusetts module above.

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
uv run python tools/seed_public_records_catalog.py --audit \
    --output "$WORKDIR/public-record-catalog-audit.json"
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
uv run python -m pytest tests/test_query_wisconsin_court_directory_live.py \
    --run-live-public-records
```

`ok`, true `no_results`, `partial`, `rate_limited`, `human_required`,
`terms_blocked`, `restricted`, `unavailable`, and `source_changed` remain
separate result states. Shared HTTP families provide Socrata and ArcGIS
pagination/cursors; the bulk family provides release manifests, resumable
transfer, hashes, and ZIP inspection/extraction. The local shapefile family
streams aligned SHP/SHX/DBF feature occurrences with native-CRS geometry,
attributes, conservative parcel joins, and artifact-bound cursors:

```bash
uv run python tools/public_records_shapefile.py inspect \
    "$WORKDIR/parcels.zip" --source-id us-example-parcels \
    --release-id 2026-final --parcel-field PARCELNO \
    --output "$WORKDIR/parcels-inspection.json"
uv run python tools/public_records_shapefile.py search \
    "$WORKDIR/parcels.zip" 00123 --source-id us-example-parcels \
    --release-id 2026-final --parcel-field PARCELNO \
    --field PARCELNO --match exact \
    --output "$WORKDIR/parcels-search.json"
```

`public_records_filegdb.py` supplies the corresponding source-neutral
interface for FileGDB artifacts. Container inventory and content identity do
not require GDAL. Layer inspection uses a caller-installed `ogrinfo` from GDAL
3.7+ with OpenFileGDB read support. Feature paging additionally verifies the
independently selected `ogr2ogr`, OpenFileGDB read, and GPKG write support.
Each operation reports its own availability while preserving the same
container receipt:

```bash
uv run python tools/public_records_filegdb.py backend \
    --output "$WORKDIR/filegdb-backend.json"
uv run python tools/public_records_filegdb.py container \
    "$WORKDIR/parcels.zip" \
    --output "$WORKDIR/filegdb-container.json"
uv run python tools/public_records_filegdb.py inspect \
    "$WORKDIR/parcels.zip" --source-id us-example-parcels \
    --release-id 2026-final --parcel-field PARCELNO \
    --output "$WORKDIR/filegdb-inspection.json"
uv run python tools/public_records_filegdb.py features \
    "$WORKDIR/parcels.zip" --source-id us-example-parcels \
    --release-id 2026-final --layer Parcels \
    --parcel-field PARCELNO --limit 100 \
    --output "$WORKDIR/filegdb-page.json"
```

There is no platform-wide
`maximum_records_per_run` compatibility setting; caller limits and endpoint
page-size mechanics remain explicit. Monitor `run` exits `0` only when every
requested probe records `ok` or an authoritative `no_results`, exits `1` for
an unhealthy or undispatched requested probe, and reserves `2` for command or
catalog errors.

`--run-live-public-records` enables the existing opt-in live gates for the
pytest paths selected in that invocation. Source-specific environment switches
remain available for running one adapter's established live checks directly.

### Nationwide source census and priority

```bash
uv run python tools/public_records_census.py seed
uv run python tools/public_records_priority.py recompute --by methodology-review
uv run python tools/public_records_census.py stats --json
uv run python tools/public_records_census.py list --compact \
    --source-presence none --candidate-presence some \
    --output "$WORKDIR/source-candidate-review.json"
uv run python tools/public_records_census.py claim --domain property --state FL \
    --source-presence none --candidate-presence none \
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
recomputation. CLI recompute results also include a non-blocking
`catalog_audit` summary, and the one-line output reports drift so a successful
scoring run is not mistaken for evidence that its selected catalog is current.
The compact list is the ranked triage view; it omits expanded association and
evidence detail while retaining the priority profile, run, input fingerprint,
and effective `as_of` provenance. Priority metrics report
`priority_provenance.status`; `current` means the stored ranking matches the
active investigation profile and its current demand inputs. A profile
mismatch, mixed profile set, or changed input fingerprint is visible before
the queue is used and can be refreshed with `recompute`.
`--source-presence` filters materialized source associations.
For direct read-only catalog audits, those associations live in
`source_census_target_sources` and join to `source_census_targets` and
`jurisdictions`.
After priority recomputation, `--candidate-presence` filters compatible
catalog candidates recorded in the target's priority basis. Combining
`--source-presence none --candidate-presence some` produces the
association/integration-review queue; combining `none` with
`--candidate-presence none` produces the source-discovery queue.
`--coverage-status` can narrow either queue. The catalog audit is read-only
and reports shared-router,
source-module declaration, manifest, live-catalog, review, and
census-association drift. Source-module findings include the adapter file and
cover literal component and complementary source IDs as well as the primary
source, so standalone implementations can be cataloged without first adding a
shared route.

Before ranking a newly discovered source for implementation, retain a compact
live contract packet: the official linker, exact tenant URL, one
target-bearing query, native record and child identifiers, pager mechanics,
detail sections, the source-published acquisition grain, and the closest
official field-matched fallback. Keep acquisition grain distinct from
technical pagination and caller windows: a source may expose broad discovery
while describing individual-record retrieval as the supported transaction.
Generated search plans read canonical executable capabilities such as
`search_owner`, `fetch_account`, and `list_releases` from the source manifest.
A source-specific capability and a shared router's `shared_operations` entry
can preserve useful detail about the same route. Automatic task materialization
also uses a canonical operation and a concrete adapter command or action
handoff. Until that mapping is added, keep the source-specific or shared
operation visible as an advisory, model-usable capability rather than hiding
it. Pairing the route with its canonical manifest capability and
`adapter_tool`/`adapter_command` mapping keeps the detailed source contract
while making it directly executable in generated plans.
Record the reusable transport family separately from tenant identity. A
second hostname for the same vendor dataset is a failover path, while
assessor, tax collector, recorder, case index, and document systems remain
separately attributable components. When one interface is unavailable,
evaluate those component-level alternatives instead of treating the entire
jurisdiction as unavailable. For versioned portals, compare the same
publisher-facing record across multiple periods before treating an internal
ID as durable. If that locator changes, retain it as version-specific
retrieval state and key the observation with the publisher's stable identifier
plus the applicable version, such as parcel number plus tax year. When a
repeated child table has no native child ID, derive one from the published
field tuple and use an ordinal only to distinguish identical tuples; keep the
absolute row position as ordering state so an unrelated insertion does not
churn every later child identity.

### Census ACS geographic context

```bash
uv run python tools/query_census_acs.py state \
    --profile population-age --output "$WORKDIR/acs-states.json"
uv run python tools/query_census_acs.py county --state 24 \
    --profile core --output "$WORKDIR/acs-md-counties.json"
uv run python tools/query_census_acs.py tract --state 24 --county 005 \
    --profile income-poverty --output "$WORKDIR/acs-baltimore-tracts.json"
uv run python tools/query_census_acs.py block-group --state 24 --county 005 \
    --profile housing --output "$WORKDIR/acs-baltimore-block-groups.json"
uv run python tools/query_census_acs.py place --state 24 \
    --profile race-ethnicity --output "$WORKDIR/acs-md-places.json"
uv run python tools/query_census_acs.py zcta --zcta 21201 \
    --profile core --output "$WORKDIR/acs-zcta-21201.json"
uv run python tools/query_census_acs.py variables B25077 \
    --contains "Median value" --output "$WORKDIR/acs-variables.json"
uv run python tools/query_census_acs.py routes \
    --output "$WORKDIR/acs-routes.json"
uv run python tools/query_census_acs.py probe \
    --output "$WORKDIR/acs-probe.json"
```

The adapter preserves ACS vintage, full GEOID and FIPS joins, estimates,
published margins of error, annotations, backend attribution, and
release/schema/data-bound cursors. `--profile` selects a curated metric group;
`--variables` adds Detailed Table estimate variables. A configured
`CENSUS_API_KEY` selects the official data endpoint, while the keyless Census
Reporter backend represents the same Census release and is recorded as
redundancy rather than independent corroboration. `routes` also exposes the
official table-based summary files, Census Geocoder, and TIGERweb complements.
Canonical observation references use
`USCENSUS:ACS5:<vintage>:<full_geoid>`.

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
uv run python tools/query_property.py owner "GRACE CHURCH" \
    --source us-tx-bexar-bcad-property --jurisdiction 48029 \
    --output "$WORKDIR/property-bexar.json"
uv run python tools/query_property.py parcel 612115 \
    --source us-tx-bexar-bcad-property --geometry --ingest \
    --output "$WORKDIR/property-bexar-parcel.json"
uv run python tools/query_property.py owner "MIAMI-DADE COUNTY" \
    --source us-fl-miami-dade-property-appraiser --jurisdiction 12086 \
    --output "$WORKDIR/property-miami.json"
uv run python tools/query_property.py parcel 0101000000020 \
    --source us-fl-miami-dade-property-appraiser --geometry --ingest \
    --output "$WORKDIR/property-miami-parcel.json"
uv run python tools/query_property.py map 0017103008000 \
    --source us-co-denver-parcels --jurisdiction 08031 --ingest \
    --output "$WORKDIR/property-denver-map.json"
uv run python tools/query_property.py parcel 1001300033 \
    --source us-de-firstmap-parcels --jurisdiction 10003 --ingest \
    --output "$WORKDIR/property-delaware-firstmap.json"
uv run python tools/query_property.py parcel 03-001-009 \
    --source us-va-arlington-property-map --jurisdiction 51013 --ingest \
    --output "$WORKDIR/property-arlington.json"
uv run python tools/query_property.py parcel 2004-001-003 \
    --source us-ca-los-angeles-county-assessor-parcels \
    --jurisdiction 06037 --ingest \
    --output "$WORKDIR/property-la-assessor.json"
uv run python tools/query_property.py account 2004001003 \
    --source us-ca-los-angeles-county-ttc-payment-history \
    --jurisdiction 06037 --ingest \
    --output "$WORKDIR/property-la-payments.json"
uv run python tools/query_property.py event all \
    --source us-ca-los-angeles-county-ttc-tax-sale \
    --jurisdiction 06037 \
    --output "$WORKDIR/property-la-auctions.json"
uv run python tools/query_property.py search 2025B \
    --source us-ca-los-angeles-county-ttc-tax-sale \
    --process-stage sale-results --jurisdiction 06037 \
    --output "$WORKDIR/property-la-publications.json"
uv run python tools/query_property.py sale 2025B \
    --source us-ca-los-angeles-county-ttc-tax-sale \
    --jurisdiction 06037 --ingest \
    --output "$WORKDIR/property-la-sale-results.json"
uv run python tools/query_property.py owner "PENA ROSADO" \
    --source us-pa-philadelphia-opa-properties \
    --jurisdiction 42101 --output "$WORKDIR/property-phila-owner.json"
uv run python tools/query_property.py parcel 341086700 \
    --source us-pa-philadelphia-opa-assessment-history \
    --tax-year 2023 --jurisdiction 42101 --ingest \
    --output "$WORKDIR/property-phila-history.json"
uv run python tools/query_property.py instrument 062N200131 \
    --source us-pa-philadelphia-dor-parcels \
    --jurisdiction 42101 --ingest \
    --output "$WORKDIR/property-phila-dor-parcel.json"
uv run python tools/query_property.py account 135278 \
    --source us-or-deschutes-dial-property --jurisdiction 41017 \
    --output "$WORKDIR/property-deschutes-dial-account.json"
uv run python tools/query_property.py subdivision "SISTERS" \
    --source us-or-deschutes-dial-property --jurisdiction 41017 \
    --output "$WORKDIR/property-deschutes-subdivision.json"
uv run python tools/query_property.py owner "SMITH" \
    --source us-or-morrow-helion-property --jurisdiction 41049 \
    --output "$WORKDIR/property-morrow-owner.json"
uv run python tools/query_property.py account 171 \
    --source us-or-morrow-helion-property --jurisdiction 41049 --ingest \
    --output "$WORKDIR/property-morrow-account.json"
uv run python tools/query_property.py parcel 2038010000001 \
    --source us-wa-current-parcels-ecology --jurisdiction 53001 \
    --geometry --ingest --output "$WORKDIR/property-wa-parcel.json"
uv run python tools/query_property.py count King \
    --source us-wa-current-parcels-dnr --search-field county \
    --output "$WORKDIR/property-wa-king-count.json"
uv run python tools/query_property.py freshness "San Juan" \
    --source us-wa-current-parcels-county-freshness \
    --output "$WORKDIR/property-wa-freshness.json"
uv run python tools/query_property.py land-use R \
    --source us-wa-current-parcels-county-land-use --county-fips 001 \
    --output "$WORKDIR/property-wa-land-use.json"
uv run python tools/query_property.py parity wisaard \
    --source us-wa-state-parcels-normalized \
    --output "$WORKDIR/property-wa-parity.json"
uv run python tools/query_property.py account "PAR 01300036" \
    --source us-dc-itspe-public-extract --jurisdiction 11 --ingest \
    --output "$WORKDIR/property-dc-account.json"
uv run python tools/query_property.py map "PAR 01300036" \
    --source us-dc-common-ownership-polygons --jurisdiction 11 \
    --geometry --ingest --output "$WORKDIR/property-dc-map.json"
uv run python tools/query_property.py sale "PAR 01300036" \
    --source us-dc-cama-property-sales --jurisdiction 11 --ingest \
    --output "$WORKDIR/property-dc-sales.json"
uv run python tools/query_property.py survey \
    9B59CB35-62CB-C473-B297-59097C200000 \
    --source us-dc-surveyor-document-system --jurisdiction 11 --ingest \
    --output "$WORKDIR/property-dc-survey.json"

uv run python tools/query_state_courts.py sources --jurisdiction 36 \
    --output "$WORKDIR/court-sources.json"
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
    --output "$WORKDIR/court-local.json"
uv run python tools/query_state_courts.py search "EXAMPLE LLC" --source us-ny-nyscef \
    --jurisdiction 36 --output "$WORKDIR/nyscef-human-action.json"
uv run python tools/query_state_courts.py search "EXAMPLE LLC" --source us-fl-acis \
    --jurisdiction 12 --output "$WORKDIR/florida-acis-search.json"
uv run python tools/query_state_courts.py calendar 3A \
    --source us-co-denver-county-court-public-docket \
    --jurisdiction 08031 --hearing-date 2026-07-29 --ingest \
    --output "$WORKDIR/denver-county-calendar.json"
uv run python tools/query_state_courts.py search "24-BG-1045" \
    --source us-dc-court-of-appeals-opinions-mojs --jurisdiction 11 \
    --case-type opinions --ingest \
    --output "$WORKDIR/dc-opinions-unified.json"

uv run python tools/public_records_search_plan.py "Example Holdings LLC" \
    --alias "Example Holdings" --address "100 Main St, Albany, NY" \
    --jurisdiction 36 --output "$WORKDIR/public-record-search-plan.json"
```

Los Angeles County keeps Assessor routing, TTC payment history, TTC
auction/result publications, and Recorder instruments separately attributable
and joins the first three by exact ten-digit AIN. Source-native operations are:

```bash
uv run python tools/query_los_angeles_ttc.py sources \
    --output "$WORKDIR/la-ttc-sources.json"
uv run python tools/query_los_angeles_ttc.py route 2004-001-003 \
    --output "$WORKDIR/la-ttc-route.json"
uv run python tools/query_los_angeles_ttc.py history 2004001003 \
    --output "$WORKDIR/la-ttc-history.json"
uv run python tools/query_los_angeles_ttc.py auctions \
    --output "$WORKDIR/la-ttc-auctions.json"
uv run python tools/query_los_angeles_ttc.py publications --cycle 2025B \
    --output "$WORKDIR/la-ttc-publications.json"
uv run python tools/query_los_angeles_ttc.py sale-results 2025B \
    --output "$WORKDIR/la-ttc-sale-results.json"
uv run python tools/query_los_angeles_ttc.py probe \
    --output "$WORKDIR/la-ttc-probe.json"
```

Philadelphia preserves OPA current property rows, OPA annual history, and
Department of Records parcel maps as three source components. The current
ArcGIS layer, nightly current CSV, CARTO current mirror, and interactive
property application share the OPA record identity and are transport
alternatives rather than additional corroborating sources.

```bash
uv run python tools/query_philadelphia_property.py owner "PENA ROSADO" \
    --output "$WORKDIR/phila-opa-owner.json"
uv run python tools/query_philadelphia_property.py parcel 341086700 \
    --geometry --output "$WORKDIR/phila-opa-parcel.json"
uv run python tools/query_philadelphia_property.py history 341086700 \
    --from-year 2020 --to-year 2026 \
    --output "$WORKDIR/phila-opa-history.json"
uv run python tools/query_philadelphia_property.py parcel-shape 062N200131 \
    --by registry --output "$WORKDIR/phila-dor-polygon.json"
uv run python tools/query_philadelphia_property.py alternatives \
    --output "$WORKDIR/phila-official-alternatives.json"
uv run python tools/public_records_monitor.py run \
    us-pa-philadelphia-opa-properties \
    us-pa-philadelphia-opa-assessment-history \
    us-pa-philadelphia-dor-parcels \
    --output "$WORKDIR/phila-property-monitor.json"
```

Michigan's DTMB directory exposes one current route for each of 83 counties.
It is a discovery source rather than a statewide parcel service: the
publisher's parcel-layer description, the destination URL/platform signals,
and destination-verified assessment, tax, transfer, bulk, or land-record
capabilities remain separate.

```bash
uv run python tools/query_michigan_property_directories.py list \
    --county Oakland --output "$WORKDIR/mi-oakland-route.json"
uv run python tools/query_michigan_property_directories.py platforms \
    --output "$WORKDIR/mi-platforms.json"
uv run python tools/query_michigan_property_directories.py discovery \
    --platform bsa_online --output "$WORKDIR/mi-bsa-routes.json"
uv run python tools/query_michigan_property_directories.py alternatives \
    --output "$WORKDIR/mi-property-complements.json"
uv run python tools/query_property.py discovery \
    --source us-mi-dtmb-tax-parcel-directory --jurisdiction 26125 \
    --search-field county --output "$WORKDIR/mi-shared-route.json"
```

Local assessors, county Registers of Deeds, LARA subdivision plats, the state
plat ImageServer, DNR's state-land service, Treasury's tax estimator, and the
foreclosing-unit directory are cataloged as field- or scope-specific
complements.

Wisconsin's annual statewide service, Virginia's item-resolved parcel
geometry, New York's parcel and transfer components, and New Jersey's
item-resolved parcel/MOD-IV composite are also live through the unified router:

```bash
uv run python tools/query_wisconsin_parcels.py coverage \
    --output "$WORKDIR/wi-parcel-coverage.json"
uv run python tools/query_property.py owner "EXAMPLE OWNER" \
    --source us-wi-statewide-parcels --jurisdiction 55001 --ingest \
    --output "$WORKDIR/wi-owner.json"
uv run python tools/query_wisconsin_parcels.py alternatives \
    --output "$WORKDIR/wi-property-alternatives.json"

uv run python tools/query_virginia_parcels.py metadata \
    --output "$WORKDIR/va-vgin-metadata.json"
uv run python tools/query_virginia_parcels.py parcel 5108700000001 \
    --field vgin-qpid --fips 51087 --geometry \
    --output "$WORKDIR/va-vgin-parcel.json"
uv run python tools/query_virginia_parcels.py localities \
    --output "$WORKDIR/va-vgin-localities.json"
uv run python tools/query_virginia_parcels.py alternatives \
    --output "$WORKDIR/va-vgin-alternatives.json"
uv run python tools/query_property.py parcel 5108700000001 \
    --source us-va-vgin-parcels --jurisdiction 51087 \
    --search-field vgin-qpid --geometry --ingest \
    --output "$WORKDIR/va-vgin-unified.json"

uv run python tools/query_va_beach_delinquent_tax.py owner "EXAMPLE LLC" \
    --output "$WORKDIR/va-beach-tax-owner.json"
uv run python tools/query_va_beach_delinquent_tax.py parcel 14469645070000 \
    --output "$WORKDIR/va-beach-tax-gpin.json"
uv run python tools/query_va_beach_delinquent_tax.py bill 1125000027 \
    --output "$WORKDIR/va-beach-tax-bill.json"
uv run python tools/query_va_beach_delinquent_tax.py search \
    --tax-year 2025 --installment 2 --min-total-due 1000 \
    --output "$WORKDIR/va-beach-tax-filtered.json"
uv run python tools/query_va_beach_delinquent_tax.py probe \
    --output "$WORKDIR/va-beach-tax-probe.json"
uv run python tools/query_va_beach_delinquent_tax.py routes \
    --output "$WORKDIR/va-beach-tax-routes.json"
uv run python tools/query_property.py event 1125000027 \
    --source us-va-virginia-beach-delinquent-real-estate-taxes \
    --jurisdiction 51810 --ingest \
    --output "$WORKDIR/va-beach-tax-shared.json"
uv run python tools/public_records_monitor.py run \
    us-va-virginia-beach-delinquent-real-estate-taxes \
    --output "$WORKDIR/va-beach-tax-monitor.json"

uv run python tools/query_ny_statewide_parcels.py coverage \
    --output "$WORKDIR/ny-parcel-coverage.json"
uv run python tools/query_property.py owner "EXAMPLE OWNER" \
    --source us-ny-statewide-parcels --jurisdiction 36001 --ingest \
    --output "$WORKDIR/ny-owner.json"
uv run python tools/query_ny_statewide_parcels.py point -73.7562 42.6526 \
    --geometry --output "$WORKDIR/ny-parcel-boundary.json"
uv run python tools/query_ny_salesweb.py search \
    --seller "EXAMPLE LLC" --county Albany --all \
    --output "$WORKDIR/ny-sales.json"
uv run python tools/query_property.py instrument 2025/19127 \
    --source us-ny-orpts-sales-web --jurisdiction 36001 --ingest \
    --output "$WORKDIR/ny-sale-by-book-page.json"
uv run python tools/public_records_monitor.py run \
    us-ny-statewide-parcels us-ny-orpts-sales-web \
    --output "$WORKDIR/ny-property-monitor.json"

uv run python tools/query_property.py parcel 0703_14_5 \
    --source us-nj-njgin-parcels-modiv --jurisdiction 34013 \
    --geometry --ingest --output "$WORKDIR/nj-parcel.json"
uv run python tools/query_new_jersey_parcels.py search \
    --county Essex --has-modiv no \
    --output "$WORKDIR/nj-unmatched-parcels.json"
uv run python tools/query_new_jersey_sr1a.py manifest \
    --output "$WORKDIR/nj-sr1a-manifest.json"
uv run python tools/query_new_jersey_sr1a.py search "EXAMPLE LLC" \
    --field party --county Essex \
    --output "$WORKDIR/nj-sr1a-sales.json"
uv run python tools/query_new_jersey_tax_court.py manifest \
    --dataset both --format all \
    --output "$WORKDIR/nj-tax-court-artifacts.json"
uv run python tools/query_new_jersey_tax_court.py search "EXAMPLE LLC" \
    --field case-title --dataset both \
    --output "$WORKDIR/nj-tax-court-cases.json"
uv run python tools/query_new_jersey_tax_court.py search \
    --docket 003855-2026 \
    --output "$WORKDIR/nj-tax-court-docket.json"
uv run python tools/query_new_jersey_tax_court.py alternatives \
    --output "$WORKDIR/nj-tax-court-alternatives.json"
uv run python tools/query_new_jersey_tax_court_opinions.py search "Freehold" \
    --collection both --all-pages \
    --output "$WORKDIR/nj-tax-opinions.json"
uv run python tools/query_new_jersey_tax_court_opinions.py search \
    --docket 000052-2025 --collection published \
    --output "$WORKDIR/nj-tax-opinion-docket.json"
uv run python tools/query_new_jersey_tax_court_opinions.py document \
    https://www.njcourts.gov/system/files/court-opinions/2026/000052-2025.pdf \
    --metadata-only --output "$WORKDIR/nj-tax-opinion-document.json"
uv run python tools/query_new_jersey_tax_court_opinions.py probe \
    --output "$WORKDIR/nj-tax-opinion-probe.json"
uv run python tools/query_new_jersey_tax_court_opinions.py alternatives \
    --output "$WORKDIR/nj-tax-opinion-alternatives.json"
uv run python tools/query_new_jersey_dca_property.py registration \
    0714002653 --output "$WORKDIR/nj-dca-registration.json"
uv run python tools/query_new_jersey_dca_property.py parcel \
    --county Essex --block 441 --lot 61 \
    --output "$WORKDIR/nj-dca-block-lot.json"
uv run python tools/query_new_jersey_dca_property.py alternatives \
    --output "$WORKDIR/nj-dca-alternatives.json"
uv run python tools/query_property.py account 0714002653 \
    --source us-nj-dca-property-registration --jurisdiction 34 \
    --ingest --output "$WORKDIR/nj-dca-unified.json"
uv run python tools/query_property.py owner "EXAMPLE LLC" \
    --source us-nj-treasury-sr1a-sales --jurisdiction 34013 \
    --tax-year 2025 --ingest --output "$WORKDIR/nj-sr1a-unified.json"
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
    --source us-nj-tax-court-property-cases --jurisdiction 34 \
    --search-field case-title --ingest \
    --output "$WORKDIR/nj-tax-court-unified.json"
uv run python tools/public_records_monitor.py run \
    us-wi-statewide-parcels us-va-vgin-parcels \
    us-nj-njgin-parcels-modiv \
    us-nj-treasury-sr1a-sales us-nj-tax-court-property-cases \
    us-nj-tax-court-opinions us-nj-dca-property-registration \
    --output "$WORKDIR/statewide-parcel-monitor.json"
```

Wisconsin's `STATEID` is the projected statewide parcel identity; local
`PARCELID` and `TAXPARCELID` remain aliases, owner-withheld states remain
explicit, and known map-only labels remain observations. Bulk releases and
the interactive map share the statewide record lineage, while county systems
and DOR transfer returns add different records.

Ohio OGRIP uses `StateParcelID` as the statewide parcel identity and county
plus `LocalParcelID` as the local join. The shared router exposes `address`,
`count`, `discovery`, `freshness`, `land-use`, `map`, `parcel`, `probe`, and
`search`; Franklin, Licking, and Delaware assessor and recorder routes remain
separate catalog tasks.

```bash
uv run python tools/query_ohio_statewide_parcels.py parcel \
    39049-010-042534 --geometry \
    --output "$WORKDIR/ohio-parcel.json"
uv run python tools/query_property.py discovery \
    --source us-oh-ogrip-statewide-parcels \
    --output "$WORKDIR/ohio-property-routes.json"
uv run python tools/query_ohio_pax_recorders.py search \
    --source us-oh-delaware-county-recorder-pax \
    --name "EXAMPLE LLC" \
    --output "$WORKDIR/delaware-recorder.json"
uv run python tools/query_property.py instrument 201310100025382 \
    --source us-oh-licking-county-recorder-instrument-detail \
    --jurisdiction 39089 --ingest \
    --output "$WORKDIR/licking-instrument.json"
uv run python tools/query_property.py download 201310100025382 \
    --source us-oh-licking-county-recorder-instrument-detail \
    --jurisdiction 39089 \
    --destination "$WORKDIR/licking-instrument.pdf" --ingest \
    --output "$WORKDIR/licking-document.json"
uv run python tools/public_records_monitor.py run \
    us-oh-delaware-county-recorder-pax \
    us-oh-licking-county-recorder-pax \
    us-oh-licking-county-recorder-instrument-detail \
    --output "$WORKDIR/ohio-recorder-monitor.json"
uv run python tools/query_ohio_sheriff_sales.py auctions licking \
    --date 2026-07-30 --case-number 25CV01926 \
    --output "$WORKDIR/licking-sheriff-sale.json"
uv run python tools/query_licking_foreclosure_archive.py year \
    --year 2026 --case-number 25CV01926 \
    --output "$WORKDIR/licking-foreclosure-archive.json"
uv run python tools/query_property.py search 25CV01926 \
    --source us-oh-licking-sheriff-realauction \
    --jurisdiction 39089 --search-field case \
    --from-date 2026-07-30 --to-date 2026-07-30 --ingest \
    --output "$WORKDIR/licking-sheriff-shared.json"
uv run python tools/query_property.py search 25CV01926 \
    --source us-oh-licking-sheriff-foreclosure-archive \
    --jurisdiction 39089 --search-field case --tax-year 2026 --ingest \
    --output "$WORKDIR/licking-archive-shared.json"
uv run python tools/public_records_monitor.py run \
    us-oh-franklin-sheriff-realauction \
    us-oh-delaware-sheriff-realauction \
    us-oh-licking-sheriff-realauction \
    us-oh-licking-sheriff-foreclosure-archive \
    --output "$WORKDIR/ohio-sheriff-monitor.json"
uv run python tools/public_records_search_plan.py "INN INVESTMENT CORP." \
    --jurisdiction 39049 --jurisdiction 39089 --jurisdiction 39041 \
    --output "$WORKDIR/ohio-search-plan.json"
```

For Delaware, omitting `--limit` exhausts native PAX pages; an explicit limit
returns a query-bound cursor. `InstrumentReferenceId` is the stable recorder
row identity. Licking PAX discovery currently requires an account, while
`us-oh-licking-county-recorder-instrument-detail` supports anonymous detail
and PDF retrieval for a known instrument number. The exact route is stored as
a representation source, but ingestion keys the instrument under
`us-oh-licking-county-recorder-pax` so both access paths deduplicate without
being treated as independent corroboration. Recorder parties remain instrument
parties rather than current-owner assertions.

### Licking County Auditor GIS

The structured Licking Auditor layer supports complete ordered parcel,
owner, address, value, attribute, occurrence, metadata, and probe operations.
`GlobalID` is the feature-occurrence identity; `OBJECTID` is its locator and
fallback, while `Parcel` is the county business join. See [the detailed source
contract](sources/ohio-licking-auditor-gis.md).

```bash
uv run python tools/query_ohio_licking_property.py parcel \
  001-000006-01.000 --geometry \
  --output "$WORKDIR/licking-auditor-parcel.json"
uv run python tools/query_ohio_licking_property.py owner "SMITH" \
  --output "$WORKDIR/licking-auditor-owner.json"
uv run python tools/query_ohio_licking_property.py probe \
  --output "$WORKDIR/licking-auditor-probe.json"
```

### Franklin County Auditor bulk releases

The Franklin bulk adapter discovers the `appraisal`, `tax-accounting`,
`daily-conveyances`, `gis-shapefiles`, and `parcel-csv` release families. It
lists and boundedly probes artifacts, downloads them through the resumable
bulk path, inspects local ZIP/XLSX/CSV structure, and streams component rows.
Shared local-row routing accepts `--artifact-path`, `--artifact-source-url`,
the row family in `--dataset-type`, and release identity in
`--collection-id`. See [the detailed source
contract](sources/ohio-franklin-auditor-bulk.md).

```bash
uv run python tools/query_ohio_franklin_auditor_bulk.py releases parcel-csv \
  --year 1997 --output "$WORKDIR/franklin-parcel-releases.json"
uv run python tools/query_ohio_franklin_auditor_bulk.py artifacts appraisal \
  --release current --output "$WORKDIR/franklin-appraisal-artifacts.json"
uv run python tools/query_ohio_franklin_auditor_bulk.py download \
  tax-accounting Payment2025.xlsx --release current \
  --destination "$WORKDIR/Payment2025.xlsx" \
  --output "$WORKDIR/franklin-payment-download.json"
uv run python tools/query_property.py search "010-000001-00" \
  --source us-oh-franklin-county-auditor-bulk --jurisdiction 39049 \
  --artifact-path "$WORKDIR/Payment2025.xlsx" --dataset-type payment \
  --collection-id tax-accounting-2026-07-15 \
  --artifact-source-url https://apps.franklincountyauditor.com/Outside_User_Files/2026/2026-07-15%20Tax%20Accounting/Payment2025.xlsx \
  --ingest --output "$WORKDIR/franklin-payment-rows.json"
uv run python tools/public_records_monitor.py run \
  us-oh-franklin-county-auditor-bulk \
  --output "$WORKDIR/franklin-auditor-monitor.json"
```

Row identity includes release, artifact SHA-256, archive member and worksheet
when applicable, and physical row. Dated positive-price appraisal Sales rows
retain native `VALID` in `qualification_code`; daily conveyances require the
native `NON-EXEMPT` state. These qualification fields remain distinct from
the existence of the reported transaction. Normalized sale identity is
separate: appraisal rows use parcel plus `INSTRUNO`, daily rows use parcel plus
`CONVEYNUMBER`, and missing business numbers use a deterministic parcel/date/
instrument/amount/party semantic fallback. Repeated release rows remain
individually observable while the newest source release controls one
cross-roll normalized event, regardless of archive retrieval order. Franklin
bulk facts stay on Franklin-owned annual or event-anchor parcel shells; OGRIP
remains a separate same-lineage parcel representation regardless of load
order.

### Franklin County Auditor Sales GIS

The Auditor's canonical `Sales Details` layer exposes recent sale
occurrences, exact parcel and conveyance selectors, four-field grantor/grantee
search, inclusive date ranges, raw validity values, address and structure
context, and optional point geometry. `GlobalID` identifies a feature
occurrence; `ConveyanceNum` plus `PARCELID` identifies the normalized business
event. See the [detailed source
contract](sources/ohio-franklin-auditor-sales-gis.md).

```bash
uv run python tools/query_ohio_franklin_sales_gis.py parcel 010-000006 \
  --geometry --output "$WORKDIR/franklin-sales-parcel.json"
uv run python tools/query_ohio_franklin_sales_gis.py party \
  "LAMAR EQUITY INVESTMENTS LLC" \
  --output "$WORKDIR/franklin-sales-party.json"
uv run python tools/query_ohio_franklin_sales_gis.py date-range \
  --start 2024-01-01 --end 2024-12-31 \
  --output "$WORKDIR/franklin-sales-2024.json"
uv run python tools/query_property.py instrument 00004012 \
  --source us-oh-franklin-county-auditor-sales-gis \
  --jurisdiction 39049 --ingest \
  --output "$WORKDIR/franklin-sales-conveyance.json"
uv run python tools/public_records_monitor.py run \
  us-oh-franklin-county-auditor-sales-gis \
  --output "$WORKDIR/franklin-sales-monitor.json"
```

Omitting `--limit` exhausts matching `OBJECTID` pages; explicit limits return
query-bound cursors. Dated positive-price rows project as assessor sale
observations while retaining the source's `ValidSale` qualification. Grantor
and grantee values remain transaction parties, and the Auditor bulk,
interactive property, Sales GIS, and county-origin OGRIP representations share
an evidence lineage rather than supplying independent corroboration.

The three RealAuction source components share one adapter family but preserve
county-tenant identity. A sheriff-sale event is keyed by tenant plus AID, and
omitting `--limit` traverses the complete selected native page set. The
Licking archive is a distinct source keyed by its published case number; a
selected year returns the complete source-reported array at retrieval, while
the current maximum year remains mutable.

Shared ingestion stores both as neutral `property_event` observations. It
does not create a sale/conveyance, ownership, title-transfer, or recorded
instrument assertion from a scheduled or source-reported auction outcome.
Licking records with the same exact normalized case, event date, and at least
one exact normalized parcel overlap receive `same_event_candidate` edges.
Every exact candidate is retained in one-to-many cases, those cases remain
marked ambiguous, and the edge is not independent corroboration. Published
parcel join keys remain searchable even when multiple parcels prevent a
single OGRIP parcel attachment.

Virginia's official ArcGIS item is the stable VGIN source identity; the
adapter resolves its current FeatureServer at runtime. `VGIN_QPID` is the
durable parcel key, `OBJECTID` is a transport locator, and `FIPS + PARCELID`
or `FIPS + PTM_ID` carry candidate joins into local assessment and tax
systems. Locality coverage and `LASTUPDATE` values remain observations rather
than synthetic parcel rows. Bulk VGIN downloads share the same record lineage;
local assessors, Treasurers, Commissioners of the Revenue, GIS offices, and
Circuit Court land records add distinct administrative and title evidence.

Virginia Beach source
`us-va-virginia-beach-delinquent-real-estate-taxes` is a locality-specific
tax-collection complement to VGIN. One occurrence is identified by bill
number, installment, GPIN, and tax year; GPIN is the parcel join and
`OBJECTID` remains a transport locator. The adapter retains tax, penalty,
interest, fee, and total balances as exact cents. Its daily source snapshot is
not treated as the delinquency-onset date. `routes` keeps the Manatron account
inquiry, assessor, Circuit Court land records, Circuit and General District
case indexes, and Treasurer tax-sale publications as separate record roles.

New York's centroid, public-polygon, and state-owned-polygon components retain
separate provenance but share the published `SWIS_SBL_ID`,
`SWIS_PRINT_KEY_ID`, and `MUNI_PARCEL_ID` joins. The centroid component
supplies the all-county annual assessment/owner snapshot; polygon components
add geometry for their stated footprints. SalesWeb keeps `saleTranNmbr` as
the transfer identity and links to the parcel by exact `SWIS_PRINT_KEY_ID`.
Buyer and seller project as transaction parties, not a current-ownership
assertion. ACRIS, Richmond County Clerk, other county clerks, OGS, and local
assessment routes supply complementary NYC, older-transfer, instrument-image,
state-land, and local-detail coverage.

NJGIN preserves parcel-only rows when the MOD-IV join is absent and does not
invent owners from its redacted hosted field. The complete MOD-IV table,
annual Treasury files, SR1A sale rows, local assessor/tax-board records,
county recorded instruments, Tax Court cases, DCA registrations, and OPRA
custodian routes remain separately selectable complements. SR1A cursors bind
to selected release artifacts; stable sale identity is separate from each
release/row occurrence. The parser retains raw fixed-width values with their
field-specific date and amount normalization provenance, and ingestion keeps
grantor/grantee transaction parties distinct from ownership assertions.

The DCA adapter treats the 13-digit building registration as the source-row
identity and its first 10 digits as the related property registration.
Registered-owner data is regulatory registration context, so ingestion creates
a regulatory event and party rather than a deed-title assertion. The DCA
record's county, municipality, block, and lot remain an unresolved parcel
candidate until an exact MOD-IV municipality-code crosswalk is available. The
same-agency BHI Active Building report adds fields for its active,
non-redacted reporting footprint; NJGIN, SR1A, county instruments, local
assessment records, and OPRA routes retain their separate record roles.

The Tax Court adapter discovers the current docketed/open XLSX and PDF report
pairs from the Judiciary's anonymous object manifest. Search traverses the
selected workbooks completely unless limited, and a continuation binds both
the query and artifact set. Docket number is the case identity; artifact hash,
worksheet, row number, and row hash identify each report occurrence. Exact
duplicates and multiple property rows therefore survive ingestion. The
current reports publish county/block/lot/unit/year but not municipality, so
they do not alone provide a deterministic NJGIN or SR1A parcel join.
Historical judgments, retained current-key versions, GovConnect notices, case
jackets, opinions, appeal statistics, and county-board routes remain
separately attributable alternatives.

The Tax Court opinion adapter traverses the separate published and unpublished
20-row indexes and keeps index occurrence, official document, and normalized
case-docket identities distinct. New Jersey Courts is always the publisher;
when direct access is edge-challenged, a result labels Jina Reader as the
rendering or text-extraction transport. Reader text is not original PDF bytes
and its hash has a different scope, but both transports point to the same
official document. The July 30, 2026 counts of 104 published and 374
unpublished occurrences are rolling monitor observations. New Jersey Courts
site search, Tax Case Public Access, docket/judgment reports, Tax Court
Reports/State Library, local property sources, Rutgers, and CourtListener keep
their separate route and same-lineage relationships.

Omitted limits traverse the full count-checked result set; explicit limits
return source-snapshot-bound cursors. Unified ingestion joins annual history
and DOR geometry to the stable OPA parcel through exact parcel, registry, and
PIN values while retaining the raw source observation for every component.
Philadox, the Department of Records copy/City Archives service, and Atlas are
cataloged as distinct instrument and cross-department follow-up routes.

Payment history follows every source-reported page when `--max-pages` is
omitted. Sale-result extraction follows the complete selected PDF when
`--limit` is omitted; a caller-selected limit returns a resumable cursor. The
source manifest and unified query guidance also retain the official
annual-bill, duplicate-bill, multi-parcel request, individual
tax-default/redemption, and excess-proceeds routes.

Search-plan output includes `complementary_routes`: catalog-declared source
groups with each route's added roles and capabilities, access mode,
coverage start/cadence, jurisdiction match, and record-identity relationship.
Use those groups when a primary portal is incomplete or difficult instead of
treating it as the only path to the underlying information.

Normalized data live in `datasets/property_records.db` and
`datasets/state_court_records.db`. Cite retained records with
`PROPERTY:<source>/<jurisdiction>/<kind>/<native-id>` or
`STATECOURT:<source>/<court>/<case>/<kind>[/<native-id>]`. See
`docs/modules/property.md` and `docs/modules/legal.md`.

### Florida ACIS appellate-court adapter

`query_florida_acis.py` queries the anonymous backend used by the official
Florida Appellate Case Information System. Coverage is the Supreme Court of
Florida and the six District Courts of Appeal; county trial-court systems are
separate sources.

```bash
# Seven-court directory and stable court resource UUIDs
uv run python tools/query_florida_acis.py courts \
    --output "$WORKDIR/acis-courts.json"

# Party, case, document-text, and publication indexes
uv run python tools/query_florida_acis.py party-search "EXAMPLE LLC" \
    --output "$WORKDIR/acis-parties.json"
uv run python tools/query_florida_acis.py case-search "2024-0442" \
    --output "$WORKDIR/acis-cases.json"
uv run python tools/query_florida_acis.py document-search "motion" \
    --output "$WORKDIR/acis-documents.json"
uv run python tools/query_florida_acis.py publications "rules" \
    --output "$WORKDIR/acis-publications.json"

# Calendar-session taxonomy and appellate events with attached case hearings
uv run python tools/query_florida_acis.py calendar-types \
    --output "$WORKDIR/acis-calendar-types.json"
uv run python tools/query_florida_acis.py calendar \
    --court "2nd District Court of Appeal" \
    --after 2026-08-19 --before 2026-08-19 \
    --session-type "Oral Argument" \
    --output "$WORKDIR/acis-calendar.json"
uv run python tools/query_state_courts.py calendar "*" \
    --source us-fl-acis --court-id "2nd District Court of Appeal" \
    --hearing-date 2026-08-19 --case-type "Oral Argument" \
    --output "$WORKDIR/acis-calendar-shared.json"

# Case detail, parties, docket entries, and available public documents
uv run python tools/query_florida_acis.py case SC2024-0442 \
    --court 68f021c4-6a44-4735-9a76-5360b2e8af13 --documents \
    --output "$WORKDIR/acis-case.json"
uv run python tools/query_florida_acis.py docket SC2024-0442 \
    --court 68f021c4-6a44-4735-9a76-5360b2e8af13 \
    --output "$WORKDIR/acis-docket.json"
uv run python tools/query_florida_acis.py documents SC2024-0442 \
    --court 68f021c4-6a44-4735-9a76-5360b2e8af13 \
    --output "$WORKDIR/acis-case-documents.json"

# Retrieve a selected public document or publication with UUIDs from results
uv run python tools/query_florida_acis.py download \
    "<COURT_RESOURCE_UUID>" "<CASE_INSTANCE_UUID>" "<DOCUMENT_LINK_UUID>" \
    "$WORKDIR/acis-document.pdf" \
    --output "$WORKDIR/acis-document.json"
uv run python tools/query_florida_acis.py publication \
    "<COURT_RESOURCE_UUID>" "<PUBLICATION_UUID>" \
    --output "$WORKDIR/acis-publication.json"

# Monitor the seven-court identity and a bounded calendar/hearing contract
uv run python tools/public_records_monitor.py run us-fl-acis \
    --output "$WORKDIR/acis-monitor.json"
```

Results retain source UUIDs for courts, cases, parties, docket entries,
calendar events, documents, and publications. Calendar-event UUIDs identify
events; an attached hearing occurrence is keyed by event UUID, case-instance
UUID, and source order. The default calendar command hydrates those case
hearings, and `--events-only` skips the per-event detail calls. Public-document
availability and source access state can differ by record. The integration
does not claim that records predating migration into ACIS are complete.

### Florida court-directory and aggregate-data adapter

`query_florida_court_directory_data.py` exposes four independent official
source identities: the statewide court-location directory, Virtual Courtroom
Directory, OSCA public-records request route, and Trial Courts Statistical
Reference Guide.

```bash
# Source-family inventory and relationship map
uv run python tools/query_florida_court_directory_data.py sources \
    --output "$WORKDIR/fl-court-data-sources.json"
uv run python tools/query_florida_court_directory_data.py manifest \
    --output "$WORKDIR/fl-court-data-manifest.json"

# Court/clerk routing and current virtual courtrooms
uv run python tools/query_florida_court_directory_data.py locations \
    --query Miami --output "$WORKDIR/fl-court-locations.json"
uv run python tools/query_florida_court_directory_data.py virtual \
    --county "Lee County" \
    --output "$WORKDIR/fl-virtual-courtrooms.json"

# OSCA-held-record request process
uv run python tools/query_florida_court_directory_data.py data-request \
    --output "$WORKDIR/fl-osca-request.json"

# Aggregate statistical publications
uv run python tools/query_florida_court_directory_data.py statistics \
    --fiscal-year 2024-25 --section Statistics \
    --output "$WORKDIR/fl-trial-statistics.json"

# Exact catalog selector; validates and saves the official PDF
uv run python tools/query_florida_court_directory_data.py download \
    2472276 "$WORKDIR/fl-overall-statistics.pdf" \
    --output "$WORKDIR/fl-overall-statistics-download.json"

# Shared router: search only for these snapshots and catalogs
uv run python tools/query_state_courts.py search Miami \
    --source us-fl-state-court-location-directory \
    --output "$WORKDIR/fl-location-shared.json"
uv run python tools/query_state_courts.py search 2024-25 \
    --source us-fl-trial-court-statistical-reference-guide \
    --search-field fiscal-year \
    --output "$WORKDIR/fl-statistics-shared.json"

# Independent contract and rolling-snapshot observations
uv run python tools/public_records_monitor.py run \
    us-fl-state-court-location-directory \
    us-fl-virtual-courtroom-directory \
    us-fl-osca-public-records-request \
    us-fl-trial-court-statistical-reference-guide \
    --output "$WORKDIR/fl-court-data-monitor.json"
```

All four result families ingest as source snapshots, not cases. The verified
location feed omitted Gadsden County and carried ten map-category/embedded-DCA
region mismatches. Both source fields, the omission, and the mismatch list are
retained as publisher observations; the embedded region is not used as
normalized geography. Virtual entries are a current route directory and
partial personnel roster. OSCA request fulfillment is record-specific.
Statistical rows are aggregate catalog occurrences. Exact PDF download remains
on the direct adapter because it resolves a content ID, canonical reference,
filename, or exact title before saving and hashing the artifact.

### Florida Ninth Circuit archived-opinions adapter

`query_florida_ninth_opinions.py` traverses the official paginated archive of
Ninth Judicial Circuit appellate, certiorari, and writ opinions and validates
selected court-hosted PDFs.

```bash
# Source scope and official complements
uv run python tools/query_florida_ninth_opinions.py manifest \
    --output "$WORKDIR/ninth-opinions-manifest.json"

# Keyword search with a query-bound continuation cursor
uv run python tools/query_florida_ninth_opinions.py search \
    "Orange County" --limit 50 \
    --output "$WORKDIR/ninth-opinions.json"
uv run python tools/query_state_courts.py search "Orange County" \
    --source us-fl-ninth-circuit-appellate-opinions-archive \
    --output "$WORKDIR/ninth-opinions-shared.json"

# Validate and optionally save one official PDF returned by search
uv run python tools/query_florida_ninth_opinions.py download \
    "https://ninthcircuit.org/sites/default/files/06-45.pdf" \
    "$WORKDIR/06-45.pdf" \
    --output "$WORKDIR/ninth-opinion-document.json"

# First index page, pagination contract, identity, and one official PDF
uv run python tools/public_records_monitor.py run \
    us-fl-ninth-circuit-appellate-opinions-archive \
    --output "$WORKDIR/ninth-opinions-monitor.json"
```

Each index record preserves its published title, official PDF URL, source page,
and ordinal. Its native document ID is the first 24 hexadecimal characters of
the PDF URL's SHA-256. These publication snapshots do not project as trial
cases. The cataloged Orange Clerk route provides a separate trial-case and
docket layer, Ninth Circuit division calendars add Orange and Osceola schedule
context, and the official Osceola Clerk Benchmark and PERCH/JustFOIA routes are
tracked as the county-specific follow-up. Florida ACIS and the statewide
opinions search provide the separate Supreme Court and District Court of
Appeal layers.

### Osceola Clerk Benchmark adapter

`query_osceola_courts.py` covers the anonymous Osceola Benchmark case index,
exact case summaries, dockets, public document-page metadata, acquisition
handoffs, and two separately attributed rolling PDF reports.

```bash
uv run python tools/query_osceola_courts.py search \
    "2023 CF 001540" --search-mode case-number \
    --output "$WORKDIR/osceola-search.json"
uv run python tools/query_state_courts.py case "2023 CF 001540" \
    --source us-fl-osceola-benchmark-courts --ingest \
    --output "$WORKDIR/osceola-case.json"
uv run python tools/query_state_courts.py documents "2023 CF 001540" \
    --source us-fl-osceola-benchmark-courts \
    --docket-entry-uuid 56773534 \
    --output "$WORKDIR/osceola-document-pages.json"
uv run python tools/query_osceola_courts.py request-handoff \
    --case-number "2023 CF 001540" --docket-id 56773534 \
    --output "$WORKDIR/osceola-request-routes.json"
uv run python tools/query_osceola_courts.py report calendar \
    --artifact-output "$WORKDIR/osceola-calendar.pdf" \
    --output "$WORKDIR/osceola-calendar.json"
uv run python tools/public_records_monitor.py run \
    us-fl-osceola-benchmark-courts \
    us-fl-osceola-court-hearing-calendar \
    us-fl-osceola-mortgage-foreclosure-schedule \
    --output "$WORKDIR/osceola-monitor.json"
```

The main source exposes shared `case`, `discovery`, `docket`, `documents`,
`probe`, and `search` operations. The hearing calendar and mortgage
foreclosure schedule expose only `discovery` and `probe`; their current PDFs
ingest as source snapshots.

### Georgia AOC court-personnel directory adapter

`query_georgia_court_directory.py` searches the current statewide personnel
directory through its published search view and reads exact native record IDs
through the corresponding public detail view.

```bash
# Source contract, verified fields, classifications, and complements
uv run python tools/query_georgia_court_directory.py manifest \
    --output "$WORKDIR/ga-court-directory-manifest.json"

# Native contains/equality filters and bounded paging
uv run python tools/query_georgia_court_directory.py search \
    --directory-section "Superior Court Clerks" --county Fulton \
    --limit 100 --output "$WORKDIR/ga-superior-clerks.json"
uv run python tools/query_georgia_court_directory.py search \
    --court-class Superior --details \
    --output "$WORKDIR/ga-superior-personnel-details.json"

# Resume only with the same filters and page size
uv run python tools/query_georgia_court_directory.py search \
    --directory-section "Superior Court Clerks" \
    --cursor "<NEXT_CURSOR>" --limit 100 \
    --output "$WORKDIR/ga-superior-clerks-next.json"

# Exact detail and bounded source monitor
uv run python tools/query_georgia_court_directory.py detail \
    "<NATIVE_RECORD_ID>" \
    --output "$WORKDIR/ga-court-personnel-detail.json"
uv run python tools/query_state_courts.py search Robinson \
    --source us-ga-aoc-court-personnel-directory \
    --county Fulton --output "$WORKDIR/ga-directory-shared.json"
uv run python tools/query_state_courts.py detail "<NATIVE_RECORD_ID>" \
    --source us-ga-aoc-court-personnel-directory \
    --output "$WORKDIR/ga-directory-detail-shared.json"
uv run python tools/query_state_courts.py discovery \
    --source us-ga-aoc-court-personnel-directory \
    --search-field manifest \
    --output "$WORKDIR/ga-directory-discovery.json"
uv run python tools/public_records_monitor.py run \
    us-ga-aoc-court-personnel-directory \
    --output "$WORKDIR/ga-court-directory-monitor.json"
```

Search and detail records use
`GA-AOC-COURT-PERSONNEL:<native_record_id>` references and retain their
snapshot state. Court Class and Directory Section stay separate. The source's
Prefix field is emitted as `prefix_or_title`; composite City-search scope and
conditional email display state are preserved without inferring a broader
role or location. Directory rows remain current snapshot observations rather
than cases or historical roster entries.

Georgia AOC eAccess/eFile routes, official local court and county sites, and
GSCCCA systems add case access, filing-provider routing, local calendars and
contacts, or clerk-administered indices. They remain separately attributable
complements rather than copies of the personnel dataset.

### Georgia AOC court-access provider directories

`query_georgia_court_access.py` exposes the current eAccess and eFile tables
under distinct source identities. Both support court-text, county, court
class, provider, and published-state filters, plus provider summaries and
bounded probes.

```bash
# Account-backed case-search provider handoffs
uv run python tools/query_georgia_court_access.py search Fulton \
    --source us-ga-aoc-eaccess-court-records-directory \
    --output "$WORKDIR/ga-eaccess-fulton.json"

# Filing-provider state; blank cells are emitted as not_listed
uv run python tools/query_georgia_court_access.py search "*" \
    --source us-ga-aoc-efile-court-records-directory \
    --provider greenfiling_infotrack --published-state available \
    --output "$WORKDIR/ga-efile-greenfiling.json"
uv run python tools/query_georgia_court_access.py providers \
    --source us-ga-aoc-efile-court-records-directory \
    --output "$WORKDIR/ga-efile-provider-summary.json"

# Shared snapshot search, provider discovery, and monitoring
uv run python tools/query_state_courts.py search researchga \
    --source us-ga-aoc-eaccess-court-records-directory \
    --search-field provider \
    --output "$WORKDIR/ga-eaccess-shared.json"
uv run python tools/query_state_courts.py discovery \
    --source us-ga-aoc-efile-court-records-directory \
    --search-field providers \
    --output "$WORKDIR/ga-efile-providers-shared.json"
uv run python tools/public_records_monitor.py run \
    us-ga-aoc-eaccess-court-records-directory \
    us-ga-aoc-efile-court-records-directory \
    --output "$WORKDIR/ga-court-access-monitors.json"
```

Each current directory has 230 court rows: 159 Superior Court and 71 State
Court entries. eAccess keeps its direct-provider and provider-selection
handoffs distinct, including the source's two HTTP Chatham routes and the
provider page's published “e-Filing Vendor” copy. eFile retains Mandatory,
Available, and `not_listed` per provider; the latter means the table cell was
blank. Shared ingestion stores both envelopes only as source snapshots, with
zero case and filing projection.

### Georgia aggregate caseload and workload adapter

`query_georgia_court_data.py` lists six self-reported aggregate caseload
dashboards, verifies the dashboard-export request handoff, lists annual
Superior Court workload assessments, and validates exact annual PDFs.

```bash
uv run python tools/query_georgia_court_data.py dashboards Superior \
    --output "$WORKDIR/ga-superior-dashboard.json"
uv run python tools/query_georgia_court_data.py handoff \
    --output "$WORKDIR/ga-dashboard-export-handoff.json"
uv run python tools/query_georgia_court_data.py workloads --year 2024 \
    --output "$WORKDIR/ga-workload-2024.json"
uv run python tools/query_georgia_court_data.py document 2024 \
    --artifact-output "$WORKDIR/ga-workload-2024.pdf" \
    --output "$WORKDIR/ga-workload-document.json"

uv run python tools/query_state_courts.py search Superior \
    --source us-ga-aoc-caseload-dashboards \
    --search-field court-class \
    --output "$WORKDIR/ga-dashboard-shared.json"
uv run python tools/query_state_courts.py discovery \
    --source us-ga-aoc-caseload-dashboards \
    --search-field export \
    --output "$WORKDIR/ga-dashboard-export-shared.json"
uv run python tools/query_state_courts.py documents "*" \
    --source us-ga-superior-court-workload-assessments \
    --document-type pdf \
    --output "$WORKDIR/ga-workloads-shared.json"
uv run python tools/query_state_courts.py detail 2024 \
    --source us-ga-superior-court-workload-assessments \
    --search-field publication-year \
    --output "$WORKDIR/ga-workload-detail-shared.json"
uv run python tools/public_records_monitor.py run \
    us-ga-aoc-caseload-dashboards \
    us-ga-superior-court-workload-assessments \
    --output "$WORKDIR/ga-court-data-monitors.json"
```

Dashboard rows use court-class canonical references and remain aggregate
source snapshots. The export handoff currently offers 2021–2025 and all six
classes with `submission_performed=false`. Workload publication and validated
PDF rows share a year-bound canonical reference; the verified archive spans
2018–2024, and the 2024 PDF SHA-256 is
`21afb894a332aa67bbef46cecfa50a8721fbfee95392d0a711d57a6de8c4c099`.
Shared `detail` validates one exact year; no shared download route is exposed.

### Supreme Court of Georgia public-docket adapter

`query_georgia_supreme_docket.py` queries the official anonymous case-search
and exact-detail APIs for cases docketed in the last five years. Search modes
cover case number, case style, party, attorney, lower-court case number plus
county, and Court of Appeals case number.

```bash
uv run python tools/query_georgia_supreme_docket.py manifest \
    --output "$WORKDIR/ga-supreme-manifest.json"
uv run python tools/query_georgia_supreme_docket.py search S26G \
    --field case-number --limit 100 \
    --output "$WORKDIR/ga-supreme-search.json"
uv run python tools/query_georgia_supreme_docket.py detail S26G0537 \
    --output "$WORKDIR/ga-supreme-detail.json"
uv run python tools/query_georgia_supreme_docket.py documents S26G0537 \
    --output "$WORKDIR/ga-supreme-document-handoff.json"

uv run python tools/query_state_courts.py case S26G0537 \
    --source us-ga-supreme-court-public-docket \
    --output "$WORKDIR/ga-supreme-case-shared.json"
uv run python tools/query_state_courts.py docket S26G0537 \
    --source us-ga-supreme-court-public-docket \
    --output "$WORKDIR/ga-supreme-docket-shared.json"
uv run python tools/query_state_courts.py documents S26G0537 \
    --source us-ga-supreme-court-public-docket \
    --document-type metadata \
    --output "$WORKDIR/ga-supreme-documents-shared.json"
uv run python tools/query_state_courts.py discovery counties \
    --source us-ga-supreme-court-public-docket \
    --output "$WORKDIR/ga-supreme-counties-shared.json"
uv run python tools/public_records_monitor.py run \
    us-ga-supreme-court-public-docket \
    --output "$WORKDIR/ga-supreme-monitor.json"
```

The source returns complete search arrays, so continuation cursors are local
and bound to the observed query snapshot. `case` and `docket` both hydrate
exact detail and project the case, explicit attorneys, stable filing/order
docket entries, judgment/calendar events, and county-qualified lower-court
relations. The API has no public document URL or document ID; `documents`
returns filing metadata and the Clerk copy-request handoff as a source
snapshot, with zero document artifacts.

Annual opinions, certiorari grants and denials, discretionary/interlocutory
grant orders, oral calendars, and case announcements are separately
attributable official complements. The four decision-publication collections
are integrated below; oral calendars and case announcements remain separate
official routes.

### Supreme Court of Georgia decision publications

`query_georgia_supreme_publications.py` keeps four official annual publication
contracts distinct:

| Source ID | Verified annual pages | Publication grain |
|---|---:|---|
| `us-ga-supreme-court-opinions` | 2017–2026 | Opinion PDFs and selected noteworthy-summary packets |
| `us-ga-supreme-court-certiorari-grants` | 2022–2026 | Grant PDFs plus attributed Court of Appeals case/PDF crosswalks |
| `us-ga-supreme-court-certiorari-denials` | 2022–2026 | HTML denial entries with explicitly linked supplements when present |
| `us-ga-supreme-court-application-grant-orders` | 2022–2026 | Discretionary and interlocutory grant-order PDFs |

```bash
uv run python tools/query_georgia_supreme_publications.py sources \
    --output "$WORKDIR/ga-supreme-publication-sources.json"
uv run python tools/query_georgia_supreme_publications.py search "*" \
    --source us-ga-supreme-court-opinions --year 2026 \
    --output "$WORKDIR/ga-supreme-opinions.json"
uv run python tools/query_georgia_supreme_publications.py search "*" \
    --source us-ga-supreme-court-certiorari-grants \
    --case-number S26G0537 \
    --output "$WORKDIR/ga-supreme-cert-grant.json"
uv run python tools/query_georgia_supreme_publications.py detail \
    ga-sc-cert-grant-2026-c13c36859bc2de8874bd \
    --source us-ga-supreme-court-certiorari-grants \
    --output "$WORKDIR/ga-supreme-publication-detail.json"
uv run python tools/query_georgia_supreme_publications.py download \
    "https://www.gasupreme.us/wp-content/uploads/2026/07/s26c0537.pdf" \
    "$WORKDIR/s26c0537.pdf" \
    --source us-ga-supreme-court-certiorari-grants \
    --output "$WORKDIR/ga-supreme-download.json"

uv run python tools/query_state_courts.py search S26G0537 \
    --source us-ga-supreme-court-certiorari-grants \
    --search-field case-number \
    --output "$WORKDIR/ga-supreme-publication-shared.json"
uv run python tools/query_state_courts.py documents S26G0537 \
    --source us-ga-supreme-court-certiorari-grants \
    --output "$WORKDIR/ga-supreme-publication-documents.json"
uv run python tools/public_records_monitor.py run \
    us-ga-supreme-court-opinions \
    us-ga-supreme-court-certiorari-grants \
    us-ga-supreme-court-certiorari-denials \
    us-ga-supreme-court-application-grant-orders \
    --output "$WORKDIR/ga-supreme-publication-monitors.json"
```

All four sources expose shared `case`, `discovery`, `documents`, `download`,
`probe`, and `search` operations. Case-bearing rows project sparse appellate
case shells, typed publication events, and only the documents actually linked
by the source. Multi-case opinions and orders share one publication identity;
no parties are inferred. The certiorari-grant crosswalk keeps a linked Court of
Appeals PDF attributed to its originating court and does not treat it as a
second source for the Supreme Court grant.

The enumerated archive contains 2,938 opinion/summary occurrences for
2017–2026, 133 certiorari grants and 140 Court of Appeals crosswalks for
2022–2026, 1,660 denial entries with 26 linked supplements for 2022–2026, and
54 application grant orders for 2022–2026. These annual collections provide
partial decision-publication coverage, not a comprehensive historical opinion
archive or complete appellate docket.

The opinion index retains the Court's version notice: website and docket copies
may be modified, a `Final Copy` in the advance sheets replaces prior versions,
and bound Georgia Reports contain the final and official text. The monitor
fingerprints that contract, the annual route and output schema separately from
rolling annual counts and current HTML/PDF hashes.

### Orange County hearing-calendar adapter

`query_orange_county_courts.py` queries the official Clerk calendar for
current and future hearings. It returns case-shaped envelopes with each
hearing represented as a docket entry.

```bash
uv run python tools/query_orange_county_courts.py search \
    --case-number 2020-CT-001540-A-O \
    --output "$WORKDIR/orange-hearings.json"
uv run python tools/query_orange_county_courts.py search \
    --date 2026-07-29 --limit 100 --offset 0 \
    --output "$WORKDIR/orange-daily-hearings.json"
uv run python tools/query_orange_county_courts.py search \
    --first-name EXAMPLE --last-name PERSON \
    --output "$WORKDIR/orange-name-hearings.json"
uv run python tools/query_orange_county_courts.py probe \
    --output "$WORKDIR/orange-calendar-probe.json"
uv run python tools/public_records_monitor.py run \
    us-fl-orange-county-hearing-calendar \
    --output "$WORKDIR/orange-calendar-monitor.json"
```

The route exposes hearing date/time, location, caption, judge, and status, but
not past hearings, juvenile cases, docket history, or case-detail links. The
separate `us-fl-orange-clerk-my-eclerk` source action covers the interactive
case/docket/document portal, while Florida ACIS and official local
opinion/calendar/request/recorder routes provide appellate, document, event,
and property-record complements.

### Los Angeles Superior Court civil adapter

```bash
# Complete anonymous exact-case summary
uv run python tools/query_los_angeles_court.py case 24NNCV00427 \
    --output "$WORKDIR/la-civil-case.json"

# List the complete current native selection inventory, then fetch one or all
uv run python tools/query_los_angeles_court.py selections \
    --output "$WORKDIR/la-ruling-selections.json"
uv run python tools/query_los_angeles_court.py rulings \
    "ALH,3,07/30/2026" --output "$WORKDIR/la-selected-rulings.json"
uv run python tools/query_los_angeles_court.py rulings all \
    --output "$WORKDIR/la-all-current-rulings.json"
uv run python tools/query_los_angeles_court.py probe \
    --output "$WORKDIR/la-civil-probe.json"

# Shared exact-case and current-ruling routes
uv run python tools/query_state_courts.py case 24NNCV00427 \
    --source us-ca-los-angeles-superior-civil --ingest \
    --output "$WORKDIR/la-civil-unified-case.json"
uv run python tools/query_state_courts.py docket 24NNCV00427 \
    --source us-ca-los-angeles-superior-civil --ingest \
    --output "$WORKDIR/la-civil-unified-docket.json"
uv run python tools/query_state_courts.py documents 24NNCV00427 \
    --source us-ca-los-angeles-superior-civil --ingest \
    --output "$WORKDIR/la-civil-unified-documents.json"
uv run python tools/query_state_courts.py calendar all \
    --source us-ca-los-angeles-superior-civil --ingest \
    --output "$WORKDIR/la-civil-unified-rulings.json"
```

Case Summary preserves all six source sections: case information, future
hearings, parties, filed-document metadata, past proceedings, and register
actions. Repeated source rows receive deterministic case-scoped identifiers
and duplicate ordinals. The current tentative-ruling inventory contained 84
exact location/department/date selections in validation; omitted bounds
traverse all of them and preserve full text and tentative status.

The paid civil name index and document-image delivery service are separate
catalog sources linked to the same civil case identity. Family-law,
small-claims, probate, Superior Court Appellate Division tentative rulings,
Second District case information, statewide opinions, and public notices are
also retained as explicit complements.

```bash
uv run python tools/public_records_monitor.py run \
    us-ca-los-angeles-superior-civil \
    --output "$WORKDIR/la-civil-monitor.json"
```

### Los Angeles Superior Court paid name-index adapter

The adapter verifies the official coverage, fees, form fields, and receipt
recovery route; prepares a person or company search through the court cart;
and normalizes purchased results from either a guest receipt or saved HTML.

```bash
uv run python tools/query_los_angeles_name_index.py sources \
    --output "$WORKDIR/la-name-routes.json"
uv run python tools/query_los_angeles_name_index.py probe \
    --output "$WORKDIR/la-name-probe.json"
uv run python tools/query_los_angeles_name_index.py prepare \
    --company "EXAMPLE HOLDINGS LLC" \
    --output "$WORKDIR/la-name-cart.json"
uv run python tools/query_los_angeles_name_index.py receipt \
    PA-2026-123456789 1234 --retrieve \
    --output "$WORKDIR/la-name-results.json"
uv run python tools/query_los_angeles_name_index.py parse-results \
    purchased-results.html --output "$WORKDIR/la-name-results.json"
uv run python tools/ingest_state_court_records.py ingest \
    "$WORKDIR/la-name-results.json" \
    --output "$WORKDIR/la-name-ingest.json"
uv run python tools/public_records_monitor.py run \
    us-ca-los-angeles-superior-civil-name-index \
    --output "$WORKDIR/la-name-monitor.json"
```

The result identity includes the matched party, case type, filing date,
filing location, and duplicate ordinal. Ingestion records each hit in
`case_source_occurrence` while crosswalking the case number to the matching
civil, family-law, small-claims, or probate Case Summary identity. Official
Archives, divorce-judgment orders, document images, Second District records,
and the Trellis Los Angeles coverage route remain distinct complements.

### Los Angeles Superior Court probate adapter

`query_los_angeles_probate.py` queries three verified anonymous court routes
for a known probate case number. Case Summary returns case metadata, parties,
future hearings, the filed-document index, past proceedings, and register
actions. Probate Notes and Case Calendar remain distinct commands because
their fields and publisher-stated windows differ.

```bash
# Exact case metadata, parties, filed-document index, proceedings, and ROA
uv run python tools/query_los_angeles_probate.py case 17STPB02676 \
    --output "$WORKDIR/la-probate-case.json"

# Future, past, or both Probate Notes views
uv run python tools/query_los_angeles_probate.py notes 26STPB00601 \
    --view all --output "$WORKDIR/la-probate-notes.json"

# Upcoming hearings for a known case
uv run python tools/query_los_angeles_probate.py calendar 26STPB00601 \
    --output "$WORKDIR/la-probate-calendar.json"

# Verify the anonymous form and result schemas
uv run python tools/query_los_angeles_probate.py probe \
    --output "$WORKDIR/la-probate-probe.json"

# Unified exact-case, docket, document-index, notes, and calendar routes
uv run python tools/query_state_courts.py case 26STPB00601 \
    --source us-ca-los-angeles-superior-probate --ingest \
    --output "$WORKDIR/la-probate-unified-case.json"
uv run python tools/query_state_courts.py notes 26STPB00601 \
    --source us-ca-los-angeles-superior-probate --view all --ingest \
    --output "$WORKDIR/la-probate-unified-notes.json"
uv run python tools/query_state_courts.py calendar 26STPB00601 \
    --source us-ca-los-angeles-superior-probate --ingest \
    --output "$WORKDIR/la-probate-unified-calendar.json"
uv run python tools/public_records_monitor.py run \
    us-ca-los-angeles-superior-probate \
    --output "$WORKDIR/la-probate-monitor.json"
```

Repeated rows are uncapped by the adapter unless the caller supplies
`--limit` and `--offset`. The source does not expose stable identifiers for
Case Summary filing and register rows, so the adapter derives deterministic
case-scoped identifiers from displayed fields and duplicate occurrence.

The paid 1983-present name index, paid document-image delivery, Clerk and
Archives copies, Second District appellate case information, Judicial Branch
opinions, California Public Notices, County Assessor parcels, and
Registrar-Recorder instruments are cataloged as separate complementary
routes. They join through native case numbers, trial/appellate cross-
references, party aliases, hearing fields, document IDs, AIN/APN, recording
locators, and notice reference codes.

### California current appellate opinions

`query_california_opinions.py` searches the Judicial Branch's current
published/citable and unpublished/non-citable opinion pages. The published
feed retains 120 days and represents as-filed slip opinions; the unpublished
feed retains 60 days. Detail pages enumerate the official PDF and DOCX
formats. A modified publication identifier such as `B350634M` remains
distinct while crosswalking to base appellate case `B350634`.

```bash
# Direct current-feed search, exact detail, and source route inventory
uv run python tools/query_california_opinions.py search \
    --collection published --case-number S287786 \
    --output "$WORKDIR/ca-opinions-search.json"
uv run python tools/query_california_opinions.py detail \
    https://courts.ca.gov/opinion/published/2026-07-30/s287786 \
    --output "$WORKDIR/ca-opinion-detail.json"
uv run python tools/query_california_opinions.py alternatives \
    --output "$WORKDIR/ca-opinion-complements.json"

# Shared exact-case publication metadata and listed document formats
uv run python tools/query_state_courts.py case S287786 \
    --source us-ca-judicial-branch-opinions \
    --case-type published --output "$WORKDIR/ca-opinion-case.json"
uv run python tools/query_state_courts.py documents S287786 \
    --source us-ca-judicial-branch-opinions \
    --document-type published --output "$WORKDIR/ca-opinion-documents.json"

# Bounded listing/detail monitor for both rolling collections
uv run python tools/public_records_monitor.py run \
    us-ca-judicial-branch-opinions \
    --output "$WORKDIR/ca-opinions-monitor.json"
```

The `citings` command preserves an opinion's source-displayed web URL and the
court-hosted archived copy; that transport pairing is not separate
corroboration. Appellate Case Information remains the older-case and docket
complement. The no-fee Official Reports service supplies corrected and
historical citable text from 1850 onward, rather than a version already
contained in these current feeds.

### California directory, Santa Clara, and San Diego

```bash
# Statewide discovery snapshot; no case rows are projected
uv run python tools/query_california_court_directory.py list \
    --output "$WORKDIR/ca-court-directory.json"
uv run python tools/query_state_courts.py search "Santa Clara" \
    --source us-ca-superior-court-directory --ingest \
    --output "$WORKDIR/ca-court-route.json"

# Current Santa Clara ruling publications and requested index descriptions
uv run python tools/query_santa_clara_court_records.py rulings \
    --department 1 --output "$WORKDIR/santa-clara-rulings.json"
uv run python tools/query_santa_clara_court_records.py products \
    --output "$WORKDIR/santa-clara-index-products.json"

# San Diego live index and separate five-court-day filing publication
uv run python tools/query_state_courts.py search "Example" \
    --source us-ca-san-diego-superior-court-index --case-type civil \
    --output "$WORKDIR/san-diego-party-index.json"
uv run python tools/query_san_diego_court_index.py new-filings \
    --case-type all --output "$WORKDIR/san-diego-new-filings.json"
```

The California directory and Santa Clara ruling records ingest as source
snapshots. San Diego index/new-filing rows share source/court/case identity and
can project cases, but they do not create docket or document rows. Santa Clara
index products remain request routes, and its observed portal operations
remain a separate interactive component.

### Fresno Superior Court source family

```bash
# Complete current artifact indexes and selected source documents
uv run python tools/query_fresno_superior_court.py calendar-index \
    --output "$WORKDIR/fresno-calendar-index.json"
uv run python tools/query_fresno_superior_court.py calendar \
    --date 2026-07-30 --output "$WORKDIR/fresno-calendar.json"
uv run python tools/query_fresno_superior_court.py rulings-index \
    --output "$WORKDIR/fresno-rulings-index.json"
uv run python tools/query_fresno_superior_court.py rulings \
    --department 501 --date 2026-07-30 \
    --output "$WORKDIR/fresno-rulings.json"

# Exact-case examiner notes and mapped acquisition alternatives
uv run python tools/query_fresno_superior_court.py probate-notes \
    --case-number 19CEPR00967 \
    --output "$WORKDIR/fresno-probate-notes.json"
uv run python tools/query_fresno_superior_court.py alternatives \
    --output "$WORKDIR/fresno-alternatives.json"
uv run python tools/query_fresno_superior_court.py probe \
    --output "$WORKDIR/fresno-probe.json"

# Shared routes and normalized ingestion
uv run python tools/query_state_courts.py calendar 2026-07-30 \
    --source us-ca-fresno-superior-court-daily-calendar --ingest \
    --output "$WORKDIR/fresno-calendar-unified.json"
uv run python tools/query_state_courts.py calendar 501 \
    --source us-ca-fresno-superior-court-tentative-rulings \
    --hearing-date 2026-07-30 --ingest \
    --output "$WORKDIR/fresno-rulings-unified.json"
uv run python tools/query_state_courts.py notes 19CEPR00967 \
    --source us-ca-fresno-superior-court-probate-examiner-notes --ingest \
    --output "$WORKDIR/fresno-probate-unified.json"
```

The daily-calendar parser covers both observed PDF layouts and parsed all
1,056 rows in the live validation artifact. The ruling parser preserves
ordinary tentative rulings, continuances, and must-appear entries from 20
current department PDFs. The probate application returned 52 sentinel notes
and preserves their examiner-note—not official case-file—lineage.

The e-Court portal, calendar, rulings, probate notes, ordered monthly case
indexes, and record/copy routes have separate source IDs. If the portal is not
the useful representation for a query, `alternatives` returns the official
monthly PDF/text case-index product, archive viewing/copy/certification,
case-contact, administrative-record, elevated-access, and Fifth District
appellate paths.

```bash
uv run python tools/public_records_monitor.py run \
    us-ca-fresno-superior-court-public-records \
    us-ca-fresno-superior-court-ecourt-portal \
    us-ca-fresno-superior-court-daily-calendar \
    us-ca-fresno-superior-court-tentative-rulings \
    us-ca-fresno-superior-court-probate-examiner-notes \
    --output "$WORKDIR/fresno-monitors.json"
```

### Orange County Superior Court source family

```bash
# Exhaust the native calendar pages unless a caller supplies --limit.
uv run python tools/query_orange_county_court.py calendar civil \
    --title "Kiani" --output "$WORKDIR/orange-calendar.json"

# Current ruling directories and an exact department artifact.
uv run python tools/query_orange_county_court.py ruling-index \
    --division all --output "$WORKDIR/orange-ruling-index.json"
uv run python tools/query_orange_county_court.py ruling civil C44 \
    --download "$WORKDIR/orange-c44.pdf" \
    --output "$WORKDIR/orange-c44.json"
uv run python tools/query_orange_county_court.py sources \
    --output "$WORKDIR/orange-sources.json"

# Shared routes preserve the source-native category and department selectors.
uv run python tools/query_state_courts.py search "Kiani" \
    --source us-ca-orange-superior-court-calendar --case-type civil --ingest \
    --output "$WORKDIR/orange-calendar-unified.json"
uv run python tools/query_state_courts.py calendar all \
    --source us-ca-orange-superior-court-probate-tentative-rulings \
    --output "$WORKDIR/orange-probate-ruling-index.json"
uv run python tools/query_state_courts.py documents C44 \
    --source us-ca-orange-superior-court-civil-tentative-rulings --ingest \
    --output "$WORKDIR/orange-c44-unified.json"
```

The calendar exposes civil, criminal, family, probate, small-claims, and
traffic categories. Its 50-row page size is transport, while the court's
six-week future visibility is source coverage; neither becomes a hidden
caller cap. Current ruling directories are fully enumerated, and exact PDFs
retain their bytes, digest, full text, tentative status, case identifiers,
department, judge, and hearing fields.

The free-account name search, case-type access portals, permanent filing
index, $50 monthly/legacy plain-text index products, probate notes, and
record-copy/certification routes have distinct catalog entries. Use those
substitutes when a calendar or rolling ruling publication does not supply the
case history, document, older record, or name-to-case discovery needed.

```bash
uv run python tools/public_records_monitor.py run \
    us-ca-orange-superior-court-public-records \
    us-ca-orange-superior-court-calendar \
    us-ca-orange-superior-court-civil-tentative-rulings \
    us-ca-orange-superior-court-family-tentative-rulings \
    us-ca-orange-superior-court-probate-tentative-rulings \
    --output "$WORKDIR/orange-monitors.json"
```

### Riverside Superior Court source family

```bash
# Complete selected eCalendar response; the visible 12-row grid is client-side.
uv run python tools/query_riverside_court.py calendar \
    --courthouse "Historic Court House" --department 8 \
    --area-of-law probate \
    --output "$WORKDIR/riverside-calendar.json"

# Complete current ruling directory and one exact department PDF/text.
uv run python tools/query_riverside_court.py ruling-index \
    --output "$WORKDIR/riverside-ruling-index.json"
uv run python tools/query_riverside_court.py ruling PS1 \
    --download "$WORKDIR/riverside-ps1.pdf" \
    --output "$WORKDIR/riverside-ps1.json"
uv run python tools/query_riverside_court.py sources \
    --output "$WORKDIR/riverside-sources.json"

# Shared routing and court-sidecar projection.
uv run python tools/query_state_courts.py calendar 8 \
    --source us-ca-riverside-superior-court-ecalendar \
    --jurisdiction 06065 --case-type probate --ingest \
    --output "$WORKDIR/riverside-calendar-unified.json"
uv run python tools/query_state_courts.py calendar all \
    --source us-ca-riverside-superior-court-tentative-rulings \
    --output "$WORKDIR/riverside-ruling-index-unified.json"
uv run python tools/query_state_courts.py documents PS1 \
    --source us-ca-riverside-superior-court-tentative-rulings --ingest \
    --output "$WORKDIR/riverside-ps1-unified.json"

uv run python tools/public_records_monitor.py run \
    us-ca-riverside-superior-court-ecalendar \
    us-ca-riverside-superior-court-tentative-rulings \
    --output "$WORKDIR/riverside-monitors.json"
```

The eCalendar publishes the current day plus the next three business days and
accepts courthouse, department, area-of-law, and date selections. The current
directory lists department ruling PDFs but can retain mixed-age artifacts;
directory membership, artifact identity, and extracted hearing date are
preserved independently. Only case-bearing calendar rows and ruling documents
project to the court sidecar.

Registered Public Access, its coverage guide, paid name-index products,
clerk-performed searches, copy/certification forms, Probate Notes,
high-interest cases, transcript requests, the Appellate Division, and Fourth
District Division Two case information are distinct catalog sources. Use them
for case history, documents, older discovery, hearing text, or appellate
context when the current calendar or ruling publication does not contain those
records.

### Queensland eCourts civil case adapter

```bash
# Complete party/company search, with adaptive partitioning at the source cap.
uv run python tools/query_qld_ecourts.py search \
    --party-name COSCOLLUELA \
    --output "$WORKDIR/qld-party-search.json"

# Exact registry-qualified case detail.
uv run python tools/query_qld_ecourts.py case 6819/11 \
    --court SUPRE --location BRISB \
    --output "$WORKDIR/qld-case.json"

# Source inventory and bounded known-file probe.
uv run python tools/query_qld_ecourts.py sources \
    --output "$WORKDIR/qld-sources.json"
uv run python tools/query_qld_ecourts.py probe \
    --output "$WORKDIR/qld-probe.json"

# Shared routing and normalized case/party/event/document-metadata ingestion.
uv run python tools/query_state_courts.py search COSCOLLUELA \
    --source au-qld-ecourts-civil --jurisdiction AU-QLD \
    --court-id qld-supreme-court --courthouse BRISB \
    --output "$WORKDIR/qld-unified-search.json"
uv run python tools/query_state_courts.py case 6819/11 \
    --source au-qld-ecourts-civil --jurisdiction AU-QLD \
    --court-id qld-supreme-court --courthouse BRISB --ingest \
    --output "$WORKDIR/qld-unified-case.json"

uv run python tools/public_records_monitor.py run \
    au-qld-ecourts-civil \
    --output "$WORKDIR/qld-monitor.json"
```

Native search pages contain 20 files and one search partition reports at most
500 matches. Omitted limits traverse the pages and split capped searches by
court, originating registry, category, and party role. Any remaining capped
partition is explicit in a `partial` result.

The file number is not globally unique. Canonical source identity includes the
court code and originating registry, for example
`QLD-ECOURTS:SUPRE-BRISB-6819-2011`. Document rows are index metadata rather
than downloaded artifacts. Use the separately cataloged court-record copy
request for filings, and the criminal lookup, daily lists, CaseLaw, Queensland
Judgments, or State Archives routes for the adjacent record role.

### San Mateo Superior Court MIDX adapter

`query_san_mateo_midx.py` searches the court's anonymous MIDX case and party
index through its native Chromium form flow.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_san_mateo_midx.py case PRO116668-B \
    --output "$WORKDIR/san-mateo-case-index.json"
uv run python tools/query_san_mateo_midx.py search \
    --first-name FRANK --last-name CREER \
    --output "$WORKDIR/san-mateo-person-index.json"
uv run python tools/query_san_mateo_midx.py search \
    --business-name "EXAMPLE HOLDINGS*" \
    --output "$WORKDIR/san-mateo-business-index.json"
uv run python tools/query_san_mateo_midx.py search \
    --filed-from 2026-07-20 --filed-to 2026-07-24 \
    --output "$WORKDIR/san-mateo-filed-index.json"
uv run python tools/query_san_mateo_midx.py probe \
    --output "$WORKDIR/san-mateo-midx-probe.json"
```

The date selector accepts at most five inclusive calendar days. MIDX uses
opaque same-origin pagination; the adapter follows every page and returns all
native index rows by default. `--limit` and `--offset` are optional caller
controls. No total-result ceiling was observed: a verified date partition
returned 1,290 rows across 86 pages, with 15 rows on each full page.

MIDX emits case number, party name, native `Type` code, filing date, and index
information link. It is not a register of actions or filing-image source.
Odyssey case detail/documents, daily hearing PDFs, tentative rulings, Records
Management copies, First District appellate records, Judicial Branch
opinions, Recorder/Assessor records, and California Public Notices remain
separate complementary routes.

### Pima County Superior Court Agave adapter

`query_pima_courts.py` uses the Clerk-linked PublicDocs frame application for
party search, case detail, parties, charges/dispositions, docket rows, and
available public PDFs.

```bash
uv run python tools/query_pima_courts.py search MALLETT --limit 25 \
    --output "$WORKDIR/pima-search.json"
uv run python tools/query_pima_courts.py case C20256501 \
    --output "$WORKDIR/pima-case.json"
uv run python tools/query_pima_courts.py document C20256501 \
    "<PIMA_DOCKET_ENTRY_ID>" "$WORKDIR/pima-filing.pdf" \
    --output "$WORKDIR/pima-document.json"
uv run python tools/query_pima_courts.py probe \
    --output "$WORKDIR/pima-probe.json"

# The unified router supports search, case, docket, documents, and download
uv run python tools/query_state_courts.py search MALLETT \
    --source us-az-pima-superior-agave --ingest \
    --output "$WORKDIR/pima-unified-search.json"
uv run python tools/public_records_monitor.py run \
    us-az-pima-superior-agave \
    --output "$WORKDIR/pima-monitor.json"
```

Ephemeral result/detail/PDF tokens are resolved only inside the active
session. Case numbers remain canonical; displayed docket fields plus duplicate
occurrence produce deterministic case-scoped row IDs. For an Agave
exact-number miss when a party is known, the direct case/document commands
accept `--last-name` and optional `--first-name` as a party-index fallback.
Arizona eAccess, statewide public case lookup, the Pima future calendar, Clerk
record requests, and appellate case/opinion systems remain complementary
routes with different fields and coverage.

### Franklin County Common Pleas CIO adapter

`query_ohio_franklin_courts.py` searches the ordered lower-bound CIO party-name
index and retrieves exact cases, parties, schedule rows, the complete native
next-key docket, and public filing metadata. Name rows preserve duplicates and
lexical spillover while `matched_query` identifies true prefix matches.

```bash
uv run python tools/query_ohio_franklin_courts.py name WEXNER \
    --court civil --filed-from 2020-05-19 --filed-to 2020-05-19 \
    --exhaustive --output "$WORKDIR/franklin-party.json"
uv run python tools/query_ohio_franklin_courts.py case 22CV3098 \
    --output "$WORKDIR/franklin-case.json"
uv run python tools/query_ohio_franklin_courts.py document 22CV3098 \
    "franklin:document:<id>" "$WORKDIR/franklin-filing.pdf" \
    --output "$WORKDIR/franklin-download.json"

# Shared operations include search, case, docket, documents, and download
uv run python tools/query_state_courts.py search WEXNER \
    --source us-oh-franklin-common-pleas-cio --ingest \
    --output "$WORKDIR/franklin-shared-party.json"
uv run python tools/query_state_courts.py case 22CV3098 \
    --source us-oh-franklin-common-pleas-cio --ingest \
    --output "$WORKDIR/franklin-shared-case.json"
uv run python tools/public_records_monitor.py run \
    us-oh-franklin-common-pleas-cio \
    --output "$WORKDIR/franklin-monitor.json"
```

CIO's party index has no continuation. Exhaustive mode can partition supplied
filing dates and the all-court category; a matching native boundary or an
incomplete response-buffer terminal row remains partial. Document coordinates
and disclaimer/session values remain transport state. The fixed monitor makes
five requests for landing, acceptance, party sentinel, case sentinel, and first
docket continuation; full case retrieval continues until the docket next key
is empty.

### Franklin County Municipal Court adapter

`query_ohio_franklin_municipal.py` searches person, company, exact case number,
or ticket and retrieves detailed case, party, attorney, charge, disposition,
event, financial, receipt, and docket records. Search occurrence identity does
not retain the encrypted case handle. The explicit 250-row ceiling has no
continuation and returns partial coverage when reached.

```bash
uv run python tools/query_ohio_franklin_municipal.py person BURKHALTER ERIKA \
    --output "$WORKDIR/fcmc-party.json"
uv run python tools/query_ohio_franklin_municipal.py company "L BRANDS" \
    --output "$WORKDIR/fcmc-company.json"
uv run python tools/query_ohio_franklin_municipal.py case "2022 CVF 020731" \
    --output "$WORKDIR/fcmc-case.json"
uv run python tools/query_state_courts.py download generated-case-summary \
    --case-number "2022 CVF 020731" \
    --destination "$WORKDIR/fcmc-summary.pdf" \
    --source us-oh-franklin-municipal-court-records \
    --output "$WORKDIR/fcmc-summary.json"
```

The PDF route generates a current case summary, not an individual filed
document. The five-request monitor checks the search form, bounded person
result, exact case, detail sections, and PDF contract without treating the
rolling PDF digest or rate-limit remainder as stable schema.

### Delaware County Common Pleas CourtView adapter

`query_ohio_delaware_common_pleas.py` operates the official CourtView portal in
a persistent headed browser session after the user clears its visible
challenge. Search selects the native 100-row page size and exhausts every page;
bounded output uses a query-bound offset cursor over that collected set.

```bash
uv run python tools/query_ohio_delaware_common_pleas.py warmup \
    --wait-seconds 120 --output "$WORKDIR/delaware-session.json"
uv run python tools/query_ohio_delaware_common_pleas.py search-party \
    --last-name SMITH --first-name JOHN \
    --output "$WORKDIR/delaware-party.json"
uv run python tools/query_ohio_delaware_common_pleas.py case <case-number> \
    --output "$WORKDIR/delaware-case.json"
uv run python tools/query_ohio_delaware_common_pleas.py document \
    <case-number> <dktdoc-id> \
    --document-output "$WORKDIR/delaware-filing.pdf" \
    --output "$WORKDIR/delaware-document.json"
```

Case detail includes parties, attorneys, docket, events, and financial/receipt
tables. Document identity derives from the case and docket occurrence; download
reopens the case and resolves the current Wicket action. Domestic Relations
filing images are not public online, and the portal states additional Juvenile
and Probate image limitations. The monitor fingerprints the rendered browser
contract without inventing a fixed network-request budget.

### Licking County Common Pleas remote-record adapter

`query_ohio_licking_common_pleas.py` verifies the county landing and anonymous
Tyler tenant/configuration shell and produces structured targeted-browser,
bulk, current/certified-copy, and historical-archive handoffs. The observed
terminal transition reaches AWS Human Verification, so no post-login case API
or paging contract is asserted.

```bash
uv run python tools/query_ohio_licking_common_pleas.py probe \
    --output "$WORKDIR/licking-probe.json"
uv run python tools/query_ohio_licking_common_pleas.py targeted-browser-handoff \
    --party-name SMITH \
    --output "$WORKDIR/licking-browser.json"
uv run python tools/query_ohio_licking_common_pleas.py bulk-request-handoff \
    --scope "party index and docket rows" --party-name SMITH \
    --output "$WORKDIR/licking-bulk.json"
uv run python tools/query_ohio_licking_common_pleas.py archives-handoff \
    --party-name SMITH --year 1990 \
    --output "$WORKDIR/licking-archives.json"
```

The fixed six-request probe covers the official landing, Tyler tenant shell,
and four public JSON components. Sheriff foreclosure sources, Recorder PAX, Auditor/OGRIP
property records, Clerk requests, and county archives remain separately
attributable alternatives. See
[`docs/sources/ohio-county-trial-court-party-indexes.md`](sources/ohio-county-trial-court-party-indexes.md)
for result semantics and coverage details.

### Franklin County Probate NetData adapter

`query_ohio_franklin_probate.py` searches the official Probate Court indexes
by case name, exact opened date, case type/subtype, attorney, fiduciary, or
case number. Exact case operations expose the type-specific detail page,
docket rows, fiduciaries, and linked attorney records.

```bash
uv run python tools/query_ohio_franklin_probate.py name "SMITH" \
    --output "$WORKDIR/franklin-probate-name.json"
uv run python tools/query_ohio_franklin_probate.py case 617503 \
    --output "$WORKDIR/franklin-probate-case.json"
uv run python tools/query_ohio_franklin_probate.py fiduciaries 617503 \
    --output "$WORKDIR/franklin-probate-fiduciaries.json"

uv run python tools/query_state_courts.py search "SMITH" \
    --source us-oh-franklin-probate-netdata --ingest \
    --output "$WORKDIR/franklin-probate-shared-search.json"
uv run python tools/query_state_courts.py docket 617503 \
    --source us-oh-franklin-probate-netdata --ingest \
    --output "$WORKDIR/franklin-probate-shared-docket.json"
uv run python tools/public_records_monitor.py run \
    us-oh-franklin-probate-netdata \
    --output "$WORKDIR/franklin-probate-monitor.json"
```

Omitted limits follow the source's forward keys to exhaustion; explicit
limits return a cursor bound to the query, page, row, and schema. Case
identity is the number plus the fixed-width optional suffix. Docket identity
uses the logical displayed entry and its retained physical rows; fiduciary
identity uses the case selector plus fiduciary number. Normalized ingestion
projects case metadata, docket entries, fiduciaries, and their explicitly
linked attorneys while preserving standalone attorney/profile records as
source snapshots. Published docket costs stay docket fields, not estate
claims, and the verified routes do not publish filing images. The seven-request
monitor covers landing, exact-number index, type detail, docket, fiduciary
list, and one fiduciary/attorney pair.

### Supreme Court of Ohio eCMS shared adapter

`query_ohio_supreme_court.py` covers the official Supreme Court public case
index, exact case detail, parties and attorney appearances, docket entries,
decision metadata, case issues, recent filings, and public PDFs.

```bash
uv run python tools/query_state_courts.py search Newsome \
    --source us-oh-supreme-court-public-docket \
    --output "$WORKDIR/ohio-supreme-search.json"
uv run python tools/query_state_courts.py search 2017-1682 \
    --source us-oh-supreme-court-public-docket \
    --search-field case-number \
    --output "$WORKDIR/ohio-supreme-case-search.json"
uv run python tools/query_state_courts.py case 2017-1682 \
    --source us-oh-supreme-court-public-docket --ingest \
    --output "$WORKDIR/ohio-supreme-case.json"
uv run python tools/query_state_courts.py download 835936.pdf \
    --source us-oh-supreme-court-public-docket \
    --case-number 2017-1682 --document-section DocketItems \
    --destination "$WORKDIR/835936.pdf" \
    --output "$WORKDIR/ohio-supreme-download.json"
uv run python tools/public_records_monitor.py run \
    us-oh-supreme-court-public-docket \
    --output "$WORKDIR/ohio-supreme-monitor.json"
```

Shared search defaults to the native caption field and supports the verified
case-number, prior-case, party, attorney, and filing-date alternatives.
Caller limits are applied only after the source array is retrieved; exactly
1,000 returned search rows remain an explicit partial source-boundary result.
Case identity is the published case number. The eCMS internal case locator and
search-row ID remain raw metadata and never split shared search/detail
identity. Downloads require an explicit `DocketItems` or `DecisionItems`
section. Direct `recent` remains a discovery operation because those rows do
not publish the native docket ID.

The five-request monitor covers the landing, request-token bundle, stable
caption search, exact case, and rolling recent filings without downloading a
PDF. Reporter of Decisions publications, Clerk's Journal orders, attorney and
judge directories, trial-court routing, court statistics, and local court
systems remain separately attributable components.

### Ohio Reporter of Decisions shared publication adapter

`query_ohio_reporter_decisions.py` searches the official statewide opinion
and case-announcement publication index. The shared surface keeps WebCite
publication identity separate from the optional deciding-court case number
and official PDF representation.

```bash
uv run python tools/query_state_courts.py search "public records" \
    --source us-oh-reporter-of-decisions \
    --output "$WORKDIR/ohio-reporter-search.json"
uv run python tools/query_state_courts.py search C-250425 \
    --source us-oh-reporter-of-decisions \
    --court-id oh-court-of-appeals-district-1 \
    --search-field case-number \
    --output "$WORKDIR/ohio-reporter-case-number.json"
uv run python tools/query_state_courts.py detail 2018-Ohio-723 \
    --source us-oh-reporter-of-decisions --ingest \
    --output "$WORKDIR/ohio-reporter-publication.json"
uv run python tools/query_state_courts.py download 2018-Ohio-723 \
    --source us-oh-reporter-of-decisions \
    --destination "$WORKDIR/2018-Ohio-723.pdf" \
    --output "$WORKDIR/ohio-reporter-document.json"
uv run python tools/public_records_monitor.py run \
    us-oh-reporter-of-decisions \
    --output "$WORKDIR/ohio-reporter-monitor.json"
```

Shared operations are `search`, `detail`, and `download`; there is no
Reporter `case` route. Search defaults to full text across all Reporter
sources and supports deciding-court, exact case-number, author, topics, and
print-citation selection. Every native GridView page is fetched before an
explicit `--limit` or `--max-records` caller window. With no explicit window,
the shared router adds no local result cap. The documented 1,000-row full-text
boundary remains an explicit partial source result rather than a local cap.

Every result envelope is snapshotted. Only an unambiguous single case-number
token can add a sparse normalized case join; case-less announcements and
ambiguous or combined case-number cells remain snapshot-only. The joined
publication is a WebCite-keyed event, and the PDF remains a document
representation rather than a case identity. The fixed three-request monitor
checks the landing and exact-WebCite route without downloading a PDF or
persisting WebForms state. Reporter, eCMS, Clerk's Journal, and district
copies of the same judicial act are complementary official representations,
not independent corroboration merely because they use different routes.

### Connecticut Superior Court Civil/Family shared adapter

`query_connecticut_civil_family.py` implements the official party-name,
exact-docket, history, notice, and linked `DocumentNo` routes. Shared
operations are `search`, `case`, `docket`, `documents`, `download`,
`discovery`, and `probe`.

```bash
uv run python tools/query_state_courts.py search EPSTEIN \
    --source us-ct-superior-court-civil-family-case-lookup \
    --output "$WORKDIR/ct-party-search.json"
uv run python tools/query_state_courts.py case FBT-CV-26-6159214-S \
    --source us-ct-superior-court-civil-family-case-lookup --ingest \
    --output "$WORKDIR/ct-case.json"
uv run python tools/query_state_courts.py documents FBT-CV-26-6159214-S \
    --source us-ct-superior-court-civil-family-case-lookup \
    --output "$WORKDIR/ct-document-metadata.json"
uv run python tools/query_state_courts.py download 32503295 \
    --source us-ct-superior-court-civil-family-case-lookup \
    --destination "$WORKDIR/ct-document.pdf" \
    --output "$WORKDIR/ct-document-download.json"
uv run python tools/query_state_courts.py download 32503295 \
    --source us-ct-superior-court-civil-family-case-lookup \
    --case-number FBT-CV-26-6159214-S --ingest \
    --destination "$WORKDIR/ct-verified-document.pdf" \
    --output "$WORKDIR/ct-verified-document.json"
```

Party search returns the source's fixed 50-row display as `partial` with
`source_display_slice`. Omitted caller limits retain the whole display. An
explicit limit may use a query- and snapshot-bound adapter cursor within the
same reacquired display, but the cursor does not traverse a publisher page or
imply records beyond row 50. Same-name rows remain unresolved discovery
candidates.

Exact docket ingestion preserves publisher party numbers, roles, appearance
records, `DocumentNo`, docket entries, scheduled events, transfer history,
and notices. Case-detail filing links are metadata only. A downloaded PDF is
projected as an artifact only after byte-level validation; `--case-number` is
optional for retrieval and supplies both membership verification and the
durable case relationship when present. The paid Civil/Family bulk feed is a
same-publisher field-matched complement without electronic documents, and
clerk offices supply the human request/copy route.

### New Mexico Judiciary Case Lookup shared adapter

`query_new_mexico_case_lookup.py` covers targeted first-page party discovery
and one caller-selected exact case in the official anonymous statewide
metadata application.

```bash
uv run python tools/query_state_courts.py search "Epstein Jeffrey" \
    --source us-nm-judiciary-case-lookup \
    --output "$WORKDIR/nm-party-search.json"
uv run python tools/query_state_courts.py case D-101-CV-199602449 \
    --source us-nm-judiciary-case-lookup --ingest \
    --output "$WORKDIR/nm-case.json"
uv run python tools/query_state_courts.py docket D-101-CV-199602449 \
    --source us-nm-judiciary-case-lookup \
    --output "$WORKDIR/nm-docket.json"
uv run python tools/query_state_courts.py claims D-101-CV-199602449 \
    --source us-nm-judiciary-case-lookup \
    --output "$WORKDIR/nm-causes.json"
uv run python tools/public_records_monitor.py run \
    us-nm-judiciary-case-lookup \
    --output "$WORKDIR/nm-monitor.json"
```

The exact page preserves parties and counsel, complaint/cause/disposition
fields, register continuation text, current judge, and judge history. The
published full case number and derived court code are the case identity;
Tapestry session, CSRF, and component locators are transport state. Child
records without source-native IDs use published field tuples plus an ordinal
only among identical tuples.

Case Lookup publishes metadata, not filed documents. re:SearchNM, judiciary
public-records requests, and individual clerks are the field-matched
complements. The four-request monitor exercises the exact historical-case
lifecycle without requesting documents or retaining session values. See
`docs/sources/new-mexico-case-lookup.md`.

### Palm Beach County eCaseView browser adapter

`query_palm_beach_courts.py` uses a local headed Playwright/Chrome session for
the Clerk's public guest UI, then emits the shared court envelope. Node,
Playwright, and Chrome can be checked without opening the source:

```bash
uv run python tools/query_palm_beach_courts.py runtime-check \
    --output "$WORKDIR/palm-beach-runtime.json"
uv run python tools/query_palm_beach_courts.py probe \
    --output "$WORKDIR/palm-beach-probe.json"

uv run python tools/query_palm_beach_courts.py search KRAFT \
    --output "$WORKDIR/palm-beach-search.json"
uv run python tools/query_palm_beach_courts.py search \
    50-2019-MM-002346-AXXX-NB --search-scope case-number \
    --output "$WORKDIR/palm-beach-case-search.json"
uv run python tools/query_palm_beach_courts.py case \
    50-2019-MM-002346-AXXX-NB \
    --output "$WORKDIR/palm-beach-case.json"
uv run python tools/query_palm_beach_courts.py docket \
    50-2019-MM-002346-AXXX-NB --limit 100 \
    --output "$WORKDIR/palm-beach-docket.json"
uv run python tools/query_palm_beach_courts.py documents \
    50-2019-MM-002346-AXXX-NB \
    --output "$WORKDIR/palm-beach-documents.json"
uv run python tools/query_palm_beach_courts.py download \
    50-2019-MM-002346-AXXX-NB 5 "$WORKDIR/palm-beach-din-5.pdf" \
    --output "$WORKDIR/palm-beach-din-5.json"

uv run python tools/query_state_courts.py case \
    50-2019-MM-002346-AXXX-NB \
    --source us-fl-palm-beach-ecaseview --timeout 300 --ingest \
    --output "$WORKDIR/palm-beach-unified-case.json"
```

The full UCN identifies a case and UCN plus DIN identifies a docket/document
row. The source's 200-match broad-search ceiling becomes an explicit `partial`
result; caller limits page only across rows actually returned. Docket metadata
and image access are modeled separately, including public, View on Request,
in-process, and unavailable-online states.

Complementary catalog routes include ClerkCart compiled reports, Clerk Records
Service copy/certification requests, Florida ACIS/Fourth DCA appellate records,
Fifteenth Circuit division notices, and Palm Beach Official Records for deeds,
mortgages, judgments, liens, and recorded-document images.

### Palm Beach County Property Appraiser GIS adapter

`query_palm_beach_property_appraiser.py` queries the anonymous official
`PARCEL_DETAILS` FeatureServer layer for parcel-number, PARID, owner, address,
sale, legal, land-use, subdivision, point, bounding-box, count, and polygon
results.

```bash
uv run python tools/query_palm_beach_property_appraiser.py parcel \
    04364325000005040 --geometry \
    --output "$WORKDIR/pbc-parcel.json"
uv run python tools/query_palm_beach_property_appraiser.py owner SMITH \
    --limit 100 --output "$WORKDIR/pbc-owner.json"
uv run python tools/query_palm_beach_property_appraiser.py sale 5021/1011 \
    --field book-page --output "$WORKDIR/pbc-sale.json"
uv run python tools/query_palm_beach_property_appraiser.py discovery \
    --output "$WORKDIR/pbc-property-source.json"
uv run python tools/query_palm_beach_property_appraiser.py probe \
    --output "$WORKDIR/pbc-property-probe.json"

uv run python tools/query_property.py parcel 04364325000005040 \
    --source us-fl-palm-beach-property-appraiser --jurisdiction 12099 \
    --geometry --ingest --output "$WORKDIR/pbc-unified-parcel.json"
uv run python tools/public_records_monitor.py run \
    us-fl-palm-beach-property-appraiser \
    --output "$WORKDIR/pbc-property-monitor.json"
```

`OBJECTID` is the feature-occurrence identity. `PARCEL_NUMBER` is a candidate
exact county parcel/account join whose uniqueness is not assumed; `PARID`
remains a separate published geometry/group identifier. Omitted limits
traverse the complete maximum-OBJECTID-bounded population, while bounded
queries return criteria/schema/snapshot-bound cursors.

Owner and last-sale fields are assessment-layer observations. Book/page is a
Clerk pivot, not an instrument copy. The adapter preserves `CONFID_FLG`, blank
owner/address values, and repeated parcel-number occurrences. QSALES is a
same-publisher thematic representation rather than separate corroboration.
The advertised flat-file cloud invitation's consent discrepancy applies to
that transfer path, not to the anonymous GIS or the Florida DOR bulk
complement.

### Palm Beach County Tax Collector adapter

`query_palm_beach_tax_collector.py` queries the Constitutional Tax Collector's
official Aumentum PublicAccessNow tenant for account discovery, exact account
state, bill/installment snapshots, payment history, bill-detail links, and
account-refresh routing.

```bash
uv run python tools/query_palm_beach_tax_collector.py settings \
    --output "$WORKDIR/pbc-tax-settings.json"
uv run python tools/query_palm_beach_tax_collector.py owner SMITH \
    --limit 100 --output "$WORKDIR/pbc-tax-owner.json"
uv run python tools/query_palm_beach_tax_collector.py parcel \
    04-36-43-25-00-000-5040 \
    --output "$WORKDIR/pbc-tax-pcn.json"
uv run python tools/query_palm_beach_tax_collector.py account \
    04364325000005040 --alternate-key 1081671 \
    --output "$WORKDIR/pbc-tax-account.json"
uv run python tools/query_palm_beach_tax_collector.py bills \
    04364325000005040 --alternate-key 1081671 --tax-year 2018 \
    --output "$WORKDIR/pbc-tax-bills.json"
uv run python tools/query_palm_beach_tax_collector.py payments \
    04364325000005040 --alternate-key 1081671 --tax-year 2024 \
    --output "$WORKDIR/pbc-tax-payments.json"
uv run python tools/query_palm_beach_tax_collector.py bill-detail \
    04364325000005040 770001 --alternate-key 1081671 \
    --tax-year 2018 --bill-number 2018-009991 \
    --output "$WORKDIR/pbc-tax-bill-detail.json"
uv run python tools/query_palm_beach_tax_collector.py sync-status \
    --output "$WORKDIR/pbc-tax-refresh-contract.json"
uv run python tools/query_palm_beach_tax_collector.py discovery \
    --output "$WORKDIR/pbc-tax-routes.json"
uv run python tools/query_palm_beach_tax_collector.py probe \
    --output "$WORKDIR/pbc-tax-probe.json"

uv run python tools/query_property.py account 04364325000005040 \
    --source us-fl-palm-beach-tax-collector --jurisdiction 12099 \
    --ingest --output "$WORKDIR/pbc-tax-unified-account.json"
uv run python tools/query_property.py event 04364325000005040 \
    --source us-fl-palm-beach-tax-collector \
    --search-field payment-history --tax-year 2024 --ingest \
    --output "$WORKDIR/pbc-tax-unified-payments.json"
uv run python tools/public_records_monitor.py run \
    us-fl-palm-beach-tax-collector \
    --output "$WORKDIR/pbc-tax-monitor.json"
```

QuickSearch publishes the `AUMENTUMTAX`/`QuickSearch` configuration, ten rows
per page, and `maximumRecords=300`. The 300 boundary is a completeness signal:
a reported total at that value produces `partial`; it is not an adapter cap or
an authoritative population count. Omitting a caller limit traverses the
publisher-returned window, while bounded calls use criteria-, settings-,
total-, and offset-bound cursors. Shared `--limit` and `--max-records` values
remain caller-selected return bounds rather than source-access settings.

PCN is the reversible 17-digit parcel join. `AlternateKey` locates the Tax
Collector account, while bill ID, bill number, installment, receipt number,
and payment occurrence retain separate identities. Account owner labels are
tax-account observations, and a payment-history payer is not projected as an
owner or title holder. Confidential flags and publisher masking remain
unchanged.

Balances, delinquency/paid labels, source messages, online-payment capability,
and source freshness are retrieved-state observations. Due dates remain bill
dates; effective payment dates become payment-event dates. The ingester
preserves every normalized record, projecting only exact account snapshots,
bill/installment states, and payments.

Account summary modules 462/465, bill module 652, and payment-history module
663 are verified for this tenant. Bill-detail modules are discovered from the
page. The module-461 sync-status response is settings/routing metadata, not a
per-account completion poll; `FetchData` is the separate one-shot refresh.
The Property Appraiser/Florida DOR roll, Official Records, and Tax Deeds
adapters provide field-matched assessment/geometry, title/document, and
certificate/case/auction complements.

### Palm Beach County Tax Deeds adapter

`query_palm_beach_tax_deeds.py` searches the Clerk's anonymous native form and
session-backed jqGrid by certificate, case, PCN, Tax Collector number,
applicant, source-reported owner label, lifecycle status, published sale date,
or Lands Available. It also retrieves exact case details, complete document
inventories, and listed public PDFs.

```bash
uv run python tools/query_palm_beach_tax_deeds.py discovery \
    --output "$WORKDIR/pbc-tax-deed-discovery.json"
uv run python tools/query_palm_beach_tax_deeds.py parcel \
    04-36-43-25-00-000-5040 \
    --output "$WORKDIR/pbc-tax-deed-pcn.json"
uv run python tools/query_palm_beach_tax_deeds.py owner PRIEST \
    --from-date 2023-01-01 --to-date 2024-12-31 \
    --output "$WORKDIR/pbc-tax-deed-owner.json"
uv run python tools/query_palm_beach_tax_deeds.py status "LANDS AVAILABLE" \
    --from-date 2023-01-01 --to-date 2026-12-31 \
    --output "$WORKDIR/pbc-tax-deed-status.json"
uv run python tools/query_palm_beach_tax_deeds.py lands-available \
    --output "$WORKDIR/pbc-lands-available.json"
uv run python tools/query_palm_beach_tax_deeds.py detail 43079 \
    --output "$WORKDIR/pbc-tax-deed-43079.json"
uv run python tools/query_palm_beach_tax_deeds.py document 43079 24748216 \
    --document-output "$WORKDIR/pbc-tax-certificate-24748216.pdf" \
    --output "$WORKDIR/pbc-tax-certificate-24748216.json"
uv run python tools/query_palm_beach_tax_deeds.py routes \
    --output "$WORKDIR/pbc-tax-deed-routes.json"
uv run python tools/query_palm_beach_tax_deeds.py probe \
    --output "$WORKDIR/pbc-tax-deed-probe.json"

uv run python tools/query_property.py parcel 04-36-43-25-00-000-5040 \
    --source us-fl-palm-beach-tax-deeds --jurisdiction 12099 --ingest \
    --output "$WORKDIR/pbc-tax-deed-unified-pcn.json"
uv run python tools/query_property.py event 43079 \
    --source us-fl-palm-beach-tax-deeds --ingest \
    --output "$WORKDIR/pbc-tax-deed-unified-detail.json"
uv run python tools/query_property.py download 43079:24748216 \
    --source us-fl-palm-beach-tax-deeds \
    --destination "$WORKDIR/pbc-tax-certificate-shared.pdf" --ingest \
    --output "$WORKDIR/pbc-tax-certificate-shared.json"
uv run python tools/public_records_monitor.py run \
    us-fl-palm-beach-tax-deeds \
    --output "$WORKDIR/pbc-tax-deed-monitor.json"
```

Omitting `--limit` exhausts the source-reported jqGrid pages. Bounded results
use continuations tied to the submitted criteria, schema, native page size,
reported totals, and first-page occurrence snapshot. Sale-date choices and
their range are discovered live.

Portal row ID, case number, certificate number, PCN, auction event, document
occurrence, and image ID retain distinct roles. Lifecycle status and
source-reported parties do not become title conclusions. Exact detail retains
both available documents and explicit `Image Not Available` rows. Download
validates that an image belongs to the selected case and is a PDF; certified
copies use the Clerk's separate ordering route. Property Appraiser, Tax
Collector, Official Records, eCaseView, legal notices, and certified-copy
service remain separately attributable complements.

### Palm Beach County Official Records adapter

`query_palm_beach_official_records.py` uses the Clerk's deterministic
instrument-number and book/page routes after the normal public
acknowledgement. It returns official instrument metadata, indexed parties,
PCNs, legal descriptions, consideration, and per-record image availability.
The official instrument number is the record identity; the Landmark document
ID and page ID remain source locators.

```bash
uv run python tools/query_palm_beach_official_records.py instrument \
    19860255822 --output "$WORKDIR/pbc-instrument.json"
uv run python tools/query_palm_beach_official_records.py book-page \
    5021 1011 --output "$WORKDIR/pbc-book-page.json"
uv run python tools/query_palm_beach_official_records.py image \
    --instrument 19860255822 --image-page 1 \
    --document-output "$WORKDIR/pbc-page-1.png" \
    --output "$WORKDIR/pbc-page-1.json"
uv run python tools/query_palm_beach_official_records.py routes \
    --output "$WORKDIR/pbc-recorder-routes.json"

uv run python tools/query_property.py instrument 19860255822 \
    --source us-fl-palm-beach-official-records --jurisdiction 12099 \
    --ingest --output "$WORKDIR/pbc-unified-instrument.json"
uv run python tools/query_property.py instrument 5021/1011 \
    --search-field book-page \
    --source us-fl-palm-beach-official-records --ingest \
    --output "$WORKDIR/pbc-unified-book-page.json"
uv run python tools/public_records_monitor.py run \
    us-fl-palm-beach-official-records \
    --output "$WORKDIR/pbc-recorder-monitor.json"
```

Broad party, parcel, legal, case, and date discovery remains a distinct
interactive portal operation where reCAPTCHA was observed. The `routes`
command inventories the separately attributable daily index, historical
index/image archive, Records Service, Property Appraiser, Florida DOR, Tax
Collector, Tax Deeds, and eCaseView alternatives.

```bash
uv run python tools/public_records_actions.py plan \
    us-fl-palm-beach-clerkcart --operation request_case_report \
    --selector 50-2019-MM-002346-AXXX-NB
uv run python tools/public_records_actions.py plan \
    us-fl-palm-beach-records-service --operation request_case_copy \
    --selector 50-2019-MM-002346-AXXX-NB
```

### Broward County Official Records adapter

`query_broward_official_records.py` keeps the AcclaimWeb search session, its
session-issued public PDF, the County's ten-day verified bulk release, and
older-record copy/certification service as distinct routes. Instrument number
is the shared identity across portal and bulk observations.

```bash
uv run python tools/query_broward_official_records.py runtime-check \
    --output "$WORKDIR/broward-runtime.json"
uv run python tools/query_broward_official_records.py probe \
    --output "$WORKDIR/broward-probe.json"
uv run python tools/query_broward_official_records.py name \
    "EPSTEIN, JEFFREY" --from-date 1977-01-01 \
    --output "$WORKDIR/broward-name.json"
uv run python tools/query_broward_official_records.py parcel \
    514223CB0580 --from-date 1977-01-01 \
    --output "$WORKDIR/broward-parcel.json"
uv run python tools/query_broward_official_records.py detail 114957232 \
    --output "$WORKDIR/broward-detail.json"
uv run python tools/query_broward_official_records.py download \
    114957232 "$WORKDIR/114957232.pdf" \
    --output "$WORKDIR/broward-pdf.json"
uv run python tools/query_broward_official_records.py routes \
    --output "$WORKDIR/broward-routes.json"

uv run python tools/query_property.py instrument 114957232 \
    --source us-fl-broward-official-records --jurisdiction 12011 \
    --ingest --output "$WORKDIR/broward-shared-instrument.json"
uv run python tools/public_records_monitor.py run \
    us-fl-broward-official-records \
    --output "$WORKDIR/broward-monitor.json"
```

The direct `bulk` command accepts downloaded DOC, NME, LNK, LGL, RNG, and IMG
files, verifies their layouts, and joins them by instrument number. Portal
party and parcel searches are shared-query operations; `download`, `bulk`,
`routes`, and `runtime-check` remain direct adapter operations.

### U.S. Virgin Islands Recorder of Deeds adapter

`query_usvi_recorder.py` follows the anonymous CountyFusion guest flow linked
by the Office of the Lieutenant Governor. Native name, date/type, document
number, book/page, and legal-field searches exhaust all source-reported pages
before an optional caller window. Stable instrument identity is
`district + instId`; instrument number and book/page remain lookup keys.

```bash
uv run python tools/query_usvi_recorder.py search "SMITH" \
    --district "ST THOMAS" --output "$WORKDIR/usvi-recorder-search.json"
uv run python tools/query_usvi_recorder.py document 2026000625 \
    --district "ST THOMAS" --inst-id 903442 \
    --output "$WORKDIR/usvi-recorder-detail.json"
uv run python tools/query_usvi_recorder.py page 2026000625 1 \
    --district "ST THOMAS" --inst-id 903442 \
    "$WORKDIR/usvi-recorder-page-1.png" \
    --output "$WORKDIR/usvi-recorder-page.json"

uv run python tools/query_property.py instrument 2026000625 \
    --source us-vi-recorder-of-deeds-countyfusion \
    --jurisdiction 78 --district "ST THOMAS" --inst-id 903442 \
    --ingest --output "$WORKDIR/usvi-recorder-shared.json"
uv run python tools/query_property.py download 2026000625 \
    --source us-vi-recorder-of-deeds-countyfusion \
    --jurisdiction 78 --district "ST THOMAS" --inst-id 903442 \
    --page-number 1 --destination "$WORKDIR/usvi-recorder-page-1.png" \
    --ingest --output "$WORKDIR/usvi-recorder-page-shared.json"
uv run python tools/public_records_monitor.py run \
    us-vi-recorder-of-deeds-countyfusion \
    --output "$WORKDIR/usvi-recorder-monitor.json"
```

The fixed monitor verifies an exact detail record without fetching an image.
Normalized Party 1/Party 2 and legal-description fields remain instrument-index
metadata and do not become current ownership assertions. Retrieved PNGs use the
rights label `official_host_reference_image_uncertified`: the Recorder-hosted
page is reference material, a nested representation of the instrument, and not
independent corroboration. The modern `usvi.publicsearch.us` route is another
interface from the same recorder authority; Capture CAMA is the separate
assessment/tax complement.

### U.S. Virgin Islands Capture CAMA property-tax adapter

`query_usvi_property_tax.py` searches the anonymous territorial assessment and
property-tax portal by owner, formatted parcel, address, legal description,
and tax year. It exhausts native WebForms result pages before applying an
explicit caller window. Exact record identity is formatted parcel plus tax
year; `ParcelId` is retained only as the locator for that version.

```bash
uv run python tools/query_usvi_property_tax.py search legal "ST JAMES" \
    --tax-year 2026 --output "$WORKDIR/usvi-cama-legal.json"
uv run python tools/query_usvi_property_tax.py parcel 1-09801-0101-00 \
    --tax-year 2026 --output "$WORKDIR/usvi-cama-parcel.json"
uv run python tools/query_usvi_property_tax.py artifact 1-09801-0101-00 \
    --tax-year 2026 --kind receipt --transaction-id 1786629 \
    --destination "$WORKDIR/usvi-cama-receipt.html" \
    --output "$WORKDIR/usvi-cama-receipt.json"

uv run python tools/query_property.py owner "SMITH" \
    --source us-vi-property-tax-capture-cama \
    --jurisdiction 78 --tax-year 2026 \
    --output "$WORKDIR/usvi-cama-shared-owner.json"
uv run python tools/query_property.py parcel 1-09801-0101-00 \
    --source us-vi-property-tax-capture-cama \
    --tax-year 2026 --ingest \
    --output "$WORKDIR/usvi-cama-shared-parcel.json"
uv run python tools/query_property.py download 1-09801-0101-00 \
    --source us-vi-property-tax-capture-cama \
    --tax-year 2026 --artifact-kind property-card \
    --destination "$WORKDIR/usvi-cama-property-card.html" --ingest \
    --output "$WORKDIR/usvi-cama-shared-card.json"
uv run python tools/public_records_monitor.py run \
    us-vi-property-tax-capture-cama \
    --output "$WORKDIR/usvi-cama-monitor.json"
```

The shared ingester projects tax-year parcel snapshots, assessment-roll owner
and address observations, valuation history, statement/balance/payment tax
events, and actually retrieved printable HTML. The owner assertion remains
explicitly assessment-roll evidence; payer labels and assessor sales do not
become owners, recorded instruments, or title events.

The fixed five-request monitor fetches the search, exact parcel, detail shell,
navigation, and valuation component only. Route/identity/paging/schema hashes
are separated from rolling owner, value, balance, locator, and child-count
observations. The Office of the Tax Collector and Recorder of Deeds are
separately attributable complements. `usvi.capturecama.com` is the same tenant
on an alternate hostname and is not independent evidence.

### Virgin Islands C-Track and legacy-file adapter

`query_vicourts.py` uses the official anonymous C-Track backend for the Virgin
Islands Supreme and Superior Courts and a separate exact numeric
`DisplayFile.aspx` route for legacy PDFs.

```bash
# Live court directory; --court accepts external ID, current UUID, or name
uv run python tools/query_vicourts.py courts \
    --output "$WORKDIR/vicourts-courts.json"

# Unified case-number, title, and party search
uv run python tools/query_vicourts.py search ST-19-PB-80 \
    --field number --match-mode exact \
    --output "$WORKDIR/vicourts-number-search.json"
uv run python tools/query_vicourts.py search "Estate of Epstein" \
    --field title --match-mode contains \
    --output "$WORKDIR/vicourts-title-search.json"
uv run python tools/query_vicourts.py search Epstein \
    --field party --match-mode match \
    --output "$WORKDIR/vicourts-party-search.json"

# Exact case, docket, limited claims, and documents for one docket entry
uv run python tools/query_vicourts.py case ST-19-PB-80 \
    --output "$WORKDIR/vicourts-case.json"
uv run python tools/query_vicourts.py docket ST-19-PB-80 \
    --output "$WORKDIR/vicourts-docket.json"
uv run python tools/query_vicourts.py claims ST-19-PB-80 \
    --output "$WORKDIR/vicourts-claims.json"
uv run python tools/query_vicourts.py documents ST-19-PB-80 \
    "<DOCKET_ENTRY_UUID>" --output "$WORKDIR/vicourts-documents.json"

# Shared live router plus normalized claim/document projection
uv run python tools/query_state_courts.py claims ST-19-PB-80 \
    --source us-vi-c-track --ingest \
    --output "$WORKDIR/vicourts-claims-ingested.json"
uv run python tools/query_state_courts.py documents ST-19-PB-80 \
    --source us-vi-c-track --docket-entry-uuid "<DOCKET_ENTRY_UUID>" \
    --ingest --output "$WORKDIR/vicourts-documents-ingested.json"
uv run python tools/query_state_courts.py claims ST-2019-PB-00080 \
    --output "$WORKDIR/vicourts-local-claims.json"

# OCR document criteria: any combination of exact, any, all, and none
uv run python tools/query_vicourts.py document-search \
    --exact "quarterly accounting" --any "estate probate" \
    --all "executor report" --none "sample" \
    --output "$WORKDIR/vicourts-document-search.json"

# C-Track publications and selected PDF retrieval
uv run python tools/query_vicourts.py publications \
    --publication-number PB-2026-00032 \
    --output "$WORKDIR/vicourts-publications.json"
uv run python tools/query_vicourts.py publication 1 \
    "<PUBLICATION_UUID>" --output "$WORKDIR/vicourts-publication.json"
uv run python tools/query_vicourts.py download 1 \
    "<CASE_INSTANCE_UUID>" "<DOCUMENT_LINK_UUID>" \
    "$WORKDIR/vicourts-document.pdf" \
    --output "$WORKDIR/vicourts-download.json"

# Exact legacy itemId retrieval, direct probe, and catalog monitor
uv run python tools/query_vicourts.py legacy-file 16911884 \
    "$WORKDIR/vicourts-legacy-16911884.pdf" \
    --output "$WORKDIR/vicourts-legacy-16911884.json"
uv run python tools/query_vicourts.py probe \
    --output "$WORKDIR/vicourts-probe.json"
uv run python tools/public_records_monitor.py run us-vi-c-track \
    --output "$WORKDIR/vicourts-monitor.json"
```

The adapter resolves the external C-Track court ID through `/courts` on each
new client rather than pinning a resource UUID. It normalizes legacy case
numbers (`ST-19-PB-80` becomes `ST-2019-PB-00080`) before exact resolution.
Spring pages are zero-based with a verified maximum size of 500. There is no
default aggregate ceiling: caller limits return `ok` plus `next_cursor`, while
a reported total of 10,000 returns `partial`/`source_overflow` and requires
narrower criteria.

The claims route supplies only type, date, and sequence stubs; creditor names
and amounts were not verified. Normalized claim rows retain their native
identity and nullable claimant, amount, currency, status, and source-access
fields. Docket rows are retained even when a secured entry's document-access
query returns zero rows.

C-Track identities use `CTRACK_COURT:<uuid>`, `CTRACK_CASE:<uuid>`,
`CTRACK_DOCKET:<uuid>`, `CTRACK_CLAIM:<uuid-or-sequence>`,
`CTRACK_DOCUMENT:<uuid>`, and `CTRACK_PUBLICATION:<uuid>`. Legacy identities
use `VICOURTS_ITEM:<itemId>` and `backend=legacy_displayfile`. The observed
96-file legacy publication container is separate from the live 452-entry
probate docket for `ST-2019-PB-00080`; it is neither a docket enumeration nor a
docket-completeness measure. Cross-backend records may be deduplicated only
when validated downloaded PDF SHA-256 values match.

### Texas TAMES appellate adapter and complementary routes

`query_texas_appellate.py` provides anonymous statewide appellate discovery,
case detail, parties and attorneys, docket events, calendar settings,
originating-trial-case pivots, and public PDFs for the Supreme Court, Court of
Criminal Appeals, and fifteen Courts of Appeals.

```bash
# Case-style, trial-case, exact/partial case-number, or attorney discovery
uv run python tools/query_texas_appellate.py search "Tesla" --limit 25 \
    --output "$WORKDIR/texas-appellate-style.json"
uv run python tools/query_texas_appellate.py search D-1-GN-24-008508 \
    --scope trial-case-number --county Travis \
    --output "$WORKDIR/texas-appellate-trial-pivot.json"
uv run python tools/query_texas_appellate.py search "Example Counsel" \
    --scope attorney --court coa03 \
    --output "$WORKDIR/texas-appellate-attorney.json"

# Exact case sections and one selected public PDF
uv run python tools/query_texas_appellate.py case 03-25-00287-CV \
    --output "$WORKDIR/texas-appellate-case.json"
uv run python tools/query_texas_appellate.py docket 03-25-00287-CV \
    --output "$WORKDIR/texas-appellate-docket.json"
uv run python tools/query_texas_appellate.py documents 03-25-00287-CV \
    --output "$WORKDIR/texas-appellate-documents.json"
uv run python tools/query_texas_appellate.py download \
    03-25-00287-CV "<MEDIA_VERSION_ID>" \
    "$WORKDIR/texas-appellate-document.pdf" \
    --output "$WORKDIR/texas-appellate-download.json"

# Unified router, ingestion, direct probe, and catalog monitor
uv run python tools/query_state_courts.py search "Tesla" \
    --source us-tx-appellate-tames --court-id tx-appellate-coa03 \
    --after 2025-01-01 --limit 25 --ingest \
    --output "$WORKDIR/texas-appellate-unified.json"
uv run python tools/query_texas_appellate.py probe \
    --output "$WORKDIR/texas-appellate-probe.json"
uv run python tools/public_records_monitor.py run us-tx-appellate-tames \
    --output "$WORKDIR/texas-appellate-monitor.json"
```

Search supports `--scope style|case-number|partial-case-number|
trial-case-number|attorney`, repeatable `--court`, `--case-type`,
`--date-from`, `--date-to`, `--originating-coa`, `--county`,
`--trial-court`, `--exclude-inactive`, `--limit`, and `--cursor`. TAMES'
reported 1,000-result broad-search ceiling returns a `partial` envelope and
continuation cursor; there is no separate adapter aggregate ceiling.
Single-result redirects are accepted as one-row searches.

Normalized ingestion creates a distinct originating trial-case stub and
trial-to-appellate `appealed_to` relationship. Trial judge data stays on the
trial court, calendar settings project as case events, and source-native
calendar and reporter values remain in provenance.

`query_texas_supreme_publications.py` is the executable official-publication
complement. It parses release rows structurally from `#oReportDiv`, retaining
the native Supreme docket, release occurrence, section/action headings, raw
case and disposition/participation text, and lower-court locator candidates.
It does not depend on the pages' generated CSS classes.

```bash
# Source/coverage inventory and all dates on selected annual pages
uv run python tools/query_texas_supreme_publications.py source \
    --output "$WORKDIR/texas-supreme-source.json"
uv run python tools/query_texas_supreme_publications.py years \
    --output "$WORKDIR/texas-supreme-years.json"
uv run python tools/query_texas_supreme_publications.py releases --year 2026 \
    --output "$WORKDIR/texas-supreme-2026-releases.json"

# Exact release, scoped search, PDF transfer, and contract monitor
uv run python tools/query_texas_supreme_publications.py release 2026-05-29 \
    --output "$WORKDIR/texas-supreme-release.json"
uv run python tools/query_texas_supreme_publications.py search "24-0205" \
    --case-number 24-0205 --year 2026 \
    --output "$WORKDIR/texas-supreme-case.json"
uv run python tools/query_texas_supreme_publications.py download \
    "https://www.txcourts.gov/media/<MEDIA_ID>/<FILE>.pdf" \
    "$WORKDIR/texas-supreme-document.pdf" \
    --output "$WORKDIR/texas-supreme-download.json"
uv run python tools/query_state_courts.py search "Huffman" \
    --source us-tx-supreme-orders-opinions \
    --after 2026-01-01 --before 2026-12-31 --ingest \
    --output "$WORKDIR/texas-supreme-unified.json"
uv run python tools/public_records_monitor.py run \
    us-tx-supreme-orders-opinions \
    --output "$WORKDIR/texas-supreme-monitor.json"
```

Document types distinguish the print-order release, editorial summary, court
opinion, per curiam opinion, concurrence, dissent, May 2020 outage documents,
pre-October-2014 archive, and fiscal-year order/opinion aggregates. Omitted
limits exhaust the selected annual/date page set; bounded results use a cursor
bound to both the query and source-reported release set.

Complementary Texas source IDs:

| Source | Contribution |
|---|---|
| `us-tx-appellate-released-orders-opinions` | Release dates, case styles, dispositions, judges, and public orders/opinions |
| `us-tx-supreme-orders-opinions` | Implemented hand-down text, release occurrences, summaries, independent PDFs, outage files, and archives |
| `us-tx-researchtx` | Account-based trial case, filing, text, hearing, export, and document-purchase actions |
| `us-tx-travis-odyssey-courts` | Free Travis digital case/document route |
| `us-tx-travis-criminal-docket-search` | Future settings and sorted docket PDFs |
| `us-tx-travis-district-clerk-records-request` | Official/certified/authenticated copies, data, and subscriptions |
| `us-tx-hays-district-court-portal` | Free civil/criminal party and cause discovery |
| `us-tx-hays-county-clerk-courts` | County-court criminal, civil, probate, guardianship, calendar, jail, and bond pivots |
| `us-tx-hays-district-clerk-records-request` | Clerk name searches and copy/certification actions |
| `us-tx-oca-citations-notices` | Public notice text plus name, cause, court, county, and status pivots |
| `us-tx-oca-vexatious-litigants` | HTML/Excel litigant and cause index with linked prefiling orders |
| `us-tx-oca-local-rules-standing-orders` | Searchable procedural documents |
| `us-tx-oca-court-activity` | Monthly aggregate filed/disposed statistics from September 1992 |
| `us-tx-oca-statistical-supplements` | Annual downloadable judge and court-activity files |

OCA court-activity and statistical-supplement records belong in an aggregate
analytics store, not the individual-case sidecar. Account and clerk routes can
be planned without adding source-specific action code:

```bash
uv run python tools/public_records_actions.py plan us-tx-researchtx \
    --operation search_hearings --selector "<PARTY OR CASE>" \
    --output "$WORKDIR/researchtx-hearing-plan.json"
uv run python tools/public_records_actions.py plan \
    us-tx-travis-district-clerk-records-request \
    --operation request_case_copy --selector "<CASE NUMBER>" \
    --output "$WORKDIR/travis-copy-plan.json"
```

### Bexar County historical-court adapter and current routes

`query_bexar_courts.py` queries the Bexar County District Clerk Historical
Cases archive through its anonymous Kofile Neumo PublicSearch session. The
source provides offset-paginated index and OCR searches, exact case-file
detail, and individual page images.

```bash
# Indexed and OCR searches
uv run python tools/query_bexar_courts.py search "SMITH" --limit 50 \
    --output "$WORKDIR/bexar-historical-index.json"
uv run python tools/query_bexar_courts.py search "jury verdict" --ocr \
    --date-from 1900-01-01 --date-to 1919-09-17 \
    --output "$WORKDIR/bexar-historical-ocr.json"

# Date-only search omits the optional query
uv run python tools/query_bexar_courts.py search \
    --date-from 1919-01-01 --date-to 1919-12-31 \
    --offset 0 --output "$WORKDIR/bexar-historical-1919.json"

# Exact detail, selected page image, and source probe
uv run python tools/query_bexar_courts.py case "<DOC_ID>" \
    --output "$WORKDIR/bexar-historical-case.json"
uv run python tools/query_bexar_courts.py page "<DOC_ID>" 1 \
    "$WORKDIR/bexar-historical-page-1.png" \
    --output "$WORKDIR/bexar-historical-page-1.json"
uv run python tools/query_bexar_courts.py probe \
    --output "$WORKDIR/bexar-historical-probe.json"
```

The verified archive census contained 13,965 records through an observed
index date of 1919-09-17. The raw `1/1/1800` value is retained as an
unknown-date sentinel. Historical case detail is not a synthesized docket,
and page images are uncertified source artifacts.

The related catalog routes are deliberately separate:

- `us-tx-bexar-justice-portal` is the current Tyler interactive case-metadata
  and hearing route. Its guide states a 200-result display ceiling; CAPTCHA
  was observed, and the verified public route exposed no document images.
- `us-tx-bexar-district-clerk-records-request` covers District Clerk civil
  district and felony criminal data/copy requests.
- `us-tx-bexar-county-clerk-records-request` covers County Clerk
  county-court-at-law, misdemeanor, and probate data/copy requests.

Create request plans without merging the two custodians:

```bash
uv run python tools/public_records_actions.py plan \
    us-tx-bexar-district-clerk-records-request \
    --operation request_case_copy --selector "<DISTRICT_CASE_NUMBER>" \
    --output "$WORKDIR/bexar-district-copy-plan.json"
uv run python tools/public_records_actions.py plan \
    us-tx-bexar-county-clerk-records-request \
    --operation request_court_data --selector "probate cases" \
    --output "$WORKDIR/bexar-county-data-plan.json"
```

### D.C. Court of Appeals opinions and MOJs

```bash
# Direct list traversal is exhaustive by default.
uv run python tools/query_dc_opinions.py list \
    --query "24-BG-1045" --type opinions \
    --output "$WORKDIR/dc-opinions.json"
uv run python tools/query_dc_opinions.py list \
    --type mojs --date-from 2026-07-01 --date-to 2026-07-31 \
    --output "$WORKDIR/dc-mojs.json"

# One source-native page is an explicit bounded selection.
uv run python tools/query_dc_opinions.py list \
    --type all --page 7 --page-only \
    --output "$WORKDIR/dc-opinions-page-7.json"

# The shared router returns one 10-row native page and a page:N continuation.
uv run python tools/query_state_courts.py search "24-BG-1045" \
    --source us-dc-court-of-appeals-opinions-mojs --jurisdiction 11 \
    --case-type opinions --ingest \
    --output "$WORKDIR/dc-opinions-unified.json"
uv run python tools/query_state_courts.py documents "24-BG-1045" \
    --source us-dc-court-of-appeals-opinions-mojs \
    --document-type appellate_opinion \
    --output "$WORKDIR/dc-opinion-documents.json"

uv run python tools/query_dc_opinions.py probe \
    --output "$WORKDIR/dc-opinions-probe.json"
uv run python tools/public_records_monitor.py run \
    us-dc-court-of-appeals-opinions-mojs \
    --output "$WORKDIR/dc-opinions-monitor.json"
```

The current redesigned index exposes appeal number, caption, date,
disposition, and judge across 16,313 observed entries and 1,632 zero-based
pages. Published-opinion rows retain linked court PDFs. MOJ rows remain
separate index records with their source-published full-text state. The
separate Court of Appeals case search, Superior Court eAccess, and
CourtListener are complementary routes for docket, trial-court, and
independently searchable opinion/case information.

### D.C. Court of Appeals C-Track cases and filings

```bash
# Case-number, caption, originating-matter, and participant searches.
uv run python tools/query_dc_appellate_cases.py search \
    --appellate-case-number 24-BG-1045 \
    --output "$WORKDIR/dc-appellate-number.json"
uv run python tools/query_dc_appellate_cases.py search \
    --originating-case-number "DDN 2024-D175" \
    --output "$WORKDIR/dc-appellate-origin.json"
uv run python tools/query_dc_appellate_cases.py participant \
    --last-name "Example" --first-name "Alex" \
    --output "$WORKDIR/dc-appellate-participant.json"

# Exact case detail resolves parties, counsel, docket rows, and filing links.
uv run python tools/query_dc_appellate_cases.py case 24-BG-1045 \
    --output "$WORKDIR/dc-appellate-case.json"
uv run python tools/query_dc_appellate_cases.py case 24-BG-1045 \
    --metadata-only --output "$WORKDIR/dc-appellate-locators.json"

# Shared routing supports search, case, docket, documents, and download.
uv run python tools/query_state_courts.py search "Example Holdings" \
    --source us-dc-court-of-appeals-case-search --jurisdiction 11 \
    --search-field participant \
    --output "$WORKDIR/dc-appellate-unified-search.json"
uv run python tools/query_state_courts.py case 24-BG-1045 \
    --source us-dc-court-of-appeals-case-search --ingest \
    --output "$WORKDIR/dc-appellate-unified-case.json"

uv run python tools/query_dc_appellate_cases.py probe \
    --output "$WORKDIR/dc-appellate-probe.json"
uv run python tools/public_records_monitor.py run \
    us-dc-court-of-appeals-case-search \
    --output "$WORKDIR/dc-appellate-monitor.json"
```

The source uses one-based 50-row pages and returns an opaque continuation bound
to the operation and selectors. The adapter resolves filing links through the
case page's source-native DWR call and hashes downloaded court PDFs. An
originating trial or agency number becomes a related-case edge; it does not
replace the appellate case number.

The trial layer remains componentized. The Tyler portal covers civil, civil
Tax, probate, landlord-tenant, and small-claims matters, while eAccess covers
criminal, criminal Tax, and Domestic Violence matters. Their current
verification observations are recorded on those components and do not change
the C-Track route's state.

### D.C. court calendars

```bash
# Today's Superior Court HTML search and complete REST snapshot
uv run python tools/query_dc_superior_calendar.py search \
    --case-number "2026-LTB-005132" \
    --output "$WORKDIR/dc-today.json"
uv run python tools/query_dc_superior_calendar.py snapshot \
    --output "$WORKDIR/dc-today-snapshot.json"

# Criminal hearing rows and separately attributed schedule PDFs
uv run python tools/query_dc_superior_calendar.py criminal \
    --case-number "2026 CTF 004287" \
    --output "$WORKDIR/dc-criminal.json"
uv run python tools/query_dc_superior_calendar.py artifacts \
    --family criminal --output "$WORKDIR/dc-criminal-pdfs.json"

# Tax Division and appellate calendar artifacts
uv run python tools/query_dc_superior_calendar.py artifacts \
    --family tax --output "$WORKDIR/dc-tax-pdfs.json"
uv run python tools/query_dc_superior_calendar.py appeals \
    --year 2024 --output "$WORKDIR/dc-appeals-calendars.json"

# Unified hearing queries return one native page and a continuation cursor.
uv run python tools/query_state_courts.py search "Example Holdings" \
    --source us-dc-superior-court-today-calendar --jurisdiction 11 \
    --ingest --output "$WORKDIR/dc-today-unified.json"
uv run python tools/query_state_courts.py search "OPERATING A VEHICLE" \
    --source us-dc-superior-court-criminal-calendar \
    --search-field charge --ingest \
    --output "$WORKDIR/dc-criminal-unified.json"
uv run python tools/query_state_courts.py calendar 2024 \
    --source us-dc-court-of-appeals-calendars \
    --output "$WORKDIR/dc-appeals-unified.json"

uv run python tools/query_dc_superior_calendar.py probe \
    --output "$WORKDIR/dc-calendar-family-probe.json"
uv run python tools/public_records_monitor.py run \
    us-dc-superior-court-today-calendar \
    us-dc-superior-court-criminal-calendar \
    us-dc-superior-court-tax-calendars \
    us-dc-court-of-appeals-calendars \
    --output "$WORKDIR/dc-calendar-monitors.json"
```

Direct HTML searches traverse every advertised zero-based 10-row page when no
bound is selected. The REST snapshot returns the complete current-day array
when `--limit` is omitted. Hearing records preserve event timestamps, offsets,
case number, judge, courtroom, and native page occurrence; criminal
charge-level rows remain distinct. Tax, criminal-schedule, and appellate PDFs
remain calendar artifacts rather than case-file documents. Portal, eAccess,
and the opinion/MOJ index provide the complementary case-history, available
document, and appellate-disposition coverage.

### D.C. judicial directories and data publications

```bash
uv run python tools/query_dc_court_directory_data.py directory \
    --court superior --query Becker \
    --output "$WORKDIR/dc-superior-directory.json"
uv run python tools/query_dc_court_directory_data.py directory \
    --court appeals --role senior \
    --output "$WORKDIR/dc-appeals-directory.json"
uv run python tools/query_dc_court_directory_data.py contacts \
    --court all --output "$WORKDIR/dc-court-contacts.json"
uv run python tools/query_dc_court_directory_data.py assignments \
    --output "$WORKDIR/dc-assignment-publications.json"

uv run python tools/query_dc_court_directory_data.py data-request \
    --output "$WORKDIR/dc-data-request-program.json"
uv run python tools/query_dc_court_directory_data.py reports \
    --section annual-reports --year 2025 \
    --output "$WORKDIR/dc-reports.json"
uv run python tools/query_dc_court_directory_data.py download \
    --collection reports "2025 Annual Report - Statistical Summary" \
    "$WORKDIR/dc-2025-statistical-summary.pdf" \
    --output "$WORKDIR/dc-report-download.json"

uv run python tools/query_state_courts.py search Becker \
    --source us-dc-superior-court-judicial-directory \
    --search-field associate \
    --output "$WORKDIR/dc-directory-shared.json"
uv run python tools/public_records_monitor.py run \
    us-dc-superior-court-judicial-directory \
    us-dc-court-of-appeals-judicial-directory \
    us-dc-courts-reports-publication-catalog \
    --output "$WORKDIR/dc-directory-data-monitors.json"
```

The two directory components retain current judge roles, contact blocks, and
profile/assignment routes as source snapshots. The request program remains a
submitted fulfillment product; the reports catalog remains a directly
retrievable aggregate publication source. Report records are keyed by catalog
occurrence so duplicate links and differing source labels remain visible.

### Maryland MDEC cases, estates, judgment/liens, and published decisions

```bash
# Discover and search all reports currently published by the Judiciary.
uv run python tools/query_md_public_cases.py reports \
    --output "$WORKDIR/md-mdec-reports.json"
uv run python tools/query_md_public_cases.py search --all-current \
    --name "Example" --filing-date-from 2026-07-01 \
    --output "$WORKDIR/md-mdec-name.json"
uv run python tools/query_md_public_cases.py search --all-current \
    --address "Baltimore" \
    --output "$WORKDIR/md-mdec-address.json"

# Parse an already acquired report with the same filters.
uv run python tools/query_md_public_cases.py parse \
    "$WORKDIR/md-cases-filed.pdf" --charge "ASSAULT" \
    --output "$WORKDIR/md-mdec-local.json"

# The judgment index has distinct person and company form modes.
uv run python tools/query_md_judgment_liens.py person "Example" \
    --first-name "Alex" --filed-from 2020-01-01 \
    --output "$WORKDIR/md-judgments-person.json"
uv run python tools/query_md_judgment_liens.py company "Example Holdings LLC" \
    --county "Baltimore City" \
    --output "$WORKDIR/md-judgments-company.json"
uv run python tools/query_md_judgment_liens.py detail 03-L-12-005195 \
    --output "$WORKDIR/md-judgment-detail.json"

# The estate index has separate decedent, representative, and exact-number modes.
uv run python tools/query_md_estate_search.py decedent Novak \
    --first-name Patricia --county "Baltimore County" \
    --output "$WORKDIR/md-estate-decedent.json"
uv run python tools/query_md_estate_search.py representative Novak \
    --county "Baltimore County" --all-results \
    --output "$WORKDIR/md-estate-representative.json"
uv run python tools/query_md_estate_search.py estate 238438 \
    --county "Baltimore County" \
    --output "$WORKDIR/md-estate-number.json"
uv run python tools/query_md_estate_search.py detail 1868548158 \
    --output "$WORKDIR/md-estate-detail.json"
uv run python tools/query_md_estate_search.py routes \
    --output "$WORKDIR/md-estate-alternatives.json"

# Legal notices retain each published occurrence and its complete notice text.
uv run python tools/query_md_estate_notices_claims.py notices \
    --county "Montgomery County" --published-from 2026-07-01 \
    --party-type decedent --last-name Smith \
    --output "$WORKDIR/md-estate-notices.json"

# Claim search covers decedent and filed-by roles and enriches every row from
# its exact RecordId detail page.
uv run python tools/query_md_estate_notices_claims.py claims \
    --role decedent --last-name Smith --county "Charles County" \
    --claim-status OPEN --output "$WORKDIR/md-estate-claims.json"
uv run python tools/query_md_estate_notices_claims.py claim-detail 270350434 \
    --source-partition row --output "$WORKDIR/md-estate-claim-detail.json"
uv run python tools/query_md_estate_notices_claims.py sources \
    --output "$WORKDIR/md-estate-source-graph.json"

uv run python tools/query_md_opinions.py reported \
    --year all --query "Harbor Properties" \
    --output "$WORKDIR/md-reported-opinions.json"
uv run python tools/query_md_opinions.py unreported \
    --date-from 2026-01-01 --date-to 2026-07-31 \
    --query "Properties" \
    --output "$WORKDIR/md-unreported-opinions.json"
uv run python tools/query_md_opinions.py routes \
    --output "$WORKDIR/md-opinion-routes.json"
uv run python tools/query_md_opinions.py probe \
    --output "$WORKDIR/md-opinion-probe.json"

uv run python tools/query_md_business_opinions.py search --all-pages \
    --query "Lockheed Martin" --filed-from 2003-01-01 \
    --output "$WORKDIR/md-business-publications.json"
uv run python tools/query_md_business_opinions.py search --year 2008 \
    --document-type order \
    --output "$WORKDIR/md-business-orders-2008.json"
uv run python tools/query_md_business_opinions.py routes \
    --output "$WORKDIR/md-business-routes.json"
uv run python tools/query_md_business_opinions.py probe \
    --output "$WORKDIR/md-business-probe.json"

# Shared routing exposes current case discovery and judgment event/claim rows.
uv run python tools/query_state_courts.py search "Baltimore" \
    --source us-md-mdec-public-cases --jurisdiction 24 \
    --search-field address --after 2026-07-01 --ingest \
    --output "$WORKDIR/md-mdec-unified.json"
uv run python tools/query_state_courts.py search "Example Holdings LLC" \
    --source us-md-judgment-liens --jurisdiction 24 \
    --search-field company --entity-kind organization \
    --output "$WORKDIR/md-judgments-unified.json"
uv run python tools/query_state_courts.py claims 03-L-12-005195 \
    --source us-md-judgment-liens --ingest \
    --output "$WORKDIR/md-judgment-claims.json"
uv run python tools/query_state_courts.py search "Patricia Novak" \
    --source us-md-estate-search --jurisdiction 24005 --ingest \
    --output "$WORKDIR/md-estate-name-unified.json"
uv run python tools/query_state_courts.py docket 238438 \
    --source us-md-estate-search --county "Baltimore County" --ingest \
    --output "$WORKDIR/md-estate-docket-unified.json"
uv run python tools/query_state_courts.py search "Harbor Properties" \
    --source us-md-appellate-opinions --jurisdiction 24 --ingest \
    --output "$WORKDIR/md-reported-opinions-unified.json"
uv run python tools/query_state_courts.py documents "1539/24" \
    --source us-md-appellate-opinions --search-field unreported \
    --after 2026-01-01 --before 2026-07-31 --ingest \
    --output "$WORKDIR/md-unreported-opinion-unified.json"
uv run python tools/query_state_courts.py search "Lockheed Martin" \
    --source us-md-business-technology-opinions --jurisdiction 24 \
    --after 2003-01-01 --before 2008-12-31 --ingest \
    --output "$WORKDIR/md-business-publications-unified.json"
uv run python tools/query_state_courts.py documents "24-C-05-009296" \
    --source us-md-business-technology-opinions --document-type order \
    --ingest --output "$WORKDIR/md-business-orders-unified.json"

uv run python tools/public_records_monitor.py run \
    us-md-mdec-public-cases us-md-estate-search \
    us-md-estate-legal-notices us-md-estate-claims us-md-judgment-liens \
    us-md-appellate-opinions us-md-business-technology-opinions \
    --output "$WORKDIR/md-court-monitors.json"
```

The MDEC feed consists of five current court-generated Cases Filed PDFs rather
than a historical docket. It retains report identity, publication date,
reporting period, case filing date, cross-page records, party names and
published addresses, and charge stubs as separate fields. The judgment source
uses stateful JSF responses; the adapter rediscovers the active form, action,
and view state after each response and keeps original and modification events
separate from case identity.

The estate source likewise rediscovers current WebForms state. Its
continuations bind the query, schema, total, native position, and daily source
refresh marker, then resume through a fresh session. County plus estate number
is the normalized case identity; `RecordId` locates detail and `SecId` locates
a docket occurrence. Shared case and docket commands perform that exact
resolution before fetching detail. If the same estate number appears in more
than one jurisdiction, the returned candidates identify which county or
Register of Wills court ID to select.

Legal notices and claims remain independently attributable source records.
Notice identity is the source's numeric notice occurrence ID; the adapter
retains the exact title, full HTML and text, source-published variant, party
and date filters, and a query-bound result marker for continuation. Claim
identity is source partition plus `RecordId`; result rows are enriched from
the exact detail page with filed-by person or corporation, amount, type,
status, remarks, estate pivots, and the source's current-data marker. The
shared ingester preserves these components as source snapshots instead of
coercing either occurrence into a generic estate case.

The appellate source preserves two official publication collections. Reported
decisions are partitioned by filing year from 1995 onward and include source
line markers that verify a complete returned CGI index. Unreported decisions
are partitioned by month from February 2001 onward; source-linked PDFs begin in
May 2015, so earlier rows are retained as metadata-only. The normalized case
join is court plus docket file and term. Reported/unreported disposition
identity, opinion/order type, source correction text, and PDF identity remain
separate from that case key. Shared search defaults to the reported archive;
`--search-field unreported` selects monthly indexes and accepts shared date
bounds. Shared case/document lookup matches the published case number exactly,
while free-text discovery excludes technical PDF paths and provenance fields.
These publication indexes are not represented as complete dockets.

The Business and Technology source traverses the complete current
2009-present publication table and all six closed annual archives for
2003-2008. In the verified snapshot, 160 publications expose 268 attachment
references across 267 unique exact URLs in PDF, DOC, and WPD formats. The
adapter searches published metadata and filters exact case number, county,
judge, document role, or source filing interval. It preserves omitted fields,
month-precision dates, multiple case-number lines, duplicate links, doubled
path segments, and filename/designation mismatches as source observations.
Normalized ingestion creates a publication event for each supplied case,
retains each attachment as a separate artifact, and uses an explicit
publication-designation fallback when the source omits a case number.
Monitoring keeps routes, schemas, identity rules, and document formats in the
stable contract while current counts and the sampled artifact remain rolling
observations.

When a desired field is absent, the catalog exposes the relevant adjacent
route instead of treating the general Case Search portal as the only path:
Circuit Court clerks for underlying files, AOC data products for compiled
records, appellate opinions and Business and Technology publications for
adjudicative text, Register of Wills offices for estate
instruments/certified copies, legal notices and claim search for their
separate record roles, MDLandRec and Plats.net for instruments and plats, SDAT
for property accounts, and local finance offices for property-tax or
municipal-lien status.

### Michigan appellate cases, opinions, and orders

```bash
# Each result category has its own native pagination and continuation.
uv run python tools/query_michigan_appellate.py search \
    --result-type cases --party-name "Example" --limit 100 \
    --output "$WORKDIR/mi-appellate-cases.json"
uv run python tools/query_michigan_appellate.py search insurance \
    --result-type opinions --resource opinion --limit 100 \
    --output "$WORKDIR/mi-appellate-opinions.json"
uv run python tools/query_michigan_appellate.py search \
    --result-type orders --case-id 166702 \
    --output "$WORKDIR/mi-appellate-orders.json"

# Inspect or verify the page model, all three APIs, one PDF, and alternatives.
uv run python tools/query_michigan_appellate.py overview Example \
    --output "$WORKDIR/mi-appellate-preview.json"
uv run python tools/query_michigan_appellate.py routes \
    --output "$WORKDIR/mi-appellate-routes.json"
uv run python tools/query_michigan_appellate.py probe \
    --output "$WORKDIR/mi-appellate-probe.json"

# Shared source routing uses --case-type to select cases/opinions/orders.
uv run python tools/query_state_courts.py search "Example" \
    --source us-mi-appellate-case-opinion-order-search \
    --jurisdiction 26 --case-type opinions --search-field party --ingest \
    --output "$WORKDIR/mi-appellate-unified.json"
uv run python tools/query_state_courts.py case 360440 \
    --source us-mi-appellate-case-opinion-order-search \
    --output "$WORKDIR/mi-appellate-case.json"
```

Case-route court codes take precedence over inconsistent source flags.
`currentPage` and `totalPages` determine continuation; `hasMoreResults` is not
used as the sole completion signal. The overview endpoint is a cross-category
preview, while `search` traverses the selected category. Opinion and order rows
project as separately keyed publication events and document artifacts on their
resolved case. The route inventory exposes MiCOURT trial search, the MiCOURT
developer product, Business Court rulings, and the responsible trial clerk for
fields or documents absent from the appellate index.

### Michigan Business Court document search

```bash
# Inspect the exact source-published category and court facet values.
uv run python tools/query_michigan_business_court.py categories \
    --output "$WORKDIR/mi-business-categories.json"
uv run python tools/query_michigan_business_court.py sources \
    --output "$WORKDIR/mi-business-courts.json"

# Omit --limit to traverse every source-reported page.
uv run python tools/query_michigan_business_court.py search "real estate" \
    --business-court "Real Estate" --sort Newest \
    --output "$WORKDIR/mi-business-documents.json"

# Shared search maps --case-type to the exact native business category.
uv run python tools/query_state_courts.py search "real estate" \
    --source us-mi-business-court-search --jurisdiction 26 \
    --case-type "Real Estate" --ingest \
    --output "$WORKDIR/mi-business-shared.json"

uv run python tools/query_michigan_business_court.py probe \
    --output "$WORKDIR/mi-business-probe.json"
uv run python tools/public_records_monitor.py run \
    us-mi-business-court-search \
    --output "$WORKDIR/mi-business-monitor.json"
```

The native page size is eight and continuation follows `currentPage <
totalPages`; `hasMoreResults` is preserved as a source value rather than used
as the traversal authority. Explicit limits produce query-bound cursors.
Search rows retain the PDF identity, query/page/row occurrence, raw case label,
and each parsed case-number candidate independently. Rows with omitted legacy
date/name/number fields remain valid document occurrences. Shared ingestion
uses the publication collection as its court scope and does not convert a
selected court facet or filename prefix into a verified trial-court field.

### Pennsylvania and Delaware court adapters

```bash
# Pennsylvania UJS public dockets and official reports
uv run python tools/query_pa_ujs.py case CP-51-CR-0007622-2022 \
    --output "$WORKDIR/pa-ujs-case.json"
uv run python tools/query_pa_ujs.py person SMITH \
    --output "$WORKDIR/pa-ujs-person.json"
uv run python tools/query_pa_ujs.py report CP-51-CR-0007622-2022 \
    "$WORKDIR/pa-ujs-docket.pdf" --kind docket_sheet \
    --output "$WORKDIR/pa-ujs-docket-receipt.json"

# Pennsylvania appellate opinion/posting API and PDFs
uv run python tools/query_pa_opinions.py docket "69 WAL 2026" \
    --court supreme --output "$WORKDIR/pa-opinion-postings.json"
uv run python tools/query_pa_opinions.py list --court superior --year 2026 \
    --output "$WORKDIR/pa-superior-opinions.json"

# Delaware CourtConnect cases, dockets, and judgments
uv run python tools/query_delaware_courts.py options \
    --output "$WORKDIR/de-courtconnect-options.json"
uv run python tools/query_delaware_courts.py cases "EXAMPLE HOLDINGS LLC" \
    --output "$WORKDIR/de-courtconnect-cases.json"
uv run python tools/query_delaware_courts.py case JP13-23-013991 \
    --output "$WORKDIR/de-courtconnect-case.json"
uv run python tools/query_delaware_courts.py judgments "EXAMPLE HOLDINGS LLC" \
    --output "$WORKDIR/de-courtconnect-judgments.json"

# Delaware's separate Opinions and Orders archive
uv run python tools/query_delaware_opinions.py options \
    --output "$WORKDIR/de-opinion-options.json"
uv run python tools/query_delaware_opinions.py search \
    --case-number 4373-LM --year 2026 \
    --output "$WORKDIR/de-opinions.json"
uv run python tools/query_delaware_opinions.py download 398840 \
    "$WORKDIR/de-opinion.pdf" \
    --output "$WORKDIR/de-opinion-receipt.json"

# Catalog sentinels for the four active sources
uv run python tools/public_records_monitor.py run \
    us-pa-ujs-public-dockets us-pa-appellate-opinions-postings \
    us-de-courtconnect us-de-opinions-orders \
    --output "$WORKDIR/pa-de-court-monitor.json"
```

UJS and CourtConnect provide case/docket metadata. The two opinion adapters
provide publication metadata and public PDFs. Pennsylvania AOPC compiled data,
Delaware clerk records/certified copies, and Delaware's named commercial
remote-record route remain separate catalog actions for fields or documents
not present in those public sources.

### Harris County District Clerk public datasets

```bash
# Inventory the live catalog by source-native section and normalized family
uv run python tools/query_harris_court_bulk.py list \
    --section Civil --family case_summary --published-after 2026-07-01 \
    --result-limit 25 \
    --output "$WORKDIR/harris-civil-case-summary-catalog.json"

# Inspect or download one exact member of the current catalog
uv run python tools/query_harris_court_bulk.py inspect \
    'Civil\2024-08-15 FIELD_CODES.xlsx' \
    --sample-bytes 4096 \
    --output "$WORKDIR/harris-field-codes-inspection.json"
uv run python tools/query_harris_court_bulk.py download \
    'Civil\2024-08-15 FIELD_CODES.xlsx' \
    --destination "$WORKDIR/harris-field-codes.xlsx" \
    --output "$WORKDIR/harris-field-codes-receipt.json"

# Verify catalog structure plus a stable schema-workbook artifact
uv run python tools/query_harris_court_bulk.py sentinel \
    --output "$WORKDIR/harris-court-bulk-sentinel.json"

# The unified router exposes artifact operations only
uv run python tools/query_state_courts.py discovery Civil \
    --source us-tx-harris-district-clerk-public-datasets \
    --case-type case_summary --limit 25 \
    --output "$WORKDIR/harris-shared-discovery.json"
uv run python tools/query_state_courts.py probe \
    --source us-tx-harris-district-clerk-public-datasets \
    --output "$WORKDIR/harris-shared-probe.json"

# Download and parse one header-bearing extract into the court sidecar
uv run python tools/query_harris_court_bulk.py download \
    'Civil\CaseSummaryMods_Daily-2026-07-30.txt' \
    --destination "$WORKDIR/CaseSummaryMods_Daily-2026-07-30.txt" \
    --output "$WORKDIR/harris-case-summary-download.json"
uv run python tools/ingest_harris_court_bulk.py ingest \
    "$WORKDIR/CaseSummaryMods_Daily-2026-07-30.txt" \
    --artifact-result "$WORKDIR/harris-case-summary-download.json" \
    --schema-workbook "$WORKDIR/harris-field-codes.xlsx" \
    --court-db "$WORKDIR/harris-courts.db" \
    --output "$WORKDIR/harris-case-summary-ingest.json"
```

The adapter obtains fresh ASP.NET state for each exact catalog-member
selection and validates the response filename and file signature because the
server's MIME type is not reliable. Civil and criminal extracts supply bulk
case, party, activity, setting, service, filing, and disposition metadata. The
shared operation set is exactly `discovery`, `documents`, `download`, and
`probe`; `documents` means bulk-artifact inspection.

`ingest_harris_court_bulk.py` streams civil case-summary, party, and activity
rows plus criminal filing and disposition rows. It preserves each artifact
row occurrence before projecting cases, parties, attorneys, representations,
docket entries, and case events. The 2026-07-30 five-artifact validation
produced 18,419 source-row occurrences and no filing-document artifacts.
Catalog counts and validation totals are rolling observations. Individual
filing images remain in the separately attributed District Clerk eDocs source.

### Colorado dockets, appellate opinions, court data, and Virginia complements

```bash
# Denver County Court courtroom/date schedule
uv run python tools/query_denver_county_court.py search \
    --courtroom 3A --date 2026-07-29 \
    --output "$WORKDIR/denver-county-docket.json"
uv run python tools/query_denver_county_court.py search \
    --courtroom 3A --date 2026-07-29 --limit 25 --offset 25 \
    --output "$WORKDIR/denver-county-docket-window.json"
uv run python tools/query_denver_county_court.py probe \
    --output "$WORKDIR/denver-county-docket-probe.json"
uv run python tools/public_records_monitor.py run \
    us-co-denver-county-court-public-docket \
    --output "$WORKDIR/denver-county-docket-monitor.json"

# Colorado Judicial Branch statewide option directory and docket search
uv run python tools/query_colorado_judicial.py courts \
    --output "$WORKDIR/colorado-court-directory.json"
uv run python tools/query_colorado_judicial.py search \
    --courthouse 16_civil --date 2026-07-29 --limit 25 \
    --output "$WORKDIR/colorado-dockets.json"
uv run python tools/query_colorado_judicial.py search \
    --courthouse 16_civil --date 2026-07-29 \
    --cursor "$COLORADO_CURSOR" \
    --output "$WORKDIR/colorado-dockets-resumed.json"

# Source case, party/business, and attorney selectors
uv run python tools/query_colorado_judicial.py search \
    --case-year 2025 --case-class CV --case-sequence 858 \
    --date 2026-07-29 \
    --output "$WORKDIR/colorado-case-calendar.json"
uv run python tools/query_colorado_judicial.py search \
    --business-name "EXAMPLE ASPHALT CO LLC" --date-range 1_month \
    --output "$WORKDIR/colorado-business-calendar.json"
uv run python tools/query_colorado_judicial.py search \
    --attorney-bar-number 12345 --date-range today \
    --output "$WORKDIR/colorado-attorney-calendar.json"

# Advertised source export and live form/search/export contract probe
uv run python tools/query_colorado_judicial.py export \
    --courthouse 16_civil --date 2026-07-29 \
    "$WORKDIR/colorado-dockets-export" \
    --output "$WORKDIR/colorado-dockets-export-receipt.json"
uv run python tools/query_colorado_judicial.py probe \
    --courthouse 16_civil --date 2026-07-29 \
    --output "$WORKDIR/colorado-docket-probe.json"

# Historical appellate case-law archive
uv run python tools/query_colorado_opinions.py search "water rights" \
    --court supreme --limit 25 \
    --output "$WORKDIR/colorado-supreme-opinions.json"
uv run python tools/query_colorado_opinions.py docket 25CA0631 \
    --court appeals \
    --output "$WORKDIR/colorado-appeals-docket-opinions.json"
uv run python tools/query_colorado_opinions.py document 887202075 \
    --output "$WORKDIR/colorado-opinion-document.json"
uv run python tools/query_colorado_opinions.py download 887202075 \
    "$WORKDIR/colorado-opinion.pdf" \
    --output "$WORKDIR/colorado-opinion-download.json"

# Separate current-release surfaces
uv run python tools/query_colorado_opinions.py releases \
    --court supreme --year 2026 \
    --output "$WORKDIR/colorado-supreme-releases.json"
uv run python tools/query_colorado_opinions.py releases \
    --court appeals --year 2026 --query "water" \
    --output "$WORKDIR/colorado-appeals-announcements.json"
uv run python tools/query_colorado_opinions.py probe --component all \
    --output "$WORKDIR/colorado-opinions-probe.json"

# Official reports, dashboards, and compiled-data request materials
uv run python tools/query_colorado_court_data.py catalog \
    --output "$WORKDIR/colorado-court-data-catalog.json"
uv run python tools/query_colorado_court_data.py list \
    --component-source us-co-judicial-annual-statistical-reports \
    --fiscal-year 2024 \
    --output "$WORKDIR/colorado-court-data-fy2024.json"
uv run python tools/query_colorado_court_data.py search eviction \
    --output "$WORKDIR/colorado-eviction-data-routes.json"
uv run python tools/query_colorado_court_data.py download \
    annual-statistical-report-fy-2024 \
    --destination "$WORKDIR/colorado-annual-statistics-fy2024.pdf" \
    --output "$WORKDIR/colorado-annual-statistics-download.json"
uv run python tools/query_colorado_court_data.py probe \
    --output "$WORKDIR/colorado-court-data-probe.json"

# Unified live route; the positional calendar selector is the courtroom.
uv run python tools/query_state_courts.py calendar 3A \
    --source us-co-denver-county-court-public-docket \
    --jurisdiction 08031 --hearing-date 2026-07-29 --ingest \
    --output "$WORKDIR/denver-county-docket-unified.json"

# Virginia General District Court direct adapter
uv run python tools/query_va_general_district.py courts \
    --output "$WORKDIR/va-gdc-courts.json"
uv run python tools/query_va_general_district.py name 013 "EXAMPLE LLC" \
    --division civil --limit 25 \
    --output "$WORKDIR/va-gdc-name.json"
uv run python tools/query_va_general_district.py case 013 GV26004683-00 \
    --division civil \
    --output "$WORKDIR/va-gdc-case.json"
uv run python tools/query_va_general_district.py hearing 013 2026-07-30 \
    --division civil --limit 25 \
    --output "$WORKDIR/va-gdc-hearings.json"
uv run python tools/query_va_general_district.py service 013 SMITH \
    --division civil --limit 25 \
    --output "$WORKDIR/va-gdc-service.json"
uv run python tools/query_va_general_district.py probe --court 013 \
    --output "$WORKDIR/va-gdc-probe.json"

# Unified Virginia search, exact case, and hearing-date routes
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
    --source us-va-general-district-court-case-information \
    --jurisdiction 51 --court-id va-gdc-013 --case-type civil \
    --search-field name --limit 25 \
    --output "$WORKDIR/va-gdc-shared-name.json"
uv run python tools/query_state_courts.py case GV26004683-00 \
    --source us-va-general-district-court-case-information \
    --jurisdiction VA --court-id va-gdc-013 --case-type civil \
    --output "$WORKDIR/va-gdc-shared-case.json"
uv run python tools/query_state_courts.py calendar 2026-07-30 \
    --source us-va-general-district-court-case-information \
    --jurisdiction US-VA --court-id va-gdc-013 --case-type civil \
    --hearing-date 2026-07-30 --limit 25 \
    --output "$WORKDIR/va-gdc-shared-calendar.json"
uv run python tools/public_records_monitor.py run \
    us-va-general-district-court-case-information \
    --output "$WORKDIR/va-gdc-monitor.json"

# Virginia complementary appellate, Clerk-copy, and land-record routes
uv run python tools/public_records_catalog.py show \
    us-va-general-district-court-case-information --json
uv run python tools/public_records_catalog.py show \
    us-va-local-court-clerk-records --json
uv run python tools/public_records_catalog.py show \
    us-va-circuit-court-case-information --json
uv run python tools/public_records_catalog.py show \
    us-va-appellate-opinions --json
uv run python tools/public_records_actions.py plan \
    us-va-secure-remote-access-land-records \
    --operation search_land_records --selector "Arlington deed or judgment" \
    --court-or-office "Arlington Circuit Court Clerk" \
    --output "$WORKDIR/virginia-sra-action.json"
```

The Virginia General District adapter verified 134 source-published court
components on 2026-07-30. A component code such as `013` is the application's
court selector and becomes `va-gdc-013`; it is not a geographic FIPS code.
Civil (`V`) and Traffic/Criminal (`T`) each expose name, exact case-number,
hearing-date, and service/process routes. Name, hearing, and service results
use native 20-row pages without a reported total. Omitting `--limit` follows
`Next` until it disappears; a caller bound returns a criteria-bound replay
cursor.

Exact case detail retains the source's section states, masked
date-of-birth value and state, payment links, and the source's published-empty
versus absent distinction. Search occurrences do not replace that richer
detail. The application publishes neither a filing index nor filing images.
Use the responsible General District Court Clerk for official or certified
case records and copies; Circuit Court Case Information, the official
appellate opinion archive, and Secure Remote Access land records add
court-level metadata, adjudicative text, and recorded-instrument evidence
without being treated as the same source.

### E.D. Virginia bankruptcy RECAP archive adapter

`query_edva_bankruptcy.py` resolves an exact E.D. Virginia bankruptcy docket
number through CourtListener, reads archived docket entries and nested RECAP
document metadata by positive CourtListener docket ID, inventories
complementary access routes, and exposes a bounded lifecycle probe.

```bash
# Direct archive reads
uv run python tools/query_edva_bankruptcy.py sources \
    --output "$WORKDIR/edva-bankruptcy-sources.json"
uv run python tools/query_edva_bankruptcy.py case 05-39367 \
    --output "$WORKDIR/edva-bankruptcy-case.json"
uv run python tools/query_edva_bankruptcy.py entries 49921079 \
    --output "$WORKDIR/edva-bankruptcy-entries.json"
uv run python tools/query_edva_bankruptcy.py probe \
    --output "$WORKDIR/edva-bankruptcy-probe.json"

# Shared routes: exact case number, then CourtListener docket ID
uv run python tools/query_state_courts.py case 05-39367 \
    --source us-va-ed-bankruptcy-pacer-recap \
    --jurisdiction VA --court-id us-bankr-edva \
    --output "$WORKDIR/edva-bankruptcy-shared-case.json"
uv run python tools/query_state_courts.py docket 49921079 \
    --source us-va-ed-bankruptcy-pacer-recap \
    --jurisdiction 51 --court-id vaeb \
    --output "$WORKDIR/edva-bankruptcy-shared-docket.json"
uv run python tools/query_state_courts.py documents 49921079 \
    --source us-va-ed-bankruptcy-pacer-recap \
    --jurisdiction US-VA --court-id us-bankr-edva --ingest \
    --output "$WORKDIR/edva-bankruptcy-shared-documents.json"
uv run python tools/query_state_courts.py discovery \
    --source us-va-ed-bankruptcy-pacer-recap \
    --jurisdiction VA \
    --output "$WORKDIR/edva-bankruptcy-shared-sources.json"

uv run python tools/public_records_monitor.py run \
    us-va-ed-bankruptcy-pacer-recap \
    --output "$WORKDIR/edva-bankruptcy-monitor.json"
```

Shared operations are exactly `case`, `docket`, `documents`, `discovery`, and
`probe`. `case` maps to the direct exact-docket lookup; `docket` and
`documents` both map to the archived entry collection because each entry
carries its nested RECAP document metadata; `discovery` maps to the
role-specific source inventory. Ingestion creates one case per CourtListener
docket ID and retains source occurrences for the docket, each entry, and each
RECAP document. Documents distinguish available archive files from
metadata-only records.

The five-request lifecycle monitor reads two known docket identities, one
entry page for each, and the RECAP Fetch `OPTIONS` contract. It makes no
`POST` request and retrieves no document. The adapter's direct
`fetch-docket`, `fetch-document`, `fetch-status`, and `pray` commands are
separate explicit operations.

CourtListener/RECAP availability varies by docket and document and is not the
official PACER docket. A blocked or empty archive response does not establish
official absence or sealing. PACER Case Locator, E.D. Virginia CM/ECF,
Clerk-provided copies, courthouse public-access terminals, and transferred
closed-case files through the court, a Federal Records Center, or the National
Archives remain separately attributable complementary paths.

The Denver portal returns one server-rendered schedule for a courtroom and
date. The verified form exposed 35 unique courtrooms and 14 result columns.
`--limit` and `--offset` select from that response; there is no native server
paginator. Normalized rows contain case number, defendant, status, language,
case type, hearing, time, disposition, domestic-violence indicator, counsel,
date of birth, and charges/violations. Case-history URLs are retained, but two
tested live links returned HTTP 500 and are not used as a verified detail
route. The Colorado Judicial Branch docket catalog entry provides the broader
state trial-court calendar and party/business/attorney filters.

`query_colorado_judicial.py` provides four direct operations: `courts`,
`search`, `export`, and `probe`. The verified directory contained 23 judicial
districts, 66 county values, and 74 non-placeholder courthouse values. A live
Denver civil query returned 56 rows through replayable anonymous GET result
URLs with native 20-row pages. Omitting `--limit` follows every reported page;
a caller limit returns an opaque
`colorado-judicial:v1:query:<sha256>:page:N:row:N` cursor. Set
`COLORADO_CURSOR` to the exact `next_cursor` from the preceding response; the
query fingerprint prevents reuse with different source selectors.
For the unified name route, matching `--after DATE --before DATE` values map to
the source's exact-date selector. Unequal bounds are reported explicitly
because the source form does not expose arbitrary start/end dates.

Search filters map directly to the form's district, county, courthouse,
County/District court type, division, date range or specific date, case
year/class/sequence, individual party, business, attorney name, and attorney
bar-number fields. Normalized `docket_entry` rows preserve the source Name as
`calendar_name`, use a stable row identity, and share a stable `hearing_id`
when multiple calendar names describe the same case/date/time/hearing. The
source advertises an export link. A verified 56-row query returned HTTP 204
through both direct and browser requests, while a later integrated probe
produced an export artifact for its current query. The adapter preserves that
query-dependent result as an artifact or `source_export_unavailable`,
independently of search results.

`query_colorado_opinions.py` uses one adapter family for two independently
cited source components:

| Source ID | Role |
|---|---|
| `us-co-appellate-case-law-search` | Historical Colorado-branded Supreme Court and Court of Appeals opinion search, metadata, indexed full text, and PDFs |
| `us-co-judicial-appellate-opinion-releases` | Current Supreme Court releases and Court of Appeals announcement packets |

Current Court of Appeals announcement packets are release indexes, not
individual opinions, and remain separate from archive records. The historical
search's native pages contain up to 20 rows, but completion is driven by the
reported result count. A short page does not end traversal while that count
indicates more records. Omitting `--limit` follows the reported count; a
caller limit yields a query-bound
`colorado-opinions:v2:query:<sha256>:page:N:row:N:seen:N:anchor:<document-id>`
cursor. Count drift,
repeated identities, an early empty page, and another failure to advance are
reported rather than converted into a complete result.

The current-release command uses its own
`colorado-opinion-releases:v2:query:<sha256>:offset:N:anchor:<sha256>`
continuation and follows
the Court of Appeals page links before applying a caller-selected window.
`document` returns archive metadata and indexed full text; `download` accepts
an archive document ID, the Supreme release-node URL emitted by `releases`, or
a verified Colorado appellate PDF URL. Archive IDs are checked against opinion
metadata. The historical service may regenerate equivalent PDFs with different
file hashes, so the monitor records the hash but bases drift identity on the
document identity, full-text hash, media type, and byte length. Historical,
release, and artifact references use `COOPINION:`,
`COOPINION-RELEASE:`, and `COOPINION-ARTIFACT:` respectively. The archive is
useful adjudicative text and case discovery, not a complete appellate docket
or a source for the parties' underlying briefs and trial filings.

`query_colorado_court_data.py` catalogs official publications and request
routes without assigning their assertions to its umbrella adapter ID. Returned
records preserve one of four component source IDs:

| Component source ID | Records |
|---|---|
| `us-co-judicial-annual-statistical-reports` | Current statistical Power BI dashboards and archived annual-report PDFs |
| `us-co-judicial-case-parties-without-representation` | Fiscal-year cases/parties-without-representation PDFs; the source excludes Denver County Court |
| `us-co-judicial-eviction-filings-dashboard` | Public forcible-entry-and-detainer dashboard for Colorado state courts and Denver County Court |
| `us-co-judicial-compiled-aggregate-data-requests` | CJD 05-01, Addendum A, and the compiled/aggregate-data request workflow |

The 2026-07-29 live catalog contained 18 records: nine annual-statistics
records, five cases/parties-without-representation reports, one eviction
dashboard, and three compiled-data program records. The verified annual set
comprised five current dashboards plus FY 2021–2024 PDFs; the representation
reports covered FY 2021–2025. Power BI links are preserved as public
interactive dashboards, but no machine-readable export contract was verified.
`download` selects exact cataloged PDFs; `catalog`, `list`, and `search` retain
the dashboard and request-workflow records for discovery.

The compiled-data program is a distinct source, not an inferred bulk feed.
CJD 05-01 Section 4.30 describes Department policy not to release the entire
case-management system or a substantial subset as bulk data. Section 4.40 and
Addendum A provide the route for requesting publicly accessible compiled or
aggregate data not already available remotely or in an existing report. The
program also describes a monthly civil-judgment report available from the
State Court Administrator's Office upon request and applicable fees, with case
number, creditor/debtor names and entered addresses, judgment date and amount,
and an applicable satisfaction date.

Together these components illustrate the source-census fallback for a bulk
route that is not directly distributed: preserve the official request
workflow, static reports, and interactive dashboards as separate,
field-specific sources rather than treating the location as having no useful
data.

Virginia General District Court Case Information adds civil, criminal,
traffic, judgment, service, garnishment, eviction, and hearing metadata.
Circuit Court Case Information adds participating-court civil/criminal
metadata. The official appellate archive supplies direct opinion PDFs.
Secure Remote Access routes land-record work to the participating Circuit
Court Clerk, whose registration, record groups, fees, coverage, and image
availability apply to that court.

### Washington official court source family

`query_washington_courts.py` exposes a component-attributed manifest. The AOC
directory and appellate-opinion components also have shared live routes,
normalized ingestion, stable-contract monitors, census associations, and
canonical source URLs.

```bash
# Inventory separately attributable components and their operation states.
uv run python tools/query_washington_courts.py sources \
    --output "$WORKDIR/wa-court-sources.json"
uv run python tools/query_washington_courts.py manifest \
    --output "$WORKDIR/wa-court-manifest.json"

# Directory records and current statewide PDF snapshot.
uv run python tools/query_washington_courts.py directory-counties \
    --output "$WORKDIR/wa-directory-counties.json"
uv run python tools/query_washington_courts.py directory-search SMITH \
    --initial J --output "$WORKDIR/wa-directory-search.json"
uv run python tools/query_washington_courts.py directory-org 190 \
    --output "$WORKDIR/wa-directory-org.json"
uv run python tools/query_washington_courts.py directory-pdf \
    "$WORKDIR/wa-court-directory.pdf" \
    --output "$WORKDIR/wa-directory-pdf-receipt.json"

# Opinion release, enumeration, exact information, and official PDF.
uv run python tools/query_washington_courts.py opinions-feed \
    supreme-published --output "$WORKDIR/wa-supreme-feed.json"
uv run python tools/query_washington_courts.py opinions-list \
    --scope all --query "water" \
    --output "$WORKDIR/wa-opinion-search.json"
uv run python tools/query_washington_courts.py opinion-detail 883666MAJ \
    --output "$WORKDIR/wa-opinion-detail.json"
uv run python tools/query_washington_courts.py opinion-download 883666MAJ \
    "$WORKDIR/wa-opinion.pdf" \
    --output "$WORKDIR/wa-opinion-download.json"

# Shared routes. Directory ingestion retains a source snapshot; opinion
# ingestion projects each source-published docket separately.
uv run python tools/query_state_courts.py search SMITH \
    --source us-wa-aoc-court-directory --jurisdiction 53 \
    --entity-kind person --search-field person --first-name J \
    --output "$WORKDIR/wa-directory-shared.json"
uv run python tools/query_state_courts.py search "water" \
    --source us-wa-appellate-opinions --jurisdiction WA \
    --search-field query --output "$WORKDIR/wa-opinions-shared.json"
uv run python tools/query_state_courts.py case 88366-6 \
    --source us-wa-appellate-opinions --jurisdiction US-WA \
    --output "$WORKDIR/wa-opinion-case.json"
uv run python tools/query_state_courts.py documents 883666MAJ \
    --source us-wa-appellate-opinions \
    --output "$WORKDIR/wa-opinion-documents.json"
uv run python tools/query_state_courts.py download 883666MAJ \
    --source us-wa-appellate-opinions \
    --destination "$WORKDIR/wa-opinion-shared.pdf" \
    --output "$WORKDIR/wa-opinion-shared-download.json"

# Component-selective source health.
uv run python tools/public_records_monitor.py run \
    us-wa-aoc-court-directory \
    --output "$WORKDIR/wa-directory-monitor.json"
uv run python tools/public_records_monitor.py run \
    us-wa-appellate-opinions \
    --output "$WORKDIR/wa-opinions-monitor.json"
```

Directory identity is scoped by record kind and source organization/person
identifiers; its shared route searches personnel by last name and optional
first initial. Opinion identity has separate publication-occurrence,
appellate-docket, information-page, and official-PDF layers. Feed and list
duplicates remain source occurrences, consolidated opinions fan out to every
source-published docket, and direct official retrieval is not a second
publisher. Slip opinions may later be replaced by final reported versions.

Use the other component commands when those two sources do not contain the
needed fields:

```bash
uv run python tools/query_washington_courts.py case-form \
    --output "$WORKDIR/wa-case-form.json"
uv run python tools/query_washington_courts.py case-routes \
    --output "$WORKDIR/wa-current-routes.json"
uv run python tools/query_washington_courts.py appellate-documents 88366-6 \
    --court supreme --output "$WORKDIR/wa-appellate-document-route.json"
uv run python tools/query_washington_courts.py appellate-complements \
    --kind all --case-number 88366-6 \
    --output "$WORKDIR/wa-appellate-complements.json"
uv run python tools/query_washington_courts.py data-products \
    --output "$WORKDIR/wa-data-products.json"
uv run python tools/query_washington_courts.py custom-extract \
    --output "$WORKDIR/wa-custom-extract.json"
uv run python tools/query_washington_courts.py jislink \
    --output "$WORKDIR/wa-jislink.json"
uv run python tools/query_washington_courts.py caseload-routes \
    --output "$WORKDIR/wa-caseload-routes.json"
uv run python tools/query_washington_courts.py archive-title 2778 \
    --output "$WORKDIR/wa-archive-title-2778.json"
```

The statewide case form and exact-case appellate document portals retain
CAPTCHA-backed result execution as `human_required`. The current-system matrix
routes to Odyssey, local case systems, re:SearchWA, and appellate portals.
JIS-Link is a registered subscription docket display without filed documents;
AOC index products and custom extracts have product-specific acquisition
terms. Washington State Archives, not AOC, publishes the title-scoped
historical superior-court component. Aggregate caseload products diagnose
activity and coverage but are not case-level evidence.

### Oregon parcel and court-document source families

`query_oregon_lane_property.py` exposes two Lane County (`41039`) source
components. `us-or-lane-property-account-information` searches account,
map-taxlot, address, and taxpayer-name indexes and fetches account, receipt,
valuation, tax, and related-link detail.
`us-or-lane-tax-maps` searches map-lot/address or map-name locators and
downloads the separately identified official PDF. An omitted search limit
returns all rows supplied by the source query; an explicit window uses a
query-bound total and boundary anchor.

The account index's `Tax Payer` and `Owner` labels retain their distinct
taxpayer and owner-index roles. Lane Deeds and Records is the recorded-title
source, the Lane ArcGIS parcel and recent-sales layers supply their own
geometry/assessment/sale observations, and RLID remains a subscribed
appraisal/card representation. Tax-map locator occurrences and PDF document
IDs are also separate. The official tax-map ordering route offers a complete
image set and daily, weekly, or monthly updates as another acquisition path.

`query_oregon_taxlots.py` shares one count-driven ArcGIS retrieval core while
retaining three publisher-scoped source identities:

| Source ID | Working coverage and fields |
|---|---|
| `us-or-portland-regional-taxlots` | Clackamas, Multnomah, and Washington parcels with owner and mailing names, situs and legal fields, assessment values, buildings, sales, and geometry |
| `us-or-metro-rlis-public-taxlots` | The same regional area with assessment, building, sale, public-ownership classification, and geometry fields |
| `us-or-owrd-public-tax-lots` | Thirteen county-contributed parcel sets with taxlot IDs, situs and mailing fields, acreage, update dates, and geometry |

```bash
# Inspect each component's field and county contract
uv run python tools/query_oregon_taxlots.py sources \
    --output "$WORKDIR/oregon-taxlot-sources.json"

# Owner search is available on the owner-bearing Portland regional source
uv run python tools/query_oregon_taxlots.py search "EXAMPLE HOLDINGS LLC" \
    --source us-or-portland-regional-taxlots --field owner \
    --county Multnomah --limit 25 \
    --output "$WORKDIR/oregon-owner.json"

# Search or resolve an exact identifier in another publisher component
uv run python tools/query_oregon_taxlots.py search "123 MAIN ST" \
    --source us-or-metro-rlis-public-taxlots --field address \
    --county Washington --limit 25 \
    --output "$WORKDIR/oregon-address.json"
uv run python tools/query_oregon_taxlots.py parcel 21E10DC12800 \
    --source us-or-owrd-public-tax-lots --county Clackamas --geometry \
    --output "$WORKDIR/oregon-taxlot.json"

# Unified routing and component-independent monitoring
uv run python tools/query_property.py owner "EXAMPLE HOLDINGS LLC" \
    --source us-or-portland-regional-taxlots --jurisdiction 41051 \
    --output "$WORKDIR/oregon-owner-unified.json"
uv run python tools/query_oregon_taxlots.py probe --all \
    --output "$WORKDIR/oregon-taxlot-probes.json"
uv run python tools/public_records_monitor.py run \
    us-or-portland-regional-taxlots \
    us-or-metro-rlis-public-taxlots \
    us-or-owrd-public-tax-lots \
    --output "$WORKDIR/oregon-taxlot-monitors.json"
```

Queries use source-reported counts and object-ID progress rather than assuming
that a short ArcGIS page is complete. Continuation cursors bind the source,
field, county, selector, geometry choice, schema fingerprint, and last emitted
identity. Each normalized row retains publisher and county lineage; the
Portland `SOURCE` field is upstream provenance, not a second corroborating
record.

Metro omits personal owner names but remains useful for values, sales,
buildings, geometry, and public-ownership classification. OWRD extends working
parcel discovery beyond the Portland region. The statewide ODF
`TaxlotsDisplay` directory supplies county-layer schemas and visual coverage
even though its live layer query operation currently returns an unsupported
operation. ORMAP supplies the statewide cadastral identifier standard and
routes investigators to county assessor maps. The search planner exposes
these as complements based on the fields they add.

`query_oregon_benton_property.py` adds three Benton County (`41003`)
components under separate identities:

| Source ID | Commands and record grain |
|---|---|
| `us-or-benton-county-taxlot-owners` | `search`, `owner`, `address`, `account`, `map-taxlot`, `or-taxlot`, `map-number`, and `scan`; one owner-party/account row with optional WGS84 taxlot geometry |
| `us-or-benton-county-assessment-bulk` | `bulk-manifest`, `artifact-probe`, and `artifact-download`; one current three-artifact release manifest |
| `us-or-benton-county-assessment-maps` | `maps`, `artifact-probe`, and `artifact-download`; one PDF map or index artifact per directory row |

```bash
uv run python tools/query_oregon_benton_property.py owner "NOLAN" \
    --geometry --output "$WORKDIR/benton-owner.json"
uv run python tools/query_oregon_benton_property.py bulk-manifest \
    --output "$WORKDIR/benton-bulk.json"
uv run python tools/query_oregon_benton_property.py maps \
    --map-number 11513A --match exact \
    --output "$WORKDIR/benton-maps.json"
uv run python tools/query_property.py parcel 11513A000100 \
    --source us-or-benton-county-taxlot-owners \
    --jurisdiction 41003 --geometry --ingest \
    --output "$WORKDIR/benton-unified.json"
```

The unified parcel/map selector defaults to `MapTaxlot`; `--search-field`
chooses account, ORTaxlot, or map number. The live owner-party rows project to
parcel, alias, owner, address, and geometry observations without collapsing
multiple parties into one source row. Bulk and map records remain
artifact-metadata observations. Helion property detail, the county account
history API, and the Helion recorder remain separately attributed complements.

Lincoln County (`41041`) adds two direct property adapters alongside the
existing Helion recorder:

| Source ID | Direct commands | Join fields |
|---|---|---|
| `us-or-lincoln-propertyweb` | `sources`, `search`, `detail`, `document`, `probe` | `property_quick_ref` to WFS `propertyid`; `map_number` to WFS `parcelid`; sale instrument to recorder document number |
| `us-or-lincoln-county-taxlots-wfs` | `sources`, `search`, `probe` | `propertyid`, `parcelid`, `imagekey`, and `ogc_fid` |
| `us-or-lincoln-helion-recorder` | Shared Helion `search`, `detail`, and `probe` commands | Instrument number, party, recording date, and PropertyWeb sale reference |

```bash
uv run python tools/query_oregon_lincoln_propertyweb.py search R452940 \
    --output "$WORKDIR/lincoln-propertyweb-search.json"
uv run python tools/query_oregon_lincoln_propertyweb.py detail \
    R452940 O0064958 \
    --output "$WORKDIR/lincoln-propertyweb-detail.json"
uv run python tools/query_oregon_lincoln_propertyweb.py document \
    appraisal-card 61623 2026 \
    --destination "$WORKDIR/lincoln-appraisal-card.pdf" \
    --output "$WORKDIR/lincoln-appraisal-card.json"
uv run python tools/query_oregon_lincoln_taxlots.py search R452940 \
    --field property --match exact --geometry \
    --output "$WORKDIR/lincoln-taxlot.json"
uv run python tools/query_property.py account R452940 \
    --source us-or-lincoln-propertyweb --jurisdiction 41041 --ingest \
    --output "$WORKDIR/lincoln-account-unified.json"
uv run python tools/query_property.py map 07-11-03-DC-05800-00 \
    --source us-or-lincoln-county-taxlots-wfs \
    --jurisdiction 41041 --ingest \
    --output "$WORKDIR/lincoln-map-unified.json"
uv run python tools/public_records_monitor.py run \
    us-or-lincoln-propertyweb \
    us-or-lincoln-county-taxlots-wfs \
    us-or-lincoln-helion-recorder \
    --output "$WORKDIR/lincoln-property-monitors.json"
```

PropertyWeb detail preserves its account, party, value, sale, bill, payment,
improvement, land, district, exemption, and document-representation
components. Current generated PDFs retain the same-session filename/PDF
lineage; historical statements retain their direct-route lineage. The WFS
uses deterministic WFS 2.0 `COUNT`/`STARTINDEX` paging ordered by
`propertyid,ogc_fid`, and retains its declared EPSG:26915 CRS, the requested
EPSG:4326 representation, and the returned CRS84 coordinate order.

Shared ingestion keeps PropertyWeb and WFS snapshots separate while indexing
their common property and map identifiers as typed aliases. An exact
PropertyWeb sale-instrument reference can link its assessment-roll sale event
to the Helion `recorded_instrument` and `instrument_parcel`; each source keeps
its own derivation and provenance.

`query_oregon_yamhill_property.py`,
`query_oregon_clackamas_property.py`, and
`query_oregon_wasco_property.py` expose county components through a common
`sources`, `source`, `search`, and `probe` shape while preserving different
native schemas:

| County | Direct components and extra commands |
|---|---|
| Yamhill (`41071`) | AscendWeb accounts, current and retired taxlots, and assessment permits; `detail` fetches exact component detail |
| Clackamas (`41005`) | AscendWeb accounts and CMap taxlots; `detail` fetches one component and `account` joins exact account/taxlot observations |
| Wasco (`41065`) | AscendWeb accounts, current taxlots, and eight surveyor index layers; `detail` and `account` cover assessment records, while `attachments` enumerates published survey representations |

```bash
uv run python tools/query_oregon_yamhill_property.py search "EXAMPLE LLC" \
    --source us-or-yamhill-county-at-taxlots --field owner --geometry \
    --output "$WORKDIR/yamhill-owner.json"
uv run python tools/query_oregon_yamhill_property.py search 41270 \
    --source us-or-yamhill-county-assessment-permits --field account \
    --output "$WORKDIR/yamhill-permits.json"
uv run python tools/query_oregon_clackamas_property.py account 05001234 \
    --geometry --output "$WORKDIR/clackamas-account.json"
uv run python tools/query_oregon_wasco_property.py account 9450 \
    --geometry --output "$WORKDIR/wasco-account.json"
uv run python tools/query_oregon_wasco_property.py attachments \
    us-or-wasco-county-surveyor-survey-book 12 \
    --output "$WORKDIR/wasco-survey-book-attachments.json"
```

The unified `query_property.py` router supports account, parcel/map,
owner/address, recording, and event selectors where the chosen component
publishes them. Current assessor records project to parcels, parties,
addresses, values, and geometry. Yamhill permits project to property events;
Yamhill retired-taxlot and Wasco survey rows remain source observations.

Alternative routes are returned in each component contract: Yamhill assessment
extracts/public-information requests and Helion recorder records; Clackamas
GIS downloads, value history, tax statements, recording research, and
assessment contact; Wasco's state archive inventory, survey service directory,
and Helion recorder. This makes the next useful route discoverable when a live
component is incomplete without merging distinct evidence into one source.

`query_oregon_washington_property.py` keeps six Washington County (`41067`)
components separately attributable:

| Source ID | Direct commands |
|---|---|
| `us-or-washington-county-survey-explorer-api` | `survey-search`, `survey-detail`, and `survey-document` across survey, plat, taxlot, benchmark, corner, geocontrol, county-road, and section-map records |
| `us-or-washington-county-survey-explorer-arcgis` | `arcgis LAYER` for the Survey Explorer geometry collection |
| `us-or-washington-county-taxlots` | `taxlots` for current `TLNO`/`MAPNO` geometry |
| `us-or-washington-county-situs-addresses` | `situs` for `TAXLOT`, `SERIAL`, `ACCOUNT_ID`, and `FULLADDRESS` points |
| `us-or-washington-county-intermap-property` | `intermap TLNO --report parcel|assessment|tax-map|all` |
| `us-or-washington-county-washcotax` | `tax-account` and `tax-statement` |

```bash
uv run python tools/query_oregon_washington_property.py survey-detail \
    survey 35242 --output "$WORKDIR/washington-survey.json"
uv run python tools/query_oregon_washington_property.py survey-document \
    plat 2026-021 --destination "$WORKDIR/2026-021.pdf" \
    --output "$WORKDIR/washington-plat-document.json"
uv run python tools/query_oregon_washington_property.py taxlots \
    2N2330002700 --geometry \
    --output "$WORKDIR/washington-taxlot.json"
uv run python tools/query_oregon_washington_property.py intermap \
    2N2330002700 --report assessment \
    --output "$WORKDIR/washington-intermap.json"
uv run python tools/query_oregon_washington_property.py tax-account R2069997 \
    --output "$WORKDIR/washington-tax-account.json"
```

The unified router provides only component-backed operations: Survey Explorer
API search, exact taxlot detail, and plat-document-number lookup; Survey
Explorer/current-taxlot geometry searches; situs address, parcel, and account
searches; exact Intermap parcel/tax-map reports; and exact WashCoTax accounts.
The direct tool retains the full kind/layer matrix and PDF retrieval commands.

`TLNO/TLID`, account/`PropertyQuickRefID`, `TAXLOT`, survey/plat numbers, and
`DocNumber` retain their native names through routing and ingestion. Intermap
parcel/assessment and WashCoTax account rows project as assessor records;
survey, geometry, situs, tax-map, and downloaded-document rows remain source
observations. Component monitors probe one selected source at a time and keep
stable contract/schema identity separate from current counts, sentinel
matches, and statement years.

Official alternatives in the source contract include Portland/Metro regional
taxlots, county recording/copy requests, Assessment and Taxation data
requests, Accela permit/planning records, and older land-use casefiles.

`query_oregon_washington_case_permits.py` keeps six additional Washington
County planning and permit components distinct from the assessor/survey
family:

| Source ID | Direct commands |
|---|---|
| `us-or-washington-county-casefiles` | `case-search`, `case-detail`, `case-review`, `case-decisions`, `case-staff` |
| `us-or-washington-county-taxlot-project-activity` | `taxlot-activity` for project/activity rows linked to an exact taxlot |
| `us-or-washington-county-building-permits` | `building-search` and `building-types` |
| `us-or-washington-county-permit-reports` | `permit-report project|activity|people|inspection|review` |
| `us-or-washington-county-accela-current-planning` | `accela-record`, `accela-document`, and `accela-download` |
| `us-or-washington-county-land-use-document-routes` | `document-routes` for case-number publication and request alternatives |

```bash
uv run python tools/query_oregon_washington_case_permits.py sources \
    --output "$WORKDIR/washington-case-permit-sources.json"
uv run python tools/query_oregon_washington_case_permits.py case-detail \
    L2500106 --output "$WORKDIR/washington-casefile.json"
uv run python tools/query_oregon_washington_case_permits.py taxlot-activity \
    2N2330002700 --collection all \
    --output "$WORKDIR/washington-taxlot-activity.json"
uv run python tools/query_oregon_washington_case_permits.py building-search \
    taxlot 2N2330002700 \
    --output "$WORKDIR/washington-building-taxlot.json"
uv run python tools/query_oregon_washington_case_permits.py permit-report \
    inspection 05214429 \
    --output "$WORKDIR/washington-inspection-report.json"
uv run python tools/query_oregon_washington_case_permits.py accela-record \
    L2500106 --output "$WORKDIR/washington-current-planning.json"
uv run python tools/query_oregon_washington_case_permits.py document-routes \
    L2500106 --output "$WORKDIR/washington-document-routes.json"
```

`NUMBER_KEY`, `SubmittalNo`, `B1_ALT_ID`, `PARCEL_NO`, and the three Accela CAP
parts preserve the casefile → taxlot → activity/report → CurrentPlanning join
chain. `Project` and `PermitNO` connect building index rows to project,
inspection, and review reports. Dated casefile and report rows project as
property events; undated index rows, vocabularies, the people report, Accela
record/document representations, and the document-route catalog stay as
source observations. These components do not contribute direct property
census roles and are planning/permit sources rather than court dockets.

Unified routes cover casefile search/parcel/event selectors, taxlot
project/activity search, building search/address/parcel/event selectors,
permit-report search/event selectors, and exact Accela or document-route event
lookups. For permit reports, `--search-field
project|activity|people|inspection|review` selects the native report type.

Building access is recorded by operation: taxlot search and the permit-type
vocabulary were anonymously verified, while the source challenge was observed
on permit-number, type/date/address, and individual-detail operations. The
monitor therefore probes the anonymous building operations separately. It
also probes four casefile routes, one taxlot route, all five report types, and
the three-request Accela case/detail/attachment chain; the route catalog probe
uses no network request. Rolling counts and sentinel identities remain outside
stable contract hashes.

When the casefile application does not expose an embedded document, the
adapter returns the separately attributed current-review, decision,
development-hub, frequently-discussed, hearing, CivicWeb, Accela, legacy
Laserfiche, and permit-records/request routes. The alternatives remain
discoverable without being treated as copies or corroboration of one another.

`query_oregon_multnomah_sail.py` keeps eight Multnomah County (`41051`) SAIL
components separately attributable:

| Source ID | Native contribution |
|---|---|
| `us-or-multnomah-sail-tax-parcels` | Current parcel, owner, addresses, roll values, building facts, latest deed/sale pivot, and geometry |
| `us-or-multnomah-sail-survey-records` | Survey point/index metadata and image join |
| `us-or-multnomah-sail-subdivision-plats` | Subdivision plat polygon, metadata, and image join |
| `us-or-multnomah-sail-partition-plats` | Partition plat polygon, metadata, and image join |
| `us-or-multnomah-sail-condominium-plats` | Condominium plat polygon, metadata, and image join |
| `us-or-multnomah-sail-road-surveys` | Road-survey polygon, metadata, and image join |
| `us-or-multnomah-sail-bearing-tree-public-land-corners` | Bearing-tree/public-land-corner point and document references |
| `us-or-multnomah-sail-field-book-quarter-sheets` | Field-book or quarter-sheet footprint and image join |

```bash
uv run python tools/query_oregon_multnomah_sail.py sources \
    --output "$WORKDIR/multnomah-sail-sources.json"
uv run python tools/query_oregon_multnomah_sail.py search R330254 \
    --source us-or-multnomah-sail-tax-parcels --field property-id \
    --geometry --output "$WORKDIR/multnomah-sail-tax-parcel.json"
uv run python tools/query_oregon_multnomah_sail.py search 05335 \
    --source us-or-multnomah-sail-survey-records --field survey-id \
    --match exact --geometry --output "$WORKDIR/multnomah-sail-survey.json"
uv run python tools/query_oregon_multnomah_sail.py image 05335 \
    --source us-or-multnomah-sail-survey-records \
    --output "$WORKDIR/multnomah-sail-image.json"
uv run python tools/query_oregon_multnomah_sail.py download 05335 \
    --source us-or-multnomah-sail-survey-records \
    --destination "$WORKDIR/05335.pdf" \
    --output "$WORKDIR/multnomah-sail-document.json"
```

`SURVEYID` joins each survey/image row to the county image viewer and resolved
PDF. Tax rows retain `PROPID`, `MAPTAXLOT`, `ALTACCTNUM`, address, `INST_NUM`,
legal description, roll and building fields, geometry, and assessor-map links.
The unified router exposes owner, address, account, parcel, map, instrument,
and general search for tax parcels; survey/image components expose general,
map, and `SURVEYID` instrument searches. Exact object lookup and viewer/PDF
retrieval remain in the direct adapter.

```bash
uv run python tools/query_property.py parcel R330254 \
    --source us-or-multnomah-sail-tax-parcels --jurisdiction 41051 \
    --geometry --ingest \
    --output "$WORKDIR/multnomah-sail-parcel-unified.json"
uv run python tools/query_property.py instrument 05335 \
    --source us-or-multnomah-sail-survey-records --jurisdiction 41051 \
    --ingest --output "$WORKDIR/multnomah-sail-survey-unified.json"
uv run python tools/public_records_monitor.py run \
    us-or-multnomah-sail-tax-parcels \
    us-or-multnomah-sail-survey-records \
    --output "$WORKDIR/multnomah-sail-probes.json"
```

Only the current tax-parcel component projects to the assessor grain and
contributes assessment-roll and current parcel-geometry census coverage. The
Multnomah Helion recorder supplies the separately attributed recorded-
instrument index. Survey, plat, road, corner, field-book, viewer, and PDF
representations stay as source observations and joins. Monitors keep stable
schema/contract identity separate from rolling counts, sentinels, and image
hashes.

The county describes the road-survey layer as incomplete. The source contract
therefore also surfaces County Surveyor assistance, MultcoPropTax,
MultcoRecords, DART and custom requests, older-record ordering, ORMAP, and
Portland/Metro regional taxlots. Regional and SAIL taxlots may share county
upstream data, so that overlap retains lineage rather than being treated as
independent corroboration.

`query_oregon_jackson_douglas_assessors.py` keeps two county ArcGIS layers
under their canonical component IDs:

| Source ID | County | Native identity and strongest fields |
|---|---:|---|
| `us-or-jackson-county-assessor-taxlots` | `41029` | Account plus Jackson map/taxlot forms; owner, mailing and situs fields; acreage; market/assessed land and improvements; classifications, selected building fields, tax codes, and polygon geometry |
| `us-or-douglas-county-assessor-parcels` | `41019` | `TAXID` parcel/account identity; owner, mailing and situs fields; acreage, assessed/market values, legal description, current-row instrument/sale-date reference, and polygon geometry |

```bash
uv run python tools/query_oregon_jackson_douglas_assessors.py sources \
    --output "$WORKDIR/jackson-douglas-assessor-sources.json"
uv run python tools/query_oregon_jackson_douglas_assessors.py owner \
    "O & C REVESTED GRANT" \
    --source us-or-douglas-county-assessor-parcels \
    --output "$WORKDIR/douglas-owner.json"
uv run python tools/query_oregon_jackson_douglas_assessors.py parcel 30-2E-100 \
    --source us-or-jackson-county-assessor-taxlots --geometry \
    --output "$WORKDIR/jackson-taxlot.json"
uv run python tools/query_oregon_jackson_douglas_assessors.py probe --all \
    --output "$WORKDIR/jackson-douglas-assessor-probes.json"
```

`search` accepts `auto`, `parcel`, `account`, `owner`, `address`, and
`instrument`; `owner`, `address`, `parcel`, and `account` are direct aliases.
Results retain native identifiers and source CRS, with optional WGS84 polygon
output. The shared projection adds typed Jackson map/taxlot aliases, normalized
Douglas `TAXID`, owners, addresses, assessment values, and geometry. Douglas's
current-row instrument/sale-date fields become an
`assessor_current_parcel_reference` sale observation. The separately cited
Douglas data products carry certified rolls, land/improvement segments,
three-year sales, map images, and shapefiles; Jackson's assessment maps, JIM
map, data-request route, and recorder remain separate components.

`query_oregon_jackson_property_events.py` treats Jackson's three published
event layers as three source identities:

| Source ID | Native event |
|---|---|
| `us-or-jackson-county-building-permits` | Building-permit `PERMITID` plus type, description, status/dates, cost, applicant/contractor, address, map-taxlot, Accela identifiers/link, and centroid |
| `us-or-jackson-county-land-use-permits` | Land-use `PERMITID` plus 1980-present layer coverage, type, description, status/dates, applicant, address, map-taxlot, Accela identifiers/link, and centroid |
| `us-or-jackson-county-code-compliance` | Code-compliance `VIOLATIONID` plus case/type, description, status/dates, published owner, address, map-taxlot, related identifiers/link, and centroid |

```bash
uv run python tools/query_oregon_jackson_property_events.py sources \
    --output "$WORKDIR/jackson-property-event-sources.json"
uv run python tools/query_oregon_jackson_property_events.py search solar \
    --field description \
    --source us-or-jackson-county-building-permits \
    --output "$WORKDIR/jackson-building-solar.json"
uv run python tools/query_oregon_jackson_property_events.py map-taxlot 30-2E-100 \
    --source us-or-jackson-county-land-use-permits --geometry \
    --output "$WORKDIR/jackson-land-use-taxlot.json"
uv run python tools/query_oregon_jackson_property_events.py probe --all \
    --output "$WORKDIR/jackson-property-event-probes.json"
```

`search` accepts `auto`, `native_id`, `case`, `address`, `person`,
`map_taxlot`, `status`, `type`, and `description`; exact `record`, `address`,
`person`, and `map-taxlot` commands are also available. Projection retains a
`property_event` identity built from source ID, jurisdiction, native
permit/violation ID, and ArcGIS `OBJECTID`, so repeated native IDs remain
separate observations. It stores dates, status, cost, location, optional
point, event parties, and linked Accela representations. A published
map-taxlot produces an assessor-parcel link only for one exact normalized
Jackson alias, with the resolution method recorded as exact, ambiguous, or
unresolved. Event parties are not projected as title ownership.

`query_oregon_jackson_accela.py` resolves the record-detail links published by
Jackson's building and land-use ArcGIS layers:

| Source ID | Module | Commands and representations |
|---|---|---|
| `us-or-jackson-county-accela-building-details` | `building` | `record`, `record-url`, `document`, and `download` for record detail, status, related records, fees, inspections, attachments, document metadata, and document binaries |
| `us-or-jackson-county-accela-planning-details` | `planning` | The same representations for land-use records |

```bash
uv run python tools/query_oregon_jackson_accela.py sources \
    --output "$WORKDIR/jackson-accela-sources.json"
uv run python tools/query_oregon_jackson_accela.py record \
    building 26CAP-00000-006GM \
    --output "$WORKDIR/jackson-building-detail.json"
uv run python tools/query_oregon_jackson_accela.py record-url \
    'https://aca-oregon.accela.com/oregon/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=006GM&agencyCode=JACKSON_CO' \
    --output "$WORKDIR/jackson-accela-record.json"
uv run python tools/query_oregon_jackson_accela.py document \
    building 16767279 \
    --output "$WORKDIR/jackson-document.json"
uv run python tools/query_oregon_jackson_accela.py download \
    building 26CAP-00000-006GM 16767279 \
    --destination "$WORKDIR/jackson-building-permit.pdf" \
    --output "$WORKDIR/jackson-building-permit-receipt.json"
uv run python tools/query_oregon_jackson_accela.py probe --all \
    --output "$WORKDIR/jackson-accela-probes.json"
```

The adapter preserves agency, module, all three CAP components, native record
number, session-bound attachment rows, stable Accela document numbers,
document-detail pages, and binary receipts. These are linked representations
of the separately sourced ArcGIS event row. Jackson code-compliance detail is
not exposed through the same anonymous Accela route; use the official
`us-or-jackson-county-code-compliance` ArcGIS component and the county
records-request route for unpublished detail.

`query_deschutes_property.py` adds the official relationship-aware Deschutes
County service. Its polygon layer is joined to eight declared account, retired
number, improvement, mailing, owner, property-class, roll-value, and serial
cross-reference relationships. The sales table is a separate component in the
same service joined by the published taxlot key; it is retained as a keyed
complement rather than relabeled as an ArcGIS relationship.

```bash
uv run python tools/query_deschutes_property.py search "VACH" \
    --field owner --limit 25 \
    --output "$WORKDIR/deschutes-owner.json"
uv run python tools/query_deschutes_property.py parcel 141031B000700 \
    --geometry --output "$WORKDIR/deschutes-parcel.json"
uv run python tools/query_property.py account 135278 \
    --source us-or-deschutes-county-taxlots --jurisdiction 41017 \
    --ingest --output "$WORKDIR/deschutes-account-unified.json"
uv run python tools/query_deschutes_property.py probe \
    --output "$WORKDIR/deschutes-source-probe.json"
```

The exact parcel result includes current and retired account links, owners,
situs and mailing addresses, roll values, improvements, property classes,
sales, component schema identities, source counts, and optional WGS84
geometry. The parcel's published DIAL link is a distinct official account
route; its tax/payment history, reports, development records, and
recorder-image links are tracked as a separate integration.

`query_deschutes_laserfiche.py` follows the DIAL account-to-document index into
the county CDD Laserfiche repository. The Laserfiche entry ID remains the
document identity; account ID and map/taxlot remain cross-source joins.
Document metadata, folder metadata, electronic files, and PDFs generated from
historical imaged pages are preserved as distinct representations. The
repository-wide anonymous search controls are not exposed in the observed
public session, so DIAL account discovery, Oregon ePermitting, the taxlot
service, and the county records-request channel remain useful complements.

`query_oregon_helion_property.py` implements six county Helion/ORCATS
Property Search Online tenants without merging their county contracts:

| Source ID | County GEOID | Native selectors observed |
|---|---:|---|
| `us-or-umatilla-helion-property` | `41059` | account, tax account, name, address, map/taxlot, legal |
| `us-or-morrow-helion-property` | `41049` | account, tax account, name, address, map/taxlot, legal |
| `us-or-polk-helion-property` | `41053` | account, tax account, name, address, map/taxlot, legal |
| `us-or-tillamook-helion-property` | `41057` | account, tax account, name, address, map/taxlot, legal |
| `us-or-columbia-helion-property` | `41009` | tax account, name, address, map/taxlot |
| `us-or-coos-helion-property` | `41011` | account, tax account, name, address, map/taxlot |

```bash
uv run python tools/query_oregon_helion_property.py search smith \
    --field name --source us-or-morrow-helion-property --limit 10 \
    --output "$WORKDIR/morrow-pso-name.json"
uv run python tools/query_oregon_helion_property.py detail 171 \
    --roll-type R --source us-or-morrow-helion-property \
    --output "$WORKDIR/morrow-pso-account.json"
uv run python tools/query_property.py account 171 \
    --source us-or-morrow-helion-property --jurisdiction 41049 --ingest \
    --output "$WORKDIR/morrow-pso-unified.json"
uv run python tools/query_oregon_helion_property.py probe \
    --source us-or-tillamook-helion-property \
    --output "$WORKDIR/tillamook-pso-probe.json"
```

Unified `search`/`owner`, `address`, `parcel`, and `account` operations map to
the selected tenant's name, address, map/taxlot, and detail routes. The direct
adapter retains the additional tax-account and legal selectors where
published. The map/taxlot selector resolves a source identifier; parcel
geometry remains on each county's distinct map or GIS complement.

Rendered searches showed a native ten-row page. Continuation is bound to the
source, field, query, page boundary, and last emitted identity. Full detail
retains owners and addresses, certified-roll and historical values, current
tax balance and payoff data, payment and sale history, improvements, special
assessments, notations, account history, and linked reports/files. The shared
ingester projects the common parcel, owner, address, assessment, and sale
fields and retains the complete source record. Morrow name continuation and
account `171/R`, Columbia account `28102/R`, and all six rendered source forms
were live-verified. Tillamook's observed long-poll fallback is recorded as a
runtime detail, while its source contract and county-specific historical
roll, tax-map, sales, foreclosure, and tax-deed complements remain separate.

`query_oregon_smart_search.py` exposes the rendered Oregon Circuit and Tax
Court Smart Search contract as `us-or-ojd-smart-search`:

```bash
uv run python tools/query_oregon_smart_search.py sources \
    --output "$WORKDIR/oregon-smart-search-sources.json"
uv run python tools/query_oregon_smart_search.py probe \
    --output "$WORKDIR/oregon-smart-search-probe.json"
uv run python tools/query_oregon_smart_search.py options CaseStatus \
    --output "$WORKDIR/oregon-smart-search-statuses.json"
uv run python tools/query_oregon_smart_search.py prepare "EXAMPLE LLC" \
    --search-by BusinessName --location Multnomah --case-type Civil \
    --output "$WORKDIR/oregon-smart-search-handoff.json"
```

`runtime-check` reports the local rendered-browser runtime. `probe` validates
the current POST action, named controls, page settings, reCAPTCHA state, and
selector contract. `options` accepts `JudicialOfficerSearchBy`, `NameSuffix`,
`CourtLocation`, `SearchBy`, `CaseType`, `CaseStatus`, `JudicialOfficer`,
`JudgmentType`, `WarrantType`, or `WarrantStatus`.

`prepare` accepts the source's general, party, case, judgment, and warrant
selectors and emits a `public-records-result/1.0` envelope. Its sole
`interactive_court_search_handoff` record preserves the complete
form-affecting query fingerprint, native form values, checkbox state, and
prefill instructions. It explicitly identifies itself as a prepared search,
not a returned case record.

`query_oregon_ojcin_products.py` catalogs and probes six source identities:
the public directory `us-or-ojd-statewide-court-data-products` and the five
components `us-or-ojcin-oeci-subscription`,
`us-or-ojcin-acms-subscription`,
`us-or-ojcin-standard-report-package`,
`us-or-ojcin-bulk-data-transfer`, and
`us-or-osca-statewide-court-data-request`.

```bash
uv run python tools/query_oregon_ojcin_products.py products \
    --output "$WORKDIR/oregon-court-data-products.json"
uv run python tools/query_oregon_ojcin_products.py search "case index" \
    --output "$WORKDIR/oregon-product-search.json"
uv run python tools/query_oregon_ojcin_products.py handoff \
    us-or-ojcin-oeci-subscription \
    --output "$WORKDIR/oregon-oeci-handoff.json"
uv run python tools/query_oregon_ojcin_products.py probe \
    --output "$WORKDIR/oregon-ojcin-route-probe.json"
uv run python tools/query_oregon_ojcin_products.py inspect-delivery \
    us-or-ojcin-bulk-data-transfer /path/to/acquired-delivery \
    --delivery-version 2026-07 --correction-state original \
    --specification-ref /path/to/delivery-specification.pdf \
    --output "$WORKDIR/oregon-delivery-receipt.json"
```

`products` and the product-metadata `search` command return the shared result
envelope. `handoff` and the 13-representation official-route probe use
`oregon-ojcin-products/1.0`. `inspect-delivery` uses
`oregon-ojcin-delivery-receipt/1.0` and records the selected product,
delivery version and receipt basis, provider and correction fields, artifact
set and per-file hashes, observed formats, ZIP members, specification
references, and separately acquired case-document references. It records
`rows_interpreted=false` until an acquired delivery and its accompanying
specification establish row semantics.

The earlier Smart Search ID
`us-or-ojd-free-circuit-tax-record-search` is replaced by
`us-or-ojd-smart-search`. The earlier `us-or-ojcin` umbrella is now the public
directory plus separate OECI and ACMS products; `us-or-ojcin-bulk-data` is
split into the standard report and approved bulk-transfer products; and
`us-or-ojd-statewide-data-request` is now
`us-or-osca-statewide-court-data-request`. These are visible source-history
mappings rather than alternate record identities.

`query_oregon_appellate.py` implements the official anonymous Supreme Court
and Court of Appeals API:

```bash
uv run python tools/query_oregon_appellate.py search-party \
    "EXAMPLE ORGANIZATION" --court coa --limit 25 \
    --output "$WORKDIR/oregon-appellate-party.json"
uv run python tools/query_oregon_appellate.py case A182332 --court coa \
    --output "$WORKDIR/oregon-appellate-case.json"
uv run python tools/query_oregon_appellate.py docket A182332 --court coa \
    --output "$WORKDIR/oregon-appellate-docket.json"
uv run python tools/query_oregon_appellate.py document-metadata A182332 \
    --court coa --output "$WORKDIR/oregon-appellate-documents.json"
uv run python tools/query_oregon_appellate.py calendar \
    --after 2026-01-01 --court supreme \
    --output "$WORKDIR/oregon-appellate-calendar.json"
uv run python tools/query_oregon_appellate.py probe \
    --output "$WORKDIR/oregon-appellate-probe.json"
```

Search cursors are query-bound and preserve the source's reported totals and
10,000-result ceiling state. Case aggregation reports docket, parties and
attorneys, hearings, judgments, groups, and document metadata independently.
The verified A182332 case currently returns a server error for its judgments
subresource while the other components remain available, so the aggregate is
explicitly partial rather than discarded. A document's metadata and its
retrievable-file state are separate fields.

`query_oregon_appellate_calendars.py` follows the current official SharePoint
lists that replaced the historical `/coadocket` and `/sclist` pages:

```bash
uv run python tools/query_oregon_appellate_calendars.py search \
    --court coa --current --limit 25 \
    --output "$WORKDIR/oregon-coa-calendar.json"
uv run python tools/query_oregon_appellate_calendars.py search \
    --court supreme --case-number S072119 \
    --output "$WORKDIR/oregon-supreme-calendar.json"
uv run python tools/query_state_courts.py calendar S072119 \
    --source us-or-supreme-court-calendar --ingest \
    --output "$WORKDIR/oregon-supreme-calendar-unified.json"
uv run python tools/query_oregon_appellate_calendars.py probe --court supreme \
    --output "$WORKDIR/oregon-supreme-calendar-probe.json"
```

The Court of Appeals list traversal returned all 321 declared items across
four API pages even though the official view has a 300-row limit. The Supreme
Court traversal returned all 149 declared items and preserves its published
attachment links. List growth and event-date movement are monitor details;
the drift fingerprint represents the stable page/list/view contract.

`query_oregon_court_calendar.py` follows the official Circuit and Tax Court
same-session location/form/search workflow:

```bash
uv run python tools/query_oregon_court_calendar.py locations \
    --output "$WORKDIR/oregon-calendar-locations.json"
uv run python tools/query_oregon_court_calendar.py judicial-officers \
    --location Deschutes \
    --output "$WORKDIR/oregon-calendar-officers.json"
uv run python tools/query_oregon_court_calendar.py search \
    --location Deschutes --after 2026-07-29 --before 2026-07-29 \
    --output "$WORKDIR/oregon-circuit-calendar.json"
uv run python tools/query_oregon_court_calendar.py search \
    --location "Tax Court" --case-number TC-MD-240001R \
    --output "$WORKDIR/oregon-tax-calendar-case.json"
uv run python tools/query_state_courts.py calendar Deschutes \
    --source us-or-circuit-tax-court-calendars \
    --hearing-date 2026-07-29 --ingest \
    --output "$WORKDIR/oregon-calendar-unified.json"
uv run python tools/query_oregon_court_calendar.py probe \
    --location Deschutes \
    --output "$WORKDIR/oregon-calendar-probe.json"
```

Location, case, party/business, attorney name/bar number, judicial-officer,
and date selectors retain their source-native semantics. Returned hearings are
grouped under stable case identities and stored as docket events. The source
accepts current/forward dates within 90 days. Its guide describes 400 displayed
results, while a live statewide response returned 550 rows with an explicit
truncation alert; the adapter retains both observations, preserves all returned
rows, and does not impose a 400-row local cap.

`query_oregon_court_directories.py` retrieves four separate OJD SharePoint
lists for state courts, state judges, municipal/justice courts, and their judge
assignments:

```bash
uv run python tools/query_oregon_court_directories.py sources \
    --output "$WORKDIR/oregon-directory-sources.json"
uv run python tools/query_oregon_court_directories.py views \
    --source us-or-state-judge-directory \
    --output "$WORKDIR/oregon-judge-views.json"
uv run python tools/query_oregon_court_directories.py search Deschutes \
    --source us-or-state-court-directory \
    --output "$WORKDIR/oregon-court-directory.json"
uv run python tools/query_oregon_court_directories.py list \
    --source us-or-local-judge-registry --limit 50 \
    --output "$WORKDIR/oregon-local-judges.json"
uv run python tools/query_oregon_court_directories.py discovery \
    --query Bend \
    --output "$WORKDIR/oregon-local-source-candidates.json"
uv run python tools/query_oregon_court_directories.py probe \
    --source us-or-local-court-registry \
    --output "$WORKDIR/oregon-directory-probe.json"
```

The source-native flow is an anonymous page bootstrap followed by cookie-bound
SOAP calls without a `SOAPAction` header. Results preserve raw SharePoint
fields, semantic identities, list/view provenance, timestamps, and complete
rowset state. Local cursors bind the source, view, query, snapshot, and prior
boundary. The discovery operation turns published local-court websites into
attributed candidates for subsequent adapter work.

`query_eugene_municipal_court.py` implements eight independently attributed
Oregon-area Tyler Municipal Record Search tenants. Five currently expose
public case and docket components: Eugene, Hermiston, Linn County Justice
Court, Medford, and Springfield. Direct probes observed case sign-in plus a
missing docket route for Clackamas County Justice Court, and sign-in on both
components for Corvallis and the Confederated Tribes of Grand Ronde Tribal
Court.

| Tenant key | Source ID | Direct case / docket state |
|---|---|---|
| `eugene` | `us-or-eugene-municipal-record-search` | public / public |
| `hermiston` | `us-or-hermiston-municipal-record-search` | public / public |
| `linn-county` | `us-or-linn-county-justice-record-search` | public / public |
| `medford` | `us-or-medford-municipal-record-search` | public / public |
| `springfield` | `us-or-springfield-municipal-record-search` | public / public |
| `clackamas` | `us-or-clackamas-county-justice-record-search` | login required / not found |
| `corvallis` | `us-or-corvallis-municipal-record-search` | login required / login required |
| `grand-ronde` | `us-tribal-grand-ronde-record-search` | login required / login required |

```bash
uv run python tools/query_eugene_municipal_court.py search \
    --tenant medford --citation M100 \
    --output "$WORKDIR/medford-citation-search.json"
uv run python tools/query_eugene_municipal_court.py dockets \
    --tenant hermiston --date-from 2026-07-29 --date-to 2026-07-31 \
    --output "$WORKDIR/hermiston-dockets.json"
uv run python tools/query_eugene_municipal_court.py docket \
    --tenant hermiston 20260730090000 ARR 1 \
    --output "$WORKDIR/hermiston-docket-detail.json"
uv run python tools/query_eugene_municipal_court.py case \
    --tenant eugene E018359 01 \
    --output "$WORKDIR/eugene-case-detail.json"
uv run python tools/query_eugene_municipal_court.py tenants \
    --output "$WORKDIR/oregon-tyler-tenants.json"
uv run python tools/query_eugene_municipal_court.py probe \
    --tenant corvallis --output "$WORKDIR/corvallis-probe.json"
```

Selector vocabulary is tenant-specific: the public forms expose different
subsets of name, citation, docket, police-case, plate, and VIN search.
Server-rendered pages and local cursors bind to the tenant, query, snapshot,
and prior record. The OJD local-court registry is a discovery source, while
the component states above come from direct tenant probes.

Official alternatives remain attached to their own tenant and role. Eugene's
JustFOIA form is a record-request/file-delivery complement; Clackamas and
Corvallis retain their county or city request and archive routes. Grand Ronde
retains Tribal Court request, rule, and form routes for court-record
requesters separately from Tribal Records Center routes identified for tribal
members.

`query_oregon_court_documents.py` similarly shares CONTENTdm transport while
keeping seven official Law Library collections separate:

| Source ID | Collection |
|---|---|
| `us-or-law-library-supreme-opinions` | Supreme Court opinions |
| `us-or-law-library-coa-opinions` | Court of Appeals opinions |
| `us-or-law-library-tax-court-decisions` | Tax Court decisions and orders |
| `us-or-law-library-supreme-briefs` | Supreme Court briefs |
| `us-or-law-library-coa-briefs` | Court of Appeals briefs |
| `us-or-law-library-coa-orders-interest` | Court of Appeals orders of interest |
| `us-or-law-library-multnomah-presiding-orders` | Multnomah County presiding-judge orders |

```bash
uv run python tools/query_oregon_court_documents.py sources \
    --output "$WORKDIR/oregon-court-collections.json"
uv run python tools/query_oregon_court_documents.py search A182332 \
    --source us-or-law-library-coa-opinions --field all \
    --output "$WORKDIR/oregon-coa-search.json"
uv run python tools/query_oregon_court_documents.py latest \
    --source us-or-law-library-supreme-opinions --limit 25 \
    --output "$WORKDIR/oregon-supreme-latest.json"
uv run python tools/query_oregon_court_documents.py item 42527 \
    --source us-or-law-library-coa-opinions \
    --output "$WORKDIR/oregon-coa-item.json"
uv run python tools/query_oregon_court_documents.py download 42527 \
    "$WORKDIR/oregon-coa-opinion.pdf" \
    --source us-or-law-library-coa-opinions \
    --output "$WORKDIR/oregon-coa-download.json"
uv run python tools/query_oregon_court_documents.py probe --all \
    --output "$WORKDIR/oregon-court-document-probes.json"
```

Search follows the collection's reported count and returns a source-bound
cursor when the caller selects a smaller window. `item` retains structured
metadata, source-extracted text, compound-page state, and document identity.
`download` resolves both ordinary and compound CONTENTdm items to a verified
PDF and writes an atomic receipt. References use
`ORCOURT-DOC:<source-id>:<item-id>` for document records and
`ORCOURT-ARTIFACT:<source-id>:<sha256>` for retained files.

These collections are document corpora rather than a combined case register.
The catalog connects them to the official appellate case/docket API, the free
Circuit and Tax Court discovery portal, OJCIN, official calendars, case-copy
and statewide-data request routes, and separate state/local court and judge
directories. Each of the seven collections, each of the three regional/state
taxlot publishers, the Deschutes relationship service, and the appellate API
has its own monitor observation so component drift is visible even when a
shared landing service remains online.

### Denver Public Trustee foreclosure files

`query_denver_foreclosures.py` implements the direct GTS route for
`us-co-denver-public-trustee-gts`.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Exact, filtered, and source-wide searches
uv run python tools/query_denver_foreclosures.py search \
    --foreclosure-number 2026-000418 \
    --output "$WORKDIR/denver-foreclosure.json"
uv run python tools/query_denver_foreclosures.py search \
    --owner "SMITH" --status Active --limit 25 \
    --output "$WORKDIR/denver-foreclosure-owner.json"
uv run python tools/query_denver_foreclosures.py search \
    --show-all --limit 25 \
    --output "$WORKDIR/denver-foreclosure-page.json"

# Complete detail and document-index records
uv run python tools/query_denver_foreclosures.py detail 2026-000418 \
    --output "$WORKDIR/denver-foreclosure-detail.json"
uv run python tools/query_denver_foreclosures.py documents 2026-000418 \
    --output "$WORKDIR/denver-foreclosure-documents.json"

# Retrieve one source document by the stable ID returned by `documents`
uv run python tools/query_denver_foreclosures.py download \
    2026-000418 \
    1d69be5337f3de9a8e159ded1fcb7b8729ded0ea2d7c4122295136ffb9ca7118 \
    --destination "$WORKDIR/denver-foreclosure-document.pdf" \
    --output "$WORKDIR/denver-foreclosure-download.json"

# Verify the search, paging, detail-section, and document-index contracts
uv run python tools/query_denver_foreclosures.py probe \
    --foreclosure-number 2026-000418 \
    --output "$WORKDIR/denver-foreclosure-probe.json"
```

The operations are `search`, `detail`, `documents`, `download`, and `probe`.
Search accepts foreclosure number, grantor, current owner, ZIP code, street,
subdivision, status, NED date range, sold date range, scheduled-sale date
range, and expedited-sale status. `--show-all` invokes the portal's native
source-wide operation. Omitting `--limit` follows every reported page; a
caller-selected limit returns a query-bound
`denver-gts:v1:page:N:offset:N:...` continuation cursor when more results
remain.

The July 29, 2026 live probe reported 5,062 files with 25 rows per native page
and retained that total through tested later pages. It verified the portal's
zero-record response and all 12 sections: Address, Bankruptcy, Basics, Cure,
Deed, Law Firm, Mailings, Publications, Lienor Redemption, Sale Information,
Withdrawal, and View Documents. Sentinel `2026-000418` contained 15 indexed
documents: 13 TIF, one PDF, and one DOC. A native TIF entry retrieved through
the source viewer returned a valid PDF.

Normalized case rows use `record_kind=foreclosure_case` and
`record_scope=index`, `detail`, or `documents`; the Public Trustee number is
their stable identity. Indexed files receive a stable document ID derived from
the case number and source filename. Retrieved files use
`record_kind=document_artifact`.

Join GTS rows to `us-co-denver-parcels` and
`us-co-denver-spatialest-property-tax` by address and owner observations, to
`us-co-denver-recorder-publicsearch` by NED/deed reception number, to
`us-co-denver-realforeclose-auctions` by Public Trustee number, address, and
scheduled sale date, and to the cataloged Denver/Colorado court routes for
related litigation.

### Denver Treasury delinquent-tax workbook

`query_denver_delinquent_tax.py` implements the direct annual XLSX route for
`us-co-denver-delinquent-real-property-tax-list`.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Discover and deeply probe the current official release
uv run python tools/query_denver_delinquent_tax.py discover \
    --output "$WORKDIR/denver-tax-release.json"
uv run python tools/query_denver_delinquent_tax.py probe \
    --output "$WORKDIR/denver-tax-probe.json"

# Download and inspect a retained workbook
uv run python tools/query_denver_delinquent_tax.py download \
    --destination "$WORKDIR/denver-delinquent-tax.xlsx" \
    --output "$WORKDIR/denver-tax-download.json"
uv run python tools/query_denver_delinquent_tax.py inspect \
    "$WORKDIR/denver-delinquent-tax.xlsx" \
    --output "$WORKDIR/denver-tax-inspection.json"

# Auto-discover and search the current official workbook
uv run python tools/query_denver_delinquent_tax.py search \
    --parcel 05044-12-043-000 \
    --output "$WORKDIR/denver-tax-parcel.json"
uv run python tools/query_denver_delinquent_tax.py search \
    --owner "HOLDINGS LLC" --tax-year 2024 --partially-paid-only \
    --output "$WORKDIR/denver-tax-owner.json"

# Search a retained workbook with a caller-selected ceiling and cursor
uv run python tools/query_denver_delinquent_tax.py search \
    --artifact "$WORKDIR/denver-delinquent-tax.xlsx" \
    --address "LARIMER ST" --max-records 25 \
    --output "$WORKDIR/denver-tax-address.json"
uv run python tools/query_denver_delinquent_tax.py search \
    --artifact "$WORKDIR/denver-delinquent-tax.xlsx" \
    --address "LARIMER ST" --cursor "$DENVER_TAX_CURSOR" \
    --output "$WORKDIR/denver-tax-resume.json"
```

The operations are `discover`, `probe`, `download`, `inspect`, and `search`.
Search filters are `--query`, `--parcel`/`--account`, `--owner`, `--address`,
`--tax-year`, `--tax-sale-only`, and `--partially-paid-only`. It automatically
discovers and temporarily downloads the current official artifact unless
`--artifact` supplies a local workbook. `--max-records` is optional; when it
selects a window with further matches, the result is `partial` with a
`denver-delinquent-tax:v1:criteria:<sha256>:artifact:<sha256>:row:N` cursor.
Set `DENVER_TAX_CURSOR` to the exact `next_cursor` from the preceding response;
it is bound to both the filters and the immutable workbook/release identity.

The July 29, 2026 live probe verified the 2024 release at 984,387 bytes and
8,373 data rows, distributed as 2019: 1, 2023: 8, and 2024: 8,364. Its
full-file SHA-256 was
`b874a7d4dcf0814cbe044284568ae5ae6e2867e7655ce6f3944bf6f9d3e411b7`;
the parsed workbook-schema fingerprint was
`0e038c4bfc0c29e5073d6561c4e70daa2f4fa89298a409089f241ff9ff324a20`,
and the adapter-schema fingerprint was
`95c965cbadb42c48a66b1d247aa0fec669aa178688432a279f867c52890fffb6`.
The 14 source fields cover primary and additional owner names, parcel ID and
address, parcel valuation, tax, interest, fees/advertising, total owed,
tax-sale and partial-payment indicators, and legal description.
`(tax_year, parcel_id)` was unique in the live workbook.

Normalized search rows use `property_tax_delinquency` and expose
`native_parcel_id`, `native_account_id`, `stable_account_key`, `tax_year`,
`owner_names`, `situs_address`, `release_date`, `delinquency_status`,
`amounts`, `valuation`, the two source indicators, legal description,
artifact/schema provenance, and the exact native row under `raw`. The
workbook does not distinguish its published delinquency categories per row,
so the row keeps a null `delinquency_category` plus the release-level category
list.

### Property adapter pilots

#### Georgia county property directory and statewide land-index handoff

`query_georgia_property_sources.py` searches Georgia DOR's county property
route directory, summarizes destination platform families, and verifies the
GSCCCA statewide deed/lien/plat index acquisition path.

```bash
uv run python tools/query_georgia_property_sources.py sources \
    --output "$WORKDIR/ga-property-sources.json"
uv run python tools/query_georgia_property_sources.py manifest \
    --source us-ga-dor-county-property-records-directory \
    --output "$WORKDIR/ga-dor-manifest.json"
uv run python tools/query_georgia_property_sources.py directory \
    --county Fulton --output "$WORKDIR/ga-fulton-route.json"
uv run python tools/query_georgia_property_sources.py directory qpublic \
    --limit 50 --output "$WORKDIR/ga-qpublic-routes.json"
uv run python tools/query_georgia_property_sources.py platforms \
    --output "$WORKDIR/ga-platforms.json"
uv run python tools/query_georgia_property_sources.py handoff \
    --output "$WORKDIR/ga-gsccca-handoff.json"
uv run python tools/query_georgia_property_sources.py probe \
    --source us-ga-gsccca-real-estate-index \
    --output "$WORKDIR/ga-gsccca-probe.json"

uv run python tools/query_property.py search Fulton \
    --source us-ga-dor-county-property-records-directory \
    --jurisdiction 13 --output "$WORKDIR/ga-shared-directory.json"
uv run python tools/query_property.py discovery \
    --source us-ga-gsccca-real-estate-index \
    --jurisdiction 13 --output "$WORKDIR/ga-gsccca-discovery.json"
uv run python tools/public_records_monitor.py run \
    us-ga-dor-county-property-records-directory \
    us-ga-gsccca-real-estate-index \
    --output "$WORKDIR/ga-property-monitors.json"
```

The verified DOR snapshot published 158 of 159 counties, omitting White. Its
destinations grouped into 133 legacy qPublic, five Schneider qPublic, and 20
county-hosted routes. Atkinson was the only row whose two published links
disagreed; the description link pointed to Bacon County. GSCCCA states
statewide index coverage and deed data since at least January 1, 1999. A free
limited-use account returns index summaries but not images. The adapter emits
route and acquisition snapshots, leaving county parcel records, local clerk
records, and account search results attributable to their respective sources.

D.C. property records use four separately attributable components under
`us-dc-itspe-property-lineage`: ITSPE assessment/tax accounts (layer 53),
common-ownership polygons (layer 40), CAMA sale observations (layer 57), and
Surveyor documents (layer 69). All join on SSL. The verified source counts
were 221,400 accounts, 137,400 physical common-ownership polygons, 421,472
sales, and 184,449 Surveyor documents. Account/polygon grain is not assumed
one-to-one, and overlapping ITSPE values are same-lineage rather than
independent corroboration. The actual instrument index is the separately
cataloged registered-user Recorder PublicSearch route
`us-dc-recorder-of-deeds-public-records`; CAMA and Surveyor records are
complements, not substitutes for that index.

```bash
uv run python tools/query_dc_property.py sources \
    --output "$WORKDIR/dc-property-sources.json"
uv run python tools/query_dc_property.py assessment "PAR 01300036" \
    --field ssl --output "$WORKDIR/dc-account.json"
uv run python tools/query_dc_property.py geometry "PAR 01300036" \
    --field ssl --geometry --output "$WORKDIR/dc-polygon.json"
uv run python tools/query_dc_property.py sales "PAR 01300036" \
    --output "$WORKDIR/dc-sales.json"
uv run python tools/query_dc_property.py surveys \
    9B59CB35-62CB-C473-B297-59097C200000 --field document \
    --output "$WORKDIR/dc-survey.json"
uv run python tools/query_dc_property.py probe assessment \
    --output "$WORKDIR/dc-account-probe.json"
uv run python tools/public_records_monitor.py run \
    us-dc-itspe-property-lineage us-dc-itspe-public-extract \
    us-dc-common-ownership-polygons us-dc-cama-property-sales \
    us-dc-surveyor-document-system \
    --output "$WORKDIR/dc-property-monitors.json"
```

Washington State Archives record series 14 is implemented as
`us-wa-state-archives-digital-recorded-land`. It exposes anonymous title
inventory, title metadata, county-scoped party search/browse, and exact
detail keyed by a 32-hex record ID across 26 county titles. Asotin, Columbia,
Douglas, Ferry,
Garfield, Grant, King, Kittitas, Lincoln, San Juan, Skagit, Stevens, and
Wahkiakum use separately listed official recorder routes. The source is not
classified as statewide: each title retains its own date coverage and image
statement, including the Skamania 2014-2015 gap.

Search rows are occurrence-preserving index-party records and can repeat one
instrument ID. Detail supplies the instrument and ordered party list, with
published company/person names kept intact. Listed image objects remain
metadata-only—with null acquisition fields and page count—until bytes are
acquired. The archive's document-generation step is a separate
`generateDocument` reCAPTCHA queue and is not part of the five-request monitor.
Ferry TaxSifter and the statewide parcel services remain separate
assessment/parcel lineages rather than recorded-instrument proof.

```bash
uv run python tools/query_washington_digital_archives_land.py inventory \
    --refresh --output "$WORKDIR/wa-land-inventory.json"
uv run python tools/query_washington_digital_archives_land.py metadata \
    --county adams --refresh --output "$WORKDIR/wa-land-title.json"
uv run python tools/query_washington_digital_archives_land.py search \
    --county adams --last-name SMITH --first-name AMOS \
    --start-year 2020 --end-year 2020 --limit 50 \
    --output "$WORKDIR/wa-land-search.json"
uv run python tools/query_washington_digital_archives_land.py detail \
    64742C2528B8C19D43FCC54D20DC97D0 \
    --output "$WORKDIR/wa-land-detail.json"
uv run python tools/query_washington_digital_archives_land.py alternatives \
    --output "$WORKDIR/wa-land-alternatives.json"
uv run python tools/query_property.py owner "ACME HOLDINGS, LLC" \
    --source us-wa-state-archives-digital-recorded-land \
    --jurisdiction 53001 --search-field company \
    --output "$WORKDIR/wa-land-shared-owner.json"
uv run python tools/query_property.py instrument \
    64742C2528B8C19D43FCC54D20DC97D0 \
    --source us-wa-state-archives-digital-recorded-land \
    --jurisdiction 53001 --ingest \
    --output "$WORKDIR/wa-land-shared-detail.json"
uv run python tools/public_records_monitor.py run \
    us-wa-state-archives-digital-recorded-land \
    --output "$WORKDIR/wa-land-monitor.json"
```

Monitor stable hashes cover operation, identity, and observed schema
contracts. Growing title counts, coverage-year labels, search totals, and
current detail values remain rolling observations. The monitor does not call
the document-generation queue.

Washington TaxSifter uses the umbrella
`us-wa-taxsifter-property-family` and eleven county leaf sources for Adams,
Douglas, Ferry, Franklin, Kittitas, Lincoln, Mason, Okanogan, Pacific,
Skamania, and Whitman. Ten tenants completed the source-native search,
assessor, treasurer, appraisal, and sales operations. Mason retains an
operation-scoped JavaScript/cookie challenge observation; it does not change
the other tenant states.

The client follows the real WebForms session transition when a fresh request
lands on the disclaimer: it posts the returned hidden fields and agreement
control, then retries the requested page in the same session. An authoritative
zero-result response remains accessible. General-search continuation follows
native pages without an adapter default result ceiling. Sales results preserve
the publisher's count separately from rows returned in the current response;
the observed postback controls are not treated as verified continuation.
The family monitor retains the complete tenant-by-operation matrix while leaf
monitors isolate one county's current state.

Account occurrence identity is leaf source ID + `keyId` + `typeID`. County
GEOID + parcel number is the parcel join. Assessor views and assessor sales,
Treasurer account rows, and county-auditor instruments retain their separate
lineages. For Mason, TaxParcels GIS supplies assessor/geometry fields,
EagleWeb supplies the current recorded-instrument index, Washington Digital
Archives title 56 supplies the archived recorder representation, and Ecology
supplies normalized parcel context. None is relabeled as Mason Treasurer data.

```bash
uv run python tools/query_washington_taxsifter.py sources \
    --output "$WORKDIR/wa-taxsifter-sources.json"
uv run python tools/query_washington_taxsifter.py metadata --county adams \
    --output "$WORKDIR/wa-taxsifter-adams-metadata.json"
uv run python tools/query_washington_taxsifter.py search HERCULES \
    --county adams --output "$WORKDIR/wa-taxsifter-owner.json"
uv run python tools/query_washington_taxsifter.py detail 2038010000001 \
    --county adams --output "$WORKDIR/wa-taxsifter-account.json"
uv run python tools/query_washington_taxsifter.py sales --county adams \
    --parcel 2038010000001 \
    --output "$WORKDIR/wa-taxsifter-sales.json"
uv run python tools/query_washington_taxsifter.py probe --verified \
    --operations all --output "$WORKDIR/wa-taxsifter-probes.json"

uv run python tools/query_property.py owner HERCULES \
    --source us-wa-adams-county-taxsifter --jurisdiction 53001 \
    --output "$WORKDIR/wa-taxsifter-shared-owner.json"
uv run python tools/query_property.py parcel 2038010000001 \
    --source us-wa-taxsifter-property-family --county Adams --ingest \
    --output "$WORKDIR/wa-taxsifter-shared-account.json"
uv run python tools/public_records_monitor.py run \
    us-wa-taxsifter-property-family us-wa-mason-county-taxsifter \
    --output "$WORKDIR/wa-taxsifter-monitors.json"
```

Mason's field-oriented substitute is
`us-wa-mason-county-tax-parcels-gis`, implemented by
`query_mason_county_tax_parcels.py`. The county layer exposes current
assessor/GIS name, address, value, exemption, acreage, legal/map, parcel-ID,
and polygon fields. It does not expose Auditor instruments or Treasurer
balance/payment history. `FID` remains the source-feature occurrence;
`PIN`, `TERRA_PIN`, and `Taxlot` remain candidate county-scoped parcel joins
whose uniqueness is not assumed.

The published ArcGIS contract reports `maxRecordCount=1000`,
`supportsPagination=false`, and `supportsOrderBy=false`. Queries snapshot all
matching FIDs with `returnIdsOnly=true`, sort them locally, and fetch exact
`objectIds` batches. Cursors bind criteria, schema, the complete FID-set
fingerprint, and the prior boundary. Omitted `--limit` means exhaustive
traversal; there is no adapter default result ceiling.

An official ArcGIS GET-form probe on 2026-07-30 returned 60,522 IDs spanning
`FID=0` through `FID=60521`, then returned the expected parcel fields for exact
`FID=0` (`PIN=219010090013`, `TERRA_PIN=21901-00-90013`,
`Taxlot=0090013`). The adapter accepts zero as a valid FID. The observed count
and range remain rolling monitor values rather than fixed contract checks.

```bash
uv run python tools/query_mason_county_tax_parcels.py metadata \
    --output "$WORKDIR/mason-tax-parcels-metadata.json"
uv run python tools/query_mason_county_tax_parcels.py owner SMITH \
    --limit 50 --output "$WORKDIR/mason-tax-parcels-owner.json"
uv run python tools/query_mason_county_tax_parcels.py parcel 21901-00-90013 \
    --geometry --output "$WORKDIR/mason-tax-parcels-parcel.json"
uv run python tools/query_property.py address "100 MAIN" \
    --source us-wa-mason-county-tax-parcels-gis --jurisdiction 53045 \
    --limit 50 --ingest --output "$WORKDIR/mason-tax-parcels-shared.json"
uv run python tools/public_records_monitor.py run \
    us-wa-mason-county-tax-parcels-gis \
    --output "$WORKDIR/mason-tax-parcels-monitor.json"
```

Mason Auditor EagleWeb and Washington Digital Archives title 56 remain
separate recorder-instrument publications. Washington Current Parcels is a
normalized representation with the same county-assessor origin, so it is a
discovery/join complement rather than independent corroboration of the Mason
GIS values.

Washington parcel records preserve `us-wa-state-parcels-normalized` lineage
across Ecology (normal default), DNR, and optional WISAARD representations.
Freshness and county-native land-use tables retain separate source IDs.
Current values and counts are rolling monitor observations; representation
parity is mirror health rather than independent corroboration. The four empty
current Ecology partitions are Grays Harbor, Pend Oreille, San Juan, and Walla
Walla; older WISAARD rows fill the same-lineage discovery gap for all but Pend
Oreille. County `DATA_LINK` values provide the next assessor/tax detail route.

```bash
# Washington statewide normalized parcels: Ecology default, DNR/WISAARD
# same-lineage representations, county freshness, and county land-use lookup
uv run python tools/query_washington_parcels.py metadata \
    --representation all --output "$WORKDIR/wa-parcel-metadata.json"
uv run python tools/query_washington_parcels.py search 2038010000001 \
    --field parcel --geometry --output "$WORKDIR/wa-parcel.json"
uv run python tools/query_washington_parcels.py count --county King \
    --output "$WORKDIR/wa-king-count.json"
uv run python tools/query_washington_parcels.py point -122.3321 47.6062 \
    --geometry --output "$WORKDIR/wa-point.json"
uv run python tools/query_washington_parcels.py county-freshness \
    --county "San Juan" --output "$WORKDIR/wa-freshness.json"
uv run python tools/query_washington_parcels.py land-use-codes \
    --county Adams --code R --output "$WORKDIR/wa-land-use.json"
uv run python tools/query_washington_parcels.py parity --include-wisaard \
    --output "$WORKDIR/wa-parity.json"
uv run python tools/query_washington_parcels.py probe --operation all \
    --include-wisaard --output "$WORKDIR/wa-probe.json"
uv run python tools/public_records_monitor.py run \
    us-wa-state-parcels-normalized us-wa-current-parcels-ecology \
    us-wa-current-parcels-dnr us-wa-current-parcels-wisaard \
    us-wa-current-parcels-county-freshness \
    us-wa-current-parcels-county-land-use \
    --output "$WORKDIR/wa-parcel-monitors.json"

# North Carolina OneMap: owner/address/parcel/geometry
uv run python tools/query_nc_property.py owner "SMITH" --county-fips 005 \
    --limit 25 --output "$WORKDIR/nc-owner.json"
uv run python tools/query_nc_property.py parcel 3013467134 --county-fips 005 \
    --geometry --output "$WORKDIR/nc-parcel.json"

# Denver assessor parcel layer: owner/address, values, sale observations,
# legal description, geometry, and recorder reception-number join
uv run python tools/query_denver_property.py owner "RODRIGUEZ" --limit 25 \
    --output "$WORKDIR/denver-owner.json"
uv run python tools/query_denver_property.py address "16159 E RANDOLPH PL" \
    --limit 25 --output "$WORKDIR/denver-address.json"
uv run python tools/query_denver_property.py parcel 0017103008000 --geometry \
    --output "$WORKDIR/denver-parcel.json"
uv run python tools/query_denver_property.py probe \
    --output "$WORKDIR/denver-parcel-probe.json"

# Delaware FirstMap: statewide polygon/centroid identity and routing
uv run python tools/query_delaware_firstmap.py pin 1001300033 \
    --county "New Castle" --geometry \
    --output "$WORKDIR/firstmap-pin.json"
uv run python tools/query_delaware_firstmap.py search 10013 \
    --county "New Castle" --layer polygon --max-records 25 \
    --output "$WORKDIR/firstmap-search.json"
uv run python tools/query_delaware_firstmap.py list \
    --county Sussex --layer centroid --max-records 25 \
    --output "$WORKDIR/firstmap-centroids.json"
uv run python tools/query_delaware_firstmap.py probe \
    --output "$WORKDIR/firstmap-probe.json"

# Arlington County: RPC/parcel, owner mailing address, assessment, and geometry
uv run python tools/query_arlington_property.py rpc 03001009 --geometry \
    --output "$WORKDIR/arlington-rpc.json"
uv run python tools/query_arlington_property.py parcel 03-001-009 \
    --output "$WORKDIR/arlington-parcel.json"
uv run python tools/query_arlington_property.py address "3905 44TH ST N" \
    --output "$WORKDIR/arlington-mailing-address.json"
uv run python tools/query_arlington_property.py probe \
    --output "$WORKDIR/arlington-probe.json"

# Deschutes DIAL: all native account-search modes, account components, permits,
# official reports, linked document states, and an account/taxlot monitor
uv run python tools/query_deschutes_dial.py search "VACH" --field owner \
    --output "$WORKDIR/deschutes-dial-owner.json"
uv run python tools/query_deschutes_dial.py search "SISTERS" --field subdivision \
    --output "$WORKDIR/deschutes-dial-subdivision.json"
uv run python tools/query_deschutes_dial.py account 135278 \
    --output "$WORKDIR/deschutes-dial-account.json"
uv run python tools/query_deschutes_dial.py download 135278 ownership \
    --destination "$WORKDIR/deschutes-ownership.pdf" \
    --output "$WORKDIR/deschutes-ownership-receipt.json"
uv run python tools/query_deschutes_dial.py probe \
    --output "$WORKDIR/deschutes-dial-probe.json"
uv run python tools/public_records_monitor.py run \
    us-or-deschutes-dial-property \
    --output "$WORKDIR/deschutes-dial-monitor.json"

# Deschutes CDD WebLink: account discovery, metadata, folders, and both
# source-native document storage modes
uv run python tools/query_property.py account 135278 \
    --source us-or-deschutes-cdd-weblink --jurisdiction 41017 --ingest \
    --output "$WORKDIR/deschutes-cdd-account.json"
uv run python tools/query_deschutes_laserfiche.py document 1383062 \
    --account 135278 --taxlot 141031B000700 \
    --output "$WORKDIR/deschutes-cdd-document.json"
uv run python tools/query_deschutes_laserfiche.py folder 1378494 \
    --output "$WORKDIR/deschutes-cdd-folder.json"
uv run python tools/query_deschutes_laserfiche.py download 333623 \
    --account 135278 --destination "$WORKDIR/deschutes-cdd-333623.pdf" \
    --output "$WORKDIR/deschutes-cdd-download.json"
uv run python tools/query_deschutes_laserfiche.py probe \
    --output "$WORKDIR/deschutes-cdd-probe.json"
uv run python tools/public_records_monitor.py run \
    us-or-deschutes-cdd-weblink \
    --output "$WORKDIR/deschutes-cdd-monitor.json"

# Lane parcels and rolling sales; Marion parcels, values, and sale reference
uv run python tools/query_oregon_lane_marion_parcels.py search \
    "US DEPT OF INTERIOR" \
    --source us-or-lane-county-assessor-parcels --field owner \
    --output "$WORKDIR/lane-owner.json"
uv run python tools/query_oregon_lane_marion_parcels.py sale 2024-019914 \
    --source us-or-lane-county-recent-property-sales \
    --output "$WORKDIR/lane-sale.json"
uv run python tools/query_property.py parcel 032W290000400 \
    --source us-or-marion-county-assessor-parcels \
    --jurisdiction 41047 --geometry --ingest \
    --output "$WORKDIR/marion-parcel.json"
uv run python tools/query_oregon_lane_marion_parcels.py probe --all \
    --output "$WORKDIR/lane-marion-probes.json"

# Lane Property Account Information: account/map-taxlot/address/name search
# plus account, receipt, valuation, and related-representation detail
uv run python tools/query_oregon_lane_property.py search 0057313 \
    --source us-or-lane-property-account-information --field account \
    --output "$WORKDIR/lane-account-search.json"
uv run python tools/query_oregon_lane_property.py account 0057313 \
    --output "$WORKDIR/lane-account-detail.json"

# Lane Tax Map Search: locator occurrences and separate official PDF documents
uv run python tools/query_oregon_lane_property.py search 1605070001100 \
    --source us-or-lane-tax-maps --field map_lot \
    --output "$WORKDIR/lane-tax-map-locator.json"
uv run python tools/query_oregon_lane_property.py download-tax-map 326 \
    --destination "$WORKDIR/lane-tax-map-326.pdf" \
    --output "$WORKDIR/lane-tax-map-download.json"
uv run python tools/query_oregon_lane_property.py probe \
    --source us-or-lane-property-account-information \
    --output "$WORKDIR/lane-account-probe.json"
uv run python tools/query_oregon_lane_property.py probe \
    --source us-or-lane-tax-maps \
    --output "$WORKDIR/lane-tax-map-probe.json"

# Marion official downloads: complete 1940-current sales manifest and
# replaceable comprehensive assessment snapshot
uv run python tools/query_oregon_marion_downloads.py manifest \
    --output "$WORKDIR/marion-download-manifest.json"
uv run python tools/query_oregon_marion_downloads.py probe \
    --source us-or-marion-sales-data \
    --output "$WORKDIR/marion-sales-probe.json"
uv run python tools/query_oregon_marion_downloads.py download \
    --source us-or-marion-comprehensive-assessment-download \
    --destination "$WORKDIR/marion-comprehensive.zip" \
    --output "$WORKDIR/marion-comprehensive-download.json"
uv run python tools/query_oregon_marion_downloads.py inspect \
    "$WORKDIR/marion-comprehensive.zip" \
    --source us-or-marion-comprehensive-assessment-download \
    --output "$WORKDIR/marion-comprehensive-inspection.json"
uv run python tools/query_property.py account 123456 \
    --source us-or-marion-comprehensive-assessment-download \
    --artifact-path "$WORKDIR/marion-comprehensive.zip" --ingest \
    --output "$WORKDIR/marion-comprehensive-account.json"
uv run python tools/query_property.py sale 2026-480 \
    --source us-or-marion-sales-data \
    --artifact-path "$WORKDIR/2026SalesData.csv" --ingest \
    --output "$WORKDIR/marion-sale.json"
uv run python tools/public_records_monitor.py run \
    us-or-marion-sales-data \
    us-or-marion-comprehensive-assessment-download \
    --output "$WORKDIR/marion-download-monitors.json"

The Marion listing is parsed as release slots, not immutable file versions.
The downloaded validator or SHA-256 identifies an occurrence of a slot;
archive member and row occurrences bind to that artifact, while sale identity
and parcel/account joins remain separate. CSV layouts are versioned, and the
2020 duplicate headers are parsed by position. Historical XLS/XLSB members
remain discoverable and inspectable even when that artifact is not locally
row-searchable.

The comprehensive archive uses `ORCATS999_(NEW).csv:RDATE` as its source
vintage. Owner and mailing columns have been omitted since 2015-02-01, so
shared ingestion projects assessment and situs fields without owners.
Assessor latest-sale party/book labels remain labels rather than current
ownership, title, or verified recorder evidence.

The alternative records output uses two independently cataloged Clerk source
identities: `us-or-marion-clerk-recorded-documents` for the officially
described 1974-present Digital Research Room route, and
`us-or-marion-clerk-historical-deeds` for the separately published 1855-1976
deed search. Each has its own canonical catalog manifest and citation mapping;
neither is treated as an assessor-download alias.

The current Clerk source is a verified Helion tenant under its existing stable
source ID:

```bash
uv run python tools/query_oregon_helion_recorder.py search \
    --source us-or-marion-clerk-recorded-documents \
    --year 2026 --document-from 1 --document-to 2 \
    --output "$WORKDIR/marion-recorder-search.json"
uv run python tools/query_oregon_helion_recorder.py detail \
    --source us-or-marion-clerk-recorded-documents 2026 1 \
    --output "$WORKDIR/marion-recorder-detail.json"
uv run python tools/query_property.py instrument 2026-00001 \
    --source us-or-marion-clerk-recorded-documents \
    --jurisdiction 41047 --ingest \
    --output "$WORKDIR/marion-recorder-unified.json"
uv run python tools/public_records_monitor.py run \
    us-or-marion-clerk-recorded-documents \
    --output "$WORKDIR/marion-recorder-monitor.json"
```

The county listing labels the current index 1974-present and the historical
deed search 1855-1976, while the historical form itself says records are
available for year periods 1850-1976. The 1974-1976 overlap and both start-year
statements remain source observations. The sampled current detail exposed
parties, consideration, return-to data, Reel & Page, and a related instrument,
but no direct image, OCR-text, or cart link. Counter/mail copies and official
certification are therefore retained as a separate Clerk representation.
Recorder searches use 50-row native windows. With no caller `--limit`, the
adapter follows the source-reported total; an explicit positive limit can span
multiple native windows and returns a query-bound continuation when needed.

# Benton County taxlot owners, bulk assessment snapshots, and map PDFs
uv run python tools/query_oregon_benton_property.py owner "NOLAN" \
    --geometry --output "$WORKDIR/benton-owner.json"
uv run python tools/query_oregon_benton_property.py bulk-manifest \
    --output "$WORKDIR/benton-bulk.json"
uv run python tools/query_oregon_benton_property.py maps \
    --map-number 11513A --match exact \
    --output "$WORKDIR/benton-maps.json"
uv run python tools/public_records_monitor.py run \
    us-or-benton-county-taxlot-owners \
    us-or-benton-county-assessment-bulk \
    us-or-benton-county-assessment-maps \
    --output "$WORKDIR/benton-monitors.json"

# Lincoln County account detail, WFS geometry, recorder join, and monitors
uv run python tools/query_oregon_lincoln_propertyweb.py detail \
    R452940 O0064958 \
    --output "$WORKDIR/lincoln-propertyweb-detail.json"
uv run python tools/query_oregon_lincoln_taxlots.py search R452940 \
    --field property --match exact --geometry \
    --output "$WORKDIR/lincoln-taxlot.json"
uv run python tools/query_oregon_helion_recorder.py detail \
    --source us-or-lincoln-helion-recorder 2025 1695 \
    --output "$WORKDIR/lincoln-recorder.json"
uv run python tools/public_records_monitor.py run \
    us-or-lincoln-propertyweb \
    us-or-lincoln-county-taxlots-wfs \
    us-or-lincoln-helion-recorder \
    --output "$WORKDIR/lincoln-property-monitors.json"

# Oregon county Helion/ORCATS assessment and tax-account tenants
uv run python tools/query_oregon_helion_property.py search smith \
    --field name --source us-or-morrow-helion-property --limit 10 \
    --output "$WORKDIR/morrow-pso-name.json"
uv run python tools/query_oregon_helion_property.py detail 171 \
    --roll-type R --source us-or-morrow-helion-property \
    --output "$WORKDIR/morrow-pso-account.json"
uv run python tools/query_property.py account 171 \
    --source us-or-morrow-helion-property --jurisdiction 41049 --ingest \
    --output "$WORKDIR/morrow-pso-unified.json"
uv run python tools/public_records_monitor.py run \
    us-or-morrow-helion-property \
    --output "$WORKDIR/morrow-pso-monitor.json"

# Oregon county Helion recorder indexes and exact instrument detail
uv run python tools/query_oregon_helion_recorder.py search \
    --source us-or-umatilla-helion-recorder \
    --year 2026 --document-from 1 --document-to 40 --limit 10 \
    --output "$WORKDIR/umatilla-recorder.json"
uv run python tools/query_oregon_helion_recorder.py detail \
    --source us-or-wasco-helion-recorder 2023 2123 \
    --output "$WORKDIR/wasco-recorder-detail.json"
uv run python tools/query_property.py instrument 2023-002123 \
    --source us-or-wasco-helion-recorder --jurisdiction 41065 --ingest \
    --output "$WORKDIR/wasco-recorder-unified.json"

# Oregon county tax-foreclosure publication stages and versioned artifacts
uv run python tools/query_oregon_tax_foreclosures.py sources \
    --output "$WORKDIR/oregon-tax-foreclosure-sources.json"
uv run python tools/query_oregon_tax_foreclosures.py discover --all \
    --output "$WORKDIR/oregon-tax-foreclosure-routes.json"
uv run python tools/query_property.py owner "EXAMPLE OWNER" \
    --source us-or-tillamook-tax-foreclosure-publications \
    --jurisdiction 41057 --process-stage foreclosure_list_published \
    --ingest --output "$WORKDIR/tillamook-tax-foreclosure.json"
uv run python tools/query_oregon_tax_foreclosures.py download \
    --source us-or-marion-tax-foreclosure-publications \
    --process-stage foreclosure_list_published \
    --destination "$WORKDIR/marion-foreclosure-list.pdf" \
    --output "$WORKDIR/marion-foreclosure-download.json"
uv run python tools/query_oregon_tax_foreclosures.py inspect \
    --source us-or-marion-tax-foreclosure-publications \
    --artifact "$WORKDIR/marion-foreclosure-list.pdf" \
    --process-stage foreclosure_list_published \
    --text-artifact "$WORKDIR/marion-foreclosure-list-ocr.txt" \
    --text-method OCR \
    --output "$WORKDIR/marion-foreclosure-inspection.json"
```

The Helion recorder adapter keeps every registered county source ID, access
observations, complements, and native form contracts separate. `probe`
enumerates the selected tenant's current controls and option values: the
current Wasco form includes document-type and property-ID selectors that the
current Umatilla and Polk forms do not. Unified routing covers party and
instrument discovery; the direct adapter retains every offered date, party,
map/legal, subtype, and title-detail field. Image, OCR-text, cart-copy, and
certified-copy states are retained only where the selected tenant publishes
them. Index freshness remains live monitor detail while form
fields, option vocabularies, action, and method define the stable tenant
contract.

The tax-foreclosure adapter keeps Tillamook, Marion, Multnomah, and Clackamas
as distinct publication sources. `discover` returns each official landing-page
observation and publication route with a deterministic
`publication_document_id`; `download` versions the selected PDF; `inspect`
binds embedded or supplied text to the parent artifact SHA-256; and `search`
filters structured records by general text, published owner, account,
map/taxlot, real-property ID, address, or court case. `--process-stage`
selects one exact county route. Query metadata records both the requested and
resolved stage, so the default discovery choice is visible.

Tillamook currently parses annual foreclosure lists; Marion parses
end-of-redemption notices; Multnomah parses statutory redemption notices and
tax-title inventory; Clackamas parses auction offerings and results. Other
published artifacts remain first-class versioned documents with representation
provenance and a parser-coverage warning. The shared ingester retains those
artifacts even when no structured rows are available, and projects parsed rows
as tax events using their exact process-stage values. The source monitor keeps
landing-page hashes, current routes, and current PDF hashes as rolling details
while hashing the publisher, county, route roles, stage vocabulary, join keys,
complements, and artifact/text lineage contract.

```bash
# Bexar Central Appraisal District: current roll, parcel geometry, rich detail,
# roll history, appeals, improvements, and deed-history enrichment
uv run python tools/query_bexar_property.py owner "GRACE CHURCH" \
    --output "$WORKDIR/bcad-owner.json"
uv run python tools/query_bexar_property.py address "STONE OAK PKWY" \
    --output "$WORKDIR/bcad-address.json"
uv run python tools/query_bexar_property.py parcel 612115 --geometry \
    --output "$WORKDIR/bcad-parcel.json"
uv run python tools/query_bexar_property.py search '"CORNERSTONE CHURCH"' \
    --output "$WORKDIR/bcad-search.json"
uv run python tools/query_bexar_property.py detail 612115 --year 2026 \
    --output "$WORKDIR/bcad-detail.json"
uv run python tools/query_bexar_property.py probe \
    --output "$WORKDIR/bcad-probe.json"

# Reeves County Clerk recorded instruments and selected page images
uv run python tools/query_reeves_records.py search "THREE RIVERS" \
    --output "$WORKDIR/reeves-party.json"
uv run python tools/query_reeves_records.py search 18-06481 \
    --output "$WORKDIR/reeves-instrument.json"
uv run python tools/query_reeves_records.py document 20798096 \
    --output "$WORKDIR/reeves-detail.json"
uv run python tools/query_reeves_records.py page \
    20798096 1 "$WORKDIR/reeves-page-1.png" \
    --output "$WORKDIR/reeves-page-1.json"
uv run python tools/query_property.py instrument 18-06481 \
    --source us-tx-reeves-county-clerk-official-records \
    --jurisdiction 48389 --ingest \
    --output "$WORKDIR/reeves-unified.json"
uv run python tools/public_records_monitor.py run \
    us-tx-reeves-county-clerk-official-records \
    --output "$WORKDIR/reeves-monitor.json"

# Configured county GovOS/Kofile recorder tenants
uv run python tools/query_govos_recorders.py search \
    --source us-pa-berks-recorder-publicsearch 2024000062 \
    --output "$WORKDIR/berks-instrument.json"
uv run python tools/query_govos_recorders.py search \
    --source us-pa-berks-recorder-publicsearch --department MISC \
    "EXAMPLE NAME" --output "$WORKDIR/berks-misc.json"
uv run python tools/query_govos_recorders.py document \
    --source us-pa-delaware-recorder-publicsearch 187146913 \
    --output "$WORKDIR/delaware-pa-detail.json"
uv run python tools/query_govos_recorders.py page \
    --source us-pa-indiana-recorder-publicsearch \
    133236252 1 "$WORKDIR/indiana-page-1.png" \
    --output "$WORKDIR/indiana-page-1.json"
uv run python tools/query_property.py instrument 2001-017168 \
    --source us-pa-lawrence-recorder-publicsearch --ingest \
    --output "$WORKDIR/lawrence-unified.json"
uv run python tools/query_govos_recorders.py probe \
    --source us-de-kent-recorder-publicsearch \
    --output "$WORKDIR/kent-govos-sentinel.json"
uv run python tools/query_govos_recorders.py search \
    --source us-co-denver-recorder-publicsearch \
    --department RP 2026010037 \
    --output "$WORKDIR/denver-instrument.json"
uv run python tools/query_govos_recorders.py search \
    --source us-oh-franklin-county-recorder-publicsearch \
    202607290091301 --output "$WORKDIR/franklin-instrument.json"

# Texas Railroad Commission bulk: release discovery, transfer, streaming
# parsing, and P-4 -> P-5/Wellbore native-key resolution
uv run python tools/query_rrc_bulk.py contracts \
    --output "$WORKDIR/rrc-contracts.json"
uv run python tools/query_rrc_bulk.py releases wellbore \
    --output "$WORKDIR/rrc-wellbore-releases.json"
uv run python tools/query_rrc_bulk.py download p5 "$WORKDIR/rrc" \
    --output "$WORKDIR/rrc-p5-download.json"
uv run python tools/query_rrc_bulk.py p5 "$WORKDIR/rrc/orf850.txt.gz" \
    --p5-number 028612 --output "$WORKDIR/rrc-operator.json"
uv run python tools/query_rrc_bulk.py p4 "$WORKDIR/rrc/p4f606.ebc.gz" \
    --oil-gas O --district 06 --lease-id 04411 \
    --output "$WORKDIR/rrc-history.json"
uv run python tools/query_rrc_bulk.py wellbore \
    "$WORKDIR/rrc/OG_WELLBORE_EWA_Report_2026-07-02.csv" \
    --operator-number 028612 --output "$WORKDIR/rrc-wells.json"
uv run python tools/query_rrc_bulk.py resolve \
    --p4 "$WORKDIR/rrc/p4f606.ebc.gz" \
    --p5 "$WORKDIR/rrc/orf850.txt.gz" \
    --wellbore "$WORKDIR/rrc/OG_WELLBORE_EWA_Report_2026-07-02.csv" \
    --oil-gas O --district 06 --lease-id 04411 \
    --output "$WORKDIR/rrc-resolved.json"
uv run python tools/public_records_monitor.py run \
    us-tx-rrc-p4-bulk us-tx-rrc-p5-bulk us-tx-rrc-wellbore-bulk \
    --output "$WORKDIR/rrc-monitor.json"

# Orleans Parish City Property Viewer: current assessment account, parcel,
# owner/address, and polygon geometry
uv run python tools/query_orleans_property.py owner "CITY OF NEW ORLEANS" \
    --output "$WORKDIR/orleans-owner.json"
uv run python tools/query_orleans_property.py address "1300 PERDIDO" \
    --output "$WORKDIR/orleans-address.json"
uv run python tools/query_orleans_property.py account "<TAXBILLID>" --geometry \
    --output "$WORKDIR/orleans-account.json"
uv run python tools/query_orleans_property.py parcel "<PARCELID>" --geometry \
    --output "$WORKDIR/orleans-parcel.json"
uv run python tools/query_orleans_property.py search "PERDIDO" \
    --output "$WORKDIR/orleans-search.json"
uv run python tools/public_records_monitor.py run \
    us-la-orleans-property-viewer \
    --output "$WORKDIR/orleans-monitor.json"

# Miami-Dade Property Appraiser: owner/address/folio, rich assessment and sale
# history, and official parcel geometry
uv run python tools/query_miami_dade_property.py owner "MIAMI-DADE COUNTY" \
    --output "$WORKDIR/miami-pa-owner.json"
uv run python tools/query_miami_dade_property.py address "111 NW 1 ST" \
    --output "$WORKDIR/miami-pa-address.json"
uv run python tools/query_miami_dade_property.py detail 0101000000020 \
    --geometry --output "$WORKDIR/miami-pa-detail.json"
uv run python tools/query_miami_dade_property.py history 0101000000020 \
    --output "$WORKDIR/miami-pa-history.json"
uv run python tools/query_miami_dade_property.py probe \
    --output "$WORKDIR/miami-pa-probe.json"

# Orange County Tax Collector: current GovHub/TaxSys account and bill state,
# plus fixed 2020 historical bulk snapshots
uv run python tools/query_orange_tax_collector.py sources \
    --output "$WORKDIR/orange-tax-sources.json"
uv run python tools/query_orange_tax_collector.py search \
    01-20-27-0000-00001 --limit 15 \
    --output "$WORKDIR/orange-tax-search.json"
uv run python tools/query_orange_tax_collector.py account \
    01-20-27-0000-00001 \
    --output "$WORKDIR/orange-tax-account.json"
uv run python tools/query_orange_tax_collector.py history \
    01-20-27-0000-00001 \
    --output "$WORKDIR/orange-tax-history.json"
uv run python tools/query_orange_tax_collector.py bill \
    01-20-27-0000-00001 ca0e3d54-aad7-11f0-bb75-005056815849 \
    --output "$WORKDIR/orange-tax-bill.json"
uv run python tools/query_orange_tax_collector.py bulk-manifest --verify-page \
    --output "$WORKDIR/orange-tax-bulk-manifest.json"
uv run python tools/query_orange_tax_collector.py bulk-probe current \
    --output "$WORKDIR/orange-tax-current-probe.json"
uv run python tools/query_orange_tax_collector.py bulk-download current \
    "$WORKDIR/TaxPaymentTape.zip" --inspect \
    --output "$WORKDIR/orange-tax-current-download.json"
uv run python tools/query_orange_tax_collector.py bulk-search current \
    "$WORKDIR/TaxPaymentTape.zip" --account 01-20-27-0000-00001 \
    --output "$WORKDIR/orange-tax-historical-search.json"
uv run python tools/query_property.py account 01-20-27-0000-00001 \
    --source us-fl-orange-tax-collector-property-tax --jurisdiction 12095 \
    --ingest --output "$WORKDIR/orange-tax-shared-account.json"
uv run python tools/query_property.py parcel 01-20-27-0000-00001 \
    --source us-fl-orange-tax-collector-property-tax \
    --artifact-path "$WORKDIR/TaxPaymentTape.zip" --dataset-type current \
    --ingest --output "$WORKDIR/orange-tax-shared-historical.json"
uv run python tools/public_records_monitor.py run \
    us-fl-orange-tax-collector-property-tax \
    --output "$WORKDIR/orange-tax-monitor.json"

# The current portal and bulk snapshots have separate freshness. The landing
# page calls the ZIP links Daily but labels them as of 2020-02-17; observed
# archive metadata and the current-file TaxYear 2019 confirm historical use.
# The exact 15-digit account is the parcel join. Algolia objects, TaxSys
# tokens, bill UUIDs, certificates, receipts, validation values, artifacts,
# members, and source rows remain separate identities. Normalized ingestion
# retains payer and certificate-buyer roles without promoting them to owners
# or treating tax-deed state as a recorded instrument.

# Miami-Dade Clerk public detail/image routes
uv run python tools/query_miami_dade_recorder.py document-types \
    --output "$WORKDIR/miami-recorder-types.json"
uv run python tools/query_miami_dade_recorder.py parties 50126241 \
    --output "$WORKDIR/miami-recorder-parties.json"
uv run python tools/query_miami_dade_recorder.py financial 50126241 \
    --doc-type "DEED - DEE" --recording-date 2026-01-27 \
    --output "$WORKDIR/miami-recorder-financial.json"
uv run python tools/query_miami_dade_recorder.py image 35134 800 \
    --book-type O --document-output "$WORKDIR/miami-record.pdf" \
    --output "$WORKDIR/miami-recorder-image.json"

# Exact CFN/book-page/folio selectors through the Clerk commercial API
uv run python tools/query_miami_dade_recorder.py cfn 2026 55844 \
    --output "$WORKDIR/miami-recorder-cfn.json"
uv run python tools/query_miami_dade_recorder.py book-page 35134 800 \
    --output "$WORKDIR/miami-recorder-book-page.json"
uv run python tools/query_miami_dade_recorder.py folio 0141380670370 \
    --output "$WORKDIR/miami-recorder-folio.json"

# Cook County Parcel Universe: PIN history/geography/tax districts
uv run python tools/query_cook_property.py parcel 01-01-106-009-1001 \
    --output "$WORKDIR/cook-parcel.json"

# Maryland statewide assessments: address/parcel; current owner names are
# source-withheld and represented as such
uv run python tools/query_md_property.py address "7 TRAYMORE RD" \
    --output "$WORKDIR/md-address.json"
uv run python tools/query_md_property.py parcel 04030311078580 \
    --output "$WORKDIR/md-parcel.json"

# Maryland MD iMAP Parcel Points: same SDAT account identity plus planning,
# appraisal, structure/land, deed/plat-reference, and point fields
# Catalog source: us-md-mdp-parcel-points
uv run python tools/query_md_mdp_parcel_points.py account 1901000047 \
    --geometry --output "$WORKDIR/md-mdp-account.json"
uv run python tools/query_md_mdp_parcel_points.py address "100 MAIN" \
    --county-code 19 --output "$WORKDIR/md-mdp-address.json"
uv run python tools/query_md_mdp_parcel_points.py query --county-code 19 \
    --map 0042 --zoning R \
    --output "$WORKDIR/md-mdp-map-zoning.json"
uv run python tools/query_md_mdp_parcel_points.py point -76.63 38.30 \
    --geometry --output "$WORKDIR/md-mdp-point.json"
uv run python tools/query_property.py search 1901000047 \
    --source us-md-mdp-parcel-points --search-field ACCTID \
    --output "$WORKDIR/md-mdp-shared.json"

# ACCTID is the exact same-record join to us-md-sdat-property-hidden;
# OBJECTID is the ArcGIS feature-occurrence and continuation order. The point
# source publishes owner mailing addresses but no current-owner-name field.
# Its projected fields retain us-md-mdp-parcel-points provenance.

# Maryland official parcel geodatabase, CAMA, and residential-sales downloads
uv run python tools/query_md_mdp_property_downloads.py sources \
    --output "$WORKDIR/md-mdp-download-sources.json"
uv run python tools/query_md_mdp_property_downloads.py manifest \
    --source us-md-mdp-parcel-downloads \
    --output "$WORKDIR/md-mdp-parcel-releases.json"
uv run python tools/query_md_mdp_property_downloads.py manifest \
    --source us-md-mdp-cama-downloads --component building \
    --output "$WORKDIR/md-mdp-cama-building.json"
uv run python tools/query_md_mdp_property_downloads.py prepare \
    --source us-md-mdp-property-sales-downloads \
    --release sales-2026-02 \
    --output "$WORKDIR/md-mdp-sales-transfer.json"
uv run python tools/query_property.py manifest \
    --source us-md-mdp-cama-downloads --dataset-type building \
    --output "$WORKDIR/md-mdp-cama-shared.json"

# These commands retain release, provider-link, artifact, member, and future
# row-occurrence identities separately. ACCTID is the parcel-account join;
# CAMALINK joins Building to Subareas. No row projection is claimed until the
# acquired geodatabase/table schemas have been decoded.

# Maryland State Archives Plats.net: all 24 county-equivalent routes,
# metadata-only units, native source totals/paging, and exact artifacts
uv run python tools/query_md_plats.py counties \
    --output "$WORKDIR/md-plats-counties.json"
uv run python tools/query_md_plats.py search MO --mode advanced \
    --description "Estate" --include-no-images \
    --output "$WORKDIR/md-plats-estate.json"
uv run python tools/query_md_plats.py search MO --mode series \
    --qualifier C --series 1136 --unit 1 \
    --output "$WORKDIR/md-plats-series.json"
uv run python tools/query_md_plats.py plat MO C 1136 1 \
    --output "$WORKDIR/md-plats-unit.json"
uv run python tools/query_property.py subdivision "Timberland Estates" \
    --source us-md-plats --county "Montgomery County" --ingest \
    --output "$WORKDIR/md-plats-shared.json"
uv run python tools/public_records_monitor.py run us-md-plats \
    --output "$WORKDIR/md-plats-monitor.json"

# The stable record is county + archive qualifier + series + unit. Printed
# plat/book/page values and developer/owner display text remain plat metadata,
# not title or current parcel-owner assertions. Omitted limits exhaust the
# source-reported set; only an explicit caller limit emits a continuation.
# Compiled PDFs and individual TIFF/JPEG scans remain separate representations.

# Florida DOR official assessment-roll and GIS releases
# Catalog source: us-fl-dor-property-roll
uv run python tools/query_fl_dor_property.py manifest --type sdf \
    --county Baker --year 2026 --output "$WORKDIR/fl-baker-manifest.json"
uv run python tools/query_fl_dor_property.py probe --type gis-pin \
    --county 12 --year 2026 --output "$WORKDIR/fl-gis-probe.json"
uv run python tools/query_fl_dor_property.py dry-run --type nal \
    --county Baker --destination "$WORKDIR/fl-dor" \
    --output "$WORKDIR/fl-transfer-plan.json"
uv run python tools/query_fl_dor_property.py download --type nal \
    --county Baker --year 2026 --destination "$WORKDIR/fl-baker-nal.zip" \
    --output "$WORKDIR/fl-baker-download.json"
uv run python tools/ingest_fl_dor_property.py ingest \
    "$WORKDIR/fl-baker-nal.zip" --dataset-type nal \
    --property-db "$WORKDIR/property-records.db" \
    --output "$WORKDIR/fl-baker-nal-ingest.json"

# Montana MSL live parcels plus statewide/county parcel and ORION releases
# Catalog source: us-mt-msl-cadastral
uv run python tools/query_montana_cadastral.py metadata \
    --output "$WORKDIR/montana-cadastral-metadata.json"
uv run python tools/query_montana_cadastral.py owner "EXAMPLE RANCH LLC" \
    --county Petroleum --tax-year 2026 \
    --output "$WORKDIR/montana-owner.json"
uv run python tools/query_montana_cadastral.py parcel 56382732101040000 \
    --geometry --output "$WORKDIR/montana-parcel.json"
uv run python tools/query_montana_cadastral.py counties \
    --output "$WORKDIR/montana-counties.json"
uv run python tools/query_montana_cadastral.py releases \
    --output "$WORKDIR/montana-releases.json"
uv run python tools/query_montana_cadastral.py manifest \
    --dataset parcel-shp --county Petroleum \
    --output "$WORKDIR/montana-petroleum-manifest.json"
uv run python tools/query_montana_cadastral.py artifact-probe \
    --dataset orion --county 55 \
    --output "$WORKDIR/montana-orion-probe.json"
uv run python tools/query_montana_cadastral.py download \
    --dataset parcel-gdb --county 30069 \
    --destination "$WORKDIR/montana-petroleum-gdb.zip" \
    --output "$WORKDIR/montana-download.json"
uv run python tools/query_property.py map 56382732101040000 \
    --source us-mt-msl-cadastral --jurisdiction 30069 --ingest \
    --output "$WORKDIR/montana-shared-parcel.json"
uv run python tools/public_records_monitor.py run us-mt-msl-cadastral \
    --output "$WORKDIR/montana-monitor.json"

# MassGIS official municipal snapshots
uv run python tools/query_massgis_property.py manifest --town GOSNOLD \
    --output "$WORKDIR/massgis-manifest.json"
uv run python tools/query_massgis_property.py probe --town GOSNOLD \
    --output "$WORKDIR/massgis-probe.json"
uv run python tools/query_massgis_property.py download --town GOSNOLD \
    --destination "$WORKDIR/massgis-gosnold.zip" --dry-run \
    --output "$WORKDIR/massgis-transfer-plan.json"

# Texas Comptroller EPTS request handoff and delivered-artifact processing
# Catalog source: us-tx-comptroller-epts
uv run python tools/query_texas_epts.py discover \
    --output "$WORKDIR/texas-epts-source.json"
uv run python tools/query_texas_epts.py schema \
    --output "$WORKDIR/texas-epts-schema.json"
uv run python tools/query_texas_epts.py request-plan --cad-id 101 \
    --output "$WORKDIR/texas-epts-request-plan.json"
uv run python tools/query_texas_epts.py inspect \
    "$WORKDIR/epts-delivery.zip" \
    --output "$WORKDIR/texas-epts-inspection.json"
uv run python tools/query_texas_epts.py search \
    "$WORKDIR/epts-delivery.zip" "EXAMPLE LLC" --field party \
    --output "$WORKDIR/texas-epts-party-results.json"

# Harris Central Appraisal District CAMA releases
# Catalog source: us-tx-harris-hcad-property
uv run python tools/query_harris_property.py manifest --year 2026 \
    --output "$WORKDIR/hcad-2026-manifest.json"
uv run python tools/query_harris_property.py probe --year 2026 \
    --artifact Real_acct_owner.zip \
    --output "$WORKDIR/hcad-owner-probe.json"
uv run python tools/query_harris_property.py dry-run --year 2026 \
    --artifact Real_acct_owner.zip --destination "$WORKDIR/hcad" \
    --output "$WORKDIR/hcad-owner-transfer-plan.json"
uv run python tools/ingest_hcad_property.py ingest \
    --archive "$WORKDIR/hcad/Real_acct_owner.zip" --tax-year 2026 \
    --release-id 2026:preliminary:2026-07-26 \
    --certification-status preliminary \
    --property-db "$WORKDIR/property-records.db" \
    --output "$WORKDIR/hcad-owner-ingest.json"

# HCAD GIS current/historical bulk plus the county MapServer representation
# Catalog source: us-tx-harris-hcad-gis
uv run python tools/query_hcad_gis.py releases \
    --output "$WORKDIR/hcad-gis-releases.json"
uv run python tools/query_hcad_gis.py probe \
    --output "$WORKDIR/hcad-gis-parcels-probe.json"
uv run python tools/query_hcad_gis.py download \
    --destination "$WORKDIR/hcad-parcels.zip" \
    --output "$WORKDIR/hcad-gis-download.json"
uv run python tools/query_hcad_gis.py inspect \
    "$WORKDIR/hcad-parcels.zip" \
    --output "$WORKDIR/hcad-gis-inspection.json"
uv run python tools/query_hcad_gis.py account 1144740190749 --geometry \
    --output "$WORKDIR/hcad-gis-account.json"
uv run python tools/query_hcad_gis.py search "WOODSMAN" --field address \
    --output "$WORKDIR/hcad-gis-address.json"

# TxGIO annual county/state parcel archives and local DBF search
# Catalog source: us-tx-txgio-land-parcels
uv run python tools/query_txgio_land_parcels.py releases \
    --output "$WORKDIR/txgio-releases.json"
uv run python tools/query_txgio_land_parcels.py manifest --county Harris \
    --output "$WORKDIR/txgio-harris-manifest.json"
uv run python tools/query_txgio_land_parcels.py probe --county Kenedy \
    --output "$WORKDIR/txgio-kenedy-probe.json"
uv run python tools/query_txgio_land_parcels.py download --county Kenedy \
    --destination "$WORKDIR/txgio-kenedy.zip" \
    --output "$WORKDIR/txgio-kenedy-download.json"
uv run python tools/query_txgio_land_parcels.py inspect \
    "$WORKDIR/txgio-kenedy.zip" \
    --output "$WORKDIR/txgio-kenedy-inspection.json"
uv run python tools/query_txgio_land_parcels.py search \
    "$WORKDIR/txgio-kenedy.zip" "KING RANCH" --field owner \
    --output "$WORKDIR/txgio-kenedy-owner.json"

uv run python tools/public_records_monitor.py run \
    us-tx-harris-hcad-property us-tx-harris-hcad-gis \
    us-tx-txgio-land-parcels \
    --output "$WORKDIR/texas-property-monitor.json"

# Harris County Clerk real-property index and foreclosure notices
uv run python tools/query_harris_recorder.py search \
    --file-number RP-2026-72194 \
    --output "$WORKDIR/harris-instrument.json"
uv run python tools/query_harris_recorder.py search \
    --grantor "EXAMPLE HOLDINGS LLC" --from-date 2026-01-01 \
    --to-date 2026-07-29 --output "$WORKDIR/harris-grantor.json"
uv run python tools/query_harris_recorder.py products \
    --output "$WORKDIR/harris-recorder-products.json"
uv run python tools/query_harris_foreclosures.py search \
    --document-id FRCL-2026-4797 \
    --output "$WORKDIR/harris-foreclosure.json"
uv run python tools/query_harris_foreclosures.py download FRCL-2026-4797 \
    --destination "$WORKDIR/harris-foreclosure.pdf" \
    --output "$WORKDIR/harris-foreclosure-receipt.json"
uv run python tools/public_records_monitor.py run \
    us-tx-harris-clerk-real-property us-tx-harris-clerk-foreclosures \
    --output "$WORKDIR/harris-clerk-monitor.json"
```

Florida DOR's summary PDFs number 92 logical NAL fields and 14 logical SDF
fields, while current public CSV archives include expanded physical context.
The sampled 2026P Baker files have 165 and 23 physical columns, respectively.
Successful downloads include bounded `nal_csv` or `sdf_csv` header inspection
with the observed fields, fingerprint, and projection-column check.
`ingest_fl_dor_property.py` streams NAL parcels, assessment-owner observations,
addresses, values, and legal descriptions; SDF assessment-sale events and
their book/page/clerk references; and aligned GIS-PIN feature occurrences,
blank-key state, native-CRS geometry, and artifact provenance. Exact
`PARCELNO` values create source-attributed parcel shells. Repeated values are
retained as separate occurrences and represented by a parcel-level feature
collection without dissolving the published geometries. SDF references do not
become recorded-title instruments.

Montana's `COUNTYCD` is the ORION CountyPrefix, not Census FIPS. The adapter
ships the exact 56-entry crosswalk to Census county GEOIDs and accepts either
identity explicitly. A live feature keeps `GlobalID`/`OBJECTID` occurrence
identity apart from nullable `PARCELID`; rows without a parcel join remain
source observations. Owner/value fields project as assessment-roll evidence,
not recorded title. The ORION databases, parcel SHP/FileGDB archives, PLSS,
public-land, conservation-easement, historic-cadastral, and county
assessor/treasurer/clerk routes provide complementary detail. Monthly archive
filenames are rolling aliases, so manifest identity includes the observed
filename, publisher modification marker, and byte size.

HCAD CAMA archive ingestion preserves repeated source-row occurrences and
projects appraisal facts without treating its deed/clerk references as
controlling recorded-title instruments. HCAD GIS keeps the bulk publication
date separate from the MapServer tax-year field. The current HCAD
`Parcels.zip` is a FileGDB. `query_hcad_gis.py inspect` preserves its release
and archive lineage; `public_records_filegdb.py` preserves content-based
container identity without GDAL. `ogrinfo` 3.7+ OpenFileGDB supplies
structural layer schemas; feature paging separately requires verified
`ogr2ogr` OpenFileGDB read and GPKG write support for native FID occurrences
and native-CRS WKB. MapServer records can project returned EPSG:4326 Esri JSON
geometry. Turning a generic FileGDB feature page into HCAD-specific normalized
rows remains an explicit source-mapping step.

The current TxGIO collection has 253 county artifacts plus one statewide
aggregate, so its 254 resources do not mean 254 county archives; Donley is the
observed gap. The Texas Comptroller appraisal-district directory is the
official alternative route for that gap or a fresher local release. TxGIO
searches an explicit local archive, and its map/geometry projection is an
artifact-hash/member/DBF-row shapefile reference with
`geometry_decoded=false`. Coordinate decoding remains infrastructure request
#314. The HCAD County MapServer and TxGIO map service are representations of
their underlying publications rather than independent corroboration.

Denver parcel results can join `RECEPTION_NUM` to
`us-co-denver-recorder-publicsearch`. FirstMap supplies statewide PIN,
polygon, centroid, and geographic-routing records; Kent adds owner/address,
deed-reference, assessment, permit, violation, survey, and geometry fields;
Sussex adds parcel plus ownership/assessment-unit rows; New Castle adds
owner, deed/sale, assessment/tax, permit, violation, and characteristic
history. Arlington's property layer publishes an owner mailing address but no
owner name, situs address, or sale fields. The VGIN statewide parcel layer
adds common geometry/routing, while Arlington PublicSearch and Virginia
Secure Remote Access add the Clerk land-record index and document routes.

NYC ACRIS and East Baton Rouge commands are listed later in this reference.
See `docs/modules/property.md` for each pilot's source coverage and canonical
record semantics.

### Wisconsin court directories

The directory adapter retrieves six separately identified current snapshots:
circuit court offices, circuit clerks, circuit judges, judicial
administrative districts, Court of Appeals offices, and Supreme Court/state
offices. Shared ingestion retains them as source snapshots and creates no case
rows.

```bash
uv run python tools/query_wisconsin_court_directory.py county Dane \
    --output "$WORKDIR/wi-dane-directory.json"
uv run python tools/query_wisconsin_court_directory.py search Ashley \
    --component administrative-districts \
    --output "$WORKDIR/wi-directory-personnel.json"
uv run python tools/query_wisconsin_court_directory.py discovery \
    --query Dane --output "$WORKDIR/wi-county-court-routes.json"
uv run python tools/query_state_courts.py search "Example" \
    --source us-wi-court-directory --jurisdiction 55025 \
    --search-field clerk --ingest \
    --output "$WORKDIR/wi-directory-snapshot.json"
```

The official municipal-court PDF, alphabetical employee list, and county
juror contacts are mapped adjacent routes. WCCA, WSCCA, and the opinion corpus
remain distinct case and publication sources.

### Wisconsin appellate cases and publications

```bash
# WSCCA case metadata, parties, counsel, docket, and public documents
uv run python tools/query_wisconsin_wscca.py search 2025AP000699 \
    --scope case-number --output "$WORKDIR/wi-wscca-search.json"
uv run python tools/query_wisconsin_wscca.py case 2025AP000699 \
    --output "$WORKDIR/wi-wscca-case.json"
uv run python tools/query_wisconsin_wscca.py docket 2025AP000699 \
    --output "$WORKDIR/wi-wscca-docket.json"
uv run python tools/query_wisconsin_wscca.py documents 2025AP000699 \
    --output "$WORKDIR/wi-wscca-documents.json"
uv run python tools/query_wisconsin_wscca.py rss 2025AP000699 \
    --output "$WORKDIR/wi-wscca-rss.json"
uv run python tools/query_wisconsin_wscca.py routes \
    --output "$WORKDIR/wi-wscca-routes.json"

# Official opinions, orders, summary dispositions, full text, feeds, and PDFs
uv run python tools/query_wisconsin_opinions.py search \
    --collection appeals-opinions --case-number 2025AP000482 \
    --output "$WORKDIR/wi-appeals-opinions.json"
uv run python tools/query_wisconsin_opinions.py search \
    --collection supreme-orders --party "Example Party" --all-pages \
    --output "$WORKDIR/wi-supreme-orders.json"
uv run python tools/query_wisconsin_opinions.py keyword \
    "Wisconsin Voter Alliance" --court supreme \
    --output "$WORKDIR/wi-supreme-fulltext.json"
uv run python tools/query_wisconsin_opinions.py feed --court appeals \
    --output "$WORKDIR/wi-appeals-feed.json"
uv run python tools/query_wisconsin_opinions.py taxonomy \
    --collection appeals-opinions \
    --output "$WORKDIR/wi-opinion-taxonomy.json"

# The unified court wrapper exposes the common search and retention path
uv run python tools/query_state_courts.py case 2025AP000699 \
    --source us-wi-wscca-public \
    --output "$WORKDIR/wi-unified-case.json"
uv run python tools/query_state_courts.py documents 2025AP000482 \
    --source us-wi-court-opinions \
    --search-field appeals-opinions \
    --output "$WORKDIR/wi-unified-opinion.json"
```

WSCCA browser operations and its direct case RSS feed share appellate case
identity but retain operation-level provenance. The publication corpus is a
separate source: its metadata indexes use one-based pages, full-text results
use ten-row native offsets, and release feeds are monitored independently.
Consolidated cases can share one PDF, so document occurrence remains
case-scoped while the native PDF identifier supplies shared artifact identity.
Use the cataloged State Law Library, UW Law historical briefs, appellate
clerk, CourtListener, WCCA public search, and WCCA REST routes as field- and
era-specific complements.

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

# Wisconsin circuit and subscription actions; live appellate adapters are above
uv run python tools/public_records_actions.py plan us-wi-wcca-public \
    --operation search_cases --selector "Example Person" --jurisdiction 55 \
    --output "$WORKDIR/wisconsin-circuit-search-plan.json"
uv run python tools/public_records_actions.py plan us-wi-wcca-rest \
    --operation sync --selector "Wisconsin circuit case metadata" \
    --jurisdiction 55 --output "$WORKDIR/wisconsin-rest-plan.json"
uv run python tools/public_records_actions.py plan us-wi-appellate-clerk \
    --operation request_document --selector "2025AP000699 brief" \
    --jurisdiction 55 --output "$WORKDIR/wisconsin-clerk-plan.json"

# ACRIS selected-image/copy route from an index document ID
uv run python tools/public_records_actions.py plan us-nyc-acris-images \
    --operation open_selected_image --selector 2017021700466001 \
    --output "$WORKDIR/acris-image-plan.json"

# Recorder data-product routes
uv run python tools/public_records_actions.py plan \
    us-fl-miami-dade-official-records --operation request_bulk_files \
    --selector "Miami-Dade deed index" \
    --output "$WORKDIR/miami-recorder-plan.json"
uv run python tools/public_records_actions.py plan \
    us-tx-harris-clerk-real-property --operation request_bulk_index \
    --selector "Harris County real-property index" \
    --output "$WORKDIR/harris-recorder-plan.json"

# Formal or request-based court complements
uv run python tools/public_records_actions.py plan us-pa-aopc-bulk \
    --operation request_bulk_distribution \
    --selector "Pennsylvania case metadata" \
    --output "$WORKDIR/pennsylvania-bulk-plan.json"
uv run python tools/public_records_actions.py plan us-de-court-records-access \
    --operation request_record_copy --selector "JP13-23-013991 filing" \
    --output "$WORKDIR/delaware-record-copy-plan.json"
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

### U.S. Tax Court DAWSON public API

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Optional petitioner name plus source-native case filters
uv run python tools/query_tax_court.py cases Hagee \
    --output "$WORKDIR/tax-court-cases.json"
uv run python tools/query_tax_court.py cases \
    --state CA --filed-after 2025-01-01 \
    --case-type Deficiency --procedure-type Regular \
    --output "$WORKDIR/tax-court-filtered-cases.json"

uv run python tools/query_tax_court.py case 455-22S \
    --output "$WORKDIR/tax-court-case.json"
uv run python tools/query_tax_court.py docket 455-22S \
    --output "$WORKDIR/tax-court-docket.json"
uv run python tools/query_tax_court.py docket 455-22S --page 0 \
    --output "$WORKDIR/tax-court-docket-page-0.json"

# Order and opinion full-text retrieval search
uv run python tools/query_tax_court.py orders --docket 455-22 \
    --output "$WORKDIR/tax-court-orders.json"
uv run python tools/query_tax_court.py opinions \
    --keyword '"innocent spouse"' --opinion-type memorandum \
    --output "$WORKDIR/tax-court-opinions.json"

# Current releases and source directories
uv run python tools/query_tax_court.py today-orders \
    --sort filing-date-desc --output "$WORKDIR/tax-court-today-orders.json"
uv run python tools/query_tax_court.py today-opinions \
    --output "$WORKDIR/tax-court-today-opinions.json"
uv run python tools/query_tax_court.py judges \
    --output "$WORKDIR/tax-court-judges.json"
uv run python tools/query_tax_court.py trial-sessions \
    --output "$WORKDIR/tax-court-trial-sessions.json"
uv run python tools/query_tax_court.py trial-session "<TRIAL_SESSION_ID>" \
    --output "$WORKDIR/tax-court-trial-session.json"

# Public source document and printable docket record
uv run python tools/query_tax_court.py download 455-22 \
    "<DOCKET_ENTRY_ID>" "$WORKDIR/tax-court-entry.pdf" \
    --output "$WORKDIR/tax-court-entry.json"
uv run python tools/query_tax_court.py docket-pdf 455-22 \
    "$WORKDIR/tax-court-docket.pdf" \
    --output "$WORKDIR/tax-court-docket-pdf.json"
uv run python tools/query_tax_court.py probe \
    --output "$WORKDIR/tax-court-probe.json"
```

Case search has a native 5,000-row ceiling and no source pagination;
`cases --limit` slices the returned source rows. Orders and opinions have a
5,000-row source ceiling and request that full ceiling by default.
`today-opinions` has a 200-row ceiling. Docket pages are zero-based `0`–`20`
with 1,000 rows per page; omitting `--page` returns all source-accessible
pages. Today's Orders pages are one-based with 100 rows per page; omitting
`--page` returns all reported pages.

DAWSON is the primary official case/docket/document route. Tax Court Reports
pamphlets are a separate official published-opinion archive; the clerk and
reporter provide copies, certification, and transcripts; GovInfo `USCOURTS`
court code `tc` and CourtListener provide additional opinion/citation and
historical discovery. A docket row is metadata, while a downloaded filing,
order, opinion, or printable docket is the corresponding court record.

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

### DOJ Epstein court-record release adapter

`query_doj_court_records.py` indexes the case-grouped Court Records section of
DOJ's consolidated Epstein disclosures and follows each exact case page's
native pagination. The emitted rows describe DOJ's release corpus: they do not
represent a complete underlying court docket and are not normalized into the
court-case sidecar.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Current release case groups and one exact case group's documents
uv run python tools/query_doj_court_records.py index \
    --query "United States v. Epstein" \
    --output "$WORKDIR/doj-court-case-groups.json"
uv run python tools/query_doj_court_records.py case \
    "https://www.justice.gov/epstein/doj-disclosures/court-records-united-states-v-epstein-no-119-cr-00490-sdny-2019" \
    --output "$WORKDIR/doj-court-documents.json"

# Source roles, former-link resolution, and validated PDF acquisition
uv run python tools/query_doj_court_records.py sources \
    --output "$WORKDIR/doj-court-sources.json"
uv run python tools/query_doj_court_records.py recover "$FORMER_DOJ_PDF_URL" \
    --output "$WORKDIR/doj-court-recovery.json"
uv run python tools/query_doj_court_records.py download \
    "$INDEXED_DOJ_PDF_URL" "$WORKDIR/document.pdf" \
    --output "$WORKDIR/doj-court-download.json"

# Shared routing: corpus search, exact case-page documents, discovery, probe
uv run python tools/query_state_courts.py search "United States v. Epstein" \
    --source us-doj-epstein-court-records \
    --output "$WORKDIR/doj-court-shared-search.json"
uv run python tools/query_state_courts.py documents "$DOJ_CASE_PAGE_URL" \
    --source us-doj-epstein-court-records \
    --output "$WORKDIR/doj-court-shared-documents.json"
uv run python tools/query_state_courts.py discovery \
    --source us-doj-epstein-court-records \
    --output "$WORKDIR/doj-court-shared-sources.json"
uv run python tools/query_state_courts.py probe \
    --source us-doj-epstein-court-records \
    --output "$WORKDIR/doj-court-shared-probe.json"

# Lifecycle monitor: one index page, one sentinel case page, five PDF bytes
uv run python tools/public_records_monitor.py run \
    us-doj-epstein-court-records \
    --output "$WORKDIR/doj-court-monitor.json"
```

Omitting `--limit` returns every matching case group or follows every native
document page. Direct and shared DOJ routes use a `0.0`-second interval when
the caller omits pacing; an explicit shared `--minimum-interval` is forwarded
unchanged. A caller-limited document listing returns a checksum-protected v2
cursor bound to the canonical case URL, current page URL, page fingerprint,
and offset. The three-request probe separates stable source, identity, schema,
route, cursor, and request contracts from rolling release counts, page shape,
and PDF response metadata.

Published EFTA identifiers are the preferred document identity; the fallback
is canonical case slug plus filename. `recover` accepts a replacement only
when the current listing has an exact EFTA or filename match. PACER/CM/ECF,
CourtListener/RECAP, the named court clerk, Wayback, and the local EFTA/OCR
corpus remain separately attributable routes. Use
`[DOJCOURT:EFTA02824136]` for an exact mapped release-document citation.

### New York OCA attorney-registration adapter

`query_ny_attorneys.py` uses official NY Open Data dataset `eqw2-r5nb`.
`registration_number` is the record identity, company values remain whole
publisher organization names, and limited searches use a checksum-protected v2
cursor bound to the query and quarterly snapshot.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Direct adapter
uv run python tools/query_ny_attorneys.py sources \
    --output "$WORKDIR/ny-attorney-sources.json"
uv run python tools/query_ny_attorneys.py search \
    --company "ACME HOLDINGS, LLC" \
    --output "$WORKDIR/ny-attorney-company.json"
uv run python tools/query_ny_attorneys.py registration 2064509 \
    --output "$WORKDIR/ny-attorney-registration.json"
uv run python tools/query_ny_attorneys.py probe \
    --output "$WORKDIR/ny-attorney-probe.json"

# Shared state-court routing: search, exact detail, discovery, and probe
uv run python tools/query_state_courts.py search "Example Attorney" \
    --source us-ny-oca-attorney-registrations --jurisdiction NY \
    --output "$WORKDIR/ny-attorney-shared-search.json"
uv run python tools/query_state_courts.py detail 2064509 \
    --source us-ny-oca-attorney-registrations --jurisdiction 36 \
    --output "$WORKDIR/ny-attorney-shared-detail.json"
uv run python tools/query_state_courts.py discovery \
    --source us-ny-oca-attorney-registrations --jurisdiction US-NY \
    --output "$WORKDIR/ny-attorney-shared-discovery.json"
uv run python tools/query_state_courts.py probe \
    --source us-ny-oca-attorney-registrations --jurisdiction "New York" \
    --output "$WORKDIR/ny-attorney-shared-probe.json"

# Lifecycle monitor: metadata, sentinel count/query, final metadata,
# and statewide count
uv run python tools/public_records_monitor.py run \
    us-ny-oca-attorney-registrations \
    --output "$WORKDIR/ny-attorney-monitor.json"
```

The five monitor requests hold dataset, registration, schema, cursor, and
complementary-route identity stable while recording current totals,
`rowsUpdatedAt`, and sentinel contents as rolling observations. The quarterly
open dataset, interactive OCA directory, 22 NYCRR 118.2 written-request data,
Appellate Division discipline publications, and NYSCEF case filings retain
their own provenance. Attorney-registration rows are not normalized as court
cases.

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

After acquiring a case document list and its PDFs, the local full-text
processor can normalize identities, extract text with targeted OCR, build an
incremental SQLite FTS5 index, and search it with page-level evidence:

```bash
uv run python tools/query_nyscef_fulltext.py sources \
    --output "$WORKDIR/nyscef-fulltext-sources.json"
uv run python tools/query_nyscef_fulltext.py probe \
    --output "$WORKDIR/nyscef-fulltext-probe.json"
uv run python tools/query_nyscef_fulltext.py normalize \
    "$WORKDIR/nyscef-documents.json" \
    --output "$WORKDIR/nyscef-normalized.json"
uv run python tools/query_nyscef_fulltext.py extract \
    "$WORKDIR/filings/document-7.pdf" \
    --case-number 156728/2019 \
    --court "New York County Supreme Court" \
    --document-number 7 \
    --output "$WORKDIR/nyscef-document-7-text.json"
uv run python tools/query_nyscef_fulltext.py index \
    "$WORKDIR/nyscef-documents.json" \
    --pdf-dir "$WORKDIR/filings" \
    --database "$WORKDIR/nyscef-fulltext.db" \
    --output "$WORKDIR/nyscef-index.json"
uv run python tools/query_nyscef_fulltext.py search \
    "$WORKDIR/nyscef-fulltext.db" '"EXAMPLE HOLDINGS LLC"' \
    --mode fts --mention-name "EXAMPLE HOLDINGS LLC" \
    --output "$WORKDIR/nyscef-hits.json"
uv run python tools/query_nyscef_fulltext.py stats \
    "$WORKDIR/nyscef-fulltext.db" \
    --output "$WORKDIR/nyscef-stats.json"
```

The processor retains case, document, artifact-version, and page identities.
Search filters include case number, county, document type, filer, and filed
date. Mention checks distinguish listed parties, non-party candidates, and
manifests that did not contain a party list. The main NYSCEF adapter and the
local processor share `us-ny-nyscef`; this is a processing capability, not a
second authoritative source.

### New York Law Reporting Bureau decisions

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Current RSS windows and advertised monthly archives
uv run python tools/query_ny_law_reports.py rss --collection all \
    --output "$WORKDIR/ny-law-rss.json"
uv run python tools/query_ny_law_reports.py archives --collection all \
    --output "$WORKDIR/ny-law-archives.json"

# Current or one archived month of Selected Trial/Other or Commercial decisions
uv run python tools/query_ny_law_reports.py index --collection other \
    --output "$WORKDIR/ny-law-current.json"
uv run python tools/query_ny_law_reports.py index --collection commercial \
    --year 2026 --month 6 \
    --output "$WORKDIR/ny-law-commercial-2026-06.json"

# Exact official opinion and full-body search within one selected source window
uv run python tools/query_ny_law_reports.py opinion 2026_26113 \
    --output "$WORKDIR/ny-law-opinion.json"
uv run python tools/query_ny_law_reports.py search "fraudulent conveyance" \
    --collection commercial --year 2026 --month 6 \
    --match-mode phrase --output "$WORKDIR/ny-law-body-search.json"
uv run python tools/query_ny_law_reports.py sentinel \
    --output "$WORKDIR/ny-law-sentinel.json"
```

RSS, current-index, monthly-index, and body-search commands return all rows
from the selected source window by default. `--limit` is optional and has no
adapter maximum. The source partitions its archive into one page per month,
not numbered result pages. Results preserve official opinion metadata and full
HTML body text. Linked PDFs remain discoverable but are not counted as
searched HTML bodies.

Law Reporting Bureau decisions are official opinion publications, not a
complete docket or filing-body repository. Use their NYSCEF document
references, parties, counsel, and procedural facts to pivot to NYSCEF or clerk
copies for the underlying filings. CourtListener supplies a separate broader
opinion/citation/docket discovery layer.

### New York Column public notices

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# All source-reported pages return by default
uv run python tools/query_ny_column.py search "EXAMPLE HOLDINGS LLC" \
    --output "$WORKDIR/ny-column-notices.json"

# Repeat source facets to partition a broad notice search
uv run python tools/query_ny_column.py search "mortgage" \
    --start-date 2026-01-01 --end-date 2026-06-30 \
    --county "New York" --county "Kings" \
    --notice-type "Foreclosure Sale" \
    --newspaper "New York Law Journal" --filer "<FILER_ID>" \
    --output "$WORKDIR/ny-column-foreclosures.json"

uv run python tools/query_ny_column.py sentinel \
    --output "$WORKDIR/ny-column-sentinel.json"
```

The source uses one-indexed pages and displays at most 10,000 matches per
partition. The adapter returns all source-reported pages by default;
`--limit` is optional. Dates and repeatable county, notice-type, newspaper,
and filer facets support narrower partitions. Results retain full notice text,
PDF URL, notice/filer IDs, notice type, publication/newspaper metadata,
publication date, county/state, and raw source metadata. These are newspaper
public notices and discovery pivots, not court filings.

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

### Orleans Parish Property Viewer (ArcGIS)

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_orleans_property.py owner "CITY OF NEW ORLEANS" \
    --limit 25 --output "$WORKDIR/orleans-owner.json"
uv run python tools/query_orleans_property.py address "1300 PERDIDO" \
    --output "$WORKDIR/orleans-address.json"
uv run python tools/query_orleans_property.py account "<TAXBILLID>" --geometry \
    --output "$WORKDIR/orleans-account.json"
uv run python tools/query_orleans_property.py parcel "<PARCELID>" --geometry \
    --output "$WORKDIR/orleans-parcel.json"
uv run python tools/query_orleans_property.py search "PERDIDO" \
    --output "$WORKDIR/orleans-search.json"
```

The adapter uses the official City Property Viewer locator and rich
`TaxParcelPublishing` MapServer layer; viewer layer 15 remains cataloged as
the application parcel surface. The public UI describes weekly Assessor and
City data. `TAXBILLID` identifies an assessment account;
`PARCELID` (GeoPIN) and retained `PARID` support physical-parcel joins, and
multiple assessment accounts can share a GeoPIN. The published layer is a
current assessment/parcel snapshot with polygon geometry, not a historical
assessment or deed/title collection. Normalized rows combine `TAXBILLID`,
`PARCELID`, and `PARID` into a collision-tolerant row key while retaining all
three source identifiers independently for lookup and joins.

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
python tools/ingest_sec_enforcement.py stats                            # Summary counts + body coverage
python tools/ingest_sec_enforcement.py reparse                          # Re-run defendant parsing

# Release text (separate resumable pass — `ingest` stores index metadata only)
python tools/ingest_sec_enforcement.py fetch-bodies                     # Backfill all missing bodies
python tools/ingest_sec_enforcement.py fetch-bodies --start 2021-01-01 --end 2025-12-31
python tools/ingest_sec_enforcement.py fetch-bodies --source litigation --workers 4
python tools/ingest_sec_enforcement.py fetch-bodies --retry-failed       # Re-attempt transport failures

# Query
python tools/query_sec_enforcement.py search "insider trading" --output $WORKDIR/sec-search.json
python tools/query_sec_enforcement.py search "Epstein" --source litigation --output $WORKDIR/sec-epstein.json
python tools/query_sec_enforcement.py search "10b-5" --with-body --output $WORKDIR/sec-10b5.json
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

Statutory/conduct queries (`10b-5`, `Section 10(b)`) only work on rows whose text
`fetch-bodies` has retrieved; `search` reports `body_chars` per result and warns
when a match is metadata-only. `ingest` alone leaves `body_text` NULL.

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
uv run python scripts/queue_dispatcher.py --dry-run run

# Show pending vs active by persona
uv run python scripts/queue_dispatcher.py status

# Daemon mode: poll every N seconds
uv run python scripts/queue_dispatcher.py daemon
uv run python scripts/queue_dispatcher.py daemon --poll-interval 60
```

## Investigation Dispatcher (unattended)

Optional unattended dispatcher — launches headless Claude Code instances based on lead priorities, triage scheduler fields (depth_tier, recommended_skill), and analysis cooldowns when this execution path is explicitly selected. Interactive investigations use native subagents supervised in the current chat. Uses `dispatch_runs` table. Config: `scripts/dispatch_config.json`; its unset model inherits the CLI configuration. See the execution contract for staging, review, import, and retained process limits.

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
